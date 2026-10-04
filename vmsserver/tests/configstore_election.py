#!/usr/bin/env python3
"""Do the workers' leases survive a raft leader election? — measured, not argued (the note on the cluster without an
orchestrator, open question 1; the notes on the raft prototype have the prototype's numbers).

Not part of the suite: it kills processes for minutes, and needs the raft library (`pip install pysyncobj
cryptography`). Run as

    python3 tests/configstore_election.py                          # the library's default timings, 25 kills
    python3 tests/configstore_election.py --timing lan --kills 25
    python3 tests/configstore_election.py --mode stop              # the leader frozen (SIGSTOP), not killed

What it does, on one machine, with real processes where a deployment has them:

  1. three `configstore` daemons (`python3 -m w2cplatform.configstore`), each on its own ports, journal and socket
     directory, the raft port with its secret and the `-api` door with the test certificates (`tests/tls/`): a group
     of one (`-bootstrap`), then two servers joining it (`-join`) — as a box becomes a cluster;
  2. workers — the platform's own `Worker`, not a model of it — spread over the three servers, each holding its slot
     and `--units` epochs with the course's numbers (`lease_ttl`, `lease_margin`, `slot_ttl`: the `Worker`
     defaults, `w2cplatform/contract.py`), renewing as `vms/worker.py` `run` does: a lease step when
     `(lease_ttl − lease_margin)/3` has passed, looked at every `poll` (2 s) — so every ~10 s; each through its own
     server's `admin.sock` (`configstore://…`), as a process talks only to its local daemon;
  3. a probe per server writing every 20 ms;
  4. `--kills` times: find the leader, SIGKILL it (or SIGSTOP), measure until the probes on the two others write
     again, bring the killed one back with the same command line — it starts from its journal — (or SIGCONT), wait
     for it to catch up.

Per kill it reports the pause of writes, the longest a surviving worker's lease went unconfirmed (lost at
`lease_ttl − lease_margin`), the longest a slot went unrenewed (lapses at `slot_ttl`), and whether any lease would
have been lost. Workers on the killed server are counted apart: they die with their server.

TWO WAYS TO LOSE A LEASE, and only one of them is what `renew_leases` reports. `leases_lost` is a lease the
worker gave up: fenced, or found expired while the store was silent. `past_window` is a lease that went longer than
`lease_ttl − lease_margin` between two confirmations and was then confirmed again: `Lease.renew` takes an answer
with the same epoch as a renewal, so the worker carries on — but for those seconds `may_write` was false and its
writes stood still. Both are counted; the second is the one the slow timings produce.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from w2cplatform.configstore import TUNINGS  # noqa: E402
from w2cplatform.contract import Subsystem, Worker  # noqa: E402
from w2cplatform.variables import open_vars  # noqa: E402

POLL = 2.0                     # `Worker.run`'s default `poll`: the lease step is LOOKED AT this often
NAMES = ("srv-a", "srv-b", "srv-c")
TLS = os.path.join(HERE, "tests", "tls")
for _name in NAMES:                # a checkout leaves them 0644; the daemon takes a raft secret only 0600 (`tls.raft_secret`)
    os.chmod(os.path.join(TLS, _name, "raft.secret"), 0o600)
ALIASES = {"defaults": "default", "fast": "lan"}     # the prototype's names for the same timings


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _status(node: "Node", timeout: float = 0.5) -> dict | None:
    try:
        return open_vars(node.url(f"timeout={timeout}")).status()
    except Exception:                                    # noqa: BLE001
        return None


class Node:
    def __init__(self, k: int, root: str, timing: str):
        self.k, self.timing, self.name = k, timing, NAMES[k]
        self.raft = f"127.0.0.1:{_port()}"
        self.api_port = _port()
        self.adv = f"{self.name}@127.0.0.1:{self.api_port}"
        self.data = os.path.join(root, f"d{k}")
        self.sockets = os.path.join(root, f"s{k}")
        self.proc: subprocess.Popen | None = None
        self.up = False
        self.join: str | None = None

    def url(self, query: str = "") -> str:
        return f"configstore://{self.sockets}/admin.sock" + (f"?{query}" if query else "")

    def start(self, join: str | None = None) -> None:
        self.join = join or self.join
        cmd = [sys.executable, "-m", "w2cplatform.configstore", "-id", self.name, "-dir", self.data,
               "-raft", self.raft, "-api", f"127.0.0.1:{self.api_port}", "-advertise", self.adv,
               "-sockets", self.sockets, "-tls", os.path.join(TLS, self.name), "-tuning", self.timing]
        cmd += ["-join", self.join] if self.join else ["-bootstrap"]
        self.proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.monotonic() + 60
        while _status(self) is None:
            if self.proc.poll() is not None or time.monotonic() > end:
                raise RuntimeError(f"node {self.k} did not come up")
            time.sleep(0.05)
        self.up = True


class Objects:
    def __init__(self): self.d = {}
    def put(self, k, b): self.d[k] = b
    def get(self, k): return self.d.get(k)
    def list(self, p): return sorted(k for k in self.d if k.startswith(p))


class _W(Worker):
    def reconcile_once(self, now=None):
        return []


class Sim:
    """One worker: the slot and its units' leases, renewed the way `vms/worker.py` `run` renews them."""

    def __init__(self, i: int, node: Node, units: int, timeout: float):
        self.node = node
        self.w = _W(Subsystem("bench"), None, open_vars(node.url(f"timeout={timeout}")), Objects())
        self.w.claim_slot(prefer=f"w-{i}")
        for u in range(units):
            self.w.take_epoch(f"{i}-{u}")
        self.lock = threading.Lock()
        self.max_gap = 0.0          # the longest a lease went between two confirmations, this round
        self.slot_gap = 0.0         # the same for the slot row (wall clock, as `until` is)
        self.failed = 0             # renewals the store did not answer, this round
        self.pass_max = 0.0         # the longest one lease step took, this round
        self.start_gap = 0.0        # the longest between two lease steps' starts, this round
        self.lost: list[str] = []   # leases `renew_leases` gave up, ever
        self.slot_lost = False
        self.past_window = 0        # confirmations that came later than `lease_ttl − lease_margin`, this round
        self.last_slot_ok = time.time()
        self.last_slot_mono = time.monotonic()
        # Every gap closed, as (kind, when it began, how long): the report counts a gap against the round it CLOSED
        # in — the round whose kill opened it, since a round ends only when every gap is closed again.
        self.gaps: list[tuple[str, float, float]] = []

    def lease_pass(self) -> None:
        w = self.w
        before = {u: l.last_renewal for u, l in w.leases.items()}
        try:
            if w.renew_slot():
                now, mono = time.time(), time.monotonic()
                with self.lock:
                    self.slot_gap = max(self.slot_gap, now - self.last_slot_ok)
                    self.gaps.append(("slot", self.last_slot_mono, now - self.last_slot_ok))
                self.last_slot_ok, self.last_slot_mono = now, mono
            else:
                self.slot_lost = True
        except OSError:
            with self.lock:
                self.failed += 1
        lost = w.renew_leases()
        with self.lock:
            for u, l in w.leases.items():
                if l.last_renewal > before[u]:
                    self.max_gap = max(self.max_gap, l.last_renewal - before[u])
                    self.gaps.append(("lease", before[u], l.last_renewal - before[u]))
                    if l.last_renewal - before[u] >= w.lease_ttl - w.lease_margin:
                        self.past_window += 1
                elif u not in lost:
                    self.failed += 1
            self.lost += [u for u in lost if u not in self.lost]

    def run(self, stop: threading.Event) -> None:
        every = max(1.0, (self.w.lease_ttl - self.w.lease_margin) / 3)
        stop.wait(random.uniform(0, POLL))
        last = time.monotonic() - random.uniform(0, every)        # workers started at different moments
        started = None
        while not stop.wait(POLL):
            if time.monotonic() - last >= every:
                t0 = time.monotonic()
                self.lease_pass()
                last = time.monotonic()
                with self.lock:
                    self.pass_max = max(self.pass_max, last - t0)
                    if started is not None:
                        self.start_gap = max(self.start_gap, t0 - started)
                started = t0

    def take_round(self) -> tuple:
        with self.lock:
            out = (self.max_gap, self.slot_gap, self.failed, self.pass_max, self.start_gap, self.past_window)
            self.max_gap = self.slot_gap = self.pass_max = self.start_gap = 0.0
            self.failed = self.past_window = 0
        return out


class Probe:
    """Writes one row every 20 ms through one server's daemon; keeps (start, end, ok)."""

    def __init__(self, node: Node):
        self.node = node
        self.v = open_vars(node.url("timeout=1.0"))
        self.log: list[tuple[float, float, bool]] = []
        self.lock = threading.Lock()

    def run(self, stop: threading.Event) -> None:
        n = 0
        while not stop.is_set():
            t0 = time.monotonic()
            ok = True
            try:
                self.v.put(f"bench/probe/{self.node.k}", {"n": n})
            except OSError:
                ok = False
            t1 = time.monotonic()
            with self.lock:
                self.log.append((t0, t1, ok))
            n += 1
            stop.wait(max(0.0, 0.02 - (t1 - t0)))

    def back_after(self, t: float) -> float | None:
        """When the first write started after `t` came back done."""
        with self.lock:
            for t0, t1, ok in self.log:
                if t0 >= t and ok:
                    return t1
        return None

    def worst(self, a: float, b: float) -> float:
        with self.lock:
            return max([t1 - t0 for t0, t1, ok in self.log if a <= t0 <= b] or [0.0])


def leader_of(nodes: list[Node]) -> Node | None:
    for n in nodes:
        if n.up:
            s = _status(n)
            if s and s["state"] == "leader":
                return n
    return None


def caught_up(n: Node, nodes: list[Node], within: float = 60.0) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < within:
        lead = leader_of([m for m in nodes if m is not n])
        me, ls = _status(n), (_status(lead) if lead else None)
        if me and ls and me["leader"] and me["applied"] >= ls["commit"] - 50:
            return time.monotonic() - t0
        time.sleep(0.05)
    raise RuntimeError(f"node {n.k} did not catch up")


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", default="default", choices=sorted({*TUNINGS, *ALIASES}))
    ap.add_argument("--kills", type=int, default=25)
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--units", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=5.0, help="what one store call may take (the handle's)")
    ap.add_argument("--mode", default="kill", choices=["kill", "stop"])
    ap.add_argument("--out", help="write every round as JSON here")
    a = ap.parse_args()
    a.timing = ALIASES.get(a.timing, a.timing)

    root = tempfile.mkdtemp(prefix="cse", dir="/tmp")      # short: a unix socket's path is at most 104 bytes
    nodes = [Node(k, root, a.timing) for k in range(3)]
    nodes[0].start()
    for n in nodes[1:]:
        n.start(join=nodes[0].adv)
        caught_up(n, nodes)
    sims = [Sim(i, nodes[i % 3], a.units, a.timeout) for i in range(a.workers)]
    w0 = sims[0].w
    budget = w0.lease_ttl - w0.lease_margin
    print(f"timing={a.timing} {TUNINGS[a.timing] or '(library defaults)'} mode={a.mode} workers={a.workers} "
          f"units={a.units} leases={a.workers * a.units} lease_ttl={w0.lease_ttl:g} margin={w0.lease_margin:g} "
          f"slot_ttl={w0.slot_ttl:g} renew every {max(1.0, budget / 3):.2f} s looked at every {POLL:g} s", flush=True)
    probes = [Probe(n) for n in nodes]
    stop = threading.Event()
    threads = [threading.Thread(target=s.run, args=(stop,), daemon=True) for s in sims]
    threads += [threading.Thread(target=p.run, args=(stop,), daemon=True) for p in probes]
    for t in threads:
        t.start()
    time.sleep(12)                                                # every worker through one lease step at least
    for s in sims:
        s.take_round()

    rounds, spans = [], []
    t_start = time.monotonic()
    for r in range(a.kills):
        time.sleep(random.uniform(3, 10))                         # a random phase against the workers' steps
        lead = leader_of(nodes)
        if lead is None:
            time.sleep(2)
            lead = leader_of(nodes)
        others = [n for n in nodes if n is not lead]
        lost_before = {id(s): len(s.lost) for s in sims}
        t_kill = time.monotonic()
        lead.up = False
        if a.mode == "kill":
            lead.proc.send_signal(signal.SIGKILL)
            lead.proc.wait()
        else:
            lead.proc.send_signal(signal.SIGSTOP)
        backs = []
        while time.monotonic() - t_kill < 120:
            backs = [probes[n.k].back_after(t_kill) for n in others]
            if all(b is not None for b in backs):
                break
            time.sleep(0.02)
        pause = [b - t_kill for b in backs if b is not None]
        new_lead = leader_of(others)
        time.sleep(2)
        t_back = time.monotonic()
        if a.mode == "kill":
            lead.start()                                          # from its journal: -join is not asked again
        else:
            lead.proc.send_signal(signal.SIGCONT)
            lead.up = True
        catch = caught_up(lead, nodes)
        time.sleep(1)
        rejoin_worst = max(probes[n.k].worst(t_back, time.monotonic()) for n in others)
        # The round ends when every lease AND every slot has been confirmed since the killed server came back: a gap
        # this kill opened closes in this round, and is counted against the server its worker was on now. (Waiting
        # for the leases alone let a slot gap of the killed server close a round later, among the survivors.)
        end = time.monotonic() + 60
        while time.monotonic() < end and (any(l.last_renewal < t_back for s in sims for u, l in s.w.leases.items()
                                              if u not in s.lost) or any(s.last_slot_mono < t_back for s in sims)):
            time.sleep(0.2)
        spans.append((t_start, time.monotonic(), lead))
        t_start = time.monotonic()
        surv = [s for s in sims if s.node is not lead]
        dead = [s for s in sims if s.node is lead]
        got = {id(s): s.take_round() for s in sims}
        row = {
            "round": r + 1, "killed": lead.k, "new_leader": new_lead.k if new_lead else None,
            "pause_first": round(min(pause), 3) if pause else None, "pause_last": round(max(pause), 3) if len(pause) == 2 else None,
            "lease_gap_max": round(max(got[id(s)][0] for s in surv), 2),
            "slot_gap_max": round(max(got[id(s)][1] for s in surv), 2),
            "renewals_unanswered": sum(got[id(s)][2] for s in surv),
            "lease_step_max": round(max(got[id(s)][3] for s in surv), 2),
            "between_steps_max": round(max(got[id(s)][4] for s in surv), 2),
            "leases_lost": sum(len(s.lost) - lost_before[id(s)] for s in surv), "slots_lost": sum(s.slot_lost for s in surv),
            "past_window": sum(got[id(s)][5] for s in surv),
            "killed_server": {"lease_gap_max": round(max(got[id(s)][0] for s in dead), 2),
                              "leases_lost": sum(len(s.lost) - lost_before[id(s)] for s in dead),
                              "past_window": sum(got[id(s)][5] for s in dead)},
            "catch_up": round(catch, 2), "rejoin_worst_write": round(rejoin_worst, 3),
        }
        rounds.append(row)
        print(json.dumps(row), flush=True)

    stop.set()
    # The gaps, each against the round it closed in (`Sim.gaps`), the slots included — what the rows printed live
    # said about gaps is replaced by this.
    for row, (t0, t1, lead) in zip(rounds, spans):
        for who, key in ((lambda s: s.node is not lead, None), (lambda s: s.node is lead, "killed_server")):
            mine = [g for s in sims if who(s) for g in s.gaps if t0 <= g[1] + g[2] < t1]
            out = row if key is None else row[key]
            out["lease_gap_max"] = round(max([g[2] for g in mine if g[0] == "lease"] or [0.0]), 2)
            out["slot_gap_max"] = round(max([g[2] for g in mine if g[0] == "slot"] or [0.0]), 2)
            out["past_window"] = sum(1 for g in mine if g[0] == "lease" and g[2] >= budget)
            out["slot_lapsed"] = sum(1 for g in mine if g[0] == "slot" and g[2] >= w0.slot_ttl)
    for n in nodes:
        if n.proc and n.proc.poll() is None:
            n.proc.send_signal(signal.SIGCONT)
            n.proc.kill()
    pauses = [r["pause_last"] for r in rounds if r["pause_last"] is not None]
    gaps = [r["lease_gap_max"] for r in rounds]
    summary = {
        "timing": a.timing, "mode": a.mode, "kills": len(rounds), "budget": budget,
        "pause_s": {"min": min(pauses), "median": round(statistics.median(pauses), 3), "p90": pct(pauses, 0.9), "max": max(pauses)},
        "lease_gap_s": {"median": round(statistics.median(gaps), 2), "max": max(gaps)},
        "slot_gap_max_s": max(r["slot_gap_max"] for r in rounds),
        "slot_gap_max_on_the_killed_server_s": max(r["killed_server"]["slot_gap_max"] for r in rounds),
        "slots_lapsed_on_survivors": sum(r["slot_lapsed"] for r in rounds),
        "slots_lapsed_on_the_killed_server": sum(r["killed_server"]["slot_lapsed"] for r in rounds),
        "leases_lost_on_survivors": sum(r["leases_lost"] for r in rounds),
        "leases_lost_on_the_killed_server": sum(r["killed_server"]["leases_lost"] for r in rounds),
        "rounds_with_a_lost_lease": sum(1 for r in rounds if r["leases_lost"]),
        "rounds_with_a_lease_past_its_window": sum(1 for r in rounds if r["lease_gap_max"] >= budget),
        "leases_past_window_on_survivors": sum(r["past_window"] for r in rounds),
        "rounds_with_a_lease_past_its_window_on_the_killed_server": sum(1 for r in rounds if r["killed_server"]["lease_gap_max"] >= budget),
        "rejoin_worst_write_max": max(r["rejoin_worst_write"] for r in rounds),
        "renewals_unanswered": sum(r["renewals_unanswered"] for r in rounds),
    }
    print("SUMMARY " + json.dumps(summary), flush=True)
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"summary": summary, "rounds": rounds}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

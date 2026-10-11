"""The store's drills (ADR-0070, steps 1 and 4): what the product drills on its stand — `scripts/drills/recover.sh`, and the
nightly run's partition and power loss — run here on the course's own store, real raft (`pysyncobj`) on this machine's
loopback, three servers with the TLS bundles of `tests/tls/`. Each drill asks the two things the owner's blocker was
about: NO EPOCH IS ISSUED TWICE — an epoch is the fence of a single writer, and one issued twice is two writers of one
unit — and THE GROUP COMES BACK, three voters as declared (`-group-size 3`), one leader.

- recover: a group of three loses its majority while one member is BEHIND; `configstore recover` gives the group to that
  member — the floor under every epoch raised a generation before its daemon starts — and the group grows back to three
  only as declared: the second of three with `-force`, a plain one refused.
- partition: the leader is cut off from the other two, every message dropped both ways; the two elect and issue, the one
  cut off issues nothing (it cannot even read: reads go through the log), and when the network heals it follows.
- power loss: processes killed with SIGKILL — the leader, then all three at once — and started again from their
  journals. What this drill is NOT is a power cut of the machine: the library's journal is a memory-mapped file nobody
  syncs, the page cache outlives a killed process and would not outlive the power (`configstore.py`: TEACHING-ONLY, NOT
  DURABLE). The product's store syncs before it acknowledges; the course's says so instead.

Skipped where the raft library is not installed. Daemons are processes (`python3 -m w2cplatform.configstore`, the command
line an installation runs) for the recover and the power loss, and members in this process for the partition — the
messages are cut in the library's own transport, which a process apart would not let us reach."""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

import pytest

from w2cplatform.configstore import have_library
from w2cplatform.configstorevars import unix_transport
from w2cplatform.epoch import EPOCH_FLOOR_KEY, epoch_floor, generation_hours, hours_of, next_epoch
from w2cplatform.variables import open_vars

pytestmark = pytest.mark.skipif(not have_library(), reason="the raft library is not installed: pip install pysyncobj")

SOURCE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TLS = os.path.join(SOURCE, "tests", "tls")
NAMES = ("srv-a", "srv-b", "srv-c")
KEY = "drill/epoch/7"
for _name in NAMES:                                  # a checkout keeps no mode: the daemon refuses a secret others read
    os.chmod(os.path.join(TLS, _name, "raft.secret"), 0o600)


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait(what: str, ok, within: float = 30.0):
    end = time.monotonic() + within
    while True:
        try:
            got = ok()
            if got:
                return got
        except OSError:
            pass
        if time.monotonic() > end:
            raise AssertionError(f"waited {within:g} s for {what}")
        time.sleep(0.1)


def _metric(sock: str, name: str) -> float | None:
    code, raw = unix_transport(sock)("GET", "/metrics", None, {}, 5.0)
    for line in raw.decode().splitlines():
        if line.startswith(name + " "):
            return float(line.split()[-1])
    return None


class Daemon:
    """One server's daemon, a process: `-group-size 3`, `-tuning lan`, its own directory, sockets and log."""

    def __init__(self, root: str, name: str):
        self.root, self.name = root, name
        self.tls = os.path.join(TLS, name)
        self.raft, self.api_port = f"127.0.0.1:{_port()}", _port()
        self.adv = f"{name}@127.0.0.1:{self.api_port}"
        self.data, self.sockets = os.path.join(root, name), os.path.join(root, name + ".s")
        self.admin = os.path.join(self.sockets, "admin.sock")
        self.log = os.path.join(root, name + ".log")
        self.proc: subprocess.Popen | None = None

    def spawn(self, *flags: str) -> subprocess.Popen:
        cmd = [sys.executable, "-m", "w2cplatform.configstore", "-id", self.name, "-dir", self.data, "-raft", self.raft,
               "-api", f"127.0.0.1:{self.api_port}", "-advertise", self.adv, "-sockets", self.sockets, "-tls", self.tls,
               "-tuning", "lan", "-group-size", "3", *flags]
        with open(self.log, "a") as log:
            self.proc = subprocess.Popen(cmd, cwd=SOURCE, stdout=log, stderr=log)
        return self.proc

    def start(self, *flags: str) -> "Daemon":
        proc = self.spawn(*flags)
        _wait(f"{self.name}'s admin socket", lambda: proc.poll() is None and self.vars().status(), 60)
        return self

    def vars(self):
        return open_vars(f"configstore://{self.admin}?timeout=3")

    def status(self) -> dict:
        return self.vars().status()

    def leads(self) -> bool:
        return self.status()["state"] == "leader"

    def stop(self, sig=signal.SIGTERM) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(sig)
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None

    def wipe(self) -> None:
        shutil.rmtree(self.data, ignore_errors=True)


def _group(root: str) -> list[Daemon]:
    """Three, as an installation grows one: srv-a bootstraps, srv-b joins with -force (two is even), srv-c plainly."""
    a, b, c = (Daemon(root, n) for n in NAMES)
    a.start("-bootstrap")
    _wait("srv-a to lead", a.leads)
    b.start("-join", a.adv, "-force")
    c.start("-join", a.adv)
    _wait("three voters", lambda: _metric(a.admin, "configstore_raft_voters") == 3)
    return [a, b, c]


def _leader(ds: list[Daemon]) -> Daemon | None:
    for d in ds:
        try:
            if d.proc is not None and d.leads():
                return d
        except OSError:
            pass
    return None


def _back(ds: list[Daemon]) -> Daemon:
    """The group back: one leader, every member counting three voters of three declared, all caught up."""
    lead = _wait("a leader", lambda: _leader(ds))
    for d in ds:
        _wait(f"{d.name} to count three", lambda d=d: _metric(d.admin, "configstore_raft_voters") == 3
              and _metric(d.admin, "configstore_raft_voters_expected") == 3)
    commit = lead.status()["commit"]
    for d in ds:
        _wait(f"{d.name} to catch up", lambda d=d: d.status()["applied"] >= commit)
    return lead


def test_recover_from_the_member_that_was_behind_issues_no_epoch_twice_and_the_group_grows_back_as_declared():
    """The product's `scripts/drills/recover.sh`, step for step. srv-c holds epochs 1..3 and stops; the majority issues 4
    and 5 and is lost (srv-a killed, srv-b stopped). `configstore recover -id srv-c -peers srv-c=…` on srv-c's directory,
    its daemon started: the floor is 2^32, the next epoch of the unit 2^32+1 and of a new unit 2^32+1 — 4 and 5 are not
    issued again. srv-a, emptied, asks to join plainly: two voters, even — refused, at once, and the daemon does not run;
    with -force it joins; srv-b, emptied, joins plainly as the third. Three voters of three, and the next epoch, asked at
    srv-b, is 2^32+2. (The generation is `max(by the content + 1, the clock's hours since 2026-01-01)`, ADR-0070's
    addition: on this machine's clock the floor is its hour's generation, and the numbers follow it.)"""
    root = tempfile.mkdtemp(prefix="drill-")
    ds = []
    try:
        ds = _group(root)
        a, b, c = ds
        assert [next_epoch(a.vars(), KEY)[0] for _ in range(3)] == [1, 2, 3]
        commit = a.status()["commit"]
        _wait("srv-c to hold epoch 3", lambda: c.status()["applied"] >= commit)
        c.stop()
        assert [next_epoch(a.vars(), KEY)[0] for _ in range(2)] == [4, 5]       # the majority, without srv-c
        a.stop(signal.SIGKILL)
        b.stop()
        hour = generation_hours()
        out = subprocess.run([sys.executable, "-m", "w2cplatform.configstore", "recover", "-id", c.name, "-dir", c.data,
                              "-peers", f"{c.name}={c.raft}"], cwd=SOURCE, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        c.start()
        _wait("srv-c to lead", c.leads)
        floor = epoch_floor(c.vars())                    # max(by the content + 1, the clock's hours) << 32 (ADR-0070)
        assert floor % (1 << 32) == 0 and floor >> 32 >= max(1, hour) and floor < 1 << 53, floor
        assert next_epoch(c.vars(), KEY)[0] == floor + 1, "4 and 5 were issued before: two writers of one epoch"
        assert next_epoch(c.vars(), "drill/epoch/new")[0] == floor + 1
        a.wipe()
        b.wipe()
        refused = a.spawn("-join", c.adv)
        assert refused.wait(30) != 0                                           # said at once; it does not run
        with open(a.log) as f:
            assert "would make the group 2 voters: an even group" in f.read()
        a.start("-join", c.adv, "-force")
        b.start("-join", c.adv)
        lead = _back(ds)
        assert lead is c or lead in ds
        assert next_epoch(b.vars(), KEY)[0] == floor + 2
        said = c.vars().get(EPOCH_FLOOR_KEY)[0]
        assert said["floor"] == str(floor) and hours_of(said["generation_at"]) >= hour, said
    finally:
        for d in ds:
            d.stop(signal.SIGKILL)
        shutil.rmtree(root, ignore_errors=True)


def test_power_loss_of_the_leader_and_then_of_all_three_issues_no_epoch_twice_and_the_group_comes_back():
    """Processes killed (SIGKILL), not shut down: first the leader while epochs are being issued, then all three at once.
    Each is started again from its journal with the flags it ran with, none of them new. Every epoch the group CONFIRMED
    is above every one confirmed before it — none issued twice, whichever member was asked — and the group is back: one
    leader, three voters of three. (A killed process loses nothing of a memory-mapped journal; a power cut of the machine
    could — the store is teaching-only, not durable, and says so.)"""
    root = tempfile.mkdtemp(prefix="drill-")
    ds = []
    confirmed: list[int] = []

    def issue(n: int) -> None:
        for _ in range(n):
            for d in ds:                                                       # whichever member answers
                if d.proc is None:
                    continue
                try:
                    confirmed.append(next_epoch(d.vars(), KEY)[0])
                    break
                except OSError:
                    continue

    try:
        ds = _group(root)
        issue(5)
        lead = _leader(ds)
        lead.stop(signal.SIGKILL)
        _wait("a new leader", lambda: _leader([d for d in ds if d is not lead]))
        issue(5)
        lead.start()
        _back(ds)
        issue(3)
        for d in ds:
            d.stop(signal.SIGKILL)
        for d in ds:
            d.spawn()                                                          # all three at once, from their journals
        for d in ds:
            _wait(f"{d.name}'s admin socket", lambda d=d: d.vars().status(), 60)
        _back(ds)
        issue(3)
        assert len(confirmed) >= 14, confirmed
        assert all(x < y for x, y in zip(confirmed, confirmed[1:])), f"an epoch issued twice or backwards: {confirmed}"
        assert int(_leader(ds).vars().get(KEY)[0]["epoch"]) >= confirmed[-1]
    finally:
        for d in ds:
            d.stop(signal.SIGKILL)
        shutil.rmtree(root, ignore_errors=True)


def test_a_partition_leaves_the_leader_cut_off_issuing_nothing_and_it_follows_when_the_network_heals():
    """The leader cut off from the other two: every raft message between them dropped, both ways, in the library's own
    transport. The two elect a leader of a higher term and issue epochs; the one cut off answers «not done» or «do not
    know» (503) and issues nothing — not even a read goes through, reads are entries of the log. Healed, it follows the
    new term, and every member holds the same epoch: the count of the epochs the majority confirmed, none issued twice,
    the cut-off member's attempts never applied. Three voters of three, one leader."""
    from tests.test_configstore import Group, _caught_up

    g = Group(3)
    try:
        old = g.leader()
        rest = [m for m in g.members if m is not old]
        for _ in range(2):
            next_epoch(open_vars(old.url()), KEY)
        cut = {}

        def drop(m, others) -> None:
            t = m.daemon.backend.raft._SyncObj__transport
            send, gone = t.send, {o.raft for o in others}
            cut[m.name] = t
            t.send = lambda node, message: False if node.id in gone else send(node, message)

        drop(old, rest)
        for m in rest:
            drop(m, [old])
        new = _wait("the two to elect", lambda: next((m for m in rest if m.status()["state"] == "leader"), None))
        assert new.status()["term"] > old.status()["term"]
        issued = [next_epoch(open_vars(new.url()), KEY)[0] for _ in range(3)]
        assert issued == [3, 4, 5]
        try:
            next_epoch(open_vars(old.url(query="timeout=2")), KEY)
            raise AssertionError("the leader cut off issued an epoch")
        except OSError:                                                       # StoreUnavailable / StoreAmbiguous: 503
            pass
        for t in cut.values():
            del t.send                                                         # the network heals
        _wait("the old leader to follow", lambda: old.status()["state"] == "follower"
              and old.status()["term"] >= new.status()["term"])
        lead = g.leader()
        for m in g.members:
            _caught_up(m, lead)
            assert open_vars(m.url()).get(KEY)[0] == {"epoch": "5"}, m.name
            assert len(m.daemon.backend.raft.otherNodes) + 1 == 3
    finally:
        g.stop()

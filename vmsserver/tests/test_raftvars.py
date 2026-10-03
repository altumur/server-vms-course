"""`raft://` — the prototype of the replicated store (the owner's decision of 3 October; `w2cplatform/raftvars.py`,
the notes on the raft prototype). EXPERIMENTAL, and skipped where the raft library is not installed:

    pip install pysyncobj

What it proves: the contract suite every `Variables` backend is held to (`test_variables_contract.py`) is green
against a raft group of one and of three; a server that joins a running group gets its data; CAS conflicts across
servers; a write the daemon retried during an election is applied once; and the platform's own CAS loops run on it
with nothing changed. The leader-election measurement is not here — it kills processes for minutes:
`tests/raft_election.py`.

Groups here run with the `fast` timings (an election in 0.15–0.35 s) so that a fresh group per clause costs a
fraction of a second; the measurement runs the library's defaults as well."""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
import uuid

import pytest

from w2cplatform import raftvars
from w2cplatform.raftvars import RaftUnavailable, have_library
from w2cplatform.variables import Conflict, open_vars

pytestmark = pytest.mark.skipif(not have_library(), reason="the raft library is not installed: pip install pysyncobj")


def _addr() -> str:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"127.0.0.1:{port}"


def _url(store, query: str = "") -> str:
    return "raft://" + store.url[len("http://"):] + (f"?{query}" if query else "")


# Answered through the log: a leader exists and commits. A read leaves no row behind, so the clause that lists
# the store finds only what it wrote.
def _ready(store, within: float = 10.0) -> None:
    v = open_vars(_url(store, "timeout=1"))
    end = time.monotonic() + within
    while True:
        try:
            v.get("ready")
            return
        except OSError:
            if time.monotonic() > end:
                raise
            time.sleep(0.05)


def _caught_up(store, leader, within: float = 10.0) -> None:
    end = time.monotonic() + within
    while store.status()["applied"] < leader.status()["commit"]:
        if time.monotonic() > end:
            raise AssertionError(f"{store.self_addr} did not catch up: {store.status()} vs {leader.status()}")
        time.sleep(0.02)


class Group:
    """A box (a group of one), and as many servers joined to it as asked — each with its journal on disk."""

    def __init__(self, n: int, timing: str = "fast"):
        self.nodes = [raftvars.RaftStore(_addr(), [], tempfile.mkdtemp(), timing=timing)]
        _ready(self.nodes[0])
        for _ in range(n - 1):
            s = raftvars.join(_addr(), self.nodes[0].url, tempfile.mkdtemp(), timing=timing)
            self.nodes.append(s)
            _ready(s)
            _caught_up(s, self.nodes[0])

    def leader(self):
        for s in self.nodes:
            if s.status()["state"] == "leader":
                return s
        return None

    def stop(self) -> None:
        for s in self.nodes:
            try:
                s.stop()
            except Exception:                          # noqa: BLE001 — stopped already
                pass


def _contract_on(n: int) -> list[str]:
    """Every clause of the contract suite, each against a fresh group of `n`, through a member that is NOT the
    leader when there is one — the request crosses the group as a process's would."""
    from tests import test_variables_contract as contract
    clauses = [(name, fn) for name, fn in vars(contract).items() if name.startswith("test_") and callable(fn)]
    assert len(clauses) >= 13, "the contract suite shrank"
    failed = []
    saved = os.environ.get("CONTRACT_URL")
    for name, fn in clauses:
        g = Group(n)
        try:
            leader = g.leader()
            via = next((s for s in g.nodes if s is not leader), g.nodes[0])
            os.environ["CONTRACT_URL"] = _url(via)
            try:
                fn()
            except Exception as e:                     # noqa: BLE001 — collected and reported by clause
                failed.append(f"{name}: {type(e).__name__}: {e}")
        finally:
            if saved is None:
                os.environ.pop("CONTRACT_URL", None)
            else:
                os.environ["CONTRACT_URL"] = saved
            g.stop()
    return failed


def test_the_variables_contract_holds_on_a_raft_group_of_one():
    """A box is a group of one, and its store is held to the same file as `file://` and `memory://` — every clause."""
    failed = _contract_on(1)
    assert not failed, "\n".join(failed)


def test_the_variables_contract_holds_on_a_raft_group_of_three():
    """Three servers, the handle on a follower: every write and every read for CAS is forwarded to the leader by the
    library, and the contract cannot tell."""
    failed = _contract_on(3)
    assert not failed, "\n".join(failed)


def test_a_server_that_joins_a_running_group_gets_its_data():
    """The note's «from one server to three without a migration»: rows written on the box are on the third server once
    it has joined — at the same versions, because a version is the log's index and the log is one — and the group
    of three goes on writing when the box that started it is gone."""
    g = Group(1)
    try:
        box = open_vars(_url(g.nodes[0]))
        written = {f"vms/cameras/{k}": box.put(f"vms/cameras/{k}", {"k": k}, cas=0) for k in range(50)}
        for _ in range(2):
            s = raftvars.join(_addr(), g.nodes[0].url, tempfile.mkdtemp(), timing="fast")
            g.nodes.append(s)
            _ready(s)
        third = g.nodes[2]
        _caught_up(third, g.nodes[0])
        local = open_vars(_url(third, "reads=local"))                  # its own copy, not the leader's answer
        assert local.list("vms/cameras/") == sorted(written)
        assert all(local.get(k)[1] == idx for k, idx in written.items()), "a joined server holds other versions"
        assert sorted(g.nodes[0].members()) == sorted(s.self_addr for s in g.nodes)

        g.nodes[0].stop()                                              # the box that started it all
        v3 = open_vars(_url(third))
        _ready(third)
        i = v3.put("vms/cameras/0", {"k": "moved"}, cas=written["vms/cameras/0"])
        assert v3.get("vms/cameras/0") == ({"k": "moved"}, i)
        assert open_vars(_url(g.nodes[1])).get("vms/cameras/0") == ({"k": "moved"}, i)
    finally:
        g.stop()


def test_cas_conflicts_across_servers():
    """One key, three writers on three servers, one version to write against: one wins, two get `Conflict` — and what
    one server wrote, a read on another sees at once (reads go through the log), so a version read anywhere is a
    version the next CAS anywhere is judged against."""
    g = Group(3)
    try:
        hs = [open_vars(_url(s)) for s in g.nodes]
        won, refused = [], []

        def go(k):
            try:
                hs[k].put("vms/slots/w-1", {"holder": f"on-{k}"}, cas=0)
                won.append(k)
            except Conflict:
                refused.append(k)

        ts = [threading.Thread(target=go, args=(k,)) for k in range(3)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert len(won) == 1 and len(refused) == 2, (won, refused)
        items, idx = hs[(won[0] + 1) % 3].get("vms/slots/w-1")      # read on ANOTHER server, at once
        assert items == {"holder": f"on-{won[0]}"}

        j = hs[1].put("vms/slots/w-1", {"holder": "renewed"}, cas=idx)
        for k in (0, 2):
            with pytest.raises(Conflict):                             # the version it read has moved, on another server
                hs[k].put("vms/slots/w-1", {"holder": f"late-{k}"}, cas=idx)
        with pytest.raises(Conflict):
            hs[2].delete("vms/slots/w-1", cas=idx)
        assert hs[0].get("vms/slots/w-1") == ({"holder": "renewed"}, j)
        hs[2].delete("vms/slots/w-1", cas=j)
        assert hs[0].get("vms/slots/w-1") == (None, 0)
    finally:
        g.stop()


def test_a_write_retried_after_its_first_copy_landed_is_applied_once():
    """During an election the library reports «leader changed» or «unknown outcome» for a command the old leader had
    already appended, and which may yet commit. Retried as a new write, a CAS would conflict with its own first copy
    — and a slot renewal that comes back `Conflict` fences the worker. So a write carries an operation id and the
    state machine answers a repeat with the first answer: same index, nothing applied twice. Asked here as the
    daemon's retry asks it, by the same id."""
    g = Group(3)
    try:
        v = open_vars(_url(g.nodes[1]))
        idx = v.put("vms/slots/w-2", {"holder": "a"}, cas=0)
        op = uuid.uuid4().hex
        body = {"path": "vms/slots/w-2", "items": {"holder": "a", "until": "1"}, "cas": idx, "op": op}
        first = raftvars._http_json("POST", g.nodes[1].url + "/v1/put", body)
        again = raftvars._http_json("POST", g.nodes[2].url + "/v1/put", body)      # the retry, through another server
        assert first == again, (first, again)
        assert v.get("vms/slots/w-2") == ({"holder": "a", "until": "1"}, first["index"])
        with pytest.raises(Conflict):                                 # a DIFFERENT write against the same version
            v.put("vms/slots/w-2", {"holder": "b"}, cas=idx)
    finally:
        g.stop()


def test_the_platforms_cas_loops_run_on_raft_unchanged():
    """The seam's promise, run: two workers on two servers take a slot each, take epochs, renew — and the second
    taking a unit the first holds fences the first on its next renewal, as on files. Nothing in the platform knows
    which store answered."""
    from w2cplatform.contract import Subsystem, Worker

    class _W(Worker):
        def reconcile_once(self, now=None):
            return []

    class _Objects:
        def __init__(self): self.d = {}
        def put(self, k, b): self.d[k] = b
        def get(self, k): return self.d.get(k)
        def list(self, p): return sorted(k for k in self.d if k.startswith(p))

    g = Group(3)
    try:
        sub = Subsystem("vms")
        a = _W(sub, None, open_vars(_url(g.nodes[1])), _Objects())
        b = _W(sub, None, open_vars(_url(g.nodes[2])), _Objects())
        assert a.claim_slot() == "w-1" and b.claim_slot() == "w-2"   # w-1 is taken by CAS, on another server
        assert a.take_epoch("7") == 1 and a.renew_slot() and a.renew_leases() == []
        assert b.take_epoch("7") == 2                                 # somebody else started the unit
        assert a.renew_leases() == ["7"] and a.leases["7"].fenced
        assert b.renew_leases() == [] and b.renew_slot()
        a.release_slot()
        assert open_vars(_url(g.nodes[0])).get("vms/slots/w-1")[0]["released"] == "true"
    finally:
        g.stop()


def test_an_answer_cut_off_by_a_dying_daemon_is_not_an_answer():
    """Found by the measurement, at the fifteenth leader kill: the daemon sent its headers and was killed before the
    body, and `http.client.IncompleteRead` — an `HTTPException`, not an `OSError` — flew out of the handle and out of
    `renew_slot`. Whatever a daemon does while dying, the handle says «the store did not answer» (`RaftUnavailable`):
    a cut-off body, a body that is not JSON, a connection closed before any answer. Never `ValueError`, which reads
    as «not a key». A door that misbehaves on purpose stands in for the dying daemon."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Dying(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if "cut" in self.path:
                self.send_response(200)
                self.send_header("Content-Length", "27")
                self.end_headers()
                self.wfile.write(b'{"items"')                # and then nothing: the process is gone
            elif "garbage" in self.path:
                self.send_response(200)
                self.send_header("Content-Length", "5")
                self.end_headers()
                self.wfile.write(b"<html")
            else:
                self.connection.close()                       # not even a status line
            self.close_connection = True

        do_POST = do_GET

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Dying)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        v = open_vars(f"raft://127.0.0.1:{srv.server_address[1]}?timeout=2")
        for key in ("vms/cut/1", "vms/garbage/1", "vms/silent/1"):
            with pytest.raises(RaftUnavailable):
                v.get(key)
        with pytest.raises(RaftUnavailable):
            v.list("vms/cut/")
        with pytest.raises(RaftUnavailable):
            v.put("vms/silent/1", {"x": "1"})
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_group_without_a_majority_does_not_answer_and_does_not_refuse():
    """Two of three gone: the last one cannot commit anything. Its handle says so as `RaftUnavailable` — an `OSError`,
    which every caller reads as «the store did not answer» (a worker keeps what it holds; feedback BC) — and never
    as `Conflict`, which would fence it. Reads too: a read through the log needs a majority like a write."""
    g = Group(3)
    try:
        v = open_vars(_url(g.nodes[0], "timeout=1.5"))
        idx = v.put("vms/epoch/9", {"epoch": 1}, cas=0)
        for s in g.nodes[1:]:
            s.stop()
        t0 = time.monotonic()
        with pytest.raises(RaftUnavailable):
            v.put("vms/epoch/9", {"epoch": 2}, cas=idx)
        with pytest.raises(OSError):
            v.get("vms/epoch/9")
        assert time.monotonic() - t0 < 5.0, "the handle waited past its own timeout"
    finally:
        g.stop()

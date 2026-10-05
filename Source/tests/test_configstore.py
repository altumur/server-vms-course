"""`configstore` on real raft — the daemon (`w2cplatform/configstore.py`) with `pysyncobj` behind it, in groups of
one and three, joined through the members' mutual-TLS doors as servers join. Skipped where the raft library is not
installed (`pip install pysyncobj cryptography`): the main suites run without it, and the machine, the API, the
handle and the doors are proved without it in `test_storemachine.py` and `test_configstorevars.py`.

What it proves: the contract suite holds on a group of one and of three (the handle on a follower's socket); a
server that joins a running group gets its data at the same versions; the group goes on writing when its leader is
killed; CAS conflicts across servers; a write retried with its id is applied once; a group without a majority says
«not answered», never «no»; a role's socket refuses what the role may not do before anything is forwarded; the
`-api` door refuses a join without a daemon's certificate; a member restarted on its journal comes back; and the
platform's own CAS loops run on it unchanged. The leader-election measurement is not here — it kills processes for
minutes: `tests/configstore_election.py`.

Groups run with the `lan` tuning (an election in 0.15–0.35 s) so a fresh group per clause costs a fraction of a
second; the measurement runs the library's defaults as well."""
from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import tempfile
import threading
import time
import uuid

import pytest

from w2cplatform import configstore, tls
from w2cplatform.configstore import StoreDaemon, have_library
from w2cplatform.configstorevars import StoreAmbiguous, StoreUnavailable
from w2cplatform.storemachine import Rights
from w2cplatform.variables import Conflict, Forbidden, open_vars

pytestmark = pytest.mark.skipif(not have_library(), reason="the raft library is not installed: pip install pysyncobj")

HERE = os.path.dirname(os.path.abspath(__file__))
TLS = os.path.join(HERE, "tls")
NAMES = ("srv-a", "srv-b", "srv-c")                  # one TLS bundle each under tests/tls/
# A checkout keeps no mode but the executable bit, so the bundles' secrets come out 0644 — and the daemon refuses a raft
# secret others can read (`tls.raft_secret`, the review's twelfth pass). `w2c-ca.sh` writes them 0600; so does this.
for _name in NAMES:
    os.chmod(os.path.join(TLS, _name, "raft.secret"), 0o600)
RIGHTS = Rights.parse({"roles": {
    # `platform/schema` too: a worker checks the store's schema version before it runs (`contract.check_schema`).
    "testsubworker": {"read": ["testsub/*", "platform/schema"], "write": ["testsub/epoch/*", "testsub/slots/*"],
                  "delete": ["testsub/slots/*"]},
}})


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Member:
    def __init__(self, group: "Group", k: int, join: str | None):
        self.k, self.name = k, NAMES[k]
        self.tls = os.path.join(TLS, self.name)
        self.raft = f"127.0.0.1:{_port()}"
        self.api_port = _port()
        self.adv = f"{self.name}@127.0.0.1:{self.api_port}"
        self.data = os.path.join(group.root, f"d{k}")
        self.sockets = os.path.join(group.root, f"s{k}")
        self.tuning = group.tuning
        self.daemon = None
        self.start(join, group.index_base)

    def start(self, join: str | None = None, index_base: int = 0) -> None:
        backend = configstore.start_member(self.name, self.data, self.raft, bootstrap=join is None, join=join,
                                           tls_dir=self.tls, tuning=self.tuning, index_base=index_base,
                                           api_advertised=self.adv)
        self.daemon = StoreDaemon(backend, node_id=self.name, sockets=self.sockets, rights=RIGHTS,
                                  api=("127.0.0.1", self.api_port), tls_dir=self.tls, api_advertised=self.adv)

    def url(self, role: str = "admin", query: str = "") -> str:
        return f"configstore://{self.sockets}/{role}.sock" + (f"?{query}" if query else "")

    def status(self) -> dict:
        return self.daemon.status()

    def stop(self) -> None:
        if self.daemon is not None:
            self.daemon.stop()
            self.daemon = None


class Group:
    """A box (a group of one), and as many servers joined to it as asked — each through the member named, over its
    `-api` door, each with its journal on disk."""

    def __init__(self, n: int, tuning: str = "lan", index_base: int = 1000, via_follower: bool = False):
        self.root = tempfile.mkdtemp(prefix="cs", dir="/tmp")
        self.tuning, self.index_base = tuning, index_base
        self.members: list[Member] = []
        for k in range(n):
            via = None
            if k:
                via = (self.members[-1] if via_follower else self.members[0]).adv
            m = Member(self, k, via)
            self.members.append(m)
            _ready(m)
            if k:
                _caught_up(m, self.leader())

    def leader(self) -> Member | None:
        for m in self.members:
            if m.daemon is not None and m.status()["state"] == "leader":
                return m
        return None

    def stop(self) -> None:
        for m in self.members:
            try:
                m.stop()
            except Exception:                          # noqa: BLE001 — stopped already
                pass
        shutil.rmtree(self.root, ignore_errors=True)


# Answered through the log: a leader exists and commits. A read leaves no row behind.
def _ready(m: Member, within: float = 15.0) -> None:
    v = open_vars(m.url(query="timeout=1"))
    end = time.monotonic() + within
    while True:
        try:
            v.get("ready")
            return
        except OSError:
            if time.monotonic() > end:
                raise
            time.sleep(0.05)


def _caught_up(m: Member, leader: Member, within: float = 15.0) -> None:
    end = time.monotonic() + within
    while m.status()["applied"] < leader.status()["commit"]:
        if time.monotonic() > end:
            raise AssertionError(f"{m.name} did not catch up: {m.status()} vs {leader.status()}")
        time.sleep(0.02)


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
            via = next((m for m in g.members if m is not leader), g.members[0])
            os.environ["CONTRACT_URL"] = via.url()
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


def test_the_variables_contract_holds_on_a_configstore_group_of_one():
    """A group of one is held to the same file as `file://` and `memory://` — every clause."""
    failed = _contract_on(1)
    assert not failed, "\n".join(failed)


def test_the_variables_contract_holds_on_a_configstore_group_of_three():
    """Three servers, the handle on a follower's admin socket: every write and every read is carried to the leader by
    the library, and the contract cannot tell."""
    failed = _contract_on(3)
    assert not failed, "\n".join(failed)


def test_a_server_that_joins_a_running_group_gets_its_data():
    """From one server to three without a migration: rows written on the first server are on the third once it has
    joined — through the SECOND, a follower, whose door hands the change to the library and the library to the
    leader — at the same versions, because a version is the log's index above the group's base; and the group of
    three goes on writing when the server that started it is gone."""
    g = Group(1, index_base=5000)
    try:
        box = open_vars(g.members[0].url())
        written = {f"testsub/counters/{k}": box.put(f"testsub/counters/{k}", {"k": k}, cas=0) for k in range(50)}
        assert min(written.values()) > 5000
        for k in (1, 2):
            m = Member(g, k, g.members[k - 1].adv)                  # the third joins through the second
            g.members.append(m)
            _ready(m)
        third = g.members[2]
        _caught_up(third, g.leader())
        assert sorted(x["id"] for x in third.status()["members"]) == list(NAMES)
        machine = third.daemon.backend.rep.m                        # its own copy, not the leader's answer
        assert sorted(machine.rows) == sorted(written)
        assert all(machine.rows[k][1] == idx for k, idx in written.items()), "a joined server holds other versions"

        g.members[0].stop()                                         # the server that started it all
        v3 = open_vars(third.url())
        _ready(third)
        i = v3.put("testsub/counters/0", {"k": "moved"}, cas=written["testsub/counters/0"])
        assert v3.get("testsub/counters/0") == ({"k": "moved"}, i)
        assert open_vars(g.members[1].url()).get("testsub/counters/0") == ({"k": "moved"}, i)
    finally:
        g.stop()


def test_the_leader_killed_the_group_keeps_writing():
    """A slot renewed every 100 ms through each survivor's socket while the leader's daemon is killed: the survivors
    elect a new leader and the renewals go on — no `Conflict` (a conflict would fence the worker), at most a pause
    shorter than the handle's 5 s, and nothing lost of what was answered."""
    g = Group(3)
    try:
        leader = g.leader()
        survivors = [m for m in g.members if m is not leader]
        hs = {m.name: open_vars(m.url("testsubworker")) for m in survivors}
        idx = {n: h.put(f"testsub/slots/w-{n}", {"holder": n, "n": 0}, cas=0) for n, h in hs.items()}
        stop, errors, gaps = threading.Event(), [], []

        def renew(n, h):
            last_ok, k = time.monotonic(), 0
            while not stop.is_set():
                k += 1
                try:
                    idx[n] = h.put(f"testsub/slots/w-{n}", {"holder": n, "n": k}, cas=idx[n])
                    now = time.monotonic()
                    gaps.append(now - last_ok)
                    last_ok = now
                except Conflict as e:
                    errors.append(f"{n}: Conflict {e}")
                    return
                except OSError:
                    pass                                            # not answered: the worker keeps what it holds
                stop.wait(0.1)

        ts = [threading.Thread(target=renew, args=(n, h)) for n, h in hs.items()]
        for t in ts:
            t.start()
        time.sleep(1.0)
        leader.stop()
        time.sleep(4.0)
        stop.set()
        for t in ts:
            t.join()
        assert not errors, errors
        assert g.leader() in survivors
        assert max(gaps) < 5.0, f"a renewal waited {max(gaps):.2f} s"
        for n, h in hs.items():
            items, version = h.get(f"testsub/slots/w-{n}")
            assert version == idx[n], "the last answered renewal is not what the group holds"
    finally:
        g.stop()


def test_cas_conflicts_across_servers():
    """One key, three writers on three servers, one version to write against: one wins, two get `Conflict` — and
    what one server wrote, a read on another sees at once (reads go through the log)."""
    g = Group(3)
    try:
        hs = [open_vars(m.url()) for m in g.members]
        won, refused = [], []

        def go(k):
            try:
                hs[k].put("testsub/slots/w-1", {"holder": f"on-{k}"}, cas=0)
                won.append(k)
            except Conflict:
                refused.append(k)

        ts = [threading.Thread(target=go, args=(k,)) for k in range(3)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert len(won) == 1 and len(refused) == 2, (won, refused)
        items, idx = hs[(won[0] + 1) % 3].get("testsub/slots/w-1")      # read on ANOTHER server, at once
        assert items == {"holder": f"on-{won[0]}"}
        j = hs[1].put("testsub/slots/w-1", {"holder": "renewed"}, cas=idx)
        for k in (0, 2):
            with pytest.raises(Conflict):
                hs[k].put("testsub/slots/w-1", {"holder": f"late-{k}"}, cas=idx)
        assert hs[0].get("testsub/slots/w-1") == ({"holder": "renewed"}, j)
        hs[2].delete("testsub/slots/w-1", cas=j)
        assert hs[0].get("testsub/slots/w-1") == (None, 0)
    finally:
        g.stop()


def test_a_write_retried_with_its_id_after_its_first_copy_landed_is_applied_once():
    """During an election the library reports «leader changed» for a command the old leader had already appended,
    and which may yet commit. A write carries its id, and the machine answers a repeat with the first answer: same
    version, nothing applied twice — asked here as a retry asks it, the same body through another server."""
    g = Group(3)
    try:
        v = open_vars(g.members[1].url())
        idx = v.put("testsub/slots/w-2", {"holder": "a"}, cas=0)
        body = {"op": "put", "key": "testsub/slots/w-2", "items": {"holder": "a", "until": "1"}, "cas": idx,
                "id": uuid.uuid4().hex}
        first = v._call("POST", "/v1/write", body)
        again = open_vars(g.members[2].url())._call("POST", "/v1/write", body)
        assert first == again, (first, again)
        assert v.get("testsub/slots/w-2") == ({"holder": "a", "until": "1"}, first["index"])
        with pytest.raises(Conflict):                                 # a DIFFERENT write against the same version
            v.put("testsub/slots/w-2", {"holder": "b"}, cas=idx)
    finally:
        g.stop()


def test_a_group_without_a_majority_does_not_answer_and_does_not_refuse():
    """Two of three gone: the last one cannot commit anything. Its handle says so as `StoreUnavailable` — or, for a
    write handed to a leader that is gone, `StoreAmbiguous`, which is one — an `OSError`, read by every caller as
    «the store did not answer» (a worker keeps what it holds; feedback BC), never `Conflict`, which would fence it.
    A read too: a read through the log needs a majority like a write, and a read is never «maybe done»."""
    g = Group(3)
    try:
        last = g.members[0]
        v = open_vars(last.url(query="timeout=1.5"))
        idx = v.put("testsub/epoch/9", {"epoch": 1}, cas=0)
        for m in g.members[1:]:
            m.stop()
        t0 = time.monotonic()
        with pytest.raises(StoreUnavailable):
            v.put("testsub/epoch/9", {"epoch": 2}, cas=idx)
        try:
            v.get("testsub/epoch/9")
            raise AssertionError("a read was answered without a majority")
        except StoreUnavailable as e:
            assert not isinstance(e, StoreAmbiguous), "a read was answered as «maybe done»"
        assert time.monotonic() - t0 < 6.0, "the handle waited past its own timeout"
    finally:
        g.stop()


def test_a_role_socket_on_a_follower_refuses_before_anything_is_forwarded():
    """The rights are the RECEIVING daemon's: a worker on a follower writing a counter row gets 403 from its own
    server's daemon, and the leader's log does not move — the request never left the follower."""
    g = Group(3)
    try:
        leader = g.leader()
        follower = next(m for m in g.members if m is not leader)
        w = open_vars(follower.url("testsubworker"))
        w.put("testsub/slots/w-1", {"holder": "x"}, cas=0)
        _caught_up(follower, leader)
        before = leader.status()["commit"]
        with pytest.raises(Forbidden):
            w.put("testsub/counters/7", {"name": "gate"})
        with pytest.raises(Forbidden):
            w.delete("testsub/epoch/7")
        time.sleep(0.3)
        assert leader.status()["commit"] == before, "a refused request reached the leader's log"
    finally:
        g.stop()


def test_a_join_is_refused_without_a_daemons_certificate():
    """The join door of a running group: no client certificate — the handshake fails; a certificate of the
    installation's CA for another role (a worker's) — 403; either way the group's members do not change."""
    g = Group(1)
    try:
        box = g.members[0]
        host, port = "127.0.0.1", box.api_port
        body = json.dumps({"id": "srv-x", "raft": f"127.0.0.1:{_port()}", "api": ""}).encode()
        bare = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare.load_verify_locations(os.path.join(TLS, "ca.pem"))
        import http.client
        for ctx, expect in ((bare, None), (tls.client_context(os.path.join(TLS, "srv-a"), "testsub2worker"), 403)):
            try:
                s = ctx.wrap_socket(socket.create_connection((host, port), timeout=5), server_hostname="srv-a")
                conn = http.client.HTTPConnection(host, port, timeout=5)
                conn.sock = s
                conn.request("POST", "/v1/join", body=body, headers={"Content-Type": "application/json"})
                code = conn.getresponse().status
            except (ssl.SSLError, OSError):
                code = None
            assert code == expect, (expect, code)
        assert [m["id"] for m in box.status()["members"]] == ["srv-a"]
    finally:
        g.stop()


def _listening(backend) -> tuple:
    """Where the library's raft port listens: its own socket, which pysyncobj keeps private."""
    end = time.monotonic() + 10
    while True:
        srv = getattr(backend.raft, "_SyncObj__transport")._server
        sock = getattr(srv, "_TcpServer__socket")
        if sock is not None:
            return sock.getsockname()
        assert time.monotonic() < end, "the raft port was never opened"
        time.sleep(0.02)


def test_a_member_without_the_raft_secret_listens_on_loopback_only_and_takes_nobody():
    """The review's twelfth pass, blocker 1, by its probe (`cfg/probe_raft_bind.py`): a member started with
    `-raft 127.0.0.1:<port>` and no secret listened on `*:<port>` — pickle from the network is code execution. The
    library is told where to listen (`bindAddress`) and the daemon asks its socket: `127.0.0.1`, and `lsof` says the
    same. Such a member is a group of one: the operator's `join` is refused (409) and the group does not change, and
    a restart from a journal that names a partner is refused."""
    import subprocess
    d = tempfile.mkdtemp(prefix="cs", dir="/tmp")
    port = _port()
    b = configstore.start_member("solo", d, f"127.0.0.1:{port}", bootstrap=True, tls_dir=None, tuning="lan")
    dm = None
    try:
        assert _listening(b)[0] == "127.0.0.1", _listening(b)
        if shutil.which("lsof"):
            out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
            assert f"127.0.0.1:{port}" in out and f"*:{port}" not in out, out
        dm = StoreDaemon(b, node_id="solo", sockets=os.path.join(d, "s"), rights=RIGHTS)
        admin = open_vars(f"configstore://{d}/s/admin.sock")
        code, said = dm.serve("POST", "/v1/join", json.dumps({"id": "srv-x", "raft": f"127.0.0.1:{_port()}"}).encode(),
                              "admin", 5.0)
        assert (code, said["kind"]) == (409, "refused") and "group of one" in said["error"], said
        assert [m["id"] for m in admin.status()["members"]] == ["solo"]
    finally:
        (dm.stop() if dm else b.stop())
    doc = configstore.RaftBackend.member_doc(d)
    with open(os.path.join(d, "member.json"), "w") as f:
        json.dump({**doc, "partners": [f"127.0.0.1:{_port()}"]}, f)
    try:
        with pytest.raises(ValueError):
            configstore.start_member("solo", d, f"127.0.0.1:{port}", tls_dir=None, tuning="lan")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_daemon_joins_only_as_its_own_server_and_no_join_leaves_a_voter_nobody_runs():
    """The review's twelfth pass, major 3, on a real group: srv-b's certificate at srv-a's `-api` door may not join
    srv-c or remove srv-a (403), and srv-b again at another raft address is refused (409) — the old address would
    stay a voter nobody runs. The operator's `join` through `admin.sock` is held to the same (the sibling): an id the
    group holds at another address, an address another id holds. The group stays two."""
    g = Group(2)
    try:
        a, b = g.members
        ctx = tls.client_context(b.tls)
        call = lambda route, body: _api(a, ctx, route, body)                              # noqa: E731
        assert call("/v1/join", {"id": "srv-c", "raft": f"127.0.0.1:{_port()}"})[0] == 403
        assert call("/v1/leave", {"id": "srv-a"})[0] == 403
        code, said = call("/v1/join", {"id": "srv-b", "raft": f"127.0.0.1:{_port()}"})
        assert (code, said["kind"]) == (409, "refused") and "leave first" in said["error"], said
        assert call("/v1/join", {"id": "srv-b", "raft": b.raft, "api": b.adv})[0] == 200   # a retry of its own join
        admin = open_vars(a.url())
        for body, words in (({"id": "srv-b", "raft": f"127.0.0.1:{_port()}"}, "leave first"),
                            ({"id": "srv-z", "raft": b.raft}, "srv-b's raft address")):
            try:
                admin._call("POST", "/v1/join", body)
                raise AssertionError(f"a join that leaves a voter nobody runs was taken: {body}")
            except Conflict as e:                               # the handle's word for a 409
                assert words in str(e), e
        assert sorted(m["id"] for m in a.status()["members"]) == ["srv-a", "srv-b"]
        assert len(a.status()["members"]) == 2
    finally:
        g.stop()


def _api(m: "Member", ctx, route: str, body: dict) -> tuple[int, dict]:
    import http.client
    s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", m.api_port), timeout=10), server_hostname=m.name)
    conn = http.client.HTTPConnection("127.0.0.1", m.api_port, timeout=40)
    conn.sock = s
    conn.request("POST", route, body=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    return r.status, json.loads(r.read() or b"{}")


# A member in its group, not a group of one: it counts the other two, and all three name one leader. Which one is the
# election's business — a member restarted may win one (the same term's log, the same rows), and a test that asked
# for «follower» failed whenever its election timer fired before the leader reached it.
def _in_its_group(c: Member, g: Group, within: float = 10.0) -> dict:
    end = time.monotonic() + within
    while True:
        leaders = {m.status()["leader"] for m in g.members}
        st = c.status()
        if len(c.daemon.backend.raft.otherNodes) == 2 and len(leaders) == 1 and None not in leaders:
            return st
        assert time.monotonic() < end, (leaders, st)
        time.sleep(0.05)


def test_a_member_killed_right_after_its_join_comes_back_into_its_group_not_as_a_group_of_one(monkeypatch):
    """The review's thirteenth pass, blocker 1, by its probe (`probe_join_window.py`): `member.json` was written as the
    join was accepted and the partners half a second later; killed between the two, the member came back on its
    journal with no partner — a leader of a group of one, 0 rows, create-only handing out epoch «1» where the group's
    was 7. The library's tick that keeps the partners is switched off here, so what is on disk is only what the
    membership itself wrote: the joined member's `member.json` names its partners (the bootstrap member among them,
    whom no journal names), and so does the member whose door took the join — `add` writes at once (the sibling).
    Restarted with the same flags, srv-c is a member of the real group (one leader for all three) and the epoch is 7,
    its create-only a conflict. And a member that joined but knows no partner (a `member.json` from before) does not start alone: it
    asks its `-join` door, or refuses with words."""
    monkeypatch.setattr(configstore.RaftBackend, "_keep_peers", lambda self: None)
    g = Group(2)
    try:
        a = g.leader()
        v = open_vars(a.url())
        for i in range(20):
            v.put(f"testsub/epoch/c{i}", {"epoch": "7"}, cas=0)
        c = Member(g, 2, a.adv)
        g.members.append(c)
        joined = configstore.RaftBackend.member_doc(c.data)
        assert joined["how"] == "join" and sorted(joined["partners"]) == sorted([g.members[0].raft, g.members[1].raft])
        assert c.raft in configstore.RaftBackend.member_doc(a.data)["partners"], "the door that took it did not write"
        c.stop()                                                    # killed before any tick of the library
        c.start(join=a.adv)
        _ready(c)
        _caught_up(c, g.leader())
        st = _in_its_group(c, g)
        assert sorted(m["id"] for m in st["members"]) == list(NAMES), st
        assert c.daemon.backend.rep.m.rows["testsub/epoch/c5"][0] == {"epoch": "7"}
        with pytest.raises(Conflict):
            open_vars(c.url("testsubworker")).put("testsub/epoch/c5", {"epoch": "1"}, cas=0)
        c.stop()
        with open(os.path.join(c.data, "member.json"), "w") as f:  # a member.json from before the partners were in it
            json.dump({"id": c.name, "raft": c.raft}, f)
        try:
            c.start()                                               # no -join to ask: it waits for its group
            raise AssertionError("a joined member that knows no partner started")
        except ValueError as e:
            assert "does not start as a group of one" in str(e), e
        c.start(join=a.adv)                                         # its -join door says who the group is
        _ready(c)
        _in_its_group(c, g)
        assert sorted(configstore.RaftBackend.member_doc(c.data)["partners"]) == sorted(
            [g.members[0].raft, g.members[1].raft])
    finally:
        g.stop()


def test_a_join_under_another_spelling_of_a_members_raft_address_is_refused():
    """The review's thirteenth pass, major 3, by its probe (`probe_alias_voter.py`): srv-d of the same CA joined with
    `raft=localhost:<srv-a's port>` — 200, a voter nobody runs, and the group of three no longer survived losing one.
    Addresses are compared as where they lead (`_places`): `localhost`, `LOCALHOST.`, `[::ffff:127.0.0.1]` are srv-a's
    `127.0.0.1` — 409, and the voters stay two. An address that leads nowhere, or to every interface, and one where
    nothing answers are refused too. A retry of srv-b's own join under another spelling is the retry (200), under the
    spelling the group holds."""
    g = Group(2)
    try:
        a, b = g.members
        port = a.raft.rsplit(":", 1)[1]
        ctx_c = tls.client_context(os.path.join(TLS, "srv-c"))
        for alias in (f"localhost:{port}", f"LOCALHOST.:{port}", f"[::ffff:127.0.0.1]:{port}", f"127.1:{port}"):
            code, said = _api(a, ctx_c, "/v1/join", {"id": "srv-c", "raft": alias})
            assert (code, said["kind"]) == (409, "refused"), (alias, code, said)
        for nowhere in (f"0.0.0.0:{port}", "no-such-host.invalid:8301", f"127.0.0.1:{_port()}"):
            code, said = _api(a, ctx_c, "/v1/join", {"id": "srv-c", "raft": nowhere})
            assert (code, said["kind"]) == (409, "refused"), (nowhere, code, said)
        bport = b.raft.rsplit(":", 1)[1]
        code, said = _api(a, tls.client_context(b.tls), "/v1/join", {"id": "srv-b", "raft": f"localhost:{bport}",
                                                                     "api": b.adv})
        assert code == 200, said
        st = a.status()
        assert sorted((m["id"], m["raft"]) for m in st["members"]) == sorted([("srv-a", a.raft), ("srv-b", b.raft)])
        assert len(a.daemon.backend.raft.otherNodes) == 1
    finally:
        g.stop()


def test_a_join_whose_raft_address_is_no_raft_member_of_this_installation_is_refused():
    """The product's cross-check (hashicorp/raft): a new voter's raft address was checked by a TCP answer, and every
    listener answers TCP — srv-a's own `-api` door among them: srv-b joined with `raft=<srv-a's -api>`, 200, a voter
    nobody runs, and the group of two had no majority. A new voter must now answer the raft library's handshake with
    this installation's secret AND say, in the library's own status, that it is the very address asked for (`add`,
    `_raft_says`). Refused (409), the group unchanged and writing: the `-api` door, a listener that says nothing, the
    raft port of another installation's group (another secret), and srv-c's own raft port asked for under another
    spelling — the group would dial an address srv-c does not answer to as itself. Under its own: 200, two members."""
    g = Group(1)
    dirs, backends = [], []
    silent = socket.socket()
    try:
        a = g.members[0]
        v = open_vars(a.url())
        ctx_b, ctx_c = tls.client_context(os.path.join(TLS, "srv-b")), tls.client_context(os.path.join(TLS, "srv-c"))
        silent.bind(("127.0.0.1", 0))
        silent.listen(4)
        stranger_tls = tempfile.mkdtemp(prefix="cs", dir="/tmp")    # another installation: another raft secret
        dirs.append(stranger_tls)
        for f in ("ca.pem", "crl.pem"):
            shutil.copy(os.path.join(TLS, "srv-c", f), stranger_tls)
        with open(os.path.join(stranger_tls, "raft.secret"), "w") as f:
            f.write("cd" * 32 + "\n")
        os.chmod(os.path.join(stranger_tls, "raft.secret"), 0o600)
        stranger = f"127.0.0.1:{_port()}"
        dirs.append(tempfile.mkdtemp(prefix="cs", dir="/tmp"))
        backends.append(configstore.RaftBackend("stranger", stranger, [], dirs[-1], "lan",
                                                tls.raft_secret(stranger_tls)))
        for raft in (f"127.0.0.1:{a.api_port}", f"127.0.0.1:{silent.getsockname()[1]}", stranger):
            t0 = time.monotonic()
            code, said = _api(a, ctx_b, "/v1/join", {"id": "srv-b", "raft": raft})
            assert (code, said["kind"]) == (409, "refused") and "raft port" in said["error"], (raft, code, said)
            assert time.monotonic() - t0 < 3 * configstore.ANSWER_WAIT, raft
        c_port = _port()
        dirs.append(tempfile.mkdtemp(prefix="cs", dir="/tmp"))
        backends.append(configstore.RaftBackend("srv-c", f"127.0.0.1:{c_port}", [a.raft], dirs[-1], "lan",
                                                tls.raft_secret(os.path.join(TLS, "srv-c"))))
        code, said = _api(a, ctx_c, "/v1/join", {"id": "srv-c", "raft": f"localhost:{c_port}"})
        assert (code, said["kind"]) == (409, "refused") and f"127.0.0.1:{c_port}" in said["error"], (code, said)
        assert [m["id"] for m in a.status()["members"]] == ["srv-a"] and not a.daemon.backend.raft.otherNodes
        v.put("testsub/counters/after-the-refusals", {"name": "x"}, cas=0)          # the group of one still writes
        code, said = _api(a, ctx_c, "/v1/join", {"id": "srv-c", "raft": f"127.0.0.1:{c_port}"})
        assert code == 200, said
        assert sorted(m["id"] for m in a.status()["members"]) == ["srv-a", "srv-c"]
        v.put("testsub/counters/with-srv-c", {"name": "y"}, cas=0)                  # a majority of two answers
    finally:
        silent.close()
        for b in backends:
            b.stop()
        g.stop()
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)


def test_a_member_restarted_on_its_journal_comes_back_with_its_rows():
    """A unit restarted by systemd with the same flags: the daemon was taken into its group (`member.json`), so it
    starts from its journal with the members it saw — `-join` is not asked again — and catches up on what was
    written while it was down."""
    g = Group(3)
    try:
        leader = g.leader()
        m = next(x for x in g.members if x is not leader)
        v = open_vars(leader.url())
        a = v.put("testsub/counters/1", {"name": "before"}, cas=0)
        _caught_up(m, leader)
        m.stop()
        b = v.put("testsub/counters/1", {"name": "while down"}, cas=a)
        m.start(join="nobody@127.0.0.1:1")                           # a join that could not be answered: not asked
        _ready(m)
        _caught_up(m, g.leader())
        assert m.daemon.backend.rep.m.rows["testsub/counters/1"] == ({"name": "while down"}, b)
        assert open_vars(m.url()).get("testsub/counters/1") == ({"name": "while down"}, b)
    finally:
        g.stop()


def test_the_platforms_cas_loops_run_on_configstore_unchanged():
    """The seam's promise, run: two workers on two servers take a slot each, take epochs, renew — and the second
    taking a unit the first holds fences the first on its next renewal, as on files. Nothing in the platform knows
    which store answered."""
    from w2cplatform.contract import Subsystem
    from w2cplatform.worker import Worker

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
        sub = Subsystem("testsub")
        a = _W(sub, None, open_vars(g.members[1].url("testsubworker")), _Objects())
        b = _W(sub, None, open_vars(g.members[2].url("testsubworker")), _Objects())
        assert a.claim_slot() == "w-1" and b.claim_slot() == "w-2"   # w-1 is taken by CAS, on another server
        assert a.take_epoch("7") == 1 and a.renew_slot() and a.renew_leases() == []
        assert b.take_epoch("7") == 2                                 # somebody else started the unit
        assert a.renew_leases() == ["7"] and a.leases["7"].fenced
        assert b.renew_leases() == [] and b.renew_slot()
        a.release_slot()
        assert open_vars(g.members[0].url()).get("testsub/slots/w-1")[0]["released"] == "true"
    finally:
        g.stop()

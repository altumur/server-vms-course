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
    "vmsworker": {"read": ["vms/*", "platform/schema"], "write": ["vms/epoch/*", "vms/slots/*"],
                  "delete": ["vms/slots/*"]},
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
        written = {f"vms/cameras/{k}": box.put(f"vms/cameras/{k}", {"k": k}, cas=0) for k in range(50)}
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
        i = v3.put("vms/cameras/0", {"k": "moved"}, cas=written["vms/cameras/0"])
        assert v3.get("vms/cameras/0") == ({"k": "moved"}, i)
        assert open_vars(g.members[1].url()).get("vms/cameras/0") == ({"k": "moved"}, i)
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
        hs = {m.name: open_vars(m.url("vmsworker")) for m in survivors}
        idx = {n: h.put(f"vms/slots/w-{n}", {"holder": n, "n": 0}, cas=0) for n, h in hs.items()}
        stop, errors, gaps = threading.Event(), [], []

        def renew(n, h):
            last_ok, k = time.monotonic(), 0
            while not stop.is_set():
                k += 1
                try:
                    idx[n] = h.put(f"vms/slots/w-{n}", {"holder": n, "n": k}, cas=idx[n])
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
            items, version = h.get(f"vms/slots/w-{n}")
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
            with pytest.raises(Conflict):
                hs[k].put("vms/slots/w-1", {"holder": f"late-{k}"}, cas=idx)
        assert hs[0].get("vms/slots/w-1") == ({"holder": "renewed"}, j)
        hs[2].delete("vms/slots/w-1", cas=j)
        assert hs[0].get("vms/slots/w-1") == (None, 0)
    finally:
        g.stop()


def test_a_write_retried_with_its_id_after_its_first_copy_landed_is_applied_once():
    """During an election the library reports «leader changed» for a command the old leader had already appended,
    and which may yet commit. A write carries its id, and the machine answers a repeat with the first answer: same
    version, nothing applied twice — asked here as a retry asks it, the same body through another server."""
    g = Group(3)
    try:
        v = open_vars(g.members[1].url())
        idx = v.put("vms/slots/w-2", {"holder": "a"}, cas=0)
        body = {"op": "put", "key": "vms/slots/w-2", "items": {"holder": "a", "until": "1"}, "cas": idx,
                "id": uuid.uuid4().hex}
        first = v._call("POST", "/v1/write", body)
        again = open_vars(g.members[2].url())._call("POST", "/v1/write", body)
        assert first == again, (first, again)
        assert v.get("vms/slots/w-2") == ({"holder": "a", "until": "1"}, first["index"])
        with pytest.raises(Conflict):                                 # a DIFFERENT write against the same version
            v.put("vms/slots/w-2", {"holder": "b"}, cas=idx)
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
        idx = v.put("vms/epoch/9", {"epoch": 1}, cas=0)
        for m in g.members[1:]:
            m.stop()
        t0 = time.monotonic()
        with pytest.raises(StoreUnavailable):
            v.put("vms/epoch/9", {"epoch": 2}, cas=idx)
        try:
            v.get("vms/epoch/9")
            raise AssertionError("a read was answered without a majority")
        except StoreUnavailable as e:
            assert not isinstance(e, StoreAmbiguous), "a read was answered as «maybe done»"
        assert time.monotonic() - t0 < 6.0, "the handle waited past its own timeout"
    finally:
        g.stop()


def test_a_role_socket_on_a_follower_refuses_before_anything_is_forwarded():
    """The rights are the RECEIVING daemon's: a worker on a follower writing a camera row gets 403 from its own
    server's daemon, and the leader's log does not move — the request never left the follower."""
    g = Group(3)
    try:
        leader = g.leader()
        follower = next(m for m in g.members if m is not leader)
        w = open_vars(follower.url("vmsworker"))
        w.put("vms/slots/w-1", {"holder": "x"}, cas=0)
        _caught_up(follower, leader)
        before = leader.status()["commit"]
        with pytest.raises(Forbidden):
            w.put("vms/cameras/7", {"name": "gate"})
        with pytest.raises(Forbidden):
            w.delete("vms/epoch/7")
        time.sleep(0.3)
        assert leader.status()["commit"] == before, "a refused request reached the leader's log"
    finally:
        g.stop()


def test_a_join_is_refused_without_a_daemons_certificate():
    """The join door of a running group: no client certificate — the handshake fails; a certificate of the
    installation's CA for another role (a recorder's) — 403; either way the group's members do not change."""
    g = Group(1)
    try:
        box = g.members[0]
        host, port = "127.0.0.1", box.api_port
        body = json.dumps({"id": "srv-x", "raft": f"127.0.0.1:{_port()}", "api": ""}).encode()
        bare = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare.load_verify_locations(os.path.join(TLS, "ca.pem"))
        import http.client
        for ctx, expect in ((bare, None), (tls.client_context(os.path.join(TLS, "srv-a"), "recworker"), 403)):
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
    with open(os.path.join(d, "peers.json"), "w") as f:
        json.dump([f"127.0.0.1:{_port()}"], f)
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


def test_a_member_restarted_on_its_journal_comes_back_with_its_rows():
    """A unit restarted by systemd with the same flags: the daemon was taken into its group (`member.json`), so it
    starts from its journal with the members it saw — `-join` is not asked again — and catches up on what was
    written while it was down."""
    g = Group(3)
    try:
        leader = g.leader()
        m = next(x for x in g.members if x is not leader)
        v = open_vars(leader.url())
        a = v.put("vms/cameras/1", {"name": "before"}, cas=0)
        _caught_up(m, leader)
        m.stop()
        b = v.put("vms/cameras/1", {"name": "while down"}, cas=a)
        m.start(join="nobody@127.0.0.1:1")                           # a join that could not be answered: not asked
        _ready(m)
        _caught_up(m, g.leader())
        assert m.daemon.backend.rep.m.rows["vms/cameras/1"] == ({"name": "while down"}, b)
        assert open_vars(m.url()).get("vms/cameras/1") == ({"name": "while down"}, b)
    finally:
        g.stop()


def test_the_platforms_cas_loops_run_on_configstore_unchanged():
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
        a = _W(sub, None, open_vars(g.members[1].url("vmsworker")), _Objects())
        b = _W(sub, None, open_vars(g.members[2].url("vmsworker")), _Objects())
        assert a.claim_slot() == "w-1" and b.claim_slot() == "w-2"   # w-1 is taken by CAS, on another server
        assert a.take_epoch("7") == 1 and a.renew_slot() and a.renew_leases() == []
        assert b.take_epoch("7") == 2                                 # somebody else started the unit
        assert a.renew_leases() == ["7"] and a.leases["7"].fenced
        assert b.renew_leases() == [] and b.renew_slot()
        a.release_slot()
        assert open_vars(g.members[0].url()).get("vms/slots/w-1")[0]["released"] == "true"
    finally:
        g.stop()

"""`configstore://` — the handle (`w2cplatform/configstorevars.py`) and the daemon's doors (`w2cplatform/configstore.py`)
on real unix sockets and a real mutual-TLS door, with the state machine applied in the daemon's own process
(`LocalBackend`) instead of through raft. Needs no raft library, so it runs in every suite; what raft adds — a
group, joins, a leader killed — is `test_configstore.py`, where `pysyncobj` is installed.

Socket directories are short ones under /tmp: a unix socket's path is at most 104 bytes on macOS."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import socket
import socketserver
import ssl
import stat
import tempfile
import threading
import time
from contextlib import redirect_stdout

import pytest

from w2cplatform import configstore, tls
from w2cplatform.configstore import LocalBackend, StoreDaemon
from w2cplatform.configstorevars import StoreAmbiguous, StoreUnavailable
from w2cplatform.storemachine import Ambiguous, Rights, Unavailable
from w2cplatform.variables import Conflict, FileVariables, Forbidden, open_vars, store_url

HERE = os.path.dirname(os.path.abspath(__file__))
TLS = os.path.join(HERE, "tls")
RIGHTS = Rights.parse({"roles": {
    "vmsworker": {"read": ["vms/*"], "write": ["vms/epoch/*", "vms/slots/*"], "delete": ["vms/slots/*"]},
    "console": {"read": ["vms/*"], "write": ["vms/cameras/*"], "delete": ["vms/cameras/*"]},
}})


@contextlib.contextmanager
def refused(words: str):
    """A `ValueError` that says `words` — the operator reads the reason, so the reason is part of what is tested."""
    try:
        yield
    except ValueError as e:
        assert words in str(e), f"refused, but not for {words!r}: {e}"
        return
    raise AssertionError(f"not refused ({words})")


def short_dir() -> str:
    d = tempfile.mkdtemp(prefix="cs", dir="/tmp")
    assert len(os.path.join(d, "vmscontroller.sock")) < 104, d
    return d


def url(d: str, role: str = "admin", query: str = "") -> str:
    return f"configstore://{d}/{role}.sock" + (f"?{query}" if query else "")


class Daemon:
    """A daemon over the machine in this process: its sockets in a short directory, optionally its `-api` door."""

    def __init__(self, backend=None, api: bool = False, tls_dir: str = os.path.join(TLS, "srv-a"), d: str | None = None):
        self.dir = d or short_dir()
        self.backend = backend or LocalBackend("srv-a", 1000)
        self.d = StoreDaemon(self.backend, node_id="srv-a", sockets=self.dir, rights=RIGHTS,
                             api=("127.0.0.1", 0) if api else None, tls_dir=tls_dir if api else None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.d.stop()
        shutil.rmtree(self.dir, ignore_errors=True)


def test_the_variables_contract_holds_on_configstore_through_a_daemon_socket():
    """Every clause of the contract suite against `configstore://<dir>/admin.sock`: the handle, HTTP over a unix
    socket, the daemon's door, the API and the machine — everything but raft, which `test_configstore.py` adds."""
    from tests import test_variables_contract as contract
    clauses = [(n, fn) for n, fn in vars(contract).items() if n.startswith("test_") and callable(fn)]
    assert len(clauses) >= 13, "the contract suite shrank"
    failed = []
    saved = os.environ.get("CONTRACT_URL")
    for name, fn in clauses:
        with Daemon() as dm:
            os.environ["CONTRACT_URL"] = url(dm.dir)
            try:
                fn()
            except Exception as e:                     # noqa: BLE001 — collected and reported by clause
                failed.append(f"{name}: {type(e).__name__}: {e}")
            finally:
                if saved is None:
                    os.environ.pop("CONTRACT_URL", None)
                else:
                    os.environ["CONTRACT_URL"] = saved
    assert not failed, "\n".join(failed)


def test_a_role_without_the_grant_is_refused_at_its_own_socket_before_anything_is_applied():
    """The socket is the identity: the worker's socket may write slots and epochs, not cameras. The 403 is the
    daemon's, before the command reaches the machine (on a raft member: before it is forwarded to the leader) — the
    machine's log index does not move. The handle's own `as_writer` check is a second one, not the one proved here:
    this handle has no writer at all."""
    with Daemon() as dm:
        w = open_vars(url(dm.dir, "vmsworker"))
        w.put("vms/slots/w-1", {"holder": "x"}, cas=0)
        applied = dm.backend.machine.applied
        with pytest.raises(Forbidden):
            w.put("vms/cameras/7", {"name": "gate"})
        with pytest.raises(Forbidden):
            w.delete("vms/cameras/7")
        with pytest.raises(Forbidden):
            open_vars(url(dm.dir, "console")).delete("vms/epoch/7")
        assert dm.backend.machine.applied == applied, "a refused request reached the log"
        assert open_vars(url(dm.dir)).get("vms/cameras/7") == (None, 0)


def test_each_role_has_its_own_socket_and_the_admin_socket_is_the_owners():
    """0660 for a role's socket (its group is the role's unit's: `socket_group`), 0600 for `admin.sock`; join and
    leave are refused on a role's socket, the rights are shown on the admin's only."""
    with Daemon() as dm:
        names = sorted(f for f in os.listdir(dm.dir) if f.endswith(".sock"))
        assert names == ["admin.sock", "console.sock", "vmsworker.sock"]
        mode = lambda f: stat.S_IMODE(os.stat(os.path.join(dm.dir, f)).st_mode)    # noqa: E731
        assert mode("admin.sock") == 0o600 and mode("vmsworker.sock") == 0o660
        assert configstore.socket_group("vmsworker") == "w2c-vmsworker"            # the file names no group for it here
        assert configstore.socket_group("resource") == "w2c-resource"
        w = open_vars(url(dm.dir, "vmsworker"))
        with pytest.raises(Forbidden):
            w._call("POST", "/v1/join", {"id": "srv-x", "raft": "127.0.0.1:1"})
        with pytest.raises(Forbidden):
            w._call("GET", "/v1/rights")
        assert open_vars(url(dm.dir))._call("GET", "/v1/rights")["roles"]["vmsworker"]["write"] == \
            ["vms/epoch/*", "vms/slots/*"]


def test_a_refused_connection_is_tried_again_within_d():
    """A daemon restarting has no socket for a second or two. Nothing was sent, so the handle tries again — a write
    too — for up to D (`REFUSED_WAIT`, 5 s): the worker's lease step waits out the restart instead of losing a turn
    (the notes on the raft prototype, "what to change", point 2). Past its time it is `StoreUnavailable`."""
    d = short_dir()
    try:
        v = open_vars(url(d))
        holder = {}

        def start_late():
            time.sleep(1.0)
            holder["dm"] = Daemon(d=d)

        t = threading.Thread(target=start_late)
        t.start()
        t0 = time.monotonic()
        i = v.put("vms/epoch/7", {"epoch": 1}, cas=0)
        took = time.monotonic() - t0
        t.join()
        assert 0.9 <= took < 5.0, took
        assert v.get("vms/epoch/7") == ({"epoch": "1"}, i)
        holder["dm"].d.stop()
        quick = open_vars(url(d, query="timeout=1"))
        t0 = time.monotonic()
        with pytest.raises(StoreUnavailable):
            quick.get("vms/epoch/7")
        assert 0.9 <= time.monotonic() - t0 < 3.0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_callers_refused_together_try_again_each_at_its_own_moment(monkeypatch):
    """The sibling of the product's cross-check (D) at the store's socket: every process of a server loses its daemon
    at the same moment, and tried again every 0.1 s exactly — in step, at the new socket at once. Now each wait is
    `REFUSED_STEP` give or take half, drawn afresh."""
    from w2cplatform import configstorevars
    from w2cplatform.configstorevars import ConfigstoreVariables, _NotConnected
    slept, refused = [], {"n": 12}

    def transport(method, target, raw, headers, timeout):
        if refused["n"]:
            refused["n"] -= 1
            raise _NotConnected("ConnectionRefusedError: the daemon restarts")
        return 200, b'{"index": "", "items": null}'
    me, real = threading.current_thread(), time.sleep                # `time` is every thread's: only this one's is counted
    monkeypatch.setattr(configstorevars.time, "sleep", lambda s: slept.append(s) if threading.current_thread() is me else real(s))
    ConfigstoreVariables("/nowhere.sock", transport=transport).get("vms/epoch/7")
    assert len(slept) == 12 and all(0.05 <= s <= 0.15 for s in slept), slept
    assert len({round(s, 6) for s in slept}) > 6, slept


class _Faulty(LocalBackend):
    def __init__(self, fault):
        super().__init__("srv-a", 1000)
        self.fault = fault

    def submit(self, cmd, deadline=None):
        if cmd["op"] in ("put", "delete"):
            raise self.fault
        return super().submit(cmd, deadline)


def test_not_done_and_outcome_unknown_reach_the_caller_as_their_own_kinds():
    """503 `unavailable` → `StoreUnavailable` (not done; repeat freely), 503 `ambiguous` → `StoreAmbiguous` (may yet
    land; read before writing again). Both are `OSError`s — "the store did not answer" to every caller in the
    platform, which keeps what it holds — and neither is ever `Conflict`, which would fence a worker."""
    with Daemon(_Faulty(Unavailable("no leader within 5 s"))) as dm:
        try:
            open_vars(url(dm.dir)).put("vms/epoch/7", {"epoch": 1})
            raise AssertionError("a write no leader took was answered")
        except StoreUnavailable as e:
            assert not isinstance(e, StoreAmbiguous), "a write that was not done was said to be maybe done"
    with Daemon(_Faulty(Ambiguous("the leader went"))) as dm:
        with pytest.raises(StoreAmbiguous):
            open_vars(url(dm.dir)).put("vms/epoch/7", {"epoch": 1})
    assert issubclass(StoreAmbiguous, StoreUnavailable) and issubclass(StoreUnavailable, OSError)


def test_an_answer_cut_off_by_a_dying_daemon_is_not_an_answer():
    """Found by the prototype's measurement at the fifteenth leader kill: the daemon sent its headers and died before
    the body, and `http.client.IncompleteRead` — an `HTTPException`, not an `OSError` — flew out of the handle and out
    of `renew_slot`. Whatever a daemon does while dying, the handle says «the store did not answer»: a cut-off body,
    a body that is not JSON, a connection closed before any answer. For a read `StoreUnavailable`; for a write,
    which was sent, `StoreAmbiguous`. Never `ValueError`, which reads as «not a key»."""
    d = short_dir()

    class Dying(socketserver.StreamRequestHandler):
        def handle(self):
            line = self.rfile.readline().decode()
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass
            if "cut" in line:
                self.wfile.write(b'HTTP/1.1 200 OK\r\nContent-Length: 27\r\n\r\n{"items"')
            elif "garbage" in line:
                self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n<html")
            # else: not even a status line

    srv = socketserver.ThreadingUnixStreamServer(os.path.join(d, "admin.sock"), Dying)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        v = open_vars(url(d, query="timeout=2"))
        for key in ("vms/cut/1", "vms/garbage/1", "vms/silent/1"):
            with pytest.raises(StoreUnavailable):
                v.get(key)
        with pytest.raises(StoreUnavailable):
            v.list("vms/cut/")
        with pytest.raises(StoreAmbiguous):
            v.put("vms/silent/1", {"x": "1"})
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(d, ignore_errors=True)


# -- the -api door: mutual TLS ------------------------------------------------------------------------
def _dial(api_url: str, ctx: ssl.SSLContext, name: str, method: str, route: str, body: bytes = b"{}",
          headers: dict | None = None):
    import http.client
    host, port = api_url.rsplit(":", 1)
    s = ctx.wrap_socket(socket.create_connection((host, int(port)), timeout=5), server_hostname=name)
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    conn.sock = s
    conn.request(method, route, body=body, headers={"Content-Type": "application/json", **(headers or {})})
    r = conn.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_the_api_door_refuses_a_join_without_a_certificate_and_with_another_roles_certificate():
    """A daemon that accepts `POST /v1/join` from anybody hands the cluster's store to anybody. Without a client
    certificate the handshake itself fails; with a certificate of the installation's CA for another role (a
    recorder's, `urn:w2c:role:recworker`) the door answers 403 before it reads the request; a daemon's certificate
    (`configstore.<server>`, `urn:w2c:role:configstore`) gets through for its own server — here to a store that is
    no group, 503."""
    with Daemon(api=True) as dm:
        api = dm.d.api_url
        bare = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare.load_verify_locations(os.path.join(TLS, "ca.pem"))
        join = json.dumps({"id": "srv-x", "raft": "127.0.0.1:1", "api": ""}).encode()
        with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
            _dial(api, bare, "srv-a", "POST", "/v1/join", join)
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-a"), "recworker"), "srv-a", "POST",
                           "/v1/join", join)
        assert (code, said["kind"]) == (403, "forbidden") and "recworker" in said["error"]
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-b")), "srv-a", "POST", "/v1/join",
                           join.replace(b"srv-x", b"srv-b"))
        assert code == 503, said
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-b")), "srv-a", "GET", "/v1/status")
        assert code == 200 and said["id"] == "srv-a"


def test_a_daemon_dialling_another_checks_the_name_and_the_role_of_the_one_that_answers():
    """The client side of the same door: the answering certificate must be the CA's, carry the SAN DNS of the server
    dialled (`srv-b@host:port` dials srv-b), and be a store daemon's — a recorder's certificate for the right server
    is not the store."""
    with Daemon(api=True) as dm:
        assert configstore.peer_call(f"srv-a@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")["id"] \
            == "srv-a"
        with pytest.raises(ssl.SSLCertVerificationError):
            configstore.peer_call(f"srv-c@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")
    rogue_dir = short_dir()
    try:
        for f in ("ca.pem", "crl.pem"):
            shutil.copy(os.path.join(TLS, "srv-a", f), rogue_dir)
        shutil.copy(os.path.join(TLS, "srv-a", "recworker.pem"), os.path.join(rogue_dir, "server.pem"))
        shutil.copy(os.path.join(TLS, "srv-a", "recworker.key"), os.path.join(rogue_dir, "server.key"))
        with Daemon(api=True, tls_dir=rogue_dir) as dm:
            with pytest.raises(PermissionError):
                configstore.peer_call(f"srv-a@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")
    finally:
        shutil.rmtree(rogue_dir, ignore_errors=True)


def test_a_daemon_will_not_open_its_doors_unprotected():
    """The `-api` door is mutual TLS or nothing; a raft port off loopback without the secret is refused before the
    raft library is even asked."""
    with pytest.raises(ValueError):
        StoreDaemon(LocalBackend(), node_id="srv-a", api=("127.0.0.1", 0), tls_dir=None)
    with pytest.raises(ValueError):
        configstore.start_member("srv-a", short_dir(), "10.0.0.1:8301", bootstrap=True)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_a_raft_port_without_its_secret_is_refused_on_every_interface_but_loopback_before_it_opens():
    """The review's twelfth pass, blocker 1: `-raft 127.0.0.1:…` without `-tls` passed a check of the address's TEXT
    and the library listened on `0.0.0.0` — pickle from the network. Without the secret the address is resolved and
    BOUND before the library is asked (`0.0.0.0` is every interface, not loopback), and refused then: nothing ever
    listened on the port. A join makes a group of more, and is refused too. No raft library is needed to say so."""
    port = _free_port()
    with refused("loopback"):
        configstore.start_member("srv-a", short_dir(), f"0.0.0.0:{port}", bootstrap=True)
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
    with refused("loopback"):
        configstore.start_member("srv-b", short_dir(), f"127.0.0.1:{_free_port()}", join="srv-a@127.0.0.1:1")


# -- every door of the daemon is bounded (the review's twelfth pass, major 1) -----------------------------
def _raw(path: str, data: bytes = b"", wait: float = 3.0) -> bytes:
    """What a door answers on a unix socket to `data`, until it closes the connection or `wait` is over."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(wait)
    s.connect(path)
    out = b""
    try:
        if data:
            s.sendall(data)
        while True:
            got = s.recv(65536)
            if not got:
                break
            out += got
    except (socket.timeout, ConnectionResetError):
        pass
    finally:
        s.close()
    return out


def test_every_door_lets_an_idle_connection_go_and_serves_so_many_at_once(monkeypatch):
    """The reviewer's probe: 200 idle connections to a role's socket were 203 threads, held for ever. A request's line
    and headers arrive within `HEADERS_WAIT` or the connection is let go; a socket serves `ROLE_CONNECTIONS` at once,
    and the next is answered on the spot, unread, 503 `unavailable` — not done, so the handle says `StoreUnavailable`
    and never «maybe done», even for a write. The role's socket the review ran, and `admin.sock` beside it."""
    monkeypatch.setattr(configstore, "HEADERS_WAIT", 0.5)
    monkeypatch.setattr(configstore, "ROLE_CONNECTIONS", 6)
    before = threading.active_count()
    with Daemon() as dm:
        for sock in ("vmsworker.sock", "admin.sock"):
            path = os.path.join(dm.dir, sock)
            idle = []
            for _ in range(6):
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(path)
                idle.append(s)
            time.sleep(0.2)
            t0 = time.monotonic()
            busy = _raw(path, b"GET /v1/status HTTP/1.1\r\nHost: x\r\n\r\n")
            assert busy.startswith(b"HTTP/1.1 503") and b'"unavailable"' in busy, (sock, busy[:80])
            assert time.monotonic() - t0 < 1.0, "the full door kept the next caller waiting"
            if sock == "vmsworker.sock":
                try:
                    open_vars(url(dm.dir, "vmsworker")).put("vms/slots/w-1", {"holder": "x"})
                    raise AssertionError("a full socket took a write")
                except StoreUnavailable as e:
                    assert not isinstance(e, StoreAmbiguous), f"a refused connection was said to be maybe done: {e}"
            for s in idle:
                s.settimeout(2.0)
                assert s.recv(1) == b"", f"{sock}: an idle connection was kept past its headers' deadline"
                s.close()
            time.sleep(0.2)
            assert open_vars(url(dm.dir, sock[:-5])).get("vms/slots/w-1") == (None, 0), sock
    time.sleep(0.3)
    assert threading.active_count() <= before + 1, (before, threading.active_count())


def _role_door(dm, role: str):
    path = os.path.join(dm.dir, f"{role}.sock")
    return next(s for s in dm.d.servers if getattr(s, "server_address", None) == path)


def test_processes_of_one_role_leave_no_connection_held_at_their_socket():
    """The product's cross-check (C), the client's half: a pool of keep-alive connections, 16 idle per process, four
    processes of one role — the whole door, and the fifth process was answered 503 for five seconds. The handle keeps
    no pool: a connection per call, closed in the call (`unix_transport`). Four handles of one role, eight threads
    each, two hundred calls at once: not one refused, and nothing held at the socket the moment they are done."""
    with Daemon() as dm:
        door = _role_door(dm, "vmsworker")
        handles = [open_vars(url(dm.dir, "vmsworker")) for _ in range(4)]
        errors = []

        def calls(h, n):
            try:
                for i in range(25):
                    h.put(f"vms/slots/w-{n}", {"holder": str(i)})
                    h.get(f"vms/slots/w-{n}")
            except Exception as e:                     # noqa: BLE001
                errors.append(e)
        threads = [threading.Thread(target=calls, args=(h, 8 * k + j)) for k, h in enumerate(handles) for j in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors and door.refused == 0, (errors[:3], door.refused)
        end = time.monotonic() + 2.0                               # a loaded box: the door's threads end when they end
        while door.serving and time.monotonic() < end:
            time.sleep(0.05)
        assert door.serving == 0, f"{door.serving} connection(s) held after every call was answered"


def test_a_role_socket_lets_a_kept_alive_connection_go_once_it_has_answered(monkeypatch):
    """C, the door's half, reproduced with the product's client — one that keeps its connection for the next call. The
    door spoke HTTP/1.1 and kept every answered connection until its next request's headers' deadline (5 s): six
    such callers on a socket of six, each answered once, and the seventh was refused `busy` until they timed out —
    the product's 503 for five seconds. Nobody here sends two requests on one connection, so a door answers and
    closes (`Connection: close`): a caller that keeps its socket keeps nothing of the door's."""
    monkeypatch.setattr(configstore, "ROLE_CONNECTIONS", 6)
    import http.client
    from w2cplatform.configstorevars import _UnixConnection
    with Daemon() as dm:
        path = os.path.join(dm.dir, "vmsworker.sock")
        kept, said = [], []
        for _ in range(6):
            c = _UnixConnection(path, 5.0)
            c.request("GET", "/v1/status")
            r = c.getresponse()
            r.read()
            assert r.status == 200
            said.append((r.getheader("Connection") or "").lower())
            kept.append(c)                                         # the caller keeps it, as a pool does
        door = _role_door(dm, "vmsworker")
        end = time.monotonic() + 2.0                               # a loaded box: the door's threads end when they end
        while door.serving and time.monotonic() < end:
            time.sleep(0.05)
        try:
            assert door.serving == 0 and said == ["close"] * 6, (door.serving, said)   # kept: six, for five seconds
            open_vars(url(dm.dir, "vmsworker")).put("vms/slots/w-1", {"holder": "x"})   # served, not `busy`
        finally:
            for c in kept:
                c.close()


def _queued(family, where, n: int) -> int:
    """How many of `n` connections at once the kernel takes for a door that has not accepted one yet."""
    held, taken = [], 0
    try:
        for _ in range(n):
            s = socket.socket(family, socket.SOCK_STREAM)
            s.settimeout(0.5)
            held.append(s)
            try:
                s.connect(where)
            except OSError:                          # refused (a unix socket), or its SYN dropped (TCP)
                break
            taken += 1
        return taken
    finally:
        for s in held:
            s.close()


def test_a_door_queues_as_many_connections_as_it_serves_before_it_accepts_one():
    """The flake of the test above, found: a role socket was opened with `socketserver`'s queue of 5, and a unix socket
    whose queue is full refuses `connect` — six idle callers at once, before the accepting thread woke, and the sixth
    was `ConnectionRefusedError`: neither served nor answered `busy`. The kernel's queue is the door's bound — a role
    socket's `ROLE_CONNECTIONS`, the `-api` door's `API_CONNECTIONS` (a TCP door drops the SYN instead: a second's
    wait) — so a burst as large as the bound waits to be counted, whatever the accepting thread is doing."""
    d = short_dir()
    try:
        path = os.path.join(d, "vmsworker.sock")
        srv = configstore._unix_server(path, socketserver.BaseRequestHandler, 0o600, None)   # never accepts
        try:
            assert _queued(socket.AF_UNIX, path, configstore.ROLE_CONNECTIONS) == configstore.ROLE_CONNECTIONS
        finally:
            srv.server_close()
        api = configstore._TlsServer(("127.0.0.1", 0), socketserver.BaseRequestHandler,
                                     tls.ServerContext(os.path.join(TLS, "srv-a")))
        try:
            assert _queued(socket.AF_INET, api.server_address, configstore.API_CONNECTIONS) == configstore.API_CONNECTIONS
        finally:
            api.server_close()
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_length_that_is_no_byte_count_or_past_the_ceiling_is_refused_unread_at_every_door():
    """The reviewer's probe: `Content-Length: -1` was `read(-1)` — a read to the end of a connection the caller keeps
    open, the door's thread held. A length that is not a non-negative number is 400, one past `MAX_BODY` 413, neither
    read, at once — on a role's socket, `admin.sock` and the `-api` door (`read_body`, the platform's)."""
    with Daemon(api=True) as dm:
        for sock in ("vmsworker.sock", "admin.sock"):
            for length, code in ((b"-1", b"400"), (b"ten", b"400"), (str(configstore.MAX_BODY + 1).encode(), b"413")):
                t0 = time.monotonic()
                said = _raw(os.path.join(dm.dir, sock), b"POST /v1/write HTTP/1.1\r\nHost: x\r\nContent-Length: " +
                            length + b"\r\n\r\n{")
                assert said.startswith(b"HTTP/1.1 " + code), (sock, length, said[:80])
                assert time.monotonic() - t0 < 1.0, (sock, length)
        import http.client
        host, port = dm.d.api_url.rsplit(":", 1)
        ctx = tls.client_context(os.path.join(TLS, "srv-b"))
        for length, code in (("-1", 400), (str(configstore.MAX_BODY + 1), 413)):
            s = ctx.wrap_socket(socket.create_connection((host, int(port)), timeout=5), server_hostname="srv-a")
            s.sendall(f"POST /v1/join HTTP/1.1\r\nHost: x\r\nContent-Length: {length}\r\n\r\n{{".encode())
            r = http.client.HTTPResponse(s)
            r.begin()
            assert r.status == code, (length, r.status)
            s.close()


def test_the_api_door_serves_so_many_of_one_address_and_lets_a_stalled_handshake_go(monkeypatch):
    """The `-api` door is a door too (the sibling the review did not run): a connection that never finishes its TLS
    handshake holds a place for `DOOR_TIMEOUT` at most, one address holds `API_PER_ADDRESS` places, and the next of it
    is closed on the spot — there is no TLS yet to answer it in. Once the stalled ones are let go a daemon is served."""
    monkeypatch.setattr(configstore, "API_CONNECTIONS", 4)
    monkeypatch.setattr(configstore, "API_PER_ADDRESS", 2)
    monkeypatch.setattr(configstore, "DOOR_TIMEOUT", 0.5)
    with Daemon(api=True) as dm:
        host, port = dm.d.api_url.rsplit(":", 1)
        stalled = [socket.create_connection((host, int(port)), timeout=3) for _ in range(2)]
        time.sleep(0.1)
        extra = socket.create_connection((host, int(port)), timeout=3)
        t0 = time.monotonic()
        assert extra.recv(1) == b"" and time.monotonic() - t0 < 0.4, "the address's third connection was served"
        extra.close()
        for s in stalled:
            assert s.recv(1) == b"", "a handshake that never came was waited on"
            s.close()
        assert configstore.peer_call(f"srv-a@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")["id"] \
            == "srv-a"


def test_another_daemon_changes_the_group_only_for_its_own_server_and_never_touches_a_row():
    """The review's twelfth pass, major 3: a daemon's certificate deleted slots, wrote the schema, added false voters
    and removed members. On the `-api` door a daemon reads the group's status, and joins and leaves for the server
    its certificate names (srv-b's certificate: srv-b, not srv-c, not srv-a). The thirteenth pass, major 1, by its
    probe (`probe_mtls.py`): `X-Configstore-Forwarded: vmsworker` made srv-b's certificate the worker — it deleted
    `vms/slots/w-1`; `domain` read and deleted `domain/keys/k1`. Nobody forwards in the course, so the path is gone:
    a data request on the door is 403 with or without the mark, for every role it names, and the log never moves."""
    with Daemon(api=True) as dm:
        api, ctx = dm.d.api_url, tls.client_context(os.path.join(TLS, "srv-b"))
        call = lambda m, r, b=b"{}", h=None: _dial(api, ctx, "srv-a", m, r, b, h)      # noqa: E731
        write = lambda key: json.dumps({"op": "put", "key": key, "items": {"x": "1"}}).encode()   # noqa: E731
        drop = lambda key: json.dumps({"op": "delete", "key": key}).encode()             # noqa: E731
        fwd = "X-Configstore-Forwarded"
        assert not hasattr(configstore, "FORWARDED")
        assert call("GET", "/v1/status")[0] == 200
        for route, body in (("/v1/join", {"id": "srv-c", "raft": "127.0.0.1:1"}), ("/v1/leave", {"id": "srv-a"})):
            code, said = call("POST", route, json.dumps(body).encode())
            assert (code, said["kind"]) == (403, "forbidden") and "srv-b" in said["error"], (route, said)
        assert call("POST", "/v1/leave", b'{"id": "srv-b"}')[0] == 503                  # its own: a store that is no group
        dm.backend.machine.apply({"op": "put", "key": "vms/slots/w-1", "items": {"holder": "w"}})
        dm.backend.machine.apply({"op": "put", "key": "domain/keys/k1", "items": {"k": "secret"}})
        applied = dm.backend.machine.applied
        for headers in (None, *({fwd: role} for role in ("vmsworker", "console", "domain", "admin", "configstore",
                                                           "nobody", ""))):
            for method, route, body in (("POST", "/v1/write", write("vms/slots/w-1")),
                                        ("POST", "/v1/write", drop("vms/slots/w-1")),
                                        ("POST", "/v1/write", drop("domain/keys/k1")),
                                        ("GET", "/v1/get?key=domain/keys/k1", None),
                                        ("GET", "/v1/get?key=vms/cameras/1", None),
                                        ("GET", "/v1/list?prefix=", None)):
                code, said = call(method, route, body, headers)
                assert (code, said["kind"]) == (403, "forbidden"), (headers, route, code, said)
        assert dm.backend.machine.applied == applied, "a refused request reached the log"
        assert set(dm.backend.machine.rows) == {"vms/slots/w-1", "domain/keys/k1"}


def test_a_certificate_that_names_no_server_is_refused_and_a_join_names_a_server():
    """The review's thirteenth pass, minor: a certificate without «.» in its CN and without a SAN DNS gave
    `peer_server` "", and `join` with `id: ""` passed the check that the id is the caller's own (`w2c-ca.sh` issues
    no such certificate; another tool could). Such a peer is refused at the door; and a join — the operator's too —
    names a server and a raft address that are what their names say, bounded: they become a member row of the log."""
    role = (("URI", tls.ROLE_URI + "configstore"),)

    class Conn:
        def __init__(self, cert):
            self.cert = cert

        def getpeercert(self):
            return self.cert

    class Handler:
        def __init__(self, cert):
            self.connection, self.peer = Conn(cert), None

    for cert in ({"subject": ((("commonName", "configstore"),),), "subjectAltName": role},
                 {"subject": ((("commonName", "anything"),),), "subjectAltName": role + (("DNS", ""),)}):
        with pytest.raises(PermissionError):
            configstore._peer_role(Handler(cert))
    ok = Handler({"subject": ((("commonName", "configstore.srv-b"),),), "subjectAltName": role})
    assert configstore._peer_role(ok) == "configstore" and ok.peer == "srv-b"
    dm = StoreDaemon(LocalBackend(), node_id="srv-a")
    for body in ({"id": "", "raft": "127.0.0.1:1"}, {"id": "srv b", "raft": "127.0.0.1:1"},
                 {"id": "x" * 65, "raft": "127.0.0.1:1"}, {"id": "srv-b", "raft": "x" * (1 << 20) + ":1"},
                 {"id": "srv-b", "raft": "127.0.0.1"}, {"id": "srv-b", "raft": "127.0.0.1:1", "api": ["x"]},
                 {"id": 7, "raft": "127.0.0.1:1"}, [1]):
        for role_, peer in (("admin", ""), ("configstore", "srv-b"), ("configstore", "")):
            code, said = dm.serve("POST", "/v1/join", json.dumps(body).encode(), role_, 1.0, peer=peer)
            assert code == 400 and len(json.dumps(said)) < 400, (body if len(str(body)) < 80 else "big", code)
    code, said = dm.serve("POST", "/v1/join", b'{"id": "srv-b", "raft": "127.0.0.1:1"}', "configstore", 1.0, peer="")
    assert code == 403, said


# -- revocation ------------------------------------------------------------------------------------------
def _w2c_ca(ca: str, *args: str) -> str:
    import subprocess
    script = os.path.join(HERE, os.pardir, "deploy", "w2c-ca.sh")
    env = {**os.environ, "W2C_CA_DIR": ca, "W2C_CA_DAYS": "30"}
    done = subprocess.run(["sh", script, *args], env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_a_revoked_daemon_is_refused_at_the_api_door_and_on_its_join_and_the_door_hears_of_it_without_a_restart():
    """The review's thirteenth pass, major 5: a decommissioned or stolen server's bundle — 825 days — joined under its
    own id; there was no revocation. `w2c-ca.sh revoke <server>` puts every certificate issued for the server on the
    CA's revocation list and writes `crl.pem` into every bundle; both sides of the `-api` door verify against it.
    Run end to end with the script: srv-x is a daemon (status 200, its join reaches the backend); revoked, its
    handshake fails at a door that is ALREADY running (the door re-reads the list when the file changes) — no status,
    no join — while srv-b goes on; a daemon dialling the revoked srv-x refuses it; a re-issued srv-x certificate
    replaced in the bundle before the revocation is revoked with it; and a bundle without the list opens no door."""
    ca, stolen = short_dir(), short_dir()
    try:
        _w2c_ca(ca, "init")
        for server in ("srv-a", "srv-b", "srv-x"):
            _w2c_ca(ca, "issue", server)
        for f in ("ca.pem", "crl.pem", "server.pem", "server.key"):                # the first bundle, as somebody kept it
            shutil.copy(os.path.join(ca, "srv-x", f), stolen)
        _w2c_ca(ca, "issue", "srv-x")                                             # re-issued: the bundle holds a new one
        join = json.dumps({"id": "srv-x", "raft": "127.0.0.1:1"}).encode()
        with Daemon(api=True, tls_dir=os.path.join(ca, "srv-a")) as dm:
            api = dm.d.api_url
            ctxs = {name: tls.client_context(d) for name, d in (("srv-x", os.path.join(ca, "srv-x")),
                                                                ("stolen", stolen), ("srv-b", os.path.join(ca, "srv-b")))}
            for name in ("srv-x", "stolen"):
                assert _dial(api, ctxs[name], "srv-a", "GET", "/v1/status")[0] == 200, name
                assert _dial(api, ctxs[name], "srv-a", "POST", "/v1/join", join)[0] == 503, name   # the backend: no group
            out = _w2c_ca(ca, "revoke", "srv-x")
            assert out.count("revoked ") == 2 and "raft.secret" in out, out
            for name in ("srv-x", "stolen"):
                for method, route, body in (("GET", "/v1/status", b""), ("POST", "/v1/join", join)):
                    with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
                        _dial(api, ctxs[name], "srv-a", method, route, body)
            assert _dial(api, ctxs["srv-b"], "srv-a", "GET", "/v1/status")[0] == 200
        with Daemon(api=True, tls_dir=os.path.join(ca, "srv-x")) as revoked:           # srv-x answering a join
            with pytest.raises(ssl.SSLError):
                configstore.peer_call(f"srv-x@{revoked.d.api_url}", os.path.join(ca, "srv-b"), "GET", "/v1/status")
        os.remove(os.path.join(ca, "srv-b", "crl.pem"))
        with refused_missing():
            tls.server_context(os.path.join(ca, "srv-b"))
    finally:
        shutil.rmtree(ca, ignore_errors=True)
        shutil.rmtree(stolen, ignore_errors=True)


@contextlib.contextmanager
def refused_missing():
    try:
        yield
    except FileNotFoundError as e:
        assert "crl.pem" in str(e), e
        return
    raise AssertionError("a door opened without its revocation list")


def _forge(ca: str, server: str, roles: list[str], out: str) -> None:
    """A bundle in `out` whose `server.pem` the CA of `ca` signed for `roles` — one `w2c-ca.sh issue` would not make,
    another tool's."""
    import subprocess
    os.makedirs(out, exist_ok=True)
    key, pem, csr, ext = (os.path.join(out, f) for f in ("server.key", "server.pem", "x.csr", "x.ext"))
    with open(ext, "w") as f:
        f.write("basicConstraints = critical, CA:FALSE\nkeyUsage = critical, digitalSignature, keyEncipherment\n"
                "extendedKeyUsage = serverAuth, clientAuth\n"
                f"subjectAltName = DNS:{server}," + ",".join(f"URI:{tls.ROLE_URI}{r}" for r in roles) + "\n")
    for cmd in (["ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", key],
                ["req", "-new", "-key", key, "-subj", f"/CN={roles[0]}.{server}", "-out", csr],
                ["x509", "-req", "-in", csr, "-CA", os.path.join(ca, "ca.pem"), "-CAkey", os.path.join(ca, "ca.key"),
                 "-CAserial", os.path.join(ca, "ca.srl"), "-days", "30", "-sha256", "-extfile", ext, "-out", pem]):
        subprocess.run(["openssl", *cmd], check=True, capture_output=True, timeout=30)
    for f in ("ca.pem", "crl.pem", "raft.secret"):
        shutil.copy(os.path.join(ca, f), out)
    os.chmod(os.path.join(out, "raft.secret"), 0o600)
    os.remove(csr)
    os.remove(ext)


def test_a_certificate_with_the_store_role_and_another_is_no_daemons_at_the_door_on_a_call_or_at_start():
    """The product's cross-check (hashicorp/raft): a certificate that carries `configstore` TOGETHER with another role
    (configstore+recworker) was a daemon wherever the role was asked — `require_role` granted on any of its roles. A
    daemon's certificate carries exactly one role: `w2c-ca.sh issue` refuses `configstore` with another; the `-api`
    door answers such a certificate 403 (status and join alike); a daemon dialling a door that shows one refuses it;
    and a daemon handed one as its own refuses to start — the door and the member alike. A recorder's certificate of
    several roles is still several roles: the rule is the store's."""
    import subprocess
    ca, dual = short_dir(), short_dir()
    try:
        _w2c_ca(ca, "init")
        for server in ("srv-a", "srv-b"):
            _w2c_ca(ca, "issue", server)
        script = os.path.join(HERE, os.pardir, "deploy", "w2c-ca.sh")
        for roles in (["configstore", "recworker"], ["recworker", "configstore"]):
            done = subprocess.run(["sh", script, "issue", "srv-x", *roles], env={**os.environ, "W2C_CA_DIR": ca},
                                  capture_output=True, text=True, timeout=60)
            assert done.returncode != 0 and "one role" in done.stderr, (roles, done.stdout, done.stderr)
        assert not os.path.exists(os.path.join(ca, "srv-x", "server.pem"))
        _forge(ca, "srv-b", ["configstore", "recworker"], dual)
        assert tls.peer_roles(ssl._ssl._test_decode_cert(os.path.join(dual, "server.pem"))) == {"configstore",
                                                                                                "recworker"}
        with refused("one role"):
            tls.client_context(dual)                  # our own contexts are not built on it: the caller's is plain ssl

        def plain(side):
            ctx = ssl.SSLContext(side)
            ctx.load_cert_chain(os.path.join(dual, "server.pem"), os.path.join(dual, "server.key"))
            ctx.load_verify_locations(os.path.join(dual, "ca.pem"))
            ctx.check_hostname = side == ssl.PROTOCOL_TLS_CLIENT
            return ctx

        join = json.dumps({"id": "srv-b", "raft": "127.0.0.1:1"}).encode()
        with Daemon(api=True, tls_dir=os.path.join(ca, "srv-a")) as dm:
            api, ctx = dm.d.api_url, plain(ssl.PROTOCOL_TLS_CLIENT)
            for method, route, body in (("GET", "/v1/status", b""), ("POST", "/v1/join", join)):
                code, said = _dial(api, ctx, "srv-a", method, route, body)
                assert (code, said.get("kind")) == (403, "forbidden") and "one role" in said["error"], (route, said)
            assert _dial(api, tls.client_context(os.path.join(ca, "srv-b")), "srv-a", "GET", "/v1/status")[0] == 200

        class Shows:                                  # a door that shows the certificate, as another program's might
            def get(self):
                ctx = plain(ssl.PROTOCOL_TLS_SERVER)
                ctx.verify_mode = ssl.CERT_REQUIRED
                return ctx

        door = configstore._TlsServer(("127.0.0.1", 0), configstore._door(StoreDaemon(LocalBackend(), node_id="srv-b"),
                                                                          configstore._peer_role), Shows())
        threading.Thread(target=door.serve_forever, daemon=True).start()
        try:
            with pytest.raises(PermissionError):
                configstore.peer_call(f"srv-b@127.0.0.1:{door.server_address[1]}", os.path.join(ca, "srv-a"), "GET",
                                      "/v1/status")
        finally:
            door.shutdown()
            door.server_close()
        with refused("one role"):
            StoreDaemon(LocalBackend(), node_id="srv-b", api=("127.0.0.1", 0), tls_dir=dual)
        with refused("one role"):
            configstore.start_member("srv-b", short_dir(), f"127.0.0.1:{_free_port()}", bootstrap=True, tls_dir=dual)
    finally:
        shutil.rmtree(ca, ignore_errors=True)
        shutil.rmtree(dual, ignore_errors=True)


def test_a_revocation_is_never_lifted_by_the_list_going_missing_or_changing_unseen():
    """The product's cross-check (hashicorp/raft): a revocation could be lifted by accident — the list missing at start
    meant no revocation, a list deleted while running read as empty, and one rewritten with the same size and mtime
    was not read again. Here: missing at start, no door (as before); deleted while the door runs, the door keeps the
    list it holds — the revoked srv-x stays out and srv-b stays in (it used to shut the door on everybody); and a
    list rewritten in place with the same size and the same mtime is seen by its CONTENT — srv-x, revoked by the new
    list, is out at once. A list that does not load keeps the one held too, and is tried again on the next caller."""
    ca = short_dir()
    try:
        _w2c_ca(ca, "init")
        for server in ("srv-a", "srv-b", "srv-x"):
            _w2c_ca(ca, "issue", server)
        crl = os.path.join(ca, "srv-a", "crl.pem")
        before = open(crl, "rb").read()
        _w2c_ca(ca, "revoke", "srv-x")
        after = open(os.path.join(ca, "crl.pem"), "rb").read()
        assert after != before
        # The two lists at one size: text outside a PEM block is no part of it (OpenSSL reads the blocks).
        width = max(len(before), len(after))
        before, after = (t + b"#" * (width - len(t)) + b"\n" for t in (before, after))
        with open(crl, "wb") as f:
            f.write(before)
        stamp = os.stat(crl)
        ctxs = {s: tls.client_context(os.path.join(ca, s)) for s in ("srv-b", "srv-x")}
        with Daemon(api=True, tls_dir=os.path.join(ca, "srv-a")) as dm:
            api = dm.d.api_url
            status = lambda who: _dial(api, ctxs[who], "srv-a", "GET", "/v1/status", b"")[0]   # noqa: E731
            assert status("srv-x") == 200 and status("srv-b") == 200
            with open(crl, "r+b") as f:                       # rewritten in place: the same inode, size and mtime
                f.write(after)
            os.utime(crl, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            assert (os.stat(crl).st_ino, os.stat(crl).st_size, os.stat(crl).st_mtime_ns) == \
                (stamp.st_ino, stamp.st_size, stamp.st_mtime_ns)
            with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
                status("srv-x")
            said = io.StringIO()
            with contextlib.redirect_stderr(said):
                os.remove(crl)                                # deleted while running: the list held stays
                with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
                    status("srv-x")
                assert status("srv-b") == 200 and status("srv-b") == 200
                with open(crl, "wb") as f:                    # half a copy: does not load — the list held stays
                    f.write(after[:len(after) // 2])
                with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
                    status("srv-x")
                assert status("srv-b") == 200
            lines = said.getvalue().splitlines()              # each trouble said once, not per caller
            assert len(lines) == 2 and all("could not be read" in line for line in lines), lines
            with open(crl, "wb") as f:                        # the copy finished: read on the next caller
                f.write(before)
            assert status("srv-x") == 200
        os.remove(crl)
        with refused_missing():
            tls.ServerContext(os.path.join(ca, "srv-a"))
    finally:
        shutil.rmtree(ca, ignore_errors=True)


def _another_ca(ca: str) -> None:
    """Another installation's CA in `ca`, made by `w2c-ca.sh init` and named apart: every CA the script makes is
    «w2c installation CA», and OpenSSL, finding ours by that name first, would refuse the stranger by luck."""
    import subprocess
    _w2c_ca(ca, "init")
    ext = os.path.join(ca, "x.ext")
    with open(ext, "w") as f:
        f.write("[req]\ndistinguished_name = dn\n[dn]\n[ca]\nbasicConstraints = critical, CA:TRUE\n"
                "keyUsage = critical, keyCertSign, cRLSign\nsubjectKeyIdentifier = hash\n")
    subprocess.run(["openssl", "req", "-x509", "-new", "-key", os.path.join(ca, "ca.key"), "-sha256", "-days", "30",
                    "-subj", "/CN=another installation CA", "-config", ext, "-extensions", "ca",
                    "-out", os.path.join(ca, "ca.pem")], check=True, capture_output=True, timeout=30)
    os.remove(ext)
    _w2c_ca(ca, "crl")


def test_ca_pem_is_exactly_one_ca_certificate_and_a_foreign_ca_beside_it_is_refused_not_trusted():
    """The product's cross-check (hashicorp/raft): `load_verify_locations(ca.pem)` trusts EVERY certificate in the
    file, so a foreign CA appended to it (with its list appended to `crl.pem`, which the leaf check needs) let that
    CA's daemon certificate through the `-api` door — 200 on status. `ca.pem` is exactly one CA certificate block now,
    in any of the spellings OpenSSL reads; two are refused by the door, the caller and the raft password alike, and
    the CA is loaded from the one block only. CRLF line ends and text around the block are fine."""
    ours, foreign = short_dir(), short_dir()
    try:
        _w2c_ca(ours, "init")
        _w2c_ca(ours, "issue", "srv-a")
        _another_ca(foreign)
        _w2c_ca(foreign, "issue", "srv-b")
        bundle = os.path.join(ours, "srv-a")
        ca_text = open(os.path.join(bundle, "ca.pem")).read()
        crl_text = open(os.path.join(bundle, "crl.pem")).read()
        alien = open(os.path.join(foreign, "ca.pem")).read()
        # The stranger's daemon: its own CA's certificate, and our CA and list, which are no secret, to dial us.
        for f in ("ca.pem", "crl.pem"):
            shutil.copy(os.path.join(bundle, f), os.path.join(foreign, "srv-b", f))
        alien_ctx = tls.client_context(os.path.join(foreign, "srv-b"))
        for spelling in (alien, alien.replace("CERTIFICATE", "TRUSTED CERTIFICATE")):
            with open(os.path.join(bundle, "ca.pem"), "w") as f:
                f.write(ca_text + spelling)
            with open(os.path.join(bundle, "crl.pem"), "w") as f:
                f.write(crl_text + open(os.path.join(foreign, "crl.pem")).read())
            for build in (tls.server_context, tls.client_context, tls.ServerContext, tls.raft_secret):
                with refused("one CA certificate"):
                    build(bundle)
        with open(os.path.join(bundle, "crl.pem"), "w") as f:
            f.write(crl_text)
        for text in ("# the installation's CA\r\n" + ca_text.replace("\n", "\r\n") + "\r\n\r\n", "\n\n" + ca_text):
            with open(os.path.join(bundle, "ca.pem"), "w") as f:
                f.write(text)
            with Daemon(api=True, tls_dir=bundle) as dm:
                assert _dial(dm.d.api_url, tls.client_context(bundle), "srv-a", "GET", "/v1/status", b"")[0] == 200
                with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
                    _dial(dm.d.api_url, alien_ctx, "srv-a", "GET", "/v1/status", b"")
    finally:
        shutil.rmtree(ours, ignore_errors=True)
        shutil.rmtree(foreign, ignore_errors=True)


# -- the handle -----------------------------------------------------------------------------------------
def test_a_write_asked_again_after_its_outcome_was_unknown_carries_its_first_id_and_is_applied_once():
    """The review's twelfth pass, minor, and its probe: two calls of the same `put` after a cut connection carried two
    ids, so a first copy that had landed was not recognised and the repeat's CAS conflicted with it — what fences a
    worker. The same write asked again carries the id of the one whose outcome is unknown, and is answered with the
    first copy's index; a write that got an answer forgets it, and a different write has an id of its own."""
    from w2cplatform.storemachine import ADMIN, StoreMachine, local_transport
    from w2cplatform.configstorevars import ConfigstoreVariables
    m = StoreMachine(1000)
    inner = local_transport(m.apply, RIGHTS, ADMIN)
    sent, cut = [], {"next": False}

    def transport(method, target, raw, headers, timeout):
        if raw:
            sent.append(json.loads(raw)["id"])
        got = inner(method, target, raw, headers, timeout)
        if cut["next"]:
            cut["next"] = False
            raise ConnectionResetError("the daemon went after applying it")
        return got

    h = ConfigstoreVariables("/stand", transport=transport)
    v = h.put("vms/slots/w-1", {"holder": "a"}, cas=0)
    cut["next"] = True
    with pytest.raises(StoreAmbiguous):
        h.put("vms/slots/w-1", {"holder": "a", "n": "2"}, cas=v)
    landed = m.rows["vms/slots/w-1"][1]
    assert landed > v, "the first copy should have landed"
    again = h.put("vms/slots/w-1", {"holder": "a", "n": "2"}, cas=v)       # not `Conflict`: the same write, once
    assert again == landed and sent[-1] == sent[-2]
    h.put("vms/slots/w-1", {"holder": "a", "n": "3"}, cas=again)
    assert sent[-1] != sent[-2], "a new write took an old one's id"
    # the reviewer's own probe: a transport that cuts every time — both calls carry one id
    ids = []

    def cutting(method, target, raw, headers, timeout):
        ids.append(json.loads(raw)["id"])
        raise ConnectionResetError("cut")

    probe = ConfigstoreVariables("/stand", transport=cutting)
    for _ in range(2):
        with pytest.raises(StoreAmbiguous):
            probe.put("vms/x", {"a": "r"}, cas=5)
    assert ids[0] == ids[1]


def test_a_write_asked_again_after_another_write_to_its_key_is_a_new_write_and_is_applied():
    """The review's thirteenth pass, major 4, by its probe (`probe_unknown_aba.py`): `put on` — ambiguous, it landed;
    `put off` — OK; `put on` again went with the first `on`'s id and was answered «OK (2)» from the machine's memory,
    and the row stayed `off`. The same with delete, put, delete and with create-only. A repeat is a repeat only of the
    LAST write asked of its key: a later write to the key ends it, whatever its outcome, so the third call is a new
    write with a new id, and is applied. Each sequence also with the middle write ambiguous too."""
    from w2cplatform.storemachine import ADMIN, StoreMachine, local_transport
    from w2cplatform.configstorevars import ConfigstoreVariables
    for middle_cut in (False, True):
        m = StoreMachine(1000)
        inner = local_transport(m.apply, RIGHTS, ADMIN)
        cut = {"n": 0}

        def transport(method, target, raw, headers, timeout):
            got = inner(method, target, raw, headers, timeout)  # the daemon applies; the answer may be cut
            if cut["n"]:
                cut["n"] -= 1
                raise ConnectionResetError("answer cut")
            return got

        h = ConfigstoreVariables("/stand", transport=transport)
        row = lambda key: m.rows.get(key, (None,))[0]                               # noqa: E731

        def step(do, cut_it):
            cut["n"] = 1 if cut_it else 0
            try:
                do()
            except StoreAmbiguous:
                assert cut_it

        key = "vms/servers/srv-b"
        m.apply({"op": "put", "key": key, "items": {"state": "init"}})
        step(lambda: h.put(key, {"state": "on"}), True)
        step(lambda: h.put(key, {"state": "off"}), middle_cut)
        step(lambda: h.put(key, {"state": "on"}), False)
        assert row(key) == {"state": "on"}, (middle_cut, row(key))
        key = "vms/locks/cam1"
        m.apply({"op": "put", "key": key, "items": {"owner": "w-1"}})
        step(lambda: h.delete(key), True)
        step(lambda: h.put(key, {"owner": "w-2"}), middle_cut)
        step(lambda: h.delete(key), False)
        assert row(key) is None, (middle_cut, row(key))
        key = "vms/epoch/cam9"
        step(lambda: h.put(key, {"epoch": "1"}, cas=0), True)
        m.apply({"op": "delete", "key": key})                                        # gone again, by somebody
        step(lambda: h.put(key, {"epoch": "2"}, cas=0), middle_cut)
        m.apply({"op": "delete", "key": key})
        step(lambda: h.put(key, {"epoch": "1"}, cas=0), False)
        assert row(key) == {"epoch": "1"}, (middle_cut, row(key))


# -- the raft port's secret -------------------------------------------------------------------------------
def test_the_raft_secret_is_refused_readable_by_others_or_short_and_is_keyed_by_the_installation():
    """The review's twelfth pass, minor: `raft.secret` was taken whatever its mode and length, and pysyncobj salts
    every installation's key alike. Refused when others may read it or it is shorter than `SECRET_CHARS`; the
    password handed to the library is the secret keyed with the installation's CA — the same for every member of one
    installation, another for another installation with the same secret. The thirteenth pass, minor: the key was
    the hash of `ca.pem`'s BYTES, so one more newline, or a second CA added for a rotation, changed one member's
    password and it dropped out of its group. It is the CA certificate in the file now, whatever text is around it;
    and a second certificate beside it is refused, not keyed past (the product's cross-check: `ca.pem` is exactly
    one CA)."""
    d = short_dir()
    try:
        shutil.copy(os.path.join(TLS, "ca.pem"), d)
        secret = os.path.join(d, "raft.secret")
        with open(secret, "w") as f:
            f.write("ab" * 32 + "\n")
        os.chmod(secret, 0o644)
        with refused("chmod 600"):
            tls.raft_secret(d)
        os.chmod(secret, 0o600)
        mine = tls.raft_secret(d)
        assert mine != "ab" * 32 and mine == tls.raft_secret(d)
        ca_text = open(os.path.join(TLS, "ca.pem")).read()
        other_ca = open(os.path.join(TLS, "srv-a", "server.pem")).read()     # any other certificate will do
        for text in ("\n" + ca_text + "\n\n", ca_text.replace("\n", "\r\n")):
            with open(os.path.join(d, "ca.pem"), "w") as f:
                f.write(text)                          # an editor's newlines
            assert tls.raft_secret(d) == mine
        with open(os.path.join(d, "ca.pem"), "w") as f:
            f.write(ca_text + other_ca)                # a second certificate beside the CA
        with refused("one CA certificate"):
            tls.raft_secret(d)
        with open(os.path.join(d, "ca.pem"), "w") as f:
            f.write(other_ca)                          # another installation's CA
        assert tls.raft_secret(d) != mine
        with open(secret, "w") as f:
            f.write("short\n")
        with refused("fewer than"):
            tls.raft_secret(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# -- a box becomes a cluster: the one-time import, backup and restore ------------------------------------
def _box() -> tuple[FileVariables, dict, int]:
    """A box's file store with rows at various versions: rewritten, deleted, created again."""
    box = FileVariables(tempfile.mkdtemp(), volatile=True)
    remembered = {}
    for n in range(5):
        remembered[f"vms/cameras/{n}"] = box.put(f"vms/cameras/{n}", {"name": f"cam {n}"}, cas=0)
    remembered["vms/epoch/1"] = box.put("vms/epoch/1", {"epoch": "7"}, cas=0)
    remembered["vms/cameras/2"] = box.put("vms/cameras/2", {"name": "renamed"}, cas=remembered["vms/cameras/2"])
    box.delete("vms/cameras/4", cas=remembered.pop("vms/cameras/4"))
    remembered["rec/recordings/1"] = box.put("rec/recordings/1", {"camera": "1", "days": "10"}, cas=0)
    counter = int(open(box.index_file).read())
    return box, remembered, counter


def test_a_box_imported_into_a_fresh_group_keeps_its_values_and_no_version_it_handed_out_matches():
    """`configstore import --from file://…`: the values arrive exactly as the box held them (epochs, generations and
    revisions live inside values); every new version is above the box's counter because the group was started with
    `-index-base` at least that counter — so a CAS with a version a process still remembers from the box conflicts
    instead of matching a different row; and the store goes on keeping the contract after the import."""
    box, remembered, counter = _box()
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        admin = open_vars(url(dm.dir))
        got = configstore.import_rows("file://" + box.root, admin)
        assert got["rows"] == len(remembered) == 7 - 1
        for key in remembered:
            items, index = admin.get(key)
            assert items == box.get(key)[0], key
            assert index > counter, (key, index, counter)
        assert admin.get("vms/cameras/4") == (None, 0)
        for key, old in remembered.items():
            with pytest.raises(Conflict):
                admin.put(key, {"stale": "yes"}, cas=old)
        fresh = admin.put("vms/cameras/9", {"name": "new"}, cas=0)
        assert fresh > max(remembered.values()) and fresh > counter

        from tests import test_variables_contract as contract
        saved = os.environ.get("CONTRACT_URL")
        os.environ["CONTRACT_URL"] = url(dm.dir)
        failed = []
        try:
            for name, fn in vars(contract).items():
                if name.startswith("test_") and callable(fn):
                    try:
                        fn()
                    except Exception as e:             # noqa: BLE001
                        failed.append(f"{name}: {type(e).__name__}: {e}")
        finally:
            if saved is None:
                os.environ.pop("CONTRACT_URL", None)
            else:
                os.environ["CONTRACT_URL"] = saved
        assert not failed, "\n".join(failed)


def test_an_import_is_refused_whole_into_a_group_it_could_confuse():
    """Before the first write: a group whose base is below the box's counter (a remembered version could match a new
    row), a group that already holds rows, and a box with a row that does not read (dropped, it would read as
    absent — an absent epoch starts again from 1)."""
    box, _, counter = _box()
    with Daemon(LocalBackend("srv-a", index_base=counter - 1)) as dm:
        with refused("index-base"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
        assert open_vars(url(dm.dir)).list("") == []
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        open_vars(url(dm.dir)).put("vms/already", {"x": "1"})
        with refused("fresh"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
    with open(box._file("vms/epoch/1"), "w") as f:
        f.write('{"items": {"epoch": "7"}, "ind')
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        with refused("vms/epoch/1"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
        assert open_vars(url(dm.dir)).list("") == []


def test_an_import_that_stopped_goes_on_and_a_row_heavier_than_the_store_takes_refuses_it_whole():
    """The review's twelfth pass, minor: an import that stopped half-way could not be continued — the group held rows,
    and a group with rows is refused. The same import again goes on after the rows it wrote, when every row the group
    holds is one of them, the same; a row it did not write still refuses it. And a box's row heavier than the store
    takes (`MAX_VALUE`; `FileVariables` has no ceiling) refuses the import whole, before the first write."""
    from w2cplatform.storemachine import MAX_VALUE
    box, remembered, counter = _box()

    class Cut:
        def __init__(self, h, after):
            self.h, self.left = h, after

        def __getattr__(self, name):
            return getattr(self.h, name)

        def put(self, *a, **kw):
            if self.left == 0:
                raise OSError("the operator's ssh went")
            self.left -= 1
            return self.h.put(*a, **kw)

    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        admin = open_vars(url(dm.dir))
        with pytest.raises(OSError):
            configstore.import_rows("file://" + box.root, Cut(admin, 2))
        assert len(admin.list("")) == 2
        got = configstore.import_rows("file://" + box.root, admin)
        assert (got["rows"], got["there_before"]) == (len(remembered), 2)
        assert {k: admin.get(k)[0] for k in remembered} == {k: box.get(k)[0] for k in remembered}
        admin.put("vms/cameras/0", {"name": "changed since"}, cas=admin.get("vms/cameras/0")[1])
        with refused("did not write"):
            configstore.import_rows("file://" + box.root, admin)
    box.put("vms/heavy", {"blob": "x" * MAX_VALUE})
    with Daemon(LocalBackend("srv-a", index_base=counter + 10)) as dm:
        with refused("vms/heavy"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
        assert open_vars(url(dm.dir)).list("") == []


def test_a_backup_restores_into_a_fresh_group_above_its_highest_version():
    """`configstore backup` / `restore`: every row and the highest version the group could have handed out; the
    restored group keeps the values and conflicts with every version from before."""
    with Daemon(LocalBackend("srv-a", 1000)) as a:
        h = open_vars(url(a.dir))
        old = {f"vms/cameras/{n}": h.put(f"vms/cameras/{n}", {"name": str(n)}, cas=0) for n in range(4)}
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["backup", "--socket", url(a.dir)])
        backup = json.loads(out.getvalue())
    assert backup["highest"] >= max(old.values())
    path = os.path.join(tempfile.mkdtemp(), "rows.json")
    with open(path, "w") as f:
        json.dump(backup, f)
    with Daemon(LocalBackend("srv-b", 10)) as low:
        with refused("index-base"):
            configstore.main(["restore", "--from", path, "--socket", url(low.dir)])
    with Daemon(LocalBackend("srv-b", backup["highest"])) as b:
        with redirect_stdout(io.StringIO()):
            configstore.main(["restore", "--from", path, "--socket", url(b.dir)])
        h = open_vars(url(b.dir))
        for key, index in old.items():
            assert h.get(key)[0] == {"name": key.rsplit("/", 1)[1]}
            with pytest.raises(Conflict):
                h.put(key, {"name": "stale"}, cas=index)


def test_the_operator_commands_speak_to_the_admin_socket():
    """`python3 -m w2cplatform.configstore status | rights [file]` — the product's own `configstore …` command."""
    with Daemon() as dm:
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["status", "--socket", url(dm.dir)])
        assert json.loads(out.getvalue())["id"] == "srv-a"
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["rights", "--socket", url(dm.dir)])
        assert sorted(json.loads(out.getvalue())["roles"]) == ["console", "vmsworker"]


def test_a_process_reads_platform_store_and_no_other_name():
    """One function says which store a process opens (`variables.store_url`, product P7): `PLATFORM_STORE`, else the
    process's default. The older name `CONFIG_URL` is not read (the owner's rule of 4 Oct: no aliases, the system runs
    on one machine) — set alone, the process opens its default and not that store."""
    both = {"PLATFORM_STORE": "configstore:///run/configstore/vmsworker.sock", "CONFIG_URL": "file:///data/c"}
    assert store_url(both) == both["PLATFORM_STORE"]
    assert store_url({"CONFIG_URL": "file:///data/c"}) is None
    assert store_url({"CONFIG_URL": "file:///data/c"}, "file:///data/platform/config") == "file:///data/platform/config"
    assert store_url({"PLATFORM_STORE": "", "CONFIG_URL": "memory://x"}, "file:///d") == "file:///d"
    entry = os.path.join(os.path.dirname(HERE), "vms", "__main__.py")      # the process entry: the same function
    src = open(entry, encoding="utf-8").read()
    assert "store_url(os.environ" in src and "CONFIG_URL" not in src

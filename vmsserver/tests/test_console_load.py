"""The console under load (the review's fifth pass): what a request may cost it before anybody knows who sent it.

    the body after the gate     no token is 401 before a byte of the body is read; a body past the ceiling is 413
    a deadline per request      a request's line and headers arrive whole within `CONSOLE_TIMEOUT`, or it is closed
    a bound on connections      past `CONSOLE_CONNECTIONS` the next is answered 503 at once, not given a thread

…and what the sixth pass found left of it, at the console and at every other door:

    whose connections           one address holds a share of the bound, not all of it; the door in and monitoring have a
                                reserve; the caller on the box — through the unix socket — a lane of its own
    rights before the body      what the path alone decides is asked before a byte of the body; a blob's ceiling is a
                                blob route's alone
    the other doors             the holder's, the recorder's and the gateway's are bounded the same way; what they
                                stream goes in pieces, to a client that takes them, and says when it was cut
"""
import http.client
import json
import os
import socket
import tempfile
import threading
import time

from w2cplatform.access import Gate
from tests.conftest import Box
from tests.test_console_gate import Tokens, _call, _console, _console_with_jobs


def _raw(port: int, data: bytes, wait: float = 5.0) -> tuple[bytes, float]:
    """Send `data` and read whatever comes back until the console closes: `(reply, seconds it took)`."""
    s = socket.create_connection(("127.0.0.1", port))
    s.settimeout(wait)
    began = time.monotonic()
    s.sendall(data)
    out = b""
    try:
        while True:
            got = s.recv(65536)
            if not got:
                break
            out += got
    except (socket.timeout, ConnectionResetError):
        pass
    s.close()
    return out, time.monotonic() - began


def _env(**kw):
    was = {k: os.environ.get(k) for k in kw}
    os.environ.update({k: str(v) for k, v in kw.items()})
    return was


def _restore(was):
    for k, v in was.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_a_body_is_not_read_before_the_caller_is_known_nor_past_its_ceiling():
    """The review's fifth pass, major: `POST /marks` with no token and `Content-Length: 400 MiB` grew the console by
    806 MiB, and only then was told 401 — the gate read the body to find the unit an action names. Now the caller is
    proved from the headers first: no token is 401 at once, the 400 MiB never sent and never waited for. A caller
    with a token who declares more than `MAX_BODY` is 413, also without a byte read; within it, the body is read as
    before."""
    box = Box()
    ctl, rec, m, srv, base = _console(box, Tokens({"guard": [("edit", "1", ())], "admin": [("admin", None, ())]}))
    port = srv.server_address[1]
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        head = (b"POST /marks HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nIdempotency-Key: k\r\n"
                b"Content-Length: 419430400\r\n")
        reply, took = _raw(port, head + b"\r\n")
        assert reply.startswith(b"HTTP/1.0 401") and took < 2.0, (reply[:60], took)     # without the 400 MiB
        reply, took = _raw(port, head + b"Authorization: Bearer guard\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 413") and b"419430400" in reply and took < 2.0
        reply, _ = _raw(port, b"POST /cameras HTTP/1.1\r\nHost: x\r\nContent-Length: lots\r\n"
                              b"Authorization: Bearer admin\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 400")
        assert _call(base, "POST", "/marks", {"cam": 1, "note": "seen"}, token="guard")[0] == 201   # a body within it: as before
    finally:
        srv.shutdown()


def test_a_request_that_trickles_its_headers_is_closed_at_its_deadline():
    """The review's fifth pass, major: `CONSOLE_TIMEOUT` bounded each read, not the request — a header byte every 1.5 s
    under a timeout of 2 kept the connection for as long as the client liked. The request's line and headers have
    `CONSOLE_TIMEOUT` to arrive in whole; past it the console closes the connection, however steadily the bytes come."""
    was = _env(CONSOLE_TIMEOUT=1)
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    port = srv.server_address[1]
    s = socket.create_connection(("127.0.0.1", port))
    try:
        began, closed = time.monotonic(), None
        for b in b"GET /cameras HTTP/1.1\r\nX-Padding: " + b"a" * 40:
            try:
                s.sendall(bytes([b]))
                s.settimeout(0.4)
                if s.recv(1) == b"":
                    closed = time.monotonic() - began
                    break
            except socket.timeout:
                continue                                              # nothing back yet: send the next byte
            except (BrokenPipeError, ConnectionResetError):
                closed = time.monotonic() - began
                break
        assert closed is not None and closed < 3.0, closed            # the deadline, not the client's patience
    finally:
        s.close(); srv.shutdown(); _restore(was)


def test_past_its_bound_on_connections_the_console_answers_503_at_once():
    """The review's fifth pass, major: three hundred slow clients were three hundred threads. `CONSOLE_CONNECTIONS` are
    served at once; the next connection is answered 503 with `Retry-After` by the accepting thread, without being read;
    when a slot frees, the console answers again. (With no reserve here, `CONSOLE_RESERVE=0`: what the reserve is for
    is the next test's.)"""
    was = _env(CONSOLE_CONNECTIONS=3, CONSOLE_TIMEOUT=30, CONSOLE_HEADER_TIMEOUT=30, CONSOLE_RESERVE=0)
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    port = srv.server_address[1]
    held = []
    try:
        for _ in range(3):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(b"GET /cam")                                    # half a request line: each holds its slot
            held.append(s)
        time.sleep(0.2)
        reply, took = _raw(port, b"GET /cameras HTTP/1.1\r\nHost: x\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 503") and b"Retry-After: 1" in reply and took < 2.0
        assert srv.refused >= 1
        for s in held:
            s.close()
        held = []
        for _ in range(50):                                           # the slots come back as their threads end
            reply, _ = _raw(port, b"GET /cameras HTTP/1.1\r\nHost: x\r\n\r\n")
            if reply.startswith(b"HTTP/1.0 200"):
                break
            time.sleep(0.1)
        assert reply.startswith(b"HTTP/1.0 200")
    finally:
        for s in held:
            s.close()
        srv.shutdown(); _restore(was)


# -- the sixth pass: whose connections ----------------------------------------------------------------------------------
class _Unix(http.client.HTTPConnection):
    """HTTP through the console's unix socket — what `curl --unix-socket <path> http://console/…` does on the box."""
    def __init__(self, path: str):
        super().__init__("console", timeout=10)
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def _unix(path: str, method: str, url: str, body=None, headers=None):
    c = _Unix(path)
    try:
        c.request(method, url, body=json.dumps(body).encode() if body is not None else None,
                  headers={"Content-Type": "application/json", **(headers or {})})
        r = c.getresponse()
        return r.status, r.read(), dict(r.getheaders())
    finally:
        c.close()


def _as(who: dict, addr: str, port: int) -> socket.socket:
    """A connection the console sees as coming from `addr`: the test names addresses by source port (`peer_of`) —
    on one machine every caller is 127.0.0.1."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    who[s.getsockname()[1]] = addr
    s.connect(("127.0.0.1", port))
    return s


def _ask(s: socket.socket, data: bytes, wait: float = 5.0) -> bytes:
    s.settimeout(wait)
    s.sendall(data)
    out = b""
    try:
        while True:
            got = s.recv(65536)
            if not got:
                break
            out += got
    except (socket.timeout, ConnectionResetError):
        pass
    s.close()
    return out


def test_a_flood_from_one_address_keeps_neither_the_emergency_entry_at_the_box_nor_monitoring_out():
    """The review's sixth pass, major — reproduced by a run: 64 connections with no token, reconnecting, and 99.3 % of
    all requests were 503, the right emergency password from the box and Prometheus among them. The bound was one for
    everybody and was taken before anybody was known. Now one address holds `CONSOLE_PER_ADDRESS` of the common
    connections and no more; with the common ones gone — taken by many addresses — monitoring and the door in are
    still answered, on the reserve, and nothing else is; and the caller on the box, through the console's unix
    socket, has connections of its own and is answered on every route."""
    from w2cplatform import console as wc
    sock = os.path.join(tempfile.mkdtemp(prefix="con-"), "c.sock")
    was = _env(CONSOLE_UNIX=sock, CONSOLE_TIMEOUT=30, CONSOLE_HEADER_TIMEOUT=30)
    Gate.forget_glass()
    box = Box()
    ctl, rec, m, srv, base = _console(box, Tokens({"admin": [("admin", None, ())]}))
    port, who, stop, others = srv.server_address[1], {}, threading.Event(), []
    srv.peer_of = lambda request, ca: (who.get(ca[1], str(ca[0])), False)
    glass = {"glass": {"who": "anna", "why": "the domain is down", "password": "open-sesame"}}
    get = lambda path, token="": (f"GET {path} HTTP/1.1\r\nHost: x\r\n" + (f"Authorization: Bearer {token}\r\n" if token else "")
                                  + "\r\n").encode()

    def flood():                                                      # 64 at a time, no token, half a request line each;
        socks = []                                                    # one refused or let go is opened again at once
        while not stop.is_set():
            alive = []
            for s in socks:
                try:
                    s.setblocking(False)
                    s.recv(4096)                                      # a 503, or the end: the console let this one go
                    s.close()
                except BlockingIOError:
                    alive.append(s)                                   # still held
                except OSError:
                    s.close()
            socks = alive
            try:
                while len(socks) < 64:
                    s = _as(who, "203.0.113.9", port)
                    s.sendall(b"GET /cam")
                    socks.append(s)
            except OSError:
                pass
            stop.wait(0.05)
        for s in socks:
            s.close()
    t = threading.Thread(target=flood, daemon=True)
    t.start()
    try:
        time.sleep(0.6)
        assert srv.bounds.by_addr[("common", "203.0.113.9")] == wc.CONSOLE_PER_ADDRESS     # its share, and not one more
        assert srv.refused > 40                                       # the rest: 503 on the spot, no thread
        # one address did not take the door: another one's monitoring and its ordinary requests are answered
        assert _ask(_as(who, "192.0.2.7", port), get("/metrics")).startswith(b"HTTP/1.0 200")
        assert _ask(_as(who, "192.0.2.7", port), get("/cameras", "admin")).startswith(b"HTTP/1.0 200")
        # the emergency entry from the box, through the unix socket — and then work under it, on any route
        code, _, headers = _unix(sock, "POST", "/session", glass)
        assert code == 200 and "w2c_glass=" in headers.get("Set-Cookie", ""), (code, headers)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        assert _unix(sock, "GET", "/cameras", headers={"Cookie": cookie})[0] == 200

        # …and with the common connections ALL taken — by many addresses, each inside its share
        for i in range(wc.CONSOLE_CONNECTIONS - wc.CONSOLE_PER_ADDRESS):
            s = _as(who, f"198.51.100.{i}", port)
            s.sendall(b"GET /cam")
            others.append(s)
        time.sleep(0.3)
        assert srv.bounds.used["common"] == wc.CONSOLE_CONNECTIONS
        assert _ask(_as(who, "192.0.2.7", port), get("/metrics")).startswith(b"HTTP/1.0 200")       # monitoring: the reserve
        busy = _ask(_as(who, "192.0.2.7", port), get("/cameras", "admin"))
        assert busy.startswith(b"HTTP/1.0 503") and b"/session" in busy                              # nothing else is
        body = json.dumps(glass).encode()
        door_in = _ask(_as(who, "192.0.2.8", port), b"POST /session HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                       + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        assert door_in.startswith(b"HTTP/1.0 200") and b"w2c_glass=" in door_in                      # the door in, from the network
        code, _, headers = _unix(sock, "POST", "/session", glass)                                    # the box: its own lane
        assert code == 200
        assert _unix(sock, "GET", "/cameras", headers={"Cookie": headers["Set-Cookie"].split(";", 1)[0]})[0] == 200
        assert _unix(sock, "GET", "/metrics")[0] == 200
        assert oct(os.stat(sock).st_mode & 0o777) == "0o660"          # who may open it is the file's mode
    finally:
        stop.set(); t.join(5)
        for s in others:
            s.close()
        srv.shutdown(); _restore(was); Gate.forget_glass()


def test_a_connection_nobody_knows_yet_has_seconds_for_its_headers_not_the_sockets_timeout():
    """The same finding: each of those connections held its slot for `CONSOLE_TIMEOUT` — thirty seconds of a thread for
    half a request line. The request line and headers have `CONSOLE_HEADER_TIMEOUT`, whatever the socket's timeout
    is; a connection of the reserve has `RESERVE_HEADERS`."""
    from w2cplatform import console as wc
    was = _env(CONSOLE_TIMEOUT=30, CONSOLE_HEADER_TIMEOUT=1, CONSOLE_CONNECTIONS=1)
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    port = srv.server_address[1]
    try:
        began = time.monotonic()
        reply, took = _raw(port, b"GET /cam", wait=10.0)              # half a request line, and then nothing
        assert reply == b"" and 0.8 < took < 3.0, (reply, took)       # let go at the headers' deadline, not at thirty seconds
        a = socket.create_connection(("127.0.0.1", port)); a.sendall(b"GET /cam")       # the one common connection, held…
        time.sleep(0.2)
        began = time.monotonic()
        reply, took = _raw(port, b"GET /met", wait=10.0)              # …so this one is the reserve's: shorter still
        assert reply == b"" and took < min(1.0, wc.RESERVE_HEADERS) + 1.5
        a.close()
    finally:
        srv.shutdown(); _restore(was)


# -- the sixth pass: rights before the body ----------------------------------------------------------------------------
def test_what_the_path_decides_is_asked_before_the_body_and_a_blobs_ceiling_is_a_blob_routes():
    """The review's sixth pass, major — a run: a token with no grant at all sent `PUT /<rows>/1/mask` with 32 MiB, eight
    at once, and the console held 331 MiB before it answered 403 (in М11 four such requests were its memory limit).
    The caller was proved before the body; what they MAY do was asked after it. Now everything the path alone decides
    is asked first — 403 with not a byte of the body read, for a stranger and for the administrator of another camera
    alike; a route whose unit is in the body is first asked for any grant at all; `MAX_BLOB` is the ceiling of a blob
    field of the spec and of nothing else; and `BLOBS_AT_ONCE` of them are read at a time."""
    from w2cplatform import console as wc
    box = Box()
    access = Tokens({"nobody": [], "one": [("admin", "1", ())], "two": [("admin", "2", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    port = srv.server_address[1]
    was = _env(BLOBS_AT_ONCE=2)
    wc._blobs.clear()
    held = []

    def head(method, path, token, n, more=""):
        return (f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {n}\r\nAuthorization: Bearer {token}\r\n"
                f"Idempotency-Key: k\r\n{more}\r\n").encode()
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/det/units", {"name": "1-motion", "cam": "1", "kind": "motion"}, token="admin")[0] == 201
        scenario = {"name": "lobby", "when": [{"sub": "vms", "kind": "motion", "unit": "1"}],
                    "then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", scenario, token="admin")[0] == 201
        blob = "/det/units/1-motion/mask"
        # 32 MiB declared and never sent: each of these is answered at once, the body not waited for
        for token, path, method, n, want in (
                ("nobody", blob, "PUT", wc.MAX_BLOB, b"403"),                    # no grant at all
                ("two", blob, "PUT", wc.MAX_BLOB, b"403"),                       # another camera's administrator
                ("one", "/det/units/1-motion/params", "PUT", wc.MAX_BLOB, b"404"),   # her unit, and not a blob field
                ("admin", "/det/units/9-motion/mask", "PUT", wc.MAX_BLOB, b"404"),   # no such unit
                ("one", blob, "PUT", wc.MAX_BLOB + 1, b"413"),                   # past a blob's own ceiling
                ("one", "/det/units/1-motion", "PUT", wc.MAX_BLOB, b"413"),      # a row is JSON: `MAX_BODY`, not a blob's
                ("nobody", "/marks", "POST", wc.MAX_BODY, b"403"),               # the unit is in the body: any grant, first
                ("two", "/auto/scenarios/lobby", "PUT", wc.MAX_BODY, b"403"),    # a scenario IS its cameras: as it is, first
                ("two", "/cameras/1", "DELETE", wc.MAX_BODY, b"403")):
            reply, took = _raw(port, head(method, path, token, n))
            assert reply.startswith(b"HTTP/1.0 " + want) and took < 2.0, (token, path, reply[:80], took)
        too_much = b"x" * (wc.SESSION_BODY + 1)                           # the door in is anybody's: a token, not a megabyte
        reply, _ = _raw(port, b"POST /session HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(too_much))
        assert reply.startswith(b"HTTP/1.0 413")
        # her own unit's mask, within the ceiling: taken, and the row names its digest
        mask = b"\x01" * 4096
        reply, _ = _raw(port, head("PUT", blob, "one", len(mask)) + mask)
        assert reply.startswith(b"HTTP/1.0 200") and mounts["det"].unit("1-motion")["mask"].startswith("sha256-")
        # two of them in flight — declared, and trickling — and the third is told to come back
        for _ in range(2):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(head("PUT", blob, "one", 100000) + b"\x02" * 10)
            held.append(s)
        time.sleep(0.3)
        reply, took = _raw(port, head("PUT", blob, "one", len(mask)) + mask)
        assert reply.startswith(b"HTTP/1.0 503") and b"Retry-After: 1" in reply and took < 2.0
        for s in held:
            s.close()
        held = []
        for _ in range(50):
            reply, _ = _raw(port, head("PUT", blob, "one", len(mask)) + mask)
            if reply.startswith(b"HTTP/1.0 200"):
                break
            time.sleep(0.1)
        assert reply.startswith(b"HTTP/1.0 200")
    finally:
        for s in held:
            s.close()
        srv.shutdown(); _restore(was); wc._blobs.clear()


# -- the sixth pass: the other doors -----------------------------------------------------------------------------------
def _holder(box, dev, **attrs):
    """A holder of `dev` with its playback door open, in a cluster that is open (the door asks nobody)."""
    from vms.config import SPEC
    from vms.controller import VmsController
    from vms.worker import FakeActuator, VmsWorker
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  archive_root=box.archive, device_factory=lambda k: dev)
    for k, v in attrs.items():
        setattr(w, k, v)
    w.heartbeat_once()
    for ch in dev.channels():
        con.create_camera({"source": f"driverpack://{dev.key}/ch/{ch}"})
    placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    return w, w.serve_playback("127.0.0.1", 0)


def test_the_holders_door_is_bounded_and_deadlined_like_the_consoles():
    """The review's sixth pass, major: the console's protections were the console's alone — 300 slow connections to the
    holder's door were 302 threads in the process holding every camera of its server. The door's server is the
    console's now (`door_server`): so many connections at once and so many to one address, the next 503 on the spot;
    the request line and headers have a deadline whole; and an unknown camera is an answer, not a dropped connection."""
    from vms.worker import FakeDevice
    was = _env(CONSOLE_HEADER_TIMEOUT=1)
    box = Box()
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (0.0, 100.0)}, index={"1": [(0.0, 100.0)]})
    w, door = _holder(box, dev, PLAYBACK_CONNECTIONS=4, PLAYBACK_PER_ADDRESS=2)
    port = door.server_address[1]
    held = []
    try:
        for _ in range(2):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(b"GET /play")                                    # half a request line: each holds a connection
            held.append(s)
        time.sleep(0.2)
        reply, took = _raw(port, b"GET /devices HTTP/1.1\r\nHost: x\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 503") and took < 1.0 and door.refused == 1   # this address has its two
        began = time.monotonic()
        held[0].settimeout(5)
        assert held[0].recv(1) == b"" and time.monotonic() - began < 3.0   # let go at the headers' deadline, not at thirty seconds
        for _ in range(30):
            reply, _ = _raw(port, b"GET /devices HTTP/1.1\r\nHost: x\r\n\r\n")
            if reply.startswith(b"HTTP/1.0 200"):
                break
            time.sleep(0.1)
        assert reply.startswith(b"HTTP/1.0 200") and b"acme/10.0.0.50" in reply
        assert _raw(port, b"GET /recordings/1?from=0&to=50 HTTP/1.1\r\nHost: x\r\n\r\n")[0].startswith(b"HTTP/1.0 200")
        assert _raw(port, b"GET /recordings/9 HTTP/1.1\r\nHost: x\r\n\r\n")[0].startswith(b"HTTP/1.0 404")
        assert _raw(port, b"GET /recordings/1?from=soon HTTP/1.1\r\nHost: x\r\n\r\n")[0].startswith(b"HTTP/1.0 400")
        assert _raw(port, b"GET /playback/1?from=soon HTTP/1.1\r\nHost: x\r\n\r\n")[0].startswith(b"HTTP/1.0 400")
    finally:
        for s in held:
            s.close()
        door.shutdown(); _restore(was)


def _slowly(port: int, path: str, rate: float, wait: float = 10.0) -> tuple[bytes, float]:
    """`GET path`, read no faster than `rate` bytes a second: `(everything that came, seconds)`."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
    s.connect(("127.0.0.1", port))
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
    data, began = b"", time.monotonic()
    s.settimeout(wait)
    try:
        while True:
            got = s.recv(8192)
            if not got:
                break
            data += got
            ahead = len(data) / rate - (time.monotonic() - began)
            if ahead > 0:
                time.sleep(ahead)
    except (socket.timeout, ConnectionResetError):
        pass
    s.close()
    return data, time.monotonic() - began


def test_a_viewer_who_reads_at_his_own_pace_gets_the_devices_footage_whole_and_holds_no_session_of_it():
    """The review's sixth pass, major: the door wrote a minute of footage in one `sendall`, and a socket's timeout is
    the whole of a `sendall` — a viewer reading faster than the camera recorded was cut after 36 s; and the device's
    session stayed open while he read, so two slow connections held both sessions of a recorder that has two. The
    footage goes out `STREAM_PIECE` at a time: a piece takes longer to read than the socket's timeout here, and the
    reply is whole, last chunk and all. The session is closed before a byte of the piece is sent: while he reads, the
    device has none in use and serves somebody else. One slower than `PLAYBACK_MIN_RATE` is cut, and sees it."""
    from vms.worker import FakeDevice
    box = Box()
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (0.0, 40.0)}, max_playbacks=1, bps=100_000)
    w, door = _holder(box, dev, PLAYBACK_PIECE=20.0, PLAYBACK_TIMEOUT=1.0)      # two pieces of 2 MB; a second a write
    port = door.server_address[1]
    seen, out = {}, {}

    def meanwhile():                                                  # while the viewer is still reading the first piece
        time.sleep(1.0)
        seen["in_use"] = dev.in_use()
        seen["other"] = _raw(port, b"GET /playback/1?from=0&to=1 HTTP/1.1\r\nHost: x\r\n\r\n")[0]
    try:
        t = threading.Thread(target=meanwhile); t.start()
        got, took = _slowly(port, "/playback/1?from=0&to=40", 1_000_000)
        t.join(10)
        assert b"Transfer-Encoding: chunked" in got and got.endswith(b"0\r\n\r\n"), got[-40:]   # whole, and said so
        assert len(got) > 40 * 100_000 and took > 3.0                 # every byte, at his pace: two seconds a piece
        assert seen["in_use"] == 0                                    # the device's one session is not his while he reads
        assert seen["other"].startswith(b"HTTP/1.1 200")              # …and serves another: it was 503, the device full
        assert not dev.open
        w.PLAYBACK_MIN_RATE, w.PLAYBACK_GRACE = 500_000, 0.5          # a floor a trickle falls under
        cut, took = _slowly(port, "/playback/1?from=0&to=40", 100_000)
        assert b" 200 " in cut.split(b"\r\n", 1)[0] and not cut.endswith(b"0\r\n\r\n") and len(cut) < len(got)
        assert took < 8.0 and not dev.open                            # let go, its session with it
    finally:
        door.shutdown()


def test_the_gateways_offer_is_bounded_and_its_door_is_the_consoles():
    """The sixth pass's sweep of every place a body is read: the gateway read `Content-Length` bytes of an offer,
    whatever that said, into the process every viewer's stream goes through. An offer past `MAX_OFFER` is 413 and
    is not read; the door is bounded and deadlined like the others."""
    from w2cplatform.console import ConsoleServer
    from tests.test_lesson8_live import _gateway
    box = Box()
    box.vars.put("vms/cameras/1", {"name": "gate", "labels": ""})
    g = _gateway(box, "g-1")
    srv = g.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    try:
        reply, took = _raw(port, b"POST /whep/1 HTTP/1.1\r\nHost: x\r\nContent-Length: 104857600\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 413") and took < 2.0
        assert _raw(port, b"POST /whep/1 HTTP/1.1\r\nHost: x\r\nContent-Length: lots\r\n\r\n")[0].startswith(b"HTTP/1.0 400")
        assert isinstance(srv, ConsoleServer) and srv.bounds.reserve == 0 and srv.bounds.box == 0   # a door between processes
    finally:
        srv.shutdown()

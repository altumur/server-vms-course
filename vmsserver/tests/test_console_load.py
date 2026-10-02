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
    socket, has connections of its own and is answered on every route. (Monitoring on its own lane, the address named
    in `CONSOLE_MONITORS`: the seventh pass, and the next test.)"""
    from w2cplatform import console as wc
    sock = os.path.join(tempfile.mkdtemp(prefix="con-"), "c.sock")
    was = _env(CONSOLE_UNIX=sock, CONSOLE_TIMEOUT=30, CONSOLE_HEADER_TIMEOUT=30, CONSOLE_MONITORS="192.0.2.7")
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
        # one address did not take the door: another one's monitoring and its ordinary requests are answered
        assert _ask(_as(who, "192.0.2.7", port), get("/metrics")).startswith(b"HTTP/1.0 200")
        assert _ask(_as(who, "192.0.2.7", port), get("/cameras", "admin")).startswith(b"HTTP/1.0 200")
        assert srv.bounds.by_addr[("common", "203.0.113.9")] == wc.CONSOLE_PER_ADDRESS     # its share, and not one more
        assert srv.refused > 40                                       # the rest: 503 on the spot, no thread
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
        assert _ask(_as(who, "192.0.2.7", port), get("/metrics")).startswith(b"HTTP/1.0 200")       # monitoring: its lane
        busy = _ask(_as(who, "192.0.2.7", port), get("/cameras", "admin"))
        assert busy.startswith(b"HTTP/1.0 503") and b"/metrics" in busy                              # nothing else is
        busy = _ask(_as(who, "192.0.2.9", port), get("/cameras", "admin"))
        assert busy.startswith(b"HTTP/1.0 503") and b"/session" in busy                              # …nor on the reserve
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


def _flood(who: dict, port: int, addrs: list, stop: threading.Event, each: int = 24) -> threading.Thread:
    """Every address of `addrs` keeps `each` connections open with half a request line, and opens again at once one
    that was refused or let go — what the seventh pass ran from four addresses."""
    def run():
        socks = []
        while not stop.is_set():
            alive = []
            for a, s in socks:
                try:
                    s.setblocking(False)
                    s.recv(4096)                                      # a 503, or the end: let go
                    s.close()
                except BlockingIOError:
                    alive.append((a, s))
                except OSError:
                    s.close()
            socks = alive
            for a in addrs:
                try:
                    while sum(1 for b, _ in socks if b == a) < each:
                        s = _as(who, a, port)
                        s.sendall(b"GET /cam")
                        socks.append((a, s))
                except OSError:
                    pass
            stop.wait(0.05)
        for _, s in socks:
            s.close()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def test_four_or_eight_addresses_flooding_keep_neither_an_honest_door_in_nor_a_listed_monitor_out():
    """The review's seventh pass, major — reproduced by a run: four addresses, each sending half a request line and
    reconnecting, held all 64 common connections (16 an address) and all 8 of the reserve (2 an address), and an honest
    address had not one 200 — `/metrics`, `/healthz`, `/session`, `/cameras`. "Addresses in their dozens" was four. Now
    an address holds `CONSOLE_PER_ADDRESS` (8), the reserve is taken only once the common connections are all gone,
    one to an address, and `/metrics` is answered past the common connections only to the monitors named in
    `CONSOLE_MONITORS`, on a lane of their own. Four addresses leave the door open to everybody; eight fill the common
    connections, and the door in is still answered on the reserve, and the listed monitor on its lane; sixteen fill
    the reserve as well — and the listed monitor is answered still. The numbers are the ones the lessons write down."""
    from w2cplatform import console as wc
    was = _env(CONSOLE_TIMEOUT=30, CONSOLE_HEADER_TIMEOUT=30, CONSOLE_MONITORS="192.0.2.100, 198.18.0.0/24")
    Gate.forget_glass()
    box = Box()
    ctl, rec, m, srv, base = _console(box, Tokens({"admin": [("admin", None, ())]}))
    port, who = srv.server_address[1], {}
    srv.peer_of = lambda request, ca: (who.get(ca[1], str(ca[0])), False)
    glass = json.dumps({"glass": {"who": "anna", "why": "the domain is down", "password": "open-sesame"}}).encode()
    door_in = (b"POST /session HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
               + f"Content-Length: {len(glass)}\r\n\r\n".encode() + glass)
    get = lambda path, token="": (f"GET {path} HTTP/1.1\r\nHost: x\r\n" + (f"Authorization: Bearer {token}\r\n" if token else "")
                                  + "\r\n").encode()

    def settle(want_common: int, want_reserve: int) -> None:
        for _ in range(100):
            if srv.bounds.used["common"] >= want_common and srv.bounds.used["reserve"] >= want_reserve:
                return
            time.sleep(0.05)
        raise AssertionError(dict(srv.bounds.used))
    try:
        for n, honest in ((4, "192.0.2.50"), (8, "192.0.2.51"), (16, "192.0.2.52")):
            stop = threading.Event()
            flooders = [f"203.0.113.{i}" for i in range(n)]
            t = _flood(who, port, flooders, stop)
            try:
                full = n * wc.CONSOLE_PER_ADDRESS >= wc.CONSOLE_CONNECTIONS
                settle(min(n * wc.CONSOLE_PER_ADDRESS, wc.CONSOLE_CONNECTIONS),
                       min(n, wc.CONSOLE_RESERVE) if full else 0)
                assert all(srv.bounds.by_addr.get(("common", a), 0) <= wc.CONSOLE_PER_ADDRESS for a in flooders)
                assert all(srv.bounds.by_addr.get(("reserve", a), 0) <= wc.RESERVE_PER_ADDRESS for a in flooders)
                session = _ask(_as(who, honest, port), door_in)
                cameras = _ask(_as(who, honest, port), get("/cameras", "admin"))
                metrics = _ask(_as(who, "198.18.0.7", port), get("/metrics"))                 # a listed network
                stranger = _ask(_as(who, honest, port), get("/metrics"))
                if n == 4:                                            # 32 of 64: the door is everybody's as usual
                    assert not full and srv.bounds.used["reserve"] == 0
                    assert session.startswith(b"HTTP/1.0 200") and cameras.startswith(b"HTTP/1.0 200")
                    assert stranger.startswith(b"HTTP/1.0 200")
                elif n == 8:                                          # the common connections gone: the door in, on the reserve
                    assert session.startswith(b"HTTP/1.0 200") and b"w2c_glass=" in session, session[:200]
                    assert cameras.startswith(b"HTTP/1.0 503") and stranger.startswith(b"HTTP/1.0 503")
                else:                                                 # the reserve gone too: only the listed monitor, over TCP
                    assert srv.bounds.used["reserve"] == wc.CONSOLE_RESERVE
                    assert session.startswith(b"HTTP/1.0 503") and cameras.startswith(b"HTTP/1.0 503")
                assert metrics.startswith(b"HTTP/1.0 200") and b"vms_" in metrics, metrics[:200]   # the monitor: always
                listed = _ask(_as(who, "192.0.2.100", port), get("/healthz"))                 # a listed address
                assert listed.startswith(b"HTTP/1.0 200"), listed[:80]
            finally:
                stop.set(); t.join(5)
            for _ in range(100):                                      # the flood's connections end before the next round
                if srv.bounds.used["common"] == 0 and srv.bounds.used["reserve"] == 0:
                    break
                time.sleep(0.05)
    finally:
        srv.shutdown(); _restore(was); Gate.forget_glass()


def test_a_refusal_is_read_by_the_client_not_reset_under_it():
    """The review's seventh pass, minor: the 503 was written and the socket closed with the client's request unread in
    it — and a socket closed with unread bytes is reset: on macOS the client's read was `ECONNRESET`, not the 503 and
    its `Retry-After` (the domain's door test failed six runs of six). The refused socket is finished (`SHUT_WR`) and
    what the client still sends is read and dropped until it closes or a second passes (`linger`); a handler's own
    refusal with a body unread — a 413 — is finished the same way."""
    from w2cplatform import console as wc
    was = _env(CONSOLE_CONNECTIONS=2, CONSOLE_PER_ADDRESS=2, CONSOLE_RESERVE=0, CONSOLE_HEADER_TIMEOUT=30)
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    port = srv.server_address[1]
    held = []
    body = b"x" * (256 << 10)                                         # more than the refusal reads: it stays unread
    try:
        for _ in range(2):
            s = socket.create_connection(("127.0.0.1", port)); s.sendall(b"GET /cam"); held.append(s)
        time.sleep(0.2)
        for _ in range(10):
            s = socket.create_connection(("127.0.0.1", port))
            s.settimeout(5)
            try:
                s.sendall(b"POST /marks HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
            except OSError:
                pass                                                  # the door may finish before all of it went
            out = b""
            while True:
                got = s.recv(65536)                                   # ECONNRESET here was the finding
                if not got:
                    break
                out += got
            s.close()
            assert out.startswith(b"HTTP/1.0 503") and b"Retry-After: 1" in out, out[:80]
        for s in held:
            s.close()
        held = []
        time.sleep(0.3)
        huge = wc.MAX_BODY + 1
        s = socket.create_connection(("127.0.0.1", port)); s.settimeout(5)
        s.sendall(b"POST /marks HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % huge + body)
        out = b""
        while True:
            got = s.recv(65536)
            if not got:
                break
            out += got
        s.close()
        assert out.startswith(b"HTTP/1.0 413"), out[:80]
    finally:
        for s in held:
            s.close()
        srv.shutdown(); _restore(was)


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
    getattr(wc, "_blobs", []).clear()                               # the bound is read when it is first needed
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
        srv.shutdown(); _restore(was); getattr(wc, "_blobs", []).clear()


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


def _released(door, dev, wait: float = 15.0) -> threading.Event:
    """Set once the next connection `door` takes is given back — its handler done, its slot free. The event's `took`
    is the seconds from this call, `dev_open` the sessions `dev` still had open at that moment."""
    used = door.bounds.used
    settle = time.monotonic() + 2.0                                   # the last connection's slot, given back after its EOF
    while used["common"] and time.monotonic() < settle:
        time.sleep(0.005)
    began, done = time.monotonic(), threading.Event()
    done.took = done.dev_open = None

    def watch():
        deadline = began + wait
        while not used["common"] and time.monotonic() < deadline:
            time.sleep(0.005)
        while used["common"] and time.monotonic() < deadline:
            time.sleep(0.005)
        if not used["common"]:
            done.took, done.dev_open = time.monotonic() - began, len(dev.open)
            done.set()
    threading.Thread(target=watch, daemon=True).start()
    return done


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
        # When the DOOR let go is asked of the door — its connection slot back, the device's session closed — not of
        # the client's clock. The client still reads for seconds after the cut: what the door wrote before it is in
        # the kernel's buffers (the sender's grows on its own on macOS, 0.7–0.8 MB here), and at 100 kB/s that is
        # 7.6–8.2 s whatever the door does — a bound of 8 s on it failed whenever the buffer came out larger, under
        # load or after the first read; the door let go at 1.5 s every time (the reviewer's run, two agents' runs).
        # (What cuts this trickle here is the socket's one-second timeout on a write of `STREAM_PIECE`, before the floor.)
        let_go = _released(door, dev)
        cut, _ = _slowly(port, "/playback/1?from=0&to=40", 100_000)
        assert b" 200 " in cut.split(b"\r\n", 1)[0] and not cut.endswith(b"0\r\n\r\n") and len(cut) < len(got)
        assert let_go.wait(5.0) and let_go.took < 4.0, let_go.took    # let go: a second's write it did not take, past the grace
        assert let_go.dev_open == 0 and not dev.open                  # …its session with it
    finally:
        door.shutdown()


def test_the_holders_door_holds_a_budget_of_footage_not_a_minute_a_connection_and_two_connections_a_signature():
    """The review's seventh pass, major — a run: a viewer with `view` on one camera opened eight connections on one
    signed address to a camera of 8 Mbit/s, and the holder — the process holding every camera of its server — went from
    45 to 503 MB: a piece was sixty seconds, whatever bytes that was, one per connection. A piece is sized in bytes now
    (`PLAYBACK_PIECE_BYTES`, from the rate the last one came at), the pieces the door holds across its connections are
    at most `PLAYBACK_BUDGET` — past it the next first piece waits, then is 503 — and one signed address holds
    `PLAYBACK_PER_SIGNATURE` connections."""
    from vms.worker import FakeDevice
    box = Box()
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (0.0, 3600.0)}, max_playbacks=64, bps=1_000_000)
    piece, budget = 2 << 20, 8 << 20                              # two seconds of this camera a piece; four pieces
    w, door = _holder(box, dev, PLAYBACK_PIECE_BYTES=piece, PLAYBACK_BUDGET=budget, PLAYBACK_FIRST=0.25,
                      PLAYBACK_BUDGET_WAIT=0.5, PLAYBACK_CONNECTIONS=32, PLAYBACK_PER_ADDRESS=16)
    port = door.server_address[1]
    idle, peak, stop = [], [0], threading.Event()

    def watch():
        while not stop.is_set():
            peak[0] = max(peak[0], w.playback_budget().used)
            time.sleep(0.005)

    def nobody_reads(sig: str) -> socket.socket:
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        s.connect(("127.0.0.1", port))
        s.sendall(f"GET /playback/1?from=0&to=3600&sig={sig} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        return s
    t = threading.Thread(target=watch, daemon=True)
    t.start()
    try:
        idle += [nobody_reads("one"), nobody_reads("one")]           # one viewer's address, twice: its two
        time.sleep(0.5)
        third, _ = _raw(port, b"GET /playback/1?from=0&to=3600&sig=one HTTP/1.1\r\nHost: x\r\n\r\n")
        assert third.startswith(b"HTTP/1.0 503") and b"at once already" in third, third[:120]
        idle += [nobody_reads(f"v{i}") for i in range(6)]             # six more viewers who read nothing
        time.sleep(1.5)
        refused, _ = _raw(port, b"GET /playback/1?from=0&to=3600&sig=late HTTP/1.1\r\nHost: x\r\n\r\n")
        assert refused.startswith(b"HTTP/1.0 503") and b"bytes of footage at once" in refused, refused[:160]
        assert peak[0] <= budget + piece, peak[0]                     # the budget, and one piece over it at most
        sizes = [int((b - a) * dev.bps) for _, a, b in dev.fetched]
        assert sizes and max(sizes[1:] or sizes) <= 2 * piece, max(sizes)   # pieces of bytes, not of sixty seconds
    finally:
        stop.set(); t.join(2)
        for s in idle:
            s.close()
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


def test_the_resources_door_is_bounded_and_a_mirrored_bucket_is_never_held_whole():
    """The same sweep, at the resource: `PUT /mirror/…` read `Content-Length` bytes into memory, whatever that said,
    at a door that asks nobody. Past `MIRROR_MAX` it is 413 and nothing is read; within it the copy goes to the file
    a piece at a time, and a body that ends early leaves no copy at all. The door is the bounded one, and the
    requests it holds (`WAITERS_MAX`) with the queries it answers at once fit inside one address's share."""
    from w2cplatform import longpoll, resource as wr
    from w2cplatform.console import ConsoleServer
    box = Box()
    res = wr.Resource(box.archive, "srv-1", "http://127.0.0.1:0", box.vars, box.objects, wall=box.wall)
    srv = wr.serve(res, "127.0.0.1", 0)
    port = srv.server_address[1]
    path = "/mirror/srv-2/vms/7/e1/1757499600.events.jsonl"
    copy = os.path.join(box.archive, wr.MIRROR_DIR, "srv-2", "vms", "7", "e1", "1757499600.events.jsonl")
    put = lambda n, body=b"": f"PUT {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {n}\r\n\r\n".encode() + body
    try:
        assert isinstance(srv, ConsoleServer)
        assert longpoll.WAITERS_MAX + wr.EVENTS_INFLIGHT < srv.bounds.per_address <= srv.bounds.limit
        reply, took = _raw(port, put(wr.MIRROR_MAX + 1))
        assert reply.startswith(b"HTTP/1.0 413") and took < 2.0 and not os.path.exists(copy)
        lines = b'{"t": 1, "kind": "motion"}\n' * 5000                # more than one piece of the copy
        assert _raw(port, put(len(lines), lines))[0].startswith(b"HTTP/1.0 204")
        assert open(copy, "rb").read() == lines
        s = socket.create_connection(("127.0.0.1", port))
        s.sendall(put(len(lines) * 2, lines)); s.shutdown(socket.SHUT_WR)   # half of what it declared, and gone
        s.settimeout(5)
        assert s.recv(100).startswith(b"HTTP/1.0 400")
        s.close()
        assert open(copy, "rb").read() == lines and not os.path.exists(copy + ".tmp")   # the copy that was there stands; no half of one
    finally:
        srv.shutdown()


def test_the_resources_door_gives_a_mirrored_body_a_deadline_whole_and_a_subsystems_write_too():
    """The review's seventh pass, major — a run: past the headers a request was its handler's, and `PUT /mirror` read its
    body under nothing but the socket's timeout on each read: 32 connections declaring 60 MB and sending a byte every
    twenty seconds held an address's share for ever, and two addresses the whole door. The body has the door's
    `timeout` and a second for every `BODY_RATE` bytes (`body_deadline`); one that does not arrive in time is 408 and
    leaves no copy. A subsystem's own write (`extra_put`) reads under the same deadline."""
    from w2cplatform import resource as wr
    box = Box()
    res = wr.Resource(box.archive, "srv-1", "http://127.0.0.1:0", box.vars, box.objects, wall=box.wall)
    was, wr.DOOR_TIMEOUT = getattr(wr, "DOOR_TIMEOUT", 30.0), 1.0
    seen = {}

    def extra_put(path, headers, rfile):
        try:
            seen["got"] = rfile.read(int(headers.get("Content-Length", 0)))
        except TimeoutError:
            seen["late"] = True
            raise
        return 204, b""
    srv = wr.serve(res, "127.0.0.1", 0, extra_put=extra_put)
    wr.DOOR_TIMEOUT = was
    port = srv.server_address[1]
    path = "/mirror/srv-2/vms/7/e1/1757499600.events.jsonl"
    copy = os.path.join(box.archive, wr.MIRROR_DIR, "srv-2", "vms", "7", "e1", "1757499600.events.jsonl")

    def trickle(target: str, n: int) -> tuple[bytes, float]:
        s = socket.create_connection(("127.0.0.1", port))
        s.sendall(f"PUT {target} HTTP/1.1\r\nHost: x\r\nContent-Length: {n}\r\n\r\n".encode())
        began, out = time.monotonic(), b""
        s.settimeout(0.5)
        try:
            while time.monotonic() - began < 15:
                try:
                    s.sendall(b"x")                                   # a byte, inside the socket's timeout of each read
                except OSError:
                    break
                try:
                    got = s.recv(4096)
                    if not got:
                        break
                    out += got
                    break
                except socket.timeout:
                    pass
        finally:
            s.close()
        return out, time.monotonic() - began
    try:
        reply, took = trickle(path, 60000)                            # 1 s and 60000 / BODY_RATE ≈ 0.9 s: under 2 s
        assert reply.startswith(b"HTTP/1.0 408") and took < 4.0, (reply[:40], took)
        assert not os.path.exists(copy) and not os.path.exists(copy + ".tmp")
        reply, took = trickle("/theirs/1", 60000)
        assert reply.startswith(b"HTTP/1.0 408") and took < 4.0 and seen.get("late"), (reply[:40], took)
        assert _raw(port, b"PUT /theirs/2 HTTP/1.1\r\nHost: x\r\nContent-Length: 3\r\n\r\nabc")[0].startswith(b"HTTP/1.0 204")
        assert seen["got"] == b"abc"                                   # a body in time: as before
    finally:
        srv.shutdown()


def test_a_bucket_goes_out_in_pieces_to_a_slow_reader_and_is_never_held_whole():
    """The review's seventh pass, major — a run: `GET /events/<bucket>` was `f.read()` into one reply; eight readers of a
    60 MB bucket that did not read held 400 MB in the resource, and a peer slower than 2 MB/s never got one — the
    socket's timeout is the whole of a `sendall`, and `restore` of that bucket failed on every retry. The bucket goes
    out `STREAM_PIECE` at a time with its length said: a reader slower than the socket's timeout allows for the whole
    gets every byte, and readers that read nothing hold pieces, not buckets."""
    import tracemalloc
    from w2cplatform import resource as wr
    box = Box()
    res = wr.Resource(box.archive, "srv-1", "http://127.0.0.1:0", box.vars, box.objects, wall=box.wall)
    rel = "vms/7/e1/1757499600.events.jsonl"
    os.makedirs(os.path.join(box.archive, os.path.dirname(rel)), exist_ok=True)
    line = b'{"t": 1, "kind": "motion", "pad": "' + b"p" * 200 + b'"}\n'
    with open(os.path.join(box.archive, rel), "wb") as f:
        f.write(line * (4 * (1 << 20) // len(line)))                 # four megabytes of one bucket
    size = os.path.getsize(os.path.join(box.archive, rel))
    was, wr.DOOR_TIMEOUT = getattr(wr, "DOOR_TIMEOUT", 30.0), 1.0                      # a second a write: the whole would need four
    srv = wr.serve(res, "127.0.0.1", 0)
    wr.DOOR_TIMEOUT = was
    port = srv.server_address[1]
    idle = []
    try:
        got, took = _slowly(port, f"/events/{rel}", 1_000_000, wait=20.0)
        head, _, body = got.partition(b"\r\n\r\n")
        assert b" 200 " in head.split(b"\r\n", 1)[0] and f"Content-Length: {size}".encode() in head
        assert len(body) == size and took > 2.0, (len(body), size, took)   # every byte, at its pace
        tracemalloc.start()
        for _ in range(6):                                            # six readers that read nothing
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.connect(("127.0.0.1", port))
            s.sendall(f"GET /events/{rel} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
            idle.append(s)
        time.sleep(0.5)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 6 * size // 4, peak                             # pieces in flight, not six buckets
    finally:
        for s in idle:
            s.close()
        srv.shutdown()


def test_the_mirror_sends_and_takes_back_a_bucket_in_pieces_never_whole():
    """The resource's own client of the mirror held a bucket whole on both sides: `mirror` sent `f.read()`, and
    `restore` wrote what `PeerClient.get` had read whole (the review's seventh pass, beside "the resource sends a bucket
    whole"; the door's side was closed in the same pass). Two real resources over HTTP, a bucket of 16 MB: the copy goes
    over and comes back byte for byte, and the most Python held at once during each is a few pieces, not the bucket."""
    import shutil
    import tracemalloc
    from w2cplatform import resource as wr
    from w2cplatform.events import EventLog
    box = Box(); t = box.wall() - 7200
    roots = {s: tempfile.mkdtemp(prefix=f"res-{s}-") for s in ("srv-a", "srv-b")}
    res, srvs = {}, []
    for s, root in roots.items():
        r = wr.Resource(root, s, "", box.vars, box.objects, wall=box.wall)
        srv = wr.serve(r, "127.0.0.1", 0); srvs.append(srv)
        r.url = f"http://127.0.0.1:{srv.server_address[1]}"
        res[s] = r
    try:
        EventLog(roots["srv-a"], "thing", "x", 1).append(t + 5, "tick")                       # a closed bucket…
        bucket = next(os.path.join(d, f) for d, _, fs in os.walk(os.path.join(roots["srv-a"], "thing")) for f in fs)
        with open(bucket, "ab") as f:                                                       # …of a storm
            for _ in range(16):
                f.write(b'{"t": 1, "kind": "tick"}' + b" " * ((1 << 20) - 25) + b"\n")
        whole = open(bucket, "rb").read()
        for r in res.values():
            r.heartbeat()
        box.vars.put(wr.MIRROR_KEY, {"enabled": "true", "copies": "1"})
        tracemalloc.start()
        try:
            assert res["srv-a"].mirror()["mirrored"] == 1
            sent_peak = tracemalloc.get_traced_memory()[1]
            res["srv-b"].heartbeat()
            shutil.rmtree(roots["srv-a"]); os.makedirs(roots["srv-a"])                        # back with a replaced disk
            tracemalloc.reset_peak()
            assert res["srv-a"].restore()["pulled"] == 1
            took_peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert open(bucket, "rb").read() == whole
        assert sent_peak < 4 << 20 and took_peak < 4 << 20, (sent_peak, took_peak)        # pieces, never the 16 MB
    finally:
        for srv in srvs:
            srv.shutdown()

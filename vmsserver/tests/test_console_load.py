"""The console under load (the review's fifth pass): what a request may cost it before anybody knows who sent it.

    the body after the gate     no token is 401 before a byte of the body is read; a body past the ceiling is 413
    a deadline per request      a request's line and headers arrive whole within `CONSOLE_TIMEOUT`, or it is closed
    a bound on connections      past `CONSOLE_CONNECTIONS` the next is answered 503 at once, not given a thread
"""
import os
import socket
import time

from tests.conftest import Box
from tests.test_console_gate import Tokens, _call, _console


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
    when a slot frees, the console answers again."""
    was = _env(CONSOLE_CONNECTIONS=3, CONSOLE_TIMEOUT=30)
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

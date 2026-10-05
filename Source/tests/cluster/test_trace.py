"""The trace the lessons print is what the real handle sends — checked, not asserted.

The same operations go once through `ConfigstoreVariables` over a real unix socket, to a tiny daemon stub that
records what arrives and answers with the daemon's own API over its own state machine (`storemachine.answer`), and
once through the stand's door (`storemachine.local_transport`, recorded by `TraceLog.transport`). The requests must
be the same — method, route, query, body — save the operation id, which is a fresh uuid per call on both sides and
which the trace leaves out of what it prints.
"""
import json
import os
import re
import socketserver
import tempfile
import threading
from http.server import BaseHTTPRequestHandler

from w2cplatform.cluster.variables import Conflict, Forbidden
from tests.cluster.trace import TraceLog, body_shown
from w2cplatform.configstorevars import ConfigstoreVariables
from w2cplatform.storemachine import Rights, StoreMachine, answer, local_transport

RIGHTS = Rights.parse({"roles": {"console": {"group": "vms-console", "read": ["vms/*"], "write": ["vms/cameras/*"],
                                             "delete": ["vms/cameras/*"]}}})


class _Daemon:
    """Just enough of a configstore daemon to answer the handle on a unix socket: the API over one machine, as
    `console`. What arrived is kept in `seen`."""

    def __init__(self):
        self.machine, self.seen, self.lock = StoreMachine(1000), [], threading.Lock()
        self.dir = tempfile.mkdtemp(prefix="cs-")             # the run's root is short: a socket's path is at most 104 bytes on macOS
        self.path = os.path.join(self.dir, "console.sock")
        me = self

        class H(BaseHTTPRequestHandler):
            def address_string(self):
                return "unix"

            def log_message(self, *a):
                pass

            def _serve(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                me.seen.append((self.command, self.path, json.loads(raw) if raw else None))
                code, body = answer(self.command, self.path, raw, "console", RIGHTS, me.submit)
                out = json.dumps(body).encode()
                self.send_response(code); self.send_header("Content-Length", str(len(out))); self.end_headers()
                self.wfile.write(out)
            do_GET = do_POST = _serve

        self.srv = socketserver.ThreadingUnixStreamServer(self.path, H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def submit(self, cmd):
        with self.lock:
            return self.machine.apply(cmd, self.machine.applied if cmd["op"] in ("get", "list") else None)

    def stop(self):
        self.srv.shutdown(); self.srv.server_close()
        os.unlink(self.path); os.rmdir(self.dir)


def _script(v):
    v.put("vms/cameras/7", {"name": "Ворота", "labels": "vlan:cctv-a"}, cas=0)
    items, idx = v.get("vms/cameras/7")
    v.put("vms/cameras/7", {**items, "name": "Северные ворота"}, cas=idx)
    try:
        v.put("vms/cameras/7", {"name": "stale"}, cas=idx)           # the second writer, with the old version
    except Conflict:
        pass
    v.list("vms/cameras/")
    v.get("vms/cameras/8")
    try:
        v.put("vms/epoch/7", {"epoch": "1"})                          # not the console's
    except Forbidden:
        pass
    v.delete("vms/cameras/7", cas=v.get("vms/cameras/7")[1])


def _without_id(body):
    return None if body is None else {k: v for k, v in body.items() if k != "id"}


def test_the_trace_is_what_the_handle_sends_over_the_socket():
    d = _Daemon()
    try:
        _script(ConfigstoreVariables(d.path))
    finally:
        d.stop()
    log, stand = TraceLog(), StoreMachine(1000)

    def submit(cmd):
        return stand.apply(cmd, stand.applied if cmd["op"] in ("get", "list") else None)
    path = "/run/configstore/console.sock"
    _script(ConfigstoreVariables(path, transport=log.transport("console on srv-a", path,
                                                               local_transport(submit, RIGHTS, "console"))))
    real = [(m, p, _without_id(b)) for m, p, b in d.seen]
    traced = [(c.method, c.target, _without_id(c.body)) for c in log.calls]
    assert real == traced
    assert [c.status for c in log.calls] == [200, 200, 200, 409, 200, 200, 403, 200, 200]
    ids = [b["id"] for m, p, b in d.seen if b is not None]
    assert len(ids) == 5 and all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids) and len(set(ids)) == 5
    assert [c.answer for c in log.calls][:2] == [{"index": 1001}, {"items": {"name": "Ворота", "labels": "vlan:cctv-a"},
                                                                    "index": 1001}]


def test_the_printed_trace_leaves_out_the_id_and_the_percent_signs_and_says_what_a_write_asks_first():
    """What a lesson quotes: the route with its query readable, a write's body with `op`, `key` and `cas` first and no
    operation id, the answer in the product's words. The request itself is unchanged — only its printing is."""
    log, m = TraceLog(), StoreMachine(1000)
    path = "/run/configstore/console.sock"
    v = ConfigstoreVariables(path, transport=log.transport("console on srv-a", path,
                                                           local_transport(m.apply, RIGHTS, "console")))
    v.put("vms/cameras/1", {"name": "gate"}, cas=0)
    v.get("vms/cameras/1")
    text = log.render()
    assert "# console on srv-a → /run/configstore/console.sock" in text
    assert 'POST /v1/write {"op": "put", "key": "vms/cameras/1", "cas": "", "items": {"name": "gate"}}' in text
    assert "GET /v1/get?key=vms/cameras/1\n" in text and "%2F" not in text and '"id"' not in text
    assert '→ 200 {"index": 1001}' in text
    assert log.calls[0].target == "/v1/write" and "id" in log.calls[0].body          # sent, not printed
    assert list(body_shown({"items": {}, "id": "x", "cas": None, "key": "k", "op": "put"})) == ["op", "key", "cas", "items"]

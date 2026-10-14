"""C5: one generic unitless worker door, under a person's rights, for two subsystems."""
import io
import json
from email.message import Message

from tests.conftest import Box, Served
from w2cplatform.access import Denied
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import SpecController, SubsystemSpec


def raw_spec(name="testsub"):
    return {"name": name, "unit": {"rows": "items", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "seen": {"type": "string"}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}},
        "tables": ["entries"], "door": {"pass": ["entries"]}}


def refused(raw):
    try:
        SubsystemSpec.from_dict(raw)
    except ValueError:
        return
    raise AssertionError("invalid spec loaded")


class Access:
    def who(self, token):
        if token not in ("viewer", "admin"):
            raise Denied(401, "unknown person")
        return {"sub": token}

    def may(self, payload, capability, unit, labels):
        return payload["sub"] == "admin" or capability == "view"


class Client:
    def __init__(self):
        self.calls = []
        self.reply = (201, b'{"ok":true}', {"Content-Type": "application/json"})

    def request(self, method, url, body, headers, *, role):
        self.calls.append((method, url, body, headers, role))
        return self.reply


class Handler:
    def __init__(self, path="/entries", body=b"", token="admin", **headers):
        self.path, self.rfile, self.wfile = path, io.BytesIO(body), io.BytesIO()
        self.headers = Message()
        for k, v in {"Content-Length": str(len(body)), "Authorization": "Bearer " + token, **headers}.items():
            self.headers[k] = v
        self.status = None
        self.close_connection = False
        self.reply_headers = {}

    def _send(self, status, body):
        self.status = status
        self.wfile.write(json.dumps(body).encode())

    def send_response(self, status): self.status = status
    def send_header(self, name, value): self.reply_headers[name] = value
    def end_headers(self): pass


def site(name="testsub", *, client=True):
    box = Box()
    spec = SubsystemSpec.from_dict(raw_spec(name))
    door = Client() if client else None
    con = SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall), worker_client=door)
    con.gate.impl = Access()
    return box, con, door


def heartbeat(box, sub, name, *, ts=None, url="http://worker:9000"):
    hb = Heartbeat(name, box.wall() if ts is None else ts, extra={"url": url})
    raw = hb.to_bytes()
    box.objects.put(sub + "/heartbeats/" + name, raw)
    return Heartbeat.from_bytes(raw)


def dispatch(con, h, method="GET", path="/entries"):
    con.dispatch(h, method, path, {})
    return h.status


def test_pass_is_closed_distinct_and_cannot_shadow_rows_or_console_crud():
    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        assert SubsystemSpec.from_dict(raw).door_pass == ("entries",)
        for door in ({}, {"pass": []}, {"pass": None}, {"pass": "entries"}, {"pass": [5]},
                     {"pass": ["entries", "entries"]}, {"pass": ["a/b"]}, {"pass": ["Entries"]},
                     {"pass": ["entries\n"]}, {"pass": ["entries"], "unknown": 1},
                     {"routes": ["entries"], "pass": ["entries"]}, {"pass": ["items"]},
                     {"pass": ["where"]}, {"pass": ["policy"]}, {"pass": ["domain"]}):
            refused({**raw, "door": door})
        raw["tables"] = {"entries": {"key": "name", "fields": {"name": {"type": "string"}}}}
        refused(raw)
        raw = raw_spec(name)
        raw["door"] = {"routes": ["read"], "pass": ["entries"]}
        spec = SubsystemSpec.from_dict(raw)
        assert spec.door_routes == ("read",) and spec.door_pass == ("entries",)


def test_two_subsystems_select_the_smallest_live_worker_with_a_door_and_preserve_request():
    for name in ("testsub", "testsub2"):
        box, con, client = site(name)
        old = heartbeat(box, name, "a-old", ts=box.wall() - 46)
        con.ctl.eyes.age(name + "/heartbeats/a-old", old.token)
        box.wall.advance(46)
        for worker, kwargs in (("b-no-door", {"url": ""}),
                               ("z-live", {"url": "http://last:9000"}), ("c-live", {"url": "http://first:9000"})):
            heartbeat(box, name, worker, **kwargs)
        heartbeat(box, "other", "a-other")
        box.objects.put(name + "/heartbeats/aa-broken", b'{"ts":true}')
        body = b'{"disabled":true}'
        h = Handler("/" + name + "/entries/alice/password?mode=one&mode=two", body,
                    **{"Content-Type": "application/custom+json", "Idempotency-Key": "one-edit",
                       "X-Operator": "the-person", "X-User": "forged", "X-Agent-Signature": "untrusted"})
        # A person's request has no member edit signature; it must not be handed through as a different identity.
        del h.headers["X-Agent-Signature"]
        assert dispatch(con, h, "POST", "/entries/alice/password") == 201
        assert client.calls == [("POST", "http://first:9000/" + name + "/entries/alice/password?mode=one&mode=two",
            body, {"Authorization": "Bearer admin", "Content-Type": "application/custom+json",
                   "Idempotency-Key": "one-edit", "X-Operator": "console"}, name + "worker")]
        assert h.wfile.getvalue() == b'{"ok":true}'
        client.reply = (200, b'<script>untrusted()</script>', {"Content-Type": "text/html"})
        h = Handler()
        assert dispatch(con, h) == 200
        assert h.reply_headers["Content-Type"] == "application/json"
        assert h.wfile.getvalue() == b'<script>untrusted()</script>'


def test_worker_selection_uses_observed_change_with_skew_and_stops_after_silence():
    box, con, client = site()
    heartbeat(box, con.spec.name, "worker", ts=box.wall() - 3600)
    assert dispatch(con, Handler()) == 201
    box.wall.advance(20)
    heartbeat(box, con.spec.name, "worker", ts=box.wall() - 3600)
    assert dispatch(con, Handler()) == 201
    box.wall.advance(46)
    assert dispatch(con, Handler()) == 503
    assert len(client.calls) == 2


def test_pass_proves_view_or_admin_before_reading_body_and_does_not_use_route_cap_overrides():
    box, con, client = site()
    heartbeat(box, con.spec.name, "worker")
    con.spec.route_caps = {"view": ("entries",)}
    class Unread:
        def read(self, n): raise AssertionError("unauthorized body read")
    for token, method, wanted in (("unknown", "GET", 401), ("viewer", "PUT", 403),
                                   ("viewer", "DELETE", 403), ("viewer", "POST", 403)):
        h = Handler(token=token)
        h.rfile = Unread()
        assert dispatch(con, h, method) == wanted
        assert h.close_connection
    assert not client.calls
    assert dispatch(con, Handler(token="viewer")) == 201


def test_pass_has_explicit_missing_client_no_worker_and_failed_worker_statuses():
    box, con, client = site(client=False)
    assert dispatch(con, Handler()) == 503
    con.worker_client = Client()
    assert dispatch(con, Handler()) == 503
    heartbeat(box, con.spec.name, "worker")
    def failed(*args, **kwargs): raise OSError("gone")
    con.worker_client.request = failed
    assert dispatch(con, Handler()) == 502


def test_console_uses_the_runtime_role_client_without_an_injected_transport():
    import os
    from unittest.mock import patch
    from tests.test_role_client import kits, server
    from w2cplatform.tls import Bundle, RoleClient
    with kits() as ca, server(Bundle(ca.root, "testsubworker")) as (url, calls):
        with patch.dict(os.environ, {"W2C_TLS_DIR": ca.root, "W2C_ROLE": "console"}):
            box = Box()
            spec = SubsystemSpec.from_dict(raw_spec())
            con = SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall))
        assert isinstance(con.worker_client, RoleClient)
        con.gate.impl = Access()
        heartbeat(box, spec.name, "worker", url=url)
        h = Handler("/entries?from=page", b'{"name":"alice"}', **{"Idempotency-Key": "create",
                                                                      "X-Operator": "forged"})
        assert dispatch(con, h, "POST") == 202
        assert calls[0][:3] == ("POST", "/testsub/entries?from=page", b'{"name":"alice"}')
        assert calls[0][3]["Authorization"] == "Bearer admin"
        assert calls[0][3]["X-Operator"] == "console"
        # A transport identity mismatch reaches no worker handler and is a gateway failure, not a fake response.
        con.worker_client.required_role = "other"
        assert dispatch(con, Handler()) == 502
        assert len(calls) == 1


def test_pass_bounds_body_and_reply_and_cannot_be_reached_by_an_unknown_route():
    box, con, client = site()
    heartbeat(box, con.spec.name, "worker")
    h = Handler(body=b"x" * ((1 << 20) + 1))
    assert dispatch(con, h, "POST") == 413
    assert not client.calls
    # Exactly the contract's one MiB is accepted; it does not take the console's larger blob limit.
    body = b"x" * (1 << 20)
    assert dispatch(con, Handler(body=body), "POST") == 201
    assert client.calls[-1][2] == body
    for path in ("/entries-other", "/other/entries", "/entry"):
        assert dispatch(con, Handler(path), path=path) == 404
    assert len(client.calls) == 1
    client.reply = (200, b"x" * ((1 << 20) + 1), {})
    assert dispatch(con, Handler()) == 502


def test_named_root_and_mounted_subsystems_use_their_own_worker():
    box, first, client1 = site("testsub")
    _, second, client2 = site("testsub2")
    heartbeat(box, "testsub", "worker")
    heartbeat(second.ctl, "testsub2", "worker")
    with Served(Mount(first, {"testsub2": second})) as call:
        for path in ("/entries", "/testsub/entries", "/testsub2/entries"):
            assert call("GET", path, headers={"Authorization": "Bearer viewer"})[0] == 201
    assert [call[1] for call in client1.calls] == ["http://worker:9000/testsub/entries"] * 2
    assert [call[1] for call in client2.calls] == ["http://worker:9000/testsub2/entries"]


def test_member_console_forwards_the_three_person_routes_to_the_known_holder():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    calls = []
    class Holder(BaseHTTPRequestHandler):
        def answer(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            calls.append((self.command, self.path, self.headers.get("Authorization"),
                          self.headers.get("Idempotency-Key"), body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
        do_GET = answer
        do_PUT = answer
        def log_message(self, *args): pass

    holder = ThreadingHTTPServer(("127.0.0.1", 0), Holder)
    threading.Thread(target=holder.serve_forever, daemon=True).start()
    box, con, _ = site()
    box.objects.put("domain/view", json.dumps({"ts": box.wall(),
        "url": "http://127.0.0.1:" + str(holder.server_address[1])}).encode())
    try:
        with Served(Mount(con)) as call:
            assert call("GET", "/domain/users", headers={"Authorization": "Bearer admin"})[0] == 200
            assert call("GET", "/domain/grants?name=person", headers={"Authorization": "Bearer admin"})[0] == 200
            assert call("PUT", "/domain/grants/south", body={"person": ["view"]},
                        headers={"Authorization": "Bearer admin", "Idempotency-Key": "one-grant"})[0] == 200
            assert call("GET", "/domain/users", headers={"Authorization": "Bearer unknown"})[0] == 401
        assert calls == [("GET", "/domain/users", "Bearer admin", None, b""),
                         ("GET", "/domain/grants?name=person", "Bearer admin", None, b""),
                         ("PUT", "/domain/grants/south", "Bearer admin", "one-grant", b'{"person": ["view"]}')]
    finally:
        holder.shutdown()
        holder.server_close()

"""A member with no domain/view reaches only the holder's three person routes, by a signed record."""
import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tests.conftest import Box, Served
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.domain.agent import GRANTS_PATH, KEYS_PATH
from w2cplatform.domain.grants import Grant, grants_to_items
from w2cplatform.domain.term import HOLDER
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.trust.documents import sign
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.signer import DomainRoot
from w2cplatform.trust.tokens import TokenIssuer


def site():
    box = Box()
    spec = SubsystemSpec.from_dict({"name": "testsub", "unit": {"rows": "items", "id": "name", "fields": {
        "name": {"type": "string", "required": True}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}}})
    ctl = SpecController(spec, box.vars, box.objects, wall=box.wall, cluster="member")
    con = SpecConsole(ctl, box.resource_root)
    root = DomainRoot("site", now=box.wall)
    issuer = TokenIssuer("site", book_seal=MemberKey.new().seal_pub)
    box.vars.put(KEYS_PATH, root.key_set(issuer.keyset(), 1))
    box.vars.put(GRANTS_PATH, grants_to_items([Grant("alice", "view", None, box.wall() + 3600)]))
    record = sign({"holder": "holder", "term": 2, "at": box.wall(), "url": "http://127.0.0.1:1/untrusted"}, root)
    box.vars.put(HOLDER, {"doc": json.dumps(record)})
    token = issuer.issue("alice", 900, now=box.wall(), kind="person")
    assert box.objects.get("domain/view") is None
    return box, con, root, issuer, record, {"Authorization": "Bearer " + token}


@contextlib.contextmanager
def target(*, status=200, location=None):
    calls = []
    class H(BaseHTTPRequestHandler):
        def answer(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            calls.append((self.command, self.path, raw, dict(self.headers)))
            body = b'{"from":"holder"}'
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            if location:
                self.send_header("Location", location)
            self.send_header("X-Unreachable", "offline-member")
            self.end_headers()
            self.wfile.write(body)
        do_GET = do_PUT = answer
        def log_message(self, *args): pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}", calls
    finally:
        srv.shutdown(); srv.server_close(); thread.join(5)


def journal(box):
    return EventIndex(box.resource_root, "test", wall=box.wall).query(
        0, box.wall() + 1, subsystem="audit", unit="audit/console")["events"]


def forwarded_events(box, count):
    deadline = time.monotonic() + 2
    while True:
        events = [event for event in journal(box) if event["kind"] == "domain.forwarded"]
        if len(events) >= count:
            return events
        assert time.monotonic() < deadline, events
        time.sleep(.01)  # forward replies before its durable journal append finishes


def test_a_member_uses_its_verified_record_and_clusters_without_any_domain_view():
    box, con, root, issuer, record, headers = site()
    with target() as (url, calls), patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
        for path in ("/domain/users", "/domain/grants?subject=alice&subject=bob"):
            assert call("GET", path, headers={**headers, "X-Operator": "forged", "X-User": "forged"}) == (200, {"from": "holder"})
        raw = b' { "lines" : [{"subject":"account","cap":"view","scope":"*"}] } '
        assert call("PUT", "/domain/grants/member?rev=old", raw=raw,
                    headers={**headers, "Idempotency-Key": "original-key", "X-Operator": "forged"})[0] == 200
        assert len(calls) == 3
        assert [(method, path) for method, path, _, _ in calls] == [
            ("GET", "/domain/users"), ("GET", "/domain/grants?subject=alice&subject=bob"),
            ("PUT", "/domain/grants/member?rev=old")]
        for _, _, _, forwarded in calls:
            assert forwarded["Authorization"] == headers["Authorization"]
            assert forwarded["X-Operator"] == "console"
            assert forwarded["X-W2C-Via"] == "member"
            assert "X-User" not in forwarded
        assert calls[-1][2] == raw and calls[-1][3]["Idempotency-Key"] == "original-key"
        events = forwarded_events(box, 3)
        assert [(event["cluster"], event["user"], event["status"]) for event in events] == [("holder", "alice", 200)] * 3
        assert all(headers["Authorization"] not in json.dumps(event) for event in events)
        assert box.objects.get("domain/view") is None


def test_the_original_gate_still_refuses_unknown_people_before_the_hop():
    box, con, *_ = site()
    with target() as (url, calls), patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
        assert call("GET", "/domain/users", headers={"Authorization": "Bearer forged"})[0] == 401
        assert calls == []


def test_the_holder_mount_accepts_the_member_hop_then_reaches_its_own_domain_process():
    box, con, root, issuer, record, headers = site()
    holder_box, holder, *_ = site()
    holder.ctl.cluster = "holder"
    for key in (KEYS_PATH, GRANTS_PATH, HOLDER):
        holder_box.vars.put(key, box.vars.get(key)[0])
    with target() as (domain_url, calls):
        holder_box.objects.put("domain/view", json.dumps({"ts": holder_box.wall(), "url": domain_url}).encode())
        with Served(Mount(holder)) as there, patch.dict("os.environ", {"CLUSTERS": "holder=" + there.base}), \
                Served(Mount(con)) as call:
            assert call("GET", "/domain/users", headers=headers) == (200, {"from": "holder"})
            raw = b'{ "lines" : [{"subject":"account","cap":"view","scope":"*"}] }'
            assert call("PUT", "/domain/grants/member?change=one", raw=raw,
                        headers={**headers, "Idempotency-Key": "same-key"})[0] == 200
            assert [(method, path) for method, path, _, _ in calls] == [
                ("GET", "/domain/users"), ("PUT", "/domain/grants/member?change=one")]
            assert calls[-1][2] == raw and calls[-1][3]["Idempotency-Key"] == "same-key"
            assert all(sent["Authorization"] == headers["Authorization"] and sent["X-Operator"] == "console"
                       for _, _, _, sent in calls)
            assert all("X-W2C-Via" not in sent for _, _, _, sent in calls), "the local domain process is not another member hop"
            assert [(event["cluster"], event["user"], event["status"]) for event in forwarded_events(box, 2)] == [
                ("holder", "alice", 200), ("holder", "alice", 200)]


def test_no_record_forged_record_and_unknown_address_are_not_an_unverified_fallback():
    box, con, root, issuer, record, headers = site()
    with target() as (url, calls), patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
        bad = [None, {"doc": "{"}, {"doc": "[]"}, {"doc": json.dumps({**record, "holder": "forged"})},
               {"doc": json.dumps(sign({"holder": "holder", "term": 2, "at": box.wall()}, issuer))}]
        for row in bad:
            box.vars.as_writer("domainagent", [HOLDER]).delete(HOLDER) if row is None else box.vars.put(HOLDER, row)
            status, body = call("GET", "/domain/users", headers=headers)
            assert status == 503 and body["error"] == "the holder does not read", (row, status, body)
        box.vars.put(HOLDER, {"doc": json.dumps(record)})
        with patch.dict("os.environ", {"CLUSTERS": "other=" + url}):
            status, body = call("GET", "/domain/users", headers=headers)
            assert status == 404 and body["error"] == "no console known"
        with patch.dict("os.environ", {"CLUSTERS": "holder=" + url + ",holder=" + url}):
            status, body = call("GET", "/domain/grants", headers=headers)
            assert status == 503 and body["error"] == "CLUSTERS does not read"
        box.vars.put(HOLDER, {"doc": json.dumps(sign({"holder": "member", "term": 3, "at": box.wall()}, root))})
        assert call("GET", "/domain/users", headers=headers)[0] == 503
        assert calls == []


def test_the_fallback_does_not_open_other_domain_routes_or_another_hop():
    box, con, root, issuer, record, headers = site()
    with target() as (url, calls), patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
        for method, path in (("GET", "/domain/users/alice"), ("POST", "/domain/users"),
                             ("GET", "/domain/grants/member"), ("PUT", "/domain/grants/member/extra"),
                             ("DELETE", "/domain/grants/member"), ("GET", "/domain/topology")):
            assert call(method, path, headers=headers)[0] == 404, (method, path)
        assert call("GET", "/domain/users", headers={**headers, "X-W2C-Via": "earlier"})[0] == 400
        assert calls == []
    # A real second member receives the first one's marker and cannot proxy the request onwards.
    second_box, second, *_ = site()
    second.ctl.cluster = "second"
    for key in (KEYS_PATH, GRANTS_PATH, HOLDER):
        second_box.vars.put(key, box.vars.get(key)[0])
    with Served(Mount(second)) as there, patch.dict("os.environ", {"CLUSTERS": "holder=" + there.base}), Served(Mount(con)) as call:
        status, body = call("GET", "/domain/users", headers=headers)
        assert status == 400 and body["error"] == "one hop"
        assert not [event for event in journal(second_box) if event["kind"] == "domain.forwarded"]
        assert forwarded_events(box, 1)[-1]["status"] == 400


def test_this_hop_never_redirects_the_original_bearer_even_on_explicit_http():
    box, con, root, issuer, record, headers = site()
    with target() as (leak, leaked), target(status=307, location=leak) as (url, calls), \
            patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
        status, body = call("GET", "/domain/users", headers=headers)
        assert status == 307 and body == {"from": "holder"}
        assert len(calls) == 1 and leaked == []


def test_this_hop_uses_the_real_console_role_client_and_refuses_wrong_peer_or_missing_kit():
    from tests.test_role_client import kits, server
    box, con, root, issuer, record, headers = site()
    with kits() as ca, patch.dict("os.environ", {"W2C_TLS_DIR": ca.root, "W2C_ROLE": "console"}):
        with server(ca.issue("console")) as (url, calls), \
                patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
            assert call("GET", "/domain/users", headers=headers)[0] == 202
            assert len(calls) == 1 and calls[0][3]["Authorization"] == headers["Authorization"]
        with server(ca.issue("testsubworker")) as (url, calls), \
                patch.dict("os.environ", {"CLUSTERS": "holder=" + url}), Served(Mount(con)) as call:
            assert call("GET", "/domain/users", headers=headers)[0] == 502
            assert calls == []
        with server(ca.issue("console")) as (url, calls), \
                patch.dict("os.environ", {"CLUSTERS": "holder=" + url, "W2C_TLS_DIR": ca.root + "/absent"}), \
                Served(Mount(con)) as call:
            assert call("GET", "/domain/users", headers=headers)[0] == 502
            assert calls == []

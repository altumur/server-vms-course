"""Who is calling a cluster's console, and may they (the platform review, blocker 1; step 3 of the order agreed with
the product, feedback BP).

Whoever reached a console was an administrator under any name. The gate asks — when this cluster's store holds a key
set. Without one the console is as open as it was, and says so; with one and no way to check, it is SHUT.
"""
import json
import logging
import os
import urllib.error
import urllib.request

from w2cplatform.access import TRUST_KEYS, Denied, Gate, caller_addr, token_of
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC, SPEC
from vms.console import make_console
from vms.controller import VmsController
from tests.conftest import Box


class Tokens:
    """An `Access` with no cryptography: a token is a name, a grant is a line. What the domain's does with
    signatures and expiry (М12, `domain/access.py`), with none of it — the GATE is what is under test."""
    def __init__(self, grants):
        self.grants = grants                                           # {subject: [(capability, unit or None, labels)]}

    def who(self, token):
        if token.startswith("glass:"):
            return {"sub": "break-glass", "via": "break-glass", "who": token[6:]}
        if token not in self.grants:
            raise Denied(401, "token refused: nobody's")
        return {"sub": token}

    def glass(self, who, why, password):
        if password != "open-sesame":
            raise Denied(403, "the emergency password is wrong")
        return {"sub": "break-glass", "via": "break-glass", "who": who, "exp": 1e12}

    def may(self, payload, capability, unit, labels):
        if payload.get("via") == "break-glass":
            return True
        rank = {"view": 0, "edit": 1, "admin": 2}
        mine = self.grants[payload["sub"]]
        if unit is None and capability == "view":
            return bool(mine)
        return any(rank[c] >= rank[capability] and ((set(lab) <= set(labels)) if lab else u in (unit, None)) for c, u, lab in mine)


def _console(box, access=None):
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    m = make_console(ctl, box.archive, box.wall, mounts={"rec": rec},
                     index=EventIndex(box.archive, "srv-1", wall=box.wall))       # this box's own events, read where they lie
    if access is not None:
        m.root.gate.impl = access
        for con in m.mounts.values():
            con.gate.impl = access
    srv = m.serve("127.0.0.1", 0)
    return ctl, rec, m, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _call(base, method, path, body=None, token=None, user=None):
    _call.n = getattr(_call, "n", 0) + 1
    headers = {"Content-Type": "application/json", "Idempotency-Key": f"k-{_call.n}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if user:
        headers["X-User"] = user
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, (json.loads(r.read() or b"null") if "json" in r.headers.get("Content-Type", "") else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _audit(box):
    return [(e["kind"], e.get("user")) for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]]


def test_a_cluster_with_no_key_set_is_as_open_as_it_was_and_says_so():
    box = Box()
    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("w2cplatform.access").addHandler(h)
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"})[0] == 201
        assert _call(base, "DELETE", "/cameras/1", user="whoever")[0] == 200
        assert ("unit.deleted", "whoever") in _audit(box)              # the name the caller gave: nothing else to go by
        assert sum("this console is OPEN" in s for s in said) == 1     # said, once
    finally:
        srv.shutdown(); logging.getLogger("w2cplatform.access").removeHandler(h)


def test_the_journal_says_who_made_changed_and_deleted_a_unit_and_who_turned_the_policy():
    """The review's third pass, minor: the journal knew who deleted a camera, not who created or edited it; the
    policy was not written at all. `unit.created` and `unit.changed` name the fields — never their values — and the
    author; `policy.changed` the new values. `unit.deleted` is written BEFORE the delete: a deleted unit is not there
    to be its own evidence, and a delete that then fails is followed by `unit.delete.failed`."""
    box = Box()
    ctl, rec, m, srv, base = _console(box)

    def lines():
        return [{k: e.get(k) for k in ("kind", "user", "target", "fields", "policy") if e.get(k) is not None}
                for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]]
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4", "cred_secret": "hunter2"}, user="anna")[0] == 201
        assert _call(base, "PUT", "/cameras/1", {"enabled": False, "priority": 5}, user="boris")[0] == 200
        assert _call(base, "PUT", "/policy", {"servers": "shared"}, user="carol")[0] == 200
        delete = m.root.ctl.delete
        m.root.ctl.delete = lambda uid: (_ for _ in ()).throw(PermissionError(13, "the store does not answer"))
        assert _call(base, "DELETE", "/cameras/1", user="dave")[0] == 503
        m.root.ctl.delete = delete
        assert _call(base, "DELETE", "/cameras/1", user="dave")[0] == 200
        assert lines() == [
            {"kind": "unit.created", "user": "anna", "target": "1", "fields": "cred_secret,source"},
            {"kind": "unit.changed", "user": "boris", "target": "1", "fields": "enabled,priority"},
            {"kind": "policy.changed", "user": "carol", "policy": '{"servers": "shared"}'},
            {"kind": "unit.deleted", "user": "dave", "target": "1"},
            {"kind": "unit.delete.failed", "user": "dave", "target": "1"},
            {"kind": "unit.deleted", "user": "dave", "target": "1"},
        ]
        assert "hunter2" not in json.dumps(lines())
    finally:
        srv.shutdown()


def test_a_key_set_and_no_way_to_check_a_token_is_shut_not_open():
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "GET", "/cameras")[0] == 200
        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})   # the cluster joined a domain while the console ran
        code, body = _call(base, "GET", "/cameras", token="anything")
        assert code == 503 and "cannot verify a token" in body["detail"]   # `domain.access` is not installed beside this console
        assert _call(base, "DELETE", "/cameras/1")[0] == 503 and _call(base, "GET", "/rec/recordings")[0] == 503
        assert _call(base, "GET", "/metrics")[0] == 200                     # what monitoring reads stays open
        # the key set deleted, or rolled back from a backup made before the cluster joined: NOT open again
        os.remove(box.vars._file(TRUST_KEYS))                         # past the store: only the agent may delete it there
        code, body = _call(base, "GET", "/cameras")
        assert code == 503 and "has gone" in body["detail"]
    finally:
        srv.shutdown()

    class Away:
        def get(self, path): raise PermissionError(13, "the store does not answer")
    try:
        Gate(Away(), box.wall).admit({}, "view")
        raise AssertionError("a gate that could not read the trust admitted somebody")
    except Denied as e:
        assert e.status == 503


def test_a_cluster_that_is_in_a_domain_stays_shut_without_its_keys_after_a_restart_too():
    """The review's third pass (Н-M2): that a cluster had a key set lived in one `Gate`'s memory — the row rolled
    back, the console restarted, and every request passed as `admin`. What says "a member" is in the store: the root
    the agent pinned, or any other row only the agent writes (`DOMAIN_MARKS`). With one of them and no key set a
    console that has never seen the keys is shut too. And `domain/*` is deleted by nobody but the agent."""
    from w2cplatform.access import DOMAIN_MARKS
    from w2cplatform.variables import Forbidden
    box = Box()
    box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})
    box.vars.put("domain/root", {"pub": "ab" * 32})
    box.vars.put("domain/grants", {"anna": "admin"})
    for who in (box.vars, box.vars.as_writer("console", SPEC.acl_console())):
        try:
            who.delete(TRUST_KEYS)
            raise AssertionError("somebody other than the agent deleted the key set")
        except Forbidden:
            pass
    os.remove(box.vars._file(TRUST_KEYS))                              # rolled back from a backup, past the store
    for mark in DOMAIN_MARKS:                                          # …a console started afterwards, by each mark alone
        others = [p for p in DOMAIN_MARKS if p != mark and box.vars.get(p)[0]]
        for p in others:
            os.remove(box.vars._file(p))
        if not box.vars.get(mark)[0]:
            box.vars.put(mark, {"x": "1"})
        ctl, rec, m, srv, base = _console(box)
        try:
            code, body = _call(base, "GET", "/cameras", user="admin")
            assert code == 503 and mark in body["detail"], (mark, code, body)
        finally:
            srv.shutdown()
    box.vars.as_writer("agent", ["domain/*"]).delete(DOMAIN_MARKS[-1])  # the agent may; then nothing says "a member"
    assert not any(box.vars.get(p)[0] for p in DOMAIN_MARKS)
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "GET", "/cameras")[0] == 200                   # a cluster nobody joined: open, as it was
    finally:
        srv.shutdown()


def test_the_gate_asks_who_and_the_grant_says_what():
    box = Box()
    access = Tokens({"viewer": [("view", "1", ())], "guard": [("edit", None, ("ground",))], "admin": [("admin", None, ())], "nobody": []})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["ground"]}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/2.mp4"}, token="admin")[0] == 201

        assert _call(base, "GET", "/cameras")[0] == 401                                   # nobody proved who they are
        assert _call(base, "GET", "/cameras", token="stranger")[0] == 401
        assert _call(base, "GET", "/cameras", user="admin")[0] == 401                     # a name in a header is not a proof
        assert _call(base, "GET", "/cameras", token="nobody")[0] == 403                   # proved, and holds no grant at all
        assert _call(base, "GET", "/cameras", token="viewer")[0] == 200                   # to look: any grant
        assert _call(base, "GET", "/where/1", token="viewer")[0] in (200, 404)            # its camera
        assert _call(base, "GET", "/where/2", token="viewer")[0] == 403                   # not its camera
        assert _call(base, "DELETE", "/cameras/1", token="viewer")[0] == 403              # looking is not changing

        # a labelled grant: the cameras that carry the label, and not "every camera"
        assert _call(base, "GET", "/where/1", token="guard")[0] in (200, 404) and _call(base, "GET", "/where/2", token="guard")[0] == 403
        assert _call(base, "POST", "/marks", {"cam": 1, "note": "bag"}, token="guard")[0] == 201   # an action names its unit in the BODY
        assert _call(base, "POST", "/marks", {"cam": 2, "note": "bag"}, token="guard")[0] == 403   # …and this one is not the guard's
        assert _call(base, "POST", "/marks", {"cam": 1, "note": "bag"}, token="viewer")[0] == 403  # looking is not acting
        # a body that names two units is refused, not checked on one and acted on the other (the review's second pass)
        assert _call(base, "POST", "/marks", {"unit": 1, "cam": 2, "note": "bag"}, token="guard")[0] == 400
        # a GET names its unit in the query the same way: the device's own footage of camera 2 is not the viewer's
        assert _call(base, "GET", "/segment?cam=1&from=0&to=1", token="viewer")[0] in (200, 503)
        assert _call(base, "GET", "/segment?cam=2&from=0&to=1", token="viewer")[0] == 403
        assert _call(base, "GET", "/events?from=0&to=1&cam=2", token="viewer")[0] == 403
        # …and an export of camera 1 cannot name a recording of camera 2 (blocker 1 of that pass)
        assert _call(base, "POST", "/rec/recordings", {"name": "2-cloud", "cam": "2"}, token="admin")[0] == 201
        assert _call(base, "GET", "/export/1?rec=2-cloud&from=0&to=60", token="viewer")[0] == 404
        assert _call(base, "GET", "/export/2?rec=2-cloud&from=0&to=60", token="viewer")[0] == 403

        # a list shows a caller what their grants cover, and not the cluster's
        ids = lambda token: sorted(r["id"] for r in _call(base, "GET", "/cameras", token=token)[1]["configured"])
        assert ids("viewer") == [1] and ids("guard") == [1] and ids("admin") == [1, 2]

        # the name in the journal is the one the token proved — whatever the header said
        assert _call(base, "DELETE", "/cameras/2", token="admin", user="somebody-else")[0] == 200
        said = _audit(box)
        assert ("unit.deleted", "admin") in said and ("unit.deleted", "somebody-else") not in said
        assert ("access.denied", "viewer") in said
        # …and the events too: the journal names no unit, and is shown to whoever may view the whole cluster
        seen = lambda token: {e["kind"] for e in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}", token=token)[1]["events"]}
        assert "unit.deleted" in seen("admin") and "unit.deleted" not in seen("viewer") and "mark" in seen("viewer")

        # a mount is gated by the same rules, and its own routes: a keep is an operator's, a volume an administrator's
        t = box.wall()
        keep = {"cam": "1", "from": t - 900, "to": t - 300}
        assert _call(base, "POST", "/rec/keeps", keep, token="viewer")[0] == 403
        assert _call(base, "POST", "/rec/keeps", {**keep, "cam": "2"}, token="guard")[0] == 403
        assert _call(base, "POST", "/rec/keeps", keep, token="admin")[0] == 201
        vol = {"name": "cold", "kind": "network", "url": "s3://vms/x", "quota_bytes": 10 ** 12}
        assert _call(base, "POST", "/rec/volumes", vol, token="guard")[0] == 403 and _call(base, "POST", "/rec/volumes", vol, token="admin")[0] == 201

        # the one local account: admitted, and every use that ACTS is an alarm with the person's name in it — a
        # read is not (the session's opening was the alarm for looking; a page polls every three seconds)
        assert _call(base, "GET", "/cameras", token="glass:carol")[0] == 200
        alarms = lambda: [(e["kind"], e["user"]) for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]
        assert alarms() == []
        assert _call(base, "DELETE", "/cameras/1", token="glass:carol")[0] == 200
        assert alarms() == [("access.break_glass", "break-glass(carol)")]
    finally:
        srv.shutdown()


def test_what_a_route_needs_and_where_a_token_is_read_from():
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    srv.shutdown()
    cam = ctl.create_camera({"source": "driverpack://file/1.mp4", "labels": ["ground"]})["id"]
    rec.create({"name": "1-cloud", "cam": str(cam)})
    root, recs = m.root, m.mounts["rec"]
    assert root.needs("GET", "/cameras") == ("view", None, []) and root.needs("GET", f"/cameras/{cam}") == ("view", str(cam), ["ground"])
    assert root.needs("POST", "/cameras") == ("admin", None, []) and root.needs("DELETE", f"/cameras/{cam}")[0] == "admin"
    assert root.needs("POST", "/requests")[0] == "edit" and root.needs("POST", "/backfill")[0] == "edit" and root.needs("POST", "/marks")[0] == "edit"
    assert root.needs("POST", f"/whep/{cam}") == ("view", str(cam), ["ground"])          # a live stream: `view` on that camera
    assert root.needs("GET", f"/timeline/{cam}")[1] == str(cam)
    assert recs.needs("DELETE", "/recordings/1-cloud") == ("admin", str(cam), ["ground"])   # a recording is its camera's — and so are its labels
    assert recs.needs("POST", "/keeps")[0] == "edit" and recs.needs("POST", "/volumes")[0] == "admin"
    assert root.needs("POST", "/marks", str(cam)) == ("edit", str(cam), ["ground"]) and recs.needs("POST", "/keeps", str(cam)) == ("edit", str(cam), ["ground"])
    assert token_of({"Authorization": "Bearer abc"}) == "abc" and token_of({"Cookie": "a=b; w2c_token=xyz"}) == "xyz"
    assert token_of({}) is None and token_of({"Authorization": "Basic abc"}) is None


def test_the_live_gateway_asks_the_viewer_too():
    """The console checks a viewer's token and then calls the gateway — a door anybody on its network could call
    instead. The console passes the token on, and the gateway checks it by the same gate, against the same
    store: `view` on this camera."""
    from tests.test_lesson8_live import OFFER, _gateway
    box = Box()
    box.vars.put("vms/cameras/1", {"name": "gate", "labels": "ground"})
    box.vars.put("vms/cameras/2", {"name": "yard", "labels": ""})
    g = _gateway(box, "g-1")
    base = g.url

    def whep(cam, token=None, method="POST", path=None):
        req = urllib.request.Request(base + (path or f"/whep/{cam}"), data=OFFER.encode() if method == "POST" else None, method=method,
                                     headers={"Content-Type": "application/sdp", **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    assert whep(1) == 404                                              # no key set: open — and the stream is simply not here
    g.gate.impl = Tokens({"viewer": [("view", "1", ())], "guard": [("view", None, ("ground",))], "nobody": []})
    assert whep(1) == 401 and whep(1, "stranger") == 401               # now it asks
    assert whep(1, "viewer") == 404 and whep(2, "viewer") == 403       # admitted for its camera (and the stream is not here); not for another
    assert whep(1, "guard") == 404 and whep(2, "guard") == 403         # a grant on a label: the camera's labels, read from its row
    assert whep(1, "nobody") == 403
    assert whep(None, method="DELETE", path="/whep/session/x") == 401 and whep(None, "viewer", "DELETE", "/whep/session/x") == 404


def test_a_grant_on_labels_reaches_the_recordings_of_the_cameras_that_carry_them():
    """A recording is its camera's, and so is a keep. A grant on the label `ground` covers the recordings of the
    cameras labelled `ground` — read from the CAMERA's row: a recording's own labels say where it may run."""
    box = Box()
    access = Tokens({"guard": [("edit", None, ("ground",))], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["ground"]}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/2.mp4"}, token="admin")[0] == 201
        rec.create({"name": "1-cloud", "cam": "1", "labels": ["rack-7"]}); rec.create({"name": "2-cloud", "cam": "2"})
        t = box.wall()
        assert _call(base, "POST", "/rec/keeps", {"cam": "1", "from": t - 900, "to": t - 300}, token="guard")[0] == 201
        assert _call(base, "POST", "/rec/keeps", {"cam": "2", "from": t - 900, "to": t - 300}, token="guard")[0] == 403
        names = sorted(r["id"] for r in _call(base, "GET", "/rec/recordings", token="guard")[1]["configured"])
        assert names == ["1-cloud"]                                   # its camera carries the label; the recording's own "rack-7" does not matter
        assert _call(base, "GET", "/rec/where/1-cloud", token="guard")[0] in (200, 404) and _call(base, "GET", "/rec/where/2-cloud", token="guard")[0] == 403
    finally:
        srv.shutdown()



def test_the_emergency_door_closes_after_a_handful_of_wrong_passwords():
    """The one account with rights to everything is the one password worth guessing — and every wrong guess was a
    fsync'd alarm. Five refusals from one address in fifteen minutes close the door to it, with ONE alarm saying
    so; the right password does not open it until the window has passed."""
    Gate._glass_tries.clear(); Gate._glass_limited.clear()                # the counts are the process's
    box = Box()
    ctl, rec, m, srv, base = _console(box, Tokens({"admin": [("admin", None, ())]}))
    try:
        glass = lambda pw: _call(base, "POST", "/session", {"glass": {"who": "carol", "why": "uplink down", "password": pw}})[0]
        assert glass("open-sesame") == 200                                                        # the account works
        assert [glass("wrong") for _ in range(5)] == [403] * 5
        assert glass("wrong") == 429 and glass("open-sesame") == 429                              # closed, to the right password too
        alarms = [e["kind"] for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]
        assert alarms.count("access.break_glass.refused") == 5 and alarms.count("access.break_glass.limited") == 1
        assert alarms.count("access.break_glass.opened") == 1                                     # nothing more for the guesses past the limit
        box.wall.advance(901)
        assert glass("open-sesame") == 200                                                        # the window passed
    finally:
        srv.shutdown()


def test_an_emergency_attempt_is_reserved_before_its_password_and_counted_by_the_callers_own_address():
    """The review's third pass, major. The limit was a check and then a count: thirty parallel guesses all passed the
    check. An attempt is reserved under a lock before the password is looked at, and given back only when it was
    right — so at most five guesses from one address are ever checked. Behind a proxy every caller was the proxy;
    `X-Forwarded-For` is taken from a proxy named in `TRUSTED_PROXY` and from nobody else. And while a window is
    full — the address's, or the process's — the right password is 429 too: a limit that lets the right guess in
    limits nothing."""
    import threading
    import time
    Gate._glass_tries.clear(); Gate._glass_limited.clear()
    box = Box()

    class Slow(Tokens):
        def glass(self, who, why, password):
            time.sleep(0.05)                                           # every check in flight at once
            return super().glass(who, why, password)

    gate = Gate(box.vars, box.wall, impl=Slow({}))
    out = []

    def guess(addr="10.0.0.9", pw="wrong"):
        try:
            gate.open_glass("mallory", "testing", pw, addr=addr)
            out.append(200)
        except Denied as e:
            out.append(e.status)
    threads = [threading.Thread(target=guess) for _ in range(30)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sorted(out).count(403) == 5 and out.count(429) == 25          # five checked; the rest never reached the password
    out.clear(); guess(pw="open-sesame")
    assert out == [429]                                                  # this address's window is full: the right password too
    out.clear(); guess("10.0.0.1", "open-sesame"); guess("10.0.0.1", "open-sesame")
    assert out == [200, 200]                                             # another address; and the right password is no guess
    for i in range(3):                                                   # spread over addresses: the process's window fills
        for _ in range(5):
            guess(f"10.0.1.{i}")
    out.clear(); guess("10.0.2.1", "open-sesame")
    assert out == [429]                                                  # 20 refused in the window: shut to everybody
    assert caller_addr({"X-Forwarded-For": "1.2.3.4"}, "10.0.0.5") == "10.0.0.5"   # nobody said to trust anybody

    # over HTTP, behind a proxy: five wrong from one person close it to that person, not to the next one
    Gate._glass_tries.clear(); Gate._glass_limited.clear()
    ctl, rec, m, srv, base = _console(box, Tokens({"admin": [("admin", None, ())]}))

    def glass(pw, xff):
        req = urllib.request.Request(base + "/session", method="POST", headers={"Content-Type": "application/json", "X-Forwarded-For": xff},
                                     data=json.dumps({"glass": {"who": "carol", "why": "uplink down", "password": pw}}).encode())
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
    was = os.environ.get("TRUSTED_PROXY")
    try:
        os.environ["TRUSTED_PROXY"] = "127.0.0.1"
        assert [glass("wrong", "10.9.9.9") for _ in range(5)] == [403] * 5
        assert glass("open-sesame", "10.9.9.9") == 429                   # that person
        assert glass("open-sesame", "203.0.113.7, 10.8.8.8") == 200      # the next one: the address the proxy saw
        os.environ.pop("TRUSTED_PROXY")                                  # not trusted: the header is the caller's word
        assert [glass("wrong", f"10.6.6.{i}") for i in range(5)] == [403] * 5
        assert glass("open-sesame", "10.7.7.7") == 429                   # …five "addresses" that were one peer
    finally:
        srv.shutdown()
        os.environ.pop("TRUSTED_PROXY", None)
        if was is not None:
            os.environ["TRUSTED_PROXY"] = was
        Gate._glass_tries.clear(); Gate._glass_limited.clear()


def test_the_gate_and_the_route_read_the_unit_from_the_same_segment():
    """The review's third pass, blocker 1. The gate read the unit from the second segment and the routes from the
    last: `DELETE /cameras/1/2` with `admin` on camera 1 deleted camera 2, `GET /export/1/2` with `view` on 1 reached
    2. One reading of a path's id (`path_id`) for both; a family that takes an id takes one, and more after it is
    404 before the gate — except `PUT /<rows>/<id>/<blob>`, the one route with a third segment."""
    box = Box()
    access = Tokens({"one": [("admin", "1", ())], "viewer": [("view", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "1"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "2-cloud", "cam": "2"}, token="admin")[0] == 201

        assert _call(base, "DELETE", "/cameras/1/2", token="one")[0] == 404          # the confirmed case: no route
        assert _call(base, "DELETE", "/cameras/1/2")[0] == 404                       # …said before the gate is asked
        assert ctl.camera(2) is not None and ctl.camera(1) is not None
        assert _call(base, "PUT", "/cameras/1/2", {"enabled": False}, token="one")[0] == 404   # a blob route: `2` is no blob field
        assert _call(base, "PUT", "/cameras/1/2/3", {"enabled": False}, token="one")[0] == 404
        assert ctl.camera(2)["enabled"] is True
        for path in ("/export/1/2?from=0&to=60", "/timeline/1/2", "/where/1/2", "/cameras/1/2"):
            assert _call(base, "GET", path, token="viewer")[0] == 404, path
        assert _call(base, "POST", "/whep/1/2", token="viewer")[0] == 404
        # the mounts' families: a recording, a keep, a volume — one id, and nothing after it
        assert _call(base, "DELETE", "/rec/recordings/1-cloud/2-cloud", token="one")[0] == 404
        assert rec.unit("2-cloud") is not None
        assert _call(base, "DELETE", "/rec/keeps/a/b", token="admin")[0] == 404
        assert _call(base, "DELETE", "/rec/volumes/cold/x", token="admin")[0] == 404
        # and the one id there is, is the one checked and the one acted on
        assert _call(base, "DELETE", "/cameras/2", token="one")[0] == 403
        assert _call(base, "DELETE", "/rec/recordings/2-cloud", token="one")[0] == 403
        assert _call(base, "DELETE", "/cameras/1", token="one")[0] == 200 and ctl.camera(2) is not None
    finally:
        srv.shutdown()


def test_a_console_listening_beyond_loopback_says_so_when_it_starts():
    """The review's third pass, minor: the unit binds `0.0.0.0` over plain HTTP. It keeps doing so — the page is
    opened from the operator's machine and no TLS proxy ships — and the console says it in its log at start."""
    from w2cplatform.console import say_where
    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("w2cplatform.console").addHandler(h)
    try:
        say_where("127.0.0.1"); say_where("::1")
        assert said == []
        say_where("0.0.0.0")
        assert len(said) == 1 and "beyond loopback" in said[0] and "TLS" in said[0]
    finally:
        logging.getLogger("w2cplatform.console").removeHandler(h)


def test_drain_schema_and_mounts_ask_the_gate_too():
    """The review's third pass, blocker 2: `/drain`, `/schema` and `/mounts` were answered by the Mount before the
    console's gate — `POST /drain` with no token took every recording off a server. Now the root console's gate:
    `admin` to change, `view` to read; a drain and a schema raised are lines in the journal, with the name."""
    from w2cplatform.contract import SCHEMA
    box = Box()
    access = Tokens({"viewer": [("view", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        assert _call(base, "POST", "/drain?server=srv-1")[0] == 401
        assert _call(base, "POST", "/drain?server=srv-1", token="viewer")[0] == 403
        assert ctl.draining() == ""
        assert _call(base, "POST", "/drain?server=srv-1", token="admin")[0] == 200 and ctl.draining() == "srv-1"
        assert _call(base, "GET", "/drain")[0] == 401 and _call(base, "GET", "/drain", token="viewer")[0] == 200
        assert _call(base, "DELETE", "/drain", token="viewer")[0] == 403 and ctl.draining() == "srv-1"
        assert _call(base, "DELETE", "/drain", token="admin")[0] == 200 and ctl.draining() == ""

        assert _call(base, "PUT", f"/schema?version={SCHEMA}")[0] == 401
        assert _call(base, "PUT", f"/schema?version={SCHEMA}", token="viewer")[0] == 403
        assert _call(base, "GET", "/schema")[0] == 401 and _call(base, "GET", "/schema", token="viewer")[0] == 200
        code, body = _call(base, "PUT", f"/schema?version={SCHEMA}", token="admin")
        assert code == 403 and "platform/schema" in body["detail"]       # past the gate, the console's TOKEN may not
        m.root.ctl.vars = box.vars                                         # a console whose token reaches it
        assert _call(base, "PUT", f"/schema?version={SCHEMA}", token="admin")[0] == 200

        assert _call(base, "GET", "/mounts")[0] == 401
        code, body = _call(base, "GET", "/mounts", token="viewer")
        assert code == 200 and "rec" in body["mounts"]

        said = _audit(box)
        assert ("drain.started", "admin") in said and ("drain.ended", "admin") in said and ("schema.raised", "admin") in said
        assert not [s for s in said if s[0].startswith(("drain.", "schema.")) and s[1] != "admin"]
    finally:
        srv.shutdown()

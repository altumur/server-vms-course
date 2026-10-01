"""Who is calling a cluster's console, and may they (the platform review, blocker 1; step 3 of the order agreed with
the product, feedback BP).

Whoever reached a console was an administrator under any name. The gate asks — when this cluster's store holds a key
set. Without one the console is as open as it was, and says so; with one and no way to check, it is SHUT.
"""
import json
import logging
import urllib.error
import urllib.request

from w2cplatform.access import TRUST_KEYS, Denied, Gate, token_of
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
        box.vars.delete(TRUST_KEYS)
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

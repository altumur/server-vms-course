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


def test_one_garbled_camera_row_costs_that_cameras_events_and_not_the_timeline():
    """The gate of `/events` read each unit's labels with `ctl.unit` bare (the scaling pass after the eighth review): one
    row that does not parse was a 400 for the whole timeline of everybody the gate checks — a row with no `id`, no reply
    at all. Now the row is that unit's: a grant by label is not shown its events (what labels it carries is not known),
    and the answer says so by unit (`withheld`); the unit's own grant and the whole cluster's see them; the row is counted
    once, on `/metrics`."""
    from w2cplatform.console import UNIT_LABELS
    from w2cplatform.rows import forget
    forget()
    box = Box()
    access = Tokens({"guard": [("view", None, ("ground",))], "two": [("view", "2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for n in (1, 2, 3):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{n}.mp4", "labels": ["ground"]}, token="admin")[0] == 201
            assert _call(base, "POST", "/marks", {"cam": n, "note": f"bag {n}"}, token="admin")[0] == 201
        cams = lambda token: sorted({e.get("cam") for e in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}",
                                                                 token=token)[1]["events"] if e.get("cam") is not None})
        assert cams("guard") == [1, 2, 3]
        items, _ = box.vars.get("vms/cameras/2")
        box.vars.put("vms/cameras/2", {**items, "revision": "two"})              # a word where a number goes
        items3, _ = box.vars.get("vms/cameras/3")
        box.vars.put("vms/cameras/3", {k: v for k, v in items3.items() if k != "id"})   # no `id`: a KeyError
        reads, real_get = [], ctl.vars.get
        ctl.vars.get = lambda *a, **k: (reads.append(a[0]), real_get(*a, **k))[1]
        status, rep = _call(base, "GET", f"/events?from=0&to={box.wall() + 1}", token="guard")
        ctl.vars.get = real_get
        assert status == 200, rep
        assert len(reads) <= 3, reads                                            # a row per camera in the answer, no more
        assert sorted({e.get("cam") for e in rep["events"] if e.get("cam") is not None}) == [1]
        assert [(w["unit"], w["events"]) for w in rep["withheld"]] == [("2", 1), ("3", 1)], rep["withheld"]
        assert "does not parse" in rep["withheld"][0]["why"]
        assert cams("two") == [2] and cams("admin") == [1, 2, 3]                 # no label needed: shown as before
        assert "withheld" not in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}", token="admin")[1]
        assert UNIT_LABELS.counts.get("vms") == 2                                # two rows, each once — not once a read
        metrics = urllib.request.urlopen(urllib.request.Request(base + "/metrics", headers={"Authorization": "Bearer admin"})).read().decode()
        assert 'vms_console_rows_garbled{table="unit"} 2' in metrics
    finally:
        srv.shutdown()
        forget()


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
    Gate.forget_glass()                # the counts are the process's
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
    `X-Forwarded-For` is taken from a proxy named in `TRUSTED_PROXY` and from nobody else. And while an address's
    window is full the right password from it is 429 too: a limit that lets the right guess in limits nothing."""
    import threading
    import time
    Gate.forget_glass()
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
    assert caller_addr({"X-Forwarded-For": "1.2.3.4"}, "10.0.0.5") == "10.0.0.5"   # nobody said to trust anybody

    # over HTTP, behind a proxy: five wrong from one person close it to that person, not to the next one
    Gate.forget_glass()
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
        Gate.forget_glass()


def test_the_emergency_doors_limit_across_addresses_is_a_pace_and_a_trickle_cannot_hold_it_shut():
    """The review's fourth pass, major: the process's limit was a window — twenty wrong passwords from anywhere shut
    the door to everybody, the right password too, and one wrong guess every 45 s from four addresses kept it shut
    for good (the product's own check). It is a pace now: at most `GLASS_RATE` checks a minute, a check past it WAITS
    its turn, and only one that would wait more than `GLASS_WAIT` is 429 with `Retry-After`. Twenty wrong from four
    addresses, then the right one from a fifth: in, within a turn. A trickle never fills the pace: in at once. A
    flood is told when to come back, and the alarm says the pace was full — once."""
    clock = {"t": 1000.0}
    waited = []
    Gate.forget_glass()
    real = Gate._glass_clock, Gate._glass_sleep
    Gate._glass_clock = staticmethod(lambda: clock["t"])
    Gate._glass_sleep = staticmethod(lambda s: (waited.append(s), clock.__setitem__("t", clock["t"] + s)))
    box = Box()
    gate = Gate(box.vars, box.wall, impl=Tokens({}))

    def guess(addr, pw="wrong"):
        try:
            gate.open_glass("x", "testing", pw, addr=addr)
            return 200, None
        except Denied as e:
            return e.status, e.retry_after
    try:
        got = [guess(f"10.0.1.{i % 4}")[0] for i in range(20)]
        assert got == [403] * 20                                       # all checked — at the pace, not refused
        assert len(waited) == 10 and max(waited) <= Gate.GLASS_WAIT    # ten at once, ten in their turns
        before = len(waited)
        assert guess("10.0.2.1", "open-sesame")[0] == 200              # the right one, from an address not refused
        assert sum(waited[before:]) <= 60.0 / Gate.GLASS_RATE          # …within one turn
        assert guess("10.0.1.0", "open-sesame")[0] == 429              # an address refused five times is still refused

        Gate.forget_glass(); waited.clear()                            # a trickle: one wrong every 45 s from four addresses, for hours
        for i in range(400):
            clock["t"] += 45; box.wall.advance(45)
            guess(f"10.0.3.{i % 4}")
        n = len(waited)
        assert guess("10.0.4.1", "open-sesame")[0] == 200 and len(waited) == n   # in at once: the trickle never filled the pace

        Gate.forget_glass(); waited.clear()                            # a flood: forty at the same moment, from many addresses
        Gate._glass_sleep = staticmethod(lambda s: waited.append(s))   # all of them in flight at once: nobody's wait has passed
        codes = [guess(f"10.1.{i // 5}.{i % 5}") for i in range(40)]
        refused = [c for c in codes if c[0] == 429]
        assert refused and all(0 < r <= 60.0 for _, r in refused)      # told when the next turn is
        assert guess("10.0.5.1", "open-sesame")[0] == 429              # the right password competes for a turn…
        clock["t"] += 60; box.wall.advance(60)
        assert guess("10.0.5.1", "open-sesame")[0] == 200              # …and gets the next one
    finally:
        Gate._glass_clock, Gate._glass_sleep = staticmethod(real[0]), staticmethod(real[1])
        Gate.forget_glass()


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


def test_a_row_cannot_be_moved_to_another_camera_by_an_edit():
    """The review's fourth pass, major: the gate checks the camera a row names NOW, and `PUT /rec/recordings/1-cloud
    {"cam": "2"}` with `admin` on camera 1 passed on camera 1 and moved the recording to camera 2 — the recorder wrote
    camera 2 into the tree camera 1's viewers read; a detector took its alarms along. `cam` is fixed at creation:
    400, naming why, for anybody — the same value is no change. Every subsystem whose rows name a camera."""
    from vms.config import DET_SPEC
    box = Box()
    access = Tokens({"one": [("admin", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "1"}, token="admin")[0] == 201
        # (since the review's sixth pass the gate asks about every camera a recording's row reaches, as it will be
        # too: camera 2 is not hers, and she is told that first — 403; with rights on both it is still not a move)
        assert _call(base, "PUT", "/rec/recordings/1-cloud", {"cam": "2"}, token="one")[0] == 403
        code, body = _call(base, "PUT", "/rec/recordings/1-cloud", {"cam": "2"}, token="admin")
        assert code == 400 and "fixed" in body["detail"] and rec.unit("1-cloud")["cam"] == "1"
        assert _call(base, "PUT", "/rec/recordings/1-cloud", {"cam": "1", "retention_days": 3}, token="one")[0] == 200
        assert rec.unit("1-cloud")["retention_days"] == 3
        det = SpecController(DET_SPEC, box.vars.as_writer("console", DET_SPEC.acl_console()), box.objects, wall=box.wall)
        det.create({"name": "1-motion", "cam": "1", "kind": "motion"})
        try:
            det.update("1-motion", {"cam": "2"})
            raise AssertionError("a detector moved to another camera")
        except Exception as e:
            assert "fixed" in str(e) and det.unit("1-motion")["cam"] == "1"
        assert all(c.labels_of is not None for n, c in m.mounts.items() if "cam" in c.spec.fields)
    finally:
        srv.shutdown()


def _console_with_jobs(box, access):
    """A gated console that fronts `rec`, `det`, `detjob` (`DetJobController`) and `auto`, as `python3 -m vms console` does."""
    from vms.auto import AutoController
    from vms.config import AUTO_SPEC, DET_SPEC, DETJOB_SPEC
    from vms.jobs import DetJobController
    acl = SPEC.acl_console() + REC_SPEC.acl_console() + DET_SPEC.acl_console() + DETJOB_SPEC.acl_console() + AUTO_SPEC.acl_console()
    vars_ = box.vars.as_writer("console", acl)
    ctl = VmsController(vars_, box.objects, wall=box.wall)
    mounts = {"rec": SpecController(REC_SPEC, vars_, box.objects, wall=box.wall),
              "det": SpecController(DET_SPEC, vars_, box.objects, wall=box.wall),
              "detjob": DetJobController(vars_, box.objects, wall=box.wall),
              "auto": AutoController(vars_, box.objects, wall=box.wall)}
    m = make_console(ctl, box.archive, box.wall, mounts=mounts, index=EventIndex(box.archive, "srv-1", wall=box.wall))
    for con in (m.root, *m.mounts.values()):
        con.gate.impl = access
    srv = m.serve("127.0.0.1", 0)
    return mounts, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_a_scan_reads_only_its_own_cameras_recording_and_keeps_it():
    """The review's fifth pass, major: `cam` was fixed, and a scan names a camera through another field too — `rec`, the
    recording whose footage it reads. `PUT /detjob/jobs/1-motion-1 {"rec": "2"}` with `admin` on camera 1 was 200, and
    the scan read camera 2's archive. The gate asks for the route's capability on every camera a row reaches, before
    and after the edit; and `rec` is a recording of `cam`, fixed when the job is made — for anybody."""
    box = Box()
    access = Tokens({"one": [("admin", "1", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    t = box.wall()
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
            assert _call(base, "POST", "/rec/recordings", {"name": str(i), "cam": str(i)}, token="admin")[0] == 201
        job = {"name": "1-motion-1", "cam": "1", "rec": "1", "kind": "motion", "from": t - 600, "to": t - 300}
        assert _call(base, "POST", "/detjob/jobs", job, token="admin")[0] == 201
        assert _call(base, "PUT", "/detjob/jobs/1-motion-1", {"rec": "2"}, token="one")[0] == 403   # camera 2 is not hers
        code, body = _call(base, "PUT", "/detjob/jobs/1-motion-1", {"rec": "2"}, token="admin")
        assert code == 400 and "fixed" in body["detail"]                                      # rights on both: still not a move
        assert mounts["detjob"].unit("1-motion-1")["rec"] == "1"
        assert _call(base, "PUT", "/detjob/jobs/1-motion-1", {"params": "{}"}, token="one")[0] == 200   # her camera, her scan
        code, body = _call(base, "POST", "/detjob/jobs", {**job, "name": "1-motion-2", "rec": "2"}, token="admin")
        assert code == 400 and "camera 2's" in body["detail"]                                 # another camera's recording
    finally:
        srv.shutdown()


def test_a_scenario_is_edited_by_whoever_may_act_on_every_camera_it_names():
    """The review's fifth pass, major, and its question about `auto`: a scenario's labels are PLACEMENT labels — where
    its evaluator runs — and a grant on a label matched them: `PUT /auto/scenarios/lobby` with `then: output unit 12`
    was 200 for somebody whose `POST /requests` on camera 12 is 403. A scenario is the cameras it watches and acts on
    (`scenario_cams`): an edit or a delete needs the route's capability on every one of them, old and new; a trigger
    with no unit is any camera's, which only a grant on the whole cluster covers."""
    box = Box()
    access = Tokens({"lobby": [("admin", None, ("lobby",))], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["lobby"]}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/2.mp4"}, token="admin")[0] == 201
        scenario = {"name": "lobby", "labels": ["lobby"],
                    "when": [{"sub": "vms", "kind": "motion", "unit": "1"}],
                    "then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", scenario, token="admin")[0] == 201
        assert _call(base, "POST", "/requests", {"unit": "2", "action": "output", "port": 1}, token="lobby")[0] == 403
        other = [{"sub": "vms", "action": "output", "unit": "2", "port": 1}]
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"then": other}, token="lobby")[0] == 403   # camera 2: not hers
        anyone = [{"sub": "vms", "kind": "motion"}]
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"when": anyone}, token="lobby")[0] == 403  # every camera: the cluster's
        assert mounts["auto"].unit("lobby")["then"][0]["unit"] == "1"
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"within": 0, "then": [{**scenario["then"][0], "port": 2}]},
                     token="lobby")[0] == 200                                                      # her camera, before and after
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"then": other}, token="admin")[0] == 200
        assert _call(base, "DELETE", "/auto/scenarios/lobby", token="lobby")[0] == 403              # it acts on camera 2 now
    finally:
        srv.shutdown()


def test_a_deleted_recordings_name_comes_back_only_for_its_own_camera():
    """The review's fifth pass, major: DELETE «1-cloud» of camera 1, then POST `{"name": "1-cloud", "cam": "2"}` — and a
    viewer of camera 2 alone got camera 1's frames from `GET /export/2`, because footage is found by the recording's
    name. The rule: a tombstone keeps its camera, and the name comes back for that camera only — for another it is
    400, and so is the PUT that asked for it, whose refusal no longer suggests the trick."""
    from tests.conftest import door, footage, store
    box = Box()
    access = Tokens({"two": [("view", "2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    st = store()
    t = box.wall()
    footage(st, "1-cloud", 1, t - 900, t - 300)                       # what «1-cloud» recorded: camera 1's footage
    rdoor = door(box, st)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "1"}, token="admin")[0] == 201
        code, body = _call(base, "PUT", "/rec/recordings/1-cloud", {"cam": "2"}, token="admin")
        assert code == 400 and "another name" in body["detail"] and "delete it" not in body["detail"]
        assert _call(base, "DELETE", "/rec/recordings/1-cloud", token="admin")[0] == 200
        code, body = _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "2"}, token="admin")
        assert code == 400 and "cam 1's" in body["detail"]
        assert _call(base, "GET", f"/export/2?from={t - 900}&to={t - 300}", token="two")[0] == 404   # nothing of camera 1's
        assert _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "1"}, token="admin")[0] == 201   # its own camera
        assert rec.unit("1-cloud")["cam"] == "1"
    finally:
        rdoor.shutdown(); srv.shutdown()


def test_forty_addresses_flooding_the_emergency_door_do_not_keep_the_operator_on_the_box_out():
    """The review's fifth pass, Ч-M3's remainder: a refusal by the pace spends no try of the address, so forty addresses
    — each inside its five a window — keep every turn of the pace taken, and the operator competes with them for each.
    The box has a lane of its own: an hour of such a flood, simulated on the pace's clock, and the operator at the box
    gets in at once, every time; guessing from the network is exactly as slow as it was.

    Who is "at the box" (the review's sixth pass, minor): a caller that came through the console's unix socket
    (`is_local`: a peer named `unix…`) — not a TCP peer of 127.0.0.1, which behind a proxy on the box is every caller
    there is, and which any process on the box can be."""
    from w2cplatform.access import is_local
    clock = {"t": 1000.0}
    Gate.forget_glass()
    real = Gate._glass_clock, Gate._glass_sleep
    Gate._glass_clock = staticmethod(lambda: clock["t"])
    Gate._glass_sleep = staticmethod(lambda s: None)               # every attempt in flight at once: nobody waits out a turn
    box = Box()
    gate = Gate(box.vars, box.wall, impl=Tokens({}))

    def guess(addr, pw="wrong", local=False):
        try:
            gate.open_glass("x", "testing", pw, addr=addr, local=local)
            return 200
        except Denied as e:
            return e.status
    checked, turned_away, operator = 0, 0, []
    try:
        for second in range(3600):                                 # an hour; the forty try as often as they are let
            clock["t"] += 1; box.wall.advance(1)
            for i in range(40):
                code = guess(f"198.51.100.{i}")
                checked += code == 403
                turned_away += code == 429
            if second % 300 == 150:                                # the operator at the box, every five minutes
                operator.append(guess("unix:uid=0", "open-sesame", local=True))
        assert operator == [200] * 12                              # in, every time, while the flood goes on
        interval = 60 / Gate.GLASS_RATE                            # the network's pace: as slow as it was
        assert checked <= 3600 / interval + Gate.GLASS_BURST + Gate.GLASS_WAIT / interval + 1, checked
        assert turned_away > checked                               # …and the flood saturated it
        assert guess("198.51.100.200", "open-sesame") == 429       # from the network, the right one still competes
        assert is_local("unix") and is_local("unix:uid=0")         # through the socket: the box
        assert not any(is_local(a) for a in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "10.0.0.5"))   # no TCP peer is
    finally:
        Gate._glass_clock, Gate._glass_sleep = staticmethod(real[0]), staticmethod(real[1])
        Gate.forget_glass()


def test_a_camera_without_a_recording_does_not_read_another_cameras_tree_by_its_name():
    """The review's fourth pass, major: a camera with no recording of its own falls back to the tree named after it —
    and a recording NAMED «1» that records camera 2 made `/timeline/1` and `/export/1` serve camera 2's frames to camera
    1's viewers, journalled as camera 1, and `POST /backfill` for camera 1 wrote into camera 2's tree. The fallback is
    taken only when no recording of that name says it is another camera's — alive or deleted; a keep likewise.
    And a backfill asks for a day at most, a keep for a week."""
    from tests.conftest import door, footage, store
    from vms import keeps
    box = Box()
    access = Tokens({"guard": [("edit", "1", ())], "other": [("edit", "2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    st = store()
    t = box.wall()
    footage(st, "1", 1, t - 900, t - 300)                              # the tree «1»: camera 2's footage
    rdoor = door(box, st)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "2"}, token="admin")[0] == 201
        code, spans = _call(base, "GET", f"/timeline/1?from={t - 1000}&to={t}", token="guard")
        assert code == 200 and not [s for s in (spans if isinstance(spans, list) else spans["segments"]) if s.get("recording")]
        assert _call(base, "GET", f"/export/1?from={t - 900}&to={t - 300}", token="guard")[0] == 404
        assert _call(base, "GET", f"/timeline/2?from={t - 1000}&to={t}", token="other")[0] == 200   # it IS camera 2's
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 900, "to": t - 300}, token="guard")[0] == 404
        assert not box.vars.list("rec/requests/")
        rec.delete("1")                                                 # deleted, the tombstone still says whose it was
        assert _call(base, "GET", f"/export/1?from={t - 900}&to={t - 300}", token="guard")[0] == 404
        assert _call(base, "POST", "/rec/keeps", {"cam": "1", "from": t - 900, "to": t - 300}, token="guard")[0] == 201
        assert [k.recordings for k in keeps.declared(box.vars) if k.cam == "1"] == [()]

        code, body = _call(base, "POST", "/backfill", {"cam": "2", "from": t - 40 * 365 * 86400, "to": t}, token="other")
        assert code == 400 and "86400" in body["detail"]                 # a day at most
        code, body = _call(base, "POST", "/rec/keeps", {"cam": "2", "from": t - 30 * 86400, "to": t}, token="other")
        assert code == 400 and "7 days" in body["detail"]                # a week at most
    finally:
        rdoor.shutdown(); srv.shutdown()


def test_a_backfill_is_two_finite_numbers_a_handful_at_a_time_and_a_line():
    """The review's fifth pass, minor: `POST /backfill` with `NaN` broke the connection with no reply (`NaN` passes
    `t1 <= t0`, and then `int()` fails); nothing bounded how many day-long asks one person filed; and an ask left no
    line. Now: 400 for anything but two finite numbers; at most `BACKFILLS_OPEN` of one person's asks waiting for a
    recorder (the same range again is the same ask); and `archive.backfill.asked` names who, which camera, which
    recording and which minutes."""
    from vms import console as vc
    box = Box()
    access = Tokens({"guard": [("edit", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    t = box.wall()
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1"}, token="admin")[0] == 201
        for bad in ({"cam": "1", "from": float("nan"), "to": t}, {"cam": "1", "from": t - 60, "to": float("inf")},
                    {"cam": "1", "from": "soon", "to": t}):
            assert _call(base, "POST", "/backfill", bad, token="guard")[0] == 400, bad
        asks = [_call(base, "POST", "/backfill", {"cam": "1", "from": t - 3600 * (i + 1), "to": t - 3600 * i}, token="guard")[0]
                for i in range(vc.BACKFILLS_OPEN)]
        assert asks == [202] * vc.BACKFILLS_OPEN
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 3600, "to": t}, token="guard")[0] == 202   # the same ask
        code, body = _call(base, "POST", "/backfill", {"cam": "1", "from": t - 9e4, "to": t - 8.9e4}, token="guard")
        assert code == 429 and "guard has 7" in body["detail"]
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 9e4, "to": t - 8.9e4}, token="admin")[0] == 202  # another person
        lines = [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]
                 if e["kind"] == "archive.backfill.asked"]
        assert len(lines) == vc.BACKFILLS_OPEN + 2 and lines[0]["user"] == "guard" and lines[0]["target"] == "1" \
            and lines[0]["recording"] == "1"
    finally:
        srv.shutdown()


def test_forty_backfills_asked_at_once_are_seven_and_an_ask_nobody_can_answer_is_refused():
    """The review's sixth pass, minor — a run: forty POSTs at once left fifteen rows where `BACKFILLS_OPEN` is seven.
    The bound was a count of rows read before the write, and requests in flight all counted the same ones. A person's
    open asks are one row now, changed by CAS (`rec/requests/asks-<sha256 of the person, 16 hex>`): forty at once are seven asks and
    thirty-three refusals, never an eighth. And an ask no recorder could ever answer — a range of milliseconds, a
    range that has not happened yet — is refused instead of holding a place for good."""
    import threading
    from vms import console as vc
    box = Box()
    access = Tokens({"guard": [("edit", "1", ())], "admin": [("admin", None, ())]})
    was = os.environ.get("CONSOLE_PER_ADDRESS")
    os.environ["CONSOLE_PER_ADDRESS"] = "64"                          # forty at once from one address: the door lets them in
    ctl, rec, m, srv, base = _console(box, access)
    t = box.wall()
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1"}, token="admin")[0] == 201
        for bad, why in (({"from": t - 60, "to": t - 59.5}, "at least"), ({"from": t + 3600, "to": t + 7200}, "from now"),
                         ({"from": t - 60, "to": t + 600}, "from now")):
            code, body = _call(base, "POST", "/backfill", {"cam": "1", **bad}, token="guard")
            assert code == 400 and why in body["detail"], (bad, body)
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 60, "to": t + 30}, token="admin")[0] == 202   # two clocks apart: taken
        codes, lock = [], threading.Lock()

        def ask(i):
            code = _call(base, "POST", "/backfill", {"cam": "1", "from": t - 3600 * (i + 2), "to": t - 3600 * (i + 1)}, token="guard")[0]
            with lock:
                codes.append(code)
        threads = [threading.Thread(target=ask, args=(i,)) for i in range(40)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(30)
        mine = [k for k in box.vars.list(REC_SPEC.sub.requests_prefix())
                if (box.vars.get(k)[0] or {}).get("by") == "guard" and "from" in box.vars.get(k)[0]]
        assert sorted(codes) == [202] * vc.BACKFILLS_OPEN + [429] * (40 - vc.BACKFILLS_OPEN), sorted(codes)
        assert len(mine) == vc.BACKFILLS_OPEN                                              # never an eighth row
        # a place comes back when its ask is answered: the recorder fetched one, the console cleared its row
        box.vars.delete(mine[0])
        box.wall.advance(vc.ASK_SETTLE + 1)
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 9e4, "to": t - 8.9e4}, token="guard")[0] == 202
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 9.9e4, "to": t - 9.8e4}, token="guard")[0] == 429
    finally:
        srv.shutdown()
        os.environ.pop("CONSOLE_PER_ADDRESS", None)
        if was is not None:
            os.environ["CONSOLE_PER_ADDRESS"] = was


def _get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {})) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_a_segment_is_signed_for_what_the_device_holds_and_the_door_streams_it_a_piece_at_a_time():
    """The review's fifth pass, major: `/segment` signed any interval, and the holder's door read it in one `read` into
    one buffer — 1000 s of a 100 kB/s card was 100 MB in the process holding every camera of its server. The console
    cuts the interval to the coverage the holder announces and holds it to `SEGMENT_MAX` before it signs (nothing of
    the device's there: 404; longer: 400). The door asks the device for `PLAYBACK_PIECE` seconds at a time, one session
    at a time, and sends each piece as it comes, in chunks — the last one only when every piece went."""
    import http.client
    from urllib.parse import parse_qs, urlsplit
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"viewer": [("view", "1", ()), ("view", "2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    dev = FakeDevice("acme/10.0.0.50", channels=["1", "2"], coverage={"1": (0.0, 1000.0), "2": (0.0, 10000.0)},
                     max_playbacks=2, bps=20000)
    pieces = []
    read = dev.read
    dev.read = lambda sid: (lambda b: (pieces.append((len(b), len(dev.open))), b)[1])(read(sid))
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  archive_root=box.archive, device_factory=lambda k: dev)
    w.heartbeat_once()
    door = w.serve_playback("127.0.0.1", 0)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})          # gated: the console signs
        code, body = _call(base, "GET", "/segment?cam=1&from=0&to=86400", token="viewer")
        assert code == 200, body
        q = {k: v[0] for k, v in parse_qs(urlsplit(body["playback"]).query).items()}
        assert (q["from"], q["to"]) == ("0.000", "1000.000")                     # a day asked: what the card holds, signed
        assert _call(base, "GET", "/segment?cam=1&from=5000&to=6000", token="viewer")[0] == 404
        code, body2 = _call(base, "GET", "/segment?cam=2&from=0&to=1e12", token="viewer")
        assert code == 400 and "3600" in body2["detail"]                          # longer than an export: not signed at all

        u = urlsplit(body["playback"])
        c = http.client.HTTPConnection(u.hostname, u.port, timeout=30)
        c.request("GET", f"{u.path}?{u.query}")
        r = c.getresponse()
        assert r.status == 200 and r.getheader("Transfer-Encoding") == "chunked" and r.getheader("Content-Length") is None
        total = len(r.read())
        assert total == 1000 * 20000                                               # all of it, through the stream
        assert max(n for n, _ in pieces) <= w.PLAYBACK_PIECE * 20000                # never more than a piece at once
        assert len(pieces) >= 1000 / w.PLAYBACK_PIECE and max(o for _, o in pieces) == 1   # one session at a time
        assert not dev.open                                                          # and every one closed
    finally:
        door.shutdown(); srv.shutdown()


def test_the_doors_expiry_forgives_clocks_a_little_apart_and_names_the_difference_when_they_are_not():
    """The review's fifth pass, minor: the address's expiry is the console's clock, read by the holder's — more than
    `TTL` apart and every address was "expired" the moment it was made, with nothing to say why. The address carries
    when it was signed: `SKEW` apart either way is forgiven; further, the refusal names the difference as the door
    measured it, and an address signed in the door's future is refused too (it would live longer than `TTL`)."""
    from vms import playback as pb
    key = pb.new_key()

    def check(console_now, door_now):
        q = {k: v[0] for k, v in __import__("urllib.parse").parse.parse_qs(
            pb.signed_query(key, "7", 100, 200, "anna", console_now)).items()}
        try:
            return pb.check_signed(key, "7", q, door_now)
        except PermissionError as e:
            return str(e)
    assert check(1000, 1000) == "anna"
    assert check(1000, 1000 - pb.SKEW + 1) == "anna"                          # the console a little ahead
    assert check(1000, 1000 + pb.TTL + pb.SKEW - 1) == "anna"                 # …or behind, or a viewer a little late
    ahead = check(1000, 1000 - 400)
    assert "400 s ahead" in ahead and "NTP" in ahead                          # the console 400 s ahead of the door
    behind = check(1000, 1000 + 700)
    assert "expired" in behind and "700 s" in behind and "NTP" in behind      # …or 700 s behind it: named, not a riddle
    q = {k: v[0] for k, v in __import__("urllib.parse").parse.parse_qs(pb.signed_query(key, "7", 100, 200, "anna", 1000)).items()}
    assert "did not sign" in str(_raises(lambda: pb.check_signed(key, "7", {k: v for k, v in q.items() if k != "at"}, 1000)))
    q["at"] = "1100"
    assert "does not match" in str(_raises(lambda: pb.check_signed(key, "7", q, 1000)))   # `at` is under the signature


def _raises(fn):
    try:
        fn()
    except Exception as e:                                                     # noqa: BLE001
        return e
    raise AssertionError("did not raise")


def test_the_devices_own_door_opens_only_to_what_the_console_signed():
    """The review's fourth pass, blocker 4. The console checked `view` and journalled `archive.read`, and handed the
    browser the holder's door as it is; the door asked nobody, so a viewer of camera 1 edited `1` into `2` and took
    camera 2's card. Now the console signs what it allowed — camera, minutes, expiry, viewer — with the door's own key
    from its heartbeat, and in a gated cluster the door serves only that: the camera edited, the minutes stretched,
    the address unsigned or expired is 403 and a line; the signed one is 200 and a line naming the viewer. A process
    of the cluster reads by a per-camera capability derived from the same key, and an open cluster's door is open."""
    from vms.playback import process_url
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    from w2cplatform.console import holder_of
    box = Box()
    access = Tokens({"viewer": [("view", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    dev = FakeDevice("acme/10.0.0.50", channels=["1", "2"], coverage={"1": (0.0, 1000.0), "2": (0.0, 1000.0)}, max_playbacks=4)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  archive_root=box.archive, device_factory=lambda k: dev)
    w.heartbeat_once()
    door = w.serve_playback("127.0.0.1", 0)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
        bare = f"http://127.0.0.1:{door.server_address[1]}/playback/2?from=0&to=5"
        assert _get(bare)[0] == 200                                    # no key set in the store: open, as the console is

        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})   # in a domain: the door asks
        code, body = _call(base, "GET", "/segment?cam=1&from=0&to=5", token="viewer")
        assert code == 200 and "&sig=" in body["playback"] and "&v=viewer" in body["playback"], body
        url = body["playback"]
        assert _get(url)[0] == 200                                     # what the console signed
        assert _get(url.replace("/playback/1?", "/playback/2?"))[0] == 403          # the camera edited
        assert _get(url.replace("to=5.000", "to=900.000"))[0] == 403               # the minutes stretched
        assert _get(url.replace("v=viewer", "v=admin"))[0] == 403                  # somebody else's name
        assert _get(bare)[0] == 403                                               # unsigned
        assert _call(base, "GET", "/segment?cam=2&from=0&to=5", token="viewer")[0] == 403   # the console's gate, as before

        found = holder_of(box.objects, "vms/", "2", box.wall(), field="playback_url")
        cap = process_url(found)                                     # the recorder's and the survey's address for camera 2
        assert _get(f"{cap}?from=0&to=5")[0] == 200
        assert _get(f"{cap.replace('/playback/2/', '/playback/1/')}?from=0&to=5")[0] == 403   # one camera's capability is not another's

        from vms import playback as pb
        box.wall.advance(pb.TTL + pb.SKEW + 1)
        assert _get(url)[0] == 403                                   # five minutes on (and the clocks' grace): ask again

        audit = EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]
        at_door = [e for e in audit if e.get("unit") == "door-w-1"]
        reads = [(e["user"], e["target"]) for e in at_door if e["kind"] == "archive.read"]
        assert reads and set(reads) == {("viewer", "1")}             # the door says the address was USED, and by whom
        assert sum(e["kind"] == "access.denied" for e in at_door) == 6
        handed = [(e["user"], e["target"], e["source"], bool(e.get("until"))) for e in audit
                  if e["kind"] == "archive.read" and e.get("unit") == "console"]
        assert handed == [("viewer", "1", "device", True)]
    finally:
        door.shutdown(); srv.shutdown()


# -- the sixth pass: a field that points at another unit ---------------------------------------------------------------
def test_a_recording_is_homed_on_a_card_only_by_whoever_may_act_on_that_cards_camera_and_only_its_own():
    """The review's sixth pass, major: `PUT /rec/recordings/1-b {"home": "card2"}` with `admin` on camera 1 was 200 —
    and the card in camera 2, whose recorder writes its own camera's ring whatever the row says, wrote camera 2's
    frames into camera 1's recording, out of its own budget. An edge volume names the camera whose card it is
    (`cam`); the gate asks for the route's capability on that camera too, before and after the edit
    (`recording_cams`); and whoever holds both is refused by the controller: a card holds its own camera's
    recordings (`volumes.refuse_recording`). The same reach through a scenario's `record` with `archive: card2` is
    asked about at the gate, and refused when the request is turned into a row. A disk or a bucket is no camera's."""
    from vms import jobs, volumes
    box = Box()
    access = Tokens({"one": [("admin", "1", ())], "both": [("admin", "1", ()), ("admin", "2", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    rec = mounts["rec"]
    card = {"name": "card2", "kind": "edge", "server": "cam-2", "url": "/media/sd", "quota_bytes": 1 << 30}
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        code, body = _call(base, "POST", "/rec/volumes", card, token="admin")
        assert code == 400 and "`cam`" in body["detail"]                                     # a card says whose it is
        assert _call(base, "POST", "/rec/volumes", {**card, "cam": "2"}, token="admin")[0] == 201
        disks = {"name": "disks", "kind": "local", "server": "srv-1", "url": "/data/v", "quota_bytes": 1 << 30}
        assert _call(base, "POST", "/rec/volumes", disks, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/volumes", {**disks, "name": "d2", "cam": "2"}, token="admin")[0] == 400   # a disk is no camera's
        assert _call(base, "POST", "/rec/recordings", {"name": "1-b", "cam": "1"}, token="admin")[0] == 201
        assert _call(base, "PUT", "/rec/recordings/1-b", {"home": "card2"}, token="one")[0] == 403      # camera 2's card: not hers
        code, body = _call(base, "PUT", "/rec/recordings/1-b", {"home": "card2"}, token="both")
        assert code == 400 and "card in camera 2" in body["detail"]                           # hers too — and still not camera 1's place
        assert _call(base, "POST", "/rec/recordings", {"name": "1-c", "cam": "1", "home": "card2"}, token="admin")[0] == 400
        assert not rec.unit("1-b").get("home") and rec.unit("1-c") is None
        assert _call(base, "PUT", "/rec/recordings/1-b", {"home": "disks"}, token="one")[0] == 200       # a disk: her recording, her say
        assert _call(base, "POST", "/rec/recordings", {"name": "2-card", "cam": "2", "home": "card2"}, token="admin")[0] == 201
        assert _call(base, "PUT", "/rec/recordings/2-card", {"retention_days": 3}, token="one")[0] == 403   # camera 2's, as it is
        # the card declared again as another camera's, a recording homed on it: refused
        code, body = _call(base, "POST", "/rec/volumes", {**card, "cam": "1"}, token="admin")
        assert code == 400 and "2-card" in body["detail"]

        # the same reach through a scenario: `record` into an archive that is another camera's card
        record = lambda **more: [{"sub": "rec", "action": "record", "cam": "1", "minutes": 10, **more}]
        scenario = {"name": "keep", "when": [{"sub": "vms", "kind": "motion", "unit": "1"}], "then": record()}
        assert _call(base, "POST", "/auto/scenarios", scenario, token="admin")[0] == 201
        assert _call(base, "PUT", "/auto/scenarios/keep", {"then": record(archive="disks")}, token="one")[0] == 200
        assert _call(base, "PUT", "/auto/scenarios/keep", {"then": record(archive="card2")}, token="one")[0] == 403
        # …and what a request for it becomes, whoever filed it: no recording, and the request gone
        rec.vars.put(rec.sub.request_key("s-1"), {"action": "record", "cam": "1", "minutes": "10", "archive": "card2"})
        assert jobs.record_on_request(rec, box.wall()) == 0 and rec.unit("1-auto") is None
        assert rec.vars.get(rec.sub.request_key("s-1"))[0] is None
        assert volumes.volume_named(box.vars, "card2").cam == "2"
    finally:
        srv.shutdown()


def test_a_cards_recorder_does_not_record_another_cameras_recording_even_when_the_row_is_there():
    """The other end of the same finding: the row is refused at the door now — and a row that is there all the same,
    written before the rule or past it, is not recorded by the card's recorder (`CardRecorder.enrich`): its status
    says whose card this is, and the card's own recording goes on."""
    from vms.config import REC_SPEC
    from tests.test_camera_card import _camera, _film, _status
    box, rec, ring, act, rec_ctl = _camera(when=None)
    assert rec.card_cam == "1" and "1-card" in rec.reconciler.actual
    row = REC_SPEC.new_row("2-b", {"name": "2-b", "cam": "2", "home": "card"})
    box.vars.put("rec/recordings/2-b", REC_SPEC.items(row))                              # past the door
    rec_ctl.ensure_placed()
    rec.reconcile_once(); rec.heartbeat_once()
    st = _status(rec, "2-b")
    assert st["phase"] != "running" and "2-b" not in rec.reconciler.actual
    assert "card in camera 1" in st["why"] and "camera 2's" in st["why"]
    _film(ring, box.wall(), box.wall() + 10, act=act)
    assert act.stats("1-card")["samples_written"] == 20 and act.stats("2-b").get("samples_written", 0) == 0


def test_a_cameras_source_is_moved_only_by_whoever_administers_every_camera_of_the_device_and_is_nobody_elses():
    """The review's sixth pass, major: `PUT /cameras/1 {"source": "…/ch/2"}` with `admin` on camera 1 was 200 — the
    credentials are the device's, so the holder opened channel 2 as camera 1, and camera 1's viewers and archive got
    camera 2's picture. A change of device or channel is asked about on every camera of the device it leaves and of
    the device it moves to (`source_cams`); a channel is one camera, for anybody (`volumes.refuse_camera`); an edit
    that leaves the source where it is asks for nothing more. `ref` — the name the domain knows the camera by — is
    the cluster's to change, and one camera's."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"one": [("admin", "1", ())], "both": [("admin", "1", ()), ("admin", "2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.60/ch/1"}, token="admin")[0] == 201   # camera 3
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}2"}, token="one")[0] == 403          # camera 2's channel
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}7"}, token="one")[0] == 403          # a free one, and still camera 2's device
        code, body = _call(base, "PUT", "/cameras/1", {"source": f"{nvr}2"}, token="both")
        assert code == 400 and "camera 2 is that source already" in body["detail"]                      # every camera of the device hers: still one camera
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}2/"}, token="admin")[0] == 400       # the same channel, spelt otherwise
        assert _call(base, "PUT", "/cameras/1", {"source": "driverpack://acme/10.0.0.60/ch/5"}, token="both")[0] == 403   # camera 3's device
        assert ctl.camera(1)["source"] == f"{nvr}1"
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}1", "name": "gate"}, token="one")[0] == 200   # nothing moved: her camera
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}7"}, token="both")[0] == 200          # a free channel, every camera of it hers
        code, body = _call(base, "POST", "/cameras", {"source": f"{nvr}7"}, token="admin")
        assert code == 400 and "camera 1 is that source already" in body["detail"]
        assert _call(base, "DELETE", "/cameras/1", token="admin")[0] == 200
        assert _call(base, "POST", "/cameras", {"source": f"{nvr}7"}, token="admin")[0] == 201           # a deleted camera holds no channel
        # `ref`: the cluster's to change, and one camera's
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2"}, token="both")[0] == 403
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2"}, token="admin")[0] == 200
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2", "name": "yard"}, token="both")[0] == 200   # unchanged: hers
        code, body = _call(base, "PUT", "/cameras/3", {"ref": "SN-2"}, token="admin")
        assert code == 400 and "`ref` SN-2 already" in body["detail"]
    finally:
        srv.shutdown()


def test_every_field_of_every_spec_that_points_at_something_else_is_asked_about():
    """The sixth pass's complaint was the class, not the two fields: a field that points at another unit, volume or
    device, and a gate that asks only about the camera the row is about. Every field of every subsystem's spec is
    named here — what it points at, or that it points at nothing — so a field added to a spec fails this test until
    somebody has said which it is; and for each one that points, the console built by `make_console` has the hook
    that asks (`cams_of`, `moved_cams`), or the controller keeps the field fixed."""
    from vms.auto import AutoController
    from vms.config import AUTO_SPEC, DET_SPEC, DETJOB_SPEC, LIVE_SPEC, SURVEY_SPEC
    from vms.jobs import DetJobController
    FIXED, GATE, MOVED, RULE, PLAIN = "fixed at creation", "cams_of", "moved_cams", "refused by the controller", None
    points = {
        ("vms", "source"): (MOVED, RULE),      # a channel of a device: every camera of both devices; one channel, one camera
        ("vms", "ref"): (MOVED, RULE),         # the domain's name for it: the cluster's grant; one name, one camera
        ("rec", "cam"): (FIXED, GATE),         # whose footage
        ("rec", "home"): (GATE, RULE),         # a volume; a camera's card is that camera's
        ("det", "cam"): (FIXED,),
        ("detjob", "cam"): (FIXED, GATE),
        ("detjob", "rec"): (FIXED, GATE, RULE),   # a recording: of the same camera
        ("survey", "cam"): (FIXED,),
        ("live", "cam"): (FIXED,),             # the row's own name
        ("auto", "when"): (GATE,),             # the units it watches
        ("auto", "then"): (GATE,),             # the units it acts on, and the card a `record` writes to
    }
    plain = {
        "vms": {"name", "enabled", "events_retention_days", "alarms_retention_days", "priority", "labels", "folders",
                "alarms", "cred_username", "cred_secret", "live", "kind"},
        "rec": {"name", "retention_days", "enabled", "labels", "until", "min_depth_days", "when"},
        "det": {"name", "kind", "params", "mask", "enabled", "labels", "alarms", "until"},
        "detjob": {"name", "kind", "params", "mask", "from", "to", "state", "ended", "labels"},
        "survey": {"name", "kind", "params", "mask", "start", "keep", "pre", "post", "join", "enabled", "labels"},
        "live": {"labels", "grace"},
        "auto": {"name", "within", "rate_per_minute", "valid_for", "enabled", "labels"},
    }
    specs = {s.name: s for s in (SPEC, REC_SPEC, DET_SPEC, DETJOB_SPEC, SURVEY_SPEC, LIVE_SPEC, AUTO_SPEC)}
    for name, spec in specs.items():
        named = {f for (s, f) in points if s == name} | plain[name]
        assert set(spec.fields) == named, (name, sorted(set(spec.fields) ^ named))     # a new field: say which it is

    box = Box()
    acl = [a for s in specs.values() for a in s.acl_console()]
    vars_ = box.vars.as_writer("console", acl)
    ctl = VmsController(vars_, box.objects, wall=box.wall)
    mounts = {n: SpecController(specs[n], vars_, box.objects, wall=box.wall) for n in ("rec", "det", "survey")}
    mounts.update(detjob=DetJobController(vars_, box.objects, wall=box.wall), auto=AutoController(vars_, box.objects, wall=box.wall))
    m = make_console(ctl, box.archive, box.wall, live_ctl=SpecController(LIVE_SPEC, vars_, box.objects, wall=box.wall),
                     mounts=mounts, index=EventIndex(box.archive, "srv-1", wall=box.wall))
    consoles = {"vms": m.root, **m.mounts}
    from w2cplatform.spec import REFUSE
    for (sub, field), how in points.items():
        con = consoles[sub]
        if GATE in how:
            assert con.cams_of is not None, (sub, field)
        if MOVED in how:
            assert con.moved_cams is not None, (sub, field)
        if RULE in how:
            assert sub in REFUSE or type(con.ctl) is not SpecController, (sub, field)   # a rule of the subsystem's own
        if FIXED in how and field == "cam":
            assert "cam" in con.spec.fields and con.labels_of is not None, (sub, field)   # the gate reads the camera's own labels


def test_a_command_to_a_device_is_asked_of_every_camera_of_the_device_by_hand_and_through_a_scenario():
    """The review's seventh pass, major — a run: a guard with `edit` on camera 1 of a sixteen-channel recorder sent
    `output` to ports 1–4 and `preset 5`: 202, and the device did all of it — the lock of camera 2's zone among them.
    The holder performs a command on the DEVICE (`perform`: `dev.output(port)`, `dev.preset(n)`), and nothing a device
    says of itself binds a relay or a preset to a channel. So a command needs `edit` on every camera of the device
    (`command_cams`, `body_cams`) — and a scenario that commands it, `admin` on every one (`scenario_cams`); a camera
    that is its device's only channel asks for nothing more than it did."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"guard": [("edit", "1", ())], "both": [("edit", "1", ()), ("edit", "2", ())],
                     "lobby": [("admin", "1", ())], "lobbies": [("admin", "1", ()), ("admin", "2", ())],
                     "three": [("edit", "3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201   # its own device
        for cmd in ({"unit": "1", "action": "output", "port": 3}, {"unit": "1", "action": "preset", "n": 5}):
            assert _call(base, "POST", "/requests", cmd, token="guard")[0] == 403, cmd   # camera 2 is on that device
            assert _call(base, "POST", "/requests", cmd, token="both")[0] == 202, cmd    # every camera of it hers
        assert box.vars.list("vms/requests/") and all(box.vars.get(k)[0]["by"] for k in box.vars.list("vms/requests/"))
        assert _call(base, "POST", "/requests", {"unit": "3", "action": "output", "port": 1}, token="three")[0] == 202
        # through a scenario: the same reach
        acting = {"name": "gate", "when": [{"sub": "vms", "kind": "motion", "unit": "1"}],
                  "then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", acting, token="admin")[0] == 201
        assert _call(base, "PUT", "/auto/scenarios/gate", {"within": 0}, token="lobby")[0] == 403   # it acts on camera 2's device too
        assert _call(base, "PUT", "/auto/scenarios/gate", {"within": 0}, token="lobbies")[0] == 200
        assert _call(base, "DELETE", "/auto/scenarios/gate", token="lobby")[0] == 403
    finally:
        srv.shutdown()


def test_one_device_under_another_spelling_is_one_device_to_every_right_asked_of_it():
    """The review's eighth pass, major — a run: with `admin` on a file camera of her own, a user set its `source` to
    `driverpack://ACME/10.0.0.50/ch/2` (or `:80`, `10.0.0.50.`) — channel 2 of a recorder whose cameras were not hers:
    200, and then her `output` to port 1 was 202, the recorder pulsed. `device_of` took the address as typed. It is
    canonical now — scheme and host in lower case, no trailing dot, an address in the form the resolver dials (`012.0.0.50`
    is `10.0.0.50`), no default port, no credentials — so every spelling is the recorder, for the move (`source_cams`), for the command
    (`device_cams`) and for "one channel, one camera" (`refuse_camera`, `…/ch/02` being `…/ch/2`). A command carries the
    device its rights were asked on (`device`)."""
    from vms.config import channel_key, device_of
    nvr = "driverpack://acme/10.0.0.50/ch/"
    for spelt in ("driverpack://ACME/10.0.0.50/ch/2", "DRIVERPACK://acme/10.0.0.50:80/ch/2", "driverpack://acme/10.0.0.50./ch/2",
                  "driverpack://acme/012.0.0.50/ch/2", "driverpack://acme/10.50/ch/2", "driverpack://acme/[::ffff:10.0.0.50]/ch/2",
                  "driverpack://acme/admin:pw@10.0.0.50:0080/ch/2"):
        assert device_of(spelt) == "acme/10.0.0.50", spelt
    assert device_of("driverpack://acme/10.0.0.050/ch/2") == "acme/10.0.0.40"               # octal, as the resolver reads it
    assert device_of("driverpack://acme/10.0.0.50:8000/ch/2") == "acme/10.0.0.50:8000"       # another port: another door
    assert device_of("rtsp://u:p@CAM-7.local.:554/Stream1") == "rtsp://cam-7.local/Stream1"  # the path is the vendor's, as typed
    assert device_of("driverpack://file/Lobby.mp4") == "file/Lobby.mp4"                         # a file's name, as typed
    assert channel_key(f"{nvr}02") == channel_key("driverpack://acme/10.0.0.50/CH/2") == "2"
    box = Box()
    access = Tokens({"three": [("admin", "3", ())], "guard": [("edit", "3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201   # hers
        for spelt in ("driverpack://ACME/10.0.0.50/ch/2", "driverpack://acme/10.0.0.50:80/ch/9",
                      "driverpack://acme/10.0.0.50./ch/9", "driverpack://acme/012.0.0.50/ch/9"):
            assert _call(base, "PUT", "/cameras/3", {"source": spelt}, token="three")[0] == 403, spelt   # the recorder's
        code, body = _call(base, "PUT", "/cameras/3", {"source": "driverpack://ACME/10.0.0.50.:80/ch/02"}, token="admin")
        assert code == 400 and "camera 2 is that source already" in body["detail"], (code, body)        # one channel
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://ACME/10.0.0.50:80/ch/9"}, token="admin")[0] == 200
        for cmd in ({"unit": "3", "action": "output", "port": 1}, {"unit": "3", "action": "preset", "n": 2}):
            assert _call(base, "POST", "/requests", cmd, token="guard")[0] == 403, cmd   # camera 3 is the recorder's now
        assert _call(base, "POST", "/requests", {"unit": "1", "action": "output", "port": 1, "id": "r-1"}, token="admin")[0] == 202
        assert box.vars.get("vms/requests/r-1")[0]["device"] == "acme/10.0.0.50"       # what the rights were asked on
        for bad in ('r"2', "r|2", "r\n2"):                                               # a name's rule (`doors.unnamable`)
            assert _call(base, "POST", "/requests", {"unit": "1", "action": "output", "port": 1, "id": bad}, token="admin")[0] == 400
    finally:
        srv.shutdown()


def test_a_dns_name_and_its_address_are_one_device_once_a_holder_has_opened_it():
    """The same finding, the part syntax cannot say: `nvr50.local` and `10.0.0.50` are two keys and one recorder. The
    holder learns what the device IS when it opens it (`identity` — a serial number, a MAC; `FakeDevice(identity=)`)
    and writes it into the device's row; rights and "one channel, one camera" compare by it where it is known
    (`config.one_device`). A spelling no holder has opened yet is its key alone until a holder opens it — and a holder
    that finds it is a second name of a device known already refuses it (the next test)."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"three": [("admin", "3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    devs = {"acme/10.0.0.50": FakeDevice("acme/10.0.0.50", channels=["1", "2"], relays=2, identity="ACME-SN-0042"),
            "acme/nvr50.local": FakeDevice("acme/nvr50.local", channels=["2"], relays=2, identity="ACME-SN-0042")}
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  archive_root=box.archive, device_factory=lambda k: devs.get(k))
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"     # the holder said what it is
        # Both names known — rows written before holders refused a second name, or by two holders at one moment: the
        # console compares by what the device said it is.
        box.vars.put("vms/devices/acme/nvr50.local", {**box.vars.get("vms/devices/acme/10.0.0.50")[0]})
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/9"}, token="three")[0] == 403
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/7"}, token="admin")[0] == 200
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert _call(base, "POST", "/requests", {"unit": "3", "action": "output", "port": 1}, token="three")[0] == 403
        assert _call(base, "PUT", "/cameras/3", {"name": "now hers no more"}, token="three")[0] == 200   # nothing moved
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/9"}, token="three")[0] == 403
        code, body = _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/2"}, token="admin")
        assert code == 400 and "camera 2 is that source already" in body["detail"], (code, body)
    finally:
        srv.shutdown()


def test_a_holder_refuses_a_second_name_of_a_device_it_knows_and_opens_a_first_name():
    """The owner's decision on the review's eighth pass. A camera moved onto `nvr50.local` — never opened, its key alone
    — passed the console with rights on its old device and none on the new key's cameras, and the holder opened the
    name on its next pass: the camera showed the recorder's channel, the one another camera holds as `10.0.0.50`. The
    holder now looks the identity up when it learns it (`describe_devices`): under another key it is a second name —
    no row written, the device closed, the camera not started and its status saying the name the device goes by, and a
    command to it reaches no relay. A name never seen opens, which is how identities are learned; the other name's row
    removed, this one opens too."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"two": [("admin", "2", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    devs = {"acme/10.0.0.50": FakeDevice("acme/10.0.0.50", channels=["1", "2"], relays=2, identity="ACME-SN-0042"),
            "acme/nvr50.local": FakeDevice("acme/nvr50.local", channels=["2"], relays=2, identity="ACME-SN-0042"),
            "acme/10.0.0.60": FakeDevice("acme/10.0.0.60", channels=["1"], identity="ACME-SN-0060")}
    opened: list[str] = []
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, server="srv-1",
                  archive_root=box.archive, device_factory=lambda k: opened.append(k) or devs.get(k))
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    nvr = "driverpack://acme/nvr50.local/ch/2"
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/1"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/2.mp4"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"   # a first name opens
        # The window the lesson named: `admin` on a file camera alone, moved onto the never-opened name — the console
        # lets it by (its key alone, no camera on it) — and the holder refuses the name at open.
        assert _call(base, "PUT", "/cameras/2", {"source": nvr}, token="two")[0] == 200
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert "acme/nvr50.local" not in w.devices and w.second_names["acme/nvr50.local"][0] == "acme/10.0.0.50"
        assert box.vars.get("vms/devices/acme/nvr50.local")[0] is None                    # one identity, one row
        assert not any(c.get("source") == nvr for c in act.started.values())              # no picture of the recorder
        [st] = [x for x in w.status() if str(x["id"]) == "2"]
        assert "already known as acme/10.0.0.50" in st["why"], st
        _call(base, "POST", "/requests", {"unit": "2", "action": "output", "port": 1}, token="two")
        for _ in range(3):
            w.heartbeat_once(); w.reconcile_once(); w.requests()
        assert devs["acme/10.0.0.50"].did == [] and devs["acme/nvr50.local"].did == []   # nobody's relay was pulsed
        assert opened.count("acme/nvr50.local") == 1                                    # refused once, not opened every pass
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.60/ch/1"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.60")[0]["identity"] == "ACME-SN-0060"   # another device's first name

        box.vars.delete("vms/devices/acme/10.0.0.50")                                   # the operator removes the other row
        w.heartbeat_once(); w.reconcile_once()
        assert "acme/nvr50.local" in w.devices and "acme/nvr50.local" not in w.second_names
        assert box.vars.get("vms/devices/acme/nvr50.local")[0]["identity"] == "ACME-SN-0042"
    finally:
        srv.shutdown()


def test_a_camera_moved_to_another_device_asks_for_every_camera_of_the_scenarios_that_command_it():
    """The review's eighth pass, minor: rights on an action are asked when the scenario is written, and a scenario is
    not rewritten when its camera moves. `output` on a camera that was its device's only channel, the camera then
    moved onto a recorder's channel: the scenario pulsed the RECORDER's relay — a port chosen by somebody with no right
    on it. Whoever moves a camera to another device answers for every scenario that commands it: `admin` on every
    camera such a scenario reaches (`source_cams`, `scenario_cams`). A move inside one device asks for nothing more."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"mover": [("admin", c, ()) for c in ("1", "2", "3")],
                     "both": [("admin", c, ()) for c in ("1", "2", "3", "4")], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        for f in ("3", "4"):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{f}.mp4"}, token="admin")[0] == 201
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://file/3b.mp4"}, token="mover")[0] == 200   # no scenario yet
        gate = {"name": "gate", "when": [{"sub": "vms", "kind": "motion", "unit": "4"}],
                "then": [{"sub": "vms", "action": "output", "unit": "3", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", gate, token="admin")[0] == 201
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}7"}, token="mover")[0] == 403   # the scenario watches camera 4
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}7"}, token="both")[0] == 200    # every camera of it hers
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}8"}, token="mover")[0] == 200   # within the device: as before
    finally:
        srv.shutdown()


def test_a_backfill_of_a_time_nothing_could_hold_is_refused():
    """The review's seventh pass, minor: `{"from": 0, "to": 600}` — 1970 — and even `false`/`true` were rows, each
    holding one of its person's seven places for a day. A range that ends before anything the recording shows (its
    `retention_days`) or the device holds (the coverage its holder announces) is 400; true and false are not seconds."""
    box = Box()
    access = Tokens({"guard": [("edit", "1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    t = box.wall()
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1", "retention_days": 2}, token="admin")[0] == 201
        for bad in ({"cam": "1", "from": 0, "to": 600}, {"cam": "1", "from": False, "to": True},
                    {"cam": "1", "from": t - 3 * 86400, "to": t - 2 * 86400 - 60}):
            code, body = _call(base, "POST", "/backfill", bad, token="guard")
            assert code == 400, (bad, code, body)
        assert "before anything the recording shows" in body["detail"]
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 2 * 86400 - 60, "to": t - 2 * 86400 + 600},
                     token="guard")[0] == 202                          # reaching into what it shows: an ask
        assert not [k for k in box.vars.list("rec/requests/") if "-0-600" in k]
    finally:
        srv.shutdown()

    # …and before anything the DEVICE holds: the coverage its holder announces
    from tests.test_console_load import _holder
    from vms.worker import FakeDevice
    box = Box()
    t = box.wall()
    dev = FakeDevice("acme/10.0.0.50", channels=["1"], coverage={"1": (t - 3600.0, t)})
    w, door = _holder(box, dev)
    ctl, rec, m, srv, base = _console(box, access)
    try:
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1"}, token="admin")[0] == 201
        code, body = _call(base, "POST", "/backfill", {"cam": "1", "from": t - 7200, "to": t - 3700}, token="guard")
        assert code == 400 and "before anything the device holds" in body["detail"], (code, body)
        assert _call(base, "POST", "/backfill", {"cam": "1", "from": t - 4000, "to": t - 3000}, token="guard")[0] == 202
    finally:
        srv.shutdown(); door.shutdown()


def test_a_units_name_holds_no_comma_and_no_digit_but_ascii_and_a_stored_one_stops_no_list():
    """The review's ninth pass, a minor and the product team's sibling B: an assignment is its units joined by `,` — a
    recording named `1,9` made its recorder take `9` and never start `1,9`, and its fetched range scanned recording 9's
    camera. And `"7²".isdigit()` is true while `int("7²")` raises: `POST /rec/recordings {"name": "7²"}` was 201, and
    every `GET /rec/recordings` after it went unanswered. Both are refused at creation now (`doors.unnamable`, `unit`);
    a unit stored under such a name before is listed as it stands, counted and named once (`UNIT_NAMES`), and one with a
    comma is written into no assignment (`UNLISTED`) — never split into names it is not."""
    from w2cplatform.contract import UNLISTED
    from w2cplatform.doors import numeric
    from w2cplatform.spec import UNIT_NAMES, _unit_key
    from tests.test_slot_fence import _forget_garbled
    assert numeric("12") == 12 and numeric("7²") is None and numeric("٣") is None and numeric("9" * 5000) is None
    assert _unit_key("9" * 5000) == (1, "9" * 5000)                                  # past what `int` takes: a name
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"})[0] == 201
        for bad in ("1,9", "7²", "٣", "７", "1,"):
            code, body = _call(base, "POST", "/rec/recordings", {"name": bad, "cam": "1"})
            assert code == 400 and "may not hold" in body.get("detail", ""), (bad, code, body)
        assert _call(base, "POST", "/rec/recordings", {"name": "1-9", "cam": "1"})[0] == 201
        for old in ("7²", "1,9"):                                                    # as an older build let them in
            box.vars.put(f"rec/recordings/{old}", {"id": old, "name": old, "cam": "1"})
        code, body = _call(base, "GET", "/rec/recordings")
        assert code == 200, (code, body)
        assert sorted(r["id"] for r in body["configured"])[:3] == ["1,9", "1-9", "7²"], body["configured"]
        assert _call(base, "GET", "/rec/recordings")[0] == 200
        assert UNIT_NAMES.counts == {"rec": 2} and UNIT_NAMES.named("rec/recordings/") == {"7²", "1,9"}   # once each
    finally:
        srv.shutdown()
    on = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    assert on.assign_add("r-1", "1,9").units == [] and box.vars.get("rec/workers/r-1")[0] is None   # no write at all
    a = on.assign("r-1", ["1-9", "1,9", "7²"])
    assert a.units == ["1-9", "7²"] and box.vars.get("rec/workers/r-1")[0]["units"] == "1-9,7²"
    assert on.assign_remove("r-1", "7²").units == ["1-9"]
    assert UNLISTED.counts == {"rec": 1}, UNLISTED.counts                            # the one unit, said once
    _forget_garbled()

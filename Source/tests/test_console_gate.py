"""Who is calling a cluster's console, and may they (the platform review, blocker 1; step 3 of the order agreed with
the product, feedback BP).

Whoever reached a console was an administrator under any name. The gate asks — when this cluster's store holds a key
set. Without one the console is as open as it was, and says so; with one and no way to check, it is SHUT.
"""
import json
import logging
import os
import sys
import urllib.error
import urllib.request

from w2cplatform.access import TRUST_KEYS, Denied, Gate, caller_addr, token_of
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC, SPEC
from vms.console import make_console
from vms.controller import VmsController
from tests.vmsconftest import Box


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

    def by_labels(self, payload, capability):
        rank = {"view": 0, "edit": 1, "admin": 2}
        return payload.get("via") != "break-glass" and any(lab and rank[c] >= rank[capability]
                                                           for c, _, lab in self.grants.get(payload.get("sub"), ()))


def _console(box, access=None):
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    m = make_console(ctl, box.resource_root, box.wall, mounts={"rec": rec},
                     index=EventIndex(box.resource_root, "srv-1", wall=box.wall))       # this box's own events, read where they lie
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
    return [(e["kind"], e.get("user")) for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]]


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
                for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]]
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
    # `domain.access` sits in the same code root (`Source/domain/`) since the move: this console is one without it
    hidden = sys.modules.get("w2cplatform.domain.access")
    sys.modules["w2cplatform.domain.access"] = None
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
        if hidden is None:
            del sys.modules["w2cplatform.domain.access"]
        else:
            sys.modules["w2cplatform.domain.access"] = hidden

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
    box.vars.as_writer("domainagent", ["domain/*"]).delete(DOMAIN_MARKS[-1])  # the agent may; then nothing says "a member"
    assert not any(box.vars.get(p)[0] for p in DOMAIN_MARKS)
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "GET", "/cameras")[0] == 200                   # a cluster nobody joined: open, as it was
    finally:
        srv.shutdown()


def test_the_gate_asks_who_and_the_grant_says_what():
    box = Box()
    access = Tokens({"viewer": [("view", "vms/1", ())], "guard": [("edit", None, ("ground",))], "admin": [("admin", None, ())], "nobody": []})
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
        assert _call(base, "POST", "/marks", {"unit": "vms/1", "note": "bag"}, token="guard")[0] == 201   # an action names its unit in the BODY
        assert _call(base, "POST", "/marks", {"unit": "vms/2", "note": "bag"}, token="guard")[0] == 403   # …and this one is not the guard's
        assert _call(base, "POST", "/marks", {"unit": "vms/1", "note": "bag"}, token="viewer")[0] == 403  # looking is not acting
        # a body that names its unit by a bare id is refused: the gate would have nothing to check it on (the boundary's
        # step 2 — and the review's second pass, which refused a body naming two units, has one name left to read)
        assert _call(base, "POST", "/marks", {"unit": "1", "note": "bag"}, token="guard")[0] == 400
        # a GET names its unit in the query the same way: camera 2's events are not the viewer's
        assert _call(base, "GET", "/events?from=0&to=1&unit=vms/2", token="viewer")[0] == 403
        # …nor the door to a recording of camera 2 (blocker 1 of that pass: an export of camera 1 named a recording of
        # camera 2). The holders' doors are handed out with the unit's place since the boundary's step 6, to whoever may
        # view the unit — the recording's camera (`about`)
        assert _call(base, "POST", "/rec/recordings", {"name": "2-cloud", "cam": "2"}, token="admin")[0] == 201
        assert _call(base, "GET", "/rec/where/2-cloud", token="viewer")[0] == 403

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
        alarms = lambda: [(e["kind"], e["user"]) for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]
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
    access = Tokens({"guard": [("view", None, ("ground",))], "two": [("view", "vms/2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for n in (1, 2, 3):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{n}.mp4", "labels": ["ground"]}, token="admin")[0] == 201
            assert _call(base, "POST", "/marks", {"unit": f"vms/{n}", "note": f"bag {n}"}, token="admin")[0] == 201
        cams = lambda token: sorted({e.get("of") for e in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}",
                                                                token=token)[1]["events"] if e.get("of")})
        assert cams("guard") == ["vms/1", "vms/2", "vms/3"]
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
        assert sorted({e.get("of") for e in rep["events"] if e.get("of")}) == ["vms/1"]
        assert [(w["unit"], w["events"]) for w in rep["withheld"]] == [("vms/2", 1), ("vms/3", 1)], rep["withheld"]
        assert "does not parse" in rep["withheld"][0]["why"]
        assert cams("two") == ["vms/2"] and cams("admin") == ["vms/1", "vms/2", "vms/3"]   # no label needed: shown as before
        assert "withheld" not in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}", token="admin")[1]
        # …and not to a grant on one unit (the review's tenth pass, minor): camera 3's id and its count were said to the
        # guard of camera 2, whose grant never covered camera 3 whatever its labels
        assert "withheld" not in _call(base, "GET", f"/events?from=0&to={box.wall() + 1}", token="two")[1]
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
    ref = f"vms/{cam}"                                                  # a unit as the platform names one (the boundary's step 2)
    assert root.needs("GET", "/cameras") == ("view", None, [], None) and root.needs("GET", f"/cameras/{cam}") == ("view", ref, ["ground"], None)
    assert root.needs("POST", "/cameras") == ("admin", None, [], None) and root.needs("DELETE", f"/cameras/{cam}")[0] == "admin"
    assert root.needs("POST", "/requests")[0] == "edit" and recs.needs("POST", "/requests")[0] == "edit" and root.needs("POST", "/marks")[0] == "edit"
    assert root.needs("GET", f"/where/{cam}") == ("view", ref, ["ground"], None)          # the holder's door: `view` on the unit
    assert recs.needs("GET", "/where/1-cloud") == ("view", "rec/1-cloud", ["ground"], ref)  # …a recording's, on its camera
    # a recording is about its camera (`about`): asked with it, and the labels are the camera's
    assert recs.needs("DELETE", "/recordings/1-cloud") == ("admin", "rec/1-cloud", ["ground"], ref)
    assert recs.needs("POST", "/keeps")[0] == "edit" and recs.needs("POST", "/volumes")[0] == "admin"
    assert root.needs("POST", "/marks", ref) == ("edit", ref, ["ground"], None) and recs.needs("POST", "/keeps", ref) == ("edit", ref, ["ground"], None)
    assert token_of({"Authorization": "Bearer abc"}) == "abc" and token_of({"Cookie": "a=b; w2c_token=xyz"}) == "xyz"
    assert token_of({}) is None and token_of({"Authorization": "Basic abc"}) is None


def test_the_live_gateway_asks_the_viewer_too():
    """A gateway's door is reached by anybody on its network. The console gave the viewer a door token with the stream's
    place — after asking `view` on the camera — and the gateway checks it by the cluster's public keys (`door/keys` in
    the store): this gateway, this stream, the `whep` route, not past its time; any refusal is a 401 whose `reason` says
    which. No key in the store: open, and it says so."""
    import time
    from tests.conftest import door_keys
    from tests.test_lesson8_live import OFFER, _gateway
    box = Box()

    def whep(g, cam, token=None, method="POST", path=None):
        req = urllib.request.Request(g.url + (path or f"/whep/{cam}"), data=OFFER.encode() if method == "POST" else None, method=method,
                                     headers={"Content-Type": "application/sdp", **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    assert whep(_gateway(box, "g-0"), 1) == 404                        # no ring: open — and the stream is simply not here
    with door_keys(box.vars) as keys:
        g = _gateway(box, "g-1")
        sign = keys.signer
        now = box.wall()
        token = lambda unit="live/1", holder="g-1", routes=("whep",), at=now: sign.issue("anna", unit, holder, routes, at)[0]   # noqa: E731
        assert whep(g, 1) == 401 and whep(g, 1, "not-a-token") == 401   # now it asks
        assert whep(g, 1, token()) == 404                               # admitted (and the stream is not here)
        assert whep(g, 2, token()) == 401                               # a token for another stream
        assert whep(g, 1, token(holder="g-2")) == 401                   # …for another gateway: the stream moved
        assert whep(g, 1, token(routes=("segment",))) == 401            # …for another route
        assert whep(g, 1, token(at=now - 600)) == 401                   # …ended
        forged = token()[:-4] + ("AAAA" if not token().endswith("AAAA") else "BBBB")
        assert whep(g, 1, forged) == 401                                # a signature that does not hold
        assert whep(g, None, method="DELETE", path="/whep/session/x") == 404   # no such session


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
        glass = lambda pw: _call(base, "POST", "/session/break-glass", {"who": "carol", "why": "uplink down", "password": pw})[0]
        assert glass("open-sesame") == 200                                                        # the account works
        assert [glass("wrong") for _ in range(5)] == [403] * 5
        assert glass("wrong") == 429 and glass("open-sesame") == 429                              # closed, to the right password too
        alarms = [e["kind"] for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]
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
        req = urllib.request.Request(base + "/session/break-glass", method="POST", headers={"Content-Type": "application/json", "X-Forwarded-For": xff},
                                     data=json.dumps({"who": "carol", "why": "uplink down", "password": pw}).encode())
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
    2 (an export is its holder's door since the boundary's step 6; `/where` is the route that names a unit). One reading of a path's id (`path_id`) for both; a family that takes an id takes one, and more after it is
    404 before the gate — except `PUT /<rows>/<id>/<blob>`, the one route with a third segment."""
    box = Box()
    access = Tokens({"one": [("admin", "vms/1", ())], "viewer": [("view", "vms/1", ())], "admin": [("admin", None, ())]})
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
        for path in ("/where/1/2", "/cameras/1/2", "/rec/where/1-cloud/2-cloud"):
            assert _call(base, "GET", path, token="viewer")[0] == 404, path
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
    access = Tokens({"viewer": [("view", "vms/1", ())], "admin": [("admin", None, ())]})
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
        assert _call(base, "PUT", f"/schema?version={SCHEMA}", token="admin")[0] == 200   # the console's token reaches it

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
    400, naming why, for anybody — the same value is no change. Every subsystem whose rows are about a camera says so in
    its spec (`about: {sub: vms, field: cam}`, the field `fixed: true`; the boundary's step 2)."""
    from vms.config import DET_SPEC
    box = Box()
    access = Tokens({"one": [("admin", "vms/1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1-cloud", "cam": "1"}, token="admin")[0] == 201
        # the gate asks about the camera the row is about NOW — hers — and the spec refuses the move, to her and to
        # whoever holds rights on both: a fixed field is nobody's to change
        code, body = _call(base, "PUT", "/rec/recordings/1-cloud", {"cam": "2"}, token="one")
        assert code == 400 and "fixed" in body["detail"]
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
        assert all(c.spec.about_sub == "vms" and c.spec.fields["cam"].fixed for n, c in m.mounts.items() if "cam" in c.spec.fields)
    finally:
        srv.shutdown()


def _console_with_jobs(box, access):
    """A gated console that fronts `rec`, `det`, `detjob` and `auto`, as the console process does."""
    from vms.config import AUTO_SPEC
    from w2cplatform.spec import SpecController
    from vms.config import AUTO_SPEC, DET_SPEC, DETJOB_SPEC
    acl = SPEC.acl_console() + REC_SPEC.acl_console() + DET_SPEC.acl_console() + DETJOB_SPEC.acl_console() + AUTO_SPEC.acl_console()
    vars_ = box.vars.as_writer("console", acl)
    ctl = VmsController(vars_, box.objects, wall=box.wall)
    mounts = {"rec": SpecController(REC_SPEC, vars_, box.objects, wall=box.wall),
              "det": SpecController(DET_SPEC, vars_, box.objects, wall=box.wall),
              "detjob": SpecController(DETJOB_SPEC, vars_, box.objects, wall=box.wall),
              "auto": SpecController(AUTO_SPEC, vars_, box.objects, wall=box.wall)}
    m = make_console(ctl, box.resource_root, box.wall, mounts=mounts, index=EventIndex(box.resource_root, "srv-1", wall=box.wall))
    for con in (m.root, *m.mounts.values()):
        con.gate.impl = access
    srv = m.serve("127.0.0.1", 0)
    return mounts, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_a_scan_reads_only_its_own_cameras_recording_and_keeps_it():
    """The review's fifth pass, major: `cam` was fixed, and a scan names a camera through another field too — `rec`, the
    recording whose footage it reads. `PUT /detjob/jobs/1-motion-1 {"rec": "2"}` with `admin` on camera 1 was 200, and
    the scan read camera 2's archive. A scan is about its camera (`about`), and `rec` is a recording of `cam`, said at
    the door (`rec: {ref: rec/recordings, must_match: {cam: cam}}` in the spec, the platform's since the boundary's
    step 6) and fixed when the job is made (`fixed: true`) — for anybody."""
    box = Box()
    access = Tokens({"one": [("admin", "vms/1", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    t = box.wall()
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
            assert _call(base, "POST", "/rec/recordings", {"name": str(i), "cam": str(i)}, token="admin")[0] == 201
        job = {"name": "1-motion-1", "cam": "1", "rec": "1", "kind": "motion", "from": t - 600, "to": t - 300}
        assert _call(base, "POST", "/detjob/jobs", job, token="admin")[0] == 201
        code, body = _call(base, "PUT", "/detjob/jobs/1-motion-1", {"rec": "2"}, token="one")
        assert code == 400 and "fixed" in body["detail"]                                      # her scan: still not a move
        code, body = _call(base, "PUT", "/detjob/jobs/1-motion-1", {"rec": "2"}, token="admin")
        assert code == 400 and "fixed" in body["detail"]                                      # rights on both: still not a move
        assert mounts["detjob"].unit("1-motion-1")["rec"] == "1"
        assert _call(base, "PUT", "/detjob/jobs/1-motion-1", {"params": "{}"}, token="one")[0] == 200   # her camera, her scan
        code, body = _call(base, "POST", "/detjob/jobs", {**job, "name": "1-motion-2", "rec": "2"}, token="admin")
        assert code == 400 and "rec 2 is cam 2's" in body["detail"]                           # another camera's recording
    finally:
        srv.shutdown()


def test_a_scenario_is_the_whole_clusters_to_write_whatever_its_labels_say():
    """The review's fifth pass, major, and its question about `auto`: a scenario's labels are PLACEMENT labels — where
    its evaluator runs — and a grant on a label matched them: `PUT /auto/scenarios/lobby` with `then: output unit 12`
    was 200 for somebody whose `POST /requests` on camera 12 is 403. A scenario is the cameras it watches and acts on,
    and it is about no one unit: writing one is the whole cluster's business (`CLUSTER_ROWS`, as the product's gate says
    of `/auto/…`; the boundary's step 2 took away the hook that read every camera out of its triggers). A grant on its
    labels, or on every camera it names, writes nothing of it."""
    box = Box()
    access = Tokens({"lobby": [("admin", None, ("lobby",))], "both": [("admin", "vms/1", ()), ("admin", "vms/2", ())],
                     "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["lobby"]}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/2.mp4"}, token="admin")[0] == 201
        scenario = {"name": "lobby", "labels": ["lobby"],
                    "when": [{"sub": "vms", "kind": "motion", "unit": "1"}],
                    "then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", scenario, token="admin")[0] == 201
        assert _call(base, "POST", "/requests", {"unit": "vms/2", "action": "output", "port": 1}, token="lobby")[0] == 403
        other = [{"sub": "vms", "action": "output", "unit": "2", "port": 1}]
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"then": other}, token="lobby")[0] == 403   # its labels grant nothing
        anyone = [{"sub": "vms", "kind": "motion"}]
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"when": anyone}, token="lobby")[0] == 403
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"within": 0, "then": [{**scenario["then"][0], "port": 2}]},
                     token="lobby")[0] == 403                                                      # not even on her own camera
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"within": 0}, token="both")[0] == 403   # nor on every camera it names
        assert mounts["auto"].unit("lobby")["then"][0]["unit"] == "1"
        assert _call(base, "PUT", "/auto/scenarios/lobby", {"then": other}, token="admin")[0] == 200
        assert _call(base, "DELETE", "/auto/scenarios/lobby", token="lobby")[0] == 403
        assert _call(base, "DELETE", "/auto/scenarios/lobby", token="admin")[0] == 200
    finally:
        srv.shutdown()


def test_a_deleted_recordings_name_comes_back_only_for_its_own_camera():
    """The review's fifth pass, major: DELETE «1-cloud» of camera 1, then POST `{"name": "1-cloud", "cam": "2"}` — and a
    viewer of camera 2 alone got camera 1's frames from `GET /export/2`, because footage is found by the recording's
    name. The rule: a tombstone keeps its camera, and the name comes back for that camera only — for another it is
    400, and so is the PUT that asked for it, whose refusal no longer suggests the trick."""
    from tests.vmsconftest import door, footage, store
    box = Box()
    access = Tokens({"two": [("view", "vms/2", ())], "admin": [("admin", None, ())]})
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
    taken only when no recording of that name says it is another camera's — alive or deleted; a keep likewise. Since
    the boundary's step 6 a page reads a RECORDING at its holder's door, handed out with its place (`/rec/where/<name>`)
    to whoever may view the camera the recording is ABOUT; a backfill names its recording (`rec/requests`) and is asked
    the same way."""
    from tests.vmsconftest import door, footage, store
    from vms import keeps
    box = Box()
    access = Tokens({"guard": [("edit", "vms/1", ())], "other": [("edit", "vms/2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    st = store()
    t = box.wall()
    footage(st, "1", 1, t - 900, t - 300)                              # the tree «1»: camera 2's footage
    rdoor = door(box, st)
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "2"}, token="admin")[0] == 201
        assert _call(base, "GET", "/rec/where/1", token="guard")[0] == 403          # «1» is camera 2's: no door for camera 1
        assert _call(base, "GET", "/rec/where/1", token="other")[0] in (200, 404)   # it IS camera 2's
        # a backfill names the recording (`rec/requests`, step 6): «1» is camera 2's, and camera 1's guard may not
        assert _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 900, "to": t - 300}, token="guard")[0] == 403
        assert not box.vars.list("rec/requests/")
        rec.delete("1")                                                 # deleted, the tombstone still says whose it was
        assert _call(base, "GET", "/rec/where/1", token="guard")[0] in (403, 404)
        assert _call(base, "POST", "/rec/keeps", {"cam": "1", "from": t - 900, "to": t - 300}, token="guard")[0] == 201
        assert [k.recordings for k in keeps.declared(box.vars) if k.cam == "1"] == [()]

        # a day at most is the recorder's to say (`RecWorker._range_refusal`: `test_a_backfill_nobody_could_answer_…`), and
        # a keep holds a week at most on the resources (`holds.longest`) — taken at the door, held as far as it may
        code, body = _call(base, "POST", "/rec/keeps", {"cam": "2", "from": t - 30 * 86400, "to": t}, token="other")
        assert code == 201 and REC_SPEC.holds["longest"] == 7 * 86400
    finally:
        rdoor.shutdown(); srv.shutdown()


def test_a_backfill_is_two_finite_numbers_a_handful_at_a_time_and_a_line():
    """The review's fifth pass, minor: `POST /backfill` with `NaN` broke the connection with no reply; nothing bounded how
    many day-long asks one person filed; and an ask left no line. A backfill is the recorder's request since the
    boundary's step 6 (`POST /rec/requests {unit: rec/<recording>, from, to}`, the spec's `requests:`): 400 for anything
    but two finite numbers (the schema's, and `NaN` is no number); at most seven of one person's asks waiting for a
    recorder (`per_person`; the same range again is the same ask); and `archive.backfill.asked` names who and which."""
    box = Box()
    access = Tokens({"guard": [("edit", "vms/1", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    t = box.wall()
    per = REC_SPEC.requests["per_person"]
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1"}, token="admin")[0] == 201
        for bad in ({"unit": "rec/1", "from": float("nan"), "to": t}, {"unit": "rec/1", "from": t - 60, "to": float("inf")},
                    {"unit": "rec/1", "from": "soon", "to": t}, {"unit": "rec/1", "from": False, "to": True}):
            assert _call(base, "POST", "/rec/requests", bad, token="guard")[0] == 400, bad
        asks = [_call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 3600 * (i + 1), "to": t - 3600 * i},
                      token="guard")[0] for i in range(per)]
        assert asks == [202] * per
        assert _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 3600, "to": t}, token="guard")[0] == 202   # the same ask
        code, body = _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 9e4, "to": t - 8.9e4}, token="guard")
        assert code == 429 and "guard has 7" in body["detail"]
        assert _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 9e4, "to": t - 8.9e4}, token="admin")[0] == 202  # another person
        row = box.vars.get(REC_SPEC.sub.request_key(f"1-{int(t - 3600)}-{int(t)}"))[0]
        assert (row["unit"], row["cam"], row["by"]) == ("1", "1", "guard")                    # its recording, whose, who
        lines = [e for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]
                 if e["kind"] == "archive.backfill.asked"]
        assert len(lines) == per + 2 and lines[0]["user"] == "guard" and lines[0]["target"] == "rec/1"
    finally:
        srv.shutdown()


def test_forty_backfills_asked_at_once_are_seven():
    """The review's sixth pass, minor — a run: forty POSTs at once left fifteen rows where seven is the bound. The bound
    was a count of rows read before the write, and requests in flight all counted the same ones. A person's open asks are
    one row now, changed by CAS (`<sub>/requests/asks-<sha256 of the person, 16 hex>`, the platform's `per_person`):
    forty at once are seven asks and thirty-three refusals, never an eighth; a place comes back when an ask is answered.
    (An ask no recorder could ever answer is refused by the recorder since the boundary's step 6.)"""
    import threading
    box = Box()
    access = Tokens({"guard": [("edit", "vms/1", ())], "admin": [("admin", None, ())]})
    was = os.environ.get("CONSOLE_PER_ADDRESS")
    os.environ["CONSOLE_PER_ADDRESS"] = "64"                          # forty at once from one address: the door lets them in
    ctl, rec, m, srv, base = _console(box, access)
    t = box.wall()
    per, settle = REC_SPEC.requests["per_person"], REC_SPEC.requests["settle"]
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/1.mp4"}, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/recordings", {"name": "1", "cam": "1"}, token="admin")[0] == 201
        codes, lock = [], threading.Lock()

        def ask(i):
            code = _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 3600 * (i + 2), "to": t - 3600 * (i + 1)},
                         token="guard")[0]
            with lock:
                codes.append(code)
        threads = [threading.Thread(target=ask, args=(i,)) for i in range(40)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(30)
        mine = [k for k in box.vars.list(REC_SPEC.sub.requests_prefix())
                if (box.vars.get(k)[0] or {}).get("by") == "guard" and "from" in box.vars.get(k)[0]]
        assert sorted(codes) == [202] * per + [429] * (40 - per), sorted(codes)
        assert len(mine) == per                                                            # never an eighth row
        box.vars.delete(mine[0])                                      # the recorder fetched one, its row was cleared
        box.wall.advance(settle + 1)
        assert _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 9e4, "to": t - 8.9e4}, token="guard")[0] == 202
        assert _call(base, "POST", "/rec/requests", {"unit": "rec/1", "from": t - 9.9e4, "to": t - 9.8e4}, token="guard")[0] == 429
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


def _device_site(box, dev, access=None):
    """A console, a camera holder serving its playback door over `dev`, cameras 1 and 2 (its channels) placed on it, and
    a recording of each (`1`, `2`) — what a recording's door reads the camera's own footage for."""
    from vms.worker import FakeActuator, VmsWorker
    ctl, rec, m, srv, base = _console(box, access or Tokens({"admin": [("admin", None, ())]}))
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root, device_factory=lambda k: dev)
    w.heartbeat_once()
    play = w.serve_playback("127.0.0.1", 0)
    for ch in (1, 2):
        assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        rec.create({"name": str(ch), "cam": str(ch)})
    placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    return w, play, srv, base


def _piece(a: float, b: float) -> str:
    """The path of a piece of what the camera holds: `.device.mp4`, epoch 0, the bounds in milliseconds."""
    return f"e0/{a * 1000:.0f}-{b * 1000:.0f}.device.mp4"


def test_a_segment_is_cut_to_what_the_device_holds_and_the_door_streams_it_a_piece_at_a_time():
    """The review's fifth pass, major: `/segment` signed any interval, and the holder's door read it in one `read` into
    one buffer — 1000 s of a 100 kB/s card was 100 MB in the process holding every camera of its server. The console
    is out of the bytes: a recording's door (its recorder's, `/segment/<recording>/e0/<a>-<b>.device.mp4`) cuts the
    interval to the coverage the camera's holder announces and holds it to `SEGMENT_MAX` (nothing of the device's there:
    404; longer: 400), reads it from the holder by its capability and passes it on as it comes, in chunks — the last one
    only when every piece went. The holder asks the device for `PLAYBACK_PIECE` seconds at a time, one session at a
    time."""
    import http.client
    from tests.vmsconftest import page_door
    from vms.worker import FakeDevice
    box = Box()
    dev = FakeDevice("acme/10.0.0.50", channels=["1", "2"], coverage={"1": (0.0, 1000.0), "2": (0.0, 10000.0)},
                     max_playbacks=2, bps=20000)
    pieces = []
    read = dev.read
    dev.read = lambda sid: (lambda b: (pieces.append((len(b), len(dev.open))), b)[1])(read(sid))
    w, play, srv, base = _device_site(box, dev)
    pd = page_door(box)
    try:
        code, spans = _get(f"{pd.base}/timeline/1?from=0&to=86400")
        assert code == 200 and [(s["start_ms"], s["end_ms"], s["yields"]) for s in json.loads(spans)] == [(0, 1000000, True)]
        assert _get(f"{pd.base}/segment/1/{_piece(5000, 6000)}")[0] == 404          # the card holds nothing there
        code, body2 = _get(f"{pd.base}/segment/2/{_piece(0, 3601)}")
        assert code == 400 and b"3600" in body2                                  # longer than an export: not served at all

        c = http.client.HTTPConnection("127.0.0.1", pd.server_address[1], timeout=30)
        c.request("GET", f"/segment/1/{_piece(0, 86400)}")
        r = c.getresponse()
        assert r.status == 200 and r.getheader("Transfer-Encoding") == "chunked" and r.getheader("Content-Length") is None
        total = len(r.read())
        assert total == 1000 * 20000                                               # all of it, through the stream
        assert max(n for n, _ in pieces) <= w.PLAYBACK_PIECE * 20000                # never more than a piece at once
        assert len(pieces) >= 1000 / w.PLAYBACK_PIECE and max(o for _, o in pieces) == 1   # one session at a time
        assert not dev.open                                                          # and every one closed
    finally:
        pd.shutdown(); play.shutdown(); srv.shutdown()


def test_the_devices_own_footage_opens_only_to_the_token_the_console_gave():
    """The review's fourth pass, blocker 4. The console checked `view` and handed the browser the holder's door as it
    is; the door asked nobody, so a viewer of camera 1 edited `1` into `2` and took camera 2's card. A page reads the
    camera's own footage at a RECORDING's door now — its recorder's, handed out with the recording's place — with a
    door token: this recorder, this recording, these routes, two minutes, checked by the cluster's public keys
    (`door/keys`): the recording edited, no token, a token past its time are refused (401, the `reason` says which);
    the token's is served and a line names the viewer. The camera's holder has no door for a page: a process of the
    cluster reads it by a per-camera capability (`/playback/<cam>/<capability>`), and in a gated cluster the bare
    address is refused."""
    from tests.conftest import door_keys
    from tests.vmsconftest import page_door
    from vms.playback import process_url
    from vms.worker import FakeDevice
    from w2cplatform.console import holder_of
    from w2cplatform.door import TTL, DoorKeeper
    from w2cplatform.events import buckets_under
    box = Box()
    dev = FakeDevice("acme/10.0.0.50", channels=["1", "2"], coverage={"1": (0.0, 1000.0), "2": (0.0, 1000.0)}, max_playbacks=4)
    w, play, srv, base = _device_site(box, dev)
    bare = f"http://127.0.0.1:{play.server_address[1]}/playback/2?from=0&to=5"
    assert _get(bare)[0] == 200                                        # no key set in the store: open, as the console is
    with door_keys(box.vars) as keys:
        pd = page_door(box, "r-1", keeper=DoorKeeper("r-1", box.wall, box.vars))
    token = keys.signer.issue("viewer", "rec/1", "r-1", ("timeline", "segment"), box.wall())[0]

    def get(unit, tok=token):
        return _get(f"{pd.base}/segment/{unit}/{_piece(0, 5)}", {"Authorization": f"Bearer {tok}"} if tok else {})
    try:
        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})   # in a domain: the holder asks
        assert get(1)[0] == 200                                        # the token the console gave
        code, body = get(2)
        assert code == 401 and json.loads(body)["reason"] == "unit"   # the recording edited
        code, body = get(1, None)
        assert code == 401 and json.loads(body)["reason"] == "token"  # no token
        assert _get(bare)[0] == 403                                   # the holder's bare address, no capability

        found = holder_of(box.objects, "vms/", "2", box.wall(), field="playback_url")
        cap = process_url(found)                                     # the recorder's and the survey's address for camera 2
        assert _get(f"{cap}?from=0&to=5")[0] == 200
        assert _get(f"{cap.replace('/playback/2/', '/playback/1/')}?from=0&to=5")[0] == 403   # one camera's capability is not another's

        box.wall.advance(TTL + 6)
        code, body = get(1)
        assert code == 401 and json.loads(body)["reason"] == "expired"   # two minutes on: ask `/rec/where` again

        reads = [(e["user"], e.get("recording")) for b in buckets_under(box.resource_root, "audit", "door-r-1", 600)
                 for e in map(json.loads, open(os.path.join(box.resource_root, b.path))) if e["kind"] == "archive.read"]
        assert reads == [("viewer", "1")]                            # the door says the door was USED, and by whom
    finally:
        pd.shutdown(); play.shutdown(); srv.shutdown()


# -- the sixth pass: a field that points at another unit ---------------------------------------------------------------
def test_a_recording_is_homed_on_a_card_only_by_whoever_may_act_on_that_cards_camera_and_only_its_own():
    """The review's sixth pass, major: `PUT /rec/recordings/1-b {"home": "card2"}` with `admin` on camera 1 was 200 —
    and the card in camera 2, whose recorder writes its own camera's ring whatever the row says, wrote camera 2's
    frames into camera 1's recording, out of its own budget. An edge volume names the camera whose card it is
    (`cam`), and the controller refuses a recording of another camera on it, for whoever writes the row: a card holds
    its own camera's recordings (`home: {ref: rec/volumes, must_match: {cam: cam}}` in the spec, read by the platform
    since the boundary's step 6; it was a hook of the VMS's, `volumes.refuse_recording`). (The gate asked about the card's camera as well until the
    boundary's step 2, through a hook that read cameras out of a row; whose a recording is, is its spec's `about` now,
    and the rule that a card is its camera's is the one place the refusal lives.) The same reach through a scenario's `record` with `archive: card2`: a
    scenario is the whole cluster's to write, and what it asks is refused when the request is turned into a row. A disk or a bucket is no camera's."""
    from vms import jobs, volumes
    box = Box()
    access = Tokens({"one": [("admin", "vms/1", ())], "both": [("admin", "vms/1", ()), ("admin", "vms/2", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    rec = mounts["rec"]
    card = {"name": "card2", "kind": "edge", "server": "cam-2", "url": "/media/sd", "quota_bytes": 1 << 30}
    try:
        for i in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{i}.mp4"}, token="admin")[0] == 201
        code, body = _call(base, "POST", "/rec/volumes", card, token="admin")
        assert code == 400 and "needs 'cam'" in body["detail"]                               # a card says whose it is (the table's schema)
        assert _call(base, "POST", "/rec/volumes", {**card, "cam": "2"}, token="admin")[0] == 201
        disks = {"name": "disks", "kind": "local", "server": "srv-1", "url": "/data/v", "quota_bytes": 1 << 30}
        assert _call(base, "POST", "/rec/volumes", disks, token="admin")[0] == 201
        assert _call(base, "POST", "/rec/volumes", {**disks, "name": "d2", "cam": "2"}, token="admin")[0] == 400   # a disk is no camera's
        assert _call(base, "POST", "/rec/recordings", {"name": "1-b", "cam": "1"}, token="admin")[0] == 201
        code, body = _call(base, "PUT", "/rec/recordings/1-b", {"home": "card2"}, token="one")
        assert code == 400 and "home card2 is cam 2's" in body["detail"]                      # camera 2's card: nobody's place for it
        code, body = _call(base, "PUT", "/rec/recordings/1-b", {"home": "card2"}, token="both")
        assert code == 400 and "home card2 is cam 2's" in body["detail"]                      # hers too — and still not camera 1's place
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
        assert _call(base, "PUT", "/auto/scenarios/keep", {"then": record(archive="disks")}, token="one")[0] == 403   # the cluster's to write
        assert _call(base, "PUT", "/auto/scenarios/keep", {"then": record(archive="card2")}, token="admin")[0] == 200  # written…
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
    assert rec.card_cam == "1" and "1-card" in rec.reconciler.running()
    row = REC_SPEC.new_row("2-b", {"name": "2-b", "cam": "2", "home": "card"})
    box.vars.put("rec/recordings/2-b", REC_SPEC.items(row))                              # past the door
    rec_ctl.ensure_placed()
    rec.reconcile_once(); rec.heartbeat_once()
    st = _status(rec, "2-b")
    assert st["phase"] != "running" and "2-b" not in rec.reconciler.running()
    assert "card in camera 1" in st["why"] and "camera 2's" in st["why"]
    _film(ring, box.wall(), box.wall() + 10, act=act)
    assert act.stats("1-card")["samples_written"] == 20 and act.stats("2-b").get("samples_written", 0) == 0


def test_a_cameras_source_is_moved_only_by_whoever_administers_every_camera_of_the_device_and_is_nobody_elses():
    """The review's sixth pass, major: `PUT /cameras/1 {"source": "…/ch/2"}` with `admin` on camera 1 was 200 — the
    credentials are the device's, so the holder opened channel 2 as camera 1, and camera 1's viewers and archive got
    camera 2's picture. A change of device or channel is asked about on every camera of the device it leaves and of
    the device it moves to (`source_cams`); an address is one camera, for anybody (`source: {unique: canonical}`, the
    platform's — `…/ch/2/` beside `…/ch/2` is the holder's «device busy», `test_two_spellings_of_one_channel_…`); an edit
    that leaves the source where it is asks for nothing more. `ref` — the name the domain knows the camera by — is
    the cluster's to change, and one camera's."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"one": [("admin", "vms/1", ())], "both": [("admin", "vms/1", ()), ("admin", "vms/2", ())], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.60/ch/1"}, token="admin")[0] == 201   # camera 3
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}2"}, token="one")[0] == 403          # camera 2's channel
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}7"}, token="one")[0] == 403          # a free one, and still camera 2's device
        code, body = _call(base, "PUT", "/cameras/1", {"source": f"{nvr}2"}, token="both")
        assert code == 400 and "vms 2 has that source already" in body["detail"]                        # every camera of the device hers: still one camera
        assert _call(base, "PUT", "/cameras/1", {"source": "driverpack://ACME/10.0.0.50/ch/2"}, token="admin")[0] == 400   # the same address, its host in capitals
        assert _call(base, "PUT", "/cameras/1", {"source": "driverpack://acme/10.0.0.60/ch/5"}, token="both")[0] == 403   # camera 3's device
        assert ctl.camera(1)["source"] == f"{nvr}1"
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}1", "name": "gate"}, token="one")[0] == 200   # nothing moved: her camera
        assert _call(base, "PUT", "/cameras/1", {"source": f"{nvr}7"}, token="both")[0] == 200          # a free channel, every camera of it hers
        code, body = _call(base, "POST", "/cameras", {"source": f"{nvr}7"}, token="admin")
        assert code == 400 and "vms 1 has that source already" in body["detail"]
        assert _call(base, "DELETE", "/cameras/1", token="admin")[0] == 200
        assert _call(base, "POST", "/cameras", {"source": f"{nvr}7"}, token="admin")[0] == 201           # a deleted camera holds no channel
        # `ref`: the cluster's to change, and one camera's
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2"}, token="both")[0] == 403
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2"}, token="admin")[0] == 200
        assert _call(base, "PUT", "/cameras/2", {"ref": "SN-2", "name": "yard"}, token="both")[0] == 200   # unchanged: hers
        code, body = _call(base, "PUT", "/cameras/3", {"ref": "SN-2"}, token="admin")
        assert code == 400 and "vms 2 has that ref already" in body["detail"]
    finally:
        srv.shutdown()


def test_every_field_of_every_spec_that_points_at_something_else_is_asked_about():
    """The sixth pass's complaint was the class, not the two fields: a field that points at another unit, volume or
    device, and a gate that asks only about the camera the row is about. Every field of every subsystem's spec is
    named here — what it points at, or that it points at nothing — so a field added to a spec fails this test until
    somebody has said which it is; and for each one that points, the spec says it (`about`, `fixed: true`), the
    platform's console asks what a change reaches by the spec (`rights.reach`: by the group, or the cluster's) or takes
    the rows as the cluster's (`rights.cluster_rows`), or the controller refuses what it may not point at (the
    boundary's step 2 took the hooks that read a camera out of a row — `cams_of` — and put whose a row is into the
    specs; step 6 took the console's last hooks, `moved_units` and `CLUSTER_ROWS`, into `rights:`)."""
    from vms.config import AUTO_SPEC
    from w2cplatform.spec import SpecController
    from vms.config import AUTO_SPEC, DET_SPEC, DETJOB_SPEC, LIVE_SPEC, SURVEY_SPEC
    FIXED, ABOUT, MOVED, RULE, CLUSTER = "fixed: true", "about", "rights.reach", "refused by the controller", "rights.cluster_rows"
    points = {
        ("vms", "source"): (MOVED, RULE),      # a channel of a device: every camera of both groups; one channel, one camera
        ("vms", "ref"): (MOVED, RULE),         # the domain's name for it: the cluster's grant; one name, one camera
        ("rec", "cam"): (FIXED, ABOUT),        # whose footage
        ("rec", "home"): (RULE,),              # a volume; a camera's card holds that camera's recordings and nobody else's
        ("det", "cam"): (FIXED, ABOUT),
        ("detjob", "cam"): (FIXED, ABOUT),
        ("detjob", "rec"): (FIXED, RULE),      # a recording: of the same camera
        ("survey", "cam"): (FIXED, ABOUT),
        ("live", "cam"): (FIXED, ABOUT),       # the row's own name
        ("auto", "when"): (CLUSTER,),          # the units it watches
        ("auto", "then"): (CLUSTER,),          # the units it acts on, and the card a `record` writes to
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
    mounts.update(detjob=SpecController(DETJOB_SPEC, vars_, box.objects, wall=box.wall), auto=SpecController(AUTO_SPEC, vars_, box.objects, wall=box.wall))
    m = make_console(ctl, box.resource_root, box.wall, live_ctl=SpecController(LIVE_SPEC, vars_, box.objects, wall=box.wall),
                     mounts=mounts, index=EventIndex(box.resource_root, "srv-1", wall=box.wall))
    consoles = {"vms": m.root, **m.mounts}
    for (sub, field), how in points.items():
        con = consoles[sub]
        if FIXED in how:
            assert con.spec.fields[field].fixed, (sub, field)
        if ABOUT in how:                                                                  # the gate reads the camera, and its labels
            assert (con.spec.about_sub, con.spec.about_field) == ("vms", field), (sub, field)
        if MOVED in how:
            reach = con.spec.reach
            assert field in reach.get("group", ()) + reach.get("cluster", ()), (sub, field)
        if CLUSTER in how:
            assert con.spec.cluster_rows, (sub, field)
        if RULE in how:
            f = con.spec.fields[field]                                                   # declared: what it points at, or one per cluster
            assert f.must_match or f.unique or type(con.ctl) is not SpecController, (sub, field)


def test_a_command_to_a_device_is_asked_of_every_camera_of_the_device_by_hand_and_through_a_scenario():
    """The review's seventh pass, major — a run: a guard with `edit` on camera 1 of a sixteen-channel recorder sent
    `output` to ports 1–4 and `preset 5`: 202, and the device did all of it — the lock of camera 2's zone among them.
    The holder performs a command on the DEVICE (`perform`: `dev.output(port)`, `dev.preset(n)`), and nothing a device
    says of itself binds a relay or a preset to a channel. So a command needs `edit` on every camera of the device
    (`command_cams`, `body_units`) — and a scenario is the cluster's to write (`CLUSTER_ROWS`); a camera that is its
    device's only channel asks for nothing more than it did."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"guard": [("edit", "vms/1", ())], "both": [("edit", "vms/1", ()), ("edit", "vms/2", ())],
                     "lobby": [("admin", "vms/1", ())], "lobbies": [("admin", "vms/1", ()), ("admin", "vms/2", ())],
                     "three": [("edit", "vms/3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201   # its own device
        for cmd in ({"unit": "vms/1", "action": "output", "port": 3}, {"unit": "vms/1", "action": "preset", "n": 5}):
            assert _call(base, "POST", "/requests", cmd, token="guard")[0] == 403, cmd   # camera 2 is on that device
            assert _call(base, "POST", "/requests", cmd, token="both")[0] == 202, cmd    # every camera of it hers
        assert box.vars.list("vms/requests/") and all(box.vars.get(k)[0]["by"] for k in box.vars.list("vms/requests/"))
        assert _call(base, "POST", "/requests", {"unit": "vms/3", "action": "output", "port": 1}, token="three")[0] == 202
        # through a scenario: the same reach
        acting = {"name": "gate", "when": [{"sub": "vms", "kind": "motion", "unit": "1"}],
                  "then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", acting, token="admin")[0] == 201
        assert _call(base, "PUT", "/auto/scenarios/gate", {"within": 0}, token="lobby")[0] == 403   # it acts on camera 2's device too
        assert _call(base, "PUT", "/auto/scenarios/gate", {"within": 0}, token="lobbies")[0] == 403  # …and a scenario is the cluster's
        assert _call(base, "PUT", "/auto/scenarios/gate", {"within": 0}, token="admin")[0] == 200
        assert _call(base, "DELETE", "/auto/scenarios/gate", token="lobby")[0] == 403
    finally:
        srv.shutdown()


def test_every_spelling_of_a_devices_host_is_its_group_and_a_host_nobody_can_read_is_refused():
    """The review's eighth pass, major — a run: with `admin` on a file camera of her own, a user set its `source` to
    `driverpack://ACME/10.0.0.50/ch/2` (or `:80`, `10.0.0.50.`) — channel 2 of a recorder whose cameras were not hers:
    200, and then her `output` to port 1 was 202, the recorder pulsed. `device_of` took the address as typed. The VMS's
    reading is canonical — an address in the form the resolver dials (`012.0.0.50` is `10.0.0.50`), no default port, no
    credentials — and the holder dials by it. Since the boundary's step 6 the rights are the platform's, by the spec's
    group (`rights.reach.group`): the HOST the source names (`cut_at: host`, «Архитектор» 2026-10-06), in one spelling
    — `ACME` and `acme` are one vendor and the vendor is no part of it, `:80` is no part of it, nor the root's dot — so
    every one of those spellings is the recorder's group, and `admin` on camera 3 alone is refused each. A host the
    platform cannot read (`012.0.0.50`, `nvr%2Ecorp`) is refused for everybody, the cluster's administrator too — 400,
    nothing written (ADR 0053: with the grouping declared, no camera is without a group but a file). Moved by the
    cluster's administrator onto the recorder, camera 3 is one of its cameras and a command on it asks for all three;
    moved back onto a file, it is on no device and a command asks for camera 3 alone. "One channel, one camera" is the platform's for one spelling
    (`unique: canonical`) and the holder's for the twins only the VMS reads as one (`…/ch/02` beside `…/ch/2`: «device
    busy», the next test). A command carries the group its rights were asked on (`group`)."""
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
    access = Tokens({"three": [("admin", "vms/3", ())], "guard": [("edit", "vms/3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201   # hers
        for spelt in ("driverpack://ACME/10.0.0.50/ch/2", "driverpack://acme/10.0.0.50:80/ch/9",
                      "driverpack://other/10.0.0.50./ch/9"):
            assert _call(base, "PUT", "/cameras/3", {"source": spelt}, token="three")[0] == 403, spelt   # not hers alone
        for unread in ("driverpack://acme/012.0.0.50/ch/9", "driverpack://acme/nvr%2Ecorp/ch/9", "driverpack://acme/10.1/ch/9"):
            assert _call(base, "PUT", "/cameras/3", {"source": unread}, token="three")[0] in (400, 403), unread
            code, body = _call(base, "PUT", "/cameras/3", {"source": unread}, token="admin")
            assert code == 400 and "source names no host that can be told" in body["detail"], (unread, code, body)
            assert body["fault"] == "bad_url" and unread not in json.dumps(body)
            assert _call(base, "POST", "/cameras", {"source": unread}, token="admin")[0] == 400, unread
        # every refusal of a url by address is `fault: bad_url` at the door, the reason in `detail` (the closed dictionary,
        # `canonical.FAULTS`): a login, no host — a file is a camera only through `driverpack://file/…` (`none`) —, a port
        # that is no number, a scheme the source is not reached by
        for bad in ("rtsp://admin:hunter2@nvr50/ch/1", "file:///media/a.mp4", "/media/a.mp4", "rtsp://nvr50:pw/ch/1",
                    "ftp://nvr50/a", "rtsp://nvr50/ch/1#x"):
            code, body = _call(base, "POST", "/cameras", {"source": bad}, token="admin")
            assert code == 400 and body.get("fault") == "bad_url" and body["detail"], (bad, code, body)
            assert "hunter2" not in json.dumps(body)
        assert box.vars.get("vms/cameras/3")[0]["source"] == "driverpack://file/3.mp4"   # nothing written
        code, body = _call(base, "PUT", "/cameras/3", {"source": "driverpack://ACME/10.0.0.50/ch/2"}, token="admin")
        assert code == 400 and "vms 2 has that source already" in body["detail"], (code, body)          # one address
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://ACME/10.0.0.50:80/ch/9"}, token="admin")[0] == 200
        cmds = ({"unit": "vms/3", "action": "output", "port": 1}, {"unit": "vms/3", "action": "preset", "n": 2})
        for cmd in cmds:
            assert _call(base, "POST", "/requests", cmd, token="guard")[0] == 403, cmd   # on the recorder: all three
        assert _call(base, "POST", "/requests", {"unit": "vms/1", "action": "output", "port": 1, "id": "r-1"}, token="admin")[0] == 202
        assert box.vars.get("vms/requests/r-1")[0]["group"] == "10.0.0.50"               # what the rights were asked on
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://file/3c.mp4"}, token="admin")[0] == 200
        for cmd in cmds:
            assert _call(base, "POST", "/requests", cmd, token="guard")[0] == 202, cmd   # a file: camera 3's alone
            assert _call(base, "POST", "/requests", {**cmd, "unit": "vms/1"}, token="guard")[0] == 403, cmd
        for bad in ('r"2', "r|2", "r\n2"):                                               # a name's rule (`doors.unnamable`)
            assert _call(base, "POST", "/requests", {"unit": "vms/1", "action": "output", "port": 1, "id": bad}, token="admin")[0] == 400
    finally:
        srv.shutdown()


def test_two_spellings_of_one_channel_are_one_camera_to_its_holder_which_says_device_busy():
    """The owner's decision on the boundary's step 6: the platform canonicalises an address by RFC 3986 and does not know
    that `…/ch/02` is `…/ch/2` — that is how the VMS reads its addresses. Both are one group (`group_by: {field: source,
    cut_at: host}`: one host), so one worker holds both, and that worker opens the first by id and says «device busy» of the other in
    its heartbeat (`VmsWorker.held_back`), never dialling it: two pipelines on one channel would be camera 2's picture
    in camera 1's archive (the review's sixth pass). Deleted, the first gives the channel to the second."""
    from vms.worker import FakeActuator, VmsWorker
    box = Box()
    mounts, srv, base = _console_with_jobs(box, Tokens({"admin": [("admin", None, ())]}))
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/2"}, token="admin")[0] == 201
        code, body = _call(base, "POST", "/cameras", {"source": "driverpack://ACME/10.0.0.50/ch/02"}, token="admin")
        assert code == 201, body                                                          # another spelling: the platform takes it
        w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                      resource_root=box.resource_root)
        placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
        w.heartbeat_once(); placer.ensure_placed()
        assert placer.where(1) == placer.where(2) == "w-1"                                # one group, one worker
        w.reconcile_once(); w.heartbeat_once()
        said = {str(s["id"]): s for s in json.loads(box.objects.get(SPEC.sub.heartbeat_key("w-1")))["status"]}
        assert said["2"]["device_state"] == "busy" and "device busy: camera 1" in said["2"]["why"], said
        assert "device_state" not in said["1"] and 1 in w.reconciler.running() and 2 not in w.reconciler.running()
        assert _call(base, "DELETE", "/cameras/1", token="admin")[0] == 200
        placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
        said = {str(s["id"]): s for s in json.loads(box.objects.get(SPEC.sub.heartbeat_key("w-1")))["status"]}
        assert said["2"].get("device_state") != "busy" and 2 in w.reconciler.running()    # the channel is the second's now
    finally:
        srv.shutdown()


def test_a_fragment_or_a_login_in_a_source_names_no_other_device_and_a_labels_change_asks_for_the_whole_device():
    """The product team's additions to the tenth round, reproduced here first. `driverpack://acme/cam7#@10.0.0.50/ch/2`:
    `urlsplit` stops at `#`, so the rights were asked of device `acme/cam7` — nobody's camera, `admin` on camera 3 was
    enough — while a driver that reads past `#` dials the recorder: 200. `#` is refused in every url field, `?` in a
    `driverpack://` source, and a login in the path as in the host (`…/acme/admin:pw@10.0.0.50/…` was taken, password
    and all, into the snapshot). No refusal repeats a password. And a camera's `labels` moved every channel of its
    recorder (the channels move together), with `admin` on that one camera: now the right is asked on each."""
    from vms.config import shown_source, source_refusal
    box = Box()
    access = Tokens({"three": [("admin", "vms/3", ())], "one": [("admin", "vms/1", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        nvr = "driverpack://acme/10.0.0.50/ch/"
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        for spelt in ("driverpack://acme/cam7#@10.0.0.50/ch/9", "rtsp://cam7#@10.0.0.50/x",
                      "driverpack://acme/cam7?@10.0.0.50/ch/9", "driverpack://acme/admin:hunter2@10.0.0.50/ch/9"):
            for token in ("three", "admin"):
                code, body = _call(base, "PUT", "/cameras/3", {"source": spelt}, token=token)
                assert code in (400, 403), (spelt, token, code)
                assert "hunter2" not in json.dumps(body), body
        assert box.vars.get("vms/cameras/3")[0]["source"] == "driverpack://file/3.mp4"
        assert "hunter2" not in (source_refusal("driverpack://acme/u:hunter2@10.0.0.5:8²/ch/1") or "")
        assert shown_source("rtsp://u:hunter2@cam/x") == "rtsp://u:***@cam/x"
        # the labels of camera 1 move channel 2 too: `admin` on camera 1 is not enough, on the cluster it is
        assert _call(base, "PUT", "/cameras/1", {"labels": ["vlan:b"]}, token="one")[0] == 403
        assert _call(base, "PUT", "/cameras/1", {"labels": ["vlan:b"]}, token="admin")[0] == 200
        assert _call(base, "PUT", "/cameras/3", {"labels": ["vlan:b"]}, token="three")[0] == 200   # alone on its device
    finally:
        srv.shutdown()


def test_a_dns_name_and_its_address_are_two_groups_to_the_platform_and_its_second_name_is_the_clusters_to_make():
    """The same finding, the part syntax cannot say: `nvr50.local` and `10.0.0.50` are two keys and one recorder. The
    holder learns what the device IS when it opens it (`identity`) and says a coincidence; rights compared by it in the
    VMS's code on the console (`config.one_device`) until the boundary's step 6. The platform reads no device row: its
    rights go by the spec's group (`rights.reach.group`: the source in its one spelling up to `/ch/`), and two names of
    one recorder are two groups — one spelling is the operator's rule (the owner's decision on step 6). So the second
    name is a group nobody's camera is in, and only the cluster's grant opens it: `admin` on camera 3 is refused it,
    the cluster's administrator is not, and the holder says what it found (`warning` in the camera's status)."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"three": [("admin", "vms/3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    devs = {"acme/10.0.0.50": FakeDevice("acme/10.0.0.50", channels=["1", "2"], relays=2, identity="ACME-SN-0042"),
            "acme/nvr50.local": FakeDevice("acme/nvr50.local", channels=["7"], relays=2, identity="ACME-SN-0042")}
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root, device_factory=lambda k: devs.get(k))
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"     # the holder said what it is
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/9"}, token="three")[0] == 403
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/7"}, token="admin")[0] == 200
        for _ in range(2):
            w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        [st] = [x for x in w.status() if str(x["id"]) == "3"]
        assert "same serial number as acme/10.0.0.50" in st.get("warning", ""), st              # said by the holder
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.50/ch/2"}, token="three")[0] == 403
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.50/ch/2"}, token="admin")[0] == 400   # one address
    finally:
        srv.shutdown()


def _opened(box, *keys, holder: str = "w-held") -> None:
    """Device rows as their holders write them once they have opened the devices and learned what each is (`identity`)
    — and the heartbeat of the live holder that holds them now and has heard them describe themselves (`can`): a row is
    known only while a holder says so (the review's tenth pass). The holder has no room, so
    nothing is placed on it."""
    from w2cplatform.contract import Heartbeat
    for key in keys:
        box.vars.put(f"vms/devices/{key}", {"events": "command", "rays": "0", "relays": "1", "ptz": "false",
                                            "presets": "0", "identity": f"SN-{key}"})
    key_ = SPEC.sub.heartbeat_key(holder)
    raw = box.objects.get(key_)
    had = [d for d in (Heartbeat.from_bytes(raw).extra.get("devices") or []) if d["device"] not in keys] if raw else []
    box.objects.put(key_, Heartbeat(holder, box.wall(), [], {
        "server": "srv-held", "capacity": 0, "headroom": 0,
        "devices": had + [{"device": k, "can": {"events": ["command"], "relays": 1}} for k in keys]}).to_bytes())


def test_a_camera_is_moved_onto_a_device_nobody_has_opened_only_by_a_grant_on_the_cluster():
    """The review's ninth pass, major (a) — a run, and the owner's decision on its question. The eighth pass closed the
    second name at the holder, when the holder learned what the device is — and the course's build has no device
    factory: no holder ever learns it. `admin` on camera 3 moved it onto `nvr50.local/ch/2`, the recorder another
    camera holds as `10.0.0.50`: 200, and its command pulsed the recorder's relay (202). A move to a device no holder
    has opened is now a grant on the whole cluster, whatever the spelling (`source_cams`, `Devices.known`): a DNS name,
    leading zeros, full-width digits, an ideographic full stop, another driver's name for the address. Since the
    boundary's step 6 the platform says it from the spec (`rights.reach.group`): a move into a GROUP no other camera is
    in yet — the host the source names, `group_by` — is the cluster's grant; into one that has cameras, it asks for every
    camera of it; onto a host nobody can tell, it is refused (ADR 0053). (What a holder has learned of a device is no
    part of it: the platform reads no device row.)"""
    from vms.worker import FakeActuator, VmsWorker
    box = Box()
    access = Tokens({"three": [("admin", "vms/3", ())], "three4": [("admin", "vms/3", ()), ("admin", "vms/4", ())],
                     "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root)                           # the course's build: no device factory
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert not box.vars.list("vms/devices/")                       # nobody has learned what any device is
        for spelt in ("driverpack://acme/nvr50.local/ch/2", "driverpack://onvif/10.0.0.50/ch/2",
                      "rtsp://10.0.0.50/Streaming/Channels/201"):
            code, body = _call(base, "PUT", "/cameras/3", {"source": spelt}, token="three")
            assert code == 403, (spelt, code, body)
        # …and a host nobody can tell — leading zeros, full-width digits, an ideographic full stop — is refused for
        # everybody (ADR 0053), before any right is asked
        for spelt in ("driverpack://acme/010.000.000.050/ch/2", "driverpack://acme/１０.０.０.５０/ch/2",
                      "driverpack://acme/10。0。0。50/ch/2"):
            for token in ("three", "admin"):
                code, body = _call(base, "PUT", "/cameras/3", {"source": spelt}, token=token)
                assert code == 400 and "names no host that can be told" in body["detail"], (spelt, token, code, body)
        assert box.vars.get("vms/cameras/3")[0]["source"] == "driverpack://file/3.mp4"
        assert _call(base, "PUT", "/cameras/3", {"name": "still hers"}, token="three")[0] == 200   # nothing moved
        # A group with a camera in it: the move asks for that camera — and, the camera's too, no more.
        _opened(box, "acme/10.0.0.70")
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.70/ch/1"}, token="three")[0] == 403   # nobody's in it yet
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.70/ch/2"}, token="admin")[0] == 201   # camera 4
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.70/ch/1"}, token="three")[0] == 403   # camera 4's
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.70/ch/1"}, token="three4")[0] == 200
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.70/ch/4"}, token="three4")[0] == 200   # within it
        # …and the cluster's administrator may point a camera anywhere, as before
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/9"}, token="admin")[0] == 200
    finally:
        srv.shutdown()


def test_an_empty_word_from_a_device_does_not_unsay_what_it_said_before():
    """The review's ninth pass, major (в) — a run: a recorder that answered two passes without its serial number had its
    row rewritten without one (`describe_devices`); `nvr50.local`, opened meanwhile, took the identity, and after a
    restart the holder refused the recorder by its own name — 0 of its 2 cameras recorded. What a device said before —
    in the holder's memory, or in its row for a holder that has just started — stands until it says something else."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    nvr = FakeDevice("acme/10.0.0.50", channels=["1", "2"], relays=2, identity="ACME-SN-0042")
    alias = FakeDevice("acme/nvr50.local", channels=["2"], relays=2, identity="ACME-SN-0042")
    devs = {"acme/10.0.0.50": nvr, "acme/nvr50.local": alias}
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)

    def holder():
        act = FakeActuator()
        return act, VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, server="srv-1",
                              resource_root=box.resource_root, device_factory=lambda k: devs.get(k))
    act, w = holder()
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"
        nvr.identity = ""                                             # two passes without its serial
        for _ in range(2):
            w.heartbeat_once(); w.reconcile_once()
            assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"   # not unsaid
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/nvr50.local/ch/2"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert w.coincidences == {"acme/nvr50.local": ("acme/10.0.0.50", "ACME-SN-0042")}   # the new name is the one said
        act, w = holder()                                             # a restart, the recorder still silent about itself
        w.heartbeat_once(); w.reconcile_once()
        assert box.vars.get("vms/devices/acme/10.0.0.50")[0]["identity"] == "ACME-SN-0042"   # the row's word stands
        assert {1, 2} <= set(act.running), act.running                # both of the recorder's cameras record
        nvr.identity = "ACME-SN-0042"
        w.heartbeat_once(); w.reconcile_once()
        assert {1, 2, 3} <= set(act.running), act.running
    finally:
        srv.shutdown()


def test_two_devices_with_one_serial_number_are_both_recorded_and_the_coincidence_is_said():
    """The owner's decision on the review's ninth pass (г): a serial number is not unique — firmware clones say the same
    one — and the eighth pass refused the second clone for good, its status pointing at the first clone's address. Both
    open and record now; the coincidence is said (`describe_devices`): in the log once, in the status of the camera
    (`warning`), in the holder's device list (`same_serial_as`), counted on `/metrics`. "One channel, one camera" asks
    by the key, so a clone's channel 1 is not the other clone's; rights go by the spec's group (`rights.reach.group`,
    step 6), which knows no serial number. The other row gone, the warning goes."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    box = Box()
    access = Tokens({"guard": [("edit", "vms/1", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    devs = {k: FakeDevice(k, channels=["1"], relays=1, identity="CLONE-0000") for k in ("acme/10.0.0.50", "acme/10.0.0.60")}
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root, device_factory=lambda k: devs.get(k))
    placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    said: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record):
            said.append(record.getMessage())
    catch = Catch(level=logging.WARNING)
    logging.getLogger("vmsworker").addHandler(catch)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/1"}, token="admin")[0] == 201
        w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.60/ch/1"}, token="admin")[0] == 201
        for _ in range(3):
            w.heartbeat_once(); placer.ensure_placed(); w.reconcile_once()
        assert set(act.running) == {1, 2}                              # both clones record
        assert box.vars.get("vms/devices/acme/10.0.0.60")[0]["identity"] == "CLONE-0000"
        [st] = [x for x in w.status() if str(x["id"]) == "2"]
        assert st["phase"] == "running" and "same serial number as acme/10.0.0.50" in st["warning"], st
        assert "why" not in st
        assert [d.get("same_serial_as") for d in w.device_status()] == [None, "acme/10.0.0.50"]
        assert len([m for m in said if "firmware clones" in m]) == 1   # said once, not every pass
        w.heartbeat_once()
        text = m_text(base)
        assert 'vms_device_identity_coincidences{worker="w-1"} 1' in text, text
        # rights are the platform's, by the spec's group (one address, one group; the boundary's step 6): two clones at
        # two addresses are two devices to it, and the holder is the one that says they may be one
        assert _call(base, "POST", "/requests", {"unit": "vms/1", "action": "output", "port": 1}, token="guard")[0] == 202
        box.vars.delete("vms/devices/acme/10.0.0.50")                  # the operator: the other row is stale
        w.heartbeat_once(); w.reconcile_once()
        assert not w.coincidences and "warning" not in [x for x in w.status() if str(x["id"]) == "2"][0]
    finally:
        logging.getLogger("vmsworker").removeHandler(catch)
        srv.shutdown()


def m_text(base: str) -> str:
    with urllib.request.urlopen(f"{base}/metrics", timeout=10) as r:
        return r.read().decode()


def test_a_camera_moved_to_another_device_asks_for_every_camera_of_the_scenarios_that_command_it():
    """The review's eighth pass, minor: rights on an action are asked when the scenario is written, and a scenario is
    not rewritten when its camera moves. `output` on a camera that was its device's only channel, the camera then
    moved onto a recorder's channel: the scenario pulsed the RECORDER's relay — a port chosen by somebody with no right
    on it. Whoever moves a camera to another device answers for every scenario that commands it: `admin` on every
    unit such a scenario names (the specs' `rights.reach.group` and the scenario's `rights.names`, read by the platform
    since the boundary's step 6). A move inside one device asks for nothing more."""
    nvr = "driverpack://acme/10.0.0.50/ch/"
    box = Box()
    access = Tokens({"mover": [("admin", f"vms/{c}", ()) for c in ("1", "2", "3")],
                     "both": [("admin", f"vms/{c}", ()) for c in ("1", "2", "3", "4")], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"{nvr}{ch}"}, token="admin")[0] == 201
        for f in ("3", "4"):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{f}.mp4"}, token="admin")[0] == 201
        # a host nobody's camera is at: the cluster's to open (`rights.reach.group`, step 6), as before; a file is on no
        # host (`schemes: {driverpack: {none: [file]}}`), and moving a file camera onto another file is the camera's alone
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.77/ch/1"}, token="mover")[0] == 403
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://file/3b.mp4"}, token="mover")[0] == 200   # no scenario yet
        gate = {"name": "gate", "when": [{"sub": "vms", "kind": "motion", "unit": "4"}],
                "then": [{"sub": "vms", "action": "output", "unit": "3", "port": 1}]}
        assert _call(base, "POST", "/auto/scenarios", gate, token="admin")[0] == 201
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}7"}, token="mover")[0] == 403   # the scenario watches camera 4
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}7"}, token="both")[0] == 200    # every camera of it hers
        assert _call(base, "PUT", "/cameras/3", {"source": f"{nvr}8"}, token="mover")[0] == 200   # within the device: as before
    finally:
        srv.shutdown()


def test_a_backfill_nobody_could_answer_is_refused_by_the_recorder_in_its_heartbeat():
    """The reviews' fourth, sixth and seventh passes: a range of thirty-one years, of milliseconds, one that has not
    happened yet, `{"from": 0, "to": 600}` — 1970 — each held one of its person's seven places for a day. The console's
    route refused them; since the boundary's step 6 the platform files a backfill by its shape alone (`requests:`), and
    the recorder judges what only it can — a day at most, a second at least, not in the future, not before anything the
    recording shows (its `retention_days`) — and refuses it in words: in its heartbeat (`requests_refused`), on the
    recording's events (`archive.backfill.refused`), the row closed (`fetched`). The line is about the recording's
    camera (`of: vms/1`), as the recorder's other lines are: it is written through the platform's `observe`, which said
    no `of` until the base stamped it (the architect's rule after step 7) — a query for the camera did not find it."""
    from tests.vmsconftest import recorder
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    rec.create({"name": "1", "cam": "1", "retention_days": 2})
    r = recorder(box)
    r.lease_pass()
    r.rows = [rec.unit("1")]
    r.take_epoch("1")                                # the recording's holder: its epoch, what its lines are written under
    r.may_act = lambda unit: True                    # …its lease its own
    t = box.wall()
    cases = {"day": (t - 40 * 365 * 86400, t, "at most 86400 s"), "ms": (t - 60, t - 59.5, "at least 1 s"),
             "future": (t + 3600, t + 7200, "from now"), "1970": (0.5, 600, "before anything the recording shows"),
             "old": (t - 3 * 86400, t - 2 * 86400 - 60, "before anything the recording shows")}
    for rid, (a, b, _) in cases.items():
        box.vars.put(REC_SPEC.sub.request_key(rid), {"unit": "1", "cam": "1", "from": str(a), "to": str(b), "by": "guard"})
    r.requests(budget=10)
    said = r.heartbeat_extra()
    for rid, (_, _, why) in cases.items():
        assert why in said["requests_refused"][rid] and rid in r.requests_fields()["fetched"].split(","), (rid, said["requests_refused"])
    import glob
    from w2cplatform.events import read_bucket
    lines = [ln for p in glob.glob(os.path.join(r.resource_root, "rec", "1", "e*", "*.events.jsonl")) for ln in read_bucket(p)]
    refused = [ln for ln in lines if ln["kind"] == "archive.backfill.refused"]
    assert sorted(ln["request"] for ln in refused) == sorted(cases) and {ln.get("of") for ln in refused} == {"vms/1"}, refused


def _raw_call(url, method="GET", body: bytes | None = None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_the_door_in_is_the_consoles_alone_and_takes_a_token_or_an_emergency_entry_and_nothing_else():
    """The product's own finding on the review's ninth pass (C): its `POST /session/break-glass` was served by every door
    that mounts the shared gate — a recorder, the live gateway. Here `/session` is routed by the console alone; swept
    door by door — the holder's playback door, the live gateway, a recorder's archive door, the resource — none answers
    it, and none opens an emergency session. And the gate a door holds does not take the console's emergency session
    either (`Gate(glass=False)`): one opened at the console, in the same process, was a viewer at the gateway. At the
    console a body that is not an object holding a string token — a list, a token that is a list or a number, nested
    brackets, no JSON at all — is 400 (the review's ninth pass, minor: it was no answer at all, the handler raised)."""
    from types import SimpleNamespace
    from tests.test_lesson8_live import OFFER, _gateway
    from vms.recworker import RecWorker
    from w2cplatform.resource import platform_resource
    from vms.worker import FakeActuator, VmsWorker
    from w2cplatform.access import GLASS_COOKIE
    from w2cplatform.resource import serve as serve_resource
    Gate.forget_glass(); held = dict(Gate._glass)          # sessions other tests left in this process
    box = Box()
    access = Tokens({"admin": [("admin", None, ())], "viewer": [("view", "vms/1", ())]})
    ctl, rec, m, srv, base = _console(box, access)
    from tests.conftest import door_keys
    with door_keys(box.vars) as keys:                  # the gateway checks the console's door token by `door/keys`
        g = _gateway(box, "g-1")
        door_token = keys.signer.issue("viewer", "live/1", "g-1", ("whep",), box.wall())[0]
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root)
    holder = w.serve_playback("127.0.0.1", 0)
    rec_door = RecWorker.serve_archive(SimpleNamespace(store=None, wall=box.wall, epochs={}, server="srv-1", name="r-1",
                                                       objects=box.objects, vars=box.vars, resource_root=None, eyes=None,
                                                       _visible_from=lambda *a: None, _kept_of=lambda *a: None,
                                                       _held_since=lambda *a: None), "127.0.0.1", 0)
    res = serve_resource(platform_resource(box.resource_root, "srv-1", "", box.vars, box.objects, wall=box.wall), "127.0.0.1", 0)
    doors = {"holder": f"http://127.0.0.1:{holder.server_address[1]}", "gateway": g.url,
             "recorder": f"http://127.0.0.1:{rec_door.server_address[1]}", "resource": f"http://127.0.0.1:{res.server_address[1]}"}
    entry = json.dumps({"who": "carol", "why": "the domain is down", "password": "open-sesame"}).encode()
    try:
        for name, url in doors.items():
            for path in ("/session", "/session/break-glass"):
                code, _, hdrs = _raw_call(url + path, "POST", entry, {"Content-Type": "application/json"})
                assert code in (404, 405, 501) and "Set-Cookie" not in hdrs, (name, path, code)
            assert _raw_call(url + "/session")[0] in (404, 405, 501), name
        assert Gate._glass == held                                     # nothing was opened anywhere
        for bad in (b"[1]", b'{"token": ["a", "b"]}', b'{"token": 7}', b"[" * 8000 + b"]" * 8000, b"{not json"):
            code, body, _ = _raw_call(base + "/session", "POST", bad, {"Content-Type": "application/json"})
            assert code == 400, (bad[:20], code, body[:200])
        code, _, hdrs = _raw_call(base + "/session/break-glass", "POST", entry, {"Content-Type": "application/json"})
        assert code == 200 and hdrs["Set-Cookie"].startswith(GLASS_COOKIE + "="), (code, hdrs)   # the console's door
        sid = hdrs["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
        assert _call(base, "GET", "/cameras", token=None)[0] == 401
        assert _raw_call(base + "/cameras", headers={"Cookie": f"{GLASS_COOKIE}={sid}"})[0] == 200   # …in its own process
        code, _, _ = _raw_call(g.url + "/whep/1", "POST", OFFER.encode(),
                               {"Content-Type": "application/sdp", "Cookie": f"{GLASS_COOKIE}={sid}"})
        assert code == 401, code                                       # the gateway takes a door token, not the console's session
        assert _raw_call(g.url + "/whep/1", "POST", OFFER.encode(),
                         {"Content-Type": "application/sdp", "Authorization": f"Bearer {door_token}"})[0] == 404   # a token: admitted
    finally:
        for s in (srv, holder, rec_door, res):
            s.shutdown()
        Gate._glass.clear(); Gate._glass.update(held)


def test_a_press_of_a_relay_and_a_move_of_a_camera_read_the_rows_of_their_devices_not_every_device_row():
    """The review's ninth pass, minor — a count: `one_device` read every device row there is on every command, move and
    scenario edit; rows are never removed, and with 1000 of them one press of a relay was 1009 reads of the store (in
    М11, a thousand HTTP calls to Nomad). A device's row is read when a right is asked about that device, once a
    request (`config.Devices`, until the boundary's step 6 — the platform reads none now), and "one channel, one camera"
    reads none (`refuse_camera`). Counted as here — every
    read of the process, the gate's too — before and after: 1013 → 14 for the press, 2019 → 19 for the move; pinned with
    room, and not growing with the stale rows."""
    from w2cplatform.variables import FileVariables
    box = Box()
    for i in range(1000):                                              # devices that came and went: their rows stay
        box.vars.put(f"vms/devices/acme/10.1.{i // 250}.{i % 250}", {"events": "command", "relays": "1", "identity": f"SN-{i}"})
    box.vars.put("vms/devices/acme/10.0.0.50", {"events": "command", "relays": "2", "identity": "SN-NVR"})
    mounts, srv, base = _console_with_jobs(box, Tokens({"admin": [("admin", None, ())]}))
    reads = [0]
    real = FileVariables.get

    def counted(self, path):
        reads[0] += 1
        return real(self, path)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.50/ch/{ch}"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        FileVariables.get = counted
        assert _call(base, "POST", "/requests", {"unit": "vms/1", "action": "output", "port": 1}, token="admin")[0] == 202
        press, reads[0] = reads[0], 0
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.50/ch/7"}, token="admin")[0] == 200
        move = reads[0]
    finally:
        FileVariables.get = real
        srv.shutdown()
    print(f"reads: a press of a relay {press}, a move of a camera {move} (1000 stale device rows)")
    assert press <= 40 and move <= 50, (press, move)


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


def test_a_device_nobody_holds_a_camera_of_is_the_clusters_whatever_a_row_says():
    """The review's tenth pass, major — a run: the old recorder `nvr50.local` (row `SN-OLD`, its cameras deleted) was
    replaced, the name led to the new one, and `admin` on camera 3 pointed it at `nvr50.local/ch/2` — 200 by the stale
    row. Since the boundary's step 6 the platform reads no device row at all: a move into a group nobody's camera is in
    is the cluster's grant, whatever any row says; into one that has cameras, it asks for each of them."""
    box = Box()
    access = Tokens({"three": [("admin", "vms/3", ()), ("admin", "vms/4", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        for ch in (1, 2):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://acme/10.0.0.42/ch/{ch}"}, token="admin")[0] == 201
        for f in ("3", "4"):
            assert _call(base, "POST", "/cameras", {"source": f"driverpack://file/{f}.mp4"}, token="admin")[0] == 201
        box.vars.put("vms/devices/acme/nvr50.local", {"events": "command", "relays": "1", "identity": "SN-OLD"})   # the past
        _opened(box, "acme/nvr50.local")                              # …and a holder saying it holds it: no matter
        code, body = _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/2"}, token="three")
        assert code == 403, (code, body)
        assert _call(base, "PUT", "/cameras/4", {"source": "driverpack://acme/nvr50.local/ch/5"}, token="admin")[0] == 200
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/nvr50.local/ch/2"}, token="three")[0] == 200   # 4 is hers
        assert _call(base, "PUT", "/cameras/3", {"source": "driverpack://acme/10.0.0.42/ch/7"}, token="three")[0] == 403    # 1 and 2 are not
    finally:
        srv.shutdown()


def test_a_port_or_channel_in_digits_that_are_not_ascii_stops_neither_the_holder_nor_the_console():
    """The review's tenth pass, major: `isdigit` then `int` on `²`, `①` in a source's port or channel. A camera row stored
    with `…:8²/ch/1` before the canonical key made its holder raise in `reconcile_once` and `heartbeat_once` on every
    pass — no status, no commands for any of its cameras — and the console could create no camera at all (500: one
    channel, one camera reads every row). By `doors.numeric` now: such a source is a key of its own, that camera's
    trouble. What is not an address by RFC 3986 — `rtsp://[…` (`urlsplit` raised), a port past 65535 — the platform
    refuses at the door (400); what only the VMS reads in an address — a port written in its path, a channel in digits
    that are not 0–9 — is the holder's since the boundary's step 6: the row is taken, the holder does not dial it and
    says why in its heartbeat (`VmsWorker.held_back`). A source nobody can read a device from is still the cluster's
    grant to point a camera at, never the open path."""
    from vms.config import channel_key, device_of, source_refusal
    from vms.worker import FakeActuator, VmsWorker
    for raw in ("driverpack://acme/10.0.0.5:8²/ch/1", "driverpack://acme/10.0.0.5/ch/①", "rtsp://[10.0.0.5/x",
                "rtsp://h:8²/x", "driverpack://acme/h:" + "9" * 5000 + "/ch/1"):
        device_of(raw), channel_key(raw)                              # no `ValueError` out of any reader
        assert source_refusal(raw), raw
    assert channel_key("driverpack://acme/h/ch/" + "9" * 5000) == "9" * 5000   # past what `int` takes: a name
    assert device_of("driverpack://acme/10.0.0.5:8²/ch/1") == "acme/10.0.0.5:8²"
    assert channel_key("driverpack://acme/10.0.0.5/ch/①") == "①" and channel_key("driverpack://acme/h/ch/007") == "7"
    assert source_refusal("driverpack://acme/10.0.0.5:8080/ch/2") is None and source_refusal("rtsp://[::1]:554/x") is None
    box = Box()
    access = Tokens({"three": [("admin", "vms/3", ())], "admin": [("admin", None, ())]})
    mounts, srv, base = _console_with_jobs(box, access)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/1"}, token="admin")[0] == 201
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/3.mp4"}, token="admin")[0] == 201
        for i, bad in enumerate(("driverpack://acme/10.0.0.5:8²/ch/1", "driverpack://acme/10.0.0.6/ch/①")):
            box.vars.put(f"vms/cameras/{10 + i}", {"id": str(10 + i), "name": f"old{i}", "source": bad, "revision": "1"})
        w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                      resource_root=box.resource_root)
        placer = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
        w.heartbeat_once(); placer.ensure_placed()
        w.reconcile_once(); w.heartbeat_once()                        # neither raises
        hb = json.loads(box.objects.get(SPEC.sub.heartbeat_key("w-1")))
        assert {str(s["id"]) for s in hb["status"]} >= {"1", "2", "10", "11"}, hb["status"]
        said = {str(s["id"]): s for s in hb["status"]}
        assert all(said[c].get("device_state") == "refused" and "not opened" in said[c]["why"] for c in ("10", "11")), said
        assert said["1"].get("device_state") != "refused"
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/2"}, token="admin")[0] == 201
        for bad in ("rtsp://[10.0.0.7/x", "rtsp://10.0.0.7:99999/x"):     # not an address by RFC 3986: the platform's
            code, body = _call(base, "POST", "/cameras", {"source": bad}, token="admin")
            assert code == 400 and ("port" in body["detail"] or "address" in body["detail"]), (bad, code, body)
            assert _call(base, "PUT", "/cameras/3", {"source": bad}, token="three")[0] == 403       # the cluster's grant
            assert _call(base, "PUT", "/cameras/3", {"source": bad}, token="admin")[0] == 400       # …and then refused
        made = []
        for bad in ("driverpack://acme/10.0.0.7:8²/ch/1", "driverpack://acme/10.0.0.7/ch/①"):   # the VMS's words: its holder's
            assert _call(base, "PUT", "/cameras/3", {"source": bad}, token="three")[0] == 403       # the cluster's grant still
            code, body = _call(base, "POST", "/cameras", {"source": bad}, token="admin")
            assert code == 201, (bad, code, body)
            made.append(str(body["id"]))
        placer.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
        said = {str(s["id"]): s for s in json.loads(box.objects.get(SPEC.sub.heartbeat_key("w-1")))["status"]}
        assert all(said[c].get("device_state") == "refused" for c in made), said
        assert not set(made) & {str(c) for c in w.reconciler.running()}             # never dialled
    finally:
        srv.shutdown()


def test_a_relay_port_written_in_a_digit_that_is_not_ascii_is_a_misfit_and_not_a_500():
    """The tenth pass's sweep of `isdigit` then `int` (`vms/auto.py`, the scenario's catalogue check, and М12's
    `domain/scenario.py`): `"²".isdigit()` is true and `int` raised out of the check — a 500 to whoever wrote the
    scenario. By `doors.numeric` now: a port that is no number is a misfit like port 9 of a device with two relays — said
    by the evaluator since the boundary's step 6 (`Catalog.check`, a scenario `refused` in its heartbeat), never a 500."""
    from vms.auto import Catalog
    box = Box()
    mounts, srv, base = _console_with_jobs(box, Tokens({"admin": [("admin", None, ())]}))
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://acme/10.0.0.50/ch/1"}, token="admin")[0] == 201
        _opened(box, "acme/10.0.0.50")                                # its device said: one relay
        for i, port in enumerate(("²", "١", "2")):
            then = [{"sub": "vms", "action": "output", "unit": "1", "port": port}]
            code, body = _call(base, "POST", "/auto/scenarios", {"name": f"s{i}", "when": [{"sub": "vms", "kind": "motion"}],
                               "then": then}, token="admin")
            assert code == 201, (port[:5], code, body)                # the shape is right: the door takes it
            misfit, _ = Catalog(box.vars).check({"when": [{"sub": "vms", "kind": "motion"}], "then": then})
            assert any("relay" in m for m in misfit), (port[:5], misfit)
    finally:
        srv.shutdown()


def test_an_id_that_is_no_id_is_a_400_in_words_on_every_route_that_takes_one():
    """The coordinator's find in the twelfth round: `GET /where/None` dropped the connection — `parse_id` raised out of
    `dispatch` — and `PUT`/`DELETE /cameras/x` answered 500 "the write failed". Swept over every mount and every family
    that takes an id, with ids that are no id: nothing drops, nothing is a 5xx, and the routes that read an id say 400
    in words. `..` among them (the review's thirteenth pass, minor): a NAME the store refuses as a key — `PUT`/`DELETE` on
    `/rec/recordings/..`, `/detjob/jobs/..`, `/auto/scenarios/..` were 500."""
    import http.client
    box = Box()
    *_, srv, base = _console_with_jobs(box, None)
    try:
        bad_ones = []
        for bad in ("None", "x", "1.5", "%00", "..", "."):
            for prefix in ("", "/rec", "/det", "/detjob", "/auto"):
                for fam in ("where", "cameras", "recordings", "units", "jobs", "scenarios", "timeline", "export", "whep"):
                    for method in ("GET", "PUT", "DELETE"):
                        try:
                            st, _ = _call(base, method, f"{prefix}/{fam}/{bad}", {} if method == "PUT" else None)
                        except (http.client.RemoteDisconnected, ConnectionError, urllib.error.URLError) as e:
                            st = type(e).__name__
                        if not isinstance(st, int) or st >= 500:
                            bad_ones.append((method, f"{prefix}/{fam}/{bad}", st))
        assert bad_ones == [], bad_ones
        st, out = _call(base, "GET", "/where/None")
        assert st == 400 and "not an id of vms" in out["detail"] and "whole numbers" in out["detail"], out
        assert _call(base, "PUT", "/cameras/x", {"name": "n"})[0] == 400
        assert _call(base, "DELETE", "/cameras/x")[0] == 400
        st, out = _call(base, "PUT", "/rec/recordings/..", {})
        assert st == 400 and "one segment" in out["detail"], out
    finally:
        srv.shutdown()

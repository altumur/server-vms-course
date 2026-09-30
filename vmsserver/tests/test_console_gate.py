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
from vms.archive import ArchiveResource
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
    m = make_console(ctl, ArchiveResource(box.spool, box.archive, wall=box.wall), box.wall, mounts={"rec": rec})
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

        # the name in the journal is the one the token proved — whatever the header said
        assert _call(base, "DELETE", "/cameras/2", token="admin", user="somebody-else")[0] == 200
        said = _audit(box)
        assert ("unit.deleted", "admin") in said and ("unit.deleted", "somebody-else") not in said
        assert ("access.denied", "viewer") in said

        # a mount is gated by the same rules, and its own routes: a keep is an operator's, a volume an administrator's
        t = box.wall()
        keep = {"cam": "1", "from": t - 900, "to": t - 300}
        assert _call(base, "POST", "/rec/keeps", keep, token="viewer")[0] == 403
        assert _call(base, "POST", "/rec/keeps", {**keep, "cam": "2"}, token="guard")[0] == 403
        assert _call(base, "POST", "/rec/keeps", keep, token="admin")[0] == 201
        vol = {"name": "cold", "kind": "network", "url": "s3://vms/x", "quota_bytes": 10 ** 12}
        assert _call(base, "POST", "/rec/volumes", vol, token="guard")[0] == 403 and _call(base, "POST", "/rec/volumes", vol, token="admin")[0] == 201

        # the one local account: admitted, and every use is an alarm with the person's name in it
        assert _call(base, "GET", "/cameras", token="glass:carol")[0] == 200
        alarms = [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]
        assert [(e["kind"], e["user"]) for e in alarms] == [("access.break_glass", "break-glass(carol)")]
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
    assert recs.needs("DELETE", "/recordings/1-cloud") == ("admin", str(cam), [])        # a recording is its camera's
    assert recs.needs("POST", "/keeps")[0] == "edit" and recs.needs("POST", "/volumes")[0] == "admin"
    assert root.needs("POST", "/marks", str(cam)) == ("edit", str(cam), ["ground"]) and recs.needs("POST", "/keeps", str(cam)) == ("edit", str(cam), [])
    assert token_of({"Authorization": "Bearer abc"}) == "abc" and token_of({"Cookie": "a=b; w2c_token=xyz"}) == "xyz"
    assert token_of({}) is None and token_of({"Authorization": "Basic abc"}) is None

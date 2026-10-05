"""Where a PLACE is held (`w2cplatform/console.py`, `SpecConsole.where_place`; the architect's decision after step 7):
`GET /<sub>/where/<table>/<place>?unit=<sub>/<id>` — the worker holding a place of the spec's `placement.places` now,
and its door for that unit, as `/where/<id>` hands out a unit's. On testsub2, whose units are kept on shelves: the
console has no byte routes of its own, so what a unit left on a shelf another worker holds now is read at THAT worker's
door, with a token for that holder, that unit and the spec's routes."""
import json
import os
import tempfile
import urllib.error
import urllib.request

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def _get(base, path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=10) as r:
            return r.status, json.loads(r.read() or b"null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Idempotency-Key": os.urandom(6).hex()})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


class _Grants:
    """An `Access` with no cryptography: a token is a name, a grant a unit (`tests/test_console_gate.py`'s, cut down)."""

    def __init__(self, grants):
        self.grants = grants                                           # {subject: [unit or None]}

    def who(self, token):
        from w2cplatform.access import Denied
        if token not in self.grants:
            raise Denied(401, "token refused: nobody's")
        return {"sub": token}

    def may(self, payload, capability, unit, labels):
        mine = self.grants[payload["sub"]]
        return bool(mine) if unit is None and capability == "view" else any(u in (unit, None) for u in mine)

    def by_labels(self, payload, capability):
        return False


def _site():
    """The deployment's console over testsub (at `/`) and testsub2 (at `/testsub2`), from the specs alone, with a key
    ring (`SECRETS_KEY`), so the console signs door tokens; three shelves — `s1` on srv-1, `s2` on srv-2, `s3` not
    enabled (no place: `where: {enabled: true}`) — and the tally `t1`."""
    from w2cplatform import host
    root = tempfile.mkdtemp(prefix="where-place-")
    ring = os.path.join(root, "platform.key")
    with open(ring, "w") as f:
        f.write(f"k1 {os.urandom(32).hex()}\n")
    env = {"SPEC_DIR": TESTDATA, "PLATFORM_DIR": root, "CONSOLE_ROOT": "testsub", "SECRETS_KEY": ring}
    was = os.environ.get("SECRETS_KEY")
    os.environ["SECRETS_KEY"] = ring                    # the console's controller seals with the ring of its process
    try:
        m, ctls = host.build_console(env)
    finally:
        os.environ.pop("SECRETS_KEY", None) if was is None else os.environ.__setitem__("SECRETS_KEY", was)
    srv = m.serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    assert _post(base, "/counters", {"name": "c1"}) in (200, 201)
    assert _post(base, "/testsub2/tallies", {"name": "t1", "of": "c1"}) in (200, 201)
    for name, server, enabled in (("s1", "srv-1", True), ("s2", "srv-2", True), ("s3", "srv-3", False)):
        assert _post(base, "/testsub2/shelves", {"name": name, "server": server, "enabled": enabled}) in (200, 201)
    raw_vars, _ = host.stores(env)
    return m, ctls, srv, base, raw_vars


def _beat(ctls, worker, shelf, instance, url):
    from w2cplatform.contract import Heartbeat
    ctl = ctls["testsub2"]
    ctl.objects.put(f"testsub2/heartbeats/{worker}", Heartbeat(worker, ctl.wall(), [], {
        "server": "srv-1", "shelf": shelf, "instance": instance, "url": url}).to_bytes())


def test_a_places_holder_is_found_and_its_door_opens_for_the_unit_asked_and_that_holder_alone():
    """The live worker whose heartbeat names the shelf (`place_by: shelf`) and announces a door holds it: the answer is
    `/where/<id>`'s — `{worker, place, server, door: {url, token, expires, routes}}` — the token for THAT holder, the
    unit named in `?unit=` and the spec's routes (`door: {routes: [read, play]}`), checked by the cluster's public keys:
    another holder, another unit refused. Two heartbeats on one shelf are told apart by the shelf's live hold. No unit
    named: the holder, no door. `/spec` names the table of places; the place's table is the only one after `/where/`."""
    from w2cplatform.door import DoorRefused, Ring
    m, ctls, srv, base, raw = _site()
    try:
        st, spec, _ = _get(base, "/testsub2/spec")
        assert spec["places"] == {"table": "shelves"}, spec.get("places")
        _beat(ctls, "t-1", "s1", "i-1", "http://holder-1:9000/")
        st, got, _ = _get(base, "/testsub2/where/shelves/s1?unit=testsub2/t1")
        assert st == 200 and got["worker"] == "t-1" and got["place"] == "s1" and got["server"] == "srv-1", (st, got)
        door = got["door"]
        assert door["url"] == "http://holder-1:9000" and door["routes"] == ["read", "play"] and door["token"], door
        ring = Ring(raw)
        now = ctls["testsub2"].wall()
        assert ring.check(door["token"], unit="testsub2/t1", holder="t-1", route="read", now=now)
        for kw, reason in (({"holder": "t-2"}, "holder"), ({"unit": "testsub2/t9"}, "unit"), ({"route": "write"}, "route")):
            try:
                ring.check(door["token"], **{"unit": "testsub2/t1", "holder": "t-1", "route": "read", "now": now, **kw})
                raise AssertionError(kw)
            except DoorRefused as e:
                assert e.reason == reason, (kw, e.reason)

        st, got, _ = _get(base, "/testsub2/where/shelves/s1")
        assert st == 200 and got["worker"] == "t-1" and got["door"] is None, got        # a token is one unit's
        assert _get(base, "/testsub2/where/shelves/s1?unit=testsub/c1")[0] == 400       # another subsystem's unit
        assert _get(base, "/testsub2/where/shelves/s1?unit=t1")[0] == 400               # a bare id names nobody's unit
        assert _get(base, "/testsub2/where/marks/x")[0] == 404                          # not the table of places
        assert _get(base, "/testsub2/where/shelves/s1/x")[0] == 404
        st, got, _ = _get(base, "/testsub2/where/shelves/s3?unit=testsub2/t1")
        assert st == 404 and got["error"] == "no such place", got                       # not enabled: no place
        assert _get(base, "/testsub2/where/shelves/nope")[1]["error"] == "no such place"

        _beat(ctls, "t-2", "s1", "i-2", "http://holder-2:9000")                        # a second word for the shelf…
        raw.put("testsub2/holds/s1", {"holder": "i-2", "until": now + 30, "released": "false", "gen": 1, "by": "t-2"})
        st, got, _ = _get(base, "/testsub2/where/shelves/s1?unit=testsub2/t1")
        assert st == 200 and got["worker"] == "t-2" and got["door"]["url"] == "http://holder-2:9000", got   # …the hold's
        assert ring.check(got["door"]["token"], unit="testsub2/t1", holder="t-2", route="play", now=now)
    finally:
        srv.shutdown(); srv.server_close()


def test_a_place_nobody_holds_is_said_with_its_server_in_the_unreachable_header():
    """Nobody holding an enabled shelf: 404, `door: null`, `reason` in words, and the place as `<place>@<server>` (its
    row's `server_field`) in `unreachable` and in the header `X-Unreachable` — what a page names as missing from its
    picture. A worker of another shelf is no holder of this one."""
    m, ctls, srv, base, raw = _site()
    try:
        _beat(ctls, "t-1", "s1", "i-1", "http://holder-1:9000")
        st, got, headers = _get(base, "/testsub2/where/shelves/s2?unit=testsub2/t1")
        assert st == 404 and got["worker"] is None and got["door"] is None and got["unreachable"] == "s2@srv-2", got
        assert headers.get("X-Unreachable") == "s2@srv-2" and "nobody holds s2" in got["reason"], headers
        _beat(ctls, "t-3", "s2", "i-3", "")                                              # it says the shelf, no door
        assert _get(base, "/testsub2/where/shelves/s2?unit=testsub2/t1")[2].get("X-Unreachable") == "s2@srv-2"
    finally:
        srv.shutdown(); srv.server_close()


def test_a_places_door_is_asked_with_the_rights_of_the_unit_it_is_for():
    """The gate asks `view` on the unit named in `?unit=`, as on `/where/<id>`: a grant on that unit (or the cluster's)
    gets the door, a grant on another unit is 403 — the holder of a shelf holds what every unit left on it, and the token
    opens one unit's. With no unit named, any grant may ask who holds a place (a list of places is everybody's to read)."""
    m, ctls, srv, base, raw = _site()
    access = _Grants({"ann": ["testsub2/t1"], "bob": ["testsub2/t9"]})
    for con in (m.root, *m.mounts.values()):
        con.gate.impl = access
    try:
        _beat(ctls, "t-1", "s1", "i-1", "http://holder-1:9000")
        st, got, _ = _get(base, "/testsub2/where/shelves/s1?unit=testsub2/t1", token="ann")
        assert st == 200 and got["door"]["token"], (st, got)
        assert _get(base, "/testsub2/where/shelves/s1?unit=testsub2/t1", token="bob")[0] == 403
        assert _get(base, "/testsub2/where/shelves/s1?unit=testsub2/t1")[0] == 401
        st, got, _ = _get(base, "/testsub2/where/shelves/s1", token="bob")
        assert st == 200 and got["worker"] == "t-1" and got["door"] is None, got
    finally:
        srv.shutdown(); srv.server_close()


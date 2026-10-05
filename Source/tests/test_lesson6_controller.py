"""Lesson 6 — vmscontroller: the only writer; refusals; placement with its
property tests; two controllers; the read model; the failure arithmetic."""
import json
import os
import threading
import time
import urllib.request
from vms.console import serve
from vms.controller import Refused, VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.vmsconftest import Box


def test_crud_by_cas_and_what_it_refuses():
    box = Box(); ctl = VmsController(box.vars, box.objects, wall=box.wall)
    r = ctl.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"})
    assert r["id"] == 1 and r["revision"] == 1 and ctl.camera(1)["name"] == "gate"
    assert ctl.update_camera(1, {"events_retention_days": 14})["revision"] == 2
    for bad in ({"worker": "w-1"}, {"revision": 9}, {"phase": "running"}, {"epoch": 3}, {"placement": {}}):
        try:
            ctl.update_camera(1, bad); raise AssertionError("must refuse")
        except Refused as e:
            assert "may not set" in str(e)
    try:
        ctl.create_camera({"name": "x"}); raise AssertionError()
    except Refused as e:
        assert "needs a source" in str(e)
    ctl.delete_camera(1)
    assert ctl.camera(1) is None and ctl.cameras() == []


def test_placement_is_stored_with_a_reason_and_adding_a_worker_moves_nothing():
    box = Box(); ctl = VmsController(box.vars, box.objects, capacity=3, wall=box.wall)
    for i in range(6):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    placed = ctl.ensure_placed(workers=["w-1", "w-2"])
    assert len(placed) == 6 and all(p.reason.startswith("most free capacity") for p in placed)
    before = {c["id"]: ctl.where(c["id"]) for c in ctl.cameras()}
    assert sorted(before.values()).count("w-1") == 3 and sorted(before.values()).count("w-2") == 3
    assert ctl.create_camera({"source": "driverpack://file/7.mp4"}) and ctl.place(7, workers=["w-1", "w-2"]) is None   # the system is full
    ctl.ensure_placed(workers=["w-1", "w-2", "w-3"])                        # a worker arrives
    assert {c: ctl.where(c) for c in before} == before and ctl.where(7) == "w-3"    # nothing moved; the new one went to the new worker
    assert ctl.placement(7).rev == 1 and ctl.placement(7).at == box.wall()


def test_capacity_is_the_workers_word_not_the_controllers():
    """Two workers on different hardware say different numbers in their
    heartbeats; the controller places by what they said and its own constant
    is only the fallback for a worker that said nothing."""
    box = Box(); ctl = VmsController(box.vars, box.objects, capacity=50, wall=box.wall)
    small = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=2)
    big = VmsWorker("w-2", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=6)
    small.heartbeat_once(); big.heartbeat_once()
    assert (ctl.capacity_of("w-1"), ctl.capacity_of("w-2"), ctl.capacity_of("w-9")) == (2, 6, 50)
    for i in range(9):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    placed = ctl.ensure_placed()
    assert len(placed) == 8 and ctl.load("w-1") == 2 and ctl.load("w-2") == 6    # the ninth waits: the system is full
    assert ctl.place(9) is None and ctl.headroom() == 8                            # headroom is stale until they heartbeat again
    small.reconcile_once(); big.reconcile_once(); small.heartbeat_once(); big.heartbeat_once()
    assert ctl.headroom() == 0
    assert "(6)" in ctl.placement(1).reason or "(6)" in ctl.placement(2).reason    # the reason says whose number it was


def test_two_controllers_agree_by_cas():
    box = Box()
    a = VmsController(box.vars, box.objects, capacity=100, wall=box.wall)
    for i in range(40):
        a.create_camera({"source": f"driverpack://file/{i}.mp4"})
    def race(prefer):
        c = VmsController(box.vars, box.objects, capacity=100, wall=box.wall)
        for cam in c.cameras():
            c.place(cam["id"], workers=prefer)
    ts = [threading.Thread(target=race, args=(w,)) for w in (["w-1", "w-2"], ["w-2", "w-1"])]
    [t.start() for t in ts]; [t.join() for t in ts]
    c = VmsController(box.vars, box.objects, wall=box.wall)
    where = {cam["id"]: c.where(cam["id"]) for cam in c.cameras()}
    assert len(where) == 40 and all(where.values())
    units = c.assignment("w-1").units + c.assignment("w-2").units
    assert sorted(int(u) for u in units) == list(range(1, 41))              # every camera exactly once, whoever won


def test_rebalance_is_explicit_budgeted_and_stops_in_the_dead_band():
    box = Box(); ctl = VmsController(box.vars, box.objects, capacity=10, wall=box.wall)
    for i in range(8):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.ensure_placed(workers=["w-1"])                                       # all eight on w-1
    assert ctl.rebalance(budget=0, workers=["w-1", "w-2"]) == []             # no budget, no moves
    moves = ctl.rebalance(budget=3, workers=["w-1", "w-2"])
    assert len(moves) == 3 and all(m[1] == "w-1" and m[2] == "w-2" for m in moves)
    assert "rebalance" in ctl.placement(moves[0][0]).reason
    assert ctl.load("w-1") == 5 and ctl.load("w-2") == 3
    assert ctl.rebalance(budget=5, workers=["w-1", "w-2"]) == [(m, "w-1", "w-2") for m in [4]]   # one more, then inside the dead band


def test_the_failure_arithmetic():
    """Stop each process in turn and say what stopped."""
    box = Box(); ctl = VmsController(box.vars, box.objects, wall=box.wall)
    for i in range(1, 3):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall)
    w.heartbeat_once(); ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()
    assert act.running == {1, 2}
    # controller down: the read model still answers (heartbeats), recording continues, edits stop
    rows = VmsController(box.vars, box.objects, wall=box.wall).read_model()
    assert [r["phase"] for r in rows] == ["running", "running"]
    # worker down: the console shows the last snapshot with its age — how long IT has seen the heartbeat stand still
    # (r29-writers2) —; edits still land in the store
    ctl.read_model()
    box.wall.advance(100)
    ctl.update_camera(1, {"name": "edited while w-1 was down"})
    rows = ctl.read_model(lost_after=45)
    assert rows[0]["worker_state"] == "stale" and rows[0]["age"] == 100.0
    # ...and are applied the moment the worker is back — from the store, not from the controller
    w2 = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall)
    assert w2.reconcile_once() == [("start", 1), ("start", 2)] and w2.rows[0]["name"] == "edited while w-1 was down"


def test_scale_in_releases_a_slot_and_the_controller_redistributes():
    """Nomad decided `count` 3 → 2. The worker it stops releases its slot;
    the controller's placement pass moves that slot's cameras — its one
    unasked move — and nothing else. A crash releases nothing and moves nothing."""
    box = Box(); ctl = VmsController(box.vars, box.objects, capacity=4, wall=box.wall)
    ws = [VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4) for _ in range(3)]
    for w in ws:
        w.heartbeat_once()
    for i in range(1, 7):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.ensure_placed()
    assert {w: len(a.units) for w, a in ctl.assignments().items()} == {"w-1": 2, "w-2": 2, "w-3": 2}
    assert ctl.headroom() == 12 and ctl.redistribute() == []           # nothing released: nothing moves
    box.wall.advance(46)                                               # w-3 crashed: silent, not released
    ws[0].heartbeat_once(); ws[1].heartbeat_once()
    assert ctl.redistribute() == [] and ctl.where(3) == "w-3"          # a crash is Nomad's to fix; the cameras wait for w-3
    ws[2].release_slot()                                               # scale-in: SIGTERM, an orderly stop
    moves = ctl.redistribute()
    assert [(cid, frm) for cid, frm, _ in moves] == [(3, "w-3"), (6, "w-3")]
    assert ctl.assignment("w-3").units == [] and {ctl.where(3), ctl.where(6)} <= {"w-1", "w-2"}
    assert "slot w-3 released" in ctl.placement(3).reason
    ws[0].reconcile_once(); ws[1].reconcile_once()
    for w in ws[:2]:
        w.heartbeat_once()
    assert ctl.headroom() == 8 - 6                                     # 2 workers × 4, six cameras: what the autoscaler reads
    assert not ctl.free_slot("w-1") and ctl.released_slots() == []      # a slot that renews is freed by nobody


def test_the_console_over_http():
    """The console is its own process with its own token: the operator's rows,
    never placement. The controller, on its pass, places what the console created
    and unplaces what it deleted."""
    from vms.config import SPEC
    from w2cplatform.variables import Forbidden
    box = Box(); ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)   # what the console process holds
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1")
    w.heartbeat_once()
    from w2cplatform.events import read_bucket, subsystems_under
    from tests.vmsconftest import door, footage, store
    srv = serve(con, box.resource_root, port=0, wall=box.wall); port = srv.server_address[1]
    rec_door = None
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras", data=json.dumps({"name": "gate", "source": "driverpack://file/gate.mp4"}).encode(),
                                     method="POST", headers={"Idempotency-Key": "k1"})
        r = json.load(urllib.request.urlopen(req)); assert r["id"] == 1 and r["worker"] is None    # the row; not placed by the console
        r2 = json.load(urllib.request.urlopen(req)); assert r2 == r                    # the same POST, not a second camera
        assert len(ctl.cameras()) == 1
        try:
            con.place(1); raise AssertionError("a console token never writes placement")
        except Forbidden:
            pass
        assert ctl.ensure_placed()[0].worker == "w-1" and ctl.where(1) == "w-1"          # the controller's pass did
        req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras/1", data=b'{"worker":"w-9"}', method="PUT", headers={"Idempotency-Key": "k2"})
        try:
            urllib.request.urlopen(req); raise AssertionError()
        except urllib.error.HTTPError as e:
            assert e.code == 400
        w.reconcile_once(); w.heartbeat_once()
        body = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/cameras"))
        assert body["rows"][0]["phase"] == "running" and body["rows"][0]["server"] == "srv-1"
        where = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/where/1"))
        assert where["worker"] == where["directory"] == "w-1"                         # the placement says, the assignments agree
        spec = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/spec"))      # what the page reads first: the YAML, not code
        assert spec["rows"] == "cameras" and "media" not in spec and {f["name"] for f in spec["fields"]} >= {"name", "source", "enabled"}
        assert b"vms_cameras_running 1" in urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics").read()   # held and streaming; recording is rec's gauge
        # an operator's mark is the CONSOLE's event: its own bucket, never a worker's
        req = urllib.request.Request(f"http://127.0.0.1:{port}/marks", data=json.dumps({"unit": "vms/1", "note": "left the bag"}).encode(),
                                     method="POST", headers={"Idempotency-Key": "k3", "X-User": "murat"})
        m = json.load(urllib.request.urlopen(req))
        assert m["subsystem"] == "console" and m["bucket"].startswith(f"console/{m['unit']}/e1/")
        assert json.load(urllib.request.urlopen(req)) == m                                      # idempotent: one mark
        ev = read_bucket(os.path.join(box.resource_root, m["bucket"]))
        name = ev[0].pop("id")                                                                   # every line has a name, given by its writer
        assert name.startswith(f"{m['unit']}-e1-") and name.rsplit("-", 1)[1].isdigit()
        assert ev == [{"t": box.wall(), "kind": "mark", "of": "vms/1", "user": "murat", "note": "left the bag"}]   # about camera 1
        # not in vms/1/: that bucket has one writer. (`audit/console`: the journal — who created camera 1, the third pass)
        assert subsystems_under(box.resource_root) == {"audit": ["console"], "console": [m["unit"]]}
        # the page, and what it plays: the spans a recording's recorder says at its door — handed out with the recording's
        # place (`/rec/where/<name>`) — raw, in milliseconds, and a piece of one epoch as an MP4, from the same door; the
        # console carries none of it
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "/platform/console.js" in page and "/rec/where/" in page and "<video" in page   # the VMS's page over the console module: the doors its own
        st = store()
        t = box.wall() - 3600
        footage(st, "1", 1, t, t + 600)
        rec_door = door(box, st)                                                                 # a recorder serving its volume
        tl = json.load(urllib.request.urlopen(f"{rec_door.page}/timeline/1"))
        assert tl == [{"start_ms": t * 1000, "end_ms": (t + 600) * 1000, "epoch": 1}]
        with urllib.request.urlopen(f"{rec_door.page}/segment/1/e1/{(t + 60) * 1000:.0f}-{(t + 120) * 1000:.0f}.mp4") as r:
            assert r.status == 200 and r.headers["Content-Type"] == "video/mp4" and r.read()[4:8] == b"ftyp"
        try:
            urllib.request.urlopen(f"{rec_door.page}/segment/1/e1/{(t - 900) * 1000:.0f}-{(t - 600) * 1000:.0f}.mp4"); raise AssertionError()
        except urllib.error.HTTPError as e:
            assert e.code == 404                                                                 # nothing recorded there
        # the page's writes: disable, then delete — through the controller, refused where the controller refuses
        req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras/1", data=b'{"enabled": false}', method="PUT", headers={"Idempotency-Key": "k4"})
        assert json.load(urllib.request.urlopen(req))["enabled"] is False and ctl.camera(1)["revision"] == 2
        req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras/1", method="DELETE")
        assert json.load(urllib.request.urlopen(req)) == {"deleted": 1} and ctl.cameras() == [] and ctl.where(1) == "w-1"   # the row is gone; the placement waits for the pass
        assert ctl.unplace_deleted() == [1] and ctl.where(1) is None and ctl.assignment("w-1").units == []
        try:
            urllib.request.urlopen(req); raise AssertionError()
        except urllib.error.HTTPError as e:
            assert e.code == 404                                                                   # gone is gone
    finally:
        srv.shutdown(); srv.server_close()
        if rec_door is not None:
            rec_door.shutdown()


def test_a_retry_that_lands_on_another_console_is_one_camera():
    """With a console on every server, a client's retry may reach a different
    instance. The key is a Variable, claimed by create-only CAS, so the second
    console serves the first one's reply and never repeats the write."""
    import threading
    from vms.config import SPEC
    box = Box()
    a = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    b = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    s1 = serve(a, None, port=0, wall=box.wall); s2 = serve(b, None, port=0, wall=box.wall)
    p1, p2 = s1.server_address[1], s2.server_address[1]
    try:
        def post(port, key, name="gate"):
            req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras", data=json.dumps({"name": name, "source": "driverpack://file/g.mp4"}).encode(),
                                         method="POST", headers={"Idempotency-Key": key})
            try:
                with urllib.request.urlopen(req) as r: return r.status, json.load(r)
            except urllib.error.HTTPError as e: return e.code, json.load(e)
        first = post(p1, "k-1"); again = post(p2, "k-1")                     # the retry reaches the OTHER console
        assert first == again and first[0] == 201 and len(a.cameras()) == 1
        assert box.vars.get("vms/idem/k-1")[0]["state"] == "done"
        # in flight: console B holds the claim and has not answered yet; A waits for B's reply rather than writing
        box.vars.put("vms/idem/k-2", {"state": "pending", "at": box.wall()}, cas=0)
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("r", post(p1, "k-2"))); t.start()
        time.sleep(0.15); assert "r" not in out and len(a.cameras()) == 1
        box.vars.put("vms/idem/k-2", {"state": "done", "status": 201, "body": json.dumps({"id": 1, "worker": None}), "at": box.wall()})
        t.join(3); assert out["r"] == (201, {"id": 1, "worker": None}) and len(a.cameras()) == 1
        # a key with a slash is not a path segment
        assert post(p1, "a/b")[0] == 400
        # old keys go: a day later the next claim prunes them (at most once a minute)
        from w2cplatform.console import IdempotencyKeys
        keys = IdempotencyKeys(box.vars, "vms/idem/", box.wall, clock=box.clock)
        box.wall.advance(90000); box.clock.advance(61)
        assert keys.prune() == 2 and box.vars.list("vms/idem/") == [] and keys.prune() == 0
        # a forgotten key is a new request, by design — and what stops the second camera then is the rule about
        # sources (`source: {unique: canonical}`, the platform's since the boundary's step 6): camera 1 is that address
        code, body = post(p2, "k-1")
        assert code == 400 and "vms 1 has that source already" in body["detail"] and len(a.cameras()) == 1
    finally:
        s1.shutdown(); s1.server_close(); s2.shutdown(); s2.server_close()


def _console_with_its_own_clock(box, ctl):
    """A console over `ctl` whose idempotency keys age by `box.clock` and never sleep between polls — so a test
    can make thirty seconds pass, or none, without waiting."""
    from vms.console import make_console
    m = make_console(ctl, None, box.wall)
    m.root.seen.clock, m.root.seen.sleep = box.clock, (lambda s: None)
    srv = m.serve("127.0.0.1", 0)
    return m, srv, srv.server_address[1]


def _post(port, key, name="gate", user=None, body=None):
    data = json.dumps(body if body is not None else {"name": name, "source": f"driverpack://file/{key}.mp4"}).encode()   # a source per key: one channel is one camera
    req = urllib.request.Request(f"http://127.0.0.1:{port}/cameras", data=data, method="POST",
                                 headers={"Idempotency-Key": key, **({"X-User": user} if user else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, json.load(e)


def test_a_claim_is_stale_by_standing_still_on_this_consoles_clock_and_not_by_another_consoles_at():
    """The review's second pass, major: the age of a pending claim was `wall() − at`, and `at` was written by
    ANOTHER console with its own wall clock. A console a minute behind its neighbour read every fresh claim as
    stale, took it over and made the second camera. Now a claim is nobody's only once THIS process has seen the
    same revision of it stand for `PENDING_TTL` of its own monotonic clock; a claim re-made meanwhile is a new
    revision and the count starts again. And the reply is sent even when the store would not remember it: the
    write happened, so 201 — not a 503 that sends the client back for a second camera.

    The id is reserved IN the claim before the row is written (the product's `Reserve`/`CreateAs`, feedback CS):
    a take-over creates under that id, or finds the unit created and answers with it — so a lost reply and a
    write never made, the same claim from outside, end as one camera either way."""
    from vms.config import SPEC
    box = Box()
    a = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    m, srv, port = _console_with_its_own_clock(box, a)
    try:
        # the neighbour's clock is ninety seconds behind: its `at` says "old", and it is not
        box.vars.put("vms/idem/k-1", {"state": "pending", "at": box.wall() - 90}, cas=0)
        assert _post(port, "k-1")[0] == 409 and a.cameras() == []          # in flight: waited, served nothing, wrote nothing
        box.clock.advance(20)
        assert _post(port, "k-1")[0] == 409 and a.cameras() == []          # twenty seconds of standing still: not yet
        # …re-made by somebody meanwhile (a new revision): the count starts again
        box.vars.put("vms/idem/k-1", {"state": "pending", "at": box.wall()})
        assert _post(port, "k-1")[0] == 409 and a.cameras() == []          # twenty seconds since the first claim, none since this revision
        box.clock.advance(20)
        assert _post(port, "k-1")[0] == 409 and a.cameras() == []          # forty since the first, twenty of this one
        box.clock.advance(11)
        assert _post(port, "k-1")[0] == 201 and len(a.cameras()) == 1      # thirty-one of the same revision: nobody's — taken over
        assert box.vars.get("vms/idem/k-1")[0]["state"] == "done"
        # the store takes the camera and refuses the reply: the client still hears 201, once, for one camera
        store = m.root.seen.store
        m.root.seen.store = lambda key, resp: (_ for _ in ()).throw(PermissionError(13, "the store does not answer"))
        code, body = _post(port, "k-2")
        assert code == 201 and body["id"] == 2 and len(a.cameras()) == 2
        claim = box.vars.get("vms/idem/k-2")[0]
        assert claim["state"] == "pending" and claim["id"] == "2"           # left standing, naming its camera: a retry waits on it…
        m.root.seen.store = store
        assert _post(port, "k-2")[0] == 409
        box.clock.advance(31)
        assert _post(port, "k-2") == (code, body) and len(a.cameras()) == 2   # …and past the TTL takes it over: camera 2 exists, so camera 2 is the answer
        # the first attempt died between reserving the id and writing the row: the retry creates under the reserved id
        box.vars.put("vms/idem/k-3", {"state": "pending", "at": box.wall(), "id": "9"}, cas=0)
        assert _post(port, "k-3")[0] == 409
        box.clock.advance(31)
        assert _post(port, "k-3")[1]["id"] == 9 and [c["id"] for c in a.cameras()] == [1, 2, 9]
        assert _post(port, "k-4")[1]["id"] == 3                            # the counter was never touched by the take-over
    finally:
        srv.shutdown(); srv.server_close()


def test_an_idempotency_key_is_one_callers_for_one_body():
    """The review's second pass, minor: a replay under a known key was answered with the stored reply to anybody —
    a stranger got anna's 201, and anna's own second mark under a reused key was silently not written. The claim
    carries who (`X-User`, the name the gate proved where there is one) and a digest of the body; a replay by
    another caller or with another body is 422. The same caller with the same body is the same request."""
    from vms.config import SPEC
    box = Box()
    a = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    m, srv, port = _console_with_its_own_clock(box, a)
    try:
        first = _post(port, "k-1", user="anna")
        assert first[0] == 201 and _post(port, "k-1", user="anna") == first and len(a.cameras()) == 1
        code, body = _post(port, "k-1", user="boris")
        assert code == 422 and body["error"] == "key reused" and len(a.cameras()) == 1   # not anna's reply, not a camera
        code, body = _post(port, "k-1", user="anna", name="yard")
        assert code == 422 and body["error"] == "key reused" and len(a.cameras()) == 1   # anna, another body: said so, not swallowed
        # …and while the first caller's claim is still pending on another console, the stranger is told at once
        box.vars.put("vms/idem/k-2", {"state": "pending", "at": box.wall(), "sub": "anna", "sha256": "0" * 64}, cas=0)
        assert _post(port, "k-2", user="boris")[0] == 422
        assert box.vars.get("vms/idem/k-1")[0]["sub"] == "anna" and len(box.vars.get("vms/idem/k-1")[0]["digest"]) == 64
    finally:
        srv.shutdown(); srv.server_close()


def test_a_console_whose_claim_was_taken_over_while_it_stood_still_writes_nothing():
    """The review's third pass, major: a take-over did not fence the console it took from. A stood still for thirty
    seconds, B took the claim and created camera 1, A woke and created camera 2 under the same key. `reserve`, `store`
    and `release` are CAS on the revision the console holds: A, waking before its reserve, loses it — 409, no row; A,
    waking after its reserve, finds B created under the id it reserved — 409, the same camera. Either way one camera,
    and the key answers with B's reply.

    Its waits are the test's own events, not seconds (seen failing once under a loaded full run): A's claim is waited
    for until it is there — it was two seconds, and past them B claimed the key itself — and A stands still until B has
    taken over, however long that takes — it was ten seconds, and past them A went on and created camera 2."""
    from vms.config import SPEC
    box = Box()
    a = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    b = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    ma, sa, pa = _console_with_its_own_clock(box, a)
    mb, sb, pb = _console_with_its_own_clock(box, b)
    try:
        for stall in ("before the reserve", "after the reserve"):
            key, go, out = f"k-{stall[0]}", threading.Event(), {}
            if stall == "before the reserve":
                create = a.create
                a.create = lambda body, **kw: (go.wait(120), create(body, **kw))[1]
            else:
                reserve = ma.root.seen.reserve
                ma.root.seen.reserve = lambda k, uid: (reserve(k, uid), go.wait(120))[0]
            t = threading.Thread(target=lambda: out.setdefault("a", _post(pa, key))); t.start()
            deadline = time.monotonic() + 60
            while not box.vars.get(f"vms/idem/{key}")[0] and time.monotonic() < deadline:   # A holds the claim and stands still
                time.sleep(0.01)
            assert box.vars.get(f"vms/idem/{key}")[0], "A's claim never appeared"
            assert _post(pb, key)[0] == 409                                      # B sees it in flight…
            box.clock.advance(31)
            code, body = _post(pb, key)                                          # …and thirty seconds later takes it over
            assert code == 201
            go.set(); t.join(120)
            assert out["a"][0] == 409 and out["a"][1]["error"] == "taken over", (stall, out)
            assert _post(pa, key) == (code, body)                                # the key answers with B's reply
            if stall == "before the reserve":
                a.create = create
            else:
                ma.root.seen.reserve = reserve
        # one camera per key: 1, and 3 under the id A reserved — the 2 A drew before it lost its reserve is a gap, not a camera
        assert [c["id"] for c in a.cameras()] == [1, 3]
    finally:
        sa.shutdown(); sa.server_close(); sb.shutdown(); sb.server_close()


def test_a_claim_nobody_will_answer_does_not_hold_its_key_for_a_day():
    """A console claims the key, then crashes — or its write raises — before it stores the reply. The claim stood
    for the key's whole day and every correct retry got 409 "in flight" (the platform review; feedback BG). A
    pending claim that has stood still for thirty seconds is nobody's: the next request takes it over and does the
    work. A 5xx is not remembered under the key — "the store is away" is not an answer to the request — and a write
    that raised lets its claim go at once. The store failing at the claim is 503, which a client retries, not 400."""
    from vms.config import SPEC
    from w2cplatform.console import IdempotencyKeys
    box = Box()
    a = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    m, srv, port = _console_with_its_own_clock(box, a)

    def post(key, name="gate"):
        return _post(port, key, name)

    try:
        box.vars.put("vms/idem/k-1", {"state": "pending", "at": box.wall()}, cas=0)   # claimed by a console that then died
        assert post("k-1")[0] == 409                                                   # seen once: in flight, for all this console knows
        box.clock.advance(31)
        assert post("k-1")[0] == 201 and len(a.cameras()) == 1                          # taken over: the work is done
        assert box.vars.get("vms/idem/k-1")[0]["state"] == "done"

        create = a.create
        a.create = lambda body, **kw: (_ for _ in ()).throw(PermissionError(13, "the store does not answer"))
        code, body = post("k-2")
        assert code == 503 and body["error"] == "store unavailable"
        assert box.vars.get("vms/idem/k-2")[0] is None                                 # the claim was let go, not left pending
        a.create = create
        assert post("k-2")[0] == 201 and len(a.cameras()) == 2                          # the retry does the work

        keys = IdempotencyKeys(box.vars, "vms/idem/", box.wall, clock=box.clock)
        assert keys.claim("k-3") is None
        keys.store("k-3", (500, {"error": "the write failed"}))
        assert box.vars.get("vms/idem/k-3")[0] is None                                 # a 5xx is not the key's answer
        keys.store("k-3", (400, {"error": "no such source"}))
        assert box.vars.get("vms/idem/k-3")[0]["status"] == "400"                      # a refusal is
    finally:
        srv.shutdown()


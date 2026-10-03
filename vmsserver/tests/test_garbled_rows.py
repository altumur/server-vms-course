"""One row of the store that does not parse is that row's trouble (the review's sixth pass, the follow-up).

Three passes of the review found the same thing in a new place each time: a row read bare — a word where a number
goes, after a hand edit or half a write — raised out of a loop over MANY rows, and one unit's trouble stopped
everybody's pass. The epoch rows went first, then the slot rows. This module is the rest of what the platform's
controller and worker read, one test per kind of row: the assignment, the slot under `retire`, the placement, the
controller's own report, the numbers inside a heartbeat, the published snapshot, the retention row — and a unit's
own row as each worker reads it. The rule is the same everywhere: what the row still says is used, the row is
counted and logged once, the pass goes on, and nothing is read as "no" that only failed to parse.
"""
import json

from w2cplatform.contract import Assignment, Heartbeat, Slot
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_group_by import _worker
from tests.test_lesson4_worker import _box_with_cameras


def _placed(cameras=3):
    box, ctl = _box_with_cameras(cameras)
    for name, server in (("w-1", "srv-a"), ("w-2", "srv-b")):
        _worker(box, name, server)
    ctl.ensure_placed()
    return box, ctl


def _counter(obj, name):
    """A module counter, through a method of the class in use — `test_portability` rebuilds `sys.modules`."""
    return type(obj).assignment.__globals__[name]


from tests.test_slot_fence import _forget_garbled  # noqa: E402


# -- the assignment -------------------------------------------------------------------------------------------

def test_a_garbled_assignment_row_is_that_workers_trouble_and_the_pass_goes_on():
    """`Controller.assignments()` read every row bare, and it is under everything the pass does — the sync of
    assignments with their placement rows, every move, `/where`: one worker's `rev` with a word in it, and no unit
    of the subsystem was placed, every pass. The row still says what it DECIDES — `units` — and is read so, with
    `rev 0`, counted and logged; the controller's next change to it writes it whole."""
    box, ctl = _placed(4)
    on1 = ctl.assignment("w-1").units
    assert on1 and ctl.assignment("w-2").units
    garbled = _counter(ctl, "ASSIGNMENTS_GARBLED")
    before = garbled.get("vms", 0)
    box.vars.put("vms/workers/w-1", {"units": ",".join(on1), "rev": "seven"})
    new = ctl.create_camera({"name": "cam5", "source": "driverpack://file/cam5.mp4"})["id"]
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0 and ctl.where(new), rep                       # the pass placed what was new
    assert ctl.assignments()["w-1"].units and garbled.get("vms", 0) > before and rep["assignments_garbled"] > before
    assert set(on1) <= set(ctl.assignment("w-1").units)                                     # what it decided stands
    where = ctl.where(int(on1[0]))
    ctl.move(int(on1[0]), "w-2" if where == "w-1" else "w-1", "operator")                    # the next change to the row…
    assert Assignment.from_items("w-1", box.vars.get("vms/workers/w-1")[0]).rev >= 1         # …wrote it whole
    _forget_garbled()


def test_a_worker_whose_own_assignment_row_is_garbled_carries_out_what_it_names():
    """The worker's side of the same row: it raised out of `refresh`, every pass — nothing new started, nothing
    taken away stopped. The units are read, the pass is a pass, and the heartbeat says a row could not be read."""
    box, ctl = _box_with_cameras(3)
    ctl.assign("w-1", ["1", "2"])
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, server="srv-1")
    assert w.reconcile_once() == [("start", 1), ("start", 2)]
    box.vars.put("vms/workers/w-1", {"units": "1,2,3", "rev": "seven"})
    assert w.reconcile_once() == [("start", 3)] and act.running == {1, 2, 3}                # the units it names are read
    box.vars.put("vms/workers/w-1", {"units": "2,3", "rev": "eight"})
    assert w.reconcile_once() == [("stop", 1)]                                              # …and what it takes away is stopped
    w.heartbeat_once()
    # One row, garbled across two passes and two hand edits: ONE row that does not parse, not one per read (the
    # review's seventh pass, a minor — the count grew on every pass).
    assert Heartbeat.from_bytes(box.objects.get("vms/heartbeats/w-1")).extra["assignments_garbled"] == 1
    _forget_garbled()


# -- the epoch, under a lease ------------------------------------------------------------------------------------

def test_a_lease_whose_epoch_row_stops_parsing_is_lost_alone():
    """The renewal's side of the epoch row, as it has been since the second pass and kept said here: the store
    ANSWERED, with something that is not an epoch — not silence to record through. That unit's lease is fenced and
    counted; the worker's other leases are renewed."""
    box, ctl = _box_with_cameras(2)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1")
    w.take_epoch("1"); w.take_epoch("2")
    box.vars.put("vms/epoch/1", {"epoch": "one"})
    box.clock.advance(10)
    assert w.renew_leases() == ["1"] and w.conflicts() == 1
    assert w.may_write("2") and w.leases["2"].last_renewal == box.clock() and not w.may_write("1")


# -- the slot, freed by the controller ---------------------------------------------------------------------------

def test_freeing_a_slot_whose_row_is_garbled_writes_it_released():
    """`free_slot` is how the controller lets go of a name nothing runs under (`Controller.slot_fate`) — and a row that
    does not parse is exactly the slot somebody wants to be rid of. It raised (`ValueError`, when it was the operator's
    `retire`). The row is written over, whole: released, held by nobody; freeing it again does nothing."""
    box, ctl = _placed(2)
    box.vars.put("vms/slots/w-9", {"holder": "somebody", "until": "soon", "released": "false", "gen": "1"})
    assert ctl.free_slot("w-9")
    row = Slot.from_items("w-9", box.vars.get("vms/slots/w-9")[0])
    assert row.released and row.holder == "" and row.claimable(box.wall()) and "w-9" in ctl.slots()
    assert not ctl.free_slot("w-9") and Slot.from_items("w-9", box.vars.get("vms/slots/w-9")[0]).released   # and again: nothing to do
    _forget_garbled()


# -- the placement row ---------------------------------------------------------------------------------------

def test_a_garbled_placement_row_still_says_where_its_unit_is_and_stops_no_pass():
    """A placement row decides one thing — `worker` — and carries three more for a person (`reason`, `at`, `rev`).
    `placement()` parsed all four bare, and it is asked about OTHER units while one is placed (`together`,
    `apart`), by `unplaced()`, by `ensure_home`: one row's `at` with a word in it stopped them all. And the passes
    that walk `<sub>/placement/` (`unplace_deleted`, `unplace_retired`) raised on a `rev` they only wanted to add
    one to, or on a row there whose name is no unit's id."""
    box, ctl = _placed(3)
    w = ctl.where(1)
    box.vars.put("vms/placement/1", {"worker": w, "reason": "by hand", "at": "yesterday", "rev": "two"})
    box.vars.put("vms/placement/not-a-camera", {"worker": w, "reason": "?", "at": "1", "rev": "1"})
    new = ctl.create_camera({"name": "cam4", "source": "driverpack://file/cam4.mp4"})["id"]
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0 and ctl.where(new), rep
    pl = ctl.placement(1)
    assert (pl.worker, pl.reason, pl.at, pl.rev) == (w, "by hand", 0.0, 0)
    ctl.delete_camera(1)                                                                    # …and the row is still the controller's to change
    assert ctl.unplace_deleted() == [1] and ctl.placement(1) is None
    assert str(box.vars.get("vms/placement/1")[0]["rev"]) == "1" and "1" not in ctl.assignment(w).units


# -- the controller's own report -------------------------------------------------------------------------------

def test_a_garbled_pass_report_does_not_stop_the_controllers_loop():
    """`pass_once` begins by reading its last report, to carry the count of failures on — and "it does not raise" is
    what the loop that calls it relies on (`_controller_loop`). A report object that is half a write raised out of
    the pass before its first step and out of the loop: the controller process ended, was started again, and ended
    again on the same object — which only a pass that finishes writes over."""
    box, ctl = _placed(2)
    box.objects.put("vms/controller/pass", b'{"ts": 17575, "fail')
    assert ctl.pass_report() is None
    rep = ctl.pass_once()
    assert rep["ok"] and rep["failures"] == 0 and ctl.pass_report()["ok"]                   # written whole again
    box.objects.put("vms/controller/pass", json.dumps({"ts": 1, "failures": "many"}).encode())
    assert ctl.pass_once()["failures"] == 0


# -- the numbers a heartbeat carries ---------------------------------------------------------------------------

def test_a_heartbeat_whose_numbers_are_words_is_that_workers_trouble():
    """A heartbeat that does not parse at all is skipped (`parse_heartbeat`, the second pass). One that parses and
    carries a word where the controller reads a number — `capacity`, `headroom`, `started` — raised where it was
    read: `capacity_of` is asked of every candidate while ANY unit is placed, so one worker's field stopped every
    placement. It is read as "has not said": the fallback capacity, no headroom, no failover time."""
    box, ctl = _box_with_cameras(2)
    _worker(box, "w-1", "srv-a")
    box.objects.put("vms/heartbeats/w-2", Heartbeat("w-2", box.wall(), [], {
        "server": "srv-b", "capacity": "many", "headroom": "some", "started": "then", "previous_hb": "before"}).to_bytes())
    assert ctl.capacity_of("w-2") == ctl.capacity and ctl.capacity_of("w-1") == 50
    assert ctl.headroom() == 50 and ctl.failover_seconds() == {}
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0, rep


def test_a_garbled_snapshot_shard_makes_the_published_copy_old_and_never_fresh():
    """`snapshot_age` is the stalest shard's age, because the number must never be wrong in the comfortable
    direction. A shard that does not parse has no age to read: it raised, and `/metrics` with it. It is the oldest
    there can be — the copy the layer above reads is broken, and the number says so."""
    box, ctl = _placed(2)
    ctl.publish_snapshot()
    assert ctl.snapshot_age() == 0
    box.objects.put("vms/snapshot/w-1", b'{"cameras": [')
    assert ctl.snapshot_age() == box.wall()
    ctl.publish_snapshot()
    assert ctl.snapshot_age() == 0                                                          # the next publish mends it
    for ts in ("nan", "inf", "-inf"):                                                     # a number that is no time is no age either
        box.objects.put("vms/snapshot/w-1", json.dumps({"ts": ts, "cameras": []}).encode())
        assert ctl.snapshot_age() == box.wall(), ts


# -- the sweep's list ------------------------------------------------------------------------------------------

def test_a_garbled_sweep_list_stops_no_upload_and_deletes_nothing_on_its_word():
    """`<sub>/sweep` is one row, and `put_blob` reads it on every upload to take its own digest off the list: half a
    list in it raised there, and no mask of any detector could be stored. A list nobody can read is no list — an
    upload goes through, the sweep deletes nothing on its word and marks afresh, with a new grace."""
    from vms.config import DET_SPEC
    from w2cplatform.spec import SpecController
    box = Box()
    ctl = SpecController(DET_SPEC, box.vars, box.objects, wall=box.wall)
    ctl.create({"name": "7-linecross", "cam": "7", "kind": "linecross"})
    ctl.update("7-linecross", {"mask": ctl.put_blob(b"a" * 900)})
    ctl.update("7-linecross", {"mask": ctl.put_blob(b"b" * 900)})                           # the first is an orphan now
    box.vars.put(DET_SPEC.sub.sweep_key(), {"at": "then", "digests": '["sha256-'})
    d = ctl.put_blob(b"c" * 900)                                                            # it raised here
    assert ctl.blob(d) == b"c" * 900 and len(box.objects.list("det/blobs/")) == 3
    assert ctl.sweep_blobs() == {"marked": 2, "deleted": 0, "waiting": 0}                   # marked afresh, nothing deleted
    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 0, "waiting": 2}                   # …and the grace is a new one


# -- the retention row ---------------------------------------------------------------------------------------

def test_one_units_garbled_retention_row_keeps_that_units_buckets_and_the_rest_are_swept():
    """The resource reads a unit's days before it sweeps (`retention_days`), every unit's in one loop: one row with
    `days` a word raised out of `retain`, and nothing of anybody's was swept, every pass. Not knowing a unit's days
    is not "zero days": THAT unit is left alone this pass, named in `retention_garbled` and in the log, and the
    others are swept by theirs. The same for the copies kept of another server's buckets."""
    from w2cplatform.events import EventLog
    from w2cplatform.resource import Resource
    box = Box()
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock)
    old = box.wall() - 40 * 86400
    for unit in ("7", "8"):
        EventLog(box.archive, "vms", unit, 1).append(old, "stats", "observation")
    box.vars.put("vms/retention", {"days": "30"})
    box.vars.put("vms/retention/7", {"days": "a month"})
    assert res.retain() == 1
    from w2cplatform.events import bucket_names_under
    assert len(bucket_names_under(box.archive, "vms", "7", 600)) == 1 and bucket_names_under(box.archive, "vms", "8", 600) == []
    assert res.retention_garbled == ["vms/7"]
    box.vars.put("vms/retention/7", {"days": "30"})                                          # mended: swept by its days
    assert res.retain() == 1 and res.retention_garbled == []


# -- a unit's own row, as each worker reads it ------------------------------------------------------------------
#
# The controller has skipped a row that does not parse since the second pass (`units()`, `_parsed`). The workers
# had not: each reads the rows of the units it was assigned in one loop, bare, and a row garbled AFTER it was placed
# raised out of the pass — nothing after it started, nothing taken away stopped, every pass.

def _garble(box, path):
    """A hand edit: the row keeps every field, and its `revision` is a word."""
    it, idx = box.vars.get(path)
    assert it, path
    box.vars.put(path, {**it, "revision": "two"}, cas=idx)


def test_the_holder_goes_on_with_the_row_it_read_last_and_runs_the_rest():
    """The holder reads its cameras' rows in `refresh`. One that stops parsing is not a camera taken away: what runs
    under the row read last keeps running — not knowing is not "no" — the cameras after it start, and the status
    says why that one is not following its row. A worker that never read it whole does not start it."""
    box, ctl = _box_with_cameras(3)
    ctl.assign("w-1", ["1", "2"])
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, server="srv-1")
    assert w.reconcile_once() == [("start", 1), ("start", 2)]
    _garble(box, "vms/cameras/2")
    ctl.assign("w-1", ["1", "2", "3"])
    for _ in range(2):                                                 # every pass, not once
        acts = w.reconcile_once()
    assert act.running == {1, 2, 3} and acts == [] and w.pass_failures == 0
    st = {s["id"]: s for s in w.status()}
    assert "row does not parse" in st[2]["why"] and "why" not in st[1] and st[3]["phase"] == "running"
    fresh = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1")
    assert fresh.reconcile_once() == [("start", 1), ("start", 3)]


def test_the_recorder_reads_past_a_recording_whose_row_does_not_parse():
    """The recorder walks EVERY recording's row to answer questions about one — who else records this camera, which
    backup holds it, what a keep names — and parsed each bare: one garbled row, and no backup's pipeline started, no
    range was fetched, no keep was copied, for any recording."""
    from tests.conftest import recorder
    from tests.test_rec_volume import _site
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    rec_con.create({"name": "1", "cam": "1"})
    rec_con.create({"name": "1-b", "cam": "1"})
    rec_ctl.ensure_placed()
    _garble(box, "rec/recordings/1")
    r.lease_pass()
    acts = r.reconcile_once()
    assert ("start", "1-b") in acts and "1-b" in r.reconciler.actual, acts
    assert r.backup_sources({"id": "1-b", "cam": "1", "home": ""}) == []                    # walked, not raised
    assert r.primary_needs_cover({"id": "1-b", "cam": "1", "home": ""}) in (True, False)


def test_the_detector_the_scan_the_survey_the_evaluator_and_the_gateway_each_pass_a_garbled_row_by():
    """The same in the five workers of the other subsystems, each on the setup its epoch test uses: the unit whose
    row does not parse says `failed` and why (the gateway keeps the fan-out it has), and the next unit moves."""
    # the scan
    from tests.test_detjob_worker import _footage, _site, _worker as _scan, m
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC, LIVE_SPEC
    box = _site(); _footage(box, "7", 1, 0, 10)
    ctl = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    for name in ("7-lpr-1", "7-lpr-2"):
        ctl.create({"name": name, "cam": "7", "rec": "7", "kind": "lpr", "from": m(0), "to": m(10)})
    box.vars.put(DETJOB_SPEC.sub.assignment("j-1"), {"units": "7-lpr-1,7-lpr-2", "rev": 1})
    _garble(box, "detjob/jobs/7-lpr-1")
    w = _scan(box)
    w.reconcile_once()
    assert "row does not parse" in w.status_by_unit["7-lpr-1"]["why"] and w.status_by_unit["7-lpr-1"]["phase"] == "failed"
    assert w.status_by_unit["7-lpr-2"]["phase"] in ("running", "done") and w.events_written > 0

    # the evaluator
    from tests.test_autoworker import DOOR, _Log, _assigned, _scenario, _worker as _auto, ev
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="a-door")
    _scenario(box)                                                     # `door-on-badge`, after `a-door` in the pass
    actl = _assigned(box, "a-door")
    actl.assign("a-1", ["a-door", "door-on-badge"])
    _garble(box, "auto/scenarios/a-door")
    a = _auto(box, log)
    assert a.reconcile_once() == ["door-on-badge"] and DOOR["name"] in a.epochs
    assert a.status_by_unit["a-door"]["phase"] == "failed" and "row does not parse" in a.status_by_unit["a-door"]["why"]

    # the gateway: an idle fan-out whose row stopped parsing is kept — nobody can say its grace has run out
    from tests.test_pass_failures import _workers
    box = Box()
    gw = _workers(box)[3]
    gw.rtp_source = lambda cam: ("srv-1", f"rtsp://srv-1/{cam}", 1)
    for cam in ("7", "8"):
        gw.ctl.create({"cam": cam})
    box.vars.put(LIVE_SPEC.sub.assignment("g-1"), {"units": "7,8", "rev": 1})
    gw.reconcile_once()
    assert set(gw.upstreams) == {"7", "8"}
    _garble(box, "live/streams/7")
    box.wall.advance(600); box.clock.advance(600)                      # far past the grace of an idle fan-out
    gw.reconcile_once()
    assert "7" in gw.upstreams and gw.ctl.unit("8") is None            # 8 was idle and its row said so: deleted; 7 is kept

    # the survey
    from tests.test_survey import Every, _holder, _watch, _worker as _survey, m as sm
    from vms.config import SURVEY_SPEC
    box = Box(); spans = _holder(box)
    sctl = _watch(box, name="7-lpr", start="earliest")
    sctl.create({"name": "7-motion", "cam": "7", "kind": "motion", "start": "earliest"})
    box.vars.put(SURVEY_SPEC.sub.assignment("s-1"), {"units": "7-lpr,7-motion", "rev": 2}, cas=box.vars.get(SURVEY_SPEC.sub.assignment("s-1"))[1])
    _garble(box, "survey/watches/7-lpr")
    sw = _survey(box, spans); sw.SECONDS_PER_PASS = sm(100) - sm(0); sw.models = {"lpr": Every, "motion": Every}
    sw.reconcile_once()
    assert sw.status_by_unit["7-lpr"]["phase"] == "failed" and "row does not parse" in sw.status_by_unit["7-lpr"]["why"]
    assert sw.status_by_unit["7-motion"]["phase"] == "running" and sw.events_written > 0


def test_the_detector_passes_a_garbled_row_by_and_keeps_what_it_runs():
    """…and the detector, on a live console as its epoch test is: the model already running under the row read last
    keeps running; a detector never started says `failed` and why."""
    from tests.test_lesson9_det import _box, _det, call
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        gpu = _det(box, "d-1")

        class Sees:
            def __init__(self, row): self.row = row
            def observe(self, now): return [("motion", {"area": 1})]
            def close(self): pass
        gpu.models = {"lpr": Sees, "motion": Sees}
        call(base, "POST", "/det/units", {"name": "1-lpr", "cam": "1", "kind": "lpr"}, {"Idempotency-Key": "k1"})
        call(base, "POST", "/det/units", {"name": "1-motion", "cam": "1", "kind": "motion"}, {"Idempotency-Key": "k2"})
        det_ctl.ensure_placed()
        assert sorted(gpu.reconcile_once()) == ["1-lpr", "1-motion"]
        _garble(box, "det/units/1-lpr")
        assert sorted(gpu.reconcile_once()) == ["1-lpr", "1-motion"]   # running under the row read last: kept
        fresh = _det(box, "d-1"); fresh.models = gpu.models
        assert fresh.reconcile_once() == ["1-motion"]
        assert fresh.status_by_unit["1-lpr"]["phase"] == "failed" and "row does not parse" in fresh.status_by_unit["1-lpr"]["why"]
    finally:
        srv.shutdown(); srv.server_close()


def test_days_that_are_no_number_of_days_keep_the_units_buckets_and_nought_still_sweeps():
    """The product team's sibling of the review's ninth pass: `days: "nan"` passed `float`, and `nan` days passed no
    comparison — nothing swept and nothing said; `-1` swept every bucket of the unit, the current one too; `inf` is no
    number any controller writes. Each is a row that does not read: the unit's buckets are kept, the row counted once
    (`retentions_garbled`) and named in the heartbeat (`retention_garbled`). `days: 0` — a deleted unit's — still
    sweeps."""
    from w2cplatform.events import EventLog, bucket_names_under
    from w2cplatform.resource import RETENTION, Resource
    box = Box()
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock)
    t = box.wall()
    days = {"1": "ten", "2": "nan", "3": "inf", "4": "-1", "5": "0", "6": "-inf"}
    for unit, d in days.items():
        EventLog(box.archive, "vms", unit, 1).append(t - 3 * 86400, "stats", "observation")
        box.vars.put(f"vms/retention/{unit}", {"days": d})
    assert res.retain() == 1                                           # the `0`: nothing of the rest
    assert res.retain() == 0                                           # and the next pass sweeps none of them either
    for unit in ("1", "2", "3", "4", "6"):
        assert len(bucket_names_under(box.archive, "vms", unit, 600)) == 1, unit
    assert bucket_names_under(box.archive, "vms", "5", 600) == []
    named = ["vms/1", "vms/2", "vms/3", "vms/4", "vms/6"]
    assert res.retention_garbled == named
    hb = res.heartbeat()
    assert hb["retention_garbled"] == named and hb["rows_garbled"]["retention"] == 5, hb.get("rows_garbled")
    assert RETENTION.counts == {"vms": 5}                              # twice read, once counted
    box.vars.put("vms/retention/2", {"days": "1"})                     # mended: swept by its days, and no longer named
    assert res.retain() == 1 and "vms/2" not in res.retention_garbled and RETENTION.counts == {"vms": 5}
    _forget_garbled()


def test_a_recordings_ceiling_that_is_no_number_of_days_hides_and_does_not_fall_back_to_thirty():
    """The same sibling at the recorder's door: `retention_days` is how far back a recording is SHOWN — "nobody sees more
    than a week" — and the door read it with `float`: a word raised out of the door and the backfill's plan, `nan` was a
    ceiling nothing is under, `inf` showed everything, `-1` hid a day ahead. Not said is thirty days, as before; said and
    not a number of days, nothing older than now is shown or fetched — never a default — counted once and named."""
    from vms.archive import CEILINGS, visible_from
    now = 1_757_500_000.0
    assert visible_from(None, now) == now - 30 * 86400 and visible_from({"id": "1"}, now) == now - 30 * 86400
    assert visible_from({"id": "1", "retention_days": "7"}, now) == now - 7 * 86400
    assert visible_from({"id": "1", "retention_days": "0"}, now) == now                       # nought: what it says
    for bad in ("ten", "nan", "inf", "-1", ["7"]):
        assert visible_from({"id": "r9", "retention_days": bad}, now) == now, bad
    assert CEILINGS.counts == {"rec": 1} and CEILINGS.named("rec/recordings/") == {"r9#retention_days"}
    assert visible_from({"id": "r9", "retention_days": "7"}, now) == now - 7 * 86400          # mended
    assert CEILINGS.named("rec/recordings/") == set()
    _forget_garbled()


# -- the ninth review: numbers past any number, a clock ahead, a step that fails every pass --------------------------

def test_a_heartbeat_with_a_number_past_any_number_or_nested_ten_thousand_deep_stops_no_placement():
    """Two parse errors the readers' own lists left out (the ninth review's sweep). `headroom: Infinity` — JSON reads
    it — made `int(inf)` raise `OverflowError` past `_number`'s `(ValueError, TypeError)`: `capacity_of` and
    `headroom` are asked of every candidate, so no unit was placed. A heartbeat of `[` ten thousand deep raised
    `RecursionError` past `parse_heartbeat`'s list, out of `workers_seen` — every reader of heartbeats. The field is
    "not said", the heartbeat is skipped, both counted; the pass places."""
    box, ctl = _box_with_cameras(3)
    _worker(box, "w-1", "srv-a")
    box.objects.put("vms/heartbeats/w-2", Heartbeat("w-2", box.wall(), [], {
        "server": "srv-b", "capacity": 1e400, "headroom": float("inf"), "started": 10**400}).to_bytes())
    box.objects.put("vms/heartbeats/w-3", b"[" * 10000)
    box.objects.put("vms/heartbeats/w-4", json.dumps({"worker": "w-4", "ts": 10**400, "status": []}).encode())
    assert ctl.capacity_of("w-2") == ctl.capacity and ctl.headroom() == 50
    assert set(ctl.workers_seen()) == {"w-1", "w-2"}
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0, rep
    _forget_garbled()


def test_a_snapshot_written_by_a_clock_running_ahead_is_not_fresh_and_its_lead_is_measured():
    """A controller whose clock ran an hour ahead and then stopped wrote shards an hour ahead: `max(0, now − ts)` read
    them as age 0 for that hour — the copy above "fresh" while nothing published it. A shard further ahead than the
    heartbeats' tolerance has no age anybody can vouch for: the oldest there can be, counted once, and its lead goes
    into `heartbeat_skew_seconds_max`."""
    from w2cplatform.contract import SKEW_MAX
    from w2cplatform.rows import FIELDS
    box, ctl = _placed(2)
    ctl.publish_snapshot()
    box.objects.put("vms/snapshot/w-1", json.dumps({"ts": box.wall() + 3600, "cameras": []}).encode())
    assert ctl.snapshot_age() == box.wall()
    assert SKEW_MAX.get("vms", 0) >= 3600 and "vms/snapshot/w-1#ts" in FIELDS.bad
    box.objects.put("vms/snapshot/w-1", json.dumps({"ts": box.wall() + 2, "cameras": []}).encode())   # within tolerance
    assert ctl.snapshot_age() == 0 and "vms/snapshot/w-1#ts" not in FIELDS.bad
    SKEW_MAX.pop("vms", None)
    _forget_garbled()


def test_a_pass_report_counting_past_any_number_stops_no_pass_and_a_step_that_fails_every_pass_is_said_once():
    """`failures: 1e400` in the last report made `int(inf)` raise `OverflowError` before any step ran, and the report
    is only written at the end of a pass: that subsystem's controller placed nothing, for ever. And a step that failed
    on every pass put its trace in the log every five seconds (the eighth review's minor «трейс _steps»): the trace
    once per spell now, "works again" when it does."""
    import logging
    box, ctl = _placed(2)
    box.objects.put("vms/controller/pass", json.dumps({"failures": 1e400}).encode())
    assert ctl.pass_once()["ok"]
    records = []

    class Keep(logging.Handler):
        def emit(self, record):
            records.append(record)
    spec_log = logging.getLogger(type(ctl).pass_once.__module__)
    keep = Keep(); spec_log.addHandler(keep)
    real = ctl.redistribute
    try:
        ctl.redistribute = lambda: (_ for _ in ()).throw(RuntimeError("a store that says no"))
        for _ in range(3):
            assert not ctl.pass_once()["ok"]
        ctl.redistribute = real
        assert ctl.pass_once()["ok"]
    finally:
        spec_log.removeHandler(keep)
    traced = [r for r in records if r.exc_info and "redistribute" in r.getMessage()]
    again = [r for r in records if "redistribute works again" in r.getMessage()]
    assert len(traced) == 1 and len(again) == 1, [r.getMessage() for r in records]


# -- the course's file store: a row it holds and cannot read, a key it cannot name (the eleventh review) ---------------

_DAMAGE = {
    "torn": lambda raw: raw[:len(raw) // 2],
    "items not a map": lambda raw: json.dumps({"items": ["a", "b"], "index": json.loads(raw)["index"]}),
    "index not a number": lambda raw: json.dumps({"items": json.loads(raw)["items"], "index": "seven"}),
}
_NOT_STRINGS = lambda raw: json.dumps({"items": {k: [7, True, 1e999] for k in json.loads(raw)["items"]},  # noqa: E731
                                       "index": json.loads(raw)["index"]}).replace("Infinity", "1e999")


def test_a_row_file_the_store_cannot_read_is_one_parse_error_of_that_row_and_the_routes_go_on():
    """The eleventh review, a minor: a torn file of the course's file store — or one whose `items` are not a map — raised
    whatever `json` raised out of `FileVariables.get`, and the routes that read the drain, a slot, a placement, a
    worker's row, a hold or a decommission bare fell whole: `/servers`, `/unplaceable`, `/drain`, `/where` gave no answer
    at all. `get` raises one error now (`Garbled`, a `ValueError` naming the row); the readers of those rows read it as
    that row not parsing (`contract.stored`) — counted and logged once — and every route answers. Values that are not
    strings, which Nomad never answers, come back as their JSON text: the field's trouble, as a Nomad value's. A write
    replaces a row that does not read whole (`Controller.write`, `cas=TORN`): the controller's next pass places a unit
    whose placement nobody could read again; a create-only write conflicts."""
    import urllib.error
    import urllib.request
    from w2cplatform.variables import TORN, Conflict, Garbled
    from vms.config import SPEC
    from vms.controller import VmsController
    from tests.test_console_gate import _console
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        c2 = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
        w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                      archive_root=box.archive)
        w.heartbeat_once()
        ctl.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); c2.ensure_placed()
        w.reconcile_once(); w.heartbeat_once()
        box.vars.put("platform/drain", {"server": "", "at": "1"})
        box.vars.put("rec/holds/v1", Slot("v1", "i-1", box.wall() + 60, False, 1, "r-1").to_items())
        box.vars.put("platform/decommission/srv-9", {"by": "anna", "at": "1", "why": "gone"})

        def get(path):
            try:
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code
            except OSError as e:                                          # no answer at all: the review's
                return type(e).__name__
        routes = ("/servers", "/unplaceable", "/drain", "/where/1", "/cameras", "/metrics", "/rec/volumes")
        assert {r: get(r) for r in routes} == {r: 200 for r in routes}
        for key in ("platform/drain", "vms/slots/w-1", "vms/placement/1", "vms/workers/w-1", "rec/holds/v1",
                    "platform/decommission/srv-9"):
            f = box.vars._file(key)
            with open(f) as fh:
                raw = fh.read()
            for how, damage in _DAMAGE.items():
                with open(f, "w") as fh:
                    fh.write(damage(raw))
                try:
                    box.vars.get(key)
                    raise AssertionError(f"{key} {how}: read as a row")
                except Garbled as e:
                    assert isinstance(e, ValueError) and key in str(e) and e.index == TORN
                answers = {r: get(r) for r in routes}
                want = {r: 404 if (r, key) == ("/where/1", "vms/placement/1") else 200 for r in routes}   # placed nowhere
                assert answers == want, (key, how, answers)
            # Values that are not strings: each its JSON text, as Nomad would hold it — the field's parse error, not the row's.
            with open(f, "w") as fh:
                fh.write(_NOT_STRINGS(raw))
            items, _ = box.vars.get(key)
            assert set(items.values()) == {"[7, true, Infinity]"}, items
            answers = {r: get(r) for r in routes}
            assert all(isinstance(s, int) for s in answers.values()), (key, answers)   # every route answers
            with open(f, "w") as fh:
                fh.write(raw)
        _forget_garbled()
        # A write replaces it whole; a create-only one conflicts; the controller's pass places again what nobody can read.
        f = box.vars._file("vms/placement/1")
        with open(f) as fh:
            raw = fh.read()
        with open(f, "w") as fh:
            fh.write(raw[:20])
        try:
            box.vars.put("vms/placement/1", {"worker": "w-1"}, cas=0)
            raise AssertionError("a create-only write over a row that is there")
        except Conflict:
            pass
        assert c2.placement(1) is None                                    # read as placed nowhere…
        c2.ensure_placed()
        assert c2.placement(1).worker == "w-1"                            # …placed again, the row written whole
        assert "garbled" not in c2.vars.get("vms/placement/1")[0]
    finally:
        srv.shutdown()
        _forget_garbled()


def test_a_key_the_file_store_cannot_name_a_file_is_refused_at_the_write_in_words_and_is_no_row_at_a_read():
    """The eleventh review, a minor: a recording named with 100 000 characters became a file name the disk refused —
    "File name too long", answered 503 "the store did not answer" with the store's local path in the reply, and a keep
    for such a camera dropped the connection. A key is at most `KEY_BYTES` here, as a file's name: longer is refused at
    the write (`KeyTooLong`, the store's limit as `TooLarge` says one: 413, in words, no path); a read finds no such row;
    a delete removes nothing. And a `source` of 100 000 characters, which is a field, not a key, is taken in a moment
    (the login hidden in it was looked for from every position: minutes of a console's thread)."""
    import time
    import urllib.error
    import urllib.request
    from w2cplatform.limits import TooLarge
    from w2cplatform.variables import KEY_BYTES, KeyTooLong
    from tests.test_console_gate import _console
    box = Box()
    long = "x" * 100_000
    try:
        box.vars.put("rec/recordings/" + long, {"cam": "1"})
        raise AssertionError("a key no file can be named after")
    except KeyTooLong as e:
        assert isinstance(e, TooLarge) and e.limit == KEY_BYTES == 246 and "a shorter name" in str(e) and len(str(e)) < 400
    assert box.vars.get("rec/recordings/" + long) == (None, 0)
    box.vars.delete("rec/recordings/" + long)
    edge = "vms/cameras/" + "y" * (KEY_BYTES - len("vms%2Fcameras%2F"))
    box.vars.put(edge, {"id": "1"})                                       # at the limit: a row
    assert box.vars.get(edge)[0] == {"id": "1"}
    ctl, rec, m, srv, base = _console(box)

    def call(method, path, body, key="k"):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method=method,
                                     headers={"Content-Type": "application/json", "Idempotency-Key": key})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
    try:
        for path, body in (("/rec/recordings", {"name": long, "cam": "1"}),
                           ("/rec/keeps", {"cam": long, "from": 1, "to": 2}),
                           ("/rec/volumes", {"name": long, "url": "file:///tmp/x", "server": "srv-1", "quota_bytes": 1 << 30})):
            status, said = call("POST", path, body, key=f"k{len(path)}")
            assert status == 413 and "a shorter name" in said["detail"] and box.root not in said["detail"], (path, said)
        status, said = call("POST", "/cameras", {"name": "c"}, key="%" * 100)   # an Idempotency-Key: 300 bytes as a file's name
        assert status == 413 and "a shorter name" in said["detail"], said
        t = time.monotonic()
        status, _ = call("POST", "/cameras", {"source": "driverpack://file/" + long + ".mp4"}, key="k-src")
        assert status == 201 and time.monotonic() - t < 5.0
    finally:
        srv.shutdown()

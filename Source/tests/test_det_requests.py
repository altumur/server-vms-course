"""The detectors' family of requests: one door, two kinds of asking, two budgets.

A scenario may ask the detectors for the STREAM — "watch camera 7 for plates for ten minutes" — or for the
ARCHIVE around its moment — "run plates over the minute before the alarm and the minute after". The first is
a detector row with an end, the second a scan job; both are written by the console from `det/requests/<id>`,
as the recorder's two kinds of asking are. A scan whose interval runs past what is recorded follows the
recording until its end, instead of calling the job done on the footage that happened to exist."""
import inspect

from w2cplatform.spec import SpecController
from vms.config import DET_SPEC, DETJOB_SPEC, REC_SPEC
from vms.detjobworker import DetJobWorker
from vms.jobs import detect_on_request, expire
from tests.vmsconftest import Box, door, footage, store


def _ctl(box, spec):
    return SpecController(spec, box.vars.as_writer("console", spec.acl_console()), box.objects, wall=box.wall)


def _site(box, cam="7", record=True):
    det, job, rec = _ctl(box, DET_SPEC), _ctl(box, DETJOB_SPEC), _ctl(box, REC_SPEC)
    if record:
        rec.create({"name": cam, "cam": cam})
    return det, job, rec


def _ask(box, rid, **fields):
    now = box.wall()
    box.vars.put(f"det/requests/{rid}", {"at": str(now), "valid_until": str(now + 30), "by": "auto/door",
                                         **{k: str(v) for k, v in fields.items()}})


def test_detect_is_a_detector_with_an_end_and_a_second_request_extends_it():
    """The operator's own `7-lpr` is off; its settings are what "plates on camera 7" means, so they travel."""
    box = Box(); det, job, rec = _site(box)
    det.create({"name": "7-lpr", "cam": "7", "kind": "lpr", "enabled": False, "params": "lpr-settings"})
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    assert detect_on_request(det, job, rec, box.wall()) == 1
    row = det.unit("7-lpr-auto")
    assert row["until"] == box.wall() + 600 and row["params"] == "lpr-settings" and row["cam"] == "7"
    assert box.vars.get("det/requests/f1-0")[0] is None                 # performed: nothing left to say

    box.wall.advance(120)
    _ask(box, "f2-0", action="detect", cam="7", kind="lpr", minutes=10)
    assert detect_on_request(det, job, rec, box.wall()) == 1
    assert det.unit("7-lpr-auto")["until"] == box.wall() + 600 and len(det.units()) == 2   # extended, not a second


def test_a_request_with_params_of_its_own_still_carries_the_detectors_mask_and_labels():
    """The review's third pass (Н-m7). A request that brought `params` brought ONLY them: the standing detector's
    mask and labels stayed behind, and the scenario's detector watched the whole frame on whatever worker came first.
    The request's params win; the rest of the setup travels."""
    box = Box(); det, job, rec = _site(box)
    det.create({"name": "7-lpr", "cam": "7", "kind": "lpr", "enabled": False, "params": "lpr-settings",
                "labels": ["gpu"], "mask": det.put_blob(b"m" * 64)})
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10, params="night-settings")
    assert detect_on_request(det, job, rec, box.wall()) == 1
    row, standing = det.unit("7-lpr-auto"), det.unit("7-lpr")
    assert row["params"] == "night-settings" and row["labels"] == ["gpu"] and row["mask"] == standing["mask"]


def test_a_camera_already_watched_by_hand_is_not_watched_twice():
    """An enabled detector with no end already counts every car; a second model would count each one twice."""
    box = Box(); det, job, rec = _site(box)
    det.create({"name": "7-lpr", "cam": "7", "kind": "lpr"})
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    assert detect_on_request(det, job, rec, box.wall()) == 0
    assert det.unit("7-lpr-auto") is None and box.vars.get("det/requests/f1-0")[0] is None


def test_a_detector_ends_by_the_clock_and_one_made_by_hand_never_does():
    box = Box(); det, job, rec = _site(box)
    det.create({"name": "9-motion", "cam": "9", "kind": "motion"})
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=1)
    detect_on_request(det, job, rec, box.wall())
    assert expire(det, box.wall()) == 0
    box.wall.advance(61)
    assert expire(det, box.wall()) == 1
    assert det.unit("7-lpr-auto") is None and det.unit("9-motion") is not None


def test_scan_is_a_job_around_the_moment_the_scenario_fired():
    box = Box(); det, job, rec = _site(box)
    det.create({"name": "7-lpr", "cam": "7", "kind": "lpr", "params": "lpr-settings"})
    at = box.wall()
    _ask(box, "f1-1", action="scan", cam="7", kind="lpr", before=120, after=30)
    assert detect_on_request(det, job, rec, box.wall()) == 1
    (j,) = job.units()
    assert j["rec"] == "7" and j["from"] == at - 120 and j["to"] == at + 30 and j["params"] == "lpr-settings"
    assert j["state"] == "queued" and box.vars.get("det/requests/f1-1")[0] is None
    assert det.unit("7-lpr-auto") is None                               # a scan is not a detector: the budgets stay apart


def test_a_scan_of_a_camera_nobody_records_is_refused_and_the_request_goes():
    box = Box(); det, job, rec = _site(box, record=False)
    _ask(box, "f1-0", action="scan", cam="7", kind="lpr")
    assert detect_on_request(det, job, rec, box.wall()) == 0
    assert job.units() == [] and box.vars.get("det/requests/f1-0")[0] is None


def test_a_request_too_late_to_mean_anything_is_dropped():
    box = Box(); det, job, rec = _site(box)
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    box.wall.advance(31)
    assert detect_on_request(det, job, rec, box.wall()) == 0
    assert det.units() == [] and box.vars.get("det/requests/f1-0")[0] is None


def test_a_request_the_store_would_not_take_stays_for_the_next_pass():
    box = Box(); det, job, rec = _site(box)
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    create = det.create
    det.create = lambda fields: (_ for _ in ()).throw(RuntimeError("det/units/7-lpr-auto: 10 conflicts"))
    assert detect_on_request(det, job, rec, box.wall()) == 0
    assert box.vars.get("det/requests/f1-0")[0] is not None
    det.create = create
    assert detect_on_request(det, job, rec, box.wall()) == 1


def test_the_console_runs_it_and_the_evaluator_may_file_it():
    """Written, tested and never called is the failure this project has had twice."""
    import vms.__main__ as m
    loop = (inspect.getsource(m._requests_loop) + inspect.getsource(m._requests_turn))
    assert "detect_on_request(" in loop and "expire(det_ctl" in loop
    assert "_requests_loop" in inspect.getsource(m.jobs)            # the VMS's housekeeping since the boundary's step 6
    assert 'requests_acl("vms", "rec", "det")' in inspect.getsource(m.autoworker)


def test_requests_are_looked_at_far_more_often_than_they_live():
    """A request is valid for thirty seconds (`autoworker.valid_for`), and the loop that turned it into a row
    ran every thirty: about one firing in six arrived expired and was dropped with a warning (the review's
    second pass). The requests have a loop of their own now, and its period is a fraction of their life — and
    the drops that still happen are a number on `/metrics`, not a line in a log."""
    import vms.__main__ as m
    from vms import jobs
    from w2cplatform import requests
    from w2cplatform.metrics import text as spec_metrics
    from vms.controller import VmsController
    from vms.config import SPEC
    assert inspect.signature(m._requests_loop).parameters["every"].default <= 2.0
    assert inspect.signature(m._reap_loop).parameters["every"].default >= 30.0     # the reaper did not get faster for it
    reaper = (inspect.getsource(m._reap_loop) + inspect.getsource(m._reap_turn))
    assert "record_on_request(" not in reaper and "detect_on_request(" not in reaper   # moved, not copied

    box = Box(); det, job, rec = _site(box)
    before = requests.expired.get("det", 0)
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    box.wall.advance(31)
    assert detect_on_request(det, job, rec, box.wall()) == 0 and requests.expired.get("det", 0) == before + 1
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    assert f'w2c_requests_expired_total{{sub="det"}} {before + 1}' in requests.metrics_lines()   # the loop's process's own numbers


def test_firings_that_overlap_widen_one_job_instead_of_making_a_job_each():
    """A swaying camera fires every second; every firing used to be its own two-minute scan — each second
    scanned a dozen times, thousands of rows a day, both of a worker's places taken by one minute (the review's
    second pass). Two firings five seconds apart are ONE job, reaching to the later `after`."""
    box = Box(); det, job, rec = _site(box)
    at = box.wall()
    _ask(box, "f1-0", action="scan", cam="7", kind="lpr", before=60, after=60)
    assert detect_on_request(det, job, rec, box.wall()) == 1
    box.wall.advance(5)
    _ask(box, "f1-5", action="scan", cam="7", kind="lpr", before=60, after=60)
    assert detect_on_request(det, job, rec, box.wall()) == 1
    (j,) = job.units()
    assert j["from"] == at - 60 and j["to"] == at + 65 and j["state"] == "queued"
    assert box.vars.get("det/requests/f1-5")[0] is None                    # performed: nothing left to say
    # inside what is already asked for: nothing to widen, and still one job
    _ask(box, "f1-6", action="scan", cam="7", kind="lpr", before=30, after=30)
    assert detect_on_request(det, job, rec, box.wall()) == 0 and len(job.units()) == 1
    # another model is another job: the budgets and the results are per model
    _ask(box, "f1-7", action="scan", cam="7", kind="motion", before=60, after=60)
    assert detect_on_request(det, job, rec, box.wall()) == 1 and len(job.units()) == 2
    # a job that ENDED is not widened — its worker let it go; a new firing is a new job
    job.update(j["id"], {"state": "done"})
    box.wall.advance(5)
    _ask(box, "f1-10", action="scan", cam="7", kind="lpr", before=60, after=60)
    assert detect_on_request(det, job, rec, box.wall()) == 1 and len(job.units()) == 3


def test_a_job_the_worker_finished_before_it_was_widened_is_not_done():
    """The reaper believes the worker's `done` only about the shape of the row the worker saw: a job widened
    by a firing between the worker's last pass and the reaper's is still running."""
    from w2cplatform.console import Heartbeat
    from vms.jobs import reap
    box = Box(); det, job, rec = _site(box)
    adm = SpecController(DETJOB_SPEC, box.vars.as_writer("detjobcontroller", DETJOB_SPEC.acl_controller()), box.objects, wall=box.wall)
    at = box.wall()
    _ask(box, "f1-0", action="scan", cam="7", kind="lpr", before=60, after=60)
    detect_on_request(det, job, rec, box.wall())
    (j,) = job.units()
    box.objects.put(DETJOB_SPEC.sub.heartbeat_key("j-1"), Heartbeat("j-1", box.wall(), [], {"server": "srv-1", "capacity": 2, "headroom": 2, "labels": "gpu"}).to_bytes())
    adm.ensure_placed()
    done = {"id": j["id"], "phase": "done", "from": at - 60, "to": at + 60, "covered": 120.0, "events": 1}
    box.wall.advance(5)
    _ask(box, "f1-5", action="scan", cam="7", kind="lpr", before=60, after=60)
    detect_on_request(det, job, rec, box.wall())                            # widened to `at + 65`
    box.objects.put(DETJOB_SPEC.sub.heartbeat_key("j-1"), Heartbeat("j-1", box.wall(), [done], {"server": "srv-1", "capacity": 2, "headroom": 2, "labels": "gpu"}).to_bytes())
    assert reap(job) == {"done": 0, "failed": 0} and job.unit(j["id"])["state"] == "queued"
    done["to"] = at + 65                                                    # the worker saw the new end and finished THAT
    box.objects.put(DETJOB_SPEC.sub.heartbeat_key("j-1"), Heartbeat("j-1", box.wall(), [done], {"server": "srv-1", "capacity": 2, "headroom": 2, "labels": "gpu"}).to_bytes())
    assert reap(job) == {"done": 1, "failed": 0}
    row = job.unit(j["id"])
    assert row["state"] == "done" and row["ended"] == box.wall()


def test_a_job_finished_for_days_is_forgotten_and_a_running_one_never_is():
    """Nothing removed a finished job's row before (the review's second pass): a scenario firing all night left
    the operator a list of hundreds of `done`. Three days after the reaper saw it end, the row goes — by the
    day it ENDED, not by its interval: a search over last month ends today."""
    from vms.jobs import FINISHED_RETENTION_SECONDS, forget_finished
    box = Box(); det, job, rec = _site(box)
    W = box.wall()
    job.create({"name": "old", "cam": "7", "rec": "7", "kind": "lpr", "from": W - 30 * 86400, "to": W - 29 * 86400})
    job.create({"name": "live", "cam": "7", "rec": "7", "kind": "lpr", "from": W - 30 * 86400, "to": W - 29 * 86400})
    job.update("old", {"state": "done", "ended": W})
    box.wall.advance(FINISHED_RETENTION_SECONDS - 1)
    assert forget_finished(job, box.wall()) == 0                            # an old interval, finished today: kept
    box.wall.advance(2)
    assert forget_finished(job, box.wall()) == 1
    assert [r["id"] for r in job.units()] == ["live"]                       # still running: never, whatever its dates
    import vms.__main__ as m
    assert "forget_finished(" in (inspect.getsource(m._reap_loop) + inspect.getsource(m._reap_turn))


def test_a_scenario_that_asks_for_what_cannot_be_is_refused_where_it_is_written():
    from vms.auto import Catalog
    from tests.vmsconftest import door_site
    box = Box(); door_site(box)
    cat = Catalog(box.vars)
    misfit, _ = cat.check({"then": [{"sub": "det", "action": "detect", "cam": "99", "kind": "lpr", "minutes": "5"}]})
    assert misfit == ["there is no camera 99 to detect"]
    misfit, _ = cat.check({"then": [{"sub": "det", "action": "scan", "cam": "7", "kind": "lpr"}]})
    assert misfit == ["nothing records camera 7: a scan reads the archive"]
    box.vars.put("rec/recordings/7", {"name": "7", "cam": "7"})
    assert cat.check({"then": [{"sub": "det", "action": "scan", "cam": "7", "kind": "lpr"}]})[0] == []


# -- a scan that reaches past what is recorded ------------------------------------------------------

class Every:
    def __init__(self, row): self.row = row
    def observe(self, now): return [(self.row["kind"], {"at": now})]
    def close(self): pass


LAG = 300.0                  # how far behind the visible footage runs: a block's worth, at this bitrate


def _recorded():
    """A box with a recorder's archive door over a volume: where the follower reads what is recorded."""
    box = Box()
    box.st = store()
    box.door = door(box, box.st)
    return box


def _footage(box, a, b, epoch=1):
    """Footage of recording 7, `[a, b)`, visible — a block that closed. The door's heartbeat said again: the
    clock moved."""
    footage(box.st, "7", epoch, a, b, step=10)
    box.door.announce()


def _follower(box, frm, to):
    ctl = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    ctl.create({"name": "7-lpr-f", "cam": "7", "rec": "7", "kind": "lpr", "from": frm, "to": to})
    box.vars.put(DETJOB_SPEC.sub.assignment("j-1"), {"units": "7-lpr-f", "rev": 1}, cas=0)
    return DetJobWorker("j-1", box.vars.as_writer("detjobworker", DETJOB_SPEC.sub.acl_worker()), box.objects,
                        models={"lpr": Every}, clock=box.clock, wall=box.wall, server="srv-1",
                        resource_root=box.archive, env={"LABELS": "gpu", "VISIBLE_LAG_SECONDS": str(LAG)}, step=60.0)


def _phase(w):
    return w.status_by_unit["7-lpr-f"]["phase"]


def test_a_scan_into_the_future_follows_the_recording_and_ends_when_the_footage_does():
    """Created at W for [W−600, W+300): ten minutes are visible, five are not yet. It scans what there is,
    FOLLOWS, scans the block that brings its end, and only then is done — and the ten minutes it scanned are
    not scanned again when the span they were part of grows."""
    box = _recorded(); W = box.wall()
    _footage(box, W - 600, W - 300); _footage(box, W - 300, W)
    w = _follower(box, W - 600, W + 300)
    w.reconcile_once()
    assert _phase(w) == "following" and w.status_by_unit["7-lpr-f"]["done_through"] == W
    events = w.status_by_unit["7-lpr-f"]["events"]
    box.wall.advance(320); _footage(box, W, W + 300)
    w.reconcile_once()
    assert _phase(w) == "running" and w.status_by_unit["7-lpr-f"]["done_through"] == W + 300
    assert w.status_by_unit["7-lpr-f"]["events"] == events + 5          # the new five minutes, a look a minute — and nothing twice
    w.reconcile_once()                                                  # as any job: done on the pass after its last stretch
    assert _phase(w) == "done"


def test_an_interval_entirely_in_the_future_follows_and_does_not_wait_for_another_server():
    box = _recorded(); W = box.wall()
    w = _follower(box, W + 60, W + 120)
    w.reconcile_once()
    assert _phase(w) == "following" and "following the recording" in w.status_by_unit["7-lpr-f"]["why"]


def test_a_recording_that_stopped_does_not_keep_a_follower_for_ever():
    """The camera went dark at W. Two lags after the end, what there is is the answer."""
    box = _recorded(); W = box.wall()
    _footage(box, W - 300, W)
    w = _follower(box, W - 300, W + 300)
    w.reconcile_once()
    assert _phase(w) == "following"
    box.wall.advance(300 + 2 * LAG + 1); box.door.announce()
    w.reconcile_once()
    assert _phase(w) == "done" and w.status_by_unit["7-lpr-f"]["covered"] == 300.0

"""The detectors' family of requests: one door, two kinds of asking, two budgets.

A scenario may ask the detectors for the STREAM — "watch camera 7 for plates for ten minutes" — or for the
ARCHIVE around its moment — "run plates over the minute before the alarm and the minute after". The first is
a detector row with an end, the second a scan job; both are written by the console from `det/requests/<id>`,
as the recorder's two kinds of asking are. A scan whose interval runs past what is recorded follows the
recording until its end, instead of calling the job done on the footage that happened to exist."""
import inspect

from w2cplatform.spec import SpecController
from vms.archive import Manifest, Segment
from vms.config import DET_SPEC, DETJOB_SPEC, REC_SPEC
from vms.detjobworker import DetJobWorker
from vms.jobs import detect_on_request, expire
from tests.conftest import Box


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
    loop = inspect.getsource(m._reap_loop)
    assert "detect_on_request(" in loop and "expire(det_ctl" in loop
    assert 'requests_acl("vms", "rec", "det")' in inspect.getsource(m.autoworker)


def test_a_scenario_that_asks_for_what_cannot_be_is_refused_where_it_is_written():
    from vms.auto import Catalog
    from tests.conftest import door_site
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


SEG = 300.0


def _footage(box, a, b, epoch=1):
    Manifest(box.archive, "7").append(Segment("7", epoch, a, b, f"rec/7/e{epoch}/{int(a)}.mp4", 1000))


def _follower(box, frm, to):
    ctl = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    ctl.create({"name": "7-lpr-f", "cam": "7", "rec": "7", "kind": "lpr", "from": frm, "to": to})
    box.vars.put(DETJOB_SPEC.sub.assignment("j-1"), {"units": "7-lpr-f", "rev": 1}, cas=0)
    return DetJobWorker("j-1", box.vars.as_writer("detjobworker", DETJOB_SPEC.sub.acl_worker()), box.objects,
                        models={"lpr": Every}, clock=box.clock, wall=box.wall, server="srv-1",
                        archive_root=box.archive, env={"LABELS": "gpu", "SEGMENT_SECONDS": str(SEG)}, step=60.0)


def _phase(w):
    return w.status_by_unit["7-lpr-f"]["phase"]


def test_a_scan_into_the_future_follows_the_recording_and_ends_when_the_footage_does():
    """Created at W for [W−600, W+300): ten minutes are on the disk, five are not yet. It scans what there is,
    FOLLOWS, scans the segment that brings its end, and only then is done."""
    box = Box(); W = box.wall()
    _footage(box, W - 600, W - 300); _footage(box, W - 300, W)
    w = _follower(box, W - 600, W + 300)
    w.reconcile_once()
    assert _phase(w) == "following" and w.status_by_unit["7-lpr-f"]["done_through"] == W
    box.wall.advance(320); _footage(box, W, W + 300)
    w.reconcile_once()
    assert _phase(w) == "running" and w.status_by_unit["7-lpr-f"]["done_through"] == W + 300
    w.reconcile_once()                                                  # as any job: done on the pass after its last stretch
    assert _phase(w) == "done"


def test_an_interval_entirely_in_the_future_follows_and_does_not_wait_for_another_server():
    box = Box(); W = box.wall()
    w = _follower(box, W + 60, W + 120)
    w.reconcile_once()
    assert _phase(w) == "following" and "following the recording" in w.status_by_unit["7-lpr-f"]["why"]


def test_a_recording_that_stopped_does_not_keep_a_follower_for_ever():
    """The camera went dark at W. Two segments after the end, what there is is the answer."""
    box = Box(); W = box.wall()
    _footage(box, W - 300, W)
    w = _follower(box, W - 300, W + 300)
    w.reconcile_once()
    assert _phase(w) == "following"
    box.wall.advance(300 + 2 * SEG + 1)
    w.reconcile_once()
    assert _phase(w) == "done" and w.status_by_unit["7-lpr-f"]["covered"] == 300.0

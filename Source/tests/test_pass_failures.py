"""Two jobs in one loop, and what it costs to report them as one.

The controller's pass does two different things: it PLACES units, and it
PUBLISHES a copy of where they went for the layer above. They fail
independently and mean different things to whoever is woken up — and until
now they shared one `try` and one sentence in the log.

The sentence was "placement pass failed", and `publish_snapshot()` is the last
call in the block, so the message named the one thing that had *not* failed.
The other direction was worse: a placement that threw skipped the publish, the
layer above quietly went stale, and the word "snapshot" appeared nowhere.
"""
import logging

from vms.config import SPEC
from vms.controller import VmsController
from vms.__main__ import _controller_loop, stop
from w2cplatform.console import SpecConsole
from w2cplatform.objects import FsObjectStore
from tests.conftest import Box


class _Recorder(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def _one_pass(ctl) -> list[str]:
    """One turn of the REAL loop — the same function `__main__.controller` runs.

    Driven by the loop's own `stop.wait(5)` at the end of a pass: it sets the flag,
    so the pass runs once and the `while` exits. The point of going through
    `_controller_loop` rather than calling the four methods by hand is that the
    thing under test IS the try blocks.

    `stop` is cleared FIRST: it is the module's own flag, and a loop that finds it set runs no pass at all.

    WHAT IS KNOWN ABOUT THE FLAKE, AND WHAT IS NOT (the review's fifth pass saw `test_a_failed_placement_still_
    publishes_what_is_known` fail in one full run and pass alone; the sixth asked for the cause to be proved).
    `vms.__main__` used to install its SIGTERM/SIGINT handler at import — for the whole test run. A signal that
    reached the runner did not stop it: it set `stop`, nothing else in the suite reads it, and the first test to come
    through this helper ran no pass — `AssertionError: []` — and cleared the flag for the next, which passed.

    Proved, on the tree before the fix (`c61aee8^`), under a watch on the runner's signals and on every `stop.set()`:
      - one SIGTERM sent to the runner's pid from OUTSIDE, five minutes before this module: the run goes on, and
        exactly that one test fails, with exactly that assertion — 687 passed, 2 failed (the other is the disk's);
      - three whole runs with nothing sent from outside: no signal reaches the runner, and `stop` is set by this
        helper alone. No test sends one that could: the daemon is stopped through `Popen.terminate`/`kill` (its own
        pid, and only while it is not reaped), the tests that freeze it send SIGSTOP/SIGCONT to that pid, nothing
        signals a process group — though the daemon IS in the runner's group — and obsd signals nobody.
    Not proved: what sent a signal to the reviewer's run — a tool's timeout, a `kill` from another shell, an
    interrupt. So the cause of THAT run is still not known; what is closed is the mechanism, three ways: the handler
    is installed only when the module is run, this helper clears the flag, and the runner fails any module or test
    that takes its signals (`tests/run.py`)."""
    stop.clear()
    rec = _Recorder()
    logging.getLogger().addHandler(rec)
    real_wait = stop.wait

    def wait_once(timeout=None):
        stop.set()
        return True

    stop.wait = wait_once
    try:
        _controller_loop(ctl)
    finally:
        stop.wait = real_wait
        logging.getLogger().removeHandler(rec)
        stop.clear()
    return rec.lines


def _cluster(box, cameras=2, objects=None):
    ctl = VmsController(box.vars, objects or box.objects, capacity=50, wall=box.wall)
    for i in range(cameras):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    return ctl


def test_a_failed_publish_is_not_reported_as_a_failed_placement():
    """The bug this was written for. Placement worked; the log must not say it did not."""
    box = Box()
    tiny = FsObjectStore(box.root + "/tiny", max_bytes=64)          # the shard will not fit
    ctl = _cluster(box, cameras=2, objects=tiny)
    ctl.ensure_placed(workers=["w-1"])

    lines = _one_pass(ctl)
    assert any("publishing the snapshot failed" in ln for ln in lines), lines
    assert not any("placement pass failed" in ln for ln in lines), lines
    # …and the placement it did is still there: the pass did its first job
    assert ctl.where(1) == "w-1"


def test_a_failed_placement_still_publishes_what_is_known():
    """The other direction. Placement threw, so the two are now separate — and the
    copy the layer above reads still moves forward instead of silently freezing."""
    box = Box()
    ctl = _cluster(box, cameras=1)

    def boom(*a, **kw):
        raise RuntimeError("the store went away mid-pass")

    ctl.ensure_placed = boom
    lines = _one_pass(ctl)
    assert any("placement pass failed" in ln for ln in lines), lines
    assert not any("publishing the snapshot failed" in ln for ln in lines), lines
    assert box.objects.list("vms/snapshot/"), "the publish was skipped because placement failed"


def test_one_pass_runs_a_pass_whatever_signal_reached_the_runner_before():
    """The mechanism of the flake above, closed in the helper: `stop` left set by whatever came before — what the
    old handler did with a signal sent to the run — and the helper runs its pass all the same. No signal is sent
    here: a test that signals its own runner is the thing the runner's guard is there to catch."""
    box = Box()
    ctl = _cluster(box, cameras=1)
    stop.set()
    _one_pass(ctl)
    assert ctl.pass_report() is not None and box.objects.list("vms/snapshot/")   # the pass ran, and published
    assert not stop.is_set()


def test_importing_the_entry_point_takes_none_of_the_runners_signals():
    """The other half, and the one the fix had no test for: `vms.__main__` imported — as this module imports it, and
    six others — installs no handler. One installed at import swallows a SIGTERM or SIGINT sent to the test run,
    which then goes on with `stop` set. The handlers this process has now are not the entry point's, and the lines
    that install them are under `if __name__ == "__main__"`."""
    import inspect
    import signal
    import vms.__main__ as m
    for s in (signal.SIGTERM, signal.SIGINT):
        assert getattr(signal.getsignal(s), "__module__", None) != m.__name__, f"importing vms.__main__ took {s.name}"
    src = inspect.getsource(m)
    assert "signal.signal(" not in src.split('if __name__ == "__main__":')[0], "a handler installed at import"
    assert "signal.signal(" in src.split('if __name__ == "__main__":')[1]          # …and the process still stops on SIGTERM


def test_the_age_of_the_published_copy_is_on_metrics():
    """A log line is on a host nobody is looking at. This is the number that climbs.

    Read from the STORE and not from the process: the controller has no port, is
    restarted freely, and two may be running — so the question is answered by
    whoever can read the objects, which is what lets a console put it on /metrics."""
    box = Box()
    ctl = _cluster(box, cameras=1)
    con = SpecConsole(ctl)

    # never published is not the same as published a moment ago, and the gauge says so
    assert ctl.snapshot_age() is None
    assert "vms_snapshot_age_seconds -1" in con.metrics_text()

    ctl.ensure_placed(workers=["w-1"])
    ctl.publish_snapshot()
    assert "vms_snapshot_age_seconds 0" in con.metrics_text()

    box.wall.advance(90)                                            # the controller stopped publishing
    assert round(ctl.snapshot_age()) == 90
    assert "vms_snapshot_age_seconds 90" in con.metrics_text()


def test_the_age_is_the_stalest_shard_and_never_the_freshest():
    """A number like this must only ever be wrong in the pessimistic direction.
    One shard that stopped being rewritten IS the cluster being behind, and taking
    the newest would report an RPO better than the real one."""
    import json
    box = Box()
    ctl = _cluster(box, cameras=4)
    ctl.ensure_placed(workers=["w-1", "w-2"])
    ctl.publish_snapshot()

    ctl.snapshot_age()                                              # the reader's first look
    box.wall.advance(300)                                           # w-1's shard stopped moving; w-2's goes on
    fresh = json.loads(box.objects.get("vms/snapshot/w-2"))
    box.objects.put("vms/snapshot/w-2", json.dumps({**fresh, "ts": box.wall()}).encode())

    assert round(ctl.snapshot_age()) == 300, "the freshest shard was taken, and the RPO looked better than it is"


# -- the workers' loops: a pass that raises half-way must not take the leases with it -------------------------

class _OnePass:
    """One turn of a worker's `run`: the first `is_set` lets the pass in, the second ends the loop."""
    def __init__(self): self.asked = 0
    def is_set(self): self.asked += 1; return self.asked > 1
    def wait(self, s): return None


def _workers(box):
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC, LIVE_SPEC, SURVEY_SPEC
    from vms.detjobworker import DetJobWorker
    from vms.detworker import DetWorker
    from vms.liveworker import LiveWorker
    from vms.surveyworker import SurveyWorker
    common = dict(clock=box.clock, wall=box.wall, server="srv-1", env={"LABELS": "gpu"})
    live_vars = box.vars.as_writer("liveworker", ["live/epoch/*", "live/slots/*", "live/streams/*"])
    return [DetWorker("d-1", box.vars.as_writer("detworker", ["det/epoch/*", "det/slots/*"]), box.objects,
                      archive_root=box.archive, **common),
            DetJobWorker("j-1", box.vars.as_writer("detjobworker", DETJOB_SPEC.sub.acl_worker()), box.objects,
                         archive_root=box.archive, **common),
            SurveyWorker("s-1", box.vars.as_writer("surveyworker", SURVEY_SPEC.sub.acl_worker()), box.objects,
                         archive_root=box.archive, **common),
            LiveWorker("g-1", live_vars, box.objects, ctl=SpecController(LIVE_SPEC, live_vars, box.objects, wall=box.wall), **common)]


def test_a_pass_that_raises_half_way_still_renews_the_leases_and_heartbeats():
    """M19 of the review, the remainder. The heartbeat had been given a `try` of its own; `renew_leases()` was
    still the LAST line of `reconcile_once`, so the one exception that skipped the heartbeat also skipped the
    renewal — the worker was reported alive, held its units, and `may_write` ran out on all of them twenty-five
    seconds later. Every worker here: the four that renewed at the end of the pass (det, detjob, survey, live)."""
    box = Box()
    for w in _workers(box):
        w.take_epoch("u")
        box.clock.advance(10)                                       # the lease is ten seconds old; the renewal stamps it anew

        def boom(*a, **kw):
            raise RuntimeError("the store went away mid-pass")

        w.reconcile_once = boom
        rec = _Recorder(); logging.getLogger().addHandler(rec)
        try:
            w.run(poll=0, stop=_OnePass())
        finally:
            logging.getLogger().removeHandler(rec)
        assert any("pass failed" in ln for ln in rec.lines), (type(w).__name__, rec.lines)
        assert w.leases["u"].last_renewal == box.clock(), f"{type(w).__name__}: the pass raised and the lease was not renewed"
        assert w.may_write("u"), type(w).__name__
        hb = box.objects.get(w.sub.heartbeat_key(w.name))
        assert hb is not None, f"{type(w).__name__}: no heartbeat after a failed pass"


def test_a_cluster_with_no_units_publishes_that_it_has_none():
    """Feedback AA. A cluster with no units used to publish nothing — no shard to write — and "there are
    none" read as "never published". Above the cluster that is two different answers: М12's member that has
    not published does not report (Lesson 10), and a camera's cluster before its camera stayed "never
    reported" for ever. So a pass over an empty cluster writes an empty `unplaced` shard, and once there is
    a unit, the shard is emptied like any other the pass did not fill."""
    import json
    box = Box()
    ctl = _cluster(box, cameras=0)
    assert ctl.snapshot_age() is None                                # before any pass: never published
    ctl.publish_snapshot()
    shard = json.loads(box.objects.get("vms/snapshot/unplaced"))
    assert shard["cameras"] == [] and shard["worker"] is None and ctl.snapshot_age() == 0
    assert ctl.snapshot()["cameras"] == []                            # published, and it says none

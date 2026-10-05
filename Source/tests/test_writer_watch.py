"""Lesson 10 — is the writer writing (feedback, point U).

The pipeline's watchdog sees frames arrive. Whether they reach the volume after the sink, nothing checked —
and the product lost fifteen and twenty-seven minutes that way with every sign saying "writing". The
recorder compares what it OFFERED its sinks with what LANDED, says stuck or losing in its heartbeat, and
reopens the writer, at most every ten minutes.
"""
from vms import volumes
from vms.config import REC_SPEC
from vms.writerwatch import BLOCK, WriterWatch, describe
from tests.test_backup_archive import _site

MB = BLOCK


def test_a_quiet_camera_is_not_stuck_and_a_standing_volume_with_megabytes_waiting_is():
    w = WriterWatch()
    t = 0.0
    for _ in range(20):                                   # a quiet camera: half a block in ten minutes
        t += 30; w.observe(int(t * 800), 0, t)
    assert w.state["state"] == "ok"                       # nothing outstanding worth a word

    w = WriterWatch()
    w.observe(0, 0, 0.0)
    w.observe(5 * MB, 0, 30.0)
    assert w.state["state"] == "ok"                       # not for a minute yet
    w.observe(8 * MB, 0, 61.0)
    assert w.state["state"] == "stuck" and w.state["outstanding"] == 8 * MB
    assert describe(w.state) == "writing stuck: 8 MB not landed for 61 s"
    w.observe(9 * MB, 9 * MB, 70.0)                       # it moved
    assert w.state["state"] == "ok"


def test_a_volume_that_moves_but_takes_two_thirds_is_losing():
    """The case a "does the volume move" watch never sees, and the one the product's box had: 66–69 %."""
    w = WriterWatch()
    for i in range(0, 11):
        t = i * 30.0
        w.observe(int(i * 3 * MB), int(i * 2 * MB), t)   # a third of every megabyte goes nowhere
    assert w.state["state"] == "losing" and w.state["share"] == 0.67
    assert describe(w.state) == "losing writes: 67 % landing over 300 s"


def test_the_writer_is_reopened_once_in_ten_minutes_however_long_it_stays_wrong():
    w = WriterWatch()
    w.observe(0, 0, 0.0); w.observe(10 * MB, 0, 100.0)
    assert w.reopen_due(100.0) is True
    assert [w.reopen_due(t) for t in (160.0, 400.0, 699.0)] == [False, False, False]
    w.observe(20 * MB, 0, 700.0)
    assert w.reopen_due(700.0) is True


def test_the_recorder_says_it_in_its_heartbeat_reopens_the_writer_and_the_console_says_it_on_the_volume():
    box, rec_ctl, primary, backup, holder = _site()
    act = primary.actuator
    act.offered_bytes["1"] = 0
    primary.writer_pass()
    assert primary.heartbeat_extra()["writer"] == {"state": "ok"}

    for _ in range(3):                                    # megabytes handed to the sink, nothing reaching the volume
        box.wall.advance(30); act.offered_bytes["1"] += 4 * MB
        primary.writer_pass()
    assert primary.heartbeat_extra()["writer"]["state"] == "stuck"
    assert ("stop", "1") in act.calls and "1" not in primary.reconciler.running()   # reopened: the reconciler starts it again
    first = primary.store
    assert primary.engine_lost
    primary.lease_pass()
    assert primary.store is not first and primary.store.writer is not None       # …into a writer opened again

    from w2cplatform.contract import Slot                 # pinned by VOLUME here; on a cluster it holds the volume
    box.vars.put("rec/holds/disks", Slot("disks", primary.instance, box.wall() + 45, False, 1).to_items())
    primary.heartbeat_once()
    served = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)
    disks = next(v for v in served["volumes"] if v["name"] == "disks")
    assert disks["served_by"] and disks["writing"].startswith("writing stuck:")


def test_an_actuator_that_does_not_measure_says_nothing():
    box, rec_ctl, primary, backup, holder = _site()
    box.wall.advance(600)
    assert primary.writer_pass() == {"state": "ok"} and primary.writer.samples == []


def test_what_was_offered_stays_offered_when_a_recording_stops():
    """Offered was the SUM over the running recordings: one that stopped took its megabytes out of the sum,
    `outstanding` went negative, and a volume that had taken nothing of them was never called stuck (the review's
    second pass). Offered is summed by deltas now, and nothing is taken back."""
    from w2cplatform.spec import SpecController
    box, rec_ctl, primary, backup, holder = _site()
    SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall).create({"name": "2", "cam": "1", "home": "disks"})
    rec_ctl.ensure_placed()
    assert primary.reconcile_once() == [("start", "2")]
    act = primary.actuator
    act.offered_bytes["1"] = act.offered_bytes["2"] = 0
    primary.writer_pass()
    act.offered_bytes["1"] += 2 * MB; act.offered_bytes["2"] += 2 * MB           # four megabytes, nothing landing
    box.wall.advance(30); primary.writer_pass()
    primary._actuate("stop", {"id": "1"}); primary.reconciler.drop("1")   # one recording stops
    box.wall.advance(31)
    assert primary.writer_pass()["state"] == "stuck"                                 # the four megabytes are still owed

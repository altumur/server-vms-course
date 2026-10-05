"""Lesson 6 — the recorder: the fourth subsystem, and the only one placed on
top of the archive. A recording is a unit named by its camera; the recorder
subscribes to the fan-out of whichever worker holds the camera — from the
heartbeat, never a second connection — takes its own epoch, and writes
footage into the stream <cam>/e<epoch> of the volume ITS server holds. The
worker that holds the camera may be anywhere; the recorder must be where the
disks are. Two writers, one camera: events on the resource, footage in the volume."""
import os

from w2cplatform.events import subsystems_under
from w2cplatform.spec import SpecController
from w2cplatform.variables import Forbidden
from vms.config import DET_SPEC, LIVE_SPEC, REC_SPEC, SPEC, live_shm, live_url
from vms.controller import VmsController
from vms.recworker import RecSink
from vms.worker import FakeActuator, VmsWorker, fake_samples
from tests.vmsconftest import Box, recorder


def _box():
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con_vars = box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console() + DET_SPEC.acl_console() + REC_SPEC.acl_console())
    con = VmsController(con_vars, box.objects, wall=box.wall)
    rec_con = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)                      # the console's door to recordings
    rec_ctl = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.resource_root)
    w.heartbeat_once(); con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    return box, ctl, con, rec_con, rec_ctl, w


def _recorder(box, name="r-1", server="srv-1", capacity=50):
    """A recorder on `server`, its server's volume open — a directory of its own per server, as two boxes have."""
    r = recorder(box, name, server, capacity=capacity, env={"ARCHIVE_VOLUME": f"file://{os.path.join(box.root, 'vol-' + server)}"})
    r.lease_pass(); r.heartbeat_once()
    return r


def test_a_recording_is_a_unit_placed_on_the_archive_and_fed_by_the_workers_fan_out():
    box, ctl, con, rec_con, rec_ctl, w = _box()
    assert REC_SPEC.requires == "resource" and rec_ctl.policy() == {"servers": "distinct"} and ctl.policy() == {"servers": "shared"}   # the recorder is the one that must be where the disks are, one per server; workers are not
    assert REC_SPEC.near == "none" and REC_SPEC.home == "home"                                      # it follows nothing; it is the one pinned to disks, and its row names which
    assert SPEC.near == "rec" and SPEC.home == "near"                                               # the camera is the one that can move, so it is the one that follows
    r = _recorder(box); r2 = _recorder(box, "r-2", "srv-2", capacity=1)                            # two servers with archives; the camera's worker is on srv-1
    assert r.name == "r-1" and r.SUB.name == "rec" and box.vars.list("rec/slots/") == ["rec/slots/r-1", "rec/slots/r-2"]
    # the operator records camera 1: a row under rec/, the console's token; placement is the rec controller's pass
    row = rec_con.create({"name": "1", "cam": "1", "retention_days": 7})
    assert row["id"] == "1" and row["retention_days"] == 7 and box.vars.list("rec/recordings/") == ["rec/recordings/1"]
    try:
        rec_con.place("1"); raise AssertionError("a console token never writes placement")
    except Forbidden:
        pass
    pl = rec_ctl.ensure_placed()[0]
    assert pl.worker == "r-1" and pl.reason.endswith("on srv-1, whose resource is unknown")         # placed by the disks, not by where the camera happens to be
    # the recorder's pass: the pipeline is built from the worker's tee — its shared-memory branch, since the worker is on THIS
    # server (no RTSP hop, no fan-out process on the recording path) — under the RECORDER's epoch
    assert r.reconcile_once() == [("start", "1")]
    started = r.actuator.started["1"]
    assert started["source"] == live_shm(1) == "shm:///run/vms/1.shm" and started["via"] == "shm" and started["source_server"] == "srv-1"
    assert live_url("srv-1", 1) == "rtsp://srv-1:8554/1"                                           # what a recorder on another server would read
    assert started["epoch"] == 1 and box.vars.get("rec/epoch/1")[0] == {"epoch": "1"} and w.epochs == {"1": 1}   # two epochs, two writers, one camera
    sink = started["sink"]                                                                          # what it writes into: its volume's writer, as `1/e1`
    assert isinstance(sink, RecSink) and sink.store is r.store and (sink.unit, sink.epoch) == ("1", 1)
    r.heartbeat_once()
    st = rec_ctl.workers_seen()["r-1"].status[0]
    assert st["phase"] == "running" and st["cam"] == "1" and st["source"] == "shm:///run/vms/1.shm" and st["via"] == "shm" and st["epoch"] == 1
    assert "rec_recordings_running 1" in r.metrics_text()
    # what the pipeline hands its sink lands in the volume, as the stream `1/e1` — and the resource's tree stays events-only
    assert r.actuator.feed("1", box.wall() - 600, box.wall()) == {"OK": 600}
    r.store.seal()
    assert [(s.stream, s.start, s.end) for s in r.store.spans("1")] == [("1/e1", box.wall() - 600, box.wall())]
    w.observe(1, "motion")
    assert subsystems_under(box.resource_root) == {"vms": ["1"]}
    # the camera's worker fails over to srv-2: the recorder re-subscribes — to the RTSP fan-out now, the worker is on another
    # server — same recorder, same disks, same tree; a new pipeline is a new epoch (e1 before the move, e2 after, both here)
    w2 = VmsWorker("w-2", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2", resource_root=box.resource_root)
    ctl.move(1, "w-2", "test"); w2.reconcile_once(); w2.heartbeat_once(); w.reconcile_once(); w.heartbeat_once()
    assert r.resubscribe() == ["1"] and r.actuator.calls[-1] == ("stop", "1")
    box.clock.advance(10)
    assert r.reconcile_once() == [("start", "1")] and r.actuator.started["1"]["source"] == "rtsp://srv-2:8554/1" and r.actuator.started["1"]["via"] == "rtsp"
    assert r.actuator.started["1"]["epoch"] == 2 and rec_ctl.where("1") == "r-1" and w2.epochs == {"1": 2}   # the recording did not move; its source did
    # two more cameras, both held on srv-2 by w-2. The recordings go where their DISKS are — the operator
    # named one srv-2 and the other srv-1 — and each camera then comes to its recording, so both recorders
    # read shared memory. The recorder never chases the camera: it is the one thing here that cannot move.
    con.create_camera({"name": "yard", "source": "driverpack://file/yard.mp4"}); con.create_camera({"name": "dock", "source": "driverpack://file/dock.mp4"})
    ctl.ensure_placed(); ctl.move(2, "w-2", "test"); ctl.move(3, "w-2", "test")
    w2.reconcile_once(); w2.heartbeat_once(); w.reconcile_once(); w.heartbeat_once()
    rec_con.create({"name": "2", "cam": "2", "home": "srv-2"}); rec_con.create({"name": "3", "cam": "3", "home": "srv-1"})
    pl2, pl3 = rec_ctl.ensure_placed()[-2:]                                                        # (the pass returns every placement, camera 1's first)
    assert (pl2.worker, pl3.worker) == ("r-2", "r-1")
    assert pl2.reason.endswith("on srv-2, whose resource is unknown, at home on srv-2")
    assert pl3.reason.endswith("on srv-1, whose resource is unknown, at home on srv-1")
    r2.reconcile_once(); r2.heartbeat_once(); r.reconcile_once(); r.heartbeat_once()
    # and now the cameras come to their recordings — camera 1 back to srv-1, where its recording never moved,
    # and camera 3 with it; camera 2 is already on srv-2 where r-2 writes it
    assert ctl.ensure_home(2) == [(1, "w-2", "w-1"), (3, "w-2", "w-1")]
    assert "it follows rec onto srv-1" in ctl.placement(3).reason
    w.reconcile_once(); w.heartbeat_once(); w2.reconcile_once(); w2.heartbeat_once()
    box.clock.advance(10)
    assert r2.reconcile_once() == [] and r2.actuator.started["2"]["via"] == "shm" and r2.actuator.started["2"]["source"] == "shm:///run/vms/2.shm"
    assert sorted(r.resubscribe()) == ["1", "3"]                                                   # both sources are on this server again
    box.clock.advance(10)                                                                          # past the restart's backoff
    assert r.reconcile_once() == [("start", "1"), ("start", "3")]
    for cid in ("1", "3"):                                                                         # the network hop is gone: shared memory again
        assert r.actuator.started[cid]["via"] == "shm" and r.actuator.started[cid]["source"] == f"shm:///run/vms/{cid}.shm"


def test_a_recording_waits_while_nobody_holds_the_camera_and_records_when_someone_does():
    box, ctl, con, rec_con, rec_ctl, w = _box()
    con.create_camera({"name": "yard", "source": "driverpack://file/yard.mp4"})                    # camera 2: created, not placed yet
    r = _recorder(box)
    rec_con.create({"name": "2", "cam": "2"}); rec_ctl.ensure_placed()
    assert r.reconcile_once() == [("failed", "2")]                                                   # no fan-out to subscribe to
    r.heartbeat_once()
    st = rec_ctl.workers_seen()["r-1"].status[0]
    assert st["phase"] == "waiting" and st["why"] == "camera held by nobody" and st["source"] is None
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()                                   # the worker takes it
    box.clock.advance(10)
    assert r.reconcile_once() == [("start", "2")] and r.actuator.started["2"]["source"] == "shm:///run/vms/2.shm"   # held here: the tee's shared memory
    # a camera with no recording is watched, not recorded: it is held (live, detection, events), and has no stream
    assert rec_ctl.units() == [{"id": "2", "name": "2", "cam": "2", "retention_days": 30, "enabled": True, "labels": [], "home": "", "until": 0.0, "min_depth_days": 0.0, "when": "always", "revision": 1}]
    assert [c["id"] for c in ctl.cameras()] == [1, 2] and subsystems_under(box.resource_root) == {}
    w.observe(1, "motion")
    assert subsystems_under(box.resource_root) == {"vms": ["1"]}
    # stop recording: the row goes, the placement is taken back on the next pass, the footage stays until the ring needs the room
    rec_con.delete("2"); rec_ctl.unplace_deleted()
    assert rec_ctl.assignment("r-1").units == [] and r.reconcile_once() == [("stop", "2")]


def test_a_recording_started_twice_writes_two_streams_and_overwrites_nothing():
    """The epoch is in the stream's NAME. A pipeline restarted is a new epoch and a new stream — and a zombie that
    went on writing for a moment under the old one wrote its own stream, not over the survivor's. The volume
    keeps both; the index says which epoch owns which minutes (Lesson 3)."""
    box, ctl, con, rec_con, rec_ctl, w = _box()
    r = _recorder(box)
    rec_con.create({"name": "1", "cam": "1"})
    rec_ctl.ensure_placed()
    assert r.reconcile_once() == [("start", "1")]
    t = box.wall()
    r.actuator.feed("1", t - 120, t - 60)
    old = r.actuator.started["1"]["sink"]
    r.actuator("stop", {"id": "1"}); r.reconciler.forget("1")
    box.clock.advance(10)
    assert r.reconcile_once() == [("start", "1")] and r.actuator.started["1"]["epoch"] == 2
    r.actuator.feed("1", t - 60, t)
    for smp in fake_samples(t - 60, t - 30):
        old.put(smp)                                                                               # the zombie, a moment late
    old.finish()
    r.store.seal()
    assert sorted({s.stream for s in r.store.spans("1")}) == ["1/e1", "1/e2"]
    assert [(x["epoch"], x["fenced"]) for x in r.store.timeline("1", t - 120, t, current_epoch=2)] == [(1, True), (2, False)]

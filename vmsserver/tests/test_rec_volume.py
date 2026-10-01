"""The recorder writes into a VOLUME — ObjectStorage, through the host's `obsd` — and nothing else.

A recorder takes a volume (declared, or its server's own), opens it through the daemon — formatting it at its
quota if it is new — and becomes its one writer on the host, under the owner `rec:<volume>`. A recording's
pipeline writes the stream `<recording>/e<epoch>`; what it wrote is readable once its block is closed; a
recorder killed and started again picks up the writer it left; footage fetched into a gap goes into the
recording's backfill stream; the archive door hands out timelines and frames, never files."""
import json
import time
import urllib.request

from w2cplatform.obsd import unix_s
from w2cplatform.spec import SpecController
from vms import volumes
from vms.config import DET_SPEC, LIVE_SPEC, REC_SPEC, SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker, fake_samples
from tests.conftest import OBSD_LINGER_MS, Box, recorder


def _site():
    """A camera held by a worker on srv-1, and a recording of it placed on a recorder of srv-1."""
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con_vars = box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console() + DET_SPEC.acl_console() + REC_SPEC.acl_console())
    con = VmsController(con_vars, box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive)
    w.heartbeat_once(); con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()
    rec_con = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)
    rec_ctl = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    return box, rec_con, rec_ctl


def _recording(box, rec_con, rec_ctl, r, name="1"):
    rec_con.create({"name": name, "cam": "1"})
    rec_ctl.ensure_placed()
    r.lease_pass()
    assert r.reconcile_once() == [("start", name)]


def test_a_recorder_with_nothing_declared_formats_its_servers_volume_and_records_into_it():
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    assert r.volume == "srv-1" and r.store.formatted and r.store.url == f"file://{box.archive}/volume"
    epoch = r.epochs["1"]
    assert r.actuator.feed("1", box.wall() - 120, box.wall()) == {"OK": 120}
    assert r.our_coverage("1") == []                                   # written is not visible: the block is open
    r.store.seal()
    assert r.our_coverage("1") == [(box.wall() - 120, box.wall())]
    assert [s.stream for s in r.store.spans("1")] == [f"1/e{epoch}"]  # the epoch is in the stream's name


def test_a_recorder_killed_and_started_again_picks_up_the_writer_it_left():
    """No stale lock to wait out and nothing to recover: the daemon kept the writer DETACHED, and the recorder
    started again under the same slot names the same owner, `rec:<volume>`."""
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    r.actuator.feed("1", box.wall() - 60, box.wall())
    r.session.vanish()                                                 # kill -9: no BYE, no close
    time.sleep(OBSD_LINGER_MS / 1000 + 0.3)                            # the daemon notices the session is gone
    box.wall.advance(5)
    again = recorder(box)
    again.lease_pass()
    assert again.store is not None and again.store.reattached and again.store.formatted is False
    again.store.seal()
    assert again.our_coverage("1") == [(box.wall() - 65, box.wall() - 5)]   # nothing the dead one wrote was lost


def test_leaving_a_volume_closes_its_writer_before_the_hold_goes():
    """A declared volume handed over: the writer is closed — its flush puts the last minutes on the volume —
    and only then is the hold let go. Whoever takes it next mounts a volume with no writer left in it."""
    box, rec_con, rec_ctl = _site()
    vol_dir = box.archive + "-net"
    volumes.write(box.vars, {"name": "net", "kind": "network", "url": f"file://{vol_dir}", "quota_bytes": 64 << 20})
    r = recorder(box)
    r.lease_pass(); r.heartbeat_once()
    assert r.volume == "net" and r.hold == "net"
    _recording(box, rec_con, rec_ctl, r)
    r.actuator.feed("1", box.wall() - 30, box.wall())
    r.leave_volume("test: hand it over")
    assert r.store is None and r.hold is None
    other = recorder(box, "r-2", "srv-2")
    other.lease_pass()
    assert other.volume == "net" and not other.store.reattached         # a clean mount: the writer was closed
    assert other.our_coverage("1") == [(box.wall() - 30, box.wall())]   # and what it held is readable


def test_the_archive_door_hands_out_timelines_and_frames():
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    r.actuator.feed("1", t - 100, t)
    r.store.seal()
    srv = r.serve_archive()
    try:
        tl = json.load(urllib.request.urlopen(f"{r.archive_url}/timeline/1?from={t - 200}&to={t}"))
        assert [(s["start"], s["end"], s["fenced"]) for s in tl["spans"]] == [(t - 100, t, False)]
        got = r.read_samples(r.archive_url, "1", t - 50, t - 10)
        assert got and got[0].key and unix_s(got[0].begin) >= t - 50 and unix_s(got[-1].end) <= t - 10 + 1
    finally:
        srv.shutdown()


def test_footage_fetched_into_a_gap_goes_into_the_backfill_stream_and_waits_to_be_seen():
    """A range from the device's card lands as OURS — our epoch, our volume — in `<recording>/e<epoch>/backfill`.
    Until its block closes the volume does not show it, and the recorder remembers it as LANDING: neither a hole
    to fetch again nor something the card did not have."""
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    r.actuator.feed("1", t - 600, t - 400)
    r.actuator.feed("1", t - 200, t)
    r.store.seal()
    out = r.fetch("1", "1", "http://holder/playback/1", t - 400, t - 200)
    assert out["groups"] > 0 and r.landing["1"] == [(t - 400, t - 200)]
    assert r.gaps("1", {"from": t - 600, "to": t}, t, planned=False) == []        # landing: not a hole
    r.store.seal()
    epoch = r.epochs["1"]
    assert {s.stream for s in r.store.spans("1")} == {f"1/e{epoch}", f"1/e{epoch}/backfill"}
    assert r.our_coverage("1") == [(t - 600, t)]
    assert r.closed == [f"1|{t - 400:.0f}|{t - 200:.0f}"]


def test_a_recorder_with_no_daemon_says_the_archive_is_away_and_keeps_its_place():
    from w2cplatform.obsd import Session
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.session = Session("/nonexistent/obsd.sock", client="nobody")
    r.lease_pass()
    assert r.store is None and r.archive_failure == "away" and "obsd is not answering" in r.archive_error
    assert r.volume == "srv-1" and r.capacity == r.full_capacity                  # away is not wrong: the place is kept


def test_a_volume_nobody_serves_is_named_on_the_timeline_and_not_drawn_as_a_hole():
    """srv-a went down with its disk: the recorder that held `disks-a` is silent, and nobody else can hold a
    disk of srv-a. The footage in it is not lost — it is there, unavailable until srv-a is back — and the
    camera's timeline says exactly that, by volume and server, beside what the live doors answered."""
    from w2cplatform.contract import Heartbeat
    from vms.console import vms_routes
    from tests.conftest import door, footage, store
    box, rec_con, rec_ctl = _site()
    con = VmsController(box.vars, box.objects, wall=box.wall)
    t = box.wall()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-a"),
                    Heartbeat("r-a", t - 600, [], {"server": "srv-a", "volume": "disks-a"}).to_bytes())   # silent ten minutes
    st = store("disks-b")
    footage(st, "1", 2, t - 300, t)
    srv = door(box, st, "r-b", "srv-b")
    try:
        routes = vms_routes(True, None, con, rec_con)
        rec_con.create({"name": "1", "cam": "1"})
        status, body = routes(None, "GET", "/timeline/1", {})
        assert status == 200 and [(s["start"], s["recorder"]) for s in body["segments"]] == [(t - 300, "r-b")]
        assert body["unavailable"] == [{"volume": "disks-a", "server": "srv-a", "recorder": "r-a", "since": t - 600}]
        assert "disks-a (on srv-a) is unavailable" in body["note"] and "not lost" in body["note"]

        box.objects.put(REC_SPEC.sub.heartbeat_key("r-a"),                 # srv-a is back, its recorder holds the disk again
                        Heartbeat("r-a", t, [], {"server": "srv-a", "volume": "disks-a"}).to_bytes())
        status, body = routes(None, "GET", "/timeline/1", {})
        assert isinstance(body, list) and len(body) == 1                   # nothing to explain: a plain list
    finally:
        srv.shutdown()


def test_a_recording_goes_on_into_the_volume_opened_again_after_the_engine_was_lost():
    """A remount replaces the store. A pipeline's sink asks for the recorder's CURRENT volume on every sample —
    one that kept the volume it started with would write into a closed one for as long as the pipeline ran, and
    nothing restarts a pipeline for a remount. And `WRITER_STOPPED` — the engine stopped this writer — is a
    remount too, not a refusal to skip past for ever."""
    from w2cplatform.obsd import ObsdError
    from vms.recworker import RecSink
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    assert r.actuator.feed("1", t - 120, t - 60) == {"OK": 60}
    first = r.store
    r._lost_engine(); r.lease_pass()                                   # the next pass remounts
    assert r.store is not first and first.writer is None
    assert r.actuator.feed("1", t - 60, t) == {"OK": 60}               # the same pipeline, into the new writer
    r.store.seal()
    assert r.our_coverage("1") == [(t - 120, t)]

    stopped = RecSink(r.store, "1", 1, on_lost=r._lost_engine)
    r.engine_lost = False
    r.store.writer.put = lambda *a, **k: (_ for _ in ()).throw(ObsdError(121, "PUT_MEDIA", "writer stopped"))
    try:
        stopped.put(fake_samples(t, t + 1)[0])
    except ObsdError:
        pass
    assert r.engine_lost                                               # a new writer on the next pass

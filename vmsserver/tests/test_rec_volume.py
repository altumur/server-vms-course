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
    assert r.volume == "srv-1" and r.store.formatted and r.store.url == f"file://{box.root}/volume"
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


def test_a_fetched_range_lands_under_its_lease_into_the_volume_it_was_fetched_for_and_landing_is_what_landed():
    """The review's second pass. A fetch takes minutes; `_land` used to write into whatever volume was open when it
    ended, under epoch 0 when the lease had gone, and to remember the whole DELIVERED range as landing — the groups
    the engine refused or that began without a key frame included, so they were never asked for again."""
    import dataclasses
    from w2cplatform.obsd import FLAG_NEED_KEY_FRAME
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    r.actuator.feed("1", t - 600, t - 400)
    r.store.seal()
    # the first group's key frame is not one: that group opens on nothing and stays a hole; the rest lands
    samples = fake_samples(t - 400, t - 300, gop=10.0)
    samples[0] = dataclasses.replace(samples[0], flags=samples[0].flags | FLAG_NEED_KEY_FRAME)
    out = r._land("1", "1", samples, t - 400, t - 300, "device")
    assert out["groups"] == 9 and r.landing["1"] == [(t - 390, t - 300)]
    assert r.nowhere == {}                                                      # the source DID deliver it: not "nowhere"
    r.store.seal()                                                              # …a hole, asked again once what landed is visible
    assert r.gaps("1", {"from": t - 600, "to": t - 300}, t + r.settle, planned=False) == [(t - 400, t - 390)]   # (past `settle`, which bounds a gap above)
    # a fetch that began on another volume lands nowhere; nor does one whose lease is gone
    before = r.backfilled
    out = r._land("1", "1", fake_samples(t - 300, t - 200), t - 300, t - 200, "device", store=object())
    assert out["skipped"] and r.backfilled == before and r.landing["1"] == []      # (what landed is visible now: nothing pending)
    r.release("1")
    out = r._land("1", "1", fake_samples(t - 300, t - 200), t - 300, t - 200, "device")
    assert out["skipped"] and r.backfilled == before


# -- the review's third pass: the archive on obsd ------------------------------------------------------------------

def test_a_daemon_restarted_between_two_samples_is_a_remount_and_the_recording_goes_on():
    """Blocker 4. A restarted daemon is a new, empty session under the old token: the client reconnected in silence,
    every handle answered `UNKNOWN_HANDLE`, the recorder took it for a passing outage and wrote into dead handles
    until somebody restarted IT. Any `UNKNOWN_HANDLE` is the engine lost now: the next pass mounts the volume again,
    the same pipeline goes on into the new writer, and the heartbeat says what happened — while it lasts, and after."""
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=5))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        assert r.actuator.feed("1", t - 120, t - 60) == {"OK": 60}
        d.restart(kill=False)                                          # SIGTERM: every writer closed cleanly; back empty
        said = r.actuator.feed("1", t - 60, t - 30)
        assert said == {"SESSION_LOST": 30}                            # nothing "taken" by a writer that is not there
        hb = r.heartbeat_extra()
        assert r.engine_lost and "no longer knows this recorder's session" in hb["archive_error"]
        r.lease_pass()                                                 # the next pass mounts the volume again
        hb = r.heartbeat_extra()
        assert r.store is not None and hb["archive_error"] == "" and hb["archive_remounts"] == 1
        assert "no longer knows" in hb["archive_remounted"]["why"]
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}           # the same pipeline, into the new writer
        r.store.seal()
        assert r.our_coverage("1") == [(t - 120, t - 60), (t - 30, t)]
    finally:
        d.stop()


def test_a_daemon_that_crashed_is_a_remount_once_its_lock_is_stale():
    """The same, by SIGKILL: no writer was closed, and the volume's lock is the dead daemon's until it is stale
    (`lockRefreshSec`). The remount is `busy` until then — kept, said — and then the recording goes on."""
    import time as _time
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=5), env={"ARCHIVE_LOCK_REFRESH_S": "1"})
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        r.actuator.feed("1", t - 120, t - 60)
        d.restart(kill=True)
        assert r.actuator.feed("1", t - 60, t - 50) == {"SESSION_LOST": 10}
        deadline = _time.monotonic() + 10
        while True:
            r.lease_pass()
            if r.store is not None or _time.monotonic() > deadline:
                break
            assert r.archive_failure in ("busy", "away") and r.volume == "srv-1"     # kept while the lock is stale
            _time.sleep(0.5)
        assert r.store is not None and r.remounts == 1
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}
        r.store.seal()
        assert r.our_coverage("1")[-1] == (t - 30, t)
    finally:
        d.stop()


def test_an_engine_gone_at_the_finish_of_a_fetched_range_does_not_take_the_pass_with_it():
    """The review's fourth pass, a minor. The finish after a fetched range's last group, and a keep's copy's, stood
    outside the `try`: the engine gone between the last sample and the finish raised out of `_land` — every request
    of the pass with it, and what had landed not counted. It is the engine lost now, said, and what landed counts."""
    from w2cplatform.obsd import Unavailable
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()

    def gone(*a, **k):
        raise Unavailable("FINISH_MEDIA", "obsd closed the connection")
    r.store.finish = gone
    out = r._land("1", "1", fake_samples(t - 400, t - 300, gop=10.0), t - 400, t - 300, "device")
    assert out["groups"] == 10 and r.backfilled == 10 and r.engine_lost
    r.engine_lost = False
    assert r._copy_in("1", fake_samples(t - 300, t - 200, gop=10.0)) is True and r.engine_lost


def test_a_refused_group_ends_its_sequence_and_a_lost_sequence_is_not_landed():
    """The review's fourth pass, an open item. A group the engine refused left the sequence before it open, and the
    next group went on in it: the index drew the refused stretch as footage — no hole on the timeline, nothing to
    fetch again — in a fetched range and in a keep's copy alike. And a sequence the engine took and then LOST (the
    next put answers `SEQUENCE_LOST`) was counted as landed, so it was never asked for again either."""
    import dataclasses
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall() - 3600

    def with_a_bad_group(a, b, bad):
        """Frames of `[a, b)`, the ten seconds from `bad` one group whose key frame is larger than a block."""
        out = fake_samples(a, bad) + fake_samples(bad, bad + 10, gop=100.0) + fake_samples(bad + 10, b)
        i = next(i for i, s in enumerate(out) if unix_s(s.begin) == bad)
        out[i] = dataclasses.replace(out[i], body=out[i].body + b"\x80" * (5 << 20))
        return out
    out = r._land("1", "1", with_a_bad_group(t, t + 100, t + 40), t, t + 100, "device")
    assert out["groups"] == 45 and r.landing["1"] == [(t, t + 40), (t + 50, t + 100)]
    assert r._copy_in("1", with_a_bad_group(t + 200, t + 300, t + 240)) is True
    r.store.seal()
    assert r.our_coverage("1") == [(t, t + 40), (t + 50, t + 100), (t + 200, t + 240), (t + 250, t + 300)]

    # the engine answers the first put of the third sequence `SEQUENCE_LOST`: the second one is a hole again
    real = r.store.put

    def put(unit, epoch, smp, backfill=False):
        st = real(unit, epoch, smp, backfill)                                   # taken…
        return "SEQUENCE_LOST" if unix_s(smp.begin) == t + 1060 else st          # …and an earlier sequence said lost
    r.store.put = put
    samples = fake_samples(t + 1000, t + 1010) + fake_samples(t + 1030, t + 1040) + fake_samples(t + 1060, t + 1070)
    out = r._land("1", "1", samples, t + 1000, t + 1070, "device")
    assert out["groups"] == 10 and (t + 1030, t + 1040) not in r.landing["1"]
    assert {(a, b) for _, a, b in r.refusals.values()} >= {(t + 1030 + 2 * i, t + 1032 + 2 * i) for i in range(5)}   # its groups, counted


def test_a_daemon_that_froze_between_two_samples_is_a_remount_and_the_recording_goes_on():
    """The review's fourth pass, blocker 1. Frozen, not restarted: SIGSTOP longer than a call's timeout. The write
    connection answered `Unavailable` at once for its silent window, the remount's `WRITER_CLOSE` was refused in it
    before it reached the daemon, the store forgot the handle — and the writer lived on in the session the readers and
    the pass kept alive: every mount after it `ALREADY_LOCKED`, the volume not written until somebody restarted the
    recorder. A writer whose close did not happen is left to the daemon now, in a session abandoned: detached after the
    linger, picked up by the next mount under the same owner — and the same pipeline goes on into it."""
    import os
    import signal
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=1))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        assert r.actuator.feed("1", t - 120, t - 60) == {"OK": 60}
        r.store.status()                                               # the readers' connection is up too
        first = r.session
        os.kill(d.proc.pid, signal.SIGSTOP)
        try:
            said = r.actuator.feed("1", t - 60, t - 50)                # the first waits its second; the rest fail at once
        finally:
            os.kill(d.proc.pid, signal.SIGCONT)
        assert said == {"UNAVAILABLE": 10}
        assert r.engine_lost and r.heartbeat_extra()["archive_error"] == "obsd stopped answering"
        r.lease_pass()                                                 # the remount, inside the write connection's window
        assert first.abandoned and r.session is not first              # the writer's close was refused: left behind
        deadline = time.monotonic() + 10
        while r.store is None and time.monotonic() < deadline:        # busy while the old session lingers
            assert r.archive_failure in ("busy", "away") and r.volume == "srv-1"
            time.sleep(OBSD_LINGER_MS / 1000)
            r.lease_pass()
        assert r.store is not None and r.store.reattached and r.remounts == 1   # the writer the old session left
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}           # the same pipeline, into it
        r.store.seal()
        assert r.our_coverage("1") == [(t - 120, t - 59), (t - 30, t)]    # the sample out before the freeze landed after it
    finally:
        d.stop()


def test_a_close_that_waits_on_the_leases_thread_waits_one_call_and_not_thirty_seconds():
    """The review's fourth pass, Т-M1. `WRITER_CLOSE` may take thirty seconds to flush, and a remount or a volume let
    go closes the writer on the thread that renews the leases — twenty-five seconds a lease leaves. That thread waits
    one call's timeout now; a close that did not come back in it leaves the session to the daemon, as a silence does."""
    import os
    import signal
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=1, long_timeout=30))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        first = r.session
        os.kill(d.proc.pid, signal.SIGSTOP)
        t0 = time.monotonic()
        try:
            r._lost_engine()
            r._close_store(quiet=True, wait=r.session.timeout)         # what `_write_into` and `leave_volume` do
        finally:
            os.kill(d.proc.pid, signal.SIGCONT)
        assert time.monotonic() - t0 < 5 and r.store is None and first.abandoned
    finally:
        d.stop()


def test_a_sample_that_races_its_writers_own_close_is_not_the_engine_lost():
    """The review's fourth pass, a minor. A handle this client closed answers `UNKNOWN_HANDLE` like a handle the
    daemon lost, and was counted as one: `SESSION_LOST`, a remount, an outage in the heartbeat for a close of our own.
    The client remembers what it closed: that answer is `Closed`, and the session is not lost."""
    from w2cplatform.obsd import Closed, SessionLost
    from tests.conftest import store
    st = store()
    w = st.writer
    st.seal()                                                          # the writer closed and taken again
    smp = fake_samples(Box().wall() - 10, Box().wall())[0]
    try:
        w.put("1/e1", smp)                                             # the old handle, after its own close
        raise AssertionError("a closed writer took a sample")
    except SessionLost:
        raise AssertionError("our own close was taken for the engine lost")
    except Closed as e:
        assert e.name == "CLOSED"
    assert st.session.lost == 0 and not st.lost


def test_readers_do_not_close_each_other_in_the_middle_of_a_read():
    """Blocker 5. One reader was shared: every question closed it and mounted another, so the door, the backfill,
    the keeps and the pass — reading at once — closed each other's reader mid-read. A reader is the question's own
    now, closed when the question is answered."""
    import threading
    from tests.conftest import footage, store
    st = store()
    t = Box().wall()
    footage(st, "7", 1, t - 1800, t, step=1)
    want = len(st.samples("7", t - 1800, t))
    errors, counts = [], []

    def read():
        try:
            for _ in range(3):
                counts.append(len(st.samples("7", t - 1800, t)))
        except Exception as e:                                         # noqa: BLE001
            errors.append(e)

    def status():
        try:
            for _ in range(40):
                st.status(); st.units()
        except Exception as e:                                         # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=read) for _ in range(3)] + [threading.Thread(target=status) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(60)
    assert errors == [] and counts == [want] * 9


def test_a_long_range_is_fetched_from_a_backup_a_minute_at_a_time_and_lands_whole():
    """Blocker 6. A range was one request and one list — a day from a backup, tens of gigabytes in two recorders'
    memory. It is asked for about a minute at a time and landed before the next minute is asked for, cut at key
    frames so that nothing is fetched twice and nothing is left between two pieces."""
    from w2cplatform.obsd import unix_s
    from tests.conftest import door, footage, store
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    backup = store("backup")
    footage(backup, "1-backup", 1, t - 1800, t - 600, step=0.5)
    srv = door(box, backup, "r-backup", "srv-2")
    asked, real = [], r.read_samples

    def read(url, unit, a, b):
        got = real(url, unit, a, b)
        asked.append((a, b, len(got)))
        return got
    r.read_samples = read
    try:
        out = r.fetch_from("1", "1", {"kind": "backup", "key": "backup:1-backup", "url": srv.url, "recording": "1-backup"},
                           t - 1800, t - 600)
    finally:
        srv.shutdown()
    assert len(asked) >= 20 and all(b - a <= r.PIECE for a, b, _ in asked)       # twenty minutes, a minute at a time
    assert all(n <= 2 * (r.PIECE + 2) for _, _, n in asked)                       # …never more than a piece in hand
    assert out["groups"] > 0 and r.closed == [f"1|{t - 1800:.0f}|{t - 600:.0f}"]  # reported once, whole
    r.store.seal()
    landed = r.store.samples("1", t - 1800, t - 600)
    assert r.our_coverage("1") == [(t - 1800, t - 600)]                            # nothing between two pieces
    assert len(landed) == len({s.begin for s in landed}) == 2400                  # and nothing twice
    assert unix_s(landed[0].begin) == t - 1800


# -- the review's fifth pass: the volume's writer ------------------------------------------------------------------

def _two_boxes_over_one_network_volume():
    """Two daemons — two hosts — and a network volume both may serve, in one directory. Recorder A on daemon A holds
    it and records camera 1; recorder B on daemon B is a spare. The volume's engine lock goes stale after 2 s."""
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    da, db = ObsdDaemon.fresh(), ObsdDaemon.fresh()
    box, rec_con, rec_ctl = _site()
    volumes.write(box.vars, {"name": "net", "kind": "network", "url": f"file://{box.archive}-net", "quota_bytes": 64 << 20})
    env = {"ARCHIVE_LOCK_REFRESH_S": "2"}
    a = recorder(box, "r-1", "srv-1", obsd=Session(da.socket, client="rec-r-1", timeout=1), env=dict(env))
    a.lease_pass(); a.heartbeat_once()
    assert a.hold == "net"
    _recording(box, rec_con, rec_ctl, a)
    b = recorder(box, "r-2", "srv-2", obsd=Session(db.socket, client="rec-r-2", timeout=1), env=dict(env))
    b.lease_pass()
    assert b.hold is None                                              # a spare while A holds it
    return box, da, db, a, b


def _freeze_a_and_let_b_take_the_volume(box, da, a, b):
    """Box A frozen whole — its daemon stopped, its recorder running no pass — past the hold's term; B takes the hold,
    waits out the engine lock A's frozen daemon no longer refreshes, and mounts the volume."""
    import os
    import signal
    os.kill(da.proc.pid, signal.SIGSTOP)
    box.clock.advance(b.slot_ttl + b.HOLD_SKEW + 1); box.wall.advance(b.slot_ttl + b.HOLD_SKEW + 1)
    time.sleep(3)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        b.lease_pass()
        if b.store is not None and b.store.writer is not None:
            return
        time.sleep(0.5)
    raise AssertionError(f"B did not mount the volume: {b.archive_failure} {b.archive_error}")


def test_a_box_frozen_whole_writes_nothing_into_the_network_volume_another_box_took_and_closes_nothing_there():
    """The review's fifth pass, blocker 1, on two live daemons over one `kind: network` directory. The hold was checked
    before `VOLUME_MOUNT_RW` and never again: box A frozen whole woke with its writer mounted, its pipeline put thirty
    frames beside B's — all `OK` — and its pass closed the writer, the close's flush and its lock's release landing on
    B's volume: `VOLUME_UNCLEAN` at B's every mount after, and nothing called `VOLUME_RECOVER`.

    Now every sample into a network volume is fenced by the age of the hold's confirmation, and nothing of A's goes
    in. A's writer is not closed: a daemon with the engine's patch 07 abandons it — writing nothing — and one without
    leaves it parked, mounted and fed nothing. And B, holding the volume, recovers it if the woken engine left it
    unclean (an engine without patch 07 flushes its queue by its own timer when it wakes) — an alarm, not `away`."""
    import os
    import signal
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.obsd import Session
    from tests.conftest import footage
    from tests.test_lock_lost import _abandons
    box, da, db, a, b = _two_boxes_over_one_network_volume()
    p7 = _abandons(da.socket)
    try:
        t = box.wall()
        assert a.actuator.feed("1", t - 60, t - 30) == {"OK": 30}
        try:
            _freeze_a_and_let_b_take_the_volume(box, da, a, b)
            tb = box.wall()
            footage(b.store, "9", 1, tb - 20, tb, seal=False)              # B records into the volume it holds
        finally:
            os.kill(da.proc.pid, signal.SIGCONT)
        said = a.actuator.feed("1", t - 30, t)                         # A's pipeline, before A's pass has run
        assert said == {"FENCED": 30}, said                            # nothing of it sent into B's volume
        assert not a.engine_lost                                       # and not taken for the engine lost: no remount
        a.lease_pass()                                                 # A's pass: the hold is B's
        assert a.hold is None and a.store is None
        writers = [w for w in Session(da.socket, client="peek").stats()["writers"] if w["owner"] == "rec:net"]
        if p7:
            assert a.parked == {} and writers == []                    # abandoned, writing nothing
        else:
            assert list(a.parked) == ["net"] and a.heartbeat_extra()["archive_parked"] == ["net"]
            assert [w["state"] for w in writers] == ["attached"]       # not closed: its flush is not B's to receive
        time.sleep(7)                                                  # the woken engine's own flush timer, if it has one
        b.store.seal()                                                 # B closes its writer and mounts it again
        assert b.store.writer is not None
        for _ in range(3):
            b.lease_pass()
            assert b.store is not None and b.archive_failure == "", b.archive_error
        recovered = [e for e in EventIndex(box.archive, "srv-2", wall=box.wall).query(0, box.wall() + 1,
                                                                                       subsystem="rec")["events"]
                     if e["kind"] == "archive.volume.recovered"]
        assert all(e["class"] == "alarm" and e["volume"] == "net" and e["result"] == "recovered" for e in recovered)
        if p7:
            assert recovered == [] and b.store.coverage("9") == [(tb - 20, tb)]   # nothing of A's touched B's
    finally:
        da.stop(); db.stop()


def test_every_sample_into_a_network_volume_needs_a_hold_confirmed_within_its_write_window():
    """The fence itself, on one daemon (the review's fifth pass, blocker 1). Past `slot_ttl − lease_margin` without a
    confirmation nothing is sent — and the sink does not take that for the engine lost; confirmed again by the pass,
    the same pipeline writes on. A disk of this server is never fenced: nobody else can write there."""
    box, rec_con, rec_ctl = _site()
    volumes.write(box.vars, {"name": "net", "kind": "network", "url": f"file://{box.archive}-net", "quota_bytes": 64 << 20})
    r = recorder(box)
    r.lease_pass(); r.heartbeat_once()
    assert r.hold == "net"
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    assert r.actuator.feed("1", t - 60, t - 50) == {"OK": 10}
    for _ in range(4):                                                 # the leases renewed, the hold not: a pass stuck
        box.clock.advance((r.slot_ttl - r.lease_margin) / 4); box.wall.advance((r.slot_ttl - r.lease_margin) / 4)
        r.renew_leases()
    assert r.actuator.feed("1", t - 50, t - 40) == {"FENCED": 10}       # the hold's write window has run out
    assert not r.engine_lost and r.samples_lost["1"] == {"FENCED": 10}
    r.lease_pass()                                                     # confirmed again: nobody took it meanwhile
    assert r.hold == "net" and r.actuator.feed("1", t - 40, t - 30) == {"OK": 10}

    own = recorder(Box(), "r-1", "srv-1")                              # nothing declared: the box's own disk
    own.lease_pass()
    own.clock.advance(3600)
    assert own._may_write_volume(own._vol_last)


def test_an_unclean_volume_is_recovered_only_under_a_hold_confirmed_this_second():
    """The review's fifth pass, blocker 1 and its second question. `VOLUME_UNCLEAN` is recovered by the recorder that
    holds the volume — the hold confirmed once more right before `VOLUME_RECOVER`; refused then, nothing is recovered.
    And an `Archive` nobody told to recover (no `on_unclean`) refuses as it always did."""
    from w2cplatform.obsd import CODE, ObsdError
    from vms.archive import Archive, ArchiveError

    class Volume:
        def __init__(self):
            self.recovered = 0

        def mount_rw(self, owner):
            if not self.recovered:
                raise ObsdError(CODE["VOLUME_UNCLEAN"], "VOLUME_MOUNT_RW", "volume was not unmounted properly")
            return "writer"

        def recover(self):
            self.recovered += 1
            return 1

    def confirms(*answers):
        it = iter(answers)

        def confirm():
            e = next(it)
            if e is not None:
                raise e
        return confirm

    said, vol = [], Volume()
    taken = ArchiveError("wrong", "net is held by another recorder now: not mounted", "HOLD_LOST")
    st = Archive("file:///net", "net", confirm=confirms(None, taken), on_unclean=lambda r, d: said.append(r))
    try:
        st._mount_rw(vol)
        raise AssertionError("mounted without the hold")
    except ArchiveError as e:
        assert e.name == "HOLD_LOST" and vol.recovered == 0 and said == []
    st = Archive("file:///net", "net", confirm=confirms(None, None), on_unclean=lambda r, d: said.append(r))
    assert st._mount_rw(vol) == "writer" and vol.recovered == 1 and said == [1]
    vol.recovered = 0
    try:
        Archive("file:///net", "net")._mount_rw(vol)
        raise AssertionError("an archive nobody told to recover recovered")
    except ObsdError as e:
        assert e.name == "VOLUME_UNCLEAN" and vol.recovered == 0


def test_a_mount_whose_answer_was_lost_leaves_its_session_and_the_next_one_picks_the_writer_up():
    """The review's fifth pass, blocker 2. The daemon frozen right at `VOLUME_MOUNT_RW`: the client's wait ran out, the
    mount — not sent twice — was `away`, and the writer the daemon made when it woke stayed ATTACHED to the recorder's
    session, which its readers kept alive: every mount after it `ALREADY_LOCKED`, the volume busy until the recorder
    was restarted. A mount that went out and did not come back leaves its session behind now, and a successor under
    the same owner gets that writer back."""
    import os
    import signal
    import threading
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=1))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        assert r.actuator.feed("1", t - 120, t - 60) == {"OK": 60}
        first = r.session
        real = first.call

        def call(op, *a, **kw):                                        # the daemon stops the moment the mount goes out
            if op == "VOLUME_MOUNT_RW":
                first.call = real
                os.kill(d.proc.pid, signal.SIGSTOP)
                threading.Timer(1.5, lambda: os.kill(d.proc.pid, signal.SIGCONT)).start()
            return real(op, *a, **kw)
        first.call = call
        r._lost_engine()                                               # a remount: the writer closed, the volume opened again
        r.lease_pass()
        assert r.store is None and r.archive_failure == "away"
        assert first.abandoned and r.session is not first              # the mount's writer is an orphan: session left
        time.sleep(1)                                                  # the daemon wakes and makes the writer
        deadline = time.monotonic() + 10
        while r.store is None and time.monotonic() < deadline:
            time.sleep(OBSD_LINGER_MS / 1000)
            r.lease_pass()
            assert r.archive_failure != "busy" or "ALREADY_LOCKED" in r.archive_error
        assert r.store is not None and r.store.reattached              # the writer the frozen mount made, picked up
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}
        r.store.seal()
        assert r.our_coverage("1") == [(t - 120, t - 60), (t - 30, t)]
    finally:
        d.stop()


def test_a_volume_locked_by_our_own_owner_longer_than_a_linger_is_an_orphan_of_this_session():
    """The review's fifth pass, blocker 2, its other half. Whatever lost the handle — `ALREADY_LOCKED` naming this
    recorder's own owner, `rec:<volume>`, attached to a session that stays, is a writer of this session nobody here
    holds. Not at once (a predecessor may be closing its writer this moment); after `OWN_LOCK_FOR` the session is left
    behind, and the writer comes back to the next mount."""
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    _recording(box, rec_con, rec_ctl, r)
    t = box.wall()
    assert r.actuator.feed("1", t - 60, t - 30) == {"OK": 30}
    first = r.session
    r.store.writer = None                                              # the handle forgotten: an orphan, made by hand
    r.lease_pass()
    assert r.store is None and r.archive_failure == "busy" and "(rec:srv-1)" in r.archive_error
    assert r.session is first                                          # not at once
    box.clock.advance(r.OWN_LOCK_FOR); box.wall.advance(r.OWN_LOCK_FOR)
    r.lease_pass()
    assert first.abandoned and r.session is not first
    deadline = time.monotonic() + 10
    while r.store is None and time.monotonic() < deadline:
        time.sleep(OBSD_LINGER_MS / 1000)
        r.lease_pass()
    assert r.store is not None and r.store.reattached
    assert r.actuator.feed("1", t - 30, t) == {"OK": 30}


def test_a_remount_on_a_frozen_daemon_costs_the_pass_one_call_and_not_three():
    """The review's fifth pass, Т-M1. After the writer's close did not come back, the remount still sent `VOLUME_CLOSE`
    and then `VOLUME_OPEN` on the thread that renews the leases: `close(1.0)` took two seconds and the open one more —
    in production some thirty seconds against a lease's twenty-five. The volume's close goes with the session now,
    and the volume is mounted again on the next pass."""
    import os
    import signal
    from w2cplatform.obsd import Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=1, long_timeout=30))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        first = r.session
        os.kill(d.proc.pid, signal.SIGSTOP)
        try:
            r._lost_engine()
            t0 = time.monotonic()
            r.lease_pass()
            took = time.monotonic() - t0
        finally:
            os.kill(d.proc.pid, signal.SIGCONT)
        assert took < 1.8, took                                        # one call's wait, the close's
        assert first.abandoned and r.store is None and r.archive_failure == "away"
        deadline = time.monotonic() + 10
        while r.store is None and time.monotonic() < deadline:
            time.sleep(OBSD_LINGER_MS / 1000)
            r.lease_pass()
        assert r.store is not None
    finally:
        d.stop()


def test_after_a_second_restart_of_the_daemon_a_lost_session_is_not_taken_for_a_closed_handle():
    """The review's fifth pass, a major. A restarted daemon numbers its handles from the start again, and the client's
    list of the handles it closed outlived the session: after the second restart the new volume handle — the same
    number as the first session's, closed at the first remount — answered `UNKNOWN_HANDLE` as `Closed`, `lost` stayed
    False, and the volume was never mounted again. The list is the session's now, emptied when the session is lost."""
    from w2cplatform.obsd import Session
    from vms.archive import ArchiveError
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=5))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        assert r.actuator.feed("1", t - 120, t - 90) == {"OK": 30}
        for n in (1, 2):
            d.restart(kill=False)
            try:
                r.store.coverage("1")
                raise AssertionError("a volume handle of a restarted daemon answered")
            except ArchiveError as e:
                assert e.name == "SESSION_LOST", (n, e.name)
            assert r.store.lost
            r.lease_pass()
            assert r.store is not None and not r.store.lost and r.remounts == n
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}
    finally:
        d.stop()


def test_a_seal_that_did_not_come_back_leaves_no_dead_writer_and_the_next_pass_mounts_again():
    """The review's fifth pass, a major. `seal()` — a keep's copy made readable — timed out on a frozen daemon and
    kept the handle it had just closed: every sample after it `Closed`, `lost` False, the volume taking nothing until a
    restart. The writer is forgotten before its close goes out now; a close that did not come back is an orphan — the
    session is left behind on the next pass — and the volume is mounted again."""
    import os
    import signal
    from w2cplatform.obsd import ObsdError, Session
    from tests.conftest import ObsdDaemon
    d = ObsdDaemon.fresh()
    try:
        box, rec_con, rec_ctl = _site()
        r = recorder(box, obsd=Session(d.socket, client="rec-r-1", timeout=1, long_timeout=1))
        r.heartbeat_once()
        _recording(box, rec_con, rec_ctl, r)
        t = box.wall()
        assert r.actuator.feed("1", t - 120, t - 60) == {"OK": 60}
        first = r.session
        os.kill(d.proc.pid, signal.SIGSTOP)
        try:
            try:
                r.store.seal()
                raise AssertionError("a seal on a frozen daemon came back")
            except ObsdError as e:
                assert e.name == "UNAVAILABLE"
        finally:
            os.kill(d.proc.pid, signal.SIGCONT)
        assert r.store.writer is None and r.store.orphan
        assert r.actuator.feed("1", t - 60, t - 50) == {"UNAVAILABLE": 10}     # not `CLOSED`: no writer, said
        assert r.engine_lost
        r.lease_pass()
        assert first.abandoned and r.session is not first
        deadline = time.monotonic() + 10
        while r.store is None and time.monotonic() < deadline:
            time.sleep(OBSD_LINGER_MS / 1000)
            r.lease_pass()
        assert r.store is not None and r.store.writer is not None
        assert r.actuator.feed("1", t - 30, t) == {"OK": 30}
    finally:
        d.stop()

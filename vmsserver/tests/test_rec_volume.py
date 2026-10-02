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

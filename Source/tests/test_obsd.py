"""What the archive's engine IS — against a live `obsd`, not a picture of one.

Every rule the recorder follows later comes from one of these: a reader sees only closed blocks, a sequence
opens on a key frame, a group of pictures longer than a block is cut, the volume is a ring that gives up its
oldest minutes first, a volume has one writer on a host, and a writer whose process vanished waits for its
owner before anybody else may have the volume."""
import os
import time

from vms.obsd import EPOCH_OFFSET_MS, ObsdError, archive_ms, unix_s, video
from tests.vmsconftest import OBSD_GRACE_S, OBSD_LINGER_MS, obsd_session, obsd_volume

T0 = archive_ms(1_757_500_000)
FRAME = 40                                                # ms: 25 frames a second


def _frames(writer, stream, n, start=0, gop=25, key_bytes=20_000, p_bytes=3_000):
    """`n` frames from frame number `start`: a key frame every `gop`. Returns {status: count}."""
    said = {}
    for i in range(start, start + n):
        key = i % gop == 0
        try:
            st = writer.put(stream, video(T0 + i * FRAME, T0 + (i + 1) * FRAME, os.urandom(key_bytes if key else p_bytes), key))
        except ObsdError as e:
            st = e.name
        said[st] = said.get(st, 0) + 1
    return said


def _spans(reader, stream):
    return [((x["start"] - T0) // 1000, (x["end"] - T0) // 1000) for x in reader.timeline(stream, T0 - 1, T0 + 10 ** 9)]


def test_the_archives_clock_starts_in_1900():
    assert archive_ms(0) == EPOCH_OFFSET_MS and unix_s(archive_ms(1_757_500_000.5)) == 1_757_500_000.5


def test_what_is_written_is_read_back_by_stream_and_time():
    s = obsd_session()
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:t1")
    assert _frames(w, "7/e1", 250) == {"OK": 250}
    w.close()
    r = vol.mount_ro()
    assert r.streams() == ["7/e1"]
    assert _spans(r, "7/e1") == [(0, 6), (6, 10)]                          # sequences cut by the read size, on key frames
    first = r.sequences("7/e1", T0 - 1, T0 + 10 ** 9)[0]
    got = r.read(first)
    assert len(got) == 150 and got[0].key and got[0].begin == T0 and got[-1].end == T0 + 150 * FRAME
    s.bye()


def test_a_reader_sees_only_closed_blocks_and_only_what_was_there_when_it_mounted():
    """The rule half the recorder's logic follows from: written is not visible. A flush puts the tail on the
    medium and does not close the block; a reader mounted before the writer closed keeps its own picture."""
    s = obsd_session()
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:t2")
    _frames(w, "7/e1", 250)
    early = vol.mount_ro()
    assert early.streams() == [] and _spans(early, "7/e1") == []
    w.flush()
    assert _spans(vol.mount_ro(), "7/e1") == []                             # flushed is not closed
    w.close()
    assert _spans(vol.mount_ro(), "7/e1") == [(0, 6), (6, 10)]             # closed: visible to a reader mounted now
    assert _spans(early, "7/e1") == []                                      # …and not to the one mounted before
    s.bye()


def test_a_sequence_opens_on_a_key_frame():
    s = obsd_session()
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:t3")
    try:
        w.put("7/e1", video(T0, T0 + FRAME, b"x" * 100, key=False))
        raise AssertionError("a sequence that does not open on a key frame")
    except ObsdError as e:
        assert e.name == "SEQUENCE_NEEDS_KEY_SAMPLE"
    s.bye()


def test_a_group_of_pictures_longer_than_a_block_is_cut_and_the_rest_waits_for_a_key():
    """One key frame and then six megabytes of the rest, into four-megabyte blocks: the sequence is closed where
    the block is full, and every frame after it is refused until a key frame opens a new one — lost, not queued."""
    s = obsd_session()
    vol, _ = obsd_volume(s, max_block=4 << 20)
    w = vol.mount_rw("rec:t4")
    said = _frames(w, "7/e1", 2100, gop=10 ** 6)
    assert said["OK"] < 2100 and said["SEQUENCE_NEEDS_KEY_SAMPLE"] == 2100 - said["OK"]
    s.bye()


def test_the_volume_is_a_ring_and_its_oldest_minutes_go_first():
    """Sixteen megabytes, four blocks, twenty-two megabytes written: nobody deleted anything, and the first
    minutes are gone — the ring overwrote its oldest blocks. What the archive keeps is decided by its size."""
    s = obsd_session()
    vol, _ = obsd_volume(s, size=16 << 20, max_block=4 << 20)
    w = vol.mount_rw("rec:t5")
    assert _frames(w, "7/e1", 6000) == {"OK": 6000}
    w.close()
    r = vol.mount_ro()
    st = r.status()
    assert st["totalWritten"] > 16 << 20 and st["firstBlockId"] > 0 and st["numBlocks"] == 4
    assert _spans(r, "7/e1")[0][0] > 0                                       # the first seconds are not there any more
    s.bye()


def test_one_writer_per_volume_and_a_vanished_one_waits_for_its_owner():
    """A recorder killed mid-write: its session vanishes without BYE. The daemon closes the open sequences and
    keeps the writer DETACHED for the grace. Anybody else is refused; the same owner — the recorder started again,
    `rec:<volume>` — gets the very writer back: no lock waited out, nothing recovered, no seam in the footage."""
    a = obsd_session("recorder")
    vol, path = obsd_volume(a)
    w = vol.mount_rw("rec:vol1")
    _frames(w, "7/e1", 50)
    other = obsd_session("other").open_volume(params={"schema": "file", "path": path})
    try:
        other.mount_rw("rec:other")
        raise AssertionError("two writers on one volume")
    except ObsdError as e:
        assert e.name == "ALREADY_LOCKED"
    a.vanish()
    time.sleep(OBSD_LINGER_MS / 1000 + 0.5)
    try:
        other.mount_rw("rec:other")
        raise AssertionError("somebody else took a writer waiting for its owner")
    except ObsdError as e:
        assert e.name == "ALREADY_LOCKED"
    again = obsd_session("recorder").open_volume(params={"schema": "file", "path": path}).mount_rw("rec:vol1")
    assert again.reattached
    _frames(again, "7/e1", 50, start=50)
    again.close()
    reader = obsd_session().open_volume(params={"schema": "file", "path": path}).mount_ro()
    assert _spans(reader, "7/e1") == [(0, 2), (2, 4)]                        # one recording, no seam


def test_after_the_grace_the_volume_is_clean_for_anybody():
    a = obsd_session("recorder")
    vol, path = obsd_volume(a)
    w = vol.mount_rw("rec:vol2")
    _frames(w, "7/e1", 50)
    a.vanish()
    time.sleep(OBSD_LINGER_MS / 1000 + OBSD_GRACE_S + 1)
    b = obsd_session("spare")
    w2 = b.open_volume(params={"schema": "file", "path": path}).mount_rw("rec:somebody-else")
    assert not w2.reattached                                                  # a clean mount: the writer was closed
    w2.close()
    assert _spans(b.open_volume(params={"schema": "file", "path": path}).mount_ro(), "7/e1") == [(0, 2)]   # nothing it took was lost


def test_two_writers_epochs_are_two_streams_in_one_volume():
    """The epoch is part of the stream's NAME — the only metadata a stream has. A fenced writer's frames and the
    survivor's are told apart by which stream they are in, not by a directory."""
    s = obsd_session()
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:t8")
    _frames(w, "7/e1", 50)
    _frames(w, "7/e2", 50, start=25)
    w.close()
    r = vol.mount_ro()
    assert sorted(r.streams()) == ["7/e1", "7/e2"]
    assert _spans(r, "7/e1") == [(0, 2)] and _spans(r, "7/e2") == [(1, 3)]  # the minutes both held: two streams, both kept
    s.bye()


def test_a_recording_a_month_deep_is_answered_whole():
    """An engine before patch 05 answered `INTERNAL_ERROR` to `READER_TIMELINE` over six days of footage or more:
    one index read per hour, all handed to a pool whose queue holds 128. A recording is a month deep, so `Archive`
    asks five days at a time, halves a window refused anyway, and puts the intervals back together
    (`Archive._timeline`) — insurance against an older daemon, and the same answer on a fixed one."""
    from tests.vmsconftest import footage, store
    now = 1_757_500_000.0
    st = store()
    footage(st, "7", 1, now - 30 * 86400, now - 15 * 86400 - 3600, step=3600, seal=False)
    footage(st, "7", 1, now - 15 * 86400, now, step=600)
    assert st.coverage("7") == [(now - 30 * 86400, now - 15 * 86400 - 3600), (now - 15 * 86400, now)]
    assert round(st.depth_days("7", now), 3) == 30.0
    assert [(s.start, s.end) for s in st.spans("7", now - 2 * 86400, now - 86400)][0][1] == now   # a window inside a span


def test_a_new_quota_resizes_the_ring_without_stopping_the_writer():
    """A quota is the size of the ring, and a new one is applied at once (`WRITER_RESIZE`): the writer goes on,
    and what was written stays readable."""
    from tests.vmsconftest import footage, store
    st = store(quota=64 << 20)
    t = 1_757_500_000.0
    footage(st, "7", 1, t - 600, t, step=10, seal=False)
    st.resize(128 << 20)
    assert st.quota == 128 << 20 and st.writer is not None
    footage(st, "7", 1, t, t + 600, step=10)
    assert st.coverage("7") == [(t - 600, t + 600)]


def test_a_write_that_went_out_before_the_connection_broke_is_not_sent_twice():
    """The daemon may have taken the sample before the connection broke; sent again it is a frame twice. So
    `PUT_MEDIA` and its kin are not resent — the caller hears `Unavailable` and decides — while a request that
    never went out (the break came on connecting) is simply tried once more."""
    import socket
    from vms.obsd import NOT_RESENT, Session, Unavailable
    from tests.vmsconftest import ObsdDaemon
    s = Session(ObsdDaemon.get().socket, client="t")
    s.call("STATS")                                               # connected
    assert "PUT_MEDIA" in NOT_RESENT and "WRITER_CLOSE" in NOT_RESENT and "STATS" not in NOT_RESENT
    sent = []

    class Breaks:                                                 # the request leaves; the answer never comes back
        def __init__(self, inner): self.inner = inner
        def sendall(self, data):
            self.inner.sendall(data); sent.append(data); self.inner.shutdown(socket.SHUT_RDWR)
        def __getattr__(self, name): return getattr(self.inner, name)
    ln = s.lane("write")                                          # a sample goes on the writer's own connection
    s._connect(ln)
    ln.sock = Breaks(ln.sock)
    try:
        s.call("PUT_MEDIA", None, b"\x00" * 10)
        raise AssertionError("resent a sample the daemon may have taken")
    except Unavailable:
        pass
    assert len(sent) == 1                                         # out once, never again
    assert s.call("STATS")[0]                                     # a fresh connection: the session goes on


def test_a_thin_stream_is_visible_after_the_flush_periods_and_not_when_its_block_fills():
    """Feedback CP. A thin stream — a few kilobytes a second against a block of megabytes — took ten minutes to
    reach a reader: the block was written only when full, because the engine's flush timer never fired (patch
    04). With the writer told its two periods, a finished sequence is on the volume after `blockFlushPeriodSec`,
    and an open one is cut by the engine `sequenceFlushPeriodMs` after it opened — without anybody closing the
    writer. Left at nought, the block waits for the engine's own minute: this test would wait with it."""
    import time
    from tests.vmsconftest import store
    from vms.worker import fake_samples
    st = store()                                                       # the course's periods: 10 s and 5 s
    st.seal()                                                          # (a fresh writer, configured)
    assert st.block_flush_s == 5 and st.sequence_flush_ms == 10_000
    quick = store("quick")
    quick.writer.configure(sequenceFlushPeriodMs=1000, blockFlushPeriodSec=1)
    t = 1_757_500_000.0
    for smp in fake_samples(t - 30, t, step=1, size=256):             # thirty seconds, eight kilobytes: no block fills
        quick.put("7", 1, smp)
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline and not quick.coverage("7"):
        time.sleep(0.25)
    seen = quick.coverage("7")
    assert seen and seen[0][0] == t - 30 and seen[0][1] >= t - 2        # the sequence the engine cut, on the volume
    assert quick.status()["numBlocks"] >= 1


def test_the_writer_the_readers_and_the_pass_each_have_a_connection_of_their_own():
    """The review's third pass. One connection behind one lock: a long read held every camera's samples, and a
    silent request held the pass that renews the leases. The writer's ops, the readers' and the rest each have a
    connection of their own now; and a connection held by a request that does not come back answers the next
    caller `Unavailable` after a timeout instead of queueing it for ever."""
    import time as _time
    from vms.obsd import Session, Unavailable
    from tests.vmsconftest import ObsdDaemon
    s = Session(ObsdDaemon.get().socket, client="t", timeout=0.5)
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:lanes")
    reads = s.lane("read")
    reads.lock.acquire()                                              # a read in flight that does not come back
    try:
        assert _frames(w, "7/e1", 50) == {"OK": 50}                   # the writer writes
        assert s.call("STATS")[0] is not None                         # the pass asks
        t0 = _time.monotonic()
        try:
            vol.mount_ro()
            raise AssertionError("a read queued behind a read that never ends")
        except Unavailable as e:
            assert "held by a request" in e.detail and _time.monotonic() - t0 < 2
    finally:
        reads.lock.release()
    assert vol.mount_ro().status() is not None                        # the connection is free again
    s.bye()


def test_a_session_past_its_linger_answers_session_lost_and_its_handles_are_gone():
    """Blocker 4, from the client's side. Every connection of a session gone longer than the linger, or the daemon
    restarted: a HELLO under the same token makes a NEW, empty session, and nothing in its reply says so. The
    old handles answer `UNKNOWN_HANDLE` — which the client raises as `SessionLost`, the engine lost: remount."""
    from vms.obsd import SessionLost, Unavailable
    s = obsd_session("lingered")
    vol, _ = obsd_volume(s)
    w = vol.mount_rw("rec:lingered")
    _frames(w, "7/e1", 25)
    s.vanish()
    time.sleep(OBSD_LINGER_MS / 1000 + 0.5)
    try:
        w.put("7/e1", video(T0 + 2000, T0 + 2040, b"x" * 100, True))
        raise AssertionError("a handle of a session that ended was taken")
    except SessionLost as e:
        assert isinstance(e, Unavailable) and e.name == "SESSION_LOST" and s.lost == 1


def test_abandoning_a_session_under_calls_in_flight_answers_them_unavailable_at_once():
    """The review's fifth pass, a minor. `abandon` closed every connection's socket and set it to None while other
    threads were in the middle of calls on them: forty races gave three `AttributeError`s — a 500 from the archive's
    door instead of a 503 — and twenty-eight calls that waited their whole timeout on a daemon that was answering. A
    connection in use is shut down now, its caller answered `Unavailable` at once; and the door says 503."""
    import random
    import threading
    from vms.obsd import Session, Unavailable
    from vms.archive import Archive
    from vms.recworker import archive_routes
    from tests.vmsconftest import ObsdDaemon
    wrong, slow = [], []
    for _ in range(40):
        s = Session(ObsdDaemon.get().socket, client="abandoned", timeout=5)
        vol, _ = obsd_volume(s)
        got = []

        def ask():
            while True:
                try:
                    vol.space()                                        # the pass's connection
                    vol.mount_ro().status()                            # the readers'
                except Exception as e:                                 # noqa: BLE001
                    got.append(e)
                    return
        th = threading.Thread(target=ask)
        th.start()
        time.sleep(random.uniform(0, 0.02))
        t0 = time.monotonic()
        s.abandon()
        th.join(10)
        took = time.monotonic() - t0
        wrong += [e for e in got if not isinstance(e, Unavailable)]
        if took > 1.0:
            slow.append(took)
    assert wrong == [] and slow == [], (wrong[:3], slow[:3])
    st = Archive("file:///anywhere", "gone", session=s)
    status, _, _ = archive_routes(lambda: st, time.time)("/spans/1?from=0&to=1")
    assert status == 503

"""What the archive's engine IS — against a live `obsd`, not a picture of one.

Every rule the recorder follows later comes from one of these: a reader sees only closed blocks, a sequence
opens on a key frame, a group of pictures longer than a block is cut, the volume is a ring that gives up its
oldest minutes first, a volume has one writer on a host, and a writer whose process vanished waits for its
owner before anybody else may have the volume."""
import os
import time

from w2cplatform.obsd import EPOCH_OFFSET_MS, ObsdError, archive_ms, unix_s, video
from tests.conftest import OBSD_GRACE_S, OBSD_LINGER_MS, obsd_session, obsd_volume

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


def test_a_timeline_over_six_days_is_refused_so_the_archive_asks_in_windows():
    """Seen, and not in the protocol's README: `READER_TIMELINE` over six days of footage or more answers
    `INTERNAL_ERROR`. A recording is a month deep, so `Archive` asks five days at a time and puts the intervals
    back together (`Archive._timeline`). If this test starts failing, the engine has stopped refusing — and the
    windows can go."""
    from tests.conftest import footage, store
    now = 1_757_500_000.0
    st = store()
    footage(st, "7", 1, now - 9 * 86400, now, step=3600)
    r = st.reader()
    assert r.timeline("7/e1", archive_ms(now - 5 * 86400), archive_ms(now))          # five days: answered
    try:
        r.timeline("7/e1", archive_ms(now - 9 * 86400), archive_ms(now))
        raise AssertionError("the engine answered a nine-day timeline: Archive._timeline's windows can go")
    except ObsdError as e:
        assert e.name == "INTERNAL_ERROR"
    assert st.coverage("7") == [(now - 9 * 86400, now)]                              # …and the archive answers it whole

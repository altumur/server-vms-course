"""The camera's card without an engine (Lesson 26; М12 Lesson 16) — as the product does it.

A camera has some 32 MB of memory, and the archive engine wants 20–25 MB for a writer (the product's design note,
§12 and §14; feedback CB, CT, CV, DG). So on a camera there is no obsd: its frames live in ONE ring in memory
(`CamRing`, a window of 60 s in at most `RING_BYTES`), and its card is a BUFFER of plain segment files with a byte
budget (`CardBuffer`), written from the ring by the card's actuator (`CardActuator`) under the platform's recorder
(`CardRecorder`) — the gate of Lesson 26 unchanged. The server reads the card by ASKING the camera for a range
(`answer_range`, the ingest's range request in М12), never through a door on the camera.

The camera's memory is ONE budget in bytes (`MEMORY_BUDGET`): the ring, what waits for the card, and a piece of the
card on its way to the server are cut out of it, and every test of that below runs on the real `CardBuffer`.
"""
import os
import tempfile

from vms import volumes
from vms.archive import stitch
from vms.card import (MEMORY_BUDGET, PIECE_BYTES, QUEUE_BYTES, QUEUE_LEN, RING_BYTES, NO_ENGINE, CamRing, CardActuator,
                      CardBuffer, CardError, CardRecorder, NeedKey, NoRecording, declare_card, memory_split)
from vms.config import REC_SPEC
from vms.worker import FakeDevice, fake_samples
from w2cplatform.obsd import archive_ms, unix_s
from w2cplatform.spec import SpecController
from tests.conftest import REC_ACL, footage, recorder
from tests.test_lesson11_edge import CARD, _box, _holder


def _frames(t0, t1, step=0.5):
    return fake_samples(t0, t1, step=step, gop=2.0)


def _film(ring, t0, t1, step=0.5, act=None, every=100):
    """The camera's sensor: frames into the ring — and, when the card's writer is the test's, written every so often."""
    for i, s in enumerate(_frames(t0, t1, step)):
        ring.add(s)
        if act is not None and i % every == every - 1:
            act.drain()
    if act is not None:
        act.drain()


# -- the card: segment files with a byte budget ---------------------------------------------------------------------
def test_a_full_card_lets_its_oldest_segments_go_and_never_refuses_a_frame():
    """The budget is the card's size. Past it the oldest segments go — whatever recording they belong to — and the
    open one never does; nothing is refused for a full card (the product's cardbuf)."""
    d = tempfile.mkdtemp(prefix="card-")
    card = CardBuffer(d, budget=20_000, segment_span=10.0)
    for s in _frames(1000, 1100):
        card.append("1-card/e1", s)
    segs, size, budget = card.stats()
    assert size <= budget and segs == 3                                    # within its budget, the open segment kept
    first = card.coverage("1-card")[0][0]
    assert first == 1070.0 and card.coverage("1-card")[-1][1] == 1100.0    # the newest kept, the oldest gone
    assert not os.path.exists(os.path.join(d, "1-card", "e1", f"{archive_ms(1000)}.smpl"))
    assert segs == len(card.coverage("1-card"))


def test_a_stream_opens_on_a_key_frame():
    """A delta frame with no segment of its stream open could never be read: refused, and the writer waits for a key."""
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    delta = _frames(1000, 1002)[1]
    assert not delta.key
    try:
        card.append("1-card/e1", delta)
        raise AssertionError("a delta frame opened a segment")
    except NeedKey:
        pass


def test_a_segment_a_power_loss_cut_is_read_to_its_last_whole_record():
    """Nothing but appends is ever written, so the only repair there is: a record cut in the middle is cut off when
    the card opens, and everything before it is whole."""
    d = tempfile.mkdtemp(prefix="card-")
    card = CardBuffer(d)
    for s in _frames(1000, 1010):
        card.append("1-card/e1", s)
    card.close()
    path = os.path.join(d, "1-card", "e1", f"{archive_ms(1000)}.smpl")
    whole = os.path.getsize(path)
    with open(path, "ab") as f:
        f.write(b"SMPL\x00\x00\x00")                                     # the power went in the middle of a record
    again = CardBuffer(d)
    assert again.coverage("1-card") == [(1000.0, 1010.0)] and os.path.getsize(path) == whole


def test_a_range_starts_on_a_key_frame_and_an_unreadable_card_is_an_error_not_an_empty_answer():
    """What the camera answers a server's request with. From the first key frame in the range, in time order. And a
    segment shorter than the card wrote is an ERROR: answered as "less", the server would remember the rest as not on
    the card and never ask again."""
    d = tempfile.mkdtemp(prefix="card-")
    card = CardBuffer(d)
    for s in _frames(1000, 1060):
        card.append("1-card/e1", s)
    got = card.range("1-card", 1003, 1010)
    assert got[0].key and unix_s(got[0].begin) == 1004.0 and unix_s(got[-1].begin) < 1010
    assert [s.begin for s in got] == sorted(s.begin for s in got)
    path = os.path.join(d, "1-card", "e1", f"{archive_ms(1000)}.smpl")
    with open(path, "r+b") as f:
        f.truncate(os.path.getsize(path) // 2)                            # the card lost half the segment under us
    try:
        card.range("1-card", 1000, 1060)
        raise AssertionError("a segment cut short was answered as if whole")
    except CardError as e:
        assert "shorter than written" in str(e)


def test_a_card_that_is_not_a_directory_does_not_open():
    """Opening is the only honest test, as for a volume: a card that is not there says so here and nowhere later."""
    f = tempfile.mktemp(prefix="card-")
    open(f, "w").close()
    try:
        CardBuffer(f)
        raise AssertionError("a file opened as a card")
    except OSError:
        pass


def test_a_range_is_read_off_the_card_in_pieces_of_bytes_never_as_one_list():
    """The sixth review, blocker 3 and the first row of the card's table: a range came off the card as ONE list — a
    minute at 4 Mbit/s 28.6 MiB, ten minutes 272 — in a camera that has 32 MB. `pieces` hands it over a piece at a
    time, each at most `max_bytes` of frames, read as it is asked for: a hundred seconds of 100-kB frames are a
    hundred pieces of two frames to a reader that never holds a third."""
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    frames = fake_samples(1000, 1100, step=0.5, gop=2.0, size=100_000)
    for s in frames:
        card.append("1-card/e1", s)
    got, sizes = [], []
    for piece in card.pieces("1-card", 1000, 1100, max_bytes=250_000):
        sizes.append(sum(len(s.body) for s in piece))
        got += [s.begin for s in piece]
    assert got == [s.begin for s in frames]                               # every frame, once, in order
    assert len(sizes) == 100 and max(sizes) <= 250_000                    # …and never more than a piece of it in hand
    assert [len(p) for p in card.pieces("1-card", 1000, 1002, max_bytes=1)] == [1, 1, 1, 1]   # a frame larger than a piece goes alone
    whole = card.range("1-card", 1000, 1100)                              # the list a server may ask for: the pieces, joined
    assert [s.begin for s in whole] == got
    import inspect
    assert inspect.isgenerator(card.pieces("1-card", 1000, 1100))         # nothing is read until a piece is asked for


def test_a_read_of_the_card_left_open_between_two_pieces_holds_neither_of_them():
    """The seventh review: the camera's pusher keeps a read of the card open from one pass to the next — a break's
    continuation, a range being answered — and a reader suspended after handing a piece over kept that piece: one more
    piece of the card in memory for every read left open. The piece given away is the reader's only."""
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    for s in fake_samples(1000, 1010, step=0.5, gop=2.0, size=100_000):
        card.append("1-card/e1", s)
    reader = card.pieces("1-card", 1000, 1010, max_bytes=250_000)
    piece = next(reader)
    held = list(reader.gi_frame.f_locals.values())                        # what the suspended reader still holds
    assert not any(v is piece or (isinstance(v, list) and any(x is piece for x in v)) for v in held)
    assert len(next(reader)) == 2 and len(list(reader)) == 8


def test_a_range_names_its_recording_and_a_recording_the_card_does_not_hold_is_an_error():
    """The sixth review: the request did not say WHICH recording. Two recordings on one card, and the server's request
    for `2-card` was answered out of the one the reader was wired to — nothing in the range, remembered as "not on
    the card", never asked again. The reader takes the name: each recording is answered with its own frames; a name
    the card holds nothing of is an ERROR, never an empty answer; and no name is the card's one recording — an error
    when it holds two."""
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    for s in _frames(1000, 1010):
        card.append("1-card/e1", s)
    assert unix_s(card.range(None, 1000, 1010)[0].begin) == 1000.0        # one recording: no name needed
    for s in _frames(2000, 2010):
        card.append("2-card/e1", s)
    assert card.recordings() == ["1-card", "2-card"]
    assert [unix_s(s.begin) for s in card.range("2-card", 0, 3000)] == [2000 + i / 2 for i in range(20)]
    assert [unix_s(s.begin) for s in card.range("1-card", 0, 3000)] == [1000 + i / 2 for i in range(20)]
    assert card.range("1-card", 2000, 2010) == []                         # held, and nothing in that range: the truth
    for name in ("3-card", None):
        try:
            card.pieces(name, 1000, 1010)
            raise AssertionError(f"{name!r} was answered")
        except NoRecording as e:
            assert "1-card, 2-card" in str(e)


# -- the ring: one copy of the camera's frames in memory ------------------------------------------------------------
def test_the_ring_keeps_its_window_from_a_key_frame_and_lets_go_of_whole_groups():
    """The window, from a key frame; never more than its bytes. What goes, goes as whole groups of pictures — a group
    cut in the middle is a group nobody can play (the product's camfeed)."""
    ring = CamRing(window=10.0, max_bytes=1 << 20)
    _film(ring, 1000, 1030)
    held = ring.after(0)
    assert held[0].key and 10.0 <= (held[-1].end - held[0].begin) / 1000 < 12.0
    size = len(held[0].body)
    small = CamRing(window=60.0, max_bytes=20 * size)
    _film(small, 1000, 1030)
    assert small.bytes <= small.max_bytes and small.after(0)[0].key
    assert ring.added == small.added == 60                                # every frame was given to both


def test_a_kept_ring_lets_nothing_go_by_its_window_and_spills_its_oldest_groups_past_its_ceiling():
    """A break the server has not taken is in the ring: kept, it lets go of nothing by its window, and what its byte
    ceiling makes it let go of goes to the card — whole groups, oldest first, no seam between them and the ring."""
    frame = len(_frames(1000, 1001)[0].body)
    ring = CamRing(window=10.0, max_bytes=40 * frame)
    spilled = []
    ring.set_keep(True, spilled.extend)
    _film(ring, 1000, 1030)                                               # sixty frames, a ceiling of forty
    assert spilled and spilled[0].key and len(spilled) % 4 == 0          # whole groups of four frames
    assert [s.begin for s in spilled + ring.after(0)] == [s.begin for s in _frames(1000, 1030)]
    ring.set_keep(False)
    _film(ring, 1030, 1031)
    assert (ring.after(0)[-1].end - ring.after(0)[0].begin) / 1000 < 12.0  # ordinary again: back to its window


def test_the_ring_says_whether_frames_arrive_and_what_it_holds():
    """What the camera's worker says of its frames (the product's `frames_connected`, `last_frame_age_s`, `ring_*`)."""
    now = [1000.0]
    ring = CamRing(window=60.0, max_bytes=32 << 20, clock=lambda: now[0])
    ring.connected = True
    _film(ring, 1000, 1010)
    now[0] = 1013.0
    st = ring.status()
    assert st["frames_connected"] is True and st["last_frame_age_s"] == 13.0
    assert st["ring_samples"] == 20 and st["ring_span_s"] == 10.0 and st["ring_window_s"] == 60.0
    assert st["ring_bytes"] > 0 and st["ring_max_bytes"] == 32 << 20


def test_the_cameras_memory_is_one_budget_cut_three_ways():
    """The sixth review asked what the camera's memory budget is and how it is split. One number — 40 MiB — and three
    shares that add up to it: the ring, the card's queue (every recording's, and the spill), and two pieces in
    flight. A camera measured to have more hands `memory_split` more, and the shares grow with it."""
    ring, queue, piece = memory_split()
    assert (ring, queue, piece) == (RING_BYTES, QUEUE_BYTES, PIECE_BYTES) == (32 << 20, 6 << 20, 1 << 20)          # the product's ring
    assert ring + queue + 2 * piece == MEMORY_BUDGET == 40 << 20
    assert CamRing().max_bytes == RING_BYTES
    act = CardActuator(CamRing())
    assert (act.queue_bytes, act.piece_bytes) == (QUEUE_BYTES, PIECE_BYTES)
    for budget in (16 << 20, 48 << 20):
        r, q, p = memory_split(budget)
        assert r + q + 2 * p == budget and r > q > p > 0


def test_the_ring_says_how_far_back_it_reaches_at_the_bitrate_it_is_given():
    """The window is sixty seconds and the ceiling is bytes: what the ring HOLDS of a camera's stream is whichever is
    less, and it says which (`reach`). At 8 Mbit/s the ring's 32 MiB are thirty-three seconds, at 4 — more than the window, so sixty; a stream
    it holds a whole window of reaches the window, and one it has seen too little of to measure is not guessed."""
    def at(mbit: float) -> CamRing:
        ring = CamRing()
        for s in fake_samples(1000, 1080, step=0.5, gop=2.0, size=int(mbit * 1e6 / 8 / 2)):
            ring.add(s)
        return ring
    four, eight, one = at(4), at(8), at(1)
    assert four.reach() == 60.0 and four.bytes <= RING_BYTES              # 67 s of bytes: the window is less
    assert 32.0 <= eight.reach() <= 35.0 and eight.status()["ring_reach_s"] == round(eight.reach(), 1)
    assert abs(eight.reach() - eight.status()["ring_span_s"]) <= 2.5      # full: what it reaches is what it holds
    assert one.reach() == 60.0                                            # the window is the smaller of the two
    young = CamRing()
    for s in fake_samples(1000, 1002, step=0.5, gop=2.0, size=1_000_000):
        young.add(s)
    assert young.reach() == 60.0                                          # two seconds are not a bitrate


def test_the_ring_is_taken_a_piece_at_a_time_and_says_when_a_piece_does_not_follow_the_last():
    """What a reader HOLDS of the ring while it writes it is a piece, never a snapshot of all of it. A piece goes on
    from the frame the reader had last — in the middle of a group — while the ring still holds that frame; when the
    ring has let it go, the piece starts at the next key frame and says it is not whole."""
    five = sum(len(s.body) for s in _frames(1000, 1010)[:5])              # a piece of five frames, and not a byte more
    ring = CamRing(window=600.0)
    _film(ring, 1000, 1010)                                               # twenty frames, groups of four
    first, whole = ring.piece(0, five)
    assert whole and [unix_s(s.begin) for s in first] == [1000.0, 1000.5, 1001.0, 1001.5, 1002.0] and first[0].key
    again, whole = ring.piece(first[-1].begin, five)                      # 1002.5: a delta, mid-group — it follows
    assert whole and unix_s(again[0].begin) == 1002.5 and not again[0].key
    small = CamRing(window=4.0)
    _film(small, 1000, 1010)                                              # only the last four seconds are held
    gone, whole = small.piece(first[-1].begin, five)
    assert not whole and gone[0].key and unix_s(gone[0].begin) >= 1004.0  # what lay between is gone: from a key frame
    told = []
    nothing, whole = ring.piece(ring.newest(), five, caught_up=lambda: told.append(True))
    assert nothing == [] and whole and told == [True]                     # caught up: said under the ring's lock
    assert [unix_s(s.begin) for s in ring.piece(0, 1 << 20, upto=archive_ms(1001))[0]] == [1000.0, 1000.5, 1001.0]


# -- the card's actuator: hold, release, a slow card, a failing card ---------------------------------------------------
def _act(window=20.0, budget=1 << 30):
    ring, card = CamRing(window=window), CardBuffer(tempfile.mkdtemp(prefix="card-"), budget=budget)
    return ring, card, CardActuator(ring, card, threaded=False)


def test_a_held_recording_writes_nothing_and_its_release_writes_the_ring_then_live():
    """On hold the ring is the pre-record and the card is untouched. Released, the card gets what the ring holds —
    from before anybody noticed — and every frame live after it, one stretch, nothing twice."""
    ring, card, act = _act()
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1030, act=act)
    assert card.stats()[0] == 0 and act.stats("1-card")["hold"] is True
    assert act("release", {"id": "1-card", "now": 1030.0})
    act.drain()                                                           # the writer wakes on the release
    _film(ring, 1030, 1040, act=act)
    cov = stitch(card.coverage("1-card"))
    assert len(cov) == 1 and cov[0][0] <= 1012.0 and cov[0][1] == 1040.0
    st = act.stats("1-card")
    assert st["hold"] is False and st["samples_written"] == round((1040 - cov[0][0]) / 0.5)


def test_a_card_slower_than_the_stream_loses_frames_up_to_the_next_key_frame_and_never_slows_the_ring():
    """The card's queue holds about twenty seconds. A card that does not keep up loses frames FOR THE CARD — counted,
    and up to the next key frame, so the card has a clean hole and never half a group — while the ring takes every
    frame: the pusher and the firmware never wait for a card."""
    ring = CamRing(window=600.0, max_bytes=256 << 20)
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    act = CardActuator(ring, card, threaded=False)
    act("start", {"id": "1-card", "epoch": 1})
    every = fake_samples(1000, 1040, step=0.04, gop=2.0)                  # forty seconds at 25 fps
    stuck, rest = every[:760], every[760:]                                # …the card stuck for the first thirty and a bit
    for s in stuck:
        ring.add(s)
    assert ring.added == len(stuck)                                       # the ring took every frame
    assert act.stats("1-card")["samples_dropped"] == len(stuck) - QUEUE_LEN
    act.drain()                                                           # the card catches up
    for s in rest:                                                        # 1030.4: mid-group — dropped up to 1032
        ring.add(s)
    act.drain()
    cov = card.coverage("1-card")
    assert [round(a, 2) for a, _ in cov] == [1000.0, 1032.0] and cov[-1][1] == 1040.0   # a clean hole, then a key frame
    assert round(cov[0][1], 2) == round(1000 + QUEUE_LEN * 0.04, 2)       # what the queue held reached the card
    assert act.stats("1-card")["samples_dropped"] == len(stuck) - QUEUE_LEN + 40   # …and the deltas up to the key, counted


def test_on_a_camera_the_card_is_written_by_a_thread_of_its_own():
    """The ring only queues; a writer thread per recording takes the queue to the card — nobody calls `drain` on a
    camera — and a stop writes what is left and ends the thread."""
    import time as _time
    ring = CamRing(window=20.0)
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    act = CardActuator(ring, card)                                        # threaded, as on a camera
    act("start", {"id": "1-card", "epoch": 1})
    _film(ring, 1000, 1010)
    deadline = _time.monotonic() + 5.0
    while act.stats("1-card")["samples_written"] < 20 and _time.monotonic() < deadline:
        _time.sleep(0.01)
    assert act.stats("1-card")["samples_written"] == 20
    thread = act.recs["1-card"].thread
    act("stop", {"id": "1-card"})
    assert not thread.is_alive() and card.coverage("1-card") == [(1000.0, 1010.0)]


def test_on_a_camera_a_release_and_a_restart_under_the_writers_thread_lose_no_frame():
    """The same as the tests around it, as it runs on a camera: the writer is a thread, the frames keep arriving while
    it takes the kept ring a piece at a time, and the gate lets the ring go in the same breath as it releases. Between
    the last piece of the ring and the first queued frame nothing falls; nothing is written twice; and a recording
    started again — a new epoch — goes on from where the one before it stopped."""
    import time as _time
    ring = CamRing(window=20.0)
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    act = CardActuator(ring, card, piece_bytes=2_000)                     # threaded; a piece of the ring is seven frames

    def written(n):
        deadline = _time.monotonic() + 10.0
        while act.stats("1-card")["samples_written"] < n and _time.monotonic() < deadline:
            _time.sleep(0.005)
        return act.stats("1-card")["samples_written"]
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1010)
    act.keep("1-card", True)
    _film(ring, 1010, 1100)                                               # a break of a hundred seconds, kept
    assert act("release", {"id": "1-card"}) and act.keep("1-card", False)
    _film(ring, 1100, 1160)                                               # …and frames go on while the writer catches up
    assert written(320) == 320
    assert not ring.kept and act.stats("1-card")["keep"] is False
    act("start", {"id": "1-card", "epoch": 2})                            # started again while it writes
    _film(ring, 1160, 1200)
    assert written(400) == 400
    act("stop", {"id": "1-card"})
    got = [s.begin for s in card.range("1-card", 0, 2000)]
    assert got == [archive_ms(1000 + i / 2) for i in range(400)]          # every frame, once, in order
    assert stitch(card.coverage("1-card")) == [(1000.0, 1200.0)] and act.queued == 0


def test_a_recording_stopped_while_its_ring_is_kept_writes_the_ring_first():
    """A kept ring is a break nobody else has: a stop — a restart of the process in the middle of an outage — writes
    it to the card before the ring may let go of it. A ring on hold and not kept is the pre-record: nothing owed."""
    ring, card, act = _act()
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1010, act=act)
    act("stop", {"id": "1-card"})
    assert card.stats()[0] == 0                                           # held, not kept: the card owes nothing
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    act.keep("1-card", True)
    _film(ring, 1010, 1040, act=act)
    act("stop", {"id": "1-card"})
    assert stitch(card.coverage("1-card"))[0][1] == 1040.0


def test_the_ring_the_queue_and_the_spill_are_bytes_out_of_one_budget():
    """The sixth review: only the ring had a ceiling in bytes. The queue was 512 frames and the spill 2048 — at
    4 Mbit/s a kept ring of 31.5 MiB came with 38.2 MiB spilled, seventy megabytes in a camera of thirty-two. Counted
    here as the review counted it: the bytes the ring holds plus the bytes that wait for a card that is stuck, after
    every frame of a hundred and fifty seconds at 4 Mbit/s. What there is no room for is lost to the CARD, counted,
    and a hole in its coverage. And the writer takes the ring a piece at a time, never as one list."""
    ring = CamRing()
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    act = CardActuator(ring, card, threaded=False)                        # the card is stuck: nobody drains
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    act.keep("1-card", True)                                              # a break, kept in memory
    rec = act.recs["1-card"]

    def waiting() -> int:
        return sum(len(s.body) for q in (rec.spill, rec.live) for s in q if hasattr(s, "body"))
    peak = 0
    for t in range(1000, 1150, 10):                                       # 75 MB through a camera whose budget is 40
        for s in fake_samples(t, t + 10, step=0.5, gop=2.0, size=250_000):
            ring.add(s)
            peak = max(peak, ring.bytes + waiting())
    assert waiting() == act.queued and 5 << 20 < act.queued <= QUEUE_BYTES and ring.bytes <= RING_BYTES
    assert 29 << 20 < peak <= RING_BYTES + QUEUE_BYTES < MEMORY_BUDGET    # full, and never over
    dropped = act.stats("1-card")["samples_dropped"]
    assert dropped == 300 - len(ring.after(0)) - len([s for s in rec.spill if hasattr(s, "body")]) > 100

    taken, piece = [], ring.piece

    def pieces(*a, **kw):
        got = piece(*a, **kw)
        taken.append(sum(len(s.body) for s in got[0]))
        return got
    ring.piece = pieces
    assert act("release", {"id": "1-card"})
    act.drain()                                                           # the card writes at last
    assert len(taken) > 20 and max(taken) <= PIECE_BYTES and act.queued == 0   # the ring, a megabyte at a time
    cov = stitch(card.coverage("1-card"))
    assert len(cov) == 2 and cov[0] == (1000.0, 1012.0) and cov[1][1] == 1150.0   # the spill, a hole, the ring
    assert act.stats("1-card")["samples_written"] == 300 - dropped

    act("stop", {"id": "1-card"})
    act("start", {"id": "2-card", "epoch": 1})                            # a recording that writes — into a stuck card
    for s in fake_samples(2000, 2030, step=0.04, gop=2.0, size=40_000):   # 8 Mbit/s at 25 fps: forty kilobytes a frame
        ring.add(s)
    live = act.recs["2-card"].live
    assert sum(len(s.body) for s in live if hasattr(s, "body")) == act.queued <= QUEUE_BYTES
    assert 100 < len(live) < QUEUE_LEN                                    # the bytes ran out long before the frames did
    assert act.stats("2-card")["samples_dropped"] > 0


def test_two_recordings_keep_the_ring_and_one_letting_go_does_not_take_it_from_the_other():
    """The sixth review: `keep` was one flag on the whole ring. Two recordings on a card kept the same break, the
    second let go — and the ring went back to its window under the first, which lost the start of its break. Each
    recording keeps under its own name; the ring is ordinary again when the LAST of them lets go."""
    ring, card, act = _act()                                              # a window of twenty seconds
    for uid in ("1-a", "1-b"):
        act("start", {"id": uid, "epoch": 1, "hold": True})
    _film(ring, 1000, 1010, act=act)
    assert act.keep("1-a", True) and act.keep("1-b", True)                # both keep the break
    _film(ring, 1010, 1030, act=act)
    assert act.keep("1-b", False)                                         # B's wait is over…
    _film(ring, 1030, 1040, act=act)                                      # …and the ring is still A's: nothing went by the window
    assert ring.kept and act.stats("1-a")["keep"] is True and act.stats("1-b")["keep"] is False
    assert act("release", {"id": "1-a"})
    act.drain()
    assert stitch(card.coverage("1-a")) == [(1000.0, 1040.0)]             # all of A's break, from its start
    assert card.coverage("1-b") == []
    act.keep("1-a", False)
    _film(ring, 1040, 1041, act=act)
    assert not ring.kept and ring.status()["ring_span_s"] < 22.0          # the last keeper let go: back to its window


def test_two_recordings_released_together_write_one_card_at_once_and_neither_loses_a_frame():
    """The neighbour of the same class: two recordings that kept the same break are released in the same pass, and
    from then on both write — frame by frame, in turn. The card had ONE open segment: a frame of the second recording
    closed the first one's, whose next delta frame was refused for want of a key frame, and each lost every group of
    pictures the other wrote in. A segment is open per STREAM; both get the break whole, and every frame after it."""
    ring, card, act = _act()                                              # a window of twenty seconds
    for uid in ("1-a", "1-b"):
        act("start", {"id": uid, "epoch": 1, "hold": True})
    _film(ring, 1000, 1010, act=act)
    for uid in ("1-a", "1-b"):
        act.keep(uid, True)
    _film(ring, 1010, 1030, act=act)
    for uid in ("1-a", "1-b"):
        assert act("release", {"id": uid}) and act.keep(uid, False)       # the gate: both, in one pass
    _film(ring, 1030, 1040, act=act, every=1)                             # both writers run after every frame
    assert len(card.open) == 2 and not ring.kept
    for uid in ("1-a", "1-b"):
        assert stitch(card.coverage(uid)) == [(1000.0, 1040.0)]
        assert [s.begin for s in card.range(uid, 0, 2000)] == [s.begin for s in _frames(1000, 1010) + _frames(1010, 1030)
                                                              + _frames(1030, 1040)]
        st = act.stats(uid)
        assert (st["samples_written"], st["samples_dropped"]) == (80, 0) and "seconds_lost" not in st
    act.stop_all()
    assert card.open == {}


def test_a_ring_kept_by_two_spills_to_both():
    """What a kept ring lets go of past its ceiling goes to EVERYONE keeping it — the second keeper's spill used to
    replace the first's, and the first recording's break lost what the ring let go of."""
    frame = len(_frames(1000, 1001)[0].body)
    ring = CamRing(window=10.0, max_bytes=40 * frame)
    a, b = [], []
    ring.set_keep(True, a.extend, who="1-a")
    ring.set_keep(True, b.extend, who="1-b")
    _film(ring, 1000, 1030)
    assert a and [s.begin for s in a] == [s.begin for s in b]
    ring.set_keep(False, who="1-b")
    _film(ring, 1030, 1040)
    assert ring.kept and len(a) > len(b)                                  # A still keeps, and still gets what goes
    assert [s.begin for s in a + ring.after(0)] == [s.begin for s in _frames(1000, 1030) + _frames(1030, 1040)]


def test_a_released_ring_stays_kept_until_the_writer_has_taken_it():
    """The sixth review: the gate released a recording and let the ring go in the same pass. The writer takes the ring
    a moment later; in between, the next frame trimmed the ring to its window — a break of a hundred seconds, kept
    whole in memory, reached the card as its last thirty. Letting go is remembered, and done by the writer when it
    has taken the ring."""
    ring, card, act = _act()                                              # a window of twenty seconds
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1010)
    act.keep("1-card", True)
    _film(ring, 1010, 1100)                                               # a break of a hundred seconds, whole in memory
    assert act("release", {"id": "1-card"}) and act.keep("1-card", False)  # the gate: released and let go, one pass
    _film(ring, 1100, 1110)                                               # the writer has not run yet; frames go on arriving
    assert ring.kept and act.stats("1-card")["keep"] is True              # still kept: the card has not had the ring
    act.drain()
    assert stitch(card.coverage("1-card")) == [(1000.0, 1110.0)]          # from the start of the break, not its last seconds
    assert not ring.kept and act.stats("1-card")["keep"] is False         # …and now it is let go
    _film(ring, 1110, 1112, act=act)
    assert ring.status()["ring_span_s"] < 22.0 and stitch(card.coverage("1-card")) == [(1000.0, 1112.0)]


def test_a_recording_held_again_and_released_again_writes_no_interval_twice():
    """The sixth review, a minor: a recording started again knew nothing of the one before it. A primary that flaps
    — released, on hold again, released five seconds later, all inside the ring's window — had the same seconds
    written to the card twice, in two segments. Where a recording stopped is carried to the one started after it,
    under the same epoch and under a new one; a `last` ahead of the ring is a clock that stepped back, and is
    forgotten."""
    ring, card, act = _act()                                              # a window of twenty seconds
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1010, act=act)
    act("release", {"id": "1-card"})
    act.drain()
    _film(ring, 1010, 1020, act=act)                                      # released: the ring, then live
    act("restart", {"id": "1-card", "epoch": 1, "hold": True})            # the primary is back: on hold, the same epoch
    _film(ring, 1020, 1025, act=act)
    act("release", {"id": "1-card"})                                      # …and gone again five seconds later
    act.drain()
    _film(ring, 1025, 1030, act=act)
    begins = [s.begin for s in card.range("1-card", 0, 2000)]
    assert begins == sorted(set(begins)) and len(begins) == 60            # thirty seconds at two frames, each once
    assert stitch(card.coverage("1-card")) == [(1000.0, 1030.0)]
    assert act.stats("1-card")["samples_written"] == 60                   # the count goes on across the restart too
    act("start", {"id": "1-card", "epoch": 2})                            # a new epoch: the same recording, the same card
    act.drain()
    _film(ring, 1030, 1032, act=act)
    assert [s.begin for s in card.range("1-card", 0, 2000)] == begins + [archive_ms(1030 + i / 2) for i in range(4)]
    act("stop", {"id": "1-card"})
    act.carried["1-card"] = (archive_ms(5000), 64, 0, 0)                  # the clock stepped back an hour's worth
    act("start", {"id": "1-card", "epoch": 3})
    _film(ring, 1032, 1034, act=act)
    assert stitch(card.coverage("1-card")) == [(1000.0, 1034.0)]          # not waiting for 5000 to come round again


def test_a_hold_in_the_middle_of_a_group_leaves_the_segment_open_and_the_release_loses_no_frame_of_it():
    """The eighth review, found running its probe whole: the gate put a released recording on hold again in the middle
    of a group of pictures. The hold closed the segment, a segment opens on a key frame, and the release that followed
    skipped the rest of the group — on the card nowhere, counted nowhere, while the ring still held it; the camera's
    pusher, reading the card for what memory had let go of, pushed the frames after the hole as if they followed. Now a
    hold — and a restart on hold under the same epoch — leaves the segment open, forced onto the card, and the release
    goes on in it from the frame after the last: every frame once, one segment, nothing dropped. Under a new epoch the
    segment closes, as before."""
    ring, card, act = _act(window=60.0)
    act("start", {"id": "1-card", "epoch": 1, "hold": True})
    _film(ring, 1000, 1005, act=act)
    act("release", {"id": "1-card"})
    act.drain()
    later = _frames(1005, 1020)                                           # key frames at 1005, 1007, 1009, 1011…
    for s in [s for s in later if s.begin < archive_ms(1010)]:
        ring.add(s)
    act.drain()                                                           # …written to 1009.5, a delta of the group of 1009
    act("restart", {"id": "1-card", "epoch": 1, "hold": True})            # on hold again, in the middle of that group
    assert card.follows("1-card/e1", archive_ms(1009.5)) and act.stats("1-card")["hold"] is True
    assert not act.hold("1-card", True)                                   # (already: nothing changes)
    for s in [s for s in later if s.begin >= archive_ms(1010)]:           # 1010 and 1010.5: the rest of the group
        ring.add(s)
    act.drain()
    act("release", {"id": "1-card"})
    act.drain()
    _film(ring, 1020, 1024, act=act)
    begins = [s.begin for s in card.range("1-card", 0, 2000)]
    assert begins == [archive_ms(1000 + i / 2) for i in range(48)]        # every frame, once, in order
    assert card.stats()[0] == 1 and act.stats("1-card")["samples_dropped"] == 0 and "seconds_lost" not in act.stats("1-card")
    act("restart", {"id": "1-card", "epoch": 2, "hold": True})            # a new epoch: its own segment, from a key frame
    assert not card.follows("1-card/e1", archive_ms(1023.5)) and card.stats()[0] == 1
    ring, card, act = _act(window=60.0)                                   # …and what a new epoch costs is counted
    act("start", {"id": "1-card", "epoch": 1})
    frames = _frames(1000, 1010)
    for s in [s for s in frames if s.begin < archive_ms(1003)]:
        ring.add(s)
    act.drain()                                                           # to 1002.5, in the group of 1002
    act("restart", {"id": "1-card", "epoch": 2, "hold": True})
    for s in [s for s in frames if s.begin >= archive_ms(1003)]:
        ring.add(s)
    act("release", {"id": "1-card"})
    act.drain()
    assert act.stats("1-card")["samples_dropped"] == 2                    # 1003 and 1003.5: passed over, and said


def test_a_write_is_given_time_by_what_it_moves_before_the_card_is_said_stalled():
    """The eighth review, a minor: the watch said a card STALLED when one write took longer than `stall_after`, however
    much it moved — a slow, healthy card forcing five seconds of stream at once was a stalled one. What a write may take
    is `stall_after` and its bytes at `STALL_FLOOR`: two mebibytes a second and a half, then the stall."""
    import threading
    import time
    from vms.card import STALL_FLOOR
    from w2cplatform.obsd import video
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"), stall_after=0.3)
    real, seen = card._write, {}

    def slow(data):
        time.sleep(0.6)
        real(data)
    card._write = slow
    for name, size in (("big", 2 * STALL_FLOOR), ("small", 300)):
        t = threading.Thread(target=card.append, args=(f"{name}/e1", video(archive_ms(1000), archive_ms(1001),
                                                                            b"\x00" * size, True)), daemon=True)
        t.start()
        time.sleep(0.45)
        seen[name] = (card.stalled(), round(card.stall_limit(), 1))
        t.join(5)
    assert seen["big"] == (False, 2.3)                                    # 0.3 s and two seconds for two mebibytes
    assert seen["small"][0] is True                                       # a few hundred bytes for 0.45 s: stalled


# -- the recorder on the camera -----------------------------------------------------------------------------------------
def _camera(card_dir=None, when="offline", budget=64 << 20):
    """A camera that is a cluster of its own: its row, its card declared (`kind: edge`), a recording on the card and
    the platform's recorder over the card — the ring its source, no engine anywhere."""
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"]))
    con.create_camera({"name": "gate", "source": CARD, "ref": "SN1"})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    card_dir = card_dir or tempfile.mkdtemp(prefix="card-")
    declare_card(box.vars, "srv-1", card_dir, budget, cam="1")
    SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall).create(
        {"name": "1-card", "cam": "1", "home": "card", **({"when": when} if when else {})})
    ring = CamRing(clock=box.wall)
    act = CardActuator(ring, threaded=False)
    rec = CardRecorder("r-1", box.vars.as_writer("recworker-r-1", REC_ACL), box.objects, ring, act, clock=box.clock,
                       wall=box.wall, server="srv-1", archive_root=box.archive, env={})
    rec.lease_pass(); rec.heartbeat_once()
    rec_ctl = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    rec_ctl.ensure_placed()
    rec.reconcile_once(); rec.heartbeat_once()
    return box, rec, ring, act, rec_ctl


def _status(rec, uid="1-card"):
    return next(s for s in rec.status() if s["id"] == uid)


def test_a_camera_recorder_holds_its_card_and_never_touches_an_engine():
    """The card is a place like any volume — a hold, so the console sees who serves it — and a directory to open,
    not a daemon: the recorder runs with `NO_ENGINE`, which refuses every call, and the whole pass goes through."""
    box, rec, ring, act, rec_ctl = _camera(when=None)
    assert rec.session is NO_ENGINE and rec.hold == "card" and rec.volume == "card" and rec.card is not None
    assert "1-card" in rec.reconciler.actual
    try:
        rec.session.open_volume(params={})
        raise AssertionError("an engine answered on a camera")
    except RuntimeError as e:
        assert "no archive engine" in str(e)
    _film(ring, box.wall(), box.wall() + 10, act=act)
    assert act.stats("1-card")["samples_written"] == 20
    view = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)
    assert [(v["name"], v["kind"], bool(v["served_by"])) for v in view["volumes"]] == [("card", "edge", True)]
    assert volumes.holders(box.vars, REC_SPEC.sub)["card"].by == "r-1"


def test_a_network_volume_declared_in_the_cameras_cluster_does_not_take_the_cameras_recorder():
    """Feedback DH: the product's camera recorder chose its volume by the general rules, where a network volume comes
    before a standby — declared on the camera's console, it lured the recorder off the card, the card stopped being
    a standby (`when: offline` wrote always) and the server stopped seeing it as a source. The camera's recorder
    takes its card and nothing else, pass after pass; a second recorder does not take the card from it."""
    box, rec, ring, act, rec_ctl = _camera()
    volumes.write(box.vars, {"name": "nas", "kind": "network", "url": "s3://nas/cams", "quota_bytes": 1 << 30})
    for _ in range(3):
        rec.lease_pass(); rec_ctl.ensure_placed(); rec.reconcile_once(); rec.heartbeat_once()
        assert rec.hold == "card" and rec.volume == "card" and "1-card" in rec.reconciler.actual
    assert rec.holding["1-card"] is True                                  # still a standby: on hold, not writing
    view = {v["name"]: v for v in volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"]}
    assert view["card"]["served_by"] and view["nas"]["served_by"] is None
    assert volumes.holders(box.vars, REC_SPEC.sub)["card"].by == "r-1"
    other = CardRecorder("r-2", box.vars.as_writer("recworker-r-2", REC_ACL), box.objects, ring,
                         CardActuator(ring, threaded=False), clock=box.clock, wall=box.wall, server="srv-1",
                         archive_root=box.archive, env={})
    other.lease_pass()
    assert other.hold is None and other.capacity == 0 and rec.hold == "card"


def test_what_a_camera_recorder_says_of_its_card_and_its_frames():
    """What the server and the console see of the camera's recording: hold and keep, written and dropped, the last
    error, the card's segments, bytes and budget, and its coverage — read every ten seconds. Of the frames: arriving,
    how long since the last, the ring. And none of the engine's fields: no `archive` to offer to declare, no ring
    quota, no writer watch — nothing on a camera says "engine"."""
    box, rec, ring, act, rec_ctl = _camera(when=None)
    ring.connected = True
    t = box.wall()
    _film(ring, t, t + 30, act=act)
    box.clock.advance(rec.COVERAGE_EVERY)
    rec.heartbeat_once()
    st = _status(rec)
    assert st["via"] == "ring" and st["hold"] is False and st["keep"] is False
    assert st["samples_written"] == 60 and st["samples_dropped"] == 0 and "last_error" not in st
    assert st["card_segments"] == 1 and st["card_bytes"] > 0 and st["card_budget"] == 64 << 20
    assert st["coverage"] == {"from": t, "to": t + 30, "fragments": 1}
    from w2cplatform.console import heartbeats
    hb = heartbeats(box.objects, "rec/")["r-1"]
    assert hb.extra["card"]["state"] == "recording" and hb.extra["card"]["budget"] == 64 << 20
    assert hb.extra["feed"]["frames_connected"] is True and hb.extra["feed"]["ring_samples"] == 60
    assert not hb.extra["archive"] and not {"archive_quota", "volume_quota", "writer", "archive_url"} & set(hb.extra)
    assert volumes.suggest(box.vars, box.objects, REC_SPEC.sub, box.wall()) == []      # nothing to "declare" on a camera
    from vms.console import as_held
    vol = next(v for v in volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"])
    assert as_held(rec_ctl, vol, box.wall())["card"]["state"] == "recording"


def test_a_camera_whose_card_does_not_open_works_without_it_says_why_and_tries_again():
    """An SD card is often mounted after the camera's process starts, or put in later. A card that does not open
    costs the recorder its capacity — not a place to put a recording — and is said, in the heartbeat and in the
    status; the ring keeps taking frames (the pusher needs nothing else), and the card is tried again."""
    bad = tempfile.mktemp(prefix="card-")
    open(bad, "w").close()                                                # not a directory: will not open
    box, rec, ring, act, rec_ctl = _camera(card_dir=bad)
    assert rec.card is None and rec.capacity == 0 and rec.volume_error.startswith("the card would not open")
    assert "1-card" not in rec.reconciler.actual
    from w2cplatform.console import heartbeats
    card = heartbeats(box.objects, "rec/")["r-1"].extra["card"]
    assert card["state"] == "unavailable" and card["error"] and card["tries"] == 1
    _film(ring, box.wall(), box.wall() + 5)
    assert ring.status()["ring_samples"] == 10                            # the camera's frames go on without the card
    try:
        rec.answer_range("1-card", 0, 2e9)
        raise AssertionError("a camera with no card answered a range")
    except CardError as e:
        assert "not open" in str(e)                                       # an error, never "the card holds nothing"
    os.remove(bad); os.makedirs(bad)                                      # the card is put in
    rec.lease_pass()
    assert rec.card is None                                               # …not before the retry is due
    box.clock.advance(rec.CARD_RETRY)
    rec.lease_pass(); rec.heartbeat_once(); rec_ctl.ensure_placed(); rec.reconcile_once()
    assert rec.card is not None and rec.capacity == rec.full_capacity and "1-card" in rec.reconciler.actual


def test_a_card_that_refuses_a_write_kills_the_recording_and_the_recorder_starts_it_again_after_a_backoff():
    """A write error is the card failing, not the stream: the recording is declared dead — the same contract as a
    pipeline that died — said in its status, and started again after the reconciler's backoff."""
    box, rec, ring, act, rec_ctl = _camera(when=None)
    real = rec.card._write

    def refuses(data):
        raise OSError(5, "Input/output error")
    rec.card._write = refuses
    _film(ring, box.wall(), box.wall() + 4, act=act)
    assert "Input/output error" in _status(rec)["last_error"]
    rec.pump_once()
    assert "1-card" not in rec.reconciler.actual                          # dead, and waiting out its backoff
    rec.card._write = real
    rec.reconcile_once()
    assert "1-card" not in rec.reconciler.actual
    box.clock.advance(61)
    rec.reconcile_once()
    assert "1-card" in rec.reconciler.actual and act.calls[-1][0] in ("start", "restart")
    _film(ring, box.wall() + 4, box.wall() + 10, act=act)
    assert act.stats("1-card")["samples_written"] > 0 and "last_error" not in _status(rec)


def test_a_card_that_refuses_writes_is_said_closed_opened_again_and_written_from_where_it_stopped():
    """The sixth review: a card gone read-only refused every write, and for six passes the heartbeat said
    `state: recording`, `volume_error` was empty, and the recording was started again seven times on a card nobody had
    opened again — the frames between the refusal and each restart on the card nowhere. Now the card's own word is
    read every pass: `failing` in the heartbeat at once; then the card is CLOSED — `unavailable`, with what it
    refused, in the heartbeat and in `volume_error`, the refusals counted — and opened again after `CARD_RETRY`; and
    its recording goes on from the last frame the card took, out of the ring: no hole for the half-minute it was
    away."""
    from w2cplatform.console import heartbeats
    box, rec, ring, act, rec_ctl = _camera(when=None)
    t = box.wall()
    _film(ring, t, t + 10, act=act)

    def refuses(data):
        raise OSError(30, "Read-only file system")
    rec.card._write = refuses
    _film(ring, t + 10, t + 14, act=act)                                  # the card refuses; the ring takes every frame
    rec.heartbeat_once()
    card = heartbeats(box.objects, "rec/")["r-1"].extra["card"]
    assert card["state"] == "failing" and "Read-only" in card["error"] and card["failures"] == 1
    rec.pump_once()
    rec.lease_pass()                                                      # the pass reads the card's word, and closes it
    rec.heartbeat_once()
    hb = heartbeats(box.objects, "rec/")["r-1"]
    assert rec.card is None and rec.capacity == 0 and act.card is None
    assert hb.extra["card"]["state"] == "unavailable" and hb.extra["card"]["error"].startswith("refused a write: ")
    assert hb.extra["volume_error"].startswith("the card refused a write: ") and "Read-only" in hb.extra["volume_error"]
    assert hb.extra["card"]["failures"] == 1 and "1-card" not in rec.reconciler.actual
    assert "refused a write" in _status(rec)["why"]
    for _ in range(3):                                                    # no storm of restarts into a card that is closed
        rec.lease_pass(); rec.reconcile_once(); rec.pump_once()
    assert rec.card is None and rec.card_tries == 1 and [c for c in act.calls if c[0] == "start"] == [("start", "1-card")]
    _film(ring, t + 14, t + 40, act=act)                                  # half a minute without a card: all in the ring
    box.clock.advance(rec.CARD_RETRY)
    rec.lease_pass(); rec.heartbeat_once(); rec_ctl.ensure_placed(); rec.reconcile_once()
    assert rec.card is not None and rec.card_tries == 2 and "1-card" in rec.reconciler.actual
    act.drain()
    _film(ring, t + 40, t + 44, act=act)
    rec.heartbeat_once()
    hb = heartbeats(box.objects, "rec/")["r-1"]
    assert hb.extra["card"]["state"] == "recording" and not hb.extra["volume_error"] and "error" not in hb.extra["card"]
    assert stitch(rec.card.coverage("1-card")) == [(t, t + 44)]          # from the last frame written: not a second missing
    assert _status(rec)["samples_written"] == 88 and "last_error" not in _status(rec)


def _alarms(box, kind):
    from w2cplatform.eventdatabase import EventIndex
    return [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1e6, subsystem="rec")["events"]
            if e["kind"] == kind]


def test_a_card_that_stays_read_only_is_an_error_at_every_heartbeat_and_one_alarm_not_a_blinking_metric():
    """The seventh review: under a card gone read-only for good, `volume_error` was empty in the `failing` phase (the
    last write refused, the card not closed yet) and again after each opening anew, until the next refusal — so
    `rec_volume_error` went 1, 0, 1 every thirty seconds, an alert with `for:` never fired, and there was no event of
    the card failing at all. Now every heartbeat of the episode says it — failing, closed, opened again with nothing
    written since — and `card.failing` is raised once for it; a write that lands ends it, and the next failure is a
    new alarm."""
    from w2cplatform.console import heartbeats
    box, rec, ring, act, rec_ctl = _camera(when=None)
    t = box.wall()
    _film(ring, t, t + 10, act=act)
    real = CardBuffer._write

    def refuses(self, data):
        raise OSError(30, "Read-only file system")
    said = []

    def beat():
        rec.heartbeat_once()
        said.append(heartbeats(box.objects, "rec/")["r-1"].extra["volume_error"])
    CardBuffer._write = refuses                                          # the card, and every opening of it, read-only
    try:
        _film(ring, t + 10, t + 14, act=act)
        beat()                                                            # failing: refused, not closed yet
        assert rec.card is not None and said[-1].startswith("the card refused a write: ") and "Read-only" in said[-1]
        rec.gate_pass()
        assert len(_alarms(box, "card.failing")) == 1
        for n in range(3):                                                # three rounds of close, open again, refuse
            rec.pump_once(); rec.lease_pass(); beat()                     # closed
            assert rec.card is None
            box.clock.advance(rec.CARD_RETRY)
            rec.lease_pass(); beat()                                      # opened again: nothing has landed on it
            assert rec.card is not None and "opened again, nothing written to it since" in said[-1]
            rec_ctl.ensure_placed(); rec.reconcile_once()
            _film(ring, t + 14 + 4 * n, t + 18 + 4 * n, act=act); beat()  # …and the first write is refused again
            assert rec.card.err is not None
        assert all(said) and len(said) == 10, said                       # never once empty
        assert len(_alarms(box, "card.failing")) == 1                     # one episode, one alarm
    finally:
        CardBuffer._write = real
    rec.pump_once(); rec.lease_pass()
    box.clock.advance(rec.CARD_RETRY)
    rec.lease_pass(); rec_ctl.ensure_placed(); rec.reconcile_once()
    _film(ring, t + 30, t + 34, act=act); beat()
    assert said[-1] == "" and rec.failing_pass() == "" and rec.failing_said is None   # a write landed: over
    rec.card._write = lambda data: refuses(rec.card, data)
    _film(ring, t + 34, t + 36, act=act)
    rec.gate_pass()
    assert len(_alarms(box, "card.failing")) == 2                         # a new failure, a new alarm


def _timed(fn, *args):
    """`(seconds, result or the exception)` of `fn(*args)` on a thread of its own, given up after three seconds."""
    import threading
    import time
    out, began = {}, time.monotonic()

    def run():
        try:
            out["r"] = fn(*args)
        except Exception as e:                                            # noqa: BLE001
            out["r"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(3.0)
    return time.monotonic() - began, out.get("r", TimeoutError(f"{fn.__name__} did not return in 3 s"))


def test_a_card_write_that_hangs_holds_neither_the_heartbeat_nor_a_range_and_the_card_is_said_stalled():
    """The seventh review: a write to the card that hung for forty seconds held the card's one lock, and every reader
    took it — the heartbeat's counters, the status, a range's answer were blocked past eight seconds, the recorder went
    "lost" after 45 s with no reason, and the card said `recording` all along. Now the card's I/O and what the card
    holds are two locks, and the I/O is watched: while one write hangs, the heartbeat and the status come at once, a
    range is refused at once (`Stalled`, an error — never an empty answer), and the card is said `stalled` — in the
    heartbeat, in `volume_error`, as `writer: stuck` for the console's `rec_writer`, and — once the stall has lasted
    `STALL_ALARM` times what the write may take (the eighth review: a slow, healthy card was an alarm) — as the alarm
    `card.failing`. When the write returns, the card records again and nothing is said."""
    import threading
    import time
    from vms.card import Stalled
    from vms.console import _recorders
    from w2cplatform.console import heartbeats
    box, rec, ring, act, rec_ctl = _camera(when=None)
    card, gate = rec.card, threading.Event()
    card.stall_after = 0.3
    real = card._write

    def hangs(data):
        gate.wait(10)
        real(data)
    t = box.wall()
    _film(ring, t, t + 4, act=act)
    card._write = hangs
    _film(ring, t + 4, t + 6)
    writer = threading.Thread(target=act.drain, daemon=True)            # the card's writer, stuck in its first write
    writer.start()
    try:
        time.sleep(0.5)
        took, _ = _timed(rec.heartbeat_once)
        assert took < 1.0, f"the heartbeat waited {took:.1f} s for a card that does not answer"
        took, st = _timed(rec.status)
        assert took < 1.0 and isinstance(st, list)
        took, got = _timed(rec.answer_range, "1-card", t, t + 4)
        assert took < 1.0 and isinstance(got, Stalled) and "not finished a write" in str(got)
        took, _ = _timed(card.finish, "1-card/e1")                       # the gate's hold: left for the next write
        assert took < 1.0 and card._finish_due == {"1-card/e1"}
        hb = heartbeats(box.objects, "rec/")["r-1"]
        assert hb.extra["card"]["state"] == "stalled" and hb.extra["card"]["stalled_s"] >= 0.3
        assert hb.extra["volume_error"].startswith("the card does not answer: a write to it has not returned for")
        assert "check or replace the card" in hb.extra["volume_error"]
        assert hb.extra["writer"]["state"] == "stuck"
        lines = _recorders(rec_ctl)
        assert 'rec_writer{worker="r-1",state="stuck"} 1' in lines and 'rec_volume_error{worker="r-1"} 1' in lines
        rec.gate_pass()
        assert _alarms(box, "card.failing") == []                        # a slow write is not yet the alarm (the eighth review)…
        time.sleep(rec.STALL_ALARM * card.stall_limit() - card.stalled_for() + 0.1)
        rec.gate_pass(); rec.gate_pass()
        [alarm] = _alarms(box, "card.failing")                           # …one that lasts is, once
        assert alarm["class"] == "alarm" and alarm["state"] == "stalled" and "does not answer" in alarm["error"]
    finally:
        gate.set()
        writer.join(5)
    card._write = real
    act.drain()
    rec.heartbeat_once()
    hb = heartbeats(box.objects, "rec/")["r-1"]
    assert hb.extra["card"]["state"] == "recording" and not hb.extra["volume_error"] and "writer" not in hb.extra
    assert rec.failing_pass() == "" and rec.failing_said is None


def test_the_pre_record_is_what_the_ring_holds_and_a_ring_shorter_than_the_detection_is_an_alarm():
    """The sixth review: `PREBUFFER` was the ring's WINDOW — sixty seconds — whatever the ring held. At 6 Mbit/s it
    holds thirty-three; the primary's death is noticed after forty-five; and the log said "recording from 60 s ago".
    The pre-record is what the ring reaches at the bitrate it is given; the status and the log say what it holds; and
    a ring that reaches less than a break takes to be noticed raises `card.prebuffer.short` — once, not every pass. A
    camera whose own stream tells it of the break notices in ten seconds, and for it the same ring is enough."""
    box, rec, ring, act, rec_ctl = _camera()                              # `when: offline`: on hold, the ring its pre-record
    assert rec.PREBUFFER == 60.0 and rec.prebuffer_pass() == {} and _alarms(box, "card.prebuffer.short") == []
    t = box.wall()
    for a in range(0, 80, 10):                                            # 6 Mbit/s: the ring's 32 MiB are 44 seconds of it
        for s in fake_samples(t + a, t + a + 10, step=0.5, gop=2.0, size=375_000):
            ring.add(s)
    assert 43.0 <= rec.PREBUFFER <= 46.0 and rec.PREBUFFER == ring.reach()
    assert abs(rec.prebuffered("1-card") - ring.status()["ring_span_s"]) < 1e-9 and rec.prebuffered("1-card") <= 46.0
    rec.gate_pass()
    [alarm] = _alarms(box, "card.prebuffer.short")
    assert alarm["class"] == "alarm" and alarm["unit"] == "1-card" and alarm["need_s"] == 50.0
    assert 43.0 <= alarm["reach_s"] <= 46.0 and alarm["window_s"] == 60.0
    st = _status(rec)
    assert st["prebuffer_short"] == 50.0 and 43.0 <= st["prebuffer_s"] <= 46.0
    assert f"the last {rec.prebuffered('1-card'):.0f} s are held in memory" in st["why"] and "60 s" not in st["why"]
    rec.gate_pass(); rec.gate_pass()
    assert len(_alarms(box, "card.prebuffer.short")) == 1                 # when it begins — not once a pass
    assert rec.defer_for() == 15.0                                        # the wait counts on what the ring holds, too
    rec.stream_says = lambda row: False                                   # a camera that pushes hears of a break in ten seconds
    assert rec.prebuffer_pass() == {} and "prebuffer_short" not in _status(rec)


def test_a_ring_that_dips_short_and_back_is_one_alarm_until_it_has_reached_far_enough_for_a_while():
    """The product's sibling of the eighth review: `card.prebuffer.short` had no hysteresis. What the ring reaches is
    measured on what it holds, and a bitrate that moves around the line went short, long, short — every turn a new
    alarm. The status says what is true now; the alarm is one episode, over only when the ring has reached far enough
    for `WELL_FOR`."""
    box, rec, ring, act, rec_ctl = _camera()
    t = box.wall()

    def film(size, seconds=70):
        nonlocal t
        for s in fake_samples(t, t + seconds, step=0.5, gop=2.0, size=size):
            ring.add(s)
        t += seconds
        box.wall.advance(seconds)
        rec.gate_pass()
    film(375_000)                                                         # 6 Mbit/s: 44 s, short of 50
    assert len(_alarms(box, "card.prebuffer.short")) == 1 and "prebuffer_short" in _status(rec)
    film(100_000)                                                         # 1.6 Mbit/s: the whole window — long again
    assert "prebuffer_short" not in _status(rec)
    film(375_000)                                                         # short again, inside the episode: no new alarm
    assert len(_alarms(box, "card.prebuffer.short")) == 1 and "prebuffer_short" in _status(rec)
    for _ in range(int(rec.WELL_FOR // 70) + 1):
        film(100_000)                                                     # long enough for long enough: the episode ends
    film(375_000)
    assert len(_alarms(box, "card.prebuffer.short")) == 2


def test_the_pushers_word_on_the_stream_is_in_the_heartbeat_on_metrics_and_one_alarm_an_episode_of_lagging():
    """The eighth review, blocker 1: the pusher's `continued` — the seconds cut to the live edge, left to backfill,
    failed off the card — reached neither a heartbeat, nor a metric, nor an alarm. Whoever runs the camera's pusher
    beside its recorder hands its word over (`stream_said`): it is the heartbeat's `stream`, the console's
    `rec_stream_behind_seconds`, `rec_stream_lagging` and `rec_stream_skipped_seconds_total{why}`, and a stream that
    lags — the uplink does not carry it — is the alarm `camera.uplink.short`, one an episode: a lagging stream is cut to
    the live edge, lags no more for a minute or two and lags again, and that is not a new alarm each time."""
    from vms.console import _recorders
    from w2cplatform.console import heartbeats
    box, rec, ring, act, rec_ctl = _camera()
    said = {"state": "pushing", "road": "primary", "behind_s": 31.5, "lagging": True, "cut_s": 61.0, "left_s": 4.0,
            "failed_s": 0.0, "failed": 0}
    rec.stream_said = lambda: dict(said)
    rec.heartbeat_once()
    assert heartbeats(box.objects, "rec/")["r-1"].extra["stream"] == said
    lines = _recorders(rec_ctl)
    assert 'rec_stream_behind_seconds{worker="r-1"} 31.5' in lines and 'rec_stream_lagging{worker="r-1"} 1' in lines
    assert 'rec_stream_skipped_seconds_total{worker="r-1",why="cut"} 61.0' in lines
    assert 'rec_stream_skipped_seconds_total{worker="r-1",why="left"} 4.0' in lines
    rec.gate_pass(); rec.gate_pass()
    [alarm] = _alarms(box, "camera.uplink.short")
    assert alarm["class"] == "alarm" and alarm["behind_s"] == 31.5 and alarm["cut_s"] == 61.0
    for lagging in (False, True, False, True):                            # cut, caught up, lagging again: one episode
        said["lagging"] = lagging
        box.wall.advance(60); rec.gate_pass()
    assert len(_alarms(box, "camera.uplink.short")) == 1
    said["lagging"] = False
    box.wall.advance(rec.WELL_FOR); rec.gate_pass()                       # well long enough: over
    said["lagging"] = True
    rec.gate_pass()
    assert len(_alarms(box, "camera.uplink.short")) == 2
    rec.stream_said = lambda: 1 / 0                                       # the pusher's trouble is not the heartbeat's end
    rec.heartbeat_once()
    assert "ZeroDivisionError" in heartbeats(box.objects, "rec/")["r-1"].extra["stream"]["error"]
    """A card is opened by the camera's recorder as files — a bucket or a share is something no card reader opens,
    and a key to one has nowhere to go. That is a `local` or `network` volume, with an engine."""
    volumes.refuse({"name": "card", "kind": "edge", "server": "cam-7", "cam": "7", "url": "/media/sd", "quota_bytes": 1})
    for bad in ({"url": "s3://cards/cam-7"}, {"url": "/media/sd", "access_secret": "x"}):
        try:
            volumes.refuse({"name": "card", "kind": "edge", "server": "cam-7", "cam": "7", "quota_bytes": 1, **bad})
            raise AssertionError(f"{bad} was taken for a card")
        except Exception as e:                                             # Refused
            assert "card in a camera" in str(e)


def test_a_recorder_of_the_engine_never_takes_a_cameras_card():
    """The card is the camera's buffer, written by the camera's own recorder. A recorder of the engine on the same
    box — free to take, or pinned to it by mistake — does not mount it."""
    box, ctl, con, con_vars = _box()
    declare_card(box.vars, "srv-1", tempfile.mkdtemp(prefix="card-"), cam="1")
    r = recorder(box, "r-9", "srv-1", keep_days=1.0)
    r.lease_pass()
    assert r.hold is None and r.volume != "card"
    pinned = recorder(box, "r-8", "srv-1", env={"VOLUME": "card"})
    pinned.lease_pass()
    assert pinned.store is None and "camera's card" in pinned.volume_error


# -- the server closes its gaps from the card: by asking the camera -------------------------------------------------
def _room_and_camera():
    """Camera 1, recorded on srv-a's disks (`1`, through the engine) and on its own card (`1-card`, no engine). One
    cluster here; `card_range` is the server asking the camera for a range — in М12 the ingest does it."""
    from tests.test_backup_archive import _recorder, _volume
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"]))
    con.create_camera({"name": "gate", "source": CARD})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    _volume(box, "disks", "local", "srv-a")
    declare_card(box.vars, "cam-1", tempfile.mkdtemp(prefix="card-"), cam="1")
    con_rec = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)
    con_rec.create({"name": "1", "cam": "1", "home": "disks"})
    con_rec.create({"name": "1-card", "cam": "1", "home": "card"})
    primary = _recorder(box, "r-a", "srv-a", "disks")
    ring = CamRing(clock=box.wall)
    act = CardActuator(ring, threaded=False)
    cam = CardRecorder("r-c", box.vars.as_writer("recworker-r-c", REC_ACL), box.objects, ring, act, clock=box.clock,
                       wall=box.wall, server="cam-1", archive_root=box.archive, env={})
    cam.lease_pass(); cam.heartbeat_once()
    SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects,
                   wall=box.wall).ensure_placed()
    for r in (primary, cam):
        r.reconcile_once(); r.heartbeat_once()
    asked = []

    def card_range(src, t0, t1):                                          # the pieces, joined: what the ingest hands over
        asked.append((src["recording"], t0, t1))
        return [s for piece in cam.answer_range(src["recording"], t0, t1) for s in piece]
    primary.card_range = card_range
    return box, primary, cam, ring, act, asked


def _ours(primary, spans):
    for a, b in spans:
        footage(primary.store, "1", primary.epochs["1"], a, b, step=10, seal=False)
    primary.store.seal()


def test_the_primary_closes_its_gap_from_the_card_by_asking_the_camera():
    """The card's recorder says what the card holds in its heartbeat; the primary plans from that and ASKS the camera
    for exactly the missing hundred seconds — the camera's answer is its card's frames with their own times, and
    they land as ours: our volume, our epoch, the backfill stream. No door on the camera, no engine on it."""
    box, primary, cam, ring, act, asked = _room_and_camera()
    now = box.wall()
    _film(ring, now - 4100, now - 3800, step=1.0, act=act)
    _ours(primary, ((now - 7200, now - 4000), (now - 3900, now - 600)))
    box.clock.advance(cam.COVERAGE_EVERY); cam.heartbeat_once()
    [src] = primary.backup_sources({"id": "1", "cam": "1", "home": "disks"})
    assert (src["kind"], src["recording"], src["url"]) == ("edge", "1-card", "")
    done = primary.backfill(budget=1, now=now, force=True)
    assert [(d["from"], d["to"], d["source"]) for d in done] == [(now - 4000, now - 3900, "edge:1-card")]
    assert asked and all(a >= now - 4000 and b <= now - 3900 for _, a, b in asked)   # asked for the hole, nothing more
    primary.store.seal()
    copied = [s for s in primary.store.spans("1") if s.stream.endswith("/backfill")]
    assert [(c.start, c.end) for c in copied] == [(now - 4000, now - 3900)]
    assert primary.our_coverage("1") == [(now - 7200, now - 600)]


def test_a_hole_on_the_card_itself_is_remembered_as_not_on_the_source_either():
    """The card's summary says start and end. The card itself has forty seconds missing — dropped by a slow card, or
    a break before it opened. What the camera did not send for a clean answer is remembered for THIS source, and the
    next pass does not ask the camera again."""
    box, primary, cam, ring, act, asked = _room_and_camera()
    now = box.wall()
    _film(ring, now - 4100, now - 3960, step=1.0, act=act)
    _film(ring, now - 3920, now - 3800, step=1.0, act=act)
    _ours(primary, ((now - 7200, now - 4000), (now - 3900, now - 600)))
    box.clock.advance(cam.COVERAGE_EVERY); cam.heartbeat_once()
    primary.backfill(budget=1, now=now, force=True)
    primary.store.seal()
    copied = sorted((c.start, c.end) for c in primary.store.spans("1") if c.stream.endswith("/backfill"))
    assert copied == [(now - 4000, now - 3960), (now - 3920, now - 3900)]
    assert primary.nowhere[("1", "edge:1-card")] == [(now - 3960, now - 3920)]
    assert primary.backfill(budget=1, now=now, force=True) == []


def test_a_range_the_camera_could_not_read_fails_the_copy_and_is_asked_again_later():
    """The camera's card was not open when the request came — or a segment read short: the answer is an error, the
    copy fails, nothing is remembered as "not on the card", and a later pass asks again and lands it."""
    box, primary, cam, ring, act, asked = _room_and_camera()
    now = box.wall()
    _film(ring, now - 4100, now - 3800, step=1.0, act=act)
    _ours(primary, ((now - 7200, now - 4000), (now - 3900, now - 600)))
    box.clock.advance(cam.COVERAGE_EVERY); cam.heartbeat_once()
    cam._close_store()                                                    # the card went away under the camera
    [done] = primary.backfill(budget=1, now=now, force=True)
    assert "not open" in done["error"] and not primary.nowhere
    cam._card_retry_at = float("-inf"); cam.volume_pass()                 # it is back
    box.clock.advance(2 * primary.SOURCE_BACKOFF)                       # …and the camera is asked again after its backoff
    cam.heartbeat_once()
    [done] = primary.backfill(budget=1, now=now, force=True)
    assert "error" not in done and done["groups"] > 0


def test_a_camera_that_failed_a_range_is_not_asked_again_at_once():
    """The sixth review: a range that failed was asked again on the very next pass, and the next — the camera read its
    card four times for four failures. A card that failed a range is not a source for a backoff that doubles, with
    jitter; the pass goes on without it instead of spending itself on a camera that just said no; and one range
    landed forgets the failures."""
    box, primary, cam, ring, act, asked = _room_and_camera()
    now = box.wall()
    _film(ring, now - 4100, now - 3800, step=1.0, act=act)
    _ours(primary, ((now - 7200, now - 4000), (now - 3900, now - 600)))
    box.clock.advance(cam.COVERAGE_EVERY); cam.heartbeat_once()
    ask, silent, tried = primary.card_range, {"camera": True}, []

    def card_range(src, t0, t1):
        if silent["camera"]:
            tried.append((t0, t1))
            raise OSError("camera SN1 did not answer a range: nothing of it came for 21 s")
        return ask(src, t0, t1)
    primary.card_range = card_range
    row = {"id": "1", "cam": "1", "home": "disks"}
    waits = []
    for n in (1, 2, 3):
        [done] = primary.backfill(budget=1, now=now, force=True)
        assert "did not answer" in done["error"] and len(tried) == n
        assert primary.backfill(budget=1, now=now, force=True) == [] and len(tried) == n   # not asked again at once…
        assert primary.backup_sources(row) == []                          # …the card is not a source meanwhile
        tries, until = primary._source_asks["edge:1-card"]
        waits.append(until - box.clock())
        assert tries == n and primary.SOURCE_BACKOFF * 2 ** n / 2 <= waits[-1] <= primary.SOURCE_BACKOFF * 2 ** n
        box.clock.advance(waits[-1])
        for r in (primary, cam):
            r.lease_pass(); r.heartbeat_once()
    assert waits[0] < waits[2] and not primary.nowhere                    # the backoff grows; nothing is "not on the card"
    silent["camera"] = False
    [done] = primary.backfill(budget=1, now=now, force=True)
    assert "error" not in done and "edge:1-card" not in primary._source_asks  # landed: the failures are forgotten

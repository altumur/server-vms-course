"""Lesson 16 — the camera's card is read by asking the camera, and a camera without a card is a camera all the same.

The card is the camera's buffer of plain files, written from the camera's one ring with no archive engine on the
camera (`vms/card.py`; the product's camera, feedback CB, DG, DH). Nobody can open a door to a camera that pushes,
and there is no door: the recorder asks for a range, the camera uploads it in answer to its poll. What the card could
not read — no card at all, a card that would not open, a segment read short — is answered RANGE FAILED: the
recorder's copy fails and its backfill asks again later. An empty answer would say "not on the card", for good.

Every card here is the REAL one (`vms.card.CardBuffer`; the sixth review): its reader gives the range in pieces of
sample records, as much as a camera can hold — and the tests that count what the camera holds count it over the ten
minutes at 4 Mbit/s the review measured.
"""
import shutil
import tempfile
import threading
import time
import tracemalloc

from domain.federation import Unreachable
from domain.ingest import (ANSWER_KEPT, LANDED_KEPT, POLL_ROUND, UPLINK_FLOOR, CameraPusher, RangeFailed, card_range,
                           piece_wait)
from tests.conftest import Clock, real_card
from tests.test_lesson16_nobody_reaches import SERIAL, URLS, _site, _times
from vms.card import MEMORY_BUDGET, PIECE_BYTES


def _card(t0, t1):
    """A real card — the camera's buffer, no engine — holding `[t0, t1)` of recording `1-card`."""
    return real_card(t0, t1)


def _frame(t):
    return {"t": float(t), "key": int(t) % 2 == 0}                     # the sensor's frame: a keyframe every two seconds


class _Sink:
    """The recorder's end of the pushed stream, as a subscriber of the ingest: it counts what arrives — frames, the
    bytes of the records that came off the card, whether each is later than the one before — and keeps none of it."""

    def __init__(self):
        self.frames = self.bytes = self.off_card = 0
        self.first, self.last, self.in_order = None, float("-inf"), True

    def push(self, f):
        self.frames += 1
        self.in_order, self.last = self.in_order and f["t"] > self.last, f["t"]
        if "sample" in f:
            self.off_card, self.bytes = self.off_card + 1, self.bytes + len(f["sample"].body)
            self.first = f["t"] if self.first is None else self.first


def test_a_break_of_ten_minutes_is_continued_off_the_card_and_the_camera_holds_one_piece_of_it():
    """The sixth review, blocker 3 — run as it was measured. A break of ten minutes at 4 Mbit/s: the continuation read
    the whole gap off the card into one list — 272 MiB, in a camera that has 32 MB — and then threw all of it away,
    because the card's reader gives `Sample` and the continuation kept only dicts. The camera's process dies of that,
    and its ring, the break it was keeping and its live stream go with it; and had it lived, it sent nothing.

    The same break, on a real `CardBuffer`: every frame of it arrives, in order, from the first keyframe after what the
    recorder has — and what the camera holds while it sends 272 MiB, measured, is a piece of the card and not the gap."""
    from vms.card import CardBuffer
    from vms.worker import fake_samples
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    start, down = wall(), set()

    def dial(url):
        if url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    try:
        for a in range(0, 630, 30):                                    # what the card wrote: 4 Mbit/s, five frames a second
            for s in fake_samples(start + a, start + a + 30, step=0.2, gop=2.0, size=100_000):
                card.append("1-card/e1", s)
        pusher = CameraPusher(SERIAL, cam.flash, dial, clock=wall, card=card.pieces, recording="1-card")
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        sink = ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = _Sink()
        for _ in range(3):
            wall.advance(1); pusher.pass_once([_frame(wall())])
        ingest.written = lambda ref: start + 3.0                       # the recorder wrote up to here
        down.update(URLS)
        for _ in range(600):                                           # ten minutes without a road
            wall.advance(1); pusher.pass_once([_frame(wall())])
        assert pusher.broken_at is not None and len(pusher.ring) == 31  # in memory: the last half-minute
        down.clear()
        wall.advance(1)
        before = sink.frames
        tracemalloc.start()
        held = tracemalloc.get_traced_memory()[0]
        out = pusher.pass_once([_frame(wall())])                       # the road is back: the break is continued
        peak = tracemalloc.get_traced_memory()[1] - held
        tracemalloc.stop()
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    off_card = (573 - 4) * 5                                           # from the keyframe at +4 to where memory begins, +573
    assert sink.off_card == off_card and sink.first == start + 4.0     # every frame of the gap, from a keyframe
    assert sink.frames - before == off_card + 31 + 1 == out["pushed"]  # …then what memory held, then the live frame
    assert sink.in_order and sink.last == wall() and pusher.resumed == off_card + 31
    assert sink.bytes > 270 << 20                                      # 272 MiB went through the camera…
    assert peak < 4 * PIECE_BYTES < MEMORY_BUDGET // 4                 # …and it never held more than a few pieces of it
    assert pusher.broken_at is None and pusher.ring == []


def test_the_camera_answers_a_range_off_its_card_with_the_cards_own_frames_on_the_clusters_clock():
    """The recorder asks on the cluster's clock; the camera — its clock ninety seconds fast — reads its card on its
    own and answers with the card's sample records, from a key frame; they come back on the cluster's clock."""
    from w2cplatform.obsd import unix_s
    wall = Clock(100_000.0)
    fast = Clock(wall() + 90)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(fast() - 1000, fast())
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=fast, card=card.pieces)
    pusher.pass_once([])                                               # the camera states its clock
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
    assert pusher.pass_once([])["uploaded"] == [(fast() - 600, fast() - 590)]
    got = ingest.result(SERIAL, rid)
    assert got[0].key and [round(unix_s(s.begin) - wall()) for s in got] == list(range(-600, -590))


def test_a_range_is_answered_in_pieces_the_camera_can_hold_and_names_the_recording_it_is_of():
    """The sixth review. A minute at 4 Mbit/s was read off the card into one list of 28.6 MiB and uploaded as one: the
    answer goes up in pieces of at most `PIECE_BYTES`, one in the camera's memory at a time, and an upload with
    nothing in it says the answer is whole. And the request NAMES the recording: the card holds two, each is answered
    with its own frames, and one the camera does not have — or no name at all, with two to choose from — is RANGE
    FAILED, never the empty answer the recorder would remember as "not on the card"."""
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = real_card(wall() - 100, wall() - 40, step=0.2, size=100_000)          # a minute at 4 Mbit/s: thirty megabytes
    real_card(wall() - 100, wall() - 90, recording="2-card", card=card)          # …and a second recording on the same card
    try:
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces)
        sizes, upload = [], ingest.upload

        def weighed(token, ref, rid, samples, **kw):
            sizes.append(sum(len(s.body) for s in samples))
            return upload(token, ref, rid, samples, **kw)
        ingest.upload = weighed
        rid = ingest.request_range(SERIAL, wall() - 100, wall() - 40, recording="1-card")
        assert pusher.pass_once([])["uploaded"] == [(wall() - 100, wall() - 40)]
        got = ingest.result(SERIAL, rid)
        assert len(got) == 300 and sum(sizes) == sum(len(s.body) for s in got) > 28 << 20
        assert len(sizes) >= 30 and max(sizes) <= PIECE_BYTES and sizes[-1] == 0   # thirty pieces, and the word "whole"
        rid = ingest.request_range(SERIAL, wall() - 100, wall() - 40, recording="2-card")
        pusher.pass_once([])
        assert _times(ingest.result(SERIAL, rid)) == [wall() - 100 + i for i in range(10)]   # the OTHER recording's frames
        for name, why in (("3-card", "no recording 3-card"), (None, "names no recording")):
            rid = ingest.request_range(SERIAL, wall() - 100, wall() - 40, recording=name)
            assert pusher.pass_once([])["uploaded"] == []
            try:
                ingest.result(SERIAL, rid)
                raise AssertionError(f"a request for {name!r} was answered as if the card held nothing of it")
            except RangeFailed as e:
                assert why in str(e) and "1-card, 2-card" in str(e)
    finally:
        shutil.rmtree(card.path, ignore_errors=True)


def test_the_ingest_forgets_an_answer_it_has_handed_over_and_one_nobody_came_for():
    """The sixth review: the ingest kept every answer for good — twenty requests, twenty answers and 19 MiB, and a day
    of backfill took down the ingest of every camera. An answer is handed over ONCE and forgotten; a failure too; one
    nobody came for goes after `ANSWER_KEPT`; and of what landed, the ingest remembers the last `LANDED_KEPT`."""
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces)
    for _ in range(20):
        rid = ingest.request_range(SERIAL, wall() - 600, wall() - 540)
        pusher.pass_once([])
        assert len(ingest.result(SERIAL, rid)) == 60 and ingest.result(SERIAL, rid) is None   # taken: not there twice
    kept = ingest.cams[SERIAL]
    assert kept.answers == {} and kept.parts == {} and kept.failed == {} and kept.ranges == {} and len(kept.landed) == 20
    pusher.card = None
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 540)
    pusher.pass_once([])
    try:
        ingest.result(SERIAL, rid)
        raise AssertionError("a camera with no card answered")
    except RangeFailed:
        assert kept.failed == {}                                       # said once, and forgotten
    pusher.card = card.pieces
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 540)
    pusher.pass_once([])
    assert len(ingest.answer(SERIAL, rid)) == 60 and len(ingest.answer(SERIAL, rid)) == 60   # a look leaves it there…
    wall.advance(ANSWER_KEPT)
    pusher.pass_once([])                                               # …and nobody came for it: the next poll sweeps
    assert ingest.answer(SERIAL, rid) is None and kept.answers == {}
    for _ in range(LANDED_KEPT + 10):
        rid = ingest.request_range(SERIAL, wall() - 600, wall() - 599)
        pusher.pass_once([])
        assert len(ingest.result(SERIAL, rid)) == 1
    assert len(kept.landed) == LANDED_KEPT and kept.answers == {} and kept.ranges == {}


def test_a_camera_without_a_card_pushes_and_continues_from_memory_and_answers_a_range_failed():
    """No card was put in, or it would not open (feedback DH): the camera still pushes its stream, and continues a
    break from what it kept in memory. A range it is asked for is answered RANGE FAILED — the recorder learns it at
    once and asks again later — never an empty answer it would remember as "not on the card"."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall)          # no card
    ingest.want(SERIAL, "recorder:r-0")
    q = ingest.subscribe(SERIAL, "recorder:r-0")
    wall.advance(1); assert pusher.pass_once([{"t": wall(), "key": True}])["pushed"] == 1
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 300)
    out = pusher.pass_once([])
    assert out["uploaded"] == [] and pusher.failed_ranges[-1][2] == "this camera has no card"
    assert ingest.answer(SERIAL, rid) is None and ingest.landed(SERIAL) == []
    try:
        ingest.result(SERIAL, rid)
        raise AssertionError("a camera with no card answered as if its card were empty")
    except RangeFailed as e:
        assert "no card" in str(e)
    assert [f["t"] for f in q.drain()] == [wall()]                    # the stream itself never needed the card


def test_a_range_the_card_could_not_read_fails_and_a_later_ask_lands_it():
    """The card failed the read — a segment shorter than written, a card gone for a moment — at the first piece or in
    the middle of the answer. The answer is an error, the request is over, nothing of the pieces that did come is
    handed over, and the recorder's next ask is answered with the frames."""
    from w2cplatform.obsd import unix_s
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    broken = {"at": 0}

    def read(recording, t0, t1, max_bytes):
        for n, piece in enumerate(card.pieces(recording, t0, t1, 600)):   # two frames a piece
            if broken["at"] == n:
                raise OSError("reading 1-card/e1: 512 of 4096 bytes — the segment is shorter than written")
            yield piece
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=read)
    for at in (0, 3):                                                  # at once, and with three pieces already up
        broken["at"] = at
        rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
        assert pusher.pass_once([])["uploaded"] == []
        try:
            ingest.result(SERIAL, rid)
            raise AssertionError("a read the card failed was answered")
        except RangeFailed as e:
            assert "shorter than written" in str(e)
        assert ingest.cams[SERIAL].parts == {} and ingest.answer(SERIAL, rid) is None   # no part of it stays
    broken["at"] = None
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
    pusher.pass_once([])
    assert [round(unix_s(s.begin) - wall()) for s in ingest.result(SERIAL, rid)] == list(range(-600, -590))


def test_the_recorders_card_range_asks_the_camera_and_waits_for_its_answer():
    """`RecWorker.card_range` as the ingest gives it: the recorder's request goes in the answer to the camera's poll —
    with the recording the source names — and the call returns when the camera has uploaded, or raises when it
    answered RANGE FAILED, or not at all. Whatever happened, nothing of the request stays in the ingest."""
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    real_card(wall() - 1000, wall() - 990, recording="2-card", card=card)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces)
    ask = card_range(ingest, lambda src: SERIAL, wait=5.0)
    stop = threading.Event()

    def camera():                                                      # the camera's long poll, on its own thread
        while not stop.is_set():
            pusher.pass_once([], wait=0.2)
    t = threading.Thread(target=camera, daemon=True)
    t.start()
    try:
        got = ask({"recording": "1-card", "cam": "1"}, wall() - 600, wall() - 590)
        assert len(got) == 10 and got[0].key
        assert ask({"recording": "2-card", "cam": "1"}, wall() - 600, wall() - 590) == []    # asked of 2-card: it has none there
        assert len(ask({"recording": "2-card", "cam": "1"}, wall() - 1000, wall() - 990)) == 10
        pusher.card = None                                             # the card went
        try:
            ask({"recording": "1-card", "cam": "1"}, wall() - 600, wall() - 590)
            raise AssertionError("a camera without its card answered")
        except RangeFailed:
            pass
    finally:
        stop.set(); t.join(timeout=5)
    try:
        card_range(ingest, lambda src: SERIAL, wait=0.2)({"recording": "1-card"}, wall() - 10, wall())
        raise AssertionError("nobody answered, and the call did not say so")
    except RangeFailed as e:
        assert "did not answer" in str(e)
    kept = ingest.cams[SERIAL]
    assert kept.answers == {} and kept.parts == {} and kept.failed == {} and kept.ranges == {}


def test_a_range_is_waited_for_a_piece_at_a_time_so_a_slow_camera_is_not_a_silent_one():
    """The sixth review: the recorder waited ONE fixed time for the whole answer, whatever it weighed — a camera that
    answered in 1.2 s to a wait of 1 failed four requests of four, and read its card four times. The wait is for the
    next PIECE, and it is derived from what a piece weighs: the poll's round, and a megabyte at the uplink's floor. A
    camera that takes twice the wait to send its answer, a piece every fraction of it, is answered whole; one that
    stops in the middle fails the range one piece's wait later — and is told, at its next piece, that nobody waits:
    it does not read the rest of its card for a recorder that gave up."""
    assert piece_wait() == POLL_ROUND + PIECE_BYTES / UPLINK_FLOOR == 21.0
    assert piece_wait(4 * PIECE_BYTES) - piece_wait() == 3 * PIECE_BYTES / UPLINK_FLOOR   # a larger piece, a longer wait
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    read, gate, stalls = [], threading.Event(), {"after": None}

    def slow(recording, t0, t1, max_bytes):
        for n, piece in enumerate(card.pieces(recording, t0, t1, 600)):   # two frames a piece, each a while in coming
            if stalls["after"] == n:
                gate.wait(10)
            time.sleep(0.15)
            read.append(n)
            yield piece
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=slow)
    ask = card_range(ingest, lambda src: SERIAL, wait=1.0)             # a second for each piece
    stop = threading.Event()

    def camera():
        while not stop.is_set():
            pusher.pass_once([], wait=0.2)
    t = threading.Thread(target=camera, daemon=True)
    t.start()
    try:
        began = time.monotonic()
        got = ask({"recording": "1-card"}, wall() - 600, wall() - 576)   # twelve pieces: 1.8 s of a camera that keeps sending
        assert len(got) == 24 and time.monotonic() - began > 1.5 and read == list(range(12))
        del read[:]
        stalls["after"] = 2                                            # …and one that stops after its second piece
        try:
            ask({"recording": "1-card"}, wall() - 600, wall() - 576)
            raise AssertionError("a camera that went quiet in the middle of its answer was waited for")
        except RangeFailed as e:
            assert "did not answer" in str(e)
        gate.set()                                                     # it wakes, sends its third piece, and is told
    finally:
        time.sleep(0.6)
        stop.set(); t.join(timeout=5)
    assert read == [0, 1, 2]                                           # nine pieces of the card it did not read for nobody
    kept = ingest.cams[SERIAL]
    assert kept.answers == {} and kept.parts == {} and kept.ranges == {}

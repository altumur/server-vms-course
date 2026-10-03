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
import json
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


def _weighed(ingest):
    """The ingest's `upload`, weighing what the camera sends and keeping none of it — the protocol untouched (piece
    numbers, `more`, `failed`): `{"bytes", "samples", "passes": [bytes of each pass]}`. A test that moves 272 MiB
    measures the camera, not the ingest."""
    seen, upload = {"bytes": 0, "samples": 0, "passes": [0], "in_order": True, "last": float("-inf")}, ingest.upload

    def weigh(token, ref, rid, samples, **kw):
        size = sum(len(s.body) for s in samples)
        seen["bytes"] += size
        seen["samples"] += len(samples)
        seen["passes"][-1] += size
        for smp in samples:
            seen["in_order"], seen["last"] = seen["in_order"] and smp.begin > seen["last"], smp.begin
        return upload(token, ref, rid, [], **kw)
    ingest.upload = weigh
    return seen


def test_a_break_of_ten_minutes_is_half_a_minute_of_stream_and_the_rest_is_backfilled_a_piece_a_pass_beside_it():
    """The sixth review, blocker 3, and the seventh's major on its fix. Ten minutes without a road at 4 Mbit/s: the
    continuation read the whole gap off the card into one list — 272 MiB in a camera of 32 MB — and threw it away;
    fixed to read it a piece at a time, it then sent all 272 MiB inside ONE pass: about five minutes over 8 Mbit/s with
    no live frame, no poll, no ask answered. Now the stream continues the last `hold_seconds` out of memory and says
    how much it left (`continued["left_s"]`); the recorder's backfill asks the card for the rest — a range, answered a
    piece's worth a pass, each pass pushing the live frame too. Every frame of the 272 MiB arrives, in order, and what
    the camera holds over the whole of it, measured, is a few pieces and not the gap."""
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
        down.clear()
        before = sink.frames
        wall.advance(1); out = pusher.pass_once([_frame(wall())])      # the road is back
        assert sink.frames - before == out["pushed"] == 31 and sink.last == wall()   # the last thirty seconds, and live
        assert out["continue"]["left_s"] == 571.0 and pusher.broken_at is None       # …and 3..574 left, said
        seen = _weighed(ingest)                                        # the recorder's backfill asks for what was left
        rid = ingest.request_range(SERIAL, start + 3, wall() - 30, recording="1-card")
        tracemalloc.start()
        held, passes, live = tracemalloc.get_traced_memory()[0], 0, sink.frames
        while ingest.cams[SERIAL].ranges and passes < 400:
            seen["passes"].append(0)
            wall.advance(1); pusher.pass_once([_frame(wall())])
            passes += 1
        peak = tracemalloc.get_traced_memory()[1] - held
        tracemalloc.stop()
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    assert ingest.result(SERIAL, rid) == []                            # (landed: its samples were weighed, not kept)
    assert seen["samples"] == (574 - 4) * 5 and seen["in_order"] and seen["bytes"] > 270 << 20   # every frame, in order
    assert passes > 100 and max(seen["passes"]) <= 2 * PIECE_BYTES     # a piece's worth a pass, never the whole range…
    assert sink.frames - live == passes and sink.in_order              # …and every one of those passes pushed live
    assert peak < 4 * PIECE_BYTES < MEMORY_BUDGET // 4                 # the camera held a few pieces of it, not 272 MiB


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
        uploaded, passes = [], 0
        while not uploaded and passes < 100:                           # a piece's worth a pass (the seventh review)
            uploaded, passes = pusher.pass_once([])["uploaded"], passes + 1
        assert uploaded == [(wall() - 100, wall() - 40)] and passes >= 15
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


def test_with_one_upload_in_twenty_lost_and_one_answer_in_twenty_lost_every_range_lands_whole():
    """The seventh review: a lost answer to piece 3 and the camera began the range again from piece 0 — the ingest
    failed it as "out of its turn", the recorder backed off, and at 5 % of answers lost one range in ten landed,
    after 159 pieces read and sent. Now the camera keeps the piece it has no answer for and sends it again under its
    own number: an upload that never arrived is simply taken, one whose answer was lost is taken as a repeat
    (`Ingest.upload`), and a pass whose upload did not get through ends there — `Unreachable` is caught per range,
    never out of the pass. Ten ranges of five pieces each: every one lands whole."""
    import random
    from domain.ingest import Unreachable as Gone
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = real_card(wall() - 1000, wall(), step=0.2, size=50_000)    # 2 Mbit/s: twenty seconds are five pieces
    try:
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces)
        rng, lost, upload = random.Random(16), {"uploads": 0, "answers": 0}, ingest.upload

        def lossy(*a, **kw):
            r = rng.random()
            if r < 0.05:
                lost["uploads"] += 1
                raise Gone("the upload did not arrive")
            out = upload(*a, **kw)
            if r > 0.95:
                lost["answers"] += 1
                raise Gone("the answer to the upload was lost on its way back")
            return out
        ingest.upload = lossy
        rids = {ingest.request_range(SERIAL, wall() - 600 + 30 * i, wall() - 580 + 30 * i): i for i in range(10)}
        got, failed = {}, []
        for _ in range(200):
            pusher.pass_once([])
            for rid in [r for r in rids if r not in got]:
                try:
                    answer = ingest.result(SERIAL, rid)
                except RangeFailed as e:
                    failed.append(str(e))
                    continue
                if answer is not None:
                    got[rid] = answer
            if len(got) + len(failed) == len(rids):
                break
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    assert lost["answers"] >= 2 and lost["uploads"] >= 2                # both kinds of loss happened…
    assert failed == [] and len(got) == 10                              # …and every range landed
    for rid, i in rids.items():
        assert _times(got[rid]) == [wall() - 600 + 30 * i + 0.2 * k for k in range(100)]   # whole, once, in order


def test_the_whole_camera_holds_its_frames_inside_its_memory_budget_through_a_break_and_its_continuation():
    """The seventh review: the pusher's `tail` and `ring` held the camera's frames a second time, outside the budget —
    some 70 MiB in a camera that says 40. On a camera the pusher is given the camera's ring (`ring=`) and holds no
    frame of its own: what it sent, a break, the event's ring are the ring's, under the ring's bytes, and of the card
    it holds one piece in flight. Measured, the whole camera — the ring, the card's writer and its queue, the card,
    the pusher — at 10 Mbit/s, through ten seconds of stream, a minute without a road and the catch-up after it: the
    ring reaches 27 s, less than the stream's 30, so the continuation's first seconds come off the card too. The peak
    stays under `MEMORY_BUDGET`, and every frame from the first keyframe the stream reaches reaches the writer once."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from vms.worker import fake_samples
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    down = set()

    def dial(url):
        if url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest

    class Writer:                                                       # the recorder's writer: newer than its last, or nothing
        def __init__(self):
            self.times, self.repeats, self.off_card = [], 0, 0

        def push(self, f):
            if self.times and f["t"] <= self.times[-1]:
                self.repeats += 1
                return
            self.times.append(f["t"])
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    try:
        ring = CamRing(clock=wall)
        act = CardActuator(ring, card, threaded=False)
        act("start", {"id": "1-card", "epoch": 1})                      # the card writes every frame: its queue is full work
        pusher = CameraPusher(SERIAL, cam.flash, dial, clock=wall, card=card.pieces, recording="1-card", ring=ring)
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        writer = ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        ingest.written = lambda ref: writer.times[-1] if writer.times else None
        reads, pieces = [], card.pieces

        def read(recording, t0, t1, max_bytes):
            reads.append((t0, t1))
            return pieces(recording, t0, t1, max_bytes)
        pusher.card = read

        def second():                                                   # the sensor: 25 frames of 50 kB into the ring
            for s in fake_samples(wall(), wall() + 1, step=0.04, gop=2.0, size=50_000):
                ring.add(s)
            act.drain()
            wall.advance(1)
        tracemalloc.start()
        for _ in range(10):
            second(); pusher.pass_once([])
        down.update(URLS)
        for _ in range(60):
            second(); pusher.pass_once([])
        down.clear()
        back, catching = wall(), 0
        for _ in range(120):
            second(); pusher.pass_once([])
            catching += 1
            if not pusher.behind():
                break
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    assert 24 < ring.reach() < 30 and reads                             # memory reached less than the stream: the card gave the rest
    assert peak < MEMORY_BUDGET, f"the camera held {peak / 2**20:.1f} MiB of a {MEMORY_BUDGET >> 20} MiB budget"
    assert pusher.continued["failed_s"] == 0 and pusher.continued["cut_s"] == 0 and catching > 1, (pusher.continued, catching, peak / 2**20)
    reach = back + 1 - pusher.hold_seconds                              # the first keyframe at `now - hold_seconds`, on
    tail = [t for t in writer.times if t >= reach]
    assert tail[0] - reach < 1.0 and writer.repeats == 0
    assert all(round(b - a, 3) == 0.04 for a, b in zip(tail, tail[1:]))  # …every frame of it, once, in order


# -- the eighth review, blocker 1: what the stream skips is on the card --------------------------------------------------
def _gate(ring, act, pusher, wall, row):
    """The card's gate as the camera's recorder runs it — `RecWorker.gate_pass` itself, with its deferral, its kept ring,
    its release and its hold again — over the camera's real ring and card writer, told by the pusher (`edge_gate`,
    `edge_resumes`). The book (`carried_primary`) says the primary is written: only the stream can open the card."""
    from types import SimpleNamespace
    from domain.ingest import edge_gate, edge_resumes
    from vms.card import CardRecorder
    from vms.recworker import RecWorker

    class Gate(CardRecorder):
        def __init__(self):                                             # the gate alone: no slot, no store, no engine
            self.ring, self.actuator, self.wall, self.name, self.rows = ring, act, wall, "cam", [row]
            self.reconciler = SimpleNamespace(actual={row["id"]})
            self.holding = {row["id"]: True}
            self._primary_back_since, self._cover_since, self._kept_until = {}, {}, {}
            self.stream_says, self.resumes = edge_gate(pusher), edge_resumes(pusher)

        def _offline_backup(self, r):
            return True

        def carried_primary(self, r, now):
            return False

        def _actuate(self, verb, r):                                    # held again: a restart, its hold by the gate's rule
            self.holding[r["id"]] = hold = not self.primary_needs_cover(r)
            return self.actuator(verb, {"id": r["id"], "epoch": 1, "hold": hold})

        def gate_pass(self, now=None):
            return RecWorker.gate_pass(self, now)
    return Gate()


def test_below_the_streams_bitrate_what_the_stream_skips_is_on_the_card_and_backfill_lands_it():
    """The eighth review, blocker 1, run as its probe ran it: the road answers every poll, and the uplink carries 0.75 of
    an 8 Mbit/s stream for 400 s. The stream fell behind, memory let go of what it had not sent, the pusher cut to the
    live edge and logged the seconds as backfill's — and the card `when: offline` never wrote, because a road that
    answers is not "uncovered": 126 s the recorder never got, none of them on the card. Now a stream behind by what
    memory holds is LAGGING, and lagging is uncovered: the real gate opens the card at once (a lagging stream is not
    one memory will continue), the stream goes on off the card while it can, and what the cut skips is on the card.
    Every frame the recorder did not get is on the card, and backfill — ranges asked of the camera — lands it all."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from vms.worker import FAKE_PPS, FAKE_SPS
    from w2cplatform.obsd import archive_ms, unix_s, video
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    start, size = wall(), 100_000                                       # ten frames a second of 100 kB: 8 Mbit/s

    def frame(i):                                                       # the sensor's frame `i`: a key frame every two seconds
        t, key = start + i / 10, i % 20 == 0
        body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + b"\x80" * size
        return video(archive_ms(t), archive_ms(t + 0.1), body, key, 1280, 720)

    class Writer:                                                       # the recorder's writer: newer than its last, or nothing
        def __init__(self):
            self.ms = []

        def push(self, f):
            if not self.ms or archive_ms(f["t"]) > self.ms[-1]:
                self.ms.append(archive_ms(f["t"]))
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    try:
        ring = CamRing(clock=wall)
        act = CardActuator(ring, card, threaded=False)
        row = {"id": "1-card", "cam": "1", "when": "offline"}
        act("start", {"id": "1-card", "epoch": 1, "hold": True})        # a standby: on hold, the ring its pre-record
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces, recording="1-card",
                              ring=ring)
        gate = _gate(ring, act, pusher, wall, row)
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        w = ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        ingest.written = lambda ref: unix_s(w.ms[-1]) if w.ms else None
        fast, rate = ingest.push, 0.75 * size * 10

        def slow(token, ref, frames, camera_now=None):                  # a push takes as long as its bodies take
            took = fast(token, ref, frames, camera_now=camera_now)
            wall.advance(sum(len(f["sample"].body) for f in frames if "sample" in f) / rate)
            return took
        ingest.push, n, lagged = slow, 0, set()

        def second():
            nonlocal n
            while start + n / 10 <= wall():
                ring.add(frame(n))
                n += 1
            act.drain()
            pusher.pass_once([])
            gate.gate_pass()
            act.drain()
            wall.advance(0.5)
        while wall() - start < 400:
            second()
            lagged.add(pusher.lag)
        said, newest = pusher.said(), w.ms[-1]
        missed = [m for m in sorted(set(archive_ms(start + i / 10) for i in range(n)) - set(w.ms)) if m < newest]
        cover = [(archive_ms(a), archive_ms(b)) for a, b in card.coverage("1-card")]
        assert pusher.continued["cut_s"] > 50 and len(missed) > 500     # the stream did skip: a minute and more of it…
        assert [m for m in missed if not any(a <= m <= b for a, b in cover)] == []     # …and every frame of it is on the card
        assert lagged == {True, False} and said["cut_s"] == pusher.continued["cut_s"] and "behind_s" in said
        assert pusher.continued["failed_s"] == 0 and act.stats("1-card")["samples_dropped"] == 0   # no hole on the card
        # Backfill: the recorder asks the camera for each hole in what it wrote, from a key frame before it.
        ingest.push = fast
        holes = [(a, b) for a, b in zip(w.ms, w.ms[1:]) if b - a > 150]
        rids = {ingest.request_range(SERIAL, unix_s(a) - 2.0, unix_s(b), recording="1-card") for a, b in holes}
        landed = set()
        for _ in range(600):
            if not rids:
                break
            second()
            for rid in list(rids):                                      # (taken as each lands: the ingest keeps none for long)
                got = ingest.result(SERIAL, rid)
                if got is not None:
                    landed |= {s.begin for s in got}
                    rids.discard(rid)
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    assert holes and not rids
    assert [m for m in missed if m not in landed] == []                 # all of it, off the card


# -- the ninth review -----------------------------------------------------------------------------------------------------
def test_a_camera_clock_that_steps_back_loses_no_frame_on_the_way_to_the_recorder_nor_on_the_card_and_is_counted():
    """The ninth review, blocker, run as its probe ran it: a camera pushing in real time, its card writing all along,
    and its clock steps — NTP after a boot with a fast RTC — sixty seconds in. The pusher's cursor and the card writer's
    `last` were on the camera's clock: the frames of the next J seconds were "not newer" than where each stood, and
    both passed them over — −5 s lost 5.0 s, −30 s lost 30.0, at the recorder and on the card, and nothing counted
    them. Now the camera's ring keeps one line of time that only goes forward (`CamRing._timed`): every frame captured
    reaches the recorder once, on the cluster's clock where it was captured, every frame is on the card once, and the
    step back is counted and said. A step forward loses nothing either, and is taken up on the line as well (the tenth
    review: the camera's steady clock tells it from a pause): the ingest's offset moves for neither."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from vms.worker import FAKE_PPS, FAKE_SPS
    from w2cplatform.obsd import archive_ms, video
    for step in (-30.0, -5.0, +30.0):
        wall = Clock(100_000.0)
        fed, north, south, signer, ingest, cam, *_ = _site(wall)
        skew = [0.0]
        camclock = lambda: wall() + skew[0]                             # the camera's clock: the cluster's, then stepped
        card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
        try:
            ring = CamRing(clock=camclock, steady=wall)                 # (the camera's steady clock: the true one)
            act = CardActuator(ring, card, threaded=False)
            act("start", {"id": "1-card", "epoch": 1})                  # the card writes every frame
            pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=camclock, ring=ring)
            ingest.want(SERIAL, "recorder:r")
            ingest.subscribe(SERIAL, "recorder:r")
            got = []

            class Writer:                                               # the recorder: which frame, and when on its clock
                def push(self, f):
                    got.append((int.from_bytes(f["sample"].body[-8:], "big"), f["t"]))
            ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
            start, n = wall(), 0
            while wall() - start < 120:
                while start + n / 10 <= wall():                         # ten frames a second, stamped by the camera
                    t, key = camclock() - (wall() - start - n / 10), n % 20 == 0
                    body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + \
                        b"\x80" * 200 + n.to_bytes(8, "big")
                    ring.add(video(archive_ms(t), archive_ms(t + 0.1), body, key, 1280, 720))
                    n += 1
                act.drain(); pusher.pass_once([])
                wall.advance(0.5)
                if abs(wall() - start - 60.0) < 0.26:
                    skew[0] += step                                     # the camera's clock steps here
            act.drain()
            on_card = [int.from_bytes(s.body[-8:], "big") for s in card.range("1-card", 0, 1e12)]
        finally:
            shutil.rmtree(card.path, ignore_errors=True)
        sent = [i for i, _ in got]
        assert sent == list(range(len(sent))) and len(sent) >= n - 10, (step, len(sent), n)   # every frame, once, in order
        assert all(abs(t - (start + i / 10)) < 0.002 for i, t in got), step                 # …where it was captured
        assert on_card == list(range(n)), step                                               # every frame on the card
        said = pusher.said()
        if step < 0:
            assert ring.clock_back == 1 and abs(ring.clock_back_ms / 1000 + step) < 0.01, step  # counted…
            assert abs(said["clock_back_s"] + step) < 0.01 and ring.status()["clock_back_s"] == -step   # …and said
        else:
            assert ring.clock_back == 0 and "clock_back_s" not in said
            assert ring.clock_forward == 1 and abs(said["clock_forward_s"] - step) < 0.01, step
        assert ingest.cams[SERIAL].clock_steps == 0                    # neither moves the offset


def test_a_lagging_stream_keeps_on_the_card_what_it_skipped_until_backfill_has_it_and_backfill_waits_for_the_uplink():
    """The ninth review, major, run as its probe ran it: the uplink carries 0.75 of an 8 Mbit/s stream for 400 s and the
    night's backfill has not come. A lagging stream opens the card, the card writes the whole stream, and its budget let
    go of the oldest first: 345 MiB written into 200, and 61 of the 121 seconds the stream skipped were gone before
    anybody asked for them — on no copy, counted nowhere. Now the card asks the pusher what the server has not got
    (`owed_spans`) and lets go of that last: every skipped second is still on the card at 400 s, nothing is counted as
    let go of, and backfill lands it all once the uplink is back. And no range's piece goes while the stream lags (the
    ninth review, a minor: backfill took the uplink of a stream that was falling behind) — the ranges asked at once wait
    until the stream is at its live edge again."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from vms.worker import FAKE_PPS, FAKE_SPS
    from w2cplatform.obsd import archive_ms, unix_s, video
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    start, size = wall(), 100_000                                       # ten frames a second of 100 kB: 8 Mbit/s

    def frame(i):
        t, key = start + i / 10, i % 20 == 0
        body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + b"\x80" * size
        return video(archive_ms(t), archive_ms(t + 0.1), body, key, 1280, 720)

    class Writer:
        def __init__(self):
            self.ms = []

        def push(self, f):
            if not self.ms or archive_ms(f["t"]) > self.ms[-1]:
                self.ms.append(archive_ms(f["t"]))
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"), budget=200 << 20)
    try:
        ring = CamRing(clock=wall)
        act = CardActuator(ring, card, threaded=False)
        row = {"id": "1-card", "cam": "1", "when": "offline"}
        act("start", {"id": "1-card", "epoch": 1, "hold": True})
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=card.pieces, recording="1-card",
                              ring=ring)
        card.owed = pusher.owed_spans                                   # (the camera's recorder does it: `stream_owed`)
        gate = _gate(ring, act, pusher, wall, row)
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        w = ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        ingest.written = lambda ref: unix_s(w.ms[-1]) if w.ms else None
        fast, upload, rate, written = ingest.push, ingest.upload, 0.75 * size * 10, [0]

        def slow(token, ref, frames, camera_now=None):                  # a push takes as long as its bodies take
            took = fast(token, ref, frames, camera_now=camera_now)
            wall.advance(sum(len(f["sample"].body) for f in frames if "sample" in f) / rate)
            return took
        pieces_while_lagging = []

        def watched(token, ref, rid, samples, **kw):                    # a range's piece: never while the stream lags
            if samples and pusher.lag:
                pieces_while_lagging.append(rid)
            return upload(token, ref, rid, samples, **kw)
        ingest.push, ingest.upload, n = slow, watched, 0
        real_append = card.append

        def counted(stream, s):
            written[0] += len(s.body)
            return real_append(stream, s)
        card.append = counted

        def second():
            nonlocal n
            while start + n / 10 <= wall():
                ring.add(frame(n))
                n += 1
            act.drain()
            pusher.pass_once([])
            gate.gate_pass()
            act.drain()
            wall.advance(0.5)
        while wall() - start < 400:
            second()
        newest = w.ms[-1]
        missed = [m for m in sorted(set(archive_ms(start + i / 10) for i in range(n)) - set(w.ms)) if m < newest]
        cover = [(archive_ms(a), archive_ms(b)) for a, b in card.coverage("1-card")]
        assert written[0] > card.budget * 3 // 2 and pusher.continued["cut_s"] > 100   # the card wrote far past its budget…
        assert [m for m in missed if not any(a <= m <= b for a, b in cover)] == []       # …and kept every skipped frame
        assert card.evicted_owed == 0 and pusher.continued["failed_s"] == 0
        holes = [(a, b) for a, b in zip(w.ms, w.ms[1:]) if b - a > 150]
        rids = {ingest.request_range(SERIAL, unix_s(a) - 2.0, unix_s(b), recording="1-card") for a, b in holes}
        ingest.push = fast                                              # the uplink is back
        landed = set()
        for _ in range(900):
            if not rids:
                break
            second()
            for rid in list(rids):
                got = ingest.result(SERIAL, rid)
                if got is not None:
                    landed |= {s.begin for s in got}
                    rids.discard(rid)
    finally:
        shutil.rmtree(card.path, ignore_errors=True)
    assert holes and not rids and pieces_while_lagging == []
    assert [m for m in missed if m not in landed] == [] and card.evicted_owed == 0     # all of it, off the card


# -- the tenth review -----------------------------------------------------------------------------------------------------
def _sensor(ring, start, camclock, wall, n, size=200):
    """Ten frames a second up to now into the camera's ring, each stamped by the camera's clock where it was captured and
    carrying its number; returns the next number."""
    from vms.worker import FAKE_PPS, FAKE_SPS
    from w2cplatform.obsd import archive_ms, video
    while start + n / 10 <= wall():
        t, key = camclock() - (wall() - start - n / 10), n % 20 == 0
        body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + \
            b"\x80" * size + n.to_bytes(8, "big")
        ring.add(video(archive_ms(t), archive_ms(t + 0.1), body, key, 1280, 720))
        n += 1
    return n


def _number(s) -> int:
    return int.from_bytes(s.body[-8:], "big")


def test_backfill_across_a_forward_step_of_the_cameras_clock_asks_the_card_for_the_hole_and_lands_it_where_captured():
    """The tenth review, blocker, its probe `pl4_fwd_backfill`: the road goes 20–80 s, the camera's clock steps forward J
    in the middle, and the server asks the card for its hole, [19.9, 50.5] on its own clock. The ingest moved the range
    onto the camera's clock by the offset after the step, and the card answered what was captured at [19.9 + J, 50.5 + J],
    laid into the archive at [19.9, 50.5]: at J = 10, the frames of 30–60.4 s ten seconds early; at J = 30, those of 50–80.4
    thirty seconds early — the wrong pictures at the wrong time, and the hole never asked for. The camera's ring takes the
    step forward up on its line now (`CamLine`), so one offset holds for the whole of it: the answer is the frames
    captured in the hole (asked from the key frame before it), each where it was captured; with what the stream carried, every
    frame of the two minutes is at the server once."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from w2cplatform.obsd import unix_s
    for jump in (10.0, 30.0):
        wall = Clock(100_000.0)
        fed, north, south, signer, ingest, cam, *_ = _site(wall)
        skew, down = [0.0], set()
        camclock = lambda: wall() + skew[0]

        def dial(url):
            if url in down:
                raise Unreachable(f"{url} did not answer")
            return ingest
        card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
        try:
            ring = CamRing(clock=camclock, steady=wall)
            act = CardActuator(ring, card, threaded=False)
            act("start", {"id": "1-card", "epoch": 1})                  # the card writes every frame
            pusher = CameraPusher(SERIAL, cam.flash, dial, card=card.pieces, recording="1-card", ring=ring)
            ingest.want(SERIAL, "recorder:r")
            ingest.subscribe(SERIAL, "recorder:r")
            live = []

            class Writer:
                def push(self, f):
                    live.append((_number(f["sample"]), f["t"]))
            ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
            ingest.written = lambda ref: live[-1][1] if live else None
            start, n = wall(), 0

            def second():
                nonlocal n
                n = _sensor(ring, start, camclock, wall, n)
                act.drain()
                pusher.pass_once([])
                wall.advance(0.5)
            while wall() - start < 120:
                second()
                at = wall() - start
                if abs(at - 20) < 0.26:
                    down.update(URLS)
                if abs(at - 50) < 0.26:
                    skew[0] += jump                                     # the camera's clock steps forward, mid-break
                if abs(at - 80) < 0.26:
                    down.clear()
            rid = ingest.request_range(SERIAL, start + 18.0, start + 50.5, recording="1-card")   # (from a key frame)
            answer = None
            for _ in range(40):
                second()
                answer = ingest.result(SERIAL, rid)
                if answer is not None:
                    break
        finally:
            shutil.rmtree(card.path, ignore_errors=True)
        got = [_number(s) for s in answer]
        assert got == list(range(180, 505)), (jump, got[:3], got[-3:])  # the hole, from the key frame before it
        assert all(abs(unix_s(s.begin) - (start + _number(s) / 10)) < 0.002 for s in answer), jump   # where captured
        assert all(abs(t - (start + i / 10)) < 0.002 for i, t in live), jump
        newest = max(i for i, _ in live)
        assert sorted(set(i for i, _ in live) | set(got)) == list(range(newest + 1)), jump    # all of it, once somewhere
        assert ring.clock_forward == 1 and ingest.cams[SERIAL].clock_steps == 0


def _camera_process(wall, vars_, objects, root, flash, dial):
    """The camera's process as the course builds it: its ring, its card's recorder (`CardRecorder`, the card a volume of
    the camera's own cluster) and its pusher — tied in the one call a camera's process makes (`camera_process`)."""
    import os
    from domain.ingest import camera_process
    from vms.card import CamRing, CardActuator, CardRecorder
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    ring = CamRing(clock=wall, steady=wall)
    act = CardActuator(ring, threaded=False)
    rec = CardRecorder("r-cam", vars_, objects, ring, act, clock=wall, wall=wall, server="cam-1",
                       archive_root=os.path.join(root, "archive"), env={})
    rec.lease_pass(); rec.heartbeat_once()
    SpecController(REC_SPEC, vars_, objects, wall=wall).ensure_placed()
    rec.reconcile_once(); rec.heartbeat_once()
    assert rec.card is not None and "1-card" in rec.reconciler.actual
    rec.card.segment_span = 10.0
    return ring, act, rec, camera_process(SERIAL, flash, dial, rec)


def test_what_the_server_has_not_got_outlives_a_restart_of_the_cameras_process_wired_as_a_camera_wires_it():
    """The tenth review, two majors, run through the camera's own wiring (`camera_process`: the course's camera built its
    pusher and its card's recorder nowhere, and the hooks were set by the tests alone). The road goes at 20 s and is
    back at 100: the card wrote the break, the stream continued its last thirty seconds from memory, and 20–70 s are
    owed — backfill's, off the card. The camera's process then starts again, the road down, and its card fills: the
    pusher of the new process said owed only what came after its own start, so the card let go of 20–70 FIRST — on no
    copy, `evicted_owed` nought, no alarm. What the server has is kept on the card now (`delivery`, the recorder's note)
    and the new pusher takes it back (`remember`): the card lets go of what the server has, and every owed frame is
    still on it. The same run with the note taken away was the review's: the owed seconds gone, uncounted — gone still
    (nobody can say they were owed), and counted now (the eleventh review: `test_a_card_with_no_note_…`)."""
    out = {note: _restart_with_a_full_card("kept" if note else "none") for note in (True, False)}
    assert out[True][:3] == (0, 0, True), out                          # every owed frame kept; what went, the server had
    assert out[False][0] > 0 and out[False][1] == 0, out                # owed seconds gone, as owed uncounted…
    assert out[False][3] >= out[False][0] * 100, out                    # …and as let go of unknowing, counted


def test_a_card_with_no_note_a_torn_note_or_another_cameras_note_counts_what_it_lets_go_of_and_offers_no_strange_footage():
    """The eleventh review, a minor: without `delivered.json` — none, torn (a rename a power cut undid on a card without its
    directory forced), or written by another camera — what the card held from before the new process went oldest first
    and was counted nowhere, and a card moved from another camera handed that camera's note and footage to this one. Now
    what lies before the pusher's `since` is unknown (`CameraPusher.unknown_before`, `CardBuffer.unknown`): let go of in
    the same order, counted (`evicted_unknown_ms`, the heartbeat's `evicted_unknown_s`). The note names its camera
    (`serial`): another camera's note is not taken, and a range of the card from before this process is refused as not
    this camera's (`foreign_before`), while what this camera wrote since is given. The kept note counts nothing."""
    out = {case: _restart_with_a_full_card(case) for case in ("kept", "none", "torn", "foreign")}
    assert out["kept"][:4] == (0, 0, True, 0), out
    for case in ("none", "torn", "foreign"):
        missing, owed, within, unknown_ms, said_s, old_range, new_range = out[case]
        assert missing > 0 and owed == 0 and within, (case, out[case])
        assert unknown_ms >= missing * 100 and said_s == round(unknown_ms / 1000.0, 1), (case, out[case])
        assert new_range is True, (case, out[case])
        assert old_range is (case != "foreign"), (case, out[case])     # another camera's footage: not this one's
    assert out["kept"][5] is True and out["kept"][6] is True


def _restart_with_a_full_card(case: str):
    """The tenth review's run: the road down 20–100 s, the camera's process started again, its card filled. `case` — what
    the new process finds of the card's note: `kept`, `none`, `torn` (half its bytes), `foreign` (another camera's).
    Returns (owed frames gone, `evicted_owed`, within budget, `evicted_unknown_ms`, the heartbeat's `evicted_unknown_s`,
    whether a range of the first process's footage is given, whether one of the second's is)."""
    import os
    from vms.card import declare_card
    from vms.config import REC_SPEC
    from w2cplatform.console import heartbeats
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController
    from w2cplatform.variables import FileVariables
    from w2cplatform.obsd import archive_ms
    note = case
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    root, down = tempfile.mkdtemp(prefix="camproc-"), set()
    vars_, objects = FileVariables(os.path.join(root, "config")), FsObjectStore(os.path.join(root, "objects"))
    card_dir = tempfile.mkdtemp(prefix="card-")
    declare_card(vars_, "cam-1", card_dir, 64 << 20, cam="1")
    SpecController(REC_SPEC, vars_, objects, wall=wall).create(
        {"name": "1-card", "cam": "1", "home": "card", "when": "offline"})

    def dial(url):
        if url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest
    ingest.want(SERIAL, "recorder:r")
    ingest.subscribe(SERIAL, "recorder:r")
    live = []

    class Writer:
        def push(self, f):
            if not live or f["t"] > live[-1]:
                live.append(f["t"])
    ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
    ingest.written = lambda ref: live[-1] if live else None
    try:
        ring, act, rec, pusher = _camera_process(wall, vars_, objects, root, cam.flash, dial)
        start, n = wall(), 0

        def second(until):
            nonlocal n
            while wall() - start < until:
                n = _sensor(ring, start, wall, wall, n)
                act.drain(); pusher.pass_once([]); rec.gate_pass(); act.drain()
                wall.advance(0.5)
                at = wall() - start
                if abs(at - 20) < 0.26:
                    down.update(URLS)
                if abs(at - 100) < 0.26:
                    down.clear()
        second(200)
        missed = [m for m in (archive_ms(start + i / 10) for i in range(200, 700))
                  if m not in {archive_ms(t) for t in live}]
        assert len(missed) > 400                                    # 20–70 s: owed, on the card
        card_bytes = rec.card.stats()[1]
        rec.note_pass(force=True)
        del ring, act, rec, pusher                                  # the camera's process ends — no goodbye
        first = start
        kept = os.path.join(card_dir, "delivered.json")
        if note == "none":
            os.remove(kept)
        elif note == "torn":
            with open(kept, "rb") as f:
                raw = f.read()
            with open(kept, "wb") as f:
                f.write(raw[:len(raw) // 2])
        elif note == "foreign":
            with open(kept) as f:
                d = json.load(f)
            assert d["serial"] == SERIAL                            # the note names the camera that wrote it
            d["serial"] = "another-camera"
            with open(kept, "w") as f:
                json.dump(d, f)
        wall.advance(60.0)                                          # …and starts again a minute later
        down.update(URLS)
        ring, act, rec, pusher = _camera_process(wall, vars_, objects, root, cam.flash, dial)
        rec.card.budget = int(card_bytes * 1.1)                     # the card nearly full of the first process
        start, n = wall(), 0
        second(70)
        cover = [(archive_ms(a), archive_ms(b)) for a, b in rec.card.coverage("1-card")]
        rec.heartbeat_once()
        said = heartbeats(objects, "rec/")["r-cam"].extra["stream"].get("evicted_unknown_s", 0)

        def given(t0, t1):
            try:
                return any(True for _ in pusher._read_card("1-card", t0, t1))
            except OSError:
                return False
        lo = max(a for a, _ in rec.card.coverage("1-card") if a < start)  # the first process's newest left
        return (len([m for m in missed if not any(a <= m <= b for a, b in cover)]),
                rec.card.evicted_owed, rec.card.stats()[1] <= rec.card.budget, rec.card.evicted_unknown_ms, said,
                given(lo, lo + 5), given(start + 50, start + 55))
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(card_dir, ignore_errors=True)


# -- the eleventh review -------------------------------------------------------------------------------------------------
def _process(wall, path, camclock, steady, epoch, ingest_of, cam):
    """One process of the camera: its ring, its card (`path`) written whole by the card's writer, and its pusher — what a
    camera's process builds when it starts."""
    from vms.card import CamRing, CardActuator, CardBuffer
    ring = CamRing(clock=camclock, steady=steady)
    card = CardBuffer(path)
    act = CardActuator(ring, card, threaded=False)
    act("start", {"id": "1-card", "epoch": epoch, "hold": False})
    pusher = CameraPusher(SERIAL, cam.flash, ingest_of, card=card.pieces, recording="1-card", ring=ring)
    return ring, card, act, pusher


def test_backfill_after_a_step_and_a_restart_of_the_cameras_process_lands_the_hole_where_captured_at_any_ingest():
    """The eleventh review, blocker 1, run as its probe `pr1_restart_line` ran it, with the product's cross-check beside
    it: the camera's clock steps J at 10 s, the road is down 20–80 s (a hole on the card), the camera's PROCESS starts
    again at 100 s — a new ring, a new line, a steady clock that starts again with it — and at 130 s the server asks the
    card for its hole. The new process's line was the raw clock: the ingest's offset moved by J and the range read the
    card J away — at J = +30 the frames of 50–80 s laid at 20–50, at J = −30 those of 0–20 s at 30–50. The line goes on
    from the card's now (`CamLine.restore`): the hole's frames, each where it was captured, and the ingest's offset never
    moves. The same when the camera comes back after the restart to ANOTHER ingest of the cluster — the hole asked at the
    first: a new ingest measures the camera's offset afresh, and the line it measures is the same line."""
    import os
    from domain.ingest import Ingest
    from domain.agent import ClusterTrust
    from w2cplatform.obsd import unix_s
    for jump in (30.0, -30.0):
        for move in (False, True):
            wall = Clock(100_000.0)
            fed, north, south, signer, ingest, cam, *_ = _site(wall)
            other = Ingest("south", ["srt://srv-2.south:9000"], keys=lambda: ClusterTrust(south.vars).keyset(), wall=wall)
            ingest.peers, other.peers = (lambda: [other]), (lambda: [ingest])
            skew, boot, down, at = [0.0], [wall()], [False], [ingest]
            camclock, steady = (lambda: wall() + skew[0]), (lambda: wall() - boot[0])

            def dial(url):
                if down[0]:
                    raise Unreachable("down")
                return at[0]
            path = tempfile.mkdtemp(prefix="card-")
            try:
                ring, card, act, pusher = _process(wall, path, camclock, steady, 1, dial, cam)
                ingest.want(SERIAL, "recorder:r")
                ingest.subscribe(SERIAL, "recorder:r")
                live = {}

                class Writer:
                    def push(self, f):
                        live.setdefault(_number(f["sample"]), f["t"])
                ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
                start, n, rid, answer = wall(), 0, None, None
                while wall() - start < 200:
                    n = _sensor(ring, start, camclock, wall, n)
                    act.drain()
                    el = round(wall() - start, 1)
                    down[0] = 20 <= el < 80
                    pusher.pass_once([])
                    if rid is not None and answer is None:
                        answer = ingest.result(SERIAL, rid)
                    wall.advance(0.5)
                    el = round(wall() - start, 1)
                    if el == 10.5:
                        skew[0] += jump                                     # the camera's clock steps
                    if el == 100.0:                                         # the camera's process starts again
                        act.stop_all()
                        card.close()
                        boot[0] = wall()
                        ring, card, act, pusher = _process(wall, path, camclock, steady, 2, dial, cam)
                        at[0] = other if move else ingest                   # …and comes back to another ingest
                    if el == 130.0:
                        rid = ingest.request_range(SERIAL, start + 18.0, start + 50.5, recording="1-card")
            finally:
                import shutil
                shutil.rmtree(path, ignore_errors=True)
            case = (jump, move)
            got = [_number(s) for s in answer or []]
            assert got == list(range(180, 505)), (case, got[:2], got[-2:])            # the hole, from the key frame before
            assert all(abs(unix_s(s.begin) - (start + _number(s) / 10)) < 0.002 for s in answer), case   # where captured
            assert all(abs(t - (start + i / 10)) < 0.002 for i, t in live.items()), case
            assert ingest.cams[SERIAL].clock_steps == 0 and (not move or other.cams[SERIAL].clock_steps == 0), case
            assert os.path.basename(path)                                         # (the card's own dir, gone)


def test_a_camera_without_an_rtc_battery_has_its_first_boots_hole_backfilled_and_its_boots_apart_on_the_card():
    """The eleventh review, blocker 2, a regression, run as its probe `pr6_rtcless` ran it (and the product's cross-check:
    "500 of 1000 hole frames after a reboot from the first boot, 300 s off, uncounted"): a camera with no RTC battery
    boots in 1970, NTP sets its clock ten seconds later, the road is down 120–180 s, and at 300 s it reboots — 1970 again,
    NTP again ten seconds later. The line took the first NTP step up and stayed in 1970: the first boot's hole, asked at
    360 s, came back empty — for good — and a hole after the reboot came back half from the first boot, 300 s off. The
    line is re-anchored when the clock is set and what the card wrote before is relabelled (`CamLine._set`,
    `CardBuffer.relabel`); a reboot unset again goes on after the card's newest until it is set: the first boot's hole
    lands whole, each frame where it was captured, and a hole after the reboot holds the second boot's frames only."""
    import shutil
    from w2cplatform.obsd import unix_s
    wall = Clock(1_780_000_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    boot, rtc, down = [wall()], [False], [False]
    camclock = lambda: wall() if rtc[0] else wall() - boot[0]             # 1970 and its uptime until NTP
    steady = lambda: wall() - boot[0]

    def dial(url):
        if down[0]:
            raise Unreachable("down")
        return ingest
    path = tempfile.mkdtemp(prefix="card-")
    try:
        ring, card, act, pusher = _process(wall, path, camclock, steady, 1, dial, cam)
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        live = {}

        class Writer:
            def push(self, f):
                live.setdefault(_number(f["sample"]), f["t"])
        ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        start, n, rids, answers = wall(), 0, {}, {}
        while wall() - start < 440:
            n = _sensor(ring, start, camclock, wall, n)
            act.drain()
            el = round(wall() - start, 1)
            down[0] = 120 <= el < 180 or 340 <= el < 400
            pusher.pass_once([])
            for k, rid in rids.items():
                answers[k] = answers.get(k) or ingest.result(SERIAL, rid)
            wall.advance(0.5)
            el = round(wall() - start, 1)
            if el in (10.0, 310.0):
                rtc[0] = True                                               # NTP sets the clock
            if el == 300.0:                                                 # the camera reboots: 1970 again
                n = _sensor(ring, start, camclock, wall, n)                 # (what it captured until then, its own)
                act.stop_all()
                card.close()
                boot[0], rtc[0] = wall(), False
                ring, card, act, pusher = _process(wall, path, camclock, steady, 2, dial, cam)
                after = n
            if el == 360.0:
                rids["first"] = ingest.request_range(SERIAL, start + 118.0, start + 150.5, recording="1-card")
            if el == 420.0:
                missing = [i for i in range(after, n) if i not in live]
                rids["second"] = ingest.request_range(SERIAL, start + missing[0] / 10 - 2.0,
                                                      start + missing[-1] / 10 + 0.5, recording="1-card")
    finally:
        shutil.rmtree(path, ignore_errors=True)
    first = [_number(s) for s in answers.get("first") or []]
    assert first == list(range(1180, 1505)), (first[:2], first[-2:])        # the first boot's hole, whole
    for s in answers["first"] + answers["second"]:
        assert abs(unix_s(s.begin) - (start + _number(s) / 10)) < 0.002, _number(s)   # every frame where it was captured
    second = [_number(s) for s in answers["second"]]
    assert [i for i in second if i >= after], (after, second[:3])           # the second boot's own frames, none 300 s off
    assert all(abs(t - (start + i / 10)) < 0.002 for i, t in live.items()), [(i, round(t - start - i / 10, 3)) for i, t in sorted(live.items()) if abs(t - (start + i / 10)) >= 0.002][:8]


def test_a_range_being_answered_when_the_cameras_clock_is_set_fails_and_lands_where_captured_when_asked_again():
    """The sibling of the eleventh review's blocker 2 that it did not name: the camera's clock is set while the camera is
    answering a range piece by piece, off segments the card relabels under the read (`CardBuffer.relabel`). The pieces
    after the set would land at the ingest moved by the set — the range asked on the old line, the answer put on the
    cluster's clock by the new offset. A move of the line fails every range under way (`CameraPusher._follow`): the
    server hears RANGE FAILED, asks again, and the range lands whole, every frame where it was captured."""
    import shutil
    from domain.ingest import RangeFailed
    from w2cplatform.obsd import unix_s
    wall = Clock(1_780_000_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    boot, rtc = wall(), [False]
    camclock = lambda: wall() if rtc[0] else wall() - boot                # 1970 and its uptime until NTP
    steady = lambda: wall() - boot
    path = tempfile.mkdtemp(prefix="card-")
    try:
        ring, card, act, pusher = _process(wall, path, camclock, steady, 1, lambda url: ingest, cam)
        start, n, rid, outcome, again = wall(), 0, None, None, None
        while wall() - start < 120:
            n = _sensor(ring, start, camclock, wall, n, size=40_000)
            act.drain()
            pusher.pass_once([])
            if rid is not None and outcome is None:
                try:
                    outcome = ingest.result(SERIAL, rid)
                except RangeFailed as e:
                    outcome = e
                    again = ingest.request_range(SERIAL, start + 4.0, start + 40.0, recording="1-card")
            wall.advance(0.5)
            el = round(wall() - start, 1)
            if el == 58.0:
                rid = ingest.request_range(SERIAL, start + 4.0, start + 40.0, recording="1-card")   # 14 MB: many pieces
            if el == 60.0:
                rtc[0] = True                                               # NTP sets the clock, mid-answer
        answer = ingest.result(SERIAL, again) if again is not None else None
    finally:
        shutil.rmtree(path, ignore_errors=True)
    assert isinstance(outcome, RangeFailed), type(outcome)                  # the answer under way: failed, not moved
    got = [_number(s) for s in answer or []]
    assert got == list(range(40, 400)), (got[:2], got[-2:])
    assert all(abs(unix_s(s.begin) - (start + _number(s) / 10)) < 0.002 for s in answer)

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
from tests.domain.conftest import Clock, real_card
from tests.domain.test_lesson16_nobody_reaches import SERIAL, URLS, _site, _times
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
    from vms.obsd import unix_s
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
    from vms.obsd import unix_s
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
    from vms.obsd import archive_ms, unix_s, video
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

        def slow(token, ref, frames, camera_now=None, **kw):            # a push takes as long as its bodies take
            took = fast(token, ref, frames, camera_now=camera_now, **kw)
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
    from vms.obsd import archive_ms, video
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
    from vms.obsd import archive_ms, unix_s, video
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

        def slow(token, ref, frames, camera_now=None, **kw):            # a push takes as long as its bodies take
            took = fast(token, ref, frames, camera_now=camera_now, **kw)
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
    from vms.obsd import archive_ms, video
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
    from vms.obsd import unix_s
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
    act = CardActuator(ring, threaded=False, serial=SERIAL)            # whose line: said before the card opens (13th review)
    rec = CardRecorder("r-cam", vars_, objects, ring, act, clock=wall, wall=wall, server="cam-1",
                       resource_root=os.path.join(root, "archive"), env={})
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
    this camera's (`foreign_before`), while what this camera wrote since is given. The kept note counts nothing. And with
    no `delivered.json` at all, the line's note says whose card it is (the twelfth review, a minor: `line.json` named no
    camera): another camera's line — `foreign-line` — is that camera's footage, not offered either."""
    out = {case: _restart_with_a_full_card(case) for case in ("kept", "none", "torn", "foreign", "foreign-line")}
    assert out["kept"][:4] == (0, 0, True, 0), out
    for case in ("none", "torn", "foreign", "foreign-line"):
        missing, owed, within, unknown_ms, said_s, old_range, new_range = out[case]
        assert missing > 0 and owed == 0 and within, (case, out[case])
        assert unknown_ms >= missing * 100 and said_s == round(unknown_ms / 1000.0, 1), (case, out[case])
        assert new_range is True, (case, out[case])
        assert old_range is (not case.startswith("foreign")), (case, out[case])   # another camera's footage: not this one's
    assert out["kept"][5] is True and out["kept"][6] is True


def _restart_with_a_full_card(case: str):
    """The tenth review's run: the road down 20–100 s, the camera's process started again, its card filled. `case` — what
    the new process finds of the card's note: `kept`, `none`, `torn` (half its bytes), `foreign` (another camera's),
    `foreign-line` (none, and the line's note another camera's).
    Returns (owed frames gone, `evicted_owed`, within budget, `evicted_unknown_ms`, the heartbeat's `evicted_unknown_s`,
    whether a range of the first process's footage is given, whether one of the second's is)."""
    import os
    from vms.card import declare_card
    from vms.config import REC_SPEC
    from w2cplatform.console import heartbeats
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController
    from w2cplatform.variables import FileVariables
    from vms.obsd import archive_ms
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
        if note in ("none", "foreign-line"):
            os.remove(kept)
        if note == "foreign-line":
            line = os.path.join(card_dir, "line.json")
            with open(line) as f:
                d = json.load(f)
            assert d["serial"] == SERIAL                            # the line's note names its camera too
            d["serial"] = "another-camera"
            with open(line, "w") as f:
                json.dump(d, f)
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
    from vms.obsd import unix_s
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
    from vms.obsd import unix_s
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
    from vms.obsd import unix_s
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


def test_polls_in_the_middle_of_an_upload_recreate_nothing_and_the_answer_lands_where_asked_whatever_the_offset_does():
    """The product's DZ, its second half ("a poll recreated the parts of a range during the upload, and the range never
    assembled"; the product's fix is a `coming` mark on the part), checked in the course: a poll here only READS the
    ranges — the parts of an answer are the upload's alone — and a range of thirty pieces assembles whole, the card read
    once and no piece sent twice, with three polls between every two passes, a poll before and after every upload, and
    three threads polling the whole time. Nothing of it stays behind. The sibling the probe found on this path: the
    camera's held offset that moves while a range is answered — this cluster's clock stepped forward two seconds, taken
    after `OFFSET_RISE` — moved every piece after it: 10 of 300 samples past the range asked for, two seconds of it
    missing. A range goes back by the offset it was first told by (`_Camera.told_by`): it lands where it was asked."""
    import shutil
    import threading
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card, reads = real_card(wall() - 100, wall() - 40, step=0.2, size=100_000), []    # thirty megabytes: thirty pieces

    def read(recording, t0, t1, max_bytes):
        reads.append((t0, t1))
        return card.pieces(recording, t0, t1, max_bytes)
    try:
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=read)
        pusher.pass_once([])
        token, upload, seqs = pusher.entry()["ingest"]["token"], ingest.upload, []

        def poll():
            return ingest.poll(token, SERIAL, camera_now=wall(), version=pusher.versions.get("primary"))

        def polled(*a, **kw):                                              # a poll beside every upload, both sides
            seqs.append(kw.get("seq"))
            poll()
            try:
                return upload(*a, **kw)
            finally:
                poll()
        ingest.upload = polled
        stop = threading.Event()
        threads = [threading.Thread(target=lambda: [poll() for _ in iter(stop.is_set, True)]) for _ in range(3)]
        for th in threads:
            th.start()
        try:
            t0, t1 = wall() - 100, wall() - 40
            rid, uploaded, passes = ingest.request_range(SERIAL, t0, t1, recording="1-card"), [], 0
            while not uploaded and passes < 100:
                for _ in range(3):
                    poll()
                uploaded, passes = pusher.pass_once([])["uploaded"], passes + 1
        finally:
            stop.set()
            for th in threads:
                th.join()
        got = [round(t - t0, 1) for t in _times(ingest.result(SERIAL, rid))]
        assert got == [round(i * 0.2, 1) for i in range(300)], len(got)   # whole, in order, where asked
        assert len(reads) == 1 and sorted(seqs) == sorted(set(seqs)) and passes >= 15     # read once, no piece twice
        c = ingest.cams[SERIAL]
        assert not (c.ranges or c.parts or c.answers or c.failed or getattr(c, "told_by", None))

        skew = [0.0]                                                       # this cluster's clock steps two seconds forward
        ingest.wall = lambda: wall() + skew[0]
        ingest.upload, reads[:] = upload, []
        t0, t1 = wall() - 100, wall() - 40
        rid, uploaded, passes, moved = ingest.request_range(SERIAL, t0, t1, recording="1-card"), [], 0, None
        skew[0] = 2.0
        while not uploaded and passes < 100:
            uploaded, passes = pusher.pass_once([])["uploaded"], passes + 1
            moved = moved or (c.clock_steps and passes)
            wall.advance(2.5)
        assert c.clock_steps == 1 and abs(c.offset - 2.0) < 0.01 and moved < passes - 1, (moved, passes)   # mid-answer
        got = [round(t - t0, 1) for t in _times(ingest.result(SERIAL, rid))]
        assert got == [round(i * 0.2, 1) for i in range(300)], ([t for t in got if not 0 <= t < 60][:3], len(got))
    finally:
        shutil.rmtree(card.path, ignore_errors=True)


def test_a_camera_without_an_rtc_that_reboots_for_seconds_has_its_frames_before_ntp_where_captured():
    """The product's DZ, its rule for a large rise, and the reason for it the course measured: a camera with no RTC battery
    that reboots for R seconds goes on with its line right after the card's newest frame (`CamLine`), so the requests after
    the boot say its offset is R higher. While a rise waited for `OFFSET_RISE` (the first DZ pass), every frame between the
    boot and NTP lay R early at the recorder — 86 to 100 of them for R = 3, 10, 60 s; before that pass a rise past
    `CLOCK_STEP` was taken at once and they lay where captured, but a single slow request then lost its travel's worth of
    frames. A rise past `CLOCK_STEP` is taken at once PROVISIONALLY now (`provisional`): the requests after the boot agree
    with it, it is a step — and the frames of R = 10 and 60 s lie where they were captured, before NTP, after it, and for a
    camera whose clock nobody sets, none of them missing across the set (the twelfth review); R = 3 s, inside
    `CLOCK_STEP`, still waits for `OFFSET_RISE`, its frames 3 s early."""
    import shutil
    wall0 = 1_780_000_000.0
    for R, ntp in ((10.0, 10.0), (60.0, 10.0), (60.0, None), (3.0, 10.0)):
        wall = Clock(wall0)
        fed, north, south, signer, ingest, cam, *_ = _site(wall)
        boot, rtc = [wall()], [False]
        camclock = lambda: wall() if rtc[0] else wall() - boot[0]         # 1970 and its uptime until NTP
        steady = lambda: wall() - boot[0]
        path, live = tempfile.mkdtemp(prefix="card-"), {}

        class Writer:
            def push(self, f):
                live.setdefault(_number(f["sample"]), f["t"])
        try:
            ring, card, act, pusher = _process(wall, path, camclock, steady, 1, lambda url: ingest, cam)
            ingest.want(SERIAL, "recorder:r")
            ingest.subscribe(SERIAL, "recorder:r")
            ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
            start, n, booted, set_at = wall(), 0, None, None
            while wall() - start < 160 + R:
                n = _sensor(ring, start, camclock, wall, n)
                act.drain()
                pusher.pass_once([])
                wall.advance(0.5)
                if round(wall() - start, 1) == 10.0:
                    rtc[0] = True                                           # the first boot's NTP
                if round(wall() - start, 1) == 100.0:                       # off for R seconds, back in 1970
                    n = _sensor(ring, start, camclock, wall, n)
                    act.stop_all()
                    card.close()
                    wall.advance(R)
                    n = booted = int(round((wall() - start) * 10))
                    boot[0], rtc[0] = wall(), False
                    ring, card, act, pusher = _process(wall, path, camclock, steady, 2, lambda url: ingest, cam)
                if booted is not None and ntp is not None and set_at is None and wall() - boot[0] >= ntp:
                    n = set_at = _sensor(ring, start, camclock, wall, n)
                    rtc[0] = True                                           # NTP sets the clock
        finally:
            shutil.rmtree(path, ignore_errors=True)
        before_ntp = {i: t - (start + i / 10) for i, t in live.items() if booted <= i < (set_at or n)}
        after_ntp = {i: t - (start + i / 10) for i, t in live.items() if set_at is not None and i >= set_at}
        assert len(before_ntp) >= 90, (R, ntp, len(before_ntp))
        if R > 5.0:
            assert all(abs(e) < 0.002 for e in before_ntp.values()), (R, ntp, min(before_ntp.values()))
            # …and none missing across the set (the twelfth review's sibling: the stream's place was compared on the old
            # line with the clock on the set one — taken for fallen behind, cut to the next key frame: 4 frames at R = 60)
            missing = [i for i in range(booted, n - 30) if i not in live]
            assert not missing, (R, ntp, missing[:6])
        else:
            assert sum(1 for e in before_ntp.values() if abs(e + R) < 0.002) >= 80, R    # inside the hold: R early
        assert all(abs(e) < 0.002 for e in after_ntp.values()), (R, ntp)


# -- the twelfth review ----------------------------------------------------------------------------------------------
def _road(scenario: str, travel: float, dur: float = 20.0) -> dict:
    """The twelfth review's probe `pz4_road`, as a world of a test: a camera with its ring and card pushes ten frames a
    second; its requests go one after another, and a request stamped `camera_now` as it is sent arrives `travel` later
    while the camera goes on capturing. The camera's clock is the cluster's (the right offset is 0). `scenario`: "one" —
    one push sent at 60 s travels; "stop" — so, and nobody wants the stream after it (no frame to slew by); "poll" — the
    first poll sent after 61 s travels, and it carries the range; "plateau" — every request sent in [60, 60 + dur)
    travels. A range [20, 40] is asked at 61 s (75 s for "stop", 60.6 s for "poll"). Returns what reached the recorder
    and where, and where the range landed."""
    from vms.card import CamRing, CardActuator, CardBuffer
    from vms.worker import FAKE_PPS, FAKE_SPS
    from vms.obsd import archive_ms, unix_s, video
    wall = Clock(100_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    start, st, captured = wall(), {"n": 0, "slow": False}, {}
    ring = CamRing(clock=wall, steady=wall)
    path = tempfile.mkdtemp(prefix="card-")
    try:
        card = CardBuffer(path)
        act = CardActuator(ring, card, threaded=False)
        act("start", {"id": "1-card", "epoch": 1, "hold": False})

        def tick():
            n, key = st["n"], st["n"] % 20 == 0
            body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + \
                b"\x80" * 200 + n.to_bytes(8, "big")
            captured[n] = wall()
            ring.add(video(archive_ms(wall()), archive_ms(wall() + 0.1), body, key, 1280, 720))
            st["n"] += 1
            wall.advance(0.1)
            if st["n"] % 5 == 0:
                act.drain()

        def took(name, el):
            if scenario in ("one", "stop") and name == "push" and el >= 60 and not st["slow"] or \
                    scenario == "poll" and name == "poll" and el >= 61 and not st["slow"]:
                st["slow"] = True
                return travel
            return travel if scenario == "plateau" and 60 <= el < 60 + dur else 0.05

        class Road:                                                    # the camera's requests, each `took` on its way
            def __getattr__(self, name):
                fn = getattr(ingest, name)
                if name not in ("poll", "push", "upload", "answer_ask"):
                    return fn

                def call(*a, camera_now=None, **kw):
                    if camera_now is not None:
                        for _ in range(int(round(took(name, wall() - start) / 0.1))):
                            tick()
                    return fn(*a, camera_now=camera_now, **kw)
                return call
        road = Road()
        pusher = CameraPusher(SERIAL, cam.flash, lambda url: road, ring=ring, card=card.pieces, recording="1-card")
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        got = {}

        class Writer:
            def push(self, f):
                got.setdefault(_number(f["sample"]), f["t"])
        ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        rid = told = landed = None
        ask_at, stopped = {"stop": 75.0, "poll": 60.6}.get(scenario, 61.0), False
        while wall() - start < 200:
            tick()
            if st["n"] % 5 == 0:
                pusher.pass_once([])
                c = ingest.cams[SERIAL]
                if rid is not None and told is None and rid in c.told_by:
                    told = c.told_by[rid]
                if rid is not None and landed is None:
                    landed = ingest.result(SERIAL, rid)
            if scenario == "stop" and st["slow"] and not stopped:
                stopped = True
                ingest.cams[SERIAL].wants.clear()
            if rid is None and wall() - start >= ask_at:
                rid = ingest.request_range(SERIAL, start + 20, start + 40, recording="1-card")
        act.drain()
    finally:
        shutil.rmtree(path, ignore_errors=True)
    c, tee = ingest.cams[SERIAL], ingest.tees[(SERIAL, "live")]
    upto = st["n"] - 30 if scenario != "stop" else 600
    return {"never": [i for i in range(upto) if i not in got], "repeats": tee.repeats, "clock_steps": c.clock_steps,
            "late": max(abs(t - captured[i]) for i, t in got.items()), "told": told,
            "late_n": sum(1 for i, t in got.items() if abs(t - captured[i]) > 0.5),
            "landed": [(_number(s), unix_s(s.begin) - captured[_number(s)]) for s in landed or []]}


def test_a_range_is_told_the_camera_only_by_a_firm_offset_never_by_one_slow_request_or_the_middle_of_a_slew():
    """The twelfth review, blocker 11, run as its probe `pz4_road` ran it: a range is told the camera by the offset it is
    first told by, and goes back by the same (`told_by`) — and that was whatever the held offset was at the moment: a
    provisional rise (the poll that carried the range travelled 6 or 8 s: the range read 6 or 8 s away from the hole), or
    the middle of the slew back after one slow push (10 s on its way: told by 5.0, landed 5 s off; nobody wanting the
    stream after it, the slew stuck at half way, and the range told by 4.0). A range is told by the FIRM offset now
    (`Ingest._told`): the target the stream slews to, and nothing while a rise is provisional — it waits for the requests
    that decide it. Every range lands whole, each frame where it was captured, and no frame of the stream is lost."""
    for scenario, travel in (("one", 10.0), ("poll", 6.0), ("poll", 8.0), ("stop", 8.0)):
        r = _road(scenario, travel)
        assert abs(r["told"]) < 0.01, (scenario, travel, r["told"])
        assert [n for n, _ in r["landed"]] == list(range(200, 400)), (scenario, travel, len(r["landed"]))
        assert all(abs(e) < 0.002 for _, e in r["landed"]), (scenario, travel, sorted({round(e, 1) for _, e in r["landed"]}))
        assert not r["never"] and r["repeats"] == 0 and r["clock_steps"] == 0, (scenario, travel, r["never"][:3])


def test_a_long_poll_held_at_the_ingest_is_not_a_request_that_travelled_and_tells_a_range_by_the_offset_held():
    """The twelfth review, blocker 11, its probe `pz7_held_poll`: the camera's long poll is held at the ingest, and every
    wake ran the poll again — `_check` with the `camera_now` stamped when the poll was SENT — so the hold itself read as
    the request's travel: a range asked 7 s into the hold was told by 5.0 (a provisional rise), 12 s in by 10.02; the
    camera's clock is the cluster's, the right offset is 0. The clock is measured as the poll arrives, once now: a range
    asked during a hold of 7 s is told by the offset held, and the hold moved nothing."""
    from domain.ingest import CLOCK_STEP
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    token = pusher.entry()["ingest"]["token"]
    for _ in range(3):
        ingest.poll(token, SERIAL, camera_now=wall())
        wall.advance(0.5)
    version, out = ingest.poll(token, SERIAL, camera_now=wall())["version"], {}
    held = threading.Thread(target=lambda: out.update(ingest.poll(token, SERIAL, camera_now=wall(), version=version,
                                                                  wait=5.0)))
    held.start()
    time.sleep(0.2)
    wall.advance(7.0)                                                  # seven seconds into the hold (past `CLOCK_STEP`)…
    rid = ingest.request_range(SERIAL, wall() - 100.0, wall() - 80.0)  # …a range: it wakes the held poll
    held.join()
    c = ingest.cams[SERIAL]
    assert 7.0 > CLOCK_STEP and abs(out["ranges"][rid]["from"] - (wall() - 100.0)) < 0.01, out["ranges"][rid]
    assert abs(c.told_by[rid]) < 0.01 and c.provisional is None and abs(c.offset) < 0.01 and c.clock_steps == 0


def test_a_range_told_by_the_travel_of_a_first_request_fails_and_is_told_again_by_the_offset_held():
    """The sibling of blocker 11 the review did not name: the camera's first request sets its offset as it says it, its
    travel in it — eight seconds on a cold uplink — and a range told then reads the card eight seconds from the hole. The
    quick request after it moves the offset down from one not held firm (`_firm`): the range told by the travel fails
    (`Ingest._untold`) — RANGE FAILED, never a wrong answer — and asked again it is told by the offset held."""
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    token = pusher.entry()["ingest"]["token"]
    rid = ingest.request_range(SERIAL, wall() - 60.0, wall() - 50.0)
    work = ingest.poll(token, SERIAL, camera_now=wall() - 8.0)        # the first request: eight seconds on its way
    assert abs(work["ranges"][rid]["from"] - (wall() - 68.0)) < 0.01   # told by the travel
    wall.advance(0.5)
    ingest.poll(token, SERIAL, camera_now=wall())                      # a quick one: the offset comes down
    try:
        ingest.result(SERIAL, rid)
        raise AssertionError("a range told by a request's travel landed")
    except RangeFailed as e:
        assert "slow request" in str(e), e
    again = ingest.request_range(SERIAL, wall() - 60.0, wall() - 50.0)
    work = ingest.poll(token, SERIAL, camera_now=wall())
    t0 = work["ranges"][again]["from"]
    assert abs(t0 - (wall() - 60.0)) < 0.01, t0                        # told by the offset held
    ingest.upload(token, SERIAL, again, [_frame(t0 + 1.0)], camera_now=wall())
    assert [round(f["t"] - (wall() - 59.0), 3) for f in ingest.result(SERIAL, again)] == [0.0]


def test_a_plateau_of_travel_longer_than_the_clock_step_is_not_a_step_and_loses_no_frame():
    """The twelfth review, blocker 13, its probe `pz4_road SC=bloat`: every request for twenty seconds travelled eight —
    a full drop-tail buffer, the delay constant — so three requests agreed with the provisional rise, it became a step,
    and the first quick request after the plateau jumped the offset down at once: 79 frames to `repeats`, `clock_steps`
    2; six seconds for a minute, 59. The camera says its last round trip with every request now (`rtt`), and a request
    whose round trip explains its rise does not count for it (`Ingest._offset`); a move down past `CLOCK_STEP` is never a
    jump, from a firm offset too. Both plateaus: no frame lost, none repeated, no step counted, the plateau's frames at
    most its travel late — and a range asked during it lands where it was captured."""
    for travel, dur in ((8.0, 20.0), (6.0, 60.0)):
        r = _road("plateau", travel, dur)
        assert not r["never"] and r["repeats"] == 0 and r["clock_steps"] == 0, (travel, dur, len(r["never"]), r["clock_steps"])
        assert r["late"] <= travel + 0.11, (travel, dur, r["late"])
        assert [n for n, _ in r["landed"]] == list(range(200, 400)) and all(abs(e) < 0.002 for _, e in r["landed"])


def _rtcless(R: float, ntp_after: float | None):
    """The twelfth review's probe `pz3_rtcless_window`, with a recorder's backfill beside it: a camera with no RTC battery
    — NTP sets its clock 10 s after its first boot; the road is down 120–180 s (a hole on its card); at 300 s it is off
    for `R` s and boots in 1970 again, NTP `ntp_after` s after that boot (None: never). Five seconds after the boot the
    recorder asks the first boot's hole, the reboot's gap and three seconds of the second boot; a range answered RANGE
    FAILED is asked again ten seconds later, as backfill does. Returns the answers and the refusals."""
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
        start, n, rids, spans, answers, refused, retry = wall(), 0, {}, {}, {}, {}, {}
        booted = last = first = None
        while wall() - start < 300 + R + 120:
            el = round(wall() - start, 1)
            if booted is None or el >= booted:
                n = _sensor(ring, start, camclock, wall, n)
                act.drain()
                down[0] = 120 <= el < 180
                pusher.pass_once([])
            for k, rid in list(rids.items()):
                try:
                    got = ingest.result(SERIAL, rid)
                except RangeFailed:
                    refused[k] = refused.get(k, 0) + 1
                    del rids[k]
                    retry[k] = el + 10.0
                    continue
                if got is not None:
                    answers[k] = got
                    del rids[k]
            for k in [k for k, at in retry.items() if el >= at]:
                del retry[k]
                rids[k] = ingest.request_range(SERIAL, *spans[k], recording="1-card")
            wall.advance(0.5)
            el = round(wall() - start, 1)
            if el == 10.0:
                rtc[0] = True                                               # the first boot's NTP
            if el == 300.0:                                                 # off for R seconds, 1970 again
                n = _sensor(ring, start, camclock, wall, n)
                act.stop_all()
                card.close()
                last, booted = n - 1, 300.0 + R
            if el == booted:
                boot[0], rtc[0] = wall(), False
                n = first = int(round(el * 10))
                ring, card, act, pusher = _process(wall, path, camclock, steady, 2, dial, cam)
            if booted is not None and ntp_after is not None and el == booted + ntp_after:
                n = _sensor(ring, start, camclock, wall, n)
                rtc[0] = True                                               # NTP sets the clock
            if booted is not None and el == booted + 5.0:
                spans = {"hole": (start + 118.0, start + 150.5), "reboot": (start + last / 10 - 2.0, start + first / 10 + 2.0),
                         "boot2": (start + first / 10 + 1.0, start + first / 10 + 4.0)}
                rids = {k: ingest.request_range(SERIAL, *sp, recording="1-card") for k, sp in spans.items()}
    finally:
        shutil.rmtree(path, ignore_errors=True)
    return start, last, first, answers, refused


def test_a_camera_without_an_rtc_that_reboots_for_longer_than_the_clock_step_backfills_nothing_off_by_the_reboot():
    """The twelfth review, blocker 12, its probes `pz3_rtcless_window` and `pz3b_told_before_set`: a camera with no RTC
    that reboots for R seconds goes on with its line right after the card's newest frame, so the ingest's one offset is R
    higher after the boot — right for the second boot's frames, wrong by R for the first boot's on the card. Asked between
    the boot and NTP, the first boot's hole came back as the frames captured R before it (R = 30: 90–120 s laid at
    120–150; R = 8: +8.1 s), and the reboot's gap with 340 frames off — and so for a camera whose clock is never set. While
    the line is adrift — a reboot put it on the card's newest by a guess (`CamLine.adrift`) — the camera refuses a range
    that reaches before where it went adrift (`CameraPusher._stale_range`): RANGE FAILED, never a wrong frame, and asked
    again after NTP it lands whole, every frame where it was captured. The second boot's own seconds, asked before NTP,
    land where they were captured by the second boot's offset. A camera whose clock is never set has the first boot's
    hole refused for as long as it stays unset — and nothing anywhere off by the reboot."""
    from vms.obsd import unix_s
    for R, ntp in ((30.0, 40.0), (8.0, 40.0), (30.0, None)):
        start, last, first, answers, refused = _rtcless(R, ntp)
        for k, frames in answers.items():
            off = [(_number(s), round(unix_s(s.begin) - (start + _number(s) / 10), 3)) for s in frames]
            assert off and all(abs(e) < 0.002 for _, e in off), (R, ntp, k, [o for o in off if abs(o[1]) >= 0.002][:3])
        assert all(first <= _number(s) < first + 40 for s in answers["boot2"]), (R, ntp)   # its own frames, before NTP
        assert refused.get("hole") and refused.get("reboot"), (R, ntp, refused)          # asked before NTP: refused
        if ntp is not None:
            assert [_number(s) for s in answers["hole"]] == list(range(1180, 1505)), (R, ntp)
            assert {last, first} <= {_number(s) for s in answers["reboot"]}, (R, ntp)    # both boots' edges, in place
        else:
            assert "hole" not in answers and "reboot" not in answers, (R, list(answers))


def test_a_range_told_before_the_cameras_clock_was_set_and_begun_after_it_fails_and_lands_where_captured_when_asked_again():
    """The sibling of blocker 12 the review did not name: the ingest goes on telling a range by the offset it was first
    told by, and the camera began it only after its clock was set and the line relabelled — the uplink was not free when
    it was told (`uplink_free`). Read on the moved line, it brought what lay where the range had been. A range told
    before the line moved is refused when it is begun (`CameraPusher._stale_range`), as one being answered fails at the
    move (`test_a_range_being_answered_when_the_cameras_clock_is_set_fails…`): asked again, it lands where captured."""
    from vms.obsd import unix_s
    wall = Clock(1_780_000_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    boot, rtc = wall(), [False]
    camclock = lambda: wall() if rtc[0] else wall() - boot                # 1970 and its uptime until NTP
    steady = lambda: wall() - boot
    path = tempfile.mkdtemp(prefix="card-")
    try:
        ring, card, act, pusher = _process(wall, path, camclock, steady, 1, lambda url: ingest, cam)
        free = [True]
        pusher.uplink_free = lambda: free[0]
        start, n, rid, outcome, again, answer, waited = wall(), 0, None, None, None, None, 0
        while wall() - start < 90:
            n = _sensor(ring, start, camclock, wall, n)
            act.drain()
            pusher.pass_once([])
            if rid is not None and outcome is None and not free[0]:
                waited += rid in ingest.cams[SERIAL].told_by and rid not in pusher.uploading   # told, not begun
            if rid is not None and outcome is None and free[0]:
                try:
                    outcome = ingest.result(SERIAL, rid)
                except RangeFailed as e:
                    outcome = e
                    again = ingest.request_range(SERIAL, start + 4.0, start + 20.0, recording="1-card")
            if again is not None and answer is None:
                answer = ingest.result(SERIAL, again)
            wall.advance(0.5)
            el = round(wall() - start, 1)
            if el == 30.0:
                free[0] = False                                             # the uplink is taken by the stream
                rid = ingest.request_range(SERIAL, start + 4.0, start + 20.0, recording="1-card")
            if el == 40.0:
                rtc[0] = True                                               # NTP sets the clock: the line moves
            if el == 50.0:
                free[0] = True
    finally:
        shutil.rmtree(path, ignore_errors=True)
    assert waited >= 10, waited
    assert isinstance(outcome, RangeFailed) and "moved after the range was told" in str(outcome), outcome
    assert [_number(s) for s in answer or []] == list(range(40, 200)), [_number(s) for s in answer or []][-3:]
    assert all(abs(unix_s(s.begin) - (start + _number(s) / 10)) < 0.002 for s in answer)


# -- the thirteenth review -------------------------------------------------------------------------------------------
def _two_reboots(ntp_after: float | None, down2: bool):
    """The thirteenth review's probe `pq1_two_reboots`, with a recorder's backfill beside it: a camera with no RTC battery,
    NTP 10 s into its first boot, the road down 120–180 s (a hole on its card); off at 300 s for 30 s, boot 2 runs 60 s
    with its clock never set (the road down all of it if `down2`: its frames on the card alone); off at 390 s for 30 s,
    boot 3 unset, NTP `ntp_after` s after it (None: never). Five seconds into boot 3 the recorder asks the first boot's
    hole and boot 2's own seconds; a range answered RANGE FAILED is asked again ten seconds later. Returns the answers,
    the refusals, what reached the recorder live and where, and the last pusher."""
    wall = Clock(1_780_000_000.0)
    fed, north, south, signer, ingest, cam, *_ = _site(wall)
    boot, rtc, down, on = [wall()], [False], [False], [True]
    camclock = lambda: wall() if rtc[0] else wall() - boot[0]             # 1970 and its uptime until NTP
    steady = lambda: wall() - boot[0]

    def dial(url):
        if down[0]:
            raise Unreachable("down")
        return ingest
    path, live = tempfile.mkdtemp(prefix="card-"), {}

    class Writer:
        def push(self, f):
            live.setdefault(_number(f["sample"]), f["t"])
    try:
        ring, card, act, pusher = _process(wall, path, camclock, steady, 1, dial, cam)
        ingest.want(SERIAL, "recorder:r")
        ingest.subscribe(SERIAL, "recorder:r")
        ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = Writer()
        start, n, rids, spans, answers, refused, retry = wall(), 0, {}, {}, {}, {}, {}
        while wall() - start < 420 + 120:
            el = round(wall() - start, 1)
            if on[0]:
                n = _sensor(ring, start, camclock, wall, n)
                act.drain()
                down[0] = 120 <= el < 180 or (down2 and 330 <= el < 390)
                pusher.pass_once([])
            for k, rid in list(rids.items()):
                try:
                    got = ingest.result(SERIAL, rid)
                except RangeFailed:
                    refused[k] = refused.get(k, 0) + 1
                    del rids[k]
                    retry[k] = el + 10.0
                    continue
                if got is not None:
                    answers[k] = got
                    del rids[k]
            for k in [k for k, at in retry.items() if el >= at]:
                del retry[k]
                rids[k] = ingest.request_range(SERIAL, *spans[k], recording="1-card")
            wall.advance(0.5)
            el = round(wall() - start, 1)
            if el == 10.0:
                rtc[0] = True                                               # the first boot's NTP
            if el in (300.0, 390.0):                                        # off for 30 s
                n = _sensor(ring, start, camclock, wall, n)
                act.stop_all()
                card.close()
                on[0] = False
            if el in (330.0, 420.0):                                        # …and back, its clock unset
                boot[0], rtc[0], on[0] = wall(), False, True
                n = int(round(el * 10))
                ring, card, act, pusher = _process(wall, path, camclock, steady, 2 if el < 400 else 3, dial, cam)
            if ntp_after is not None and el == 420.0 + ntp_after:
                n = _sensor(ring, start, camclock, wall, n)
                rtc[0] = True                                               # NTP sets the clock in boot 3
            if el == 425.0:
                spans = {"hole": (start + 118.0, start + 150.5), "boot2": (start + 330.0, start + 390.0)}
                rids = {k: ingest.request_range(SERIAL, *sp, recording="1-card") for k, sp in spans.items()}
    finally:
        shutil.rmtree(path, ignore_errors=True)
    return start, answers, refused, live, pusher


def test_a_camera_without_an_rtc_that_reboots_twice_before_ntp_answers_no_range_with_another_moments_frames():
    """The thirteenth review, blocker 7, its probe `pq1_two_reboots`: a second boot with the clock unset was told unset
    through the first unset boot's guess — a step back of its length — and lost `adrift`. Asked between boot 3 and NTP,
    the first boot's hole came back as the frames of 60–90 s (+60.2 s), and boot 2's own seconds as 600 frames 30.1 and
    60.2 s off; after NTP boot 2's frames lay 30.1 s early for good. Every unset boot is adrift now and the set clock
    places only the boot it is set in (`vms.card.CamLine`): before NTP both ranges are refused (RANGE FAILED, asked again);
    after it the hole lands whole, every frame where it was captured, and boot 2 — its clock never set, its road down —
    gives no frame at all: its frames have no capture time and are left out (`CameraPusher.unplaced_left`), never
    another moment's. With boot 2's road up, its frames reached the recorder live where they were captured. A camera
    whose clock is never set refuses both, every time."""
    from vms.obsd import unix_s
    for ntp, down2 in ((40.0, True), (40.0, False), (None, True)):
        start, answers, refused, live, pusher = _two_reboots(ntp, down2)
        case = (ntp, down2)
        for k, frames in answers.items():
            off = [(_number(s), round(unix_s(s.begin) - (start + _number(s) / 10), 3)) for s in frames]
            assert all(abs(e) < 0.002 for _, e in off), (case, k, [o for o in off if abs(o[1]) >= 0.002][:3])
        assert refused.get("hole") and refused.get("boot2"), (case, refused)          # asked before NTP: refused
        if ntp is None:
            assert answers == {}, (case, list(answers))
            continue
        assert [_number(s) for s in answers["hole"]] == list(range(1180, 1505)), case
        # (boot 2's frames lie where a guess put them, 300–360 s: the range reaches 330–360 of them, all left out)
        assert answers["boot2"] == [] and pusher.unplaced_left >= 290, (case, len(answers["boot2"]), pusher.unplaced_left)
        if not down2:                                                    # its road up: live, where captured
            two = {i: t for i, t in live.items() if 3300 <= i < 3900}
            assert len(two) >= 590 and all(abs(t - (start + i / 10)) < 0.002 for i, t in two.items()), (case, len(two))


def test_a_step_of_this_clusters_clock_inside_the_cameras_round_trip_is_taken_and_counted():
    """The thirteenth review, major 10, its probe `pq4_cluster_step_rtt`: this cluster's clock steps forward while the
    camera's road takes a steady 0.6 s there and back. A rise its round trip brought under `CLOCK_STEP` (5.5 − 0.6) was
    neither a provisional rise nor a small one, and no request ever said otherwise: every frame after it 5.5 s early,
    nothing counted; so a rise of 0.6 under `OFFSET_HOLD` + rtt, and a provisional rise the requests agreed with only "as
    their round trip explains". What the road explains now is what its round trip GREW BY since the least the camera
    said (`Ingest._offset`, `rtt_least`): a steady road explains nothing. Each zone is taken and counted — the step of
    5.5 provisionally and confirmed by the next requests, the small one after `OFFSET_RISE`, the provisional rise whose
    road grew under it after `OFFSET_RISE` (not at once: that one is a small rise) — and a plateau, whose round trip grew
    by all of the rise, is still nothing."""
    from domain.ingest import CLOCK_STEP, OFFSET_RISE

    def world():
        wall = Clock(100_000.0)
        *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
        return wall, ingest, pusher.entry()["ingest"]["token"]

    def polls(wall, ingest, token, seconds, behind, rtt, every=5.0):
        """The camera polls every `every` s for `seconds`: its clock `behind` the cluster's (its road's travel in it)."""
        out = []
        for _ in range(int(seconds / every)):
            ingest.poll(token, SERIAL, camera_now=wall() - behind, rtt=rtt)
            c = ingest.cams[SERIAL]
            out.append((round(c.offset, 2), c.provisional is not None))
            wall.advance(every)
        return out

    # (CLOCK_STEP, CLOCK_STEP + rtt]: the step of 5.5 on a road of 0.6 — provisional at once, confirmed by the next two
    wall, ingest, token = world()
    polls(wall, ingest, token, 60, 0.6, 0.6)
    seen = polls(wall, ingest, token, 60, 6.1, 0.6)
    c = ingest.cams[SERIAL]
    assert 5.5 - 0.6 <= CLOCK_STEP < 5.5 and seen[0] == (6.1, True) and seen[2] == (6.1, False), seen[:3]
    assert abs(c.offset - 6.1) < 0.01 and c.provisional is None and c.clock_steps == 1, (c.offset, c.clock_steps)
    # (OFFSET_HOLD, OFFSET_HOLD + rtt]: a step of 0.6 on the same road — a small rise, taken after `OFFSET_RISE`
    wall, ingest, token = world()
    polls(wall, ingest, token, 60, 0.6, 0.6)
    seen = polls(wall, ingest, token, 60, 1.2, 0.6)
    c = ingest.cams[SERIAL]
    assert seen[0] == (0.6, False) and seen[-1] == (1.2, False) and c.clock_steps == 1, seen
    assert sum(1 for o, _ in seen if o < 1.0) * 5.0 >= OFFSET_RISE, seen               # …not before `OFFSET_RISE`
    # a provisional rise whose road grew under it (5.5 − 0.55): confirmed as a small rise is, after `OFFSET_RISE`
    wall, ingest, token = world()
    polls(wall, ingest, token, 60, 0.05, 0.05)
    seen = polls(wall, ingest, token, 5, 5.55, 0.05) + polls(wall, ingest, token, 60, 5.55, 0.6)
    c = ingest.cams[SERIAL]
    assert seen[0] == (5.55, True) and seen[3][1] and not seen[-1][1] and c.clock_steps == 1, seen
    assert sum(1 for _, p in seen if p) * 5.0 >= OFFSET_RISE, seen
    # a plateau: the round trip grew by all of the rise — withdrawn at the next request, nothing counted
    wall, ingest, token = world()
    polls(wall, ingest, token, 60, 0.05, 0.05)
    seen = polls(wall, ingest, token, 5, 8.05, 0.05) + polls(wall, ingest, token, 60, 8.05, 8.05)
    c = ingest.cams[SERIAL]
    assert seen[0] == (8.05, True) and not seen[1][1] and c.clock_steps == 0 and c.provisional is None, seen
    assert (c.target if c.target is not None else c.offset) < 0.1, (c.offset, c.target)


def test_a_provisional_rise_a_plateau_of_travel_agrees_with_is_withdrawn_and_the_plateau_lies_where_captured():
    """The thirteenth review, a minor on the twelfth answer ("the first frames of a plateau land late" — understated): a
    provisional rise was held until the plateau ended, every request of it agreeing "as its round trip explains", and
    every frame of the plateau went to the recorder as late as the plateau's travel — 314 frames of 8 s for 20 s, 654 of
    6 s for a minute. A request agreeing with the rise only as far as its round trip grew withdraws it now
    (`Ingest._withdraw`, by the frames): the plateau lies where captured, no frame lost or repeated, no step counted."""
    for travel, dur in ((8.0, 20.0), (6.0, 60.0)):
        r = _road("plateau", travel, dur)
        assert not r["never"] and r["repeats"] == 0 and r["clock_steps"] == 0, (travel, dur, len(r["never"]))
        assert r["late_n"] <= 10, (travel, dur, r["late_n"])                # at most one request's frames


def test_the_ranges_a_camera_could_not_read_are_remembered_to_a_bound_and_all_of_them_counted():
    """The thirteenth review, a minor: `failed_ranges` kept every range the camera answered RANGE FAILED — about 144 a day
    for one hole while a camera's clock stays unset (asked again every ten minutes), for as long as the process lives. The
    last `FAILED_KEPT` are kept, with why, and every one is counted (`ranges_failed`)."""
    from domain.ingest import FAILED_KEPT
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall)          # no card: every range fails
    for i in range(FAILED_KEPT + 20):
        rid = ingest.request_range(SERIAL, wall() - 600 + i, wall() - 590 + i)
        pusher.pass_once([])
        try:
            ingest.result(SERIAL, rid)
            raise AssertionError("a camera with no card answered")
        except RangeFailed:
            pass
        wall.advance(1.0)
    assert len(pusher.failed_ranges) == FAILED_KEPT and pusher.ranges_failed == FAILED_KEPT + 20
    assert pusher.failed_ranges[-1][2] == "this camera has no card"

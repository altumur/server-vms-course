"""Feedback CB — a short break is closed from memory, and the card is not written.

A camera that pushes its stream and loses its road for seconds used to leave the break to its card and to
backfill: every Wi-Fi drop a card write and a backfill. Now every poll answer says how far the cluster's
recorder WROTE the camera (`have`), and the camera's next push starts at the first keyframe after it — out of
its memory, which holds what it SENT and may not have been written, and off its card for what memory no longer
holds. Nothing the recorder has goes twice.

The seventh review added three rules, each tested below: nothing of the stream's state moves until an ingest
TOOK a push (a push that fails loses nothing); the stream reaches back `hold_seconds` and leaves what is older to
backfill, saying how much; and it goes ahead of the live edge a piece a pass, so a pass still polls and answers."""
from vms.config import REC_SPEC
from w2cplatform.console import Heartbeat
from w2cplatform.domain.federation import Unreachable
from vms.domainpart.ingest import CameraPusher, written_from_heartbeats
from tests.domain.conftest import Clock, real_card
from tests.domainvms.test_lesson16_nobody_reaches import SERIAL, URLS, _site


def _frame(t):
    return {"t": float(t), "key": int(t) % 2 == 0}                     # a keyframe every two seconds


def _world(wall, card=None, clock=None, **kw):
    fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, _, domain_pass = _site(wall)
    down = set()

    def dial(url):
        if url not in URLS or url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest
    nothing = lambda recording, t0, t1, max_bytes: iter(())            # a card that holds nothing of the range
    pusher = CameraPusher(SERIAL, cam.flash, dial, card=card or nothing, clock=clock or wall, **kw)
    ingest.want(SERIAL, "recorder:r")
    rq = ingest.subscribe(SERIAL, "recorder:r", maxsize=1000)
    return south, ingest, pusher, rq, down


def _second(wall, pusher, n=1):
    for _ in range(n):
        wall.advance(1)
        pusher.pass_once([_frame(wall())])


def test_a_break_continues_after_what_the_recorder_wrote_and_nothing_goes_twice():
    """Pushing at t=1..5; the recorder WROTE up to 3 (4 and 5 were lost in its queue: it restarted, and subscribed
    anew). The road goes for six seconds. Back: the push starts at the first keyframe after 3 — 4, 5 again, then the
    break, then live."""
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 5)
    assert [f["t"] for f in rq.drain()] == [1, 2, 3, 4, 5]
    ingest.written = lambda ref: 3.0
    ingest.tees[(SERIAL, "live")].unsubscribe("recorder:r")            # the recorder restarted: its queue is gone
    rq = ingest.subscribe(SERIAL, "recorder:r", maxsize=1000)
    down.update(URLS)
    _second(wall, pusher, 6)                                           # t=6..11: nobody answers
    assert pusher.broken_at == 5.0
    down.clear()
    _second(wall, pusher)                                              # t=12: back
    got = rq.drain()
    assert [f["t"] for f in got] == [4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert all(f.get("ring") for f in got[:-1]) and not got[-1].get("ring")     # the continuation is not the live edge
    assert pusher.broken_at is None and pusher.resumed == 8


def test_what_the_recorder_has_is_dropped_at_the_ingest():
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 4); rq.drain()
    ingest.written = lambda ref: 7.0                                   # a recorder further on than the camera thinks
    down.update(URLS); _second(wall, pusher, 4); down.clear()
    _second(wall, pusher)
    assert [f["t"] for f in rq.drain()] == [8, 9]                     # nothing the recorder wrote, a keyframe first
    ingest.push(_token(ingest, pusher), SERIAL, [_frame(6), _frame(10)], camera_now=wall())   # a camera that cannot say
    assert [f["t"] for f in rq.drain()] == [10]                       # the ingest drops what was written all the same


def test_a_break_longer_than_the_stream_reaches_leaves_the_older_part_to_backfill_and_says_how_much():
    """The seventh review: a continuation is sent AHEAD of the live stream — the recorder's writer takes nothing older
    than its last frame — and ten minutes of it held the live edge back for five. So the stream reaches back no further
    than `hold_seconds`: fifty seconds without a road, and the stream goes on from the first keyframe thirty seconds
    back; the twenty before that the card wrote (its gate released it) and backfill takes off it. The pusher says how
    much it left (`continued["left_s"]`), and asks the card nothing: memory holds all the stream reaches."""
    wall = Clock(0.0)
    card, asked = real_card(0, 60), []

    def read(recording, t0, t1, max_bytes):
        asked.append((t0, t1))
        return card.pieces(recording, t0, t1, max_bytes)
    south, ingest, pusher, rq, down = _world(wall, card=read)
    _second(wall, pusher, 3); rq.drain()
    ingest.written = lambda ref: 3.0
    down.update(URLS); _second(wall, pusher, 50); down.clear()
    _second(wall, pusher)
    got = [f["t"] for f in rq.drain()]
    assert got == [float(t) for t in range(24, 55)] and asked == []   # from the first keyframe at 54 - 30
    assert pusher.continued["left_s"] == 21.0 and pusher.resumed == 30  # 3..24: backfill's


def _short_memory(pusher, frames: int):
    """The camera's memory holds fewer seconds than the stream reaches — the camera's ring at a high bitrate (32 MiB
    are 27 s at 10 Mbit/s): here `frames` frames of a kilobyte."""
    pusher.frames.max_bytes = frames * 1000


def _heavy(t):
    return {"t": float(t), "key": int(t) % 2 == 0, "body": b"x" * 1000}


def test_what_the_stream_reaches_and_memory_does_not_hold_comes_off_the_card_and_joins_memory_mid_gop():
    """Memory holds the last twenty seconds and the stream reaches back thirty: the ten between come off the REAL card
    (`Sample` records, turned into push frames by `wire`, the record riding along), from a keyframe; and where the
    card's part reaches memory, memory follows it in the middle of a group of pictures — every second once, in order."""
    from vms.obsd import archive_ms
    wall = Clock(0.0)
    card, asked = real_card(0, 60), []

    def read(recording, t0, t1, max_bytes):
        asked.append((t0, t1))
        return card.pieces(recording, t0, t1, max_bytes)
    south, ingest, pusher, rq, down = _world(wall, card=read)
    _short_memory(pusher, 20)
    for _ in range(3):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    rq.drain()
    ingest.written = lambda ref: 3.0
    down.update(URLS)
    for _ in range(50):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    down.clear()
    wall.advance(1); pusher.pass_once([_heavy(wall())])
    frames = rq.drain()
    got = [f["t"] for f in frames]
    assert [(round(a, 2), b) for a, b in asked] == [(24.0, 35.0)]    # from where the stream reaches to where memory begins
    assert got == [float(t) for t in range(24, 55)]                   # the card's part, then memory: 35 is a delta frame
    off_card = [f for f in frames if "sample" in f]
    assert [f["t"] for f in off_card] == [float(t) for t in range(24, 35)] and all(f["ring"] for f in off_card)
    assert all(f["sample"].begin == archive_ms(f["t"]) and f["sample"].key == f["key"] for f in off_card)


def test_a_card_that_holds_less_than_the_break_leaves_a_hole_and_the_stream_goes_on_from_a_keyframe():
    """The card's part and memory's part join in the middle of a group of pictures only when the card's part reaches
    memory. A card that has less — it was slow, it opened late — leaves a hole before memory, and after a hole the
    stream starts on a keyframe: the half-group after it could not be decoded. What is missing is backfill's."""
    wall = Clock(0.0)
    card = real_card(0, 30)                                            # the card stops at 30; memory begins at 35
    south, ingest, pusher, rq, down = _world(wall, card=card.pieces)
    _short_memory(pusher, 20)
    for _ in range(3):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    rq.drain()
    ingest.written = lambda ref: 3.0
    down.update(URLS)
    for _ in range(50):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    down.clear()
    wall.advance(1); pusher.pass_once([_heavy(wall())])
    got = [f["t"] for f in rq.drain()]
    assert got == [float(t) for t in range(24, 30)] + [float(t) for t in range(36, 55)]   # 35 is a delta frame: dropped


def test_a_hole_in_the_middle_of_the_cards_part_is_counted_and_the_stream_goes_on_from_a_keyframe_after_it():
    """The product's sibling of the eighth review: its live loop had no hole check, and the server took the frames after
    a hole as if they followed them. Off the card it was the same: a read checked only where it began, and a hole in
    the middle of the card's part — a queue the card's writer dropped, a hold that closed a segment — went into the
    stream unsaid. Every frame off the card must begin where the one before ended: after a hole the stream goes on from
    the next key frame, and the seconds are said (`failed_s`) — they are on no copy."""
    wall = Clock(0.0)
    card = real_card(28, 60, card=real_card(0, 25))                    # the card lost 25..28 (a key frame at 28)
    south, ingest, pusher, rq, down = _world(wall, card=card.pieces)
    _short_memory(pusher, 20)
    for _ in range(3):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    rq.drain()
    ingest.written = lambda ref: 3.0
    down.update(URLS)
    for _ in range(50):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    down.clear()
    wall.advance(1); out = pusher.pass_once([_heavy(wall())])
    got = [f["t"] for f in rq.drain()]
    assert got == [24.0] + [float(t) for t in range(28, 55)]            # 24, the hole, 28 on: every second after it once
    assert out["continue"]["failed_s"] == 3.0 and "hole" in out["continue"]["failed_why"]


def test_a_card_that_cannot_give_its_part_of_a_break_is_logged_counted_and_said_in_the_pushers_state():
    """The seventh review: `except OSError: reached = have` swallowed the card's error — two recordings on the card
    and a pusher not told which, and the part of the break that only the card held was neither sent nor said. Now
    the error is logged, counted (`continued["failed"]`), the seconds the card could not give and why are in the
    pusher's state and in what every pass returns, and the stream goes on from memory, from a keyframe."""
    import logging
    wall = Clock(0.0)
    card = real_card(0, 60)
    real_card(0, 60, recording="2-card", card=card)                    # two recordings, and the pusher names neither
    south, ingest, pusher, rq, down = _world(wall, card=card.pieces)
    _short_memory(pusher, 20)
    for _ in range(3):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    ingest.written = lambda ref: 3.0
    down.update(URLS)
    for _ in range(50):
        wall.advance(1); pusher.pass_once([_heavy(wall())])
    down.clear()
    said = []

    class Catch(logging.Handler):
        def emit(self, record):
            said.append(record.getMessage())
    catch = Catch()
    logging.getLogger("ingest").addHandler(catch)
    try:
        wall.advance(1); out = pusher.pass_once([_heavy(wall())])
    finally:
        logging.getLogger("ingest").removeHandler(catch)
    assert [f["t"] for f in rq.drain()][3:] == [float(t) for t in range(36, 55)]   # memory, from its first keyframe
    c = out["continue"]
    assert c["failed"] == 1 and c["failed_s"] == 11.0 and "names no recording" in c["failed_why"]
    assert pusher.continued == c and any("could not be continued off the card" in m for m in said)


def test_without_have_the_continuation_is_what_the_camera_kept():
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 3); rq.drain()
    down.update(URLS); _second(wall, pusher, 3); down.clear()
    _second(wall, pusher)
    assert pusher.resumed == 6                                         # an ingest that cannot say: all it kept went…
    assert [f["t"] for f in rq.drain()] == [4, 5, 6, 7]               # …and the recorder is given only what it had not had


def test_back_with_nobody_wanting_the_stream_continues_nothing():
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 3)
    down.update(URLS); _second(wall, pusher, 3)
    ingest.release(SERIAL, "recorder:r"); wall.advance(60)
    down.clear(); _second(wall, pusher)
    assert pusher.broken_at is None and pusher.cursor is None and pusher.pushing is None


def test_have_is_the_recorders_word_on_the_cameras_clock_whichever_ingest_it_reaches():
    """`have` comes from the recorders' heartbeats in the cluster's store — not from the ingest's memory — and
    is given on the CAMERA's clock: a camera a hundred seconds behind is told a hundred seconds less."""
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall, clock=lambda: wall() - 100)
    south.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", wall(), [{"id": SERIAL, "cam": f"ref:{SERIAL}",
                                                                       "written_through": 990.0}], {}).to_bytes())
    ingest.written = written_from_heartbeats(south.objects, wall)
    work = ingest.poll(_token(ingest, pusher), SERIAL, camera_now=wall() - 100)
    assert work["have"] == 890.0
    wall.advance(60)                                                   # the heartbeat went stale: nobody can say
    assert "have" not in ingest.poll(_token(ingest, pusher), SERIAL, camera_now=wall() - 100)
    # A `written_through` from the future is no word either (the ninth review's sibling): it would drop every frame.
    south.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", wall(), [{"id": SERIAL, "cam": f"ref:{SERIAL}",
                                                                       "written_through": 1e300}], {}).to_bytes())
    assert "have" not in ingest.poll(_token(ingest, pusher), SERIAL, camera_now=wall() - 100)


def _token(ingest, pusher):
    return pusher.entry()["ingest"]["token_secret"]


# -- the seventh review: nothing moves until an ingest took it; a break goes a piece at a time ------------------------
class _Writer:
    """The recorder's writer at the end of the pushed stream: it writes a frame only when it is newer than the last it
    wrote — as the real writer does — and keeps the times, never the bodies. Its last frame is the cluster's `have`."""

    def __init__(self, ingest):
        self.written, self.repeats, self.passes = [], 0, [[]]
        ingest.tees[(SERIAL, "live")].subscribers["recorder:r"] = self
        ingest.written = lambda ref: self.written[-1] if self.written else None

    def push(self, f):
        if self.written and f["t"] <= self.written[-1]:
            self.repeats += 1
            return
        self.written.append(f["t"])
        self.passes[-1].append(f)


def _flaky(ingest, pushes: int, answered: bool = False):
    """The next `pushes` pushes fail after a poll that answered: never arrived — or, `answered`, arrived and the answer
    to them was lost on the way back."""
    real, left = ingest.push, {"n": pushes}

    def push(*a, **kw):
        if left["n"] <= 0:
            return real(*a, **kw)
        left["n"] -= 1
        if answered:
            real(*a, **kw)
        raise Unreachable("the push's connection dropped")
    ingest.push = push


def test_a_push_that_fails_after_a_poll_that_answered_loses_nothing_of_the_break_it_was_continuing():
    """The seventh review, blocker 3, run as its probe ran it. Ten seconds without a road; the road comes back — the
    poll answers — and the push that continues the break fails. The pusher had cleared the break before that push,
    and `Unreachable`, which is not an `OSError`, left the pass on the way out: seconds 4 to 13 never arrived, while
    `resumed` counted them as sent. Now the break stands until an ingest TAKES its continuation; the next pass sends it,
    and every second reaches the writer once — whether the failed push never arrived or arrived with its answer lost."""
    for answered in (False, True):
        wall = Clock(0.0)
        south, ingest, pusher, rq, down = _world(wall)
        w = _Writer(ingest)
        _second(wall, pusher, 3)
        down.update(URLS); _second(wall, pusher, 10); down.clear()        # t=4..13: no road
        _flaky(ingest, 1, answered)
        _second(wall, pusher)                                             # t=14: the poll answers, the push fails
        assert pusher.broken_at == 3.0 and pusher.pushing is None and pusher.resumed == 0
        _second(wall, pusher)                                             # t=15: the road holds
        assert w.written == [float(t) for t in range(1, 16)] and pusher.broken_at is None
        assert pusher.resumed == (0 if answered else 11) and w.repeats == 0  # sent again only what the writer did not have


def test_an_ordinary_push_that_fails_loses_none_of_its_own_frames():
    """The sibling the review named: a push that failed with no break before it — its frames were never kept, the next
    pass kept what had been sent before them, and a whole group of pictures was gone. A failed push is a break of one
    pass now, and the next pass sends from the last frame an ingest took."""
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    w = _Writer(ingest)
    _second(wall, pusher, 3)
    _flaky(ingest, 1)
    _second(wall, pusher)                                                 # t=4: polled, and the push dropped
    assert w.written == [1.0, 2.0, 3.0] and pusher.sent == 3.0
    _second(wall, pusher, 2)
    assert w.written == [float(t) for t in range(1, 7)] and w.repeats == 0


BODY = b"\x80" * 400_000                                                  # 3.2 Mbit/s: a frame a second of 400 kB


def _fat(t):
    return {"t": float(t), "key": int(t) % 2 == 0, "body": BODY}


def test_a_break_is_continued_a_piece_a_pass_and_the_pass_still_polls_and_answers_asks():
    """The seventh review: the continuation went out whole inside one pass — no poll, no ask answered, no live frame
    for as long as the uplink took the backlog. Now a pass sends this pass's own frames and one piece (`PIECE_BYTES`)
    of the backlog on top: twenty seconds at 3.2 Mbit/s are eight passes, an ask filed in the middle is answered in the
    next pass, the live edge is never more than `hold_seconds` behind, and every second reaches the writer once."""
    from vms.card import PIECE_BYTES
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    pusher.perform = lambda action: "performed"
    w = _Writer(ingest)
    for _ in range(3):
        wall.advance(1); pusher.pass_once([_fat(wall())])
    down.update(URLS)
    for _ in range(20):
        wall.advance(1); pusher.pass_once([_fat(wall())])
    down.clear()
    passes, behind, answered = 0, [], []
    while True:
        w.passes.append([])
        if passes == 3:                                                   # an ask, filed while the stream catches up
            ingest._cam(SERIAL).asks["a1"] = {"action": {"preset": 3}, "deadline": wall() + 30, "by": "gate"}
            ingest._changed()
        wall.advance(1); out = pusher.pass_once([_fat(wall())])
        passes += 1
        answered += [(passes, a) for a in out["asks"]]
        behind.append(pusher.behind())
        assert sum(len(f["body"]) for f in w.passes[-1]) <= PIECE_BYTES + 2 * len(BODY)   # a piece, and this pass's own
        if not pusher.behind():
            break
        assert "catching up after a break" in pusher.state
    assert 6 <= passes <= 12 and max(behind) <= pusher.hold_seconds
    assert answered == [(4, ({"preset": 3}, "performed"))]               # in the pass after it was filed, mid-catch-up
    assert w.written == [float(t) for t in range(1, int(wall()) + 1)] and w.repeats == 0


def _uplink(ingest, wall, rate: float):
    """An uplink of `rate` bytes a second: a push takes as long as its bodies take, and the camera's clock goes on."""
    real = ingest.push

    def push(token, ref, frames, camera_now=None, **kw):
        took = real(token, ref, frames, camera_now=camera_now, **kw)  # (the clocks are compared as the push begins)
        wall.advance(sum(len(f.get("body") or b"") for f in frames) / rate)
        return took
    ingest.push = push


def _sensor(wall, last):
    """What the sensor captured since `last`, a frame a second, for one pass — and the newest it captured."""
    frames = [_fat(t) for t in range(int(last) + 1, int(wall()) + 1)]
    return frames, (frames[-1]["t"] if frames else last)


def test_at_the_assumed_uplink_a_break_is_caught_up_in_twice_its_length_and_below_the_stream_it_is_cut_and_said():
    """The review's question: what uplink does the camera assume for a continuation? One and a half times the stream's
    own bitrate: a backlog of B seconds is caught up in 2B, the stream gaining half a second a second. Twenty seconds
    of break at 4.8 Mbit/s of uplink for a 3.2 Mbit/s stream: caught up in about forty, every second written. Below
    the stream's own bitrate it never catches up: when it is `lag_limit` behind it goes on from the newest keyframe —
    or, sooner, memory lets go of what it had not sent — and the seconds it skipped are counted and logged: backfill's
    to take off the card, never silently lost."""
    for rate, catches_up, memory in ((1.5 * len(BODY), True, 0), (0.75 * len(BODY), False, 0),
                                     (0.75 * len(BODY), False, 120)):
        wall = Clock(0.0)
        south, ingest, pusher, rq, down = _world(wall)
        if memory:                                                        # memory longer than `lag_limit`: the cut is the pusher's
            pusher.frames.window = memory
        w, last = _Writer(ingest), 0.0
        for _ in range(3):
            wall.advance(1); frames, last = _sensor(wall, last); pusher.pass_once(frames)
        down.update(URLS)
        for _ in range(20):
            wall.advance(1); frames, last = _sensor(wall, last); pusher.pass_once(frames)
        down.clear()
        _uplink(ingest, wall, rate)
        back, lagged = wall(), False
        while wall() - back < 300:
            wall.advance(0.5); frames, last = _sensor(wall, last); pusher.pass_once(frames)
            lagged |= pusher.lag and pusher.uncovered is True and "the uplink does not carry the stream" in pusher.state
            if catches_up and not pusher.behind():
                break
        if catches_up:
            assert 30 <= wall() - back <= 50 and pusher.continued["cut_s"] == 0, wall() - back
            assert w.written == [float(t) for t in range(1, int(last) + 1)] and w.repeats == 0
        else:
            missing = set(float(t) for t in range(1, int(pusher.sent) + 1)) - set(w.written)   # (not what is still to go)
            assert missing and pusher.continued["cut_s"] >= len(missing)   # every second it skipped is counted
            assert pusher.behind() <= pusher.lag_limit and w.repeats == 0 and w.written == sorted(w.written)
            assert lagged                                              # …and it said so: lagging, the card told (the eighth review)


# -- the eighth review ---------------------------------------------------------------------------------------------------
def test_a_push_repeated_after_its_answer_was_lost_adds_nothing_even_with_have_five_seconds_old():
    """The eighth review, major, run as its probe ran it: every third push reaches the ingest and its answer is lost,
    and `have` — the recorder's word in its heartbeat — is five seconds old. Each lost answer is a break of one pass to
    the camera, and its continuation starts at `have`: five seconds the recorder has, sent again. The ingest dropped
    only what was not newer than `have`, and the rest went to the recorder — 53 repeats, out of order; the rule "the
    writer takes nothing older than its last" lived in the course's test writer alone. Now no subscriber of the ingest
    is given a frame not newer than the last it was given: the repeats are counted at the ingest and reach nobody."""
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    w = _Writer(ingest)
    ingest.written = lambda ref: w.written[-1] - 5.0 if w.written else None   # a heartbeat five seconds old
    real, calls = ingest.push, {"n": 0}

    def push(*a, **kw):
        calls["n"] += 1
        took = real(*a, **kw)
        if calls["n"] % 3 == 0:
            raise Unreachable("the answer to the push was lost")
        return took
    ingest.push = push
    _second(wall, pusher, 60)
    _second(wall, pusher, 2)                                              # (the last lost answer's frames, sent again)
    assert ingest.tees[(SERIAL, "live")].repeats > 50                     # the camera did send them again…
    assert w.repeats == 0 and w.written == [float(t) for t in range(1, int(wall()) + 1)]   # …and nobody got them twice
    # What the ingest did not hand on is said (the product's sibling: a full queue's refusals were counted nowhere).
    import json
    from vms.domainpart.ingest import POLLED
    ingest.push = real
    ingest.subscribe(SERIAL, "viewer:v", maxsize=2, edge=True)            # a viewer that does not read
    _second(wall, pusher, 5)
    lost = ingest.lost()[SERIAL]
    assert lost["repeats"] > 50 and lost["dropped"] == {"viewer:v": 3}
    ingest.publish_polled(south.objects)
    [key] = south.objects.list(POLLED + "/")
    assert json.loads(south.objects.get(key))["lost"][SERIAL] == lost


def test_a_camera_that_polls_an_ingest_that_restarted_is_answered_at_once_whatever_version_it_says():
    """The eighth review's sibling of the pull's number: the poll's `version` restarted at nought with the ingest too. A
    camera that had seen version 1 before the restart polled the new ingest with 1, the new ingest's first version was 1,
    and the poll was held as "nothing changed" — up to the whole wait — with a want waiting in the answer. Versions start
    at a number of the ingest's own boot now: one from before, or from another ingest of the road, is answered at once."""
    import time
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    token = _token(ingest, pusher)
    seen = ingest.poll(token, SERIAL, version=-1)["version"]
    from vms.domainpart.ingest import Ingest
    again = Ingest(ingest.cluster, ingest.urls, ingest.keys, wall=wall)    # the same ingest, restarted
    again.want(SERIAL, "recorder:r")
    began = time.monotonic()
    out = again.poll(token, SERIAL, version=seen, wait=2.0)
    assert time.monotonic() - began < 0.5 and not out.get("held") and out["push"] is True
    assert again.poll(token, SERIAL, version=out["version"]).get("held")    # (and its own version is still "nothing new")


def test_a_torn_book_entry_snapshot_shard_or_heartbeat_field_is_that_ones_trouble_and_the_camera_goes_on_pushing():
    """The eighth review's siblings, left in this module by the М12 pass: the camera's entry in its book of primaries,
    this cluster's rec snapshot shards (`should_from_snapshot`) and a recorder's `written_through` (`written_from_
    heartbeats`) were read bare — one torn entry raised out of the camera's whole pass, and one torn shard or field out
    of every poll at the ingest. Each is skipped and counted once (`BOOKS`, `FIELDS`), and what was read last of it is
    kept: the camera pushes on by the entry it read before, the ingest says what the shards it can read say."""
    import json
    from vms.domainpart.keys import PRIMARIES_PATH
    from vms.domainpart.ingest import BOOKS, should_from_snapshot
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 2)
    items, idx = pusher.flash.get(PRIMARIES_PATH)
    pusher.flash.put(PRIMARIES_PATH, {**items, SERIAL: '{"cluster": "south", "ingest": {"urls": '}, cas=idx)   # half a write
    _second(wall, pusher, 2)
    assert [f["t"] for f in rq.drain()] == [1001.0, 1002.0, 1003.0, 1004.0] and "pushing" in pusher.state
    assert f"{PRIMARIES_PATH}/{SERIAL}" in BOOKS.bad
    row = {"id": SERIAL, "cam": f"ref:{SERIAL}", "enabled": True}
    south.objects.put("rec/snapshot/a", json.dumps({"recordings": [row]}).encode())
    south.objects.put("rec/snapshot/b", b'{"recordings": [')
    south.objects.put("rec/snapshot/c", json.dumps({"recordings": [{**row, "id": "x", "until": "soon"}]}).encode())
    should = should_from_snapshot(south.objects, wall)
    assert should(SERIAL) is True and "rec/snapshot/b" in BOOKS.bad      # the shard it can read decides
    south.objects.put("rec/snapshot/a", b"[")                            # torn now: the shard as read last
    assert should(SERIAL) is True
    south.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", wall(), [
        {"id": SERIAL, "cam": f"ref:{SERIAL}", "written_through": "x"},
        {"id": "y", "cam": f"ref:{SERIAL}", "written_through": 990.0}], {}).to_bytes())
    ingest.written = written_from_heartbeats(south.objects, wall)
    assert ingest.poll(_token(ingest, pusher), SERIAL, camera_now=wall())["have"] == 990.0   # the field that is a number


# -- the ninth review ----------------------------------------------------------------------------------------------------
def test_a_model_camera_whose_clock_steps_back_pushes_every_frame_and_says_the_step():
    """The ninth review's blocker on the pusher that keeps its own frames (the course's model camera, no ring): a frame
    not newer than the one before it was "stale" there, and not taken — a clock that stepped back thirty seconds lost
    the thirty seconds after it, counted in a field nobody read. Now the pusher's frames are on one line of time as the
    camera's ring keeps it: every frame reaches the recorder once, on the cluster's clock where it was captured, the
    step is said in the pusher's word (`clock_back_s`), and the ingest's offset does not move."""
    wall = Clock(0.0)
    skew = [0.0]
    camclock = lambda: wall() + skew[0]
    south, ingest, pusher, rq, down = _world(wall, clock=camclock)
    for i in range(1, 121):
        if i == 61:
            skew[0] -= 30.0                                               # the camera's clock steps back here
        wall.advance(1)
        pusher.pass_once([_frame(camclock())])
    got = [f["t"] for f in rq.drain()]
    assert got == [float(t) for t in range(1, 121)]                       # every frame, once, where it was captured
    assert pusher.said()["clock_back_s"] == 30.0 and ingest.cams[SERIAL].clock_steps == 0


def test_a_frame_with_an_absurd_time_is_refused_and_counted_and_the_frames_after_it_reach_the_recorder():
    """The ninth review, major, run as its probe ran it: a camera with a valid token sends one frame stamped `t = 1e300`
    (or `"1e400"`): it became the recorder's last frame, and 250 of 250 frames after it were dropped as repeats until the
    recorder subscribed anew — seen only in `repeats`. A frame later than the ingest's clock by more than `FRAME_AHEAD`,
    or whose time is no finite number, is refused now, counted (`ahead`, under `lost`), and never anybody's last frame;
    a frame of an hour ahead too. The same at the other doors into the tees, which the review did not name: what this
    cluster's forwarder injects, and what a peer ingest hands on."""
    from vms.domainpart.ingest import FRAME_AHEAD, Ingest, PeerLink
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall)
    token = _token(ingest, pusher)
    bad = [{"t": 1e300, "key": True}, {"t": "1e400", "key": True}, {"t": "ten", "key": True}, {"t": float("nan")},
           {"t": wall() + FRAME_AHEAD + 3600, "key": True}]
    for f in bad:
        ingest.push(token, SERIAL, [f, _frame(wall())], camera_now=wall())
        wall.advance(1)
    for _ in range(250):
        ingest.push(token, SERIAL, [_frame(wall())], camera_now=wall())
        wall.advance(1)
    got = [f["t"] for f in rq.drain()]
    assert len(got) == len(bad) + 250 and got == sorted(got)               # every good frame, none of the bad
    assert ingest.lost()[SERIAL]["ahead"] == len(bad) and "repeats" not in ingest.lost()[SERIAL]
    ingest.inject(SERIAL, [{"t": 1e300, "key": True}, _frame(wall())])     # this cluster's forwarder…
    peer = Ingest("south", ["srt://srv-2.south:9000"], keys=lambda: {}, wall=wall)
    pq = peer.subscribe(SERIAL, "recorder:p", maxsize=1000)
    wall.advance(1)
    PeerLink(peer, SERIAL).send([{"t": 1e300, "key": True}, _frame(wall())])   # …and a peer ingest's stream
    assert [f["t"] for f in rq.drain()] == [wall() - 1] and [f["t"] for f in pq.drain()] == [wall()]
    assert ingest.lost()[SERIAL]["ahead"] == len(bad) + 1 and peer.lost()[SERIAL]["ahead"] == 1


# -- the tenth review -----------------------------------------------------------------------------------------------------
def _forward_step(steady: bool):
    """The tenth review's probe `pl2_steps`: ten frames a second for 90 s; the road goes at 30 s, the camera's clock steps
    forward thirty seconds at 60.2 and the road is back at 60.4. `steady`: the camera has its steady clock (a camera's
    `time.monotonic`; here the cluster's, which is the true one)."""
    wall, skew = Clock(0.0), [0.0]
    camclock = lambda: wall() + skew[0]
    south, ingest, pusher, rq, down = _world(wall, clock=camclock, steady=wall if steady else None, hold_seconds=40.0)
    w = _Writer(ingest)
    for n in range(1, 901):
        wall.t = n / 10
        if n == 300:
            down.update(URLS)
        if n == 602:
            skew[0] += 30.0                                               # the camera's clock steps forward here
        if n == 604:
            down.clear()
        pusher.pass_once([{"t": camclock(), "key": n % 20 == 0, "n": n}])
    return ingest, pusher, w


def test_a_camera_clock_that_steps_forward_in_a_break_loses_no_second_of_it_and_puts_no_frame_at_a_wrong_time():
    """The tenth review, blocker, run as its probe ran it. The camera's line of time took up a step BACK; a step forward
    it left to the frames ("it looks like a pause"), and the camera stated its clock thirty seconds later: the ingest's
    offset moved by thirty, and the recorder's `have`, moved onto the camera's clock by the new offset, stood thirty
    seconds past what the recorder had — the camera went on from there, and 30.2 s of the break were on no copy, with
    `left_s` nought and nothing counted. Now the camera tells a step from a pause by its steady clock (`CamLine`) and
    takes the step forward up on its line as it takes one back: every frame of the 90 s reaches the recorder once, on
    the cluster's clock where it was captured, the step is said (`clock_forward_s`), and the ingest's offset does not
    move. Without a steady clock the step is the old gap — and the review's loss."""
    ingest, pusher, w = _forward_step(steady=True)
    got = [(f["n"], f["t"]) for f in w.passes[0]]
    assert [n for n, _ in got] == list(range(1, 901)) and w.repeats == 0           # every frame, once, in order
    assert all(abs(t - n / 10) < 1e-6 for n, t in got)                              # …where it was captured
    assert pusher.said()["clock_forward_s"] == 30.0 and pusher.continued["left_s"] == 0.0
    assert ingest.cams[SERIAL].clock_steps == 0
    ingest, pusher, w = _forward_step(steady=False)                                 # no steady clock: the review's run
    assert 900 - len(w.passes[0]) >= 300 and ingest.cams[SERIAL].clock_steps == 1


def test_the_cameras_offset_is_held_through_the_travel_of_its_requests_and_moves_only_when_its_clock_does():
    """Feedback DU — the product's, found on a real engine — checked in the course by the ninth review's answer: the
    ingest measured the camera's offset anew on every request, a request's travel in it, so the first frame of a request
    landed a few milliseconds before the last one written (the engine refuses it) or after it (a hole). It is held now:
    two hundred requests whose travel is 0–200 ms put a thousand frames on the cluster's clock 20 ms apart, every one, none
    twice; one request a second on its way moves nothing. A camera clock found AHEAD by more than `OFFSET_HOLD` moves the
    offset at once (no request arrives before it was sent); one found BEHIND moves it only when every request for
    `OFFSET_RISE` says so. Each move is counted (`clock_steps`)."""
    import random
    from vms.domainpart.ingest import OFFSET_RISE
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall)
    token, w, rnd, n, true = _token(ingest, pusher), _Writer(ingest), random.Random(16), [0], [1000.0]

    def request(travel, camera=0.0):                                     # five frames of the last tenth of a second
        true[0] += 0.1
        frames = []
        for k in range(5):
            n[0] += 1
            frames.append({"t": true[0] - 0.08 + k * 0.02 + camera, "key": n[0] % 25 == 1, "n": n[0]})
        wall.t = true[0] + travel                                        # the ingest's clock as the request arrives
        ingest.push(token, SERIAL, frames, camera_now=true[0] + camera)
    for _ in range(200):
        request(rnd.uniform(0.0, 0.2))
    t = w.written
    assert len(t) == 1000 and w.repeats == 0 and ingest.cams[SERIAL].clock_steps == 0
    assert all(abs((b - a) - 0.02) < 1e-6 for a, b in zip(t, t[1:]))     # one offset: nothing early, no hole
    request(1.0)                                                         # a request a second on its way
    request(0.1)
    assert ingest.cams[SERIAL].clock_steps == 0 and len(w.written) == 1010
    assert all(abs((b - a) - 0.02) < 1e-6 for a, b in zip(w.written[-11:], w.written[-10:]))
    request(0.1, camera=3.0)                                             # its clock is found three seconds ahead
    assert ingest.cams[SERIAL].clock_steps == 1
    for _ in range(int(OFFSET_RISE / 0.1) - 5):
        request(0.1, camera=2.5)                                         # …and then half a second behind that
    assert ingest.cams[SERIAL].clock_steps == 1                          # not yet: it could be the requests' travel
    for _ in range(10):
        request(0.1, camera=2.5)
    assert ingest.cams[SERIAL].clock_steps == 2                          # every request for `OFFSET_RISE` said so


def test_one_frame_far_past_the_stream_silences_no_recorder_at_any_door():
    """The tenth review, major, run as its probe ran it: a frame stamped inside the bound of its door but far past the
    stream — now+59 inside `FRAME_AHEAD`, now+9 — became the subscriber's last frame, and the frames after it were
    dropped as repeats: 1 of 251 reached the recorder, 26 of 251 — at the camera's door, the forwarder's and a peer's.
    A camera's own frame is held to its own clock now (`CAMERA_AHEAD`), and in the tee a frame further past the stream
    than `STREAM_JUMP` is the stream's only when the frame after it follows it: 251 of 251 at every door, the stray
    frame counted (`ahead`). A stream that truly jumps — a push begun again after a pause — loses nothing."""
    from vms.domainpart.ingest import Ingest, PeerLink
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall)
    token = _token(ingest, pusher)
    peer = Ingest("south", ["srt://srv-2.south:9000"], keys=lambda: {}, wall=wall)
    pq, link = peer.subscribe(SERIAL, "recorder:p", maxsize=1000), PeerLink(peer, SERIAL)
    doors = [("push", lambda fs: ingest.push(token, SERIAL, fs, camera_now=wall()), rq, ingest),
             ("inject", lambda fs: ingest.inject(SERIAL, fs), rq, ingest), ("relay", link.send, pq, peer)]
    for ahead in (59.0, 9.0):
        for door, send, q, at in doors:
            before, got, good = at.lost().get(SERIAL, {}).get("ahead", 0), [], []
            for i in range(251):
                wall.advance(0.2)
                good.append(wall())
                send([_frame(wall())] + ([{"t": wall() + ahead, "key": True}] if i == 1 else []))
                got += [f["t"] for f in q.drain()]
            assert got == good, (door, ahead, len(got))                  # every frame of the stream, none of the stray
            assert at.lost()[SERIAL]["ahead"] == before + 1, (door, ahead)
    wall.advance(20.0)                                                   # the camera pushes again after a pause
    pushed = []
    for _ in range(5):
        wall.advance(0.2)
        pushed.append(wall())
        doors[0][1]([_frame(wall())])
    assert [f["t"] for f in rq.drain()] == pushed


# -- the eleventh review -------------------------------------------------------------------------------------------------
def test_a_sparse_stream_reaches_the_recorder_whole_and_at_once_at_every_door():
    """The eleventh review, major, a regression of the tenth's far-ahead hold, its probe `pr5_sparse`: one frame every 11,
    15 or 60 s — a time-lapse, a snapshot camera, frames on an event — was "far past the stream" every time, held, and
    failed by the frame after it, as far again: 1 of 40 reached the recorder (`ahead` 38) at the camera's door, the
    forwarder's and a peer's. Only a frame later than the ingest's own clock is held now (`_InOrder`): forty frames 11 to
    60 s apart reach the recorder, every one, each the moment it arrives — and the stray frame from the future the hold
    is there for is still held and dropped (`test_one_frame_far_past_the_stream_silences_no_recorder_at_any_door`)."""
    import random
    from vms.domainpart.ingest import Ingest, PeerLink
    rnd = random.Random(11)
    for door in ("push", "inject", "relay"):
        wall = Clock(1000.0)
        south, ingest, pusher, rq, down = _world(wall)
        token = _token(ingest, pusher)
        peer = Ingest("south", ["srt://srv-2.south:9000"], keys=lambda: {}, wall=wall)
        pq, link = peer.subscribe(SERIAL, "recorder:p", maxsize=1000), PeerLink(peer, SERIAL)
        send, q = {"push": (lambda fs: ingest.push(token, SERIAL, fs, camera_now=wall()), rq),
                   "inject": (lambda fs: ingest.inject(SERIAL, fs), rq), "relay": (link.send, pq)}[door]
        at_once = 0
        for i in range(40):
            wall.advance(rnd.uniform(11.0, 60.0))
            send([{"t": wall(), "key": True}])
            at_once += [f["t"] for f in q.drain()] == [wall()]
        assert at_once == 40, (door, at_once)                            # every frame, the moment it came
        assert not (ingest if door != "relay" else peer).lost(), door


def test_a_camera_clock_that_runs_fast_or_a_first_request_that_travelled_long_loses_no_frame_when_the_offset_comes_down():
    """The eleventh review, major ("a move of the offset down at once sends the frames after it to `repeats`"), with the
    product's cross-check beside it ("an open stream keeps the offset it opened with"): a camera clock 0.5 % fast moves
    its offset down 5 ms a second, past `OFFSET_HOLD` every fifty seconds — taken at once, the next frames landed a
    quarter of a second earlier than the last ones written, and every subscriber dropped them as not newer (4 frames in
    the probe); a first request that travelled two seconds (TLS, a cold uplink) put the offset two seconds high, and the
    next quick request took two seconds of frames to `repeats`. A move down is a target the open stream slews to now
    (`OFFSET_SLEW`, `_slewed`): two minutes of the fast clock and the slow first request each put every frame at the
    recorder once, in order, never further from where it was captured than the hold and the slew allow — and the open
    stream takes every correction: the drift stays within the hold, it does not grow with the stream."""
    import random
    from vms.domainpart.ingest import OFFSET_HOLD
    for case in ("fast clock", "slow first request"):
        wall = Clock(1000.0)
        south, ingest, pusher, rq, down = _world(wall)
        token, w, rnd, n = _token(ingest, pusher), _Writer(ingest), random.Random(17), [0]
        rate = 0.005 if case == "fast clock" else 0.0
        cam = lambda t: t + rate * (t - 1000.0)                           # the camera's clock, on the true one
        true, captured = 1000.0, {}
        for k in range(1200):                                            # two minutes, a request a tenth of a second
            frames = []
            for j in range(5):
                n[0] += 1
                t = true - 0.08 + j * 0.02
                captured[n[0]] = t
                frames.append({"t": cam(t), "key": n[0] % 25 == 1, "n": n[0]})
            travel = 2.0 if (case == "slow first request" and k == 0) else rnd.uniform(0.0, 0.05)
            wall.t = true + travel
            ingest.push(token, SERIAL, frames, camera_now=cam(true))
            true += 0.1
        got = [f["n"] for f in w.passes[0]]
        assert got == list(range(1, 6001)) and w.repeats == 0, (case, len(got), w.repeats)   # every frame, once, in order
        errors = [f["t"] - captured[f["n"]] for f in w.passes[0]]
        late = 2.0 if case == "slow first request" else OFFSET_HOLD + 0.05
        assert max(abs(e) for e in errors) <= late + 0.01, (case, max(errors), min(errors))
        assert max(abs(e) for e in errors[-500:]) <= OFFSET_HOLD + 0.05, case          # …and it does not grow
        assert ingest.cams[SERIAL].clock_steps >= 1, case


# -- the product's DZ, checked in the course --------------------------------------------------------------------------
def _travelled(delay, line: bool, seconds: float = 180.0):
    """A camera pushing ten frames a second (`line`: the course's pusher, its clock on its line; not: a camera that states
    its raw clock and stamps its frames by it, fifty a second, its own requests) whose every request — poll, push, upload
    — takes `delay(name, t) -> (there, back)`: the ingest's clock moves on by `there` before the request is served and by
    `back` before the camera hears the answer. Returns the ingest and the writer, and when each frame was captured."""
    wall = Clock(1000.0)
    south, ingest, pusher, rq, down = _world(wall)
    w, captured, n, last = _Writer(ingest), {}, 0, wall()
    if line:
        real = pusher.dial

        class Slow:
            def __init__(self, ing):
                self.ing = ing

            def __getattr__(self, name):
                fn = getattr(self.ing, name)
                if name not in ("poll", "push", "upload", "answer_ask"):
                    return fn

                def call(*a, **kw):
                    there, back = delay(name, wall() - 1000)
                    wall.advance(there)
                    try:
                        return fn(*a, **kw)
                    finally:
                        wall.advance(back)
                return call
        pusher.dial = lambda url: Slow(real(url))
        while wall() < 1000 + seconds:
            frames = []
            while last + 0.1 <= wall():
                last, n = last + 0.1, n + 1
                captured[n] = last
                frames.append({"t": last, "key": n % 20 == 1, "n": n})
            pusher.pass_once(frames)
            wall.advance(0.1)
        return ingest, w, captured
    token, k, pending = _token(ingest, pusher), 0, []
    while wall() < 1000 + seconds:
        while last + 0.02 <= wall():
            last, n = last + 0.02, n + 1
            captured[n] = last
            pending.append({"t": last, "key": n % 25 == 1, "n": n})
        name, sent = ("poll" if k % 10 == 0 else "push"), wall()
        there, back = delay(name, sent - 1000)
        wall.advance(there)
        if name == "poll":
            ingest.poll(token, SERIAL, camera_now=sent)
        else:
            ingest.push(token, SERIAL, pending, camera_now=sent)
            pending = []
        wall.advance(back + 0.1)
        k += 1
    return ingest, w, captured


def test_a_request_that_travelled_long_is_not_a_step_of_the_cameras_clock_and_loses_no_frame():
    """The product's DZ ("a network delay of 1–3 s gave false steps of the camera's clock back"), checked in the course by
    measurement. Bursts of 1–3 s on every request, both ways, shorter than `OFFSET_RISE`, moved nothing here before either:
    a rise waits for every request of half a minute. But ONE request that took longer than `CLOCK_STEP` on its way was a
    move up taken at once: its frames landed that much late, the next quick request took the offset back down at once, and
    the frames of the seconds after it were not newer than `have` — dropped, counted nowhere (a push of 5.5 s: 54 of 1800
    frames, 2 `clock_steps`; of 40 s: 399). A rise past `CLOCK_STEP` is taken PROVISIONALLY now (`provisional`, the
    product's rule): the next requests on the old clock withdraw it by the frames, slewed, never a jump. A poll or a push of
    5.5 to 40 s on its way, the camera on its line or stating its raw clock: no step counted, every frame once and in order;
    a slow poll put no frame by it — every frame where captured; a slow push's frames are at most its travel late, and for
    about twice its travel (40 s: the frames of the stall pressed below `CAMERA_AHEAD`, none refused). And a first pass
    whose requests all travelled eight seconds — its frames put eight seconds late — is slewed back (`_firm`): none lost."""
    import random

    def once(d, kind):
        rnd, done = random.Random(2), [False]

        def delay(name, t):
            x = rnd.uniform(0.0, 0.05)
            if name == kind and not done[0] and t > 60.0:
                done[0], x = True, d
            return x, 0.0                                              # all of it on the way there: what moves the offset
        return delay

    def burst(a, b):
        rnd = random.Random(1)

        def delay(name, t):
            d = rnd.uniform(1.0, 3.0) if a <= t < b else rnd.uniform(0.0, 0.05)
            return d / 2, d / 2
        return delay
    for line in (True, False):
        for kind, d in (("push", 5.5), ("push", 12.0), ("push", 40.0), ("poll", 12.0)):
            ingest, w, captured = _travelled(once(d, kind), line)
            got = [f["n"] for f in w.passes[0]]
            assert ingest.cams[SERIAL].clock_steps == 0, (line, kind, d)
            assert got == sorted(set(got)) and w.repeats == 0, (line, kind, d)
            # (a stall of 40 s outruns the pusher's memory: what it cut is said in `cut_s` — the card's and backfill's)
            assert (line and d == 40.0) or got == list(range(1, max(got) + 1)), (line, kind, d, max(got) - len(got))
            late = [(captured[f["n"]], f["t"] - captured[f["n"]]) for f in w.passes[0] if abs(f["t"] - captured[f["n"]]) >= 0.06]
            if kind == "poll":
                assert not late, (line, d, late[:3])
            else:
                assert all(0 < e <= d + 0.06 for _, e in late), (line, d, min(e for _, e in late))   # late, never early
                assert late[-1][0] - late[0][0] <= 2 * d + 1.0, (line, d, late[-1][0] - late[0][0])
            assert not ingest.lost().get(SERIAL, {}).get("ahead"), (line, kind, d)
        ingest, w, captured = _travelled(burst(60.0, 85.0), line)          # 25 s of 1–3 s, both ways
        assert ingest.cams[SERIAL].clock_steps == 0 and w.repeats == 0, line
        assert max(abs(f["t"] - captured[f["n"]]) for f in w.passes[0]) < 0.06, line
        ingest, w, captured = _travelled(lambda name, t: (8.0, 0.0) if t < 16.5 else (0.01, 0.0), line, 120.0)
        got = [f["n"] for f in w.passes[0]]
        assert got == list(range(1, max(got) + 1)) and w.repeats == 0, (line, max(got) - len(got))
        assert ingest.cams[SERIAL].clock_steps == 1, line                  # the first pass's travel, slewed back


# -- the twelfth review ----------------------------------------------------------------------------------------------
def test_a_plateau_of_travel_under_the_clock_step_for_longer_than_the_rise_wait_moves_no_offset():
    """The sibling of the twelfth review's blocker 13 below `CLOCK_STEP`: two seconds on every request for a minute — longer
    than `OFFSET_RISE` — was, by the requests' times, this cluster's clock stepped forward: the offset moved up by the
    least delay, the frames of the plateau's second half lay two seconds late, and a step was counted (the course named it
    as what stays). The camera says its round trip with every request now, and a rise its round trip explains counts for
    nothing (`Ingest._offset`): the camera on its line, no step, every frame once and where it was captured. A camera that
    states no round trip (its raw clock, its own requests) is held as before."""
    import random
    rnd = random.Random(12)

    def plateau(name, t):
        return (2.0, 0.0) if 60.0 <= t < 120.0 else (rnd.uniform(0.0, 0.05), 0.0)
    ingest, w, captured = _travelled(plateau, True)
    got = [f["n"] for f in w.passes[0]]
    assert got == list(range(1, max(got) + 1)) and w.repeats == 0
    assert ingest.cams[SERIAL].clock_steps == 0
    assert max(abs(f["t"] - captured[f["n"]]) for f in w.passes[0]) < 0.06
    ingest, w, captured = _travelled(plateau, False)                   # no round trip said: by the requests' times
    assert ingest.cams[SERIAL].clock_steps >= 1

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
from domain.federation import Unreachable
from domain.ingest import CameraPusher, written_from_heartbeats
from tests.conftest import Clock, real_card
from tests.test_lesson16_nobody_reaches import SERIAL, URLS, _site


def _frame(t):
    return {"t": float(t), "key": int(t) % 2 == 0}                     # a keyframe every two seconds


def _world(wall, card=None, clock=None):
    fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, _, domain_pass = _site(wall)
    down = set()

    def dial(url):
        if url not in URLS or url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest
    nothing = lambda recording, t0, t1, max_bytes: iter(())            # a card that holds nothing of the range
    pusher = CameraPusher(SERIAL, cam.flash, dial, card=card or nothing, clock=clock or wall)
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
    from w2cplatform.obsd import archive_ms
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


def _token(ingest, pusher):
    return pusher.entry()["ingest"]["token"]


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

    def push(token, ref, frames, camera_now=None):
        took = real(token, ref, frames, camera_now=camera_now)        # (the clocks are compared as the push begins)
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
    from domain.ingest import POLLED
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
    from domain.ingest import Ingest
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
    from domain.agent import PRIMARIES_PATH
    from domain.ingest import BOOKS, should_from_snapshot
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

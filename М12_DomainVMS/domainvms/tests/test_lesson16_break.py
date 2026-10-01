"""Feedback CB — a short break is closed from memory, and the card is not written.

A camera that pushes its stream and loses its road for seconds used to leave the break to its card and to
backfill: every Wi-Fi drop a card write and a backfill. Now every poll answer says how far the cluster's
recorder WROTE the camera (`have`), and the camera's next push starts at the first keyframe after it — off
its card, then out of what it kept through the break, which begins with what it had SENT and may not have
been written. Nothing the recorder has goes twice."""
from vms.config import REC_SPEC
from w2cplatform.console import Heartbeat
from domain.federation import Unreachable
from domain.ingest import CameraPusher, written_from_heartbeats
from tests.conftest import Clock
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
    pusher = CameraPusher(SERIAL, cam.flash, dial, card=card or (lambda t0, t1: []), clock=clock or wall)
    ingest.want(SERIAL, "recorder:r")
    rq = ingest.subscribe(SERIAL, "recorder:r", maxsize=1000)
    return south, ingest, pusher, rq, down


def _second(wall, pusher, n=1):
    for _ in range(n):
        wall.advance(1)
        pusher.pass_once([_frame(wall())])


def test_a_break_continues_after_what_the_recorder_wrote_and_nothing_goes_twice():
    """Pushing at t=1..5; the recorder WROTE up to 3 (4 and 5 were lost in its queue). The road goes for six
    seconds. Back: the push starts at the first keyframe after 3 — 4, 5 again, then the break, then live."""
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 5)
    assert [f["t"] for f in rq.drain()] == [1, 2, 3, 4, 5]
    ingest.written = lambda ref: 3.0
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


def test_a_long_break_is_read_back_off_the_card():
    """Fifty seconds without a road: the camera keeps thirty in memory; the card wrote the rest (its gate
    released it), and the continuation reads it off the card from the first keyframe after `have`."""
    wall = Clock(0.0)
    asked = []

    def card(t0, t1):
        asked.append((t0, t1))
        return [_frame(t) for t in range(int(t0), int(t1))]
    south, ingest, pusher, rq, down = _world(wall, card=card)
    _second(wall, pusher, 3); rq.drain()
    ingest.written = lambda ref: 3.0
    down.update(URLS); _second(wall, pusher, 50); down.clear()
    _second(wall, pusher)
    got = [f["t"] for f in rq.drain()]
    assert asked and asked[0][0] == 3.0
    assert got[0] == 4 and got == sorted(set(got)) and got[-1] == 54  # from the card, then memory, then live, once each


def test_without_have_the_continuation_is_what_the_camera_kept():
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 3); rq.drain()
    down.update(URLS); _second(wall, pusher, 3); down.clear()
    _second(wall, pusher)
    assert [f["t"] for f in rq.drain()] == [1, 2, 3, 4, 5, 6, 7]      # an ingest that cannot say: all it kept


def test_back_with_nobody_wanting_the_stream_continues_nothing():
    wall = Clock(0.0)
    south, ingest, pusher, rq, down = _world(wall)
    _second(wall, pusher, 3)
    down.update(URLS); _second(wall, pusher, 3)
    ingest.release(SERIAL, "recorder:r"); wall.advance(60)
    down.clear(); _second(wall, pusher)
    assert pusher.broken_at is None and pusher.tail == []


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

"""Lesson 16 — the camera's card is read by asking the camera, and a camera without a card is a camera all the same.

The card is the camera's buffer of plain files, written from the camera's one ring with no archive engine on the
camera (`vms/card.py`; the product's camera, feedback CB, DG, DH). Nobody can open a door to a camera that pushes,
and there is no door: the recorder asks for a range, the camera uploads it in answer to its poll. What the card could
not read — no card at all, a card that would not open, a segment read short — is answered RANGE FAILED: the
recorder's copy fails and its backfill asks again later. An empty answer would say "not on the card", for good.
"""
import tempfile
import threading

from domain.ingest import CameraPusher, RangeFailed, card_range
from tests.conftest import Clock
from tests.test_lesson16_nobody_reaches import SERIAL, _site


def _card(t0, t1):
    """A real card — the camera's buffer, no engine — holding `[t0, t1)` of recording `1-card`."""
    from vms.card import CardBuffer
    from vms.worker import fake_samples
    card = CardBuffer(tempfile.mkdtemp(prefix="card-"))
    for s in fake_samples(t0, t1, step=1.0, gop=2.0):
        card.append("1-card/e1", s)
    return card


def test_the_camera_answers_a_range_off_its_card_with_the_cards_own_frames_on_the_clusters_clock():
    """The recorder asks on the cluster's clock; the camera — its clock ninety seconds fast — reads its card on its
    own and answers with the card's sample records, from a key frame; they come back on the cluster's clock."""
    from w2cplatform.obsd import unix_s
    wall = Clock(100_000.0)
    fast = Clock(wall() + 90)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(fast() - 1000, fast())
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=fast,
                          card=lambda t0, t1: card.range("1-card", t0, t1))
    pusher.pass_once([])                                               # the camera states its clock
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
    assert pusher.pass_once([])["uploaded"] == [(fast() - 600, fast() - 590)]
    got = ingest.result(SERIAL, rid)
    assert got[0].key and [round(unix_s(s.begin) - wall()) for s in got] == list(range(-600, -590))


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
    """The card failed the read — a segment shorter than written, a card gone for a moment. The answer is an error,
    the request is over, and the recorder's next ask is answered with the frames."""
    from w2cplatform.obsd import unix_s
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    broken = {"now": True}

    def read(t0, t1):
        if broken["now"]:
            raise OSError("reading 1-card/e1: 512 of 4096 bytes — the segment is shorter than written")
        return card.range("1-card", t0, t1)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=read)
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
    pusher.pass_once([])
    try:
        ingest.result(SERIAL, rid)
        raise AssertionError("a read the card failed was answered")
    except RangeFailed as e:
        assert "shorter than written" in str(e)
    broken["now"] = False
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 590)
    pusher.pass_once([])
    assert [round(unix_s(s.begin) - wall()) for s in ingest.result(SERIAL, rid)] == list(range(-600, -590))


def test_the_recorders_card_range_asks_the_camera_and_waits_for_its_answer():
    """`RecWorker.card_range` as the ingest gives it: the recorder's request goes in the answer to the camera's poll,
    and the call returns when the camera has uploaded — or raises when it answered RANGE FAILED, or not at all."""
    wall = Clock(100_000.0)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    card = _card(wall() - 1000, wall())
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, card=lambda t0, t1: card.range("1-card", t0, t1))
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

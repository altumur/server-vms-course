"""The camera's card without an engine (Lesson 26; М12 Lesson 16) — as the product does it.

A camera has some 32 MB of memory, and the archive engine wants 20–25 MB for a writer (the product's design note,
§12 and §14; feedback CB, CT, CV, DG). So on a camera there is no obsd: its frames live in ONE ring in memory
(`CamRing`, 60 s in at most 32 MiB), and its card is a BUFFER of plain segment files with a byte budget
(`CardBuffer`), written from the ring by the card's actuator (`CardActuator`) under the platform's recorder
(`CardRecorder`) — the gate of Lesson 26 unchanged. The server reads the card by ASKING the camera for a range
(`answer_range`, the ingest's range request in М12), never through a door on the camera.
"""
import os
import tempfile

from vms import volumes
from vms.archive import stitch
from vms.card import (QUEUE_LEN, NO_ENGINE, CamRing, CardActuator, CardBuffer, CardError, CardRecorder, NeedKey,
                      declare_card)
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


# -- the recorder on the camera -----------------------------------------------------------------------------------------
def _camera(card_dir=None, when="offline", budget=64 << 20):
    """A camera that is a cluster of its own: its row, its card declared (`kind: edge`), a recording on the card and
    the platform's recorder over the card — the ring its source, no engine anywhere."""
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"]))
    con.create_camera({"name": "gate", "source": CARD, "ref": "SN1"})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    card_dir = card_dir or tempfile.mkdtemp(prefix="card-")
    declare_card(box.vars, "srv-1", card_dir, budget)
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


def test_an_edge_volume_is_a_directory_on_the_camera_never_an_address():
    """A card is opened by the camera's recorder as files — a bucket or a share is something no card reader opens,
    and a key to one has nowhere to go. That is a `local` or `network` volume, with an engine."""
    volumes.refuse({"name": "card", "kind": "edge", "server": "cam-7", "url": "/media/sd", "quota_bytes": 1})
    for bad in ({"url": "s3://cards/cam-7"}, {"url": "/media/sd", "access_secret": "x"}):
        try:
            volumes.refuse({"name": "card", "kind": "edge", "server": "cam-7", "quota_bytes": 1, **bad})
            raise AssertionError(f"{bad} was taken for a card")
        except Exception as e:                                             # Refused
            assert "card in a camera" in str(e)


def test_a_recorder_of_the_engine_never_takes_a_cameras_card():
    """The card is the camera's buffer, written by the camera's own recorder. A recorder of the engine on the same
    box — free to take, or pinned to it by mistake — does not mount it."""
    box, ctl, con, con_vars = _box()
    declare_card(box.vars, "srv-1", tempfile.mkdtemp(prefix="card-"))
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
    declare_card(box.vars, "cam-1", tempfile.mkdtemp(prefix="card-"))
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

    def card_range(src, t0, t1):
        asked.append((src["recording"], t0, t1))
        return cam.answer_range(src["recording"], t0, t1)
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
    [done] = primary.backfill(budget=1, now=now, force=True)
    assert "error" not in done and done["groups"] > 0

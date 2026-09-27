"""Lesson 16 — a camera nobody can reach.

The camera's door is closed for good: no domain, no recorder, no gateway can open a connection to it. It
reaches out — its agent for books and reports (Lesson 10), a long poll to the recording cluster's ingest for
work, a push for media — and recording, live view and backfill all work. The stream token is the domain
signer's; the ingest checks it with the key set its own agent carried.
"""
from cluster.variables import FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from domain.crossing import Crossings, resolve
from domain.device import DeviceCluster
from domain.federation import Federation, Unreachable
from domain.gateway import Gateway
from domain.ingest import LINGER, CameraPusher, Ingest, IngestLiveEndpoint, Refused, audience
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

SERIAL = "SN5001"
URLS = ["srt://srv-1.south:9000", "srt://srv-2.south:9000"]


def _site(wall, down=()):
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    south, _ = make_cluster("south")                                   # the server room that records it
    fed.add(north); fed.add(south)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    room_agent = DomainAgent("south", north.vars, south.vars, now=wall)
    room_agent.sync()                                                  # the room's key set: what the ingest checks with
    ingest = Ingest("south", URLS, keys=lambda: ClusterTrust(south.vars).keyset(), wall=wall)
    ingest.announce(south.objects)
    SpecController(REC_SPEC, south.vars, south.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot()
    cam.door_open = False                                              # nobody can open a connection to it, ever
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    cam_agent.sync()

    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens)
    crossings.record(SERIAL, on="south")

    def dial(url):                                                     # the camera dialling OUT; only the ingest answers
        if url not in URLS or url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest

    pusher = CameraPusher(SERIAL, cam.flash, dial, card=lambda t0, t1: [("card", t0, t1)], clock=wall)

    def domain_pass():
        view.refresh(); crossings.publish(); crossings.publish_primaries(); cam_agent.sync(); room_agent.sync()

    domain_pass()
    return fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass


def test_the_camera_learns_where_to_push_from_its_book_and_the_book_does_not_churn():
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    e = pusher.entry()
    assert e["cluster"] == "south" and e["ingest"]["urls"] == URLS
    ingest.poll(e["ingest"]["token"], SERIAL)                          # the ingest takes the domain's token
    writes = cam.flash.writes
    for _ in range(10):
        wall.advance(30); cam.publish(); domain_pass()
    assert cam.flash.writes == writes                                  # five minutes of passes: the book did not change
    wall.advance(13 * 3600); cam.publish(); domain_pass()
    assert pusher.entry()["ingest"]["token"] != e["ingest"]["token"]  # past half its life: a new token, one write


def test_a_recorder_holding_an_always_recording_gets_the_stream_the_camera_pushes():
    """The recorder wants the stream for ever, so the camera pushes for ever — and it finds the camera the
    way it found any camera of another cluster: in its own cluster's source book, which now says ingest."""
    wall = Clock()
    fed, north, south, signer, ingest, cam, *_rest, pusher, domain_pass = _site(wall)
    src = resolve(south.vars, f"ref:{SERIAL}", wall())
    assert src.live_url == f"ingest://south/{SERIAL}" and src.playback_url is None
    ingest.want(SERIAL, "recorder:r-0")
    q = ingest.subscribe(SERIAL, "recorder:r-0")
    out = pusher.pass_once(["f1", "f2"])
    assert out["pushed"] == 2 and q.drain() == ["f1", "f2"] and ingest.pushing(SERIAL)


def test_live_view_on_demand_the_camera_pushes_only_while_somebody_watches():
    """An event-recorded camera nobody watches pushes nothing. A viewer opens it: the gateway's endpoint is the
    ingest, opening it is wanting the stream, the camera learns on its poll and pushes. The viewer leaves:
    after a short linger, it stops."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    assert pusher.pass_once(["f0"])["pushed"] == 0 and "nobody wants" in pusher.state

    ep = IngestLiveEndpoint(ingest, authorise=lambda token, camera: "anna")
    gw = Gateway("gw-1", where=lambda camera: audience("south"), endpoint=lambda w: ep)
    vq = gw.watch(SERIAL, "anna-token", "anna")
    assert pusher.pass_once(["f1", "f2"])["pushed"] == 2
    gw.pump()
    assert vq.drain() == ["f1", "f2"]

    gw.leave(SERIAL, "anna")
    assert pusher.pass_once(["f3"])["pushed"] == 1                     # the linger: a viewer who clicks back
    wall.advance(LINGER + 1)
    assert pusher.pass_once(["f4"])["pushed"] == 0


def test_backfill_and_card_playback_are_ranges_the_camera_uploads_on_request():
    """Nobody can read the card, so the recorder asks and the camera pushes — into the backfill stream, never
    the live one. The same request serves an operator who wants to see what only the card holds."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    rid = ingest.request_range(SERIAL, 1000.0, 1600.0)
    assert ingest.answer(SERIAL, rid) is None                          # asked, not answered
    out = pusher.pass_once([])
    assert out["uploaded"] == [(1000.0, 1600.0)] and ingest.landed(SERIAL) == [(1000.0, 1600.0)]
    assert ingest.answer(SERIAL, rid) == [("card", 1000.0, 1600.0)]   # the answer to THAT request, by its id (AD)
    assert pusher.pass_once([])["uploaded"] == []                      # asked once, uploaded once


def test_the_ingest_refuses_a_token_for_another_camera_another_cluster_or_past_its_expiry():
    wall = Clock()
    fed, north, south, signer, ingest, *_ = _site(wall)
    for bad in (signer.tokens.issue("cam-SN9", 3600, now=wall(), aud=audience("south"), ref="SN9"),
                signer.tokens.issue(f"cam-{SERIAL}", 3600, now=wall(), aud=audience("east"), ref=SERIAL)):
        try:
            ingest.poll(bad, SERIAL)
            assert False
        except Refused:
            pass
    old = signer.tokens.issue(f"cam-{SERIAL}", 60, now=wall(), aud=audience("south"), ref=SERIAL)
    wall.advance(3600)
    try:
        ingest.push(old, SERIAL, ["f"])
        assert False
    except Refused as e:
        assert "expired" in str(e)


def test_one_ingest_down_the_camera_dials_the_next():
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall, down=(URLS[0],))
    ingest.want(SERIAL, "recorder:r-0")
    assert pusher.pass_once(["f"])["pushed"] == 1 and pusher.state == f"pushing to {URLS[1]}"


def test_a_frame_carries_its_capture_time_and_the_ingest_moves_it_between_the_clocks_both_ways():
    """Feedback AC. The camera's clock is ninety seconds fast. Its frames arrive stamped with the camera's time;
    the ingest moves them onto the cluster's by what the camera states in every request, and a range asked on
    the cluster's clock reaches the camera on its own — and comes back on the cluster's."""
    wall = Clock()
    fast = Clock(wall() + 90)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=fast,
                          card=lambda t0, t1: [{"t": t0, "k": True}, {"t": t1 - 1}])
    ingest.want(SERIAL, "recorder:r-0")
    q = ingest.subscribe(SERIAL, "recorder:r-0")
    pusher.pass_once([{"t": fast(), "k": True}])
    [f] = q.drain()
    assert abs(f["t"] - wall()) < 1e-6                                 # on the cluster's clock
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 300)
    assert pusher.pass_once([])["uploaded"] == [(fast() - 600, fast() - 300)]   # on the camera's clock
    assert [round(s["t"] - wall()) for s in ingest.answer(SERIAL, rid)] == [-600, -301]   # and back


def test_the_ring_lives_on_the_camera_the_recorder_gets_it_and_the_viewer_does_not():
    """Feedback AC and AF. Nobody wants the stream, and the camera keeps the last thirty seconds. An event:
    the recorder wants it, and the first push starts with the ring — marked, with its own capture times, so
    the start of the event is not lost to the time the want took. A viewer, opened at the same moment, gets the
    live edge: the ring would be the last half-minute played fast."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, ring_seconds=30)
    for _ in range(6):                                                 # a minute nobody watches: the ring keeps 30 s
        wall.advance(10); pusher.pass_once([{"t": wall()}])
    ingest.want(SERIAL, "recorder:event")
    rq = ingest.subscribe(SERIAL, "recorder:event")
    vq = ingest.subscribe(SERIAL, "viewer", edge=True)
    wall.advance(1); pusher.pass_once([{"t": wall()}])
    got = rq.drain()
    assert [f.get("ring", False) for f in got] == [True, True, True, True, False]   # 30 s of ring, then live
    assert got[0]["t"] == wall() - 31 and vq.drain() == [{"t": wall()}]


def test_the_long_poll_answers_first_holds_when_nothing_changed_and_wakes_when_a_want_runs_out():
    """Feedback AF: a camera that never polled is answered at once (version -1); the same version again is a
    poll the real ingest holds; a viewer who left wakes it at the end of the linger, not at the end of the poll."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    token = pusher.entry()["ingest"]["token"]
    first = ingest.poll(token, SERIAL, version=-1)
    assert "held" not in first and first["push"] is False
    assert ingest.poll(token, SERIAL, version=first["version"]).get("held")
    ingest.want(SERIAL, "anna"); ingest.release(SERIAL, "anna")        # a viewer came and went
    woke = ingest.poll(token, SERIAL, version=first["version"])
    assert "held" not in woke and woke["push"] is True                 # the linger
    wall.advance(LINGER + 0.1)
    lapsed = ingest.poll(token, SERIAL, version=woke["version"])
    assert "held" not in lapsed and lapsed["push"] is False            # woken by the want running out


def test_two_ingests_of_one_cluster_pass_the_stream_to_each_other():
    """Feedback AG. The book lists both ingests of the recording cluster; the camera pushes to the first that
    answers; the recorder holding the recording is on the other server. A want at either counts at both, and the
    ingest with a subscriber and no camera takes the stream from the one that has it. A range asked there is
    answered there."""
    wall = Clock()
    fed, north, south, signer, ingest, cam, *_rest, pusher, domain_pass = _site(wall)
    keys = lambda: ClusterTrust(south.vars).keyset()
    a = Ingest("south", URLS, keys=keys, wall=wall, name=URLS[0], peers=lambda: [b])
    b = Ingest("south", URLS, keys=keys, wall=wall, name=URLS[1], peers=lambda: [a])
    by_url = {URLS[0]: a, URLS[1]: b}
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: by_url[url], clock=wall, card=lambda t0, t1: [("card", t0, t1)])
    b.want(SERIAL, "recorder:srv-2")                                   # the recorder is on the second server
    rq = b.subscribe(SERIAL, "recorder:srv-2")
    assert pusher.pass_once(["x1", "x2"])["pushed"] == 2 and pusher.state == f"pushing to {URLS[0]}"
    b.pump()
    assert rq.drain() == ["x1", "x2"]
    rid = b.request_range(SERIAL, 100.0, 200.0)
    pusher.pass_once([])                                               # asked at b, polled and answered at a
    assert b.answer(SERIAL, rid) == [("card", 100.0, 200.0)]

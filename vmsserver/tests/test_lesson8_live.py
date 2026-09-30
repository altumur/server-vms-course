"""Lesson 8 — live video as the second subsystem. A gateway is a worker
whose unit is a camera's fan-out and whose capacity is viewers; the unit is
created by the first viewer and deleted after the last; one subscription per
camera whatever the audience; the worker never learns a viewer exists."""
import json
import threading
import urllib.error
import urllib.request

from w2cplatform.spec import SpecController
from w2cplatform.variables import Forbidden
from vms.config import LIVE_SPEC, SPEC
from vms.controller import VmsController
from vms.liveworker import LiveWorker
from vms.config import live_url
from vms.worker import FakeActuator, VmsWorker
from vms.console import serve
from tests.conftest import Box, published_snapshot

OFFER = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=recvonly\r\na=rtpmap:96 H264/90000\r\n"


def _box():
    """One box: a VMS worker recording camera 1, the two controllers, a console with both tokens."""
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con_vars = box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console())
    con = VmsController(con_vars, box.objects, wall=box.wall)
    live_ctl = SpecController(LIVE_SPEC, box.vars.as_writer("livecontroller", LIVE_SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive)
    w.heartbeat_once()
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); ctl.ensure_placed()   # the console writes the row, the controller places
    w.reconcile_once(); w.heartbeat_once()
    srv = serve(con, None, port=0, wall=box.wall, live_ctl=SpecController(LIVE_SPEC, con_vars, box.objects, wall=box.wall))
    return box, ctl, live_ctl, w, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _gateway(box, name, capacity=100, labels="", url=""):
    g = LiveWorker(name, box.vars.as_writer("liveworker", ["live/epoch/*", "live/slots/*", "live/streams/*"]), box.objects,
                    ctl=SpecController(LIVE_SPEC, box.vars.as_writer("liveworker", ["live/epoch/*", "live/slots/*", "live/streams/*"]), box.objects, wall=box.wall),
                    capacity=capacity, clock=box.clock, wall=box.wall, server="srv-1", env={"LABELS": labels})
    g.serve("127.0.0.1", 0); g.heartbeat_once()
    return g


def _whep(base, cam, headers=None, method="POST", path=None):
    req = urllib.request.Request(base + (path or f"/whep/{cam}"), data=OFFER.encode() if method == "POST" else None, method=method,
                                 headers={"Content-Type": "application/sdp", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode(), r.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), ""


def test_the_first_viewer_creates_the_stream_and_the_controller_places_it():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        # the worker's heartbeat says where the stream is — its RTSP fan-out, reachable from any server; nobody asked the worker
        st = [s for s in ctl.workers_seen()["w-1"].status if s["id"] == 1][0]
        assert st["live_url"] == live_url("srv-1", 1) == "rtsp://srv-1:8554/1" and "viewers" not in st
        # first viewer: the console creates live/streams/1 and says "retry" — placement is the controller's pass
        code, body, _ = _whep(base, 1)
        assert code == 503 and json.loads(body)["retry_after"] == 2
        assert live_ctl.unit("1") == {"id": "1", "cam": "1", "labels": [], "grace": 30, "revision": 1}
        assert box.vars.list("live/placement/") == []                                 # the console could not place it
        try:
            SpecController(LIVE_SPEC, box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console()), box.objects, wall=box.wall).place("1")
            raise AssertionError("a console token never writes placement")
        except Forbidden:
            pass
        assert live_ctl.ensure_placed()[0].worker == "g-1"                              # the live controller's pass
        assert g.reconcile_once() == ["1"] and g.subscriptions == 1 and g.upstreams["1"].url == "rtsp://srv-1:8554/1" and g.upstreams["1"].server == "srv-1"
        g.heartbeat_once()
        # second try: 201 with the gateway's SDP answer, and a session URL that goes back through the console
        code, answer, loc = _whep(base, 1)
        assert code == 201 and "m=video" in answer and "a=sendonly" in answer and loc.startswith("/whep/session/") and loc.endswith("?gateway=g-1")
        g.heartbeat_once()                                                               # what the page reads: the gateway's word, from its heartbeat
        st = json.loads(urllib.request.urlopen(f"{base}/whep/1").read())
        assert st["gateway"] == "g-1" and st["status"]["phase"] == "live" and st["status"]["sessions"] == 1
        # unknown camera: 404, no unit created
        assert _whep(base, 9)[0] == 404 and live_ctl.unit("9") is None
    finally:
        srv.shutdown(); srv.server_close()


def test_fifty_viewers_one_subscription_and_the_worker_unchanged():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1", capacity=60)
        _whep(base, 1); live_ctl.ensure_placed(); g.reconcile_once(); g.heartbeat_once()
        before = box.objects.get("vms/heartbeats/w-1")
        sessions = [_whep(base, 1)[2] for _ in range(50)]
        assert all(s.startswith("/whep/session/") for s in sessions) and len(g.sessions) == 50
        assert g.subscriptions == 1 and len(g.upstreams) == 1                            # fifty browsers, one tee subscription
        assert g.headroom() == 10                                                        # capacity is viewers: what the autoscaler moves N on
        assert box.objects.get("vms/heartbeats/w-1") == before                            # the worker never learned a viewer exists
        # full: the sixty-first viewer is refused by the gateway, through the console
        for _ in range(10):
            _whep(base, 1)
        code, body, _ = _whep(base, 1)
        assert code == 503 and "full" in json.loads(body)["detail"]
        # hang up one through the console: the session is gone on the gateway
        sid = sessions[0].split("/")[-1].split("?")[0]
        assert _whep(base, 1, method="DELETE", path=sessions[0])[0] == 200 and sid not in g.sessions and len(g.sessions) == 59
        assert "live_sessions 59" in urllib.request.urlopen(f"{g.url}/metrics").read().decode()
    finally:
        srv.shutdown(); srv.server_close()


def test_the_last_viewer_leaves_and_the_gateway_deletes_the_unit_after_grace():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        _whep(base, 1); live_ctl.ensure_placed(); g.reconcile_once(); g.heartbeat_once()
        _, _, loc = _whep(base, 1)
        _whep(base, 1, method="DELETE", path=loc)
        box.wall.advance(10); g.reconcile_once()
        assert live_ctl.unit("1") is not None and "1" in g.upstreams                     # inside the grace: kept, a returning viewer costs nothing
        box.wall.advance(25); g.reconcile_once()
        assert live_ctl.unit("1") is None                                                # the gateway deleted the unit it held
        assert live_ctl.unplace_deleted() == ["1"] and live_ctl.where("1") is None      # the controller's half
        assert g.reconcile_once() == [] and "1" not in g.epochs                           # the subscription is closed
        # a viewer comes back: the unit is created again under its name, placed, served
        assert _whep(base, 1)[0] == 503 and live_ctl.unit("1")["revision"] == 2
        live_ctl.ensure_placed(); g.reconcile_once(); g.heartbeat_once()
        assert _whep(base, 1)[0] == 201 and g.subscriptions == 2
    finally:
        srv.shutdown(); srv.server_close()


def test_the_first_press_of_live_is_answered_with_wait_and_not_with_not_found():
    """Between the controller placing the fan-out and the gateway's next pass
    there is a window of one pass, and the FIRST press of Live lands in it: the
    row exists, the placement exists, the gateway is up — and it has not
    subscribed yet, so it answers 404. The page retries on 503 and on nothing
    else, so a 404 forwarded verbatim ends the attempt and the operator is told
    the stream does not exist. It does. The console turns that one 404 into a
    503 and keeps the gateway's word in `detail`."""
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        assert _whep(base, 1)[0] == 503              # the press creates the row; nobody holds it yet
        live_ctl.ensure_placed(); g.heartbeat_once()
        assert live_ctl.where("1") == "g-1"          # placed, and the gateway has heartbeaten its url
        assert g.upstreams == {}                     # but it has not made its pass yet
        code, body, _ = _whep(base, 1)
        assert code == 503, "the page retries on 503 only: a 404 here is the operator pressing Live twice"
        d = json.loads(body)
        assert "g-1" in d["detail"] and d["retry_after"] == 2
        g.reconcile_once()                           # the pass happens
        assert _whep(base, 1)[0] == 201              # and the same press now succeeds
    finally:
        srv.shutdown(); srv.server_close()


def test_a_dead_gateway_loses_its_fan_outs_to_the_survivor_and_viewers_reconnect():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g1, g2 = _gateway(box, "g-1", capacity=100), _gateway(box, "g-2", capacity=50)
        _whep(base, 1); assert live_ctl.ensure_placed()[0].worker == "g-1"               # the most free capacity
        g1.reconcile_once(); g1.heartbeat_once()
        assert _whep(base, 1)[0] == 201
        # g-1 dies: its slot lapses, the controller redistributes, g-2 subscribes, the viewer's next offer lands there
        box.clock.advance(60); box.wall.advance(60)
        g2.heartbeat_once(); w.heartbeat_once()      # g-1 silent for a minute; g-2 and the camera's holder still here

        assert live_ctl.released_slots() == []                                           # a crash releases nothing…
        assert live_ctl.redistribute() == []                                             # …and the controller moves nothing on its own
        live_ctl.retire("g-1")                                                           # the operator (or Nomad's stop) releases the slot
        assert [m[:3] for m in live_ctl.redistribute()] == [("1", "g-1", "g-2")]
        g2.reconcile_once(); g2.heartbeat_once()
        code, _, loc = _whep(base, 1)
        assert code == 201 and loc.endswith("?gateway=g-2") and g2.subscriptions == 1
        w.reconcile_once(); w.heartbeat_once()
        assert ctl.workers_seen()["w-1"].status[0]["phase"] == "running" and w.actuator.running == {1}   # recording did not notice any of it
    finally:
        srv.shutdown(); srv.server_close()


def test_placement_by_label_a_stream_for_outside_viewers_needs_a_public_address():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        inside, outside = _gateway(box, "g-1", labels=""), _gateway(box, "g-2", labels="public-address")
        code, body, _ = _whep(base, 1, path="/whep/1?labels=public-address")
        assert code == 503 and live_ctl.unit("1")["labels"] == ["public-address"]
        assert live_ctl.ensure_placed()[0].worker == "g-2"                              # only the gateway with a public address is eligible
        assert "reaching public-address" in live_ctl.placement("1").reason
    finally:
        srv.shutdown(); srv.server_close()


def test_the_two_subsystems_share_the_platform_and_see_nothing_of_each_other():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        _whep(base, 1); live_ctl.ensure_placed(); g.reconcile_once(); g.heartbeat_once(); _whep(base, 1)
        assert sorted(p.split("/")[0] for p in box.vars.list("")) and all(p.startswith(("vms/", "live/")) for p in box.vars.list(""))
        assert [p for p in box.vars.list("live/") if "/idem/" not in p] == [
            "live/epoch/1", "live/placement/1", "live/slots/g-1", "live/streams/1", "live/workers/g-1"]
        assert not any("live" in p for p in box.vars.list("vms/"))                        # the VMS's rows carry nothing about viewers
        live_ctl.publish_snapshot()                                                      # the live controller publishes its own snapshot
        snap = published_snapshot(box.objects, "live", rows="streams")
        assert snap["streams"][0]["cam"] == "1" and snap["streams"][0]["worker"] == "g-1"
    finally:
        srv.shutdown(); srv.server_close()


def _watched(base, live_ctl, g, viewers=1):
    _whep(base, 1); live_ctl.ensure_placed()                          # the first viewer creates the unit; the controller places it
    assert g.reconcile_once() == ["1"]
    return [g.offer("1", OFFER)[0] for _ in range(viewers)]


def test_a_viewer_that_left_without_saying_so_does_not_hold_its_session_for_ever():
    """A session ended with DELETE, and only with DELETE. A closed tab says nothing: its session stayed, the
    fan-out was never idle, and a gateway of `capacity` viewers filled with nobody watching and answered 503
    "full" to everybody after (the product's gateway, feedback BC). Every pass asks each peer what became of it."""
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1", capacity=2)
        a, b = _watched(base, live_ctl, g, viewers=2)
        assert g.headroom() == 0
        try:
            g.offer("1", OFFER); raise AssertionError("full")
        except OverflowError:
            pass
        g.sessions[a][1].lost = True                                   # the tab was closed: no DELETE, the connection is gone
        g.reconcile_once()
        assert a not in g.sessions and b in g.sessions and g.headroom() == 1 and g.swept == 1
        assert g.upstreams["1"].idle_since is None                     # somebody is still watching
        g.sessions[b][1].lost = True
        g.reconcile_once()
        assert g.sessions == {} and g.upstreams["1"].idle_since == box.wall()   # idle from now: the grace period can start
    finally:
        srv.shutdown()


def test_an_offer_whose_connection_never_came_up_is_closed_after_half_a_minute():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        (sid,) = _watched(base, live_ctl, g)
        peer = g.sessions[sid][1]
        peer.connected = False                                         # answered, and the browser never connected
        box.wall.advance(20); g.reconcile_once()
        assert sid in g.sessions                                       # still inside the time a connection may take
        box.wall.advance(11); g.reconcile_once()
        assert sid not in g.sessions and peer.closed and g.swept == 1
    finally:
        srv.shutdown()


def test_an_offer_that_fails_leaves_no_peer_behind():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        _watched(base, live_ctl, g, viewers=0)
        made = []
        factory = g.peer_factory
        g.peer_factory = lambda up: made.append(factory(up)) or made[-1]
        try:
            g.offer("1", "v=0\r\n"); raise AssertionError("an offer with no video section")
        except ValueError:
            pass
        assert made[0].closed and g.sessions == {}
    finally:
        srv.shutdown()


def test_the_codec_report_is_on_the_peer_the_gateway_asks():
    """`codec_note` was defined twice on `_Source` — the second, meant for the peer, replaced the first and called
    an attribute `_Source` does not have — and `GstPeer`, which is what the gateway asks, had none: a camera
    sending a codec no browser plays was a black picture with an empty `codec`. Read from the source: the module
    needs GStreamer to import."""
    import ast
    import os
    tree = ast.parse(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gstvms", "webrtc.py")).read())
    methods = {c.name: [f.name for f in c.body if isinstance(f, ast.FunctionDef)] for c in tree.body if isinstance(c, ast.ClassDef)}
    assert methods["_Source"].count("codec_note") == 1
    assert "codec_note" in methods["GstPeer"] and "state" in methods["GstPeer"]


def test_a_camera_that_moved_hangs_up_its_viewers_and_the_subscription_takes_the_new_address():
    """Where the camera is was read once, when the subscription was made. Its worker restarted the pipeline under
    a new epoch, or the camera moved: the gateway's source died quietly, the status said `live` at the old
    address and the viewers had a black picture (the platform review; the product's gateway, feedback BF). Every
    pass compares `(url, epoch)` with what the holder says now."""
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        (sid,) = _watched(base, live_ctl, g)
        peer, before = g.sessions[sid][1], g.upstreams["1"]
        g.reconcile_once()
        assert sid in g.sessions and g.resets == 0                     # nothing changed: nothing reopened
        w.actuator("stop", {"id": 1}); w.reconciler.actual.pop(1, None); w.release("1")
        w.reconcile_once(); w.heartbeat_once()                         # the worker started it again: epoch 2
        g.reconcile_once()
        up = g.upstreams["1"]
        assert up is not before and up.epoch == 2 and up.reset == "the camera is served elsewhere now"
        assert sid not in g.sessions and peer.closed and g.resets == 1 and up.idle_since == box.wall()
        assert g.offer("1", OFFER)[0] in g.sessions                    # the viewer's page connects again: the new source
    finally:
        srv.shutdown()


def test_a_source_that_died_is_reopened_even_where_the_camera_has_not_moved():
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1")
        (sid,) = _watched(base, live_ctl, g)

        class Source:
            def __init__(self): self.ok, self.closed = True, False
            def alive(self): return self.ok
            def close(self): self.closed = True

        src = g.upstreams["1"].pipeline = Source()
        g.reconcile_once()
        assert sid in g.sessions
        src.ok = False                                                 # rtspsrc posted an error: nobody else would have read it
        g.reconcile_once()
        assert sid not in g.sessions and src.closed and g.upstreams["1"].reset == "the source stopped"
    finally:
        srv.shutdown()


def test_an_answer_is_prepared_outside_the_gateways_lock_with_its_seat_already_taken():
    """The answer waits for every ICE candidate — up to five seconds — and it was prepared under the lock the pass
    takes for the leases and the heartbeat, and every other viewer takes to be answered (feedback BE). Now the
    pass goes on while a viewer is being answered; the seat is taken first, so a burst cannot overfill; and an
    answer into a subscription the pass has dropped meanwhile closes its peer."""
    import threading
    box, ctl, live_ctl, w, srv, base = _box()
    try:
        g = _gateway(box, "g-1", capacity=1)
        _watched(base, live_ctl, g, viewers=0)
        answering, go, peers = threading.Event(), threading.Event(), []
        factory = g.peer_factory

        class Slow:
            def __init__(self, up): self.inner = factory(up); self.closed = False; peers.append(self)
            def answer(self, sdp):
                answering.set(); go.wait(10)
                return self.inner.answer(sdp)
            def state(self): return "connected"
            def close(self): self.closed = True

        g.peer_factory = Slow
        out = {}
        t = threading.Thread(target=lambda: out.update(r=_try(lambda: g.offer("1", OFFER))), daemon=True)
        t.start()
        assert answering.wait(5)
        assert g.reconcile_once() == ["1"] and g.headroom() == 0       # the pass ran, and the seat is taken
        try:
            g.offer("1", OFFER); raise AssertionError("the one seat is being answered")
        except OverflowError:
            pass
        g._drop("1")                                                   # …and the pass takes the subscription away
        go.set(); t.join(5)
        assert isinstance(out["r"], KeyError) and peers[0].closed and g.sessions == {} and g.answering == 0
    finally:
        srv.shutdown()


def _try(fn):
    try:
        return fn()
    except Exception as e:                                             # noqa: BLE001
        return e


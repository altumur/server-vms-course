"""The doors are shut until somebody opens them, and a door announces what it bound (the platform review, blocker 1;
the product's step 0, feedback BP).

Nothing below М12 asks who is calling. What stood between a camera's live stream and anybody on the network was the
address a door listened on — and the RTSP fan-out and the door to a device's own archive listened on every interface.
"""
import logging

from vms.config import announce_host, is_loopback, local_only
from vms.worker import FakeActuator, VmsWorker
from tests.vmsconftest import Box
from tests.test_lesson4_worker import _box_with_cameras


def test_a_door_announces_what_it_bound():
    assert is_loopback("127.0.0.1") and is_loopback("localhost") and is_loopback("127.0.0.53") and not is_loopback("0.0.0.0")
    # …by what the address is, not how it is spelt (the review's eighth pass, the sweep of spellings)
    assert all(is_loopback(h) for h in ("LOCALHOST", "localhost.", "::ffff:127.0.0.1", "0:0:0:0:0:0:0:1", "[::1]"))
    assert not any(is_loopback(h) for h in ("127.example.com", "", "::", "10.0.0.5"))
    assert announce_host("127.0.0.1", "srv-a") == "127.0.0.1"          # bound to loopback: says loopback
    assert announce_host("0.0.0.0", "srv-a") == "srv-a" and announce_host("10.0.0.5", "srv-a") == "srv-a"
    assert announce_host(None, "srv-a") == "srv-a"                     # not told: the name, as it always was
    assert local_only("rtsp://127.0.0.1:8554/7", "srv-b", "srv-a")     # another machine's loopback: not for us
    assert not local_only("rtsp://127.0.0.1:8554/7", "srv-a", "srv-a") and not local_only("rtsp://srv-b:8554/7", "srv-b", "srv-a")


def _worker(env):
    box, ctl = _box_with_cameras(1)
    ctl.assign("w-1", ["1"])
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, resource_root=box.resource_root,
                  server="srv-a", env=env)
    w.claim_slot(prefer="w-1"); w.reconcile_once()
    return box, w


def test_the_heartbeat_says_loopback_for_a_door_bound_to_loopback():
    box, w = _worker({"RTSP_HOST": "127.0.0.1"})
    assert w.status()[0]["live_url"] == f"rtsp://127.0.0.1:{w.fanout_port()}/1"
    box, w = _worker({"RTSP_HOST": "0.0.0.0"})
    assert w.status()[0]["live_url"] == f"rtsp://srv-a:{w.fanout_port()}/1"


def test_the_door_to_a_devices_archive_binds_to_loopback_unless_it_is_opened():
    box, w = _worker({"PLAYBACK_PORT": "auto"})
    srv = w.serve_playback()
    try:
        assert srv.server_address[0] == "127.0.0.1" and w.playback_host == "127.0.0.1"   # it was every interface
    finally:
        srv.shutdown()

    said = []
    handler = logging.Handler(); handler.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("vmsworker").addHandler(handler)
    box, w = _worker({"PLAYBACK_PORT": "auto", "PLAYBACK_HOST": "0.0.0.0"})
    srv = w.serve_playback()
    try:
        assert srv.server_address[0] == "0.0.0.0"
        assert any("asks for a process's capability for the camera" in m for m in said)   # opened: and the process says what it asks (the fourth review: not "nobody")
    finally:
        srv.shutdown(); logging.getLogger("vmsworker").removeHandler(handler)


def test_a_recorder_on_another_server_does_not_knock_on_its_own_loopback():
    from w2cplatform.contract import Heartbeat
    from tests.test_volumes import _recorder
    box = Box()
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", box.wall(), [
        {"id": 7, "phase": "running", "live_url": "rtsp://127.0.0.1:8554/7", "live_shm": "shm:///run/vms/7.shm"}],
        {"server": "srv-b"}).to_bytes())
    far, near = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    assert near.source("7") == ("srv-b", "shm:///run/vms/7.shm")       # the same server: shared memory, as before
    assert far.source("7") is None and far.behind_loopback == {"7": "srv-b"}
    far.waiting = {"7"}
    why = far.status_extra({"id": "7", "cam": "7"})["why"]
    assert "served on loopback on srv-b" in why and "RTSP_HOST" in why   # not "camera held by nobody"


def test_a_gateway_and_a_backfill_do_not_knock_on_their_own_loopback_either():
    """The same rule for the other two subscribers (the product applied it to both, feedback BT): the live gateway
    does not open another server's loopback fan-out, and a backfill does not take a source whose door is on
    another server's loopback — a device's own archive, or a backup recorder's."""
    from w2cplatform.contract import Heartbeat
    from tests.test_lesson8_live import _gateway
    from tests.test_volumes import _recorder
    box = Box()
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", box.wall(), [
        {"id": 7, "phase": "running", "live_url": "rtsp://127.0.0.1:8554/7",
         "playback_url": "http://127.0.0.1:8083/playback/7", "coverage": {"from": 1, "to": 2}}], {"server": "srv-b"}).to_bytes())
    g = _gateway(box, "g-1")                                           # on srv-1
    assert g.rtp_source("7") is None
    far, near = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    assert far.device_source("7") is None and near.device_source("7") == ("http://127.0.0.1:8083/playback/7", {"from": 1, "to": 2})


"""The gateway's RTSP door — RTSP outward for a stream client's account (the product's `liveproc/rtsp.go`; ADR-0031, the
addendum of 2026-10-07; ADR-0024: the gateway reads the accounts because its spec says so).

One box: a VMS worker holding two cameras, a live gateway with the door over `FakeRTSPServer` (what speaks RTSP is
pluggable, as the WebRTC peer is). What the cluster's agent would have carried is written as it lies: the accounts this
cluster is granted, sealed with the cluster's ring (`domain/vms/stream-accounts`), and its grants (`domain/grants`). The
declarations are the product's lines added to the course's YAML (`tests/streamspec.py`)."""
import json
import os
import tempfile

from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.carry import seal_row
from w2cplatform.domain.grants import Grant, grants_to_items
from w2cplatform.sealing import Sealer, new_key_file
from vms.config import LIVE_SPEC, SPEC
from vms.controller import VmsController
from vms.liveworker import LiveWorker
from vms.rtspdoor import FakeRTSPServer, RTSPDoor
from vms.streamclients import STREAM_ACCOUNTS_KEY
from vms.worker import FakeActuator, VmsWorker
from tests.streamspec import declared
from tests.vmsconftest import Box

PW = {"wall1": "p" * 32, "wall2": "q" * 32, "wall3": "r" * 32}


def _key():
    path = os.path.join(tempfile.mkdtemp(prefix="ring-"), "platform.key")
    new_key_file(path)
    return path


def _box():
    """A VMS worker holding cameras 1 and 2 on srv-1 — what the gateway's door finds their streams by."""
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console()), box.objects,
                        wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  resource_root=box.resource_root)
    w.heartbeat_once()
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"})
    con.create_camera({"name": "yard", "source": "driverpack://file/yard.mp4"})
    ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()
    return box, w


def _carried(vars_, key_path, accounts: dict, grants: list):
    """What the agent leaves in the cluster's store: the accounts sealed with its ring, and the grants."""
    ring = Sealer.from_file(key_path)
    vars_.put(STREAM_ACCOUNTS_KEY, seal_row(ring, {"accounts_secret": json.dumps(accounts)}, STREAM_ACCOUNTS_KEY))
    _, idx = vars_.get("domain/grants")
    vars_.put("domain/grants", grants_to_items(grants), cas=idx)


def _gateway(box, env, server):
    v = box.vars.as_writer("liveworker", ["live/epoch/*", "live/slots/*", "live/streams/*"])
    return LiveWorker("g-1", v, box.objects, clock=box.clock, wall=box.wall, server="srv-1",
                      env={"LABELS": "", "CLUSTER": "room-a", **env}, resource_root=box.resource_root, rtsp_server=server)


def test_the_door_is_off_unless_asked_for_declared_and_given_a_server():
    """LIVE_RTSP_LISTEN unset: no door. Set, and the gateway's spec does not say it reads the accounts (the course's YAML
    as it is): no door. Declared, and no server to open it with: no door. All three: the door."""
    box, _ = _box()
    on = {"LIVE_RTSP_LISTEN": "127.0.0.1:8554"}
    assert _gateway(box, {}, FakeRTSPServer()).rtsp is None
    assert _gateway(box, on, FakeRTSPServer()).rtsp is None
    with declared():
        assert _gateway(box, {}, FakeRTSPServer()).rtsp is None
        assert _gateway(box, on, None).rtsp is None
        assert _gateway(box, on, FakeRTSPServer()).rtsp is not None


def test_a_mount_per_camera_and_on_it_only_the_accounts_whose_grants_let_them_view_it():
    """The accounts carried are the server's; a mount for every camera a worker holds, over its stream; on each mount the
    accounts a grant of `view` or more lets see that camera — one on camera 1, one on the cluster, none for the third
    account — and nobody else: a person with a grant is no account here."""
    key = _key()
    box, w = _box()
    until = box.wall() + 3600
    _carried(box.vars, key, PW, [Grant("wall1", "view", "vms/1", until), Grant("wall2", "view", None, until),
                                 Grant("anna", "admin", None, until)])
    with declared():
        srv = FakeRTSPServer()
        g = _gateway(box, {"LIVE_RTSP_LISTEN": "127.0.0.1:8554", "SECRETS_KEY": key}, srv)
        g.reconcile_once()
        assert srv.accounts_ == PW
        assert set(srv.mounts) == {"1", "2"} and srv.mounts["1"] == g.rtp_source("1")[1]
        assert srv.roles_ == {"1": ["wall1", "wall2"], "2": ["wall2"]}
        assert srv.play("wall1", PW["wall1"], "1")
        for user, password, cam, why in (("wall1", PW["wall1"], "2", 403), ("wall3", PW["wall3"], "1", 403),
                                         ("wall1", PW["wall2"], "1", 401), ("anna", "", "1", 401)):
            try:
                srv.play(user, password, cam)
                raise AssertionError(f"{user} played camera {cam}")
            except PermissionError as e:
                assert e.args == (why,), (user, cam, e.args)
        published = srv.published
        g.reconcile_once()
        assert srv.published == published                   # the same stream: the mount is not made again


def test_a_revoked_grant_is_honoured_on_the_next_sync_and_a_lapsed_one_too():
    """The grants are read once a sync, and every sync: a grant the agent carried away takes the account off the mount
    on the next pass; a grant that lapsed — the agent did not renew it — the same."""
    key = _key()
    box, _ = _box()
    _carried(box.vars, key, PW, [Grant("wall1", "view", "vms/1", box.wall() + 3600),
                                 Grant("wall2", "view", None, box.wall() + 60)])
    with declared():
        srv = FakeRTSPServer()
        g = _gateway(box, {"LIVE_RTSP_LISTEN": "127.0.0.1:8554", "SECRETS_KEY": key}, srv)
        g.reconcile_once()
        assert srv.roles_ == {"1": ["wall1", "wall2"], "2": ["wall2"]}
        _carried(box.vars, key, PW, [Grant("wall2", "view", None, box.wall() + 60)])        # wall1's grant revoked
        g.reconcile_once()
        assert srv.roles_ == {"1": ["wall2"], "2": ["wall2"]}
        box.wall.advance(61)                                                                # wall2's lapsed
        g.reconcile_once()
        assert srv.roles_ == {"1": [], "2": []}
        _carried(box.vars, key, {"wall2": PW["wall2"]}, [Grant("wall2", "view", None, box.wall() + 60)])
        g.reconcile_once()                                  # an account the agent no longer carries cannot log in
        assert srv.accounts_ == {"wall2": PW["wall2"]} and srv.roles_ == {"1": ["wall2"], "2": ["wall2"]}


def test_a_grant_on_labels_mounts_the_cameras_that_carry_them_and_a_camera_nobody_holds_is_unmounted():
    """The door over a store of its own: a grant on labels covers the cameras that carry all of them; a camera whose
    stream nobody serves now has no mount, and a client gets a 404; back, it is mounted again."""
    v = FakeVariables()
    v.put("vms/cameras/7", {"id": "7", "name": "lobby", "source": "driverpack://acme/10.0.0.77/ch/1", "labels": "lobby,floor0"})
    v.put("vms/cameras/8", {"id": "8", "name": "yard", "source": "driverpack://acme/10.0.0.78/ch/1"})
    v.put(STREAM_ACCOUNTS_KEY, {"accounts_secret": json.dumps({"wall1": PW["wall1"]})})
    v.put("domain/grants", grants_to_items([Grant("wall1", "view", None, 2000.0, ("lobby",))]))
    up = {"7": "rtsp://srv-1:8554/7", "8": "rtsp://srv-1:8554/8"}
    srv = FakeRTSPServer()
    door = RTSPDoor(srv, up.get, v, "room-a", wall=lambda: 1000.0)
    door.sync()
    assert srv.roles_ == {"7": ["wall1"], "8": []}
    del up["7"]
    door.sync()
    assert set(srv.mounts) == {"8"}
    try:
        srv.play("wall1", PW["wall1"], "7")
        raise AssertionError("a camera nobody holds was played")
    except KeyError:
        pass
    up["7"] = "rtsp://srv-2:8554/7"                          # held again, elsewhere: a new road
    door.sync()
    assert srv.mounts["7"] == "rtsp://srv-2:8554/7" and srv.roles_["7"] == ["wall1"]


def test_a_play_and_its_end_are_lines_in_the_gateways_journal():
    """Who played which camera, from where, and for how long: `live.rtsp.play` when a session appears, `live.rtsp.ended`
    when it is gone — the gateway's journal (`audit/liveworker`), as a viewer in a browser is `live.view`."""
    from w2cplatform.events import buckets_under
    key = _key()
    box, _ = _box()
    _carried(box.vars, key, PW, [Grant("wall1", "view", "vms/1", box.wall() + 3600)])
    with declared():
        srv = FakeRTSPServer()
        g = _gateway(box, {"LIVE_RTSP_LISTEN": "127.0.0.1:8554", "SECRETS_KEY": key}, srv)
        g.reconcile_once()
        sid = srv.play("wall1", PW["wall1"], "1", ip="10.0.0.9", agent="wall/1")
        g.reconcile_once()
        box.wall.advance(42)
        srv.stop(sid)
        g.reconcile_once()
        g.reconcile_once()                                   # said once, not every pass

    def said():
        return [{k: e[k] for k in ("kind", "user", "target", "session", "gateway", "addr", "agent", "seconds") if k in e}
                for b in buckets_under(box.resource_root, "audit", "liveworker", 600)
                for e in map(json.loads, open(os.path.join(box.resource_root, b.path))) if e["kind"].startswith("live.rtsp")]
    assert said() == [
        {"kind": "live.rtsp.play", "user": "wall1", "target": "1", "session": sid, "gateway": "g-1", "addr": "10.0.0.9",
         "agent": "wall/1"},
        {"kind": "live.rtsp.ended", "user": "wall1", "target": "1", "session": sid, "gateway": "g-1", "addr": "10.0.0.9",
         "seconds": 42}], said()

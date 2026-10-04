"""Lesson 3 — what stays on the server, and what does not. Configuration is
already in the replicated store (the RPO is zero); footage stays in the volume it was written
into — a server's own, through its host's obsd — and is read through the door
of the recorder that holds it; a camera's timeline spans two volumes and names
the one nobody serves now: unavailable, not lost."""
import json
import os

from cluster.console import cluster_routes
from cluster.controller import ClusterController

from w2cplatform.spec import SpecController
from vms.config import REC_SPEC
from tests.cluster.conftest import Cluster, footage


def _recorder_with_footage(c: Cluster, server: str, unit: str, epoch: int, spans, name: str | None = None):
    """A recorder on `server`, its own volume open and serving it at its door, with `spans` of `unit` in it."""
    r = c.recorder(server, name=name)
    r.lease_pass()
    for a, b in spans:
        footage(r.store, unit, epoch, a, b, step=10, seal=False)
    r.store.seal()
    r.serve_archive()
    r.heartbeat_once()
    return r


def test_an_edit_during_the_failover_is_simply_there():
    """The RPO inside the cluster is zero: the console's write went into the replicated store (raft, under the
    configstore), and the new process of the unit — systemd starts it again two seconds later — reads it there.
    """
    c = Cluster(); ctl = ClusterController(c.vars, c.objects, wall=c.wall)
    ctl.create_camera({"source": "driverpack://file/1.mp4", "name": "before"})
    a = c.worker("srv-a"); a.heartbeat_once(); ctl.ensure_placed(); a.reconcile_once()
    c.wall.advance(2)                                                      # w-srv-a-1 died; systemd starts its unit again
    ctl.update_camera(1, {"name": "edited during the failover"})          # acknowledged after the CAS commit: it is in raft
    b = c.worker("srv-a")                                                  # the new process, the same name
    assert b.reconcile_once() == [("start", 1)] and b.rows[0]["name"] == "edited during the failover"
    assert c.objects.get("vms/config") is None                             # nothing was published for this to work


def test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves():
    c = Cluster(); ctl = ClusterController(c.vars, c.objects, wall=c.wall)
    t = c.wall()
    c.vars.put("rec/epoch/7", {"epoch": "4"})                                       # the recording's writer is e4 now
    a = _recorder_with_footage(c, "srv-a", "7", 3, ((t - 1200, t - 900), (t - 600, t - 450)))   # before the failure, on A
    b = _recorder_with_footage(c, "srv-b", "7", 4, ((t - 300, t),))                             # after, on B, next epoch
    routes = cluster_routes(ctl)
    try:
        status, tl = routes(None, "GET", "/timeline/7", {"from": t - 2000, "to": t})
        assert status == 200 and isinstance(tl, list)                                # everything answered: a plain list
        assert [(s["recorder"], s["epoch"], s["fenced"]) for s in tl] == [("r-srv-a-1", 3, True), ("r-srv-a-1", 3, True), ("r-srv-b-1", 4, False)]
        # srv-a dies: its recorder goes silent, nobody else can hold srv-a's disk — its footage is unavailable, by name
        c.wall.advance(60); b.heartbeat_once()
        status, tl = routes(None, "GET", "/timeline/7", {"from": t - 2000, "to": t})
        assert [s["recorder"] for s in tl["segments"]] == ["r-srv-b-1"]
        assert [(g["volume"], g["server"]) for g in tl["unavailable"]] == [("srv-a", "srv-a")]
        assert "unavailable until a recorder holds it again" in tl["note"] and "not lost" in tl["note"]
        # srv-a returns: its volume came back with its disks — nothing was rebuilt, nothing copied
        a.heartbeat_once()
        status, tl = routes(None, "GET", "/timeline/7", {"from": t - 2000, "to": t})
        assert isinstance(tl, list) and len(tl) == 3
    finally:
        for r in (a, b):
            r.after_stop()


def test_the_resource_policy_needs_neither_worker_nor_controller_and_touches_no_footage():
    """The resource retains each subsystem's buckets by its own row. Footage is not on its tree: a recording's
    retention is a ceiling on what its door shows, and its volume is a ring that keeps what fits."""
    from vms.archive import event_log
    c = Cluster()
    srv = c.servers["srv-a"]; t = c.wall()
    event_log(srv.archive, 1, 1).append(t - 3 * 86400, "motion")                    # three days old…
    event_log(srv.archive, 1, 1).append(t - 60, "motion")
    c.vars.put("vms/retention/1", {"days": "1"})                                     # …past camera 1's one day
    r = _recorder_with_footage(c, "srv-a", "1", 1, ((t - 3 * 86400, t - 3 * 86400 + 600),))
    rep = srv.res.pass_()
    assert rep["removed"] == 1 and rep["space"] == "off"
    assert r.store.coverage("1") == [(t - 3 * 86400, t - 3 * 86400 + 600)]          # the volume is not the resource's
    r.after_stop()


def test_a_worker_with_no_assignment_invents_nothing():
    c = Cluster(); w = c.worker("srv-c")
    assert w.reconcile_once() == [] and w.name == "w-srv-c-1"
    w.heartbeat_once()
    hb = json.loads(c.objects.get("vms/heartbeats/w-srv-c-1"))
    assert hb["status"] == [] and hb["headroom"] == 50


def test_the_timeline_route_asks_for_a_camera_and_answers_with_its_recordings():
    """`/timeline/<id>` names a CAMERA, and the console turns it into every recording of it (`recordings_of`) —
    named, not numbered: `7-main` on one server and `7-backup` on another are two recordings of camera 7, each
    in its own volume, each served by its own recorder. A route that parsed a recording's id as a number would
    answer 500 to the first `7-backup`."""
    c = Cluster(); ctl = ClusterController(c.vars, c.objects, wall=c.wall)
    rec = SpecController(REC_SPEC, c.vars, c.objects, wall=c.wall)
    rec.create({"name": "7-main", "cam": "7"}); rec.create({"name": "7-backup", "cam": "7"})
    t = c.wall()
    a = _recorder_with_footage(c, "srv-a", "7-main", 1, ((t - 1200, t - 600),))
    b = _recorder_with_footage(c, "srv-b", "7-backup", 1, ((t - 600, t),))
    try:
        status, tl = cluster_routes(ctl, rec)(None, "GET", "/timeline/7", {"from": t - 2000, "to": t})
        assert status == 200 and sorted((s["recording"], s["recorder"]) for s in tl) == [("7-backup", "r-srv-b-1"), ("7-main", "r-srv-a-1")]
        assert {s["media"] for s in tl} == {"/export/7?rec=7-main", "/export/7?rec=7-backup"}
    finally:
        a.after_stop(); b.after_stop()

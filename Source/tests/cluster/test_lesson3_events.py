"""Lesson 3, second half — events. Written by the worker holding a unit's
epoch into the unit's bucket on its server's resource; any subsystem, its
own prefix; indexed by EACH RESOURCE over its own tree — a cache that proves
it by being deleted and rebuilt — and merged by the console, which holds
none; unavailable — by name — when the resource is, never lost; a detector's
event about camera 7 found by a field, not by living in camera 7's bucket."""
import os
from w2cplatform.eventdatabase import EventIndex, MergedIndex
from cluster.resource import peers_of, resources_seen
from vms.archive import event_log
from w2cplatform.events import EventLog, buckets_under, subsystems_under
from tests.cluster.conftest import Cluster, host

B = 600


def _observe(c, server, sub, unit, epoch, t, kind, **fields):
    """A worker of `sub` holding `unit`'s epoch on `server` observed something."""
    return EventLog(c.servers[server].archive, sub, unit, epoch, B).append(t, kind, **fields)


def _resources(c):
    """Each server's resource unit, heartbeating — the stand's own, its peers the other servers (`StandPeers`)."""
    return c.resources_up()


def _index(c, rs, server):
    """What the resource job holds: its EventIndex over ITS tree — nothing rebuilt; the job's `/events` answers from it."""
    return rs[server].index.listing()


def _merged(c, rs):
    """The console's side: no index — `GET <resource>/events` on every live resource, here a call instead of HTTP."""
    def fetch(url, p):
        s = host(url)
        if c.servers[s].down:
            raise ConnectionError(s)
        return rs[s].index.query(float(p["from"]), float(p["to"]), int(p["cam"]) if "cam" in p else None, p.get("kind"),
                                 p.get("subsystem"), p.get("unit"), limit=int(p.get("limit", 1000)))
    m = MergedIndex(c.objects, fetch=fetch, wall=c.wall)
    m.SEEN_FOR = 0.0          # these tests move only the wall: each query reads the resources afresh (the cache: М10's Lesson 13)
    return m


def test_events_are_indexed_by_each_resource_and_merged_by_the_console_which_holds_none():
    c = Cluster(); t = c.wall() - 3600
    _observe(c, "srv-a", "vms", "7", 3, t + 12, "motion", zone="gate")            # the VMS worker, recording camera 7
    _observe(c, "srv-a", "vms", "7", 3, t + 40, "silent")
    _observe(c, "srv-b", "vms", "7", 4, t + 1205, "motion")                        # after a failover: next epoch, other server, not recording
    _observe(c, "srv-c", "det", "d-12", 1, t + 30, "person", cam=7, score=0.9)   # a detector on a GPU server, ABOUT camera 7
    _observe(c, "srv-c", "lpr", "lane-1", 1, t + 5, "plate", plate="AB123")      # a third subsystem, its own prefix
    rs = _resources(c)
    assert resources_seen(c.objects)["srv-c"]["units"] == {"det": ["d-12"], "lpr": ["lane-1"]}
    # one index per resource, over its own tree only — nothing cluster-wide
    reps = {s: _index(c, rs, s) for s in rs}
    assert reps["srv-a"] == {"units": 1, "buckets": 1, "mirrored": [], "cached": 0} and rs["srv-a"].index.state == "live"
    assert reps["srv-c"] == {"units": 2, "buckets": 2, "mirrored": [], "cached": 0}
    assert [e["server"] for e in rs["srv-a"].index.query(t, t + 3600)["events"]] == ["srv-a", "srv-a"]
    # the console merges by time, and fences by the epochs only the cluster's rows know
    m = _merged(c, rs)
    q = m.query(t, t + 3600, cam=7, current_epochs={("vms", "7"): 4})
    assert q["state"] == "live" and [(e["subsystem"], e["unit"], e["kind"], e["server"], e["epoch"], e["fenced"]) for e in q["events"]] == [
        ("vms", "7", "motion", "srv-a", 3, True), ("det", "d-12", "person", "srv-c", 1, False),
        ("vms", "7", "silent", "srv-a", 3, True), ("vms", "7", "motion", "srv-b", 4, False)]
    assert q["events"][1]["score"] == 0.9 and q["events"][1]["bucket"].startswith("det/d-12/e1/")   # found by the field; it lives in ITS bucket
    assert [e["plate"] for e in m.query(t, t + 3600, subsystem="lpr")["events"]] == ["AB123"]
    assert [e["cam"] for e in m.query(t, t + 3600, kind="motion")["events"]] == [7, 7]
    # the index holds nothing of its own: a resource job restarted answers the same, from its tree alone
    before = rs["srv-a"].index.query(t, t + 3600)["events"]
    again = EventIndex(c.servers["srv-a"].archive, "srv-a", wall=c.wall, bucket_seconds=B)
    assert again.query(t, t + 3600)["events"] == before
    # a new bucket on srv-c is on the merged timeline in the next answer — nobody tailed it, nobody was told
    _observe(c, "srv-c", "det", "d-12", 1, t + 700, "person", cam=9)
    assert [e["cam"] for e in m.query(t, t + 3600, kind="person")["events"]] == [7, 9]


def test_a_dead_resource_makes_the_answer_incomplete_by_name_not_wrong():
    c = Cluster(); t = c.wall() - 3600
    _observe(c, "srv-a", "vms", "7", 3, t + 12, "motion")
    _observe(c, "srv-b", "vms", "8", 1, t + 20, "motion")
    rs = _resources(c)
    for s in rs: _index(c, rs, s)
    c.wall.advance(60); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()                  # srv-a went silent
    m = _merged(c, rs)
    assert [e["cam"] for e in m.query(t, t + 3600)["events"]] == [8] and m.state == "live; srv-a unreachable"   # unavailable, and the state says so
    rs["srv-a"].heartbeat()
    assert [e["cam"] for e in m.query(t, t + 3600)["events"]] == [7, 8] and m.state == "live"   # back with its disks: its database answers again, nothing rebuilt
    c.servers["srv-b"].down = True                                                     # live by heartbeat, not answering: named too
    assert [e["cam"] for e in m.query(t, t + 3600)["events"]] == [7] and m.state == "live; srv-b unreachable"
    c.servers["srv-b"].down = False
    # retention on srv-b removed a bucket: ITS index lets it go, by (server, path) — the console is not told, it asks
    c.vars.put("vms/retention/8", {"days": "0.01"})
    assert rs["srv-b"].retain() == 1 and [e["cam"] for e in m.query(t, t + 3600)["events"]] == [7]
    assert c.vars.list("vms/events") == [] and c.objects.list("vms/events") == []   # no controller, no index store, wrote an event


def test_the_resource_policy_retains_each_subsystems_buckets_by_its_own_row():
    from cluster.controller import ClusterController
    c = Cluster(); ctl = ClusterController(c.vars, c.objects, wall=c.wall); srv = c.servers["srv-a"]
    ctl.create_camera({"source": "driverpack://file/7.mp4", "events_retention_days": 30})       # the camera's events: the VMS row's knob
    assert c.vars.get("vms/retention/1")[0] == {"days": "30"}                     # the VMS's policy for its unit, as a row the platform reads
    assert c.vars.get("rec/recordings/1")[0] is None                              # no recording: the camera is watched, its footage nobody's
    now = c.wall()
    p1 = _observe(c, "srv-a", "vms", "1", 1, now - 40 * 86400, "motion")       # older than the VMS's policy
    p2 = _observe(c, "srv-a", "vms", "1", 1, now - 3600, "motion")             # recent
    p3 = _observe(c, "srv-a", "det", "d-1", 1, now - 400 * 86400, "person")   # another subsystem: a year by default
    for p in (p1, p2, p3): os.utime(p, (now - 100, now - 100))
    rep = srv.res.pass_()
    assert rep["removed"] == 2 and os.path.exists(p2) and not os.path.exists(p1) and not os.path.exists(p3)
    assert not any(k.startswith("rec.") for k in rep)                            # no footage here: nothing of the recorder's to pass over
    assert not os.path.exists(os.path.join(srv.archive, "rec"))                   # events are the worker's tree (vms/); footage is in a volume


def test_the_events_knob_is_a_peer_copy_and_the_owner_restores():
    """The storage knob's events row, as a copy between resources — no store in
    between. Off: a silent server's events are unavailable by name. On: each
    resource copied its CLOSED buckets to the next live resource after it, and
    a fresh merge answers completely from the peer, saying so. Back with an
    empty disk, the owner pulls its buckets home; nobody else ever writes them."""
    from w2cplatform.resource import MIRROR_KEY, mirrored_buckets
    import shutil
    assert peers_of("srv-a", ["srv-a", "srv-b", "srv-c"], 1) == ["srv-b"] and peers_of("srv-c", ["srv-a", "srv-b", "srv-c"], 1) == ["srv-a"]
    assert peers_of("srv-b", ["srv-a", "srv-b", "srv-c"], 2) == ["srv-c", "srv-a"] and peers_of("srv-a", ["srv-a"], 1) == []
    c = Cluster(); t = c.wall() - 7200
    _observe(c, "srv-a", "vms", "7", 3, t + 12, "motion", zone="gate")
    _observe(c, "srv-a", "det", "d-12", 1, t + 30, "person", cam=7)
    _observe(c, "srv-a", "vms", "7", 3, t + 6800, "motion")                      # in the OPEN bucket: not closed, not mirrored
    _observe(c, "srv-b", "vms", "8", 1, t + 20, "motion")
    pol = hbs = _resources(c)
    assert pol["srv-a"].pass_()["enabled"] is False and mirrored_buckets(c.servers["srv-b"].archive, "srv-a") == []   # knob off: nothing leaves
    c.vars.put(MIRROR_KEY, {"enabled": "true", "copies": "1"})                                       # the knob: one row
    r = pol["srv-a"].pass_(); assert (r["mirrored"], r["peers"]) == (2, ["srv-b"])                        # a -> b, closed buckets only
    r = pol["srv-b"].pass_(); assert (r["mirrored"], r["peers"]) == (1, ["srv-c"])                        # b -> c
    assert pol["srv-a"].pass_()["mirrored"] == 0                                                          # exactly once: the peer said what it holds
    for hb in hbs.values(): hb.heartbeat()
    assert resources_seen(c.objects)["srv-b"]["mirrors"] == {"srv-a": 2} and resources_seen(c.objects)["srv-c"]["mirrors"] == {"srv-b": 1}
    assert [b.path for b in mirrored_buckets(c.servers["srv-b"].archive, "srv-a")][0].startswith("det/d-12/e1/")   # the ORIGINAL path, under .mirror/srv-a/
    assert ".mirror" not in subsystems_under(c.servers["srv-b"].archive)
    # srv-b's own index covers the copies it holds — under srv-a's name, since only the source differs
    rep = _index(c, rs := pol, "srv-b")
    assert rep == {"units": 3, "buckets": 3, "mirrored": ["srv-a"], "cached": 0}   # its own unit and two of srv-a's, a bucket each
    assert [e["server"] for e in rs["srv-b"].index.query(t, t + 7200)["events"]] == ["srv-a", "srv-b", "srv-a"]   # by time; two of them under srv-a's name
    _index(c, rs, "srv-a"); _index(c, rs, "srv-c"); m = _merged(c, rs)
    ev = m.query(t, t + 7200, cam=7)["events"]
    assert [(e["subsystem"], e["kind"], e["server"]) for e in ev] == [("vms", "motion", "srv-a"), ("det", "person", "srv-a"), ("vms", "motion", "srv-a")]
    assert m.state == "live"                                                                         # the owner answers, open bucket included; srv-b's copies are dropped
    # srv-a dies
    c.wall.advance(60); hbs["srv-b"].heartbeat(); hbs["srv-c"].heartbeat()
    ev = m.query(t, t + 7200, cam=7)["events"]
    assert [(e["subsystem"], e["kind"], e["server"]) for e in ev] == [("vms", "motion", "srv-a"), ("det", "person", "srv-a")]   # complete, from the peer; the open bucket is the RPO
    assert m.state == "live; srv-a from mirror"
    # srv-a returns — with a REPLACED, empty disk
    shutil.rmtree(c.servers["srv-a"].archive); os.makedirs(c.servers["srv-a"].archive)
    hbs["srv-a"].heartbeat()
    r = pol["srv-a"].restore()
    assert r["pulled"] == 2 and not any(k.startswith("rec.") for k in r)                             # its two closed buckets are home; footage is never here (it is in volumes)
    assert [b.path for b in buckets_under(c.servers["srv-a"].archive, "vms", "7", B)] == [ev[0]["bucket"]]
    hbs["srv-a"].heartbeat()
    assert _index(c, rs, "srv-a")["buckets"] == 2                                                    # its job restarts: the index over the restored tree
    ev2 = m.query(t, t + 7200, cam=7)["events"]
    assert [(e["kind"], e["server"], e["bucket"]) for e in ev2] == [(e["kind"], e["server"], e["bucket"]) for e in ev] and m.state == "live"   # the owner is the source again; no duplicates
    assert c.objects.list("platform/mirror") == [] and c.vars.list("vms/mirror") == []               # no store in between, ever; and not the VMS's knob

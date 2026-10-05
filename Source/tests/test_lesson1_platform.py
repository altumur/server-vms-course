"""Lesson 1 — the subsystem contract, and the platform that knows nothing."""
import os
import threading
from w2cplatform.contract import Assignment, Controller, Heartbeat, Subsystem
from w2cplatform.worker import Worker
from w2cplatform.epoch import Lease, current_epoch, next_epoch
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.variables import Conflict, FileVariables, Forbidden
from tests.conftest import Box, Clock, console_ctl, controller_ctl, counter_worker


def test_the_config_store_survives_a_restart_and_refuses_a_stale_cas():
    box = Box()
    idx = box.vars.put("testsub/counters/gate", {"name": "gate", "revision": 1}, cas=0)
    assert idx == 1001
    again = FileVariables(box.vars.root)                       # a new process, same directory
    items, idx2 = again.get("testsub/counters/gate")
    assert items == {"name": "gate", "revision": "1"} and idx2 == idx
    try:
        again.put("testsub/counters/gate", {"name": "x"}, cas=idx - 1); raise AssertionError("must conflict")
    except Conflict:
        pass
    assert again.put("testsub/counters/gate", {"name": "x"}, cas=idx) == 1002
    assert again.list("testsub/") == ["testsub/counters/gate"] and again.get("nope") == (None, 0)


def test_two_processes_one_cas_winner():
    box = Box()
    results = []
    def race(n):
        v = FileVariables(box.vars.root)                       # each "process" opens the store itself
        for _ in range(40):
            items, idx = v.get("counter")
            try:
                v.put("counter", {"n": int(items["n"]) + 1 if items else 1}, cas=idx); results.append(n)
            except Conflict:
                pass
    ts = [threading.Thread(target=race, args=(i,)) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    n = int(box.vars.get("counter")[0]["n"])
    assert n == len(results)                                   # every successful write counted exactly once


def test_one_writer_per_prefix():
    box = Box()
    ctl = box.vars.as_writer("testsubcontroller", ["testsub/*"])
    wrk = box.vars.as_writer("testsubworker-1", ["testsub/epoch/*"])
    ctl.put("testsub/counters/gate", {"name": "gate"})
    wrk.put("testsub/epoch/gate", {"epoch": 1})
    try:
        wrk.put("testsub/counters/gate", {"name": "mine now"}); raise AssertionError("a worker never writes configuration")
    except Forbidden:
        pass


def test_epoch_issuer_never_reuses_a_number():
    box = Box()
    issued = []
    def race():
        v = FileVariables(box.vars.root)
        for _ in range(25):
            issued.append(next_epoch(v, "testsub/epoch/gate")[0])
    ts = [threading.Thread(target=race) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(issued) == list(range(1, 101)) and current_epoch(box.vars, "testsub/epoch/gate") == 100


def test_lease_on_a_monotonic_clock():
    box = Box(); clk = Clock()
    e, _ = next_epoch(box.vars, "testsub/epoch/gate")
    lease = Lease(box.vars, "testsub/epoch/gate", e, ttl=30, margin=5, clock=clk)
    clk.advance(24.9); assert lease.may_act()
    clk.advance(0.2);  assert not lease.may_act() and lease.seconds_left() == 0
    assert lease.renew() and lease.may_act()
    next_epoch(box.vars, "testsub/epoch/gate")                 # somebody else took counter gate
    assert lease.renew() is False and lease.fenced and lease.conflicts == 1


def test_the_platform_knows_nothing_about_its_subsystems():
    """No import of a subsystem's package anywhere under w2cplatform/ — and not even the word for the unit of a
    subsystem whose package carries its spec, whatever that spec calls it (`test_boundary.py` holds the platform's
    whole tree to every word of the product)."""
    from tests.test_boundary import ROOT, SUBSYSTEM_PACKAGES
    here = os.path.join(ROOT, "w2cplatform")
    specs = [os.path.join(ROOT, p, f"{p}.subsystem.yaml") for p in SUBSYSTEM_PACKAGES]
    units = [SubsystemSpec.load(s).rows.rstrip("s") for s in specs if os.path.exists(s)]
    assert units, "no subsystem package carries its own spec"
    for f in os.listdir(here):
        if f.endswith(".py"):
            src = "\n".join(l for l in open(os.path.join(here, f)) if not l.lstrip().startswith("#"))   # the code, not the notes
            for p in SUBSYSTEM_PACKAGES:
                assert f"from {p}" not in src and f"import {p}" not in src, (f, p)
            if f != "__init__.py":
                assert not [u for u in units if u in src.lower()], f     # not even the word
    sub = Subsystem("testsub")
    assert sub.assignment("w-1") == "testsub/workers/w-1" and sub.epoch_key("7") == "testsub/epoch/7"
    assert sub.heartbeat_key("w-1") == "testsub/heartbeats/w-1" and sub.acl_controller() == ["testsub/*"]


def test_controller_and_worker_bases_speak_only_the_contract():
    box = Box()
    sub = Subsystem("thing")
    ctl = Controller(sub, box.vars, box.objects, wall=box.wall)
    w = Worker(sub, "t-1", box.vars, box.objects, clock=box.clock, wall=box.wall)
    assert ctl.workers_seen() == {}                            # nobody has heartbeaten
    w.heartbeat([{"id": 1, "phase": "running"}], server="srv-1")
    seen = ctl.workers_seen()
    assert list(seen) == ["t-1"] and seen["t-1"].extra["server"] == "srv-1"
    a = ctl.assign("t-1", ["3", "1", "2"])
    assert a.units == ["1", "2", "3"] and a.rev == 1 and w.assignment().units == ["1", "2", "3"]
    assert ctl.assign("t-1", ["1"]).rev == 2
    assert w.take_epoch("1") == 1 and w.may_act("1")
    box.wall.advance(100)
    assert ctl.workers_seen(max_age=45) == {}                  # a silent worker is not a worker


def test_identity_by_claim_is_a_platform_piece():
    """A name is a slot: taken by CAS, renewed, released on purpose or lapsed
    by silence. Two processes claiming without a preference get two names;
    a third, after the first lapsed, gets the first's name back — and with
    it, its assignment — once the margin past the lapse is out, when the
    controller would move that assignment too (the review's twelfth pass,
    blocker 2). The controller hands nothing out — but it says which names are
    given: it has watched the slots, and a worker that never said where it runs
    is `wait`, whose name stays until the controller's limit (the thirteenth
    pass, blockers 2 and 4; `Controller.publish_names`)."""
    from w2cplatform.contract import HUNG_MOVE_AFTER
    box = Box()
    sub = Subsystem("thing")
    ctl = Controller(sub, box.vars, box.objects, wall=box.wall)
    a = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="A")
    b = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="B")
    assert a.claim_slot() == "w-1" and b.claim_slot() == "w-2"        # `count = 2`: two names, in order
    ctl.assign("w-1", ["1", "2"])
    assert a.renew_slot() and b.renew_slot()
    ctl.look()                                                         # the controller sees them renewed
    box.wall.advance(91 + HUNG_MOVE_AFTER)                             # A went silent: the slot's TTL, the margin, the limit
    assert b.renew_slot()
    assert list(ctl.publish_names()["names_given"]) == ["w-1"]         # B's renewal is new to it: B's name stays
    c = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="C")
    assert c.claim_slot() == "w-1" and c.assignment().units == ["1", "2"]   # the replacement inherits
    assert not a.renew_slot()                                          # A, if it is still alive, finds out
    assert ctl.released_slots() == []                                  # a lapse is not a release
    b.release_slot()                                                   # scale-in: B is told to stop and says so
    ctl.assign("w-2", ["3"])
    assert ctl.released_slots() == ["w-2"]                             # what the subsystem redistributes
    d = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="D")
    assert d.claim_slot(prefer="w-7") == "w-7"                         # the scheduler's index wins, and creates
    assert sorted(ctl.slots()) == ["w-1", "w-2", "w-7"] and sub.slot_key("w-1") == "thing/slots/w-1"
    assert sub.acl_worker() == ["thing/epoch/*", "thing/slots/*", "thing/holds/*"]   # what it is, and where it writes


def test_a_named_unit_deleted_comes_back_under_its_name():
    """Create, delete, create again under the same name. The row is marked, not
    removed, so the second create is neither "exists" nor a create-only write:
    it is a fresh row one revision on from the old one, by CAS on what it read.
    The revision has to keep growing — a reader that remembered 2 and sees 1
    concludes the row rolled back — and no tombstone may survive the comeback."""
    box = Box()
    spec = SubsystemSpec.from_dict({
        "name": "thing",
        "unit": {"rows": "u", "id": "name", "fields": {"name": {"type": "string"}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}},
    })
    ctl = SpecController(spec, box.vars, box.objects, wall=box.wall)

    r = ctl.create({"name": "gate"})
    assert r["revision"] == 1 and ctl.unit("gate")["name"] == "gate"
    assert ctl.ensure_placed(workers=["w-1"])[0].worker == "w-1"

    ctl.delete("gate")
    assert ctl.unit("gate") is None                       # gone for every reader
    assert ctl.unplace_deleted() == ["gate"] and ctl.where("gate") is None

    back = ctl.create({"name": "gate"})                   # the operator switches it on again
    assert back["revision"] == 2, "the revision restarted: a reader that saw 2 will read this as a rollback"
    assert ctl.unit("gate") is not None                   # no tombstone survived the comeback
    assert ctl.vars.get("thing/u/gate")[0].get("deleted") != "true"
    assert ctl.ensure_placed(workers=["w-1"])[0].worker == "w-1"   # and it is placed again


def test_the_resource_is_a_platform_job_that_mirrors_any_subsystems_buckets():
    """Two resources on one box (two roots), one raft. The knob is one Variable;
    each resource copies its CLOSED buckets — whatever subsystem wrote them — to
    the next live resource after it; a resource back with an empty disk pulls
    its own buckets home. Nothing here knows what a bucket is about."""
    import os, shutil, tempfile
    from w2cplatform.events import EventLog, buckets_under
    from w2cplatform.resource import MIRROR_KEY, Resource, mirrored_buckets, peers_of, resources_seen
    box = Box(); t = box.wall() - 7200
    roots = {s: tempfile.mkdtemp(prefix=f"res-{s}-") for s in ("srv-a", "srv-b", "srv-c")}

    class Local:                                     # PeerClient's three calls, against directories
        def mirrored(self, url, server): return mirrored_buckets(roots[url], server)
        def put(self, url, server, path, data):
            p = os.path.join(roots[url], ".mirror", server, path); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(data)
        def get(self, url, server, path): return open(os.path.join(roots[url], ".mirror", server, path), "rb").read()

    res = {s: Resource(r, s, s, box.vars, box.objects, wall=box.wall, peers=Local()) for s, r in roots.items()}
    EventLog(roots["srv-a"], "thing", "x", 1).append(t + 5, "tick", n=1)         # some subsystem's bucket, closed
    EventLog(roots["srv-a"], "other", "y", 2).append(t + 9, "seen")               # another's
    EventLog(roots["srv-a"], "thing", "x", 1).append(t + 7000, "tick", n=2)      # the open one
    for r in res.values(): r.heartbeat()
    assert resources_seen(box.objects)["srv-a"]["units"] == {"other": ["y"], "thing": ["x"]}
    assert peers_of("srv-a", list(res), 1) == ["srv-b"] and peers_of("srv-c", list(res), 1) == ["srv-a"]
    assert res["srv-a"].pass_()["enabled"] is False                              # knob off: nothing leaves
    box.vars.put(MIRROR_KEY, {"enabled": "true", "copies": "1"})
    r = res["srv-a"].pass_(); assert (r["mirrored"], r["peers"]) == (2, ["srv-b"])
    assert res["srv-a"].pass_()["mirrored"] == 0                                  # once
    res["srv-b"].heartbeat()
    assert resources_seen(box.objects)["srv-b"]["mirrors"] == {"srv-a": 2}
    assert ".mirror" not in res["srv-b"].units()                                  # a copy is not srv-b's data
    shutil.rmtree(roots["srv-a"]); os.makedirs(roots["srv-a"])                    # srv-a back with a replaced disk
    assert res["srv-a"].restore()["pulled"] == 2
    assert [b.events for b in buckets_under(roots["srv-a"], "thing", "x", 600)] == [1]   # the closed one is home; the open one was the RPO
    box.vars.put("other/retention", {"days": 1})
    box.wall.advance(3 * 86400)
    assert res["srv-a"].retain() == 1 and buckets_under(roots["srv-a"], "other", "y", 600) == []   # each subsystem's days, from its own row


def test_a_worker_that_released_its_slot_stops_receiving_units():
    """Deregistration, the one thing a service catalogue has that a heartbeat does not.

    A worker that lets go of its slot has said it is leaving. Its heartbeat is still
    seconds old and will stay "live" for `lost_after`, so without this the controller
    keeps placing NEW units on a process on its way out — and the next pass moves them
    off again. Churn at every scale-in and every rolling update. `redistribute` already
    read `Slot.released`; placement did not."""
    box = Box()
    ctl, con = controller_ctl(box), console_ctl(box)
    w1 = counter_worker(box, "w-1", server="srv-1")
    w2 = counter_worker(box, "w-2", server="srv-2")
    w1.heartbeat_once(); w2.heartbeat_once()

    w1.heartbeat_once(); w1.release_slot()                    # an orderly stop: a last word, then let go
    assert "w-1" in ctl.workers_seen()                        # still in the catalogue: its heartbeat is seconds old
    con.create({"name": "c1"})
    assert ctl.ensure_placed()[0].worker == "w-2"             # …and still not a place to put work


def test_a_subscriber_is_not_handed_a_holder_that_has_gone_silent():
    """`heartbeats()` returns every last word whatever its age — the read model wants the
    stale ones, to show them muted. A SUBSCRIBER wants only who is reachable, and each of
    the four that ask (three subsystems' workers and the console) used to decide that for
    itself: three leant on a dead worker's last `phase: running`, the fourth checked
    nothing. `holders()`/`holder_of()` put the filter in the catalogue, where it cannot
    be forgotten."""
    from w2cplatform.console import heartbeats, holder_of, holders

    box = Box()
    ctl, con = controller_ctl(box), console_ctl(box)
    w = counter_worker(box, "w-1", server="srv-1")
    w.heartbeat_once(); con.create({"name": "c1"}); ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()

    assert holder_of(box.objects, "testsub/", "c1", box.wall(), phase="running", field="epoch") is not None

    box.wall.advance(60)                                      # the holder stops saying anything
    assert heartbeats(box.objects, "testsub/")["w-1"].status[0]["phase"] == "running"   # its LAST word still says so
    assert holders(box.objects, "testsub/", box.wall()) == {}                            # …and it is not reachable
    assert holder_of(box.objects, "testsub/", "c1", box.wall(), phase="running", field="epoch") is None


def _counter(name: str = "counter"):
    """A subsystem that frees — `requests: {free: true}` — registered in this process's catalogue, as a loaded spec is."""
    from w2cplatform import catalog
    spec = SubsystemSpec.from_dict({"name": name, "unit": {"rows": "ticks", "id": "name", "fields": {"name": {"type": "string"}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}}, "requests": {"free": True}})
    catalog.register(spec)
    return spec


def test_the_watermark_asks_and_never_deletes():
    """Lesson 21. The resource measures the DISK (a test cannot fill one, so the probe
    is a seam), and over the high mark it says how many bytes to free — down to the LOW
    mark, or the next write puts it straight back over. What to give up is the
    subsystem's to decide: the platform ASKS, by a request row of the subsystem's own
    family (`requests: {free: true}`: `<sub>/requests/free-<server>-<volume>`), reads
    what its workers on this server say they freed, and touches nothing itself (the
    boundary's step 6: it called the subsystem's `free`, code of the subsystem's in the
    resource's pass).

    The subsystem here keeps no files and no buckets — it counts. Nothing in this test
    knows what any subsystem's unit is, which is the point of the door being a row."""
    import tempfile
    from w2cplatform.resource import SPACE_KEY, Resource

    spec = _counter()
    box = Box()
    res = Resource(tempfile.mkdtemp(prefix="space-"), "srv-1", "http://srv-1", box.vars, box.objects,
                   wall=box.wall, space_probe=lambda root: (1_000_000, 500_000))
    [vol] = list(res.volumes)
    asked = lambda: box.vars.get(spec.sub.request_key(f"free-srv-1-{vol}"))[0]

    assert res.relieve() == {"space": "off"}                   # a knob, and it is off until an operator says otherwise
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75"}, cas=0)
    assert res.relieve() == {"space": "ok", "full": 0.5} and asked() is None
    assert res.heartbeat()["space"] == {"total": 1_000_000, "free": 500_000, "used": 500_000, "full": 0.5}

    res.space_probe = lambda root: (1_000_000, 100_000)        # 90 % full
    rep = res.relieve()
    assert asked()["free"] == "150000" and asked()["volume"] == vol   # to the LOW mark, not to the high one
    assert rep["space"] == "over" and rep["need"] == 150_000 and rep["freed"] == 0 and rep["short"] == 150_000
    # its worker on this server gave up three ticks of fifty kB, and says so in its heartbeat
    box.objects.put(spec.sub.heartbeat_key("t-1"), Heartbeat("t-1", box.wall(), [], {"server": "srv-1",
                                                                                     "freed": {vol: 150_000}}).to_bytes())
    rep = res.relieve()
    assert rep["freed"] == 150_000 and rep["short"] == 0 and rep["counter.freed"] == 150_000

    # and a subsystem that does not free is simply not asked: `retain` by days is its whole policy
    other = SubsystemSpec.from_dict({"name": "other", "unit": {"rows": "units", "id": "name", "fields": {}},
                                     "placement": {"capacity": {"from": "capacity", "default": 4}}})
    assert box.vars.list(other.sub.requests_prefix()) == []
    res.space_probe = lambda root: (1_000_000, 500_000)        # back under the mark: nothing asked of anybody
    assert res.relieve()["space"] == "ok" and asked() is None


def test_the_tree_is_walked_once_a_pass_and_never_on_a_heartbeat():
    """Lesson 21's other half. `usage` answers "how much do we hold" and can only be
    answered by walking; `space` answers "how much is left" and is one syscall. The
    first is measured with the policy pass and published from the cache with the time
    it was taken; the second is live in every heartbeat.

    At fifty units writing ten-minute segments a month of the tree is a quarter of a
    million files. Walking them every ten seconds does not merely cost a second — it
    touches every inode in the tree, so the cache holds the tree's metadata instead
    of the data the machine exists to serve."""
    import tempfile
    from w2cplatform.resource import Resource

    box = Box()
    res = Resource(tempfile.mkdtemp(prefix="usage-"), "srv-1", "http://srv-1", box.vars, box.objects,
                   wall=box.wall, space_probe=lambda root: (1_000_000, 400_000))
    walks = []
    res.usage = lambda: (walks.append(box.wall()), 4_100_000_000)[1]

    hb = res.heartbeat()                                   # the first one of a process pays for it once
    assert len(walks) == 1 and hb["usage"] == 4_100_000_000 and hb["usage_at"] == box.wall()
    box.wall.advance(10)
    for _ in range(59):                                    # ten minutes of heartbeats, one per ten seconds
        hb = res.heartbeat()
    assert len(walks) == 1                                 # not one more walk
    assert hb["usage_at"] < hb["ts"]                       # and the number says how old it is
    assert hb["space"]["free"] == 400_000                  # while `space` is measured every time

    res.pass_()
    assert len(walks) == 2 and res.usage_at == box.wall()  # the pass is where the walk belongs
    assert res.heartbeat()["usage_at"] == box.wall()


def test_space_does_not_average_across_volumes():
    """A box with three disks is not a box with one big disk.

    Half full across two volumes, one of them at 98%, is a box that stops writing:
    the unit that cannot write is on the full one, and bytes freed on the empty one
    close nothing. So the watermark is per volume, and the volume goes into the ask —
    only the subsystem knows which of its files are where, only the resource knows
    which disk is short."""
    import tempfile
    from w2cplatform.resource import SPACE_KEY, Resource

    spec = _counter()
    box = Box()
    roots = {"vol-a": tempfile.mkdtemp(prefix="vol-a-"), "vol-b": tempfile.mkdtemp(prefix="vol-b-")}
    sizes = {roots["vol-a"]: (1_000_000, 20_000),              # 98 % full
             roots["vol-b"]: (1_000_000, 980_000)}             # all but empty
    res = Resource(None, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall,
                   volumes=roots, space_probe=lambda root: sizes[root])
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75"}, cas=0)

    summed = res.space()
    assert summed["full"] == 0.5, "the box averages out to half full, and that is the number that lies"
    assert res.spaces()["vol-a"]["full"] == 0.98 and res.spaces()["vol-b"]["full"] == 0.02

    rep = res.relieve()
    asked = lambda v: box.vars.get(spec.sub.request_key(f"free-srv-1-{v}"))[0]
    assert asked("vol-a")["free"] == "230000" and asked("vol-b") is None, "asked on the full volume, and only there"
    assert rep["space"] == "over" and [v["volume"] for v in rep["volumes"]] == ["vol-a"]
    assert rep["counter.vol-a.freed"] == 0                     # the report says which disk it was about
    assert res.heartbeat()["volumes"]["vol-a"]["full"] == 0.98


def test_which_volume_holds_a_unit_is_the_directory_and_not_a_map():
    """A map of unit → volume would be a second truth about the disks, and it would
    drift. The unit's directory IS the answer, the same way `subsystems_under` already
    derives what is on this resource at all."""
    import os
    import tempfile
    from w2cplatform.resource import Resource

    box = Box()
    roots = {"vol-a": tempfile.mkdtemp(prefix="vol-a-"), "vol-b": tempfile.mkdtemp(prefix="vol-b-")}
    res = Resource(None, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, volumes=roots,
                   space_probe=lambda root: (1_000_000, 100_000 if root == roots["vol-a"] else 900_000))
    assert res.volume_of("thing", "7") is None                 # nothing written yet: no answer, not a guess
    os.makedirs(os.path.join(roots["vol-b"], "thing", "7"))
    assert res.volume_of("thing", "7") == "vol-b"
    assert res.place_volume() == "vol-b"                       # a new unit goes where there is room
    assert res.units() == {"thing": ["7"]}                     # and the tree is read across volumes


def test_the_schema_is_raised_after_the_upgrade_and_never_during_it():
    """A rolling upgrade means old and new processes read the same rows for a while.
    Adding a field is free; changing what one MEANS is a new schema number — and the
    direction of every check here is what keeps the upgrade rolling.

    A NEWER process against an older store is fine: it understands the old layout, and
    that is the whole of an upgrade. An OLDER process against a newer store refuses to
    start, loudly, rather than quietly dropping fields it does not know on its next
    read-modify-write. And the version is raised once, by the operator, when everything
    is new — never by the first new process, which would lock out every machine not yet
    upgraded and turn a rolling upgrade into an outage."""
    from w2cplatform.contract import (BUILD, SCHEMA, SCHEMA_KEY, Controller, SchemaTooNew,
                                      Subsystem, builds, check_schema, schema_version)
    box = Box()
    ctl = Controller(Subsystem("testsub"), box.vars, box.objects, wall=box.wall)
    assert schema_version(box.vars) == SCHEMA          # absent: a fresh install is whatever this build is

    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA + 1)}, cas=0)     # somebody upgraded the store
    try:
        Controller(Subsystem("testsub"), box.vars, box.objects, wall=box.wall)
        raise AssertionError("an old build started against a newer store")
    except SchemaTooNew as e:
        assert "understands" in str(e)
    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA)}, cas=box.vars.get(SCHEMA_KEY)[1])
    assert check_schema(box.vars) == SCHEMA

    # every process says what it understands, and one scan finds them all — any subsystem, and the resource
    w = counter_worker(box, "w-1", server="srv-1")
    w.heartbeat_once()
    seen = builds(box.objects, box.wall())
    assert seen["testsub/w-1"]["schema"] == SCHEMA and seen["testsub/w-1"]["build"] == BUILD and seen["testsub/w-1"]["live"]

    # raising is refused while anything live understands less: you cannot raise the store out from
    # under a machine you forgot to upgrade
    old = Heartbeat("w-2", box.wall(), [], {"server": "srv-2", "schema": SCHEMA, "build": "old"}).to_bytes()
    box.objects.put("testsub/heartbeats/w-2", old)
    try:
        ctl.set_schema(SCHEMA + 1); raise AssertionError("raised the schema over a running old build")
    except SchemaTooNew as e:
        assert "still running" in str(e) and "testsub/w-2" in str(e)

    box.wall.advance(60); w.heartbeat_once()            # w-2 is gone; w-1 is new and says so
    box.objects.put("testsub/heartbeats/w-1",
                    Heartbeat("w-1", box.wall(), [], {"server": "srv-1", "schema": SCHEMA + 1}).to_bytes())
    assert ctl.set_schema(SCHEMA + 1)["version"] == str(SCHEMA + 1)
    try:
        ctl.set_schema(SCHEMA); raise AssertionError("the schema went back")
    except SchemaTooNew as e:
        assert "does not go back" in str(e)


def test_a_build_the_store_outgrew_while_it_ran_fences_and_does_not_rejoin():
    """The review's second pass, m4. `set_schema` looks for LIVE builds that understand less, and a build that
    passed its check at construction and has not heartbeaten yet is not live to it: the version is raised under a
    process that was told a moment ago it may run. It used to run on, reading rows in a layout it does not know.
    Now the check is repeated where the slot is renewed: the instance fences with the reason, and a fenced
    instance does not rejoin while the store stays ahead of it."""
    from w2cplatform.contract import SCHEMA, SCHEMA_KEY, Controller, SchemaTooNew, Subsystem
    box = Box()
    ctl = Controller(Subsystem("testsub"), box.vars, box.objects, wall=box.wall)
    w = counter_worker(box, None, server="srv-1")
    assert w.name == "w-1" and w.lease_pass() == []                  # claimed its slot, checked the schema — and has not heartbeaten
    ctl.set_schema(SCHEMA + 1)                                       # nobody live understands less: raised
    try:
        w.renew_slot(); raise AssertionError("the slot was renewed against a store this build does not understand")
    except SchemaTooNew:
        pass
    assert w.lease_pass() == [] and not w.writing_allowed and f"schema {SCHEMA + 1}" in w.fenced_reason
    assert w.rejoin() is None and not w.writing_allowed             # nobody to rejoin as while the store is ahead
    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA)}, cas=box.vars.get(SCHEMA_KEY)[1])    # the operator rolled it back
    assert w.rejoin() is not None and w.writing_allowed


def test_a_schema_row_that_does_not_parse_fences_nobody_who_is_running_and_starts_nobody_new():
    """The review's third pass (minor). `platform/schema` is read at every slot renewal, by every process: a hand edit
    that made `version` a word raised out of `renew_slot` everywhere at once — no lease renewed, no heartbeat, the
    whole fleet fenced by one field. A process that already read the schema keeps what it read; one that never did
    refuses to start, as for a newer layout. Only a version that PARSES as newer fences a running build."""
    from w2cplatform.contract import SCHEMA, SCHEMA_KEY, SchemaTooNew
    box = Box()
    w = counter_worker(box, None, server="srv-1")
    assert w.lease_pass() == [] and w.writing_allowed
    box.vars.put(SCHEMA_KEY, {"version": "one"}, cas=0)                              # a hand edit
    assert w.renew_slot() and w.lease_pass() == [] and w.writing_allowed           # running: what it read stands
    try:
        counter_worker(box, None, server="srv-2")
        raise AssertionError("a new process started on a schema it cannot read")
    except SchemaTooNew as e:
        assert "does not parse" in str(e)
    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA + 1)}, cas=box.vars.get(SCHEMA_KEY)[1])
    try:
        w.renew_slot(); raise AssertionError("a newer layout that parses did not fence")
    except SchemaTooNew:
        pass


def test_a_worker_fenced_for_its_slot_rejoins_over_a_garbled_schema_row_and_one_fenced_for_the_schema_does_not():
    """The review's fourth pass (Т-m7's remainder). `renew_slot` keeps the schema it last read whole when the row
    stops parsing, but `rejoin` asked bare — and a bare check refuses a row it cannot read: a worker fenced because
    another instance took its slot never came back while one field of `platform/schema` was garbled. It asks with
    what it last read now. A worker fenced FOR the schema has nothing to keep: a garbled row does not say the store
    came back to its layout, and it stays fenced until a version that parses says so."""
    from w2cplatform.contract import SCHEMA, SCHEMA_KEY, Slot
    box = Box()
    w = counter_worker(box, None, server="srv-1")
    assert w.name == "w-1" and w.lease_pass() == [] and w.writing_allowed
    box.vars.put(w.sub.slot_key("w-1"), Slot("w-1", "somebody-else", box.wall() + 60, False, 9).to_items(),
                 cas=box.vars.get(w.sub.slot_key("w-1"))[1])                # another instance took the slot
    w.lease_pass()
    assert not w.writing_allowed and "held by another instance" in w.fenced_reason
    box.vars.put(SCHEMA_KEY, {"version": "one"}, cas=0)                     # …and a hand edit garbled the schema
    assert w.rejoin() == "w-2" and w.writing_allowed                       # what it read stands: it comes back

    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA + 1)}, cas=box.vars.get(SCHEMA_KEY)[1])
    w.lease_pass()
    assert not w.writing_allowed and f"schema {SCHEMA + 1}" in w.fenced_reason
    box.vars.put(SCHEMA_KEY, {"version": "two"}, cas=box.vars.get(SCHEMA_KEY)[1])   # garbled again, over the newer one
    assert w.rejoin() is None and not w.writing_allowed
    box.vars.put(SCHEMA_KEY, {"version": str(SCHEMA)}, cas=box.vars.get(SCHEMA_KEY)[1])
    assert w.rejoin() is not None and w.writing_allowed

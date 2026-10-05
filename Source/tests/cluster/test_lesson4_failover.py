"""Lesson 4 — failover, and the two instances of one worker. With no orchestrator nothing restarts a process on
another server: a crash is systemd's to restart under the same name on the same server, and a dead server is the
controller's to act on — by assignment, after two silences (the slot out by `SLOT_LOST_AFTER` more, and the resource
on its server silent). The power pull on a fake clock; the old instance waking up; two processes with one name; and
the reassignment window, which is the same window with a different verdict."""
from vms.controller import VmsController
from vms.worker import FakeActuator
from w2cplatform.console import SpecConsole
from tests.cluster.conftest import Cluster


def metrics_text(ctl, worst_failover: float) -> str:
    """What a console's `/metrics` says of `ctl`'s subsystem — the platform's console over the controller."""
    return SpecConsole(ctl, worst_failover=worst_failover).metrics_text()

SLOT_TTL = 45.0             # how long a renewal holds the name (`Worker.slot_ttl`)
LOST_AFTER = 45.0           # the margin past it (`contract.SLOT_LOST_AFTER`): what it started may still be writing


def _recording(n=3, b=True):
    """w-srv-a-1 holds cameras 1..n under epoch 1; w-srv-b-1 is there with room; the controller on srv-b has heard
    both and every server's resource."""
    c = Cluster(); c.resources_up()
    ctl, con = c.controller("srv-b"), c.console("srv-b")
    for i in range(n):
        con.create_camera({"source": f"driverpack://file/{i}.mp4"})
    act = FakeActuator(); a = c.worker("srv-a", actuator=act)
    a.heartbeat_once(); ctl.ensure_placed(); a.reconcile_once(); a.heartbeat_once()
    assert act.running == set(range(1, n + 1)) and act.epochs == {i: 1 for i in range(1, n + 1)}
    other = None
    if b:
        other = c.worker("srv-b", actuator=FakeActuator()); other.heartbeat_once()
    ctl.workers_seen()
    return c, ctl, a, act, other


def _silence(c, dead: str, seconds: float, alive=()):
    """`dead` says nothing for `seconds`: the others renew, heartbeat, and their resources too, every ten seconds."""
    for _ in range(int(seconds // 10)):
        c.wall.advance(10); c.clock.advance(10)          # both clocks: readers judge by their own (13th)
        for name, srv in c.servers.items():
            if name != dead:
                srv.res.heartbeat()
        for w in alive:
            w.lease_pass(); w.heartbeat_once()
    c.wall.advance(seconds % 10); c.clock.advance(seconds % 10)


def test_the_power_pull():
    """srv-a dies at t=0 — its processes, its resource, its disks (its doors answer nothing). Nothing restarts
    w-srv-a-1 anywhere else. For 90 s the controller on srv-b moves nothing: the name is held 45 s, and for 45 s more
    what it started may still be writing. Past both, with srv-a's resource silent, the cameras move by assignment to
    w-srv-b-1, which takes the next epoch for each and records — asking nobody. The controller reads the dead
    server's last heartbeats from what it heard while it lived (`ClusterObjectStore._remembered`)."""
    c, ctl, a, act_a, b = _recording()
    c.servers["srv-a"].down = True
    _silence(c, "srv-a", 80, alive=[b])
    assert ctl.redistribute() == [] and ctl.where(1) == "w-srv-a-1"          # 80 s: within the name and the margin
    _silence(c, "srv-a", 13, alive=[b])
    assert ctl.gone_servers() == {"w-srv-a-1": "srv-a"}
    ctl.pass_once(1)
    assert [ctl.where(i) for i in (1, 2, 3)] == ["w-srv-b-1"] * 3
    assert ctl.placement(1).reason.startswith("server srv-a gone: slot w-srv-a-1 lapsed and its resource silent; ")
    assert b.reconcile_once() == [("start", 1), ("start", 2), ("start", 3)] and b.actuator.epochs == {1: 2, 2: 2, 3: 2}
    assert ctl.objects.missing == ["srv-a"]                                     # named, and what it said last remembered
    assert act_a.epochs == {1: 1, 2: 1, 3: 1}                                    # srv-a's footage is e1, b's e2


def test_a_restart_is_measured_on_one_clock_and_a_name_taken_elsewhere_by_the_readers():
    """The review's ninth pass (the product's sibling D): `started − previous_hb` subtracted one server's clock from
    another's. The same server — systemd starts the unit again — is one clock, the workers' own numbers. A name taken
    on ANOTHER server (by hand: no unit does it) is what the READER saw, by its own clock: when the old instance's
    heartbeat last moved, when the new one was first there; a reader that did not see the old one alive measures
    nothing — it counts it — and a number that is not finite is no number. A name is taken on another server once the
    controller gives it (the thirteenth review, blocker 3): the old server silent, its slot out and the margin past it."""
    from vms.worker import VmsWorker
    c, ctl, a, _, _ = _recording(b=False)
    fresh = VmsController(c.vars, c.objects, wall=c.wall)              # a console started after the failure
    ctl.failover_seconds()                                                  # this one scraped while w-srv-a-1 was alive
    c.wall.advance(SLOT_TTL + LOST_AFTER + 3)                               # srv-a silent, the slot out and the margin
    ctl.pass_once(1)                                                        # the controller gives the name
    v = c.door("vmsworker")
    b = VmsWorker(None, v, c.objects_on("srv-b", v), FakeActuator(), env=c.env("srv-b", "w-srv-a-1"), clock=c.clock,
                  wall=lambda: c.wall() - 600.0)                            # srv-b's clock: 10 min behind
    b.reconcile_once(); b.heartbeat_once()
    assert ctl.failover_seconds() == {"w-srv-a-1": 93.0}                    # by the reader's clock — not −507
    assert fresh.failover_seconds() == {} and fresh.failovers_unmeasured == 1
    assert "vms_failovers_unmeasured 1" in metrics_text(fresh, 0.0)
    # the same server: one clock, the workers' own numbers (`started − previous_hb`)
    c2, ctl2, a2, _, _ = _recording(b=False)
    c2.wall.advance(31)
    again = c2.worker("srv-a"); again.reconcile_once(); again.heartbeat_once()
    assert VmsController(c2.vars, c2.objects, wall=c2.wall).failover_seconds() == {"w-srv-a-1": 31.0}
    assert 'vms_failover_seconds{kind="worst"} 31.0' in metrics_text(VmsController(c2.vars, c2.objects, wall=c2.wall), 0.0)
    # a number that is not one: not said, counted — and the worst stays the worst this reader measured
    from w2cplatform.contract import Heartbeat
    hb = Heartbeat.from_bytes(again.objects.get("vms/heartbeats/w-srv-a-1"))
    again.objects.put("vms/heartbeats/w-srv-a-1", Heartbeat("w-srv-a-1", hb.ts, hb.status, {**hb.extra, "previous_hb": "-inf"}).to_bytes())
    from w2cplatform.rows import FIELDS
    assert ctl2.failover_seconds() == {} and "vms/heartbeats/w-srv-a-1#previous_hb" in FIELDS.bad   # not said: counted once
    assert 'vms_failover_seconds{kind="worst"} 0.0' in metrics_text(ctl2, 0.0)
    c.wall.advance(SLOT_TTL + LOST_AFTER + 5)                               # it fails again, srv-b silent this time
    ctl.pass_once(1)
    third = c.worker("srv-c", name="w-srv-a-1"); third.reconcile_once(); third.heartbeat_once()
    text = metrics_text(ctl, 0.0)
    assert 'vms_failover_seconds{kind="last",worker="w-srv-a-1"} 95.0' in text and 'vms_failover_seconds{kind="worst"} 95.0' in text
    import sys
    sys.modules["w2cplatform.rows"].forget()          # the counts are the process's: every later heartbeat would carry them


def test_one_silence_moves_nothing_and_two_silences_move_the_cameras_under_either_policy():
    """One silence — a process that lives and says nothing, its resource answering and naming it running — moves
    nothing: it is hung, and the unit is systemd's to stop and start again (`WatchdogSec`), under the same name, on the
    same server (a process that ENDED is the next test's). Two silences from one server — the slot out and out by the
    margin, and the resource on that server silent — are a fact about the server, and the controller moves its
    cameras to a worker that is here, under `distinct` (one worker per server carries cameras) and under `shared`
    (the default) alike: there is no orchestrator to bring the process back elsewhere
    (`SpecController._moves_off_silent`)."""
    c, ctl, a, act_a, b = _recording()
    rs = c.resources
    assert ctl.policy() == {"servers": "shared"}                                              # the default: a box is several workers on one server
    assert c.console().set_policy({"servers": "distinct"}) == {"servers": "distinct"}         # the administrator's choice, one row: vms/policy
    assert ctl.assignment("w-srv-b-1").units == []
    # a hang: w-srv-a-1's process lives (its lock in srv-a's tree held) and says nothing; srv-a's resource heartbeats
    c.wall.advance(2 * LOST_AFTER + 3); b.lease_pass(); b.heartbeat_once(); rs["srv-a"].heartbeat(); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    assert ctl.slots()["w-srv-a-1"].lapsed(c.wall()) and ctl.gone_servers() == {} and ctl.redistribute() == []   # one silence: left alone
    # the power pull: srv-a is gone — its worker and its resource both silent
    c.wall.advance(2 * LOST_AFTER + 3); b.lease_pass(); b.heartbeat_once(); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    assert ctl.gone_servers() == {"w-srv-a-1": "srv-a"}
    moves = ctl.redistribute()
    assert [(m[1], m[2]) for m in moves] == [("w-srv-a-1", "w-srv-b-1")] * 3
    assert ctl.placement(1).reason.startswith("server srv-a gone: slot w-srv-a-1 lapsed and its resource silent; ") and ctl.placement(1).reason.endswith("; on srv-b")
    assert b.reconcile_once() == [("start", 1), ("start", 2), ("start", 3)] and b.actuator.epochs == {1: 2, 2: 2, 3: 2}   # the next epoch, on srv-b
    b.heartbeat_once()
    assert ctl.assignment("w-srv-a-1").units == [] and ctl.where(1) == "w-srv-b-1"
    # srv-a returns: its unit claims w-srv-a-1 again, reads an empty assignment, records nothing; nothing moves back
    rs["srv-a"].heartbeat(); a2 = c.worker("srv-a"); a2.heartbeat_once()
    assert a2.name == "w-srv-a-1" and a2.reconcile_once() == [] and ctl.redistribute() == []
    assert ctl.resource_state("srv-a") == "live" and ctl.where(1) == "w-srv-b-1"             # adding a place to record moves nothing
    assert act_a.epochs == {1: 1, 2: 1, 3: 1}                                                  # the fenced instance's footage is intact under e1
    # under `shared` the same two silences move the cameras too
    c.console().set_policy({"servers": "shared"})
    c.console().create_camera({"source": "driverpack://file/9.mp4"}); assert ctl.ensure_placed()[-1].worker == "w-srv-a-1"   # back on srv-a, the most room
    c.wall.advance(2 * LOST_AFTER + 3); b.lease_pass(); b.heartbeat_once(); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()   # srv-a dies again
    assert ctl.slots()["w-srv-a-1"].lapsed(c.wall()) and ctl.gone_servers() == {"w-srv-a-1": "srv-a"}
    assert [(m[1], m[2]) for m in ctl.redistribute()] == [("w-srv-a-1", "w-srv-b-1")] and ctl.where(4) == "w-srv-b-1"


def test_every_unit_registers_with_its_servers_resource_and_a_process_that_ended_moves_when_its_slot_runs_out():
    """The twelfth review's «Вопросы», defect 1: the cluster's entry points never called `Worker.present` (the box's do,
    `vms/__main__._present`). Every resource heartbeat said `workers` and `running` empty, so a worker whose process
    died on a live server was `wait` — "cannot be told" — for ever, and nobody wrote its cameras if systemd did not
    bring it back. Now `vms.__main__.make_worker`/`make_recorder` build AND register — what the units run, and what
    the stand builds its processes with. srv-a's resource lists its worker and its recorder, placed and running. The
    worker hangs (its process lives): past its slot nothing moves — `hung`. Its process ends: placed, not running — and
    its cameras go to w-srv-b-1 at that pass, srv-a's resource answering all along, its reason saying why."""
    from w2cplatform.resource import resources_seen
    c, ctl, a, act_a, b = _recording()
    r = c.recorder("srv-a")
    try:
        c.servers["srv-a"].res.heartbeat()
        said = resources_seen(c.objects)["srv-a"]
        assert said["workers"] == said["running"] == {"vms": ["w-srv-a-1"], "rec": ["r-srv-a-1"]}, said

        def beat(seconds):                                  # srv-a's resource answers; w-srv-a-1 says nothing
            for _ in range(int(seconds // 10)):
                c.wall.advance(10)
                for srv in c.servers.values():
                    srv.res.heartbeat()
                b.lease_pass(); b.heartbeat_once()
        beat(SLOT_TTL + LOST_AFTER + 10)                    # past the name AND the margin
        assert ctl.slot_fate("w-srv-a-1", ctl.slots()["w-srv-a-1"])[0] == "hung"
        ctl.pass_once(1)
        assert [ctl.where(i) for i in (1, 2, 3)] == ["w-srv-a-1"] * 3          # hung: its units stay, no second writer
        a.absent()                                                              # its process ends; systemd does not bring it back
        beat(10)
        said = resources_seen(c.objects)["srv-a"]
        assert said["workers"]["vms"] == ["w-srv-a-1"] and "vms" not in said["running"], said
        ctl.pass_once(1)
        assert [ctl.where(i) for i in (1, 2, 3)] == ["w-srv-b-1"] * 3
        assert ctl.placement(1).reason.startswith("w-srv-a-1's process on srv-a is not running"), ctl.placement(1).reason
        assert b.reconcile_once() == [("start", 1), ("start", 2), ("start", 3)] and b.actuator.epochs == {1: 2, 2: 2, 3: 2}
    finally:
        r.after_stop()


def test_the_worker_entry_point_registers_its_process_before_it_runs():
    """What a unit runs, run: `vms.__main__.worker()` with this server's store and objects and its unit's
    environment, stopped before its first turn — its registration is in its server's events archive (`RESOURCE_ROOT`), under
    the name it claimed, and its lock held for as long as its process lives."""
    import json
    import os
    import vms.__main__ as m
    c = Cluster(); c.resources_up()
    srv = c.servers["srv-a"]
    v = c.door("vmsworker")
    env = {**c.env("srv-a", "w-srv-a-1"), "RTSP_HOST": "0.0.0.0", "PLAYBACK_PORT": "auto"}
    saved, stores = {k: os.environ.get(k) for k in env}, m._stores
    built = []
    real = m.make_worker

    def keep(*a, **kw):
        built.append(real(*a, **kw))
        return built[-1]
    try:
        os.environ.update(env)
        m._stores = lambda role, acl: (v, c.objects_on("srv-a", v))
        m.make_worker = keep
        m.stop.set()                                                            # SIGTERM before the first turn
        m.worker()
    finally:
        m.stop.clear(); m._stores, m.make_worker = stores, real
        for k, val in saved.items():
            os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
    d = os.path.join(srv.resource, ".workers")
    said = [json.load(open(os.path.join(d, f))) for f in os.listdir(d) if f.endswith(".json")]
    assert said == [{"sub": "vms", "name": "w-srv-a-1", "pid": os.getpid()}], said
    srv.res.heartbeat()
    from w2cplatform.resource import resources_seen
    assert resources_seen(c.objects)["srv-a"]["running"] == {"vms": ["w-srv-a-1"]}
    built[0].absent()


def test_a_recorder_keeps_a_live_cameras_source_while_its_holders_door_is_away_and_lets_it_go_when_the_store_says_so():
    """The twelfth review, major 10 (`m11/p3`): the recorder found a camera's source in its holder's heartbeat, an
    object on the holder's server read through that server's door — with only the DOOR away, the heartbeat aged past
    45 s and `source(1)` said nobody, fifty seconds in, while w-srv-a-1 held the camera and its fan-out served. Now the
    store says who holds it: placed on w-srv-a-1, whose slot is held — the source read last stands. And it lets go when
    the store says otherwise: camera 2 moved to w-srv-b-1 (until w-srv-b-1 says it runs it, nobody), and camera 1 once
    its holder's slot ran out."""
    c, ctl, a, act_a, b = _recording(2)
    r = c.recorder("srv-b")
    try:
        r.lease_pass(); r.heartbeat_once()
        first = {i: r.source(i) for i in (1, 2)}
        assert [s[0] for s in first.values()] == ["srv-a", "srv-a"], first
        c.servers["srv-a"].down = True                          # its door: the worker renews and heartbeats on
        for _ in range(6):
            c.wall.advance(10); c.clock.advance(10)
            a.lease_pass(); a.heartbeat_once(); b.lease_pass(); b.heartbeat_once()
        assert {i: r.source(i) for i in (1, 2)} == first        # 60 s into the door's outage: the store's word
        assert r._by_the_book == {"1", "2"}
        ctl.move(2, "w-srv-b-1", "operator: srv-b sees that VLAN")
        assert r.source(2) is None                              # placed elsewhere: not the old holder's any more
        b.reconcile_once(); b.heartbeat_once()
        assert r.source(2)[0] == "srv-b" and r.source(1) == first[1]   # heard on its new holder; 1 still stands
        for _ in range(5):                                      # and now w-srv-a-1 is gone too: nobody renews its name
            c.wall.advance(10); c.clock.advance(10)
            b.lease_pass(); b.heartbeat_once()
        assert r.source(1) is None                              # its slot ran out: the store says nobody holds it
    finally:
        r.after_stop()


def test_a_worker_starts_while_its_servers_resource_does_not_answer():
    """The twelfth review, major 11: a worker read its name's previous heartbeat in its constructor — through this
    server's resource door, in a cluster — and while that resource restarted, `ObjectsUnavailable` ended every worker of
    the server at its start, round and round systemd's restarts, its cameras held by nobody: for a number that only
    measures the failover. Now it starts — its name claimed, its cameras run — and that restart is not measured."""
    c, ctl, a, act_a, _ = _recording(2, b=False)
    c.servers["srv-a"].down = True                                      # srv-a's resource is restarting
    c.wall.advance(5)
    again = c.worker("srv-a")                                           # systemd starts the worker's unit again
    assert again.name == "w-srv-a-1" and again.previous_hb == 0.0
    assert again.reconcile_once() == [("start", 1), ("start", 2)]


def test_the_old_instance_wakes_up_and_the_archive_is_intact():
    """srv-a was not dead — cut off from the others, or paused. The controller moved its cameras to w-srv-b-1 under
    epoch 2; srv-a comes back with w-srv-a-1 still recording epoch 1. Its next lease pass finds every epoch moved on:
    it stops each camera, and its assignment says they are not its any more. Its footage is in e1, w-srv-b-1's in e2.
    Its NAME is still its own — nobody took it — and it goes on as a worker with nothing to do."""
    c, ctl, a, act_a, b = _recording()
    c.servers["srv-a"].down = True
    _silence(c, "srv-a", 93, alive=[b])
    ctl.pass_once(1); b.reconcile_once(); b.heartbeat_once()
    c.servers["srv-a"].down = False
    lost = a.lease_pass()                                                  # kill -CONT, or the network back
    assert sorted(lost) == ["1", "2", "3"] and act_a.running == set() and a.writing_allowed
    assert a.reconcile_once() == [] and a.assignment().units == [] and a.name == "w-srv-a-1"
    assert act_a.epochs == {1: 1, 2: 1, 3: 1} and b.actuator.epochs == {1: 2, 2: 2, 3: 2}


def test_two_processes_with_one_name_the_old_one_is_nobody():
    """The unit restarted while the old process still lived — it hung past systemd's stop, or somebody started a
    second copy by hand. The new one takes the name; the old one's next renewal finds the slot held by another:
    fenced at the slot, and every epoch says the same. It stops. And it is nobody (the review's sixth pass): the name
    is the new one's, so the old says nothing under it and reads nothing of its assignment. And it takes no other name
    (the owner's decision of 4 Oct): it came back as `w-2` once — a second worker on srv-a its unit knew nothing of. It
    waits for its own, free or lapsed, and what the epochs said of it goes with it."""
    c, ctl, a, act_a, _ = _recording(b=False)
    c.wall.advance(5)
    b = c.worker("srv-a"); b.reconcile_once()
    a.lease_pass()
    assert not a.writing_allowed and act_a.running == set() and "slot w-srv-a-1" in a.fenced_reason
    assert a.renew_leases() == ["1", "2", "3"] and a.conflicts() == 3      # the resource-level token agrees, per camera
    b.heartbeat_once()
    theirs = ctl.workers_seen()["w-srv-a-1"].extra
    a.heartbeat_once()                                                     # one heartbeat under the name, and it is the new one's
    assert ctl.workers_seen()["w-srv-a-1"].extra == theirs and "fenced" not in theirs and theirs["alloc"] == b.instance
    assert a.reconcile_once() == [] and a.rows == []                       # not even the assignment is read
    assert a.rejoin() is None and "w-2" not in ctl.slots()
    assert a.nameless["holder"] == b.instance                              # nobody, waiting: no other number taken
    b.release_slot()                                                       # the new one stops: the name is free
    name = a.rejoin()                                                      # its own name, from nothing — and what the epochs
    a.heartbeat_once()                                                     # said of it goes with it: the number of this lesson
    told = ctl.workers_seen()[name].extra
    assert name == "w-srv-a-1" and told["conflicts"] == 3 and "slot w-srv-a-1" in told["was_fenced"] and "fenced" not in told


def test_the_reassignment_window_is_the_same_window_with_a_different_verdict():
    """The controller moves camera 2 from w-srv-a-1 to w-srv-b-1. For up to TTL − margin both may write — into
    different epochs. w-srv-a-1 loses the lease on 2, sees it is no longer assigned, lets it go; it is NOT a zombie
    and keeps 1 and 3."""
    c, ctl, a, act_a, b = _recording()
    ctl.move(2, "w-srv-b-1", "operator: srv-b sees that VLAN")
    assert b.reconcile_once() == [("start", 2)] and b.actuator.epochs[2] == 2   # the destination takes the next epoch
    assert a.lease_pass() == ["2"] and a.writing_allowed and act_a.running == {1, 3}
    assert a.reconcile_once() == [] and ctl.where(2) == "w-srv-b-1"


def test_the_lease_stops_writing_before_anybody_else_may_start():
    """TTL 30, margin 5: the holder stops at 25 on its own clock; the controller moves its cameras only past the
    slot's 45 s and 45 s more. The window between is the margin the design buys."""
    c, ctl, a, act, _ = _recording(1, b=False)
    c.clock.advance(24); assert a.may_act("1")
    c.clock.advance(2);  assert not a.may_act("1")                       # 26 s without a renewal: it stops itself
    assert a.lease_pass() == []                                            # renewal succeeds (nobody took the epoch)...
    assert a.may_act("1")                                                # ...and it may write again — it was never fenced


def test_the_power_pull_moves_the_recording_and_leaves_the_footage_where_it_was_written():
    """Two subsystems fail over from one dead server, each by its own controller and the same two silences. The
    camera moves from w-srv-a-1 to w-srv-b-1, under the next epoch; the recording moves from r-srv-a-1 to r-srv-b-1,
    which subscribes to the camera's new fan-out — on its own server now, so through shared memory. The footage written
    on srv-a stays in srv-a's volume under e1 — unavailable until it returns, never rebuilt, never lost; the timeline
    names it."""
    import time
    from vms.footage import footage_routes
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC, live_shm, live_url
    from tests.cluster.conftest import VMS_TESTS
    c, ctl, a, act_a, b = _recording(1)
    rec = SpecController(REC_SPEC, c.door("reccontroller"), c.objects_on("srv-b", c.door("reccontroller")), wall=c.wall)
    c.wall.watchers.append(rec)                                             # it looks as time moves, as a controller does
    assert rec.policy() == {"servers": "distinct"} and ctl.policy() == {"servers": "shared"}   # each subsystem's own default
    r1, r2 = c.recorder("srv-a"), c.recorder("srv-b")
    for r in (r1, r2):
        r.lease_pass(); r.serve_archive(); r.heartbeat_once()                # each its server's own volume, open and served
    SpecController(REC_SPEC, c.vars, c.objects, wall=c.wall).create({"name": "1", "cam": "1"})           # the operator: record camera 1
    pl = rec.ensure_placed()[0]
    assert pl.worker == "r-srv-a-1" and r1.reconcile_once() == [("start", "1")]   # beside the worker that holds the camera (`near: vms`)
    assert r1.actuator.started["1"]["source"] == live_shm(1) and r1.actuator.started["1"]["via"] == "shm" and r1.actuator.started["1"]["epoch"] == 1
    t = c.wall()
    assert r1.actuator.feed("1", t - 600, t, step=10) == {"OK": 60}                           # ten minutes into srv-a's volume, as 1/e1
    r1.heartbeat_once(); rec.workers_seen()
    routes = footage_routes(ctl.objects, ctl.vars, ctl.wall, eyes=ctl.eyes)   # a recorder's door to the page
    routes(None, "GET", "/timeline/1", {"from": t - 2000, "to": t + 1})       # the door looks, as the page asks it (r29)
    # srv-a dies: w-srv-a-1, r-srv-a-1 and srv-a's resource silent
    r1.session.vanish()                                                                         # no BYE: the writer is left detached
    _silence(c, "srv-a", 93, alive=[b, r2])
    assert rec.gone_servers() == {"r-srv-a-1": "srv-a"} and ctl.gone_servers() == {"w-srv-a-1": "srv-a"}
    ctl.pass_once(1)
    assert b.reconcile_once() == [("start", 1)] and b.actuator.epochs == {1: 2}                 # the worker: the next epoch, on srv-b
    b.heartbeat_once()
    assert [(m[1], m[2]) for m in rec.redistribute()] == [("r-srv-a-1", "r-srv-b-1")]
    assert rec.placement("1").reason.startswith("server srv-a gone: slot r-srv-a-1 lapsed and its resource silent; ")
    # r-srv-b-1 first looks at camera 1's holders now: w-srv-a-1's last heartbeat is new to it, as w-srv-b-1's is — the
    # holder under the higher epoch is the one it reads (`newest`; the thirteenth review)
    assert r2.reconcile_once() == [("start", "1")] and r2.actuator.started["1"]["source"] == live_shm(1) and r2.actuator.started["1"]["epoch"] == 2
    r2.heartbeat_once()
    assert rec.workers_seen()["r-srv-b-1"].status[0]["via"] == "shm" and rec.where("1") == "r-srv-b-1"
    assert live_url("srv-b", 1) == "rtsp://srv-b:8554/1"                                        # what r-srv-b-1 would read had the camera landed on srv-c
    # the timeline: e1 in srv-a's volume unavailable by name — and srv-a's footage comes back with its disks; silent by
    # what the console saw: r-srv-a-1's heartbeat has stood still since its look (the product's r29-writers2)
    _, tl, headers = routes(None, "GET", "/timeline/1", {"from": t - 2000, "to": t + 1})
    assert [s for s in tl if s["epoch"] == 1] == []
    assert dict(headers) == {"X-Unavailable": "srv-a@srv-a"}                                      # unavailable, not lost
    time.sleep(VMS_TESTS.OBSD_LINGER_MS / 1000 + 0.3)                                            # the daemon notices r-srv-a-1's session is gone
    a2 = c.recorder("srv-a"); a2.lease_pass(); a2.serve_archive(); a2.heartbeat_once()          # srv-a is back: its recorder's unit again, on its own disks
    assert a2.name == "r-srv-a-1" and a2.store.reattached                                       # the writer the dead one left, picked up whole
    a2.store.seal()
    _, tl, headers = routes(None, "GET", "/timeline/1", {"from": t - 2000, "to": t + 1})
    assert [(s["epoch"], s.get("fenced")) for s in tl] == [(1, True)] and headers == []          # e1, kept and told apart: e2 is the writer now
    assert a2.reconcile_once() == [] and rec.redistribute() == [] and rec.where("1") == "r-srv-b-1"  # a place to record returned; nothing moves back
    for r in (r2, a2):
        r.after_stop()

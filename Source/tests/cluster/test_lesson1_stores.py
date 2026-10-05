"""Lesson 1 — the platform's stores become the cluster's. М10's contract against the cluster's store — the
configstore's own state machine behind a door per role (`tests/cluster/conftest.py`): the same versions and CAS, rights by
the socket a process came through, the same base classes — nothing in vms/ notices. Objects are files on each
server, read across through the resources."""
import json
import os
import threading

from cluster.variables import Conflict, FakeVariables, Forbidden
from w2cplatform.contract import Controller, Subsystem, Worker
from w2cplatform.epoch import next_epoch
from tests.cluster.conftest import Cluster


def test_cas_is_the_same_promise_as_the_files_made():
    c = Cluster()
    v = c.door("console")
    idx = v.put("vms/cameras/1", {"name": "gate"}, cas=0)
    v.put("vms/cameras/1", {"name": "gate 2"}, cas=idx)
    try:
        v.put("vms/cameras/1", {"name": "stale"}, cas=idx); assert False
    except Conflict:
        pass
    items, _ = v.get("vms/cameras/1")
    assert items == {"name": "gate 2"} and v.list("vms/cameras/") == ["vms/cameras/1"]


def test_one_writer_per_prefix_is_the_rights_of_a_socket():
    """The worker's socket writes its epochs and its slot; the controller's, placement. The refusal is the daemon's,
    by the rights file — the worker's code holds no list of its own (`as_writer` stays as a second, client-side
    check, and is not asked here)."""
    c = Cluster()
    ctl, wrk = c.door("vmscontroller"), c.door("vmsworker")
    ctl.put("vms/placement/7", {"worker": "w-srv-a-1"})
    wrk.put("vms/epoch/7", {"epoch": 1})
    for v, key in ((wrk, "vms/cameras/7"), (wrk, "vms/placement/7"), (ctl, "vms/cameras/7"), (ctl, "vms/epoch/7")):
        try:
            v.put(key, {"name": "y"}); assert False, key
        except Forbidden:
            pass


def test_the_epoch_issuer_under_four_threads_on_the_clusters_store():
    c = Cluster(); v = c.door("vmsworker"); got = []

    def take():
        for _ in range(50):
            got.append(next_epoch(v, "vms/epoch/7")[0])
    ts = [threading.Thread(target=take) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(got) == list(range(1, 201))


def test_m10s_base_classes_run_on_the_cluster_stores_unchanged():
    c = Cluster(); sub = Subsystem("thing")
    ctl = Controller(sub, c.vars, c.objects, wall=c.wall)
    w = Worker(sub, None, c.vars, c.objects, clock=c.clock, wall=c.wall, instance="A")
    assert w.claim_slot() == "w-1"
    w.heartbeat([{"id": 1, "phase": "running"}], server="srv-a")
    assert list(ctl.workers_seen()) == ["w-1"] and ctl.workers_seen()["w-1"].extra["server"] == "srv-a"
    ctl.assign("w-1", ["1"]); assert w.assignment().units == ["1"]
    assert w.take_epoch("1") == 1 and w.may_act("1")


def test_objects_are_files_on_each_server_read_across():
    """Heartbeats, shards and pass reports have ONE writer each, written again within a pass: no consensus holds
    them. The worker on srv-a puts its heartbeat — a file on srv-a, no row in the store — and the controller on
    srv-c reads it through srv-c's resource, which asks srv-a's. No ceiling: the 64 KiB of a Nomad Variable went with
    the Variables. The contract is the point — nothing in vms/ knows which store it is talking to."""
    c = Cluster(); sub = Subsystem("vms")
    v = c.door("vmsworker")
    w = Worker(sub, "w-srv-a-1", v, c.objects_on("srv-a", v), clock=c.clock, wall=c.wall)
    w.heartbeat([{"id": 7, "phase": "running", "pad": "x" * 100_000}], server="srv-a")
    assert os.path.exists(os.path.join(c.servers["srv-a"].objects, "vms", "heartbeats", "w-srv-a-1"))
    assert c.vars.list("objects/") == []                                  # not a row: a file
    reader = c.objects_on("srv-c", c.door("vmscontroller"))
    ctl = Controller(sub, c.door("vmscontroller"), reader, wall=c.wall)
    assert ctl.workers_seen()["w-srv-a-1"].extra["server"] == "srv-a"
    assert reader.list("vms/") == ["vms/heartbeats/w-srv-a-1"] and reader.max_bytes == 0
    assert not os.path.exists(os.path.join(c.servers["srv-c"].objects, "vms"))   # read across, not copied here


def test_a_command_mark_is_create_only_across_the_cluster():
    """The platform review's third pass. A worker marks a device command BEFORE it calls the device, and two holders
    of one device in the same two seconds must not both believe they were first — and they may be on two servers,
    where two directories each say "first" (`link` is create-only on ONE disk). So the mark is a row: `put_new` is a
    row written with `cas=""`, the store's create-only, through the worker's own socket."""
    c = Cluster()
    v = c.door("vmsworker")
    a, b = c.objects_on("srv-a", v), c.objects_on("srv-b", v)
    assert a.put_new("vms/commands/r1", json.dumps({"instance": "a"}).encode())
    assert not b.put_new("vms/commands/r1", json.dumps({"instance": "b"}).encode())
    assert json.loads(b.get("vms/commands/r1"))["instance"] == "a"             # …and not written over
    assert c.vars.list("objects/") == ["objects/vms/commands/r1"]
    try:
        c.objects_on("srv-a", c.door("console")).put_new("vms/commands/r2", b"{}"); assert False
    except Forbidden:
        pass                                                                    # the console's socket has no such grant


def test_every_writer_sees_one_log():
    """A version comes from ONE log, whichever socket wrote. Two writers' views of the store must never hand out the
    same version — or a stale CAS can match a write it never saw, and an edit is lost with no 409 to say so. The
    fake broke this once: each writer's view counted on its own; the fake keeps the rule too."""
    for console, worker in ((lambda c: (c.door("console"), c.door("vmsworker")))(Cluster()),
                            (lambda v: (v.as_writer("console", ["vms/cameras/*"]), v.as_writer("vmsworker", ["vms/epoch/*"])))(FakeVariables())):
        a = console.put("vms/cameras/1", {"name": "gate"}, cas=0)
        b = worker.put("vms/epoch/1", {"epoch": "1"}, cas=0)
        c = console.put("vms/cameras/1", {"name": "gate-2"}, cas=a)
        assert a < b < c and len({a, b, c}) == 3

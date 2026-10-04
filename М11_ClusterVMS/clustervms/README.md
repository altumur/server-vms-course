# ClusterVMS — the М11 project, whole

М10's shape across several servers, built **on** М10's `vmsserver/` rather than beside it: the same `w2cplatform` contract, the same `vms/` controller, worker, recorder and console, imported unchanged — and no orchestrator (the owner's decision of 3 October). Every server runs the same units: the platform's `configstore` daemon (a member of one raft group over the servers) and resource, the VMS's console, controllers and workers. What this package adds is exactly what a cluster adds — the store by the socket of a process's role, objects read across the servers, names from the units, spares that a script starts when the controller says one is missing, placement under constraints, a resource that has to say it exists, and a timeline that spans servers.

```
clustervms/
  cluster/
    __main__.py      python3 -m cluster worker | recorder | controller | reccontroller | console | resource | rights — a unit's process; its store by its role's socket
    rights.py        L5  the configstore's rights file, generated from the spec (acl_*, the create-only object rows, the reads with the code that makes them)
    variables.py     L1  the store's contract by this package's name (Variables, Conflict, Forbidden) and FakeVariables — for the older tests and М12
    objectstore.py   L6  cluster:// — this server's objects as files, every server's through the resources (/v1/objects), the create-only keys as rows; S3 (s3.py) when rented
    worker.py        L2  the worker as a unit — М10's VmsWorker: its name from the unit (WORKER_NAME=w-%l-1), a spare by SPARE_FOR, the server and its labels from the environment
    recworker.py     L3  the recorder as a unit — М10's RecWorker: r-%l-1, the volume it holds, through the host's obsd
    controller.py    L10 the controller on every server — М10's VmsController: constraints, the server in the reason, the offers for the workers it is short of, the snapshot
    directory.py     L10 where is camera 7 — one scan of vms/workers/*
    resource.py      L6  М10's resource process (vms.resource) as the platform's unit: cluster_resource = vms_resource — an EventIndex attached; no footage on its tree
    eventdatabase.py L7  a name for w2cplatform.eventdatabase — EventIndex, MergedIndex
    console.py       L5  the cluster console: SpecConsole over the VMS spec with М10's media routes — a camera's timeline from every recorder's door, a volume nobody serves named *unavailable*
  deploy/
    systemd/         configstore.service, w2c-resource.service, vms-console, vms-vmscontroller, vms-reccontroller, vms-vmsworker, vms-recworker (.service);
                     w2c.env.example (/etc/w2c/w2c.env), vms.env.example (/etc/vms/vms.env), w2c-cluster.sysusers, w2c-cluster.tmpfiles
    launchd/         com.w2c.configstore, com.w2c.resource, com.w2c.vms.<role>, com.w2c.spares (.plist) — the units' twins on a macOS server
    configstore-rights.json    L5  generated (`python3 -m cluster rights`), committed, installed as /etc/w2c/configstore-rights.json; checked both ways by tests/test_policies.py
    install.sh                 L3  a machine becomes a server: /opt/w2c, the users, /etc/w2c -> /data/platform/etc and /etc/vms -> /data/vms/etc, the rights, the units (--spares: the spares' timers)
    w2c-run.sh                 L3  what every unit runs: the two env files under what the unit says, then python3 -m cluster <verb> or the configstore daemon
    verify-bench.sh            the checks that need a real cluster, PASS/FAIL — the store's group, the sockets and their groups, the rights by `curl --unix-socket`, mTLS, the objects, the mirror
    failover-drill.sh          L8  the power pull, measured: three runs, worst case kept, the old instance's conflicts counted
    nomad/                     the appendix «форма поставки» for a site that runs Nomad anyway (М12 Lesson 8): configstore as a system job, vmsworker, recworker, console
  tests/                       no Nomad, no GStreamer; the stand (conftest.py): three servers, one configstore state machine behind a door per role, a resource and objects on each;
                               the archive's tests start a real obsd: OBSD_BIN=… python3 tests/run.py; the traces: python3 tests/stand.py --write
```

## What a cluster adds, and what it does not

| | М10, one box | М11, a cluster | Where |
|---|---|---|---|
| The config store | files with a version and CAS | `configstore://` — the same promises, kept by raft over the servers; a process talks to its own server's daemon through its role's socket, and the daemon judges by the socket (`deploy/configstore-rights.json`) | `w2cplatform/configstore*.py`, `storemachine.py`, `rights.py` |
| The object store | a directory | the same, on every server: each server's objects are files there, read across through the resources; a key that must be created once across the cluster is a row | `objectstore.py` |
| A worker's name | `systemd`'s `%i` | the unit's: `WORKER_NAME=w-%l-1`, one per server, claimed by CAS — two processes with one name resolve at the CAS | `worker.py`, `deploy/systemd/` |
| Who decides how many workers | the operator starts units | the controller counts what is short and writes OFFERS; `w2c-spares.sh` on each server starts a spare for an offer of a label set it covers; **the controller starts no process** | `w2cplatform/spec.py`, `vmsserver/deploy/w2c-spares.sh` |
| Placement | most free capacity; `labels` empty | most free capacity **among workers whose server can reach the camera** — the same `constraint: labels-subset` in `vms.subsystem.yaml`, now with labels to match | `vmsserver/vms/vms.subsystem.yaml` |
| The resource | a directory on the box | the platform's resource on *each* server: every subsystem's buckets served and mirrored, retention by each subsystem's row, the door to the server's objects; no footage | `w2cplatform/resource.py`, `resource.py` |
| Footage | a volume through the box's `obsd` | a volume through *each host's* `obsd`, held by one recorder, read at its door; a dead server's volume named *unavailable* | `vms/recworker.py`, `vms/console.py` |
| What leaves the cluster | the same snapshot, of a cluster of one | one snapshot object for М12's read model — a copy with an age | `w2cplatform/spec.py` |
| Events | buckets per unit on the resource, written by the worker holding the epoch, any subsystem | the same, on each server's resource; answered by each resource's own `EventIndex` over its tree, and merged by the console's `/events`; mirrored to the next resource with `platform/mirror` on | `w2cplatform/eventdatabase.py`, `w2cplatform/resource.py` |
| The contract, **the controller**, **the worker**, the epoch, the lease, the volume | | **unchanged**: imported from `vmsserver/` — `controller.py` and `worker.py` here are one import each | |

## The three lines the tests hold

**Failover rewrites nothing, and starts nothing elsewhere.** `test_the_power_pull`: srv-a dies, its doors with it; for 90 s nothing moves (the name held 45 s, and 45 s more for what it started); then the controller on srv-b sees two silences — the slot out, srv-a's resource silent, both from what it heard while srv-a lived — and moves the cameras by assignment to w-srv-b-1, which takes the next epoch for each and records; the edit made *during* the failover is in the rows it read (`test_an_edit_during_the_failover_is_simply_there`, and the scene `06-an-edit-during-the-failover`).

**The controller never decides how many workers, or where they run.** `test_a_spare_takes_an_offer_then_stops`: the workers are full, the controller writes an offer, a spare takes it by CAS and the waiting camera lands on it; stopped, its camera moves in one pass. `test_two_processes_with_one_name_resolve_at_the_cas`: a unit's name taken twice is harmless — the second claim wins, the first is fenced.

**Old footage is unavailable, never lost.** `test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves`: a camera's footage is in two servers' volumes; when one server is silent its volume is listed as unavailable *by name*, and when it returns its volume came back with its disks — nothing was rebuilt, nothing copied.

## Verified where

The tests run on the author's machine: the store is the configstore's own state machine with the committed rights file, the processes open it with the real handle, and the traces in `../traces/` are what that handle sent (`tests/test_trace.py` compares them with a real unix socket); the archive runs against a real obsd. The real raft daemon is `vmsserver/tests/test_configstore.py`'s. `deploy/verify-bench.sh` and `deploy/failover-drill.sh` are what proves the rest on three real servers: the store's group, the sockets and their rights, mTLS on the daemons' door, and the power pull with the worst case kept.

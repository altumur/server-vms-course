# ClusterVMS — the М11 project, whole

М10's shape across several servers, built **on** М10's `vmsserver/` rather than beside it: the same `w2cplatform` contract, the same `vms/` controller, worker, recorder and console, imported unchanged. What this package adds is exactly what a cluster adds — Nomad's stores, what an allocation knows about itself, placement under constraints, a resource that has to say it exists, and a timeline that spans servers.

```
clustervms/
  cluster/
    variables.py     L1  Nomad Variables over HTTP with the task's own token (ModifyIndex, cas, 409, 403) — and the fake with the promised semantics
    objectstore.py   L1  the object-store contract: Variables under objects/… on this cluster (heartbeats, the snapshot); S3 (s3.py, SigV4) when rented or outgrown; a directory in tests
    worker.py        L2  the worker as an allocation — М10's VmsWorker by the name the lessons use: the slot from NOMAD_ALLOC_INDEX, the server and its labels from the environment
    controller.py    L5  the controller as a job — М10's VmsController by the name the lessons use: constraints, the server in the reason, the snapshot and the measured failover are the one-box behaviour with N = 1
    directory.py     L5  where is camera 7 — one scan of vms/workers/*
    resource.py      L3  М10's resource process (vms.resource) as the job: cluster_resource = vms_resource — an EventIndex attached; no footage on its tree
    eventdatabase.py L3  a name for w2cplatform.eventdatabase — EventIndex, the one each resource job reads its own tree by; MergedIndex, the console's merge
    console.py       L5  the cluster console — its own job, its own token: the platform's SpecConsole over the VMS spec with М10's media routes: a camera's timeline from every recorder's door, a volume nobody serves named *unavailable*, never *lost*
    console.py       L5  the cluster console: SpecConsole (/spec /cameras /where /resources /unplaceable /events /metrics /marks, the writes) plus /timeline and /export
    __main__.py      python3 -m cluster worker | controller | resource   (the resource job keeps the event index over its own tree; the console holds none)
  deploy/
    server.hcl, client.hcl     L1  three servers, ACLs on, meta.labels and meta.archive, the Podman plugin
    vmsworker.nomad.hcl        L2  service, count = N, the `scaling` block on avg(vms_worker_load), the disconnect numbers, kill_timeout for the slot release
    vmscontroller.nomad.hcl    L2  service, count = 1, no port — safe at two; economy, not correctness
    console.nomad.hcl          L2  system — one console on every server with a resource, nothing in front; the page, the API — no index of its own
    resource.nomad.hcl         L2  system, on meta.archive — the PLATFORM's resource job, with the VMS registered on it
    autoscaler.nomad.hcl       L2  the Nomad Autoscaler (MPL-2.0): the fifth job, and the only thing that changes count
    vmsworker-policy.hcl, vmscontroller-policy.hcl, console-policy.hcl, resource-policy.hcl   L2  one writer per prefix: placement (workers/, placement/, slots/, the snapshot) for the controller; the operator's rows (cameras/, next_id, retention/) for the console; vms/epoch/*, vms/slots/* and its heartbeat for a worker; platform/resources/* for a resource
    verify-bench.sh            the six checks that need a real cluster, PASS/FAIL — including the ACL from inside an allocation and a scale drill
    failover-drill.sh          L4  the power pull, measured: three runs, worst case kept, the old instance's conflicts counted
    Containerfile              the image: FROM М10's localhost/vmsserver (the Quadlet units' image) plus cluster/, four entrypoints
  tests/                       43 tests, no Nomad, no GStreamer; the archive's tests start a real obsd: OBSD_BIN=… python3 tests/run.py
```

## What a cluster adds, and what it does not

| | М10, one box | М11, a cluster | Where |
|---|---|---|---|
| The config store | files with `ModifyIndex` and CAS | Nomad Variables — the same two promises, kept by raft | `variables.py` |
| The object store | a directory | Variables under `objects/…` — a dozen 10 KB heartbeats every ten seconds is not a raft load; MinIO/S3 only when a cluster outgrows this or is rented | `objectstore.py`, `s3.py` |
| A worker's name | `systemd`'s `%i` | `w-<NOMAD_ALLOC_INDEX>`, claimed by CAS — the index is the preference, the Variable the proof | `worker.py` |
| Who decides how many workers | the operator starts units | Nomad runs `count`; the Autoscaler moves it from `vms_worker_load`; **never the controller** | `deploy/vmsworker.nomad.hcl` |
| Placement | most free capacity; `labels` empty | most free capacity **among workers whose server can reach the camera** — the same `constraint: labels-subset` in `vms.subsystem.yaml`, now with labels to match | `vmsserver/vms/vms.subsystem.yaml` |
| The resource | a directory on the box | the platform's `resource` job on *each* server: every subsystem's buckets served and mirrored, retention by each subsystem's row; no footage | `w2cplatform/resource.py`, `resource.py` |
| Footage | a volume through the box's `obsd` | a volume through *each host's* `obsd`, held by one recorder, read at its door; a dead server's volume named *unavailable* | `vms/recworker.py`, `vms/console.py` |
| What leaves the cluster | the same snapshot, of a cluster of one | one snapshot object for М12's read model — a copy with an age | `w2cplatform/spec.py` |
| Events | buckets per unit on the resource, written by the worker holding the epoch, any subsystem | the same, on each server's resource; answered by each resource's own `EventIndex` over its tree, and merged by the console's `/events`; mirrored to the next resource with `platform/mirror` on | `w2cplatform/eventdatabase.py`, `w2cplatform/resource.py` |
| The contract, **the controller**, **the worker**, the epoch, the lease, the volume | | **unchanged**: imported from `vmsserver/` — `controller.py` and `worker.py` here are one import each | |

## The three lines the tests hold

**Failover rewrites nothing.** `test_the_power_pull`: Server A dies; 48 s later a fresh allocation with the same index claims `w-1`, reads the assignment the controller wrote before the failure, takes the next epoch for each camera and records on Server B — and the edit made *during* the failover is in the rows it read, because the controller's acknowledgement was the CAS commit into raft (`test_an_edit_during_the_failover_is_simply_there`).

**The controller never decides how many workers, or where.** `test_nomad_job_scale_out_then_in`: a new allocation claims a new slot and the waiting camera lands on it; a stopped one releases its slot and its cameras are redistributed; `test_two_allocations_with_one_index_resolve_at_the_cas`: Nomad's documented duplicate-index bug is harmless because the index is not the identity.

**Old footage is unavailable, never lost.** `test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves`: a camera's footage is in two servers' volumes; when one server is silent its volume is listed as unavailable *by name*, and when it returns its volume came back with its disks — nothing was rebuilt, nothing copied.

## Verified where

The 43 tests run on the author's machine on fakes that implement what Nomad's and S3's documentation promise, and against a real obsd for the archive. `deploy/verify-bench.sh` and `deploy/failover-drill.sh` are what proves the promises against real Nomad: the ACL from inside an allocation, the four jobspecs validating, the scale drill, and the power pull with the worst case kept. There is no Go port of this package: a worker on a cluster is a worker on a box whose stores happen to be raft, and what is М11's about the rest is the jobspecs. М10's `../../vmsserver-go/` is whole and current if one is wanted again.

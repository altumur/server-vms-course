# w2cplatform.cluster — the platform across several servers (М11_Cluster)

М10A's platform across several servers, built **on** the same code rather than beside it: the same contract, the same
spec controller, worker runtime, resource and console — and no orchestrator (the owner's decision of 3 October). Every
server runs the same units: the platform's `configstore` daemon (a member of one raft group over the servers), its
resource, its console and a controller per subsystem; a subsystem's own workers beside them. What this package adds is
exactly what a cluster adds — the store by the socket of a process's role, objects read across the servers, the rights
file generated from the specs, names from the units, spares that a script starts when a controller says one is missing.
It knows the subsystems by their specs and by nothing else, as the rest of the platform does.

```
Source/w2cplatform/cluster/
  __main__.py      python3 -m w2cplatform.cluster controller <sub> | console | resource | rights — a unit's process; the
                   box's verbs (`host.py`) over a cluster's two stores: its role's socket, `cluster://` objects
  rights.py        L5  the configstore's rights file, generated from the catalogue of specs (the roles of every process)
  variables.py     L1  the store's contract by this package's name (Variables, Conflict, Forbidden) and FakeVariables
  objectstore.py   L6  cluster:// — this server's objects as files, every server's through the resources (/v1/objects),
                   the create-only keys as rows; S3 (s3.py) when rented
  directory.py     L10 where is unit N of a subsystem — one scan of `<sub>/workers/*`
Source/deploy/cluster/
  systemd/, launchd/, nomad/   the units of a server and their twins; the subsystem's units run `w2c-run.sh <package> <verb>`
  configstore-rights.json      generated (`SPEC_DIR=… python3 -m w2cplatform.cluster rights`), checked by tests/cluster/test_policies.py
  install.sh, w2c-run.sh, verify-bench.sh, failover-drill.sh
Source/tests/cluster/          the stand (conftest.py): three servers, one configstore state machine behind a door per role,
                               a resource and objects on each; the traces: python3 tests/cluster/stand.py --write
```

## What a cluster adds, and what it does not

| | М10, one box | М11, a cluster | Where |
|---|---|---|---|
| The config store | files with a version and CAS | `configstore://` — the same promises, kept by raft over the servers; a process talks to its own server's daemon through its role's socket, and the daemon judges by the socket | `w2cplatform/configstore*.py`, `storemachine.py`, `rights.py` |
| The object store | a directory | the same, on every server: each server's objects are files there, read across through the resources; a key that must be created once across the cluster is a row (`objects.rows` in a spec) | `objectstore.py` |
| A worker's name | `systemd`'s `%i` | the unit's: `WORKER_NAME=w-%l-1`, one per server, claimed by CAS — two processes with one name resolve at the CAS | `w2cplatform/contract.py`, `deploy/cluster/systemd/` |
| Who decides how many workers | the operator starts units | the controller counts what is short and writes OFFERS; `w2c-spares.sh` on each server starts a spare for an offer of a label set it covers; **the controller starts no process** | `w2cplatform/spec.py`, `Source/deploy/w2c-spares.sh` |
| Placement | most free capacity; `labels` empty | most free capacity **among workers whose server can reach the unit** — `constraint: labels-subset` in a spec, now with labels to match | the specs |
| The resource | a directory on the box | the platform's resource on *each* server: every subsystem's buckets served and mirrored, retention by each subsystem's row, the door to the server's objects | `w2cplatform/resource.py` |
| The rights | a writer's grant in the file store | one file the daemon reads, generated from the catalogue: a controller and a worker role for every spec, the console, the resource, the domain's | `rights.py` |
| What leaves the cluster | the same snapshot, of a cluster of one | one snapshot object per worker for the layer above — a copy with an age | `w2cplatform/spec.py` |
| Events | buckets per unit on the resource, written by the worker holding the epoch | the same, on each server's resource; answered by each resource's own `EventIndex` and merged by the console's `/events` | `w2cplatform/eventdatabase.py` |
| The contract, the controller, the worker, the epoch, the lease | | **unchanged**: the platform's own | |

## The lines the tests hold

**Failover rewrites nothing, and starts nothing elsewhere.** A server dies, its doors with it; for 90 s nothing moves
(the name held 45 s, and 45 s more for what it started); then a controller on another server sees two silences — the slot
out, the server's resource silent, both from what it heard while the server lived — and moves the units by assignment,
whose new holder takes the next epoch for each.

**The controller never decides how many workers, or where they run.** The workers are full, the controller writes an
offer, a spare takes it by CAS and the waiting unit lands on it; stopped, its unit moves in one pass. A unit's name taken
twice is harmless — the second claim wins, the first is fenced.

## Verified where

The tests run on the author's machine: the store is the configstore's own state machine with the committed rights file,
the processes open it with the real handle, and the traces in `../../traces/` are what that handle sent. The real raft
daemon is `Source/tests/test_configstore.py`'s. `deploy/cluster/verify-bench.sh` and `deploy/cluster/failover-drill.sh`
prove the rest on three real servers.

> **The first cluster design's demos that still run (М11_Cluster).** The module is the platform across several servers: every server runs the same systemd units, the store is the platform's `configstore` (raft over the servers, a socket per role, rights from a file generated from the specs), and the objects are files on each server read across through the resources — `../Source/w2cplatform/cluster/README.md` (ADR 0021). The scripts below are what the first design measured its arguments with; each still runs on its own, none is part of a suite, and none needs a cluster. A site that runs an orchestrator anyway: `../orchestrator-as-a-delivery-form.md`.

# М11 reference — what runs without a cluster

| File | Lesson | Runs |
|---|---|---|
| `variables.py` | 8, step 3 | a stand-in for a replicated store with CAS (a version per row, 409 on a stale `cas`) and for a lock service (opaque UUID, TTL) — the two answers lesson 8 compares |
| `test_issuer.py` | 8, step 3 | the wrong answer (a lock's IDs have no order) and the right one (CAS: 200 epochs from four racing threads, all distinct); `python3 test_issuer.py` |
| `lease.py` | 8, step 4 | the lease state machine on a monotonic clock; partition and pause; what the margins buy; `python3 lease.py` |
| `fencing_demo.py` | 9 | the zombie writer with two real processes, `kill -STOP` / `kill -CONT`; `--no-fencing` shows the corruption; `python3 fencing_demo.py` |
| `rehydrate.py` | 6, step 2 | the first design's six-step restore against fakes, the publication order, and the RPO measured over 1000 failovers — what the module does without; `python3 rehydrate.py` |
| `placement.py`, `test_placement.py` | 10 | placement by measured capacity under constraints; the stability property; the tidy rebalance that fails it; `python3 test_placement.py` |

The platform's own code for each of these is in `../Source/w2cplatform/` (`epoch.py` — the lease and the epoch issuer, `spec.py` — placement); these scripts are the arguments, small enough to read in a sitting.

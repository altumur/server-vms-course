# readview.py — Lesson 3: the list of units from the workers' heartbeats and the controllers' snapshots, its age on every row, one cause per dead server

**Role in the module.** The read model reads what each cluster's workers already publish (`<sub>/heartbeats/<w>`) and, for the units no worker reports, each cluster's snapshot (`<sub>/snapshot/*`), for every subsystem of the directory. It holds both in memory and serves the list, search and pagination from there — no call to any worker or controller on any request. A heartbeat is an OBSERVATION, the snapshot is the CONFIGURATION: a unit configured and observed by nobody appears marked `configured`. Staleness is shown, never hidden; a silent cluster keeps its last rows, named as such; silence is grouped by failure domain — one cause per dead server.

## Names
- `class Row(unit, name, worker, cluster, server, phase, position, revision, observed_revision, epoch, age, worker_state, ref, sub)` — `to_json()` adds `as_of`. `unit` is the cluster's own id, as its spec says ids are (`_unit_id`).
- `class Cause(scope, name, silent_for, workers, units)` — `sentence()`.
- `class Snapshot(worker, cluster, ts, server, status, doors, sub)` — a worker's last heartbeat; `doors` is what else it said, as it said it, for a subsystem's own passes.

## `class ReadView(fed, lost_after, wall, lanes, backoff, backoff_max)`
- `refresh()` — one pass: every member due, `lanes` at a time, a silent one retried after a backoff; what a member published is masked as a snapshot would carry it (no `*_secret`, no credential in an address).
- `last_known(ref)`, `where(ref)` — from this pass's memory (Lesson 11).
- `rows()`, `list(q, page, size, cluster, sub)`, `rpo()`, `causes()`.
- `publish(objects, tables=None)` — the shared view, one object `domain/view` in the holder's store: members and their state, the units with the platform's fields and the ones their spec shows (`domain.view`), the causes, and the tables the specs serve (`tables`, by `<sub>/<table>`). Served at the holder cluster's `GET /domain`.

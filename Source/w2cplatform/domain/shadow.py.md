# shadow.py — Lesson 2: the divergence report from worker reports keyed by ref, and the written exit criterion

**Role in the module.** Shadow mode: the domain computes what the directory WOULD say, observes what the clusters' workers report, and writes nothing. Six kinds per unit: lagging (behind within grace — not a fault), stalled (behind past grace, no progress), orphaned (placed, run by nobody), unmanaged (run, never placed — in shadow mode a measurement), conflict (two clusters or workers claim one unit), stale_epoch (a worker under a superseded epoch — the fence at work). The one number is `unmanaged == 0`.

## Names
- `class WorkerReport(worker, cluster, server, units: [(ref, epoch, revision, observed_revision)], ts)`.
- `class Finding(kind, unit, where, detail)`, `class DivergenceReport` — `count`, `unmanaged`, `faults`, `summary`.
- `class Shadow(grace_seconds)` — `compare(placed, epochs, reports, now)`; progress remembered per (worker, unit), so slow and stuck are told apart by distance and time.
- `reports_from(fed)` — the reports and the epoch map from every reachable cluster's heartbeats and `<sub>/epoch/*`, for every subsystem of the directory; one entry or one epoch row that does not parse is that unit's, skipped and counted.
- `exit_criterion(rep, consecutive_clean, required=3)` — the written criterion for switching the domain into write mode.

# directory.py — where is unit N: the cluster directory as one scan of `<sub>/workers/*`

**Role in the module.** Lesson 5. The assignment rows `<sub>/workers/<worker>` are written by the controller into one store and read by every worker from the same store; scanning that prefix *is* the cluster directory, and it is consistent because it is one store. A layer above that aggregates several clusters' snapshots *cannot* be consistent, which is why "where is unit 7" is answered here, inside the cluster. `SpecConsole.directory()`/`where()` does the same scan through the controller (`ctl.assignments()`); this class is the standalone form the lesson used, with an explicit TTL and a scan counter so a test can prove "nine answers, one scan". Depends only on `Variables.list/get` and the platform's `Assignment` record.

## `class Directory`
A cached view of every worker's assignment of one subsystem: `{worker: [unit ids as strings]}`.

### `__init__(self, vars_, sub, ttl=5.0, clock=time.monotonic)`
`vars_` is any `Variables` (the console's token is enough); `sub` the subsystem whose `<sub>/workers/` it scans. `ttl` is how long an answer may be served from the cache — 5 s, the controller's own pass period. `_at = -1e9` forces the first call to scan.

### `scan(self, force=False)`, `where(self, unit)`, `holdings(self, worker)`
One `list` plus one `get` per worker when the cache is older than `ttl` (a row whose `rev` does not parse is read for the units it names — `read_assignment`); `where` — exactly one worker's name, `None`, or the names joined with `+` during a reassignment window; `holdings` — the sorted ids (strings: a unit name in the platform is a string) assigned to a worker.

## Notes
- `tests/cluster/test_lesson5_controller.py`: nine `where()` calls, `scans == 1`, every answer agrees with the controller.
- The class never reads heartbeats: an assignment to a dead worker is still the answer, because that is what the controller wrote.

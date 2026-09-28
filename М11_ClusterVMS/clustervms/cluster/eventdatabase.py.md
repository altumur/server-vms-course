# eventdatabase.py — a name for `w2cplatform.eventdatabase`: the event index each resource reads its own tree by, and the console's merge

**Role in the module.** Lesson 3 (events). Three lines: the event index is the platform's and lives with the resource, so this module only re-exports `EventIndex` and `MergedIndex` from `w2cplatform.eventdatabase` (`noqa: F401`) under the platform's name (М11's lessons once called it `eventindex`). `EventDatabase(root, server, wall, path=":memory:", bucket_seconds, interval)` is a SQLite cache over ONE resource's tree — its own buckets and the `.mirror/<server>/` copies it holds — rebuilt on start (`rebuild()`), tailed every few seconds (`tail()`, open buckets by the lines past what is held) and queried by time, camera, kind, subsystem and unit (`query(...)`); the resource job serves it as `GET /events`. `MergedIndex(objects, fetch, wall)` is what the console has instead of an index: `query(...)` asks every live resource's `/events`, merges by time, fences by the cluster's epochs, drops a peer's copy when the owner answered, and names the servers nobody answered for.

## Module-level names
- `EventIndex`, `MergedIndex` — re-exports; no code of М11's own.

## Notes
- `__main__.resource` gets its `EventIndex` from `cluster_resource` (М10's `vms_resource`), which attaches it as `res.index`. It keeps nothing of its own — the tree is read where it lies at each query — so there is nothing to start, nothing to rebuild after `restore()`, and a restart loses only the cache.
- The tests (`tests/test_lesson3_events.py`, `test_the_console_over_http`) import from `w2cplatform.eventdatabase` and `cluster.console`, so nothing in the package depends on this alias.

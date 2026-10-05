# variables.py — the store's contract by this package's name, and the in-memory fake

**Role in the module.** Lesson 1. On a cluster without an orchestrator the store is `configstore://` — this server's daemon, a member of a raft group over the servers, reached through the unix socket of the process's role (`../../../Source/w2cplatform/configstorevars.py` the handle, `configstore.py` the daemon, `storemachine.py` what they agree on). Nothing here speaks to it: a process opens `PLATFORM_STORE` with `open_vars` (`__main__.stores`), and the platform knows the scheme. This module spoke Nomad's Variables API before (`NomadVariables`, the `nomad://` scheme, `NOMAD_MAX_VARIABLE_BYTES`); they went with the orchestrator. What stays is what other code imports from here — М12 does so some 27 times: `Variables` (the Protocol), `Conflict`, `Forbidden`, and `FakeVariables`.

## Module-level names
- `Conflict`, `Forbidden` — re-exported from `w2cplatform.variables`; `cluster.variables.Conflict is w2cplatform.variables.Conflict`, so a CAS retry in `w2cplatform.epoch.next_epoch` catches ours too.

## `class Variables(Protocol)`
The contract restated: `get(path) -> (items | None, version)`, `put(path, items, cas=None) -> version`, `list(prefix) -> [paths]`, `delete(path, cas=None)`.

## `class FakeVariables`
One log for the whole cluster, in memory, with a lock — what `storemachine.StoreMachine` does, without the rights file and the API. The module's own stand runs the machine itself behind per-role doors (`tests/cluster/conftest.py`); this fake is for the tests that need a store and nothing about its doors (`tests/cluster/test_cluster_objects.py`, `test_lesson1_stores.py::test_every_writer_sees_one_log`, all of М12).

### `__init__(self)`
`_log = [1000]` (a list, so the views `as_writer` makes share ONE counter: two views handing out the same version once let a stale CAS match a write it never saw), `_items: {path: (items, version)}`, `acl: {writer: [prefixes]}`, `writer = None`.

### `as_writer(self, writer, allowed=None) -> FakeVariables`
The same log seen through one identity — what a role's socket is under the rights file. A shallow copy sharing the lock, the items, the log and the ACL, with `writer` set; `allowed` registers that writer's prefixes.

### `_acl(self, path)`
With a writer and any ACL: the path must equal a granted entry or match a `prefix*`, else `Forbidden`. A handle with `writer=None` bypasses it — the tests' own hand.

### `get(path)`, `put(path, items, cas=None)`, `list(prefix)`, `delete(path, cas=None)`
`safe_path` first, as the real store (the fake may not be laxer). `get` copies; absent is `(None, 0)`. `put` checks the ACL, then under the lock a `cas` that differs from the current version (0 for absent) is `Conflict`; else the log grows by one, the items are stored as strings and the version returned. `delete` refuses an epoch row (`refuse_delete`, the platform's rule), checks the ACL and the `cas`, and burns a version, as every command does.

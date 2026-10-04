# __init__.py — the `cluster` package: М11's additions on top of М10's `vmsserver`, and the import path that makes that possible

**Role in the module.** The package docstring is the module map for М11 (ClusterVMS) — a cluster with no orchestrator (the owner's decision of 3 October): every server runs the same units, the platform's `configstore` daemon (a member of one raft group over the servers) and resource, and the VMS's console, controllers and workers. The same `w2cplatform` contract and the same `vms/` controller, worker and archive resource as М10, *imported* rather than copied, plus what a cluster adds: the entry points by role (`__main__.py`), the rights file generated from the spec (`rights.py`), the contract's name and the fake for the older tests and М12 (`variables.py`), the objects on every server (`objectstore.py`), the worker and recorder as units, the controller on every server, the resource, the directory, the console. The only code is a `sys.path` fix-up so that `import vms` and `import w2cplatform` resolve to М10's package without an install step. Every entry point (`__main__.py`, `tests/conftest.py`, `tests/run.py`) does `import cluster` first for exactly this side effect. It registers no store scheme any more: `configstore://` is the platform's own (`w2cplatform/configstorevars.py`), and Nomad's `nomad://` went with the orchestrator.

## Module-level names
- `_here` — the directory that contains `cluster/`, i.e. the `clustervms/` module directory.
- The search loop — tries the candidates in order and appends the **first** existing directory to `sys.path`:
  1. `$VMSSERVER_PATH` — set by `deploy/w2c-run.sh` to `/opt/w2c/vmsserver`, where `install.sh` copied М10's package;
  2. `<clustervms>/vmsserver` — a sibling checkout or symlink beside `cluster/`;
  3. `<notes>/vmsserver` — the course layout, two directories up from `clustervms/`, which is what the tests use in this tree. (Before 17 September 2026 the package sat at `М10_ServerVMS/vmsserver`; that candidate is still tried, last.)
  It **appends** rather than inserts: `clustervms/tests/` must shadow `vmsserver/tests/` when both are importable as `tests`.

## Notes
- It runs whenever any `cluster.*` module is imported, so a process that imports `vms` before `cluster` (nothing in this package does) would fail with `ModuleNotFoundError`. М12's `domain` package imports `cluster` for the same path, and its comments say so.

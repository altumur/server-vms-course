# __main__.py — `python3 -m w2cplatform.cluster controller <sub> | console | resource | rights`: the platform's processes on a cluster server

**Role in the module.** What the platform's units of a server run (`deploy/cluster/w2c-run.sh controller <sub> | console | resource | rights`, from `deploy/cluster/systemd/*.service` and `deploy/cluster/launchd/*.plist`). The verbs and their loops are the box's (`w2cplatform/host.py`: `host.controller`, `host.console`, `host.resource` — the boundary's step 5); what a cluster changes is only where the two stores are, and both are the environment's (`host.stores`): the store by `PLATFORM_STORE` — this server's `configstore` daemon through the role's socket, `configstore:///run/configstore/<role>.sock` by default (`<sub>controller`, `console`, `resource`) — and the objects by `OBJECTS`, `cluster:///data/platform/objects?resource=http://127.0.0.1:8090` by default, whose create-only keys are rows through THAT store handle and its rights. Every subsystem's controller is the platform's from its spec alone (`SPEC_DIR`, which `w2c-run.sh` sets to the installed tree's specs); the console is the platform's spec console (`CONSOLE_ROOT` at `/`, every other spec mounted by name). A subsystem's own processes on a cluster are its own entry point's over the same two variables (`w2c-run.sh <package> <verb>`).

Until the boundary's step 7 this was a top-level `cluster` package whose entry point built one subsystem's classes and ran its request turns inside the console's process; those are the subsystem's processes now, and nothing here imports a subsystem.

## Module-level names
- `OBJECTS` — the default object store, `cluster:///data/platform/objects?resource=http://127.0.0.1:8090`.
- `USAGE` — the verbs.
- `stop` — the platform's flag (`w2cplatform.host.stop`), set by `SIGTERM` or `SIGINT`; the handler is installed when the module is run, never at import.

## Functions

### `cluster_env(role, env=None) -> dict`
The environment a verb runs in: the unit's, and where it said nothing, the cluster's two stores — `PLATFORM_STORE` the role's socket on this server, `OBJECTS` the objects across the servers. `tests/cluster/test_lesson2_jobs.py::test_each_process_opens_its_roles_socket_and_its_objects_on_its_own_server`.

### `main(argv, env=None) -> int`
`rights` first (`rights.main`, its exit code: it needs `SPEC_DIR` and nothing else); then `SPEC_DIR` is required and loaded; `controller <sub>` runs `host.controller` without a journal (its unit gives it no write in the events tree: its decisions are in its log), `resource` runs `host.resource`, `console` runs `host.console` (a `CONSOLE_ROOT` naming no spec is said, exit 2). Anything else: the usage, exit 2.

## Notes
- Nothing is opened at import: a test imports this module. With no daemon on this server a process fails at its first store call (the handle tries a refused connection again for 5 s, then `StoreUnavailable`), not at import.

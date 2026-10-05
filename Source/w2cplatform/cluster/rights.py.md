# rights.py — the configstore's rights file, generated from the catalogue of specs (`python3 -m w2cplatform.cluster rights`)

**Role in the module.** Lesson 5. The cluster's store judges a request by the socket it came through: the daemon opens one per role (`/run/configstore/<role>.sock`), owned by the role's group, and a unit joins its role's group (`SupplementaryGroups=`) — so the socket a process could open IS its role, and the daemon asks the rights file before anything is forwarded or applied (`w2cplatform/storemachine.py`, `Rights`). This module writes that file from the specs of the catalogue (`SPEC_DIR`) — the roles of every process come from the specs (§3 row 8 of the boundary note; until the boundary's step 7 the roles and their grants were written here by hand from one subsystem's constants). The file is installed as `/etc/w2c/configstore-rights.json` and committed as `deploy/cluster/configstore-rights.json`; `tests/cluster/test_policies.py` holds it to the code both ways.

The format is the product's: `{"comment": …, "roles": {"<role>": {"group": "...", "read": [...], "write": [...], "delete": [...]}}}` — a trailing `*` a prefix, a leading `!` a denial.

## Module-level names
- `OBJECTS` — `objects/`, the prefix of the create-only object rows.
- `PLATFORM` — the platform's own roles (`resource`, `console` (ADR 0014), `domain`, `domainagent`, `member`): their group is `w2c-<role>`, and so is every subsystem's controller's (`w2c-<sub>controller`: a platform process, ADR 0023; the role keeps the spec's name `<sub>controller`); every other role's is `<deployment>-<role>` (`group`), the deployment being `ROLE_GROUP` or the name of the directory the specs ship in.
- `SIGNER_KEYS` — the domain's keys, read and written by the domain's own role alone.

## Functions

### `roles(specs, deployment) -> dict`
For every spec of the catalogue a controller role (`<sub>controller`: writes `acl_controller`; reads its subsystem, the subsystems its spec refers to — `about`, `near`, a field's `ref` — and `platform/*`) and a worker role (`<sub>worker`: writes `acl_worker_role` — its claims and what its spec's `worker:` says it writes and files — plus its create-only object rows; reads its subsystem, what its units are about, `platform/decommission/*`, the key set and `domain/member` its door's gate asks, and its spec's `worker.reads`). The console: every spec's `acl_console`; reads every subsystem, `platform/*`, the gate's rows and every worker's create-only rows. The resource: its doors and the requests to free bytes of the specs that say `requests: {free: true}`; reads the doors, mirror and watermark, every subsystem's days, a `holds:` table and the rows of units about another. The domain's three roles. A role deletes what it writes; the store refuses the two deletes nobody does whatever the file says. Last, `check_secrets`.

### `check_secrets(specs, out)`
The specs' `secrets: {readers, reads}` (the product's key) held to the grants just made: a declared secret row (a key, or a prefix ending in `/`) is read by exactly the roles named — a spec's `controller`/`worker` its subsystem's, `console`, `domain`, `domainagent`, `resource` the one role of the name, and the worker of every spec that `reads` it — or the file is not made (`ValueError`, every disagreement named). A row only `reads` names is held to that worker's grant. The course derives no denial from a declaration: the reads are the grants, and the declaration is the promise they are checked against.

### `specs_of(env) -> (specs, deployment)`, `rights(specs, deployment)`, `render(specs, deployment)`
The catalogue from `SPEC_DIR` (loaded, so the create-only keys are known), the file's JSON with its comment, and its text (`indent=1`, a trailing newline) — what is committed, byte for byte.

### `main(argv, env=None) -> int`
Prints `render()`; `--check FILE` says whether FILE is what the specs generate now (exit 0/1) — `install.sh` refuses to install a stale file. No `SPEC_DIR`: said, exit 2.

## Notes
- Tests: `tests/cluster/test_policies.py` — the committed file is `render()` over the installed tree's specs; each role's group; write grants equal the specs' lists, both ways; the denials by name; every write and read the stand makes is granted; no role reads a `secrets/` row. The stand itself (`tests/cluster/conftest.py`) opens every process's store with this file's rights, so a missing grant is a 403 in the suite.

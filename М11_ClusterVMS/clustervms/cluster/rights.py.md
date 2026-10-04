# rights.py — the configstore's rights file, generated from the spec (`python3 -m cluster rights`)

**Role in the module.** Lesson 5. The cluster's store judges a request by the socket it came through: the daemon opens one per role (`/run/configstore/<role>.sock`), owned by the role's group, and a unit joins its role's group (`SupplementaryGroups=`) — so the socket a process could open IS its role, and the daemon asks the rights file before anything is forwarded or applied (`../../../vmsserver/w2cplatform/storemachine.py`, `Rights`). This module writes that file. It replaces the Nomad Variables ACL policies (`deploy/*-policy.hcl`), which were written by hand and drifted from the code three times in two commits; the file is installed as `/etc/w2c/configstore-rights.json` (on the data partition, `/data/platform/etc`) and committed as `deploy/configstore-rights.json`, and `tests/test_policies.py` holds it to the code both ways.

The format is the product's (its configstore round 2): `{"comment": …, "roles": {"<role>": {"group": "...", "read": [...], "write": [...], "delete": [...]}}}` — a trailing `*` a prefix, a leading `!` a denial (none generated now; the daemon takes them).

## Module-level names
- `OBJECTS` — `objects/`, the prefix of the create-only object rows.
- `PLATFORM` — the roles that are the platform's own: `resource`, `domainagent`, `member`; their group is `w2c-<role>`, every other `vms-<role>` (`group(role)`).
- `TREES` — the subsystems whose buckets a resource may hold, and so whose days it reads (`resource.retention_days`): every spec of the VMS, `console`, `audit`. A rights file names keys and prefixes, not `*/retention`, so the names are said.

## Functions

### `roles() -> dict`
The roles and their grants. WRITES from the code's own lists: `console` — `SPEC.acl_console() + REC_SPEC.acl_console()`; `vmscontroller` — `SPEC.acl_controller()`; `reccontroller` — `REC_SPEC.acl_controller()`; `vmsworker` — `WORKER_ACL` and, of its objects, only the create-only rows (`objects/vms/commands/*`: every other object is a file on its writer's server now); `recworker` — `REC_SPEC.sub.acl_worker()`; `resource` — `platform/doors/*`; М12's `domainagent` — `domain/*`, `relay/*`; `member` — nothing. A role deletes what it writes; the store refuses the two deletes nobody does whatever the file says (an epoch row; `domain/*` but by `domain`/`domainagent`). READS, each with the code that makes it: `platform/schema` for every role (`Worker.__init__` → `check_schema`); the console its subsystems, `platform/*` and the gate's rows (`TRUST_KEYS`, `DOMAIN_MARKS`, `domain/grants/*`); the controllers their subsystems and `platform/*`; the holder its subsystem, `platform/decommission/*` (`Worker._claim_slot`), the key set and `domain/member` (its playback door's gate) and its marks; the recorder both subsystems, `platform/decommission/*`, `domain/primaries`; the resource the doors, the mirror and watermark knobs, every tree's days, `rec/recordings/*`, `rec/keeps/*`.

### `rights() -> dict`, `render() -> str`
The file's JSON with its comment ("generated … do not edit, regenerate"), and its text (`indent=1`, a trailing newline) — what is committed, byte for byte.

### `main(argv) -> int`
`python3 -m cluster rights` prints `render()`; `--check FILE` says whether FILE is what the spec generates now (exit 0/1) — `install.sh` refuses to install a stale file.

## Notes
- Tests: `tests/test_policies.py` — the committed file is `render()`; each role's group; write grants equal the code's lists, both ways; the denials by name; every write and read the stand makes is granted (`code_calls`: every scene and `_doors`, by the socket each call came through); the gate and the schema readable; the holder reads no more of the domain than its door asks; no role reads a `secrets/` row. The stand itself (`tests/conftest.py`) opens every process's store with this file's rights, so a missing grant is a 403 in the suite.

# Controller — lifecycle (lesson P/04)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The lifecycle contract of the process `<sub>controller`. The rows refer to the norms of the
lesson [P/04] and of the neighbouring lessons and do not retell them.

[P/02.3]:../02-installer/spec/02.3-installer.norms.md
[P/02.4]:../02-installer/spec/02.4-installer.norms.md
[P/02.5]:../02-installer/spec/02.5-installer.norms.md
[P/04]: spec/04-controller.norms.md
[P/06.6]:../06-console/spec/06.6-console.norms.md
[Stand]:../common/acceptance/README.md
[catalogue]:../common/data/catalog.tsv

## Launch

- **Unit** — `w2c-controller@<sub>.service`, one instance per manifest on every server; there is no leader ([P/02.4] N1.1,
  [P/04]).
- **Launch** — through the runner `w2c-run.sh controller <sub>` with `W2C_ROLE=<sub>controller` ([P/02.4] N1.1, N1.9).
- **Order** — after `configstore.service` (`After`, not `Wants`); the controller waits by itself for the readiness of the
  store, of the rights and of the manifest ([P/02.4] N3 «server start», step 3).

## Environment

| Variable | Meaning | Read phase | Source / setting channel |
|---|---|---|---|
| `W2C_ROLE` | the role `<sub>controller`; not the role of the runner command — code 2 | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `PLATFORM_STORE` | the store door — the role socket `configstore:///run/configstore/<sub>controller.sock` | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `PLATFORM_DIR` | the state root | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `OBJECTS` / `PLATFORM_OBJECTS` | the objects root: the pass report, the snapshot shards | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 «The setting channel» |
| `RESOURCE_ROOT` / `EVENTS` | the events root: its own journal `audit/<sub>controller/e1/…` | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 «The setting channel», [the event journal contract](../common/contracts/event-journal.md) `journal` |
| `SERVER_NAME` | its own server; not by the grammar of the slot suffix — code 2 | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `BOX_ID` | the box | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `HUNG_MOVE_AFTER`, `REACH_BUDGET` | the terms of the fate of a hung slot and the reachability budget | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2, [P/04] N1.4, «Implementation decides» item 4 |
| `W2C_SHRINK_AFTER` | stand only: the shrink term `SHRINK_AFTER`, s; when set — a loud journal line at start; outside the stand it is not set | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2, [P/04] N1.4 `SHRINK_AFTER` |
| `CLUSTER` | the cluster name in the snapshot shard | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2, [P/04] N1.3a |
| `W2C_TLS_DIR` | the root of the kits; its own kit — `<W2C_TLS_DIR>/<sub>controller` | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2, N1.6 |
| `W2C_ENV`, `W2C_SUB_ENV` | the environment files: the common one and the subsystem one | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.2 |
| `NOTIFY_SOCKET` | the systemd watchdog | process start | [daemon-flags.tsv](forms/daemon-flags.tsv); [P/02.4] N1.1 `notify` |

The environment files are read by parsing, not by `source` ([the environment file contract](../common/contracts/env-file.md)); the order — the unit values, the role file, `w2c.env`, the subsystem file
([P/02.4] N1.2).

## Flags

None: the setting channel is the environment only ([P/02.4] N1.2 «The setting channel and the layout of `PLATFORM_DIR`»). The
argument of the runner command is the subsystem name `<sub>`.

## Directories and files

- **Store rows** — through the role socket, the rights — the rights file [P/02.5] N1.4. The rows of the lesson — [catalogue], owner `P/04`:
  `<sub>/placement/<id>`, `<sub>/workers/<name>`, `<sub>/want/<host>`, `<sub>/controller/placement_turn`,
  `<sub>/controller/placement_intent`, `<sub>/decommissioned/<host>`; participation in `<sub>/slots/<name>` (a proposal) and `<sub>/<manifest:unit.rows>/<id>`
  (`delete_after`).
- **Objects** in the objects root: the pass report `<sub>/controller/pass` ([P/04] N1.2), the snapshot shards
  `<sub>/snapshot/<worker>`, `<sub>/snapshot/unplaced` ([P/04] N1.3a). File names — one encoding ([the event journal contract](../common/contracts/event-journal.md) «File names in shared trees»).
- **Cluster objects** (the heartbeats of workers and resources, the reports) the controller reads through the resource of its own server (the
  objects door [P/05](../05-resource/spec/05-resource.norms.md), `scope`); without a resource on its own server with `cluster://` — «unknown», not «no» ([the object store client contract](../common/contracts/object-client.md) `door`); a stand that needs the worker heartbeats
  puts a resource on the server of the controller ([P/04] N3 «pass()» step 0).
- **Reads**: the worker heartbeats `<sub>/heartbeats/<name>`, the resource heartbeat `platform/resources/<server>/heartbeat`,
  `platform/manifest/<sub>` and the mark `/rev`, `platform/schema`, `platform/servers/*`, `platform/doors/*`,
  `platform/decommission/*`, `platform/drain`, the slots `<sub>/slots/<name>`, the places `<sub>/holds/<place>` ([catalogue]);
  the placement turn and the intent (`<sub>/controller/placement_turn`, `placement_intent`) it both writes and reads ([P/04] N1.5).
- **The build word** (`BUILD`) of the controller is not in the output: it writes no heartbeat and is not in `processes` of `/schema`
  ([P/06.6] N2.3 `GET /schema`).
- **Does not write** into the events root, except its own journal `audit/<sub>controller/e1/…` (the event journal contract `journal`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | a manifest change: the mark `platform/manifest/<sub>/rev` is above the remembered one or has disappeared — stop, the supervisor starts it again | [P/02.3] N3 «Manifest change» |
| 2 | the manifest mark is out of form at a running process — a stop, a restart refuses until the operator fixes the mark | [P/02.3] N3 «Manifest change», N4 |
| 2 | the store schema is above its own or not a number | [P/04] N3 «controller start — schema check» |
| 2 | there is no manifest row or mark, the read is not confirmed, `sha256` is not the right one, the manifest or the catalogue is refused | [P/02.3] N3 «Process start» |
| 2 | the environment file is not by the grammar; `SERVER_NAME` is not by the grammar; `W2C_ROLE` is not the role of the command | [P/02.4] N1.2, N4 |
| ≠ 0 | another start refusal — a log line names the source | [P/02.3] N3 «Process start» |

`RestartPreventExitStatus` from its P/02.4 unit source: after the code 2 the unit is not restarted until an operator action ([P/02.4] N1.1).

## Signals and readiness

- **Readiness** — `Type=notify`: `READY=1` after the schema check and the manifest read, `WATCHDOG=1` at the boundaries of completed decisions and of progress of the pass, not from an independent timer, so that a hung call is not masked;
  `WatchdogSec` from its P/02.4 unit source (SHOULD) limits the gap between notifications, the finite budget of a pass is a separate existing obligation; without `NOTIFY_SOCKET` it is silent ([P/02.4] N1.1 `notify`, `watchdog`).
- **The first LOST_AFTER** after start it judges nobody: what is seen for the first time has «just changed» ([P/04] N3 «pass()» step 0, N1.4a
  `fresh_controller`).
- **SIGTERM** — an orderly exit; an unfinished intent is completed by the next holder of the turn
  ([P/04] N1.5, N3 «accept and complete a decision»). **SIGKILL** — the same for the neighbour: the state is only in the rows.
- **Restart** — `Restart=always`, `RestartSec` from its P/02.4 unit source, except the code 2 ([P/02.4] N1.1).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) N1.1 `dirs`).

- The command of the «Stand» with the substitution `{sub}` (`testsub` when there is no `<sub>`); `{data}` is `PLATFORM_DIR`, the stand turns
  the substitutions into the environment of [P/02.4] N1.2 ([Stand] «One data directory»).
- The command printing the pass report — a template with `{data}` and `{sub}` ([Stand]).
- The rights of the acceptance stand — `{rights}` from the manifests of the stand by the rights output command ([Stand]).

## Open

- The pass outcome when the resource of the server is unreadable the controller derives from the resource heartbeat and the presence lock (P/05 N1.4, [the presence lock contract](../common/contracts/presence-lock.md));
  the controller resumes from the common state and has no open lifecycle rows.

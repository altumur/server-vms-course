# Controller — lifecycle (lesson P/04)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the process `<sub>controller` (ADR-0083 addendum (2) item 1). The rows refer to the norms of the
lesson [P/04] (stage B) and of the neighbouring lessons and do not retell them.

[P/02.3]: ../02-installer/spec/02.3-installer.norms.md
[P/02.4]: ../02-installer/spec/02.4-installer.norms.md
[P/02.5]: ../02-installer/spec/02.5-installer.norms.md
[P/04]: spec/04-controller.norms.md
[P/06.6]: ../06-console/spec/06.6-console.norms.md
[Stand]: ../common/acceptance/README.md
[catalogue]: ../common/data/catalog.tsv

## Launch

- **Unit** — `w2c-controller@<sub>.service`, one instance per manifest on every server; there is no leader ([P/02.4] Н1.1,
  [P/04]).
- **Launch** — through the runner `w2c-run.sh controller <sub>` with `W2C_ROLE=<sub>controller` ([P/02.4] Н1.1, Н1.9).
- **Order** — after `configstore.service` (`After`, not `Wants`); the controller waits by itself for the readiness of the
  store, of the rights and of the manifest ([P/02.4] Н3 «server start», step 3).

## Environment

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `<sub>controller`; not the role of the runner command — code 2 | set by the unit | [P/02.4] Н1.2 |
| `PLATFORM_STORE` | the store door — the role socket `configstore:///run/configstore/<sub>controller.sock` | `file://<PLATFORM_DIR>/config` (the profile of a box of one implementation) | [P/02.4] Н1.2 |
| `PLATFORM_DIR` | the state root | `/data/platform` | [P/02.4] Н1.2 |
| `OBJECTS` / `PLATFORM_OBJECTS` | the objects root: the pass report, the snapshot shards | `<PLATFORM_DIR>/objects` | [P/02.4] Н1.2 «The setting channel» |
| `RESOURCE_ROOT` / `EVENTS` | the events root: its own journal `audit/<sub>controller/e1/…` | `<PLATFORM_DIR>/events` | [P/02.4] Н1.2 «The setting channel», [the event journal contract](../common/contracts/event-journal.md) `journal` |
| `SERVER_NAME` | its own server; not by the grammar of the slot suffix — code 2 | the short hostname | [P/02.4] Н1.2 |
| `BOX_ID` | the box | `/etc/machine-id`, otherwise the hostname | [P/02.4] Н1.2 |
| `HUNG_MOVE_AFTER`, `REACH_BUDGET` | the terms of the fate of a hung slot and the reachability budget | 900, 10 | [P/02.4] Н1.2, [P/04] Н1.4, «Implementation decides» item 4 |
| `W2C_SHRINK_AFTER` | stand only: the shrink term `SHRINK_AFTER`, s; when set — a loud journal line at start; outside the stand it is not set (review of stage B 3–5, № 18) | not set (`SHRINK_AFTER` 300) | [P/02.4] Н1.2, [P/04] Н1.4 `SHRINK_AFTER` |
| `CLUSTER` | the cluster name in the snapshot shard | `local` | [P/02.4] Н1.2, [P/04] Н1.3а |
| `W2C_TLS_DIR` | the root of the kits; its own kit — `<W2C_TLS_DIR>/<sub>controller` | `/etc/w2c/tls` | [P/02.4] Н1.2, Н1.6 |
| `W2C_ENV`, `W2C_SUB_ENV` | the environment files: the common one and the subsystem one | `/etc/w2c/w2c.env`; without a value — none | [P/02.4] Н1.2 |
| `NOTIFY_SOCKET` | the systemd watchdog | — | [P/02.4] Н1.1 `notify` |

The environment files are read by parsing, not by `source` ([the environment file contract](../common/contracts/env-file.md)); the order — the unit values, the role file, `w2c.env`, the subsystem file
([P/02.4] Н1.2).

## Flags

None: the setting channel is the environment only ([P/02.4] Н1.2 «The setting channel and the layout of `PLATFORM_DIR`»). The
argument of the runner command is the subsystem name `<sub>`.

## Directories and files

- **Store rows** — through the role socket, the rights — the rights file [P/02.5] Н1.4. The rows of the lesson — [catalogue], owner `P/04`:
  `<sub>/placement/<id>`, `<sub>/workers/<имя>`, `<sub>/want/<сервер>`, `<sub>/controller/placement_turn`,
  `<sub>/controller/placement_intent`, `<sub>/decommissioned/<сервер>`; participation in `<sub>/slots/<имя>` (a proposal) and `<sub>/<manifest:unit.rows>/<id>`
  (`delete_after`).
- **Objects** in the objects root: the pass report `<sub>/controller/pass` ([P/04] Н1.2), the snapshot shards
  `<sub>/snapshot/<воркер>`, `<sub>/snapshot/unplaced` ([P/04] Н1.3а). File names — one encoding ([the event journal contract](../common/contracts/event-journal.md) «File names in shared trees»).
- **Cluster objects** (the heartbeats of workers and resources, the reports) the controller reads through the resource of its own server (the
  objects door [P/05](../05-resource/spec/05-resource.norms.md), `scope`); without a resource on its own server with `cluster://` — «unknown», not «no» ([the object store client contract](../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision 2026-10-27); a stand that needs the worker heartbeats
  puts a resource on the server of the controller ([P/04] Н3 «pass()» step 0; ADR-0084 addendum (2) Р17; review of stage A
  3–5, № 22).
- **Reads**: the worker heartbeats `<sub>/heartbeats/<имя>`, the resource heartbeat `platform/resources/<server>/heartbeat`,
  `platform/manifest/<sub>` and the mark `/rev`, `platform/schema`, `platform/servers/*`, `platform/doors/*`,
  `platform/decommission/*`, `platform/drain`, the slots `<sub>/slots/<имя>`, the places `<sub>/holds/<место>` ([catalogue]);
  the placement turn and the intent (`<sub>/controller/placement_turn`, `placement_intent`) it both writes and reads ([P/04] Н1.5).
- **The build word** (`BUILD`) of the controller is not in the output: it writes no heartbeat and is not in `processes` of `/schema`
  ([P/06.6] Н2.3 `GET /schema`).
- **Does not write** into the events root, except its own journal `audit/<sub>controller/e1/…` (the event journal contract `journal`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | a manifest change: the mark `platform/manifest/<sub>/rev` is above the remembered one or has disappeared — stop, the supervisor starts it again | [P/02.3] Н3 «Manifest change» |
| 2 | the manifest mark is out of form at a running process — a stop, a restart refuses until the operator fixes the mark (review of stage A 6–7, Б2) | [P/02.3] Н3 «Manifest change», Н4 |
| 2 | the store schema is above its own or not a number | [P/04] Н3 «controller start — schema check» |
| 2 | there is no manifest row or mark, the read is not confirmed, `sha256` is not the right one, the manifest or the catalogue is refused | [P/02.3] Н3 «Process start» |
| 2 | the environment file is not by the grammar; `SERVER_NAME` is not by the grammar; `W2C_ROLE` is not the role of the command | [P/02.4] Н1.2, Н4 |
| ≠ 0 | another start refusal — a log line names the source | [P/02.3] Н3 «Process start» |

`RestartPreventExitStatus=2`: after the code 2 the unit is not restarted until an operator action ([P/02.4] Н1.1).

## Signals and readiness

- **Readiness** — `Type=notify`: `READY=1` after the schema check and the manifest read, `WATCHDOG=1` on every turn of the pass;
  `WatchdogSec=360` (SHOULD); without `NOTIFY_SOCKET` it is silent ([P/02.4] Н1.1 `notify`, `watchdog`).
- **The first 45 s** after start it judges nobody: what is seen for the first time has «just changed» ([P/04] Н3 «pass()» step 0, Н1.4а
  `fresh_controller`).
- **SIGTERM** — an orderly exit; an unfinished intent is completed by the next holder of the turn
  ([P/04] Н1.5, Н3 «accept and complete a decision»). **SIGKILL** — the same for the neighbour: the state is only in the rows.
- **Restart** — `Restart=always`, `RestartSec=2`, except the code 2 ([P/02.4] Н1.1).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

- The command of the «Stand» with the substitution `{sub}` (`testsub` when there is no `<sub>`); `{data}` is `PLATFORM_DIR`, the stand turns
  the substitutions into the environment of [P/02.4] Н1.2 ([Stand] «Один каталог данных»).
- The command printing the pass report — a template with `{data}` and `{sub}` ([Stand]).
- The rights of the stand of the acceptances moved from М10/4–11 (review of stage B 3–5, № 34) — `{rights}` from the manifests of the stand by the rights output command ([Stand]).

## Open

- The pass outcome when the resource of the server is unreadable the controller derives from the resource heartbeat and the presence lock (P/05 Н1.4, [the presence lock contract](../common/contracts/presence-lock.md));
  the second pilot confirmed the replaceability of the controller on the common state — it has no open lifecycle rows.

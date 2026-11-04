# Worker — lifecycle (lesson P/03)

This English text is the source; the Russian [`lifecycle.md`](../lifecycle.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the process `<sub>worker` — the worker SDK in any language (ADR-0083 addendum (2) item 1): start, name,
environment, presence lock, exit codes, signals. The norms are not retold here: each line leads to its norm.

Norms: the lesson chapters [3.2](../spec/03.2-worker.norms.md) (Н1.4 the slot name, Н3 «start()», «schema check by the worker», Н4),
[3.3](../spec/03.3-worker.norms.md) (Н3 «loop()»), [3.4](../spec/03.4-worker.norms.md) (Н1.1 heartbeat, Н3 «start() — the budget step»,
«stop by SIGTERM», Н4), [3.5](../spec/03.5-worker.norms.md) (Н1.2 the key ring, Н3 «open»), [3.6](../spec/03.6-worker.norms.md)
(Н1.2 events);
[P/02.4](../../02-installer/spec/02.4-installer.norms.md) (Н1.1 units, Н1.2 environment, Н1.5
workers on demand), [P/02.3](../../02-installer/spec/02.3-installer.norms.md) (Н3 «Process start», «Manifest
change»), [P/06.6](../../06-console/spec/06.6-console.norms.md) (Н1.1а the schema row),
[presence lock contract](../../common/contracts/presence-lock.md), [event journal contract](../../common/contracts/event-journal.md) (buckets),
[local token door contract](../../common/contracts/local-token-door.md) (the token request, chapter 3.7).

## Start

| What | How | Norm |
|---|---|---|
| worker | the unit `<dep>-<sub>worker@.service`: the instance `%i` is the slot name `<prefix>-<SERVER_NAME>-<n>` (1 — the base one, 2…99 — on the controller's order, ADR-0084), as the command argument; a server in `%i` ≠ `SERVER_NAME` — code 2; `W2C_ROLE=<sub>worker`; `Type=notify`, `NotifyAccess=main`, `WatchdogSec=360` | P/02.4 Н1.1 |
| slot name | the command argument; none — the variable `slot.name_env`, if the manifest declared it; otherwise without a name | P/03.2 Н3 «start()» step 3 |
| worker on demand | the same unit, the instance `<prefix>-<SERVER_NAME>-<n>`, n 2…99; started and stopped by the workers script by the series `<sub>_workers_wanted{server}`; the slot capture is the usual one | P/02.4 Н1.1, Н1.5 |
| start by steps | schema → manifest → memory budget → instance → presence lock → name → capture | P/03.2 Н3 «start()» steps 0–3 (step 1 — P/03.4 Н3 «start() — the budget step»), P/03.2 Н3 «schema check by the worker» |

## Environment

The environment is built by the runner `w2c-run.sh worker <sub> <слот>` (a worker on the domain — `domainworker <sub>`) in the order of P/02.4 Н1.2,
the same as for the platform processes; the runner executes `worker.exec` of the manifest row and passes `W2C_MANIFEST_REV`
(ADR-0091 addendum (4)–(6)): the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` →
the subsystem file, what was read earlier wins ([02-installer/lifecycle.md](../../02-installer/lifecycle.md)).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| the manifest variable `slot.name_env` | the slot name, only if the manifest declared it (`testsub2` — `TALLY_NAME`) | — | P/02.4 Н1.2 |
| `BOX_ID` | the box | `/etc/machine-id`, otherwise the hostname | P/02.4 Н1.2, P/03.2 Н3 «start()» step 2 |
| `SERVER_NAME` | the server by the grammar of the slot suffix | the short hostname | P/02.4 Н1.2 |
| `LABELS` | the node labels | — | P/02.4 Н1.2 |
| `INSTANCE_ID` | the instance instead of `<box>:<pid>:<6hex>`; not by the grammar — a start refusal, code 2 (analysis of the review of stage B 3–5, № 7) | — | P/02.4 Н1.2, P/03.2 Н3 «start()» step 2, Н4 |
| `PLATFORM_DIR` | the state root | `/data/platform` | P/02.4 Н1.2 «The setting channel and the layout» |
| `PLATFORM_STORE` | the store door `configstore:///run/configstore/<sub>worker.sock` | `file://<PLATFORM_DIR>/config` (a box of one implementation) | P/02.4 Н1.2 |
| `OBJECTS` / `PLATFORM_OBJECTS` | the object store | `file://`; `cluster://` with configstore | P/02.4 Н1.2 |
| `RESOURCE_ROOT` / `EVENTS` | the event root: the buckets and the presence lock | `<PLATFORM_DIR>/events` | P/02.4 Н1.2, P/05 Н1.4, the presence lock contract |
| `SECRETS_KEY` | the ring — at the secret holders | — | P/03.5 Н1.2 |
| `W2C_ROLE`, `W2C_TLS_DIR` | the role and the kit; `W2C_ROLE` ≠ the role of the runner command (`worker <sub>` — `<sub>worker`, `domainworker <sub>` — `<sub>domain`) — a launch refusal, code 2 (ADR-0091 addendum (5) item 1) | `<sub>worker`; `/etc/w2c/tls` | P/02.4 Н1.1, Н1.2, Н1.6 |
| `AGENT_TOKEN_DIR` | the socket directory of the agent's local token door: the worker requests a token at `<AGENT_TOKEN_DIR>/<W2C_ROLE>.sock` (chapter 3.7 Н1.5) | `/run/w2c/domainagent` | [local token door contract](../../common/contracts/local-token-door.md) «Сокет роли» (analysis of the review of stage A 8–10, № 1 / decision 1) |
| `CAPACITY`, `WORKER_MEMORY_MB` | the capacity and the memory budget | — | P/02.4 Н1.2, Н1.5 `memory` |
| `BUILD` | the build word in the heartbeat (chapter 6.6) | `dev` | P/02.4 Н1.2, P/06.6 Н1.1а |
| `W2C_ENV`, `W2C_SUB_ENV` | environment files | `/etc/w2c/w2c.env`; the unit's path | P/02.4 Н1.2 |
| `NOTIFY_SOCKET` | the systemd watchdog | — | P/02.4 Н1.2 |

`SLOT_INDEX` is removed: the worker unit does not set it (P/02.4 Н1.1), the slot name is the argument `%i` or the variable `slot.name_env`
(P/03.2 Н3 «start()» step 3) (analysis of the review of stage B 3–5, № 7).

## Flags

None: the setting channel is only the environment and the name argument (P/02.4 Н1.2 «The setting channel»).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `<корень событий>/.workers/<sub>/<экземпляр>.lock` | the presence lock: the content anew at start, an exclusive `flock` for the whole lifetime | [catalogue](../../common/data/catalog.tsv), the presence lock contract, P/03.2 Н3 «start()» step 2б |
| `<корень событий>/<sub>/<unit>/e<эпоха>/…`, `<sub>.alarms/…`, `audit/<sub>worker/e1/…` | event buckets, the `append` participant | [catalogue](../../common/data/catalog.tsv), the event journal contract, P/03.6 Н1.2 |
| the objects `<sub>/heartbeats/<имя>`, `<sub>/contenders/<имя>/<коробка>` | the heartbeat and the contender mark | [catalogue](../../common/data/catalog.tsv), P/03.4 Н1.1, P/03.2 Н1.4а |
| `/etc/w2c/secrets/platform.key` (`SECRETS_KEY`) | the ring — read only | [catalogue](../../common/data/catalog.tsv), [sealing contract](../../common/contracts/sealing.md) |
| component names in the trees | one encoding `%XX`, `%h<sha256>`; the `%h` threshold — by the full file name (the component, the norm's suffix, the reserve of the temporary name; analysis of the review of stage B 3–5, № 20) | the event journal contract «Имена файлов в общих деревьях» |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | the manifest mark changed — stop, the supervisor starts it again; an orderly stop by SIGTERM | P/02.3 Н3 «Manifest change», P/03.4 Н3 «stop by SIGTERM» |
| 2 | the manifest mark is not by the form at a running worker — a stop, the restart refuses until the operator fixes the mark (P/02.3 Н3 «Manifest change»; analysis of the review of stage A 6–7, Б2) | P/02.3 Н3, Н4 |
| 2 | a start refusal: the schema is above the build or not a number; no manifest row or mark, a wrong sha256, the manifest is refused; the name is not by the grammar or not with `prefix`; the presence lock: an error of open, flock or of writing the content (a blocking flock waits, it does not refuse — analysis of the review of stage B 6–7, № 45); an environment file line not by the grammar; a server in `%i` ≠ `SERVER_NAME` | P/03.2 Н3 «schema check by the worker», P/02.3 Н3, P/03.2 Н3 «start()» steps 2а, 2б, P/02.4 Н1.2, Н1.5 |
| ≠ 0 | the memory budget is exceeded — do not start (`MemoryBudgetRefused`); the norm does not set its own code | P/03.4 Н3 «start() — the budget step», Н4; P/02.4 Н4 |
| 2 | after renewal the schema is above the build — fence, give the name back, exit; the slot is not released | P/03.2 Н3 «schema check by the worker», Н4 |

## Signals and readiness

| What | How | Norm |
|---|---|---|
| SIGTERM | the stand-in and the polling — stop; `before_stop_all`, the units, the place writers; the last heartbeat; let the place go, then release the slot (analysis of the review of stage B 3–5, № 4); `after_stop`; `TimeoutStopSec` = `worker.stop_timeout` of the manifest (20…50, default 20) | P/03.4 Н3 «stop by SIGTERM», P/02.4 Н1.1 |
| SIGKILL | writes nothing: the controller judges by the silence and the presence lock | P/03.4 Н3 «stop by SIGTERM», P/05 Н1.4 |
| readiness | `READY=1` after capturing the name; `WATCHDOG=1` on every turn of the loop, not from the stand-in | P/02.4 Н1.1 `notify`, `watchdog` |
| restart | `Restart=always`, `RestartSec=2`, `RestartPreventExitStatus=2` | P/02.4 Н1.1 `common` |
| a sealed unit | is not launched, takes no epochs, in `status` — `why` | P/03.5 Н3 «open», P/03.4 Н1.1 |

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the profile's role launch command — the [common acceptance
README](../../common/acceptance/README.md) «Стенд без root»; the process does not create the roots ([P/02.4](../../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

«Стенд» — the [common acceptance README](../../common/acceptance/README.md): `@start worker [<sub>]
<имя>` — the name by the substitution `{name}` (the argument), `{sub}`; the environment from `{data}` (`PLATFORM_DIR`), the stand's `BOX_ID`,
`SERVER_NAME`, `PLATFORM_STORE` of the role socket, the variable `slot.name_env`, if the manifest declared it; `@sigterm`, `@sigkill`;
workers on demand — the directive `@grow` (it executes the series `workers_wanted` instead of the script).

## Open

- `SERVER_NAME` and `INSTANCE_ID` are checked against P/02.4 Н1.2.

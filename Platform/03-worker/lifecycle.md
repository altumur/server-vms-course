# Worker — lifecycle (lesson P/03)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The lifecycle contract of the process `<sub>worker` — the worker SDK in any language: start, name,
environment, presence lock, exit codes, signals. The norms are not retold here: each line leads to its norm.

Norms: the lesson chapters [3.2](spec/03.2-worker.norms.md) (N1.4 the slot name, N3 «start()», «schema check by the worker», N4),
[3.3](spec/03.3-worker.norms.md) (N3 «loop()»), [3.4](spec/03.4-worker.norms.md) (N1.1 heartbeat, N3 «start() — the budget step»,
«stop by SIGTERM», N4), [3.5](spec/03.5-worker.norms.md) (N1.2 the key ring, N3 «open»), [3.6](spec/03.6-worker.norms.md)
(N1.2 events);
[P/02.4](../02-installer/spec/02.4-installer.norms.md) (N1.1 units, N1.2 environment, N1.5
workers on demand), [P/02.3](../02-installer/spec/02.3-installer.norms.md) (N3 «Process start», «Manifest
change»), [P/06.6](../06-console/spec/06.6-console.norms.md) (N1.1a the schema row),
[presence lock contract](../common/contracts/presence-lock.md), [event journal contract](../common/contracts/event-journal.md) (buckets),
[local token door contract](../common/contracts/local-token-door.md) (the token request, chapter 3.7).

## Start

| What | How | Norm |
|---|---|---|
| worker | Unit template and slot-name argument, role, notify/watchdog and server check follow their owner; admission precedes the presence lock | P/02.4 N1.1; P/03.2 N3 start |
| slot name | the command argument; none — the variable `slot.name_env`, if the manifest declared it; otherwise without a name | P/03.2 N3 «start()» step 3 |
| worker on demand | The workers script starts/stops by `<sub>_workers_wanted{server}`; name and ordinal range follow the owner, capture is ordinary | P/02.4 N1.1, N1.5 |
| start by steps | schema → manifest → memory budget → instance → presence lock → name → capture | P/03.2 N3 «start()» steps 0–3 (step 1 — P/03.4 N3 «start() — the budget step»), P/03.2 N3 «schema check by the worker» |

## Environment

The environment is built by the runner `w2c-run.sh worker <sub> <slot>` (a worker on the domain — `domainworker <sub>`) in the order of P/02.4 N1.2,
the same as for the platform processes; the runner executes `worker.exec` of the manifest row and passes `W2C_MANIFEST_REV`:
the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` →
the subsystem file, what was read earlier wins ([02-installer/lifecycle.md](../02-installer/lifecycle.md)).

The complete static input catalogue, types, requiredness and defaults are [daemon-flags.tsv](forms/daemon-flags.tsv). This table records only meaning and read phase; each row points to that form flag. A dynamic slot.name_env is consulted when the name argument is absent, by P/03.2 N3 start. Ring rereads and token connections follow their imported contracts.

| Input | Meaning and phase | Source |
|---|---|---|
| `<name>` | Preferred ordinary worker name; selected after manifest/instance admission. | `daemon-flags.tsv`, flag=`<name>` |
| `$BOX_ID` | Box identity, resolved before instance and presence-lock creation. | `daemon-flags.tsv`, flag=`$BOX_ID` |
| `$SERVER_NAME` | Nonempty current server, admitted before the presence lock. | `daemon-flags.tsv`, flag=`$SERVER_NAME` |
| `$LABELS` | Node labels for startup name/place admission. | `daemon-flags.tsv`, flag=`$LABELS` |
| `$INSTANCE_ID` | Current process identity, resolved and checked before the presence lock. | `daemon-flags.tsv`, flag=`$INSTANCE_ID` |
| `$PLATFORM_DIR` | Initial platform state root. | `daemon-flags.tsv`, flag=`$PLATFORM_DIR` |
| `$PLATFORM_STORE` | Store endpoint resolved at SDK initialization. | `daemon-flags.tsv`, flag=`$PLATFORM_STORE` |
| `$OBJECTS` | Object-store setting, resolved with its existing paired name at initialization. | `daemon-flags.tsv`, flag=`$OBJECTS` |
| `$PLATFORM_OBJECTS` | Paired object-store setting, same initialization step. | `daemon-flags.tsv`, flag=`$PLATFORM_OBJECTS` |
| `$RESOURCE_ROOT` | Event/presence root resolved with its paired name at initialization. | `daemon-flags.tsv`, flag=`$RESOURCE_ROOT` |
| `$EVENTS` | Paired event/presence-root setting, same initialization step. | `daemon-flags.tsv`, flag=`$EVENTS` |
| `$SECRETS_KEY` | Initial ring-file reference; ring reading/reloads follow the sealing contract. | `daemon-flags.tsv`, flag=`$SECRETS_KEY` |
| `$W2C_ROLE` | Launcher route identity; checked before role-file use; direct SDK rules stay those of the input form. | `daemon-flags.tsv`, flag=`$W2C_ROLE` |
| `$W2C_TLS_DIR` | TLS-kit directory selected at initialization. | `daemon-flags.tsv`, flag=`$W2C_TLS_DIR` |
| `$AGENT_TOKEN_DIR` | Local token-door directory; connections follow the local-token-door contract. | `daemon-flags.tsv`, flag=`$AGENT_TOKEN_DIR` |
| `$CAPACITY` | Initial worker capacity used by the memory-budget step. | `daemon-flags.tsv`, flag=`$CAPACITY` |
| `$WORKER_MEMORY_MB` | Initial budget for the memory check before the presence lock. | `daemon-flags.tsv`, flag=`$WORKER_MEMORY_MB` |
| `$BUILD` | Build word used by the initial and later base heartbeat. | `daemon-flags.tsv`, flag=`$BUILD` |
| `$W2C_MANIFEST_REV` | Launch-time published manifest reference, checked before the name capture. | `daemon-flags.tsv`, flag=`$W2C_MANIFEST_REV` |
| `$W2C_ENV` | Runner environment-file input; read in launcher order, not recursively by SDK. | `daemon-flags.tsv`, flag=`$W2C_ENV` |
| `$W2C_SUB_ENV` | Runner subsystem-file input in that same order. | `daemon-flags.tsv`, flag=`$W2C_SUB_ENV` |
| `$W2C_BOX` | Initial box-layout root. | `daemon-flags.tsv`, flag=`$W2C_BOX` |
| `$CONSOLE_ORIGINS` | Initial CORS origin setting for the subsystem process door. | `daemon-flags.tsv`, flag=`$CONSOLE_ORIGINS` |
| `$TIMEZONE` | Initial display-timezone setting; protocol Time is unchanged. | `daemon-flags.tsv`, flag=`$TIMEZONE` |
| `$NOTIFY_SOCKET` | Systemd notification endpoint; notify from the ordinary loop, not stand-in. | `daemon-flags.tsv`, flag=`$NOTIFY_SOCKET` |

## Flags

None: the setting channel is only the environment and the name argument (P/02.4 N1.2 «The setting channel»).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `<events root>/.workers/<sub>/<instance>.lock` | the presence lock: the content anew at start, an exclusive `flock` for the whole lifetime | [catalogue](../common/data/catalog.tsv), the presence lock contract, P/03.2 N3 «start()» step 2b |
| `<events root>/<sub>/<unit>/e<epoch>/…`, `<sub>.alarms/…`, `audit/<sub>worker/e1/…` | event buckets, the `append` participant | [catalogue](../common/data/catalog.tsv), the event journal contract, P/03.6 N1.2 |
| the objects `<sub>/heartbeats/<name>`, `<sub>/contenders/<name>/<box>` | the heartbeat and the contender mark | [catalogue](../common/data/catalog.tsv), P/03.4 N1.1, P/03.2 N1.4a |
| `SECRETS_KEY` | the ring — read only | [catalogue](../common/data/catalog.tsv), [sealing contract](../common/contracts/sealing.md) |
| component names in the trees | one encoding `%XX`, `%h<sha256>`; the `%h` threshold — by the full file name (the component, the norm's suffix, the reserve of the temporary name) | the event journal contract «File names in shared trees» |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | the manifest mark changed — stop, the supervisor starts it again; an orderly stop by SIGTERM | P/02.3 N3 «Manifest change», P/03.4 N3 «stop by SIGTERM» |
| 2 | the manifest mark is not by the form at a running worker — a stop, the restart refuses until the operator fixes the mark (P/02.3 N3 «Manifest change») | P/02.3 N3, N4 |
| 2 | a start refusal: the schema is above the build or not a number; no manifest row or mark, a wrong sha256, the manifest is refused; the name is not by the grammar or not with `prefix`; the presence lock: an error of open, flock or of writing the content (a blocking flock waits, it does not refuse); an environment file line not by the grammar; a server in `%i` ≠ `SERVER_NAME` | P/03.2 N3 «schema check by the worker», P/02.3 N3, P/03.2 N3 «start()» steps 2a, 2b, P/02.4 N1.2, N1.5 |
| ≠ 0 | the memory budget is exceeded — do not start (`MemoryBudgetRefused`); the norm does not set its own code | P/03.4 N3 «start() — the budget step», N4; P/02.4 N4 |
| 2 | after renewal the schema is above the build — fence, give the name back, exit; the slot is not released | P/03.2 N3 «schema check by the worker», N4 |

## Signals and readiness

| What | How | Norm |
|---|---|---|
| SIGTERM | the stand-in and the polling — stop; `before_stop_all`, the units, the place writers; the last heartbeat; let the place go, then release the slot; `after_stop`; `TimeoutStopSec` = `worker.stop_timeout` of the manifest (bounds/default by the owner form) | P/03.4 N3 «stop by SIGTERM», P/02.4 N1.1 |
| SIGKILL | writes nothing: the controller judges by the silence and the presence lock | P/03.4 N3 «stop by SIGTERM», P/05 N1.4 |
| readiness | `READY=1` after capturing the name; `WATCHDOG=1` on every turn of the loop, not from the stand-in | P/02.4 N1.1 `notify`, `watchdog` |
| restart | Supervisor policy follows the unit owner, without a second copy of its timings/defaults | P/02.4 N1.1 `common` |
| a sealed unit | is not launched, takes no epochs, in `status` — `why` | P/03.5 N3 «open», P/03.4 N1.1 |

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the profile's role launch command — the [common acceptance
README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) N1.1 `dirs`).

«Stand» — the [common acceptance README](../common/acceptance/README.md): `@start worker [<sub>]
<name>` — the name by the substitution `{name}` (the argument), `{sub}`; the environment from `{data}` (`PLATFORM_DIR`), the stand's `BOX_ID`,
`SERVER_NAME`, `PLATFORM_STORE` of the role socket, the variable `slot.name_env`, if the manifest declared it; `@sigterm`, `@sigkill`;
workers on demand — the directive `@grow` (it executes the series `workers_wanted` instead of the script).

## Open

- `SERVER_NAME` and `INSTANCE_ID` are checked against P/02.4 N1.2.

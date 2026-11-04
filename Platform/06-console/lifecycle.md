# Cluster console — lifecycle (lesson P/06)

The lifecycle contract of the process `console` (ADR-0083 addendum (2) item 1). The rows refer to the chapters of the lesson and do not
retell them (stage B, the move of lesson 6).

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

[P/02.3]: ../02-installer/spec/02.3-installer.norms.md
[P/02.4]: ../02-installer/spec/02.4-installer.norms.md
[P/03.2]: ../03-worker/spec/03.2-worker.norms.md
[P/06.1]: spec/06.1-console.norms.md
[P/06.2]: spec/06.2-console.norms.md
[P/06.3]: spec/06.3-console.norms.md
[P/06.4]: spec/06.4-console.norms.md
[P/06.5]: spec/06.5-console.norms.md
[P/06.6]: spec/06.6-console.norms.md
[P/06.8]: spec/06.8-console.norms.md
[P/06.9]: spec/06.9-console.norms.md
[Stand]: ../common/acceptance/README.md
[catalogue]: ../common/data/catalog.tsv

## Launch

- **Unit** — `w2c-console.service` on every server; `User=w2c`,
  `SupplementaryGroups=w2c-store w2c-events w2c-secrets`, `SECRETS_KEY` ([P/02.4] Н1.1).
- **Launch** — through the runner `w2c-run.sh console` with `W2C_ROLE=console` ([P/02.4] Н1.1, Н1.9).
- **Start order** — the check of the schema ([P/06.6] Н3 «console start — schema check»), of the manifest from the rows, the shell
  `CONSOLE_ROOT`; the start does not check the static files of the subsystems: a file without bytes — 503 of its own door ([P/06.5] Н2), the resealing of secrets ([P/06.2] Н3 «reseal at start»), the reaper of requests and of table rows ([P/06.4] Н3 «reaper»), the folder reaper ([P/06.8] Н3 «folder reaper»), the reaper and the leader of operations ([P/06.9] Н3)
  and the marks of bodies ([P/06.1] Н3 «уборка тел»); the deletion of bodies — only in the maintenance window, by the cleanup window command (below)
  ([P/02.4] Н3 «server start», step 4).
- **The console module** is shipped together with the console — the same bytes as in the specification; it is not read from the export catalogue
  while running ([P/06.5] Н1.1 `module`).

## Environment

The environment is assembled by the runner `w2c-run.sh` in the order of P/02.4 Н1.2: the unit values → `roles/<W2C_ROLE>.env` → `w2c.env` →
the subsystem file, what is read earlier wins; the files are read by parsing, not by `source` ([the environment file contract](../common/contracts/env-file.md); [02-installer/lifecycle.md](../02-installer/lifecycle.md)).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `console`; not the role of the runner command — code 2 | set by the unit | [P/02.4] Н1.2 |
| `PLATFORM_STORE` | the store door — the role socket `configstore:///run/configstore/console.sock` | `file://<PLATFORM_DIR>/config` (the profile of a box of one implementation) | [P/02.4] Н1.2 |
| `PLATFORM_DIR` | the state root | `/data/platform` | [P/02.4] Н1.2 |
| `RESOURCE_ROOT` / `EVENTS` | the events root of its own server: the journal `audit/console` and the marks `console/<экземпляр>` | `<PLATFORM_DIR>/events` | [P/02.4] Н1.2, [P/06.4] Н1.2 `writer` |
| `OBJECTS` / `PLATFORM_OBJECTS` | the objects: the bodies `blob`, the cleanup marks | `<PLATFORM_DIR>/objects`; `cluster://` with configstore | [P/02.4] Н1.2 |
| `CONSOLE_ROOT` | the subsystem whose shell is served on `/`; empty or not from the catalogue — code 2 | — | [P/06.5] Н1.1 `root` |
| `CONSOLE_HOST`, `CONSOLE_PORT` | the console address — from `w2c.env` (written by the installer, the unit does not set it; one per box — the clients of their own console build the URL by it as well, [the role certificate contract](../common/contracts/role-certificate.md) `own_url`); TLS — by the role kit (`kit`) and on the loopback too, HTTP is not opened when there is a kit; `::1` — only by an explicit entry; the browser origin with a kit — `https://<SERVER_NAME>:<порт>` in `CONSOLE_ORIGINS` (ADR-0075 addendum 2026-10-26 (2) item 3, (3) items 3–4, (5) item 2) | `127.0.0.1`, `8080` | [P/02.4] Н1.2, Н1.6 `console`, Н1.7 `w2c_env` |
| `CONSOLE_CALL_PORT` | the port of the callback listener, only with a kit and a manifest with `door.pass.calls`, [the role certificate contract](../common/contracts/role-certificate.md) «The callback leaf» | 8081 | [P/02.4] Н1.7 `w2c_env`, ADR-0094 addendum (16) |
| `SECRETS_KEY` | the ring path; set empty — unreadable, 503 | — (the installer layout: for the unit — `<PLATFORM_DIR>/etc/secrets/platform.key`; not set for the process — the development mode with a loud line, review analysis of stage A 6–7, № 19) | [P/06.2] Н1.2, [P/02.4] Н1.1 `dirs` |
| `SERVER_NAME` | the server | the short hostname (`%l`) | [P/02.4] Н1.2 |
| `BOX_ID` | the box; the instance `<коробка>:<pid>:<6 hex>` | `BOX_ID`, otherwise `/etc/machine-id`, otherwise the hostname | [P/02.4] Н1.2, [P/03.2] Н3 «start()» step 2 |
| `CLUSTER` | the cluster name | `local` | [P/02.4] Н1.2 |
| `TIMEZONE` | the time zone of the cluster: the value `timezone` in `/session`; from `w2c.env` (written by the installer); empty or out of form — code 2 | `UTC` | [the environment file contract](../common/contracts/env-file.md); [P/06.3] Н2 |
| `BUILD` | the build word in `/schema` | `dev` | [P/02.4] Н1.2, [P/06.6] Н2.3 |
| `W2C_TLS_DIR` | the root of the kits; its own kit — `<W2C_TLS_DIR>/console` | `/etc/w2c/tls` | [P/02.4] Н1.2, Н1.6 |
| `LOGIN_URL`, `SIGNER_URL`, `DOMAIN_*`, `CLUSTERS` | the domain (the late layer of lesson 6 — [chapter 6.7](spec/06.7-console.norms.md): `CLUSTERS` — Н1.4, `SIGNER_URL` — Н1.8, `DOMAIN_CA`/`RELAY_CA` — the peer contract; `LOGIN_URL` — the guard contract `login_url`) | — | [P/02.4] Н1.2 |
| `W2C_ENV` | the file of common settings | `/etc/w2c/w2c.env` | [P/02.4] Н1.2 |

## Flags

None: the setting channel is the environment only ([P/02.4] Н1.2 «The setting channel and the layout of `PLATFORM_DIR`»).

## Directories and files

- **The ring** — the file `SECRETS_KEY` (the path is set for the unit by the installer — `/etc/w2c/secrets/platform.key` by the layout
  `<PLATFORM_DIR>/etc/secrets/platform.key`, [P/02.4] Н1.1 `dirs`), outside the store directory, the objects root and the events root; the console reads it, only `w2cctl secrets` writes it ([P/06.2] Н1.2, [P/02.4] Н1.2, [catalogue]).
  On reading, the console checks the placement of the ring ([the secret files contract](../common/contracts/secret-files.md) `forbidden`, `daemon`)
  against the roots it knows itself from the environment: the store directory with `PLATFORM_STORE=file://…`, the objects root
  (`OBJECTS`), the events root (`RESOURCE_ROOT` / `EVENTS`). With the store door through the daemon socket (`configstore://…`)
  the `-dir` of the daemon and the directories of its copies are not known to the console — the installation excludes them (the layout of P/02.4 Н1.1); there are no new
  variables (C08-RING-FORBIDDEN-ROOTS-01, the decision of the Domain Specification; the class in P/06 — the decision of the Specification).
- **The events root of its own server** — the journal `audit/console/e1/…` under an exclusive file lock and the operator
  marks `console/<экземпляр>/e1/…`; the names — one `%XX` encoding ([the event journal contract](../common/contracts/event-journal.md),
  [P/06.4] Н1.2 `writer`, `marks`).
- **The objects root** — the bodies `<sub>/blobs/sha256-<hex>` ([P/06.1] Н1.5); the tombstones `.gone/<ключ>` — a resource row, the console
  is a participant `put` in it ([P/05](../05-resource/spec/05-resource.norms.md) Н1.1 «Tombstones»; review analysis of stage A 6–7, № 17).
- **Store rows** — the doors of units and tables, the requests and their accounting, the cleanup marks, the drain, the policy, the server labels,
  the decommission of servers, the schema ([catalogue]: the rows where the participant is `console`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | a manifest change — stop, the supervisor starts it again | [P/02.3] Н3 «Manifest change» |
| 2 | the manifest mark is out of form at a running process — a stop, a restart refuses until the operator fixes the mark (review analysis of stage A 6–7, Б2) | [P/02.3] Н3 «Manifest change», Н4 |
| 2 | the store schema is above its own or not a number | [P/06.6] Н3 «console start — schema check» |
| 2 | the manifest is not read or is refused | [P/02.3] Н3 «Process start» |
| 2 | `CONSOLE_ROOT` is empty or not from the catalogue | [P/06.5] Н1.1 `root`, Н4 |
| 2 | `TIMEZONE` is empty or out of form | [P/06.5] Н4; [the environment file contract](../common/contracts/env-file.md) |
| 2 | the environment file is not by the grammar; `SERVER_NAME` is not by the grammar; `W2C_ROLE` is not the role of the command | [P/02.4] Н1.2, Н4 |
| ≠ 0 | outside the loopback without a kit; another start refusal — a log line names the source | [P/02.4] Н1.6, [P/02.3] Н3 |

An unreadable family row during the resealing at start — a log line, the start is not interrupted ([P/06.2] Н3
«reseal at start»).

## The cleanup window command

The deletion of bodies — by a separate command of the implementation with the flag `--writers-stopped` (the command name — [P/06.1] «Implementation decides»
item 9), not by the process `console`: the operator runs it in an exclusive window, when the writers are stopped. The codes —
[P/06.1] Н2 «Sweep window command» (review analysis of stage A 6–7, № 8):

| Code | When | Norm |
|---|---|---|
| 0 | the window is done, including when there is nothing to delete | [P/06.1] Н2 «Sweep window command», Н3 «уборка тел» |
| 2 | no `--writers-stopped`; a failure to read the references or the list; a CAS conflict of the list — nothing is deleted | [P/06.1] Н2 «Sweep window command» |
| 3 | a failure after the deletions began: a tombstone or a deletion outcome is not confirmed — do not open the writers and the copying | [P/06.1] Н3 «уборка тел» («завершение») |

## Signals and readiness

- **Readiness** — the port `CONSOLE_PORT` ([Stand]); the callback listener is opened before it, if there is one.
- **SIGTERM** — an orderly exit. The claim `<sub>/idem/*` stays in the row, a client retry with the same key completes it
  ([P/06.1] Н3 «create», Н4); the requests stay in the rows, the reaper of the next process completes them ([P/06.4] Н3 «reaper»); the leader gives up the queue of operations, another holder picks them up ([P/06.9] Н3 «leader»)
  (review analysis of stage A 6–7, № 7).
- **Restart** — `Restart=always`, `RestartSec=2`, except the code 2 ([P/02.4] Н1.1). The stand has the directive
  `@restart console` ([Stand]).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

- The command of the «Stand» with the substitution `{port}`; `{data}` is `PLATFORM_DIR`: the stand sets `PLATFORM_DIR={data}`,
  `CONSOLE_PORT={port}`, `PLATFORM_STORE` — the role socket, `SECRETS_KEY={data}/etc/secrets/platform.key` — the ring, which the runner creates
  by the «Stand» command `ring {file}` before the first process, `BOX_ID`,
  `SERVER_NAME` ([Stand] «Один каталог данных»); `CONSOLE_CALL_PORT={cport}` — on the stand with the kit of [the second kind of pass](../common/acceptance/pass/README.md).
- `CONSOLE_ROOT` is named by the acceptance README of the chapter: chapter 6.2 — `testsub2`, the others — `testsub` ([Stand]).

## Open

- None. The stand ring — one path `{data}/etc/secrets/platform.key` (above, «Stand»); `BOX_ID` — by [P/02.4] Н1.2;
  an instance with `:` in the name is representable by the name encoding ([the event journal contract](../common/contracts/event-journal.md)).

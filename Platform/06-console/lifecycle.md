# Cluster console — lifecycle (lesson P/06)

The lifecycle contract of the process `console`. The rows refer to the chapters of the lesson and do not
retell them.

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

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
  `SupplementaryGroups=w2c-store w2c-events w2c-secrets`, `SECRETS_KEY` ([P/02.4] N1.1).
- **Launch** — through the runner `w2c-run.sh console` with `W2C_ROLE=console` ([P/02.4] N1.1, N1.9).
- **Start order** — the check of the schema ([P/06.6] N3 «console start — schema check»), of the manifest from the rows, the shell
  `CONSOLE_ROOT`; the start does not check the static files of the subsystems: a file without bytes — 503 of its own door ([P/06.5] N2), the resealing of secrets ([P/06.2] N3 «reseal at start»), the reaper of requests and of table rows ([P/06.4] N3 «reaper»), the folder reaper ([P/06.8] N3 «folder reaper»), the reaper and the leader of operations ([P/06.9] N3)
  and the marks of bodies ([P/06.1] N3 «body sweep»); the deletion of bodies — only in the maintenance window, by the cleanup window command (below)
  ([P/02.4] N3 «server start», step 4).
- **The console module** is shipped together with the console — the same bytes as in the specification; it is not read from the export catalogue
  while running ([P/06.5] N1.1 `module`).

## Environment

The console input roster, types, requiredness, defaults and validation expressions are the rows for `console` in [forms/daemon-flags.tsv](forms/daemon-flags.tsv). The cleanup-window acknowledgement is a separate command row in that form. This section is not another default registry.

The runner assembles the environment in the order of [P/02.4] N1.2; it parses files under [the environment file contract](../common/contracts/env-file.md), never by `source`. Each form row cites the contract that owns its activation and semantic checks, including listener/kit checks, ring placement, role, server and box identity. Cross-process `DOMAIN_*` and `RELAY_*` configuration belongs to its owning domain/agent process; this reference introduces no console input or flag.

## Flags

None: the setting channel is the environment only ([P/02.4] N1.2 «The setting channel and the layout of `PLATFORM_DIR`»).

## Directories and files

- **The ring** — the file `SECRETS_KEY` (the path is set for the unit by the installer — `/etc/w2c/secrets/platform.key` by the layout
  `<PLATFORM_DIR>/etc/secrets/platform.key`, [P/02.4] N1.1 `dirs`), outside the store directory, the objects root and the events root; the console reads it, only `w2cctl secrets` writes it ([P/06.2] N1.2, [P/02.4] N1.2, [catalogue]).
  On reading, the console checks the placement of the ring ([the secret files contract](../common/contracts/secret-files.md) `forbidden`, `daemon`)
  against the roots it knows itself from the environment: the store directory with `PLATFORM_STORE=file://…`, the objects root
  (`OBJECTS`), the events root (`RESOURCE_ROOT` / `EVENTS`). With the store door through the daemon socket (`configstore://…`)
  the `-dir` of the daemon and the directories of its copies are not known to the console — the installation excludes them (the layout of P/02.4 N1.1); there are no new
  variables.
- **The events root of its own server** — the journal `audit/console/e1/…` under an exclusive file lock and the operator
  marks `console/<instance>/e1/…`; the names — one `%XX` encoding ([the event journal contract](../common/contracts/event-journal.md),
  [P/06.4] N1.2 `writer`, `marks`).
- **The objects root** — the bodies `<sub>/blobs/sha256-<hex>` ([P/06.1] N1.5); the tombstones `.gone/<object-key>` — a resource row, the console
  is a participant `put` in it ([P/05](../05-resource/spec/05-resource.norms.md) N1.1 «Tombstones»).
- **Store rows** — the doors of units and tables, the requests and their accounting, the cleanup marks, the drain, the policy, the server labels,
  the decommission of servers, the schema ([catalogue]: the rows where the participant is `console`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | a manifest change — stop, the supervisor starts it again | [P/02.3] N3 «Manifest change» |
| 2 | the manifest mark is out of form at a running process — a stop, a restart refuses until the operator fixes the mark | [P/02.3] N3 «Manifest change», N4 |
| 2 | the store schema is above its own or not a number | [P/06.6] N3 «console start — schema check» |
| 2 | the manifest is not read or is refused | [P/02.3] N3 «Process start» |
| 2 | `CONSOLE_ROOT` is empty or not from the catalogue | [P/06.5] N1.1 `root`, N4 |
| 2 | `TIMEZONE` is empty or out of form | [P/06.5] N4; [the environment file contract](../common/contracts/env-file.md) |
| 2 | the environment file is not by the grammar; `SERVER_NAME` is not by the grammar; `W2C_ROLE` is not the role of the command | [P/02.4] N1.2, N4 |
| ≠ 0 | outside the loopback without a kit; another start refusal — a log line names the source | [P/02.4] N1.6, [P/02.3] N3 |

An unreadable family row during the resealing at start — a log line, the start is not interrupted ([P/06.2] N3
«reseal at start»).

## The cleanup window command

The deletion of bodies — by a separate command of the implementation with the flag `--writers-stopped` (the command name — [P/06.1] «Implementation decides»
item 9), not by the process `console`: the operator runs it in an exclusive window, when the writers are stopped. The codes —
[P/06.1] N2 «Sweep window command»:

| Code | When | Norm |
|---|---|---|
| 0 | the window is done, including when there is nothing to delete | [P/06.1] N2 «Sweep window command», N3 «body sweep» |
| 2 | no `--writers-stopped`; a failure to read the references or the list; a CAS conflict of the list — nothing is deleted | [P/06.1] N2 «Sweep window command» |
| 3 | a failure after the deletions began: a tombstone or a deletion outcome is not confirmed — do not open the writers and the copying | [P/06.1] N3 «body sweep» («completion») |

## Signals and readiness

- **Readiness** — the port `CONSOLE_PORT` ([Stand]); the callback listener is opened before it, if there is one.
- **SIGTERM** — an orderly exit. The claim `<sub>/idem/*` stays in the row, a client retry with the same key completes it
  ([P/06.1] N3 «create», N4); the requests stay in the rows, the reaper of the next process completes them ([P/06.4] N3 «reaper»); the leader gives up the queue of operations, another holder picks them up ([P/06.9] N3 «leader»).
- **Restart** — `Restart=always`, `RestartSec=2`, except the code 2 ([P/02.4] N1.1). The stand has the directive
  `@restart console` ([Stand]).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) N1.1 `dirs`).

- The command of the «Stand» with the substitution `{port}`; `{data}` is `PLATFORM_DIR`: the stand sets `PLATFORM_DIR={data}`,
  `CONSOLE_PORT={port}`, `PLATFORM_STORE` — the role socket, `SECRETS_KEY={data}/etc/secrets/platform.key` — the ring, which the runner creates
  by the «Stand» command `ring {file}` before the first process, `BOX_ID`,
  `SERVER_NAME` ([Stand] «One data directory»); `CONSOLE_CALL_PORT={cport}` — on the stand with the kit of [the second kind of pass](../common/acceptance/pass/README.md).
- `CONSOLE_ROOT` is named by the acceptance README of the chapter: chapter 6.2 — `testsub2`, the others — `testsub` ([Stand]).

## Open

- None. The stand ring — one path `{data}/etc/secrets/platform.key` (above, «Stand»); `BOX_ID` — by [P/02.4] N1.2;
  an instance with `:` in the name is representable by the name encoding ([the event journal contract](../common/contracts/event-journal.md)).

# The process `domain` — lifecycle (lesson P/08)

The lifecycle contract of the process (ADR-0083 addendum (2) item 1): how it is launched, what configures it, what it keeps on disk,
how it exits. The rows refer to the chapters of the lesson (`spec/08.K-domain.norms.md`), the lessons of the module, the contracts, the chapters of lesson P/09, chapter 6.7 and lesson P/10 (the moves of
lessons 8–10, stage B); the norms are not repeated here.

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

## Launch

- The unit `w2c-domain.service`, the role `domain`, the runner `w2c-run.sh domain`, `User=w2c`, the groups `w2c-store w2c-events
  w2c-secrets` — [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md) «Domain ports and units» (P/02.4-13).
- What the units share (`Restart`, `RestartPreventExitStatus=2`, the runner, `ProtectSystem`) — P/02.4 Н1.1 `common`.
- Only at the holder cluster. There can be several processes (the nodes of the cluster), one is active — the queue
  `domain/signer-turn` ([P/08.10 Н1.7](spec/08.10-domain.norms.md)).
- The process does not found the domain: the installation is done by an operator command, once per domain
  ([P/02.4 Н3 «domain installation»](../02-installer/spec/02.4-installer.norms.md), P/02.4-10); without the row
  `domain/signer` the process waits for it once every `VIEW_EVERY` and does not take the holder role ([P/08.2](spec/08.2-domain.norms.md) Н3
  «the process `domain` does not found the domain», «cold start»).

## Environment

The setting channel is only the environment of P/02.4 Н1.2 and the layout of `PLATFORM_DIR` (the second pilot, N-4).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `domain` | the unit | P/02.4 Н1.2 |
| `PLATFORM_DIR`, `PLATFORM_STORE`, `OBJECTS`, `RESOURCE_ROOT` / `EVENTS` | the state, the store door, the roots of objects and events | P/02.4 Н1.2 | P/02.4 Н1.2 «The setting channel and the layout» |
| `SECRETS_KEY` | the ring (credential): the holder keys, `book_seal` — envelopes of the ring | — | [P/08.2 Н1.3, Н1.4](spec/08.2-domain.norms.md); [P/06.2](../06-console/spec/06.2-console.norms.md) Н1.2 (`holders`); [the sealing contract](../common/contracts/sealing.md) |
| `SIGNER_HOST`, `SIGNER_PORT` | the door of the process: the reports of the agents, the login of people, the edits of the domain console; the unit does not write it — the default of the process `0.0.0.0` is not an explicit address: without a kit — a start refusal, code 2; the variable set outside the loopback without a kit — a start with a loud line ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.6 `process`; ADR-0075 addendum 2026-10-26 (5) item 4) | `0.0.0.0:8445` | P/02.4 Н1.6, Н1.12 |
| `SIGNER_URL` | the address of this door, which the term record writes as `domain/holder.url`; the clients of their own box (forwarding to the signer) check it by [the role certificate contract](../common/contracts/role-certificate.md) «The client of a door of its own cluster»: the host — a loopback literal — the name `SERVER_NAME`, `localhost` — a name, checked as a name: the outcome — the first refusal `peer` (ADR-0075 addendum 2026-10-26 (6) item 1); at a holder of several nodes — an address that reaches any node | `http://localhost:8445` (the stand of one machine; review analysis of stage A 8–10, № 33) | [P/08.8 Н1.1](spec/08.8-domain.norms.md) (the form of `url` — [the term record contract](../common/contracts/record.md)), [P/08.10 Н1.7](spec/08.10-domain.norms.md) `url` |
| `DOMAIN_CONSOLE_URL` | the address of the domain console door — the field `view.url`; with a kit — `https://` by a loopback literal or the name `SERVER_NAME` (hop 2 — a client of its own cluster, [the role certificate contract](../common/contracts/role-certificate.md) `own_client`: with a loopback literal `host` = `SERVER_NAME`; `localhost` — a name, checked as a name; an IP outside the loopback — `ip_address`) (the review of the norms of ADR-0075 by Kimi 80ee2b775, Н3) | — (none — `domain console not known` at the consoles) | [P/08.1](spec/08.1-domain.norms.md) Н1.4 `url`; the forwarding address — [the forwarding contract](../common/contracts/forwarding.md) (`view.url`) (review analysis of stage B 8–10, № 22: M-16) |
| `CLUSTER` | the name of the cluster of the installation — the name of the holder member | `local` | P/02.4 Н1.2 |
| `CLUSTERS` | the consoles of the member clusters `<name>=<url>[,…]`: the target of the planned handover, the retry of an edit of the deposed one, the neighbours of the emergency move | none or empty — an empty list | [the forwarding contract](../common/contracts/forwarding.md) (`CLUSTERS`; the form — at the owner it refers to) (review analysis of stage B 8–10, № 22: M-16); [P/08.8](spec/08.8-domain.norms.md) Н1.6 `apply`, Н1.7 `target`, Н1.8 step 5 (review analysis of stage A 8–10, № 32) |
| `BOX_ID`, `SERVER_NAME` | the box and the server; the instance `<box>:<pid>:<6 hex>` — the holder of the queue | P/02.4 Н1.2 | P/08.10 Н1.7 `turn` |

TLS: the kit of the role `domain` by `W2C_ROLE` (P/02.4 Н1.6 `roles`); the server side of the class `signed` — [P/08.0 Н1.6](spec/08.0-domain.norms.md)
and [the role certificate contract](../common/contracts/role-certificate.md).

## Flags

None: the setting channel is the environment only (P/02.4 Н1.2).

## Directories and files

- The rows and the objects of the holder — in the store and the objects store of its own cluster; the families and their writers — the data catalogue
  [`common/data/catalog.tsv`](../common/data/catalog.tsv) (the owners — chapters P/08.K, P/09, P/06.7 and lesson P/10).
- The ring `SECRETS_KEY` — by the layout `<PLATFORM_DIR>/etc/secrets/platform.key` (`/etc/w2c/secrets` — a link), outside the store
  directory, the objects root and the events root (P/02.4 Н1.1 `dirs`, Н1.2); on the stand — `{data}/etc/secrets/platform.key`.
  On reading, the process checks the placement of the ring ([the secret files contract](../common/contracts/secret-files.md) `forbidden`)
  against the roots it knows itself from the environment: the store directory with `PLATFORM_STORE=file://…`, the objects root
  (`OBJECTS`), the events root (`RESOURCE_ROOT` / `EVENTS`). With the store door through the daemon socket (`configstore://…`)
  the `-dir` of the daemon and the directories of its copies are not known to the process — the installation excludes them (the layout of P/02.4 Н1.1, `w2cctl secrets
  new` with the installer's list); there are no new variables (C08-RING-FORBIDDEN-ROOTS-01, the decision of the Domain Specification).
- The recovery file — at the operator: the installation creates it, mode 0600, outside the store directories (P/02.4 Н3
  «domain installation», step 3; the form — [P/08.2](spec/08.2-domain.norms.md) Н1.1); the process does not read it. It is needed by the installation, the planned change
  of the token key, the change of the book acceptance key and the change after a theft (P/08.2 Н1.1 `needed_for`; the move — `w2cctl domain move`,
  [P/08.8](spec/08.8-domain.norms.md) Н1.8; review analysis of stage A 8–10, № 33).
- The role journal — `<events root>/audit/domain/e1/…` ([the event journal contract](../common/contracts/event-journal.md) `journal`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 2 | a start refusal by the manifest, the rights, the schema — without a restart | P/02.4 Н1.1 `common` |
| ≠ 0 | another failure; the unit restarts | P/02.4 Н1.1 |

Without the row `domain/signer` the process does not exit but waits (P/08.2 Н3 «the process `domain` does not found the domain»).

## Signals and readiness

- The queue `domain/signer-turn`: capture and renewal — the algorithm `placement_turn` (TURN_TERM 45, TURN_RENEW 10); every
  write of a holder row — under the guard of the queue ([P/08.10](spec/08.10-domain.norms.md) Н1.7 `turn`, `guard`).
- `SIGTERM` — give up the queue (`holder ""` by CAS of its own version); `SIGKILL` — the queue is taken by TURN_TERM (P/08.10 Н1.7
  `release`).
- Without the queue — a standby: there is no pass, every door answers `503 standby` before reading the body (P/08.10 Н1.7 `standby`).
- The pass of the holder — once every `VIEW_EVERY` (3 s; [P/08.1 Н3](spec/08.1-domain.norms.md)).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

The stand of several clusters — the section «Domain stand» of [the common acceptance README](../common/acceptance/README.md): `@install domain` — the installation
with `{domain}` and `{recovery}`; `@start domain` — the processes `domain` and of the domain console on `hold`; `@start domain on
<cluster>` — without the installation; `@start domain second` — a second copy with the same `{data}`; `@move` — the move. The door `signer` —
through the runner's proxy (`DOMAIN_URL` of the agents). `{data}` — `PLATFORM_DIR` of the cluster ([the common acceptance README](../common/acceptance/README.md) «Stand»; review analysis of stage B 3–5, № 33).

## Open

- The reader side of the manifest, the schema check at start and the readiness by port — [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md) (decided by the Architect 2026-10-18 (the second pilot)).
- The name of the domain installation command and `first-admin` — the implementation decides: [P/02.4](../02-installer/spec/02.4-installer.norms.md)
  «Implementation decides» item 8 (the installation command), [P/08.2](spec/08.2-domain.norms.md) «Implementation decides» item 2 (the call of the changes),
  [P/08.4](spec/08.4-domain.norms.md) «Implementation decides» item 1 (`domain first-admin`).

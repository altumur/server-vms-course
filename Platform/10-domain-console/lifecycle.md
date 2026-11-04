# The domain console — lifecycle (lesson P/10)

The lifecycle contract of the domain console process `domainconsole` (ADR-0083 addendum (2) item 1): launch, setting, disk, exit. The norms —
[P/10](spec/10-domain-console.norms.md) (stage B).

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

## Launch

- The unit `w2c-domainconsole.service`, the role `domainconsole`, the runner `w2c-run.sh domainconsole`, `W2C_ROLE=domainconsole`,
  `User=w2c`, the groups `w2c-store w2c-events` (review analysis of stage A 8–10, № 33); there is no ring and no group `w2c-secrets` —
  [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md); what the units share — P/02.4 Н1.1 `common`
  ([P/02.4](../02-installer/spec/02.4-installer.norms.md)).
- At the holder cluster, next to the process `domain`. The console writes no holder rows: it passes the edits to the process
  `domain` ([P/10 Н1.3](spec/10-domain-console.norms.md) — the passing; the reception —
  [P/08.0 Н1.8](../08-domain/spec/08.0-domain.norms.md)); it does not need the queue `domain/signer-turn`
  ([P/08.10 Н1.7](../08-domain/spec/08.10-domain.norms.md) `guard`).
- At start — the reader side of the manifest row and the schema check, the readiness — the port ([P/10 Н1.1](spec/10-domain-console.norms.md),
  P/10-15; the text — P/02.4 Н1.12).

## Environment

The setting channel is only the environment of P/02.4 Н1.2 and the layout of `PLATFORM_DIR` (the second pilot, Н-4).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `domainconsole` | the unit | P/02.4 Н1.2 |
| `PLATFORM_DIR`, `PLATFORM_STORE`, `OBJECTS`, `RESOURCE_ROOT` / `EVENTS` | the state, the store door, the roots of objects and events (the role journal is written) | P/02.4 Н1.2 | P/02.4 Н1.2 «The setting channel and the layout» |
| `DOMAIN_CONSOLE_HOST`, `DOMAIN_CONSOLE_PORT` | the door of the domain operator; the consoles of the members forward here; TLS — by the kit of the role (P/02.4 Н1.6, [the role certificate contract](../common/contracts/role-certificate.md) `kit`; ADR-0075 addendum 2026-10-26 (2) item 4) | `0.0.0.0:8444` — the default of the process (the unit does not write it), not an explicit address: only with the kit, without the kit — a start refusal, code 2 (P/02.4 Н1.6 `process`; ADR-0075 addendum 2026-10-26 (3) item 5, (4) item 4; review of the norms of ADR-0075, Claude fd85ea8cc, С-3) | [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md) |
| `SIGNER_URL` | the door of the process `domain` of its own box — the passing of edits; the server check — [the role certificate contract](../common/contracts/role-certificate.md) «The client of a door of its own cluster» (the host is a loopback literal — the name `SERVER_NAME`; `localhost` — a name) | `http://localhost:8445` (the stand of one machine, as [the lifecycle of P/08](../08-domain/lifecycle.md); review analysis of stage A 8–10, № 33) | [P/10 Н1.3](spec/10-domain-console.norms.md) (the passing; the reception — P/08.0 Н1.8); [P/08.2 Н1.3](../08-domain/spec/08.2-domain.norms.md) |
| `LOGIN_URL` | the login of people, the value `login_url` in `/session` | `/api/login` | [the gate-and-pass contract](../common/contracts/gate-and-pass.md) `session` `login_url`; [P/08.4 Н1.2](../08-domain/spec/08.4-domain.norms.md); P/02.4 Н1.2 |
| `TIMEZONE` | the time zone: the value `timezone` in `/session`; from `w2c.env` of its own box; empty or out of form — code 2 | `UTC` | [the environment file contract](../common/contracts/env-file.md); [P/10 Н1.7](spec/10-domain-console.norms.md) `session` |
| `W2C_TLS_DIR` | the kit of the role `domainconsole` and its own `ca.pem`, `ca.next.pem` — the union of the centres of the role door | P/02.4 Н1.6 | [P/10 Н1.4](spec/10-domain-console.norms.md) `roles`, `server.role`; [the role certificate contract](../common/contracts/role-certificate.md) `kit` |
| `CLUSTER`, `BOX_ID`, `SERVER_NAME` | the cluster, the box, the server | P/02.4 Н1.2 | P/02.4 Н1.2 |

## Flags

None: the setting channel is only the environment (P/02.4 Н1.2).

## Directories and files

- It reads the holder rows (`domain/*` except `!domain/signer*` and `!domain/idem/*`, P/02.5 Н1.4); it writes no rows of its own; the reads — the paragraph
  «Данные» of [P/10 Н1](spec/10-domain-console.norms.md) and the data catalogue [`common/data/catalog.tsv`](../common/data/catalog.tsv),
  the reader `domainconsole`.
- There is no ring ([P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md)).
- The holder page is the same page of the console module, `sections: [domain]` ([P/10 Н1.7](spec/10-domain-console.norms.md));
  the module is shipped with the console binary, not from `$CAMMETA_SPECS` ([P/06.5](../06-console/spec/06.5-console.norms.md) Н1.1 `module`).
- The role journal — `<корень событий>/audit/domainconsole/e1/…`, the alarm `session.debug_open` — `audit.alarms/domainconsole`
  ([the event journal contract](../common/contracts/event-journal.md) `journal`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 2 | a start refusal by the manifest, the rights, the schema — without a restart | P/02.4 Н1.1 `common`; P/10 Н1.1 |
| 2 | `TIMEZONE` is empty or out of form | [the environment file contract](../common/contracts/env-file.md); [P/10 Н1.7](spec/10-domain-console.norms.md) `session` |
| ≠ 0 | another failure; the unit restarts | P/02.4 Н1.1 |

## Signals and readiness

- The process `domain` of its own box is standby or unreachable — the edits get its answer (`503 standby`) as it is
  ([P/08.10 Н1.7](../08-domain/spec/08.10-domain.norms.md) `standby`; [P/08.0 Н1.8](../08-domain/spec/08.0-domain.norms.md) `answers`);
  a break and silence — 502 ([P/10 Н1.3](spec/10-domain-console.norms.md) `pass`).
- The readiness is the port, there is no `sd_notify` ([P/10 Н1.1](spec/10-domain-console.norms.md)); the restart — by the unit (P/02.4 Н1.1 `common`).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

The stand of several clusters ([the common acceptance README](../common/acceptance/README.md#стенд-домена), the section «Domain stand»): `@start domain` brings up the processes `domain` and of the domain console on
`hold`; the door `holder <запрос>` — the domain console on `hold`, `holder@<кластер>` — on another cluster after the move;
`Idempotency-Key` at `POST`, `PUT`, `DELETE` — by the rule `@key`. `{data}` — `PLATFORM_DIR` of the cluster ([the common
acceptance README](../common/acceptance/README.md) «Stand»; review analysis of stage B 3–5, № 33).

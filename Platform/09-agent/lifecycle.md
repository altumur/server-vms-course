# The agent — lifecycle (lesson P/09)

The lifecycle contract of the agent process `domainagent` (ADR-0083 addendum (2) item 1): launch, setting, disk, exit. Three modes of one
process: the agent of a member (chapter 9.1), the relay mode `RELAY=1` (chapter 9.2) and the agent in the platform process of a cluster of
one. The norms — chapters [9.1](spec/09.1-agent.norms.md) and [9.2](spec/09.2-agent.norms.md) (stage B).

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

## Launch

- The unit `w2c-domainagent.service`, the role `domainagent`, the runner `w2c-run.sh domainagent`, `User=w2c`, the groups `w2c-store
  w2c-events w2c-secrets`; the agent of a member has no port of its own —
  [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md); what the units share — P/02.4 Н1.1 `common`
  ([P/02.4](../02-installer/spec/02.4-installer.norms.md)).
- On every member, the holder included: the holder is a member too
  ([P/09.1 Н1.1](spec/09.1-agent.norms.md) `agent`).
- A member pins the domain root by the operator command `join` ([P/09.1 Н1.1](spec/09.1-agent.norms.md) `join`); the order
  of the acceptance sides is any ([P/08.3 Н1.1](../08-domain/spec/08.3-domain.norms.md)).
- **The relay mode** — the same process, role and member key: `RELAY=1` opens the relay door
  ([P/09.2 Н1.1](spec/09.2-agent.norms.md) `door`); the memory is in the process, empty after a restart (P/09.2 Н1.4,
  «Implementation decides» item 1).
- **The agent in the process** — a cluster of one MAY hold the agent in the platform process without the kit of the role `domainagent`;
  the local token door is then a call, not a door ([P/09.1 Н1.11](spec/09.1-agent.norms.md); [the local token
  door contract](../common/contracts/local-token-door.md) «The call in the process»).

## Environment

The setting channel is only the environment of [P/02.4 Н1.2](../02-installer/spec/02.4-installer.norms.md) and the layout of `PLATFORM_DIR`
(the second pilot, N-4).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `domainagent` | the unit | P/02.4 Н1.2 |
| `PLATFORM_DIR`, `PLATFORM_STORE`, `OBJECTS`, `RESOURCE_ROOT` / `EVENTS` | the state, the store door, the roots of objects and events | P/02.4 Н1.2 | P/02.4 Н1.2 «The setting channel and the layout» |
| `SECRETS_KEY` | the ring (credential): the member key, the books and the emergency rows — envelopes of the ring | — | P/02.4 Н1.12; [P/09.1](spec/09.1-agent.norms.md) Н1 «Данные» (what the agent seals with the ring: `seed_secret` of the member key — Н1.1, the member books and the copy of the emergency row — Н1.4); the bytes of the envelope — [the sealing contract](../common/contracts/sealing.md) |
| `CLUSTER` | the name of its own member | `local` | P/02.4 Н1.2; [P/09.1 Н1.1](spec/09.1-agent.norms.md) |
| `CLUSTERS` | the consoles of the member clusters `<имя>=<url>[,…]`: «follow» — `GET /api/held` of each | none or empty — an empty list | the form `<имя>=<url>[,…]` — here, the row of the environment contract — [P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.2 (the reference to the norm P/06.7 is removed: review analysis of stage B 8–10, № 22, Claude M-16, Kimi SB810-08); [P/09.1 Н3](spec/09.1-agent.norms.md) «follow» step 1 (review analysis of stage A 8–10, № 32) |
| `REACHES` | the networks of the member — words of `domain/reaches` separated by commas; empty — as if not set | not set — the networks of the interfaces | [P/09.1 Н1.7](spec/09.1-agent.norms.md) `networks` (review analysis of stage A 8–10, № 32) |
| `DOMAIN_URL` | the door of the holder process `domain` — the road of the report | — | [P/09.1](spec/09.1-agent.norms.md) Н3 «the agent pass», Н1.7; [P/08.3 Н1.3а](../08-domain/spec/08.3-domain.norms.md) |
| `RELAY_URL` | the relay door — the road instead of `DOMAIN_URL` at a member behind a relay; a list of the addresses of the servers of the relay cluster separated by commas, in order: a connection refusal or `503 standby` — the next one (DOM-AGENT-TURN-01, the owner's consent 2026-10-26) | — | [P/09.2 Н1.1](spec/09.2-agent.norms.md) `door`; the member side — [P/09.1](spec/09.1-agent.norms.md) Н1.7, Н3 «the member's agent behind a relay» |
| `DOMAIN_CA`, `RELAY_CA` | the fingerprint of the centre of the holder / of the relay at the first contact, while the member record does not name `ca` | — | [the `peer` contract](../common/contracts/peer.md) «Client and first contact» `first`; [P/09.1 Н1.7](spec/09.1-agent.norms.md) |
| `RELAY_MEMBER` | the name of the relay member for the server check over `https://`; `RELAY_URL` on `https://` without it — the agent does not start | — | [the `peer` contract](../common/contracts/peer.md) `client`, `first`; [P/09.1 Н1.7](spec/09.1-agent.norms.md) |
| `CONSOLE_HOST`, `CONSOLE_PORT` | the address of its own console — the edit (P/09.1 Н1.5) and the alarms (Н1.10): the URL — `own_url`, the server check — `own_client` of [the role certificate contract](../common/contracts/role-certificate.md) (ADR-0075 addendum 2026-10-26 (4) item 3, (5) items 1–2) | `127.0.0.1`, `8080` | `w2c.env`, [P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.7 `w2c_env` |
| `RELAY`, `RELAY_HOST`, `RELAY_PORT` | the relay mode: the door for the members behind it (`RELAY` — `1`, none or empty — without the door, anything else — code 2); the unit does not write `RELAY_HOST`, `RELAY_PORT` — the default of the process `0.0.0.0` is not an explicit address: without a kit — a start refusal, code 2 (P/02.4 Н1.6 `process`; ADR-0075 addendum 2026-10-26 (5) item 4) | `RELAY` not set; `0.0.0.0`; `8446` | [P/09.2 Н1.1](spec/09.2-agent.norms.md) `door`; [P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.2 (the row `RELAY`), Н1.12 |
| `AGENT_TOKEN_DIR` | the directory of the sockets of the local token door `<роль>.sock` | `/run/w2c/domainagent` | [the local token door contract](../common/contracts/local-token-door.md) «The role socket» (review analysis of stage A 8–10, № 1 / decision 1); [P/09.1 Н1.6](spec/09.1-agent.norms.md); [the env file contract](../common/contracts/env-file.md) «Environment variables» (a table row) |
| `W2C_WALL_OFFSET` | the stand only: the shift of the wall clock of the agent; when set — a loud journal line | not set | [P/09.1](spec/09.1-agent.norms.md) «Implementation decides» item 3; [the env file contract](../common/contracts/env-file.md) «Environment variables» (a table row, «только стенд», like `W2C_SHRINK_AFTER`) |
| `BOX_ID`, `SERVER_NAME` | the box and the server | P/02.4 Н1.2 | P/02.4 Н1.2 |

TLS: the kit of the role `domainagent` by `W2C_ROLE`; the client of the doors of the holder and of the relay — [P/09.1 Н1.7](spec/09.1-agent.norms.md)
(the expected role of the server: the holder — `domain`, the relay — `domainagent` — [the role certificate
contract](../common/contracts/role-certificate.md) `peer_role`; review analysis of stage B 8–10, № 4); the relay door — the same kit `domainagent`, the server side of the class
`signed` ([P/09.2 Н1.6](spec/09.2-agent.norms.md); [the role certificate
contract](../common/contracts/role-certificate.md#the-server-side-the-class-signed); the kit — [P/02.4 Н1.6](../02-installer/spec/02.4-installer.norms.md)).
The agent in the process — without a kit, the client only `https://` with the check `peer` ([P/09.1 Н1.11](spec/09.1-agent.norms.md) `client`).

## Flags

None: the setting channel is the environment only (P/02.4 Н1.2).

## Directories and files

- The rows and the objects of the agent at its own cluster — the copies, the outcomes, the row `domain/agent` etc.; `domain/reached` and
  `domain/reaches` are objects (P/05 Н1.1), not store rows ([P/09.1 Н1.7](spec/09.1-agent.norms.md)); the families and
  the participants — the data catalogue [`common/data/catalog.tsv`](../common/data/catalog.tsv) (the owner — P/09.1, the participant
  `domainagent` in the rows of P/08.2, P/08.4, P/08.8, P/08.9).
- The ring `SECRETS_KEY` — by the layout `<PLATFORM_DIR>/etc/secrets/platform.key` (`/etc/w2c/secrets` — a link), outside the store
  directory, the objects root and the events root (P/02.4 Н1.1 `dirs`, Н1.2); on the stand — `{data}/etc/secrets/platform.key`.
  On reading, the process checks the placement of the ring ([the secret files contract](../common/contracts/secret-files.md) `forbidden`)
  against the roots it knows itself from the environment: the store directory with `PLATFORM_STORE=file://…`, the objects root
  (`OBJECTS`), the events root (`RESOURCE_ROOT` / `EVENTS`). With the store door through the daemon socket (`configstore://…`)
  the `-dir` of the daemon and the directories of its copies are not known to the process — the installation excludes them (the layout of P/02.4 Н1.1, `w2cctl secrets
  new` with the installer's list); there are no new variables (C08-RING-FORBIDDEN-ROOTS-01, the decision of the Domain Specification).
- The relay memory (the copies and the `rev` of the members, the answers of the holder, the knocks) — in the process memory, not in the store
  ([P/09.2 Н1.4](spec/09.2-agent.norms.md); where it is held — «Implementation decides» item 1 of chapter 9.2).
- The local token door — Unix sockets `<AGENT_TOKEN_DIR>/<роль>.sock`, one per worker role of the catalogue; the sockets —
  from the units `w2c-domainagent-token-<роль>.socket`, one not passed by a unit the agent creates itself ([the local token
  door contract](../common/contracts/local-token-door.md) «The role socket»; review analysis of stage A 8–10, № 1 / decision 1); the tokens —
  only in the memory of the asker.
- The role journal — `<корень событий>/audit/domainagent/e1/…` ([the event journal contract](../common/contracts/event-journal.md) `journal`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 2 | a start refusal by the manifest, the rights, the schema — without a restart | P/02.4 Н1.1 `common` |
| 2 | `RELAY` is not empty and not `1` — the agent does not start: a setting refusal (the Architect's decision, review analysis of stage B 8–10, № 17, ADR-0083 addendum (15)) | [P/09.2](spec/09.2-agent.norms.md) Н1.1 `door`; [P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.2 (the row `RELAY`) |
| 2 | `RELAY_URL` on `https://` without `RELAY_MEMBER` — the agent does not start: a setting refusal ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `common`; the Architect's decision on the move plans 8–10, ADR-0083 addendum (14) item 10; plan 9 V8) | [the `peer` contract](../common/contracts/peer.md) `first`; [P/09.1 Н1.7](spec/09.1-agent.norms.md) |
| 2 | neither `DOMAIN_URL` nor `RELAY_URL` (not set or empty) — there is no road, the agent does not start: a setting refusal, nothing is written before the queue and the birth of the key (C09-NO-ROAD-01) | [P/09.1](spec/09.1-agent.norms.md) Н1.7 |

## Signals and readiness

- The pass — once every `every`, the default `REPORT_EVERY` 5 s; the answer of the holder can set `every` 1…3600
  ([P/08.3](../08-domain/spec/08.3-domain.norms.md) Н1.3, Н1.5; [P/09.1](spec/09.1-agent.norms.md) Н3 «the agent pass»).
- `503 standby` of the holder — «держатель недоступен» for this pass, not a reason to look for another term; a retry by the next
  pass ([P/09.1 Н1.12](spec/09.1-agent.norms.md) `agent`).
- Following the holder — before the report in every pass ([P/09.1](spec/09.1-agent.norms.md) Н3 «follow»).
- In the relay mode the relay pass — in every pass of the agent, after its own report, and even if its own report did not
  pass ([P/09.2 Н3](spec/09.2-agent.norms.md)).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

The stand of several clusters ([the common acceptance README](../common/acceptance/README.md#domain-stand), the section «Domain stand»): `@start agent <кластер>` — `CLUSTER`, `DOMAIN_URL` —
the runner's proxy; `@start agent <кластер> via <ретранслятор>` — `RELAY_URL` instead of `DOMAIN_URL`; `@join <кластер>
[<файл>]` — the command `join` with the recovery file; `@clock` — `W2C_WALL_OFFSET`. `{data}` — `PLATFORM_DIR` of the cluster
([the common acceptance README](../common/acceptance/README.md) «Stand»; review analysis of stage B 3–5, № 33). The fourth cluster
`relay` with `RELAY=1` and `{relay_port}` — the acceptance of [chapter 9.2](acceptance/2/README.md).

## Implementation decides

- The name and the arguments of the command `join` and the launch of the agent — [P/09.1](spec/09.1-agent.norms.md) «Implementation decides» item 2.
- The reader side of the manifest, the schema check at start and the readiness by port — [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md) (decided by the Architect 2026-10-18 (the second pilot)).

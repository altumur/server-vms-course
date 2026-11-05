# Resource — lifecycle (lesson P/05)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the process `resource` (ADR-0083 addendum (2) item 1). The rows refer to the norms of the lesson and do not
retell them (stage B: the references to М10/8, М10/10, М10/11 are retargeted to P/05 and the common contracts).

[P/02.3]: ../02-installer/spec/02.3-installer.norms.md
[P/02.4]: ../02-installer/spec/02.4-installer.norms.md
[P/02.5]: ../02-installer/spec/02.5-installer.norms.md
[P/05]: spec/05-resource.norms.md
[event journal]: ../common/contracts/event-journal.md
[presence lock]: ../common/contracts/presence-lock.md
[Stand]: ../common/acceptance/README.md
[catalogue]: ../common/data/catalog.tsv

## Launch

- **Unit** — `w2c-resource.service`, one process per server, without a controller; `User=w2c`,
  `SupplementaryGroups=w2c-store w2c-events` ([P/02.4] Н1.1, [P/05] Н1.4).
- **Launch** — through the runner `w2c-run.sh resource` with `W2C_ROLE=resource` ([P/02.4] Н1.1 — the unit sets it, review of stage B 3–5, № 29; Н1.9).
- **Start order** — the schema check of `platform/schema` and the read of the manifest row before the first write ([P/05] Н3 «resource start
  — schema check», [P/02.3] Н3 «Process start»); then the heartbeat at once, the heartbeat stream, `restore` of the buckets in its own attempt,
  the door row `platform/doors/<сервер>` ([P/02.4] Н3 «server start», step 2).

## Environment

The environment is assembled by the runner `w2c-run.sh` in the order of P/02.4 Н1.2: the unit values → `roles/<W2C_ROLE>.env` → `w2c.env` →
the subsystem file, what is read earlier wins; the files — by parsing, not by `source` ([the environment file contract](../common/contracts/env-file.md); [02-installer/lifecycle.md](../02-installer/lifecycle.md)).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `W2C_ROLE` | the role `resource`; not the role of the runner command — code 2 | set by the unit | [P/02.4] Н1.2 |
| `PLATFORM_STORE` | the store door — the role socket `configstore:///run/configstore/resource.sock` | `file://<PLATFORM_DIR>/config` (the profile of a box of one implementation) | [P/02.4] Н1.2 |
| `PLATFORM_DIR` | the state root | `/data/platform` | [P/02.4] Н1.2 |
| `RESOURCE_ROOT` / `EVENTS` | the root of the event trees; the presence locks `.workers/` are in it too | `<PLATFORM_DIR>/events` | [P/02.4] Н1.2 «The setting channel», [event journal], [presence lock] |
| `OBJECTS` / `PLATFORM_OBJECTS` | the root of the objects of the objects door and of the body copies | `<PLATFORM_DIR>/objects` | [P/02.4] Н1.2, [P/05] Н1.1 |
| `RESOURCE_HOST`, `RESOURCE_PORT` | the address of the resource door; the unit does not write it — the process default; set in `w2c.env` — the bind address (off the loopback — only with a kit, ADR-0075 addendum of 2026-10-26 (6) item 2); with `mtls` the chain — the leaf, then its center ([the role certificate contract](../common/contracts/role-certificate.md) `server`; review of the norms of ADR-0075, Claude fd85ea8cc, S-2, S-3) | `127.0.0.1`, `8090` | [P/02.4] Н1.1, Н1.2, Н1.6 |
| `RESOURCE_URL` | the door address that the resource writes into the door row; an IP literal off the loopback (the loopback threshold of [the role certificate contract](../common/contracts/role-certificate.md) `loopback`: `ip`) — the resource writes a journal line at start; with `https://` the clients refuse `ip_address`, with `http://` — a configuration error visible as a connection refusal (ADR-0075 addendum of 2026-10-26 (4) item 6) | — | [P/02.4] Н1.2, [P/05] Н1.4 `door_row` |
| `RESOURCE_TLS` | the door over TLS | — | [P/02.4] Н1.2, Н1.6 |
| `SERVER_NAME` | its own server: the key of the heartbeat and of the door row; not by the grammar — code 2 | the short hostname | [P/02.4] Н1.2 |
| `BOX_ID` | the box | `/etc/machine-id`, otherwise the hostname | [P/02.4] Н1.2 |
| `BUILD` | the build word in the heartbeat | `dev` | [P/02.4] Н1.2 |
| `W2C_TLS_DIR` | the root of the kits; its own — `<W2C_TLS_DIR>/resource` | `/etc/w2c/tls` | [P/02.4] Н1.2, Н1.6 |
| `W2C_ENV` | the file of the common settings | `/etc/w2c/w2c.env` | [P/02.4] Н1.2 |

## Flags

None: the setting channel is the environment only ([P/02.4] Н1.2 «The setting channel and the layout of `PLATFORM_DIR`»).

## Directories and files

- **The events root** — the buckets of all the trees of the server `<корень событий>/<дерево>/<unit>/e<эпоха>/<start>Z.events.jsonl`;
  the resource is the owner of the file contract of the event journal, the workers and the console write into it ([event journal], [P/05] Н1.2, [catalogue]).
  The copies of the buckets of the neighbours — `<корень событий>/.mirror/<server>/…`, only the resource writes them.
- **Presence locks** — `<корень событий>/.workers/<sub>/<экземпляр>.lock`: the resource takes `flock` without waiting and derives
  `runs`, `gone`, `unknown`; a `gone` file it MAY remove under its own `flock` ([presence lock] `presence_lock`, [catalogue]).
- **The objects root** — the objects door, the body copies `<sub>/blobs/sha256-<hex>` from the neighbours of the ring, the tombstones `.gone/<ключ>`, the directory locks `<каталог>/~lock`
  ([P/05] Н1.1, Н1.1 «Tombstones»; ADR-0083 addendum (16)). File names in both roots — one encoding `%XX` / `%h<sha256>` ([event journal]
  «File names in shared trees»; the threshold of `%h` — by the full file name with the suffix of the norm and the margin of the temporary name, review of stage B 3–5, № 20).
- **Store rows** — the heartbeat `platform/resources/<server>/heartbeat` (an object), the door row `platform/doors/<сервер>`,
  the release requests `<sub>/requests/free-<server>-<volume>`; it reads `platform/space`, `platform/mirror`,
  `<sub>/retention`, `<sub>/alarms_retention`, `platform/decommission/*`, `platform/schema`, `platform/manifest/<sub>` and the mark
  `/rev` ([catalogue], [P/02.5] Н1.4).
- **Its own journal** — `<корень событий>/audit/resource/e1/…` under an exclusive file lock ([event journal]
  `journal`, `writer`).

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | a manifest change — stop, the supervisor starts it again | [P/02.3] Н3 «Manifest change» |
| 2 | the manifest mark is out of form at a running process — a stop, a restart refuses until the operator fixes the mark (review of stage A 6–7, B2) | [P/02.3] Н3 «Manifest change», Н4 |
| 2 | the store schema is above its own or not a number | [P/05] Н3 «resource start — schema check» |
| 2 | the manifest row is not readable or is refused | [P/02.3] Н3 «Process start» |
| 2 | the environment file is not by the grammar; `SERVER_NAME` is not by the grammar; `W2C_ROLE` is not the role of the command | [P/02.4] Н1.2, Н4 |
| ≠ 0 | another start refusal — a log line names the source | [P/02.3] Н3 «Process start» |

Off the loopback the resource listens only with a kit (`door.mode` `mtls`): without a kit — only the loopback, an address off the loopback is a
start refusal, code 2 ([P/02.4] Н1.6 `process`; ADR-0075 addendum of 2026-10-26 (6) item 2 — the resource is removed from the exception of the signer and the relay).

## Signals and readiness

- **Readiness** — the port `RESOURCE_PORT` and the row `platform/doors/<сервер>`; the stand runner waits for both ([Stand], [P/05]
  Н1.4).
- **Heartbeat** — every 10 s; the door row — every 15 s; the pass — every 600 s, a step longer than `PULSE_LIMIT` gives
  `pass_stalled` ([P/05] Н1.4, «Implementation decides» item 7 — the value of `PULSE_LIMIT`).
- **SIGTERM/SIGKILL** — the state is in the rows and files; after the server returns, the resource pulls its closed buckets from the neighbours
  (`restore`, [P/05] Н1.4 «Bucket restore»).
- **Restart** — `Restart=always`, `RestartSec=2`, except the code 2 ([P/02.4] Н1.1).

## Stand

The roots `{data}/config`, `objects`, `events` are created before the process start by the role start command of the profile — [the common
acceptance README](../common/acceptance/README.md) «Stand without root»; the process does not create the roots ([P/02.4](../02-installer/spec/02.4-installer.norms.md) Н1.1 `dirs`; STAND-ROOTS-CLEAR-01, the Architect's decision 2026-10-27).

- The command of the «Стенд» with the substitutions `{rport}` — the door port, `{server}` — the server name (`srv-a`; at the stand of М11 —
  `srv-<кластер>`) ([Stand] «Ресурс»).
- `{data}` is `PLATFORM_DIR`: the stand sets `PLATFORM_DIR={data}`, `RESOURCE_PORT={rport}`, `SERVER_NAME`, `BOX_ID`;
  the events root is `{data}/events`, there is no separate key ([Stand] «Один каталог данных»).

## Open

- The events root at a stand of several servers on one `{data}` — no stand is arranged so: each server has its own
  `{data}`.
- The value of `PULSE_LIMIT` — the implementation decides ([P/05] «Implementation decides» item 7).

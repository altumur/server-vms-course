# Store — lifecycle (lesson P/01)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the store process `configstore` (ADR-0083 addendum (2) item 1): start, configuration, files on disk, exit codes,
signals. Stage A — on top of the current norms of М10. The norms are not retold here: each line leads to its norm.

Norms: [P/02.4](../02-installer/spec/02.4-installer.norms.md) (Н1.1 units, Н1.2 environment,
Н3 «server start»), [P/01.3](spec/01.3-store.norms.md) (Н1.3 daemon, Н4), [P/04](../04-controller/spec/04-controller.norms.md) (Н1.4а server refusal), [P/01.1](spec/01.1-store.norms.md) (door,
durability barriers), [P/01.2](spec/01.2-store.norms.md) (rights file, role sockets).

## Start

| What | How | Norm |
|---|---|---|
| the group daemon | the unit `configstore.service`: `User=configstore`, `UMask=0077`, `-dir /data/platform/configstore`, `-sockets /run/configstore`, `-rights`, `-tls`, `-group-size`; the runner `w2c-run.sh configstore` | P/02.4 Н1.1 `units` |
| sockets | the units `configstore-admin.socket` and `configstore-<роль>.socket`, `FileDescriptorName=admin \| <роль>`, `Service=configstore.service` | P/02.4 Н1.1, P/01.3 Н1.3 `sockets` |
| first start and restart | `member.json` exists — a restart, otherwise `-bootstrap` (the first server) or `-join` (the others) | P/02.4 Н3 «server start» step 1, P/01.3 Н1.3 `group.join` |
| the box store | a build without raft, one voter (`box`) | P/01.3 Н1.3 `box` |
| the in-process store | the profile `file://` «the whole box is one implementation», without a door; the on-disk format is not a contract | P/02.4 Н1.2 `PLATFORM_STORE`, P/01.1 Н2 |

## Environment

The daemon's configuration is set by flags (below): the file `configstore.env` is read by the runner, which builds the flags from it. The daemon itself reads
only the systemd environment — the passed sockets (`LISTEN_FDS`, `LISTEN_FDNAMES`) and the watchdog (`NOTIFY_SOCKET`): a passed
socket cannot be replaced by a flag (P/01.3 Н1.3 `sockets`).
The order of the runner's environment files — the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` → `configstore.env`
(P/02.4 Н1.2; [02-installer/lifecycle.md](../02-installer/lifecycle.md)).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `CONFIGSTORE_ID`, `_RAFT`, `_API`, `_GROUP_SIZE`, `_JOIN`, `_FLAGS`, `_TUNING` | daemon flags from `configstore.env`; read by the runner | `configstore.env` sets `tuning` `lan`; the default of the flag `-tuning` itself is `default` | P/02.4 Н1.2, P/01.3 Н1.3 «Daemon flags» |
| `SERVER_NAME` | the default of `-id` outside a group | the short hostname | P/02.4 Н1.2, P/01.3 Н1.3 «Daemon flags» `-id` |
| `LISTEN_FDS`, `LISTEN_FDNAMES` | inherited sockets (`sd_listen_fds`); read by the daemon itself | — | P/01.3 Н1.3 `sockets` |
| `NOTIFY_SOCKET` | the systemd watchdog | — | P/02.4 Н1.2 |

## Flags

The closed table «Daemon flags» — [P/01.3 Н1.3](spec/01.3-store.norms.md), machine form [`forms/daemon-flags.tsv`](forms/daemon-flags.tsv):
`-dir` (required), `-id`, `-sockets`, `-rights`, `-tls`, `-raft`, `-raft-bind`, `-api`, `-bootstrap`, `-join`,
`-group-size`, `-force`, `-isolated`, `-upper`, `-peers` (the last three — only for `recover`), `-door`, `-voters`, `-tuning`, `-leader-wait`, `-max-value`, `-max-body`, `-max-conns`,
`-api-conns`, `-api-per-address`, `-index-base`, `-groups` (only for `rights`), `--from` (only for `restore`, `import`). A flag outside the table is a start refusal, code 2. The administrative commands —
`configstore status | join | leave | admit | backup | restore | import | recover | rights` (P/01.3 Н1.3 `admin_ops`,
Н1.9).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `<PLATFORM_DIR>/configstore` (`-dir`) | the daemon's data directory; the on-disk format — the implementation decides (P/01.1 «Implementation decides» item 3) | P/02.4 Н1.2 «The setting channel and the layout» |
| `<-dir>/FORMAT` | the format mark `{format, version, impl}`: written first into an empty directory; a foreign one or none in a non-empty directory — a refusal, code 2 | P/01.3 Н1.3 `format` |
| `<-dir>/member.json` | the partners and `how` after joining; a restart is not a join | P/01.3 Н1.3 `group.join` (the path inside `-dir` — the implementation decides) |
| `/run/configstore/admin.sock`, `/run/configstore/<роль>.sock` | flat; inherited from the `.socket` units: `admin.sock` 0600, a role socket 0660 with the role's group (`SocketGroup=`); a socket that was not passed the daemon creates itself in `-sockets`: `admin.sock` 0600, a role socket 0660 with the process's group | P/01.3 Н1.3 `sockets`, Н1.1 `dirs` |
| `/etc/w2c/configstore-rights.json` (`-rights`) | the rights file; without the file — only `admin.sock`; there is no live reload | P/01.2 Н1.2 |
| `/etc/w2c/tls` (`-tls`) | the root of the kits: inside — the kit of the role `configstore` or `configstore-door` | P/01.3 Н1.3 «Daemon flags» `-tls`, Н1.6 |
| the copy file (`backup <файл>`) | JSON Lines `copy`, 0600, tmp + rename, outside `-dir` | P/01.3 Н1.3 `copy`, `admin_ops`; the vector — `Platform/common/vectors/README.md` |
| the row `platform/configstore-doors/<id>` | written by a door without a vote every 30 s | [catalogue](../common/data/catalog.tsv) |
| the row `platform/epoch_floor` | raised only by `op: floor` on the leader's `admin.sock` (`restore`, `import`, `recover`) | P/01.3 Н1.3 `floor`, [catalogue](../common/data/catalog.tsv) |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | an orderly stop | — |
| 2 | a start refusal: `-bootstrap` with `-join`, a size not 1/3/5, an address outside the loopback without `-tls`, a door certificate at a voter; no `-dir`; no `-id` in a group; a flag outside the table; `-max-value` or `-max-body` not > 0; a foreign or missing mark `FORMAT`; an inherited socket with a foreign name; the box store with `-group-size 3`/`5` or `-join`; `recover` on a box | P/01.3 Н1.3 `refuse_start`, Н4 |
| ≠ 0 | an administrative command refused: `backup` into `-dir`, a repeated `import`, an input not by `copy`, the clock earlier than `generation_at` | P/01.3 Н4 |

## Signals and readiness

| What | How | Norm |
|---|---|---|
| SIGTERM | a stop; `TimeoutStopSec` 20–30 | P/02.4 Н1.1 |
| restart | `Restart=always`, `RestartSec=2`, `RestartPreventExitStatus=2` | P/02.4 Н1.1 `common` |
| readiness | the socket is open; `After=configstore.service` at the others is an order, not readiness: each process itself waits for a reliable read | P/02.4 Н3 «server start», «Races» |
| durability | the barriers are switched off neither by the environment nor by an operation flag | P/01.3 Н1.3 `durability`, P/01.1 «Implementation decides» item 3 |
| a majority failure | 503 `unavailable` after 5 s; recovery — `recover` by hand | P/04 Н1.4а `power_pull` `store`; P/01.3 Н3 «recover the store» |

## Stand

«Stand» — the [common acceptance README](../common/acceptance/README.md) (analysis of the review of stage B 3–5, № 33):
- the store command gets `{data}` (`PLATFORM_DIR`, the store — `{data}/configstore`), `{socket}` (`admin.sock`,
  the role sockets next to it), `{rights}`, `{body_limit}` → `-max-body`, `{row_ceiling}` → `-max-value`; it puts no manifests;
- `{rights}`: in P/01.1 — the file of the role `acc`, in the acceptances moved from М10/4–11 — the rights derived from the stand's manifests by the rights derivation command;
- the directives `@restart store`, `@foreign store`, `@backup store`, `@import store`, the door `restored`;
- a stand flag that switches off the barriers for speed is named by the implementation in its «Stand» command.

## Open

- The path of `member.json` inside `-dir` and the format of the data directory — the implementation decides (P/01.1 «Implementation decides» item 3); between
  implementations only the copy `copy` transfers.
- The daemon's readiness is the socket: it does not send `sd_notify`, `Type=notify` — only at the controller and the worker ([P/02.4 Н1.1](../02-installer/spec/02.4-installer.norms.md) `notify`; Decided by the Architect 2026-10-18 (the second pilot)).

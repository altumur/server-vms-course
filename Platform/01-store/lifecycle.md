# Store — lifecycle (lesson P/01)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the store process `configstore` (ADR-0083 addendum (2) item 1): start, configuration, files on disk, exit codes,
signals. Stage A — on top of the current norms of M10. The norms are not retold here: each line leads to its norm.

Norms: [P/02.4](../02-installer/spec/02.4-installer.norms.md) (N1.1 units, N1.2 environment,
N3 «server start»), [P/01.3](spec/01.3-store.norms.md) (N1.3 daemon, N4), [P/04](../04-controller/spec/04-controller.norms.md) (N1.4a server refusal), [P/01.1](spec/01.1-store.norms.md) (door,
durability barriers), [P/01.2](spec/01.2-store.norms.md) (rights file, role sockets).

## Start

| What | How | Norm |
|---|---|---|
| the group daemon | the unit `configstore.service`: `User=configstore`, `UMask=0077`, `-dir /data/platform/configstore`, `-sockets /run/configstore`, `-rights`, `-tls`, `-group-size`; the runner `w2c-run.sh configstore` | P/02.4 N1.1 `units` |
| sockets | the units `configstore-admin.socket` and `configstore-<role>.socket`, `FileDescriptorName=admin \| <role>`, `Service=configstore.service` | P/02.4 N1.1, P/01.3 N1.3 `sockets` |
| first start and restart | `member.json` exists — a restart, otherwise `-bootstrap` (the first server) or `-join` (the others) | P/02.4 N3 «server start» step 1, P/01.3 N1.3 `group.join` |
| the box store | a build without raft, one voter (`box`) | P/01.3 N1.3 `box` |
| the in-process store | the profile `file://` «the whole box is one implementation», without a door; the on-disk format is not a contract | P/02.4 N1.2 `PLATFORM_STORE`, P/01.1 N2 |

## Environment

The daemon's configuration is set by flags (below): the file `configstore.env` is read by the runner, which builds the flags from it. The daemon itself reads
SERVER_NAME for the non-group name fallback when -id is absent, and the systemd environment — the passed sockets (`LISTEN_FDS`, `LISTEN_FDNAMES`) and the watchdog (`NOTIFY_SOCKET`): a passed
socket cannot be replaced by a flag (P/01.3 N1.3 `sockets`).
The order of the runner's environment files — the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` → `configstore.env`
(P/02.4 N1.2; [02-installer/lifecycle.md](../02-installer/lifecycle.md)).

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `CONFIGSTORE_ID`, `_RAFT`, `_API`, `_GROUP_SIZE`, `_JOIN`, `_FLAGS`, `_TUNING` | daemon flags from `configstore.env`; read by the runner | launcher setting by P/02.4 N1.2; daemon defaults only in the flag form | P/02.4 N1.2, P/01.3 N1.3 «Daemon flags» |
| `SERVER_NAME` | input of the non-group `-id` fallback | launcher-owned value by P/02.4 N1.2; default semantics only in the flag form | P/02.4 N1.2, P/01.3 N1.3 «Daemon flags» `-id` |
| `LISTEN_FDS`, `LISTEN_FDNAMES` | inherited sockets (`sd_listen_fds`); read by the daemon itself | — | P/01.3 N1.3 `sockets` |
| `NOTIFY_SOCKET` | common systemd environment; this daemon does not send sd_notify (readiness below) | — | P/02.4 N1.2 |

The daemon itself reads `SERVER_NAME` only when `-id` is absent and the non-group name fallback of the [flag form](forms/daemon-flags.tsv) applies. The launcher sets the environment by P/02.4; the daemon does not infer a hostname on its own. An explicit `-id` does not require this fallback; neither source gives the existing `start_flags` refusal.

## Flags

Flag purposes and administrative commands are [P/01.3 N1.3](spec/01.3-store.norms.md). The single machine source for spelling, types, defaults, required/bad checks and command scopes is [forms/daemon-flags.tsv](forms/daemon-flags.tsv); this lifecycle adds no flag restrictions. Administrative command grammar is N1.3 `admin_ops`; startup refusal names and codes are [forms/refusals.tsv](forms/refusals.tsv).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `<PLATFORM_DIR>/configstore` (`-dir`) | the daemon's data directory; the on-disk format — the implementation decides (P/01.1 «Implementation decides» item 3) | P/02.4 N1.2 «The setting channel and the layout» |
| `<-dir>/FORMAT` | the format mark `{format, version, impl}`: written first into an empty directory; a foreign one or none in a non-empty directory — a refusal, code 2 | P/01.3 N1.3 `format` |
| `<-dir>/member.json` | the partners and `how` after joining; a restart is not a join | P/01.3 N1.3 `group.join` (the path inside `-dir` — the implementation decides) |
| `/run/configstore/admin.sock`, `/run/configstore/<role>.sock` | flat; inherited from the `.socket` units: `admin.sock` 0600, a role socket 0660 with the role's group (`SocketGroup=`); a socket that was not passed the daemon creates itself in `-sockets`: `admin.sock` 0600, a role socket 0660 with the process's group | P/01.3 N1.3 `sockets`; P/02.4 N1.1 |
| `/etc/w2c/configstore-rights.json` (`-rights`) | the rights file; without the file — only `admin.sock`; there is no live reload | P/01.2 N1.2 |
| `/etc/w2c/tls` (`-tls`) | the root of the kits: inside — the kit of the role `configstore` or `configstore-door` | P/01.3 N1.3 «Daemon flags» `-tls`, N1.6 |
| the copy file (`backup <file>`) | JSON Lines `copy`, 0600, tmp + rename, outside `-dir` | P/01.3 N1.3 `copy`, `admin_ops`; the vector — `Platform/common/vectors/README.md` |
| the row `platform/configstore-doors/<id>` | written by a door without a vote every DOOR_SEEN_EVERY (the P/01 constant form) | [catalogue](../common/data/catalog.tsv) |
| the row `platform/epoch_floor` | raised only by `op: floor` on the leader's `admin.sock` (`restore`, `import`, `recover`) | P/01.3 N1.3 `floor`, [catalogue](../common/data/catalog.tsv) |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | an orderly stop | — |
| by the start causes in `forms/refusals.tsv` | `start_config`, `start_flags`, `start_format`, `start_data_dir_owned`, `box_no_raft`; exact conditions and codes are owned by the form and P/01.3 N4 | [forms/refusals.tsv](forms/refusals.tsv), P/01.3 N4 |
| by the CLI causes in `forms/refusals.tsv` | administrative refusal names and caller actions — P/01.3 N4; no separate lifecycle refusal catalog | [forms/refusals.tsv](forms/refusals.tsv), P/01.3 N4 |

## Signals and readiness

| What | How | Norm |
|---|---|---|
| SIGTERM | stop admission, bound/cancel I/O, classify admitted work and release resources within the declared orderly-stop budget below the actual manager deadline; no automatic budget from an example | [P/01.3 Snapshot output and orderly stop](spec/01.3-store.norms.md#snapshot-output-and-orderly-stop); P/02.4 N1.1 |
| data-directory ownership | atomic for one process; after orderly exit or `SIGKILL` former ownership needs no manual cleanup and alone does not forbid start; `start_format` and, on a box, unfinished `import`/`restore` remain | P/01.3 N1.3 «Data-directory ownership»; `start_data_dir_owned`, `local_data_dir_owned` in the form |
| restart | `Restart=always`, `RestartSec=2`, `RestartPreventExitStatus=2` | P/02.4 N1.1 `common` |
| readiness | the socket is open; `After=configstore.service` at the others is an order, not readiness: each process itself waits for a reliable read | P/02.4 N3 «server start», «Races» |
| durability | the barriers are switched off neither by the environment nor by an operation flag | P/01.3 N1.3 `durability`, P/01.1 «Implementation decides» item 3 |
| a majority failure | 503 `unavailable` after the effective `-leader-wait` interval; recovery — `recover` by hand | P/04 N1.4a `power_pull` `store`; P/01.3 N3 «recover the store» |

## Stand

«Stand» — the [common acceptance README](../common/acceptance/README.md) (analysis of the review of stage B 3–5, № 33):
- the store command gets `{data}` (`PLATFORM_DIR`, the store — `{data}/configstore`), `{socket}` (`admin.sock`,
  the role sockets next to it), `{rights}`, `{body_limit}` → `-max-body`, `{row_ceiling}` → `-max-value`; it puts no manifests;
- `{rights}`: in P/01.1 — the file of the role `acc`, in the acceptances moved from M10/4–11 — the rights derived from the stand's manifests by the rights derivation command;
- the directives `@restart store`, `@foreign store`, `@backup store`, `@import store`, the door `restored`;
- a stand flag that switches off the barriers for speed is named by the implementation in its «Stand» command.

## Open

- The path of `member.json` inside `-dir` and the format of the data directory — the implementation decides (P/01.1 «Implementation decides» item 3); between
  implementations only the copy `copy` transfers.
- The daemon's readiness is the socket: it does not send `sd_notify`, `Type=notify` — only at the controller and the worker ([P/02.4 N1.1](../02-installer/spec/02.4-installer.norms.md) `notify`; Decided by the Architect 2026-10-18 (the second pilot)).

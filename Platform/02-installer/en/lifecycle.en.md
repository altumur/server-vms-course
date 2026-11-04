# Manifest and installer — lifecycle (lesson P/02)

This English text is the source; the Russian [`lifecycle.md`](../lifecycle.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 2).

The lifecycle contract of the installer `w2cctl` and its commands (ADR-0083 addendum (2) item 1): installation and upgrade, manifest installation,
rights derivation, the certificate center, the on-demand workers script. Stage A — on top of the current norms of М10 and М11. The norms are not
retold here: each line leads to its norm.

Norms: [P/02.4](../spec/02.4-installer.norms.md) (Н1.1 units, Н1.2 environment, Н1.5 workers on demand, Н1.6 certificates,
Н1.7 installation, Н1.9 commands and `w2cctl secrets`, Н1.10 a cluster of one, Н4), [P/02.3](../spec/02.3-installer.norms.md)
(Н1.5 the manifest row, Н3 «Manifest change», Н4), [P/02.5](../spec/02.5-installer.norms.md) (Н2 the rights tool,
Н3 «generate_rights», «install»); late chapters — [P/02.4](../spec/02.4-installer.norms.md) Н1.12 domain ports and units,
Н3 «domain installation» (the move of lesson 8, stage B).

## Start

The installer is not a service but operator commands; a repeated installation is an upgrade.

| Command | What | Norm |
|---|---|---|
| `install.sh` | installation and upgrade: code, users and groups, directories, manifests, environment and role files (never over existing ones), the secrets key, units, the center, the rights file, `manifest put`, `enable` | P/02.4 Н1.7 `install` |
| upgrade server by server | `POST /drain` → `safe: true` → stop, upgrade, start → `DELETE /drain`; last — the schema raise. The upgrade does not rewrite an existing `w2c.env`: there is no line `TIMEZONE` — `UTC` applies; another cluster time zone the operator writes into the file by hand on each server | P/02.4 Н1.7 `upgrade`, `w2c_env`, P/06.6 Н2.3, Н3 «raise_schema» |
| `w2cctl manifest put <файл>` | installation of one manifest: load, the full catalogue, the row, then the mark `/rev` | P/02.3 Н3 «Manifest change» |
| `w2cctl manifest status [-rights]` | the state of the manifest rows; with `-rights` — of the rights file too | P/02.4 Н1.9, P/02.5 |
| `w2c-run.sh <роль>` | the process runner: `configstore`, `controller <sub>`, `console`, `resource`, `domain`, `domainconsole`, `domainagent`, `worker <sub> <слот>`, `domainworker <sub>` (they execute `worker.exec` of the manifest row, `W2C_MANIFEST_REV`), `workers`, `rights`, `part <sub> <часть>` (a part of a subsystem: the unit's values and the subsystem file, without `W2C_ROLE`); the environment — the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` → the subsystem file (what was read earlier wins), the files — by parsing, not `source`; `W2C_ROLE` of a wrong role — code 2 | P/02.4 Н1.2, Н1.9 |
| `w2cctl rights -deployment <имя> [--check <файл>]` | rights derivation from `MANIFEST_DIR`; `--check` — by meaning | P/02.5 Н2, Н3 |
| `w2c-ca.sh init \| issue \| revoke \| crl \| own` | the center and the role kits | P/02.4 Н1.6 |
| `w2cctl secrets new \| seal \| rotate \| status` | the key ring | [sealing contract](../../common/contracts/sealing.md), P/02.4 Н1.9 |
| `w2cctl mirror \| space \| retention \| tls status \| domain move` | operator rows and checks | P/02.4 Н1.9 |
| `w2c-workers.sh` | the on-demand workers script: `w2c-workers.service` (`Type=oneshot`, `Restart=no`, `User=w2c-workers` without groups, one per server) and `.timer` (`OnBootSec` 1–2 min, `OnUnitActiveSec` 1 min); the series `<sub>_workers_wanted{server}` → `start`/`stop` of the instances `<prefix>-<SERVER_NAME>-<n>`, n 2…99 (ADR-0084) | P/02.4 Н1.1, Н1.5 |
| a cluster of one with a built-in manifest | the box process itself writes the manifest row and the mark — with the right `admin`, like the installer | P/02.3 Н1.5, P/02.4 Н1.10 |

## Environment

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `MANIFEST_DIR` | the installer's manifest directory | `/opt/w2c/manifests` | P/02.4 Н1.2 |
| `W2C_BOX` | the installation root | `/opt/w2c` | P/02.4 Н1.2 |
| `W2C_ENV` | the file of common settings; `roles/` — next to it | `/etc/w2c/w2c.env` | P/02.4 Н1.2 |
| `PLATFORM_DIR` | the state root, the directory layout | `/data/platform` | P/02.4 Н1.2 «The setting channel and the layout» |
| `SECRETS_KEY` | the ring path: by the layout `<PLATFORM_DIR>/etc/secrets` (`/etc/w2c` is a link), outside the store directory, the object root and the event root | — (the installer's layout: to the unit — `<PLATFORM_DIR>/etc/secrets/platform.key`; not set for a process — development mode, analysis of the review of stage A 6–7, № 19) | P/06.2 Н1.2, P/02.4 Н1.1 `dirs`, Н1.2 |
| `W2C_TLS_DIR` | the root of the kits | `/etc/w2c/tls` | P/02.4 Н1.2, Н1.6 |
| `HOST_MEMORY_MB`, `WORKER_MEMORY_MB`, `CAPACITY` | the ceiling of the role's workers from `roles/<роль>.env` | — | P/02.4 Н1.5 rules 4 |

## Flags

None: operator commands take their own arguments (above), platform processes — only the environment (P/02.4 Н1.2 «The setting
channel»).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `/etc/w2c` → `/data/platform/etc`, `/etc/<sub>` | links; a real directory in their place — an installation refusal | P/02.4 Н1.1 `dirs`, Н1.7 `install.refuse` |
| `/etc/w2c/w2c.env`, `/etc/w2c/roles/<роль>.env`, `<W2C_SUB_ENV>`, `/etc/w2c/configstore.env` | environment files: created, never rewritten; the grammar — the [environment file contract](../../common/contracts/env-file.md), parsing, not `source` | P/02.4 Н1.2, Н1.7 |
| `/etc/w2c/configstore-rights.json` | the rights file, equal by meaning to the derivation; otherwise the installation is refused | P/02.5 Н3 «install» |
| the rows `platform/manifest/<sub>`, `platform/manifest/<sub>/rev` | the manifest row and the mark | [catalogue](../../common/data/catalog.tsv), P/02.3 Н1.5 |
| `/etc/w2c/tls/ca.pem`, `ca.next.pem`, `revoked`, `crl.pem`, `<роль>/server.pem`, `<роль>/server.key` | the center and the role kits | [catalogue](../../common/data/catalog.tsv), P/02.4 Н1.6 |
| `/etc/w2c/secrets/platform.key` | the ring: `secrets new` creates it, `rotate` appends on top | [catalogue](../../common/data/catalog.tsv), [sealing contract](../../common/contracts/sealing.md) «Файл кольца» |
| the units of Н1.1 and the socket units `configstore-*.socket` | written by `install.sh` | P/02.4 Н1.1 |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | the installation or upgrade passed; `manifest put` put the manifest or «unchanged» | P/02.4 Н1.7, P/02.3 Н3 |
| 2 | `manifest put`: the file is refused by the loader, the full catalogue is refused, `toolarge`, a shell with `on…=`, a declared shell or a file of `console.files` is missing | P/02.1 Н4, P/02.3 Н4 |
| ≠ 0 | the installer: a refusal before changes or after the start of writing — with the phase and the path, new services are not enabled | P/02.4 Н1.7 `failure`, Н4 |
| ≠ 0 | `rights --check`: the file is not equal by meaning to the derivation; the derivation is refused on an unrepresentable declaration | P/02.5 Н4 |

A workers script that has started and stopped nothing for a role (no role file — the role is skipped, the walk goes
on; there is no series or it cannot be read; the console is silent; polkit refused) writes a log line; the norm does not
set an exit code for this (P/02.4 Н1.5 rules, Н4).

## Signals and readiness

The commands are one-shot. The workers script is `Type=oneshot`, the repeat is set by the timer; it stops only the instances with n ≥ 2 above the series,
from the highest number (P/02.4 Н1.5 rules 3).

## Stand

«Стенд» — the [common acceptance README](../../common/acceptance/README.md) (analysis of the review of stage B 3–5, № 33):
- the command that loads one manifest file — `{file}` (P/02.1, the corpus `verdicts.tsv`);
- `manifest-put {socket} {file}` — through `admin.sock`, the stand's manifests one by one before the first `@start`;
- the rights derivation command — `{manifests}`, `{deployment}` (`dep`), `{file}`: `{rights}` of the acceptances moved from М10/4–11 (analysis of the review of stage B 3–5, № 34), and the variants of chapter 2.5.

## Late chapters (domain)

| What | How | Norm |
|---|---|---|
| domain units | `w2c-domain.service` (`SIGNER_HOST/PORT` 0.0.0.0:8445), `w2c-domainconsole.service` (8444), `w2c-domainagent.service` (no port of its own; the relay door — `RELAY_PORT` 8446); `w2c-domainagent-token-<роль>.socket` — the local token door, `<AGENT_TOKEN_DIR>/<роль>.sock` | P/02.4 Н1.12, Н1.1, [local token door contract](../../common/contracts/local-token-door.md) (analysis of the review of stage A 8–10, decision 1) |
| domain installation | an operator command, once per domain | P/02.4 Н3 «domain installation» (P/02.4-10) |

## Open

- The installer is not in the list of roles of P/01.2 Н1.1: its writes go with the right `admin` (the decision on the data catalogue, item 8).

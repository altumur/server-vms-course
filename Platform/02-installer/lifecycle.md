# Manifest and installer — lifecycle (lesson P/02)

This English text is the source; the Russian translation `ru/lifecycle.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The lifecycle contract of the installer `w2cctl` and its commands: installation and upgrade, manifest installation,
rights derivation, the certificate center, the on-demand workers script. The norms are not
retold here: each line leads to its norm.

Norms: [P/02.4](spec/02.4-installer.norms.md) (N1.1 units, N1.2 environment, N1.5 workers on demand, N1.6 certificates,
N1.7 installation, N1.9 commands and `w2cctl secrets`, N1.10 a cluster of one, N4), [P/02.3](spec/02.3-installer.norms.md)
(N1.5 the manifest row, N3 «Manifest change», N4), [P/02.5](spec/02.5-installer.norms.md) (N2 the rights tool,
N3 «generate_rights», «install»); late chapters — [P/02.4](spec/02.4-installer.norms.md) N1.12 domain ports and units,
N3 «domain installation».

## Start

The installer is not a service but operator commands; a repeated installation is an upgrade.

| Command | What | Norm |
|---|---|---|
| `install.sh` | installation and upgrade: code, users and groups, directories, manifests, environment and role files (never over existing ones), the secrets key, units, the center, the rights file, `manifest put`, `enable` | P/02.4 N1.7 `install` |
| upgrade server by server | `POST /drain` → `safe: true` → stop, upgrade, start → `DELETE /drain`; last — the schema raise. The upgrade does not rewrite an existing `w2c.env`: there is no line `TIMEZONE` — `UTC` applies; another cluster time zone the operator writes into the file by hand on each server | P/02.4 N1.7 `upgrade`, `w2c_env`, P/06.6 N2.3, N3 «raise_schema» |
| `w2cctl manifest put <file>` | installation of one manifest: load, the full catalogue, the row, then the mark `/rev` | P/02.3 N3 «Manifest change» |
| `w2cctl manifest status [-rights]` | the state of the manifest rows; with `-rights` — of the rights file too | P/02.4 N1.9, P/02.5 |
| `w2c-run.sh <role>` | the process runner: `configstore`, `controller <sub>`, `console`, `resource`, `domain`, `domainconsole`, `domainagent`, `worker <sub> <slot>`, `domainworker <sub>` (they execute `worker.exec` of the manifest row, `W2C_MANIFEST_REV`), `workers`, `rights`, `part <sub> <part name>` (a part of a subsystem: the unit's values and the subsystem file, without `W2C_ROLE`); the environment — the unit's values → `roles/<W2C_ROLE>.env` → `w2c.env` → the subsystem file (what was read earlier wins), the files — by parsing, not `source`; `W2C_ROLE` of a wrong role — code 2 | P/02.4 N1.2, N1.9 |
| `w2cctl rights -deployment <name> [--check <file>]` | rights derivation from `MANIFEST_DIR`; `--check` — by meaning | P/02.5 N2, N3 |
| `w2c-ca.sh init \| issue \| revoke \| crl \| own` | the center and the role kits | P/02.4 N1.6 |
| `w2cctl secrets new \| seal \| rotate \| status` | the key ring | [sealing contract](../common/contracts/sealing.md), P/02.4 N1.9 |
| `w2cctl mirror \| space \| retention \| tls status \| domain move` | operator rows and checks | P/02.4 N1.9 |
| `w2c-workers.sh` | the on-demand workers script: `w2c-workers.service` (`Type=oneshot`, `Restart=no`, `User=w2c-workers` without groups, one per server) and `.timer` (`OnBootSec` 1–2 min, `OnUnitActiveSec` 1 min); the series `<sub>_workers_wanted{server}` → `start`/`stop` of the instances `<prefix>-<SERVER_NAME>-<n>`, n 2…99 | P/02.4 N1.1, N1.5 |
| a cluster of one with a built-in manifest | the box process itself writes the manifest row and the mark — with the right `admin`, like the installer | P/02.3 N1.5, P/02.4 N1.10 |

## Environment

| Variable | Meaning | Default | Norm |
|---|---|---|---|
| `MANIFEST_DIR` | the installer's manifest directory | `/opt/w2c/manifests` | P/02.4 N1.2 |
| `W2C_BOX` | the installation root | `/opt/w2c` | P/02.4 N1.2 |
| `W2C_ENV` | the file of common settings; `roles/` — next to it | `/etc/w2c/w2c.env` | P/02.4 N1.2 |
| `PLATFORM_DIR` | the state root, the directory layout | `/data/platform` | P/02.4 N1.2 «The setting channel and the layout» |
| `SECRETS_KEY` | the ring path: by the layout `<PLATFORM_DIR>/etc/secrets` (`/etc/w2c` is a link), outside the store directory, the object root and the event root | — (the installer's layout: to the unit — `<PLATFORM_DIR>/etc/secrets/platform.key`; not set for a process — development mode) | P/06.2 N1.2, P/02.4 N1.1 `dirs`, N1.2 |
| `W2C_TLS_DIR` | the root of the kits | `/etc/w2c/tls` | P/02.4 N1.2, N1.6 |
| `HOST_MEMORY_MB`, `WORKER_MEMORY_MB`, `CAPACITY` | the ceiling of the role's workers from `roles/<role>.env` | — | P/02.4 N1.5 rules 4 |

## Flags

No daemon flags: P/02 is operator commands. Their option form is [`forms/daemon-flags.tsv`](forms/daemon-flags.tsv), the command grammar is [`forms/operator-commands.tsv`](forms/operator-commands.tsv); platform processes use the environment (P/02.4 N1.2).

## Directories and files

| Path | What | Norm |
|---|---|---|
| `/etc/w2c` → `/data/platform/etc`, `/etc/<sub>` | links; a real directory in their place — an installation refusal | P/02.4 N1.1 `dirs`, N1.7 `install.refuse` |
| `/etc/w2c/w2c.env`, `/etc/w2c/roles/<role>.env`, `<W2C_SUB_ENV>`, `/etc/w2c/configstore.env` | environment files: created, never rewritten; the grammar — the [environment file contract](../common/contracts/env-file.md), parsing, not `source` | P/02.4 N1.2, N1.7 |
| `/etc/w2c/configstore-rights.json` | the rights file, equal by meaning to the derivation; otherwise the installation is refused | P/02.5 N3 «install» |
| the rows `platform/manifest/<sub>`, `platform/manifest/<sub>/rev` | the manifest row and the mark | [catalogue](../common/data/catalog.tsv), P/02.3 N1.5 |
| `/etc/w2c/tls/ca.pem`, `ca.next.pem`, `revoked`, `crl.pem`, `<role>/server.pem`, `<role>/server.key` | the center and the role kits | [catalogue](../common/data/catalog.tsv), P/02.4 N1.6 |
| `/etc/w2c/secrets/platform.key` | the ring: `secrets new` creates it, `rotate` appends on top | [catalogue](../common/data/catalog.tsv), [sealing contract](../common/contracts/sealing.md) «Ring file» |
| the units of N1.1 and the socket units `configstore-*.socket` | written by `install.sh` | P/02.4 N1.1 |

## Exit codes

| Code | When | Norm |
|---|---|---|
| 0 | the installation or upgrade passed; `manifest put` put the manifest or «unchanged» | P/02.4 N1.7, P/02.3 N3 |
| 2 | `manifest put`: the file is refused by the loader, the full catalogue is refused, `toolarge`, a shell with `on…=`, a declared shell or a file of `console.files` is missing | P/02.1 N4, P/02.3 N4 |
| ≠ 0 | the installer: a refusal before changes or after the start of writing — with the phase and the path, new services are not enabled | P/02.4 N1.7 `failure`, N4 |
| ≠ 0 | `rights --check`: the file is not equal by meaning to the derivation; the derivation is refused on an unrepresentable declaration | P/02.5 N4 |

A workers script that has started and stopped nothing for a role (no role file — the role is skipped, the walk goes
on; there is no series or it cannot be read; the console is silent; polkit refused) writes a log line; the norm does not
set an exit code for this (P/02.4 N1.5 rules, N4).

## Signals and readiness

The commands are one-shot. The workers script is `Type=oneshot`, the repeat is set by the timer; it stops only the instances with n ≥ 2 above the series,
from the highest number (P/02.4 N1.5 rules 3).

## Stand

«Stand» — the [common acceptance README](../common/acceptance/README.md):
- the command that loads one manifest file — `{file}` (P/02.1, the corpus `verdicts.tsv`; judge-only: the corpus table);
- `manifest-put {socket} {file}` — through `admin.sock`, the stand's manifests one by one before the first `@start`;
- the rights derivation command — `{manifests}`, `{deployment}` (`dep`), `{file}`: `{rights}` of the acceptances of the other lessons and the variants of chapter 2.5.

## Late chapters (domain)

| What | How | Norm |
|---|---|---|
| domain units | `w2c-domain.service` (`SIGNER_HOST/PORT` 0.0.0.0:8445), `w2c-domainconsole.service` (8444), `w2c-domainagent.service` (no port of its own; the relay door — `RELAY_PORT` 8446); `w2c-domainagent-token-<role>.socket` — the local token door, `<AGENT_TOKEN_DIR>/<role>.sock` | P/02.4 N1.12, N1.1, [local token door contract](../common/contracts/local-token-door.md) |
| domain installation | an operator command, once per domain | P/02.4 N3 «domain installation» (P/02.4-R009, P/02.4-R013, P/02.4-R483, P/02.4-R484, P/02.4-R504) |

## Open

- The installer is not in the list of roles of P/01.2 N1.1: its writes go with the right `admin`.

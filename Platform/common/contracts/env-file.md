# The environment file contract: the grammar `KEY=VALUE`

This English text is the source; the Russian translation `ru/contracts/env-file.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in chapters; guess of stage C C04-ENV-01, the Architect's decision of 2026-10-23). The owner is chapter
[P/02.4](../../02-installer/spec/02.4-installer.norms.md) of the installer (N1.2: variables, files, reading order). The participants are
all whose norm itself parses environment files: the runner `w2c-run.sh` and the workers script (`roles/<role>.env`, P/02.4 N1.5
step 4); the role processes get their environment from the runner (lifecycle of lessons P/02–P/10: «by parsing, not `source`» — the runner's
parsing; ACC-VECTORS-CONNECT-04). Moved from P/02.4 N1.2 together with the edges B19 without a change of behaviour; files and reading order, variables, `CLUSTERS` and
the unit constants are the sections below (layout audit, the Architect's decision of 2026-10-25, A-07, A-09, A-16, A-17, B-26).

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Grammar

Environment files (`w2c.env`, `roles/*.env`, the subsystem file, `configstore.env`) are read by parsing, not by
`source`: a line `KEY=VALUE`, `KEY` is `[A-Za-z_][A-Za-z0-9_]*`; an optional prefix `export `; a value in paired `"…"`
or `'…'` is taken without the quotes, there are no substitutions; an empty line and a line whose first non-blank character is `#` are skipped. Any other
line is a start refusal with code 2 and a log line that names the file and the line number.

At the edges (reconciliation of python and go M10/6–11, B19): lines are separated by LF; a CR character in a line, a BOM at the start of the file, a space or a tab before or after
`=` and in the name — the line is not by the grammar; `export` is exactly one word and one space before `KEY`, `export` without `KEY=` is not by the
grammar; a value without quotes is everything after `=` to the end of the line as is, without trimming spaces, a `#` inside the value is
part of the value, not a comment; an empty value (`KEY=`) is an empty string; an unpaired quote is not by the grammar.

More at the edges (guess of stage C ENV-G01, the Architect's decision of 2026-10-23): «blank» before the `#` of a comment is only a space and a tab (U+00A0 and the others are not);
a line of spaces only is not by the grammar; a NUL character in a line is not by the grammar; the last line without LF is accepted;
a repeated name in one file — the first occurrence wins. The file is strictly UTF-8: a line with an invalid UTF-8 sequence is
not by the grammar (code 2, the log line names the file and the line number; guess of stage C ENV-F01, the Architect's decision of
2026-10-23).

## No file

For all environment files (the role file, `w2c.env`, the subsystem file, `configstore.env`; the path explicit or by default): there is no file —
a skip, not an error (like `W2C_SUB_ENV` [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N1.2); the file exists but is not readable
(permissions, an I/O error) — a start refusal with code 2 and a log line that names the file (guess of stage C W03-G07, the Architect's decision of 2026-10-23).

## Files and reading order

Moved from [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N1.2 without change (layout audit, the Architect's decision of 2026-10-25, B-26).

The runner's reading order: the unit values → the role file `roles/<W2C_ROLE>.env` → `w2c.env` → the subsystem file; what is read earlier wins. A part unit (`w2c-run.sh part`, P/02.4 N1.9) reads only the unit values and the subsystem file `W2C_SUB_ENV` (ADR-0091 addendum (3) item 2). The directory `roles/` lies next to `w2c.env` (the directory of the file `W2C_ENV`, by default `/etc/w2c/roles/`); there is no other place. A `W2C_ROLE` of the unit that does not match the role of the runner command (`w2c-run.sh <command>`, P/02.4 N1.9) is a start refusal with code 2 (reconciliation of python and go M10/6–11, B20); for `w2c-run.sh worker <sub>` the role of the command is `<sub>worker`, for `domainworker <sub>` it is `<sub>domain`: one program in both roles sees the environment by one rule (ADR-0091 addendum (4), (5); the Architect's decisions on the repeated review of 2026-10-23).

`W2C_ENV` and `W2C_SUB_ENV` are taken from the unit environment once per reading pass: the same key in a loaded file is not
applied (there is no redirection), a journal line without the value, not a refusal. `W2C_ROLE` of the unit is mandatory and equals the role of the
command: absent or not equal — a start refusal, code 2 (ENV54-01/02, the Architect's decision of 2026-10-25). The rule of `W2C_ROLE` belongs to
the routes of processes of a platform role (the runner with a role file), not to the route of a part: a part has no role — `W2C_ROLE` is not
required and not read, the role file and `w2c.env` are not read; the unit values and the file `W2C_SUB_ENV` are read (C02-ENV-PART-99, the Architect's decision of 2026-10-26).

## Environment variables

The table is moved from P/02.4 N1.2 without change (layout audit, the Architect's decision of 2026-10-25, A-07, A-09): the form and the default are here; what a process does
with the value is the norms of its lesson. `CLUSTERS` is the section below.

| Variable | Meaning | Default | Set by |
|---|---|---|---|
| the variable `slot.name_env` of the manifest (only if the manifest declared it; `testsub2` — `TALLY_NAME`) | the slot name (a wish, P/03.2 N1.4) — the same as the argument `%i` of the unit | — | the unit |
| `BOX_ID` | the box; otherwise `/etc/machine-id`, otherwise hostname; an empty value is as if not set ([the instance contract](instance.md) `sources`; INSTANCE130-SOURCES-01) | `%m` | the unit |
| `SERVER_NAME` | the server; by the grammar of the slot suffix `^[a-z0-9]+(-[a-z0-9]+)*$` (P/03.2 N1.4: lowercase, without dots — the server name enters the slot name `<prefix>-<server>-<n>` of the unit instance, P/02.4 N1.1, and the series `workers_wanted{server}`, P/02.4 N1.5), otherwise a start refusal with code 2; narrower than the host name of the doors of P/06.6 N2.1 (reconciliation of python and go M10/3–5) | the short hostname (`%l`) | `w2c.env` |
| `LABELS` | the node labels separated by commas — [the label list](labels.md); a word outside the label alphabet is a worker start refusal, code 2, like other wrong environment values (P/03.2 N3 «start()» step 2; the VMS request «heartbeat and a garbled row», the Architect's decision of 2026-10-23) | — | `w2c.env` |
| `INSTANCE_ID` | a unique instance instead of `<box>:<pid>:<6hex>`; an empty value is as if not set (INSTANCE130-SOURCES-01); both sources are by the grammar of [the instance contract](instance.md), on disk — the name encoding of [the event journal contract](event-journal.md); otherwise a refusal before the start (P/03.2 N3 «start()» step 2, N4; analysis of the review of stage B 3–5, № 7); a new process does not reuse a former value | — | — |
| `PLATFORM_DIR` | the state root | `/data/platform` | `w2c.env` |
| `PLATFORM_STORE` | the store: `configstore:///run/configstore/<role>.sock` — the door of P/01.1, the only link of a process with the store of another implementation (ADR-0083 item 2); `file://` — the profile «the whole box is one implementation»: the processes of the box and the store are of one implementation, the format on disk is not normed and is not a contract; `memory://` — in the process, without durability (the store pilot, A9) | `file://<PLATFORM_DIR>/config` | the unit |
| `OBJECTS` / `PLATFORM_OBJECTS` | objects: `file://` \| `cluster://[<name>][?resource=<url>]` (without `resource` — the resource of its own server by the door row, P03-OBJECTS-DEFAULT-1FD); parsing of the address — [the object store client contract](object-client.md) `parse` (C10-OBJECT-ADDRESS-32) | `file://`; `cluster://` with configstore | `w2c.env` |
| `RESOURCE_ROOT` / `EVENTS` | the root of the event trees | `<PLATFORM_DIR>/events` | `w2c.env` |
| `MANIFEST_DIR` | the directory of the installer's manifests (chapter 2.3) | `/opt/w2c/manifests` | the runner |
| `SECRETS_KEY` | the path of the key ring; for a unit — by the layout `<PLATFORM_DIR>/etc/secrets/platform.key`; not set for a process — development mode (P/06.2 N1.2 `unset`; analysis of the review of stage A 6–7, № 19) | — | the unit (credential) |
| `W2C_ROLE` | the role of the process | none: set by the unit | the unit / the runner |
| `W2C_TLS_DIR` | the root of the certificate kits | Linux `/etc/w2c/tls`; macOS `<W2C_BOX>/tls` by ADR-0075 | the unit / the runner |
| `W2C_ENV` | the file of common settings | `/etc/w2c/w2c.env` | the unit |
| `W2C_SUB_ENV` | the file of subsystem settings | for the unit of a worker and of a subsystem part — `/etc/<sub>/<sub>.env` (`/data/platform/etc/subsystems/<sub>/<sub>.env` through a link; macOS — the same path relative to `W2C_BOX`); there is no file — the subsystem defaults, not an error; without a value the file is not included; the platform processes do not include it; the grammar and the order are above, the subsystem file last: it does not override the platform (ADR-0091 addendum (2) item 3) | the unit |
| `W2C_BOX` | the installation root | `/opt/w2c` | the unit |
| `CONSOLE_ORIGINS` | the origins of the page of the cluster console and the domain console of this installation, in a domain also of the members' consoles whose pages view the archive of this cluster (the browser goes to the holder's door itself; C03-ORIGINS-MEMBERS-01), for CORS of the doors of subsystem processes: exact `scheme://host[:port]` separated by commas, compared byte for byte; empty — no CORS (P/03.4 N1.7 `cors`; ADR-0091 addendum (7), (8)); a console with a kit — the origin `https://<SERVER_NAME>:<port>` (the port — always, if not 443; a tunnel — to the same port, or its origin is written; ADR-0075 addendum 2026-10-26 (3) item 4, (4) item 5) | — | `w2c.env` |
| `W2C_DEPLOYMENT` | `<dep>` — the beginning of the OS names of subsystems (users, groups, units, share directories; P/02.4 N1.1 `users_groups`); whole `[a-z][a-z0-9]{0,15}`, otherwise an installation refusal before changes; a mismatch of the installer environment with the line of `w2c.env` is the same refusal (P/02.4 N1.7) | `w2c` | `w2c.env` (written by the installation, the input is the installer environment; guess of stage C I02-OS-STEM, the Architect's decision of 2026-10-23) |
| `CONSOLE_ROOT` | the console | — | the unit (an input of the installer environment, P/02.4 N1.7 `w2c_env`) |
| `CONSOLE_HOST`, `CONSOLE_PORT` | the address of the cluster console; one per box: read by the console (binding) and by the clients of their own console — the URL by `own_url` of [the role certificate contract](role-certificate.md) «The client of a door of its own cluster»; TLS — by the role kit, on the loopback too (P/02.4 N1.6 `console`; ::1 — only by an explicit entry) | 127.0.0.1, 8080 | `w2c.env` (written by the installer, P/02.4 N1.7 `w2c_env`; the unit does not set it; ADR-0075 addendum 2026-10-26 (5) item 2) |
| `CONSOLE_CALL_PORT` | the port of the callback listener of the cluster console: a mandatory leaf of the role, only requests with a ticket ([the role certificate contract](role-certificate.md) «The callback leaf»; ADR-0094 addendum (16)); the address — the addresses of `SERVER_NAME`, not `CONSOLE_HOST`; without a kit or without a manifest with `door.pass.calls` the listener is not opened, the value is not read | 8081 | `w2c.env` (written by the installer, P/02.4 N1.7 `w2c_env`; no line — the default) |
| `RESOURCE_HOST`, `RESOURCE_PORT`, `RESOURCE_URL`, `RESOURCE_TLS` | the resource; `RESOURCE_HOST`, `RESOURCE_PORT` are not written by the unit — the process default; off the loopback — only with a kit (P/02.4 N1.6 `process`; ADR-0075 addendum 2026-10-26 (6) item 2; review of the norms of ADR-0075, Claude fd85ea8cc, S-3) | 127.0.0.1, 8090 | `w2c.env` |
| `CAPACITY`, `WORKER_MEMORY_MB`, `HOST_MEMORY_MB` | the capacity of the role and the memory budget (ADR-0070) | — | `roles/<role>.env` |
| `HUNG_MOVE_AFTER`, `REACH_BUDGET` | the controller ([P/04 N1.4](../../04-controller/spec/04-controller.norms.md)) | 900, 10 | `w2c.env` |
| `W2C_SHRINK_AFTER` | stand only: the shrink period of the controller `SHRINK_AFTER`, s ([P/04 N1.4](../../04-controller/spec/04-controller.norms.md); when set — a loud journal line at start) (analysis of the review of stage B 3–5, № 18) | not set (300) | the stand runner; not set outside the stand |
| `W2C_DEBUG_PERSON` | the debug identity of the cluster console and the domain console: the name of a person for requests without a token and without a cookie from the loopback ([the gate-and-pass contract](gate-and-pass.md) «The gate» `identity` item 4; ADR-0050; when set — the alarm `session.debug_open` at start); the table row is by a finding of the move of lesson 10 (the variable was named by the contract and by P/06.3 N1.3, while the table is closed) | not set | `roles/<role>.env` (development only) |
| `BUILD` | the build word ([the schema contract](schema.md); P/06.6 N1.1a) | `dev` | the build |
| `CLUSTER` | the cluster name of the installation: the name of the domain member ([P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.1) and `cluster` of the snapshot ([P/04 N1.3a](../../04-controller/spec/04-controller.norms.md)) | `local` (outside a domain) | `w2c.env` |
| `PUBLIC_URL` | the entry address of the cluster for people, https:// with a host: the agent carries it into the domain view (P/09.1 N1.2, P/08.1 N1.4); a link to another cluster's camera (ADR-0111 item 11); behind NAT it is not set | not set | `w2c.env` |
| `DOMAIN_FOLDERS` | the copy of the common folders at the member: `chains` — only the chains of its own units (camera, flash), P/08.5 N1.8; set by the installer of the camera profile | `all` | `w2c.env` |
| `TIMEZONE` | the time zone of the cluster: the value `timezone` of the answer `GET /session` ([the gate-and-pass contract](gate-and-pass.md) `session`; ADR-0094 B6); read by the cluster console and the domain console at start, by the worker — as a value of the runner's environment (ADR-0105 item 4; the part `W2C_SUB_ENV` does not get it). An IANA name by the grammar `^(?:[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z][A-Za-z0-9_+-]*)*)$`. Only the form is checked: the console does not read the zone database, so a name of the form that is not in the zone database passes. An empty value and a value out of form are a start refusal, code 2, the log line names the value, like other wrong environment values; at the installer — an installation refusal before changes (P/02.4 N1.7 `refuse`). The value is one for all servers of the cluster — the operator's business, as with `CLUSTER`: the consoles do not check it | `UTC` | `w2c.env` (written by the installer, P/02.4 N1.7 `w2c_env`) |
| `DOMAIN_SERVER` | installer only: `yes` — this server holds the domain or stands as a spare, the installation enables `w2c-domain`, the domain console and the worker units on the domain (P/02.4 N1.7 `w2c_env`); processes do not read it | `no` | `w2c.env` (written by the installer, the input is the installer environment) |
| `LOGIN_URL`, `SIGNER_URL`, `DOMAIN_*`, `CLUSTERS`, `RELAY_*`, `REACHES` | the domain (lessons P/08–P/10 and chapter P/06.7; `SIGNER_HOST/PORT`, `DOMAIN_CONSOLE_HOST/PORT` — P/02.4 N1.12 (`SIGNER_HOST`, `SIGNER_PORT`, `RELAY_HOST`, `RELAY_PORT` are not written by the unit: the process default `0.0.0.0` is not an explicit address, without a kit — a start refusal, code 2; P/02.4 N1.6 `process`; ADR-0075 addendum 2026-10-26 (5) item 4); `SIGNER_URL` — [P/08.2](../../08-domain/spec/08.2-domain.norms.md) N1.3; `CLUSTERS`, `DOMAIN_CONSOLE_URL` — [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.4, `CLUSTERS` is read both by the process `domain` ([P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.6–N1.8) and by the agent (P/09.1 N3 «follow»); `REACHES` — the agent, P/09.1 N1.7 (analysis of the review of stage A 8–10, № 32); `DOMAIN_CA`, `RELAY_CA`, `RELAY_MEMBER` — [the peer contract](peer.md) «Client and first contact»; `RELAY_URL` — P/09.1 N1.7) | — | the operator |
| `RELAY` | the relay mode of the agent: `1` — the agent holds a door for the members behind it, absent or empty — does not hold, anything else — a start refusal, code 2 (the Architect's decision, analysis of the review of stage B 8–10, № 17, ADR-0083 addendum (15); [P/09.2](../../09-agent/spec/09.2-agent.norms.md) N1.1 `door`; the Architect's decision on the move plans 8–10, ADR-0083 addendum (14) item 13) | not set | `roles/domainagent.env` |
| `AGENT_TOKEN_DIR` | the directory of the sockets of the local token door `<role>.sock` — one for the agent unit and the worker unit ([the local token door contract](local-token-door.md) «The role socket»; P/02.4 N1.1 `users_groups`, `dirs`; the Architect's decision on the move plans 8–10, ADR-0083 addendum (14) item 13) | `/run/w2c/domainagent` | the unit |
| `W2C_WALL_OFFSET` | stand only: the shift of the agent's wall clock, s ([P/09.1](../../09-agent/spec/09.1-agent.norms.md) «Implementation decides» item 3; when set — a loud journal line at start; the Architect's decision on the move plans 8–10, ADR-0083 addendum (14) item 13) | not set (0) | the stand runner; not set outside the stand |
| `CONFIGSTORE_ID/RAFT/API/GROUP_SIZE/JOIN/FLAGS/TUNING` | the store daemon | tuning `lan` | `configstore.env` |
| `NOTIFY_SOCKET` | the systemd watchdog | — | systemd |

**Two names of one setting** (`OBJECTS` / `PLATFORM_OBJECTS`, `RESOURCE_ROOT` / `EVENTS`): one is set — that one; both are set
with equal values (byte for byte) — the same; both are set with different ones — a start refusal, code 2, the log line names both names, like
other wrong environment values (a silent choice would hide a layout error); neither is set — the table default
(C10-ENV-PAIR-01, the decision of the Specification).

The slot name is the argument `%i` or the variable `slot.name_env` ([P/03.2](../../03-worker/spec/03.2-worker.norms.md) N3 «start()» step 3).

### `CLUSTERS`

From [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.4 without change (layout audit, the Architect's decision of 2026-10-25, A-09); read by the cluster console, the process `domain`
([P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.6–N1.8) and the agent ([P/09.1](../../09-agent/spec/09.1-agent.norms.md) N3 «follow»). An environment line for the holder and the first contact: the address of any other member is `Entry.url` of its section row; for tens of thousands, no environment can be written (P/06.7 N1.6; ADR-0113 addendum (1) item 4).

```yaml
CLUSTERS:     <name>=<url>[,<name>=<url>…]; name — a member name (P/08.3 N1.1), url — http:// or https:// with a host, without
              userinfo (`user@`), a path and a trailing «/» (userinfo — added by the reconciliation of M11, D6); a repeated name, an element without
              «=», another url — the value is not read (503 at the console, not a process crash); no variable or empty — an empty list
```

## Constants and units

One place of the values that the installer's unit and the processes read (layout audit, the Architect's decision of 2026-10-25, A-16, A-17); the role of each is in its lesson.

```yaml
FOR:              300   # s; a worker substitution longer than this does not substitute: the units leave (role — P/03.4 N1.2)
HUNG_MOVE_AFTER:  900   # s; the age of the observed slot version up to the limit hung/unsure/wait; the variable HUNG_MOVE_AFTER
                        # of the controller environment, default 900 (role — P/04 N1.4)
REACH_BUDGET:     10    # units per pass for moves by reachability; the variable REACH_BUDGET, default 10 (P/04 N1.4)
SHRINK_AFTER:     300   # s; without a shortage — shrinking (P/04 N3 «shortage(), order(), withdraw the order, shrink() — with grows: true»); only at the stand — W2C_SHRINK_AFTER (the table above)
watchdog:         WatchdogSec of the worker unit — between FOR and HUNG_MOVE_AFTER: 360 (SHOULD; P/02.4 N1.1); notify — from the loop,
                  not from the substitution (P/03.3 N1.2 watchdog)
```

## Vectors

The package [`env-file`](../vectors/env-file/README.md): one line of a file → a skip, a pair `KEY`, `VALUE` or «not by the
grammar»; `files.tsv` — the reading order of files: `W2C_ENV`/`W2C_SUB_ENV` in a file do not redirect, `W2C_ROLE` absent or not
equal to the role of the command — code 2 (ENV54-01/02, the Architect's decision of 2026-10-25); the route of a part — without a role, the unit and
`W2C_SUB_ENV` (C02-ENV-PART-99).

## Stand command

The command `env-line` of the profile `02-installer` — a line of an environment file → a pair, `skip` or `bad`, without an envelope; the wire is the section
«Stand command `env-line`» of [the README of the package](../vectors/env-file/README.md) (guess of stage C C04-ENV-01, the Architect's decision of
2026-10-23).

# Vectors: a line of the environment file

This English text is the source; the Russian translation `ru/vectors/env-file/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is chapter P/02.4 through [the environment file contract](../../contracts/env-file.md) (the grammar `KEY=VALUE`, the edges B19;
stage C guess C04-ENV-01, the Architect's decision 2026-10-23). The participants are those whose norm itself parses environment files:
the runner `w2c-run.sh` and the workers script (the profile `02-installer`); the role processes get the environment from the runner (below,
«Who performs it»; ACC-VECTORS-CONNECT-04). The bytes are written by
«Спецификация».

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is the header. Four fields:

| Field | Meaning |
|---|---|
| `case` | the name of the case, unique |
| `line` | one line of the file without the terminating LF — a JSON string (CR, BOM, tab are written by the escapes `\r`, `﻿`, `\t`) |
| `expect` | a JSON value: `["KEY","VALUE"]` — a pair; `"skip"` — the line is skipped (empty or a comment); `"bad"` — not by the grammar (at a process — a refusal to start with code 2 with a log line naming the file and the line number) |
| `note` | the rule of the contract |

33 cases: 13 pairs, 3 `skip`, 17 `bad`. A BOM belongs to the beginning of the file; the row `bom` is the first line of the file. The rules of the file
as a whole a line does not express — they are checked by reading: a last line without LF is accepted; a repeated name in one file —
the first occurrence wins (ENV-G01); a line with an invalid UTF-8 sequence is not by the grammar: a cell is a JSON string
and does not express invalid UTF-8 (ENV-F01).

## `files.tsv` (ENV54-01/02)

The same file rules; the header `case<TAB>input<TAB>expect<TAB>note`. `input` — `{route?, command_role?, unit, files}`: the route
(`"part"` — the unit of a part, `w2c-run.sh part`; absent — a process of a platform role), the role of the runner command (only at the role route),
the values of the unit (a mapping) and the files by path — an array of the lines of each file (the lines — by the grammar of `cases.tsv`);
a file not in the mapping does not exist. `expect` — the environment after the reading pass (a mapping, comparison by value) or
`@exit 2` — a refusal to start. The reading order is the contract «Files and reading order»: the unit → `roles/<W2C_ROLE>.env` next to
`W2C_ENV` → `W2C_ENV` → `W2C_SUB_ENV`; what is read earlier wins; at a part — the unit → `W2C_SUB_ENV`. 6 rows: `W2C_ENV` and `W2C_SUB_ENV`
in a file do not redirect; `W2C_ROLE` is absent and is not equal to the role of the command — code 2; the route of a part — without a role, only the unit and
`W2C_SUB_ENV`, `w2c.env` is not read (C02-ENV-PART-99). `files.tsv` is performed by the runner `w2c-run.sh` (`02-installer`): the reading order
of the files is its own (the contract «Files and reading order»); `cases.tsv` — by those whose norm itself parses an environment file: the runner `w2c-run.sh` and the workers script (`roles/<роль>.env`,
P/02.4 Н1.5 step 4) — the profile `02-installer`; the role processes get the variables from the runner and do not parse files
(lifecycle P/03–P/10: «окружение собирает раннер») (ACC-VECTORS-CONNECT-02, -04, the Architect's decisions 2026-10-26).

A native input outside the form (not a JSON string) exits with code 2 and empty stdout. Computed line outcomes and whole-file start refusal remain distinct; the wire of each table is in the form below.

## Vector wire

The wire of `cases.tsv`, `files.tsv` is set by the `common/env-file` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.

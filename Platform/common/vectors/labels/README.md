# Vectors: the label alphabet

This English text is the source; the Russian translation `ru/vectors/labels/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is lesson P/06 through [the label alphabet contract](../../contracts/labels.md) (`label`, `set` `output`, `text`, `read`;
stage C guesses L01–L03, the Architect's decision 2026-10-23). The participants are those who read labels by the contract: the console (the labels field
of a unit, the label doors of a server), the controller (`labels-subset`), grants by labels. The bytes are written by «Спецификация». The labels field
of a unit as a list field — the vectors [`values-by-type`](../values-by-type/README.md) (`list:labels`) and
[`row-check`](../row-check/README.md).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is the header. Five fields:

| Field | Meaning |
|---|---|
| `case` | the name of the case, unique |
| `op` | `label` — one label by the alphabet; `set_write` — a label set (the input array) → the list text that the platform writes; `text_read` — a list text → a set; `env_labels` — the `LABELS` of the worker's environment → the node labels as a set (a repeat collapses; ENV54-02) |
| `input` | a JSON value: a string at `label`, `text_read` and `env_labels`, an array of strings at `set_write` |
| `expect` | `ok` (the label is admissible), `@refuse` (a refusal), otherwise a JSON value: at `set_write` — a text string (byte for byte), at `text_read` and `env_labels` — a set as an array in ascending byte order (compared as a set) |
| `note` | the rule of the contract or an acceptance step of P/06.6 |

32 cases: 15 `label`, 6 `set_write`, 8 `text_read`, 3 `env_labels`.

## Run

A side performs its own label alphabet code: the check of a label, the write of a set as a list text and the read of a list text into a set.
The value of the labels field of a unit is not reordered as a set (the contract `output`) — these vectors do not check it: a field with
a repeat `["a","a"]` is stored as is (`values-by-type` `lb-repeat`, `row-check` `labels_repeat`); comparing such a field
as the set `{a}` (the constraint `labels-subset`) the package does not express — it has no set comparison operation: by reading
(C51-LABEL-LIST-01). `read_repeat` — a repeat in the label text of a server and the query of a probe: a refusal (P/06.6), not a field of a unit.
Who performs it — by `op`: `env_labels` — the worker (`03-worker`, the contract `env`); `label` — those who read labels by the contract:
the controller (`04-controller`), the console (`06-console`), grants by labels (`08-domain`) and the worker (`03-worker`: each label
of `LABELS` — by the alphabet); `set_write` — the console (`06-console`: the label row of a server, the labels field of a unit; the heartbeat labels
the worker writes as a comma-separated string — P/03.4 Н1.1, the family `heartbeats`; C03-PULSE-LABELS-STRING-01); `text_read` — the controller (`04-controller`) and the console (`06-console`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).

## Native outcome

The package has no separate command contract — the common rule «Vectors» of [the common acceptance README](../../acceptance/README.md)
(ACC-VECTORS-CONNECT-04, the Architect's decision 2026-10-26): the function answers with code 0 and one JSON value. `ok` — the JSON string `"ok"`, a refusal — the JSON string `"@refuse"`, otherwise a JSON value, as in `expect`.

## Vector wire

The wire of `cases.tsv` is set by the `common/labels` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

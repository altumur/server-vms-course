# Vectors: text forms of values by type (`values_by_type`)

This English text is the source; the Russian translation `ru/vectors/values-by-type/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is chapter P/06.1 ([norms](../../../06-console/spec/06.1-console.norms.md) Н1.2 `values_by_type`, `absent`; Н2 — the values of the JSON answer;
Н4 — type refusals). The participants are all who read or write unit and table rows by the manifest: `<s>controller`, `<s>worker`,
`<s>domain`, `domain`, `domainagent` (the readers of a unit row by [the catalog](../../data/catalog.tsv)), the codec of the schemas
of families [`codec.tsv`](../../data/codec.tsv) (the types `string`, `integer`, `number`, `boolean`, `array`, `null` — the
same rule), table rows (P/06.1 Н1.6: the values and stamps — by `values_by_type`), the row `sweep` (P/06.1 Н1.5: `at`).
The bytes are written by «Спецификация» (ADR-0083, stage B; review analysis of stage A 6–7, № 33); the conformance of the product is by its acceptance
against this table (ADR-0080 addendum 16).

## `cases.tsv`

UTF-8, LF, fields separated by TAB. Lines with `#` and empty lines are skipped, the first line not skipped is the header. Six fields:

| Field | Meaning |
|---|---|
| `case` | the name of the row |
| `type` | the type of the manifest field: `string`, `url`, `int`, `float`, `bool`, `list`, `json`, `blob`; `secret` — a string field with the suffix `_secret`; `list:labels` — the field of the placement labels (`placement.constraint: labels-subset`, the label alphabet — [the contract](../../contracts/labels.md)); `int:inherit` — an `int` field with `inherit` |
| `dir` | `write` — a JSON value at the input of a door → an element of the row; `read` — an element of the row → a JSON value of the answer; `both` — both directions |
| `json` | the JSON value (JSON text) — as in the request body (`write`) or the answer (`read`); `@unset` — the field is not passed (`write`) / the answer has no field (`read`); `@unreadable` — the element does not read as its type (`read`) |
| `row` | the element of the store row — **a JSON string** with the text of the element (`"5"` — the text `5`, `""` — an empty text); `@absent` — there is no element; `@refuse` — the write is refused, 400 at the door (Н4), `@refuse <word>` — with this `fault` ([the dictionary](../fault/README.md)); `@json <JSON text>` — the element is the text of a JSON array, equal by value; `@sealed` — an envelope `enc:v2:…` ([the sealing contract](../../contracts/sealing.md)) |
| `note` | where the row comes from: a rule of the norm or an acceptance step of P/06.1 (sc. — the scenario number of [the acceptance of the chapter](../../../06-console/acceptance/1/README.md)) |

## Run

A side takes a loaded manifest with a field of the needed type (`testsub2` has fields of all types, `int:inherit` — `keep_days`;
`list:labels` — `testsub.labels`) and checks the rows by its own conversion code, without HTTP:

1. **`write`, `both`** — from `json` it gets the element of the row: the text is byte for byte equal to `row`; `@absent` — there is no element;
   `@refuse` — the conversion is refused as a type refusal of Н4 (at `@refuse <word>` — with this `fault`); `@json X` — the text
   begins with `[`, parses as a JSON array and equals `X` by value (the norm does not set the whitespace inside the text);
   `@sealed` — the text begins with `enc:v2:` and opens with a ring key into the original value.
2. **`read`, `both`** — from `row` it gets the value of the answer: equal to `json` by JSON value (`1` = `1.0`; a string, a boolean and
   `null` are not equal to a number); `@unset` — the answer has no field; `@unreadable` — the element does not read as its type (at a table
   row — `{name, garbled: true}`, P/06.1 Н2); the input `@json X` is given as the text `X` as written in the cell; the input `@sealed`
   — any envelope, the answer is the mask `"***"`.

The door observes the `@refuse` refusals too: the same values in `POST`/`PUT` give 400 before the write (the scenarios named in `note`).

Who performs it — by `dir` (at `both` — each half by its own direction): reading — the readers of a unit row by
the catalog (`03-worker`, `04-controller`, `06-console`, `08-domain`, `09-agent`); writing — those who write unit and table rows:
the console (`06-console`) and the worker (`03-worker`, `worker.creates`, «Preparation of fields»); the rows with `@sealed` (seal at
the write, the mask `"***"` at the read) — only the console: the worker does not seal and opens a secret, does not mask it (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).

## Stand command `values-by-type`

Through the record `vectors` `common/values-by-type` (the single command of the common acceptance README; it or `stand.values-by-type` is enough —
ACC-VECTORS-COVERS-STAND-01) a frame per half of a row: `variant` — `write` or `read` (at `both` — two frames), `cells` — the input
columns of this half as written: at `write` — `{type, json}`, at `read` — `{type, row}`; there is no `dir` in `cells` (`variant` carries it),
the expectation is not passed (`row` at `write`, `json` at `read`); the native object below is built by the command (C-VBT-FRAME-01, the decision
of the Specification).

The key `stand` of the profile `06-console` (the section «Layout by processes» of [the common acceptance README](../../acceptance/README.md));
a template with `{input}` — the path of a file with one JSON object. The runner gives a `both` row by two independent calls `write` and
`read`; `both` never occurs in the input; the command does not get the expected result.

- **Write** — exactly `{type, direction, json}`, all rows, `direction` = `write`, `type` — the word of the column `type` (including
  `list:labels`, `int:inherit`); `json` — the original text of the cell `json` as a JSON string (the lexeme is not re-derived: `1`, `1.0`,
  `1e0`, `-0` are distinguishable) or exactly `@unset` — the field is not passed (the JSON string `"@unset"` is passed as text with quotes and
  does not match the marker). The answer is one of the closed ones: `{"status": "ok", "row": <element text as a string>}` (an empty text is
  `ok` too); `{"status": "absent"}` — there is no element (`@absent`); `{"status": "refused"}` or `{"status": "refused",
  "fault": <word>}` — a type refusal (`@refuse <word>` requires this `fault`; a bare `@refuse` neither requires nor
  forbids the field). At a secret — `{"status": "ok", "row": <envelope>, "plaintext": <value>}`: the command seals by its own
  regular procedure on a temporary test ring and by the same ring regularly opens the obtained envelope; `plaintext` is
  the result of the opening, not a copy of the input; the field `plaintext` occurs only at a secret envelope. The reconciliation: `row` — byte for byte with the text
  of the cell `row`; `@json X` — `row` begins with `[` and equals `X` by value; `@sealed` — `row` begins with `enc:v2:`,
  `plaintext` equals the value of `json`.
- **Read** — exactly `{type, direction, present, sealed, row}`, `direction` = `read`: a cell that is a JSON string — `present: true`,
  `sealed: false`, `row` — its text, decoded once; `@json X` — `row` is the text `X` as written; `@absent` —
  `present: false`, `sealed: false`, `row: null`; `@sealed` — `present: true`, `sealed: true`, `row: null`: only `secret`,
  the command itself prepares an envelope by its sealing procedure and gives it to the regular read («любой конверт» of item 2
  above). The answer is `{"status": "ok", "value": <JSON value>}` (`value: null` — the field exists with the value `null`),
  `{"status": "absent"}` (`@unset`) or `{"status": "unreadable"}` (`@unreadable`; an unreadable text is an input of the form, code 0).
  The reconciliation of `value` with the column `json` — by JSON value, as in item 2.

An input not of the form: an unknown `type`, `direction` not `write`/`read`, a missing, extra or repeated field, a wrong
field type, `json` not one JSON value and not `@unset`, another combination of `present`/`sealed`/`row`. A refusal of a value by the norm is
code 0 with `refused`, not code 2. The conversion and the choice of the field by type are a function of the side, not of the runner. stdout is exactly one JSON object and LF: the first byte `{`, after the object — LF and the end; extra fields, bytes, CRLF, whitespace around — FAIL of the row; formatting inside the object is allowed; service output — to stderr. Code 0 — computed; an input not of the form — code 2, stdout empty. There is no envelope `result` (stage C guess C06-F2-IO-02, the Architect's decision 2026-10-23).

## What the vector does not cover

The preparation of the field set at creation (passed, `inherit`, `default`, the empty form — Н1.2, sc. 01, 02, 10), the order
of refusals (Н3 step 4), the ceiling of a `json` field of 4000 bytes (Н1.4, sc. 16), address parsing and the password in it (chapter 6.2 Н1.1а, the vectors
`secret-in`), the bytes of the envelope (the vectors [`common/vectors/sealing/`](../sealing/README.md)), `fixed`,
references and `unique` (Н1.3). The cross-language notation of `float` beyond the examples is by the rule `values_by_type` of [the row check contract](../../contracts/row-check.md) «Unit row» («the shortest that restores
the number, without an exponent»), not by this table.

## Vector wire

The wire of `cases.tsv` is set by the `common/values-by-type` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

# Vectors: writing a body value into a row and canonical JSON

This English text is the source; the Russian translation `ru/vectors/requests-body/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.4 ([norms](../../spec/06.4-console.norms.md) Н1.5 `<поля тела>`: «строка — как есть, иное значение — канонический JSON (JCS, ADR-0072)»;
Н2: the `fault` of the requests door is only `too_long`). The participants are the units and tables door of
[chapter 6.1](../../spec/06.1-console.norms.md) (a field of type `json`: the value as is, the ceiling `JSON_CEILING`, `not_json`) and
the worker that writes a request itself ([chapter 3.6](../../../03-worker/spec/03.6-worker.norms.md) Н1.5: the fields of the row body
as text). The bytes are written by the Specification (ADR-0083, stage B; the rules — the Architect, 2026-10-05/06, the numbers by JCS — stage A
ADR-0083, 2026-10-18); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The package was moved from `Source/tests/testdata/requests_body.tsv` (stage A) together with lesson 6 (stage B, ADR-0083 addendum (1));
the bytes of the table are the same, including the header comment (its «М10/3», «М10/8» are the former addresses of the norms, now chapter 6.1 and
chapter 6.4; the product copy is checked against these bytes). The `fault` words of the table are from the dictionary
[`fault`](../../../common/vectors/fault/README.md) (chapter 6.1).

## `requests_body.tsv`

UTF-8, LF, fields separated by TAB. Rows with `#` and empty ones are skipped; there is no header row. Four fields in each row (the TAB
is present even with an empty `fault`). A cell is read byte for byte between TABs, nothing is unescaped: a TAB or a line feed inside
the JSON text is written the way JSON writes them in a string (`\t`, `\n`).

| Field | Value |
|---|---|
| `field` | `request` — the field `v` of the request row; `json` — the field `doc` of type `json` of a unit |
| `body` | the value as the body carries it — the JSON text exactly as sent (`5.0` — not `5`) |
| `stored` | the text that the row holds; `<absent>` — the field is not in the row; `<empty>` — an empty string |
| `fault` | empty — accepted; `too_long` — longer than `maxLength` of the schema (`request`) or `JSON_CEILING` (`json`); `not_json` — the body is not JSON (rows `json`); `<refused>` — 400 of the requests door without `fault` (rows `request`) |

## Stand

Both sides file through one stand: a family whose schema says `v: {maxLength: 32}` (the request row: `POST /<sub>/requests
{"unit": <единица>, "v": <body>}`, the field `v` of the row is read back), and the table `counters`, whose field `doc` is of type `json`
(`POST /counters {"name": …, "doc": <body>}`, the field `doc` of the unit is read back); a refusal is the `fault` of the 400 answer.

The stand manifest is `Source/tests/testdata/testsub.subsystem.yaml` with two changes and no others (a copy in the temporary
directory of the stand; the source file does not change):
- `unit.fields.doc: {type: json}`;
- `requests.schema` — `{type: object, required: [unit, v], additionalProperties: false, properties: {unit: {type:
  string}, v: {maxLength: 32}}}` (`v` without `type`: the length is by the written text, the rule below); `valid_for: 30`,
  `most_valid: 600` — as in `testsub`.

Before the table, the unit `c1` is created; the requests are filed to it. Processes other than the store and the console are not started.
The row is read by a role with the right to read `testsub/` through the store door; a refusal is 400 with `fault` (or without it) and no
row. A repeated filing of a `json` row (below) is `PUT /counters/<name> {"doc": <прочитанное значение>}` (an edit of chapter 6.1),
then the field `doc` is compared again. The stand is one fresh stand for the whole table (analysis of the reading of the «cammeta-acceptance» commits
2026-10-20: preparation is the data of the package, not a choice of the runner).


For this store+console HTTP fixture, set both `OBJECTS=file://` and `PLATFORM_OBJECTS=file://` explicitly before the console starts. By [the object client contract](../../../common/contracts/object-client.md) Address, bare `file://` resolves to `<PLATFORM_DIR>/objects`. The role launch command creates this real local root with the stand permissions before startup, as in [the common stand](../../../common/acceptance/README.md); the console reads the actual directory, not a canned empty answer. This makes the configured local object source available to GET /counters while keeping the fixture to store+console.

This is the fixture's selected configuration, not a fallback of a running process: with configstore and no OBJECTS setting the normal source remains cluster://; an unconfirmed first object read still gives 503. No resource process or pure native console command is added. The native worker rows do not use this HTTP fixture. The 77 table rows, refusal checks and all 21 accepted-json round trips are unchanged.

## Rules

The writing rules are the header comment of the table (a string, `true`/`false`, a top-level `null`, a number by JCS, the length by the
written text, canonical JSON of a dictionary and a list, the value of a `json` field as is, the ceiling `JSON_CEILING` 4000 bytes
of UTF-8, not JSON — a refusal without repair). The round trip: a value read and filed again is written the same way, byte for
byte — both sides file each accepted `json` row a second time with the read value.

## Run

The side files `body` by the kind `field` through the stand and compares `stored` (or the refusal and `fault`) byte for byte. One
canonical function per side — at the requests door, at the units door and at the worker. Who executes it is by `field`: `json` — the units
door of the console (`06-console`, chapter 6.1); `request` — the requests door of the console (`06-console`) and the worker that writes a request
itself (`03-worker`, chapter 3.6 Н1.5; with its own body-writing function, without the console stand) (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

For the worker (`03-worker`, the rows `request`, 52: 46 accepted, 1 `too_long`, 5 `<refused>`) the input of the single command `vectors` is
`cells: {body}`, the cell as is; the native outcome is code 0 and `{"stored": <строка>}` for an accepted row (`<empty>` — `""`)
or `{"fault": "too_long"}` or `{"fault": "<refused>"}` — by the column `fault`; the comparison is by value. `too_long` for the worker
is judged not by the writing function but by the check of the body against `requests.schema` before filing (P/03.6 Н1.5) — by the schema of the package stand
(`v: {maxLength: 32}`, the length by the written text); a refusal by the schema is the outcome `refused` of the norm, in the vector it is distinguished
by the word of the column `fault` (ACC-REQUESTS-BODY-WORKER-01, the Architect's decision of 2026-10-27).

## Vector wire

The wire of `requests_body.tsv` is set by the `06-console/requests-body` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

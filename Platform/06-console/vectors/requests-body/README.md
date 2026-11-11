# Vectors: writing a body value into a row and canonical JSON

This English text is the source; the Russian translation `ru/vectors/requests-body/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter P/06.4 ([norms](../../spec/06.4-console.norms.md) N1.5 `<body fields>`: «row — as is, another value — canonical JSON (JCS)»;
N2: the `fault` of the requests door is only `too_long`). The participants are the units and tables door of
[chapter 6.1](../../spec/06.1-console.norms.md) (a field of type `json`: the value as is, the ceiling `JSON_CEILING`, `not_json`) and
the worker that writes a request itself ([chapter 3.6](../../../03-worker/spec/03.6-worker.norms.md) N1.5: the fields of the row body
as text). The bytes are written by the Specification; the conformance of the product is by its acceptance against this table.

The product copy is checked against the table bytes. The `fault` words of the table are from the dictionary
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
{"unit": <unit>, "v": <body>}`, the field `v` of the row is read back), and the table `counters`, whose field `doc` is of type `json`
(`POST /counters {"name": …, "doc": <body>}`, the field `doc` of the unit is read back); a refusal is the `fault` of the 400 answer.

The stand manifest is `Platform/common/data/testsub/testsub.subsystem.yaml` with two changes and no others (a copy in the temporary
directory of the stand; the source file does not change):
- `unit.fields.doc: {type: json}`;
- `requests.schema` — `{type: object, required: [unit, v], additionalProperties: false, properties: {unit: {type:
  string}, v: {maxLength: 32}}}` (`v` without `type`: the length is by the written text, the rule below); `valid_for: 30`,
  `most_valid: 600` — as in `testsub`.

Before the table, the unit `c1` is created; the requests are filed to it. Processes other than the store and the console are not started.
The row is read by a role with the right to read `testsub/` through the store door; a refusal is 400 with `fault` (or without it) and no
row. A repeated filing of a `json` row (below) is `PUT /counters/<name> {"doc": <read value>}` (an edit of chapter 6.1),
then the field `doc` is compared again. The stand is one fresh stand for the whole table (preparation is the data of the package, not a choice of the runner).


For this store+console HTTP fixture, set both `OBJECTS=file://` and `PLATFORM_OBJECTS=file://` explicitly before the console starts. By [the object client contract](../../../common/contracts/object-client.md) Address, bare `file://` resolves to `<PLATFORM_DIR>/objects`. The role launch command creates this real local root with the stand permissions before startup, as in [the common stand](../../../common/acceptance/README.md); the console reads the actual directory, not a canned empty answer. This makes the configured local object source available to GET /counters while keeping the fixture to store+console.

This is the fixture's selected configuration, not a fallback of a running process: with configstore and no OBJECTS setting the normal source remains cluster://; an unconfirmed first object read still gives 503. No resource process or pure native console command is added. The native worker rows do not use this HTTP fixture. The 77 table rows, refusal checks and all 21 accepted-json round trips are unchanged.

## Rules

In the header of `requests_body.tsv` (judge-only: vector inputs and expectations), `M10/3` and `M10/8` are internal judge labels for chapters P/06.1 and P/06.4 respectively. The writing rules are:

```text
  scalars in a request row
    true / false      the JSON text: true, false (not Python's True)
    null              at the top level of a `json` field: the field is ABSENT from the row (P/06.1 N1.2: «null value —
                      absent»); at the top level of a request field: the JSON text null (P/06.4 N1.5 «another value —
                      canonical JSON»); an empty string is the empty string; inside a JSON value a null stays null
    a number          JCS (RFC 8785; P/06.4 N1.5 «another value — canonical JSON»): ES6
                      Number.prototype.toString of the IEEE-754 double — a whole value in integer digits below 1e21
                      (5, not 5.0; -0 is 0), otherwise the shortest form that reads back as the same double, with an
                      exponent below 1e-6 and from 1e21 (1e-7, 1e+21); digits past the double are rounded
                      (9007199254740993 → 9007199254740992); one past float64 (1e400) is refused by the body's parse

    a string          as it is, unquoted, its own quotes its own; a string that looks like a number or a boolean
                      stays the string; what type a field is, the schema says, not the text
    length            the schema's maxLength over the WRITTEN text (1e40 is written 1e+40: 5 characters); the writing
                      function does not judge length
  the canonical JSON (JCS) — a dict or a list in a request row, and any value of a `json` field: compact,
  a dict's keys sorted by UTF-16 code units (U+1F600 before U+FB33), UTF-8 as it is (no \u escaping; no HTML escaping of < > &; / not escaped), U+2028/2029 raw, control
  characters as json.dumps(ensure_ascii=False) writes them (\b \f \n \r \t short, the rest \u00xx lowercase),
  numbers inside by the scalar rule, a null inside stays null. A `json` field's value is taken AS IT IS: a string
  is a string document ("s" is stored "s"), never parsed again; the page parses its own text box before it sends,
  its «not JSON» under the box; not_json at a `json` field is only a body that is not JSON. Round trip:
  the value read back and filed again is stored the same, byte for byte — both tests file every taken `json` row a
  second time with the value they read. The ceiling of a `json` field: its canonical text's BYTES of UTF-8,
  JSON_CEILING 4000: too_long. One canonical function each side.
  A body that is not UTF-8, holds a lone surrogate or a number past float64 is not JSON: at the unit and table doors a
  400 with `fault: not_json` (P/06.1 N3, N4; words of fault.tsv); at the request door a 400 RequestError WITHOUT `fault`
  — that door's only fault is too_long (P/06.4 N2, N4).
  not JSON is refused, never repaired: NaN, Infinity, a lone surrogate (\ud800) — not_json, not U+FFFD.
```

## Run

The side files `body` by the kind `field` through the stand and compares `stored` (or the refusal and `fault`) byte for byte. One
canonical function per side — at the requests door, at the units door and at the worker. Who executes it is by `field`: `json` — the units
door of the console (`06-console`, chapter 6.1); `request` — the requests door of the console (`06-console`) and the worker that writes a request
itself (`03-worker`, chapter 3.6 N1.5; with its own body-writing function, without the console stand).

For the worker (`03-worker`, the rows `request`, 52: 46 accepted, 1 `too_long`, 5 `<refused>`) the input of the single command `vectors` is
`cells: {body}`, the cell as is; the native outcome is code 0 and `{"stored": <row>}` for an accepted row (`<empty>` — `""`)
or `{"fault": "too_long"}` or `{"fault": "<refused>"}` — by the column `fault`; the comparison is by value. `too_long` for the worker
is judged not by the writing function but by the check of the body against `requests.schema` before filing (P/03.6 N1.5) — by the schema of the package stand
(`v: {maxLength: 32}`, the length by the written text); a refusal by the schema is the outcome `refused` of the norm, in the vector it is distinguished
by the word of the column `fault`.

## Vector wire

The wire of `requests_body.tsv` (judge-only: checking material outside M) is set by the `06-console/requests-body` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

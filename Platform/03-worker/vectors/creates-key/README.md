# Vectors: the id of an order row (`worker.creates[].key`)

This English text is the source; the Russian translation `ru/vectors/creates-key/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/03.6 ([norms](../../spec/03.6-worker.norms.md) Н1.6 `id`, `key`; ADR-0091 item 1). The participant is
`<s>worker` of the orderer (the worker library). The writing of values by types is [P/06.1](../../../06-console/spec/06.1-console.norms.md)
Н1.2 `values_by_type` (the vectors [`values-by-type`](../../../common/vectors/values-by-type/README.md)). The bytes are written by the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

| Field | Value |
|---|---|
| `case` | the name of the row |
| `input` | a JSON object: `customer` — the name of the orderer subsystem; `key` — the template `worker.creates[].key`; `fields` — field → `{type, value}`: the type of the field of the addressee (`string`, `url`, `int`, `float`, `bool`) and the JSON value, as the logic of the orderer gives it |
| `expect` | the id of the order row — byte for byte |
| `note` | the rule |

## Run

The side builds the id with its own library code, without a store: each `{поле}` of the template is the writing of the value by `values_by_type`
(the row check contract `values_by_type`; `float` — its choice rule), then each UTF-8 byte outside `A–Z a–z 0–9 _ . ~` is `%XX` with hex digits
in upper case; between the substitutions — the `-` of the template; in front — `<customer>-`. The result is compared with `expect`.
Pairs of rows with the same `pair` in `note` check that different values give different ids.
Who executes it is the orderer worker (`03-worker`: the library builds the id, P/03.6 Н1.6 `id`, `key`, Н3 «order»). The console (`06-console`) does not build the id: the door checks only the prefix of the orderer and the invariance of the `key` fields of a ready row (P/06.1 Н1.6 `made_prefix`, `made_key`) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Stand command

`creates-key` is the key `stand` of the profile `03-worker` (the section «Layout by processes» of [the common acceptance README](../../../common/acceptance/README.md)):
a template with `{input}` — the path of the file into which the runner writes the cell `input` of the row byte for byte; stdout — the UTF-8 bytes of the id exactly
as `expect`, without a line feed at the end and without a JSON wrapper; code 0. An input not by the form of this README — code 2 (`@exit 2`).
Another code or extra bytes — FAIL of the row.

# Vectors: the step package key and the expected version of a step

This English text is the source; the Russian translation `ru/vectors/op-step/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.9 ([norms](../../spec/06.9-console.norms.md) N1.4, N2 «Пакет шага»; ADR-0095). The participants are the console leader (the expected version in the step call) and the subsystem (the step package key). The bytes are written by the Specification; the values were computed by the text of the norm, not by the code of implementations.
There is no dry run by an implementation.

## `key.tsv`

UTF-8, LF, fields separated by TAB; the first row is the header `case<TAB>id<TAB>i<TAB>expect<TAB>note`.

| Field | Value |
|---|---|
| `id` | the operation id, a string |
| `i` | the step number, decimal |
| `expect` | `step_key(id, i)`: hex SHA-256 of `UTF-8(id) ‖ 0x00 ‖ UTF-8(decimal notation of i)`, 64 lowercase characters |

6 rows. The separator `0x00` keeps a pair `(id, i)` from coinciding with another pair when concatenated.

## `expected.tsv`

UTF-8, LF, fields separated by TAB; the first row is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object:

| Field | Value |
|---|---|
| `steps` | the steps of the operation in order: `{root, expected}`, `expected` — as in the step row |
| `done` | the outcomes by step number, the key is a decimal string: `{state, versions?}` |
| `i` | the step number for which the value is needed |

**Output** — the JSON value `expected(i)` of N1.4, in `expect` of the table as JSON text: `versions` of the outcome `ok` with the greatest number less than `i` and the same `root`, otherwise `expected` of step `i`. The comparison is JSON by value. 10 rows: without earlier steps, `ok`, `fail`, `cancel`, `ok → fail → set`, two `ok`, a foreign root, two objects of one root, an outcome after `i`, a copy of the step `retry-failed`.

## Run

The side checks both tables with its own function: the command is the entry `vectors/06-console/op-step` of the profile (the section «Layout by processes» of [the common acceptance README](../../../common/acceptance/README.md)). The native outcome is code 0 and the value `expect`; an input not in form — code 2. The form of the command is the same as for the neighbouring packages.

## Vector wire

The wire of `expected.tsv`, `key.tsv` is set by the `06-console/op-step` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

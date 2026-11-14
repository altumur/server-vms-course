# Vectors: the common row check: case data and coverage

This English text is the source; the Russian translation `ru/vectors/row-check/README.cases.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter P/06.1 of the console through [the row check contract](../../contracts/row-check.md) (the guess of stage C W03-E07,
the Architect's decision of 2026-10-23). The participants are the units door of the console ([P/06.1](../../../06-console/spec/06.1-console.norms.md)
N3 «create», «edit») and the customer's library of the worker ([P/03.6](../../../03-worker/spec/03.6-worker.norms.md) N1.6,
N3 «order»): one table for both sides. The bytes are written by «Specification». The cases are taken from the norms of the contract and the steps
of the acceptance of P/06.1 (sc. 15, 16, 18, 20 — in the column `note`).

The manifests are `testsub` and `testsub2` (`Platform/common/data/testsub/*.subsystem.yaml`), loaded together: the catalogue of manifests
of both. `testsub2/tallies` is the table that the library of `testsub` orders (`worker.creates`), so most
cases are on it. In the input of the single command `vectors` the manifests are `files` with the keys
`testsub.subsystem.yaml` and `testsub2.subsystem.yaml` (the bytes of these files of the export); `cells` — `unit`, `op`, `body`,
`stored`, `rows` (the inventory C04/C06-NEXT-167, the Architect's decision of 2026-10-27).

The `manifest` input column selects the bytes supplied under `testsub2.subsystem.yaml`. Ordinary rows select
`Platform/common/data/testsub/testsub2.subsystem.yaml`. Rows that need required inheritance, an integer weight without a default,
or a unit as a reference target select the isolated [fixture](fixtures/testsub2.subsystem.yaml). Its subsystem name and units table remain
`testsub2/tallies`; its `name` and `of` fields are required and inherited, `weight` has no default and is declared as
`placement.weight.field`, and unit and table `link` fields refer to the units table. This fixture is judge input only; the common manifests are unchanged.
`manifest` selects input bytes in the wire and is not passed as an algorithm cell. Expected answers never select fixture bytes.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is the header. Fourteen fields:

| Field | Meaning |
|---|---|
| `case` | the name of the case, unique |
| `unit` | `<subsystem>/<rows>` — the units table of a manifest, or `<subsystem>/<table>` — a table of a manifest (a table row: `P1` by `table_platform_fields`, the preparation — «Table row» of the contract) |
| `op` | `create` — creation (`P1`–`P5` of the contract), `edit` — an edit (`R1`–`R3`) |
| `body` | the passed fields — a JSON object; numbers are lexemes as written (`1e2`, `-0`) |
| `stored` | for `edit` — the read row; for `create` — the tombstone over which one creates; empty — there is no row. A JSON object in the form of a unit row (the elements are strings) |
| `rows` | the other rows of the store that the check reads: a JSON object `{key: row}`; `"@garbled"` instead of a row — the row is not read by its form |
| `expect` | `ok` or `refused` |
| `word` | for `refused` — the `fault` from the dictionary [`../fault/`](../fault/README.md), if the refusal carries it; otherwise the class of the row «Refusals» of the contract: `platform_field`, `unknown_field`, `blob`, `enum`, `type`, `labels`, `bad_id`, `fixed`, `required`; for `ok` empty |
| `field` | the field that the refusal names (the first in the order of the contract); for `unknown_field` — all unknown names in ascending byte order separated by commas (RC-10) |
| `step` | the step of the contract at which the refusal occurs |
| `row` | for `ok` — the part of the prepared row that is compared: a JSON object `{element: text}`, `"@absent"` — there is no element; empty — not compared. The text of a list in the form of a JSON array is compared by JSON value (as `@json` of the vectors [`values-by-type`](../values-by-type/README.md)) |
| `manifest` | input-only path from the export root to the manifest supplied as `testsub2.subsystem.yaml`; it selects bytes in `files`, not an algorithm cell |
| `credential_fields` | optional expected JSON array of credential-field names for `bad_url`; compared as a set; `[]` requires no names; an empty cell leaves this list unjudged |
| `note` | a rule of the contract or a step of the acceptance of P/06.1 |

116 cases: 36 `ok`, 80 `refused`. Existing label-repeat and empty-unique cases retain their input values and outcomes.

| Boundary | Cases and observation |
|---|---|
| Empty matching elements | `must_match_empty_both_*` and `reverse_must_match_empty_both_*`: direct and reverse checks refuse empty against empty at creation and edit; nonempty-equal controls pass |
| Required inheritance | `required_inherit_{name,of}_{null,missing}`: omitted and null inherited fields are not given; P4 refuses, including an absent named-id source; `required_inherit_given` passes |
| URL refusal fields | `url_{scheme,no_host,no_path}_credentials`: parsed-address Schemes refusals have `credential_fields: []`, despite credential findings; `url_a15_*` cover secret, login, both and an unparsable address |
| Numeric type refusal | `{int,float}_as_{bool,array,object}` receive `type`; `float_as_numeric_string` receives `not_number`, as do the existing numeric-string and int-lexeme/range cases |
| Reverse unreadable rows | `reverse_garbled`, `direct_before_reverse_garbled`, `reverse_key_*` and `reverse_unit_*`: unreadability is found at the referring-family check in RC-15 order, after direct checks; competing errors distinguish row-key and unit-before-table order |
| Weight presence | `weight_absent_empty_form`: omitted weight without default prepares `"0"` and passes; `weight_explicit_zero` refuses and `weight_explicit_one` passes |
| State number range | `state.tsv`: positive and negative overflow in result values and overflow in cursor values are unreadable; large finite controls act |

## Run

A side performs its common row check: the preparation of the fields and the checks `P1`–`P5` (`create`) or `R1`–`R3` (`edit`) over
`body`, `stored` and `rows`. Compared are the outcome, the class or `fault`, the field and, for `ok`, the elements of `row`. At the door the class is read
from the refusal: the word `error` by P/06.1 N2 «Refusal: `error` and `field`» (the class `unknown_field` — the word `unknown field`; at a table row
`platform_field` — also `unknown field`), the field — `field` without the leading `/` (for `unknown_field` — the first name); the text of `detail` is not compared; at the library — the outcome `refused`
together with the reason that the library writes to the log. The library gives the fields of its order: the id source field — as a ready id
(P/03.6 N1.6), `born` and `made` it sets itself and does not pass them to the check.
Who performs: the units door of the console (`06-console`) — all rows; the customer's library (`03-worker`) — the rows with `unit`
`testsub2/tallies` (`create` and `edit`): this is the table that `testsub` orders (`worker.creates`), the library writes no other
tables (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-26).

The native outcome of `cases.tsv` is code 0 and one JSON object: `ok` — `{"result": "ok", "row": {…}}`, `row` — the prepared row
`{element: text}` (no element — no key); `refused` — `{"result": "refused", "word": "<fault or class>", "field": "<field>"}`
(no field — no key `field`). Compared are `result`, `word`, `field` and for `ok` — the elements named in the column `row`
(`@absent` — no key; a list in the form of a JSON array — by value). For `bad_url`, the native `credential_fields` array names fields by A15; it is empty for a refusal by Schemes. It is compared as a set only when its expectation cell is nonempty; earlier cases leave it unjudged. The column `step` is not compared — it is for a human: the step
of the contract (C06-VECTOR-ROWCHECK-WIRE-168-11, the Architect's decision of 2026-10-27; the input and the algorithm do not change).

## `state.tsv`

The state of a unit is the row check contract «Unit state» (`acts`, `unreadable`); the form of the row is [`state.schema.json`](../../../03-worker/data/state.schema.json), the outcomes are [`state.outcomes.tsv`](../../../03-worker/data/state.outcomes.tsv)
(STATE169-VECTORS-01, the Architect's decision of 2026-10-27). UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped;
the first line without `#` is the header `case<TAB>name<TAB>unit<TAB>state<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `name` | the name of the state — a JSON string: `result` or `cursor` from `unit.state` of the manifest `testsub2` (the unit is `testsub2/tallies`) |
| `unit` | the unit row as read: an object of elements (`born`, `revision`; `deleted: "true"` — a tombstone) or `"@absent"` — there is no row |
| `state` | the row `testsub2/state/<name>/<id>` as read: an object of elements (`born`, `revision`, `epoch`, `value` — JSON text) or `"@absent"` |
| `expect` | `{acts, unreadable}` and for an acting one `value` — the parsed value; JSON by value |
| `note` | a rule of the contract |

The expectations are the judge of the family `state` in the reader mode by the text of the row (`x-encoding: jcs` — JCS is checked only by the writer),
then `value` by the schema `unit.state.<name>` of the manifest; `acts` — the unit row is live, the `born` are equal, the `revision` are equal (for `cursor`
not reconciled: the contract `acts`, P/03.6 N1.7 `cursor`; C170-STATE-CURSOR-01), the epoch is not reconciled. 29 rows: 8 act, 15 are unreadable, 6 are readable and do not act. Strict JSON parsing of `value` rejects numbers outside finite binary64 even when the schema accepts a number; the reader's tolerance of non-JCS spacing does not relax this range.
The input of the single command `vectors` is `cells` `name`, `unit`, `state`; `files` — `testsub2.subsystem.yaml` (the schemas of `unit.state`).
The native outcome is code 0 and the object `expect` (the general rule «Vectors» of the common acceptance README).

Who performs is everyone whose norm judges «the state is effective»: the holder of the unit (`03-worker`, P/03.6 N1.7 — writes anew
a non-acting one), the controller (`04-controller`, P/04 N1.3 `retire_when`, N1.3a `state` and the count `snapshot_state_garbled`) and
the console (`06-console`, P/06.1 N2 «State in the answer») — all rows (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

A current state born is required: 32 lowercase hex. born-empty-both and born-empty-state-only keep their input bytes and receive the existing unreadable/nonacting result, without an empty-life substitution.

## What the vector does not cover

Weight presence and its threshold, direct and reverse `must_match` (including unit targets), and the tested first-refusal boundaries of RC-15
are covered above. The full subsystem-name, table-name and manifest-field order of RC-15, and a reference of a row to itself (RC-16),
remain reading or P/06.1 scenario checks. The claim, the number, the write and the HTTP codes of the door are the acceptance of P/06.1; `made_prefix`, `made_key` and the secrets of the door too. A table row
(the contract, «Preparation of fields» — «Table row») and the ring boundary (ibid.) — by reading and by the scenarios of P/06.1 (tables) and
P/06.2: the table rows are `table_*` (`testsub2/shelves`: the preparation and the platform fields of a table, C06-ROWCHECK-TABLE-FIELDS-707-01),
the full replacement and the secrets of a table, the states of the ring — by reading: they are not in the input (C06-ROWCHECK-TABLE-33-01, C06-ROWCHECK-DEV-01).
A table field with a name from the `platform_fields` of a unit — by reading: the tables of `testsub`/`testsub2` have no such field.

## Vector wire

The wire of `cases.tsv`, `state.tsv` is set by the `common/row-check` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

## Source metadata

This English text is the source; the Russian translation `ru/vectors/row-check/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Source file `vectors/row-check/README.md`: [README](README.md).

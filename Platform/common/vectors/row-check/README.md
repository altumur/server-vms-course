# Vectors: the common row check

This English text is the source; the Russian translation `ru/vectors/row-check/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

Chapter P/06.1 of the console owns the [row check contract](../../contracts/row-check.md). Its consumers are the console units door ([P/06.1](../../../06-console/spec/06.1-console.norms.md), N3 create and edit) and the worker customer's library ([P/03.6](../../../03-worker/spec/03.6-worker.norms.md), N1.6 and N3 order). Both sides execute their common row check.

## Run

The function prepares fields and checks `P1`–`P5` for `create` or `R1`–`R3` for `edit` over these input cells:

| Cell | Meaning |
|---|---|
| `unit` | `<subsystem>/<rows>` for a manifest units table, or `<subsystem>/<table>` for a manifest table; table rows use `table_platform_fields` and the contract's table-row preparation |
| `op` | `create` or `edit` |
| `body` | passed fields as a JSON object; numeric lexemes stay as passed |
| `stored` | for edit, the row read; for create, the tombstone over which creation occurs; empty means no row; row elements are strings |
| `rows` | other store rows read by the check, a JSON object `{key: row}`; `"@garbled"` denotes a row unreadable by its form |

The `vectors` command receives the manifests together in `files` under `testsub.subsystem.yaml` and `testsub2.subsystem.yaml`; these are the exact bytes of the fixtures selected by the wire. The library supplies its order fields: the id source field is a ready id; it sets `born` and `made` itself and does not pass them to the check.

## Row-check native output

Exit code 0 and one JSON object: success is `{"result": "ok", "row": {…}}`, where `row` is the prepared `{element: text}` row and an absent element has no key. Refusal is `{"result": "refused", "word": "<fault or class>", "field": "<field>"}`; an absent field has no `field` key. Refusal words and field order follow the contract; `fault` comes from [the fault dictionary](../fault/README.md), otherwise the class is `platform_field`, `unknown_field`, `blob`, `enum`, `type`, `labels`, `bad_id`, `fixed` or `required`.

A `bad_url` refusal additionally returns `credential_fields`, an array of strings naming the credential fields carried by
its diagnostic under A15 of the [address contract](../../contracts/url-credentials.md). A parsed address refused by «Schemes»
returns `[]`, even if it contains credentials. This is the diagnostic's actual selection of field names, never the address or its
parts; their order is not judged. It does not replace `field`.

At the door, the class is read from `error` under P/06.1 N2; `unknown_field` is `unknown field`, and a table row's `platform_field` is also `unknown field`. The field is `field` without its leading `/`; for unknown names the function names all in ascending byte order separated by commas, while the door names the first. The text of `detail` is not compared. At the library, the observation is `refused` together with the reason written to the log.

The judge compares `result`, `word`, `field` and the selected elements of `row`: `@absent` means no key; list text encoded as a JSON array is compared by value. Where a credential-field expectation is provided, `credential_fields` is compared as a set; an empty expectation cell means that this field is not compared. The contract-step annotation is for a human and is not compared. Expectation columns never enter the call.

## `state.tsv`

The contract's «Unit state» defines `acts` and `unreadable`. The row form is [state.schema.json](../../../03-worker/data/state.schema.json), with [family outcomes](../../../03-worker/data/state.outcomes.tsv). Input cells are `name` (a JSON string naming a manifest `unit.state` entry), `unit` (the row read, or `"@absent"`) and `state` (the state row read, or `"@absent"`); `files` supplies `testsub2.subsystem.yaml` for the `unit.state` schemas. Unit row elements include `born`, `revision` and the tombstone `deleted: "true"`; state row elements include `born`, `revision`, `epoch` and `value` as JSON text.

The native result is exit code 0 and `{acts, unreadable}`, plus parsed `value` for an acting state, compared as JSON by value. The family is read by row text; JCS is checked only by the writer. The manifest schema checks `value`. A current state `born` is required and is 32 lowercase hex; the reader does not substitute an empty life.

## Who performs and checks outside the function

The console units door (`06-console`) executes all row checks. The worker customer's library (`03-worker`) executes checks for the table its manifest's `worker.creates` declares, for create and edit; it writes no other tables. The worker, controller and console execute state checks whenever their norms judge whether a state is effective: P/03.6 N1.7, P/04 N1.3 and N1.3a, and P/06.1 N2 respectively. A role executes the function its norm calls.

The function does not cover the claim, number, write, HTTP codes, `made_prefix`, `made_key` or door secrets. Self-references, full table replacement, table secrets, ring boundaries and table fields named like unit platform fields also need the contract's reading or separate acceptance checks. Concrete coverage and omissions are recorded with the cases.

## Vector wire

The public `table` selector is `cases.tsv` for a row check and `state.tsv` for a state check (judge-only: `cases.tsv`, `state.tsv`).

The `common/row-check` rows of [the single form](../wire.tsv) (judge-only: `wire.tsv`) bind headers, inputs, fixtures, native framing and comparison; [wire grammar](../wire.md) defines the frame. Layout is an excluded function declaration, never proof that its separate acceptance ran.

Concrete rows, case-to-refusal mappings, expected answers and coverage are in [case data and coverage](README.cases.md) (judge-only: `README.cases.md`).

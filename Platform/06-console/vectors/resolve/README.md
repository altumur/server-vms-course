# Vectors of the value on read

This English text is the source; the Russian translation `ru/vectors/resolve/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

Vectors of the function `resolve(field, unit, domain)` of the cluster console — the value of a shared field for a unit on read: the unit →
the domain → `inherit` of the manifest; a document field and a grouping field come only from the domain. The owner is lesson P/06, chapter 6.7 of the late
layer ([P/06.7](../../spec/06.7-console.norms.md) N1.14, N3 `resolve`, N5 `resolve`); it is executed by the cluster console at the door
`GET /domain/shared/<sub>`. The declaration `domain.shared` and `merge` are [P/02.1 N1.2b](../../../02-installer/spec/02.1-installer.norms.md),
the shared document is [P/08.9](../../../08-domain/spec/08.9-domain.norms.md) N1.2. The bytes are written by the Specification;
the conformance of the product is by its acceptance against this table.

`case` is the case name; `expect` is the expected output. The table is the only source of these cases.

## Run

Without a stand: the function of the implementation receives the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output or
`@exit 2` (an input not in form, P/06.7 N5 `exit`: for `resolve` `term`, `rev` not integers 1 … 2^53 − 1, an empty `field.name`, an unknown
`field.type` or `merge`, with `merge: union` any of the three values not a list of strings, the value `group_by` not a list, no `domain`
or `domain` without `value`, `unit` or `domain.value` `null` with `union`, an extra field, a field without `inherit`, not `document` and
not `group_by` — the full list is there).
The other cases of code 2 are by reading (N5). The exit codes follow the principle of the «Domain stand» of the common acceptance
README («Command exit codes-vectors M11»: `field` and `domain` are the trusted input of the caller, code 2).

## Files

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header; `note` is the scenario and step
of the acceptance M11.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv) (judge-only: checking material outside M), 14 rows: 10 computed, 4 `@exit 2` | `input` — the input of the command `resolve` as JSON text (`field` — `{name, type, inherit?, merge?, document?, group_by?}`, `unit` — the value of the unit row, no key — no value, `domain` — `{term, rev, value}` or `null`) → `expect`: `{"value":…,"from":…}` — own (`unit`), of the domain (`domain term T rev R`), of the manifest (`manifest`), the union `union` (`unit + domain term T rev R`), a document and its absence (`none`), `override` for a list; `{"groups":…,"from":…}` — a grouping field |

On a divergence
the norm is right, the vector is corrected by the Specification.

## Vector wire

The wire of `cases.tsv` (judge-only: checking material outside M) is set by the `06-console/resolve` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

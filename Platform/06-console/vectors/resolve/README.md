# Vectors of the value on read

This English text is the source; the Russian translation `ru/vectors/resolve/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Vectors of the function `resolve(field, unit, domain)` of the cluster console — the value of a shared field for a unit on read: the unit →
the domain → `inherit` of the manifest; a document field and a grouping field come only from the domain. The owner is lesson P/06, chapter 6.7 of the late
layer ([P/06.7](../../spec/06.7-console.norms.md) Н1.14, Н3 `resolve`, Н5 `resolve`); it is executed by the cluster console at the door
`GET /domain/shared/<sub>`. The declaration `domain.shared` and `merge` are [P/02.1 Н1.2б](../../../02-installer/spec/02.1-installer.norms.md),
the shared document is [P/08.9](../../../08-domain/spec/08.9-domain.norms.md) Н1.2. The bytes are written by the Specification (ADR-0083);
the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `resolve` of the acceptance М11/11 (`inputs/resolve-*.json`, sc. 03) without a change of bytes: only
the spaces and line feeds outside JSON strings were removed; `case` is the name of the input file; the expectation `ok <JSON>` is the cell `expect` (the plan of
the move of lesson 8, § 3, V1; the Architect's decision on the plans 8–10, ADR-0083 addendum (14) item 17). Scenario 03 of the acceptance М11/11 and
its inputs were removed by the move of lesson 10: the table is the only source of these cases.

## Run

Without a stand: the function of the implementation receives the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output or
`@exit 2` (an input not in form, P/06.7 Н5 `exit`: for `resolve` `term`, `rev` not integers 1 … 2^53 − 1, an empty `field.name`, an unknown
`field.type` or `merge`, with `merge: union` any of the three values not a list of strings, the value `group_by` not a list, no `domain`
or `domain` without `value`, `unit` or `domain.value` `null` with `union`, an extra field, a field without `inherit`, not `document` and
not `group_by` (C06-RESOLVE-ABSENT-INHERIT-91-01) — the full list is there; review analysis of
stage B 8–10, № 22: M-18). There are four rows `@exit 2` in the table
(`resolve-11-term-zero`, `resolve-12-no-inherit`, `resolve-13-union-not-string`, `resolve-14-rev-over`; C06-RESOLVE-UNION-FORM-01); the other cases of code 2 are by reading (Н5). The exit codes follow the principle of the «Стенда домена» of the common acceptance
README («Коды выхода команд-векторов М11»: `field` and `domain` are the trusted input of the caller, code 2).

## Files

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header; `note` is the scenario and step
of the acceptance М11.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 14 rows: 10 computed, 4 `@exit 2` | `input` — the input of the command `resolve` as JSON text (`field` — `{name, type, inherit?, merge?, document?, group_by?}`, `unit` — the value of the unit row, no key — no value, `domain` — `{term, rev, value}` or `null`) → `expect`: `{"value":…,"from":…}` — own (`unit`), of the domain (`domain term T rev R`), of the manifest (`manifest`), the union `union` (`unit + domain term T rev R`), a document and its absence (`none`), `override` for a list; `{"groups":…,"from":…}` — a grouping field |

The vectors were checked by the runs of the implementations of the acceptance М11/11 (run 41, reconciliation М11 09–12) and by the text of the norms; on a divergence
the norm is right, the vector is corrected by the Specification.

## Source log

The rows of `corrections.tsv` of the acceptance М11/11 about sc. 03 (the paths and numbers are the former ones, they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)):

| date | sample | fix |
|---|---|---|
| 2026-10-19 | 03-resolve 11, 04-alarms 15 | the expectation @exit 2 (the dictionary М10/01, the Architect's decision on the reconciliation М11, H14): the form of a trusted input — code 2, for both implementations by the norm |
| 2026-10-20 | the move | sc. 03 (11 steps) from М11/11 — the rows of this table (stage B; the plan of the move of lesson 8, § 3, appendix) |

## Vector wire

The wire of `cases.tsv` is set by the `06-console/resolve` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

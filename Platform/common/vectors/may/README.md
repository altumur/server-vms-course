# Vectors of the right by grants

This English text is the source; the Russian translation `ru/vectors/may/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the right contract](../../contracts/may.md): the function `may` — the right of a person by the grant lines (rank, scope,
the term of the line, the age of the copy, a disabled person, a break-glass session). The owner is lesson P/08, chapter 8.4; it is performed by the gate consoles
of a cluster ([P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.3, chapter 6.7), by the consoles of the domain (lesson 10) and by the process
`domain` (8.4) (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 1; the review analysis of stage A 8–10). The bytes are written by
«Specification» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `may` of the acceptance of M11/9 (`inputs/may-*.json`, sc. 07) without a change of values: the JSON
of the input is in one line, the order of keys and the lexemes of numbers are as in the file; `case` is the name of the input file. One exception is
`may-24-unit-id-not-grammar`: `"labels": []` was added to the unit of the input (the Architect's decision of 2026-10-20): a unit
`{sub, id}` without `labels` is itself an input not of the form (`unit` is `{sub, id, labels, about?}`), and `@exit 2` would not distinguish an id
of a scope `unit:` not by the grammar from a unit without labels. Sc. 07 of the acceptance of M11/9 and its inputs were removed by the move of lesson 8 (the Architect's
decision of 2026-10-20, ADR-0083 addendum (14) item 17): the table is the only source of these cases; the log is the acceptance of chapter 8.4 (`corrections-4.tsv` (historical correction record), a log, not in the export).

## Form of the input of the command `may`

The normative input form and its native exit meanings are defined in [the common native input form](../../contracts/may-input.md#may). Case inputs and answer associations below remain judge-only.

## `covers`

The normative input, output and coverage rule are defined in [the common covers form](../../contracts/may-input.md#covers).

19 rows. Tiers 1–4 and the choice of the first non-empty one are judged by the role group, not by one scope, so they are in [`cases.tsv`](cases.tsv) (may-62…may-92), not here. The first 9: `unit:` by the name at an unreadable row — `true`; `labels:` and a grant on an about-unit at an unreadable one — `false`; `*` at
an unreadable one — `true`; at a readable one — the labels at the row itself, the labels at about, a grant on an about-unit — `true`, `unit:` of a foreign
unit without about — `false`; a scope not by the grammar — `@exit 2`. Another 10 — `folder:`: at a unit, at about, at a subfolder, at a folder as an object, over a dead chain, at an unknown membership.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output (`{"result":"unavailable"}` — the third outcome, the door answers 503) or
`@exit 2` (an input not of the form of [P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N5 `exit`: the lines of `grants` are a trusted input, a line not of the form — 2, not a skip). The time is
by the input `now`, not by the process clock. Who performs: `cases.tsv` — the gate consoles of a cluster (`06-console`) and of the domain
(`10-domain-console`) and the process `domain` (`08-domain`); `covers.tsv` — only `06-console` and `10-domain-console` (the record `vectors` `common/may` or the former command
`covers` of the common acceptance README; one is enough — ACC-VECTORS-COVERS-STAND-01) (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

## Units

`c1` `testsub` with the labels `east`, `ground`; `c2` without labels; `t1` `testsub2` with the label `west` and `about` — `c1`. Folders — ids of 32 hex digits: `0f…`, `0b…` are root ones, `0a…` is a root one with the subfolder `0c…`. `now` is
1760000000; the age of the copy is `GRANT_LIFETIME` ([P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N1.3).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 127 rows: 52 `allow`, 44 `deny`, 7 `unavailable`, 24 `@exit 2` (may-26 — `until` does not fit in binary64, MAY-UNTIL-D8-01; may-27…may-106 — ADR-0097–ADR-0100, there is no dry run by an implementation) | `input` is the input of the command `may` as JSON text → `expect`: `{"result":"allow"}` (a break-glass session without grants, a copy of exactly one day of age, a holder line without `as_of`, `view` without a unit — any line, `*`, `unit:` its own and through `about`, `labels:` all labels, the labels of `about`, a higher rank, the term of the line ahead) or `{"result":"deny","reason":<word>}`: `disabled` (disabled at a grant), `stale` (a copy older than one day), `no_grant` (no line, `edit` without a unit not by `*`, a foreign unit, one label missing, the labels of the unit itself at `about`, a lower rank, an expired line, `"*"` not by `*`, a line of another subject, a unit without labels); `@exit 2` — a scope `unit:` with an id not by the grammar of [P/06.1](../../../06-console/spec/06.1-console.norms.md) N1.3; `subject` "" of a grant line (`may-25`, MAY-G03) |

The vectors were checked by an oracle against the text of the contract (steps 1–8) and the form of the input of [P/08.4](../../../08-domain/spec/08.4-domain.norms.md) N1.3, N5 `exit`, not against the code of implementations; on a
divergence the contract is right, the vector is corrected by «Specification».

## Vector wire

The wire of `cases.tsv`, `covers.tsv` is set by the `common/may` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

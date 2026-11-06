# Vectors of following the holder

This English text is the source; the Russian translation `ru/vectors/follow/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of the function `follow(keys, held, answers)` of the agent of a member — the choice of whose term record to follow: its own row
`domain/holder` and the records from the answers of the consoles (`/api/held`, 409 `deposed`) are checked by the function `record`
of [the term record contract](../../../common/contracts/record.md) and compared by term. The owner is lesson P/09, chapter 9.1
([P/09.1](../../spec/09.1-agent.norms.md) N3 «follow», N5 `follow`); only the agent performs it (review analysis of stage A 8–10,
№ 8). The bytes are written by «Specification» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `follow` of the acceptance of M11/10 (`inputs/follow-*.json`, sc. 06) without a change of bytes: only
whitespace and line breaks outside JSON strings are removed; `case` is the name of the input file; the expectation `ok <JSON>` is the cell `expect` (the plan
of the move of lesson 9, § 3; the Architect's decision on the plans 8–10, ADR-0083 addendum (14) item 17). Scenario 06 of the acceptance of M11/10 and its
inputs were removed by the move of lesson 9: the table is the only source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output or
`@exit 2` (an input not of the form of P/09.1 N5 `exit`: `follow` has no `held` or `answers`, `answers` is not an object, an extra field, the trusted
set `keys` is not of the form). The function does not check the signature of the set itself: the set is trusted. The `@exit 2` rows are 13–18.
The absence of a field (`term` at `stay` without its own record that passed `record`) is not compared by the subset — N5 `follow`, by reading.

## Keys

The keys of the issuer and the set are bytes in the inputs (`keys.issuing`, `doc.issuer`). The seeds are `sha256("w2c test <word>")`, as
in the package [`record`](../../../common/vectors/record/README.md) «Keys» (the root `root 1`, the token key `token key 1`, the issuers
`issuing key 1`, `issuing key 0` — in `revoked_issuing`, `issuing key 9` — a foreign one, the members `member m1`, `member m2`). The set `keys`
of rows 01–12 is one: `domain: acme`, `rev: 2`, the root signature; rows 13–21 change in it only what their `note` names
(`keys` null, no `revoked_issuing`, `issuing` not a list, `sig` — 64 zero bytes).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is, in rows 01–12,
the scenario and the step of the acceptance of M11, in rows 13–21 — the case of P/09.1 N5 `exit`.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 21 rows: 7 `follow`, 8 `stay`, 6 `@exit 2` | `input` — the input of the command `follow` as JSON text (`keys` — the set document, `held` — `{doc}` of its own row `domain/holder` or `null`, `answers` — `{<cluster>: {doc} \| null}`) → `expect`: `{"result":"follow","term":…,"holder":…,"url":…}` (a larger term; the same holder with a new `url` and a larger `at`; the same term at another holder; its own `held` is a backup copy document or a grant, it does not count as its own record) or `{"result":"stay","reason":<word>}` — `larger` (its own is larger), `holding` (the same; a forged or tampered larger answer — in `refused`), `two_holders` (two holders on one term), `none` (no answers; only a forged one); `refused` — `{<cluster>: <record word>}` |

The vectors were checked by the runs of the implementations of the acceptance of M11/10 (run 41, the reconciliation of M11 09–12) and by the text of the norms; on a discrepancy
the norm is right, «Specification» corrects the vector. Rows 13–21 — the coverage audit of P/09, the second pass (Gemini): the input forms and the exit
codes of N5 `exit` (`keys` not of the form, no `held`, an extra field, `answers` not an object — 2; a tampered `sig` of the set — not
a refusal; `held` not `{doc}` — its own record did not pass `record`; `answers.<to>` not `{doc}` — `not_a_record`, a key that is not a cluster name
— counted as an answer); the expectations are the output and the exit code of the command `follow` of the witness M11, reconciled with the norm.

## Source log

The rows of `corrections.tsv` of the acceptance of M11/10 about sc. 06 (the paths and numbers are the former ones, they are resolved by
`id-map.tsv` (historical record)):

| date | sample | fix |
|---|---|---|
| 2026-10-18 | 10/scenarios.tsv: 06 step 4 | run 41 B1: term at stay — the term of its own record for any reason (N5 follow), at two_holders — 1, not the disputed term |
| 2026-10-19 | 05 steps 13–16, 06 steps 11–12; inputs record-13…16, follow-11, follow-12 | reconciliation of M11 09–12 (H9–H12): the document kinds of record are closed, the document types of the backup copy, ca without repeats; its own held — only a term record |
| 2026-10-20 | the move | sc. 06 (12 steps) from M11/10 — the rows of this table (stage B; the plan of the move of lesson 9, § 3) |

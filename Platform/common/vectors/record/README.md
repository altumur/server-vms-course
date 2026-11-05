# Vectors of the term record and the issuer signature

This English text is the source; the Russian translation `ru/vectors/record/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the term record contract](../../contracts/record.md): the function `record(keys, row, виды)` — the check of a document
signed by the issuing key of the holder (a term record, a backup copy document, a grant). The owner is lesson P/08, chapter 8.8;
the function is performed by the member's agent (9.1), the process `domain` (8.8) and the cluster console (6.7, the shared document of [chapter 8.9](../../../08-domain/spec/08.9-domain.norms.md)) (the review
analysis of stage A 8–10, № 13 / decision 2; ADR-0083 addendum (13)). The bytes are written by «Спецификация» (ADR-0083); the conformance of the product is
by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `record` of the acceptance of М11/10
(`inputs/record-*.json`, sc. 05) without a change of bytes; `case` is the name of the input file. Scenario 05 of the acceptance of М11/10 and its inputs
were removed by the move of lesson 8 (ADR-0083 addendum (14) item 17; the log is the acceptance of chapter P/08.8 (`Platform/08-domain/journal/corrections-8.tsv`, a log, not in the export)):
the table is the only source of these cases.

## Run

Without a stand: the function of an implementation with four kinds (the three of chapter [P/08.8](../../../08-domain/spec/08.8-domain.norms.md) and the members row) gets the input (the column `input`) and gives the output; `expect` is
a subset of the fields of the output or `@exit 2` (an input not of the form of P/08.8 Н5 `exit`: the trusted set `keys` is not of the form). The signature
of the set itself the function does not check: the set is trusted (P/08.8 Н5).
Who performs (the table of the participants of the contract): `cases.tsv` — the process `domain` (`08-domain`, four kinds) all rows; `record-member-row-*` and [`take.tsv`](take.tsv) are also performed by the member's agent; the member's
agent (`09-agent`, the kinds «term record» and «backup copy document») — all rows except the grant document (`doc.grant`:
`record-12-grant-tampered` — at the agent this is another document, not its kind); `shared.tsv` — the cluster console (`06-console`,
P/06.7 Н1.14) and the member's agent (`09-agent`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-26).

## Keys

The keys of the issuer and the set are bytes in the inputs (`keys.issuing`, `doc.issuer`). The seeds are `sha256("w2c test <слово>")`
(moved from the acceptance README of М11/10 «Входы»): the root `root 1`, the token keys `token key 1` (`t1`) and `token key 0` (`t0`, rows 25–27); the issuers `issuing key 1` (in
`issuing` of the set), `issuing key 0` (in `revoked_issuing`), `issuing key 9` (a foreign one); the members `member m1`, `member m2`. The set
`keys` is one at all rows: `domain: acme`, `rev: 2`, the root signature; at rows 25–27 `t0` and `until` are added to it (the function does not check the signature of the set).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 46 rows: 14 `ok`, 27 refusals, 5 `@exit 2` (`record-member-row-gathered` — the sign of a gathering row; `record-holder-with-key` — a term record with `key`; `record-member-row-*` — the kind «members row», ADR-0113; 28 — `until` beyond binary64, C137-SCHEMA-TIME-01; 29–35 — the field `raw` of the backup copy document: the bytes `ff7b` of an object that is not JSON — `/3s=`, an object of 0 bytes — `""`, JSON not of the form « [ 1.00 ] » — `IFsgMS4wMCBdIA==` (not by value), an object of the form — in `objects` by value; without padding, the base64url alphabet and a key both in `objects` and in `raw` — `not_a_record`, C08-BACKUP-JSON-99) (rows 18–20 — REC-G01, 21–24 — nesting 64/65, REC-G02; 25–27 — the time `until` of the trusted set by the canon of P/01.1 Н0: the string «1700000000.5» is accepted, −1 and «1e9» — `@exit 2`, REC-TRUSTED-TIME73; the token key `t0` — the seed `token key 0`) | `input` is the input of the command `record` as JSON text (`keys` — the set document, `row` — `{doc}` as read) → `expect`: `{"result":"ok","term":…,"holder":…}` (a term record, a restored term, a backup copy document) or `{"result":"refused","reason":<слово>}`: `another_domain`, `revoked_issuer`, `unknown_issuer`, `bad_signature` (`kid` ≠ `issuer`, a forgery of a record, of a backup copy document, of a grant), `not_a_record` (not a row, an extra field, the shared document of chapter 8.9, `holder` of a backup copy document, a repeat in `members` and `ca`); `@exit 2` — `keys` is not a set |
| [`take.tsv`](take.tsv), 9 rows | `input` — `{keys, row, part, have}` → `expect`: `take`, `same`, `older` or a refusal by a word; the freshness boundary of the members row |
| [`shared.tsv`](shared.tsv), 8 rows: 1 `ok`, 7 refusals | the input is the same; the function with one kind «shared document» (P/08.9 Н1.2 document) → `expect` — a subset of `{result, term?, reason?}`; `kid` and `sig` outside the writer's form — steps 3–5, not `not_a_record` (REC-G01) |

The vectors were checked by reference Ed25519 (RFC 8032) and JCS (RFC 8785) against the text of the contract (the signatures and steps 2–5), not against the code
of implementations; on a divergence the contract is right, the vector is corrected by «Спецификация».

## Vector wire

The wire of `shared.tsv` is set by the `common/record` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

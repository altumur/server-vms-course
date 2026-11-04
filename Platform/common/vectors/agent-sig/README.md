# Vectors of the agent signature

This English text is the source; the Russian translation `ru/vectors/agent-sig/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the agent signature contract](../../contracts/agent-signature.md): the check of the header `X-Agent-Signature` by the function
`agent-sig`. The member's agent signs (the owner is lesson P/09, chapter 9.1); the checkers are the holder (chapters 8.3, 8.7), the relay
(9.2) and the cluster console ([P/06.3](../../../06-console/spec/06.3-console.norms.md) Н1.3 `identity` step 2). The package is common:
one signature is checked by three processes (the review analysis of stage A 8–10, № 13 / decision 2; ADR-0083 addendum (13)). The bytes are written by
«Спецификация» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `agent-sig` of the acceptance of
М11/3 (`inputs/agent-sig-*.json`, sc. 10) without
a change of bytes; `case` is the name of the input file. The scenario М11/03 sc. 10 and its inputs were removed by the move of lesson 8 (ADR-0083 addendum (14)
item 17; the log is the acceptance of chapter P/08.3 (`Platform/08-domain/journal/corrections-3.tsv`, a log, not in the export)): the table is the only source of these cases.

## Run

Without a stand: the check function of an implementation gets the input (the column `input`) and gives the outcome (the column `expect`); the comparison is a subset of the fields of the output, as at the other domain packages (the reading of the commits of «cammeta-acceptance» 2026-10-20). The time is by the input
`now` (the checker's wall seconds), not by the process clock.
Who performs is every checker of the signature, all rows (the window is the input `window`): the cluster console (`06-console`, the units doors and `GET /events?class=alarm`, P/06.3 Н1.3 `identity` step 2), the holder (`08-domain`, P/08.3 Н1.4, Н2; P/08.7 Н3 «issue» step 1) and the relay (`09-agent`, P/09.2 Н1.3, Н2). The member's agent signs (P/09.1 Н1.3) and does not call the check; the domain console (`10-domain-console`) has no step 2 of `identity` (P/10 Н1.5) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

`batch-knock.tsv` — the signature of a batch knock (the report acceptance contract «The batch knock»), 6 rows; performed by the process `domain`.

## Keys

The signing key is the key of the member `m1`: the seed `sha256("w2c test member m1")` =
`c27e2aa35b5905de643148195bc7c476e5c8dabaf63a2e9bb2dd17ac6d5cac39`, the public Ed25519
`b7b1b2708888b80495bdee35906cdbf0143b649eb92b6cf1f95d8108a3533b62`; the foreign key (the row `agent-sig-07-other-key`) is the member's
`m2`, `88cae557b9e5d4285769289b5af9d27cfdee0092823f38993912feae4b0c92c7`. The key of small order (the row
`agent-sig-19-small-order-key`) is the point `0100…00`.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 25 rows: 4 `ok`, 21 refusals (the last three rows — `X-Agent-For`, the input `for`, ADR-0111 item 16: `agent-sig-for-ok` — `ok`, two — refusals) (row 20 — the order of the checks: a foreign key outside the window → `out_of_window`, the review analysis of stage B 8–10, № 3; 21 — `sig` with non-zero trailing bits, 22 — GET with a body and a signature over it, AS-01/02) | `input` is the input of the command `agent-sig` as JSON text (`key`, `method`, `path`, `body`, `header`, `now`, `window`; the lexemes of numbers — as in the input file) → `expect` — `{"result":"ok"}` or `{"result":"refused","reason":<слово>}`: `out_of_window` (the boundary `now` = `мс`/1000 + the window — `ok`, 0.001 s further and in the other direction — a refusal; the window 60 at the units door), `bad_signature` (a foreign key, the body, the path, the method changed; GET with a body — with a signature over the empty one and over the one that came; a key of small order), `not_a_signature` (no «.», `мс` not digits, with a leading zero, 17 characters; `sig` with «=», 63 bytes, non-zero trailing bits), `no_signature` (an empty header) |

The vectors were checked by reference Ed25519 (RFC 8032) and SHA-256 against the text of the contract, not against the code of implementations; on a divergence the
contract is right, the vector is corrected by «Спецификация».

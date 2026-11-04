# Request signature vectors

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the request signature contract](../../../contracts/ask-sig.md): the function `ask-sig` — the check of the headers `X-W2C-Member`,
`X-W2C-Time`, `X-W2C-Signature` at the requests `backup`, `prepare` and `move`. The owner is lesson P/08, chapter 8.8; the checkers are the cluster console
(6.7, `GET /api/backup`) and the process `domain` of the target (8.8, `POST /api/prepare`) (review analysis of stage A 8–10, № 13 / decision 2;
ADR-0083 addendum (13)). The bytes are written by «Спецификация» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080
addendum 16).

The rows were transferred from the inputs of the command `ask-sig` of the acceptance of М11/10
(`inputs/ask-sig-*.json`, sc. 07) without a change of bytes; `case` is the name of the input file. Scenario 07 of the acceptance of М11/10 and its inputs
were removed by the move of lesson 8 (ADR-0083 addendum (14) item 17; the log — the acceptance of chapter P/08.8 (`Platform/08-domain/journal/corrections-8.tsv`, a log, not in the export)):
the table is the only source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the outcome (the column `expect`) or `@exit 2` (an input not of
the form of [P/08.8](../../../../08-domain/spec/08.8-domain.norms.md) Н5 `exit`); the comparison is a subset of the fields of the output, as at the other domain packages (the reading of the commits of «cammeta-acceptance» 2026-10-20). The time is by the input `now`, not by the process clock.
Who performs it — by the `ask` of the input: `backup` — the cluster console (`06-console`, `GET /api/backup`); `prepare` — the process
`domain` of the target (`08-domain`, `POST /api/prepare`); `move` — the cluster console of the target and the process `domain` (ACC-VECTORS-CONNECT-02, the Architect's decision 2026-10-26).

## Keys

The key of the member `m1` is `b7b1b2708888b80495bdee35906cdbf0143b649eb92b6cf1f95d8108a3533b62` (the seed `sha256("w2c test member m1")`);
the token key `t1` is `dc8561d3f7f3a8f7fd68636f4762ed842dfbceb256c56f0707ed3b1ee41b9d8f`; a foreign key is that of the member `m2`
`88cae557b9e5d4285769289b5af9d27cfdee0092823f38993912feae4b0c92c7`.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](../cases.tsv), 27 rows: 5 `ok`, 16 refusals, 6 `@exit 2` (row 13 — the field `member` at the top level of the input, review analysis of stage B 8–10, question 2; rows 14–26 — `move`, row 27 — `backup` with an extra `body_sha256`, C08-MOVE-BY-FILE-01) | `input` — the input of the command `ask-sig` as JSON text → `expect`: `{"result":"ok"}` (`backup`, `prepare`, the window boundary of 300 s) or `{"result":"refused","reason":<слово>}`: `missing` (no signature), `bad_time` (without a fraction, one digit of the fraction), `skew` (301 s into the past and into the future), `bad_signature` (a foreign key, another cluster in the message, `prepare` with a foreign key); `@exit 2` — `pub` is not hex |

The vectors are checked by reference Ed25519 (RFC 8032) against the text of the contract, not by the code of implementations; on a discrepancy the contract is right,
«Спецификация» corrects the vector.

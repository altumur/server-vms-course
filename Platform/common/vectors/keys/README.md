# Vectors of the domain key set

This English text is the source; the Russian translation `ru/vectors/keys/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the domain key set contract](../../contracts/keys.md): the function `keys(pinned, held, offered)` — accept the set
`domain/keys` signed by the root, only forward. The owner is lesson P/08, chapter 8.2; the function is performed by the member's agent (9.1),
the cluster console ([P/06.3](../../../06-console/spec/06.3-console.norms.md) «Keys exist» (keys exist)) and the process `domain` at a move and at
following (the review analysis of stage A 8–10, № 13 / decision 2; ADR-0083 addendum (13)). The bytes are written by «Specification» (ADR-0083);
the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `keys` of the acceptance of M11/2
(`inputs/keys-*.json`, sc. 01–03) without a change of bytes; `case` is the name of the input file. The scenarios M11/02 sc. 01–03 and their inputs
were removed by the move of lesson 8 (ADR-0083 addendum (14) item 17; the log is [the README of the package `domain-token`](../domain-token/README.cases.md#source-log)): the table is the only source
of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output.
Who performs: `cases.tsv` — the member's agent (`09-agent`), the cluster console (`06-console`) and the process `domain` (`08-domain`);
`revoked.tsv` — the member's agent (`09-agent`): it writes the row `jtis` (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

## Keys

The seeds are `sha256("w2c test <word>")`, the words are [the README of the package `domain-token`](../domain-token/README.cases.md#keys) «Keys» (`root 1` — the root of the domain `acme`, `root 2` —
a foreign root, `token key 1…3`, `book seal 1`, `book seal 2`); the bytes of the keys are in the inputs themselves (`pinned.pub`, `doc`).
The public root of `acme` is `34dc3424ca1fc497170b49eef38222db60fbcaa887852645d7c73bedcc9f7684`.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 29 rows: 7 `took`/`holding`, 22 refusals | `input` is the input of the command `keys` as JSON text (`pinned` — `{pub, domain}` or `null`, `held` — the set document or `null`, `offered` — the row `domain/keys` as it came) → `expect` — `{"result":"took"\|"holding","rev":…}` or `{"result":"refused","reason":<word>[,"rev":…]}`: `older` (rev of `held`), `no_pin`, `another_root` (the root, the domain), `bad_signature` (a forgery, `kid` not `root`, a signature of 63 bytes, the wrong key), `not_a_set` (not JSON, an extra field, `current` not in `keys`, an extra element of the row, a repeat of a JSON key), `no_book_seal` (none, a point of small order) |
| [`revoked.tsv`](revoked.tsv), 7 rows | `input` — `{own, answer, now}`: the member's own row `jtis`, the `jtis` of the holder's answer or `null`, the wall seconds; `expect` — the `jtis` of the row that the agent writes (`merge`, `repeat`, `prune` of the contract; `TOKEN_SKEW` 60; KEYS-G01) |

The vectors were checked by reference Ed25519 (RFC 8032), X25519 (RFC 7748) and JCS (RFC 8785) against the text of the contract, not against the code
of implementations; on a divergence the contract is right, the vector is corrected by «Specification».

## Vector wire

The wire of `cases.tsv` and `revoked.tsv` is set by the `common/keys` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

# `peer` vectors: case data and coverage

This English text is the source; the Russian translation `ru/vectors/peer/README.cases.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of [the `peer` contract](../../contracts/peer.md): the function `peer` — a client of a door of another cluster over `https://` about the server
(the anchor fingerprint, the signature path by the closed list `sig`, the terms, the role and the name of the leaf). The owner is lesson P/09 (the first contract —
the agent to `https://`); the participants are the cluster console (6.7), the process `domain` (8.8) and the domain console (lesson P/10) (the Architect's
decision 2026-10-20, ADR-0083 addendum (14) item 2; review analysis of stage A 8–10, № 7). The bytes are written by «Specification»
(ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `peer` of the acceptance of M11/8
(`inputs/peer-*.json`, sc. 06) without a change of values: the JSON of the input — in one line (PEM — as a JSON string with `\n`), the order
of keys and the lexemes of numbers — as in the file; `case` is the name of the input file. Scenario 06 of the acceptance of M11/8 and its
inputs were removed by the move of lesson 9 (ADR-0083 addendum (14) item 17), the directory M11/08 — by the move of lesson 10: the table is the only
source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output or
`@exit 2` (an input not of the form of M11/8 N5 `exit`: there are no fields of the trusted input — the row `peer-32-exit2-fields-missing`; the acceptance README «Exit codes of vector commands»; a chain not of the form is not 2 but `bad_chain`, step 2). The time is by the input `now`, not by the process clock.
Who performs it: the clients of another cluster — the agent and the relay (`09-agent`), the cluster console (`06-console`) and
the process `domain` (`08-domain`) — all rows; the domain console (`10-domain-console`, a server of the class `role`: steps 6–7 over
the client's leaf) — the rows with `reason` `no_role` and `wrong_role` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).

## Centres and leaves

As in the README of the acceptance of M11/8 «Inputs»: the centres A (`w2c test ca north`), its intermediate AI and B (`w2c test ca south`), EC
P-256; the leaves of the role `console` with SAN DNS `m2.w2c.test`; the anchors RSA-2048, Ed25519 and P-384 with SHA-384 (the reconciliation of M11, D14). The fingerprint
is the sha256 hex of the DER of the centre ([P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `fingerprint`). `now` is 1760000000.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 31 rows: 7 `ok`, 23 refusals, 1 `@exit 2` (the row `peer-27-chain-out-of-order` — the centres are swapped, step 4 by adjacent elements; review analysis of stage B 8–10, № 10; rows 28–32 — the coverage audit of P/09, the second pass: `127.1` — a name, `::1` — `ip_address`, an empty chain before empty fingerprints — `bad_chain`, a dot at the end of host — `wrong_name`, an input without fields — `@exit 2`) | `input` — the input of the command `peer` as JSON text → `expect`: `{"result":"ok"}` (directly, an intermediate anchor, a root anchor through an intermediate, two fingerprints — either, an RSA, Ed25519, P-384 anchor) or `{"result":"refused","reason":<word>}`: `foreign_ca` (no fingerprints, a foreign centre, only the leaf in the chain), `bad_chain` (the leaf is not from the anchor, there is no intermediate, the leaf is not from the named centre, the intermediate is not a centre, not PEM), `expired` (the leaf, the anchor, the leaf is not yet valid), `no_role` (no SAN URI, two roles, an empty role), `wrong_role`, `wrong_name`, `ip_address` (IPv4, IPv6 with a zone) |

The vectors are checked by an oracle against the text of the contract (steps 1–9; the signatures — the closed list `sig` of the role certificate contract;
the library `cryptography`), not by the code of implementations; on a discrepancy the contract is right, «Specification» corrects the vector. Rows 28–32 are
the output and the exit code of the command `peer` of the witness M11, reconciled with steps 1, 2, 3, 8 of the contract.

## Vector wire

The wire of `cases.tsv` is set by the `common/peer` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

## Source metadata

This English text is the source; the Russian translation `ru/vectors/peer/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Source file `vectors/peer/README.md`: [README](README.md).

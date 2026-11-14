# Domain token vectors: case data and coverage

This English text is the source; the Russian translation `ru/vectors/domain-token/README.cases.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of [the domain token contract](../../contracts/domain-token.md): the function `token(keys, revoked, now, token)` — the check of
a domain token by the accepted set `domain/keys` and the row `domain/revoked` by the wall clock of the checker, with the `expect`
of the recipient (the kind and its own cluster). The owner is lesson P/08, chapter 8.2; the function is performed by the gate of the cluster console
([P/06.3](../../../06-console/spec/06.3-console.norms.md) N1.3, N1.8), the recipient of a kind token — the worker and the door of a member
([P/03.7](../../../03-worker/spec/03.7-worker.norms.md) N3 «check at the recipient»), the process `domain` at the doors of people
([chapter 8.4](../../../08-domain/spec/08.4-domain.norms.md)) and the domain console (lesson P/10). The bytes are written by «Specification»
(ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `token` of the acceptance of M11/2
(`inputs/token-*.json`, sc. 04–07, 12) without a change of bytes: only whitespace and line breaks outside JSON strings are removed; `case` is
the name of the input file (the move of lesson 8, the plan of the move of lesson 8 § 3, the Architect's decision on the plan, item 17; the row «Vectors»
of the contract). The scenarios M11/02 sc. 04–07, 12 and their inputs were removed by the move of lesson 8 (the log is «Source log» below): the table is
the only source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output. Exit
code 0 — computed (a refusal by a word included); `@exit 2` — an input not of the form: exit code 2, the output is not compared
(the dictionary of the «Stand» of [the common acceptance README](../../acceptance/README.md)); there are ten such rows — `token-30`, `token-31`, `token-32`, `token-39`…`token-42`, `token-44`, `token-45`, `token-keep-no-until`.
Who performs it — every checker of a token, all rows by one function (`expect` is an input): the gate of the cluster console (`06-console`, P/06.3 N1.3 `identity` step 3), the recipient of a kind token and the process door (`03-worker`, P/03.7 N1.5; P/03.4 N1.7 `door_admission`), the process `domain` at the doors of people (`08-domain`, P/08.4) and the gate of the domain console (`10-domain-console`, P/10 N1.5). The agent of a member (`09-agent`) does not call the function: it checks the answer of the local token door by `request_id` and `exp` (P/08.7 N3) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Keys

The keys of the inputs of chapter [P/08.2](../../../08-domain/spec/08.2-domain.norms.md) (the packages `keys`, `domain-token`,
`domain-envelopes`; the book acceptance key — and the package `assemble`) are test keys and open: the seed of each is `sha256("w2c test
<word>")`, the words are `root 1` (the root of the domain `acme`),
`root 2` (a foreign root), `token key 1…3` (the token keys `t1…t3`), `book seal 1`, `book seal 2` (the book acceptance keys),
`member m1` (the member key in `revoked_members`), `eph 1…3` (one-time pairs of the vector envelopes; `nonce` — the bytes 0…11).
The envelope vectors are sealed with these `eph` and `nonce` only for reproducibility; an implementation takes
random ones when sealing ([P/08.2](../../../08-domain/spec/08.2-domain.norms.md) N1.5, [the domain envelopes contract](../../contracts/domain-envelopes.md)). The public keys:

```text
root 1      34dc3424ca1fc497170b49eef38222db60fbcaa887852645d7c73bedcc9f7684
book seal 1 bcd5fdec0a3585c7b8793b352a0322a72c6aa1801c1874dac9e7cebfc2c8f970
book seal 2 57bf48000f17919375a83a26f7b2064ade5a0b8ee1c29f9a3bbdd87c28434603
```

`token-*`: the moment `now` = 1760000000 (except the boundary cases), the token — `iat = now − 10`, `exp = now + 890`,
`jti = 0123456789abcdef`, `sub = alice`; the set rev 3: `current = t2`, `t1` with `until = now + 100`. `keys-15` and `token-15` are
the set after a theft (rev 1760000000, the key `t3`, `revoked_issuing = [i1]`, a new `book_seal`). The tokens of the inputs have `kind`
(`person`; every domain token has a kind); sc. 12 is the check by the recipient (the inputs, except `token-21`, have the kind `tally` with an audience field; `expect`: the kind and its own cluster, [P/08.7](../../../08-domain/spec/08.7-domain.norms.md), [P/03.7](../../../03-worker/spec/03.7-worker.norms.md)).
`seal-round` is reconciled by `opened` and `distinct`; the form of the two `envelopes` — by the domain envelopes contract.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is the scenario and the step
of the acceptance.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 53 rows: 12 `ok`, 31 refusals, 10 `@exit 2` | `input` — the input of the command `token` as JSON text (`keys` — the set document, `revoked` — `{jtis}` as read or `null`, `now`, `token`, `expect?` — `{kind, cluster, audience_claim?}`, `kind` — a string or a list of kinds) → `expect` — `{"result":"ok","payload":{…}}` (a subset of the fields of `payload`) or `{"result":"refused","reason":<word>}`: `unknown_key` (a former key after `until`, the key is not in the set, a stolen key after a new set), `bad_signature` (a substituted `payload`), `not_a_token` (two parts, `alg` not `EdDSA`, a repeated key in `header`), `bad_claims` (no `jti`, `jti` not by the grammar, no `kind`, `exp` as a string), `expired`, `future`, `revoked`, `no_revocations` (`jtis` not a string, the `exp` of an entry — a word, a leading zero, not finite), `wrong_kind`, `wrong_audience` (a foreign cluster, the audience field `audience_claim`) |

Boundaries: `now = exp + 60` — `ok`, `exp + 61` — `expired`; `now = iat − 60` — `ok`, `iat − 61` — `future`; `expect` with
`cluster: null` (`person`) — the audience is not checked.

The form of `expect` ([the contract](../../contracts/domain-token.md) «The check», `expect`; item 7 of the note on the plans 8–10, the edit
`0c9521c66`): the key `cluster` is mandatory, `null` — only at `kind: person`. The rows `token-30-expect-no-cluster` (the input
`token-18` without the key `cluster`) and `token-31-null-cluster-not-person` (the input `token-18` with `cluster: null` at `kind: tally`) are
`@exit 2`; the token and the other fields of the input are the bytes of `token-18` (review analysis of stage B 8–10, № 13). `expect` is a closed form:
`token-32-expect-unknown-key` (the input `token-18` with an extra key `audience_clam`) — `@exit 2` (DT-G03).

The list of kinds (ADR-0091 addendum (18) item 1, addendum (19) item 1; the route `domain` of the process door, P/03.4 N1.7): `token-33`…`token-38` —
a kind from the list — `ok`, not from the list — `wrong_kind`, an expired token of a foreign kind — `expired` before the kind, the audience field is that of
the kind that matched at step 9 (the mapping `audience_claim`; a kind without an entry — `aud`); the token of the kind `probe` of rows 36–38 is signed
with the key `t2` (`token key 2`), `aud` — `[m9]`, `for` — `[m1]`. `token-43` is a token of the kind `tally` with the same mapping as at `token-36` (the audience field is by the kind of the token, W03-G10). `token-39`…`token-42` are `@exit 2`: `person` in the list, a list with
`audience_claim` as a string, a mapping key not from the list, an empty list.

An input not of the form (the coverage audit of P/08, the second pass of Gemini): `token-44-expect-empty-audience-claim` (the input `token-18` with `audience_claim: ""`, P/08.2 N5, T4) and
`token-45-keys-no-current` (the input `token-18`, the set `keys` without `current`) — `@exit 2`. The expectations are the output of both witnesses
`cammeta-python` and `cammeta-go`: at them `token-18` is `ok`, with this edit — code 2 with the named reason.

## Candidates

- a row `domain/revoked` unreadable by the store at the door («nothing to check with», the contract «The check») is a property of the door, not of the
  function: it is checked by the stand;
- a repeated kind in the list `expect.kind` (`["tally", "tally"]`) — code 2 by the contract («The check» `expect`: a list without repeats):
  there is no row — both witnesses do not know lists of kinds and refuse with code 2 for another reason, the expectation is not confirmed by them.

The vectors are checked by reference Ed25519 (RFC 8032) and by JSON parsing with a ban on a repeated key, by the text of the contract (steps 1–11
of the «The check»), not by the code of implementations: all 29 expectations matched the output of the oracle; the rows `token-30`, `token-31`, `token-32` (`@exit 2`) and `token-33`…`token-43`
were added by the text of the contract (`token-44`, `token-45` — above), `expect` (the signature of rows 36–38 — by reference Ed25519 with the key `t2`). On a discrepancy the contract is right, «Specification» corrects
the vector.

## Source log

The rows of `corrections.tsv` of the acceptance of M11/02 before the move and the rows of the move — for the packages `keys`, `domain-token`,
`domain-envelopes` (the acceptance directory of M11/02 is removed by the move of lesson 8; the paths and numbers are the former ones, they are resolved by
`id-map.tsv` (historical record)):

| date | sample | fix |
|---|---|---|
| 2026-10-17 | 02/seal-16-noncanonical-ct | cammeta-python M11-02 № 6: base64url — the canonical notation (the extra bits are zero); a non-canonical envelope — not_an_envelope |
| 2026-10-17 | 02/inputs/token-*, sc. 05 step 7, sc. 12 | the Architect's decision on M11/7 item 6 and the addition: kind at every token (without it — bad_claims); the check by the recipient — wrong_kind, wrong_audience |
| 2026-10-18 | 02/scenarios.tsv: 02/02, 02/03; keys-18, keys-19 | run 41, mutations №7, №8: kid not root before a foreign domain; the signature before book_seal (a double error — the first refusal in order) |
| 2026-10-18 | 02/scenarios.tsv; inputs | run 41, mutations №6: iat = now + 60 — ok |
| 2026-10-18 | 02/scenarios.tsv; inputs | run 41, mutations №9, №10: a revocation entry not «`<jti>:<JSON number>`» — no_revocations; the audience by audience_claim, not by aud |
| 2026-10-18 | 02/scenarios.tsv; inputs | run 41, mutations of the signature class: a set signature of 63 bytes; exp as a string — bad_claims |
| 2026-10-19 | 03 step 8, 07 step 6, 11 step 2; inputs keys-21, token-29, seal-round-02 | reconciliation of M11 01–04 (S1, T3): a book_seal of small order — no_book_seal and not_an_envelope at seal-round, the exp of a revocation not finite — no_revocations |
| 2026-10-20 | the move | the scenarios 04-token-keys, 05-token-form, 06-token-clock, 07-token-revoked, 12-token-kind-and-audience from M11/02 (stage B) — the vector rows common/vectors/domain-token/cases.tsv (29), the inputs inputs/token-*.json — the input cells without a change of bytes; the expectations reconciled by an oracle against the text of the domain token contract «The check» |
| 2026-10-20 | the move | the scenarios 01-key-set-forward, 02-key-set-root, 03-key-set-form, 08-envelope-opens, 09-envelope-does-not-open, 10-envelope-form, 11-seal-round from M11/02 are removed (stage B): the same cases — common/vectors/keys (21), common/vectors/domain-envelopes x25519-open.tsv (16), x25519-round.tsv (2) (the plan of the move of lesson 8 V1; the Architect's decision, ADR-0083 addendum (14), item 17) |
| 2026-10-20 | the history of M11/02 | the rows of corrections.tsv of the acceptance of M11/02 before the move — whole at the beginning of the log, with the former paths and numbers (they are resolved by the historical id map) |
| 2026-10-20 | token-30, token-31 | review analysis of stage B 8–10, № 13 (item 7 of the note on the plans 8–10, the edit 0c9521c66): expect without the key cluster and cluster: null at kind ≠ person — @exit 2; the input — token-18 with a changed expect |
| 2026-10-23 | token-32 | stage C guess DT-G03, the Architect's decision 2026-10-23: expect is a closed form, an unknown key — @exit 2; the input — token-18 with an extra key audience_clam |
| 2026-10-30 | +token-44-expect-empty-audience-claim, token-45-keys-no-current | the coverage audit of P/08, the second pass of Gemini (G02, e32df6f8b): package candidates — `audience_claim` empty and `keys` not of the form — `@exit 2`; the input — token-18 with one edit; the expectations — the output of the witnesses cammeta-python and cammeta-go; a repeated kind in `expect.kind` stays a candidate |

## Vector wire

The wire of `cases.tsv` is set by the `common/domain-token` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

## Source metadata

This English text is the source; the Russian translation `ru/vectors/domain-token/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Source file `vectors/domain-token/README.md`: [README](README.md).

# Acceptance P/08.7 — issuing tokens (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Стенд домена»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly the dictionary of the М11 README of the acceptance
М11/01; the plan of the move of lesson 8, В5). The norm of the chapter is
[`08.7-domain.norms.md`](../../spec/08.7-domain.norms.md) Н5. Scenarios 01, 02 were moved from the acceptance of М11/07 (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones (steps 02/6 and 02/12 have the agent's `error` words, the guesses of stage C LTD-E01, LTD-E02). Scenario 03 is the framing of the local door (the guesses of stage C LTD-E01, LTD-E02): `@header` adds a second `Host`, a second `Content-Length`, `Transfer-Encoding`, headers larger than 16 KiB; a body larger than `TOKEN_BODY`; an answer with `Connection: close`; the input deadline of 10 s — by reading (there is no slow-client directive). Scenario 04 is the body limit at the holder's door (the coverage audit of P/08, audit-kimi 1e9929d51), scenarios 05, 06 are unreadable rows at issuing (the coverage audit of P/08, the second pass of Gemini). In total 7 scenarios / 55 steps.

Scenario 07 is a token of a `keep` kind and the word `revoked` (ADR-0110 addenda (10)–(16); P/08.2 Н1.6а `jti`, `door`; P/08.7 Н1.3 `body`; roadmap 4.5). The kind `vault` of the manifest `testsub2` is `keep: true`. Steps 3–6 — `jti` is constant for the target. Steps 7–8 — a word not equal to the `jti` of the row is an ordinary request, `jti` is the earlier one. Steps 9–11 — a word equal to the `jti` of the row: so asks a member whose receiver refused the token with `revoked` while the holder does not know of the revocation (a copy older than `DELETE`); the holder puts `jti` into `domain/revoked` in one batch with the new row, issues a new `jti`, the earlier token is refused at the member by the revocation. Step 12 — a word at a kind without `keep` — 400. Steps 13–15 — `DELETE` revokes the tokens of the target, a repeated one — 404. The copy older than `DELETE` itself (the transfer from a copy), the raise of `exp` at a restore, the limit `REVOKED_WORDS` and a full row `domain/revoked` (409) — by reading: the stand does not hold a copy before `DELETE` longer than `BACKUP_EVERY` and does not fill the revocations row.

Issuing in all scopes and refusal words without a stand is checked by the vector [`issue`](../../vectors/issue/README.md) (38 rows:
30 — the former sc. 03 of the acceptance of М11/07, 8 — the coverage audit of P/08, the second pass of Gemini). The refusals of a kind declaration are the cases `m57_tokens_*` of the corpus of
[P/02.1](../../../02-installer/acceptance/1/README.md); the check of a token at the receiver on vectors is
[the domain token contract](../../../common/contracts/domain-token.md), the package `domain-token` (the former sc. 12 of the acceptance of М11/02).

The division (the plan of the move of lesson 8, В12): both scenarios are chapter 8.7, their outcome is the holder's issuing and the token claims. The local
door of the agent ([the local token door contract](../../../common/contracts/local-token-door.md), [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) Н1.6) and the receiver
(`@verify`, [P/03.7](../../../03-worker/spec/03.7-worker.norms.md) Н1.5) are neighbours on the stand: steps 02/6, 02/8, 02/12 are refusals of
the local door (400 `request_id`, 413 `TOKEN_BODY`, 404 `<sub>` not from the catalog), steps 01/4–7 are the check at the receiver.

## Preparation

As the stand preparation of chapter 8.3 ([the acceptance of chapter 8.3](../3/README.md); before the move, the acceptance README of
М11/03, «Подготовка каждого сценария 01–09») with one
difference: the catalog of each cluster is `testsub` and `testsub2`, like the stand of chapter 8.5 (the order is the «Stand» of the common acceptance
README); on each cluster the controller of `testsub2` works too (without its snapshot shard the agent does not report — [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md)
Н1.2 `ready`), the worker of `testsub2` is not needed. The kind `tally` of the manifest `testsub` is the scope `placement`,
`caller: origin`, `target_fields: [cluster, copies]`. The role `testsub2worker` of the stand is a real identity (a role socket or a kit), and
the `grant` of the kind `tally` does not name it: step 02/3 — a foreign role asks for a kind that was not given to it. The door `token <кластер> <роль>` and
the directive `@verify` are the dictionary of the domain: `@verify` checks a token with the function `token`
([the domain token contract](../../../common/contracts/domain-token.md) «Проверка») by the rows `domain/keys` and `domain/revoked`
of the named cluster and with its name in `expect`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the dictionary of the domain; an expectation is a subset of fields. `$tok` is the token from the answer of the local door.

- Sc. 02 steps 7–8 — the body limit: 4096 bytes at the local door pass to the holder (`no_assignment`), 4097 — 413 at the local
  door; `TOKEN_HOLDER_BODY` 4608 at the holder's door — sc. 04.
- Sc. 02 steps 9–11 — the member's clock outside the window of the agent signature: 401 at the holder, then the clock back
  ([the agent signature contract](../../../common/contracts/agent-signature.md)).
- Sc. 01 step 7 — a forged token (`@spoil`) at the receiver — `bad_signature`.
- Sc. 04 — the holder's door `POST /api/tokens/m1/testsub/tally` through the door `signer` (the process `domain` on `hold`, like
  `POST /api/relay` in sc. 18 of [the acceptance of chapter 8.3](../3/README.md)), without an agent signature, a `@raw` body of the bytes `x`: exactly
  4608 bytes — the limit is not exceeded, the first check after it is the signature (`m1` is a member with a key in the record): 401 `no_signature`
  ([the agent signature contract](../../../common/contracts/agent-signature.md)); 4609 — 413 `refused` before the signature and the parse
  (the local token door contract `refusal_413`; Н1.3 `body`).
- Sc. 05, 06 (the coverage audit of P/08, the second pass of Gemini, the draft G08 `e32df6f8b`, rewritten): the holder's rows are spoiled past the door (`admin.sock`).
  Sc. 05 — the record `domain/placement/testsub/c1` without `copies` is unreadable (the М11 check, T2; the outcomes of the family, Г-35): `tally` — 403
  `assignment_unreadable` (Н3 step 5; the vector `issue-08` is the same record as the input `"garbled"`). Sc. 06 — `domain/topology` is not
  JSON (Н3 step 4а): `tally` (the scope `placement` with `target_fields` `[cluster, copies]`) does not take the topology — 200; `probe`
  (the scope `unit`, `poll_home`) — 503 `unavailable` before the scope; the local door passes the code and the body of the holder as they came
  (the local token door contract `answer`).

## `journal/corrections-7.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М11/07 as a whole, at the beginning of the log, with the former paths and numbers (they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)); the rows about sc. 03 are the history of the source (the plan of the move of lesson 8, § 3 «Журналы»).
Implementations and their runners check their own result; this directory does not run them itself.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There are no sleeps. The member's clock is moved by `@clock` (sc. 02 steps 9, 11).

## Kit seams

[3 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

# Acceptance P/08.7 — issuing tokens (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly the dictionary of the M11 README of the acceptance
M11/01; the plan of the move of lesson 8, V5). The norm of the chapter is
[`08.7-domain.norms.md`](../../spec/08.7-domain.norms.md) N5. Scenarios 01, 02 were moved from the acceptance of M11/07 (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones (steps 02/6 and 02/12 have the agent's `error` words, the guesses of stage C LTD-E01, LTD-E02). Scenario 03 is the framing of the local door (the guesses of stage C LTD-E01, LTD-E02): `@header` adds a second `Host`, a second `Content-Length`, `Transfer-Encoding`, headers larger than 16 KiB; a body larger than `TOKEN_BODY`; an answer with `Connection: close`; the input deadline of 10 s — by reading (there is no slow-client directive). Scenario 04 is the body limit at the holder's door (the coverage audit of P/08, audit-kimi 1e9929d51), scenarios 05, 06 are unreadable rows at issuing (the coverage audit of P/08, the second pass of Gemini). In total 7 scenarios / 55 steps.

Issuing in all scopes and refusal words without a stand is checked by the vector [`issue`](../../vectors/issue/README.md) (cases and their provenance: the canonical package README). The refusals of a kind declaration are the cases `m57_tokens_*` of the corpus of
[P/02.1](../../../02-installer/acceptance/1/README.md); the check of a token at the receiver on vectors is
[the domain token contract](../../../common/contracts/domain-token.md), the package `domain-token` (the former sc. 12 of the acceptance of M11/02).

The division (the plan of the move of lesson 8, V12): both scenarios are chapter 8.7, their outcome is the holder's issuing and the token claims. The local
door of the agent ([the local token door contract](../../../common/contracts/local-token-door.md), [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) N1.6) and the receiver
(`@verify`, [P/03.7](../../../03-worker/spec/03.7-worker.norms.md) N1.5) are neighbours on the stand: steps 02/6, 02/8, 02/12 are refusals of
the local door, steps 01/4–7 are the check at the receiver.

## Preparation

As the stand preparation of chapter 8.3 ([the acceptance of chapter 8.3](../3/README.md); before the move, the acceptance README of
M11/03, «Setup of each scenario 01–09») with one
difference: the catalog of each cluster is `testsub` and `testsub2`, like the stand of chapter 8.5 (the order is the «Stand» of the common acceptance
README); on each cluster the controller of `testsub2` works too (without its snapshot shard the agent does not report — [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md)
N1.2 `ready`), the worker of `testsub2` is not needed. The kind `tally` of the manifest `testsub` is the scope `placement`,
`caller: origin`, `target_fields: [cluster, copies]`. The role `testsub2worker` of the stand is a real identity (a role socket or a kit), and
the `grant` of the kind `tally` does not name it: step 02/3 — a foreign role asks for a kind that was not given to it. The door `token <cluster> <role>` and
the directive `@verify` are the dictionary of the domain: `@verify` checks a token with the function `token`
([the domain token contract](../../../common/contracts/domain-token.md) «The check») by the rows `domain/keys` and `domain/revoked`
of the named cluster and with its name in `expect`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the dictionary of the domain; an expectation is a subset of fields. `$tok` is the token from the answer of the local door.

## Kit seams

[3 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

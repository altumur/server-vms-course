# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/7/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

[`08.7-domain.norms.md`](../../spec/08.7-domain.norms.md) N5. Scenarios 01, 02 were moved from the acceptance of M11/07 (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones (steps 02/6 and 02/12 have the agent's `error` words, the guesses of stage C LTD-E01, LTD-E02). Scenario 03 is the framing of the local door (the guesses of stage C LTD-E01, LTD-E02): `@header` adds a second `Host`, a second `Content-Length`, `Transfer-Encoding`, headers larger than 16 KiB; a body larger than `TOKEN_BODY`; an answer with `Connection: close`; the input deadline of 10 s — by reading (there is no slow-client directive). Scenario 04 is the body limit at the holder's door (the coverage audit of P/08, audit-kimi 1e9929d51), scenarios 05, 06 are unreadable rows at issuing (the coverage audit of P/08, the second pass of Gemini). In total 7 scenarios / 55 steps.

<!-- original-mixed-case-paragraph -->

[the domain token contract](../../../common/contracts/domain-token.md), the package `domain-token` (the former sc. 12 of the acceptance of M11/02).

<!-- original-mixed-case-paragraph -->

The division (the plan of the move of lesson 8, V12): both scenarios are chapter 8.7, their outcome is the holder's issuing and the token claims. The local
door of the agent ([the local token door contract](../../../common/contracts/local-token-door.md), [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) N1.6) and the receiver
(`@verify`, [P/03.7](../../../03-worker/spec/03.7-worker.norms.md) N1.5) are neighbours on the stand: steps 02/6, 02/8, 02/12 are refusals of
the local door, steps 01/4–7 are the check at the receiver.

<!-- original-mixed-case-paragraph -->

the `grant` of the kind `tally` does not name it: step 02/3 — a foreign role asks for a kind that was not given to it. The door `token <cluster> <role>` and

# Acceptance P/08.10 — the queue and the price

This English text is the source; the Russian translation `ru/acceptance/10/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are [the common acceptance README](../../../common/acceptance/README.md), the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand)
(a stand of several clusters; formerly the dictionary of the M11 README of the acceptance M11/01). The norm of the chapter is
[`08.10-domain.norms.md`](../../spec/08.10-domain.norms.md) N5. The scenarios were moved from the acceptance of M11/12 (04, 05) (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers, the names of the scenarios and the steps are the former ones. The other scenarios of M11/12: 01, 03,
06 — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md), 02 — [chapter 8.3](../3/README.md) (17) (the plan of the move of lesson 8, the appendix). Scenarios 07, 08 are
the coverage audit of P/08; 09, 10 — the coverage audit of P/08, the second pass of Gemini. There are no vectors: the chapter introduces no new functions.

## Stand

The preparation is as the «Preparation of each scenario» of the acceptance of [chapter 8.3](../3/README.md) (formerly the acceptance README of M11/03,
«Setup of each scenario 01–09»), the catalog `testsub`. The doors `holder`, `member`, `resource`, `signer`, `signer2` and
the directives `@domain`, `@start domain`, `@start agent`, `@install domain`, `@start domain second`, `@on`, `@freeze`, `@thaw` are the dictionary of the
«Domain stand» and the common dictionary of directives of the common acceptance README. The runner goes as the human `root` (chapter 8.4). The clock is not accelerated: `LOST_AFTER` 45 s,
`REPORT_EVERY` 5 s, `MARK_REFRESH` 22.5 s, `TURN_TERM` 45 s.

By reading: `whole too large` (N1.5), a holder `url` of several nodes and an unknown outcome of a write with the guard (N1.7),
the price (N1.9).

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and its section «Domain stand»; the expectation of `@carry` is `ok <JSON>`.

In total 6 scenarios / 56 steps.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 04 steps 3 (the second copy is standby), 7 (the second took the queue after the SIGTERM
of the first), 8 (a new report of `m1` is accepted), 9 (the view is full); sc. 05 step 6 (both members knock); sc. 07 step 5 (`m1` knocks);
sc. 08 steps 4, 9, 11 (standby, the taking of the queue, standby after the thaw). Sleeps:

| Sc./step | Sleep | Reason |
|---|---|---|
| 08/7 | 20 s | absence: the frozen copy holds the queue while its version is younger than `TURN_TERM` by the clock of the second — the second does not take the queue earlier (step 8 — 503 `standby`); 20 s is less than `TURN_TERM` − `TURN_RENEW` (35 s) with a margin for the steps |

## Kit seams

[5 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

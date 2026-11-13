# Acceptance P/08.10 — the queue and the price

This English text is the source; the Russian translation `ru/acceptance/10/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are [the common acceptance README](../../../common/acceptance/README.md), the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand)
(a stand of several clusters). The norm of the chapter is
[`08.10-domain.norms.md`](../../spec/08.10-domain.norms.md) N5. There are no vectors: the chapter introduces no new functions.

## Stand

The preparation is as the «Preparation of each scenario» of the acceptance of [chapter 8.3](../3/README.md), the catalog `testsub`. The doors `holder`, `member`, `resource`, `signer`, `signer2` and
the directives `@domain`, `@start domain`, `@start agent`, `@install domain`, `@start domain second`, `@on`, `@freeze`, `@thaw` are the dictionary of the
«Domain stand» and the common dictionary of directives of the common acceptance README. The runner goes as the human `root` (chapter 8.4). The clock is not accelerated: `LOST_AFTER` 45 s,
`REPORT_EVERY` 5 s, `MARK_REFRESH` 22.5 s, `TURN_TERM` 45 s.

By reading: `whole too large` (N1.5), a holder `url` of several nodes and an unknown outcome of a write with the guard (N1.7),
the price (N1.9).

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and its section «Domain stand»; the expectation of `@carry` is `ok <JSON>`.

In total 6 scenarios / 56 steps.

## Kit seams

5 CALL seams  execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

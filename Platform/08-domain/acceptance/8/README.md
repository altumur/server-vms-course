# Acceptance P/08.8 — term, backup, move and handover

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are the section «Domain stand» of [the common acceptance README](../../../common/acceptance/domain-stand.md#domain-stand).
The norm of the chapter is [`08.8-domain.norms.md`](../../spec/08.8-domain.norms.md) N5.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../3/README.md) («Preparation of each scenario»).
The doors `holder`, `holder@<cluster>`, `member`, `signer` and the directives `@domain`, `@start domain on`, `@stop domain`, `@move` are
the dictionary of the «Domain stand». The runner goes as the human `root` (chapter 8.4).


The freeze for the time of a handover, «the newer one has not been read», an abandoned one and its replay, `stolen` the stand does not cause — by reading (N5
of the chapter). `stolen` is the steps of chapter 8.2 «change after theft».

## Inputs

The scenarios of the chapter have no inputs.

## scenarios.tsv

The format is the dictionary of the «Domain stand»; the directives `@move` are `<code> <JSON>`.

In total 13 scenarios / 122 steps.

## Kit seams

CALL seams  execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

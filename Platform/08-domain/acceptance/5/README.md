# Acceptance P/08.5 — books and the index of names (stand)

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`08.5-domain.norms.md`](../../spec/08.5-domain.norms.md) N5. In total 7 scenarios / 72 steps. The delivery of a key with the `sub` of a book and the key `role:` — by reading: the stand does not give a row with `sub` when the book is already assembled.

The assembly on all edges without a stand is checked by the vector [`assemble`](../../vectors/assemble/README.md) (cases and their provenance: the canonical package README).
The refusals of the declaration of a book and of the index of names are the cases `m51_books_*`, `m59_names_*` of the corpus of
[P/02.1](../../../02-installer/acceptance/1/README.md).

## Preparation

As the preparation of the stand of chapter 8.3 ([the acceptance of chapter 8.3](../3/README.md), «Stand», «Preparation of each scenario») with
differences: the catalogue of each cluster is `testsub` and `testsub2` (the order — the «Stand» of the common acceptance README); on each cluster
there run the controllers of both, the worker `w-1` of the manifest `testsub`, the worker `t-1` of the manifest `testsub2` (with the training writer of contributions, N5
of the chapter) and the resource of its own server `srv-<cluster>`; before the steps the store of each cluster has the counter `testsub` `c1-<cluster>`
(its own ref at each: a common `c1` would be contested, and `@domain` would not wait for `complete: true`) and the shelf `testsub2` `sh1`
`{zone: z1, server: srv-<cluster>}`: both are created through the console door of the cluster (`POST /counters {"name": "c1-<cluster>"}` and `POST /testsub2/shelves {"name": "sh1", "zone": "z1", "server": "srv-<cluster>"}` with the keys `prep-<cluster>-counters` and `prep-<cluster>-testsub2-shelves`), and a status other than 201 is a failure of the stand. `console2` at `member` is the prefix `/testsub2`.

Scenarios with people:
- the person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`); the runner goes as them by default: `admin` `*` at the domain door and in the grants row of each cluster of the stand;
- the doors of people and grants `holder` (chapter 8.4, lesson P/10 — neighbours on the stand), the directive `@stop agent` — the domain dictionary.

## scenarios.tsv

The format is the dictionary of the «Stand» and the domain dictionary; the expectation is a subset of fields. The log — by reading ([P/06.2](../../../06-console/spec/06.2-console.norms.md) N1.4).

## Kit seams

2 CALL seams  execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

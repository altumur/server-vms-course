# Acceptance P/08.5 — books and the index of names (stand)

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly — the M11 dictionary of the acceptance README of
M11/01; the plan of the move of lesson 8, V5). The norm of the chapter is
[`08.5-domain.norms.md`](../../spec/08.5-domain.norms.md) N5. The scenarios were moved from the acceptances of M11/05 (01, 03, 05) and
M11/09 (05 → 11) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenario of M11/09:
the number 05 is taken by a scenario of M11/05, it got the number 11 — the next one after the largest number of the sources of the chapter (M11/09
sc. 10; the Architect's decision 2026-10-20, ADR-0083 addendum (14) item 14; the row of `corrections-5.tsv` (historical correction record)). In total 7 scenarios / 72 steps (sc. 14 — ADR-0097 §4, there is no dry run by an implementation; the delivery of a key with the `sub` of a book and the key `role:` — by reading: the stand does not give a row with `sub` when the book is already assembled) (sc. 13 — the coverage audit of P/08, the second pass of Gemini).

The assembly on all edges without a stand is checked by the vector [`assemble`](../../vectors/assemble/README.md) (cases and their provenance: the canonical package README). Sc. 02 `notes-unique` of the acceptance of M11/05 is [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 13, sc. 04 `slot-liveness` — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md) sc. 13.
The refusals of the declaration of a book and of the index of names are the cases `m51_books_*`, `m59_names_*` of the corpus of
[P/02.1](../../../02-installer/acceptance/1/README.md).

## Preparation

As the preparation of the stand of chapter 8.3 ([the acceptance of chapter 8.3](../3/README.md); before the move — the acceptance README of
M11/03, «Setup of each scenario 01–09») with
differences: the catalogue of each cluster is `testsub` and `testsub2` (the order — the «Stand» of the common acceptance README); on each cluster
there run the controllers of both, the worker `w-1` of the manifest `testsub`, the worker `t-1` of the manifest `testsub2` (with the training writer of contributions, N5
of the chapter) and the resource of its own server `srv-<cluster>`; before the steps the store of each cluster has the counter `testsub` `c1-<cluster>`
(its own ref at each: a common `c1` would be contested, and `@domain` would not wait for `complete: true`) and the shelf `testsub2` `sh1`
`{zone: z1, server: srv-<cluster>}`. `console2` at `member` is the prefix `/testsub2`.

Sc. 11 has people too (the former stand of the acceptance of M11/09):
- the person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`); the runner goes as them by default: `admin` `*` at the domain door and in the grants row of each cluster of the stand;
- steps 5, 7, 12, 13 write the grants row of `m2` as a whole and therefore repeat the row of `root`;
- the doors of people and grants `holder` (chapter 8.4, lesson P/10 — neighbours on the stand), the directive `@stop agent` — the domain dictionary.

## scenarios.tsv

The format is the dictionary of the «Stand» and the domain dictionary; the expectation is a subset of fields. In sc. 01 the rows of the book at the member and at the holder
are checked for the ring envelope (`~enc:v2:`) and for the absence of the value of the secret (`!contains`); the log — by reading
([P/06.2](../../../06-console/spec/06.2-console.norms.md) N1.4).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 01/13 | 12 s | absence: the envelope `note_secret` is not resealed in the next generations — two agent passes (`REPORT_EVERY` 5 s); there may be no new generation at all (above), therefore not `@until` |
| 13/10 | 12 s | absence: the key `alice` (the name of a person) is not delivered to `m2` — two agent passes (`REPORT_EVERY` 5 s) after the delivery of the book with `t7` (step 9) |

The other waits for an event are `@until` by a sign.

## Kit seams

[2 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

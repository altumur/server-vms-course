# Acceptance P/08.5 — books and the index of names (stand)

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly — the M11 dictionary of the acceptance README of
M11/01; the plan of the move of lesson 8, V5). The norm of the chapter is
[`08.5-domain.norms.md`](../../spec/08.5-domain.norms.md) N5. The scenarios were moved from the acceptances of M11/05 (01, 03, 05) and
M11/09 (05 → 11) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenario of M11/09:
the number 05 is taken by a scenario of M11/05, it got the number 11 — the next one after the largest number of the sources of the chapter (M11/09
sc. 10; the Architect's decision 2026-10-20, ADR-0083 addendum (14) item 14; the row of `corrections-5.tsv` (historical correction record)). In total 7 scenarios / 72 steps (sc. 14 — ADR-0097 §4, there is no dry run by an implementation; the delivery of a key with the `sub` of a book and the key `role:` — by reading: the stand does not give a row with `sub` when the book is already assembled) (sc. 13 — the coverage audit of P/08, the second pass of Gemini).

The assembly on all edges without a stand is checked by the vector [`assemble`](../../vectors/assemble/README.md) (17 rows, the former sc. 06
of the acceptance of M11/05). Sc. 02 `notes-unique` of the acceptance of M11/05 is [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 13, sc. 04 `slot-liveness` — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md) sc. 13.
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

- Sc. 01 step 18 — the name of the book in the path is not decoded (`%72olls` is not `rolls`; the M11 reconciliation 05–08, B6).
- Sc. 01 steps 11–15 (`seal_reuse`, [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) N1.2 `seal_reuse`) compare not the generation number of `m1`, but the envelope
  `note_secret` of the contribution `t1` in two generations 12 s apart: the same envelope. A new generation in this time is possible — from
  `domain/backup-taken` of the backup copy of chapter 8.8 (`m1` is a keeper), — and the step does not depend on the moment of the copy.
- Sc. 01 steps 3–5, 10, 18 read the book door of the cluster console (the OpenAPI of lesson 6, chapter P/06.7) — a neighbour on the
  stand; steps 16–17 — the leaving of a member (chapter 8.3; the door of the domain console — lesson P/10) and the removal of the row of the former member (N1.3 `write`).
- Sc. 11 — the index of names of the book `notes` of `testsub2`: the contribution `t7` from `m1` with the recipient `m2`. The silence of `m1` (`@stop agent`,
  longer than `LOST_AFTER`) makes the index unknown: the creation of a person and a new grant row — 503, the removal of a row — not.
- Sc. 12 — a subject without a name (the neighbour chapter 8.4, N3 «reconciliation»; C08-GRANTS-ORPHAN-01): the grant `t7` (`view`) at `m2`, then the contribution `t7`
  is deleted (`DELETE /tallies/t7` on `m1`) — the index is known even without `t7`; the holder's reconciliation removes the row `t7`
  (step 7), and the person `t7` is created without the grants of the former subject (steps 8–9).
- Sc. 13 (the coverage audit of P/08, the second pass of Gemini, the draft G05 `e32df6f8b`) — the index is known (step 4): a new grant row with the subject `zed`, who
  is neither among the people nor in the indexes, — 400 `unknown subject` (N1.7 `checks`). The contribution `alice` in `notes` with the person `alice`
  (the reverse rule, N1.7 `reverse`): the key is in `view.books.testsub2/notes.person_names` and is not delivered to `m2`, although
  `alice` has the grant `view` there (the delivery condition is met). Step 9 waits for the delivery of `t7` — `m2` has the book; step 11 — two
  agent passes after it `alice` is absent. The silence of `m1` (steps 12–13) makes the index unknown, but a new row of a person
  (`alice` `edit`) does not wait for the index, and the former row `t7` is not checked — 200 (N1.7 `checks`; the M11 reconciliation, P5, P6).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 01/13 | 12 s | absence: the envelope `note_secret` is not resealed in the next generations — two agent passes (`REPORT_EVERY` 5 s); there may be no new generation at all (above), therefore not `@until` |
| 13/10 | 12 s | absence: the key `alice` (the name of a person) is not delivered to `m2` — two agent passes (`REPORT_EVERY` 5 s) after the delivery of the book with `t7` (step 9) |

The other waits for an event are `@until` by a sign.

## Kit seams

[2 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

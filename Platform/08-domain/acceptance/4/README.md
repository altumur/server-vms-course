# Acceptance P/08.4 — people and grants (stand)

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly — the M11 dictionary of the acceptance README of
M11/01; the plan of the move of lesson 8, V5). The norm of the chapter is
[`08.4-domain.norms.md`](../../spec/08.4-domain.norms.md) N5. Scenarios 01, 02, 04, 08, 09, 10 were moved from the acceptance of M11/09
(stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones (there is one source, the numbers do not collide).
In total 33 scenarios / 498 steps (sc. 23 — versions and the replay memory, ADR-0094 B3, B4; sc. 21, 22 — the feed `GET /changes` under a grant, ADR-0094 B2; sc. 24–37 — the increment of rights ADR-0097–ADR-0100, **there is no dry run by an implementation**, and the steps of sc. 02, 17 are rewritten for the role `admin`; sc. 13–15 — the coverage audit of P/08, audit-kimi 1e9929d51; sc. 16–19 — the coverage audit of P/08, the second pass of Gemini; sc. 12 `pass-need` — 9 steps, `need` of the route `door.pass` at the cluster console, C06-PASS-NEED-51-01; sc. 11 `events-view` — 10 steps, the visibility of `GET /events` under a narrow grant, C06-EVENTS-VIEW-33-01; steps 01/22–24 — the White_Space boundary of a name, the review analysis of stage B 8–10, № 18).

The function `may` without a stand is the vectors [`may`](../../../common/vectors/may/README.md) (the canonical package README lists the cases).
The scenario M11/09 07 (`07-may`, 24 steps) is the same cases, it is not moved (the Architect's decision 2026-10-20 on the plans
8–10, item 1; the row of `corrections-4.tsv` (historical correction record)). The other scenarios of M11/09 are at the neighbours: 03 (`break-glass`) and 06 (`domain-keys`) —
[the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) (14, 06); 05 (`names-index`) — [chapter 8.5](../5/README.md) (number 11).

## Stand

The preparation is as the acceptance of [chapter 8.5](../5/README.md) (formerly the acceptance README of
M11/05): the catalogue `testsub` and `testsub2`, the counter
`c1-<cluster>` and the shelf `sh1` on each cluster, the training writer of contributions. The doors `holder`, `member`, `signer` and the directives
`@domain`, `@person`, `@stop agent` — the section «Domain stand» of the common acceptance README.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`): an assignment of the role `admin`, there is no direct row in `domain/grants/domain` (ADR-0100 §5). The runner goes as them by default:
  step 4a at the domain door and `admin` `*` in the grants row of each cluster of the stand.
- Scenario 29 step 13: moving `root` to an assignment through a group gives a new `at`, and the former token does not serve step 4a (N1.3c `tokens`); `iat` and `at` are compared by whole seconds (the right contract step 4a), therefore no sleep is needed.
- Scenario 27 steps 24–26: the mark is written directly, the step goes in the window before the nearest pass, as sc. 10.
- `@person -` is without a token, therefore sc. 24–33 return `root` by the directive `@person root …`.
- Scenario 30 step 17 writes `domain/roles/admin` past the door (an unreadable row, `name` not by the form), step 19 restores it.
- Scenarios 01, 02 write the grants rows as a whole and therefore repeat the row of `root`.
- `$ta` is the token of `ann` from the login answer; the steps with `@header Authorization: Bearer $ta` go on her behalf, the others — on behalf of
  the current person.

An equal answer time to an unknown and a wrong one, the log and the limit band by the address of the client from the domain console (not by its
TCP peer) — by reading (the norms N5).

The steps at the cluster console (`member … console`: `/session` with grants, reading and writing a unit under a token, 401 without a token) and
step 02/23 (`holder GET /domain/grants` — a door of the domain console) are neighbours on the stand: their norms are the cluster console (a late
layer of lesson P/06) and lesson P/10; the outcome of the scenarios is the rows of people and grants of the process `domain`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the section «Domain stand» of the common acceptance README; the expectation is a subset of fields.

## Kit seams

[CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

# Acceptance P/08.8 — term, backup, move and handover

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are the section «Domain stand» of [the common acceptance README](../../../common/acceptance/README.md#domain-stand)
(before the merge, the dictionary of the M11 README of the acceptance M11/01).
The norm of the chapter is [`08.8-domain.norms.md`](../../spec/08.8-domain.norms.md) N5. The scenarios and the text below were moved from the acceptance of
M11/10 (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers of the scenarios and the steps are the former ones. Scenarios 05 (`record`) and 07 (`ask-sig`) are removed — the same cases are in
the packages [`common/vectors/record`](../../../common/vectors/record/README.md) and
[`common/vectors/ask-sig`](../../../common/vectors/ask-sig/README.md) (the plan of the move of lesson 8, V1); scenario 06 (`follow`) is removed — the package
[`follow`](../../../09-agent/vectors/follow/README.md), 11 — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md); 01 —
[the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 15.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../3/README.md) («Preparation of each scenario»; from the acceptance README of M11/03).
The doors `holder`, `holder@<cluster>`, `member`, `signer` and the directives `@domain`, `@start domain on`, `@stop domain`, `@move` are
the dictionary of the «Domain stand». The runner goes as the human `root` (chapter 8.4).

- **Scenario 02.**
  - The grant is issued to the human `ann`, who is created first (chapter 8.4: the subject of a grant is a human). An edit of the grants changes
    the state; `@sleep 45` — `BACKUP_EVERY` and the pass of the keeper's agent, and `$r` already names the backup with this
    edit.
  - `@stop domain` switches the holder off, `@start domain on m1` brings up an empty signer on `m1`, `@move m1` moves
    by the installation file.
  - `@start domain` returns `hold`: its agent brings the term record 2, the process yields. Step 13 waits (`@until`) for its forgotten keys — a look at
    its own store.
- **Scenario 04.** The handover target is `m1`. `m9` is not a member.

The freeze for the time of a handover, «the newer one has not been read», an abandoned one and its replay, `stolen` the stand does not cause — by reading (N5
of the chapter). `stolen` is the steps of chapter 8.2 «change after theft». The cancellation of a handover — sc. 13.

## Inputs

The scenarios of the chapter have no inputs. The inputs `record-*` and `ask-sig-*` of the acceptance of M11/10 are removed together with scenarios 05 and 07: the same
cases are the tables of the packages `record` and `ask-sig` (the input is JSON text in a row). The inputs `follow-*` are removed — the same cases are in
the package [`follow`](../../../09-agent/vectors/follow/README.md).

## scenarios.tsv

The format is the dictionary of the «Domain stand»; the directives `@move` are `<code> <JSON>`.

In total 13 scenarios / 122 steps. Sc. 18 — ADR-0098 §5, there is no dry run by an implementation.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 02 step 13, sc. 09 step 7, sc. 12 step 8 wait for the displaced process to have forgotten the keys
(`domain/signer` `forgotten`, N1.6 `forget` — unconditionally at the moment of yielding); sc. 13 step 3 — for a view without `frozen_for`.
The remaining sleeps:

| Sc./step | Sleep | Reason |
|---|---|---|
| 09/2, 10/2 | 35 s | time before an action: the domain went quiet — after the acceptance of the members the next backup is not earlier than `BACKUP_EVERY` 30 s, it is brought by the agent's pass 5 s; `$r` is the last copy (silence is not observed: «there will be no more copies» is an absence) |
| 18/6 | 45 s | like 02/4: a copy with roles and the rows `role:` — not earlier than `BACKUP_EVERY` and the agent's pass |
| 18/13 | 7 s | a check of absence: the first pass of the new holder did not remove the rows `role:` (the length — like 13/9 of acceptance 8.4: a pass of 3 s and a margin) |
| 02/4 | 45 s | time before an action: a copy with the grants edit — not earlier than `BACKUP_EVERY` 30 s from the previous one, the holder's pass 3 s and the keeper agent's 5 s, a margin |
| 08/3, 14/3 | 6 s | absence: a forged record does not displace the holder — the check of the record at each pass of the holder (`VIEW_EVERY` 3 s), two passes |
| 10/10 | 40 s | time before an action: a copy of term 2 with the user `bob` — not earlier than `BACKUP_EVERY` 30 s from the first copy of the term, the passes of the holder and the agent |

## Kit seams

[CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

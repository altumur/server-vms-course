# Acceptance P/08.8 — term, backup, move and handover

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are the section «Domain stand» of [the common acceptance README](../../../common/acceptance/README.md#domain-stand)
(before the merge, the dictionary of the М11 README of the acceptance М11/01).
The norm of the chapter is [`08.8-domain.norms.md`](../../spec/08.8-domain.norms.md) N5. The scenarios and the text below were moved from the acceptance of
М11/10 (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers of the scenarios and the steps are the former ones. Scenarios 05 (`record`) and 07 (`ask-sig`) are removed — the same cases are in
the packages [`common/vectors/record`](../../../common/vectors/record/README.md) and
[`common/vectors/ask-sig`](../../../common/vectors/ask-sig/README.md) (the plan of the move of lesson 8, V1); scenario 06 (`follow`) is removed — the package
[`follow`](../../../09-agent/vectors/follow/README.md), 11 — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md); 01 —
[the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 15.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../3/README.md) («Preparation of each scenario»; from the acceptance README of М11/03).
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
- **Scenario 03.** `copy=1.999` — nobody has such a backup. Step 6 — a move with `why` (N1.8 step 6, ER) — 200
  at any outcome of the choice of a copy. Both 409 branches without `why` («из ничего» and «сосед не ответил») — by reading: the stand does not give
  «копии нет нигде» deterministically — the first copy is made in the first pass of the holder (N1.5 first), and `m1` is a keeper
  (BACKUP_HOLDERS 2 of two members) and holds it in its store, so even with silent neighbours the move restores
  from its own. Sc. 12 step 6 — with `why`: a backup of term 2 may not exist yet. The branch «сосед не ответил» is the stand
  of the fourth cluster ([the TLS stand](../../../common/acceptance/tls/README.md) «Четвёртый кластер», item 9).
- **Scenario 04.** The handover target is `m1`. `m9` is not a member.

The freeze for the time of a handover, «новее не прочитана», an abandoned one and its replay, `stolen` the stand does not cause — by reading (N5
of the chapter). `stolen` is the steps of chapter 8.2 «change after theft». The cancellation of a handover — sc. 13.

- **Scenarios 13, 14** (the coverage audit of P/08, audit-kimi 1e9929d51):
  - 13 — a handover to `m1` without a signer (`@start domain on m1` is not done): the console of `m1` without `SIGNER_URL` answers
    `POST /api/prepare` with 404 (P/06.7 N1.8 `codes`), and if `m1` did not take the copy within `HANDOVER_WAIT`, the refusal comes at step 3 —
    in both cases N1.7 orders to lift the freeze and answer 409 `called off` (steps 3–5, HF;
    C08-HANDOVER-STEPS-CALLED-OFF-01). `detail` is not compared: at step 4 it «называет шаг и причину», the norm gives no
    text. After the refusal: in the view term 1 at `hold`, no `frozen_for` (`@until` — the next pass of the view), an edit of placement
    is accepted (not 503 `frozen`), the keys are not forgotten. The answer of step 2 comes no later than `HANDOVER_WAIT` (30 s) and 10 s of `prepare`.
  - 14 — like sc. 08, but the term of the record equals its own (1, without `restored_from` — the form of term 1) and the holder is another one (`m1`):
    the record does not pass `record` (the issuer is not from the set), there is no yielding (N1.6 `yields`, G4): the edit — 200, the login — 200, and not
    409 `deposed`, the keys are not forgotten.

- **Scenarios 09, 10, 12** (the Quint model М11, scenarios Q1, Q2, Q4): 09 — a move with the former holder alive: its agent
  takes the move set into the follow set, `hold` yields, forgets the keys, `domain/keys` at `hold` is the new set (G1);
  10 — a move to a member with the old set: the copy (2, r2) of a neighbour is checked by the move set, term 3, without a rollback (RB);
  12 — a handover, then a move (term 3), both former ones are displaced and forgot the keys. Scenario 11 (Q3, a revocation does not revive after
  a move — RV) — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md).

## Inputs

The scenarios of the chapter have no inputs. The inputs `record-*` and `ask-sig-*` of the acceptance of М11/10 are removed together with scenarios 05 and 07: the same
cases are the tables of the packages `record` and `ask-sig` (the input is JSON text in a row). The inputs `follow-*` are removed — the same cases are in
the package [`follow`](../../../09-agent/vectors/follow/README.md).

## scenarios.tsv

The format is the dictionary of the «Domain stand»; the directives `@move` are `<code> <JSON>`.

Sc. 15–17 (the coverage audit of P/08, the second pass of Gemini, the draft G09 `e32df6f8b`, rewritten):
- sc. 15 — `POST /domain/stranded/apply` (N1.6 `apply`): at the acting holder — 409; after a handover to `m1` (`stranded`
  is empty) the displaced `hold` has no element — 404; the row `domain/stranded` is spoiled past the door (`doc` is not JSON) — 503
  `unavailable`, nothing is applied (the outcomes of `domain/stranded`, G-40). A replay of an edit at the new holder and 400 «redo it on
  the new holder» for an element that is not an edit — by reading: the stand does not create abandoned ones.
- sc. 16 — `POST /api/take` (N1.7 `take`, the order): at the domain holder — 409 before the body form; at a signer without keys
  on `m1` (`@start domain on m1`; C08-TURN-WITHOUT-SIGNER-01 — the door answers on the merits) the body `{}` — 400.
  «Ничего не подготовлено» — by reading: a body of the form carries the `grant` of the term record and `keys_sealed`.
- sc. 17 — the restore is exact (N1.8 step 7, C08-RESTORE-EXACT-01): `m1` has before the move its own unreadable row of the family
  `domain/users/*` (`ghost`, without the fields of a human row), which is not in the backup; the move to `m1` deletes it.
  Step 2 waits for any backup of term 1 at the keeper `m1` (there are no edits after `@domain` — the copy number is not bound).

Not taken from the draft G09: `POST /api/prepare` at the holder «409» — the signature of the request (`missing`, `bad_time`) is checked
earlier (400); the move of an object not of the form (`raw`, C08-BACKUP-JSON-99) — objects are written by the holder's pass, the stand does not put an object not
of the form into a copy (the vectors `record`, the rows C08-BACKUP-JSON-99).

In total 13 scenarios / 122 steps. Sc. 18 — ADR-0098 §5, there is no dry run by an implementation.

## `journal/corrections-8.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are the log
`corrections.tsv` of the acceptance of М11/10 as a whole, with the former paths and numbers (they are resolved by `Platform/common/id-map.tsv`; the plan
of the move of lesson 8, § 3 «Журналы»: the log of the source goes into all directories that take its scenarios).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 02 step 13, sc. 09 step 7, sc. 12 step 8 wait for the displaced process to have forgotten the keys
(`domain/signer` `forgotten`, N1.6 `forget` — unconditionally at the moment of yielding); sc. 13 step 3 — for a view without `frozen_for`.
The remaining sleeps:

| Sc./step | Sleep | Reason |
|---|---|---|
| 09/2, 10/2 | 35 s | time before an action: the domain went quiet — after the acceptance of the members the next backup is not earlier than `BACKUP_EVERY` 30 s, it is brought by the agent's pass 5 s; `$r` is the last copy (silence is not observed: «копий больше не будет» is an absence) |
| 18/6 | 45 s | like 02/4: a copy with roles and the rows `role:` — not earlier than `BACKUP_EVERY` and the agent's pass |
| 18/13 | 7 s | a check of absence: the first pass of the new holder did not remove the rows `role:` (the length — like 13/9 of acceptance 8.4: a pass of 3 s and a margin) |
| 02/4 | 45 s | time before an action: a copy with the grants edit — not earlier than `BACKUP_EVERY` 30 s from the previous one, the holder's pass 3 s and the keeper agent's 5 s, a margin |
| 08/3, 14/3 | 6 s | absence: a forged record does not displace the holder — the check of the record at each pass of the holder (`VIEW_EVERY` 3 s), two passes |
| 10/10 | 40 s | time before an action: a copy of term 2 with the user `bob` — not earlier than `BACKUP_EVERY` 30 s from the first copy of the term, the passes of the holder and the agent |

## Kit seams

[3 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

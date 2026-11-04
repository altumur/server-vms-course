# Acceptance P/08.4 — people and grants (stand)

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей),
the section [«Стенд домена»](../../../../common/acceptance/README.md#стенд-домена) (a stand of several clusters; formerly — the М11 dictionary of the acceptance README of
М11/01; the plan of the move of lesson 8, В5). The norm of the chapter is
[`08.4-domain.norms.md`](../../../spec/08.4-domain.norms.md) Н5. Scenarios 01, 02, 04, 08, 09, 10 were moved from the acceptance of М11/09
(stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones (there is one source, the numbers do not collide).
In total 33 scenarios / 498 steps (sc. 23 — versions and the replay memory, ADR-0094 B3, B4; sc. 21, 22 — the feed `GET /changes` under a grant, ADR-0094 B2; sc. 24–37 — the increment of rights ADR-0097–ADR-0100, **there is no dry run by an implementation**, and the steps of sc. 02, 17 are rewritten for the role `admin`; sc. 13–15 — the coverage audit of P/08, audit-kimi 1e9929d51; sc. 16–19 — the coverage audit of P/08, the second pass of Gemini; sc. 12 `pass-need` — 9 steps, `need` of the route `door.pass` at the cluster console, C06-PASS-NEED-51-01; sc. 11 `events-view` — 10 steps, the visibility of `GET /events` under a narrow grant, C06-EVENTS-VIEW-33-01; steps 01/22–24 — the White_Space boundary of a name, the review analysis of stage B 8–10, № 18; steps 01/25–26 — `GET /drain` with a narrow grant — 403: the drain requires `view` on `*`, C06-DRAIN-VISIBILITY-33-01; steps 01/27–33 — `POST /marks` without the grant `edit` — 403 before the body, a narrow `edit unit:` — one's own unit 2xx, a foreign one 403, C06-BODYEDIT-SCOPE-33-01).

The function `may` without a stand is the vectors [`may`](../../../../common/vectors/may/README.md) (106 rows; the owner is chapter 8.4).
The scenario М11/09 07 (`07-may`, 24 steps) is the same cases, it is not moved (the Architect's decision 2026-10-20 on the plans
8–10, item 1; the row of `corrections.tsv`). The other scenarios of М11/09 are at the neighbours: 03 (`break-glass`) and 06 (`domain-keys`) —
[the acceptance of chapter 6.7](../../../../06-console/acceptance/7/README.md) (14, 06); 05 (`names-index`) — [chapter 8.5](../../5/README.md) (number 11).

## Stand

The preparation is as the acceptance of [chapter 8.5](../../5/README.md) (formerly the acceptance README of
М11/05): the catalogue `testsub` and `testsub2`, the counter
`c1-<кластер>` and the shelf `sh1` on each cluster, the training writer of contributions. The doors `holder`, `member`, `signer` and the directives
`@domain`, `@person`, `@stop agent` — the section «Domain stand» of the common acceptance README.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`): an assignment of the role `admin`, there is no direct row in `domain/grants/domain` (ADR-0100 §5). The runner goes as them by default:
  step 4а at the domain door and `admin` `*` in the grants row of each cluster of the stand.
- Scenario 29 step 13: moving `root` to an assignment through a group gives a new `at`, and the former token does not serve step 4а (Н1.3в `tokens`); `iat` and `at` are compared by whole seconds (the right contract step 4а), therefore no sleep is needed.
- Scenario 27 steps 24–26: the mark is written directly, the step goes in the window before the nearest pass, as sc. 10.
- `@person -` is without a token, therefore sc. 24–33 return `root` by the directive `@person root …`.
- Scenario 30 step 17 writes `domain/roles/admin` past the door (an unreadable row, `name` not by the form), step 19 restores it.
- Scenarios 01, 02 write the grants rows as a whole and therefore repeat the row of `root`.
- Scenario 01 step 12 — `until` with seven fraction digits at the input is stored rounded to thousandths: 4102444800.1234565 →
  4102444800.123 (Н1.3 until; the Architect's decision on the М11 reconciliation, P8).
- Scenario 01 steps 22–24 — the boundary of white space in the name of a person (Н1.1 `name`, the property White_Space; the edit `f31941fb2`):
  again on behalf of `root` (`@person root …`), the name `a\u0085b` (U+0085 is white space) — 400 `bad name`, as `a|b` of steps 7–8;
  `a\ufeffb` (U+FEFF is not white space) — by the other rules, 201. In `request` and `expect` the character is written by JSON escaping
  `\u0085`, `\ufeff` (the review analysis of stage B 8–10, № 18).
- `$ta` is the token of `ann` from the login answer; the steps with `@header Authorization: Bearer $ta` go on her behalf, the others — on behalf of
  the current person.
- Scenario 02:
  - steps 05–07 — a forged token `@spoil($ta)`: at the member console, at the door of people and at the revocation — 401 (a check of the signature, not
    only of the presence of a token);
  - steps 09–11 — disabling: at the holder `domain/disabled`, at `m1` — a refusal after the answer to the agent;
  - steps 15–16 — revocation: `domain/revoked` reaches `m1`.
- Scenario 04 — the limit of the login door of the process `domain`. Step 8 — the counting key is the pair (address, name): another name from the same
  address after 429 at `root` gets an ordinary 401, not 429 (P/08.4 Н1.10 `key`; ADR-0083 addendum (19) item 2, the review analysis of
  ADR-0090, № 26).
- Scenario 13 — an unreadable row of a person (Н1.1 `unreadable`): `ann` with the grant `view` at `m1` is disabled, then the row
  `domain/users/ann` is rewritten past the writer with `name: bob` (≠ the name of the key; `disabled: "false"` and a secret that the ring does not
  open, — a non-strict reader would lift the disabling and so give itself away). The login of `ann` — 503 `unavailable`, not 401 (Н1.2
  `check`, `Г-42`); the login of `root` — 200 (the other rows serve). Step 9 — a sleep of 7 s (two reconciliation passes, `VIEW_EVERY` 3 s):
  `domain/disabled` is still `["ann"]`, the grant of `ann` is not removed (the reconciliation of subjects without a name: the row exists, but is unreadable —
  the person exists, C08-GRANTS-ORPHAN-01). `DELETE` deletes the unreadable row too, removes the grant (`grants_changed: ["m1"]`);
  then `domain/disabled` is `[]` (the reconciliation by the flags of the rows of people), the login of `ann` — an ordinary 401. The norm does not name an edit `PUT` of an unreadable
  row (Н3 «дверь людей» step 7: «нет — 404» against the rule «Unreadable row») — there is no step.
- Scenario 14 — the common ceiling (Н1.10 `ceiling`, the contract of the gate and the forwarding «Attempt limit»): the names `n1`–`n4` with
  five failures each (the key is the pair (address, name): the fifth failure of each key still passes, `per_address` does not fire) — 20
  refusals of all keys; a fresh name `n5` — the first attempt passes (401: «не чаще одной попытки в 60 с» does not yet act for a key without an attempt),
  the second right after it — 429 `too many attempts`. `Retry-After` is not compared in the TSV (the number of seconds is not
  predicted). The steps are logins in a row, the ceiling window of 60 s does not expire.
- Scenario 15 — the cluster in the grants path byte for byte (Н1.3, the М11 reconciliation, P13): `PUT /domain/grants/m%31` — 400 `bad name`
  (`%` is not in the grammar of a member), the row `m1` is the former one (the rejected edit has `view`), there is no row `m%31`.

An equal answer time to an unknown and a wrong one, the log and the limit band by the address of the client from the domain console (not by its
TCP peer) — by reading (the norms Н5).

The steps at the cluster console (`member … console`: `/session` with grants, reading and writing a unit under a token, 401 without a token) and
step 02/23 (`holder GET /domain/grants` — a door of the domain console) are neighbours on the stand: their norms are the cluster console (a late
layer of lesson P/06) and lesson P/10; the outcome of the scenarios is the rows of people and grants of the process `domain`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the section «Domain stand» of the common acceptance README; the expectation is a subset of fields.

| № | Scenario | Steps | What |
|---|---|---|---|
| 01 | `login-people-grants` | 33 | login, one refusal to an unknown and a wrong one; people — 201, 400, 409; a name with U+0085 — 400 `bad name`, with U+FEFF — 201; the grant `unit:` — `/session` with grants, reading, 403 of a write and of another cluster, 401 without a token; `until` rounded |
| 02 | `disable-revoke-last-admin` | 23 | a forged token — 401; disabling and enabling; revocation; the last administrator — 409 |
| 04 | `login-limit` | 8 | five failures, then 429 for the right pair too; another name from the same address — 401 |
| 08 | `grant-by-kept` | 7 | a row that matched the former one keeps its `by`; a new one — the name of the writer |
| 09 | `deleting-mark` | 6 | the mark `domain/deleting/dz` is written directly — the pass reconciliation removes the grant row `dz` and the mark |
| 10 | `deleting-any-mark` | 10 | a mark of any form is removed by the pass, the pass does not stall; a mark without a person — 409 `being deleted`, `POST` 409 `exists`; after the removal — 201 |
| 11 | `events-view` | 10 | ann with `view unit:testsub/c1`: three rows — an alarm `of=testsub/c2` (not visible), an observation and a mark of the console of root `of=testsub/c1` (visible); without `limit` — two visible, `truncated` 0; `limit=1` — the first visible (the mark), `truncated` 1; `complete` does not change (`@append event` under `@on m1`) |
| 12 | `pass-need` | 9 | ann with `view unit:testsub2/t1` at the console of the cluster `m1`: `GET /entries` without `?unit=` and with `?unit=testsub2/t1` passes the gate — 503 `{"error": "denied"}`, `detail` «no worker of testsub2 with a door is heard» (the word — `GP-L03`, the Architect's decision 2026-10-28) (there is no worker of `testsub2` on the stand); with `?unit=testsub2/t2` — 403; `POST /entries` — `entries` is not named in `rights.routes`, `admin` is needed — 403; the side of the domain console (`"*"` without `?unit=`) — by reading: `testsub2` has no worker on the domain and no forwarding route of the domain console |
| 13 | `garbled-person-row` | 16 | an unreadable row of a person: login — 503, `domain/disabled` and the grant are not removed; `DELETE` deletes it and the grant; then `disabled` is empty, login — 401 |
| 14 | `login-ceiling` | 23 | four names with five failures each — 20 refusals; a fresh name — 401, its second attempt — 429 |
| 15 | `grants-cluster-no-decode` | 5 | `PUT /domain/grants/m%31` — 400 `bad name`; the row `m1` is the former one, there is no `m%31` |
| 16 | `until-by-value` | 5 | `until` by value: without `until` and `0.0` — one row, a repeat — 400 `bad line`; `…0011` and `…0014` round into one — 400; `0.0001` is written `0.001` |
| 17 | `last-admin-garbled` | 7 | a second administrator with an unreadable row of a person is not counted as an admin: removing `root` from `assigned` of the role `admin` and disabling `root` — 409 `last admin`; `DELETE` of the unreadable one — 200 |
| 18 | `garbled-grants-row` | 6 | an unreadable row `domain/grants/m1`: `POST /domain/users` — 503, an edit `PUT` over it — 503; the row is fixed past the door (`delete` under `domain/` is forbidden to `admin` too) — 201 |
| 19 | `garbled-break-glass` | 7 | an unreadable `domain/break-glass/m1`: `GET /domain/break-glass` — the key `m1` is there, `{}`; `PUT` writes the row anew — `set_at` again |
| 20 | `batch-rights` | 18 | ann with `admin unit:testsub/c1-m1` at the console of `m1`; steps 16–17 — tombstones by `about`: one's own unit — 200, a foreign one — 403; step 18 — `GET /testsub/next_id` as a creation of rows — 403 (ADR-0094 B4); the batch door (ADR-0094 B9): the second row without a right — 403 of the whole batch, the indexes of both are the former ones; the guard `c2-m1` without `view` — 412 `row moved` with `index: ""`, as for an absent row; one's own row — 200 `{written: 1}` |
| 21 | `changes-rights` | 23 | the feed `GET /changes` of the member console under a narrow grant (ADR-0094 B2): a change of the set of the grant lines — a reset; the number of another person; there is no grant — 403 |
| 22 | `changes-labels` | 21 | the feed under a narrow grant by marks (ADR-0094 B2): a new row with a mark is visible without a reset, a row without a mark is not visible, a change of the mark of the unit — a reset |
| 23 | `versions-and-repeats` | 30 | the versions and the replay memory of the doors of people (chapter 8.0 Н1.9, ADR-0094 B3, B4) |
| 24 | `grant-line-forms` | 10 | the forms of a line: `sub`, `folder:`, `none`, a repeat, the order (ADR-0097); there is no dry run |
| 25 | `sub-of-each-check` | 15 | `sub` of each check: `/drain`, a batch, `/marks`; there is no dry run |
| 26 | `events-by-sub` | 12 | `/events` by the `sub` of an event; there is no dry run |
| 27 | `roles-and-groups` | 26 | groups, roles, `/session` with `role`, deletion of a person and a role; there is no dry run |
| 28 | `person-card-and-term` | 15 | `email` by right, the term of an account; there is no dry run |
| 29 | `last-admin-by-role` | 18 | the last administrator by role and group, `builtin`; there is no dry run |
| 30 | `manager-of-people` | 21 | the manager: `admin only`, the status of the target, the body before the target; there is no dry run |
| 31 | `password-set-by-non-admin` | 13 | `pw_by`: an assignment and membership in a group; there is no dry run |
| 32 | `domain-batch` | 16 | `POST /domain/batch`: the difference, `cas`, the outcome of the batch; there is no dry run |
| 33 | `folder-rights` | 23 | the write rights of folders ADR-0097 §6, ADR-0099 §4; there is no dry run |
| 34 | `changes-folders` | 15 | the feed: a change of the composition and deletion of a folder — a reset to a subscriber with the line `folder:`; there is no dry run |
| 35 | `changes-folder-rows` | 15 | the feed under a narrow grant: a message about a folder, a tombstone; there is no dry run |
| 36 | `changes-role-assignment` | 12 | the removal of a role assignment — a reset; there is no dry run |
| 37 | `versions-groups-roles` | 20 | the versions and the memory of groups, roles, a batch; there is no dry run |

Sc. 09 — the deletion mark `domain/deleting/<имя>`: the mark is written directly into the holder's store, the pass reconciliation (chapter 8.4 Н3,
«Обрыв шага 9») removes the grant rows by it and deletes it; a break of `DELETE` after the row of the person — by reading (the stand debt
item 3, ADR-0083 addendum (9)). Sc. 10 (the М11 reconciliation, P1, P3) — a mark of any form: `a|b` (a name not by the grammar) and `aa` with
non-empty `items` are removed by the pass, the pass does not stall; the mark `zz` without a person — an edit of a grant with the line `zz` 409
`being deleted` and `POST` 409 `exists` before the checks of names. Steps 7–8 go right after the writing of the mark: the window is up to the nearest
pass (3 s), the reconciliation removes the mark not earlier; after the removal (step 9) the name is free — 201.

Sc. 16–19 (the coverage audit of P/08, the second pass of Gemini, the draft G04 `e32df6f8b`, rewritten):
- sc. 16 — `until` of a grant line by value (Н1.3 `lines`, the М11 reconciliation, P7, P9): a line without `until` and with `until: 0.0` are one
  line, a repeat — 400 `bad line`; `4102444800.0011` and `4102444800.0014` round to thousandths into `4102444800.001` — a repeat,
  400; a positive `0.0001` that would round into 0 is written `0.001` (C08-UNTIL-REWRITE-01); the lines of the answer are by
  `subject` (`ann` before `root`).
- sc. 17 — `last_admin` (Н1.3, C08-LAST-ADMIN-UNREADABLE-01): `ann` is the second administrator of `domain/grants/domain`, her row is
  spoiled past the door (`name` ≠ the name of the key, as sc. 13); removing `root` and disabling `root` — 409 `last admin`: an unreadable
  row of a person is not counted as an admin. `DELETE` deletes it too (Н3 «дверь людей» step 7).
- sc. 18 — an unreadable row `domain/grants/m1` (`doc` is not JSON): `POST /domain/users` — 503 `unavailable` (Н3 «дверь людей»
  step 7а, C08-GRANTS-ORPHAN-01), an edit `PUT /domain/grants/m1` over it — 503 (the outcomes of `domain/grants`, `Г-25`: an edit
  over an unreadable row is not written); the row is fixed through `admin.sock` by a write by the form (`doc` with an empty `lines`; `delete` under `domain/` is forbidden to `admin` too, C09-AUDIT-HEAL-NOT-DELETE-01) — the person is created.

- sc. 19 — an unreadable row `domain/break-glass/m1` (no `pwhash_secret`): `GET /domain/break-glass` keeps the key of the cluster
  without `set_at` — exactly `{}` (the outcomes of the family, `Г-23`, C08-BREAK-GLASS-UNREAD-KEY-01; the witness `cammeta-go` omits the key —
  a defect of the witness); `PUT` does not read the row and writes it anew — the door has no refusal for this.

Not taken from the draft G04: healing the grants row by the door `PUT` (expectation 200): the norm (`Г-25`) requires 503.

Sc. 21, 22 — the feed `GET /changes` of the member console under a narrow grant (ADR-0094 B2; P/06.1 Н2 «Change feed»). The subscription goes before the creation of rows: ann takes a number, root creates units, therefore the message about a creation does not fall outside the expected array. root writes the foreign row first: if the message about one's own has already come, the tick saw the foreign one too, so it was cut off by the filter, not by time. Sc. 21: step 17 — a change of the set of the grant lines gives a reset, step 20 — the number of another person, step 23 — there is no grant, 403. Sc. 22: step 11 — a new row with a mark is visible and gives no reset, step 16 — a row without a mark is not visible, step 20 — the mark of the unit changed, a reset.

Sc. 23 — the versions and the replay memory of the doors of people ([chapter 8.0](../../../spec/08.0-domain.norms.md) Н1.9). The `revision` of the first administrator is 1: the row is written by `first-admin`. Step 11 repeats step 10 with the former `If-Match`: the answer from memory, `revision` 3 in the row did not move (step 13). Step 12 — another password under the same key: the fingerprint sees the password.
Step 14: `<key>` — `sha256("root" ‖ 0x00 ‖ "PUT" ‖ 0x00 ‖ "/domain/users/ann" ‖ 0x00 ‖ "u-r1")`; neither the fingerprint nor the body carries the password. Steps 16, 19 — a repeat of a creation and of a deletion: without the memory these are 409 `exists` and 404. Step 20 goes with a new key: 404. For the grants `$g` is the `revision` of the row `m1` after the preparation `@start domain`.
Step 25: there is no row `c9`, the condition — 412 with `revision: 0`. The break-glass account of `m1` is set here for the first time, therefore `revision` 1.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The log of the acceptance of М11/09 is moved here
as a whole, as it is (the paths of the old rows — `09/…` and the names of the scenarios of М11/09 — are resolved by [id-map](../../../../common/id-map.tsv));
the rows of 2026-10-20 are the move, the removed scenario 07 and the edit of the input `may-24` of the package `common/vectors/may`.

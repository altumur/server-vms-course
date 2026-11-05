# Acceptance P/09.1 — the agent of a member (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand, the dictionary of directives and doors — [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Стенд домена»](../../../common/acceptance/README.md#domain-stand) (the stand of several clusters; formerly — the М11 dictionary of the acceptance README
of М11/01; the plan of the move of lesson 8, В5). The norm of the chapter is [`09.1-agent.norms.md`](../../spec/09.1-agent.norms.md) Н5;
[the contract](../../spec/09-agent.api.openapi.yaml), the lecture (`ru/09-agent.md`, for people, not in the export). The scenarios were moved (stage B, ADR-0083
addendum (1): without a change of behaviour) from the acceptances of М11/05 (04 → 13), М11/06 (04, 07, 08), М11/10 (11), М11/11 (05, 06 → 14) and
М11/12 (01, 03, 06); the numbers, names and steps are the former ones, except `13-slot-liveness` (in М11/05 — `04-slot-liveness`) and
`14-pointer-checksum` (in М11/11 — `06-pointer-checksum`): the number 04 is taken by the scenario of М11/06, the number 06 — by the scenario of М11/12;
the next numbers after the largest number of the sources of the chapter (М11/10 sc. 12) — in the order of the lesson М11, then of the scenario
(the Architect's decision on the move plans 8–10, item 14; a row of `journal/corrections-1.tsv`). In total 22 scenarios / 252 steps: 5 from
М11/05, 26 from М11/06, 20 from М11/10, 11 from М11/11, 40 from М11/12, 2 — sc. 06 steps 9–10 (`as_of` to the medium no more often than once an hour; VMS request № 19); 20 — sc. 15 `one-agent` (DOM-AGENT-TURN-01);
35 — sc. 16–19 of the coverage audit of P/09 (audit-kimi aee4369fb, drafts J01–J04); 72 — sc. 20–25 of its second pass (Gemini,
cc36de538, drafts G03, G04; below); 21 — sc. 27 `roles-copy` (ADR-0098 §4).

The other scenarios of the sources are at the chapters of their outcome (ADR-0083 addendum (13); the appendix of the plan of the move of lesson 8): М11/05
sc. 01, 03, 05 — [chapter 8.5](../../../08-domain/acceptance/5/README.md), 02 — [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) (13); М11/06 sc. 01, 02,
03, 05, 09 — [chapter 8.6](../../../08-domain/acceptance/6/README.md), 06 — [chapter 8.1](../../../08-domain/acceptance/1/README.md)
(sc. 15); М11/10 sc. 01 — the acceptance of chapter 6.7 (15), 02–04, 08–10, 12 — [chapter 8.8](../../../08-domain/acceptance/8/README.md),
06 — the vector package [`follow`](../../vectors/follow/README.md); М11/11 sc. 01 — [chapter 8.9](../../../08-domain/acceptance/9/README.md),
02 — [the acceptance of lesson P/10](../../../10-domain-console/acceptance/README.md), 04 — the vector [`alarms`](../../../10-domain-console/vectors/alarms/README.md), 03 — the vectors [`resolve`](../../../06-console/vectors/resolve/README.md); М11/12 sc. 02 — [chapter 8.3](../../../08-domain/acceptance/3/README.md) (sc. 17), 04,
05 — [chapter 8.10](../../../08-domain/acceptance/10/README.md). The agent side in the scenarios of other chapters — the list
«Соседи на стенде» of the norm of the chapter, Н5.

## Stand

**Preparation of each scenario** — as the acceptance README of [chapter 8.3](../../../08-domain/acceptance/3/README.md)
(«Подготовка каждого сценария»; from the acceptance README of М11/03): the runner brings up on one machine three clusters — `hold`, `m1`, `m2`; each has
its own empty store, its own `{data}`, its own role sockets and ports of the console and the resource, its own ring (P/06.2 Н1.2), the manifest catalogue
— only `testsub`; the console, the controller and the worker `w-1` of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`).
There are no units. There is no domain: it is set up by the directive `@domain` of the first step of each scenario. The domain name is `acme`.

- `store` at `member <кластер>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows at a member:
  `domain/agent`, `domain/member-key`, `domain/member-list/<раздел>`, `domain/keys`, `domain/member-topology`, `domain/grants`,
  `domain/backup-taken`, `domain/shared`, `domain/shared-refused`, `domain/root`, `domain/placed`, `domain/outcomes`,
  `domain/agent-turn`); `store` without `member` is the store of `hold`.
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<член>/…` are read.
- Do not speed up the clocks: `LOST_AFTER` 45 s, `REPORT_EVERY` 5 s, `MARK_REFRESH` 22.5 s, `VIEW_EVERY` 3 s; the `@until` terms are taken with
  a margin.
- The runner goes as the human `root` (the first administrator — chapter 8.4).

The differences by scenario (from the READMEs of the source acceptances):

- **Scenarios 01, 03, 06** (from the acceptance README of М11/12). The doors `holder`, `member`, `resource` and the directives `@domain`,
  `@start`/`@stop agent` — the dictionary of the «Стенда домена».
  - **01.** The member `m1` without changes: after `@domain` and 10 s of silence its generation stands, and the mark freshens within 30 s (more than
    `MARK_REFRESH` and a pass). The indices of the rows `domain/member-list/<раздел>` and `domain/keys` at `m1` do not grow: the agent writes at home only
    on a difference. There is no row `domain/agent`: it is written only on a signature failure or a too large whole. The observation window
    opens only after the backup copy (chapter 8.8): step 2 waits for `BACKUP_EVERY` and a pass after `@domain` — the last
    copy of the holder is made; steps 3–4 — `m1` (a keeper) has written at itself the same copy as the pointer `domain/keepers/m1`
    of the holder; step 5 — its report with `domain/backup-taken` is accepted. Further the content of `m1` does not change, and `reported.rev`
    stands. `@domain` does not wait for the copies at the keepers.
  - **03.** The member key of `m1` is spoiled through `admin.sock` while the agent is stopped: the agent runs but does not sign — the row
    `domain/agent` with a count, the member is `silent` within `LOST_AFTER`. The key is returned — `m1` is `ok` again. Steps 12–14 spoil the key on
    the move, without `@stop agent`: the agent reads the key in every pass (Н1.12 `key_read`) — the same count and `silent`; steps 15–19
    return the key and restart the agent — the member is `ok`, there is no row of the past launch (Н1.12 `at`; the reconciliation of М11, N1, N2).
  - **06.** An edit of the topology and the grants of `m1` by the holder (the doors `holder`: chapter 8.3, chapter 8.4) — then the home rows at `m1`
    are not rewritten for two agent passes, `as_of` of the grants copy is not freshened earlier than `FRESH_EVERY`.
- **Scenarios 04, 07, 08** (from the acceptance README of М11/06). The catalogue `testsub` — `domain.edit: [start, labels]`, `domain.ref:
  name`. The doors `holder`, `member` and the directives `@domain`, `@cut`, `@mend`, `@clock` — the dictionary of the «Стенда домена»; at the door
  `holder` the runner sets `Idempotency-Key` also for `PUT`/`DELETE`. `$id` is the id of the stored edit from the answer 202. The holder stores
  the edit (chapter 8.6), the agent of `m1` applies it (Н1.5) after `@mend`; the condition `If-Match` of the units door — sc. 14 of the acceptance of
  [P/06.1](../../../06-console/acceptance/1/README.md). Sc. 08: `@clock m1 +90` — the agent clock outside the window of the units door
  `UNIT_WINDOW` 60 s ([the agent signature contract](../../../common/contracts/agent-signature.md)); step 10 returns the clock.
- **Scenario 11** (from the acceptance README of М11/10; the Quint model of М11, scenario Q3). The stand with a signer also on `m1`: the doors
  `holder`, `member`, `signer` and the directives `@domain`, `@start domain on`, `@stop domain`, `@move` — the dictionary of the
  «Стенда домена». A revocation after the last backup copy does not revive after a move: the agent of a member merges `domain/revoked` of the answer
  with its own row (RV, Н1.4 `from_carry`), step 20 — 401.
- **Scenarios 05, 14** (from the acceptance README of М11/11). The catalogue `testsub` with a declaration of the shared document:
  - `domain.shared: [step, marks, {rounds}]`;
  - `step` — `int` with `inherit: 1`;
  - `marks` — `list` with `inherit: []`, `merge: union`.

  The doors `holder`, `member` and the directives `@domain`, `@on`, `@put object` — the dictionary of the «Стенда домена». A document of the form of
  [P/08.9 Н1.2](../../../08-domain/spec/08.9-domain.norms.md) `document`, but signed by an unknown issuer
  (`inputs/shared-doc-unknown-issuer.json`: `kid` `0000000000000000` is not in `issuing` of the set, `sig` — 64 bytes), the runner
  puts as an object and a pointer bypassing the edit (C09-SHARED-ACCEPT-01; the Architect's decision 2026-10-29: the outcomes of the family `shared-docs` —
  the holder does not send out what is unreadable): sc. 05 — with its sum: the holder sends the document, the member does not take it — `record`
  refuses `unknown_issuer` (Н3 «take the document» step 4), there is no row `domain/shared` at the member; the holder console — `record`
  did not pass, the values without the domain (`from: manifest`, [P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.14; a neighbour
  on the stand). Sc. 14 — with a foreign sum: an object not with the `sha256` of the pointer — unreadable for the holder (the outcomes of `shared-docs`):
  the holder console — 503 `unavailable`, the document is not sent to the member, there is no row `domain/shared` at the member. The refusal of the agent
  «does not match the pointer» (Н3 «take the document» step 3) the stand does not reach — the holder does not send such a document, and
  the step has no separate function (a vector would require a new agent command): the sum check by the agent — by reading.
- **Scenario 13** (from the acceptance README of М11/05). The catalogue of each cluster is `testsub` and `testsub2` (the order — the «Стенд» of the common
  acceptance README); on each cluster run the controllers of both, the worker `w-1` of the manifest `testsub`, the worker `t-1` of the manifest
  `testsub2` (with the training writer of contributions — [P/08.5](../../../08-domain/spec/08.5-domain.norms.md) Н5) and the resource of its own
  server `srv-<кластер>`; before the steps the store of each cluster has the counter `testsub` `c1-<кластер>` (its own ref at
  each: a common `c1` would be disputed, and `@domain` would not wait for `complete: true`) and the shelf `testsub2` `sh1` `{zone: z1,
  server: srv-<кластер>}`. `console2` at `member` — the prefix `/testsub2`. The directive `@on m1 @sigkill t-1` kills
  the contributing worker: its row does not go into the report by the slot term (Н1.2 `liveness`), the book `rolls` at `m2` — without the record `t4`.
  The book door (`GET /domain/testsub2/books/rolls`) — the cluster console (chapter P/06.7), the assembly — chapter 8.5: neighbours
  on the stand.
- **Scenarios 16–19** (the coverage audit of P/09, audit-kimi aee4369fb). The doors `holder`, `member`, `store`, `token` and the directives
  `@domain`, `@stop`/`@start agent`, `@on` (`@freeze`, `@thaw`, `@put object`) — the dictionary of the «Стенда домена» and the common dictionary
  of directives; the freeze limit is 120 s.
  - **16** (J01). The holder is a member (Н1.5 `holder_self`): the unit `h1` is created by the console of `hold`, the edit with `?cluster=hold`
    is stored in `domain/pending/hold` (202, `cluster: hold`), the agent of the holder applies it itself — the value at the unit of `hold`,
    in the holder view the pending 0 and the outcome `performed` 200. `base` is the revision of the unit in the copy of `hold` at the holder (P/08.6 Н1.4),
    `If-Match` matches.
  - **17** (J02). The local token door with a silent holder ([the local token
    door contract](../../../common/contracts/local-token-door.md) `no_queue`, `TOKEN_WAIT` 10 s): the process `domain` on `hold`
    is frozen (`@on hold @freeze domain`; there is one copy, the signer queue has nobody to pass to) — the connection is accepted, there is no
    answer; the request of `m2` — 503 `unavailable` in one request (the door answers no later than `TOKEN_WAIT`, the runner waits for the answer longer).
    After `@thaw` — again 200. The freeze is about `TOKEN_WAIT`, less than `LOST_AFTER` and `TURN_TERM` (45 s).
  - **18** (J03). The copy of the emergency row (Н1.4 `break_glass`): the password of `m1` is set by the holder — a copy at `m1`; the password of
    `hold` is its own row, the agent of the holder does not write and does not delete it (`set_at` and the index are the former ones after two
    passes and at the end). The holder row `domain/break-glass/m1` is spoiled through `admin.sock` (`set_at` not of the time form, `pwhash_secret` — `enc:v2` not by
    the grammar: the row is unreadable by form, without relying on the parsing of the open secret): the holder sends `held` with the name `break_glass` (the outcomes of the family `domain/break-glass/<кластер>`, the reader `domain`), the copy of `m1` is the former one.
    There is no removal door (the path has only GET and PUT), so the row is removed by `admin.sock`: there is no row — there is no field, the agent deletes the copy.
  - **19** (J04). The keeper's agent (Н1.9, Н3 «check the backup copy» step 3): `m1` is the only keeper
    (`BACKUP_HOLDERS`); while the agent is stopped the runner puts at it its own copy of term 99 — the object `domain/backup`
    (`inputs/backup-foreign-term.json`, the form `backup.schema.json`; the signature of the form, which does not verify, is the business of `record` over
    what is sent, its own copy the agent reads by form) and the row `domain/backup-taken` with its sum. The report carries the pair 99 —
    the holder sends the document (the pointer ≠ the copy of the member, P/08.8 Н1.5 `carry`), the agent refuses «older than the copy kept
    here» with the pair of the pointer (`term` 1); the object and the row of the keeper are the former ones. Steps 1, 2 of Н3 (a foreign sum, `record`) — by reading:
    the holder signs and sums itself.

### Coverage audit of P/09, the second pass (Gemini)

Sc. 20–25 (`audit-coverage-gemini` cc36de538, drafts G03, G04) — the same stand; the doors `holder`, `member`, `store`,
`token` and the directives `@domain`, `@join`, `@stop`/`@start agent`, `@on` (`@put object`) — the dictionary of the «Стенда домена». The rows
bypassing the writer are put by the store door of the member through `admin.sock`, as in sc. 03 and 18.

- **20** (G03). `join` at a member (Н1.1 `same`, `another`): a repeated `@join m1` with the same `{pub, domain}` — `ok`, the row
  `domain/root` and its index are the former ones. At `m2` (`@domain m1` does not accept and does not pin it) the runner puts `domain/root`
  of the same root with the domain `other` — `@join m2` `refused`, the row and the index are the former ones. The refusal after a foreign root — sc. 02 step 10
  of [the acceptance of chapter 8.3](../../../08-domain/acceptance/3/README.md); here it is checked that the row does not change in either case.
- **21** (G03). The pair of the member key (Н1.1 `pub`, C09-MEMBER-KEY-PAIR-01): while the agent is stopped `pub` of the row
  `domain/member-key` at `m1` is replaced by the public key of the member `hold`. It is a point of the curve, the form of the row is right, `seed_secret`
  is the former one and opens, but `pub` is not from the seed: the row is unreadable by the outcome of the family. The agent runs and does not sign: the row
  `domain/agent` with the count `sign_failures_domain` (Н1.12 `count`), the local token door answers 503
  `unavailable` at once (Н1.12 `key_unreadable`; the request is not carried to the holder, a placement is not needed), the member becomes `silent` within
  `LOST_AFTER`. The key row is not born anew: the index is the former one (the outcome of the family at `domainagent`, Н1.1 `born`). An agent
  that would sign with the seed the holder would hear, and the member would stay `ok`. The count `sign_failures_console` is checked
  by reading («Evidence outside the TSV»).
- **22** (G04). The removal of the refusal of the shared document (Н1.10 `member`, C09-SHARED-REFUSED-CLEANUP-01, -02). The document
  of an unknown issuer, as in sc. 05, gets the refusal `unknown_issuer`. An edit of the holder with `base_rev` 1 passes:
  the former document is readable for the holder, the form and the sum are right ([P/08.9](../../../08-domain/spec/08.9-domain.norms.md)
  Н1.3 step 5). The holder signs the document rev 2, the member takes it, and the taken document removes the refusal with the pair (1, 1),
  which is not newer than its own. Then the runner puts a refusal with the pair (1, 2), not newer than its own `domain/shared`: it is removed by the next
  pass without a new document (the follow-through; step 1 of «take the document» — «nothing»). An unreadable refusal (`doc` not JSON) is removed
  by the same follow-through: a comparison with the unreadable gives «differs» (П2). Its own `domain/shared` does not roll back.
- **23** (G04). Unreadable home copies (Н1.4 `home_write`, `member_copy`; Н1.5 `member`; the outcomes of the families
  `domain/member-list/<раздел>` — `Г-53`, `domain/member-topology` — `Г-54`, `domain/grants` — `Г-51`, `domain/placed` — `Г-58`). The agent is
  the only writer: an answer against an unreadable row is «differs» for it, and it rewrites the row by CAS with the value of the
  answer. The runner spoils four rows of `m1` (`doc` not JSON, `as_of` not a time, `rev` not an integer), and each returns to the
  value bound before the spoiling (`$ml`, `$mt`, `$gd`). At `domain/placed` it is `rev` 2: 1 after `@domain`, 2 after the write of
  the placement, as in sc. 01 of [the acceptance of chapter 8.6](../../../08-domain/acceptance/6/README.md). The holder sends `members`
  because the agent without a readable copy does not send `members_rev` ([the report acceptance
  contract](../../../common/contracts/accept.md) «The list of members to the one lagging behind»).
- **24** (G04). An unreadable outcomes row `domain/outcomes` (Н1.5 `apply`; the outcome of the family, `Г-56` — an exception to the rule
  of the only writer): the element `e-000000000001` is not an outcome object. The edit of the holder is stored (202), but the agent does not
  perform it: it has nothing to check «an outcome with `kept_at = at` is already written» by. For three passes the unit is the former one, the holder has one
  pending edit, the outcomes row is the former one — the agent does not rewrite it. The runner (the operator) fixes the row: `items: {}`, it cannot be deleted (`never` P/01.2 Н1.3, `delete` under `domain/` is forbidden to `admin` too) — the edit is performed,
  the outcome `performed` 200, the pending 0.
- **25** (G04). An unreadable row of the agent queue `domain/agent-turn` (Н1.13 `standby`, Н3 «the agent turn» step 1; the outcome
  of the family, `Г-44`): while the agent of `m2` is stopped the row is `{bad: "1"}` (no `holder`, an extra field). The started agent
  stays waiting. It sends no reports: the member is `silent` within `LOST_AFTER`, while an agent that took the queue would report in 5 s.
  There is no CAS over an unreadable row: the row and the index are the former ones. The local token door works — the request of `m2` goes to
  the holder and gets 200 (DOM-AGENT-TURN-02; the placement `c1` — as in sc. 17). After the row is fixed (`holder: ""` — the queue is given up; `delete` is forbidden, as in sc. 24) the agent takes the queue
  (`holder` with `:`), and the member is `ok` again.

## Inputs `inputs/`

| File | Scenario | What is in it |
|---|---|---|
| `shared-doc-unknown-issuer.json` | 05, 14, 22 | a shared document of the form ([P/08.9 Н1.2](../../../08-domain/spec/08.9-domain.norms.md) `document`) with an unknown issuer: `kid` `0000000000000000`, `issuer` — 32 bytes `0x11`, `sig` — 64 zero bytes base64url |
| `backup-foreign-term.json` | 19 | a backup copy document of the form `backup.schema.json` (`common.domain_backup_doc`) of term and revision 99, `holder` `hold`, `members` `[hold, m1]`, empty `state` and `objects`, `issuer` — 32 bytes `0x33`, `kid` — the first 16 characters, `sig` — the bytes 0…63 base64url (does not verify: the agent reads its own copy by form); JCS without a line break, sha256 `eec6d36c2e9636846f2d335daf072c791c8022e1e714091f05fe56e4b2380434` — in the row `domain/backup-taken` of step 5 |

`shared-doc-unknown-issuer.json` is copied byte for byte from `inputs/` of the acceptance of М11/11 (the plan of the move of lesson 9, § 3
«Входы и форма»); `backup-foreign-term.json` — the coverage audit of P/09 (draft J04), the bytes of the draft.

## scenarios.tsv

The format is the dictionary of the «Стенда» of the common acceptance README and the section «Domain stand»; the expectation is a subset of the fields, `~` — a substring,
`@time` — a time in a string (P/01.1 Н0), `@not(…)` — not equal. In total 22 scenarios / 252 steps. Sc. 27 — ADR-0098 §4, there is no dry run by an implementation; steps 14–15 give the emergency row so that `sealed` opens without the grant fields too; step 19 `@sleep 7` is a check of absence: the agent pass 5 s and a margin, the copies are not erased, the indices are the same; a break between two writes of the agent, an old agent and a rollback — by reading: the stand does not interrupt a write and does not substitute the agent version.

Sc. 15 `one-agent` (DOM-AGENT-TURN-01, -02, the owner's consent 2026-10-26; P/09.1 Н1.13, Н3 «the agent turn»): two agents of the cluster `m1` (`@start agent m1 second` —
a copy of «another server» with its own `AGENT_TOKEN_DIR`). Steps 3–6: one holds the queue (`$a1`), for two `TURN_RENEW` the holder is the
same, the reports go. Steps 7–8: the local token door of the waiting one (`token m1#2`) carries the request to the holder — the answer is the same as at
the active one (`$e`, `$r` — the refusal words of the holder, the request is not by placement; DOM-AGENT-TURN-02). Steps 9–12: SIGTERM of the active one —
holder `""`, then the waiting one takes the queue (holder with `:` — an instance, `$a1` has already exited), the reports continue. Steps 13–19:
SIGKILL of the active one — the queue is not given up: after 30 s the holder is the former one, after `TURN_TERM` 45 s — taken by the third copy. Step 20 —
the member is `ok`.

| № | Scenario | Steps | What |
|---|---|---|---|
| 01 | `quiet-member` | 13 | a quiet member: `reported.rev` stands, `received_at` freshens, the indices of `domain/member-list/<раздел>` and `domain/keys` at the member do not grow, there is no `domain/agent` |
| 03 | `unreadable-member-key` | 19 | the member key is spoiled — `domain/agent` with a count, the member is `silent`; repaired — `ok`; spoiled on the move — the same count; a restart — there is no row of the past launch |
| 04 | `conflict` | 9 | the edit is stored, the member changes the unit itself — the outcome 412 `conflict`, the value of the member is kept |
| 05 | `unsigned-document` | 6 | a document of an unknown issuer bypassing the edit — `domain/shared-refused` `unknown_issuer`, there is no row `domain/shared`; the holder console — `from: manifest` (C09-SHARED-ACCEPT-01) |
| 06 | `fresh-and-unchanged` | 10 | the home row without changes is not rewritten, `as_of` of the grants copy no more often than `FRESH_EVERY`; steps 9–10 — after 65 s `as_of` and the index of the row are the former ones: freshening to the medium no more often than `AS_OF_STORE_EVERY` 3600 s (VMS request № 19) |
| 07 | `outcome-refused` | 7 | an edit that the member refused with 409 (`exists`) — the outcome `refused`, the pending 0 |
| 08 | `unit-door-window` | 10 | the agent clock +90 — the member console 401, the outcome `refused` 401, the unit is not touched |
| 11 | `revoked-not-revived` | 20 | a revocation after the last backup copy does not revive after a move — 401 |
| 13 | `slot-liveness` | 5 | the contributing worker is killed — its row does not go into the report by the slot term, there is no record in the book |
| 14 | `pointer-checksum` | 5 | a pointer with a foreign sum — the holder console 503 `unavailable`, the document is not sent to the member, there is no row `domain/shared` at the member; the refusal of the agent by the sum — by reading (C09-SHARED-ACCEPT-01) |
| 15 | `one-agent` | 20 | two agents of `m1` — one holds the queue, for two `TURN_RENEW` the waiting one does not take it; the local token door of the waiting one answers as at the active one; SIGTERM of the active one — the waiting one takes the queue; SIGKILL — the queue is not given up before `TURN_TERM`, then taken by the third copy; the member is `ok` (DOM-AGENT-TURN-01, -02) |
| 16 | `holder-self-edit` | 6 | an edit of a unit of the holder cluster (`?cluster=hold`) — the agent of the holder applies it itself: the value at `hold`, the pending 0, the outcome `performed` 200 (audit of P/09, J01) |
| 17 | `token-wait` | 7 | the process `domain` is frozen — the local token door of `m2` 503 `unavailable` within `TOKEN_WAIT`; after the thaw — 200 (audit of P/09, J02) |
| 18 | `break-glass-copy` | 13 | the copy of the emergency row at `m1` from the field `break_glass`; the holder row is unreadable — `held`, the copy is the former one; there is no row — the copy is deleted; its own row of `hold` is not touched by the agent (audit of P/09, J03) |
| 19 | `backup-refused` | 9 | the keeper's own copy of term 99 — the sent document of term 1 is refused «older than the copy kept here», the object and `domain/backup-taken` are the former ones (audit of P/09, J04) |
| 20 | `join-same-and-another` | 9 | a repeated `join` of the same root — `ok`, `domain/root` and the index are the former ones; another one is pinned — `refused`, the row is the former one (audit of P/09, the second pass, G03) |
| 21 | `member-key-pair` | 11 | `pub` of the member key is not from `seed_secret` — the row is unreadable: `sign_failures_domain`, the local token door 503 `unavailable`, the member is `silent`, the row is not born anew (C09-MEMBER-KEY-PAIR-01; G03) |
| 22 | `shared-refused-cleanup` | 12 | the taken document removes the refusal with a pair not newer than its own; a refusal not newer than its own `domain/shared` and an unreadable refusal are removed by the follow-through (C09-SHARED-REFUSED-CLEANUP-01, -02; G04) |
| 23 | `unreadable-copies-heal` | 16 | the unreadable `domain/member-list/<раздел>`, `domain/member-topology`, `domain/grants`, `domain/placed` are rewritten by the holder's answer (Г-51, Г-53, Г-54, Г-58; G04) |
| 24 | `unreadable-outcomes` | 12 | an unreadable `domain/outcomes` — the edit is not performed, the row is not rewritten; fixed — the outcome `performed` (Г-56; G04) |
| 25 | `unreadable-agent-turn` | 12 | an unreadable `domain/agent-turn` — the agent is waiting, the member is `silent`, the row is not rewritten, the local token door 200; fixed — the queue is taken, the member is `ok` (Г-44; G04) |
| 27 | `roles-copy` | 21 | the copy of `domain/roles` at `m1` by the holder grants: the disabled `bob` drops out of `assigned`, the session of `ann` — `view` through the role `ops`; the holder grants row is unreadable — the copies `domain/grants` and `domain/roles` are not erased, the indices are the former ones (ADR-0098 §4) |

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event — `@until`: sc. 01 step 9 waits for the next report of the same generation (`received_at` changed, `rev` the
same). The remaining sleeps (from the READMEs of the acceptances of М11/12 and М11/10):

| Sc./step | Sleep | Reason |
|---|---|---|
| 01/2 | 35 s | time before an action: the first backup copy and its keepers after `@domain` — `BACKUP_EVERY` 30 s and the agent pass 5 s |
| 01/5 | 10 s | time before an action: the member went quiet after the write of `domain/backup-taken` — two agent passes |
| 06/6 | 10 s | absence: fresh copies with the same content are not rewritten — a rewrite would be in the nearest agent pass (5 s), two passes; `as_of` is freshened no more often than `FRESH_EVERY` 60 s |
| 06/9 | 65 s | absence: longer than `FRESH_EVERY` 60 s — the freshening of `as_of` in memory has already happened, but it is not in the row: to the medium no more often than `AS_OF_STORE_EVERY` 3600 s (VMS request № 19; the whole hour — by reading) |
| 11/6 | 65 s | time before an action: two windows of `BACKUP_EVERY` after the revocation — the copy with `bob` (step 9) is made at once, not after a window |
| 11/10 | 6 s | time before an action: the copy with `bob` — in the nearest pass of the holder (3 s) with a margin |
| 15/4 | 25 s | absence: for two `TURN_RENEW` (10 s) the waiting one does not take a fresh queue — the holder is the former one (step 5) |
| 15/16 | 30 s | absence: the killed active one has not given up the queue, and it is not taken earlier than `TURN_TERM` 45 s from the last renewal (the renewal — no later than 10 s before SIGKILL: 30 < 35) |
| 18/6 | 10 s | absence: the agent of the holder does not write and does not delete its own row `domain/break-glass/hold` — a write or a deletion would be in the nearest agent pass (5 s) after the holder's answer; two passes |
| 18/9 | 10 s | absence: the copy of `m1` is not touched with an unreadable holder row (`held`) — a deletion would be in the nearest agent pass (5 s); two passes |
| 24/6 | 15 s | absence: with an unreadable `domain/outcomes` the agent does not perform the edit — the performance would be in the nearest agent pass (5 s) after the issue by the holder; three passes, and the holder view (`VIEW_EVERY` 3 s) manages to show the pending edit |
| 27/19 | 7 s | absence: the copies `domain/grants` and `domain/roles` are not touched with an unreadable holder row — an erasure would be in the nearest agent pass (5 s) with a margin |

## Evidence outside the TSV

Checked by reading (the norm of the chapter, Н5 «Чтением»): the agent does not send a new generation by time, an unreadable edits row
of the holder at itself, the alarm page and the urgent report (the stand does not raise alarms), the agent in the process (the stand has no process without
a kit), the field `sign_failures` of the publication and the count `sign_failures_console` (an edit has no way to be delivered to an agent without a key: it does not ask
for the holder's answer, and an edit received before the key was spoiled is a race of one pass), `no_seal` and `domain.reports`, key changes at a member without a connection, the book secrets at
a member, the refusals of the keeper's agent by the sum and by `record` (the holder does not send such a document), a break of the road of the local token door,
an answer from the relay memory and `as_of` of the grants copy (on the stand `as_of` is visible only as a store row, and its freshening is
no more often than `AS_OF_STORE_EVERY`), the agent body limit; the HTTPS client and the first contact (the stand without TLS). The bytes of the agent signature
— the package [`agent-sig`](../../../common/vectors/agent-sig/README.md), the function `peer` — the package
[`peer`](../../../common/vectors/peer/README.md), the function `follow` — the package [`follow`](../../vectors/follow/README.md).

## `journal/corrections-1.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows of the logs of the acceptances of М11/05, М11/06,
М11/10, М11/11 and М11/12 from before the move — at the beginning of the log, with the former paths and numbers (they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)): by `sample` — the rows about the scenarios of this chapter; the rows without a scenario (the whole
`scenarios.tsv`, `inputs`, `@sleep`, the preparation, the move) — into all the successor chapters (review analysis of stage B 6–7, № 18).
Then — the rows of the move of this chapter and of the history of the sources.

## Anywhere copy hash (G09-ANYWHERE-HASH-01)

The four fixture vectors in [`inputs/anywhere-hash/cases.tsv`](inputs/anywhere-hash/cases.tsv) specify the complete-body
digest of P/08.4 Н1.3 carry and the check before the copy of Н1.4 member_anywhere. The input column names a JSON file
next to the table; expect is a JSON subset of the observations, not an input to the implementation.

Each input has an initial stored copy with its exact index and last confirmed taken_sha256 marker, and a list of attempts.
Every attempt starts independently from that initial state: its trusted carry advertisement is advertised, its real
200 body from `GET /api/anywhere/{member}` is the UTF-8 text body. The fixture calls the ordinary agent copy code with
the body and mark, and records the store operations and marker changes. received_at is the receipt time and domain_age is the answer age; each case prepares a valid trusted carry for server m1 and its active agent guard. It reports arrays in attempt order:
computed_sha256, copy_writes, marker_confirmed; for a refusal also related_edits (the writes belonging to this copy),
copy_items, copy_index and taken_sha256. The digest observation comes from the normal code path that judges the body;
it is not computed by the fixture instead of that path. The two positive vectors must reach the actual copy write.

The existing agent-carry IO seam can carry these inputs: these files do not declare a new native command. A fixture
that only calculates the expected digest does not check the negative cases: they require the former copy, exact index
and marker to stay unchanged and zero copy writes and related edits. The four cases cover as_of in the digest, JCS
instead of wire formatting, a refused digest of doc alone and a refused mismatching whole-body digest.

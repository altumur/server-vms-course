# Acceptance P/08.6 — placement and kept edits (stand)

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Стенд домена»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters; formerly the dictionary of the М11 README of the acceptance
М11/01; the plan of the move of lesson 8, V5). The norm of the chapter is
[`08.6-domain.norms.md`](../../spec/08.6-domain.norms.md) Н5; [the contract](../../spec/08-domain.api.openapi.yaml),
the lecture (`ru/08-domain.md`, for people, not in the export). Scenarios 01, 02, 03, 05, 09 were moved from the acceptance of М11/06 (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers and the steps are the former ones, except sc. 03: step 14 (the holder's copy with `start` 7 before `DELETE`) is inserted, the former 14–16 are now 15–17 (the decision of «Архитектор» 2026-10-21 on a data finding of cammeta-python ac3509b). The other scenarios of М11/06: 04, 07, 08 — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md), 06 — [the acceptance of chapter 8.1](../1/README.md) (sc. 15). Sc. 10 is added by ADR-0091 addenda (12)–(19) (the executors of placement). Sc. 11 — the coverage audit of P/08 (audit-kimi 1e9929d51), sc. 12–15 — its second pass (Gemini). In total 12 scenarios / 261 steps.

The `If-Match` condition of the units door, by which the agent applies an edit, is sc. 14 of the acceptance of
[P/06.1](../../../06-console/acceptance/1/README.md). The doors `GET /domain/placement`, `/domain`, `/domain/<sub>/<rows>`,
through which the stand reads placements, the view and the units, are doors of the domain console (lesson P/10, [the forwarding contract](../../../common/contracts/forwarding.md) «Domain doors»; [Н1.2а, Н1.2г](../../../10-domain-console/spec/10-domain-console.norms.md)); the chapter normates their content.

## Preparation

As the acceptance README of [chapter 8.3](../3/README.md) («Stand», «Подготовка каждого сценария»;
formerly the acceptance README of М11/03): the runner brings up three clusters on one machine — `hold`, `m1`, `m2`; each has its own
empty store, its own `{data}`, its own role sockets and console and resource ports, its own ring (P/06.2 Н1.2), a manifest catalog of
only `testsub` (`domain.edit: [start, labels]`, `domain.ref: name`); the console, the controller and the worker `w-1` of `testsub`, the resource
of its own server (`srv-hold`, `srv-m1`, `srv-m2`). There are no units. There is no domain: it is set by the directive `@domain` of the first step of each
scenario. The domain name is `acme`; the recovery file is `{recovery}` in the instance directory.

- `store` of `member <кластер>` is the store door of the cluster through `admin.sock` (observation of the domain rows:
  `domain/placed*` of the members, `domain/pending/m1` of the holder).
- The clock is not accelerated: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s, VIEW_EVERY 3 s; the deadlines of `@until` are taken with a margin.
- At the door `holder` the runner sets `Idempotency-Key` for `PUT`/`DELETE` too; `@key(N)` repeats the key of step `N`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the dictionary of the domain; an expectation is a subset of fields. `$id` is the id of the kept edit from the 202 answer.

| № | Scenario | Steps | What |
|---|---|---|---|
| 01 | `placement` | 19 | placement: empty; refusals 404/409/400; a write; the same — without a new `rev`; copies at `cluster` and at a member from `copies`, at an uninvolved one — none (the filter `records`); deletion — the copies are removed; a repeated deletion — 404; a copy at a member from `origin` |
| 02 | `edit-refusals` | 15 | edit: no unit with a full answer — 404; a field outside `domain.edit`, an empty body, a platform field — 400; a secret — 400; `?cluster=` not a member — 404; `contested` — 503; not found with a silent one — 503 |
| 03 | `kept-and-applied` | 17 | an edit to a switched-off member: 202 `kept`, a replay — the same id, another body — 422, `view.pending`; after the return — applied, outcomes `performed`, 0 waiting; the holder's copy with a new `start` — then `DELETE` of the edit door — outcome `performed`, the unit is gone |
| 05 | `kept-full` | 56 | 50 edits of one unit wait for a switched-off member, edit 51 — 409 `kept_full`; `view.pending` — 50 |
| 09 | `forms-of-edits` | 16 | forms (the М11 check 05–08): `POST` without `cluster` or with a number — 400; `<sub>` not from the catalog — 404; `DELETE` with a body — 400; placement `cluster: ""` — 400, `ref` with `/` — 400, `a%20b` — ref literally; `asked.path` of the kept edit — with `?cluster=<член>` |
| 10 | `executors` | 14 | the executors of placement (ADR-0091 addenda (12)–(19)): one ref at `m1` and `m2` without placement — `contested`; placement `{cluster: m1, copies: [m2]}` — the view is full, both units in `units`; `m1` switched off — an edit without `?cluster=` — 409 `executors` with `clusters`; with `?cluster=m1` — 202; the same key without `?cluster=` — an early replay at `m1`, 202 with the same id; placement `{cluster: m1, origin: m2}` — `m2` outside the executors, `contested` |
| 11 | `outcomes-limit` | 60 | the outcomes limit 50: the outcome of the first edit (`Idempotency-Key: h05-oldest`) is written; 50 edits to the switched-off `m1`, the return — 0 waiting, exactly 50 outcomes in the view, the first is displaced from the row `domain/outcomes/m1` |
| 12 | `post-kept` | 8 | a kept `POST`: 202 `kept`, `what` — `name,start` (the field `domain.ref`, without `cluster`), `asked.path` without a query; after the return of `m1` — the unit is created, outcome `performed` 201 |
| 13 | `waiting-delete` | 11 | a `DELETE` of a unit waits — a new edit of the same path (`PUT`, a second `DELETE`) — 409 `unit is being deleted`; after the return — the unit is gone |
| 14 | `garbled-placement` | 14 | an unreadable placement record: `PUT` writes over it with a new `rev`, `DELETE` deletes it; `DELETE` without a manifest — 404; an unreadable counter `domain/placement` — `PUT` and `DELETE` 503, nothing is written |
| 16 | `placement-versions` | 20 | the `index` of a record, `ETag`, `If-Match` by a number and by an index, 412 with `row`, no record — 412 for `PUT` and 404 for `DELETE`; a key replay, another body 422; the same content under a key and a replay — `ETag`; a replay of `DELETE` — the earlier answer |
| 15 | `garbled-pending` | 11 | an unreadable element of `domain/pending/m1`: the same key — 422, a fresh one — 202, the element is not touched, `seq` 2; an unreadable `seq` — 503, the row is as before |

Sc. 09: step 14 sets `Idempotency-Key: a3-asked`, so the id of the edit is known in advance — `e-a5231d61506d`
(`sha256("m1" ‖ 0x00 ‖ "a3-asked")`, Н1.4 id), and step 15 reads its `asked.path` in the row `domain/pending/m1`.

Sc. 11: step 4 sets `Idempotency-Key: h05-oldest` — the id of the edit is `e-d43101de75c2` (`sha256("m1" ‖ 0x00 ‖ "h05-oldest")`,
Н1.4 id); step 5 waits for its outcome in the view (0 waiting — the 50 next edits fit into `KEPT_LIMIT`). There are 51 outcomes in all: the first
is applied earlier than the others, its `at` (the agent's wall seconds) is the smallest, and the trimming «последние 50 по (at, id) убывая»
(Н1.6) displaces exactly it. The outcome of an edit is both `performed` and `conflict` (412, if the `base` from the holder's copy lags behind the
applied value, Н1.4 base): the steps judge the number of outcomes and the field `what`, not `result`.

Sc. 12–15 (the coverage audit of P/08, the second pass of Gemini, the draft G06 `e32df6f8b`, rewritten): the keys `Idempotency-Key` are set by `@header`, the ids are known
in advance (Н1.4 id): `g08-post` — `e-a56508c8a4e8`, `g08-garbled` — `e-2a8bdc8848eb`, `g08-fresh` — `e-747d2dcc4cc4`
(`sha256("m1" ‖ 0x00 ‖ <ключ>)`, the first 12 hex). Sc. 12 — a kept creation `POST` (Н1.3 `kept`, Н1.4 `what`, `asked`):
`asked.path` is `/domain/testsub/counters` without a query (step 4), the outcome is the status of the units door (201). Sc. 13 — a waiting `DELETE`
(Н3 «принять правку» step 4). Sc. 14 — the outcomes of `domain/placement/<sub>/<ref>` and `domain/placement` (G-35, G-36): a record
without the fields `origin`, `copies`, `reason`, `at`, `rev` is not of the form (without `copies` — unreadable, the М11 check, T2),
«то же содержимое» with it is false — `rev` 3; the counter `{rev: "x"}` is unreadable — 503, `c3` is not written. `rev` after the start is 1 (the section
«Placement counter after the start»): the write 2, the overwrite 3, the deletion 4, `c2` — 5. Sc. 15 — the outcomes of `domain/pending/<член>`
(G-32, G-34): the element `e-2a8bdc8848eb` is not JSON — a replay of its key 422 (the key is not reused), an edit with a fresh key
— 202, the element is not touched; `seq` `"x"` — 503, nothing is written. `m1` is cut (`@cut`) — the edits wait.

Not taken from the draft G06: an unreadable row `domain/outcomes/m1` at the acceptance of an edit (expectation 503) — the norm (G-31) does not
stop the acceptance: settle is not performed in this pass, the view `outcomes` is without the field; `view.pending.<член>: null` with
an unreadable `seq` — the norm gives `null` to a row unreadable as a whole, and the outcomes table does not distinguish the refusal path of a row without `seq` (`""` or `/seq`)
(by reading).

Sc. 01 steps 10–16, 19 and sc. 03 steps 11–17 also observe the side of the member's agent (the copies `domain/placed*`, the application of an edit
through the units door) — items of [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) (P/09.1-07, -08) refer to them; the outcome of the scenario is the placement and the holder's edit
(ADR-0083 addendum (13)).

## `journal/corrections-6.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are `corrections.tsv`
of the acceptance of М11/06 as a whole, at the beginning of the log, with the former paths and numbers (they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)); the rows about scenarios of other chapters are the history of the source (the plan of the move of lesson 8,
§ 3 «Журналы»).

## Placement counter after the start (sc. 01, 10)

The process `domain`, at its start and at each new taking of the queue `domain/signer-turn` — before the first answer to an agent — raises
the counter `domain/placement` by 1 (P/08.6 Н3, C08-PLACEMENT-BUMP-TURN-01). After `@domain` the counter is 1, not 0: sc. 01 step 2
waits for `{"rev": 1, "records": {}}` (`@until`: the raise could come at the first answer to an agent), the first placement write is `rev` 2,
then one by one. The former expectations `rev 0` / the first write `rev 1` (the move of М11/06) are from before this decision
(C08-PLACEMENT-BUMP-ACCEPT-01, a question of c-go 2026-10-30).

## Kit seams

[3 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.

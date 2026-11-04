# Acceptance P/06.1 — the units door, bodies, tables (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.1-console.norms.md`](../../spec/06.1-console.norms.md) Н5. The scenarios were moved from the acceptance of
М10/03 (01–14, all) and
М10/10 (04, 05, 06, 07, 11 → 15–19) (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenarios of М10/10: their numbers 04–07 and 11 are taken
by scenarios of М10/03, they got the next free ones (`15-blob`, `16-ceilings`, `17-tables`, `18-table-ref`,
`19-table-feed`; the rows of `corrections.tsv`). In all 46 scenarios / 514 steps: 11 — the service table (46, ADR-0094 B1, below), 79 — the feed (41–45, ADR-0094 B2, below), 65 — versions (38–40, ADR-0094 B4, below), 95 — the batch door (33–37, ADR-0094 B9, below), 100 — the units door (01–14), 56 — bodies and
tables (15–19), 16 — the order row and the unit state (20, ADR-0091), 6 — the deletion of a row of a worker table (21, the VMS request «команды и строка устройства»),
48 — the coverage audit of P/06 (22–27, below), 38 — its second pass (Gemini; 28–32, below).

The full forms of the answers are [the OpenAPI of the lesson](../../spec/06-console.api.openapi.yaml) (the paths `/{rows}`, `/{rows}/{id}`,
`/{rows}/{id}/{blob_field}`, `/{table}`, `/{table}/{name}`). The state of the slot, the epoch and the lease is not checked here — that is
the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md).

## Preparation and order: scenarios 01–14 (the units door)

The scenarios go through the units door of the console of the subsystem `testsub` (`Source/tests/testdata/testsub.subsystem.yaml`, the same one as
the product's): the rows `counters`, `id: name`.

For each full run the runner creates a separate instance of the store and of the console, loads `testsub`
by P/02.1. After the installation of the manifest the application and service data of `testsub/` are empty: in particular, there are no rows
of units, tombstones, the counter and the claims `testsub/idem/`; the replay memory in the console process is empty too.
The installation rows `platform/manifest/testsub` and the marks are admitted. The controller and the workers are not started:
they are not to change or delete rows during these scenarios.

The instance is started by the section «Stand» of the common acceptance README (the substitutions `{data}`, `{port}`, `{manifest}`).
The preparation, the rights and the path to the door are provided by the runner before the requests. All the steps are called by one and the same
identity with the right to create, read, edit and delete units; in the variant without a domain the requests come from the loopback
by [chapter 6.3](../../spec/06.3-console.norms.md) Н1.3 `open` (only from the loopback, otherwise 403). The runner records the address of the door, the way of preparation and the declared body limit;
the table requests are to fit in it. The limit itself stays a choice of the implementation by the norms of the chapter Н4 and of chapter 6.3 Н1.3 `body` (≥ 1 MiB).

Scenarios 01–14 are 100 steps. Scenarios 03 and 14 run **each on its own clean instance** (the preparation above): their steps 03/8 and
14/8 read the whole list `GET /counters`, and the door does not narrow the read to one unit (Н2), so the expectation does not depend on the order of
the scenarios. The other 12 run sequentially **on one instance**, without cleanup between them. Scenario 14 is
the condition `If-Match` of PUT and DELETE (P/08.6: the domain agent applies an edit from the revision that the domain saw), steps 11–23 — the replay memory of these doors before the condition (Н3 «память повторов»). Scenario 13 is
the limits of the component `Idempotency-Key` (200 bytes of UTF-8, not `..`, without `/`) of the first row of the table «Additional checks»,
moved into the TSV by the mutation check 7cecaf2 (№ 16, 17); `@header Idempotency-Key:` replaces the runner's key.
Scenario 02 creates `c2`, which scenarios 04 and 11 address. The binding of variables acts
within a scenario; the data and the claims — until the end of the whole run. A repeated and a parallel run get
their own instances. Deleting only the units is not enough: old claims can return the former answers.
If the initial state, the rights or the absence of background changes are not provided, the run is not performed.

## The batch door (sc. 33–37; ADR-0094 B9)

`POST /console/batch` (Н2 «Batch door», Н3 «batch») by an open console, the stand and an empty store are as for scenarios 15–32 below; the scenarios create the unit `c1` themselves. The indices
of rows are given by the console doors (Н2 «Версии»): the element `configured`, `GET` of a table row, a tombstone — `?deleted=1&about=`; `GET /{rows}` reads the heartbeats, so sc. 33–35, 37 begin with `@start resource`. The store door stayed where the scenario looks at the row itself. The replay key is by the dictionary: the runner sets its own, `@key(N)` repeats it, `@nokey` removes it.

- Sc. 46 — the table `stash` of the manifest `testsub2` (`service: true`, P/06.1 Н1.6 `service`). Steps 2–6 — the human door and a batch row are closed, the row has not appeared (step 7). Step 8 puts a row past the door by the role `console`: the door is closed for a live row too (step 9), and the rows feed does not give out this table: `changes` of step 11 is only `c1`. Reading and writing by a ticket — [the stand of the transfer of the second kind](../../../common/acceptance/pass/README.md).
- Sc. 33 — the anchor row: `tallies` is a part of `counters` (`about: {sub: testsub, field: of}` of the manifest `testsub2`). Step 4 — a part without an anchor; steps 6–8 — a unit and a part, one index; steps 9–11 — an edit of the part raises
  the `revision` of the anchor; steps 12–13 — a stale `cas` of the second row, the first one is not written; steps 14–15 — the removal of the part is a tombstone, its index is read by `?deleted=1&about=`; step 16 — the anchor is judged at the removal too, the value `of` from the read row; steps 18–19 — a write over the tombstone by its index, the `revision` of the tombstone + 1.
- Sc. 34 — guards: step 6 — the guard row is not written; steps 10–12 — a number in `field`, the guards before `cas`.
- Sc. 35 — the replay memory: steps 4–6 — a repeat gets the saved answer, although `cas` is already stale; step 7 — a different body; step 8 — the same request without a key — 412; steps 10–13 — a refusal is remembered: a repeat gives the former index, although the row has gone further; step 14 — `If-Match` is not read.
  That `done` lies in the batch itself — by reading (Н5).
- Sc. 36 — the form and refusals; step 19 — the weight of a row is counted after the preparation; steps 20–21 — one over the limit, steps 29–30 — exactly at the limit: the claim of the runner's key does not count.
- Sc. 37 — references by the state after the batch: step 4 — the target is created by the same batch, it stands after the referring row; step 8 — the target is edited alone, the reverse `must_match`; step 10 — the pair is edited together; step 12 — the target is outside the batch; step 13 — the target is removed by the batch;
  step 16 — `unique` of two rows of the batch.

## Versions (sc. 38–40; ADR-0094 B4)

The stand and an empty store are as for scenarios 15–32 below; 38 and 40 begin with `@start resource`: `GET /{rows}` reads the heartbeats. `$имя` of an index in a request header is by the dictionary: the substitution goes into the request whole, the quotes of the value are written by the scenario.
The dictionary does not combine an expectation of the body and of a header in one cell, so `ETag` is judged by steps with `@header` without a body: whether the header is there and the quote in it. That the value equals the index — by reading; that an index from the body is good for `If-Match` — step 5 of sc. 38.

- Sc. 38 — a unit: step 4 — the `index` of the door equals the index of the store; step 5 — a condition by the index; steps 7–8 — both forms of the condition are not met, the body carries the current `revision` and `row`; step 10 — the form `revision` works as before; steps 12–15 — other values; step 20 — a condition without a row.
- Sc. 39 — the table `shelves`: step 5 — the condition is met, `revision` grows; steps 8–9 — the condition by the index is not met at `DELETE` and `POST`; steps 11, 13 — no row: `POST` — 412, `DELETE` — 404, as for units; steps 16–17 — a repeat answers from the memory before the condition; steps 19–21 — 412 is remembered and repeated, although the row has gone further; step 23 — a removed row counts anew.
- Sc. 40 — tombstones of a part: `tallies` is a part of `counters`. Step 8 — the `ETag` of the answer of `DELETE`; steps 10–12 — the listing; steps 13–15 — the form and a manifest without `about` (`testsub`); step 16 — a foreign tombstone index, there is no `row`: a tombstone is not a row; step 17 — a write over the tombstone by its index; step 19 — by the same condition by `revision`.

The right `view` on the unit `about`, `row` and the mask without the right — the acceptance P/08.4, sc. 20 and by reading (Н5): the stand of the chapter has no grants.

## The feed (sc. 41–45; ADR-0094 B2)

`GET /changes` (Н2 «Change feed», Н3 «лента») by an open console, the stand is as for scenarios 15–32 below. Each scenario runs **on its own new instance of the console and the store**: the feed remembers the rows of the previous scenario, and an empty store under a live console would give messages about their removal. The controller, the workers and the row reaper do not write, so `changes` is judged whole: the length and the order of the array.

The tick is asynchronous to the write: a message is waited for by `@until`, not by the first answer. The first `GET /changes` of a scenario is `@until` too: before the first tick the door answers 503. Messages with one `after` accumulate, so `@until` with the former `after` waits for the whole array. There is one subscriber in a scenario, the requests go one by one: the waking of the waiting one and the feed band — by reading (Н5). The form of the long poll is judged by the dictionary: the feed requires no new directives.

- Sc. 41 — the form. Step 3 — there is no value in the message; step 4 — nothing new, `position` equals `after`; step 8 — a resend gives the same `at`; step 9 — the whole history in order; steps 11–14 — `wait` holds the answer not less than named: the time is given by `server_time` of the door `/session`, so step 14 tolerates the rounding of the write (no sleep is needed); step 15 — the bound `wait=25` with a ready message does not wait; step 16 — without `after` `wait` is not read; steps 19–25 — the forms of the parameters; steps 26–27 — the door has no prefix.
- Sc. 42 — the gap of the initial load: step 5 takes a number, step 6 edits a row in the gap, step 7 reads it, step 8 — the message about the edit arrives, and the client discards it: `revision` 2 is not above the read one; step 10 — the next edit is new already. That the client discards is its norm, the door is obliged to say it. `GET /{rows}` reads the heartbeats, so the scenario begins with `@start resource`.
- Sc. 43 — deletion: the index of the tombstone is read by `store`, the message carries it (step 6); a write over the tombstone — `revision` (step 8). A table: step 14 — there is no tombstone, `deleted: ""`; steps 19–21 — the row was removed and created anew. Whether the removal and the write fell into one tick or not, the array is one: the removal before the write, otherwise the client would discard `revision` 1 as old.
- Sc. 44 — eviction: four batches of 64 rows — exactly `CHANGES_HISTORY`, the number `$p` stands before the oldest message and is still good (step 6, all 256 keys in order); one row beyond evicts it (step 8, a reset). Step 9 — a number inside the history works as before.
- Sc. 45 — restart: step 5 — a reset, step 6 — the new number is not equal to the former one, steps 8–9 — the feed goes on, the memory of the first tick knows the row `c1`; steps 10–11 — a value not by the form and a number of the former instance.

A change of a grant and of labels, the filter `view` — the acceptance [P/08.4](../../../08-domain/acceptance/4/README.md), sc. 21, 22: the stand of the chapter has no grants. The series `w2c_changes_*` — sc. 31 of [the acceptance of 6.5](../5/README.md).

## Preparation and order: scenarios 15–32 (bodies, tables, the order row, the worker table, the coverage audit)

The console doors of `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the resource `srv-a` as the first step of sc. 03, 14, 15, 18, 20 (`@start resource`: `GET /{rows}` reads the heartbeats, and the bytes door of sc. 15 writes and reads the body through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29) and by
the directive (`@start resource`, sc. 17 step 10), the store (`store …`); without workers, the controller and the domain (so `held_by` of sc. 17 steps 2–3 is `null`: there is no acting
hold of a place, Н1.6; C06-TABLE-HELD-BY-33-01). The doors and
directives are `console`, `console2`, `store`, `@start`, `@until`, `@big(N)`, `@raw`, `@header` in an expectation, `@as`, `@restart console`, `ASSERT`.

The stand: the body limit of the console is 1 MiB (the minimum of the norm; sc. 16 expects 413 at 1.1 MB), the build with schema 1, the object store with
the default ceiling. Each scenario begins with an empty store: the runner resets it between scenarios. Scenario 21 (the worker table `gauges` of `testsub2`) — likewise, on its own empty store: the row is put past the worker
by `@as testsub2worker`, the worker is not started (that it writes the row anew — by reading). Scenario 20
(ADR-0091 items 1, 3) — likewise, on its own empty store, without `c1`: the ordering party `testsub` (its `worker.creates` to
`testsub2/tallies`) is not started; the order row and the state row are put by steps 3, 8, 10 past the writer through the door
of the store (`@as console`, `@as testsub2worker`) — the door is checked, not the library. Before
scenarios 15, 16 and 18 the runner creates the counter `c1` in `testsub` (for `of` of `tallies`) — `console POST /counters` with
its own `Idempotency-Key`, before the first step; in the other scenarios there is no `c1`. The resource is started by the command of the resource role
of the server `srv-a` (the substitutions `{data}`, `{socket}`, `{manifest}`, `{rport}`); it is ready when it listens on `{rport}` and there is the row
`platform/doors/srv-a`. `console …` and `console2 …` are one console on `{port}`, the second is the prefix `/testsub2`. `store …` is
the store door by a role with full rights on the prefix of the subsystem (the common acceptance README «Stand»).

Before each scenario stop the processes of the previous one, create separate empty row/object stores and clear
the variables/the replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2;
there is no domain, the calls come from the loopback. Background processes do not run before @start. For each POST the runner issues
a fresh Idempotency-Key, kept only for repeats of the same step; `PUT` and `DELETE` carry a key only with `@header`.

Scenarios 22–27 (the coverage audit of P/06, `audit-kimi` 9007ca60f) — likewise, each on its own empty store, without `c1` (the field `of`
of `tallies` is a string, it does not require the counter to exist; likewise sc. 20), without workers, the controller and the domain; the resource
`srv-a` — as the first step of sc. 25 and 26 (`GET /{rows}`).
- Sc. 22 — direct references of the unit `tallies` (the row check contract П5, «Identifier» `ref_and_must_match`, `unique`):
  the `zone` of the unit ≠ the `zone` of the live target — 409 `conflict`/`must_match`, there is no row (steps 1–3; a successful pair — step 4); the target
  has no element `zone` (a table field without a default is not passed), the unit has `""` — 409 `must_match` (steps 5–7); no target is not
  a refusal, ADR-0057 (step 8); `feed` — `unique: canonical`: a host in another case is the same value, 409 `unique` (steps 9–10);
  the target is not readable (the row `shx` with `size: "many"` is written by the runner with the role `console`, as sc. 19 step 11) — 409 `garbled`
  (steps 11–12). There is no row — the read of the store door `{"items": null}`: one refusal code of a write does not prove it.
- Sc. 23 — `of` of `tallies` is `fixed`: a creation over a tombstone with another `of` — 400 «… is fixed», the tombstone is the former one; with the same one —
  201, the `revision` of the tombstone + 1 (Н3 «create» steps 5, 8); an edit of `of` of a live row — 400, the row and the `revision` are the former ones
  (the row check contract Р2).
- Sc. 24 — `born` of the counter row: a deletion keeps it (steps 2–4), a creation over a tombstone sets a new random one
  (steps 5–7, `ASSERT`; Н3 «create» step 8, «delete» step 2; ADR-0091 item 3).
- Sc. 25 — the counterexample of run 24 (below): `marks` `[]` and `[""]` — the row elements `""` and `'[""]'` (the row check contract
  `values_by_type` list), an edit of `start` does not touch them, after `@restart console` the listing and the rows are the same.
- Sc. 26 — the state row `testsub2/state/result/t1` with `born` and `revision` of the live row (past the holder — `@as
  testsub2worker`, as sc. 20): a `value` not by the schema `unit.state.result` (`state` not from `enum`) does not act, there is no `state` in
  the listing; the same row with a `value` by the schema acts (Н2 «Состояние в ответе»).
- Sc. 27 — PUT of `marks` of one element of 524288 bytes: the body ≈ 524310 bytes is less than the body limit of the stand (1 MiB), the weight
  of the prepared row is greater than the ceiling 524288 — 413 `row too large` without `fault`, the row and the `revision` are the former ones (Н3 «edit»
  step 6, Н4). The words of `detail` are a choice of the implementation («Implementation decides» item 4), the TSV does not compare them.

### Coverage audit of P/06, second pass (Gemini)

Scenarios 28–32 (`audit-coverage-gemini` 0a5ae79f9) — likewise, each on its own empty store, without `c1`, workers,
the controller and the domain; the resource `srv-a` — as the first step of sc. 28, 29, 30, 32 (`GET /{rows}`, the bytes door, `/metrics`). The rows
past the writer — through the store door, as sc. 20, 26: the state and the hold — by the holder role `@as testsub2worker`, the cleanup list
— by the role `console`.
- Sc. 28 — the cursor (`unit.state.cursor`) is reconciled only by `born` (the row check contract «Unit state» `acts`;
  P/03.6 Н1.7 `cursor`): both state rows with `born` and `revision` of the live row act (step 6); an edit of the row (`revision`
  2) removes the `result` of the former `revision`, the cursor stays (step 8); a cursor with another `born` does not act — there is no `state` (step 10).
- Sc. 29 — an edit of the fields removes the blob digest by an empty string (the row check contract `values_by_type` blob:
  «лишь прежний дайджест строки или "" (снять)»): 200, `revision` + 1, `""` in the row; the former digest after the removal is no longer the former
  digest of the row, 400 (Р2; Н3 «edit», «Races»).
- Sc. 30 — the bytes door removes the digest of its bytes from the list `testsub2/sweep` (Н3 «put_body» step 2), the second
  mark stays; the list is unreadable as a whole (`digests` not by the form, the outcome of the row `console` of the family `sweep`) — the door does not
  rewrite it (the version is the former one) and answers 200. Step 3 reads the version of the list, step 4 writes a non-empty batch by it: a background
  mark does not rewrite a non-empty batch (Н1.5 `mark`). The digest of `hello-blob` (10 bytes) is
  `sha256-57a256c65db5af18f8a04c7a42df26c3009dd01381fbaaaec7b432fc30d4c8d0`.
- Sc. 31 — the stamps `by`, `at`, `made_at` in the body of a table row write — 400 `unknown field` before the write (Н3
  «table — write a row» step 1; `made_at` — also outside `stamp: [by, at]` of the table `shelves`); a write without stamps — `by` and `at` of the console,
  there is no `made_at` outside `stamp` (Н1.6 `stamp`). The mark `was: true` of the overwrite log — by reading: two events of one kind in a row
  the TSV does not order (with an equal `t` the order is by `id`).
- Sc. 32 — the hold row `testsub2/holds/sh1` not by the form (`gen: "x"`, the reader outcome `console` of the family `holds`):
  `held_by` is `null` in `GET /shelves` and `GET /shelves/sh1`, not 503 (Н1.6 `held_by`; C06-TABLE-HELD-BY-33-01); the same outcome
  is distinguished from «no hold» — `/where/shelves/sh1` 503 (chapter 6.5 Н3 «`/where/<table>/<place>`») and the series
  `testsub2_shelves_open` 1 → 0 (`unheld`: an unreadable hold does not count the place as free).

Details of the steps (reconciliation of python and go М10/6–11):
- Sc. 15 steps 7–8 — the words of 404 of the bytes door (T26); steps 11–12 — another method on it is 405 (T9); step 13 — `If-Match`
  is not read by the bytes door.
- Sc. 16 steps 1, 3 — the words of the ceilings: `detail` «… the ceiling is 4000» (T24), `detail` «… this door takes at most …» (T25);
  16/4–5 — the bound of a json field of 4000/4001 bytes of canonical JSON (the mutation check 7cecaf2 № 44).
- Sc. 17 steps 11–12 — the form of the table log `{sub, target, was}` (T21); step 10 — `@start resource` (review analysis of stage B 6–7, № 22); steps 13–19 — the replay memory of the tables door.
- Sc. 18: a table row that a unit references (`tallies.shelf` → `shelves`, `must_match: {zone: zone}`) is not
  overwritten with another `zone` (the reverse side of `must_match`, Н3 step 2) and is deleted: a reference does not require the target
  (ADR-0057), the unit keeps the value.
- Sc. 19 — a change of `feed` on the tables door (S10, T13; the rule of chapter 6.2 Н3 step 3), `ftp://` (T14), null at a string field
  (T15), the key `-0.5` (T17), the order «name before field» (T18) and «key before an undeclared field» (T19), the target `over` is not
  readable (T20: the row `shx` with `size: "many"` is written by the runner with the role `console`). The stand has no ring: secrets are not
  sent in the body, the rule is checked by an empty and an absent secret.

@raw hello-blob is exactly 10 UTF-8 bytes without LF; Content-Length is computed by the bytes. @big(4100)/@big(3000)
are substituted before JSON serialization: the canonical JSON string takes 4102/3002 bytes. 1,100,000 bytes in tags exceed
the common body limit. The deletion of a blob, maintenance windows and fsync are not checked in the TSV.

## scenarios.tsv

Tab-separated: `scenario`, `step`, `request`, `expect`. Rows with `#` are notes.

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): a door without a prefix is the console; `@key`/`@nokey`, a subset of fields, `$имя` (here they bind `revision` and the digest `$d`).
Its own: the field `bytes` of the answer of the bytes door — Н2 «Doors of bodies and tables» of the chapter; the code is always compared.

Partial expectations of the TSV do not cancel the forms of the full answer: the mandatory fields, the JSON types and the restrictions
of extra fields are checked by Н2, the OpenAPI and the loaded manifest. For example, any refusal contains the string
`detail` and `error`, although the TSV often names only `error`, `fault` or the code; DELETE has only `deleted`.
The set of fields of an arbitrary unit depends on the manifest and is not checked by one common schema `Unit`.

A subset expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, the types,
Content-Type, the special headers and the absence of a body at HEAD/204. In the expectation rows `$имя` is first bound only
after a successful match of the whole answer; the following uses compare, the requests use only already bound
values. A failed attempt of @until does not change the variables. @until repeats the read up to the given local deadline, not
a mutation; after the expiry — FAIL with the last answer. @any admits any value of a present field, @absent requires
absence; they do not substitute the types of the full schema. A JSON object is compared by a subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array — by the length and the order.

In scenario 01 the runner additionally saves the **full** answer of step 1. At step 2 the code and the JSON body are to
match it whole (the order of the fields of an object does not matter, the order of arrays matters). This checks the promised
repeat, including the fields not named in the expectation of step 2. Step 3 with a different body under the former key checks 422.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptances of М10/03 and М10/10 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (review analysis of stage B 6–7, № 18).

## Additional checks R29-01…03

These are separate cases P/06.1-01, 09, 11 (formerly М10/3-01, 09, 19); they are not in the main TSV. For each case
create a separate instance with testsub, empty rows and claim memory, the needed rights
and a store with a full key limit of 1024 UTF-8 bytes; there is no narrower file limit (Н1.3). Do not count the schema check as a run of these scenarios.

| Preparation and action | Expected outcome |
|---|---|
| POST /counters with a correct body, an Idempotency-Key of 187, 188, 200 ASCII letters; each case separately (200 — in the TSV, sc. 13) | The claim key is a digest of a constant length, all three cases pass the limit; 201 with the full row; a repeat returns the same result |
| The same POST with 201 ASCII letters; separately 100/101 Cyrillic characters (200/202 UTF-8 bytes) — in the TSV, sc. 13 | 201 and 202 bytes of the component — 400 before pending; 200 bytes of the component are admitted |
| A named id of 1007/1008 ASCII letters (testsub/counters/ has 17 bytes); separately Cyrillic/four-byte characters with the same full lengths | 1024 — 201 at any implementation (the file names are encoded by the implementation, the event log contract «File names in shared trees»); 1025 — 400 badkey; a POST after its own pending keeps the refusal by step 9, the unit is not written; PUT/DELETE do not change the row/revision |
| A badkey refusal on the write of the initial pending; separately on the write of the unit, then on the saving of the answer | Before pending — 400 without a claim; after pending — 400 only after a confirmed saving of the refusal; on a failure of the saving — 503, the rules of pending and of a foreign guard are kept |

The rows of the table R29 about the slot, the epoch, the guard and holds are the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md) (the
branches of the worker of full keys, stage B).

For unique a separate manifest with `tag: {type: string, unique: true}` and two live units
c1/c2 with a/b are needed. First a sequential PUT c1→x, then PUT c2→x: the second sees the new value
and gets 409 conflict/fault unique. In a separate case both reads finish before both
writes: independent CAS of their own rows can return two 200 and leave x/x. The placement pass
by itself is not obliged to detect or fix x/x. Repeat the bound with unique: canonical
for equivalent URLs by ADR-0057 and with a change/deletion of the linked row between the check
of must_match and the write. The presence of ref without must_match does not mean must_exist. An analysis
of the real reads/writes is required; this README does not claim that any implementation was run.

Reconcile the reference holds not only for the existence of the lesson: its Н1.3 is in the norms of [P/03.2](../../../03-worker/spec/03.2-worker.norms.md)
and sets the form of the slot without server, plus by. Reconcile the other references of the key layout with the concrete
owner form; the presence of a file does not prove the correctness of the reference.

## Checks outside the sequential HTTP file

The status of all the checks of the README outside `scenarios.tsv` (this section, «Additional checks», the counterexamples of runs) is
«проверяется чтением»: the subject is the transitions of the implementation under a named intervention; the evidence is a test of the implementation
with controlled clocks and two consoles on a common store of P/01.1, or a code analysis. The stand of the section «Stand»
of the common acceptance README does not execute them: it has no controlled clocks and no two consoles.

Н5 requires separate evidence of reading or a controlled stand for races.
The table below sets the counterexamples of run 23; the execution of the steps of scenarios.tsv does not mean they pass.
The author of the implementation names the place of the check and the actual result. For numeric ids a manifest with
`unit.id: numeric` is needed; for the check of required+default — a separate instance with a copy of the current testsub,
where only the field start has required: true added, and default: 0 is kept. A POST with name without start
is to get 400, with an explicitly passed start: 0 — 201. The counterexamples of run 23 about the slot (P/03.2-01, 02, 05, 07, 08) are
the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md).

| Norm | Initial state and intervention | Expected observation |
|---|---|---|
| P/06.1-02 | Create testsub with name and without start/labels/step/marks; then edit only labels; separately — a required field with a default, not passed by the client | start = 0, labels = [], step/marks are absent; an edit of labels does not reset start. A default does not satisfy the requirement to pass a required field; the other types without a default — by the table Н1.2 |
| P/06.1-06 | Separately create c3 with name=c3; PUT /counters/c3 with name=x; re-read; then PUT with name=c3 | A new name — 400 `error: fixed`, `field: /name`, detail «name is fixed», id/name/revision are not changed; the former name — 200, the ordinary increase of revision. A PUT of an absent unit with a new name stays 404 (the read before the prohibition of the change) |
| P/06.1-07 | A holds pending, reserves 1 and is delayed before saving the number; after 30 s B takes over the claim, reserves 2; A continues | The CAS of the claim of A is refused, the unit 1 is not created; only 2 is created. A does not save the answer and does not delete the claim of B; the result of A by the current pending/done in Н3 |
| P/06.1-07 | A has already written the number 1 into the claim; B takes over before the write of the unit; A continues | B keeps the number 1; the guard of the late A is refused; B creates 1, there is no second number for this claim |
| P/06.1-07 | A created the unit but did not save the answer; B took over and finished; A tries to save the answer or remove the claim | The CAS of A is refused; the answer of B is not replaced and the claim is not removed; A returns the saved answer. On an unknown outcome of the creation 5xx does not turn into done, pending is kept for recovery |

The forms of the answers are checked separately: the values `a/b` and `..`, inadmissible at any kind of id,
do not pass UnitId; a refusal 400 of GET/DELETE with `fault: not_number` does not pass the contract.
These are probes of schemas and rules, not additional rows of the HTTP scenario with another manifest.

### Counterexamples of run 24

All the cases below are separate instances/evidence, not a continuation of the rows of the main TSV.

| Norms | Preparation and action | Expected outcome |
|---|---|---|
| P/06.1-02, 08 | In two clean states POST with name=c and marks=[] / marks=[""]; re-read the row, restart the console, PUT only start:1 (in the TSV — sc. 25) | In the store marks="" / marks='[""]'; HTTP returns the original list after the read and the edit, the values do not merge |
| P/06.1-07 | POST with the key ..; separately with the admissible . and ..foo, each on its own state | .. — 400 before pending, the row of the claim/unit does not appear; . and ..foo are not refused because of this grammar |
| P/06.1-02, 07, 08 | The body limit 1048576 bytes, the row 524288; a compact POST {"name":"wide","marks":["x" × 524288]}, then a repeat with the same key; separately a PUT of such marks into a short existing unit (PUT — in the TSV, sc. 27) | The body 524316 bytes, items 524328: 413 row too large without fault, not a refusal of the HTTP limit. The POST does not create the unit, the refusal is saved and repeated whole; the PUT keeps the former row and revision |
| P/06.1-07 | With the chosen form of the claim pick a successful answer whose done row would exceed the ceiling although the unit fits; separately a failure of the write of the result after the creation | Before the creation — 413 and a saved refusal instead of an unstorable success. On an unconfirmed saving after a written/unknown unit — 503 and pending for recovery, without deleting a foreign claim |

The weight of items is counted as the sum of the UTF-8 bytes of the names and values of the elements after the preparation of Н1.2;
it differs from the JSON bytes of the HTTP body. For the counterexample wide the materialized ones are id=wide, revision=1,
name=wide, start=0, labels="" and marks of 524288 x; step is absent. The record of the refusal of the POST is to
fit into the claim row for this stand; a repeat is compared whole. For numeric a reserve
obtained before the refusal is not returned. The variation of the successful answer depends on the declared form of the claim,
so its actual bytes and the chosen ceiling are attached by the owner of the implementation.

## Additional checks of run 25

In the TSV — sc. 23 of [the acceptance of chapter 6.5](../5/README.md): the field `cost` and `placement.weight` are declared at `probe-x`.
These checks go separately from the TSV, on an isolated copy of testsub.
Add the field cost: {type: int, default: 1} and placement.weight: {field: cost, default: 1};
do not change the other keys. For POST use a separate name and key for each case.

| Input | Expectation |
|---|---|
| POST/PUT cost = -1 or 0 | 400, `error: type`, `field: /cost`, detail «cost must be at least 1», without fault |
| POST/PUT cost = 1 | 201/200, the number 1 is kept |
| POST without cost | 201, the default 1 is materialized |
| POST/PUT cost = "1" or true | 400, fault not_number by the ordinary type check |

A refused POST does not create a unit, its repeat returns the saved answer whole.
On a refused PUT the former fields/revision are kept; after a successful PUT revision grows by 1.
Read the row before and after the refusal; one HTTP code does not prove the absence of a write.

The deadlines of the slot (the first look of the judge, until with shifts) are the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md).

## Checks of the full answer `GET /{rows}`

RunningUnit.worker have the form of a slot name of [P/03.2 Н1.4](../../../03-worker/spec/03.2-worker.norms.md).
Admissible are `w-1`, `w-server-12`, a prefix of eight letters and a long admissible suffix;
not admitted are `""`, `w`, `w-`, `w--1`, `W-1`, `w/1`, `w_1` and a final line feed.
The schema checks the common grammar; the correspondence to slot.prefix of a concrete manifest is checked
separately. CreatedUnit.worker:null is kept.

## Additional check of the class of errors of run 36 (Kimi)

By reading, check the term of completed HTTP<500 of not less than a day and the conservative recovery of the observation; the TSV is short and does not observe a day. (NameOnAnotherBox and the alarm `worker.name_taken` are the acceptance of chapter P/03.2.)

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Check of the error class R37 (Codex)

Numeric with delete_after is rejected at load; without a physical cleanup the successful numbers are kept in rows/tombstones after the cleanup of done. On a loss of the history or an incomplete read the formula recover is not applied. The source of a named id is not secret and is a string. For the file profile with a component255 bytes:201 ASCII in an id are admissible by this limit,256 —400 with detail/error naming the file restriction before the write; w- plus254 letters does not capture a slot. The long keys in the table R29 check the limit of rows, and do not promise the placement of a literal file of any length.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

## Probes of the reconciliation of python and go (2026-10-18)

The probes of the README are `decisions/inbox/2026-10-18-сверка-python-go-м10-3-5.md`; the expectation is the norms of the chapter.

| Probe | Expectation |
|---|---|
| `If-Match` and `Idempotency-Key` with a space or TAB at the edges | the value without OWS (Н2) |
| an empty `If-Match:` at PUT | 400 «If-Match is a unit revision» |
| `testsub2`: `must_match`, the target has no element, the unit has `""` | 409 `conflict`, `fault: must_match` (in the TSV — sc. 22 steps 5–7) |
| `testsub2`: url `https://h/%zz`, `https://h\a`, with TAB; `mirror://local` without a path | 400 `bad_url` |
| `start: -0` | in the store row `0` |
| a foreign `pending` younger than 30 s with a different fingerprint | 409 `in flight`; after 30 s — 422 `key reused` |
| a claim not by the form of a claim | 503 `store unavailable`, the claim is not touched |
| a heartbeat with an element `status` without the id grammar or with a fractional `epoch` | the element is not in `rows`; `worker` — from the key of the heartbeat |
| the names `A`, `é`, `.a` by the grammar | 201 at any implementation (Н1.3: there is no file profile) |

`rows` with a live worker (`phase: running`, `worker`, `worker_state: live`) — the steps of the acceptances of [P/03.3](../../../03-worker/acceptance/3/README.md) (sc. 02) and [P/03.2](../../../03-worker/acceptance/2/README.md) (sc. 08) on a catalogue of two manifests.

## Bodies and tables: probes outside TSV

From the acceptance of М10/10 (runs 33–37, R36); the subject is the reading of the norms and a future stand, not an execution of an implementation.

For 400 of a table check the full text and structured refusals. The common TextRefusal/FormRefusal overlap without fault,
so anyOf, not oneOf; check all local oneOf for an overlap of the branches.

Kimi 33: check the template of the table notches with three substitutions by the owner P/02.1. Names of tables/rows: lowercase ASCII
1–32, the prohibitions of families/doors, Audit and 33 characters are rejected at load.

The service names next_id/placement/workers/sweep and the actual unit.rows are rejected as table names, placement_log/workers2
are admissible with a correct manifest.

The name scope of all added fields: rows=cluster/worker/ts is refused, records is admissible; bytes+blob is refused, bytes
without blob is admissible. TableInput accepts the declared id and other names of the unit, but not held_by/garbled; name is admissible only
as a string with key=name.

Declarations of unit.fields with any platform_fields (Н1.2, including deleted) are rejected before the materialization of default/inherit.
Check each element of the list, an empty declaration, default and inherit; the neighbouring deleted_flag/worker_label are admissible, the names
of table fields do not get this prohibition.

Blob: an empty name, /, %, dots, a space, control characters, non-ASCII and 65 characters are rejected by the loader; admissible are _, A,
payload_2 and 64 characters. A table blob is outside the profile, the ordinary fields of a table are not narrowed by this.

R36-09/11/12: by/at/made_at cannot be declared as editable fields of tables regardless of stamp; a passed top-level stamp
gives 400 unknown field before the write, and a key of the same name inside an allowed JSON field is not affected by this prohibition. The neighbouring
by_note/at_time/made_at_hint are admissible as ordinary fields. A unit id of 201 ASCII bytes is admissible with a short full key;
200 bytes refers to rid/Idempotency-Key, not to id. A passed stamp — sc. 31 (the second pass of the coverage audit of P/06); the negative checks of a name are outside the current TSV.

Run 36 (Kimi): reconcile the priority of the common framing/length of a blob before the search for the field. A non-empty sweep batch does not refresh at/the version
and does not collect new digests; 300 s are counted by the observer of an unchanged version, a new judge/a new version start from zero.
In the exclusive window the other sweepers are stopped; do not delete on an unconfirmed quiet or read.

R37 (Codex): Table.key does not extract *_secret; a single field/an ordinary substitution — string, :int — int/float.
A non-matching declaration is refused by the loader; an absent/wrong value of the body gives 400 before the computation of
the name and the write. The names of mount and root tables are checked together at the load of the catalogue, not by the priority of the URL.

The bounds of :int by P/02.1: binary64, the absolute value not greater than 2^53−1; bool/null/a string/non-numeric/non-finite/out of bounds — 400, not
a language coercion. Check ±0.5, ±7.9, ±(2^53−1), 1e16, 1e21 and the canonical decimal result without an exponent.

The cleanup with grace — the phases of Н3 and the codes of the window command of Н2: without `--writers-stopped` nothing is deleted, the grace of 300 s of an unchanged
version, an object newer than the mark is not touched (controlled clocks are needed, the common acceptance README «Stand»). They are checked by reading (reconciliation of python and go
М10/6–11): T16 — `null` at a json field of a table and T23 — `made_at` (the tables of `testsub2` have no json field and no `made_at`).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There are no sleeps. Waiting for an event is `@until`: sc. 17 step 11 waits for the log row `shelf.declared` after `@start resource`.

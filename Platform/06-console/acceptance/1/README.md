# Acceptance P/06.1 — the units door, bodies, tables (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.1-console.norms.md`](../../spec/06.1-console.norms.md) N5. The scenarios were moved from the acceptance of
M10/03 (01–14, all) and
M10/10 (04, 05, 06, 07, 11 → 15–19) (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenarios of M10/10: their numbers 04–07 and 11 are taken
by scenarios of M10/03, they got the next free ones (`15-blob`, `16-ceilings`, `17-tables`, `18-table-ref`,
`19-table-feed`; the rows of `corrections-1.tsv` (historical correction record)). In all 46 scenarios / 514 steps: 11 — the service table (46, ADR-0094 B1, below), 79 — the feed (41–45, ADR-0094 B2, below), 65 — versions (38–40, ADR-0094 B4, below), 95 — the batch door (33–37, ADR-0094 B9, below), 100 — the units door (01–14), 56 — bodies and
tables (15–19), 16 — the order row and the unit state (20, ADR-0091), 6 — the deletion of a row of a worker table (21, the VMS request «commands and device row»),
48 — the coverage audit of P/06 (22–27, below), 38 — its second pass (Gemini; 28–32, below).

The full forms of the answers are [the OpenAPI of the lesson](../../spec/06-console.api.openapi.yaml) (the paths `/{rows}`, `/{rows}/{id}`,
`/{rows}/{id}/{blob_field}`, `/{table}`, `/{table}/{name}`). The state of the slot, the epoch and the lease is not checked here — that is
the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md).

## Preparation and order: scenarios 01–14 (the units door)

The scenarios go through the units door of the console of the subsystem `testsub` (`Platform/common/data/testsub/testsub.subsystem.yaml`, the same one as
the product's): the rows `counters`, `id: name`.

For each full run the runner creates a separate instance of the store and of the console, loads `testsub`
by P/02.1. After the installation of the manifest the application and service data of `testsub/` are empty: in particular, there are no rows
of units, tombstones, the counter and the claims `testsub/idem/`; the replay memory in the console process is empty too.
The installation rows `platform/manifest/testsub` and the marks are admitted. The controller and the workers are not started:
they are not to change or delete rows during these scenarios.

The instance is started by the section «Stand» of the common acceptance README (the substitutions `{data}`, `{port}`, `{manifest}`).
The preparation, the rights and the path to the door are provided by the runner before the requests. All the steps are called by one and the same
identity with the right to create, read, edit and delete units; in the variant without a domain the requests come from the loopback
by [chapter 6.3](../../spec/06.3-console.norms.md) N1.3 `open` (only from the loopback, otherwise 403). The runner records the address of the door, the way of preparation and the declared body limit;
the table requests are to fit in it. The limit itself stays a choice of the implementation by the norms of the chapter N4 and of chapter 6.3 N1.3 `body` (≥ 1 MiB).

Scenarios 01–14 are 100 steps. Scenarios 03 and 14 run **each on its own clean instance** (the preparation above): their steps 03/8 and
14/8 read the whole list `GET /counters`, and the door does not narrow the read to one unit (N2), so the expectation does not depend on the order of
the scenarios. The other 12 run sequentially **on one instance**, without cleanup between them. Scenario 14 is
the condition `If-Match` of PUT and DELETE (P/08.6: the domain agent applies an edit from the revision that the domain saw), steps 11–23 — the replay memory of these doors before the condition (N3 «replay memory»). Scenario 13 is
the limits of the component `Idempotency-Key` (200 bytes of UTF-8, not `..`, without `/`) of the first row of the table «Additional checks»,
moved into the TSV by the mutation check 7cecaf2 (№ 16, 17); `@header Idempotency-Key:` replaces the runner's key.
Scenario 02 creates `c2`, which scenarios 04 and 11 address. The binding of variables acts
within a scenario; the data and the claims — until the end of the whole run. A repeated and a parallel run get
their own instances. Deleting only the units is not enough: old claims can return the former answers.
If the initial state, the rights or the absence of background changes are not provided, the run is not performed.

## The batch door (sc. 33–37; ADR-0094 B9)

`POST /console/batch` (N2 «Batch door», N3 «batch») by an open console, the stand and an empty store are as for scenarios 15–32 below; the scenarios create the unit `c1` themselves. The indices
of rows are given by the console doors (N2 «Versions»): the element `configured`, `GET` of a table row, a tombstone — `?deleted=1&about=`; `GET /{rows}` reads the heartbeats, so sc. 33–35, 37 begin with `@start resource`. The store door stayed where the scenario looks at the row itself. The replay key is by the dictionary: the runner sets its own, `@key(N)` repeats it, `@nokey` removes it.

## Versions (sc. 38–40; ADR-0094 B4)

The stand and an empty store are as for scenarios 15–32 below; 38 and 40 begin with `@start resource`: `GET /{rows}` reads the heartbeats. `$name` of an index in a request header is by the dictionary: the substitution goes into the request whole, the quotes of the value are written by the scenario.
The dictionary does not combine an expectation of the body and of a header in one cell, so `ETag` is judged by steps with `@header` without a body: whether the header is there and the quote in it. That the value equals the index — by reading; that an index from the body is good for `If-Match` — step 5 of sc. 38.

The right `view` on the unit `about`, `row` and the mask without the right — the acceptance P/08.4, sc. 20 and by reading (N5): the stand of the chapter has no grants.

## The feed (sc. 41–45; ADR-0094 B2)

`GET /changes` (N2 «Change feed», N3 «feed») by an open console, the stand is as for scenarios 15–32 below. Each scenario runs **on its own new instance of the console and the store**: the feed remembers the rows of the previous scenario, and an empty store under a live console would give messages about their removal. The controller, the workers and the row reaper do not write, so `changes` is judged whole: the length and the order of the array.

The tick is asynchronous to the write: a message is waited for by `@until`, not by the first answer. The first `GET /changes` of a scenario is `@until` too: before the first tick the door answers 503. Messages with one `after` accumulate, so `@until` with the former `after` waits for the whole array. There is one subscriber in a scenario, the requests go one by one: the waking of the waiting one and the feed band — by reading (N5). The form of the long poll is judged by the dictionary: the feed requires no new directives.

A change of a grant and of labels, the filter `view` — the acceptance [P/08.4](../../../08-domain/acceptance/4/README.md), sc. 21, 22: the stand of the chapter has no grants. The series `w2c_changes_*` — sc. 31 of [the acceptance of 6.5](../5/README.md).

## Preparation and order: scenarios 15–32 (bodies, tables, the order row, the worker table, the coverage audit)

The console doors of `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the resource `srv-a` as the first step of sc. 03, 14, 15, 18, 20 (`@start resource`: `GET /{rows}` reads the heartbeats, and the bytes door of sc. 15 writes and reads the body through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29) and by
the directive (`@start resource`, sc. 17 step 10), the store (`store …`); without workers, the controller and the domain (so `held_by` of sc. 17 steps 2–3 is `null`: there is no acting
hold of a place, N1.6; C06-TABLE-HELD-BY-33-01). The doors and
directives are `console`, `console2`, `store`, `@start`, `@until`, `@big(N)`, `@raw`, `@header` in an expectation, `@as`, `@restart console`, `ASSERT`.

The stand: the body limit of the console is 1 MiB (the minimum of the norm), the build with schema 1, the object store with
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

### Coverage audit of P/06, second pass (Gemini)

Scenarios 28–32 (`audit-coverage-gemini` 0a5ae79f9) — likewise, each on its own empty store, without `c1`, workers,
the controller and the domain; the resource `srv-a` — as the first step of sc. 28, 29, 30, 32 (`GET /{rows}`, the bytes door, `/metrics`). The rows
past the writer — through the store door, as sc. 20, 26: the state and the hold — by the holder role `@as testsub2worker`, the cleanup list
— by the role `console`.

@raw hello-blob is exactly 10 UTF-8 bytes without LF; Content-Length is computed by the bytes. @big(4100)/@big(3000)
are substituted before JSON serialization: the canonical JSON string takes 4102/3002 bytes. 1,100,000 bytes in tags exceed
the common body limit. The deletion of a blob, maintenance windows and fsync are not checked in the TSV.

## scenarios.tsv

Tab-separated: `scenario`, `step`, `request`, `expect`. Rows with `#` are notes.

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): a door without a prefix is the console; `@key`/`@nokey`, a subset of fields, `$name` (here they bind `revision` and the digest `$d`).
Its own: the field `bytes` of the answer of the bytes door — N2 «Doors of bodies and tables» of the chapter; the code is always compared.

Partial expectations of the TSV do not cancel the forms of the full answer: the mandatory fields, the JSON types and the restrictions
of extra fields are checked by N2, the OpenAPI and the loaded manifest. For example, any refusal contains the string
`detail` and `error`, although the TSV often names only `error`, `fault` or the code; DELETE has only `deleted`.
The set of fields of an arbitrary unit depends on the manifest and is not checked by one common schema `Unit`.

A subset expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, the types,
Content-Type, the special headers and the absence of a body at HEAD/204. In the expectation rows `$name` is first bound only
after a successful match of the whole answer; the following uses compare, the requests use only already bound
values. A failed attempt of @until does not change the variables. @until repeats the read up to the given local deadline, not
a mutation; after the expiry — FAIL with the last answer. @any admits any value of a present field, @absent requires
absence; they do not substitute the types of the full schema. A JSON object is compared by a subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array — by the length and the order.

In scenario 01 the runner additionally saves the **full** answer of step 1. At step 2 the code and the JSON body are to
match it whole (the order of the fields of an object does not matter, the order of arrays matters). This checks the promised
repeat, including the fields not named in the expectation of step 2.

Reconcile the reference holds not only for the existence of the lesson: its N1.3 is in the norms of [P/03.2](../../../03-worker/spec/03.2-worker.norms.md)
and sets the form of the slot without server, plus by. Reconcile the other references of the key layout with the concrete
owner form; the presence of a file does not prove the correctness of the reference.

## Checks outside the sequential HTTP file

The status of all the checks of the README outside `scenarios.tsv` (this section, «Additional checks», the counterexamples of runs) is
«checked by reading»: the subject is the transitions of the implementation under a named intervention; the evidence is a test of the implementation
with controlled clocks and two consoles on a common store of P/01.1, or a code analysis. The stand of the section «Stand»
of the common acceptance README does not execute them: it has no controlled clocks and no two consoles.

The deadlines of the slot (the first look of the judge, until with shifts) are the acceptance of [chapter P/03.2](../../../03-worker/acceptance/2/README.md).

## Additional check of the class of errors of run 36 (Kimi)

By reading, check the term of completed HTTP<500 of not less than a day and the conservative recovery of the observation; the TSV is short and does not observe a day. (NameOnAnotherBox and the alarm `worker.name_taken` are the acceptance of chapter P/03.2.)

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There are no sleeps. Waiting for an event is `@until`: sc. 17 step 11 waits for the log row `shelf.declared` after `@start resource`.

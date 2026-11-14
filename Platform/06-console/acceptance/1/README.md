# Acceptance P/06.1 — the units door, bodies, tables (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.1-console.norms.md`](../../spec/06.1-console.norms.md) N5. In all 46 scenarios / 514 steps.

The full forms of the answers are [the OpenAPI of the lesson](../../spec/06-console.api.openapi.yaml) (the paths `/{rows}`, `/{rows}/{id}`,
`/{rows}/{id}/{blob_field}`, `/{table}`, `/{table}/{name}`). The state of the slot, the epoch and the lease is not checked here — that is
the acceptance of chapter P/03.2.

## Preparation and order: the units door

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

Some scenarios run each **on their own clean instance** (the preparation above); the others run sequentially **on one instance**, without cleanup between them. The binding of variables acts
within a scenario; the data and the claims — until the end of the whole run. A repeated and a parallel run get
their own instances. Deleting only the units is not enough: old claims can return the former answers.
If the initial state, the rights or the absence of background changes are not provided, the run is not performed.

## The batch door

`POST /console/batch` (N2 «Batch door», N3 «batch») by an open console, the stand and an empty store are as in the preparation for bodies and tables below. The indices
of rows are given by the console doors (N2 «Versions»): the element `configured`, `GET` of a table row, a tombstone — `?deleted=1&about=`; `GET /{rows}` reads the heartbeats. The store door stayed where the scenario looks at the row itself. The replay key is by the dictionary: the runner sets its own, `@key(N)` repeats it, `@nokey` removes it.

## Versions

The stand and an empty store are as in the preparation for bodies and tables below. `GET /{rows}` reads the heartbeats. `$name` of an index in a request header is by the dictionary: the substitution goes into the request whole, the quotes of the value are written by the scenario.
The dictionary does not combine an expectation of the body and of a header in one cell, so `ETag` is judged by steps with `@header` without a body: whether the header is there and the quote in it. That the value equals the index — by reading; that an index from the body is good for `If-Match` — by a scenario step.

The right `view` on the unit `about`, `row` and the mask without the right — the acceptance P/08.4 and by reading (N5): the stand of the chapter has no grants.

## The feed

`GET /changes` (N2 «Change feed», N3 «feed») by an open console, the stand is as in the preparation for bodies and tables below. Each scenario runs **on its own new instance of the console and the store**: the feed remembers the rows of the previous scenario, and an empty store under a live console would give messages about their removal. The controller, the workers and the row reaper do not write, so `changes` is judged whole: the length and the order of the array.

The tick is asynchronous to the write: a message is waited for by `@until`, not by the first answer. The first `GET /changes` of a scenario is `@until` too: before the first tick the door answers 503. Messages with one `after` accumulate, so `@until` with the former `after` waits for the whole array. There is one subscriber in a scenario, the requests go one by one: the waking of the waiting one and the feed band — by reading (N5). The form of the long poll is judged by the dictionary: the feed requires no new directives.

A change of a grant and of labels, the filter `view` — the acceptance [P/08.4](../../../08-domain/acceptance/4/README.md): the stand of the chapter has no grants. The series `w2c_changes_*` — [the acceptance of 6.5](../5/README.md).

## Preparation and order: bodies, tables, the order row, the worker table

The console doors of `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the resource `srv-a` (`@start resource`: `GET /{rows}` reads the heartbeats, and the bytes door writes and reads the body through the objects door of the resource of its server), the store (`store …`); without workers, the controller and the domain. The doors and
directives are `console`, `console2`, `store`, `@start`, `@until`, `@big(N)`, `@raw`, `@header` in an expectation, `@as`, `@restart console`, `ASSERT`.

The stand: the body limit of the console is 1 MiB (the minimum of the norm), the build with schema 1, the object store with
the default ceiling. Each scenario begins with an empty store: the runner resets it between scenarios. The resource is started by the command of the resource role
of the server `srv-a` (the substitutions `{data}`, `{socket}`, `{manifest}`, `{rport}`); it is ready when it listens on `{rport}` and there is the row
`platform/doors/srv-a`. `console …` and `console2 …` are one console on `{port}`, the second is the prefix `/testsub2`. `store …` is
the store door by a role with full rights on the prefix of the subsystem (the common acceptance README «Stand»).

Before each scenario stop the processes of the previous one, create separate empty row/object stores and clear
the variables/the replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2;
there is no domain, the calls come from the loopback. Background processes do not run before @start. For each POST the runner issues
a fresh Idempotency-Key, kept only for repeats of the same step; `PUT` and `DELETE` carry a key only with `@header`.

The deletion of a blob, maintenance windows and fsync are not checked in the TSV.

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
absence; they do not substitute the types of the full schema. A JSON object is compared by a subset (`{}` at any level is exactly an empty object: the dictionary of the common README), an array — by the length and the order.

Reconcile the reference holds not only for the existence of the lesson: its N1.3 is in the norms of [P/03.2](../../../03-worker/spec/03.2-worker.norms.md)
and sets the form of the slot without server, plus by. Reconcile the other references of the key layout with the concrete
owner form; the presence of a file does not prove the correctness of the reference.

## Checks outside the sequential HTTP file

The controlled machine checks use [seams.tsv](seams.tsv) (judge-only: controlled failure cases) through the existing ports of [the forms README](../../forms/README.md).
The status of the other checks of the README outside `scenarios.tsv` (judge-only: checking material outside M) (this section, «Additional checks», additional examples) is
«checked by reading»: the subject is the transitions of the implementation under a named intervention; the evidence is a test of the implementation
with controlled clocks and two consoles on a common store of P/01.1, or a code analysis. The stand of the section «Stand»
of the common acceptance README does not execute them: it has no controlled clocks and no two consoles.

The deadlines of the slot (the first look of the judge, until with shifts) are the acceptance of chapter P/03.2.

The blob admission interval of P/06.1-R120 is checked by reading the implementation: the sequential HTTP file cannot keep two
PUT requests unfinished while issuing a third. Trace two admitted unfinished blob PUT requests on different connections and subsystem
doors of one console instance. A third request receives the existing 503 with Retry-After before body reading; a place remains
occupied until its admitted request has sent the full response or terminated, including after its body has been read.
The internal admission mechanism is not prescribed or judged.

### Recovery observations

For `console-next-id`, `row_listing`, `tombstones` and `live_claims` independently select the outcome of each required history read. Cases `s03-counter-history-unknown`, `s12-counter-tombstones-unknown` and `s13-counter-live-claims-unknown` leave exactly one read unconfirmed and the other two confirmed. Each must return 503 without issuing a number or rewriting the counter. This tests the existing full-history condition of P/06.1-R102 and the `next-id` family outcomes.

For `console-repeat`, `s08-review127-plan-unknown` confirms the owned saved intent before the target call. Its negative pair `s14-post-plan-still-unknown` leaves the reread unconfirmed: the request returns 503 and makes no target write, including before confirmation. The pending claim remains subject to P/06.1-R381 and P/06.1-R388. An unreadable or unconfirmed planning result cannot be replaced with an invented successful intent.

These cases inject dependency outcomes into ordinary console code. They do not demonstrate a disk failure, a power cut or storage durability.

## Additional checks

By reading, check the term of completed HTTP<500 of not less than a day and the conservative recovery of the observation; the TSV is short and does not observe a day. (NameOnAnotherBox and the alarm `worker.name_taken` are the acceptance of chapter P/03.2.)

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

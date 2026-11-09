# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/1/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

The norm of the chapter is [`06.1-console.norms.md`](../../spec/06.1-console.norms.md) N5. The scenarios were moved from the acceptance of
M10/03 (01–14, all) and
M10/10 (04, 05, 06, 07, 11 → 15–19) (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenarios of M10/10: their numbers 04–07 and 11 are taken
by scenarios of M10/03, they got the next free ones (`15-blob`, `16-ceilings`, `17-tables`, `18-table-ref`,
`19-table-feed`; the rows of `corrections-1.tsv` (historical correction record)). In all 46 scenarios / 514 steps: 11 — the service table (46, ADR-0094 B1, below), 79 — the feed (41–45, ADR-0094 B2, below), 65 — versions (38–40, ADR-0094 B4, below), 95 — the batch door (33–37, ADR-0094 B9, below), 100 — the units door (01–14), 56 — bodies and
tables (15–19), 16 — the order row and the unit state (20, ADR-0091), 6 — the deletion of a row of a worker table (21, the VMS request «commands and device row»),
48 — the coverage audit of P/06 (22–27, below), 38 — its second pass (Gemini; 28–32, below).

## Preparation and order: scenarios 01–14 (the units door)

Scenarios 01–14 are 100 steps. Scenarios 03 and 14 run **each on its own clean instance** (the preparation above): their steps 03/8 and
14/8 read the whole list `GET /counters`, and the door does not narrow the read to one unit (N2), so the expectation does not depend on the order of
the scenarios. The other 12 run sequentially **on one instance**, without cleanup between them. Scenario 14 is
the condition `If-Match` of PUT and DELETE (P/08.6: the domain agent applies an edit from the revision that the domain saw), steps 11–23 — the replay memory of these doors before the condition (N3 «replay memory»). Scenario 13 is
the limits of the component `Idempotency-Key` (200 bytes of UTF-8, not `..`, without `/`) of the first row of the table «Additional checks»,
moved into the TSV by the mutation check 7cecaf2 (№ 16, 17); `@header Idempotency-Key:` replaces the runner's key.
Scenario 02 creates `c2`, which scenarios 04 and 11 address. The binding of variables acts

## The batch door (sc. 33–37; ADR-0094 B9)

`POST /console/batch` (N2 «Batch door», N3 «batch») by an open console, the stand and an empty store are as for scenarios 15–32 below; the scenarios create the unit `c1` themselves. The indices
of rows are given by the console doors (N2 «Versions»): the element `configured`, `GET` of a table row, a tombstone — `?deleted=1&about=`; `GET /{rows}` reads the heartbeats, so sc. 33–35, 37 begin with `@start resource`. The store door stayed where the scenario looks at the row itself. The replay key is by the dictionary: the runner sets its own, `@key(N)` repeats it, `@nokey` removes it.

## Versions (sc. 38–40; ADR-0094 B4)

The stand and an empty store are as for scenarios 15–32 below; 38 and 40 begin with `@start resource`: `GET /{rows}` reads the heartbeats. `$name` of an index in a request header is by the dictionary: the substitution goes into the request whole, the quotes of the value are written by the scenario.
The dictionary does not combine an expectation of the body and of a header in one cell, so `ETag` is judged by steps with `@header` without a body: whether the header is there and the quote in it. That the value equals the index — by reading; that an index from the body is good for `If-Match` — step 5 of sc. 38.

The right `view` on the unit `about`, `row` and the mask without the right — the acceptance P/08.4, sc. 20 and by reading (N5): the stand of the chapter has no grants.

## The feed (sc. 41–45; ADR-0094 B2)

`GET /changes` (N2 «Change feed», N3 «feed») by an open console, the stand is as for scenarios 15–32 below. Each scenario runs **on its own new instance of the console and the store**: the feed remembers the rows of the previous scenario, and an empty store under a live console would give messages about their removal. The controller, the workers and the row reaper do not write, so `changes` is judged whole: the length and the order of the array.

A change of a grant and of labels, the filter `view` — the acceptance [P/08.4](../../../08-domain/acceptance/4/README.md), sc. 21, 22: the stand of the chapter has no grants. The series `w2c_changes_*` — sc. 31 of [the acceptance of 6.5](../5/README.md).

## Preparation and order: scenarios 15–32 (bodies, tables, the order row, the worker table, the coverage audit)

The console doors of `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the resource `srv-a` as the first step of sc. 03, 14, 15, 18, 20 (`@start resource`: `GET /{rows}` reads the heartbeats, and the bytes door of sc. 15 writes and reads the body through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29) and by
the directive (`@start resource`, sc. 17 step 10), the store (`store …`); without workers, the controller and the domain (so `held_by` of sc. 17 steps 2–3 is `null`: there is no acting
hold of a place, N1.6; C06-TABLE-HELD-BY-33-01). The doors and

the default ceiling. Each scenario begins with an empty store: the runner resets it between scenarios. Scenario 21 (the worker table `gauges` of `testsub2`) — likewise, on its own empty store: the row is put past the worker
by `@as testsub2worker`, the worker is not started (that it writes the row anew — by reading). Scenario 20
(ADR-0091 items 1, 3) — likewise, on its own empty store, without `c1`: the ordering party `testsub` (its `worker.creates` to
`testsub2/tallies`) is not started; the order row and the state row are put by steps 3, 8, 10 past the writer through the door
of the store (`@as console`, `@as testsub2worker`) — the door is checked, not the library. Before
scenarios 15, 16 and 18 the runner creates the counter `c1` in `testsub` (for `of` of `tallies`) — `console POST /counters` with
its own `Idempotency-Key`, before the first step; in the other scenarios there is no `c1`. The resource is started by the command of the resource role

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

In scenario 01 the runner additionally saves the **full** answer of step 1. At step 2 the code and the JSON body are to
match it whole (the order of the fields of an object does not matter, the order of arrays matters). This checks the promised
repeat, including the fields not named in the expectation of step 2.


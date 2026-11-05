# Acceptance P/03.3 — the reconciliation loop of the worker (stand)

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.3-worker.norms.md`](../../spec/03.3-worker.norms.md) Н5. The scenarios were moved from the acceptance of
М10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones, except sc. 02 and 06: the first step is `@start resource`, the former ones are shifted by one
— the controller and the console read the heartbeats of the workers through the objects door of the resource of their server, without the resource «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`;
P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). The chapter is read after lesson P/04: the scenarios wait for an assignment from the controller.
Five scenarios / 49 steps; sc. 12 `12-row-unreadable` (the VMS request «пульс и битая строка») — also the resource `srv-a` (`@start resource`): the heartbeat is read through the door of the resource, the unit row is put bypassing the console by `@as console store`. Sc. 25 `25-unit-never-read` (coverage audit of P/03, 2026-10-30) — the unit row is broken (`start: "x"`) already before the first read: there is no controller, the assignment `testsub/workers/w-1` (the form of P/04 Н1.1) and the unit row are put by the runner through the door `admin`; the unit does not start, there is no epoch, the heartbeat element is `phase: unreadable` without `epoch` and `observed_revision`, `garbled_rows` ≥ 1 (`ASSERT`), `pass_failures` 0 (Н3 the loop, step 2; chapter 3.4 Н1.1). Sc. 35 `35-unit-born-changed` (coverage audit of P/03, the second pass of Gemini, 2026-10-30, the draft G06) — the unit row and the assignment, as in sc. 25, through the door `admin`, there is no controller; the unit runs under epoch 1, then the runner rewrites its row with a new `born` (a new life, the row check contract `born`) and `revision` 2, while the unit stays in the assignment `testsub/workers/w-1`: the worker stops it, releases the epoch and takes a new one — epoch 2, the heartbeat element `running` under epoch 2 and `observed_revision` 2 (Н3 the loop, step 2 «born сменился»; in sc. 02 an edit without a change of `born` does not change the epoch).

The scenarios run on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers `testsub` (the training worker of counters), which the runner controls. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of the section «Стенд» of the common acceptance README (reconciliation of python and go М10/3–5, item 24): the worker of one manifest does not touch the rows of the other on capture and cleanup. The training worker `testsub` reports the started counter by the element `status` with `phase: running` ([chapter 3.4](../../spec/03.4-worker.norms.md) Н1.1 `phase`) and one word of the subsystem `n` — the value of the counter (chapter 3.4 Н1.1 `status`; the second pilot, `Н-7`). Observation — rows through the store door P/01.1 and units through the console door P/06.1; the heartbeat (an object) is not read here. The controller is a neighbour by contract (the data catalogue, `lifecycle.md` of P/04), not the norms of P/04 (the plan of the move of lesson 3, В2).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `store` (a role with read rights on `testsub/`), `console`, `resource` and `admin` (sc. 25, 35), the directives `@start`,
`@sleep`, `@until`, `@as`, `ASSERT`; the expectation is a subset of fields.

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 Н1.2) — with full rights on `testsub/` and `testsub2/`.

The stand begins with an empty store and without workers; the runner stops everything it started after the last step of a scenario. One scenario takes no longer than 3 minutes.

**Scenarios of 2026-10-18** (reconciliation of python and go М10/3–5):
- sc. 02 step 8 — `rows` of the units door (P/06.1 Н2): an element of a live heartbeat with `phase: running`, `worker`,
  `worker_state: live`; an empty `rows` with a live worker — FAIL.

## `journal/corrections-3.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М10/05 (removed by the move), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are resolved by
`Platform/common/id-map.tsv`; analysis of the review of stage B 3–5, № 30).

## Scenario boundaries

Between scenarios the runner stops all the processes it started, resets the store (rows and objects) and the variables `$имя`: each scenario begins with an empty store, there is no slot `w-1`, the console is restarted.

## Exact preparation and completion

Each scenario gets a new isolated store, a new console, an empty id memory of the store
and empty POST claims, and also cleared objects of heartbeats/controller/contenders and cleared runner variables.
Before the start the catalogue `testsub` and `testsub2` from the common testdata and the service marks of the manifests are installed.
There are no foreign controllers, resources, spare processes or start timers. The console door is open from the loopback;
the read role of the store has access to testsub/ and testsub2/. The preparation uses separate administrative rights.

All the workers of a scenario have the constant BOX_ID of the stand and server = srv-a; each copy gets a new
instance. The name is passed by the substitution `{name}` of the directive (the common acceptance README, «Stand»; analysis of the review of stage B 3–5, № 33). A decreasing memory budget is not provoked: the chosen
CAPACITY/WORKER_MEMORY_MB must satisfy Н1.2 of chapter 3.4. The ordinary configuration of testsub uses
safe defaults; the parameters of the stand-in and of the deadlines are not accelerated for the sake of the test.

@start confirms the start of the process, the readiness of the slot is checked by the following @until.
After the scenario the runner terminates and waits for all the created processes,
and only then deletes the state. A parallel scenario uses other ports and directories.

## Exact comparison and boundaries

The TSV header and comments are skipped. The step numbers are continuous inside a scenario.
@until repeats only the nested request and the comparison up to the limit; an exhausted limit — FAIL.
The directive ASSERT compares bound values: `$имя` is bound at its first appearance, then compared.
The new bindings of variables of each comparison attempt are first temporary: they become common only
after the match of the code and of the whole expect. A repeat of a variable inside expect is compared with its temporary
value. A failure of any field, type, array element or code discards all the new bindings of this
attempt; the already common bindings do not change. The order of traversing the fields does not change the result.
This applies both to an ordinary HTTP step, and to each attempt of @until, and to ASSERT.
@any requires the presence of a field; @absent — its absence; ~text — a string occurrence.
JSON types are exact, true is not equal to 1; objects are compared by the given fields recursively,
arrays — by the number, order and values of the elements, except arrays without a normed order (`configured`) — the dictionary of the common acceptance README. An expectation of a single code does not require an empty body.
The full HTTP answer additionally matches the contract of the store (P/01.1) or of units (P/06, chapter 6.1).

The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes
of a unit. A change of the epoch/assignment by itself does not prove that the old process has stopped working.
06-deleted ends with a new assignment and epoch 2; the absence of growth before the new assignment is not measured
separately. The other evidence is Н5 of the norms of the chapter, «Evidence outside TSV».

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`. The remaining sleeps are a check of absence or the time before an action; the length is the smallest by the deadlines of Н1.2 of [chapter 3.2](../../spec/03.2-worker.norms.md) and Н1.2 of chapter 3.3:

| Sc./step | Sleep | Reason |
|---|---|---|
| 02/10 | 12 s | absence: an edit of the row does not raise the epoch; the worker would see a new revision within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s |
| 06/9 | 12 s | time before an action: the worker must see the empty assignment (the lease step ≈ 8.3 s and a pass) before `c6` is created again; its heartbeat is an object, the stand of the chapter does not read it |

SDK tests at the seams are in [seams.tsv](seams.tsv); their adapter contract is [forms/README.md](../../forms/README.md). They supplement the process scenarios and do not change the counts above or replace a reading witness they do not execute.

# Acceptance P/03.3 — the reconciliation loop of the worker (stand)

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.3-worker.norms.md`](../../spec/03.3-worker.norms.md) N5. The scenarios were moved from the acceptance of
M10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones, except sc. 02 and 06: the first step is `@start resource`, the former ones are shifted by one
— the controller and the console read the heartbeats of the workers through the objects door of the resource of their server, without the resource «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`;
P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). The chapter is read after lesson P/04: the scenarios wait for an assignment from the controller.
Five scenarios / 49 steps; sc. 12 `12-row-unreadable` (the VMS request «heartbeat and a garbled row») — also the resource `srv-a` (`@start resource`): the heartbeat is read through the door of the resource, the unit row is put bypassing the console by `@as console store`. Sc. 25 `25-unit-never-read` (coverage audit of P/03, 2026-10-30) — the unit row is broken (`start: "x"`) already before the first read: there is no controller, the assignment `testsub/workers/w-1` (the form of P/04 N1.1) and the unit row are put by the judge through the door `admin`; the unit does not start, there is no epoch, the heartbeat element is `phase: unreadable` without `epoch` and `observed_revision`, `garbled_rows` ≥ 1 (`ASSERT`), `pass_failures` 0 (N3 the loop, step 2; chapter 3.4 N1.1). Sc. 35 `35-unit-born-changed` (coverage audit of P/03, the second pass of Gemini, 2026-10-30, the draft G06) — the unit row and the assignment, as in sc. 25, through the door `admin`, there is no controller; the unit runs under epoch 1, then the judge rewrites its row with a new `born` (a new life, the row check contract `born`) and `revision` 2, while the unit stays in the assignment `testsub/workers/w-1`: the worker stops it, releases the epoch and takes a new one — epoch 2, the heartbeat element `running` under epoch 2 and `observed_revision` 2 (N3 the loop, step 2 «born changed»; in sc. 02 an edit without a change of `born` does not change the epoch).

The scenarios run on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers `testsub` (the training worker of counters), which the steps of the scenario start. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of the section «Stand» of the common acceptance README (reconciliation of python and go M10/3–5, item 24): the worker of one manifest does not touch the rows of the other on capture and cleanup. The training worker `testsub` reports the started counter by the element `status` with `phase: running` ([chapter 3.4](../../spec/03.4-worker.norms.md) N1.1 `phase`) and one word of the subsystem `n` — the value of the counter (chapter 3.4 N1.1 `status`; the second pilot, `N-7`). Observation — rows through the store door P/01.1 and units through the console door P/06.1; the heartbeat (an object) is not read here. The controller is a neighbour by contract (the data catalogue, `lifecycle.md` of P/04), not the norms of P/04 (the plan of the move of lesson 3, V2).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `store` (a role with read rights on `testsub/`), `console`, `resource` and `admin` (sc. 25, 35), the directives `@start`,
`@sleep`, `@until`, `@as`, `ASSERT`; the body of an answer is compared by the mode `body` of the routing row of the target («Expectation» of the dictionary).

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 N1.2) — with full rights on `testsub/` and `testsub2/`.

Each scenario runs on the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand) of the common acceptance README: a fresh stand per scenario, no foreign processes, one box, the stop of `@sigterm` and `@sigkill`, the time of a scenario. What is own to the chapter is in the section «[Stand and steps of the chapter](#stand-and-steps-of-the-chapter)» below.

**Scenarios of 2026-10-18** (reconciliation of python and go M10/3–5):
- sc. 02 step 8 — `rows` of the units door (P/06.1 N2): an element of a live heartbeat with `phase: running`, `worker`,
  `worker_state: live`; an empty `rows` with a live worker — FAIL.

## Stand and steps of the chapter

The boundaries of each scenario are those of the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand). Own to the chapter:

- the read role of the store has full rights on `testsub/` and `testsub2/` (above); the door `admin` prepares the rows of sc. 25 and 35 bypassing their writers;
- every worker has the box and the server of the stand; the name is passed by the substitution `{name}` of the directive (the common acceptance README, «Stand»; analysis of the review of stage B 3–5, № 33);
- the chosen `CAPACITY`/`WORKER_MEMORY_MB` satisfy N1.2 of chapter 3.4: a decreasing memory budget is not provoked;
- `@start` confirms the start of the process, not its life; the readiness of the slot is checked by the following `@until`.

The comparison is «Expectation» of the [dictionary](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) with the full form by
door. The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes of a unit;
a change of the epoch or of the assignment by itself does not prove that the old process has stopped working. The other evidence is N5 of the
norms of the chapter, «Evidence outside TSV».

## Not judged in this lesson

- The absence of growth of the counter of 06-deleted between the delete and the new assignment: the scenario ends with the new assignment and
  epoch 2, and the TSV does not observe the external writes of a unit; the stop of the deleted unit is the order of N3 the loop (step 2) and
  the seams of [the chapter](seams.tsv) do not execute it; checked by reading N3 and N5 of the norms.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

The generic meanings of `@sleep` and `@until` are defined in the [common stand protocol](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). Scenario-specific wait steps, durations and reasons are kept in the [judge-only case instructions](sleeps.cases.md).

SDK tests at the seams are in [seams.tsv](seams.tsv); their adapter contract is [forms/README.md](../../forms/README.md). They supplement the process scenarios and do not change the counts above or replace a reading witness they do not execute.

# Acceptance P/03.4 — the heartbeat, writes, the stop, the budget (stand)

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.4-worker.norms.md`](../../spec/03.4-worker.norms.md) Н5. The scenario was moved from the acceptance of
М10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the number of the scenario and of the steps are the former ones, except the first step `@start resource` of sc. 03: the controller reads the heartbeat of the worker through the objects door of the resource of its server, without the resource «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Four scenarios / 36 steps: 03-sigterm (9), 13-pulse-counters (9; the VMS request «пульс и битая строка»: the counts of the heartbeat and the rows of `/metrics`, with the resource `srv-a` — the heartbeat is read through its door), 36-previous-heartbeat (12), 37-place-released-on-sigterm (6) (coverage audit of P/03, the second pass of Gemini).

The scenario runs on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers `testsub` (the training worker of counters), which the runner controls. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of the section «Стенд» of the common acceptance README (reconciliation of python and go М10/3–5, item 24). Observation — rows through the store door P/01.1; the heartbeat (an object) is not read here. The controller is a neighbour by contract (the data catalogue, `lifecycle.md` of P/04), not the norms of P/04 (the plan of the move of lesson 3, В2): step 8 sees that the placement is removed by the controller with a reason.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `store` (a role with read rights on `testsub/`), `console`, `resource` and `admin` (sc. 37 — the shelf), the directives `@start`, `@sigterm`,
`@sigkill`, `@spoil object` (sc. 36), `@until`; the expectation is a subset of fields.

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 Н1.2) — with full rights on `testsub/` and `testsub2/`.

The stand begins with an empty store and without workers; the runner stops everything it started after the last step of a scenario. One scenario takes no longer than 3 minutes.

**Coverage audit of P/03, second pass (Gemini)** (2026-10-30, the report `gemini/audit-coverage` `fad5fa2ba`, the drafts G03, G05;
analysis by the Specification):
- sc. 36 — the fields `previous_*` of the heartbeat (Н1.1; chapter 3.2 Н3 «start()» step 4): the copy `w-1` is killed by `@sigkill`, its heartbeat remained;
  a new copy of the same box takes the name (`gen` 2) and writes `previous_instance` — the instance of the killed one, `previous_server` — `srv-a`,
  `previous_hb` — a time by the form (`@time`; the step does not compare equality with `ts` of the found heartbeat: the type of the time notation —
  a string or a number — is the writer's choice, P/01.1 Н0). Then this copy is killed too, its heartbeat is spoiled by `@spoil object` (the writer is
  stopped — the dictionary): the third copy (`gen` 3) has no fields `previous_*` — the found heartbeat is unreadable, the fields are not written
  (`heartbeats.outcomes.tsv` `<s>worker`);
- sc. 37 — the worker `testsub2` took its own place `sh1` (the shelf — through the door `admin`, as in sc. 23 of the acceptance of chapter 3.2); on `@sigterm`
  the hold row is released (`released: "true"`, `by` as before) and the slot is released (Н3 «stop by SIGTERM» step 4; chapter 3.2
  Н3 «место» `отпустить` — before the release of the slot; the steps do not distinguish the order of the two writes — by reading).

## `journal/corrections-4.tsv`

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
CAPACITY/WORKER_MEMORY_MB must satisfy Н1.2 of the chapter. The ordinary configuration of testsub uses
safe defaults; the parameters of the stand-in and of the deadlines are not accelerated for the sake of the test.

@start confirms the start of the process, the readiness of the slot is checked by the following @until.
@sigterm sends the signal to the right process and **waits for a confirmed termination**;
a timeout/a wrong process is a refusal of the runner, not ok.
After the scenario the runner terminates and waits for all the created processes,
and only then deletes the state. A parallel scenario uses other ports and directories.

## Exact comparison and boundaries

The TSV header and comments are skipped. The step numbers are continuous inside a scenario.
@until repeats only the nested request and the comparison up to the limit; an exhausted limit — FAIL.
The new bindings of variables of each comparison attempt are first temporary: they become common only
after the match of the code and of the whole expect. A failure of any field, type, array element or code discards all the new bindings of this
attempt; the already common bindings do not change. The order of traversing the fields does not change the result.
@any requires the presence of a field; @absent — its absence; ~text — a string occurrence.
JSON types are exact, true is not equal to 1; objects are compared by the given fields recursively,
arrays — by the number, order and values of the elements, except arrays without a normed order (`configured`) — the dictionary of the common acceptance README. An expectation of a single code does not require an empty body.
The full HTTP answer additionally matches the contract of the store (P/01.1) or of units (P/06, chapter 6.1).

The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes
of a unit. The other evidence is Н5 of the norms of the chapter, including the first/last heartbeat, the stand-in and the budget.

## Checks outside TSV after run 25

For unknown server keep the known BOX_ID/instance and the taken name, but do not set the server;
in a separate manifest enable places.server_field and places.lease: strict. Read the heartbeat through the objects door or check
the formation of the object by reading: server is present and equals "", server_unsaid contains the text of
ADR-0029, all places are strict. A separate variant with a known server gives a non-empty server and does not
contain server_unsaid. The substitution of BOX_ID instead of the server does not pass. The ordinary TSV sets srv-a
and does not observe this branch.

## Additional check of the class of errors of run 36 (Kimi)

Sc. 03 does not read the heartbeat object and does not prove its period (Н1.1 of the chapter).

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

SDK tests at the seams are in [seams.tsv](seams.tsv); their adapter contract is [forms/README.md](../../forms/README.md). They supplement the process scenarios and do not change the counts above or replace a reading witness they do not execute.

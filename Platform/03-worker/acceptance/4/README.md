# Acceptance P/03.4 — the heartbeat, writes, the stop, the budget (stand)

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.4-worker.norms.md`](../../spec/03.4-worker.norms.md) N5. The scenario was moved from the acceptance of
M10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the number of the scenario and of the steps are the former ones, except the first step `@start resource` of sc. 03: the controller reads the heartbeat of the worker through the objects door of the resource of its server, without the resource «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Five scenarios / 42 steps: 03-sigterm (9), 13-pulse-counters (9; the VMS request «heartbeat and a garbled row»: the counts of the heartbeat and the rows of `/metrics`, with the resource `srv-a` — the heartbeat is read through its door), 36-previous-heartbeat (12), 37-place-released-on-sigterm (6) (coverage audit of P/03, the second pass of Gemini). Scenario 38-door-per-address has 6 steps.

The scenario runs on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers `testsub` (the training worker of counters), which the steps of the scenario start. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of the section «Stand» of the common acceptance README (reconciliation of python and go M10/3–5, item 24). Observation — rows through the store door P/01.1 and the named heartbeat fields through the resource door. The controller is a neighbour by contract (the data catalogue, `lifecycle.md` of P/04), not the norms of P/04 (the plan of the move of lesson 3, V2): step 8 sees that the placement is removed by the controller with a reason.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `store` (a role with read rights on `testsub/`), `console`, `resource`, `worker <name>` (sc. 38) and `admin` (sc. 37 — the shelf), the directives `@start`, `@sigterm`,
`@sigkill`, `@hold` (sc. 38), `@spoil object` (sc. 36), `@until`; the body of an answer is compared by the mode `body` of the routing row of the target («Expectation» of the dictionary).

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 N1.2) — with full rights on `testsub/` and `testsub2/`.

Each scenario runs on the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand) of the common acceptance README: a fresh stand per scenario, no foreign processes, one box, the stop of `@sigterm` and `@sigkill`, the time of a scenario. What is own to the chapter is in the section «[Stand and steps of the chapter](#stand-and-steps-of-the-chapter)» below.

**Coverage audit of P/03, second pass (Gemini)** (2026-10-30, the report `gemini/audit-coverage` `fad5fa2ba`, the drafts G03, G05;
analysis by the Specification):
- sc. 36 — the fields `previous_*` of the heartbeat (N1.1; chapter 3.2 N3 «start()» step 4): the copy `w-1` is killed by `@sigkill`, its heartbeat remained;
  a new copy of the same box takes the name (`gen` 2) and writes `previous_instance` — the instance of the killed one, `previous_server` — `srv-a`,
  `previous_hb` — a time by the form (`@time`; the step does not compare equality with `ts` of the found heartbeat: the type of the time notation —
  a string or a number — is the writer's choice, P/01.1 N0). Then this copy is killed too, its heartbeat is spoiled by `@spoil object` (the writer is
  stopped — the dictionary): the third copy (`gen` 3) has no fields `previous_*` — the found heartbeat is unreadable, the fields are not written
  (`heartbeats.outcomes.tsv` `<s>worker`);
- sc. 37 — the worker `testsub2` took its own place `sh1` (the shelf — through the door `admin`, as in sc. 23 of the acceptance of chapter 3.2); on `@sigterm`
  the hold row is released (`released: "true"`, `by` as before) and the slot is released (N3 «stop by SIGTERM» step 4; chapter 3.2
  N3 «place» `release` — before the release of the slot; the order of the two writes is the edge `let-go-place` → `release-slot` of the seams
  `s1-stop-order` and `s3-stop-slow-unit` of [chapter 3.1](../1/seams.tsv)).

## Door connection limit

Scenario `38-door-per-address` (6 steps) starts the resource and worker `testsub2 t-1` with its declared `read/play` door; there is no controller or unit. The `worker t-1` door is the `url` of this process heartbeat, not the console door or a stand-in worker. `@hold worker t-1 8` confirms eight accepted sockets of that process group alive together. The next two HTTP requests from the same source address check `503 {"error":"busy"}` and the exact `Retry-After: 1` value.

The [shared `@hold` rules](../../../common/acceptance/command-tables.md#held-connections) apply before and during both requests: loss of a held socket or independent observation gives `stand`, not an implementation mismatch. The 5 s header deadline remains in force; the stand does not extend it. The 32-connection limit is not checked by this scenario: the format has no source-address facility for several addresses, and from one address the limit of 8 acts first. The limit of 32 is checked by reading.

## Stand and steps of the chapter

The boundaries of each scenario are those of the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand), including the
stop of `@sigterm` and `@sigkill`: the step matches only after the whole process group has exited. Own to the chapter:

- the read role of the store has full rights on `testsub/` and `testsub2/` (above); the door `admin` puts the shelf of sc. 37;
- every worker has the box and the server of the stand; the name is passed by the substitution `{name}` of the directive (the common acceptance README, «Stand»; analysis of the review of stage B 3–5, № 33);
- the chosen `CAPACITY`/`WORKER_MEMORY_MB` satisfy N1.2 of the chapter: a decreasing memory budget is not provoked;
- `@start` confirms the start of the process, not its life; the readiness of the slot is checked by the following `@until`.

The comparison is «Expectation» of the [dictionary](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) with the full form by
door. The scenarios observe rows, HTTP answers and the named heartbeat fields through the resource door; sc. 38 also observes accepted worker sockets. They do not observe the actual external writes of a unit.

## SDK seams of the chapter

The cases that need a scripted clock, the order of calls or store replies are rows of [seams.tsv](seams.tsv) and of the seams of
[chapter 3.1](../1/seams.tsv) through the ports of [forms/README.md](../../forms/README.md#seams) (the judge runs them by the seam adapter protocol of the common acceptance README):

| Subject | Seams |
|---|---|
| the order of the stop by SIGTERM: the units, the closing of the place writers, the last heartbeat, the place let go before the slot is given away (sc. 37 sees only both writes); a crash writes nothing | `s1-stop-order`, `s2-crash-no-hooks` of chapter 3.1 |
| the stop term (P/03.4-18): a slow `stop_unit` under the scripted clock, the write that gives away the slot is sent no later than `WRITE_WINDOW` after the send moment of the last confirmed request | `s3-stop-slow-unit`, `s4-stop-two-slow-units` of chapter 3.1 |
| the stand-in at the neighbours of STALL and FOR, its strict place, no revival of a fenced holder | `s1`, `s2`, `s7`–`s13` |
| the memory budget and the base heartbeat | `s3`–`s6` |
| the cadence of the heartbeat (at most ⌊seconds / HEARTBEAT_EVERY⌋ + 1 writes) and no writes of a nobody | `s14-lease-run-live`, `s15-lease-run-nobody` |
| a repeat of a write under the slot after `ambiguous` and after `unavailable` with the same id (P/03.4-07) | `s16-slot-write-ambiguous-replay`, `s17-slot-write-unavailable-replay` |

SDK seams s8–s13 use the existing worker-stand-in at neighbours of STALL and FOR. At age <= STALL there are no stand-in effects; at STALL < age <= FOR they observe slot renewal before confirmation and repeated heartbeat, without watchdog or epoch issue. Beyond FOR this substitution stops and the existing done applies. s13 does not forbid ordinary completion cleanup writes: it observes no renewal-confirmation sequence, epoch issue or watchdog, without a new done port.

## Not judged in this lesson

- The contents of the heartbeat of sc. 03 and its first write before the first pass: sc. 03 does not read the heartbeat object; the cadence is
  the seam `s14-lease-run-live`, the last heartbeat after the units are stopped — the seam `s1-stop-order`, its `status: []` — steps 05/14–15 of
  [the acceptance of chapter 3.6](../6/README.md); the first heartbeat before the first pass is checked by reading N1.1 `cadence`.
- The admission of the server before the presence lock: as in [the acceptance of chapter 3.2](../2/README.md#not-judged-in-this-lesson).
- A stop call that never returns: the process is ended by the unit manager at `worker.stop_timeout` (P/02.4 N1.1), the stage of the system;
  the value of `worker.stop_timeout` is «Implementation decides» item 3 of the norms.

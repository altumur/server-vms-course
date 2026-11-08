# Acceptance P/06.6 — control doors

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.6-console.norms.md`](../../spec/06.6-console.norms.md) N5. The scenarios were moved from the acceptances of
M10/04 (01–07),
M10/10 (01 → 08, 02 → 10, 09, 12) and
M10/11 (03 → 11) (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers and the steps are the former ones, except the coinciding numbers: `08-schema` (in M10/10 — `01-schema`; the number 01
is taken by `01-unplaced` from M10/04), `10-drain-strand` (in M10/10 — `02-drain-strand`; 02 is taken by `02-unplaceable`),
`11-schema-processes` (in M10/11 — `03-schema-processes`; 03 is taken by `03-policy`). 17 scenarios / 195 steps (sc. 17 — versions of the settings snapshots, ADR-0094 B4; sc. 13–16 — the second pass of the coverage audit of P/06, Gemini; sc. 01, 08, 10, 12 — the first step `@start resource` by C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29; sc. 09 — the first step `@start resource`: the console and the controller read the heartbeat of the worker through the objects door of the resource of their own server, without the resource «unknown», [the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27; the steps 04/14 and 05/6 — the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7; the step 05/5 — analysis of the review of stage B 6–7, № 40; sc. 12: steps 9–10,
13–14, 17–18 were added — analysis of the review of stage B 6–7, № 21).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors):
the doors `console`, `console2`, `resource`, `store`; the directives `@start controller`, `@start resource`, `@as`, `@put object`,
`@spoil object`, `@until`, `@sleep` (sc. 13), `@big(N)`; the expectation is an exact code or `2xx`/`4xx` and a subset of fields. A request without a door
prefix (sc. 01–07, the former acceptance of M10/04) goes to the console `testsub` — the door of the lesson P/06; `Idempotency-Key` — per the dictionary,
a repeat of a transport attempt — the same key and body.

Full answers are additionally checked by [the contract of the lesson](../../spec/06-console.api.openapi.yaml): the mandatory fields,
their types and the absence of extra fields; for `POST /counters` — by chapter 6.1. `2xx` does not widen the normative list of codes:
the drain operations by N2 return 200. The success of the deletion of labels/decommission `{}` is not equal to the absence of a body. For the codes without a body in
the table the form of the full answer of N2 is checked all the same.

## Sc. 01–07: one instance without workers

The scenarios are executed sequentially on one instance: 02 uses u1 from 01, 07 — u1 from 01. The state is not
reset between them.

A separate store and a new console without a domain, access only from the loopback by chapter 6.3 N1.3 `open` (there are no keys — only from the
loopback, the name operator). The current testsub from the common testdata is loaded: unit.id = name, rows = counters,
placement.servers has the effective default shared (the key is not set in testsub). Its controller works, and the resource `srv-a` — by the first step of sc. 01 (`@start resource`: the console reads the heartbeats through the objects door
of the resource of its own server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29); there are no workers, ordered processes and background
writers. The servers srv-b, srv-nobody are unknown.
The creation of a drain does not declare a server known for the operations labels/decommission.

«Empty» refers to the application rows and objects, placements, assignments, slots, policy,
platform/servers, platform/doors, platform/drain, the requests and notes of decommission,
the POST replay claims and the id memory of the store. The manifest, its mark and the necessary configuration data
are installed by the preparation and are not removed by the word «empty». A new run/a parallel run gets
its own state, without shared directories and ports.

Between 01 and 02 the controller must complete at least one pass after the creation of u1.
The confirmation is a change of the report controller/pass, observed by the report printing command from the section «Stand»
of the common acceptance README; it does not require adding a new HTTP door. The waiting limit is 15 s. The expiry of the deadline is a refusal of the preparation,
not a permission to continue. GET /counters without a placement does not prove the completion of a pass:
with an empty pool the placement row may not appear at all.

For these branches use the evidence table of N5. The success of the schema does not prove the rights,
the change of state, the deadline or the execution of a request by the controller.

## Sc. 08–16: a fresh stand per scenario

The doors of the console `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the controller and the resource
`srv-a` by directives (`@start controller`, `@start resource`), the store (`store …`); without workers and a domain. A build with
schema 1 (sc. 08 waits for `understood: 1`, sc. 11 — `understood: 1`, `can_raise_to: 1`); the body limit of the console is 1 MiB.

The start interface is the section «Stand» of the common acceptance README, without commands of the chapter's own: `@start controller` and
`@start resource` are the role commands of the controller `testsub` and of the resource of the server `srv-a` (the substitutions `{data}`, `{socket}`,
`{manifest}`, at the resource `{rport}`); the resource is ready when it listens on `{rport}` and there is the row `platform/doors/srv-a`.
`console …` and `console2 …` are one console on `{port}`, the second is the prefix `/testsub2`. `store …` without `@as` is the store door
`admin.sock` (`{socket}` — the door with full rights, [the common acceptance README](../../../common/acceptance/README.md) «Role sockets»):
step 14 of sc. 04 and step 10 of sc. 05 read `platform/drain` and `platform/servers/srv-a` outside the subsystem prefix; `@as <role>` — the role socket until the end of the scenario.

Before each scenario stop the processes of the previous one, create separate empty row/object stores and clear
the variables/replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2;
there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The store is fresh and empty — there is no row
platform/schema, the runner does not write it (reading of the commits «cammeta-acceptance» 2026-10-20). For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for
the replays of the same step.

By reading: the query version is only ASCII [1-9][0-9]* whole; reconcile all the reasons of 409 of the schema raise (N3 «raise_schema»,
N4).

## Coverage audit of P/06, second pass (Gemini)

Sc. 13–16 (`audit-coverage-gemini` 0a5ae79f9) — the stand of sc. 08–12: fresh per scenario, the resource `srv-a` by the first step, without
the controller and workers. Rows bypassing the writer — through the store door by the role of the owner: the slot — `testsubworker` (as in sc. 07, 09),
the rows of the console (`testsub/policy`, `platform/drain`, `platform/schema`, `platform/servers/srv-a`) — `console`.

## Inputs `inputs/`

The heartbeats of the worker `w-1` for `@put object` (the object write command of the «Stand», bypassing the writer): `hb-w-1-no-status.json` (sc. 07,
09; from the acceptances of M10/04 and M10/10 — the bytes coincide), `hb-w-1-pending-0.json`, `hb-w-1-pending-missing.json`,
`hb-w-1-pending-fraction.json`, `hb-w-1-pending-minus-zero.json`, `hb-w-1-pending-2p63.json`, `hb-w-1-schema-fraction.json`,
`hb-w-1-build-number.json` (sc. 12; from the acceptance of M10/10, the registry row e31e5c28).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

One sleep: sc. 13 step 7, 46 s — time before an action: the version of the slot `srv-b` does not change for longer than LOST_AFTER 45 s ([the observation contract](../../../common/contracts/observation.md) «Freshness»), only then the server is not «heard» and `may_confirm_gone` can be `true` (N3 «decommission_server»). Waiting for an event is `@until`: sc. 02 step 2 (the reason in `/unplaceable` after a pass), 07 steps 4–5, 09 step 6
(the assignment by a pass of the controller), 10 step 8 (the journal in the index of the resource), 11 step 3 (the heartbeat of the resource in `processes`), 12
steps 4, 5 and the odd 7–25 (the console sees the new heartbeat; the even 6–24 — `@put object`; analysis of the review of stage B 6–7, № 21, № 22), 13 steps 2, 15, 16 (a live resource, the decommission journal in the index of the resource), 16 step 3 (`/servers` by the labels row).

## Scenario boundaries

Sc. 01–07 — one instance, the state is not reset between them. Before sc. 08–16 the runner stops the processes,
resets the store (rows and objects) and the variables. After the last step wait for the stop of all the created processes,
then delete the state.

## Sc. 17: versions of the settings snapshots (ADR-0094 B4)

A fresh stand, the resource `srv-a` by the first step; there are no rows `testsub/policy`, `platform/drain`, `platform/servers/srv-a`, `platform/schema` before the scenario. Step 25 waits until the server becomes known, hence `@until`.

The intended `revision` and the continuation of an intercepted claim — by reading: one console without controlled breaks does not create these branches.

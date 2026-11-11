# Acceptance P/06.6 — control doors

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.6-console.norms.md`](../../spec/06.6-console.norms.md) N5. 17 scenarios / 195 steps.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors):
the doors `console`, `console2`, `resource`, `store`; the directives `@start controller`, `@start resource`, `@as`, `@put object`,
`@spoil object`, `@until`, `@sleep`, `@big(N)`; the expectation is an exact code or `2xx`/`4xx` and a subset of fields. A request without a door
prefix goes to the console `testsub` — the door of the lesson P/06; `Idempotency-Key` — per the dictionary,
a repeat of a transport attempt — the same key and body.

Full answers are additionally checked by [the contract of the lesson](../../spec/06-console.api.openapi.yaml): the mandatory fields,
their types and the absence of extra fields; for `POST /counters` — by chapter 6.1. `2xx` does not widen the normative list of codes:
the drain operations by N2 return 200. The success of the deletion of labels/decommission `{}` is not equal to the absence of a body. For the codes without a body in
the table the form of the full answer of N2 is checked all the same.

## One instance without workers

Selected scenarios are executed sequentially on one instance. The state is not
reset between them.

A separate store and a new console without a domain, access only from the loopback by chapter 6.3 N1.3 `open` (there are no keys — only from the
loopback, the name operator). The current testsub from the common testdata is loaded: unit.id = name, rows = counters,
placement.servers has the effective default shared (the key is not set in testsub). Its controller works, and the resource `srv-a` — by a first step (`@start resource`: the console reads the heartbeats through the objects door
of the resource of its own server); there are no workers, ordered processes and background
writers. The servers srv-b, srv-nobody are unknown.
The creation of a drain does not declare a server known for the operations labels/decommission.

«Empty» refers to the application rows and objects, placements, assignments, slots, policy,
platform/servers, platform/doors, platform/drain, the requests and notes of decommission,
the POST replay claims and the id memory of the store. The manifest, its mark and the necessary configuration data
are installed by the preparation and are not removed by the word «empty». A new run/a parallel run gets
its own state, without shared directories and ports.

Between selected scenarios the controller must complete at least one pass.
The confirmation is a change of the report controller/pass, observed by the report printing command from the section «Stand»
of the common acceptance README; it does not require adding a new HTTP door. The waiting limit is 15 s. The expiry of the deadline is a refusal of the preparation,
not a permission to continue. GET /counters without a placement does not prove the completion of a pass:
with an empty pool the placement row may not appear at all.

For these branches use the evidence table of N5. The success of the schema does not prove the rights,
the change of state, the deadline or the execution of a request by the controller.

## A fresh stand per scenario

The doors of the console `testsub` (root) and `testsub2` (mounted, `console2 …` — its doors `/testsub2/…`), the controller and the resource
`srv-a` by directives (`@start controller`, `@start resource`), the store (`store …`); without workers and a domain. A build with
schema 1; the body limit of the console is 1 MiB.

The start interface is the section «Stand» of the common acceptance README, without commands of the chapter's own: `@start controller` and
`@start resource` are the role commands of the controller `testsub` and of the resource of the server `srv-a` (the substitutions `{data}`, `{socket}`,
`{manifest}`, at the resource `{rport}`); the resource is ready when it listens on `{rport}` and there is the row `platform/doors/srv-a`.
`console …` and `console2 …` are one console on `{port}`, the second is the prefix `/testsub2`. `store …` without `@as` is the store door
`admin.sock` (`{socket}` — the door with full rights, [the common acceptance README](../../../common/acceptance/README.md) «Role sockets»):
it reads `platform/drain` and `platform/servers/srv-a` outside the subsystem prefix; `@as <role>` — the role socket until the end of the scenario.

Before each scenario stop the processes of the previous one, create separate empty row/object stores and clear
the variables/replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2;
there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The store is fresh and empty — there is no row
platform/schema, the runner does not write it. For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for
the replays of the same step.

By reading: the query version is only ASCII [1-9][0-9]* whole; reconcile all the reasons of 409 of the schema raise (N3 «raise_schema»,
N4).

## Inputs `inputs/`

The heartbeats of the worker `w-1` for `@put object` (the object write command of the «Stand», bypassing the writer) lie in `inputs/`.

## Scenario boundaries

Selected scenarios share one instance, the state is not reset between them. Before the others the runner stops the processes,
resets the store (rows and objects) and the variables. After the last step wait for the stop of all the created processes,
then delete the state.

## Versions of the settings snapshots

A fresh stand, the resource `srv-a` by the first step; there are no rows `testsub/policy`, `platform/drain`, `platform/servers/srv-a`, `platform/schema` before the scenario.

The intended `revision` and the continuation of an intercepted claim — by reading: one console without controlled breaks does not create these branches.

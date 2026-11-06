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

Sc. 07 — the units of a drain. There is no worker, it is forged: step 1 writes the slot row `w-1` by the role `testsubworker` (`@as`),
step 2 puts the heartbeat `inputs/hb-w-1-no-status.json` with `status: []` (`@put object`). The controller assigns `d1` and `u1` to
`w-1`. The drain of `srv-a` counts the units by the assignment ∪ `status[].id`: `units: 2`, `safe: false`, although `status` is empty
(N2.2, reconciliation of python and go M10/3–5, P8).

Sc. 01 — an unplaced unit and 404 where; 02 — its presence in unplaceable; 03 — the policy;
04 — one active drain; 05 — a refusal of the form of labels earlier than the check of the server, and an unknown server;
06 — an unknown server at decommission; 04, steps 11–13 — a server name not by the grammar of N2.1 — 400. They do not check the choice in a live pool, races, safe with pending_writes,
the decommission of a live/never heard resource, the issue of door, the forecast of a change of labels. A successful change of labels — only in the replay memory (sc. 05 steps 7–13).
The replay memory of the write doors (N2.1) — sc. 03 steps 8–12, 04 steps 15–22, 05 steps 7–13, 08 steps 7–9, 13 steps 17–20.
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

Reconciliation of python and go M10/6–11 (sc. 08–12 and the added steps):
- Sc. 08 step 6 — a schema version without an upper bound of the form: greater than its own SCHEMA — 409, not 400.
- Sc. 10 steps 8–10 — the drain journal through `/events` of the console (the resource — from step 1, C06-PULSE-LAPSE-503-03): `drain.started`, `drain.ended`,
  there is no other kind (`drain.cleared`) (T22).
- Sc. 09 — a drain with an unreadable heartbeat (T2): the slot `w-1` by the role `testsubworker`, the heartbeat — by the same input as sc. 07,
  `inputs/hb-w-1-no-status.json`, then `@spoil object`; the worker of the server — by the slot.
- Sc. 12 — the number forms of the heartbeat of the worker `w-1` without a live worker: the slot row and the heartbeats `@put object` from `inputs/`
  (`hb-w-1-pending-0.json` — the reference: `safe: true`; `-pending-missing`, `-pending-fraction` (`1000.0`), `-pending-minus-zero`,
  `-pending-2p63` — `pending_unsaid`; `-schema-fraction` (`1.0`) — `schema: null`; `-build-number` (`5`) — `build: null`, not known, P1; V7 item 3 row 14).
  Each `@put object` changes the version of the heartbeat — the console sees it alive (N1.2: a stale heartbeat would also give
  `pending_unsaid`, so steps 4 and 21 are the reference of freshness; freshness — [the observation contract](../../../common/contracts/observation.md))
  (reconciliation of python and go M10/6–11, T1, T3, T4, T27). Before each input not by the form, except the first one, — again
  `-pending-0` and `@until` until `safe: true` (steps 8–9, 12–13, 16–17): otherwise the expectation `pending_unsaid` of the next input
  would coincide with the earlier state, and a console that sees a new heartbeat with a delay would pass the step by the old heartbeat
  (analysis of the review of stage B 6–7, № 21).

Sc. 10 after DELETE removes only the drain: d1 remains unplaced, would_strand.testsub=[d1], the counters 0 and safe=true;
the full answer keeps the same keys would_strand/subsystems by N2.2. Sc. 11 (`/schema` after an update) is
evidence and P/02.4-08: the resource is under the key `resource/srv-a` (N2.3).

By reading: the query version is only ASCII [1-9][0-9]* whole; reconcile all the reasons of 409 of the schema raise (N3 «raise_schema»,
N4).

## Coverage audit of P/06, second pass (Gemini)

Sc. 13–16 (`audit-coverage-gemini` 0a5ae79f9) — the stand of sc. 08–12: fresh per scenario, the resource `srv-a` by the first step, without
the controller and workers. Rows bypassing the writer — through the store door by the role of the owner: the slot — `testsubworker` (as in sc. 07, 09),
the rows of the console (`testsub/policy`, `platform/drain`, `platform/schema`, `platform/servers/srv-a`) — `console`.
- Sc. 13 — the decommission of a server, the console side (N3 «decommission_server»). A live `srv-a` (step 2 waits for `resource: live`): 409 `server
  answers`, `may_confirm_gone: false`, `gone: true` does not bypass it. `srv-b` is known only by the slot row `w-1` (step 5; the resource
  `srv-b` was never heard): while the slot is fresh — 409 `may_confirm_gone: false` also with `gone` (step 6 — the first observation of the version of
  the slot by this console); `@sleep 46` — the version of the slot does not change for longer than LOST_AFTER 45 s, there is no fresh evidence: without `gone`
  — 409 `may_confirm_gone: true`, with `gone` — 202 `{warning}`, the row `platform/decommission/srv-b` `{by, at, why, gone}`;
  a repeat — 202, the row is not rewritten (`at`, `why` of the first), there is no journal — `server.decommission_requested` exactly once;
  the withdrawal — 200 `{}`, there is no row, `server.decommission_withdrawn`. The execution by the controller and the removal of the door row — by reading.
- Sc. 14 — the row `testsub/policy` not by the form (`servers: bogus`) after `distinct`: `GET /policy` — the default of the manifest
  `shared`, not a refusal and not the earlier value (the outcome `console` of the family `policy`); the row `platform/drain` not by the form (`server:
  bad/srv`) — `GET /drain` 503 `unavailable` (the outcome of the family `drain`, N4).
- Sc. 15 — `platform/schema` with `version: "x"` at a working console: `GET /schema` — `version: null`, `schema_unknown: true`;
  `PUT /schema?version=1` — 409 «mend the row first» (N3 «raise_schema» step 2), the row is the earlier one. A refusal of the start of the console with
  such a row — by reading (as before).
- Sc. 16 — `platform/servers/srv-a` with a label not by the alphabet (`bad label`): `/servers` — `labels: null`, `labels_source: null`;
  the series `testsub_servers_labels_unread 1` (the acceptance README of chapter 6.5 «Rows»; the outcome of the family `server-labels`).

## Inputs `inputs/`

The heartbeats of the worker `w-1` for `@put object` (the object write command of the «Stand», bypassing the writer): `hb-w-1-no-status.json` (sc. 07,
09; from the acceptances of M10/04 and M10/10 — the bytes coincide), `hb-w-1-pending-0.json`, `hb-w-1-pending-missing.json`,
`hb-w-1-pending-fraction.json`, `hb-w-1-pending-minus-zero.json`, `hb-w-1-pending-2p63.json`, `hb-w-1-schema-fraction.json`,
`hb-w-1-build-number.json` (sc. 12; from the acceptance of M10/10, the registry row e31e5c28).

## Separate checks of full answers

- `POST /drain` with server=srv-a: the full answer `{draining: "srv-a"}`; `DELETE`: `{draining: ""}`.
  The opposite bodies do not pass the schema even with a correct following GET.
- The full answers of labels and drain are checked by the whole grammar of a subsystem name
  [P/02.1 N1.2](../../../02-installer/spec/02.1-installer.norms.md#n12-document),
  including the whole closed list of reserved names. For each word check the refusal
  in the prefix of UnitRef (would_move and will_move), in the key of each of the maps would_strand/subsystems
  and in the field subsystem; for example, platform/u1, domain/u1, events/u1 and the key events are inadmissible.
  Close admissible names are platformx and events2 (the references platformx/u1 and events2/u1).
  Additional negative cases of a name: bad/name, a capital first letter, 33 characters
  and a final line feed. Positive ones: testsub and a name of length 32. This is a check of the schemas
  of answers, not a requirement to load a forbidden subsystem or to get such an answer from a process.
  The existence and visibility of subsystems, the coincidence of the keys of the maps and of the field subsystem are checked
  separately, one grammar does not prove this.
- In both GET answers of drain the field `draining` is checked as a server name of one segment
  or `""`: `a/b` and a backslash are rejected by the schema, `box-a` and an empty string are admissible.
  This does not change POST (only a non-empty name) and DELETE (only an empty string).
- Where.worker, a non-null Where.directory and each element of SubsystemDrain.pending_unsaid have the form of a slot name
  [P/03.2 N1.4](../../../03-worker/spec/03.2-worker.norms.md).
  Admissible are `w-1`, `w-server-12`, a prefix of eight letters and a long admissible suffix;
  not admitted are `""`, `w`, `w-`, `w--1`, `W-1`, `w/1`, `w_1` and a final line feed.
  The schema checks the common grammar; the correspondence to slot.prefix of a particular manifest is checked
  separately. directory:null and an empty pending_unsaid are admissible; an empty name of directory or of an array element is not.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models
of the author are not a performed stand test.

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

- Steps 2–15 — the policy: no row — `revision: 0`, a condition — 412 without `row`; a creation without a condition; a condition by `revision` and by the index; 412 with `row`; step 10 — the index of the row is read by the store door: the body of `GET /policy` carries `revision`, the index is `ETag`, and an expectation of a header `$name` does not bind; steps 13–14 — the replay memory earlier than the condition.
- Steps 16–24 — the drain: `POST` of the same server and `DELETE` without a drain do not move `revision` (steps 19–20, 23–24).
- Steps 25–30 — the labels: a removed row counts anew.
- Steps 31–36 — the schema: `PUT` of the same version is a write, `revision` grows.

The intended `revision` and the continuation of an intercepted claim — by reading: one console without controlled breaks does not create these branches.

## Accepted ADR-0127 review: symmetric drain sources

Use the ordinary GET /drain door with one active server and one schema-valid worker. Stop the placement writer after establishing the fixture so it cannot silently repopulate the controlled assignment. Use the existing authorized store writer with CAS for the assignment and the ordinary resource object path for a fresh valid heartbeat, pending_writes0; all other required sources are confirmed. In separate prepared cases, assignment[] with status[id=u1] gives units1/safe=false; assignment[u1] with status[] gives units1/safe=false; assignment[u1] with status[id=u1] gives units1, not2. No other worker or unplaced unit may distort these counts. The completely empty positive neighbor has no live unit rows, an empty assignment and status, confirmed sources and pending0: units0/safe=true. Unknown assignment/heartbeat uses the existing unavailable/lapse/unsaid rule and must not turn into that empty neighbor.

Record the actual source versions, heartbeat bytes and HTTP body, including deduplication. This is a required real-HTTP/source probe, not a new CALL port, native command or proof supplied by this document. safe remains an observation and does not cancel the operator stop window.

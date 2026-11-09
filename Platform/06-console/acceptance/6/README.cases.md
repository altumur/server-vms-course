# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/6/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

The norm of the chapter is [`06.6-console.norms.md`](../../spec/06.6-console.norms.md) N5. The scenarios were moved from the acceptances of
M10/04 (01–07),
M10/10 (01 → 08, 02 → 10, 09, 12) and
M10/11 (03 → 11) (stage B, ADR-0083 addendum (1): without
a change of behaviour); the numbers and the steps are the former ones, except the coinciding numbers: `08-schema` (in M10/10 — `01-schema`; the number 01
is taken by `01-unplaced` from M10/04), `10-drain-strand` (in M10/10 — `02-drain-strand`; 02 is taken by `02-unplaceable`),
`11-schema-processes` (in M10/11 — `03-schema-processes`; 03 is taken by `03-policy`). 17 scenarios / 195 steps (sc. 17 — versions of the settings snapshots, ADR-0094 B4; sc. 13–16 — the second pass of the coverage audit of P/06, Gemini; sc. 01, 08, 10, 12 — the first step `@start resource` by C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29; sc. 09 — the first step `@start resource`: the console and the controller read the heartbeat of the worker through the objects door of the resource of their own server, without the resource «unknown», [the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27; the steps 04/14 and 05/6 — the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7; the step 05/5 — analysis of the review of stage B 6–7, № 40; sc. 12: steps 9–10,
13–14, 17–18 were added — analysis of the review of stage B 6–7, № 21).

<!-- original-mixed-case-paragraph -->

`@spoil object`, `@until`, `@sleep` (sc. 13), `@big(N)`; the expectation is an exact code or `2xx`/`4xx` and a subset of fields. A request without a door
prefix (sc. 01–07, the former acceptance of M10/04) goes to the console `testsub` — the door of the lesson P/06; `Idempotency-Key` — per the dictionary,

<!-- original-mixed-case-paragraph -->

## Sc. 01–07: one instance without workers

<!-- original-mixed-case-paragraph -->

The scenarios are executed sequentially on one instance: 02 uses u1 from 01, 07 — u1 from 01. The state is not

<!-- original-mixed-case-paragraph -->

placement.servers has the effective default shared (the key is not set in testsub). Its controller works, and the resource `srv-a` — by the first step of sc. 01 (`@start resource`: the console reads the heartbeats through the objects door

<!-- original-mixed-case-paragraph -->

Between 01 and 02 the controller must complete at least one pass after the creation of u1.

<!-- original-mixed-case-paragraph -->

## Sc. 08–16: a fresh stand per scenario

<!-- original-mixed-case-paragraph -->

schema 1 (sc. 08 waits for `understood: 1`, sc. 11 — `understood: 1`, `can_raise_to: 1`); the body limit of the console is 1 MiB.

<!-- original-mixed-case-paragraph -->

step 14 of sc. 04 and step 10 of sc. 05 read `platform/drain` and `platform/servers/srv-a` outside the subsystem prefix; `@as <role>` — the role socket until the end of the scenario.

<!-- original-mixed-case-paragraph -->

## Coverage audit of P/06, second pass (Gemini)

Sc. 13–16 (`audit-coverage-gemini` 0a5ae79f9) — the stand of sc. 08–12: fresh per scenario, the resource `srv-a` by the first step, without
the controller and workers. Rows bypassing the writer — through the store door by the role of the owner: the slot — `testsubworker` (as in sc. 07, 09),
the rows of the console (`testsub/policy`, `platform/drain`, `platform/schema`, `platform/servers/srv-a`) — `console`.


<!-- original-mixed-case-paragraph -->

The heartbeats of the worker `w-1` for `@put object` (the object write command of the «Stand», bypassing the writer): `hb-w-1-no-status.json` (sc. 07,
09; from the acceptances of M10/04 and M10/10 — the bytes coincide), `hb-w-1-pending-0.json`, `hb-w-1-pending-missing.json`,
`hb-w-1-pending-fraction.json`, `hb-w-1-pending-minus-zero.json`, `hb-w-1-pending-2p63.json`, `hb-w-1-schema-fraction.json`,
`hb-w-1-build-number.json` (sc. 12; from the acceptance of M10/10, the registry row e31e5c28).

<!-- original-mixed-case-paragraph -->

Sc. 01–07 — one instance, the state is not reset between them. Before sc. 08–16 the runner stops the processes,

<!-- original-mixed-case-paragraph -->

## Sc. 17: versions of the settings snapshots (ADR-0094 B4)

<!-- original-mixed-case-paragraph -->

A fresh stand, the resource `srv-a` by the first step; there are no rows `testsub/policy`, `platform/drain`, `platform/servers/srv-a`, `platform/schema` before the scenario. Step 25 waits until the server becomes known, hence `@until`.

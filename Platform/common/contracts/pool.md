# The pool contract: a live worker, the pool, the keeper of a place, server eligibility

This English text is the source; the Russian translation `ru/contracts/pool.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13), addendum (30): a common algorithm of several processes is a contract, not
copies in chapters; guess of stage C C06-SERVER-POLICY-33-01, the Architect's decision of 2026-10-25). The owner is lesson
[P/04](../../04-controller/spec/04-controller.norms.md) (N3 «choose»: the controller places units only on the workers of the pool).
The participant is the cluster console ([P/06.5](../../06-console/spec/06.5-console.norms.md) N2: `WorkerRow.idle_by_policy`,
`ServerRow.placeable`, `why`): the same computation by its own reads and its own clock.

Moved from P/04 N3 «choose» (the lines «live worker», «pool», «keeper») without a change of the controller's behaviour; for the view
of the console, about which P/04 was silent, — four answers of the Architect of 2026-10-25 (the sections below, marked). What a unit requires
beyond the pool (`constraint`, `spread_by`, `affinity`, the group, the home, capacity and order) — still P/04 N3 «choose», the line
«eligible» and below.

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

The rows and objects that the pool computation reads follow the forms and outcomes of their families (layout audit, V-42–V-44, B-07; the Architect's decision of 2026-10-25): the heartbeat `<sub>/heartbeats/<name>`
— `Platform/03-worker/data/heartbeats.schema.json`, `Platform/03-worker/data/heartbeats.outcomes.tsv`; the slot `<sub>/slots/<name>` —
`Platform/03-worker/data/slots.schema.json`, `Platform/03-worker/data/slots.outcomes.tsv`; the assignment `<sub>/workers/<name>` —
`Platform/04-controller/data/workers.schema.json`, `Platform/04-controller/data/workers.outcomes.tsv`; the order row
`<sub>/want/<host>` — `Platform/04-controller/data/want.schema.json`, `Platform/04-controller/data/want.outcomes.tsv`; the decision
`<sub>/controller/placement_intent` — `Platform/04-controller/data/placement-intent.schema.json`,
`Platform/04-controller/data/placement-intent.outcomes.tsv`; the decommission `<sub>/decommissioned/<host>` —
`Platform/04-controller/data/decommissioned.schema.json`, `Platform/04-controller/data/decommissioned.outcomes.tsv`; the drain
`platform/drain` — `Platform/06-console/data/drain.schema.json`, `Platform/06-console/data/drain.outcomes.tsv`; the decommission request
`platform/decommission/<host>` — `Platform/06-console/data/decommission.schema.json`,
`Platform/06-console/data/decommission.outcomes.tsv`.

## Live worker

```yaml
live:      the heartbeat <sub>/heartbeats/<name> is readable and changed within the last LOST_AFTER by the reader's clock (the observation contract
           «Freshness»; the boundary — the vector fresh-age) ∧ the slot row <sub>/slots/<name> is readable, released = false (not given away and not in
           the capture taking — slots.schema.json), holder is non-empty; a heartbeat whose worker ≠ the name in the key (heartbeats.schema.json) is not read —
           there is no worker
```

## Pool

```yaml
pool:      the live workers
           − the released slots
           − the workers of the draining server (platform/drain, drain.schema.json) and of the decommissioned servers (the observation contract «Server decommissioned»: a readable row platform/decommission/<s> or
             <sub>/decommissioned/<s>; an unreadable one is not a fact, do not subtract, like the rule want_rule; the Architect's answer of 2026-10-25)
           − with requires: resource — the workers of a server whose resource is silent (resource_state of the observation contract; unknown is not
             a fact, the worker passes)
           − retiring of the order rows <sub>/want/<host> (the field retiring, want.schema.json; ADR-0084)
           − the role processes with a number greater than want of their server (the name and the number — the slot name contract
             «Role process name and its number»; ADR-0084 addendum (4) R28)
           − the workers with an unreadable assignment row <sub>/workers/<name> (P/04 N4 «a heartbeat/slot/assignment does not read»;
             at the console — the same, answer (3))
           − with servers: distinct — all except the keeper of their place (the section below)
want_rule: retiring and «number above want» apply only with grows: true and only to the processes of a server whose order row
           <sub>/want/<host> is readable: grows: false — they do not apply; there is no order row of the server — they do not apply to its
           processes; the row is unreadable — they do not apply (the server script does not stop by it — P/02.4 N1.5; the controller —
           an error of step 9, P/04 N4); retiring — only from a readable row (POOL-WANT-33-01, the Architect's decision of 2026-10-25)
```

## Keeper of a place with `distinct`

```yaml
place:     the place of a worker — by place_by of the manifest (default server): the server or a heartbeat field; the value "" from the heartbeat — there is no place
           (as with spread_by), there is no common place "" (ADR-0084 addendum (2) R15; moved from P/04 N1.3 place_by — layout audit, the Architect's decision of 2026-10-25, B-07)
keeper:    every non-empty place has one keeper among the workers of the pool before the subtraction of distinct: the greatest load, on
           equality — the first in slot order (the slot name contract); a worker without a place is not a keeper
load:      the load — one definition with «free» of P/04 N3: the sum of the weights of the unique ids assigned to the worker (the row
           <sub>/workers/<name>) or directed to it by the effective decision (the reserve of the active intent — the observation contract «Reading the decision»; B-07); there is no
           assignment row — the load is 0; not the number of units (answer (2))
weight:    the weight of an id — the field placement.weight.field of its unit row, an integer ≥ 1 (P/04 N1.3); no field — weight.default; for
           a manifest without placement.weight — 1; there is no unit row, it is unreadable or the field is not an integer ≥ 1 — 0 (C06-POOL-FACTS-33-01,
           the Architect's decision of 2026-10-25)
count:     the count — the number of all assigned ids (with the intent reserve), whether their rows are readable or not
capacity:  the capacity — the heartbeat field placement.capacity.from (default capacity); no field — capacity.default (mandatory); the field
           is there but not a number (a word, a boolean) — the worker accepts no new units until the heartbeat is fixed, those already assigned are not
           removed, the reason is in the pass report, the field fates.<worker>.why: «capacity is not a number» (like the weight, R25);
           unit_mb/base_mb — the memory budget of the worker at start (P/03.4) (moved from P/04 N1.3 capacity; layout audit, the Architect's decision of 2026-10-25, A-12)
```

Load and its active-intent reserve are exact nonnegative integer weight aggregates, not record counts. Sum and compare them without binary64/int64 narrowing, rounding or saturation, including keeper selection and the load subtracted for free capacity. Their JSON output uses integer notation without a common.uint53 ceiling. Individual weights, capacity and other counts keep their existing forms; serialized-object limits do not change (P/04-R007, R050).

## `idle_by_policy` (answer (1))

```yaml
idle_by_policy: true — with servers: distinct, a live worker of the pool before the subtraction of distinct that is not the keeper of its place,
           and a live worker without a place (""); otherwise false — also for a worker that is not live, and always with shared
```

## Server eligibility: `placeable`, `why` (answer (4))

```yaml
placeable: true — the server has a live worker of the pool (the pool already subtracts requires: resource when silent, the drain and the decommission
           of the server, the released slots, retiring, the number above want, distinct); labels are a property of a unit and do not enter placeable;
           capacity does not enter
why:       with placeable: false — «no eligible live worker»; with true — there is no field
```

## Vectors

The package [`pool`](../vectors/pool/README.md): the input — heartbeats (who is live), slots, assignments, unit rows, servers (drain,
decommission, order), resources, the manifest; the output — the pool, the keepers, `idle_by_policy`, `placeable`/`why`, the load and the count. The liveness of a heartbeat by history is the package
[`fresh-age`](../vectors/fresh-age/README.md) and [`resource-state`](../vectors/resource-state/README.md); `constraint`,
`spread_by`, `affinity`, the order of choice — P/04, the scenarios and reading. A participant: the package [`slot-name`](../vectors/slot-name/README.md)
— the package of the common contract slot-name, executed by common; this contract is a participant there (slot order —
the keeper on equal load; V-44; CM-RECORD-VECTORS-128, the Architect's decision of 2026-10-25).

The cell `input` of `cases.tsv` is one JSON object (the reads are replaced by the input). `manifest` is `{prefix, servers, place_by?, requires, grows?, weight?: {field, default}, capacity?: {from, default}}`: `prefix` is the `slot.prefix` of the manifest (by it the slot order and the parsing of the name of the role process `<prefix>-<server>-<n>`), `servers` is `shared` or `distinct`, `place_by` is `server` or a heartbeat field, `requires` is `none` or `resource`, `grows` is a boolean, `from` of `capacity` is a field of the heartbeat in `heartbeats`. `heartbeats` is `{<worker>: {server, <place_by field>?}}`, the read heartbeats; `live` is the workers whose heartbeat changed within the last `LOST_AFTER`; `slots` is `{<worker>: {released: "false" | "true" | "taking", holder}}`, no entry — there is no slot row; `assignments` is `{<worker>: [<id>…] | "@garbled"}`, the assignment rows, no entry — there is no row; `units` is `{<id>: <unit row> | "@garbled"}`, the elements as text, no entry — there is no row (weight 0); `intent` is `{target, members}`, an active intent (a load reserve), or no field; `drain` is the drained server (`""` — none), `decommissioned` is the decommissioned servers; `resources` is `{<server>: live | silent | unknown}`, `resource_state`; `wants` is `{<server>: {want, retiring?} | "@garbled"}`, the order rows, no entry — there is no row.

The native output is the JSON object `{pool, keepers, idle_by_policy, placeable, load, count}`: `pool` is the array of workers in the slot order; `keepers` is `{<place>: <worker>}`, the keepers at `distinct`; `idle_by_policy` is `{<worker>: bool}` at each read heartbeat; `placeable` is `{<server>: {placeable, why?}}` at the servers of the heartbeats and the resources; `load` and `count` are `{<worker>: n}` at the workers with a readable assignment (unreadable — no entry). With `manifest.capacity` the output also has `capacity`, `{<worker>: <count> | null}` (`null` — the field is not a number: it does not accept new units), and `fates`, `{<worker>: {why}}` (a field of the controller's pass report; the console computes all the fields except `fates`).


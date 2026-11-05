# Vectors: the pool, the place keeper, the fitness of a server

This English text is the source; the Russian translation `ru/vectors/pool/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the pool contract](../../contracts/pool.md) (lesson P/04; the guess of stage C C06-SERVER-POLICY-33-01, the Architect's decision of
2026-10-25). The participants are the controller (P/04 Н3 «choose») and the console (P/06.5 Н2: `idle_by_policy`, `placeable`, `why`). The bytes
are written by «Спецификация»; the rows were composed by the text of the contract and checked by its oracle, not by the code of implementations.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object (the reads are replaced by the input):

| Field | Meaning |
|---|---|
| `manifest` | `{prefix, servers: shared \| distinct, place_by?: server \| <поле пульса>, requires: none \| resource, grows?: bool, weight?: {field, default}, capacity?: {from, default}}` (`capacity` — the pool contract capacity; the field `from` of the heartbeat in the input `heartbeats`) |
| `manifest.prefix` | the `slot.prefix` of the manifest (P/02.1 Н1.2; the slot name contract): by it the slot order (the keeper at equality, the order of the pool) and the parsing of the name of the role process `<prefix>-<сервер>-<n>` («number above `want`»); in all rows `t` (C61-PREFIX-01) |
| `heartbeats` | `{<воркер>: {server, <поле place_by>?}}` — the read heartbeats |
| `live` | the workers whose heartbeat changed within the last `LOST_AFTER` |
| `slots` | `{<воркер>: {released: "false" \| "true" \| "taking", holder}}`; no entry — there is no slot row |
| `assignments` | `{<воркер>: [<id>…] \| "@garbled"}` — the assignment rows; no entry — there is no row |
| `units` | `{<id>: <строка единицы — элементы текстом> \| "@garbled"}`; no entry — there is no row (weight 0) |
| `intent` | `{target, members}` — an active intent (a load reserve) or no field |
| `drain`, `decommissioned` | the drained server (`""` — none) and the decommissioned servers |
| `resources` | `{<сервер>: live \| silent \| unknown}` — `resource_state` |
| `wants` | `{<сервер>: {want, retiring?} \| "@garbled"}` — the order rows; no entry — there is no row |

**Output** — `{pool: [<воркер>…], keepers: {<место>: <воркер>}, idle_by_policy: {<воркер>: bool}, placeable: {<сервер>:
{placeable, why?}}, load: {<воркер>: n}, count: {<воркер>: n}}`: the pool in the slot order; `load` and `count` — at the workers with
a readable assignment (unreadable — no entry); the keepers at `distinct`; `idle_by_policy` at each read heartbeat;
`placeable` at the servers of the heartbeats and the resources; with `manifest.capacity` — also `capacity: {<воркер>: <число> | null}` (`null` — the field is not a number: it does not accept new units) and `fates: {<воркер>: {why}}` (C04-POOL-CAPACITY-0E-01). The comparison is JSON by value.

22 rows: the capacity — no field (the default), a fraction, not a number (a boolean, a string; C04-POOL-CAPACITY-0E-01); `grows: false`, without an order row, with an unreadable one, retiring from a readable one; the load at an absent, an unreadable
unit row, a weight field not a number, without `placement.weight`; the former ones — liveness by the slot, the drain and the decommission, `requires: resource` (silent, unknown) and `requires: none`, `retiring` and a number above
`want`, `distinct` — the keeper by weights and the slot order, an unreadable assignment, a new worker without an assignment, the intent reserve,
the place `""`, a worker that is not live.

## Run

Without a stand: a side gives the input to its pool computation and compares the output. The requirements of a unit beyond the pool (`constraint`,
`spread_by`, `affinity`, the order) are P/04, not this package; the capacity of a worker (`capacity`) is here, the comparison of the capacity with the load at the choice is P/04.
Who performs is the controller (`04-controller`, P/04 Н3 «choose»: a live worker, the pool, the place keeper) — all fields; the cluster console (`06-console`, P/06.5 Н2: `WorkerRow.load`, `capacity`, `idle_by_policy`, `ServerRow.placeable`, `why` — the same computation by its own reads) — all fields except `fates` (a field of the controller's pass report). Only reads the result: the console module (`07-console-module`, the output of `/servers`); the worker (`03-worker`) takes `CAPACITY` only for the memory budget at start (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/pool` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

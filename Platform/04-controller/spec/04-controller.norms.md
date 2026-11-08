# P/04 — Controller: norms

This English text is the source; the Russian translation `ru/spec/04-controller.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of the lesson. Lecture (`ru/04-controller.md`, for people, not in the export), [instructions](04-controller.README.md), [life cycle](../lifecycle.md),
[acceptance](../acceptance/README.md), vectors [`order`](../vectors/order/README.md),
[`shrink-victim`](../vectors/shrink-victim/README.md) and [`shrink-allowed`](../vectors/shrink-allowed/README.md). The lesson has no HTTP contract of its own (`P/04 no-openapi`): the doors through
which the operator talks to the controller are the doors of the console ([P/06.6](../../06-console/spec/06.6-console.norms.md) N2; `/where` — [chapter 6.5](../../06-console/spec/06.5-console.norms.md)). Current source dependencies are the [observation contract](../../common/contracts/observation.md), the current data families below, and the linked console doors. Requirement and checklist identifiers are retained; the acceptance files define the full completion boundary.

## N0 Vocabulary

<!-- req: P/04-R001 -->

Normative keywords (MUST, MUST NOT, SHOULD, MAY by RFC 2119 and RFC 8174) follow the [course canon](../../common/NORMATIVE-TERMS.md). The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

<!-- req: P/04-R069 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner (ADR-0130 Addendum (10)). MB4: a turn protects guarded store mutations only; external actions require their owner-declared independent fence. Q4 retry ownership and Q5 bounded resources also apply.

## N1 Form

<!-- req: P/04-R002 -->

**Time.** The time fields of the rows and objects of the lesson are time by [the canon of N0 of P/01.1](../../01-store/spec/01.1-store.norms.md#time-in-a-row): `<sub>/placement/<id>` — `at`; `platform/doors/<host>` — `since`, `at`; `platform/drain` — `at`; `platform/decommission/<host>` — `at`; `<sub>/decommissioned/<host>` — `asked_at`, `at`; `<sub>/decommission-pending/<host>` — `asked_at`, `at`; `<sub>/controller/placement_intent` — `at`; `<sub>/want/<host>` — `at`; the object `<sub>/controller/pass` — `at`, `last_success`; the object `<sub>/snapshot/<worker>` — `ts`.

<!-- req: P/04-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/placement/<id>`, `<sub>/workers/<name>`, `<sub>/want/<host>`, `<sub>/decommissioned/<host>`, `<sub>/decommission-pending/<host>`, `<sub>/controller/placement_turn`, `<sub>/controller/placement_intent`, `<sub>/controller/pass`, `<sub>/snapshot/<worker>`, `<sub>/snapshot/unplaced`, `<sub>/snapshot-tables/<table>`;
- writes: `<sub>/slots/<name>` (cas), `<sub>/<manifest:unit.rows>/<id>` (delete), `<sub>/<manifest:domain.books.from>/<slot>` (delete), `<sub>/state/<name>/<id>` (delete), `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events or objects root>/<path>/%h<sha256>.name` (create), `<objects root>/<dir>/~lock` (create);
- reads: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `<sub>/heartbeats/<name>`, `<sub>/slots/<name>`, `<sub>/holds/<place>`, `<sub>/<manifest:unit.rows>/<id>`, `<sub>/state/<name>/<id>`, `platform/schema`, `platform/resources/<server>/heartbeat`, `<sub>/policy`, `platform/servers/<host>`, `platform/doors/<host>`, `platform/drain`, `platform/decommission/<host>`, `<sub>/<manifest:tables>/<name>`, `/etc/w2c/tls/<role>/server.key`.

<!-- req: P/04-R004 -->

The tables of places and links (`places.table`, `places.wanted`, `affinity.table`, N1.3) and the tables `domain.view_tables` (N1.3b) the controller reads as rows `<sub>/<manifest:tables>/<name>`;
the journal `unit.unplaced_deleted` (N3 «pass()», step 8) and the alarms (`workers.raise_failed` — N1.4, hung/unsure — step 3) it writes to
`audit/<role>` and `audit.alarms/<role>`, the file `%h<sha256>.name` — by the [event journal
contract](../../common/contracts/event-journal.md) (`journal`, `writer`, «File names»); the key of its own kit is for
the resource doors over HTTPS ([P/02.4 N1.6](../../02-installer/spec/02.4-installer.norms.md) `roles`) (review of stage B 3–5, № 10).

<!-- req: P/04-R005 -->

The rows `<sub>/policy`, `platform/servers/<host>`, `platform/drain`, `platform/decommission/<host>` (written by the console, P/06.6) and
`platform/doors/<host>` (written by the resource, P/05) are given in N1.1 in the form that the controller reads; the owner of the row is
the writer process (catalogue).

### N1.1 Controller rows

<!-- req: P/04-R006 -->

```yaml
<sub>/placement/<id>:                     # a decision; the writer is the controller
  worker:    <worker name> | ""           # "" — not placed; with an active intent the common decision of N1.5 applies
  reason:    <a string for a human>       # non-empty; grammar — N3 «Reason»
  at:        <wall seconds of the controller>
  rev:       <decimal integer ≥ 1>        # +1 on every write
  manifest_rev:  <revision of the manifest under which the decision was taken>   # required for the current decision; a missing value is unreadable, never stamped (P/02.3)
<sub>/workers/<name>:                      # an assignment; derived from the placement rows
  units:     <list of ids by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array)>   # sorted
  rev:       <decimal integer ≥ 1>        # +1 only when the list changes
<sub>/policy:                             # the writer is the console; the controller reads it
  servers:   shared | distinct            # another value or key on read — the manifest default; on write — a refusal
platform/servers/<host>:                # the writer is the console (ADR-0026)
  labels:    <comma-separated labels>     # "" — none; the row beats the node labels
platform/doors/<host>:                  # the writer is the resource of the server (ADR-0045); the form — P/05 N1.4 door_row (family doors)
  room.<sub>, live.<sub>:                 # the controller reads them — free(s) N3 «shortage()» (ADR-0084 addendum (3) R14′); the element
                                          # is absent, does not read or is unknown — the server is not an order candidate
platform/drain:                           # the writer is the console; one row per cluster
  server: <server>; at: <moment>
platform/decommission/<host>:           # the writer is the console
  by: <who>; at: <moment>; why: <words>; gone: "true"?   # gone — the confirmation «there is no server» when the resource was never heard
<sub>/decommissioned/<host>:            # the writer is the controller; removed when the request is withdrawn
  asked_at, at:  <wall seconds of the console request and of the controller mark>
  slots, units, holds:  <names of the released slots, ids of the removed units, places of the holds — by the list rule of P/06.1 N1.2; "" — none>
                 # an element: slots — a slot name P/03.2 N1.4, units — a unit id P/06.1 N1.3, holds — a place name P/03.2 N1.3;
                 # a count («0») is not an element (added by the pilot of the data family schemas, D7)
                 # names, not numbers (reconciliation of python and go 2026-10-18)
<sub>/decommission-pending/<host>:     # unfinished controller progress, never the final decommission mark
  state: prepared | cleaning | finalizing
  request_index: <version>             # exact fixed platform/decommission/<host> index
  asked_at, at: <time>                 # request at and plan acceptance time
  manifest_rev: <revision>
  remaining: [{name: <slot name>, index: <version>}, ...]  # JSON; original versions, no later substitution
  from: [<owned from prefix>, ...]     # fixed full prefixes, each ending in /
  released, skipped: [<slot name>, ...]
  current: [<slot name>, ...]          # at most BATCH_WRITES - 1, the confirmed release chunk
  cleanup_index: "" | <version>        # empty means the progress row's own index, before its first cleanup rewrite
  slot_cursor, from_cursor: <count>    # next current slot and its next from prefix
  units, holds: <lists>                # fixed final-mark metadata, same form as decommissioned
<sub>/want/<host>:                      # the writer is the controller, cas with the guard placement_turn (N1.5); ADR-0084 and addendum (1)
  want:      <decimal 1…WANT_NUM_MAX>               # the absolute target of the number of role processes on the server, the base <prefix>-<server>-1 is included
  at:        <moment of the write>        # diagnostics; the terms — by the observation of the row version (N1.4 terms)
  by:        <controller instance>        # diagnostics; the authority — cas and the guard placement_turn
  why:       <non-empty reason>           # grammar N3 «shortage(), order()…»
  retiring?: <worker name>                # chosen for shrinking (N3 «shrink»)
  # the row exists, except while pending/finally decommissioned, for an installed role on a server of a manifest with grows: true (N3 «order row»); only the decommission
  # of the server and the removal of the role delete it; shrinking writes want 1, does not delete; the controller and the console read it (series workers_wanted P/06.5 N3 «/metrics — text»)
```

### N1.2 Pass report

<!-- req: P/04-R007 -->

The object `<sub>/controller/pass` is written at the end of every pass; it is read by the console (the series `<sub>_reconcile_last_pass_age_seconds`, `<sub>_reconcile_pass_seconds`, `<sub>_reconcile_failures`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — text») and by the workers (`names_given`, `hung_move_after` — P/03.2). The pass report MUST contain the fields below; an implementation MAY add its own counters.

<!-- req: P/04-R008 -->

```yaml
pass:
  at:                   <moment the control part ends, before snapshot publication>
  ok:                   bool;  error: <text of the last error or "">;  failures: <number>;  last_success: <moment>
                        #   ok: true — the control part reached its end, all its inputs were read and no control write was refused; otherwise false
                        #   (C04-PASS-OK-01)
  seconds:              <duration of the control part, excluding later snapshot/report publication>
  manifest_rev:             <manifest revision of the controller>;  manifest_behind: <rows of this pass whose write
                        is postponed because of a lagging manifest; a row — once per pass> (C04-MANIFEST-BEHIND-COUNT-01)
  names_given:          {<slot name>: <version of the slot row at which the name is given>}
  hung_move_after:      <seconds of the hang limit in force at this controller>
  fates:                {<name>: {fate, server, why, rev, since}}   # only occupied slots not released: holder non-empty, released
                        #   false (not true and not taking — the slot contract «States»); since — the moment the slot entered this fate on the clock of the controller
                        #   (a change of fate — a new since), not the first look at the slot (reconciliation of python and go 2026-10-18)
  diverged:             <assignments fixed by sync>
  unplaced:             <units without a worker, except those taken out of service>
  garbled:              <unit rows that do not read>
  expired_kept:         <manual rows with a passed deadline that the deadline removed but did not delete: a target with fixed fields
                        or about not by id (N3 «pass()» step 8; ADR-0091 item 1)>
  snapshot_state_garbled: <unit states not included in the snapshot shard of this cycle: the state row does not read
                        by its type (N1.3a; P/03.6 N1.7 unreadable; ADR-0091 item 3)>
  state_swept_total:    <state rows removed by the sweep of the orphaned and after the delete of the unit row (N3 step 8a)>
  snapshot_tables_refused: <tables of N1.3b that this cycle replaced with a stub: the object is larger than SNAPSHOT_TABLE_MAX>
  snapshot_rows_garbled: <unit rows not included in the snapshot shard of this cycle: a field of snapshot does not read
                        by its type (N1.3a garbled)>   # P/01.1 N0 «Stability of output»; the decision of the Architect,
                        #   reconciliation of python and go M10/6–11, T7
  reach_moves_total, slots_released_total, unplaced_deleted_total, servers_decommissioned_total,
  workers_hung, workers_hung_moved_total, workers_unsure_moved_total, name_conflicts: <numbers>
  unplaceable:          {<id>: <why>}   # units without a place in this pass and a non-empty reason; the console takes why from it
                        #   for /unplaceable and reason 404 /where/<id> of an unplaced one (N2.2)
  short:                # only with placement.grows: true; an element for each label set with waiting ones
    - {labels: [<labels>], units: <exact nonnegative integer sum of waiting unit weights>, workers: <processes needed beyond the live ones and the capacity in flight>,
       groups: <waiting groups>, ordered: <ordered by this pass>, withheld?: <words why it is not ordered>}
                        #   labels — the canonical notation: unique labels ascending, a repeat collapses (R21);
                        #   groups — always, 0 too (required in the form — review of stage B 3–5, № 13); own counters of the element MAY be added by the existing count form; standard fields keep their forms; acceptance compares the named fields;
                        #   an empty set in the words of why is any labels; a set without a computable per is the same element: workers 0,
                        #   ordered 0, withheld «no positive capacity estimate» (R20); the series <sub>_workers_withheld{labels}
                        #   (P/06.5 /metrics) — for each set of the pass report, zero too (ADR-0084 addendum (2) R23)
  wants:                {<server>: {want, live, pending, retiring?, why, state}}   # only with grows: true; live — the live
                        #   role processes of the server, pending — in flight(s) by heartbeats (N3, R13′); state: ok | raising |
                        #   raise_failed | no_base
  raise_failed:         {<server>: {since, times}}   # the server «failed to raise»: since — the moment the order was withdrawn, times — in a row
  near_waiting:         [<subsystem>…]   # only with placement.near whose near.sub is not in the manifest catalogue of this pass:
                        #   the affinity waits for its installation (N1.3 near; ADR-0091 addendum (27) item 6); otherwise there is no field
```

The current reader and writer both require expired_kept, snapshot_state_garbled and state_swept_total as nonnegative count values. Missing or invalid fields use the existing unreadable outcome. The first two belong to this cycle; state_swept_total accumulates confirmed deletions from zero in this process. The current snapshot reader and writer both require exactly one admissible unit.rows array, including an empty array; missing or multiple arrays are unreadable. Absence before the first object publication is separate.

Weight aggregates short[].units, waiting and load are exact nonnegative integers without a common.uint53 ceiling; their JSON output has integer notation and never rounds or saturates through binary64/int64. Individual weights/capacities and other count fields keep their forms. Custom short counters keep count; widening the aggregate changes no full serialized-object write limit.

A cycle ends its control part and releases the placement turn, then attempts the unit snapshots and table snapshots, and finally writes one pass report containing the snapshot counters of that same cycle. At, seconds, last_success, ok and failures describe only the control part. Snapshot errors keep their own existing outcomes/logs/counters and do not become control failures. The three snapshot counters start at zero for each cycle; the next cycle cannot reset or absorb an unfinished prior cycle. After publication attempts return their confirmed, refused, failed or unconfirmed outcomes, write the final report once, without later patching it. state_swept_total is not reset.

### N1.3 Placement keys and their meaning

<!-- req: P/04-R009 -->

The form of the keys is P/02.1 (N1.2). Here — what each of them means for the controller, and the default.

<!-- req: P/04-R010 -->

| Key | Meaning | Default |
|---|---|---|
| `capacity: {from, default, unit_mb, base_mb}` | capacity — [the pool contract](../../common/contracts/pool.md) `capacity` (moved there without a change; layout audit, the Architect's decision of 2026-10-25, A-12); the reason — the field `fates.<worker>.why` of the pass report (N1.2) | `from: capacity`; `default` is required |
| `headroom: {from}` | headroom — a heartbeat field that the subsystem names; the controller does not read it (neither the choice, nor the slot fate, nor the pass report); the console shows it — the series `worker_headroom{worker,server}` and `headroom` ([P/06.5](../../06-console/spec/06.5-console.norms.md) N3 «/metrics — text») (C04-HEADROOM-UNREADABLE-01) | `from: headroom` |
| `weight: {field, default}` | the weight of a unit — an `int` field of the row ≥ 1, when the field is absent — weight.default ≥ 1; a wrong present value is not replaced with default: the unit row is unreadable (`garbled` of the pass report), the unit is neither placed nor removed, the reason is in `unplaceable`; the load = Σ of the weights (ADR-0078) | without the key — weight 1 for all |
| `constraint` | `none` \| `labels-subset`: the labels of the unit ⊆ the labels of the worker. The labels of the unit — its field `labels` of type `list` (no field — an empty set, the constraint holds); a label — by [the label alphabet](../../common/contracts/labels.md); the labels of the worker — the row `platform/servers/<host>` or the node labels | `none` |
| `tie_break` | `most-free-capacity` — the only word | the same |
| `servers` | `shared` \| `distinct`: with `distinct` only one worker can carry the units on one place — the one with the largest load, on equality the first in the slot order of P/03.2 N1.4; the others stay idle | `shared`; the row `policy` overrides |
| `place_by` | what counts as a place with `distinct` — [the pool contract](../../common/contracts/pool.md) `place`, the keeper — `keeper` (layout audit, the Architect's decision of 2026-10-25, B-07); `distinct` units are given only to the keeper of a non-empty place (ADR-0084 addendum (2) R15) | `server` |
| `places: {table, where, server_field, lease, wanted}` | the table of places and the hold row `<sub>/holds/<place>` (P/03.2 N1.3); `lease: strict` — a strict place; `wanted` — a table of the subsystem: a row with the name of a place says that the place needs a holder, the reason is known to the subsystem (N3 «shortage()»; C04-PLACE-WANTED-01) | — |
| `spread_by` | a field: two units with one value are not on one server; an absent or empty value does not take part in the spreading — a unit without a value neither constrains nor is constrained (a pair to `group_by`: empty is not a group; reconciliation of python and go M10/3–5, the Architect's decision) | — |
| `group_by: {field, cut_at}` | a group — one value of the field (for `url` — the host by `cut_at: host`); it is placed only whole on one worker (ADR-0011). What a group is, the host in one spelling, `none`, an unreadable host, «not in a group» and the refusal — [the contract of the group by host](../../common/contracts/group-of.md) (moved without a change of behaviour; stage C guess W03-GROUP-01, the Architect's decision of 2026-10-23; ADR-0053; vector [`group-of`](../../common/vectors/group-of/README.md); review of stage A, SA1-20; reconciliation of python and go 2026-10-18) | — |
| `near: {sub, by, of, prefer}` | a preference: beside the holder of a neighbour — the units of the subsystem `sub` (the manifest catalogue). My value — the field `by` of my row, without `by` — my id; the value of a neighbour — its field `of`, without `of` — its id; the neighbours — the live rows of `sub` whose value equals mine. Among several neighbours first those that matched `prefer` — AND over the fields, OR over a list of values; a field value is a scalar (equality) or a list (as `affinity.strict`; C04-NEAR-PREFER-SCALAR-01); a field of `prefer` is a path: a segment through `.` is a step along a reference field of the neighbour to the row it names (`home.kind` — the field `kind` of the row named by the field `home` of the neighbour); among equals — by the id of the neighbour (UTF-8 bytes). The worker holding the chosen neighbour is preferred; no holder — no preference (ADR-0091 item 10; vectors [`near-of`](../vectors/near-of/README.md)). The manifest `sub` is not in the catalogue — the affinity does not apply, the unit is placed without it, the controller does not need the rows of `sub`; the subsystem is in `near_waiting` of the pass report (N1.2); the affinity is switched on from the pass at which the manifest `sub` appeared in the catalogue (N3 «pass()» step 1; ADR-0091 addendum (26) item 2, addendum (27) items 5–6) | `none` |
| `home` | a preference, not a filter: a field of the row naming the home (the value — of the first member in UTF-8 order; no value — no home), or `near` — the home is at the neighbour; only one side of a pair can follow. The field is a reference `ref` to the table of places `places.table`: the home is the holder of the named place, the worker whose place (`place_by`, the pool contract `place`) is the name of this row; there is no holder among the eligible (N3 «choose») — the workers of the server from the field `places.server_field` of this row, if the field is non-empty; otherwise there is no home. An empty server field does not hinder the home when there is a holder: the home is the holder (a volume without a server). Another worker of the same server, when there is a holder, is not the home: a unit at it moves to the holder (N3 «pass()», step 7). The reason: `place_by` names where the data of the unit lie; a comparison with the server would give it to the holder of another place of this server, and step 7 would not bring it back. No row or it does not read — no home. A field without `ref` — its value is the server itself: the home is the workers whose `server` equals the value. A `ref` to another table (or the manifest has no `places`) — no home: the value is the id of a foreign row, not a server, and `places.server_field` is not named for it (C04-HOME-REF-OTHER-01). C04-HOME-PLACE-HOLDER-01, the Architect's decision of 2026-10-30, replaces the comparison with the server C04-HOME-PLACE-OR-SERVER-01 | — |
| `affinity: {field, table, server_field, strict, exclusive}` | a filter: a place from the table that admits the unit; `admits: false` takes nobody; a binding row leads the unit only to its own place. The place of the unit is the row of `table` named by its `field` (no value or no row — affinity does not apply). `strict` is a predicate that selects the binding rows: a row is binding when each field of `strict` equals the value or is in the list of values (AND over the fields, OR over a list); no `strict` or `{}` — all rows of the table bind, there are no non-binding ones (C04-AFFINITY-EMPTY-STRICT-01). A binding row leads the unit only to the holder of its place — the worker whose place (`place_by`, P/03.2 N1.3) is the name of the row; with a non-empty `server_field` of the row — also only if the server of the worker is that one (both conditions; another worker of the same server with another place does not fit; C04-AFFINITY-BOUND-HOLDER-01); a non-binding one is a preference for the server `server_field`, not a filter. `admits` is checked at the actual place of the unit (journal of cammeta-go, lesson 8 № 2). `exclusive: true` (only with `strict`, P/02.1) — the binding place is exclusive: its holder admits only the units bound to this place, the others are not placed on it (as `admits` for strangers); a worker with such a place takes no other places (P/03.2 N3 «place: take, hold, let go»); a binding row with an empty `server_field` — strictness by the holder of the place without a check of the server (ADR-0091 addendum (9) item 6, addendum (10) items 1–3; repeated review of addendum (10)) | — |
| `requires` | `none` \| `resource`: with `resource` a worker is eligible only while the resource of its server is not silent | `none` |
| `grows` | `true` — the role grows on demand: the controller counts the shortage and orders processes of the role per server with the row `<sub>/want/<host>` (N3 «shortage(), order()…»; ADR-0084) | `false` |
| `retire_when: {state?, field, in, delete_after?}` | a unit with a value of the field from `in` is not placed and is removed with the value as the reason. Without `state` the field is one of the unit row; with `state` — a field of the value of the acting state `unit.state.<state>` (the row-check contract «Unit state» acts; no acting one — not finished). `delete_after` — N s after the removal by `retire_when`, by the clock of the controller, delete the row (N3 step 8): the count starts from the first pass at which the controller saw the unit removed by `retire_when`; a pass at which it is no longer removed (an operator edit removed the value or the acting state) clears the count, a new removal counts anew (C04-RETIRE-TIMER-CLEAR-01); after a restart of the controller the count starts anew, as for `unplaced.delete_after` (ADR-0091 items 1, 3; replaces `forget_finished` of the subsystems) | — |
| `ends: {field, never}` | the deadline of a unit: the field `field` of the row (Unix seconds) ≠ `never` and not later than the clock of the controller — the unit is not placed, is removed with the reason `ends`, the row is deleted (N3 step 8); `never` — no deadline (ADR-0091 item 2) | without the key — no deadline; `never: 0` |
| `rebalance: {dead_band}` | rebalancing on request: while the spread of the load is smaller — do not move | `0.10` |
| `unplaced: {delete_after}` | a unit row that nobody holds for longer than N s by the clock of the controller is deleted by the controller (ADR-0067); one removed by `retire_when` too: nobody holds it. For a table with `fixed` fields (except the field that is the source of the id) or with `about` not by id, only the rows with `made` are physically deleted (the name is held by the template `key` of the customer, P/03.6 N1.6) — likewise by `retire_when.delete_after` and `ends`; the deadline does not delete the manual rows of such a table: `ends` removes them and does not place them, `delete_after` does not delete them, the counter `expired_kept` of the pass report (amendment of ADR-0067 addendum 2026-10-10, ADR-0091 item 1); the operator deletes them through a door. The worker of the subsystem MAY also delete its own unit rows by the key `worker.deletes` — a delete with `cas` without the write right (ADR-0067 addendum 2026-10-17; there is no training consumer yet — a debt in «the specification progress note (for people)») | without the key — never |

### N1.3a Snapshot

<!-- req: P/04-R011 -->

```yaml
<sub>/snapshot/<worker> | <sub>/snapshot/unplaced:     # objects; the writer is the controller; the worker name unplaced is a refusal
  {cluster, worker: <name> | null, ts, <rows>: [{id, revision, <fields of snapshot:>, state?, worker, server}]}
          worker: the worker name of the shard; null — for the shard unplaced and for the shard of a gone worker (C04-SNAPSHOT-GONE-WORKER-01)
cluster:  the installation name — CLUSTER of the environment (the environment file contract «Environment variables»; the name of a domain member, [P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.1); not set — "local" (outside a domain)
fields:   snapshot: of the manifest (P/02.1): no key — all fields except *_secret and blob; [] — no field (id, revision, worker, server
          remain); an author field server is also excluded by default; a secret, blob or server in an explicit list — the manifest does not load; addresses — with the mask
          P/06.2 N1.1a, the same as in the console output (password → ***)
          the declared fields of a unit do not include platform_fields P/06.1 N1.2, including deleted/worker: a load refusal P/02.1;
          unit.rows not cluster/worker/ts: a collision with the envelope — the load refusal refused:form (P/02.1)
state:    with a declared unit.state — an object {<name>: <value of the acting state>} (the row-check contract «Unit state» acts, the same rule
          as at the console P/06.1 N2 «State in the answer»): the names — state.<name> of the snapshot list of the manifest; without the key snapshot —
          all states except cursor; [] — none; no acting one — no name, none at all — no state. A state row
          that does not read by its type — the unit is in the shard without this state, the counter snapshot_state_garbled of the pass
          report (N1.2) (ADR-0091 item 3)
publish:  after the control part releases turn and before this cycle's one final report (N3 «pass()»); the shards of gone workers — empty; without units — an empty unplaced
          an empty shard has one form for all: {cluster, worker: null, ts, <rows>: []} — the field <rows> is present, the list is empty
          (as the witness; C04-SNAPSHOT-GONE-WORKER-01)
garbled:  a unit row whose snapshot field does not read by its type by values_by_type P/06.1 N1.2 is not included in the shard;
          the shard is published with the other units, a log line once per series and the counter `snapshot_rows_garbled` of the pass report
          N1.2 (P/01.1 N0 «Stability of output») (reconciliation of python and go M10/6–11, T7)
ceiling:  before the write the controller judges the resource door limit L owned by P/05; max_bytes of the store is held by the store itself on put
          ([P/05](../../05-resource/spec/05-resource.norms.md) «object store» — `TooLarge`), the controller does not count it itself;
          TooLarge of the store gives the same outcome of N4 — the shard is not written, the former one is kept (C04-SNAPSHOT-CEILING-MAXBYTES-01, the decision of the Architect 2026-10-28).
          The size is the number of bytes of the full serialized object, including the envelope and the empty shards, with the actual
          notation of ts (its length is part of the size) (reconciliation of python and go M10/6–11, matched without a norm).
          Exactly L is allowed; more than L → TooLarge before put_durable, do not replace the former shard.
          Diagnostics: «N units on <shard>; snapshot is B bytes, limit is L bytes»; raising OBJECTS does not lift the door limit
```

### N1.3b Table snapshot

<!-- req: P/04-R012 -->

The domain view shows the units with `domain.ref`; the other unit rows and the console tables of a foreign cluster are not visible to the domain without this object (ADR-0110, step 2 of the analysis). A manifest without `domain.ref` and a unit without a value of `ref` are visible here.

<!-- req: P/04-R013 -->

```yaml
<sub>/snapshot-tables/<table>:  # an object; the writer is the controller; <table> — a key of domain.view_tables of the manifest (P/02.1, P/08.1 N1.4a):
                                  # a table of tables or unit.rows
  {cluster, ts, refused?, rows: [{key, revision, fields, secrets?, labels?, about?, worker?, server?, phase?, status?}]}
cluster:  as for a shard, N1.3a
ts:       the moment of the object write; rows did not change — the object is not written, ts is the former one: liveness is not ts but members[].state of the view
rows:     store rows, the order — key in UTF-8 bytes; key — the row name (P/06.1 N1.6) or the unit id, revision — the row version
          (P/06.1 N2 «Row revision»); a removed row and a tombstone are not in rows
fields:   only the fields of the list domain.view_tables of the manifest; the value — by its type by values_by_type P/06.1 N1.2; a field absent from the row — in fields
          it is absent, no default is substituted; held_by of a table of places — as P/06.1 N1.6 held_by; addresses — with the mask P/06.2 N1.1a;
          the keys *_secret inside json values are cut at any depth (P/06.2 N1.4); the list does not name the *_secret fields themselves (P/02.1)
secrets:  the names of the *_secret fields of the row with a non-empty value, ascending in UTF-8 bytes; none such — no field; no values:
          the domain needs to know whether a secret is set (ADR-0110)
labels, about: only for unit rows — the field labels and the value of the field about.field of the manifest, whether the list names them or not: the right judges by them (the right contract
          «Judgement by target»); no value — no field
worker, server: only for unit rows — from the assignment; no assignment — no fields
phase, status:  only for unit rows — phase and the fields domain.view_status of the manifest from the element status[] of the heartbeat of this unit (P/08.1 N1.4 status);
          no element — no fields
garbled:  a row whose field from the list does not read by its type is not included in rows; the counter snapshot_rows_garbled, as N1.3a garbled
ceiling:  SNAPSHOT_TABLE_MAX from forms/runtime-constants.tsv of the full serialized object; more — instead of the object a stub {cluster, ts, refused:
          "too_large", rows: []} and snapshot_tables_refused of the pass report (N1.2). A stub, not the former object: an old snapshot would look alive.
           The agent owns per-member and combined table budgets (P/09.1 N1.2 tables_budget and its linked P/08 admission bounds); this controller introduces no second member count, camera count or measured domain-wide byte ceiling.
scope:    the object exists for a manifest with domain.view_tables; domain.ref is not needed for it; the key removed from the manifest — the object
          is not removed, the agent no longer carries it (the report intake contract member_objects)
reader:   only the domain agent (P/09.1 N1.2); the cluster console reads its own tables as rows
```

### N1.4 Terms and states of the judge

<!-- req: P/04-R014 -->

```yaml
constants:
  LOST_AFTER:       the observation contract «Freshness» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-01)   # heartbeat freshness («within the last LOST_AFTER»;
                          # review of stage A 6–7, № 1, № 2) and the margin after SLOT_TERM of observing an unchanged slot version
  HUNG_MOVE_AFTER:  the environment file contract «Constants and units» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-17)   # s; the age of the observed slot version up to the hung/unsure/wait limit; from the environment of the controller, published in the report
  ALIVE_EVERY:      the observation contract «Resource state» (the value is there; layout audit, the decision of the Architect 2026-10-25, A-10)   # the resource rewrites at of its door
  REACH_BUDGET:     the environment file contract «Constants and units» (the value is there; A-17)   # units per pass for moves by reachability; from the environment
  WRITE_CONFLICT_LIMIT: forms/runtime-constants.tsv  # consecutive conflicts of one logical change; after the limit the existing step fails, not an extra attempt; barriers remain
  HOME_BUDGET:      forms/runtime-constants.tsv     # unit per pass for moves home
  WANT_GRACE:      forms/runtime-constants.tsv    # s; an order the server has not raised is withdrawn (N3 «withdraw on deadline»)
  RAISE_QUIET:      forms/runtime-constants.tsv   # s; a server that «failed to raise» gets no orders
  RAISE_FAILS_LOUD:      forms/runtime-constants.tsv     # failures in a row — the alarm workers.raise_failed of raised severity
  SHRINK_AFTER:     the environment file contract «Constants and units» (the value is there; A-17)   # s; without a shortage — shrinking (N3 «shrink»); only on the stand — W2C_SHRINK_AFTER=<seconds>
                          # of the environment of the controller (as W2C_WALL_OFFSET M11/3): with the variable set, the controller writes
                          # a loud journal line at start; outside the stand the variable is not set (ADR-0084)
  SHRINK_BUDGET:      forms/runtime-constants.tsv     # unit per pass for a move from the worker being shrunk (as HOME_BUDGET)
  # the terms of the order and of shrinking are starting values of the policy; the count is by the local monotonic clock of the controller from the first
  # observation of the order row version (for SHRINK_AFTER — from the first pass without a shortage), a new controller starts from 0,
  # a repeated write of the same target does not extend the term, at is diagnostics (ADR-0049; ADR-0084 addendum (1) R5);
  # WANT_GRACE — from the first pass where in flight(s) > 0 (N3), reset — when in flight(s) = 0: the order is raised, then the process
  # of the number died without a change of the row version — the count is from the pass where the number is in flight again, not from the former version (C04-WANT-GRACE-REPATH-01)
resource_state:     # the resource of a server — live | unreachable | unknown | silent: one definition for all observers
                    # (the controller, the console) by their monotonic clocks, the rules in order — the observation contract
                    # (common/contracts/observation.md «Resource state»; review of stage A 6–7, № 2);
                    # only silent excludes and moves
process_presence:   # what the resource says about the process of a worker: the output of [P/05 N1.4](../../05-resource/spec/05-resource.norms.md) `presence` by the key <sub>/<slot name> of its subsystem;
                    # only from the heartbeat of a resource in the state live: a stale heartbeat with the word runs gives no presence, and the slot
                    # is judged by resource_state (reconciliation of python and go 2026-10-18); an absent one of the fields workers, running,
                    # unknown is an empty list (a partial set: running without workers — runs, workers without running — gone;
                    # C04-PRESENCE-PARTIAL-01)
  runs | gone | unlisted | unknown   # unknown — an unconfirmed read; silent — only the resource state above
fate:               alive | wait | hung | hung_moved | unsure | unsure_moved | move | release
NAME_FATES:         [move, hung_moved, unsure_moved, release]   # + wait beyond the limit HUNG_MOVE_AFTER
MOVED_FATES:        [move, hung_moved, unsure_moved]
```

<!-- req: P/04-R015 -->

The observation of a version, the freshness `LOST_AFTER` («within the last LOST_AFTER» — one relation `≤`) and `resource_state` are
[the observation contract](../../common/contracts/observation.md) (review of stage A 6–7, № 1, № 2); here — what they
mean for the judge and the pool of the controller (N3 «choose», «fate»).

### N1.4a Server failure: the move

<!-- req: P/04-R016 -->

```yaml
power_pull:
  moves:    units — by two silences (the heartbeat of the worker and the word of the resource), by the tolerances of N3; (SLOT_TERM + LOST_AFTER) + a pass —
            a guide for a sound stand with heartbeats known in advance, an available store and capacity, not a general deadline; the new holder takes
            the next epoch; the same with shared and distinct; it does not move back by itself, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)
  stays:    the archive on the volume of the server — under the old epoch, unavailable until the return, not rebuilt, not lost;
            the units of a hung live worker — stay with it (one writer)
  lost:     the open bucket and the closed buckets without a confirmed mirror copy; one vote of the group.
            An RPO of a bucket length is admissible only with a confirmed mirror of all closed ones; otherwise the loss is larger
  store:    1 of 3 — an election in seconds; 2 of 3 — 503 unavailable after the effective P/01 -leader-wait, the workers live on the last assignment by the lease
            and unconfirmed_max; recovery — recover by hand (P/01.3 N3 «recover the store (no majority)»)
  restore:  P/05 N1.4 «Bucket restore»
  return:   the resource pulls the buckets; the workers take free names; a name with an expired slot — only by the word of the controller (P/03.2)
  presence: the presence lock contract (common/contracts/presence-lock.md)
fresh_controller: what is seen for the first time has just changed; it moves nothing for the first LOST_AFTER (N3 «pass()», step 0)
```

<!-- req: P/04-R017 -->

`stays`, `lost`, `store`, `return` and the procedure «pull the power» (N3) are the remainder of M10/11 N1.4, N3, moved here with lesson 6
(stage B; the plan of the move of lesson 6, item 5: no norms remain in M10/11).

### N1.5 Placement admission between controllers

<!-- req: P/04-R018 -->

A subsystem has one controller changing the placement at each moment. The right is set by a row,
not by the presence of a process: late writes of the former holder are cut off by the store guard.
The new service rows belong to the controller role; the placement readers also read them.
The store doors and the vocabulary of operations remain P/01.1.

<!-- req: P/04-R019 -->

```yaml
<sub>/controller/placement_turn:         # a row; the writer is the controller
  holder: <unique mark of the capture attempt> | ""  # a new attempt does not repeat the mark of the former one
  manifest_rev: <manifest revision>              # does not decrease; an old controller does not capture a new revision
<sub>/controller/placement_intent:       # a row; it is not deleted after creation
  state: active | idle
  manifest_rev: <revision of the accepted decision>
  # only with active:
  members: <JSON array of all ids of the decision; unique, sorted>
  target: <worker name> | ""             # one target of the whole group; "" — remove the placement
  reason: <non-empty reason>
  at: <wall seconds of taking the decision>
constants:
  TURN_TERM, TURN_RENEW: the writer turn contract «Terms» (moved there without a change; layout audit A-03, the decision of the Architect 2026-10-25)
```

<!-- req: P/04-R020 -->

An unreadable turn/intent row is a refusal of the placement change with failures, not an empty row. An intent row out of form
(`state` is not `active`/`idle`; an active one has no `members`, `target`, `reason`, `at`, or they are not in the form above) is unreadable:
the controller — a refusal with failures, the readers (`/where`, `/unplaceable`, label forecasts) — 503 `unavailable`, not idle
(reconciliation of python and go 2026-10-18).
Their initial absence is admissible; after creation neither row is deleted. Turn keeps
the lower bound of manifest_rev, idle is kept so that the version of intent does not return to
the version of absence between two reads; the readers below need this.

<!-- req: P/04-R021 -->

An active intent is an accepted common decision for members while the individual placement and workers
are being brought to it. For each of its ids the target/reason/at/manifest_rev of the intent decide; the other ids
are decided by their own placement. A reader (/where, unplaceable, forecasts and the controller) reads the decision by
[the observation contract](../../common/contracts/observation.md) «Reading the decision: intent → placement → intent» (review
of stage A 6–7, № 2). With idle, all rows of the completed decision have already been brought to it.

<!-- req: P/04-R022 -->

For admission the load of a target is counted conservatively: the sum of the weights of the unique ids already assigned
to it **or** directed there by the effective decision. Double counting of one id at one worker
is excluded; an old assignment not yet removed keeps the room at the former worker. The same aggregate
is counted for spread_by. An active intent reserves all members at target even before workers.
The indicators of the actual assignment are still counted by workers; the reserve is a condition of admission,
not a statement that the unit already runs. Before a new admission an unfinished intent is completed.

<!-- req: P/04-R023 -->

A group is admitted by one intent with all its members from a fresh look and one common target;
the preferences are chosen by the first id in UTF-8 order, the constraints and the weight — by all members.
The workers never get the assignments of the members of this operation at different targets at the same time:
first all former assignments of all members are removed, then the members are added to one target.
An intermediate absence of a part of the assignments is admissible and is repaired; a partial decision on capacity is not.
Changes of the unit fields, the group composition, the capacity, the policy and the life after the look are processed
by the next pass: they are not atomic with the admission. With unchanged inputs the competition of controllers
does not exceed the capacity, does not violate spread_by and does not split a group.
If after a change of composition a group is placed only partially and does not fit whole on the former target,
it is first removed whole by an intent with target ""; it waits or chooses a new common
target by the next decision. A fully placed group is not reconsidered without a reason to leave.

<!-- families:begin -->
### Data families (built from the standard files)

The form of the rows and objects that the chapter owns by the [catalog](../../common/data/catalog.tsv) is the JSON Schema 2020-12 of the family (ADR-0092). An instance of a row is `{key, row}`, of an object `{key, object}`; the key is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after the [codec](../../common/data/codec.tsv): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority applies.

#### `<sub>/placement/<id>` — row

Schema — [`placement.schema.json`](../data/placement.schema.json), outcomes — [`placement.outcomes.tsv`](../data/placement.outcomes.tsv); form version 1; norm — P/04 N1.1, N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `worker` | string; matching `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` in full | required |  | the worker name — a slot name, P/03.2 N1.4 (`<prefix>-<suffix>`; prefix of its own manifest — a check of the lesson, not of the form); "" — not placed |
| `reason` | string | required |  | The current nonempty human reason, required for readers and writers (P/04 N3 Reason). |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the controller's wall-clock seconds at the moment of the decision |
| `rev` | string; matching `[1-9][0-9]*` in full | required |  | a decimal integer ≥ 1; +1 for each write of the row |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | Required manifest revision under which the current intent completion wrote this decision. A missing value is unreadable and is never stamped or repaired; newer-revision protection remains P/04 N3 manifest_rev. |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `reason` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the controller — an error of a pass step (failures + 1), the unreadable is not replaced by absence and is not rewritten as unplaced (N3 «pass()»: «data from such a read are not replaced by empty ones»); the cause goes to the log (layout audit, G-04; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | P/04 N3 «pass()» |
| the whole row | `console` | the whole row is unreadable: the effective placement (/where, /unplaceable, label forecasts) — an unconfirmed read, not «not placed» (layout audit, G-04) | 0 | row | P/04 N1.5 |

#### `<sub>/workers/<name>` — row

Schema — [`workers.schema.json`](../data/workers.schema.json), outcomes — [`workers.outcomes.tsv`](../data/workers.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `units` | list, without repeats, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | ids of the assigned units by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array; codec array), sorted; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the unit id (P/06.1 N1.3); a numeric id — also by this grammar |
| `rev` | string; matching `[1-9][0-9]*` in full | required |  | a decimal integer ≥ 1; +1 only when the list changes |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the worker is not in the pool, does not enter garbled of the pass report (N4 «heartbeat/slot/assignment is unreadable»; the Architect's answer of 2026-10-25 to the questions of stage 3, G-08) | 0 | row | P/04 N4 |
| the whole row | `<s>worker` | the whole row is unreadable: the worker reading its own assignment does not change its set of units (takes no new ones, does not give away the ones held by this row), the log (the Architect's answer of 2026-10-25 to the questions of stage 3, G-08) | 0 | row | P/03.3 N3 «loop()» step 2 |
| the whole row | `console` | the whole row is unreadable: drain — `GET /drain` 503 `unavailable` (the Architect's answer of 2026-10-25 to the questions of stage 3, G-08) | 0 | row | P/06.6 N1.2 |

#### `<sub>/want/<host>` — row

Schema — [`want.schema.json`](../data/want.schema.json), outcomes — [`want.outcomes.tsv`](../data/want.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `want` | integer; ≥ 1; ≤ 99 | required |  | the absolute target of the number of processes of the role on the server, the base `<prefix>-<server>-1` is included; maximum WANT_NUM_MAX is defined by P/04 forms/runtime-constants.tsv; numeric minimum/maximum carriers stay unchanged. |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the write; diagnostics — the terms go by the observation of the row version (N1.4 terms) |
| `by` | string | required |  | the controller instance; diagnostics — the authority is given by cas and the guard placement_turn |
| `why` | string | required |  | a non-empty reason; the grammar of N3 «shortage(), order()…» |
| `retiring` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the worker chosen for shrinking (N3 «shrink»); a slot name, P/03.2 N1.4 |

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `why` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the unreadable is not replaced by absence and is not rewritten: an error of step 9 (failures + 1), the order rules (retiring, «number above want») are not applied to the processes of the server (the pool contract want_rule), the cause goes to the pass log (layout audit, G-07; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | row | P/04 N3 «pass()»; pool contract want_rule |
| the whole row | `console` | the whole row is unreadable: there is no series workers_wanted{server} of this server, the server's script starts and stops nothing by it (P/02.4 N1.5; layout audit, G-07) | 0 | row | P/06.5 N3 «/metrics — text» |

#### `<sub>/decommissioned/<host>` — row

Schema — [`decommissioned.schema.json`](../data/decommissioned.schema.json), outcomes — [`decommissioned.outcomes.tsv`](../data/decommissioned.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `asked_at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the console request (`platform/decommission/<server>` at) |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the controller's mark |
| `slots` | list, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | names of the given-away slots by the list rule of P/06.1 N1.2; "" — none; names, not a number (D7) |
| `slots[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `units` | list, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | list, element — string | required |  | the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | string | optional |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the controller does not remove or rewrite the mark at revocation, the cause goes to the pass log (layout audit, G-03; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25); the mark of the subsystem about.sub, near.sub or ref of the unit being placed is unreadable — the server is not confirmed for this placement: not a candidate, a step error (failures + 1), the cause goes to the log; it counts neither as decommissioned nor as not decommissioned (P1; V7 item 3, row 7) | 0 | row | P/04 N3 «choose(unit)»; P/04 N1.1 |
| the whole row | `<s>domain` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value (P1; V7 item 3, row 6) | 0 | row | P/03.7 N1.6 start; P/03.2 N3 «start()» step 3 |
| the whole row | `<s>worker` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value (P1; V7 item 3, row 6) | 0 | row | P/03.2 N3 «start()» step 3 |
| the whole row | `console` | the whole row is unreadable: `/servers` — `decommissioned: null` (the general rule of output: a field with an unreadable source — null, if required) (the Architect's answer of 2026-10-25 to the questions of stage 3, G-03) | 0 | row | P/06.6 N2.1; P/04 N3 «decommission_server» |

#### `<sub>/decommission-pending/<host>` — row

Schema — [`decommission-pending.schema.json`](../data/decommission-pending.schema.json), outcomes — [`decommission-pending.outcomes.tsv`](../data/decommission-pending.outcomes.tsv); form version 1; norm — P/04 N1.1; N3 decommission_server; ADR-0127 review P/04 C2.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `state` | string; one of: `prepared`, `cleaning`, `finalizing` | required |  | prepared: release the next original candidates; cleaning: remove contributions for the confirmed current release chunk; finalizing: publish the final mark last |
| `request_index` | string; not one of: `""` | required |  | the immutable index of platform/decommission/\<host> for this plan |
| `asked_at` | time (P/01.1 N0 «Time in a row») | required |  | at of the fixed console request |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the controller time at plan acceptance |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision used to freeze the owned from prefixes |
| `remaining` | list, without repeats, element — map `{name, index}`; in `items` — a JSON text (x-encoding: json) | required |  | ordered immutable slot names and original observed versions still to release; never replace a version after conflict |
| `remaining[]` | map `{name, index}` | optional |  |  |
| `remaining[].name` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the name of the given-away slot, P/03.2 N1.4 |
| `remaining[].index` | string; not one of: `""` | required |  | the exact opaque store version; compare only for equality |
| `from` | list, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` in full | required |  | distinct ordered owned family prefixes from this manifest domain.books declarations; full prefixes including final slash; never a foreign subsystem |
| `from[]` | string; matching `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` in full | optional |  |  |
| `released` | list, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | slot names confirmed released by this plan, in release order; historical names, never an authority to touch a later holder |
| `released[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `skipped` | list, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | original candidates whose version changed; never reread/adopt a newer version for release |
| `skipped[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `current` | list, at most 63 items, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the current atomic release chunk; at most BATCH_WRITES-1 slots; exact shared release index from cleanup_index or the progress row index |
| `current[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `cleanup_index` | string | required |  | empty only before the first progress rewrite of a confirmed release chunk: then the progress row index is the exact release index; otherwise its preserved value, never a later slot reread |
| `slot_cursor` | integer; ≥ 0; ≤ 9007199254740991 | required |  | zero-based current slot being cleaned; compared with current length by the procedure |
| `from_cursor` | integer; ≥ 0; ≤ 9007199254740991 | required |  | zero-based next from prefix for the current slot; conflict discards the remainder of this slot |
| `units` | list, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | final mark metadata fixed before plan acceptance: ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | list, element — string | required |  | final mark metadata fixed before plan acceptance: the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | string | optional |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Rules:

- `<root>`: if `state` — `prepared`: `current` — also any value; `cleanup_index` — also one of: `""`; `slot_cursor` — also one of: `0`; `from_cursor` — also one of: `0`; `remaining` — also any value.
- `<root>`: if `state` — `finalizing`: `current` — also any value; `cleanup_index` — also one of: `""`; `slot_cursor` — also one of: `0`; `from_cursor` — also one of: `0`; `remaining` — also any value.
- `<root>`: if `state` — `cleaning`: `current` — also any value; `from` — also any value.

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the progress row is unreadable: do not infer completion, recreate the plan, release slots or delete contributions; keep progress and final mark unchanged, record a step error and retry only after a readable source is restored | 0 | row | P/04 N1.1; N3 decommission_server, progress and recovery; ADR-0127 review P/04 C2 |

#### `<sub>/controller/placement_turn` — row

Schema — [`placement-turn.schema.json`](../data/placement-turn.schema.json), outcomes — [`placement-turn.outcomes.tsv`](../data/placement-turn.outcomes.tsv); form version 1; norm — P/04 N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `holder` | string | required |  | a unique mark of the capture attempt or "" — the turn is free; a new attempt does not repeat the mark of the previous one |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision (P/02.3 N1.5 rev); does not decrease — an old controller does not capture a new revision |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: a refusal of the placement change with failures and a cause, not an empty row; without a new admission; restore the service row | 0 | row | P/04 N1.5, N3 «get and hold the placement turn» step 1, N4 |

#### `<sub>/controller/placement_intent` — row

Schema — [`placement-intent.schema.json`](../data/placement-intent.schema.json), outcomes — [`placement-intent.outcomes.tsv`](../data/placement-intent.outcomes.tsv); form version 1; norm — P/04 N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `state` | string; one of: `active`, `idle` | required |  | active — the decision is still being carried through; idle — all rows of the completed decision have been carried through |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision of the decision made |
| `members` | list, without repeats, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full; in `items` — a JSON text (x-encoding: json) | optional |  | a JSON array of all ids of the decision; unique, sorted (the order is a rule of the lesson, not of the form); only when active |
| `members[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of a unit of the decision (P/06.1 N1.3) |
| `target` | string; matching `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` in full | optional |  | one target of the whole group — a worker name (slot, P/03.2 N1.4); "" — remove the placement; only when active |
| `reason` | string | optional |  | A nonempty human reason when state is active, for reader and writer alike. The idle form does not require reason. |
| `at` | time (P/01.1 N0 «Time in a row») | optional |  | wall-clock seconds of making the decision; only when active |

Rules:

- `<root>`: if `state` — `active`: required `members`, `target`, `reason`, `at` (the path is the missing key); `reason` — also any value; not one of: `""`.

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `reason` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): the controller — a refusal of the placement change with failures, not an empty row and not idle | 0 | row | P/04 N1.5, N4 «intent row out of the form of N1.5» |
| the whole row | `console` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): /where, /unplaceable, label forecasts — 503 unavailable, not idle | 0 | row | P/04 N1.5 |

#### `<sub>/controller/pass` — object

Schema — [`controller-pass.schema.json`](../data/controller-pass.schema.json), outcomes — [`controller-pass.outcomes.tsv`](../data/controller-pass.outcomes.tsv); form version 1; norm — P/04 N1.2.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `at` | time (P/01.1 N0 «Time in a row») | required |  | Wall time when this cycle control part ended; frozen before snapshot publication, not the final object put time. |
| `ok` | bool | required |  | The control part completed with its confirmed inputs/writes and no control-step failure; snapshot outcomes are recorded separately. |
| `error` | string | required |  | the text of the last error or an empty string |
| `failures` | by the definition `count` | required |  | Independent control-step failures of this cycle; snapshot publication outcomes do not increment this field. |
| `last_success` | time (P/01.1 N0 «Time in a row») | required |  | Last successful control-part completion time, unchanged by a later snapshot publication failure. |
| `seconds` | number; ≥ 0 | required |  | Duration of this cycle control part only, excluding snapshot and final-report publications. |
| `manifest_rev` | string or integer | required |  | the manifest revision of the controller |
| `manifest_behind` | by the definition `count` | required |  | rows of this pass whose write was postponed because of a lagging manifest; a row — once per pass |
| `names_given` | map author names: name — by the definition `slot_name`, value — string; not one of: `""` | required |  | names given away by the fate; the worker reads them at capture (P/03.2 N3 «capture») |
| `names_given.<name>` | string; not one of: `""` | optional |  | the version of the slot row (index P/01.1 N1, an opaque string) at which the name was given away (N3 «fate» names_given) |
| `hung_move_after` | number; ≥ 0 | required |  | seconds of the hang limit in force at this controller (N1.4 HUNG_MOVE_AFTER); the worker reads it |
| `fates` | map author names: name — by the definition `slot_name`, value — map `{fate, server, why, rev, since}` | required |  | only taken slots not given away (holder non-empty, released false) |
| `fates.<name>` | map `{fate, server, why, rev, since}` | optional |  |  |
| `fates.<name>.fate` | string; one of: `alive`, `wait`, `hung`, `hung_moved`, `unsure`, `unsure_moved`, `move`, `release` | required |  |  |
| `fates.<name>.server` | string | required |  |  |
| `fates.<name>.why` | string | required |  |  |
| `fates.<name>.rev` | string or integer | required |  | the version of the judgment about the slot |
| `fates.<name>.since` | time (P/01.1 N0 «Time in a row») | required |  | the moment the slot entered this fate by the controller's clock |
| `diverged` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaced` | by the definition `count` | required |  | a counter ≥ 0 |
| `garbled` | by the definition `count` | required |  | a counter ≥ 0 |
| `snapshot_tables_refused` | by the definition `count` | required |  | Tables replaced by the too_large stub during this cycle at SNAPSHOT_TABLE_MAX; included in this same final report, outside control-step failures. |
| `snapshot_rows_garbled` | by the definition `count` | required |  | Unreadable snapshot fields omitted by unit/table publications of this same cycle; reset only for the next cycle after this final report. |
| `reach_moves_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `slots_released_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaced_deleted_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `servers_decommissioned_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_hung` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_hung_moved_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_unsure_moved_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `name_conflicts` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaceable` | map author names: name — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full, value — string; not one of: `""` | required |  |  |
| `unplaceable.<name>` | string; not one of: `""` | optional |  | a non-empty reason — why of /unplaceable and reason of 404 `/where/<id>` |
| `short` | list, element — map `{labels, units, workers, groups, ordered, withheld?}` and other author names: name — string, value — by the definition `count` | optional |  | only when placement.grows true |
| `short[]` | map `{labels, units, workers, groups, ordered, withheld?}` and other author names: name — string, value — by the definition `count` | optional |  |  |
| `short[].labels` | list, element — string | required |  | the label set — the canonical notation in ascending order (N3 «set order») |
| `short[].labels[]` | string | optional |  |  |
| `short[].units` | integer; ≥ 0; the whole sign for the reader too (x-whole) | required |  | Exact nonnegative sum of waiting unit weights, in integer JSON notation, without an upper common.uint53 bound. Preserve the whole serialized-report limit; never round or saturate through binary64/int64 (P/04-R008). |
| `short[].workers` | by the definition `count` | required |  | processes needed beyond the live ones and the capacity in flight |
| `short[].groups` | by the definition `count` | required |  | waiting groups; always, 0 too (analysis of review of stage B 3–5, № 13) |
| `short[].ordered` | by the definition `count` | required |  | ordered by this pass |
| `short[].withheld` | string | optional |  | words for why it was not ordered |
| `short[].<name>` | by the definition `count` | optional |  | An own counter of the short element; standard properties keep their declared forms. |
| `wants` | map author names: name — by the definition `server_name`, value — map `{want, live, pending, retiring?, why, state}` | optional |  | only when placement.grows true |
| `wants.<name>` | map `{want, live, pending, retiring?, why, state}` | optional |  |  |
| `wants.<name>.want` | integer; ≥ 1; ≤ 99 | required |  |  |
| `wants.<name>.live` | by the definition `count` | required |  | live processes of the role of the server |
| `wants.<name>.pending` | by the definition `count` | required |  | capacity in flight |
| `wants.<name>.retiring` | by the definition `slot_name` | optional |  | a slot name, P/03.2 N1.4 |
| `wants.<name>.why` | string | required |  |  |
| `wants.<name>.state` | string; one of: `ok`, `raising`, `raise_failed`, `no_base` | required |  |  |
| `raise_failed` | map author names: name — by the definition `server_name`, value — map `{since, times}` | required |  |  |
| `raise_failed.<name>` | map `{since, times}` | optional |  |  |
| `raise_failed.<name>.since` | time (P/01.1 N0 «Time in a row») | required |  | the moment the order was removed |
| `raise_failed.<name>.times` | by the definition `count` | required |  | refusals in a row |
| `near_waiting` | list, at least 1 items, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  | the subsystems of placement.near.sub that are not in the manifest catalog of this pass: the affinity waits for their installation (N1.3 near; ADR-0091 addendum (27) item 6); otherwise there is no field |
| `near_waiting[]` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  |  |
| `expired_kept` | by the definition `count` | required |  | Manual rows retained after ends removed them; required nonnegative count for current reader and writer, zero when none. |
| `snapshot_state_garbled` | by the definition `count` | required |  | Unreadable unit states omitted by the unit snapshot publications of this same cycle; reset only for the next cycle after this final report. |
| `state_swept_total` | by the definition `count` | required |  | Cumulative confirmed orphan-state deletions from this process start; not reset between cycles. |
| `.<name>` | any value | optional |  | the implementation's own counters (N1.2 — MAY add) |

**`count`** — a counter ≥ 0

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<count>` | integer; ≥ 0; ≤ 9007199254740991 |  |  |  |

**`server_name`** — the server name — the grammar of SERVER_NAME (P/02.4 N1.2)

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<server_name>` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full |  |  |  |

**`slot_name`** — a slot name, P/03.2 N1.4

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<slot_name>` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full |  |  |  |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| `/names_given` | * | the worker at capture (P/03.2 N3 «capture» step 1): without a readable names_given there is no permission by it — the name is taken only when released or free, the cause goes to the log (layout audit, G-01; rule DF-OUTCOMES-109, the Architect's decision of 2026-10-25) | 0 | field | P/04 N1.2; P/03.2 N3 «capture» |
| `/short` | * | short out of form (an element without a required field of N1.2, including groups): the console does not give the series units_short, workers_withheld and groups_waiting of this pass (C06-GROUPS-WAITING-33-01), /metrics — 200 (P/01.1 N0 «Stability of output»); the rest of the report is read (analysis of review of stage B 3–5, № 13) | 1 | field | P/04 N1.2; P/06.5 N3 «/metrics — text» (review analysis of stage B 6–7, № 24) |
| `/hung_move_after` | * | the worker (P/03.2): keeps the previous hang limit (the last one read); if none was read — does not judge itself hung by the limit of the report; the cause goes to the log once per pass (the Architect's answer of 2026-10-25 to the questions of stage 3, G-02) | 1 | field | P/04 N1.2 |
| the whole object | `<s>worker` | the whole object is unreadable: the worker at capture — as /names_given: there is no permission by it, the name is taken only when released or free, the cause goes to the log; the hang limit — as /hung_move_after: the previous one read, without one read it does not judge itself hung by the limit of the report | 2 | row | P/04 N1.2; P/03.2 N3 «capture» |
| the whole object | `console` | the whole object is unreadable: the console removes the series from the pass report rather than dropping the /metrics answer (P/01.1 N0 «Stability of output»); /where of an unplaced one — reason without why: «not placed: no worker holds it» | 2 | row | P/06.5 N3 «/metrics — text»; P/06.6 N2.2 |

#### `<sub>/snapshot/<worker>` — object

Schema — [`snapshot.schema.json`](../data/snapshot.schema.json), outcomes — [`snapshot.outcomes.tsv`](../data/snapshot.outcomes.tsv); form version 1; norm — P/04 N1.3a.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | string or null; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the worker name of the shard (slot, P/03.2 N1.4); for the shard of a gone worker — null |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of publication |
| `.<name>` | list, element — map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  | name: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<name>[]` | map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  |  |
| `.<name>[].id` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | the unit id (P/06.1 N1.3) |
| `.<name>[].revision` | string or integer | required |  | revision of the unit row |
| `.<name>[].worker` | string or null | required |  | the worker of the assignment; unplaced has none |
| `.<name>[].server` | string or null | required |  | the worker's server |
| `.<name>[].<name>` | any value | optional |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `<root>` | at most 1 names (x-max-names) |
| `.<name> (name)` | string; not one of: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; matching `[a-z][a-z0-9_-]{0,31}` in full |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output»; the Architect's answer of 2026-10-25 to the questions of stage 3, G-05) | 0 | row | P/06.5 N1.3 age, metrics |
| the whole object | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log (the Architect's answer of 2026-10-25 to the questions of stage 3, G-06) | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot/unplaced` — object

Schema — [`snapshot-unplaced.schema.json`](../data/snapshot-unplaced.schema.json), outcomes — [`snapshot-unplaced.outcomes.tsv`](../data/snapshot-unplaced.outcomes.tsv); form version 1; norm — P/04 N1.3a.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | null | required |  | for the shard of the unplaced — null |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of publication |
| `.<name>` | list, element — map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  | name: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<name>[]` | map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  |  |
| `.<name>[].id` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | the unit id (P/06.1 N1.3) |
| `.<name>[].revision` | string or integer | required |  | revision of the unit row |
| `.<name>[].worker` | string or null | required |  | an unplaced one has no worker |
| `.<name>[].server` | string or null | required |  | the worker's server; an unplaced one has none |
| `.<name>[].<name>` | any value | optional |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `<root>` | at most 1 names (x-max-names) |
| `.<name> (name)` | string; not one of: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; matching `[a-z][a-z0-9_-]{0,31}` in full |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output»; the Architect's answer of 2026-10-25 to the questions of stage 3, G-05) | 0 | row | P/06.5 N1.3 age, metrics |
| the whole object | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log (the Architect's answer of 2026-10-25 to the questions of stage 3, G-06) | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot-tables/<table>` — object

Schema — [`snapshot-tables.schema.json`](../data/snapshot-tables.schema.json), outcomes — [`snapshot-tables.outcomes.tsv`](../data/snapshot-tables.outcomes.tsv); form version 1; norm — P/04 N1.3b.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the write of the object; rows did not change — the previous one |
| `refused` | string; one of: `too_large`, `whole_too_large` | optional |  | a stub instead of rows: the table did not fit (P/04 N1.3b ceiling, P/09.1 N1.2 tables_budget) |
| `rows` | list, element — map `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | required |  | the rows of the table by key in UTF-8 bytes (the order is a rule of the lesson, not the form) |
| `rows[]` | map `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | optional |  |  |
| `rows[].key` | string; not one of: `""` | required |  | the row name (P/06.1 N1.6) |
| `rows[].revision` | integer; ≥ 1; ≤ 9007199254740991 | required |  | the row version |
| `rows[].fields` | map, opaque | required |  | fields of the list domain.view_tables of the manifest; values of their own type; no secrets |
| `rows[].secrets` | list, element — string | optional |  | names of the set *_secret fields; no values |
| `rows[].secrets[]` | string | optional |  |  |
| `rows[].worker` | string | optional |  | for unit rows — from the assignment |
| `rows[].server` | string | optional |  | for unit rows — from the assignment |
| `rows[].phase` | string | optional |  | for unit rows — from the heartbeat |
| `rows[].status` | map, opaque | optional |  | fields of domain.view_status from the element of status[] of the heartbeat |
| `rows[].labels` | list, element — string | optional |  | for unit rows — the field labels |
| `rows[].labels[]` | string | optional |  |  |
| `rows[].about` | string | optional |  | for unit rows — the id of the about unit |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `domainagent` | the whole object is unreadable (not JSON or not an object of the family): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log (P/09.1 N1.2) | 1 | row | P/09.1 N1.2 |
<!-- families:end -->

---

## N2 Doors

<!-- req: P/04-R024 -->

The lesson has no HTTP doors of its own (`P/04 no-openapi`). The console doors through which the operator talks to the controller
(`/policy`, `/drain`, `/servers/{server}/labels`, `/servers/{server}/decommission`, `/unplaceable`, `/where/{id}`), their
procedures and refusals are [P/06.6](../../06-console/spec/06.6-console.norms.md) N2 (`/where` — [chapter 6.5](../../06-console/spec/06.5-console.norms.md) N2); the controller executes their writes as the rows of N1.1 on its pass
(N3).

---

## N3 Procedures

<!-- req: P/04-R025 -->

delete_after applies only to a named id: numeric together with this key is rejected by the loader of P/02.1. The controller does not replace a physical delete with a tombstone and does not destroy the history of numeric issues.

### get and hold the placement turn

<!-- req: P/04-R026 -->

Steps 1–6, the barrier and «Races» are [the writer turn contract](../../common/contracts/turn.md) «Get and hold the turn»,
«Barrier» (moved there without a change of behaviour; layout audit A-03, the Architect's decision of 2026-10-25). The turn row of the controller is `<sub>/controller/placement_turn`
(N1.5), `holder` is a new unique mark of the attempt; the changing writes under the guard (step 5 of the contract) are every write/delete of
placement/*, workers/* and placement_intent, and also the delete of a unit row by delete_after; the turn is given up at the end of the pass
(step 6 of the contract).

### accept and complete a decision(members, target, reason)

<!-- req: P/04-R027 -->

```
0. the turn is mine; an active intent → first complete it, do not accept new decisions yet;
   manifest_rev of the intent > mine → do not change it and the placements; the rows of its members — into manifest_behind (N1.2)
1. for a new decision: freshly read the units, the effective decisions, the assignments and the properties of the candidates;
   at least one placement of members has manifest_rev > mine → do not accept the intent; the rows of members — into manifest_behind (N1.2);
   check the whole group/unit, the free capacity with the reserves of N1.5, spread_by and the other constraints;
   for the estimate of a move the own former reserves of members are not counted as a second copy at the target;
   the final set is checked: the former ids without members + ALL members, including spread_by between
   the members of the group itself and over all workers of the target server;
   no common target → no new admission (the removal uses target "")
   the full key <sub>/placement/<id> of at least one of the members is longer than the key limit of the store
   (P/01.1 N1) → there is no decision, the intent is not written; these members — into unplaceable with why
2. write the active intent with cas of the read idle (or cas "" on the initial absence) and guard turn;
   toolarge before a confirmed active → a refusal of the step, do not change placement/workers, do not split the group
3. after a confirmed intent freshly list/read ALL workers;
   remove ALL members from ALL assignments, including target, each by a write cas + guard turn;
   only the confirmed completion of all removals allows going on
4. assign to each placement of members target/reason/at/manifest_rev of the intent with cas + guard turn,
   rev + 1; the row already contains these fields → do not rewrite it; an absent one starts with rev 1
5. target non-empty → add ALL members to its assignment by one write cas + guard turn;
   target empty → no addition; while 3–4 are not complete, step 5 is forbidden
6. only after the confirmation of 3–5 write the intent {state: idle, manifest_rev} with cas + guard turn
```

<!-- req: P/04-R028 -->

Each group occupies one intent write; it is not split for the sake of the ceiling of a row or of an assignment.
The weight of both future rows (the intent and the full assignment of the target) is checked before step 2; an excess is
a refusal of the step with a reason and failures, without a partial placement. Before step 2 it is likewise checked that
the full key `<sub>/placement/<id>` of each of the members is representable within the key limit of the store
(P/01.1 N1): an id admissible by P/06.1 N1.3 for a unit row may not fit into the longer
placement key. An unrepresentable key — there is no decision, the intent is not written, the group is not split;
these members go into `unplaceable` with `why`, the other decisions of the pass go on. Therefore
an intent that cannot be completed because of the key length never happens, and one such unit does not stop the placement
of the subsystem. An incomplete read also forbids admission.
On a change of holder an active intent is recovered **from step 3**; a new decision and another direction
for its members are forbidden until completion. The composition, the target and the rule are fixed in the intent;
changes of the inputs after its acceptance are processed by the next decision after the recovery.
After completion all new calculations take a fresh look, so the reserve of the previous decision is already visible.

<!-- req: P/04-R029 -->

**Races.** Two admissions of different units do not use one remainder: B gets the turn after A and sees
the decision/assignment of A or its active intent, which B is obliged to complete first. With capacity=1
the second weight 1 does not pass; with spread_by the occupied value is already visible. Two different first members of
a group do not create different decisions: one active intent fixes all of them and one target. After a break
in the middle of the removals the additions do not start; after a break in the middle of placement the new holder
repeats the removals and completes the same target. Until the addition to the new target the old ones have not a single
assignment of members. This is a guarantee of rows/assignments, while stopping the actions of old processes
is ensured by their reconciliation and leases (P/03.3, P/03.2), not by one change of the placement map.

### pass() — every PASS_EVERY

<!-- req: P/04-R030 -->

```
0. observation: update the memory of the seen heartbeats, slots and resources on the own clock; the objects of the cluster (heartbeats of workers
   and resources, reports) are read through the resource of the own server (the objects door of P/05, `scope`; ADR-0084 addendum (2) R17); without
   a resource on the own server with `cluster://` — «unknown», not «absent» ([the object store client contract](../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27);
   seen for the first time = has just changed; get the placement turn by N3 above;
   busy → no changing pass, a retry after TURN_BUSY_RETRY; mine → first complete an active intent;
   then a fresh look: the units, the placements, the assignments and the properties of the candidates;
   before every new decision the look is refreshed, the results of the previous decision are taken into account
1. revision: read the manifest revision; a placement without its required manifest_rev is unreadable; do not stamp or repair it;
   read the manifest catalogue (platform/manifest/*) — on every pass: the manifest near.sub has appeared — the affinity (N1.3 near)
   applies from this pass; it is absent — no affinity, near_waiting (ADR-0091 addendum (27) item 5)
2. decommission of servers: resume pending or admit a stopped server by N3 decommission_server; release/cleanup in bounded chunks,
   then publish <sub>/decommissioned/<s> only at finalization. Before admission a heard server leaves the request standing.
3. slot fates (below); release → write the slot as released; names_given; alarms hung/unsure; an abandoned capture — remove the rows under it (below)
4. place: remove the deleted (reason deleted) → remove by retire_when (by the acting state with retire_when.state) →
   remove by ends (the field ≠ never and ≤ the clock of the controller; reason ends) → sync of the assignments with the placements (diverged) →
   each unplaced unit from placeable (N3 shortage; deleted, ends and retire_when excluded) — choose (below), a group whole at its first member; each in its own attempt;
   the order of the unplaced — by id in UTF-8 bytes (a group — by the id of the first member); the same order for the moves of steps 5–7
   (added by the reconciliation of M11, cammeta-python 05 № 25)
5. reachability: the units whose server no longer reaches their labels — a move within REACH_BUDGET;
   a group — whole, the first group goes even beyond the budget; nowhere — remove with a reason
6. leaving: the units of the workers that are leaving (below) — a move without a budget; a group whole, or it waits
7. home: no more than HOME_BUDGET units — home, if there is room there; the home is judged as in «choose» (N1.3 home): the holder
   of the named place is eligible — it alone is the home, a unit at another worker, including one of the same server, moves to it; there is no
   holder — the home is the server of the place, and a unit on this server is already home; no home, it has no free room or is not eligible — the unit
   stays: a preference does not become a filter (C04-HOME-PLACE-HOLDER-01)
8. unplaced for longer than delete_after: under the own turn re-read the unit and its effective placement
   by N1.5; there is an assignment, an active intent (with any target) or the read is not confirmed → do not delete. Still unplaced and the deadline is confirmed →
   delete the row with cas of its fresh version AND guard of the own version of placement_turn (the admission of step 5 above);
   conflict/412/no answer → the barrier and a new plan by the turn rule, the journal unit.unplaced_deleted only on success.
   Likewise — one removed by retire_when now, for longer than retire_when.delete_after (from the first pass that saw it removed; a pass
   at which it is no longer removed clears the count, N1.3; after a restart — anew): the condition is checked on the fresh row and, with
   retire_when.state, on its acting state, no longer removed — do not delete: an operator edit is not lost (the Architect's decision of
   2026-11-01, Quint V/05.1 V1, C04-RETIRE-TIMER-CLEAR-01) — and one removed by ends: ends deletes right after the removal (ADR-0091 items 1, 2). For a table with fixed fields or
   about not by id only a row with made is deleted; a manual row is not deleted — expired_kept + 1 (N1.3 unplaced).
   A row with made is deleted by the row-check contract «Customer row: made» `delete` (strictly after made.keep, not_before = max(0, made.keep − 60);
   layout audit A-11): 409 early — not deleted, without a barrier and a journal, on the next pass;
   keep prevents only an obviously early delete attempt; a delete arriving late is still bounded by not_before at store admission. It never authorizes deletion before keep.
   The row is deleted physically, without a tombstone (P/01.1 delete): the row first, with cas of the read version and guard of the own
   version of placement_turn; an edit or a prolongation between the read and the delete — conflict: the delete is cancelled, the state is not
   touched; only after a confirmed delete of the row — its states (step 8a); the journal unit.unplaced_deleted
   {reason: unplaced | retired | ends}
8a. state sweep (unit.state declared; ADR-0091 item 3): list <sub>/state/; for each state row read
   the unit row: it is absent, a tombstone or its born ≠ born of the state → orphaned: delete by one operation with cas of the version of the
   state and guard {key: the unit row, index: the read version — for a tombstone its version, "" — no row}; a row
   created or changed after the read cancels the sweep (412 — leave it until the next pass); the acting and
   other non-orphaned ones (born matched, revision differs) — do not touch; state_swept_total + 1 for each removed one
9. shortage and order (grows: true): order rows, capacity in flight, short, order, withdraw on deadline
9a. shrink (grows: true): the victim, retiring, a move of no more than SHRINK_BUDGET, the end or the cancel; drain — N3 below
10. finish the control part and its ok/failures/at/seconds/last_success; release the turn;
    then attempt unit snapshots and table snapshots outside turn, and write this cycle's one final <sub>/controller/pass
each step — in its own attempt: an error of a step — failures + 1, the other steps go on
```

<!-- req: P/04-R031 -->

A definite badkey of a full store key is an error of the corresponding step, not the absence
of a row; the data of such a read are not replaced with empty ones. If the error does not allow completing
an active intent, a new decision is not accepted: the recovery rule of N1.5/N3 applies.
The pass checks the placement and the assignments; `unique`/`ref`/`must_match` of the unit fields are checked
in advance by the units door of P/06.1. This pass does not guarantee a background audit and journaling of a violation of these constraints after
a race of separate writes (P/06.1 N3).

<!-- req: P/04-R032 -->

**Races.** The target of placement/assignment changes only under the turn and through an intent; one cas of a unit row
does not replace the common admission. A break of the turn/store stops the whole changing pass,
not just one unit; the errors of the other independent steps are counted by the usual failures.
The next holder first repairs the unfinished decision, then accepts its own.
A missing manifest_rev is an unreadable current row, not authority to stamp it; all existing turn/intent barriers remain.

### choose(unit) → worker | none

<!-- req: P/04-R033 -->

```
placed (worker ≠ "")                                               → as is; do not reconsider
retire_when (by the acting state with retire_when.state); ends ≠ never and ≤ the clock of the controller → none
live worker, pool, keeper of the place with distinct — the pool contract (common/contracts/pool.md; moved there without a change
      of behaviour, C06-SERVER-POLICY-33-01): live − released slots − the draining, pending and decommissioned servers − (requires: resource ∧
      resource silent) − retiring − number above want − unreadable assignment − (distinct: all except the keeper of the place)
eligible = pool ∩ constraint ∩ spread_by ∩ affinity ∩ (the group is already at a worker → only it)
            ∩ (the worker holds an exclusive place → only the units bound to it; N1.3 affinity.exclusive)
a group of several waiting: eligible ∩ {admits all ∧ free ≥ Σ of the weights}; empty → wait, tell
order: home → preference → all; home — among the eligible (N1.3 home): the holder of the named place, no holder — the workers
         of the server of this place; the holder lacks free room — the rank is empty, the server of the home does not replace it;
         preference — one rank: a worker beside the neighbour (near) or on the server
         of a non-binding affinity row (N1.3) — either of the two, both at once do not raise the rank (journal of cammeta-go, lesson 4 № 4);
         inside a rank — free = capacity − load with the reserves of N1.5,
         free ≥ the weight of the unit ∧ strictly more than the former best; equality — the first by name (ASCII, P/03.2 N1.4)
found → accept and complete a decision for the unit or the whole group by N3 above;
         already placed while the turn was being got → do not accept the former choice, a fresh look
none  → the row is not written (or reason, why), the unit is in unplaced; heavier than any — into unplaceable with words
```

<!-- req: P/04-R034 -->

If the decommission mark `<sub>/decommissioned/<s>` of the subsystem named by `about.sub`, `near.sub` or `ref` of the unit being placed
does not read, then the server `s` is not confirmed for this placement: it is not a candidate, an error of the step (failures + 1), the reason goes into the journal;
it is counted neither as decommissioned nor as not decommissioned (V7 item 3, the Architect's decision of 2026-10-28, on a proposal; line 7 of the list).

<!-- req: P/04-R035 -->

**Reason** (for a human; it MUST be non-empty; it SHOULD follow the grammar): `most free capacity (<free>) among <n> worker(s)` — `<n>` is the number of the eligible (after the filters), not of all live ones + `; weight <w>` — only for a manifest with `placement.weight` + ` reaching <labels>` + `; on <server>` + `, whose resource is <state>` + a mark of the choice by the rank of the chosen worker: the home rank — `, at home on <s>`, with `home: near` — `, beside <their ids> holding it`; the neighbour rank — `, beside <their ids> holding it`, and if a home is declared but its rank is empty — also ` (home <s> has no room)`; the rank «all» with `near` whose server is not chosen — `, away from <their ids> on <neighbour's server> (no room there)`, and with a declared `home`, except `home: near`, outside the home — also `; away from home <s>`; `<s>` of the home marks is what the home is named by: the place of the holder or the server. Leaving: `slot <name> released`, `slot <name> capture did not finish`, `resource on <s> silent`, `server <s> draining`, `server <s> decommissioned`, `<w> holds no <place_by> now`, `<w>'s <place_by> <place> admits no unit` (`<place_by>` is the name of the field `placement.place_by`, `<place>` is the id of the place of the worker: `w-1 holds no shard now`, `w-1's shard s3 admits no unit`; C04-LEAVING-PLACE-WORD-01). Reachability: `<s> no longer reaches <label>; …` / `; nothing live reaches it`. Group: `with <id>, one <group_by>: <why>; on <s>`. Deleted: `deleted`.

<!-- req: P/04-R036 -->

**Materialization and sync.** They use the same intent and turn. Even if the correct decision
already exists, the repair first fixes it for the unit/group, removes the former assignments and completes
one target. There is no partial addition by the snapshot of the start of the pass. The only guard of the target
write is the turn version; the stability of the decision is ensured by the exclusive ownership of the turn,
the fresh check and the intent that is unchangeable until completion. This replaces the former guard of a separate placement.

### move(unit, from, to) → ok | already moved

<!-- req: P/04-R037 -->

```
1. the turn of the current pass is mine and confirmed; outside a pass first get it;
   re-capturing an already held turn is not needed; complete the former active intent;
   freshly read the effective placement;
   worker != from → Moved, do not touch; for a group check all members and the common target
2. check to by all constraints and the free capacity with the reserves;
   accept an intent for the whole unit/group and complete it by steps 2–6 above
```

<!-- req: P/04-R038 -->

**Races.** A was delayed after the decision w-2, B got the turn and completed it, then moved the unit to w-3.
Each late write of A has an old guard turn and is refused. It can neither add to w-2
nor remove from the already new w-3. If A managed to add before the capture by B, B sees the assignment at the fresh
removal. One unit never gets two assignments; for a group all old assignments are removed before the addition of the new target.
A moment without an assignment and a lag of directory remain admissible.

<!-- req: P/04-R039 -->

In all branches hung/unsure/wait, HUNG_MOVE_AFTER is counted from the first observation
by this judge of an unchanged slot version (age 0), not from until, the end of SLOT_TERM or the entry
into the fate. The diagnostic fates.since does not carry this term. A new judge starts the observation anew.

### fate(slot) → fate — by the clock of the controller

<!-- req: P/04-R040 -->

The ordered decision machine is [forms/slot-fate.tsv](../forms/slot-fate.tsv). Its typed inputs are the observations of this judge, not the writer's `until`. The first matching rule wins. It returns the fate and, when allowed, the exact judgement version for `names_given`. The release branch calls [forms/slot-release.tsv](../forms/slot-release.tsv): only its confirmed CAS answer can publish the post-release version. A `-` action is YOURS at its anchor; it must not be skipped. The write, abandoned-capture cleanup and permission rules remain below.

<!-- req: P/04-R041 -->

```
write release: write the slot released (cas),
                                                                                   keep holder/until/gen/server; a torn one —
                                                                                   wholly released and nobody's, keeping a readable gen and writing until as zero Time in the existing writer notation, never now;
                                                                                   keep server only if readable by the current slot field schema; otherwise omit the field, with no empty substitute. No liveness or registry check;
                                                                                   if gen does not read — do not change the row, do not issue
                                                                                   a permission for the capture (P/03.2 N1.4)
abandoned capture: released = "taking", the version unchanged ≥ SLOT_TERM on the clock of the controller (the capturer died between the writes
                   of P/03.2 N3 «capture» steps 3 and 4) → remove the rows under the slot: the contributions <sub>/<from>/<slot> of each book of the manifest
                   with a from family (P/03.7 N1.2) by a batch with guards by <sub>/slots/<slot> with the version of this judgement, do not write the slot;
                   no row — skip; a guard refusal (412 guard, 409 conflict) — a live capture changed the version: do not repeat;
                   with a server decommission and without: an abandoned capture carries the server of the capturer, step 2 of «decommission_server» by server = s does
                   not recognise it, and an orphan under taking would keep the contribution stale forever (ADR-0113 addendum (49), (50))
names_given[name] = the version of the slot row at which the name is taken: for move, hung_moved, unsure_moved and wait ≥ HUNG_MOVE_AFTER —
                   the version at the moment of the judgement (the controller does not write the row); for release — the version AFTER the write of the release (the answer
                   of this write): the released slot is taken by it, and as a «free» one it is also a candidate (P/03.2 N3 «capture» step 2c)
```

<!-- req: P/04-R042 -->

An unreadable gen of an existing slot is not replaced with zero on release;
such a row is kept and is not included in names_given until the generation is recovered. A reassignment
of units by fate does not mean a permission to rewrite a damaged generation of the slot.

<!-- req: P/04-R043 -->

**Transitions of `release` (ADR-0080 addendum 12).** The branch `release` is reachable by the row «gone without assigned units»:
a live resource tells about a process with one of `runs`, `gone`, `unlisted`, `unknown` (P/05 N1.4; `silent` is a state of the resource,
not a presence), and the higher-priority rules still run first. The two closing rows are reachable when server/slot are known,
the slot version has been observed unchanged for at least SLOT_TERM + LOST_AFTER, worker freshness is not confirmed, and resource_state
is unknown: with assignments select move, without assignments enter the release procedure. This uses the existing closing-row policy, not the
unreachable-resource delay of the effective HUNG_MOVE_AFTER; unknown is not evidence of either silence or unreachability (review P/04 M1).

<!-- req: P/04-R044 -->

The transition selector is [forms/slot-release.tsv](../forms/slot-release.tsv). It receives the fate selected above; the CAS action is YOURS, then a confirmed reply or conflict is delivered to the machine. The five original witnesses remain covered: gone without units, a competing renewal, gone with units, unlisted without units and runs without units. A competing renewal refuses the release, and the next pass judges the changed version as `alive`.

<!-- req: P/04-R045 -->

The order of the rules is normative: more definite knowledge before less definite; the margin before the judgements. The controller does not write the slot at any outcome except `release` and the server decommission, and it removes the rows under an abandoned capture (above; ADR-0113 addendum (50)).

<!-- req: P/04-R046 -->

**Races.** The holder renewed the slot between the judgement and the capture of the name by a new process: `names_given` is bound to the version, a capture with `cas` by it will not pass — the name stays. Two controllers can have different observation histories and therefore different judgements (ADR-0049); each uses its own version age by P/03.2 N1.4. The `release` writes go with `cas` of the read version, so two decisions do not overwrite a renewal or someone else's capture. A shift of the writer clock with the same observation history does not change the fate.

### leaving(worker) → reason | none

<!-- req: P/04-R047 -->

The first of: the slot is released (released = true — at once); an abandoned capture (released = taking, the version unchanged for SLOT_TERM on the clock of the controller — the capturer died between the writes; earlier — not leaving, the capture will finish; added by the Quint pilot, F2); the resource of the server is silent — only with `requires: resource` and a live worker (the pool contract): it works, but its units need a resource that is absent; it does not hold a place (`distinct`); the place does not admit; the server is draining; the server is decommissioned; an outcome from MOVED_FATES — its `why`. The units of a leaving worker — a move (step 6) by the rules of the choice; a group whole, or it stays with the alarm `units.left_on_leaving`; the placement row is not cleared until a new place is found, except for a released slot and an abandoned capture: their units that nobody can take are removed by the write `worker: ""`, the reason `slot <w> released; nothing live can take it` (`slot <w> capture did not finish; nothing live can take it`) (the worker has gone forever, a row with its name would say «placed»; acceptance P/03.4, sc. 03). A silence of the store moves nothing. Without `requires: resource` a silence of the resource does not count as leaving, and a worker silent together with the resource leaves only by fate: the units are carried by its outcome `move`, SLOT_TERM + LOST_AFTER of observation of an unchanged slot version (N3 «fate», [P/03.2-08](../../03-worker/spec/03.2-worker.norms.md); the Architect's decision of 2026-10-31, stage 2 of the plan of the group scenarios).

<!-- req: P/04-R048 -->

**Races.** Leaving and a revived worker: the decision is by the snapshot of the pass; a worker that returned after the move reads an assignment without the unit and stops it (P/03.3 N3 «loop()», step 2: the carried one is not in the assignment → `stop_unit`); the move is not rolled back.

### shortage(), order(), withdraw the order, shrink() — with grows: true

<!-- req: P/04-R049 -->

The role grows on demand: the controller orders the number of processes of the role on a specific server with the row
`<sub>/want/<host>`, the server script brings the number of processes to it (P/02.4 N1.5); the controller does not start processes
(ADR-0021, ADR-0084 and addendum (1)).

<!-- req: P/04-R050 -->

```
order row:    on every server where the role is installed and neither pending nor finally decommissioned (the door row has room.<sub>, N1.1) — the row
              <sub>/want/<host>; none — create want 1 by a write with cas "" and guard of the own version of placement_turn
placeable = readable live unit rows, excluding deleted/tombstoned rows and every unit removed by ends or retire_when in step 4;
            a manual expired row may remain in the store, but it is outside this set. Apply this same set before grouping or weighing.
waiting = placeable ∩ (units without a placement ∪ units of the leaving ∪ out of reach); a group is one piece.
          Only these waiting units feed shortage, growth, the no-shortage timer and shrinking; retained expired rows and garbled rows
          neither cause an order nor delay shrinking (the Architect decision on ADR-0127, review P/04 C3).
live(s) = the live role processes of the server s (a live worker of N3 «choose»), including the base <prefix>-<s>-1 and the shrink victim
          (retiring): for «in flight» and «failed to raise» the victim is a live process, want includes it while it is alive; it is excluded
          from the placement pool (shrink); the number n of the name — as an integer (P/03.2 N1.4) (ADR-0084; cammeta-go M10-04 № 6)
in flight(s) = the count of the numbers 2…want(s) that have no live role process of the server s (by heartbeats, live(s)) — ordered
          and not yet raised, until the order is withdrawn on deadline; the base <prefix>-<s>-1 is not ordered and is never in flight;
          by heartbeats — for needed, the order of candidates (review of stage B 3–5, № 16), the shrink condition, the withdrawal on deadline
          and wants.<s>.pending; the candidate and the share — by the door
          (free(s) below); with consecutive numbers — max(0, want(s) − live(s)) (ADR-0084 addendum (2) R13, addendum (3) R13′)
no_base:         the base <prefix>-<s>-1 is dead — wants.<s>.state no_base, an alarm; the server is not a candidate (R6); the base is never
                 in flight, therefore it does not hold back the shrinking of the role on other servers (ADR-0084 addendum (2) R13)
free(s) = room.<sub>(s) − |{2…want(s)} ∖ live.<sub>(s)| — by the door row platform/doors/<s> of one snapshot
          (P/05 N1.4 door_row): live.<sub> — the numbers n ≥ 2 of the live presence locks by which room.<sub> was counted;
          it is counted once per pass before the loop over the sets and decreases with every share (order); no live.<sub> or it
          does not read — the server is not a candidate (ADR-0084 addendum (3) R14′)
set order:       a worker or a server that suits several label sets gives its capacity (free of the worker),
                 free(s) of the server and in flight to the sets in turn — in the UTF-8 byte order of the canonical notation of the set
                 (unique labels ascending, comma-separated, a repeat collapses — a label set is a set;
                 the empty set first; ADR-0084 addendum (2) R21); each unit of capacity, of free(s) and of in flight
                 is spent by one set once; a set takes the free, free(s) and in flight only up to its own
                 need (min): the in flight taken by a set — min(Σ in flight, processes) (R18), the remainder — to the next set
                 (ADR-0084; cammeta-go M10-04 № 7; stage A, A6)
per label set:   the capacity of a worker without a named one — placement.capacity.default (N1.3); a named 0 is not replaced with default
                 (ADR-0084 addendum (2) R19, addendum (3) R19′);
                 per = the smallest positive capacity over all suitable live workers, named or default;
                 none such → placement.capacity.default, if it is > 0;
                 no positive default either → no order for the set, withheld: "no positive capacity estimate";
                 the element of the set of the vector `order` has the same fields as a computed one: per: null, processes, in flight, needed,
                 withheld — zeros, plus why (ADR-0084 addendum (2) R20); in the pass report — an element short[] of N1.2 (workers: 0,
                 withheld — words) (review of stage B 3–5, № 15)
                 (still show the shortage of weight and of groups, workers: 0; with this withheld, zero means
                 the absence of a computable estimate, not the absence of a shortage; this is not an error of the step)
                 otherwise needed = max(0, processes − Σ in flight(s) of the suitable servers), where processes = ceil(max(0,
                 Σ of the weights of the waiting − free at the suitable live) / per) + one per group that has no room anywhere:
                 the capacity in flight is subtracted from the growth by groups too, otherwise the same growth would be ordered by every
                 pass (ADR-0084 R2; cammeta-go M10-04 № 5)
                 an exclusive place (N1.3 affinity.exclusive): the capacity of the worker holding it does not enter free for the other
                 units; waiting units bound to a place without a holder — an order for the place: the server of the place (server_field
                 of the row) is a candidate out of order, share 1; an empty server_field — no order, the place waits for a holder; a place
                 whose secret did not open — no order, withheld «<place_by> <place> is sealed»: the controller learns Sealed from
                 place_error.<place> = sealed in the heartbeats of the live workers of the role on the server of the place (P/03.4 N1.1); there are no live workers
                 there — one ordinary order (ADR-0091 addendum (9) item 6, addendum (10) items 1–3; repeated review of addendum (10))
                 a place without a holder: for a manifest with places.wanted the row of the table of places passes places.where, its hold does not act, and the row
                 <sub>/<wanted>/<place> exists and reads — an order for the place, a waiting piece of weight 1: the place may wait for neither a record nor a unit,
                 and without a holder nobody reads its archive. The server is from the row of the place, as for an exclusive place: server_field non-empty — this server is a candidate out of
                 order, share 1, on top of the general check of the candidate; not fit — no order, the place waits; Sealed — withheld, as there. server_field empty — the place is on any server: the piece goes
                 with the empty label set as an ordinary probe; a limit: a new process will take the first free place, not necessarily this one, a superfluous process lives until shrinking.
                 The row does not read — there is no reason, a journal line without the value; another empty place gives no order
                 (ADR-0084 R15; C04-PLACE-WANTED-01, the Architect's decision of 2026-11-01, analysis of the VMS invariants)
                 servers: distinct and the place from the heartbeat (place_by is a heartbeat field): free at the suitable live — only at
                 the keepers of places; a candidate for the set — a server on which in flight(s) = 0 (no probe: ordered and not raised;
                 review of stage B 3–5, № 40) and there is no live suitable process without a place; the growth of the set — no more than one probe
                 process per pass: the place of a new process is unknown before its start (R8); on a server no more than one
                 unfinished probe; no candidate or the growth is exhausted — the remainder of needed is withheld with the reason «no free
                 <place_by>» (N4); a probe on one server does not stop the growth on another (ADR-0084 addendum (5) R16‴)
candidate s:     the order row exists; the base <prefix>-<s>-1 is alive (otherwise no_base above: the server is not a candidate, R6);
                 free(s) > 0 (R14′); want(s) < WANT_NUM_MAX (otherwise the reason «<s> has no instance numbers left»,
                 the alarm workers.no_server); the labels of the server suit the set (constraint), requires: resource — the resource
                 is not silent; not draining, not decommission-pending or decommissioned; not «failed to raise» (RAISE_QUIET); servers: distinct — by the place
                 place_by: with place_by: server a server with a live worker of the role is not a candidate, with a heartbeat field the place of a new
                 process is unknown before its start — it does not restrict the choice of the server (R8)
candidate order: smaller live(s) + in flight(s) — by heartbeats (R13′; not by the door), then the server name in UTF-8 bytes (review
                 of stage B 3–5, № 16)
order:           distribute needed of the set over the candidates in order, to each — no more than min(free(s), WANT_NUM_MAX − want(s));
                 for a manifest with a non-empty door.pass.calls the ceiling of want(s) is 1, not WANT_NUM_MAX: a ticket is bound to the sheet of the server, there is one sheet per role and server
                 (the warden and hand-over contract «Pass of the second kind»); the remainder of needed — withheld, as with a lack of candidates;
                 after a share free(s) −= share (R14′); want(s) := want(s) + share — a write of the order row with cas by the read version and guard
                 of the own version of placement_turn, why — the reason «<n> more for <labels> on <s>: <waiting> waiting» (<labels> — the canonical
                 notation of the set; the empty set — any labels, R23);
                 want is the absolute target: a repeated pass and a new holder of the turn recompute needed with the capacity in
                 flight and do not repeat the growth — one acting logical order per piece of shortage (label set);
                 no candidates — the remainder of needed of the set is withheld: the number of processes in the series workers_withheld{labels} (P/06.5),
                 the words — in short.withheld of the report (N1.2), the alarm workers.no_server {server, labels, want, why} (stage A,
                 A6)
                 the competition of subsystems for the last room of a server (room of different roles) is an admissible delay;
                 the common memory ceiling of a server over all roles is a limit of the scheme (R12)
withdraw on deadline: in flight(s) > 0 for longer than WANT_GRACE (N1.4 terms) → want(s) := 1 + |live numbers ∩ {2…want(s)}|; the script
                 then renumbers: it stops a number above want, starts a missing one below; stopping a worker with
                 an assignment is a move of the units (ADR-0084 item 7; ADR-0084 addendum (4) R27);
                 the server «failed to raise» for RAISE_QUIET, raise_failed.<s>.times + 1, the alarm workers.raise_failed
                 {server, labels, want, why}; after RAISE_FAILS_LOUD in a row — of raised severity; it is removed when
                 the server raised the order; the shortage is ordered on the next candidate in the same pass; the base does not count
                 toward «failed to raise» (R6)
number above want: a live role process of the server s (the name and the number N — the slot name contract, «Role process name and its number»; not a role
                 process — the rule does not apply) with a number greater than want(s) (raised after the withdrawal of the order, a shrink victim before its stop, a remainder
                 of a door race) — not in the pool (as retiring) and gets no units; the server script stops it
                 (P/02.4 N1.5 rules 3); the controller does not raise want(s) (ADR-0084 addendum (4) R28 instead of R25)
```

<!-- req: P/04-R051 -->

```
shrink (step 9a):
  condition: the set has had no shortage for longer than SHRINK_AFTER (from the first pass without a shortage, N1.4 terms), there is no in flight (by
             heartbeats, R13′), and after the move of the units of the victim the remaining suitable live ones have free ≥ per (hysteresis,
             R3); «no shortage» — there are no waiting: with servers: distinct the live ones without a place are not shrunk while there are waiting
             (ADR-0084 addendum (3) R16′, addendum (5) R16‴);
             the reason for not shrinking — the first that fires in order: no victim (no_victim: no eligible live top, including only base ones, a number above
             want is not in the pool, R28), live ones without a place while there are waiting (placeless_with_waiting), there is a shortage or the hold time has not
             passed (no_shortage_long_enough), in flight (in_flight), hysteresis (hysteresis; no per — too); the words and
             the cases — the vector shrink-allowed (the Architect's decision of 2026-10-20, № 12 of the review analysis of stage B 3–5)
  victim:    only a live worker with n = want(s) > 1 of its server s is a candidate; select the largest eligible n (as an integer); a live number above want(s) is not
             a victim: the script stops it (R28), the end of shrinking does not extinguish it (ADR-0084 addendum (6); review
             of stage B 6–7, № 42); on equal numbers on different servers — the smaller name
             of the server in UTF-8 bytes first, as the order of candidates (stage A, A6); each of its units
             (a group — whole) passes choose(unit) on the pool without the victim; otherwise do not shrink, the reason is in the report
  wanted:    only the top ordered number n = want(s) of a server may be a victim. If that worker holds a place with a readable row of places.wanted, skip the entire server and consider the top candidate of another server, with the same number/server ordering. Never fall back to a lower number on that server: reducing want would stop its protected top process. A removed wanted place would at once order a process (C04-PLACE-WANTED-01; the Architect decision on ADR-0127, review P/04 C1).
  retiring:  write retiring = <victim> into the order row of its server (cas, guard turn); the victim is outside the pool of all steps
             (choose, move, home, reachability), and at a new holder of the turn — by the row; one victim per role at a time;
             in live(s) for «in flight» and «failed to raise» it stays while it is alive (cammeta-go M10-04 № 6)
  move:      no more than SHRINK_BUDGET units per pass, the reason «<w> is retiring: the role shrinks on <s>»; the first
             indivisible group goes even beyond the budget (as reachability, step 5)
  end:       the assignment of the victim is empty → want := want − 1 (not below 1) and retiring removed — by one write; the server script
             stops the process with the largest n (P/02.4 N1.5) — this is the victim: there is no in flight (the condition), the numbers
             2…want(s) are alive, and the victim is the number want(s) (ADR-0084 addendum (6))
  cancel:    the shortage returned before the end → retiring removed, the victim is in the pool again
drain:       a server in platform/drain gets no new orders; its additional processes are shrunk one by one
             without the hold time and hysteresis (the units leave anyway, «server <s> draining»), want − 1 with an empty assignment
             of the victim, down to 1 (R7)
decommission: step 2 — accepting pending deletes the order row with cas and turn/request guards; pending/final servers get no new orders (R7)
```

<!-- req: P/04-R052 -->

**Races.** Two controllers write one order row: cas by the version and the guard `placement_turn` let one pass, the second
re-reads and recomputes from the absolute target. The order has no separate kind of record in `placement_intent`: the absolute
target under cas with the guard `placement_turn` and the capacity in flight close a repeat of the growth — a repeated pass and a new
controller complete the target, they do not add to it (ADR-0084 addendum (1) R2). The order against the script: the script reads the row once a minute (P/02.4 N1.5) and
lags — a process raised after the withdrawal of the order, with a number above want, is not in the pool and is stopped by the script (R28); a process
stopped by the script with a non-empty assignment (a desync) releases the slot in the regular way (P/03.4 N3 «stop by SIGTERM»; ADR-0084 item 7) —
this is a move, not a loss of units. Shrinking and a change of the turn holder: `retiring` is in the row, the new holder continues
the move and does not choose a new victim. The door against the heartbeats: the candidate and the share are counted by `live.<sub>` of the door, the shortage — by heartbeats; the remainder of the race is
a process with a number greater than want, raised after the door mark, for no longer than the mark period (ALIVE_EVERY): it is caught by the memory check
of the workers script (P/02.4 N1.5, the ceiling by memory) (ADR-0084 addendum (3) R14′).

<!-- req: P/04-R053 -->

**The probe process with `distinct` (R16‴).** A worker without a place carries no units and does not leave for another server: a place on its
server is freed only by the leaving of the keeper (R8 does not change), until then it stays idle. A new process, until its first heartbeat
with a taken place, carries the place `""` and in this window is a live one without a place: its server is not a candidate in this window; while it is ordered and not
raised — too (a probe in flight); a delayed start does not give the server a second probe; the other servers of the set are candidates, with
one probe process per pass (ADR-0084 addendum (3) R16′, addendum (5) R16‴; review of stage A 3–5, № 13).

### decommission_server(s) — a console request, executed by the controller

<!-- req: P/04-R054 -->

```
console: request, 409 server answers, platform/decommission/<host>, door deletion and withdrawal remain P/06.6 N3.
existing valid final mark and standing request: do not rewrite the mark, its slots or remaining contributions; no new cleanup is authorized.
0. Resume a readable pending row before admitting a new plan. Its fixed request_index must still be the current request.
   Before mutation validate the progress invariants: remaining names are distinct and disjoint from released/skipped;
   released and skipped are disjoint; current is an ordered subset of released. In cleaning, slot_cursor < len(current)
   and from_cursor <= len(from); every from prefix belongs to this subsystem. The from list is frozen at acceptance from
   the declared owned books, never rebuilt from a later manifest. A malformed progress plan is a step error: keep it,
   do not infer completion, release/delete anything or replace it with a fresh plan. Schema readability alone is insufficient.
   No pending/final row: the server is heard by the ordinary observation rule -> leave the request standing, no mutation;
   otherwise completely read the request, owned slots and required metadata. An incomplete/unreadable source is not an empty list.
   Fix the original readable slots with server = s as ordered {name,index}, the owned from prefixes, asked_at, manifest_rev,
   units/holds metadata. Preflight every full key, the largest reachable serialized progress row and final mark, row weights,
   and real batch-body ceiling. Reserve the P/01 wire index width for cleanup_index; never parse an opaque version.
   An unrepresentable plan is a step error before any slot/order change, not a partial final mark.
1. Accept pending with cas "" and delete an existing want row with its read cas in one conditional batch. Guards: the own
   placement_turn version and the fixed request_index. Count both writes. State prepared has remaining candidates; no candidates
   means finalizing. The pending server is outside the placement pool and gets no new orders/automatic want-row creation.
   After acceptance continue only this frozen plan, also after a break or a later server answer; never add/adopt a new holder.
2. Prepared: read each next candidate only to confirm its original index and obtain the unchanged readable slot items.
   A different index (including absence) is obsolete: move its name to skipped, never substitute the new version for release.
   A non-answer postpones the step; it is not obsolescence. Keep holder/gen/server/until, set released = "true"; never invent gen.
   Write up to BATCH_WRITES - 1 slots with their original cas plus pending with its read cas, guarded by turn and request.
   Atomically record their names in released/current and enter cleaning; the one returned batch index is the version of ALL
   those released slots AND pending. After a lost answer, a cleaning row with empty cleanup_index carries that exact release
   index as its own row index: no slot reread is needed. With no from families, the same batch advances directly to prepared
   or finalizing with empty current/cursors. A refused release batch changes neither slots nor progress: barrier/re-read pending;
   only discard candidates proved to have changed from their planned index, never retry a release against a newer slot version.
   Persist skipped candidates under pending cas and turn/request guards; if none remain, advance directly to finalizing.
3. Cleaning: process one current slot at a time, from prefixes in their fixed order, split across bounded batches.
   Derive its authority from cleanup_index when non-empty, otherwise the current pending row index. Before ANY progress rewrite
   preserve that exact authority in cleanup_index; a later pending index must not replace it. Delete existing contribution rows
   by their read cas plus pending progress in one batch, guarded by turn, the fixed request and this slot's exact release index.
   Count all deletes AND progress/service writes, all guards, row weights and the full body. No guard key is also a written key.
   A confirmed missing contribution advances the cursor; an unknown read does not. A 409 conflict or 412 guard discards ALL
   remaining removals for this slot, with no new slot read/retry. Record cursor advancement under turn/request guards; never
   delete a new holder's contribution. Only confirmed cursor progress allows the next slot, then the next release chunk.
   On finishing a slot, advance slot_cursor and reset from_cursor. On finishing the whole current chunk, clear current,
   cleanup_index and both cursors, and set prepared if remaining is non-empty, otherwise finalizing, in a guarded progress write.
4. Every prepared/cleanup/final batch fits BATCH_WRITES, BATCH_GUARDS and the actual body ceiling. If even one indivisible
   operation plus required service writes cannot fit, record a step error and keep progress, never publish completion.
   Renew the turn by the ordinary rule; an unknown write or lost turn stops further mutation behind the existing barrier.
   A new holder re-reads pending after taking the turn and resumes its recorded phase, never restarts releases from slot names.
5. Only after remaining is empty and the current chunk's eligible removals are confirmed or conservatively discarded, enter
   finalizing. Atomically write the absent final <sub>/decommissioned/<host> mark from released/units/holds and asked_at (at = now),
   delete pending by cas, and delete a remaining want by cas if necessary, with turn/request guards. Count EVERY service write.
   The final mark is the LAST atomic step, never plan acceptance or merely the first released chunk. A failed/unknown final
   batch proves no completion: use the barrier and confirm the actual pending/final state before continuing.
6. A withdrawn/replaced request cancels its old pending row with cas and guards proving the current request state and own turn;
   it does not roll back confirmed releases/deletes, invent a final mark, or authorize an old delayed batch for a new request.
   Withdrawal removes an existing final mark as before. The resource publishes its door again; contributions return by normal
   start/capture cleanup, not by rollback. A new request requires a new admission and fresh plan.
```

<!-- req: P/04-R055 -->

The console side (the refusal 409 `server answers` by [the observation contract](../../common/contracts/observation.md), the write of
the request, the delete of the door row, the withdrawal) is [chapter P/06.6](../../06-console/spec/06.6-console.norms.md) N3
«decommission_server(s) — the console side» (review of stage A 6–7, № 2); here — the execution by the controller.

<!-- req: P/04-R056 -->

**Races.** The decommission of a server and the return of its workers: `decommissioned/*` is written with `cas`; a worker of this server checks the decommission at the capture (P/03.2 N3 «start()», step 3: `platform/decommission/<s>` or `<sub>/decommissioned/<s>`) and does not take the name; the console request and the pass of the controller are separated by a row — a repeat of the request is idempotent.

### manifest_rev — the rule guard

<!-- req: P/04-R057 -->

```
before every write of a placement row (place, move, remove): a missing manifest_rev is unreadable, never stamped;
row.manifest_rev > my revision
                                                                       → do not touch; the row — into manifest_behind
manifest_behind (N1.2): the number of rows of this pass whose write is postponed because of a lagging manifest; each row —
                        once per pass, however many write attempts touched it (C04-MANIFEST-BEHIND-COUNT-01)
```

---

<!-- req: P/04-R058 -->

**Races.** A change of the manifest during a pass: `rev` is read once per pass, the decisions are written with this `manifest_rev`; the controller sees a change of `rev` by the mark check (P/02.3) and stops with code 0; a new instance with the new `rev` re-reads everything; a row with a former `manifest_rev` is a snapshot of a decision, not a rule.

### controller start — schema check

<!-- req: P/04-R059 -->

The environment and the launcher argument are inventoried in [forms/daemon-flags.tsv](../forms/daemon-flags.tsv). Derived defaults and imported checks remain the linked contract rules; no CLI flags are added.

<!-- req: P/04-R060 -->

The current controller start check uses the common block of [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «console start — schema check». The platform/schema row, SCHEMA and its raise remain P/06.6 N1.1a, N3 «raise_schema».

<!-- req: P/04-R061 -->

```
start: the schema contract «Check at start» ([the schema contract](../../common/contracts/schema.md); moved there without a change; layout audit A-02, the Architect's decision of 2026-10-25)
```

### table snapshot — after the unit snapshot, before the final report

<!-- req: P/04-R062 -->

```
for each table from domain.view_tables of the manifest: the rows of the table → rows by N1.3b, the order — key;
a row whose field does not read by its type — skip, the counter snapshot_rows_garbled;
rows equal to those this process has already written — do not write, ts is the former one;
serialize; more than SNAPSHOT_TABLE_MAX → write the stub of N1.3b ceiling, snapshot_tables_refused + 1, a log line once per series;
an error reading a table — do not write the object, a log line once per series: an empty object is not published instead of an unread one
```

### snapshot — after the control part, before the final report

<!-- req: P/04-R063 -->

```
per worker: the unit rows of its assignment → [{id, revision, the fields of snapshot (address mask), worker, server}];
a row whose snapshot field does not read by its type — skip, a log line once per series and the counter in
`snapshot_rows_garbled` of the pass report (N1.2; N1.3a garbled; reconciliation of python and go M10/6–11, T7);
the unplaced → unplaced; a shard that existed and is not filled → empty; without units → an empty unplaced;
an empty shard — {cluster, worker: null, ts, <rows>: []} (N1.3a; C04-SNAPSHOT-GONE-WORKER-01);
each unit has state by N1.3a (the acting states of the snapshot list); an unreadable state — without it, the counter
snapshot_state_garbled
serialize each shard; check the size by N1.3a before the write; more than L → TooLarge, do not write this shard;
write an admissible shard; TooLarge of the store → the same refusal; a publication error — one log line per series;
TooLarge before the write keeps the former shard and its time; an unknown outcome of a write does not prove that the shard stayed the former one.
On any error do not publish an empty shard instead of unchecked data
```

<!-- req: P/04-R064 -->

**Races.** On one server there is one controller of a manifest; different servers can publish different local copies of one logical shard key. A choice by written does not create a common moment of reading. Rows and shards are published separately: a snapshot is an observed configuration, not a consistent backup. An error reading the rows/list does not allow publishing an empty shard; an error of one write does not roll back the ones already published. A consumer checks revision and does not infer absence from an incomplete set.

### pull the power (do nothing) — a drill

<!-- req: P/04-R065 -->

```
t = 0      the server is off; its daemon — minus a vote; its heartbeats and its door stop changing
about 45 s the controllers with already known heartbeats: the slots expire; the resource is silent; the tolerances of N3
SLOT_TERM + LOST_AFTER with all the tolerances of N3 and free capacity → move; a new epoch. With unknown/unavailability/lack
           of room there is no common term; the archive stays on the volume. The neighbours have only confirmed mirror copies
return     the daemon restarts with the saved member.json (does not repeat join); the resource pulls the buckets (restore); the workers take free names; names with expired
           slots — by the word of the controller; nothing moves back, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)
```

<!-- req: P/04-R066 -->

**Races.** The failure coincides with a renewal, a write and mirroring; the boundaries are this lesson, [P/03.2](../../03-worker/spec/03.2-worker.norms.md), [P/05](../../05-resource/spec/05-resource.norms.md). The absence of operator actions does not turn an observation into a snapshot. The terms given are the profile of the drill, not a guarantee for an arbitrary failure (from M10/11 N3, the move of lesson 6).

---

## N4 Refusals

<!-- req: P/04-R067 -->

The refusals of the console doors (the policy, the drain, the labels, the server decommission, `/where`, the common codes of the console) are [P/06.6](../../06-console/spec/06.6-console.norms.md) N4 and [P/06.5](../../06-console/spec/06.5-console.norms.md) N4.
The row «an intent row out of the form of N1.5» is given here whole: 503 at the reader doors of the console, failures at the controller.

<!-- req: P/04-R068 -->

The closed catalogue is [forms/refusals.tsv](../forms/refusals.tsv), `chapter = 4`. Columns `cause`, `outcome`, `diagnostic`, `caller` preserve the four original cells in source order; fixed machine codes supplement them. `peer` refers to the console contract, not a controller HTTP API.

---

## N5 Acceptance

The directory [`../acceptance/`](../acceptance/README.md): a stand of the workers and the controller of `testsub` and `testsub2` of the implementation under
the control of the runner on a catalogue of two manifests ([the common README of the acceptance](../../common/acceptance/README.md), section «Stand»);
sc. 12, 14–17 — with the resource P/05 on the server of the controller (review of stage B 3–5, № 17); the rows are read through the store door P/01.1, the console doors
(`/where`, `/unplaceable`, `/servers`, `/metrics`) and the pass report object through the resource door. The numbers of the scenarios and steps are
the former numbers of the acceptance of M10/05, except the steps of sc. 11 (the former 4–9 are 7–12, the preparation of the shelf), the first step `@start resource` of sc. 07, 11, 13 (P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27), the new sc. 17 (review
of stage B 3–5, № 17), steps 15–19 of sc. 18 and the new sc. 20–27 (coverage audit of P/04, 2026-10-30; sc. 25 — `@cut role`/`@mend role`, sc. 26, 27 — `@freeze`/`@thaw`) and sc. 28–42 (the second pass of the coverage audit of P/04, Gemini, G01–G07); sc. 03, 08 (snapshot) — from the acceptance of M10/10, without the steps `/metrics` of the console (the reader side of
the snapshot is [chapter 6.5](../../06-console/spec/06.5-console.norms.md); review of stage A 6–7, № 32). In total 37 scenarios /
533 steps (sc. 18, 19 — ADR-0091; sc. 20–27 — the coverage audit of P/04; sc. 28–42 — its second pass; sc. 43, 44 — C04-HOME-PLACE-HOLDER-01).

Detailed case descriptions and their expected outcomes are recorded in [judge-only N5 coverage](04-controller.n5.cases.md). Governing rules and the public acceptance scope remain in this chapter.

The console doors without workers (a unit without a worker, `/unplaceable`, the policy, the drain, the labels, the server decommission) — sc. 01–07
[of the acceptance of P/06.6](../../06-console/acceptance/6/README.md). The snapshot — sc. 03 and 08; the age of a shard and a spoiled shard in
`/metrics` of the console — the acceptance of [P/06.5](../../06-console/acceptance/5/README.md); the shards of a gone worker — N3 «snapshot»:
an empty shard — sc. 40, the size of a shard with `ts` — N1.3a `ceiling` — by reading. A server failure
(N1.4a) — drill 05 of [the system acceptance](../../common/acceptance/system/README.md), sc. `09-resource-door` [of the acceptance of
P/05](../../05-resource/acceptance/README.md) (from M10/11 sc. 01) and sc. `14-resource-silent` (from M10/11 sc. 02) of the acceptance of
[P/06.5](../../06-console/acceptance/5/README.md). The start refusal by the schema — N3 «controller start — schema check»: `version` above SCHEMA and not a number, code 2 — sc. 23;
a read error — wait — sc. 25; «before the manifest is read» — by reading. The vectors [`order`](../vectors/order/README.md) (the shortage of a label set and the order over
the servers), [`shrink-victim`](../vectors/shrink-victim/README.md) (the shrink victim) and [`shrink-allowed`](../vectors/shrink-allowed/README.md)
(whether shrinking is allowed and the order of the refusal reasons; the Architect's decision of 2026-10-20, № 12 of the review analysis of stage B 3–5) — N3 «shortage(), order()…»,
«shrink».

Checked by reading and on the stand (workers with heartbeats are needed — sc. 02-unit of the acceptance of P/03.3, 03-sigterm — P/03.4, 05-sigkill — P/03.2; the stand of the system acceptance): the choice of a worker and the reason; the group whole (except «room for all or all wait» on one worker — sc. 22); the weight and the free capacity; `distinct` and the keeper of the place; the spread, the neighbourhood, the home, the affinity (except the spread by a non-empty zone, binding shelves, a move home and `admits: false` — sc. 36–39, the home at the holder with two places of a server — sc. 43, on a place without a server — sc. 44); the slot fate by each rule and `names_given` with the version (except the release of a slot without units and the write release by
the slot row — sc. 21; the margin and `hung` of a live silent worker with a unit and without — sc. 26, 27; `wait` before HUNG_MOVE_AFTER — sc. 42); the move through intent and the repair `sync` (except the recovery of intent by one holder, `sync` of one assignment and an unreadable intent — sc. 28–30); leaving by each reason (drain — sc. 33, the place does not admit — sc. 39); drain with live workers (except the move and `safe` — sc. 33); decommission with live workers, `gone: true`; a url group without a host (without a value and with an unreadable value, and with them `spread_by: zone` without a value — sc. 11; drain «assignment ∪ `status`» — sc. 07 of the acceptance of P/06.6); `fates` and `since`; presence only from the live heartbeat
of the resource; the order, the withdrawal on deadline, the number above want and shrinking (ADR-0084), except the shrink condition by the input of the pass — with the branch «live ones without a place are not shrunk while there are waiting» with `servers: distinct` (R16′), which sc. 17 does not distinguish from the hysteresis; it is checked by the vector `shrink-allowed` (the Architect's decision of 2026-10-20, № 12 of the review analysis of stage B 3–5); the delete by `delete_after`; `manifest_rev` and `manifest_behind` with two revisions of the manifest (the rows and the turn decided by a newer revision, without a change of the manifest — sc. 31, 32); the pass report.

**ADR-0127 review obligations.** The 50 CALL seams retain the former 33 and add 17 review witnesses. Public obligations cover resource-state/fate handling, top-number and wanted-place protection composed with the P/02 script stop plan, excluded expired manual rows, complete decommission and durable recovery under exact guards, regular-loader name restrictions and progress validation before mutation. They use the existing controller-pass/fate ports and actual IO observations of the forms README, not new commands or kit parts. Detailed named witness inputs and outcomes are judge-only coverage.

Current reader/writer requirements are the data-family source, including the three report counters, one snapshot array, required placement manifest_rev and active nonempty reason. Pending recovery, exact opaque guards and the named current witnesses remain required. Source/schema projections do not prove OS stop, process recovery or runtime acceptance; related generator/runner checks and joint GATE remain separate.

### Evidence outside TSV

Scenarios 01–06 [of the acceptance of P/06.6](../../06-console/acceptance/6/README.md) (from M10/04) observe an empty pool and several refusals; they do not prove the other branches.
«Reading» below means a check of the transitions of the implementation by the owner of the implementation with the given
interventions; in the translation window the author reads only documents and does not claim that code passes.

| Norms | Subject and intervention | What must be shown |
|---|---|---|
| P/04-01…03, 12, 16 | two controllers, a pause/break after each read and write of placement/workers; a newer manifest_rev | cas/guard by own versions, a repeated check by the mutator, the repair sync, the old rule does not write |
| P/04-04, 05 | the first look, a shift of ts, an absence/damage/empty row of labels (a row, an empty and an unreadable row with node labels — on the stand sc. 24) | life by local observation; labels are not guessed on a non-answer |
| P/04-06…09, 18 | two weights, equality, a group, distinct, incompatible constraint/home; the weight of a row `"7x"` and the capacity of a heartbeat `"2x"` | an admissible candidate and a non-empty reason; a preference does not bypass a filter; a spoiled weight — the unit in `garbled` and `unplaceable`, a spoiled capacity — a worker without new units, the reason in the report, not `default` |
| P/04-10, 11 | each fate outcome before/at/after the boundary; a renewal between the judgement and the capture; gen damaged; `gone` without assigned units and with them (without units and the write release — on the stand sc. 21) | the order of the judge, the version of names_given, an unknown generation is not reset; `release` before `move` for a slot without units (the transition table of N3) |
| P/04-13, 14, 15 | all reasons of leaving; an order by two controllers, the withdrawal on deadline, the number above want, shrinking with a change of the turn holder; the count of delete_after | budgets/group, one logical order per piece of shortage, retiring survives the change of holder, the delete by version and local time |
| P/04-17 | a successful/partly refused pass, grows on/off | the required fields of the report, failures, short and wants correspond to the steps performed |
| P/04-20 | a unit whose key `<sub>/placement/<id>` is 1 byte longer than the key limit of the store, with free capacity; the same unit in a group | the intent is not written; the unit is in `unplaceable` with `why`; the other units of the same subsystem are placed |
| P/04-19 | two controllers admit different units with capacity 1; spread_by; a group with different home; a change of holder after each step of intent | one common decision, no overload/split from competition; late writes are cut off by turn; an incomplete transfer is completed before the next admission |

---

## Implementation decides

The implementation is to name in its description:

1. **how the cache and retries implement the fixed sources** — PASS_EVERY, TURN_BUSY_RETRY and WRITE_CONFLICT_LIMIT are norms in forms/runtime-constants.tsv, not discretionary values;
2. **the cache between passes** — what is held by the row version, and how this does not change the decisions (the rows decide, not the cache);
3. **how the resource of a server reports the presence of a process** (the form of the field `workers` of the resource heartbeat — P/05 N1.4) and the presence lock ([the presence lock contract](../../common/contracts/presence-lock.md));
4. **how the effective inputs are read** — channel and defaults are the named source of lifecycle/forms/common contracts, not another local choice;
5. **how rebalancing is requested** and who calls it; the budget;
6. **additional fields of the report** beyond N1.2 and how the metrics are made from it (the series `<sub>_reconcile_*`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — text»);
7. **the exact texts** of reasons and refusals beyond the grammar of N3/N4;
8. **what a manifest without `grows` does** with a shortage (it counts nothing) and where the server script lives (`w2c-workers.sh`, P/02.4 N1.5 `script`);
9. **the command printing the pass report** `<sub>/controller/pass` for the acceptance — by the section «Stand» of the common README of the acceptance.
10. **how the snapshot is published** on a store refusal (a log once per series); the period — after every pass (N1.3a `publish`), there is no choice;
11. ~~**where the `cluster` of the snapshot comes from**~~ — normed: `CLUSTER` of the environment (N1.3a; P/02.4 N1.2), not set — `local`.

---

## Readiness checklist

An implementation conforms to the lesson when every norm is fulfilled; a norm id `P/04-MM` is what the decision deltas,
findings and window records refer to (ADR-0080 addendum 6):

- [ ] **P/04-01** the effective decision is the active intent for members, otherwise placement; the assignment is derived; `rev` grows; `sync` repairs a broken one — sc. 01 [of the acceptance of P/06.6](../../06-console/acceptance/6/README.md); the recovery of an active intent by a new holder — sc. 28, `sync` of one assignment and `diverged` — sc. 29, an unreadable intent at the controller — sc. 30 [of the lesson acceptance](../acceptance/README.md); a double read of intent and a break in the middle of completion — checked by reading
- [ ] **P/04-02** decisions and an unfinished intent are kept in the store; every write is with `cas`; placement changes go through the common turn with CAS/guard by N1.5/N3; the local observation history starts anew after a restart and does not replace reading the decision — a restart of the controller: the decision and the epoch are the former ones, the new instance places — sc. 20 [of the lesson acceptance](../acceptance/README.md); an unfinished intent from the store is completed by a new holder — sc. 28; the rest is checked by reading
- [ ] **P/04-03** the order of the pass of N3 and an attempt per step — checked by reading
- [ ] **P/04-04** the picture of the world: capacity, server, node labels — without a term; life — by a change of the heartbeat within 45 s by the clock of the controller; seen for the first time — has just changed — checked by reading (stand P/03.3, sc. 02-unit; no scenario observes the term of 45 s); the boundary `≤ LOST_AFTER` — the vector [`fresh-age`](../../common/vectors/fresh-age/README.md) (review of stage B 6–7, № 20)
- [ ] **P/04-05** server labels: the row beats the node, an empty one — «reaches nothing», an unreadable one — the last ones and without a judgement; the label alphabet — sc. 05 of the acceptance of P/06.6 (form refusals); the priority of the row over the node, an empty list, an unreadable row — sc. 24 [of the lesson acceptance](../acceptance/README.md) (the stand of the acceptance of P/06.6 (sc. 01–07) has no workers)
- [ ] **P/04-06** the pool, the constraints, the preferences in the order of N3; the placed is not reconsidered — checked by reading; an unreadable assignment is outside the pool — sc. 41; `spread_by` with a non-empty value — sc. 36; a binding shelf leads to its holder — sc. 37; home (step 7) — sc. 38, the holder of the place with two places of a server — sc. 43, on a place without a server — sc. 44 [of the lesson acceptance](../acceptance/README.md); the fallback to the server of the place with a worker of another server — by reading: there are no vectors for the choice of a worker, and sc. 43 stands on one server;
  `affinity.strict` selects the binding rows, a non-binding shelf is a preference: `tallies` on the shelf `plain` with
  `strict.kind: [reserve]` are placed — sc. 07 [of the acceptance of P/03.6](../../03-worker/acceptance/6/README.md)
- [ ] **P/04-07** weight and free capacity: Σ of the weights, strictly more, the first by name — equality of capacity: sc. 07; heavier than any — `unplaceable` (ADR-0078) — checked by reading
- [ ] **P/04-08** the group whole: room for all or all wait (ADR-0011) — sc. 22; no value of `group_by`, it is empty, does not read
  or has no host — not a group; `spread_by` without a value does not spread — sc. 11 (the stand of two manifests, `testsub2`)
- [ ] **P/04-09** `distinct`: one keeper per place, the largest load, on equality the slot order of P/03.2 N1.4 for all admissible names; the policy by a row, a soft read, a strict write — sc. 03 of the acceptance of P/06.6; the keeper — by reading by the [README of the acceptance](../acceptance/README.md) («Checks by reading from M10/04 acceptance»)
- [ ] **P/04-10** the slot fate of N3: the outcomes, the order of the rules, presence only from the live heartbeat of the resource, the terms SLOT_TERM/LOST_AFTER/HUNG_MOVE_AFTER, the controller does not write the slot except `release`; an unreadable gen is not reset and does not allow its capture — release of a slot without units (not move), the write release of a readable slot, of a torn `until` and of an unreadable gen — sc. 21 [of the lesson acceptance](../acceptance/README.md); the margin SLOT_TERM + LOST_AFTER and `hung` with the presence `runs` (the name is not given, the slot is not released, the unit does not leave; without units — not release) — sc. 26, 27; `wait` with `unlisted` (the name is not given, the slot is not released) — sc. 42; the rest is checked by reading (drill 05 of [the system acceptance](../../common/acceptance/system/README.md) «pull the power», the terms SLOT_TERM/(SLOT_TERM + LOST_AFTER) of N1.4a)
- [ ] **P/04-11** `names_given` is bound to the version of the slot row; only NAME_FATES and `wait` beyond the limit; a row with an unreadable gen is not included until the generation is recovered — the name of a released slot in `names_given`, an unreadable gen outside it — sc. 21; `wait` does not give the name before the limit — sc. 42; the binding to the version — checked by reading
- [ ] **P/04-12** move/first addition/sync — one intent: remove all members from all assignments, complete placement, add to one target and only then idle; each change with cas and guard turn, 412 stops the attempt; `Moved` with an already different source target — the completion of an active intent (removal, row, addition, idle) — sc. 28, `sync` — sc. 29 [of the lesson acceptance](../acceptance/README.md); the rest is checked by reading
- [ ] **P/04-13** leaving: the reasons in order, without a budget, a group whole or it stays; `silent` — only with `requires: resource` and a live worker, otherwise the fate of SLOT_TERM + LOST_AFTER — checked by reading: the heartbeat of a worker is read through the resource of its server, and the stand does not hold a live worker with a silent resource; the term of the fate — the drill `05-power-pull`; a released slot — the units without a place are removed (`worker: ""`); a capture in progress (`taking`) takes them away only after SLOT_TERM of an unchanged version — sc. 13; drain — sc. 33, the place does not admit (`admits: false`) — sc. 39; reachability — with a budget — checked by reading (acceptance P/03.4, sc. 03)
- [ ] **P/04-14** order (ADR-0084): per — a positive observed capacity, otherwise a positive capacity.default, otherwise withheld without division; the shortage by label sets and weight minus the capacity in flight; the order row always, `want` 1…WANT_NUM_MAX as an absolute target, cas and guard turn; the candidates (the base is alive, room, numbers, distinct by place_by, drain, decommission); the withdrawal on deadline `WANT_GRACE`, «failed to raise» `RAISE_QUIET`; shrinking — `SHRINK_AFTER`, hysteresis, only the live top number n=want(s)>1 per server; a protected top skips its whole server (a number above want is not a victim; review of stage B 6–7, № 42), `retiring`, `SHRINK_BUDGET`, cancel; the alarms `workers.no_server`, `workers.raise_failed`; in flight — the numbers 2…want without a live process by heartbeats, the candidate and the share — by the door (`live.<sub>` by numbers, free once per pass), a number above want is outside the pool and is stopped by the script (R28), the withdrawal on deadline — by numbers (R27), `distinct` with the place from the heartbeat — a server without a live suitable one without a place, without a probe in flight (in flight(s) = 0; review of stage B 3–5, № 40), no more than one probe per pass, and `no free <place_by>` (R16‴), the capacity — the smallest positive one, the forms of `short[]` (ADR-0084 addendum (2)–(4) R13′–R28) — sc. 14–17 after P/05 (`@grow`), the vectors `order`, `shrink-victim`, `shrink-allowed` (the shrink condition and the order of the refusal reasons, including live ones without a place while there are waiting, R16′; the Architect's decision of 2026-10-20, № 12 of the review analysis of stage B 3–5); the rest by reading
- [ ] **P/04-15** `delete_after` by the clock of the controller from the first look, a fresh check of the effective placement, `cas` of the unit and guard of the own turn, the journal (ADR-0067) — checked by reading
- [ ] **P/04-16** current manifest_rev is required, no missing-revision stamp; the rule guard and manifest_behind for a newer row — sc.31; a newer placement turn is not taken — sc.32 [of the lesson acceptance](../acceptance/README.md); manifest change/code0 remains checked by reading
- [ ] **P/04-17** the pass report of N1.2 with the required fields; `fates` — only occupied slots not released, `since` — the entry into
  the fate; `short[]` and `wants` with `grows`, the waiting without the removed and the unreadable — the fields `diverged` (sc. 29), `manifest_behind` (sc. 31),
  `unplaced` without those removed by `retire_when` (sc. 34), `state_swept_total` (sc. 35), `garbled` without assignments (sc. 41)
  [of the lesson acceptance](../acceptance/README.md); the rest is checked by reading
- [ ] **P/04-18** the reason of a decision MUST be non-empty and SHOULD follow the grammar of N3 «choose» (`among` — the number of the eligible, `weight` —
  only with `placement.weight`) — checked by reading: the subject is the field `reason` of the placement row and of the answer `/where/<id>` for a placed unit (sc. 02-unit of the acceptance of P/03.3, step 5: `reason` of the row `testsub/placement/c1`; `/where/<id>` is not read there); the reason — the stand of the acceptance of P/06.6 (sc. 01–07) has no workers
- [ ] **P/04-19** the common admission of N1.5/N3: turn with cas/guard, a new look after the capture and between decisions; the reserve of the whole group by intent, the recovery before a new admission; the barrier after an unknown outcome, idle is kept for the readers; competition does not bypass capacity/spread_by/group — the recovery of an active intent and idle without deleting the row — sc. 28, an unreadable intent — a refusal without admission — sc. 30; the rest is checked by reading and by the models of N5
- [ ] **P/04-20** before the write of intent the full key `<sub>/placement/<id>` of each of the members is representable within the key limit of the store; otherwise there is no decision, the members are in `unplaceable` with `why`, the placement of the other units of the subsystem does not stop — checked by reading of N5 («Evidence outside TSV»): the stand of the acceptance of P/06.6 (sc. 01–07) has no workers
- [ ] **P/04-21** snapshot: shards per worker, the content of N1.3a, empty shards, `unplaced`, the mask, after the pass — sc. 03 [of the lesson acceptance](../acceptance/README.md) (from M10/10, steps 1–4); the shard of a worker, an empty `unplaced` and an empty shard of a gone worker — sc. 40; an unreadable unit row outside the shard, the shard is published — sc. 08 (steps 1–6); the age and a spoiled shard in `/metrics` of the console — [chapter 6.5](../../06-console/spec/06.5-console.norms.md); by reading
- [ ] **P/04-22** a server failure of N1.4a (`stays`, `lost`): the move by the tolerances of two silences without a common deadline, the archive stays, the buckets not re-mirrored are lost, nothing back, except `home` (N3 «pass()», step 7) — the drill `05-power-pull` of [the system acceptance](../../common/acceptance/system/README.md); sc. 01 — `09-resource-door` of the acceptance of [P/05](../../05-resource/acceptance/README.md), sc. 02 — `14-resource-silent` of the acceptance of [chapter 6.5](../../06-console/acceptance/5/README.md)
- [ ] **P/04-23** the schema check at the start of the controller (the schema row and the raise — [P/06.6](../../06-console/spec/06.6-console.norms.md) N1.1a): N3 «controller start — schema check» — no row — the own SCHEMA, not a number or above SCHEMA — do not start, code 2 before reading the manifest, a read error — wait — not a number and above SCHEMA, code 2 — sc. 23 [of the lesson acceptance](../acceptance/README.md); a read error — wait — sc. 25; «before the manifest is read» — checked by reading
- [ ] **P/04-24** the deadline `ends`, `retire_when.state` and `retire_when.delete_after`, the delete of the row first without a tombstone and of the state after it, the sweep of the orphaned (step 8a), manual rows — `expired_kept` (ADR-0091 items 1–3): `ends`, the sweep, `expired_kept` — sc. 18; `retire_when` by the acting state (a removal with the value as the reason, outside `unplaced`) — sc. 34; the count is cleared when the removal is cancelled (C04-RETIRE-TIMER-CLEAR-01) — by reading; the sweep of a state with a foreign `born` and `state_swept_total` — sc. 35; the count of `delete_after` from the removal (600 s at `testsub2`, after a restart anew), a cancelled delete and a sweep cancelled by a row after the read — checked by reading: the stand does not hold the term and does not wedge in between the read and the delete
- [ ] **P/04-25** the replay protection on delete (ADR-0091 item 1): a row with `made` — strictly after `made.keep`, with `not_before`; `409 early` — without a barrier and a journal — the delete in sc. 18 (`keep` in 2001); `keep` in the future — the row is not deleted, sc. 18 steps 15–19; the equality boundary and the answer `409 early` of the store — by reading (the stand does not move clocks)
- [ ] **P/04-26** the table snapshot of N1.3b — by reading until step 11 of the analysis of ADR-0110; the snapshot with `state` (N1.3a; ADR-0091 item 3) — sc. 19; `snapshot_state_garbled` — sc. 18
- [ ] **P/04-27** `near`: `by`/`of`, `prefer` (AND, OR, path), the order by the id of the neighbour (N1.3; ADR-0091 item 10) — the vectors [`near-of`](../vectors/near-of/README.md); the preference for the worker of the holder — by reading; the manifest `near.sub` is not in the catalogue — no affinity, `near_waiting` in the pass report, switching on from the pass at which it appeared (ADR-0091 addendum (26) item 2, addendum (27) items 5–6) — by reading: the stand sets the catalogue `testsub` + `testsub2` before the start, and the vocabulary of the «Stand» has no directive installing a manifest in the middle of a scenario
- [ ] **P/04-28** the exclusive place (N1.3 `affinity.exclusive`): the holder admits only the bound units, its capacity is outside the shortage count of the others; an order for the place — the server of the place, an empty `server_field` — without an order, `Sealed` by `place_error` of the live workers — `withheld`, no live ones — one ordinary order — the stand prepares neither an exclusive place nor a row of a place with a secret that does not open — by reading; scenarios of P/04 and P/03.2 — when the training subsystem gets such a place (a debt) (ADR-0091 addendum (9)–(10))


# P/04 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/04-controller.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/04-controller.md` (for people, not in the export).

The model is not given acceptance scenarios, fixtures or expected outputs. The `sc. NN` / `scenario NN` and named CALL seam references identify acceptance evidence; the public norms and forms define the required behaviour.

## Task

Implement the controller of the manifest. The controller makes its decisions as rows; the launch of processes is the units `w2c-controller@.service` and
`<dep>-<sub>worker@.service` [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N1.1. The operator doors of the policy,
the drain, the labels and the decommission of a server are the doors of the console ([P/06.6](../../06-console/spec/06.6-console.norms.md) N2).

## Inputs and their priority

The canon is the [norms](04-controller.norms.md), including N0. The lecture (`ru/04-controller.md`, for people, not in the export) explains the mechanism and does not change the norm. The lesson has no HTTP contract of its own (`P/04 no-openapi`).
The forms of a unit are set in [P/06.1](../../06-console/spec/06.1-console.norms.md), of the slot — in
[P/03.2](../../03-worker/spec/03.2-worker.norms.md), the manifest keys — in [P/02.1](../../02-installer/spec/02.1-installer.norms.md),
the heartbeat — in [P/03.4](../../03-worker/spec/03.4-worker.norms.md). The forms of the rows and objects of the lesson are the family schemas `data/*.schema.json`
(the data catalogue). On a discrepancy, record the places and a counterexample, do not choose the behaviour by a guess; the order
of escalation is in the section «On a discrepancy». Internal functions, types and libraries are chosen by the implementation.

## Glossary

These terms point to their governing requirements; this table adds no rules.

| Term | Meaning and owner |
|---|---|
| `row` | A store key with textual items, not an HTTP response or an object. P/04-R003. |
| `object` | A JSON report or snapshot read through the resource object door. P/04-R007, P/04-R011, P/04-R013. |
| `placement` | The decision; an active intent supplies the effective decision for its members. P/04-R021. |
| `assignment` | The derived workers row, listing the units assigned to that worker. P/04-R078, P/04-R036. |
| `version`, `index` | The exact opaque store version for CAS/guard, distinct from the counters below. P/04-R026, P/04-R094, P/04-R103. |
| `rev` | The lesson counter in a placement/assignment; its increment rule depends on that row. P/04-R076, P/04-R078. |
| `manifest_rev` | The revision of the manifest under which a decision was taken. P/04-R076, P/04-R116, P/04-R405. |
| `turn holder` | The unique capture-attempt mark in placement_turn; its version fences store mutations. P/04-R209, P/04-R212, P/04-R026. |
| `slot holder` | The process occupying a slot; it is not the holder of the placement turn. P/03.2 N1.4; P/04-R041. |
| `place keeper` | The worker selected for a non-empty place under distinct policy. P/04-R152. |
| `resource_state`, `presence`, `fate` | Resource freshness, the resource word about a process, and this controller’s slot judgement are separate. P/04-R196, P/04-R197, P/04-R198, P/04-R040. |
| `at`, `ts`, `age` | at and ts are wall timestamps with the field-specific meanings of N1; age and policy deadlines use the specified local observation. P/04-R002, P/04-R039. |
| `live(s)`, `live.<sub>` | Heartbeat process presence for shortage versus door lock numbers for the order share. P/04-R329, P/04-R332. |
| `free`, `free(s)` | Worker capacity after conservative reserves versus server process room after in-flight orders. P/04-R022, P/04-R332. |
| `home`, `near`, `affinity` | Preferences and place constraints have different admission effects. P/04-R157, P/04-R158, P/04-R159, P/04-R290. |
| `want`, `pending`, `decommission-pending` | Absolute process target, in-flight count in a report, and durable server-removal progress respectively. P/04-R094, P/04-R107, P/04-R330. |
| `release`, `names_given` | A confirmed release write and the exact version permitting capture are separate results. P/04-R041, P/04-R310, P/04-R311, P/04-R042. |
| `pass`, `control part`, `cycle` | The control part ends before snapshot attempts and the cycle’s final report. P/04-R142. |

## What to create

- The check of the store schema as the first step of the start (N3 «controller start — schema check»).
- The reading of the picture of the world, of the effective labels and the observation of freshness by its own clock; the states of the resource and the fates of the slot.
- The pass of N3 with separate attempts of the steps, the choice of candidates and the write of decisions through cas.
- The reconciliation of assignments, the move, the departure, the order of workers by servers and the shrinking, the decommission of a server and the protection of manifest_rev.
- The report of N1.2, the snapshot of N1.3a after the pass and the evidence of the fulfilment of the 28 checklist items, including the admission of N1.5.
- The description of the choices listed under «Implementation decides». Internal functions, types and libraries are chosen by the implementation.

## Order of work

1. Write out the rows and the writers. Distinguish the decision placement, the derived workers, the operator command
   and the pass report. The version of a store row, rev and manifest_rev are different values.
2. Assemble the picture of the world: the last known properties separately from the observed freshness.
   Start the count from the first look. Check an unreadable labels row, the absence of the row and the first start.
3. Check the choice in the order of N3: the pool, the constraints, the preferences, the free capacity.
   A group requires a place on all the waiting ones; a home preference does not bypass a constraint.
   An already placed unit does not become new because a freer worker has appeared.
   For distinct apply the slot order of P/03.2 N1.4, including w-a/w-b and the equal numbers w-01/w-1.
   With equal free capacity a separate comparison by the full ASCII name is kept.
   The order of workers: the row `<sub>/want/<host>` always, `want` is an absolute target, the capacity in flight is subtracted
   from the shortage; the withdrawal by the deadline, the number above want, the shrinking with `retiring` and a budget — N3 «shortage(), order()…»;
   the vectors [`order`](../vectors/order/README.md), [`shrink-victim`](../vectors/shrink-victim/README.md) and
   [`shrink-allowed`](../vectors/shrink-allowed/README.md) (the condition of shrinking and the order of the reasons of refusal).
   In flight — the numbers 2…want without a live process by the heartbeats; the candidate and the share — by the door row (`room.<sub>`, `live.<sub>`
   of one snapshot), free(s) is computed once per pass and decreases with each share; the withdrawal by the deadline — `want := 1 + |live
   numbers ∩ {2…want}|`; a number above want is outside the pool, the script stops it (want is not raised); with `distinct` and a place
   from the heartbeat — a candidate without a live suitable process without a place and without a probe in flight, no more than one trial process per pass, the rest
   withheld with `no free <place_by>`; a probe on one server does not stop the growth on another. Check on the vectors a hole in the numbers, numbers in the door that are not consecutive, a door without `live.<sub>`, a set without
   a computable `per`, a repeat of labels in a set, an input not by form — code 2 exactly by the list of the README of the package.
4. Implement turn and intent per N1.5/N3: all changes of placement/workers are protected by the guard turn,
   and a new decision takes the fresh load with the reserves. A group gets one target, the removals of all
   precede the common addition; an unfinished intent is restored before the next admission.
   After an unknown outcome first the barrier of the version of turn, then a re-read. Check two controllers
   on different units: capacity 1, the same spread_by, different home of the members of a group. A change of owner
   lets a late writer neither add to the old assignment nor remove from the new one.
5. Work out the table of fates by the age of the observed version of the slot: SLOT_TERM / (SLOT_TERM + LOST_AFTER), gone, hung, wait, unsure, two silences.
   A shift of the writer's until and a restart of the judge are checked separately; a future finite until is not spoiling.
   Check names_given on a renewal between the judgment and the capture; do not replace an unknown gen with zero.
   The release of a readable row keeps holder/until/gen/server; a torn row with a readable gen is written wholly released and
   nobody's: released "true", holder "", until 0, gen as read, server — keep it if readable by the field schema, otherwise omit it without a substitute; gen is not readable —
   do not change the row, do not grant a permission to capture (N3 «write release»).
6. Publish separate snapshot shards only after a successful reading of the source, mask the addresses, exclude
   secrets/blob. Check an empty unplaced, a departed worker, a refusal of one shard (N1.3a, N3 «snapshot»). Before the publication
   check the bytes of the whole serialization against its P/05 resource door limit L; max_bytes is held by the store on put, its `TooLarge` is the
   same outcome; exactly the limit / +1, an empty shard and the former shard after a refusal.
7. Run the acceptance by its README: the full published scenario and step set in the order of the file (all — with the resource P/05 on
   the server of the controller: the controller reads the objects of the cluster through the resource of its server; without the resource — «unknown»).
   A repeated run also clears the POST claims and the id memory.
8. Attach the evidence of reading per N5 for the branches not observable on the stand. The stand checks several cases with
   a worker; it does not replace the races of two controllers and the whole judge.

## Pitfalls of the language and the library

| Subject | Pitfall | Check |
|---|---|---|
| time | judging freshness by the ts of a foreign process | shift the writer's clock, keep the rhythm of the observed changes |
| rows | taking absence, unreadability and empty labels as the same | three different outcomes of N1/N3 |
| weight | counting the number of units instead of the sum of the weights | unequal weights and a group exceeding the free space |
| order | a non-numeric name or an equal number has no definite winner | equal capacity: the full ASCII name; distinct: the slot order of P/03.2 N1.4; check all the admissible forms |
| cas | repeating the ready decision after a conflict | re-read and check the mutator and manifest_rev anew |
| guard | replacing the guard turn with the version of a separate placement | a late A after a change of holder gets 412 on any change of an assignment |
| admission | re-reading workers but keeping the former estimate of the free space | a new computation under turn with the reserve of the whole intent, capacity/spread_by/group |
| forecast | min of an empty pool or a division by zero | a positive default as the estimate; without it withheld with an explanation; a named 0 is not replaced with default  |
| door | the candidate by `live` of the heartbeats instead of `live.<sub>` of the door; free recomputed by the current want in each set | `free(s)` by the door, once per pass, minus each share  |
| labels | the anchor $ lets a final line feed through | check a, vlan:a and a\n as different cases |
| counters | true is taken for 1 | JSON booleans are not numbers |
| N1.3a | a read error zeroes the age/publishes an empty shard | keep the unknown and the last observation; emptiness only from a successful traversal |

## Done when

P/04-01…28 are fulfilled, the choices of the implementation are described, the acceptance has passed with the declared initial state,
and the remaining guarantees have evidence per N5.
State the slice, the commands/stand, the observations and the limitations. A check of the documents does not mean
the passing of an implementation. A discrepancy of a norm and a form is to be drawn up with a counterexample by the rules of the project;
a repeatable error of the acceptance is to be recorded in the lesson correction history outside the model input.

## On a discrepancy

Reconcile the norm and the scenario on one exact input. Record the places, the initial state,
the intervention and the expected/actual result; if the sources diverge, pass the question to the Specification
with a recommendation and do not carry the behaviour of the implementation into the canon silently. A correction of a norm affects
the acceptance; a repeatable error of the acceptance is to be recorded in the lesson correction history outside the model input.

The optional kit plan is [forms/stages.tsv](../forms/stages.tsv), with [forms/README.md](../forms/README.md) describing inputs, machines and test normalization. Kit seams supplement the reading witnesses and runner acceptance; they do not replace them.

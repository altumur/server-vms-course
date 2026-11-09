# The stand of group operations

This English text is the source; the Russian translation `ru/acceptance/ops/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The scenarios of `door.pass.operations`: the acceptance with the memory of the caller, the leader, the generation, the step batch (ADR-0095; the norms — [P/06.9](../../../06-console/spec/06.9-console.norms.md) N1.1–N1.6, N2, N3, [the writer turn contract](../../contracts/turn.md), the batch door and the replay memory — [P/06.1](../../../06-console/spec/06.1-console.norms.md) N2, N3, the ticket — [the gate-and-pass contract](../../contracts/gate-and-pass.md) «Pass of the second kind»). What is checked without an operation step goes in the [acceptance 6.9](../../../06-console/acceptance/9/README.md), sc. 01, 02.

**There is no dry run by an implementation.** Not a single step is executed: the values are computed from the text of the norm. New scenarios enter the pin of the lines only by a runner release, after a run against an implementation; each red step is analysed by the question «norm or data», as on the [stand of the pass of the second kind](../pass/README.md#executability).

5 scenarios / 112 steps. The runner plays the worker: a scenario needs to keep a step call open and to write the step batch itself. The manifest is [`probe-op`](probe-op.subsystem.yaml): the table `repeats` — the memory of the caller, like `backend/repeats` (`service: true`), the unit row `things` — the target of a step. The kits [`stand.json`](stand.json) — for sc. 12 of the plan: the scenarios of this release go without `@tls-setup`, because the second console stands only on the stand without a kit.

`step_key` in `Idempotency-Key` is computed by the definition of N2 and checked against [`op-step/key.tsv`](../../../06-console/vectors/op-step/key.tsv). The `id` of the operations are random, written as they are.

## Preparation

The stand is [«Domain stand»](../README.md#domain-stand), `@domain m1`; the runner sets up `probe-op` on `m1` together with the manifests of the stand. The door `socket m1 probe-opworker` — [the dictionary](../README.md#stand-in-worker-of-the-pass-of-the-second-kind). The person of the scenarios is `root`: the steps go by their right, the token validity `TOKEN_LIFETIME` is longer than any scenario. The target of a step is the row `things`. `expected` and `versions` carry its `revision`: for the console these are opaque values, and the index in the `cas` of the batch is taken from the answer of `POST`.

In sc. 03 the instance `backend` is a repeated submission of `@pass-worker` of the same name: the previous worker is closed, the client gets 502, the 202 is lost. A second console of sc. 03 is not needed: ADR-0095, Confirmation, speaks of another instance of `backend`.

## Two consoles

`console#2` is the console of another server: there is one console per server ([P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.5), so the copy has its own `PLATFORM_DIR`, port and role socket, while the store and the ring are common. The ticket lives at the instance that issued it (`ticket` step 1), so the door `socket m1#2` leads to copy 2, a foreign ticket there is 401.

- `07-restart-with-outcome`, `07-restart-no-outcome`: the leader is copy 1, copy 2 starts in the middle of a call and after the first is stopped becomes the leader; the new ticket goes to it.
- `07-late-batch`: the late batch goes by the ticket of the previous leader, so the previous leader is copy 2. Copy 1 is frozen until the acceptance and does not contend for the turn. Step 9 puts the operation on pause: the call of copy 2 plays to the end, and the new leader does not call the step, so the cancel does not wait for its call `OPS_STEP_WAIT`; step 24 holds this. `OPS_STEP_WAIT` is shorter than `TURN_TERM`, so the turn gives up the write through `admin.sock`: otherwise the ticket would die earlier than the new holder.

## Timings

The bounds of `@until` are derived from the constants of the norm: `OPS_TICK` 5, `OPS_STEP_WAIT` 30 (P/06.9 N1.6), `TURN_TERM` 45 (the turn contract).

| Timing, s | From where | Where |
|---|---|---|
| 65 | `TURN_TERM` + 4 × `OPS_TICK`: the tick at which the new console saw the row, the term, the tick of taking and two ticks of margin for the start of the copy and the write of the epoch | `07-restart-with-outcome` step 11 |
| 40 | `OPS_STEP_WAIT` + 2 × `OPS_TICK`: SIGTERM gives up the turn, an open call can live out its term, then a tick | `07-restart-no-outcome` step 9 |
| 15 | 3 × `OPS_TICK`: a tick sees the outcome (step 4), the next tick completes, one tick of margin | the completion of the operation in all scenarios except `07-late-batch` |
| 10 | 2 × `OPS_TICK`: the tick of taking the turn or of the round and one tick of margin | `07-late-batch` steps 14, 16 |

`@pass-step` waits no longer than 40 s by the dictionary, and `TURN_TERM` is longer, so first goes an `@until` by the index of the row `<sub>/operations-epoch`.

`07-late-batch`: with an honest wait of `TURN_TERM` the ticket of the previous call would die earlier: `OPS_STEP_WAIT` is shorter than `TURN_TERM`, and the late batch would get 401 and would not reach the guard. Therefore the turn of the frozen leader is given up by the stand with the write `holder: ""` through `admin.sock` (the turn contract step 2: «`holder` is empty → the cas of the read version»). Steps 7–18 fit into `OPS_STEP_WAIT`: 2 × 10 s plus the business of the runner.

Sc. 03: `pause` right after the acceptance holds the steps while the stand-in worker is replaced, and is removed after the repeat. Otherwise the calls to a closed address would eat up `OPS_STEP_TRIES`.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There is no `@sleep`. `@pass-step-none` counts as a sleep ([the dictionary](../README.md#stand-in-worker-of-the-pass-of-the-second-kind)):

| Step | Timing, s | Reason |
|---|---|---|
| `03-accept-repeat` step 41 | 10 | a check of absence: the operation is completed and the memory is given away, a new step call does not come; 2 × `OPS_TICK` — a tick of the leader and a tick of margin |

## What is checked by reading

- The simultaneity of sc. 03: the TSV steps go one after another, so both executors read «started» with one index and submit the acceptance one after the other. The race of two batches is decided by the `cas` of the store; the outcome is the same.
- The refusal of the guard at step 9 of the batch door (`412 guard` of the store): the window between the check and the write cannot be caught by a TSV, the scenario catches step 5.
- `412 leader moved` does not go into the memory of `step_key`: the refusal of both passes looks the same.
- A new leader and a landed batch: the leader rewrites the generation before reading the outcome, so it sees a landed batch as an outcome. The scenario `07-lost-batch-answer` puts the repeat inside one call.

## The other scenarios of the plan

Sc. 04–06, 08–13 of the plan of [acceptance 6.9](../../../06-console/acceptance/9/README.md) — by reading for now, the meaning is the former one:

| № | Scenario | Norms |
|---|---|---|
| 04 | occupancy: the root of an unfinished operation, including one on pause, — 409 `root busy`, nothing is written; two acceptances without common roots both pass; two steps over one root | N1.3 |
| 05 | versions: `fail → set`, `ok → fail → set` over one root, the same cases in `retry-failed`, a foreign edit between steps | N1.4 |
| 06 | a pause in the middle of a step: the step plays to the end, the next is not started; resume; cancel: the remaining ones `cancel`, the executed ones stayed; a cancel on pause; 409 for a completed one and `retry-failed` for an unfinished one | N3 |
| 08 | the token validity: at `exp` the operation goes on pause; a request of the author with a new token rebinds and removes `expired`; a request of a non-author does not rebind; a human pause stays | N3 «rebind» |
| 09 | rights: the person is switched off in the middle of an operation: the step whose `may` refused — `fail`, the remaining ones `cancel`; `kid` retired — a cancel; a revocation on pause — a cancel, `resume` after `exp + 60` — 409; without `view` — 404; without `edit` — `pause` 403; a callback after the end of the call — 401; a ticket for the outcome of a foreign step — 403 | N2, N3 «round» |
| 10 | a poisonous step: `OPS_STEP_TRIES` failed calls, the outcome `fail not_run`, the operation goes on; the series `<sub>_op_step_retries_total`, `<sub>_op_step_poisoned_total` | N3 «step» |
| 11 | secrets: a raw read of the store — there is no open value anywhere, the step `ok` and `cancel` have no sealed one either, for `fail` the sealed one lies until `OPS_KEEP` and `retry-failed` uses it; after a change of the ring the body of an unfinished operation opens; the value did not open — `fail not_run` | N1.2, N3 |
| 12 | the server leaf: on a stand with TLS the leaf of another instance — there is no call | N2 |
| 13 | the limits of steps and operations, the weight of the acceptance batch; the reaper removes a completed operation after `OPS_KEEP`, bodies without a record and hanging `opbusy` | N1.6, N3 «operations reaper» |

The change of the ring of sc. 11 stays by reading forever: there is no directive for it.

## scenarios.tsv

The format is the [dictionary of directives and doors](../README.md#dictionary-of-directives-and-doors).


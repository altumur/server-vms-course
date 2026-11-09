# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/ops/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

| № | Scenario | Norms |
|---|---|---|
| 03 | `03-accept-repeat`: two executors of one key, a lost 202 on a fall of the worker, a repeat on another instance of `backend`, the same `id`, a repeat of the key after the completion: one operation, the steps are executed once | N3 «accept», N4 |
| 07 | `07-restart-with-outcome`: the leader is killed, the generation is rewritten, there is an outcome, the step is not executed again | N3 «leader», «step» step 4; the turn contract steps 2, 3 |
| 07 | `07-restart-no-outcome`: the leader is stopped, the generation is rewritten, there is no outcome, a new call of the same step | N3 «leader» step 5, «step»; `ticket` step 1 |
| 07 | `07-lost-batch-answer`: a lost answer of the batch, a repeat with the same key: the saved answer, not 412 | N2 «Step batch»; P/06.1 N3 «batch» |
| 07 | `07-late-batch`: the leader on a process pause, another took the turn, a cancel, a late batch — `412 leader moved`, the outcome stays `cancel` | N2 «Step batch», N3 «finish», «Races» |

### Original passage 2

In sc. 03 the instance `backend` is a repeated submission of `@pass-worker` of the same name: the previous worker is closed, the client gets 502, the 202 is lost. A second console of sc. 03 is not needed: ADR-0095, Confirmation, speaks of another instance of `backend`.

### Original passage 3

- `07-restart-with-outcome`, `07-restart-no-outcome`: the leader is copy 1, copy 2 starts in the middle of a call and after the first is stopped becomes the leader; the new ticket goes to it.
- `07-late-batch`: the late batch goes by the ticket of the previous leader, so the previous leader is copy 2. Copy 1 is frozen until the acceptance and does not contend for the turn. Step 9 puts the operation on pause: the call of copy 2 plays to the end, and the new leader does not call the step, so the cancel does not wait for its call `OPS_STEP_WAIT`; step 24 holds this. `OPS_STEP_WAIT` is shorter than `TURN_TERM`, so the turn gives up the write through `admin.sock`: otherwise the ticket would die earlier than the new holder.

### Original passage 4

| 65 | `TURN_TERM` + 4 × `OPS_TICK`: the tick at which the new console saw the row, the term, the tick of taking and two ticks of margin for the start of the copy and the write of the epoch | `07-restart-with-outcome` step 11 |
| 40 | `OPS_STEP_WAIT` + 2 × `OPS_TICK`: SIGTERM gives up the turn, an open call can live out its term, then a tick | `07-restart-no-outcome` step 9 |
| 15 | 3 × `OPS_TICK`: a tick sees the outcome (step 4), the next tick completes, one tick of margin | the completion of the operation in all scenarios except `07-late-batch` |
| 10 | 2 × `OPS_TICK`: the tick of taking the turn or of the round and one tick of margin | `07-late-batch` steps 14, 16 |

### Original passage 5

`07-late-batch`: with an honest wait of `TURN_TERM` the ticket of the previous call would die earlier: `OPS_STEP_WAIT` is shorter than `TURN_TERM`, and the late batch would get 401 and would not reach the guard. Therefore the turn of the frozen leader is given up by the stand with the write `holder: ""` through `admin.sock` (the turn contract step 2: «`holder` is empty → the cas of the read version»). Steps 7–18 fit into `OPS_STEP_WAIT`: 2 × 10 s plus the business of the runner.

Sc. 03: `pause` right after the acceptance holds the steps while the stand-in worker is replaced, and is removed after the repeat. Otherwise the calls to a closed address would eat up `OPS_STEP_TRIES`.

### Original passage 6

| `03-accept-repeat` step 41 | 10 | a check of absence: the operation is completed and the memory is given away, a new step call does not come; 2 × `OPS_TICK` — a tick of the leader and a tick of margin |

### Original passage 7

- The simultaneity of sc. 03: the TSV steps go one after another, so both executors read «started» with one index and submit the acceptance one after the other. The race of two batches is decided by the `cas` of the store; the outcome is the same.
- The refusal of the guard at step 9 of the batch door (`412 guard` of the store): the window between the check and the write cannot be caught by a TSV, the scenario catches step 5.

### Original passage 8

- A new leader and a landed batch: the leader rewrites the generation before reading the outcome, so it sees a landed batch as an outcome. The scenario `07-lost-batch-answer` puts the repeat inside one call.

### Original passage 9

Sc. 04–06, 08–13 of the plan of [acceptance 6.9](../../../06-console/acceptance/9/README.md) — by reading for now, the meaning is the former one:

### Original passage 10

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

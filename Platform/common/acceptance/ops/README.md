# The stand of group operations

This English text is the source; the Russian translation `ru/acceptance/ops/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The scenarios of `door.pass.operations`: the acceptance with the memory of the caller, the leader, the generation, the step batch (ADR-0095; the norms — [P/06.9](../../../06-console/spec/06.9-console.norms.md) N1.1–N1.6, N2, N3, [the writer turn contract](../../contracts/turn.md), the batch door and the replay memory — [P/06.1](../../../06-console/spec/06.1-console.norms.md) N2, N3, the ticket — [the gate-and-pass contract](../../contracts/gate-and-pass.md) «Pass of the second kind»). What is checked without an operation step goes in the [acceptance 6.9](../../../06-console/acceptance/9/README.md), sc. 01, 02.

**There is no dry run by an implementation.** Not a single step is executed: the values are computed from the text of the norm. New scenarios enter the pin of the lines only by a runner release, after a run against an implementation; each red step is analysed by the question «norm or data», as on the [stand of the pass of the second kind](../pass/README.md#executability).

5 scenarios / 112 steps. The runner plays the worker: a scenario needs to keep a step call open and to write the step batch itself. The manifest is [`probe-op`](probe-op.subsystem.yaml): the table `repeats` — the memory of the caller, like `backend/repeats` (`service: true`), the unit row `things` — the target of a step. The kits [`stand.json`](stand.json) — for sc. 12 of the plan: the scenarios of this release go without `@tls-setup`, because the second console stands only on the stand without a kit.

`step_key` in `Idempotency-Key` is computed by the definition of N2 and checked against [`op-step/key.tsv`](../../../06-console/vectors/op-step/key.tsv). The `id` of the operations are random, written as they are.

## Preparation

The stand is [«Domain stand»](../README.md#domain-stand), `@domain m1`; the runner sets up `probe-op` on `m1` together with the manifests of the stand. The door `socket m1 probe-opworker` — [the dictionary](../README.md#stand-in-worker-of-the-pass-of-the-second-kind). The person of the scenarios is `root`: the steps go by their right, the token validity `TOKEN_LIFETIME` is longer than any scenario. The target of a step is the row `things`. `expected` and `versions` carry its `revision`: for the console these are opaque values, and the index in the `cas` of the batch is taken from the answer of `POST`.

## Two consoles

`console#2` is the console of another server: there is one console per server ([P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.5), so the copy has its own `PLATFORM_DIR`, port and role socket, while the store and the ring are common. The ticket lives at the instance that issued it (`ticket` step 1), so the door `socket m1#2` leads to copy 2, a foreign ticket there is 401.

## Timings

The bounds of `@until` are derived from the constants of the norm: `OPS_TICK` 5, `OPS_STEP_WAIT` 30 (P/06.9 N1.6), `TURN_TERM` 45 (the turn contract).

| Timing, s | From where | Where |
|---|---|---|
| 65 | `TURN_TERM` + 4 × `OPS_TICK`: the tick at which the new console saw the row, the term, the tick of taking and two ticks of margin for the start of the copy and the write of the epoch | taking the turn by a new console |
| 40 | `OPS_STEP_WAIT` + 2 × `OPS_TICK`: SIGTERM gives up the turn, an open call can live out its term, then a tick | the turn after SIGTERM |
| 15 | 3 × `OPS_TICK`: a tick sees the outcome, the next tick completes, one tick of margin | the completion of an operation |
| 10 | 2 × `OPS_TICK`: the tick of taking the turn or of the round and one tick of margin | a round or the taking of the turn |

`@pass-step` waits no longer than 40 s by the dictionary, and `TURN_TERM` is longer, so first goes an `@until` by the index of the row `<sub>/operations-epoch`.

With an honest wait of `TURN_TERM` the ticket of a previous call would die earlier: `OPS_STEP_WAIT` is shorter than `TURN_TERM`. A stand can give up the turn with the write `holder: ""` through `admin.sock` (the turn contract step 2: «`holder` is empty → the cas of the read version»).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There is no `@sleep`. `@pass-step-none` counts as a sleep ([the dictionary](../README.md#stand-in-worker-of-the-pass-of-the-second-kind)):

| Step | Timing, s | Reason |
|---|---|---|
| a check of absence | 10 | 2 × `OPS_TICK` — a tick of the leader and a tick of margin |

## What is checked by reading

- The simultaneity of two executors: the TSV steps go one after another, so both executors read «started» with one index and submit the acceptance one after the other. The race of two batches is decided by the `cas` of the store; the outcome is the same.
- The refusal of the guard at step 9 of the batch door (`412 guard` of the store): the window between the check and the write cannot be caught by a TSV.
- `412 leader moved` does not go into the memory of `step_key`: the refusal of both passes looks the same.
- A new leader and a landed batch: the leader rewrites the generation before reading the outcome, so it sees a landed batch as an outcome.

## The other scenarios of the plan

Sc. 04–06, 08–13 of the plan of [acceptance 6.9](../../../06-console/acceptance/9/README.md) — by reading for now, the meaning is the former one.

The change of the ring stays by reading forever: there is no directive for it.

## scenarios.tsv

The format is the [dictionary of directives and doors](../README.md#dictionary-of-directives-and-doors).


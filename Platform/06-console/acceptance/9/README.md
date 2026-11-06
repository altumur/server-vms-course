# Acceptance P/06.9 — group operations (stand)

This English text is the source; the Russian translation `ru/acceptance/9/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`06.9-console.norms.md`](../../spec/06.9-console.norms.md) N5. The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
In total 2 scenarios / 8 steps.

**There is no dry run by an implementation.** The chapter is part of the rights increment and waits for the credit of increment B.

## Preparation

A console with the manifest `testsub`, it declares no operations. A door without a prefix is the console; the role of the door `store` is `console`. There are no sleeps.

## scenarios.tsv

The format is [the dictionary of directives and doors](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). The scenarios check only what is executable without a declaration: the subsystem has no operation doors, rows do not appear, there is no rollback as a path.

## Plan of scenarios after ADR-0094 B1

A step of an operation requires a manifest with `door.pass.operations` and a worker with a route of the step call. The test worker is in the dictionary, the data lie in [`common/acceptance/ops`](../../../common/acceptance/ops/README.md): sc. 03 and 07 are written there, the other rows of the table are by reading for now.

| № | Scenario | Norms |
|---|---|---|
| 03 | admission: a lost 202, a repeat on another instance — the same operation, the steps are not executed twice; two simultaneous executors of one key; a repeat of a key after the completion of the operation | N3 «accept» |
| 04 | occupancy: the root of an unfinished operation, including one on pause, — 409 `root busy`, nothing is written; two admissions without common roots both pass; two steps over one root | N1.3 |
| 05 | versions: `fail → set`, `ok → fail → set` over one root, the same cases in `retry-failed`, a foreign edit between the steps | N1.4 |
| 06 | a pause in the middle of a step: the step plays to the end, the next one is not begun; continuation; cancellation: the remaining ones `cancel`, the executed ones remain; cancellation on pause; 409 for a completed one and `retry-failed` for an unfinished one | N3 |
| 07 | a restart of the leader during a step: the generation is rewritten; there is a result — the step is not executed again; there is no result — it is brought to the end with the same key; a lost answer of the batch — the saved answer, not 412; the leader on a process pause, another one took the queue, cancellation: the late batch is refused by the generation guard, the result remains `cancel` | N3 «leader», «step», «finish» |
| 08 | the token deadline: at `exp` the operation goes on pause; a request of the author with a new token rebinds and removes `expired`; a request not of the author does not rebind; a human pause remains | N3 «rebind» |
| 09 | rights: the person is disabled in the middle of an operation: the step whose `may` refused — `fail`, the remaining ones `cancel`; `kid` is withdrawn — cancellation; a revocation on pause — cancellation, `resume` after `exp + 60` — 409; without `view` — 404; without `edit` — `pause` 403; a callback after the end of the call — 401; a ticket to the result of a foreign step — 403 | N2, N3 «round» |
| 10 | a poisonous step: `OPS_STEP_TRIES` failed calls, the result `fail not_run`, the operation goes on; the series `<sub>_op_step_retries_total`, `<sub>_op_step_poisoned_total` | N3 «step» |
| 11 | secrets: a raw read of the store — there is no open value anywhere, a step `ok` and `cancel` has no sealed one either, at `fail` the sealed one lies until `OPS_KEEP` and `retry-failed` uses it; after a change of the ring the body of an unfinished operation opens; the value did not open — `fail not_run` | N1.2, N3 |
| 12 | the server leaf: on a stand with TLS the leaf of another instance — there is no call | N2 |
| 13 | the limits of steps and operations, the weight of the admission batch; the reaper removes a completed operation after `OPS_KEEP`, bodies without a record and hanging `opbusy` | N1.6, N3 «operations reaper» |

## What is checked by reading

Sc. 04–06, 08–13 of the plan table — by reading, the change of the ring of sc. 11 — for good: there is no directive; the form of the key — the cases `a95_*` of the corpus of P/02.1. The algorithms without a stand are checked by the vectors [`op-step`](../../vectors/op-step/README.md): `step_key` and the expected version along the chain of the root.

## `journal/corrections-9.tsv`

The log of corrections of the scenarios of the chapter (ADR-0124: a log, not an input, not in the export), the format is as in the neighbouring chapters.

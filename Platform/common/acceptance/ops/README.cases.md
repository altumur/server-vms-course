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

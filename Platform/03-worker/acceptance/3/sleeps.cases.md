# Judge-only sleep case instructions

This English text is the source; the Russian translation `ru/acceptance/3/sleeps.cases.md` is derived from it (ADR-0121).

This file preserves the case-specific instructions from the chapter acceptance README. It is judge-only data, not model input. Generic wait semantics remain in the common stand protocol.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`. The remaining sleeps are a check of absence or the time before an action; the length is the smallest by the deadlines of N1.2 of [chapter 3.2](../../spec/03.2-worker.norms.md) and N1.2 of chapter 3.3:

| Sc./step | Sleep | Reason |
|---|---|---|
| 02/10 | 12 s | absence: an edit of the row does not raise the epoch; the worker would see a new revision within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s |
| 06/9 | 12 s | time before an action: the worker must see the empty assignment (the lease step ≈ 8.3 s and a pass) before `c6` is created again; its heartbeat is an object, the stand of the chapter does not read it |

End of judge-only case instructions.

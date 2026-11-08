# Judge-only sleep case instructions

This English text is the source; the Russian translation `ru/acceptance/sleeps.cases.md` is derived from it (ADR-0121).

This file preserves the case-specific instructions from the chapter acceptance README. It is judge-only data, not model input. Generic wait semantics remain in the common stand protocol.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`. The remaining sleeps are a check of absence or the time before an action; the length is the smallest by the deadlines
of P/03.2 and P/03.4 (formerly M10/5 N1.2):

| Sc./step | Sleep | Reason |
|---|---|---|
| 07/7 | 12 s | time before an action: the controller must see the heartbeats of both workers (HEARTBEAT_EVERY 10 s, the pass of the controller 5 s) before `t7` is created; the heartbeat is an object, the stand does not read it |
| 13/12 | 10 s | absence: `c13` does not leave `w-1` earlier than SLOT_TERM — two passes of the controller of 5 s each |
| 17/21 | 25 s | absence: `want` does not grow above 2 and the trial process without a place is not shrunk — the deadline `shrink_after=20` and the pass step of the controller 5 s (analysis of the review of stage B 3–5, № 12) |
| 18/17 | 12 s | absence: the row `testsub-c3` with `made.keep` in the future is not deleted — two passes of the controller of 5 s each (the deletion by `ends` is in the same pass as the removal, N3 step 8) |
| 24/12 | 12 s | absence: `c2` is not placed with an empty labels row — two passes of the controller |
| 24/19 | 12 s | absence: `c1` and `c2` are not removed with an unreadable labels row — two passes of the controller |
| 25/4 | 10 s | absence: there is no pass report while the store is silent to the controller on the schema read — a working controller would have written it within two passes of 5 s each |
| 30/8 | 12 s | absence: `c1` with a live `w-1` is not placed while the intent row is not by form — two passes of the controller |
| 32/9 | 12 s | absence: `c2` is not placed while the turn row carries a `manifest_rev` above the revision of the controller — two passes |
| 41/8 | 12 s | time before an action: the controller must see the heartbeats of `w-1` and `w-2` before `c1` is created (as 07/7) — otherwise `c1` at `w-2` proves nothing |
| 26/10 | 75 s | absence: until the end of the margin the fate is `alive`, not `hung` — the last version of the slot is no earlier than ≈ 8.3 s before the freeze (P/03.2 N1.2 LEASE_EVERY), the margin SLOT_TERM + LOST_AFTER = 90 s from its first observation: `hung` not earlier than ≈ 81.7 s |

End of judge-only case instructions.

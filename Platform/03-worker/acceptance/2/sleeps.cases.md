# Judge-only sleep case instructions

This English text is the source; the Russian translation `ru/acceptance/2/sleeps.cases.md` is derived from it (ADR-0121).

This file preserves the case-specific instructions from the chapter acceptance README. It is judge-only data, not model input. Generic wait semantics remain in the common stand protocol.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 01 step 4 waits for the first renewal after step 3 (`until` ≠ `$u0`), step 6 — for the second
(`until` ≠ `$u1`; LEASE_EVERY ≈ 8.3 s, N1.2 of the chapter; review of stage B 1–2, item 3). The remaining sleeps are a check of absence or the time before an action; the length is the smallest by the deadlines of N1.2:

| Sc./step | Sleep | Reason |
|---|---|---|
| 04/11, 10/11 | 12 s | absence: the displaced copy does not take the name back; a repeat of the name search — once per CONTEND_EVERY 10 s |
| 05/6 | 20 s | absence: after SIGKILL the slot is not released and not renewed (the deadline is named in N5, sc. 05) |
| 08/9 | 12 s | absence: `gen` does not grow — a repeated capture would be visible within a lease step ≈ 8.3 s |
| 09/3 | 12 s | absence: there are no slots under the wrong name — by this deadline the capture at the start would already have passed (a correct worker holds the slot by the step `@until 20`) |
| 10/14 | 12 s | absence: there is no second row `worker.name_taken` — a repeat of the mark would come after CONTEND_EVERY 10 s |
| 11/2 | 12 s | absence: there is no slot `w-1` — the worker with `LABELS` outside the alphabet refused at the start with code 2; a correct one would have captured the slot by this deadline, as in 09/3 (the VMS request «heartbeat and a garbled row») |
| 14/4, 16/4 | 12 s | absence: the slot row is not rewritten — the capture at the start and the repeat of the search (CONTEND_EVERY 10 s) would have passed by this deadline |
| 14/7 | 50 s | absence: even after `TORN_STILL` 50 s from the first read (together with 14/4 — 62 s, a repeat of the search once per CONTEND_EVERY 10 s) the row with an unreadable `gen` is not rewritten |
| 17/3 | 12 s | absence: the torn row is not touched earlier than `TORN_STILL` — the capture at the start would have passed by this deadline |
| 18/10 | 12 s | absence: the epoch rows are not rewritten — the worker sees the assignment within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s (as 02/10 of the acceptance of chapter 3.3) |
| 20/6 | 12 s | time before an action: the renewal of the slot with the schema check passes within LEASE_EVERY ≈ 8.3 s; after it the version of the slot and `ts` of the heartbeat are bound |
| 20/9 | 12 s | absence: the version of the slot and `ts` of the heartbeat do not change — the renewal (≈ 8.3 s) and the heartbeat (HEARTBEAT_EVERY 10 s) would be visible |
| 21/4 | 12 s | absence: there is no slot and no contender mark — the capture at the start and the mark (CONTEND_EVERY 10 s) would be visible |
| 23/8 | 12 s | absence: the torn hold row is not rewritten — the renewal of the place at the lease step ≈ 8.3 s |
| 23/11 | 60 s | absence: the place is held even after the strict window — a strict one is released by `CLOSE_BY` 50 s from the last confirmation (≤ 8.3 s before the spoiling), the heartbeat — after HEARTBEAT_EVERY 10 s; together with 23/8 — 72 s |
| 24/9 | 10 s | time of silence: longer than the lease step LEASE_EVERY ≈ 8.3 s (the renewal goes into silence) and shorter than the lease window of 25 s minus the step (25 − 8.3 ≈ 16.7 s): the lease does not expire before the mend |
| 27/9, 31/6, 32/4 | 12 s | absence: there is no epoch row — the worker sees the assignment within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s (as 18/10); there is no slot — the capture at the start and the repeat of the search (CONTEND_EVERY 10 s) would have passed (as 21/4) |
| 34/5 | 12 s | absence: the worker would have taken a free place at the first lease step after the capture of the slot (≈ 8.3 s; N3 «lease_step()» step 6) |
| 34/7 | 50 s | absence: the foreign place is free, having stood without changes LOST_AFTER + HOLD_SKEW = 50 s by the clock of the taker; together with 34/5 — 62 s: and the torn one is not taken after this deadline either |

End of judge-only case instructions.

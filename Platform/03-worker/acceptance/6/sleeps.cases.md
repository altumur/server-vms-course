# Judge-only sleep case instructions

This English text is the source; the Russian translation `ru/acceptance/6/sleeps.cases.md` is derived from it (ADR-0121).

This file preserves the case-specific instructions from the chapter acceptance README. It is judge-only data, not model input. Generic wait semantics remain in the common stand protocol.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 05/7 | 20 s | absence: the request row is not removed right after `performed` — the lower bound of settle with a margin (above, «scenarios.tsv») |
| 10/12 | 12 s | absence: after the loss of the name the version of the slot, `ts` of the heartbeat and the state row do not change, a second `worker.name_taken` is not written — the renewal (≈ 8.3 s), the heartbeat (10 s) and the name search (CONTEND_EVERY 10 s) would be visible |
| 40/7 | 12 s | absence: there is no mark by the unreadable request row and the row is not removed — the holder's view at every pass (POLL ~2 s) and the reaper would have had time |

End of judge-only case instructions.

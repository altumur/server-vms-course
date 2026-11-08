# Judge-only sleep case instructions

This English text is the source; the Russian translation `ru/acceptance/sleeps.cases.md` is derived from it (ADR-0121).

This file preserves the case-specific instructions from the chapter acceptance README. It is judge-only data, not model input. Generic wait semantics remain in the common stand protocol.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

One sleep: sc. `18-schema-read-wait` step 3, `@sleep 10` — a check of absence: while the store is silent to the resource, it does not exit
(an error of reading `platform/schema` — wait, do not start with code 2; an exit is visible by step 5 — there is still no door row); within 10 s
a started process reaches the first step of the start — the reading of the schema. The second pass of the audit (Gemini) — two more: sc. 33 step 3,
`@sleep 2` — a check of absence: a repeated reception of the same copy of a bucket does not shift `written` (R05-G04); `written` is wall-clock seconds,
an implementation may have it as an integer, therefore more than a second passes between the receptions, otherwise the shift would not be visible; sc. 41 step 6,
`@sleep 12` — a check of absence: the own row `free-*` in the band between the marks is neither removed nor rewritten; the heartbeat with
`pass_started` (step 5) says only that the first pass has begun. The fixed sleep does not confirm the end of `relieve`; this is an early observation. Completion is checked separately by synchronous CALL s63-free-ask-band-completed. Waiting for an event is `@until`: sc. 09-resource-door step 2 waits for the first door row, step 3 — for a new door mark
(`at` has changed; the mark — every ALIVE_EVERY, N1.4 `door_row`), sc. 08 step 16 — for the alarm row in the index, sc. 16-presence-lock
steps 3, 5, 7 — for `running` in the heartbeat of the resource (analysis of the review of stage B 3–5, № 26); sc. 17 step 8, 18 step 5 — for the first door row; sc. 19 step 3 — for the heartbeat
of `w-1` in the listing; sc. 20 steps 3, 5, 7, 9 — for the count of the door after the mark (every ALIVE_EVERY); sc. 22 steps 3, 5 — for the index rows; sc. 31 steps 2, 4 — for the doors
of `srv-b` and `srv-a`, step 8 — for the copy of the body at `srv-b` after the first pass of the restarted `srv-a`; sc. 33 step 9, 37–39 the heartbeat step, 40
steps 4, 5, 41 step 5, 42 step 5 — for the heartbeat of the resource (every 10 s) after the first pass; sc. 34–36 — for the index rows; sc. 43 step 2 — for the heartbeat
of `w-1` in the listing.

End of judge-only case instructions.

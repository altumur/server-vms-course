# alarms.py — Lesson 14: one list of alarms from every member; an alarm that leaves at once; silence as an alarm, with a witness; a week of history at the domain

**Role in the module.** The brief's `MergedIndex` over cameras. The domain merges each member's alarms from the page in its report, newest first, a page per member, with what it could not hear said (Lesson 1's honesty). The camera that goes dark is the one whose last alarm matters, so: the card wakes the agent on an alarm; a silent member is answered from its last report; its silence is an alarm of its own, and the ingest it polls says whether it is alive; the domain keeps a week of what it read. Copies of alarms on neighbours' cards were removed on 29 September — they copied only closed buckets, so the last alarm before a camera went dark was in none of them (the lesson's step 7).

## Module-level names
- `BUCKET = 600` — М10A's bucket span. `WINDOW = 86400` — a page's span.
- `POLLED = "rec/polled"` — an ingest's word: when each camera last polled it, as ages.
- `HISTORY = "domain/alarm-history"` — in the domain's object store: one object per member, a rolling week.

## `class Card`
A member's events on its card, as М10A's buckets. `observe(epoch, t, kind, alarm=False)` — and on an alarm, `on_alarm()` (the agent's `wake`); `alarms(since, until, limit)` → `{events, truncated}`.

## `pages(card, now, per_member=100, window=WINDOW)` — the page the agent puts in its report: `{"alarms": …}`.

## `class ReportedDoor`
A member's alarms from its last report in the domain's store. `alarms(...)` raises `Unreachable` when the report is older than `lost_after`; `last(...)` is the page of that last report anyway, `known_until` its time — None if it never reported.

## `class AlarmHistory`
`keep(member, events)` adds what is not kept yet and drops what is older than `days`, rewriting the member's one object (the store under the domain may not delete). `read(member, since, until)`.

## `class DomainAlarms`
`alive_at(ref)` → `(time, cluster)` of the latest poll any ingest reports for that camera. `list(since, until=None)` → `{events (each with member; from_history when only the history had it; a synthetic class-alarm line `silent` or `not_reporting` for each silent member), members: {name: {state ok|last_report|unreachable, known_until, silent_since, alive_at, alive_via, truncated}}, complete, sentence}`. A fresh page is kept in the history as it is read.

## Notes
- `serial_of(member)` — `cam-<serial>` → `<serial>`, the ref a camera's poll is known by.
- The agent's side is `DomainAgent.wake/due/report_now` in `agent.py`; the ingest's is `Ingest.publish_polled` in `ingest.py`.

## Feedback AZ and BA (29 September)
- `Card.waiting(since)` — an alarm newer than the last page reported: what an agent in another process asks once a second (`DomainAgent(alarm_waiting=...)`), instead of being woken by `on_alarm`.
- `_same` compares by `t_src` — the line's time on the member's clock, which `uplink.page` now keeps beside the shifted `t` — because the shift is taken afresh with every report and moves with how late the domain read it.
- `alive_at` reads every `rec/polled/<ingest>` of a cluster: one witness object per ingest, not one per cluster that the last writer owned.
- `AlarmHistory(max_lines=2000)`: the newest lines only; the object is `{events, cut_before}` (the first form, a plain list, still reads); lines older than `cut_before` are not taken back; `cut_before(member)`. `DomainAlarms.list` keeps the page first and reads the history after, and a window reaching past `cut_before` gets `history_cut_before` and a sentence.
- Tests: `test_an_agent_the_card_cannot_wake_asks_it_once_a_second`, `test_the_history_keeps_an_alarm_once_however_late_the_domain_reads_the_report`, `test_a_storm_pushes_its_oldest_out_of_the_history_and_the_list_says_so`.

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

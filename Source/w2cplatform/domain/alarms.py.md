# alarms.py — Lesson 14: one list of alarms from every member; an alarm that leaves at once; silence as an alarm, with a witness; a week of history at the domain

**Role in the module.** The brief's `MergedIndex` over members. The domain merges each member's alarms from the page in its report, newest first, a page per member, with what it could not hear said (Lesson 1's honesty). The member that goes dark is the one whose last alarm matters, so: the card wakes the agent on an alarm; a silent member is answered from its last report; its silence is an alarm of its own; and a witness a spec declares (`domain.witness`) tells "alive, not reporting" from "gone".

## Module-level names
- `BUCKET = 600` — М10A's bucket span. `WINDOW = 86400` — a page's span.
- `HISTORY = "domain/alarm-history"` — in the domain's object store: one object per member, a rolling week.

## `class Card(sub, root, unit="1", ...)` — a member's events of subsystem `sub` on its card (`root`, the caller's: an empty one is refused), as М10A's buckets. `observe(...)`, and on an alarm `on_alarm()` (the agent's `wake`); `alarms(since, until, limit)`; `waiting(since)` for an agent in another process.

## `pages(card, now, per_member=100, window=WINDOW)` — the page the agent puts in its report: `{"alarms": …}`.

## `class ReportedDoor` — a member's alarms from its last report. `alarms(...)` raises `Unreachable` when the report is older than `lost_after`; `last(...)` is the page of that last report anyway, `known_until` its time.

## `class AlarmHistory` — `keep(member, events)`, `read(member, since, until)`, `cut_before(member)`; at most `max_lines` (2000), the newest, the object `{events, cut_before}`.

## `class DomainAlarms(fed, doors, wall, per_member, history, lost_after, ref_of=str)`
`alive_at(ref)` → `(time, cluster)` of the latest word any witness gives of that unit (`declared.witnesses()`: `<sub>/<witness>/*` = `{ts, cluster, units: {ref: seconds since}}`). `ref_of(member)` is the name the witnesses know a member's unit by — the member's own name unless a subsystem names its boxes otherwise and passes its own. `list(since, until=None)` → `{events, members, complete, sentence}`, a synthetic `silent` or `not_reporting` line for each silent member — READ ONLY: it writes nothing. `keep()` is the pass's step that writes the week — every reporting member's whole page into `history` — run by the signer's pass alone (ADR-0032: every output of the holder's pass has one writer); the domain's console answers `GET /domain/alarms` with `list`.

## Notes
- `_same` compares by `t_src` — the line's time on the member's clock — because the shift onto the domain's clock is taken afresh with every report.
- The agent's side is `DomainAgent.wake/due/report_now`; a witness is a subsystem's process, which writes one object per witnessing process.

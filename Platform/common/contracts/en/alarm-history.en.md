# The alarm history contract: the history of a member at the holder, equality of lines, `cut_before`

This English text is the source; the Russian [`alarm-history.md`](../alarm-history.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): the holder writes the history, the domain console reads it — a contract,
not copies in chapters; the stage C guess C10-ALARM-SAME-LINE83, the Architect's decision of 2026-10-25). The owner is chapter
[P/08.9](../../../08-domain/spec/08.9-domain.norms.md) Н1.9. Participants: the writer — the holder pass, the process `domain`
(ADR-0032); the reader — the alarm list of the domain console ([P/10](../../../10-domain-console/spec/10-domain-console.norms.md) Н1.8, Н3
`alarms`: the merge of the page and the history); the backup copy of the holder (P/08.8 Н1.5 `objects`).

Moved from P/08.9 Н1.9 without a change of behaviour, together with the rule of a repeated line within one page (P/10 Н3 `alarms`
step 2; reconciliation of М11, A16); P/08.9 and P/10 refer here.

Normative keywords follow [the course canon](../../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The object `domain/alarm-history/<член>` is the family `alarm-history`: the form `Platform/08-domain/data/alarm-history.schema.json`,
the outcomes `Platform/08-domain/data/alarm-history.outcomes.tsv` ([form](../../../08-domain/data/alarm-history.schema.json),
[outcomes](../../../08-domain/data/alarm-history.outcomes.tsv)). A history line is a line of the alarm page of the member, as accepted:
`t` — by the domain clock (the section «Domain clock»), `t_src` — the `t` of the line as it came, by the member's clock. Times follow the canon of P/01.1 Н0
«Time in a row» (`Platform/common/data/codec.tsv`, the row `time`): the writer — at most three fraction digits.

## Domain clock

Moved from [P/10](../../../10-domain-console/spec/10-domain-console.norms.md) Н1.8 `clock` without a change of behaviour (layout audit, the Architect's decision of 2026-10-25, А-13):
the clock of a line is read by the holder pass (it writes the history, `events[].t`) and by the alarm list of the domain console.

```yaml
clock:         the time of a page line by the domain clock: t + (received_at − sent_at) of the last accepted report that
               carries this page (the fields of the last mark request, P/08.3 Н1.3); not page.to: a former page in a new report
               does not shift old alarms forward (the Architect's decision on R41-16 of run 41); t_src — t as it came
```

## History

```yaml
history:       the holder object domain/alarm-history/<член> {events, cut_before} — a sliding week, at most
               HISTORY_LINES lines, the newest ones; cut_before — from which moment the member is held whole: a number (domain clock),
               on creation of the history — 0, not null (reconciliation of М11, A13)
cut:           cut_before moves only on removal of lines and on an unappended line older than a week (`writer` below): lines with t < now − HISTORY_DAYS × 86400 removed —
               cut_before = max(cut_before, now − HISTORY_DAYS × 86400); the oldest ones beyond HISTORY_LINES removed —
               cut_before = max(cut_before, t of the newest removed one); beyond HISTORY_LINES the newest by t (domain clock) stay,
               with equal t — stably by the order of the history (the earlier accepted are removed first), the remaining ones — in the former
               order (AH-SAME52-01, AH-CUT52-01, the Architect's decision of 2026-10-25); nothing removed and cut_before not moved — the history object and its bytes are the former ones, there is no write, and a silent
               member does not move the rev of the backup copy (P/08.8 Н1.5 rev); the initial 0; cut_before does not decrease (reconciliation of М11,
               A14; the Architect's decision on cammeta-go М11-03 № 11)
  events:      the page lines as accepted: t — by the domain clock (the section «Domain clock»), t_src — as it came
HISTORY_DAYS:  7
HISTORY_LINES: 2000
writer:        only the holder pass (the process domain, ADR-0032): after accepting a report, append the lines of its page
               that are absent (same_line below); a page line with t < now − HISTORY_DAYS × 86400 is not appended: cut_before = max(cut_before, t of the newest such one), and a repeat
               of the same line by the next pass changes nothing (C08-ALARM-OLD-LINE-01); the alarm list (P/10 Н1.8) only reads the history
in_copy:       the history travels with the backup copy of the holder (P/08.8 Н1.5 objects)
```

## Equality of lines

```yaml
same_line:     lines a and b are one line when (t_src, kind, subsystem, unit) are equal: t_src — as it came, by the member's clock
               (the clock correction changes from report to report, therefore not t); id, t and the other fields do not enter the equality;
               t_src is compared as a number (the time canon of P/01.1 Н0: 990 and 990.0 are one value), it is stored as it came, the bytes
               do not change; kind, subsystem, unit: absent = absent, absent ≠ null, present ones — equality
               of JSON values, not of text (AH-SAME52-01, AH-CUT52-01, the Architect's decision of 2026-10-25)
page_repeat:   a repeat by same_line within one page — the first line in the order of the page is taken, the others are dropped
               (reconciliation of М11, A16)
```

The merge of the page and the history in the output of the domain console (a page line before a history line, the window `[since, until]`, the silence
line) is P/10 Н3 `alarms`, by `same_line` from here.

## Vectors

The package [`alarm-history`](../../vectors/alarm-history/README.md): the equality of lines (`same`), a repeat in a page (`page`), the write
of the holder (`write`: creation with `cut_before` 0, no repeats by `same_line`, removal by the week and movement of `cut_before`,
nothing removed, equal `t` at the boundary `HISTORY_LINES`); `same` — also `t_src` 990/990.0, absent/`null` (AH-SAME52-01, AH-CUT52-01).
The merge of the page and the history is the package `alarms` of lesson P/10.

## Correspondence to former lessons

From P/08.9 Н1.9 (the block whole; the norm P/08.9 — by `note` of [id-map](../../id-map.tsv)) and P/10 Н3 `alarms` step 2 (a repeat in
a page); they refer here (C10-ALARM-SAME-LINE83).

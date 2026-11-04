# Vectors of the alarm list

This English text is the source; the Russian translation `ru/vectors/alarms/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of the function `alarms(input)` of the domain console — the alarm list of the members at the holder: the state of each member (`ok`,
`silent`, `not_reporting`, `never`, `unreadable`), the silence row, the witnesses, the domain clock at the lines of the page, the history without
repeats, the window and the phrase `sentence`. The owner is lesson P/10 ([norms](../../spec/10-domain-console.norms.md) Н1.8, Н3 `alarms`,
Н5 `alarms`; the Architect's decision on the review analysis of stage A 8–10, № 8: the function `alarms` and its vector are at the domain console).
The history that the function reads is written by the process `domain` ([P/08.9](../../../08-domain/spec/08.9-domain.norms.md) Н1.9);
the alarm page of a member — by the agent ([P/09.1](../../../09-agent/spec/09.1-agent.norms.md) Н1.10). The bytes are written by «Спецификация»
(ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows 01–15 were transferred from the inputs of the command `alarms` of the acceptance of М11/11 (`inputs/alarms-*.json`, sc. 04) without a change of the bytes
of the values: only whitespace and line breaks outside JSON strings are removed; `case` is the name of the input file; the expectation `ok <JSON>` is the cell
`expect` without whitespace outside strings, `@exit 2` — as a string (the plan of the move of lesson 10, § 3, В7; the Architect's decision on the plans
8–10, ADR-0083 addendum (14) item 17). Scenario 04 of the acceptance of М11/11 and its inputs `alarms-*` are removed by the move of lesson 10: the table is
the only source of these cases.

## Run

Without a stand: the function of an implementation (the command `alarms`, the norms «Implementation decides» item 1) gets the input (the column `input`) and
gives the output; `expect` is a subset of the fields of the output (`@absent` — no such field) or `@exit 2` (the input is out of form: the norms Н5
`exit`). The `@exit 2` rows are `alarms-15-lost-after-negative` (`lost_after` not > 0) and `alarms-17`…`alarms-23` (the other cases of
code 2 of Н5 `exit`). A page out of the form of P/09.1 Н1.10 — the outcome 0 `unreadable`, not code 2 (rows 06, 12, 24–26).
Who performs it — the domain console (`10-domain-console`, P/10 Н3 `alarms`, Н1.8, Н5 `alarms`). The process `domain` (`08-domain`) does not perform it: it writes the history that the function reads (P/08.9 Н1.9 `writer`; its writing without repeats — the package `alarm-history`); the agent (`09-agent`) writes the alarm page of a member (P/09.1 Н1.10) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Input

- `now` = 1760000000, the window — a day (`since` = `now` − 86400, `until` = `now`; except rows 08, 27), `lost_after` 45 (except row 15);
- the members: `last_report` and `received_at` — the domain clock, `sent_at` — the member clock of the same report (at the vectors — `page.to`; with
  `page` not an object — a number, as `received_at`: `null` at a member with a report — code 2, H14, row 19), `page` — the page of P/09.1 Н1.10 (`"garbled"` — does not read; `null` — none), `history` —
  the history object of P/08.9 Н1.9; `reported: "garbled"` instead of `last_report`, `received_at`, `sent_at` — the mark is read, out of form (C10-REPORTED-OUTCOME-1D6);
- `witnesses` — the witness objects `{sub, name, ts, cluster, units}` (the norms Н1.8 `witness`).

The names of the subsystems and the units in the input (`testsub`, `testsub/c1`) are data of the input: the vector does not depend on the bytes of the manifests of the catalogue.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is, at the rows 01–15, the scenario and the step
of the acceptance of М11, at the rows 16–27 — the checked case and its norm (an item of P/10 or a case `C10-…`).

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 27 rows: 19 computed, 8 `@exit 2` | `input` — the input of the command `alarms` as JSON text → `expect`: `{events, members, complete, sentence}` or a part of it |

| Rows | What they check |
|---|---|
| 01–10 | all answered; a storm — `truncated`, a quiet member is visible; silent — the silence row and the alarms of the last report; a witness later than the report — `not_reporting`, earlier — `silent`; never and does not read; the history without repeats, `history_cut_before`; the window; the clock correction; two witnesses |
| 11–14 | reconciliation of М11 09–12: `cut_before` 0 — the history from the start, there is no `history_cut_before` (A13); a page line not `alarm` — the page is `unreadable` (A15); a repeat of `same_line` in one page — the first one (A16); a tie of witnesses by `alive_at` — the smaller `alive_via` (A17) |
| 15 | `lost_after` −1 — the input is out of form, code 2 (H14) |
| 16 | the mark `reported` is read, out of form (`reported: "garbled"`) — the member is `unreadable`, there is no silence row, the other member is `ok` (C10-REPORTED-OUTCOME-1D6) |
| 17–23 | the second pass of the coverage audit of P/10 (G01): the input is out of form, code 2 — the member name not by the grammar; `page` without `last_report`; `sent_at` null at a member with a report (H14); `history` with `cut_before` null (A13); a witness without `ts` (H14); `reported` together with `last_report` (C10-REPORTED-OUTCOME-1D6); an extra field |
| 24–26 | the second pass (G01): the page is out of form — 0 `unreadable`, not code 2: `page` — the array `[]`; `from > to`; a line without `id` (A15) |
| 27 | the second pass (G01): the window `[since, until]` also for the silence row — `silent_since` earlier than `since`: there is no row, the member is `silent`, `known_until`, `silent_since` and `sentence` — as without the window |

The vectors were checked by the runs of the implementations of the acceptance of М11/11 (run 41, the reconciliation of М11 09–12) and by the text of the norms; on a discrepancy
the norm is right, «Спецификация» corrects the vector.

## Source log

The rows of `corrections.tsv` of the acceptance of М11/11 about sc. 04 and its inputs (the paths and numbers are the former ones, they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)):

| date | sample | fix |
|---|---|---|
| 2026-10-18 | 11/inputs/alarms-*; README | run 41 R41-16: the alarm clock — t + (received_at − sent_at) of the report; the input carries sent_at (at the vectors = page.to, the expectations are the former ones) |
| 2026-10-18 | 11/scenarios.tsv; inputs | run 41, mutations №52–54: all the reasons of an edit joined by «; » (two substrings); since > until — 400; two witnesses — the largest alive_at |
| 2026-10-19 | 04-alarms 11–14; inputs alarms-11…14 | reconciliation of М11 09–12 (A13, A15–A17): cut_before 0 at the start, a page line not alarm — unreadable, a repeat of same_line in a page — the first one, a tie of witnesses — the smaller alive_via |
| 2026-10-19 | 03-resolve 11, 04-alarms 15 | the expectation @exit 2 (the dictionary of М10/01, the Architect's decision on the reconciliation of М11, H14): the form of a trusted input — code 2, at both implementations by the norm |
| 2026-10-19 | 04-alarms 6; inputs alarms-06 | cammeta-go М11-11 № 12: at m2 with last_report, sent_at null — by Н5 (H14) the input is out of form, code 2, while the step waits for unreadable; sent_at as a number, page garbled is kept. The other inputs of the М11 vectors are reconciled with the rules of code 2 — there are no other mismatches (codes 2 — only at the steps @exit 2) |
| 2026-10-20 | the move | sc. 04 (15 steps) from М11/11 — the rows of this table (stage B; the plan of the move of lesson 10, § 3) |

Rows 17–27 — the second pass of the coverage audit of P/10 (audit-coverage-gemini 798e11a44, the draft G01; 2026-10-30): the expectations
were obtained by the command `alarms` of the frozen witnesses `cammeta-python` and `cammeta-go`
(`cammeta domain-vector alarms`) — both give the expectation of each row; the witnesses do not know the field `reported` (row 16 is red
at them), the code 2 of row 22 at them is «extra field», by the norm — `reported` together with `last_report`.

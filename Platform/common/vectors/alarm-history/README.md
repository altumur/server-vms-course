# Vectors: the alarm history — the equality of lines, a repeat within a page, the holder's write

This English text is the source; the Russian translation `ru/vectors/alarm-history/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the alarm history contract](../../contracts/alarm-history.md) (chapter P/08.9 Н1.9; the guess of stage C
C10-ALARM-SAME-LINE83, the Architect's decision of 2026-10-25). The participants are the holder's pass (the process `domain`) and the alarm list
of the domain console (P/10). The bytes are written by «Спецификация»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>op<TAB>input<TAB>expect<TAB>note`.
An alarm line in the input is `{id, class, kind, subsystem, unit, t, t_src}`.

| `op` | Input → output |
|---|---|
| `same` | `{a, b}` — two lines → `true` (one line by `same_line`) or `false` |
| `page` | `{events}` — the lines of one page → the `id` of the remaining lines in order (a repeat — the first one) |
| `write` | `{now, history, lines}`: `history` — `{events, cut_before}` or `null` (there is no history), `lines` — the accepted lines of the page (`t` already on the domain clock) → `{ids, cut_before, written}` of the history after the write: the `id` of the lines in order, `cut_before` and `written` — whether there was a write (nothing new and nothing removed — `false`, the object is the former one) |

The comparison is JSON by value. 16 rows: 8 `same` (including `t_src` 990 and 990.0, absent and `null`), 1 `page`, 7 `write` (creation with
`cut_before` 0, without a repeat by `same_line`, removal by the week and the movement of `cut_before`, nothing removed, equal `t` at
the boundary `HISTORY_LINES` 2000; AH-SAME52-01, AH-CUT52-01).

## Run

Without a stand: a side gives the input to its functions of equality, of the parsing of a page and of the write of the history (the store and the clock are replaced by
the input). The merge of a page and the history in the output of the domain console is the package `alarms` of lesson P/10.
Who performs is by `op`: `same` — the holder's pass (`08-domain`, a write without repeats) and the alarm list of the domain console
(`10-domain-console`); `page` — the domain console (P/10 Н3 `alarms` step 2); `write` — only the holder's pass (the contract,
`writer`) (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

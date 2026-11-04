# Vectors: the moment function — schedule, sun, object mode

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson V/07 ([the norms of chapter 6](../../../spec/07.6-auto.norms.md) Н1.2–Н1.5, Н1.7). The numbers were computed by the reference
automation engine from the consolem set `785824c` (`api/rule-engine.js`) and rechecked by an independent recomputation from the text of the norm;
the line `at` of the manual mode is a rule of the norm (Н1.5), the engine does not have it. The run — after the first stage C generation that has passed the platform
acceptance (ADR-0090 addenda (8), (9)).

Who executes them: the implementation of `auto`, by its own package command; the package `VMS/07-auto/moment` (the path in the export without `vectors/`).

## Files

| File | What |
|---|---|
| `world.json` | the input of all cases: `schedules`, `day_groups`, `modes` — the rows of the tables (V/07.6 Н1.1); `unreadable: true` at a group — the row is not read |
| `cases.tsv` | the cases: UTF-8, LF, the fields separated by TAB, the first line is the header |

## `cases.tsv`

- `case` — the name of the case; the prefix is the chapter's checklist: `w-` week, `n-` across midnight, `d-` day bounds, `b-` built-in, `g-` day groups, `t-` dates, `c-` cycle, `v-` deadline, `z-` zone, `s-` clock changes, `a-` sun, `m-` mode, `u-` unreadable group, `e-` the row has no field;
- `func` — `in_effect`, `object_mode` or `sun`;
- `arg` — `in_effect`: the `title` of a schedule from `world.json`; `object_mode`: the row `mode_current` as JSON `{mode, until, at}` (the time is in seconds, `at` 0 does not restrict) or `-` — there is no row; `sun`: JSON `{date, lat, lon, utc_offset_hours, event}`, `event` — `rise`, `set`;
- `tz` — the zone of the moment, for `sun` — `-`;
- `t` — the moment in RFC 3339 UTC, for `sun` — `-`;
- `expect` — `in_effect`: `true`, `false`, `unknown` (the prefix `u-`); `object_mode`: the `name` of the mode; `sun`: the minute of the day or the word `day`, `night`;
- `why` — an explanation, not compared.

## Package command

Per the common platform acceptance README («Единая команда пакета векторов»): the profile of the implementation `auto` declares `vectors` →
`VMS/07-auto/moment`: its own command with `{input}`. The input is a JSON file `{format, package, table, case, variant, cells, files}`: `cells` —
`func`, `arg`, `tz`, `t` as the cell string, `files` — `world.json`. The output is the value of the column `expect` as a string.

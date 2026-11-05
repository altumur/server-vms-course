# Vectors: the manifest series `metrics[]`

This English text is the source; the Russian translation `ru/vectors/metrics/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.5 ([norms](../../spec/06.5-console.norms.md) Н3 «Ряды манифеста metrics[]»; stage C guess
C06-METRICS-DSL-33-01, the Architect's decision of 2026-10-25). The participant is the cluster console (`GET /metrics`). The bytes are written by
the Specification; the expectations were obtained by the course witness over the same input (the behaviour was moved without a change), except
`garbled-two-elements` — by the norm: the witness counted a numeric field common to two elements once (C06-METRICS-GARBLED-PER-ELEMENT-01).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object:

| Field | Value |
|---|---|
| `sub` | the series prefix (`metrics.prefix`) |
| `now` | the wall seconds of the console |
| `metrics` | the elements `metrics[]` of the manifest (usually one; a repeated `name` — two) |
| `heartbeats` | `{<worker>: <heartbeat without worker>}` — the heartbeats read by the console (the heartbeat fields and `status`) |
| `live` | the workers whose heartbeat version changed within the last `LOST_AFTER` (no field — empty) |
| `tables` | `{<table>: {<row name>: {<element>: <text>}}}` — the readable rows of the manifest tables |
| `held` | the row names of the places table held by a live hold `<sub>/holds/<name>` |

**Output** — `{"lines": [<output line>…], "garbled": <n>}`: the `/metrics` lines of these elements in order (with `# TYPE`) and the number of
fields whose unreadable count increased (`<sub>_console_rows_garbled{table="field"}`). The comparison is the array of lines byte for byte
and the number.

29 rows: all the keys — `name` (and a repeat), `type`, `labels`, `from` (`heartbeat`, `status`, the segment `<name>`), `agg` (`value`, `flag`,
`age`, `label`, `count`, `sum`, `max`, `histogram`), `equals`, `when`, `default`, `live`, `count`, `where` (a word and a list), `unheld`,
`unless`, `buckets`, `label`, `values`; the value is written in the canonical JCS number notation (P/06.5 Н3: an integer < 1e21 in digits,
otherwise the shortest ECMAScript notation — 1e+21, 1e-7, 1234567.5), escaping of a label; a boolean value in a numeric field
(`value`, `sum`: true — 1, false — 0); rounding half to even for `age` (0.25, 0.35, 0.45) and `_sum` (7.0625) — C06-METRICS-ROUND-91-01.

## Run

Without a stand: the side gives the input to its own construction of the series (the reads are replaced by the input) and compares the lines.
Who executes it is the console (`06-console`, `GET /metrics`: P/06.5 Н3 «Manifest series `metrics[]`»). The manifest loader (`02-installer`) checks only the form of the element `metrics[]` (P/02.1 «Form», the field `metrics`) and does not build series; the heartbeats and the table rows of the input are written by their owners (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `06-console/metrics` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

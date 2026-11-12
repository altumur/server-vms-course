# Vectors: the manifest series `metrics[]`

This English text is the source; the Russian translation `ru/vectors/metrics/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter P/06.5 ([norms](../../spec/06.5-console.norms.md) N3 «Manifest rows metrics[]»). The participant is the cluster console (`GET /metrics`).
In `garbled-two-elements`, the common numeric field is counted separately for each of the two elements.

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

29 rows.

## Run

Without a stand: the side gives the input to its own construction of the series (the reads are replaced by the input) and compares the lines.
Who executes it is the console (`06-console`, `GET /metrics`: P/06.5 N3 «Manifest series `metrics[]`»). The manifest loader (`02-installer`) checks only the form of the element `metrics[]` (P/02.1 «Form», the field `metrics`) and does not build series; the heartbeats and the table rows of the input are written by their owners (a row is executed by the role whose norm calls its function).

## Vector wire

The wire of `cases.tsv` (judge-only: checking material outside M) is set by the `06-console/metrics` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

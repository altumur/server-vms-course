# Vectors: projection of the contender marks into `name_conflict` and `name_conflicts`

This English text is the source; the Russian translation `ru/vectors/contender-projection/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter P/06.5 ([norms](../../spec/06.5-console.norms.md) N3 «/servers» «Contenders»). The participant is the cluster console (`/servers`
`WorkerRow.name_conflict`, the series `<sub>_name_conflicts` of `/metrics`). The freshness of a mark is the [observation contract](../../../common/contracts/observation.md)
«Freshness of a contender mark» (the boundary is the package `contender-fresh`). The rows follow the text of the norm, the rule is there, not here.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object `{workers, marks}`: `workers` — the names of the workers of the output; `marks` — the marks
`{key: "<name>/<box>", name, state, age}`: `key` — the part of the key after `<sub>/contenders/`, `name` and `state` — fields
of the mark object, `age` — the age of the observed version on the console clock, s.

**Output** — `{name_conflict: {<worker>: bool}, name_conflicts: n, name_conflict_unreadable?: [<worker>…]}`:
`name_conflict_unreadable` — the workers under whose name there is a fresh unreadable mark (the conflict is counted in
`name_conflict`, `name_conflicts` as well), in ascending order of bytes; the key is absent when there are none; the comparison is JSON by
value.

7 rows.

## Run

Without a stand: the side gives the input to its own computation of `name_conflict` and `name_conflicts` (the reads of the marks and the clock are replaced by the input).
Who executes it is the console (`06-console`: `WorkerRow.name_conflict` and the series `<sub>_name_conflicts`, P/06.5 N3 «/servers» «Contenders»). The controller (`04-controller`) does not execute it: it does not read the contender marks, the field `name_conflicts` of its pass report is its own count and does not enter the console series (P/06.5 N3 «/metrics — text»); the marks are written by the worker (`03-worker`, P/03.2 N1.4a) (a row is executed by the role whose norm calls its function).

## Vector wire

The wire of `cases.tsv` (judge-only: checking material outside M) is set by the `06-console/contender-projection` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

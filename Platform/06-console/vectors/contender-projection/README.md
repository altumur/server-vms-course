# Vectors: projection of the contender marks into `name_conflict` and `name_conflicts`

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.5 ([norms](../../../spec/06.5-console.norms.md) Н3 «/servers» «Соперники»; stage C guess
C06-CONTENDER-PROJECTION-33-01, the Architect's decision of 2026-10-25). The participant is the cluster console (`/servers`
`WorkerRow.name_conflict`, the series `<sub>_name_conflicts` of `/metrics`). The freshness of a mark is the [observation contract](../../../../common/contracts/observation.md)
«Свежесть метки соперника» (the boundary is the package [`contender-fresh`](../../../../common/vectors/contender-fresh/README.md)). The bytes
are written by the Specification; the rows follow the text of the norm, the rule is there, not here.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object `{workers, marks}`: `workers` — the names of the workers of the output; `marks` — the marks
`{key: "<имя>/<коробка>", name, state, age}`: `key` — the part of the key after `<sub>/contenders/`, `name` and `state` — fields
of the mark object, `age` — the age of the observed version on the console clock, s.

**Output** — `{name_conflict: {<воркер>: bool}, name_conflicts: n, name_conflict_unreadable?: [<воркер>…]}`:
`name_conflict_unreadable` — the workers under whose name there is a fresh unreadable mark (the conflict is counted in
`name_conflict`, `name_conflicts` as well), in ascending order of bytes; the key is absent when there are none (В7 item 3, the Architect's decision of 2026-10-28, П1; row 22 of the list); the comparison is JSON by
value.

7 rows: three marks of one name (two `refused` and `waiting`), the mark «-», any `state`, the boundary 300 / 300.001, `name` ≠
the key segment (an unreadable fresh mark — a conflict with the flag), a name without a worker, a fresh and a stale one under one name.

## Run

Without a stand: the side gives the input to its own computation of `name_conflict` and `name_conflicts` (the reads of the marks and the clock are replaced by the input).
Who executes it is the console (`06-console`: `WorkerRow.name_conflict` and the series `<sub>_name_conflicts`, P/06.5 Н3 «/servers» «Соперники»). The controller (`04-controller`) does not execute it: it does not read the contender marks, the field `name_conflicts` of its pass report is its own count and does not enter the console series (P/06.5 Н3 «/metrics — text»); the marks are written by the worker (`03-worker`, P/03.2 Н1.4а) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

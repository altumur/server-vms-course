# Vectors: the judgement of a slot row

This English text is the source; the Russian translation `ru/vectors/slot/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the slot contract](../../contracts/slot.md) (chapter P/03.2 N1.4; C140-SLOT-TIME-01, the Architect's decision 2026-10-26).
The participants are the worker (capture, renewal), the controller (the slot judge), the console, the agent, the pool contract. The bytes are written by «Specification»;
the rows are by the text of the contract, the norms do not change.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{row, age}`: `row` — the elements of the row `<sub>/slots/<name>` as text (`holder`, `until`, `released`, `gen`), `age` —
the age of the observed version on the judge's clock, s (the observation contract «Observation of a version»). **Output** — `{state}`: `held`, `lapsed`,
`released`, `taking`, `torn`; at `torn` also `takeable` — whether it may be captured by this version (gen reads and the version
has been observed for no less than `TORN_STILL`; P/03.2 the outcomes `/until`, `/gen`). The comparison — JSON by value.

11 rows: held, the boundary `SLOT_TERM` (44.999 — held, 45 — lapsed), released, taking, a finite `until` in the past, `until`
of the order of 1e308 and beyond binary64 (MAY-UNTIL-D8-01), the boundary `TORN_STILL` (49.999 and 50), an unreadable `gen`.

## Run

Without a stand: a side gives the input to its judgement of the slot (the reading and the clock are replaced by the input). The transitions (capture, renewal,
the leaving of units) — the acceptance scenarios of P/03.2, P/04 and reading.
Who performs it — the capture and the renewal of the worker (`03-worker`, P/03.2 N1.4, N3 «capture») — all rows; the controller (`04-controller`, P/04 N3 «fate», «leaving») — the field `state` of all rows, `takeable` is needed only by the capture of the worker. They do not perform it: the console (`06-console`) shows the fields of the row (`slot_garbled`, `released`, `slot_taking`, P/06.5 N2) without the terms `SLOT_TERM` and `TORN_STILL`; the agent (`09-agent`) judges the liveness of a slot on a member by its own rule by `until` (P/09.1 N1.2 `liveness`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

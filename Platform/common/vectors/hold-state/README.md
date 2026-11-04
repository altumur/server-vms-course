# Vectors: the effective hold of a place

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../../contracts/observation.md) «Hold of a place» (stage C guess C06-WHERE-PLACE-HOLD-33-01,
the Architect's decision 2026-10-25). The participants are the console (`/where/<table>/<place>`, [P/06.5](../../../../06-console/spec/06.5-console.norms.md)
Н3) and the worker taking a place ([P/03.2](../../../../03-worker/spec/03.2-worker.norms.md) Н3 «take_place»: the same relation to
`LOST_AFTER + HOLD_SKEW`). The bytes are written by «Спецификация»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

| Input field | Meaning |
|---|---|
| `hold` | the row `<sub>/holds/<place>` by the form (P/03.2 Н1.3): `{by, holder, released, gen}`, or `null` — there is no row |
| `hold_age` | the age of the observed version of the hold row on the monotonic clock of the observer, seconds |
| `heartbeat` | the heartbeat of the worker `by` (`{worker, instance}`) or `null` — there is no heartbeat |
| `heartbeat_age` | the age of the observed version of the heartbeat, seconds |

**Output** — `{"active": true | false}`. 10 rows: the age 0, 49.999, 50; the heartbeat 45 and 45.001; another instance; `released`; an empty
`holder`; no heartbeat; no row.

## Run

Without a stand: a side gives the input to its judgement «удержание действует» (the observation memory and the clock are replaced by the input).
The freshness of the heartbeat as a boundary — the package [`fresh-age`](../../fresh-age/README.md).
Who performs it — the console (`06-console`: the judgement «удержание действует» in `/where/<table>/<place>` and `held_by`, P/06.5 Н3, P/06.1 Н1). The worker taking a place (`03-worker`) shares with it only the boundary 45 + `HOLD_SKEW`, does not judge the holder's heartbeat and does not perform the table (P/03.2 Н3 «take_place»); the controller (`04-controller`) reads the holds only to account for places at the decommission of a server (P/04 Н1.1) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

# Vectors: the freshness of a contender mark — the age of the observed version → fresh

This English text is the source; the Russian translation `ru/vectors/contender-fresh/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../contracts/observation.md) «Freshness of a contender mark: `CONTENDER_FRESH`» (stage C guess
C06-CONTENDER-FRESH-33-01, the Architect's decision 2026-10-25). The writer of the mark is the worker
([P/03.2](../../../03-worker/spec/03.2-worker.norms.md) N1.4a, `CONTEND_EVERY`); the reader is the console (`WorkerRow.name_conflict`
`/servers`, the series `name_conflicts`, [chapter 6.5](../../../06-console/spec/06.5-console.norms.md)). The bytes are written by «Specification»;
the rows are by the text of the contract.

## Rule

- `CONTENDER_FRESH` = 300 s;
- **fresh** — the age of the observed version of the mark ≤ `CONTENDER_FRESH`; older — the reader does not take the mark into account.

The function is pure: the input is the age in seconds (a number, a fraction is admissible), the output is fresh or not. How the age is obtained
(the monotonic clock of the reader, the first look — 0, the field `at` — a display) is the contract, the section «Observation of a version»; an unreadable
mark — as older: this is a reading of the form, not an age, it is not in the table — it is checked by reading.

## `fresh.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header. The fields `case`, `age`,
`fresh`, `note` are as in the package [`fresh-age`](../fresh-age/README.md) (`age` — a JSON number, `fresh` — `true` | `false`).

6 rows: 0 (the first look), 299, 300, 300.0, 300.001, 301.

## Run

Without a stand: a side gives `age` to its judgement of the freshness of a mark and reconciles with `fresh`, over the number as is, without
rounding.
On a discrepancy the contract is right, «Specification» corrects the vector.
Who performs it — the console (`06-console`: the freshness of marks for `WorkerRow.name_conflict` and the series `name_conflicts`, P/06.5 N3 «/servers»). The worker (`03-worker`) only writes the mark and does not judge the freshness of foreign marks (P/03.2 N1.4a; ACC-VECTORS-CONNECT-02, the Architect's decision 2026-10-26); the field `name_conflicts` of the controller report (`04-controller`, P/04 N1.2) is not counted by this rule (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Native outcome

Code 0 and the value of the column `fresh` — `true` or `false` (one expectation column — the common rule «Vectors» of [the common acceptance
README](../../acceptance/README.md); as at [`fresh-age`](../fresh-age/README.md)); the input is the cell `age`; the Architect's decision 2026-10-27.

## Vector wire

The wire of `fresh.tsv` is set by the `common/contender-fresh` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

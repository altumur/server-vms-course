# Vectors: the schema check at start

This English text is the source; the Russian translation `ru/vectors/schema/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the schema contract](../../contracts/schema.md) (chapter P/06.6; C06-SCHEMA-WIDE-32-01, the Architect's decision
2026-10-25). The participants are the processes that check the schema at start: the controller, the worker, the resource, the console, the domain processes.
The bytes are written by «Specification»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{SCHEMA, row}`: `SCHEMA` is the current build number, 1 in the current specification and these vectors; `row` is `platform/schema` elements as text (`{version, at}`), or `null` for an absent row. Synthetic positive support of a former layout under SCHEMA=3 is not required.
**Output** — `{start: true, version}` (start; the version as a decimal string) or `{refuse: "too_new", n}` (the schema is newer; `n` —
the exact N as a decimal string) or `{refuse: "not_a_form"}`. The comparison — JSON by value. «Refusal — code 2» is an outcome
of the process at start; the function of the package in the single command `vectors` answers with code 0 and the output object `{refuse…}`
(ACC-VECTORS-CONNECT-04; ACC-SCHEMA-REFUSE-EXIT-01, the Architect's decision 2026-10-27).

## Run

Without a stand: a side gives the input to its schema check function (the reading of the row is replaced by the input). A read error (wait for
availability) and the check by the worker after the renewal of the slot — by reading and by the acceptance scenarios of the participants.
Who performs it — every process whose norm checks the schema at start: the worker (`03-worker`, P/03.2 N3 «schema check by the worker»), the controller (`04-controller`, P/04 N3 «controller start — schema check»), the resource (`05-resource`, P/05 N3 «resource start — schema check»), the console (`06-console`, P/06.6 N3 «console start — schema check»), the process `domain` (`08-domain`) and the agent (`09-agent`) — by P/02.4 N1.12, the domain console (`10-domain-console`, P/10 N1.1). The console module (`07-console-module`) takes `/schema` ready-made (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/schema` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

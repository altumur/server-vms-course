# Vectors: the process instance — a given `INSTANCE_ID`

This English text is the source; the Russian translation `ru/vectors/instance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the process instance contract](../../contracts/instance.md) (chapter P/03.2; INSTANCE54-02, the Architect's decision
2026-10-25). The participants are the processes that write an instance (the worker, the resource, the process `domain`, the writers of the event journal).
The bytes are written by «Спецификация»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{INSTANCE_ID}`: the value of the environment variable. **Output** — `{instance}`: the instance as the process writes it, or
`@refuse` — a refusal to start, code 2. The comparison — JSON by value, `instance` — byte for byte.

`cases.tsv`, 5 rows: accepted; leading zeros of the pid and uppercase hex — as given; a pid of zeros, 5 hex, a pid with a sign — a refusal.

## `box.tsv` (INSTANCE130-SOURCES-01)

The same file rules. **Input** — `{INSTANCE_ID?, BOX_ID?, machine_id, hostname}`: the environment variables (no key — not
set), the content of `/etc/machine-id` as a JSON string or `"@missing"` (no file), `"@error"` (a read error), the hostname
of the system as a string. **Output** — `{box, source}`: the box and the source taken (`BOX_ID`, `machine-id`, `hostname`), or `@refuse`
— a refusal to start, code 2. 12 rows: BOX_ID; empty INSTANCE_ID and BOX_ID; BOX_ID not by the grammar — a refusal; machine-id — trimming,
the first line, absent, an error, empty, not by the grammar → hostname; the hostname is unfit — the refusal «no box name».

## Run

Without a stand: a side gives the value to its instance function (the environment is replaced by the input). The computed form (without
`INSTANCE_ID`) depends on the machine — by reading.
Who performs it — every process whose norm writes its own instance — both tables: the worker (`03-worker`, P/03.2 Н3 «start()» step 2 — the slot, the heartbeat, the contender mark), the controller (`04-controller`, the writer of `audit/<роль>`, `by` of the rows of P/04 Н1.1), the resource (`05-resource`, the writer of `audit/resource`, P/05 Н1.2 `writer`), the console (`06-console`, P/06.4 Н1.2: `console/<экземпляр>`, `audit/console`), the process `domain` (`08-domain`, P/08.10 Н1.7 `holder` of the turn, P/08.9 `audit/domain`), the agent (`09-agent`, P/09.1 Н1.13 `holder` of the turn) and the domain console (`10-domain-console`, the event journal). The instance of a worker in a presence lock the resource reads ready-made (P/05 Н1.4) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Native outcome

The package has no separate command contract — the common rule «Vectors» of [the common acceptance README](../../acceptance/README.md)
(ACC-VECTORS-CONNECT-04, the Architect's decision 2026-10-26): the function answers with code 0 and one JSON value. The output object of the table or the JSON string `"@refuse"`; «отказ старта, код 2» is an outcome of the process, at the function of the package — `"@refuse"`
with code 0.

## Vector wire

The wire of `box.tsv`, `cases.tsv` is set by the `common/instance` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

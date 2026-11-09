# Vectors: the slot name

This English text is the source; the Russian translation `ru/vectors/slot-name/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the slot name contract](../../contracts/slot-name.md) (chapter P/03.2 N1.4; the guess of stage C POOL-ORDER-51-01, the Architect's decision
of 2026-10-25). The participants are the slot capture, the controller, the pool contract, the workers script, the console. The bytes are written by
«Specification»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>op<TAB>input<TAB>expect<TAB>note`.

| `op` | Input → output |
|---|---|
| `order` | `{prefix, names}` → the admissible names in the slot order (an array) |
| `next` | `{prefix, names}` → the next name `<prefix>-<max+1>` (a string) |
| `role` | `{prefix, name, server}` (`server` — the field of the worker heartbeat or `null` — there is no heartbeat) → `{server, n}` (`n` — a string of decimal digits, without overflow) or `"not_role"` |

The comparison is JSON by value.

## Run

Without a stand: a side gives the input to its functions of the order, of the next number and of the parsing of the name of a role process.
Who performs is by `op`: `order` — the slot capture (`03-worker`) and the place keeper of the pool contract (`04-controller`,
`06-console`); `next` — the slot capture (`03-worker`); `role` — «number above want» and the victim of shrinking (`04-controller`,
`06-console` by the pool contract); the workers script takes the numbers from its own unit instances and does not read the heartbeat — it does not perform
`role` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-26).

## Vector wire

The wire of `cases.tsv` is set by the `common/slot-name` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

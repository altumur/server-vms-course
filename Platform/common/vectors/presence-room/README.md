# Vectors: the count of `room` and `live`

This English text is the source; the Russian translation `ru/vectors/presence-room/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the presence lock contract](../../contracts/presence-lock.md) «Count `room`» (the guess of stage C PL-EXT-01, the decision of
the Architect of 2026-10-23). The participants are the resource (writes `room.<sub>`, `live.<sub>` by the door mark, P/05 N1.4) and the controller
(reads, P/04 N3 «order()», «free(s)»). The bytes are written by «Specification».

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.
`input` — `{prefix, server, HOST_MEMORY_MB, WORKER_MEMORY_MB, locks}`: the `slot.prefix` of the manifest and `SERVER_NAME` (by them the number
`n` of the name `<prefix>-<server>-<n>`; in all rows `w` and `srv-a`, C61-PREFIX-01), the values of the role file and the field `worker`
of each live lock of the role (the flock is held); `expect` — `{room, live}` as strings, as in the door row.

## Run

A side computes `room` and `live` by its own resource code from the input, without files, and compares with `expect` (JSON by value).
Who performs is the resource (`05-resource`); the controller does not perform the count: it reads `room`/`live` from the door row
([P/04](../../../04-controller/spec/04-controller.norms.md) N3 «free(s)»; ACC-VECTORS-CONNECT-03; the Architect's decision of
2026-10-27).

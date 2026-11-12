# Vectors: the victim of shrinking

This English text is the source; the Russian translation `ru/vectors/shrink-victim/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is lesson P/04 ([norms](../../spec/04-controller.norms.md) N3 «shrink()», `victim`; P/03.2 N1.4 the grammar of the name). The participant is
`<s>controller`. The bytes are written by the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header. A cell is read byte for
byte. Fields: `case`, `input` and `expect` — JSON text, `note`.

**Input** — `{prefix, want: {<server>: <want>}, workers: [{name, server, wanted?: bool}]}`: the live workers of the role, the names
`<prefix>-<server>-<n>` (P/03.2 N1.4); `want` — the target of the order row of each server on which there is a worker (an integer 1…99,
P/04 N1.4).
**Output** — `{victim: <name> | null}`: only the live top ordered number `n = want(server) > 1` is eligible on each server. A worker with `wanted: true` is the holder of a place with a readable places.wanted row; skip that whole server, never take its lower number instead. Missing wanted means false. Select the greatest remaining number as an integer, not by slot order; the base `-1` is never a victim; a live number above the want of its server is not a victim: the script stops it
, the end of the shrinking does not put it out; `null` — there is no victim.
Comparison — JSON by value.

Equal numbers on different servers — the smaller name of the server in UTF-8 bytes first, as the order of the candidates (N3
«shrink», the victim). Not covered: the check «each unit of the victim passes choose()» — by an acceptance step and by reading.

## Input not by form

The executor of the vector answers with code 2 (the cell `expect` — `@exit 2`) exactly to an input from the list: not a JSON object; `prefix` or
the name of a server not by the grammar (P/03.2 N1.4, P/02.4 N1.2); the name of a worker not `<prefix>-<server>-<n>` of its element, `n` — not
an integer 1…99 or with a leading zero; a repeat of a name; `want` is not an object, does not name the server of the worker or its value is not an integer
1…99; a present wanted is not a boolean. An integer — by the exact decimal value of the notation, as `x-integer` (LAYERS §3): `1.0`, `1e0` — 1; `1.5`, a boolean, a string, a number outside binary64 — not an integer; the number `n` in the name of a worker is a lexeme of the string, without a leading zero. The rest is outside the vector.

## Who executes

Who executes it is the controller (`04-controller`: the victim of shrinking, P/04 N3 «shrink», `victim`) — all the rows. The server script (`02-installer`) does not choose the victim: it stops the numbers above the ready `want` by its own rule (P/02.4 N1.5 `rules` 3, the vectors `workers-script`); the worker (`03-worker`) sees the ready `retiring` (a row is executed by the role whose norm calls its function).

The composed seams s36/s37 also require: run the actual victim choice, retiring/move/end decision and the existing P/02 server-script reconciliation, observing the target and physically selected stop number. A pure victim vector alone does not establish that composition.
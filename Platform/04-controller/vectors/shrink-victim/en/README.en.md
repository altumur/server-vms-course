# Vectors: the victim of shrinking

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson P/04 ([norms](../../../spec/04-controller.norms.md) Н3 «сократить()», `жертва`; ADR-0084 addendum (1) Р4, addendum (6); P/03.2 Н1.4 the grammar of the name). The participant is
`<s>controller`. The bytes are written by the Specification (ADR-0083, stage A, A6).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header. A cell is read byte for
byte. Fields: `case`, `input` and `expect` — JSON text, `note`.

**Input** — `{prefix, want: {<сервер>: <want>}, workers: [{name, server}]}`: the live workers of the role, the names
`<prefix>-<сервер>-<n>` (P/03.2 Н1.4); `want` — the target of the order row of each server on which there is a worker (an integer 1…99,
P/04 Н1.4).
**Output** — `{victim: <имя> | null}`: the largest number `n ∈ {2…want}` of its own server, the number — as an integer, not by the slot
order; the base `-1` is never a victim; a live number above the want of its server is not a victim: the script stops it
(Р28), the end of the shrinking does not put it out (ADR-0084 addendum (6); analysis of the review of stage B 6–7, № 42); `null` — there is no victim.
Comparison — JSON by value.

Equal numbers on different servers — the smaller name of the server in UTF-8 bytes first, as the order of the candidates (Н3
«сократить», the victim). Not covered: the check «каждая единица жертвы проходит выбрать()» — by an acceptance step and by reading.

## Input not by form (Р22)

The executor of the vector answers with code 2 (the cell `expect` — `@exit 2`) exactly to an input from the list: not a JSON object; `prefix` or
the name of a server not by the grammar (P/03.2 Н1.4, P/02.4 Н1.2); the name of a worker not `<prefix>-<server>-<n>` of its element, `n` — not
an integer 1…99 or with a leading zero; a repeat of a name; `want` is not an object, does not name the server of the worker or its value is not an integer
1…99. An integer — by the exact decimal value of the notation, as `x-integer` (LAYERS §3): `1.0`, `1e0` — 1; `1.5`, a boolean, a string, a number outside binary64 — not an integer; the number `n` in the name of a worker is a lexeme of the string, without a leading zero (C04-VECTOR-INT-VALUE-01). The rest is outside the vector (ADR-0084 addendum (2) Р22).

## Who executes

Who executes it is the controller (`04-controller`: the victim of shrinking, P/04 Н3 «сократить», `жертва`) — all the rows. The server script (`02-installer`) does not choose the victim: it stops the numbers above the ready `want` by its own rule (P/02.4 Н1.5 `rules` 3, the vectors `workers-script`); the worker (`03-worker`) sees the ready `retiring` (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

# Vectors: the neighbour of a unit by `near` (`by`, `of`, `prefer`)

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson P/04 ([norms](../../../spec/04-controller.norms.md) Н1.3 `near`; ADR-0091 item 10). The participant is
`<s>controller` (the preference when choosing a worker, Н3 «choose»). The bytes are written by the Specification. The vector checks only
the choice of the neighbour; that the worker holding it is preferable, and that without a holder there is no preference, — Н3 «choose», by reading.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

| Field | Value |
|---|---|
| `case` | the name of the row |
| `input` | a JSON object: `near` — the manifest key (`{sub, by?, of?, prefer?}`); `me` — my row (`id` and fields); `neighbours` — the live rows of the subsystem `sub` (`id` and fields); `refs` — a field of the neighbour → `<подсистема>/<семья>` of its `ref` (for the path of `prefer`); `rows` — the rows of the targets of the references: the key `<подсистема>/<семья>/<id>` → fields |
| `expect` | the id of the chosen neighbour; `""` — there is no neighbour |
| `note` | the rule of the norm |

The values of the fields are the text of a store row (P/06.1 Н1.2 `values_by_type`); the values of `prefer` are compared in the same
writing: `0` in `prefer` equals `"0"` of the row. An absent field is equal to nothing. The value of a field of `prefer` is a scalar (equality) or a list of scalars (OR over the list), as `affinity.strict` of P/04 Н1.3 (C04-NEAR-PREFER-SCALAR-01).

## Run

The side builds from `input` the choice of Н1.3 `near` with its own code, without a store: my value is the field `by` (without `by` — my `id`),
the value of the neighbour is the field `of` (without `of` — its `id`); the neighbours are the rows with an equal value; first those matching `prefer`
(AND over the fields, OR over the list; a segment of the path through `.` is a step by the reference field of the neighbour to a row of `rows`); among equals — by
`id` in UTF-8 bytes. The result is compared with `expect` byte for byte.
Who executes it is the controller (`04-controller`: the neighbour by `near`, P/04 Н1.3, the rank of the preference in Н3 «choose») — all the rows. The installer (`02-installer`) only checks the fields `near` in the catalogue (P/02.1 Н3) and does not choose a neighbour; the worker (`03-worker`) gives the input by the phase `running` (P/03.4 Н1.1) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Stand command

`near-of` is the key `stand` of the profile `04-controller` (the section «Раскладка по процессам» of [the common acceptance README](../../../../common/acceptance/README.md)):
a template with `{input}` — the path of the file into which the runner writes the cell `input` of the row byte for byte; stdout — the UTF-8 bytes of the id
of the chosen neighbour exactly as `expect`, without a line feed and without a JSON wrapper; there is no neighbour (`expect` is empty) — an empty stdout;
code 0. An input not by the form of this README — code 2 (`@exit 2`). Another code or extra bytes — FAIL of the row.

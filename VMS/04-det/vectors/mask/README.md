# Vectors: the detector mask — the PGM grammar and the scale to the frame

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson V/04 ([the norms of chapter 1](../../../spec/04.1-det.norms.md) Н1.1 «Маска и размер кадра»). The participants are `detworker`
(the detector mask, V/04.2 Н1.2), `detjobworker` (the mask of a scan job, V/05.3 Н1.3) and `detedgeworker` (the mask of a traversal of the device
archive, V/06.3 Н1.4): the rule is one. The bytes are written by «Спецификация VMS»
(a decision of «Архитектор» on the second round of the review «потоки камеры», item 13). The run — after the first stage C generation
that has passed the platform acceptance (ADR-0090 addenda (8), (9)).

Who executes: the implementations of the subsystems `det`, `detjob` and `detedge`, each with its own package command (below); the rule is one, the package
is one: `VMS/04-det/mask` (the path of the package in the export without `vectors/`); V/05 and V/06 have no packages of their own — the lessons refer to this one.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` are explanations, empty lines are skipped. Five fields:

- `case` — the name of the case: `g-…` — the grammar of the body, `s-…` — the scale;
- `body` — the bytes of the mask body: parts joined by `+`, a part is a hexadecimal notation of bytes or `<hex>*<n>` (the bytes `<hex>`,
  repeated `n` times);
- `frame` — the frame size `<W>x<H>`; empty — only parsing of the body;
- `expect` — `refused` (the body is not by the grammar: the mask is not read, V/04.2 `failed`) or `ok <w>x<h>` (the mask size), and with a
  non-empty `frame` — `ok <w>x<h> <строки>`: the mask mapped onto the frame — the frame lines from top to bottom separated by `/`, each one is
  a hexadecimal notation of `W` bytes;
- `why` — an explanation, not compared.

## The package command

The single vector package command is per the common platform acceptance README («Единая команда пакета векторов»): the profiles of the implementations
of `det`, `detjob` and `detedge` each declare `vectors` → `VMS/04-det/mask`: their own command with `{input}` (its description
names the command, the section «Решает реализация» of the lesson's instructions). The input is a JSON file `{format, package, table, case, variant,
cells, files}`: `cells` — `body` and `frame` as the cell string as in the table (`body` — the notation of parts above, the command assembles the bytes from it;
`frame` — `<W>x<H>` or `""` — only parsing of the body), `files` — empty; there are no expectations and no `why` in the input.

The native outcome is the command's stdout: `{"result": "refused"}` or `{"result": "ok", "size": "<w>x<h>", "frame": [<строки кадра
hex>] | null}` (`null` — with an empty `frame` of the input); code 0 — computed, 2 — the input is not by the form (not expected for the package rows: code 2 is
a divergence of the row). The comparison is by fields: for `refused` — exactly `result`; for `ok` — `result`, `size`, `frame`; an extra field is
a divergence; the frame lines — by bytes (the case of hex does not matter). The package rows are executed by each of the three owners; if one of them has no record
`vectors`, the target is `blocked`.

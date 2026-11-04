# Vectors: the command line `exec`

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter [P/02.1](../../../spec/02.1-installer.norms.md) of the loader (Н1.3 `worker.exec`, the definition `execLine`; ADR-0091
addendum (4)–(6)). The participants are the loader (a refusal of the manifest with the key path) and the runner `w2c-run.sh` ([P/02.4](../../../spec/02.4-installer.norms.md)
Н1.9: `worker`, `domainworker`, `part` execute argv themselves, without a shell). The bytes are written by the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>exec<TAB>expect<TAB>note`.
`exec` — the value of the key as a JSON string; `expect` — argv as a JSON array (splitting by the space U+0020, the only one) or
`@refuse` — a string not by the grammar: the loader refuses `refused:value` with the key path, the runner does not execute it.

## Stand command `exec`

The key `stand` of the profile `02-installer` (the section «Раскладка по процессам» of [the common acceptance README](../../../../common/acceptance/README.md)),
following the pattern of `door-token-verify` ([the door-token vectors](../../../../common/vectors/door-token/README.md)): a template with `{input}` —
the path of the file into which the runner writes the bytes of the cell `exec` of the row as they are. stdout — exactly one JSON object in UTF-8 and LF,
code 0: `{"result":"ok","argv":[…]}` — compared with `expect` by JSON value, — or `{"result":"refused"}` (`expect` — `@refuse`). An input not by
form (not a JSON string) — code 2, stdout empty; a refusal by a rule on an input that is by form — code 0, `{"result":"refused"}` (guess of stage C I02-STAND-FORM, the Architect's decision of 2026-10-23). A different code, a different `result`, extra fields or bytes — FAIL of the row (guess of stage C I02-STAND, the Architect's decision of 2026-10-23).

## Run

The side parses `exec` with its own code of the loader or of the runner and compares argv with `expect` (JSON by value) or a refusal with `@refuse`.

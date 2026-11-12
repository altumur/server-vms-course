# Vectors: the command line `exec`

This English text is the source; the Russian translation `ru/vectors/exec/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter [P/02.1](../../spec/02.1-installer.norms.md) of the loader (N1.3 `worker.exec`, the definition `execLine`). The participants are the loader (a refusal of the manifest with the key path) and the runner `w2c-run.sh` ([P/02.4](../../spec/02.4-installer.norms.md)
N1.9: `worker`, `domainworker`, `part` execute argv themselves, without a shell). The bytes are written by the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>exec<TAB>expect<TAB>note`.
`exec` — the value of the key as a JSON string; `expect` — argv as a JSON array (splitting by the space U+0020, the only one) or
`@refuse` — a string not by the grammar: the loader refuses `refused:form` with the key path, the runner does not execute it.

The command’s native form and rule-refusal mapping are in the wire form below. An input outside the form exits with code 2 and empty stdout; a rule refusal on a well-formed input is a computed outcome, not a transport error. This does not change the installation or loader refusal named above.

## Run

The side parses `exec` with its own code of the loader or of the runner and compares argv with `expect` (JSON by value) or a refusal with `@refuse`.

## Vector wire

The wire of `cases.tsv` (judge-only: the table itself) is set by the `02-installer/exec` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.

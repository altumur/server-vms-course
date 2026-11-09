# Acceptance target registry

This English text is the source; the Russian translation `ru/acceptance/forms/targets.README.md` is derived from it and is not edited by hand (ADR-0121).

[`targets.tsv`](targets.tsv) is the registry of acceptance targets. The form is for every lesson. The rows of P/01 are filled first, with the same cells as their rows in [`runner-targets.tsv`](../runner-targets.tsv); the targets of the other lessons are only in that table for now. The row `P/01/production` exists only here: it is not in that table.

## Table form

UTF-8, physical LF rows, TAB-separated cells. The first row is the header:

```text
id\towner\tstand_commands\tstand_addresses\tkeys\trequirements\tnorm_anchors\tflags
```

`id` and `owner` are strings; every other cell is a compact JSON value. `id` is unique.

| Column | Meaning |
|---|---|
| `id` | Target name: a contract scope, not a selection of an implementation or of inputs. |
| `owner` | Module responsible for the target. |
| `stand_commands`, `stand_addresses`, `keys`, `requirements`, `norm_anchors` | The same cell forms and meanings as the columns of the same names in [the target requirements](../runner-targets.README.md). |
| `flags` | JSON array of flag words, closed list below; empty when none applies. |

| Flag | Meaning |
|---|---|
| `optional` | A profile that does not declare the interface of the target leaves the target not executed. Without this flag an absent interface blocks the target. At `P/01/production` the flag concerns only the functional verdict (N6.1 of the judge norms). |

These columns add no profile field, command, substitution, address or parameter.

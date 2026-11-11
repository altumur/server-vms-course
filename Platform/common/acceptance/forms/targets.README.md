# Acceptance target registry

This English text is the source; the Russian translation `ru/acceptance/forms/targets.README.md` is derived from it and is not edited by hand (ADR-0121).

[`targets.tsv`](targets.tsv) is the registry of acceptance targets. The form is for every lesson. This file holds the header; the rows of the targets of a lesson are in `forms/targets.tsv` of that lesson with this header, their routing rows in `forms/targets.routing.tsv` of that lesson, and the registry is assembled from them ([target registry and export lists assembled from the lessons](../README.md#target-registry-and-export-lists-assembled-from-the-lessons)). The rows of P/01 ([`Platform/01-store/forms/targets.tsv`](../../../01-store/forms/targets.tsv)) and P/02 ([`Platform/02-installer/forms/targets.tsv`](../../../02-installer/forms/targets.tsv)) are filled, with the same cells as their rows in [`runner-targets.tsv`](../runner-targets.tsv); the targets of the other lessons are only in that table for now. The rows `P/01/production`, `P/02.1/seams`, `P/02.4/seams` and `P/02.5/variants` exist only in the registry: they are not in that table. A routing row has one engine word, so the seams of P/02.1 and P/02.4 and the rights variants of P/02.5 are targets of their own beside the verdicts of P/02.1 and the scenarios of P/02.5. Of P/02, `P/02/vectors-canonical` and `P/02/vectors-workers-script` are the rows `P/02.2/vectors` and `P/02.4/vectors` of that table, named after their packages as the other `P/02/vectors-*`; the condition `rights_check` of the row `P/02.5/rights` of that table stands in the registry at `P/02.5/variants`, whose `check.tsv` calls `stand.rights-check`. The row `P/02.1/put` of that table is not a target: P/02.1 has no installation sample (the [acceptance of P/02.1](../../../02-installer/acceptance/1/README.md#no-installation-sample)).

## Table form

UTF-8, physical LF rows, TAB-separated cells. The first row that is not a note (`#`) is the header, and the columns are read by its names ([table header and columns by name](../README.md#table-header-and-columns-by-name)):

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

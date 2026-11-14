# Acceptance target registry

This English text is the source; the Russian translation `ru/acceptance/forms/targets.README.md` is derived from it and is not edited by hand.

[`targets.tsv`](targets.tsv) is the registry of acceptance targets. The form is for every lesson. This file holds the header; the rows of the targets of a lesson are in `forms/targets.tsv` of that lesson with this header, their routing rows in `forms/targets.routing.tsv` of that lesson, and the registry is assembled from them ([target registry and export lists assembled from the lessons](../tables.md#target-registry-and-export-lists-assembled-from-the-lessons)). The rows of P/01 ([`Platform/01-store/forms/targets.tsv`](../../../01-store/forms/targets.tsv)), P/02 ([`Platform/02-installer/forms/targets.tsv`](../../../02-installer/forms/targets.tsv)) and P/03 ([`Platform/03-worker/forms/targets.tsv`](../../../03-worker/forms/targets.tsv)) are filled, with the same cells as their rows in [`runner-targets.tsv`](../runner-targets.tsv). The P/04 targets are declared in [`Platform/04-controller/forms/targets.tsv`](../../../04-controller/forms/targets.tsv); their routing is in `forms/targets.routing.tsv` of that lesson (judge-only: the routing), and they have no duplicate in `runner-targets.tsv`. The rows `P/01/production`, `P/02.1/seams`, `P/02.4/seams` and `P/02.5/variants` exist only in the registry: they are not in that table. A routing row has one engine word, so the seams of P/02.1 and P/02.4 and the rights variants of P/02.5 are targets of their own beside the verdicts of P/02.1 and the scenarios of P/02.5. Of P/02, `P/02/vectors-canonical` and `P/02/vectors-workers-script` are the rows `P/02.2/vectors` and `P/02.4/vectors` of that table, named after their packages as the other `P/02/vectors-*`; the condition `rights_check` of the row `P/02.5/rights` of that table stands in the registry at `P/02.5/variants`, whose `check.tsv` calls `stand.rights-check`. The row `P/02.1/put` of that table is not a target: P/02.1 has no installation sample (the [acceptance of P/02.1](../../../02-installer/acceptance/1/README.md#no-installation-sample)). Of P/03, the seven seam targets `P/03.1/seams` … `P/03.7/seams` exist only in the registry; the seams of P/03.2, P/03.3, P/03.4 and P/03.6 have the engine word `seams`, because their directory also holds the `scenarios.tsv` of the target `P/03.K/stand` (judge-only: the scenario table). `P/03/vectors-creates-key` calls the stand command `creates-key` of its package, the one surface of its wire row, instead of the `vectors` record of that table. The stands `P/03.2/stand`, `P/03.3/stand`, `P/03.4/stand` and `P/03.6/stand` require a spoil interface only by its condition and only where a scenario of the directory spoils: `object_spoil` at P/03.2 and P/03.4, `row_spoil` at P/03.2; no scenario of P/03 puts an object, so the condition `object_put` of that table is not carried.

## Table form

UTF-8, physical LF rows, TAB-separated cells. The first row that is not a note (`#`) is the header, and the columns are read by its names ([table header and columns by name](../tables.md#table-header-and-columns-by-name)):

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
| `optional` | A profile that does not declare the interface of the target leaves the target not executed. Without this flag an absent interface blocks the target. A profile key of the column `keys` is not an interface: absent, it leaves the target not executed with the name of the key, with or without the flag (P/AC-R030; judge-only: the norms of the judge). At `P/01/production` the flag concerns only the functional verdict (N6.1 of the judge norms). |

These columns add no profile field, command, substitution, address or parameter.

## Routing execution

The judge-only routing table `targets.routing.tsv` has the required columns `id`, `engine`, `acceptance`, `scenarios`, `tables`, `parts`, `body`, `role`, `free`, `rights`, and the optional column `execution`. A lesson may omit `execution`; assembly supplies the compact JSON object `{}` in that column. Routing columns are read by name, in any order; unknown columns are ignored. A repeated column, a missing required column or a row of another width is a data error. The other routing cells keep the forms of their common header.

`execution` is a compact JSON object by [its schema](targets.execution.schema.json) (judge-only: the routing execution schema). Its closed fields are `stand`, `exclude` and `between`. Absence of a field does not override the engine family's existing rule: `{}` changes neither its selection nor its life cycle. A target name, a suffix such as `shared`, a flag or a lesson name sets none of these fields. A present cell must be an object; an empty cell, `null`, duplicate JSON keys and non-finite JSON numbers are data errors.

A nonempty `execution` applies only to the `scenarios.tsv` in the first directory of `acceptance`, for the engine words `run`, `l06`, `l11`, `store_group` and `power_stand`. That table must exist. The additional files of `tables` keep their own execution and life cycle; they do not join this group. The fields do not change the step requests or expectations, start additional roles or add a profile interface.

### Scenario selection

The runner first applies `scenarios` with its existing meaning: `all`, `none`, `first-step:<directive>`, `not-first-step:<directive>` or the inclusive numeric-prefix `range:<first>-<last>`. A first-step selector compares the decoded first request to the directive word, alone or followed by a space; the negative selector selects its complement. A range selects the decimal digit prefix of a scenario id; an id without that prefix is outside a range. The lower bound must not exceed the upper bound.

`exclude` is an array of unique, nonempty strings: exact scenario ids, not numbers, prefixes, ranges or patterns. It defaults to `[]`. Each id must occur in the set selected by `scenarios` before exclusions. The runner removes these scenarios and keeps the remaining ones in their table order, with each scenario's step order unchanged. An unknown or already unselected exclusion is a data error. Excluding a scenario does not execute it on another stand: another routing row must select it if it is needed separately. An empty final selection starts no stand and contributes no successful scenario.

### Stand lifetime

`stand: "shared"` creates one fresh stand for the whole final selection of this routing row, prepares it once before the first selected scenario, and executes the selected scenarios sequentially on it. Processes, stored rows and objects, replay claims and process memory persist between them; the runner resets scenario-local variables, current role and request-key bindings at every scenario boundary by their usual rules. `stand: "scenario"` creates and prepares a separate fresh stand for each selected scenario. Fresh means new process instances and separate empty row/object state and replay memory, followed by the manifest/configuration preparation of the stand; deleting only application rows is insufficient.

The runner isolates directories, ports and process groups from other targets and from repeated or parallel invocations. It does not share an instance across routing rows. It tears down a shared stand after its last selected scenario, or on an abort, and a per-scenario stand at each scenario boundary. At every teardown it applies the usual whole-group stop and cleanup order. Stop and cleanup failures keep their existing classes; an unclear cleanup stops the run under the ordinary cleanup rule, and the runner does not reuse an uncleared instance.

An ordinary mismatch keeps the continuation rule of the scenario dictionary. If a scenario aborts because its preparation or adapter failed, or a directive could not execute, a shared stand cannot be resumed with the next scenario or silently rebuilt: the remaining selected scenarios are `not_executed`, with the scenario/step or existing reason that caused the abort. Already observed outcomes remain in the report. Teardown still runs on every exit path.

### Between-scenario preparation

`between` defaults to `[]`. It is an array of preparations in the final selected scenario order, allowed only with explicit `stand: "shared"`. Each object has exactly `id`, `after`, `before`, `action`, `command`, `sub`, `timeout_s`. Its `id` is a word matching `[a-z][a-z0-9-]*`, unique within the routing row. `after` and `before` are exact selected scenario ids and must be consecutive after exclusions, with `after` first. A boundary occurs once in the array. Repeated ids or boundaries, reversed or nonconsecutive boundaries and boundaries with excluded or absent scenarios are data errors before the stand starts.

The dry plan names the stand scope, the final ordered selection and each preparation at its boundary. Preparation identity is `<target>#between/<id>` and is separate from the scenario-step inventory: it is neither a scenario nor an additional candidate test case. The run report retains its identity, boundary, start/deadline, observations and result. It must not fabricate a source step or alter a source scenario's step count. A failed preparation prevents `before` and every later scenario of that shared instance; their reason is `precondition:<target>#between/<id>`. The failure itself keeps its class and the target cannot be GREEN. All already completed steps keep their results, and teardown still runs.

The closed action word is `controller-pass`. `command` is the exact `{owner, section: "stand", key}` of a pass-report printing command already present in this target's `stand_commands`. The command receives the running instance's `{data}` and `{sub}` = `sub`; it prints the current controller report JSON object, or nothing when no report exists. The inspection command reads that same published report and does not create a pass or define another report form. The declaration adds no command, HTTP door, profile key or substitution. A missing required interface follows the target's normal interface/flag rules before any process starts.

After the last step of `after` completes, the runner starts one monotonic budget of the positive JSON integer token `timeout_s`, in seconds, and reads a fresh baseline with that command. It then polls the same command until a valid report object differs from the baseline by JSON value, ignoring object member order only. An absent baseline may be followed by the first valid object; absence or an unchanged object never proves completion. Baseline acquisition, all command invocations and waits share that one deadline; no poll restarts the budget, and no command may outlive it. A report captured before the boundary is not a baseline, and a sleep or the absence of a placement is not proof of a pass.

Expiry without a changed report is a failed preparation of class `stand`; unavailable or broken observation by the judge has the same class. Failure of the implementation's printing command, including an invalid nonempty report frame, keeps the ordinary profile-command class. The runner records the baseline and confirming report with secrets redacted; command exit alone is not confirmation. The operation proves a new completed pass after the boundary, not the candidate's placement result.

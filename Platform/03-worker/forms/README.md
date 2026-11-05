# P/03 forms and SDK seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export (ADR-0121).
These forms express the existing worker norms (ADR-0125 addendum (5)). The SDK has no new binary or HTTP API.

## Process inputs

[`daemon-flags.tsv`](daemon-flags.tsv) keeps the eight P/01 columns. `$NAME` denotes an environment value and `<name>` the optional
ordinary worker slot-name argument; `commands` names `worker` and/or `domainworker`. The domain worker has its fixed slot of 3.7 Н1.6, not this name argument. The dynamic variable named by manifest `slot.name_env` is resolved by the adapter
only when the argument is absent; the form does not turn it into a fixed environment name or a command option.

Types are the P/01 vocabulary plus `string`. `default` is a literal, or `-` when there is no literal default; `default_text` preserves a
computed/default rule such as short hostname or `file://<PLATFORM_DIR>/config`. Such a rule is implemented from `norm`, never copied as a
literal value. The adapter supplies resolved external defaults to the SDK. CEL `required` and `bad` use map `f` keyed by the exact input name,
and string `cmd`. Alias checks run over supplied values before defaults. Empty `bad` adds no CEL rule and does not replace contract validation:
instance/box, labels, addresses, role, capacity and the dynamic name remain the checks of the linked norms. In particular no path or member-id
type substitutes for the instance grammar. The launcher reads environment files; this is not a request that the SDK parse them again.

## Refusals

[`refusals.tsv`](refusals.tsv) columns are `chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller`.
It is literal TAB, without CSV quoting. The first ten columns are P/01's. `row` is consecutive within a chapter; the two former 3.2 tables
are concatenated in source order. The final five columns retain the original cells: four-cell tables use cause/outcome/diagnostic/caller;
3.7 uses word/outcome/cause. The first 3.2 table's Code and Body are retained as outcome and diagnostic, including an em dash. No refusal is
removed because its Code cell has no numeric code. `-` means no cell or no extra machine projection.

`start` is a start refusal, `process` a running process, `call` a library result, `peer` an imported door contract. `code` is a fixed HTTP
code, `exit N`, `exit !0` or `-`; a conditional code stays in its normative outcome cell. `kind` is `-`: the imported peer's `error` is not a
worker HTTP Fault schema. No unspecified stdout/stderr format is imposed by a diagnostic token. Н4 links to the form and has no second table.

## Capture machine

[`slot-capture.tsv`](slot-capture.tsv) is the machine of 3.2 Н3 capture. Its header declares closed states and actions, typed CEL inputs and
TORN_STILL. Only the first matching row for the current state is taken. An action `-` means YOURS at `norm`, and must run before the next event
is accepted; it never means no effect. The kit part `slot-capture` generates admission and transition choice and is called by `core`; candidate enumeration, deriving reader outcomes,
full-key validation, store-item encoding, logical write ids, and guarded cleanup are the procedures at their anchors. A store non-answer is not
absence. All operations within one logical retry retain their id and first-send time. The first-start-right input describes the right available
for this candidate's confirmed read; spending it must not erase the very exception being tested. Rejoin never restores it.

## Seams

`acceptance/K/seams.tsv` uses the four columns of scenarios, with a final header comment `# scenario TAB step TAB request TAB expect`.
They are kit stagetests at SDK seams, separate from the process runner's `scenarios.tsv`. Each scenario starts a fresh real SDK, deterministic
store/object clients, monotonic and wall clocks, and a recording subsystem. The adapter invokes the implementation, translates its result and
records its effects. It may not answer a case from its expected output. These port names and JSON are test normalization, not mandatory SDK APIs.

`CALL <name> <JSON>` consumes one JSON value; expectations use the common acceptance JSON subset rules (an empty list is empty, `{}` exactly
empty). Only the listed fields are asserted. A normal refusal must not be obtained by catching a panic or unrelated exception. `@parallel K`,
`@clock +/-N`, `@file` and `@read`, when used, have the P/02 forms README grammar and the course checker grammar. No shell is evaluated.

The adapters complete background data before calling the SDK: a valid manifest `testsub` with prefix `w` (the opening port uses the published testsub2 manifest and a valid tally row for its explicit testsub2 key), valid schema, slot, ownership,
assignment of `u1` and running lease where a port needs them. Explicit input overrides that background; missing is not an unconfirmed read.
A null slot means confirmed absence; `reply: unavailable` means an unknown read. Partial marks/rows in probes override a valid fixture of that
kind, not malformed JSON fed as an unintended second failure. `self` denotes this instance. Row objects in `slot` are store wire `{index,items}`;
other normalized numeric epoch/generation fields are decoded values. Versions are opaque strings. Event lists are delivered in order; no event
name adds a new process operation. All counters are observations since the fresh start.

| CALL port | Input and observation |
|---|---|
| `worker-stop` | signal, units, place, optional erroring stop hooks. Observe stop effects and exit. `order` is the declared list of happens-before edges, each included only if it held in the recorded trace; it does not order units against one another. `stopped` is a sorted set for comparison, not a required stop order. SIGKILL observes no orderly hooks/writes. |
| `worker-capture` | name, prefix, instance, server, given/first_start, slot, names_given, optional observed_for, contributions and scripted write/cleanup replies. The store returns fresh versions on successful writes. A final-write or cleanup reply belongs to that operation, not the first CAS. Observe live/nobody, writes, contender and events, and whether the first-start right was spent. `slot_writes` preserves write order and wire items; `logical_slot_writes` excludes network replays. `again` confirms the original write, retaining its id and send clock. |
| `worker-grant` | epoch/floor or floor_reads, issue send/answer moments, confirm send moment, answered assignment and silence policy. Queue the answer at its declared time and recheck all gates before start. Observe issued epoch, lease, launch and rollback writes, and requirement of a fresh assignment read. `confirmation_after_issue` records causal order even at an equal clock reading. |
| `worker-start-gate` | a controlled interleaving: block issue/start at begin, deliver answers, fence, rejoin and read assignment as named. Observe accepted calls, cancellation/stopping and published units. Returning the old start must not register a live unit. No store request or blocked start holds a lock that prevents fence. |
| `worker-confirm` | lease, epoch/read_epoch, floor, last, send/answer times, optional ceiling. The own slot term is open in the background. Observe lease, last and predicates. `last` is monotonic over confirmed send times, not wall time. |
| `worker-slot-write` | consecutive slot_reads, write_replies and own_term_open. Record each target write's guard version; a 412 must trigger a fresh ownership read before retry. Observe ownership loss and definite success, not only the count of calls. |
| `worker-reconcile` | current and desired unit, lease and answered assignment. Observe epoch issues, stop's restarting word, start epochs, observed_revision and continued lease. A born change is a new unit; an edit under the same born restarts with the same epoch. |
| `worker-retry` | failure count, at_max and events. Observe the count after each event and final stalled. A non-answer is not confirmed absence; a move/fence/name change is not a failed start. |
| `worker-stand-in` | step age, ownership, write permission, last loop heartbeat and wall clock. Observe renewal/confirmation order, absence of epoch writes and watchdog calls, and repeated heartbeat with unchanged as_of. |
| `worker-memory` | launcher command, manifest and environment. Read unit_mb/base_mb from placement.capacity. Missing unit_mb, capacity or WORKER_MEMORY_MB skips the check; domainworker receives no invented role-file values. Observe checked/refused and the fixed refusal word, no invented exact exit code. |
| `worker-open-unit` | id, row key, row and ring (null means no ring). Run the real opening path before epoch issue. Observe recipient values, no epoch/start on Sealed, status and absence of forbidden status fields; the adapter scans recorded heartbeat/log values for an opened plaintext. The envelope is the published synthetic common sealing vector. |
| `worker-holder-look` | request, mark, now, optional put_new reply; normal profile, one live unit, most_valid above the requested deadline unless overridden. Observe action calls and outcome writes. A foreign begun with an expired request still waits until the foreign call's timeout; an unknown put_new never admits the action. |
| `worker-holder-group` | ordered begin/timeout/observe/look/return events for two requests of one group. Observe calls before/after the first return and maximum unfinished calls. Timeout does not stand in for completion of the device call. |
| `worker-state-write` | start identity, re-read unit row, state name/value, may_write. Observe wire items and epoch-row guard. The fixture declares result as an object schema. Identity stamps remain those of the start, not the newer unit row. |
| `worker-token-cache` | kind, current token identity, ordered refusal/issue events, same-local-day and a verification fixture. The agent transport is controlled; real token bytes, keys, revocations and time are copied from the public common domain-token cases token-36-kind-list-audience-map and token-keep-alive. No validation path is bypassed. Observe requests, revoked word, waiting, files/rows/logs. Recipient crypto also passes the common domain-token vectors. |

These seams supplement reading witnesses. They do not remove the checklist or close a process scenario, domain stand, keyless opening case,
place writer, or OS presence-lock race that they do not execute. The stage plan lists them as kit tests; the full lesson remains the runner's work.

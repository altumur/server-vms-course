# P/03 forms and SDK seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export (ADR-0121).
These forms express the existing worker norms (ADR-0125 addendum (5)). The SDK has no new binary or HTTP API.

## Process inputs

[`daemon-flags.tsv`](daemon-flags.tsv) keeps the eight P/01 columns. `$NAME` denotes an environment value and `<name>` the optional
ordinary worker slot-name argument; `commands` names `worker` and/or `domainworker`. The domain worker has its fixed slot of 3.7 N1.6, not this name argument. The dynamic variable named by manifest `slot.name_env` is resolved by the adapter
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
worker HTTP Fault schema. No unspecified stdout/stderr format is imposed by a diagnostic token. N4 links to the form and has no second table.

## Capture machine

[`slot-capture.tsv`](slot-capture.tsv) is the machine of 3.2 N3 capture. Its header declares closed states and actions, typed CEL inputs and
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
| `worker-base-heartbeat` | Ordinary base heartbeat without subsystem overrides; report decoded schema/build/pending_writes from SCHEMA/BUILD/defaults. |
| `worker-contribution-cleanup` | Actual two-manifest taking/guarded-cleanup/final-live fixture; count own and foreign contribution IO and inspect the preserved foreign row. |
| `worker-holder-takeover` | Two holder process epochs with a real late-return callback; record pending calls after fixed wait and the explicit overlap witness, not a cross-holder exclusion promise. |

These seams supplement reading witnesses. They do not remove the checklist or close a process scenario, domain stand, keyless opening case,
place writer, or OS presence-lock race that they do not execute. The stage plan lists them as kit tests; the full lesson remains the runner's work.


## Lesson-review boundaries

The Architect's accepted P/03 review under ADR-0127 supplements the same ports and [seams](../acceptance/2/seams.tsv); no process command or HTTP API is introduced. All original seams and process scenarios remain required.

The capture adapter derives gen_readable from the unchanged family reader, and gen_incrementable by exact comparison before any int conversion. The latter is true for confirmed absence or a readable generation in [0,9007199254740991). Only then is gen the exact machine operand; otherwise gen=0 is an unused placeholder and the exact original remains available. A high generation is not an unreadable one. Range refusal applies only to an otherwise eligible existing-row capture, retaining the prior NameOnAnotherBox and torn-young precedence. New capture probes observe final_gen or the exact slot_gen_after, gen_readable, refusal and absence of writes.

worker-grant likewise compares epoch and floor exactly, including values beyond int64. New issue probes report actual issue_writes and launch_calls; >=MAX refuses before a write and without retrying the known invalid issue. These are independent from capture generation.

worker-base-heartbeat invokes the ordinary base heartbeat builder with no subsystem overrides. It reports decoded schema/build/pending_writes, using SCHEMA and BUILD, with pending_writes zero. worker-stand-in with strict_place=true installs one real held permitted strict-place fixture and observes its actual CAS under the slot guard. It counts contribution/state writes separately; no such publication becomes allowed.

worker-contribution-cleanup loads two real valid manifests with distinct subsystem names and the same slot name. own_from names every declared book source of the own manifest (two actual rows); foreign_from names a live foreign contribution. It invokes ordinary taking/guarded cleanup/final-live code. The result counts contribution reads/deletes of each subsystem from recorded IO and verifies the foreign row directly after the run. Manifest catalogue reads are not foreign contribution reads. A prepared answer or a model of cleanup is not this seam.

worker-holder-takeover runs two holder process epochs and a real blocked action callback. A starts r1 at 0.2; B takes epoch2 at 1; the old callback returns at 30.2. At 11.2 the fixed 10.2-second wait of B has elapsed while the actual old call is still pending. Record the real in-flight trace and holder/epoch changes: old_call_unfinished_after_wait=true, cross_holder_exclusion_proven_by_wait=false, witness=overlap_possible_marked. The adapter derives these observations from the controlled IO/callback trace, not by returning constants. The seam does not require B to dispatch at the earliest permitted instant: a stronger barrier/fence may defer or reject it. It records why fixed wait alone is not cross-holder exclusion; the original single-holder s4 still requires maximum one unfinished call. No new alarm/event kind is introduced.

worker-token-cache now distinguishes local now from verification.now at the receiver. The keep-current probe sets local now beyond exp but verifies and accepts the real current token at the recipient's still-valid time; receiver=accepted is that actual reply. It counts actual new-token requests and cache replacements and checks that current remains. Signature verification is retained; a local clock is not substituted for the receiver's outcome.

## Row-write bindings

[row-write-bindings.tsv](row-write-bindings.tsv) and its [grammar](row-write-bindings.md) define the state constructor from the start snapshot at P/03.6-R018/R029 under ADR-0127; IO/CAS/retry remain with the procedure.

## Worker policy machines

The existing machine class is used by [`contender-writer.machine.yaml`](contender-writer.machine.yaml) with
[`contender-writer.traces.tsv`](contender-writer.traces.tsv), and [`token-cache.machine.yaml`](token-cache.machine.yaml)
with [`token-cache.traces.tsv`](token-cache.traces.tsv). Their norm fields name P/03.2-R012, P/03.2-R047 and
P/03.7-R009, P/03.7-R018. One ordered transition is one row of transitions; from/to refer only to states, initial is
one state, terminal is an explicit subset with no outgoing transitions. There is no additional KIT_PART.

The files declare their typed events, typed variables and action arguments. Action args are a name → type map; positional call arguments follow that declaration order, while an event payload is matched by field name. The closed types are bool, int (int64), double, number, string, dyn, null, object, array, `list<T>`, `map<string,T>`, unions with | and records declared in types. An external event has exactly the named
payload fields. The event names input and advance belong to the trace envelope, all others are declared in events.
const contains only this machine's finite JSON constants. timers is empty in these two policies: cadence, wall-clock
reads and local calendar-day computation are inputs supplied by the ordinary core. No rollout timer or constant is implied.
The shared executor also accepts declared every/after timers from an explicit clock expression (or s0), and a timer
after_io an explicitly named IO action; a typed timer event's payload is declared by CEL expressions. Timer events
come from the executor, not an external trace. A terminal state stops all transitions and timers.

A non-IO action performs simultaneous CEL assignments to its declared variables. Actions are executed in row order;
action arguments see assignments made by earlier actions of that transition. An action with io selects an ordinary
core effect: the reference trace records io, the declared action name and a JSON array of its evaluated arguments.
The reference executes no IO. Assertions io=[...] compare the complete ordered list for that step, including an empty
list that rejects any unpromised IO; `var.<name>=JSON` compares a variable. TSV has literal TAB cells and LF rows;
Unicode U+2028 within a JSON string is data, not a row boundary.

For contender-writer, the caller supplies actual capture/loss and NameOnAnotherBox results. The form selects
state/since/at and the existing name_taken/name_back episode events; it neither captures a slot nor constructs a
holder snapshot. Actual capture admission, CONTEND_EVERY scheduling, the complete contender object and its write are
still governed by the ordinary core and the data family. since does not restart just because the writer clock moves
backwards. The form has 8 traces, with first search, foreign-box priority, no mark while decommissioned, no write
before due, state changes and repeated loss/recovery episodes.

For token-cache, the scope is a kind with keep:true and one ref in the running worker. Handles and JTIs refer to actual
parsed tokens without placing token bytes in the form or trace. Recipient results, not local exp, drive replacement;
unknown_key waits, a revoked token supplies its exact JTI, a same-JTI reply waits through that worker day. The machine
selects persist only after the first accepted request using the candidate. persist is an IO intent, not confirmation
of a completed file write: sealing, the path/context, mode0600, IO errors, retries and write ordering remain with the
ordinary file writer under the norm. These are existing core effects and call sites; no new token command is declared.
The form has 12 traces with positive acceptance and negative unknown-key, early-file, same-day and stale-result paths.

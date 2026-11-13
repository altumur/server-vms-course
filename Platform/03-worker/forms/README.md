# P/03 forms and SDK seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export.
These forms express the existing worker norms. The SDK has no new binary or HTTP API.

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

## Owned scalar settings

[runtime-constants.tsv](runtime-constants.tsv): name/value/unit/norm/meaning, positive JSON integer through int64; units count/s/ms/bytes. WAKE_GAP_MS, PERFORM_GRACE_MS and REQUESTS_HOLD_MS convert to seconds by exact /1000. Foreign values link to their owners, derived timings are formulas, ROAD_BUCKETS remains the typed list in chapter 3.4 N1.1, and independent boundary witnesses keep their own test numbers.

## Refusals

[`refusals.tsv`](refusals.tsv) columns are `chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller`.
It is literal TAB, without CSV quoting. The first ten columns are P/01's. `row` is consecutive within a chapter, in file order. The final five columns are the normative cells: rows of four cells use
cause/outcome/diagnostic/caller; 3.7 uses word/outcome/cause. Chapter 3.2 rows 1–11 carry the code cell as outcome (an em dash: no code)
and the body cell as diagnostic. A row whose code cell has no numeric code is still a refusal. `-` means no cell or no extra machine projection.

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

`acceptance/K/seams.tsv` (judge-only: the SDK seam tests) uses the four columns of scenarios, with a final header comment `# scenario TAB step TAB request TAB expect`.
They are kit stagetests at SDK seams, separate from the process scenarios `scenarios.tsv` of the chapter (judge-only: the process acceptance); the judge runs them by the [seam adapter protocol](../../common/acceptance/seams.md#seam-adapter-protocol). Each scenario starts a fresh real SDK, deterministic
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

Background completion is only for SDK CALL fixtures: a positive ordinary unit/tally fixture contains id and the current 32-hex born. Partial logical row/mark arguments overlay it; this is not substitution for missing born in a raw row. Explicit slot wire rows {index,items} are complete: a missing items field remains missing. family-read text is also the complete raw input and is never completed or repaired.

Scripted store replies (`first_write_replies`, `final_write_replies`, `cleanup_replies`, `write_replies`, `issue_replies`, `reply`) are words, one per request sent by that operation, in order; a request beyond the listed words gets `ok`. `ok` — the write is applied, a read answers with the fixture; `again` — the replay of the same id is answered with its first answer (P/01.1, `again`); `guard` — 412 `guard`; `unavailable` — no answer; `ambiguous` — 503 `ambiguous`, the outcome is unknown; `badkey` — 400 `badkey` of P/01.1 N4, a definite refusal of that operation (P/03.2 N3 «Full keys and store refusal»). `replay_same_id` is true when each `unavailable` or `ambiguous` reply of one logical write is followed by at least one repeat of that logical write, and every request sent after such a reply carries the id and keeps the first-send moment of that logical write (P/03.4-07, P/03.2 N1.6). It is false when such a reply is followed by no repeat, when a repeat carries another id or another first-send moment, and when the operation got no such reply. A definite reply needs no repeat. The adapter derives these observations from the recorded store IO.

| CALL port | Input and observation |
|---|---|
| `worker-stop` | signal, units, place, optional errors from the ordered stop calls, optional `stop_unit_seconds` (unit → seconds of the scripted clock that its `stop_unit` takes; default 0) and `confirmed_age` (the age at the signal of the send moment of the last confirmed request of the lease and the slot renewal; default 0). Observe stop effects and exit. `release_within_budget` is true when the write that gives away the slot is sent no later than `WRITE_WINDOW` (P/03.2 N1.2, N1.4) after the send moment of the last confirmed request before it, including a renewal sent during the stop. `order` is the declared list of happens-before edges, each included only if it held in the recorded trace; it does not order units against one another. `stopped` is a sorted set for comparison, not a required stop order. SIGKILL makes no ordered stop calls or writes. |
| `worker-capture` | name, prefix, instance, server, given/first_start, slot, names_given, optional observed_for, contributions and scripted write/cleanup replies. The store returns fresh versions on successful writes. A final-write or cleanup reply belongs to that operation, not the first CAS. Observe live/nobody, writes, contender and events, and whether the first-start right was spent. `live_returns` counts live slots handed out; `final_slot_writes` counts sent final writes. The name is used as given, with no shortening: the slot key is the full key of P/03.2 N3 «Full keys and store refusal». `slot_writes` preserves write order and wire items; `logical_slot_writes` excludes network replays. `again` confirms the original write, retaining its id and send clock. |
| `worker-grant` | epoch/floor or floor_reads, issue send/answer moments, optional `issue_replies`, confirm send moment, answered assignment and silence policy. Queue the answer at its declared time and recheck all gates before start. Observe issued epoch, lease, launch and rollback writes, and requirement of a fresh assignment read. `confirmation_after_issue` records causal order even at an equal clock reading. |
| `worker-start-gate` | a controlled interleaving: block issue/start at begin, deliver answers, fence, rejoin and read assignment as named. Observe accepted calls, cancellation/stopping and published units. Returning the old start must not register a live unit. No store request or blocked start holds a lock that prevents fence. |
| `worker-confirm` | lease, epoch/read_epoch, floor, last, send/answer times (`answered: null` — the request got no answer), optional `reply` of the confirmation read, optional `unconfirmed_max` (the manifest word or seconds; default off) and `at` (the moment at which the predicates are read; default the answer moment). The own slot term is open in the background. Observe lease, last and predicates `may_act`, `may_write`. `last` is monotonic over confirmed send times, not wall time. |
| `worker-slot-write` | consecutive slot_reads, write_replies and own_term_open. Record each target write's guard version; a 412 must trigger a fresh ownership read before retry. Observe `guards`, `name_lost`, `confirmed_writes` and `replay_same_id`: ownership loss and definite success, not only the count of calls. |
| `worker-reconcile` | Current and desired unit, lease and answered assignment; the exact [JSON normalization](#worker-reconcile-json) is below. A born change is a new unit; an edit under the same born restarts with the same epoch. |
| `worker-retry` | Failure count, at_max and ordered events; the exact [JSON normalization](#worker-retry-json) is below. A non-answer is not confirmed absence; a move/fence/name change is not a failed start. |
| `worker-stand-in` | step age, ownership, write permission, last loop heartbeat and wall clock. Observe renewal/confirmation order, absence of epoch writes and watchdog calls, and repeated heartbeat with unchanged as_of. |
| `worker-memory` | launcher command, manifest and environment. Read unit_mb/base_mb from placement.capacity. Missing unit_mb, capacity or WORKER_MEMORY_MB skips the check; domainworker receives no invented role-file values. Observe checked/refused and the fixed refusal word, no invented exact exit code. |
| `worker-open-unit` | id, row key, row and ring (null means no ring). Run the real opening path before epoch issue. Observe recipient values, no epoch/start on Sealed, status and absence of forbidden status fields; the adapter scans recorded heartbeat/log values for an opened plaintext. The envelope is the published synthetic common sealing vector. |
| `worker-holder-look` | request, mark, now, optional put_new reply; normal profile, one live unit, most_valid above the requested deadline unless overridden. Observe action calls and outcome writes. A foreign begun with an expired request still waits until the foreign call's timeout; an unknown put_new never admits the action. |
| `worker-holder-group` | Ordered events for two requests of one group; the exact [JSON normalization](#worker-holder-group-json) is below. Timeout does not stand in for completion of the device call. |
| `worker-state-write` | start identity, re-read unit row, state name/value, may_write, optional `write_replies`. Observe wire items, epoch-row guard, `confirmed_writes` (the logical state writes confirmed by a definite `ok` or `again`) and `replay_same_id`. The fixture declares result as an object schema. Identity stamps remain those of the start, not the newer unit row. |
| `worker-token-cache` | kind, current token identity, ordered refusal/issue events, same-local-day and a verification fixture. The agent transport is controlled; token bytes, keys, revocations and time come from the input of the case. No validation path is bypassed. Observe requests, revoked word, waiting, files/rows/logs. Recipient crypto also passes the common domain-token vectors. |
| `worker-base-heartbeat` | Ordinary base heartbeat without subsystem overrides; report decoded schema/build/pending_writes from SCHEMA/BUILD/defaults. |
| `worker-contribution-cleanup` | Actual two-manifest taking/guarded-cleanup/final-live fixture; count own and foreign contribution IO and inspect the preserved foreign row. |
| `worker-lease-run` | `seconds` of the scripted clock, `role` and `units`; optional `cursor_every` (the subsystem asks to write the cursor state of each unit every that many seconds). `live`: the background holds the own slot, the assignment and a confirmed lease of the units, and the run starts at the confirmed capture (moment 0); `nobody`: the given name is held by a live instance of another box. Every store request is answered at once with `ok`; no step is stuck. Observe the writes sent in [0, seconds]: `slot_writes` (renewals of the slot, not the capture), `heartbeat_writes`, `state_writes`, `kinds_written` — the sorted set of these three kinds with at least one write, and `over_ceiling` — the sorted list of the kinds whose count is above the ceiling: `heartbeat` ⌊seconds / HEARTBEAT_EVERY⌋ + 1 (P/03.3 N3 the loop, P/03.4 N1.1 `cadence`), `state` ⌊seconds / STATE_EVERY⌋ + 1 (P/03.6 N1.7 `cursor`). The renewal step is fixed by P/03.2-R079 and P/03.2-R098: RENEW_EVERY = LEASE_EVERY. This probe records `slot_writes` without judging its count; the slot has no ceiling in `over_ceiling`. |
| `worker-holder-takeover` | Two holder process epochs with a real late-return callback; record pending calls after fixed wait and the explicit overlap witness, not a cross-holder exclusion promise. |

These seams supplement reading witnesses. They do not remove the checklist or close a process scenario, domain stand, keyless opening case,
place writer, or OS presence-lock race that they do not execute. The stage plan lists them as kit tests; the process scenarios of the lesson remain the judge's work.

### worker-reconcile JSON

The input is an object. The following fields are required unless marked optional. Partial unit objects complete the ordinary fixture described above; the named fields below retain their supplied values. Unit identity, revision, epoch and lease behavior follow P/03.2-R212, P/03.2-R213, P/03.2-R214, P/03.2-R215, P/03.2-R216, P/03.2-R217, P/03.2-R218, P/03.2-R044, P/03.2-R220, P/03.2-R045, P/03.2-R224, P/03.2-R226, P/03.2-R227, P/03.2-R229, P/03.2-R230, P/03.2-R231 and P/03.3-R033 through P/03.3-R035.

| Input field | JSON type and meaning |
|---|---|
| `current` | Object with `id` (string), `born` (string), `revision` (integer) and `epoch` (integer): the running unit and its accepted start identity. |
| `desired` | Object with `id` (string), `born` (string) and `revision` (integer): the desired unit row. |
| `lease` | String, `confirmed` or `silent`: the prepared lease state. |
| `assignment_confirmed` | Boolean: whether the desired assignment was confirmed by a successful read. |
| `may_write`, `may_act` | Optional booleans overriding the corresponding scripted lease predicates; when absent the prepared lease supplies them. |

The result is an object with all fields below. The adapter records actual epoch-issue writes and subsystem calls; it reads the final accepted revision and lease state from the implementation. Array order is call order.

| Result field | JSON type and meaning |
|---|---|
| `epoch_issues` | Nonnegative integer: number of new epoch issues. |
| `stop_calls` | Nonnegative integer: number of `stop_unit` calls. |
| `stop_restarting` | Array of booleans, one per `stop_unit` call: whether the subsystem's `restarting(id)` word holds for that call. |
| `start_epochs` | Array of integers: the epoch passed to each accepted `start_unit` call. |
| `observed_revision` | Integer: the accepted revision after reconciliation. |
| `lease` | String, `confirmed` or `silent`: the resulting lease state. |

### worker-retry JSON

The input is an object with required `unit` (string), `failure_count` (nonnegative integer), `at_max` (boolean: the initial retry pause has reached RETRY_MAX) and `events` (an ordered array of strings). The closed event words are `assignment-unavailable` (the assignment read got no answer), `move` (the unit moved), `fence` (the unit was fenced), `name-change` (the worker changed its name) and `assignment-absent-confirmed` (a successful assignment read confirms that the unit is absent). These events exercise the count classification and reset of P/03.3-R025, P/03.3-R028; they are not synthetic start failures.

The result is an object with required `counts_before_absence` (array of nonnegative integers), `failure_count` (nonnegative integer) and `stalled` (boolean). `counts_before_absence` records the count after each event preceding the first `assignment-absent-confirmed`, in event order; if no such event occurs it records the count after every event. It excludes that confirmed-absence event and all later events. `failure_count` and `stalled` are the final observed count and retry state after all events. The adapter reads these values from the real retry state, not from the event names alone.

### worker-holder-group JSON

The input is an object with required `group` (string) and `events` (an ordered array of strings). The fixture prepares two otherwise eligible requests of that group in one holder process epoch. A request identifier is the nonempty suffix following the first colon; the same string denotes the same request throughout the trace. The closed event forms are:

| Event form | Intervention |
|---|---|
| `begin:<request>` | Admit the named request through the real holder path and keep its device callback unfinished. |
| `timeout:<request>` | Deliver the named call's timeout while its device callback remains unfinished. |
| `observe:<request>` | Make the named eligible request visible to the holder. |
| `look` | Run the holder's ordinary look at the visible requests. This event has no colon or request suffix. |
| `return:<request>` | Complete the named unfinished device callback. |

The result is an object with required `calls_before_return` (array of strings: request identifiers of actual device calls dispatched before the first `return:<request>`), `calls_after_return` (array of strings: those dispatched after that event) and `max_unfinished` (nonnegative integer: maximum simultaneous unfinished device callbacks). Each array preserves dispatch order. A timeout leaves its callback unfinished until `return:<request>`; the adapter measures this actual overlap under P/03.6-R162, P/03.6-R163, P/03.6-R164, P/03.6-R165, P/03.6-R167, P/03.6-R168, P/03.6-R169, P/03.6-R170, P/03.6-R171, P/03.6-R172.


## Additional seam boundaries

The boundaries below supplement the same ports and [seams](../acceptance/2/seams.tsv) (judge-only: the SDK seam tests of chapter 3.2); no process command or HTTP API is introduced. All other seams and process scenarios remain required.

The capture adapter obtains gen_readable from the current generation field codec/range independently of the other slot fields, before narrowing. row_readable separately checks the whole slot. Confirmed absence is separate, with operand 0. An existing gen in 1..9007199254740991 is readable; gen_incrementable holds only below the maximum. Outside that range is the existing unreadable gen, retaining its original bytes. When false, machine gen=0 is an unused placeholder. generation_exhausted remains for a readable maximum at an otherwise eligible candidate; NameOnAnotherBox/torn-young admission is not bypassed. An unreadable generation introduces no programmatic unreadable word where the refusal catalogue specifies none.

worker-grant first validates an existing epoch in the current positive range, using the existing EpochUnreadable for damage. In the existing CALL fixture, epoch=0 denotes confirmed absence only; stored zero is independently negative in family-read. Floor follows P/01.3 and is compared exactly, including beyond int64, without narrowing its range to epoch. An impossible next issue retains issue_writes=0/launch_calls=0 before any write, without retrying a known invalid number.

worker-base-heartbeat invokes the ordinary base heartbeat builder with no subsystem overrides. It reports decoded schema/build/pending_writes, using SCHEMA and BUILD, with pending_writes zero. worker-stand-in with strict_place=true installs one real held permitted strict-place fixture and observes its actual CAS under the slot guard. It counts contribution/state writes separately; no such publication becomes allowed.

worker-contribution-cleanup loads two real valid manifests with distinct subsystem names and the same slot name. own_from names every declared book source of the own manifest (two actual rows); foreign_from names a live foreign contribution. It invokes ordinary taking/guarded cleanup/final-live code. The result counts contribution reads/deletes of each subsystem from recorded IO and verifies the foreign row directly after the run. Manifest catalogue reads are not foreign contribution reads. A prepared answer or a model of cleanup is not this seam.

worker-holder-takeover runs two holder process epochs and a real blocked action callback. Record the real in-flight trace and holder/epoch changes as the fields old_call_unfinished_after_wait, cross_holder_exclusion_proven_by_wait and witness. The adapter derives these observations from the controlled IO/callback trace, not by returning constants. The seam does not require B to dispatch at the earliest permitted instant: a stronger barrier/fence may defer or reject it. It records why fixed wait alone is not cross-holder exclusion; the single-holder s4 still requires maximum one unfinished call. No new alarm/event kind is introduced.

worker-token-cache distinguishes local now from verification.now at the receiver. It counts actual new-token requests and cache replacements and checks that current remains. Signature verification is retained; a local clock is not substituted for the receiver's outcome.

## Row-write bindings

[row-write-bindings.tsv](row-write-bindings.tsv) and its [grammar](row-write-bindings.md) define the state constructor from the start snapshot at P/03.6-R018, P/03.6-R128, P/03.6-R192; IO/CAS/retry remain with P/03.6-R193 and P/03.6-R194.

## Worker policy machines

The existing machine class is used by [`contender-writer.machine.yaml`](contender-writer.machine.yaml) with
[`contender-writer.traces.tsv`](contender-writer.traces.tsv) (judge-only: reference traces), and [`token-cache.machine.yaml`](token-cache.machine.yaml)
with [`token-cache.traces.tsv`](token-cache.traces.tsv) (judge-only: reference traces). Their norm fields name P/03.2-R012, P/03.2-R121, P/03.2-R123, P/03.2-R125, P/03.2-R128, P/03.2-R233, P/03.2-R234 and
P/03.7-R009, P/03.7-R055, P/03.7-R056, P/03.7-R057, P/03.7-R058, P/03.7-R059, P/03.7-R060, P/03.7-R106, P/03.7-R107. One ordered transition is one row of transitions; from/to refer only to states, initial is
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

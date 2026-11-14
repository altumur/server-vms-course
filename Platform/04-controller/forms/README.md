# P/04 forms and controller seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export.
These forms express the existing controller norms; no controller HTTP door is introduced.

## Inputs and refusals

[daemon-flags.tsv](daemon-flags.tsv) has the eight P/01 columns, with the P/03 environment/argument spelling: `$NAME` is environment,
`<sub>` is the subsystem argument of the controller launcher route. These are process settings, not new CLI flags. `default` is a literal or
`-`; `default_text` may preserve a computed default that the adapter resolves from `norm`, never a literal hostname rule or path placeholder.
`number` is finite; the form adds no otherwise unspecified lexical/range refusal. `required`/`bad` are CEL over exact-key map `f` and `cmd`.
Alias checks run before defaults. Empty `bad` does not remove imported validation. The launcher parses environment files, the process consumes them.

The observable start refusals come from [lifecycle.md](../lifecycle.md#exit-codes) and the environment-file contract: malformed environment files or SERVER_NAME, a missing/mismatched W2C_ROLE, and unequal paired names refuse start with code 2; the log names the offending source or names as that contract specifies. Accepted inputs are observed through the store/object roots, the report field hung_move_after, snapshot cluster and the policy effects specified by their norms. A numeric setting with no normative refusal gains no rejection case from its type alone; NOTIFY_SOCKET is observed on the host under the system checklist.

[refusals.tsv](refusals.tsv) has `chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller`.
The separator is literal TAB, without CSV quoting. Chapter is `4`; the final four cells define the cause, outcome, diagnostic and caller action.
`start` is process start, `call` a controller procedure, `peer` an imported console door. A fixed code supplements the normative outcome;
`-` adds no machine projection. `kind` is `-`: the console's error is not a controller HTTP Fault. N4 refers to the form, without a second table.
For `call`, outcome names the observable report fields, stored rows or absence of a mutation; it is not an HTTP status or a process exit. A `peer` outcome is checked through the console, and a `start` outcome through process exit. The seam adapter records actual effects as described below; an internal return word alone does not replace those effects.

## Machines

[slot-fate.tsv](slot-fate.tsv) and [slot-release.tsv](slot-release.tsv) have `n state condition action next norm`, with the P/03 capture grammar:
closed states/actions, typed `#var`, `#const`, `#action`, CEL conditions/arguments, first matching row for the current state. The kit parts have
the file names `slot-fate` and `slot-release`, called by `core`. No match waits without an effect. A `-` action is YOURS at `norm`, never noop.
Fate returns the judgement and permission version; release permission requires the confirmed CAS answer's version. The release machine receives
the already selected fate, after every higher-priority fate rule; its branch table must not judge a fresh live slot as gone on its own.

The input age is the local observation of the same version, not `until`, heartbeat ts or `fates.since`. Reader outcomes and process presence
come from the common contracts; unknown reads are not absence. A damaged existing generation is not zero. The CAS action validates it, keeps
the readable row fields or writes the complete torn-row release, and never retries blindly with a renewed version. Its blocked/error/unknown
outcomes publish no name. A competing renewal leaves the row intact; only the next pass judges the changed version. The abandoned-capture
cleanup, decommission batches and placement turn/intent procedures remain their source anchors, not effects of this pure fate selector.

## Seams

Controller seams use kit testing, separate from the process runner's scenarios. Grammar and JSON comparison are
those of [the P/03 forms README](../../03-worker/forms/README.md) and [the P/02 forms README](../../02-installer/forms/README.md): CALL with one
JSON value, object subset, exact empty objects/lists, fresh scenario roots; no shell. The single-chapter address is `4`, with no acceptance subdirectory.
The port names normalize tests, not the implementation API. Invoke the real controller functions and record effects, never return a canned expect.

Each adapter completes a valid synthetic background before the named intervention: schema and manifest, readable turn/idle intent, unit rows,
workers, live ownership and room. The `testsub` manifest is used, with an explicit placement feature enabled where the case names it. All state
is obtained by running the initialization/previous pass through the same implementation, not by assigning private implementation fields.
An omitted value is not a non-answer; explicit null is confirmed absence. Opaque versions are scripted client replies, and numeric normalized
fields are decoded values; release_items are store wire strings. A normal refusal cannot be supplied by swallowing a crash or unrelated exception.

| CALL port | Intervention and observation |
|---|---|
| `controller-fate` | Supply typed observations of slot-fate. For release, supply a valid slot and controlled CAS reply, run the real release path and record its items/version. A conflict leaves no permission; next_observation drives a fresh pass. No slot_writes means no attempt, no confirmed_slot_writes means no confirmed mutation. The five release witnesses include no-units gone/runs/unlisted, gone with units, and competing renewal. |
| `controller-admit` | Workers, units and an explicit interleaving of two turn holders. Accept the first decision before the second holder gets its fresh look. Observe effective load, assignments and admission, not two independent choices over one stale snapshot. |
| `controller-complete-intent` | A valid active intent and assignments; optionally break after the first confirmed removal and change holder. Resume from all removals, never add before their confirmation. An ambiguous write requires the own-turn barrier; a foreign holder stops all later writes and new admissions. |
| `controller-key-admission` | Read the actual implementation's declared key limit; construct a valid named unit whose unit-row key fits and placement key is exactly placement_key_over_by bytes over it (one here), with ASCII filler in the id. Do not invent a smaller limit or make both keys inadmissible. Put it with another member of one group, plus an independent fitting unit. Observe refusal of the whole group's intent/placements and progress of the independent unit. |
| `controller-choose` | A valid unplaced unit and candidate workers; apply the named constraint and home preference. A home that fails the constraint never wins the rank. |
| `controller-delete-after` | Drive removed/unremoved observations on the virtual monotonic clock; an unremoval clears the count. For a delete response, read a fresh unit/decision first. On CAS refusal touch no state/journal. On store early retain not_before and do not run a barrier or journal. Now is the controller clock; store early is a controlled admission response, not the same clock. |
| `controller-state-sweep` | First read the state and retain its CAS, then freshly read the unit and born. Null means no unit: no unit guard is supplied. For an existing unit or tombstone, record its exact-version guard. Delete only the read orphan state by its retained CAS. A refusal leaves the state with no swept counter increment, for next-pass retry; s24 scripts a 412 of the existing unit guard. |
| `controller-snapshot` | Exercise the real serializer/object publication. serialized_bytes is a fixture target: construct a valid row field with ASCII padding until the full actual serialized shard, including envelope and ts, has this size. Do not inject a fake byte count or bypass serialization. Read failure publishes nothing; exactly the limit is admitted, above it is refused before put; store TooLarge has the same refusal. |
| `controller-table-snapshot` | Drive a valid table publication, then changed/unchanged objects. For the size case use real serialization/padding as above. Above the table limit form the too_large stub. Compare the candidate cluster/refused/rows without ts by P/04-R174; equality preserves the previous ts and writes nothing. The unchanged-row witness keeps cluster and refused unchanged too; a cluster change or stub transition is not an unchanged object. |
| `controller-want` | Drive want and live-number observations at the given monotonic times. A fully raised order clears the in-flight timer; a later missing number starts a new timer even without a changed want version. Observe withdrawals, current target and in_flight_since. |
| `controller-pass` | Inject the named independent step's client failure, continue later steps. Observe failures/ok and that the later step ran. A broken turn has its own rule and must not be normalized as this independent failure. |

These witnesses supplement the reading checklist and common vectors; they do not close an OS process race or a scenario they do not execute.
The stage plan is [stages.tsv](stages.tsv); all runner scenarios and assigned common tables remain required, with row selections from their package README.

### Composed pass witnesses

The existing controller-pass port accepts fixture controls. These controls select a valid synthetic environment, not an expected answer and not an implementation API. Run real controller code through the normal pass. Complete testsub2 with grows, per/capacity, places.table/places.wanted and the existing valid shelf/place fields; no field or role is invented outside its manifest form. Instantiate every live number with a real name and a fresh heartbeat; give each the stated available capacity. The wanted_holder actually holds an admissible place with a readable wanted row. empty_workers have no unit assignment. no_shortage_for is established by previous actual passes on the virtual clock, not by writing an internal timer. Use enough free remaining capacity to satisfy hysteresis, so wanted is the targeted restriction.

Record the real victim/retiring/end result, feed its resulting want to the existing P/02 workers-script reconciliation and record the actual stop plan. A plan is the normalized script observation here, not an OS-kill claim; the process stand retains its own scope. All other label/group/room/turn inputs are valid and unchanged. Compute all observation fields from recorded row/placement/target/script effects; fixture names or expected data cannot manufacture them.

manifest_yaml is the exact supplied YAML input, independently accepted by the regular P/02 loader; the adapter loads these bytes through that loader. It is not an internal canonical tree.

### Resumable decommission witnesses

The same controller-pass port uses fixture=decommission_resume. Load the supplied manifest_yaml through the ordinary P/02 loader. Create the named server's slot_count readable slots and want target, a valid standing console request and an acquired placement turn. The server has not been heard for the required observation interval. All source reads are complete. populate_all_book_contributions gives every original slot one readable contribution in every declared book, using that book's real row form and full prefix. These are controlled store inputs; pending is initially absent and must be created by the implementation. No expected progress row is injected.

Run the real decommission procedure, recording every store request, reply and persisted state. first_batch_index is a controlled store reply sequence starting at the exact decimal STRING shown; every confirmed batch shares one index across its writes. It is never a floating-point fixture counter. There is no requirement to choose the fullest possible chunk. all_batches_within_limits checks every actual request's total writes, distinct guards, row weights and serialized body against the published store limits, including plan acceptance, progress-only writes and finalization; a guard key must not also be a write key. all_cleanup_guards_exact compares each cleanup guard with the recorded release batch index, also after a progress rewrite. final_mark_last_atomic requires the attempted final mark and pending deletion in one conditional batch only after the recorded plan has no remaining release or cleanup work; it cannot be satisfied by a marker written with the first chunk.

break_after_release stops the controller after its first confirmed release chunk and before the first cleanup request; preserve the scripted store, discard controller memory and run a fresh controller through ordinary turn acquisition and recovery. Observe real reads of pending and no repeated slot release.

pending_removed_at_completion is observed only after confirmed finalization. Failure/unknown observations come from the scripted replies and recorded IO, not a swallowed exception or a boolean copied from expect.

fixture=loader_reserved_name: pass the exact manifest_yaml to the same ordinary loader used by the controller, report its actual verdict/layer and diagnostic paths normalized to JSON Pointer.

Begin like the restart witness, then deliberately corrupt the persisted pending row while keeping it readable by its schema. duplicate_remaining_name gives two references with one name and different indices; cursor_past_chunk sets slot_cursor to len(current); foreign_from_prefix keeps the prefix grammar but uses another subsystem. Run recovery from that actual row. Invalid outer source JSON remains a form error, not this semantic intervention. Every observation field is derived from actual implementation effects/IO; these source witnesses do not claim a performed runtime/SUT run.

## Owned scalar settings

The acting [runtime-constants.tsv](runtime-constants.tsv) has only name/value/unit/norm/meaning: positive JSON integers through int64, units count/s/bytes. These are not new environment options. Borrowed values retain their common/P01/P05 owners. Numeric SLOT_TERM/LOST_AFTER machine carriers and pending maxItems stay literal with explicit bindings for an independent subject checker; no symbolic alias is introduced.

## Current reports and witnesses

Positive backgrounds come from the current writer: placement has manifest_rev and nonempty reason; active intent has nonempty reason, idle does not require it; a report has the three mandatory counters; a snapshot has one unit.rows array, including []. Raw family-read is never completed or repaired. Absence before the first object publication is not a malformed wrapper. Recovery goes through pending after a confirmed release, not an early final mark; the exact old guards stay.

All s51-s63 use the existing controller-pass port. fixture and scripted replies select real inputs/client outcomes, never a canned result or an implementation API. The adapter never receives expect. Compute observations from actual controller calls and recorded store/object IO; fixture names are not evidence of execution.

- short_weight: an ordinary current testsub manifest declares an integer weight field w, placement.weight.field=w, the given capacity and one full live worker (free=0). Two readable acting waiting units have weights, each within the existing individual domain; their ids, born, rows and heartbeats are valid. grows/room/want/live provide eligible room, without capacity in flight. Run the real pass before reading its report; short[].units is the exact sum, workers is exact ceil division, not the row count.
- write_conflict_limit: feed target_replies to one logical write in order. After each conflict honor the existing own-turn barrier and fresh read/plan/CAS; never substitute a new version into an old command. Count real attempts and confirmed outcome; the eleventh scripted answer after ten conflicts stays unconsumed. Derive stale_version_writes from requests and observed versions.
- valid_final_mark: obtain a valid final mark by completing a current pending plan, leaving the standing request. A remaining released slot/contribution does not authorize new cleanup. Count slot writes, contribution deletes and final mark writes.
- publication_cycles: keep one process across the listed cycles and run ordinary passes. For target_counter materialize an independent real bad state/type in a snapshot field or real serialization above the table ceiling. The next valid cycle repairs that source. orphan_states creates an actual orphan state for guarded sweep, not a seeded counter. snapshot_read/put script client outcomes; commit_reply_lost really persists the new object before losing its reply. External object readback observes persisted bytes, not controller confirmation. Freeze control timing/ok/failures at control end, release turn before snapshots, and write the one final report after both attempts. Count actual report writes and IO order; introduce no runtime counter or port.

Pure seams do not prove OS/process recovery or SUT. An unsupported binding remains an explicit gap until adapter/independent-check delivery, never canned PASS or an excluded execution.

## Shrink checks

This is the ordered selector of P/04-R051. The first true row returns `why`; only `ok` allows shrinking. `victim_exists` means an eligible live top number `n = want(s) > 1` under the victim/wanted-place rules, never a number above want. `waiting` uses the existing placeable set; `distinct` and `placeless` use the heartbeat-place policy. `no_shortage_for` is one role-wide timer by P/04-R563: seconds since the first pass without waiting in any label set, null when any set has waiting; a new controller starts that observation again. `in_flight` is the heartbeat count of missing numbers in `2…want`, excluding the base. `per` is the existing positive capacity estimate, or null. `remaining_free_after_move` is the suitable live workers' free capacity after transferring the victim's units, excluding the victim and numbers above want; with distinct, only place keepers contribute. The existing numeric forms and units apply; no new constant is introduced. Equality at `SHRINK_AFTER` refuses; equality at `per` passes.

| n | CEL | outcome | R-id |
|---|---|---|---|
| 1 | `!victim_exists` | `no_victim` | P/04-R051 |
| 2 | `distinct && waiting > 0 && placeless` | `placeless_with_waiting` | P/04-R051 |
| 3 | `waiting > 0 \|\| no_shortage_for == null \|\| no_shortage_for <= SHRINK_AFTER` | `no_shortage_long_enough` | P/04-R051 |
| 4 | `in_flight > 0` | `in_flight` | P/04-R051 |
| 5 | `per == null \|\| remaining_free_after_move < per` | `hysteresis` | P/04-R051 |
| 6 | `true` | `ok` | P/04-R051 |

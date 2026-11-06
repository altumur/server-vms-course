# P/04 forms and controller seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export (ADR-0121).
These forms express the existing controller norms (ADR-0125 addendum (5)); no controller HTTP door is introduced.

## Inputs and refusals

[daemon-flags.tsv](daemon-flags.tsv) has the eight P/01 columns, with the P/03 environment/argument spelling: `$NAME` is environment,
`<sub>` is the subsystem argument of the controller launcher route. These are process settings, not new CLI flags. `default` is a literal or
`-`; `default_text` may preserve a computed default that the adapter resolves from `norm`, never a literal hostname rule or path placeholder.
`number` is finite; the form adds no otherwise unspecified lexical/range refusal. `required`/`bad` are CEL over exact-key map `f` and `cmd`.
Alias checks run before defaults. Empty `bad` does not remove imported validation. The launcher parses environment files, the process consumes them.

[refusals.tsv](refusals.tsv) has `chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller`.
The separator is literal TAB, without CSV quoting. Chapter is `4`; the four final cells preserve all former N4 cells in source order.
`start` is process start, `call` a controller procedure, `peer` an imported console door. A fixed code supplements the normative outcome;
`-` adds no machine projection. `kind` is `-`: the console's error is not a controller HTTP Fault. N4 refers to the form, without a second table.

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

[acceptance/seams.tsv](../acceptance/seams.tsv) is kit testing, separate from the process runner's scenarios. Grammar and JSON comparison are
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
| `controller-fate` | Supply typed observations of slot-fate. For release, supply a valid slot and controlled CAS reply, run the real release path and record its items/version. A conflict leaves no permission; next_observation drives a fresh pass. No slot_writes means no attempt, no confirmed_slot_writes means no confirmed mutation. The five former release witnesses include no-units gone/runs/unlisted, gone with units, and competing renewal. |
| `controller-admit` | Workers, units and an explicit interleaving of two turn holders. Accept the first decision before the second holder gets its fresh look. Observe effective load, assignments and admission, not two independent choices over one stale snapshot. |
| `controller-complete-intent` | A valid active intent and assignments; optionally break after the first confirmed removal and change holder. Resume from all removals, never add before their confirmation. An ambiguous write requires the own-turn barrier; a foreign holder stops all later writes and new admissions. |
| `controller-key-admission` | Read the actual implementation's declared key limit; construct a valid named unit whose unit-row key fits and placement key is exactly placement_key_over_by bytes over it (one here), with ASCII filler in the id. Do not invent a smaller limit or make both keys inadmissible. Put it with another member of one group, plus an independent fitting unit. Observe refusal of the whole group's intent/placements and progress of the independent unit. |
| `controller-choose` | A valid unplaced unit and candidate workers; apply the named constraint and home preference. A home that fails the constraint never wins the rank. |
| `controller-delete-after` | Drive removed/unremoved observations on the virtual monotonic clock; an unremoval clears the count. For a delete response, read a fresh unit/decision first. On CAS refusal touch no state/journal. On store early retain not_before and do not run a barrier or journal. Now is the controller clock; store early is a controlled admission response, not the same clock. |
| `controller-state-sweep` | Read the orphan state and unit; null means no unit. Record the unit-row guard and state CAS. A 412 leaves the row, no swept counter increment, next-pass retry. |
| `controller-snapshot` | Exercise the real serializer/object publication. serialized_bytes is a fixture target: construct a valid row field with ASCII padding until the full actual serialized shard, including envelope and ts, has this size. Do not inject a fake byte count or bypass serialization. Read failure publishes nothing; exactly the limit is admitted, above it is refused before put; store TooLarge has the same refusal. |
| `controller-table-snapshot` | Drive a valid table publication, then changed/unchanged rows. For the size case use real serialization/padding as above. Above the table limit write the too_large stub, not the former object; unchanged rows preserve the previous ts and write nothing. |
| `controller-want` | Drive want and live-number observations at the given monotonic times. A fully raised order clears the in-flight timer; a later missing number starts a new timer even without a changed want version. Observe withdrawals, current target and in_flight_since. |
| `controller-pass` | Inject the named independent step's client failure, continue later steps. Observe failures/ok and that the later step ran. A broken turn has its own rule and must not be normalized as this independent failure. |

These witnesses supplement the reading checklist and common vectors; they do not close an OS process race or a scenario they do not execute.
The stage plan is [stages.tsv](stages.tsv); all runner scenarios and assigned common tables remain required, with row selections from their package README.

Review ADR-0127 P/04 M1 witnesses s34/s35 have a legal observation prefix: first read the slot at t=0 and again unchanged at t=90; its server is known, but no readable resource heartbeat/door has ever been observed and the worker heartbeat does not confirm freshness. Resource state is unknown, not silent or unreachable. With units the existing closing rule selects move; without units it enters release, whose confirmed CAS produces the permission. M2 s14 supplies an actual existing row with gen=broken: both slot_readable and gen_readable are false; a readable slot with unreadable required gen is never fabricated.

### Review ADR-0127 composed pass witnesses

The existing controller-pass port accepts fixture controls in s36-s38. These controls select a valid synthetic environment, not an expected answer and not an implementation API. Run real controller code through the normal pass. Complete testsub2 with grows, per/capacity, places.table/places.wanted and the existing valid shelf/place fields; no field or role is invented outside its manifest form. Instantiate every live number with a real name and a fresh heartbeat; give each the stated available capacity. The wanted_holder actually holds an admissible place with a readable wanted row. empty_workers have no unit assignment. no_shortage_for is established by previous actual passes on the virtual clock, not by writing an internal timer. Use enough free remaining capacity to satisfy hysteresis, so wanted is the targeted restriction.

For s36/s37 record the real victim/retiring/end result, feed its resulting want to the existing P/02 workers-script reconciliation and record the actual stop plan. A plan is the normalized script observation here, not an OS-kill claim; the process stand retains its own scope. A protected top is never replaced by a lower victim of that server. All other label/group/room/turn inputs are valid and unchanged. For s38 use a valid named manual unit with a non-id fixed field and an expired ends value; perform removal and cleanup before shortage/shrink. The row remains stored, expired_kept increments, the row contributes no waiting/weight/order and does not prevent an otherwise allowed shrink. Compute all observation fields from recorded row/placement/target/script effects; fixture names or expected data cannot manufacture them.

manifest_yaml in s36-s38 is the exact supplied YAML input, independently accepted by the regular P/02 loader; the adapter loads these bytes through that loader. It is not an internal canonical tree. The wanted manifest declares the wanted table; the ends manifest declares a fixed non-id field. capacity_per_worker=per=1 is actual observed capacity. Prior passes establish the no-shortage timer before injecting the already-expired manual row at now=400, ends_at=399.

### Resumable decommission witnesses

The same controller-pass port uses fixture=decommission_resume in s39-s45 and s48-s50. Load the supplied manifest_yaml through the ordinary P/02 loader. It declares exactly 0, 2 or 65 owned book prefixes; the zero-book manifest also removes its book-dependent names declaration. Create the named server's slot_count readable slots and want target, a valid standing console request and an acquired placement turn. The server has not been heard for the required observation interval. All source reads are complete. populate_all_book_contributions gives every original slot one readable contribution in every declared book, using that book's real row form and full prefix. These are controlled store inputs; pending is initially absent and must be created by the implementation. No expected progress row is injected.

Run the real decommission procedure, recording every store request, reply and persisted state. first_batch_index is a controlled store reply sequence starting at the exact decimal STRING shown; every confirmed batch shares one index across its writes. It is never a floating-point fixture counter. In s39/s40 release all 62/63 slots without books. In s41 clean all 65 contribution keys of one slot with progress/service writes counted. There is no requirement to choose the fullest possible chunk. all_batches_within_limits checks every actual request's total writes, distinct guards, row weights and serialized body against the published store limits, including plan acceptance, progress-only writes and finalization; a guard key must not also be a write key. all_cleanup_guards_exact compares each cleanup guard with the recorded release batch index, also after a progress rewrite. final_mark_last_atomic requires the attempted final mark and pending deletion in one conditional batch only after the recorded plan has no remaining release or cleanup work; it cannot be satisfied by a marker written with the first chunk.

break_after_release stops the controller after its first confirmed release chunk and before the first cleanup request; preserve the scripted store, discard controller memory and run a fresh controller through ordinary turn acquisition and recovery. Observe real reads of pending and no repeated slot release. In s43 the original legacy slot name is t-1, admissible without a server suffix: a worker without a given instance name on srv-b captures that released name through the ordinary P/03 capture procedure, completes predecessor cleanup and writes its new contribution. No SERVER_NAME/instance-name check is bypassed. Resume the controller with the unchanged console request; its old exact slot guard must fail, its remaining deletes for that slot are discarded, and the new holder/contribution remain. Count reads of that slot after the cleanup conflict: zero, rather than adopting a renewed version.

In s44 return a conditional conflict for the final batch without committing any of its writes and stop before a later retry. Inspect actual persisted progress and absence of the final mark. In s45 commit the final conditional batch but lose its reply; observe zero later mutations before the ordinary unknown-outcome barrier and confirmation by actual store reads. pending_removed_at_completion is observed only after confirmed finalization. Failure/unknown observations come from the scripted replies and recorded IO, not a swallowed exception or a boolean copied from expect.

s46/s47 use fixture=loader_reserved_name: pass the exact manifest_yaml to the same ordinary loader used by the controller, report its actual verdict/layer and diagnostic paths normalized to JSON Pointer. Only unit.rows or a table name is decommission-pending. These are P04 linked witnesses; P02 corpus 947 and canonical 220 are unchanged.

s48-s50 begin like the restart witness, then deliberately corrupt the persisted pending row while keeping it readable by its schema. duplicate_remaining_name gives two references with one name and different indices; cursor_past_chunk sets slot_cursor to len(current); foreign_from_prefix keeps the prefix grammar but uses another subsystem. Run recovery from that actual row. Observe the step error and unchanged progress, with no subsequent slot write, contribution delete or final mark. Invalid outer source JSON remains a form error, not this semantic intervention. Every observation field is derived from actual implementation effects/IO; these source witnesses do not claim a performed runtime/SUT run.

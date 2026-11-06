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

# Acceptance P/03.2 — the slot, the epoch, the lease, nobody, the place (stand)

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.2-worker.norms.md`](../../spec/03.2-worker.norms.md) N5. The scenarios were moved from the acceptance of
M10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones, except sc. 04 and 08: the first step is `@start resource`, the former ones are shifted by one (P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Sc. 02, 06 are the acceptance of chapter 3.3, sc. 03 — of chapter 3.4, the rest — [P/04](../../../04-controller/acceptance/README.md).

The scenarios run on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers
`testsub` (the training worker of counters), which the steps of the scenario start. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of
the section «Stand» of the common acceptance README (reconciliation of python and go M10/3–5, item 24): the worker of one manifest does not touch the rows
of the other on capture and cleanup. The training worker `testsub` reports the started counter by the element `status` with `phase: running` (chapter 3.4 N1.1
`phase`) and one word of the subsystem `n` — the value of the counter (chapter 3.4 N1.1 `status`; the second pilot, `N-7`). Observation — rows
through the store door P/01.1 and units through the console door P/06.1; the heartbeat (an object) is not read here. The controller of the stand is
a neighbour by contract (the data catalogue, the life cycle of P/04), not the norms of the chapter (the plan of the move of lesson 3, V2).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors):
the doors `store` (a role with read rights on `testsub/`), `console`, `resource` and `admin` (preparation of rows bypassing their writers — sc. 14–34;
the floor of epochs — `op: floor`, sc. 26, 27), the directives `@start` (with the expectation `@exit 2` and the environment `<NAME>=<value>` of the worker), `@sigkill`,
`@sigterm` (sc. 29), the expectation `@oneof` (sc. 33), `@sleep`, `@until`, `ASSERT`, `@cut role testsubworker store` / `@mend role testsubworker store` (sc. 24),
`@spoil row` (sc. 27), `@spoil object` (sc. 44);
the body of an answer is compared by the mode `body` of the routing row of the target («Expectation» of the dictionary).

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 N1.2) — with full rights on `testsub/` and `testsub2/`.

Each scenario runs on the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand) of the common acceptance README:
a fresh stand per scenario, no foreign processes, one box, the stop of `@sigterm` and `@sigkill`, the time of a scenario. What is own to the chapter
is in the section «[Stand and steps of the chapter](#stand-and-steps-of-the-chapter)» below.

In total 28 scenarios / 263 steps: 01-start (8), 04-two-copies (12), 05-sigkill (7), 08-two-manifests (11), 09-bad-given-name (6),
10-name-taken-once (15), 11-labels-off-alphabet (5; `@start worker … labels=`, the VMS request «heartbeat and a garbled row»),
14-slot-gen-unreadable (8), 15-slot-row-free (6), 16-slot-foreign-box (7), 17-slot-torn-until (5), 18-epoch-edges (12),
19-schema-too-new (3), 20-schema-raised (11), 21-decommissioned (10), 22-start-refusals (10), 23-own-place-torn-hold (13),
24-store-silence (15), 26-epoch-floor (10), 27-epoch-floor-unreadable (10), 28-contender-waiting-refused (8),
29-contender-nameless-back (11), 30-slot-row-taking (6), 31-sub-decommissioned (12), 32-decommission-unreadable (8),
33-claim-clears-contributions (9), 34-foreign-place-torn-hold (11), 44-place-holder-pulse-unreadable (14).

**Scenarios of 2026-10-18** (reconciliation of python and go M10/3–5):
- sc. 08 step 8 — `rows` of the units door (P/06.1 N2): an element of a live heartbeat with `phase: running`, `worker`,
  `worker_state: live`; an empty `rows` with a live worker — FAIL;
- sc. 08 — the workers of two manifests: `t-1` `testsub2` (the name is also in `TALLY_NAME`, the dictionary `@start`), the slots are held, `gen` 1
  does not grow — an endless capture with a catalogue of two manifests is visible;
- sc. 09 — a wrong given name: `@start` confirms the start of the process, not its life; the worker exits with code 2, which the expectation
  `@exit 2` compares (the dictionary, `@start worker`); observable — neither a slot under this name nor the slot `w-1` (the name is not replaced by a search);
- sc. 10 — sc. 04 with the resource P/05 (`@start resource` as the first step): the platform journal `audit/<role>` (the event journal
  contract `journal`) is read by the events door of the console; exactly one row `worker.name_taken` — at the displaced copy; the second
  `GET` after 12 s — the same one. The resource of the stand is on the server of the controller (`srv-a`; ADR-0084 addendum (2) R17).
- sc. 04, 08, 10 — with the resource P/05 (`@start resource` as the first step): the controller and the console read the heartbeats of the workers through the objects door
  of the resource of their server; without the resource the reading is «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Sc. 01, 05, 09, 11 do not wait for placement.

**Scenarios of 2026-10-30** (coverage audit of P/03, audit-kimi `ba6666f13`, `fe341f708`). The rows that are not written by the console,
the judge puts and spoils through the door `admin` (full rights, the dictionary of the common acceptance README) — a write bypassing the writer, as the unit row
of sc. 12 of the acceptance of chapter 3.3; `cas` is not set where the writer itself rewrites the row (a write on top, P/01.1 N1
`cas`), — there is no race with the renewal. Sc. 09, 11 wait for the start refusal by the expectation `@exit 2` (the dictionary, `@start worker`).
- sc. 14 — an existing row `w-1` with an unreadable `gen` (released, `holder` empty): the worker with a given name does not
  rewrite it either at once or after `TORN_STILL` 50 s ([the slot contract](../../../common/contracts/slot.md) «Terms»), no name —
  no heartbeat (N1.4 the paragraph «An absent row…», N3 «capture», the table of transitions);
- sc. 15 — readable free rows: without `released` and with an empty `holder` (`gen` 7 → 8), a released one with a foreign `holder`
  (`gen` 3 → 4); the capture writes its own `server` (N3 «capture», the table of transitions; analysis of the review of stage B 3–5, № 6);
- sc. 16 — an occupied unreleased row of the box `otherbox`: NameOnAnotherBox — the row is the same, no heartbeat, no `worker.name_taken`
  (N3 «nobody and getting the name back», N4);
- sc. 17 — a torn row (`until` not by the form) with a readable `gen`: not touched for 12 s, after `TORN_STILL` captured with
  `gen` 8 (N3 «capture», the table of transitions);
- sc. 18 — epoch rows before the issue: `2^53 − 1` and not a number; after the assignment of units both rows are of the same version — the issue
  is refused before the write, 0 is not substituted (N1.5, N3 «take_epoch(id)», N4);
- sc. 19, 20 — the row `platform/schema` with `version` 2 (SCHEMA of the build 1, [the schema contract](../../../common/contracts/schema.md)):
  before the start — a start refusal with code 2, no slot; on the go — after a renewal the worker exits, the slot is not released (`released`
  as before, the version of the row does not change), there is no heartbeat any more (N3 «schema check by the worker»);
- sc. 21 — the row `platform/decommission/srv-a` before the start: no name, no heartbeat, no contender marks (the listing of the objects
  door is empty); the row is removed — a new worker takes the name (N3 «start()» step 3, N1.4a);
- sc. 22 — start refusals with code 2: the name from the unit names a foreign server (`w-srv-b-1`, N3 «start()» step `2c`), `INSTANCE_ID` and
  `BOX_ID` not by the grammar ([the instance contract](../../../common/contracts/instance.md) `forms`, `sources`), `SERVER_NAME`
  not by the grammar ([the environment file contract](../../../common/contracts/env-file.md)); no slots; `w-srv-a-1` — the name of its own
  server — is taken;
- sc. 23 — the own place `sh1` (the shelf names `srv-a`; `testsub2`: `places.lease: strict`, `lease.unconfirmed_max: 600`):
  the hold row is torn (`gen` not a number) — the worker does not rewrite it and holds the place longer than the strict window `CLOSE_BY`
  50 s: its own place is held for `WRITE_WINDOW` + `unconfirmed_max` (N3 «place: take, hold, let go», N1.3 `own_place`;
  the outcomes `holds.outcomes.tsv`).

**Scenario of 2026-10-30** (coverage audit of P/03 C11, audit-kimi `7f03ff89b`; the directives `@cut role`/`@mend role` — the dictionary of the common
acceptance README):
- sc. 24 — silence of the store for the role `testsubworker` (P/02.5 N1.4): the judge's proxy accepts the connections of the worker and does not
  forward bytes for 10 s — longer than the lease step `LEASE_EVERY` ≈ 8.3 s (N1.2: at least one renewal and one confirmation go into
  silence) and shorter than the lease window of 25 s from the last confirmed request (N1.6: it was no earlier than ≈ 8.3 s before
  the cut, the window stays open another ≈ 6.7 s after the mend). The store did not answer — «still mine» (N3 «renew», N4 «slot renewal: the store did not answer»):
  the slot is the same (`holder`, `gen` 1, `released` false); after `@mend` — a renewal by the same holder
  (`until` changed, `gen` as before — not a new capture), the lease is confirmed (the heartbeat element has no `lease`, chapter 3.4
  N1.1), the epoch of the unit has the same version and number (not released and not issued anew, N3 «lease_step()» step 4, «take_unit_epoch»),
  the placement is as before. The counts of the heartbeat under the silence and a silence longer than the window — «[Not judged in this lesson](#not-judged-in-this-lesson)» below.

**Coverage audit of P/03, second pass (Gemini)** (2026-10-30, the report `gemini/audit-coverage` `fad5fa2ba`, the drafts G01–G05;
analysis by the Specification). The rows that are not written by the worker, the judge puts through the door `admin`, as in sc. 14–23; the floor of epochs — by the service
write `op: floor` of the door `admin` (the dictionary of the common acceptance README, P/01.3 N1.3 `floor`): the floor is an integer, at the stand
`1 << 32` = 4294967296 and `2 << 32` = 8589934592 (the form of the floor of P/01.3 — the generation `<< 32`; the epochs are computed: `max(0, 4294967296) + 1`
= 4294967297, `max(4294967297, 8589934592) + 1` = 8589934593). The scenario names the box of the contender marks by the environment
`BOX_ID=box1` (the dictionary, `@start worker … <NAME>=<value>`): the key of the mark is `<sub>/contenders/<name>/<box>` (N1.4a).
- sc. 26 — the floor before the start: the first epoch of the unit is `max(0, floor) + 1`; the floor raised on the go above the epoch — the lease step
  confirms the lease by reading the floor, an epoch below the floor — `lost`, the unit is stopped and the epoch is released (N3 «confirm»,
  «lease_step()» steps 2, 4); the next pass takes a new `max(current, floor) + 1`, the heartbeat element — `running` under it
  (N1.5, N3 «take_epoch(id)»; chapter 3.4 N1.1 `status`);
- sc. 27 — the floor row is spoiled before the start (`@spoil row`: the body is not readable, the outcome of the family `epoch_floor` at `<s>worker` —
  «the whole row is unreadable»): the unit is assigned, the issue of the epoch is refused, the floor is not substituted by 0 — there is no epoch row (N3
  «take_epoch(id)»; P/01.3 `epoch_floor.outcomes.tsv`). Without the command `spoil-row` at the implementation — the scenario is not_executed
  (the dictionary);
- sc. 28 — the contender marks of two states «there was no own capture»: the given name `w-1` with an unreadable `gen` — there is no candidate
  without NameOnAnotherBox, the mark `waiting` with the sought name and its holder `""`; `w-2` is occupied by an unreleased row of the box
  `otherbox` — `refused` with `holder` and `holder_box`; no `worker.name_taken` — neither has lost a name (N1.4a,
  N3 «nobody and getting the name back», N4);
- sc. 29 — a second copy `w-1` of the same box took the name (sc. 04): the first one has the mark `nameless` (`instance` — its own,
  `holder` — the displacing one, `holder_box` — the same box), one `worker.name_taken`; the displacing copy is stopped by
  `@sigterm` — the slot is released, the first copy returns the name by a capture (`gen` 3, `holder` — its instance) and writes
  `worker.name_back` — after the `name_taken` of this episode (N3 «nobody and getting the name back» `rejoin()`; the event journal
  contract `journal`);
- sc. 30 — readable free rows that are not in sc. 15: `released: "taking"` of a foreign box (an unfinished capture —
  free for capture, the slot contract `taking`) — `gen` 4 → 5; `released: "false"` with an empty `holder` — `gen` 6 → 7;
  the capture writes its own `server` (N3 «capture», the table of transitions);
- sc. 31 — the decommission mark of the subsystem `testsub/decommissioned/srv-a` (the form of P/04 `decommissioned`): the worker `testsub` is
  nobody, there is no slot, heartbeat or contender marks; the worker `testsub2` of the same server takes the name — the mark of a foreign subsystem
  does not concern it (N3 «start()» step 3: `<sub>/decommissioned/<my server>`); the mark is removed — a new worker takes the name, as in
  sc. 21;
- sc. 32 — the row `platform/decommission/srv-a` is not readable by its form (`at: "x"`): no name, no heartbeat; the row is
  removed — the same worker takes the name (N3 «start()» step 3 «until it can be read»; `decommission.outcomes.tsv` `<s>worker` —
  «remains nobody until the row is readable»);
- sc. 33 — the capture of the released slot `t-1` of the former holder `otherbox`: before `released: "false"` the worker deletes under the guard
  the contributions of the predecessor by each `from` of the books of the manifest (`testsub2/notes/t-1`, `testsub2/rolls/t-1`: there is no row or there is
  no element of the predecessor in it — `@oneof`: the training writer of contributions `testsub2` may already have written its own row under the slot,
  the norms of chapter 3.6 N5); the contribution of a foreign slot
  `testsub2/notes/t-2` is of the same version (N3 «capture» step 4; [chapter 3.7](../../spec/03.7-worker.norms.md) N1.2 `claim`);
- sc. 34 — a foreign place `sh1` with a torn hold row (`gen` not a number, `by: t-9`): the worker does not take it either at once or
  after `LOST_AFTER + HOLD_SKEW` (the row is of the same version after 62 s); a free shelf `sh2` appeared — it takes it (N3 «place»
  `take_slot`: the torn ones — skip; `holds.outcomes.tsv` `<s>worker`).

Not taken from the second pass (the analysis is in the commit): the check of `W2C_MANIFEST_REV` at the start (the stand starts the worker not
by the runner `w2c-run.sh`, the variable is not set — the program does not check, N3 «start()» step 1, C03-MANIFEST-REV-UNSET-01;
P/02.3 N3 step 4 — the system acceptance, sc. 08 `@manual`).

**Scenario 44** (the draft G05c of the second pass of Gemini `fad5fa2ba`, rewritten into the form of acceptance by the Architect's decision of
2026-10-30, the questions of norms of the Gemini audit, P/03 item 1; C03-PLACE-PULSE-LIVE-ROW-01):
- sc. 44 — the worker `t-2` (`testsub2`) took the shelf `sh1` of the server `srv-a` and is killed by `@sigkill`: the hold row stands at the same
  version (`holder` — the instance of `t-2`, not `released`), its heartbeat is spoiled by `@spoil object` (the writer is stopped). The worker
  `t-1` of the same server is the taker: the place of another name is not taken at once, it waits `LOST_AFTER + HOLD_SKEW` without changes of the row by
  its own clock from the first look. 30 s after the capture of the slot by `t-1` the row is still in effect — the heartbeat of the holder is read,
  it is unreadable: the place is not taken, the row is of the same version (an unreadable heartbeat is not «the heartbeat is not fresh», N3 «place» `take_slot`;
  `heartbeats.outcomes.tsv` `<s>worker`). The row has stood for 50 s — it is no longer in effect by itself: the place is free by the row,
  the heartbeat is not read — `t-1` takes `sh1` (`gen` 2, `by: t-1`, a new `holder`) and names the shelf in the heartbeat. The draft expected
  the opposite (the place is not taken even after 60 s) — by the decision this is wrong.


## Stand and steps of the chapter

The boundaries of each scenario are those of the [testsub process stand](../../../common/acceptance/testsub-stand.md#testsub-process-stand). Own to the chapter:

- the read role of the store has full rights on `testsub/` and `testsub2/` (above); the door `admin` prepares the rows bypassing their writers;
- every worker has the box and the server of the stand, except `@start worker … on <server>` and the environment `<NAME>=<value>` of sc. 11, 22, 28, 29
  (the dictionary of the common acceptance README, `@start`; analysis of the review of stage B 3–5, № 33); the name is passed by the substitution
  `{name}` of the directive (the common acceptance README, «Stand»);
- the chosen `CAPACITY`/`WORKER_MEMORY_MB` satisfy N1.2 of chapter 3.4: a decreasing memory budget is not provoked;
- `@start` confirms the start of the process, not its life; the readiness of the slot is checked by the following `@until`. In 05-sigkill
  step 3 also waits for `released="false"`: the intermediate write of the capture with `released="true"` is not yet ready for SIGKILL, so the
  signal goes only after a completed capture; the control `until` is read after the confirmed termination of the process and compared after 20 s
  (a read before the signal would admit a race with the renewal).

The comparison is «Expectation» of the [dictionary](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) with the full form by
door. The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes of a unit;
a change of the epoch or of the assignment by itself does not prove that the old process has stopped working. 05-sigkill proves the invariance
of the row during the observed 20 s after the crash, not the common boundary of 90 s: the controller may get a reliable gone earlier.

## SDK seams of the chapter

The cases that need controlled clocks, store replies or the order of calls are rows of [seams.tsv](seams.tsv) through the ports of
[forms/README.md](../../forms/README.md#seams) (the judge runs them by the seam adapter protocol of the common acceptance README):

| Subject | Seams |
|---|---|
| the capture table: unknown read, unreadable `gen`, a lapsed row of another box, a stale and a fresh `names_given`, `taking`, the first start and a repeated search on its own box, a torn `until` at 49/50 s, the cleanup guard, a replay with the same id | `s1`–`s11` |
| the bounds of `gen` and of the epoch and the floor (2^53 − 1, beyond int64) | `s19`–`s30` |
| the full slot key of 1023, 1024 and 1025 bytes (`testsub/slots/` and a given name) | `s31-capture-key-1023`, `s32-capture-key-1024`, `s33-capture-key-1025` |
| `badkey` on the first and on the final write of the capture, on a write under the slot, on the issue and on the confirmation of an epoch (N3 «Full keys and store refusal») | `s34-capture-first-write-badkey`, `s35-capture-final-write-badkey`, `s36-slot-write-target-badkey`, `s38-issue-epoch-badkey`, `s43-confirm-badkey` |
| the guard after an own renewal, after a foreign one and after a change of gen alone (P/03.2-05) | `s18-guard-own-renewal`, `s37-guard-foreign-renewal`, `s48-guard-gen-changed` |
| the first lease window: the answer of the issue at 24, 25 and 30 s after the send, a floor raised after the issue, the same tick | `s39-epoch-answer-before-window-end`, `s40-epoch-answer-at-window-end`, `s12-epoch-initial-late`, `s13-epoch-post-grant-floor`, `s14-epoch-same-tick` |
| the gates around the local acceptance of a start: the fence before and after it, the old answer after the loss and the return of the name | `s41-gate-fence-before-accept`, `s15-gate-cancelled-late-start`, `s42-gate-old-answer-after-rejoin` |
| the window of the lease: an overslept request, a monotonic `last`, silence with `unconfirmed_max` off, 2 and forever at 26 s and the ceiling 2 reached at 27 s (P/03.2-07, -08) | `s16-confirm-overslept`, `s17-confirm-last-monotonic`, `s44-confirm-silent-off`, `s45-confirm-silent-below-ceiling`, `s46-confirm-silent-forever`, `s47-confirm-silent-ceiling-reached` |

The restart by revision under the same epoch and its wait under silence are the seams of [chapter 3.3](../3/seams.tsv) (`s1-revision-same-epoch`,
`s3-silent-revision-waits`). The producers of the contender marks are the scenarios: `refused` — sc. 16, 28 and the seam `s3-capture-lapsed-foreign`
(a lapsed unreleased row of another box is NameOnAnotherBox, without `worker.name_taken`), `waiting` — sc. 28, `nameless` — sc. 29; the priority of
`refused` — the traces of [contender-writer](../../forms/contender-writer.traces.tsv); a schema above the build on the go — sc. 20.

## The capture table and operations on names (R28-01/02)

The order of the names and the next number are the vectors [`slot-name`](../../../common/vectors/slot-name/README.md) (`order`, `next`): the
slot order of `w-0`, `w-01`, `w-1`, `w-2`, `w-10`, `w-a`, `w-b`, `w-srv-a-1` whatever the order of the source list, the next number without the
names outside the numeric grammar (`w-1` when there are only they), leading zeros and a suffix beyond 64 bits without overflow. The transitions of the capture are [`forms/slot-capture.tsv`](../../forms/slot-capture.tsv)
and the seams above; a free readable row, an occupied one, a torn one and its time are also the scenarios 14–17 and 30.

## Not judged in this lesson

- The counts `store_errors` and `stood_in` of the heartbeat under the silence of sc. 24: the deadline of waiting for an answer of the client and the
  repeats inside a logical call are decided by the implementation ([the store client contract](../../../common/contracts/store-client.md) `wait`;
  N1.6 «Network retries inside it»), and a step stuck longer than STALL depends on it (chapter 3.4 N3 «stand_in()»); checked by reading.
- A silence of the store longer than the lease window in real time, with `unconfirmed_max`: the stage of the system (P/03.2-04); the window itself
  is the seams `s16`, `s44`–`s47` on the scripted clock.
- The admission of the server before the presence lock (an empty `SERVER_NAME` and one outside the grammar end with code 2 before the lock is
  taken): the order against the OS lock is a race of processes, the stage of the system; the refusal outside the grammar is sc. 22 step 4
  (`@exit 2`, no slot), the field `server` of a live heartbeat is step 05/11 of [the acceptance of chapter 3.6](../6/README.md).
- A conflict of the issue write and its next attempt with its own send moment (the window from the new send, not from the first call): the port
  `worker-grant` has no conflict reply; checked by reading N3 «take_epoch(id)» and N1.6.
- The fence of a restart by revision during its start and the loss of `writing_allowed` during a fast request: checked by reading N3
  «lease_step()»; the gates of a first start are the seams above.
- `badkey` on the guard key and on the taking, renewal and letting go of a place: a reply of the store does not tell the guard key from the
  target key at the seam, and the place has no own port; checked by reading N3 «Full keys and store refusal» and «place: take, hold, let go».
- The deadlines of the slot at the judge of a slot (the first look, 45 s with gone, 90 s with unknown, a new judge at 80 s): the reader of the slot
  is the controller, [P/04](../../../04-controller/acceptance/README.md); the own write under the slot by the own confirmed term is
  `worker-slot-write` (`own_term_open`) and the seam `s16-confirm-overslept`.
- The order of the released names of `names_given` by name (`w-10` before `w-2`) against the slot order of the free ones, and a suffix of 100 nines
  with its variant with a leading zero: the vectors fix the slot order and a suffix beyond 64 bits; checked by reading N3 «capture» and the
  [slot name contract](../../../common/contracts/slot-name.md).
- A given name that fails the key limit in an automatic search (the next candidate is checked, a new computed name ends the search): the seams
  call the capture with a given name; checked by reading N3 «Full keys and store refusal».

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

The generic meanings of `@sleep` and `@until` are defined in the [common stand protocol](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). Scenario-specific wait steps, durations and reasons are kept in the [judge-only case instructions](sleeps.cases.md).

SDK boundary seams s19–s22 distinguish a readable maximum with generation_exhausted from unreadable existing gen above it: s21/s22 retain their original requests/raw bytes and no writes, with gen_readable=false. No new refusal word is introduced. s23–s26 separately cover epoch; s27–s30 keep the owner-defined floor and exact comparisons without int64 narrowing. CALL epoch=0 is confirmed absence, not a positive stored row.

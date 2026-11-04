# Acceptance P/03.2 — the slot, the epoch, the lease, nobody, the place (stand)

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#словарь-директив-и-дверей).
The norm of the chapter is [`03.2-worker.norms.md`](../../spec/03.2-worker.norms.md) Н5. The scenarios were moved from the acceptance of
М10/05 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones, except sc. 04 and 08: the first step is `@start resource`, the former ones are shifted by one (P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Sc. 02, 06 are the acceptance of chapter 3.3, sc. 03 — of chapter 3.4, the rest — [P/04](../../../04-controller/acceptance/README.md).

The scenarios run on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers
`testsub` (the training worker of counters), which the runner controls. The catalogue of the stand is two manifests, `testsub` and `testsub2`, in the order of
the section «Стенд» of the common acceptance README (reconciliation of python and go М10/3–5, item 24): the worker of one manifest does not touch the rows
of the other on capture and cleanup. The training worker `testsub` reports the started counter by the element `status` with `phase: running` (chapter 3.4 Н1.1
`phase`) and one word of the subsystem `n` — the value of the counter (chapter 3.4 Н1.1 `status`; the second pilot, `Н-7`). Observation — rows
through the store door P/01.1 and units through the console door P/06.1; the heartbeat (an object) is not read here. The controller of the stand is
a neighbour by contract (the data catalogue, the life cycle of P/04), not the norms of the chapter (the plan of the move of lesson 3, В2).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#словарь-директив-и-дверей):
the doors `store` (a role with read rights on `testsub/`), `console`, `resource` and `admin` (preparation of rows bypassing their writers — sc. 14–34;
the floor of epochs — `op: floor`, sc. 26, 27), the directives `@start` (with the expectation `@exit 2` and the environment `<ИМЯ>=<значение>` of the worker), `@sigkill`,
`@sigterm` (sc. 29), the expectation `@oneof` (sc. 33), `@sleep`, `@until`, `ASSERT`, `@cut role testsubworker store` / `@mend role testsubworker store` (sc. 24),
`@spoil row` (sc. 27), `@spoil object` (sc. 44);
the expectation is a subset of fields.

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of
the store without a rights file (P/01.2 Н1.2) — with full rights on `testsub/` and `testsub2/`.

The stand begins with an empty store and without workers; the runner stops everything it started after the last step of
a scenario. One scenario takes no longer than 3 minutes.

In total 28 scenarios / 263 steps: 01-start (8), 04-two-copies (12), 05-sigkill (7), 08-two-manifests (11), 09-bad-given-name (6),
10-name-taken-once (15), 11-labels-off-alphabet (5; `@start worker … labels=`, the VMS request «пульс и битая строка»),
14-slot-gen-unreadable (8), 15-slot-row-free (6), 16-slot-foreign-box (7), 17-slot-torn-until (5), 18-epoch-edges (12),
19-schema-too-new (3), 20-schema-raised (11), 21-decommissioned (10), 22-start-refusals (10), 23-own-place-torn-hold (13),
24-store-silence (15), 26-epoch-floor (10), 27-epoch-floor-unreadable (10), 28-contender-waiting-refused (8),
29-contender-nameless-back (11), 30-slot-row-taking (6), 31-sub-decommissioned (12), 32-decommission-unreadable (8),
33-claim-clears-contributions (9), 34-foreign-place-torn-hold (11), 44-place-holder-pulse-unreadable (14).

**Scenarios of 2026-10-18** (reconciliation of python and go М10/3–5):
- sc. 08 step 8 — `rows` of the units door (P/06.1 Н2): an element of a live heartbeat with `phase: running`, `worker`,
  `worker_state: live`; an empty `rows` with a live worker — FAIL;
- sc. 08 — the workers of two manifests: `t-1` `testsub2` (the name is also in `TALLY_NAME`, the dictionary `@start`), the slots are held, `gen` 1
  does not grow — an endless capture with a catalogue of two manifests is visible;
- sc. 09 — a wrong given name: `@start` confirms the start of the process, not its life; the worker exits with code 2, the runner does not compare
  the code (by reading); observable — neither a slot under this name nor the slot `w-1` (the name is not replaced by a search);
- sc. 10 — sc. 04 with the resource P/05 (`@start resource` as the first step): the platform journal `audit/<роль>` (the event journal
  contract `journal`) is read by the events door of the console; exactly one row `worker.name_taken` — at the displaced copy; the second
  `GET` after 12 s — the same one. The resource of the stand is on the server of the controller (`srv-a`; ADR-0084 addendum (2) Р17).
- sc. 04, 08, 10 — with the resource P/05 (`@start resource` as the first step): the controller and the console read the heartbeats of the workers through the objects door
  of the resource of their server; without the resource the reading is «not known» ([the object store client contract](../../../common/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; the Architect's decision of 2026-10-27). Sc. 01, 05, 09, 11 do not wait for placement.

**Scenarios of 2026-10-30** (coverage audit of P/03, audit-kimi `ba6666f13`, `fe341f708`). The rows that are not written by the console,
the runner puts and spoils through the door `admin` (full rights, the dictionary of the common acceptance README) — a write bypassing the writer, as the unit row
of sc. 12 of the acceptance of chapter 3.3; `cas` is not set where the writer itself rewrites the row (a write on top, P/01.1 Н1
`cas`), — there is no race with the renewal. Sc. 09, 11 wait for the start refusal by the expectation `@exit 2` (the dictionary, `@start worker`).
- sc. 14 — an existing row `w-1` with an unreadable `gen` (released, `holder` empty): the worker with a given name does not
  rewrite it either at once or after `TORN_STILL` 50 s ([the slot contract](../../../common/contracts/slot.md) «Сроки»), no name —
  no heartbeat (Н1.4 the paragraph «У отсутствующей строки…», Н3 «capture», the table of transitions);
- sc. 15 — readable free rows: without `released` and with an empty `holder` (`gen` 7 → 8), a released one with a foreign `holder`
  (`gen` 3 → 4); the capture writes its own `server` (Н3 «capture», the table of transitions; analysis of the review of stage B 3–5, № 6);
- sc. 16 — an occupied unreleased row of the box `otherbox`: NameOnAnotherBox — the row is the same, no heartbeat, no `worker.name_taken`
  (Н3 «nobody and getting the name back», Н4);
- sc. 17 — a torn row (`until` not by the form) with a readable `gen`: not touched for 12 s, after `TORN_STILL` captured with
  `gen` 8 (Н3 «capture», the table of transitions);
- sc. 18 — epoch rows before the issue: `2^53 − 1` and not a number; after the assignment of units both rows are of the same version — the issue
  is refused before the write, 0 is not substituted (Н1.5, Н3 «take_epoch(id)», Н4);
- sc. 19, 20 — the row `platform/schema` with `version` 2 (SCHEMA of the build 1, [the schema contract](../../../common/contracts/schema.md)):
  before the start — a start refusal with code 2, no slot; on the go — after a renewal the worker exits, the slot is not released (`released`
  as before, the version of the row does not change), there is no heartbeat any more (Н3 «schema check by the worker»);
- sc. 21 — the row `platform/decommission/srv-a` before the start: no name, no heartbeat, no contender marks (the listing of the objects
  door is empty); the row is removed — a new worker takes the name (Н3 «start()» step 3, Н1.4а);
- sc. 22 — start refusals with code 2: the name from the unit names a foreign server (`w-srv-b-1`, Н3 «start()» step `2c`), `INSTANCE_ID` and
  `BOX_ID` not by the grammar ([the instance contract](../../../common/contracts/instance.md) `forms`, `sources`), `SERVER_NAME`
  not by the grammar ([the environment file contract](../../../common/contracts/env-file.md)); no slots; `w-srv-a-1` — the name of its own
  server — is taken;
- sc. 23 — the own place `sh1` (the shelf names `srv-a`; `testsub2`: `places.lease: strict`, `lease.unconfirmed_max: 600`):
  the hold row is torn (`gen` not a number) — the worker does not rewrite it and holds the place longer than the strict window `CLOSE_BY`
  50 s: its own place is held for `WRITE_WINDOW` + `unconfirmed_max` (Н3 «place: take, hold, let go», Н1.3 `own_place`;
  the outcomes `holds.outcomes.tsv`).

**Scenario of 2026-10-30** (coverage audit of P/03 C11, audit-kimi `7f03ff89b`; the directives `@cut role`/`@mend role` — the dictionary of the common
acceptance README):
- sc. 24 — silence of the store for the role `testsubworker` (P/02.5 Н1.4): the runner's proxy accepts the connections of the worker and does not
  forward bytes for 10 s — longer than the lease step `LEASE_EVERY` ≈ 8.3 s (Н1.2: at least one renewal and one confirmation go into
  silence) and shorter than the lease window of 25 s from the last confirmed request (Н1.6: it was no earlier than ≈ 8.3 s before
  the cut, the window stays open another ≈ 6.7 s after the mend). The store did not answer — «still mine» (Н3 «renew», Н4 «продление слота: хранилище не ответило»):
  the slot is the same (`holder`, `gen` 1, `released` false); after `@mend` — a renewal by the same holder
  (`until` changed, `gen` as before — not a new capture), the lease is confirmed (the heartbeat element has no `lease`, chapter 3.4
  Н1.1), the epoch of the unit has the same version and number (not released and not issued anew, Н3 «lease_step()» step 4, «take_epoch»),
  the placement is as before. Not checked in the TSV (depends on a choice of the implementation): the count `store_errors` — the deadline of waiting for an answer
  of the client and the repeats inside a logical call are decided by the implementation ([the store client contract](../../../common/contracts/store-client.md)
  `wait`; Н1.6 «Сетевые повторы внутри него»); the stand-in heartbeat `stood_in` — whether a step gets stuck longer than STALL 12.5 s also
  depends on this deadline (chapter 3.4 Н3 «stand_in()»); silence longer than the window and `unconfirmed_max` — by reading (Н5 of the norms).

**Coverage audit of P/03, second pass (Gemini)** (2026-10-30, the report `gemini/audit-coverage` `fad5fa2ba`, the drafts G01–G05;
analysis by the Specification). The rows that are not written by the worker, the runner puts through the door `admin`, as in sc. 14–23; the floor of epochs — by the service
write `op: floor` of the door `admin` (the dictionary of the common acceptance README, P/01.3 Н1.3 `floor`): the floor is an integer, at the stand
`1 << 32` = 4294967296 and `2 << 32` = 8589934592 (the form of the floor of P/01.3 — the generation `<< 32`; the epochs are computed: `max(0, 4294967296) + 1`
= 4294967297, `max(4294967297, 8589934592) + 1` = 8589934593). The scenario names the box of the contender marks by the environment
`BOX_ID=box1` (the dictionary, `@start worker … <ИМЯ>=<значение>`): the key of the mark is `<sub>/contenders/<имя>/<коробка>` (Н1.4а).
- sc. 26 — the floor before the start: the first epoch of the unit is `max(0, пол) + 1`; the floor raised on the go above the epoch — the lease step
  confirms the lease by reading the floor, an epoch below the floor — `lost`, the unit is stopped and the epoch is released (Н3 «confirm»,
  «lease_step()» steps 2, 4); the next pass takes a new `max(текущая, пол) + 1`, the heartbeat element — `running` under it
  (Н1.5, Н3 «take_epoch(id)»; chapter 3.4 Н1.1 `status`);
- sc. 27 — the floor row is spoiled before the start (`@spoil row`: the body is not readable, the outcome of the family `epoch_floor` at `<s>worker` —
  «строка целиком нечитаема»): the unit is assigned, the issue of the epoch is refused, the floor is not substituted by 0 — there is no epoch row (Н3
  «take_epoch(id)»; P/01.3 `epoch_floor.outcomes.tsv`). Without the command `spoil-row` at the implementation — the scenario is not_executed
  (the dictionary);
- sc. 28 — the contender marks of two states «there was no own capture»: the given name `w-1` with an unreadable `gen` — there is no candidate
  without NameOnAnotherBox, the mark `waiting` with the sought name and its holder `""`; `w-2` is occupied by an unreleased row of the box
  `otherbox` — `refused` with `holder` and `holder_box`; no `worker.name_taken` — neither has lost a name (Н1.4а,
  Н3 «nobody and getting the name back», Н4);
- sc. 29 — a second copy `w-1` of the same box took the name (sc. 04): the first one has the mark `nameless` (`instance` — its own,
  `holder` — the displacing one, `holder_box` — the same box), one `worker.name_taken`; the displacing copy is stopped by
  `@sigterm` — the slot is released, the first copy returns the name by a capture (`gen` 3, `holder` — its instance) and writes
  `worker.name_back` — after the `name_taken` of this episode (Н3 «nobody and getting the name back» `воссоединиться()`; the event journal
  contract `journal`);
- sc. 30 — readable free rows that are not in sc. 15: `released: "taking"` of a foreign box (an unfinished capture —
  free for capture, the slot contract `taking`) — `gen` 4 → 5; `released: "false"` with an empty `holder` — `gen` 6 → 7;
  the capture writes its own `server` (Н3 «capture», the table of transitions);
- sc. 31 — the decommission mark of the subsystem `testsub/decommissioned/srv-a` (the form of P/04 `decommissioned`): the worker `testsub` is
  nobody, there is no slot, heartbeat or contender marks; the worker `testsub2` of the same server takes the name — the mark of a foreign subsystem
  does not concern it (Н3 «start()» step 3: `<sub>/decommissioned/<мой сервер>`); the mark is removed — a new worker takes the name, as in
  sc. 21;
- sc. 32 — the row `platform/decommission/srv-a` is not readable by its form (`at: "x"`): no name, no heartbeat; the row is
  removed — the same worker takes the name (Н3 «start()» step 3 «пока она не прочтётся»; `decommission.outcomes.tsv` `<s>worker` —
  «остаётся никем до читаемой строки»);
- sc. 33 — the capture of the released slot `t-1` of the former holder `otherbox`: before `released: "false"` the worker deletes under the guard
  the contributions of the predecessor by each `from` of the books of the manifest (`testsub2/notes/t-1`, `testsub2/rolls/t-1`: there is no row or there is
  no element of the predecessor in it — `@oneof`: the training writer of contributions `testsub2` may already have written its own row under the slot,
  the norms of chapter 3.6 Н5); the contribution of a foreign slot
  `testsub2/notes/t-2` is of the same version (Н3 «capture» step 4; [chapter 3.7](../../spec/03.7-worker.norms.md) Н1.2 `claim`);
- sc. 34 — a foreign place `sh1` with a torn hold row (`gen` not a number, `by: t-9`): the worker does not take it either at once or
  after `45 + HOLD_SKEW` (the row is of the same version after 62 s); a free shelf `sh2` appeared — it takes it (Н3 «место»
  `взять_место`: the torn ones — skip; `holds.outcomes.tsv` `<s>worker`).

Not taken from the second pass (the analysis is in the commit): the check of `W2C_MANIFEST_REV` at the start (the stand starts the worker not
by the runner `w2c-run.sh`, the variable is not set — the program does not check, Н3 «start()» step 1, C03-MANIFEST-REV-UNSET-01;
P/02.3 Н3 step 4 — the system acceptance, sc. 08 `@manual`).

**Scenario 44** (the draft G05c of the second pass of Gemini `fad5fa2ba`, rewritten into the form of acceptance by the Architect's decision of
2026-10-30, the questions of norms of the Gemini audit, P/03 item 1; C03-PLACE-PULSE-LIVE-ROW-01):
- sc. 44 — the worker `t-2` (`testsub2`) took the shelf `sh1` of the server `srv-a` and is killed by `@sigkill`: the hold row stands at the same
  version (`holder` — the instance of `t-2`, not `released`), its heartbeat is spoiled by `@spoil object` (the writer is stopped). The worker
  `t-1` of the same server is the taker: the place of another name is not taken at once, it waits `45 + HOLD_SKEW` without changes of the row by
  its own clock from the first look. 30 s after the capture of the slot by `t-1` the row is still in effect — the heartbeat of the holder is read,
  it is unreadable: the place is not taken, the row is of the same version (an unreadable heartbeat is not «пульс не свеж», Н3 «место» `взять_место`;
  `heartbeats.outcomes.tsv` `<s>worker`). The row has stood for 50 s — it is no longer in effect by itself: the place is free by the row,
  the heartbeat is not read — `t-1` takes `sh1` (`gen` 2, `by: t-1`, a new `holder`) and names the shelf in the heartbeat. The draft expected
  the opposite (the place is not taken even after 60 s) — by the decision this is wrong.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М10/05 (removed by the move), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are resolved by
`Platform/common/id-map.tsv`; analysis of the review of stage B 3–5, № 30).

## Scenario boundaries

Between scenarios the runner stops all the processes it started, resets the store (rows and objects) and the variables `$имя`: each scenario begins with an empty store, there is no slot `w-1`, the console is restarted.

## Exact preparation and completion

Each scenario gets a new isolated store, a new console, an empty id memory of the store
and empty POST claims, and also cleared objects of heartbeats/controller/contenders and cleared runner variables.
Before the start the catalogue `testsub` and `testsub2` from the common testdata and the service marks of the manifests are installed.
There are no foreign controllers, resources, spare processes or start timers. The console door is open from the loopback;
the read role of the store has access to testsub/ and testsub2/. The preparation uses separate administrative rights.

All the workers of a scenario have the constant BOX_ID of the stand and server = srv-a, except `@start worker … on <сервер>` (the dictionary of the common acceptance README; analysis of the review of stage B 3–5, № 33) and the environment `<ИМЯ>=<значение>` of sc. 22; each copy gets a new
instance. The name is passed by the substitution `{name}` of the directive (the common acceptance README, «Stand»; analysis of the review of stage B 3–5, № 33). A decreasing memory budget is not provoked: the chosen
CAPACITY/WORKER_MEMORY_MB must satisfy Н1.2 of chapter 3.4. The ordinary configuration of testsub uses
safe defaults; the parameters of the stand-in and of the deadlines are not accelerated for the sake of the test.

@start confirms the start of the process, the readiness of the slot is checked by the following @until.
In 05-sigkill step 3 also waits for released="false": the intermediate write of the capture with released="true"
is not yet ready for SIGKILL. Only after a completed capture is the signal sent.
@sigkill sends the signal to the right process and **waits for a confirmed termination**;
a timeout/a wrong process is a refusal of the runner, not ok. In 05-sigkill the control until is read after
this confirmation, then compared after 20 s: a read before the signal admitted a race with the renewal.
After the scenario the runner terminates and waits for all the created processes, including the first copy of w-1,
and only then deletes the state. A parallel scenario uses other ports and directories.

## Exact comparison and boundaries

The TSV header and comments are skipped. The step numbers are continuous inside a scenario.
@until repeats only the nested request and the comparison up to the limit; an exhausted limit — FAIL.
The directive ASSERT compares bound values: `$имя` is bound at its first appearance, then compared.
The new bindings of variables of each comparison attempt are first temporary: they become common only
after the match of the code and of the whole expect. A repeat of a variable inside expect is compared with its temporary
value. A failure of any field, type, array element or code discards all the new bindings of this
attempt; the already common bindings do not change. The order of traversing the fields does not change the result.
This applies both to an ordinary HTTP step, and to each attempt of @until, and to ASSERT.
The control for 04-two-copies, step 8: the old holder with gen="1" does not bind $h2; the next answer
with the new holder and gen="2" successfully binds $h2 to the new one. The earlier bound $h1 is kept.
@any requires the presence of a field; @absent — its absence; ~text — a string occurrence.
JSON types are exact, true is not equal to 1; objects are compared by the given fields recursively,
arrays — by the number, order and values of the elements, except arrays without a normed order (`configured`) — the dictionary of the common acceptance README. An expectation of a single code does not require an empty body.
The full HTTP answer additionally matches the contract of the store (P/01.1) or of units (P/06, chapter 6.1).

The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes
of a unit. A change of the epoch/assignment by itself does not prove that the old process has stopped working.
05-sigkill proves the invariance of the row during the observed 20 s after the crash,
not the common boundary of 90 s: the controller may get a reliable gone earlier. The other evidence is
Н5 of the norms, including another box and the closing of the place writer.

## Checks outside TSV after run 25

For unknown server keep the known BOX_ID/instance and the taken name, but do not set the server;
in a separate manifest enable places.server_field and places.lease: strict. Read the heartbeat through the objects door or check
the formation of the object by reading: server is present and equals "", server_unsaid contains the text of
ADR-0029, all places are strict. A separate variant with a known server gives a non-empty server and does not
contain server_unsaid. The substitution of BOX_ID instead of the server does not pass. The ordinary TSV sets srv-a
and does not observe this branch.

Check the comparison of @until on two consecutive answers: holder=old/gen="1", then
holder=new/gen="2", with expect holder=$h2/gen="2". The first attempt does not keep $h2; the second
passes and binds it to new. Check both orders of the fields and a repeat of a variable in one expect.
The common variables of the earlier successful steps remain unchanged after any failed attempt.

## A late answer of the epoch issue

Separately from the TSV check the first start on controlled clocks by
[the cases «First lease window»](#first-lease-window-check-after-run-26) below (from the acceptance of М10/03):
sending at 0, answers at 24/25/30; a pause between the answer and start_unit; a new CAS attempt with a new
sending time; a loss of the slot or of writing_allowed during the request. Record the calls of
start_unit, not only the number epoch. A late success does not start the unit and does not become silent
even with forever; the number is not rolled back. The next attempt requires a new successful reading of
the assignment. The TSV steps do not set this delay.

Check the race with the stand-in on both sides of the local acceptance of a start: fencing before it
does not give start_unit; fencing after it also sees an unfinished start and cancels/stops
it, the lease is fenced, a late result does not publish the managed unit anew. An additional
order: the epoch request → the loss of the name → the return of the name → the old answer; the old answer does not start
the unit even with the gates open again. Only a new attempt after a new reading of the assignment
can start. During the delay of the request/start_unit the stand-in is able to close the admission;
holding a lock through the whole external call, which hinders the fencing, does not pass the check.
Repeat the race for a restart by revision: no new number is issued, last is not reset,
the fencing cancels this start too. With silent and may_write=true the former unit can continue
the data, and the change of revision waits for a confirmation; after it the restart keeps the epoch/lease.

## Additional check of the class of errors of run 36 (Kimi)

By reading, reconcile all the producers of marks: NameOnAnotherBox gives refused; another case of the absence of a candidate — waiting until one's own first capture and nameless after the loss of the former one. The priority of refused is kept. The check of a schema above the build on renewal gives fenced without rejoin (Н3 «schema check by the worker»; the owner of the schema row — P/06.6).

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Cases of the acceptance of М10/03 on the slot, the epoch and the lease (the move of lesson 6)

Moved from the acceptance README of М10/03 with the move of lesson 6 (stage B): the main acceptance of the units door went to
[the acceptance of P/06.1](../../../06-console/acceptance/1/README.md), the cases below check chapter 3.2.

### Additional checks R29 — slot, epoch, guard, holds

For each case — a separate instance with testsub, empty rows and claim memory, the needed rights and a store with
a full key limit of 1024 UTF-8 bytes; there is no narrower file limit (P/06.1 Н1.3).

| Preparation and action | Expected outcome |
|---|---|
| The name w- + 1007/1008 letters (the full testsub/slots/… — 1023/1024), then w- + 1009 letters (1025) | The first two pass the limit of the string key and are captured; the last one — a refusal of the candidate without the first write. A given name stays nobody, the automatic search checks the next candidate; an error of a newly computed name ends the search |
| Badkey after the first write of the capture; separately on renewal; separately at the target key of a write under the slot | The capture does not give out a live slot and does not roll back what was confirmed; the renewal loses the name; the target write is refused, the key error by itself does not prove the loss of the slot |
| Badkey at the guard key; separately at the issue/confirmation of the epoch; separately at holds | The guard does not admit the write; the issue of the epoch does not start the unit, the confirmation — fenced; the taking of holds is refused, the renewal loses the place per [P/03.2 Н3 «place: take, hold, let go»](../../spec/03.2-worker.norms.md); the refusal does not turn into silent |

### Counterexamples of run 23 — slot and lease

For slots and the lease — a worker and controlled clocks/delays.

| Norm | Initial state and intervention | Expected observation |
|---|---|---|
| P/03.2-02 | The preferred name is held by a live instance of another box | NameOnAnotherBox: the process is nobody, the mark refused (without `worker.name_taken` — it is only on the loss of the name, [P/03.2 Н3 «nobody and getting the name back»](../../spec/03.2-worker.norms.md)), another name is not taken |
| P/03.2-02 | B on its first start takes the given name from A of the same box; A after the loss searches for its name again | A stays nobody: the right of the first start is not restored; the live slot of B is not rewritten |
| P/03.2-01, -02 | gen = bad, the row is still for 50 s; separately — gen = 7 and a torn until, also 50 s; separately — an absent row | unreadable gen: the candidate is refused, the row does not change (also on a release by the controller); readable gen: a new 8; absence: the first 1 |
| P/03.2-05 | the write is prepared with the guard v1; one's own renewal gives v2 with the same holder/gen; separately — v2 was written by another holder | in both cases the late write gets 412 and changes nothing; the re-read keeps the name in the first case and fences off in the second; the repeat uses a fresh check, not the old guard |
| P/03.2-07…08 | last = 0, the request at t = 20 did not answer; check t = 26 with off, 2, forever and t = 27 with the ceiling 2 | the actions are halted in all cases; the data at t = 26 are halted only for off, with 2 and forever they are allowed; at t = 27 the ceiling 2 is reached and the data are halted. Without a request inside the window — lost, the continuation of the data is not allowed |

### Slot deadlines (run 25)

For the slot a reading of the implementation or a controlled model is needed: one history of versions, the first look
of the judge at t=0, the writer's until with shifts -30/0/+300 s. At t=20 the liveness is the same; with gone
the judge may release after 45 s of observation, with unknown — not earlier than 90 s. A new judge
at t=80 starts its window from zero. A finite future until does not become torn.
One's own write under the slot is permitted only by the deadline of one's own confirmed
request; a re-read and a late answer do not start the window anew. The TSV of the units door does not measure these deadlines.

### First lease window: check after run 26

A separate controlled time/reading of the implementation by the owner, not the main TSV: the slot and the assignment
are obtained, all the gates are open, the request to write a new epoch is sent at t=0. A success with the answer at 24
permits a start until 25, answers at 25 and 30 — lost without a call of start_unit; the number could already be written
and is not rolled back. An answer at 24 with a pause until the start at 26 also forbids the start, if during the pause there was no
new confirmation. Repeat for off, a finite unconfirmed_max and forever: a late
first issue is not silent. For CAS-conflict the next attempt has its own t0:
a conflict at 30, a new sending at 31 and a success at 34 give a window from 31, not from the first call or from 34.
After a refusal a new successful reading of the assignment is required before a new attempt. Separately
lose the slot/writing_allowed during a request with a fast answer: the repeated gates forbid
start_unit, although the window is still open. A log of the real calls of start_unit and of the times of the requests is needed;
a single epoch row does not prove these outcomes (P/03.2-06, 07 and P/03.2-10).

### The capture table and operations on names (R28-01/02)

Each case is a separate initial state. Prefix = w; the read versions, the CAS result,
the observation time and the deletion of contributions are controlled by the stand or worked out by reading by the owner of the implementation.
These are the checks P/03.2-01, -02, -03; the 53 HTTP steps of the units door do not observe them.

| Preparation and action | Expected outcome |
|---|---|
| A free row w-1 with gen=bad; separately gen=7, until torn and age 49/50 s; separately a readable released | gen=bad is not rewritten; a torn until admits the transition only from 50 s, a new gen=8; a readable released admits the transition at once |
| The first CAS succeeds, then a refusal of the guard of a deletion or of the CAS of the final write; separately the success of the final write is not confirmed | The slot is not returned as live, there are no writes under it; foreign contributions are not deleted. On an unknown outcome the current operation is repeated with the same id per [P/03.4-07](../../spec/03.4-worker.norms.md); after a definite refusal a new capture gets fresh versions |
| A non-answer of the read of slots; separately an empty list read successfully | A non-answer leaves the process nobody. An empty list allows a process without a name to create w-1 |
| Free are w-b, w-10, w-1, w-01, w-2, w-a, w-0, w-srv-a-1; go through the candidates with a CAS refusal to the previous one | The slot order: w-0, w-01, w-1, w-2, w-10, w-a, w-b, w-srv-a-1; the order of the source list has no effect |
| Both names w-2/w-10 are released through names_given, then separately both are simply free | For names_given the order by name: w-10 first; for free ones — the slot order: w-2 first |
| All the listed names are occupied without permission; a process without a name has reached a new name | max=10, the new w-11; w-srv-a-1 and w-a do not enter the numeric max. If there are only they, the new w-1 |
| There is a digit suffix of 100 nines and its variant with a leading zero; a process without a name has reached a new name | The numbers are equal, the order distinguishes the full names; the new suffix — 1 and 100 zeros, without overflow. w-0 and leading zeros do not change the admissible grammar |

Also checked are the positive neighbouring transitions: the process takes a free slot;
the first start on its own box keeps the right of Н3; a repeated search does not get such a right;
a fresh names_given permits an occupied slot, a stale one does not. Both writes of the capture
and the guard of the cleanup are applied; the table of admission does not make them one atomic operation.

### Run 36 (Kimi) — name

NameOnAnotherBox includes an occupied unreleased lapsed row of another box; the mark refused, `worker.name_taken` is not written (only on the loss of the name).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 01 step 4 waits for the first renewal after step 3 (`until` ≠ `$u0`), step 6 — for the second
(`until` ≠ `$u1`; LEASE_EVERY ≈ 8.3 s, Н1.2 of the chapter; review of stage B 1–2, item 3). The remaining sleeps are a check of absence or the time before an action; the length is the smallest by the deadlines of Н1.2:

| Sc./step | Sleep | Reason |
|---|---|---|
| 04/11, 10/11 | 12 s | absence: the displaced copy does not take the name back; a repeat of the name search — once per CONTEND_EVERY 10 s |
| 05/6 | 20 s | absence: after SIGKILL the slot is not released and not renewed (the deadline is named in Н5, sc. 05) |
| 08/9 | 12 s | absence: `gen` does not grow — a repeated capture would be visible within a lease step ≈ 8.3 s |
| 09/3 | 12 s | absence: there are no slots under the wrong name — by this deadline the capture at the start would already have passed (a correct worker holds the slot by the step `@until 20`) |
| 10/14 | 12 s | absence: there is no second row `worker.name_taken` — a repeat of the mark would come after CONTEND_EVERY 10 s |
| 11/2 | 12 s | absence: there is no slot `w-1` — the worker with `LABELS` outside the alphabet refused at the start with code 2; a correct one would have captured the slot by this deadline, as in 09/3 (the VMS request «пульс и битая строка») |
| 14/4, 16/4 | 12 s | absence: the slot row is not rewritten — the capture at the start and the repeat of the search (CONTEND_EVERY 10 s) would have passed by this deadline |
| 14/7 | 50 s | absence: even after `TORN_STILL` 50 s from the first read (together with 14/4 — 62 s, a repeat of the search once per CONTEND_EVERY 10 s) the row with an unreadable `gen` is not rewritten |
| 17/3 | 12 s | absence: the torn row is not touched earlier than `TORN_STILL` — the capture at the start would have passed by this deadline |
| 18/10 | 12 s | absence: the epoch rows are not rewritten — the worker sees the assignment within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s (as 02/10 of the acceptance of chapter 3.3) |
| 20/6 | 12 s | time before an action: the renewal of the slot with the schema check passes within LEASE_EVERY ≈ 8.3 s; after it the version of the slot and `ts` of the heartbeat are bound |
| 20/9 | 12 s | absence: the version of the slot and `ts` of the heartbeat do not change — the renewal (≈ 8.3 s) and the heartbeat (HEARTBEAT_EVERY 10 s) would be visible |
| 21/4 | 12 s | absence: there is no slot and no contender mark — the capture at the start and the mark (CONTEND_EVERY 10 s) would be visible |
| 23/8 | 12 s | absence: the torn hold row is not rewritten — the renewal of the place at the lease step ≈ 8.3 s |
| 23/11 | 60 s | absence: the place is held even after the strict window — a strict one is released by `CLOSE_BY` 50 s from the last confirmation (≤ 8.3 s before the spoiling), the heartbeat — after HEARTBEAT_EVERY 10 s; together with 23/8 — 72 s |
| 24/9 | 10 s | time of silence: longer than the lease step LEASE_EVERY ≈ 8.3 s (the renewal goes into silence) and shorter than the lease window of 25 s minus the step (25 − 8.3 ≈ 16.7 s): the lease does not expire before the mend |
| 27/9, 31/6, 32/4 | 12 s | absence: there is no epoch row — the worker sees the assignment within LEASE_EVERY ≈ 8.3 s and the pass POLL ~2 s (as 18/10); there is no slot — the capture at the start and the repeat of the search (CONTEND_EVERY 10 s) would have passed (as 21/4) |
| 34/5 | 12 s | absence: the worker would have taken a free place at the first lease step after the capture of the slot (≈ 8.3 s; Н3 «lease_step()» step 6) |
| 34/7 | 50 s | absence: the foreign place is free, having stood without changes 45 + HOLD_SKEW = 50 s by the clock of the taker; together with 34/5 — 62 s: and the torn one is not taken after this deadline either |

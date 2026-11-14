# Acceptance P/04 — the controller

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the lesson is [`04-controller.norms.md`](../spec/04-controller.norms.md) N5. Scenarios and steps are in `scenarios.tsv`; scenario 11 steps 7–12 prepare the shelf, and scenarios 07, 11 and 13 begin with `@start resource`. The `/metrics` checks for scenario 03 step 5 and scenario 08 steps 7–9 belong to [the acceptance of P/06.5](../../06-console/acceptance/5/README.md). The console doors without workers are checked by [the acceptance of P/06.6](../../06-console/acceptance/6/README.md).

## Stand

The scenarios run on a stand of the `testsub` processes of the implementation: the store, the console `testsub`, the controller `testsub` and the workers `testsub`
(the training worker of counters), which the runner controls; sc. 11, 14–17, 34–39, 43, 44 — the controller and the workers `testsub2`. The catalogue of the stand is two
manifests, `testsub` and `testsub2`, in the order of the section «Stand» of the common acceptance README: the worker
of one manifest does not touch the rows of the other on capture and cleanup. The training worker `testsub` reports the started counter by the element
`status` with `phase: running` (P/03.4 N1.1 `phase`) and one word of the subsystem `n` — the value of the counter (P/03.4 N1.1 `status`). Observation — rows through the store door P/01.1, units and placement through the console door (`/where`,
`/unplaceable`, `/servers`, `/metrics`), the pass report `<sub>/controller/pass` — through the objects door of the resource (sc. 12, 15);
the heartbeat (an object) is not read here. The resource P/05 is needed by all the scenarios with workers and the controller — 03, 07, 08, 11–44 (the resource on the server of the controller; sc. 15, 33, 36–39, 44 — two resources): the controller reads the heartbeats of the workers through the objects door of the resource of its server, without the resource — «unknown» ([the object store client contract](../../common/contracts/object-client.md) `door`).

- **Pass report print command** of the controller `<sub>/controller/pass` ([P/04](../spec/04-controller.norms.md)) — a template with `{data}` and `{sub}`;
  prints the current report object or nothing if there is none; by it the runner waits for the report to change (the norms of P/04,
  «Implementation decides» item 9).

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors):
the doors `store` (a role with read rights on `testsub/`), `console`, `console2`, `resource`, `admin` (sc. 23 — the row `platform/schema`);
the directives `@start` (including `@start controller <sub> shrink_after=<s>`, `@start worker <sub> <name> on <server>`,
`@start worker <name> on srv-b` sc. 33 and `@start worker <name> labels=<labels>` sc. 24), `@sigterm`, `@sigkill`, `@sleep`, `@until`,
`@as` (including `@as console store …` sc. 08, 24, 34, 35; `@as testsubcontroller store …` — rows of the controller bypassing it,
sc. 28–32, 41; `@as testsubworker store …` sc. 13, 21, 42), `@grow`, `@cut role testsubcontroller store` / `@mend role testsubcontroller store` (sc. 25), `@freeze w-1` /
`@thaw w-1` (sc. 26, 27); the expectation — a subset of fields, `@any`, `@absent` (sc. 21), `@time` (sc. 03, 23, 25), `@oneof` (sc. 21), `@exit 2` at
`@start controller` (sc. 23).

The processes are started per the section «Stand» of the common acceptance README (the commands of roles, the environment of the worker); the read role of the store
without a rights file (P/01.2 N1.2) — with full rights on `testsub/` and `testsub2/`.

The stand begins with an empty store and without workers; the runner stops everything it started after the last step of
a scenario. One scenario takes no longer than 3 minutes.

**Scenarios:**
- sc. 03 — the snapshot: after a pass of the controller the object `testsub/snapshot/unplaced` with the unit `s1`,
  `worker: null`, without secrets (the norms N1.3a; the time `ts` — `@time`);
  the object is read through the objects door of the resource (`@start resource`);
- sc. 07 — two workers of equal free capacity, `w-2` is started, then `w-1`: a new unit goes to `w-1` (the norms N3 «first by name»;
  the mutation check 7cecaf2 № 23);
- sc. 08 — the snapshot with spoiled records: the row `testsub/counters/s7` with `start: "notint"` is written by the runner
  by the role `console` (`@as console store …`); it does not enter the shard, the shard `unplaced` is published with `s8`, the pass report —
  `snapshot_rows_garbled: 1` (the norms N1.3a garbled, N1.2);
- sc. 11 — `group_by` of `testsub2` (`feed`, the norms N1.3): two `tallies` without a value and one written bypassing the door with
  an unreadable `feed` are not a group; each is placed on `t-1` by itself and does not wait for a common group. `testsub2` has `spread_by: zone`:
  the three `tallies` have no `zone`, and an empty value does not separate — all three are on one worker (the norms N1.3). `testsub2` has
  `servers: distinct` and the place from the heartbeat (`place_by: shelf`): units are given only to the keeper of a non-empty place,
  therefore steps 4–5 put the shelf `s-1` on the server of `t-1` (`srv-a`) and wait for the hold row `testsub2/holds/s-1`;
- sc. 12 — `@sigkill` of a worker with a live resource P/05 and a second worker `w-2`: the resource sees the lock free, the fate of
  `w-1` is `move` (`why` — a word about `gone`, as a substring), `c12` moves to `w-2` within 60 s, then the slot `w-1` is released (`released: true`; `move` is visible in the report of one pass, 5 s, — the step `fates` goes before the check of the move) ([the presence lock contract](../../common/contracts/presence-lock.md), the norms N3 «fate»; the norms do not tell to remove the placement before a new target); as sc. 10 of the acceptance of P/03.2 — after P/05;
- sc. 13 — an abandoned capture: step 7 waits for epoch 1 — `w-1` has started `c13` (the placement row does not
  mean this: the worker reads the assignment once per LEASE_EVERY, P/03.3 N3 «loop()»); `@sigkill w-1`, then the first write of the capture
  `released: "taking"` bypassing the writer (the role `testsubworker`, a foreign box, `gen` 2); `c13` stays on `w-1` in the nearest
  passes (step 12 after 10 s — two passes of the controller, less than SLOT_TERM) and goes to `w-2` after SLOT_TERM of an unchanged
  version with a reason about an unfinished capture (the norms N3 «leaving»); `"true"` would take it away at once (sc. 03 of the acceptance of P/03.4).
  A completed capture (the second write) does not take the unit away — by reading;
- sc. 14, 15 — the order of workers: `testsub2` with `grows: true` without `placement.weight` — each unit weighs 1
  (the norms N1.3), the default capacity is 8: the ninth `tally` on one base (sc. 14, 16) and the seventeenth on two (sc. 15) —
  a shortage of one process; `@grow <server>` executes the series `testsub2_workers_wanted{server}` instead of the script (the dictionary
  of the common acceptance README). Sc. 15 — two resources (after P/05; the door `resource` of the steps is the resource `srv-a` on the server of the controller, `{rport}` of the first
  `@start resource`; the second — `@start resource on srv-b`): «failed to raise» is observed — the order on `srv-a` without `@grow`, after
  `WANT_GRACE` `want` goes back, `raise_failed`, the order on `srv-b`. The shrinking (`SHRINK_AFTER` 300 s) does not fit into the ceiling of 3 min of the scenario
  — it is checked by sc. 16 with `shrink_after=20` (`W2C_SHRINK_AFTER`). A refusal to start a process by the order
  (systemd did not raise the instance of the unit, code 2 of the process) and a number above want (the process came up after the withdrawal by the deadline — outside the pool,
  the script stops it, want is not raised) — by reading: `@grow` raises the process at once or does not raise it at all
  (a debt of the stand);
- sc. 16 — the shrinking: all nine `tallies` are deleted (the hysteresis `per` 8 requires 8 free at the remaining one), the assignment of
  `t-srv-a-2` is empty — `retiring` and `want − 1` in one write, `@grow` stops `-2`. The transfer of the units of the victim the stand does not
  observe: with capacity 8 and `per` 8 the hysteresis requires 8 free at the remaining ones — by reading;
- sc. 17 — `distinct`, one shelf: `testsub2` has the place from the heartbeat,
  there is one shelf (`s-a1` on `srv-a`), the base `t-srv-a-1` holds it and carries eight `tallies`; the ninth — a shortage, the growth — one
  trial process (`want` 2), `@grow` raises `t-srv-a-2` without a place; it carries no units, `t9` is in `/unplaceable` with
  the words `no free shelf`; within 25 s (the deadline `shrink_after=20` and the pass step 5 s) `want` does not grow and `t-srv-a-2` is not shrunk
  (after P/05: the resource writes `room.testsub2`). The branch «live workers without a place are not shrunk while units wait»  the stand does not distinguish
  from the hysteresis: the remaining `t-srv-a-1` has free 8 − 8 = 0 < `per` 8, and the shrinking is forbidden with any definition of
  «no shortage»; a preparation where the hysteresis would allow shrinking with waiting ones the stand with one shelf and capacity 8 does not give —
  the branch is checked by the vector [`shrink-allowed`](../vectors/shrink-allowed/README.md) — the rows `placeless-with-waiting`
  (the hysteresis would pass) and `placeless-no-waiting` (N5);
- sc. 18, steps 15–19 — the protection of a replay on deletion (N3 step 8; the row check contract «The customer's row: `made`» `delete`):
  the order row `testsub-c3` with `ends` in 2001 and `made.keep` 9999999999 (2286) — the clock of the controller is not later than `keep`, the row
  is not deleted, and its state (born matched) is not removed by the cleanup; within 12 s (two passes) the deletion would have been tried
;
- sc. 20 — a restart of the controller (N3 «Races»): after `@sigterm controller` and a new `@start controller` the placement row
  of `c20` is the same (the version `index` and `rev` did not change: the decision is read, not revised), epoch 1; the new instance
  works — it places `c21` (within 90 s: the turn of the former holder may wait TURN_TERM 45 s);
  sc. 47 repeats the same observations after `@sigkill controller`, with confirmed termination before restart;
- sc. 21 — the write `release` (N3 «fate», «write release»; the table below, the last row): three workers without units
  are killed by `@sigkill`, the resource is alive; the slot `w-1` (readable) is released with the former `holder`, `until`, `gen`, `server`, the name `w-1` is in
  `names_given` (the fate `release`, not `move`: there are no assigned units); `w-2` — a row bypassing the writer with a torn `until` and
  a readable `gen` 2: released wholly and nobody's (`holder` "", `until` — zero Time in the writer form, `gen` 2, `server` as read);
  `w-3` — a row with an unreadable `gen`: it does not change (the version `index` is the same), the name `w-3` is not in `names_given`; the released `w-1` is taken
  by a new process with `gen` 2. The window of `names_given` is the pass of the release: the step of the report goes before the steps of the rows
;
- sc. 22 — a group as a whole (N1.3 `group_by`, N3 «choose»: free ≥ Σ of the weights): nine `tallies` with one host `feed` — one
  group of weight 9 with capacity 8 — none is placed (`unplaced` 9, `/where` 404), `g10` without `feed` is placed; after
  the deletion of `g9` and `g10` the group of eight with 8 free — wholly on `t-1`. The units and the shelf are set up before the worker: the first
  pass with the keeper of the shelf sees the group as a whole, not in parts;
- sc. 23 — the schema check at the start of the controller ([the schema contract](../../common/contracts/schema.md) «Check at start»):
  `platform/schema` with `version` 2 (above SCHEMA 1) and `x` (not a number) — `@start controller` exits with code 2, there is no pass report;
  with `version` 1 — the controller starts and writes the report. The resource is raised before the write of the row: it checks the schema at its own
  start. The branch «read error — wait» — sc. 25, «before reading the manifest» — by reading;
- sc. 24 — the labels of a server (N1.1 `platform/servers/<host>`, N1.3 `constraint`, N3 «pass()» step 5): the labels of the node of `w-1` —
  `{zz}`; the row `{qq}` beats the node — `c1` with the label `qq` is placed; an empty row reaches nothing: the forecast
  `will_move` names `testsub/c1`, `c1` is removed with a reason of reachability, `c2` with the label `zz` is not placed within 12 s (the labels
  of the node would accept it); the row is removed — the labels of the node again: `c2` is placed; the row `{qq, zz}` — `c1` is again on `w-1`; a row
  bypassing the writer with an unreadable label `qq!` — the last read labels and without a judgment of reachability: within 12 s neither `c1`
  (the labels of the node do not accept it) nor `c2` is removed (the outcomes of the family `server-labels`, the reader `<s>controller`);
- sc. 25 — a read error of the schema row at the start of the controller ([the schema contract](../../common/contracts/schema.md) «Check at start»:
  «read error → wait for availability without starting work»): `@cut role testsubcontroller store` before the start —
  the store is silent to the role of the controller (P/02.5 N1.4), the read of `platform/schema` hangs without an answer; within 10 s there is no pass report
  (the work is not begun); after `@mend` the controller without a new `@start` writes the report — it waited and did not exit (a refusal of the start is
  repeated only by a restart of the unit). The deadline `@until` 90 s — the repeat of the read after a non-answer is decided by the implementation, as with the resource
  (sc. 18 of the acceptance of P/05);
- sc. 26, 27 — a silent live worker (N3 «fate»: the order of the rules and the margin): `@freeze w-1`
  stops the whole process with all the threads — the loop and the stand-in (the slot is not renewed, the heartbeat is not written), the process is alive and
  holds the flock of the presence lock ([the presence lock contract](../../common/contracts/presence-lock.md)): the resource says
  `runs` (`running` of the heartbeat of the resource — both before and during the freeze). The last version of the slot was written no earlier than a lease
  step ≈ 8.3 s before the freeze (P/03.2 N1.2), therefore the margin «the same version is observed for < SLOT_TERM + LOST_AFTER» (SLOT_TERM + LOST_AFTER)
  holds `alive` no less than ≈ 81.7 s from the freeze: sc. 26 step 11 after 75 s sees `alive`, then — `hung` (the rule
  «resource live ∧ process runs»), no later than ≈ 100 s (the first observation of the version — a PASS_EVERY pass, one more pass for the report). With
  `hung` the name is not released (`names_given` is empty; the effective HUNG_MOVE_AFTER — [the environment file contract](../../common/contracts/env-file.md)),
  the slot is not released, the unit `c26` stays on `w-1` (`hung` is not in MOVED_FATES, N3 «leaving»). Sc. 27 — the same without units:
  `hung`, not `release` (the table «Release transitions»: the presence `runs` — write nothing). After `@thaw` the worker
  renews the slot — `alive` again. The freeze is no longer than the limit of the directive 120 s: sc. 26 — 75 + up to 35 s, sc. 27 — up to 110 s.
  `hung_moved` (the effective HUNG_MOVE_AFTER) and the `why` of the word `hung` — by reading (beyond the ceiling of the scenario; the norm does not fix the word of the reason).

## Scenarios 28–42

The scenarios are in the forms of sc. 13, 18–27 (rows bypassing the writer `@as <role> store`, the pass report through the door of the resource, `@sleep` with
a reason in the table of sleeps); the rows of the controller before its start are written by the role `testsubcontroller` (as sc. 07 of the acceptance of P/06.5).
The revision of the manifest of the stand is 1 (the first installation, P/02.3 N1.5).
- Sc. 28 — the restoration of intent (N1.5; N3 «accept and complete a decision», «On holder change recover active intent from step 3»):
  before the start of the controller the assignment of `w-1` carries `c1`, the intent row is active `{c1} → w-2`;
  the first holder removes `c1` from `w-1` (`rev` 2, `units` ""), writes the placement row of `c1` with the target, the reason and
  the `manifest_rev` of the intent (`rev` 1 — there was no row), adds `c1` to `w-2` (`rev` 1) and moves the intent into idle — the row is
  not deleted. The witness does not know intent — reconciled with the norm.
- Sc. 29 — `sync` (N3 «pass()» step 4, «Materialization and sync»; N1.2 `diverged`): the assignment of `w-1` is rewritten without `c1`
  (cas of the read version); the next pass returns `c1` (`rev` 3 — one write of the addition, there is nothing to remove), the report
  of this pass is `diverged: 1`; the step of the report goes before the step of the row (the window of one pass).
  The discrepancy is made by one change: two writes (removing from `w-1`, adding to `w-2`) a pass could split — the count and `rev` would be
  ambiguous.
- Sc. 30 — an unreadable intent row (N1.5 «An intent row out of form is unreadable», N4): `state: broken` — the pass report
  `ok: false`, `c1` is not placed within two passes with a live `w-1`, the intent row is the same (the version); restored
  (idle by cas) — `c1` is placed. 503 of `/where` for such a row — sc. 07 of the acceptance of P/06.5.
- Sc. 31 — manifest_rev (N3 pass step1, manifest_rev guard; N1.2 manifest_behind): c1 lacks its required revision, is intentionally unreadable and is not repaired; index/rev/items remain unchanged. c2 has revision 2 but no unit row: the guard forbids deletion, the row stays and manifest_behind: 1 counts it once per pass. The w-1 assignment with c1,c2 is not rewritten.
- Sc. 32 — a turn with a newer revision ([the turn contract](../../common/contracts/turn.md) step 1): the row
  `placement_turn` with `manifest_rev` 10 — the controller does not take it and does not rewrite it (the version is the same), `c2` is not
  placed within two passes; `c1` is placed before the write (the controller worked).
- Sc. 33 — a drain with live workers (N3 «leaving»: the server is being drained; P/06.6 N2 `/drain`): `c1` on `w-1` (`srv-a`),
  `w-2` on `srv-b`; `POST /drain?server=srv-a` — `c1` goes to `w-2` with the reason `server srv-a draining`, `GET /drain` —
  `safe: true` (there are no units on `srv-a` — the assignment and the `status` of the heartbeat, `@until` 60 s: the worker stops the unit and
  writes the heartbeat), `DELETE /drain` — `draining: ""`. The counts of the console without workers — sc. 04, 07 of the acceptance of P/06.6.
- Sc. 34 — `retire_when` by the state (N1.3 `retire_when`; [the row check contract](../../common/contracts/row-check.md)
  «Unit state» `acts`): the holder of `t1` writes `result` `{state: open}` (P/03.6 sc. 09); its row is rewritten to
  `done` by cas — the state is in effect (born and the revision of the row), `t1` is removed with the reason `done`, the assignment is empty, it does not enter
  `unplaced` (0); the row of the unit is not deleted (`delete_after` 600 s — by reading), the effective state is not removed by the cleanup.
- Sc. 35 — the cleanup of a state with a foreign `born` (N3 step 8a): the row of the unit `t2` is live, the state row has another `born`:
  orphaned, removed, `state_swept_total: 1`; the row of the unit is not touched (the cleanup without the row of the unit and after its deletion
  — sc. 18).
- Sc. 36–39 — `testsub2` on two servers (N1.3 `spread_by`, `affinity`, `home`; N3 «choose», «leaving», step 7). The shelf of
  `srv-b` is set up after `t-srv-a-1` has taken `s-a1`: which of the shelves of its server a worker takes is decided by the order of
  the subsystem (P/03.2 N3 «place: take»), therefore each server has one shelf. 36 — `z1a`, `z1b` of one zone `z1`: the second one
  is not placed on the same server (`unplaced: 1` — a pass that would place it would give 0), a worker of `srv-b` — it is on
  it. 37 — `r1` on the shelf `s-b1` `kind: reserve` (binding by `strict`) leads only to the holder of `s-b1`: with a live
  `t-srv-a-1`, which carries `u0`, it is not placed; `t-srv-b-1` has taken `s-b1` — `r1` is at it. 38 — `h1` with the home `s-b1` (`home:
  shelf`, the server — the `server` of the shelf row) is first at `t-srv-a-1`, then moves home to `t-srv-b-1` (step 7, the deadline
  `@until` 90 s: N1.4a `fresh_controller`); the words of the reason of the move home are not fixed by the norm (`SHOULD`) — they are not
  compared. 39 — the shelf `s-a1` is rewritten with `admits: false` (a repeated `POST /shelves`, P/06.1 N2) — `u1` goes to
  `t-srv-b-1` with the reason `t-srv-a-1's shelf s-a1 admits no unit`.
- Sc. 40 — the shard of a worker (N1.3a; N3 «snapshot — after the pass»): `testsub/snapshot/w-1` with `c1` (the fields `snapshot`
  of the manifest, `worker`, `server`), the shard `unplaced` is empty (`worker: null`, `counters: []`); `@sigterm w-1` — `c1` in the shard
  of `w-2`, the shard `w-1` is published empty in the same form: `worker: null`, `counters: []` (N1.3a — one form of an empty shard).
- Sc. 41 — an unreadable assignment (N4 «heartbeat/slot/assignment is unreadable»; the outcomes of the family `workers`): the row `workers/w-1`
  with `rev: x` — `w-1` is not in the pool: `c1` is at `w-2` (with equal capacity the first by name is `w-1`, sc. 07), `garbled: 0`, the controller
  does not rewrite the row. The witness reads such a row by `units` and keeps the worker in the pool — the norm is right.
- Sc. 42 — the fate `wait` (N3 «fate»; the table «Release transitions»): an occupied slot `w-9` without a process, the resource is alive — the resource knows nothing about
  the worker (`unlisted`); before the margin SLOT_TERM + LOST_AFTER — `alive`, then `wait`: `names_given` is empty
  (the effective HUNG_MOVE_AFTER), the slot row is the same. `wait` beyond HUNG_MOVE_AFTER — by reading (beyond the ceiling of the scenario).
  After forced controller termination and restart, the new observer reports alive again without rewriting the slot; the 60 s wait allows the former turn term and stays below the 90 s slot margin.

### Home at the place holder (sc. 43, 44)

Scenarios 43 and 44 check the home at the holder of a place.

- Sc. 43 — the home at the holder of a place (N1.3 `home`; N3 «choose», step 7): two shelves on `srv-a`. Which
  shelf is at which worker is set by the order of the steps: `s-a2` is set up after `t-1` has taken `s-a1`, and `t-2` is left with one
  free shelf (P/03.2 N3 «place: take»: the order of the subsystem has nothing to choose from). The names `t-1`, `t-2` are not processes of the role
  (the slot name contract: there is no server in the name), `want` does not apply to them, and the second worker needs no order. The zones of the shelves
  are different: `must_match` equates the zone of a unit with the zone of the shelf, and `spread_by` will not let two units of one zone onto one server.
  `h1` with the home `s-a2` and `u1`, `u2` without a home are on `t-1`: there is no holder of `s-a2`, the home is `srv-a`. `t-2` has taken `s-a2` — `h1` moves to it
  (step 7, the deadline `@until` 90 s, as sc. 38); a comparison with the server would have left it on `t-1`. The load is now `t-1` 2 and `t-2` 1:
  `t-2` is freer, but `h2` with the home `s-a1` goes to `t-1` — the rank of the home is senior to the capacity; a comparison with the server would have given it to `t-2`.
  `u1` without a home does not move. Sc. 38 is not changed by this: there is one shelf per server there, the holder of `s-b1` is the only worker of `srv-b`.
- Sc. 44 — the home on a place without a server (N1.3 `home`, a volume without a server; step 7): the form of sc. 38, but the shelf
  `s-n` has no `server`. There is no holder, there is no server field — there is no home, `h1` is on `t-srv-a-1`. `s-n` is set up after `t-srv-a-1`
  has taken `s-a1`, therefore `t-srv-b-1` gets it (a shelf without a server is not excluded by N3 «place: take»: the condition on the server
  there is only for a place which «follows the name»). The holder has appeared — `h1` moves to it (step 7, the deadline `@until` 90 s, as
  sc. 38); without a home on an empty server field the unit would have stayed on `t-srv-a-1`.

The controller executes a server decommission request that the console writes only for a silent server (P/06.6 N3); the witness holds that request standing, and `DELETE /servers/{server}/decommission` returns `{}`. This acceptance stand has no `@put object` directive for a heartbeat. The reason `deleted` is checked by scenario 06 of the acceptance of P/03.3.

### Recovery and corrupted turn (sc. 45–47)

Sc. 45 begins with a valid persisted want=2/retiring=t-srv-a-2 row and an empty assignment of that live victim. The stand confirms both published worker heartbeats and the unchanged seeded want version before starting the controller. A new controller completes want=1 and clears retiring within 30 s, without waiting a new default SHRINK_AFTER. The stand has no worker script running here and does not claim an OS stop. Sc. 46 varies the sc. 30 background by corrupting placement_turn.manifest_rev instead of intent: failed pass, absent placement and unchanged turn version; after a CAS repair of the turn, placement progresses. Sc. 47 checks forced controller restart as described with sc. 20.

## Scenario boundaries

Between scenarios the runner stops all the processes it started, resets the store (rows and objects) and
the variables `$name`: each scenario begins with an empty store, there is no slot `w-1`, the console is restarted.

## Exact preparation and completion

Each scenario gets a new isolated store, a new console, an empty id memory of the store
and empty POST claims, and also cleared objects of heartbeats/controller/contenders and cleared runner variables.
Before the start the catalogue `testsub` and `testsub2` from the common testdata and the service marks of the manifests are installed.
There are no foreign controllers, resources, spare processes or start timers. The console door is open from the loopback;
the read role of the store has access to testsub/ and testsub2/. The preparation uses separate administrative rights.

All the workers of a scenario have the constant BOX_ID of the stand and server = srv-a, except `@start worker … on <server>` (the dictionary of the common acceptance README);
each copy gets a new instance. The name is passed by the substitution `{name}` of the directive (the common acceptance README, «Stand»).
A decreasing memory budget is not provoked: the chosen CAPACITY/WORKER_MEMORY_MB must satisfy P/03.4 (the budget).
The ordinary configuration of testsub uses safe defaults; the parameters of the stand-in and of the deadlines are not accelerated for the sake of the test.

@start confirms the start of the process, the readiness of the slot is checked by the following @until.
@sigterm and @sigkill send the signal to the right process and **wait for a confirmed termination**;
a timeout/a wrong process is a refusal of the runner, not ok. After the scenario the runner terminates and waits for all the created
processes, and only then deletes the state. A parallel scenario uses other ports and directories.

## Exact comparison and boundaries

The TSV header and comments are skipped. The step numbers are continuous inside a scenario.
@until repeats only the nested request and the comparison up to the limit; an exhausted limit — FAIL.
The directive ASSERT compares bound values: `$name` is bound at its first appearance, then compared.
The new bindings of variables of each comparison attempt are first temporary: they become common only
after the match of the code and of the whole expect. A repeat of a variable inside expect is compared with its temporary
value. A failure of any field, type, array element or code discards all the new bindings of this
attempt; the already common bindings do not change. The order of traversing the fields does not change the result.
This applies both to an ordinary HTTP step, and to each attempt of @until, and to ASSERT.
@any requires the presence of a field; @absent — its absence; ~text — a string occurrence.
JSON types are exact, true is not equal to 1; objects are compared by the given fields recursively,
arrays — by the number, order and values of the elements, except arrays without a normed order (`configured`) — the dictionary of the common acceptance README. An expectation of a single code does not require an empty body.
The full HTTP answer additionally matches the contract of the store (P/01.1) or of units ([P/06](../../06-console/spec/06-console.api.openapi.yaml), chapter 6.1).

The scenarios observe rows and HTTP answers, not the contents of the heartbeat objects and not the actual external writes
of a unit. A change of the epoch/assignment by itself does not prove that the old process has stopped working.
The other evidence is N5 of the norms of the lesson («Evidence outside TSV»).

## Sleeps (`@sleep`)

The generic meanings of `@sleep` and `@until` are defined in the [common stand protocol](../../common/acceptance/README.md#dictionary-of-directives-and-doors). Scenario-specific wait steps, durations and reasons are kept in the [judge-only case instructions](sleeps.cases.md).

## Count

In total 40 scenarios / 575 steps: 03 — 4, 07 — 9, 08 — 6, 11 — 12, 12 — 12, 13 — 15, 14 — 28, 15 — 38, 16 — 32, 17 — 23, 18 — 19, 19 — 6,
20 — 13, 21 — 20, 22 — 23, 23 — 9, 24 — 21, 25 — 7, 26 — 17, 27 — 11, 28 — 13, 29 — 11, 30 — 12, 31 — 12, 32 — 11, 33 — 13,
34 — 14, 35 — 7, 36 — 15, 37 — 15, 38 — 12, 39 — 13, 40 — 12, 41 — 12, 42 — 10, 43 — 18, 44 — 12, 45 — 13, 46 — 12, 47 — 13.
Sc. 18, 19 — with the resource P/05: the rows of the units and of the states of `testsub2` are put by the runner bypassing the writer (`@as console store`,
`@as testsub2worker store`); the time `1000000000` (2001) — a past deadline of `ends` and `made.keep` with any clock of the stand;
there are no workers — the units are in the shard `unplaced`. After
P/05 (the resource) — all the scenarios (above, «Observation»).

## Snapshot outside TSV

The publication of a shard: max_bytes=0, less than, equal to and greater than the resource door limit L; the full size exactly L/+1; on a refusal the former
object and time are kept. Scenario 03 does not prove these boundaries. Outside TSV reconcile the whole list of service families and the size of the full
snapshot shard against the resource door limit L (before the write); max_bytes of the store is held by the store itself on put — its `TooLarge`
gives the same outcome. max_bytes=0 does not remove the ceiling of the door; a refusal keeps the former shard and its
time. The `@until` of the snapshot reads the local resource; an error of publication does not become an empty snapshot.

## Checks by reading

The console doors are checked by [the acceptance of P/06.6](../../06-console/acceptance/6/README.md). The controller checks follow. The TSV on an empty pool does not prove the properties below. For each one state the place of the implementation, an observation of
a controlled stand or an abstract model on the operations of P/01.1.

- Two controllers, different units of weight 1, one worker capacity 1: the second decision sees the reserve
  of the first; the total admitted load does not become 2.
- Two units with the same spread_by: the second decision does not take the same server, including
  through another worker of this server.
- Two members of a group with different home, two controllers: one intent contains all of them and the common target.
  Check the stop after active, after each removal/placement and before idle. The next
  holder first finishes the intent; before the addition of the group all its old assignments are removed.
- A late old controller after a change of turn gets 412 on the addition and the removal. On an unknown
  outcome the barrier turn is confirmed first; an old command cannot apply after the re-read.
  On the loss of the barrier itself the changes do not continue.
- The read intent → placement → intent is repeated on a change of version ([the observation contract](../../common/contracts/observation.md)
  «Reading the decision»). Idle is not deleted. A group over the ceiling of intent/assignment is refused wholly before the change of placements.
- With the same history of the versions of the slot, shifts of the writer's clock -30/0/+300 do not change the fate.
  The first look begins 45 s, then the margin up to 90 s; the different histories of judges are not obliged to coincide.
- Grows: an empty pool and capacity.default=4 give per=4; workers capacity=0 and default=4 also
  use 4; no positive capacities and default=0 — withheld «no positive capacity estimate»,
  without an order and a division by zero. The shortage of the weight and of the groups stays visible.

Operations on names: the checks P/04-09, 10, 11 are performed separately from the HTTP steps of the TSV — the reading of
the implementation by the owner or a controlled pool is needed; the last row of the table (the release of the slot by the controller) is on the stand of sc. 21, except
the exact value `until` 0 of the torn row (the writer is entitled to write `0.0`, N0 P/01.1 «Time in a row»; the scenario sees
the time by the form of the writer — `@time`). All the other placement filters pass the candidates, the needed resources are alive,
the capacity is sufficient. Each case has its own initial state, the order of traversal of the map changes.

| Preparation and action | Expected outcome |
|---|---|
| distinct, one place, live w-a/w-b, equal loads 0 and capacities 1; place a unit of weight 1 | The keeper w-a by the slot order of P/03.2 N1.4 |
| Repeat with w-2/w-10; with w-01/w-1; with w-2/w-a; with w-srv-a-10/w-srv-a-2 | The keepers are respectively w-2, w-01, w-2, w-srv-a-10. The last number of a composite name is not extracted |
| The load of w-b is higher than of w-a, both positive; separately shared and an equal free capacity w-2/w-10 | distinct leaves w-b: the load has priority. With shared the equal capacity is resolved by the comparison by the full name, w-10 first |
| The slot is released by the controller: readable; separately until is torn, gen is readable; separately gen is not readable | readable — holder/until/gen/server are kept; torn with a readable gen — released "true", holder "", until 0, gen as read, server — if it is readable, otherwise ""; gen is not readable — the row does not change, the name is not given (N3 «write release») |

An additional check by reading: A under turn v1 sends a deletion by delete_after with CAS U; the request is delayed. B
gets v2 and places the same version U. At A the guard v1 gives 412 and keeps the unit. Check also a conflict of the version
of the unit, an unconfirmed read of intent/placement, the barrier after a non-answer and a repeat without substituting a new guard into the old
plan. Operations in flight are not modelled by the current HTTP-TSV.

An additional check of the class of errors of run 36 (Kimi): by reading check the priority of the branches of the fate: after the early branches
a slot without assigned and running units gets release; an unknown gen keeps the prohibition of writing (on the stand — sc. 21:
a slot without units after `@sigkill` with a live resource — release, not move; an unreadable gen — the row is the same, there is no name). For hung/unsure/wait
the beginning of HUNG_MOVE_AFTER is the first observation of an unchanged version of the slot, not until or fate.since. A new judge starts from zero.
A return home is allowed only in a declared pass with HOME_BUDGET.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models
of the author are not a performed stand test.

[seams.tsv](seams.tsv) adds kit witnesses at controller function seams; [forms/README.md](../forms/README.md) defines their normalization. They do not change the process scenario/step counts above and do not close a witness they do not execute.

21/17 checks zero Time using four existing full @oneof 200 branches (0/0.0/0.00/0.000); all other fields remain. 31/5 binds the damaged row index and 31/10 checks no repair; requests and other neighbors stay. s51-s63 and their real fixture/observation contracts are declared in forms/README; none is a SUT execution claim.

## External qualification

The [external procedures](../qualification/stand-procedures.md) (judge-only: qualification preparation and observations) supplement these process scenarios, seams and reading checks. They test ordinary controller/launcher behaviour using an independently qualified stand; their publication does not execute them or change the scenario/step counts. A missing binding or unactivated intervention leaves the dependent slice NotExecuted.

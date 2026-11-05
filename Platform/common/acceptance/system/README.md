# System acceptance of the module «Platform» — the stand of all processes

This English text is the source; the Russian translation `ru/acceptance/system/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

End-to-end scenarios that check the norms of several micromodules at once and require a stand of all processes of the platform
(the module note `Platform/module-design.md`, for people, not in the export: «сквозные сценарии … со стендом из всех микромодулей»). Moved from the acceptance of М10/11
(sc. 05, 06; stage B, ADR-0083 addendum (1): without a change of behaviour) by the Architect's decision on V2 of the move plan of lesson 6:
a scenario belongs to the lesson whose norm it checks (the presence lock, sc. 16 of М10/11, — the acceptance of
[P/05](../../../05-resource/acceptance/README.md)), the drills of many processes — here. The numbers and steps are the former ones.
Four scenarios / 75 steps: sc. 05 — 61 automatic steps on the three-server cluster stand (the section «Sc. 05»; not executable yet — the section «Executability»), sc. 07 and 08 — 7 steps `@manual`, sc. 09 — 7 steps `@manual`; sc. 06 `recover` is moved by scenario 18 of the [acceptance of P/01.3](../../../01-store/acceptance/3/README.md) to the store group stand (ПРАВИЛА-РАБОТЫ.md § 4, 2026-10-30); sc. 07 — a cold start of a part and a worker (ADR-0091 addendum (2), (3)), sc. 08 — the worker program from the manifest row (ADR-0091 addendum (4)–(6)).

## Stand

Sc. 05 runs on the stand of the runner: [«Three-server cluster stand»](../README.md#three-server-cluster-stand) of the common README,
the manifests `testsub` and `testsub2`, the event mirror is switched on by step 6. Before, it was a drill `@manual` on a real cluster; the plan
of stage 2 is `decisions/inbox/2026-10-30-план-сценарии-группы-автоматом.md` (ПРАВИЛА-РАБОТЫ.md § 4).

Sc. 07 and 08 check a box with systemd, not a group: a real test server with the units of the platform
([P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.1). The operator runs the drills by the drill log, the runner only prints the steps
`@manual` ([the dictionary of directives](../README.md#dictionary-of-directives-and-doors)): they do not enter the result, they are neither green nor
red, they get no PASS from printing. The log of the operator is to name the preconditions of N3 of the norms, the outcomes and the limitations.

## Scenarios

| № | Drill | Norms |
|---|---|---|
| 05 | «pull the power»: the server failure table, the timing profile 45/90 with all tolerances, the return without moving back, except a declared `home` | [P/04](../../../04-controller/spec/04-controller.norms.md) N1.4a `power_pull` (`stays`, `lost`, `store`, `return`), N3 «pull the power (do nothing) — a drill», «fate», «pass()» step 7 (P/04-22); [P/05](../../../05-resource/spec/05-resource.norms.md) N1.4 «Bucket restore» (P/05-12); [P/01.3](../../../01-store/spec/01.3-store.norms.md) N1.3 (a restart by `member.json` without `join`) |
| 06 | moved: sc. 18 of the [acceptance of P/01.3](../../../01-store/acceptance/3/README.md) (the store group stand, 2026-10-30) | [P/01.3](../../../01-store/spec/01.3-store.norms.md) N1.3 `floor`, N3 «recover the store» |
| 07 | a part of a subsystem: after a reboot the share directories exist before the units, the part starts earlier than the workers, both without the subsystem file; the units by the keys; the producer writes into the share under `ProtectSystem=strict`, the consumer connects without `ReadWritePaths`; a stop of the part does not stop the worker | [P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.1 (`units`, `dirs`), N1.2 `W2C_SUB_ENV`, N1.7 `install`, N3 «server start» (ADR-0091 addendum (2), (3)) |
| 08 | the worker program: the unit is the command of the runner, the runner executes `worker.exec` of the row with `W2C_MANIFEST_REV`; a change v1 → v2 through `manifest put` — v2 after a restart; the keys of the units are the installation source, `manifest put` does not change them; for a worker on the domain — by reading | [P/02.3](../../../02-installer/spec/02.3-installer.norms.md) N3 «Process start», «The worker program from the row», «The installation source»; [P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.1, N1.9 (ADR-0091 addendum (4)–(6)) |
| 09 | add a subsystem to a working cluster (ADR-0115 addendum (21)–(24)): a degraded group — a refusal before the first restart; the leader — last (`-last`); a failed return between steps — the round stands; a changed manifest of a working subsystem — `get` replaces the previous file, the round passes on all servers (ADR-0115 addendum (26)); a repeat — «already done» on a passed one; after all — the switch-on; a box — only with `-allow-downtime`; `manifest get` with another hash — a refusal; three voters and a server with a door; the switch without restarts (ADR-0115 addendum (25)) | [P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.7 `add`, N1.9 `rollout`, `manifest get`; [P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N3 «install»; [P/06.5](../../../06-console/spec/06.5-console.norms.md) N2 `/manifest/<sub>/source` |

For `recover` (now sc. 18 of the acceptance of P/01.3) the isolation of the previous group, the saved sources and
a reliable upper are mandatory; the absence of any condition means a refusal before changes, including with `force`. One available copy does not
prove a full restore of the events.

## Sc. 05 — pull the power

The server `srv-b` carries a unit without a home `c1` (`testsub`, the worker `w-2`) and a unit with a home `h1` (`testsub2`, the shelf `s-b1`, the holder
`t-srv-b-1`). The scenario pulls the power, watches the move and the copies, then returns the server. Steps and norms:

| Steps | What is seen | Norm |
|---|---|---|
| 1–5 | a group of three is assembled, the leader is `srv-a` | P/01.3 N1.3 `join` |
| 6–7 | the mirror is switched on, one copy: the neighbour of `srv-b` is the single `srv-c`; the retention of `testsub` is 36500 days, because the bucket of step 33 is dated 2026-01-01 and the pass `retain` could otherwise remove it | P/05 N1.4 `mirror`, N3 `retain`; P/02.4 N1.9 |
| 8–29 | controllers, shelves, workers; `w-2` is the only worker of `testsub` when `c1` is created, so `c1` is on `srv-b`, epoch 1; `h1` — at the holder of its shelf | P/04 N3 «choose», N1.3 `home` |
| 30–32 | a closed bucket `$closed` on the volume of `srv-b`; the pass at the start of the resource copies it to `srv-c` | P/05 N1.4 `pass`, `mirror` |
| 33 | a copy of a bucket which is not on the volume of `srv-b`: only restore will show it | P/05 N1.6, N1.4 «Bucket restore» |
| 34 | an open bucket on the volume of `srv-b`: it has no copy, it is in `lost` until the return | P/04 N1.4a `lost` |
| 35–37 | the power is pulled: minus a vote, the group lives, the resource is `silent` | P/04 N1.4a `store`; the observation contract `resource_state`; chapter 6.5 `ServerRow.resource` |
| 38–40 | `c1` at another worker, epoch 2 | P/04 N1.4a `moves`, N3 «fate»; P/03.2 N1.5 |
| 41 | `h1` at another holder, without waiting for the home | P/04 N3 «pass()» step 6, N1.3 `home` (a preference, not a filter) |
| 42 | `fate: move`, the name `w-2` is given away by the controller | P/04 N3 «fate», N1.2 `names_given` |
| 43–46 | the merge of the console: the closed bucket — from the copy of `srv-c` under the name of the owner, `from mirror`, `fenced`; there is no open one; the answer is incomplete, `srv-b` is `silent`; `srv-a` has no copies | the merge contract «Слияние» steps 2, 7, «Epochs», `from_mirror`; P/04 N1.4a `stays`, `lost`; P/05 N2 `/mirrored` |
| 47–48 | the return: the member is a follower again, without `-join` | P/04 N3 «pull the power» «return»; P/01.3 N1.3 `join` |
| 49–50 | the restore is done, one bucket is pulled, it is on the volume | P/05 N1.4 «Bucket restore», the heartbeat field `restore` |
| 51–53 | the archive is intact: both previous buckets are on the volume, the row of the open one is seen by the merge under the old epoch, the answer is complete | P/04 N1.4a `stays`; the merge contract «Epochs» |
| 54–56 | `w-2` captured its name again, `gen` 2 | P/04 N1.4a `return`; P/03.2 N3 «capture» |
| 57–58 | `t-srv-b-1` holds the shelf again, `h1` goes home | P/04 N3 «pass()» step 7, HOME_BUDGET |
| 59–60 | `c1` has no home — it stays at `$holder` | P/04 N1.4a `moves`; N3 «pull the power» |
| 61 | the resource of `srv-b` is `live` again | the observation contract `resource_state` |

The stand gives a name to each process (`@start worker <name>`), so step 54 checks the return of its own name, while the choice of a free name
by a nameless process is the acceptance of chapter P/03.2. Step 49 waits for `restored: 1`: `srv-c` has two copies, but `$closed` remained on the volume of `srv-b` and is not counted, only the bucket of step 33 is pulled
(the Architect's decision of 2026-10-31).

A declared home allows an automatic return within HOME_BUDGET; without a home the return of a server by itself does not cause
a rebalancing (a check of the error class R37, Codex): steps 58–60.

### Timings

The timings 45/90 s of the norm are the drill profile of a healthy stand with heartbeats observed in advance, an available store and capacity, not
a common deadline (P/04 N1.4a `moves`); the scenario judges only the upper bound. The steps do not assert a lower bound of the move.
`t = 0` is the `ok` of the directive `@power-pull`. The numbers are from the constants of the norms:

| Quantity | Calculation | s |
|---|---|---|
| the judge moves a slot not earlier than | `SLOT_TERM` 45 + `LOST_AFTER` 45 from the first read of the last version (N3 «fate», the margin row) | 90 |
| the judge certainly moves by | the last version is read no later than 5 s (a pass), the pass after the bound — no later than 5 s: 90 + 5 + 5 | 100 |
| the move on a healthy stand by | the leader could be on `srv-b`: + `leader_wait` 5; the margin of the stand + 15 | 120 |
| step 37 (`silent`) | `LOST_AFTER` 45 + poll 5 + the margin of the stand 20; the bound is strict: `age > LOST_AFTER` | 70 |
| step 37 ends not earlier than | the heartbeat of the resource is written every 10 s (P/05 N1.4), the last version is not older than 10 s at `t = 0`: 45 − 10 | 35 |
| steps 38, 41, 42 | the remainder 120 − 35 (they go after step 37) | 85 |
| step 40 | the epoch after the move: `POLL` ~2 s and the writes of the store; the timing as in the acceptances of P/03 | 30 |
| step 58 | the timing of sc. 38 of the acceptance of P/04 (the same way home) | 90 |

The `silent` of the resource (step 37) moves nothing by itself. N3 «leaving» fires on it only with `requires: resource` and a live worker
(the Architect's decision of 2026-10-31). `testsub` does not declare this key, `testsub2` declares it, but the holder `h1` is silent together with the resource.
Therefore both units go by the fate `move`, and steps 38, 41 judge one timing of 120 s. Step 42 waits as long as step 38: `fate: move`
comes out with the pass that takes `c1` away. Later it does not disappear: `move` of a silent resource does not depend on the units, the slot is not given away.

### Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 05/59 | 12 s | absence: `c1` does not go to the returned `w-2` — the controller sees its heartbeat on the next pass, the move would happen a pass later: two passes of 5 s and a margin, as for the sleeps of the acceptance of P/04 |

### Executability

Sc. 05 is **not executable yet**: the runner has the directives and doors of the section (the target `system/05-power-pull`, by name only), but there was no dry run by an implementation. The rule of the plan
«Сухой прогон до выпуска»: a scenario goes into a runner release only after a run against an implementation, each red step is analysed
by the question «norm or data» before the release. New scenarios enter the pin of the lines only by a runner release. The store build `box`
does not execute the scenario (the common README).

## scenarios.tsv

The format is the [dictionary of directives and doors of «Стенда» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). Sc. 05 — the directives
and doors of the section «Three-server cluster stand» and of the dictionary; sc. 07, 08 — only `@manual`, the expectation — `manual`.

## Scenario boundaries

Sc. 05 — the boundary of the common README: each run gets new directories and ports of all three servers. The drills 07, 08 are executed on a real box and have no runner boundaries: each one — on its own test box, the original directories are saved before the start.

## `journal/corrections-system.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М10/11 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (review analysis of stage B 6–7, № 18).

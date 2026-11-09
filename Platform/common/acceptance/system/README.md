# System acceptance of the module «Platform» — the stand of all processes

This English text is the source; the Russian translation `ru/acceptance/system/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

End-to-end scenarios that check the norms of several micromodules at once and require a stand of all processes of the platform
(the module note `Platform/module-design.md`, for people, not in the export: «end-to-end scenarios … with a stand of all micro-modules»). Moved from the acceptance of M10/11
(sc. 05, 06; stage B, ADR-0083 addendum (1): without a change of behaviour) by the Architect's decision on V2 of the move plan of lesson 6:
a scenario belongs to the lesson whose norm it checks (the presence lock, sc. 16 of M10/11, — the acceptance of
[P/05](../../../05-resource/acceptance/README.md)), the drills of many processes — here. The numbers and steps are the former ones.
Four scenarios / 75 steps: sc. 05 — 61 automatic steps on the three-server cluster stand (the section «Sc. 05»; not executable yet — the section «Executability»), sc. 07 and 08 — 7 steps `@manual`, sc. 09 — 7 steps `@manual`; sc. 06 `recover` is moved by scenario 18 of the [acceptance of P/01.3](../../../01-store/acceptance/3/README.md) to the store group stand (work rules (for people) § 4, 2026-10-30); sc. 07 — a cold start of a part and a worker (ADR-0091 addendum (2), (3)), sc. 08 — the worker program from the manifest row (ADR-0091 addendum (4)–(6)).

## Stand

Sc. 05 runs on the stand of the runner: [«Three-server cluster stand»](../README.md#three-server-cluster-stand) of the common README,
the manifests `testsub` and `testsub2`, the event mirror is switched on by step 6. Before, it was a drill `@manual` on a real cluster; the plan
of stage 2 is `automatic group scenarios plan (2026-10-30, for people)` (work rules (for people) § 4).

Sc. 07 and 08 check a box with systemd, not a group: a real test server with the units of the platform
([P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.1). The operator runs the drills by the drill log, the runner only prints the steps
`@manual` ([the dictionary of directives](../README.md#dictionary-of-directives-and-doors)): they do not enter the result, they are neither green nor
red, they get no PASS from printing. The log of the operator is to name the preconditions of N3 of the norms, the outcomes and the limitations.

## Scenarios

For `recover` (now sc. 18 of the acceptance of P/01.3) the isolation of the previous group, the saved sources and
a reliable upper are mandatory; the absence of any condition means a refusal before changes, including with `force`. One available copy does not
prove a full restore of the events.

## Sc. 05 — pull the power

Sc. 05 pulls the power of one server, watches the move and the copies, then returns the server. The governing norms are P/01.3 N1.3 `join`, P/03.2 N1.5 and N3 «capture», P/04 N1.3 `home`, N1.4a and N3, P/05 N1.4 and N1.6, the observation contract `resource_state` and the merge contract.

The stand gives a name to each process (`@start worker <name>`); the choice of a free name by a nameless process is the acceptance of chapter P/03.2.

A declared home allows an automatic return within HOME_BUDGET; without a home the return of a server by itself does not cause
a rebalancing (a check of the error class R37, Codex).

### Timings

The timings 45/90 s of the norm are the drill profile of a healthy stand with heartbeats observed in advance, an available store and capacity, not
a common deadline (P/04 N1.4a `moves`); the scenario judges only the upper bound. The steps do not assert a lower bound of the move.
`t = 0` is the `ok` of the directive `@power-pull`.

The `silent` of the resource moves nothing by itself. N3 «leaving» fires on it only with `requires: resource` and a live worker
(the Architect's decision of 2026-10-31). `move` of a silent resource does not depend on the units, the slot is not given away.

### Executability

Sc. 05 is **not executable yet**: the runner has the directives and doors of the section (the target `system/05-power-pull`, by name only), but there was no dry run by an implementation. The rule of the plan
«Dry run before release»: a scenario goes into a runner release only after a run against an implementation, each red step is analysed
by the question «norm or data» before the release. New scenarios enter the pin of the lines only by a runner release. The store build `box`
does not execute the scenario (the common README).

## scenarios.tsv

The format is the [dictionary of directives and doors of «Stand» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). Sc. 05 — the directives
and doors of the section «Three-server cluster stand» and of the dictionary; sc. 07, 08 — only `@manual`, the expectation — `manual`.

## Scenario boundaries

Sc. 05 — the boundary of the common README: each run gets new directories and ports of all three servers. The drills 07, 08 are executed on a real box and have no runner boundaries: each one — on its own test box, the original directories are saved before the start.


# System acceptance of the module «Platform» — the stand of all processes

This English text is the source; the Russian translation `ru/acceptance/system/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

End-to-end scenarios that check the norms of several micromodules at once and require a stand of all processes of the platform
(the module note `Platform/module-design.md`; judge-only: for people, not in the export: «end-to-end scenarios … with a stand of all micro-modules»).
A scenario belongs to the lesson whose norm it checks (the presence lock — the acceptance of
[P/05](../../../05-resource/acceptance/README.md); judge-only: the acceptance of a later lesson), the drills of many processes — here.
Four scenarios / 75 steps: sc. 05 — 61 automatic steps on the three-server cluster stand (the section «Sc. 05»; not executable yet — the section «Executability»), sc. 07 and 08 — 7 steps `@manual`, sc. 09 — 7 steps `@manual`; sc. 06 `recover` is checked by scenario 18 of the [acceptance of P/01.3](../../../01-store/acceptance/3/README.md) on the store group stand; sc. 07 — a cold start of a part and a worker, sc. 08 — the worker program from the manifest row.

## Stand

Sc. 05 runs on the stand of the runner: [«Three-server cluster stand»](#three-server-cluster-stand) below,
the manifests `testsub` and `testsub2`, the event mirror is switched on by step 6.

Sc. 07 and 08 check a box with systemd, not a group: a real test server with the units of the platform
([P/02.4](../../../02-installer/spec/02.4-installer.norms.md) N1.1). The operator runs the drills by the drill log, the runner only prints the steps
`@manual` ([the dictionary of directives](../README.md#dictionary-of-directives-and-doors)): their result is the word `manual`, they are neither green nor
red, they get no PASS from printing. The log of the operator is to name the preconditions of N3 of the norms, the outcomes and the limitations.

## Three-server cluster stand

Three platform servers on one machine of the stand — sc. 05 of this system acceptance. A server failure, the move of units and
the return the stand sees from outside, so a drill on a real cluster no longer replaces them. The norms are P/04 N1.4a, N3 «pull the power», P/05 N1.4, P/01.3 N1.3, P/02.4 N3
«server start»; the section introduces no new norms. The section continues «Store group stand» ([P/01.3](../../../01-store/acceptance/3/README.md#store-group-stand)) and the form `on <server>` of the dictionary.

- **Servers** — `srv-a`, `srv-b`, `srv-c`. Each has its own `SERVER_NAME`, `BOX_ID` and `PLATFORM_DIR` — as for `on <server>`
  of the dictionary (`{data}` for `srv-a`, `{data}/servers/<server>` for the others); this directory is the volume of the server: its objects, event root and
  presence locks. Each has its own resource with its own `{rport}`. The key ring is one (`SECRETS_KEY`).
- **Store** — a group of three voters per «Store group stand»; the `<id>` of a member is the name of the server. Kits — the description
  [`system/inputs/cluster.json`](inputs/cluster.json) (`@group-setup`; judge-only: the kit description); the `-dir` of a member is `<PLATFORM_DIR>/configstore`,
  `-sockets` — `<PLATFORM_DIR>/run`; the runner derives the file `{rights}` from the stand manifests with the rights derivation command. Each process
  talks to the member of its own server: `{socket}` and `PLATFORM_STORE` are the sockets of this member. Therefore a switched-off server takes away one
  vote, not the store of the neighbours.
- **Controllers and console** — one controller per manifest and one console, all on `srv-a`; the doors `console`, `console2`.
  The scenario does not switch off `srv-a`: a new controller judges no one for the first `LOST_AFTER` (P/04 N1.4a `fresh_controller`), and
  the drill checks a controller with heartbeats observed in advance.
- **Workers** — `@start worker … on <server>` of the dictionary, so that the scenario itself names the names and the order of the launch.
- **Store build — the profile feature `keys.store_build`** of the profile `01-store`, as for the group stand: `raft` — the scenario
  is executed; `box` — not_applicable, it does not enter the result and is not red, because such a build has no group; there is no feature or
  another value — not_executed, not GREEN. The scenario begins with `@group-setup`, the runner plans it by the same rule.
- **What is needed from the profiles.** There are no new commands and keys. The former commands of «Stand» (`store`, `manifest-put`, the rights derivation, `resource`,
  `worker`, `controller`, `console`) do not write in the port, the directory, the socket and the server name themselves: the runner substitutes `{data}`, `{socket}`,
  `{rport}`, `{server}` and the environment for each server. A needed part is absent from the composition — a composition error before the start.
- **Boundaries**: between scenarios the runner stops all processes of all servers, removes the proxies and deletes the directories.

| Form | Meaning | Lesson |
|---|---|---|
| `@server-start <name>` | bring up a server: the store member, then the resource. The flags of the member — as for `@store-start`, the runner chooses the join by the order of the directives in the scenario (the first directive names the console server `srv-a`; a fourth directive is a data error): the first — `-bootstrap -group-size 3`, the second — `-join {api@<first>} -group-size 3 -force`, the third — `-join {api@<first>} -group-size 3` (assembly 1→2→3). On the first server, after the member is ready, the runner sets up the manifests (`manifest-put`, the order — «Manifests» of the [stand](../stand.md#layout-by-processes-stage-c)) through its `admin.sock` and starts the console, then the resource. The role files of the resource — as for `@start resource on <server>`. The expectation `ok` — `admin@<name> GET /v1/status` answers 200 no later than 20 s, then the role sockets of the member accept a connection no later than 30 s, then the resource port listens and the row `platform/doors/<name>` exists no later than 20 s | system |
| `@power-pull <name>` | pull the power: the proxy of the runner on the raft address of the member breaks the live connections and does not accept new ones (like `@cut store@<id>`), then the runner immediately sends SIGKILL to all processes of the server — the member, the resource, the workers; it does not touch the directories. There is no proxy on the resource door, because the resource names the address of its door itself: after SIGKILL its port is closed. The expectation `ok` — all processes exited; this moment is `t = 0` of the drill. `<name>` — a server that is up, not the server of the console and the controllers; otherwise a data error when the step is executed | system |
| `@power-back <name>` | return the power: the same directories, ports, kit. The proxy lets through again; the member is started with the previous command and the previous flags without `-bootstrap`, `-join`, `-force`: it takes its partners from `member.json` (P/01.3 N1.3 `join`; P/02.4 N3 «server start» step 1), and only so the steps below prove a restart without a join. Then the resource — with the same command, with the same `{rport}`. The directive does not start workers; they are returned by the steps `@start worker … on <name>`. The expectation — as for `@server-start` | system |
| `@restart resource#<name>` | SIGTERM to the resource of the server, wait for the exit, start it with the same command with the same `{rport}` and directory; the expectation `ok` — the port listens and the door row exists no later than 20 s. The first pass goes at the start (P/05 N1.4 `pass`), so the scenario gets a mirror pass without waiting 600 s | system |
| `@append event on <name> <tree>/<unit>/e<epoch> <text>` | like `@append event` of the dictionary, but into the event root of the server `<name>` (`<PLATFORM_DIR>/events`) | system |
| `@append event-closed on <name> <tree>/<unit>/e<epoch> <text>` | like the row above, but into the bucket of the previous window: `start = floor(now / 600) × 600 − 600`; such a bucket is already closed (the event journal contract `span`: closed when end ≤ now). `{now}` in the text is `start + 300`, because the `t` of the line chooses the bucket. After `ok` the runner binds `$closed` — the path of the bucket `<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`. The real closing cannot be waited for: up to 600 s per window and up to 600 s more for the mirror pass | system |
| door `resource#<name> <request>` | the door of the resource of the server `<name>` on its `{rport}` with an admissible identity; `#` here is the name of the server, not the number of a copy as in `@sigkill resource#1` | system |
| door `admin@<name> <request>` | the door of a member per «Store group stand»; sc. 05 reads and writes through it, because it needs the rows of all families | P/01.3 |

## Scenarios

For `recover` (sc. 18 of the acceptance of P/01.3) the isolation of the previous group, the saved sources and
a reliable upper are mandatory; the absence of any condition means a refusal before changes, including with `force`. One available copy does not
prove a full restore of the events.

## Sc. 05 — pull the power

Sc. 05 pulls the power of one server, watches the move and the copies, then returns the server. The governing norms are P/01.3 N1.3 `join`, P/03.2 N1.5 and N3 «capture», P/04 N1.3 `home`, N1.4a and N3, P/05 N1.4 and N1.6, the observation contract `resource_state` and the merge contract.

The stand gives a name to each process (`@start worker <name>`); the choice of a free name by a nameless process is the acceptance of chapter P/03.2.

A declared home allows an automatic return within HOME_BUDGET; without a home the return of a server by itself does not cause
a rebalancing.

### Timings

The timings 45/90 s of the norm are the drill profile of a healthy stand with heartbeats observed in advance, an available store and capacity, not
a common deadline (P/04 N1.4a `moves`); the scenario judges only the upper bound. The steps do not assert a lower bound of the move.
`t = 0` is the `ok` of the directive `@power-pull`.

The `silent` of the resource moves nothing by itself. N3 «leaving» fires on it only with `requires: resource` and a live worker. `move` of a silent resource does not depend on the units, the slot is not given away.

### Executability

Sc. 05 is **not executable yet**: the runner has the directives and doors of the section (the target `system/05-power-pull`, by name only), but there was no dry run by an implementation. The rule
«Dry run before release»: a scenario goes into a runner release only after a run against an implementation, each red step is analysed
by the question «norm or data» before the release. New scenarios enter the pin of the lines only by a runner release. The store build `box`
does not execute the scenario (the section «Three-server cluster stand»).

## scenarios.tsv

The format is the [dictionary of directives and doors of «Stand» of the common acceptance README](../README.md#dictionary-of-directives-and-doors). Sc. 05 — the directives
and doors of the section «Three-server cluster stand» and of the dictionary; sc. 07, 08 — only `@manual`, the expectation — `manual`.

## Scenario boundaries

Sc. 05 — the boundary of the section «Three-server cluster stand»: each run gets new directories and ports of all three servers. The drills 07, 08 are executed on a real box and have no runner boundaries: each one — on its own test box, the original directories are saved before the start.


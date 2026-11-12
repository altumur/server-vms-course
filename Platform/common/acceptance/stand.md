# Stand: assembly, processes and environment

A topic of the [common acceptance README](README.md): the directives and doors are its [dictionary](README.md#dictionary-of-directives-and-doors).

## Assembly example

The following `assembly.yaml` is a schematic complete Platform composition, not delivered profiles or implementation code. The `example/…/acceptance.yaml` values are placeholder paths relative to the assembly; replace them with the actual profile locations. `modules` is a mapping from the canonical module identities (the lesson-directory names) to profile-file paths, not a list of module records.

```yaml
format: 1
modules:
  01-store: example/01-store/acceptance.yaml
  02-installer: example/02-installer/acceptance.yaml
  03-worker: example/03-worker/acceptance.yaml
  04-controller: example/04-controller/acceptance.yaml
  05-resource: example/05-resource/acceptance.yaml
  06-console: example/06-console/acceptance.yaml
  07-console-module: example/07-console-module/acceptance.yaml
  08-domain: example/08-domain/acceptance.yaml
  09-agent: example/09-agent/acceptance.yaml
  10-domain-console: example/10-domain-console/acceptance.yaml
```

The assembly uses `format: 1`; each selected `acceptance.yaml` uses profile `format: 2`. The [assembly form](PROFILE.md#assembly-and-input-identity) has only `format` and `modules`, with no root build, commands, keys or inherited defaults. A partial map is permitted for preparation, but a target missing a required module is blocked before execution. These paths declare no supplied backend, provider or successful run.

## Layout by processes (stage C)

An implementation uses one micromodule per process. The full generic forms of `acceptance.yaml` (profile version 2),
`assembly.yaml` (composition version 1), substitutions, executable adapters and the vector envelope are defined once in
[Acceptance profiles and assembly](PROFILE.md). The following sections assign the stand interfaces used by the lessons.
A profile describes those interfaces; it does not change their scenarios or expectations.

- **A profile per micromodule.** `acceptance.yaml` lies in the directory of the module; `module` is the lesson directory from
  [`Platform/lessons.tsv`](../../lessons.tsv) (`01-store` … `10-domain-console`); the profile has its own build (`build`),
  its own optional regressions (`unit`), its own commands and stand addresses (`stand`), keys (`keys`), adapters (`adapters`) and
  public build results (`artifacts`). A profile names only its own commands — a command of a neighbouring process is not in it.
  The command templates below («Launch command», «Manifest install command», the commands of vectors and directives) are `stand`
  keys of the profile of the owner process.
- **Composition of the stand.** The root `assembly.yaml` (`format: 1`, `modules`) is only the map «module → profile file», without
  root commands and a common build. The stand takes the neighbours from this composition; replacing a part (`--part`) carries its
  profile whole — directory, keys, commands. A needed part is absent from the composition — a composition error before the start,
  not a substitution by a neighbour.
- **Working directories and phases.** Each command is executed from the directory of its profile. The build is a separate phase
  before the inputs are fixed; there is no rebuild during acceptance. The stand records the profiles, sources and artifacts of the
  parts in the run passport. Coinciding algorithm names of different consumers (`said-id`, `fresh-age`) are commands of each
  consumer, not one common one.
- **The stand vocabulary is unchanged.** The substitutions (`{data}`, `{socket}`, `{rights}`, `{port}`, `{rport}`, `{manifest}`,
  `{manifests}`, `{name}`, `{agent_tokens}` and the others below), the environment of the processes (`PLATFORM_DIR`, role sockets,
  the ring, `MANIFEST_DIR`, the common directory of the local token doors) and the directives are set by the stand per this README
  and the lifecycle of the lessons. The profile fields do not become environment variables of processes, HTTP doors or any other
  means of communication between modules.
- **Libraries.** P/03 — its own worker SDK and the test worker of profile 03 (the command `worker`); P/07 — the packaging of the
  published `console.*` by the build of profile 07, without its own process and its own TSV acceptance: the builds 06 and 10 take
  these bytes before the inputs are fixed, the console process does not read the export directory while it works (lifecycle P/06);
  the relay P/09.2 — a mode of the agent of the same module 09 (`RELAY=1`), not a separate profile.
- **Vectors.** The command of a vector package is an executable wrapper of its function of the owner process per the package README;
  the input and output forms are set by the package README (`creates-key` and `near-of` have a raw id in stdout, their README
  «Stand command»). An `expect` that the package README compares by a subset of the output fields reads `{}` as the string
  `<code> <JSON>` of the [dictionary](README.md#dictionary-of-directives-and-doors) does: `{}` at any level is exactly an empty object; any object is `@any`; no field is
  `@absent`; for the packages that compare the output whole, `{}` is exactly empty anyway.
  A package without a separate command contract (the section «Stand command» of the package README or a command line below): the
  computed outcome of the function is native code 0 and one JSON value; the refusal markers `@refuse`, `@bad`, `@skip` are JSON
  strings of the same spelling; a positive value that is not JSON (the hex of a key, a name, a word) is a JSON string; a published
  `@exit 2` is native code 2, the output is not judged. Explicit `stand` commands and raw ids (`creates-key`, `near-of`) — without
  changes (the line «Native outcome» in the READMEs of the packages
  with markers).
  A table whose package README names no native form: one expectation column (`expect` or another name) — the value of this column
  by the rule above; two or more — native code 0 and a JSON object, the keys are the names of the expectation columns of the table,
  the values are per column, as in the TSV (`@absent` — there is no key); which columns are the expectation is named by the package
  README.
- **The unified vector command.** The optional profile map `vectors` and its complete input/output wire are defined in
  [Acceptance profiles and assembly](PROFILE.md#unified-vector-command). A package README assigns its consumer, tables,
  input columns, fixtures and directions; the implementation computes its own native result. A missing assigned entry is
  `blocked`, not PASS. Coverage uses the full export SHA and table SHA; a source line is an address only within that pin.

- **Launch command** — a template with substitutions: `{data}` — a new empty data directory of the instance; `{socket}` — the
  socket path of the store door (P/01.1); `{port}` — the HTTP port of the console on the loopback (lesson P/06 and the acceptances with the console stand); `{manifest}` — the directory
  of the stand manifests for the processes that need it (`MANIFEST_DIR`, P/02.3); the store command does not receive it and puts no manifests; `{body_limit}` and `{row_ceiling}` — the body limit and the row ceiling (N5 P/01.1);
  `{rights}` — the path of the rights file which the runner puts before the store starts (P/01.2 N1.2); the column `rights` of the routing row of the target names it (judge-only: the routing of the judge, [`forms/targets.routing.tsv`](forms/targets.routing.tsv)): in P/01.1 — the file of «Role sockets» below, in the chapters P/01.2 and P/01.3 — the ready input [`01-store/acceptance/2/inputs/rights.json`](../../01-store/acceptance/2/inputs/rights.json) (judge-only: an input of the stand), in the acceptances whose stand sets up the stand manifests — the rights derived from the stand manifests by the rights derivation command below (`{manifests}` — the directory of the stand
  manifests, `{deployment}` = `dep`); the store command receives `{rights}`, not `{manifest}`. The implementation names which substitutions each of its processes needs.
- **Manifest install command** `manifest-put` (P/02.3 N3 «Manifest change») — a template with `{socket}` and `{file}`: puts one manifest
  through the `admin.sock` of the store (`{socket}`); code 0 — put, another — a refusal. With it the runner sets up the stand manifests one by one
  in the order of «Manifests» below, after the store is ready and before the first `@start`.
- **Rights derivation command** (P/02.5 N2) — a template with `{manifests}` (the directory of the manifests), `{deployment}` and `{file}`: writes the rights file per
  P/02.5 N1.4; code 0 — the file is written, another — a generation refusal. The implementation names it in its description (P/02.5
  «Implementation decides» item 1). The acceptance variants of P/02.5 (`5/variants/`) call it with `{deployment}` = `dep`.
- **Ring command** — the template `ring {file}`: creates a key ring per the [sealing contract](../contracts/sealing.md) (`w2cctl secrets new` of the implementation, P/02.4 N1.9) in the file
  `{file}`; the runner calls it before the first process with `{file}` = `{data}/etc/secrets/platform.key`; code 0 — the ring is created. The owner and the mode of the ring file on the stand — the section «Stand without root» below.
- **Command to load one manifest file** (P/02.1) — a template with `{file}`; exit code 0 — a manifest, another — a refusal, the text
  of the refusal names the file (the norms of P/02.1, «Implementation decides» item 3).
- **Processes of several roles** (lesson P/03 and later): the implementation names the launch command of each role — the store,
  the console, the controller, the worker, later the resource; the worker command receives the name by the substitution `{name}` (an argument), the environment —
  `BOX_ID` and `SERVER_NAME` with the values of the form [`forms/stand-environment.tsv`](forms/stand-environment.tsv) (P/02.4 N1.2); from the environment the worker takes its name only by `slot.name_env` of its manifest
  (P/02.1 N1.2a), and the runner sets this variable if the manifest declared it (`testsub2` — `TALLY_NAME`; `testsub` has none). Where the acceptance README of a lesson reads the store by a role with full rights on the prefix of the subsystem (P/06.1), the runner reads the store with such a role.
- **Resource** ([P/05](../../05-resource/spec/05-resource.norms.md)): the launch command of the server resource with the substitution `{rport}` — the port of its door; the runner waits for the port
  and the row `platform/doors/<host>` before the first step. For a scenario that needs the heartbeats of other servers, the resource is on the server
  of the controller: the process reads the cluster objects through the resource of its own server (P/04 N3 «pass()» step 0).
- **Role sockets** (P/01.2, P/01.3 N1.3 `sockets`): on a box too the store opens a socket per role (`<role>.sock`, `admin.sock`) per the rights
  file; the runner calls through the socket of the role of the scenario. `{socket}` is the path of `admin.sock`; the role sockets lie next to it, in the same directory, flat (P/01.3 N1.3 `sockets`).
  `{socket}` is a door with full rights (preparation). Lesson 1 runs the scenarios with the role `acc` — read and write rights only on
  `acc/*`, the socket `acc.sock` next to `{socket}`. The runner supplies `{rights}` in the form of P/01.2 N1.2:
  the role `acc` with the group `acc` and the patterns `acc/*` for `read`, `write` and `delete`.
  Deletion is a separate action (P/01.2 N1.3 `allowed`); in the file it is named explicitly.
  The store is ready when `admin.sock` and the socket `<role>.sock` of every role of its rights file accept a connection, within the term of «Terms of the stand» (15 s from the start by default; `@store-start` and `@server-start` are exceptions, their rows name their own terms); without a rights file only `admin.sock` is awaited. An instance that exits earlier or is not ready by then is a failed start; a rights file that cannot be read or has no object `roles` is a failure of the stand.
  The stand of P/01.2 is the store with its ready rights input above: it has no installer and no manifest is laid.
- **One data directory** `{data}` per instance — it is `PLATFORM_DIR` (P/02.4 N1.2 «The setting channel and the layout»). The stand translates the substitutions into the environment of P/02.4 N1.2 by the column `value` of the form
  [`forms/stand-environment.tsv`](forms/stand-environment.tsv); the ring of `SECRETS_KEY` is per the layout of P/02.4 N1.1, created by the runner with the ring command before the first process; the worker name — by the argument `{name}`. The layout is per P/02.4 N1.2: the store
  `{data}/configstore`, the objects `{data}/objects`, the events `{data}/events`, the presence locks `{data}/events/.workers`.
  In a composite stand, where the store runs together with other parts, the launch command of the store receives `-dir {data}/configstore`: `{data}` itself also holds the ring and the settings, so it is not the store directory. Before the first start of a store the stand creates the empty directory `{data}/configstore` with mode `0700`, as the installer does on a box ([P/02.4 N1.1](../../02-installer/spec/02.4-installer.norms.md#n11-processes-and-units)), on the stand of one store, on the [store group stand](../../01-store/acceptance/3/README.md#store-group-stand) for every member and on the stand of three servers; the daemon does not create an absent `-dir`.
  The event root of a server is derived unambiguously — `{data}/events` of its `PLATFORM_DIR` (the stand does not set `RESOURCE_ROOT` and
  `EVENTS`), so «Stand» has no separate key for the event root.
  The server settings file is `W2C_ENV` of the form (P/02.4 N1.2: the directory `roles/` is next to `w2c.env`,
  there is no other place), the role files are `{data}/etc/w2c/roles/<role>.env`; for a server `on <server>` — the same paths in its
  `PLATFORM_DIR` `{data}/servers/<server>`.
- **Manifests** are the files of [`Platform/common/data/testsub/`](../data/testsub/README.md) (judge-only: the stand manifests); the stand sets them up by the command `manifest-put` in this order: `testsub`, then `testsub2` (it references `testsub`: `about`,
  `near`, `worker.requests`; the manifests reference each other, so their files do not give the order); loading the directory (P/02.1 N3) sees both.
  The manifest `testsub2` declares `console.shell` and `console.files`: the installation reads these files next to the manifest file (P/02.3 N3
  «Manifest change»), so the stand puts next to the copy of the manifest the whole content of the directory
  [`06-console/acceptance/5/inputs/testsub2/`](../../06-console/acceptance/5/inputs/testsub2), under the same paths — on every stand where
  `testsub2` is set up, not only in acceptance 6.5.
- **Console root** (`CONSOLE_ROOT`) is named by the lesson README: chapter 6.2 — `testsub2` (the short paths `/tallies`),
  the others — `testsub`, the second subsystem is mounted under `/testsub2`.
- **Platform vector commands** `order`, `shrink-victim`, `shrink-allowed`, `workers-script` — templates with
  `{input}` — the path of the input file; the output — JSON in stdout; code 0 — computed, 2 — the input is not in form. The packages are
  `Platform/04-controller/vectors/order/`, `…/shrink-victim/`, `…/shrink-allowed/` (P/04 N3 «shortage(), order()», «shrink()»),
  `Platform/02-installer/vectors/workers-script/` (P/02.4 N1.5): the runner reads the `cases.tsv` of the package (judge-only: the cases of the package; UTF-8, TAB, lines
  with `#` and empty ones are skipped, the first one not skipped is the header), for each row writes the cell `input` byte for byte into a
  temporary file, calls the command of the package with `{input}` and compares stdout with the cell `expect` as JSON by value,
  whole (the order of the object keys does not matter; an array — by length, order and elements); code ≠ 0 or not JSON — FAIL of the
  row; a cell `expect` of the form `@exit <code>` judges only the exit code of the command, a bare `exit N` is a data error; the result of the package — the rows by `case`. The implementation names the templates in its description, like the other commands of «Stand».
  The commands `exec` and `install-order` of the profile `02-installer` and `door-token-verify` of the profile `03-worker` answer with the envelope
  `{"result": …}` — the protocol: `exec` — the README of its package `Platform/02-installer/vectors/exec/`, `install-order` — [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N5, `door-token-verify` — [the door token contract](../contracts/door-token.md) (the packages `…/install-order/`,
  `Platform/common/vectors/door-token/`).
  The commands `group-of` (the profiles `03-worker`, `04-controller`: an address → `{group, fault}`) and `fresh-age` (the profiles `04-controller`,
  `06-console`: an age → `true`/`false`) — without an envelope, per the READMEs of their packages `Platform/common/vectors/group-of/`,
  `…/fresh-age/`.
  The commands `rid` and `request-digest` of the profile `06-console` — without an envelope: `{"status": …}` and `{"canonical", "sha256"}`; the input —
  in the READMEs of the packages `Platform/06-console/vectors/rid/`, `…/request-digest/`.
  The command `password-hash` of the profiles `08-domain` and `06-console` — a password hash and its check, without an envelope; the package
  `Platform/common/vectors/password-hash/`.
  The command `env-line` of the profile `02-installer` — a line of an environment file → a pair, `skip` or `bad`, without an envelope; the package
  `Platform/common/vectors/env-file/`.
  The commands `said-id` and `said-read` of the profiles `03-worker` and `06-console` — without an envelope: stdout — a SaidID as a JSON string or
  `true`/`false`, code 0 — computed, 2 — the input is not in form; the input — in the README of the package `Platform/common/vectors/said-id/`.
  The commands `fault`, `values-by-type` and `door-token-issue` of the profile `06-console` — without an envelope: the map of the refusal dictionary,
  the closed `{status, …}` records and reads, `{claims_jcs, token}`; the input — in the READMEs of the packages `Platform/common/vectors/fault/`,
  `…/values-by-type/`, `…/door-token/`.
  The command `covers` of the profiles `06-console` and `10-domain-console` — whether a grant covers a unit, without an envelope: stdout
  `true`/`false`, code 2 — the input is not in form; the input — in the README of the package `Platform/common/vectors/may/` «covers». This is the former wire: the table `covers.tsv` (judge-only: the cases of the package) is also executed
  by the `vectors` entry `common/may` of the profile (the unified command of a package above); with it `stand.covers` is not required, `blocked` — only without
  both; likewise the former commands `fault`, `values-by-type`, `door-token-issue` when there is a `vectors` entry for their package.
- **Instance** — per scenario (P/01.1) or per full run, as the lesson README says; the runner waits for the socket or the port,
  then checks the parameters by behaviour per N5 P/01.1. A ready door instead of a launch — the run is not isolated and not green.
  A run of named scenarios only (the gate `accept:<chapter>:<scenarios>` of a stage) keeps the isolation per scenario and
  does not carry the chapter-wide probes of the parameters and of raw HTTP: its result names the subset, and a target is green
  only by its full run.
- **README checks beyond the TSV** in each lesson are a scenario or an item «checked by reading» with a subject: controlled
  clocks, two consoles on one store and drills on a real box with systemd (`@manual`, [system acceptance](system/README.md)) are not given by this interface;
  a store group of several daemons is given by [«Store group stand»](../../01-store/acceptance/3/README.md#store-group-stand) (P/01.3 N5), a server failure — by [«Three-server cluster stand»](system/README.md#three-server-cluster-stand).

## Environment of stand processes

A stand process receives only the variables of the form [`forms/stand-environment.tsv`](forms/stand-environment.tsv) and the names below; other variables of the environment of the runner are not inherited. A listed name is admitted, not required. The form names each variable, the processes that admit it, its value on the stand of one server (or that the form sets none) and its norms; the words of a directive give their own value instead.

| Applies | Variables besides the form |
|---|---|
| Stands of processes and chapters | the variable named by `slot.name_env` of a stand manifest |
| One launch | the assignments `<NAME>=<value>` of that `@start worker`; `W2C_TOKEN` for the person's command of `@move` |

## Stand without root

The stand is started by an unprivileged user; the product is strict, the stand is not:

- **platform groups** (`w2c-events`, `w2c-secrets`, `w2c-store` and the others of P/02.4 N1.1) on the stand are the current (primary) group of the process,
  one for all roles, on any OS and whether such a group exists on the machine or not (the event trees — the event journal contract
  `modes`); the product requires system groups without a fallback;
- **roots** `{data}/config` — 2770, `{data}/objects` — 2770, `{data}/events` — 2771 (the modes of P/02.4 N1.1 `dirs`; there are no other
  roots; the directories inside `objects` are 0775 per P/05 `disk`, they are not roots) are created by the role launch command of the profile before the start of the
  process, if they are absent, — with these modes, with the current uid/gid (the group on the stand is the current one); it does not change the existing permissions and owners; the role
  process does not create roots (P/02.4 N1.1 `dirs`); `PLATFORM_DIR` is an absolute path;
- **key ring** — the ring command above creates a new file (the bytes — per the sealing contract) with the owner — the current
  uid/gid — and the mode 0640; it does not replace an existing file — a nonzero code; the owner `root:w2c-secrets` of the product (P/02.4 N1.9)
  is not checked by the stand;
- **the entry point of a process on the stand** is a profile command (for example, `controller-stand <sub>`): the process connects to the store
  with its own role (`PLATFORM_STORE` of the role), not `admin`.

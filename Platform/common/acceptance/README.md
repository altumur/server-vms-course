# The acceptance stand of the module «Platform», M10 and M11

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

## Stand — common to the acceptance of the lessons of the module «Platform», M10 and M11

The acceptance runner of any lesson of M10 starts an implementation only through the interface that the implementation names
in its description (the norms of P/01.1, «Implementation decides» item 10); the runner does not know its internal API.

### Assembly example

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

### Layout by processes (stage C)

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
  `<code> <JSON>` of the dictionary below does: `{}` at any level is exactly an empty object; any object is `@any`; no field is
  `@absent`; for the packages that compare the output whole, `{}` is exactly empty anyway (ACC-EMPTY-OBJECT-02, the Architect's
  decision of 2026-10-26).
  A package without a separate command contract (the section «Stand command» of the package README or a command line below): the
  computed outcome of the function is native code 0 and one JSON value; the refusal markers `@refuse`, `@bad`, `@skip` are JSON
  strings of the same spelling; a positive value that is not JSON (the hex of a key, a name, a word) is a JSON string; a published
  `@exit 2` is native code 2, the output is not judged. Explicit `stand` commands and raw ids (`creates-key`, `near-of`) — without
  changes (ACC-VECTORS-CONNECT-04, the Architect's decision of 2026-10-26; the line «Native outcome» in the READMEs of the packages
  with markers).
  A table whose package README names no native form: one expectation column (`expect` or another name) — the value of this column
  by the rule above; two or more — native code 0 and a JSON object, the keys are the names of the expectation columns of the table,
  the values are per column, as in the TSV (`@absent` — there is no key); which columns are the expectation is named by the package
  README (the Architect's decision of 2026-10-27).
- **The unified vector command.** The optional profile map `vectors` and its complete input/output wire are defined in
  [Acceptance profiles and assembly](PROFILE.md#unified-vector-command). A package README assigns its consumer, tables,
  input columns, fixtures and directions; the implementation computes its own native result. A missing assigned entry is
  `blocked`, not PASS. Coverage uses the full export SHA and table SHA; a source line is an address only within that pin.

- **Launch command** — a template with substitutions: `{data}` — a new empty data directory of the instance; `{socket}` — the
  socket path of the store door (P/01.1); `{port}` — the HTTP port of the console on the loopback (lesson P/06 and the acceptances with the console stand); `{manifest}` — the directory
  of the stand manifests for the processes that need it (`MANIFEST_DIR`, P/02.3); the store command does not receive it and puts no manifests; `{body_limit}` and `{row_ceiling}` — the body limit and the row ceiling (N5 P/01.1);
  `{rights}` — the path of the rights file which the runner puts before the store starts (P/01.2 N1.2): in P/01.1 — the file below
  («Role sockets»), in the chapters P/01.2 and P/01.3 — the ready input [`01-store/acceptance/2/inputs/rights.json`](../../01-store/acceptance/2/inputs/rights.json), in the acceptances moved from M10/4–11 — the rights derived from the stand manifests by the rights derivation command below (`{manifests}` — the directory of the stand
  manifests, `{deployment}` = `dep`); the store command receives `{rights}`, not `{manifest}` (the log of cammeta-python, lesson 11
  № 29). The implementation names which substitutions each of its processes needs.
- **Manifest install command** `manifest-put` (P/02.3 N3 «Manifest change») — a template with `{socket}` and `{file}`: puts one manifest
  through the `admin.sock` of the store (`{socket}`); code 0 — put, another — a refusal. With it the runner sets up the stand manifests one by one
  in the order of «Manifests» below, after the store is ready and before the first `@start` (the store pilot, A6).
- **Rights derivation command** (P/02.5 N2) — a template with `{manifests}` (the directory of the manifests), `{deployment}` and `{file}`: writes the rights file per
  P/02.5 N1.4; code 0 — the file is written, another — a generation refusal. The implementation names it in its description (P/02.5
  «Implementation decides» item 1). The acceptance variants of P/02.5 (`5/variants/`) call it with `{deployment}` = `dep` (reconciliation of python and go
  M10/6–11).
- **Rights check command** (P/02.5 N2 `--check`, N3 «install») — the key `stand.rights-check` of the profile `02-installer`, a template with
  the same substitutions as the rights derivation command (`stand.rights`): `{manifests}` — the directory of the manifests, `{deployment}`, `{file}` —
  the rights file that is checked (not written); the outcome is the code: 0 — the file is equal in meaning to the rights derived from the manifests, another — they differ.
  The acceptance variants of P/02.5 with `check.tsv` call it for each case with the manifest directory of the variant, `{deployment}` = `dep` and
  `{file}` = `check/<case>.rights`; the code is compared with the column `code` (`0` | `!0`). There is no key in the profile — the cases of `check.tsv`
  are not executed (not GREEN and not an outcome of the implementation). There is no substitution `{specs}` in the stand vocabulary (the Architect's decision of 2026-10-30,
  the norm questions of the Gemini audit, P/02 item 3; C02-RIGHTS-CHECK-STAND-01).
- **Ring command** — the template `ring {file}`: creates a key ring per the [sealing contract](../contracts/sealing.md) (`w2cctl secrets new` of the implementation, P/02.4 N1.9) in the file
  `{file}`; the runner calls it before the first process with `{file}` = `{data}/etc/secrets/platform.key` (the Architect's decision,
  the second pilot); code 0 — the ring is created. The owner and the mode of the ring file on the stand — the section «Stand without root» below
  (I02-RING-FIXTURE).
- **Copy commands** (P/01.3 N1.3 `copy`, `admin_ops`): `backup` — a template with `{socket}` and `{file}`: a copy of the store through
  `admin.sock` into a file, code 0 — the copy is taken; `import` — a template with `{data}`, `{file}` and `{index_base}`: the transfer of a copy into
  a fresh directory of a stopped store (P/01.3 N1.3 `box`), code 0 — transferred, another — a refusal. The implementation names
  both (P/01.3 «Implementation decides» items 4, 11; the store pilot).
- **Command to load one manifest file** (P/02.1) — a template with `{file}`; exit code 0 — a manifest, another — a refusal, the text
  of the refusal names the file (the norms of P/02.1, «Implementation decides» item 3).
- **Processes of several roles** (lesson P/03 and later): the implementation names the launch command of each role — the store,
  the console, the controller, the worker, later the resource; the worker command receives the name by the substitution `{name}` (an argument), the environment —
  `BOX_ID` (the constant box of the stand, `stand-box`) and `SERVER_NAME` (`srv-a` on a single-server stand; P/02.4 N1.2); from the environment the worker takes its name only by `slot.name_env` of its manifest
  (P/02.1 N1.2a), and the runner sets this variable if the manifest declared it (`testsub2` — `TALLY_NAME`; `testsub` has none). In the acceptances moved from the lessons before M10/6 (rights — now P/01.2), the runner reads the store with a role that has full rights on the prefix of the subsystem.
- **Resource** ([P/05](../../05-resource/spec/05-resource.norms.md)): the launch command of the server resource with the substitution `{rport}` — the port of its door; the runner waits for the port
  and the row `platform/doors/<host>` before the first step. For a scenario that needs the heartbeats of other servers, the resource is on the server
  of the controller: the process reads the cluster objects through the resource of its own server (P/04 N3 «pass()» step 0; ADR-0084 addendum (2) R17).
- **Role sockets** (P/01.2, P/01.3 N1.3 `sockets`): on a box too the store opens a socket per role (`<role>.sock`, `admin.sock`) per the rights
  file; the runner calls through the socket of the role of the scenario. `{socket}` is the path of `admin.sock`; the role sockets lie next to it, in the same directory, flat (P/01.3 N1.3 `sockets`).
  `{socket}` is a door with full rights (preparation). Lesson 1 runs the scenarios with the role `acc` — read and write rights only on
  `acc/*`, the socket `acc.sock` next to `{socket}`. The runner puts exactly this file into `{rights}` (the form — P/01.2 N1.2):
  `{"roles": {"acc": {"group": "acc", "read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}}`.
  Deletion is a separate action (P/01.2 N1.3 `allowed`); in the file it is named explicitly.
  The store is ready when `admin.sock` and the socket `<role>.sock` of every role of its rights file accept a connection, within the term of «Terms of the stand» (15 s from the start by default; `@store-start` and `@server-start` are exceptions, their rows name their own terms); without a rights file only `admin.sock` is awaited. An instance that exits earlier or is not ready by then is a failed start; a rights file that cannot be read or has no object `roles` is a failure of the stand.
  The stand of P/01.2 is the store with its ready rights input above: it has no installer and no manifest is laid.
- **One data directory** `{data}` per instance — it is `PLATFORM_DIR` (P/02.4 N1.2 «The setting channel and the layout»;
  the second pilot, N-4). The stand translates the substitutions into the environment of P/02.4 N1.2: `PLATFORM_DIR={data}`,
  `PLATFORM_STORE=configstore://<role socket>`, `CONSOLE_PORT={port}`, `RESOURCE_PORT={rport}`, `BOX_ID`, `SERVER_NAME`,
  `SECRETS_KEY={data}/etc/secrets/platform.key` — the ring per the layout of P/02.4 N1.1, created by the runner with the ring command before the first process; the worker name — by the argument `{name}`. The layout is per P/02.4 N1.2: the store
  `{data}/configstore`, the objects `{data}/objects`, the events `{data}/events`, the presence locks `{data}/events/.workers`.
  In a composite stand, where the store runs together with other parts, the launch command of the store receives `-dir {data}/configstore`: `{data}` itself also holds the ring and the settings, so it is not the store directory. Before the first start of a store the stand creates the empty directory `{data}/configstore` with mode `0700`, as the installer does on a box ([P/02.4 N1.1](../../02-installer/spec/02.4-installer.norms.md#n11-processes-and-units)), on the stand of one store, on the [store group stand](#store-group-stand) for every member and on the stand of three servers; the daemon does not create an absent `-dir` (the Architect's decision on P01.89.4).
  The event root of a server is derived unambiguously — `{data}/events` of its `PLATFORM_DIR` (the stand does not set `RESOURCE_ROOT` and
  `EVENTS`), so «Stand» has no separate key for the event root.
  The server settings file is `W2C_ENV={data}/etc/w2c/w2c.env` (P/02.4 N1.2: the directory `roles/` is next to `w2c.env`,
  there is no other place), the role files are `{data}/etc/w2c/roles/<role>.env`; for a server `on <server>` — the same path in its
  `PLATFORM_DIR` `{data}/servers/<server>` (the choice of the owner of the runners, cammeta-acceptance e3ec5c3).
- **Manifests** are the files of [`Platform/common/data/testsub/`](../data/testsub/README.md); the stand sets them up by the command `manifest-put` in the order of dependencies: `testsub`, then `testsub2` (it references `testsub`: `about`,
  `near`, `worker.requests`); loading the directory (P/02.1 N3) sees both.
  The manifest `testsub2` declares `console.shell` and `console.files`: the installation reads these files next to the manifest file (P/02.3 N3
  «Manifest change»), so the stand puts next to the copy of the manifest the whole content of
  [`06-console/acceptance/5/inputs/testsub2/`](../../06-console/acceptance/5/inputs/testsub2) under the same paths — on every stand where
  `testsub2` is set up, not only in acceptance 6.5 (ADR-0094 B7).
- **Console root** (`CONSOLE_ROOT`) is named by the lesson README: chapter 6.2 — `testsub2` (the short paths `/tallies`),
  the others — `testsub`, the second subsystem is mounted under `/testsub2`.
- **Pass report print command** of the controller `<sub>/controller/pass` ([P/04](../../04-controller/spec/04-controller.norms.md)) — a template with `{data}` and `{sub}`;
  prints the current report object or nothing if there is none; by it the runner waits for the report to change (the norms of P/04,
  «Implementation decides» item 9).
- **Platform vector commands** `order`, `shrink-victim`, `shrink-allowed`, `workers-script` (stage A, A6; ADR-0084;
  `shrink-allowed` — the Architect's decision of 2026-10-20, № 12 of the review analysis of stage B 3–5) — templates with
  `{input}` — the path of the input file; the output — JSON in stdout; code 0 — computed, 2 — the input is not in form. The packages are
  `Platform/04-controller/vectors/order/`, `…/shrink-victim/`, `…/shrink-allowed/` (P/04 N3 «shortage(), order()», «shrink()»),
  `Platform/02-installer/vectors/workers-script/` (P/02.4 N1.5): the runner reads the `cases.tsv` of the package (UTF-8, TAB, lines
  with `#` and empty ones are skipped, the first one not skipped is the header), for each row writes the cell `input` byte for byte into a
  temporary file, calls the command of the package with `{input}` and compares stdout with the cell `expect` as JSON by value,
  whole (the order of the object keys does not matter; an array — by length, order and elements); code ≠ 0 or not JSON — FAIL of the
  row; a cell `expect` of the form `@exit <code>` judges only the exit code of the command, a bare `exit N` is a data error; the result of the package — the rows by `case`. The implementation names the templates in its description, like the other commands of «Stand».
  The commands `exec` and `install-order` of the profile `02-installer` and `door-token-verify` of the profile `03-worker` answer with the envelope
  `{"result": …}` — the protocol: `exec` — the README of its package `Platform/02-installer/vectors/exec/`, `install-order` — [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N5, `door-token-verify` — [the door token contract](../contracts/door-token.md) (the packages `…/install-order/`,
  `Platform/common/vectors/door-token/`; the stage C guess I02-STAND, the Architect's decision of 2026-10-23).
  The commands `group-of` (the profiles `03-worker`, `04-controller`: an address → `{group, fault}`) and `fresh-age` (the profiles `04-controller`,
  `06-console`: an age → `true`/`false`) — without an envelope, per the READMEs of their packages `Platform/common/vectors/group-of/`,
  `…/fresh-age/` (the stage C guess C04-VECTOR-01, the Architect's decision of 2026-10-23).
  The commands `rid` and `request-digest` of the profile `06-console` — without an envelope: `{"status": …}` and `{"canonical", "sha256"}`; the input —
  in the READMEs of the packages `Platform/06-console/vectors/rid/`, `…/request-digest/` (the stage C guess C06-F2-IO-01, the Architect's
  decision of 2026-10-23).
  The command `password-hash` of the profiles `08-domain` and `06-console` — a password hash and its check, without an envelope; the package
  `Platform/common/vectors/password-hash/` (the stage C guess GP-G06, the Architect's decision of 2026-10-23).
  The command `env-line` of the profile `02-installer` — a line of an environment file → a pair, `skip` or `bad`, without an envelope; the package
  `Platform/common/vectors/env-file/` (the stage C guess C04-ENV-01, the Architect's decision of 2026-10-23).
  The commands `said-id` and `said-read` of the profiles `03-worker` and `06-console` — without an envelope: stdout — a SaidID as a JSON string or
  `true`/`false`, code 0 — computed, 2 — the input is not in form; the input — in the README of the package `Platform/common/vectors/said-id/`
  (the stage C guess W03-G03, the Architect's decision of 2026-10-23).
  The commands `fault`, `values-by-type` and `door-token-issue` of the profile `06-console` — without an envelope: the map of the refusal dictionary,
  the closed `{status, …}` records and reads, `{claims_jcs, token}`; the input — in the READMEs of the packages `Platform/common/vectors/fault/`,
  `…/values-by-type/`, `…/door-token/` (the stage C guess C06-F2-IO-02, the Architect's decision of 2026-10-23).
  The command `covers` of the profiles `06-console` and `10-domain-console` — whether a grant covers a unit, without an envelope: stdout
  `true`/`false`, code 2 — the input is not in form; the input — in the README of the package `Platform/common/vectors/may/` «covers»
  (C06-EVENTS-QUERY-UNKNOWN-138-10, the Architect's decision of 2026-10-26). This is the former wire: the table `covers.tsv` is also executed
  by the `vectors` entry `common/may` of the profile (the unified command of a package above); with it `stand.covers` is not required, `blocked` — only without
  both; likewise the former commands `fault`, `values-by-type`, `door-token-issue` when there is a `vectors` entry for their package
  (ACC-VECTORS-COVERS-STAND-01, the Specification's decision).
- **Durability.** The store command MAY carry an implementation flag that switches off the durability barriers for the speed of the
  stand; the implementation names it in its description (P/01.1 «Implementation decides» item 3). There is no environment variable for this
  (P/01.3 N1.3 `durability`).
- **Instance** — per scenario (P/01.1) or per full run, as the lesson README says; the runner waits for the socket or the port,
  then checks the parameters by behaviour per N5 P/01.1. A ready door instead of a launch — the run is not isolated and not green.
  A run of named scenarios only (the gate `accept:<chapter>:<scenarios>` of a stage, ADR-0126) keeps the isolation per scenario and
  does not carry the chapter-wide probes of the parameters and of raw HTTP: its result names the subset, and a target is green
  only by its full run.
- **README checks beyond the TSV** in each lesson are a scenario or an item «checked by reading» with a subject: controlled
  clocks, two consoles on one store and drills on a real box with systemd (`@manual`, [system acceptance](system/README.md)) are not given by this interface;
  a store group of several daemons is given by «Store group stand» below (P/01.3 N5), a server failure — by «Three-server cluster stand» below.

### Environment of stand processes

A stand process receives only the variables below; other variables of the environment of the runner are not inherited. A listed name is admitted, not required: the stand sets values by this README.

| Applies | Variables |
|---|---|
| Every process, system | `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`, `TMP`, `TEMP`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ` |
| Every process, platform | `PLATFORM_DIR`, `PLATFORM_STORE`, `BOX_ID`, `SERVER_NAME`, `SECRETS_KEY`, `CONSOLE_ROOT`, `CONSOLE_PORT`, `RESOURCE_PORT`, `AGENT_TOKEN_DIR`, `MANIFEST_DIR`, `LABELS`, `TIMEZONE`, `W2C_ENV`, `W2C_TLS_DIR`, `CONSOLE_CALL_PORT`, `CLUSTER`, `CLUSTERS`, `DOMAIN_URL`, `RELAY_URL`, `RELAY`, `RELAY_HOST`, `RELAY_PORT`, `RELAY_MEMBER`, `W2C_WALL_OFFSET`, `DOMAIN_CA`, `RELAY_CA`, `SIGNER_URL`, `DOMAIN_CONSOLE_URL`, `LOGIN_URL` |
| Stands of processes and chapters | the variable named by `slot.name_env` of a stand manifest, `W2C_SHRINK_AFTER`, `W2C_ROLE`, `W2C_DEPLOYMENT`, `W2C_MANIFEST_REV` |
| One launch | the assignments `<NAME>=<value>` of that `@start worker`; `W2C_TOKEN` for the person's command of `@move` |

### Stand without root

The stand is started by an unprivileged user; the product is strict, the stand is not (the stage C guesses I02-RING-FIXTURE,
C04-STAND-GID-01, the Architect's decision of 2026-10-23):

- **platform groups** (`w2c-events`, `w2c-secrets`, `w2c-store` and the others of P/02.4 N1.1) on the stand are the current (primary) group of the process,
  one for all roles, on any OS and whether such a group exists on the machine or not (the event trees — the event journal contract
  `modes`; ACC-EJ-STAND-GROUP-01, the Architect's decision of 2026-10-28); the product requires system groups without a fallback;
- **roots** `{data}/config` — 2770, `{data}/objects` — 2770, `{data}/events` — 2771 (the modes of P/02.4 N1.1 `dirs`; there are no other
  roots; the directories inside `objects` are 0775 per P/05 `disk`, they are not roots) are created by the role launch command of the profile before the start of the
  process, if they are absent, — with these modes, with the current uid/gid (the group on the stand is the current one); it does not change the existing permissions and owners; the role
  process does not create roots (P/02.4 N1.1 `dirs`); `PLATFORM_DIR` is an absolute path (STAND-ROOTS-CLEAR-01, the Architect's decision of 2026-10-27);
- **key ring** — the ring command above creates a new file (the bytes — per the sealing contract) with the owner — the current
  uid/gid — and the mode 0640; it does not replace an existing file — a nonzero code; the owner `root:w2c-secrets` of the product (P/02.4 N1.9)
  is not checked by the stand;
- **the entry point of a process on the stand** is a profile command (for example, `controller-stand <sub>`): the process connects to the store
  with its own role (`PLATFORM_STORE` of the role), not `admin`.

### Dictionary of directives and doors

One definition per module. A lesson README references this dictionary and writes only its own: the preparation, the roles and
the special comparison rules. The column «Lesson» is the lesson that introduced the directive: a number — the former lesson M10/N (before the move),
`P/NN` — a lesson of the module, `M11/N` — a lesson of M11, `ADR-NNNN` — a decision without a lesson (like `@grow`, ADR-0084); a lesson introducing a new one
adds a row here (review analysis of stage B 3–5, № 33).

**A row of `scenarios.tsv`** — exactly the four cells `scenario`, `step`, `request`, `expect` separated by tabs. A cell contains neither a TAB nor a LF and has no escaping; a table with a `# cell-json:` declaration wraps the named cells by the [source-cell form](../contracts/source-cells.md), decoded once. Empty lines, lines of whitespace and lines beginning with `#` are notes and are skipped; a line whose first cell is exactly `scenario` is the header and is skipped too, so a table may also write its header as a `#` note. `expect` is empty only on an `ASSERT` step (which may also write `ok`). The steps of a scenario are numbered from 1 consecutively (1). A row outside this form or outside the forms of this dictionary is a data error of the table, found before the stand starts, not an outcome of the implementation.

**Doors** — the prefix of `request`. Without a prefix the request goes to the door of the lesson: the store in P/01 (chapters 1.1, 1.2) and P/02.5, the console in the chapters P/06 6.1, 6.3, 6.5, 6.6 (the former M10/1, 6 and M10/3, 4, 9).

| Door | Where | Lesson |
|---|---|---|
| `store` | the store door of P/01.1 through the socket of the role of the scenario; the role is named by the lesson README, `@as` changes it | 5 |
| `admin` | the store door through `admin.sock`; the stand sets the epoch floor through it — `admin POST /v1/write {"op": "floor", "floor": N, "id": …}` (P/01.3 N1.3 `floor`, `admin_ops`); there is no `w2cctl` command for the floor | 11; floor — P/01 |
| `restored` | the door through `admin.sock` of the store instance which the last `@import store` of the scenario brought up | 11 (the store pilot) |
| `console` | the console on `{port}`, the root subsystem `testsub` | 5 |
| `console2` | the same console, the prefix `/testsub2` of the mounted subsystem | 10 |
| `resource` | the door of the server resource on `{rport}` with an admissible identity | 8 |

**Request.**

| Form | Meaning | Lesson |
|---|---|---|
| `<METHOD> <path with query> [<body>]` | the path and the query go byte for byte, without re-encoding; the body is the bytes after the substitutions, invalid JSON is admissible; without a body text `POST` and `PUT` send `Content-Length: 0`, other methods send no body, on every door | 1 |
| `@big(N)` | a substitution in any part of the request: a string of N bytes `x`; inside a JSON string — before serialization; the substitutions of a request go in the order `@spoil($name)`, then `$name`, then `@profile(<name>)` and `@profile+1(<name>)`, then `@rep(N,<text>)`, then `@big(N)` | 1 |
| `@raw <text>` | the body is the text as UTF-8 bytes, `application/octet-stream`; `Content-Length` — by the bytes; `@raw` — only in the place of the body, as the first word after the path (`<door> <METHOD> <path> @raw <text>`), at any door; «@raw» inside a JSON body or another word is ordinary text of the body, not a directive (Codex review of the runner series 4faf728) | 10 |
| `@wire <text>` | raw HTTP: in the place of the method (`<door> @wire <text>`) the step opens a new connection to its door and writes exactly the bytes of the text, nothing added: no header, no `Content-Length`; the escapes `\r`, `\n`, `\t`, `\\` and `\xHH` (two hexadecimal digits) give one byte each and are read after the substitutions, another `\` is a data error of the table; the response is read as HTTP/1.1 on the same connection | P/01.1 (P01.142) |
| `@halfclose` | the last word of a `@wire` request, after one space, not one of its bytes: after the bytes the judge closes the write side of the connection and goes on reading | P/01.1 (P01.142) |
| `@rep(N,<text>)` | a substitution in any part of the request: the text repeated N times; the text runs to the first `)` and holds none | P/01.1 (P01.142) |
| `@profile(<name>)` / `@profile+1(<name>)` | a substitution in any part of the request, also in the place of N of `@big(N)` and `@rep(N,<text>)`: the value of the integer key `<name>` of the profile field `keys` (`forms/profile-keys.tsv`), or this value plus 1, in decimal; there is no other arithmetic; an absent key leaves the step `not_executed` with its name as the reason | P/01.1 (P01.142) |
| `@pause(<seconds>)` | inside the bytes of a `@wire` request: the judge stops writing for that many seconds, a decimal number, and then writes the rest; meanwhile it reads the connection | P/01 (P01.149) |
| `@key(<word>)` / `@nokey` | `Idempotency-Key` on `POST` — by default `<run>-<scenario>-<step>`, fresh per run; `@key(<word>)` sets `<run>-<scenario>-<word>`, that is, `@key(N)` repeats the exact bytes of the key of step N of its scenario; `@nokey` — without the header | 3 |
| `@as <role>` | the step and the following `store` steps of the scenario — from this role, through the socket `<role>.sock` (the section «Stand» above) | 6 |
| `@header <Name>: <value>` before the method | add a header to one request; `@header Idempotency-Key: …` replaces the default key of the runner (`@key`) | 6; key — 3 |
| `ASSERT $a != $b [$c …]` | the named values are pairwise distinct; no HTTP is sent | 1 |
| `ASSERT <term> <op> <term>` | a comparison of bound values; no HTTP is sent. `<term>` is `$name`, a JSON number or a difference `$a - $b`; `<op>` is `==`, `!=`, `<`, `<=`, `>`, `>=`. Order and difference — only for numbers; for strings — `==` and `!=`; different types — a mismatch (`ASSERT $t2 - $t1 < 2`, `ASSERT $a <= $b`) | M11 (mutation check 2026-10-18) |

**Stand directives** — not HTTP; the answer is `ok` or a refusal of the runner.

| Form | Meaning | Lesson |
|---|---|---|
| `@start controller [<sub>] [shrink_after=<s>]` / `@start worker [<sub>] <name> [on <server>] [labels=<labels>] [<NAME>=<value>…]` / `@start resource [on <server>]` | start a role process with the command of «Stand»; `shrink_after=<s>` — the environment `W2C_SHRINK_AFTER=<s>` for the controller (stand only, P/04 N1.4 `SHRINK_AFTER`; ADR-0084); `<sub>` — a subsystem of the stand directory, without it — `testsub`; `labels=<labels>` — only for a worker (on another role — a data error), the environment `LABELS=<labels>` for the worker as it is (P/03.2 sc. 11); the worker's `LABELS` comes only from this word: it is neither inherited from the runner nor carried between workers; `<NAME>=<value>` (only for a worker; the name is `^[A-Z][A-Z0-9_]*$`, the value — up to a space, empty — the variable is empty) — the environment `<NAME>` of this process with this value instead of the value of the runner, the other substitutions, directories and environment — as before (P/03.2 sc. 22: `INSTANCE_ID`, `BOX_ID`, `SERVER_NAME`; the coverage audit of P/03, 2026-10-30); the expectation: `ok` — the process is started; for a worker, a controller and a resource also `@exit <code>` — the process exited with this code no later than 10 s from the start together with its whole process group, the output is not compared (a start refusal, P/03.2 sc. 09, 11, 19, 22; the controller — P/04 sc. 23, the resource — P/05 sc. 17, the schema check at start); the worker receives its name by the substitution `{name}` in the command of «Stand» and, if the manifest declared `slot.name_env`, also in this variable (`testsub2` — `TALLY_NAME`), the same box, `server=srv-a`; `on <server>` (ADR-0084) — a process of the server `<server>`: `SERVER_NAME=<server>`, `BOX_ID` — `<stand box>-<server>`; a server other than `srv-a` has its own `PLATFORM_DIR` `{data}/servers/<server>` (its own event root and presence locks), the same store (`PLATFORM_STORE`) and the same ring (`SECRETS_KEY`), a resource has its own `{rport}`; for the resource of each server the runner puts the role file `roles/<sub>worker.env` of each manifest with `grows: true` (`HOST_MEMORY_MB=4096`, `WORKER_MEMORY_MB=256`, the directory `roles/` — next to `W2C_ENV` of its `PLATFORM_DIR`: `<PLATFORM_DIR>/etc/w2c/roles/`, P/02.4 N1.2), so that the resource writes `room.<sub>` (P/05 N1.4; the presence lock contract «Count `room`»); a repeat of the same name — a second copy; the readiness is checked by the following `@until`; the controller and worker commands of «Stand» receive the substitution `{sub}` (without `<sub>` — `testsub`), the resource command — `{server}` (`srv-a`; on the stand of M11 — `srv-<cluster>`) | 5; the resource and `<sub>` — 8; `on <server>` — ADR-0084; `<NAME>=<value>` and `@exit` of the worker — P/03.2 (the coverage audit of P/03, 2026-10-30); `@exit` of the controller — P/04 (the coverage audit of P/04, 2026-10-30); `@exit` of the resource — P/05 (the coverage audit of P/05, 2026-10-30) |
| `@grow <server>…` | until the end of the scenario the runner reads, once every 5 s, `/<sub>/metrics` of the console of each manifest with `grows: true` and for the named servers keeps exactly the worker numbers `<prefix>-<server>-<n>` from `{2…want}`, where `want` is the series `<sub>_workers_wanted{server="<server>"}` (the base one `-1` is started by the scenario itself; ADR-0084 addendum (4) R26): a missing number — `@start worker <sub> <prefix>-<server>-<n> on <server>`, the smallest first, but no more than `floor(HOST_MEMORY_MB / WORKER_MEMORY_MB)` processes of the role on the server together with the base one — like the memory ceiling of the script (P/02.4 N1.5; ADR-0084 addendum (2) R14); a number greater than `want` — `@sigterm`, the largest first (the number — as an integer); there is no series, it is unreadable or the console is silent — nothing; the servers are not named — the order on them is not executed («did not bring up»); the server script of P/02.4 N1.5 is executed without polkit (it is checked by the test of the unit and the policy) | ADR-0084 |
| `@sigterm <name>[#n]` / `@sigkill <name>[#n]` | stop a process; `<name>` is a worker name or the role of a process `controller` (the controller of `testsub`), `resource`, `console` — the cluster console, `domain` — the process `domain`, `domainconsole` — the domain console, `agent` — the cluster agent (copies — `agent#<n>`, `@start agent <cluster> second`; DOM-AGENT-TURN-01) (on the domain stand — `@on <cluster> …`; review analysis of stage B 8–10, № 15); by default the last copy with this name, `#1` — the first | 5; `#n` of `@sigterm` — M11/12 |
| `@freeze <name>[#n]` / `@thaw <name>[#n]` | freeze a role process (SIGSTOP to the process group) / unfreeze it (SIGCONT); `<name>` — as for `@sigkill`; does not wait for an exit; the expectation `ok`. The freeze limit is 120 s: not unfrozen by the limit or by the end of the scenario — the runner sends SIGCONT itself (also before the teardown of the stand: a stopped process does not hear SIGTERM), the step is of the class «data», not an outcome of the implementation. The meaning is a pause of the machine: the whole process freezes, with all its threads (at the Architect's request of 2026-10-30, the estimate of the runner ~2–3 h; the audits of P/03, P/04) | P/03, P/04 (2026-10-30) |
| `@cut role <role> store` / `@mend role <role> store` | a proxy of the runner on the unix socket of the store role `<role>`: for the stand processes of this role `PLATFORM_STORE` points to the socket of the proxy (the runner sets it up before the processes start if the role is named in the scenario), the proxy itself connects to the real `<role>.sock` — the identity is the same (P/01.2: the identity is the role socket). `@cut` — silence: live and new connections are accepted, bytes are not forwarded in either direction, nothing is closed (the store «hangs without an answer», not a refusal); `@mend` — the connections opened or hanging during the cut are closed (the outcome of their requests is unknown to the client), new ones are forwarded again; the expectation `ok`. The name is not `store@<id>` of a group member (at the Architect's request of 2026-10-30, the estimate of the runner ~1 day; the audits of P/03 C11, P/04 D07) | P/03, P/04 (2026-10-30) |
| `@put object <key> <file>` | put an object of the object store of the stand with the bytes of the file (the path — from the acceptance directory of the lesson) by the object write command of the implementation ([P/05](../../05-resource/spec/05-resource.norms.md) «Implementation decides» item 8), bypassing the writer and its checks | M11/11 (mutation check) |
| `@spoil object <key>` | spoil an object of the object store of the stand by the spoil command of the implementation (P/05 «Implementation decides» item 8): after it a read of the object is unreadable (P/05 N1.1): the bytes of the object are spoiled — the body is not read by its family; the file and the directory of the object are intact, the resource door gives it out as it is — in the listing with `written`, `server`, `size`, `GET` 200 (P/05 N1.1 `door`), the judgement garbled is the reader's; an object which the door itself does not read is not a spoil (C05-SPOIL-OBJECT-BYTES-01, the Specification's decision); the writer process of the object is stopped before this | 11 (reconciliation of python and go) |
| `@restart store` | SIGTERM to the store, wait for the exit, start it with the same command with the same `{data}`, wait for its readiness by the rule of «Role sockets» | 11 |
| `@sigterm store` | on the stand of one store: SIGTERM to the process group of the store; the expectation `ok` — the process exited, `@exit <code>` — it exited with this code, not by a signal | P/01 (P01.149) |
| `@rights store <file\|none>` | SIGTERM to the stand store, wait for the exit, start it with the same command with the same `{data}` and the rights file `<file>` (the path from the acceptance directory of the lesson; the runner puts it into `{rights}`) or without `-rights` (`none`: in the command template of «Stand» the runner removes the occurrence `-rights {rights}` or `-rights={rights}` — the flag with the substitution `{rights}`, not any word `-rights`: in a composite command it may belong not to the store — and changes nothing else; `<file>` — the same `{rights}` points to it; there is no such occurrence in the template or there is more than one — the scenario is not_executed with a reason, Codex review of series A); the expectation: `ok` — the store is ready by the rule of «Role sockets» above (`none` — without a rights file); the runner sends no request for this (`/v1/status` of chapter 1.3 may still be a stub at the stage `rights`); `@exit 2` — the process exited with code 2 no later than 10 s (the file is not in the form of P/01.2 N1.2, N4); the file of the previous row does not carry over to the following scenarios | P/01.2 (the coverage audit of P/01, 2026-10-30) |
| `@spoil row <key>` / `@spoil row-index <key>` | spoiling a row of the stand store bypassing the door: SIGTERM to the store, the command `spoil-row` of «Stand» with `{data}`, `{key}` and `{what}` (`body` — the bytes of the row body are unreadable, the version is intact; `index` — the row version is lost, the body is intact), a start with the same command; the expectation `ok`; the implementation names the command and what it spoils in its description (P/01.1 «Implementation decides» item 5); the command in the profile is also the declaration of a durable store (there is no separate key); there is no command — not_executed only for a scenario with `@spoil row`, the others are executed, the result of the lesson is not GREEN | P/01.1 (the coverage audit of P/01, 2026-10-30) |
| `@restart console` | SIGTERM to the console, wait for the exit, start it with the same command of «Stand» with the same `{data}` and `{port}`, wait for the port; the port did not come within 20 s — a refusal of the runner | 7 (reconciliation of python and go M10/6–11, S8) |
| `@append event <tree>/<unit>/e<epoch> <text>` | append the text as a line (UTF-8 bytes and LF) into the bucket by `t` of the line `<events root of srv-a>/<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`, `start` = floor(t / 600) × 600; a text that is not JSON, without a numeric `t` or with `t` outside [0, 253402300799] (the bucket name is a four-digit year, 1970–9999; the writer refuses a line later than the year 9999, the event journal contract «Writer refusals», EJ-G06) — the bucket of the current window ([event journal contract](../contracts/event-journal.md) «Writing a line», step 4 — review analysis of stage B 3–5, V1; the root — `{data}/events`, «Stand») bypassing the writer; there is no file — create it; `{now}` in the text — the wall seconds of the runner at the moment of the write (time per N0 P/01.1); the components of the path — per the encoding of names ([event journal contract](../contracts/event-journal.md) «File names in shared trees») | 8 (reconciliation of python and go M10/6–11, E19) |
| `@append event-raw <tree>/<unit>/e<epoch> <text>` | like `@append event` (the bucket of the current window, the root, the encoding of the path components, `{now}`; there is no file — create it), but the text is appended as UTF-8 bytes without LF at the end — a torn tail of the bucket ([event journal contract](../contracts/event-journal.md) «The line and the bucket» `torn`); the expectation `ok`. The next append into the same bucket will glue together with the tail into one line — the tail is written last in the bucket of the scenario | P/05 (the coverage audit of P/05, 2026-10-30) |
| `@backup store <name>` | take a copy of the stand store with the command `backup` of «Stand» into a file of the runner `<name>` (it lives until the end of the scenario); `ok` — code 0 and the file in the form of P/01.3 N1.3 `copy` (a header, Row rows, keys in ascending byte order); otherwise a refusal of the runner | 11 (the store pilot) |
| `@backup store <name> in-data` | the command `backup` of «Stand» with `{file}` = `{data}/configstore/<name>` — inside the data directory of the stand store (`-dir`); the expectation `refused` — code ≠ 0 and there is no file `{data}/configstore/<name>` | 11 (reconciliation of python and go M10/6–11, B8) |
| `@import store <file>` / `@import store backup <name>` | the input is a file from the acceptance directory of the lesson or a copy `@backup store <name>` of this scenario; the runner takes a new empty `{data}`, calls the command `import` of «Stand» with `{index_base}` — the `index` of the header of the input (the header is not readable — `0`), then on this `{data}` starts a second store instance with the command of «Stand» with its own `{socket}` and waits for its readiness by the rule of «Role sockets» — its door is `restored`. The expectation `ok` — the code of `import` is 0; `refused` — code ≠ 0 (that the directory remained without rows is seen by the following steps `restored`). The stand store is not touched | 11 (the store pilot) |
| `@foreign store nolabel` / `@foreign store otherlabel` | a second store instance with the same command with a new directory `{data}` and its own `{socket}`; before the start the runner puts into the store directory `{data}/configstore`: `nolabel` — a file `rows` with the bytes `x` and without `FORMAT`; `otherlabel` — `FORMAT` with the bytes `{"format":"w2c-acceptance-foreign","version":1,"impl":"runner"}`. `ok` — the process exited with code 2 no later than 10 s and the directory tree (names, bytes) is the same as before the start; otherwise a refusal of the runner. The stand store is not touched (P/01.3 N1.3 `format`) | 11 (the store pilot) |
| `@sleep <seconds>` | wait. Only a check of absence (nothing happened within the term) or a time that the norm requires before an action; waiting for an event — `@until` by an observable sign. The length is the smallest at which a violation would have had time to show; each judge-owned case sleep is named with its reason in the lesson’s acceptance case instructions (ADR-0080 addendum (17) item 4) | 5 |
| `@together <request> \|\| <request>` | two requests at once: the runner opens both connections and sends both requests without waiting for the answer to the first (the last byte of the second leaves before the answer to the first arrives); the expectation `ok {"codes": [<code>, <code>]}` — the codes of both answers in ascending order, the bodies are not judged; so the acceptance sees an admission race that sequential steps would not show | ADR-0119 addendum (18) |
| `@until <seconds> <request>` | repeat the request, at least once per second, until it matches `expect`, no longer than the term; the term ran out — FAIL with the last answer; a read is repeated, not a mutation | 5 |
| `@hold <door> <N>` | open N connections to the door and write nothing on them; they stay open until the end of the scenario, then the judge closes them; the expectation `ok` — all N were accepted | P/01 (P01.149) |
| `@io store $<name>` | bind the name to the number of bytes that the processes of the store caused to be written to storage: the field `write_bytes` of `/proc/<pid>/io`, summed over the process group of the store; the expectation `ok`. When the judge cannot read this counter, for example under another account, the step and every step that compares the name are `not_executed` with the reason `io_counter_unreadable`, not red | P/01 (P01.149) |
| `@manual <text>` | a drill step: the runner prints the text and does not execute it; it does not enter the result (neither green nor red), `expect` — `manual` | 11 |

**Terms of the stand** (upper bounds; the class of an expired term — N4 of the [norms](spec/acceptance.norms.md)).

| What | Term | Ready or judged when |
|---|---|---|
| the readiness of a store, by default | 15 s | the rule of «Role sockets» |
| the console, its first start and a copy `console#<n>` | 40 s | the port listens |
| `@start` of a role with a door (the resource) | 20 s | the port listens and the door row exists |
| `@import store` | 30 s | the instance `restored` is ready |
| the process `domain`, also on a cluster and its second copy | 30 s | its door answers |
| the login of `root` after `@install domain` | 30 s | `signer POST /api/login` succeeds, with repeats |
| the local door of a just started agent copy | 10 s | the process is alive at the end of the term; the term ends early when the socket of the door, created after the start, accepts a connection |
| one HTTP step, raw HTTP included | 60 s | the answer of the door |
| `@noreply`, and the end of reading after `@close` | 10 s | no byte of a response arrives, or the implementation closes the connection |
| a command of «Stand» run by the stand (`manifest-put`, `backup`, `import`, `spoil-row`, `ring`, the commands of the installer) | 120 s | the exit of the command |
| one row of a vector | 60 s | the exit of the command |
| the command `move` | 150 s | the exit of the command |

**Expectation.**

| Form | Meaning | Lesson |
|---|---|---|
| `<code>` | the code is exact; the body is not checked, except the full form per the contract of the owner | 1 |
| `@exit <code>` | for a vector command (the request is a command of the lesson on an input `inputs/`): the exit code of the command is exactly `<code>`; the output is not compared, stderr is not normed; the expectation `ok <JSON>` — code 0 and the output; for `@start worker`, `@start controller` and `@start resource` — the process exited with the code `<code>` no later than 10 s from the start (the stand directives above) | M11 (the Architect's decision on the reconciliation of M11, H14); `@start worker` — P/03.2 (the coverage audit of P/03, 2026-10-30); `@start controller` — P/04 (the coverage audit of P/04, 2026-10-30); `@start resource` — P/05 (the coverage audit of P/05, 2026-10-30) |
| `2xx` / `4xx` | the class of the code | 4 |
| `@oneof <code> <JSON> \| <code> <JSON>` | one of the answers: the branches are separated by « \| », each is the form `<code> <JSON>` and is judged by the rule of this form in the mode `body` of the target (`whole` — JSON whole, without `@any`; `subset` — a subset, `@any`/`@absent`/`~`); the separator is only between branches, after a completed JSON value (« \| » inside a JSON string is part of the string); there are at least two branches, the JSON of a branch is strict, `NaN` or `Infinity` in a branch is a data error; the code of a branch is exact, there is no class `2xx` in a branch; the branches are checked in order, the first that matches wins; the bindings `$name` are fixed only by the matched branch — a name bound only in another branch is not bound further; for a race which the norm allows with two answers (P/06.4 N3 «file a request» step 5: `200 answered` or `202 queued`) | the request of VMS of 2026-10-29 (C-ONEOF-01, the Specification's decision) |
| `<code> <JSON>` | by the mode of the column `body` of the routing row of the target ([`forms/targets.routing.tsv`](forms/targets.routing.tsv)); a lesson or a chapter name sets no mode. `whole` — JSON whole (the order of the object fields does not matter): a field that the expectation does not name is a mismatch, except where the README of the first directory of the routing row admits it — by a line «An unnamed `<name>` is admitted only in the root of the body» (then `<name>` is compared only where the expectation names it, and unnamed it is admitted with any value in the root object of the body and nowhere else) or by a special comparison rule of that README. `subset` (since the former M10/3) — a **subset**: the named fields are present and equal, the others are admissible; `{}` in an expectation at any level is exactly an empty object; any object is `@any`; no field is `@absent` (ACC-EMPTY-OBJECT-01, the Architect's decision of 2026-10-26); an array whose order the norm does not set (the list is here: `configured` of the answer `GET /<rows>`, P/06.1 N2) — without order: the lengths are equal and there is a one-to-one matching under which each element of the expectation matches its actual one by subset; the other arrays — by length, order and elements (the Architect's decision of 2026-10-27); JSON types are exact: in both modes, `whole` included, a JSON number is compared by value (`50` = `50.0`, `1e2` = `100`), a string, `true`/`false` and `null` are not equal to a number | 1, 3 |
| `$name` | binds a JSON string or number (a number — for `ASSERT`; in the mode `whole` only a string, another type is a mismatch of the step); the first occurrence binds, the following ones compare; in `request` the bound value is substituted; the bindings of an attempt are fixed only after the whole step matches; they live until the end of the scenario; the name is `[A-Za-z0-9_]+`, it ends at the first other character (`…/$r2.delta` — the name `r2`) | 1 |
| `@spoil($name)` in `request` | the bound string with a character changed in the middle of its last segment after «.» (for a string without «.» — in the middle of the string): the position ⌊n/2⌋ of a segment of length n, `A` → `B`, any other character → `A`; the form (length, base64url alphabet, canonicity) is the same — in a signature a character with full 6 bits is changed, not the last one (in a 64-byte signature it carries 2 bits, and the replacement would give a non-canonical tail — `not_a_token` instead of `bad_signature`); the signature of the token or the document no longer verifies — this is how a bound token is forged (`$ta`, `$tok`) (the log of cammeta-python; the Architect's decision of 2026-10-18) | M11 (mutation check 2026-10-18) |
| `@any` / `@absent` | the field is present with any value / there is no field | 3 |
| `@time` | the field is present, and its value is a time in the form of the writer (N0 P/01.1 «Time in a row»): a string `^(0\|[1-9][0-9]*)(\.[0-9]{1,3})?$` or a JSON number whose text in the answer body is the same notation | 1 (the Architect's decision of 2026-10-18) |
| `@not(<value>)` | the field is present, and its value is not the given JSON string (or not the bound `$name`): so the growth of a monotonic counter is observed without fixing the number | 5 |
| `~text` | a string value contains a substring; several substrings — separated by « ~»: `"~at rev 1 ~look again"` — both (a substring with « ~» inside is not written this way); for the body of `/metrics` of the console — a series, not a substring (the acceptance README of P/06.5 «Series») | 3; several — M11 (mutation check 2026-10-18) |
| `!contains text` | a string value does not contain the substring | 1 |
| `<code> ~text` | a non-JSON body (html, text) contains the substring as UTF-8 bytes; several — separated by « ~», as above; on a JSON body (`Content-Type: application/json`; JSON Lines is not a JSON body) this form is a data error of the class `data`, found when the step runs: a JSON body is judged by the JSON forms | 9 |
| `<code> !contains text` | a non-JSON body does not contain the substring (UTF-8 bytes) | 9 (reconciliation of python and go M10/6–11, C39) |
| `@header <Name>: ~<text>` after the code | a header of the answer contains the text; for a repeated header (two `Set-Cookie`) — at least one of its values | 9; repeated — reconciliation of python and go M10/6–11, C34 |
| `@header <Name>: =<text>` after the code | the header is present exactly once, and its value is equal to the text byte for byte; the text — up to the end of the cell; so a value is judged for which a substring would let a foreign address through (`Location`) | 6 (ADR-0094 B7; C06-HEADER-EXACT-01) |
| `@file <path>` after the code | the body is equal to the file byte for byte; the path — from the root of the specification | 9 |
| `<code> @empty` | the answer body is zero bytes; after `@empty` in the same cell one `@header` of the expectation is admissible | 6 (ADR-0094 B7; C06-HEADER-EXACT-01) |
| `<code> @close …` | `@close` right after the code: after its response the implementation closes the connection, within the term of `@noreply`; the rest of the cell is judged as the expectation without `@close` | P/01.1 (P01.142) |
| `@noreply` | the whole expectation: no byte of a response arrives until the implementation closes the connection or the term of `@noreply` in «Terms of the stand» ends; a response is a mismatch | P/01.1 (P01.142) |
| `… @by(<seconds>)` | the last word of an expectation: the response, the close of `@close` or `@noreply`, or the exit after `@sigterm store` comes no later than that many seconds after the start of the step, instead of the term of `@noreply`; with `@noreply` the implementation must also close the connection within it. It is an upper bound: the judge records the resolution of its clock and of its scheduling separately and does not widen the bound | P/01 (P01.149) |

A subset in `expect` does not cancel the full form of the answer per the contract of the owner of the door. A response code that the contract of its door does not describe is a gap of the contract, the class `data` on the row of the contract, not a silent pass.

**Full form by door.**

| Door | Contract of the full form |
|---|---|
| `store`, `admin`, `restored`, `store@<id>`, `admin@<id>` | P/01 |
| `console`, `console2`, `member <cluster> console`, `member <cluster> console2`: the paths `/api/…` and `/domain…`; on a stand other than the domain stand, every path | P/06 |
| `console` on a forwarded path `/domain/at/<cluster>/…` of a successful answer | P/06 of the forwarded path |
| `resource`, `resource#<name>` | P/05 |
| `holder`, `holder@<cluster>` | P/10, then P/08: the first contract that names the operation |
| `signer`, `signer2` | P/08 |
| `token <cluster>` | P/09 |
| any of the doors above with the refusal `deposed`, `frozen` or `standby` | `Refusal` of P/08 |

On a stand without a kit, `no_role`, `wrong_role` or `bad_chain` from `holder` over plain HTTP is a mismatch (P/10 `no_kit`). No full form is judged for the door `socket`, for a console path of the domain stand other than `/api/…` and `/domain…`, and for a body that is not JSON unless the row of its door requires it.

An answer body compared as JSON is parsed strictly: a repeated object name at any level or a non-JSON number constant (`NaN`, `Infinity`) is a mismatch of the step.

The isolated instance of chapter 1.1, its preparation and its limits are in the [acceptance README of that chapter](../../01-store/acceptance/1/README.md).

### Command tables

In a command table a row is a call of a command or an adapter of the profile, not an HTTP step. The routing word of the target names the form: `verdicts`, `puts` or `variants` ([`forms/targets.routing.tsv`](forms/targets.routing.tsv)). The tables are those of the first directory of the routing row. The interface of each call comes from the public row of the target ([target registry](forms/targets.README.md)). The judge reads every table of the target whole before the stand starts. Empty lines and lines that begin with `#` are notes, except the declarations that a form names. A row outside its form is a data error of the class `data`, found before the stand starts; it is not an outcome of the implementation. The inventory of the target (N1.4 of the [norms](spec/acceptance.norms.md)) names each row by its file and the number of its physical line.

#### Loader verdicts

The word `verdicts` runs `verdicts.tsv` of the first directory with `classes.tsv` and `diagnostics.tsv` next to it. The rules by which a verdict is set are the norms of the owner of the target (P/02.1 N1, N4); this form says only how a row runs and what the judge observes.

- **`verdicts.tsv`.** A row is `case<TAB>verdict`. The input is the file `cases/<case>.subsystem.yaml`, loaded alone, without a catalogue of other manifests. `verdict` is `ok` (the manifest loads) or `refused` (a loading refusal). The set of files of `cases/` equals the set of rows; an extra file or an extra row is a data error.
- **The call.** The judge loads each file through the interface of the target. With the command `stand.load` the substitution `{file}` is the path of the file. Exit code 0 is a manifest. An exit with another code, not by a signal, whose stdout or stderr contains the file name `<case>.subsystem.yaml` is a refusal. With the adapter `load` ([manifest loader](PROFILE.md#manifest-loader)) the answer `verdict` is `ok` or `refused`; a refusal is `refused` whose `text` contains the file name. Anything else is a mismatch of the row: a death by a signal, a refusal that does not name the file, a broken answer of the adapter.
- **The verdict.** It is strict: `ok` matches only a manifest, `refused` only a refusal.
- **`classes.tsv`.** A row is `case<TAB>class`, where `class` is `text`, `form`, `relations` or `catalogue`. Its `case` has `refused` in `verdicts.tsv`. The refusal text contains the word `refused:<class>` of the class of the case and no other word `refused:<word>`; otherwise the row of the case is a mismatch.
- **`diagnostics.tsv`.** A row is `case<TAB>paths<TAB>lines`. Its `case` occurs once and has `refused` in `verdicts.tsv`. `paths` is a JSON array of paths, each an array of key names and list indexes; `lines` is a JSON array of line numbers from 1. A row is a hint, not a check. The judge looks for each path in the refusal text in the form of `keys.path_style` of the profile: `json` — the text of the JSON array, `dotted` — the names joined by `.` with an index as `[N]`. It looks for each line number as a decimal word. What it does not find it writes into the report, without a failure. Extra paths in the text are not observed.

A run of these files through `manifest put` is not part of this word; such a sample is written as rows of [installation sequences](#installation-sequences).

#### Installation sequences

The word `puts` runs `puts.tsv` of the first directory and the files of the column `tables` of the routing row, all by this form. A row is a sequence of installations of manifests into one fresh store.

**The form of the table.** UTF-8, lines separated by LF, cells by TAB. The first line that is not a note is the header. It selects the columns: `case<TAB>puts<TAB>expect`, `case<TAB>puts<TAB>expect<TAB>canonical` or `case<TAB>puts<TAB>expect<TAB>canonical<TAB>ceiling`. Then one line per case with exactly the cells of the header.

- `case` — the name of the case, `[a-z0-9_]+`, unique in the file.
- `puts` — words separated by one space, in order: file names and the directives below. A file name `<file>` is the file `puts/<file>.subsystem.yaml` of the first directory. A file comes first and last.
- `expect` — `<code> <rev>`, then optionally `@stderr`. `<code>` is the return code of the **last** installation, `0` or `2`. `<rev>` is the decimal `rev` of the row `platform/manifest/<name>` after it, where `<name>` is the `name` of the last file; `-` — there is no row.
- `canonical` — the name of a case of the vector package of the declaration `# canonical:`. The bytes of its file `expect/<canonical>.json` are the expected field `manifest` of the view row; `-` — there is no view row.
- `ceiling` — the row ceiling of the store of this line, its `{row_ceiling}`.

**Declarations.** Two note lines are declarations of the table:

- `# canonical: <directory>` — the vector package whose files `expect/<case>.json` give the bytes of the column `canonical`. A table with the column `canonical` and without this declaration is a data error.
- `# beside: <directory>` — the whole content of the directory lies, under the same paths, next to the working copies of every installation of every line.

The path of a declaration is from the root of the specification. It names a directory of the routing row of the target; another directory is a data error.

**Names.** `<name>` of a file is the value of its top-level key `name`, read as YAML. A directive takes `<name>` of the file before it.

**Execution.** The lines are independent; their order does not matter. For each line the judge takes a new empty store and a new working directory. The store is started by the store command of the target, without a rights file; `{row_ceiling}` is the cell `ceiling`, or, without that column, the row ceiling of the [parameters of each instance](../../01-store/acceptance/1/README.md) of P/01.1, 524288 bytes. Then the judge runs `puts` in order. A file is copied into the working directory under its own file name and installed by a separate call of the command `manifest-put` of the target, with `{socket}` and `{file}` — the working copy. A directive is executed by its row below. Every installation except the last MUST return `0` and every directive MUST pass; otherwise the case is a mismatch (the preparation failed).

**Comparison.** After the last installation the judge compares:

1. the return code with `<code>`;
2. with a code other than `0`: stderr contains the file name of the last installation and every substring of `@stderr`;
3. `rev` of the row `platform/manifest/<name>` with `<rev>`: the row is read by `GET /v1/get?key=platform/manifest/<name>` through `{socket}`, the field `rev` in `items`; `-` — `items: null`.

With the column `canonical` the judge also compares:

4. the mark `platform/manifest/<name>/rev`. With the code `0` its `rev` is `<rev>` and its `sha256` is the `sha256` of the row; with `-` there is no mark. With another code the mark is byte for byte the mark before the last installation: a refused installation does not touch it;
5. the view row `platform/manifest/<name>/canonical/1`, its `items` by the codec of [the family `canonical-row`](../../02-installer/data/canonical-row.schema.json): `form` is `"1"`, `rev` is `<rev>`, `sha256` is the `sha256` of the row, `manifest` is byte for byte the bytes of `expect/<canonical>.json`. Other fields are not compared. With `canonical` = `-` there is no view row.

Without the column `canonical` the mark and the view are not compared. The order of the writes in time and the repeat of the view after a `cas` conflict are not compared; they are checked by reading. The former rule of P/02.2 «with code `2` stderr names the key of the view, after `@rev-spoil` the key of the mark» is now written in the table by the word `@stderr`.

**A line with `ceiling`.** Before the case the judge confirms the ceiling of the new store. `GET /v1/status` gives `max_value` = `ceiling`. A `put` through `{socket}` of the row `acceptance/ceiling` with `items` of weight exactly `ceiling` succeeds; one byte more gives `413 toolarge` with `limit` = `ceiling`. Then the judge deletes the row. The weight is that of P/01.1 N1. If the judge cannot confirm the ceiling, the line is `not_executed` with the reason `installer_ceiling_unproven`.

**Words of `puts` and `expect`.** The directives write through `admin.sock` of the instance, that is `{socket}`, by the operations of P/01.1. A directive that does not pass fails the preparation of its line.

| Form | Meaning | Lesson |
|---|---|---|
| `@view-delete` | `delete` of the row `platform/manifest/<name>/canonical/1` | P/02.2 |
| `@view-spoil` | read the row `platform/manifest/<name>/canonical/1` and write it back with `cas` by the version read, but with the field `manifest` equal to `{}` (a different view: not a projection of the manifest); the other fields as they were | P/02.2 |
| `@rev-delete` | `delete` of the mark `platform/manifest/<name>/rev` | P/02.2 (the Gemini coverage audit of P/02) |
| `@rev-spoil` | read the mark `platform/manifest/<name>/rev` and write it back with `cas` by the version read, but with the field `rev` equal to the string `"x"` (a mark not by the form of N1.5 of P/02.3: `rev` is not a decimal integer); the other fields as they were | P/02.2 (the Gemini coverage audit of P/02) |
| `@rev-max` | read the row `platform/manifest/<name>`, the mark `platform/manifest/<name>/rev` and the view `platform/manifest/<name>/canonical/1` and write each with `cas` by the version read, where `rev` = `9007199254740991` (2^53 − 1) and the other fields are byte for byte the former ones: the state as after an honest installation with such a revision (P/02.3 N1.5 `rev`); an absent one — the directive does not pass | P/02.3 (the coverage audit of P/02, B02) |
| `@row-spoil <field>` | read the row `platform/manifest/<name>` and write it back with `cas` by the version read, with the field `<field>` of `items` equal to the string `"x"` and the other fields byte for byte; the row has no such field — the directive does not pass. For `yaml`, `sha256` and `rev` the row becomes unreadable by the outcomes of [`manifest-row.outcomes.tsv`](../../02-installer/data/manifest-row.outcomes.tsv) | P/02 (P02.33) |
| `@shell-put <source>` | put next to the working copies the shell `<name>.shell.html` with the bytes of `puts/<source>.shell.html`, replacing the former one; it applies to the following installations of the line. Until then the line has no shell next to the manifest | P/02.3 (the coverage audit of P/02, B03) |
| `@file-fill <path> <bytes>` | put next to the working copies the file `<path>` (relative, without `..`) of exactly `<bytes>` bytes `x`; it applies to the following installations of the line. The subject is the size, so the file is not in `puts/` | P/02.3 (ADR-0094 B7) |
| `… @stderr ~<text>` | the tail of the cell `expect` after `<code> <rev>`, up to the end of the cell: the stderr of the last installation contains the text as UTF-8 bytes; several substrings are separated by « ~», as for `~text`. Only with `<code>` other than `0`; with `0` it is a data error | P/02 (P02.33) |

#### Rights variants

The word `variants` runs every directory `variants/<variant>/` of the first directory. A variant derives rights by meaning on a manifest catalogue outside the stand. Its directory holds the files `*.subsystem.yaml` (the catalogue of the variant) and exactly one of: `expect.tsv`, `refused`, or `check.tsv` with the directory `check/`. A directory with none or with more than one is a data error. The inventory is the physical lines of `expect.tsv` and `check.tsv` and the single line of `refused`.

**`expect.tsv`.** UTF-8, LF, cells separated by TAB, `#` lines skipped. The header is `role<TAB>action<TAB>key<TAB>expect`; then one line per probe: a role of the rights file (P/01.2 N1.1), the action `read`, `write` or `delete`, the row key, and `allow` or `deny`. For the variant the judge:

1. calls the rights derivation command of the target, `stand.rights`, with `{manifests}` — the directory of the variant, `{deployment}` = `dep` and `{file}`. A code other than `0` is a mismatch of every probe of the variant;
2. starts a fresh store instance with this file as `{rights}`;
3. for each line calls through the socket of the role: `read` — `GET /v1/get?key=<key>`, `write` — `put` with `items: {"p": "1"}`, `delete` — `delete`, without `cas` and without a guard. `allow` is only a confirmed success: for a read 200 of the form `Row` (for an absent row `{items: null, index: ""}`, P/01.1 N2), for a write and a deletion 200 `Written`. `deny` is 403 `forbidden`. A role without a socket is the same as 403 (the role is not in the file, P/01.2 N1.3). A 5xx, a transport error or another answer is an undetermined outcome: the probe is neither `allow` nor `deny` and does not match.

The order of the lines does not matter. This checks the meaning of the rights file (P/01.2 N1.3 and `never`), not its bytes: the order of patterns, `comment`, extra equivalent patterns and groups are not compared.

**`refused`.** UTF-8, LF, `#` lines skipped; exactly one other line — the `name` of the manifest of the variant whose declaration is refused. The judge calls `stand.rights` as in item 1. The code MUST be `2`, there is no file at `{file}`, and stderr names this manifest by its `name` or its file. The rest of the text is not compared. The store is not started and there are no probes.

**`check.tsv`.** UTF-8, LF, cells separated by TAB, `#` lines skipped. The header is `case<TAB>file<TAB>code`; then one line per case: `case` — `[a-z0-9_]+`, unique; `file` — `check/<case>.rights`, a rights file; `code` — `0` (the file equals the derived one by meaning) or `!0` (any code except `0`). For each line the judge calls the rights check command of the target, `stand.rights-check`, with `{manifests}` — the directory of the variant, `{deployment}` = `dep` and `{file}` — `check/<case>.rights`, and compares its code with `code`. A profile without `stand.rights-check` leaves every line `not_executed` with the reason `installer_rights_check_missing`.

### Seam adapter protocol

This is the shared acceptance normalization for a lesson's `seams.tsv`, not a product API, a new process door or a generated package. The owning [P/02 seam grammar](../../02-installer/forms/README.md#non-http-seams-exact-request-and-expectation-grammar) supplies the four TAB-separated columns `scenario`, `step`, `request`, `expect` and consecutive steps from 1. Preserve the owning form's fresh-adapter and temporary-root lifetime, whether it names a scenario or a case; the protocol does not reuse mutable fixture state across that boundary. A seam records an actual call and its effects; it does not replace an ordinary process scenario, a native vector, a stand neighbour or a reading obligation that it did not execute.

The model-visible input contains norms, forms, schemas, contracts and protocols. Vectors and scenarios remain judge-only. Every interface, payload shape, exact required encoding, field order or refusal vocabulary needed by an adapter must be defined in that normative input, not solely by a test table or fixture. The judge supplies the actual input values without an expected result; an essential definition found only in a vector/scenario is a normative gap, not permission for an adapter to inspect expectations.

#### Procedure and peer ownership

The refusal catalogue's surface `call` means a procedure; `peer` means a check owned by another lesson ([P/02 catalogue](../../02-installer/forms/README.md#refusal-catalogue), [P/04 catalogue](../../04-controller/forms/README.md#inputs-and-refusals)). Neither surface creates a new local HTTP operation. Preserve the selected row's original condition and owner: its fixed code, word, required fields, headers and response form apply only where that owner assigns them. A missing numeric projection `-` does not acquire an invented status or exit code. A source `peer` surface is distinct from the domain vector command `peer` in [domain vector commands](#domain-vector-commands) and from any implementation's choice of internal function names.

#### CALL input and observation

`CALL <name> <JSON>` consumes one JSON value after the name `[a-z][a-z0-9-]*`; the port and its normalized input/output belong to the lesson's forms README. These ports adapt ordinary implementation functions, commands or HTTP paths rather than requiring an implementation to expose that private API. The [P/02 CALL normalizations](../../02-installer/forms/README.md#call-normalization) and the seam sections of [P/03](../../03-worker/forms/README.md#seams), [P/04](../../04-controller/forms/README.md#seams), [P/05](../../05-resource/forms/README.md#seams), [P/06](../../06-console/forms/README.md#seams-and-stages), [P/08](../../08-domain/forms/README.md#seams-and-stages), [P/09](../../09-agent/forms/README.md#seams-and-stages) and [P/10](../../10-domain-console/forms/README.md#seams-and-stages) fix the fixture intervention and observations. Use only the named owner's normalization; do not infer another port's defaults, rename outcomes or impose an unassigned result envelope.

Invoke the real implementation and obtain observations from its result, rows, bytes or recorded I/O. Do not send the expectation to the implementation or return it as a prepared answer. Only source-declared fixture completion is allowed: explicit raw rows and family-read text are complete inputs, not material to repair. A panic, unrelated exception, transport failure or unexecuted call is not a normal business refusal. In particular, P/02 `command` observes zero versus nonzero only where that owner does not fix an exact code; an unexpected crash does not satisfy it.

CALL JSON expectations use the existing expectation rules in this dictionary: recursive object subset, exact empty objects, exact arrays except the expressly named unordered case, numbers compared by numeric value while booleans, strings and null remain distinct from numbers, and bindings committed only after the entire step matches. A subset expectation never cancels the owner's full result form. RUN, file/clock/parallel controls and their named stream comparisons retain the P/02 grammar; no shell is evaluated by the seam request grammar.

#### P/01 seam normalization

P/01.1 `seams.tsv` has no `CALL` rows. Its steps are HTTP requests and the directives `@clock`, `@reopen` and `@parallel`. Over the [bridge](#explicit-test-side-seam-bridge) each HTTP or directive step becomes `method: call` with one of three public tokens. No bridge field or method is added (the Architect's decision of 2026-11-08, ADR-0126 addendum (11) item 4).

| `name` | Step | `input` | Observation |
|---|---|---|---|
| `store-http` | `GET` or `POST` | closed object: required `method` and `target` (the path with the query, as written in the step), optional `body` (the text of the body of the step as one string, absent when the step has none) | `{kind: "value", value: {"status": <integer>, "body": <string>}}`: the status and the whole response body |
| `clock` | `@clock +N` or `@clock -N` | closed object `{"shift": <string>}`: the shift in the same syntax as the step | `{kind: "value", value: {}}` |
| `reopen` | `@reopen` | `{}` | `{kind: "value", value: {}}` |

`store-http` reaches the ordinary request handling of the store; it is not a new door. `clock` moves the controlled clock of the store by N seconds, cumulatively; the clock starts at 2000000000 and the implementation chooses how it is controlled. `reopen` closes the store and opens it again on the same data directory with the same clock. An HTTP step's `<code> <JSON body>` is compared as in the acceptance of chapter 1.1, and a directive's `ok` matches an empty object value. `@parallel K` follows the grammar of P/02 and the exception in the bridge below. The `CALL` ports of P/01.3 are in its [acceptance README](../../01-store/acceptance/3/README.md).

#### Explicit test-side seam bridge

This newly selected bridge is a separate test-side contract. It is not an existing `stand.call` or `adapters.call` key, the native vector envelope or a mandatory product API. The separate descriptor is named `SEAM_BRIDGE.json`; the judge supplies its path explicitly for the selected case, with no search in the working directory or profile. No guessed command, profile format 2 field, assembly format 1 field, platform route or working flag is introduced. The actual receiver identity and invocation belong to the run evidence. The current Runner without this receiver has `MissingBinding`/`NOTEXEC`; publishing the format does not implement or activate it.

The descriptor is a closed JSON object with exactly required `format` (integer `1`), `source_pin` (the full Source SHA selected for the case), `scope` (a nonempty exact string: the id of a target of the registry, optionally followed by `#` and the name of one of its scenarios or cases) and `bridge`. `bridge` is closed and has required `identity` and `invoke`, using the exact file-identity and argument-vector forms in D7 below. This test-side Source identity is not an alias for the profile's `spec_version`, which retains its published export-Git-SHA meaning; the actual Source/export provenance is recorded without a new equality/inequality check on the two strings. There is no universal roots object: setup, paths and fresh process/state boundaries remain those of the existing Source owner.

Each sequential UTF-8 JSONL request is a closed object with exactly these required fields:

| Field | Required value |
|---|---|
| `format` | Integer `1`, not a boolean. |
| `scope` | The descriptor's exact scope. |
| `request` | A nonempty identifier unique within this bridge process. |
| `method` | `call` or `peer`, only as assigned by the selected public Source binding. |
| `name` | The exact public normalized port/check token selected in that binding. |
| `input` | Its once-decoded Source-owned JSON input, not the expected result or a checker answer. Source-declared controlled dependency replies remain inputs; do not manufacture them from the expectation. |

The judge owns the full per-request normalization context: full Source pin, Source-relative table and its raw SHA256, canonical owner, actual original id cells and scenario/step, physical source line, exact normalized port/peer binding and its exact public normalizer reference. It fixes this context from immutable Source before dispatch and associates it with scope/request. It is not inferred from a provider response, a short port name or scope spelling. Source/table/row/selector/normalizer/evidence/expectation metadata is not sent to the provider. The six-field request does not acquire such fields. The [source-cell wrapper](../contracts/source-cells.md), where declared, is decoded exactly once before the existing seam grammar; nested Source input is not repaired or numerically rewritten.

The judge must mechanically prevent adapter processes from reading expectation-bearing vector/scenario files; merely omitting expectation fields from the frame is not that isolation. It owns a negative control for every selected target using the same adapter over an intentionally broken product, and a green result over that broken subject fails the checking instrument rather than qualifying the product. Actual isolation and controls must be demonstrated; the current receiver is not assumed to enforce them. Adapter code is read independently before a conclusion of generation proved. Model-facing reports reveal only the case name, normative anchor and mismatch class, never the expected answer. Full raw case evidence and expectation comparison remain in the judge-private record; runtime adapters receive only their declared input frame, not that record.

`CALL <name> <JSON>` selects `call`, its exact public token and once-decoded input JSON. Catalogue `call` and `peer` rows can dispatch only when Source actually supplies the input, target and named binding. `peer` invokes the other owner's existing public check/door; it creates no local HTTP API, peer port or response shape. Native domain vector `peer` remains distinct. Unknown names or missing peer input/target/public normalizer remain exact `MissingBinding`/`NOTEXEC`, not an inferred call or a canned result.

The bridge returns one flushed JSONL record per request. It is closed and has exactly required `format`, `scope`, `request`, `observation`: integer `format: 1`, exact matching scope/request, and exactly one of these closed observation forms. There is no seam-response sequence field.

| Form | Meaning and restriction |
|---|---|
| `{kind: "value", value: <JSON>}` | The actual Source-normalized strict JSON result, including explicit null. Numbers are compared by numeric value; booleans are not numeric aliases. A Source string/marker stays a value unless that owner expressly assigns another outcome. |
| `{kind: "absence"}` | Absence/omission only where the selected Source owner explicitly assigns it. Never coerce null, an empty value, an unknown read or a string marker into absence. |
| `{kind: "native", exit_code: <integer>, stdout_b64: <string>, stderr_b64: <string>}` | An actual normal owner-declared native process exit in `0..255` and exact raw streams encoded as canonical standard RFC 4648 Base64; empty bytes use the empty string. Only a Source-assigned native-exit/raw-stream surface permits this form. This is the transport's native-process range, not a resource/QoS ceiling or a new platform refusal. |

These tags are transport metadata, not product Faults or new business outcome words. A normal native exit belongs inside the observation only where Source assigns it. The bridge's own early EOF, nonzero exit, signal, crash or protocol mismatch is an instrumentation error, never a platform refusal. No uniform status, body, Fault kind or broad refusal is invented. Apply the existing selected owner's status/word/field/header/result normalization and common comparison to the actual observation; preserve exact empty objects, arrays by length/order unless Source expressly assigns an unordered comparison, numeric-value comparison distinct from booleans/strings/null, and bindings only after the whole step matches.

There is one outstanding unique request and one correlated observation, no greeting, unsolicited frame, pipelining or extra record. One exception, for `@parallel K` of P/01 and P/02: the judge sends K frames in a row without waiting, the adapter executes them concurrently over the same instance and answers K records in any order, matched by the existing `request` field; no field is added, and the next step starts only after all K answers. Outside `@parallel` the rule above stands (the Architect's decision of 2026-11-08, ADR-0126 addendum (11) item 4). Both directions are strict UTF-8 JSONL, one physical LF per record and a flush after the response; diagnostics go to stderr. Integer fields of the bridge and D7 frames/descriptors use JSON integer tokens, not booleans, fractional or exponent notation. This concerns transport framing only; nested Source JSON retains its own numeric rules. Outer frames reject duplicate fields, BOM and non-JSON numbers. Malformed outer records are instrumentation errors, not platform refusals. The process/state is fresh at the Source-declared scenario/case boundary; setup and allowed earlier steps inside that boundary keep their owning semantics. Selected RUN, `@file`, `@read`, `@parallel` or `@clock` dispatch that is not actually supplied remains missing/unexecuted, not a skipped-prefix PASS.

At a completed boundary the caller closes stdin and the bridge exits normally with zero, leaving no background service using its test state. Record actual exit, signal, timeout and cleanup. A deliberate signal to the tested target is an observation only where Source assigns it; a signal killing the bridge cannot substitute for it. No universal timeout, line-size or resource ceiling is assigned here. Parser/transport compatibility is not candidate/native qualification or physical evidence that requires D7.

#### D7 test-side evidence bindings

This is a newly selected test-side contract for clock, storage, progress and controlled-fault bindings. It is not a platform route or working flag, and it adds no field to profile format 2 or assembly format 1. A descriptor or a provider reply is not qualification. The [production owner](../../01-store/spec/production-acceptance.md#evidence-and-outcomes) still distinguishes missing bindings, instrumentation errors and measured normative outcomes. The current Runner receiver and actual qualified providers must be identified separately; publishing this contract does not supply or execute them.

The descriptor is a separate test input. Its closed top-level fields are required `format` (the integer `1`), `source_pin` (the full 40-hex Source commit selected for the case), `scope` (a nonempty exact string for the isolated case: the id of a target of the registry, optionally followed by `#` and the name of one of its scenarios or cases) and `providers` (a mapping using only `clock`, `storage`, `progress`, `fault`). The profile's `spec_version` keeps its existing published meaning; record the case's actual Source/export provenance without inferring equality or difference from field names alone. Only capabilities required by the selected case must have entries; a required absent entry leaves that dependent check `MissingBinding`/`NOTEXEC`.

Each provider entry is a closed object with these required fields:

| Field | Type and binding |
|---|---|
| `identity` | A closed object with required `id` (nonempty string), `executable` and `artifacts`; optional `provenance_ref` is an exact published reference string. `executable` is a closed object with an absolute `path` and a 64-lowercase-hex `sha256` of those file bytes. `artifacts` is an array of objects with the same `path`/`sha256` form; an empty array is allowed. Name every script, interpreter, configuration or build-result file relevant to the provider's identified behavior. |
| `invoke` | A closed object with required `argv` (a nonempty array of strings) and `cwd` (an absolute directory path). `argv[0]` is absolute and equals `identity.executable.path`. The judge launches that argument vector without inserting a shell, PATH discovery, globbing or substitutions. An explicitly named interpreter is part of the measured invocation. |
| `observer_ref` | A nonempty opaque identifier resolved only in the judge's protected observer registry. The provider cannot nominate replacement observer code. |
| `qualification_ref` | A nonempty opaque identifier resolved only in the judge's protected independent-qualification registry. An arbitrary file path, provider boolean or self-written receipt is not qualification. |

The judge measures the launched executable/artifacts and records the actual process/runtime-executable identity and scope. It checks a trusted qualification receipt against that identity, Source, capability, scope, observer and declared claim, including the actual negative controls. Missing invocation, permission, observer, receipt or public case-payload contract is a missing binding. A known wrong/stale identity or contradictory active instrument is an instrumentation error. A declaration never grants write access to either protected registry.

A provider process belongs to one declared capability and isolated case/scope. It receives sequential UTF-8 JSONL requests on stdin and emits one flushed UTF-8 JSONL record on stdout for each request; stderr is diagnostic text. There is no greeting, unsolicited record or pipelining. Outer JSON has no duplicate fields, non-JSON numbers or BOM. A single physical LF terminates each record. Actual process exit, signal and outer timeout remain recorded evidence, not a normalized platform refusal. The case's declared finite invocation/observation budget remains separate; this protocol assigns no universal timeout or size ceiling.

| Request field | Required type |
|---|---|
| `format` | Integer `1`. |
| `scope` | The descriptor's exact nonempty scope string. |
| `request` | A nonempty identifier, unique within this provider process. |
| `capability` | The process's declared `clock`, `storage`, `progress` or `fault`; it cannot switch capability. |
| `operation` | `describe`, `activate`, `sample` or `deactivate`. |
| `payload` | The JSON value defined by a selected model-visible norm, form, schema, contract or protocol for this capability; the judge supplies case values without expected answers. A test-only vector/scenario is not a payload definition. |

The request object is closed. The response is also closed and has exactly `format`, `scope`, `request`, `seq`, `event`, `payload`. `format` is the integer `1`; `scope` and `request` exactly match the request. `seq` is a nonnegative integer starting at `0` for the first record and increasing by exactly 1 for every later record without reset, gap or reuse. `event` is `identity` for `describe`, `activation` for `activate`, `observation` for `sample`, and `deactivation` for `deactivate`. `payload` has the selected model-visible normative capability shape, not a shape defined solely by a private case or vector/scenario. A `describe` identity payload equals the descriptor's identity object; the judge still checks its actual identity independently. Records carry observations rather than a qualification or PASS verdict; a legitimate Source result word inside an observation does not by itself become a verdict.

The first request is `describe`. The provider is then inactive: `activate` is allowed only while inactive; `sample` and `deactivate` only while active. Deactivation returns it to inactive; a later activation cycle uses new request identifiers and continues the same sequence. Scope and provider identity do not change during the process. Normal closure is stdin EOF while inactive, followed by a normal zero exit. Missing or extra records, an early EOF, a crash, signal, nonzero exit or malformed record cannot satisfy an expected business refusal.

Transport order is not effect proof. For each of the four capabilities an independent observer must correlate the activation request, actual activation at the selected boundary, the actual target operation/effect/observation and actual deactivation. It rejects stale, cross-scope, cross-operation, wrong-phase or reversed-order evidence. A configured hook, `Config.Now`, `@clock`, provider ACK/counter, EIO text, manager kill, Raft Barrier or Shutdown alone does not establish the claimed physical scope.

| Capability | Public case binding and independent qualification | Required negative controls |
|---|---|---|
| `clock` | Name the observed or controlled clock domain/unit, the actual consuming boundary, independent monotonic baseline and calibration. Preserve Source wall-stamp/monotonic-deadline distinctions. | Self-report-only or unactivated control, wrong domain, stale scope and reversed timing must be detected. No invented skew allowance. |
| `storage` | Name actual file/object identity, medium/durability mode and observed effect/publication/barrier phases with before/after/qualified-reopen state. A process restart or library return does not establish physical durability. | No-op barrier/fault, wrong object or phase, false counters and stale reopened data must be detected. |
| `progress` | Name the actual operation, pin/output/sink/latch/cancel/release or other Source-owned boundary, plus independent progress/resource observations for the declared workload/budget. Activate the latch before scoring blocking; startup delay is not a sink stall. | Frozen/no-op/cross-operation activity, an unactivated latch and unobserved or missing release/progress evidence must be detected. |
| `fault` | Name the exact published Source phase, target and supported fault model; independently observe activation, effect and order. Preserve proven no-effect versus unknown or whole-published recoverable outcomes. | Inactive/no-op/wrong-phase/stale activation and a claimed effect with no independent witness must be detected. No new Fault class or universal rollback promise. |

The payloads of the four capabilities are the form [`forms/d7-payload.schema.json`](forms/d7-payload.schema.json). An `activate` request carries one object of its capability. Its fixed part is the case binding: for `clock` the mode `observe` or `control` and the consuming wall-clock domains named by `-id`; for `storage` the object, the medium, the phases and the states observed; for `progress` the operation, its Source boundaries, the resources and the latch; for `fault` the phase and the fault model. The judge sets `targets` (member, store directory and process) and, in the mode `control`, the offset of each domain at each activation. The requests `describe`, `sample` and `deactivate` carry the empty object. The records `activation` and `deactivation` carry the members whose boundary actually changed and the monotonic reading of the provider; an `observation` carries the observation of its capability. An activation holds until its deactivation: a `fault` is injected at every crossing of its phase while it is active, and a `clock` in the mode `observe` shifts nothing. The words of the form are closed; a payload outside it is a malformed request or record. Its fields are observations of the provider and qualify nothing: the observer of the binding checks them independently. The form sets no numeric value.

For the bindings of the target `P/01/production` the words of the payload mean the following. The boundary `admission_time` is the wall clock of the daemon process that P/01.1 N3 «Admission time» reads at admission: the provider observes this clock domain of the process, and the admission time that the daemon stores is judged by the public outcomes of the case, not by the provider. The resource `heap` is the resident anonymous memory of the process (`RssAnon` of `/proc/<pid>/status`), and `memory` is its resident set (`VmRSS`); a heap figure of a language runtime is no resource of the form. With the latch `sink` the provider is the reader of the output, and `cancel` is its deactivation: the provider closes the sink at `deactivate`, the `monotonic_ns` of the deactivation record is that moment, and no observation carries `cancel`. The phase `recover_mark` names no file: the mark is the first changing step of `recover` in `-dir` (P/01.3 R021), and the point of the fault is the first change of `-dir` after the first top-level entry that `recover` completes, so neither the payload nor the invocation carries a name of the mark. The phase `copy_after_headers` is the end of the stream as the client receives it after the complete header block of a `200`, made between the daemon and the client: it gives the half of `RUN-H03` that the CLI judges. The half of the daemon after `200`, only an incomplete close and no second fault, is judged on its own stream under the cancellation, the stalled sink and the stop that the judge makes; a failure inside the daemon has no binding.

Actual activated positive and negative controls qualify only their declared observer/provider claim; an unexecuted list of controls qualifies nothing. The descriptor and common frame do not invent a missing actual provider. If the selected capability has no case binding by the payload form, or its actual invocation/qualification is absent, retain `MissingBinding`/`NOTEXEC`. Retain the owner's current approved budgets and unknown inputs; add no numerical ceiling here.

### Stand-in worker of the pass of the second kind

The directives of the [stand of the pass of the second kind](pass/README.md) (ADR-0094 B1). The runner executes them (the README of the pass stand, section «Executability»). The runner plays the worker: so a scenario keeps a request open and sees what reached the worker. In the directives `<cluster>` is present on the domain stand; on the console stand it is absent.

| Form | Meaning | Lesson |
|---|---|---|
| `@pass-worker [<cluster>] <sub> <name> [kit=<leaf>]` | the runner listens on a door on the loopback (without `kit` the `url` is `http://127.0.0.1:<port>`; with `kit` — https with the server leaf `<leaf>` of the kits of `@tls-setup`: the host of the `url` is the server name of the kit and the chain is the leaf and the `ca.pem` of the cluster of the leaf; a cluster instead of the leaf name — the leaf `<cluster>-<sub>worker`); when a worker of the same name is replaced, the runner waits until a probe `GET /<sub>/api/x` through the console comes to the new listener: the `url` of the issue is not named; it writes and refreshes the object `<sub>/heartbeats/<name>` with `worker`, the `url` of this door, like a live worker with a door; it keeps an accepted request open; the expectation `ok` — the console sees it alive. The previous worker `<name>` is stopped | B1 |
| `@pass-open <label> <door> <request>` | a request to the console in the background, under a label; a `POST` without `Idempotency-Key` gets the key by the rule `@key`; waits until the stand-in worker accepts it. The expectation `ok <JSON>` — the accepted request by subset: `{method, path, query, body, ticket, headers}`, `ticket` — the value of `X-W2C-Pass-Ticket`, the absence of the header — `@absent`; it did not get through — the answer to the client, the form `<code> <JSON>` | B1 |
| `@pass-answer <label> <code> <Content-Type\|-> [<body>]` | the worker answers the request of the label: the status `<code>`, `Connection: close`, `Content-Length` except for 204, `Content-Type` unless `-`; the expectation — the answer to the client, the forms of the dictionary | B1 |
| `@pass-chunk <label> <text>` | the worker sends a part of the stream: the status 200, `Content-Type: text/event-stream`, chunked encoding, each part is the text followed by an empty line; the expectation `<code> ~<text>` — the client has already received it, the answer is still open | B1 |
| `@pass-result <label>` | the answer to the client without an action of the worker: the worker side is silent; the expectation — the forms of the dictionary | B1 |
| `@pass-abort <label>` | the client breaks the connection; the expectation `ok` — the worker saw the close | B1 |
| `@pass-closed <label>` | the console closed the connection of the client no later than `PASS_TICKET_CHECK` + 30 s; the expectation `ok` | B1 |
| `@pass-fill <cluster> <sub>` | open requests `GET /<sub>/api/x` to the route until the console answers 503 `busy`; they live until the end of the scenario; the expectation `ok` | B1 |
| `@pass-seen <name>` | how many requests the stand-in worker accepted, without the probes of a worker replacement; the expectation `ok {"requests": N}` | B1 |
| `@pass-call <client> <request>` | one probe of the door `callback <cluster>`: the callback listener, the address — `X-W2C-Pass-Console` of the last `@pass-open`, the port — `{cport}`; the client — a leaf of `stand.json` or `null`, the outcome — the closed form of `@tls`, with the substitutions `$name` | B1 |
| `@pass-step <label> [<name>]` | wait for a step call of an operation on the stand-in worker (the route `door.pass.operations.step`, [P/06.9](../../06-console/spec/06.9-console.norms.md) N2; a call is recognised by its path: without its leading and trailing `/` the path equals the route, the query does not count) and hold it: no longer than 40 s (`OPS_STEP_WAIT` + 2 × `OPS_TICK`). The expectation `ok <JSON>` — the accepted call by subset `{method, path, ticket, headers, id, index, body, secret, expected, opcount}`, `secret` without a value — `@absent`. `@pass-open` does not take step calls, `@pass-seen` counts everything accepted | ADR-0095 |
| `@pass-step-answer <label> <code> <Content-Type\|-> [<body>]` | answer the step call; the expectation `ok`. The console does not read the answer body | ADR-0095 |
| `@pass-step-none <name> <s>` | no step call came within the term; the term counts as a sleep: the lesson README names the reason; the expectation `ok` | ADR-0095 |
| `@pass-step-drop <label>` | break off the step call without an answer: a lost answer, `OPS_STEP_TRIES`; the expectation `ok` | ADR-0095 |
| `@stream-open <label> <door> <request>` | a GET stream through the door `member <cluster> console` or `console2` from the current `@person`, only on the stand without a kit, `@header Last-Event-ID` is admissible; the expectation — `<code>` or the class `2xx` of the answer headers | V/11 |
| `@stream-wait <label> <s>` | the first new message is judged: a JSON subset from `data:`, it did not match — FAIL of the step: otherwise the step would not tell a skipped message apart; a line `id:` without `data:` is not a message, it is skipped; messages are blocks separated by an empty line (CRLF reads as LF), the `data:` lines of a block are joined by LF after one space after the colon is removed, a block without its final empty line is not yet a message, a `data:` text that is not JSON does not match; `$name` is bound as in the dictionary. The expectation `ok <JSON>`. The term ran out or the stream closed before a message — FAIL of the step | V/11 |
| `@stream-none <label> <s> ~<text>` | within the term there was no message with this text (the messages seen during the term count as read: a following `@stream-wait` judges only later ones); the stream is closed — a mismatch: the silence of a closed stream proves nothing; the term counts as a sleep: the lesson README names the reason; the expectation `ok` | V/11 |
| `@stream-close <label>` | close the stream; the expectation `ok` | V/11 |

**Terms of the stand-in worker.**

| What | Term |
|---|---|
| `@pass-open`: the stand-in worker accepts the request | 30 s |
| `@pass-worker`: the console sees the worker alive | 30 s |
| the heartbeat of the stand-in worker | every 5 s |
| `@pass-answer`, `@pass-result`: the answer to the client | read within 120 s, judged within 180 s |
| `@pass-chunk`, `@pass-abort`, `@stream-open`, the answer to a request of `@pass-fill` | 30 s |
| `@pass-fill` | at most 4096 requests; the limit reached without `503` `busy` is a failure of the stand, not an outcome of the implementation |
| `@together`, each side | 150 s |
| `@person`: a new login | when less than 60 s of the token remain |

The substitution `{cport}` is the port of the callback listener of the console: the stand sets `CONSOLE_CALL_PORT={cport}` for a console with a kit (the environment file contract). The console profile declares `keys.pass_stand: 1`; without it the checks of this stand are not executed (not GREEN). Without a kit there is no substitution: the listener is not opened.

The door `socket [<cluster>[#<n>]] <role>` — a request to the worker role socket to the console `<PLATFORM_DIR>/run/console/<role>.sock`, in the same request form ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) N1.5); `#<n>` — the copy of the console `console#<n>`, without a number — the first.

### Store group stand

A raft group of several store daemons on one machine of the stand — the acceptance of [chapter 1.3](../../01-store/acceptance/3/README.md)
(sc. 07, 17, 18, 25–29, 31). The properties of the group — the composition, the elections, a restart, a door without a vote, `recover`, `import` into the group — the stand
sees from outside; drills on a real cluster ([system acceptance](system/README.md)) no longer replace this
(work rules (for people) § 4; the plan `automatic group scenarios plan (2026-10-30, for people)`, accepted by the Architect on
2026-10-30). The norms are P/01.3 N1.3 (`group`, `door`, `floor`, `import`, `leader_wait`, `repeat`), N1.6, N3
«recover the store»; the section introduces no new norms.

- **Members** — by the name `<id>`: the voters `s1`…`s5`, the doors without a vote `d1`, `d2`. The server name of the leaf of a member is its `<id>`
  (the leaf `configstore.<id>` for a voter, `configstore-door.<id>` for a door; the role certificate contract `cert`); the addresses are the loopback
  `127.0.0.1`, the ports are handed out by the runner (free ones on the loopback; there are no addresses in the kit description): `{raft@<id>}`, `{api@<id>}` —
  substitutions in flags, requests and probes. A member learns its partners as in the norm: a joining one — by the flag `-join {api@<id>}`
  (P/01.3 N1.3 `join`), a door — by `-voters`, a restart — from its `member.json`; the runner does not pass a list of peers. The daemon
  checks the name of a peer against the `<id>` of the participant, not against the host of the address (the address is the loopback for all).
- **Kits** — the description `inputs/group.json` of the acceptance of chapter 1.3: one CA of the group, a leaf for each member; the layout — the contract
  `kit` (`ca.pem`, `<role>/server.pem`, `<role>/server.key`), `revoked` is empty, there is no `ca.next.pem`.
- **Store build — the feature of the implementation profile `keys.store_build`**: `raft` — a build with a group, the scenarios of the stand
  are executed; `box` — the store of a box without raft, lawful per P/01.3 N1.3 `box` (one voter; `-group-size 3`/`5`,
  `-join`, `-door` — a start refusal, code 2): the scenarios of the group stand are not_applicable, they do not enter the result and are not red, the lesson
  is credited without them; there is no feature or another value — the scenarios are not executed (not_executed, as without `keys.tls_stand`; not
  GREEN). The refusals of the build `box` are checked by sc. 04/16 of the stand store and by reading (P/01.3-01); the group stand does not judge it
  (the Architect's decision of 2026-10-30).
- **Member launch** — the store command of «Stand» (the same as for the stand store, with the speed flag of the stand if there is one), with the environment `BOX_ID=<id>`, `SERVER_NAME=<id>`, `PLATFORM_DIR={data}/<id>` (on the three-server stand — the `PLATFORM_DIR` of its server), and
  the member's substitutions: `{data}` is its `PLATFORM_DIR`, `{rundir}` is `{data}/run`, `{socket}` is `admin.sock` there, and `{rights}`. The template carries them in its own flags `-dir {data}/configstore`, `-sockets {rundir}`, `-rights {rights}`, `-max-body {body_limit}`, `-max-value {row_ceiling}` ([substitutions](PROFILE.md#substitutions)), so the store directory of the member is `{data}/configstore` of its `PLATFORM_DIR`. The runner appends only these flags: `-id <id>`, `-tls <kit dir>`,
  `-api {api@<id>}`, `-tuning lan`; for a voter also `-raft {raft@<id>}` (the address of the proxy of the runner,
  which the member names to its partners) and `-raft-bind <own port>` (where it listens; P/01.3 N1.3 «Daemon flags»). The other flags — from the line
  of the directive as written (`-bootstrap`, `-join`, `-group-size`, `-force`, `-door`, `-voters`). The template holds none of the appended flags, and the speed flag of the stand is none of them: a repeated flag is a start refusal (P/01.3 N1.3; the Architect's answer on P01.86).
- **Member doors**: `store@<id> <request>` — the door of P/01.1 through the socket of the role of the scenario of the member (the role is named by the chapter README, `@as`
  changes it); `admin@<id> <request>` — through its `admin.sock` (not forwarded: the write is at the leader).
- **Boundaries**: between scenarios the runner stops all members and deletes their directories; the kits — per scenario.

| Form | Meaning | Lesson |
|---|---|---|
| `@group-setup <description path>` | as the first step of a scenario: the runner issues the kits per the description (the path — from the acceptance directory of the lesson) by its own clock; the expectation `ok`; a scenario with this step the runner plans by `keys.store_build` (above): `raft` — executes it, `box` — not_applicable, otherwise — not_executed | P/01.3 (2026-10-30) |
| `@store-start <id> [kit=<id2>] [<flags>…]` | start the member `<id>` (the flags above); `kit=<id2>` — the member `<id>` receives the kit of the member `<id2>` (its leaf and key) instead of its own: `-id <id>`, and the leaf names the server `<id2>` (the check «`-id` is the server of its own leaf», C01-DOOR-ID-CN-01); the expectation: `ok` — `admin@<id> GET /v1/status` answers 200 no later than 20 s; `@exit 2` — the process exited with code 2 no later than 10 s (a start refusal, P/01.3 N1.3 `refuse_start`) | P/01.3 (2026-10-30) |
| `@sigterm store@<id>` / `@sigkill store@<id>` | stop the member; the data directory remains; the expectation `ok` — the process exited | P/01.3 (2026-10-30) |
| `@restart store@<id>` | start a stopped member with the same command, with the same flags, directory and kit (a restart is not a join: `member.json`, P/01.3 N1.3 `join`); the expectation — as for `@store-start` | P/01.3 (2026-10-30) |
| `@cut store@<id>` / `@mend store@<id>` | the proxy of the runner on the raft address of the voter `<id>` breaks the live incoming connections and does not accept new ones / lets them through again; the outgoing connections of the member go to the others directly (on one machine they cannot be cut) — the member does not receive the journal entries and the heartbeats of the leader; `-api` is not cut; the expectation `ok` — the proxy has switched | P/01.3 (the coverage audit of P/01, 2026-10-30) |
| `@store-op <id> <operation> [<arguments>…]` | an operator operation of P/01.3 N1.3 `admin_ops` in the words of the command line, as in the norm (`admit s3`, `import --from inputs/copy-ok.jsonl -index-base 7`, `recover -peers … -isolated`), by the command `store-op` of «Stand» — a template with `{socket}` (the `admin.sock` of the member), `{dir}` (its `-dir`, the `configstore` directory of its `PLATFORM_DIR`), `{id}`, `{tls}` (the kit directory of the member `<id>`, even when it was started with `kit=<id2>`) and `{args}`; for `recover` the member is stopped by a step of the scenario (a live member is a data error), the command works with its `-dir`, `-id` (N3 «recover» step 1); `{raft@…}`, `{api@…}` are substituted, the path `inputs/…` — from the acceptance directory of the lesson; the expectation: `ok` — code 0; `refused` — code ≠ 0; the output is not compared | P/01.3 (2026-10-30) |
| `@tls <probe path>` with the door `raft@<id>` | a probe to the raft port of the voter (its real port, not the proxy of `@cut`): the input `{door: "raft@<id>", client: "<id2>", request: null}` — only a handshake, there is no request; the client presents the leaf of the member `<id2>`; the outcome — the closed form of the README `tls/` (`handshake: alert` — `http: null`) | P/01.3 N1.6 `raft` (C01-RAFT-DOOR-LEAF-01) |
| `@tls <probe path>` with the door `api@<id>` | a probe to the `-api` of the member: the input `{door: "api@<id>", client: "<id2>", request}` — the client presents the leaf of the member `<id2>` of the description `group.json`, checks the server by the CA of the group and `<id>`; the outcome — the closed form of the README `tls/`; the role forwarding header in `request` is a designation, the name is substituted from the description of the implementation by the same profile key as `X-Configstore-Role` in the acceptance of chapter 1.2 sc. 08 | P/01.3 (2026-10-30) |

### Three-server cluster stand

Three platform servers on one machine of the stand — sc. 05 of the [system acceptance](system/README.md). A server failure, the move of units and
the return the stand sees from outside, so a drill on a real cluster no longer replaces them (work rules (for people) § 4; stage 2 of the plan
`automatic group scenarios plan (2026-10-30, for people)`). The norms are P/04 N1.4a, N3 «pull the power», P/05 N1.4, P/01.3 N1.3, P/02.4 N3
«server start»; the section introduces no new norms. The section continues «Store group stand» and the form `on <server>` of the dictionary.

- **Servers** — `srv-a`, `srv-b`, `srv-c`. Each has its own `SERVER_NAME`, `BOX_ID` and `PLATFORM_DIR` — as for `on <server>`
  of the dictionary (`{data}` for `srv-a`, `{data}/servers/<server>` for the others); this directory is the volume of the server: its objects, event root and
  presence locks. Each has its own resource with its own `{rport}`. The key ring is one (`SECRETS_KEY`).
- **Store** — a group of three voters per «Store group stand»; the `<id>` of a member is the name of the server. Kits — the description
  [`system/inputs/cluster.json`](system/inputs/cluster.json) (`@group-setup`); the `-dir` of a member is `<PLATFORM_DIR>/configstore`,
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
| `@server-start <name>` | bring up a server: the store member, then the resource. The flags of the member — as for `@store-start`, the runner chooses the join by the order of the directives in the scenario (the first directive names the console server `srv-a`; a fourth directive is a data error): the first — `-bootstrap -group-size 3`, the second — `-join {api@<first>} -group-size 3 -force`, the third — `-join {api@<first>} -group-size 3` (assembly 1→2→3, C01-GROUP-BOOTSTRAP-EVEN-01). On the first server, after the member is ready, the runner sets up the manifests (`manifest-put`, the order — «Manifests» above) through its `admin.sock` and starts the console, then the resource. The role files of the resource — as for `@start resource on <server>`. The expectation `ok` — `admin@<name> GET /v1/status` answers 200 no later than 20 s, then the role sockets of the member accept a connection no later than 30 s, then the resource port listens and the row `platform/doors/<name>` exists no later than 20 s | system (2026-10-31) |
| `@power-pull <name>` | pull the power: the proxy of the runner on the raft address of the member breaks the live connections and does not accept new ones (like `@cut store@<id>`), then the runner immediately sends SIGKILL to all processes of the server — the member, the resource, the workers; it does not touch the directories. There is no proxy on the resource door, because the resource names the address of its door itself: after SIGKILL its port is closed. The expectation `ok` — all processes exited; this moment is `t = 0` of the drill. `<name>` — a server that is up, not the server of the console and the controllers; otherwise a data error when the step is executed | system (2026-10-31) |
| `@power-back <name>` | return the power: the same directories, ports, kit. The proxy lets through again; the member is started with the previous command and the previous flags without `-bootstrap`, `-join`, `-force`: it takes its partners from `member.json` (P/01.3 N1.3 `join`; P/02.4 N3 «server start» step 1), and only so the steps below prove a restart without a join. Then the resource — with the same command, with the same `{rport}`. The directive does not start workers; they are returned by the steps `@start worker … on <name>`. The expectation — as for `@server-start` | system (2026-10-31) |
| `@restart resource#<name>` | SIGTERM to the resource of the server, wait for the exit, start it with the same command with the same `{rport}` and directory; the expectation `ok` — the port listens and the door row exists no later than 20 s. The first pass goes at the start (P/05 N1.4 `pass`), so the scenario gets a mirror pass without waiting 600 s | system (2026-10-31) |
| `@append event on <name> <tree>/<unit>/e<epoch> <text>` | like `@append event` of the dictionary, but into the event root of the server `<name>` (`<PLATFORM_DIR>/events`) | system (2026-10-31) |
| `@append event-closed on <name> <tree>/<unit>/e<epoch> <text>` | like the row above, but into the bucket of the previous window: `start = floor(now / 600) × 600 − 600`; such a bucket is already closed (the event journal contract `span`: closed when end ≤ now). `{now}` in the text is `start + 300`, because the `t` of the line chooses the bucket. After `ok` the runner binds `$closed` — the path of the bucket `<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`. The real closing cannot be waited for: up to 600 s per window and up to 600 s more for the mirror pass | system (2026-10-31) |
| door `resource#<name> <request>` | the door of the resource of the server `<name>` on its `{rport}` with an admissible identity; `#` here is the name of the server, not the number of a copy as in `@sigkill resource#1` | system (2026-10-31) |
| door `admin@<name> <request>` | the door of a member per «Store group stand»; sc. 05 reads and writes through it, because it needs the rows of all families | P/01.3 (2026-10-30) |

### Domain stand

The stand of several clusters: the acceptances of the chapters of lesson 8 ([`08-domain/acceptance/`](../../08-domain/acceptance/)), of the chapters 6.7, 9, 10 and
of the [TLS stand](tls/README.md); the domain vectors not yet moved into packages are also here.
Moved as it is from «Dictionary of directives and doors of M11» of the acceptance README of M11/01 (the directory was removed by the move of lesson 8) (stage B,
lesson 8; the move plan of lesson 8, V5). The section relies on «Stand» and «Dictionary of directives and doors» above; the column «Lesson» —
as there (`M11/N` — the lesson of M11 that introduced the form). The acceptance README of a chapter names its own preparation; the common preparation
of the clusters `hold`, `m1`, `m2` is «Preparation of each scenario» of the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md)
(«Stand»).

#### Domain vector commands

| Door or form | Meaning | Lesson |
|---|---|---|
| `view <entry path>` | the command `view` of the implementation: a template with `{input}` — the path of the file with the input; the input — the column `input` of the package [`08-domain/vectors/view`](../../08-domain/vectors/view/README.md) (the form `ViewInput`), stdout — `ViewOutput` ([OpenAPI P/08](../../08-domain/spec/08-domain.api.openapi.yaml)); code 0 — computed, `@exit 2` — the input is not in form (review analysis of stage B 8–10, № 22: M-1) | M11/1 |
| `keys <entry path>`, `token <entry path>`, `seal <entry path>`, `seal-round <entry path>` | the commands of chapter P/08.2 of the implementation: a template with `{input}`; the input and stdout — the forms of [P/08.2 N5](../../08-domain/spec/08.2-domain.norms.md); code 0 — computed, including a refusal by a word (`{"result": "refused", "reason": …}`), 2 — the input is not in form | M11/2 |
| `ok <JSON>` in an expectation | the exit code 0 and stdout is JSON, which is compared by a subset of fields (the dictionary above) | M11/1 |
| `agent-sig`, `seal-member`, `seal-member-round`, `accept` `<entry path>` | commands of the implementation, like the doors of M11/2 ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) «Implementation decides» item 1): the forms of the input and the output — the contracts of the [agent signature](../contracts/agent-signature.md), the [domain envelopes](../contracts/domain-envelopes.md) and the [report admission](../contracts/accept.md) (review analysis of stage B 8–10, № 6, № 22: M-1) | M11/3 |
| `assemble`, `issue` `<entry path>` | the commands of M11/5 and M11/7: the forms — N5 of their norms (now [P/08.5 N5](../../08-domain/spec/08.5-domain.norms.md) and [P/08.7 N5](../../08-domain/spec/08.7-domain.norms.md)) | M11/5, M11/7 |
| `peer`, `may`, `record`, `follow`, `ask-sig`, `resolve`, `alarms` `<entry path>` | the commands of M11/8–11: a template with `{input}`; the forms of the input and the output — N5 of their norms (`may` — now [P/08.4 N5](../../08-domain/spec/08.4-domain.norms.md), `record`, `ask-sig` — [P/08.8 N5](../../08-domain/spec/08.8-domain.norms.md), `peer` — [the contract `peer`](../contracts/peer.md), `follow` — [P/09.1 N5](../../09-agent/spec/09.1-agent.norms.md), `resolve` — [P/06.7 N5](../../06-console/spec/06.7-console.norms.md), the package `06-console/vectors/resolve`, `alarms` — [P/10 N5](../../10-domain-console/spec/10-domain-console.norms.md), the package `10-domain-console/vectors/alarms`); code 0 — computed (including a refusal by a word), 2 — the input is not in form | `peer` — M11/8, `may` — M11/9, `record`, `follow`, `ask-sig` — M11/10, `resolve`, `alarms` — M11/11 |

**Exit codes of the vector commands of M11** (the Architect's decision on the reconciliation of M11, H14). Code 2 — the form of what the caller takes from its
trusted state is violated: `keys`, `pub`, `cluster`, `field`, `domain`, `now`, `lost_after`, the names of the members, `history`, the rows
`grants`. Code 0 with a word — a document is bad which the function by the norm evaluates itself because it came from another
cluster: `row` and `held` (through `record`), `answers.<cluster>`, `page`. The function does not recheck a trusted input beyond the
form (for example, the signature of the set `keys` is checked at the write — P/08.2 N3 keys). The expectation of the code is `@exit 2` (the dictionary above);
the cases without a step are listed by N5 of the lesson.

#### Multi-cluster stand

**Clusters** (M11/3). The clusters `hold` (the holder), `m1`, `m2` — each with its own store, `{data}`,
role sockets, ports and ring (the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md), 
«Preparation of each scenario»). Substitutions: `{domain}` — `acme`, `{recovery}` — the recovery file of the installation in the directory of the instance. Between
the agent of each cluster and the door of the holder the runner keeps its own TCP proxy: the `DOMAIN_URL` of the agent points to it.

The substitutions of the commands of the domain stand (their templates are named by the description of the implementation, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) and [P/09.1](../../09-agent/spec/09.1-agent.norms.md) «Implementation decides»; review analysis of stage B 8–10, № 22: M-1): for the commands of the processes
of a cluster — `{data}` and `{socket}` of its cluster, `{port}` — the port of the door of this process; for the installation and `join` — `{domain}` and
`{recovery}` (for `@join <cluster> <file>` `{recovery}` is the named file). The runner gives out the recovery file as a copy with the mode
0600: git keeps `inputs/*.json` with 0644, and the implementation checks the mode when reading (P/08.2 N1.1 `mode`; the reconciliation of M11, I3). The agent
receives the environment `CLUSTER`, `DOMAIN_URL` (the proxy) or `RELAY_URL` (P/09.1), with `@clock` — `W2C_WALL_OFFSET`.

| Door or directive | Meaning | Lesson |
|---|---|---|
| `holder <request>` | the domain console on `hold` (the doors `/domain/*`); the runner sets `Idempotency-Key` on `POST`, `PUT` and `DELETE` of this door by the rule `@key` of the dictionary above (M11/6: domain edits require a key on all three; for the doors of [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.9 the key is optional, and a step with a key sets the replay memory, so such a step does not go under `@until`) | M11/3; the key — M11/6 |
| `member <cluster> <door> <request>` | the door `store` (`admin.sock`), `console`, `console2` (the prefix `/testsub2`, M11/5) or `resource` of the cluster `hold`, `m1`, `m2`; `store`, `console`, `resource` without a prefix — of the cluster `hold` | M11/3 |
| `@install domain` | the domain installation command (P/08.2 «Implementation decides» item 2) on `hold` with `{domain}` and `{recovery}`; then the command `domain first-admin root` (P/08.4 N1.9 `first`) with the password `w2c test root password` (the directive `@admin`) | M11/3; `@admin` — M11/9 |
| `@start domain` | the processes `domain` and the domain console on `hold`; at the first start after `@install domain` the runner logs in as the person `root` (`signer POST /api/login`) and writes `holder PUT /domain/grants/<cluster> {lines: [{subject: root, cap: admin, scope: "*"}]}` for each cluster of the stand (`hold`, `m1`, `m2`, `relay`; with `@clusters` — each one named there, including `m3`; review analysis of stage B 8–10, № 22: M-18) — the grants are prepared before the admission | M11/3; the login — M11/9 |
| `signer <request>` | the door of the process `domain` on `hold` through the proxy of the runner (the same as the `DOMAIN_URL` of the agents) — the login `POST /api/login` | M11/9 |
| `@person <name> <password>` / `@person -` | the runner logs in as this person (`signer POST /api/login`; the password — the rest of the line) and from then on sets `Authorization: Bearer <its token>` on the doors `holder`, `holder@…`, `member … console`, `console2` of this scenario, and for the command `@move`, logging in again on expiry; `-` — without a token. After `@start domain` the current person is `root`; before the domain there is no header. `@header Authorization: …` of a step replaces it | M11/9 |
| `@restart domain` | SIGTERM to both, wait for the exit, start again with the same `{data}` | M11/3 |
| `@start agent <cluster>` | the agent of the cluster: `CLUSTER=<cluster>`, `DOMAIN_URL` — the proxy of the runner to the door `domain`; after `@stop agent` it restarts only the first copy, with its local door and its `AGENT_TOKEN_DIR`, the other copies stay stopped | M11/3 |
| `@start agent <cluster> via <relay>` | the agent of the cluster behind a relay: `RELAY_URL` — the proxy of the runner to the door of the relay (`DOMAIN_URL` is not set); for a relay with copies (`@start agent <relay> second`) — the proxies of all copies separated by commas by the copy number (P/09.2 N1.1 `door`) | P/09.1 |
| `@start agent <cluster> second` | one more copy of the agent of the cluster — «another server» of the cluster: the same environment, its own process and instance, its own `AGENT_TOKEN_DIR` (the sockets of the local door of this copy — `token <cluster>#<n>`); for a relay cluster (`RELAY=1`) — its own relay door through its own proxy of the runner; the copies are numbered in the order of the start: the first — `agent#1`, then `#2`, `#3`…; the expectation `ok` — the process is alive | P/09.1 N1.13 (DOM-AGENT-TURN-01) |
| `@stop agent <cluster>` | SIGTERM to the agent of the cluster (to all copies), wait for the exit | P/09.1 |
| `@join <cluster> [<file>] [batch=<name> <$key>]` | the command `join` ([P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.1; review analysis of stage B 8–10, № 22: M-1) on the cluster: the domain and `root_pub` from `{recovery}` or from the named recovery file — the runner gives out a copy with the mode 0600; with `batch=` — the template `join-batch` instead of `join` (the input `batch` of the command, P/08.3 N1.1b): the substitutions `{batch}` — the name of the batch, `{batch_key}` — the path of the file with the private key (the bound `$name` from the answer of `POST /domain/batches`): the runner writes the key into a file with the mode 0600, like `{recovery}`, — the key does not get into argv and the process log; the template `join` has no such substitutions; the member class is `camera`; the expectation — `ok` or `refused` (the command refused, code ≠ 0) | M11/3; the batch — ADR-0113, roadmap 4.5 |
| `@domain [<cluster>…]` | the preparation «domain with members»: `@install domain`, `@start domain`, the agents of `hold` and of the named clusters (without a list — `m1`, `m2`), the admission of each by the fingerprint from `knocking` (`POST /domain/members {name, fingerprint}` with the key `admit-<name>`, the answer 200), after all the admissions the `@join` of each; it is ready when `holder GET /domain` is `complete: true`, its `members` are exactly `hold` and the named clusters, all of them are `ok` and each holds the set of the holder: `reports.<member>.keys_rev` of the view = the `rev` of the document `domain/keys` of the store of `hold` (no longer than 90 s; otherwise an edit of the console of a member right after `@domain` would meet `shut`, M11/2 N1.8) | M11/3, the list — M11/4 |
| `@cut <cluster>` / `@mend <cluster>` | the proxy of the runner breaks the connections of the agent of the cluster with the holder and accepts a new connection only to close it at once (the agent sees a connect, then EOF) / accepts them again; the implementation needs nothing | M11/3 |
| `@clock <cluster> <±N>` | restart the agent of the cluster with `W2C_WALL_OFFSET=<N>` (seconds added to its wall clock; `0` — without a shift), the rest of the environment — as before (the road through the relay remains); the agent is not running — start it so; all the copies of the agent are restarted | M11/3 |
| `token <cluster>[#<n>] <role> <request>` | (`token` followed by a path under `inputs/` is the vector command of P/08.2, not this door) the local door of the agent of the cluster (`#<n>` — of the copy `agent#<n>`, without it — of the first) with the identity of the role `<role>`: the socket `<AGENT_TOKEN_DIR>/<role>.sock` ([local token door contract](../contracts/local-token-door.md) «The role socket»; review analysis of stage A 8–10, decision 1); the `AGENT_TOKEN_DIR` of the agent on the stand — the runner (P/08.7 «Implementation decides» item 1) | M11/7 |
| `@verify <cluster> <kind> <$token>` | the command `token` of chapter P/08.2 of the implementation on the input `{keys: doc of the row domain/keys of the cluster, revoked: its row domain/revoked, now: wall-clock seconds of the runner, token, expect: {kind: <kind>, cluster: <cluster>, audience_claim: from the kind declaration}}` (`audience_claim` is looked up in the areas `placement`, `unit`, `scenario` of the declaration, the first with the key, by default `aud`); the expectation — `ok <JSON>` | M11/7 |
| `holder@<cluster> <request>` | the domain console on this cluster (after a move or a handover; `holder` — the same on `hold`) | M11/10 |
| `@start domain on <cluster>` | the processes `domain` and the domain console on a cluster without an installation (a signer without keys waits for a move or a handover); the console of the cluster is restarted with `SIGNER_URL` to its door, the process `domain` — with `DOMAIN_CONSOLE_URL` and the `SIGNER_URL` of its own door through the proxy of the runner (the address of the term record, P/08.8 N1.1) | M11/10 |
| `@stop domain [<cluster>]` | SIGTERM to the processes `domain` and the domain console of the cluster (without a name — `hold`), wait for the exit; `@start domain` brings them up again on `hold` with the same `{data}` | M11/10 |
| `@move <cluster> [stolen] [copy=<term>.<rev>] [why=<words to the end of the line>]` | `w2cctl domain move` ([P/08.8 N1.8](../../08-domain/spec/08.8-domain.norms.md)) to the door of the console of the cluster with the file `{recovery}` of the installation — the runner gives out a copy with the mode 0600; the identity of the command is the current person `@person` (after `@start domain` — `root`; `@person -` — without an identity): the runner passes their token to the command in the way of the implementation profile (the identity of the door — P/08.8 N1.8); the command prints `<code> <JSON>` of the answer on stdout, a first word that is not a number is a mismatch of the step; the expectation — as for a door: `<code> <JSON>` of the answer | M11/10 |
| `@on <cluster> <directive>` | a directive of the dictionary above (`@start`, `@sigterm`, `@sigkill`, `@freeze`, `@thaw`, `@put object`, `@spoil object`, `@append event`, `@append event-raw`) on this cluster — only these, another word is a data error before the scenario starts; `@append event` and `@append event-raw` — into the event root of the resource of this cluster | M11/3; objects — M11/11; `@append event` — C06-EVENTS-VIEW-33-01; `@freeze`, `@thaw` — P/08 (the coverage audit of P/08, 2026-10-30) |
| `@on <cluster> @start console#<n>` | a copy of the console of the cluster, `<n>` 2–9, only on the stand without a kit: there is one console per server, so a copy is like another server: its own `{data}`, `PLATFORM_DIR`, `SERVER_NAME` `<server>-<n>`, `BOX_ID`, `CONSOLE_PORT`; the store and the ring of the first server. The expectation `ok` — the port listens. The door `member <cluster> console#<n>`, the signals and `@freeze` — by the name of the copy, `console` without a number — the first | ADR-0095 |
| `@env <cluster> <NAME>=<value>` / `@env <cluster> <NAME>` | restart the console and the live copies of the agent of the cluster with the environment variable `<NAME>` equal to the value (an empty value — the variable is empty); without `=` — return the default value of the runner (the paragraph «Forwarding environment» below); the value `inputs/…` — a path from the acceptance directory of the lesson | M11/8 |
| `@start domain second` | a second copy of the process `domain` on `hold` with the same `{data}` and its own `{port}`; the copies — `domain#1` (the previous one) and `domain#2`; the proxy of the runner (the `DOMAIN_URL` of the agents, the door `signer`) leads to the first live copy by number; `@on hold @sigterm domain#1` (`@sigterm <name>[#n]` of the dictionary above: `#n` of `@sigterm` — added by M11/12) stops the first; `@stop domain` — both | M11/12 |
| `signer2 <request>` | the door of the second copy of the process `domain` on `hold` directly, without a proxy | M11/12 |
| `@carry <cluster>` | the 200 answer of the holder to the last `POST /api/member/<cluster>` that went through the proxy of the runner; the expectation — `ok <JSON>`, the comparison — by a subset of fields | M11/12 |
| `@clusters <cluster>…` | before the first operation that creates the stand: the cluster instances of the scenario (`@clusters hold m1 m2 m3` — a fourth cluster); without the directive — the former composition of the lesson; a repeat or another composition after the creation — a scenario error, not a restart | M11/8 (ADR-0083 addendum (9)) |
| `@tls-setup <description path>` | before the stand is created: TLS between the clusters per the kit description ([`Platform/common/acceptance/tls/`](tls/README.md), the path — from the acceptance directory of the lesson); the runner issues the kits by its own clock, puts them into the `W2C_TLS_DIR` of the clusters and gives `DOMAIN_CA`; the proxies only pass bytes through; on ordinary steps the door `holder` presents the client leaf `hold-console`, the doors `member <cluster> console` and `signer` present none, a handshake that fails on an ordinary door is a failure of the stand; the implementation profile — `keys.tls_stand: 1`, otherwise the check is not executed; it does not change the kits after the start | M11/8 (ADR-0083 addendum (9)) |
| `@kit-start <role> <kit\|none> [<NAME>=<value>…]` | one role process on the box of the stand with the command of «Stand»: `W2C_TLS_DIR` — the directory of the kit `<kit>` of the description of `@tls-setup` (`named`), `none` — an empty directory (there is no kit); `SERVER_NAME` — the `server` of the kit (`none` — `box-n`); the rest of the environment — the default of the runner, `<NAME>=<value>` — on top of it (an empty value — the variable is empty, as for `@env`); the runner stops the process of the previous `@kit-start` before the start, the last one — at the end of the scenario. The expectation: `ok` — the role port listens no later than 20 s; `@exit 2` — the process exited with code 2 no later than 10 s; `ok ~<text>[ ~<text>…]` — it listens, and the log of exactly this launch contains each substring. Its door is the `kit` of the probe `@tls` (README `tls/`) | ADR-0075 addendum 2026-10-26 (4) item 7, (5) item 4 |
| `@tls-kit <cluster> console <kit>` | the replacement of the TLS kit of one console of the cluster: the runner restarts only it with the previous port and data and the kit directory `<kit>` (`foreign` — a rotation to a foreign CA, `<cluster>` — the original one, a return); the other processes and the published CAs do not change; the expectation `ok` — the console listens again; the composition of the kits and the check of the server by the client — [README `tls/`](tls/README.md) | TLS № 14 (ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 22) |
| `@tls <probe path>` | one probe of a door by the common TLS client of the runner: the input `{door, client, version?, request, save_session?, resume_session?}` (the doors `holder`, `signer`, `member <cluster> console`; `version` is `TLSv1.2` or `TLSv1.3`; `request` is `{method, path, headers?, body?}` with a capital method and a raw URI, and the runner adds `Host`, `Connection: close` and, with a body, `Content-Length` and `Content-Type: application/json`; the client — a leaf of the description or `null`; the client presents the leaf on any certificate request, regardless of the list of CAs in the request, without a request it does not send it, ADR-0083 addendum (20), addendum (21) item 9); the expectation — `ok <JSON>`: the closed outcome `{handshake, version, reused, session_available, http}` by subset (the form `ok <JSON>` of the dictionary above; the reading of the commits of «cammeta-acceptance» tls-stand 2026-10-20); a connection refusal, a break, a timeout, an error of the server check and of the tool — the class «stand», not an outcome (README `tls/`) | M11/8 (ADR-0083 addendum (9)) |
| `@cut-route <from> <to> console` / `@mend-route <from> <to> console` | the proxy of the runner breaks and does not accept new / accepts again the connections of only the directed road from the console (and the move process) of the cluster `<from>` to the console of the cluster `<to>`; `@cut <cluster>` is still the road of the agent to the holder | M11/8 (ADR-0083 addendum (9)) |

**Relay** (P/09.2): the fourth cluster of the stand `relay`; its agent always opens the relay door
(`RELAY=1`, `RELAY_HOST=127.0.0.1`, `RELAY_PORT` — the port `{relay_port}` of the copy), and a proxy of the runner stands in front of it too. The copies of the relay start before the members behind it: `@start agent <cluster> via relay` before the relay copies is a data error, a second copy of the relay while a member `via relay` is alive is a failure of the stand. `@cut relay` breaks the road of the relay
to the holder; the doors of the members to the relay are their own proxies (`@cut <member>` breaks the road of the member, whatever it is).

**Forwarding environment** (M11/8; `@env` — [P/06.7](../../06-console/spec/06.7-console.norms.md) «Implementation decides» item 2): the console of each cluster receives `CLUSTERS` — the addresses of the consoles of all clusters of the stand
(`hold=<url>,m1=<url>,m2=<url>[,relay=<url>]`, without proxies; on a stand with a TLS kit or a scenario with `@cut-route` the values are the addresses of the proxies of the roads of the runner); the process `domain` — `DOMAIN_CONSOLE_URL`, the address of the door
of the domain console; `SIGNER_URL` — only the console of `hold`. The stand has no TLS kit: the doors on the loopback over `http://`
(P/02.4 N1.6). The runner sets `Idempotency-Key` on `POST`, `PUT`, `DELETE` of the path `/domain/…` of the door `member <cluster> console`,
as for the door `holder`.

**Expectations** of the domain stand are the forms of the dictionary above: `<code> <JSON>` by subset, `$name`, `@spoil($name)`, `@any`/`@absent`,
`@not`, `@time`, `~text` (for example `~enc:v2:` — the envelope of the ring of a member), `!contains`, `@exit`; for the vector commands and `@carry` —
`ok <JSON>`, for `@join` — `ok` or `refused`, for `@move` — `<code> <JSON>` of the answer of the door. Sleeps (`@sleep`) with reasons — in the acceptance README
of the chapter.

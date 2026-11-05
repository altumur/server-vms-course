# The acceptance stand of the module «Platform», М10 and М11

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

## Stand — common to the acceptance of the lessons of the module «Platform», М10 and М11

The acceptance runner of any lesson of М10 starts an implementation only through the interface that the implementation names
in its description (the norms of P/01.1, «Implementation decides» item 10); the runner does not know its internal API.

### Layout by processes (stage C)

An implementation of stage C is one micromodule per process (ADR-0083 addendum (5), (25) item 4; the request of cammeta-acceptance
`decisions/inbox/2026-10-23-format2-профили-микромодулей-заявка.md`, the Architect's consent of 2026-10-23). The form of the files is
the section «format2 acceptance.yaml и assembly.yaml» of the README of the runner cammeta-acceptance (commit `0e597ca`); here is what
follows from it for the stand. The scenarios and the expectations of acceptances do not change by this.

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
- **The unified command of a vector package** (ACC-VECTORS-CONNECT-01/02, the Architect's decisions of 2026-10-26; the exact wire is
  the section «Единая команда пакета векторов — ACC-VECTORS-CONNECT-01» of the README of the runner cammeta-acceptance, commit `ab1e77a`).
  A process profile MAY declare `vectors`: a package name (the path from `Platform/` without `vectors/`, for example `common/may`) →
  its own command with `{input}`. The entry is per package; only the tables and rows that the package README assigns to this
  consumer are executed (the section «Кто исполняет»: a table or a row by a field — `may` `covers.tsv` only 06 and 10,
  `events-merge` by `participant`); a foreign selection is not required. The input is a JSON file `{format, package, table, case,
  variant, cells, files}`: only the input columns as the string of the source cell and the input fixtures of the README, without
  expectations; the parsing of the cells and markers per the package README and the native object of its function are built by the
  command of the implementation (for `values-by-type`, `rid`, `request-digest`, `covers` — their object from the README; the former
  `stand` commands do not change). A key of `cells` is the name of an input column: for a table with a header — from the header,
  for a table without a header — the field name from the package README (the input cell «as written» — `raw`: `log-mask`,
  `secret-in`, `group-of`, `jcs`). A key of `files` is the file name of an input fixture, the last component of its path in the
  README (`fields.yaml`, `testsub.subsystem.yaml`, `testsub2.subsystem.yaml`); the value is the bytes of the file as they are (the
  inventory C04/C06-NEXT-167, the Architect's decision of 2026-10-27).
  The answer is `{exit_code, stdout_b64, stderr_b64}` of the native outcome with the outer code 0; to the decoded bytes the runner
  applies the contract of the table (whole, subset, raw id, `@exit 2`). There is no `vectors` entry for an assigned package —
  `blocked`, not PASS. The coverage is reconciled by the full SHA of the export and the SHA of the table; a row number is an address
  only within this pin.

- **Launch command** — a template with substitutions: `{data}` — a new empty data directory of the instance; `{socket}` — the
  socket path of the store door (P/01.1); `{port}` — the HTTP port of the console on the loopback (lesson P/06 and the acceptances with the console stand); `{manifest}` — the directory
  of the stand manifests for the processes that need it (`MANIFEST_DIR`, P/02.3); the store command does not receive it and puts no manifests; `{body_limit}` and `{row_ceiling}` — the body limit and the row ceiling (Н5 P/01.1);
  `{rights}` — the path of the rights file which the runner puts before the store starts (P/01.2 Н1.2): in P/01.1 — the file below
  («Role sockets»), in the chapters P/01.2 and P/01.3 — the ready input [`01-store/acceptance/2/inputs/rights.json`](../../01-store/acceptance/2/inputs/rights.json), in the acceptances moved from М10/4–11 — the rights derived from the stand manifests by the rights derivation command below (`{manifests}` — the directory of the stand
  manifests, `{deployment}` = `dep`); the store command receives `{rights}`, not `{manifest}` (the log of cammeta-python, lesson 11
  № 29). The implementation names which substitutions each of its processes needs.
- **Manifest install command** `manifest-put` (P/02.3 Н3 «Manifest change») — a template with `{socket}` and `{file}`: puts one manifest
  through the `admin.sock` of the store (`{socket}`); code 0 — put, another — a refusal. With it the runner sets up the stand manifests one by one
  in the order of «Manifests» below, after the store is ready and before the first `@start` (the store pilot, A6).
- **Rights derivation command** (P/02.5 Н2) — a template with `{manifests}` (the directory of the manifests), `{deployment}` and `{file}`: writes the rights file per
  P/02.5 Н1.4; code 0 — the file is written, another — a generation refusal. The implementation names it in its description (P/02.5
  «Implementation decides» item 1). The acceptance variants of P/02.5 (`5/variants/`) call it with `{deployment}` = `dep` (reconciliation of python and go
  М10/6–11).
- **Rights check command** (P/02.5 Н2 `--check`, Н3 «install») — the key `stand.rights-check` of the profile `02-installer`, a template with
  the same substitutions as the rights derivation command (`stand.rights`): `{manifests}` — the directory of the manifests, `{deployment}`, `{file}` —
  the rights file that is checked (not written); the outcome is the code: 0 — the file is equal in meaning to the rights derived from the manifests, another — they differ.
  The acceptance variants of P/02.5 with `check.tsv` call it for each case with the manifest directory of the variant, `{deployment}` = `dep` and
  `{file}` = `check/<case>.rights`; the code is compared with the column `code` (`0` | `!0`). There is no key in the profile — the cases of `check.tsv`
  are not executed (not GREEN and not an outcome of the implementation). There is no substitution `{specs}` in the stand vocabulary (the Architect's decision of 2026-10-30,
  the norm questions of the Gemini audit, P/02 item 3; C02-RIGHTS-CHECK-STAND-01).
- **Ring command** — the template `ring {file}`: creates a key ring per the [sealing contract](../contracts/sealing.md) (`w2cctl secrets new` of the implementation, P/02.4 Н1.9) in the file
  `{file}`; the runner calls it before the first process with `{file}` = `{data}/etc/secrets/platform.key` (the Architect's decision,
  the second pilot); code 0 — the ring is created. The owner and the mode of the ring file on the stand — the section «Stand without root» below
  (I02-RING-FIXTURE).
- **Copy commands** (P/01.3 Н1.3 `copy`, `admin_ops`): `backup` — a template with `{socket}` and `{file}`: a copy of the store through
  `admin.sock` into a file, code 0 — the copy is taken; `import` — a template with `{data}`, `{file}` and `{index_base}`: the transfer of a copy into
  a fresh directory of a stopped store (P/01.3 Н1.3 `box`), code 0 — transferred, another — a refusal. The implementation names
  both (P/01.3 «Implementation decides» items 4, 11; the store pilot).
- **Command to load one manifest file** (P/02.1) — a template with `{file}`; exit code 0 — a manifest, another — a refusal, the text
  of the refusal names the file (the norms of P/02.1, «Implementation decides» item 3).
- **Processes of several roles** (lesson P/03 and later): the implementation names the launch command of each role — the store,
  the console, the controller, the worker, later the resource; the worker command receives the name by the substitution `{name}` (an argument), the environment —
  `BOX_ID` (the constant box of the stand) and `SERVER_NAME` (P/02.4 Н1.2); from the environment the worker takes its name only by `slot.name_env` of its manifest
  (P/02.1 Н1.2а), and the runner sets this variable if the manifest declared it (`testsub2` — `TALLY_NAME`; `testsub` has none). In the acceptances moved from the lessons before М10/6 (rights — now P/01.2), the runner reads the store with a role that has full rights on the prefix of the subsystem.
- **Resource** ([P/05](../../05-resource/spec/05-resource.norms.md)): the launch command of the server resource with the substitution `{rport}` — the port of its door; the runner waits for the port
  and the row `platform/doors/<server>` before the first step. For a scenario that needs the heartbeats of other servers, the resource is on the server
  of the controller: the process reads the cluster objects through the resource of its own server (P/04 Н3 «pass()» step 0; ADR-0084 addendum (2) R17).
- **Role sockets** (P/01.2, P/01.3 Н1.3 `sockets`): on a box too the store opens a socket per role (`<role>.sock`, `admin.sock`) per the rights
  file; the runner calls through the socket of the role of the scenario. `{socket}` is the path of `admin.sock`; the role sockets lie next to it, in the same directory, flat (P/01.3 Н1.3 `sockets`).
  `{socket}` is a door with full rights (preparation). Lesson 1 runs the scenarios with the role `acc` — read and write rights only on
  `acc/*`, the socket `acc.sock` next to `{socket}`. The runner puts exactly this file into `{rights}` (the form — P/01.2 Н1.2):
  `{"roles": {"acc": {"group": "acc", "read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}}`.
  Deletion is a separate action (P/01.2 Н1.3 `allowed`); in the file it is named explicitly.
- **One data directory** `{data}` per instance — it is `PLATFORM_DIR` (P/02.4 Н1.2 «The setting channel and the layout»;
  the second pilot, N-4). The stand translates the substitutions into the environment of P/02.4 Н1.2: `PLATFORM_DIR={data}`,
  `PLATFORM_STORE=configstore://<role socket>`, `CONSOLE_PORT={port}`, `RESOURCE_PORT={rport}`, `BOX_ID`, `SERVER_NAME`,
  `SECRETS_KEY={data}/etc/secrets/platform.key` — the ring per the layout of P/02.4 Н1.1, created by the runner with the ring command before the first process; the worker name — by the argument `{name}`. The layout is per P/02.4 Н1.2: the store
  `{data}/configstore`, the objects `{data}/objects`, the events `{data}/events`, the presence locks `{data}/events/.workers`.
  The event root of a server is derived unambiguously — `{data}/events` of its `PLATFORM_DIR` (the stand does not set `RESOURCE_ROOT` and
  `EVENTS`), so «Stand» has no separate key for the event root.
  The server settings file is `W2C_ENV={data}/etc/w2c/w2c.env` (P/02.4 Н1.2: the directory `roles/` is next to `w2c.env`,
  there is no other place), the role files are `{data}/etc/w2c/roles/<role>.env`; for a server `on <server>` — the same path in its
  `PLATFORM_DIR` `{data}/servers/<server>` (the choice of the owner of the runners, cammeta-acceptance e3ec5c3).
- **Manifests** are set up by the command `manifest-put` in the order of dependencies: `testsub`, then `testsub2` (it references `testsub`: `about`,
  `near`, `worker.requests`); loading the directory (P/02.1 Н3) sees both.
  The manifest `testsub2` declares `console.shell` and `console.files`: the installation reads these files next to the manifest file (P/02.3 Н3
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
  `Platform/04-controller/vectors/order/`, `…/shrink-victim/`, `…/shrink-allowed/` (P/04 Н3 «shortage(), order()», «shrink()»),
  `Platform/02-installer/vectors/workers-script/` (P/02.4 Н1.5): the runner reads the `cases.tsv` of the package (UTF-8, TAB, lines
  with `#` and empty ones are skipped, the first one not skipped is the header), for each row writes the cell `input` byte for byte into a
  temporary file, calls the command of the package with `{input}` and compares stdout with the cell `expect` as JSON by value,
  whole (the order of the object keys does not matter; an array — by length, order and elements); code ≠ 0 or not JSON — FAIL of the
  row; the result of the package — the rows by `case`. The implementation names the templates in its description, like the other commands of «Stand».
  The commands `exec` and `install-order` of the profile `02-installer` and `door-token-verify` of the profile `03-worker` answer with the envelope
  `{"result": …}` — the protocol is in the READMEs of their packages (`Platform/02-installer/vectors/exec/`, `…/install-order/`,
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
  (P/01.3 Н1.3 `durability`).
- **Instance** — per scenario (P/01.1) or per full run, as the lesson README says; the runner waits for the socket or the port,
  then checks the parameters by behaviour per Н5 P/01.1. A ready door instead of a launch — the run is not isolated and not green.
  A run of named scenarios only (the gate `accept:<chapter>:<scenarios>` of a stage, ADR-0126) keeps the isolation per scenario and
  does not carry the chapter-wide probes of the parameters and of raw HTTP: its result names the subset, and a target is green
  only by its full run.
- **README checks beyond the TSV** in each lesson are a scenario or an item «checked by reading» with a subject: controlled
  clocks, two consoles on one store and drills on a real box with systemd (`@manual`, [system acceptance](system/README.md)) are not given by this interface;
  a store group of several daemons is given by «Store group stand» below (P/01.3 Н5), a server failure — by «Three-server cluster stand» below.

### Stand without root

The stand is started by an unprivileged user; the product is strict, the stand is not (the stage C guesses I02-RING-FIXTURE,
C04-STAND-GID-01, the Architect's decision of 2026-10-23):

- **platform groups** (`w2c-events`, `w2c-secrets`, `w2c-store` and the others of P/02.4 Н1.1) on the stand are the current (primary) group of the process,
  one for all roles, on any OS and whether such a group exists on the machine or not (the event trees — the event journal contract
  `modes`; ACC-EJ-STAND-GROUP-01, the Architect's decision of 2026-10-28); the product requires system groups without a fallback;
- **roots** `{data}/config` — 2770, `{data}/objects` — 2770, `{data}/events` — 2771 (the modes of P/02.4 Н1.1 `dirs`; there are no other
  roots; the directories inside `objects` are 0775 per P/05 `disk`, they are not roots) are created by the role launch command of the profile before the start of the
  process, if they are absent, — with these modes, with the current uid/gid (the group on the stand is the current one); it does not change the existing permissions and owners; the role
  process does not create roots (P/02.4 Н1.1 `dirs`); `PLATFORM_DIR` is an absolute path (STAND-ROOTS-CLEAR-01, the Architect's decision of 2026-10-27);
- **key ring** — the ring command above creates a new file (the bytes — per the sealing contract) with the owner — the current
  uid/gid — and the mode 0640; it does not replace an existing file — a nonzero code; the owner `root:w2c-secrets` of the product (P/02.4 Н1.9)
  is not checked by the stand;
- **the entry point of a process on the stand** is a profile command (for example, `controller-stand <sub>`): the process connects to the store
  with its own role (`PLATFORM_STORE` of the role), not `admin`.

### Dictionary of directives and doors

One definition per module. A lesson README references this dictionary and writes only its own: the preparation, the roles and
the special comparison rules. The column «Lesson» is the lesson that introduced the directive: a number — the former lesson М10/N (before the move),
`P/NN` — a lesson of the module, `М11/N` — a lesson of М11, `ADR-NNNN` — a decision without a lesson (like `@grow`, ADR-0084); a lesson introducing a new one
adds a row here (review analysis of stage B 3–5, № 33).

**A row of `scenarios.tsv`** — `scenario`, `step`, `request`, `expect` separated by tabs. Lines with `#` are notes, the header
line is skipped. The steps of a scenario are numbered from 1 consecutively (1).

**Doors** — the prefix of `request`. Without a prefix the request goes to the door of the lesson: the store in P/01 (chapters 1.1, 1.2) and P/02.5, the console in the chapters P/06 6.1, 6.3, 6.5, 6.6 (the former М10/1, 6 and М10/3, 4, 9).

| Door | Where | Lesson |
|---|---|---|
| `store` | the store door of P/01.1 through the socket of the role of the scenario; the role is named by the lesson README, `@as` changes it | 5 |
| `admin` | the store door through `admin.sock`; the stand sets the epoch floor through it — `admin POST /v1/write {"op": "floor", "floor": N, "id": …}` (P/01.3 Н1.3 `floor`, `admin_ops`); there is no `w2cctl` command for the floor | 11; floor — P/01 |
| `restored` | the door through `admin.sock` of the store instance which the last `@import store` of the scenario brought up | 11 (the store pilot) |
| `console` | the console on `{port}`, the root subsystem `testsub` | 5 |
| `console2` | the same console, the prefix `/testsub2` of the mounted subsystem | 10 |
| `resource` | the door of the server resource on `{rport}` with an admissible identity | 8 |

**Request.**

| Form | Meaning | Lesson |
|---|---|---|
| `<METHOD> <path with query> [<body>]` | the path and the query go byte for byte, without re-encoding; the body is the bytes after the substitutions, invalid JSON is admissible | 1 |
| `@big(N)` | a substitution in any part of the request: a string of N bytes `x`; inside a JSON string — before serialization | 1 |
| `@raw <text>` | the body is the text as UTF-8 bytes, `application/octet-stream`; `Content-Length` — by the bytes; `@raw` — only in the place of the body, as the first word after the path (`<door> <METHOD> <path> @raw <text>`), at any door; «@raw» inside a JSON body or another word is ordinary text of the body, not a directive (Codex review of the runner series 4faf728) | 10 |
| `@key(<word>)` / `@nokey` | `Idempotency-Key` on `POST` — by default `<run>-<scenario>-<step>`, fresh per run; `@key(<word>)` sets `<run>-<scenario>-<word>`, that is, `@key(N)` repeats the exact bytes of the key of step N of its scenario; `@nokey` — without the header | 3 |
| `@as <role>` | the step and the following `store` steps of the scenario — from this role, through the socket `<role>.sock` (the section «Stand» above) | 6 |
| `@header <Name>: <value>` before the method | add a header to one request; `@header Idempotency-Key: …` replaces the default key of the runner (`@key`) | 6; key — 3 |
| `ASSERT $a != $b [$c …]` | the named values are pairwise distinct; no HTTP is sent | 1 |
| `ASSERT <term> <op> <term>` | a comparison of bound values; no HTTP is sent. `<term>` is `$имя`, a JSON number or a difference `$a - $b`; `<op>` is `==`, `!=`, `<`, `<=`, `>`, `>=`. Order and difference — only for numbers; for strings — `==` and `!=`; different types — a mismatch (`ASSERT $t2 - $t1 < 2`, `ASSERT $a <= $b`) | М11 (mutation check 2026-10-18) |

**Stand directives** — not HTTP; the answer is `ok` or a refusal of the runner.

| Form | Meaning | Lesson |
|---|---|---|
| `@start controller [<sub>] [shrink_after=<s>]` / `@start worker [<sub>] <name> [on <server>] [labels=<labels>] [<NAME>=<value>…]` / `@start resource [on <server>]` | start a role process with the command of «Stand»; `shrink_after=<s>` — the environment `W2C_SHRINK_AFTER=<s>` for the controller (stand only, P/04 Н1.4 `SHRINK_AFTER`; ADR-0084); `<sub>` — a subsystem of the stand directory, without it — `testsub`; `labels=<labels>` — the environment `LABELS=<labels>` for the worker as it is (P/03.2 sc. 11); `<NAME>=<value>` (only for a worker; the name is `^[A-Z][A-Z0-9_]*$`, the value — up to a space, empty — the variable is empty) — the environment `<NAME>` of this process with this value instead of the value of the runner, the other substitutions, directories and environment — as before (P/03.2 sc. 22: `INSTANCE_ID`, `BOX_ID`, `SERVER_NAME`; the coverage audit of P/03, 2026-10-30); the expectation: `ok` — the process is started; for a worker, a controller and a resource also `@exit <code>` — the process exited with this code no later than 10 s from the start, the output is not compared (a start refusal, P/03.2 sc. 09, 11, 19, 22; the controller — P/04 sc. 23, the resource — P/05 sc. 17, the schema check at start); the worker receives its name by the substitution `{name}` in the command of «Stand» and, if the manifest declared `slot.name_env`, also in this variable (`testsub2` — `TALLY_NAME`), the same box, `server=srv-a`; `on <server>` (ADR-0084) — a process of the server `<server>`: `SERVER_NAME=<server>`, `BOX_ID` — `<stand box>-<server>`; a server other than `srv-a` has its own `PLATFORM_DIR` `{data}/servers/<server>` (its own event root and presence locks), the same store (`PLATFORM_STORE`) and the same ring (`SECRETS_KEY`), a resource has its own `{rport}`; for the resource of each server the runner puts the role file `roles/<sub>worker.env` of each manifest with `grows: true` (`HOST_MEMORY_MB=4096`, `WORKER_MEMORY_MB=256`, the directory `roles/` — next to `W2C_ENV` of its `PLATFORM_DIR`: `<PLATFORM_DIR>/etc/w2c/roles/`, P/02.4 Н1.2), so that the resource writes `room.<sub>` (P/05 Н1.4; the presence lock contract «Count `room`»); a repeat of the same name — a second copy; the readiness is checked by the following `@until`; the controller and worker commands of «Stand» receive the substitution `{sub}` (without `<sub>` — `testsub`), the resource command — `{server}` (`srv-a`; on the stand of М11 — `srv-<cluster>`) | 5; the resource and `<sub>` — 8; `on <server>` — ADR-0084; `<NAME>=<value>` and `@exit` of the worker — P/03.2 (the coverage audit of P/03, 2026-10-30); `@exit` of the controller — P/04 (the coverage audit of P/04, 2026-10-30); `@exit` of the resource — P/05 (the coverage audit of P/05, 2026-10-30) |
| `@grow <server>…` | until the end of the scenario the runner reads, once every 5 s, `/<sub>/metrics` of the console of each manifest with `grows: true` and for the named servers keeps exactly the worker numbers `<prefix>-<server>-<n>` from `{2…want}`, where `want` is the series `<sub>_workers_wanted{server="<server>"}` (the base one `-1` is started by the scenario itself; ADR-0084 addendum (4) R26): a missing number — `@start worker <sub> <prefix>-<server>-<n> on <server>`, the smallest first, but no more than `floor(HOST_MEMORY_MB / WORKER_MEMORY_MB)` processes of the role on the server together with the base one — like the memory ceiling of the script (P/02.4 Н1.5; ADR-0084 addendum (2) R14); a number greater than `want` — `@sigterm`, the largest first (the number — as an integer); there is no series, it is unreadable or the console is silent — nothing; the servers are not named — the order on them is not executed («did not bring up»); the server script of P/02.4 Н1.5 is executed without polkit (it is checked by the test of the unit and the policy) | ADR-0084 |
| `@sigterm <name>[#n]` / `@sigkill <name>[#n]` | stop a process; `<name>` is a worker name or the role of a process `controller` (the controller of `testsub`), `resource`, `console` — the cluster console, `domain` — the process `domain`, `domainconsole` — the domain console, `agent` — the cluster agent (copies — `agent#<n>`, `@start agent <cluster> second`; DOM-AGENT-TURN-01) (on the domain stand — `@on <cluster> …`; review analysis of stage B 8–10, № 15); by default the last copy with this name, `#1` — the first | 5; `#n` of `@sigterm` — М11/12 |
| `@freeze <name>[#n]` / `@thaw <name>[#n]` | freeze a role process (SIGSTOP to the process group) / unfreeze it (SIGCONT); `<name>` — as for `@sigkill`; does not wait for an exit; the expectation `ok`. The freeze limit is 120 s: not unfrozen by the limit or by the end of the scenario — the runner sends SIGCONT itself (also before the teardown of the stand: a stopped process does not hear SIGTERM), the step is of the class «data», not an outcome of the implementation. The meaning is a pause of the machine: the whole process freezes, with all its threads (at the Architect's request of 2026-10-30, the estimate of the runner ~2–3 h; the audits of P/03, P/04) | P/03, P/04 (2026-10-30) |
| `@cut role <role> store` / `@mend role <role> store` | a proxy of the runner on the unix socket of the store role `<role>`: for the stand processes of this role `PLATFORM_STORE` points to the socket of the proxy (the runner sets it up before the processes start if the role is named in the scenario), the proxy itself connects to the real `<role>.sock` — the identity is the same (P/01.2: the identity is the role socket). `@cut` — silence: live and new connections are accepted, bytes are not forwarded in either direction, nothing is closed (the store «hangs without an answer», not a refusal); `@mend` — the connections opened or hanging during the cut are closed (the outcome of their requests is unknown to the client), new ones are forwarded again; the expectation `ok`. The name is not `store@<id>` of a group member (at the Architect's request of 2026-10-30, the estimate of the runner ~1 day; the audits of P/03 C11, P/04 D07) | P/03, P/04 (2026-10-30) |
| `@put object <key> <file>` | put an object of the object store of the stand with the bytes of the file (the path — from the acceptance directory of the lesson) by the object write command of the implementation ([P/05](../../05-resource/spec/05-resource.norms.md) «Implementation decides» item 8), bypassing the writer and its checks | М11/11 (mutation check) |
| `@spoil object <key>` | spoil an object of the object store of the stand by the spoil command of the implementation (P/05 «Implementation decides» item 8): after it a read of the object is unreadable (P/05 Н1.1): the bytes of the object are spoiled — the body is not read by its family; the file and the directory of the object are intact, the resource door gives it out as it is — in the listing with `written`, `server`, `size`, `GET` 200 (P/05 Н1.1 `door`), the judgement garbled is the reader's; an object which the door itself does not read is not a spoil (C05-SPOIL-OBJECT-BYTES-01, the Specification's decision); the writer process of the object is stopped before this | 11 (reconciliation of python and go) |
| `@restart store` | SIGTERM to the store, wait for the exit, start it with the same command with the same `{data}`, wait for the socket | 11 |
| `@rights store <файл\|none>` | SIGTERM to the stand store, wait for the exit, start it with the same command with the same `{data}` and the rights file `<file>` (the path from the acceptance directory of the lesson; the runner puts it into `{rights}`) or without `-rights` (`none`: in the command template of «Stand» the runner removes the occurrence `-rights {rights}` or `-rights={rights}` — the flag with the substitution `{rights}`, not any word `-rights`: in a composite command it may belong not to the store — and changes nothing else; `<file>` — the same `{rights}` points to it; there is no such occurrence in the template or there is more than one — the scenario is not_executed with a reason, Codex review of series A); the expectation: `ok` — `admin.sock` and the sockets of the roles of the file (`none` — only `admin.sock`) accept a connection no later than 20 s, as at the start of the instance; the runner sends no request for this (`/v1/status` of chapter 1.3 may still be a stub at the stage `rights`); `@exit 2` — the process exited with code 2 no later than 10 s (the file is not in the form of P/01.2 Н1.2, Н4); the file of the previous row does not carry over to the following scenarios | P/01.2 (the coverage audit of P/01, 2026-10-30) |
| `@spoil row <key>` / `@spoil row-index <key>` | spoiling a row of the stand store bypassing the door: SIGTERM to the store, the command `spoil-row` of «Stand» with `{data}`, `{key}` and `{what}` (`body` — the bytes of the row body are unreadable, the version is intact; `index` — the row version is lost, the body is intact), a start with the same command; the expectation `ok`; the implementation names the command and what it spoils in its description (P/01.1 «Implementation decides» item 5); the command in the profile is also the declaration of a durable store (there is no separate key); there is no command — not_executed only for a scenario with `@spoil row`, the others are executed, the result of the lesson is not GREEN | P/01.1 (the coverage audit of P/01, 2026-10-30) |
| `@restart console` | SIGTERM to the console, wait for the exit, start it with the same command of «Stand» with the same `{data}` and `{port}`, wait for the port; the port did not come within 20 s — a refusal of the runner | 7 (reconciliation of python and go М10/6–11, S8) |
| `@append event <tree>/<unit>/e<epoch> <text>` | append the text as a line (UTF-8 bytes and LF) into the bucket by `t` of the line `<events root of srv-a>/<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`, `start` = floor(t / 600) × 600; a text that is not JSON, without a numeric `t` or with `t` outside [0, 253402300799] (the bucket name is a four-digit year, 1970–9999; the writer refuses a line later than the year 9999, the event journal contract «Отказы писателя», EJ-G06) — the bucket of the current window ([event journal contract](../contracts/event-journal.md) «Writing a line», step 4 — review analysis of stage B 3–5, V1; the root — `{data}/events`, «Stand») bypassing the writer; there is no file — create it; `{now}` in the text — the wall seconds of the runner at the moment of the write (time per Н0 P/01.1); the components of the path — per the encoding of names ([event journal contract](../contracts/event-journal.md) «File names in shared trees») | 8 (reconciliation of python and go М10/6–11, E19) |
| `@append event-raw <tree>/<unit>/e<epoch> <text>` | like `@append event` (the bucket of the current window, the root, the encoding of the path components, `{now}`; there is no file — create it), but the text is appended as UTF-8 bytes without LF at the end — a torn tail of the bucket ([event journal contract](../contracts/event-journal.md) «The line and the bucket» `torn`); the expectation `ok`. The next append into the same bucket will glue together with the tail into one line — the tail is written last in the bucket of the scenario | P/05 (the coverage audit of P/05, 2026-10-30) |
| `@backup store <name>` | take a copy of the stand store with the command `backup` of «Stand» into a file of the runner `<name>` (it lives until the end of the scenario); `ok` — code 0 and the file in the form of P/01.3 Н1.3 `copy` (a header, Row rows, keys in ascending byte order); otherwise a refusal of the runner | 11 (the store pilot) |
| `@backup store <name> in-data` | the command `backup` of «Stand» with `{file}` = `{data}/configstore/<name>` — inside the data directory of the stand store (`-dir`); the expectation `refused` — code ≠ 0 and there is no file `{data}/configstore/<name>` | 11 (reconciliation of python and go М10/6–11, B8) |
| `@import store <file>` / `@import store backup <name>` | the input is a file from the acceptance directory of the lesson or a copy `@backup store <name>` of this scenario; the runner takes a new empty `{data}`, calls the command `import` of «Stand» with `{index_base}` — the `index` of the header of the input (the header is not readable — `0`), then on this `{data}` starts a second store instance with the command of «Stand» with its own `{socket}` and waits for the socket — its door is `restored`. The expectation `ok` — the code of `import` is 0; `refused` — code ≠ 0 (that the directory remained without rows is seen by the following steps `restored`). The stand store is not touched | 11 (the store pilot) |
| `@foreign store nolabel` / `@foreign store otherlabel` | a second store instance with the same command with a new directory `{data}` and its own `{socket}`; before the start the runner puts into the store directory `{data}/configstore`: `nolabel` — a file `rows` with the bytes `x` and without `FORMAT`; `otherlabel` — `FORMAT` with the bytes `{"format":"w2c-acceptance-foreign","version":1,"impl":"runner"}`. `ok` — the process exited with code 2 no later than 10 s and the directory tree (names, bytes) is the same as before the start; otherwise a refusal of the runner. The stand store is not touched (P/01.3 Н1.3 `format`) | 11 (the store pilot) |
| `@sleep <seconds>` | wait. Only a check of absence (nothing happened within the term) or a time that the norm requires before an action; waiting for an event — `@until` by an observable sign. The length is the smallest at which a violation would have had time to show; each sleep is named with its reason in the acceptance README of the lesson (ADR-0080 addendum (17) item 4) | 5 |
| `@together <request> \|\| <request>` | two requests at once: the runner opens both connections and sends both requests without waiting for the answer to the first (the last byte of the second leaves before the answer to the first arrives); the expectation `ok {"codes": [<code>, <code>]}` — the codes of both answers in ascending order, the bodies are not judged; so the acceptance sees an admission race that sequential steps would not show | ADR-0119 addendum (18) |
| `@until <seconds> <request>` | repeat the request until it matches `expect`, no longer than the term; the term ran out — FAIL with the last answer; a read is repeated, not a mutation | 5 |
| `@manual <text>` | a drill step: the runner prints the text and does not execute it; it does not enter the result (neither green nor red), `expect` — `manual` | 11 |

**Expectation.**

| Form | Meaning | Lesson |
|---|---|---|
| `<code>` | the code is exact; the body is not checked, except the full form per the contract of the owner | 1 |
| `@exit <code>` | for a vector command (the request is a command of the lesson on an input `inputs/`): the exit code of the command is exactly `<code>`; the output is not compared, stderr is not normed; the expectation `ok <JSON>` — code 0 and the output; for `@start worker`, `@start controller` and `@start resource` — the process exited with the code `<code>` no later than 10 s from the start (the stand directives above) | М11 (the Architect's decision on the reconciliation of М11, H14); `@start worker` — P/03.2 (the coverage audit of P/03, 2026-10-30); `@start controller` — P/04 (the coverage audit of P/04, 2026-10-30); `@start resource` — P/05 (the coverage audit of P/05, 2026-10-30) |
| `2xx` / `4xx` | the class of the code | 4 |
| `@oneof <code> <JSON> \| <code> <JSON>` | one of the answers: the branches are separated by « \| », each is the form `<code> <JSON>` and is judged by the rule of this form of its acceptance (in P/01.1 — JSON whole, without `@any`; in the others — a subset, `@any`/`@absent`/`~`); the separator is only between branches, after a completed JSON value (« \| » inside a JSON string is part of the string); the code of a branch is exact, there is no class `2xx` in a branch; the branches are checked in order, the first that matches wins; the bindings `$имя` are fixed only by the matched branch — a name bound only in another branch is not bound further; for a race which the norm allows with two answers (P/06.4 Н3 «file a request» step 5: `200 answered` or `202 queued`) | the request of VMS of 2026-10-29 (C-ONEOF-01, the Specification's decision) |
| `<code> <JSON>` | in P/01.1 — JSON whole (the order of the object fields does not matter); in the other acceptances (since the former М10/3) — a **subset**: the named fields are present and equal, the others are admissible; `{}` in an expectation at any level is exactly an empty object; any object is `@any`; no field is `@absent` (ACC-EMPTY-OBJECT-01, the Architect's decision of 2026-10-26); an array whose order the norm does not set (the list is here: `configured` of the answer `GET /<rows>`, P/06.1 Н2) — without order: the lengths are equal and there is a one-to-one matching under which each element of the expectation matches its actual one by subset; the other arrays — by length, order and elements (the Architect's decision of 2026-10-27); JSON types are exact: a JSON number is compared by value (`50` = `50.0`, `1e2` = `100`), a string, `true`/`false` and `null` are not equal to a number | 1, 3 |
| `$имя` | binds a JSON string or number (a number — for `ASSERT`; P/01.1 binds only strings, below); the first occurrence binds, the following ones compare; in `request` the bound value is substituted; the bindings of an attempt are fixed only after the whole step matches; they live until the end of the scenario; the name is `[A-Za-z0-9_]+`, it ends at the first other character (`…/$r2.delta` — the name `r2`) | 1 |
| `@spoil($имя)` in `request` | the bound string with a character changed in the middle of its last segment after «.» (for a string without «.» — in the middle of the string): the position ⌊n/2⌋ of a segment of length n, `A` → `B`, any other character → `A`; the form (length, base64url alphabet, canonicity) is the same — in a signature a character with full 6 bits is changed, not the last one (in a 64-byte signature it carries 2 bits, and the replacement would give a non-canonical tail — `not_a_token` instead of `bad_signature`); the signature of the token or the document no longer verifies — this is how a bound token is forged (`$ta`, `$tok`) (the log of cammeta-python; the Architect's decision of 2026-10-18) | М11 (mutation check 2026-10-18) |
| `@any` / `@absent` | the field is present with any value / there is no field | 3 |
| `@time` | the field is present, and its value is a time in the form of the writer (Н0 P/01.1 «Time in a row»): a string `^(0\|[1-9][0-9]*)(\.[0-9]{1,3})?$` or a JSON number whose text in the answer body is the same notation | 1 (the Architect's decision of 2026-10-18) |
| `@not(<value>)` | the field is present, and its value is not the given JSON string (or not the bound `$имя`): so the growth of a monotonic counter is observed without fixing the number | 5 |
| `~текст` | a string value contains a substring; several substrings — separated by « ~»: `"~at rev 1 ~look again"` — both (a substring with « ~» inside is not written this way); for the body of `/metrics` of the console — a series, not a substring (the acceptance README of P/06.5 «Series») | 3; several — М11 (mutation check 2026-10-18) |
| `!contains текст` | a string value does not contain the substring | 1 |
| `<code> ~текст` | a non-JSON body (html, text) contains the substring as UTF-8 bytes; several — separated by « ~», as above | 9 |
| `<code> !contains текст` | a non-JSON body does not contain the substring (UTF-8 bytes) | 9 (reconciliation of python and go М10/6–11, C39) |
| `@header <Name>: ~<text>` after the code | a header of the answer contains the text; for a repeated header (two `Set-Cookie`) — at least one of its values | 9; repeated — reconciliation of python and go М10/6–11, C34 |
| `@header <Name>: =<text>` after the code | the header is present exactly once, and its value is equal to the text byte for byte; the text — up to the end of the cell; so a value is judged for which a substring would let a foreign address through (`Location`) | 6 (ADR-0094 B7; C06-HEADER-EXACT-01) |
| `@file <path>` after the code | the body is equal to the file byte for byte; the path — from the root of the specification | 9 |
| `<code> @empty` | the answer body is zero bytes; after `@empty` in the same cell one `@header` of the expectation is admissible | 6 (ADR-0094 B7; C06-HEADER-EXACT-01) |

A subset in `expect` does not cancel the full form of the answer per the contract of the owner of the door.

An additional check of the full key (R29-01, P/01.1-16,22): on a separate instance
with rights on acc/ check the keys of this prefix with the full length of 200, 201, 213, 1024 and 1025
UTF-8 bytes, including Cyrillic and four-byte characters. The first four pass the door rule,
1025 gives 400 badkey without a write; check the same set in a non-empty guard.key. For an existing
guard use its actual version, for an absent one — index="", so as not to fall
into the version comparison refusal. For a file implementation separately check its declared limit:
an earlier badkey is admissible, but the threshold 200 by itself is not a norm of the platform.
This is a separate harness beyond the scenario TSV; test the full UTF-8 representation, not the number of characters.

The scenarios are run through the store door (the lesson, Н2) of any implementation; the path to the door (the unix socket of a role or a stand with the same door) is a parameter of the stand. The role of the run is `acc` («Stand» above): full rights on the prefix `acc/` and on nothing else. For **each scenario, including on a repeated run**, the runner creates a new isolated instance
of the store with empty application rows and an empty memory of the write identifiers `id`. In particular,
both test prefixes are empty — `acc/` and `other/`. Cleaning the rows `acc/<scenario>/` in the previous instance
is not enough: it does not clear the replay memory. Versions need not start from a given number.

The preparation of the instance, its data directory and its rights is done by the runner before the scenario starts; the checked requests
go only from the indicated role with rights on `acc/`. Scenario 21 does not receive additional rights on `other/`: before its first step the runner in the preparation (not a checked request)
writes the row `other/21-rights/c9` `{n: "1"}` through `admin.sock` of the instance (`{socket}` of «Stand»); step 6 sees its name
and version without the value, although the role has no read rights on `other/` (Н3 «list»). In sc. 24 step 7 — the query of a `POST` is not
read, step 8 — the body of a `GET` is not read; in sc. 26 steps 9–10 — `Infinity` and a BOM in the body (Н2.1).
Parallel scenarios use different instances and share neither rows nor the `id` memory.

The parameters of each instance (Н5 of the lesson): the row ceiling **524288 bytes**, the read limit of an HTTP body
**1048576 bytes**. The runner checks both values before the scenarios by behaviour on a probe instance obtained in the same
way: a body of exactly 1048576 bytes reaches the JSON parsing (the answer is not `413`), 1048577 bytes — `413 toolarge`
with `limit` 1048576; a weight of `items` of exactly 524288 bytes is written, 524289 — `413 toolarge` with `limit` 524288.
The runner obtains an isolated instance in the way the implementation named in its description (the norms,
«Implementation decides» item 10). If the parameters cannot be provided or the check did not agree, the run is not performed;
the expected bytes must not be adjusted to the available settings.

Scenario 15 after the expansion of `@big` sends bodies of 524348 and 524344 bytes: both are smaller than the body limit,
but the weight of `items` is 524292 and 524288 bytes. So exactly the row ceiling is checked.
Scenario 22 sends a body of 4194364 bytes, more than 1048576: the refusal arises before the JSON parsing and the weight check.
The runner passes the bytes of the body from `request` after the substitutions, without re-serialization or other additions.

### Stand-in worker of the pass of the second kind

The directives of the [stand of the pass of the second kind](pass/README.md) (ADR-0094 B1). The runner executes them (the README of the pass stand, section «Executability»). The runner plays the worker: so a scenario keeps a request open and sees what reached the worker. In the directives `<cluster>` is present on the domain stand; on the console stand it is absent.

| Form | Meaning | Lesson |
|---|---|---|
| `@pass-worker [<cluster>] <sub> <name> [kit=<leaf>]` | the runner listens on a door on the loopback (with `kit` — https with the server leaf `<leaf>` of the kits of `@tls-setup`; a cluster instead of the leaf name — the leaf `<cluster>-<sub>worker`); when a worker of the same name is replaced, the runner waits until a request through the console comes to the new listener: the `url` of the issue is not named; it writes and refreshes the object `<sub>/heartbeats/<name>` with `worker`, the `url` of this door, like a live worker with a door; it keeps an accepted request open; the expectation `ok` — the console sees it alive. The previous worker `<name>` is stopped | B1 |
| `@pass-open <label> <door> <request>` | a request to the console in the background, under a label; waits until the stand-in worker accepts it. The expectation `ok <JSON>` — the accepted request by subset: `{method, path, query, body, ticket, headers}`, `ticket` — the value of `X-W2C-Pass-Ticket`, the absence of the header — `@absent`; it did not get through — the answer to the client, the form `<code> <JSON>` | B1 |
| `@pass-answer <label> <code> <Content-Type\|-> [<body>]` | the worker answers the request of the label; the expectation — the answer to the client, the forms of the dictionary | B1 |
| `@pass-chunk <label> <text>` | the worker sends a part of the stream; the expectation `<code> ~<text>` — the client has already received it, the answer is still open | B1 |
| `@pass-result <label>` | the answer to the client without an action of the worker: the worker side is silent; the expectation — the forms of the dictionary | B1 |
| `@pass-abort <label>` | the client breaks the connection; the expectation `ok` — the worker saw the close | B1 |
| `@pass-closed <label>` | the console closed the connection of the client no later than `PASS_TICKET_CHECK` + 30 s; the expectation `ok` | B1 |
| `@pass-fill <cluster> <sub>` | open requests to the route until the console answers 503 `busy`; they live until the end of the scenario; the expectation `ok` | B1 |
| `@pass-seen <name>` | how many requests the stand-in worker accepted; the expectation `ok {"requests": N}` | B1 |
| `@pass-call <client> <request>` | one probe of the door `callback <cluster>`: the callback listener, the address — `X-W2C-Pass-Console` of the last `@pass-open`, the port — `{cport}`; the client — a leaf of `stand.json` or `null`, the outcome — the closed form of `@tls`, with the substitutions `$имя` | B1 |
| `@pass-step <label> [<name>]` | wait for a step call of an operation on the stand-in worker (the route `door.pass.operations.step`, [P/06.9](../../06-console/spec/06.9-console.norms.md) Н2) and hold it: no longer than 40 s (`OPS_STEP_WAIT` + 2 × `OPS_TICK`). The expectation `ok <JSON>` — the accepted call by subset `{method, path, ticket, headers, id, index, body, secret, expected, opcount}`, `secret` without a value — `@absent`. `@pass-open` does not take step calls, `@pass-seen` counts everything accepted | ADR-0095 |
| `@pass-step-answer <label> <code> <Content-Type\|-> [<body>]` | answer the step call; the expectation `ok`. The console does not read the answer body | ADR-0095 |
| `@pass-step-none <name> <s>` | no step call came within the term; the term counts as a sleep: the lesson README names the reason; the expectation `ok` | ADR-0095 |
| `@pass-step-drop <label>` | break off the step call without an answer: a lost answer, `OPS_STEP_TRIES`; the expectation `ok` | ADR-0095 |
| `@stream-open <label> <door> <request>` | a GET stream through the door `member <cluster> console` or `console2` from the current `@person`, only on the stand without a kit, `@header Last-Event-ID` is admissible; the expectation — `<code>` or the class `2xx` of the answer headers | V/11 |
| `@stream-wait <label> <s>` | the first new message is judged: a JSON subset from `data:`, it did not match — FAIL of the step: otherwise the step would not tell a skipped message apart; a line `id:` without `data:` is not a message, it is skipped; `$имя` is bound as in the dictionary. The expectation `ok <JSON>`. The term ran out or the stream closed before a message — FAIL of the step | V/11 |
| `@stream-none <label> <s> ~<text>` | within the term there was no message with this text; the stream is closed — a mismatch: the silence of a closed stream proves nothing; the term counts as a sleep: the lesson README names the reason; the expectation `ok` | V/11 |
| `@stream-close <label>` | close the stream; the expectation `ok` | V/11 |

The substitution `{cport}` is the port of the callback listener of the console: the stand sets `CONSOLE_CALL_PORT={cport}` for a console with a kit (the environment file contract). The console profile declares `keys.pass_stand: 1`; without it the checks of this stand are not executed (not GREEN). Without a kit there is no substitution: the listener is not opened.

The door `socket [<cluster>[#<n>]] <role>` — a request to the worker role socket to the console `<PLATFORM_DIR>/run/console/<role>.sock`, in the same request form ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) Н1.5); `#<n>` — the copy of the console `console#<n>`, without a number — the first.

### Store group stand

A raft group of several store daemons on one machine of the stand — the acceptance of [chapter 1.3](../../01-store/acceptance/3/README.md)
(sc. 07, 17, 18, 25–29, 31). The properties of the group — the composition, the elections, a restart, a door without a vote, `recover`, `import` into the group — the stand
sees from outside; drills on a real cluster ([system acceptance](system/README.md)) no longer replace this
(ПРАВИЛА-РАБОТЫ.md § 4; the plan `decisions/inbox/2026-10-30-план-сценарии-группы-автоматом.md`, accepted by the Architect on
2026-10-30). The norms are P/01.3 Н1.3 (`group`, `door`, `floor`, `import`, `leader_wait`, `repeat`), Н1.6, Н3
«recover the store»; the section introduces no new norms.

- **Members** — by the name `<id>`: the voters `s1`…`s5`, the doors without a vote `d1`, `d2`. The server name of the leaf of a member is its `<id>`
  (the leaf `configstore.<id>` for a voter, `configstore-door.<id>` for a door; the role certificate contract `cert`); the addresses are the loopback
  `127.0.0.1`, the ports are handed out by the runner (free ones on the loopback; there are no addresses in the kit description): `{raft@<id>}`, `{api@<id>}` —
  substitutions in flags, requests and probes. A member learns its partners as in the norm: a joining one — by the flag `-join {api@<id>}`
  (P/01.3 Н1.3 `join`), a door — by `-voters`, a restart — from its `member.json`; the runner does not pass a list of peers. The daemon
  checks the name of a peer against the `<id>` of the participant, not against the host of the address (the address is the loopback for all).
- **Kits** — the description `inputs/group.json` of the acceptance of chapter 1.3: one CA of the group, a leaf for each member; the layout — the contract
  `kit` (`ca.pem`, `<role>/server.pem`, `<role>/server.key`), `revoked` is empty, there is no `ca.next.pem`.
- **Store build — the feature of the implementation profile `keys.store_build`**: `raft` — a build with a group, the scenarios of the stand
  are executed; `box` — the store of a box without raft, lawful per P/01.3 Н1.3 `box` (one voter; `-group-size 3`/`5`,
  `-join`, `-door` — a start refusal, code 2): the scenarios of the group stand are not_applicable, they do not enter the result and are not red, the lesson
  is credited without them; there is no feature or another value — the scenarios are not executed (not_executed, as without `keys.tls_stand`; not
  GREEN). The refusals of the build `box` are checked by sc. 04/16 of the stand store and by reading (P/01.3-01); the group stand does not judge it
  (the Architect's decision of 2026-10-30).
- **Member launch** — the store command of «Stand» (the same as for the stand store, with the speed flag of the stand if there is one) and
  the flags which the runner sets itself: `-dir {data}/<id>`, `-sockets {data}/<id>/run`, `-id <id>`, `-tls <kit dir>`,
  `-rights {rights}`, `-api {api@<id>}`, `-tuning lan`; for a voter also `-raft {raft@<id>}` (the address of the proxy of the runner,
  which the member names to its partners) and `-raft-bind <own port>` (where it listens; P/01.3 Н1.3 «Daemon flags»). The other flags — from the line
  of the directive as written (`-bootstrap`, `-join`, `-group-size`, `-force`, `-door`, `-voters`).
- **Member doors**: `store@<id> <request>` — the door of P/01.1 through the socket of the role of the scenario of the member (the role is named by the chapter README, `@as`
  changes it); `admin@<id> <request>` — through its `admin.sock` (not forwarded: the write is at the leader).
- **Boundaries**: between scenarios the runner stops all members and deletes their directories; the kits — per scenario.

| Form | Meaning | Lesson |
|---|---|---|
| `@group-setup <description path>` | as the first step of a scenario: the runner issues the kits per the description (the path — from the acceptance directory of the lesson) by its own clock; the expectation `ok`; a scenario with this step the runner plans by `keys.store_build` (above): `raft` — executes it, `box` — not_applicable, otherwise — not_executed | P/01.3 (2026-10-30) |
| `@store-start <id> [kit=<id2>] [<flags>…]` | start the member `<id>` (the flags above); `kit=<id2>` — the member `<id>` receives the kit of the member `<id2>` (its leaf and key) instead of its own: `-id <id>`, and the leaf names the server `<id2>` (the check «`-id` is the server of its own leaf», C01-DOOR-ID-CN-01); the expectation: `ok` — `admin@<id> GET /v1/status` answers 200 no later than 20 s; `@exit 2` — the process exited with code 2 no later than 10 s (a start refusal, P/01.3 Н1.3 `refuse_start`) | P/01.3 (2026-10-30) |
| `@sigterm store@<id>` / `@sigkill store@<id>` | stop the member; the data directory remains; the expectation `ok` — the process exited | P/01.3 (2026-10-30) |
| `@restart store@<id>` | start a stopped member with the same command, with the same flags, directory and kit (a restart is not a join: `member.json`, P/01.3 Н1.3 `join`); the expectation — as for `@store-start` | P/01.3 (2026-10-30) |
| `@cut store@<id>` / `@mend store@<id>` | the proxy of the runner on the raft address of the voter `<id>` breaks the live incoming connections and does not accept new ones / lets them through again; the outgoing connections of the member go to the others directly (on one machine they cannot be cut) — the member does not receive the journal entries and the heartbeats of the leader; `-api` is not cut; the expectation `ok` — the proxy has switched | P/01.3 (the coverage audit of P/01, 2026-10-30) |
| `@store-op <id> <operation> [<arguments>…]` | an operator operation of P/01.3 Н1.3 `admin_ops` in the words of the command line, as in the norm (`admit s3`, `import --from inputs/copy-ok.jsonl -index-base 7`, `recover -peers … -isolated`), by the command `store-op` of «Stand» — a template with `{socket}` (the `admin.sock` of the member), `{dir}` (its `-dir`), `{id}`, `{tls}` (the kit directory) and `{args}`; for `recover` the member is stopped, the command works with its `-dir`, `-id` (Н3 «recover» step 1); `{raft@…}`, `{api@…}` are substituted, the path `inputs/…` — from the acceptance directory of the lesson; the expectation: `ok` — code 0; `refused` — code ≠ 0; the output is not compared | P/01.3 (2026-10-30) |
| `@tls <probe path>` with the door `raft@<id>` | a probe to the raft port of the voter (its real port, not the proxy of `@cut`): the input `{door: "raft@<id>", client: "<id2>", request: null}` — only a handshake, there is no request; the client presents the leaf of the member `<id2>`; the outcome — the closed form of the README `tls/` (`handshake: alert` — `http: null`) | P/01.3 Н1.6 `raft` (C01-RAFT-DOOR-LEAF-01) |
| `@tls <probe path>` with the door `api@<id>` | a probe to the `-api` of the member: the input `{door: "api@<id>", client: "<id2>", request}` — the client presents the leaf of the member `<id2>` of the description `group.json`, checks the server by the CA of the group and `<id>`; the outcome — the closed form of the README `tls/`; the role forwarding header in `request` is a designation, the name is substituted from the description of the implementation by the same profile key as `X-Configstore-Role` in the acceptance of chapter 1.2 sc. 08 | P/01.3 (2026-10-30) |

### Three-server cluster stand

Three platform servers on one machine of the stand — sc. 05 of the [system acceptance](system/README.md). A server failure, the move of units and
the return the stand sees from outside, so a drill on a real cluster no longer replaces them (ПРАВИЛА-РАБОТЫ.md § 4; stage 2 of the plan
`decisions/inbox/2026-10-30-план-сценарии-группы-автоматом.md`). The norms are P/04 Н1.4а, Н3 «pull the power», P/05 Н1.4, P/01.3 Н1.3, P/02.4 Н3
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
  The scenario does not switch off `srv-a`: a new controller judges no one for the first `LOST_AFTER` (P/04 Н1.4а `fresh_controller`), and
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
| `@server-start <name>` | bring up a server: the store member, then the resource. The flags of the member — as for `@store-start`, the runner chooses the join by the order of the directives in the scenario: the first — `-bootstrap -group-size 3`, the second — `-join {api@<first>} -group-size 3 -force`, the third — `-join {api@<first>} -group-size 3` (assembly 1→2→3, C01-GROUP-BOOTSTRAP-EVEN-01). On the first server, after the member is ready, the runner sets up the manifests (`manifest-put`, the order — «Manifests» above) through its `admin.sock` and starts the console, then the resource. The role files of the resource — as for `@start resource on <server>`. The expectation `ok` — `admin@<name> GET /v1/status` answers 200, the resource port listens and the row `platform/doors/<name>` exists, all no later than 20 s | system (2026-10-31) |
| `@power-pull <name>` | pull the power: the proxy of the runner on the raft address of the member breaks the live connections and does not accept new ones (like `@cut store@<id>`), then the runner immediately sends SIGKILL to all processes of the server — the member, the resource, the workers; it does not touch the directories. There is no proxy on the resource door, because the resource names the address of its door itself: after SIGKILL its port is closed. The expectation `ok` — all processes exited; this moment is `t = 0` of the drill. `<name>` — a server that is up, not the server of the console and the controllers; otherwise a data error when the step is executed | system (2026-10-31) |
| `@power-back <name>` | return the power: the same directories, ports, kit. The proxy lets through again; the member is started with the previous command and the previous flags without `-bootstrap`, `-join`, `-force`: it takes its partners from `member.json` (P/01.3 Н1.3 `join`; P/02.4 Н3 «server start» step 1), and only so the steps below prove a restart without a join. Then the resource — with the same command, with the same `{rport}`. The directive does not start workers; they are returned by the steps `@start worker … on <name>`. The expectation — as for `@server-start` | system (2026-10-31) |
| `@restart resource#<name>` | SIGTERM to the resource of the server, wait for the exit, start it with the same command with the same `{rport}` and directory; the expectation `ok` — the port listens and the door row exists no later than 20 s. The first pass goes at the start (P/05 Н1.4 `pass`), so the scenario gets a mirror pass without waiting 600 s | system (2026-10-31) |
| `@append event on <name> <tree>/<unit>/e<epoch> <text>` | like `@append event` of the dictionary, but into the event root of the server `<name>` (`<PLATFORM_DIR>/events`) | system (2026-10-31) |
| `@append event-closed on <name> <tree>/<unit>/e<epoch> <text>` | like the row above, but into the bucket of the previous window: `начало = floor(now / 600) × 600 − 600`; such a bucket is already closed (the event journal contract `span`: closed when end ≤ now). `{now}` in the text is `начало + 300`, because the `t` of the line chooses the bucket. After `ok` the runner binds `$closed` — the path of the bucket `<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`. The real closing cannot be waited for: up to 600 s per window and up to 600 s more for the mirror pass | system (2026-10-31) |
| door `resource#<name> <request>` | the door of the resource of the server `<name>` on its `{rport}` with an admissible identity; `#` here is the name of the server, not the number of a copy as in `@sigkill resource#1` | system (2026-10-31) |
| door `admin@<name> <request>` | the door of a member per «Store group stand»; sc. 05 reads and writes through it, because it needs the rows of all families | P/01.3 (2026-10-30) |

### Domain stand

The stand of several clusters: the acceptances of the chapters of lesson 8 ([`08-domain/acceptance/`](../../08-domain/acceptance/)), of the chapters 6.7, 9, 10 and
of the [TLS stand](tls/README.md); the domain vectors not yet moved into packages are also here.
Moved as it is from «Словарь директив и дверей М11» of the acceptance README of М11/01 (the directory was removed by the move of lesson 8) (stage B,
lesson 8; the move plan of lesson 8, V5). The section relies on «Stand» and «Dictionary of directives and doors» above; the column «Lesson» —
as there (`М11/N` — the lesson of М11 that introduced the form). The acceptance README of a chapter names its own preparation; the common preparation
of the clusters `hold`, `m1`, `m2` is «Preparation of each scenario» of the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md)
(«Stand»).

#### Domain vector commands

| Door or form | Meaning | Lesson |
|---|---|---|
| `view <entry path>` | the command `view` of the implementation: a template with `{input}` — the path of the file with the input; the input — the column `input` of the package [`08-domain/vectors/view`](../../08-domain/vectors/view/README.md) (the form `ViewInput`), stdout — `ViewOutput` ([OpenAPI P/08](../../08-domain/spec/08-domain.api.openapi.yaml)); code 0 — computed, `@exit 2` — the input is not in form (review analysis of stage B 8–10, № 22: M-1) | М11/1 |
| `keys <entry path>`, `token <entry path>`, `seal <entry path>`, `seal-round <entry path>` | the commands of chapter P/08.2 of the implementation: a template with `{input}`; the input and stdout — the forms of [P/08.2 Н5](../../08-domain/spec/08.2-domain.norms.md); code 0 — computed, including a refusal by a word (`{"result": "refused", "reason": …}`), 2 — the input is not in form | М11/2 |
| `ok <JSON>` in an expectation | the exit code 0 and stdout is JSON, which is compared by a subset of fields (the dictionary above) | М11/1 |
| `agent-sig`, `seal-member`, `seal-member-round`, `accept` `<entry path>` | commands of the implementation, like the doors of М11/2 ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) «Implementation decides» item 1): the forms of the input and the output — the contracts of the [agent signature](../contracts/agent-signature.md), the [domain envelopes](../contracts/domain-envelopes.md) and the [report admission](../contracts/accept.md) (review analysis of stage B 8–10, № 6, № 22: M-1) | М11/3 |
| `assemble`, `issue` `<entry path>` | the commands of М11/5 and М11/7: the forms — Н5 of their norms (now [P/08.5 Н5](../../08-domain/spec/08.5-domain.norms.md) and [P/08.7 Н5](../../08-domain/spec/08.7-domain.norms.md)) | М11/5, М11/7 |
| `peer`, `may`, `record`, `follow`, `ask-sig`, `resolve`, `alarms` `<entry path>` | the commands of М11/8–11: a template with `{input}`; the forms of the input and the output — Н5 of their norms (`may` — now [P/08.4 Н5](../../08-domain/spec/08.4-domain.norms.md), `record`, `ask-sig` — [P/08.8 Н5](../../08-domain/spec/08.8-domain.norms.md), `peer` — [the contract `peer`](../contracts/peer.md), `follow` — [P/09.1 Н5](../../09-agent/spec/09.1-agent.norms.md), `resolve` — [P/06.7 Н5](../../06-console/spec/06.7-console.norms.md), the package `06-console/vectors/resolve`, `alarms` — [P/10 Н5](../../10-domain-console/spec/10-domain-console.norms.md), the package `10-domain-console/vectors/alarms`); code 0 — computed (including a refusal by a word), 2 — the input is not in form | `peer` — М11/8, `may` — М11/9, `record`, `follow`, `ask-sig` — М11/10, `resolve`, `alarms` — М11/11 |

**Exit codes of the vector commands of М11** (the Architect's decision on the reconciliation of М11, H14). Code 2 — the form of what the caller takes from its
trusted state is violated: `keys`, `pub`, `cluster`, `field`, `domain`, `now`, `lost_after`, the names of the members, `history`, the rows
`grants`. Code 0 with a word — a document is bad which the function by the norm evaluates itself because it came from another
cluster: `row` and `held` (through `record`), `answers.<cluster>`, `page`. The function does not recheck a trusted input beyond the
form (for example, the signature of the set `keys` is checked at the write — P/08.2 Н3 keys). The expectation of the code is `@exit 2` (the dictionary above);
the cases without a step are listed by Н5 of the lesson.

#### Multi-cluster stand

**Clusters** (М11/3). The clusters `hold` (the holder), `m1`, `m2` — each with its own store, `{data}`,
role sockets, ports and ring (the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md), 
«Preparation of each scenario»). Substitutions: `{domain}` — `acme`, `{recovery}` — the recovery file of the installation in the directory of the instance. Between
the agent of each cluster and the door of the holder the runner keeps its own TCP proxy: the `DOMAIN_URL` of the agent points to it.

The substitutions of the commands of the domain stand (their templates are named by the description of the implementation, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) and [P/09.1](../../09-agent/spec/09.1-agent.norms.md) «Implementation decides»; review analysis of stage B 8–10, № 22: M-1): for the commands of the processes
of a cluster — `{data}` and `{socket}` of its cluster, `{port}` — the port of the door of this process; for the installation and `join` — `{domain}` and
`{recovery}` (for `@join <cluster> <file>` `{recovery}` is the named file). The runner gives out the recovery file as a copy with the mode
0600: git keeps `inputs/*.json` with 0644, and the implementation checks the mode when reading (P/08.2 Н1.1 `mode`; the reconciliation of М11, I3). The agent
receives the environment `CLUSTER`, `DOMAIN_URL` (the proxy) or `RELAY_URL` (P/09.1), with `@clock` — `W2C_WALL_OFFSET`.

| Door or directive | Meaning | Lesson |
|---|---|---|
| `holder <request>` | the domain console on `hold` (the doors `/domain/*`); the runner sets `Idempotency-Key` on `POST`, `PUT` and `DELETE` of this door by the rule `@key` of the dictionary above (М11/6: domain edits require a key on all three; for the doors of [P/08.0](../../08-domain/spec/08.0-domain.norms.md) Н1.9 the key is optional, and a step with a key sets the replay memory, so such a step does not go under `@until`) | М11/3; the key — М11/6 |
| `member <cluster> <door> <request>` | the door `store` (`admin.sock`), `console`, `console2` (the prefix `/testsub2`, М11/5) or `resource` of the cluster `hold`, `m1`, `m2`; `store`, `console`, `resource` without a prefix — of the cluster `hold` | М11/3 |
| `@install domain` | the domain installation command (P/08.2 «Implementation decides» item 2) on `hold` with `{domain}` and `{recovery}`; then the command `domain first-admin root` (P/08.4 Н1.9 `first`) with the password `w2c test root password` (the directive `@admin`) | М11/3; `@admin` — М11/9 |
| `@start domain` | the processes `domain` and the domain console on `hold`; at the first start after `@install domain` the runner logs in as the person `root` (`signer POST /api/login`) and writes `holder PUT /domain/grants/<cluster> {lines: [{subject: root, cap: admin, scope: "*"}]}` for each cluster of the stand (`hold`, `m1`, `m2`, `relay`; with `@clusters` — each one named there, including `m3`; review analysis of stage B 8–10, № 22: M-18) — the grants are prepared before the admission | М11/3; the login — М11/9 |
| `signer <request>` | the door of the process `domain` on `hold` through the proxy of the runner (the same as the `DOMAIN_URL` of the agents) — the login `POST /api/login` | М11/9 |
| `@person <name> <password>` / `@person -` | the runner logs in as this person (`signer POST /api/login`; the password — the rest of the line) and from then on sets `Authorization: Bearer <its token>` on the doors `holder`, `holder@…`, `member … console`, `console2` of this scenario, and for the command `@move`, logging in again on expiry; `-` — without a token. After `@start domain` the current person is `root`; before the domain there is no header. `@header Authorization: …` of a step replaces it | М11/9 |
| `@restart domain` | SIGTERM to both, wait for the exit, start again with the same `{data}` | М11/3 |
| `@start agent <cluster>` | the agent of the cluster: `CLUSTER=<cluster>`, `DOMAIN_URL` — the proxy of the runner to the door `domain` | М11/3 |
| `@start agent <cluster> via <relay>` | the agent of the cluster behind a relay: `RELAY_URL` — the proxy of the runner to the door of the relay (`DOMAIN_URL` is not set); for a relay with copies (`@start agent <relay> second`) — the proxies of all copies separated by commas by the copy number (P/09.2 Н1.1 `door`) | P/09.1 |
| `@start agent <cluster> second` | one more copy of the agent of the cluster — «another server» of the cluster: the same environment, its own process and instance, its own `AGENT_TOKEN_DIR` (the sockets of the local door of this copy — `token <cluster>#<n>`); for a relay cluster (`RELAY=1`) — its own relay door through its own proxy of the runner; the copies are numbered in the order of the start: the first — `agent#1`, then `#2`, `#3`…; the expectation `ok` — the process is alive | P/09.1 Н1.13 (DOM-AGENT-TURN-01) |
| `@stop agent <cluster>` | SIGTERM to the agent of the cluster (to all copies), wait for the exit | P/09.1 |
| `@join <cluster> [<file>] [batch=<name> <$key>]` | the command `join` ([P/09.1](../../09-agent/spec/09.1-agent.norms.md) Н1.1; review analysis of stage B 8–10, № 22: M-1) on the cluster: the domain and `root_pub` from `{recovery}` or from the named recovery file — the runner gives out a copy with the mode 0600; with `batch=` — the template `join-batch` instead of `join` (the input `batch` of the command, P/08.3 Н1.1б): the substitutions `{batch}` — the name of the batch, `{batch_key}` — the path of the file with the private key (the bound `$имя` from the answer of `POST /domain/batches`): the runner writes the key into a file with the mode 0600, like `{recovery}`, — the key does not get into argv and the process log; the template `join` has no such substitutions; the member class is `camera`; the expectation — `ok` or `refused` (the command refused, code ≠ 0) | М11/3; the batch — ADR-0113, roadmap 4.5 |
| `@domain [<cluster>…]` | the preparation «domain with members»: `@install domain`, `@start domain`, the agents of `hold` and of the named clusters (without a list — `m1`, `m2`), the admission of each by the fingerprint from `knocking` (`POST /domain/members`), the `@join` of each; it is ready when `holder GET /domain` is `complete: true`, all of them are `ok` and each holds the set of the holder: `reports.<member>.keys_rev` of the view = the `rev` of the document `domain/keys` of the store of `hold` (no longer than 90 s; otherwise an edit of the console of a member right after `@domain` would meet `shut`, М11/2 Н1.8) | М11/3, the list — М11/4 |
| `@cut <cluster>` / `@mend <cluster>` | the proxy of the runner breaks the connections of the agent of the cluster with the holder and does not accept new ones / accepts them again; the implementation needs nothing | М11/3 |
| `@clock <cluster> <±N>` | restart the agent of the cluster with `W2C_WALL_OFFSET=<N>` (seconds added to its wall clock; `0` — without a shift), the rest of the environment — as before (the road through the relay remains); the agent is not running — start it so | М11/3 |
| `token <cluster>[#<n>] <role> <request>` | the local door of the agent of the cluster (`#<n>` — of the copy `agent#<n>`, without it — of the first) with the identity of the role `<role>`: the socket `<AGENT_TOKEN_DIR>/<role>.sock` ([local token door contract](../contracts/local-token-door.md) «The role socket»; review analysis of stage A 8–10, decision 1); the `AGENT_TOKEN_DIR` of the agent on the stand — the runner (P/08.7 «Implementation decides» item 1) | М11/7 |
| `@verify <cluster> <kind> <$token>` | the command `token` of chapter P/08.2 of the implementation on the input `{keys: doc строки domain/keys кластера, revoked: его строка domain/revoked, now: стенные секунды раннера, token, expect: {kind: <kind>, cluster: <cluster>, audience_claim: из объявления вида}}`; the expectation — `ok <JSON>` | М11/7 |
| `holder@<cluster> <request>` | the domain console on this cluster (after a move or a handover; `holder` — the same on `hold`) | М11/10 |
| `@start domain on <cluster>` | the processes `domain` and the domain console on a cluster without an installation (a signer without keys waits for a move or a handover); the console of the cluster is restarted with `SIGNER_URL` to its door, the process `domain` — with `DOMAIN_CONSOLE_URL` and the `SIGNER_URL` of its own door through the proxy of the runner (the address of the term record, P/08.8 Н1.1) | М11/10 |
| `@stop domain [<cluster>]` | SIGTERM to the processes `domain` and the domain console of the cluster (without a name — `hold`), wait for the exit; `@start domain` brings them up again on `hold` with the same `{data}` | М11/10 |
| `@move <cluster> [stolen] [copy=<term>.<rev>] [why=<words to the end of the line>]` | `w2cctl domain move` ([P/08.8 Н1.8](../../08-domain/spec/08.8-domain.norms.md)) to the door of the console of the cluster with the file `{recovery}` of the installation — the runner gives out a copy with the mode 0600; the identity of the command is the current person `@person` (after `@start domain` — `root`; `@person -` — without an identity): the runner passes their token to the command in the way of the implementation profile (the identity of the door — P/08.8 Н1.8); the expectation — as for a door: `<code> <JSON>` of the answer | М11/10 |
| `@on <cluster> <directive>` | a directive of the dictionary above (`@start`, `@sigterm`, `@sigkill`, `@freeze`, `@thaw`, `@put object`, `@spoil object`, `@append event`, `@append event-raw`) on this cluster — only these, another word is a data error before the scenario starts; `@append event` and `@append event-raw` — into the event root of the resource of this cluster | М11/3; objects — М11/11; `@append event` — C06-EVENTS-VIEW-33-01; `@freeze`, `@thaw` — P/08 (the coverage audit of P/08, 2026-10-30) |
| `@on <cluster> @start console#<n>` | a copy of the console of the cluster, `<n>` 2–9, only on the stand without a kit: there is one console per server, so a copy is like another server: its own `{data}`, `PLATFORM_DIR`, `SERVER_NAME` `<server>-<n>`, `BOX_ID`, `CONSOLE_PORT`; the store and the ring of the first server. The expectation `ok` — the port listens. The door `member <cluster> console#<n>`, the signals and `@freeze` — by the name of the copy, `console` without a number — the first | ADR-0095 |
| `@env <cluster> <NAME>=<value>` / `@env <cluster> <NAME>` | restart the console and the agent of the cluster with the environment variable `<NAME>` equal to the value (an empty value — the variable is empty); without `=` — return the default value of the runner (the paragraph «Forwarding environment» below); the value `inputs/…` — a path from the acceptance directory of the lesson | М11/8 |
| `@start domain second` | a second copy of the process `domain` on `hold` with the same `{data}` and its own `{port}`; the copies — `domain#1` (the previous one) and `domain#2`; the proxy of the runner (the `DOMAIN_URL` of the agents, the door `signer`) leads to the first live copy by number; `@on hold @sigterm domain#1` (`@sigterm <name>[#n]` of the dictionary above: `#n` of `@sigterm` — added by М11/12) stops the first; `@stop domain` — both | М11/12 |
| `signer2 <request>` | the door of the second copy of the process `domain` on `hold` directly, without a proxy | М11/12 |
| `@carry <cluster>` | the 200 answer of the holder to the last `POST /api/member/<cluster>` that went through the proxy of the runner; the expectation — `ok <JSON>`, the comparison — by a subset of fields | М11/12 |
| `@clusters <cluster>…` | before the first operation that creates the stand: the cluster instances of the scenario (`@clusters hold m1 m2 m3` — a fourth cluster); without the directive — the former composition of the lesson; a repeat or another composition after the creation — a scenario error, not a restart | М11/8 (ADR-0083 addendum (9)) |
| `@tls-setup <description path>` | before the stand is created: TLS between the clusters per the kit description ([`Platform/common/acceptance/tls/`](tls/README.md), the path — from the acceptance directory of the lesson); the runner issues the kits by its own clock, puts them into the `W2C_TLS_DIR` of the clusters and gives `DOMAIN_CA`; the proxies only pass bytes through; the implementation profile — `keys.tls_stand: 1`, otherwise the check is not executed; it does not change the kits after the start | М11/8 (ADR-0083 addendum (9)) |
| `@kit-start <role> <комплект\|none> [<NAME>=<value>…]` | one role process on the box of the stand with the command of «Stand»: `W2C_TLS_DIR` — the directory of the kit `<kit>` of the description of `@tls-setup` (`named`), `none` — an empty directory (there is no kit); `SERVER_NAME` — the `server` of the kit (`none` — `box-n`); the rest of the environment — the default of the runner, `<NAME>=<value>` — on top of it (an empty value — the variable is empty, as for `@env`); the runner stops the process of the previous `@kit-start` before the start, the last one — at the end of the scenario. The expectation: `ok` — the role port listens no later than 20 s; `@exit 2` — the process exited with code 2 no later than 10 s; `ok ~<text>[ ~<text>…]` — it listens, and the log of exactly this launch contains each substring. Its door is the `kit` of the probe `@tls` (README `tls/`) | ADR-0075 addendum 2026-10-26 (4) item 7, (5) item 4 |
| `@tls-kit <cluster> console <kit>` | the replacement of the TLS kit of one console of the cluster: the runner restarts only it with the previous port and data and the kit directory `<kit>` (`foreign` — a rotation to a foreign CA, `<cluster>` — the original one, a return); the other processes and the published CAs do not change; the expectation `ok` — the console listens again; the composition of the kits and the check of the server by the client — [README `tls/`](tls/README.md) | TLS № 14 (ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 22) |
| `@tls <probe path>` | one probe of a door by the common TLS client of the runner: the input `{door, client, version?, request, save_session?, resume_session?}` (the doors `holder`, `signer`, `member <cluster> console`; the client — a leaf of the description or `null`; the client presents the leaf on any certificate request, regardless of the list of CAs in the request, without a request it does not send it, ADR-0083 addendum (20), addendum (21) item 9); the expectation — `ok <JSON>`: the closed outcome `{handshake, version, reused, session_available, http}` by subset (the form `ok <JSON>` of the dictionary above; the reading of the commits of «cammeta-acceptance» tls-stand 2026-10-20); a connection refusal, a break, a timeout, an error of the server check and of the tool — the class «stand», not an outcome (README `tls/`) | М11/8 (ADR-0083 addendum (9)) |
| `@cut-route <from> <to> console` / `@mend-route <from> <to> console` | the proxy of the runner breaks and does not accept new / accepts again the connections of only the directed road from the console (and the move process) of the cluster `<from>` to the console of the cluster `<to>`; `@cut <cluster>` is still the road of the agent to the holder | М11/8 (ADR-0083 addendum (9)) |

**Relay** (P/09.2): the fourth cluster of the stand `relay`; its agent always opens the relay door
(`RELAY=1`, the port `{relay_port}` of the instance), and a proxy of the runner stands in front of it too. `@cut relay` breaks the road of the relay
to the holder; the doors of the members to the relay are their own proxies (`@cut <member>` breaks the road of the member, whatever it is).

**Forwarding environment** (М11/8; `@env` — [P/06.7](../../06-console/spec/06.7-console.norms.md) «Implementation decides» item 2): the console of each cluster receives `CLUSTERS` — the addresses of the consoles of all clusters of the stand
(`hold=<url>,m1=<url>,m2=<url>[,relay=<url>]`, without proxies); the process `domain` — `DOMAIN_CONSOLE_URL`, the address of the door
of the domain console; `SIGNER_URL` — only the console of `hold`. The stand has no TLS kit: the doors on the loopback over `http://`
(P/02.4 Н1.6). The runner sets `Idempotency-Key` on `POST`, `PUT`, `DELETE` of the path `/domain/…` of the door `member <cluster> console`,
as for the door `holder`.

**Expectations** of the domain stand are the forms of the dictionary above: `<code> <JSON>` by subset, `$имя`, `@spoil($имя)`, `@any`/`@absent`,
`@not`, `@time`, `~текст` (for example `~enc:v2:` — the envelope of the ring of a member), `!contains`, `@exit`; for the vector commands and `@carry` —
`ok <JSON>`, for `@join` — `ok` or `refused`, for `@move` — `<code> <JSON>` of the answer of the door. Sleeps (`@sleep`) with reasons — in the acceptance README
of the chapter.

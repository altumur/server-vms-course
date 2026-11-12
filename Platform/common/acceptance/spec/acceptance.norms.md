# P/AC — The acceptance judge: norms

This English text is the source; the Russian translation `ru/acceptance/spec/acceptance.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of the shared acceptance lesson. [Instructions](acceptance.README.md), [the common stand and its dictionary](../README.md), [profiles and assembly](../PROFILE.md), [target registry](../forms/targets.README.md). The judge is the program that checks a generated implementation against this specification; the common acceptance README calls it the runner. The lesson has no process of its own and opens no door of the implementation. Norm ids are `P/AC-NN`; requirement anchors `P/AC-RNNN` are in this source only.

### Index

Existing rules by topic; paths are from `common/`.

| Topic | Requirements | Files |
|---|---|---|
| `vector_dispatch` target surface and callable | P/AC-R006 | `acceptance/runner-targets.README.md`, `vectors/wire.md`, `acceptance/forms/targets.tsv` |
| `row_inventory` grouped vector calls and diagnostic hints | P/AC-R004, P/AC-R008 | `vectors/wire.md`, `acceptance/PROFILE.md`, `acceptance/command-tables.md` |
| `store_doors` store headers, list order, TLS outcomes and full response form | P/01.1-R065, P/01.2-R017, P/01.3-R059, P/01.3-R211 | `acceptance/README.md`, `../01-store/acceptance/1/README.md`, `../01-store/acceptance/2/README.md`, `../01-store/acceptance/3/README.md` |
| `source_binding` Source seam normalization and missing dispatch | P/AC-R030, P/AC-R050 | `acceptance/seams.md` |
| `scope_and_directives` selected targets and known directive support | P/AC-R020, P/AC-R024, P/AC-R029 | `acceptance/README.md`, `acceptance/domain-stand.md`, `acceptance/pass/README.md` |
| `production_binding` missing qualification inputs and instrument failures | P/AC-R024, P/AC-R047, P/AC-R050 | `acceptance/seams.md`, `../01-store/forms/production.tsv` |
| `preflight_and_abort` scenario preflight and preparation abort | P/AC-R015, P/AC-R030, P/AC-R033 | `acceptance/PROFILE.md` |
| `command_failure` product commands, judge commands and abort | P/AC-R024, P/AC-R033, P/AC-R038 | `acceptance/seams.md`, `acceptance/stand.md` |
| `until_form` read repetition and malformed directives | P/AC-R020, P/AC-R024 | `acceptance/README.md` |
| `object_spoil_order` explicit stop before object spoil | P/AC-R017, P/AC-R020 | `acceptance/README.md` |

## N0 Scope and normative words

<!-- req: P/AC-R001 -->

Normative keywords follow the [course canon](../../NORMATIVE-TERMS.md). This lesson sets what the judge does and what it observes. It sets no behaviour of an implementation: the norms and the acceptance tables of each lesson remain the source of what an implementation must do, and the common stand gives the words in which the tables say it.

<!-- req: P/AC-R002 -->

The judge is one shared engine. A lesson is only data. The engine branches only on the closed words of this lesson and of the [dictionary of directives and doors](../README.md#dictionary-of-directives-and-doors), never on a literal lesson, target or package name. A step of a lesson that the dictionary does not express is a gap of the specification, not a reason for lesson-specific code.

<!-- req: P/AC-R029 -->

The first wave of the engine is the targets of P/01 with a stand, scenarios or vectors. The production qualification of P/01 (N6) is in it. Outside it are the judgement of families (the package `common/family-read`), the stands of consoles and of several clusters (the target `system/05-power-pull` among them), VMS, and the suites TLS and ER of [`tls/README.md`](../tls/README.md): the steps of those suites are written there as prose and their table is a separate piece of work. The registry keeps these targets; the first wave is a selection of the run, not a branch of the engine.

## N1 Forms

### N1.1 Scenario tables

<!-- req: P/AC-R003 -->

The judge reads every `scenarios.tsv` by the row form of the [dictionary](../README.md#dictionary-of-directives-and-doors) and every `seams.tsv` by the [seam adapter protocol](../seams.md#seam-adapter-protocol) and the seam grammar of its owner, and every table of the engine words `verdicts`, `puts` and `variants` by its form of the [command tables](../command-tables.md#command-tables). It reads a table whole before the stand of the target starts. A table cell declared `# cell-json:` follows the [source-cell form](../../contracts/source-cells.md).

### N1.2 Vector tables

<!-- req: P/AC-R004 -->

Vector tables, their consumers, input columns, fixtures, expectations and comparisons are defined by the [vector wire form](../../vectors/wire.md), its `wire.tsv`, `consumers.tsv` and `compare-scope.tsv` (the scope of the comparison words), and the README of each package. The older Platform vector commands keep the form of the [common stand](../stand.md#layout-by-processes-stage-c).

<!-- req: P/AC-R005 -->

In a table with a header, a row whose cell count differs from the header is a data error of that table; the judge reports it without judging the row. A table assigned to a consumer and absent from the export is a data error, not an empty table.

### N1.3 Target registry

<!-- req: P/AC-R006 -->

The targets are the rows of the registry: the public table [`forms/targets.tsv`](../forms/targets.README.md) and the judge-side routing table `forms/targets.routing.tsv` in the same directory, each assembled from its common header and the rows of the lessons ([assembly](../tables.md#target-registry-and-export-lists-assembled-from-the-lessons)). The routing table has one row for each `id` of the public table and repeats no other column. A target's owner, interfaces, keys, requirement anchors and flags come only from the public table; its engine family, acceptance directories, scenario selection, parts of other lessons and the comparison mode of answer bodies (`body`) and the initial role of its doors `store` and `store@<id>` (`role`) come only from the routing table; a lesson or a chapter name sets no comparison mode and no role. The [target requirements](../runner-targets.README.md) define the columns they share. In a routing row the first directory holds the table the target executes and the selection of scenarios applies to it alone; the other directories hold only its inputs. The column `tables` names the files whose rows the target executes besides that table; an engine word makes no directory executable.

### N1.4 Verdict of a target

<!-- req: P/AC-R007 -->

The result of a target is GREEN, red, `not_executed`, `not_applicable` or `blocked`:

| Result | Meaning |
|---|---|
| GREEN | every inventoried automatic row or step of the target was executed and matched; a step `@manual` takes no part in it (R052) |
| red | a row or step did not match, or the target failed with a class of N4 |
| `not_executed` | a scenario, row or target could not run; the result names one of the closed reasons below and is not GREEN |
| `not_applicable` | a key of the profile selects a build for which the target has no meaning, as `keys.store_build: box` for a group stand; the target does not enter the result and is not red |
| `blocked` | a required interface or part of the composition is absent before execution; this is not a test result |

<!-- req: P/AC-R030 -->

The reason of a `not_executed` result is one of the closed list: `installer_ceiling_unproven`, for a row of `puts` with the column `ceiling` whose store ceiling the judge could not confirm; `installer_rights_check_missing`, for a row of `check.tsv` of a rights variant when the profile has no `stand.rights-check`; `store_rights_template`, for a scenario with `@rights store` when the command template of the stand store holds the flag `-rights {rights}` or `-rights={rights}` not exactly once; `store_spoil_row_missing`, for a scenario with `@spoil row` or `@spoil row-index` when the profile has no `stand.spoil-row`; `stage_package_not_exported`, for a target a directory of whose routing row (the column `acceptance` of [`forms/targets.routing.tsv`](../forms/targets.routing.tsv)) is not in the judge input: the pinned export does not publish that directory, and the target runs none of its rows; a table that a published directory assigns to a consumer and that is absent from it stays a data error by N1.2; `no_machine_form`, for a probe of [`forms/extra.tsv`](../../../01-store/forms/extra.tsv) whose `id` names no scenario of the files of the column `tables` of its target; `io_counter_unreadable`, for a step `@io` whose counter the judge cannot read and the steps that compare its name; `precondition:<id>`, for every other case of a target whose row `<id>` of `forms/extra.tsv` has the kind `precondition`, runs before them and is red; `manual_only`, for a target whose selection holds no automatic row or step (R052); `MissingBinding`, when a case outside the target `P/01/production` needs a test-side input of R050 that the invocation does not name; the reasons of the table of N6.5 for the target `P/01/production`, which there also name a missing test-side input; the name of a profile key that the column `keys` of the target's row of the registry names, when the key is absent or has a value of its type that the target does not accept: such a key is required by that target whatever the column `absent` of [`forms/profile-keys.tsv`](../forms/profile-keys.tsv) says, a value outside its type is the column `outside` of that form, and a value for which the target has no meaning is `not_applicable` (R007); or the name of a public interface that a target with the flag `optional` requires and that is absent: without that flag the target is `blocked` (R007, R015). For the steps that an abort of a scenario leaves unrun the reason is the scenario and the number of the step whose failure ended it; that step keeps its own class. An `ASSERT` step runs like any other step and matches or does not; it is `not_executed` only when a name it compares is unbound because the earlier step that names it did not match or matched an `@oneof` branch that does not bind it, and then its reason is the scenario and the number of the latest earlier step of the scenario that names that name.

<!-- req: P/AC-R052 -->

A step `@manual` of the [dictionary](../README.md#dictionary-of-directives-and-doors) is in the inventory of its target (R008) and is not executed. Its result in the report is the closed word `manual`: it is neither GREEN, nor red, nor `not_executed`, and it does not take GREEN from the target. GREEN of a target and the gate of R009 count only the automatic rows and steps. A target whose selection holds no automatic row or step is `not_executed` with the reason `manual_only` (R030).

<!-- req: P/AC-R031 -->

Every `not_executed` row or scenario of a target takes GREEN from it. There is no exception: a debt row of a stand takes GREEN away like any other, and the result of the target says so.

<!-- req: P/AC-R032 -->

A target that is `not_executed`, `not_applicable` or `blocked` does not stop the other targets of the run.

<!-- req: P/AC-R008 -->

Before running a target, the judge builds an inventory of what it will run: for scenarios — their names, order, steps, source lines and manual steps; for vector rows — the identity of the row of [the unified vector command](../PROFILE.md#unified-vector-command); for the rows of the files of the column `tables` of the routing and of the [command tables](../command-tables.md#command-tables) of the engine words `verdicts`, `puts` and `variants` — the file and the number of the physical line of the row. A target is GREEN only if its result equals this inventory, at least one row or step ran, all its processes were cleaned up and the sealed inputs did not change. A result that does not agree with the inventory is red with the class `runner`.

<!-- req: P/AC-R009 -->

The gate `accept:<chapter>:<scenarios>` of a stage reads per scenario: a scenario is green when its steps equal the inventory, it has automatic steps and they all matched. A failure of the stand or an unreadable result leaves no green scenario.

### N1.5 Report and secrets

<!-- req: P/AC-R010 -->

A report given to the line that generates the implementation carries the name of a case, a norm anchor, the class of the mismatch and the tail of the stderr of a failed case, never an expected answer. The tail is at most 4 KiB, and every substring of at least 8 bytes that occurs in the inputs, fixtures or expectations of the case is cut out of it. A case name that exists only on the judge side is replaced by an opaque identifier, constant within the run, in such a report and in the `case` of a request to the implementation.

<!-- req: P/AC-R011 -->

The report does not give out response bodies, stdout, stderr or the values of secrets: it gives at most the length, the digest and the content type of such a value. For every judged step that received a response, the report gives the length in bytes, the SHA-256 digest and the content type of its body; a red step is never reported without them. A secret is the value of a field whose name contains `token` or equals `authorization`, the value after `Bearer ` and the base64, base64url and hexadecimal encodings of these values, and a value the judge itself gave out as a secret. In the logs of implementation processes kept by the judge an exact secret value is replaced by `<redacted>`.

## N2 Inputs

### N2.1 Inputs of a run

<!-- req: P/AC-R012 -->

The judge receives a pinned export of this specification and an implementation repository with its profiles and an assembly ([files and scalar syntax](../PROFILE.md#files-and-scalar-syntax), [assembly](../PROFILE.md#assembly-and-input-identity)). It starts and addresses the implementation only through the interfaces named below; it does not read implementation code and does not import it.

<!-- req: P/AC-R013 -->

The stand manifests `testsub` and `testsub2` come from [`Platform/common/data/testsub/`](../../data/testsub/README.md). The judge takes no scenario, table or fixture from outside the pinned export.

<!-- req: P/AC-R050 -->

Test-side inputs of a run are files that the invocation of the judge names explicitly; the engine decides the syntax of that invocation. They have three closed forms: the [seam bridge descriptor](../seams.md#explicit-test-side-seam-bridge) ([schema](../forms/seam-bridge.schema.json)), the [D7 descriptor](../seams.md#d7-test-side-evidence-bindings) ([schema](../forms/d7.schema.json)) and the input of the production qualification of N6.2 ([schema](../../../01-store/forms/production-input.schema.json)). A file with the field `bridge` is a seam bridge descriptor, one with `providers` is a D7 descriptor, and one with neither field and without `scope` is the input of N6.2; a file of none of these forms, or invalid against its schema, is a data error of the run. A descriptor serves the target whose id is its `scope`, or, when the scope is that id followed by `#` and the name of a scenario or case, that one case; a descriptor of a case wins over one of its target, and two descriptors of one form for one scope are a data error. The input of N6.2 serves the target `P/01/production`; a second one is a data error. The `source_pin` of every test-side input equals the Source commit of the run, the delivery marker `COURSE_COMMIT` of the pinned export ([the two pins](../PROFILE.md#specification-pin-and-source-pin)); another pin is a data error. A case that needs a test-side input which the invocation does not name is `not_executed`, as the D7 bindings say: with the reason `MissingBinding` of R030, and in the target `P/01/production` with a reason of the table of N6.5. The judge searches no working directory, profile, implementation repository or environment variable for these files.

### N2.2 Interfaces of the implementation

<!-- req: P/AC-R014 -->

The interfaces are the commands of `stand` with their [substitutions](../PROFILE.md#substitutions) and [owners](../PROFILE.md#command-ownership-and-build-results), the [executable adapters](../PROFILE.md#executable-adapters), the [unified vector command](../PROFILE.md#unified-vector-command) and the [seam adapter protocol](../seams.md#seam-adapter-protocol) with its [D7 bindings](../seams.md#d7-test-side-evidence-bindings). A stand process receives only the variables of the [environment of stand processes](../stand.md#environment-of-stand-processes).

## N3 Procedure

### N3.1 Plan and dry listing

<!-- req: P/AC-R015 -->

Before it starts any process the judge lists the plan: all selected targets, for each target its scenarios and steps or its vector rows, and the interfaces it needs. A dry mode prints this listing and starts no process. A target whose required interface is absent is `blocked` in the plan.

### N3.2 Life cycle of the stand

<!-- req: P/AC-R016 -->

The judge starts stand processes as the [layout by processes](../stand.md#layout-by-processes-stage-c), the [stand without root](../stand.md#stand-without-root) and the rows of the dictionary say. The readiness of a store is the single rule of «Role sockets» in that section; a directive that waits for a store applies this rule. Its term is in the table «Terms of the stand» of that section.

<!-- req: P/AC-R017 -->

A stop signal goes to the whole process group of the command, and the judge waits up to 60 s for the exit of the whole group, not only of the shell that started it; after this term it sends SIGKILL to the group; the step has the class `implementation` for a process of the implementation and the class `stand` only for a process of the stand itself or a proxy of the judge. A process that had already exited by itself when a stop or restart step came is a mismatch of that step: the stand does not hide it by starting the process again.

<!-- req: P/AC-R018 -->

The teardown of a stand first sends SIGCONT to frozen processes, then closes the proxies of the runner, then stops the processes and removes the directories, so that a stop of a process is not seen as a broken connection by a live member.

<!-- req: P/AC-R033 -->

A failed step ends its scenario only when it is a directive of preparation without which the later steps have no meaning: `@spoil row`, `@spoil row-index`, `@spoil object`, `@backup store`, `@import store`, `@group-setup`, `@hold` and the directives that start a stand or a role of it (`@start`, `@store-start`, `@server-start`, `@domain`, `@install domain`); a step whose door adapter (`adapters.door`) exited, broke its stream or answered outside its frame (R038) ends its scenario as well, since the scenario has no instance left, and the next scenario gets a new adapter process. If proof of the accepted-socket precondition of an earlier successful `@hold` is lost before or during a dependent step while the store command remains alive, because observation is unavailable or fails or a held socket closes, the current dependent step is `stand`, regardless of its HTTP response or timeout, and the scenario ends. An independently proven unexpected exit or signal of the store command keeps its `implementation` class under R038. Expected socket closures from an explicit scenario stop directive do not invalidate earlier successful preparation. The other steps go on and are judged. Steps that an abort leaves unrun are `not_executed`, not red. A directive that the judge does not execute is `not_executed` with its reason of R030, and so is every later step of its scenario, with the same reason.

<!-- req: P/AC-R034 -->

The terms of the stand are the tables «Terms of the stand» and «Terms of the stand-in worker» of the [dictionary](../README.md#dictionary-of-directives-and-doors). Every wait of the judge is finite.

<!-- req: P/AC-R035 -->

`@carry` is taken from the captured stream of the proxy of the runner, read as HTTP/1.1: keep-alive, several requests on a connection and chunked transfer are parsed, so that the judge does not narrow what an implementation may send.

<!-- req: P/AC-R051 -->

When the judge sends a request and the implementation answers before the judge has written the whole request, for example with a refusal of a body above the limit (RFC 9112 §9.6), the judge reads that response and judges the step by it. A write of the rest of the request that fails because the implementation closed the connection after its response is neither a mismatch of the step nor a failure of the transport of the stand. A step that received no response is judged as a step without a response.

<!-- req: P/AC-R019 -->

After a target no process started by the stand remains. Every scenario that needs its own stand runs on its own stand, and a stand that could not be cleaned up stops the remaining scenarios of its target.

<!-- req: P/AC-R020 -->

A directive of the dictionary applies on every stand of the dictionary unless its row narrows it. A step that no row of the dictionary expresses is a data error of the table.

### N3.3 Declared environment

<!-- req: P/AC-R021 -->

A credited run takes place in the declared environment. It holds the machine for the run, one target at a time. Its processes have no network except the loopback. Its open files limit is 65536 and its locale is `LANG=C.UTF-8`. The directories of the specification and of the inputs are read-only for every process it starts. A target that writes into them does not pass. Before the run the load gate requires `some avg60` of pressure stall information below 1 for cpu and memory and below 5 for io during 180 s; the thresholds are those of ADR-0083 addendum (49) item 1.

<!-- req: P/AC-R022 -->

A target is heavy if it starts implementation processes and waits for them or has steps `@until` or `@sleep`; it is light if it calls one command per case and waits only for its exit, and its longest operation on a reference run is at most one third of the timeout of the judge; otherwise it is heavy. A failed light target with a load sign MAY be repeated once after the light part. The repeat stands next to the first result and does not replace it; the first attempts decide the run, and the first failure counts as load only by the analysis of the run.

<!-- req: P/AC-R023 -->

The report of a run records the declared environment and the load at the moment of the run; a numeric group measured outside the declared environment is marked incomplete.

<!-- req: P/AC-R036 -->

The budget of a target is finite and the report names it; the budget of a scenario is the sum of the waits of its steps plus a reserve. Their values are the implementation's.

## N4 Failures

<!-- req: P/AC-R024 -->

A red result names one of these closed classes:

| Class | Meaning |
|---|---|
| `implementation` | a checked behaviour did not match: a mismatch of a step, row or probe, a failed `unit` or `build` of a profile (R053), a command of a profile that could not start, died by a signal or whose term expired (R038), or the expired term of an answer of a door or of a process of the candidate |
| `stand` | the stand did not work, outside the code of the candidate: its transport failed, the build of an auxiliary program of the judge itself failed, the term of its own command expired, the cleanup of processes failed, its own auxiliary process failed, or the sealed inputs changed during acceptance; also an unavailable or failed `@hold` observer, or loss of `@hold`'s accepted-socket precondition while the store command remains alive, including a closure permitted by its declared idle deadline |
| `runner` | the judge itself failed: an internal exception, a missing or unreadable result of a target, or a result that does not agree with its inventory |
| `data` | a table, row, directive or fixture is outside its form, or a step that the dictionary classes as data (the freeze limit of `@freeze`) |

A failure of the stand or the judge does not say anything about the implementation and does not become a mismatch of a step.

<!-- req: P/AC-R037 -->

The class of a chapter or a target over its steps is the first of `runner`, `stand`, `data`, in this priority, and otherwise an outcome of the implementation.

<!-- req: P/AC-R038 -->

A command of the profile of the implementation, `build`, `unit`, a command of `stand`, an adapter or a vector command, that could not start (the shell codes 126 and 127), died by a signal or whose term expired has the class `implementation`; so has such a command that exits by itself before it answers a request, breaks its stream or answers outside the frame of its protocol (not JSON, other fields, no LF while the process lives): the class is that of the step or row it served. The class `stand` applies only to a command of the stand itself or a proxy of the judge.

<!-- req: P/AC-R053 -->

A `build` of a profile that exits with a code other than zero, could not start, died by a signal or whose term expired fails the build of its module. The stand starts no target whose composition needs that module, and each such selected target is red with the class `implementation`; its report names the build of that module as the failed step. The targets that do not need the module are judged as usual.

<!-- req: P/AC-R025 -->

In a credited run a target without a result stops the run: the judge reports the class `runner` and runs no later target. A cleanup that could not be proven stops the run as well: the judge starts no next target over a process that survived.

<!-- req: P/AC-R026 -->

The heartbeat of a stand-in worker that fails, or any other failure of a part of the stand outside the candidate, is a failure of the stand and not an outcome of the step that was running.

## N5 Acceptance

<!-- req: P/AC-R027 -->

This lesson is checked mechanically over a stub of the protocols, not by a corpus of verdicts: the build of the judge; a dry listing that names every target of the first wave, every selected scenario and every vector row; a parse of every table of the input with its forms; and a stub of the stand protocol that records the calls and answers only with the form, on which every target of the first wave MUST actually call its interfaces.

<!-- req: P/AC-R028 -->

The correctness of the verdicts is decided outside this mechanical check: by code review of another provider and by comparison of verdicts with an existing judge on named candidates of one specification slice, unit of comparison a case. A generated judge's verdict enters a product's result only by a separate decision of the owner.

## N6 Production qualification of P/01

### N6.1 Scope and verdict

<!-- req: P/AC-R039 -->

This section assigns the production qualification of P/01 to the judge (ADR-0135 addendum (4)). The owner of its groups, budgets and measurements is [the production qualification of the store](../../../01-store/spec/production-acceptance.md). A budget is named here and its value stays there. The section adds no platform route, working flag, profile field, directive of the dictionary or numeric value.

<!-- req: P/AC-R040 -->

The target `P/01/production` of the registry has the engine word `production`. Its inventory (N1.4) is the 17 [case groups](../../../01-store/spec/production-acceptance.md#case-groups) `RUN-*` and the 13 probes of N6.3, which are the rows of [the probe debt](../../../01-store/spec/production-acceptance.md#probe-debt) by name. An entry is executed once: `RUN-L03` is the first initial state of `prod-stop`, and `RUN-F01`, `RUN-F02`, `RUN-F04` are the stages of `prod-fault-stage`; their results are shown under both names. The rows of [`forms/production.tsv`](../../../01-store/forms/production.tsv) list this inventory with the inputs and terms of each entry; the table names the entries and adds no outcome.

<!-- req: P/AC-R041 -->

The flag `optional` of this target concerns only the functional verdict: the result of `P/01/production` does not enter the verdict of any other target. Production qualification MUST NOT be claimed without GREEN of this target, and until then the milestone 2.4b of the lesson (ADR-0130 addendum (7)) stays open.

<!-- req: P/AC-R042 -->

The [public store probes](../../../01-store/probes/README.md) are eight checkers of partial slices of the groups. Their pass alone never makes an entry GREEN. The verification of a TLS peer by the daemon, P/01.3-09, on a test CA (ADR-0130 addendum (14) item 6) is not among the 13 probes: it is an unclosed branch of production qualification, stays checked by reading and is named in the report of the target as open.

### N6.2 Input of the qualification

<!-- req: P/AC-R043 -->

The values that the implementation declares and the facts of the environment reach the judge in a separate test input, as the [descriptor of the D7 bindings](../seams.md#d7-test-side-evidence-bindings) does. It is not a profile field and it gives the implementation no interface. It is one JSON object with the closed fields:

| Field | Type and meaning |
|---|---|
| `format` | The integer `1`. |
| `source_pin` | The full 40-hex Source commit of the run. |
| `budgets` | A mapping from the closed keys below to objects with exactly `value` (a finite positive number), `unit` (a nonempty string) and `threshold_ref` (a nonempty exact reference to the record that approved the threshold). |
| `manager` | An object with exactly `stop_deadline_seconds` and `teardown_margin_seconds`, finite positive numbers: the actual stop deadline of the service manager and the separately measured teardown margin. |
| `volume` | An object with exactly `path` (an absolute directory of limited size given by the environment) and `bytes` (its size, a positive integer). |

The closed keys of `budgets` are `output`, `cancellation`, `response_write`, `commit_wait`, `door_attempts`, `replay_limit`, `admin_connections`, `writer_hold`, `disk`, `descriptors` and `id_collection`. A declaration of the candidate alone is no threshold (ADR-0130 addendum (15) item 7). An input outside this form is a data error of the run.

### N6.3 Probes

<!-- req: P/AC-R044 -->

Each probe has its input, its observed outcome and its term as written here; the norm named in the row is the source of the outcome. «Group stand» is the [store group stand](../../../01-store/acceptance/3/README.md#store-group-stand); on `keys.store_build: box` such a probe, or its named part, is `not_applicable`.

| Probe | Norm | Input and means | Observed outcome | Term |
|---|---|---|---|---|
| `prod-stop` | P/01.3 R034 | `RUN-L03` and the initial states: an admitted write, a door forwarding, a connection in an input phase, a request read but not admitted; the binding `progress`; the input `manager` | admission stops; a request read but not admitted gets 503 `unavailable`; a connection whose request is unread is closed; admitted work gets its definite or ambiguous outcome; snapshots, connections and listeners are released; a forced kill is no success | `BUDGET_STOP` on `graceful_stop_elapsed`, below the deadline of `manager` less its margin |
| `prod-fault-stage` | P/01.1 R144 | `RUN-F01`, `RUN-F02`, `RUN-F04`; the bindings `fault` and `storage` | as the rows of these groups: `unavailable` with a proven absence of effect, `ambiguous` with an unknown result, a batch and its id whole or absent whole | none: the outcome is judged |
| `prod-leader-loss` | P/01.3 N1.3 `leader_wait`; P/01.1 N4 `ambiguous_leader` | group stand; the answer of the leader held after a write was sent, by a freeze of the process group of the leader; a two-way partition of a member: no traffic between it and the other members in either direction | a write sent without an answer is `ambiguous`; with no leader for the effective interval, 503 `unavailable` | the effective `-leader-wait` |
| `prod-import-interrupted` | P/01.3 N1.3 `import`; P/01.3 R021 | group stand; an interrupted `import` | a member starts and holds writers with 503 `unavailable`; the import continues through `admin.sock` of the leader; after the loss of a majority `recover` publishes a floor, a repeat of the former attempt refuses, the floor does not decrease, and a new `import` attempt carries the full input | the key `writer_hold` |
| `prod-recover-interrupted` | P/01.3 R021 | the binding `fault` at the phase mark of `recover` | the phase mark stands; a daemon start refuses with code 2; a repeat of `recover` starts over from the same input | none: the outcome is judged |
| `prod-disk-fd` | P/01.3 R036 | the input `volume`, by the stages before and after the effect; a process limit of descriptors set from the key `descriptors` | full disk: 503 `unavailable` only on a proven refusal before the effect, otherwise the `ambiguous_*` outcomes; a read keeps working; writes return after space is freed, without a restart. Exhausted descriptors: `connection_limit` if the connection could be accepted, otherwise it is closed; started requests get their definite outcome; the daemon does not crash | the keys `disk`, `descriptors` |
| `prod-clock-group` | P/01.3 N1.3 `admission`; P/01.1 R013, R070 | group stand; the binding `clock` in the scope of [clocks in a group](../../../01-store/spec/production-acceptance.md#clocks-in-a-group); a leader change; a Raft snapshot | admission time does not decrease over a leader change and a snapshot; `expired` follows `not_after`; `admission_ahead` appears when the current clock of the leader is behind the saved admission time; the equality of admission time and a replay held after `not_after` before the first application are judged by R070 | `CLOCK_SKEW` bounds the spread of the clocks; no skew allowance is added |
| `prod-reply-commit` | P/01.3 R035 | a slow reader made by the judge; group stand for the commit part: the commit held under a live leader by a freeze of the other voters | a reader that does not take the answer loses the connection; when the commit wait ends the outcome is `ambiguous` (`ambiguous_leader`) | the keys `response_write`, `commit_wait` |
| `prod-door-attempts` | P/01.3 R035 | group stand with a door without a vote; all voters unreachable | the attempts of one request take not less than the effective `-leader-wait`; a repeat only with the same `id`; a write without `id` stays `ambiguous`; the loss of the answer to a sent attempt stays `ambiguous` | the effective `-leader-wait`; the key `door_attempts` |
| `prod-replay-limit` | P/01.3 R035 | replays made by the judge above the key `replay_limit` | above the limit 503 `unavailable` with `Retry-After` before admission; neither the record nor the `id` memory is touched | the key `replay_limit` |
| `prod-admin-limit` | P/01.3 R008 | the ordinary connection limits exhausted by the judge | `admin.sock` still admits the operator; above its own limit, `connection_limit`: 503 `unavailable` with `Retry-After` | the key `admin_connections` |
| `prod-backup-temp` | P/01.3 R018 | a failure, a cancellation and a killed run of `backup`; the binding `fault` | the temporary file is removed on a failure and a cancellation; a leftover is removed by the next `backup` to the same target; the former copy stays | the key `cancellation` |
| `prod-id-age` | P/01.1 R141 | the binding `clock`; the edges of `RUN-W03` | until both conditions hold, the same answer and no new application; equality at the age minimum is not eligible; the age runs from the first application on the admission-time clock | `ID_REPLAY_MIN_AGE`, `ID_REPLAY_MIN_RECORDS` |

<!-- req: P/AC-R045 -->

A two-way partition is the observable requirement of its row, whatever the means. The means is the choice of the engine (without root, for example, group addresses through a TCP relay of the judge that silently stops forwarding in both directions). The directive `@cut` cuts only incoming connections and does not satisfy this row alone.

### N6.4 Terms

<!-- req: P/AC-R046 -->

The term of a probe is the last column of its row; the term of a group is its row in [the first approved budgets](../../../01-store/spec/production-acceptance.md#first-approved-budgets). The monotonic resolution and the scheduling uncertainty of the judge are calibrated separately and recorded; they do not increase a budget. An entry judged by its outcome alone is bounded by the budget of the target (N3.3). A timeout of the judge, a forced kill, a counter of the producer, an EIO text or a library return is no GREEN.

### N6.5 Results and controls

<!-- req: P/AC-R047 -->

An entry ends in one of these results:

| Observation | Result |
|---|---|
| every required observation matched and the controls of its instruments were activated | GREEN |
| a normative mismatch | red, class `implementation` |
| an error of an instrument or of the form of an observation, or a failed control | red, class `stand`; it says nothing about the implementation and gives no verdict for the entry |
| a required D7 binding is absent | `not_executed`, the reason is `clock`, `storage`, `progress` or `fault` |
| a required field or key of the input of N6.2 is absent, or its threshold is not approved | `not_executed`, the reason is the name of the field or key |
| a numeric group measured outside the declared environment (N3.3) | `not_executed`, the reason is `environment_undeclared` |
| the engine has no means for the two-way partition or for a Raft snapshot | `not_executed`, the reason is `two_way_partition` or `raft_snapshot` |

<!-- req: P/AC-R048 -->

Before it scores an entry the engine activates the controls of its own instruments: the negative controls of its capability in [the D7 bindings](../seams.md#d7-test-side-evidence-bindings) and those of the row of the group. A list of controls that were not activated qualifies nothing. Named mutants of a candidate belong to the comparison of R028 and are not an input of the engine.

<!-- req: P/AC-R049 -->

On the stub of R027 the target lists its whole inventory and calls the interfaces of each entry; every entry whose binding the stub does not qualify is `not_executed`. A stub establishes no production result.

## Implementation decides

An implementation is to name in its description:

1. the language and the module layout of the engine; the shared parser of the tables; how a target's data selects an engine family of the routing table;
2. the form of its evidence files and their names, beyond the report of N1.5; the budgets of a target and the reserve of a scenario (N3.3);
3. parallelism in a run that is not credited (a credited run is one target at a time, N3.3);
4. the printing form of the dry listing;
5. the means of the two-way partition and of a Raft snapshot of N6.3, and the instruments of N6;
6. the syntax of the invocation that names the test-side inputs of N2.1.

## Readiness checklist

An implementation conforms to the lesson when every norm holds; a norm id `P/AC-NN` is what findings and reviews refer to:

- [ ] **P/AC-01** one engine, no lesson-specific code (N0) — code review
- [ ] **P/AC-02** the readers of the scenario, vector and registry tables: forms, rows outside the form are data errors before the stand starts (N1.1–N1.3) — dry listing and table parse of N5
- [ ] **P/AC-03** the results of a target and the inventory (N1.4) — table parse and stub of N5; comparison with an existing judge
- [ ] **P/AC-04** the report and the secrets (N1.5) — by reading and the comparison of reports
- [ ] **P/AC-05** the inputs and the interfaces (N2) — by reading, and the stub of N5
- [ ] **P/AC-06** the dry listing (N3.1) — N5
- [ ] **P/AC-07** the life cycle: readiness, stop of a whole group, teardown, cleanup (N3.2) — stub of N5 for the calls, by reading for the rest
- [ ] **P/AC-08** the declared environment (N3.3) — by reading of the run record
- [ ] **P/AC-09** the failure classes (N4) — by reading, and the comparison of verdicts
- [ ] **P/AC-10** the checks of N5 are present and pass — N5
- [ ] **P/AC-11** the production qualification of P/01: the inventory, the input, the probes, the results and the controls (N6) — stub of N5 for the calls, by reading and by the comparison of verdicts for the rest

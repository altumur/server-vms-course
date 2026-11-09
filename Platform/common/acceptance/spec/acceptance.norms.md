# P/AC — The acceptance judge: norms

This English text is the source; the Russian translation `ru/acceptance/spec/acceptance.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of the shared acceptance lesson. [Instructions](acceptance.README.md), [the common stand and its dictionary](../README.md), [profiles and assembly](../PROFILE.md), [target registry](../forms/targets.README.md). The judge is the program that checks a generated implementation against this specification; the common acceptance README calls it the runner. The lesson has no process of its own and opens no door of the implementation. Norm ids are `P/AC-NN`; requirement anchors `P/AC-RNNN` are in this source only.

## N0 Scope and normative words

<!-- req: P/AC-R001 -->

Normative keywords follow the [course canon](../../NORMATIVE-TERMS.md). This lesson sets what the judge does and what it observes. It sets no behaviour of an implementation: the norms and the acceptance tables of each lesson remain the source of what an implementation must do, and the common stand gives the words in which the tables say it.

<!-- req: P/AC-R002 -->

The judge is one shared engine. A lesson is only data. The engine branches only on the closed words of this lesson and of the [dictionary of directives and doors](../README.md#dictionary-of-directives-and-doors), never on a literal lesson, target or package name. A step of a lesson that the dictionary does not express is a gap of the specification, not a reason for lesson-specific code.

<!-- req: P/AC-R029 -->

The first wave of the engine is the targets of P/01 with a stand, scenarios or vectors. Outside it are the combat targets of D7, load, the judgement of families (the package `common/family-read`), the stands of consoles and of several clusters (the target `system/05-power-pull` among them), VMS, and the suites TLS and ER of [`tls/README.md`](../tls/README.md): the steps of those suites are written there as prose and their table is a separate piece of work. The registry keeps these targets; the first wave is a selection of the run, not a branch of the engine.

## N1 Forms

### N1.1 Scenario tables

<!-- req: P/AC-R003 -->

The judge reads every `scenarios.tsv` by the row form of the [dictionary](../README.md#dictionary-of-directives-and-doors) and every `seams.tsv` by the [seam adapter protocol](../README.md#seam-adapter-protocol) and the seam grammar of its owner. It reads a table whole before the stand of the target starts. A table cell declared `# cell-json:` follows the [source-cell form](../../contracts/source-cells.md).

### N1.2 Vector tables

<!-- req: P/AC-R004 -->

Vector tables, their consumers, input columns, fixtures, expectations and comparisons are defined by the [vector wire form](../../vectors/wire.md), its `wire.tsv` and `consumers.tsv`, and the README of each package. The older Platform vector commands keep the form of the [common stand](../README.md#layout-by-processes-stage-c).

<!-- req: P/AC-R005 -->

In a table with a header, a row whose cell count differs from the header is a data error of that table; the judge reports it without judging the row. A table assigned to a consumer and absent from the export is a data error, not an empty table.

### N1.3 Target registry

<!-- req: P/AC-R006 -->

The targets are the rows of the registry: the public table [`forms/targets.tsv`](../forms/targets.README.md) and the judge-side routing table `forms/targets.routing.tsv` in the same directory, which has one row for each `id` of the public table and repeats no other column. A target's owner, interfaces, keys, requirement anchors and flags come only from the public table; its engine family, acceptance directories, scenario selection and parts of other lessons come only from the routing table. The [target requirements](../runner-targets.README.md) define the columns they share. In a routing row the first directory holds the table the target executes and the selection of scenarios applies to it alone; the other directories hold its inputs unless the engine word names them as executable.

### N1.4 Verdict of a target

<!-- req: P/AC-R007 -->

The result of a target is GREEN, red, `not_executed`, `not_applicable` or `blocked`:

| Result | Meaning |
|---|---|
| GREEN | every inventoried row or step of the target was executed and matched |
| red | a row or step did not match, or the target failed with a class of N4 |
| `not_executed` | a scenario, row or target could not run; the result names one of the closed reasons below and is not GREEN |
| `not_applicable` | a key of the profile selects a build for which the target has no meaning, as `keys.store_build: box` for a group stand; the target does not enter the result and is not red |
| `blocked` | a required interface or part of the composition is absent before execution; this is not a test result |

<!-- req: P/AC-R030 -->

The reason of a `not_executed` result is one of the closed list: `installer_ceiling_unproven`, `installer_rights_check_missing`, `store_rights_template`, `store_spoil_row_missing`, `stage_package_not_exported`; or, when a public interface or profile key that the target requires is absent or has a value that the target does not accept, the name of that interface or key. For the steps that an abort of a scenario leaves unrun the reason is the scenario and the number of the step whose failure ended it; that step keeps its own class.

<!-- req: P/AC-R031 -->

Every `not_executed` row or scenario of a target takes GREEN from it. There is no exception: a debt row of a stand takes GREEN away like any other, and the result of the target says so.

<!-- req: P/AC-R032 -->

A target that is `not_executed`, `not_applicable` or `blocked` does not stop the other targets of the run.

<!-- req: P/AC-R008 -->

Before running a target, the judge builds an inventory of what it will run: for scenarios — their names, order, steps, source lines and manual steps; for vector rows — the identity of the row of [the unified vector command](../PROFILE.md#unified-vector-command). A target is GREEN only if its result equals this inventory, at least one row or step ran, all its processes were cleaned up and the sealed inputs did not change. A result that does not agree with the inventory is red with the class `runner`.

<!-- req: P/AC-R009 -->

The gate `accept:<chapter>:<scenarios>` of a stage reads per scenario: a scenario is green when its steps equal the inventory, it has automatic steps and they all matched. A failure of the stand or an unreadable result leaves no green scenario.

### N1.5 Report and secrets

<!-- req: P/AC-R010 -->

A report given to the line that generates the implementation carries the name of a case, a norm anchor, the class of the mismatch and the tail of the stderr of a failed case, never an expected answer. The tail is at most 4 KiB, and every substring of at least 8 bytes that occurs in the inputs, fixtures or expectations of the case is cut out of it. A case name that exists only on the judge side is replaced by an opaque identifier, constant within the run, in such a report and in the `case` of a request to the implementation.

<!-- req: P/AC-R011 -->

The report does not give out response bodies, stdout, stderr or the values of secrets: it gives at most the length, the digest and the content type of such a value. A secret is the value of a field whose name contains `token` or equals `authorization`, the value after `Bearer ` and the base64, base64url and hexadecimal encodings of these values, and a value the judge itself gave out as a secret. In the logs of implementation processes kept by the judge an exact secret value is replaced by `<redacted>`.

## N2 Inputs

### N2.1 Inputs of a run

<!-- req: P/AC-R012 -->

The judge receives a pinned export of this specification and an implementation repository with its profiles and an assembly ([files and scalar syntax](../PROFILE.md#files-and-scalar-syntax), [assembly](../PROFILE.md#assembly-and-input-identity)). It starts and addresses the implementation only through the interfaces named below; it does not read implementation code and does not import it.

<!-- req: P/AC-R013 -->

The stand manifests `testsub` and `testsub2` come from [`Platform/common/data/testsub/`](../../data/testsub/README.md). The judge takes no scenario, table or fixture from outside the pinned export.

### N2.2 Interfaces of the implementation

<!-- req: P/AC-R014 -->

The interfaces are the commands of `stand` with their [substitutions](../PROFILE.md#substitutions) and [owners](../PROFILE.md#command-ownership-and-build-results), the [executable adapters](../PROFILE.md#executable-adapters), the [unified vector command](../PROFILE.md#unified-vector-command) and the [seam adapter protocol](../README.md#seam-adapter-protocol) with its [D7 bindings](../README.md#d7-test-side-evidence-bindings). A stand process receives only the variables of the [environment of stand processes](../README.md#environment-of-stand-processes).

## N3 Procedure

### N3.1 Plan and dry listing

<!-- req: P/AC-R015 -->

Before it starts any process the judge lists the plan: all selected targets, for each target its scenarios and steps or its vector rows, and the interfaces it needs. A dry mode prints this listing and starts no process. A target whose required interface is absent is `blocked` in the plan.

### N3.2 Life cycle of the stand

<!-- req: P/AC-R016 -->

The judge starts stand processes as the [layout by processes](../README.md#layout-by-processes-stage-c), the [stand without root](../README.md#stand-without-root) and the rows of the dictionary say. The readiness of a store is the single rule of «Role sockets» in that section; a directive that waits for a store applies this rule. Its term is in the table «Terms of the stand» of that section.

<!-- req: P/AC-R017 -->

A stop signal goes to the whole process group of the command, and the judge waits up to 60 s for the exit of the whole group, not only of the shell that started it; after this term it sends SIGKILL to the group and the step has the class `stand`. A process that had already exited by itself when a stop or restart step came is a mismatch of that step: the stand does not hide it by starting the process again.

<!-- req: P/AC-R018 -->

The teardown of a stand first sends SIGCONT to frozen processes, then closes the proxies of the runner, then stops the processes and removes the directories, so that a stop of a process is not seen as a broken connection by a live member.

<!-- req: P/AC-R033 -->

A failed step ends its scenario only when it is a directive of preparation without which the later steps have no meaning: `@spoil row`, `@spoil row-index`, `@spoil object`, `@backup store`, `@import store`, `@group-setup` and the directives that start a stand or a role of it (`@start`, `@store-start`, `@server-start`, `@domain`, `@install domain`). The other steps go on and are judged. Steps that an abort leaves unrun are `not_executed`, not red.

<!-- req: P/AC-R034 -->

The terms of the stand are the tables «Terms of the stand» and «Terms of the stand-in worker» of the [dictionary](../README.md#dictionary-of-directives-and-doors). Every wait of the judge is finite.

<!-- req: P/AC-R035 -->

`@carry` is taken from the captured stream of the proxy of the runner, read as HTTP/1.1: keep-alive, several requests on a connection and chunked transfer are parsed, so that the judge does not narrow what an implementation may send.

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
| `implementation` | a checked behaviour did not match: a mismatch of a step, row or probe, a failed `unit`, or the expired term of an answer of a door or of a process of the candidate |
| `stand` | the stand did not work, outside the code of the candidate: its transport failed, its build failed, the term of its own command expired, the cleanup of processes failed, its own auxiliary process failed, or the sealed inputs changed during acceptance |
| `runner` | the judge itself failed: an internal exception, a missing or unreadable result of a target, or a result that does not agree with its inventory |
| `data` | a table, row, directive or fixture is outside its form, or a step that the dictionary classes as data (the freeze limit of `@freeze`) |

A failure of the stand or the judge does not say anything about the implementation and does not become a mismatch of a step.

<!-- req: P/AC-R037 -->

The class of a chapter or a target over its steps is the first of `runner`, `stand`, `data`, in this priority, and otherwise an outcome of the implementation.

<!-- req: P/AC-R038 -->

A command of the profile of the implementation that could not start (the shell codes 126 and 127), died by a signal or whose term expired has the class `implementation`. The class `stand` applies only to a command of the stand itself or a proxy of the judge.

<!-- req: P/AC-R025 -->

In a credited run a target without a result stops the run: the judge reports the class `runner` and runs no later target. A cleanup that could not be proven stops the run as well: the judge starts no next target over a process that survived.

<!-- req: P/AC-R026 -->

The heartbeat of a stand-in worker that fails, or any other failure of a part of the stand outside the candidate, is a failure of the stand and not an outcome of the step that was running.

## N5 Acceptance

<!-- req: P/AC-R027 -->

This lesson is checked mechanically over a stub of the protocols, not by a corpus of verdicts: the build of the judge; a dry listing that names every target of the first wave, every selected scenario and every vector row; a parse of every table of the input with its forms; and a stub of the stand protocol that records the calls and answers only with the form, on which every target of the first wave MUST actually call its interfaces.

<!-- req: P/AC-R028 -->

The correctness of the verdicts is decided outside this mechanical check: by code review of another provider and by comparison of verdicts with an existing judge on named candidates of one specification slice, unit of comparison a case. A generated judge's verdict enters a product's result only by a separate decision of the owner.

## Implementation decides

An implementation is to name in its description:

1. the language and the module layout of the engine; the shared parser of the tables; how a target's data selects an engine family of the routing table;
2. the form of its evidence files and their names, beyond the report of N1.5; the budgets of a target and the reserve of a scenario (N3.3);
3. parallelism in a run that is not credited (a credited run is one target at a time, N3.3);
4. the printing form of the dry listing.

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

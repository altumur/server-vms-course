# Command tables

A topic of the [common acceptance README](README.md): the directives and doors are its [dictionary](README.md#dictionary-of-directives-and-doors).

In a command table a row is a call of a command or an adapter of the profile, not an HTTP step. The routing word of the target names the form: `verdicts`, `puts` or `variants` ([`forms/targets.routing.tsv`](forms/targets.routing.tsv); judge-only: the routing of the judge). The tables are those of the first directory of the routing row. The interface of each call comes from the public row of the target ([target registry](forms/targets.README.md)). The judge reads every table of the target whole before the stand starts. Empty lines and lines that begin with `#` are notes, except the declarations that a form names. A row outside its form is a data error of the class `data`, found before the stand starts; it is not an outcome of the implementation. The inventory of the target (N1.4 of the [norms](spec/acceptance.norms.md); judge-only: the norms of the judge) names each row by its file and the number of its physical line.

## Deterministic syscall faults

The two directives below are shared stand operations. They inspect the selected store process from outside; they introduce no production route, signal handler, checkpoint schedule or on-disk name. The [judge norms](spec/acceptance.norms.md#n32-life-cycle-of-the-stand) define their planning, evidence and failure classes.

| Form | Meaning |
|---|---|
| `@crash <process> <calls> <K> <trigger>` | sweep the reachable syscall ordinals 1 through K after the trigger begins; at the selected successful syscall's exit stop all traced threads before any returns to user code, send SIGKILL to the selected process group and confirm its exit; expectation `ok` requires the independently observed kill at that ordinal |
| `@io-error <process> <calls> <K> <errno> <trigger>` | sweep the same ordinals; at the selected syscall's entry suppress its execution and return the selected error to its caller, with no effect from that call; inject once, then remove the fault before subsequent steps; expectation `ok` requires the independently observed suppression and error return, and the trigger outcome below |

**Arguments.** `<process>` is `store` or `store@<id>`, an existing store identity of the stand. `<calls>` is a nonempty comma-separated set without repeats or spaces: `rename`, `fsync`, `write` for `@crash`, and `fsync`, `write` for `@io-error`. `<K>` matches `^[1-9][0-9]*$`. `<errno>` is exactly `EIO` or `ENOSPC`. `<trigger>` is one strict JSON object, with exactly one of these forms:

- `{"request":"<request>","expect":"<expect>"}`: execute an existing dictionary request with its existing expectation. It names the selected store or starts a local operator command for that stopped store. A nested sweep, a different store, an empty request/expect or a mutation under `@until` is a data error. request and expect are nonempty strings without NUL, TAB, CR or LF; duplicate fields and non-JSON numbers are invalid. The rest of the request cell is the JSON object; spaces inside its strings are ordinary content.
- `{"checkpoint":{"request":"<request>","expect":"<expect>"}}`: for the selected live store call its required profile command `stand.checkpoint`. When its value is the string `none`, execute the enclosed ordinary write request instead, with its expectation. The fallback request and expectation are validated even when the command is present; they write through the selected store's door. No phase or filename is selected by the implementation.

**Checkpoint binding.** `stand.checkpoint` is a nonempty shell command that forces saving the current state, waits for completion and exits 0 only after its durability barriers succeed, or exactly the string `none` when this implementation has no checkpoint.

It receives the selected instance's `{data}`, `{dir}`, `{socket}`, `{id}` and `{tls}`; `dir` is its store directory and `data` its platform directory. An instance without TLS has an empty `tls`. It runs with the ordinary profile working directory and stand environment. `none` is a declaration, never a command to execute.

An absent command is an incomplete profile: the selected target is `blocked` before execution, even if its registry flag is `optional`. There is no `MissingBinding` or `not_executed` fallback for an absent command. The declaration MUST describe the actual implementation; `none` does not disable tracing or skip its journal writes.

**Counting.** Install the observer before starting the trigger; zero the counter at that boundary, after the scenario prefix has completed. Count only operations on regular files or directories in the selected store directory, using resolved path/descriptor identities, including files subsequently renamed or unlinked. Do not count socket, stdout, stderr or unrelated-file writes.

Trace all threads and descendants of the selected store command; for an offline operator trigger trace the operator command from exec, not the stopped daemon. A checkpoint helper is traced too, but its socket writes do not count.

Serialize syscall stops to define one recorded order across threads. Normalize `rename`, `renameat`, `renameat2` to `rename`; `fsync`, `fdatasync` to `fsync`; and `write`, `writev`, `pwrite64`, `pwritev`, `pwritev2` to `write`.

The ordinal is in the union of the named families. For a crash count successful exits; for an error count entries that would address the selected storage object. The observer records the native syscall and the normalized family. It does not infer a phase from a candidate's path, source code, log message or counter.

**Sweep and isolation.** The scenario is a finite family of trials, not successive damage to one directory. For each sweep, first discover its reachable ordinals without that sweep's fault, under the already selected earlier faults. Run that prefix and trigger on a fresh stand with fresh bindings; require the ordinary trigger expectation (and code 0 for a checkpoint command). Record the trace and retain ordinals `1..min(K,C)`, where C is the observed call count; record the untested tail if C exceeds K. No matching call is a `stand` failure, never an empty GREEN. An ordinal beyond C is absent, not a successful injection.

Then replay the scenario from its beginning on a fresh stand for every retained ordinal, inject that fault and run the suffix. With several sweeps enumerate the product of the reachable ordinals, discovering each later sweep under each earlier faulted prefix. No counter, bound version, directory or process crosses trials; never copy a live directory as a reset. A selected ordinal not reached on its trial is `stand`.

Every trial keeps its step/source-line identity and ordinal tuple in the report. A source step matches only if it matches in every trial in which it runs; a failed preparation aborts that trial's dependent steps. Scenario success requires successful discovery and every required trial, not a successful last trial.

**Trigger outcome.** On a discovery run the trigger must match its ordinary expectation. On a crash trial its expected SIGKILL replaces only the interrupted trigger's ordinary outcome; no refusal code, closed socket or timeout proves this kill. The suffix starts after the whole selected command group has exited.

On an error trial a request trigger, including the `none` fallback, must match its supplied expectation by the ordinary response rules; a real checkpoint command may exit normally with a nonzero code after the proven fault. A crash, timeout, malformed response or unexpected loss of a serving store is still an implementation failure. The fault is removed and the observer detached before later scenario steps. These operations simulate process failure or a syscall error; they do not establish loss of dirty kernel pages or physical power-loss durability.

**Independent evidence and controls.** Before scoring, qualify the observer and injector on judge-owned temporary files/processes: correct versus wrong process/object, zero versus one effect, native call normalization, ordinal boundaries, all threads, successful versus failed calls, both error numbers, a suppressed write with unchanged bytes and a crash with a proven wait status. Include inactive/no-op and stale-ordinal controls; activating an error must leave the selected syscall's side effects absent.

A failure to trace, inject, observe or clean up is `stand`; a malformed selector or trigger is `data`. No trace capability is a stand failure, not a candidate refusal or an unexecuted successful case.

Keep process/group and storage-object identities, monotonic boundaries, native call, ordinal, result/error and kill/wait evidence, with secrets redacted. Profile ACK, helper exit, an EIO string or a configured hook alone proves nothing.

This is the same separation of binding and independently observed effect as the [test-side evidence bindings](seams.md#d7-test-side-evidence-bindings); these directives require no D7 descriptor. Budgets are finite under the common stand rules; exceeding one never produces GREEN.

## Stand controls for qualification

These operations are used only by Q procedures and the qualification of the judge's instruments. They are not functional J scenarios or candidate interfaces. They act on externally identified processes, storage objects and peer streams; they require neither candidate source nor its language, file layout or internal message format. A reference fixture is a small process of the stand that implements only the observed slice, not a modified candidate.

On a separate control stand the judge binds the same `store` / `store@<id>` slots and declared trigger interfaces to its own fixtures, with fresh process groups, directories, local role sockets and peer endpoints. Requests still use the declared public door and response form; a checkpoint fixture supplies the same checkpoint command contract. This substitution exists only in the judge's temporary stand: it neither calls the candidate nor edits its repository profile. The same observer, transport and history-checker paths run on control and candidate stands.

| Form | Meaning |
|---|---|
| `@barrier-noop <process> <objects> <trigger>` | on a fresh trial suppress every `fsync`/`fdatasync` on selected objects throughout the trigger and return 0 without executing the call; after the trigger's ordinary expectation is met, freeze all writers while suppression remains active and apply qualified loss of unsynchronised storage, then reopen for independent checking |
| `@partition store@<id> on` / `@partition store@<id> off` | isolate / reconnect the named existing member in both directions on all its inter-member API and Raft streams, including existing and new connections; leave the judge's local public role socket reachable; expectation `ok` requires independently observed activation / removal |

For `@barrier-noop`, `<process>` and the strict `<trigger>` object have the forms of [deterministic syscall faults](#deterministic-syscall-faults), including the checkpoint command or explicit `none`. A trigger cannot nest a stand control. `<objects>` is exactly `file` or `directory`: the kind is obtained from the resolved descriptor, not a filename. All threads and descendants of the selected command are traced. The interval begins before the trigger and remains active until all selected writers are frozen and then terminated by the reset or destroyed before reopening a replay copy; it is not a one-call error. Record every suppressed native call, object identity, monotonic boundary and substituted result. No matching barrier, an ordinary trigger mismatch or an unproven suppression fails the control; it is not an empty success.

The reset is a qualified guest power reset without shutdown/flush, or replay of an independently recorded device log onto a copy at a boundary that discards the affected unbarriered effects. For device-log replay freeze all selected writers before choosing the boundary, then terminate the original frozen command group; never reuse its cache or state and reopen only the replayed copy. For a guest reset, the reset itself terminates them. The storage observer proves the boundary, writes, honest versus suppressed barriers and reopened bytes. A normal process restart cannot perform this operation. For `directory`, require an independently observed successful rename into the selected parent directory before the suppressed directory barrier; file barriers remain honest. The medium model must actually expose loss of the publication on the negative reference fixture. A durable rename that happens to survive is not evidence of an activated negative control. Other ways of making data durable are recorded; they cannot silently substitute for suppressed calls.

A partition starts before the dependent workload/read and lasts until `off` or trial teardown, within the declared finite trial budget. Repeated `on`, `off` without an active partition or an unknown identity is `data`. The stand selects streams by endpoint/process identity before their payload: it neither parses a private read-fence reply nor assumes internal HTTP. At activation stop forwarding in both directions, discard already queued peer payload and reject or hold all later peer payload until removal; record these boundaries and every alternative peer path; incoming-only `@cut` and write-answer-only `@cut ... answer` do not establish this partition. After removal prove resumed transport. Isolation delays or excludes leader confirmation; it does not force a correct candidate to return a stale success.

Qualify these operations on the same stand before scoring: an honest barrier writer survives the qualified reset, a writer receiving false success loses an acknowledged distinct-key witness; a directory-publication fixture with honest file barriers loses its renamed publication when only directory barriers receive false success. For partition, prove traffic stops in both directions and resumes after removal, with wrong-member, incoming-only, inactive and stale-activation controls. The history checker must accept the corresponding correct fixtures and reject the resulting lost-write/publication or stale-success histories. A deliberately stale public-response fixture qualifies the checker, not an internal fence implementation. No candidate code is changed.

A missing qualified storage/fault binding or two-way partition means the existing Q `not_executed` reason of N6.5; a malformed directive is `data`. Once a control is attempted, an observation, activation, negative-witness, checker or cleanup failure is red, class `stand`, with no candidate verdict. Abort dependent steps, retain their unexecuted reasons, remove the partition and injection and destroy the control's fresh state. All waits are finite under the declared Q budgets. Control evidence, histories and fixture identities remain separate from the candidate's measured history; deliberate false barriers are not a candidate durability obligation. These operations add no production behaviour or threshold.

## Held connections

| Form | Definition | Users |
|---|---|---|
| `@hold <door> <N>` | open N connections to the door and write nothing on them; the judge keeps its sockets open until the end of the scenario, then closes them; the expectation `ok` — independent Linux observation matches each client socket to a live accepted server socket descriptor held by the process group that owns the door, with all N alive together by the readiness term; queued connections do not count. The observation and failure rules below apply | P/01, P/03 |

For `@hold`, the runner records the identities of its N client sockets and observes their server peers through Linux socket metadata and the open socket descriptors of the process group that owns the door. The owner is the store for a store door and the named worker for `worker <name>`. For a Unix socket, it obtains the client inode, resolves its peer inode through Unix socket diagnostics and confirms that this peer inode belongs to an open socket descriptor in that process group. For TCP, it matches the local and remote address and port pairs and confirms the accepted server socket descriptor in the same process group. A socket still in the listener queue has no such accepted descriptor and does not satisfy the observation. A successful `connect` or a sleep alone proves no acceptance. This observes accepted sockets; it prescribes neither an internal connection counter nor a new door of the implementation.

The readiness term is the `@hold` row of [Terms of the stand](README.md#dictionary-of-directives-and-doors). It is one monotonic interval from the first attempt to open a client connection through confirmation that all N matched server sockets are alive together, at or before the term. Opening or retrying another connection does not reset the interval; it is not a separate term for each connection.

The runner records closures and rechecks the held set before each dependent step, then watches it through that step. If a held socket closes, or its independent observation becomes unavailable or fails, while the command that owns the door remains alive, the result is `stand`: proof of the test-side precondition has been lost. This applies before and during a dependent step, including a closure permitted by the declared idle deadline; the response code or timeout of an already running dependent HTTP step does not become an `implementation` mismatch under that lost precondition. That current step is `stand`, the scenario ends, and later steps remain unrun by the common scenario-abort rule. Closures caused by an explicit scenario stop directive are effects of that directive and do not invalidate earlier successful preparation. An independently proven unexpected exit or signal of the command that owns the door remains an `implementation` failure under the command-failure rule.

The implementation's declared idle deadlines remain in force. `@hold` does not judge those deadlines, impose a minimum, disable the timer, write data into the held sockets or reopen closed sockets to keep them alive. If independent observation is unavailable or fails, the result is `stand`. Only when observation works, no held socket has closed and no observation failure has occurred, failure to confirm all N live accepted sockets by the readiness term is `implementation`. Loss of a held socket or observation failure takes priority over that readiness timeout.

## Loader verdicts

Row inventory, including diagnostic hints: [P/AC-R008](spec/acceptance.norms.md#n14-verdict-of-a-target); failure classes: [P/AC-R024](spec/acceptance.norms.md#n4-failures).

The word `verdicts` runs `verdicts.tsv` of the first directory with `classes.tsv` and `diagnostics.tsv` next to it. The rules by which a verdict is set are the norms of the owner of the target (P/02.1 N1, N4); this form says only how a row runs and what the judge observes.

- **`verdicts.tsv`.** A row is `case<TAB>verdict`. The input is the file `cases/<case>.subsystem.yaml`, loaded alone, without a catalogue of other manifests. `verdict` is `ok` (the manifest loads) or `refused` (a loading refusal). The set of files of `cases/` equals the set of rows; an extra file or an extra row is a data error.
- **The call.** The judge loads each file through the interface of the target. With the command `stand.load` the substitution `{file}` is the path of the file. Exit code 0 is a manifest. An exit with another code, not by a signal, whose stdout or stderr contains the file name `<case>.subsystem.yaml` is a refusal. With the adapter `load` ([manifest loader](PROFILE.md#manifest-loader)) the answer `verdict` is `ok` or `refused`; a refusal is `refused` whose `text` contains the file name. Anything else is a mismatch of the row: a death by a signal, a refusal that does not name the file, a broken answer of the adapter.
- **The verdict.** It is strict: `ok` matches only a manifest, `refused` only a refusal.
- **`classes.tsv`.** A row is `case<TAB>class`, where `class` is `text`, `form`, `relations` or `catalogue`. Its `case` has `refused` in `verdicts.tsv`. The refusal text contains the word `refused:<class>` of the class of the case and no other word `refused:<word>`; otherwise the row of the case is a mismatch.
- **`diagnostics.tsv`.** A row is `case<TAB>paths<TAB>lines`. Its `case` occurs once and has `refused` in `verdicts.tsv`. `paths` is a JSON array of paths, each an array of key names and list indexes; `lines` is a JSON array of line numbers from 1. A row is a hint, not a check. The judge looks for each path in the refusal text in the form of `keys.path_style` of the profile: `json` — the text of the JSON array, `dotted` — the names joined by `.` with an index as `[N]`. It looks for each line number as a decimal word. What it does not find it writes into the report, without a failure. Extra paths in the text are not observed.

A run of these files through `manifest put` is not part of this word; such a sample is written as rows of [installation sequences](#installation-sequences).

## Installation sequences

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

Without the column `canonical` the mark and the view are not compared. The order of the writes in time and the repeat of the view after a `cas` conflict are not compared; they are checked by reading.

**A line with `ceiling`.** Before the case the judge confirms the ceiling of the new store. `GET /v1/status` gives `max_value` = `ceiling`. A `put` through `{socket}` of the row `acceptance/ceiling` with `items` of weight exactly `ceiling` succeeds; one byte more gives `413 toolarge` with `limit` = `ceiling`. Then the judge deletes the row. The weight is that of P/01.1 N1. If the judge cannot confirm the ceiling, the line is `not_executed` with the reason `installer_ceiling_unproven`.

**Words of `puts` and `expect`.** The directives write through `admin.sock` of the instance, that is `{socket}`, by the operations of P/01.1. A directive that does not pass fails the preparation of its line.

| Form | Meaning | Lesson |
|---|---|---|
| `@view-delete` | `delete` of the row `platform/manifest/<name>/canonical/1` | P/02.2 |
| `@view-spoil` | read the row `platform/manifest/<name>/canonical/1` and write it back with `cas` by the version read, but with the field `manifest` equal to `{}` (a different view: not a projection of the manifest); the other fields as they were | P/02.2 |
| `@rev-delete` | `delete` of the mark `platform/manifest/<name>/rev` | P/02.2 |
| `@rev-spoil` | read the mark `platform/manifest/<name>/rev` and write it back with `cas` by the version read, but with the field `rev` equal to the string `"x"` (a mark not by the form of N1.5 of P/02.3: `rev` is not a decimal integer); the other fields as they were | P/02.2 |
| `@rev-max` | read the row `platform/manifest/<name>`, the mark `platform/manifest/<name>/rev` and the view `platform/manifest/<name>/canonical/1` and write each with `cas` by the version read, where `rev` = `9007199254740991` (2^53 − 1) and the other fields are byte for byte the former ones: the state as after an honest installation with such a revision (P/02.3 N1.5 `rev`); an absent one — the directive does not pass | P/02.3 |
| `@row-spoil <field>` | read the row `platform/manifest/<name>` and write it back with `cas` by the version read, with the field `<field>` of `items` equal to the string `"x"` and the other fields byte for byte; the row has no such field — the directive does not pass. For `yaml`, `sha256` and `rev` the row becomes unreadable by the outcomes of [`manifest-row.outcomes.tsv`](../../02-installer/data/manifest-row.outcomes.tsv) | P/02 |
| `@shell-put <source>` | put next to the working copies the shell `<name>.shell.html` with the bytes of `puts/<source>.shell.html`, replacing the former one; it applies to the following installations of the line. Until then the line has no shell next to the manifest | P/02.3 |
| `@file-fill <path> <bytes>` | put next to the working copies the file `<path>` (relative, without `..`) of exactly `<bytes>` bytes `x`; it applies to the following installations of the line. The subject is the size, so the file is not in `puts/` | P/02.3 |
| `… @stderr ~<text>` | the tail of the cell `expect` after `<code> <rev>`, up to the end of the cell: the stderr of the last installation contains the text as UTF-8 bytes; several substrings are separated by « ~», as for `~text`. Only with `<code>` other than `0`; with `0` it is a data error | P/02 |

## Rights variants

The word `variants` runs every directory `variants/<variant>/` of the first directory. A variant derives rights by meaning on a manifest catalogue outside the stand. Its directory holds the files `*.subsystem.yaml` (the catalogue of the variant) and exactly one of: `expect.tsv`, `refused`, or `check.tsv` with the directory `check/` (judge-only: the variant directories are acceptance data of the judge). A directory with none or with more than one is a data error. The inventory is the physical lines of `expect.tsv` and `check.tsv` and the single line of `refused` (judge-only: the files of the variants).

**`expect.tsv`** (judge-only: a file of the variants). UTF-8, LF, cells separated by TAB, `#` lines skipped. The header is `role<TAB>action<TAB>key<TAB>expect`; then one line per probe: a role of the rights file (P/01.2 N1.1), the action `read`, `write` or `delete`, the row key, and `allow` or `deny`. For the variant the judge:

1. calls the rights derivation command of the target, `stand.rights`, with `{manifests}` — the directory of the variant, `{deployment}` = `dep` and `{file}`. A code other than `0` is a mismatch of every probe of the variant;
2. starts a fresh store instance with this file as `{rights}`;
3. for each line calls through the socket of the role: `read` — `GET /v1/get?key=<key>`, `write` — `put` with `items: {"p": "1"}`, `delete` — `delete`, without `cas` and without a guard. `allow` is only a confirmed success: for a read 200 of the form `Row` (for an absent row `{items: null, index: ""}`, P/01.1 N2), for a write and a deletion 200 `Written`. `deny` is 403 `forbidden`. A role without a socket is the same as 403 (the role is not in the file, P/01.2 N1.3). A 5xx, a transport error or another answer is an undetermined outcome: the probe is neither `allow` nor `deny` and does not match.

The order of the lines does not matter. This checks the meaning of the rights file (P/01.2 N1.3 and `never`), not its bytes: the order of patterns, `comment`, extra equivalent patterns and groups are not compared.

**`refused`.** UTF-8, LF, `#` lines skipped; exactly one other line — the `name` of the manifest of the variant whose declaration is refused. The judge calls `stand.rights` as in item 1. The code MUST be `2`, there is no file at `{file}`, and stderr names this manifest by its `name` or its file. The rest of the text is not compared. The store is not started and there are no probes.

**`check.tsv`.** UTF-8, LF, cells separated by TAB, `#` lines skipped. The header is `case<TAB>file<TAB>code`; then one line per case: `case` — `[a-z0-9_]+`, unique; `file` — `check/<case>.rights`, a rights file; `code` — `0` (the file equals the derived one by meaning) or `!0` (any code except `0`). For each line the judge calls the rights check command of the target, `stand.rights-check`, with `{manifests}` — the directory of the variant, `{deployment}` = `dep` and `{file}` — `check/<case>.rights`, and compares its code with `code`. A profile without `stand.rights-check` leaves every line `not_executed` with the reason `installer_rights_check_missing`.

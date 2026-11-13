# Production qualification of the store

This English text is the canonical `qualification/README.md`; the Russian text is a derived translation for people, not in the export.

## Norms and execution boundary

The owners are P/01.1 (input phases, replay, persistence cost and stage-qualified outcomes), P/01.3 (copy, immutable output, stop, door waits and resources), the [HTTP contract](../spec/01-store.api.openapi.yaml) and [refusal catalogue](../forms/refusals.tsv). This contract assigns acceptance; it adds no platform route beyond that API, no operational flag, no profile2/assembly1 field and no adapter DSL.

Functional scenarios, compilation and an engineering Raft group run do not establish production qualification. Each applicable group below requires independent observations on the same identified candidate under a declared, agreed workload/resource envelope. Missing input, finite budget or qualified binding is blocked/NotExecuted for the dependent group; inactive fault/latch injection is an instrumentation error. A timeout of the judge, forced kill, producer counter, EIO text or library return is not PASS. No candidate execution is claimed by publishing this document.

## Qualified inputs

Before measurement record exact Source/implementation/runner/profile/artifact/fixture/library/compiler identities, invocation and durability mode. Declare workload cardinalities, operation rate/mix, key/item/body sizes, replay locality, checkpoint policy, concurrency and input bytes; record CPU, RAM, storage/filesystem/mount/cache facts relevant to the experiment. The [first approved budgets](#first-approved-budgets) apply to the envelope named there. Cache/eligible-GC, output and cancellation budgets are not approved yet. Each of them, like the budgets of P/01.3 R035 and R036, is a finite positive budget declared by the implementation, and the probe of a dependent case receives its value as input from the environment (ADR-0130 Addendum (5) item 3). The implementation declares the value; the threshold of production acceptance is approved as in ADR-0130 Addendum (9), and a claim of the candidate alone is not enough (ADR-0130 Addendum (15) item 7). The stop budget fits below the actual manager stop deadline with measured teardown margin. Calibrate monotonic resolution/scheduling uncertainty separately; it does not increase a protocol budget. Candidate assertions alone do not qualify these inputs. Unknown values stay unknown, not invented universal defaults.

The qualification stand sets the actual manager stop deadline consistently with `BUDGET_STOP`. It uses the load gate of [N3.3 Declared environment](../../common/acceptance/spec/acceptance.norms.md#n33-declared-environment).

The R141 minimum is strictly more than ID_REPLAY_MIN_AGE AND at least ID_REPLAY_MIN_RECORDS later applied identifier records, owned by [runtime-constants.tsv](../forms/runtime-constants.tsv); it is not a RAM/id upper bound. Test the two edges independently with distinct successful later applications; do not invent a counting rule from unadmitted requests, admitted refusals or replays. The age runs from the first application on the admission-time clock (R141). GC is finite only under the qualified workload/budget. Logical reclaim is not immediate physical file shrink.

## First approved budgets

ADR-0130 Addendum (9) approves these values as the first P/01 budgets. They are reviewed after the first real candidate on a new export. The bounds on declared input-phase intervals come from [P/01.1-R147 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing), and the bound on the declared raw-byte drain limit comes from [P/01.1-R234 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing). Other named normative limits retain their existing sources; this section defines the measurement thresholds and other text uses their names.

The write, import, backup, stop and recovery thresholds below measure the [performance goals](../spec/production-acceptance.md#performance-goals) of M; ADR-0130 Addendum (24) adds the recovery goals. Q retains their measurement conditions and acceptance thresholds. They are acceptance thresholds for the envelope below. They are not implementation constants, flags, profile fields or protocol values. Each is an upper bound on the observed result; this contract sets no lower bound. The implementation still declares its own finite positive intervals under P/01.1-R147. Basis `norm` means the value already exists in the canon; `judgement` means it was chosen from product goals and approved by that Addendum.

| Workload | Value | Source |
|---|---|---|
| `WORKLOAD_ROWS` | 4096 rows | ADR-0113, ordinary size |
| `WORKLOAD_ORDINARY` | 72 MiB; mean row about 18 KiB | ADR-0113, ordinary size |
| `WORKLOAD_WORST` | 2 GiB | ADR-0113, worst size |

For `WORKLOAD_ORDINARY` and `WORKLOAD_WORST`, volume is the sum of the canonical JCS byte lengths of each row's `items` value. Record raw JSONL, request and storage bytes separately; those raw bytes are outside these two workload-volume thresholds. Other budgets and the measurement definitions below are unchanged.

The largest row is the `-max-value` default and the connection limits are the `-max-conns`, `-api-conns` and `-api-per-address` defaults of [daemon-flags.tsv](../forms/daemon-flags.tsv). The sustained write rate is `REPORT_RATE` of the [P/08 form](../../08-domain/forms/runtime-constants.tsv), in writes per second.

| Name | Upper bound | Observed result | Case | Basis |
|---|---|---|---|---|
| `BUDGET_OVERFLOW_REFUSAL` | 1 s | Complete `503` with `Retry-After: 1` to a connection above a connection limit | probe `01-connections` | form `norm`; time `judgement` |
| `BUDGET_IDLE` | [The upper bound for the declared idle interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing) | Wait for the first request byte | RUN-T03 | `judgement` |
| `BUDGET_HEADERS` | [The upper bound for the declared header interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing) | Absolute header phase | RUN-T03 | `judgement` |
| `BUDGET_BODY` | [The upper bound for the declared body interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing) | Absolute body phase | RUN-T03 | `judgement` |
| `BUDGET_DRAIN` | [The upper bound for the declared refusal-drain interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing) and [the bound on the declared raw-byte drain limit in P/01.1-R234](../spec/01.1-store.norms.md#n21-request-parsing) | Raw drain after an early refusal | RUN-T01, RUN-T02 | `judgement` |
| lock wait | the `-leader-wait` value, then `unavailable` | Wait for the mutation lock | RUN-L02, probe `03-lock-wait` | `norm` |
| `BUDGET_WRITE_P99` | 250 ms | Write latency p99 at `REPORT_RATE` | RUN-W01 | `norm` |
| `BUDGET_WRITE_GROWTH` | factor 2 | Write cost at `WORKLOAD_WORST` against `WORKLOAD_ORDINARY` | RUN-W01 | `norm` |
| `BUDGET_WRITE_BYTES` | 5 body sizes | `store_write_bytes` per operation | RUN-W01 | `norm` |
| `BUDGET_IMPORT_ORDINARY` | 30 s | Import of `WORKLOAD_ORDINARY` | RUN-W02 | `norm` |
| `BUDGET_IMPORT_WORST` | 15 min | Import of `WORKLOAD_WORST` | RUN-W02 | `norm` |
| `BUDGET_IMPORT_GROWTH` | factor 13 | Import time for ten times the rows | RUN-W02 | `norm` |
| `BUDGET_MEMORY_ORDINARY` | 512 MiB | Process memory at `WORKLOAD_ORDINARY` | RUN-W04 | `judgement` |
| `BUDGET_MEMORY_WORST` | 4 GiB | Process memory at `WORKLOAD_WORST` | RUN-W04 | `judgement` |
| `BUDGET_BACKUP_ORDINARY` | 30 s | Backup of `WORKLOAD_ORDINARY` | RUN-H01 | `norm` |
| `BUDGET_BACKUP_WORST` | 10 min | Backup of `WORKLOAD_WORST` | RUN-H01 | `norm` |
| `BUDGET_BACKUP_STALL` | factor 2 | Read and write p99 with a stalled backup sink against no stalled sink | RUN-L02 | `norm` |
| `BUDGET_STOP` | 15 s | `graceful_stop_elapsed` | RUN-L03 | `norm` |
| `BUDGET_REOPEN` | 30 s at `WORKLOAD_ORDINARY`; 15 min at `WORKLOAD_WORST` | `reopen_elapsed`: process start after a crash through ordinary service | RUN-W03; RUN-SOAK | `norm` |
| `BUDGET_MEMBER_RETURN` | 60 s at `WORKLOAD_ORDINARY` | `member_return_elapsed`: restarted member start through healthy return | RUN-W03; RUN-SOAK | `norm` |

Barrier outcomes, data directory ownership and framing have no numeric budget: their outcome is judged.

The environment and the method are not budgets. The first budgets were set for a container with 12 usable cores, 32 GiB RAM and ext4 storage. Every run records its actual disk, background load and load at the moment of measurement. `BUDGET_WRITE_P99` is measured in a quiet interval with no other probes running. Warm-up, duration and sampling are the recorded experimental method of the run and add no threshold.

## Case groups

| Id | Initial state and load/fault | Required observation | Binding and negative controls |
|---|---|---|---|
| RUN-W01 | Fixed-size writes at different stored-row cardinalities; account foreground, background and checkpoint cycles. | Incremental persistence; no rewrite of the unchanged full store per application. Barriers remain enabled. | Qualified storage-byte/syscall/heap observer; full-snapshot-per-write and false-counter negative controls. |
| RUN-W02 | Whole immutable copy into a fresh target; invalid last row and duplicate key retain the same valid prefix. | Complete validation precedes publication; exact versions/floor retained; no repeated processed-prefix rewrite. Indexed O(N log N) is allowed. | Declared import and storage observer; partial-publication and replacement-version negative controls. |
| RUN-W03 | Retained successful id, constant business-row count, distinct later successful id applications; exact age/count edges, cache pressure and reopen. Separate crash-reopen and group-member-return slices use the declared ordinary/worst workload. | While either R141 condition is unmet, same answer/again and no new apply/version. Equality at the age minimum is ineligible for forgetting. After both, minimum-retention checks permit either lawful retention or forgetting. Reopen and healthy member return meet their budgets without losing acknowledged state. | Qualified clock/application-count and public replay oracle; age-only/count-only/never-applied request controls. Independent process-start/progress/public-state observation and the controls of [Recovery budget checks](#recovery-budget-checks) serve the recovery slices. |
| RUN-W04 | Constant rows, varied unique-id rate/replay access; qualified RAM/cache and eligible-GC envelope. | RAM eviction preserves required durable indexed ids; eligible backlog is collected within its finite qualified budget. File size need not shrink immediately. | Independent memory/index/replay observation; unbounded map, false gauge and required-id deletion controls. |
| RUN-T01 | Valid POST headers announce a body above the configured limit; withhold the body until the full refusal is received, then continue sending. | Complete refusal before bounded raw drain/close; no business effect or applied id. Compare a separate valid request. | Duplex paced client and declared drain budget; read-before-reply, incomplete-refusal and harness-kill controls. |
| RUN-T02 | Rejected continuing chunked body, never-final chunk, trickle and pipelined next request; malformed framing is a separate precedence control. | Full refusal, finite raw discard and close; no wait for a terminal chunk, second response or pipelined execution. | Raw-stream byte/time observer; half-close alone is insufficient, trickle-reset and inactive-latch controls. |
| RUN-T03 | No-byte accepted connection; partial request line; slow headers; complete headers establishing a body with NO first body byte; body/chunk trickle; separate EOF control. | Use the exact phase starts of R147. Absolute deadlines do not reset. Before supported complete line close silently; after it pre-execution timeout is 400 BadRequestFault/Connection: close. R054 EOF remains silent/no effect/no id. | Declared positive phase budgets and calibrated monotonic observations; first-body-byte start and per-byte-reset mutants. |
| RUN-L01 | Race atomic two-row updates with a copy; record previous destination bytes/mode and inject output failure. | One-index copy with exact versions/no half batch; writer sorts keys by UTF-8 bytes, import accepts any order; failed output preserves previous published file. | Independent copy/atomic-pair and file-publication observations; list-plus-separate-GET, version-loss and partial-file controls. |
| RUN-L02 | Confirm immutable snapshot pin/output start, then stall the sink; concurrent ordinary get/put, cancellation and release. | Blocking output is outside the mutation lock; score that trace independently from a lawful bounded 503. Snapshot stays immutable and releases on every exit. | Qualified sink/lock/progress latch; global-lock streaming, leak and unactivated-latch controls. |
| RUN-L03 | Confirmed stalled backup; separately identify admitted/unadmitted work; SIGTERM under actual manager deadline and measured teardown margin. | Stop admission, bound/cancel external I/O, classify admitted outcomes, release resources and stop within the declared bound. Forced kill or Raft Shutdown return is not graceful success. | Qualified stop/admission/resource observer and real manager configuration; deadlock, false graceful-kill and Raft-only controls. |
| RUN-F01 | Independently proven pre-effect storage fault, known prior business rows/versions and fresh id; retry after clear and reopen. | Unavailable; prior business rows, issued versions and applied-id entry unchanged. Separate allowed admission metadata; no requirement to decrement an internal reservation counter. | Qualified fault stage/no-effect proof and public state; false stage, inactive injection and occupied-id controls. |
| RUN-F02 | Medium activity with an unknown recoverable result; no complete-record premise; same-id retry and qualified reopen. | Ambiguous, no false success/definite absence. Recovered state follows the fault model and whole-operation invariants; rolling back RAM is not proof. | Qualified medium model, not an EIO string or ordinary SIGKILL; false-unavailable/rollback controls. |
| RUN-F03 | Prove complete recoverable operation bytes before a barrier error; keep failure for one same-id replay, then clear and replay, including reopen. | Whole published operation and matching id; repeated barrier error remains ambiguous; successful replay returns first answer/again and no new version. | Independent complete-record/barrier receipts; unconditional rollback, new-version replay and Raft-Barrier-as-fsync controls. |
| RUN-F04 | Two-row batch/id in each F01/F02/F03 stage; separate admitted-refusal/replay metadata control. | Batch and applied id recover whole or are absent whole. Admission advance is not a business mutation; no new status field is assumed. | Independent batch oracle and actual admission observer if supplied; half batch/id-only and false metadata-failure controls. |
| RUN-H01 | Declared backup/import CLI, existing destination and independent complete copy parser. | CLI success, JSONL form, consistent versions, 0600 and atomic publication; opaque CLI alone does not prove HTTP transport. CLI stdout stays diagnostic. | Artifact/import/public-state oracle; truncated artifact, stdout-as-JSON and opaque-transport controls. |
| RUN-H02 | Independent raw HTTP GET /v1/copy on admin and ordinary role sockets; fragmented CL/chunked success, concurrent atomic pairs, wrong method/path and framing precedence. | One 200 application/x-ndjson with complete framing/consistent artifact; exact role 403 before snapshot; 405/Allow GET, HEAD bodyless; other path 404. No private prelude or EOF-only success. | Independent HTTP+JSONL oracle; no producer client as its own judge, no list-plus-GET snapshot or 403 or 404 widening. |
| RUN-H03 | Previous published copy; pre-header snapshot refusal and failures after 200: short CL, missing terminal chunk, EOF, cancel, stalled sink and shutdown. | Before headers use owned failures incl 503 UnavailableFault; after 200 only incomplete close, no second fault/final success. CLI validates full artifact/framing and preserves previous file on any incomplete result. | Independent stream/file/cancellation evidence; false 200 success, second JSON fault and partial-file publication controls. |

## Additional adapter qualification record

RUN-F05 is an additional Q record for the Go Raft adapter. It complements the closed group/probe inventory of `P/01/production`; it adds no row to `forms/production.tsv`, no D7 payload and no requirement for other languages. It uses qualified observations of the existing fault/storage boundaries. A missing conflict/replacement observer or an unactivated control leaves the record blocked/NotExecuted, never a clean result.

| Id | Initial state and load/fault | Required observation | Binding and negative controls |
|---|---|---|---|
| RUN-F05 | A Go group under P/01.3-R180 with three voters and confirmed seed rows; a former leader has a proven uncommitted suffix, the majority commits a conflicting suffix during two-way isolation, then communication resumes. | The former leader replaces the conflict and continues serving without an unexpected command exit or signal (P/01.3-R180); reads return the confirmed rows and versions. | The [conflicting-suffix procedure](stand-procedures.md#former-leader-with-a-conflicting-suffix) requires independent activation evidence and controls; an unproved conflict is blocked/NotExecuted, never PASS. |

## Recovery budget checks

These are separate slices of RUN-W03 and observations in RUN-SOAK, not new groups or directives of J. They check P/01.3-R422 and P/01.3-R423 and the [performance goals](../spec/production-acceptance.md#performance-goals). The machine record `recovery_checks` of [soak.json](../forms/production/soak.json) binds the same goals and observations to the long run.

1. Prepare the current-format store at each applicable workload size with durability enabled. Record acknowledged distinct-key rows, exact versions and still-required replay ids; preserve its complete external history. Confirm the medium is healthy. A group has the same member ids/membership and an available quorum; heal its peer connectivity before starting the timed restart. Cases whose own rules require administrative `recover`/`import`/`restore` remain that separate procedure and do not become timed ordinary reopen cases.
2. Independently confirm a process crash, then restart the same daemon on the same directory. Record process creation/start with the stand's monotonic observer, before opening/replay; do not start at the first successful connection, status response or a candidate readiness log. Retry ordinary requests while retaining every attempt and time. Fix the candidate end timestamp at completion of the successful ordinary read and write through the reopened daemon. Independently check acknowledged state, exact versions and required replay answers before accepting that endpoint; time spent by the qualifier on the later full-state/history check does not consume the candidate budget. A listener/status response, refusal or lost acknowledged row does not finish the interval. Compare the complete interval with `BUDGET_REOPEN` for the recorded workload; do not subtract replay or election time.
3. Separately restart one member of a viable group at `WORKLOAD_ORDINARY`, once as a former follower and once as a former leader; keep its stable id, directory and membership. Drive the declared write load on the remaining quorum while it is absent. Fix a confirmed progress index at return, record it, and require the returning member's own `applied` to reach that fixed index. Complete a fresh write and a current read through that member, crosscheck their exact versions/state with the group and confirm group progress beyond the fixed index. End `member_return_elapsed` at the last required observation and compare the whole interval from process start with `BUDGET_MEMBER_RETURN`. A forwarded answer alone, the leader's applied index or successful status is not local catch-up. Never wait for equality with a moving commit under continuous load.
4. In RUN-SOAK record these same intervals after each applicable crash/restart and healthy return, with workload size and restored prerequisites. Preserve the full history checks across them. A run at an unclassified size or with an active storage/network fault reports that measured scope separately and does not establish either numeric target. For a crash of all members, declare the restart schedule and quorum availability at the timed start before execution, and record all process starts. If the timing preconditions of the goal are not present at that start, retain the full observed intervals as measured scope without a numeric target verdict; do not subtract time, pause the clock or move its start retrospectively. The independent final-state/history checks still apply.

Before scoring the slices, qualify the observer and checker with stand-owned correct and defective reference fixtures. Accept a fixture that restores the acknowledged state and progress within the applicable bound. Reject fixtures that advertise status/listening early while ordinary service is delayed beyond the bound, begin timing only after replay, return stale/missing acknowledged state, or answer through forwarding while the returning member never locally reaches the fixed boundary. For each time target include a fixture at its bound and a delayed fixture just beyond it, using the calibrated observer resolution; equality satisfies the upper bound. A negative control that cannot be activated or observed is an instrument error (`stand`), not a candidate failure or PASS.

The stand records process starts, independent monotonic timestamps, fault removal/connectivity, member id/membership, the fixed index and local `applied`, raw requests/responses, exact versions, replay answers and history/control results. Missing process-start/progress observation, group stand or a qualified required binding leaves the dependent slice `not_executed` with its reason. These procedures do not claim a new executable public checker: until the qualifier/executor implements and qualifies these observations and controls, their execution remains probe debt. The existing public partial checkers and a historical load/fault executor do not discharge it.

## Long random fault run

[`soak.json`](../forms/production/soak.json) is the Q record of the long random fault run. Its duration is 2 h; its group and box fault inventories, observed properties and negative controls are data, not parameters hidden in a task. The [stand procedure](stand-procedures.md#long-random-fault-run) defines the history, controls and evidence. This record complements the case groups and the probes of N6.2; it is not a functional scenario or a new directive of J.

The record checks the existing persistence and version guarantees of P/01.1 and the linearizable reads of P/01.1 R062. Until the qualifier is ready, `court-tools`, `soak/`, revision `6fd588df`, executes the load/fault portion; afterwards that executor is the comparison reference for that scope. Its executor reference covers load and faults only; the new stand controls require their own qualified execution binding as the procedure defines. The publication of the record does not execute it or select a candidate.

Heavy runs use the virtual machine. Until it is available, the run uses CT 103 under the load gate of [N3.3](../../common/acceptance/spec/acceptance.norms.md#n33-declared-environment). VM-only fault/storage slices without qualified bindings remain `not_executed` with their reasons and do not hold promotion until the VM exists. The long run itself remains required for promotion; its absence, a shortened run or an instrument failure does not count as a clean Q result.

## Measurement definitions

| Name | Definition |
|---|---|
| `store_write_bytes` | Actual successful store data/log/checkpoint bytes; count rewrites again, separate HTTP/log/backup bytes and device amplification. |
| `store_read_bytes` | Actual read bytes by lookup/replay/checkpoint/import phase; report cache policy, not physical-device bytes by inference. |
| `durability_barrier_attempts` | Storage barrier attempts/success/errors by operation/checkpoint, including publication directories; Raft Barrier is not fsync. |
| `logical_apply_count` | Confirmed business applications separated from admission metadata and id replay; versions compared as opaque exact strings. |
| `replay_storage_counts` | Separate required/ineligible, eligible, RAM-resident and reclaimed records; crosscheck with public replay. |
| `mutation_lock_hold_wait` | Monotonic hold/wait of the stated mutation-lock domain, separately from Raft/internal locks; no function-name oracle. |
| `backup_progress` | Confirmed pin/output-start/sink-block/cancel/release order and delivered bytes; a latch receipt excludes startup delay. |
| `graceful_stop_elapsed` | Confirmed stop delivery to orderly exit and resource release; record manager escalation/forced kill separately. |
| `reopen_elapsed` | Independent monotonic interval from the daemon process start after a crash through completed ordinary read/write service; includes state opening/replay and a viable quorum when applicable. Later full-state/history checks validate the endpoint but their own execution time is outside it. |
| `member_return_elapsed` | Independent monotonic interval from the restarted member process start through local application of the fixed confirmed progress boundary, current reads/writes through it and subsequent group progress. Record stable member id, membership and the fixed boundary. |
| `early_refusal_timeline` | Complete client refusal receipt, continuing send, raw drain bytes, absolute interval, close and independent healthy progress. |
| `fault_stage_receipt` | Independent activation/effect/barrier and recoverable-or-unknown classification, tied to public state/id/reopen. |
| `copy_transport_evidence` | Independent HTTP headers/framing/completion plus whole JSONL grammar, atomic publication and prior-file preservation. |

## Public executable probes

The [store probes](../probes/README.md) are eight public observation checkers over these groups. They cover partial slices and judge supplied observations only. They are no production result and no implementation input.

The environment of the stand, the D7 providers on a virtual machine with their controls, the history check across faults and the procedures of `prod-disk-fd`, `prod-replay-limit` and `prod-admin-limit` are in [the stand procedures](stand-procedures.md).

### Probe debt

The checks below have no executable probe yet. Until one exists, each stays checked by reading, and its group is blocked/NotExecuted for production qualification, not a success (ADR-0130 Addendum (13)). Runner writes the probes and their negative controls; this table names the debt and adds no route, flag or value. A capacity input comes from the environment (ADR-0130 Addendum (5) item 3). A clock input comes through the `clock` binding of [D7](../../common/acceptance/seams.md#d7-test-side-evidence-bindings) (ADR-0130 Addendum (11)); until that binding is supplied, the dependent case is `MissingBinding`/`NOTEXEC`.

| Missing check | Norm | Input |
|---|---|---|
| RUN-W03 and RUN-SOAK recovery-budget observations/controls | P/01.3 R422, R423 | independent process start, monotonic/public-state and local catch-up observations; group stand for member return |
| RUN-L03, executable, with added initial states: an admitted write, a door forwarding, a connection in an input phase, a request read but not admitted | P/01.3 R034 | qualified stop observer and actual manager configuration |
| RUN-F01, RUN-F02, RUN-F04, executable | P/01.1 R144 | qualified fault-stage binding |
| Loss of the leader after sending (the death of the leader; a held answer of a forwarded write); a two-way partition of a member | P/01.3 N1.3 `leader_wait`; P/01.1 N4 `ambiguous_leader` | group stand with held or cut answers |
| Interrupted `import` in a group: start, holding writers, reads answered as the store `file://`, continuation through `admin.sock` of the leader, `recover` after the loss of a majority | P/01.3 N1.3 `import`; P/01.3 R156, R159 | group stand with an interruption |
| Interrupted `recover`: phase mark, start refusal with code 2, repeat from the start | P/01.3 R265, R267, R398 | qualified interruption point |
| Full disk and exhausted descriptors | P/01.3 R036, R260 | capacity input from the environment |
| Leader change and snapshot with different clocks; `admission_ahead` | P/01.3 N1.3 `admission`; P/01.1 R070 | D7 `clock` binding; not executable on the stand of one machine (below, «Clocks in a group») |
| Response-write budget; commit wait under a live leader | P/01.3 R035, R326 | slow reader and slow commit from the environment |
| Door attempts against `-leader-wait`; all voters unreachable | P/01.3 R252 | group stand |
| Replay-processing limit | P/01.3 R329 | overload input from the environment |
| `admin.sock` limit when the ordinary limits are exhausted | P/01.3 R008, R200 | connection exhaustion from the environment |
| Temporary `backup` file after failure, cancellation and a killed run | P/01.3 R018 | qualified fault binding |
| Age of the `id` memory from the first application on the admission-time clock | P/01.1 R141 | D7 `clock` binding |

### Clocks in a group

ADR-0130 Addendum (15) item 8 and Addendum (11): this is the public scope of a D7 [`clock` binding](../../common/acceptance/seams.md#d7-test-side-evidence-bindings) in a store group. It adds no field, route, flag, directive or number, and it is not a qualification.

A node is addressed by its stable daemon `-id` in the topology of the case (P/01.3 N1.3). Leader and follower are observed changing roles (`leader_id` of `/v1/status`), not addresses. One `clock` provider controls the explicitly listed consuming wall-clock domains of the case, each named by the `-id` of its node; a domain that is not listed is not controlled. The independent monotonic baseline of the observer is not shifted. Offsets use the seconds of the wall stamps of the chapter, and no skew allowance is added.

The checks of P/01.1 R013 are the actual spread between the clocks beyond `CLOCK_SKEW`, a common shift and return, and the non-decrease of admission time. The probes also need a leader change, a Raft snapshot, the equality of admission time, and a replay held after `not_after` before the first application. Writer and client clocks belong to the scope only when the selected workload actually uses them; live P/03, P/04 or new N−1 stands are not assumed. Until the public case payload and a qualified provider exist, a dependent check stays `MissingBinding`/`NOTEXEC`.

The declared environment of the judge (P/AC N3.3) gives the processes of a run only the loopback, and the group stand puts all members on the loopback of one machine, which has one wall clock. The clocks of the members cannot differ there, so `prod-clock-group` is not executable on that stand and is `not_executed` with the reason `clock`; the environment of N3.3 is not widened for it.

## Evidence and outcomes

Separate actual protocol output/state/replay from test-only instrumentation. Qualify each storage/clock/progress/fault binding independently with activated-stage receipts and negative controls; do not infer physical durability from ordinary process restart or SIGKILL. Complete recoverable bytes must be proved before judging the R144 ambiguous_barrier branch. Compare whole batch/id state, and admission metadata separately. An absent binding is not proof that an implementation is wrong or successful.

Record raw input/output/status/signal/timeout, monotonic phase and activation order, full case/identity inventory including failures, resource cleanup and reopen observations. Report normative mismatch, instrumentation error, blocked/NotExecuted and successful measured scope separately; no silent skip or weaker expected result. Raw-copy controls include correct ordinary-role GET403 before snapshot, unsupported-method 405/Allow GET and bodyless HEAD, complete CL/chunked, missing first body byte, missing terminal chunk, short CL, after 200 no second fault, and preservation of the previous published file. These are controlled fixtures and future candidate obligations, not an executed SUT or a new private platform protocol.

## Related parsing and scope

P/05 keeps its ResourceError/ResourceDenied and body/time outcomes; P/06 parsing is owned by [gate-and-pass](../../common/contracts/gate-and-pass.md). They share R050 response-before-raw-drain, not P/01 timeout response codes or a replacement budget for forwarding, pass or stream responses. The engineering group stage remains available independently of missing production qualification inputs, with its applicable/unexecuted production groups and normative pin recorded.

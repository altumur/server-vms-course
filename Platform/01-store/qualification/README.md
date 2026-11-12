# Production qualification of the store

This English text is the canonical `qualification/README.md`; the Russian text is a derived translation for people, not in the export.

## Norms and execution boundary

The owners are P/01.1 (input phases, replay, persistence cost and stage-qualified outcomes), P/01.3 (copy, immutable output, stop, door waits and resources), the [HTTP contract](../spec/01-store.api.openapi.yaml) and [refusal catalogue](../forms/refusals.tsv). This contract assigns acceptance; it adds no platform route beyond that API, no operational flag, no profile2/assembly1 field and no adapter DSL.

Functional scenarios, compilation and an engineering Raft group run do not establish production qualification. Each applicable group below requires independent observations on the same identified candidate under a declared, agreed workload/resource envelope. Missing input, finite budget or qualified binding is blocked/NotExecuted for the dependent group; inactive fault/latch injection is an instrumentation error. A timeout of the judge, forced kill, producer counter, EIO text or library return is not PASS. No candidate execution is claimed by publishing this document.

## Qualified inputs

Before measurement record exact Source/implementation/runner/profile/artifact/fixture/library/compiler identities, invocation and durability mode. Declare workload cardinalities, operation rate/mix, key/item/body sizes, replay locality, checkpoint policy, concurrency and input bytes; record CPU, RAM, storage/filesystem/mount/cache facts relevant to the experiment. The [first approved budgets](#first-approved-budgets) apply to the envelope named there. Cache/eligible-GC, output and cancellation budgets are not approved yet. Each of them, like the budgets of P/01.3 R035 and R036, is a finite positive budget declared by the implementation, and the probe of a dependent case receives its value as input from the environment (ADR-0130 Addendum (5) item 3). The implementation declares the value; the threshold of production acceptance is approved as in ADR-0130 Addendum (9), and a claim of the candidate alone is not enough (ADR-0130 Addendum (15) item 7). The stop budget fits below the actual manager stop deadline with measured teardown margin. Calibrate monotonic resolution/scheduling uncertainty separately; it does not increase a protocol budget. Candidate assertions alone do not qualify these inputs. Unknown values stay unknown, not invented universal defaults.

The R141 minimum is strictly more than ID_REPLAY_MIN_AGE AND at least ID_REPLAY_MIN_RECORDS later applied identifier records, owned by [runtime-constants.tsv](../forms/runtime-constants.tsv); it is not a RAM/id upper bound. Test the two edges independently with distinct successful later applications; do not invent a counting rule from unadmitted requests, admitted refusals or replays. The age runs from the first application on the admission-time clock (R141). GC is finite only under the qualified workload/budget. Logical reclaim is not immediate physical file shrink.

## First approved budgets

ADR-0130 Addendum (9) approves these values as the first P/01 budgets. They are reviewed after the first real candidate on a new export. The bounds on declared input-phase intervals come from [P/01.1-R147 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing). This section is the source of the other thresholds; other text uses their names.

They are acceptance thresholds for the envelope below. They are not implementation constants, flags, profile fields or protocol values. Each is an upper bound on the observed result; this contract sets no lower bound. The implementation still declares its own finite positive intervals under P/01.1-R147. Basis `norm` means the value already exists in the canon; `judgement` means it was chosen from product goals and approved by that Addendum.

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
| `BUDGET_DRAIN` | [The upper bound for the declared refusal-drain interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing) and at most the `-max-body` value in raw bytes | Raw drain after an early refusal | RUN-T01, RUN-T02 | `judgement` |
| lock wait | the `-leader-wait` value, then `unavailable` | Wait for the mutation lock | RUN-L02, probe `03-lock-wait` | `norm` |
| `BUDGET_WRITE_P99` | 250 ms | Write latency p99 at `REPORT_RATE` | RUN-W01 | `judgement` |
| `BUDGET_WRITE_GROWTH` | factor 2 | Write cost at `WORKLOAD_WORST` against `WORKLOAD_ORDINARY` | RUN-W01 | `judgement` |
| `BUDGET_WRITE_BYTES` | 5 body sizes | `store_write_bytes` per operation | RUN-W01 | `judgement` |
| `BUDGET_IMPORT_ORDINARY` | 30 s | Import of `WORKLOAD_ORDINARY` | RUN-W02 | `judgement` |
| `BUDGET_IMPORT_WORST` | 15 min | Import of `WORKLOAD_WORST` | RUN-W02 | `judgement` |
| `BUDGET_IMPORT_GROWTH` | factor 13 | Import time for ten times the rows | RUN-W02 | `judgement` |
| `BUDGET_MEMORY_ORDINARY` | 512 MiB | Process memory at `WORKLOAD_ORDINARY` | RUN-W04 | `judgement` |
| `BUDGET_MEMORY_WORST` | 4 GiB | Process memory at `WORKLOAD_WORST` | RUN-W04 | `judgement` |
| `BUDGET_BACKUP_ORDINARY` | 30 s | Backup of `WORKLOAD_ORDINARY` | RUN-H01 | `judgement` |
| `BUDGET_BACKUP_WORST` | 10 min | Backup of `WORKLOAD_WORST` | RUN-H01 | `judgement` |
| `BUDGET_BACKUP_STALL` | factor 2 | Read and write p99 with a stalled backup sink against no stalled sink | RUN-L02 | `judgement` |
| `BUDGET_STOP` | 15 s | `graceful_stop_elapsed` | RUN-L03 | limit `norm`; margin `judgement` |

Barrier outcomes, data directory ownership and framing have no numeric budget: their outcome is judged.

The environment and the method are not budgets. The first budgets were set for a container with 12 usable cores, 32 GiB RAM and ext4 storage. Every run records its actual disk, background load and load at the moment of measurement. `BUDGET_WRITE_P99` is measured in a quiet interval with no other probes running. Warm-up, duration and sampling are the recorded experimental method of the run and add no threshold.

## Case groups

| Id | Initial state and load/fault | Required observation | Binding and negative controls |
|---|---|---|---|
| RUN-W01 | Fixed-size writes at different stored-row cardinalities; account foreground, background and checkpoint cycles. | Incremental persistence; no rewrite of the unchanged full store per application. Barriers remain enabled. | Qualified storage-byte/syscall/heap observer; full-snapshot-per-write and false-counter negative controls. |
| RUN-W02 | Whole immutable copy into a fresh target; invalid last row and duplicate key retain the same valid prefix. | Complete validation precedes publication; exact versions/floor retained; no repeated processed-prefix rewrite. Indexed O(N log N) is allowed. | Declared import and storage observer; partial-publication and replacement-version negative controls. |
| RUN-W03 | Retained successful id, constant business-row count, distinct later successful id applications; exact age/count edges, cache pressure and reopen. | While either R141 condition is unmet, same answer/again and no new apply/version. Equality at the age minimum is ineligible for forgetting. After both, minimum-retention checks permit either lawful retention or forgetting. | Qualified clock/application-count and public replay oracle; age-only/count-only/never-applied request controls. |
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
| `early_refusal_timeline` | Complete client refusal receipt, continuing send, raw drain bytes, absolute interval, close and independent healthy progress. |
| `fault_stage_receipt` | Independent activation/effect/barrier and recoverable-or-unknown classification, tied to public state/id/reopen. |
| `copy_transport_evidence` | Independent HTTP headers/framing/completion plus whole JSONL grammar, atomic publication and prior-file preservation. |

## Public executable probes

The [store probes](../probes/README.md) are eight public observation checkers over these groups. They cover partial slices and judge supplied observations only. They are no production result and no implementation input.

### Probe debt

The checks below have no executable probe yet. Until one exists, each stays checked by reading, and its group is blocked/NotExecuted for production qualification, not a success (ADR-0130 Addendum (13)). Runner writes the probes and their negative controls; this table names the debt and adds no route, flag or value. A capacity input comes from the environment (ADR-0130 Addendum (5) item 3). A clock input comes through the `clock` binding of [D7](../../common/acceptance/seams.md#d7-test-side-evidence-bindings) (ADR-0130 Addendum (11)); until that binding is supplied, the dependent case is `MissingBinding`/`NOTEXEC`.

| Missing check | Norm | Input |
|---|---|---|
| RUN-L03, executable, with added initial states: an admitted write, a door forwarding, a connection in an input phase, a request read but not admitted | P/01.3 R034 | qualified stop observer and actual manager configuration |
| RUN-F01, RUN-F02, RUN-F04, executable | P/01.1 R144 | qualified fault-stage binding |
| Loss of the leader after sending (the death of the leader; a held answer of a forwarded write); a two-way partition of a member | P/01.3 N1.3 `leader_wait`; P/01.1 N4 `ambiguous_leader` | group stand with held or cut answers |
| Interrupted `import` in a group: start, holding writers, continuation through `admin.sock` of the leader, `recover` after the loss of a majority | P/01.3 N1.3 `import` | group stand with an interruption |
| Interrupted `recover`: phase mark, start refusal with code 2, repeat from the start | P/01.3 N3 R021 | qualified interruption point |
| Full disk and exhausted descriptors | P/01.3 R036 | capacity input from the environment |
| Leader change and snapshot with different clocks; `admission_ahead` | P/01.3 N1.3 `admission`; P/01.1 R070 | D7 `clock` binding |
| Response-write budget; commit wait under a live leader | P/01.3 R035 | slow reader and slow commit from the environment |
| Door attempts against `-leader-wait`; all voters unreachable | P/01.3 R035 | group stand |
| Replay-processing limit | P/01.3 R035 | overload input from the environment |
| `admin.sock` limit when the ordinary limits are exhausted | P/01.3 R008 | connection exhaustion from the environment |
| Temporary `backup` file after failure, cancellation and a killed run | P/01.3 R018 | qualified fault binding |
| Age of the `id` memory from the first application on the admission-time clock | P/01.1 R141 | D7 `clock` binding |

### Clocks in a group

ADR-0130 Addendum (15) item 8 and Addendum (11): this is the public scope of a D7 [`clock` binding](../../common/acceptance/seams.md#d7-test-side-evidence-bindings) in a store group. It adds no field, route, flag, directive or number, and it is not a qualification.

A node is addressed by its stable daemon `-id` in the topology of the case (P/01.3 N1.3). Leader and follower are observed changing roles (`leader_id` of `/v1/status`), not addresses. One `clock` provider controls the explicitly listed consuming wall-clock domains of the case, each named by the `-id` of its node; a domain that is not listed is not controlled. The independent monotonic baseline of the observer is not shifted. Offsets use the seconds of the wall stamps of the chapter, and no skew allowance is added.

The checks of P/01.1 R013 are the actual spread between the clocks beyond `CLOCK_SKEW`, a common shift and return, and the non-decrease of admission time. The probes also need a leader change, a Raft snapshot, the equality of admission time, and a replay held after `not_after` before the first application. Writer and client clocks belong to the scope only when the selected workload actually uses them; live P/03, P/04 or new N−1 stands are not assumed. Until the public case payload and a qualified provider exist, a dependent check stays `MissingBinding`/`NOTEXEC`.

## Evidence and outcomes

Separate actual protocol output/state/replay from test-only instrumentation. Qualify each storage/clock/progress/fault binding independently with activated-stage receipts and negative controls; do not infer physical durability from ordinary process restart or SIGKILL. Complete recoverable bytes must be proved before judging the R144 ambiguous_barrier branch. Compare whole batch/id state, and admission metadata separately. An absent binding is not proof that an implementation is wrong or successful.

Record raw input/output/status/signal/timeout, monotonic phase and activation order, full case/identity inventory including failures, resource cleanup and reopen observations. Report normative mismatch, instrumentation error, blocked/NotExecuted and successful measured scope separately; no silent skip or weaker expected result. Raw-copy controls include correct ordinary-role GET403 before snapshot, unsupported-method 405/Allow GET and bodyless HEAD, complete CL/chunked, missing first body byte, missing terminal chunk, short CL, after 200 no second fault, and preservation of the previous published file. These are controlled fixtures and future candidate obligations, not an executed SUT or a new private platform protocol.

## Related parsing and scope

P/05 keeps its ResourceError/ResourceDenied and body/time outcomes; P/06 parsing is owned by [gate-and-pass](../../common/contracts/gate-and-pass.md). They share R050 response-before-raw-drain, not P/01 timeout response codes or a replacement budget for forwarding, pass or stream responses. The engineering group stage remains available independently of missing production qualification inputs, with its applicable/unexecuted production groups and normative pin recorded.

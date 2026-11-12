# Production obligations of the store

This English text is the canonical `spec/production-acceptance.md`; the Russian text is a derived translation for people, not in the export.

## Norms and execution boundary

The owners are P/01.1 (input phases, replay, persistence cost and stage-qualified outcomes), P/01.3 (copy, immutable output, stop, door waits and resources), the [HTTP contract](01-store.api.openapi.yaml) and [refusal catalogue](../forms/refusals.tsv). These obligations add no platform route beyond that API, no operational flag, no profile2/assembly1 field and no adapter DSL.

## Finite budgets

The implementation declares finite positive budgets for cache and eligible GC, output and cancellation, and the waits and resources of P/01.3 R035 and R036. Budgets apply to the declared workload/resource envelope. The stop budget fits below the actual manager stop deadline with teardown margin.

Scheduling uncertainty does not increase a protocol budget. Workload sizes and acceptance thresholds are not implementation constants, flags, profile fields or protocol values, and they set no lower bound on an interval. The implementation declares its own finite positive input-phase intervals under P/01.1-R147.

## Incremental write cost

Persistence of a fixed-size ordinary write is incremental: it does not rewrite the unchanged full store per application. Foreground, background and checkpoint work all count towards persistence cost. Durability barriers remain enabled.

## Import validation and cost

Complete validation of the whole immutable input precedes publication. Import retains exact versions and floor and does not repeatedly rewrite the already processed prefix. Indexed O(N log N) construction is allowed.

## Replay retention

While either minimum-retention condition of R141 is unmet, replay returns the same answer/again without a new application or version. The minimum is strictly more than ID_REPLAY_MIN_AGE and at least ID_REPLAY_MIN_RECORDS later applied identifier records, owned by [runtime-constants.tsv](../forms/runtime-constants.tsv). The age starts at the first application on the admission-time clock; equality at the age minimum is ineligible for forgetting. Unadmitted requests, admitted refusals and replays do not count as later successful applications.

Once both conditions hold, either lawful retention or forgetting is allowed. This minimum is not a RAM/id upper bound.

## Replay resources

RAM eviction preserves required durable indexed ids. Under the qualified workload/resource envelope, eligible backlog is collected within its declared finite budget. Logical reclaim does not require immediate physical file shrink.

## Early refusal

A complete refusal precedes bounded raw drain and close and causes no business effect or applied-id entry. For a rejected continuing chunked body, raw discard is finite and the connection closes without waiting for a terminal chunk, sending a second response or executing a pipelined request. Malformed framing keeps its own refusal priority.

## Input phase deadlines

Input phases use the exact starts of R147; their deadlines are absolute and do not reset with arriving bytes. Before a supported complete request line, timeout closes the connection silently. After that line, a pre-execution timeout is 400 BadRequestFault with Connection: close. EOF under R054 remains silent, without business effect or applied id.

## Consistent copy and publication

A copy comes from one index, retains exact versions and contains no half batch. Its writer sorts keys by UTF-8 bytes; import accepts any order. Failed output preserves the previous published file and its mode.

## Snapshot output and release

Blocking output runs outside the mutation lock. A lawful bounded 503 does not relax that obligation. A pinned snapshot remains immutable and releases on every exit, including cancellation.

## Graceful stop

Stop ends admission, bounds or cancels external I/O, classifies admitted outcomes, releases resources and completes orderly exit within the declared bound. A forced kill or return from Raft Shutdown alone is not graceful completion.

## Proven pre-effect failure

A storage refusal proven to precede any business effect returns unavailable. Prior business rows, issued versions and the applied-id entry remain unchanged. Allowed admission metadata is separate from a business mutation; an internal reservation counter need not be decremented.

## Unknown storage result

Storage activity with an unknown recoverable result returns ambiguous, without a false success or definite absence claim. Recovered state follows the fault model and whole-operation invariants. Rolling back RAM does not establish an absent durable effect.

## Complete record and failed barrier

Where complete recoverable operation bytes precede a barrier error, the operation and its matching applied id are whole. A repeated barrier error on same-id replay remains ambiguous. A successful replay returns the first answer/again without a new version. A Raft Barrier is not a filesystem durability barrier.

## Batch and id recovery

At each pre-effect, unknown-result and complete-record/barrier stage, a batch and its applied id recover whole or are absent whole. Admission advance is not a business mutation; these obligations assume no new status field.

## Backup CLI and artifact

CLI success requires the whole JSONL copy, consistent versions, mode 0600 and atomic publication. CLI stdout stays diagnostic. An opaque CLI result alone does not establish HTTP transport correctness.

## HTTP copy

GET /v1/copy returns one 200 application/x-ndjson response with complete HTTP framing and a consistent whole artifact. An ordinary-role request gets exactly role 403 before a snapshot; an unsupported method gets 405 with Allow GET, HEAD has no body, and another path gets 404. A private prelude, EOF alone, or a list followed by separate GET operations cannot replace a complete one-index HTTP copy.

## Incomplete copy output

Before response headers, snapshot refusal uses the owned failures, including 503 UnavailableFault. After 200, failure only closes incomplete output; it sends no second fault or final success. The CLI validates the whole artifact and framing and preserves the previous published file on every incomplete result, including cancellation and shutdown.

## Related parsing and scope

P/05 keeps its ResourceError/ResourceDenied and body/time outcomes; P/06 parsing is owned by [gate-and-pass](../../common/contracts/gate-and-pass.md). They share R050 response-before-raw-drain, not P/01 timeout response codes or a replacement budget for forwarding, pass or stream responses.

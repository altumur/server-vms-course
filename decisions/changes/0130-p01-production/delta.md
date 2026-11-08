# Delta 0130-p01-production — production obligations

change: 0130-p01-production rev 1. Base 2a63643ff3f338972dda9ec32231089ad38e66ea; lesson P/01, related P/05 and common parsing. State review.

Unit normalization: LF, strip trailing spaces, one final LF; headings outside code fences terminate the preceding requirement unit. Unmarked implementation/checklist/lifecycle/coverage text is represented separately by the complete raw source-map and artifact manifest, not falsely assigned to the last req.

## ADDED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R147

<!-- req: P/01.1-R147 -->
- **Input phase deadlines.** The implementation MUST declare finite positive idle, header, body and refusal-drain intervals, measured by monotonic time. Idle starts when a connection is accepted or the previous response completes. The absolute header deadline starts at the first byte of the request line. The absolute body deadline starts after complete headers have been parsed and establish a body, even if no body byte ever arrives. A slow trickle MUST NOT extend an absolute deadline; any additional inactivity interval is declared separately. Before a correct complete request line with a supported HTTP version exists, an input deadline closes the connection without an invented response. After that line, an input timeout before execution returns `400 BadRequestFault` with `Connection: close` if no response has started; no operation, business write or applied-id record is made. A started response gets no second fault. This timeout rule does not replace R054: EOF or a truncated body still receives no answer, is not executed and does not occupy an id. The phase budgets describe P/01 input, not a common deadline for forwarding, pass or stream responses owned by other lessons.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R148

<!-- req: P/01.1-R148 -->
For production qualification persistence of an ordinary fixed-size write MUST be incremental: each application MUST NOT serialize or rewrite the whole unchanged row store. Checkpoint work is accounted separately and in the amortized total; a background thread does not hide it. Import checks the entire immutable input before publication, then builds the state without repeatedly rewriting the already processed prefix. Indexed construction or sorting in O(N log N) is allowed; no particular WAL, engine or consensus algorithm is prescribed. Input bytes and stored-row cardinality are measured separately. Existing versions, the floor, transfer phases and durability barriers are preserved. The implementation declares its cost model and the qualified workload/resources; no universal numeric ceiling is supplied by this rule.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R033

<!-- req: P/01.3-R033 -->
**HTTP copy.** `GET /v1/copy` is available only through `admin.sock`; a role header or network forwarding grants no administrative access. A correct GET on an ordinary role socket returns exactly `403 ForbiddenFault` before opening or exposing a snapshot. The R017 order framing → route/method → identity still applies. Success is one `200` with `Content-Type: application/x-ndjson`: the existing UTF-8/LF `w2c-configstore-copy`, version 1, at one consistent index, without a private prelude. An exact `Content-Length` or valid completed chunked transfer is required; connection close alone is not successful framing. An unsupported method on this path is `405 BadRequestFault` with `Allow: GET`; HEAD has no body. A different path keeps the existing `404`. Before successful headers an unavailable consistent snapshot or expired wait is `503 UnavailableFault`; request and access failures keep their own existing forms. This read does not produce a write's `AmbiguousFault`.

After `200` headers a failure only closes the stream: do not send a second JSON fault, a final zero chunk after failed chunked output, or a false complete Content-Length response. Completion is not signalled before the whole artifact. The backup CLI validates both HTTP completion and the whole existing copy grammar, writes a `0600` temporary file and renames only after success; failure/cancellation preserves the previous published file. Allowed unreadable copy rows and the separate import/restore refusal on such input remain unchanged. There is no new HTTP import/restore or compatible private copy alias. Other internal named/versioned read-fence/admit/import frames remain allowed by «Implementation decides» item 1; this HTTP operation is the narrow exception for the copy transfer itself. CLI stdout remains diagnostic, not a machine JSON contract.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R034

<!-- req: P/01.3-R034 -->
A copy MUST pin one immutable version of the state. Blocking external output MUST run outside the lock that serializes ordinary mutations. The implementation declares finite bounds for lock wait, output, cancellation and orderly stop; a stalled receiver MUST NOT retain the mutation lock until transmission finishes. Success, failure and cancellation release snapshot and transport ownership. An unrelated operation may keep its existing bounded pre-effect refusal; that response alone does not prove correct lock scope.

On stop, cease admitting new work, cancel or bound external I/O, and resolve or classify admitted work by its existing definite/ambiguous outcomes. Retire owned snapshots, connections and listeners within the declared orderly-stop bound. This bound MUST fit below the actual service-manager stop deadline with a separately measured teardown margin. The manager's old example is not a Go Shutdown budget; forced kill is not orderly success. Raft Barrier is not evidence of a storage durability barrier, and a Raft Shutdown return is not proof that the platform has drained its work. Import's complete-input check, exact versions and floor/progress phases remain unchanged; construction obeys [P/01.1 Persistence cost](01.1-store.norms.md#persistence-cost).

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R050

old-sha256: c219fd7926c119e0732fd79b37ed546c6c40201984bb566df43ee9ff81d39ef6

<!-- req: P/01.1-R050 -->
- **Early refusal.** Before reading the whole body, the door MUST send the complete refusal with `Connection: close` first, then discard raw HTTP-stream bytes without parsing or executing the rejected body, then close. Discard stops at the declared body length when framing supplies one, or earlier at the declared raw-byte limit or absolute monotonic drain deadline. The drain interval starts after the complete refusal has been sent; incoming bytes do not extend it. A chunked sender need not send a terminal chunk for discard to finish. A second request or fault response is not executed or added after this refusal. The drain volume and time are declared in item 9 of «Implementation decides». This shared refusal-before-drain rule also applies at the console ([P/06.5](../../06-console/spec/06.5-console.norms.md)), its bytes door (P/06.1) and the resource (P/05); their own parsing outcomes and response/stream budgets remain with their owners.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R141

old-sha256: 26638392aa1c567493c7a171d6d49c47be79b9e013c68c2a7a15712368fc0e03

<!-- req: P/01.1-R141 -->
The store MUST answer a replay with the same answer until both conditions hold: more than `ID_REPLAY_MIN_AGE` has passed since the first application **and** at least `ID_REPLAY_MIN_RECORDS` records with an identifier have been applied after it; when both hold, it MAY forget. A forgotten replay is applied as a new write — hence `cas` on every write that matters.

For production qualification a bounded RAM cache MUST retain access to every still-required replay record through a durable indexed store. Cache eviction MUST NOT forget an ineligible id. Under the qualified declared workload, eligible records MUST be collected within the declared finite collection budget. This budget does not weaken either minimum condition. Logical index reclamation and space reuse do not promise an immediate file-size or filesystem-free-space decrease. Memory pressure adds no external refusal and does not turn an uncertain write into a definitely absent one. The teaching store's explicitly named non-durable mode remains distinct from production qualification.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R144

old-sha256: 2fff20f4a1f529b73deb075789b1155efa6cc0eb228d086d96ea156ad2f71ed4

<!-- req: P/01.1-R144 -->
A closed list. The text of `error` is for people and is not normative; the code, `kind` and the fields are.

- `key_rules`: a key not by the rules of N1 (empty, starting with `/`, with a segment `..`, longer than the limit) — the target key; for a guard row — a non-empty key not by the rules (an empty guard key is `badrequest`: out of the form of `guard`); the bytes of a read `key` after decoding are not UTF-8; a lone surrogate in `key` or `guard.key` (N2.1). Caller action: nothing: a code error.
- `body_form`: the body is not a JSON object or not JSON by N2.1 (a repeated field name, `NaN`, `Infinity`, a BOM, not UTF-8, deeper than the limit); `key` or `prefix` repeated in the query; the request does not parse as HTTP (N2.1); `op` is not `put`, `delete`, `batch` or `floor` (`floor` — P/01.3 N2); a lone surrogate in `items`; `key` of a command, `guard.key` or the read parameter `key` is absent or not a string; `items` is not an object of strings for `put`; `cas`, `guard`, `id`, `not_after` or `not_before` out of form (N1); `id` already belongs to another write; a batch out of the form of N1: `writes` absent, empty, not an array or longer than `BATCH_WRITES`, `guards` not an array or longer than `BATCH_GUARDS`, an element not in its closed form, a key twice in `writes` or in `guards`, a guard on a key from `writes`. Caller action: nothing: a code error.
- `no_route`: no route, or no such method on it (N2.1). Caller action: nothing.
- `identity`: the identity is not admitted by P/01.2 N3 «check» (list included): a role header on a role socket, an untrusted forwarding or a forbidden forwarded admin; `op: floor` not on the admin socket (P/01.3 N4). Caller action: fix the identity/trust; the absence of read by itself does not forbid list.
- `rights`: no rights (read, write, delete, guard read). Caller action: nothing: a deployment error or a foreign process (P/01.2 N4, rows «… without permission»).
- `cas_mismatch`: the version of the row is not the one in `cas`. Caller action: re-read, apply your own on top, repeat.
- `expired`: the admission time is later than `not_after` (N3 «Admission time»; ADR-0091 item 1). Caller action: do not repeat with the same write: the deadline of the write has passed; a new one is decided by the caller by its own norm (an order — [P/03.6](../../03-worker/spec/03.6-worker.norms.md)).
- `early`: the admission time is not later than `not_before` (ADR-0091 item 1). Caller action: do not repeat with the same write; a new write — at the next step (deleting a row with `made` — [P/04](../../04-controller/spec/04-controller.norms.md), P/03.6).
- `guard_mismatch`: the guard row is not at the version (for a batch — the first in the order of `guards`). Caller action: do not repeat: re-read the slot and check ownership anew ([P/03.2 N3 «write_under_slot»](../../03-worker/spec/03.2-worker.norms.md); the worker — [P/03.4 N4](../../03-worker/spec/03.4-worker.norms.md) «write under slot: `412 guard`»).
- `weight`: the row is heavier than the ceiling (for a batch — the first in the order of `writes`, nothing written). Caller action: nothing: what makes the row heavy goes into an object: a field `type: blob`, the bytes by the door `PUT /<rows>/<id>/<blob_field>` (P/06.1 N1.5, N2).
- `body_limit`: the body is larger than the read limit of N2; the store operation is not called. Caller action: shrink the body; compare its size with the body limit exactly.
- `no_leader_wait`, `lock_wait`, `connection_limit_doors`: no leader was found within the wait time, or the wait time of the local lock expired (item 1 of «Implementation decides»), or there are more connections than the declared limit of the door (added by M10/11: `-max-conns` N1.3, a row of N4); the operation is **not done** — for a write, a read and a listing. Caller action: repeat at the next step of the cycle (with `Retry-After` — not before the deadline); hold what you hold.
- `floor_not_higher`: (added by M10/11) the service `op: floor` on the admin socket (only P/01.3 N2): the new value is not larger than the current one. Caller action: nothing: the lower bound of epochs is already not lower (P/01.3 N1.3).
- `ambiguous_leader`: the write reached the leader, the outcome is **unknown**. Caller action: repeat only with the same `id`; whoever cares — read first.
- `ambiguous_medium`: a medium error before the row is published, and the implementation cannot prove that the write will not apply after a restart (item 7 of «Implementation decides»); if it can — `unavailable`. Caller action: repeat only with the same `id`.
- `ambiguous_barrier`: the durability barrier (item 3 of «Implementation decides») refused when the bytes of the write were already on the medium: the row is published (it will come back after a restart), the outcome for the caller is **unknown** — on one box too. Caller action: repeat only with the same `id`: the replay completes the barriers and answers with the first answer (`again: true`), it hands out no new version; the barrier refused again — `ambiguous` again.
- `input_timeout`: an input phase expires after a correct supported request line and before execution (N2.1). Caller action: correct the pacing or declared input envelope; no applied id or business effect is inferred.

A definite pre-effect storage refusal preserves prior business rows, issued versions and applied-id records. An unknown medium outcome stays `ambiguous`; rolling back RAM alone does not prove no effect after recovery. For `ambiguous_barrier` with a complete recoverable record already on the medium, publish the whole operation with its matching id record. Replay completes the required barriers and returns the first answer with `again`, without a new version; another barrier failure remains `ambiguous`. A batch and its applied id recover whole or are absent whole. Legitimate last-admission changes under admitted refusals/replays are checked separately from business effects.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R017

old-sha256: f6fbd7af864b3448115212f228cd039fc4b85ae4ba4002f1ef53032249e6963f

<!-- req: P/01.3-R017 -->
A member identifier is 1–128 ASCII characters: the first a letter/digit, then letters/digits/`_`/`.`/`-`. This is the input profile of this lesson. The request parsing of the service doors is chapter 1.1 N2.1 (query, the JSON of the body, the path byte for byte, HTTP, early refusal); deviations are below. The order of checks: the frame (framing, the effective `-max-body` limit — 413) → route and method (404, 405) → identity (403) → body and membership (400, 409): an extra body larger than the limit with a foreign method — 413 earlier than 404/405 (reconciliation of python and go M10/6–11, B3). `HEAD` is not a method of the service doors: `/v1/status`, `/v1/join`, `/v1/leave`, `/metrics` — 405, `/v1/write` and `/v1/rights` — 404 by their owners, chapters 1.1 and 1.2 (both implementations, agreed without a norm). The bodies of service POSTs are one JSON object; unknown fields are rejected; the read limit is the same effective `-max-body`, counting actual entity bytes, extra JSON or a detected framing violation — 400, exceeding — 413. EOF before a complete framed body keeps P/01.1 R054: no reply, no execution and no occupied id. Input timeouts follow P/01.1 R147, including a body deadline from complete headers, not from the first body byte. 400/404/405 — `BadRequestFault`, 403 — `ForbiddenFault`, 413 — `BodyTooLargeFault` of chapter 1.1. For own status/join/leave/write/metrics 503 is `UnavailableFault` before sending, `AmbiguousFault` after sending a change; at the connection limit — `UnavailableFault` with `Retry-After: 1` (chapter 1.1 N4). After an unknown join/leave the operator reads status; there is no automatic proof of success from a timeout. The floor keeps the replay memory of chapter 1.1.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R029

old-sha256: 44f5aa1885e09f5ace2bd397c149de37f906fda6c8a9e44b5677fccebc2cdbbd

<!-- req: P/01.3-R029 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125): the form is the sole source of code, kind, fields, headers and log projection. The OpenAPI fault schemas and write-check order stay their owning forms; the causes, priority and caller actions below refer to stable refusal names, without duplicating the outcome cells.

- `service_body_form`: service HTTP: unknown fields, not an object/not JSON, extra JSON, a detected framing violation or an inadmissible field. EOF/truncation follows R054 without an HTTP refusal; input-phase timeout is `input_timeout`. Caller action: fix the input; there is no side change.
- `service_body_limit`: service HTTP: a POST body larger than `-max-body`. Caller action: shrink the body; the limit is by actual bytes.
- `service_no_route`: service HTTP: no route. Caller action: fix the path.
- `service_method`: a wrong method of status/join/leave/metrics. Caller action: fix the method; for /v1/write and /v1/rights an unknown method gives 404 by their owners, chapters 1.1 and 1.2.
- `start_config`: daemon: `-bootstrap` with `-join`; `-group-size` outside its form; an address off the loopback without `-tls`; a door certificate at a voter. Caller action: fix `configstore.env`.
- `start_flags`: daemon: no `-dir`; no `-id` in a group; no `-id` and no `SERVER_NAME`; `-door` without `-voters`; a flag outside the table «Daemon flags»; an inherited socket with a name that is neither `admin` nor a role of the rights file (N1.3). Caller action: fix the unit or `configstore.env`.
- `start_format`: the data directory is not empty but there is no mark `FORMAT`; foreign `format` or `version`; `FORMAT` out of form (N1.3 `format`). Caller action: take a copy with the former implementation (`backup`) and restore it into a fresh directory.
- `box_no_raft`: the store of a box without raft (N1.3 `box`): `-group-size 3` or `5`, `-join`, `-door` (C01-BOX-DOOR-01). Caller action: take a build with raft.
- `box_last_voter`, `box_admit`: box: `leave` of the last voter; `admit`. Caller action: —.
- `join_parity`: a joining makes the group even or larger than declared. Caller action: `-force` only for a transitional evenness, not beyond the maximum.
- `join_left`: a joining of one who left, without `admit`. Caller action: `configstore admit <id>` at the leader.
- `join_role_socket`: `join`/`leave` from a role socket. Caller action: only `admin.sock` or a daemon of the group (B1).
- `backup_inside_dir`: `backup` to a file inside `-dir` of the daemon. Caller action: a file outside the data directory (B8).
- `import_repeated`: a repeated `import` after a finished one. Caller action: — (B12).
- `recover_box`: `recover` on a box without raft. Caller action: a copy and `import` (B15).
- `floor_not_integer`: `op: floor`: `floor` is not a JSON integer (`2.0e1`, `20.0`). Caller action: an integer (B5).
- `no_leader`: no leader for the effective `-leader-wait` interval. Caller action: wait; workers live by the lease.
- `leader_lost`: the leader is lost after a write is sent. Caller action: a replay with the same `id` (chapter 1.1).
- `connection_limit`: more connections than the limit. Caller action: repeat not before the deadline.
- `floor_socket`: `floor` not by admin. Caller action: —.
- `floor_not_higher_id`: `floor` not higher than the current one (a new id). Caller action: —.
- `floor_row_write`: `put`/`delete` of the floor row by an ordinary write. Caller action: only `op: floor`.
- `copy_input`: `import`/`restore`: the input is not in the form `copy` of N1.3; the base is smaller than the greatest version; a row larger than `-max-value`; an epoch or the floor is not decimal; unreadable (including a row `<sub>/epoch/<id>` or `platform/epoch_floor` — upper is not reliable; V7 item 3, the Architect's decision of 2026-10-28, row 13 of the list). Caller action: another base / fix the copy.
- `clock_early`: `recover`/`restore`: a clock earlier than `generation_at`. Caller action: `-force` removes only the clock refusal; the upper bound/isolation/monotonicity are required.
- `recovery_unsafe`: recovery: upper unknown, the old group not cut off, an overflow. Caller action: restore the preconditions; force does not help.
- `recover_isolated`: `recover` without `-isolated` (N3 step 0; guess of stage C S02, the Architect's decision of 2026-10-23). Caller action: isolate the former group and the writers, repeat with `-isolated`.
- `recover_upper`: `recover -upper N`: N is out of the flag form or below the computed upper. Caller action: check the bound; `-upper` only raises.
- `recover_peers`: `recover -peers`: an element not `id@<raft host:port>/<api host:port>`, an empty element, a repeated id or no `-id` among them (N1.3 «Daemon flags» `-peers`; guess of stage C S03). Caller action: fix the list.


- `copy_method`: unsupported method at /v1/copy. Caller action: use GET; HEAD remains bodyless.
- `copy_admin_only`: copy requested through an ordinary role socket or forwarding. Caller action: use the authorized local admin socket; no header grants it.
- `copy_snapshot_unavailable`: a consistent copy cannot be obtained before successful headers within the declared wait. Caller action: retry the read when available; no write outcome is ambiguous.

### `Platform/05-resource/spec/05-resource.norms.md` P/05-R041

old-sha256: ee70e929ed99c3ade6d0475ff1019fad55908d7ce4a2cd549bc4278b13956726

<!-- req: P/05-R041 -->

**Query parsing.** The resource door — by P/01.1 N2.1
(query, the path byte for byte, HTTP by RFC 9112, an early refusal) with deviations: a refusal of query parsing — 400 ResourceError
`{error}`; an empty or repeated parameter — 400; no path and an unsupported method — 404/405 without a body, including
`OPTIONS`, `POST /events`, `PUT /v1/objects` (the listing), `GET`/`POST`/`DELETE` on `/mirror/…`; `PUT /v1/objects/{non-blob}` —
the application 405 ResourceError (N4); `/buckets/{sub}/{unit}` — exactly two non-empty segments, `/buckets/testsub/`,
`/buckets/../objects`, `/buckets/testsub%2Fc1` — 404 without a body; the bodies of `PUT` are bytes, JSON is not parsed (reconciliation of python and go M10/6–11,
E9, E10, E17, E30, E31, E36).

The shared P/01.1 R050 drain counts raw HTTP-stream bytes and its absolute monotonic interval starts after the complete refusal has been sent; chunked discard does not wait for a terminal chunk. This parsing reference does not replace the resource's own timeout outcomes or budgets with P/01 input-phase refusals, and adds no common response deadline to resource streams.

## REMOVED

(none)

## Derived and non-requirement artifacts

All exact before/after blocks, UTF-8/codepoint/LF coordinates and complete file identities: `decisions/journal/platform/01-store/2026-11-08-z21-source-map.json`. Existing API/form classes are reused; the only new HTTP operation is the selected copy, with unsupported bodyless HEAD explicitly represented. The three new checklist identities have append-only history rows. No old runtime case, expected input, field, Source witness or version is rewritten.

Production qualification uses the 17 case groups and 11 definitions in `Platform/01-store/spec/production-acceptance.md`; budgets and actual provider remain unknown. It is not a new profile field/port/DSL or executed acceptance.

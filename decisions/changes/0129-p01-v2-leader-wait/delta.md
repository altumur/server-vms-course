# Delta 0129-p01-v2-leader-wait — effective flag source

change: 0129-p01-v2-leader-wait rev 1. Base 73096723594e9abcf35aa5ca0a9e86fa8bb1b1de; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF. Incremental follow-up after 0129-p01-v2-norms, without rewriting that frozen bundle.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R145

old-sha256: 76f289ef2d899e45f643bb643a85564817a74624981be79f36b4f9a19fde31df

<!-- req: P/01.1-R145 -->
A refusal MUST NOT quote what the caller sent, except the key: the answer does not grow with a larger error. A truncated, unreadable or missing answer and a refused connection (an overflowing `accept` queue; there is no separate 503) are on the client side: the [store client contract](../../common/contracts/store-client.md) `no_reply` (moved there without a change; SC-WIRE78-G01). The column «What the caller does» is there too, section «Outcomes and what the client does».

## N5 Acceptance

Scenarios — [`../acceptance/1/scenarios.tsv`](../acceptance/1/scenarios.tsv), run through the door of N2 of any implementation by a role with full rights on the prefix `acc/`; the format is in `README.md` next to them. The path to the door (a unix socket or a stand with the same door) is a parameter of the runner, not a norm of the lesson. The log of AI corrections is `corrections-1.tsv` (historical correction record) of the lesson.

For this acceptance the runner prepares a door with the body limit **1048576 bytes (1 MiB)** and a store with the row
ceiling **524288 bytes (512 KiB)**. These are fixed parameters of the stand, not a universal body limit of all
implementations. The runner MUST check them by behaviour on a trial instance before the scenarios: a body exactly at the
limit reaches JSON parsing, one byte more — `413` with the body limit in `limit`; a weight of `items` exactly at the ceiling
is written, one byte more — `413` with the row ceiling. How to obtain an isolated instance with these parameters, the
implementation names in its description (item 10 of «Implementation decides»). If the parameters are not provided or the
check does not agree, the run is not performed and does not count as green.
Scenario 15 checks the weight of `items` after the body is parsed, scenario 22 — a refusal before the body is parsed by N2.
The comparison of the optional `size` in the second case is set in the acceptance README.

| № | Scenario | Norm |
|---|---|---|
| 01 | an absent row reads as `null, ""` | read |
| 02 | a creation with `cas: ""` passes once | write; creation race |
| 03 | a write reads back with its content and version | write, read; memory copying — by reading, below |
| 04 | a stale `cas` is refused and not applied | write; conflict |
| 05 | a write without a condition writes over | cas absent |
| 06 | a delete with `cas` and ignored `items`, a repeated delete, a stale `cas` on a delete | delete |
| 07 | versions do not repeat after a delete and a re-creation | index |
| 08 | a listing under a prefix in byte order, with versions; the order of names in `keys` is compared by the acceptance README | list |
| 09 | a guard holds while the slot is one's own and refuses with 412 and the new version of the guard | guard |
| 10 | a guard on an absent row | guard `""` |
| 11 | the guard before CAS: both violated — 412 | order of checks |
| 12 | a replay by `id` — the first answer with `again`; other content under the same `id` — 400 | id |
| 13 | bad keys — 400 badkey | N1 key |
| 14 | a bad form of `cas` and `id` — 400 badrequest | N1 cas, id |
| 15 | a row heavier than the ceiling — 413 and not written | toolarge |
| 16 | `items` is not an object of strings — 400 badrequest | N1 items |
| 17 | not JSON and no route — 400 and 404 badrequest; `op: floor` on a role socket — 403 forbidden | N2, N2.1 |
| 18 | a refusal does not quote what was sent | N4 |
| 19 | a key longer than the limit — 400 badkey, for a guard row too | N1 key |
| 20 | guard forms: an empty key, a key that is not a path, an index that is not a version, an extra field — 400; the form before the key rules; nothing written | N1 guard, N2 |
| 21 | rights: a read, a write, a delete and a guard outside one's prefix — 403; a listing of a row prepared outside the role's rights — its name and version without the value | N2, chapter 1.2 |
| 22 | a body over 1048576 bytes — 413 toolarge with limit 1048576; nothing written | N2, N4; stand parameters — N5 |
| 23 | extra fields of a command are not read and are not in the put/delete fingerprint; guard stays closed by sc. 20 | N2, id |
| 24 | `key` of a command, `guard.key` and the read parameter `key` absent or not a string — 400 badrequest; nothing written; a query of `POST /v1/write` and a body of `GET` are not read | N2, N2.1, N4 |
| 25 | query: `+` — a space, `%2B` — a plus, `%` without digits — as written, empty pairs are skipped, `%00` — a key byte; a repeated `key` and `prefix` — 400 badrequest, and before UTF-8; `key` not UTF-8 and `?key` without a value — 400 badkey | N2.1 |
| 26 | the JSON of the body: a repeated field name at any level, `NaN`, `Infinity` and a BOM — 400 badrequest; a lone surrogate in `key` — badkey, in `items` — badrequest, in an extra field — not read | N2.1 |
| 27 | an unknown method on a known path, a known path with a wrong method, and a path equal to a route only after decoding or normalization — 404 badrequest with `Fault` | N2.1 |
| 28 | admission-time conditions: `not_after` in the past — 409 `expired`, `not_before` in the future — 409 `early`, nothing written; the order «the `id` memory → `not_after`/`not_before` → guard → CAS»; `not_after` in the fingerprint; a refusal does not take the `id`; forms — 400 | N1, N3 «Admission time», N4 |
| 29 | a key of 1025 UTF-8 bytes (Cyrillic and a four-byte character) — `400 badkey` for the target, a read (in the query — by percent-encoding: a raw byte outside 0x21–0x7E in the target is `400 badrequest` of the framing of N2.1) and a guard, nothing written (coverage audit P/01, A06; C01-KEY-1025-TARGET-01) | N1 `key` |
| 30 | the replay fingerprint: the order of the fields of `items` and `cas: null` for `put` — the same; for `delete` another `op`, `key`, `cas` (`""`, absence), `guard` (key, version, absence), `not_after`, `not_before` — 400, `items` of any type and `1.0` instead of `1` — the same (coverage audit P/01, second pass, G01) | N3 «write», «delete» |
| 31 | a delete of an absent row with `cas: ""` spends a version, the row stays absent, a creation with `cas: ""` after it passes; the `id` memory before the guard and CAS; the refusals `early`, `guard`, `conflict` do not take the `id` (G02) | N3 «delete», «write» |
| 32 | the order of command checks with combined violations: `op` → the `floor` socket → the form and rules of `key` → `items` → `cas` → `guard` → `id` → `not_after` → weight → rights; `id: null` and `not_after: 1e400` — 400; a lone surrogate in `guard.key` — `badkey`, in a value of `items` — `badrequest`; nothing written (G03) | N1, N2.1 |
| 33 | a batch all or nothing: one version for all rows; a stale `cas` of the second row — 409 `conflict` with `key`, no row written, versions unchanged (ADR-0094 B9) | N3 «write batch» |
| 34 | a batch carries a creation (`cas ""`), an edit and a removal; a delete of an absent row is done, `items` of a delete is not read; a stale `cas` of a removed row — `conflict` with `""` | N3 «write batch» |
| 35 | batch guards: they hold and are not written; a refusal 412 with `key` and the version now, nothing written; guards before `cas`; the first violation — in list order | N3 «write batch», order |
| 36 | a batch replay by `id`: the first answer with `again`; the order of `guards` and of the fields of `items`, `cas: null`, `items` of a delete do not change the fingerprint; the order of `writes`, `items`, `guards`, a deadline change it — 400; the memory before guards and `cas`; a refusal does not take the `id`; the `id` is shared with a write | N3 «write batch» |
| 37 | batch deadlines: `expired`, `early` — nothing written, before guards and `cas`; forms — 400 | N1, N3 «write batch» |
| 38 | the batch form: `writes` absent, empty, not an array; an element not in its closed form; the `op` of an element; keys — `badrequest` and `badkey`; `guards` not an array, `null`; repeated keys; a guard on a written key; the limits `BATCH_WRITES` and `BATCH_GUARDS` — exactly at the limit 200, one more 400; the order of checks; extra top-level fields are not read | N1 `batch`, N2, N2.1 |
| 39 | batch weight: each row against the ceiling, a sum larger than the ceiling with a body smaller than the limit — 200; a row heavier than the ceiling — 413 with its `key`, nothing written | N1 `batch`, N4 |
| 40 | batch rights: a row or a guard outside one's prefix — 403 for the whole batch, nothing written; before deadlines; the `id` is not taken | N3 «write batch»; chapter 1.2 |

An implementation whose store opens in the process without a door (files, memory) SHOULD (not MUST: acceptance norms the behaviour of the door, the internal API is the implementation's choice, item «Implementation decides») run the same scenarios
also through its API, mapping refusals to the codes of N4: so the order «guard before CAS» and the forms are checked in all its stores,
not only behind the door (the mutation probe of 2026-10-14: behind the door 39 % of mutants survived, in stores without a door — all).

Unparseable HTTP (N2.1) is not expressible in TSV: the probe of the acceptance README checks it on raw bytes.

The admission time in sc. 28 is only its edge: `not_after` = 1 (1970) has already passed, `not_after`/`not_before` = 4102444800
(2100) has not yet come at any clock of the stand; the equality boundary, non-decrease along the log at a leader change, a restart and
a clock move backwards, a replay after `not_after` before the first copy is applied, and `admission_ahead` are checked by reading:
the door does not move the leader's clock and does not hold a record between admission and application.

A power cut in the middle of a batch is checked by reading item 3 of «Implementation decides» and the code: the stand does not cut power; a restart after
a batch and a replay — sc. 30 of chapter 1.3, one log record in a group and forwarding by a door without a vote — sc. 31 of chapter 1.3. A body refusal of a batch over
the limit is the common body refusal before JSON parsing (sc. 22). The row-count limit of the role `console` — sc. 16 of chapter 1.2.

Checked by reading (doors do not reproduce them deterministically): `ambiguous` at the leader's death — the branch of P/01.3 N1.3 `leader_wait` (`unavailable` without a quorum — sc. 17 of chapter 1.3, the group stand); `unavailable` when the wait time of the local lock expires — the refusal branch before the write; the replay memory by time; linearizability of the read.

The independence of the memory of `items` on input and output is checked by reading the implementation of the operations: the dictionary
passed by the caller and the dictionary returned by a read do not share mutable memory with the store. The reason: HTTP serialization
hides shared memory, and sc. 03 only writes and reads a value. A run of the same two steps through the in-process API
without a later change of the passed or returned dictionary does not check copying either.

## Implementation decides

Each implementation names in its description:
1. **the indivisibility mechanism** on one box (a file lock, a mutex) and in a group (a consensus log; a batch is one log record) and the lock wait time — what the caller gets when it expires (as `unavailable`);
2. **how a version is handed out**: a counter in a file, a log index plus the group base — as long as it does not repeat; which number it starts from;
3. **the disk layout** and **the durability barriers**. The order of one write: bytes to the medium, a barrier, publication and the answer; a delete survives a power loss. If the barrier refused when the bytes are already on the medium, the row is published and the answer is `ambiguous` (N4); a replay with the same `id` repeats the barrier. A mode without barriers is admissible only by a flag of the «Stand» command of acceptance; there is no environment variable or operational flag that turns barriers off (P/01.3 N1.3 `durability`; the store pilot, A10). **A batch:** how it becomes visible as a whole and after a power loss stays whole or does not appear at all (N3 «write batch», «Atomicity») — an intent log with a barrier before the rows are published, or another way; a lock is not enough: a lock does not survive power, and the rows of different files reach the medium separately;
4. **the key length limit** of a file-based implementation, if it is smaller than KEY_BYTES;
5. **how a store that can read its row only partially** (a damaged file) reports it: the answer form is a norm (N2 `Row.unreadable`, P/01.1-17); here — how the implementation detects the damage and what it logs, and how it stores the version of the row so that damage to the body does not lose it (the loss of the version — 503, N2; C01-ROW-INDEX-LOST-01, the Architect's decision of 2026-10-29);
6. **the lifetime and volume of the replay memory** beyond the minimum of N3;
7. **how the door tells «not added to the log» from «unknown»**; the leader wait time before `unavailable` follows the effective `-leader-wait` interval from the loss of the leader, by P/01.3 N1.3; its default is owned only by [daemon-flags.tsv](../forms/daemon-flags.tsv).
8. **the read limit of the HTTP body** of a store in the process without a daemon; for the daemon it is set by the flag `-max-body` (the source of defaults is [daemon-flags.tsv](../forms/daemon-flags.tsv)) separately from the row ceiling `-max-value`; the value and meaning of `limit` — by N2, the acceptance parameters — by N5 (log of cammeta-python, lesson 11 № 24).
9. **the request parsing limits**: the length of the HTTP request line (in bytes, without the final CRLF); exceeding it is `400 badrequest` by N2.1; the length of a chunk-size line of chunked with extensions (without CRLF) — exceeding it is a framing error: `400 badrequest` and the connection closed (C01-CHUNK-LINE-LIMIT-01); the drain volume and time after an early refusal (N2.1). The header limit (`HEADER_BYTES`) and the JSON depth (`JSON_DEPTH`) are norms of N2.1, not a choice (reconciliation of python and go 2026-10-18);
10. **how the runner obtains an isolated instance** with the acceptance parameters of N5: the start command with substitutions by the section «Stand» of the acceptance README of this lesson — it is common to the acceptance of M10; the lesson does not norm an internal API;
11. **how a listing takes its list** (a copy under the lock, a version snapshot); the guarantee of the «Races» of N3 is kept.

## Readiness checklist

An implementation conforms to the lesson when every norm holds; the norm id `P/01.1-MM` is what decision deltas, findings and window records refer to (ADR-0080 addendum 6):

- [ ] **P/01.1-01** an absent row — `null, ""`, not an error — sc. 01
- [ ] **P/01.1-02** `cas: ""` creates once — sc. 02
- [ ] **P/01.1-03** a version is handed out to a write and read back with its content — sc. 03; `items` do not share memory on input and output — checked by reading: HTTP hides shared memory, sc. 03 does not change the passed or returned dictionary (N5)
- [ ] **P/01.1-04** a stale `cas` — `409 conflict` with the version now, nothing written — sc. 04, 06
- [ ] **P/01.1-05** a write without `cas` — over — sc. 05
- [ ] **P/01.1-06** a delete is idempotent and spends a version; a sent `items` is not read — sc. 06, 07; a delete of an absent row with `cas: ""` and a creation with `cas: ""` after it — sc. 31
- [ ] **P/01.1-07** a handed-out version never repeats — sc. 07; after a daemon restart — sc. 19 of chapter 1.3; after elections and a group restart — sc. 17, after `import` with `-index-base` — sc. 18 of chapter 1.3 (the group stand; item 2 of «Implementation decides», P/01.3 N1.3); rows carried by `import`/`restore` carry the copy's versions — not handed out, a coincidence with a version handed out before the transfer is not forbidden by the norm (C01-VERSION-ISSUED-01)
- [ ] **P/01.1-08** a listing: the prefix by bytes, the order by bytes, versions — sc. 08; for `keys` the order of names in the answer is checked too (acceptance README)
- [ ] **P/01.1-09** a guard: `412 guard` with `key` and `index` now, nothing written; on an absent row — `""`; a version mismatch requires a re-read of the condition and by itself does not mean a loss of the owner — sc. 09, 10; what the caller does after the re-read is checked by reading the caller's procedure ([P/03.2-05](../../03-worker/spec/03.2-worker.norms.md)): the decision is not the door's, TSV does not see it
- [ ] **P/01.1-10** the guard before CAS — sc. 11
- [ ] **P/01.1-11** a replay by `id`: the first answer, `again: true`; other content — `400`; the memory holds more than one write (id A, id B, replay A — `again`) — sc. 12; a change of ignored command fields does not change the fingerprint — sc. 23; the `delete` fingerprint (`op`, `key`, `cas`, `guard`, `not_after`, `not_before`), the order of the fields of `items` and `cas: null` for `put` — sc. 30; the memory lifetime: at least `ID_REPLAY_MIN_AGE` — sc. 21 of chapter 1.3 (`@sleep 121`: the format of chapter 1.1 carries no directives); the right to forget after the age and record-count conditions `ID_REPLAY_MIN_AGE` and `ID_REPLAY_MIN_RECORDS` (N3) — by reading the implementation's description
- [ ] **P/01.1-12** keys, forms, the ceiling, routes — `400`/`404`/`413` by N4 — sc. 13–17; weight before rights (N2.1 order) — sc. 21 step 7; an absent or non-string key — sc. 24; extra command fields are accepted without reading — sc. 23
- [ ] **P/01.1-13** a refusal does not quote what was sent — sc. 18 (`409` by `cas`, `412` by `guard.index`)
- [ ] **P/01.1-14** `unavailable` ≠ `ambiguous` ≠ `conflict`; a dropped answer reads as the first two — `unavailable` without a quorum — sc. 17 of chapter 1.3 (the group stand), `ambiguous` and a drop — by reading the branches of P/01.3 N1.3 `leader_wait`; a local lock timeout — `unavailable` before the write, checked by reading the refusal branch (N4)
- [ ] **P/01.1-15** a read is linearizable — checked by reading: the mechanism is named in the implementation's description
- [ ] **P/01.1-16** guard forms and the key limit — `400` by N1; the body limit is named in the description, exceeding it — `413` with the body limit in `limit` by N2; acceptance with the parameters of N5 — sc. 19, 20, 22, 29 (1025 UTF-8 bytes); keys of 200–1024 bytes — tooling beyond TSV (the common acceptance README, R29-01; a file-based implementation MAY refuse earlier); the description of the limit — by reading
- [ ] **P/01.1-17** a damaged row reads as `{items: null, index, unreadable: true}`, a write with `cas` on this version replaces it; the loss of the version — 503 for a read and a touched listing (C01-ROW-INDEX-LOST-01) — sc. 20 of chapter 1.3; a guard on the version of a damaged row and its delete by `cas` — sc. 22 of chapter 1.3 (`@spoil row`, `@spoil row-index`: the spoil command of the profile; without it — not_executed)
- [ ] **P/01.1-18** a client SHOULD put `id` on every write — checked by reading the clients of the platform ([P/06.1](../../06-console/spec/06.1-console.norms.md), [P/04](../../04-controller/spec/04-controller.norms.md) and P/03; the worker — [P/03.4-07](../../03-worker/spec/03.4-worker.norms.md))
- [ ] **P/01.1-19** a listing prefix SHOULD end with `/` — checked by reading the calling lessons (the subject — the `/v1/list` prefixes in N3 of the other lessons of the module): this is a rule of the caller, the door accepts any prefix
- [ ] **P/01.1-20** an implementation without a door SHOULD run the scenarios also through its API, mapping refusals to the codes of N4 — checked by reading (its description)
- [ ] **P/01.1-21** a file-based implementation MAY refuse a key shorter than KEY_BYTES UTF-8 bytes by the file name limit; its limit is named in its description — checked by reading the implementation's description
- [ ] **P/01.1-22** a store on a box MAY be opened in the process without a door; the semantics are the same, acceptance — through the door and through its API (P/01.1-20) — checked by reading the implementation's description
- [ ] **P/01.1-23** request parsing of N2.1: query, the JSON of the body, the method and the order of checks give one code and kind in all implementations — sc. 25–27; `guard` before `id` — sc. 20 step 9; the guard form before the key — sc. 20 steps 10–11; `floor` on a role socket — sc. 17 step 5; `%00` — sc. 25 step 13; the order of command checks with combined violations, `id: null`, `1e400`, a surrogate in `guard.key` and in a value of `items` — sc. 32; unparseable HTTP, CRLF, `HEADER_BYTES`, `JSON_DEPTH`, the request target, the body framing and truncation, `Host`, `HEAD` — README probes; the request line limit of item 9 — a probe of the acceptance README
- [ ] **P/01.1-24** the order of output arrays of N0 (scope — lessons 8–10): checked at the lessons of the scope — by their scenarios and vectors (before the move — the acceptance of M11) and by reading the output forms; chapter 1.1 has no outputs of the scope of its own (review of stage A 8–10, № 19 / decision 4)
- [ ] **P/01.1-25** the write conditions `not_after`, `not_before` (N1): 409 `expired`, `early`, nothing written, the `id` not taken; the order «the `id` memory → time conditions → guard → CAS»; both conditions in the replay fingerprint — sc. 28; the `id` memory before the guard and CAS, the refusals `early`, `guard`, `conflict` do not take the `id` — sc. 31; the equality boundary — by reading (N5)
- [ ] **P/01.1-26** admission time (N3): assigned by the leader on admission to the log, stored in the log record, the conditions are checked on application by it; it does not decrease along the log, survives a leader change and a restart, a store without a log stores it durably; in the state and the snapshot — checked by reading: the door does not move the leader's clock (N5)
- [ ] **P/01.1-27** the premise «the clocks of the cluster's writers differ by ≤ `CLOCK_SKEW`» (N0 «Cluster clocks») — checked by reading: a premise of deployment, the implementation does not check it
- [ ] **P/01.1-28** the batch `op: batch` (ADR-0094 B9): the form of N1, closed elements, the order of checks of N2.1, the limits `BATCH_WRITES`, `BATCH_GUARDS` — sc. 38; the weight of each row — sc. 39; a creation, an edit, a removal in one batch — sc. 34
- [ ] **P/01.1-29** a batch all or nothing, one version for all rows: a `cas` refusal — `409 conflict {key, index}`, a guard refusal — `412 guard {key, index}`, nothing written, the order «guards → `cas`» and list order — sc. 33, 35; deadlines before conditions — sc. 37; rights per row, 403 for the whole batch — sc. 40, sc. 16 of chapter 1.2
- [ ] **P/01.1-30** a batch replay by `id`: the fingerprint, the memory shared with a write, a refusal does not take the `id` — sc. 36; after a restart — sc. 30 of chapter 1.3
- [ ] **P/01.1-31** batch atomicity: visible whole or not visible, after a power loss at any point and at a barrier refusal — all or no row, the `id` memory with it, `ambiguous` for the whole batch — by reading: the stand does not cut power, the way is named in item 3 of «Implementation decides» (N5); one log record and forwarding as a whole — sc. 31 of chapter 1.3

## REMOVED

(none)

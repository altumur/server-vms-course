# Delta 0129-p01-core-clarify — ADR-0129 p5 and addendum (2)

change: 0129-p01-core-clarify rev 1. Base 62751995ba14646dac48d482d5dc394ecd9a87c2; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R019

old-sha256: 8a2b1983b2d50fe0bedf558a0a208a1de3141be8ff10ef1c585f27ff935a70c9

<!-- req: P/01.1-R019 -->
```yaml
# A store row. The store is a map key → row; it has no other entities.
row:
  key:                       # the name of the row
    type: string
    rules:
      - not empty
      - does not start with "/"
      - no segment (between "/") equals ".."
      - at most 1024 bytes                     # at the door; a file-based implementation MAY refuse earlier (below)
    note: one spelling — one place; a key that breaks a rule gets badkey, it is not repaired
    compare: by UTF-8 bytes, without normalization — a//b, a/./b, a/b/ and the NFC and NFD forms of one text are different keys
  items:                     # the content
    type: map                # string → string; the order of fields has no meaning
    rules:
      - every key and every value is a string
      - weight (sum of byte lengths of every key and every value) at most the store's ceiling
    ceiling: 524288          # 512 KiB; the same ceiling is in the summary of P/06.1 N1.4 (row «store row»); P/06.1 declares no other ceiling
  index:                     # the version
    type: string             # opaque: compared only for equality
    rules:
      - handed out by the store on every write; never the same twice within one store
      - 'one version per operation: a batch (N3 «write batch») hands out one version, and every row it writes gets it; "never the same twice" counts operations, not rows'
      - '"never the same twice" is about versions handed out: a version a write or a delete hands out is not handed out again; a row carried in by import or restore keeps the copy''s version — not handed out by this store, it may equal one handed out before the transfer (P/01.3 N1.3 import; C01-VERSION-ISSUED-01)'
      - '"" names an absent row and is no version'
    wire: an unsigned decimal number without leading zeros, up to 20 digits, as a JSON string
    note: "the wire form is a norm of the door (so the store hands out versions); opacity is a norm of the caller (it does not parse a version, it compares only for equality); a store with another version form would fit with another N2, not with another client"

# The write condition.
cas:
  absent (no field or null): unconditional — written over whatever is there
  "":                          only while the row does not exist (creation; the first one wins)
  <version>:                   only while the version of the row is exactly this one

# A condition on another row (ADR-0074 addendum 1).
guard:
  key:   string              # the guard row: usually the writer's slot; the same key rules
  index: string              # its version, "" — the guard is absent
  note: checked in the same operation as cas; the rights to the guard row are the caller's read rights: allowed(role, read, guard.key) (P/01.2 N1.3 guard, N3 «check»)

# Admission-time conditions (ADR-0091 item 1, rev. 11) — for put and delete; admission time — N3 «Admission time».
not_after:
  type: number               # Unix seconds; a JSON number, compared by value
  rules: [finite, at least 0]  # finite — finite in binary64, like codec time (codec.tsv time; MAY-UNTIL-D8-01): 1e400 — badrequest;
                               # value, comparison and the replay fingerprint — by the binary64 value (C01-TIME-NUMBER-EXACT-01)
  meaning: the log record applies only if its admission time is not later than not_after; otherwise expired (N4)
  null: out of form — badrequest (as for id); a string, a bool, a negative number — also badrequest
not_before:
  type: number               # Unix seconds; a JSON number, compared by value
  rules: [finite, at least 0]
  meaning: the log record applies only if its admission time is strictly later than not_before; otherwise early (N4)
  null: out of form — badrequest; a string, a bool, a negative number — also badrequest
  note: "both conditions MAY stand in one record; the writer writes the number in the notation of «Time in a row» N0"

# The write identifier.
id:
  type: string
  rules: [1 to 64 lowercase hex digits]
  null: out of form — badrequest; unlike cas, null is not equal to the absence of the field
  note: "optional; a client SHOULD put it on every write (32 hex digits of randomness): after an «unknown» answer only a replay with the same id is safe (N4; the worker — P/03.4-07: every write of it that carries a value carries an id, after ambiguous — a replay with the same id)"

# A batch (ADR-0094 B9, addendum (12) item 1): a separate operation; the single write and its guard do not change.
batch:
  op:      batch
  writes:                    # the writes; order matters; a key occurs once
    - op:    put | delete
      key:   string          # the same key rules
      items: map             # required for put, form and ceiling — row.items per row; not read for delete
      cas:   as cas of a write  # the condition of this row; no field or null — unconditional
  guards:                    # optional; no field — as []; order matters; a key occurs once, and not in writes (the condition of a written row is its cas)
    - {key, index}           # the form of guard
  id:      as id of a write  # one per batch
  not_after, not_before:     # as for a write, one condition per batch
  rules:
    - writes is not empty and has at most BATCH_WRITES elements; guards has at most BATCH_GUARDS (except the roles console and domain, below)
    - an element of writes is closed — exactly the fields op, key, items, cas; an element of guards — exactly the fields key, index
BATCH_WRITES: forms/runtime-constants.tsv             # the limit of batch writes; exactly at the limit — passes, one more — badrequest
BATCH_GUARDS: forms/runtime-constants.tsv             # the limit of guards; FOLDERS_DEPTH_MAX + 1 ≤ BATCH_GUARDS (P/06.8 N1.3)
```

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R048

old-sha256: 2ae0bdd1f74bed0f184bc3f080927710062a5a0fcb2da733f827a6691ad2953d

<!-- req: P/01.1-R048 -->
- **The body of `POST /v1/write`** is JSON by [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259): a repeated field name
  in any object of the body (§4), `NaN`, `Infinity`, a BOM and non-UTF-8 bytes (§8.1) — `400 badrequest`. A lone surrogate
  (`\ud800`) in `key` or `guard.key`, or for a batch in the `key` of an element of `writes` or `guards` — `400 badkey`: the
  string cannot be encoded in UTF-8 nor measured by N1; in a name or value of `items` — `400 badrequest`; in extra fields
  it is not read. Numbers and strings of extra fields are not read at any length. The nesting depth is one number for all
  implementations: `JSON_DEPTH` ([runtime-constants.tsv](../forms/runtime-constants.tsv)) nested objects and arrays from the root, the root object counts 1, in any field,
  extra ones too; 129 — `400 badrequest`.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R053

old-sha256: d0e064afd61bfedcd25e68f8723c0c02ceae0c7c80f21ce974dfa459a08fadfb

<!-- req: P/01.1-R053 -->
- **Request line and headers.** A line ends only with CRLF: a lone LF or CR — `400 badrequest`. Empty lines before the
  request line — `400 badrequest` (they are not skipped). The request target is only the bytes 0x21–0x7E without `#`; any
  other byte (a raw `\x00` included) — `400 badrequest`; `%00` is three admissible bytes: the path is compared byte for
  byte, and the query key after percent-decoding contains U+0000 and is admissible by N1. The header limit is
  `HEADER_BYTES` ([runtime-constants.tsv](../forms/runtime-constants.tsv)): the sum of the lengths of the field lines without their CRLF and without the final empty line;
  exactly at the limit — parsed, one byte more — `400 badrequest`; there is no separate limit on the number of lines.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R070

old-sha256: 4a8942fe414e73a570e9ab5caf0ec166975ede22189f5ae4136e4481cb339dda

<!-- req: P/01.1-R070 -->
The leader assigns it when admitting the record to the log and stores it in the log record itself. When a record is
**applied**, the conditions `not_after` and `not_before` MUST be checked against this stored time, not against the clock of
the applying server: the outcome is one on all servers of the group and does not depend on when the record reached
application. The admission time MUST NOT decrease along the log: a new leader and a restarted daemon continue from the
admission time of the last record of their log (including one that came by snapshot). A store without a log — a box
(`box` P/01.3 N1.3) and a store in the process — assigns the time by the same rule from its last admission time and MUST
store it as durably as rows: under the same lock and the same durability barrier as the write (item 3 of «Implementation
decides»). The admission time is part of the store state and its snapshot (P/01.3 N1.3 `admission`); the copy `copy` of
P/01.3 does not carry it: a group after `import` or `restore` starts from the clock of its leader. A write answer does not
return it. A leader clock that ran ahead raises the admission time, and writes with `not_after` get `expired` until the
clock catches up; this is visible by the flag `admission_ahead` (P/01.3 N2 `/v1/status`).
Where the clock provides fractional Unix seconds, assignment, storage and restoration of the admission time, the `max` and the
comparisons with `not_after` and `not_before` MUST retain that fractional part. The clock, the previous admission time and the
bounds MUST NOT be rounded to integer seconds for these operations. This does not prescribe the accuracy or resolution of the
physical clock source. For an admission time A, `not_after` admits A <= bound and refuses A > bound; `not_before` admits
A > bound and refuses A <= bound, also on fractional boundaries (N1).

An already-admitted replay retains its newly assigned admission time by this rule, even when id memory supplies the first answer without a business-row write, new issued version or changed applied-id entry. It must survive an ordinary close/reopen as the last admission metadata. A subsequent rollback of the physical clock cannot undo it.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R078

old-sha256: 362e6d263ae5ff6d6f957c316177b59a9c00740bd1fbfe7b4993dc5f53ff9338

<!-- req: P/01.1-R078 -->
7. If id is given and has already been applied:
   1. If that record was different (op, key, items, cas, guard, not_after, not_before), return `badrequest`.
   2. Otherwise return its answer with again=true; the rows, issued versions and applied-id entry do not change. The last admission time still advances by N3 «Admission time» (R070), with its durability, even when the answer comes from this memory.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R088

old-sha256: b9fa2f82677b4055d4d037e8c57bb946693bc4211f665d5cd5bfda3e5c55afc2

<!-- req: P/01.1-R088 -->
The order of checks inside the operation is normative: the `id` memory, then `not_after` and `not_before`, then the guard,
then CAS; with several violations the answer is by the first one (ADR-0091 item 1). A replay of an applied write gets its
answer also after `not_after` — including a replay that arrived while the first copy was not yet applied: the first one
is applied first, the replay answers with its answer. A refusal `expired` and `early`, like `conflict` and `guard`, makes no write and does not take the `id`, but the admission time of the refused
record remains the last admission time (in a group — a log record; a box and a store in the process store it as durably
as rows; C01-ADMITTED-ON-REFUSAL-01). Only `expired` remains the same refusal for the same deadline and nondecreasing admission time. `early`, `conflict` and `guard` do not occupy the `id`: the same command and `id` are checked again against the current admission time and state and may succeed. The caller still re-reads its condition and decides anew before another attempt (N4). The guard before CAS. A guard refusal means a mismatch of the observed version and the absence of this write. The caller re-reads the condition and decides anew whether it has the right to repeat; a version mismatch by itself does not prove a loss of ownership. A CAS refusal also requires a re-read before a new attempt. A guard on an absent row (`index: ""`) holds while the row does not exist.

The absence of business effects is distinct from admission metadata: an already admitted put or delete that returns any of these four refusals still updates the last admission time to this record's `admitted` (which may equal the previous time). It does not roll that metadata back with the refused row/id/version effects. The persistence rule is the same as for admission in the successful case (N3 Admission time). This statement concerns an already admitted record, not a request rejected before admission.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R090

old-sha256: fdc224295844125e6a4e20d5ca923d59fdcacecea00f52f382d6525b33e65004

<!-- req: P/01.1-R090 -->
The «different record» of a replay is compared by the values of the fingerprint fields, not by the bytes of the body:
`cas: null` equals the absence of `cas`, the order of the fields of `items` and the way JSON strings are escaped have no
meaning; both `not_after` and `not_before` — by their finite binary64 numeric values as in N1 (`10` and `10.0` are one), absence equals no number. Distinct JSON number spellings that round to the same binary64 value compare equally and have the same bound fingerprint; exact decimal-rational comparison and raw spelling are not the bound domain. This numeric rule does not apply to versions: they remain exact strings, and `"0"` is not `""`.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R122

old-sha256: 0e1daceef58cc4c32000329068dd49e29f136d95050917b2dc69e8364192e6cf

<!-- req: P/01.1-R122 -->
6. If id is given and has already been applied:
   1. If that record was different (fingerprint below), return `badrequest`.
   2. Otherwise return its answer with again=true; the rows, issued versions and applied-id entry do not change. The last admission time still advances by N3 «Admission time» (R070), with its durability, even when the answer comes from this memory.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R132

old-sha256: 984d0f0b7658f9faa176fe47f629a4cf472180bbe1367dbc53cd900e235d5169

<!-- req: P/01.1-R132 -->
The refusals `expired`, `early`, `guard`, `conflict` make no write, do not take the `id` and do not spend versions; the
admission time of a refused batch remains the last admission time, as for a write. A refusal names the row but not the
value: `412 guard {key, index}`, `409 conflict {key, index}` — the version of this row now.

The refused batch still updates the last admission time to this record's `admitted` (which may equal the previous time), with the same durability as admission of a successful batch. Zero business-row changes, no occupied `id` and no issued version do not mean rolling back this admission metadata. This applies to each of the four named refusals after admission, not to a request rejected before admission.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R143

old-sha256: 1de18dec9bba8c05f4a8e80ad5103a6c848b436603a139a7712b61f338e8c0c8

<!-- req: P/01.1-R143 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125): the form is the sole source of code, kind, fields, headers and log projection. The OpenAPI fault schemas and write-check order stay their owning forms; the causes, priority and caller actions below refer to stable refusal names, without duplicating the outcome cells.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R144

old-sha256: 576113e042936ff617d0e2da9d41a92a29165a2f68a10e88dbf9210d82ae0e69

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

### `Platform/01-store/spec/01.2-store.norms.md` P/01.2-R029

old-sha256: 11a56832004ac5521c4e87cdeb18169dd42416e93e149cbffea755fbfee8ce2f

<!-- req: P/01.2-R029 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125): the form is the sole source of code, kind, fields, headers and log projection. The OpenAPI fault schemas and write-check order stay their owning forms; the causes, priority and caller actions below refer to stable refusal names, without duplicating the outcome cells.

- `list_form`: `/v1/list` out of the form of chapter 1.1 N2.1 (a repeated `prefix`). Caller action: fix the request.
- `rights_no_route`, `rights_store_unavailable`: no route; the store is unavailable (`/v1/list`, `/v1/rights`). Caller action: —.
- `read_forbidden`: a read without the right. Caller action: a deployment error or a foreign process.
- `write_forbidden`: a write/delete without the right. Caller action: the same.
- `guard_read_forbidden`: a guard on a row without the read right. Caller action: the same.
- `never`: a delete of an epoch row; a delete under `domain/` by a role that is not a domain role; a write and a delete of `platform/epoch_floor`. Caller action: never.
- `role_header`: a role header on a role socket. Caller action: a client error.
- `forwarding_untrusted`: a forwarding not from a daemon of the group (a voting one or the door without a vote); a forwarded `admin` with a loaded rights file. Caller action: —.
- `rights_not_admin`: `/v1/rights`: the identity is not admin after the check of admissibility of the forwarding. Caller action: —.
- `rights_not_loaded`: `/v1/rights`: the file is not loaded. Caller action: set up the file and restart.
- `rights_file_form`: the rights file is out of form; it names `admin`/`configstore`/`configstore-door`; a role not by the grammar. Caller action: regenerate.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R006

old-sha256: d879e7bbaa0bf3b691ab6f1a05ec4bb28e041a40da63931f47a9370e22446954

<!-- req: P/01.3-R006 -->
```yaml
daemon:
  flags:   a closed set — forms/daemon-flags.tsv; -socket is removed: the socket path is one — -sockets (the store pilot, A3)
  refuse_start: -bootstrap with -join; group-size not from {1,3,5}; an address off the loopback without -tls; a door certificate at a voter; -door without -voters; no -id and no SERVER_NAME;
           no -dir; no -id with -join, -door or -group-size 3 | 5; with -door, -id is not equal to the server of its certificate (CN/SAN,
           C01-DOOR-ID-CN-01); a directory with an unfinished import/restore attempt (after the floor, before the phase «Done» of N3;
           C01-UNFINISHED-IMPORT-WRITERS-01); the FORMAT mark is not its own (format below) — all start refusals: code 2
           (RestartPreventExitStatus=2 — a configuration error is not restarted; review of stage B 1–2, item 9)
  tuning:  lan — heartbeat 500 ms, elections 500 ms, leader lease 250 ms; the operator's word in configstore.env
group:
  sizes:   1 | 3 | 5 — the same on all servers
  join:    the daemon starts first, then joins: ask /v1/status, start with the partners, POST /v1/join;
           an even one — 409 refused without -force (with -force — a transitional state of reassembly); more than declared — 409 refused even with -force; member.json remembers the partners and how — a restart is not a joining
  leave:   leaving; one who left is not accepted back (403 / raft) until admit <id> on admin.sock of the leader
  identity: daemons — mTLS by certificates of the CA (CN configstore.<server>, SAN DNS <server>, URI urn:w2c:role:configstore);
           a certificate carries one role; -api and -raft on loopback may run without -tls (the local box); outside loopback they require -tls; -join always requires -tls (group traffic); an additional transport secret — the implementation decides
leader_wait: 5 s from the loss of the leader (not per request) → 503 unavailable; a write gone to the leader without an answer → ambiguous (chapter 1.1)
sockets:   flat: <-sockets>/admin.sock and <-sockets>/<role>.sock, no subdirectories (the store pilot, A3);
           inherited ones (the sd_listen_fds protocol: LISTEN_FDS, LISTEN_FDNAMES) the daemon takes by FileDescriptorName=admin |
           <role>: the mode and the group were set by the unit (P/02.4 N1.1); a name that is neither admin nor a role of the rights file — start refusal, code 2, the log
           names the name; a socket that was not passed, the daemon creates itself in -sockets: admin.sock 0600, <role>.sock 0660
           with the group of the process (the store pilot, A10);
           admin.sock 0600 (root; everything except never of chapter 1.2; not forwarded); <role>.sock 0660 the group of the role;
           a role header on a role socket → 403; forwarding to the leader is trusted only from a daemon of the group — a voter or a door without a vote — by the role in SAN (chapter 1.2 N3)
door:      -door -id -voters a@h:p,…: without a vote; the same sockets and rights; to the leader or any voter (attempt 2 s, margin 1 s);
           the group membership — every 5 s; the row platform/configstore-doors/<id> {seen_at} every 30 s (not under platform/doors/ — there are the doors of servers, P/05 N1.4);
           it is written by the door itself: by a request to the leader over mTLS with its own role configstore-door (forwarding of roles of chapter 1.2 N3), by the command
           put of its own row without cas and guard, the only element seen_at; any other write from the role configstore-door, a batch op: batch included, — 403;
           a foreign batch the door forwards whole, in one request (chapter 1.1 N3 «write batch»; ADR-0094 B9);
           «own» — <id> = the server from the verified certificate of the peer (CN configstore-door.<server> / SAN DNS); a claimed
           identity of the door (<id> of the key, the door name in the forwarding header) not equal to it — 403, nothing is written; Cmd.id
           of the replay memory (P/01.1) is not an identity, it is not compared with the server (C01-DOOR-ID-CN-01);
           the door does not touch admin.sock and does not forward its requests (log of cammeta-go, lesson 11 № 3); it is counted in
           configstore_doors while its row reads in its own form and seen_at in it is not older than 3 × 30 s by the clock of the voter
           that gives the series (C01-DOORS-COUNT-FRESH-01, the Architect's decision of 2026-10-30; where and by whose clock — metrics below); a door row that does not read in its own form is not counted as a visible door — the reason goes to the log
           of the leader without the value (V7 item 3, the Architect's decision of 2026-10-28, P1; row 5 of the list); all voters unreachable → 503 unavailable; it does not do join/leave
format:    in -dir — the file FORMAT, a JSON object {format, version, impl} (string, integer, string): format and version — the on-disk format
           of this implementation, impl — the name of the implementation, only for the log; the daemon writes it first into an empty directory
           (tmp + rename), before any other write; start: the directory is empty → write FORMAT; format and version are those that
           this build reads → start; otherwise (the directory is not empty but there is no FORMAT; foreign format or version; FORMAT out of
           form) → start refusal, code 2, the log names the directory and the mark found; nothing is written to or
           removed from the directory. A change of implementation — only by a copy (copy below) into a fresh directory (the store pilot, A1)
copy:      the backup copy and the import/restore input — one format for all implementations, JSON Lines: UTF-8, a line is one
           JSON object, the line end is LF; the first line is the header
           {"format": "w2c-configstore-copy", "version": 1, "index": <version>}: index — the version of the store (Version of chapter 1.1)
           at which the copy is taken, not smaller than the index of any row of the copy; then — a line per key: {key, items, index}
           (items and index — as Row of chapter 1.1) or {key, items: null, index, unreadable: true} — a damaged row as
           read (Row of chapter 1.1); the writer puts the keys in ascending order of UTF-8 bytes, the reader does not require an order;
           platform/epoch_floor is included as an ordinary input row for upper and the generation_at clock check, but is not transferred; the id replay memory (chapter 1.1 N3) is not part of the copy; the copy knows no manifests —
           rows of any families, a family check at import is not needed (import below);
           another format or version, an extra or a missing field, a line not JSON or not by Row, a repeated key, an index
           of a row higher than the index of the header — a refusal of the whole input before the first write (N4); an unreadable row in the input — also
           a refusal (N4). A copy of one implementation is restored by another (the store pilot, A2)
batch:     a batch (chapter 1.1 N3 «write batch») — one raft log record: applied on all servers whole, it has one version and
           one admission time; on a box (`box` below) and in the store `file://` — the atomicity property of the same chapter, the way — chapter 1.1
           «Implementation decides» item 3 (ADR-0094 addendum (12) item 2); the copy copy is taken between batches, it carries no half of a batch
admission: the admission time of a record (chapter 1.1 N3 «Admission time») — in every raft log record and in the raft snapshot together with
           the rows: the snapshot carries the admission time of the last record that entered it, and a daemon raised from the snapshot continues from
           it; on a box (`box` below) — in the data directory with the same barrier as the rows. The copy copy does not carry it
           (chapter 1.1 N3). admission_ahead — in /v1/status of the leader (and of a box): by how many seconds the admission time of the last
           record is ahead of its clock, if more than CLOCK_SKEW 60 s (chapter 1.1 N0 «Cluster clocks»); otherwise there is no field; a
           follower and a door without a vote have no field. While the flag stands, writes with not_after by the writers' clocks get
           expired — the leader's clock went ahead and came back (ADR-0091 item 1)
durability: there is no environment variable or operational flag that turns off the durability barriers (chapter 1.1 «Implementation decides»
           item 3); an acceptance stand that needs speed says so by a flag of its «Stand» command
           (the common acceptance README), the units of P/02.4 N1.1 do not set it; a teaching store without durability names this in its
           description («Implementation decides» item 2) (the store pilot, A10)
admin_ops: status | join [-force] | leave [id] | admit <id> | backup <file> (0600, tmp + rename) | restore --from [-force]
           | import --from <copy> [-index-base N] [-force] | recover -id -dir -peers … -isolated [-upper N] [-force] | rights [-groups]
           import/restore/floor in a group (raft) — only on admin.sock of the leader, before the first row; on a box (`box` below) —
           into a fresh directory of a stopped daemon; recover — locally on a stopped daemon (there is no leader,
           no majority — N3 «recover»), not through a socket; status/backup/leave of oneself — at any;
           backup <file>: the file path (after resolving links) outside -dir of the daemon, otherwise a refusal before writing, code ≠ 0, the data
           directory untouched: a copy into the own log of a live daemon spoils it (reconciliation of python and go M10/6–11, B8);
           import into a directory where a former import has already finished (N3 phase «Done») — a refusal, code ≠ 0, nothing changes;
           an unfinished attempt is continued by a replay (import below) (reconciliation of python and go M10/6–11, B12)
floor:                                        # platform/epoch_floor {floor, generation_at}
  generation: max((upper >> 32) + 1, whole hours of UTC since 2026-01-01); floor = generation << 32;
              upper — the maximum of floor of the row platform/epoch_floor and epoch of every row <sub>/epoch/<id> (P/03.2 N1.5)
              in the whole verified input and in the saved state of the daemon (a fresh group has none); not a single row — 0;
              example at 2026-10-17T12:30Z (6948 whole hours): upper 5 → generation max(1, 6948) = 6948, floor 29841432772608;
              upper 30064771072005 (7000 << 32 | 5) → generation max(7001, 6948) = 7001, floor 30069066039296;
              the operator must confirm that the former installation handed out nothing above upper (for example, a copy after
              the writers were stopped);
              upper ≥ the current floor and all saved epochs. No reliable bound of the lost tail — a refusal of recovery
  when:    restore, import — before the first row: in a group only op: floor on admin.sock of the leader, on a box — as the first write
           into the directory of a stopped daemon (`box`); recover — locally in the dump of a stopped
           daemon (no socket, N3 «recover» step 1); the row is not
           written by put/delete; it only grows; a clock earlier than generation_at → a refusal without -force; force allows only
           the clock going back, but not a repeat/lowering of the generation, a uint64 overflow or a parallel recovery
  form:    floor in op: floor — a JSON integer without a fraction or an exponent (`20`, not `2.0e1` and not `20.0`), 1 … 2^53 − 2^32; otherwise — 400
           badrequest before writing (reconciliation of python and go M10/6–11, B5); epochs are JSON integers < 2^53 (ADR-0070), so the floor
           leaves 2^32 numbers above itself: generation ≤ 2^21 − 1 (hours since 2026-01-01 suffice for ~239 years); a generation
           that would give more — a refusal of recovery, as an overflow (added by the pilot of data family schemas, D6)
  issue:   next_epoch = max(current, floor) + 1 (P/03.2); an issue that read the floor before the raise can write a number
           below floor — the worker does not start such an epoch: a confirmation after the write (P/03.2 N3 «take_epoch(id)»; added
           by the Quint pilot, F1)
import:    from an immutable copy (copy above) into a fresh group — not a single row, except the rows of doors without a vote
           platform/configstore-doors/<id> (service rows of the group itself, `door` above: a live door writes its own every 30 s —
           it does not cancel the freshness; during the transfer its write, like those of ordinary writers, waits for «Done»; a door row in the input
           is transferred like a row of any family, and the live door rewrites its own; new versions — higher than any version in the group,
           of door rows too; C01-IMPORT-DOOR-ROWS-01): transferred rows keep the versions of the copy (index of the input row), restore —
           the same; -index-base ≥ the greatest version of the input — the start of new versions: every write after the transfer gets a version
           above the base and above any version of the group (C01-IMPORT-VERSIONS-01); the versions of the copy were not handed out by the group and can coincide with
           a version handed out in the fresh group before the transfer (there are only door rows there): for a door row the version can return
           lower — no harm, the door writes its row without cas and within 30 s rewrites it above the base (C01-VERSION-ISSUED-01); -index-base ≥ the greatest version; a full preliminary
           check before changing the floor/any row: the copy form (a Row line, the key by chapter 1.1 N1, the size not above the row
           ceiling), the versions (the base, index of the header) and the epochs — a row <s>/epoch/<id> with epoch not a decimal integer or
           platform/epoch_floor with floor not decimal, an epoch or floor row unreadable (outcomes of the families epoch, epoch_floor) — upper is not
           reliable, a refusal of the whole input (V7 item 3, the Architect's decision of 2026-10-28, row 13 of the list); the copy knows no manifests: import does not check
           the families of rows, a row of any family is transferred (log of cammeta-go, lesson 11 № 10). A bad row, size, base,
           epoch — without changes.
           Transfer excludes the input platform/epoch_floor: the first write is the new floor F1, with its new index and generation_at at that raise; then all other input rows keep their copy versions.
           Completeness is every input row except that old floor, plus the new floor row; a partial replay preserves the exact saved F1 row (items and index), never copies back the old floor or raises F1 again.
           After the floor is published a refusal can leave part of the rows; a replay continues the same attempt with the same floor,
           a new attempt — a new generation. Ordinary writers are not admitted until completion: the daemon does not
           start on such a directory (code 2, the log — repeat import with the same input), the store file:// in the process answers writes and reads with
           503 unavailable, the directory does not change (C01-UNFINISHED-IMPORT-WRITERS-01)
metrics:   configstore_raft_term, _state{state}, _elections_total, _index{kind=last|commit|applied}, _last_contact_seconds,
           _voters, _voters_expected, configstore_doors; configstore_doors is given by every voter — the leader and a follower — by its own
           replica of the rows and its own clock, without asking the leader (with an unreachable leader the series is the same); a door without a vote holds no replica
           of the rows and does not give the series configstore_doors (C01-DOORS-COUNT-PLACE-01, as the witness);
           a door without a vote is not a raft member: it gives no series configstore_raft_* and configstore_doors (otherwise dashboards would count it as a
           member of the group); its series are configstore_door_forwards_total{outcome=answered|unavailable|ambiguous} (counter:
           requests that it passed to the group, by outcome: answered — an answer of a voter was received, with any code; unavailable —
           no voter was reached, the door answered 503 unavailable; ambiguous — the write was sent, there is no answer, 503
           ambiguous) and configstore_door_voters_reachable (gauge: the voters that answered its last membership poll, once per 5 s)
           (C01-DOOR-METRICS-01, the Architect's decision of 2026-10-30, the meaning and the type — as the witness); alarms of the voters: membership ≠ declared, a follower lagging > 1000, more than 3 elections in 10 min
box:       the store of a box — a build without raft, one voter: -group-size 3 or 5, -join and -door — a start refusal with code 2
           («this build has no raft»); /v1/status — state Leader, term 1, leader — its -api address (empty without -api),
           leader_id — its id, voters [<id>],
           members {<id>: <api>} (without -api — {}, C01-STATUS-MEMBERS-NOAPI); /metrics — the series above with the values of one member (term 1, elections_total 1, last_contact 0,
           voters 1, voters_expected 1, doors 0); join of its own id — 200 {}, of a foreign one — 409 refused even with -force; leave — 409 refused
           («the last voter»); admit — a refusal, code ≠ 0; recover — a refusal, code 2 («this build has no raft»): a box has no
           group, there is nothing to recover it with, a copy — import (reconciliation of python and go M10/6–11, B15); import/restore on a box — into a fresh directory of a stopped daemon,
           not through admin.sock (in a group — admin.sock of the leader, `admin_ops` above): the floor as the first write, then the rows; restore
           coincides with import (there are no neighbours); forwarding from the role configstore-door on -api of a box — 403 (P/01.2 box: there are no trusted forwarding senders;
           a door without a vote — only in a build with raft; C01-BOX-DOOR-01)
repeat:    membership operations are repeatable: admit of an already admitted correct id — code 0, the membership and the rows do not change; a repeated join
           of the same id with the same Raft address — updates the API address; join of an id with another Raft address and leave of an unknown id —
           409 refused, without changes (guess of stage C CL-03, the Architect's decision of 2026-10-23)
```

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R007

old-sha256: 5635a895b567b9ce5e483c9389947416b5fa6e87af1841dd8a9fa63d93dd63b4

<!-- req: P/01.3-R007 -->
**Flag purposes.** The closed set, types, defaults, requiredness, commands and refusal predicates are sourced only by [forms/daemon-flags.tsv](../forms/daemon-flags.tsv). An unknown name is the `start_flags` refusal of the [refusal catalogue](../forms/refusals.tsv); the purposes below are not a second grammar.

- `-dir`: the data directory of the daemon; the mark `FORMAT` (`format` above); also of `recover`, `restore`, `import` — they write into the directory of a stopped daemon on a box (ADR-0125 addendum (2) item 1)
- `-id`: the member name in `members`, `voters`, `leader_id`; also of `recover`
- `-sockets`: the socket directory, flat (`sockets` above); the commands `status`, `join`, `leave`, `admit`, `backup`, `restore`, `import`, `rights` find `admin.sock` by it, `recover` does not (ADR-0125 addendum (2) item 1)
- `-rights`: the rights file
- `-tls`: the root of the certificate kits (N1.6), mTLS of `-raft` and `-api`
- `-raft`: the raft address that the daemon names to its partners
- `-raft-bind`: the address on which the daemon listens for raft, if it differs from the named one
- `-api`: the address of the service doors of N2 for partners; the value of `members` and `leader` in `/v1/status`; without `-api` the member is not in `members` (the map can be `{}`; C01-STATUS-MEMBERS-NOAPI, the Architect's decision of 2026-10-26)
- `-bootstrap`: the first server of the group (`join` above); with `-join` — a start refusal
- `-join`: the `-api` address of a group member through which the daemon joins (`join` above); always with `-tls`
- `-group-size`: the declared group size, the same on all servers
- `-force`: joining at a transitional evenness (`join` above), also of the command `join`; for `restore`, `import`, `recover` — only the clock refusal
- `-isolated`: only for `recover`, required: the operator confirms that the former group and the writers are isolated and nothing was handed out above upper (N3 step 0); without it `recover` is a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23)
- `-upper`: only for `recover`: the bound of the lost tail of epochs known to the operator; it only raises the computed upper (`floor.generation`): upper := max(computed, N); N below the computed one — a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23)
- `-peers`: only for `recover`: the recovered membership — the remaining members, the one being recovered (`-id`) among them; the id and both addresses are required for each: raft — the address of the raft membership, api — the value of `members` in `/v1/status`; any other notation — a refusal before changes (guess of stage C S03, the Architect's decision of 2026-10-23)
- `-door`: a door without a vote (`door` above)
- `-voters`: the voters for a door without a vote: the id and the `-api` address
- `-tuning`: the raft timing profile (`tuning` above)
- `-leader-wait`: the leader wait (`leader_wait` above)
- `-max-value`: the row ceiling (chapter 1.1 N4, `{row_ceiling}` of «Stand»)
- `-max-body`: the read limit of the HTTP body of `POST /v1/write` (chapter 1.1 N2, `{body_limit}` of «Stand»), separately from the row ceiling `-max-value` (log of cammeta-python, lesson 11 № 24)
- `-max-conns`, `-api-conns`, `-api-per-address`: connection limits (below)
- `-index-base`: for `import`: the version base (`import` above)
- `-groups`: only for `rights` (`admin_ops` above; ADR-0125 addendum (2) item 1)
- `--from`: only for `restore`, `import`: the input — the backup copy (`copy` above; `admin_ops` above; ADR-0125 addendum (2) item 1)

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R029

old-sha256: a73c47e5837686faa14e9638ef13c4220e945d1eeb9bfbeaeac5586633e5d87d

<!-- req: P/01.3-R029 -->
The catalogue of these refusals — [`forms/refusals.tsv`](../forms/refusals.tsv) (ADR-0125): the form is the sole source of code, kind, fields, headers and log projection. The OpenAPI fault schemas and write-check order stay their owning forms; the causes, priority and caller actions below refer to stable refusal names, without duplicating the outcome cells.

- `service_body_form`: service HTTP: unknown fields, not an object/not JSON, extra JSON, bad framing/truncation/read timeout, an inadmissible field. Caller action: fix the input; there is no side change.
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
- `no_leader`: no leader for 5 s. Caller action: wait; workers live by the lease.
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

## REMOVED

(none)

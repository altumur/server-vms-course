# Delta 0129-p01-v2-norms — ADR-0129 (10), item 3

change: 0129-p01-v2-norms rev 1. Base a635beb6a4f5c13e04034c4dc96d14a798a035a6; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R007

old-sha256: 165f8c4c9d24aee1f94e8fa48fc41c9d72403c3d2ee814ac8e56dc72bc99b581

<!-- req: P/01.1-R007 -->
- The **writer** MUST write a fraction of at most 3 digits: `^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`. A field whose form is
  `float` in [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.2 (table stamps, `sweep.at` there) is also written
  in the shortest notation.

  Private admission metadata is not a row time field subject to this writer notation. It uses the finite binary64 numeric domain of N3 «Admission time» and MUST preserve its assigned value through storage and restoration, including fractions longer than this row-writer notation permits. This exception prescribes no internal encoding or additional wire field.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R013

old-sha256: ec0aea5799ccdcfbd6c99ec8bbc37bc9b9d4818910d16d32ff65fc5df1fcbb5e

<!-- req: P/01.1-R013 -->
A premise of the cluster (ADR-0091 item 1): the wall clocks of its writers — the store leader, the controller, the console
door, the workers, and the writer of the event a worker writes about — differ from one another by at most `CLOCK_SKEW` from [forms/runtime-constants.tsv](../forms/runtime-constants.tsv). Norms rely on it (deadlines of rows with `made` — [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.1
`platform_fields`, [P/03.6](../../03-worker/spec/03.6-worker.norms.md), [P/04](../../04-controller/spec/04-controller.norms.md))
but do not check it: clock synchronization is a matter of deployment, as for the domain holders
([P/08.2](../../08-domain/spec/08.2-domain.norms.md) `rev.clocks`). A common move of all clocks backwards does not break
the premise: the order of records with time conditions is kept by the store's admission time (N3 «Admission time»), not by
the writers' clocks.

### Order of output arrays

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R019

old-sha256: 0576ef9bbef9628c2730a1e147b0a211fc009058f1775ab876cdf3f7c82d3391

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
      - at most KEY_BYTES bytes                     # at the door; a file-based implementation MAY refuse earlier (below)
    note: one spelling — one place; a key that breaks a rule gets badkey, it is not repaired
    compare: by UTF-8 bytes, without normalization — a//b, a/./b, a/b/ and the NFC and NFD forms of one text are different keys
  items:                     # the content
    type: map                # string → string; the order of fields has no meaning
    rules:
      - every key and every value is a string
      - weight (sum of byte lengths of every key and every value) at most the store's ceiling
    ceiling: ROW_CEILING     # configured ceiling; on a daemon, effective -max-value; its default is only in forms/daemon-flags.tsv
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

`KEY_BYTES`, `BATCH_WRITES` and `BATCH_GUARDS` are the named limits in [runtime-constants.tsv](../forms/runtime-constants.tsv). `ROW_CEILING` is the configured ceiling of this store instance; on a daemon it is the effective `-max-value`, whose default is owned by [daemon-flags.tsv](../forms/daemon-flags.tsv). An in-process store uses its declared ceiling and the N5 stand parameter without a required flag or internal API. This is not a second fixed row ceiling.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R021

old-sha256: ecd669b1e7f364b58a51b849a9dc05b48746106ec23abf202f8ccf0bf88145a2

<!-- req: P/01.1-R021 -->
A file-based implementation, where a row is a file named after the key, MAY refuse a key that passes the door limit if its
encoded name does not fit a file name; it names its own limit, smaller than KEY_BYTES UTF-8 bytes, in its description (the
implementation decides).

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R048

old-sha256: 4eeeec8fadf810e387db9e6318b17f43a0ea8f6c5eeac1593a24f15782154a0a

<!-- req: P/01.1-R048 -->
- **The body of `POST /v1/write`** is JSON by [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259): a repeated field name
  in any object of the body (§4), `NaN`, `Infinity`, a BOM and non-UTF-8 bytes (§8.1) — `400 badrequest`. A lone surrogate
  (`\ud800`) in `key` or `guard.key`, or for a batch in the `key` of an element of `writes` or `guards` — `400 badkey`: the
  string cannot be encoded in UTF-8 nor measured by N1; in a name or value of `items` — `400 badrequest`; in extra fields
  it is not read. Numbers and strings of extra fields are not read at any length. The nesting depth is one number for all
  implementations: `JSON_DEPTH` ([runtime-constants.tsv](../forms/runtime-constants.tsv)) nested objects and arrays from the root, the root object counts 1, in any field,
  extra ones too; depth `JSON_DEPTH + 1` — `400 badrequest`.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R070

old-sha256: e7520deade3b544a652057cf8ffb6712d4c2b2dae59420c23adb4a555f59a238

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
Admission time uses finite binary64 Unix seconds. Convert the clock reading to binary64 with round-to-nearest, ties-to-even before the `max`; the previous admission value and both bounds use that same numeric domain (R007). Storage, restoration and application MUST preserve the assigned binary64 numeric value. They MUST NOT additionally round it to integer seconds or milliseconds, or apply the row-writer notation limit of N0. The physical clock's accuracy and resolution are not prescribed; conversion to binary64 does not promise to retain a fraction smaller than its representable spacing.
For an admission time A, `not_after` admits A <= bound and refuses A > bound; `not_before` admits
A > bound and refuses A <= bound, also on fractional boundaries (N1).

An already-admitted replay retains its newly assigned admission time by this rule, even when id memory supplies the first answer without a business-row write, new issued version or changed applied-id entry. It must survive an ordinary close/reopen as the last admission metadata. A subsequent rollback of the physical clock cannot undo it.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R078

old-sha256: 41398b32548e815f5809847660cf3594177ac47b4816c4276522739d564f9d84

<!-- req: P/01.1-R078 -->
7. If id is given and has already been applied:
   1. If that record was different (op, key, items, cas, guard, not_after, not_before), return `badrequest`; keep the original applied-id entry and its answer unchanged. This is after admission, so the new last admission time is retained by R070.
   2. Otherwise return its answer with again=true; the rows, issued versions and applied-id entry do not change. The last admission time still advances by N3 «Admission time» (R070), with its durability, even when the answer comes from this memory.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R088

old-sha256: 576bb9e896399570c630f8ad7a244d614725872c56af552713649dbe4a75272d

<!-- req: P/01.1-R088 -->
The order of checks inside the operation is normative: the `id` memory, then `not_after` and `not_before`, then the guard,
then CAS; with several violations the answer is by the first one (ADR-0091 item 1). A replay of an applied write gets its
answer also after `not_after` — including a replay that arrived while the first copy was not yet applied: the first one
is applied first, the replay answers with its answer. A refusal `expired` and `early`, like `conflict` and `guard`, makes no write and does not take the `id`, but the admission time of the refused
record remains the last admission time (in a group — a log record; a box and a store in the process store it as durably
as rows; C01-ADMITTED-ON-REFUSAL-01). Only `expired` remains the same refusal for the same deadline and nondecreasing admission time. `early`, `conflict` and `guard` do not occupy the `id`: the same command and `id` are checked again against the current admission time and state and may succeed. The caller still re-reads its condition and decides anew before another attempt (N4). The guard before CAS. A guard refusal means a mismatch of the observed version and the absence of this write. The caller re-reads the condition and decides anew whether it has the right to repeat; a version mismatch by itself does not prove a loss of ownership. A CAS refusal also requires a re-read before a new attempt. A guard on an absent row (`index: ""`) holds while the row does not exist.

The absence of business effects is distinct from admission metadata: an already admitted put or delete that returns `expired`, `early`, `guard`, `conflict`, or `badrequest` for mismatching an already-applied id still updates the last admission time to this record's `admitted` (which may equal the previous time). It does not roll that metadata back with the refused row/id/version effects. An id mismatch keeps the first applied-id entry and its original answer, without replacing or freeing them. The persistence rule is the same as for admission in the successful case (N3 Admission time). This statement concerns an already admitted record, not a request rejected before admission.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R105

old-sha256: b3a4b6da492b5ed25b4537ac37d0b35b351597d32cca3ca80f6dfc8fed5b67d9

<!-- req: P/01.1-R105 -->
6. Replay by id: compare (op, key, cas, guard, not_after, not_before); items is not read and is not part of the
   fingerprint, even if sent with another JSON type. If they match, return the former answer with again=true; otherwise
   return `badrequest`. In either branch the business rows, issued versions and original applied-id entry stay unchanged; the newly admitted time is retained durably by R070, also for a mismatch.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R122

old-sha256: 0c62897e8c820a4b7b19344b6168566ac5229819317649fbfb6280b0409fb91a

<!-- req: P/01.1-R122 -->
6. If id is given and has already been applied:
   1. If that record was different (fingerprint below), return `badrequest`; keep the original applied-id entry and its answer unchanged. This is after admission, so the new last admission time is retained by R070.
   2. Otherwise return its answer with again=true; the rows, issued versions and applied-id entry do not change. The last admission time still advances by N3 «Admission time» (R070), with its durability, even when the answer comes from this memory.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R132

old-sha256: cd44f7d9272fd63887953d71a2df8a75da9aa0d7083295d6c1f68ac7e3d30bbc

<!-- req: P/01.1-R132 -->
The refusals `expired`, `early`, `guard`, `conflict` make no write, do not take the `id` and do not spend versions; the
admission time of a refused batch remains the last admission time, as for a write. A refusal names the row but not the
value: `412 guard {key, index}`, `409 conflict {key, index}` — the version of this row now.

The refused batch still updates the last admission time to this record's `admitted` (which may equal the previous time), with the same durability as admission of a successful batch. Zero business-row changes, no occupied `id` and no issued version do not mean rolling back this admission metadata. This applies to each of the four named refusals after admission. An admitted batch returning `badrequest` for an id mismatch also retains its new last admission time with the same durability and no business-row or issued-version effects; its original applied-id entry and answer remain unchanged. None of this applies to a request rejected before admission.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R141

old-sha256: d237c77126d8b964aa74d92af3dd834ff10e089b904506e123319c3dbd323b62

<!-- req: P/01.1-R141 -->
The store MUST answer a replay with the same answer until both conditions hold: more than `ID_REPLAY_MIN_AGE` has passed since the first application **and** at least `ID_REPLAY_MIN_RECORDS` records with an identifier have been applied after it; when both hold, it MAY forget. A forgotten replay is applied as a new write — hence `cas` on every write that matters.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R145

old-sha256: df524d7e91dea64ba87e5f2a56c6bf102aed0f1d146effa9e895e1cd01ca5c9f

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
7. **how the door tells «not added to the log» from «unknown»**; the leader wait time before `unavailable` is 5 s from the loss of the leader, a norm of P/01.3 N1.3, not a choice.
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

### `Platform/01-store/spec/01.2-store.norms.md` P/01.2-R031

old-sha256: 51a4471c754104ae0c12c33dc000a57929e9e16f1683054ea10ace0a29db954b

<!-- req: P/01.2-R031 -->
---

## N5 Acceptance

The catalogue `Platform/01-store/acceptance/2/` ([README](../acceptance/2/README.md)): the store door of chapter 1.1 under the **roles** of the deployment `testsub` (the ready rights file of the stand `inputs/rights.json` is a subset of the derivation of P/02.5 N1.4 from the manifests `testsub` and `testsub2`): a step goes from the named role (`@as <role>`), the runner calls through the socket of this role or by the writer's name.

| № | Scenario | Norms |
|---|---|---|
| 05 | nobody deletes an epoch: a worker, a controller, the console — 403; admin and an empty `<y>` (`testsub/epoch/`) — 403 | N1.3 |
| 06 | listing: a role without the read right gets names and versions, `GET` of a row — 403 | N1.3 |
| 07 | a guard on a row without the read right — 403; on one's own — passes | N1.3 |
| 08 | a header with another role on a role socket — 403 (only the cluster door), and with a body out of form — 403, not 400 | N3 |
| 10 | `GET /v1/rights`: a worker and the console — 403, admin — 200 the rights file | N2 |
| 11 | `never`: put and delete of `platform/epoch_floor`, delete of `domain/holder` — 403 for the console and for admin (for admin the rights would otherwise allow it); a read of the floor by admin — 200 (coverage audit P/01, A03) | N1.3 `never` |
| 12 | a header with another role on a role socket at `GET /v1/list` — 403 before the listing; without the header — 200 (A04) | N3 «check» |
| 13 | without a rights file — only `admin.sock`, `GET /v1/rights` — 404; a file with an unknown field, with an internal role, with a role name not by the grammar — start refused, code 2; the stand file again — 200 (`@rights store`, NEW-DIRECTIVES § 2 of the audit) | N1.2, N4 |
| 14 | the edges of `never`: for admin a delete of `platform/epoch/<y>`, `<x>/epoch/<y>/<z>` and `<x>/epoch` — 200; the domain roles `domain`, `domainagent`, `<sub>domain` delete under `domain/` — 200 (coverage audit P/01, second pass, G04; C01-NEVER-DOMAIN-ROLE-01) | N1.3 `never` |
| 15 | a non-string `comment` of the rights file — start refused, code 2; the string `comment` of the stand file is returned by `GET /v1/rights` (G04) | N1.2, N2 |
| 16 | a batch by roles (ADR-0094 B9): the role `console` writes `BATCH_WRITES + 1` rows in one batch, another role — 400 (`BATCH_WRITES` P/01.1 N1); `BATCH_GUARDS + 1` guards for another role — 400, for the role `domain` — 200 (sc. 14); a row without the right, a guard without read — 403 for the whole batch, nothing written; `never` of one row of the batch — 403, for admin too | N1.3 `batch`, N3 «check»; P/01.1 N1 |

The scenarios of the derivation of rights from the manifest (01–04, 09, 11, 12) and the variants of manifests are in the acceptance
of [P/02.5](../../02-installer/acceptance/5/README.md): their outcome is decided by the derivation of P/02.5 N1.4, not by the evaluator.

---

## Implementation decides

The implementation is obliged to name in its description:

1. **how the runner and the tests call as a role on one box** (the writer's name, a test socket);
2. **the exact text** of `error` beyond «\<role> may not \<action> \<key>» (the name of the file, of the daemon);
3. **the forwarding of a role inside the group of daemons** (the header, the check of the voting one).

---

## Readiness checklist

- [ ] **P/01.2-01** rights: a 403 refusal outside one's own prefix, including on the guard row of `put` and of `delete`; a listing of names without values — sc. 21 of the acceptance of chapter 1.1
- [ ] **P/01.2-02** the roles and groups of N1.1; the file does not name the internal roles; the grammar of the role name and internal roles in the file — start refused, sc. 13
- [ ] **P/01.2-03** the rights file of N1.2: the form, the patterns, `!`, separated `write`/`delete`, byte-stable generation, `--check` of the installer — checked by reading; `GET /v1/rights` only admin — sc. 10; without the file — 404, an unknown field — start refused — sc. 13; a non-string `comment` — start refused, a string one is returned — sc. 15
- [ ] **P/01.2-04** one evaluator for files, memory and the cluster; a negation wins everywhere; a role outside the file — nothing — sc. 01–04 of the [acceptance of P/02.5](../../02-installer/acceptance/5/README.md) (through the door and through the API); the negation `!testsub/idem/*` of the worker on a read — sc. 01 step 7 of the acceptance of P/02.5; a negation of a subprefix first in the list before a wider permission (`!acc/pre/secret/*`, `acc/pre/*`) — rows of the package `rights-evaluator`; an unknown role — checked by reading
- [ ] **P/01.2-05** `never`: the epoch, `domain/`, `epoch_floor` — sc. 05, for admin too (step 6) and an empty `<y>` (steps 8–10); `domain/` (a delete not by a domain role) and `platform/epoch_floor` (put, delete) — sc. 11, for the console and for admin; the edges `<x>/epoch/<y>` (`x = platform`, two segments, without `/`) outside `never` and a delete under `domain/` by domain roles — sc. 14
- [ ] **P/01.2-06** a listing without the read right — names and versions; a read without the right — 403 — sc. 06
- [ ] **P/01.2-07** a guard requires the read right to the guard row — sc. 07
- [ ] **P/01.2-08** the identity — the role socket / the writer's name; the role header is not read; forwarding only from a daemon of the group (a voting one or the door without a vote) — sc. 08; the refusal of a role header before the body is parsed — sc. 08 step 2; at a listing — sc. 12; a forwarded admin with a loaded file — sc. 07 of chapter 1.3 (the probe `@tls`); by reading
- [ ] **P/01.2-09** a batch is judged per row: `write`, `delete`, the read of a guard, `never` for admin too, a refusal of one — 403 for the whole batch, nothing written; the limit of the number of rows — for all roles except `console` — sc. 16

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R006

old-sha256: 87517b7c77f88a42b65e49889433bcc92df7ed02a320cdef3e68e7397154dd4e

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
leader_wait: the effective -leader-wait interval from the loss of the leader (not per request) → 503 unavailable; a write gone to the leader without an answer → ambiguous (chapter 1.1)
sockets:   flat: <-sockets>/admin.sock and <-sockets>/<role>.sock, no subdirectories (the store pilot, A3);
           inherited ones (the sd_listen_fds protocol: LISTEN_FDS, LISTEN_FDNAMES) the daemon takes by FileDescriptorName=admin |
           <role>: the mode and the group were set by the unit (P/02.4 N1.1); a name that is neither admin nor a role of the rights file — start refusal, code 2, the log
           names the name; a socket that was not passed, the daemon creates itself in -sockets: admin.sock 0600, <role>.sock 0660
           with the group of the process (the store pilot, A10);
           admin.sock 0600 (root; everything except never of chapter 1.2; not forwarded); <role>.sock 0660 the group of the role;
           a role header on a role socket → 403; forwarding to the leader is trusted only from a daemon of the group — a voter or a door without a vote — by the role in SAN (chapter 1.2 N3)
door:      -door -id -voters a@h:p,…: without a vote; the same sockets and rights; to the leader or any voter (attempt DOOR_REQUEST_TIMEOUT, margin DOOR_REQUEST_MARGIN);
           the group membership — every DOOR_MEMBERS_EVERY; the row platform/configstore-doors/<id> {seen_at} every DOOR_SEEN_EVERY (not under platform/doors/ — there are the doors of servers, P/05 N1.4);
           it is written by the door itself: by a request to the leader over mTLS with its own role configstore-door (forwarding of roles of chapter 1.2 N3), by the command
           put of its own row without cas and guard, the only element seen_at; any other write from the role configstore-door, a batch op: batch included, — 403;
           a foreign batch the door forwards whole, in one request (chapter 1.1 N3 «write batch»; ADR-0094 B9);
           «own» — <id> = the server from the verified certificate of the peer (CN configstore-door.<server> / SAN DNS); a claimed
           identity of the door (<id> of the key, the door name in the forwarding header) not equal to it — 403, nothing is written; Cmd.id
           of the replay memory (P/01.1) is not an identity, it is not compared with the server (C01-DOOR-ID-CN-01);
           the door does not touch admin.sock and does not forward its requests (log of cammeta-go, lesson 11 № 3); it is counted in
           configstore_doors while its row reads in its own form and seen_at in it is not older than DOOR_SEEN_PERIODS × DOOR_SEEN_EVERY by the clock of the voter
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
           record is ahead of its clock, if more than CLOCK_SKEW (chapter 1.1 N0 «Cluster clocks»); otherwise there is no field; a
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
           platform/configstore-doors/<id> (service rows of the group itself, `door` above: a live door writes its own every DOOR_SEEN_EVERY —
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
           ambiguous) and configstore_door_voters_reachable (gauge: the voters that answered its last membership poll, once per DOOR_MEMBERS_EVERY)
           (C01-DOOR-METRICS-01, the Architect's decision of 2026-10-30, the meaning and the type — as the witness); alarms of the voters: membership ≠ declared, a follower lagging > RAFT_LAG_ALARM, more than RAFT_ELECTION_ALARM_COUNT elections in RAFT_ELECTION_ALARM_WINDOW
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

Fixed `DOOR_*` and `RAFT_*` numeric limits are owned only by [runtime-constants.tsv](../forms/runtime-constants.tsv). The effective `-leader-wait` and connection-limit defaults are owned by [daemon-flags.tsv](../forms/daemon-flags.tsv).

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R007

old-sha256: d1ca4a21fc9b958300c0a461dcba8c1806993f340cabe19f473a8188ad1fa3cf

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
- `-max-body`: the effective entity-body read limit of `POST /v1/write` and service POSTs of N2 (chapter 1.1 N2, `{body_limit}` of «Stand»), separately from the row ceiling `-max-value` (log of cammeta-python, lesson 11 № 24)
- `-max-conns`, `-api-conns`, `-api-per-address`: connection limits (below)
- `-index-base`: for `import`: the version base (`import` above)
- `-groups`: only for `rights` (`admin_ops` above; ADR-0125 addendum (2) item 1)
- `--from`: only for `restore`, `import`: the input — the backup copy (`copy` above; `admin_ops` above; ADR-0125 addendum (2) item 1)

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R008

old-sha256: 1c136de4275f084150fdc9948969c40ca19185f099a43199182c291a103c798e

<!-- req: P/01.3-R008 -->
The connection-limit defaults are owned only by their rows of [daemon-flags.tsv](../forms/daemon-flags.tsv), not by a hidden choice of each implementation. A deployment MAY set other positive limits before
the run starts and name them in the description; the connection limit gives 503 `unavailable` with `Retry-After: 1` (chapter 1.1 N4).

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R031

old-sha256: b6b45b70a05d92366ceeaf04e88e00a4987ee78c6e189f24e02ecd7c81e2f809

<!-- req: P/01.3-R031 -->
The writing of the flags (ADR-0125 addendum (2)): a flag is `-name value` or `-name=value`, the name exactly as the table writes it (`--from` with two hyphens); a flag of the type `bool` is written without a value (`-door=true` is a refusal); `--` alone ends the flags. A repeated flag, a flag of another command, a value out of its type and a positional word of the daemon are a start refusal, code 2; positional words are only those of `admin_ops` by its grammar above (`admit <id>`, `backup <file>`, `leave [id]`). The values: `bytes` and `int` — a decimal integer without a sign, a plus or leading zeros (`0` itself is allowed), `bytes` without a unit suffix (`512KiB` is the writing of the prose, not a value); `duration` — `<integer><unit>`, the unit `ms`, `s`, `m` or `h`, greater than `0` (`5s`, `250ms`); `addr` — `host:port`, a non-empty host (a name, IPv4 or `[IPv6]`) and a decimal port `1`–`65535`. The default of `-id` and the absence of a default are defined only by its row and header in [daemon-flags.tsv](../forms/daemon-flags.tsv).

### N1.6 Certificates: the side of the verifying peer

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R016

old-sha256: 93348b3bb1c6283f037fe0de1b2a62c39d3de5052b38506a15a47e4b66e05301

<!-- req: P/01.3-R016 -->
| HTTP door | Full form / rule |
|---|---|
| GET `/v1/status` | `{id, state, leader, leader_id, term, commit, applied, voters, members, tls, max_value, max_body}`; optional `base, again, role, last_snapshot, out, admission_ahead` (N1.3 `admission`; ADR-0091 item 1). Indices are exact uint64, state — Leader/Follower/Candidate/Shutdown/Door; voters/out — an array of ids, members — a map id → `-api` address, without `-api` the member is not in `members` (the map can be `{}`; a value is never empty — `minLength: 1` of OpenAPI; C01-STATUS-MEMBERS-NOAPI, the Architect's decision of 2026-10-26); `leader` — the `-api` address of the leader (empty if the leader is unknown or was started without `-api`), `leader_id` — the id of the leader (empty if the leader is unknown) (the store pilot, A7). Door requires role=door and term/commit/applied=0. `max_value` is this instance’s effective row-weight ceiling in bytes, the value of `-max-value` (N1.3; the row weight of chapter 1.1), separately from `-max-body`; the acceptance stand parameters are N5. `max_body` is a required positive integer: this instance's actual configured `-max-body` in entity-body bytes (including JSON whitespace and an actual LF, excluding HTTP framing); its default is owned only by the flag form. It is not derived from max_value. The installer reads it for the static finite-profile check before writes (ADR-0127 P/06 C2). This is a local observation, not a confirmation by the majority |
| POST `/v1/join` | `{id, raft, api, force?}`, success 200 `{}`; 409 `{kind: refused, error}` — an inadmissible membership; 403 — `ForbiddenFault` of chapter 1.1: it is called only by `admin.sock` and a daemon of the group over mTLS of the role `configstore` (N1.3 `identity`); a role socket (`console.sock` and others) — 403 before parsing the membership (reconciliation of python and go M10/6–11, B1); empty `raft`, `api` — 400 before the membership (B4) |
| POST `/v1/leave` | `{id}` (an empty string — oneself), success 200 `{}`; a role socket — 403, as for join (B1); a change of another's membership — only through admin.sock (`leave [id]` of admin_ops N1.3); for a box without raft the leaving of the last voter — 409 `{kind: refused, error}` «the last voter» (N1.3 `box`) |
| GET `/v1/rights` | The exact form and the refusals of chapter 1.2, availability admin/role/forwarding by its N3 |
| POST `/v1/write` | An ordinary Cmd of chapter 1.1, a batch BatchCmd of chapter 1.1 or `{op: floor, floor: integer 1 … 2^53 − 2^32, id: 1–64 lowercase hex}` on admin.sock of the leader. A replay of floor with the same id returns the saved outcome — the replay memory is the same as for a write with id (chapter 1.1 N3 «Replay by identifier»): in the store, with its durability and the same lifetimes — a durable one survives a daemon restart, a non-durable teaching one («Implementation decides» item 2) loses at a restart both the floor and the memory, and says so in its description; another payload with this id — a refusal 400 badrequest of chapter 1.1 (not a CAS conflict); a new id with floor ≤ the current one — 409 refused (a row of chapter 1.1 N4). Success — Written of chapter 1.1. An ordinary write of floor through put/delete is forbidden |
| GET `/metrics` | The list of text series of N1.3; correct escaping of labels |

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R017

old-sha256: 1ed365d4a4367bf49c2387e42bb65b24b28aeb9ac5b823af3d1ff811ce40d37d

<!-- req: P/01.3-R017 -->
A member identifier is 1–128 ASCII characters: the first a letter/digit, then letters/digits/`_`/`.`/`-`. This is the input profile of this lesson. The request parsing of the service doors is chapter 1.1 N2.1 (query, the JSON of the body, the path byte for byte, HTTP, early refusal); deviations are below. The order of checks: the frame (framing, the effective `-max-body` limit — 413) → route and method (404, 405) → identity (403) → body and membership (400, 409): an extra body larger than the limit with a foreign method — 413 earlier than 404/405 (reconciliation of python and go M10/6–11, B3). `HEAD` is not a method of the service doors: `/v1/status`, `/v1/join`, `/v1/leave`, `/metrics` — 405, `/v1/write` and `/v1/rights` — 404 by their owners, chapters 1.1 and 1.2 (both implementations, agreed without a norm). The bodies of service POSTs are one JSON object; unknown fields are rejected; the read limit is the same effective `-max-body`, counting actual entity bytes, extra JSON/framing/truncation — 400, exceeding — 413, the read time is limited by the implementation. 400/404/405 — `BadRequestFault`, 403 — `ForbiddenFault`, 413 — `BodyTooLargeFault` of chapter 1.1. For own status/join/leave/write/metrics 503 is `UnavailableFault` before sending, `AmbiguousFault` after sending a change; at the connection limit — `UnavailableFault` with `Retry-After: 1` (chapter 1.1 N4). After an unknown join/leave the operator reads status; there is no automatic proof of success from a timeout. The floor keeps the replay memory of chapter 1.1.

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R029

old-sha256: c2a200bab9aeb047122290865cb6ba4f1c816775edf4956626408db24d3241e2

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

### `Platform/01-store/spec/01.3-store.norms.md` P/01.3-R030

old-sha256: 4d61bacb93b9ced1fe5054d46b5bf646a9c3f7b580de739242a7b81537a53c3b

<!-- req: P/01.3-R030 -->
---

## N5 Acceptance

The directory [`../acceptance/3/`](../acceptance/3/README.md): the stand store ([the common acceptance README](../../common/acceptance/README.md)) with the stand's rights file, its service doors, a copy and a foreign directory; sc. 07, 17, 18, 25–29, 31 — the store group stand (several daemons on the loopback, the common acceptance README «Store group stand»; formerly sc. 07 was a drill `@manual`; work rules (for people) § 4). The scenario numbers are the former numbers of the acceptance of M10/11.

| № | Scenario | Norms |
|---|---|---|
| 04 | daemon metrics: `configstore_raft_term`, `configstore_raft_voters_expected` on `/metrics` of the store | N1.3 |
| 07 | a group of three: the joining of a fourth — 409 even with `force`; a door without a vote: `Door`, a write with the same rights file, the row `seen_at`, the series `configstore_doors`, `-id` not the server of the leaf — code 2, a foreign door row — 403; a forwarded admin with a loaded rights file — 403 (A08); a door leaf on `-raft` — a refusal by the handshake (C01-RAFT-DOOR-LEAF-01) | N1.3 `join`, `door`, `metrics`, `refuse_start` |
| 08 | a replay of `op: floor` with the same `id` after a store restart — the saved outcome (`again`); another floor with this `id` — 400; a floor not as an integer (`2.0e1`) — 400; a floor above the upper bound of N1.3 `floor.form`, including the greatest uint64 — 400; the upper bound itself is admissible (the pilot of data family schemas, D6) | N2, N1.3 floor |
| 10 | a second store instance on a foreign directory: a non-empty one without `FORMAT` and one with a foreign mark — code 2, the directory is byte for byte the same (`@foreign store`) | N1.3 `format`, N4 |
| 11 | copy: the input `inputs/copy-ok.jsonl` and the same without key order are transferred into a fresh directory, the rows read, the floor is raised; the `backup` copy of the stand store is transferred and carries the manifests (`@backup store`, `@import store`) | N1.3 `copy`, `import` |
| 12 | copy: one input per each `copy` refusal — another `format`, `version`, an extra field of the header, no header, an extra and a missing field of a row, not JSON, not Row, a repeated key, `index` above the header, `unreadable`, a row key not by chapter 1.1 N1, `generation_at` of the floor not a time, a clock earlier than `generation_at` of the floor of the input — `import` is refused, not a single row is transferred | N1.3 `copy`, `import`, `floor`, N4 |
| 14 | the `id` replay memory is not part of the copy: a write with `id` before `backup`, after `import` a replay of the same `id` — a new write without `again`, the next one — `again` (B10) | N1.3 `copy` |
| 15 | service doors, steps 1–8: `join`/`leave` from a role socket — 403; a body larger than the effective `-max-body` — 413, also with a foreign method, earlier than 405; empty `raft`/`api` — 400; `HEAD` — 405 and 404 (B1–B4) | N2 |
| 16 | a single member without `-api`: `/v1/status` — `state` `Leader`, `leader` empty, `members` — `{}` (C01-STATUS-MEMBERS-NOAPI) | N1.3 `-api`, `box`; N2 `GET /v1/status` |
| 17 | sizes 2 and 4 — code 2; the `/metrics` series of the leader and a follower (A10); `leave`/`admit`, a repeat of membership operations; a restart of a follower and of the whole group — the versions are the same; a leader change — a read sees the last write; a cut-off follower (`@cut`) does not give an old version; a door and one voter — 503 | N1.3 `group`, `leave`, `repeat`, `leader_wait`, `door`; P/01.1 N3 |
| 18 | `import` into a fresh group — the transferred rows keep the versions of the copy, `cas` by them passes, a repeat — a refusal; `recover` without `-isolated` and with a low `-upper` — a refusal, with `-isolated` — the floor above the upper of the epoch row; new members join | N1.3 `import`, `floor`, `admin_ops`; N3 «recover the store» |
| 19 | the version after a daemon restart: the former row reads with the former version, two new writes — the versions are pairwise different (coverage audit P/01, A01) | P/01.1 N1 `index`; N1.3 `durability` |
| 20 | a damage of a row bypassing the door (`@spoil row`): `{items: null, index, unreadable: true}`, a listing — the name and the version, `cas` by it replaces; the loss of the version (`@spoil row-index`) — 503 for a read and a listing (A05; C01-ROW-INDEX-LOST-01) | P/01.1 N2, «Implementation decides» item 5 |
| 21 | the `id` replay memory (P/01.1 N3) holds at least two minutes: a replay after 121 s — the same `index` and `again` (A02; the sleep is the term of the norm) | P/01.1 N3 «Replay by identifier» |
| 22 | a damaged row (`@spoil row`) for a guard and a delete: the guard `""` — 412 with its version, a guard by its version holds; a delete with `cas: ""` — 409 with its version, with `cas` by it — deleted (coverage audit P/01, second pass, G05) | P/01.1 N2 |
| 23 | service doors: an extra field in `join`, `leave` and `op: floor` — 400, `floor` is not written; an `id` not in the member form in `join` and `leave` — 400 (G06) | N2 |
| 24 | a wrong method at `/metrics`, `/v1/join`, `/v1/leave` — 405 (G06) | N2, N4 |
| 25 | `/v1/status` of a door without a vote — `state` `Door`, `role` `door`, `term`, `commit`, `applied` — 0 (G06) | N2 `GET /v1/status`, N1.3 `door` |
| 26 | the role `configstore-door`: its own row with `cas`, with an extra element of `items`, and its delete — 403, its own row in form — 200 (G06) | N1.3 `door` |
| 27 | `import` into a fresh group where a live door has already written its row passes; `-index-base` below the greatest version of the copy — a refusal, nothing is transferred (G06; C01-IMPORT-DOOR-ROWS-01) | N1.3 `import`, N4 |
| 28 | `recover -peers` without its own `-id`, without the `api` address, with a repeated `id` — a refusal; `-upper` above the computed one raises the floor: `100001 << 32` (G06) | N1.3 «Daemon flags» `-peers`, `-upper`, N4 |
| 30 | a batch and a restart: the rows written and deleted by a batch read after `@restart store` with one version; a replay by `id` after the restart — `again`, not a single extra write (ADR-0094 B9) | N1.3 `batch`; P/01.1 N3 «write batch» |
| 31 | a batch in a group: a door without a vote forwards it whole; the rows read on followers with one version, a replay by `id` through a voter and through the door — `again`; a stale `cas` — nothing is written; the role `configstore-door` does not write a batch — 403; after the death of the leader the batch is intact (ADR-0094 B9) | N1.3 `batch`, `door`; P/01.1 N3 «write batch» |
| 29 | `import` of a copy whose floor has `generation_at` later than the clock (2100) — a refusal without `-force`, nothing is transferred; with `-force` — transferred (coverage audit P/01, second pass) | N1.3 `floor` `when`, «Daemon flags» `-force`, N4 |

The inputs of sc. 11–12 are `inputs/*.jsonl` (JSON Lines copies in the form of N1.3 `copy`). A copy of one implementation restored by another is the compatibility matrix of ADR-0083 item 5 on the same directives, outside the acceptance of one implementation.

`recover` — sc. 18 (the group stand; formerly the drill sc. 06 of the [system acceptance](../../common/acceptance/system/README.md)), step 9 of sc. 15 (`door.pass`) — step 1 of sc. 15 of the [acceptance of chapter 6.5](../../06-console/acceptance/5/README.md): they need writers and the issue of epochs (P/03.2) and the console.

---

## Implementation decides

Each implementation names in its description:

1. **the raft transport secret** beyond mTLS, if there is one, and its rotation on revocation; the raft wire between members and the frame of `admin.sock`
   (read-fence, admit, import) are internal to the implementation: a format with a name and a version, no new HTTP routes; the members of one
   store cluster are one implementation, a mix of languages — only by clients through `configstore:///` (guess of stage C CL-01,
   ADR-0087 addendum (12) item 7);
2. **the durability of the store** (fsync, raft snapshots: threshold, interval, tail) — a teaching store MAY be non-durable, and this is said in its description (ADR-0070 item 4); a stand flag that turns the barriers off is in the «Stand» command, not in the environment (N1.3 `durability`);
3. **the connection accounting of the daemon** and overrides of the limits by deployment, `-tuning` for slow networks; the normative defaults are N1.3;
4. **how `backup` obtains a consistent state of a running daemon** (N2); the requirement on the copy is a norm of N2, not a choice.
5. **the format mark and the profile `file://`**: the values `format` and `version` of its mark `FORMAT` and which versions of its format the build reads (N1.3 `format`); the on-disk format of the profile `file://`; the command by which a copy of N1.3 `copy` is taken from a store `file://` (the form of the copy is a norm) (the store pilot, A1, A2, A9).
6. **mutual exclusion of runs** of `recover`, `restore`, `import` on one installation (a lock, a mark file) — the norm requires one attempt (N3 «Races: admittance and recovery transitions»), the way is a choice (guess of stage C S02).
7. **the internal contract of `file://`** (item 5): the format of the profile `file://` is the implementation's own, not a public contract. Its description
   and the library API are written in the implementation's repository by the owner of this chapter before the code: the physical layer and the command layer — conditional
   `put`/`delete` with `guard`, the batch `batch`, CAS by version, `not_before`/`not_after`, outcomes and refusal words as at the store door (P/01.1 N1,
   N4; without retelling the norms), with vectors from its own code. Other processes of the implementation (the installer, the worker) read only
   the contract and the API; a mix of languages on `file://` is not supported — through `configstore:///` (guesses of stage C W03-E01a,
   W03-SDK-FILE-COMMAND-01, ADR-0087 addendum (12) item 7).

---

## Readiness checklist

An implementation conforms to the chapter when every norm holds; the norm id `P/01.3-MM` is what decision deltas, findings and window records refer to (ADR-0080 addendum 6):

- [ ] **P/01.3-01** the daemon: the flags of N1.3, the store of a box without raft (`box`) — sc. 04 and by reading, `members` without `-api` — `{}` (sc. 16), start refusals, sizes 1/3/5, joining and `-force`, `leave`/`admit`, the effective `-leader-wait` interval — sc. 07, 17 (the group stand); mTLS, sockets — by reading; the 503 branch «no leader for the effective `-leader-wait` interval» — sc. 17; ambiguous and unavailable with Retry-After at the connection limit — by reading N1.3/N4: the scenarios do not saturate connections and do not cut the leader's answer
- [ ] **P/01.3-02** a door without a vote: without raft, the same rights, forwarding, the row `seen_at` by the own write of the role `configstore-door` (only this row), 503 without voters — sc. 07, 17 (the group stand); the door is not part of the quorum — sc. 17; `/v1/status` of the door (`role`, `term`, `commit`, `applied`) — sc. 25; its own row only by `put` without `cas` with one `seen_at`, a delete — 403 — sc. 26; an unreadable door row outside `configstore_doors` — by reading: the TSV request does not carry a fresh `seen_at`, and with an old `seen_at` a step will not tell an unreadable row from one that the implementation does not count by age (acceptance README)
- [ ] **P/01.3-03** the epoch floor: upper and the generation formula by the clock with the example of N1.3, the replay memory of `floor` in the store, only upwards, only admin, `recover`/`restore`/`import` raise it before the first row — sc. 18 (the group stand; formerly drill 06 of the [system acceptance](../../common/acceptance/system/README.md)); the replay memory of `floor` after a restart, only upwards (the same and a smaller floor with a new id — 409), only admin (a role socket — 403) — sc. 08; `recover` without `-isolated` and with `-upper` below the computed one — a refusal before changes, `-upper` only raises upper — sc. 18 and by reading the CLI test of the implementation (guess of stage C S02); `-upper` above the computed one raises the floor, `-peers` out of form, without its own `-id`, with a repeat — a refusal — sc. 28; a clock earlier than `generation_at` of the floor of the input — a refusal without `-force` — sc. 12 steps 31–32, with `-force` — sc. 29
- [ ] **P/01.3-04** `import`/`restore`: a fresh group, an immutable input, the base ≥ the greatest; a wrong input without changes, after the floor a partial transfer is possible, a replay of the same attempt — by reading; the reason — TSV does not reproduce the error of each row and the partial restoration after the floor; a fresh group with a door row and a base below the greatest version — sc. 27; a row key not by N1 and `generation_at` of the floor not a time — sc. 12 steps 27–30
- [ ] **P/01.3-05** the daemon metrics of N1.3 — sc. 04 (two series); the series `_state`, `_elections_total`, `_index`, `_last_contact_seconds`, `_voters`, `_voters_expected` of the leader and a follower — sc. 17; the three alarms — checked by reading: the metrics test of the implementation (the subject — the list of N1.3); `configstore_doors` — the number of rows `platform/configstore-doors/<id>` that read in their own form, with `seen_at` not older than `DOOR_SEEN_PERIODS × DOOR_SEEN_EVERY` — at a voter by its own replica and its own clock, a door without a vote has no series (C01-DOORS-COUNT-FRESH-01, C01-DOORS-COUNT-PLACE-01) — sc. 07 (the group stand) (the Architect's decision on the tails of the move of lesson 1)
- [ ] **P/01.3-06** the mark `FORMAT`: a start refusal with code 2 on a foreign and on a non-empty unmarked directory, without changes — sc. 10; the first write of the mark into an empty directory, a start on its own one — sc. 08 step 2 (`@restart store`); the copy `copy` — one form for `backup` and `import`, a refusal of the input as a whole — sc. 11, 12; `restore` with the same form and a copy of another implementation — by reading and the matrix of ADR-0083 item 5; the daemon flags — a closed table, `-dir` and `-id` in a group are required, flat sockets, inherited by `FileDescriptorName` — by reading: the units and flags test of the implementation (the store pilot)
- [ ] **P/01.3-07** service doors (reconciliation of python and go M10/6–11): the order «frame → route → identity → body», 413 earlier than 405, `join`/`leave` from a role socket — 403, empty `raft`/`api` — 400, `HEAD` — 405/404 — sc. 15; extra fields of `join`, `leave`, `op: floor` and a member `id` out of form — 400 — sc. 23; 405 at `/metrics`, `/v1/join`, `/v1/leave` — sc. 24; the floor is a JSON integer < 2^53: a float notation and the greatest uint64 — 400, 2^53 − 2^32 is admissible — sc. 08 steps 10–12 (review of stage B 1–2, item 8); the replay memory is not in the copy — sc. 14; `-max-value` > 0 — by reading: the flags test of the implementation (the stand does not set daemon flags)
- [ ] **P/01.3-08** the life cycle (reconciliation of python and go M10/6–11): the `backup` target outside `-dir` — sc. 11 step 11 (`@backup store … in-data`); a repeat of a finished `import` — code ≠ 0, `recover` on a box — code 2 (N4) — by reading: the store CLI test of the implementation (the directives `@backup`/`@import` write the runner's file and each time a fresh directory, they do not give these cases)
- [ ] **P/01.3-09** verification of the TLS peer by the daemon of N1.6: CN and SAN, one role `configstore` or `configstore-door`, the signature algorithms of the chain, trust of `ca.pem` and `ca.next.pem`, revocation by content without a restart — checked by reading: the tests of the implementation on a test CA (the subject — N1.6: without a certificate, a foreign CA, a revoked one, a foreign role, its own); the reason — the CA and file rights are not changed by HTTP-TSV
- [ ] **P/01.3-10** the admission time in the log record and the snapshot, continuation from the snapshot, `admission_ahead` in `/v1/status` of the leader beyond `CLOCK_SKEW` (N1.3 `admission`) — checked by reading: the stand does not move the leader's clock and does not take a snapshot on demand
- [ ] **P/01.3-11** a batch: one log record, application on all servers whole, forwarding by a door without a vote in one request, the role `configstore-door` does not write a batch — sc. 31 (the group stand); a restart and a replay by `id` — sc. 30; a power cut in the middle of a batch — by reading (P/01.1-31)

## REMOVED

(none)

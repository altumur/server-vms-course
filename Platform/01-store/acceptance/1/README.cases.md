# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/1/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

A change of `key`, `cas`, `guard`, `not_after` and `not_before` on a replay of `delete` is now scenario 30 (below).

### Original passage 2

## Coverage audit of P/01, second pass (sc. 30–32)

The coverage audit session, second pass (Gemini, 2026-10-30, commit 6a5817f88, `coverage audit Gemini P01 (for people)`, G01–G03):
- Sc. 30 — the replay fingerprint by value (N3 «write», «delete»): for `put` a reversed order of the fields of `items` and an absent
  `cas` instead of `cas: null` give the same fingerprint (`again`); `delete` under the `id` of a `put` write — 400. For `delete` under one `id`
  (`cas`, `guard`, `not_before`, `not_after`): `items` as an array and `1.0` instead of `1` — `again`; a different `key`, `cas` `""` and no
  `cas`, a different key and version of the guard and no guard, a different `not_after` and `not_before` — 400; `put` under this `id` — 400; the row is
  deleted once.
- Sc. 31 — steps 1–4: deleting an absent row with `cas: ""` — 200 and a new version, the row is still `null, ""`,
  creation with `cas: ""` after it passes (N3 «delete», «Races»); steps 5–7: a replay of a write for which by the time of the replay both
  `cas` and the guard are violated — its answer with `again` (the `id` memory before the guard and CAS); steps 8–13: after the refusals `early`, `guard` and
  `conflict`, the same write with the same `id` and a corrected condition — a new write without `again` (N3: a refusal does not occupy the `id`).
- Sc. 32 — the order of the checks of a command of N2.1 on pairs of violations; each pair tells adjacent steps apart by the kind of refusal: `op`
  before the key; the socket of `floor` before the form of `floor` and `id`; the form of the key before the guard; the rules of the key before `items`;
  `items` and `cas` before the guard (`badrequest`, not `badkey`); `id` and `not_after` before the weight and the rights (`400`, not `413` and not
  `403`); `id: null` and `not_after: 1e400` (not finite in binary64) — 400; a lone surrogate in `guard.key` — `badkey`, in a
  value of `items` — `badrequest`. Steps 13–14 see that nothing is written either under `acc/` or under `other/`.

### Original passage 3

## Batch (sc. 33–40; ADR-0094 B9)

- Sc. 33 — all or nothing: step 6 — the `cas` of the second row is stale, steps 7–8 see both rows as before; steps 4 and 10 — one version for all rows.
- Sc. 34 — creation, edit and removal in one batch; step 7 — delete of an absent row; steps 10, 12 — `items` of delete is not read; step 11 — the `cas` of the removed row is stale.
- Sc. 35 — guards: step 3 — the guard is not written; step 7 — the guard before `cas`; steps 8–9 and 10–11 — the first violation in the order of `guards` and `writes`.
- Sc. 36 — the fingerprint: steps 2–4 — the order of `guards` and of the fields of `items`, `cas: null` give the same; steps 5–9 — a different one; steps 10–12 — the memory is shared with the write; step 14 — the memory before the guard;
  steps 15–16 — a refusal does not occupy the `id`; steps 17–21 — `items` of delete is not included, `cas` is.
- Sc. 37 — deadlines: steps 5–6 — before the guards and `cas`, steps 7–8 — a refusal does not occupy the `id`.
- Sc. 38 — the form; steps 26–30 — the order of the checks of N2.1 on pairs of violations; steps 31–32 — one over the limit, steps 35–36 — exactly at the limit; step 37 — extra top-level fields, among them the fields of a single write, are not read.
- Sc. 39 — the weight: two rows of 400000 bytes each are together heavier than the ceiling, each is lighter; a row heavier than the ceiling — 413 with its `key`. The weight of `@big`: the field name plus the value.
- Sc. 40 — rights: 403 before deadlines (step 5), a refusal does not occupy the `id` (steps 6, 8).

The role `console` does not know the limit on the number of rows — sc. 16 of chapter 1.2. Restart and the group — sc. 30, 31 of chapter 1.3. The refusal of a body over the limit is a common refusal before JSON parsing, sc. 22.

### Original passage 4

- For a `200` answer to `GET /v1/list` the **order of names inside `keys`** is also checked: the sequence of names decoded from the JSON in the order received MUST equal the sequence in `expect`, which is given by UTF-8 bytes. The runner keeps this order when parsing the answer and does not sort what it received before the comparison. For example, in sc. 08 step 4 an answer with `b` before `a` is a mismatch, although the values match. For an empty `keys` the sequence is empty. Spaces and the way of JSON escaping are insignificant; the order of other objects, `items` included, is still not checked.

### Original passage 5

- Only for the body refusal in sc. 22 step 1 the optional field `size` is admitted: if it is present, it is the integer
  JSON number 4194364 (the full size of the sent body), not a string and not a boolean. After it is checked it

### Original passage 6

  `key` included, are not admitted (the common rule of `error` is kept). For the weight refusal in sc. 15 the fields `key` and `size`

### Original passage 7

Scenario 28 takes only the edges of the admission time: `not_after` = 1 (1970) has already passed, `not_after` and `not_before` =
4102444800 (2100) have not yet come under any clock of the stand. Steps 2–4 — `expired` and `early` write nothing; steps 5–7 —
the order «time conditions → guard → CAS»; steps 8–11 — `not_after` in the replay fingerprint (`4102444800.0` equals `4102444800`
by value, a different number and absence — `400`); steps 12–13 — the refusal `expired` does not occupy the `id`; steps 15–19 — forms
(a string, a negative, `null`, `bool` — `badrequest`; the form of the guard before `not_after` — `badkey`). The equality boundary and

### Original passage 8

Scenario 17 step 5 — `op: floor` on a role socket: `403 forbidden` before parsing the key. Scenario 20 steps 10–11 —
the form of the guard before the rules of the key: `{key: "/x", index: "x"}` and `guard: null` — `badrequest`. Scenario 25 checks the query: `+` is a space (step 3 reads the row `a b`), `%2B` is a plus (step 4), `+` in `prefix`
is a space too (step 5), a repeated parameter — `badrequest`, bytes not UTF-8 — `badkey`, `%` without digits stays
a letter of the key and does not find the row. Scenario 26 — strict JSON of the body: a repeated field name at the top level
and in `items`, `NaN` in an extra field, a lone surrogate in a key and in `items`; step 6 sees that nothing is written,
steps 7–8 that a surrogate in an extra field is not read. Scenario 27 — an unknown method and a known path
with a method that is not its own: `404` with `Fault`, not 405 or 501; the paths `/v1/%67et`, `/v1/get/` and `//v1/get` are not decoded and not
normalized — also `404`. Steps 10–12 of scenario 25 — the order of the query checks: empty pairs are skipped, `?key` is an empty
key (`badkey`), a repeat before UTF-8 (`badrequest`).

### Original passage 9

The original six seam scenarios and all 73 steps remain byte-exact. Added six scenarios use only the existing HTTP, @clock and @reopen grammar. s7 and s8 check the four admitted refusals expired, early, guard and conflict for single writes and batches: advance the clock, refuse, immediately move the clock back, read the unchanged rows/list, then admit a probe above the old clock but below the refused record's admitted time. The refused identifier is then reused with a corrected condition. Zero business effects therefore coexist with retained admission metadata. s9 repeats this distinction across ordinary Close/Open for a single expired write and a guarded batch; it is a graceful restart witness, not a power-cut or consensus witness.

### Original passage 10

s10 keeps the initial clock at 2000000000. The valid raw bound 1999999999.99999999 is lower as an exact decimal rational but equals that clock in binary64: not_after admits equality, not_before refuses it, for put/delete/batch. s11 changes both bound spellings on applied put/delete/batch replays: 9007199254740992 and 9007199254740993 round to the same binary64, as do 1.00000000000000001 and 1.0. The next representable values 9007199254740994 and 1.0000000000000002 give different fingerprints and badrequest. The request bytes must not be normalized before the actual store parses them. The CALL engine's exact-number comparison is not a replacement store fingerprint. s12 distinguishes the nonempty string version "0" from the absent marker "" in single/batch CAS and guards.

### Original passage 11

s13–s15 use put/delete/batch with the former id: clock +100, successful replay, immediately −100, then a not_after probe between the former and replay admission times gives expired. A second +200/replay/−200/ordinary reopen/probe sequence checks durability. There is no read between replay and rollback/reopen/probe that could mask lost admission metadata. The original answers and versions remain, the probe row is absent, and a deleted row has no visible version. All three cases are gated by durable because they include @reopen; former steps and store_core gates are unchanged. These are source witnesses, not executed SUT acceptance.

### Original passage 12

The complete previous 15 seam scenarios / 239 steps remain byte-exact. s16–s18 add put/delete/batch with an already-applied identifier and different content: clock +100, mismatch gives badrequest, immediate -100, then a not_after probe gives expired. A second +200/mismatch/-200/ordinary reopen/probe sequence checks durable last admission metadata. No read between mismatch and rollback/reopen/probe can mask lost metadata. The original rows/visible absence and first id answer remain; an original-command replay still returns that answer with again. The mismatch does not replace or free the original applied-id entry. These are admitted refusals, distinct from form/rights/framing refusals before admission. In s16 an earlier invalid-items request with the same id is rejected before admission at clock+50; after rollback a bound-between-clocks probe succeeds. This negative control prevents treating every badrequest as admitted.

### Original passage 13

s19 starts at the existing clock2000000000. +0.0000001 is converted to the same binary64 value before max, so not_before2000000000 gives early. After a further +0.0003999, a bound2000000000.0002 passes. Roll back0.0004, reopen, and apply the same bound to another row: it still passes because the assigned fractional binary64 admission value survived. No integer/millisecond or three-digit row-time writer may truncate it. The witness does not prescribe a metadata encoding or physical clock accuracy.

### Original passage 14

- raw `\x00`, `\x01`, TAB, `\x7f` and `#` in the request target — `400` (`%00` — sc. 25, `200`);

### Original passage 15

go from the indicated role with rights on `acc/`, except the steps through the door `admin`. Scenario 21 does not receive additional rights on `other/`: its step 1
writes the row `other/21-rights/c9` `{n: "1"}` through the door `admin` (`admin.sock` of the instance, `{socket}` of «Stand») and binds its version `$v`; step 7 sees its name
and the same version without the value, although the role has no read rights on `other/` (N3 «list»). In sc. 24 step 7 — the query of a `POST` is not
read, step 8 — the body of a `GET` is not read; in sc. 26 steps 9–10 — `Infinity` and a BOM in the body (N2.1).

### Original passage 16

An additional check of the full key (R29-01, P/01.1-16,22): on a separate instance
with rights on acc/ check the keys of this prefix with the full length of 200, 201, 213, 1024 and 1025
UTF-8 bytes, including Cyrillic and four-byte characters. The first four pass the door rule,
1025 gives 400 badkey without a write; check the same set in a non-empty guard.key. For an existing
guard use its actual version, for an absent one — index="", so as not to fall
into the version comparison refusal. For a file implementation separately check its declared limit:
an earlier badkey is admissible, but the threshold 200 by itself is not a norm of the platform.
This is a separate harness beyond the scenario TSV; test the full UTF-8 representation, not the number of characters.

### Original passage 17

The runner checks both values before the scenarios by behaviour on a probe instance obtained in the same
way: a body of exactly 1048576 bytes reaches the JSON parsing (the answer is not `413`), 1048577 bytes — `413 toolarge`
with `limit` 1048576; a weight of `items` of exactly 524288 bytes is written, 524289 — `413 toolarge` with `limit` 524288.

### Original passage 18

Scenario 15 after the expansion of `@big` sends bodies of 524348 and 524344 bytes: both are smaller than the body limit,
but the weight of `items` is 524292 and 524288 bytes. So exactly the row ceiling is checked.
Scenario 22 sends a body of 4194364 bytes, more than 1048576: the refusal arises before the JSON parsing and the weight check.

# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/3/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

## Reconciliation of python and go M10/6–11 (sc. 08 steps 10–12, sc. 14, 15)

- Sc. 08 steps 10–12: `floor` that is not an integer JSON (`2.0e1`) — 400 before the write, not 409 «only upwards»; the largest uint64 is
  out of the floor form and gives 400; the upper bound of N1.3 floor `form` itself is admissible (B5).
- Sc. 14: the `id` replay memory is not part of the copy (N1.3 `copy`). A write with `id` `b1` on the stand store, a copy, a transfer:
  a replay of the same `id` at the transferred store — a new write without `again`, the next replay — `again` (B10). The key `other/b10` is
  outside the stand families; `admin` writes it.
- Sc. 15: service doors (N2). Steps 1–2 — `@as console`: `join` and `leave` from a role socket — 403 before the membership (B1); steps
  3–4 — the body `@big(1048577)` is larger than the 1 MiB limit — 413, for `PUT /v1/status` before 405 (framing → route, B2, B3); step 6 —
  empty `raft`/`api` — 400 (B4); steps 7–8 — `HEAD`. Step 9 of sc. 15 (`door.pass` `testsub2` without a worker with a door — 503,
  B26) was moved to step 1 of sc. 15 of [the acceptance of chapter 6.5](../../../06-console/acceptance/5/README.md): it needs the console.

### Original passage 2

The store copy (chapter 1.3 N1.3 `copy`; the store pilot, A2). The inputs are `inputs/*.jsonl`, JSON Lines: `copy-ok.jsonl` — a header
with `index` `"7"` and the rows `platform/epoch_floor` `{floor: "4294967296", generation_at: "1760745600.5"}` (the time form —
P/03.2 N1.5), `testsub/counters/1` `{n: "1"}`, `testsub/next_id` `{n: "2"}` in ascending order of the key;
there are no manifest rows (`platform/manifest/*`) in the input: the copy does not know manifests, `import` carries a row of any family (chapter 1.3 N1.3
`import`; the log of cammeta-go, lesson 11 № 10) — sc. 11 steps 1–3; `copy-ok-unordered.jsonl` — the unit rows in reverse order, without the floor row (the reader does not require an order). `bad-*.jsonl` — one
`copy` refusal per file; a correct row `testsub/next_id` stands in each of them before the spoiled one, so the step `restored` after the refusal sees that
nothing is transferred: there is no row (`items: null`, `index: ""`).

### Original passage 3

| File | Refusal |
|---|---|
| `bad-format.jsonl` | `format` of the header is not `w2c-configstore-copy` |
| `bad-version.jsonl` | `version` 2 |
| `bad-header-extra.jsonl` | an extra field of the header |
| `bad-no-header.jsonl` | the first line is not a header |
| `bad-row-extra.jsonl` | an extra field of a row |
| `bad-row-missing.jsonl` | a row has no `index` |
| `bad-not-json.jsonl` | a line is not JSON |
| `bad-not-row.jsonl` | a value of `items` is a number, not a string (not a Row) |
| `bad-repeat-key.jsonl` | a key twice |
| `bad-index-above.jsonl` | the `index` of a row is above the `index` of the header |
| `bad-unreadable.jsonl` | a row `unreadable` |
| `bad-epoch.jsonl` | the epoch row `testsub/epoch/u1` with a non-decimal `epoch` — upper is not reliable (sc. 12 steps 23–24) |
| `bad-floor.jsonl` | the floor row with a non-decimal `floor` `12.5` (sc. 12 steps 25–26) |
| `bad-row-key.jsonl` | the row key `testsub/../bad` — a segment `..`, not a key of chapter 1.1 N1 (sc. 12 steps 27–28) |
| `bad-floor-gen-at.jsonl` | the floor row with `generation_at` `not-a-time` — not a time, the floor row is unreadable (sc. 12 steps 29–30) |
| `copy-future-floor.jsonl` | a correct copy, the floor has `generation_at` `4102444800` (2100) — the stand clock is earlier, a refusal without `-force` (sc. 12 steps 31–32; with `-force` — sc. 29) |

### Original passage 4

Sc. 11 step 4 sees the floor `platform/epoch_floor` after `import`: the input floor is used only for the upper and generation_at checks and is not transferred; `import` raises a new floor above
the upper of the input before transferring the other rows (N1.3 `floor`); the number depends on the clock, the step does not fix it. Steps 7–10 — the copy `backup` of the stand store, transferred into a fresh directory, carries the manifest rows `testsub` and
`testsub2`. The writer side of the rule «Time in a row» (N0 of chapter 1.1): sc. 11 step 4 — the floor after `import`, `generation_at`

### Original passage 5

change. The leader after `-bootstrap` and the joins is `s1` (step 5 of each scenario checks this as well). The assembly 1→2→3: the second member joins with `-force` (a group of two is a transitional parity, P/01.3 N1.3 `join`), the third without it (C01-GROUP-BOOTSTRAP-EVEN-01). The box store build

### Original passage 6

- **Sc. 31 — a batch in the group (ADR-0094 B9).** The role `console`; the door `d1` forwards the batch whole: steps 8–10 read both rows on the followers with one
  version, steps 11–12 — a replay by `id` through a voter and through the door, step 13 — a stale `cas` of the second row, step 14 sees that the first one is not written.
  Step 15 — the probe `inputs/door-row-batch.json`: the door's own row by a batch — 403 (N1.3 `door`). Steps 16–18 — `@sigkill` of the leader: the new leader gives both rows.
- **Sc. 07 — size and the door without a vote.** A group of three; the join of a fourth — 409 `refused` both without `force` and with
  `force` (`-force` does not take beyond the declared size; N1.3 `join`). The door `d1` (`-door -voters`): `state` `Door`, a write
  through it — by the same rights file (forwarding to the leader, visible at the follower `s2`), the row `platform/configstore-doors/d1` with
  `seen_at` not later than 40 s (every 30 s), the metrics row `configstore_doors 1` at the leader. The door `d2` with the leaf `d1` — a start refusal
  (`-id` is not the server of its leaf, C01-DOOR-ID-CN-01). The probes `door-row-*` (`inputs/`): the leaf of the door `d1` writes at the leader a foreign
  row `platform/configstore-doors/d2` — 403, its own — 200 (`P-4`; N1.3 `door` «own»); the role forwarding header in the probe is
  a designation, the name is from the implementation description, as in the acceptance of chapter 1.2 sc. 08.
- **Sc. 17 — membership, restart, leader change, quorum.** Size 2 and 4 — a start refusal; `leave` of the stopped `s3`, its
  `join` before `admit` — 403, `admit` is repeatable (code 0), after it `join` with the same address — 200, with another Raft address — 409,
  `leave` of an unknown member — 409 (N1.3 `leave`, `repeat`); `s3` restarts and is a follower again.
  `P-1`: three writes without `cas` through different members, a restart of a follower, then of the whole group — each has the same version `$r3`,
  and a write with `cas` `$r3` through a follower passes (the log is not applied again; the versions are the same at all members). `P-2`: a write, `@sigkill` of the leader — a read at both
  remaining members right after the election sees its version `$w`, the returned `s1` too (the read is linearizable, P/01.1 N3). `P-3`: the door `d1` and one voter `s1` without the two others — a write through the door and
  through `s1` — 503 `unavailable` after the effective `-leader-wait` interval (`@sleep 6` — the deadline of the norm): the door is not part of the quorum.
- **Sc. 18 — `import` into a group and `recover`.** `import` of the copy `copy-ok.jsonl` (`index` 7) with `-index-base 7` into a fresh
  group at the leader; a repeat of a completed one — a refusal (N1.3 `admin_ops`, B12). `P-5`: the transferred rows keep the versions of the copy — `testsub/next_id` `3`, `testsub/counters/1` `5`, and `cas` by them passes (P/01.3 N1.3 `import`, N3 «the copy is replayed into exactly those rows and versions»; C01-IMPORT-VERSIONS-01): an implementation that rewrites the transfer by ordinary `put` with new small versions fails here. That the new versions after the transfer are above `-index-base`, the scenario does not judge by numbers (the strings are compared only by `==`/`!=`) — by reading. The epoch row
  `testsub/epoch/u1` `429496729600005` (100000 << 32 | 5); the majority is lost (`s2`, `s3` killed, `s1` stopped);
  `recover` without `-isolated` and with `-upper` below the computed one — a refusal before any changes; with `-isolated` — the floor
  `100001 << 32 = 429501024567296` (the generation is the upper of the epoch row; the hours since 2026-01-01 are fewer than 100001), the rows and the epoch
  are kept (`P-6`: upper is from all epoch rows). The former `s2`, `s3` with old directories do not return (N3 step 0);
  the new `s4` (`-force` — transitional parity) and `s5` join from empty directories; the floor is visible at the new follower.
- **`P-3`, a door leaf on `-raft`** (C01-RAFT-DOOR-LEAF-01, the Architect's decision of 2026-10-30): sc. 07, the last step —
  the probe `inputs/door-on-raft.json`: the leaf of the door `d1` on the raft port of `s1` — `handshake: alert` (P/01.3 N1.6 `raft`).
- **Coverage audit of P/01** (audit-kimi 2026-10-30, commit 399e4783b): sc. 07 — the probe `inputs/forwarded-admin.json`: the leaf
  of the voter `s2` with the role forwarding header `admin` at the leader with a loaded rights file — 403 (P/01.2 N3, A08); sc. 17
  steps 6–7 — the `/metrics` rows of the leader and of a follower (the names of N1.3 `metrics`, the state in lowercase per ADR-0070, the number of votes 3;
  the substring «3» admits the notation «3.0»; A10); sc. 17 — `@cut store@s3` (a proxy on the raft port of the member cuts incoming
  connections; the outgoing connections of the member go directly): after a write through `s1` a read at `s3` — the new version or 503, not the earlier one
  (`P-2`), after `@mend` — the new one (NEW-DIRECTIVES § 3; the steps do not assume who the leader is).
- **Coverage audit of P/01, second pass** (Gemini 2026-10-30, commit 6a5817f88, G06; the group assembly — steps 1–5, as in
  sc. 07): sc. 25 — `/v1/status` of the door `d1` whole by N2: `Door`, `role` `door`, `term`, `commit`, `applied` — 0;
  sc. 26 — probes of the leaf `d1` at the leader: its own row with `cas: ""` (`inputs/door-row-with-cas.json`), with an extra element
  `extra` (`door-row-extra-item.json`) and its deletion (`door-row-delete.json`) — 403, its own row by the form — 200 (N1.3 `door`:
  only `put` without `cas` and `guard`, the single `seen_at`); sc. 27 — a live door has written its row (`@until 40`),
  `import` of the copy `copy-ok.jsonl` with `-index-base 4` (below the versions 5 and 6 of the copy) — a refusal, no rows; with `-index-base 7` —
  transferred, the version of the copy is kept (C01-IMPORT-DOOR-ROWS-01: a door row does not cancel freshness); sc. 28 — the majority
  is lost, `recover -peers` without its own `s1`, without an `api` address, with a repeat of `s1` — a refusal; `-upper 429496729700000`
  (`429496729700000 >> 32` = 100000) above the computed one (there are no epoch and floor rows, upper 0) — the floor `100001 << 32 =
  429501024567296`; sc. 29 — `import` of `copy-future-floor.jsonl` (the `generation_at` of the floor of the input is 2100) without `-force` — a refusal,
  nothing is transferred, with `-force` — transferred, the floor is raised (N1.3 `floor` `when`, «Daemon flags» `-force`).

### Original passage 7

- Sc. 12 steps 23–26 (A07): `import` of an input with the epoch row `testsub/epoch/u1` `{"epoch": "abc"}` (`inputs/bad-epoch.jsonl`) and
  with the floor row `{"floor": "12.5"}` (`inputs/bad-floor.jsonl`) — upper is not reliable, a refusal of the whole input, nothing is
  transferred (N1.3 `import`, V7 item 3).
- Sc. 19 (A01): the version after a restart of the daemon on the same directory — the earlier row with the earlier version, the new versions
  differ from it (P/01.1 N1 `index`); a non-durable training store does not run sc. 19, as with sc. 08.
- Sc. 20 (A05): `@spoil row` / `@spoil row-index` (common README) — spoiling bypassing the door by the profile command `spoil-row`

### Original passage 8

- Sc. 21 (A02): the `id` replay memory (P/01.1 N3) is held for no less than two minutes — a replay after `@sleep 121` (the deadline of the norm
  with a margin) gives the earlier `index` and `again`; the right to forget after 2 min and 50 000 writes — by reading. Here and not in chapter 1.1:
  its directive format does not carry this.
- The second pass of the coverage audit (Gemini, G05, G06): sc. 12 steps 27–32 — a row key with `..`, the `generation_at` of the floor not
  a time, the stand clock earlier than the `generation_at` of the floor of the input (without `-force` of the directive `@import store`) — a refusal of the whole input
  (N1.3 `import`, `floor`; the outcomes of the family `epoch_floor`). Sc. 22 — a damaged row exists for a guard and for a deletion
  (P/01.1 N2): the guard `""` — 412 with its version, by the version — holds; deletion with `cas: ""` — 409, with `cas` by the version — the row
  is gone; without the profile command `spoil-row` — not_executed. Sc. 23 — service doors (N2): an extra field in `join`, `leave` and
  `op: floor` and the member `id` `_bad` — 400; step 6 — a new floor with another `id` passes, so the floor of step 5 is not written
  (otherwise — 409 `refused`). Sc. 24 — 405 for `POST /metrics`, `GET /v1/join`, `GET /v1/leave` (N4).

### Original passage 9

In total 24 scenarios / 292 steps, all automatic (sc. 07 — 18 steps, sc. 17 — 53, sc. 18 — 28; formerly sc. 07 was one step `@manual`; sc. 12 steps 23–26, 19, 20, 21 — the coverage audit of P/01; sc. 12 steps 27–32, 22–29 — its second pass, of them 25–29 on the group stand); sc. 15 — steps 1–8 (step 9 is in the acceptance of chapter 6.5, there it is step 1 of sc. 15); sc. 16 — 1 step. 08/6–9 — the floor only upwards, only admin (mutation check 7cecaf2 № 46, 47). Sc. 08: the replay memory of `op: floor` is in the store

### Original passage 10

The `bad-unreadable.jsonl` input below witnesses import refusal, not permission to omit a damaged row from backup.

The inputs are `inputs/*.jsonl`, JSON Lines: `copy-ok.jsonl` — a correct copy;

`copy-ok-unordered.jsonl` — the rows out of order (the reader does not require an order). `bad-*.jsonl` — one
`copy` refusal per file; nothing is transferred on a refusal.

### Original passage 11

Scenario16 step1 also checks required `max_body: 1048576` and the unchanged `max_value: 524288` on its default stand. Repeat the ordinary status GET on a fresh store configured through the existing `-max-body 2097152` and `-max-value 524288`: max_body is2097152, max_value stays524288. This is an actual daemon/HTTP obligation; the source/schema audit does not execute that repeat. Do not add acceptance.yaml keys or guess the limits from defaults.

## Deterministic syscall cases

- **37-recover-crash (K01).** After two confirmed rows, cut off the former majority and stop the remaining daemon. Sweep successful `rename,fsync,write` calls of local `recover`, K = 64, then repeat recover with the same peer input and restart only the recovered member. Both rows retain their exact versions; `state` is `Leader`, `leader_id` is the surviving id and `leader` its nonempty API address. A subsequent write has a different version. Expectations come from P/01.3-R021, R022, R265, R266, R267, R398 and P/01.1-R019; the case does not name an implementation's phase-mark file or use a candidate verdict. The sweep includes the first changing operation and the result barriers; its bounded trace is evidence of which points it actually covers. Old cut-off members never return.
- **38-checkpoint-eio-enospc and 39-checkpoint-enospc-eio (K02).** Keep one confirmed row, inject the first error at every reachable `fsync,write` ordinal of forced saving (K = 16), confirm a distinct second row, then inject the other error at every reachable ordinal of the next forced saving (K = 16). The two sweeps form a product, so publication followed by a later failed save is included. With `stand.checkpoint: none` each trigger is the supplied ordinary write with an id; 200, 503 `ambiguous` or 503 `unavailable` is judged by its full existing response form. These fallback rows are separate from the two confirmed control rows. After faults are removed, kill the daemon, restart, read both exact control rows/versions, replay the second id with `again`, and issue a new version distinct from both. A further restart retains that new row/version. Expectations come from P/01.1-R084 (versions), R078 (id replay), R144 (failures), R295 (whole durable batch/id), R296 (barrier recovery and later writes), and its Implementation decides item 3 (durability barriers). The test does not mandate a checkpoint algorithm or a runtime threshold. K is a finite test bound, not a storage limit; actual traces and any tail beyond K remain in evidence.

The shared directive's observer controls are required; an unproved fault cannot turn a storage refusal or missing row into success. Scenario 36 remains the separate corruption/restart case (K03).

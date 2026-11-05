# Acceptance P/01.3 — the store daemon

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`01.3-store.norms.md`](../../spec/01.3-store.norms.md) Н5. The scenarios were moved from the acceptance of
М10/11 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones.

Directives and doors: `admin`, `store`, `@as`, `@big`, `@restart store`, `@foreign store` (sc. 10), `@backup store`,
`@import store` and the door `restored` (sc. 11, 12, 14); the store group stand — `@group-setup`, `@store-start`,
`@restart store@<id>`, `@sigterm`/`@sigkill store@<id>`, `@store-op`, the doors `store@<id>`, `admin@<id>`, the probe `@tls` to
`api@<id>` (sc. 07, 17, 18, 25–29, 31; the section «Store group stand» of the common README). The stand store is durable — it survives a restart (the directory `{data}`); sc. 08 relies on this. An implementation with
a non-durable training store (the norms of chapter 1.3, «Implementation decides» item 2) does not run sc. 08 and says so in the description.

## Stand

The stand store is as in the acceptance of М10/11: schema 1, the manifest rows `testsub` and `testsub2` are written by the runner itself through `admin.sock`, without the installer
(ADR-0083 addendum (98)): `put` with `cas: ""` and exactly the fields of the writer of P/02.3 Н1.5 — `yaml` (the bytes of the file), `sha256`
of these bytes, `rev` `"1"`; the rights file `{rights}` is the ready input of chapter 1.2 [`../2/inputs/rights.json`](../2/inputs/rights.json); the runner puts it before the store starts. Of it, the steps of the chapter need only the role socket
`console` without the rights of `admin` (`@as console`: sc. 08 step 8, sc. 15 steps 1–2) and the manifest rows `testsub`, `testsub2` (sc. 11
steps 9–10: the copy `backup` carries the manifest rows). The resource, the controller, the console and the workers are not needed by the chapter. The stand store of the chapter is
a single member of a box without `-api` (Н1.3 `-api`: the flag is not mandatory; the box has no partners): sc. 16 relies on this.

## `journal/corrections-3.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М10/11 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (review analysis of stage B 6–7, № 18).

## Batch and restart (sc. 30)

The batch `op: batch` on the stand store (P/01.1 Н3 «write batch», ADR-0094 B9): the rows and the `id` memory survive `@restart store`, a replay answers
`again` with the earlier version; the next batch edits one row and removes another. The stand does not reproduce a power cut in the middle of a batch — by reading
(P/01.1-31).

## A foreign directory (sc. 10)

The store format mark (chapter 1.3 Н1.3 `format`; the store pilot, A1): a second store instance on a non-empty directory without
`FORMAT` and on a directory with a foreign mark does not start (code 2) and changes nothing in the directory. The scenario does not
touch the stand store. The first write of the mark into an empty directory and a start on one's own directory — every start of the stand and `@restart store` of sc. 08.

## The copy (sc. 11, 12)

The store copy (chapter 1.3 Н1.3 `copy`; the store pilot, A2). The inputs are `inputs/*.jsonl`, JSON Lines: `copy-ok.jsonl` — a header
with `index` `"7"` and the rows `platform/epoch_floor` `{floor: "4294967296", generation_at: "1760745600.5"}` (the time form —
P/03.2 Н1.5), `testsub/counters/1` `{n: "1"}`, `testsub/next_id` `{n: "2"}` in ascending order of the key;
there are no manifest rows (`platform/manifest/*`) in the input: the copy does not know manifests, `import` carries a row of any family (chapter 1.3 Н1.3
`import`; the log of cammeta-go, lesson 11 № 10) — sc. 11 steps 1–3; `copy-ok-unordered.jsonl` — the unit rows in reverse order, without the floor row (the reader does not require an order). `bad-*.jsonl` — one
`copy` refusal per file; a correct row `testsub/next_id` stands in each of them before the spoiled one, so the step `restored` after the refusal sees that
nothing is transferred: there is no row (`items: null`, `index: ""`).

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
| `bad-row-key.jsonl` | the row key `testsub/../bad` — a segment `..`, not a key of chapter 1.1 Н1 (sc. 12 steps 27–28) |
| `bad-floor-gen-at.jsonl` | the floor row with `generation_at` `not-a-time` — not a time, the floor row is unreadable (sc. 12 steps 29–30) |
| `copy-future-floor.jsonl` | a correct copy, the floor has `generation_at` `4102444800` (2100) — the stand clock is earlier, a refusal without `-force` (sc. 12 steps 31–32; with `-force` — sc. 29) |

Sc. 11 step 4 sees the floor `platform/epoch_floor` after `import`: the floor of the input is an ordinary row of the copy, `import` raises it above
the upper of the input before the first row (Н1.3 `floor`); the number depends on the clock, the step does not fix it. Steps 7–10 — the copy `backup` of the stand store, transferred into a fresh directory, carries the manifest rows `testsub` and
`testsub2`. The writer side of the rule «Time in a row» (Н0 of chapter 1.1): sc. 11 step 4 — the floor after `import`, `generation_at`
(`@time`).

## Reconciliation of python and go М10/6–11 (sc. 08 steps 10–12, sc. 14, 15)

- Sc. 08 steps 10–12: `floor` that is not an integer JSON (`2.0e1`) — 400 before the write, not 409 «only upwards»; the largest uint64 is
  an admissible floor (Н1.3 floor `form`; B5).
- Sc. 14: the `id` replay memory is not part of the copy (Н1.3 `copy`). A write with `id` `b1` on the stand store, a copy, a transfer:
  a replay of the same `id` at the transferred store — a new write without `again`, the next replay — `again` (B10). The key `other/b10` is
  outside the stand families; `admin` writes it.
- Sc. 15: service doors (Н2). Steps 1–2 — `@as console`: `join` and `leave` from a role socket — 403 before the membership (B1); steps
  3–4 — the body `@big(1048577)` is larger than the 1 MiB limit — 413, for `PUT /v1/status` before 405 (framing → route, B2, B3); step 6 —
  empty `raft`/`api` — 400 (B4); steps 7–8 — `HEAD`. Step 9 of sc. 15 (`door.pass` `testsub2` without a worker with a door — 503,
  B26) was moved to step 1 of sc. 15 of [the acceptance of chapter 6.5](../../../06-console/acceptance/5/README.md): it needs the console.

## A member without `-api` (sc. 16)

C01-STATUS-MEMBERS-NOAPI (the Architect's decision of 2026-10-26): a member without `-api` is not in `members` of `/v1/status`,
the map of a single member of a box is `{}` (Н1.3 `-api`, `box`; Н2 `GET /v1/status`); `leader` is empty. The expectation `members`
`{}` is exactly an empty map (the dictionary of the common README, the line `<code> <JSON>`; ACC-EMPTY-OBJECT-01); `{"<id>": ""}` is not by the form of the OpenAPI of the lesson
(`minLength: 1`), and the step does not pass.

## The store group (sc. 07, 17, 18, 25–29, 31)

The group stand is the section «Store group stand» of the common README: the members `s1`…`s5`, `d1`, `d2` on the loopback, the kits are
[`inputs/group.json`](inputs/group.json) (one centre, the server name of a leaf is the `<id>` of the member), the scenario role at the doors `store@<id>` is `console`
(the stand rights file). These scenarios do not need the stand store of the chapter. Formerly sc. 07 was a `@manual` drill on a real
cluster; by ПРАВИЛА-РАБОТЫ.md § 4 it and the drills of the checklist items of the chapter (the door, size and membership, the floor of epochs, the metrics row of doors) became scenarios (the plan
`decisions/inbox/2026-10-30-план-сценарии-группы-автоматом.md`, accepted by the Architect on 2026-10-30; steps for the defect classes
of the pilot comparison — `decisions/inbox/ревью/РЕВЬЮ-СРАВНЕНИЕ-P01-Claude.md`, `P-1`…`P-6`, where they are visible from outside). The norms do not
change. The leader after `-bootstrap` and the joins is `s1` (step 5 of each scenario checks this as well). The assembly 1→2→3: the second member joins with `-force` (a group of two is a transitional parity, P/01.3 Н1.3 `join`), the third without it (C01-GROUP-BOOTSTRAP-EVEN-01). The box store build
(`keys.store_build: box`, P/01.3 Н1.3 `box`) has no group: sc. 07, 17, 18, 25–29, 31 are not_applicable for it, not red; without
the marker they are not executed (common README, «Store group stand»).

- **Sc. 31 — a batch in the group (ADR-0094 B9).** The role `console`; the door `d1` forwards the batch whole: steps 8–10 read both rows on the followers with one
  version, steps 11–12 — a replay by `id` through a voter and through the door, step 13 — a stale `cas` of the second row, step 14 sees that the first one is not written.
  Step 15 — the probe `inputs/door-row-batch.json`: the door's own row by a batch — 403 (Н1.3 `door`). Steps 16–18 — `@sigkill` of the leader: the new leader gives both rows.
- **Sc. 07 — size and the door without a vote.** A group of three; the join of a fourth — 409 `refused` both without `force` and with
  `force` (`-force` does not take beyond the declared size; Н1.3 `join`). The door `d1` (`-door -voters`): `state` `Door`, a write
  through it — by the same rights file (forwarding to the leader, visible at the follower `s2`), the row `platform/configstore-doors/d1` with
  `seen_at` not later than 40 s (every 30 s), the metrics row `configstore_doors 1` at the leader. The door `d2` with the leaf `d1` — a start refusal
  (`-id` is not the server of its leaf, C01-DOOR-ID-CN-01). The probes `door-row-*` (`inputs/`): the leaf of the door `d1` writes at the leader a foreign
  row `platform/configstore-doors/d2` — 403, its own — 200 (`P-4`; Н1.3 `door` «own»); the role forwarding header in the probe is
  a designation, the name is from the implementation description, as in the acceptance of chapter 1.2 sc. 08.
- **Sc. 17 — membership, restart, leader change, quorum.** Size 2 and 4 — a start refusal; `leave` of the stopped `s3`, its
  `join` before `admit` — 403, `admit` is repeatable (code 0), after it `join` with the same address — 200, with another Raft address — 409,
  `leave` of an unknown member — 409 (Н1.3 `leave`, `repeat`); `s3` restarts and is a follower again.
  `P-1`: three writes without `cas` through different members, a restart of a follower, then of the whole group — each has the same version `$r3`,
  and a write with `cas` `$r3` through a follower passes (the log is not applied again; the versions are the same at all members). `P-2`: a write, `@sigkill` of the leader — a read at both
  remaining members right after the election sees its version `$w`, the returned `s1` too (the read is linearizable, P/01.1 Н3). `P-3`: the door `d1` and one voter `s1` without the two others — a write through the door and
  through `s1` — 503 `unavailable` after `leader_wait` 5 s (`@sleep 6` — the deadline of the norm): the door is not part of the quorum.
- **Sc. 18 — `import` into a group and `recover`.** `import` of the copy `copy-ok.jsonl` (`index` 7) with `-index-base 7` into a fresh
  group at the leader; a repeat of a completed one — a refusal (Н1.3 `admin_ops`, B12). `P-5`: the transferred rows keep the versions of the copy — `testsub/next_id` `3`, `testsub/counters/1` `5`, and `cas` by them passes (P/01.3 Н1.3 `import`, Н3 «the copy is replayed into exactly those rows and versions»; C01-IMPORT-VERSIONS-01): an implementation that rewrites the transfer by ordinary `put` with new small versions fails here. That the new versions after the transfer are above `-index-base`, the scenario does not judge by numbers (the strings are compared only by `==`/`!=`) — by reading. The epoch row
  `testsub/epoch/u1` `429496729600005` (100000 << 32 | 5); the majority is lost (`s2`, `s3` killed, `s1` stopped);
  `recover` without `-isolated` and with `-upper` below the computed one — a refusal before any changes; with `-isolated` — the floor
  `100001 << 32 = 429501024567296` (the generation is the upper of the epoch row; the hours since 2026-01-01 are fewer than 100001), the rows and the epoch
  are kept (`P-6`: upper is from all epoch rows). The former `s2`, `s3` with old directories do not return (Н3 step 0);
  the new `s4` (`-force` — transitional parity) and `s5` join from empty directories; the floor is visible at the new follower.
- **`P-3`, a door leaf on `-raft`** (C01-RAFT-DOOR-LEAF-01, the Architect's decision of 2026-10-30): sc. 07, the last step —
  the probe `inputs/door-on-raft.json`: the leaf of the door `d1` on the raft port of `s1` — `handshake: alert` (P/01.3 Н1.6 `raft`).
- **Coverage audit of P/01** (audit-kimi 2026-10-30, commit 399e4783b): sc. 07 — the probe `inputs/forwarded-admin.json`: the leaf
  of the voter `s2` with the role forwarding header `admin` at the leader with a loaded rights file — 403 (P/01.2 Н3, A08); sc. 17
  steps 6–7 — the `/metrics` rows of the leader and of a follower (the names of Н1.3 `metrics`, the state in lowercase per ADR-0070, the number of votes 3;
  the substring «3» admits the notation «3.0»; A10); sc. 17 — `@cut store@s3` (a proxy on the raft port of the member cuts incoming
  connections; the outgoing connections of the member go directly): after a write through `s1` a read at `s3` — the new version or 503, not the earlier one
  (`P-2`), after `@mend` — the new one (NEW-DIRECTIVES § 3; the steps do not assume who the leader is).
- **Coverage audit of P/01, second pass** (Gemini 2026-10-30, commit 6a5817f88, G06; the group assembly — steps 1–5, as in
  sc. 07): sc. 25 — `/v1/status` of the door `d1` whole by Н2: `Door`, `role` `door`, `term`, `commit`, `applied` — 0;
  sc. 26 — probes of the leaf `d1` at the leader: its own row with `cas: ""` (`inputs/door-row-with-cas.json`), with an extra element
  `extra` (`door-row-extra-item.json`) and its deletion (`door-row-delete.json`) — 403, its own row by the form — 200 (Н1.3 `door`:
  only `put` without `cas` and `guard`, the single `seen_at`); sc. 27 — a live door has written its row (`@until 40`),
  `import` of the copy `copy-ok.jsonl` with `-index-base 4` (below the versions 5 and 6 of the copy) — a refusal, no rows; with `-index-base 7` —
  transferred, the version of the copy is kept (C01-IMPORT-DOOR-ROWS-01: a door row does not cancel freshness); sc. 28 — the majority
  is lost, `recover -peers` without its own `s1`, without an `api` address, with a repeat of `s1` — a refusal; `-upper 429496729700000`
  (`429496729700000 >> 32` = 100000) above the computed one (there are no epoch and floor rows, upper 0) — the floor `100001 << 32 =
  429501024567296`; sc. 29 — `import` of `copy-future-floor.jsonl` (the `generation_at` of the floor of the input is 2100) without `-force` — a refusal,
  nothing is transferred, with `-force` — transferred, the floor is raised (Н1.3 `floor` `when`, «Daemon flags» `-force`).
- **Remaining by reading**: a full cut of a member in both directions (the outgoing connections of a member on one machine are not cut);
  the branch `ambiguous` (the write went to the leader without an answer); writers during `import` (the window between the floor and «Done»); the door leaf
  on `-raft` is now not by reading: sc. 07, the last step (above, `P-3`); an unreadable door row outside `configstore_doors` (Н1.3
  `door`) — a TSV request does not carry the current time for a fresh `seen_at`, and a row with an old `seen_at` the implementation is entitled
  not to count as a visible door by the deadline (the door writes it every 30 s): the step would not tell an unreadable row from a stale one; `recover` with the clock earlier than
  the `generation_at` of the floor — the stand does not put a floor with a future `generation_at` into the group (`op: floor` writes the clock of the leader).

## The stand store: restart, a copy with an epoch, row spoiling, replay memory, service doors (sc. 12, 19–24)

- Sc. 12 steps 23–26 (A07): `import` of an input with the epoch row `testsub/epoch/u1` `{"epoch": "abc"}` (`inputs/bad-epoch.jsonl`) and
  with the floor row `{"floor": "12.5"}` (`inputs/bad-floor.jsonl`) — upper is not reliable, a refusal of the whole input, nothing is
  transferred (Н1.3 `import`, V7 item 3).
- Sc. 19 (A01): the version after a restart of the daemon on the same directory — the earlier row with the earlier version, the new versions
  differ from it (P/01.1 Н1 `index`); a non-durable training store does not run sc. 19, as with sc. 08.
- Sc. 20 (A05): `@spoil row` / `@spoil row-index` (common README) — spoiling bypassing the door by the profile command `spoil-row`
  with the store stopped, then a start: the body is unreadable — `items: null`, the version is intact, `cas` by it replaces the row;
  the version is lost — 503 for a read and for an affected listing (P/01.1 Н2, C01-ROW-INDEX-LOST-01). Without the profile command —
  not_executed.
- Sc. 21 (A02): the `id` replay memory (P/01.1 Н3) is held for no less than two minutes — a replay after `@sleep 121` (the deadline of the norm
  with a margin) gives the earlier `index` and `again`; the right to forget after 2 min and 50 000 writes — by reading. Here and not in chapter 1.1:
  its directive format does not carry this.
- The second pass of the coverage audit (Gemini, G05, G06): sc. 12 steps 27–32 — a row key with `..`, the `generation_at` of the floor not
  a time, the stand clock earlier than the `generation_at` of the floor of the input (without `-force` of the directive `@import store`) — a refusal of the whole input
  (Н1.3 `import`, `floor`; the outcomes of the family `epoch_floor`). Sc. 22 — a damaged row exists for a guard and for a deletion
  (P/01.1 Н2): the guard `""` — 412 with its version, by the version — holds; deletion with `cas: ""` — 409, with `cas` by the version — the row
  is gone; without the profile command `spoil-row` — not_executed. Sc. 23 — service doors (Н2): an extra field in `join`, `leave` and
  `op: floor` and the member `id` `_bad` — 400; step 6 — a new floor with another `id` passes, so the floor of step 5 is not written
  (otherwise — 409 `refused`). Sc. 24 — 405 for `POST /metrics`, `GET /v1/join`, `GET /v1/leave` (Н4).

## Scenario boundaries

Between scenarios the runner stops the processes, resets the store and the variables; the group members and their directories too.

## Full form and reproducibility (2026-10-16)

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the absence of platform/schema is confirmed by reading. For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

A subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, types, Content-Type, special headers and the absence of a body for HEAD/204. In expectation lines `$имя` is first bound only after a successful match of the whole answer; the following uses compare, and requests use only values already bound. A failed attempt of @until does not change the variables. @until repeats a read until the given local deadline, not a mutation; after it expires — FAIL with the last answer. @any admits any value of a present field, @absent requires absence; they do not replace the types of the full schema. A JSON object is compared by subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array by length and order. Raw HTML/text is compared as UTF-8 bytes with the given substring, it is not parsed as JSON.

In total 24 scenarios / 292 steps, all automatic (sc. 07 — 18 steps, sc. 17 — 53, sc. 18 — 28; formerly sc. 07 was one step `@manual`; sc. 12 steps 23–26, 19, 20, 21 — the coverage audit of P/01; sc. 12 steps 27–32, 22–29 — its second pass, of them 25–29 on the group stand); sc. 15 — steps 1–8 (step 9 is in the acceptance of chapter 6.5, there it is step 1 of sc. 15); sc. 16 — 1 step. 08/6–9 — the floor only upwards, only admin (mutation check 7cecaf2 № 46, 47). Sc. 08: the replay memory of `op: floor` is in the store
(chapter 1.3 Н2): a replay with the same `id` after a restart — the same `index` and `again`, a different `floor` with this `id` — 400; an implementation
that keeps it in process memory answers 409 «only upwards» after a restart, and the scenario does not pass.

## Additional check of the class of errors of run 36 (Kimi)

By reading: 503 unavailable after 5 s without a leader, ambiguous after an unknown outcome and unavailable with Retry-After at the connection limit are different branches. Sc. 05 of [the system acceptance](../../../common/acceptance/system/README.md) with one dropped server keeps the quorum and does not check all the 503 branches. A replay of id with another floor — 400 badrequest. For /v1/write and /v1/rights an unknown method gives the 404 of the owners; 405 only for status/join/leave/metrics. The metric of sc.04 is configstore_raft_voters_expected. The environment values and 64/32/8 are normative defaults; an override of the profile is declared before acceptance.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Review seams

[seams.tsv](seams.tsv) uses the CALL/JSON grammar of [P/02](../../../02-installer/forms/README.md). These four kit seams assist the existing acceptance and reading; they are not new public runner targets. The existing chapter 1.1 s2 seam repeats the **same id** after early and a clock advance.

`store-start-flags` invokes the ordinary daemon command-line parsing and startup configuration admission (before build-specific Raft capability checks), not a validator that exists only for tests. Valid temporary dir/sockets, id and all neutral inputs are supplied. loopback/non_loopback select valid addresses under the existing loopback predicate, not new address syntax. Missing TLS must refuse before network setup; observe actual calls and exit code. Acceptance here proves configuration admission, not full process/group execution.

`store-copy-floor` uses the actual durable backup/import/continuation paths. First restore a valid seed, take a real backup of that restored store with its existing floor and at least two other rows, then import that immutable backup into a fresh destination. Interrupt I/O after one non-floor target row has been durably transferred; close and continue the same attempt with the same input. Capture the first new floor row F1, including items/index/generation_at, and compare it after continuation. Inspect actual write order, every non-floor row/version, completeness and absence of an old-floor transfer. Use a controlled wall clock; no canned backup/import result or fabricated expected observation. A panic, unrelated failure or unexecuted path fails.

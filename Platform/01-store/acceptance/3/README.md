# Acceptance P/01.3 — the store daemon

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`01.3-store.norms.md`](../../spec/01.3-store.norms.md) N5. The scenarios were moved from the acceptance of
M10/11 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones.

Directives and doors: `admin`, `store`, `@as`, `@big`, `@restart store`, `@foreign store` (sc. 10), `@backup store`,
`@import store` and the door `restored` (sc. 11, 12, 14); the store group stand — `@group-setup`, `@store-start`,
`@restart store@<id>`, `@sigterm`/`@sigkill store@<id>`, `@store-op`, the doors `store@<id>`, `admin@<id>`, the probe `@tls` to
`api@<id>` (sc. 07, 17, 18, 25–29, 31; the section «Store group stand» of the common README). The stand store is durable — it survives a restart (the directory `{data}`); sc. 08 relies on this. An implementation with
a non-durable training store (the norms of chapter 1.3, «Implementation decides» item 2) does not run sc. 08 and says so in the description.

## Profile interface

Use the `01-store` [profile format](../../../common/acceptance/PROFILE.md). `stand.store` starts the durable daemon and accepts the common stand's launch substitutions and the existing daemon flags of this chapter. `stand.backup` copies through `{socket}` to `{file}`; `stand.import` imports `{file}` into the stopped fresh `{data}` using `{index_base}`. Group operator calls use `stand.store-op` with `{socket}`, `{dir}`, `{id}`, `{tls}` and prepared `{args}`; row-corruption checks use `stand.spoil-row` with `{data}`, `{key}` and `{what}` as assigned by their existing stand contract. `keys.store_build` declares `raft` or `box` with the applicability below; omission or another value does not silently select one. The role header uses `keys.role_header`. Program names and wrappers belong to the implementation; operation semantics and the flags appended by the group stand remain those of the referenced norms and common stand.

## Stand

The stand store is as in the acceptance of M10/11: schema 1, the manifest rows `testsub` and `testsub2` are written by the runner itself through `admin.sock`, without the installer
(ADR-0083 addendum (98)): `put` with `cas: ""` and exactly the fields of the writer of P/02.3 N1.5 — `yaml` (the bytes of the file), `sha256`
of these bytes, `rev` `"1"`; the rights file `{rights}` is the ready input of chapter 1.2 [`../2/inputs/rights.json`](../2/inputs/rights.json); the runner puts it before the store starts. Of it, the steps of the chapter need only the role socket
`console` without the rights of `admin` (`@as console`: sc. 08 step 8, sc. 15 steps 1–2) and the manifest rows `testsub`, `testsub2` (sc. 11
steps 9–10: the copy `backup` carries the manifest rows). The resource, the controller, the console and the workers are not needed by the chapter. The stand store of the chapter is
a single member of a box without `-api` (N1.3 `-api`: the flag is not mandatory; the box has no partners): sc. 16 relies on this.

## Batch and restart (sc. 30)

The batch `op: batch` on the stand store (P/01.1 N3 «write batch», ADR-0094 B9): the rows and the `id` memory survive `@restart store`, a replay answers
`again` with the earlier version; the next batch edits one row and removes another. The stand does not reproduce a power cut in the middle of a batch — by reading
(P/01.1-31).

## A foreign directory (sc. 10)

The store format mark (chapter 1.3 N1.3 `format`; the store pilot, A1): a second store instance on a non-empty directory without
`FORMAT` and on a directory with a foreign mark does not start (code 2) and changes nothing in the directory. The scenario does not
touch the stand store. The first write of the mark into an empty directory and a start on one's own directory — every start of the stand and `@restart store` of sc. 08.

Separate executable Z21 probe 5 uses a healthy completed directory state, not scenario 10's foreign/missing `FORMAT` mark. It checks `start_data_dir_owned` and `local_data_dir_owned`: refusal of the second daemon before readiness/any write, unchanged first owner/data/ownership; refusal of offline box import/restore and local recover. A separate simultaneous-start race, including an empty directory, yields exactly one owner; ownership checking precedes other directory-dependent reasons. After orderly exit and `SIGKILL`, lawful start without manual cleanup is checked on a healthy completed state. This does not cancel `start_format` or refusal of unfinished `import`/`restore`: unfinished transfer is a separate negative case after the owner dies. Only owned isolated processes and directories are used. Independent live-owner confirmation, check-order observation and write attribution are required; lawful background work of the first daemon is not attributed to the second attempt. Missing native binding is `NotExecuted`, not a successful refusal.

## The copy (sc. 11, 12)

**Copying damaged rows.** An existing row with a damaged body and retained version stays in backup as `{key, items: null, index, unreadable: true}`, where `index` is its exact nonempty version; the existing key order and coherent copy header remain. This is separate from import/restore refusing unreadable input under N4. A lost version requires the P/01.1 R028 log entry, a nonzero backup CLI exit and preservation of the previous published file. HTTP copy may return `503 UnavailableFault` before `200` or close incompletely after `200`; a completed copy that omits the row or invents its `index` is invalid. An import refusal of unreadable input does not permit omitting a damaged row from backup. The `spoil-row` binding uses `what=body` or `what=index`; without it the dependent observation stays `NotExecuted`.

The store copy (chapter 1.3 N1.3 `copy`; the store pilot, A2). The input (`--from`) is JSON Lines; the reader does not require an order of the rows;
the copy does not interpret manifest rows (`platform/manifest/*`): `import` carries a row of any family (chapter 1.3 N1.3
`import`; the log of cammeta-go, lesson 11 № 10). On a `copy` refusal
nothing is transferred.

A refusal of `copy`: a wrong `format` or `version` of the header, an extra field of the header or of a row, a first line that is not a header, a row without `index`, a line that is not JSON, a value of `items` that is not a string, a key twice, the `index` of a row above the `index` of the header, a row `unreadable`, an epoch or floor row that is not decimal (upper is not reliable), a row key that is not a key of chapter 1.1 N1, a `generation_at` of the floor that is not a time; a correct copy whose floor `generation_at` is later than the stand clock is a refusal without `-force`.

The input floor is used only for the upper and generation_at checks and is not transferred; `import` raises a new floor above
the upper of the input before transferring the other rows (N1.3 `floor`); the number depends on the clock. The copy `backup` of the stand store, transferred into a fresh directory, carries the manifest rows.
The writer side of the rule «Time in a row» (N0 of chapter 1.1): the floor after `import`, `generation_at`
(`@time`).

## Actual body ceiling in status (ADR-0127 P/06 C2)

The Status response of the default stand carries the required `max_body: 1048576` and the unchanged `max_value: 524288`. Repeat the ordinary status GET on a fresh store configured through the existing `-max-body 2097152` and `-max-value 524288`: max_body is2097152, max_value stays524288. This is an actual daemon/HTTP obligation; the source/schema audit does not execute that repeat. Do not add acceptance.yaml keys or guess the limits from defaults.

The independent schema witnesses in `inputs/status-body-limits.json` use complete Status responses: positive body ceilings1/1048576/2097152, and missing/zero/negative/nonintegral/bool/string/null negatives. Apply the existing Status schema to the whole response. max_body counts entity bytes, including an actual LF; HTTP request/header/chunk framing does not enter it. The static P06 profile gate uses the value from this result, not a new flag or a replacement for max_value.

## A member without `-api` (sc. 16)

C01-STATUS-MEMBERS-NOAPI (the Architect's decision of 2026-10-26): a member without `-api` is not in `members` of `/v1/status`,
the map of a single member of a box is `{}` (N1.3 `-api`, `box`; N2 `GET /v1/status`); `leader` is empty. The expectation `members`
`{}` is exactly an empty map (the dictionary of the common README, the line `<code> <JSON>`; ACC-EMPTY-OBJECT-01); `{"<id>": ""}` is not by the form of the OpenAPI of the lesson
(`minLength: 1`), and the step does not pass.

## The store group (sc. 07, 17, 18, 25–29, 31)

The group stand is the section «Store group stand» of the common README: the members `s1`…`s5`, `d1`, `d2` on the loopback, the kits are
[`inputs/group.json`](inputs/group.json) (one centre, the server name of a leaf is the `<id>` of the member), the scenario role at the doors `store@<id>` is `console`
(the stand rights file). These scenarios do not need the stand store of the chapter. Formerly sc. 07 was a `@manual` drill on a real
cluster; by work rules (for people) § 4 it and the drills of the checklist items of the chapter (the door, size and membership, the floor of epochs, the metrics row of doors) became scenarios (the plan
`automatic group scenarios plan (2026-10-30, for people)`, accepted by the Architect on 2026-10-30; steps for the defect classes
of the pilot comparison — `P01 comparison review by Claude (for people)`, `P-1`…`P-6`, where they are visible from outside). The norms do not
change. The assembly 1→2→3: the second member joins with `-force` (a group of two is a transitional parity, P/01.3 N1.3 `join`), the third without it (C01-GROUP-BOOTSTRAP-EVEN-01). The box store build
(`keys.store_build: box`, P/01.3 N1.3 `box`) has no group: sc. 07, 17, 18, 25–29, 31 are not_applicable for it, not red; without
the marker they are not executed (common README, «Store group stand»).

- **A batch in the group (ADR-0094 B9).** A door forwards a batch whole: the followers read both rows with one version; a replay by `id` goes through a voter and through a door; a stale `cas` of a row means the others are not written. The door's own row by a batch — 403 (N1.3 `door`). After `@sigkill` of the leader the new leader gives both rows.
- **Size and the door without a vote.** A join beyond the declared size — 409 `refused` both without `force` and with `force` (`-force` does not take beyond the declared size; N1.3 `join`). A door (`-door -voters`): `state` `Door`, a write through it — by the same rights file (forwarding to the leader, visible at a follower), the row `platform/configstore-doors/<id>` with a fresh `seen_at`, the metrics row `configstore_doors` at the leader. A door whose `-id` is not the server of its leaf — a start refusal (C01-DOOR-ID-CN-01). The leaf of a door writes at the leader a foreign row of the family `platform/configstore-doors/` — 403, its own — 200 (`P-4`; N1.3 `door` «own»); the role forwarding header in a probe is a designation, the name is from the implementation description.
- **Membership, restart, leader change, quorum.** A size outside `sizes` of N1.3 — a start refusal; `leave` of a stopped member, its `join` before `admit` — 403, `admit` is repeatable (code 0), after it `join` with the same address — 200, with another Raft address — 409, `leave` of an unknown member — 409 (N1.3 `leave`, `repeat`); a restarted member is a follower again. `P-1`: after a restart of a follower and of the whole group the versions are the same at all members, and a write with `cas` of that version passes (the log is not applied again). `P-2`: after a leader change a read at the remaining members sees the version of a write, a returned member too (the read is linearizable, P/01.1 N3). `P-3`: a write through a door and through a voter without a quorum — 503 `unavailable` after the effective `-leader-wait` interval: the door is not part of the quorum.
- **`import` into a group and `recover`.** `import` of a copy into a fresh group at the leader; a repeat of a completed one — a refusal (N1.3 `admin_ops`, B12). `P-5`: the transferred rows keep the versions of the copy, and `cas` by them passes (P/01.3 N1.3 `import`, N3 «the copy is replayed into exactly those rows and versions»; C01-IMPORT-VERSIONS-01): an implementation that rewrites the transfer by ordinary `put` with new small versions fails here. That the new versions after the transfer are above `-index-base`, the scenario does not judge by numbers (the strings are compared only by `==`/`!=`) — by reading. With the majority lost, `recover` without `-isolated` and with `-upper` below the computed one — a refusal before any changes; with `-isolated` — the floor by the upper of the epoch rows, the rows and the epochs are kept (`P-6`: upper is from all epoch rows). The former members with old directories do not return (N3 step 0); new members join from empty directories (`-force` at a transitional parity); the floor is visible at a new follower.
- **`P-3`, a door leaf on `-raft`** (C01-RAFT-DOOR-LEAF-01, the Architect's decision of 2026-10-30): the leaf of a door on the raft port of a member — `handshake: alert` (P/01.3 N1.6 `raft`).
- **Coverage audit of P/01** (audit-kimi 2026-10-30, commit 399e4783b): the leaf of a voter with the role forwarding header `admin` at the leader with a loaded rights file — 403 (P/01.2 N3, A08); the `/metrics` rows of the leader and of a follower (the names of N1.3 `metrics`, the state in lowercase per ADR-0070; A10); a proxy on the raft port of a member cuts incoming connections (the outgoing connections of the member go directly): after a write a read at the cut member — the new version or 503, not the earlier one (`P-2`), after `@mend` — the new one (NEW-DIRECTIVES § 3; the steps do not assume who the leader is).
- **Coverage audit of P/01, second pass** (Gemini 2026-10-30, commit 6a5817f88, G06): `/v1/status` of a door whole by N2: `Door`, `role` `door`, `term`, `commit`, `applied` — 0; the leaf of a door at the leader: its own row with `cas: ""`, with an extra element and its deletion — 403, its own row by the form — 200 (N1.3 `door`: only `put` without `cas` and `guard`, the single `seen_at`); a live door has written its row: `import` of a copy with `-index-base` below the versions of the copy — a refusal, no rows; with `-index-base` not below them — transferred, the version of the copy is kept (C01-IMPORT-DOOR-ROWS-01: a door row does not cancel freshness); with the majority lost `recover -peers` without its own member, without an `api` address, with a repeat of a member — a refusal; a `-upper` above the computed one raises the floor; `import` of a copy with a future `generation_at` of the floor without `-force` — a refusal, nothing is transferred, with `-force` — transferred, the floor is raised (N1.3 `floor` `when`, «Daemon flags» `-force`).
- **Remaining by reading**: a full cut of a member in both directions (the outgoing connections of a member on one machine are not cut);
  the branch `ambiguous` (the write went to the leader without an answer); writers during `import` (the window between the floor and «Done»); the door leaf
  on `-raft` is now not by reading: sc. 07, the last step (above, `P-3`); an unreadable door row outside `configstore_doors` (N1.3
  `door`) — a TSV request does not carry the current time for a fresh `seen_at`, and a row with an old `seen_at` the implementation is entitled
  not to count as a visible door by the deadline (the door writes it every 30 s): the step would not tell an unreadable row from a stale one; `recover` with the clock earlier than
  the `generation_at` of the floor — the stand does not put a floor with a future `generation_at` into the group (`op: floor` writes the clock of the leader).

## The stand store: restart, a copy with an epoch, row spoiling, replay memory, service doors (sc. 12, 19–24)

- An `import` of an input with an epoch row or a floor row that is not decimal — upper is not reliable, a refusal of the whole input, nothing is transferred (N1.3 `import`, V7 item 3).
- The version after a restart of the daemon on the same directory — the earlier row with the earlier version, the new versions
  differ from it (P/01.1 N1 `index`); a non-durable training store does not run this check.
- `@spoil row` / `@spoil row-index` (common README) — spoiling bypassing the door by the profile command `spoil-row`
  with the store stopped, then a start: the body is unreadable — `items: null`, the version is intact, `cas` by it replaces the row;
  the version is lost — 503 for a read and for an affected listing (P/01.1 N2, C01-ROW-INDEX-LOST-01). Without the profile command —
  not_executed.
- The `id` replay memory (P/01.1 N3) is held for no less than two minutes; the right to forget after 2 min and 50 000 writes — by reading.
- The second pass of the coverage audit (Gemini, G05, G06): a row key with `..`, the `generation_at` of the floor not a time, the stand clock earlier than the `generation_at` of the floor of the input (without `-force` of the directive `@import store`) — a refusal of the whole input (N1.3 `import`, `floor`; the outcomes of the family `epoch_floor`). A damaged row exists for a guard and for a deletion (P/01.1 N2): the guard `""` — 412 with its version, by the version — holds; deletion with `cas: ""` — 409, with `cas` by the version — the row is gone; without the profile command `spoil-row` — not_executed. Service doors (N2): an extra field in `join`, `leave` and `op: floor` and a bad member `id` — 400; a refused floor is not written. 405 for `POST /metrics`, `GET /v1/join`, `GET /v1/leave` (N4).

## Scenario boundaries

Between scenarios the runner stops the processes, resets the store and the variables; the group members and their directories too.

## Full form and reproducibility (2026-10-16)

Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory. Load the unchanged testsub and testsub2; root is testsub, the second is available under /testsub2; there is no domain, requests come from the loopback. The background controller/resource/worker do not work before @start. The build is schema 1; the absence of platform/schema is confirmed by reading. For each POST that creates a unit the runner issues a fresh Idempotency-Key, kept only for the replays of the same step. A table POST does not get a promise of replay memory from this.

A subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, types, Content-Type, special headers and the absence of a body for HEAD/204. In expectation lines `$name` is first bound only after a successful match of the whole answer; the following uses compare, and requests use only values already bound. A failed attempt of @until does not change the variables. @until repeats a read until the given local deadline, not a mutation; after it expires — FAIL with the last answer. @any admits any value of a present field, @absent requires absence; they do not replace the types of the full schema. A JSON object is compared by subset (`{}` at any level is exactly an empty object: the dictionary of the common README, ACC-EMPTY-OBJECT-01), an array by length and order. Raw HTML/text is compared as UTF-8 bytes with the given substring, it is not parsed as JSON.

In total 24 scenarios / 292 steps, all automatic. The floor goes only upwards, only admin. The replay memory of `op: floor` is in the store
(chapter 1.3 N2): a replay with the same `id` after a restart — the same `index` and `again`, a different `floor` with this `id` — 400; an implementation
that keeps it in process memory answers 409 «only upwards» after a restart, and the scenario does not pass.

## Additional check of the class of errors of run 36 (Kimi)

By reading: 503 unavailable after the effective -leader-wait interval without a leader, ambiguous after an unknown outcome and unavailable with Retry-After at the connection limit are different branches. Sc. 05 of [the system acceptance](../../../common/acceptance/system/README.md) with one dropped server keeps the quorum and does not check all the 503 branches. A replay of id with another floor — 400 badrequest. For /v1/write and /v1/rights an unknown method gives the 404 of the owners; 405 only for status/join/leave/metrics. The metric of sc.04 is configstore_raft_voters_expected. The launcher values follow P/02.4 and the daemon defaults belong only to forms/daemon-flags.tsv; an override of the profile is declared before acceptance.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Review seams

[seams.tsv](seams.tsv) uses the CALL/JSON grammar of [P/02](../../../02-installer/forms/README.md). These four kit seams assist the existing acceptance and reading; they are not new public runner targets. The existing chapter 1.1 s2 seam repeats the **same id** after early and a clock advance.

`store-start-flags` invokes the ordinary daemon command-line parsing and startup configuration admission (before build-specific Raft capability checks), not a validator that exists only for tests. Valid temporary dir/sockets, id and all neutral inputs are supplied. loopback/non_loopback select valid addresses under the existing loopback predicate, not new address syntax. Missing TLS must refuse before network setup; observe actual calls and exit code. Acceptance here proves configuration admission, not full process/group execution.

`store-copy-floor` uses the actual durable backup/import/continuation paths. First restore a valid seed, take a real backup of that restored store with its existing floor and at least two other rows, then import that immutable backup into a fresh destination. Interrupt I/O after one non-floor target row has been durably transferred; close and continue the same attempt with the same input. Capture the first new floor row F1, including items/index/generation_at, and compare it after continuation. Inspect actual write order, every non-floor row/version, completeness and absence of an old-floor transfer. Use a controlled wall clock; no canned backup/import result or fabricated expected observation. A panic, unrelated failure or unexecuted path fails.

## Non-default service body limit

Use the existing fresh-stand body_limit parameter (the daemon -max-body), for example2097152 from the status-limit witness above. Let B be that actual limit reported by max_body. Send POST /metrics with one JSON object padded by JSON whitespace to exactly B entity bytes: the frame passes and the existing method outcome is405. At B+1 entity bytes the answer is413 before the method outcome, with BodyTooLargeFault.limit equal to B, not the row ceiling or the default of the flag. Repeat the oversized body at a service POST route: it is refused before JSON/body or membership work. Compare membership before/after; it is unchanged. Preserve the ordinary full Fault/header checks and the independent max_value observation. No new profile key, command spelling or request grammar is needed. These are raw HTTP probe obligations on the actual daemon, not a source/schema execution result.

## Production qualification coverage

The [production acceptance contract](../../spec/production-acceptance.md) assigns the workload, phase-deadline, copy/stop, fault-stage and HTTP-copy groups separately from these functional scenarios. Their declared budgets, independent activation and complete observations are required for a production result. Existing TSV inputs/expectations and ordinary/group applicability remain unchanged; a missing binding or budget is blocked/NotExecuted, not PASS.

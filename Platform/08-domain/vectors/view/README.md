# Vectors of the domain view and the shadow report

This English text is the source; the Russian translation `ru/vectors/view/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of the function `view` of [chapter P/08.1](../../spec/08.1-domain.norms.md): the holder's pass without a store, a network and a stand —
the input is the holder's passes in order, the output is the domain view and the shadow report of the last pass (N1.3–N1.6,
N3 «the holder's pass»; N2 «Command `view`»). The owner is lesson P/08, chapter 8.1; the function is performed by the process `domain` (a pass once per
`VIEW_EVERY`). The bytes are written by «Specification» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080
addendum 16).

The rows were transferred from the steps of the acceptance of M11/01
(sc. 01–16, 28 steps; the command `view` on `inputs/*.json`) at the move of lesson 8 (the plan of the move of lesson 8, § 3 and V1; the decision
of «Architect» 2026-10-20, ADR-0083 addendum (14)). `case` is the name of the input file, `note` is the scenario and the step of the acceptance of M11/01. The input is
the JSON of the file in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers (`1.0`, `100.25`) and
the values are as in the file. The expectation is a subset of the acceptance step as it is (after `ok `). The scenarios of M11/01 and their inputs were removed
by the move of lesson 8 (the directory M11/01 is removed): the table is the only source of these cases.

## Run

Without a stand: the command `view` of an implementation gets the input (the column `input`) and prints the JSON `{view, shadow}`; `expect` is
a subset of the fields of the output by the dictionary of the «Stand» ([the common acceptance README](../../../common/acceptance/README.md), `<code>
<JSON>`: the named fields exist and are equal, an array — by length, order and elements, a number — by value) or `@exit 2` (an input not
of the form `ViewInput`). Each row is a separate run on a fresh state: the memory of the shadow report does not pass between rows.
The `as_of` of the output is the wall seconds of the command process, it is not compared.

## Inputs and manifests

The form of the input is `ViewInput`, of the output `ViewOutput` ([the contract of the lesson](../../spec/08-domain.api.openapi.yaml)): `manifests` are the manifests of the catalog,
`holder` is the name of the holder, `passes` are the passes; in a pass `at` is the monotonic seconds of the holder, `members.<member>` is
`{mark, stale?, objects}` (`mark` is the `rev` of the mark `reported` or `null`, `stale` is the field `stale` of the mark, `objects` are the pulses
`<sub>/heartbeats/<worker>` and the shards `<sub>/snapshot/<shard>` of the copy), `placements` are the placements
`{<sub>: {<ref>: <member> | {cluster, copies?, origin?}}}` or `null` — the placements of this pass were not read (P/08.1 N3
step 3a; ADR-0091 addendum (13) item 1). The `shadow` of the output is the report of the last pass that built it (P/08.1 N1.6 `unread`). The holder sees a change of the mark and of the pulse between the passes of the input; the first pass
is the first look.

The input is the pulses after the read by the family `heartbeats` (P/03.4): the form of the input is this one, not the family; a pulse without `instance` or with
`worker` from the key is a positive input, the rows with it stay positive (P/08.1 N1.4; the decision of «Architect» 2026-10-20 (Go M11-01 № 7; the family heartbeats, the review analysis of stage B 6–7, № 14, № 15)).

The expectations depend on the bytes of the catalog manifests (the review analysis of stage A 8–10, № 37): `domain.ref`, `domain.view`, `unit.rows` and
`unit.id` of the manifests `testsub` and `testsub2` from the specification data:

| Manifest | File | sha256 |
|---|---|---|
| `testsub` | [`Source/tests/testdata/testsub.subsystem.yaml`](../../../../Source/tests/testdata/testsub.subsystem.yaml) | `7e6118cea2d639e11e894208d5f5be1d82cd1ec385cac0231fe7449305e5430a` |
| `testsub2` | [`Source/tests/testdata/testsub2.subsystem.yaml`](../../../../Source/tests/testdata/testsub2.subsystem.yaml) | `813a807f3472bdc64e279c94c12bfe3b00ebaaa8ebda0c996d2a50161043e6eb` |

The bytes of `testsub2` changed on 2026-11-04 (roadmap 4.5): the token kind `vault` with `keep: true` was added to `domain.tokens`, then the comments of the header were rewritten without the names of test files; the fields on which the expectations of this table depend are not touched — a recheck by the oracle is not needed.

A change of these bytes is a reason to recheck the table by the oracle.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 51 rows: 20 only `view`, 19 only `shadow`, 8 both, 4 `@exit 2` (28 — from M11/01, 5 — ADR-0091 addenda (12)–(19), 10 — the coverage audit of P/08, the second pass, 4 — the reading probe of 08, 2 — ADR-0110, ADR-0111, 2 — ADR-0113 addendum (1)) | `input` is the input of the command `view` as JSON text → `expect` is a subset of `{view, shadow}`: the members `ok`/`unseen`/`silent`/`never` and `age` (LOST_AFTER 45/46, the loss and the return of a mark, the leaving and the return of a member, rounding 0.25 → 0.3), the units `live`/`stale`/`configured`/`silent`, `contested`, `complete`, a duplicate id, a change of the pulse by JCS, a pulse element without a shard row; the findings `lagging`, `stalled` (SHADOW_STALL 60/61), `orphaned`, `unmanaged`, `conflict` (the executors `cluster` and `copies`, two workers of one member), `stale_epoch`, `unknown`, `clean_streak` and `may_write`; the executors of placement `{cluster} ∪ copies` — not `contested` (`10-copies`, `10-origin-is-cluster`), a member outside the set and `origin` outside `copies` — `contested` and `conflict` (`10-not-executor`, `10-origin-outside-copies`), a third member `silent` — `complete: false` without a dispute (`10-third-silent`), a row without a `domain.ref` value — outside `units`, without a claim (`10-no-ref-row`), the placements were not read — `contested`, the report as before (`10-placements-unread`) |

An input not of the form (N4, N5 of the chapter; the form `ViewInput`) — the rows `17-exit-*`: `holder` `""`, `passes` `[]`, `mark` 2^53, the placement
`{cluster: ""}` — `@exit 2` (the coverage audit of P/08, the second pass of Gemini; they were not in the acceptance of M11/01).

## Rows of the coverage audit of P/08, the second pass (Gemini)

Ten rows `17-*`…`21-*` (the Gemini draft G01, the commit `e32df6f8b` of the audit branch; the expectations are the output of the command `view` of both
witness implementations `cammeta-python` and `cammeta-go` on the export `d27f95d`, the input is `manifests` under the former name `specs`):

- `17-exit-*` — four inputs not of the form `ViewInput`, `@exit 2` (N4, N5);
- `18-duplicate-equal-revision` — an id in two shards of one member with an equal `revision`: the row of the first shard by key in
  the order of UTF-8 bytes (N1.4 `duplicate`, V5; `15-duplicate-id` — only a larger `revision`);
- `19-sealed-unreadable-no-claim` — pulse elements `phase: sealed` (`{id, phase, why, revision}`) and `phase: unreadable`
  (`{id, phase, why}`) by the form of P/03.4 N1.1: the units are in `units` with this phase, there are no claims — without placements they would otherwise be
  `unmanaged` (N1.6 `claim`, W03-G02, W03-G05);
- `20-stall-after-progress-at-60`, `-at-61` — a change of `observed_revision` at `at` 190 starts the SHADOW_STALL count anew:
  after 60 s — `lagging`, after 61 s — `stalled` (`06-progress` sees only the progress itself, not the count after it);
- `21-orphan-retarget-at-60`, `-at-61` — the placement `c1` → `m1`, `m2` and `m1` again (at `at` 160): the triple (sub, ref, cluster)
  is a new placement, the count of `orphaned_from` starts anew (N1.6 `orphaned_from`, V10): 60 s after the return there is no finding,
  after 61 s — `orphaned`. The witness `cammeta-python` does not reset the count at a return to the former target (at `-at-60` it gives
  `orphaned` 1, 120 s from the first look) — it diverges from V10; the norm is right, the expectation is by it and `cammeta-go`.

Not taken from the draft: a subsystem in `placements` outside `manifests` — there is no norm «input out of form» for it (the form of
`placements` is any subsystem names; both witnesses give code 0 and the finding `unknown`); the elements `sealed`/`unreadable` with
`epoch` 0 and `observed_revision` 0 — not of the form of P/03.4 N1.1, there is no claim for another reason (V14), they do not check the phase rule —
replaced by an input of the form.

The vectors are checked by an oracle against the text of the norms of chapter 8.1 (N1.3 `member_state`, `unit_state`; N1.4; N1.6; N3), not against the code of
implementations (the rows of the second pass of the audit — by the output of the witnesses, above): all 33 expectations are a subset of its output (the rows `10-*` — by the oracle extended with the rules of ADR-0091 addenda (12)–(19):
the executors, a row without `domain.ref`, the placements were not read; the former oracle diverges on five of them — the rows distinguish
the rule). On a divergence the norm is right, the vector is corrected by «Specification».

## Log of the source

The rows of `corrections.tsv` of the acceptance of M11/01 before the move (the directory is removed by the move of lesson 8; the paths and numbers are the former ones, they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)):

| date | sample | fix |
|---|---|---|
| 2026-10-17 | 01/all inputs, sc. 02, 07, 09 | A reading of «Architect»: unseen after the start of the holder, a claim only from a live pulse, orphaned after SHADOW_STALL; the inputs are rebuilt (the first pass — unseen), +sc. 09 |
| 2026-10-17 | 01/inputs/03-configured-and-stale.json, 09-zombie.json | The decision of «Architect» on M11-03 № 5: live/stale — by the stale of the mark; the inputs carry the stale of the member, the expectations are as before |
| 2026-10-17 | 01/inputs/10-copies.json, 10-not-executor.json | The decision of «Architect» on M11/6 item 7: the executors of placement are cluster and copies |
| 2026-10-18 | 07-faults/1 expected orphaned: 1 — the input gives c5 → m2 with a claim only at m1 (generator 01bf847, the log of M11-01 № 10) | by the norm N1.6 two facts: the placed one does not work (orphaned) and an unplaced one works (conflict); the expectation orphaned: 2, conflict: 1; the norm calls this the facts row |
| 2026-10-18 | 01/scenarios.tsv; inputs | run 41, mutations №1, №2: LOST_AFTER 45/46, SHADOW_STALL 160/161 — both sides |
| 2026-10-18 | 01/scenarios.tsv; inputs | run 41, mutations №3–5: sc. 11 — unknown (a placement not to a member), conflict of two workers of one member, never with age null |
| 2026-10-18 | 11-findings-without-step 4 | run 41 of Kimi (minor, lesson 1): the branch no_ref of N1.4 — a pulse element without a shard row does not enter units |
| 2026-10-19 | 12–16; inputs 12–16 | the M11 check 01–04 (V1–V6): a lost mark — silent with the former copy, never only «never», leaving forgets the memory, rounding from the decimal notation, a duplicate id — the larger revision, a change of the pulse — a change of JCS |
| 2026-10-20 | the move | sc. 01–16 (28 steps) from M11/01 — the rows of this table (stage B; the plan of the move of lesson 8, V1); the inputs in one line, the expectations as before, checked by the oracle |
| 2026-10-23 | 10-copies, 10-not-executor; +10-origin-is-cluster, 10-origin-outside-copies, 10-third-silent, 10-no-ref-row, 10-placements-unread | ADR-0091 addenda (12)–(19) (addendum (15) item 7): the executors of placement are not a dispute (10-copies — `complete: true`, both units in `units`), `origin` does not change the set, a row without `domain.ref` is not a unit, the placements were not read — there is no exception, the report is not built; the input is `placements: null`, `origin` |
| 2026-10-26 | 01-two-members | ACC-EMPTY-OBJECT-02 (the decision of «Architect» 2026-10-26): `{}` in `expect` is exactly an empty object; `contested` is a key at each manifest with `domain.ref` (N1.2, at `testsub2` — `ref: name`): the expectation `{}` → `{"testsub": {}, "testsub2": {}}` |
| 2026-10-30 | +17-exit-empty-holder, 17-exit-no-passes, 17-exit-mark-2pow53, 17-exit-placement-empty-cluster, 18-duplicate-equal-revision, 19-sealed-unreadable-no-claim, 20-stall-after-progress-at-60, -at-61, 21-orphan-retarget-at-60, -at-61 | the coverage audit of P/08, the second pass (Gemini G01, e32df6f8b): an input not of the form — `@exit 2`; a duplicate id with an equal revision; sealed and unreadable without a claim; the SHADOW_STALL count after progress; orphaned_from at a change of the target and a return (V10); the expectations are the output of the witnesses `cammeta-python` and `cammeta-go` (`-at-60` of row 21 — only `cammeta-go`: `cammeta-python` does not hold V10) |

Native camera input (G08-VIEW-CAMERA-INPUT-01). In `ViewInput`, an explicitly present `silent_after` selects camera freshness for that pass; without it the input models a server. This is the native command’s abstraction of `Entry.class` and the mark’s `received_at`, which its closed input does not carry. At the first look at an existing camera mark, the command seeds its receipt time with that pass’s monotonic `at`: the member is `ok` while the mark exists and the age since that receipt or the last observed mark change is at most `silent_after`, and `silent` when it is greater. A mark never seen is `never`; a vanished mark is `silent`, as in N1.3. A server keeps the ordinary first-look `unseen` rule until an observed mark change. This abstraction does not change the running holder: it obtains the class from the accepted entry and the receipt time from the actual mark, never from a heartbeat timestamp. No class or receipt field is inferred from the copy’s objects.

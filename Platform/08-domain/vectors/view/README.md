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
| `testsub` | [`Platform/common/data/testsub/testsub.subsystem.yaml`](../../../common/data/testsub/testsub.subsystem.yaml) | `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b` |
| `testsub2` | [`Platform/common/data/testsub/testsub2.subsystem.yaml`](../../../common/data/testsub/testsub2.subsystem.yaml) | `e4bfd9e0035dba5839018625bba20f7214176004fc2d0cb4f8d640015d915dbb` |

The bytes of `testsub2` changed on 2026-11-04 (roadmap 4.5): the token kind `vault` with `keep: true` was added to `domain.tokens`, then the comments of the header were rewritten without the names of test files; the fields on which the expectations of this table depend are not touched — a recheck by the oracle is not needed.

A change of these bytes is a reason to recheck the table by the oracle.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 51 rows: 20 only `view`, 19 only `shadow`, 8 both, 4 `@exit 2` (28 — from M11/01, 5 — ADR-0091 addenda (12)–(19), 10 — the coverage audit of P/08, the second pass, 4 — the reading probe of 08, 2 — ADR-0110, ADR-0111, 2 — ADR-0113 addendum (1)) | `input` is the input of the command `view` as JSON text → `expect` is a subset of `{view, shadow}` |

Native camera input (G08-VIEW-CAMERA-INPUT-01). In `ViewInput`, an explicitly present `silent_after` selects camera freshness for that pass; without it the input models a server. This is the native command’s abstraction of `Entry.class` and the mark’s `received_at`, which its closed input does not carry. At the first look at an existing camera mark, the command seeds its receipt time with that pass’s monotonic `at`: the member is `ok` while the mark exists and the age since that receipt or the last observed mark change is at most `silent_after`, and `silent` when it is greater. A mark never seen is `never`; a vanished mark is `silent`, as in N1.3. A server keeps the ordinary first-look `unseen` rule until an observed mark change. This abstraction does not change the running holder: it obtains the class from the accepted entry and the receipt time from the actual mark, never from a heartbeat timestamp. No class or receipt field is inferred from the copy’s objects.

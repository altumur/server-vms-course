# Vectors of the domain view and the shadow report

This English text is the source; the Russian translation `ru/vectors/view/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of the function `view` of [chapter P/08.1](../../spec/08.1-domain.norms.md): the holder's pass without a store, a network and a stand —
the input is the holder's passes in order, the output is the domain view and the shadow report of the last pass (N1.3–N1.6,
N3 «the holder's pass»; N2 «Command `view`»). The owner is lesson P/08, chapter 8.1; the function is performed by the process `domain` (a pass once per
`VIEW_EVERY`). The bytes are written by «Specification»; the conformance of the product is by its acceptance against this table.

`case` is the name of the case, `note` is a comment on the row. The input is
JSON text in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers (`1.0`, `100.25`) and
the values are kept as they are. The expectation is written as in a stand step after `ok `. The table is the only source of these cases.

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
step 3a). The `shadow` of the output is the report of the last pass that built it (P/08.1 N1.6 `unread`). The holder sees a change of the mark and of the pulse between the passes of the input; the first pass
is the first look.

The input is the pulses after the read by the family `heartbeats` (P/03.4): the form of the input is this one, not the family; a pulse without `instance` or with
`worker` from the key is a positive input, the rows with it stay positive (P/08.1 N1.4).

The expectations depend on the bytes of the catalog manifests: `domain.ref`, `domain.view`, `unit.rows` and
`unit.id` of the manifests `testsub` and `testsub2` from the specification data.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| the vector cases, 51 rows: 20 only `view`, 19 only `shadow`, 8 both, 4 `@exit 2` | `input` is the input of the command `view` as JSON text → `expect` is a subset of `{view, shadow}` |

Native camera input. In `ViewInput`, an explicitly present `silent_after` selects camera freshness for that pass; without it the input models a server. This is the native command’s abstraction of `Entry.class` and the mark’s `received_at`, which its closed input does not carry. At the first look at an existing camera mark, the command seeds its receipt time with that pass’s monotonic `at`: the member is `ok` while the mark exists and the age since that receipt or the last observed mark change is at most `silent_after`, and `silent` when it is greater. A mark never seen is `never`; a vanished mark is `silent`, as in N1.3. A server keeps the ordinary first-look `unseen` rule until an observed mark change. This abstraction does not change the running holder: it obtains the class from the accepted entry and the receipt time from the actual mark, never from a heartbeat timestamp. No class or receipt field is inferred from the copy’s objects.

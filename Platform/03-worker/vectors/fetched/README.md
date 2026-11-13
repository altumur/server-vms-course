# Vectors: retaining names in fetched

This English text is the source; the Russian translation `ru/vectors/fetched/README.md` (for people, not in the export) is derived from it.

The owner is [P/03.6](../../spec/03.6-worker.norms.md), N3 "Retaining fetched", P/03.6-R227 and P/03.6-R228. The worker (`03-worker`) selects the names of the requests whose outcomes it has reported. The selection is shared by the ordinary and append profiles; this package does not run an action, publish a mark or run the console reaper.

## cases.tsv

UTF-8, LF, literal TAB separators; blank lines and lines starting with `#` are skipped. The header is `case<TAB>input<TAB>expect<TAB>note`.

| Column | Meaning |
|---|---|
| `case` | Unique case name. |
| `input` | A JSON object with `count`, `bytes` and `reported`, described below. |
| `expect` | A JSON array of the retained `SaidID(rid)` names, compared as a set. |
| `note` | The tested boundary or retention rule. |

`count` and `bytes` are positive integers: the `FETCHED_COUNT` and `FETCHED_BYTES` limits supplied to the selection being tested. They are test inputs to the real worker selection logic, not process settings or required production values.

`reported` is an array of objects with exactly `rid` and `row`. Its order is the order in which the holder reported the names, oldest first. `rid` is the request identifier, a non-empty JSON string; the `SaidID(rid)` values in one input are distinct. `row` normalizes the holder's current read observation: `present` is a confirmed existing request row, `absent` is confirmed absence, and `unknown` is a read with no confirmed outcome. These words describe the fixture, not a new store response.

The array supplies the reported names considered by one selection, including a newly reported name when the case exercises a limit. Names already evicted before this selection are not in the input. No request body, mark state, wall clock or external action is inferred from the identifier.

## Run

The implementation's vector command calls its own worker retention and selection logic with the input limits and observations. It removes names whose request row is confirmed absent, keeps names with `present` or `unknown`, and applies the oldest-first limit rule. It measures the resulting `SaidID` names as UTF-8 with one comma between adjacent names, not the raw identifiers or a JSON encoding. The native output is one JSON array of the retained names, native exit code 0. Output order is not judged: the heartbeat need not sort its names.

The participant is only the worker. The adapter translates the fixture to its own representation and translates the observed selection back; it does not compute a replacement answer or use `expect`. No SDK signature, executable name or runtime configuration mechanism is prescribed.

## Vector wire

The profile's existing `vectors` mapping declares package `03-worker/fetched`, using the [unified vector command](../../../common/acceptance/PROFILE.md#unified-vector-command). The wire of `cases.tsv` (judge-only: the vector rows) is the `03-worker/fetched` row of [the single form](../../../common/vectors/wire.tsv), surface `vectors`; [grammar](../../../common/vectors/wire.md). The row supplies only the `input` cell, byte for byte, with no files. It compares the decoded native JSON array as a set.

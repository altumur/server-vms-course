# Vectors: the reaper over an append request and a resource row

This English text is the source; the Russian translation `ru/vectors/reap/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.4 ([norms](../../spec/06.4-console.norms.md) N3 «reaper», `gone`, `expired`) through [the contract of the request and its
mark](../../../common/contracts/request-mark.md) «States of an executed request and its mark» (the rows «reaper, append, …»;
stage C guess C06-GONE-FETCHED-33-01, the Architect's decision of 2026-10-25; the VMS request «request term», the Architect's decision of
2026-10-29). The participant is the console reaper. The bytes are written by
the Specification; the rows were composed by the text of the contract, not by the code of implementations.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object (the decision of one reaper pass over one row, the reads are replaced by the input):

| Field | Value |
|---|---|
| `profile` | `fetched` — the ADR-0054 append (`requests.outcome: fetched`); `resource` — the resource row `requests/free-<server>-<volume>` |
| `resource_state` | for `resource`: `resource_state` of the owner server from the key (`live`, `unreachable`, `unknown`, `silent`) or `noanswer` — the store did not answer |
| `settle`, `ttl` | the keys `requests` of the manifest, seconds; the key `ttl` may be absent. `REAP_AFTER` is the constant 60 (P/06.4 N1.5) |
| `row` | `{unit, digest}` of the request row read with confirmation |
| `row_age` | the age of the row (by the `ttl` rule of the contract), seconds |
| `unit` | the read of the row of the addressee unit: `present`, `absent` (no row or a tombstone, confirmed), `unknown` (not confirmed) |
| `mark` | the mark `objects/<sub>/commands/<rid>` as read, or `null` — none |
| `mark_age` | the age of the first confirmed read of the mark, local monotonic seconds, or `null` |
| `fetched_age` | the age of the first confirmed `fetched` of a holder for this row, or `null` — there was none |

**Output** — `{"write_mark": "gone" | "expired" | null, "remove_row": true | false}`: which mark to write create-once and whether to remove
the row (by CAS, with the rid from `asked`) in this pass. The comparison is JSON by value.

38 rows.

## Run

Without a stand: the side gives the input to its own reaper decision and compares the output. The CAS races, the repeated write of the mark on `conflict` and
the release of the record are by reading the contract; scenario 07 of the acceptance of chapter 6.4 is `gone` on the stand, scenario 11 is `expired` on the stand.
Who executes it is the console reaper (`06-console`, both profiles: P/06.4 N3 «reaper» and the removal of a resource row without a live owner by `ttl`; the contract of the request and its mark, the rows «reaper …»). The input is written by other roles, and they do not execute the reaper decisions: `fetched` of the heartbeat — the holder worker (`03-worker`, P/03.6 N3 «The append»), the row `free-*` — the resource (`05-resource`, P/05 N1.4 `free_ask`; its removal under the flag is `relieve`, not the reaper) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `06-console/reap` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

# Delta 0129-p01-core-clarify — ADR-0129 p5

change: 0129-p01-core-clarify rev 1. Base 62751995ba14646dac48d482d5dc394ecd9a87c2; lesson delta_base 725653954. Unit normalization: LF, strip trailing spaces, one final LF.

## ADDED

(none)

## MODIFIED

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R088

old-sha256: b9fa2f82677b4055d4d037e8c57bb946693bc4211f665d5cd5bfda3e5c55afc2

<!-- req: P/01.1-R088 -->
The order of checks inside the operation is normative: the `id` memory, then `not_after` and `not_before`, then the guard,
then CAS; with several violations the answer is by the first one (ADR-0091 item 1). A replay of an applied write gets its
answer also after `not_after` — including a replay that arrived while the first copy was not yet applied: the first one
is applied first, the replay answers with its answer. A refusal `expired` and `early`, like `conflict` and `guard`, makes no write and does not take the `id`, but the admission time of the refused
record remains the last admission time (in a group — a log record; a box and a store in the process store it as durably
as rows; C01-ADMITTED-ON-REFUSAL-01). Only `expired` remains the same refusal for the same deadline and nondecreasing admission time. `early`, `conflict` and `guard` do not occupy the `id`: the same command and `id` are checked again against the current admission time and state and may succeed. The caller still re-reads its condition and decides anew before another attempt (N4). The guard before CAS. A guard refusal means a mismatch of the observed version and the absence of this write. The caller re-reads the condition and decides anew whether it has the right to repeat; a version mismatch by itself does not prove a loss of ownership. A CAS refusal also requires a re-read before a new attempt. A guard on an absent row (`index: ""`) holds while the row does not exist.

The absence of business effects is distinct from admission metadata: an already admitted put or delete that returns any of these four refusals still updates the last admission time to this record's `admitted` (which may equal the previous time). It does not roll that metadata back with the refused row/id/version effects. The persistence rule is the same as for admission in the successful case (N3 Admission time). This statement concerns an already admitted record, not a request rejected before admission.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R090

old-sha256: fdc224295844125e6a4e20d5ca923d59fdcacecea00f52f382d6525b33e65004

<!-- req: P/01.1-R090 -->
The «different record» of a replay is compared by the values of the fingerprint fields, not by the bytes of the body:
`cas: null` equals the absence of `cas`, the order of the fields of `items` and the way JSON strings are escaped have no
meaning; both `not_after` and `not_before` — by their finite binary64 numeric values as in N1 (`10` and `10.0` are one), absence equals no number. Distinct JSON number spellings that round to the same binary64 value compare equally and have the same bound fingerprint; exact decimal-rational comparison and raw spelling are not the bound domain. This numeric rule does not apply to versions: they remain exact strings, and `"0"` is not `""`.

### `Platform/01-store/spec/01.1-store.norms.md` P/01.1-R132

old-sha256: 984d0f0b7658f9faa176fe47f629a4cf472180bbe1367dbc53cd900e235d5169

<!-- req: P/01.1-R132 -->
The refusals `expired`, `early`, `guard`, `conflict` make no write, do not take the `id` and do not spend versions; the
admission time of a refused batch remains the last admission time, as for a write. A refusal names the row but not the
value: `412 guard {key, index}`, `409 conflict {key, index}` — the version of this row now.

The refused batch still updates the last admission time to this record's `admitted` (which may equal the previous time), with the same durability as admission of a successful batch. Zero business-row changes, no occupied `id` and no issued version do not mean rolling back this admission metadata. This applies to each of the four named refusals after admission, not to a request rejected before admission.

## REMOVED

(none)

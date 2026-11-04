# Vectors: the tombstone — the peers, the acknowledgements, the removal

This English text is the source; the Russian translation `ru/vectors/tombstone/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the tombstone contract](../../contracts/tombstone.md) (lesson P/05; the guess of stage C C06-BLOB-GC-33-01 /
IF-OBJECT-TOMBSTONE63-PEERS-01, the Architect's decision of 2026-10-25). The participants are the console (writes the tombstone, P/06.1 Н3
«body sweep») and the resource (the acknowledgements and the removal, P/05 Н1.1). The bytes are written by «Спецификация»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>op<TAB>input<TAB>expect<TAB>note`.

| `op` | Input → output |
|---|---|
| `peers` | `{self, doors, decommission, silent?}`: `self` — its own server; `doors` — the servers of the keys of the listing `platform/doors/`, `decommission` — of the listing `platform/decommission/`, each — an array or `"@unconfirmed"` (the listing is not confirmed); `silent` — the servers with a silent resource (to show that silence does not change peers) → `{"peers": [...]}` or `"no_delete"` |
| `ack` | `{peers, acked, answers, decommission?}`: `answers` — the answer of GET of the copy of each of the peers that is not in acked and is not decommissioned: a code (`404`, `200`, `500`) or `"silent"` (a non-answer); `decommission` — the servers of the listing `platform/decommission/` or `"@unconfirmed"`, no field — `[]` → `{"acked": [...]}` |
| `remove` | `{tombstone, now, rewritten}`: `tombstone` — `{written, peers, acked}` or `"@garbled"` (unreadable); `now` — the wall seconds of the remover; `rewritten` — the key was written at the deleter again after `written` → `"remove"` or `"keep"` |

The comparison is JSON by value; the arrays `peers` and `acked` — as sets (the order is not normed by the contract; in the table — in ascending
byte order). 21 rows: 8 `peers`, 5 `ack`, 8 `remove`.

## Run

Without a stand: a side gives the input to its functions of the peers, of the acknowledgement and of the removal (the listings, the answers of the neighbours and the clock are replaced by
the input). The dropping of a copy by a neighbour and 409 «deleted later» — P/05, by reading.
Who performs is by `op`: `peers` — the console (`06-console`, writes the tombstone); `ack` and `remove` — the resource (`05-resource`) (ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

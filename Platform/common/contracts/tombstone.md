# The tombstone contract: the tombstone of a deleted body, neighbours, acknowledgements, removal

This English text is the source; the Russian translation `ru/contracts/tombstone.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): several processes write and read a tombstone — a contract,
not copies in chapters; the stage C guess C06-BLOB-GC-33-01 / IF-OBJECT-TOMBSTONE63-PEERS-01, the Architect's decision of 2026-10-25).
The owner is lesson [P/05](../../05-resource/spec/05-resource.norms.md) (N1.1 «Tombstones»; the family `.gone/<object-key>` —
[the catalogue](../data/catalog.tsv), the form — [`gone.schema.json`](../../05-resource/data/gone.schema.json), the outcomes —
[`gone.outcomes.tsv`](../../05-resource/data/gone.outcomes.tsv)). The participants are the console: it writes a tombstone at the completion of the body sweep
window ([P/06.1](../../06-console/spec/06.1-console.norms.md) N3 «body sweep»); the resource: it drops copies by the tombstones
of a neighbour, appends acknowledgements and removes the tombstone (P/05 N1.1 «Bodies at the resource», «Tombstones»).

Moved from P/05 N1.1 «Tombstones» (formerly M10/10 N1.5 `delete`) without a change of behaviour; new is the rule `peers`
(the section «Neighbours»): formerly the source and the completeness of the list were not named.

Normative keywords follow [the course canon](../../../NORMATIVE-TERMS.md).

## Form

```yaml
tombstone: .gone/<object-key> at the deleter — an object {written, peers, acked}: written = max(now, removed_written + 0.001) in wall seconds (one millisecond is one stamp unit of P/05 N1.1 `written`), peers —
           the neighbours of the ring that could have had a copy (the section «Neighbours»), acked — those who acknowledged, acked ⊆ peers (journal
           of cammeta-go, lesson 10 № 2); the object door has no DELETE; the door does not accept writes and deletes of .gone/
listing:   an ordinary listing does not show .gone/; /v1/objects?prefix=.gone/ is a read-only listing of tombstones;
           GET /v1/objects/.gone/<object-key> is the body of the tombstone, read only (C05-GONE-BODY-READ-01)
garbled:   an unreadable tombstone (gone.outcomes.tsv, the whole object) is an unknown outcome: a neighbour does not drop the copy,
           the deleter does not append acknowledgements and does not remove the tombstone; a new write of the key at the deleter is not refused:
           written by the former rules of P/05 N1.1 `written`, the tombstone stays until the next put of the console (bodies are addressed
           by content — the same write of the same bytes; nobody does drop by an unreadable tombstone; C05-WRITTEN-AFTER-GONE-02)
```

Files: the tombstone — `Platform/05-resource/data/gone.schema.json`, `Platform/05-resource/data/gone.outcomes.tsv`; the rows of doors
and of decommission requests (the section «Neighbours») — `Platform/05-resource/data/doors.schema.json`, `Platform/05-resource/data/doors.outcomes.tsv`,
`Platform/06-console/data/decommission.schema.json`, `Platform/06-console/data/decommission.outcomes.tsv`; the object door —
GET of a copy (404 — an acknowledgement), the listing `prefix=.gone/`, 409 «deleted later» — the contract
`Platform/05-resource/spec/05-resource.api.openapi.yaml` (layout audit, V-60; the Architect's decision of 2026-10-25).

The deleter retains the `written` of the exact body version admitted for deletion. It computes the deletion stamp before removing that version, with exact millisecond arithmetic: it is strictly greater than the removed version even when the wall clock is equal or has moved backwards. The sweep mark and the monotonic grace are admission checks, not the deletion stamp (ADR-0127, review of P/05 C1).

## Neighbours (`peers`)

The neighbours change over time (copies are put to the next `copies` live ones by name — P/05 N1.1 «Bodies at the resource»), therefore
`peers` is a superset of those who could have had a copy (C06-BLOB-GC-33-01, the Architect's decision of 2026-10-25):

```yaml
peers:     all servers <s> whose door row platform/doors/<s> is in the confirmed listing of the deleter, except its own
           server and the decommissioned ones — those whose row platform/decommission/<s> is in the confirmed decommission listing (the observation contract
           «Server decommissioned» narrower: here — only the request row)
           (P/06.6 N1.1, P/04 N3 «decommission_server»); a server — by the listing key, the readability of the row does not matter; a server without
           a copy acknowledges quickly (404)
unknown:   the door listing or the decommission listing is not confirmed (not received whole, a non-answer, unreadable) — the tombstone is not
           written and there is no deletion: the sweep waits (an unknown outcome is not a ground; P/06.1 N2 «Sweep window command», code 2)
silent:    a silent but not decommissioned server is in peers: the tombstone waits for its acknowledgement (the section «Removal»)
order:     the order of the elements of peers and acked is not normed; there are no repeats
```

## Reading by a neighbour

```yaml
drop:      a neighbour once per 10 min (the resource pass, P/05 N3) reads the tombstones of the deleter — finds them by the listing prefix=.gone/, by the body
           (GET .gone/<object-key>) takes written of the deletion: written of the listing is the mark of the tombstone write, it grows with each
           appended acked and does not name the deletion (C05-GONE-BODY-READ-01) — and drops its own
           copy older than written; a copy with source `written` strictly greater than the tombstone stays: the new write wins, and its source stamp is not raised on receipt. An existing copy is not a 404 acknowledgement. A copy than which the tombstone of the deleter is newer is not accepted (P/05 N4, «deleted later» — 409)
```

## Acknowledgement

```yaml
ack:       the deleter once per 10 min asks each of peers who is not in acked for a GET of the copy: 404 is an acknowledgement (the neighbour
           is appended to acked, cas); a copy exists, another answer or a non-answer — not (an unknown outcome is not an acknowledgement)
retired:   a neighbour from peers decommissioned after the tombstone was written (the row platform/decommission/<s> is in the confirmed
           decommission listing) counts as acknowledged: it is appended to acked without a GET of the copy; the decommission listing is not confirmed — not
           an acknowledgement (C06-BLOB-GC-33-01, the Architect's answer of 2026-10-25 (2))
```

## Removal

```yaml
rewrite:   an object with the same key is written at the deleter again after written (the resource gives the new write a written strictly greater than
           the written of the tombstone, P/05 N1.1 `written`; C05-WRITTEN-AFTER-GONE-01) — the tombstone is removed at once: without
           acknowledgements and without the term of 7 days (the key is live again; copies older than written are replaced by the new write; C06-BLOB-GC-33-01, the Architect's answer of 2026-10-25 (1));
           «at once» — on the write: a write of the key (a new body of the console, a copy of a neighbour through the resource door) removes the tombstone by the same action, before
           its answer, not by the resource pass — a read after the answer of the write does not see the tombstone (C05-GONE-REWRITE-AT-WRITE-01,
           the Architect's decision of 2026-10-30, norm questions of the Gemini audit, P/05 item 1)
remove:    otherwise the tombstone is kept for at least 7 days and is removed only when all peers have acknowledged the deletion (peers ⊆ acked);
           an unknown outcome is not an acknowledgement
```

## Vectors

The package [`tombstone`](../vectors/tombstone/README.md): `peers` — the door listing, the decommission listing, its own server → peers or
«no deletion»; `ack` — peers, acked, the answers of GET of the copy and the decommission listing → acked; `remove` — peers, acked, written, now, a write again →
remove or keep. The tombstone at the deleter — the listing `prefix=.gone/`, the body, 409 «deleted later», the removal on a newer write —
sc. 45 of the acceptance of P/05 (the tombstone is put by `@put object`); the dropping of a copy by a neighbour — reading; a stand with two resources — system
acceptance (P/05-11 — sc. 45 and by reading).

## Correspondence to former lessons

From P/05 N1.1 «Tombstones» (the block `delete`; the norm P/05-11 — by `note` of [id-map](../id-map.tsv)) and the line of P/06.1 N1.5
`delete`; they refer here. The section «Neighbours» is a new rule (C06-BLOB-GC-33-01 / IF-OBJECT-TOMBSTONE63-PEERS-01).

# The store client contract: address, request, answer, outcomes and what to do with each

This English text is the source; the Russian [`store-client.md`](../store-client.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): the store client is at all processes of the platform; a contract,
not copies in chapters; the stage C guess SC-WIRE78-G01 / C08-SDK-06, the Architect's decision of 2026-10-25). The owner is chapter
[P/01.1](../../../01-store/spec/01.1-store.norms.md). The participants are all processes that talk to the store through the door of P/01.1:
the console, the controller, the worker, the resource, the domain processes, the agent, the installer.

Moved from P/01.1 (the caller's side: Н1, Н2, Н2.1, Н3, Н4 «What the caller does») without a change of behaviour; the server's
side (parsing, the order of checks, operations, the repeat memory, codes) stays in P/01.1 and [P/01.3](../../../01-store/spec/01.3-store.norms.md);
P/01.1 refers here.

Normative keywords follow [the course canon](../../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The wire is the contract of the store door `Platform/01-store/spec/01-store.api.openapi.yaml`
([OpenAPI](../../../01-store/spec/01-store.api.openapi.yaml); it is part of the reading of `common` by ADR-0083 addendum (33) item 1): the routes
`GET /v1/get?key=`, `GET /v1/list?prefix=`, `POST /v1/write` (`Cmd`: `put` | `delete`; `BatchCmd`: `batch`), the schemas `Key`, `Row`, `Listing`,
`Cmd`, `BatchCmd`, `Written`, `Fault`. The row, the condition `cas`, the guard `guard`, the time conditions `not_after`/`not_before` and the `id` of a write are
the schemas `Row` and `Cmd` of the same OpenAPI (P/01.1 Н1; the client writes by them; layout audit, Б-05).

## Address

```yaml
address:   PLATFORM_STORE of the process (the environment file contract «Environment variables»): configstore:///run/configstore/<роль>.sock — HTTP/1.1 with JSON bodies over
           the Unix socket of the role; the identity is the socket the connection came to (P/01.2 Н1.1 identity); file:// and memory:// —
           a store inside the process of the same implementation (the profile «the whole box is one implementation»), the same semantics, no wire;
           the client has no other addresses — http(s) is not introduced (SC-WIRE78-G01, the Architect's answer of 2026-10-25 (1))
```

## Request

```yaml
query:     key and prefix — application/x-www-form-urlencoded (P/01.1 Н2.1): «+» of a key is sent as %2B, «%» — as %25;
           a parameter appears once; a listing prefix SHOULD end with «/» (testsub/count would also match testsub/counters/…)
id:        the client SHOULD put an id on every write — 32 hexadecimal characters of randomness (1–64 lowercase hex, P/01.1
           Н1); null is out of form (it is not equal to absence)
cas:       no field or null — unconditional; "" — only while there is no row; <version> — only while the version is exactly this one
guard:     {key, index}: index "" — the guard is absent; the rights to the guard row are the read rights of the caller
batch:     op: batch — {writes: [{op: put|delete, key, items?, cas?}], guards?: [{key, index}], id?, not_after?, not_before?} (P/01.1 Н1 batch):
           all or nothing, one version for all rows; at most BATCH_WRITES writes and BATCH_GUARDS guards (the role domain has no limit on the number of guards, on writes it has; the role console has no
           limit on the number); a key once; a guard on a written key is a form refusal
time:      not_after, not_before — JSON numbers in the notation «Time in a row» (Platform/common/data/codec.tsv row time; P/01.1 Н0), finite, ≥ 0
limits:    a key — at most 1024 bytes of UTF-8 of the full key (an implementation on files MAY have less — its description); the weight of items —
           at most 524288 bytes (the sum of the lengths of keys and values); the body of POST /v1/write — at most the body read limit
           named in the description of the store implementation (at the daemon — -max-body, default 1 MiB, P/01.3 Н1.3)
```

## Answer

```yaml
forms:     the answer forms are closed (P/01.1 Н2; the contract — the section «Form»): a readable row {items, index}; an absent one {items: null, index: ""};
           a damaged one {items: null, index, unreadable: true}; a listing {keys}; a write, delete or batch {index, again?};
           a refusal Fault {kind, error, the fields of its row of P/01.1 Н4}
index:     the version is opaque: the client compares it only for equality, does not parse it and does not order it; on the wire it is
           a decimal number without a sign and leading zeros, up to 20 digits, as a JSON string
unreadable: a damaged row exists and has a version: cas by this version and a guard by it pass (P/01.1-17); this is not
           the absence of the row
again:     again: true — the answer of a saved repeat of the same id: the write was already applied, the state did not change
```

## Outcomes and what the client does

The words and codes are P/01.1 Н4 (a closed list); the text of `error` is not normed.

| Outcome | Code, `kind` | What the client does |
|---|---|---|
| a key against the rules; a request out of form; no route | 400 `badkey`, 400 `badrequest`, 404 `badrequest` | nothing: a code bug |
| the identity is not admitted; no rights | 403 `forbidden` | fix the identity or the trust; no rights — a deployment bug |
| the version is not the one in `cas` | 409 `conflict`, `index` — the version now; for a batch also the `key` of this row | re-read, apply one's own on top, repeat |
| the reception time is later than `not_after` | 409 `expired` | do not repeat with the same write; a new one is decided by the caller by its own norm |
| the reception time is not later than `not_before` | 409 `early` | do not repeat with the same write; a new write — at the next step |
| the guard is not at that version (for a batch — the first one in the order of `guards`) | 412 `guard`, `key`, `index` | do not repeat: re-read the condition (the slot) and decide anew whether there is the right to write |
| the service `op: floor` (only the admin socket, P/01.3 Н2): the new value is not greater than the current one | 409 `refused` | nothing: the floor is already not lower (P/01.3 Н1.3); the outcome is `refused` by the form of the operation (C01-REFUSED-OUTCOME-01) |
| the row is heavier than the ceiling; the body is larger than the limit | 413 `toolarge`, `limit`, `size?` | nothing: something heavy — into an object (blob); the body — make it smaller, compare with the body limit |
| the operation is not done (no leader, a lock, the connection limit) | 503 `unavailable`, `Retry-After?` | repeat at the next step of the cycle (with `Retry-After` — not before the term); keep what you hold |
| the outcome of the write is unknown | 503 `ambiguous` | repeat only with the same `id`; whoever cares reads first |

```yaml
outcome:   outcome(operation, answer) for the client: an answer by the closed form of its operation — a readable row → row,
           an absent one → absent, a damaged one → unreadable, a listing → listing, a write, delete or batch → written
           (again: true — also written); Fault — its kind; no_reply below — unavailable (get, list) | ambiguous (write)
no_reply:  a truncated, unreadable (not by the closed answer form) or never arrived answer, a refused connection — for a read and
           a listing: unavailable, for a write, delete and batch: ambiguous; not «no» and not an exception that drops the cycle
wait:      the answer read limit and the answer wait term — decided by the client implementation, which names them in its description; the limit is
           not less than the largest answer the store may give by P/01: P/01 names no number (a row — the weight of items
           up to 524288 bytes, larger in JSON with escaping; a listing is not limited in the number of rows), therefore the limit
           of the client is not less than the answer of a row read at the weight ceiling and of a listing of its store; exceeding the limit or
           the term is no_reply: the outcome is unknown, the write is repeated only with the same id (SC-WIRE78-G01, the Architect's answer of 2026-10-25 (2))
retry:     after ambiguous a repeat is safe only with the same id: if the first one applied, the repeat answers with its answer (again);
           if not, it is applied as the first one; a repeat with the same id and other content — 400 badrequest
memory:    the store remembers an id for at least two minutes and at least 50 000 writes with id (P/01.1 Н3 «Replay by identifier»);
           a forgotten repeat is applied as a new write — therefore cas on every write that matters
```

## Vectors

The package [`store-client`](../../vectors/store-client/README.md): the outcome of an answer for the client — the operation and the answer (code and body, no
answer, a cut, a refused connection) → the outcome (the section «Outcomes and what the client does», `no_reply`). The wire (routes, parsing,
codes at the inputs) is the acceptance of lesson 01 ([P/01.1 Н5](../../../01-store/spec/01.1-store.norms.md)).

## Correspondence to former lessons

From P/01.1 Н1 (the fields `id` note, `index` note, `cas`, `guard`), Н2 (the address, the answer forms, a damaged row), Н2.1
(query encoding), Н3 «list» (prefix on «/»), «write» (the order for the caller, the repeat), «Replay by
identifier», Н4 (the column «What the caller does», the paragraph on a cut); they refer here.

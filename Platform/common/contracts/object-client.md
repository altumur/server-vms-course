# The object store client contract: the address, the operations, the answer of the resource door, the outcomes

This English text is the source; the Russian translation `ru/contracts/object-client.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): objects are written and read by all platform processes — a contract,
not copies in chapters; guess of stage C C10-OBJECT-ADDRESS-32, the Architect's decision of 2026-10-25). The owner is lesson
[P/05](../../05-resource/spec/05-resource.norms.md) (N1.1 «Object», N2). Participants: the worker (heartbeats, rival marks — P/03.2,
P/03.4), the controller (the snapshot, the pass report — P/04), the console (bodies — P/06.1), the resource (its own objects and the object door),
the domain processes (`domain/*`), the installer — the value of the address (P/02.4 N1.2; [the environment file contract](env-file.md)
«Environment variables»). The model is [the store client contract](store-client.md).

Moved from P/05 N1.1 (`api`, `ops`, `cluster`, `written`, the key and the prefix, the listing and the tombstones) and N2 (the answers of the object
door, `scope`, refusals) without a change of behaviour; the door side (request parsing, admission, the layout on disk, limits) is in
P/05, P/05 refers here.

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

The wire of the resource's object door is `Platform/05-resource/spec/05-resource.api.openapi.yaml`
([OpenAPI](../../05-resource/spec/05-resource.api.openapi.yaml); it enters the reading of `common` by ADR-0083 addendum (33) item 1):
`GET /v1/objects` (`ObjectListing`), `GET /v1/objects/{key}` (bytes, the headers `X-Written`, `X-Server`, `X-Missing`),
the refusals `ResourceError`, `ResourceDenied`. Tombstones `.gone/<object-key>` — [the tombstone contract](tombstone.md). The door row
`platform/doors/<host>` (the address of the read door with a bare `cluster://`, the section «Address» `door`) — the form
`Platform/05-resource/data/doors.schema.json`, the outcomes `Platform/05-resource/data/doors.outcomes.tsv`
([form](../../05-resource/data/doors.schema.json), [outcomes](../../05-resource/data/doors.outcomes.tsv); P/05 N1.4 `door_row`).

## Address

```yaml
address:   OBJECTS / PLATFORM_OBJECTS of the process (the environment file contract «Environment variables»; written by the installer into w2c.env,
           P/02.4 N1.2): file://<absolute path> — the object directory of the box; cluster://[<name>][?resource=<url>] — the objects
           of the cluster through the object door of the resource of its own server (P/05 N1.4 «Cluster objects — through the resource of its own server»);
           the default root — <PLATFORM_DIR>/objects (P/02.4 N1.2)
parse:     (C10-OBJECT-ADDRESS-32, the Architect's answer of 2026-10-25) a bare file:// — <PLATFORM_DIR>/objects; file://<a non-absolute path> — a start refusal, code 2;
           cluster:// — the part before «?» is empty or a cluster name, it is not interpreted; without resource=<url> (a bare cluster://, the
           default with configstore included — the environment file contract) — allowed: the read door is the resource of its own server by the door
           row (door below; P03-OBJECTS-DEFAULT-1FD, the Architect's decision of 2026-10-26);
           resource — exactly one, non-empty after percent-decoding; an empty or a repeated one — a start refusal, code 2;
           the value after decoding goes to the transport as is (OBJECT135-URL-01, the Architect's decision of 2026-10-25); an explicit
           resource overrides the door row — it is not read;
           another scheme — a start refusal, code 2
door:      (P03-OBJECTS-DEFAULT-1FD, the Architect's decision of 2026-10-26) with cluster:// without resource the address of the read door is the field url of the door row platform/doors/<SERVER_NAME>
           (P/05 N1.4 door_row; the form and the outcomes — the section «Form»); the row is read at every access to the cluster objects,
           the address is not remembered at start; there is no row, the row does not read (the outcomes of the form), the store did not answer — the reading
           of the cluster objects is «unknown», not «absent», not a start refusal and not a refusal of a write into its own directory
cluster:   with cluster://, a write goes into its own directory <PLATFORM_DIR>/objects (an object on the writer's server, P/05 N1.1 cluster),
           a reading of the cluster objects goes through the resource door resource (the section «Reading cluster objects»)
tls:       the resource door over https:// — the client of its own cluster of the role certificate contract own_client, the role resource: host —
           SERVER_NAME, if the host of the address is a loopback literal; an IP literal off the loopback with https:// — ip_address; http:// off the loopback —
           a configuration error, visible as a connection refusal (ADR-0075 addendum 2026-10-26 (4) item 6, (5) item 1, (6) item 2)
```

## Operations

```yaml
api:       put(key, bytes) | get(key) → bytes | null | list(prefix) → [key] (sorted, without service names with `~` —
           ADR-0083 addendum (16)) | delete(key) | put_new(key, bytes) → conflict, if it exists (create-once) | get_at/put_at
           (a write by the read index)
rule:      whole or not at all; the last writer wins; there is no search by key; the size — the limit of the store (0 = none)
ops:       put_new — «write if absent» (conflict when it exists); get_at — a read with the object index; put_at — a write by
           the read index (another index → conflict, like cas of a row); put_durable — a write of the whole body with a durability
           barrier before publication (the row refers to the body only after the answer — P/06.1 N1.5 write); delete_at —
           a delete by the read index (another index → conflict, the object is untouched); append — append an event line to
           an open bucket (only its writer, the event journal contract); there are no other atomicities
writer:    one directory — one writer; a write goes into the object directory of its own server (P/05 N1.1 cluster: a file on the server of
           the writer); an FS error after admission is not a success and not «no file»; the publication phase determines refusal or unknown durability (Q1 below)
key:       a non-empty relative path: non-empty segments, without exact `.`/`..`, backslash and control characters;
           prefix — the beginning of such a key, also emptiness or an ending `/`; it is not a full key
```

## Reading cluster objects

```yaml
scope:     for GET /v1/objects and /v1/objects/{key}: local (default) — only the object directory of the resource's server; cluster —
           the objects of the cluster: the fresh copy by written wins, on equal written — the server with the lexicographically greater
           name; another value — 400
written:   the mark of the keeper resource at the write of a key (X-Written, written of the listing), not a time field of the body; strictly grows
           per key; a new write of the same bytes is a new version, the same (server, written) is the same version (the
           observation contract «changed»)
missing:   a server that did not answer is missing (X-Missing), not the absence of the object; 404 — «absent among those that answered»: with
           an incomplete poll X-Missing is mandatory, completeness is not derived from the code 404 itself
listing:   the closed form ObjectListing; only the keys of the door families under prefix — a filter, not a refusal; deleted objects are
           tombstones .gone/<object-key>: the ordinary listing does not show them, prefix=.gone/ — a read-only listing of tombstones
```

For `scope=cluster`, the resource polls its local server and all foreign servers in a confirmed door listing, without a liveness filter. A known non-answer or unreadable door is missing: an otherwise readable listing returns 200 with missing, and key reads carry X-Missing when incomplete. An unconfirmed server set or failed local read/listing gives the existing 503, not a complete result. The implementation declares the finite dependency deadline under the common production obligations.

## Outcomes and what the client does

| Outcome | Code | What the client does |
|---|---|---|
| the key is not by the grammar (not UTF-8, Cc, Zl, Zp, `.`/`..`, an empty segment); `prefix` not UTF-8; `scope` another | 400 `ResourceError` | nothing: a code error |
| the key or the prefix outside the door families; the role is not admitted | 403 `ResourceError` / `ResourceDenied` | nothing: a code or deployment error |
| the object is absent among those that answered | 404 `ResourceError` | without `X-Missing` — there is no object; with `X-Missing` — unknown, not «absent» |
| the object exceeds Content-Length.maximum of the [P/05 HTTP form](../../05-resource/spec/05-resource.api.openapi.yaml) | 413 `ResourceError` | nothing: the door limit |
| the lane is busy; the door is unavailable | 503 `ResourceError`, `Retry-After: 1` | repeat at the next step |
| the condition of `put_at`, `put_new` or `delete_at` did not match (not an arbitrary filesystem failure) | conflict | re-read and decide anew |
| the resource door did not answer (a break, no answer, a connection refusal) | — | the reading is unknown, not «absent» (like `no_reply` of the store client contract; C10-OBJECT-ADDRESS-32, the Architect's answer of 2026-10-25) |
| a bare `cluster://`: the door row `platform/doors/<SERVER_NAME>` is absent, it does not read, the store did not answer | — | the reading is unknown, not «absent»; at the next access the row is read anew (P03-OBJECTS-DEFAULT-1FD, the Architect's decision of 2026-10-26) |

## Production obligations

ADR-0130 Addendum (10), Q1: a proven refusal before publication leaves the previous object intact. After `rename`, a failed durability barrier or lost answer leaves durability unknown; this is the existing outcome `unknown`, not proof of absence or a successful write. Do not promise rollback of published bytes or memory. For `put_new`, retain the exact key, intended bytes and create-once condition across resolution. A `conflict` alone proves no success: compare the existing operation index/version (including `(server, written)` where applicable) as well as key and bytes; identical bytes alone do not attribute the object to this attempt. For resolution, qualified readback must establish that exact intended object identity and its required durability; an absent, different, unreadable or unqualified readback leaves the outcome unknown. No new HTTP Fault is assigned to this local operation. The existing `ResourceError` and `ResourceDenied` door forms stay unchanged.

## Vectors

The package [`object-client`](../vectors/object-client/README.md): `address.tsv` — parsing of the address (a bare file://, an absolute and
a non-absolute path, cluster:// with resource and without, resource empty, repeated, percent-encoded, another scheme; a bare
cluster:// — the door by the door row of its own server, no row, does not read, the store did not answer — «unknown»; an explicit
resource overrides the row, P03-OBJECTS-DEFAULT-1FD); `read.tsv` — the class of the read outcome: the code, `X-Missing`, no
answer → the object, absent, unknown, a refusal.

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.

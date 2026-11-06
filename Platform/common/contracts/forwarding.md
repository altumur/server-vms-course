# The forwarding contract: headers between processes, forwarding by one function, refusals by transition

This English text is the source; the Russian translation `ru/contracts/forwarding.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13); analysis of review of stage A 8–10, № 23, № 14 /
decision 3). The path of a people door of the domain goes through up to three processes: the cluster console (forwarding, chapter 6.7 of the late layer of lesson
P/06), the domain console (accepting the forwarding and passing to the process, lesson P/10), the process `domain` (execution, lesson P/08). The transitions are
numbered one way in all norms (ADR-0083 addendum (19) item 2; analysis of review of ADR-0090, № 20): **transition 1** — the cluster console
of a member that does not hold the domain → the cluster console of the holder (`CLUSTERS`, `X-W2C-Via`); **transition 2** — the cluster console of
the holder → the domain console of its own box (`holds`, `view.url`); **transition 3** — the domain console → the process `domain`. A request to
the cluster console of the holder starts with transition 2. The codes by side are the section «Refusals by transition». The owner is lesson P/06, [chapter 6.7](../../06-console/spec/06.7-console.norms.md)
(N1.4, N1.5, N3 «accept by a console» are pointers here): forwarding is a function of the cluster console. The participants are the domain console (P/10: accepting
the forwarding, passing to the process — [norms of lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.3 `pass`, N1.4) and
the process `domain` (P/08: accepting and the answers — [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.8 `pass`, `answers`; reading
`X-W2C-Client` — P/08.0 N1.8; the limit by address — [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.10 `address`).

Moved from M11/8 N1.3 (the line `via`), N1.4 (the block in full), N3 «accept by a console» and M11/9 N1.10 (the line `header`) without
a change of behaviour; the section «Refusals by transition» is the Architect's decision of 2026-10-20 (decision 3: each OpenAPI carries
only its own codes), the codes in it are from the norms of the transitions, there are no new ones. The forwarding table is the section «Domain doors» below; the address (`holds`, `to`, `view.url`,
`CLUSTERS`), `where` of a member and forwarding to the signer are norms of the owner (P/06.7 N1.4, N1.6, N1.8); TLS between clusters —
P/06.7 N1.7, `peer` — [the `peer` contract](peer.md); the gate — [the gate-and-pass contract](gate-and-pass.md). References in the moved text: «N1.x»,
«N3» are of lesson M11/8 (at the line `header` — of M11/9); «lesson N» is lesson M11/N. Their addresses now (stage B, lesson 10): M11/8 N1.2 —
«Domain doors» below, N1.3 — P/06.7 N1.4, N1.4 — «Forwarding is one function» below, N1.5 — P/06.7 N1.6, N1.6 — P/06.7 N1.7 (`server.role` — P/10 N1.4), N1.7 — P/10 N1.6, N1.9 —
P/06.7 N1.8; «lesson 9 N1.5» — P/06.7 N1.9; «lesson 2 N1.8» — P/06.3 N1.8; «lesson 3 N1.8 pass» — P/10 N1.3; «lesson 10» (the terms of
the move) — P/08.8 N1.7, N1.8.

Normative keywords follow the [course canon](../../../NORMATIVE-TERMS.md).

## Form

The files the contract works by (layout audit, `V-20`–`V-22`; the Architect's decision of 2026-10-25):

- the domain view `domain/view` (`holds`, `view.url` of transition 2; 503 `domain console not known`) — the family `view`:
  `Platform/08-domain/data/view.schema.json`, `Platform/08-domain/data/view.outcomes.tsv`;
- the copy of the member list `domain/member-list/<part>` (503 `the list of members does not read`; `Entry.ca` of the destination for `tls`) —
  the family `member-list`: `Platform/09-agent/data/member-list.schema.json`, `Platform/09-agent/data/member-list.outcomes.tsv`;
- the refusal body of the gate `Denied` (401/403 at transitions 1 and 2) — `Platform/common/contracts/gate-and-pass.api.openapi.yaml`.

## Headers between processes

| Header | Set by | Read by | Section |
|---|---|---|---|
| `X-W2C-Via: <CLUSTER>` | the cluster console when forwarding to the console of another cluster (transition 1) | the receiving cluster console: if it came, the console does not forward to another cluster (400 `one hop`) | «One hop» |
| `X-Operator: console` | the cluster console on every forwarding — transition 1 and transition 2 (ADR-0083 addendum (19) item 2, № 20) | the domain console at transition 2 — only on a connection with the proven role `console` (the role door, P/10 N1.4 `server.role`); the cluster console at transition 1 does not recognize it; it is always removed (the class `signed`, P/06.7 N1.7 `server`; ADR-0083 addendum (18)) | «Forwarding is one function», «Accept by a console» |
| `X-W2C-Via-Worker: <sub>/<instance>` | the cluster console on forwarding by ticket (P/06.3 N1.9 «Domain doors»); the domain console passes it to the process `domain` | a declared sign: it serves neither as a right nor as a check, only the journal and an alarm. Transition 1 — the cluster console of the holder neither removes nor sets it: the leaf cannot be proven there (the class `signed`), the loss of the sign is more dangerous than a forgery. Transition 2 — the domain console removes it from an external request and accepts it only with the leaf of the role of the cluster console. The process `domain` — only on a connection of the role `domainconsole` | P/08.4 N1.3c `via_backend` |
| `X-W2C-Client: <address>` | the domain console when passing to the process `domain` (transition 3) | the process `domain` — only on a connection of the role `domainconsole` | «Client address» |
| `X-W2C-Pass-Policy: <digest>` | every console on a confirmed domain worker pass | every hop compares its own confirmed descriptor; no identity or authority | «Domain worker pass hop policy»; removed before the worker |
| `X-W2C-Ticket: <sub>` | the cluster console on forwarding `POST /domain/verify` by ticket (P/06.7 N1.15); the domain console passes it to the process `domain` | the domain console — only on a connection with the proven role `console`; the process `domain` — only on a connection of the role `domainconsole`; otherwise it is not read | «Ticket on forwarding» |
| `X-User` | nobody: one that came is always removed | — | [gate-and-pass contract](gate-and-pass.md) `x_user` |

### One hop

From M11/8 N1.3:

```yaml
via:          X-W2C-Via: <CLUSTER> is set by every forwarding to the console of another cluster; «X-W2C-Via came» — the header
              is present, an empty one included (added by the reconciliation of M11, D7); a console that received X-W2C-Via
              does not forward to the console of another cluster (400 one hop); to the domain console of its own box (holds) — it forwards
```

### Forwarding is one function

From M11/8 N1.4:

```yaml
request:      the method, the path and the query as they came; the path segments are decoded once, %2F creates no route level, the accepted
              encoded path and query are passed as they came (guess of stage C FW-G03, the Architect's decision of 2026-10-23); the body ≤ the body limit of the console ([gate-and-pass contract](../gate-and-pass.md) «The gate» `body`, 1 MiB): larger — 413, chunked —
              400, slow — 408 (P/06.5 N4); the body is never cut
pass:         Authorization, Content-Type, Idempotency-Key, If-Match — as they came, with the sole credential exception «First cookie transition to the domain» below (If-Match — ADR-0094 B4: the condition reaches the edit door of P/08.0 N1.9)
set:          X-Operator: console — on every forwarding: transition 1 and transition 2 (ADR-0083 addendum (19) item 2; analysis of review of
              ADR-0090, № 20); X-W2C-Via: <CLUSTER> — only to the console of another cluster (transition 1, N1.3);
              X-W2C-Via-Worker: <sub>/<instance> — on forwarding by ticket (P/06.3 N1.9 «Domain doors»)
never:        the other headers that came; X-User, X-Operator, X-W2C-Via that came never go further; X-W2C-Via-Worker at transition 1 passes as declared, at transition 2 — only from the leaf of the role of the cluster console, otherwise it is removed
x_operator:   the receiving console recognizes X-Operator: console (the value byte for byte: `Console` is not it; added
              by the reconciliation of M11, D16) only on a connection with the proven role console (the role certificate P/02.4 N1.6, N1.6 below).
              Such a connection exists only at the role door of the domain console at transition 2 (a connection without a role is refused there
              earlier — the role certificate contract «The server side: the class `role`»). The cluster console at transition 1 and for everything incoming from other clusters does not
              recognize it; it removes it always (the class signed, P/06.7 N1.7 server; the Architect's decision of 2026-10-21, ADR-0083
              addendum (18), addendum (19) item 2; analysis of review of ADR-0090, № 21, 27). An unrecognized X-Operator is removed before
              the gate, as any X-Operator and X-User that came (ADR-0075 item 3); a recognized one gives no rights — the gate
              decides by Authorization (lesson 9), it names in the journal of the receiving console that the request was forwarded by a console: the lines of
              audit/domainconsole about such a request carry the common field role: "console" (the event journal contract,
              door_journal); without a recognized header there is no field; there is no new kind and no new field (C10-XOPERATOR-JOURNAL-01)
answer:       the status, Content-Type, ETag, X-Unreachable and the body as they came, without parsing and wrapping (ADR-0061 addendum item 6; ETag — ADR-0094 B4);
              a body larger than FORWARD_MAX — 502 answer too large, nothing of the body goes out; no answer within FORWARD_WAIT or
              the network — 502 did not answer (and a handshake refusal by the server, the TLS alert of the role door N1.6 at transition 2 — the handshake did not
              take place: the network, without the word peer); the answer broke off — 502 answer broke off
FORWARD_MAX:  1 MiB
FORWARD_WAIT: the column «Wait» of the row of the table of the section «Domain doors» (the default 5 s); the doors of the move have their own terms: forwarding to the signer of its own
              box — 10 s at /api/prepare, 90 s at /api/take and /domain/move (P/06.7 N1.8 order step 5; P/08.8 N1.7, N1.8);
              the door route /domain/at — 20 s (P/06.7 N1.6 route); /domain/handover — 100 s (the table below), more than the 90 s of the answer of the process domain (P/08.8 N1.7 door) (layout audit B-19, the Architect's decision of 2026-10-25)
gate:         the gate of the forwarding console asks only who calls (any grant of this cluster or the row domain/anywhere, the right contract step 6; lesson 9 N1.5; loopback
              operator — the gate-and-pass contract «The gate» `open`), and does not ask at the open rows of the table (Identity «—»); what may be done is decided by the gate
              of the domain console or of the member
tls:          to https:// — a client of the role console (P/02.4 N1.6) with the server check peer (N1.6) by the destination member:
              the cluster console of the holder — the holder, the console of a member — the name from CLUSTERS (transition 1: host — from the URL); the domain
              console of its own box (transition 2, view.url) — a client of its own cluster, the role certificate contract own_client:
              peer with the fingerprints of its own ca.pem and ca.next.pem, the role domainconsole, host — SERVER_NAME if the host of view.url is
              a loopback literal, then revocation (ADR-0075 addendum 2026-10-26 (5) items 1, 3)
journal:      domain.forwarded {cluster, path, user, status} at the forwarding console: cluster — where to, path — the path that came,
              user — the name proven by the gate (before lesson 9 — operator), not X-User; status — the code of the answer or of the refusal (a handshake refusal of
              the role door — 502, as the network)
```

### Domain worker pass hop policy

This is the narrow exception for a confirmed `door.pass` route on the domain (P/10 N1.6), after the reserved platform routes have been matched. Ordinary platform forwarding keeps its existing row wait (normally 5 seconds), `FORWARD_MAX` 1 MiB, credentials and refusals. The 5-second table cell for the dynamic pass row is the transport interval used below, not a cap on a declared worker wait or a stream.

Every console on member console -> holder console -> domain console -> worker derives the same closed descriptor from its own validated, confirmed installed manifest and this request:

```json
{"sub":"testsub","method":"GET","path_b64":"YXBpL3g","kind":2,"wait":10,"stream":false,"max_bytes":4194304}
```

The keys are exactly `sub, method, path_b64, kind, wait, stream, max_bytes`. `sub` is the selected subsystem. `method` is the original method token. `path_b64` is unpadded base64url of the unchanged pass-path bytes after `/domain/<sub>/`, without the leading slash or query (the example is `api/x`). `kind` is 1 or 2. `wait` is the effective finite wait in seconds, or null for a stream; `stream` is boolean; `max_bytes` is 4194304 for a finite answer, or null for a stream. The first kind uses its existing `PASS_WAIT`; the second uses the longest covering declared wait key, otherwise `PASS_WAIT`, and its existing stream match. A policy is pinned for this request, not recomputed to extend a running deadline.

`X-W2C-Pass-Policy` is exactly one header field with exactly one lowercase 64-hex value: SHA-256 of UTF-8 JCS of that descriptor. Repeated fields, a comma list, uppercase hex, whitespace within the parsed digest value or any other spelling are malformed. A missing header is filled with the locally derived digest. Each hop, after the guards that it normally owes and before forwarding, computes its own policy and compares a present claim. Malformed spelling, unavailable/unconfirmed policy or a different digest gives the existing 503 `unavailable` form, without calling the worker, replacing the claim, downgrading or retrying another policy. Refusals mapped by the second-kind manifest retain their normal mapping. The claim is carried unchanged between consoles and removed before the worker; it is not returned as a credential.

The digest proves only consistency. It proves no identity, role, right, client certificate or trusted origin and cannot raise a local limit. Ordinary identity, need, may, cookie-CSRF, TLS, Authorization and first-cookie-hop rules remain mandatory, including on the signed listener without a client leaf. No guard acquires a substitute successful outcome from this header. Ordinary routes remove this header rather than taking this exception.

For a finite worker wait W, the domain console budgets W for the complete worker answer, the holder console budgets W + 2 × F for its domain-console request, and the member console budgets W + 4 × F for its holder-console request, where F is the existing 5-second forwarding transport interval of the pass row. The declared wait ceiling remains `PASS_WAIT_MAX` 9000 seconds; the transport allowances do not enlarge the worker's wait. Each hop uses its own monotonic elapsed deadline, without resetting it on a header, chunk or retry; no shared wall-clock deadline is inferred. A finite answer is buffered up to 4 MiB before exposing client headers at every hop, as required by the worker pass, rather than capped at `FORWARD_MAX`.

A stream has neither the 5-second response cap nor the 1 MiB/4 MiB body cap; connecting and TLS handshaking retain the ordinary transport bound. It is relayed as bytes arrive, without buffering the whole body. Before exposing client headers, failures use the existing own refusal: for the second kind, expiration before worker headers is 504; finite-body break, size and other transport refusals retain their specified codes. A peer refusal received in full is passed as received. After client headers are exposed, all hops propagate only bytes and closure: a break never appends, wraps or replaces them with a new `502` JSON body. Ordinary cancellation and the stream's revocation/disabled/expiry checks still close downstream work; they create no callback authority and do not release application write guards early.

The domain console still refuses an incoming `X-W2C-Pass-Ticket` with 401 and sends no `X-W2C-Pass-Console`; this exception creates no listener, callback door, JWT, X-User or credential and does not extend C06-PASS-COOKIE-01. The worker keeps its independent credential and epoch checks. The worker-side pass remains the [gate-and-pass contract](gate-and-pass.md).

### First cookie transition to the domain

G10-FORWARD-CREDENTIALS-01, the Architect's decision under ADR-0083. At the **first console transition toward the domain**, transition 1, 2 or 3 according to where the external request entered, the console sets `Authorization: Bearer <token>` only when all of these hold:

1. The ordinary `identity`, `need` and `may` checks of this request have succeeded.
2. The original request has passed its cookie-CSRF check under the gate-and-pass contract. Converting the credential does not turn an unchecked cookie request into a non-cookie request.
3. There is no incoming `Authorization` header, and the identity used for this request was proved by its person cookie session `w2c_token`.

The token is byte for byte the token proved by **that same cookie session**. A token of another session, a cache, another step, debug or break-glass is not a source. `Cookie` is never forwarded. An incoming `Authorization` is passed unchanged and is never supplemented or replaced from a cookie; an invalid presented credential is refused by the ordinary identity rule. A failed guard returns its ordinary refusal, without a forwarding call, a replacement credential or a fallback path. Later receivers verify the token independently; after the first conversion they receive an ordinary Bearer request and do not recreate a cookie session.

Debug does not create a JWT, `X-User` or a callback ticket. Its own read/worker doors keep their existing admission rules. A writer that independently requires a person token still requires it: a credential-free debug request cannot bypass that check. Its earlier standby/deposed/frozen and other operation guards retain their original order. This exception does not expand C06-PASS-COOKIE-01 (`door.pass` of the first kind to a worker), second-kind tickets or their callback rules.

The mandatory vectors are CALL seams in [P/06.7](../../06-console/acceptance/7/seams.tsv) for **both first transitions 1 and 2**, and in [P/10](../../10-domain-console/acceptance/seams.tsv) for first transition 3. They execute the ordinary gate and forwarding path and inspect actual outgoing requests; the fixture and observations are specified in [the forwarding seam protocol](../../10-domain-console/acceptance/README.md#forwarding-credential-seams). A P/10-only run does not cover the first-hop cluster-console obligation of P/06.7.

### Accept by a console

From M11/8 N3 «accept by a console (any console, before the guard)»:

```
1. X-User — remove ([gate-and-pass contract](../gate-and-pass.md) «The gate» `x_user`)
2. X-Operator: console (byte for byte) and a connection with the proven role console — keep for the journal; otherwise remove
   (the domain console at transition 2 — the role door, the role certificate contract «The server side: the class `role`»; the cluster console at transition 1 does not recognize it;
   it removes it always: the class signed, P/06.7 N1.7 server; ADR-0083 addendum (18), addendum (19) item 2)
```

### Client address

From M11/9 N1.10 `address` (the line `header`; what the process counts by address is the limit of entry attempts, [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.10):

```yaml
  header:  X-W2C-Client: <TCP peer address of the client> — set by the domain console when passing to the process domain; the process trusts it
           only on a connection of the role domainconsole (P/02.4 N1.6), on the others it does not read it; the role is proven by the certificate
           of the client: the listener of the process domain (SIGNER_URL) under TLS requests it as optional and checks a presented one
           in the handshake by the ca.pem, ca.next.pem of its own cluster — a foreign authority, the term, EKU without clientAuth —
           alert (P/02.4 N1.6 client_cert; the role certificate contract signer); the agents and relays of other clusters
           do not present it (the role certificate contract clients); the handshake passed, the role from SAN is domainconsole,
           the signatures are in the list sig, the serial is not in revoked → the header is read; otherwise (no certificate, another role, a signature
           outside sig, revoked, HTTP of the stand) — it is not read, the limit counts the address of the TCP peer (ADR-0083 addendum (20), addendum (21) item 4); on a stand without TLS the header is never trusted — a debt of the stand, not of the norm (added
           by the reconciliation of M11, cammeta-python M11-09 № 22); an X-W2C-Client that came from outside
           the console removes, as X-User (lesson 3 N1.8 pass; the Architect's decision by the reconciliation of M11, P16)
```

### Ticket on forwarding

ADR-0119 addendum (2) item 2: the process `domain` does not see the entries `calls`, and the cluster console forwards the domain doors with the token of the person.

```yaml
  header:  X-W2C-Ticket: <sub> — the subsystem of the ticket; set by the cluster console only on forwarding POST /domain/verify that came
           by a ticket with the entry domain/verify in calls (P/06.3 N1.9); the domain console reads it only on a connection with the proven role
           console (as X-Operator) and passes it to the process; the process reads it only on a connection of the role domainconsole (as
           X-W2C-Client); an X-W2C-Ticket that came from outside is removed by every console, as X-User. Unlike X-W2C-Via-Worker
           (declared, only the journal) this sign is an admission: without it POST /api/verify — 403 (P/08.4 N1.2a ticket)
```

## Domain doors

From M11/8 N1.2 «The forwarding table» without a change of behaviour (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 5):
the owner is this contract (P/06), the participants are the process `domain` (chapter [P/08.0](../../08-domain/spec/08.0-domain.norms.md)) and
the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N2); chapter 6.7 and N2 of lesson P/10 refer here. «lesson N» in the table is lesson M11/N.

A closed list. Each next lesson adds its doors to the table as a row «added by M11/N»; a door of the domain console
that is not in the table is a review finding (the Architect's decision on M11/8 item 1). «Wait» is the term of the answer of the domain console for this
row (M11/8 N1.4 `FORWARD_WAIT`, below «Forwarding is one function»); for the handover of lesson 10 (P/08.8 N1.7) it is greater than its 90 s. «Identity» «—» is an open row: the lesson whose door it is takes it
without an identity and a grant (the credential is in the body); the gate of the forwarding console does not ask it (M11/8 N1.4 `gate`).

| Method | Path | Lesson (M11/N — the source of the row; addresses — id-map) | Wait, s | Identity |
|---|---|---|---|---|
| GET | `/domain` | 1 N2 | 5 | yes |
| GET | `/domain/shadow` | 1 N2 | 5 | yes |
| GET | `/domain/<sub>/tables/<table>` (P/10 N1.2a; `tables` is a reserved name, `unit.rows` is never it, P/02.1) | 1 N2 | 5 | yes |
| GET | `/domain/<sub>/<rows>` (`<rows>` — `unit.rows` of the manifest of the directory; a manifest without `domain.ref` is forwarded, the holder answers 404 `not in the directory`, lesson 1 N2) | 1 N2 | 5 | yes |
| GET, POST | `/domain/members` | 3 N2 | 5 | yes |
| GET, POST | `/domain/batches` | P/08.3 N1.1b | 5 | yes |
| DELETE | `/domain/batches/<name>` | P/08.3 N1.1b | 5 | yes |
| GET | `/domain/members/<member>` | P/10 N1.2b | 5 | yes |
| DELETE | `/domain/members/<member>` | 3 N2 | 5 | yes |
| POST | `/domain/members/<member>/ca` | 8 N1.6 | 5 | yes |
| GET, PUT | `/domain/topology` | 4 N2 | 5 | yes |
| GET | `/domain/placement` | 6 N2 | 5 | yes |
| GET, PUT, DELETE | `/domain/placement/<sub>/<ref>` | 6 N2 | 5 | yes |
| POST | `/domain/<sub>/<rows>` | 6 N2 | 5 | yes |
| POST | `/domain/<sub>/<table>` (the key `domain.edit_tables`) | P/08.6 N1.3 | 5 | yes |
| DELETE | `/domain/<sub>/<table>/<name>` | P/08.6 N1.3 | 5 | yes |
| POST | `/domain/edits` | P/08.6 N1.3b | 5 | yes |
| POST | `/domain/edits/stranded` | P/08.6 N1.3a, P/08.8 N1.6 | 5 | yes |
| GET, POST | `/domain/folders` | P/08.5 N1.8 | 5 | yes |
| PUT, DELETE | `/domain/folders/<id>` | P/08.5 N1.8 | 5 | yes |
| GET, PUT | `/domain/memberof/<member>/<sub>/<rows>/<id>` | P/08.5 N1.8 | 5 | yes |
| GET | `/domain/folders/<id>/units` | P/08.5 N1.8 | 5 | yes |
| PUT, DELETE | `/domain/<sub>/<rows>/<ref>` | 6 N2 | 5 | yes |
| any | `/domain/<sub>/<door.pass segment of the manifest>[/…]` | 8 N1.7 | 5 | yes |
| GET, POST | `/domain/users` | 9 N2 (added by M11/9) | 5 | yes |
| PUT, DELETE | `/domain/users/<name>` | 9 N2 (added by M11/9) | 5 | yes |
| GET, POST | `/domain/groups` | P/08.4 N2 (ADR-0098) | 5 | yes |
| PUT, DELETE | `/domain/groups/<name>` | P/08.4 N2 (ADR-0098) | 5 | yes |
| GET, POST | `/domain/roles` | P/08.4 N2 (ADR-0098) | 5 | yes |
| PUT | `/domain/roles/<name>/lines` | P/08.4 N2 (ADR-0110 D-3) | 5 | yes |
| PUT, DELETE | `/domain/roles/<name>` | P/08.4 N2 (ADR-0098) | 5 | yes |
| POST | `/domain/batch` | P/08.4 N2 (ADR-0098 §6) | 5 | yes |
| GET | `/domain/grants` | 9 N2 (added by M11/9) | 5 | yes |
| PUT | `/domain/grants/<cluster>` | 9 N2 (added by M11/9) | 5 | yes |
| GET | `/domain/break-glass` | 9 N2 (added by M11/9) | 5 | yes |
| PUT | `/domain/break-glass/<cluster>` | 9 N2 (added by M11/9) | 5 | yes |
| POST | `/domain/revoke` | 9 N2 (added by M11/9) | 5 | — (the token in the body) |
| DELETE | `/domain/issued/<sub>/<kind>/<ref>` | P/08.2 N1.6a | 5 | yes |
| POST | `/domain/handover` | 10 N2 (added by M11/10) | 100 | yes |
| POST | `/domain/partial/close` | P/08.8 N1.8a | 5 | yes |
| GET | `/domain/<sub>/kept/<name>` | P/10 N1.2a | 5 | yes |
| GET | `/domain/relays/<relay>` | P/10 N1.2a | 5 | yes |
| GET | `/domain/<sub>/books/<book>/*/<part>` | P/08.5 N2 | 5 | yes |
| POST | `/domain/stranded/apply` | 10 N2 (added by M11/10) | 5 | yes |
| GET, PUT | `/domain/shared` | 11 N2 (added by M11/11) | 5 | yes |
| GET | `/domain/alarms` | 11 N2 (added by M11/11) | 5 | yes |
| POST | `/api/login` | 9 N1.2 (added by M11/9; the entry of people through the console) | 5 | — (the entry) |
| POST | `/domain/verify` (the domain console passes it to the process by the path `/api/verify`; only by ticket — «Ticket on forwarding») | P/08.4 N1.2a (ADR-0119) | 5 | yes (the token of the person who is the author) |

A row with `GET` also covers `HEAD` of the same path: it is forwarded as `HEAD`, the answer is the same code and headers without a body ([P/06.5](../../06-console/spec/06.5-console.norms.md) N2;
run 41). The same at `/domain/at/…` (M11/8 N1.5): `HEAD` — as `GET` of the same form, without a body (added by the reconciliation of M11, D2).

A path with a segment `.` or `..`, including one in the percent form (`%2e`, `%2E`, `.%2e`, `%2e%2e` and the like), is 404 `not a domain
route` before the gate, before forwarding and before the pass to the worker on the domain (N1.7); the segments are not normalized (added by the reconciliation of
M11, D4: the path `/domain/<sub>/<segment>/../members` would otherwise bypass the table).

Matching goes in order: `books` (its own: the book door `GET /domain/<sub>/books/<book>` by exactly this path, the tail `/*/<part>` is a row of the table, [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.1; layout audit `B-19`, the Architect's decision of 2026-10-25), `at` (its own), the rows of the table from top to bottom; `<sub>` is a subsystem of the directory
of this console; a segment `door.pass` that coincides with `books`, `kept`, `tables`, `placement`, `members`, `topology`, `shadow`, `at` is not
passed on the domain.

## Refusals by transition

The Architect's decision of 2026-10-20 (analysis of review of stage A 8–10, decision 3): the near transition gives the answer of a far transition as it
came (N1.4 `answer`; [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.8 `answers` — «the console does not recompute them»), therefore the client sees the codes of all transitions, and
each OpenAPI carries only the codes of its own transition and refers here for the codes of another one, without listing them. The codes are named by
side (ADR-0083 addendum (19) item 2; analysis of review of ADR-0090, № 20): «the codes of transitions 1–2» are of the forwarding cluster console,
«the codes of transition 2» are of the receiving domain console (with the pass to the process by transition 3), «the codes of transition 3» are of the process `domain`.

| Transition (side) | Process, OpenAPI | Its own codes and words | Norm |
|---|---|---|---|
| 1–2 — forwarding of `/domain/*` (forwarding) | the cluster console; [OpenAPI of lesson P/06](../../06-console/spec/06-console.api.openapi.yaml) (the paths of chapter 6.7) | 404 `not a domain route`; 413 / 400 / 408 body; 401 / 403 gate — who calls; 503 `domain console not known`; 400 `one hop`; 503 `the list of members does not read`; 404 `no domain here`; 503 `CLUSTERS does not read`; 404 `no console known`; 502 `did not answer`, `answer too large`, `answer broke off`; at `/domain/at/…` — 404 `not a route handed to a member`, `not another member`, `no such member`; at the signer — 404 `no signer here`, 502 `did not answer` | [P/06.7](../../06-console/spec/06.7-console.norms.md) N3 «forward», «at a member», N1.8, N4 |
| 2 — accepting and passing by transition 3 (receiving) | the domain console; [OpenAPI of lesson P/10](../../10-domain-console/spec/10-domain-console.api.openapi.yaml) | a handshake refusal of the role door (there is no HTTP answer); 401 `no_role`, 403 `no_role`, `wrong_role`, `bad_chain`; 401 / 403 / 503 gate; 404 `not a domain route` (the segment `.`/`..`); `door.pass` — the codes of «Pass» of the gate contract; the pass to the process — 502 at a break and at silence (as N1.4 `answer`) | [P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.4 `server.role`, N1.6; «Domain doors» above; P/10 N1.3 `pass`; [gate-and-pass contract](gate-and-pass.md) |
| 3 — execution (receiving) | the process `domain`; [OpenAPI of lesson P/08](../../08-domain/spec/08-domain.api.openapi.yaml) | the codes of its own door (N3 and N4 of the chapters of lesson P/08); 409 `deposed`; 503 `frozen`; 503 `standby` | the chapters of lesson P/08 by the door (the summary table [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N2); [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.6, N1.7; [P/08.10](../../08-domain/spec/08.10-domain.norms.md) N1.7 |

The doors of the process `domain` are described by the OpenAPI of lesson P/08; the doors of the cluster console — by the OpenAPI of lesson P/06 (the paths of chapter 6.7; the answers of
transitions 1–2 — `ForwardBadRequest`, `ForwardNotFound`, `ForwardFailed`, `ForwardUnavailable`, the answer as it came —
`ForwardAnswer`; the words — `DomainRefusal`), of the domain console — by the OpenAPI of lesson P/10 (there is no answer `Forwarded`: its own codes of
transition 2, the answers of the process — `$ref` to the OpenAPI of lesson P/08). They do not list the codes of other transitions but refer here.
A local refusal of a side goes by the refusal schema of the OpenAPI of its lesson: at the cluster console `ConsoleRefusal` `{detail, error}`, both
required (not `{error}` alone), at the domain console — the schema of lesson P/10; `detail` is a constant text of the implementation; the answer of
a far transition is unchanged (guess of stage C FW-G01, the Architect's decision of 2026-10-23).

## Vectors

There are no vectors: forwarding is checked by the scenarios of the acceptances of chapter 6.7, of lesson P/10 and of lessons P/08–P/09. (ADR-0083 addendum (32) item 2)

## Correspondence to former lessons

From M11/8 (analysis of review of stage A 8–10, № 23 / decision 3): N1.3 — the line `via` (here «One hop»; `holds`, `to`,
`view.url`, `CLUSTERS` stayed); N1.4 in full (here «Forwarding is one function»; in M11/8 — a pointer); N3 «accept by a console»
(here «Accept by a console»). From M11/9 N1.10 — the line `header` (here «Client address»). The rule
`X-W2C-Client` — by reference from [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.8 `pass` (accepting) and from lesson P/10 (passing,
N1.3; stage B, lesson 10). Parts of the norms M11/8-03, -04, -05,
-06 (chapter 6.7) and M11/9-09 — by `note` of the [id-map](../id-map.tsv).
From M11/8 N1.2 — «The forwarding table» in full (here «Domain doors»; the Architect's decision of 2026-10-20, ADR-0083 addendum (14)
item 5).

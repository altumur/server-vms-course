# A token requested by a member's ordinary worker (ADR-0074, supplement 5)

`local_handler(agent, sub, role)` is bound to one role's private Unix socket. The
role and declaring subsystem come from that binding; the body takes only `ref`.
A TCP connection is refused. The worker uses `WorkerTokenDoor(path).request(kind,
ref)`; it has neither the member key nor the issuer key.

The agent's `CarryClient` signs the request's original bytes and route with the
member key and the existing request signature/time mechanism. A relay verifies
the member signature before forwarding the same bytes, path and signature. It
cannot open the reply. The holder accepts only an admitted, unrevoked member,
a declared grant for the role and an assignment matching `placement.caller`.
All member links in the assignment must be admitted. The issuer derives the
subject, reference claim and audience itself; the caller supplies no target or
claims. Audiences are member names without prefixes.

The remote reply has `request_id`, `token` and `exp`. The token is sealed to the
member's admitted box key with AAD bound to the original route, request id and
expiry (JCS). A changed expiry or id cannot be used with the old ciphertext.
The client opens the token only after checking the returned request id and expiry.
Each retry has a fresh id and asks the current holder again. No response queue,
book row, publication, journal or backup stores the token.

The signer HTTP handler checks handover/deposition before issuing and uses its
current issuer. The local handler returns the result only on the requesting
connection. The role socket's filesystem ownership and access must be established
by deployment; constructing this handler alone does not provision a protected
socket or activate it in `domain.agent.main`.

This diff provides the request core, holder/relay HTTP handlers, agent method and
worker handle. The member process's role socket startup and the subsystem publisher,
consumer and spec switch are the next integration step. The intermediate branch
is not a completed migration window and must not be merged by itself.

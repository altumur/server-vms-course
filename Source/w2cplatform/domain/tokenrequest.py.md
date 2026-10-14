# A token requested by a member's ordinary worker (ADR-0074, supplement 5)

`local_handler(agent, role)` is bound to one role's private Unix socket. The
role comes from that binding; the unique kind identifies the declaring subsystem.
The body takes only `ref`.
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

The C3 target `centre` is read from the holder's authoritative `domain/topology`,
never its carried `domain/member-topology`. It requires a confirmed positive
revision and a valid centre: absent or malformed topology returns 409; an
unadmitted centre returns 403. A subsequent request uses the current topology.
Other target names stay closed; `star_centre` belongs to the separate C3b window.

The remote reply has `request_id`, `token` and `exp`. The token is sealed to the
member's admitted box key with AAD bound to the original route, request id and
expiry (JCS). A changed expiry or id cannot be used with the old ciphertext.
The client opens the token only after checking the returned request id and expiry.
Each retry has a fresh id and asks the current holder again. No response queue,
book row, publication, journal or backup stores the token.

The signer HTTP handler checks handover/deposition before issuing and uses its
current issuer. The local handler returns the result only on the requesting
connection.
The agent opens `open_role_doors` at startup and closes servers on shutdown.
`TOKEN_REQUESTS_DIR` unset disables issuance. Provisioned base is root:root 0755;
role directories are root:role-group 2770, sockets 0660. Unsafe owner, mode, group,
symlink or bind fails closed for that role, while carry and reports continue.
`installation` derives tmpfiles and agent groups from loaded grants, using
`cluster.rights.group`. Every request resolves its unique kind against the current
catalogue.

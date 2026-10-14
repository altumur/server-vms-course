# A token requested by a member's ordinary worker (ADR-0074, supplement 5)

`placement.target_fields` also accepts `star_centre`: the confirmed holder
topology's centre, only when the assigned `cluster` is in its `star` list.
A copy in `star` does not add an audience. The assignment remains unchanged.
The holder never derives this audience from the member's topology copy.

`local_handler(agent, role)` is bound to one role's private Unix socket. The
role comes from that binding; the unique kind identifies the declaring subsystem.
The body takes only `ref`.
A TCP connection is refused. The worker uses `WorkerTokenDoor(path).request(kind,
ref)`; it has neither the member key nor the issuer key.

The agent's `CarryClient` signs the request's original bytes and route with the
member key and the existing request signature/time mechanism. A relay verifies
the member signature before forwarding the same bytes, path and signature. It
cannot open the reply. The holder accepts only an admitted, unrevoked member,
a declared grant for the role and its declared scope.
For `placement`, the assignment must match `placement.caller` and every member link must be admitted. The issuer derives the
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


C4 adds the alternative `unit` binding, with exactly `ref_claim`,
`target_fields: [poll_home]` and `audience_claim`. The declaring subsystem's
`domain.ref` must be present in a unit in the caller's own accepted snapshot.
Only the immutable body named by its accepted report pointer proves that unit;
local objects, orphan reports and another member's units do not. Withdrawal in
its next accepted report removes that permission. A missing or malformed report
returns 403.

C6b permits `placement` and `unit` together: an existing assignment is authoritative;
only its absence permits unit scope. An invalid assignment never falls back. `scenario`
remains exclusive. Unit scope may name `sub` (default: this token owner), `caller`
(`self` by default, or `poll_home`) and targets `poll_home` and/or `centre`.
For `poll_home`, exactly one admitted member must report the reference in its
accepted immutable generation; the authenticated requester must be that member's
confirmed poll home. The target subsystem must declare `domain.ref`. A missing,
malformed, duplicate or withdrawn reference grants no token. Neither scope accepts
caller-supplied audience or claims.

`topology.poll_home(vars_, member, authoritative=False)` chooses `via[member]`,
then centre, then a valid current holder. A worker's local `domain/member`
identity chooses the original topology when it is the holder, otherwise the
carried copy. The target member never determines where that topology is read.
Holder services pass `authoritative=True`. Missing local identity or malformed
holder/topology raises ValueError; an absent policy falls back to the confirmed
holder. Issuance maps that error to 409 and refuses an unadmitted audience with
403. Replies and token storage remain ephemeral.

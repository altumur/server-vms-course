# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/tls/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

(the server side, session resumption, the handshake by `ca-certs`) and the fourth cluster. The form
of the directives was agreed by the Architect with «cammeta-acceptance» (2026-10-20); here are the data of «Specification»: the kit description,
the logical doors and clients, the closed outcome of a probe and the expectations. The directives are the section [«Domain stand»](../domain-stand.md#domain-stand) of the common acceptance README (the forms were introduced by lesson M11/8 — the column
«Lesson» of the dictionary; review analysis of stage B 8–10, № 22: M-1). The implementation profile declares `keys.tls_stand: 1`; without it the checks of this stand are not executed

### Original passage 2

the door `holder`, the client `m2-console`, a forwarded request with `X-Operator: console` → `{"handshake": "ok"}`, `http` — the answer

### Original passage 3

| Door | Client | Expectation | Norm |
|---|---|---|---|
| `holder` | `m2-console` | `{"handshake": "ok"}`, `http.body.error` ∉ {`no_role`, `wrong_role`, `bad_chain`} | `role`: the CA is in the union |
| `holder` | `null` | `{"handshake": "ok", "http": {"status": 401, "body": {"error": "no_role"}}}` | no client certificate — 401 |
| `holder` | `m2-domainagent` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "wrong_role"}}}` | steps 6–7 of peer: the role is not `console` |
| `holder` | `m2-no-role` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "no_role"}}}` | a leaf without a role |
| `holder` | `m2-sig-sha512` | `{"handshake": "ok", "http": {"status": 403, "body": {"error": "bad_chain"}}}` | the closed list `sig` — after the handshake |
| `holder` | `foreign-console` | `{"handshake": "alert", "http": null}` | the CA is outside the union |
| `holder` | `m2-expired` | `{"handshake": "alert", "http": null}` | the validity of the leaf |
| `holder` | `m2-server-only` | `{"handshake": "alert", "http": null}` | EKU without `clientAuth` |
| `holder` | `m3-console`, `m3` without `Entry.ca` (before a report with `tls_ca`) | `{"handshake": "alert", "http": null}` | the member is outside the union |
| `signer` | `null` | `{"handshake": "ok"}`, `http` — by the request signature (not 401 `no_role`) | `signer`: a client certificate is not required |
| `signer` | `hold-domainconsole` | `{"handshake": "ok"}`, `http` — as for `null` | its own CA, the role `domainconsole` (the stand does not observe `X-W2C-Client`) |
| `signer` | the leaf `domainconsole` of the next CA of `hold` (`ca.next.pem`) | `{"handshake": "ok"}`, `http` — as for `null` | rotation: the CA from `ca.next.pem`; **a debt of the stand** — below |
| `signer` | `hold-domainconsole-sig-sha512` | `{"handshake": "ok"}`, `http` — as for `null` | a signature outside `sig` — after the handshake, only `X-W2C-Client` (the stand does not observe it) |
| `signer` | `hold-domainconsole-expired` | `{"handshake": "alert", "http": null}` | the validity of the leaf |
| `signer` | `hold-domainconsole-server-only` | `{"handshake": "alert", "http": null}` | EKU without `clientAuth` |
| `signer` | `foreign-console` | `{"handshake": "alert", "http": null}` | the CA is not its own |
| `signer` | `m2-domainagent` | `{"handshake": "alert", "http": null}` | the CA of another cluster: its clients do not present a leaf here (the role certificate contract `clients`) |

### Original passage 4

A change of the union is seen by new connections: `@stop agent m2`, then `holder POST /domain/members/m2/ca {"ca": []}` (the grant
admin; the agent is stopped — its report with `tls_ca` would return the CA, [P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14) → the next probe
`holder` / `m2-console` — `{"handshake": "alert", "http": null}`; the return `{"ca": [<m2 fingerprint>], "ca_certs": [<PEM m2>]}` →
again `{"handshake": "ok"}`.

### Original passage 5

1. A positive control before the probe: the control server of the harness issues a session, the client presents it and gets
   `reused: true`. No — the check is not executed (the stand), not a failure of the implementation.
2. `holder` / `m2-console`, `save_session: s1` → `{"handshake": "ok", "reused": false}`; the outcome (a) `session_available:
   false` or (b) `session_available: true`.
3. With (b): `holder` / `m2-console`, `resume_session: s1` → `{"handshake": "ok", "reused": false}` (a full handshake).
4. Remove the CA: `@stop agent m2`, then `holder POST /domain/members/m2/ca {"ca": []}`, without restarting the server (the agent
   is stopped — its report with `tls_ca` would return the CA, [P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14).
5. `holder` / `m2-console` with a new connection → `{"handshake": "alert", "http": null}`; with (b) — also with `resume_session: s1` →
   `{"handshake": "alert", "http": null}` (there is no resumption: the ticket of the past session does not bring the CA back). With (a) the presentation
   is not executed and is not declared executed.

### Original passage 6

| Step | Expectation | Norm |
|---|---|---|
| `member m2 console GET /domain` (the CA of `m2` is in the union) | `200` — the answer of the domain console as it came (not 401/403 with the words `no_role`, `wrong_role`, `bad_chain`; ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 27) | `answer`, `tls` |
| after the removal of the CA of `m2` (below): the probe `holder` / `m2-console` — a direct connection of the console of a member with the role door of the holder | `{"handshake": "alert", "http": null}` | `server.role`: the CA of `m2` is outside the union |
| after the same removal: `member m2 console GET /domain`; the journal of the forwarding console | `200` — the answer of the domain console as it came, as in row 1; `domain.forwarded {cluster, path, user, status: 200}` | the removal of the CA is not the removal of the membership: transition 1 is the class `signed`, to the role door goes the console of the holder's cluster (P/10 N1.4 `server.role`); `journal` |
| `holder POST /domain/members/m2/ca {"ca": []}`, then `holder POST /domain/members/m2/ca {"ca": [<m2 fingerprint>]}` without `ca_certs` | both — `200`; there is no row `ca-certs` (removed by `[]`), the probe `holder` / `m2-console` → `{"handshake": "alert", "http": null}` — the member is outside the union while there are no certificates under the fingerprints | `admin`: «without ca_certs the row does not change» |
| `holder POST /domain/members/m2/ca {"ca": [<m2 fingerprint>], "ca_certs": [<PEM of the foreign CA>]}` | `400 {"error": "refused"}`; `Entry.ca` and the row `ca-certs` do not change | `admin`, N4: sha256 does not match |
| `holder POST /domain/members/m2/ca {"ca": [<sha256 DER of the m2-console leaf>], "ca_certs": [<PEM of the m2-console leaf>]}` | `400 {"error": "refused"}` — the leaf is not a CA (`CA:true`) | `admin`: «including CA:true (otherwise 400)» |
| `holder POST /domain/members/m2/ca` with the same `ca`, `ca_certs` twice | both — `200`, the `rev` of the second answer = the `rev` of the first + 1 | `admin`: «the same ca again — a new write» |

### Original passage 7

Rows 2–3 are steps (the Architect's decision of 2026-10-21 on № 14, the way was agreed with the TLS stage of «cammeta-acceptance»;
the edit «T edit» per ADR-0083 addendum (18): the former «502 at the forwarding console» and the journal with `status: 502` are removed — by the route of P/06.7 N1.4
to the role door of the holder goes the console of the cluster `hold`, whose CA is always in the union, not the console of `m2`). The positive
control of row 1 — before the removal, and right after it its journal by the same read as below: `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, status: 200, id: $positive_forward_id}` — bind `id` ([P/05](../../../05-resource/spec/05-resource.norms.md)
N1.3 `row`; the dictionary of «Domain stand» `$name`); then stop the agent of `m2` (`@stop agent m2`: the report of the agent will not return the CA into
the union) and `holder POST /domain/members/m2/ca {"ca": []}`; after this row 2 — the probe `@tls` of the door `holder`
by the client `m2-console`, row 3 — `member m2 console GET /domain` → `200`. The journal of the forwarding console (row 3) is read
by the regular door of the resource, without a new directive: `@until 30 member m2 resource GET
/events?kind=domain.forwarded&unit=audit/console&keep=newest&limit=1` → `200`, `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, user: <stand token name>, status: 200, id: @not($positive_forward_id)}`
([P/05](../../../05-resource/spec/05-resource.norms.md) N1.3 `query`, `row`): both forwardings give `200`, and without `@not` on `id`
the previous record of row 1 would give a false pass (the remark of «cammeta-acceptance» of 2026-10-21 on 967baf9ad).

### Original passage 8

| Step | Expectation | Norm |
|---|---|---|
| `member hold console GET /domain` (the original kit) | `200` | `answer`, `tls` |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <name>, status: 200, id: $hold_forward_ok}` | `journal` |
| `@tls-kit hold console foreign` | `ok` | — |
| `member hold console GET /domain` | `502 {"error": "did not answer", "detail": "!contains peer"}` — the role door refused the leaf of a foreign CA with the handshake | `answer`: a handshake refusal is the network; P/10 N1.4 `server.role` |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <name>, status: 502, id: @not($hold_forward_ok)}` | `journal`: a handshake refusal of the role door — 502 |
| `@tls-kit hold console hold` | `ok` | — |
| `member hold console GET /domain` | `200` | the return |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <name>, status: 200, id: @not($hold_forward_ok)}` — the record after the return (the record of the refusal — `status: 502`) | `journal` |

### Original passage 9

| Step | Expectation | Norm |
|---|---|---|
| `@tls`: the door `member m1 console`, the client `foreign-console`, the request `GET /domain` | `{"handshake": "ok"}` | `signed`: does not refuse by the CA |
| `@tls`: the door `member m1 console`, the client `null`, the request `GET /domain` | `{"handshake": "ok"}` | `signed`: does not require a client certificate |
| `@person -`, then `member m1 console @header X-Operator: console GET /domain/users` | `401` — the gate: there is no token, the header does not serve as an identity | `x_operator`, P/06.7 N1.9 |

### Original passage 10

| Step | Expectation | Norm |
|---|---|---|
| `@kit-start console named` | `ok` — the console with a kit listens on the `CONSOLE_HOST` default `127.0.0.1` | P/02.4 N1.6 `console`: TLS on the loopback too |
| `@tls`: the door `kit`, `url` `https://127.0.0.1:{port}`, the client `null`, `GET /healthz` | `{"handshake": "ok", "peer": "ok"}` | `own_client`: a loopback literal — `host` = `box-n`, the leaf carries `box-n` |
| `@tls`: the door `kit`, `url` `https://localhost:{port}`, the client `null`, `GET /healthz` | `{"peer": "wrong_name", "http": null}` | `loopback`: `localhost` is a name; the leaf does not have it; the system host of the stand is not touched |
| `@kit-start domainconsole none` | `@exit 2` | `DOMAIN_CONSOLE_HOST` the default `0.0.0.0` without a kit — a start refusal (N1.6 `console`, `process`) |
| `@kit-start domain none` | `@exit 2` | there is no `SIGNER_HOST` — the process default `0.0.0.0` is not an explicit address: without a kit — a start refusal ((5) item 4) |
| `@kit-start domain none SIGNER_HOST=0.0.0.0` | `ok ~domain listens on ~without a certificate kit` | an explicit address outside the loopback without a kit — a start with a loud line (N1.6 `process`) |
| `@kit-start console none TIMEZONE=` | `@exit 2` | [the environment file contract](../../contracts/env-file.md) `TIMEZONE`: an empty value is not in form (ADR-0094 B6; P/06.3-06) |
| `@kit-start console none TIMEZONE=+03:00` | `@exit 2` | the same: the value is outside the grammar |
| `@kit-start console none TIMEZONE=Etc/GMT+5` | `ok` | the value is in form; a console on the loopback does not need a kit, so the `@exit 2` of the rows above was caused by the variable itself |
| `@kit-start console none TIMEZONE=No/Such_Zone` | `ok` | only the form is checked: the console does not read the zone database |

### Original passage 11

The preparation: `@clusters hold m1 m2 m3`, `@domain m1 m3`; the keepers with `BACKUP_HOLDERS` 2 — `m3`, `m1` (the order by descending
sha256 «hold/\<member>»: `m3`, `m1`, `m2`; confirm it on the live state — the rows `domain/keepers/<member>` of the holder,
[P/08.8 N1.5](../../../08-domain/spec/08.8-domain.norms.md)); `@until` of the backup copy at both keepers; only then — the admission of the target `m2` by the same steps as
`@domain`: `@start agent m2`, the admission by the fingerprint from `knocking` (`POST /domain/members`), `@join m2`, `@until` `m2` — `ok` and
it holds the set of the holder. So `m2` is never a keeper for a single pass and has no backup copy of its own: with
`@domain m1 m2 m3` the member admitted earlier than the others managed to become a temporary keeper, and no one throws away the copy at a member
(P/08.8 N1.5; without `copy` the move would restore it — N1.8 step 6 — instead of a refusal; the finding ER of cammeta-go on 3e65002,
the class «data», the Architect's assignment of 2026-10-22). Then `@until` at `m2` of a term record ≥ 1 (following,
[P/09.1](../../../09-agent/spec/09.1-agent.norms.md) N3) and of the backup copy at both keepers; then `@stop domain`.

### Original passage 12

- **«A neighbour did not answer»** (ER, added by the Quint model of M11): `@cut-route m2 hold console`, `@cut-route m2 m1 console`,
  `@cut-route m2 m3 console` — no neighbour answers (the holder holds its copy `domain/backups/rev-N` and would otherwise give
  it out); `@start domain on m2`; `@move m2` (without `copy` and `why`) → `409 {"error": "refused", "detail": "~did not answer"}`;
  there is no new term: `@move m2 why=…` on **another instance** of the same preparation → `200 {"holder": "m2", "restored_from":
  null}`, the term — the previous one + 1.

### Original passage 13

**Item 7 — the handshake by `ca-certs`** ([P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; [P/10 N1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`): after the row `ca-certs` and `Entry.ca`
a forwarded request of the member's console with `X-Operator: console` at the role door → `{"handshake": "ok"}`, `http` — the answer
of the door per the gate (not 401/403 with the words `no_role`, `wrong_role`, `bad_chain`).

### Original passage 14

- The door of the class `role`: the CA of the member in the union — `{"handshake": "ok"}`, `http.body.error` ∉ {`no_role`, `wrong_role`, `bad_chain`}; no client certificate — `{"handshake": "ok", "http": {"status": 401, "body": {"error": "no_role"}}}`; steps 6–7 of peer, the role is not `console` — 403 `wrong_role`; a leaf without a role — 403 `no_role`; a signature outside the closed list `sig` — 403 `bad_chain` after the handshake; a CA outside the union, an expired leaf, EKU without `clientAuth`, a member outside the union — `{"handshake": "alert", "http": null}`.

### Original passage 15

- The door of the class `signed` (the listener `SIGNER_URL`): a client certificate is not required, `http` is by the request signature (not 401 `no_role`); a presented leaf of its own CA passes the handshake, `http` — as without a certificate (the stand does not observe `X-W2C-Client`); a leaf of the CA from `ca.next.pem` — the same (rotation; **a debt of the stand** — below); a signature outside `sig` — after the handshake, only `X-W2C-Client` (the stand does not observe it); an expired leaf, EKU without `clientAuth`, a CA that is not its own, the CA of another cluster (its clients do not present a leaf here, the role certificate contract `clients`) — `{"handshake": "alert", "http": null}`.

### Original passage 16

A change of the union is seen by new connections: after `POST /domain/members/<member>/ca {"ca": []}` (the grant admin; the agent is stopped — its report with `tls_ca` would return the CA, [P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14) the next probe of the member's console — `{"handshake": "alert", "http": null}`; the return of `ca` and `ca_certs` → again `{"handshake": "ok"}`.

### Original passage 17

A positive control before the probe: the control server of the harness issues a session, the client presents it and gets `reused: true`. No — the check is not executed (the stand), not a failure of the implementation. A session is saved by `save_session` and presented by `resume_session`; a presented session is a full handshake (`reused: false`), with or without `session_available`. After the removal of the CA (without restarting the server; the agent is stopped — its report with `tls_ca` would return the CA, [P/08.3 N1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14) a new connection and the presentation of a session are `{"handshake": "alert", "http": null}`: there is no resumption, the ticket of the past session does not bring the CA back. Without a usable session (`session_available: false`) the presentation is not executed and is not declared executed.

### Original passage 18

- A forwarded request with the CA of the member in the union: `200` — the answer of the domain console as it came (not 401/403 with the words `no_role`, `wrong_role`, `bad_chain`; ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 27): `answer`, `tls`.
- After the CA of a member is removed, a direct connection of the console of this member with the role door of the holder — `{"handshake": "alert", "http": null}`: `server.role`, the CA is outside the union.
- The forwarding of this member still gives `200`, the answer of the domain console as it came, and the journal of the forwarding console records `domain.forwarded {cluster, path, user, status: 200}`: the removal of the CA is not the removal of the membership: transition 1 is the class `signed`, to the role door goes the console of the holder's cluster (P/10 N1.4 `server.role`); `journal`.
- `POST /domain/members/<member>/ca {"ca": []}`, then with a fingerprint and without `ca_certs`: both — `200`; there is no row `ca-certs` (removed by `[]`), and the probe of this member → `{"handshake": "alert", "http": null}` — the member is outside the union while there are no certificates under the fingerprints (`admin`: «without ca_certs the row does not change»).
- A certificate in `ca_certs` that does not match the fingerprint — `400 {"error": "refused"}`; `Entry.ca` and the row `ca-certs` do not change (`admin`, N4: sha256 does not match); a leaf instead of a CA — `400 {"error": "refused"}` — the leaf is not a CA (`admin`: «including CA:true (otherwise 400)»); the same `ca`, `ca_certs` twice — both `200`, the `rev` of the second answer = the `rev` of the first + 1 (`admin`: «the same ca again — a new write»).

### Original passage 19

- `own_client`: for a loopback literal in `url` the `host` is the `server` of the kit and the leaf carries it — `{"handshake": "ok", "peer": "ok"}`; `localhost` is a name, the leaf does not carry it — `{"peer": "wrong_name", "http": null}` (`loopback`); the system host of the stand is not touched.

### Original passage 20

- **«A neighbour did not answer»** (ER, added by the Quint model of M11): with no neighbour answering (`@cut-route` of all neighbours; the holder holds its copy `domain/backups/rev-N` and would otherwise give it out), `@move` without `copy` and `why` → `409 {"error": "refused", "detail": "~did not answer"}`, there is no new term; `@move` with `why` on another instance of the same preparation → `200` with `restored_from: null`, the term — the previous one + 1.

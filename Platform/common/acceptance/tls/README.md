# The TLS stand and the fourth cluster — acceptance data of lessons 8–10

This English text is the source; the Russian translation `ru/acceptance/tls/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The debts of the stand of lessons 8–10 per ADR-0083 addendum (9) (the owner's decision, 387a71377): TLS between clusters
(the server side, session resumption, the handshake by `ca-certs`) and the fourth cluster. The form
of the directives was agreed by the Architect with «cammeta-acceptance» (2026-10-20); here are the data of «Спецификация»: the kit description,
the logical doors and clients, the closed outcome of a probe and the expectations. The directives are the section [«Стенд домена»](../README.md#domain-stand) of the common acceptance README (the forms were introduced by lesson М11/8 — the column
«Урок» of the dictionary; review analysis of stage B 8–10, № 22: M-1). The implementation profile declares `keys.tls_stand: 1`; without it the checks of this stand are not executed
(not GREEN). Norms: the server side of the class `signed` — the role certificate contract «The server side: the class `signed`»
([P/08.0 Н1.6](../../../08-domain/spec/08.0-domain.norms.md), P/08.0-02), the listener `SIGNER_URL` — the row `signer` of the same contract and
[P/02.4 Н1.6](../../../02-installer/spec/02.4-installer.norms.md) `client_cert` (ADR-0083 addendum (20), addendum (21)); the CA fingerprints of a member, `on_accept`, `admin` —
[P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md); `client`, `first` and the function `peer` — [the contract `peer`](../../contracts/peer.md);
forwarding — [the forwarding contract](../../contracts/forwarding.md); the class `role` — [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`
(P/10-11); the role certificate contract — [`role-certificate.md`](../../contracts/role-certificate.md); the move —
[P/08.8 Н1.8](../../../08-domain/spec/08.8-domain.norms.md). Item 3 and «the holder of a previous build» from item 7 are a check by reading
([P/08.4 Н5](../../../08-domain/spec/08.4-domain.norms.md) and [P/08.3 Н5](../../../08-domain/spec/08.3-domain.norms.md)).

## Kits: [`stand.json`](stand.json)

The runner materializes the kits per the description at the moment of `@tls-setup` (before the stand is created), by its own clock: there are no ready keys in
the course, the validity periods always suit the real time. The keys are test ones only; they do not get into the run report.

| Field | Meaning |
|---|---|
| `version` | the form of the description, `1` |
| `server` | the server name of all clusters of the stand (`localhost`): the clusters differ by name, CA, ports and directories |
| `defaults.ca` | the CA of a cluster: the key (`ec-p256`), the signature (`sha256` — ECDSA with SHA-256), `not_before` — seconds from the moment of issue (negative — in the past), `days` — the validity from `not_before`; `CA:true`, `keyCertSign`, `cRLSign`; self-signed |
| `defaults.leaf` | a role leaf per the role certificate contract `cert`: CN `<роль>.<server>`, SAN DNS `<server>`, SAN URI `urn:w2c:role:<роль>` — exactly one, EKU `serverAuth` + `clientAuth`, `days` 825; signed by the CA of its own cluster |
| `clusters` | a cluster → the roles of its kit: the CA of the cluster and a leaf for each role; the layout — the contract `kit` (`ca.pem`, `<роль>/server.pem`, `<роль>/server.key`) in the `W2C_TLS_DIR` of the cluster; `revoked` is empty, there is no `ca.next.pem` |
| `foreign` | the roles of the kit of a «foreign» CA: its own CA, which no cluster publishes (`tls_ca`) or holds |
| `named` | the kit of one box with another server name (ADR-0075 addendum 2026-10-26 (4) item 7): its own CA, the role leaves `roles` with CN `<роль>.<server>` and SAN DNS `server` (`box-n`), not `localhost`; the layout — the contract `kit`; the other clusters do not trust its CA. Only `@kit-start` uses it |
| `negative` | client leaves for probes: `issuer` — the cluster whose CA signs; `role` — the role of the leaf; the other fields replace the default of the leaf: `uri: null` — without SAN URI, `eku` — its own set, `sig` — the signature of the leaf (`sha512` — ECDSA with SHA-512, outside the closed list of the contract `sig`), `not_before`, `days` — its own validity |

The CA fingerprint is the sha256 hex of DER ([P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `fingerprint`). The runner names to each cluster its kit directory
(`W2C_TLS_DIR`) and the initial fingerprint of the holder (`DOMAIN_CA` next to `DOMAIN_URL`, [the contract `peer`](../../contracts/peer.md) «Client and first contact» `first`). The publication of
`tls_ca`/`tls_ca_certs` is the business of the implementation per the norm: the stand does not substitute them.

## Doors and clients of the probe `@tls`

| Door | What | Class (the role certificate contract «Серверная сторона»; `role` — P/10 Н1.4 `server.role`) |
|---|---|---|
| `holder` | the domain console on `hold` — the reception of forwarding with `X-Operator: console`; by the route of P/06.7 Н1.4 its client is the console of the cluster `hold`, a direct connection of the console of a member is the probe `@tls` (ADR-0083 addendum (18)) | `role` |
| `signer` | the process `domain` on `hold` — `POST /api/member/<член>`, `GET /api/carry/<член>` | `signed`, the listener `SIGNER_URL`: requests a client certificate optionally, checks a presented one in the handshake (the role certificate contract `signer`; ADR-0083 addendum (20), addendum (21)) |
| `member <кластер> console` | the console of the cluster (`/domain/at/…`, forwarding) | `signed` for incoming from other clusters: does not request a client certificate, strips `X-Operator: console` ([P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.7 `server`; ADR-0083 addendum (18)) |
| `callback <кластер>` | the callback listener of the console of the cluster, the port `{cport}` | a mandatory role leaf of the subsystem, the role certificate contract «The callback leaf»; the main listener above does not change (ADR-0094 addendum (16)); the probes — by the directive `@pass-call` of the [stand of the pass of the second kind](../pass/README.md), the kits — its `stand.json` |

`@tls-kit <кластер> console <комплект>` — the replacement of the kit of one console of a cluster (the form was agreed by the Architect with
the TLS stage of «cammeta-acceptance» 2026-10-21; ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 22). The runner stops only the console of the cluster
`<кластер>` and starts it again with the previous port, data and environment, except its kit directory
(the `W2C_TLS_DIR` of this process); the processes `domain`, `domainconsole`, the agent and the published `Entry.ca`, `ca-certs` do not
change. The kit `<кластер>` is the original kit of the cluster (a return). The kit `foreign` is a rotation to a foreign CA
(the role certificate contract `rotation`): `ca.pem` and `revoked` — the original ones of the cluster, `ca.next.pem` — the CA of `foreign`,
`console/server.pem`, `console/server.key` — the leaf of the role `console` of the CA of `foreign` (the contract `cert`). So the console
still checks the domain console of its own box by its own `ca.pem` (the forwarding contract `tls`), while it itself presents the leaf
of a foreign CA; the server gives the leaf and its CA from `ca.next.pem` (the role certificate contract «Серверная сторона»). While
`foreign` is in place, the client of the stand checks the server of this console (the door `member <кластер> console`) by the CAs of the kit (`ca.pem`
and `ca.next.pem`), the other doors — as before; the other clusters do not go to this console during these steps. The expectation is `ok`: the console
listens again; a wrong form of the directive — the class «data», the stop, the start and the tool — the class «stand».

A client is the name of a leaf: `<кластер>-<роль>` (`m2-console`, `m2-domainagent`, `foreign-console`) or a key of `negative`
(`m2-no-role`, …); `null` — without a client certificate. The client of a probe presents the indicated leaf on any certificate request
by the server, regardless of the list of CAs in the request; the server did not request a certificate — it does not send the leaf (ADR-0083 addendum (20), addendum (21) item 9).
The client checks the server by the CA of the cluster of the door (`client` of the contract `peer`);
an error of this check is an outcome of the tool, not a TLS alert.

## Outcome of a probe — the closed form

```json
{"handshake": "ok" | "alert", "version": "TLSv1.2" | "TLSv1.3" | null, "reused": true | false,
 "session_available": true | false, "http": null | {"status": <код>, "body": <JSON | text>}}
```

- `handshake: ok` — the handshake is completed, `http` is the answer of the door to the `request` of the probe (the full form — the contract of the door).
- `handshake: alert` — the server refused with the handshake (TLS alert): `http: null`; `version` — the chosen version or `null` if
  the refusal is before the choice; `reused: false`, `session_available: false`.
- `reused` — a session is presented and the server resumed it; `session_available` — the server issued a usable session (a ticket or
  an identifier) over this connection.
- A connection refusal, a break, a timeout, an error of the server check by the client and an error of the tool are the class «stand»: they are not an outcome
  of the probe and do not satisfy any expectation. The text of the library and the number of the alert are diagnostics, not a word
  of the implementation.

The expectation in a scenario row is `ok <JSON>` (the dictionary of «Стенда домена», `@tls`); the JSON is compared by a subset of fields on top of the closed form.

## Expectations

The preparation of all probes: `@clusters hold m1 m2 m3` (item 9 — the fourth cluster; for items 2, 7, 8 `hold m1 m2` is enough),
`@tls-setup …/stand.json`, `@domain m1 m2` (or `m1 m2 m3`), then `@until` of the member's record: for `m2` — `Entry.ca` with
the fingerprint of the CA of `m2` and the row `domain/members/m2/ca-certs` (`on_accept`, the admission of a report with `tls_ca`, `tls_ca_certs`).

**Item 7 — the handshake by `ca-certs`** ([P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`): after the row `ca-certs` and `Entry.ca`
the door `holder`, the client `m2-console`, a forwarded request with `X-Operator: console` → `{"handshake": "ok"}`, `http` — the answer
of the door per the gate (not 401/403 with the words `no_role`, `wrong_role`, `bad_chain`).

**Item 2 — the server side** (the rows of the door `signer` — the class `signed`, the listener `SIGNER_URL`: P/08.0-02, P/02.4 Н1.6
`client_cert`, the role certificate contract `signer`; ADR-0083 addendum (20), addendum (21) item 9; the rows of
`holder` — the class `role`, P/10 Н1.4 `server.role`):

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

A debt of the stand (ADR-0083 addendum (20), addendum (21) item 9): the kit description `version` 1 does not issue a next CA (the clusters have no `ca.next.pem`),
so the row «the leaf of the next CA of `hold`» is not executed and is not declared executed; it is closed
by a form of the description with the next CA of a cluster — the data of «Спецификация», the directive — the TLS stage of «cammeta-acceptance».

A change of the union is seen by new connections: `@stop agent m2`, then `holder POST /domain/members/m2/ca {"ca": []}` (the grant
admin; the agent is stopped — its report with `tls_ca` would return the CA, [P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14) → the next probe
`holder` / `m2-console` — `{"handshake": "alert", "http": null}`; the return `{"ca": [<отпечаток m2>], "ca_certs": [<PEM m2>]}` →
again `{"handshake": "ok"}`.

**Item 8 — resumption** (P/10 Н1.4 `server.role`: it does not resume sessions; the Architect's decision of 2026-10-20 — both
outcomes pass):

1. A positive control before the probe: the control server of the harness issues a session, the client presents it and gets
   `reused: true`. No — the check is not executed (the stand), not a failure of the implementation.
2. `holder` / `m2-console`, `save_session: s1` → `{"handshake": "ok", "reused": false}`; the outcome (a) `session_available:
   false` or (b) `session_available: true`.
3. With (b): `holder` / `m2-console`, `resume_session: s1` → `{"handshake": "ok", "reused": false}` (a full handshake).
4. Remove the CA: `@stop agent m2`, then `holder POST /domain/members/m2/ca {"ca": []}`, without restarting the server (the agent
   is stopped — its report with `tls_ca` would return the CA, [P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `on_accept`; the Architect's decision of 2026-10-21, as № 14).
5. `holder` / `m2-console` with a new connection → `{"handshake": "alert", "http": null}`; with (b) — also with `resume_session: s1` →
   `{"handshake": "alert", "http": null}` (there is no resumption: the ticket of the past session does not bring the CA back). With (a) the presentation
   is not executed and is not declared executed.

**Forwarding through the role door and the branches of `admin`** (review analysis of stage B 8–10, № 14; review analysis of stage A 8–10, № 36).
The data of «Спецификация»; the steps and the scenario are written by the TLS stage of «cammeta-acceptance»; until then — a debt of the stand. The preparation — as for item 2.
Norms: [the forwarding contract](../../contracts/forwarding.md) «Forwarding is one function» `answer`, `journal`, `tls`;
[P/06.7 Н1.7](../../../06-console/spec/06.7-console.norms.md) `server` (transition 1 — the class `signed`);
[P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md) `admin`, Н4; [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role`.

| Step | Expectation | Norm |
|---|---|---|
| `member m2 console GET /domain` (the CA of `m2` is in the union) | `200` — the answer of the domain console as it came (not 401/403 with the words `no_role`, `wrong_role`, `bad_chain`; ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 27) | `answer`, `tls` |
| after the removal of the CA of `m2` (below): the probe `holder` / `m2-console` — a direct connection of the console of a member with the role door of the holder | `{"handshake": "alert", "http": null}` | `server.role`: the CA of `m2` is outside the union |
| after the same removal: `member m2 console GET /domain`; the journal of the forwarding console | `200` — the answer of the domain console as it came, as in row 1; `domain.forwarded {cluster, path, user, status: 200}` | the removal of the CA is not the removal of the membership: transition 1 is the class `signed`, to the role door goes the console of the holder's cluster (P/10 Н1.4 `server.role`); `journal` |
| `holder POST /domain/members/m2/ca {"ca": []}`, then `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>]}` without `ca_certs` | both — `200`; there is no row `ca-certs` (removed by `[]`), the probe `holder` / `m2-console` → `{"handshake": "alert", "http": null}` — the member is outside the union while there are no certificates under the fingerprints | `admin`: «without ca_certs the row does not change» |
| `holder POST /domain/members/m2/ca {"ca": [<отпечаток m2>], "ca_certs": [<PEM центра foreign>]}` | `400 {"error": "refused"}`; `Entry.ca` and the row `ca-certs` do not change | `admin`, Н4: sha256 does not match |
| `holder POST /domain/members/m2/ca {"ca": [<sha256 DER листа m2-console>], "ca_certs": [<PEM листа m2-console>]}` | `400 {"error": "refused"}` — the leaf is not a CA (`CA:true`) | `admin`: «including CA:true (otherwise 400)» |
| `holder POST /domain/members/m2/ca` with the same `ca`, `ca_certs` twice | both — `200`, the `rev` of the second answer = the `rev` of the first + 1 | `admin`: «the same ca again — a new write» |

Rows 2–3 are steps (the Architect's decision of 2026-10-21 on № 14, the way was agreed with the TLS stage of «cammeta-acceptance»;
the edit «Т-правка» per ADR-0083 addendum (18): the former «502 at the forwarding console» and the journal with `status: 502` are removed — by the route of P/06.7 Н1.4
to the role door of the holder goes the console of the cluster `hold`, whose CA is always in the union, not the console of `m2`). The positive
control of row 1 — before the removal, and right after it its journal by the same read as below: `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, status: 200, id: $positive_forward_id}` — bind `id` ([P/05](../../../05-resource/spec/05-resource.norms.md)
Н1.3 `row`; the dictionary of «Стенда домена» `$имя`); then stop the agent of `m2` (`@stop agent m2`: the report of the agent will not return the CA into
the union) and `holder POST /domain/members/m2/ca {"ca": []}`; after this row 2 — the probe `@tls` of the door `holder`
by the client `m2-console`, row 3 — `member m2 console GET /domain` → `200`. The journal of the forwarding console (row 3) is read
by the regular door of the resource, without a new directive: `@until 30 member m2 resource GET
/events?kind=domain.forwarded&unit=audit/console&keep=newest&limit=1` → `200`, `events[0]` ⊇ `{kind: domain.forwarded,
cluster: hold, path: /domain, user: <имя токена стенда>, status: 200, id: @not($positive_forward_id)}`
([P/05](../../../05-resource/spec/05-resource.norms.md) Н1.3 `query`, `row`): both forwardings give `200`, and without `@not` on `id`
the previous record of row 1 would give a false pass (the remark of «cammeta-acceptance» of 2026-10-21 on 967baf9ad).

**№ 14, the handshake refusal of the role door on transition 2** (ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 22; the data — «Спецификация», the directive
`@tls-kit` — «cammeta-acceptance»). Norm: the forwarding contract `answer` — a handshake refusal of the role door on transition 2 is
the network, `502 did not answer` without the word `peer`; `journal` — `status: 502`. The input is the console of the cluster `hold` directly from the stand:
the request goes by transition 2 to the role door of its own box. The journal — `@until 30 member hold resource GET
/events?kind=domain.forwarded&unit=audit/console&keep=newest&limit=1` (further — «the journal of hold»); `<имя>` — the name of the token
of the stand.

| Step | Expectation | Norm |
|---|---|---|
| `member hold console GET /domain` (the original kit) | `200` | `answer`, `tls` |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 200, id: $hold_forward_ok}` | `journal` |
| `@tls-kit hold console foreign` | `ok` | — |
| `member hold console GET /domain` | `502 {"error": "did not answer", "detail": "!contains peer"}` — the role door refused the leaf of a foreign CA with the handshake | `answer`: a handshake refusal is the network; P/10 Н1.4 `server.role` |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 502, id: @not($hold_forward_ok)}` | `journal`: a handshake refusal of the role door — 502 |
| `@tls-kit hold console hold` | `ok` | — |
| `member hold console GET /domain` | `200` | the return |
| the journal of hold | `200`, `events[0]` ⊇ `{kind: domain.forwarded, cluster: hold, path: /domain, user: <имя>, status: 200, id: @not($hold_forward_ok)}` — the record after the return (the record of the refusal — `status: 502`) | `journal` |

**№ 14, the class `signed` of the console of a cluster** (ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 23). Norm: [P/06.7 Н1.7](../../../06-console/spec/06.7-console.norms.md)
`server` — everything incoming from other clusters on the listener of the console of a cluster: it does not request a client certificate, does not refuse by the CA
in the handshake, does not recognize `X-Operator: console`; it always strips it (the forwarding contract `x_operator`).

| Step | Expectation | Norm |
|---|---|---|
| `@tls`: the door `member m1 console`, the client `foreign-console`, the request `GET /domain` | `{"handshake": "ok"}` | `signed`: does not refuse by the CA |
| `@tls`: the door `member m1 console`, the client `null`, the request `GET /domain` | `{"handshake": "ok"}` | `signed`: does not require a client certificate |
| `@person -`, then `member m1 console @header X-Operator: console GET /domain/users` | `401` — the gate: there is no token, the header does not serve as an identity | `x_operator`, P/06.7 Н1.9 |

## The client of its own box and the address defaults (ADR-0075 addendum 2026-10-26 (4) item 7, (5) item 4)

Norms: [the role certificate contract](../../contracts/role-certificate.md) «The client of a door of its own cluster» (`own_client`,
`loopback`); [P/02.4 Н1.6](../../../02-installer/spec/02.4-installer.norms.md) `process`, `console`; Н1.12 and the lifecycle of
P/08, P/10 (the address defaults). The directive `@kit-start` — the dictionary of «Стенда домена» of the common README (the form was agreed with
«cammeta-acceptance» 2026-10-26). The preparation — `@tls-setup …/stand.json` (the kit `named`); the steps do not require
`@domain` and the clusters of the domain stand: the process starts alone, on the box of the stand with its store and manifests.

The probe `@tls` with the door `kit` goes to the process of the last `@kit-start`: the input `{door: "kit", url, client, request}`, `url` — the address
of the connection with the substitution `{port}` (the port of the door of this process). The client of the stand checks the server as a client of its own
cluster (`own_client`): the CA fingerprint of the kit, the role of the process, `host` — the `server` of the kit if the host of `url` is
a loopback literal (the threshold `loopback`), otherwise the host of `url`; then revocation (the `revoked` of the kit is empty). The outcome is the closed form above
with the field `peer`: `"ok"` or a word of the contract `peer`; on a word the client closes the handshake — `handshake: "ok"` (the server did not refuse), `http: null`, `version` may be `null`. The server refused with the handshake — `handshake: "alert"`, `peer: null`, `http: null`. A refusal of the check
of the server at the door `kit` is an outcome of the probe, not the class «stand» (at the other doors — as before). The client judges the steps of `peer` over the handshake chain: a leaf without a CA in `chain[1:]` — `foreign_ca` (step 3). Of the words the table names `wrong_name`; the other words are not judged by the acceptance, except `peer: "ok"`.

| Step | Expectation | Norm |
|---|---|---|
| `@kit-start console named` | `ok` — the console with a kit listens on the `CONSOLE_HOST` default `127.0.0.1` | P/02.4 Н1.6 `console`: TLS on the loopback too |
| `@tls`: the door `kit`, `url` `https://127.0.0.1:{port}`, the client `null`, `GET /healthz` | `{"handshake": "ok", "peer": "ok"}` | `own_client`: a loopback literal — `host` = `box-n`, the leaf carries `box-n` |
| `@tls`: the door `kit`, `url` `https://localhost:{port}`, the client `null`, `GET /healthz` | `{"peer": "wrong_name", "http": null}` | `loopback`: `localhost` is a name; the leaf does not have it; the system host of the stand is not touched |
| `@kit-start domainconsole none` | `@exit 2` | `DOMAIN_CONSOLE_HOST` the default `0.0.0.0` without a kit — a start refusal (Н1.6 `console`, `process`) |
| `@kit-start domain none` | `@exit 2` | there is no `SIGNER_HOST` — the process default `0.0.0.0` is not an explicit address: without a kit — a start refusal ((5) item 4) |
| `@kit-start domain none SIGNER_HOST=0.0.0.0` | `ok ~domain listens on ~without a certificate kit` | an explicit address outside the loopback without a kit — a start with a loud line (Н1.6 `process`) |
| `@kit-start console none TIMEZONE=` | `@exit 2` | [the environment file contract](../../contracts/env-file.md) `TIMEZONE`: an empty value is not in form (ADR-0094 B6; P/06.3-06) |
| `@kit-start console none TIMEZONE=+03:00` | `@exit 2` | the same: the value is outside the grammar |
| `@kit-start console none TIMEZONE=Etc/GMT+5` | `ok` | the value is in form; a console on the loopback does not need a kit, so the `@exit 2` of the rows above was caused by the variable itself |
| `@kit-start console none TIMEZONE=No/Such_Zone` | `ok` | only the form is checked: the console does not read the zone database |

## The fourth cluster — the ER branches (item 9; [P/08.8 Н1.8](../../../08-domain/spec/08.8-domain.norms.md) step 6)

The preparation: `@clusters hold m1 m2 m3`, `@domain m1 m3`; the keepers with `BACKUP_HOLDERS` 2 — `m3`, `m1` (the order by descending
sha256 «hold/<член>»: `m3`, `m1`, `m2`; confirm it on the live state — the rows `domain/keepers/<член>` of the holder,
[P/08.8 Н1.5](../../../08-domain/spec/08.8-domain.norms.md)); `@until` of the backup copy at both keepers; only then — the admission of the target `m2` by the same steps as
`@domain`: `@start agent m2`, the admission by the fingerprint from `knocking` (`POST /domain/members`), `@join m2`, `@until` `m2` — `ok` and
it holds the set of the holder. So `m2` is never a keeper for a single pass and has no backup copy of its own: with
`@domain m1 m2 m3` the member admitted earlier than the others managed to become a temporary keeper, and no one throws away the copy at a member
(P/08.8 Н1.5; without `copy` the move would restore it — Н1.8 step 6 — instead of a refusal; the finding ER of cammeta-go on 3e65002,
the class «data», the Architect's assignment of 2026-10-22). Then `@until` at `m2` of a term record ≥ 1 (following,
[P/09.1](../../../09-agent/spec/09.1-agent.norms.md) Н3) and of the backup copy at both keepers; then `@stop domain`.

- **«A neighbour did not answer»** (ER, added by the Quint model of М11): `@cut-route m2 hold console`, `@cut-route m2 m1 console`,
  `@cut-route m2 m3 console` — no neighbour answers (the holder holds its copy `domain/backups/rev-N` and would otherwise give
  it out); `@start domain on m2`; `@move m2` (without `copy` and `why`) → `409 {"error": "refused", "detail": "~did not answer"}`;
  there is no new term: `@move m2 why=…` on **another instance** of the same preparation → `200 {"holder": "m2", "restored_from":
  null}`, the term — the previous one + 1.
- **«There is no copy anywhere, all answered»** (without `why` — 409, with `why` — «from nothing») and **«there is neither a record nor a copy»** (step 6,
  `nothing to restore from`): on the public doors of the stand they are unreachable deterministically — the first backup copy is made
  by the first pass of the holder, the holder and the keepers give it out; a member without a term record does not receive grants either (the identity
  of the move). Removing the copies by the preparation of the stand is not possible either: the backup copies are objects (`domain/backup` at a keeper,
  `domain/backups/rev-*` at the holder; P/08.8 Н1.5), the admin operations of the store delete rows (only the pointer
  `domain/backup-taken` can be removed), there is no common contract for deleting objects; the stand does not touch the private files of the implementation (agreed with
  «cammeta-acceptance», the Architect's decision of 2026-10-20). A check by reading — [P/08.8 Н5](../../../08-domain/spec/08.8-domain.norms.md) («Checked by reading», step 6
  of the move), like item 3; the acceptance README of [chapter 8.8](../../../08-domain/acceptance/8/README.md), sc. 03.

# The role certificate contract: form, signatures, kit, revocation

This English text is the source; the Russian [`role-certificate.md`](../role-certificate.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5); the Architect's decision on the review of stage B 1–2, item 4). The owner is lesson
[P/02](../../../02-installer/spec/02.4-installer.norms.md), chapter 2.4 Н1.6 (the center, the role kits, the address rule; ADR-0083 addendum (29) item 9: the line names the lesson that owns the norm; the library by the contract is written by the session `common` of the generation). The
certificates are issued by the installer ([P/02.4 Н1.6](../../../02-installer/spec/02.4-installer.norms.md): the center, `w2c-ca.sh`, the role kits,
the address rule); the peer is verified by every door between processes — the store daemon
([P/01.3 Н1.6](../../../01-store/spec/01.3-store.norms.md)), the role doors ([P/02.4 Н1.6](../../../02-installer/spec/02.4-installer.norms.md)
`doors`) and the domain doors (lessons P/08–P/10; analysis of review of stage B 8–10, № 22); the server side of the doors
between clusters of the class `signed` is the section «The server side: the class `signed`» (the participants are the process `domain`, chapter P/08.0,
the relay, [P/09.2](../../../09-agent/spec/09.2-agent.norms.md) Н1.6, P/09.2-07, and the cluster console — everything incoming from other
clusters on its listener, [P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.7 `server`; ADR-0083 addendum (18), addendum (19) item 2; the class is divided by
listener: the listener `SIGNER_URL` of the process `domain` requests the client certificate optionally and verifies a presented
one, the other participants do not request it — ADR-0083 addendum (20), addendum (21)). Moved from P/01.3 Н1.6
(formerly М10/11 Н1.6) without a change of behaviour: which roles each door admits stays in the norm of that door.

Normative keywords follow the [course canon](../../../../НОРМАТИВНЫЕ-СЛОВА.md).

```yaml
cert:         CN <роль>.<server>; SAN DNS <server>; SAN URI urn:w2c:role:<роль> — exactly one role; serverAuth + clientAuth;
              825 days; the center 10 years; the roles configstore and configstore-door — with no other; the extension profile
              of the center and the leaf and the terms in seconds are the issue rule P/02.4 Н1.6 ca; the verifier does not require them beyond the contract peer of steps 2–5
              and of the class signer (guess of stage C RC-03, the Architect's decision of 2026-10-23)
sig:          the signatures of the certificates of the center, the intermediates and the leaves — a closed list: ECDSA P-256 and P-384 with SHA-256 or
              SHA-384, RSA ≥ 2048 bits — PKCS#1 v1.5 and PSS with SHA-256 or SHA-384, Ed25519; another signature —
              the chain is not verified (added by the reconciliation of М11, D14, cammeta-python М11-08 № 21)
kit:          /etc/w2c/tls/ca.pem, revoked | crl.pem, <роль>/server.pem, <роль>/server.key (the key 0600 owned by the unit's user or 0640 root:<the group of the unit's user> by ADR-0075 add.3; the directory 0750 root:<the group of the unit's user>, not the group of the role socket — P/02.4 Н1.1 `dirs`, Н1.6 `identity.doors`)
              # /etc/w2c/tls — the root W2C_TLS_DIR on Linux (the section «The cluster kit…» below; analysis of review of stage B 8–10, № 4)
revoke:       the serials in revoked — are copied to every server; the processes reread by content; configstore leave at the leader
  file:       revoked — UTF-8 text, lines separated by LF; a line is one certificate serial: hex digits (0–9, a–f, A–F) without «0x»,
              a sign and separators; case does not matter; comparison by the integer value — leading zeros are not significant (00ff and FF are
              one serial); there is no decimal notation (123 is the serial 0x123); an empty line and a line that starts
              with «#» are skipped; the last line MAY be without LF; a repeated serial is not an error (vectors
              common/vectors/revoked; guess of stage C S01, the Architect's decision of 2026-10-23)
  bad_file:   any other line (a space, «0x», «:», CR, a character outside hex, not UTF-8) makes the whole file invalid: the former
              content is not used; new connections where revoked decides admission are rejected — the refusal is closed (the door
              of the store P/01.3 Н1.6, the role door — the class role below, the worker door on the domain P/03.7 Н1.6); where revoked decides only
              the reading of X-W2C-Client (the listener SIGNER_URL, signer below), the header is not read; a log line and a count of invalid
              rereads (the place of the count is the lesson of the door; a lesson that names no /metrics series counts by log lines — one per
              invalid reread or outdated CRL, not more often than one per change of the file content; C01-TLS-COUNT-PLACE-01); a correct file is read again without a restart — by content,
              as every reread of revoked
  absent:     neither revoked nor crl.pem (kit: «revoked | crl.pem») — as an invalid file: the refusal is closed; with crl.pem
              the absence of revoked is not an error — revocation by crl.pem (the Architect's decision of 2026-10-23 on a question of «Спецификации»)
  crl:        crl.pem — PEM, one or two blocks X509 CRL v2, one per center from ca.pem and ca.next.pem; a block is signed
              by its center with an algorithm of the closed list sig; the serial of a leaf is checked against the CRL of its issuer — serials
              are unique only at the issuer, a leaf of another center with the same serial is not revoked by this CRL (guess
              of stage C RC-05); no block of a center is not an error, the leaves of this center are checked only against revoked; the file is invalid,
              as bad_file (the refusal is closed to new connections, a log line and a count), only at a defect of form (not PEM, not
              X509 CRL), of signature (an issuer not from ca.pem and ca.next.pem, a foreign signature, a signature outside sig), an extra block
              (a second block of the same center), delta CRL, indirect CRL, a scope restricted by issuingDistributionPoint, and
              an unknown critical extension; the dates of a CRL give no refusal: no nextUpdate, now later than nextUpdate or
              thisUpdate later than now by more than 60 s — a log line and a count, the list is in force (revoked has no term; a refusal
              by date would close all doors of the cluster); the issue — P/02.4 Н1.6 ca crl (vectors common/vectors/crl; guesses
              of stage C RC-02, S03, RC-06 — both generators, the Architect's decision of 2026-10-23 on a note of «Спецификации»)
  both:       there are both revoked and crl.pem — the revoked ones are the union: a leaf is revoked if its serial is in revoked (globally,
              by the integer value) or in the CRL of its issuer (crl); either of the two invalid — the refusal is closed, as bad_file (guesses of stage C RC-01, RC-05, the Architect's decision of 2026-10-23)
rotation:     ca.next.pem next to it — the next center, already trusted
```

## Form

`Entry.ca` is a field of the member record `domain/member-rows/<раздел>`: `Platform/08-domain/data/members.schema.json`, `Platform/08-domain/data/members.outcomes.tsv`; the fields `tls_ca`, `tls_ca_certs` of the publication `POST /api/member` — `Platform/08-domain/spec/08-domain.api.openapi.yaml`, `Platform/09-agent/spec/09-agent.api.openapi.yaml` (layout audit, `В-55`, `В-56`; the Architect's decision of 2026-10-25). The class `role`: the row `domain/members/<член>/ca-certs` — `Platform/08-domain/data/member-ca-certs.schema.json`, `Platform/08-domain/data/member-ca-certs.outcomes.tsv`; the refusal of the role door — the schema `RoleRefusal` `Platform/10-domain-console/spec/10-domain-console.api.openapi.yaml` (C10-SDK-ROLE83, the Architect's decision of 2026-10-25).

## The cluster kit, the domain roles, the center between clusters

From P/02.4 Н1.2 (`W2C_TLS_DIR`), P/02.4 Н1.6 `roles`, P/10 Н1.4 `roles` and P/08.3 Н1.6 (`fingerprint`, `tls_ca`,
`tls_ca_certs` — the member's side, `Entry.ca` — the form) without a change of behaviour: analysis of review of stage A 8–10, № 15; analysis
of review of stage B 8–10, № 4 (ADR-0083 addendum (15)) — lesson P/09 takes them from the contract, not from the norms 8.x and lesson P/10 (step 13
of the reading order). The owners of the text stay the same and refer here; the holder's side (`form`, `on_accept`, the row
`ca-certs`, the door `admin`) — [P/08.3 Н1.6](../../../08-domain/spec/08.3-domain.norms.md).

```yaml
W2C_TLS_DIR:  the root of the kits kit (above): Linux /etc/w2c/tls, macOS <W2C_BOX>/tls (ADR-0075; the environment file contract «Environment variables»); the paths of kit are
              from it: <W2C_TLS_DIR>/ca.pem, ca.next.pem, revoked | crl.pem, <роль>/server.pem, <роль>/server.key
domain_roles: the roles of the kits of the domain processes: the process domain — domain; the domain console — domainconsole; the agent and the door
              of the relay (P/09.2: it is an agent) — domainagent; the cluster console — console (P/02.4 Н1.6 roles; P/10 Н1.4 roles)
peer_role:    the expected role of the server — the argument role of the function peer (the contract peer) at the member's agent and the relay: the door
              of the holder (the process domain, the class signed below) — domain; the relay door — domainagent. It is the role of the server, not
              the role of the client: clients from other clusters (the member's agent, the relay) do not present their leaf to a door signed
              — the listener SIGNER_URL of the holder would verify it by its own centers: alert, the member is silent
              (signer, clients below; ADR-0083 addendum (20), addendum (21) item 6)
fingerprint:  the fingerprint of a center — sha256 hex (64 characters, lowercase) of the DER certificate of the center
tls_ca:       a field of the member's publication (the report reception contract «The member's publication»): [<отпечаток>…] ascending, without repeats —
              ca.pem and ca.next.pem of the directory W2C_TLS_DIR of the cluster (rotation above); no directory or no ca.pem — no field; each
              file is exactly one certificate of a center (CA:true): the file exists but is not readable, the blocks are not one or not a center — no
              field (the agent writes the reason to the log; added by the reconciliation of М11, D13); outside the delta (not part of whole, it creates no
              generation); goes in every publication
tls_ca_certs: a field of the publication next to tls_ca: [<PEM>…] — the certificates of the same centers in the same order; an element is exactly
              one block CERTIFICATE (as the contract peer «Функция peer» step 2) with CA:true (a leaf under its own fingerprint is not a center;
              added by the reconciliation of М11, D12), sha256(DER) of an element is the fingerprint of tls_ca at the same place; present only together with
              tls_ca; outside the delta; goes in every publication (the Architect's decision on cammeta-python М11-08 № 19). The form
              of the publication is closed: a holder of a former build rejects a report with the field — the implementations switch at the same time
Entry.ca:     a field of the member record in domain/member-rows/<раздел> and in the member's copy domain/member-list/<раздел>: [<отпечаток>…], 1–2, ascending, without
              repeats; none — no fingerprints; written by the holder (P/08.3 Н1.6 on_accept, admin); the form of the copy at the member is
              Platform/09-agent/data/member-list.schema.json (outcomes — `Platform/09-agent/data/member-list.outcomes.tsv`) (C04-DEP-OBS-HEARTBEAT-01)
```

## The client of a door of its own cluster

The Architect's decisions ADR-0075 addendum of 2026-10-26 (2) item 3, (3), (4), (5) — where they differ, (5) applies. The client of a door of its own cluster
verifies the server with the same function `peer` as a client of another cluster: there is no separate «set of its own box»; only
the arguments change — its own centers and `host` by the loopback threshold — and revocation comes after `peer`.

```yaml
own_client:   any client of a door of its own cluster over https:// (review of the norms of ADR-0075, Claude fd85ea8cc, С-1: the list is examples, not a closed list);
              among them — the agent to its own console (P/09.1 Н1.5, Н1.10), the workers script to /metrics of the console (P/02.4 Н1.5),
              the cluster console to the domain console of its own box — transition 2 by view.url (P/06.7 Н1.4) and in forwarding
              to the signer by SIGNER_URL (P/06.7 Н1.8), the domain console to SIGNER_URL of its own box (P/10 Н1.3 pass, role
              domain) and to the worker door on the domain (P/03.7 door_client, role <sub>domain), the worker and the gateway of a subsystem to
              the console of its own cluster (P/06.7 Н1.2 door, role console, URL — own_url below), the client of the resource door by
              RESOURCE_URL and url of the door row (the object store client contract, role resource); to https:// each calls peer(chain, fingerprints, role, host, now) of the contract peer with steps
              1–9, then revocation by revoke above: the server leaf is revoked, the revocation file is absent or invalid — a refusal (closed)
              (addendum (5) item 1)
  fingerprints: the fingerprints (fingerprint above) of ca.pem and ca.next.pem of the directory W2C_TLS_DIR (rotation); the workers script
              has no role kit — the center of the same directory (addendum (4) item 2)
  role:       the role of the door the client calls: console — the cluster console, domainconsole — the domain console (transition 2),
              domain — the listener SIGNER_URL, <sub>domain — the worker door on the domain, resource — the resource door, <sub>worker — the worker door at a pass of the second kind
  host:       the host of the URL; a host that is a loopback literal (loopback below) — SERVER_NAME of its own w2c.env, substituted before step 1 of peer;
              SNI — the same host; the connection is to the address of the URL, not to SERVER_NAME (addendum (2) item 3, addendum (4) item 2)
  outcomes:   the outcome is the first refusal of peer by its steps, then revocation; words by topology (a tunnel, port forwarding, localhost)
              the contract does not promise: wrong_name — only when steps 1–7 passed and host is not in SAN DNS of the leaf; an IP literal off
              the loopback at https:// — ip_address (step 1); localhost and a v4 notation with leading zeros are names, checked as names
              (SERVER_NAME=localhost is admissible and passes with a leaf localhost); two boxes of different clusters with one server
              name and a mutually trusted center the client does not tell apart — admissible (ADR-0075 addendum of 2026-10-26 (6) item 1; review of Codex
              a87ae5c00 R75D4-02, a377e0dd2 N75-01)
loopback:     the loopback threshold — a pure function {url} → loopback | name | ip over the host notation of the URL, before DNS (addendum (3) item 1, addendum
              (4) item 1); the host notation is the substring of the URL after «//» and an optional userinfo@ up to «:port», «/» or the end, as
              written, without normalisation by a URL parser (127.0.0.01, 0x7f.0.0.1, LOCALHOST, a dot at the end — are not
              rewritten; review of the norms of ADR-0075, Claude fd85ea8cc, М-2): loopback — v4 of four decimal parts 0–255 without leading zeros with the first 127, or v6 (in
              the brackets of the URL) with the value ::1 in any notation without a zone; ip — another IP literal of step 1 of peer (including v6 with
              a zone, ::ffff:127.0.0.1, 0.0.0.0, ::); name — otherwise (localhost, 127.1, 127.0.0.01); vectors —
              common/vectors/loopback
  bad_url:    a URL out of form (no scheme and «//», an empty host): from the environment (SIGNER_URL, RESOURCE_URL, own_url over
              CONSOLE_HOST) — a start refusal of the client process, code 2; from a store row (view.url, url of the door row) — as
              no field, by the outcomes of its row (review of the norms of ADR-0075, Claude fd85ea8cc, М-3)
own_url:      the URL of a client of its own console (the agent, the workers script, the worker and the gateway) — from CONSOLE_HOST and CONSOLE_PORT of w2c.env
              (the environment file contract «Environment variables»); the loopback threshold — over https://<CONSOLE_HOST> (v6 — in brackets;
              in w2c.env CONSOLE_HOST is written without brackets, with brackets — a URL out of form, bad_url) (review of the norms of ADR-0075, Claude fd85ea8cc, М-4):
              a loopback literal — https://<literal>:<port> ([::1] for v6); 0.0.0.0 — https://127.0.0.1:<port>; :: —
              https://[::1]:<port>; another (an IP off the loopback or a name, localhost included) — https://<SERVER_NAME>:<port>;
              the domain console is not in the table — transition 2 takes view.url (addendum (4) item 3, addendum (5) item 3)
  scheme:     https if W2C_TLS_DIR has ca.pem, otherwise the same table with the scheme http; a console without a kit while
              ca.pem is on the box — a connection refusal, visible (addendum (5) item 2)
```

## The server side: the class `signed`

From М11/8 Н1.6 `server` (the introduction) and `signed` without a change of behaviour (the Architect's decision of 2026-10-20, ADR-0083 addendum (14)
item 6; analysis of review of stage A 8–10, № 21). The participants are the process `domain` ([P/08.0](../../../08-domain/spec/08.0-domain.norms.md)
Н1.6, P/08.0-02), the relay ([P/09.2](../../../09-agent/spec/09.2-agent.norms.md) Н1.6, P/09.2-07) and the cluster console — everything incoming from
other clusters on its listener ([P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.7 `server`; ADR-0083 addendum (18), addendum (19) item 2). The class `role` is the door of the domain console,
the section «The server side: the class `role`» below (C10-SDK-ROLE83, the Architect's decision of 2026-10-25).

```yaml
server:       the server side of the doors between clusters — two classes (log of cammeta-go, М11-08 № 5; the Architect's decision);
              the server of both classes presents the leaf of its role with EKU serverAuth (cert above;
              analysis of review of stage A 8–10, № 35) and the center that issued this leaf: the handshake chain is the leaf, then
              its center from ca.pem or ca.next.pem of its own cluster (kit: server.pem is the leaf, the server adds the center itself);
              the same for every door of a process with a role kit that own_client goes to (the classes signed, role, mixed,
              the resource door P/05 at mtls, the cluster console, its callback listener and the domain console for clients of its own cluster) (review of the norms of ADR-0075, Claude fd85ea8cc, С-2);
              without the center in chain[1:] the client will not find the anchor (the contract peer step 3 — foreign_ca) (a clarification on the question
              «cammeta-acceptance» of 2026-10-20; it matches cammeta-go):
  signed:     the doors between clusters where the identity is by the norm of the route (a signature, a token, a password), not by the certificate
              of the client: they do not require a client certificate, it gives no rights; the first knock of a stranger — only by the signature
              (the agent signature contract agent-signature.md; P/09.2 Н1.6). The class is divided by listener, not by route
              (ADR-0083 addendum (20), addendum (21) item 2):
  signer:     the listener SIGNER_URL of the process domain of the holder (the unit — P/02.4-13) — all of its routes (the summary table
              P/08.0 Н2: POST /api/member/<член>, GET /api/carry/<член>, the relay batch — P/08.3; prepare, take,
              move — P/08.8; the people doors that the domain console passes on — P/08.0 Н1.8); TLS with a server certificate
              of the role domain (P/10 Н1.4 roles); it requests the client certificate optionally, a presented one it verifies in
              the handshake by a closed set: the leaf converges to its own ca.pem or ca.next.pem, the term is in force, no
              extendedKeyUsage without clientAuth (the words of the class role below, refusal); otherwise — alert, no HTTP; a leaf outside the contract
              cert (keyUsage, the key size, strict extensions) the handshake MAY refuse; not presented — the handshake is
              ok. After the handshake the role from SAN, the list sig and revoked decide only the reading of X-W2C-Client (P/02.4 Н1.6
              client_cert; the forwarding contract «Client address»), there is no HTTP refusal here, except `POST /domain/move`: by the same signs the process refuses 403 (P/08.8 Н1.8 step 0). A change of ca.pem, ca.next.pem,
              revoked is seen by new connections without a restart; it does not resume sessions (tickets and PSK are off) — as
              the role door (the class role below; ADR-0083 addendum (20), addendum (21) items 3–5); the norm is behaviour, not a version: TLS ≥ 1.2
              on both sides, clients must be able to do 1.2; there is no session resumption — no tickets, no PSK, no cache of the session
              id; version 1.3 — as the implementation can, with the same behaviour (guess of stage C RC-09, the Architect's
              decision of 2026-10-23)
  unasked:    the relay door and batch (P/09.2 Н1.6) and the cluster console — everything incoming from other clusters on its
              listener (transition 1 of the forwarding contract, /domain/at/…, /api/prepare, /api/take, /api/held, /api/backup;
              P/06.7 Н1.7 server) — do not request a client certificate (without a request the client sends no leaf); the cluster
              console — the leaf of the role console, in the handshake it does not refuse by center, the norm of the door lets the request through;
              X-Operator: console — it does not recognise; it always strips it (the Architect's decision of 2026-10-21, ADR-0083 addendum (18),
              addendum (19) item 2; TLS № 14)
  clients:    clients from other clusters — the member's agent, the relay — do not present their leaf to the listener SIGNER_URL of the holder
              (P/09.1 Н1.7, P/09.2 Н1.6, peer_role above): a leaf of their own center would get an alert; a leaf
              is presented by clients of its own cluster — the domain console (domainconsole) and the cluster console when forwarding
              to the signer of its own box (ADR-0083 addendum (20), addendum (21) item 6)
  stand:      checked by reading: the stand does not raise TLS between clusters on one machine (P/02.4 Н1.10)
```

## The server side: the class `role`

From [P/10 Н1.4](../../../10-domain-console/spec/10-domain-console.norms.md) `server.role` (formerly М11/8 Н1.6) without a change of
behaviour; P/10 and [the `peer` contract](../peer.md) refer here (C10-SDK-ROLE83, the Architect's decision of 2026-10-25). The participant is the domain console (the door accepting
the forwarding at transition 2, the lesson that owns the door — P/10); the normative client is the cluster console of the holder
([P/06.7](../../../06-console/spec/06.7-console.norms.md) Н1.4 `holds`). Where P/10 was silent (the trust set at unreadable
rows) — the Architect's decision of 2026-10-25 (the row `unreadable`).

```yaml
role:         the doors where the role matters: the reception by the domain console of a forwarding with X-Operator: console at transition 2 (the
              forwarding contract «Accept by a console»). The normative client of the door is the cluster console of the holder (P/06.7 Н1.4 holds;
              its center — its own ca.pem, ca.next.pem — is always in the union); the norms open no direct path to the door from a member's
              console, the union of the members' centers below is a protection of a direct connection (so the TLS acceptance № 14 tries it);
              removing a member's center removes the TLS trust in it, not the membership: a forwarding of the member with a valid token goes
              as before (the Architect's decision of 2026-10-21, ADR-0083 addendum (18), addendum (19) item 2; analysis of review of ADR-0090,
              № 24, 27). The door requests the client certificate and in the handshake trusts the union of the centers
              of the admitted members: the certificates of the row domain/members/<член>/ca-certs whose sha256 stands in the current Entry.ca
              of this member (domain/member-rows/<раздел>), and its own ca.pem, ca.next.pem of the holder's cluster (W2C_TLS_DIR); a change of the list
              or of the row — new connections see the new set; a certificate that converges to none of them (a foreign
              center, a wrong chain or term) — the handshake is refused (TLS alert), there is no HTTP answer; likewise a client leaf
              that has extendedKeyUsage without clientAuth is refused (analysis of review of stage A 8–10, № 35); a member without
              Entry.ca (before a report with tls_ca) or only with fingerprints without certificates is not part of the union. The certificate converged —
              steps 6–7 of the function peer (the contract peer) over the leaf with role: console and the check of the closed list of signatures sig above at
              the leaf and the center (outside the list — 403 bad_chain; not restricted in the handshake; added by the reconciliation of М11,
              cammeta-python М11-08 № 21), the name check (wrong_name) is not done at the server;
              the refusal is before the gate: at a TLS door there is no client certificate — 401 no_role; no_role, wrong_role, bad_chain — 403 with this word
              (P/10 Н4). The role door has no word foreign_ca: a foreign center is refused by the handshake (ssl of Python 3.12 verifies
              the client certificate in the handshake without a callback; two outcomes would diverge in mixed builds).
              «New connections» include resumed ones: the role door does not resume sessions — session tickets and PSK
              are off, every connection is a full handshake with a check of the client certificate by the current union
              (otherwise a ticket of a past session would let through a center already removed from Entry.ca; the Architect's decision of
              2026-10-19); the doors of the class signed without a certificate request (unasked of the class signed above) are not
              affected; the listener SIGNER_URL — likewise: new connections see a change, it does not resume sessions
              (signer of the class signed above; ADR-0083 addendum (20), addendum (21) item 5)
trust_set:    the trust set of the role door — a function over what is read: its own ca.pem, ca.next.pem of the holder's cluster (W2C_TLS_DIR)
              ∪ the certificates of the row domain/members/<член>/ca-certs of each member whose sha256 (fingerprint above) stands in
              the current Entry.ca of this member in domain/member-rows/<раздел>; a member without Entry.ca (before a report with tls_ca) or only with
              fingerprints without certificates — is not part of it; a certificate of the row ca-certs whose fingerprint is not in Entry.ca — is not
              part of it; a repeat — one (the domain console does not read the copy domain/member-list/<раздел> — P/10 Н1 «Data»)
unreadable:   domain/member-rows/<раздел> is unreadable — the set has only its own centers; the row ca-certs of a member is unreadable or its Entry.ca is out
              of form — the member is not part of it: less trust is safe (C10-SDK-ROLE83, the Architect's decision of 2026-10-25);
              the log — by change: a line when the input turns unreadable and when it returns, not at every handshake
              (C10-ROLE-LOG-C47, the Architect's decision of 2026-10-25)
refusal:      the refusal body is {error, detail?}, error is a word of the contract peer: no_role (at a TLS door there is no client certificate — 401; there is not exactly one
              role in SAN of the leaf — 403), wrong_role (the role is not console — 403), bad_chain (a signature of the leaf or the center outside
              sig — 403); before the gate; a chain not by the trust set — a handshake refusal, no HTTP answer (P/10 Н4;
              the schema RoleRefusal of the OpenAPI of lesson P/10; ADR-0083 addendum (19) item 2; analysis of review of ADR-0090, № 27)
no_kit:       no kit (kit_absent of the class mixed below: no W2C_TLS_DIR or no ca.pem in it) — the door serves on the loopback over
              HTTP without a role check; the role is not proven: X-Operator: console is stripped (the forwarding contract «Accept by a console»),
              X-W2C-Client is not trusted; the gate and the pass — as always; 401 no_role — only at a TLS door without a client
              leaf; a partial kit — a start refusal, code 2 (C10-ROLE-NOKIT-01, the Architect's decision of 2026-10-28)
stand:        checked by reading: the stand does not raise TLS between clusters on one machine (P/02.4 Н1.10); the trust
              set — vectors trust-set
```

## The callback leaf

The main listener of the cluster console is of the class `signed`: it does not request a client certificate and does not refuse by center. A request for a leaf on it would break this class: a stack with an optional certificate breaks the handshake at a foreign center, and shows a browser a choice of leaf. Therefore the callback by ticket goes to a separate listener of the same console, where the role leaf is mandatory ([the gate-and-pass contract](../gate-and-pass.md) «Pass of the second kind»; ADR-0094 addendum (6), addendum (12) item 6, addendum (16)). The main listener and the door classes are not changed by this.

```yaml
callback:     the callback listener — at a cluster console with a kit, if the catalogue has a manifest with a non-empty door.pass.calls; otherwise it is not opened; the port — CONSOLE_CALL_PORT
              (the environment file contract «Environment variables»), the address — as at a door of a process with a kit: the addresses of SERVER_NAME (P/03.4 Н1.7 door_address kit; CONSOLE_HOST does not apply here,
              because the worker also stands on another server). TLS ≥ 1.2, the leaf of the role console and its center (server of the class signed above); only a full handshake: it does not resume sessions,
              no tickets and PSK: a leaf is in force only on the connection where it was presented, and new connections see a change of revoked
  handshake:  the client certificate is mandatory: no leaf, the chain does not converge to ca.pem or ca.next.pem of its own cluster, the term has expired, there is extendedKeyUsage without clientAuth — TLS alert, no HTTP answer;
              browsers and other clusters do not come here, so the contract does not set the list of centers in the request
  check:      after the handshake, step 2 of the order ticket, in order; the first violation — 401 {detail: "ticket refused", error: denied}: the signatures of the leaf and the center — the closed list sig; the serial is not
              revoked (revoke above, the revocation file is absent or invalid — the refusal is closed); the role from SAN URI is exactly one and equals <sub>worker of the addressee; SAN DNS names the server of the addressee: a leaf of a foreign
              role and a leaf of another server do not fit (ADR-0094 addendum (6) item 2, addendum (12) item 6)
  routes:     only requests with the header X-W2C-Pass-Ticket; a request without it — 401 {detail: "ticket refused", error: denied}: the listener has no other routes, no open ones either
  client:     the worker to the issuing instance — own_client above, role console, presents the leaf of its role <sub>worker; URL — the header X-W2C-Pass-Console of the pass, not own_url: a ticket lives only at the issuing instance
  to_worker:  the console to the worker door at a pass of the second kind — own_client, role <sub>worker, host — the host of the url of the heartbeat, presents the leaf of the role console; the worker door — P/03.4 Н1.7 pass_door
```

## The server side: the class `mixed`

The door of a subsystem process ([P/03.4](../../../03-worker/spec/03.4-worker.norms.md) Н1.7) serves the processes of other subsystems and
a page in a browser, which has no leaf: one listener, admission by the route `door.routes` of the manifest ([P/02.1](../../../02-installer/spec/02.1-installer.norms.md)
Н1.3) (ADR-0091 addendum (7), (8); the Architect's decisions on the repeated review of 2026-10-23).

```yaml
mixed:        as signed in full: TLS of the server of the process role (cert, server above), without session resumption, TLS ≥ 1.2 (the class
              signer); the client certificate is requested optionally — CertificateRequest carries certificate_authorities:
              the centers of the cluster (ca.pem, ca.next.pem), so that a browser without such leaves does not ask the person; a TLS stack without such a
              means names this in the description of the implementation (the browser can show a choice of leaf): it is a convenience for the person, not
              a protection, the acceptance does not see the field (C01-MIXED-CA-LIST-STACK-01); a presented leaf is always verified, in the handshake, as at signer (converges to the center, the term, no EKU without clientAuth — otherwise alert);
              sig, revoked and the role from SAN — after the handshake
  routes:     a route as a name or {name} without role and domain (W03-G08) — admission token: the door token (the contract door-token), absent or invalid — 403 forbidden; a route
              {name, role} — admission by the role certificate: no leaf — 401 no_role, a role not from role — 403 wrong_role, a signature
              outside sig or a serial in revoked — 403 bad_chain (the words of the class role above, refusal); the routes {name, domain} and
              {name, role, domain} — admission by the domain token and by what is presented: domain, role_domain below (ADR-0091 addendum (14))
  no_kit:     a door without a kit (loopback only, P/03.4 Н1.7) does not serve the routes role: they are closed — 401 no_role,
              a log line at start; the process and the routes token and domain work — on the loopback (ADR-0091 addendum (14) item 3)
  kit_absent: «no kit» — no directory W2C_TLS_DIR or no ca.pem in it; ca.pem exists, but the leaf or the key of the role
              (<роль>/server.pem, server.key) are absent or invalid — a partial kit: not a switch to HTTP, a start
              refusal, code 2 — there is no silent downgrade (guess of stage C RC-NOKIT, the Architect's decision of 2026-10-23)
# from P/03.4 Н1.7 door_admission domain, role_domain and cors — without a change (layout audit Б-20, the Architect's decision of 2026-10-25; read by the process door and domain)
  domain:     a route {name, domain: [<вид>…]} — the domain token in Authorization: Bearer; one call of the function token of the domain
              token contract with expect {kind: [<the kinds of the route>], cluster: <its own cluster>, audience_claim: {<вид>: <the audience
              field from the declaration of the kind, P/02.1 Н1.2б>}}; steps 1–8 — as before, an expired one or one with a foreign signature — 401 before
              the kind; a kind not from the list — 403 wrong_kind, an audience without its own cluster — 403 wrong_audience; no header
              or not Bearer — no token: 401 not_a_token; the other words of steps 1–8 — 401 with the word, no_revocations — 503
              (ADR-0091 addendum (14) item 2, addendum (17) item 3, addendum (18) item 1, addendum (19) item 1); the claims of the read token
              (ref and the others) the platform passes to the handler of the subsystem — the subsystem checks their meaning; the audience field — by
              the kind of the token (the domain token contract «Проверка» step 10: the mapping audience_claim by the kind matched at step 9;
              W03-G10); no accepted key set domain/keys, no own member (domain/member) or no declaration of the kind at
              a manifest of the catalogue — 503 {error: "unavailable", detail: accepted key set unreadable | own member unknown |
              kind declaration unreadable}, the handler is not called (W03-G09, the Architect's decision of 2026-10-25)
  role_domain: a route {name, role, domain} — by what is presented (ADR-0091 addendum (18) item 3, addendum (19) item 3): a leaf verified in
              the handshake whose role is the role of the route — admission; a leaf of another role: Bearer present — the outcome domain,
              absent — 403 wrong_role; no leaf: Bearer present — the outcome domain, absent — 401 no_role; a refusal of the leaf in the handshake (center,
              term, EKU — mixed above) — alert, it does not come to a choice between the leaf and Bearer; a leaf of the needed
              role with sig outside the list or a serial in revoked — after the handshake 403 bad_chain, without passing to Bearer
              (W03-ROLE-DOMAIN-CHAIN-01, the Architect's decision of 2026-10-25); the outcome domain — the rule domain above, with its 503
  cors:       # the console page in a browser (P/03.4 Н1.7)
    origins:      the allowed origins — CONSOLE_ORIGINS from w2c.env (the environment file contract «Environment variables»): exact scheme://host[:port], comparison
                byte for byte; another origin — without CORS headers
    preflight:    OPTIONS of an allowed origin is answered before the route admission (a preflight has neither a leaf nor a token)
    allow:        the methods GET, HEAD, POST, PUT, DELETE; the request headers Authorization, Range, Content-Type;
                Access-Control-Expose-Headers: Content-Range, Accept-Ranges, Content-Length, Location; Vary: Origin;
                Access-Control-Max-Age: 600 on preflight; no cookies (Access-Control-Allow-Credentials is not set)
                (ADR-0091 addendum (16) item 1, addendum (18) item 5)
    every:        for an allowed origin the CORS headers are set on all answers of the door — successes and refusals (400, 401, 403, 404,
                405, 409, 413, 503 and busy): otherwise the page cannot read the refusal (ADR-0091 addendum (19) item 4)
    no_rights:    CORS gives no rights: the admission of the route (token, role, domain) is the same; a method the route does not accept — 405;
                the door has no cookies, a request from the page without Authorization gets no admission (ADR-0091 addendum (16) items 1–2)
```

## Vectors

The packages [`crl`](../../vectors/crl/README.md) (CRL: the signature, the terms, revocation) and [`revoked`](../../vectors/revoked/README.md) (the file `revoked`). (ADR-0083 addendum (32) item 2)
A participant: the package [`peer`](../../vectors/peer/README.md) — the package of the common contract peer, executed by common; this contract is a participant there: the closed list `sig` is checked by its step 4 (layout audit, `В-57`; CM-RECORD-VECTORS-128, the Architect's decision of 2026-10-25).
The package [`trust-set`](../../vectors/trust-set/README.md) — the trust set of the role door and the check of the leaf (the class `role` `trust_set`, `unreadable`; C10-SDK-ROLE83).
The package [`loopback`](../../vectors/loopback/README.md) — the loopback threshold of the client of its own cluster (`loopback`, 31 rows; ADR-0075 addendum of 2026-10-26 (4) item 1). The substitution
`host = SERVER_NAME` before step 1 of `peer` is not expressed by the package `peer` (the function does not change) — the acceptance of the client lessons checks it.

## Correspondence to former lessons

From P/01.3 Н1.6 (stage B; formerly М10/11 Н1.6, division М10/11-11): the blocks `cert`, `sig`, `kit`, `revoke`, `rotation`;
P/01.3 keeps the roles that the store daemon admits (`roles`) and the peer check at `-raft` and `-api`.
From М11/8 Н1.6 — the rows `server` (the introduction) and `signed` (here «The server side: the class `signed`»; the Architect's decision of
2026-10-20, ADR-0083 addendum (14) item 6); the row `stand` — in the part of the class `signed`; the class `role` — from P/10 Н1.4 `server.role` (here «The server side: the class `role`»; C10-SDK-ROLE83, the Architect's decision of 2026-10-25).
The section «The cluster kit, the domain roles, the center between clusters» — copies of the rows P/02.4 Н1.2 (`W2C_TLS_DIR`), P/02.4 Н1.6 and
P/10 Н1.4 `roles`, P/08.3 Н1.6 `fingerprint`, `tls_ca`, `tls_ca_certs`, `Entry.ca` (from М11/8 Н1.6) and the row `peer_role`
— a reading of М11/8 Н3 `peer(…, role, …)` for the doors of the holder and the relay (analysis of review of stage A 8–10, № 15; analysis
of review of stage B 8–10, № 4).

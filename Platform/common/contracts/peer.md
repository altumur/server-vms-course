# The `peer` contract: the client about a server of another cluster, the first contact of a CA, refusal words

This English text is the source; the Russian translation `ru/contracts/peer.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (13) and addendum (14): a common algorithm of several processes is a contract, not
copies in chapters; the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 2; analysis of the review of stage A 8–10, № 7; analysis of the review
of stage A 6–7, № 28; analysis of the review of stage B 6–7, № 25). The owner is lesson P/09, [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.7 (P/09.1-27; the first contract — the agent to `https://`;
the source — M11/8 N1.6 `client`, `first`, N3 «peer»).
By the function `peer` a client of a door of another cluster over `https://` accepts a server:

| Who | Whom it calls | Where |
|---|---|---|
| the member agent ([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.7), the relay ([9.2](../../09-agent/spec/09.2-agent.norms.md); lesson 4: it is an agent) | the holder, the relay | «Client and first contact»; the agent in a process — P/09.1 N1.11 `client` |
| the cluster console ([chapter 6.7](../../06-console/spec/06.7-console.norms.md) N1.7) | the console of a member or of the holder | [the forwarding contract](forwarding.md) `tls` |
| the process `domain` (8.8) | the consoles of the neighbours on a move and a handover | [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.7, N1.8 |
| the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.4) | — (the server of a role door: steps 6–7 over the client leaf with `role: console`) | [the role certificate contract](role-certificate.md) «The server side: the class `role`» (C10-SDK-ROLE83) |
| the clients of its own cluster ([the role certificate contract](role-certificate.md) `own_client`) | the doors of its own cluster | its own CAs (`ca.pem`, `ca.next.pem` `W2C_TLS_DIR`), `host` by the loop threshold `loopback`, then revocation (review of the norms of ADR-0075, Claude fd85ea8cc, M-5) |
| a client of another cluster to the door of a process `mixed` (a subsystem process, [P/03.4](../../03-worker/spec/03.4-worker.norms.md) N1.7 `cross_cluster`) | the door of the process of the member named by the destination or the book of the subsystem | it presents no leaf, the admission is the route `domain` by the domain token; the server is the peer of the destination member: the role is the role of the door, the fingerprints are `Entry.ca` of this member from the copy `domain/member-list/<part>` (read by `worker.reads`), the name is from the address; the role certificate contract does not change (ADR-0091 addendum (18) item 2, addendum (19) item 2) |

Moved from M11/8 N1.6 (the lines `client`, `first`; the line `revoke` is the client's side, the decision of «Specification» on
the move of lesson 10), N3 «peer(chain, fingerprints, role, host, now)» (steps 1–9 and the paragraph
after them) and N4 (the words of `peer`) without a change of behaviour; the step numbers are the former ones. The fingerprint
of a CA, the publication fields `tls_ca`, `tls_ca_certs`, the form of `Entry.ca`, `W2C_TLS_DIR`, the roles of the domain processes and the expected
role of the server `role` at the agent and the relay (the holder — `domain`, the relay — `domainagent`) are [the role certificate
contract](role-certificate.md) «The cluster kit, the domain roles, the center between clusters» (`fingerprint`, `tls_ca`,
`tls_ca_certs`, `Entry.ca`, `domain_roles`, `peer_role`; analysis of the review of stage B 8–10, № 4); the server side of the class
`signed` is there too; the write of `Entry.ca` at the holder (`on_accept`, the row `ca-certs`, `admin`) is the holder's side, P/08.3
N1.6. The class `role` (`server.role`) is a participant, [the role certificate contract](role-certificate.md) «The server side: the class `role`» (the table above); the answer of forwarding to a refusal is P/06.7 N4
`did not answer`. References in the moved text: «N1.x», «N3» are
of lesson M11/8 (N1.6 — P/06.7 N1.7 and the lines of this contract, N3 — P/06.7 N3); «lesson N» is lesson M11/N; signatures are
[the role certificate contract](role-certificate.md) `sig`. The form of the function is the input of a row of the package [`peer`](../vectors/peer/README.md) (formerly the command `peer` of the acceptance of M11/8 N5):
`{chain: [<PEM>…], fingerprints: [<hex>…], role, host, now}` → `{result: ok}` | `{result: refused, reason}`.

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Client and first contact

From M11/8 N1.6:

```yaml
client:       a client of a door of another cluster over https:// knows the destination member and accepts the server when peer = ok:
              the member console — the name from CLUSTERS; the console of the holder's cluster and the signer — the holder; the relay —
              RELAY_MEMBER; the agent at the door DOMAIN_URL — the holder, in order: carry.holder of the last trusted answer
              of this road (the record deposed); before the first answer after start — its own readable domain/holder; none — DOMAIN_CA (first below, the first contact); nothing —
              foreign_ca; there are no new words or variables (fail-closed, P1; C09-PEER-DEST-MEMBER-01); the fingerprints of the holder — ca of the term record domain/holder (the term record contract; ADR-0113 addendum (3) item 2);
              of another member — Entry.ca of its row domain/member-list/<part> of this cluster; there is no row, its fetched_at is older than MEMBER_ROW_AGE (3600 s) or peer refused by it with foreign_ca — the client puts the request domain/member-want/<part> (P/09.1 N1.4 member_want), this request goes by what there is, without a row — foreign_ca (the form of the copy — Platform/09-agent/data/member-list.schema.json,
              the outcomes — `Platform/09-agent/data/member-list.outcomes.tsv`; C04-DEP-OBS-HEARTBEAT-01)
first:        DOMAIN_CA=<fingerprint> next to DOMAIN_URL, RELAY_CA=<fingerprint> next to RELAY_URL — applies only while
              the record of the destination member does not name ca; neither a record nor a fingerprint — the refusal foreign_ca: there is no trust at the first
              contact; RELAY_URL on https:// without RELAY_MEMBER — the agent does not start, exit code 2 — a configuration refusal
              (P/02.4 N1.1 common; the Architect's decision on the move plans 8–10, ADR-0083 addendum (14) item 10; plan 9 V8)
revoke:       the revocation of a certificate of a foreign cluster is not visible to the caller; the remedy is a change of the CA (rotation)
```

## The function `peer`

From M11/8 N3 «peer(chain, fingerprints, role, host, now) — the client about the server of another cluster, in order»:

```
1. host is an IP address (v4 or v6, including v6 with a zone `%<zone>`; added by the reconciliation of M11, D15) → ip_address
   # a notation like `127.1` is not an IP address but a name (the implementations agreed, written by the reconciliation of M11)
2. chain is not a non-empty list of readable PEM certificates: an element is exactly one CERTIFICATE block, strict base64,
   the DER parses whole; otherwise — before the search for the anchor          → bad_chain
3. fingerprints is empty, or chain[1:] has no CA certificate (CA:true) with a fingerprint from fingerprints → foreign_ca
   the anchor is the first such certificate in the order of chain
4. there is no path chain[0] → … → anchor over neighbouring elements of chain: chain[i] is signed by the key of chain[i+1] with an algorithm of the closed list
   of the role certificate contract `sig` (added by the reconciliation of M11, D14), the next one is CA:true; pathLen and keyUsage are not read, a leaf with
   CA:true is a leaf (the implementations agreed, written by the reconciliation of M11)
   the order of chain is the order of the server (the leaf, then the CA; the role certificate contract server); the elements are not rearranged and
   not tried in turn (the Architect's decision, analysis of the review of stage B 8–10, № 10, ADR-0083 addendum (15))
                                                                             → bad_chain
5. now is outside [notBefore, notAfter] of some certificate of the path (the leaf and the anchor included) → expired
6. the leaf has not exactly one SAN URI of the form urn:w2c:role:<role> with a non-empty role (`urn:w2c:role:` — no role; the scheme and
   the prefix — byte for byte; added by the reconciliation of M11, D15)        → no_role
7. the role of the leaf ≠ role (byte for byte)                               → wrong_role
8. host is not among the SAN DNS of the leaf — comparison byte for byte: case matters, a wildcard is not expanded, a trailing dot is not
   removed (the implementations agreed, written by the reconciliation of M11)  → wrong_name
9.                                                                           → ok
```

A client of a door of its own cluster calls the same function with its own CAs and `host` by the loop threshold, then checks revocation —
[the role certificate contract](role-certificate.md) «The client of a door of its own cluster» (`own_client`; ADR-0075 addendum 2026-10-26 (5) item 1); the function
and its vectors do not change because of this.

Above the anchor the chain is not checked: the anchor is assigned by the fingerprint of the record (whether it stands as a root or an intermediate — it does not matter);
the revocation of a foreign cluster is not checked (the line `revoke` above; formerly M11/8 N1.6). A client with a `peer` refusal closes the connection; forwarding answers
502 `did not answer` with the refusal word in `detail`.

## Refusal words

From M11/8 N4: the words of `peer`: `ip_address`, `bad_chain`, `foreign_ca`, `expired`, `no_role`, `wrong_role`, `wrong_name`.

## Vectors

The package [`peer`](../vectors/peer/README.cases.md) (judge-only: `README.cases.md`) contains 31 rows, including 25 inputs of the former M11/8 acceptance (sc. 06). Its later cases cover certificate path order and the address, name and input-form boundaries. The function steps and refusal vocabulary above govern the result; detailed case inputs and answer associations remain judge-only in the package.


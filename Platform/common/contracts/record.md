# The term record and issuer signature contract: `domain/holder`, the function `record`, refusal words

This English text is the source; the Russian translation `ru/contracts/record.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common algorithm of several processes is a contract, not
copies in chapters; analysis of review of stage A 8–10, № 13 / decision 2). The owner is lesson P/08, chapter [8.8](../../08-domain/spec/08.8-domain.norms.md) (moved from
M11/10 N1.1, N3 «record»): the process `domain` of the holder
signs with the issuing key the record of its term, the backup document and the handover grant. They are checked by the function `record`:

| Who | Where | Kinds |
|---|---|---|
| the member's agent ([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md)) | following the holder (P/09.1 N3 «follow»), the check of the backup copy by the keeper (N3 «check the backup copy»), the condition of the holder's cluster (P/09.1 N1.4 `holder_cluster`) | the term record, the backup document |
| the process `domain` (8.8) | the displacement (P/08.8 N1.6), the handover (P/08.8 N1.7: the record of the target, the grant), the move (P/08.8 N1.8) | three kinds, the members row is the fourth |
| the cluster console ([P/06.7](../../06-console/spec/06.7-console.norms.md) N1.14; the vectors `resolve`) and the agent (9.1) | the shared document ([P/08.9](../../08-domain/spec/08.9-domain.norms.md) N1.2 `document`; N3 «take the document» step 4 — [P/09.1](../../09-agent/spec/09.1-agent.norms.md)) | the shared document |
| the token issue (8.7) | the shared document of the scenario ([P/08.7](../../08-domain/spec/08.7-domain.norms.md) N3 step 5) | the shared document checked by the agent |

Moved from M11/10 N1.1 (the row `domain/holder` and the block `doc`), N3 «`record(keys, row, kinds)`» (the paragraph about the kinds and steps
1–6) and N4 (the words of `record`) without a change of behaviour. The owner keeps: `claim` and `check` of the term record (N1.1), the forms
of the backup document (N1.5) and of the grant (N1.7), the issuing key (`issuing_key_secret`, [P/08.2](../../08-domain/spec/08.2-domain.norms.md) N1.3), the kind «shared
document» ([P/08.9](../../08-domain/spec/08.9-domain.norms.md) N1.2 `document`, `signature`). References in the moved text: «N1.x», «N3» — of lesson M11/10 (N1.1, N1.5, N1.7 — the same numbers of chapter P/08.8; N3 «follow» —
P/09.1 N3 «follow», «check the backup copy»); «lesson N» — lesson M11/N, their addresses now: «lesson 3» (the agent carries
reports) — P/09.1 N3 and P/08.3 N2, «lesson 11» (the shared document) — P/08.9 N1.2 (analysis of review of stage B 8–10, № 22; Kimi
SB810-07); `keys` — the accepted set ([the domain key set contract](keys.md)). What is common to the forms — the [domain founding contract](domain-founding.md)
«Common rules of forms» (layout audit, B-03).

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The kinds of the document: the closed set of the backup copy — `Platform/08-domain/data/backups.schema.json`, `Platform/08-domain/data/backups.outcomes.tsv`; `Platform/09-agent/data/backup.schema.json`, `Platform/09-agent/data/backup.outcomes.tsv`; the shared document — `Platform/08-domain/data/shared-docs.schema.json`, `Platform/08-domain/data/shared-docs.outcomes.tsv`; `Platform/09-agent/data/shared-copy.schema.json`, `Platform/09-agent/data/shared-copy.outcomes.tsv`; the trusted set `keys` — `Platform/08-domain/data/keys.schema.json`, `Platform/08-domain/data/keys.outcomes.tsv`. Times — `Platform/common/data/codec.tsv`, the row `time` (layout audit, V-46…V-48, B-27; the Architect's decision of 2026-10-25).

## The term record `domain/holder`

From M11/10 N1.1 (the form of the family — `Platform/08-domain/data/holder.schema.json` (outcomes — `Platform/08-domain/data/holder.outcomes.tsv`); C04-DEP-OBS-HEARTBEAT-01 — the data files named by a contract are in the reading of `common`, ADR-0083 addendum (32) item 1):

```yaml
domain/holder:   {doc: <the JCS text of the document>}       # at the holder — written by the process domain (claim); at a member — by the agent (N3 «follow»)
  doc:           {domain, term, holder, url, ca?, key?, at, restored_from?, issuer, kid, sig}   # a closed set
    domain:      the domain name (P/08.2 N1.1)
    term:        an integer ≥ 1
    holder:      the name of the holder member
    url:         the address of the door of the holder's process domain — SIGNER_URL of the environment of this process, without it
                 http://localhost:8445 (a one-machine stand) — agents carry reports there (lesson 3); at
                 a holder of several nodes — an address that reaches any node of the cluster, not one server
                 (the queue of the process domain — P/08.10 N1.7; added by M11/12)
    ca?:         [<fingerprint>…], 1–2 — the holder's centre (P/08.3 N1.6; ADR-0075 clarification 2)
    key?:        hex of the key of the holder member; at term 1 before the first report of its agent there is no field (ADR-0113 addendum (3) item 2)
    at:          wall-clock seconds of the signature; a change of the centre or the appearance of the key — a reissue of the same term with a greater at: at strictly grows, a clock going back — the former + 0.001
    restored_from?: {term, rev} — the backup copy from which this term is restored (N1.5); term 1 — without the field
    issuer:      hex of the public key of the issuer (P/08.2 N1.3 issuing_key_secret)
    kid:         serial of the issuer — the first 16 hex characters of issuer
    sig:         base64url without «=» of the Ed25519 signature of the issuer over UTF-8(JCS(doc without kid and sig))
```

The backup document (N1.5), the grant (N1.7) and the members row `domain/member-rows/<part>` (P/08.3 N1.1) are signed the same way: `issuer`, `kid`, `sig` — by the rows above; the kind of the members row also checks `part` and the part of each name (the function `record` step 1; the section «The members row»).

## The switch point `switch`

Moved from [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.6 `switch` without a change of behaviour (layout audit, the Architect's decision of 2026-10-25, B-04):
the condition is read by the process `domain` of the holder and by the agent of its cluster (the key set contract: the rows `domain/keys` and
`domain/revoked` the agent of the holder's cluster does not write while the cluster holds the term).

```yaml
switch:      at the holder's cluster the rows domain/keys, domain/revoked, domain/holder, its own domain/break-glass/<cluster> and
             the pointer domain/shared are written by the process domain, and the agent of this cluster does not write them — while the record domain/holder
             of its own store passes record by the follow set of the agent (the key set contract «The follow set»; added by the Quint model of M11,
             G1) and names this cluster as the holder (P/09.1 N1.4 holder_cluster). The condition of the agent is
             only by the record: «domain/signer not forgotten» is a condition of the process domain, domain/signer is not open to the agent; forget
             comes only after a record of a foreign greater term (P/08.8 N1.6 yields), therefore the record «the holder is this cluster» and forgotten
             keys never go together, except at a theft: the thief signs a greater term with the name of the acting holder, the process yields by it, there is no harm beyond the theft (Quint M12 N11). The switch point is one — a record domain/holder of a greater term that passed record (a change after theft can also be of a smaller one, P/08.8 N1.6 yields): at a planned
             handover it is written by the process of the former holder (P/08.8 N1.7 step 6), at a move — by the agent by «following» (its
             only write into these rows before the point). From it the process yields and writes these rows no more, the agent writes
             them as at any member. The process sees the point at its first check after it (the check is on every pass and
             every request): the window lasts until the next check, no longer than a pass; its edits in the window go into stranded
             (added by the Quint model of M11, SW). At the target — mirrored: claim of a new term (P/08.8 N1.1) is the point, from it the agent of the target does not write them
             (a record naming the target came before claim — the agent already does not write these rows, the process writes them from claim)
```

## Closed sets of the kinds and the member name

From P/08.8 N1.5 `document`, N1.7 step 5 `grant` and P/08.1 N1.1 `member` without a change of behaviour — the checker with the function
`record` (step 1) needs the closed sets of all three kinds and the grammar of a member name (analysis of review of stage B 8–10, № 4; Claude
`S-7`). The owners of the text are P/08.8 N1.5, N1.7 and P/08.1 N1.1; the meaning of the fields (`state`, `objects`, secrets, the backup key)
— there too.

```yaml
member_row:   the members row — JCS {domain, part, rev, term, members, gathered?, new?, issuer, kid, sig}   # a closed set; P/08.3 N1.1
backup_doc:   the backup document — JCS {term, rev, holder, at, members, state, objects, raw?, parts?, counts?, backup_key_rev,
              holder_member_key?, issuer, kid, sig}   # a closed set; the signature — as for the term record
grant_doc:    the handover grant — {doc: JCS {grant: "handover", domain, to, from, term, rev, at, issuer, kid, sig}}   # a closed set
member_name:  a member name — CLUSTER of its installation: 1–64 characters [a-z0-9-], not empty; holder, to, from and the elements of members —
              names by this grammar
```

## The function `record`

From M11/10 N3 «`record(keys, row, kinds)` — a term record or a signed document of N1.1, in order»:

`kinds` is the closed set of document kinds that the caller accepts. This lesson calls record with the three kinds of step 1; the agent, the holder and the relay — also with the kind «members row» (the section «The members row»);
chapter 8.9 — with the one kind «shared document» (P/08.9 N1.2 document; N3 «take the document» step 4 — P/09.1). Steps 2–5 are common
(added by the inventory of families).

The JSON nesting limit is 64, one number for the platform (the JSON depth of the body of a console door, P/06.1 N1.4): the string `row` and
the text `doc` are parsed each with its own limit; a level is an object or an array (a scalar — 0, an empty object or array — 1,
as `depth` of links, [the V7 layers](../LAYERS.md) § 5); deeper than 64 — `not_a_record` (step 1), at the trusted `keys` — the input is out of form, exit 2 (guess of stage C REC-G02, the Architect's decision of 2026-10-23).

```
1. row is not {doc: <text>}, doc is not a JSON object of the closed set of one of the kinds of the third argument; the kinds of this lesson are the term record
   N1.1, the backup document N1.5, the grant N1.7 (the kind — by the set of keys; another document, the shared document
   of lesson 11 included, is not a record) with the types: term — an integer ≥ 1, at — a number, holder — a member name, url — a non-empty string, ca — 1–2
   fingerprints without repeats, restored_from — {term, rev}, issuer — hex of 32 bytes; at the backup document rev —
   an integer ≥ 1, members — a list of member names without repeats, state — {<row key>: {<element>: <text>}}, objects —
   an object, raw — {<key>: a base64 string RFC 4648 §4 with padding, "" — 0 bytes}, a key of raw is not a key of objects (C08-BACKUP-JSON-99, the Architect's decision of 2026-10-26), backup_key_rev — an integer ≥ 1,
   holder_member_key — hex of 32 bytes, parts — {<part>: {sha256, rev, key_rev}}, counts — {servers, cameras} (P/08.8 N1.5a); at the grant grant — "handover", to and from —
   member names, rev — an integer ≥ 1 (the kinds and the types — added by the M11 reconciliation, H9, H11, H12); at the members row part — four digits 0000…4095, rev — an integer ≥ 1, members — {<member name>: object}, the part of each name (P/08.3 N1.1) equals part, gathered — {term, rev}, integers ≥ 1, or null, new — a list of names from members; at the term record key — hex of 32 bytes; at a term record with term 1 — the field
   restored_from; domain, kid and sig step 1 does not check by content (any JSON type of domain — step 2; kid — any
   string, sig — any string: steps 3–5) — one rule for all kinds, the shared document included (guess of stage C REC-G01, the Architect's decision of 2026-10-23)
                                                                                 → not_a_record
2. doc.domain ≠ keys.domain, including domain of another JSON type (for a document with domain; the backup document does not carry it —
   it is bound to the domain by the issuer, steps 3–5)                           → another_domain
3. doc.kid ∈ keys.revoked_issuing                                                → revoked_issuer
4. doc.kid ∉ keys.issuing                                                        → unknown_issuer
5. doc.kid ≠ the first 16 hex of doc.issuer, or the signature does not match     → bad_signature
6.                                                                               → ok {term, holder}
   (at the grant holder is its from: the holder who issued the grant; the shared document of lesson 11 has no holder — ok {term})
```

The function checks the trusted `keys` only by form (the fields and the types of the set of the key set contract), without the content of `kid`, `sig`
and the root signature — the set is already accepted by the function `keys`; out of form — exit 2 of the command `record`, not a refusal of the document (P/08.8 N5
`exit`; guess of stage C REC-G01, the Architect's decision of 2026-10-23).

## The members row

The reader of the row is a member (P/09.1 N1.4 `member_list_take`), the relay forwards it as it is, the holder checks only its own rows from the copy (P/08.8). The relay cannot substitute the row: the issuer signature, `part` and `domain` are inside what is signed.

```
take(keys, row, part, have):
1. record(keys, row, {members row}) is not ok                              → a refusal with the same word: the former copy stays
   (revoked_issuer — the row waits for a re-signature by a new term, P/08.3 N1.1)
2. doc.part ≠ part                                                          → another_part
3. no have, or (doc.term, doc.rev) is lexicographically greater than have   → take
4. equal to have                                                            → same: write nothing
5. record(keys, have, {members row}) — revoked_issuer: its own copy does not serve as a bound, the term after a theft can be smaller (C08-STOLEN-TERM-BACK-01) → take
6.                                                                          → older: the former copy stays
```

`have` is the copy of this part, or there is none; in steps 3, 4 — its `(term, rev)`. The input of the command `take` is `{keys, row, part, have}`, `have` — a row `{doc}` or `null`; the output is `{result: take | same | older}` or `{result: refused, reason}`; the package is [`record/take.tsv`](../vectors/record/take.tsv), the freshness bound.

## Refusal words

From M11/10 N4: the words of `record`: `not_a_record`, `another_domain`, `revoked_issuer`, `unknown_issuer`, `bad_signature`; of `take` — also `another_part`, `older`, `same`. What
the caller does with a refusal (not to follow, the journal `domain.follow.refused`, `domain.shared.refused`, to yield) — the norms
of the caller (P/08.8 N1.6; P/09.1 N3 «follow», «take the document»).

## Vectors

The package [`record`](../vectors/record/README.md) includes `shared.tsv` with 8 rows and `cases.tsv` with 47 rows. It covers the declared document kinds, trusted input, backup raw fields, Time and nesting boundaries. The detailed named case inputs and answer associations remain judge-only in the package. The function form and native exit meanings below are the existing copy of [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N5 `record`, `exit` (layout audit, the Architect's decision of 2026-10-25, B-14):

```yaml
record:    input {keys: <the set document>, row: {doc}}; output {result: ok, term, holder} | {result: refused, reason}
exit:      0 — computed; 2 — the input is out of form; exit codes follow the principle of the vocabulary of «Domain stand» («Exit codes of vector commands»: 2 — the form
           of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the M11 reconciliation, H14):
           keys of record is a trusted set document of chapter 8.2 N1.2 of a closed form: a field is absent (revoked_issuing,
           sig, domain), issuing is not a list, keys null — 2; the signature of the set was checked at the write (the function keys of the domain key set
           contract), the function does not check it — a spoiled sig is not a refusal; record has no row, an extra field, the input is not an object — 2; row (null, a string,
           {}, doc not JSON or a number, an extra field of row) — 0 not_a_record
```
 Participant: the package
[`follow`](../../09-agent/vectors/follow/README.md) — a package of the owner lesson P/09 (chapter 9.1), it executes it; the term record contract
there is a consumer: following calls `record` (layout audit, V-49; CM-RECORD-VECTORS-128, the Architect's decision of 2026-10-25). The package `resolve` of lesson P/06 does not call `record`
(the input is a domain value `{term, rev, value}`) — it is not counted in «Vectors».

The canonical JSON (RFC 8785, ADR-0072) on which the contract relies is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the form RFC 8785 → sha256; ADR-0083 addendum (33) item 2).


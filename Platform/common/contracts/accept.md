# The report reception contract: the function «accept» (`accept`) — generation, mark, roads

This English text is the source; the Russian translation `ru/contracts/accept.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common algorithm of several processes is a contract, not
copies in the chapters; analysis of review of stage A 8–10, № 13 / decision 2). The owner is lesson P/08, [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md): the process `domain` of the holder accepts
the publication of a member on `POST /api/member/<member>` after the signature. A participant is the relay
([P/09.2](../../09-agent/spec/09.2-agent.norms.md) N2): its door accepts a member with this function over its own
memory; the holder accepts a relay batch with it too, with `via` = the relay ([P/08.3](../../08-domain/spec/08.3-domain.norms.md)
N3 «the holder on `POST /api/relay/<relay>`»).

Moved from M11/3 N3 «`accept(mark, stored, body, via, heard_ago)`» (the paragraph on `via` and `heard_ago`, steps 0–7, the paragraph on
`sent_at`, the answer and a failure) without a change of behaviour. The forms that the function relies on are repeated here so that the holder,
the relay and the agent execute the contract without the norms 8.x (analysis of review of stage B 8–10, № 4, № 6; ADR-0083 addendum (15); Claude
`S-3`, `S-4`, `S-6`, `P-2`; Kimi SB810-01): the generation, the mark, `MARK_REFRESH`, `BODY_LIMIT` — the section «Generation, mark, limits»
(from [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.3, N1.3a); the publication, `member_objects`, the fields outside the delta,
`ready` — the section «The member's publication» (from [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.2 and P/08.3 N1.6 `form`);
the field `every` of the answer — the section «The answer `carry`: `every`» (from P/08.3 N1.5); the form of the function, the output and the exit code 2 — the section
«The form of the function» (from M11/3 N5, M11/4 N5). The owners of the text stay the same (P/08.3, P/09.1) and refer here; the values
do not change. The other fields of the answer `carry` — the section «The answer `carry`»; the ceiling of the integer `whole` — [P/08.10](../../08-domain/spec/08.10-domain.norms.md)
N1.5. References in the moved text: «N1.2» — the section «The member's publication» (P/09.1 N1.2); «N1.3» — the section «Generation, mark,
limits» (P/08.3 N1.3); «N1.5» — the section «The answer `carry`»; «N2» — P/08.3 N2; «lesson 4 N1.3» — the section «Generation, mark, limits»
`ROAD_QUIET` (P/08.3 N1.3a).

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The rows and objects that the function writes and reads are families by the [catalogue](../data/catalog.tsv): the report, the delta and the mark of a member — `Platform/08-domain/data/member-report.schema.json`, `Platform/08-domain/data/member-report.outcomes.tsv`; `Platform/08-domain/data/member-report-delta.schema.json`, `Platform/08-domain/data/member-report-delta.outcomes.tsv`; `Platform/08-domain/data/member-reported.schema.json`, `Platform/08-domain/data/member-reported.outcomes.tsv`; the member key `domain/member-key` — `Platform/09-agent/data/member-key.schema.json`, `Platform/09-agent/data/member-key.outcomes.tsv`; the families of `member_objects` — `Platform/03-worker/data/heartbeats.schema.json`, `Platform/03-worker/data/heartbeats.outcomes.tsv`; `Platform/04-controller/data/snapshot.schema.json`, `Platform/04-controller/data/snapshot.outcomes.tsv`; `Platform/09-agent/data/reaches.schema.json`, `Platform/09-agent/data/reaches.outcomes.tsv`; `Platform/09-agent/data/shared-refused.schema.json`, `Platform/09-agent/data/shared-refused.outcomes.tsv`; `Platform/09-agent/data/backup-taken.schema.json`, `Platform/09-agent/data/backup-taken.outcomes.tsv`; `Platform/09-agent/data/alarms.schema.json`, `Platform/09-agent/data/alarms.outcomes.tsv`; `Platform/09-agent/data/outcomes.schema.json`, `Platform/09-agent/data/outcomes.outcomes.tsv`; `Platform/08-domain/data/shared.schema.json`, `Platform/08-domain/data/shared.outcomes.tsv`. The doors — OpenAPI `Platform/08-domain/spec/08-domain.api.openapi.yaml` (`POST /api/member/<member>`, `POST /api/relay/<relay>`, the answer `carry`) and `Platform/09-agent/spec/09-agent.api.openapi.yaml` (the relay door); the manifest keys `domain.*` — `Platform/02-installer/spec/02.1-installer.schema.json` (layout audit, `V-01`…`V-04`, `B-13`; the Architect's decision of 2026-10-25).

## Generation, mark, limits

A copy of P/08.3 N1.3 (`generation` … `BODY_LIMIT`) and N1.3a (`ROAD_QUIET`) byte for byte: the lesson is the source of the copy (the
Architect's decision of 2026-11-04); `every` and `REPORT_EVERY` in detail — the section «The answer `carry`: `every`»:

```yaml
generation:     domain/members/<member>/reports/<rev>   # an object of the holder (P/05 N1.1): the whole generation, JCS
  whole:        {sent_at, objects, key, keys_rev?, pinned?, outcomes?}   # objects — all objects of the member after applying the
                change; outcomes — P/09.1 N1.5: a change of outcomes is a new generation, the agent sends the field of outcomes of the edits still named by the holder (OUTCOME_HOLD) in every
                publication while the row domain/outcomes is not empty; no field — no outcomes
delta:          domain/members/<member>/reports/<rev>.delta     # the bytes of the publication body as received — what the agent signed
reported:       domain/members/<member>/reported               # the mark object; the only boundary of what is accepted
                # two parts (the Architect's decision on R41-05 of run 41): the generation fields are written only by generation (report
                # reception contract, step 7); the fields of the last accepted request — by every acceptance with a write of the mark (steps 6, 7)
  # generation fields
  rev:          an integer ≥ 1 — the generation number; handed out by the holder: +1 per accepted change
  sha256:       hex sha256 of the bytes of generation — sha256 of the JCS of the whole whole
  base:         the rev against which the change came; 0 — a whole came
  delta_sha256: hex sha256 of the bytes of delta (at base 0 — of the body of the whole, as it came)
  signature?:   the header X-Agent-Signature of the direct report that created the generation, as it came (N1.4); through a relay
                there is no field (N1.3a); via is a field of the last request, so a mark without signature and without via is lawful:
                the generation came through a relay, then a direct heard (the Architect's decision on the reconciliation of M11, A14)
  key, keys_rev?, pinned?: from the publication — by them the domain console admits the member and shows the pinning
  # fields of the last accepted request
  sent_at:      sent_at of the publication; received_at — wall-clock seconds of the accepting holder
  request_sha256: hex sha256 of the bytes of the body of this request, as it came; a repeat is recognized by (sent_at, request_sha256)
  via?:         the relay — N1.3a
  stale:        from the publication at every acceptance, «heard» included (report reception contract, step 6); not in the publication — []
  sign_failures?: from the publication at every acceptance with a write of the mark, as stale; it creates no generation and does not
                refresh the mark by itself; not in the publication — no field (N1.6a; P/09.1 N1.12; the Architect's decision on the reconciliation of M11, A7, W1)
  every?:       s — the period told to the member by the last answer with a write of the mark (N1.5; the report reception contract «The answer `carry`: `every`»); none — REPORT_EVERY
keep:           the two last generations and their delta; older ones and those above the mark are retried by the next bounded resumable cleanup attempt
REPORT_EVERY:   5           # s — the agent pass; the holder's answer can assign every (N1.5), 1 … 3600
MARK_REFRESH:   22.5        # s = LOST_AFTER/2 (chapter 8.1 N1.3) by the holder's monotonic clock
BODY_LIMIT:     16 MiB      # the body limit of the door of the holder and of the relay: larger — 413, the body is not read further; it is also
                            # the limit of the JCS of the whole of step 4a of the report reception contract and of the whole that the agent does not send (P/09.1 N1.2 body)
ROAD_QUIET:    15         # s, the holder's monotonic clock: three passes of the agent (REPORT_EVERY 5); longer — the former road is silent;
                           # for class camera — road_quiet = max(15, 3 × mark.every) (P/08.3 N1.1a)
```

The mark is the boundary of what is accepted: an object with a number not above `reported.rev` is immutable; an object above it belongs to nobody: it is not read, not
transferred, does not hold the number, the next acceptance writes over it. The readers take `reported.rev` and read only the object of this
generation; a mark without an object or an object not with its `sha256` requires the bounded marker reread below before the member is `silent`; never a mixture (the readers — P/08.1, P/08.5,
P/08.8).

## The member's publication

From P/09.1 N1.2 (`publication`, `out_of_delta`, `member_objects`, `ready`) and P/08.3 N1.6 `form` without a change of behaviour
(analysis of review of stage B 8–10, № 4; Claude `S-6`): the body of `POST /api/member/<member>` that the agent sends (P/09.1), and the holder and
the relay accept with the function «accept». How the agent assembles the objects (`change`, `fresh`, contributions to books, the body limit of the
agent) — P/09.1 N1.2; the forms `tls_ca`, `tls_ca_certs` at the member — [the role certificate contract](role-certificate.md); their
acceptance by the holder (`on_accept`) — P/08.3 N1.6; `members_rev` — the section «The list of members to the one lagging behind»; `sign_failures` — P/09.1 N1.12.

```yaml
publication:    the body of POST /api/member/<member> — a JSON object, a closed set:
  sent_at:      a finite number — the agent's wall-clock seconds at the moment of sending
  objects:      {<object key>: <the JSON value of the object>} — what changed against base (the whole at base = 0)
  base?:        an integer ≥ 0 — the rev of the generation at the holder against which the changes are; none or 0 — the body is whole
  deleted?:     [<object key>…] — the keys that are no longer there against base; only at base > 0
  key:          hex of the member key — the one in domain/member-key
  keys_rev?:    the rev of the set domain/keys that the member holds (none — no set)
  stale?:       [<heartbeat key>…] — the heartbeats <sub>/heartbeats/<worker> of the copy that have not changed for longer than LOST_AFTER (45 s)
                by the agent's monotonic clock; ascending; none — empty. Outside the delta: not part of whole and creates no
                generation
  pinned?:      the fingerprint of domain/root of the member (none — not pinned)
  outcomes?:    {<id>: <outcome>} — the outcomes of the domain's edits, P/09.1 N1.5 (a key ≠ the id inside the outcome — the outcome is not counted,
                P/08.6 N1.6 settle);   tls_ca?, tls_ca_certs? — the role certificate contract;
                sign_failures?: {domain?: n, console?: n}, n — a platform integer 1 … 9007199254740991 (the integer ceiling P/08.10),
                as a JSON integer; a compound or unknown name, another n — out of form (guesses of stage C ACC-FORM-31-01,
                ACC-G01-COUNTER-31-01, the Architect's decision of 2026-10-23) (the requests that the agent since its start did not send because it could not
                sign them: domain — to the holder or the relay, console — an edit of its own console; none at all — no field;
                P/09.1 N1.12; guess of stage C ACC-G01, the Architect's decision of 2026-10-23);
                members_rev? — the section «The list of members to the one lagging behind» ({term, rev} of the list the member holds; outside the delta);
                book_parts?: {<sub>/<book>: {<part>: {term, rev} | null}} — the sections of the books to: "*" that the member holds, null — a request without a copy; at most BOOK_PARTS_SHOWN 64 by a window round the circle (P/08.5 N1.4), outside the delta;
                gathered?: {term, rev} | null — the field gathered of its own section row (P/08.8 N1.8a), outside the delta; it is checked against the source, send_row asks for the row;
                row?: {doc} — its own section row on the word send_row (P/08.8 N1.8a, P/09.1 N1.2a), outside the delta;
                class?: server | camera, batch?: {name, sig} — the section «The batch knock»; outside the delta; the agent sends them while its own name
                is not in its own row domain/member-list/<part> (P/09.1 N1.1 join); no class — server
out_of_delta:   a field outside the delta — a closed list of the publication form: stale, tls_ca, tls_ca_certs, sign_failures, members_rev, class, batch, row, book_parts, gathered;
                a field that is not in the publication of P/09.1 N1.2 — the body is out of form, 400 not_a_publication (the Architect's answer of 2026-10-25 (layout audit, question T5a)); a field outside the delta out of form
                of its norm — the field is not taken, the holder's log, the report is accepted, as tls_ca below; stale — keys
                without repeats, a repeat — the field is not taken
tls_ca_form:    in the publication form tls_ca and tls_ca_certs are lists of strings of any length; not a list of strings — the field is not taken
                (out_of_delta); everything else — the length, a repeat, not 64 lowercase hex, not PEM, not CA:true, does not match — the check
                of the holder on_accept (P/08.3 N1.6): nothing changes, the log domain.member.ca.refused, the report is accepted
member_objects:                               # what the agent carries and what the holder keeps; the holder silently drops the rest;
                                              # a key is compared with the list exactly, not by its start and not as a substring
  <sub>/heartbeats/<worker>:  the heartbeat P/03.4 N1.1 of each manifest of the catalogue with domain.ref
  <sub>/snapshot/<shard>:      the snapshot shard P/04 N1.3a of each such manifest
  <sub>/snapshot-tables/<table>:  the table snapshot P/04 N1.3b: <table> — a key of domain.view_tables of a manifest of the catalogue, domain.ref is not needed;
                              ready is not judged by it; the agent keeps the sum (P/09.1 N1.2 tables_budget)
  other families (guess of stage C ACC-G01, the Architect's decision of 2026-10-23; P/09.1 — where it was moved from):
    reports:                  domain.reports: [<family>/…] of the manifest (an element is a family prefix with a final «/») — the objects
                              <sub>/<family><name> (<name> — one component by the grammar of <name>; the depth is set by the element of the declaration;
                              C09-REPORTS-NAME-01) of the member as they are; a book does not read them (P/09.1 N1.2)
    contributions:            objects["<sub>/<row>[/<slot>]"] = {<item>: <the input object>} — the contribution rows of the books domain.books
                              (P/02.1 N1.2b); what the agent takes into the report (the slot liveness filter, the secret envelopes) — P/09.1 N1.2
                              liveness, in_report; the holder keeps them as they are, the assembly decides (P/08.5 N1.3)
    domain/reaches:           {networks: [<network>…]} (P/09.1 N1.7)
    domain/servers:           {servers: {<server>: {labels}}, url?} (P/09.1 N1.2)
    domain/folders-state:     {rev, scope, gone, own?} (P/08.5 N1.8, P/09.1 N1.5)
    witness:                  the objects <sub>/<report>/<name> of the witnesses domain.witness (P/02.1 N1.2b); <sub>/<report> without a name —
                              is not a witness (P/09.1 N1.10, P/10 N1.8)
    scope:                    reports and witness — of each manifest that declared them, domain.ref is not needed; a key of a heartbeat or of a snapshot
                              shard of a manifest with domain.ref belongs to its own family, reports neither widens nor replaces it; a manifest
                              without domain.ref has no such families — the objects go as reports (C09-REPORTS-SCOPE-01, the decision
                              of «Domain Specification»); reports is the last of the families of member_objects: a key of another family (contributions,
                              witnesses, domain/…) is that family's; a contribution row that did not pass liveness or no_seal does not free the key;
                              the contributions domain.books.*.from and the witnesses — of each manifest that declared them, domain.ref is not needed
                              (C09-REPORTS-SCOPE-02, the decision of «Domain Specification»)
    domain/shared, domain/shared-refused: the value is the parsed doc of the row: {term, rev, sha256} | {term, rev, reason, at};
                              at the holder's cluster domain/shared — {term, rev, sha256, object}; term and rev are JSON integers (P/09.1 N1.10)
    domain/alarms:            the alarm page (P/09.1 N1.10, P/10 N1.8)
    domain/backup-taken:      {term, rev, sha256}, term and rev are JSON integers (P/09.1 N1.9, P/08.8 N1.5 in_report)
ready:          the agent does not send a publication while it has not a single snapshot shard of every manifest of the catalogue with domain.ref:
                such a publication would say «no units» — a full answer that the domain would believe;
                this does not concern table snapshots: they can be absent (the ceiling P/04 N1.3b), the report is no worse for it
```

The «other families» of `member_objects` are the list above; the holder keeps them as they are and drops only what the list does not
name (step 4).

## The check of the member and the key

Moved from [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N2, the row `POST /api/member/<member>`, without a change of behaviour
(layout audit, the Architect's decision of 2026-10-25, `B-12`); the signature — [the agent signature contract](agent-signature.md). The relay door accepts a member in the same
order over its own memory (P/09.2 N2); the relay batch at the holder — P/08.3 N2 `POST /api/relay` (C08-G06).

```yaml
order:          in order: 503 `standby` before reading the body (P/08.10 N1.7); 413 larger than BODY_LIMIT; 400 not a publication of P/09.1 N1.2 (including JSON nesting deeper than
                JSON_DEPTH P/01.1 N1 — 128; reconciliation of M11, A12); the name is its own holder, there is no record or it is not `how: "holder"`: the signature by the key from the body is wrong — 401, right — step 1 of the procedure «the holder in the list» (P/08.3 N3), exhaustion or a failure — 503 `unavailable`, the agent will repeat; not a member — the signature by the key from the body (`key`): wrong — 401,
                right — a knock (the sections «The knock», «The batch knock») and 404 «no member called <member>», for class camera with retry_in (the section «Busy»); a gathering «from nothing» is going on — also send_row and the merge of row (P/08.8 N1.8a), the signature at 403 of the key is also judged by the key from the body; a member — a holder whose Entry is still without key
                (P/08.3 N3 «the holder in the list» step 1): the signature by the key from the body (`key`) — right → step 2 of that procedure, it checks the key against `domain/member-key`,
                otherwise 401; a record without key with `revoked_keys` (P/08.3 N3 «admit a member» step 1) — as not a member: a knock; any other member — 403 the key is not in the record or is not that one, 403 revoked (`revoked_keys`,
                `revoked_members` of the set); 401 the signature by the key of the record (P/08.3 N1.4; the agent signature contract); 409
                `deposed` (P/08.8 N1.6) or 503 `standby` of a lost turn; 429 `busy` (the section «Busy»), no write; then the steps of «accept» below in their order: 409 `same_sent_at`
                (step 2), 409 `rebase` (3), 413 `whole too large` (4a; P/08.10 N1.5), 409 `not_ready` (5), 503 `rev_exhausted` (7)
                (C08-ACCEPT-ORDER-01)
```

## The answer `carry`

Moved from [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.5 without a change of behaviour (layout audit, the Architect's decision of 2026-10-25, `B-12`); the bound of `every` is
the section below.

```yaml
carry:          the answer 200 to POST /api/member/<member> and GET /api/carry/<member> — a JSON object:
  cluster:      the name of the member
  rev:          the rev of the mark of this member after the acceptance (0 — no generation); the agent sends the next change against it
  every?:       s — the agent pass, 1 … 3600; outside — the agent takes the nearest bound; the value and the case without the field — the section «The answer `carry`: `every`»
  # in M11/3 there are: cluster, rev, every, keys, revoked, members — each row as it is, when the holder has it;
  # M11/3 had no sealed (there was nothing secret for a member before M11/5 and M11/9); in P/08 — sealed? below (analysis of review of stage B 8–10, № 22: M-9)
  keys?:        the row domain/keys of the holder {doc} (the domain key set contract «The set domain/keys»)
  revoked?:     the row domain/revoked of the holder {jtis} (the domain key set contract «Revocations domain/revoked»)
  folders?:     the shared folders (P/08.5 N1.8) — only when the rev of the copy lags behind
  gone_seen?:   the links gone for which the holder has no rows (P/08.5 N1.8)
  members?:     the row domain/member-rows/<part> {doc} (P/08.3 N1.1) — only to the one lagging behind: members_rev of the publication is absent or ≠ (term, rev)
                (the section «The list of members to the one lagging behind»; added in M11/12); at GET /api/carry — always
  holder?:      the row domain/holder of the holder {doc} (P/08.8 N1.1; the term record contract)
  book_rev?:    {<sub>/<book>: {term, rev}} — the versions of the heads of the books to: "*" (P/08.5 N1.4)
  book_stale?:  {<sub>/<book>: [<part>…]} — the sections from publication.book_parts whose version is different, or null whose row has appeared; while the head `/*` of the book of the current term is not written, there is no field (P/08.5 N1.3 first; ADR-0113 addendum (47) item 1)
  send_row?:    true — send your own section row in the field row (P/08.8 N1.8a); carry.members is then absent
  sealed?:      the envelope m1 with a JSON object of what is secret for the member — the domain envelopes contract «Content of sealed» (analysis of review
                of stage A 8–10, № 12)
  <fields of lessons>: placement — P/08.6 N1.2 (the assignment — P/08.6 N1.1), pending — P/08.6 N1.4; topology — P/08.3 N1.2;
                shared — P/08.9 N1.4; backup — P/08.8 N1.5
```

## The list of members to the one lagging behind

Moved from [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.4a without a change of behaviour (layout audit, the Architect's decision of 2026-10-25, `B-12`).

```yaml
publication.members_rev?:  {term, rev} of the copy of its own section domain/member-list/<part> that the member holds (P/09.1 N1.1); no row — no
                           field; outside the delta: not part of whole and creates no generation (as stale, tls_ca). A pair, not a number:
                           a number without a term repeats after a move (P/08.8), as at the shared document P/08.9
carry.members:             the holder puts the row of the member's own section only when members_rev of the publication is absent or ≠ (term, rev) of the row domain/member-rows/<part>, except the member whose row the gathering «from nothing» asks for (P/08.8 N1.8a send_row 200);
                           other sections — the door GET /api/members/<member>/<part> with the agent signature, at the relay the same door from memory;
                           equal — no field. No field means «no changes», not «delete» (P/09.1 N1.4 does not delete anyway)
carry_without_body:        GET /api/carry (P/08.3 N2) carries no publication — members always goes
```

## Busy (ADR-0113)

```yaml
name_hash:   the first 4 bytes of SHA-256(UTF-8 of the member name), an unsigned integer, the most significant byte first — the spread of passes and retry_in
busy:        the answer 429 {error: "busy", retry_in} — after the signature check: only members are counted; at all agent doors: POST /api/member, GET /api/carry, /api/members, /api/anywhere, /api/topology, /api/backup-part, /api/book
             class server does not get it: the clusters hold the keepers and the target of the handover; the budget REPORT_RATE holds at the agent start and at a burst of rebase
threshold:   requests of the agent doors from class camera in the last second of the monotonic clock exceed REPORT_RATE (P/08.3 N1.1a); the count is the memory of the process domain
retry_in:    s, period + name_hash mod period, an integer; period — every of the camera (P/08.3 N1.1a), no count — REPORT_EVERY; the agent does not call the doors earlier (P/09.1 N1.2a)
             busy does not write the mark: this is the cost it removes. A told retry_in is the memory of the process domain, forgotten after a restart: the silence term
             is one round shorter, that is the limit
knock:       the 404 of a knock with class camera in the body carries retry_in by the same formula; without it a stranger knocks at every pass; class server — no field, as before
packet:      in the answer to a relay batch refused[<member>] = {reason: "busy", retry_in}: the publication stays in the memory of the relay, up is not forgotten, a repeat after retry_in, a new arrival replaces it
```

## The knock

Moved from [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.1 `knock` without a change of behaviour (layout audit, the Architect's decision of 2026-10-25, `B-12`): the memory
of the process `domain` about the knocking ones; the knocks from a relay batch — the section «The relay batch: limits».

```yaml
knock:          {name, last, times, key, fingerprint, pinned, keys_rev, class, batch?}    # the knocking one: the report is rejected 404 «not a member»,
                                             # but the signature is right by the key key that the report itself presented (the publication key — P/09.1 N1.2)
  last:         the holder's wall-clock seconds of the last knock; times — the number of knocks with this key since the first one seen by this
                process (a new key — again from 1)
  pinned:       this | another | none — pinned of the body against the fingerprint of domain/root of the holder: equal — this, different — another, none — none
  forget:       the knock of an admitted one is forgotten by the pass of the view; a record without key with `revoked_keys` is not admitted, its knock is kept (P/08.3 N3 «admit a member» step 1); one that left (DELETE) knocks again
  keys_rev:     the rev of the set the member holds, or null
  class:        class of the body; out of form or absent — server; a person sees it and confirms it by admitting (P/08.3 N1.1a)
  batch?:       the name of the batch: a knock with a valid batch signature, the batch fit or not (the section «The batch knock»)
  limit:        at most KNOCKS knocking ones (P/08 forms/runtime-constants.tsv, row KNOCKS), in the memory of the process domain; the oldest by last is evicted
```

## The batch knock

The admission batch — [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.1b. The step comes after the check of the body signature by the key `key`: at the holder's door and for a knock from a relay batch (P/08.3 N3 step 3) alike; the relay door does not judge the batch, the body goes as a knock as it is.

```yaml
publication.batch: {name, sig}    # out of form — the field is not taken, an ordinary knock
  name:        the batch name, the row domain/batches/<name>
  sig:         128 hex — an Ed25519 signature by the private key of the batch over UTF-8(JCS {purpose: "batch-knock", domain, name: <member>, key}): domain — the domain name from domain/root
               of the holder, <member> — from the path, key — the field key of the body; the secret does not go over the network, the signature does not fit another name and key
order:         in order:
  1:           the row domain/batches/<batch.name> is absent, unreadable or the signature does not match → an ordinary knock (the memory KNOCKS), no field batch
  2:           the batch is fit: the gathering «from nothing» is closed or not going on (P/08.8 N1.8a), pinned of the body = this, now < until, no revoked, used < n, the fingerprint of key not in refused; the key is not of small order and not in revoked_members of the set; the name is free (no record or it is without key with revoked_keys);
               the section row is not full; the admission limit P/08.3 N3 «admit a member» steps 5a, 5b; the via of the batch is in domain/member-rows and the row domain/relay-members/<via> is not full
               all yes → step 3; otherwise → step 4
  3:           the batch admission: in one store batch — Entry {how: "admitted", since, class: camera, by: <batch.by>, key, via?, batch} in the section row (signature, rev + 1), used + 1 in the batch row, domain/member-count or the section count (P/08.8 N1.8a count),
               domain/relay-members/<via> at via; CAS — up to 3 times, then step 4; the log domain.member.admitted.batch {batch, name, fingerprint}; the knock of this name is removed from domain/knocks; the answer is the same 404 of the knock: the member learns of
               the admission at the next pass, the report already passes
  4:           the knock lies: the first knock of this name with this key is written to domain/knocks/<part> {key, pinned, at, batch, class: camera}, the row up to the ceiling of P/01.1 N1, beyond it — the memory KNOCKS; it waits for a person (P/08.3 N3 «admit a member»)
```

## The answer `carry`: `every`

From P/08.3 N1.3 `REPORT_EVERY` and N1.5 `carry.every` without a change of behaviour (analysis of review of stage B 8–10, № 4; Claude `S-3`):

```yaml
REPORT_EVERY:   5           # s — the agent pass; the holder's answer can assign every, 1 … 3600
every:          a field of the answer carry (P/08.3 N1.5): s — the agent pass, 1 … 3600; the holder gives REPORT_EVERY (5), class camera — P/08.3 N1.1a;
                the row domain/member-count is absent or unreadable — no field for a camera, the agent keeps the former one (P/09.1 N3 step 5); a value outside
                1 … 3600 the agent does not reject — the answer is accepted, the agent takes the nearest bound (1 or 3600; P/09.1 N3
                «the agent pass» step 5). The bound 1 … 3600 of the schema Carry.every `Platform/08-domain/spec/08-domain.api.openapi.yaml` is what the holder sends, not
                a reason for the agent to reject the answer (the behaviour of M11/3 N1.6)
```

The batch signature — the package [`agent-sig`](../vectors/agent-sig/README.md), the file `batch-knock.tsv`.

## The function «accept»

From M11/3 N3 «accept(mark, stored, body, via, heard_ago) — the holder, at `POST /api/member/<member>` after the signature»:

`via` is the road: none — directly, otherwise the name of the relay (lesson 4 N1.3); `heard_ago` — monotonic seconds since the last
acceptance of this member by any road (none — not heard); acceptance is the outcomes `generation`, `heard` (with a write of the mark or without) and
`same`; `ignored` and refusals do not count as acceptance.

```
0. the acceptance of one member — one at a time in the process domain (a mutex); the signature, the member and the key are already checked (the section «The check of the member and the key»)
1. body is not a JSON object by the form of N1.2                                    → 400 not_a_publication
2. mark exists and body.sent_at = mark.sent_at (one clock of the member on all roads, lesson 4 N1.3): sha256(body) ≠
   mark.request_sha256 → 409 same_sent_at; mark.via = via → same (write nothing, do not refresh the mark); otherwise → heard
   (a repeat by another road: no generation, the mark — by the refresh rule of step 6; added in M11/4)
2a. mark exists, mark.via ≠ via, body.sent_at < mark.sent_at and heard_ago < road_quiet (lesson 4 N1.3; for class server it is ROAD_QUIET) → ignored
   (write nothing: the former road is alive, and this body is older by the member's clock)
3. base > 0 and (no mark, or mark.via ≠ via, or base ≠ mark.rev, or stored is unreadable or not with mark.sha256) → 409 rebase
4. objects' = (base > 0 ? the objects of stored : {}) ∪ body.objects − body.deleted; drop the objects outside member_objects
4a. JCS(whole') larger than BODY_LIMIT → 413 {error: "whole too large", detail}; write nothing (P/08.10 N1.5; added in M11/12)
5. no snapshot shard of some manifest of the catalogue with domain.ref                → 409 not_ready
6. mark exists, stored is readable and with mark.sha256, and whole' without sent_at = whole of stored without sent_at (JCS) → heard
   (stored unreadable or not with mark.sha256 — step 7: a spoiled generation is replaced by a new one; added by the reconciliation of M11, A1):
   this process did not write the mark, or wrote it no less than MARK_REFRESH ago (monotonic), or body.stale ≠ mark.stale
   (sorted lists of keys are compared; reconciliation of M11, A8), or the input every exists and ≠ mark.every →
   rewrite the mark: the generation fields as before; the fields of the last request — sent_at, received_at, request_sha256, via, stale,
   sign_failures, every — of this request; otherwise write nothing
7. otherwise → generation: rev = (mark ? mark.rev : 0) + 1; mark.rev = 2^53 − 1 → 503 {error: "refused", reason: "rev_exhausted",
   detail: "<member>'s generations reached 2^53 − 1: the mark cannot grow"}, nothing changes (added by the reconciliation of M11, A18); write reports/<rev> = JCS(whole'), then reports/<rev>.delta = body,
   then the mark {rev, sha256, base, delta_sha256, signature?, key, keys_rev?, pinned?, sent_at, received_at,
   request_sha256 (= delta_sha256), via?, stale, sign_failures?, every?};
   remove ALL reports/<g> and their .delta for g < rev−1, and the objects above rev; resume interrupted cleanup on later attempts
```

`sent_at` below `mark.sent_at` on the same road is accepted: the order on one road is set by the road, a member's clock that stepped
back is taken at once; between two roads — step 2a (lesson 4). The answer to steps 2 (same, heard), 2a, 6, 7 is carry (N1.5); its `rev` is
the `rev` of the mark if `mark.via` = the road of the answer, otherwise 0 (the other road sends a whole). A failure between the steps of 7: an object above the mark belongs to nobody (N1.3), the next acceptance writes over it.

## The form of the function

From M11/3 N5 `accept`, `exit` and M11/4 N5 (the fields `via`, `heard_ago`) without a change of behaviour: the input and the output of the rows of the package
[`accept`](../vectors/accept/README.md) (the scenarios were removed by the move of lesson 8; analysis of review of stage B 8–10, № 6, Claude `P-2`;
№ 4, Claude `S-4`):

```yaml
input:          {catalog: [<sub>…], mark: <label> | null, stored: <whole> | null, body: <text>, refreshed_ago: <s> | null,
                 via?: <relay> | null, heard_ago?: <s> | null, class?: server | camera, every?: <s> | null}       # no via, heard_ago, every — null; no class — server
  catalog:      the names of the manifests of the holder's catalogue; which of them have domain.ref — by the bytes of the manifests themselves (steps 4, 5)
  mark:         the mark reported by the form «Generation, mark, limits» or null — no mark
  stored:       the whole whole of the generation mark.rev, as the holder read it, or null — unreadable
  body:         the text of the request body as received (the bytes are the UTF-8 of this text)
  refreshed_ago: monotonic s since this process wrote the mark; null — it did not write it
  via:          the road of the request: null — directly, otherwise the name of the relay
  heard_ago:    monotonic s since the last acceptance of this member by any road; null — not heard
  class:        Entry.class of the member: step 2a, road_quiet
  every:        the period this answer will tell the member; null — no field in the answer; the relay over its own memory passes neither class nor every
output:         {result: generation, rev, base, whole, sign_failures?} | {result: heard, refresh, sign_failures?} | {result: same}
                | {result: ignored}
                | {result: refused, status, reason: not_a_publication | same_sent_at | rebase | not_ready | whole_too_large
                   | rev_exhausted}
  whole:        the whole whole' of the new generation (step 7) — the object whose JCS is written to reports/<rev>
  refresh:      true — the mark is rewritten (step 6 or a repeat by another road of step 2), false — nothing is written
  sign_failures: at generation and heard with refresh: true — the field sign_failures as it is written to the mark; no field — not taken
                into the mark (not in the publication or out of form, out_of_delta); at heard with refresh: false there is no field (guesses
                of stage C ACC-FORM-31-01, ACC-G01-COUNTER-31-01, the Architect's decision of 2026-10-23: the output form is extended)
  status:       the answer code of the door: 400 not_a_publication (step 1); 409 same_sent_at (step 2), rebase (step 3), not_ready
                (step 5); 413 whole_too_large (step 4a; at the door — {error: "whole too large", detail}); 503 rev_exhausted (step 7)
exit:           0 — computed (a refusal by a word included); 2 — the input is out of form (the mark — strictly «Generation, mark, limits»:
                stale is always there; signature is optional also at a mark without via); an extra field of the input, the mark or stored — 2;
                the field names are compared exactly (guess of stage C ACC-FORM-31-01, the Architect's decision of 2026-10-23)
```

## The relay batch: limits

Moved from [P/09.2](../../09-agent/spec/09.2-agent.norms.md) N1.4 (`BATCH_LIMIT`, `KNOCKS`) without a change; the limits
are read by the relay (it writes the batch, P/09.2 N3) and by the holder (it accepts it, [P/08.3](../../08-domain/spec/08.3-domain.norms.md)
N3 «the holder on `POST /api/relay/<relay>`», N4) — they have references here (C08-G05, the Architect's decision of 2026-10-25).

`BATCH_LIMIT` and `KNOCKS` have one numeric source: the uniquely named rows of the [P/08 form](../../08-domain/forms/runtime-constants.tsv). In the following block the names denote those row values; `KNOCKS + 1` is the next stranger after the memory is full. The formula `BATCH_LIMIT = 4 × BODY_LIMIT` is unchanged; there is no new setting or wire field.

```yaml
BATCH_LIMIT:   the P/08 form value     # = 4 × BODY_LIMIT (the section «Generation, mark, limits»); a body of POST /api/relay/<relay>
                          # larger — 413 before parsing; the entries — in the order of the member names; a member larger than BODY_LIMIT is not sent (log)
KNOCKS:        the P/08 form value; a knock body at most 256 KiB, with the field row — 768 KiB: the section row up to 512 KiB; at the relay — KNOCKS strangers in memory, the last one from a name
               replaces the former; stranger KNOCKS + 1 evicts the oldest knock (by the reception time); the evicted one learns of it
               only by the holder's knocking (the section «The knock») — there is no new refusal
holder:        at the holder, more than KNOCKS knocks in a batch — those beyond the first KNOCKS by name are skipped without a write; a knock with a body
               larger than 256 KiB, with the field row — larger than 768 KiB — skipped without a write (as a knock out of form, P/08.3 N3 step 3); the batch lives; 413 — only
               a whole batch larger than BATCH_LIMIT
answer:        the holder's answer to the client of the agent and of the relay (carry on POST and GET /api/carry, RelayAnswer on
               POST /api/relay) the client reads at most BATCH_LIMIT; larger — as «no answer» (P/09.1 N3 step 5:
               the next pass, the base as before), a log line without the value of the body; there is no new number
               (C09-ANSWER-LIMIT-01, the Architect's decision)
```

## Production obligations

ADR-0130 Addendum (10), MB2: cleanup removes ALL report generations older than the last two committed generations, with their deltas, and the uncommitted objects above the current mark by the existing identity rule. It is resumable: a crash or bounded interrupted pass leaves pending eligible generations for a later cleanup attempt, including generations older than `rev−2`. Publication order remains whole, delta, then mark; cleanup cannot delete the current or previous committed generation. A finite positive implementation-declared cleanup/work budget bounds each attempt and completion under qualified workload.

MB3: before declaring `silent` for a missing or hash-mismatched generation, reread the marker exactly once and read the generation named by that marker. If the marker is stable and the named object is still missing or mismatched, keep the existing `silent` outcome. If the reread marker changed and its newly named generation cannot be read exactly, the observation remains temporarily unconfirmed: defer publication of this derived snapshot; a door requiring the confirmed read uses the existing `503 unavailable` outcome. Do not publish `silent` from the race, combine generations, invent a member state or loop indefinitely.

## Vectors

The package [`accept`](../vectors/accept/README.md) (analysis of review of stage A 8–10, № 13): 66 rows — the inputs of the command `accept`
of the acceptance of M11/3 (sc. 13, 26 rows) and M11/4 (sc. 06, 9 rows — roads) without a change of bytes, 3 rows of ADR-0113 (`road_quiet`, a change of `every`) (the scenarios and inputs were removed by the move
of lesson 8 — the table is the only source of these cases), 2 rows of the relay door and 25 rows of stage C: the other families
of `member_objects`, extra fields and `@exit 2`, the form of `sign_failures`, the form of the mark — `sign_failures` {} and the time `received_at` (ACC-FORM172, ACC-TIME172; the README of the package), 1 row — a mark without `stale` (coverage audit of P/08, the second pass of Gemini). The implementation of the holder and
the relay passes them with its function, without a stand. There is no row for step 4a (`whole_too_large`) — a candidate of the package
(the README of the package, «Candidates»; analysis of review of stage B 8–10, № 6). The limits of the relay batch (the bound 64 MiB, knock 33,
a knock larger than 256 KiB) are not expressed by the function «accept» — by reading (C08-G05).

The canonical JSON (RFC 8785, ADR-0072) that the contract relies on is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the form of RFC 8785 → sha256; ADR-0083 addendum (33) item 2).

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.

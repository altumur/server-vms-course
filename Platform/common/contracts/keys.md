# The domain key set contract: the row `domain/keys`, the function `keys`, the revocations `domain/revoked` and their removal

This English text is the source; the Russian translation `ru/contracts/keys.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a common algorithm of several processes is a contract, not
copies in chapters; analysis of review of stage A 8–10, № 13 / decision 2, № 3). The owner is lesson P/08, chapter 8.2
([norms](../../08-domain/spec/08.2-domain.norms.md)): the process `domain`
of the holder signs the set with the root and keeps the revocations. Participants:

| Who | What it does by the contract |
|---|---|
| the member's agent ([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.4 `from_carry`) | accepts the set from the holder's answer with the function `keys` and writes `domain/keys`; merges `domain/revoked` of the answer with its own row and removes the `prune` entries |
| the relay ([P/09.2](../../09-agent/spec/09.2-agent.norms.md) N1.4 `keys`) | reads the accepted set of its cluster (id-map M11/2-04) |
| the cluster console ([P/06.3](../../06-console/spec/06.3-console.norms.md) «Keys exist») | accepts the set with the function `keys` with the pinned root |
| the checkers of a domain token ([the domain token contract](domain-token.md)) | read the accepted set and `domain/revoked` |
| the process `domain` at a move and at following ([chapter 8.8](../../08-domain/spec/08.8-domain.norms.md) N1.8; «follow» — the section «The follow set» below) | accepts the sets of the answers of `/api/held` with the function `keys` |

Moved from M11/2 N1.2 (the rows `row`, `doc`, `writer_forms`, `only_forward`), N1.6 (the block `domain/revoked`: the form,
`writer`, `order`, `prune`, `readers`), N3 «`keys(pinned, held, offered)`» (steps 1–8 and the paragraph about the refusal) and the rows
of `from_carry` of P/09.1 N1.4 about `revoked` without a change of behaviour. The owner keeps: the root and its pinning (P/08.2 N1.1),
the `rev` of the writer, the emergency `rev` and the premise of clocks (P/08.2 N1.2 `rev`, `emergency`, `clocks`), the holder keys and `OLD_KEYS`
(P/08.2 N1.3, N1.6), the changes of the set (P/08.2 N3; installation — [P/02.4](../../02-installer/spec/02.4-installer.norms.md) N3),
the offline revocation window (P/08.2 N1.7). What is common to the forms — the [domain founding contract](domain-founding.md)
«Common rules of forms» (layout audit, B-03: hex, canonical base64url, JCS — RFC 8785, Ed25519 — RFC 8032, X25519 — RFC 7748, completeness
of JSON forms, a repeated key, «integer»). References in the moved text: «N1.x», «N3» — the chapters of P/08.2 (formerly of lesson M11/2; the numbers of the
subsections are the former ones); «lesson N» — lesson M11/N, their addresses now: «lesson 3» (the agent, the admission and the signature of a member) — P/09.1 and P/08.3,
«lesson 3 N1.6 from_carry» — P/09.1 N1.4 `from_carry`, «lesson 7» (the kind token) — P/08.7, «lesson 9» (the revocation of a person) — P/08.4,
«lesson 10» (the issuing holder) — P/08.8 (analysis of review of stage B 8–10, № 22; Kimi SB810-07).

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The rows of the contract: the set `domain/keys` and the revocations `domain/revoked` — `Platform/08-domain/data/keys.schema.json`, `Platform/08-domain/data/keys.outcomes.tsv`; `Platform/08-domain/data/revoked.schema.json`, `Platform/08-domain/data/revoked.outcomes.tsv`; the pinned root `domain/root` (`pinned`) — `Platform/08-domain/data/root.schema.json`, `Platform/08-domain/data/root.outcomes.tsv`. The set comes in the holder's answers — `Platform/08-domain/spec/08-domain.api.openapi.yaml` (`/api/carry`) and `Platform/06-console/spec/06-console.api.openapi.yaml` (`/api/held`) (layout audit, V-31, V-32, B-15; the Architect's decision of 2026-10-25).

## The set `domain/keys`

The form of the rows of the families — `Platform/08-domain/data/keys.schema.json`, `keys.outcomes.tsv` and
`Platform/08-domain/data/revoked.schema.json`, `revoked.outcomes.tsv` (C04-DEP-OBS-HEARTBEAT-01: the data files named by a contract are in the reading of `common`, ADR-0083 addendum (32) item 1).

From M11/2 N1.2:

```yaml
row:           domain/keys {doc: <the JSON text of the document>}   # exactly one element doc, a string; another composition — not_a_set;
                                                           # a store row (P/01.1); the writer at the holder is the process domain,
                                                           # at a member — the agent (lesson 3) after the function keys (N3); the agent of the cluster
                                                           # of the holder does not write it while the cluster holds the term (the term record contract «The switch point `switch`»)
doc:                                                       # a closed set of fields; an extra field — not_a_set; arrays — without
                                                           # a meaning of order, a repeated element is allowed; the writer — in ascending order
  domain:          the domain name (N1.1)
  rev:             an integer 1 … 2^53−1
  root:            hex of the public root
  current:         kid of the token key with which the holder signs now; ∈ keys; ∉ until
  keys:            {<kid>: <hex of the public token key>}, not empty; kid — a non-empty string
  until?:          {<kid>: <wall-clock seconds>} — the key is still accepted up to this moment inclusive; kid ∈ keys
  keep_until?:     {<kid>: <wall-clock seconds>} — the key is still accepted for the kinds keep (the token contract step 5a; ADR-0110 addendum (10)); kid ∈ keys and kid ∈ until: a key with keep_until keeps an expired until too, otherwise step 5a would be silent and the key would be accepted for all kinds; without this — not_a_set (ADR-0110 addendum (12) item 1); an expired until is removed only together with keep_until; at most 8 live ones, the oldest is removed, the journal domain.keys.keep_dropped
  issuing:         [<serial>…] — the keys of the issuing holder (lesson 10); serial — a non-empty string
  revoked_issuing: [<serial>…] — the revoked keys of the issuer; always an array, can be empty
  revoked_members?: [<hex of a member key>…] — the revoked keys of members (lesson 3: the admission and the signature of a member are checked against it)
  stolen_issuing?: [<serial>…] — the issuers revoked by a theft together with all the past before it (P/08.2 N3 step 3), a subset of revoked_issuing, otherwise not_a_set; none — empty; passes into each next set; the sources of the assembly «from nothing» — revoked_issuing without them (P/08.8 N1.8a; ADR-0113 addendum (16) item 2)
  thefts?:         an integer 1 … 2^53−1 — the count of changes after theft (P/08.2 N3 step 3); none — 0; passes into each next set
  book_seal:       hex of the public book acceptance key X25519 (N1.4); required: a set without it does not read; a point of small
                   order (X25519 with any scalar gives a zero shared secret, RFC 7748 §6.1) — the set does not read
                   (added by the M11 reconciliation, S1)
  kid:             "root"
  sig:             base64url of the Ed25519 signature of the root over UTF-8(JCS(doc without kid and sig))
writer_forms:      kid of a token key = the first 8 hex characters of its public key; serial = the first 16 hex characters of the public
                   key of the issuer; the reader accepts any non-empty string
only_forward:      a member holds one set; a set with a smaller rev — a refusal, with an equal one — «holding», it is not rewritten
```

The `rev` of a new set at the writer (an ordinary, a planned and an emergency change) — [P/08.2](../../08-domain/spec/08.2-domain.norms.md) N1.2 `rev`, `emergency`, `clocks`.

## The key fingerprint

From P/08.2 N1.1 `fingerprint` without a change of behaviour (the owner of the text is P/08.2 N1.1; here — for lesson P/09, which
prints the fingerprint of the member key, P/09.1 N1.1 `born`; analysis of review of stage B 8–10, № 4, Claude `S-1`):

```yaml
fingerprint:   hex(sha256(<32 bytes of the public key>)[:8]) — 16 characters; this is how people and journals name the root and the keys:
               the fingerprint of the root (domain installation, join), of a member key (the line of the agent journal «member key <fingerprint>»,
               admission by the operator — P/08.3 N1.1, the field knock.fingerprint)
not_serial:    a fingerprint is not a serial (writer_forms above: the first 16 hex characters of the public key itself, without sha256) and not
               the fingerprint of a TLS centre (sha256 hex of the DER certificate, 64 characters — the role certificate contract `fingerprint`)
```

## The function `keys`

From M11/2 N3 «`keys(pinned, held, offered) → took rev | holding rev | refused <word>`»:

A function of the member's agent over the set from the holder's answer (lesson 3) and of the process domain over its own set at a change. The steps are in
order; the first rule that fires gives the result.

```
1. no pinned                                                               → refused no_pin
2. offered is not {doc: string}; doc is not a JSON object or has a repeated key, a field outside the closed set of N1.2, a required one is absent,
   a type or a bound not by N1.2 (except book_seal)                        → refused not_a_set
   # kid or sig not a string, root not hex of 32 bytes — here; an empty issuing is allowed (non-emptiness is named only for keys)
3. kid ≠ "root"                                                            → refused bad_signature
4. doc.root ≠ pinned.pub or doc.domain ≠ pinned.domain                     → refused another_root
5. the signature sig does not verify with the key pinned.pub over JCS(doc without kid and sig) → refused bad_signature
   # sig is a string but not base64url or not 64 bytes — also here
6. no book_seal, not hex of 32 bytes or a point of small order (N1.2)      → refused no_book_seal
7. held exists: doc.rev < held.rev → refused older (rev held); doc.rev = held.rev → holding (rev held)
8. otherwise                                                               → took (rev doc); the row domain/keys := offered
```

A refusal does not change the row `domain/keys`; the member keeps trusting the former set and writes the reason into the journal (M13).

`held = null` — at an agent without a trusted set in memory and with its own row unreadable (after start): step 7 does not judge, the set is accepted from the pinned root; the rollback limit — [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.4 `from_carry` (ADR-0110 addendum (28)).

«N1.2» in steps 2 and 6 is the section «The set `domain/keys`» above; `pinned` is `{pub, domain}` of the row `domain/root` ([the domain founding contract](domain-founding.md) «Root pinning»; the form — «Form» above).
The form of the function is the input of the command `keys` ([P/08.2](../../08-domain/spec/08.2-domain.norms.md) N5).

A copy from P/08.2 N5 (layout audit, the Architect's decision of 2026-10-25, B-14):

```yaml
# Inputs are closed objects: all fields are required except those marked «?» (null — where named), an extra field or a field of another type — code 2.
keys:        input {pinned: Pin | null, held: <doc in the form «The set domain/keys» that the member trusts> | null, offered: <the row domain/keys as received>}
             output {result: took | holding, rev} | {result: refused, reason: no_pin | not_a_set | bad_signature |
                   another_root | no_book_seal | older, rev?}            # rev at older — the rev of held
held:        not in the form «The set domain/keys» (book_seal included) — code 2: this is the set that the member already trusts
Pin:         {pub, domain}                     # pinned in the input not in this form — code 2
output:      the closed objects above; keys — in any order
exit:        0 — computed (a refusal by a word included); 2 — the input is not in this form
```

## Revocations `domain/revoked`

From M11/2 N1.6:

```yaml
domain/revoked: {jtis: "<jti>:<exp>,…"}      # exactly one element jtis, a string; empty — ""; no row — no revocations;
                                            # another composition, an entry not «<jti>:<JSON number>» (jti by the token grammar) — out of form:
                                            # token → no_revocations; the reader checks neither a repeated jti nor the order
  writer:      the process domain at a revocation (lesson 9: a person; lesson 7: a kind token) and at every pass of the holder, CAS by the read version: otherwise the pass
               would overwrite a revocation of the same minute; a conflict of a revocation — read again, at most 3 times, then 503 unavailable; a conflict of a pass — the next pass
               (C08-REVOKED-CAS-01); at a member —
               the agent by merging the holder's answer with its own row (lesson 3 N1.6 from_carry; added by the Quint model of M11,
               RV): at a member an entry is removed only by prune; the agent of the holder's cluster does not write it while the cluster holds the term (the term record contract «The switch point `switch`»)
  order:       ascending by jti in bytes; exp — a JSON number, the exp of the revoked token
  repeat:      a repeated jti in one row (its own or of the answer) at a merge and a cleanup — for the jti the greatest exp is taken, then prune:
               a repeat does not shorten a revocation (x:100,x:200 at now = 161 — x:200 remains; guess of stage C KEYS-G01, the Architect's decision of 2026-10-23)
  prune:       entries with exp + TOKEN_SKEW < now, strictly, the writer MUST remove — the list is bounded by the number of live tokens;
               at now = exp + 60 the token is still valid (N3 token step 6), and its revocation stands (ADR-0074 addendum 7)
  readers:     the cluster console, the worker roles — by the platform basis of rights (P/02.5 N1.4), the agent (lesson 3); at a member — a copy
```

From M11/3 N1.6 `from_carry` (the member's agent, the field `revoked` of the holder's answer; now P/09.1 N1.4 `from_carry`):

```yaml
merge:          revoked → a union with its own row domain/revoked: the entries of the answer ∪ its own by jti (at an equal jti — the greater
                exp); only prune of lesson 2 N1.6 removes (exp + TOKEN_SKEW < now) — a revocation is not cancelled by an answer (added
                by the Quint model of M11, RV: after an emergency move an answer from a copy would otherwise remove the revocation of the last BACKUP_EVERY);
                the same after a move without stolen. The exception is a change after theft: an agent that wrote domain/keys with a set whose thefts is
                higher than that of the trusted set of its memory (P/09.1 N1.4 from_carry; not from the row — addendum (25) item 1), by any path —
                by the holder's answer (from_carry) or by following (the write of domain/holder with a set, «The follow set»), — in the same
                batch sets domain/revoked := {jtis: ""}, and the set from the answer — {jtis: ""} ∪ the revocations of this answer. No memory and
                its own domain/keys does not read — it does not touch the row until the holder's answer, then merges (ADR-0110 addendum (25) item 2, addendum (26)).
                Any merge larger than ceiling (413) — is replaced by the row of the answer, the journal domain.revoked.replaced; it happens mostly
                after a cleanup by theft, then the holder's row has lost nothing (addendum (27) item 1; the limit — P/09.1 N1.4 from_carry).
                The holder has cleaned the row (P/08.2 N3 step 3b): its revocations are for the tokens of former keys,
                the signature step no longer lets them through; revocations after the change come by an ordinary merge. Otherwise the full row would be held
                for years, new revocations would take it beyond ceiling, the agent's write — 413, and a token revoked after the change would pass at the member;
                a member usually takes the emergency set by following before the report, the answer is then holding, therefore the rule is by the write of the set,
                not by the answer (ADR-0110 addendum (22), addendum (24) — replaces «replaces by the answer» of addendum (22));
                its own row does not read — the agent, the only writer at a member, overwrites it by CAS on the read
                version with the entries of the answer, the reason into the journal without a value (V7 item 3, the Architect's decision of 2026-10-28, P2; row 44 of the list)
```

`TOKEN_SKEW` and «N3 token step 6» are the [domain token contract](domain-token.md) «The token», «The check»; «prune of lesson 2 N1.6» is
the row `prune` above. When the agent applies the field `revoked` (after the outcome `took` or `holding` of the function `keys` over the set of the same
answer) — P/09.1 N1.4 `from_carry`.

## The follow set

Moved from [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N3 «follow» step 1a without a change of behaviour (layout audit, the Architect's decision of 2026-10-25,
A-08). The follow set is the memory of the member's agent; it checks the term records of steps 2–4 of «follow» (P/09.1) and the records
of a move (the move set — by the same rule, P/08.8 N1.8 step 5, the start of the pass for it is the start of step 5; the difference of the move set: its own domain/keys which is not
confirmed by its own domain/holder that passed record with this set (its own record is spoiled, unreadable or absent; a break of the move does not leave such a row, P/08.8 N1.8 step 8): the move set starts not
from it but from null (the pinned root), and it serves only if no neighbour gave a set; its rev enters the greatest
known rev of the emergency rev (P/08.2 N1.2 emergency); the follow set of the agent — the former rule
(C08-MOVE-UNCONFIRMED-KEYS-01, -02)); the switch point by it is the term record contract
«The switch point `switch`».

```
keys of the answers of /api/held — by the function keys (the domain key set contract) by the pinned root into the follow set — the agent's memory, at the
start — the row domain/keys of its own store (a move without stolen changes the issuer: the new set comes this way, before
the answer of the new holder); the set of an answer is taken only if the term record of the same answer passes record with this set and
its term is not less than its own record (SET_GUARD; the term of its own record — of its own domain/holder that passed record by the follow set of the start of the
pass; it is computed once per pass: a set taken in the pass does not recheck it and does not remove the bound, otherwise a second candidate with a greater rev takes the term back, and the outcome depends on the order of CLUSTERS (Quint M12 N2; C09-SET-GUARD-OWN-02); there is no checked own record at the start of the pass — nothing to compare with; C09-SET-GUARD-OWN-01,
the decision of «Domain Specification»; its own record whose issuer is in revoked_issuing of the answer's set, while thefts of this set is greater than that of the follow set of the start of the pass, is revoked by a theft and does not serve as a bound: otherwise the thief's record of a huge term would forever block the set of the change after theft; revoked_issuing grows at every move, only thefts tells a theft apart (P/08.2 change after theft step 3): otherwise a cut-off member would take back an honest chain of handovers of the same issuer, C08-GUARD-STOLEN-RECORD-01; revoked_members does not fit for this: at a second theft on the same holder the new key is not in it, Quint M12 N8, C08-GUARD-THEFTS-01); the same condition at `from_carry` (P/09.1 N1.4) with the term record of this answer, the bound is the greatest of the bound of the pass and of the term written by step 4 of «follow» of this pass: otherwise a lone holder of a smaller term takes the term back (C08-GUARD-FROM-CARRY-01); the agent writes the row domain/keys from the follow set when the condition of the switch
point (the term record contract «The switch point `switch`») is false by this set (at the holder's cluster — from the switch point; added by the Quint model of M11, G1, G7); a set by which its own term record does not pass record it writes only in one batch op: batch with a term record that passes by this set: the best one of step 4 of «follow» or the record of the answer `from_carry`; each row has its own cas, the guard domain/agent-turn (otherwise a break between them deprives its own record of the check and the bound SET_GUARD of the next pass is lost; the Architect's decision of 2026-10-31, Quint M12 N2, C08-KEYS-CLAIM-BATCH-01); the batch refused — the set stays in memory (C09-HELD-MEMORY-01), together with it the bound of this pass stays in memory, the next pass writes the batch again; the bound lives in memory only while its own record has not changed: at the start of the pass, before the follow set and the bound, its own record that passed record by its own row domain/keys with a term above the bound of memory (no bound — any) removes the set and the bound of memory, otherwise a record of a new term does not pass the set of memory, the condition of the switch point is false and the next pass writes a smaller term over it; the set is not lost: it will come from a neighbour and meet the new bound, SET_GUARD will refuse, step 2a will raise an alarm (the Architect's decision of 2026-11-01, Quint M13 N15, C09-HELD-MEMORY-02); a row with a `rev` greater than its own set it does not rewrite: at the target of a move it is put by the batch claim before the agent has heard the new set (C08-TARGET-KEYS-RACE-01)
```

## Production obligations

Destructive cleanup MUST obey the clock qualification and monotonic deadline rules of [the event journal](event-journal.md), Q6 of ADR-0130 Addendum (10). An uncertain wall-clock jump defers deletion; required security/replay state is retained under finite resource/admission budgets.

## Vectors

The package [`keys`](../vectors/keys/README.md) (analysis of review of stage A 8–10, № 13): 29 lines — 21 inputs of the command `keys` of the acceptance of
M11/2 (sc. 01–03) without a change of bytes, two lines of the field `thefts`, four lines of the field `keep_until` and two lines of the field `stolen_issuing`; the scenarios and the inputs were removed by the move of lesson 8 — the table is the only source of these
cases. The merge and the removal of `domain/revoked` at a member (`merge`, `repeat`, `prune`) — `revoked.tsv` of the same package (7 lines;
guess of stage C KEYS-G01, the Architect's decision of 2026-10-23); the bound of `prune` at the token checker — the vectors [`domain-token`](../vectors/domain-token/README.md) (formerly sc. 07
of the acceptance of M11/2) through the function `token`.

A row of `revoked.tsv` checks the merge and the removal at a member: the input is the JSON object `{own, answer, now}`: `own` is the member's own row `jtis`, `answer` is the `jtis` of the holder's answer or `null` (there are no entries of the answer: `repeat` and `prune` apply to `own`), `now` is the wall seconds; the output is the `jtis` of the row that the agent writes, as a JSON string.

The canonical JSON (RFC 8785, ADR-0072) on which the contract relies is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the form RFC 8785 → sha256; ADR-0083 addendum (33) item 2).

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.

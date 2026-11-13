# The domain envelopes contract: `x25519:v1`, `m1`, the content of `sealed`

This English text is the source; the Russian translation `ru/contracts/domain-envelopes.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a contract that one
process writes and others read lies in `Platform/common/`; analysis of the review of stage A 8–10, № 12). The owner is
lesson P/08: the book acceptance key and its envelope are chapter 8.2 ([P/08.2](../../08-domain/spec/08.2-domain.norms.md) N1.4, N1.5), the answer
of the holder to a member is chapter 8.3 ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.5). Participants:

| Envelope | Seals | Carries | Opens |
|---|---|---|---|
| `x25519:v1` of a contribution to a book | the agent of the member ([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.2) before signing the report | the relay ([9.2](../../09-agent/spec/09.2-agent.norms.md)) — bytes, it cannot open | the holder when assembling the book ([8.5](../../08-domain/spec/08.5-domain.norms.md)) |
| `x25519:v1` of the transfer keys (`keys_sealed`) | the former holder ([8.8](../../08-domain/spec/08.8-domain.norms.md) N1.7 step 5) | — | the target of the transfer (8.8) |
| `m1` of the answer `carry` | the holder (8.3) | the relay (9.2) — bytes | the agent of the member (9.1) |
| `m1` of the answer of the token door | the holder ([8.7](../../08-domain/spec/08.7-domain.norms.md) N1.3) | the relay (9.2) | the agent of the member (9.1, [the local token door contract](local-token-door.md)) |

Moved from M11/2 N1.5 (a paragraph, a block, the refusal table, the paragraph about trying AAD), M11/2 N3 «seal / open» (the
order of checks), M11/3 N1.5 (the block `envelope_m1` and the paragraph of refusals), the forms of the fields `sealed` from M11/3 N1.5 `sealed?`, M11/5 N1.4 `carry`, M11/9
N1.3 `carry` and N1.6 `carry` without a change of behaviour. The book acceptance key (`domain/book-seal`, `book_seal` of the set), its
birth and changes belong to the owner (P/08.2 N1.2, N1.4, N3); what the agent does with the opened content is P/09.1 N1.4 `sealed` and the lessons of the
fields. The references «lesson N» in the moved text are lesson M11/N; their addresses now: «lesson 3» (the agent seals before signing the
report) — P/09.1 N1.2, «lesson 4» (the relay) — P/09.2, «lesson 5» (the assembly of a book, the family row `domain.books.<book>.from`)
— P/08.5 N1.3 and P/02.1 N1.2b (analysis of the review of stage B 8–10, № 22; Kimi SB810-07); «lesson 2 N1.5» in the section `m1` is the section
«Envelope `x25519:v1`» of this contract. The JSON Pointer path follows [the sealing contract](sealing.md) «AAD path».

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

Opening is by `seed_secret` of the row `domain/book-seal`, sealing is to `book_seal` of the set `domain/keys`, the recipient of `m1` is the member key `domain/member-key`: `Platform/08-domain/data/book-seal.schema.json`, `Platform/08-domain/data/book-seal.outcomes.tsv`; `Platform/08-domain/data/keys.schema.json`, `Platform/08-domain/data/keys.outcomes.tsv`; `Platform/09-agent/data/member-key.schema.json`, `Platform/09-agent/data/member-key.outcomes.tsv`; the content of `sealed` is the rows `Platform/08-domain/data/grants.schema.json`, `Platform/08-domain/data/grants.outcomes.tsv`; `Platform/08-domain/data/break-glass.schema.json`, `Platform/08-domain/data/break-glass.outcomes.tsv`; `Platform/08-domain/data/book.schema.json`, `Platform/08-domain/data/book.outcomes.tsv`. The field `sealed` of the answer `carry` and `m1` of the token door are `Platform/08-domain/spec/08-domain.api.openapi.yaml` (layout audit, V-10…V-13; the Architect's decision of 2026-10-25).

## Envelope `x25519:v1`

From M11/2 N1.5:

A secret field (`*_secret`, [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.3a) of a member's contribution to a book travels to the holder as an envelope to `book_seal`: the agent seals
before signing the report (lesson 3), the relay carries the bytes (lesson 4), the holder opens only when assembling the book (lesson 5).

```yaml
envelope:      x25519:v1:<eph>:<nonce>:<ct>          # exactly five parts separated by «:»; parts 3–5 — base64url without «=»
  eph:         32 bytes — the X25519 public key of the sealer's one-time pair
  nonce:       12 random bytes
  ct:          AES-256-GCM(key, nonce, plain, aad) with a tag of 16 bytes; not shorter than 16 bytes
key:           HKDF-SHA256(ikm = X25519(eph_priv, book_seal), salt = eph ‖ book_seal, info = "w2c book seal x25519:v1", L = 32)
               # at opening ikm = X25519(seed_secret, eph); book_seal is the public half of seed_secret
aad:           UTF-8(JCS([member, source_path, item])) ‖ 0x00 ‖ UTF-8(pointer)
  member:      the name of the contributing member
  source_path: the key of the source row of the contribution in the member's store (lesson 5: the family row domain.books.<book>.from)
  item:        the element of this row — the contribution
  pointer:     the JSON Pointer of the secret in the JSON document of the element — by the path rule of the sealing contract (`~0`, `~1`, indices)
plain:         the UTF-8 bytes of the secret value as given; an empty value is sealed too
seal:          a new eph pair and a new nonce for every envelope; two envelopes of one value differ; book_seal of small
               order (X25519(eph_priv, book_seal) — a zero shared secret) — there is no envelope, refusal not_an_envelope
               (added by the reconciliation of M11, S1)
```

A refusal of opening is one of three words; the value is repeated neither in the reason nor in the journal ([P/06.2](../../06-console/spec/06.2-console.norms.md) N1.4):

| Word | When |
|---|---|
| `not_v1` | the text does not begin with `x25519:v1:` (another version, another envelope, not a string) |
| `not_an_envelope` | there are not five parts; a part is not base64url without `=`; `eph` is not 32 bytes, `nonce` not 12, `ct` shorter than 16; X25519 gives a zero shared secret |
| `does_not_open` | the AEAD did not open (not that book acceptance key, another member, source_path, item or pointer, a spoiled `ct`) or the opened bytes are not UTF-8 |

A substituted AAD and a foreign key are indistinguishable — both causes are `does_not_open`. Trying other AAD at opening is forbidden.

From M11/2 N3 «`seal(book_seal, plain, aad)` and `open(seed_secret, envelope, aad)`»: sealing and opening are N1.5 (here — the
block above); the order of the opening checks: `not_v1` → `not_an_envelope` → `does_not_open`.

The same envelope with another AAD context is the holder's transfer keys `keys_sealed` (to `seal` of the target, AAD `take|<to>`; the form of the
plain text and the refusal — [P/08.8 N1.7](../../08-domain/spec/08.8-domain.norms.md) step 5).

## Envelope `m1`

From M11/3 N1.5:

```yaml
envelope_m1:    m1:<eph>:<nonce>:<ct>             # like x25519:v1 of lesson 2 N1.5: four parts separated by «:», 2–4 — base64url without «=»
  recipient:    X25519 of the member key: u = (1 + y)/(1 − y) mod 2^255 − 19 from y of the public Ed25519 (the high bit cleared),
                little-endian (RFC 7748 §4.1); the private one — the first 32 bytes of SHA-512(seed_secret) as an X25519 scalar
  eph:          32 bytes — a one-time X25519; nonce — 12 random bytes; ct — AES-256-GCM with a tag of 16, not shorter than 16
  key:          HKDF-SHA256(ikm = X25519(eph, recipient), salt = eph ‖ recipient, info = "w2c carry to a member", L = 32)
  aad:          UTF-8("m1" + hex of the member's public key)
  plain:        UTF-8 of the text of a JSON object
```

A refusal of opening is a word; the value is not repeated: `not_m1` (the text does not begin with `m1:`), `not_an_envelope` (there are not
four parts, a part is not base64url without `=`, `eph` is not 32 bytes, `nonce` not 12, `ct` shorter than 16, a zero shared secret),
`does_not_open` (the AEAD did not open, or not UTF-8). Trying other forms is forbidden.

## Contribution

Moved from [P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.2 (`source_row` `entry`) without a change of behaviour: the form of
the input is written by the worker (P/03.7), carried by the agent (P/09.1 N1.2 `in_report`), checked by the holder's book assembly (P/08.5 N1.3, N3 step 4)
(layout audit A-22, the Architect's decision of 2026-10-25). The contribution row is `<sub>/<row>` or `<sub>/<row>/<slot>`, the element is an input of the book: the name of the element is `item`,
the value is the text of a JSON object (P/03.7 N1.2 `source_row`).

```yaml
entry:       a JSON object: the field key is a non-empty string, the field to is a member name, a list of names or "servers" — all members of class server of this pass: the worker's copy of the list holds only its own sections, it cannot enumerate all (ADR-0113 addendum (8) item 4, addendum (9) item 2); the name servers is taken: P/08.3 N3 «admit a member» step 1. The addressee «all» is the declaration of a book to: "*" in the manifest, P/08.5 N1.3 to_all: the field to of such an input is not read, and "*" in an input of an ordinary book is bad_contribution; the other fields are the worker's;
             *_secret at any depth is a secret (P/06.2 N1.1; and a field named exactly `_secret`, without a prefix — the reconciliation of M11,
             the implementations agreed), in the member's row it is an envelope of the member's ring (the sealing contract) with the AAD
             of the profile P/08.5 N1.3 at_rest: the row key, 0x00, «/<item>» and the JSON Pointer of the secret in the text of the element
```

## Content of `sealed`

The field `sealed` of the holder's answer to the agent (`carry`, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.5) is
an envelope `m1` with a JSON object of what is secret to the member. From M11/3 N1.5 `sealed?`, M11/5 N1.4 `carry`, M11/9 N1.3 `carry` and N1.6 `carry`:

```yaml
sealed:         an envelope m1 with a JSON object of what is secret to the member; only when there is something secret or held — there is no empty envelope
                (added by the reconciliation of M11, D8)
  grants?:      {doc} — the row domain/grants/<member> (P/08.4 N1.3 carry)
  anywhere?:    {as_of, sha256} — the summary of P/08.4 N1.3 anywhere; the body by the door on a change; does not depend on grants
                sha256 names the complete {doc, as_of} value of the 200 body, by P/08.4 N1.3 carry (G09-ANYWHERE-HASH-01); as_of is part of the digest
  held?:        [<field name>…] of "grants", "roles", "anywhere", "break_glass" — not sent in this pass, do not touch the copies (P/08.4 N1.3, N1.6 carry): the row is unreadable, the assembly did not converge, the table is over the limit;
                the absence of a field without its name in held means «no row»
  roles?:       {doc_sha256, groups, assigned, admin_at} — the role table of this member (P/08.4 N1.3b); always goes together with grants, only with it;
                empty — {doc_sha256, groups: {}, assigned: {}, admin_at: {}}; the intermediary (P/09.2) does not see the assignments (ADR-0098 §4)
  break_glass?: {pwhash_secret, set_at} (P/08.4 N1.6 carry)
  books?:       {<sub>: {<book>: {<item>: <JSON text>}}} — the holder's row domain/<sub>/<book>/<member>, secrets opened; a book to: "*" does not go here: carry.book_rev (P/08.5 N1.4)
                by the holder's ring before m1 (P/08.5 N1.4 carry)
```

Opened `sealed` content is the current closed composition above. An unknown field makes that content unreadable; it is not accepted by skipping the field. Keep the copies, their freshness marks and related writes unchanged, using the existing unaccepted-content path of P/09.1 N1.4. This does not change the m1 cryptographic open function or its historical byte witnesses. What the agent writes from an opened envelope and what it does with one that did not open is [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.4 (`sealed`, `member_row`,
`member_copy`, `break_glass`). The envelope `m1` of the answer of the holder's token door carries the JSON text `{request_id, token, exp}` (P/08.7 N1.3 `answer`).

## Vectors

The package [`domain-envelopes`](../vectors/domain-envelopes/README.md) (analysis of the review of stage A 8–10, № 12): opening
`x25519:v1` (`x25519-open.tsv`) and `m1` (`m1-open.tsv`), the rounds `seal-round` (`x25519-round.tsv`) and `seal-member-round`
(`m1-round.tsv`). The rows are the inputs of the acceptance vector commands of M11/2 (`seal`, `seal-round`) and M11/3 (`seal-member`,
`seal-member-round`) without a change of bytes; the scenarios and inputs were removed by the move of lesson 8 — the tables are the only source of these
cases. An implementation passes them with its own function, without a stand. `keys_sealed` and the content of
`sealed` require the public content-probe sequences in [production obligations](../vectors/production-obligations/README.md); executable bindings remain Runner-owned and NOTEXEC until supplied.

The command `seal-member` takes `{seed, sealed}` and returns `{result: ok, plain}` or `{result: refused, reason}`. The command `seal-member-round` takes `{key, seed, plain}` and returns `{result: ok, sealed: [<m1>, <m1>], opened: [<plain>, <plain>], distinct}`.

The canonical JSON (RFC 8785, ADR-0072) on which the contract rests is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → RFC 8785 form → sha256; ADR-0083 addendum (33) item 2).


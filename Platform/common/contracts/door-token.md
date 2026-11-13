# The door token contract: the bytes `door1`, claims in JCS, an Ed25519 signature, the keys `door/keys`, the check at the holder

This English text is the source; the Russian translation `ru/contracts/door-token.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5) and addendum (11): a contract that one process writes and others read
lies in `Platform/common/`; analysis of the review of stage B 3–5, V1). The owner is lesson [P/06](../../06-console/spec/06.5-console.norms.md)
(chapter 6.5): the console issues the token in the answer of `/where/<id>` and `/where/<table>/<place>` (P/06.5 N3), holds the signer
`door/signer` and writes the public keys `door/keys`. Readers: the door holder — the worker that checks the token at its door
(chapter [P/03.4](../../03-worker/spec/03.4-worker.norms.md) N3 «the door token at the holder», P/03.4-08); the domain agent reads
`door/keys` ([the catalogue](../data/catalog.tsv)). Moved from P/06.5 N3 «`/where/<id>`» (the block «Door token — bytes»: `token`
and the row `door/keys`) and P/03.4 N3 «the door token at the holder» (the row `door/keys` about the checker and the phrase of «Races») without
a change of behaviour; after the move the check was changed — the changes of behaviour: the Architect's decisions of 2026-10-20 (ADR-0083
addendum (12): strict base64url, a closed composition and types of the claims, the segment `routes` by `name`, the whole sign of `expires`, a single
refusal `forbidden`) and the analysis of the review of stage B 6–7 (№ 10 — a whole `expires`, № 12 — a strict Ed25519 check); the implementations
are reconciled by the vectors `door-token` (analysis of the review of stage B 6–7, № 11). When and to whom the console issues a token (by `view` on a unit, TTL [DOOR_TOKEN_TTL](../../06-console/forms/runtime-constants.tsv), the journal `door.issued`, the field `door`
of the answer), the signer `door/signer` and its envelope are in the owner's norms (P/06.5 N3, the family
[`door-signer`](../../06-console/data/door-signer.schema.json)); the form of the keys row is the owner's family
[`door-keys`](../../06-console/data/door-keys.schema.json) with the outcome table next to it. JCS is RFC 8785 (ADR-0072; the vectors
[`jcs`](../vectors/jcs/README.md) of the common JCS contract).

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

The files by which the contract works (layout audit, V-15–V-17; the Architect's decision of 2026-10-25):

- the signer `door/signer` — the family `door-signer`: `Platform/06-console/data/door-signer.schema.json`,
  `Platform/06-console/data/door-signer.outcomes.tsv`;
- the keys row `door/keys` — the family `door-keys`: `Platform/06-console/data/door-keys.schema.json`,
  `Platform/06-console/data/door-keys.outcomes.tsv`;
- the holder's heartbeat (`instance` for `claims.holder`) — the family `heartbeats`: `Platform/03-worker/data/heartbeats.schema.json`,
  `Platform/03-worker/data/heartbeats.outcomes.tsv`;
- the issue of the token in the answers of `/where/{id}` and `/where/{table}/{place}` (the field `door`) —
  `Platform/06-console/spec/06-console.api.openapi.yaml`.

## Token

From P/06.5 N3 «`/where/<id>`», «Door token — bytes» (the cammeta-go journal, lesson 9 № 3):

```yaml
token:      door1.<kid>.<claims>.<sig> — exactly four parts separated by «.», ASCII
  kid:      the name of the signing key, 1–32 characters [a-z0-9-]; by it the checker takes the public key from door/keys
  claims:   base64url without «=» of the JCS (RFC 8785) bytes of the object {user, unit, holder, routes, expires}: user — the proven name
            ([the gate-and-pass contract](gate-and-pass.md) «The gate» identity), unit — "<sub>/<id>", holder — the holder's instance from its heartbeat (instance, P/03.4 N1.1), routes — an array
            of the routes door.routes of the manifest with the admission token (name elements and {name} without role and domain; routes with role or
            domain do not enter the token — their admission is the role certificate, the class mixed of the role certificate contract, or the domain token,
            P/03.4 N1.7; ADR-0091 addendum (8) item 3, addendum (14) item 1) and with a rank allowed to the person on the unit (P/06.5 N3 «/where/<id>»; ADR-0115 addendum (19) item 1), expires — the whole wall seconds of the issue + DOOR_TOKEN_TTL (analysis of the review of stage B 6–7, № 10): floor(now) + DOOR_TOKEN_TTL, now — the wall clock
            of the issuer in seconds, the fraction is dropped, not rounded (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7)
  sig:      base64url without «=» of the 64 bytes of an Ed25519 signature (RFC 8032) over the ASCII bytes «door1.<kid>.<claims>»; the check is strictly
            by RFC 8032 §5.1.7: S outside 0 ≤ S < L, R or the public key not decoded — a refusal (analysis of the review of stage B 6–7,
            № 12; the vector sig_s_not_reduced); the equation is without the cofactor: [S]B = R + [k]A (like Go crypto/ed25519 and OpenSSL),
            not [8][S]B = [8]R + [8][k]A; A or R of small order ([8]P is the neutral point) — a refusal, although the equation
            holds (the vectors key_small_order, sig_r_small_order) (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7)
```

On issue, `claims.routes` preserves the order of the selected routes in the manifest's `door.routes`.

The parts `claims` and `sig` are strict base64url without «=» (the alphabet `A–Z a–z 0–9 - _`, without «=» and other characters; the unused trailing bits of the last character are zeros); a part not
by this grammar is a check refusal (the Architect's decision of 2026-10-20, the vectors door-token). A non-zero trailing bit is a refusal too, although a non-strict
decoder would give the same bytes (the Architect's decision of 2026-10-20, the vectors door-token). The issuer is to write the claims as JCS bytes;
the checker does not check the JCS canon: the signature covers the bytes of the claims part, and a repeated canon at the checker would give
a second source of divergences (the Architect's decision of 2026-10-20, the vectors door-token).

## Keys `door/keys`

From P/06.5 N3 «`/where/<id>`» (the writer's side) and P/03.4 N3 «the door token at the holder» (the checker's side):

```yaml
door/keys:  {<kid>: <64 lowercase hex of the public key>} — a non-secret row; the console adds its own kid when it creates
            door/signer, at start and at issue, if it is not there (P/06.5 N3; analysis of the review of stage B 6–7, № 3); another value under
            its own kid the console does not overwrite: the token is not issued, the alarm door.keys_conflict (P/06.5 N3, N4; (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7)); the checker: four parts, door1, kid in door/keys, the signature, claims exactly {user, unit, holder,
            routes, expires} with the types by the contract, now < expires, unit and holder — its own, the first segment of the URL path of the request to the door
            of the holder (without query) — an element of routes byte for byte, raw — otherwise a refusal of the holder's door: 403 {"error": "forbidden"} without a reason
```

The composition of the claims is closed: an extra field or the absence of any of the five, `user` included, is a refusal (the Architect's decision of 2026-10-20, the vectors door-token).
The types of the claims are closed: `user`, `unit`, `holder` are JSON strings; `routes` is an array of JSON strings, the elements are segments by
the grammar of `door.routes` (P/02.1, `strList`), without repetitions; `expires` is a JSON integer, seconds, not greater than 2^53−1. Another type,
a fractional or greater `expires`, a repetition in `routes` — a refusal 403 `{"error": "forbidden"}`, even with a correct signature (the Architect's decision of 2026-10-20, Kimi SB67-01).
An element of `routes` is a segment by the grammar of `name` `[a-z][a-z0-9_-]{0,31}`, without «/» ([P/02.1](../../02-installer/spec/02.1-installer.norms.md)
N1 «Form», `door.routes`); `read/x` or `Read` is a refusal (the Architect's decision of 2026-10-20). A JSON integer is only a notation without a dot
and an exponent, like the whole sign of the family writer ([layers V7](../LAYERS.md) § 3, `x-whole`): `1792454520.0` and `1.79245452E9` in the bytes of the
claims are a refusal, although the value is whole (the Architect's decision of 2026-10-20).
The checker reads the text of the claims by I-JSON (RFC 7493): the bytes are strict UTF-8 (an invalid sequence is a refusal, not
a replacement with U+FFFD); a field name twice is a refusal, not «the last value»; names are compared byte for byte (`User` is not `user`:
there is no field `user` — a refusal) (analysis of the review of stage B 6–7, № 8; ADR-0083 addendum (12)); in strings and names there are no surrogates (a lone
surrogate written as `\uD800` is a refusal, although the bytes are valid UTF-8) and no noncharacters (U+FDD0–U+FDEF, U+xFFFE, U+xFFFF — a refusal) (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7).
**The place of the token and the path** (analysis of the review of stage B 6–7, № 9; ADR-0083 addendum (12)). The holder takes the token from the header
`Authorization: Bearer <token>`, and if there is no such header — from the query parameter `t` (`?t=<token>`: the element `<video>`
does not set headers, lecture M10B/24). An `Authorization` header with another scheme is as if absent (then `?t=`);
the parameter `t` twice or more is a refusal; neither Bearer nor `?t=` is a refusal; with Bearer the query is not read (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7). «The request path» is the URL path without the query: «?» and everything after it do not enter the path; for
`/play?t=…` the segment is `play`. HTTP details (guess of stage C DT-G01, the Architect's decision of 2026-10-23): the scheme `Bearer` is ASCII case-insensitive,
between the scheme and the token — SP or HTAB; an `Authorization` header with the scheme `Bearer` is present, even an empty one — the query is not
read; the query is URL-decoded; a damaged query (`%` without two hex digits), a repetition of `t`, several
`Authorization` headers — 403 `{"error": "forbidden"}`. The query is the form `application/x-www-form-urlencoded` strictly (DT-G02): fields
separated by `&`, the name and the value — by the first `=`, `+` is a space, `%XX` and UTF-8 — strictly (an invalid one — 403 `forbidden`), a field without
`=` is an empty value, `;` is an ordinary character. The vectors are the rows of `verify.tsv` with a query, DT-G01 and DT-G02.

**The place token** (ADR-0091 addendum (7) item 2, addendum (8) item 9). The place door (`/where/<table>/<place>`, P/06.5 N3): the `unit` of the token is
a unit whose data lie in the place of the holder, not necessarily held by it; the rule «`unit` and `holder` are its own» for the place door
reads so: `holder` is its own, the data of `unit` lie in its place, otherwise 403 `{"error": "forbidden"}`. The vectors are `place.tsv`.
The list of units of a place is built by the subsystem; the check compares `unit` with the list, not with the bytes. The data of a unit have not landed yet — the unit is not in the place, 403; except a door whose norm of the subsystem lesson names the unit as lying in the place before the data: then the unit is in the list, and the absence of data is told by the answer of the door itself (DT-PLACE-NOT-YET-01, the Architect's decision of 2026-11-01, analysis of the VMS pass).
The request path is compared by its first segment: for `/read/x` the segment is `read`; `/reader`, `/x/read` and `/` are not equal to the element `read`
(the Architect's decision of 2026-10-20, the vectors door-token). The segment is compared raw, without decoding `%XX`:
`/re%61d/x` is not equal to the element `read`; any divergence is a refusal, not a bypass (the Architect's decision of 2026-10-20, the vectors door-token). The refusal is one outcome for all causes: the holder's door answers 403 with the body
`{"error": "forbidden"}` without a reason (the Architect's decision of 2026-10-20, the vectors door-token) ([P/03.4](../../03-worker/spec/03.4-worker.norms.md) N4), the order of checks is not normed. So
the client does not learn which check failed, and the implementations do not diverge in the order of checks (the Architect's decision of 2026-10-20, the vectors door-token).

An unreadable row `door/keys` is an outcome of the owner's family ([`door-keys.outcomes.tsv`](../../06-console/data/door-keys.outcomes.tsv)):
at the holder — the `kid` of the token is not found, a refusal of the door (403 `forbidden`). The unit of unreadability is the whole row: an entry of another
`kid` out of form (the key is not 64 lowercase hex) makes the whole row unreadable, and a token with its own, correct `kid` also gets
a refusal — the checker does not read the row by entries (analysis of the review of stage B 6–7, № 8).

**Races.** The answer names the observed holder; a move can complete before the door is used, and the answer does not extend
the lease. The validity of the operation is checked again by the holder by epoch/lease: a holder that changed after the answer
is cut off by the epoch/lease check at the door (from P/06.5 N3 «`/where/<id>`», «`/where/<table>/<place>`» «Races» without change;
layout audit B-21, the Architect's decision of 2026-10-25).

## Vectors

The package [`door-token`](../vectors/door-token/README.md) (the Architect's decision of 2026-10-20, analysis of the review of stage B 3–5):
the issue (`issue.tsv`: the seed of `door/signer`, `kid`, claims → JCS bytes and `token`) and the check at the holder (`verify.tsv`: the row
`door/keys`, `token`, `now`, its own `unit` and `holder`, the request path → `ok` or `forbidden` by the check list above). An implementation
passes them with its own function, without a stand; at the stand the check by the holder remains a reading (P/06.5-05, P/03.4-08: the stand has no
holder door that checks the token).

The stand command `door-token-verify` of the profile `03-worker` (P/03.4 N5) gets the path of a file with one JSON object: for `verify.tsv` `{keys, authorization, now, unit, holder, path}`, for `place.tsv` `{keys, authorization, now, holder, path, place_units}`. `keys` is the value of the row `door/keys` as JSON, `authorization` and `path` are strings byte for byte, an empty `authorization` means no header, `now` is a number, `place_units` are the units whose data lie in the holder's place. stdout is exactly one JSON object in UTF-8 and LF: `{"result":"ok","claims":{…}}` with the read claims or `{"result":"forbidden"}`, code 0. An input not of this form gets code 2.

The stand command `door-token-issue` of the profile `06-console` (P/06.5 N3) gets the path of a file with one JSON object of exactly `{seed_hex, kid, now, claims}` of a row of `issue.tsv`: `seed_hex` and `kid` are the strings of the row, `now` is a number, `claims` is the JSON text of the row as it is: the order of fields, `routes` and the notation of numbers are not re-derived, and the form of the checking side does not apply to issuing. The seed, `kid` and the time are from the row, not from the clock or the stand's own secrets. An input not of this form — not an object, a missing, extra or repeated field, a wrong type, or `seed_hex`, `kid`, `claims` not by the issuing contract — gets code 2 and an empty stdout; there is no refusal of issuing with code 0. Code 0 means computed: stdout is exactly one JSON object and LF, `{"claims_jcs": …, "token": …}`, both fields byte for byte with the columns of `issue.tsv`, without the envelope `result`; the first byte is `{`, after the object — LF and the end; formatting inside the object is allowed; extra fields, bytes, CRLF or whitespace around are a FAIL of the row; service output goes to stderr.

The canonical JSON (RFC 8785, ADR-0072) on which the contract rests is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → RFC 8785 form → sha256; ADR-0083 addendum (33) item 2).


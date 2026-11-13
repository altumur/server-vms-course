# The domain token contract: the form, `TOKEN_SKEW`, the check `token` with `expect`, refusal words

This English text is the source; the Russian translation `ru/contracts/domain-token.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5) and addendum (11): a common contract can appear before the move of the
owner lesson if an already moved lesson relies on it; analysis of review of stage B 3–5, V1). The owner is lesson P/08,
chapter 8.2 ([norms](../../08-domain/spec/08.2-domain.norms.md)):
the process `domain` issues tokens and keeps the set `domain/keys` and the revocations `domain/revoked` (P/08.2 N1.2, N1.3, N1.6), the meaning
and the issue stay with the owner. Readers: the gate of the cluster console — the identity by the token
([P/06.3](../../06-console/spec/06.3-console.norms.md) N1.3, N1.8), the worker and the member's door — the recipient of a kind token (chapter
[P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.5, N3 «check at the recipient»), the worker token door ([chapter 8.7](../../08-domain/spec/08.7-domain.norms.md)),
the process `domain` — the people doors and `/domain/revoke` ([chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) N1.2, N3
«people door»), the domain console — the gate by the [gate-and-pass contract](gate-and-pass.md) ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.5) (analysis of
review of stage A 8–10, № 16). Moved from M11/2 N1.6 (the row `token` with `header`,
`payload`, `sig`, the constant `TOKEN_SKEW`, the paragraph about who checks), N3 «`token(keys, revoked, now, token)`» (the steps with
`expect` and the paragraph about the boundary) and the rows of N4 about the token without a change of behaviour. What is common to the forms of chapter 8.2 (hex, canonical
base64url, JCS — RFC 8785, ADR-0072, «wall-clock seconds», Ed25519 — RFC 8032, completeness of JSON forms, a repeated key) —
the [domain founding contract](domain-founding.md) «Common rules of forms» (layout audit, B-03); the set `domain/keys`
(`keys`, `until`), the form of the row `domain/revoked`, its writers and `prune` — the [domain key set contract](keys.md) (analysis of
review of stage A 8–10, № 13); the offline revocation window — P/08.2 N1.7. The kind of a worker token
and `audience_claim` — the kind declaration of [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.2b (the late layer),
the claims of the token — [chapter 8.7](../../08-domain/spec/08.7-domain.norms.md). The reference «lesson N»
in the moved text is lesson M11/N, their addresses now: «lesson 7» (the worker token) — P/08.7, «lesson 9» (the person token) —
P/08.4 (analysis of review of stage B 8–10, № 22); «N1.x» in the steps — the chapters of P/08.2 (formerly of lesson M11/2; the numbers of the subsections are the former ones).

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The function `token` reads `domain/keys` and `domain/revoked`: `Platform/08-domain/data/keys.schema.json`, `Platform/08-domain/data/keys.outcomes.tsv`; `Platform/08-domain/data/revoked.schema.json`, `Platform/08-domain/data/revoked.outcomes.tsv`; the kind declaration and `audience_claim` — `Platform/02-installer/spec/02.1-installer.schema.json` (layout audit, V-14, B-32; the Architect's decision of 2026-10-25).

## The token

From M11/2 N1.6:

```yaml
token:         <b64url(header)>.<b64url(payload)>.<b64url(sig)>       # exactly three parts
  header:      a JSON object; required: alg — the string "EdDSA", kid — a string; other fields are skipped (not a refusal);
               the issuer writes exactly {alg, kid} in JCS
  payload:     a JSON object; required: iat, exp — finite numbers, wall-clock seconds; jti — a string 1–64 [A-Za-z0-9_-];
               kind — a non-empty string: person for people (lesson 9), a manifest kind for workers (lesson 7); other fields are skipped
               by this lesson, except the audience field of the kind (P/02.1 N1.2b audience_claim; analysis of review of stage B 6–7, № 24) at a check by the recipient; the issuer writes
               JCS and jti — 16 hex characters from random 8 bytes, except the kinds keep with a live row domain/issued (P/08.2 N1.6a)
  sig:         Ed25519 of the key kid of the set over ASCII «<header>.<payload>» as received
TOKEN_SKEW:    60          # s, the clock tolerance in both directions; the clock is the wall clock of the checker
person:        a person token: the issuer (the process domain at login, P/08.4 N1.2) writes exactly {iss: <the domain>, sub: <the name
               of the person>, kind: "person", iat, exp, jti}, without aud; exp = iat + TOKEN_LIFETIME; the checker skips other fields
               (item payload), it checks sub by the form of a person name — [the person name contract](../person-name.md) `name` (1–64 characters without
               whitespace, control characters and : | ( ) " /, not break-glass; layout audit A-20) — otherwise 401 at the gate
               (guess of stage C GP-L01, the Architect's decision of 2026-10-23)
```

The check of a token is the function `token` (the section «The check» below) at each door that accepts domain tokens; each
such door MUST pass `expect` below, except the one named without it (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 7; analysis of review of stage A 8–10):

| Checker | Where | `expect` |
|---|---|---|
| the gate of the cluster console | [the gate-and-pass contract](gate-and-pass.md) «The gate» `identity` item 3; [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.3, [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.9 `cluster` | `{kind: person, cluster: null}` |
| the gate of the domain console (P/10 N1.5; the right — the row `domain` of P/08.4 N1.5) | the same contract, `identity` item 3 | `{kind: person, cluster: null}` |
| the process `domain`, the people doors | [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N3 «people door» step 2 | `{kind: person, cluster: null}` |
| the recipient of a kind token — a worker or a member's door | [P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.5, N3 «check at the recipient» | `{kind: <kind>, cluster: <own cluster>, audience_claim: <from the kind declaration>, keep: <kinds keep: true of the catalogue>}` |
| a worker, the door `door.pass` of the first kind: checks the credentials passed by the cluster console | [the gate-and-pass contract](gate-and-pass.md) «Pass of `door.pass`» `rule` | `{kind: person, cluster: null}` |
| the process `domain`, `POST /domain/revoke` | P/08.4 N1.2 `revoke` | `expect {kind: person, cluster: null}`: the token in the body is a credential of oneself, the tokens of the kinds with `keep` are revoked by `DELETE /domain/issued`, a kind without `keep` lives until `exp`: a limit (ADR-0110 addendum (16) item 1) |
| the door of a subsystem process, a route with `domain` | [P/03.4](../../03-worker/spec/03.4-worker.norms.md) N1.7 `door_admission` `domain`, `role_domain` | `{kind: [<kinds of the route>], cluster: <own cluster>, audience_claim: {<kind>: <field from the kind declaration>}, keep: [<kinds keep by the manifest that declared the kind>]}` (ADR-0091 addendum (17) item 9, addendum (18) item 1, addendum (19) item 1) |

The worker token door (lesson 7) issues tokens and does not check them. A subsystem worker on the domain does not check the person token of an incoming
`door.pass`: people are checked by the gate of the domain console, the worker accepts the source of the request by the role
`domainconsole` of the TLS client ([P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.6 `door_client`; the Architect's decision of 2026-10-20 on the reconciliation of 3.7). The kind of the token and `aud` — lesson 7: a token of another cluster or kind
is refused at the recipient, by steps 9–10 of this contract.

## The check: `token(keys, revoked, now, token) → ok payload | refused <word>`

From M11/2 N3; `keys` is the accepted set ([the domain key set contract](keys.md) «The set»), `revoked` is the row
`domain/revoked` as read (the form — [the domain key set contract](keys.md) «Revocations»), `now` is the wall-clock seconds of the
checker:

```
1. revoked exists and is not in the form of N1.6 (not {jtis: string}; an entry not «<jti>:<number>»; the number is finite, by the grammar of
   JSON without spaces: `0123`, `1e400`, `+1` — out of form; added by the M11 reconciliation, T2, T3) → refused no_revocations
2. token is not a string; not three parts; a part is not base64url; header or payload is not a JSON object or has a repeated key;
   header.alg ≠ "EdDSA"; header.kid is not a string                              → refused not_a_token
3. kid ∉ keys.keys                                                               → refused unknown_key
4. the signature does not verify with keys.keys[kid] over ASCII «<header>.<payload>» → refused bad_signature
5. iat or exp is not a finite number, jti is not a string by the grammar of N1.6, kind is not a non-empty string → refused bad_claims
5a. kid ∈ until, now > until[kid] and not (kind ∈ expect.keep and now ≤ keep_until[kid]) → refused unknown_key   # after the signature: kind is signed, it cannot be judged earlier; a foreign signature on an expired key — bad_signature (ADR-0110 addendum (10) item 3)
6. now > exp + TOKEN_SKEW                                                         → refused expired
7. now < iat − TOKEN_SKEW                                                         → refused future
8. jti in revoked                                                                 → refused revoked
9. expect exists and kind ≠ expect.kind (a string) or kind is not from expect.kind (a list) → refused wrong_kind
10. expect exists, expect.cluster is not null and the audience field (expect.audience_claim; for a list of kinds — the value of
    the map for the kind matched at step 9; no entry or no audience_claim — aud) is not a list of strings or is without
    expect.cluster                                                                → refused wrong_audience
11. otherwise                                                                     → ok payload
# expect — what the checker expects (the table «The token» above): the kind and its own cluster; for people's tokens the cluster is null
# (person without an audience, lesson 9): the audience is not checked
```

«N1.6» in steps 1 and 5 is M11/2 N1.6 (now P/08.2 N1.6): the form of `domain/revoked` (step 1; now — [the domain key set contract](keys.md) «Revocations») and the grammar of `jti` (the section «The token» above, step 5). The form of
`expect` is the input of the command `token` ([P/08.2](../../08-domain/spec/08.2-domain.norms.md) N5): `expect?: {kind: <row> | [<row>…], cluster: <member> | null, audience_claim?: <field
name — a non-empty string, default aud> | {<kind>: <field name>}, keep?: [<kind>…]}`; `keep` is the kinds with `keep: true` of the manifest, no field — empty. `kind` as a string — one kind, `audience_claim` with it — a string;
`kind` as a list — non-empty, without repeats, without `person`, `audience_claim` with it — a map, the keys are kinds from the list (a kind without
an entry — `aud`); another combination, `person` in the list, a key of the map not from the list — out of form, code 2 (ADR-0091 addendum (18)
item 1, addendum (19) item 1). The key `cluster` is required; `null` is allowed only with `kind: person` as a string. `expect`
without the key `cluster` or with `cluster: null` at another `kind` is out of form: this is an error of the caller, not a refusal word
(the command `token` — code 2, P/08.2 N5). `expect` is the closed form `{kind, cluster, audience_claim?, keep?}`: an unknown key is also
out of form, code 2 (the typo `audience_clam` would otherwise silently return the check to `aud`; guess of stage C DT-G03, the Architect's decision of 2026-10-23). There is no default «without `cluster` the audience is not checked»: it would weaken
the cut-off by audience (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 7; analysis of review of stage A 8–10).

Equality at the boundary accepts: `now = exp + 60` is still `ok`. `revoked` is absent (there is no row) — there are no revocations. A door
at which `domain/revoked` exists but is not read by the store answers as at `no_revocations`: nothing to check with (503 `{error: "unavailable"}` at the
gate — the rule «Unreadable row» of the gate-and-pass contract, [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.3; the Architect's decision of 2026-10-28 on the reconciliation ddc9bee1e), not «the token is valid».

## Refusal words

From M11/2 N4 (the rows about the token):

| Reason | Outcome | Who sees it and how | What the caller does |
|---|---|---|---|
| token: `no_revocations` | 503 `{error: "unavailable"}` at the gate and at the doors of the process `domain` ([P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.5; the rule «Unreadable row» of the gate-and-pass contract) and at the self-check of an issued token at the token door | the caller | wait for a readable row |
| token: `not_a_token`, `unknown_key`, `bad_signature`, `bad_claims`, `expired`, `future`, `revoked`, `wrong_kind`, `wrong_audience` | 401 at the gate ([P/06.3](../../06-console/spec/06.3-console.norms.md)); the self-check of an issued token at the token door — 503 `unavailable` (lesson 7) | the caller | log in again / get a new token; `future` — check the clock |

At the recipient of a kind token (P/03.7 N4) — `wrong_kind`, `wrong_audience` (steps 9–10). At the door of a subsystem process, a route with
`domain` (P/03.4 N1.7, N4): the words of steps 1–8 — 401 (`no_revocations` — 503), no token — 401 `not_a_token`; `wrong_kind`,
`wrong_audience` — 403; the body `{error, detail}` (ADR-0091 addendum (14) item 2, addendum (17) items 3, 8).

## Vectors

The package [`domain-token`](../vectors/domain-token/README.md) (owner P/08.2; the move of lesson 8): 53 lines — 29 inputs of the command
`token` of the acceptance of M11/2 (`inputs/token-*.json`, sc. 04–07, 12 — the key and `until`, the form, the boundary `exp + 60` and `iat − 60`,
revocation, `expect`) without a change of bytes; the scenarios and the inputs were removed by the move of lesson 8 — the table is the only source of these
cases; 3 lines of the form `expect` and 11 lines of the list of kinds (ADR-0091 addendum (18) item 1, addendum (19) item 1) — by the text of the contract; 2 lines
of an input out of form (`audience_claim` empty, `keys` without `current`; coverage audit of P/08, the second pass of Gemini) — by the output of the witnesses; 8 lines
of the kinds `keep` (`token-keep-*`, ADR-0110 addendum (10), addendum (12) item 1) — by the text of the contract.
An implementation passes them with its own function, without a stand.

The canonical JSON (RFC 8785, ADR-0072) on which the contract relies is the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the form RFC 8785 → sha256; ADR-0083 addendum (33) item 2).


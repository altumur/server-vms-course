# Vectors of the door token: case data and coverage

This English text is the source; the Russian translation `ru/vectors/door-token/README.cases.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of [the door token contract](../../contracts/door-token.md): the issuing of `door1.<kid>.<claims>.<sig>` (claims in JCS, the signature
Ed25519) and the check at the holder by the row `door/keys`. The owner of the contract is lesson P/06, chapter
[6.5](../../../06-console/spec/06.5-console.norms.md) (N3 «`/where/<id>`»: the console issues the token); the checker is the holder
of the door, chapter [3.4](../../../03-worker/spec/03.4-worker.norms.md) N3 «the door token at the holder» (P/03.4-08). The package is common:
one process writes the algorithm, others read (the Architect's decision of 2026-10-20, the review analysis of stage B 3–5: an Ed25519 signature
without vectors is a silent divergence of implementations). The bytes are written by «Specification» (ADR-0083); the conformance of the product is by its
acceptance against these tables (ADR-0080 addendum 16).

## Run

Without a stand: the console runs `issue.tsv` through its issuing function, the holder runs `verify.tsv` through its check function, and `place.tsv`
(the command `door-token-verify`; ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26). The time is by the input `now` (wall seconds), not by the process clock.

- `issue.tsv` — issue(`seed_hex`, `kid`, `claims`) gives `claims_jcs` and `token` byte for byte. Ed25519 (RFC 8032)
  is deterministic: the same seed and the same string give the same signature.
- `verify.tsv` — check(`keys`, `authorization`, `now`, `unit`, `holder`, `path`) gives `ok` and the read claims, equal
  to the column `claims` by JSON value (not by text), or `forbidden` (the reading of the commits of «cammeta-acceptance» 2026-10-20).
Who performs is by the table: `issue.tsv` — the console (`06-console`, issues the token in `/where/<id>` and `/where/<table>/<place>`, P/06.5 N3); `verify.tsv` and `place.tsv` — the worker (`03-worker`, the holder of the door checks the token, P/03.4 N3 «the door token at the holder», N1.7 `door_admission` `token`). The console does not check the token, the worker does not issue it; the domain agent does not read `door/keys` (the catalogue: the readers are the console and `<s>worker`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Stand command `door-token-issue`

The key `stand` of the profile `06-console` (the section «Layout by processes» of [the common acceptance README](../../acceptance/README.md);
chapter 6.5 N3): a template with `{input}` — the path of a file with an object of exactly `{seed_hex, kid, now, claims}` of a row of `issue.tsv`:
`seed_hex`, `kid` — the strings of the cells, `now` — the number of the cell, `claims` — the lexeme of the cell as it is (the order of fields, `routes` and
the numeric lexemes are not re-derived; the row `number_form` with an exponent at `expires` is a valid input of issuing, the form of the checking
side does not apply to issuing). The seed, `kid` and the time are from the row, not the clock and not the stand's own secrets. The answer is exactly
`{"claims_jcs": <row>, "token": <row>}`, both fields byte for byte with the columns of the table. An input not of the form: not an object,
a missing, extra or repeated field, a wrong type, `seed_hex`, `kid` or `claims` not by the issuing contract; there is no refusal
of issuing with code 0 — the published rows are computable. stdout is exactly one JSON object and LF: the first byte is `{`, after the object — LF and the end; extra fields, bytes, CRLF, whitespace around — FAIL of the row; formatting inside the object is allowed; service output goes to stderr. Code 0 — computed; an input not of the form — code 2, stdout empty. There is no envelope `result` (the guess of stage C C06-F2-IO-02, the Architect's decision of 2026-10-23).

## Stand command `door-token-verify`

The key `stand` of the profile `03-worker` (the section «Layout by processes» of [the common acceptance README](../../acceptance/README.md);
P/03.4 N5): a template with `{input}` — the path of a file into which the runner writes one JSON object of the input of a row: for `verify.tsv` —
`{keys, authorization, now, unit, holder, path}` (`keys` — the value of the column as JSON, `authorization` and `path` — strings
byte for byte, an empty string `authorization` — there is no header, `now` — a number), for `place.tsv` — the cell `input` as it is
(`place_units` instead of `unit`; the column `claims` — as for `verify.tsv`). stdout is exactly one JSON object in UTF-8 and LF: `{"result":"ok","claims":{…}}` — the claims
of the read token, compared with the column `claims` by JSON value, — or `{"result":"forbidden"}`; code 0. An input not of
this form — code 2. Another code, another `result`, extra fields or bytes — FAIL of the row (the guess of stage C W03-E04, the decision of
the Architect of 2026-10-23).

## Keys

The Ed25519 seed is 32 bytes `sha256("w2c test <word>")` (as the keys of [the sealing vectors](../sealing/README.md)); the tables do not name the words
of derivation — the seed and the public key are fixed as bytes, an implementation takes them from here and does not derive them
anew (`SA67-B3`). The seed is what the row `door/signer` holds in `seed_secret` (64 lowercase hex); the public key is the value
of the row `door/keys` under the same `kid`.

| kid in the vectors | seed_hex | public key (door/keys) |
|---|---|---|
| `c1` | `72207cdee579aae6185325025d5d4f82594247e8301c16b85909b5c363c2b8a9` | `865e70360600cb7dd29abc35426a83480f2d4039240f75d4d1ba2bcf894ea0db` |
| `c2-0123456789-abcdefghijklmnopqr` | `8e94e9035d25f0d2247b327ad5337ada38f934acd24c03e1aad23b4742f7f21a` | `3a42558c6b12b6e1dbcfc146e59401bffa3bd524e151493b65e2817e248d2428` |
| — (a forgery) | `cc7b7d5d5b400b7efbf2053fae514d14d8daf638546d30bee836e95d671159ea` | `b3bfa2c840017b6309526eed5e4c0285630ab9b9db612d503afd1961cd3ae146` |

The third seed signs the row `forged_signer`; its key is not in the `door/keys` of the vectors.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header; `case` is the name of the row,
`note` is what the row is for.

| File | Input → expectation |
|---|---|
| [`issue.tsv`](issue.tsv), 7 rows | `seed_hex`, `kid`, `now`, `claims` — an object `{user, unit, holder, routes, expires}` as JSON text, as passed to the issuer (`expires` = `now` + 120) → `claims_jcs` — its RFC 8785 form (UTF-8), `token` — `door1.<kid>.<base64url without «=» of claims_jcs>.<base64url without «=» of the signature over ASCII «door1.<kid>.<claims>»>`. Cases: an ordinary one, the order of fields (the same token), the order of `routes` (an array is not sorted), Cyrillic and a character outside the BMP, escaping, a number with an exponent, a `kid` of 32 characters |
| [`verify.tsv`](verify.tsv), 89 rows: 17 `ok`, 72 `forbidden` (5 — DT-G01, 6 — DT-G02; a separator HTAB and several headers `Authorization` cannot be expressed by a TSV row — by reading) | `keys` — the value of the row `door/keys` as JSON text; `authorization` — the header `Authorization` whole, empty — there is no header (formerly the column `token`; at most rows — `Bearer <token>`; (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7)); `now`; `unit`, `holder` — the holder's own (`unit` — `<sub>/<id>`, `holder` — the `instance` of its heartbeat); `path` — the target of the request to the holder's door: the URL path, at some rows with a query (`?t=<token>`); the first segment of the URL path without the query is compared with the elements of `routes` (the review analysis of stage B 6–7, № 9) → `ok` and `claims` (the text of the claims part) or `forbidden` (the column `claims` is empty) |
| [`place.tsv`](place.tsv), 4 rows: 2 `ok`, 2 `forbidden` | `input` — `{keys, authorization, now, holder, path, place_units}`: `place_units` — the units whose data lie in the holder's place, the list is built by the subsystem (the data have not landed yet — there is no unit, unless the door norm named it, DT-PLACE-NOT-YET-01); the place token is the contract «The place token» (ADR-0091 addendum (7), (8)) → `expect` and `claims` — the read claims at `ok` as JSON text, compared by value; at `forbidden` empty (the reading of «cammeta-acceptance» 2026-10-23) |

## Refusals

A refusal of the check is one word `forbidden`, the answer of the holder's door 403 with the body `{"error": "forbidden"}` without a reason ([P/03.4](../../../03-worker/spec/03.4-worker.norms.md)
N4, [the contract](../../contracts/door-token.md) «Keys `door/keys`») (the Architect's decision of 2026-10-20, the vectors door-token). The order of the checks
the vector does not fix: the reason is not visible in the answer. The refusal rows are by the check list of the contract:

| Check of the contract | Rows |
|---|---|
| four parts | `three_parts`, `five_parts`, `token_empty` |
| `door1` | `prefix_door2`, `prefix_upper` |
| `kid` in `door/keys` (an unreadable row — `kid` is not found, [the outcome of the family](../../../06-console/data/door-keys.outcomes.tsv)) | `unknown_kid`, `empty_keys`, `keys_upper_hex`, `keys_short_hex`, `keys_not_object`, `keys_bad_other_entry` (a foreign entry not of the form — the whole row is unreadable; the review analysis of stage B 6–7, № 8) |
| the signature — strictly by RFC 8032 §5.1.7, including `0 ≤ S < L` (the review analysis of stage B 6–7, № 12) | `foreign_key`, `forged_signer`, `sig_bit`, `sig_last_bit`, `sig_short`, `sig_s_not_reduced`, `claims_swapped`; without the cofactor, A or R of small order — a refusal (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7): `key_small_order`, `sig_r_small_order` |
| the parts — strict base64url without «=», the trailing bits of the last character are zeros | `sig_padded`, `claims_padded`, `claims_std_base64`, `sig_trailing_bits`, `claims_trailing_bits` |
| claims exactly `{user, unit, holder, routes, expires}` | `extra_field`, `missing_user`, `missing_expires`, `missing_unit`, `missing_holder`, `missing_routes`, `claims_not_json` |
| the types of the claims: `user`, `unit`, `holder` — strings; `routes` — an array of strings without repeats; `expires` — an integer ≤ 2^53−1 (the Architect's decision of 2026-10-20, Kimi SB67-01) | `user_number`, `unit_number`, `holder_null`, `routes_not_array`, `routes_item_number`, `routes_dup`, `expires_string`, `expires_float`, `expires_over_2_53` |
| the text of the claims by I-JSON: strict UTF-8, a field name is not repeated, the names byte for byte (the review analysis of stage B 6–7, № 8); without surrogates and noncharacters (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7) | `claims_bad_utf8`, `claims_dup_key`, `claims_name_case`, `claims_lone_surrogate`, `claims_noncharacter` |
| the place of the token: `Authorization: Bearer`, otherwise a single `?t=`; another scheme — as if there were no header (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7) | `no_token`, `query_t_repeated`, `auth_not_bearer_no_query` |
| an element of `routes` is a segment by the grammar `name` `[a-z][a-z0-9_-]{0,31}`; a JSON integer — only a notation without a point and an exponent (the Architect's decision of 2026-10-20) | `routes_item_slash`, `routes_item_upper`, `expires_point_zero`, `expires_exponent` |
| `now < expires` (the boundary `now = expires` — a refusal) | `expired_boundary`, `expired_after` |
| `unit` and `holder` are its own | `other_unit`, `other_sub`, `other_holder` |
| the first segment of the request path, raw without decoding `%XX`, is an element of `routes` byte for byte; the path is without the query (the review analysis of stage B 6–7, № 9) | `route_not_in_routes`, `route_segment_prefix`, `route_second_segment`, `route_root`, `route_case`, `route_percent`, `route_query_only`, `route_in_query` |

The rows `ok_query_token` and `ok_query_one_segment` are a control of the path without the query: the token in `?t=`, the segment — before «?» (№ 9);
`ok_auth_not_bearer_query` — the scheme is not Bearer, the token is from `?t=`; `ok_bearer_over_query` — at Bearer the query is not read (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7). The row `ok_expires_max` is a control of the type boundary: `expires` = 2^53−1 gives `ok`. The row `claims_not_jcs` expects `ok`: the issuer is to write the claims in JCS, and the checker does not check the canon, because
the signature covers the bytes of the claims part (the Architect's decision of 2026-10-20, the vectors door-token).

The rows `key_small_order` and `sig_r_small_order` satisfy the equation [S]B = R + [k]A; the OpenSSL check (pyca cryptography) accepts them,
the refusal is given only by the condition of the contract «A or R of small order — refusal» (the Architect's decision of 2026-10-20, the review analysis of stage B 6–7).

The vectors were obtained by reference Ed25519 (RFC 8032) and JCS (RFC 8785, checked on [`jcs`](../jcs/README.md))
by the contract, not by the code of implementations; on a divergence the contract is right, the vector is corrected by «Specification».

## Vector wire

The wire of `issue.tsv`, `verify.tsv` and `place.tsv` is set by the `common/door-token` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.

## Source metadata

This English text is the source; the Russian translation `ru/vectors/door-token/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Source file `vectors/door-token/README.md`: [README](README.md).

# Vectors of the door token

This English text is the source; the Russian translation `ru/vectors/door-token/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The [door token contract](../../contracts/door-token.md) defines issuing `door1.<kid>.<claims>.<sig>` (JCS claims and an Ed25519 signature) and checking at the holder against `door/keys`. The console owns issuing in [P/06.5](../../../06-console/spec/06.5-console.norms.md), N3 `/where/<id>`; the door holder owns checking in [P/03.4](../../../03-worker/spec/03.4-worker.norms.md), N3 and N1.7 `door_admission` `token`.

## Run

Who performs: the console (`06-console`) passes issue inputs through its issuing function; the worker (`03-worker`) passes verification and place-token inputs through its checking function. The console issues in `/where/<id>` and `/where/<table>/<place>`; it does not check. The worker checks and does not issue. The domain agent does not read `door/keys`; the catalogue readers are the console and `<s>worker`. The time is input `now` in wall seconds, not the process clock.

Issuing takes `seed_hex`, `kid`, `claims` and produces `claims_jcs` and `token` byte for byte. Ed25519 (RFC 8032) is deterministic: the same seed and byte string give the same signature. Verification takes `keys`, `authorization`, `now`, `unit`, `holder`, `path` and returns `ok` with the read claims, or `forbidden`. Claims are compared by JSON value, not text.

## Stand command `door-token-issue`

The `stand` key of profile `06-console` ([common profile layout](../../acceptance/README.md), chapter 6.5 N3) is a template with `{input}`, the path of a file containing exactly `{seed_hex, kid, now, claims}`. `seed_hex` and `kid` are strings, `now` is a number and `claims` is the input JSON lexeme unchanged: field order, `routes` order and numeric lexemes are not re-derived. The checking-side numeric form does not constrain issuing. The seed, kid and time come from the input, not the clock or the stand's own secrets.

The answer is exactly `{"claims_jcs": <text>, "token": <text>}`. The contract defines the claims `{user, unit, holder, routes, expires}`, their JCS form and token encoding: `door1.<kid>.<base64url without «=» of claims_jcs>.<base64url without «=» of the signature over ASCII «door1.<kid>.<claims>»>`. An invalid input is not an object, has a missing, extra or repeated field, a wrong type, or `seed_hex`, `kid` or `claims` outside the issuing contract. There is no issuing refusal with code 0. Stdout is exactly one JSON object followed by LF: first byte `{`, then the object, LF and end. Extra fields or bytes, CRLF and surrounding whitespace fail the row; internal JSON formatting is allowed; service output goes to stderr. Code 0 means computed; an invalid input gives code 2 and empty stdout. There is no `result` envelope.

## Stand command `door-token-verify`

The `stand` key of profile `03-worker` ([common profile layout](../../acceptance/README.md), P/03.4 N5) is a template with `{input}`, the path of a file containing a verification input object `{keys, authorization, now, unit, holder, path}`. `keys` is the JSON value of `door/keys`; `authorization` is the complete Authorization header and an empty string means no header; `now` is a number. `unit` (`<sub>/<id>`) and `holder` (the instance of its heartbeat) are the holder's own. `path` is the URL request target, possibly with a query; the first path segment without the query is checked against `routes`.

A place-token call supplies `{keys, authorization, now, holder, path, place_units}` instead. `place_units` is built by the subsystem from the units whose data lie at the holder's place; a unit whose data have not landed is absent unless the door norm names it. The contract's «The place token» defines its meaning.

Stdout is exactly one JSON object in UTF-8 followed by LF: `{"result":"ok","claims":{…}}` with the actual read claims, or `{"result":"forbidden"}`; code 0. Invalid input gives code 2. Another code or result, extra fields or bytes fail the row.

## Key input and refusal

The seed is the `door/signer` row's `seed_secret` (64 lowercase hex); the matching public key is under the same kid in `door/keys`. The implementation takes supplied seed and public-key bytes and does not derive them anew.

A verification refusal is the single word `forbidden`; the holder door returns 403 and `{"error": "forbidden"}` without a reason ([P/03.4](../../../03-worker/spec/03.4-worker.norms.md), N4). The vectors do not fix check order because the answer does not expose a reason. The contract governs a discrepancy; «Specification» corrects the vector.

## Vector wire

The public `table` selector is `issue.tsv` for issuing, `verify.tsv` for verification and `place.tsv` for place-token verification (judge-only: `issue.tsv`, `verify.tsv`, `place.tsv`).

The `common/door-token` rows of [the single form](../wire.tsv) (judge-only: `wire.tsv`) bind headers, selected inputs, fixtures, native framing and comparison; [wire grammar](../wire.md) defines the frame. Layout is an excluded function declaration, never proof that its separate acceptance ran.

Fixed keys, concrete issuing and verification cases, check-to-case mappings and expected answers are in [case data and coverage](README.cases.md) (judge-only: `README.cases.md`).

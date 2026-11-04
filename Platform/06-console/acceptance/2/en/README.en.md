# Acceptance P/06.2 — the write of secrets

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей).
The norm of the chapter is [`06.2-console.norms.md`](../../../spec/06.2-console.norms.md) Н5. The scenarios, the fields file and the text below were moved from
the acceptance of М10/07 whole (stage B, ADR-0083 addendum (1):
without a change of behaviour); the numbers of the scenarios and the steps are the former ones; the common tables `secret_in.tsv` and `log_mask.tsv` are the vectors
of the chapter [`secret-in`](../../../../common/vectors/secret-in/README.md) and [`log-mask`](../../../../common/vectors/log-mask/README.md). Two vector tables,
the fields file and the scenario file; the chapter adds no paths of its own — the units door of chapter 6.1 and the store door.

## The vectors `secret-in` and `log-mask`

The common tables [`../../../common/vectors/secret-in/cases.tsv`](../../../../common/vectors/secret-in/cases.tsv) and
[`../../../common/vectors/log-mask/cases.tsv`](../../../../common/vectors/log-mask/cases.tsv) are one source of the course and of the product (ADR-0003; the product
takes them by `sync-course.sh`), there is no copy here. The format is in the header of each and in the README of the package. The runner: `secret-in` —
each row is read by the rule of the named field from the section below: the display equals `masked`,
the refusal is empty or names the field from `fault`, the text of the refusal does not contain the raw value of the password.
`log-mask` — the log mask with the catalogue rule from the same two fields gives `masked`.

## The rules of the two fields of the table (acceptance data)

`secret-in` is read by the rule of the field named in the row. The declarations of these fields are data of this acceptance, not
a reference to the VMS catalogue (ADR-0001): an implementation of chapter 6.2 is not obliged to know the manifests `cam` and `rec`. The declarations
coincide with the fields `unit.fields.source` of the manifest `cam` and `tables.volumes.fields.url` of the manifest `rec` as of 2026-10-17;
the catalogue rule for nested addresses and for `log-mask` is the union of the rules of these two fields with the common
dictionary (Н1.1 of the chapter). The form of each key is the summary table of P/02.1 Н1.2а and Н1.1 of chapter 6.2.

The declarations are the vector file [`fields.yaml`](../../../../common/vectors/secret-in/fields.yaml) (moved from this acceptance; the stage C guess URLC-SOURCE-01, the Architect's decision of 2026-10-23): the key is the name of a field from the column `field`
of `secret-in`, the value is the declaration of the field in the form of P/02.1.

## scenarios.tsv

The units door of `testsub2` (the rows `tallies`; the tables door `shelves` — sc. 10; the console root `CONSOLE_ROOT=testsub2`, the common acceptance README «Stand») and the store door; the format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей) (`console`, `store`, `@key`, `@as`, a subset of fields). The implementation is started with a key ring (`SECRETS_KEY`), the manifests `testsub` and `testsub2`, an empty store; the resource `srv-a` is the first step of sc. 01, 05, 09 (the processes are restarted between scenarios; `@start resource`: `GET /tallies` reads the heartbeats through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29); the store rows are read by a role with the right to read `testsub2/` (for example, `testsub2worker`), sc. 06 — by a role without the right (`testsubworker`). The field `of` of `tallies` is the name of a counter of `testsub`; before the scenarios the runner creates the counter `c1` in `testsub`.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows from before the move are from
`corrections.tsv` of the acceptance of М10/07 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (review analysis of stage B 6–7, № 18).

## Scenario boundaries

Scenario boundaries: the processes are restarted between scenarios, the variables are reset, and **the store is kept** within the file — the scenarios run in order, and sc. 05 reads rows written earlier; the file begins with an empty store.

The file has 11 scenarios / 65 steps (sc. 10 — the coverage audit of P/06, sc. 11 — its second pass, Gemini). Before a full repeat a new instance gets empty
application rows and claim memory, then the runner prepares c1 again. Parallel runs
do not share an instance. Between the scenarios of one file c1, the tallies rows and the claims
are kept; the ring stays the same, rotation and background changes during the file are forbidden.

The keys `Idempotency-Key` and `@key(N)` are by the dictionary, the body is taken from the current step. A happy repeat keeps it, the probe key reused changes only the secret. A restart of the process
does not replace the reset of the claim memory in the store on a new full run. The token/role of the console
has rights to the units used, the login restrictions are set so as not to hinder the scenario.

The list `configured` is checked without order — the rule of arrays without a normed order of the dictionary of [the common acceptance README](../../../../common/acceptance/README.md) (`<код> <JSON>`). A subset of
the fields of an expectation does not cancel the full form of the answer by the contract of the units door (chapter 6.1, [`06-console.api.openapi.yaml`](../../../spec/06-console.api.openapi.yaml)). The forms of an expectation are by the dictionary. The store role
by default is set anew for each scenario; an explicit @as acts on the subsequent
store requests of this scenario. ASSERT does not perform an HTTP request.

In scenario 05 at t4 `feed_secret: ""` is expected: the field is declared a string without default/inherit,
and on the creation of t4 it was not passed. It gets the empty form by chapter 6.1 Н1.2. At t1–t3
a mask is expected; the absence of the secret field is checked separately at the table shelves — sc. 10: the file does not write `shelves` rows before it,
`GET /shelves` sees one row `sh1`; in the store row the secret is an envelope `enc:v2:`, in the answers of the tables
door there is no field `feed_secret` at all (`TableRow`: `*_secret` are excluded, chapter 6.1 Н2), not a mask.

## Coverage audit of P/06, second pass (Gemini)

Sc. 11 (`audit-coverage-gemini` 0a5ae79f9) — resealing at start (Н3 «reseal at start»): the role
`console` writes past the console the unit row `t11` with an open `feed_secret`, the table row `sh11` with an open
`feed_secret` and `door/signer` with an open `seed_secret` (kid `k-acc`, the seed — 32 bytes `0x1f`); after `@restart console`
(steps 5–8 — `@until`: the resealing pass runs at start, the port may open before its end) all three are an envelope
`enc:v2:`, the `revision` of the unit is the former `1`; `door/keys` is `{k-acc: <открытый ключ зерна>}` (chapter 6.5 Н3 «`/where/<id>`»
`door/keys`: one's own kid at start, after the resealing). The Ed25519 public key of the seed `1f…1f` is
`43046bfe4092b3e94994eada15dcc20d8aaa07b658fd3954eb8e0efb8bdca5de` (RFC 8032, obtained by the library `cryptography`).
The file does not write the rows `door/signer`, `door/keys` before sc. 11: `/where` is not called in the scenarios of the chapter. Resealing under
the former kid — by reading: the stand has one ring.

## Reconciliation of python and go М10/6–11

- Sc. 02 steps 5–6: a mask with a Unicode whitespace character at the edge (`\t***`, `\u00a0***`) — 400 (Н1.1 `mask_in`, S12).
- Sc. 04 steps 9–14:
  - unparsable urls (`https'://`, a space before `://`, `https:%3A//`) — 400 `bad_url` (S3);
  - `'` in the host name does not cut the address: `token` after it is a password (А2, S4);
  - a password in the nested address `via` and in the pair `who`, hidden by escaping, — a refusal without the login field `feed_user`
    (А8 «Вид», А7, А15; S16).
- Sc. 07: the json field `rule` of the manifest `testsub2` with nested `pw_secret`.
  - A permutation of the elements `cams` without passwords: in the answer and in the store row there are no secrets, the password of A does not go to B
    (Н3 step 3, S1).
  - A nested `null` is given as `null` (S20).
  - A nested secret as a number — 400 (S13).
- Sc. 08: a change of `feed` at a unit without a secret — 400 «must be given anew», with a secret — 200 (Н3 step 3, S9).
- Tables, rows at the end:
  - `secret-in` — `'`, `<` and a character outside the grammar without a password (S4);
  - `log-mask` — the value of a secret pair whole, a name decoded into pairs, `<` inside a value, a JSON token
    (S17, S4, S18).

## Checks outside the scenario file

- Full bodies of secret refusals: detail/error are mandatory; bad_url only for an address;
  an unreadable ring — 503 SealingUnavailable on POST/PUT. GET/DELETE requests do not get
  this new reason. No diagnostic repeats the original value of the secret.
- The states of one's own/a foreign pending and of an unknown outcome — by chapter 6.1 Н3; the outcome 503 is not done,
  a foreign claim is not removed. This check requires a model/an execution of the needed state,
  the ordinary happy repeat of scenario 01 does not replace it.
- The ring: not set, set and readable, set and empty/damaged/unreadable; a separate
  opening with a foreign kid, a wrong row/field and a damaged envelope. An empty file
  does not admit the write of an open secret. Do not count a check of the prefix as a check of AES-GCM.
- Maintenance: the successive states of the table Н3, k1/k9/k10, the refusal of rotate for
  other kids, zero, leading zeros, repeats and an unrepresentable next number.
  An unconfirmed traversal/write keeps the old keys; a dependent copy is not skipped
  only because the current rows are resealed. The work is done with the ordinary
  writes stopped, a concurrent rotation is not declared checked. In the
  profile of the chapter all the old keys are kept; status does not confirm the possibility of deleting them.
- GET of a table without secret fields, nested secrets, snapshots, the log, argv and the heartbeat are
  separate subjects of reading of Н5. File permissions and the opening by a worker are confirmed by the stand.

## Counterexamples of run 31 and close admissible cases

1. A separate new instance without SECRETS_KEY, an empty claim memory, c1 prepared.
   POST /tallies with the key x and the body {name:t1, of:c1, feed:https://hub.example/a,
   feed_secret:alpha} — 400 with the exact refusal body of Н4, without fault. Replace only alpha
   with bravo, keep x — the same refusal; there is no unit, no claim, no reserved number.
   Repeat with a nested secret in an admissible JSON field of a separate manifest; absence,
   an empty string and null are not a non-empty secret (the other form checks are kept).
   A POST without a secret stays an ordinary creation, its repeat works by chapter 6.1.
2. With the ring k1: the same POST with alpha creates a unit, an exact repeat returns the former
   answer; replacing only the secret with bravo gives 422 key reused and changes nothing.
   This is the last step of scenario 01. Also check a former pending younger/older than 30 s
   by the rules of chapter 6.1: the prohibition without a ring does not remove a foreign claim; a set unreadable
   ring stays 503, it is not replaced by the mode without a key.
3. With the ring k1 leave the done claim of the original POST, then by PUT change the secret of the unit.
   Stop the ordinary writes, add k2, restart the holders, reseal
   the rows and get zero old envelopes. k1 stays in the ring; the exact original
   POST under the former key returns the old answer, a changed one — 422. Do not recompute
   the HMAC from the current unit and do not compare the old claim only under the current k2.
4. Parsing of the ring: the line #backup + 64 hex is a comment, a ring of only it is empty
   and unreadable. # a note, an empty line, then k1 + 64 hex — a correct ring;
   a#b + 64 hex — an admissible imported kid for open/seal, but not for rotate.
   k1 + 64 hex + #tail — a wrong entry. In the diagnostic of a foreign kid it is
   exactly the name of the envelope (for example, k9) that is shown, without its key bytes.

This is a specification of additional probes, not a statement of execution by an implementation.

Probes of run 32: a set unreadable ring gives SealingUnavailable on all POST/PUT of units, including a body without secret and with an empty/null/omitted secret, before the HMAC/claim; GET/DELETE — the ordinary outcomes. An unset ring keeps a separate profile of 400 only for a non-empty secret in POST. In secret-in the row with pass%E2%80%8Bword requires an explicit removal of U+200B from the normalized name by Н1; the original name/value are not rewritten before masking.

Additional check by reading/model R36-06: the AAD of Н1.2 uses the full path. Distinguish the rows a#b with the field c and a with the field b#c, a direct field and a nested one, the same *_secret in different objects/array indices, keys with /, ~, NUL and Unicode. For each path check the unambiguous JSON Pointer escaping and the UTF-8 bytes without normalization; opening does not try the old AAD. This is a check of the form of the context, not of the strength of AES or of an actual opening by an implementation. The transition of old sealed rows requires a separate rollout and a trusted source, it is not checked by the TSV.

## Additional check of the class of errors of run 36 (Kimi)

By reading, check the order of POST/PUT: after a bounded parsing of the JSON object, the ring comes before the form of the fields, the HMAC and the capture of the claim. An unreadable ring gives the common 503 by chapter 6.1 even with a bad field. GET/DELETE do not acquire this refusal. P/02.5 Н1.3 includes domainworker as a platform role; the manifests of subsystems do not include it (there is no process of this role, P/01.2 Н1.1). The check of the common table by the loader is the work of an implementation, not of this acceptance.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Check of the error class R37 (Codex)

A source of a public id/name/rid with the suffix _secret is rejected at load, even if the original field is masked. Check a single table.key, all the substitutions and requests.key. The prohibition of NUL is a condition of the seal/open profile of the sealing contract; the common Cmd of P/01.1 by itself does not forbid NUL. Do not attribute a restriction to an owner that does not have it.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

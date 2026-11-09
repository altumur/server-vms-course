# Acceptance P/06.2 — the write of secrets

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.2-console.norms.md`](../../spec/06.2-console.norms.md) N5. The scenarios, the fields file and the text below were moved from
the acceptance of M10/07 whole (stage B, ADR-0083 addendum (1):
without a change of behaviour); the numbers of the scenarios and the steps are the former ones; the common tables `secret_in.tsv` and `log_mask.tsv` are the vectors
of the chapter [`secret-in`](../../../common/vectors/secret-in/README.md) and [`log-mask`](../../../common/vectors/log-mask/README.md). Two vector tables,
the fields file and the scenario file; the chapter adds no paths of its own — the units door of chapter 6.1 and the store door.

## The vectors `secret-in` and `log-mask`

The common tables [`../../../common/vectors/secret-in/cases.tsv`](../../../common/vectors/secret-in/cases.tsv) and
[`../../../common/vectors/log-mask/cases.tsv`](../../../common/vectors/log-mask/cases.tsv) are one source of the course and of the product (ADR-0003; the product
takes them by `sync-course.sh`), there is no copy here. The format is in the header of each and in the README of the package. The runner: `secret-in` —
each row is read by the rule of the named field from the section below: the display equals `masked`,
the refusal is empty or names the field from `fault`, the text of the refusal does not contain the raw value of the password.
`log-mask` — the log mask with the catalogue rule from the same two fields gives `masked`.

## The rules of the two fields of the table (acceptance data)

`secret-in` is read by the rule of the field named in the row. The declarations of these fields are data of this acceptance, not
a reference to the VMS catalogue (ADR-0001): an implementation of chapter 6.2 is not obliged to know the manifests `cam` and `rec`. The declarations
coincide with the fields `unit.fields.source` of the manifest `cam` and `tables.volumes.fields.url` of the manifest `rec` as of 2026-10-17;
the catalogue rule for nested addresses and for `log-mask` is the union of the rules of these two fields with the common
dictionary (N1.1 of the chapter). The form of each key is the summary table of P/02.1 N1.2a and N1.1 of chapter 6.2.

The declarations are the vector file [`fields.yaml`](../../../common/vectors/secret-in/fields.yaml) (moved from this acceptance; the stage C guess URLC-SOURCE-01, the Architect's decision of 2026-10-23): the key is the name of a field from the column `field`
of `secret-in`, the value is the declaration of the field in the form of P/02.1.

## scenarios.tsv

The units door of `testsub2` (the rows `tallies`; the tables door `shelves` — sc. 10; the console root `CONSOLE_ROOT=testsub2`, the common acceptance README «Stand») and the store door; the format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) (`console`, `store`, `@key`, `@as`, a subset of fields). The implementation is started with a key ring (`SECRETS_KEY`), the manifests `testsub` and `testsub2`, an empty store; the resource `srv-a` is the first step of sc. 01, 05, 09 (the processes are restarted between scenarios; `@start resource`: `GET /tallies` reads the heartbeats through the objects door of the resource of its server; C06-PULSE-LAPSE-503-03, the Architect's decision of 2026-10-29); the store rows are read by a role with the right to read `testsub2/` (for example, `testsub2worker`), sc. 06 — by a role without the right (`testsubworker`). The field `of` of `tallies` is the name of a counter of `testsub`; before the scenarios the runner creates the counter `c1` in `testsub`.

## Scenario boundaries

Scenario boundaries: the processes are restarted between scenarios, the variables are reset, and **the store is kept** within the file — the scenarios run in order, and sc. 05 reads rows written earlier; the file begins with an empty store.

The file has 11 scenarios / 65 steps (sc. 10 — the coverage audit of P/06, sc. 11 — its second pass, Gemini). Before a full repeat a new instance gets empty
application rows and claim memory, then the runner prepares c1 again. Parallel runs
do not share an instance. Between the scenarios of one file c1, the tallies rows and the claims
are kept; the ring stays the same, rotation and background changes during the file are forbidden.

The keys `Idempotency-Key` and `@key(N)` are by the dictionary, the body is taken from the current step. A happy repeat keeps it, the probe key reused changes only the secret. A restart of the process
does not replace the reset of the claim memory in the store on a new full run. The token/role of the console
has rights to the units used, the login restrictions are set so as not to hinder the scenario.

The list `configured` is checked without order — the rule of arrays without a normed order of the dictionary of [the common acceptance README](../../../common/acceptance/README.md) (`<code> <JSON>`). A subset of
the fields of an expectation does not cancel the full form of the answer by the contract of the units door (chapter 6.1, [`06-console.api.openapi.yaml`](../../spec/06-console.api.openapi.yaml)). The forms of an expectation are by the dictionary. The store role
by default is set anew for each scenario; an explicit @as acts on the subsequent
store requests of this scenario. ASSERT does not perform an HTTP request.

## Checks outside the scenario file

- Full bodies of secret refusals: detail/error are mandatory; bad_url only for an address;
  an unreadable ring — 503 SealingUnavailable on POST/PUT. GET/DELETE requests do not get
  this new reason. No diagnostic repeats the original value of the secret.
- The states of one's own/a foreign pending and of an unknown outcome — by chapter 6.1 N3; the outcome 503 is not done,
  a foreign claim is not removed. This check requires a model/an execution of the needed state,
  the ordinary happy repeat of scenario 01 does not replace it.
- The ring: not set, set and readable, set and empty/damaged/unreadable; a separate
  opening with a foreign kid, a wrong row/field and a damaged envelope. An empty file
  does not admit the write of an open secret. Do not count a check of the prefix as a check of AES-GCM.
- Maintenance: the successive states of the table N3, k1/k9/k10, the refusal of rotate for
  other kids, zero, leading zeros, repeats and an unrepresentable next number.
  An unconfirmed traversal/write keeps the old keys; a dependent copy is not skipped
  only because the current rows are resealed. The work is done with the ordinary
  writes stopped, a concurrent rotation is not declared checked. In the
  profile of the chapter all the old keys are kept; status does not confirm the possibility of deleting them.
- GET of a table without secret fields, nested secrets, snapshots, the log, argv and the heartbeat are
  separate subjects of reading of N5. File permissions and the opening by a worker are confirmed by the stand.

Additional check by reading/model R36-06: the AAD of N1.2 uses the full path. Distinguish the rows a#b with the field c and a with the field b#c, a direct field and a nested one, the same *_secret in different objects/array indices, keys with /, ~, NUL and Unicode. For each path check the unambiguous JSON Pointer escaping and the UTF-8 bytes without normalization; opening does not try the old AAD. This is a check of the form of the context, not of the strength of AES or of an actual opening by an implementation. The transition of old sealed rows requires a separate rollout and a trusted source, it is not checked by the TSV.

## Additional check of the class of errors of run 36 (Kimi)

By reading, check the order of POST/PUT: after a bounded parsing of the JSON object, the ring comes before the form of the fields, the HMAC and the capture of the claim. An unreadable ring gives the common 503 by chapter 6.1 even with a bad field. GET/DELETE do not acquire this refusal. P/02.5 N1.3 includes domainworker as a platform role; the manifests of subsystems do not include it (there is no process of this role, P/01.2 N1.1). The check of the common table by the loader is the work of an implementation, not of this acceptance.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Check of the error class R37 (Codex)

A source of a public id/name/rid with the suffix _secret is rejected at load, even if the original field is masked. Check a single table.key, all the substitutions and requests.key. The prohibition of NUL is a condition of the seal/open profile of the sealing contract; the common Cmd of P/01.1 by itself does not forbid NUL. Do not attribute a restriction to an owner that does not have it.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

# Acceptance P/02.5 — the derivation of rights through the store door

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.5-installer.norms.md`](../../spec/02.5-installer.norms.md) N5, the full bodies of the two routes are
[the OpenAPI](../../../01-store/spec/01-store.api.openapi.yaml) of lesson P/01.
The file has 8 scenarios / 70 steps (sc. 12 steps 12–18 — `domainagent` does not write `domain/root`, `view`, `shadow`, `backups/rev-1`, `shared-docs/rev-1`, `alarm-history/m1`, `idem/k1`, 403, C02-LOCAL-BINDING240-ROOT; the mutation check 7cecaf2 № 29, 49: the admission rows of the controller without delete, the negation of `idem` at the worker; sc. 13 — the order and the state, ADR-0091, sc. 02 step 8 — the deletion of a row of `testsub2` by the controller is now 200: it has `retire_when.delete_after` and `ends`); the roles and the rights file are generated from `testsub` and `testsub2`
(`Source/tests/testdata/testsub*.subsystem.yaml`) with the deployment name `testsub`.
The scenarios and the manifest variants were moved from the acceptance of М10/6
(stage B) with the former numbers, steps and texts. Scenarios 05–08 and 10 (the evaluator, `never`, listing, the guard, identity,
`/v1/rights`) are in the acceptance of [P/01.2](../../../01-store/acceptance/2/README.md) (stage B); the numbers of the remaining ones did not change.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): a door without a prefix is the store, `@as <role>`, `@header` before the method, `$name`, `ASSERT`;
the expectation is a subset of fields, `index` may be omitted. Own additions:

- `expect` without a body at the code `403` — the full form `{kind: forbidden, error: …}`. For a refusal of an operation on a row, error names the role, the action and the key.

An absent expectation body of 200 does not mean an empty answer. Its form is checked by the contract
of the input of chapter P/01.1; 403 — exactly the strings kind/error without console fields. `$name` is bound only
after a match of the whole step; a repeat of a variable is compared with the earlier value. The order
of keys in list remains the order of the store, the runner does not sort the actual answer.

The roles of the scenarios: `console`, `testsubcontroller`, `testsubworker`, `testsub2controller`, `testsub2worker`, `resource`;
sc. 12 — also `testsubdomain` and `domainagent` (the domain roles of the rights file `testsub`: `testsub` has `kept` and a transferable
book `tallies`, `testsub2` has only collected books — there is no role `testsub2domain` and no socket).

The reconciliation of python and go М10/6–11 (R1–R5, R7): sc. 04 steps 4–7 — the resource reads the terms of both manifests (there are no rows: `items:
null`); sc. 12 — the domain roles.

## `journal/corrections-5.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from
`corrections.tsv` of the acceptance of М10/06 (removed by the move of lesson 6, `e11928b21`), at the beginning of this log by the scenarios of the chapter, with the former paths and numbers (they are
resolved by `Platform/common/id-map.tsv`); the rows without a scenario are in all successor chapters (review analysis of stage B 6–7, № 18).

## Isolation

Each scenario, including a repeated run, gets a separate instance with empty
application rows and an empty id replay memory. Clearing the prefixes does not substitute for clearing this
memory. The runner variables are reset, the role is set by the first `@as`; the rights file is the same
in all scenarios. Parallel runs do not share an instance.

The background consoles, controllers, workers and the resource do not write into these rows. The permission data
is prepared by the runner through the generator and the instance setup, and each step is executed only by
the named role. Scenario 09 checks the read right of door/signer: the row need not be created,
an allowed read of an absent row returns Row with items null per chapter P/01.1.

## Manifest variants (`variants/`)

The derivation of rights by meaning on manifests outside the stand (the reconciliation of python and go М10/6–11: R2–R8, R10, R12; registry line e31e5c28).
The directory `variants/<variant>/` — the files `*.subsystem.yaml` (the manifest catalogue of the variant, loaded per chapter 2.1) and exactly
one of: `expect.tsv` (the derivation of rights and probes), `refused` (an expected generation refusal), `check.tsv` with the directory `check/` (the comparison
`--check`); the forms of `refused` and `check.tsv` are the Architect's decision on the question of the form (the Gemini audit P/02, properties 24, 25).

**`expect.tsv`:** UTF-8, LF, fields separated by TAB; lines with `#` are skipped; the header `role	action	key	expect`; then one
line per probe: a role of the rights file (P/01.2 N1.1), the action `read` | `write` | `delete`, the row key, `allow` | `deny`.

**Execution.** For each variant the runner:
1. calls the rights derivation tool of the implementation (N2, «Implementation decides» item 1) on the catalogue of the variant with the deployment `dep` —
   by the rights derivation command of the «Stand» of the common acceptance README; code ≠ 0 — a mismatch of the variant;
2. starts a fresh store instance with this file (`{rights}`);
3. for each line calls through the role socket: `read` — `GET /v1/get?key=<key>`, `write` — `put` with `items: {"p": "1"}`, `delete`
   — `delete`, without `cas` and a guard. The rule is as in the evaluator vector (`Platform/01-store/vectors/rights-evaluator`):
   `allow` — only a confirmed success: for a read 200 of the form `Row` (for an absent row — `{items: null, index: ""}`,
   chapter P/01.1 N2), for a write and a deletion 200 `Written`; `deny` — 403 `forbidden`; there is no role socket — the same as 403 (the role is not in the
   file: «role not in the file → no», P/01.2 N1.3); 5xx, a transport error and another answer — an undetermined outcome: the probe is not
   counted either as `allow` or as `deny`, the run of the variant is not green (review of stage A, RA1-16).

The order of lines does not matter: each probe is its own action on one fresh instance. This checks the meaning of the rights file (P/01.2 N1.3 and
`never`), not its bytes: the order of patterns, `comment`, extra equivalent patterns (R18) and groups are not compared.

**`refused`:** UTF-8, LF; lines with `#` are skipped; exactly one other line — the `name` of the manifest of the variant whose declaration
is refused. The runner calls the rights derivation command as in item 1 above: the code MUST be `2`, there is no rights file at the path `{file}` (a generation refusal
before the file, N4), stderr names this manifest — its `name` or its file (N4: «имя объявления и манифест»);
the text beyond this is not compared. The store is not started, there are no probes.

**`check.tsv`:** UTF-8, LF, fields separated by TAB; lines with `#` are skipped; the header `case	file	code`; then one line per
case: `case` — `[a-z0-9_]+`, unique; `file` — `check/<case>.rights`, a rights file; `code` — `0` (the file by meaning
equals the generated one) or `!0` (any code except 0). For each line the runner calls the rights comparison of the implementation (`rights --check
<file>`, N2, N3 «install») — by the command `stand.rights-check` of the profile `02-installer` ([the common acceptance README](../../../common/acceptance/README.md),
«Команда сверки прав»): `{manifests}` — the manifest catalogue of the variant, `{deployment}` = `dep`, `{file}` — `check/<case>.rights`;
the outcome is the code, compared with the column `code`. No key in the profile — the cases of `check.tsv` are not executed (neither GREEN nor an outcome of the
implementation) (the Architect's decision of 2026-10-30, the norm questions of the Gemini audit, P/02 item 3; C02-RIGHTS-CHECK-STAND-01). The comparison by meaning
is N3 «install»: the set of roles, for each one `group` and the sets of patterns `read`, `write`, `delete` (no `delete` — an empty
set); `comment`, order, repeats and spaces are not compared; a file not by the form of P/01.2 N1.2 — diverges.

| Variant | Manifests | What it checks |
|---|---|---|
| `v1-base` | `va` without `requests`, with `delete_after` | the roles of the platform and of the manifest; there is no console `requests/*` (R8); an empty `<y>` and `never` of the epoch (R12); `retention` of the resource (R2); `domain/grants` of the console — the exact key and the family `domain/grants/*` (`domain/grants/c1` — yes: the domain trace P/06.3 N1.8; review analysis of stage A 8–10, plan 8 V7, a behaviour change), `domain/view` — no (R5); `domain/holder` of the worker (R7); there is no role `vadomain`; `door/signer` is read by the console, not by the worker, without a declaration in the manifest (review analysis of stage B 6–7, № 36) |
| `v2-requests` | `va` with `requests`, `vb` with `worker.requests: [va]` | the console `requests/*` only at `va`; the submission of `vbworker` into `va`; the marks `objects/va/commands/*` (R8, R9) |
| `v3-objects-rows` | `va` with `objects.rows: [marks/]` | `marks/` → `objects/va/marks/*` (R10) |
| `v4-domain-kept` | `va` with `domain.kept: [ledger, badges/]` | `vadomain` writes the slot and `kept`; `domainagent` — by the form of the declaration and without the slot and the pulse of the worker on the domain (R4, R3) |
| `v6-near-about-ref` | `va`; `vb` with `placement.near.sub: va`, `vc` with `about.sub: va`, `vd` with the field `ref: va/items` | the controller reads the rows of `va` by the catalogue (`placement`, `workers`, `slots`, `holds`, unit rows, `policy`, `placement_turn`), not the epoch, `idem`, `next_id`, and does not write; there is no reverse link (the Architect's decision of 2026-10-27; P/03 Go 084a3ee9, P/03.6 sc. 07) |
| `v7-must-match` | `va` (the field `shelf` — `ref: va/shelves`, `must_match: {zone: zone}`; the table `shelves`); `vb` with `worker.creates` on `va/items` (`key: "{code}"`); `vc` with the table `links`, the field `of` — `ref: va/items`, `must_match: {zone: zone}` | the customer `vbworker` reads the targets of the row check — `va/shelves/*` (the direct branch) and `vc/links/*` (the reverse branch of `must_match`), writes only `va/items/vb-*` without deletion; foreign rows of `va/items` and the other families of `vc` — no; the controller of `va` does not read the reverse family (the coverage audit P/02, B07) | P/02.5 N1.4 `<s>worker` «чтения общей проверки строки»; the row check contract |
| `v8-worker-writes-deletes` | `va` with the tables `shelves`, `gauges`, `worker.writes: [gauges]`, `worker.deletes: [items]` | the table of `worker.writes`: the worker writes, reads and deletes, the console reads and only deletes; an ordinary table: the console writes and deletes, the worker only reads; `worker.deletes`: the worker deletes unit rows without a write, the controller without `delete_after` — no (the coverage audit P/02, second pass) | P/02.5 N1.4 `console`, `<s>worker`, N3 step 2 |
| `v9-asked-free-resource` | `va` with `requests` without `per_person` and `free`; `vb` with `about.sub: va`, the tables `notches` (`holds.table`) and `shelves`, `requests` with `per_person` and `free: true` | the console writes `vb/asked/*`, not `va/asked/*`; `!vb/asked/*` at the worker and the controller of `vb`; the resource writes, reads, deletes `vb/requests/free-*`, not `vb/requests/<rid>` and not `va/requests/free-*`; the resource reads the table `holds.table` (`vb/notches/*`) and the unit rows of the manifest with `about` (`vb/things/*`), not other tables, not the rows of `va` without `about` and not the place family `<s>/holds/*` either at `vb` or at `va` (the holds contract; C02-RESOURCE-HOLDS-TABLE-01) (ibid.) | P/02.5 N1.4 the general rules, `console`, `resource` |
| `v10-worker-domain-reads` | `va` with `worker.reads: [domain/placed/va/, domain/va/tallies]`, the books `tallies` (transferable), `notes` (`from: va/notes/`), `rolls` (`from: va/rolls`), `domain.shared`, a token kind with `unit`, `door.routes`; `vb` without them | `domain/placed/va/` gives also `domain/placement/va/*`; the copy of its own book — also the exact key `domain/va/tallies/local` (`CLUSTER` is not set — `local`), not a prefix; the write of the sources of collected books — a prefix and an exact key; `domain/shared`, `domain/topology`, `domain/member-topology`, `domain/grants` — only at `vaworker` (ibid.) | P/02.5 N1.4 `<s>worker`, N2, N3 step 3 (C02-OWN-BOOK-HOLDER-01) |
| `v11-controller-cross-tables` | `vb`, `vc`, `vd` — as in `v6-near-about-ref`; `va` with the table `shelves` and `requests` (`per_person`) | the controller of a linked subsystem reads the tables of `va`, `va/decommissioned/*`, `va/controller/placement_intent`, does not read `va/requests/*`, `va/asked/*` and does not write the table of `va` (ibid.) | P/02.5 N1.4 `<s>controller` (the Architect's decision of 2026-10-27) |
| `v12-check-rights` | `va` — byte for byte `v1-base`; `check.tsv` | `--check`: exactly the derivation of rights per N1.4 (`same`) — code 0; a derivation without the role `vaworker`, with a write of unit rows by the worker, with another worker group, without `delete` of the controller, with an extra field of the file — the code is not 0 (the Gemini audit P/02, property 24; `same` — the Architect's decisions of 2026-10-30, P/02 items 1, 2) | P/02.5 N1.4, N2, N3 step 4, «install», N4 |
| `v13-refused-idem-read` | `va` — byte for byte `v2-requests`; `vb` with `worker.reads: [va/idem/k1]`; `refused` | a declaration of the worker directly names a row inside `va/idem/` — a generation refusal before the file, code 2, the manifest `vb` (property 25) | P/02.5 N1.4 the general rules, N4 (C02-IDEM-ASKED-EXPLICIT-READ-01) |
| `v14-refused-secrets-reads-nested` | `va` with `secrets.readers: {va/vault/: [worker]}`; `vb` with `secrets.reads: [va/vault/public/]`; `refused` | an element of `secrets.reads` is strictly nested in a secret prefix of another manifest — a generation refusal before the file, code 2, the manifest `vb` (property 25) | P/02.5 N3 step 4, N4 (C02-SECRETS-READS-INTERSECTION-01) |
| `v5-secret-domainworker` | `va` with `secrets.readers: {va/vault: [domainworker]}` and `kept` | `domainworker` → `vadomain` reads, the others — no (R6) |

The manifests of the variants `v1`–`v5` are byte for byte those on which the reconciliation generated the rights of both implementations — both load them; `v6-near-about-ref` — the Architect's decision of 2026-10-27; `v7-must-match` — the coverage audit P/02 (audit-kimi 2026-10-30, commit 82f4da9fc). `v8`–`v14` — the coverage audit P/02, second pass (Gemini, c698f3291; below).

## Checks outside the scenario file

- The checks of `/v1/rights`, of the rights file form, of the evaluator, of `never` and of forwarding — in the acceptance of P/01.2 (stage B).
- Check the derivation of roles with a short and with the limit 32-character manifest name: the roles of the rights file (the grammar of P/01.2) keep
  the full name and the suffix — by the rights derivation function over the manifest, without OS names; a full catalogue with such a name — a catalogue refusal by
  OS names longer than 32 characters (P/02.4 N1.1 `users_groups` names; C02-NAME32-ROLES-01). `--check` uses an unchanged catalogue.
  The negative example of the file form contains no manually extended rights.
- Per N5, compare the effective read/write/delete of both admission rows of the controller and
  the preservation of the other deletions. Secret readers are compared among the ordinary roles;
  admin has a separate exception, it is not added to secrets.readers.

These are subjects of a separate reading/structural test, not additional executed
scenarios. Socket modes, forwarding and the certificate need a corresponding stand.

The probes of run 32: the declarations testsub/vault*, testsub/va*ult/, !testsub/vault and delete:testsub/vault are rejected before the file. For an admissible exact testsub/vault the neighbouring vault2 and vault/nested keep their ordinary rights; testsub/vault/ denotes only the family under the slash. The common Key/Listing of chapter P/01.1 still admit a literal * as data.

The check R36-05 (since 2026-10-30 — the cases `worker_writes_unit_rows`, `worker_writes_undeclared` — refused, `worker_writes_declared_ok`, `worker_writes_declared_list_ok` — ok of the acceptance of chapter 2.1; the coverage audit P/02, B06): worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

## Additional check of the error class of run 36 (Kimi)

By reading: the TLS key belongs to the user of the unit or to root with the group of the user of the unit (ADR-0075 addendum 3), the group of a role socket gives no access to the key. Compute the resulting set of rights with never and the negations of the secret readers: a positive baseline does not return a forbidden access. The generator keeps both families domain/placed and domain/placement and a separate console delete:platform/doors/*.

This is a subject of a manual check of the specification and of a future check of an implementation. The author's prepared requests, reading and finite models are not a performed stand test.

Scenario 11 — the request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and
deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4; the log of cammeta-go, lesson 8 № 4).

## The coverage audit P/02, second pass (Gemini)

The report `АУДИТ-ПОКРЫТИЯ-GEMINI-P02.md` (branch gemini/audit-coverage, c698f3291): the derivation of rights that was formerly checked by reading —
the variants `v8-worker-writes-deletes` (G04), `v9-asked-free-resource` (G05), `v10-worker-domain-reads` (G06),
`v11-controller-cross-tables` (G07; a separate variant — the manifests of `v6-near-about-ref` do not change). The variant table is above.
`--check` and the generator refusals before the file — the Architect's forms `check.tsv` and `refused` (above): `v12-check-rights`,
`v13-refused-idem-read`, `v14-refused-secrets-reads-nested`. The case of `check.tsv` with the code `0` is `same` of the variant `v12-check-rights`:
exactly the derivation of rights per N1.4 after the Architect's decisions of 2026-10-30 (the norm questions of the Gemini audit, P/02): to the resource — `<M>/<holds.table>/*`
only at a manifest with `holds`, `<s>/holds/*` is not given (item 1, C02-RESOURCE-HOLDS-TABLE-01); the negation of a secret to a non-reader — only
if after the negations already given its rights still reach the pattern (item 2, C02-NONREADER-DENY-AFTER-01); the marks
`objects/<s>/commands/*` of the console — only at a manifest with `requests` (as at the worker; `va` has none). The other files of `check/` are this derivation with
one edit. What remains by reading: the inequality
of the secret readers (cannot be built from the manifests of the catalogue: the readers are derived from the same declarations) and `CLUSTER=` (an input
of the environment, not of the catalogue of the variant).

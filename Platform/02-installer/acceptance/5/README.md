# Acceptance P/02.5 — the derivation of rights through the store door

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.5-installer.norms.md`](../../spec/02.5-installer.norms.md) N5, the full bodies of the two routes are
[the OpenAPI](../../../01-store/spec/01-store.api.openapi.yaml) of lesson P/01.
The file has 8 scenarios / 70 steps; the roles and the rights file are generated from `testsub` and `testsub2`
(`Platform/common/data/testsub/testsub*.subsystem.yaml`) with the deployment name `testsub`.
The scenarios and the manifest variants were moved from the acceptance of M10/6
(stage B) with the former numbers, steps and texts. Scenarios 05–08 and 10 (the evaluator, `never`, listing, the guard, identity,
`/v1/rights`) are in the acceptance of [P/01.2](../../../01-store/acceptance/2/README.md) (stage B); the numbers of the remaining ones did not change.

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). `stand.rights` consumes `{manifests}`, `{deployment}` and output `{file}` and derives the rights file by this chapter's algorithm; refusals and file absence are those below. `stand.rights-check` consumes the same manifest/deployment inputs and the existing `{file}` to compare, without writing it; zero means semantic equality, nonzero means disagreement. `stand.ring` and `stand.manifest-put` prepare the existing common stand as assigned there; the selected `01-store` profile owns the store process and its role sockets. The implementation chooses the commands and flags for these interfaces. Missing comparison coverage remains unexecuted, not a generated substitute result.

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

The reconciliation of python and go M10/6–11 (R1–R5, R7) is part of these scenarios.

## Isolation

Each scenario, including a repeated run, gets a separate instance with empty
application rows and an empty id replay memory. Clearing the prefixes does not substitute for clearing this
memory. The runner variables are reset, the role is set by the first `@as`; the rights file is the same
in all scenarios. Parallel runs do not share an instance.

The background consoles, controllers, workers and the resource do not write into these rows. The permission data
is prepared by the runner through the generator and the instance setup, and each step is executed only by
the named role. A read right is checked without creating the row:
an allowed read of an absent row returns Row with items null per chapter P/01.1.

## Manifest variants (`variants/`)

The derivation of rights by meaning on manifests outside the stand (the reconciliation of python and go M10/6–11: R2–R8, R10, R12; registry line e31e5c28).
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
before the file, N4), stderr names this manifest — its `name` or its file (N4: «declaration name and manifest»);
the text beyond this is not compared. The store is not started, there are no probes.

**`check.tsv`:** UTF-8, LF, fields separated by TAB; lines with `#` are skipped; the header `case	file	code`; then one line per
case: `case` — `[a-z0-9_]+`, unique; `file` — `check/<case>.rights`, a rights file; `code` — `0` (the file by meaning
equals the generated one) or `!0` (any code except 0). For each line the runner calls the rights comparison of the implementation (`rights --check
<file>`, N2, N3 «install») — by the command `stand.rights-check` of the profile `02-installer` ([the common acceptance README](../../../common/acceptance/README.md),
«Rights comparison command»): `{manifests}` — the manifest catalogue of the variant, `{deployment}` = `dep`, `{file}` — `check/<case>.rights`;
the outcome is the code, compared with the column `code`. No key in the profile — the cases of `check.tsv` are not executed (neither GREEN nor an outcome of the
implementation) (the Architect's decision of 2026-10-30, the norm questions of the Gemini audit, P/02 item 3; C02-RIGHTS-CHECK-STAND-01). The comparison by meaning
is N3 «install»: the set of roles, for each one `group` and the sets of patterns `read`, `write`, `delete` (no `delete` — an empty
set); `comment`, order, repeats and spaces are not compared; a file not by the form of P/01.2 N1.2 — diverges.

The variants and their expected outcomes are in [judge-only case data](README.cases.md). They cover these subjects:

| Subject | Norm |
|---|---|
| the roles of the platform and of a manifest; the console family `requests/*`; an empty `<y>` and `never` of the epoch; `retention` of the resource; `domain/grants`, `domain/view` and `domain/holder`; `door/signer` without a declaration in a manifest | P/02.5 N1.4 (R2, R5, R7, R8, R12; the domain trace P/06.3 N1.8) |
| the submission of a worker into the requests of another manifest and the marks `objects/<s>/commands/*` | R8, R9 |
| the family of an entry of `objects.rows` | R10 |
| the slot and `kept` of the role `<s>domain`; `domainagent` by the form of the declaration | R4, R3 |
| the reads of a linked controller by the catalogue; there is no reverse link | the Architect's decision of 2026-10-27; P/03.6 sc. 07 |
| the reads of a customer on the targets of the row check, on the direct and the reverse branch of `must_match`; its writes by `worker.creates` | P/02.5 N1.4 `<s>worker` «reads of the common row check»; the row check contract |
| the tables of `worker.writes` and `worker.deletes` next to an ordinary table | P/02.5 N1.4 `console`, `<s>worker`, N3 step 2 |
| `<s>/asked/*`, the requests `free-*` and `holds.table` for the console and the resource | P/02.5 N1.4 the general rules, `console`, `resource`; the holds contract (C02-RESOURCE-HOLDS-TABLE-01) |
| `worker.reads` of `domain/placed/<s>/`, the copy of the own book, the sources of collected books, `domain/shared` and the topology rows | P/02.5 N1.4 `<s>worker`, N2, N3 step 3 (C02-OWN-BOOK-HOLDER-01) |
| a linked controller on the tables of another manifest | P/02.5 N1.4 `<s>controller` (the Architect's decision of 2026-10-27) |
| `--check` against the derivation of rights per N1.4 | P/02.5 N1.4, N2, N3 step 4, «install», N4 |
| a declaration that directly names a row inside `<s>/idem/`: a generation refusal before the file | P/02.5 N1.4 the general rules, N4 (C02-IDEM-ASKED-EXPLICIT-READ-01) |
| an element of `secrets.reads` strictly nested in a secret prefix of another manifest: a generation refusal before the file | P/02.5 N3 step 4, N4 (C02-SECRETS-READS-INTERSECTION-01) |
| `secrets.readers` with `domainworker` | R6 |

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

The check R36-05 (since 2026-10-30 — cases of the acceptance of chapter 2.1; the coverage audit P/02, B06): worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

## Additional check of the error class of run 36 (Kimi)

By reading: the TLS key belongs to the user of the unit or to root with the group of the user of the unit (ADR-0075 addendum 3), the group of a role socket gives no access to the key. Compute the resulting set of rights with never and the negations of the secret readers: a positive baseline does not return a forbidden access. The generator keeps both families domain/placed and domain/placement and a separate console delete:platform/doors/*.

This is a subject of a manual check of the specification and of a future check of an implementation. The author's prepared requests, reading and finite models are not a performed stand test.

The request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and
deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4; the log of cammeta-go, lesson 8 № 4).

## The coverage audit P/02, second pass (Gemini)

The report the coverage audit Gemini P02 (for people) (branch gemini/audit-coverage, c698f3291): the derivation of rights that was formerly checked by reading —
the variants `v8-worker-writes-deletes` (G04), `v9-asked-free-resource` (G05), `v10-worker-domain-reads` (G06),
`v11-controller-cross-tables` (G07; a separate variant — the manifests of `v6-near-about-ref` do not change). The subjects are above.
`--check` and the generator refusals before the file use the Architect's forms `check.tsv` and `refused` (above). A file that equals the derivation of rights per N1.4 after the Architect's decisions of 2026-10-30 (the norm questions of the Gemini audit, P/02) compares as equal: to the resource — `<M>/<holds.table>/*`
only at a manifest with `holds`, `<s>/holds/*` is not given (item 1, C02-RESOURCE-HOLDS-TABLE-01); the negation of a secret to a non-reader — only
if after the negations already given its rights still reach the pattern (item 2, C02-NONREADER-DENY-AFTER-01); the marks
`objects/<s>/commands/*` of the console — only at a manifest with `requests` (as at the worker). What remains by reading: the inequality
of the secret readers (cannot be built from the manifests of the catalogue: the readers are derived from the same declarations) and `CLUSTER=` (an input
of the environment, not of the catalogue of the variant).

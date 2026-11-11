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

The format is [the dictionary of directives and doors of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): a door without a prefix is the store of P/01.1, a step goes from the role of `@as <role>`; the expectation `<code> <JSON>` is a subset of fields, and every answer is also judged by the full form of the store door (P/01): `403` is exactly the strings `{kind: "forbidden", error}`, 200 is the form of `Row` or `Written` of P/01.1. The bindings and the order of arrays follow the same dictionary.

The roles of the scenarios: `console`, `testsubcontroller`, `testsubworker`, `testsub2controller`, `testsub2worker`, `resource`;
also the domain roles `testsubdomain` and `domainagent` (a domain role `<s>domain` exists only at a manifest with `domain.kept` or a transferable
book, P/02.5 N1.4).

The reconciliation of python and go M10/6–11 (R1–R5, R7) is part of these scenarios.

## Isolation

Each scenario, including a repeated run, gets a separate instance with empty
application rows and an empty id replay memory. Clearing the prefixes does not substitute for clearing this
memory. The bindings `$name` are reset, the role is set by the first `@as`; the rights file is the same
in all scenarios. Parallel runs do not share an instance.

The background consoles, controllers, workers and the resource do not write into these rows. The permission data
is prepared by the judge through the generator and the instance setup, and each step is executed only by
the named role. A read right is checked without creating the row:
an allowed read of an absent row returns Row with items null per chapter P/01.1.

## Manifest variants (`variants/`)

The derivation of rights by meaning on manifests outside the stand (the reconciliation of python and go M10/6–11: R2–R8, R10, R12; registry line e31e5c28). The directories `variants/<variant>/` are run by the engine word `variants` in the form «[Rights variants](../../../common/acceptance/README.md#rights-variants)» of the common acceptance README: the files of a variant, `expect.tsv`, `refused`, `check.tsv` with `check/`, the calls of `stand.rights` and `stand.rights-check` with the deployment `dep` and what counts as `allow` and `deny` are defined there. The forms of `refused` and `check.tsv` are the Architect's decision on the question of the form (the Gemini audit P/02, properties 24, 25). The comparison of `check.tsv` by meaning is N3 «install»: the set of roles, for each one `group` and the sets of patterns `read`, `write`, `delete` (no `delete` — an empty set); `comment`, order, repeats and spaces are not compared; a file not by the form of P/01.2 N1.2 diverges.

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
| the two kept admission rows of the controller: read and write without delete; the console and the worker only read them; the other deletions of the controller stay | P/02.5 N5 with P/04 N1.5 (`v1-base`) |
| the roles keep the full manifest name and the suffix at the longest name whose controller group fits 32 characters | P/02.5 N1.4, N3 step 1; P/02.4 N1.1 (`v15-name18-roles`) |
| an exact secret key closes one row, a secret prefix only the rows under the slash; the neighbours keep the ordinary rights | P/02.5 N1.3, N1.4, N3 step 4 (`v5-secret-domainworker`, `v16-secret-prefix`) |

The manifests of the variants `v1`–`v5` come from the reconciliation of python and go M10/6–11; `v6-near-about-ref` — the Architect's decision of 2026-10-27; `v7-must-match` — the coverage audit P/02 (audit-kimi 2026-10-30, commit 82f4da9fc). `v8`–`v14` — the coverage audit P/02, second pass (Gemini, c698f3291; below). `v15-name18-roles`, `v16-secret-prefix` and the admission probes of `v1-base` — the readiness audit of P/02 (P02.20).

## Not judged in this lesson

- The checks of `/v1/rights`, of the rights file form, of the evaluator, of `never`, of forwarding and of the internal admin (P/01.2 N1.3: admin is not a role of the rights file and is not added to `secrets.readers`) — in the acceptance of P/01.2 (stage B).
- The roles of a manifest name of 19–32 characters: such a catalogue is refused at the installation by the OS names (P/02.4 N1.1 `users_groups` names; the row `os_name_sub_len_33` of the acceptance of chapter 2.3), so the rights derivation over it is checked by reading the function, without OS names (C02-NAME32-ROLES-01).
- The declarations `<s>/vault*`, `<s>/va*ult/`, `!<s>/vault` and `delete:<s>/vault` of run 32 are a load refusal by the form of `secrets.readers` (P/02.1 N1, P/02.5 N1.3 `rule`, N4 row 3); the corpus of chapter 2.1 has no case for them yet. The store keys themselves may hold a literal `*` (P/01.1 Key/Listing).
- The inequality of the secret readers (it cannot be built from the manifests of a catalogue: the readers are derived from the same declarations) and `CLUSTER=` (an input of the environment, not of the catalogue of the variant).
- The TLS key belongs to the user of the unit or to root with the group of the user of the unit (ADR-0075 addendum 3), the group of a role socket gives no access to the key; the socket modes and the certificate — the stage of the system.

The check R36-05 (since 2026-10-30 — cases of the acceptance of chapter 2.1; the coverage audit P/02, B06): worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

The generator keeps both families `domain/placed` and `domain/placement` (`v10-worker-domain-reads`) and a separate console `delete:platform/doors/*` (`v1-base`). The request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4; the log of cammeta-go, lesson 8 № 4) — scenario 11 and `v2-requests`.

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

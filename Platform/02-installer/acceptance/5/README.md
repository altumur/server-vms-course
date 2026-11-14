# Acceptance P/02.5 — the derivation of rights through the store door

This English text is the source; the Russian translation `ru/acceptance/5/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.5-installer.norms.md`](../../spec/02.5-installer.norms.md) N5, the full bodies of the two routes are
[the OpenAPI](../../../01-store/spec/01-store.api.openapi.yaml) of lesson P/01.
The file has 8 scenarios / 70 steps; the roles and the rights file are generated from `testsub` and `testsub2`
(`Platform/common/data/testsub/testsub*.subsystem.yaml`) with the deployment name `dep` (`{deployment}` = `dep` of the rights derivation command `stand.rights`).
The evaluator, `never`, listing, the guard, identity and `/v1/rights` follow [P/01.2](../../../01-store/spec/01.2-store.norms.md).

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). `stand.rights` consumes `{manifests}`, `{deployment}` and output `{file}` and derives the rights file by this chapter's algorithm; refusals and file absence are those below. `stand.rights-check` consumes the same manifest/deployment inputs and the existing `{file}` to compare, without writing it; zero means semantic equality, nonzero means disagreement. `stand.ring` and `stand.manifest-put` prepare the existing common stand as assigned there; the selected `01-store` profile owns the store process and its role sockets. The implementation chooses the commands and flags for these interfaces. Missing comparison coverage remains unexecuted, not a generated substitute result.

- **Rights check command** (P/02.5 N2 `--check`, N3 «install») — the key `stand.rights-check` of the profile `02-installer`, a template with
  the same substitutions as the rights derivation command (`stand.rights`): `{manifests}` — the directory of the manifests, `{deployment}`, `{file}` —
  the rights file that is checked (not written); the outcome is the code: 0 — the file is equal in meaning to the rights derived from the manifests, another — they differ.
  The acceptance variants of P/02.5 with `check.tsv` (judge-only: the case table of a variant) call it for each case with the manifest directory of the variant, `{deployment}` = `dep` and
  `{file}` = `check/<case>.rights`; the code is compared with the column `code` (`0` | `!0`). There is no key in the profile — the cases of `check.tsv` (judge-only: the case table of a variant)
  are not executed (not GREEN and not an outcome of the implementation). There is no substitution `{specs}` in the stand vocabulary.

## scenarios.tsv

The format is [the dictionary of directives and doors of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): a door without a prefix is the store of P/01.1, a step goes from the role of `@as <role>`; the expectation `<code> <JSON>` is a subset of fields, and every answer is also judged by the full form of the store door (P/01): `403` is exactly the strings `{kind: "forbidden", error}`, 200 is the form of `Row` or `Written` of P/01.1. The bindings and the order of arrays follow the same dictionary.

The roles of the scenarios: `console`, `testsubcontroller`, `testsubworker`, `testsub2controller`, `testsub2worker`, `resource`;
also the domain roles `testsubdomain` and `domainagent` (a domain role `<s>domain` exists only at a manifest with `domain.kept` or a transferable
book, P/02.5 N1.4).

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

The derivation of rights by meaning on manifests outside the stand. The directories `variants/<variant>/` are run by the engine word `variants` in the form «[Rights variants](../../../common/acceptance/command-tables.md#rights-variants)» of the common acceptance README: the files of a variant, `expect.tsv`, `refused`, `check.tsv` with `check/`, the calls of `stand.rights` and `stand.rights-check` with the deployment `dep` and what counts as `allow` and `deny` are defined there (judge-only: `expect.tsv`, `check.tsv` and `check/` of each variant). The comparison of `check.tsv` (judge-only: the `check.tsv` of `v12-check-rights`) by meaning is N3 «install»: the set of roles, for each one `group` and the sets of patterns `read`, `write`, `delete` (no `delete` — an empty set); `comment`, order, repeats and spaces are not compared; a file not by the form of P/01.2 N1.2 diverges.

The variants and their expected outcomes are in the judge's case data. They cover these subjects:

| Subject | Norm |
|---|---|
| the roles of the platform and of a manifest; the console family `requests/*`; an empty `<y>` and `never` of the epoch; `retention` of the resource; `domain/grants`, `domain/view` and `domain/holder`; `door/signer` without a declaration in a manifest | P/02.5 N1.4 (the domain trace P/06.3 N1.8) |
| the submission of a worker into the requests of another manifest and the marks `objects/<s>/commands/*` | P/02.5 N1.4 `console`, `<s>worker` |
| the family of an entry of `objects.rows` | P/02.5 N1.4 `<s>worker` |
| the slot and `kept` of the role `<s>domain`; `domainagent` by the form of the declaration | P/02.5 N1.4a `<s>domain`, `domainagent` |
| the reads of a linked controller by the catalogue; there is no reverse link | P/02.5 N1.4 `<s>controller`; P/03.6 sc. 07 |
| the reads of a customer on the targets of the row check, on the direct and the reverse branch of `must_match`; its writes by `worker.creates` | P/02.5 N1.4 `<s>worker` «reads of the common row check»; the row check contract |
| the tables of `worker.writes` and `worker.deletes` next to an ordinary table | P/02.5 N1.4 `console`, `<s>worker`, N3 step 2 |
| `<s>/asked/*`, the requests `free-*` and `holds.table` for the console and the resource | P/02.5 N1.4 the general rules, `console`, `resource`; the holds contract |
| `worker.reads` of `domain/placed/<s>/`, the copy of the own book, the sources of collected books, `domain/shared` and the topology rows | P/02.5 N1.4 `<s>worker`, N2, N3 step 3 |
| a linked controller on the tables of another manifest | P/02.5 N1.4 `<s>controller` |
| `--check` against the derivation of rights per N1.4 | P/02.5 N1.4, N2, N3 step 4, «install», N4 |
| a declaration that directly names a row inside `<s>/idem/`: a generation refusal before the file | P/02.5 N1.4 the general rules, N4 |
| an element of `secrets.reads` strictly nested in a secret prefix of another manifest: a generation refusal before the file | P/02.5 N3 step 4, N4 |
| `secrets.readers` with `domainworker` | P/02.5 N1.3, N1.4 (the words of `secrets.readers`) |
| the two kept admission rows of the controller: read and write without delete; the console and the worker only read them; the other deletions of the controller stay | P/02.5 N5 with P/04 N1.5 (`v1-base`) |
| the roles keep the full manifest name and the suffix at the longest name whose controller group fits 32 characters | P/02.5 N1.4, N3 step 1; P/02.4 N1.1 (`v15-name18-roles`) |
| an exact secret key closes one row, a secret prefix only the rows under the slash; the neighbours keep the ordinary rights | P/02.5 N1.3, N1.4, N3 step 4 (`v5-secret-domainworker`, `v16-secret-prefix`) |
| effective write and delete exclusions of domainagent over the catalogue's holder families, including `folders`, `memberof`, `folder-rev`; nearby keys and the exact member copies remain allowed | P/02.5-R062 (`v1-base`) |
| only `secrets.reads` of an exact transferable book copy adds the one holder row for the effective cluster, without widening to the book prefix | P/02.5-R082 (`v17-secret-own-book`) |
| nested `secrets.readers` prefixes across two individually valid manifests refuse even with equal readers; disjoint neighboring prefixes remain valid | P/02.5-R023/R087 (`v18-refused-secret-readers-nested`, `v19-secret-readers-neighbours`) |

## Not judged in this lesson

- The checks of `/v1/rights`, of the rights file form, of the evaluator, of `never`, of forwarding and of the internal admin (P/01.2 N1.3: admin is not a role of the rights file and is not added to `secrets.readers`) — in the acceptance of P/01.2.
- The roles of a manifest name of 19–32 characters: such a catalogue is refused at the installation by the OS names (P/02.4 N1.1 `users_groups` names; the row `os_name_sub_len_33` of the acceptance of chapter 2.3), so the rights derivation over it is checked by reading the function, without OS names.
- The declarations `<s>/vault*`, `<s>/va*ult/`, `!<s>/vault` and `delete:<s>/vault` are a load refusal by the form of `secrets.readers` (P/02.1 N1, P/02.5 N1.3 `rule`, N4 row 3); they are the cases `r32_secrets_readers_*` of the corpus of chapter 2.1. The store keys themselves may hold a literal `*` (P/01.1 Key/Listing).
- The inequality of the secret readers (it cannot be built from the manifests of a catalogue: the readers are derived from the same declarations) and `CLUSTER=` (an input of the environment, not of the catalogue of the variant).
- The TLS key belongs to the user of the unit or to root with the group of the user of the unit, the group of a role socket gives no access to the key; the socket modes and the certificate — the stage of the system.

The cases of the acceptance of chapter 2.1 check: worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

The generator keeps both families `domain/placed` and `domain/placement` (`v10-worker-domain-reads`) and a separate console `delete:platform/doors/*` (`v1-base`). The request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4) — scenario 11 and `v2-requests`.

## Properties of variants v8–v11

The derivation of rights checked by the variants `v8-worker-writes-deletes`, `v9-asked-free-resource`, `v10-worker-domain-reads`,
`v11-controller-cross-tables` (a separate variant — the manifests of `v6-near-about-ref` do not change). The subjects are above.
`--check` and the generator refusals before the file use the forms `check.tsv` and `refused` (above; judge-only: `check.tsv` and `refused` of `v12-check-rights`, `v13-refused-idem-read`, `v14-refused-secrets-reads-nested`, `v18-refused-secret-readers-nested`). A file that equals the derivation of rights per N1.4 compares as equal: to the resource — `<M>/<holds.table>/*`
only at a manifest with `holds`, `<s>/holds/*` is not given; the negation of a secret to a non-reader — only
if after the negations already given its rights still reach the pattern; the marks
`objects/<s>/commands/*` of the console — only at a manifest with `requests` (as at the worker). What remains by reading: the inequality
of the secret readers (cannot be built from the manifests of the catalogue: the readers are derived from the same declarations) and `CLUSTER=` (an input
of the environment, not of the catalogue of the variant).

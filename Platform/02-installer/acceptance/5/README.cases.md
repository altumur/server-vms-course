# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/5/README.cases.md` is derived from it.

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

The file has 8 scenarios / 70 steps (sc. 12 steps 12–18 — `domainagent` does not write `domain/root`, `view`, `shadow`, `backups/rev-1`, `shared-docs/rev-1`, `alarm-history/m1`, `idem/k1`, 403; the admission rows of the controller without delete, the negation of `idem` at the worker; sc. 13 — the order and the state, sc. 02 step 8 — the deletion of a row of `testsub2` by the controller is 200: it has `retire_when.delete_after` and `ends`); the roles and the rights file are generated from `testsub` and `testsub2`

### Original passage 2

Sc. 04 steps 4–7 — the resource reads the terms of both manifests (there are no rows: `items:
null`); sc. 12 — the domain roles.

### Original passage 3

the named role. Scenario 09 checks the read right of door/signer: the row need not be created,
an allowed read of an absent row returns Row with items null per chapter P/01.1.

### Original passage 4

| Variant | Manifests | What it checks |
|---|---|---|
| `v1-base` | `va` without `requests`, with `delete_after` | the roles of the platform and of the manifest; the two kept admission rows `va/controller/placement_turn` and `va/controller/placement_intent`: `vacontroller` reads and writes them without delete, `console` and `vaworker` only read them, the deletions of `workers`, `placement`, `slots`, `decommissioned` stay (P/02.5 N5, P/04 N1.5); there is no console `requests/*`; an empty `<y>` and `never` of the epoch; `retention` of the resource; `domain/grants` of the console — the exact key and the family `domain/grants/*` (`domain/grants/c1` — yes: the domain trace P/06.3 N1.8), `domain/view` — no; `domain/holder` of the worker; there is no role `vadomain`; `door/signer` is read by the console, not by the worker, without a declaration in the manifest |
| `v2-requests` | `va` with `requests`, `vb` with `worker.requests: [va]` | the console `requests/*` only at `va`; the submission of `vbworker` into `va`; the marks `objects/va/commands/*` |
| `v3-objects-rows` | `va` with `objects.rows: [marks/]` | `marks/` → `objects/va/marks/*` |
| `v4-domain-kept` | `va` with `domain.kept: [ledger, badges/]` | `vadomain` writes the slot and `kept`; `domainagent` — by the form of the declaration and without the slot and the pulse of the worker on the domain |
| `v6-near-about-ref` | `va`; `vb` with `placement.near.sub: va`, `vc` with `about.sub: va`, `vd` with the field `ref: va/items` | the controller reads the rows of `va` by the catalogue (`placement`, `workers`, `slots`, `holds`, unit rows, `policy`, `placement_turn`), not the epoch, `idem`, `next_id`, and does not write; there is no reverse link (P/03.6 sc. 07) |
| `v7-must-match` | `va` (the field `shelf` — `ref: va/shelves`, `must_match: {zone: zone}`; the table `shelves`); `vb` with `worker.creates` on `va/items` (`key: "{code}"`); `vc` with the table `links`, the field `of` — `ref: va/items`, `must_match: {zone: zone}` | the customer `vbworker` reads the targets of the row check — `va/shelves/*` (the direct branch) and `vc/links/*` (the reverse branch of `must_match`), writes only `va/items/vb-*` without deletion; foreign rows of `va/items` and the other families of `vc` — no; the controller of `va` does not read the reverse family | P/02.5 N1.4 `<s>worker` «reads of the common row check»; the row check contract |
| `v8-worker-writes-deletes` | `va` with the tables `shelves`, `gauges`, `worker.writes: [gauges]`, `worker.deletes: [items]` | the table of `worker.writes`: the worker writes, reads and deletes, the console reads and only deletes; an ordinary table: the console writes and deletes, the worker only reads; `worker.deletes`: the worker deletes unit rows without a write, the controller without `delete_after` — no | P/02.5 N1.4 `console`, `<s>worker`, N3 step 2 |
| `v9-asked-free-resource` | `va` with `requests` without `per_person` and `free`; `vb` with `about.sub: va`, the tables `notches` (`holds.table`) and `shelves`, `requests` with `per_person` and `free: true` | the console writes `vb/asked/*`, not `va/asked/*`; `!vb/asked/*` at the worker and the controller of `vb`; the resource writes, reads, deletes `vb/requests/free-*`, not `vb/requests/<rid>` and not `va/requests/free-*`; the resource reads the table `holds.table` (`vb/notches/*`) and the unit rows of the manifest with `about` (`vb/things/*`), not other tables, not the rows of `va` without `about` and not the place family `<s>/holds/*` either at `vb` or at `va` (the holds contract) | P/02.5 N1.4 the general rules, `console`, `resource` |
| `v10-worker-domain-reads` | `va` with `worker.reads: [domain/placed/va/, domain/va/tallies]`, the books `tallies` (transferable), `notes` (`from: va/notes/`), `rolls` (`from: va/rolls`), `domain.shared`, a token kind with `unit`, `door.routes`; `vb` without them | `domain/placed/va/` gives also `domain/placement/va/*`; the copy of its own book — also the exact key `domain/va/tallies/local` (`CLUSTER` is not set — `local`), not a prefix; the write of the sources of collected books — a prefix and an exact key; `domain/shared`, `domain/topology`, `domain/member-topology`, `domain/grants` — only at `vaworker` | P/02.5 N1.4 `<s>worker`, N2, N3 step 3 |
| `v11-controller-cross-tables` | `vb`, `vc`, `vd` — as in `v6-near-about-ref`; `va` with the table `shelves` and `requests` (`per_person`) | the controller of a linked subsystem reads the tables of `va`, `va/decommissioned/*`, `va/controller/placement_intent`, does not read `va/requests/*`, `va/asked/*` and does not write the table of `va` | P/02.5 N1.4 `<s>controller` |
| `v12-check-rights` | `va` — byte for byte `v1-base`; `check.tsv` | `--check`: exactly the derivation of rights per N1.4 (`same`) — code 0; a derivation without the role `vaworker`, with a write of unit rows by the worker, with another worker group, without `delete` of the controller, with an extra field of the file — the code is not 0 | P/02.5 N1.4, N2, N3 step 4, «install», N4 |
| `v13-refused-idem-read` | `va` — byte for byte `v2-requests`; `vb` with `worker.reads: [va/idem/k1]`; `refused` | a declaration of the worker directly names a row inside `va/idem/` — a generation refusal before the file, code 2, the manifest `vb` | P/02.5 N1.4 the general rules, N4 |
| `v14-refused-secrets-reads-nested` | `va` with `secrets.readers: {va/vault/: [worker]}`; `vb` with `secrets.reads: [va/vault/public/]`; `refused` | an element of `secrets.reads` is strictly nested in a secret prefix of another manifest — a generation refusal before the file, code 2, the manifest `vb` | P/02.5 N3 step 4, N4 |
| `v5-secret-domainworker` | `va` with `secrets.readers: {va/vault: [domainworker]}` and `kept` | `domainworker` → `vadomain` reads, the others — no; the neighbours `va/vault2` and `va/vault/nested` keep the ordinary reads of `console` and `vaworker` (P/02.5 N1.3) |
| `v15-name18-roles` | `s12345678901234567` (18 characters) — byte for byte `v1-base` except the name and `worker.exec` | the roles `s12345678901234567worker` and `s12345678901234567controller` keep the full name: the worker writes its slot and reads the unit rows, does not write them; the controller writes the placement, not the unit rows; the console writes the unit rows (P/02.5 N1.4, N3 step 1) |
| `v16-secret-prefix` | `va` — byte for byte `va` of `v14-refused-secrets-reads-nested`: `secrets.readers: {va/vault/: [worker]}` | the prefix closes only the rows under the slash: `vaworker` reads `va/vault/x`, `console` and `vacontroller` — no; `va/vault` and `va/vault2` keep the ordinary reads of `console` (P/02.5 N1.3, N1.4, N3 step 4) |
| `v17-secret-own-book` | `testsub` declares the exact and prefix secret of transferable book `tallies`; `testsub2` has only `secrets.reads` of the copy | `testsub2worker` reads the exact copy and `domain/testsub/tallies/local` (unset CLUSTER), not another member or a descendant, and cannot write/delete the holder row (P/02.5-R082) |
| `v18-refused-secret-readers-nested` | `testsub` declares `shared/`, `testsub2` declares `shared/x/`, both with reader resource | code 2 before the output file, diagnostic names `testsub2`; equal readers do not make nested declarations representable (P/02.5-R023/R087) |
| `v19-secret-readers-neighbours` | same manifests with the second prefix changed to `sharedx/` | derivation succeeds and resource reads both prefixes, the positive neighbor control of the nested-declaration refusal (P/02.5-R023/R087) |

`v1-base` also probes domainagent write and delete separately over every effective exclusion retained in the domain-role derivation: exact keys and families, with the member-copy exceptions. The concrete folder keys `domain/folders/f1`, `domain/memberof/local/va/items/u1`, `domain/folder-rev` are denied; `domain/folders-state`, `domain/revoked`, the exact `domain/roles`, `domain/grants`, `domain/outcomes` and nearby `foldersx`, `memberofx`, `folder-revx` are admitted. Thus a blanket prefix exclusion is not a passing replacement for the catalogue rule. The 200 probes observe effective rights; `v12-check-rights` separately compares the rights file by meaning.

### Original passage 5

The cases `worker_writes_unit_rows`, `worker_writes_undeclared` — refused, `worker_writes_declared_ok`, `worker_writes_declared_list_ok` — ok of the acceptance of chapter 2.1 check: worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

### Original passage 6

Scenario 11 — the request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and
deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4).

### Original passage 7

`--check` and the generator refusals before the file — the forms `check.tsv` and `refused` (above): `v12-check-rights`,
`v13-refused-idem-read`, `v14-refused-secrets-reads-nested`, `v18-refused-secret-readers-nested`. The case of `check.tsv` with the code `0` is `same` of the variant `v12-check-rights`:
exactly the derivation of rights per N1.4: to the resource — `<M>/<holds.table>/*`
only at a manifest with `holds`, `<s>/holds/*` is not given; the negation of a secret to a non-reader — only
if after the negations already given its rights still reach the pattern; the marks
`objects/<s>/commands/*` of the console — only at a manifest with `requests` (as at the worker; `va` has none). The other files of `check/` are this derivation with
one edit. What remains by reading: the inequality

### Original passage 8

sc. 12 — also `testsubdomain` and `domainagent` (the domain roles of the rights file `testsub`: `testsub` has `kept` and a transferable
book `tallies`, `testsub2` has only collected books — there is no role `testsub2domain` and no socket).

### Original passage 9



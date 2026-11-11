# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/5/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

The file has 8 scenarios / 70 steps (sc. 12 steps 12–18 — `domainagent` does not write `domain/root`, `view`, `shadow`, `backups/rev-1`, `shared-docs/rev-1`, `alarm-history/m1`, `idem/k1`, 403, C02-LOCAL-BINDING240-ROOT; the mutation check 7cecaf2 № 29, 49: the admission rows of the controller without delete, the negation of `idem` at the worker; sc. 13 — the order and the state, ADR-0091, sc. 02 step 8 — the deletion of a row of `testsub2` by the controller is now 200: it has `retire_when.delete_after` and `ends`); the roles and the rights file are generated from `testsub` and `testsub2`

### Original passage 2

The reconciliation of python and go M10/6–11 (R1–R5, R7): sc. 04 steps 4–7 — the resource reads the terms of both manifests (there are no rows: `items:
null`); sc. 12 — the domain roles.

### Original passage 3

the named role. Scenario 09 checks the read right of door/signer: the row need not be created,
an allowed read of an absent row returns Row with items null per chapter P/01.1.

### Original passage 4

| Variant | Manifests | What it checks |
|---|---|---|
| `v1-base` | `va` without `requests`, with `delete_after` | the roles of the platform and of the manifest; the two kept admission rows `va/controller/placement_turn` and `va/controller/placement_intent`: `vacontroller` reads and writes them without delete, `console` and `vaworker` only read them, the deletions of `workers`, `placement`, `slots`, `decommissioned` stay (P/02.5 N5, P/04 N1.5); there is no console `requests/*` (R8); an empty `<y>` and `never` of the epoch (R12); `retention` of the resource (R2); `domain/grants` of the console — the exact key and the family `domain/grants/*` (`domain/grants/c1` — yes: the domain trace P/06.3 N1.8; review analysis of stage A 8–10, plan 8 V7, a behaviour change), `domain/view` — no (R5); `domain/holder` of the worker (R7); there is no role `vadomain`; `door/signer` is read by the console, not by the worker, without a declaration in the manifest (review analysis of stage B 6–7, № 36) |
| `v2-requests` | `va` with `requests`, `vb` with `worker.requests: [va]` | the console `requests/*` only at `va`; the submission of `vbworker` into `va`; the marks `objects/va/commands/*` (R8, R9) |
| `v3-objects-rows` | `va` with `objects.rows: [marks/]` | `marks/` → `objects/va/marks/*` (R10) |
| `v4-domain-kept` | `va` with `domain.kept: [ledger, badges/]` | `vadomain` writes the slot and `kept`; `domainagent` — by the form of the declaration and without the slot and the pulse of the worker on the domain (R4, R3) |
| `v6-near-about-ref` | `va`; `vb` with `placement.near.sub: va`, `vc` with `about.sub: va`, `vd` with the field `ref: va/items` | the controller reads the rows of `va` by the catalogue (`placement`, `workers`, `slots`, `holds`, unit rows, `policy`, `placement_turn`), not the epoch, `idem`, `next_id`, and does not write; there is no reverse link (the Architect's decision of 2026-10-27; P/03 Go 084a3ee9, P/03.6 sc. 07) |
| `v7-must-match` | `va` (the field `shelf` — `ref: va/shelves`, `must_match: {zone: zone}`; the table `shelves`); `vb` with `worker.creates` on `va/items` (`key: "{code}"`); `vc` with the table `links`, the field `of` — `ref: va/items`, `must_match: {zone: zone}` | the customer `vbworker` reads the targets of the row check — `va/shelves/*` (the direct branch) and `vc/links/*` (the reverse branch of `must_match`), writes only `va/items/vb-*` without deletion; foreign rows of `va/items` and the other families of `vc` — no; the controller of `va` does not read the reverse family (the coverage audit P/02, B07) | P/02.5 N1.4 `<s>worker` «reads of the common row check»; the row check contract |
| `v8-worker-writes-deletes` | `va` with the tables `shelves`, `gauges`, `worker.writes: [gauges]`, `worker.deletes: [items]` | the table of `worker.writes`: the worker writes, reads and deletes, the console reads and only deletes; an ordinary table: the console writes and deletes, the worker only reads; `worker.deletes`: the worker deletes unit rows without a write, the controller without `delete_after` — no (the coverage audit P/02, second pass) | P/02.5 N1.4 `console`, `<s>worker`, N3 step 2 |
| `v9-asked-free-resource` | `va` with `requests` without `per_person` and `free`; `vb` with `about.sub: va`, the tables `notches` (`holds.table`) and `shelves`, `requests` with `per_person` and `free: true` | the console writes `vb/asked/*`, not `va/asked/*`; `!vb/asked/*` at the worker and the controller of `vb`; the resource writes, reads, deletes `vb/requests/free-*`, not `vb/requests/<rid>` and not `va/requests/free-*`; the resource reads the table `holds.table` (`vb/notches/*`) and the unit rows of the manifest with `about` (`vb/things/*`), not other tables, not the rows of `va` without `about` and not the place family `<s>/holds/*` either at `vb` or at `va` (the holds contract; C02-RESOURCE-HOLDS-TABLE-01) (ibid.) | P/02.5 N1.4 the general rules, `console`, `resource` |
| `v10-worker-domain-reads` | `va` with `worker.reads: [domain/placed/va/, domain/va/tallies]`, the books `tallies` (transferable), `notes` (`from: va/notes/`), `rolls` (`from: va/rolls`), `domain.shared`, a token kind with `unit`, `door.routes`; `vb` without them | `domain/placed/va/` gives also `domain/placement/va/*`; the copy of its own book — also the exact key `domain/va/tallies/local` (`CLUSTER` is not set — `local`), not a prefix; the write of the sources of collected books — a prefix and an exact key; `domain/shared`, `domain/topology`, `domain/member-topology`, `domain/grants` — only at `vaworker` (ibid.) | P/02.5 N1.4 `<s>worker`, N2, N3 step 3 (C02-OWN-BOOK-HOLDER-01) |
| `v11-controller-cross-tables` | `vb`, `vc`, `vd` — as in `v6-near-about-ref`; `va` with the table `shelves` and `requests` (`per_person`) | the controller of a linked subsystem reads the tables of `va`, `va/decommissioned/*`, `va/controller/placement_intent`, does not read `va/requests/*`, `va/asked/*` and does not write the table of `va` (ibid.) | P/02.5 N1.4 `<s>controller` (the Architect's decision of 2026-10-27) |
| `v12-check-rights` | `va` — byte for byte `v1-base`; `check.tsv` | `--check`: exactly the derivation of rights per N1.4 (`same`) — code 0; a derivation without the role `vaworker`, with a write of unit rows by the worker, with another worker group, without `delete` of the controller, with an extra field of the file — the code is not 0 (the Gemini audit P/02, property 24; `same` — the Architect's decisions of 2026-10-30, P/02 items 1, 2) | P/02.5 N1.4, N2, N3 step 4, «install», N4 |
| `v13-refused-idem-read` | `va` — byte for byte `v2-requests`; `vb` with `worker.reads: [va/idem/k1]`; `refused` | a declaration of the worker directly names a row inside `va/idem/` — a generation refusal before the file, code 2, the manifest `vb` (property 25) | P/02.5 N1.4 the general rules, N4 (C02-IDEM-ASKED-EXPLICIT-READ-01) |
| `v14-refused-secrets-reads-nested` | `va` with `secrets.readers: {va/vault/: [worker]}`; `vb` with `secrets.reads: [va/vault/public/]`; `refused` | an element of `secrets.reads` is strictly nested in a secret prefix of another manifest — a generation refusal before the file, code 2, the manifest `vb` (property 25) | P/02.5 N3 step 4, N4 (C02-SECRETS-READS-INTERSECTION-01) |
| `v5-secret-domainworker` | `va` with `secrets.readers: {va/vault: [domainworker]}` and `kept` | `domainworker` → `vadomain` reads, the others — no (R6); the neighbours `va/vault2` and `va/vault/nested` keep the ordinary reads of `console` and `vaworker` (P/02.5 N1.3) |
| `v15-name18-roles` | `s12345678901234567` (18 characters) — byte for byte `v1-base` except the name and `worker.exec` | the roles `s12345678901234567worker` and `s12345678901234567controller` keep the full name: the worker writes its slot and reads the unit rows, does not write them; the controller writes the placement, not the unit rows; the console writes the unit rows (P/02.5 N1.4, N3 step 1; C02-NAME32-ROLES-01) |
| `v16-secret-prefix` | `va` — byte for byte `va` of `v14-refused-secrets-reads-nested`: `secrets.readers: {va/vault/: [worker]}` | the prefix closes only the rows under the slash: `vaworker` reads `va/vault/x`, `console` and `vacontroller` — no; `va/vault` and `va/vault2` keep the ordinary reads of `console` (P/02.5 N1.3, N1.4, N3 step 4) |

### Original passage 5

The check R36-05 (since 2026-10-30 — the cases `worker_writes_unit_rows`, `worker_writes_undeclared` — refused, `worker_writes_declared_ok`, `worker_writes_declared_list_ok` — ok of the acceptance of chapter 2.1; the coverage audit P/02, B06): worker.writes with the name of its own unit.rows gives refused:reference, without generating rights. A declared table of the worker is admissible, console only reads it; this does not extend to a unit row. Compare all common manifests and all generator paths, including the list form of tables; the current TSV has no loader run on such a changed manifest.

### Original passage 6

Scenario 11 — the request marks `objects/<s>/commands/*` (P/06.4 N1.5 mark): the worker of a manifest with `requests` writes, reads and
deletes its own, of a foreign manifest — 403, the controller — 403 (N1.4; the log of cammeta-go, lesson 8 № 4).

### Original passage 7

`--check` and the generator refusals before the file — the Architect's forms `check.tsv` and `refused` (above): `v12-check-rights`,
`v13-refused-idem-read`, `v14-refused-secrets-reads-nested`. The case of `check.tsv` with the code `0` is `same` of the variant `v12-check-rights`:
exactly the derivation of rights per N1.4 after the Architect's decisions of 2026-10-30 (the norm questions of the Gemini audit, P/02): to the resource — `<M>/<holds.table>/*`
only at a manifest with `holds`, `<s>/holds/*` is not given (item 1, C02-RESOURCE-HOLDS-TABLE-01); the negation of a secret to a non-reader — only
if after the negations already given its rights still reach the pattern (item 2, C02-NONREADER-DENY-AFTER-01); the marks
`objects/<s>/commands/*` of the console — only at a manifest with `requests` (as at the worker; `va` has none). The other files of `check/` are this derivation with
one edit. What remains by reading: the inequality

### Original passage 8

sc. 12 — also `testsubdomain` and `domainagent` (the domain roles of the rights file `testsub`: `testsub` has `kept` and a transferable
book `tallies`, `testsub2` has only collected books — there is no role `testsub2domain` and no socket).

### Original passage 9

The manifests of the variants `v1`–`v5` are byte for byte those on which the reconciliation generated the rights of both implementations — both load them; `v6-near-about-ref` — the Architect's decision of 2026-10-27; `v7-must-match` — the coverage audit P/02 (audit-kimi 2026-10-30, commit 82f4da9fc). `v8`–`v14` — the coverage audit P/02, second pass (Gemini, c698f3291; below).

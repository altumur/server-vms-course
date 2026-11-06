# P/02 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/02-installer.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/02-installer.md` (for people, not in the export).

## Task

Implement the installer of lesson P/02 in the language `<LANG>` by four chapters: strict loading of a manifest and of a manifest catalogue (chapter 2.1),
reading and changing a manifest in the store (chapter 2.3), the units, the runner, the installer and the operator procedures (chapter 2.4), generation of
rights from the manifest catalogue (chapter 2.5). Pass the N5 acceptance of the chapters and close their readiness checklists.

- **2.1.** Implement strict loading of a manifest and of a manifest catalogue per N1–N4 of [chapter 2.1](02.1-installer.norms.md). Pass
  the N5 acceptance by the regular loading path and close the whole [readiness checklist](02.1-installer.norms.md#readiness-checklist).
  The main input of the chapter is the procedure `load(bytes, source)`, not an HTTP door.
- **2.2.** The canonical view of a manifest per [chapter 2.2](02.2-installer.norms.md): the projection of N1.1 (sugar, defaults, the steps P1–P5,
  `ordered`, JCS), the view row of N1.2 and the write of `manifest put` per N3 — the view before the write, above the ceiling — a refusal as a whole, the order
  row — view — mark. Pass the vectors [`canonical`](../vectors/canonical/README.md) byte for byte and the acceptance of the chapter
  [`acceptance/2/`](../acceptance/2/README.md) (window 2.2, item 8: vectors and acceptance).
- **2.3.** Reading and changing a manifest in the store per N1.5 and N3 of [chapter 2.3](02.3-installer.norms.md); close its
  [readiness checklist](02.3-installer.norms.md#readiness-checklist).
- **2.4.** Prepare the processes/units, the runner, the installer and the operator procedures of N1 of [chapter 2.4](02.4-installer.norms.md).
- **2.5.** Generate rights from the manifest catalogue per [chapter 2.5](02.5-installer.norms.md). The rights evaluator, the form of the file and the door
  `/v1/rights` are chapter [P/01.2](../../01-store/spec/01.2-store.norms.md) and its steps of the instructions
  [01-store.README.md](../../01-store/spec/01-store.README.md). The setup of the user, groups, sockets and certificates
  is tied to chapter 2.4: the units of N1.1 (`User=`, `SupplementaryGroups=`), the sockets — P/01.3 N1.3 `sockets`, the kit of N1.6 `kit` and
  the issue by `w2c-ca.sh`.

The lesson has no HTTP contract of its own: the door `GET /manifest` and the form `ManifestView` belong to chapter P/06.5
([norms](../../06-console/spec/06.5-console.norms.md), [instructions](../../06-console/spec/06-console.README.md), [contract](../../06-console/spec/06-console.api.openapi.yaml)).

## Inputs and their priority

| File | Role | Priority |
|---|---|---|
| [02.1-installer.norms.md](02.1-installer.norms.md) | the canon of chapter 2.1: text, document, fields, references, loading passes, refusals and the corpus | 1 |
| [02.1-installer.schema.json](02.1-installer.schema.json), [`.relations.json`](02.1-installer.relations.json), [`.layers.tsv`](02.1-installer.layers.tsv), [`.scalars.tsv`](02.1-installer.scalars.tsv); [the V7 layers](../../common/LAYERS.md) | the form source of chapter 2.1 (ADR-0092): standard files — JSON Schema 2020-12 and CEL, executed by libraries of pinned versions and by own layers; the section «Form» of the chapter norms is built from them | 1 |
| [02.3-installer.norms.md](02.3-installer.norms.md) | the canon of chapter 2.3: the manifest row and the mark, the start and the change, `manifest put` | 1 |
| [02.4-installer.norms.md](02.4-installer.norms.md) | the canon of chapter 2.4: units, environment, workers on order, certificates, installation, operator commands; the late layer — the ports and units of the domain, the installation of the domain (lesson 8) | 1 |
| [02.5-installer.norms.md](02.5-installer.norms.md) | the canon of chapter 2.5: roles and the derivation of rights, the readers of secret rows, generation and `--check` | 1 |
| [The acceptance README of chapter 2.1](../acceptance/1/README.md), `verdicts.tsv`, `diagnostics.tsv`, `classes.tsv`, `cases/` | common inputs, expected verdicts, classes and diagnostic hints | 3 — check the canon, do not add to it |
| [The acceptance README of chapter 2.3](../acceptance/3/README.md), `puts.tsv`, `puts/` | the installations of `manifest put` | 3 — check the canon, do not add to it |
| [The acceptance README of chapter 2.5](../acceptance/5/README.md), `scenarios.tsv`, `variants/`; the stand — [the common README](../../common/acceptance/README.md) | preparing and comparing rights | 3 — check the canon, do not add to it |
| [The vectors of the workers script](../vectors/workers-script/README.md) | rules 2–4 of the workers script (chapter 2.4 N1.5) | 3 |
| [The vectors of the exec command line](../vectors/exec/README.md) | argv of `worker.exec`, `parts.<part name>.exec` (chapter 2.1 `execLine`) | 3 |
| [The vectors of the installation order](../vectors/install-order/README.md) | the order of `manifest put` of the primary installation (chapter 2.4 N1.7 `order`) | 3 |
| [The norms of P/01](../../01-store/spec/01.1-store.norms.md) | the normative words and the store operations for N3 of chapter 2.3; the rights file and the evaluator (P/01.2) for chapter 2.5 | by the references of the canon |
| The grammars of the owner lessons listed in N1.2 of chapter 2.1 | the admissible keys inside the sections of a manifest | by the references of the canon; a consolidated list is not derived from the code of an implementation |
| The lecture (`ru/02-installer.md`, for people, not in the export), [the life cycle](../lifecycle.md) | motivation and examples for a person; a pointer to the flags and units | not a norm |

Read the norms of every chapter in full; this is an input rule, not a separate implementation stage.

The full closed set of keys needs the section grammars named in N1.2 of chapter 2.1. The opaque places
and the levels with author names are set there too; they do not turn the whole document into an arbitrary mapping.
On a gap or a contradiction in the norms, write a question with a reference to the section, pass it to the author of the norms and
do not present a behaviour chosen on one's own as a requirement of the lesson. A JSON check does not prove the correctness of permissions.

## What to create

The mandatory behaviour is in the canon. The internal types, functions, the structure of errors and the choice of libraries remain with
the implementation; the names of the procedures in N2–N3 denote their meaning, not mandatory signatures of a specific language.

Chapter 2.1:

1. **Loading of one manifest** from bytes with a source name: the check of the text, the name, the keys, the values and the references,
   then filling the defaults in the order of N3. The result is a whole manifest or a refusal with the needed information per N4. After the key check, refuse NaN, infinities and float overflow, including nested numbers of opaque/default/inherit; all accepted values are representable in JSON.
2. **Loading of a catalogue** with the checks of `worker.requests` and `placement.near` per N3. The acceptance of one file
   does not substitute for the catalogue check; neighbouring manifests not named by the table are not added to the table runner.
3. **A run of the common table** by the regular loading path according to the acceptance README. The sample of the acceptance README (all `ok` and one refusal
   per class) SHOULD be run through the manifest installation (`manifest put`, chapter 2.3), as stated in N5
   and P/02.1-12.

Chapter 2.3:

4. **Reading and installing a manifest in the store** per N1.5 and N3: the first row with `rev: 1` and `cas: ""`, the mark,
   the digest, a growing revision, a write with `cas`, bringing the mark up to date, the start and stop of processes.
   An invalid file is not installed. On `toolarge` of the main row the command ends with code 2
   with the diagnostics of N4 and does not proceed to the mark; the weight count takes into account the original YAML bytes and the page,
   not only the parsed values. The period of detecting a change is counted from the publication of the mark.

Chapter 2.4:

5. The services and unit files, groups, directories, permissions, sockets and installation configuration described in N1.
6. The runner and the installer with checks before the write and diagnostics of a partial result on a refusal.

Chapter 2.5:

7. The generator and the check `--check`; an executor of scenarios under different roles. The mechanism for issuing certificates and the generator
   of units — chapter 2.4.

For all chapters:

8. **The implementation description** with answers to the 24 items of «Implementation decides» (2.1 — four, 2.2 — two, 2.3 — six, 2.4 — eight, 2.5 —
   four; the struck-out items are already normed — the answer is a reference) and with pointers for those checklist items which
   are checked by reading.

## Order of work

The implementation stages are [`forms/stages.tsv`](../forms/stages.tsv) (ADR-0126): goals, gates, weights, kit parts and dependencies. This is a possible plan, not an additional behavior norm. The advice below complements the table; the readiness checklists keep the obligations that need reading, OS installation or a multi-process stand.

### Chapters 2.1 and 2.3 — the manifest

1. *(2.1)* Write out the boundaries of the closed, named and opaque levels from N1.2,
   their owner lessons and the choices of the implementation. Check the mandatory unit/rows/id: the loader does not invent a family or a kind of id; the absence of unit.fields means an empty mapping.
2. *(2.1)* Set up the reading of bytes and the parsing of the text per N1.1: a YAML 1.2 parser of a pinned version and the fine check of layer 1
   ([the V7 layers](../../common/LAYERS.md) § 4, workarounds D13, D16). Run the checks that need the original text or the list of keys before
   the conversion into a mapping before the library loses this information; one document — by bytes.
3. *(2.1)* Carry out the loading pass of N3 by layers: text → form (the JSON Schema 2020-12 schema and the words `x-*`, the integer place —
   layer 2) → relations (CEL, only with a clean form). Filling the defaults does not hide an erroneous input.
4. *(2.1)* Run `verdicts.tsv`: one file — one load. Compare the set of files with the table;
   count a refusal by the rules of the README, not by any exception or non-zero process code.
   Compare the class of `classes.tsv`; the paths and lines of `diagnostics.tsv` are a hint in the report without a failure (ADR-0092 item 5).
5. *(2.1 — catalogue; 2.3 — storage and change)* Check the catalogue, then the storage and the change of a manifest: a repeated installation without changes, a `cas` conflict,
   a lagging and a missing mark, all the reasons for a start refusal of N4 (including an unconfirmed read of the row/mark and a mismatch of the embedded manifest), a start between two writes of the installer, `toolarge` of the main row
   before the write of the mark. For the catalogue, do not ascribe to the read an atomic snapshot or a mandatory refusal on any
   change of a file: the bytes and relations actually received are checked. The subjects of the check are N3, N5 and the checklist.

### Chapter 2.4 — the installer

1. Match the roles, groups, directories, permissions, sockets and environment to each row of N1.1–N1.2. Check the priority of values and the absence of source for data; do not count After as readiness (N3).
2. Design the preliminary check and the write points of the installer. Force a refusal at each phase: before the write there are no changes, after the start a partial result with diagnostics is admissible and without enable/start of new services (N1.7).
3. Check the script of workers on order: budgets, reservation before start, numbers 2…99 (start of the smallest, stop of the largest), no series — nothing, an unknown outcome of a start and a stale console, polkit start/stop of the full names of its own server (ADR-0084). Certificates — a separate test CA, revocation before concluding a full cut-off (N1.5–N1.6).
4. The role certificate (SAN URI `urn:w2c:role:<role>`, CN `<role>.<server>`, the key 0640 root:<the group of the unit's user>) and
   the address rule (a daemon off the loopback — only with TLS; a process door without a kit — the loopback; signer and relay — by an explicit
   address with a loud log line, on the process default `0.0.0.0` — a start refusal, code 2; resource without a kit — only the loopback, ADR-0075 addendum 2026-10-26 (6) item 2; ADR-0075 addendum 2026-10-26 (5) item 4): confirm it by a structural test of the units and by the tests of the centre (N5) or
   explicitly leave it without evidence of execution: the acceptance has no stand with TLS, it is checked by reading ([the system stand](../../common/acceptance/system/README.md)).

### Chapter 2.5 — the derivation of rights

1. Fix the set of manifests and the deployment for the time of generation/installation. Compare
   the derived role names with P/01.2 N1.1: the restriction of the manifest name already ensures their length.
2. Derive the table of N1.4 from the manifest, then apply the secret readers of N1.3 (`secrets.readers`, `secrets.reads`, `platform_readers`).
   Check an exact name against a prefix and the effective set of readers, not
   only the presence of a line in the list. Before the conversion, reject a literal * and a leading !/delete: in the declarations; do not change the key. Check the neighbouring vault, vault2, vault/nested: an exact declaration of vault does not change their ordinary rights. The generator outputs the delete field explicitly.
3. Check the two admission rows of the controller per N5: read/write are allowed, delete
   is forbidden; the other allowed deletions have not disappeared. Compare both sides of the
   boundary console/controller/worker without changing the placement protocol of [P/04](../../04-controller/spec/04-controller.norms.md).
4. Prepare the stand per the acceptance README: a separate instance for each scenario,
   empty data and replay memory, the same rights file, the background writers stopped.
   Carry out all steps.
5. Check all items of the canonical checklist. Confirm the sockets, file permissions, TLS and certificates
   by a structural test of the units and by the tests of the centre (chapter 2.4 N5) or explicitly leave them without evidence
   of execution: the acceptance has no stand with TLS, it is checked by reading ([the system stand](../../common/acceptance/system/README.md)).

For all chapters: complete the implementation description and the checklists; do not declare the check of the table a check of the whole life cycle of a manifest.

## Traps that depend on the language and the library

| Norm | Trap | How to check |
|---|---|---|
| text per N1.1 (2.1) | the YAML library accepts more constructs than the lesson allows, or has known defects of its own | the rules of the fine check of N1.1 one by one; the workarounds and defect cases — `LAYERS.md` § 4, the list of defects of the skill `lesson-spec`; the package `yaml-suite` |
| repeated keys are forbidden (2.1 N1.1) | the library has already replaced the first value with the last | detect repeats before the key–value pairs are lost, including flow mappings |
| scalars per N1.1 (2.1) | `Off` became a boolean, `010` an octal, and a quoted string a number | compare the kind of the original scalar with the rules of N1.1; do not convert a string to a number by the expectation of the field |
| an integer is not a boolean (2.1 N1.2, N1.3) | the language or a conversion treats `true` as one | distinguish the JSON/YAML types before the numeric check |
| the integer limit 2^53 − 1 (2.1 N1.1) | a conversion to a floating point number has already rounded the input | check the exact value of the integer before a conversion that can lose digits |
| absence and a key stated without a value differ (2.1 N1.2) | `null`, an empty mapping and absence are reduced to one default | keep the difference and apply the rule of the specific section |
| named and opaque levels (2.1 N1.2) | one traversal either forbids author names or lets unknown keys of a field through | change the way of checking only at the levels from the lists of N1.2 |
| unknown keys before values (2.1 N3) | decoding into a typed structure stops at the first invalid value | first complete the key check and collect all unknown paths |
| `blob` without `required: true`, `default`, `inherit` (2.1 N1.3) | the common description of a field admits properties forbidden to this type | apply the restrictions of the type after checking the common form of the field |
| the digest of the original bytes (2.3 N1.5, N3) | the YAML is parsed and written anew before computing SHA-256 | compute the digest of the bytes of `yaml` stored as they are |
| the mark after the row, only upwards (2.3 N3) | a delayed installer writes an old revision over a new one; the read period is wrongly counted from the write of the row | follow the revision and `cas` checks; the branch «unchanged» also brings the mark up to date; after a broken-off installation this depends on the next `manifest put`, whose time is not set |
| the workers script (2.4 N1.5) | NaN, a zero divisor or two passes bypass the budget | Check finiteness/range before the division, serialize the start reservation. |
| secret readers (2.5 N1.3) | An exact secret name is treated as a prefix | A prefix only with a trailing `/`; compare the effective readers with N1.4 |

## Done when

- [ ] *(2.1)* All 947 files give the verdict from the table: 203 `ok`, 744 `refused`; the sets of files and cases coincide.
- [ ] *(2.3)* All 87 installations of `puts.tsv` give the code and rev from the table.
- [ ] *(2.1)* Refused files give an explanation with the source name; a crash or a partially loaded manifest is not counted.
- [ ] *(2.1)* All cases of `classes.tsv` give their class-layer; the hints of `diagnostics.tsv` are written into the report (a divergence is not a failure); the package `yaml-suite`: `layer1` of each test matched.
- [ ] *(2.1)* The sample of the acceptance README is run through the manifest installation, or the description names the reason for deviating from the SHOULD (P/02.1-12).
- [ ] *(2.5)* The acceptance of the chapter — 8 scenarios / 70 steps — is carried out with the stated isolation and exceptions; the evidence by reading
  names the files and the checked subject: the generator, the effectiveness of rights and the OS settings. A new file is applied on
  a restart; a live or atomic switch of the cluster is not presented as a requirement of this chapter.
- [ ] *(2.4)* Reading the units does not prove the real OS permissions: the structural tests of the units, the runner, the workers script and the centre
  are named in the description as separate results of the implementation or of the operator stand.
- [ ] *(all)* All items of the normative checklists of the chapters are closed by the checks stated in them; the checks by reading are named separately.
- [ ] *(all)* The implementation description answers all 24 items of «Implementation decides».
- [ ] *(all)* The questions to the norms are passed to their author; one's own assumptions are not presented as the canon.

## On a divergence of the code and the norms

| Situation | Action |
|---|---|
| A verdict did not match, the norm is unambiguous | fix the loader or its regular path, then repeat the case |
| The table contradicts the norm | pass an acceptance defect to the author of the norms; do not change the verdict for the sake of a green run |
| The norm is incomplete or contradictory | describe the question with the input file and a reference to the section; agree on a change of the canon |
| The rights outcome diverges from the norm | match the input and the outcome with N1–N4 of chapter 2.5, then with the acceptance file; report to «Specification» the place, a counterexample and the proposed solution |
| After an AI correction a repeated wrong interpretation is found | write the sample and the clarification into `journal/corrections-<K>.tsv` of its chapter per ADR-0080 |

# P/02 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/02-installer.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/02-installer.md` (for people, not in the export).

Concrete scenarios, fixtures and expected answers are not supplied in M; the judge receives them separately. The public acceptance READMEs define their interfaces and scope, while norms and public forms define the required behaviour.

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
  [`acceptance/2/`](../acceptance/2/README.md).
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
| [02.1-installer.schema.json](02.1-installer.schema.json), [`.relations.json`](02.1-installer.relations.json), [`.layers.tsv`](02.1-installer.layers.tsv), [`.scalars.tsv`](02.1-installer.scalars.tsv); [the V7 layers](../../common/LAYERS.md) | the form source of chapter 2.1: standard files — JSON Schema 2020-12 and CEL, executed by libraries of pinned versions and by own layers; the section «Form» of the chapter norms is built from them | 1 |
| [02.3-installer.norms.md](02.3-installer.norms.md) | the canon of chapter 2.3: the manifest row and the mark, the start and the change, `manifest put` | 1 |
| [02.4-installer.norms.md](02.4-installer.norms.md) | the canon of chapter 2.4: units, environment, workers on order, certificates, installation, operator commands; the late layer — the ports and units of the domain, the installation of the domain (lesson 8) | 1 |
| [02.5-installer.norms.md](02.5-installer.norms.md) | the canon of chapter 2.5: roles and the derivation of rights, the readers of secret rows, generation and `--check` | 1 |
| [The acceptance README of chapter 2.1](../acceptance/1/README.md) | common inputs, expected verdicts, classes and diagnostic hints | 3 — check the canon, do not add to it |
| [The acceptance README of chapter 2.3](../acceptance/3/README.md) | the installations of `manifest put` | 3 — check the canon, do not add to it |
| [The acceptance README of chapter 2.5](../acceptance/5/README.md) | preparing and comparing rights | 3 — check the canon, do not add to it |
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

## Glossary

Some words of the norms have more than one meaning; the place of the word tells them apart. This table adds no rule and renames nothing: each meaning is the one the named place already gives.

| Word | Meanings | How to tell them apart |
|---|---|---|
| manifest | (1) the file `<sub>.subsystem.yaml` in `MANIFEST_DIR` next to its shell and files (P/02.4-R265, P/02.4-R282); (2) the manifest row `platform/manifest/<sub>` in the store, whose field `yaml` holds the bytes of the file (P/02.3-R014); (3) the loaded manifest — the answer of `load(bytes, source)` (P/02.1-R147); (4) the field `manifest` of the view row — the JCS bytes of the view (P/02.2-R027); (5) the built-in manifest of a process of a cluster of one (P/02.4-R414) | a path or `MANIFEST_DIR` — the file; a key `platform/manifest/<sub>`, `rev`, `cas` — the row; the result of loading — the tree; `…/canonical/<form>` — the view field; «built-in» — the manifest of the build |
| catalogue | (1) the manifest catalogue — all manifests of the cluster, checked together by `load_catalogue` (P/02.1-R176); (2) the refusal catalogue of a chapter — [`forms/refusals.tsv`](../forms/refusals.tsv) (P/02.1-R214); (3) the data catalogue `Platform/common/data/catalog.tsv` — the row families and their writers («**Data**» of N1; P/02.4-R389); (4) the acceptance catalogue — the directory `acceptance/K/` of a chapter (P/02.3-R182, P/02.4-R490); (5) the start catalogue of a console — the manifests the console takes at its start (P/02.4-R190, P/02.4-R348) | `load_catalogue`, «catalogue refusal», `refused:catalogue` — the manifests; `chapter` and `row` of a refusal — the refusal catalogue; a row family and its writer — the data catalogue; a directory — the acceptance; «start catalogue», a console restart — the console |
| row | (1) a row of the store: a key and its fields, such as the manifest row and the mark (P/02.3-R003, P/02.3-R014); (2) a row of the relations `02.1-installer.relations.json`, numbered by its field `no` («row 122», «rows 160–162»; P/02.1-R078, P/02.1-R086); (3) the address of a refusal — the columns `chapter` and `row` of the refusal catalogue (P/02.1-R214); (4) `unit.rows` — the name of the family of the unit rows of a subsystem (P/02.1-R178); (5) a role row of the table of rights of N1.4 of chapter 2.5 (P/02.5-R031); (6) an installation row of the acceptance of chapter 2.3 (P/02.3-R182) | a key, `cas`, a version — the store; a number next to `relations` — a relation; `chapter` and `row` — a refusal; `unit.rows` — a family name; a role in the first column — the table of rights; a case name — the acceptance |
| field | (1) a field of a unit or a table declared by the manifest, `unit.fields.<name>`, `tables.<t>.fields.<name>` (P/02.1-R068); (2) a field of a store row, such as `yaml`, `sha256`, `rev`, `shell`, `files` of the manifest row (P/02.3-R014); (3) a platform field — a name of `platform_fields` (P/02.1-R070, P/02.1-R094); (4) a secret field — a name ending with `_secret` (P/02.1-R083) | inside `unit.fields` or `tables` — a field of the manifest; a field of `platform/manifest/<sub>` — a row field; `platform_fields` — the platform; `*_secret` — a secret |
| form | (1) the form layer of the loader and its refusal `refused:form` (P/02.1-R151, P/02.1-R213); (2) the section «Form» of chapter 2.1, built from the standard files (P/02.1-R049); (3) the view form — the number `form` of the view row `…/canonical/<form>` (P/02.2-R027, P/02.2-R034); (4) `display.form` of a manifest (P/02.2-R017); (5) the form of a row family — «out of its form», «not by the form» of a row or a mark (P/02.2-R067, P/02.3-R042) | `refused:form` or «layer» — the loader; «the section «Form»» — the chapter section; `canonical/<form>` — the view; `display.form` — the page; a row or a mark out of form — the family |
| layer | (1) a layer of the loader: text → form → relations, and the class of a refusal is the layer (P/02.1-R155, P/02.1-R213); (2) a numbered layer of [LAYERS.md](../../common/LAYERS.md): layer 1 — the thin check of the text, layer 2 — the integer place, layer 3 — the row codec (P/02.1-R008, P/02.1-R056); (3) the late layer — the parts of the lesson introduced by lesson 8 (P/02.4-R091, P/02.5-R058); (4) the layer table `02.1-installer.layers.tsv` and its marks `x-*` (P/02.1-R060) | `refused:<class>` — the loader; a number — LAYERS.md; «late» — lesson 8; «layer table», `x-*` — the table |
| refusal | (1) a refusal of the loader `refused:<class>`, in words with the source (P/02.1-R198, P/02.1-R213); (2) a start refusal: the process does not start and exits with a non-zero code, 2 for a confirmed unfitness (P/02.3-R063, P/02.4-R018); (3) a refusal of a command or of the installation with an exit code (P/02.3-R081, P/02.4-R286); (4) a generation refusal of the rights tool before the file (P/02.5-R046, P/02.5-R128); (5) a refusal of the handshake or 403 at a door (P/02.4-R176) | a class word — the loader; a process and its code — the start; a command — its exit code; the rights file — the generation; TLS or HTTP — the door |
| mark | (1) the mark of a manifest — the row `platform/manifest/<sub>/rev` `{rev, sha256}` (P/02.3-R005, P/02.3-R014); (2) the marks `x-*` of the layer table: `x-class`, `x-ordered`, `x-integer-place` (P/02.1-R056, P/02.1-R060, P/02.2-R021); (3) the request marks — the objects `objects/<s>/commands/*` (P/02.5-R042, P/02.5-R078); (4) the mark of a checklist item: `[test]`, `[reading]`, `[stand]` (P/02.1-R005); (5) the text «generated — do not edit» of the rights file (P/02.5-R097) | `/rev`, `rev` and `sha256` — the manifest; `x-*` — the layer table; `commands` — a request; square brackets after an item id — the checklist; the rights file — its comment |
| view | (1) the canonical view of a manifest — the row `platform/manifest/<sub>/canonical/<form>` and its bytes (P/02.2-R005, P/02.2-R027); (2) the sections `domain.view`, `domain.view_status`, `domain.view_pulse`, `domain.view_tables` of a manifest (P/02.1-R062, P/02.1-R083); (3) the object `domain/view` (P/02.5-R044); (4) the rank `view` of a route (P/02.1-R119) | `canonical`, the reader of chapter 2.2 — the view row; `domain.view*` — a manifest section; `domain/view` — an object; `rank` — a route |
| installation | (1) `install` — the installation of a server, `install.sh`; a repeat is an update (P/02.4-R206); (2) `manifest put` — the installation of one manifest into the store, refused «as a whole» (P/02.2-R050, P/02.3-R081); (3) the domain installation (P/02.4-R483); (4) the installation of the rights file, N3 «install» of chapter 2.5 (P/02.5-R104); (5) an installation row of the acceptance of chapter 2.3 (P/02.1-R224) | `install`, steps, enable — the server; a manifest file and its rev — `manifest put`; the domain root — the domain; the candidate `.new` — the rights file; a case — the acceptance |
| process | (1) a running program of a role: the console, the controller, the worker, the resource, the domain processes (P/02.4-R061, P/02.4-R098); (2) the process `domain` — the role of the domain, one active per cluster (P/02.4-R146, P/02.4-R440); (3) `address` `process` — the rule of the doors of processes without a kit (P/02.4-R164); (4) a running process on the reader side of the manifest row (P/02.3-R128) | a unit or a role name — the program; «the process domain» — the domain role; `address` — the address rule; «a running process» with the mark — the reader |
| role | (1) the role of a process and of its certificate: `W2C_ROLE`, `urn:w2c:role:<role>`, one role per certificate (P/02.4-R159, P/02.4-R176); (2) a role of the rights file — `console`, `<s>controller`, `<s>worker` and the others (P/02.5-R076); (3) the words `controller` and `worker` of `secrets.readers` — the roles of the declaring manifest (P/02.5-R038); (4) `door.routes[].role` — the roles admitted to a route (P/02.1-R119); (5) the role group — the OS group of a role socket (P/02.4-R024, P/02.5-R068) | a certificate, SAN, `W2C_ROLE` — the process; a rights row — the rights file; `secrets.readers` — the declaring manifest; `door.routes` — admission; «role group» — the OS group |
| unit | (1) a systemd unit — `.service`, `.socket`, `.timer` (launchd on macOS) (P/02.4-R016, P/02.4-R042); (2) a unit of a subsystem — its object with `unit.fields`, `unit.id`, `unit.rows`; a numeric unit (P/02.1-R068, P/02.1-R133); (3) a unit of measure — the environment file contract «Constants and units» (P/02.4-R056) | a unit file name — systemd; `unit.*` — the subsystem; a constant — measure |
| part | (1) a part of a subsystem — `parts.<part>`, a service of its own `<dep>-<sub>-<part>.service` (P/02.1-R115, P/02.4-R043); (2) a part of a static file — the row `platform/manifest/<sub>/files/<sha256>/<n>` of up to `FILE_PART` bytes (P/02.3-R018); (3) the part of a checklist item that a mark word closes (P/02.1-R005) | `parts`, a share with `part`, volumes — the subsystem; `files/<sha256>/<n>`, «bring the parts up» — a file; a checklist mark — an item |
| server | (1) a machine of the cluster, `SERVER_NAME`; the installation and the rollout go server after server (P/02.4-R030, P/02.4-R179); (2) the platform field `server` of a unit (P/02.1-R094, P/02.2-R015); (3) the server side of TLS: `server.pem`, `server.key` of a kit (P/02.4-R075); (4) `DOMAIN_SERVER` — this server holds the domain or stands as a spare (P/02.4-R220) | a host or `SERVER_NAME` — the machine; a field name — the unit; a kit file — TLS; `DOMAIN_SERVER` — the domain |
| kit | (1) the role kit — the certificate and the key in `/etc/w2c/tls/<role>` (P/02.4-R075, P/02.4-R159); a partial kit or no kit — the address rule (P/02.4-R164, P/02.4-R165); (2) the generated kit of an implementation and its parts in [`forms/stages.tsv`](../forms/stages.tsv) (P/02.1-R219, P/02.4-R488) | a role, TLS, `W2C_TLS_DIR` — the role kit; seams and stages — the generated kit |
| door | (1) an HTTP door of a process — the address rule (P/02.4-R164); (2) a door without a vote — the store daemon in the state `Door` (P/02.4-R300, P/02.4-R314); (3) `door.pass`, `door.routes` — keys of a manifest (P/02.1-R095, P/02.1-R119); (4) the row `platform/doors/<s>` of the resource (P/02.4-R460); (5) the two doors of the loader: the loading procedure, not HTTP, and `GET /manifest` of the console (P/02.1-R146); (6) the local door of the agent on a Unix socket (P/02.4-R453) | an address and a kit — a process door; `Door`, voters — the store; `door.*` — the manifest; `platform/doors/` — a row; «the loader has two doors» — chapter 2.1; `<AGENT_TOKEN_DIR>` — the agent |
| source | (1) the source name of `load(bytes, source)` — a file or a store key that a refusal names (P/02.1-R147, P/02.1-R198, P/02.1-R236); (2) `/manifest/<sub>/source` of the console — `sha256` and `served` (P/02.4-R348, P/02.4-R354); (3) the installation source — the manifest file in `MANIFEST_DIR` for the keys baked into the units (P/02.3-R165); (4) the source rights — the positive lists of chapter 2.5 N1.4 (P/02.5-R026) | a refusal — the source name; a console route — `/source`; units and their keys — the installation; the rights file — its source lists |
| window | (1) the installation window — the view written with rev N, the mark still N − 1 (P/02.2-R064, P/02.3-R060); (2) the change window of the view form — both forms are written (P/02.2-R034); (3) the operator window of the domain installation (P/02.4-R484); (4) the maintenance window of deleting bodies (P/02.4-R464) | a reader and a mark — the installation; `canonical/<form + 1>` — the view form; the domain — the operator; bodies — maintenance |
| order | (1) workers on order — the row `<sub>/want/<host>` (P/02.4-R104); (2) the order of `manifest put` of the initial installation (P/02.4-R253); (3) the order `add` — the steps of adding a subsystem (P/02.4-R296); (4) the orderer — a subsystem whose `worker.creates` creates the rows of another one (P/02.1-R164, P/02.1-R168) | `want` — the workers script; «addressees before clients» — the installation; `add` — the rollout; `worker.creates` — the orderer |
| worker | (1) the role `<sub>worker` and its unit `<dep>-<sub>worker@.service` (P/02.4-R154, P/02.4-R030); (2) the word `worker` of `secrets.readers` — `<s>worker` of the declaring manifest (P/02.5-R038); (3) the worker on the domain — the role `<sub>domain`, the platform word `domainworker` (P/02.5-R008, P/02.4-R449); (4) the platform field `worker` of a unit (P/02.1-R094); (5) the section `worker` of a manifest (P/02.1-R117) | a unit or a slot — the role; `secrets.readers` — the declaring manifest; «on the domain» — `<sub>domain`; a field name — the unit; `worker.*` — the manifest |
| reader | (1) the reader of the canonical view (P/02.2-R062); (2) the reader side of the manifest row — a process that reads the row and the mark (P/02.3-R006, P/02.3-R015, P/02.4-R435); (3) a secret reader — a role that reads a secret row (P/02.5-R007, P/02.5-R029) | «Reader» of chapter 2.2 — the view; the row and the mark — a process; `secrets.readers` — the rights |

## What to create

The mandatory behaviour is in the canon. The internal types, functions, the structure of errors and the choice of libraries remain with
the implementation; the names of the procedures in N2–N3 denote their meaning, not mandatory signatures of a specific language.

Chapter 2.1:

1. **Loading of one manifest** from bytes with a source name: the check of the text, the name, the keys, the values and the references,
   then filling the defaults in the order of N3. The result is a whole manifest or a refusal with the needed information per N4. After the key check, refuse NaN, infinities and float overflow, including nested numbers of opaque/default/inherit; all accepted values are representable in JSON.
2. **Loading of a catalogue** with the checks of `worker.requests` and `placement.near` per N3. The acceptance of one file
   does not substitute for the catalogue check; neighbouring manifests not named by the table are not added to the table runner.
3. **A run of the common table** by the regular loading path according to the acceptance README. The installation is judged separately, by `puts.tsv` of chapter 2.3
   (N5; judge-only: the installation sequences of chapter 2.3); the corpus is not run through `manifest put`.

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

The implementation stages are [`forms/stages.tsv`](../forms/stages.tsv): goals, gates, weights, kit parts and dependencies. This is a possible plan, not an additional behavior norm. The advice below complements the table; the readiness checklists keep the obligations that need reading, OS installation or a multi-process stand.

### Chapters 2.1 and 2.3 — the manifest

1. *(2.1)* Write out the boundaries of the closed, named and opaque levels from N1.2,
   their owner lessons and the choices of the implementation. Check the mandatory unit/rows/id: the loader does not invent a family or a kind of id; the absence of unit.fields means an empty mapping.
2. *(2.1)* Set up the reading of bytes and the parsing of the text per N1.1: a YAML 1.2 parser of a pinned version and the fine check of layer 1
   ([the V7 layers](../../common/LAYERS.md) § 4, workarounds D13, D16). Run the checks that need the original text or the list of keys before
   the conversion into a mapping before the library loses this information; one document — by bytes.
3. *(2.1)* Carry out the loading pass of N3 by layers: text → form (the JSON Schema 2020-12 schema and the words `x-*`, the integer place —
   layer 2) → relations (CEL, only with a clean form). Filling the defaults does not hide an erroneous input.
4. *(2.1)* Run `verdicts.tsv` (judge-only: the corpus table): one file — one load. Compare the set of files with the table;
   count a refusal by the rules of the README, not by any exception or non-zero process code.
   Compare the class of `classes.tsv`; the paths and lines of `diagnostics.tsv` are a hint in the report without a failure (judge-only: the case classes and diagnostic hints).
5. *(2.1 — catalogue; 2.3 — storage and change)* Check the catalogue, then the storage and the change of a manifest: a repeated installation without changes, a `cas` conflict,
   a lagging and a missing mark, all the reasons for a start refusal of N4 (including an unconfirmed read of the row/mark and a mismatch of the embedded manifest), a start between two writes of the installer, `toolarge` of the main row
   before the write of the mark. For the catalogue, do not ascribe to the read an atomic snapshot or a mandatory refusal on any
   change of a file: the bytes and relations actually received are checked. The subjects of the check are N3, N5 and the checklist.

### Chapter 2.4 — the installer

1. Match the roles, groups, directories, permissions, sockets and environment to each row of N1.1–N1.2. Check the priority of values and the absence of source for data; do not count After as readiness (N3).
2. Design the preliminary check and the write points of the installer. Force a refusal at each phase: before the write there are no changes, after the start a partial result with diagnostics is admissible and without enable/start of new services (N1.7).
3. Check the script of workers on order: budgets, reservation before start, numbers 2…99 (start of the smallest, stop of the largest), no series — nothing, an unknown outcome of a start and a stale console, polkit start/stop of the full names of its own server. Certificates — a separate test CA, revocation before concluding a full cut-off (N1.5–N1.6).
4. The role certificate (SAN URI `urn:w2c:role:<role>`, CN `<role>.<server>`, the key 0640 root:<the group of the unit's user>) and
   the address rule (a daemon off the loopback — only with TLS; a process door without a kit — the loopback; signer and relay — by an explicit
   address with a loud log line, on the process default `0.0.0.0` — a start refusal, code 2; resource without a kit — only the loopback): confirm it by a structural test of the units and by the tests of the centre (N5) or
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

- [ ] *(2.1)* All 951 files give the verdict from the table: 203 `ok`, 748 `refused`; the sets of files and cases coincide.
- [ ] *(2.3)* All 97 installations of `puts.tsv` (judge-only: the installation sequences of chapter 2.3; they check P/02.3-R004, P/02.3-R005, P/02.3-R007, P/02.3-R009, P/02.3-R012, P/02.3-R014, P/02.3-R016, P/02.3-R018, P/02.3-R023, P/02.3-R026, P/02.3-R027, P/02.3-R029, P/02.3-R030, P/02.3-R081, P/02.3-R082, P/02.3-R085, P/02.3-R087, P/02.3-R100, P/02.3-R102, P/02.3-R103, P/02.3-R104, P/02.3-R105, P/02.3-R107, P/02.3-R110, P/02.3-R111, P/02.3-R114, P/02.3-R119, P/02.3-R123, P/02.3-R125, P/02.3-R137, P/02.3-R138, P/02.3-R140, P/02.3-R171, P/02.3-R173, P/02.3-R191) give the code and rev from the table.
- [ ] *(2.1)* Refused files give an explanation with the source name; a crash or a partially loaded manifest is not counted.
- [ ] *(2.1)* All cases of `classes.tsv` give their class-layer; the hints of `diagnostics.tsv` are written into the report (a divergence is not a failure; judge-only: `classes.tsv` checks P/02.1-R155, P/02.1-R198, P/02.1-R213, P/02.1-R215, P/02.1-R236, the hints of `diagnostics.tsv` illustrate P/02.1-R047, P/02.1-R201, P/02.1-R205, P/02.1-R206); the package `yaml-suite`: `layer1` of each test matched.
- [ ] *(2.1)* The sample of the acceptance README is run through the manifest installation, or the description names the reason for deviating from the SHOULD (P/02.1-R147).
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
| After an AI correction a repeated wrong interpretation is found | write the sample and the clarification into `corrections-<K>.tsv` (historical correction record) of its chapter |

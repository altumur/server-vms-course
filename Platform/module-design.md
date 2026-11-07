# Platform — module design note

*Written on 18 October 2026 by the Architect. Basis: ADR-0083, Platform micromodules, with addenda (1) and (2). The second edition accounts for:*
- *21 Specification comments (the first Platform design-note findings, 2026-10-18, in decisions/inbox);*
- *Codex, Kimi and Gemini Platform review 1 reports;*
- *the store pilot (`/Users/murat/w2c/cammeta-interop/REPORT.md`).*

*The 15 comments on the second edition are also included. The owner accepted the decision summary on 2026-10-18. **The owner approved the third edition on 2026-10-18**. The fourth incorporates Platform review 2: no blockers, changes without an architectural change. Specification maintains the note thereafter.*

The module replaced two course modules: M10 Platform (11 lessons) and M11 Domain (12 lessons). Here a lesson is a **micromodule**, a process or library with its own contract, acceptance and release, optionally its own language. The module lives in the course repository's `Platform/` (ADR-0083 addendum (2) item 7). The former module directories were removed at the end of stage B (Migration item 8).

System decisions live in `decisions/`. Lesson form — lecture, `spec/`, N0–N5, OpenAPI, implementation instructions and acceptance — follows `lesson-spec`. This note describes the micromodule transition. Its migration sections record the historical plan; current lesson norms and subsequent ADR addenda remain authoritative. Under ADR-0121 (9) and ADR-0083 (113), correction journals and migration maps now live in decisions history and are not exported lesson inputs.

## Decisions

| Question | Decision | Reason |
|---|---|---|
| What is a lesson? | **Lesson = micromodule.** It specifies everything one process or library does: doors, call contract, data and files, lifecycle, and introduced algorithms. It only reads others' data, through the catalogue | ADR-0083 items 1, 6; addendum (2) item 5: relay mode is an agent chapter |
| Lesson contract | **Five kinds** (addendum (2) item 1): doors in OpenAPI; library calls and sequences; rows, objects, shared files and directories; lifecycle flags, environment, exit codes, service units, disk format and copy; algorithm vectors. No other neighbour coupling is normative | Python/Go comparisons and the store pilot: the door survived a language change; implicit disk/copy/flag contracts did not |
| Data catalogue | `common/data/catalog.tsv`: key template or file path, **contract owner** (lesson), operations and conditional **participants** (`create`, `put`, `cas`, `guard`, `mark`, `delete`, `append`), readers, form version, schema or format. A `row` or JSON `object` schema is `NN-<process>/data/<family>.schema.json`; a `file` or binary object has `-` (ADR-0088). Reading another family's data requires its catalogue row; absence is a `check_spec` error. Rights derivation follows addendum (2) item 6 | Addendum (2) items 2, 6 |
| Compatibility | Writers send only declared fields. Readers ignore unknown response/row/object fields, **but retain, forward and verify signed content byte for byte, dropping fields only after signature verification**. Door requests are strict. Incompatible changes need a new version and transition window. Lesson 1 N0 introduces the norm separately after migration | ADR-0083 item 3; addendum (2) item 3 |
| Migration and behaviour | **Moving a lesson changes no behaviour.** Norms and acceptance steps move unchanged. New behaviour follows its owner lesson in separate edits, each listing changed steps: tolerant readers, canonical manifest view, module-wide array ordering, relay extraction if chosen (then lesson 9 also splits) | Addendum (1); migration is separate from behaviour changes |
| Chapters | Large micromodules split into `spec/NN.K-<name>.norms.md`, one OpenAPI per micromodule and chapter acceptance subdirectories | The domain process and cluster console combine many former lessons |
| Late-layer chapter | An early micromodule function existing only for a later layer — domain forwarding or domain-grant sessions — is an early lesson chapter labelled “introduced by lesson N”. The later lesson migration writes it; the early lecture points to lesson N. Its OpenAPI door uses later lesson forms by `$ref`, not copies: one wire form. The path description and chapter header identify the late chapter; early chapters and `components` cannot reference it (`check_spec`) | One place for each micromodule contract |
| Order | **Lesson number is the owner's address.** Reading order is a separate chapter table below. Process and algorithm words come from earlier reading; catalogue data may be read in either order | Addendum (2) item 6; reordering cannot remove 3↔4 and 5↔6 dependencies |
| Cross-module scenarios | Drain, server failure/restore, holder move and lesson 5 `group_by` go in `common/acceptance/system/` with all required processes. First cases were M10/11 scenarios 05, 06 (lesson 6 migration, B2). `check_spec` does not walk this directory; its README defines the form. **A scenario belongs to its outcome's chapter**; neighbouring processes are stand components, not that chapter's norms | Findings item 19; stage A 8–10 review analysis, no. 24 (ADR-0083 addendum (13)) |
| Matrix | `common/acceptance/matrix/`: mixed builds for each micromodule with two implementations. Language and contract version are independent axes | ADR-0083 item 5; Codex review |
| Traceability | Historical `id-map.tsv` maps old norm/scenario/step/vector ids to new ones and redirects corrections, generator logs and `check_spec` exceptions. Steps before = steps after + removals with reasons; expected-byte samples are also compared. The map is now in decisions history | Findings items 20, 21 |
| Norm ids | `P/NN-MM`, or `P/NN.K-MM` for a chapter | ADR-0080 addendum 6 |
| Data paragraph | At each lesson N1 start, like Time: written key families/files and operations, read families/files, catalogue references. `check_spec` compares both directions. Define the form before populating the catalogue | Second findings, item 11 |
| Normative vocabulary | N0 normative words (MUST, SHOULD, MAY, etc.) are **course-wide canon**, in a stable course file extracted and linked during stage A. Platform lesson 1 N0 contains module rules, **each retaining its original scope**: stable output and row time apply module-wide as in M10/1; array order applies to lessons 8–10 as in M11/1. Extending it module-wide or adding compatibility is separate behaviour work | Second findings item 14; review 2 |
| Process lifecycle | Each process's environment, flags and exit codes live in `NN-<process>/lifecycle.md`, read with the process. Manifest-row consumer startup, checking at least every 30 s and exit 0 on change are P/02.3 N3 contracts for **consumer processes** (3–6, 8–10), not store or installer: store starts empty with `admin.sock`, installer writes the row. Each consumer acceptance has a step. P/02.1 and 2.3 define the shared manifest contract; there is no `key-template` vector | Second findings items 6, 13; stage A 6–7 finding 2a |
| Shared vectors | `Source/tests/testdata/*.tsv` are vectors shared with the product. Owner algorithm vectors move to `NN-<process>/vectors/<algorithm>/`, not `testdata/`. Specification owns bytes; product acceptance establishes conformance (the former Parity requirement was removed, ADR-0080 addendum 16). Update Owner headers in the same commit; product `sync-course.sh` switches once. Check each row against current norms before calling it a reference: `requests_body.tsv` expected `{"x":0.0000001}`, whereas JCS requires `1e-7`; the table was fixed and the product debt recorded. Pure M11 functions (`view`, `accept`, `may`, `peer`, …) are owner/common vector packages executed by an implementation command | Second findings item 9; ADR-0083 (13)–(14) |
| Catalogue-derived rights | Switch from manifest derivation only when catalogue-derived rights are **semantically** equal under `--check` for `testsub`, `testsub2` and M10/6 derivation cases. Until then the manifest remains the source | Second findings item 12 |
| Corrections | Move acceptance directories with history using `git mv`. Never rewrite old correction rows; the historical id map resolves their old paths. New rows used new paths. Journals now live under decisions, by ADR-0121 (9) | Second findings item 15 |
| Publication | One repository: each lesson migration adds the new files, removes old locations and repairs links in one consistent commit. Historically `cammeta-specs` exported both trees during migration | Addendum (2) item 7 |
| Stages | **A**: catalogue, vectors and matrix over then-current M10/M11. **B**: lesson migration. Stage A could stand on its own | Addendum (2) item 8 |

## Lessons

| No. | Micromodule | Kind | Normative scope and chapters | Origin |
|---|---|---|---|---|
| 1 | **Store** (`01-store/`) | process, roles are sockets | 1.1 operation vocabulary, op:batch, row/index, 409/412, HTTP framing, refusal order; 1.2 rights-file form, one evaluator, role sockets; 1.3 daemon flags, FORMAT and foreign-directory refusal, group of 1/3/5, admin operations, floor, JSON Lines copy and import/restore, flat/inherited sockets, durability and /v1/status; N0 module rules: compatibility, row time and array order (normative vocabulary is course canon) | M10/1; M10/6 evaluator/rights file/sockets; M10/11 daemon |
| 2 | **Subsystem manifest and strict loader** (`02-installer/`) | command process, centre, service units | 2.1 manifest text, strict loader, corpus, door.pass grammar, JSON-Schema depth; late layer introduced by lesson 8: domain.* and loader refusals m51_*, m57_*, m59_*, m61_* in labelled N1.2b, while the corpus covers the whole loader; domain projection in GET /manifest belongs with that door, temporarily M10/9 until 6.5; 2.2 one current canonical view form1 at .../canonical/1, installer projection and the existing N3 Reader, current revision publication races and per-row ceiling; 2.3 platform/manifest/<sub>, manifest-put and consumer startup/mark/stop-on-change contract for all processes; 2.4 installer, install/update assemblies, units/users/groups, centre, role certificates, URL rule, per-server requested-worker script, box profile and one-member cluster (each process environment stays in lifecycle); late domain units/ports/installation (M11/2); 2.5 role rights derivation and semantic --check | M10/2; M10/6 rights/certificates; M10/7 declarations; M10/11 units/environment/installation/centre/requested workers; M11/12 N1.2/N1.8 |
| 3 | **Worker** (`03-worker/`) | per-language library, role `<sub>worker` | 3.1 six subsystem calls and `before_stop_all`/`stop_unit`/`after_stop` order; 3.2 slot, claim, epoch/floor, lease (schema checked after each renewal), nobody and place; 3.3 assignment reconciliation, read after P/04; 3.4 heartbeat, guarded writes including `worker.writes` table rows, stop, budget and two copies; 3.5 ring and `enc:v2` opening; 3.6 request execution (`rid`) and event-journal append, whose contract belongs to lesson 5; startup schema check; late book contributions under a slot (`<sub>/<from>`, 8.5; agent only reads/repackages), local agent token request held in memory (9), recipient token verification (8.7), domain subsystem worker (`<sub>domain`, `domain/<sub>/worker`, carried books, `kept`) | M10/3 slots; M10/5; M10/7 opening; M10/8 requests/events; M10/10 schema; M11/5 N1.6; M11/7 N1.5 |
| 4 | **Controller** (`04-controller/`) | `<sub>controller` process | pass/order, pool, constraints, weights, groups, spread, slot fate, intent move under turn, drain/decommission, per-server worker order and shrink (ADR-0084), `delete_after`, pass report; **whole snapshot**, empty shards for departed entries and ceiling; startup schema check | M10/4 N1/N3; M10/10 snapshot; M10/11 requested workers |
| 5 | **Resource** (`05-resource/`) | per-server process | object door and body-copy door (64 MiB, mirror, tombstones); **event-journal file-contract owner** (line, event id, buckets, lock; append participants 3.6 and 6.4), index/serving, finite retention, bucket restore, object `max_bytes`; resource heartbeat, presence/file lock with worker, disk marks and `free-*` requests; startup schema check | M10/8 objects/index/resource; M10/10 bodies; M10/11 bucket restore |
| 6 | **Cluster console** (`06-console/`) | `console` process | startup schema check; 6.1 unit door (`values_by_type`, idempotency key/rid, 1024-byte name/key, JSON depth 64), `POST /console/batch`, `GET /changes`, client blob PUT (32 MiB, revision, two places), cleanup list of 64 digests and table doors; 6.2 sealing/mask/ring change/resealing; 6.3 gate, identity, people rights and late domain gate data; 6.4 requests/digest/reaper, journal append, merged events and marks; 6.5 manifest/mounts/servers/resources/where/metrics/page and worker `door.pass`; 6.6 policy/drain/DrainState/server labels/decommission/unplaceable/schema upgrade; late domain forwarding (10), book door (8.5), prepare/take/move to local SIGNER_URL with own refusal order and budgets (8.8), domain grants and break-glass (8.4), keys/shared resolve (8.9), held/backup (8.8), peer participant (vector owner 9) | M10/3 unit door; M10/4 doors; M10/6 people rights; M10/7 sealing; M10/8 requests/reaper/journal/events; M10/9; M10/10 schema/blob/cleanup/tables; M11/8 forwarding; M11/9 session; M11/10 N1.4/N1.9; M11/11 resolve |
| 7 | **Console module** (`07-console-module/`) | JS library | closed call list, logical-action api and retry on an unknown outcome, may, shell calls and version; late chapters introduced by 8/10: domain section, shared-document schema, mount sections `[domain]` (lesson 10 serves the page) | `CONSOLE-MODULE.md`; M10/9 module contract |
| 8 | **Domain process** (`08-domain/`) | holder `domain` process | 8.0 process doors, console edits via SIGNER_URL, reports and login; 8.1 view/shadow; 8.2 root/set/book_seal/revocation/keys/cold start; 8.3 report signature and common accept, mark/delta/relay batch/topology; 8.4 people/grants/login/break-glass/may; 8.5 books/name index with 8.4 filtering; 8.6 placement/pending edits; 8.7 tokens; 8.8 term/backup/holders/move/handover; 8.9 shared document/alarm history; 8.10 queue/waiting process/cost | M11/1–3, 5–7, 9–12 holder side |
| 9 | **Agent** (`09-agent/`) | `domainagent` process or in-process mode | 9.1 member publication/reply/write-only-if-different, member books and sealing, placement copies/outcomes/apply edits, local token door, grants copy/break-glass, follow, backup-holder agent, road choice, shared document/alarm page, embedded agent and sign_failures; 9.2 **relay mode**, RELAY=1 with the same process/role/key: member signature, relayed batch, memory reply, domain_age and carried asks; own OpenAPI section and acceptance subdirectory | M11/3–7, 9–12 member side; M11/4 N1.1/N1.4 relay pass |
| 10 | **Domain console** (`10-domain-console/`) | `domainconsole` process | operator/read doors: domain view, subsystem rows/tables, shadow, admission, topology/placement/people/grants/move/handover/shared/alarms; pass edits to domain via SIGNER_URL; holder page, CSP; domain door.pass to domain worker (cluster console is first hop only); common lesson 6 console-acceptance algorithm | M11/1 doors; M11/8 N1.7; M11/3, 4, 6, 8–11 operator doors |

Each M10/M11 norm was assigned to exactly one chapter. The historical full map contains 315 norms in 367 rows including split parts, plus 16 new norms without an old id. Late chapters not numbered in the table are 3.7 and 6.7; 6.8 cluster folders (ADR-0096) and 6.9 group operations (ADR-0095) follow increment B acceptance. Late parts of 2.1, 2.4 and 6.3 remain labelled in their chapters. Migration of 8–10 writes 6.7 and checks the earlier 2.1 N1.2b and 3.7 (stage A 6–7 review analysis, no. 27). A norm concerning several chapters lives with its subject; notes name and split other parts during migration.

**Places to check during migration** — the review identifies them; this note cannot resolve them without reading their norms:
- Operator commands from M10/11 N1.9 belong to the lesson of the process executing them.

## Reading order

| Step | Chapter | Prerequisites |
|---|---|---|
| 1 | 1.1–1.3 store | — |
| 2 | 2.1, 2.3 manifest and manifest row | 1 |
| 3 | 2.2 canonical view | 2.1 |
| 3a | Common contracts: object versus row and object door (5, first chapter), request digest, URL parsing, peer, may; sealing ring/enc:v2/AAD with vectors (`common/contracts/sealing.md`, `common/vectors/sealing/`); role certificate form/sig/bundle/revocation (`role-certificate.md`). Domain token, x25519:v1/m1 envelopes, keys, agent-signature, record, ask-sig and accept before 8/9 and late 6.3/6.7; local-token-door before 9.1/3.7; gate-and-pass before 6.3/6.5/10; forwarding before 6.7/8/10 | 1, 2 |
| 4 | 3.1, 3.2, 3.4, 3.5 worker without reconciliation | 1, 2, 3a |
| 5 | 4 controller | 3.2 slots; heartbeat catalogue |
| 6 | 3.3 worker reconciliation | 4 assignment/intent |
| 7 | 5 resource and event-journal contract | 1, 2 |
| 8 | 3.6 requests and event writes | 5 |
| 9 | 6.1–6.6 cluster console | 3–5 |
| 10 | 7 console module | 6 |
| 11 | 2.4, 2.5 installer and rights derivation | 1–7 roles; process environment is read earlier with its lifecycle |
| 12 | 8.0–8.10 domain process | 1–7 |
| 13 | 9.1 agent, 9.2 relay mode | 1, 2, 3a domain contracts, not 8.3 norms: self-contained contracts, ADR-0083 (5), (13) |
| 14 | 10 domain console | 8, 9 |
| 15 | late chapters of 2, 3, 6, 7 | 8–10 |

## Cross-cutting topics — index, not canon

| Topic | Location |
|---|---|
| Rights | 1.2 evaluator, 2.5 derivation, 6.3 people, 8.4 grants, 9 copy |
| Secrets | 2.1 declarations, 3.5 opening, 6.2 sealing, 8.2 book_seal, 9 sealing to book_seal |
| Events and alarms | 3.6/6.4 writing, 5 index, 6.4 events, 8.9 history, 9 page |
| Tokens | 8.7 issuance, 9 local door, 3 recipient verification |
| Term and epoch | 1.3 floor, 3.2 slot epoch, 8.8 holder term |
| Ceilings (M10/10 N1.4, M11/12 N1.5) | Row: 1; YAML/JSON-Schema depth: 2.1; client blob 32 MiB, console body/json, JSON depth 64, idempotency key/rid 200 bytes, name/key 1024 bytes, cleanup list 64: 6; worker rid and request-mark error: 3.6; body copy 64 MiB, object/events/retention/max_bytes: 5; domain: 8.10/9 |
| Lifecycle | 1.3 daemon, 2.4 units/environment; exit codes/schema check with each process |

## Contracts

```text
Platform/
  README.md                           lesson index
  lessons.tsv                         lesson number P/NN -> process directory
  module-design.md
  NN-<process>/                       01-store through 10-domain-console
    ru/NN-<process>.md                lecture for people, not exported
    spec/NN[.K]-<process>.norms.md     norms, chapters .K
    spec/NN-<process>.api.openapi.yaml doors
    spec/NN-<process>.library.md       library contract (3, 7; embedded agent: local-token-door in-process call, addendum (14))
    spec/NN-<process>.README.md        implementation instructions
    lifecycle.md                      flags, environment, exit codes, service units
    data/<family>.schema.json         owned-family JSON Schema 2020-12 and V7 layers (ADR-0092/0088)
    vectors/<algorithm>/              introduced algorithm vectors
    acceptance/[K/]                  acceptance
  common/
    data/catalog.tsv                  template/path, owner, operations/participants, readers, ...
    vectors/README.md                 index by owner
    acceptance/system/  acceptance/matrix/
Platform/common/data/testsub/         canonical course test manifests (ADR-0083 (115))
Platform/02-installer/acceptance/1/spec_verdicts/  course-owned legacy verdict witnesses
Source/tests/testdata/                immutable Source witness copies, not canonical input
decisions/history/platform/           historical id-map.tsv, manifest-rename.tsv, explanations/
decisions/journal/platform/           historical lesson/common correction journals (ADR-0121 (9))
```

## Vectors

The owner is the first contract's location.

| Vector | Owner and participants |
|---|---|
| JCS (`canonical_json.tsv`) | 1 |
| `values_by_type` text forms | 6 |
| Request body serialization (`requests_body.tsv`), rid (`rid.tsv`) | 6, participant 3.6 |
| Request digest: sender kind, normalized input, SHA-256 | 6, participant 3.6; separate vectors |
| Event id | 5 |
| `cut_at: host` (`group_of.tsv`) | 4 |
| Label-set shortage and per-server order (`Platform/04-controller/vectors/order/`) | 4 |
| Shrink victim (`Platform/04-controller/vectors/shrink-victim/`) | 4 |
| Fault vocabulary (`fault.tsv`) | 6, participants 4, 10 |
| Secrets and masking (`secret_in.tsv`, `log_mask.tsv`) | 6.2, participants 2.1 credentials/secret_in and 2.4 URL parsing |
| Platform secret rows (`platform_lists.tsv`) | 2.5 |
| Manifest corpus (`Platform/02-installer/acceptance/1/`) | 2.1 |
| Rights evaluator | 1.2 |
| Rights derivation | 2.5 |
| URL parsing | 2.4 |
| Requested-worker script (`Platform/02-installer/vectors/workers-script/`) | 2.4 |
| Store copy | 1.3 |
| enc:v2, AAD path, opening and ring (`Platform/common/vectors/sealing/`) | Common sealing contract; participants 2.4, 3.5, 6.2, 8–10 |
| view (`Platform/08-domain/vectors/view/`) | 8.1 |
| Root/set/token (`Platform/common/vectors/domain-token/`) | Domain-token contract, 8.2 |
| x25519:v1/m1 opening and round trip (`Platform/common/vectors/domain-envelopes/`) | Common domain-envelopes contract, owner 8 (8.2 x25519:v1, 8.3 m1); participants 8.5, 8.7, 8.8, 9.1, 9.2 |
| keys(pinned, held, offered), revoked pruning (`Platform/common/vectors/keys/`) | Common keys contract, owner 8.2; participants 6.3, 8.8, 9.1, 9.2 and token verifiers |
| agent-sig (`Platform/common/vectors/agent-sig/`) | Common agent-signature contract, owner 9.1; verified by 6.3, 8.3, 8.7, 9.2 |
| accept and roads (`Platform/common/vectors/accept/`) | Common accept contract, owner 8.3, participant 9.2 |
| assemble (`Platform/08-domain/vectors/assemble/`) | 8.5 |
| issue (`Platform/08-domain/vectors/issue/`) | 8.7 |
| Grant may (`common/vectors/may/`) | Common may contract, owner 8.4; participants 6.3, 6.7, 10, ADR-0083 (14) |
| record (`Platform/common/vectors/record/`) | Common record contract, owner 8.8; participants 6.7, 8.7, 9.1 |
| ask-sig (`Platform/common/vectors/ask-sig/`) | Common ask-sig contract, owner 8.8; participant 6.7 |
| follow (`Platform/09-agent/vectors/follow/`) | 9.1 agent execution; stage A 8–10 finding 8 |
| alarms (`Platform/10-domain-console/vectors/alarms/`) | 10; 8.9 writes history, stage A 8–10 finding 8 |
| resolve (`Platform/06-console/vectors/resolve/`) | 6, late chapter 6.7 |
| op-step (`Platform/06-console/vectors/op-step/`) | 6, chapter 6.9, ADR-0095 |
| key-families (`Platform/06-console/vectors/key-families/`) | 6, late chapter 6.7 N1.11 families, C06-DOMAIN-KEY-FAMILIES-168-21 |
| peer (`Platform/common/vectors/peer/`) | Common peer contract, owner 9 (agent to HTTPS first); participants 6.7, 8.8, 10; stage A 6–7 finding 28 and A 8–10 finding 7 |
| Console acceptance | 6, late chapter 6.7, common forwarding contract; participants 8, 10 |

The module's `console.may` is a session-grant UI hint under P/07 N1.5, not the 8.4 may algorithm or a participant in its vector package (lesson 7 migration, Architect decision on report question 3).

## Migration — historical plan

1. **Done:** ADR-0083 (1)/(2), store pilot and note reviews.
2. **Owner approves the note.**
3. **Stage A.**
   - Specification extracts the data/file/lifecycle catalogue from M10/M11 norms.
   - Shared vectors: compare every row to current norms; request digest gets its own vectors.
   - Add Data paragraphs to M10/M11 norms so read-without-catalogue-row checking can proceed lesson by lesson.
   - Complete norm id map, not only family ids, as stage B input.
   - Extract the course normative vocabulary and retarget links.
   - Specify ring-file format and worker presence lock, removing the M10/11 implementation-choice exemption.
   - Put the compatibility matrix in runners.
   - Make catalogue-free reads a check_spec error and compare rights with the catalogue.
   - Second pilot: mixed worker SDK, controller, resource and console.
4. **Canonical manifest view form:** settled by ADR-0089 (1)/(2); writing it is separate work after lesson 2 migration (item 6).
5. **Stage B: lessons in owner-address order 1 → 10, without behaviour changes.**
   - One lesson commit includes norms, OpenAPI, library contract, acceptance and historical id-map updates.
   - Remove former locations and repair links in the same commit.
   - Early lessons' late-layer chapters migrate with the later lesson.
   - Export both trees and run generators after every three lessons.
   - **Migration criterion: self-containment** (ADR-0083 (5)). The lesson plus neighbours' public contracts (OpenAPI, data catalogue, vectors, lifecycle, library contracts and common) gives the process everything needed about a neighbour. Move knowledge found only in neighbour norms into a contract. A lesson still requiring another process's norms has not migrated.
   - **Subsystem manifest (ADR-0086 (1)).** `<name>.subsystem.yaml` is the subsystem manifest; lesson 2 is Subsystem manifest and strict loader. Transition is the **last stage B commit**, after all lessons and before the first C export (R1). Prose, norms, acceptance, catalogue, OpenAPI, console module, checks and skills change together through the closed manifest-rename table (old→new→owner→consumers, R2). Reserve manifest wherever spec was reserved and add corpus cases (R3); rename 2.1's form source too (R4; ADR-0085's pair was removed by source migration). This transition was completed at the end of B. Accepted ADR text is not rewritten; supplement ADR-0071 for plugin manifests and add the glossary entry. Old course code stays a witness outside the transition (R6); the product owes Build an ADR-0086 debt (R7).
   - **Lesson 2 form-source migration (ADR-0087 (1)–(5)).** Separate source migration commit, addendum (1) R9, completed by lesson 2 migration commit B: `Platform/02-installer/spec/02.1-installer.*`, chapter Form section. Builder tests retain decisions outside the manifest form: F9, F18, O3, O6, O7, O9, O10, O12, O15. Together with it:
     - 17 norms from the journal-dialect decision digest become explicit decision records (2026-10-19 inbox digest).
     - Corpus coverage findings: references.tsv rows 59, 62, 63, 39, 40, 43, 44, 49–52, 54, 56 require the table to be declared (`when <table> in keys(tables)`); remove row 84; resolve an @path below variants through the tree value, and refuse a row lacking a source case (O3); a nested `{` in template is refused by the row class (O14).
     - Refusal paths are a canonically ordered set, addendum (3) R2.
     - The text layer provides line map and refusal path, addendum (3) R4.
     - Strict corpus coverage of references, addendum (1) R10.
     - Remove copied M10/11 N1.6 TLS peer-verifier lines from installer: issuance stays in 2.4, verification in store (Architect decision on lesson 1 migration).
     - GET /manifest (M10/9-15), ManifestView and ConsoleRefusal moved **temporarily to M10/9** until 6.5 migration, preserving lessons 9/10 OpenAPI refs. Installer has no OpenAPI (stage A 2 review, P10).
     - Canonical defaults follow the 2026-10-19 inbox defaults note and ADR-0089 (2): do not inject events.suppress.by; default:null for fields lacking a default, including blob. Narrow the N1.2a default for display.unit/units/units_count/section/general to the first three; section/general have no default, as in M10/9 N1.2.
   - **Lesson 6 migration:** 6.5 takes GET /manifest from M10/9 and reconciles the M2_* copies at /{sub}/manifest and /mounts with M10/2's original: Retry-After is a string; original ManifestView is stricter (Architect decision on lesson 2).
6. **Separate behaviour changes** follow the owner lesson: tolerant reader, canonical view, array order and relay extraction if chosen.
7. **Shared data:** the historical plan proposed Platform/common/testdata for testsub and owner vector directories for shared tables. The current course testsub canon is `Platform/common/data/testsub/`; the legacy verdict package is `Platform/02-installer/acceptance/1/spec_verdicts/` (ADR-0083 (115)). Specification owns the canonical bytes independently; Source copies remain immutable witnesses, and no product synchronization is required.
8. **Former M10/M11 directories removed on 2026-10-21.** where-the-database-lives.md remains at course root; the M10 design note's form rules moved into the lesson-spec checklist. cammeta-specs exports Platform.
9. **Stage C: regenerate by micromodule** after stage B (ADR-0083 (5)).
   - A micromodule generator reads its own lesson and neighbours' shared OpenAPI/catalogue/vectors/lifecycle/library/common contracts, never other processes' norms.
   - First one language, then another; then-current cammeta-python/cammeta-go remain witnesses until comparison, like old implementations under ADR-0080 addendum 16.
   - A gap found in a neighbour's contract is a stage B contract defect, not permission to read its norms.

# P/08 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/08-domain.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/08-domain.md` (for people, not in the export).

Scenario names (`sc. NN`), vector case names and fixture names identify the judge's checking data; scenarios, fixtures and expected results are not provided to the model. All implementation obligations are stated in the visible norms and contracts.

## Task

Implement the process `domain` of the domain holder in the language `<LANG>`: the door of the process, the domain trust, the acceptance of reports, the view and
the shadow report, people and grants, books, placement and edits, the issue of tokens, the term and the move, the shared document and the alarm
history, the queue — by the eleven chapters of the lesson; pass the N5 acceptance of the chapters and close their readiness checklists. 90 norms in all:

<!-- checklist-inventory:begin -->

| chapter | ids |
|---|---|
| 8.0 | `P/08.0-01`, `P/08.0-02`, `P/08.0-03`, `P/08.0-04`, `P/08.0-05` |
| 8.1 | `P/08.1-01`, `P/08.1-02`, `P/08.1-03`, `P/08.1-04`, `P/08.1-05`, `P/08.1-06`, `P/08.1-07`, `P/08.1-08`, `P/08.1-09`, `P/08.1-10`, `P/08.1-11` |
| 8.2 | `P/08.2-01`, `P/08.2-02`, `P/08.2-03`, `P/08.2-04`, `P/08.2-05`, `P/08.2-06`, `P/08.2-07`, `P/08.2-08`, `P/08.2-09`, `P/08.2-10`, `P/08.2-11` |
| 8.3 | `P/08.3-01`, `P/08.3-02`, `P/08.3-03`, `P/08.3-04`, `P/08.3-05`, `P/08.3-06`, `P/08.3-07`, `P/08.3-08`, `P/08.3-09`, `P/08.3-10`, `P/08.3-11`, `P/08.3-12`, `P/08.3-13`, `P/08.3-14` |
| 8.4 | `P/08.4-01`, `P/08.4-02`, `P/08.4-03`, `P/08.4-04`, `P/08.4-05`, `P/08.4-06`, `P/08.4-07`, `P/08.4-08`, `P/08.4-10`, `P/08.4-11`, `P/08.4-12`, `P/08.4-13`, `P/08.4-14`, `P/08.4-15`, `P/08.4-16`, `P/08.4-09`, `P/08.4-17` |
| 8.5 | `P/08.5-01`, `P/08.5-02`, `P/08.5-03`, `P/08.5-04`, `P/08.5-05` |
| 8.6 | `P/08.6-01`, `P/08.6-02`, `P/08.6-03`, `P/08.6-04`, `P/08.6-05` |
| 8.7 | `P/08.7-01`, `P/08.7-02`, `P/08.7-03` |
| 8.8 | `P/08.8-01`, `P/08.8-02`, `P/08.8-03`, `P/08.8-04`, `P/08.8-05`, `P/08.8-06`, `P/08.8-07`, `P/08.8-08`, `P/08.8-09`, `P/08.8-10`, `P/08.8-11` |
| 8.9 | `P/08.9-01`, `P/08.9-02`, `P/08.9-03`, `P/08.9-05`, `P/08.9-06` |
| 8.10 | `P/08.10-01`, `P/08.10-02`, `P/08.10-03` |

<!-- checklist-inventory:end -->

The inventory is built from the readiness checklists below; all 90 full ids must occur exactly once. P/08.9-04 is free: the alarm list at the holder is P/10-06 of lesson P/10.

The lesson covers the holder side.
The member agent and the relay — lesson P/09, the domain console — lesson P/10, the late layer of the cluster
console — [chapter 6.7](../../06-console/spec/06.7-console.norms.md), the worker on the domain — [chapter P/03.7](../../03-worker/spec/03.7-worker.norms.md).

- **8.0.** The door `SIGNER_URL`: one writer of the holder rows, the acceptance of the edits that the domain console passes
  (`X-W2C-Client` — only from a connection of the role `domainconsole`), the answers `deposed`, `frozen`, `standby` by its own word,
  the server side of the class `signed` — [chapter 8.0](08.0-domain.norms.md).
- **8.1.** The holder's pass, which brings the copies of the members together into the domain view and the shadow report, and the command `view` for the acceptance —
  [chapter 8.1](08.1-domain.norms.md). The domain writes nothing into the members; the doors of the view are answered by the domain console (lesson P/10).
- **8.2.** The domain trust: the acceptance function of the set `domain/keys` (`keys`), the token check (`token`), sealing and
  opening the envelope `x25519:v1`, the holder key rows, three key changes — [chapter 8.2](08.2-domain.norms.md). The chapter has no
  HTTP doors of its own; the domain installation is built by [P/02.4](../../02-installer/spec/02.4-installer.norms.md) (P/02.4-10).
- **8.3.** The acceptance of the member reports by generations, the holder's answer and the envelope `m1`, the holder side of the two-sided acceptance of a member
  (`POST /domain/members` through the domain console); the topology with an edit door, the relay package and the rule of two roads;
  the CA prints in the member entry — [chapter 8.3](08.3-domain.norms.md).
- **8.4.** People at the holder and the login that issues a person token; the attempts limit; the grant rows of each cluster and of the
  domain doors; the right — by the function `may` at the doors of the process; the emergency row of the cluster in the answer to the agent —
  [chapter 8.4](08.4-domain.norms.md).
- **8.5.** The assembly of books in the view pass, the delivery of the entry to the member, the mask; the names index and its checks at the doors of people and grants —
  [chapter 8.5](08.5-domain.norms.md).
- **8.6.** Placement by the operator (the holder record, the counter, the answer to the agent only with the records that name the member),
  the acceptance of an edit of a member unit with the refusals of chapter 8.1, stored edits for a switched-off member, outcomes and `settle` —
  [chapter 8.6](08.6-domain.norms.md).
- **8.7.** The holder door for token requests, the issue by scopes in order, the claims and the signature, the answer in the envelope
  `m1` — [chapter 8.7](08.7-domain.norms.md).
- **8.8.** The term and the term record; the backup copy at the keepers; the deposed holder and the stranded; the planned handover;
  the emergency move by the recovery file — [chapter 8.8](08.8-domain.norms.md). The members follow the larger term by themselves
  (lesson P/09).
- **8.9.** The shared document: the edit, the object and the pointer, the re-signing after a move, `shared` in the answer to the agent,
  «delivered to how many»; the alarm history in the pass — [chapter 8.9](08.9-domain.norms.md).
- **8.10.** The queue `domain/signer-turn` and the guard of every write, the standby process, giving up the queue on `SIGTERM`; the ceilings:
  the ceiling of the section row, `SERVERS_MAX`, `ENTRY_MAX`, `whole` — [chapter 8.10](08.10-domain.norms.md).

## Inputs and their priority

- The canon is the norms of chapters [8.0](08.0-domain.norms.md), [8.1](08.1-domain.norms.md), [8.2](08.2-domain.norms.md),
  [8.3](08.3-domain.norms.md), [8.4](08.4-domain.norms.md), [8.5](08.5-domain.norms.md), [8.6](08.6-domain.norms.md),
  [8.7](08.7-domain.norms.md), [8.8](08.8-domain.norms.md), [8.9](08.9-domain.norms.md), [8.10](08.10-domain.norms.md),
  including N0, the paragraphs «Data», the order of N3 and the refusals of N4. The input and the output of the acceptance commands — N5 of the chapters.
- The common algorithms are contracts; the chapters refer to them and do not repeat them: [the key set](../../common/contracts/keys.md),
  [the domain token](../../common/contracts/domain-token.md) and [the domain envelopes](../../common/contracts/domain-envelopes.md)
  (`x25519:v1`, `m1`, the content of `sealed`) — chapters 8.2, 8.3; [the report acceptance](../../common/contracts/accept.md) and
  [the agent signature](../../common/contracts/agent-signature.md) (the holder is the verifier) — chapter 8.3;
  [the right](../../common/contracts/may.md) — chapter 8.4; [the term record](../../common/contracts/record.md) and
  [the ask signature](../../common/contracts/ask-sig.md) — chapter 8.8; [the local token door](../../common/contracts/local-token-door.md)
  — chapter 8.7; [the forwarding](../../common/contracts/forwarding.md) («Client address», «Domain doors») and
  [the role certificate](../../common/contracts/role-certificate.md#the-server-side-the-class-signed) — chapter 8.0; the holder
  ring and the envelope `enc:v2` — [the sealing contract](../../common/contracts/sealing.md).
- [OpenAPI](08-domain.api.openapi.yaml) expresses the HTTP forms of the canon of all the chapters: one door of the process — one contract.
  The own doors of the process and the doors that the domain console and the cluster console pass to it stand in it with the codes of the process:
  N3 of the doors, 401/403 of its own check of identity and grant, 409 `deposed`, 503 `frozen` and `standby`. The codes of the hop
  (the gate of the console, 502) are carried by the contracts of the consoles (lesson P/10, chapter 6.7). `X-W2C-Client` at the doors that
  the domain console passes — by a reference to the forwarding contract. The schemas of the bodies of the agent publication and of the relay package, of the edits, of the view and
  of the shadow report — the original is here: the agent (lesson P/09) and the domain console (lesson P/10) read them from here.
- The forms of the rows and objects of the lesson are the family schemas `../data/*.schema.json` (the sections «Data families» of the chapters); the forms
  shared by a holder row and its copy at the agent — the common definitions (`common/data/common.schema.json` for reference; each
  family schema is self-contained).
- The acceptance of the chapters checks the norms: [8.1](../acceptance/1/README.md), 8.2 (the vectors of the common packages — [N5 of the chapter](08.2-domain.norms.md)),
  [8.3](../acceptance/3/README.md), [8.4](../acceptance/4/README.md), [8.5](../acceptance/5/README.md),
  [8.6](../acceptance/6/README.md), [8.7](../acceptance/7/README.md), [8.8](../acceptance/8/README.md),
  [8.9](../acceptance/9/README.md), [8.10](../acceptance/10/README.md); chapter 8.0 has no catalogue (N5). The stand of several
  clusters, the directives and the doors — [the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors).
  The vectors of the lesson — [`view`](../vectors/view/README.md) (8.1), [`assemble`](../vectors/assemble/README.md) (8.5),
  [`issue`](../vectors/issue/README.md) (8.7); the common ones  — `keys`,
  `domain-token`,
  `domain-envelopes` (8.2, 8.3),
  `accept`, `agent-sig` (8.3),
  `may` (8.4), `record`,
  `ask-sig` (8.8). Flags, environment, exit codes — [`../lifecycle.md`](../lifecycle.md).
- The lecture (`ru/08-domain.md`, for people, not in the export) explains the mechanism and examples.

The internal interfaces, types, error classes, libraries and the division into components are chosen by the implementation. The acceptance commands
(`view`, `keys`, `token`, `seal`, `seal-round`, `accept`, `agent-sig`, `seal-member`, `seal-member-round`, `may`,
`assemble`, `issue`, `record`, `ask-sig`) call the functions of N3 of the chapters and of the contracts without the store and the network; their names and call
templates — the items «Implementation decides» of the chapters.

**On a discrepancy.** Name the norm id, the input, the initial state, the expected and the obtained outcome. First check which
chapter or lesson the rule belongs to: the door of the process — chapter 8.0; the set, the token, the envelopes — chapter 8.2 and the contracts; the acceptance —
chapter 8.3 and the report acceptance contract; the agent and the relay — lesson P/09; the view doors, the gate of the domain and the passing of edits — lesson
P/10; the forwarding to the signer, the session with grants, the emergency login — chapter 6.7; the contribution under the slot and the token check
by the recipient — P/03.7; the declarations `domain.*` — P/02.1; the domain installation, the ports and the units — P/02.4; the rights of the roles — P/02.5.
If the implementation is wrong — fix it and repeat the related checks. If the norm, the contract or the expectation diverge —
report to the Specification the place, the counterexample and the proposed decision; the decision is reflected in the norm, the contract, the instructions and
the affected acceptance. Do not carry a difference of the implementation into the canon silently; do not add a new mechanism only for the sake of
an unsupported case. Record a change of the acceptance in `corrections-<K>.tsv` (historical correction record) of its chapter.

## Glossary

Some words of the norms have more than one meaning; the place of the word tells them apart. This table adds no rule and renames nothing: each meaning is the one the named place already gives.

| Word | Meanings | How to tell them apart |
|---|---|---|
| `domain` | (1) the domain: a set of member clusters under one root of trust (chapter 8.1 N1.1); (2) the process `domain` of the holder: the door `SIGNER_URL`, the role `W2C_ROLE=domain`, the queue `domain/signer-turn` (chapter 8.0 N1.8, chapter 8.10 N1.7, [lifecycle](../lifecycle.md)); (3) the prefix of the families `domain/*`: the rows and objects at the holder and the copies at a member (the paragraphs «Data» of the chapters); (4) the grant row `domain/grants/domain`: the grants of the domain doors (chapter 8.4 N1.3, N1.5); (5) the section `domain` of the manifest: `domain.witness`, `domain.shared` (P/02.1 N1.2b); (6) the field `domain` of a signed document: the name of the domain (chapter 8.9 N1.2 `document`) | «the process `domain`», a door, a start or the queue — the process; a key `domain/<…>` — a row or an object; `domain/grants/domain` — the grants of the domain doors; `domain.<key>` of a manifest — the manifest section; a field `domain` inside a document — the name |
| holder | (1) the role of a member: exactly one member on which the services of the domain run (chapter 8.1 N1.1; which member — chapter 8.8); (2) the term record `domain/holder` (chapter 8.8 N1.1) and the field `holder` of the head of the view (chapter 8.1 N1.4b); (3) the field `holder` of the row `domain/signer-turn`: the instance `<box>:<pid>:<6 hex>` of the active process `domain` (chapter 8.10 N1.7) | prose «the holder» — the member in its role; `domain/holder` — the term record; `holder` of `domain/signer-turn` — a process instance, not a member |
| member | (1) a cluster accepted into the list of members of the domain: `domain/member-rows/<part>` at the holder (chapter 8.1 N1.1, chapter 8.3 N1.1), its agent and its member key (chapter 8.3 N1.1); (2) a person or a group in `members` of the row `domain/groups/<name>` and in `assigned` of a role (chapter 8.4 N1.3a, N1.3b) | a cluster name, a report, a copy, the list of members — a cluster; `members` of a group or a role line — people |
| copy | (1) the copy of a member at the holder: what the holder last accepted from the member, the generation and the mark `reported` (chapter 8.1 N1.1, chapter 8.3 N1.3); (2) a member's copy of a holder row written by its agent: the grants (`as_of`, `GRANT_LIFETIME`, chapter 8.4 N1.3), the placement records (chapter 8.6 N1.2), the shared document (chapter 8.9 N1.6); (3) the backup copy of the domain at the keepers (chapter 8.8 N1.5, N1.5a); (4) the field `copies` of a placement record: the executors besides `cluster` (chapter 8.6 N1.1; chapter 8.1 N1.4) | at the holder about a member — (1); at a member about a holder row — (2); «backup copy», the keepers — (3); `copies` next to `cluster` and `origin` — (4) |
| view | (1) the domain view: the objects `domain/view` and `domain/view-rows/<part>` of the holder's pass (chapter 8.1 N1.4, N1.4b) and its fields `view.<field>` owned by other chapters (chapter 8.1 N1.2a, N1.6a, N1.7; chapter 8.5 N1.5; chapter 8.8 N1.3; chapter 8.9 N1.6); (2) the right `view` of a grant line: reading (chapter 8.4 N1.3, N1.4); (3) the command `view` of the acceptance and the vectors [`view`](../vectors/view/README.md) (chapter 8.1 N5); (4) the view doors that the domain console answers (lesson P/10 N1.2) | an object, a key `domain/view…` or `view.<field>` — (1); `view` next to `edit`, `admin` in a grant or `may` — (2); «the command `view`» — (3); «the doors of the view» — (4) |
| report | (1) the member's report: the publication `POST /api/member/<member>` accepted by generations, with the mark `reported` (chapter 8.3 N1.3); (2) the shadow report: the object `domain/shadow` of the holder's pass (chapter 8.1 N1.6) | «shadow report» or `domain/shadow` — (2); otherwise — (1) |
| key | (1) the root key of the row `domain/root` (chapter 8.2 N1.1); (2) the keys of the set `domain/keys`: the token keys and the book acceptance key `book_seal` (chapter 8.2 N1.2, N1.4); (3) the holder keys in `domain/signer`: `issuing_key_secret`, `backup_key_secret` (chapter 8.2 N1.3; chapter 8.8 N1.5); (4) the member key `domain/member-key` (chapter 8.3 N1.1); (5) the key of a row in the store (the column `key` of the catalog) and the header `Idempotency-Key` (chapter 8.0 N1.9) | the qualifier names it: root, set, token, book acceptance, issuing, backup, member; a path of a row — the store key; a header — the repeat memory |
| term | (1) the holder's term: the number of the term record `domain/holder` (chapter 8.8 N1.1) and the pair (term, rev) of the rows and documents written in it (chapter 8.5 N1.3, chapter 8.9 N1.2); (2) a duration: `TURN_TERM` of the queue (chapter 8.10 N1.7), «the term of former keys» `until` (chapter 8.2 N1.6, N1.6a), the term of a role line and of an assignment (chapter 8.4 N1.3a), «a request lives by a term» (chapter 8.5 N1.4) | an integer `term` or a pair (term, rev) — (1); a constant, `until`, «lives by» or «has run out» — (2) |
| root | (1) the root of trust: the row `domain/root` and its key (chapter 8.2 N1.1), `kid` `root` of a `keep` document (chapter 8.2 N1.6a); (2) the root of the domain folders: `""` in the place of a folder id (chapter 8.5 N1.8); (3) the person `root` of the stand: the first administrator that `@install domain` creates (the [acceptance of chapter 8.4](../acceptance/4/README.md)) | `domain/root`, a fingerprint, a signature — (1); a folder — (2); a stand directive or a login — (3) |
| token | (1) a domain token by the domain token contract: the worker tokens of the door `/api/tokens/…` (chapter 8.7 N1.3, N1.4), the person token of `POST /api/login` (chapter 8.4 N1.2), the tokens `keep` (chapter 8.2 N1.6a); (2) the field `token` of an admission batch: the private Ed25519 key of the batch, shown once (chapter 8.3 N1.1b); (3) the function and the command `token`: the check of a domain token (chapter 8.2 N1.6, N3) | a token with claims, `kind` and `Authorization` — (1); `token` in the answer of a batch — (2); `token(…)` or a vector command — (3) |
| unit | (1) a unit of a subsystem: `units` of the view and its name in the domain (chapter 8.1 N1.2, N1.4); (2) the system unit of the process (the [lifecycle](../lifecycle.md)); (3) the column `unit` of `forms/runtime-constants.tsv`: count, s, bytes | a unit id, a subsystem, a placement — (1); a service, a start, a user — (2); a constant — (3) |
| mark | (1) the mark `reported` of the copy of a member: the generation that the holder accepted, refreshed by `MARK_REFRESH` (chapter 8.3 N1.3); (2) the deletion mark `domain/deleting/<name>` of a person (chapter 8.4 N3) | `reported`, a generation, `rev` of a road — (1); a person and its deletion — (2) |

## What to create

- **8.0.** The door `SIGNER_URL`: accept the edits of the domain console as they came, check the identity and the grant itself (chapter 8.4);
  read `X-W2C-Client` only on a connection of the role `domainconsole` ([the forwarding contract](../../common/contracts/forwarding.md)
  «Client address»); its own refusals `deposed`, `frozen`, `standby` — by its own word in `error`. The server side of the class
  `signed` — [the role certificate contract](../../common/contracts/role-certificate.md#the-server-side-the-class-signed)
  (do not require a client certificate and do not give it rights; requesting it is optional, and a presented one is checked in the
  handshake — its own CA, the validity, EKU `clientAuth`, otherwise an alert).
- **8.1.** The holder's pass of N3: the domain view (the head once every 3 s, the sections in a round) and the shadow report, the objects `domain/view` and `domain/shadow`; the view fields
  of the other chapters by the same pass. The command `view` with the same function without the store; its call is the door `view` of the vocabulary of the
  «Domain stand».
- **8.2.** The functions of N3 `keys`, `token`, the opening and the sealing of `x25519:v1` — one and the same for the agent, the gate, the token
  door and the assembly of books (chapters 9.1, 6.3, 8.7, 8.5, 8.4). The rows `domain/root`, `domain/keys`, `domain/signer`,
  `domain/book-seal`, `domain/revoked` by N1.1–N1.6 and the families; the writer is the process `domain`, at a member — the agent
  (`domain/root` — only `admin`). The calls of the changes of N3. The acceptance commands `keys`, `token`, `seal`, `seal-round`.
- **8.3.** The doors `POST /api/member/<member>`, `GET /api/carry/<member>`, `POST /api/relay/<relay>`; the function «accept»
  ([the report acceptance contract](../../common/contracts/accept.md)) with a mutex per member, with `via` and `heard_ago`; the knock `knock` and
  the knocks from a package; the holder in the list; the view fields `knocking`, `reports`. The acceptance of `tls_ca` into `Entry.ca` and of
  `tls_ca_certs` into the row `domain/members/<member>/ca-certs` before it. `members` in the answer only to the one lagging behind; 409
  `too many members` at the acceptance of a member. The edits of the list (`POST`/`DELETE /domain/members`, `POST /domain/members/<member>/ca`)
  and of the topology (`PUT /domain/topology`) come through the domain console (chapter 8.0); the acceptance of a member of N3 and the write of the topology
  are executed by the process. The commands `accept`, `agent-sig`, `seal-member`, `seal-member-round`.
- **8.4.** The rows of people and `domain/disabled`, the deletion mark `domain/deleting/<name>` and the reconciliation by it at every pass;
  `POST /api/login` and the attempts limit; the doors of people, of emergency passwords, of grants and of revocation — with the check of the token and of the grants
  of the domain at itself; the command `domain first-admin`; in the answer to the agent — `grants` without the switched-off ones and `break_glass` in `sealed`
  (the form — the domain envelopes contract; the sealing of the answer — chapter 8.3); the command `may`.
- **8.5.** The assembly of N3 in the view pass, the rows `domain/<sub>/<book>/<member>`, `view.books`, the delivery into `sealed.books`;
  the names index `domain/names/<sub>/<book>` after the assembly of the books of the pass and its checks at the doors of people and grants; the delivery
  by the rank of the grant, `person_names` in the view; the command `assemble`.
- **8.6.** The doors of N2 of chapter 8.6 that the domain console passes (the write and the deletion of a placement, the edits) — the acceptance by chapter
  8.0; the rows `domain/placement`, `domain/placement/<sub>/<ref>`, `domain/pending/<member>`, `domain/outcomes/<member>`.
  The fields of the answer to the agent `placement` (only the records that name the member, under the mutex of the record; the raise of the counter at start) and
  `pending` (chapter 8.3 N1.5); the outcomes of N1.6; the view fields `pending`, `outcomes`.
- **8.7.** The door `/api/tokens/…`, the issue of N3 in order, the claims of N1.4, the signature by the token key, the answer in the envelope `m1`;
  the command `issue`.
- **8.8.** The term record and `claim`; the backup copy and the pointers of the keepers, `backup` in the answer to the agent; the look at its own
  store and the yielding, 409 `deposed`, `forgotten`, `domain/stranded`; the handover (the freeze, `prepare`, `take`) and the acceptance of
  the handover; the emergency move; `backup_key_secret` and `backup_key_rev` in `domain/signer` (chapter 8.2 N1.3, the installation —
  P/02.4). The commands `record`, `ask-sig`; `w2cctl domain move`.
- **8.9.** The edit of the shared document in the order of N1.3, the object and the pointer; the re-signing after a move (N1.2 `after_move`);
  `shared` in the answer to the agent (N1.4 `carry`); `view.shared` — «delivered to how many» (N1.6); the alarm history in the pass (N1.9).
- **8.10.** The queue `domain/signer-turn`: the guard of every write into the holder rows, the objects — after the confirmation of the queue;
  the standby — 503 `standby` at all the doors; giving up the queue on `SIGTERM`. The ceilings: 413 `whole too large`; 409
  `too many members` and «the entry of \<member> would exceed 1240 bytes» at any write of `domain/member-rows/<part>`.
- The description of all the choices of the sections «Implementation decides» of the chapters — 20 items «Implementation decides» in all — and the means of
  executing the acceptance: the vector commands and the stand directives.

## Order of work

This is a proposed order, not an obligatory structure of the code. The chapters go in the reading order of the lesson: 8.0, 8.2, 8.3, 8.1,
8.4–8.10; the queue of chapter 8.10 is built together with the door of the process.

### Chapter 8.0 — the doors of the process

1. The door of the process and the acceptance of the domain console edits (N1.8) — before the chapters whose doors it carries.
2. The queue of the process `domain` and the guard of the writes ([chapter 8.10](08.10-domain.norms.md) N1.7) — before the first holder pass:
   every write needs the guard.
3. The server side of the class `signed` by the role certificate contract.
4. The evidence of N5 of the chapter: the acceptance of edits — scenarios 01, 02 of chapter 8.3; the answers `deposed`, `frozen`, `standby` — the stands
   of chapters 8.8 and 8.10; `X-W2C-Client` and the class `signed` — by reading.

### Chapter 8.2 — the root, the set, the token, the envelope

1. JCS (RFC 8785), base64url without `=`, hex — common helpers; the signature of the set — over the JCS of the document without `kid` and `sig`.
2. `keys` — the steps of the set contract in order: the first rule that fires gives the word.
3. `token` — the steps of the token contract in order; the clock — the wall clock of the verifier; the boundary `exp + 60` accepts.
4. The envelope `x25519:v1`: the seed — the X25519 scalar as it is; HKDF with the salt `eph ‖ book_seal`; AAD — the JCS of the triple, `0x00`, JSON
   Pointer.
5. The changes of N3: the key row and the set in one batch; the recovery file — with the check of the mode 0600 at every read.
6. The vectors of N5 of the chapter (the packages `keys`, `domain-token`, `domain-envelopes`) by the commands `keys`, `token`, `seal`, `seal-round`.

### Chapter 8.3 — acceptance of reports

1. The check of the agent signature ([the agent signature contract](../../common/contracts/agent-signature.md), `agent-sig`): the window in
   both directions, the path without a query.
2. The envelope `m1` ([the domain envelopes contract](../../common/contracts/domain-envelopes.md), `seal-member`): the birational
   map of the key, SHA-512 of the seed, HKDF, AAD.
3. «Accept» ([the report acceptance contract](../../common/contracts/accept.md), `accept`): the order of the steps, 409 of three kinds,
   `heard` and `MARK_REFRESH`, the order of the writes of the object, `.delta` and the marks.
4. «Accept» with a road (`accept` with `via`, `heard_ago`): steps 2, 2a, 3 of the report acceptance contract.
5. The acceptance of a member of N3 and the holder in the list; the topology of N1.2: the form, the refusals, CAS by `base_rev` and `If-Match`, the JCS of the text `doc`.
6. The holder on a package of N3: the topology, `refused`, the answer with `rev` for this road.
7. `tls_ca` → `Entry.ca`, `tls_ca_certs` → `ca-certs` and the administrator door.
8. `members_rev`: `members` in the answer only to the one lagging behind; the ceilings of chapter 8.10 — together with the acceptance of members.
9. The stand: the scenarios of [the acceptance of the chapter](../acceptance/3/README.md).

### Chapter 8.1 — the view and the shadow mode

1. The freshness of N1.3: a change of the mark and of the heartbeat — on the holder's monotonic clock; the first look at the mark is not a change (the member
   `unseen`), at the heartbeat — a change; `LOST_AFTER` 45 s.
2. The view of N1.4: the units from the heartbeats, then from the shards of the snapshot without repeats of id (a row without the value `domain.ref` is not a unit);
   the placements — by one read per pass (N3 step 3a); `contested` except the ref of the executors; the order (cluster, id);
   `contested` before `complete`.
3. The shadow report of N1.6: the claims from `status[]` with ref by the shard of its own member; the memory of the time of a change of `observed_revision` per
   pair; `clean_streak` is reset by any finding and by `unknown`.
4. The command `view`: the input and the output — N5 of the chapter and the OpenAPI; each pass of the input is one holder pass.
5. The view fields of the other chapters (N1.2a, N1.6a, N1.7) — by the same pass; the fields `books`, `pending`, `outcomes`, `term`, `shared` —
   by chapters 8.5, 8.6, 8.8, 8.9.
6. The vectors [`view`](../vectors/view/README.md), then the stand of [the acceptance of the chapter](../acceptance/1/README.md).

### Chapter 8.4 — people and grants

1. `may` — the pure function of [the right contract](../../common/contracts/may.md) — by the vectors.
2. The row of a person, the PBKDF2 hash, the login and the limit; the indistinguishability of the answer.
3. The grant rows, the last administrator, the deletion mark and the reconciliation.
4. The check at the doors of the process by `domain/grants/domain`; the emergency account at the holder.
5. The stand of [the acceptance of the chapter](../acceptance/4/README.md) with the identity `root`, which the runner sets by the vocabulary of the «Domain stand».

### Chapter 8.5 — books and the names index

1. `assemble` (the pure function of N3): who contributes, `missing` with closed words, the removal of a contribution as a whole, `unique`/`all`,
   the order; the vectors [`assemble`](../vectors/assemble/README.md).
2. The book rows at the holder, the secrets — by the ring ([P/06.2](../../06-console/spec/06.2-console.norms.md) N1.2), a write
   only on a change; the names index after the assembly of the books of the pass; the delivery `sealed.books`; the mask.
3. The checks of the names index at the doors of people and grants (chapter 8.4 N3, the steps of the name check).
4. The stand of [the acceptance of the chapter](../acceptance/5/README.md); the training writer of the contributions `testsub2` — N5 of the chapter.

### Chapter 8.6 — placement and edits

1. The placement and the counter; the answer to the agent with the filter `records`.
2. The refusals of an edit by chapters 8.1 and 8.6; the forms of the edit and of the placement.
3. The stored edit, `base` with the waiting ones taken into account, the outcomes and `settle` — after the agent side (lesson P/09, the application with
   `If-Match`) or together with it: the stand observes the application.
4. The stand of [the acceptance of the chapter](../acceptance/6/README.md); `If-Match` of the units door — [chapter P/06.1](../../06-console/spec/06.1-console.norms.md),
   the executors in the shadow report — the stand of chapter 8.1.

### Chapter 8.7 — the issue of tokens

1. `issue` (the pure function of N3): the forms, the role, `by`, the scopes placement → unit, scenario; the audience; the refusal words;
   the vectors [`issue`](../vectors/issue/README.md).
2. The claims and the signature ([the domain token contract](../../common/contracts/domain-token.md) «The token»).
3. The holder door `/api/tokens/…` and the answer in the envelope `m1` ([the domain envelopes contract](../../common/contracts/domain-envelopes.md)).
4. The stand of [the acceptance of the chapter](../acceptance/7/README.md): the runner logs into the local door of the agent with the identity of a role
   ([the local token door contract](../../common/contracts/local-token-door.md#the-role-socket)).

### Chapter 8.8 — the term, the copy, the move

1. `record`, `ask-sig` by the vectors.
2. The term record and `claim`.
3. The backup copy: the composition, its key, the revision by the content, the keepers.
4. The emergency move: the neighbours, the choice of the backup copy, the new term, the keys.
5. The displacement; the planned handover; the stranded.
6. The stand of [the acceptance of the chapter](../acceptance/8/README.md): the signer on `m1` too, the move by the directives of the vocabulary of the «Domain stand».

### Chapter 8.9 — the shared document and the alarm history

1. The document, the pointer, the edit (N1.2, N1.3).
2. `shared` in the answer to the agent; «delivered to how many» (N1.4, N1.6).
3. The alarm history (N1.9).
4. The stand of [the acceptance of the chapter](../acceptance/9/README.md).

### Chapter 8.10 — the queue and the cost

1. The queue `domain/signer-turn` and the guard — already from step 2 of chapter 8.0; here — the standby at all the doors and giving up the queue on
   `SIGTERM`.
2. The ceilings of the section row, `SERVERS_MAX`, `ENTRY_MAX`, `whole` — together with the acceptance of members of chapter 8.3.
3. The stand of [the acceptance of the chapter](../acceptance/10/README.md): `SERVERS_MAX`, `ENTRY_MAX`, the freshness of the queue; `whole` and the cost — by reading.

### The whole lesson

Run the vectors and the acceptance scenarios separately, with the preparation that the acceptance README of the chapter names: in all the lesson has
109 scenarios / 1367 stand steps — chapter 8.1 (`acceptance/1/`: 04, 06–09, 15), chapter 8.3 (`acceptance/3/`: 01–05, 14–29),
chapter 8.4 (`acceptance/4/`: 01, 02, 04, 08–37), chapter 8.5 (`acceptance/5/`: 01, 03, 05, 11–14), chapter 8.6
(`acceptance/6/`: 01–03, 05, 09–16), chapter 8.7 (`acceptance/7/`: 01–07), chapter 8.8 (`acceptance/8/`: 02–04, 08–10, 12–18),
chapter 8.9 (`acceptance/9/`: 01, 07–09), chapter 8.10 (`acceptance/10/`: 04, 05, 07–10); chapter 8.2 — only vectors (N5 of the chapter),
chapters 8.0 and 8.2 have no catalogue. Fill the checklists of the chapters with the evidence from N5 of the chapters.

## Pitfalls of the language and the library

| Norm | Possible error | How to keep the behaviour |
|---|---|---|
| 8.0 N1.9 | writing the target and the claim row by two writes; putting the index into the answer body | the target and the claim — one batch `op: batch`; the index of the batch is unknown before the write, so the `ETag` of a replay is the index of the claim row itself or its field `index` |
| 8.0 N1.9 | the print of a body with a password by an ordinary hash | HMAC `print` of chapter P/06.2 N1 under the holder ring |
| 8.0 N1.8, 8.4 N1.10 | trusting `X-W2C-Client` from any connection or counting the login limit by the TCP peer of the process | the header — only on a connection of the role `domainconsole` (the client certificate, SAN), otherwise — the address of the TCP peer; without it all people are one address of the console |
| 8.0 N1.6 | requesting a client certificate and accepting any leaf, or refusing a foreign CA by an HTTP answer after the handshake; resuming sessions | a presented one — check it in the handshake by its own ca.pem, ca.next.pem (the CA, the validity, EKU `clientAuth`) — an alert; do not resume sessions (the role certificate contract `signer`) |
| 8.0 N1.8 | rewriting 409 `deposed`, 503 `frozen`, 503 `standby` into a common refusal | the answer of the process — by its own word in `error`; the console gives it out as it came |
| 8.2 N1.1 | pinning the root by the first set that arrived | the root is pinned only by the installation and the acceptance (chapter 8.3); without `pinned` — `no_pin` |
| 8.2 N1.2 | rewriting the set at an equal `rev` | an equal one — `holding`, the row does not change |
| 8.2 N1.2 | signing `json.dumps` with spaces or in the insertion order | the signature — over JCS; the order of the fields of the text `doc` is free |
| 8.2 N1.5 | deriving the X25519 key from the seed through HKDF or a hash | the seed is the scalar itself; the library clamps it at the multiplication |
| 8.2 N1.5 | base64 with `=` or the standard alphabet | base64url without `=`; `=` in an envelope — `not_an_envelope` |
| 8.2 N1.5 | AAD from one field name or `<JCS>:<field>` | `JCS([member, source_path, item]) ‖ 0x00 ‖ JSON Pointer` as a whole |
| 8.2 N1.6 | comparing `exp` with the holder's clock or `>=` at the boundary | the verifier's clock; `now > exp + 60` — a refusal, equality — `ok` |
| 8.2 N1.6 | counting an unreadable `domain/revoked` as empty | `no_revocations`: there is nothing to check with; empty — only when there is no row |
| 8.3 N1.3 | writing the mark before the object of the generation | the order: the object, then `.delta`, then the mark |
| 8.3 N1.4 | signing the path with a query, or a window only into the past | the path without a query; `\|now − ms/1000\| ≤ window` (`ms` — milliseconds, `window` — seconds) |
| 8.3 N1.5 | a separate X25519 key or the form `m1.<hex>.<b64>` | one key of the member; the text `m1:<eph>:<nonce>:<ct>` base64url |
| 8.3 N3 | refusing a report with `sent_at` below the mark | on the same road it is accepted at once |
| 8.3 N1.3a | refusing a body of another road with an old `sent_at` by the code 409 | this is `ignored`: 200, nothing is written |
| 8.3 N1.3a | giving another road the `rev` of the mark | `rev` — only to the road of the mark, to another — 0 |
| 8.3 N1.6 | clearing `Entry.ca` when a publication has no `tls_ca` | it does not change; only the administrator removes it |
| 8.3 N1.4a | including `members_rev` into the whole generation | outside the delta, like `stale` and `tls_ca` |
| 8.1 N1.3 | the age by the wall clock or by the member's `sent_at` | only the holder's monotonic clock and a change before its eyes |
| 8.1 N1.4 | two claims of one ref — take the first in order | both in `contested`, none in `units`, `complete: false` |
| 8.1 N1.4 | a ref at the executors of a placement is also a dispute; `origin` is an executor | `{cluster} ∪ copies` — not a dispute, both units in `units`; `origin` does not change the set; the placements are not read — a dispute |
| 8.1 N1.6 | the placements are not read — a report with empty placements | the report of the pass is not built: the previous `domain/shadow`, `clean_streak` does not change |
| 8.1 N1.4 | a unit from a shard repeats a unit from a heartbeat | an id already taken from a heartbeat is not added by the shard |
| 8.1 N1.6 | comparing revisions for equality | the lag — `revision > observed_revision`; the stagnation — time without a change |
| 8.1 N1.5 | an empty list with a silent member | `complete: false` and the member `silent`; the list is not shorter «just in case» |
| 8.4 N1.2 | 401 at once on an unknown name | a comparison with a dummy hash of the same cost: the answer and the time are indistinguishable |
| 8.4 N1.10 | blocking a name after failures | only the address and the common ceiling: blocking a name would switch off the administrator |
| 8.4 N1.3 | reading the copy of the grants as eternal | older than `as_of + GRANT_LIFETIME` — no rights |
| 8.4 N1.4 | taking the labels `labels:` from the unit itself that has `about` | the labels — from the unit that is meant (`about`) |
| 8.4 N1.4 | counting a right without a unit as any grant for `edit` | without a unit any row fits only for `view`; otherwise — `*` |
| 8.4 N3 | DELETE of a person without a mark | first the mark `domain/deleting/<name>`, then the row and the grants; the reconciliation completes an interruption |
| 8.5 N1.3 | a spoiled input — remove only it | the whole contribution of the member in the book is removed, the member — in `missing` |
| 8.5 N1.3 | a member `unseen` does not contribute | it contributes and stands in `missing` (`why: unseen`) |
| 8.5 N1.3 | a recipient outside the list — deliver «for the future» | it receives nothing; only `view.books.undelivered` |
| 8.5 N1.4 | a book secret in a door answer or in the journal | only the `show` fields; the secrets — by envelopes of the ring |
| 8.5 N1.7 | an unreadable index — «there is no name» | the unknown: 503 on creation and extension, a removal does not wait |
| 8.6 N1.2 | carrying all the records of the domain to the member | only those that name it (`cluster`, `origin`, `copies`) |
| 8.6 N1.3 | taking the first of two members with the ref | `contested` — 503 with the members |
| 8.6 N3 | an edit by ref at two executors without `?cluster=` — take the first; a replay of the key — 409 | first the early replay by the id of each executor (at exactly one — `repeat`), otherwise 409 `executors` with `clusters` |
| 8.6 N1.4 | `base` of the second edit of the same unit — from the copy | `base` = `base` of the waiting PUT + 1 |
| 8.7 N3 | an unreadable placement — go on to `unit` | unreadable — 403 `assignment_unreadable`; to `unit` — only when there is no record |
| 8.7 N3 | `by` at a kind without `scenario` — skip it | 400 `by_misplaced` |
| 8.7 N1.4 | the audience in the order of the targets | in ascending order, without repeats |
| 8.8 N1.5 | a new revision of the backup copy at every pass | only on a change of the content with the secrets opened: sealing gives a new nonce, the opened content has to be compared |
| 8.8 N1.8 | term = the term of the dead holder + 1 | `1 + max` over the records and the backup copies of all who answered: the second move will not become equal to the first |
| 8.8 N1.8 | restoring from the backup copy that was given when a neighbour declared a newer one | 409 with a list: a silent rollback of the state is worse than a refusal |
| 8.8 N1.7 | counting the handover safe against the previous holder | the keys are copied; «forgot» is a promise; if you do not trust the previous one — `stolen` |
| 8.8 N1.6 | yielding by a neighbour's word | only by the record of its own store, checked by its own set |
| 8.9 N1.3 | refusing by the first reason | all the reasons of the content by one 400 through «; » |
| 8.9 N1.9 | writing the history from a list request | only the holder's pass writes it; the list (lesson P/10) reads it |
| 8.10 N1.7 | writing the outputs of the pass without the guard of the queue | every write — with the guard `{key: domain/signer-turn, index}`; a refusal of the guard — become a standby |
| 8.10 N1.7 | writing the object `domain/view`, the mark `reported` or the alarm history by `put` without an index after the confirmation of the queue | `get_at` → CAS of the confirmation of the queue → `put_at` by the index read before the confirmation |
| 8.10 N1.5 | checking `ENTRY_MAX` only at the changed entry | every write of `domain/member-rows/<part>` checks all the entries of the new document |

## Boundary checks

### One writer of the holder rows

The holder rows are written only by the process `domain` ([chapter 8.0](08.0-domain.norms.md) N1.8 `writer`), each — with the guard
of the queue ([chapter 8.10](08.10-domain.norms.md) N1.7); the exception — the rows of the worker on the domain (P/03.7). The domain console
does not write the holder rows — it passes an edit to the process; the agent writes the copies at its member (lesson P/09). Check by reading
that every write of the rows of the families of the lesson goes from the process and with the guard, and the objects — after the confirmation of the queue.

### What the process does not do for its neighbours

The process does not open the envelope `m1` and does not apply edits on a member — that is the agent (lesson P/09); it does not check a token at
the recipient — that is the worker (P/03.7) and the gate of the console; it does not hold sessions of people and does not check an emergency password — that is
the cluster console (chapter 6.7); it does not serve the view doors and the alarm list — that is the domain console (lesson P/10). The holder's answer
carries to the member only what the norms of chapter 8.3 N1.5 and the owner chapters of the fields name.

### Vectors and the stand

The vectors check the pure functions and nothing more: the order of the writes of a generation, the queue, the mutex per member, TLS, the replay of
an edit and an interruption in the middle they do not prove. The inputs of the vectors `view`, `assemble` and `accept` depend on the bytes of the manifests
`testsub` and `testsub2`; the READMEs of the packages name their sha256 — another manifest gives another output. On a stand without TLS
`X-W2C-Client` is never trusted; the class `signed` and the rows of the door `signer` are checked by the TLS stand
([`common/acceptance/tls/`](../../common/acceptance/tls/README.md)), when it is ready.

## Done when

All the choices of the implementation are described (the items «Implementation decides» of all chapters), all the norms of the checklists of the chapters are fulfilled and
the ways of checking are recorded: for each id — a specific piece of evidence or an unchecked dependency. State the slice, the commands and the stand,
the observations and the limitations. The data of past runs do not replace the preparation of a new one.

- **8.0.** The evidence by reading for `X-W2C-Client` and the server side of the class `signed` is named; the answers `deposed`,
  `frozen`, `standby` are observed on the stands of chapters 8.8 and 8.10.
- **8.1.** The vectors [`view`](../vectors/view/README.md) pass by the command `view`; the stand of the chapter passes with real
  reports of the members; the description of the implementation names the command `view` and where the memory of the shadow report is kept.
- **8.2.** The vectors `keys`, `domain-token`, `domain-envelopes` (`x25519-open`, `x25519-round`) pass by the commands `keys`,
  `token`, `seal`, `seal-round`; the description of the implementation names the acceptance commands and the calls of the changes (the installation command — by
  P/02.4); the items «checked by reading» and the stands of chapters 8.3 and 8.8 are named separately.
- **8.3.** The acceptance scenarios of the chapter pass; the vectors `accept`, `agent-sig`, `domain-envelopes` (`m1-open`, `m1-round`)
  pass by their function; the description of the implementation names the commands of the check by the vectors.
- **8.4.** The acceptance scenarios of the chapter pass; the vectors `may` give their answers; the stands of the chapters of the lesson pass with the identity `root`
  by the vocabulary of the «Domain stand»; the description of the implementation names the commands `may` and `domain first-admin`.
- **8.5.** The acceptance scenarios of the chapter pass; the vectors `assemble` give their expectations; the cases `m51_books_*` and `m59_names_*`
  of the corpus of P/02.1 give their verdicts; the description of the implementation names `assemble` and the training writer `testsub2`.
- **8.6.** The acceptance scenarios of the chapter pass, and with them — scenario 14 of chapter P/06.1 (`If-Match`) and scenario 15 of chapter 8.1 (the executors);
  the description of the implementation names the order of the JSON fields of the records and of the answers.
- **8.7.** The acceptance scenarios of the chapter pass; the vectors `issue` give their expectations; the cases `m57_tokens_*` of the corpus of P/02.1
  give their verdicts; the description of the implementation names `issue` and how the stand runner logs into the local door of the agent by a role.
- **8.8.** The acceptance scenarios of the chapter and the vectors `record`, `ask-sig` pass; the description of the implementation names the commands and how
  the runner raises a signer on another cluster (`@start domain on`) and moves the domain (`@move`).
- **8.9.** The acceptance scenario of the chapter passes; the cases `m61_shared_*` of the corpus of P/02.1 give their verdicts.
- **8.10.** The acceptance scenarios of the chapter pass; the other ceilings and the cost — the evidence by reading.

The success of a TSV confirms only the branches it observes. It does not prove an interruption between the writes of a generation, a race of two
processes `domain`, the mutex per member, TLS between clusters and the durability of the backup copy at the keepers: for them reading by N5 of the chapters
or a separate stand is needed. A check of the documents and of the OpenAPI does not run the implementation.

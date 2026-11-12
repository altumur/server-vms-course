# P/01 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/01-store.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/01-store.md` (for people, not in the export).

Scenarios, fixtures and reference outputs are supplied only to the judge. The visible norms and public contracts state every implementation duty; a judge-only annotation identifies a specific closed file that this text still needs to name.

## Task

Implement the store process of lesson P/01 in the language `<LANG>` so that it passes the N5 acceptance of the three chapters
through the door (HTTP on a unix socket): the operations vocabulary (chapter 1.1), the rights file and the evaluator (chapter
1.2), the store daemon (chapter 1.3). Get the same answer of the rights evaluator in the file-based store, in memory and in
the cluster; show the loaded rights file only to admin.

## Inputs and their priority

| File | Role | Priority |
|---|---|---|
| [`01.1-store.norms.md`](01.1-store.norms.md), [`01.2-store.norms.md`](01.2-store.norms.md), [`01.3-store.norms.md`](01.3-store.norms.md) | the norms of the chapters: what MUST be | 1 — the canon |
| [`01-store.api.openapi.yaml`](01-store.api.openapi.yaml) | the form of the HTTP requests and answers of all doors, the full bodies of `/v1/rights` and `/v1/list` | 2 — on a divergence from the norms, the norms are right |
| [`../acceptance/1/`](../acceptance/1/README.md), [`../acceptance/2/`](../acceptance/2/README.md), [`../acceptance/3/`](../acceptance/3/README.md) (`README.md`); the stand — [the common README](../../common/acceptance/README.md) | acceptance | 3 — checks the norms, does not add to them |
| `ru/01-store.md` (for people, not in the export) | context, motivation | not a norm; do not derive requirements from it |
| [`../lifecycle.md`](../lifecycle.md) | flags, environment, exit codes, units | a pointer to the norms of chapter 1.3 |

Rules:

- Read the norms of the chapters in full before the first stage; write draft answers to «Implementation decides» into the implementation description.
- Do not add behaviour that is not in the norms of the chapters. Do not «improve» the semantics: normalization of keys, comparison of versions by greater/less, a blind repeat of an earlier command with an old guard (`guard`), new codes and kinds of refusals are forbidden. A new attempt after re-reading the condition and checking the right to it is allowed (N3 «write»: «The caller re-reads the condition and decides anew whether it has the right to repeat»; [P/03.2-05](../../03-worker/spec/03.2-worker.norms.md)).
- If the norms of the chapters are silent or contradict themselves, do not guess. Write a question into the implementation's `QUESTIONS.md` with a reference to the section and choose the most conservative behaviour (a refusal, not an assumption).
- For ease of checking, comments may refer to the norms: `// P/01.1 N3 write, step 7` or `// P/01.1-10` at the place that carries out the norm.

## Glossary

Some words of the norms have more than one meaning; the place of the word tells them apart. This table adds no rule and renames nothing: each meaning is the one the named place already gives.

| Word | Meanings | How to tell them apart |
|---|---|---|
| `configstore` | (1) the store daemon of chapter 1.3 and its command line: `configstore admit <id>` (chapter 1.3 N4 `join_left`), the commands of N1.3 `admin_ops`; (2) the certificate role of a voter: CN `configstore.<server>`, `urn:w2c:role:configstore` (N1.3 `group.identity`, P/01.3-R009 `roles`), next to the role `configstore-door` of a door without a vote; (3) the names of the unit, the user and the paths: `configstore.service`, `User=configstore`, `configstore.env`, `<PLATFORM_DIR>/configstore`, `/run/configstore` ([lifecycle](../lifecycle.md)); (4) a prefix of the series `configstore_raft_*`, `configstore_doors`, `configstore_door_*` (N1.3 `metrics`) and of the rows `platform/configstore-doors/<id>` | a certificate, SAN or forwarding — the role; a unit, a user or a file path — the unit and its paths; a command line — the daemon CLI; `/metrics` — a series name; a key — a row |
| floor | (1) the row `platform/epoch_floor` `{floor, generation_at}` that chapter 1.3 owns (P/01.3-R003; «Data families» `platform/epoch_floor`); (2) its field `floor`, the lower bound of epochs: `floor = generation << 32` (N1.3 `floor`, P/01.3-R006); (3) the service operation `{op: floor, floor, id}` of `POST /v1/write` on `admin.sock` of the leader (P/01.3-R016; OpenAPI `FloorCmd`); when `restore`, `import` and `recover` raise the floor is N1.3 `floor`; (4) the refusals named after it: `floor_not_higher` (chapter 1.1 N4), `floor_not_integer`, `floor_socket`, `floor_not_higher_id`, `floor_row_write` (chapter 1.3 N4, P/01.3-R029) | `platform/epoch_floor` or «the floor row» — the row; `floor` in `items` or in the body of `op: floor` — the field; `op: floor` — the operation; a name `floor_*` of [`forms/refusals.tsv`](../forms/refusals.tsv) — a refusal |
| «the store» | (1) the process of the lesson: «the store process» (this README, «Task»), «the store daemon» of chapter 1.3, «the stand store» of the acceptance; (2) the state that the operations of chapter 1.1 N3 read and change: rows, versions and the `id` memory («the row, the version and the `id` memory do not change», P/01.1-R034); (3) a kind of that state: in memory, on files or with a replicated log («What to create» item 2), «the store of a box» (N1.3 `box`), «the store `file://`» in the process (N1.3 `import`; P/02.4 N1.2 `PLATFORM_STORE`) | process words — start, flag, socket, door, exit code, restart; state words — row, version, operation, write, read; a kind is named by its qualifier (box, `file://`, group) |
| `Leader`, `Follower` and `leader`, `follower` | (1) the values of `state` of `GET /v1/status`, capitalized: `Leader`, `Follower`, `Candidate`, `Shutdown`, `Door` (P/01.3-R016; OpenAPI `Status`); (2) the label of the gauge `configstore_raft_state`, lowercase: `leader`, `follower`, `candidate`, `shutdown`; a box emits `state="leader"` (P/01.3-R032); (3) the fields `leader` (the `-api` address of the leader) and `leader_id` (its id) of `/v1/status` (P/01.3-R016); (4) in prose, the leader and a follower are the roles of the voters of a raft group (N1.3 `group`, `metrics`) | capitalized — a value of `Status.state`; lowercase inside the series — a metric label; `leader` or `leader_id` as a JSON field — an address or an id; plain prose — the role of a member |
| door, door without a vote, `role: door` | (1) a door is an HTTP entry of the store on a unix socket: the doors of chapter 1.1 N2 (`/v1/get`, `/v1/list`, `/v1/write`) and the service doors of the daemon of chapter 1.3 N2 (for example `/v1/status`, `/v1/join`, `/v1/leave`, `/metrics`); (2) a door without a vote is a daemon started with `-door` and `-voters`: not a raft member, without a replica of the rows, it forwards to the leader or a voter under the role `configstore-door` and writes only its own row `platform/configstore-doors/<id>` (N1.3 `door`, P/01.3-R006, P/01.3-R007); (3) the status of such a daemon: `state` `Door`, `role` `door` and `term`, `commit`, `applied` equal to 0 (P/01.3-R016; OpenAPI `Status`) | «door» with a route or a socket — an HTTP entry; «door without a vote», `-door`, `configstore-door` — the non-voting daemon; `Door` or `door` as a value of `state` or `role` — its status |
| `limit`, «the body limit», «the effective `-max-body`» | (1) the field `limit` of a `413 toolarge` refusal: the body limit in a body refusal (`BodyTooLargeFault`), the row ceiling in a row-weight refusal (`RowTooLargeFault`) (P/01.1-R034); (2) «the body limit» is the read limit of the HTTP body of `POST /v1/write`, in bytes before JSON parsing (P/01.1-R034); for the daemon it is set by the flag `-max-body` (P/01.3-R007), and «the effective `-max-body`» is the value this instance runs with: the limit of `POST /v1/write` and of the service POSTs (P/01.3-R007, P/01.3-R017), given as `max_body` in `/v1/status` (P/01.3-R016); (3) «the row ceiling» is a different quantity: the weight ceiling of `items`, the flag `-max-value`, `max_value` in `/v1/status` (P/01.1-R034, P/01.3-R016) | in a `413` answer the field `key` tells them apart: with `key` — the row ceiling, without `key` — the body limit (P/01.1-R034); «the body limit» and «the effective `-max-body`» are one quantity, named by the norm of chapter 1.1 and by the daemon flag of chapter 1.3 |

## What to create

The mandatory behaviour is set by the norms of the chapters. The internal interfaces, the representation of refusals and the structure of the code are chosen by the implementation (N5, P/01.1-20); the examples below add no requirements to the canon.

1. **A store with the five operations of N3** (read, list, write, delete, write batch). Its internal API may return typed refusals or represent them otherwise; at the door the codes and fields of the answer must match N4. For example, a typed value with the fields `kind`, `key`, `index`, `size`, `limit` is convenient to translate into an HTTP answer.

   Serialization chooses the form of exactly its own outcome of N2: `conflict` requires `index`, `guard` also
   `key`, a weight refusal `key`, `size`, `limit`, a body refusal `limit` and only an admissible `size`.
   Do not serialize all the fields of the internal type with zero values. Check the full body against the schema
   of the answer of the specific operation and code; one common `Fault` does not confirm the right kind of refusal.
2. **A data store of the chosen kind**: in memory, on files or with a replicated log (the group and the daemon `configstore` — chapter 1.3 N1.3). The implementation describes its choice and guarantees under the section «Implementation decides»; having several kinds at once is not required.
3. **An HTTP server on a unix socket** per [`01-store.api.openapi.yaml`](01-store.api.openapi.yaml), which translates the refusals of the core into the codes of N4. The read limit of the body is set separately from the row ceiling; exceeding it is refused per N2 before JSON parsing and the call of the operation.
4. **The rights check per N3 and N4**. The permissions to read, write and delete are given by `allowed(role, action, key)` of chapter 1.2 N1.3; the internal API of the check is chosen by the implementation. The identity of the caller is determined by the role socket (chapter 1.2 N1.1 `identity`). The rights file is chapter 1.2 N1.2: loading the whole file, a single evaluator, binding the identity to the socket or the writer, and checking trusted forwarding; the two HTTP forms of N2 of chapter 1.2. The internal classes, functions, the structure of the pattern index and the way the evaluator is integrated remain with the implementation; the acceptance role has full rights to the prefix `acc/` and to nothing else; listing names does not require the read right, but it is done after the identity check of chapter 1.2 (N3).
5. **The implementation description** (ARCHITECTURE) — an answer to every item of the section «Implementation decides». An item without an answer means the implementation is not ready.
6. **The store daemon** (chapter 1.3): flags, `FORMAT`, the group and the door without a vote, sockets, durability, service doors, the floor, the copy and `import`/`restore`/`recover`.
7. **An acceptance run** through the door; implementations with an in-process API SHOULD run the same scenarios through it too (N5, P/01.1-20).
8. **The vector functions of the shared packages** (the section «Shared vector packages») behind the profile command `vectors`.

## Shared vector packages

Besides the packages of the lesson itself (`vectors/jcs`, `vectors/rights-evaluator`, `01-store/write-checks`), the targets of this lesson include the five shared packages of the table. Each is run by the entry of the profile section `vectors` with the key of the table and calls the implementation's own function; the input, the output and the comparison are the README of the package and [the vector wire form](../../common/vectors/wire.md), the command is [the profile format](../../common/acceptance/PROFILE.md). The rows of the lesson `01-store` in [`consumers.tsv`](../../common/vectors/consumers.tsv) are the complete list of the shared tables assigned to this lesson.

| Key in `vectors` | Target | Table | What runs in this lesson | Package |
|---|---|---|---|---|
| `common/revoked` | `P/01/vectors-revoked` | `cases.tsv` | the reader of the file `revoked` of the door that checks a TLS peer (chapter 1.3 N1.6) | [README](../../common/vectors/revoked/README.md) |
| `common/log-mask` | `P/01/vectors-log-mask` | `cases.tsv` | the log mask of the store daemon and its CLI | [README](../../common/vectors/log-mask/README.md) |
| `common/store-client` | `P/01/vectors-store-client` | `cases.tsv` | the parsing of a store answer by the CLI of the daemon (`admin_ops` through `admin.sock`, chapter 1.3 N1.3) | [README](../../common/vectors/store-client/README.md) |
| `common/family-read` | `P/01/vectors-family-read` | `01.tsv` | the reading of the data families owned by this lesson (the catalogue column `owner`) by the common library of the implementation | [README](../../common/vectors/family-read/README.md) |
| `common/crl` | `P/01/vectors-crl` | `cases.tsv` | the reading of the file `crl.pem` by the door that checks a TLS peer (chapter 1.3 N1.6) | [README](../../common/vectors/crl/README.md) |

The packages check the functions named in the table: peer checks for `revoked` and `crl.pem` under P/01.3-R009; the store answer to the CLI under `admin_ops` of P/01.3-R006; the owned families under P/01.3-R003. The log mask follows P/06.2 N1.4 `never.log` and the log-mask contract named by its package README; P/01 adds no separate rule for it.

## Order of work

The stages of the implementation are the table [`forms/stages.tsv`](../forms/stages.tsv) (ADR-0126): the goal, the norms, the gate (own tests, vectors, scenarios of acceptance), the weight and the dependencies of each stage. It is one possible order, a plan and not a norm: the split into functions, the internal interfaces and the chosen kinds of store may be arranged otherwise, keeping the behaviour of the canon. Below is the advice to the stages by chapter; the checklists are in «Done when».

The one-box daemon work is split into `daemon_doors` (the service doors and status), then `daemon_copy` (copies). The table gives their gates, weights and dependencies.

### Chapter 1.1 — the store doors

1. The data model of N1: the checks of `key`, `items`, `cas`, `guard`, `id` as separate pure functions. These are the first tests (the stage `model`).
2. The chosen store (for example, in memory): the procedures of N3 strictly step by step, with the same order of checks (the guard before CAS).
3. The HTTP layer and the mapping of the refusals of N4 ([`forms/refusals.tsv`](../forms/refusals.tsv)).
4. Prepare instances per the acceptance README of chapter 1.1: the row ceiling and body limit declared by the acceptance stand (N5), separately. Run the scenarios of chapter 1.1. Check each failure against the norms of the chapters and fix the **code**.
5. If a file-based store is chosen: check indivisibility, versions, durability barriers, a damaged row (`Row.unreadable`). Run the scenarios again.
6. Go through the checklist of chapter 1.1 (P/01.1-01…32); for the items «checked by reading», state in the implementation description where in the code this is ensured.

### Chapter 1.2 — the rights file and the evaluator

1. Load the form of N1.2 in full. Distinguish the absence of delete from an explicit empty list.
   The file has no internal roles, no JSON syntax comments and no unknown fields.
   The optional string comment is metadata; a change of its text does not change the rights
   and is not compared by --check (comparison by meaning — P/02.5 N3 «install»); /v1/rights returns it.
2. Implement the priority of the check from N3: identity, the special operation list, never,
   the permission of admin/internal roles, the evaluator of an ordinary role, the read right of the guard.
   Check a denial when a permission matched, and the prohibitions on each action separately,
   including write/delete epoch_floor. A trusted forwarded admin without a file is allowed
   after never; with a file it is refused. A spoofed identity is refused in both modes.
3. Carry out all acceptance steps of the chapter, including the header scenario on one box: there too the store opens a socket per role,
   and a role header on it is 403 (N1.1 `box`).
   For an identity refusal check the socket role and the reason; for an operation refusal, also the action/key.
4. Supplement the HTTP scenarios with reading the loader/generator and checking the full answers of N2.
   Run the positive and negative examples of the forms of the file and of Listing; do not restrict the
   prefix parameters by the key grammar. When the file is not loaded, rights gives 404.

### Chapter 1.3 — the store daemon

References «N…» are norms of chapter 1.3; rights are chapter 1.2.

1. Describe the stable/transitional membership of the group, sequential join/leave and the door without a vote. For status keep the exact uint64; `leader` is the `-api` address, `leader_id` is the id. Do not forward admin.sock; take the rights from chapter 1.2. The daemon flags are only [forms/daemon-flags.tsv](../forms/daemon-flags.tsv); the sockets lie side by side in one directory, none in a subdirectory of it (admin.sock and the role sockets), and other entries of that directory are not a start refusal; inherited sockets are taken by `FileDescriptorName` (N1.3 `sockets`).

   Write the mark `FORMAT` first into an empty directory and check it before any write: a foreign or unmarked non-empty directory is exit code 2 without changes. Write the copy `backup`, and read `import`/`restore`, only in the form of N1.3 `copy`; do not carry your own on-disk format into the copy.

2. On a separate model check all phases of restore/import/recover: isolation, a reliable upper, the uint64 bounds, one raise of the floor, a partial transfer and continuation of the same attempt. Force does not allow a lowering or two operators (N3).

3. Run the automatic 04, 08, 10–12, 14, 15 (steps 1–8), 16, 19–24, 30 on a fresh stand with schema 1 (08, 19, 30 with a durable store; 20, 22 with the spoiling command `spoil-row`); 07, 17, 18, 25–29, 31–34 on the store group stand (the common acceptance README, «Store group stand»; for the box build `keys.store_build: box` — not_applicable). These scenarios are outside the model input; they check the checklist items that name them: P/01.3-01…08 and P/01.3-11 of chapter 1.3, P/01.1-07, P/01.1-11, P/01.1-14, P/01.1-17, P/01.1-30, P/01.1-31 of chapter 1.1.

## Language-dependent pitfalls

Places where idiomatic code in many languages breaks a norm:

| Norm | Pitfall | The right way |
|---|---|---|
| the order of list keys is by bytes (N3) | Java, C#, JS, Kotlin sort strings by UTF-16; `localeCompare` by locale | compare the UTF-8 bytes |
| the weight and the key length are in UTF-8 bytes (N1) | `len()` / `.length` count characters or UTF-16 units | the length of the UTF-8 encoding |
| the version is opaque (N1) | parsing into a number and comparing with `>` | store and compare as a string; inside the store the counter MAY be a number |
| items is a copy (N3) | returning a reference to the internal map | an independent copy on input and output; checked by reading per N5 and P/01.1-03: HTTP scenario 03  does not observe shared memory |
| indivisibility (N3) | the check and the write under different locks; async breaks between steps | the steps after «the remaining steps run as one operation» in one critical section |
| the guard before CAS (N3) | checking in the order of the request fields | strictly: the guard, then CAS |
| the whole batch (N3 «write batch») | writing the rows one at a time under a lock: power is lost between files, and half of the batch remains | the way of item 3 of «Implementation decides»: an intent log with a barrier before the rows are published; one raft log record |
| one version per batch (N1 `index`) | the version counter grows on every row | a version is handed out per operation, all rows of the batch get it |
| a refusal does not quote what was sent (N4) | messages like `invalid value "<body>"` from JSON libraries | an own message, without the sent data, except the key |
| the key spelling is the OpenAPI schema `Key`, the length is in bytes (N1, N2) | a common validator refusal turns any wrong key into `badrequest` | an absent or non-string key (of a command, a guard, a read) and an empty guard key — `badrequest`; a key string not by the rules of N1 — `badkey`, including a non-empty guard key |
| a body over the limit → 413 (N2, N4) | the framework answers with its own 413/400 or puts the row ceiling into `limit` | limit the read before JSON parsing, return a `Fault` with the body limit in `limit`; the optional `size` is the full size of the body |
| an unknown route → 404 badrequest (N2) | the standard 404 page of the framework | an own handler with `Fault` |
| query parsing (N2.1) | `+` read literally; on a repeated parameter the first or the last is taken silently | `application/x-www-form-urlencoded`: `+` is a space, `%2B` is a plus; a repeat of `key`/`prefix` — `badrequest`; `key` not UTF-8 — `badkey` |
| JSON parsing (N2.1) | the library takes the last of repeated names, accepts `NaN`, replaces a lone surrogate | a repeated name at any level — `badrequest`; a surrogate in a key — `badkey`, in `items` — `badrequest` |
| an unknown method and unparsable HTTP (N2.1) | the server by default answers 405, 501, 414 or 431 with an HTML page | `404` or `400` with `Fault` `{kind: badrequest}` |
| an isolated instance (N5) | the runner cleans the rows of the previous instance | the way to get a new instance with parameters is in the implementation description («Implementation decides» item 10) |
| `cas: null` ≡ no field (N1) | the JSON library distinguishes null from absence, or confuses `""` with null | three states: absent/null, `""`, a version |
| unknown fields of Cmd and items of delete are not read (N2) | strict body parsing rejects an extra field or includes it into the id fingerprint | ignore the extra top-level fields of put/delete and do not include them into the fingerprint; guard stays closed |
| durability («Implementation decides» item 3) | a write without a durability barrier; rename without saving the directory | provide the barriers named in the implementation description; for files this is, for example, fsync of the file and of the directory before a successful answer |


Chapter 1.2:

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| N1.1 | The role name was truncated or replaced with a common controller | Keep the manifest name and the suffix; the current limits are compatible |
| N1.2 | An empty delete was replaced with write through a «falsiness» check | The default only when the field is absent |
| N1.2/N1.3 | A common glob treats an asterisk in the middle as a pattern | Carry out only an exact name/a trailing prefix; `*` not in the last place is a literal character: `a*b` matches only the key `a*b` (vector `Platform/01-store/vectors/rights-evaluator`) |
| N1.3 | The first permission ends the search before a denial | Denials take priority regardless of position |
| N1.3/N3 | admin is absent from roles and therefore refuses, list requires read | Carry out the special rules explicitly after the identity check |
| N2 | The file is wrapped in an extra object, values are returned in list | Check the whole body against the contract and the meaning of N2 |

Chapter 1.3:

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| N2 | A JS number rounds floor/commit above 2^53 | Keep the uint64 precision in JSON parsing and serialization. |
| N3 | -force removes all safeguards | Only clocks backwards/transitional parity in its own commands; the other allowances are unchanged. |

## Done when

- [ ] all 78 scenarios / 741 steps of the three chapters (judge-only: `scenarios.tsv` of the three chapters; they check the checklist items named below) (1.1 — 40, 1.2 — 11, 1.3 — 27; sc. 07, 17, 18, 25–29, 31–34 of chapter 1.3 on the store group stand) are green through the door, including the order of names in `keys`
  per the acceptance README of chapter 1.1; sc. 07, 17, 18, 25–29, 31–34 of chapter 1.3 on the store group stand (for the box build — not_applicable);
- [ ] (SHOULD) the same scenarios are green through the in-process API for each data store;
- [ ] the implementation description answers all items of the section «Implementation decides»;
- [ ] each item of the checklists P/01.1-01…32, P/01.2-01…09, P/01.3-01…13 is either closed by a scenario, or the description states the place in the
  code; the reading evidence names the files and the checked subject (never, denials, trusted forwarding); reading does not
  prove fsync or failover — the results of the implementation or of an operator stand are needed;
- [ ] `QUESTIONS.md` is empty or each question has been passed to the author of the norms.

## When the code and the norms diverge

| Situation | What to fix |
|---|---|
| a scenario is red, the norms of the chapters are unambiguous | the code |
| the norms of the chapters are incomplete or contradictory | do not work around it in the code; a question in `QUESTIONS.md`; the fix is made by the author of the norms, then the code |
| a scenario contradicts the norms of the chapters | an acceptance defect; a question to the author; the code follows the norms of the chapters |
| an AI made a mistake and was corrected by a person | a row in `corrections-<K>.tsv` (historical correction record) of the chapter (ADR-0080 addendum 1) |

An additional check: service POSTs: unknown field/not an object/extra JSON/framing — 400; one byte above the effective `-max-body` — 413; no path/method — 404/405. Check each reason against N2, N4 and the full Fault, not only the code number.

## Production qualification

Read [production acceptance](production-acceptance.md) with the norms. Functional gates and the engineering group stage do not establish production qualification. State the declared workload/resources and finite budgets, then bind independent storage/time/fault/stream observations. Missing input or capability remains blocked/NotExecuted; no profile field, platform port or runtime flag is created by this declaration.

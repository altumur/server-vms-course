# P/06 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/06-console.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/06-console.md` (for people, not in the export).

Concrete scenarios, fixtures and expected answers are not supplied in M; the judge receives them separately. The public acceptance READMEs define their interfaces and scope; norms and public forms define the required behaviour.

## Task

Implement the process of the cluster console in the language `<LANG>`: the units door, the write of secrets, the guard, requests and the merge
of events, observations and the operator doors — by the six chapters of the lesson, the cluster console in the domain — by chapter 6.7 of the late layer
(after the lessons P/08–P/10), cluster folders and group operations — by chapters 6.8 and 6.9; pass the acceptance N5 of the chapters and close their readiness checklists. In all 146 norms: P/06.1-01…35,
P/06.2-01…-06 and P/06.2-08…-11 (number07 is unused), P/06.3-01…08,
P/06.4-01…11, P/06.5-01…19, P/06.6-01…08, P/06.7-01…19, P/06.8-01…18, P/06.9-01…18.

- **6.1.** The unit row and the operations on it — the units door of the console; the bounded blob door, the tables and the maintained
  cleanup — [chapter 6.1](06.1-console.norms.md). The maintenance windows of N3 are a mandatory condition of an admissible execution, not an
  additional locking mechanism. The slot, the epoch and the lease — [chapter P/03.2](../../03-worker/spec/03.2-worker.norms.md) and
  the steps of [the instructions of lesson P/03](../../03-worker/spec/03-worker.README.md).
- **6.2.** Keep secrets in envelopes, give them out by a mask, refuse a password in an address; keep the binding to the row/field,
  reseal at start and keep the ring in the declared maintenance area — [chapter 6.2](06.2-console.norms.md).
  The opening of an envelope by the recipient — [P/03.5](../../03-worker/spec/03.5-worker.norms.md); the commands `w2cctl secrets` —
  [P/02.4 N1.9](../../02-installer/spec/02.4-installer.norms.md).
- **6.3.** The guard, `/session` and the keys `rights:` of the manifest ([chapter 6.3](06.3-console.norms.md) N1.3, N1.5) at the console on
  an edit by people.
- **6.4.** The merge of the resource answers, the submission of requests, the accounting and the reaper — [chapter 6.4](06.4-console.norms.md). The holder
  side (the execution of a request with a mark before the call and an explicit unknown outcome, the append) and the suppression of events — chapter
  [3.6](../../03-worker/spec/03.6-worker.norms.md) and its steps of the instructions of lesson P/03.
- **6.5.** The console process and the shell boundary per N1 of [chapter 6.5](06.5-console.norms.md); the common module — the published
  files N1.1 `module`, they are served byte for byte, not written (what the module calls and gives the shell — [lesson P/07](../../07-console-module/spec/07-console-module.norms.md)).
  Its own HTTP doors and all refusals — N2; the domain, unit and event doors are connected by their owners (chapters
  6.1, 6.4, 6.6, 6.7), not defined anew here. `door.pass` — N1.8.
- **6.6.** The operator doors: the policy, the drain, the labels, the server decommission, `/unplaceable` and `/where`; the schema row, its
  check at the console start, the raise and the door `/schema` — [chapter 6.6](06.6-console.norms.md).
- **6.7.** The cluster console as the door of the cluster to the domain — [chapter 6.7](06.7-console.norms.md) (the late layer): the door of the book
  of this member, the forwarding of `/domain/*` by [the forwarding contract](../../common/contracts/forwarding.md) (transitions 1–2) and the `where`
  of a member, the TLS client to another cluster by [the `peer` contract](../../common/contracts/peer.md), the forwarding to the signer of the
  move doors, `may` by the copy of grants at the guard ([the right contract](../../common/contracts/may.md)), the order of the emergency
  entry, `/domain/keys`, `/api/held`, `/api/backup` ([the request signature contract](../../common/contracts/ask-sig.md)),
  the value on reading (`resolve`). What the domain console and the process `domain` do with the forwarding — lessons
  [P/10](../../10-domain-console/spec/10-domain-console.norms.md) and [P/08](../../08-domain/spec/08.0-domain.norms.md).
- **6.8.** Cluster folders: the rows of a folder and of membership, the chain to the root, the removal of a unit from the folders by the same batch, the folder reaper — [chapter 6.8](06.8-console.norms.md).
- **6.9.** Group operations: the reception, the leader under the queue and the generation, the step ticket, the pause, the token term, the operations reaper — [chapter 6.9](06.9-console.norms.md). The chapter stands on the ticket: without it a step is not executed.

## Inputs and their priority

- The canon is the norms of chapters [6.1](06.1-console.norms.md), [6.2](06.2-console.norms.md), [6.3](06.3-console.norms.md),
  [6.4](06.4-console.norms.md), [6.5](06.5-console.norms.md), [6.6](06.6-console.norms.md), [6.7](06.7-console.norms.md),
  [6.8](06.8-console.norms.md), [6.9](06.9-console.norms.md), including N0, the order of N3 and the refusals of N4. The bytes of the envelope, the AAD and the ring file — [the sealing contract](../../common/contracts/sealing.md); freshness, the state
  of a resource and the reading of the decision intent → placement → intent — [the observation contract](../../common/contracts/observation.md).
- [OpenAPI](06-console.api.openapi.yaml) expresses the HTTP forms of the canon of all chapters of the lesson: one door of a process — one
  contract; the description of each path names the chapter. The common answers (`BadBody`, `Unauthenticated`, `Denied`, `NoRoute`,
  `Method`, `SlowBody`, `LargeBody`, `RateLimited`) — the same for all doors. The seven writing operations covered by `writes_via`
  (chapter 6.1 N1.1a) use `WriteDenied` at 403: `Denied` or `WritesVia` (`error: writes via`, without `field`); the gate's `Denied` remains `error: denied`.
  503 — by door: `Unavailable` (`busy`,
  `denied`, `unavailable` — the doors of 6.6 and the observations of 6.5), `GuardUnavailable` (`GET /manifest`), `UnitUnavailable` and
  `WriteUnavailable` (the units door of 6.1), `ConsoleUnavailable` (the others). The schemas of the event rows and `SubsystemName` —
  `$ref` to [the contract of P/05](../../05-resource/spec/05-resource.api.openapi.yaml); the implementation reads them there.
- One path segment distinguishes the loaded manifest: `unit.rows` — `/{rows}`, `tables` — `/{table}`, `door.pass` —
  `/{pass}`; the loader of P/02.1 guarantees that the names do not intersect. In OpenAPI these are three paths with an equal template —
  the router of the implementation chooses the door by the manifest, not by the order of the paths in the contract.
- `door.pass` (`/{pass}`, chapter 6.5): the contract describes only the local refusals of the console (400/401/403/408/413/429, 502,
  503, for the second kind also 504 and `ProblemRefusal`); the worker's answer is passed on as received and is not checked by the form of the contract.
- Forwarding (`/domain`, `/domain/{route}`, chapter 6.7): the contract carries only the codes of transitions 1–2 (`ForwardBadRequest`,
  `ForwardNotFound`, `ForwardFailed`, `ForwardUnavailable`; the forwarding contract «Refusals by transition»); the answer of the domain console —
  `ForwardAnswer`, as it came, its forms — the OpenAPI of the lessons P/10 and P/08. The forwarding to the signer (`/api/prepare`, `/api/take`,
  `/domain/move`) — the codes of the forwarding cluster console and the answers of the process, `$ref` to the operations of the OpenAPI of P/08; the term records, the pairs and the member names —
  `$ref` to the schemas of P/08.
- Secrets (6.2) create no separate paths: the HTTP inputs — the units door of chapter 6.1 and [the store
  P/01.1](../../01-store/spec/01-store.api.openapi.yaml); the application of the bodies — N2 of chapter 6.2; the CLI, HTTP and the unit state
  have different outcome forms.
- Objects and marks use the store vocabulary of P/01.1, the roles — [P/02.4 N1.6](../../02-installer/spec/02.4-installer.norms.md).
  The resource doors, `PUT /v1/objects/<sub>/blobs/<digest>` and `restore` (`GET /mirrored/<server>`) —
  [P/05](../../05-resource/spec/05-resource.norms.md).
- The acceptance of the chapters checks the norms: [6.1](../acceptance/1/README.md), [6.2](../acceptance/2/README.md) (the scenarios and the
  fields file), [6.3](../acceptance/3/README.md), [6.4](../acceptance/4/README.md), [6.5](../acceptance/5/README.md),
  [6.6](../acceptance/6/README.md), [6.7](../acceptance/7/README.md) (the domain stand), [6.8](../acceptance/8/README.md), [6.9](../acceptance/9/README.md); the stand — [the common acceptance
  README](../../common/acceptance/README.md). The vectors of the lesson —
  [`values-by-type`](../../common/vectors/values-by-type/README.md), [`fault`](../../common/vectors/fault/README.md) (6.1),
  [`secret-in`](../../common/vectors/secret-in/README.md), [`log-mask`](../../common/vectors/log-mask/README.md) (6.2),
  [`rid`](../vectors/rid/README.md), [`requests-body`](../vectors/requests-body/README.md),
  [`request-digest`](../vectors/request-digest/README.md) (6.4), [`resolve`](../vectors/resolve/README.md),
  [`key-families`](../vectors/key-families/README.md) (6.7), [`op-step`](../vectors/op-step/README.md) (6.9); the common
  vectors of the contracts `peer`, `may`, `ask-sig`, `record` (`Platform/common/vectors/`) — a participant of 6.7. Flags, environment, exit
  codes — [`../lifecycle.md`](../lifecycle.md).
- The lecture (`ru/06-console.md`, for people, not in the export) explains the mechanism and the examples.

The unit fields need a loaded manifest per [P/02.1](../../02-installer/spec/02.1-installer.norms.md).
The static HTTP schema does not know an arbitrary set of `unit.fields`: perform the check of the names, types, obligatoriness,
references and constraints of a field by the manifest and N3. Conformance to the common schema alone does not mean an admissible request.
The language, internal interfaces, types, error classes, functions, libraries, the way the handlers are placed and the split into
components are chosen by the implementation and are not judged as a prescribed design. The required shared modules and their contracts
remain mandatory; a choice of language does not permit replacing a required module with a private copy.

The store client's answer-size limit and wait term follow the [store client contract](../../common/contracts/store-client.md#outcomes-and-what-the-client-does):
the implementation declares them, rather than adopting a fixed lesson-wide value. The size limit must accommodate the permitted row and listing
answers of its store; a listing has no fixed row-count ceiling. Exceeding the limit or term is `no_reply`: `unavailable` for get/list,
`ambiguous` for write/delete/batch, not a damaged row. Environment capacities and applicable budgets follow
[finite budgets and observable completion](../../common/contracts/production-obligations.md#finite-budgets-and-observable-completion);
missing factual bindings remain unqualified, not PASS.

**On a discrepancy.** Name the norm id, the input, the initial state, the expected and the obtained outcome. First check which
chapter or lesson the rule belongs to: the units door and the claim — chapter 6.1, the loader — P/02.1, the rights generator — P/02.5,
the opening of a secret — P/03.5, people and grants — P/08.4, the forwarding and `peer` — the forwarding and `peer` contracts. If the implementation is wrong — fix it and repeat
the related checks. If the norm, the contract or the expectation diverge — report the place, the counterexample
and the proposed decision to the author of the norms; the decision is reflected in the norm, the contract, the instructions and
the affected acceptance. Do not carry a difference of the implementation into the canon silently; an arbitrary refusal does not replace a missing norm, do not add a new
mechanism only for the sake of an unsupported case. Record a change of the acceptance or a recurring error of its interpretation
in `corrections-<K>.tsv` (historical correction record) of the chapter; do not leave a new rule only in the instructions.

## Glossary

Some words of the norms have more than one meaning; the place of the word tells them apart. This table adds no rule and renames nothing: each meaning is the one the named place already gives.

| Word | Meanings | How to tell them apart |
|---|---|---|
| console | (1) the process of this lesson, the cluster console: its doors are the chapters 6.1–6.9, its unit, flags and exit codes are [lifecycle](../lifecycle.md); (2) the domain console, the process of lesson [P/10](../../10-domain-console/spec/10-domain-console.norms.md), to which the cluster console forwards `/domain/*` ([chapter 6.7](06.7-console.norms.md) N1.2, N1.3); (3) the console module, the files of lesson [P/07](../../07-console-module/spec/07-console-module.norms.md) that the console serves byte for byte ([chapter 6.5](06.5-console.norms.md) N1.1 `module`); (4) the writer `console` in the column `ops` of the data catalogue and in «writer: the console» of [chapter 6.1](06.1-console.norms.md) N1.1 | «domain console» or P/10 — the process of the domain; «module» or P/07 — the served files; a writer of a row — the role; otherwise — the process of this lesson |
| the gate, the guard, `guard`, `guards` | (1) the gate of the console: the states `on`, `open`, `shut`, the identity and `need` ([chapter 6.3](06.3-console.norms.md) N1.3; «Task» of these instructions calls it «the guard»); (2) a condition on another row of a store write: `guards` of the batch door ([chapter 6.1](06.1-console.norms.md) N2 «Batch door»; P/01.1 N1 `guard`), the guard `<s>/opbusy/<root>` of a step batch (chapter 6.3 N1.9 «Batch rows»); (3) the claim guard `<sub>/idem/<key>` of the write doors ([chapter 6.1](06.1-console.norms.md) N3 «repeat memory»); (4) the epoch guard of a holder over `<sub>/state/<name>/<id>` (chapter 6.1 N1.1) | the identity, `need` or the states of the console — the gate; `guards` of a body or a key with its index — a store condition; «claim» or `Idempotency-Key` — the claim guard; «epoch» — the guard of a holder |
| door | (1) an HTTP door of the console: a path with its methods ([chapter 6.5](06.5-console.norms.md) N2; the [contract](06-console.api.openapi.yaml)); (2) `door.pass`: the key of the manifest and the path `/{pass}` by which the console passes a request to a live worker with a door, of the first or the second kind (chapter 6.5 N1.8, N2 «`door.pass`»); (3) a door route `door.routes`: `/<s>/<route>/<id>[/…]` to the live holder of the unit ([chapter 6.3](06.3-console.norms.md) N1.9 «Door route»); (4) the door token that the console puts into `Authorization: Bearer` for the worker, signed by the row `door/signer` (chapter 6.5 N1.8, «Data families»); (5) a door of the store (P/01.1) that the console calls | `door.pass`, `door.routes`, «door token» and `door/signer` name their meaning; «the store door» — the store; a path of the contract — an HTTP door of the console |
| pass, ticket | (1) `door.pass` of the first kind: the request goes to the worker with a door token (chapter 6.5 N1.8); (2) `door.pass` of the second kind: a ticket instead of a human credential, the worker calls the console back by the ticket of the request ([chapter 6.3](06.3-console.norms.md) N1.9; `via: ticket` of `GET /session`); (3) the step ticket of a group operation: the header `X-W2C-Pass-Ticket` of a step call and the step batch ([chapter 6.9](06.9-console.norms.md) N2 «Step call», «Step batch»); (4) `<sub>/controller/pass`, the pass report of the controller (P/04 N1.2), an object, not a request | «first kind» or a door token — (1); a ticket of a request of a person — (2); a step of an operation — (3); `controller/pass` — (4) |
| `revision`, index, version, `rev` | (1) `revision`: the edit counter of a row, an integer, 1 at creation, +1 per edit ([chapter 6.1](06.1-console.norms.md) N2 «Versions: `revision`, index, `ETag`, `If-Match`»; chapter 6.6 N2.1 «Row version»); (2) the index: the version of the store row (P/01.1 `index`), the condition of `cas` and of a guard, given as `ETag` in double quotes (the same section of chapter 6.1); (3) `rev`: the revision of the manifest row `platform/manifest/<sub>` ([P/02.3](../../02-installer/spec/02.3-installer.norms.md) N1.5), also `manifest_rev` of a placement | `If-Match: 3` (a bare integer) — `revision`; `If-Match: "17"` and `ETag` — the index; «the read version» of a `cas` — the index; `rev` of a manifest — the manifest row |
| unit, row, table | (1) a unit: an entity of a subsystem declared by `unit.rows`, its row `<sub>/<rows>/<id>` and its doors ([chapter 6.1](06.1-console.norms.md) N1.2, N2); (2) a row: any row of the store (P/01.1), among them the rows of the console ([chapter 6.6](06.6-console.norms.md) N1.1) and the rows of the families of `data/`; (3) a declared table: `tables` of the manifest, its rows `<sub>/<table>/<name>` ([chapter 6.1](06.1-console.norms.md) N1.6); (4) a table of the text: a Markdown table of the norms or a file `forms/*.tsv` | `unit.rows` or `/{rows}` — a unit; `tables` or `/{table}` — a declared table; a key of the catalogue — a row; a table of the norms or the forms — text, not data |
| body | (1) the HTTP body of a request: it is read bounded, the limit `body` of the gate ([chapter 6.3](06.3-console.norms.md) N1.3) and «the console request body» of the ceilings ([chapter 6.1](06.1-console.norms.md) N1.4); (2) a body (`blob`): a field of a unit declared as a blob, stored as the object `<sub>/blobs/<digest>`, written by `put_body` and cleaned by the body sweep (chapter 6.1 N1.5, N3); (3) the body fields of a request row by `requests.schema` of the manifest ([chapter 6.4](06.4-console.norms.md) N1.5) | the reading of a request, 413 and «a body of N bytes» — (1); `blob`, a digest, the sweep — (2); a request of a subsystem — (3) |
| mark | (1) the request mark `objects/<sub>/commands/<rid>` ([the request and its mark contract](../../common/contracts/request-mark.md) «Mark»; [chapter 6.4](06.4-console.norms.md)); (2) an operator mark `POST /marks`, a line of the event journal ([chapter 6.4](06.4-console.norms.md) N2; the entry `marks` of chapter 6.3 N1.9); (3) the marks of the body sweep ([chapter 6.1](06.1-console.norms.md) N3 «body sweep — marks in the background, deletion in a maintenance window»); (4) a contender mark ([the observation contract](../../common/contracts/observation.md) «Freshness of a contender mark: `CONTENDER_FRESH`»; chapter 6.5) | `rid` and `objects/` — the request mark; `/marks` — the journal; digests and the sweep window — the sweep; `CONTENDER_FRESH` — the contender |
| reaper, sweep | (1) the request reaper: every `CLEAR_EVERY` it removes the answered, every `SWEEP_EVERY` it closes the abandoned ([chapter 6.4](06.4-console.norms.md) N3); (2) the table reaper by `delete_after` (chapter 6.4 N3 `tables`; [chapter 6.1](06.1-console.norms.md) N1.1); (3) the folder reaper ([chapter 6.8](06.8-console.norms.md) N3); (4) the operations reaper ([chapter 6.9](06.9-console.norms.md) N3); (5) the body sweep: the row `<sub>/sweep` and the sweep window command ([chapter 6.1](06.1-console.norms.md) N1.5, N3) | the row it removes names the reaper; `<sub>/sweep` and «sweep window» — bodies; `SWEEP_EVERY` — requests, not bodies |
| open | (1) the state `open` of the gate ([chapter 6.3](06.3-console.norms.md) N1.3 `gate`; «loopback — operator» only in `open`, N1.8); (2) the field `open: true` of `GET /session` at an open console (chapter 6.3 N1.3 `session`); (3) `open_routes`, the routes without an identity (chapter 6.3 N1.3); (4) the opening of an envelope by its recipient ([P/03.5](../../03-worker/spec/03.5-worker.norms.md); [chapter 6.2](06.2-console.norms.md)) | a state of the gate or `/session` — (1), (2); `open_routes` — (3); an envelope or a secret — (4) |
| operation | (1) a group operation: the row `<sub>/operations/<id>`, its steps and counters ([chapter 6.9](06.9-console.norms.md)); (2) an operation of the store: read, write, batch (P/01.1 N3) that a procedure of the console performs | `/<s>/operations…`, a step, `opbusy` — (1); `cas`, a version, `written` — (2) |
| holder, worker | (1) a worker: a process of a subsystem (P/03), the writer `<s>worker` of the catalogue; (2) the holder of a unit: the live worker that holds it, the address of `/where/<id>` ([chapter 6.5](06.5-console.norms.md) N3) and the target of a door route (chapter 6.3 N1.9); (3) the holder of the domain in the late layer: `domain/holder`, «at the holder» of the break-glass entry and of the function `may` ([chapter 6.3](06.3-console.norms.md) N1.3, [chapter 6.7](06.7-console.norms.md) N1.9) | «holder of the unit» or `/where` — (2); the domain, `domain/holder`, grants — (3); otherwise «worker» — (1) |

## What to create

- **6.1.** The conversion of the typed fields of the manifest into the row elements and back per N1.2. Separately keep
  the absence of `inherit`/`json: null`, the secret mask and the write constraints of the `blob` digest. The creation, the edit and the deletion
  of units per N3: numeric and named ids, the replay claims, `revision`, tombstones. The HTTP answers are formed per N2;
  the store row and the answer object have different value types. The blob door and the table operations with CAS. The cleanup by the
  maintenance phases with acceptance evidence for the refusals of reading, publication and copying.
- **6.2.** The recognition and masking of secrets, the sealing on write and the resealing at start per N1.2 and N3,
  the check of `bound_to`, the handling of addresses by the manifest and their diagnostics. The row readers and the rights generator — P/02.5; the replay
  memory — chapter 6.1; the commands `new|seal|rotate|status` — P/02.4.
- **6.3.** Sessions and grants per [chapter 6.3](06.3-console.norms.md) N1.3 (the guard, `/session`); the keys `rights:` N1.5.
- **6.4.** The console merge; the submission of a request, the accounting and the reaper. A whole copy of a file, a source that answered, a confirmed mark
  and a published outcome are different boundaries of confirmation, one does not prove another.
- **6.5.** The console process and the shell boundary that respect the root and mounted routes; the serving of the published files
  of the module (N1.1 `module`) as they are. Its own HTTP doors per N1–N2; the observations `/servers`, `/resources`, `/where`.
  Full answers and safe output, including separate checks of CSP, media type and HEAD without a body. **The representation
  `ManifestView` for `GET /manifest`** (N2 «GET /manifest»); the built-in load procedure (P/02.1) gets no new HTTP route.
  The forwarding of `door.pass` to a live worker with a door (N1.8), the second kind: the ticket, the headers, the answer types, the stream — the gate-and-pass contract «Pass of the second kind»; the callback — chapter 6.3 N1.9.
- **6.6.** The operator doors of the console: of the policy, the drain, the labels, the server decommission, `/unplaceable` and `/where` — the HTTP doors
  of N2 of chapter 6.6 and the evidence of the fulfilment of the items P/06.6-01, -02, -03. The check of the schema and the versions before the console start, the raise
  of the schema and the door `/schema`; the observation of the drain by the given freshness bounds ([the observation
  contract](../../common/contracts/observation.md)) — P/06.6-04…06.
- **6.7.** The forwarding by one function per the forwarding contract (transitions 1–2) and its refusals N4; the `where` of a member; the `https://` client to
  the console of another cluster with the `peer` check; the forwarding to the signer in the order of N1.8; `may` by the copy of grants and `grants` in
  `/session` (N1.9); the emergency entry door in order with its own limit (N1.10); the doors `/domain/keys`, `/api/held`,
  `/api/backup`, the book door and `GET /domain/shared/<sub>` with the function `resolve` and a command for its vectors.
- The description of all the choices of the sections «Implementation decides» of the chapters — 37 items «Implementation decides» in all — and the means of executing
  the acceptance.

## Order of work

This is a suggested order, not a mandatory structure of the code.

The dependencies in `forms/stages.tsv` retain the full stage chain. Finishing the ordinary slice described under «The whole lesson»
does not complete `late_domain` or `complete_console`: unavailable domain neighbours and their positive checks remain unchecked
dependencies. Independent work can continue without marking those stages PASS.

### Chapter 6.1 — the units door, bodies, tables

1. Write out the key families, their writers and the row forms from N1. Check which fields are taken from the manifest
   and which belong to the platform. Do not carry the placement and heartbeat fields into the unit row.
   Count the UTF-8 bytes of the full key together with the prefix and the separators; a component limit
   does not replace the store limit. Handle a defined badkey per N3, including
   the pending state; the worker branches (guard, slot, epoch, holds) — P/03.2.
2. Implement the value conversions. Check the type before the conversion: a boolean does not become an integer,
   a quoted number does not become a number, a list does not become a string. On creation prepare every field per N1.2:
   the passed value, the absence of inherit (not passed or `null`), default, the empty form of the type. Check required by the original body.
   On an edit the unset fields are kept, default is not applied again. The source field of a named id
   is immutable regardless of fixed in the manifest: a passed new name gets 400 at step 4 after the row read.
   Check against the vectors `values-by-type`.
3. Perform the passes of creation, edit and deletion in the order of N3. For creation trace separately the claim,
   the counter and the row: these are different writes. Analyse a break after each of them, a retry with the same and a different fingerprint,
   `pending` before and after 30 seconds and a refusal after the reservation of a number. The takeover must cut off a late executor
   by atomic guard/cas on every write; a read of the claim before a write does not prove this. Check 5xx:
   with a written unit or an unknown outcome pending is kept, a foreign claim must not be removed.
   The checks unique/ref/must_match are preliminary: separate CAS of units do not make them atomic.
   The placement controller does not promise a background detection of a violation; check a race with this boundary of N3.
4. First put the blob durably, then the CAS of the row. Marks are allowed in the background; deletion only after all
   writers/copying are stopped, a repeated full traversal and by the phases of N3. Do not use an idempotent put as a proof of a change
   of the index. Apply P/06.1-R120 to the entire console instance: two admitted unfinished blob PUT requests across all subsystems,
   doors and connections; admission precedes body reading, and a place remains occupied until the full response or request termination.
5. Implement the tables as a full replacement by the manifest with CAS; `Idempotency-Key` is optional, with it — the replay memory of N3. Do not output secrets;
   a spoiled row differs from a read failure (N1.6, N2).
6. Prepare the instances by the acceptance README. Then separate probes of the maintenance window and of the full answer; the copy
   of the body at the resource and its refusals — [the instructions of P/05](../../05-resource/spec/05-resource.README.md).
7. Check N2 separately from the partial expectations of the TSV: the mandatory fields and types of the full answers, the masks,
   `worker: null` on creation, the same full answer on a POST retry, the form of the deletion and of the refusals.
   Values inadmissible for any unit.id are rejected by the schema; the chosen kind of id is checked separately.
   GET/DELETE do not return the fault of the write field check: their 400 contains only detail and error.
   Errors that the table checks only by code do not exempt from checking the body by the contract.
   A body below the HTTP limit can exceed the row ceiling: 413 row too large is kept as the POST answer,
   the unit is not created; an edit keeps the former row/revision. Before creation check also the future
   done claim with the full answer: the success of a unit must not make a retry non-storable.
8. Fill all the items of the checklist of chapter P/06.1. For the parts outside the TSV attach the reading evidence by the table of subjects of N5
   (for each subject a scenario or an exercise of the owner lesson is named there) or the result of the corresponding stand
   [P/04](../../04-controller/spec/04-controller.norms.md), [P/05](../../05-resource/spec/05-resource.norms.md), chapters 6.2–6.6
   and lessons P/08–P/10. A reference to a future stand is not a check by itself.

### Chapter 6.2 — the write of secrets

1. Write out the outputs of N1.4: the answer, the replay copy, the snapshot, the journal, the heartbeat, argv and the refusal.
   Check the secret fields at any depth; the table and the unit row have different
   output rules. The text of a refusal is also an output that can disclose a secret.
2. Check the address rules on all rows of the vectors `secret-in`, and the log mask —
   on all rows of `log-mask`. Use the fields named in the table (`fields.yaml` of the vectors `secret-in`),
   do not substitute them by the rules of testsub2. Compare the full display and the absence of a leak in a refusal.
3. Implement the sealing by the sealing contract, the ring and the states of an absent/unreadable key per N1.2.
   An empty/damaged file does not turn on the development mode. The opening with a wrong
   key, kid, row and field — at the worker, chapter [P/03.5](../../03-worker/spec/03.5-worker.norms.md), and the vectors
   `sealing`; a visible prefix enc:v2 does not prove a successful encryption.
   Check the ring comments: # at the beginning of a kid is forbidden, inside it is admissible; a comment
   on a separate line, after a key entry — a refusal. In the diagnostics the actual kid is substituted.
4. Embed the write into the existing POST/PUT of chapter 6.1. Before the POST claim check the constraint
   of the mode without a ring: a non-empty secret at any depth — 400 sealing key required,
   without a new claim and without a change of an existing one. With a ring the HMAC is computed over the original
   request, not the mask; on a retry — under the kid of the stored fingerprint. A mask and an external envelope are refused;
   absence, an empty string and null for a top-level secret on PUT keep the former secret; a json field with
   nested secrets is replaced as a whole, without keeping by index (N3 step 3). A change of bound_to without a new
   secret — 400, also for a row without a secret; it is checked against the row being kept under CAS, including a retry after a conflict.
5. Use the claim ownership rules of chapter 6.1: 5xx does not become done; do not remove a foreign pending;
   a confirmed or unknown write of a unit keeps pending.
   For a set unreadable ring check SealingUnavailable on any POST/PUT of a unit, also without a non-empty secret field, before HMAC/the claim. GET/DELETE keep their outcomes.
6. Perform the maintenance by the table of N3. One operator, the ordinary writes are stopped;
   rotate accepts the area kN, an unsuitable input keeps the file. The old keys remain,
   entirely: the deletion of former keys is outside the profile of the chapter. Zero envelopes does not remove
   the dependency of live HMAC claims and copies. A traversal error does not mean zero.
7. Prepare a separate instance, the ring and two manifests by the acceptance README of 6.2. Prepare c1
   before the HTTP scenarios; run the file as a whole in order, keeping the rows between scenarios.
   On a repeated full run use new data and claim memory. Check
   the key substitutions and the role store, including the explicit switch in sc. 06.
8. Close all the items of the checklist of chapter 6.2. Separate evidence is needed for the rotation
   (the opening by the worker — P/03.5), the file rights, AAD, nested fields and the refusal of an unreadable ring.
   The HTTP scenarios do not fully observe these properties.

### Chapter 6.3 — the guard and people

1. Compose a closed list of routes, methods, lanes and maximal bodies. Parse /session before the ordinary admission, but
   erase X-User before any branch. For a body-dependent grant obtain the required capability in advance, the specific units —
   after a bounded read; the write only after all checks ([chapter 6.3](06.3-console.norms.md) N1.3,
   [chapter 6.5](06.5-console.norms.md) N3).
2. Connect the three session states (`open`, closed to an anonymous one, a proven identity with `via` and `grants`;
   [chapter 6.3](06.3-console.norms.md) N1.3 `session`). The closed `may` of the module — [lesson P/07](../../07-console-module/spec/07-console-module.README.md).
3. For the keys `rights:` — reconcile the console test of the implementation line by line with [chapter 6.3](06.3-console.norms.md) N1.5 (`routes`,
   `cluster_rows`, `unit_of`, `reach`, `names`); the action `reach.requests` — the field `action` of the request body
   ([chapter 6.4](06.4-console.norms.md) N1.5 `action`).
4. Pass the acceptance of [chapter 6.3](../acceptance/3/README.md) — scenario 03, in isolation. Check separately the grants with the domain
   stand: the guard branches 401/403/503, the order of `identity`, Origin by the cookie are not executed in the acceptance TSV.

### Chapter 6.4 — requests and events

1. Merge the resources with deduplication and a bounded wait. Distinguish complete, partial
   and truncated; name the loss of a source in incomplete. A late answer is not appended
   to an already sent JSON. Do not promise a common snapshot of the resources. A live resource — a door row fresh by
   [the observation contract](../../common/contracts/observation.md) (`≤ LOST_AFTER`).
2. An ordinary request contains unit, free_ask does not ([chapter 6.4](06.4-console.norms.md) N1.5).
3. Separate ordinary requests, the append, elsewhere and free_ask per N3. The append creates no mark: fetched, the removal
   of the row and the release of asked; a retry decides by the data. For the ordinary profile perform the table: the admission and the term,
   a confirmed begun, the single call (the holder side — [chapter 3.6](../../03-worker/spec/03.6-worker.norms.md)).
   Check a conflict and an unknown outcome of every read/change. The presence of begun does not yet prove the call of the external
   action. The action of a request (for `elsewhere`) — the field `action` of the body.
4. Close the lifecycle: the result of the one that began wins over the closing of a foreign begun; the reaper writes
   by index and then removes the row not earlier than the local age settle. Check clear, sweep and a late submission; after
   a restart the count is new. The accounting is updated by CAS. The mark is deleted only by the holder
   after the disappearance of the row and kept. The boundary of the replay memory is reported to the client.
5. Pass the acceptance of [chapter 6.4](../acceptance/4/README.md) — scenarios 03, 04, 06–12, each in isolation (the step count — in the
   acceptance README). Check the full answers by the owner of the form, even when only a code is expected in the TSV. For each checklist item
   name a separate observation; the probes outside the TSV are listed in the acceptance README. The vectors `rid`, `requests-body` and
   `request-digest` — one function of the side at the door and at the worker.

### Chapter 6.5 — observations

1. Implement the observations /servers, /resources and /where. Keep the age of the seen changes on the local monotonic clock.
   Return the unavailability of a mandatory read as a refusal; never replace a proven absence by it (N3). The liveness
   boundary — `≤ LOST_AFTER` by [the observation contract](../../common/contracts/observation.md).
2. Do not update the age of a snapshot shard at the console after a failed read (N1.3 `age`).
3. Prepare a fresh stand testsub/testsub2 without the domain and background processes (sc. 08–10 raise them by the directives
   `@start`). Run scenarios 01–17 by [the acceptance README](../acceptance/5/README.md). The console module — in the console build,
   not from the export catalogue (N1.1); one unreadable record (a heartbeat, a shortage) does not bring down `/servers` and `/metrics` (N0 P/01.1
   «Stability of output»). For each own answer check the full contract and the media type, not only
   the subset of the TSV.
4. Reconcile the successful answer of `GET /manifest` with the schema `ManifestView`, and the common refusals of the console — with the schemas of their code.
   The load diagnostics and the stderr of the installer do not become bodies of this GET.
5. Check separately the page, the publication of the module and CSP; a stand with a holder is needed for the branches absent from the TSV.
   Record the chosen limits/lanes/timeouts from the section «Implementation decides». Check the constraints of `door.pass` on
   a separate test door of a subsystem.

### Chapter 6.6 — the control doors

1. Introduce three outcomes of the schema read: absent, read, unknown. Before the raise forbid the starts of old
   builds/their writers, including silent nodes. Check its own and the observed schemas, then CAS (N1.1a, N3). The schema at start
   is checked by the console too; the daemon of the opaque string store is explicitly excluded.
2. Take the full forms of drain (N2.2). Distinguish safe by observations from a confirmed rest before the shutdown;
   missing/stale pending — unknown, not zero (N1.2).
3. Make the doors per N2. The policy and where belong to the subsystem; drain and servers — to the console root.
   In UnitRef and both maps of drain the subsystem name follows [N1.2 P/02.1](../../02-installer/spec/02.1-installer.norms.md#n12-document):
   the whole closed list of reserved names applies both to the reference prefix and to the map keys.
   The field subsystem has the same grammar; the agreement of the map keys,
   the values of subsystem and the visibility are checked separately from the schema.
   For the labels the probe does not write, PUT returns the forecast will_move by references sub/id with the filter view.
   Separate 202 of an accepted decommission from the actual completion by the controller and 404 of an absent route
   from an absent server or placement. Gone does not allow decommissioning a responding server.
4. Run the acceptance of chapter 6.6 by its README: sc. 01–07 — on a separate instance without workers in the order of the file, do not
   reset u1 between 01 and 02 (and up to 07); sc. 08–12 — each on a fresh stand. A repeated run also clears the POST claims
   and the id memory.
5. Check the full HTTP answers by the contract of the lesson beyond the partial expectations of the TSV. The success of an empty object
   means {}, not the absence of a body. For drain check separately the agreement of the maps, the counters and safe;
   for where — the rights to door, the reason and the admissible lag of directory. The schema does not prove these relations.
6. The evidence of N5 for P/06.6-01, -02, -03 — the table «Evidence outside TSV»; the reading evidence of the controller branches —
   [the instructions of P/04](../../04-controller/spec/04-controller.README.md) «Order of work», step 8.

### Chapter 6.7 — the cluster console in the domain

A chapter of the late layer: it is done after the lessons P/08–P/10, with the domain stand.

1. Build the forwarding function by [the forwarding contract](../../common/contracts/forwarding.md) «Forwarding is one function»
   and the table «Domain doors»; N3 «forward» — in order: a path outside the table — 404 before the identity and without a call. Give the answer
   as it came, without parsing it ([chapter 6.7](06.7-console.norms.md) N1.2–N1.5).
2. The `https://` client to the console of another cluster — the role `console`, the check of the server by the function `peer` by `Entry.ca` of the
   destination member ([the `peer` contract](../../common/contracts/peer.md); the vectors `common/vectors/peer`).
3. The forwarding to the signer (N1.8) and its own doors `/api/held`, `/api/backup` (N1.12, N1.13; the signature — the vectors
   `common/vectors/ask-sig`).
4. The gate with grants (N1.9; the function `may` — the vectors `common/vectors/may`), the emergency entry in order (N1.10) with its own
   limit count, `/domain/keys` (N1.11), the book door (N1.1), the value on reading (N1.14) and the command `resolve`.
5. Pass the vectors [`resolve`](../vectors/resolve/README.md), [`key-families`](../vectors/key-families/README.md) and the acceptance of [chapter 6.7](../acceptance/7/README.md) on the domain
   stand; the steps of the cluster console in the acceptance of the chapters of lesson P/08 — there it is a neighbour on the stand. TLS between clusters and the branches
   that the stand does not call — by reading (N5 of the chapter).

### Chapter 6.8 — cluster folders

1. Build the chain pass: three outcomes, and «unknown» separately from «no». The read doors give out only live folders.
2. Every write is one batch `op: batch`: the folder row, the membership rows, the guards of the ancestors and of the added units. No write changes one side of a link without the other.
3. Insert the removal from folders into the deletion of a unit and into `delete` of the batch door, insert the parsing of the folder rows into the pass «batch» of chapter 6.1.
4. The folder reaper is its own work: not in the maintenance window, `cas`, an unknown read removes nothing.
5. Pass the acceptance of [chapter 6.8](../acceptance/8/README.md); the rights and strict races — by reading per its README.

### Chapter 6.9 — group operations

The chapter is done after the ticket and the second kind of pass.

1. The reception: the step rows, then a batch of `N + 3` rows. The console does not parse the body and the root.
2. The leader: the queue by the contract, the generation right after the take, a traversal on every tick, including on pause.
3. The step: read the result before the call; a ticket for one call; `step_key` on every retry.
4. The completion by one batch; the rebinding; `retry-failed`; the operations reaper; the step rows in the resealing.
5. Pass the vectors [`op-step`](../vectors/op-step/README.md) and the acceptance of [chapter 6.9](../acceptance/9/README.md); the plan of its other scenarios — the acceptance README.

### The whole lesson

Run the acceptance scenarios separately, with the preparation named by the acceptance README of the chapter: in all the lesson has
141 scenarios / 1529 steps — chapter 6.1 (`acceptance/1/`: 01–46), chapter 6.2 (`acceptance/2/`: 01–11), chapter 6.3
(`acceptance/3/`: 03), chapter 6.4 (`acceptance/4/`: 03, 04, 06–12), chapter 6.5 (`acceptance/5/`: 01–33), chapter 6.6
(`acceptance/6/`: 01–17), chapter 6.7 (`acceptance/7/`: 01–03, 06, 13–18; the domain stand), chapter 6.8 (`acceptance/8/`: 01–12), chapter 6.9 (`acceptance/9/`: 01–02). Fill the checklists of the chapters
with the evidence from N5 of the chapters.

The ordinary P/06 stage can finish before progression to P/07 and P/08 when its non-domain responsibilities are implemented and all published
executable targets of the ordinary stand and their vectors pass. Available non-domain pass checks belong to this stage too, including scenario 04 of
[the pass stand](../../common/acceptance/pass/README.md). Chapter 6.7 and the positive group-operation and pass checks that require the domain stand
(including its person and ticket setup) are recorded separately as unchecked dependencies;
return to them after P/08–P/10. Continue the independent process work, including the reapers, resealing and the feed.
Scenarios 01–02 of acceptance 6.9 confirm only the absence of operation doors without a declaration. They do not close the positive OPS checks
or the chapter's readiness checklist. A `not_executed` check remains unchecked and does not count as PASS.

## Pitfalls of the language and the library

| Norm | Possible error | How to keep the behaviour |
|---|---|---|
| 6.1 N1.2, N3: value types | `true` is taken for 1; `"7"` is cast to a number | distinguish the JSON types before the numeric check; sc. 08 of chapter 6.1 |
| 6.1 N3: `required` | a truthiness check refuses `0`, `false` or `[]` | check the presence and exactly the empty string; do not generalise this to all empty values |
| 6.1 N1.2: `inherit`, `json: null` | the serializer writes an absent field as `""` or `"null"` | keep the absence of the element; sc. 10 of chapter 6.1 and the reading of the JSON conversion |
| 6.1 N1.2: list | splitting by comma spoils `"a,b"` or a leading `[` | use JSON also with an empty element; [] and [""] must differ after a restart/edit; check the placement labels separately; sc. 09 of chapter 6.1 |
| 6.1 N1.3: name | an ASCII regular expression lets through forbidden Unicode categories | additionally check Cc, Zl, Zp and Nd outside ASCII; do not forbid the admissible `a.b` |
| 6.1 N3: replay key | the limit 200 is counted in characters, only the body is compared, or only the unit rows are cleared | reject .. before the write of the claim; count UTF-8 bytes; the fingerprint includes the caller, the method, the path and the body; the acceptance starts with empty claims |
| 6.1 N3: a write with `cas` | the write is repeated with the old version or the old check result | reread from the indicated step; in an edit check `fixed` and the former `blob` digest again |
| 6.1 N3: takeover of pending | a late console continues after a foreign CAS | the claim guard on the counter and the unit, CAS on the claim itself; on the loss of the version — the outcomes of N3, not the appropriation of a foreign version |
| 6.1 N1.4/N2 | maxLength is counted as a limit of UTF-8 bytes or Content-Length is trusted | count the real bytes; separately 32 MiB blob, 64 MiB copy and 4000 for a JSON field |
| 6.1 N3 | a repeat of put_durable necessarily changes the index | the admission of deletion is ensured by the window without writers; check the same digest/the same index |
| 6.1 N2 | an identical table POST is considered a safe retry | stamp/the journal change; first find out an unknown outcome by reading |
| 6.2 N1.1/N3 | the mask was taken for «keep», null was written as a string | the mask — a refusal; null/emptiness/absence on PUT — the former value |
| the sealing contract | the plaintext was normalised or the AAD separator was replaced | the UTF-8 bytes as given; AAD = the row key + NUL + the full JSON Pointer, including the indices; do not try the old joining |
| 6.2 N1.2 | a ring read error became an absence of the setting | distinguish the states; a set unreadable ring forbids all POST/PUT of units |
| 6.2 N1.2/N3 | max for rotate was applied to arbitrary kids | refuse outside kN; check the number before changing the file (the command — P/02.4) |
| 6.2 N3 step 3 | the nested secrets of a json field were kept by array index | replace the field as a whole: the password of an element does not pass to a neighbour after a permutation |
| 6.2 N1.1a A2, A6 | the end of a free-text address (a quote, `<`) was applied to a field value | a field value is one address; a character outside the RFC 3986 grammar — `bad_url`; the mask — up to the end of the pair value |
| 6.2 N3 «reseal at start» | an unreadable row broke the console start | skip the row with a log line, reseal the others |
| P/02.5 N1.3 | the exact name of a secret is treated as a prefix | a prefix only with a trailing `/`; reconcile the effective readers with P/02.5 |
| 6.2 N2/N4 | the console 503 was given as `{kind,error}` of the store | the unit write needs detail/error and the established reason |
| 6.2 N1.4 | a refusal or a debug line repeats the password | check the outputs after masking, including nested addresses |
| 6.3 N1.3 / 6.5 N3 | the absence of a key and a read error become one empty value | 503 on unknown trust; only a reliable absence of keys and traces is open |
| 6.4 N3 | an old reaper overwrote the outcome or deleted a new row | closing/deletion by indices; a late result of the one that began is kept |
| 6.5 N3 | the heartbeat clock is taken for the observation age | count the age from the local change; the author's clock does not confirm freshness |
| 6.5 N2 | HEAD serialises JSON or text/html is checked as JSON | HEAD without a body; the media type per operation |
| 6.5 N2 «GET /manifest» | the serialisation of the internal structure adds a revision or service fields to `ManifestView` | reconcile the mandatory fields and closed objects with the schema; there is no revision in the answer |
| 6.5 N1.8 | the proxy began to give success, then discovered a large answer | a buffer up to 4 MiB before the headers; a local 502 on excess, without redirect |
| 6.6 N2.1: labels | the anchor $ lets through a trailing newline | check a, vlan:a and a\n as different cases |
| 6.6 N2: counters | true is taken for 1 | JSON booleans are not numbers |
| 6.6 N1.2: drain | would_strand is taken for the negation of safe | an unplaced unit can be in the probe with safe: true |
| 6.6, 6.5: freshness | «changed < 45 s» instead of «in the last LOST_AFTER» | an age of exactly LOST_AFTER is fresh ([the observation contract](../../common/contracts/observation.md)); the boundary — the vector [`fresh-age`](../../common/vectors/fresh-age/README.md)  |

## Boundary checks

### The full URL of a subsystem

For the subsystem paths the contract sets two standard servers: the console origin and
origin/{sub}. A path of paths is appended to the first or the second; origin has no
trailing slash. localhost/testsub — substituted examples, not launch settings.
The short path is chosen by CONSOLE_ROOT, the prefixed one — by the named loaded manifest.
Reconcile both URLs, the methods, the codes and the bodies with N2 of chapters 6.1, 6.6 and [chapter 6.5](06.5-console.norms.md) («Complete forms and bounds N2»:
origin without a trailing `/` or origin/{sub}; the common `404 NoRoute`, `405 {detail: method, error: method}`). The common doors (`/drain`, `/schema`, `/changes`, `/servers/{server}/…`) and the resource door (P/05) do not get a prefix from a neighbouring path item.
Read the existing scenarios root and testsub2 as a control of routing; structural validity does not execute HTTP.

### Mount checks

Reconcile the full URLs per N2 and the contract of the lesson: read the standard servers together
with paths, not only the key paths or x-mounting. Make the same request to root
and /testsub2 with the chosen manifest. The observation /servers has both variants, and the operations
/servers/{server}/labels and decommission remain common. Requests (chapter 6.4) always go through
/{sub}/requests and /{sub}/asked/{sha16}, even for root; do not add short paths.
GET/HEAD of the page of a mounted subsystem without `console.shell` are both 404, HEAD has no body; with it — the shell (N1.1 `mounted`);
summary and the text of 405 must correspond to the actual list of methods.

### Chapter 6.1: weights, bodies and tables

By the separate rig of the acceptance README check the weights -1/0/1 and omission without a default. The lower bound
acts on a supplied or default-filled value, including a passed PUT; the empty type form prepared for an absent field
without a default does not trigger it. A refusal does not change the row. Type and numeric-form refusals follow the row
check contract's «Refusals»: booleans, arrays and objects for an int field give `type`; a numeric string or a number outside
the field's range or notation gives `not_number`; a present integer less than 1 gives `type` without fault.

For a table 400 check the full text and structural refusals. The common TextRefusal/FormRefusal intersect without fault,
hence anyOf, not oneOf; check all local oneOf for the intersection of branches.

Check the template of the table notches with three substitutions by the owner P/02.1. The names of tables/rows: lowercase ASCII 1–32,
the bans of families/doors, Audit and 33 characters are rejected on loading.

Reconcile the ban of table names with every row family of the layout of N1.1: including next_id, placement, workers, sweep and
the actual unit.rows. Do not forbid the neighbouring admissible names (placement_log, workers2) by prefix.

Check the name area of all added fields: rows=cluster/worker/ts is refused, records is admissible; bytes+blob
is refused, bytes without blob is admissible. TableInput accepts the declared id and other names of the unit, but not
held_by/garbled; name is admissible only as a string with key=name. Additional probes outside the TSV.

The declarations of unit.fields with any platform_fields of N1.2 (including deleted) are rejected before the materialisation of default/inherit.
Check each element of the list, an empty declaration, default and inherit; the neighbouring deleted_flag/worker_label are admissible,
the names of table fields do not get this ban. Probes outside the TSV.

Blob: an empty name, /, %, dots, a space, control characters, non-ASCII and 65 characters are rejected by the loader; _, A,
payload_2 and 64 characters are admissible. A table blob is outside the profile, the ordinary table fields are not narrowed by this. Additional probes outside the TSV.

### Chapter 6.2: normalisation of the name

The normalisation probe of N1: pass%E2%80%8Bword after decoding/NFKC/removal of U+200B is recognised as password; the value and
the original spelling of the name are not normalised. Compare U+200B at the beginning/middle/end and an already ordinary password; check
the display of the mask by the original URL.

### Chapter 6.4: submission and merge

After any submission refusal the reservation is kept: a parallel retry could have used it. Check the schedule A
reserve → B accepted → A definite failure and the refusal of a new C at the limit 1; do not release a non-empty accounting by one age.
An unavailable read of the accounting — 503, a read spoiled form — 429. Sc. 05 admits a fast 200, rid computed from the
header before the submission (sc. 05 — the acceptance of chapter 3.6).

The probe of a break between the reservation and the row: a retry with the former key passes steps 4–5; one asked does not allow 202. Check
an absent, a matching and a foreign row, a ready/begun mark and an unknown read; a foreign row does not change, a refusal
keeps the reservation.

Merge: two sources with one different row each at limit=1 give one row and truncated=1. Two mirror copies with
the same visible e3 and a local truncated=1 give the total truncated=2; this is a counter of stages, not of unique events.
Check both keep, the priority of alarm and the same time with different ids. Additional probes outside the TSV.

### Chapter 6.5: the given form of `GET /manifest` and `Where`

Besides the load verdicts check GET /manifest: the name per P/02.1 N1.2, including console/audit;
eight field types, the values default/inherit by type, enum only for string/bool.
An absent default — null, an absent inherit is not given out; list — an array of strings,
json keeps an arbitrary JSON structure with the numeric limits of P/02.1 N1.1. Check not only
a number in a float field, but also the nested default/inherit of type json, and also display/servers/door/places/domain:
`1e309` and `-1e309` are forbidden at any depth, `1e308`, `-1e308`, null, bool and the string "1e309"
are not forbidden by this constraint. `JsonValue` recursively describes this common limit of the answer;
the precision of the original int and its lexical form are still checked by the loader before the JSON output.
The schema does not check that default belongs to the value
of the neighbouring enum: it is reconciled separately with the loaded manifest. A wrong ManifestView does not become admissible
because of a successful JSON parse or a check of only the list of types.

HTTP Where without a reliable door has no field door, rather than containing null; check also the negative HTTP example
door:null. The conversion of absence into null by the library for the shell — [the instructions of P/07](../../07-console-module/spec/07-console-module.README.md).

### Chapter 6.6: slot names in answers

The fields Where.worker and Where.directory (except null), and also the elements of SubsystemDrain.pending_unsaid
use slot names per P/03.2 N1.4.
The static form is the same as for RunningUnit; the agreement of prefix with the loaded manifest and the presence
of the corresponding worker are checked by meaning, not by one schema validator.

## Done when

All the choices of the implementation are described (the items «Implementation decides» of all chapters; the renewal step and the retries of capture and epoch — chapter
P/03.2), all the norms of the checklists of the chapters are fulfilled and the ways of checking are recorded: for each id — a specific piece of evidence
or an unchecked dependency. State the slice, the commands/stand, the observations and the limitations. The data of past runs do not replace
the preparation of a new one.

- **6.1.** The HTTP acceptance passed with the stated preparation, and the full answer bodies are reconciled with N2 and the loaded manifest.
  In RunningUnit the field worker has the form of a slot name of P/03.2 N1.4: emptiness, upper case, path
  separators and a trailing newline are rejected. The agreement with slot.prefix of the manifest is checked separately;
  worker:null on creation remains a separate form CreatedUnit.
  Reading covers the remaining subjects of N5; the claim is checked with the named interventions.
  Deviations from SHOULD are explained per N0.
- **6.2.** The vectors and the sequential HTTP file are executed, the separate evidence of reading/stand is named. The development mode
  without a ring is not declared a check of sealing; the JSON schema and the answer mask are not declared a check of cryptography.
- **6.3.** The evidence of the keys `rights:` is named: the console test of the implementation and the checked subject — N1.5 line by line.
- **6.4.** The evidence for the norms outside the TSV is named. Success, a known refusal and an unknown result
  of a publication are shown separately.
- **6.5.** The answer of `GET /manifest` corresponds to the contract; the door checks are performed per N5 and sc. 02 of the acceptance (P/06.5-01).
  The TSV confirms the open local mode; it does not prove the order of loading of the module, the atomicity of the snapshot or the epoch
  of the door. The compatibility of the common console module — a separate comparison of bytes and a reading by the module contract (lesson P/07).
- **6.6.** The acceptance of the chapter passed with the declared initial state, the full answers correspond to N2, and the remaining guarantees
  have evidence per N5.
- **6.7.** The vectors `resolve` and the acceptance of the chapter on the domain stand passed; the forwarding answers are reconciled as they came, not by
  the form of its own contract; the branches that the stand does not call (TLS, large and broken answers, the signer) have
  evidence per N5.

Success of the TSV confirms only the branches it observes. It does not prove the behaviour of two consoles, fsync, the mirror,
tombstones, concurrency and the real maintenance: they need a trace of the phases and a stand with failures. Before the conclusion «safe
to delete» confirm the stop of the writers and of the copying. A check of the schema does not check file durability or a race;
a reading of an algorithm does not prove execution in several processes. A check of the documents and of OpenAPI does not run the implementation
and does not check the constraints that depend on the manifest, the state, the rights or the UTF-8 size.

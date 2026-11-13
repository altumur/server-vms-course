# P/09 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/09-agent.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or person) who writes code from the lesson. The explanation of «why» is `ru/09-agent.md` (for people, not in the export).

Scenario names (`sc. NN`), vector case names and seam names identify the judge's checking data; scenarios, fixtures and expected results are not provided to the model. All implementation obligations are stated in the visible norms and contracts.

## Task

Implement the process `domainagent` in the language `<LANG>`: the agent of a member and the relay mode — by the two chapters of the lesson; pass
the N5 acceptance of the chapters and close their readiness checklists. 45 norms in all: P/09.1-01…36 and P/09.2-01…09. The holder side — lesson [P/08](../../08-domain/spec/08-domain.README.md), the domain console — lesson P/10,
the late layer of the cluster console — [chapter 6.7](../../06-console/spec/06.7-console.norms.md), the worker on the domain — [chapter P/03.7](../../03-worker/spec/03.7-worker.norms.md).

- **9.1.** The agent of a member: the member key and the member side in the acceptance (`join`); the report pass whole or as a delta with a signature; the book
  contributions and the objects of the report; the home record from the holder's answer only on a difference, and the freshness marks; the copies of placements,
  the application of edits and the outcomes; the local token door; the roads and `domain/reached`; the HTTPS client; following the holder and
  the switch point; the keeper's agent; the shared document at a member and the alarm page; the agent in the process; the row `domain/agent` and the answer
  `standby` — [chapter 9.1](09.1-agent.norms.md).
- **9.2.** The relay mode (`RELAY=1`): the agent door for the members behind it, the package to the holder with the knocks, the memory of the answers and
  `domain_age`, the cut, the token through the relay byte for byte, the server side of the door of the class `signed` —
  [chapter 9.2](09.2-agent.norms.md). The holder side of the package — the instructions of lesson P/08, chapter 8.3.

## Inputs and their priority

- The canon is the norms of chapters [9.1](09.1-agent.norms.md) and [9.2](09.2-agent.norms.md), including N0, the paragraphs «Data», the order of N3 and
  the refusals of N4. The input and the output of the acceptance commands — N5 of the chapters.
- The common algorithms are contracts; the chapters refer to them and do not repeat them: [the agent signature](../../common/contracts/agent-signature.md)
  (the agent signs — chapter 9.1, the owner; the relay verifies — chapter 9.2),
  [the local token door](../../common/contracts/local-token-door.md) (the role socket, the body, the answer, the refusals, «The call in the process»
  — chapter 9.1, the owner), [`peer`](../../common/contracts/peer.md) (the client, the first contact, the function `peer` — chapter 9.1,
  the owner), [the key set](../../common/contracts/keys.md) (the function `keys`, merge and prune of `domain/revoked` — chapter 9.1;
  `keys` of the package answer — chapter 9.2), [the domain envelopes](../../common/contracts/domain-envelopes.md) (the agent seals
  `x25519:v1` and opens `m1`; the relay carries `m1` without opening it), [the report acceptance](../../common/contracts/accept.md)
  (the function «accept» over the relay memory — chapter 9.2), [the term record](../../common/contracts/record.md) (following,
  the keeper, the shared document — chapter 9.1), [the sealing](../../common/contracts/sealing.md) (the home secrets — envelopes
  of the ring), [the role certificate](../../common/contracts/role-certificate.md#the-server-side-the-class-signed) (the relay
  door — chapter 9.2), [the forwarding](../../common/contracts/forwarding.md) (502 `did not answer` of the token door of the
  relay), [the event journal](../../common/contracts/event-journal.md).
- [The OpenAPI of the lesson](09-agent.api.openapi.yaml) expresses the HTTP forms of the agent doors: the tag `local-door` — the local door
  `/tokens/{sub}/{kind}` (the Unix socket of the role; the server is described by a reference to the contract), the tag `relay` — the relay door. The bodies
  of the publication, of the holder's answer, of the token request and of the package — the original is in [the OpenAPI of the process
  `domain`](../../08-domain/spec/08-domain.api.openapi.yaml) (`Publication`, `Carry`, `HolderAsk`, `Batch`,
  `RelayAnswer`): the relay door refers to them, the agent calls the holder doors by it.
- The forms of the rows and objects of the lesson are the family schemas `../data/*.schema.json` (the paragraphs «Data» of the chapters); the forms shared by
  a holder row and its copy at the agent — the common definitions (`common/data/common.schema.json` for reference; each
  family schema is self-contained).
- The acceptance of the chapters checks the norms: [9.1](../acceptance/1/README.md), [9.2](../acceptance/2/README.md). The stand of several
  clusters, the directives and the doors — [the common acceptance README](../../common/acceptance/domain-stand.md#domain-stand), the section «Domain stand».
  The vectors of the lesson — [`follow`](../vectors/follow/README.md) (9.1); the common ones — `agent-sig`,
  `peer` (9.1), `accept` (9.2). Flags,
  environment, exit codes — [`../lifecycle.md`](../lifecycle.md).
- The lecture (`ru/09-agent.md`, for people, not in the export) explains the mechanism and the examples.

The internal interfaces, types, error classes, libraries and the split into components are chosen by the implementation. The acceptance commands
`peer` and `follow` call the functions of the contract `peer` and of N3 of chapter 9.1 without a store and a network; the command `agent-sig` is shared with
chapter 8.3. Their names and call templates are the items «Implementation decides» of the chapters.

**On a discrepancy.** Name the norm id, the input, the initial state, the expected and the obtained outcome. First check which
chapter or lesson the rule belongs to: the agent of a member — chapter 9.1 and its contracts; the relay — chapter 9.2; the acceptance, the answer and
the envelope `m1` at the holder, the issue of a token, the term and the shared document at the holder — lesson P/08; the topology doors and the alarm list
— lesson P/10; `/api/held`, `/api/backup` and the book door of the cluster console — chapter 6.7; the contribution under a slot and the token check
by the recipient — P/03.7; the ports, the units and the box — P/02.4; the rights of the role `domainagent` — P/02.5. If the implementation is wrong —
fix it and repeat the relevant checks. If the norm, the contract or the expectation disagree — report to «Specification»
the place, a counterexample and the proposed solution; the solution is reflected in the norm, the contract, the instructions and the affected acceptance.
Do not carry a difference of the implementation silently into the canon; do not add a new mechanism only for the sake of an unsupported case.
Record a change of the acceptance in `corrections-<K>.tsv` (historical correction record) of the chapter.

## Glossary

These words of the norms have more than one meaning; each meaning points to the requirements that give it. The table adds no rules.

| Term | Meanings and the requirements that give them |
|---|---|
| `agent` | The process of the role `domainagent` on every server of the member cluster, the holder included (P/09.1-R071); the active agent — the one of them that holds the turn `domain/agent-turn` and carries the reports (P/09.1-R071); a waiting (standby) agent — one without the turn (P/09.1-R560, P/09.1-R564); the agent in a process — in the platform process of a cluster of one, without a turn and a guard (P/09.1-R014, P/09.1-R568); the relay's agent — the agent of the relay member that opens the relay door (P/09.2-R031, P/09.2-R035). |
| `member` | A cluster of the domain whose active agent carries the member reports to the holder (P/09.1-R071); the member key `domain/member-key` (P/09.1-R077); the row `domain/member`, by whose `pub` the console of the cluster checks its own agent (P/09.1-R106); the copy of the member list `domain/member-list/<part>` (P/09.1-R104). |
| `holder` | The process `domain` of the holder's cluster — lesson P/08 (P/09.1-R571); the holder's cluster, where the agent does not write the rows of the process `domain` while the record names this cluster the holder (P/09.1-R276, P/09.1-R465); the term record `domain/holder` that following writes (P/09.1-R044, P/09.1-R461); `holder` of the row `domain/agent-turn` — the instance of the active agent `<box>:<pid>:<6 hex>` (P/09.1-R548). |
| `turn`, `term` | The agent turn `domain/agent-turn` — which agent of the member cluster is active (P/09.1-R071, P/09.1-R548); the term — of a holder, in a term record: following takes the best record, the largest term (P/09.1-R461). |
| `copy` | A copy at the member of a holder's row «as is», in the form of its source row (P/09.1-R058–P/09.1-R066); the backup copy `domain/backup` (P/09.1-R064); the relay's own whole copy of each member, over which it accepts the member by the function «accept» (P/09.2-R111). |
| `record` | A term record: the answers `/api/held`, the record from 409 `deposed`, `carry.holder` (P/09.1-R011) and the record `domain/holder` of its own store (P/09.1-R465); `record` — the function of the term record contract that judges such a record and whose words are the words of the refusals (P/09.1-R461, P/09.1-R712). |
| `set`, `keys` | The domain key set of the foreign row `domain/keys` (its revocations — `domain/revoked`), taken by the function `keys` (P/09.1-R042, P/09.1-R227); the following set under `SET_GUARD` (P/09.1-R227, P/09.1-R461); `keys` of the relay batch answer — the accepted keys of the members of `relay_for` (P/09.2-R064); the agent holds no domain keys (P/09.1-R074). |
| `road` | The environment address of the report: `DOMAIN_URL` or `RELAY_URL`, a comma-separated list tried in order (P/09.1-R010, P/09.1-R425); the memory of the road — the destination member chosen last (P/09.1-R446); in chapter 9.2 the way of a member to the holder, whose `rev` the holder gives (P/09.2-R047, P/09.2-R057, P/09.2-R153). |
| `door` | The local token door `POST /tokens/<sub>/<kind>` on the role socket (P/09.1-R009, P/09.1-R573), in a process a call, not a door (P/09.1-R418, P/09.1-R522); the doors of the holder that the agent calls as a client (P/09.1-R575); the units door of its own console (P/09.1-R222); the relay door (P/09.2-R031, P/09.2-R099). |
| `pass` | The agent pass — once per `every`, only by the active agent (P/09.1-R019, P/09.1-R560); the relay pass — in every pass of the relay's agent, after its own report and even if that report did not pass (P/09.2-R008, P/09.2-R137). |
| `journal` | The agent's journal — the lines «agent: journal» of N4 and `domain.follow.refused`, appended to `audit/domainagent` (P/09.1-R057); the alarms `domain.term_diverged`, `domain.term_split` go to `audit.alarms/domainagent` (P/09.1-R644, P/09.1-R652). |
| `refusal`, `refused` | A row of the refusal catalogue `forms/refusals.tsv` (P/09.1-R026, P/09.2-R009); the rows `domain/backup-refused` and `domain/shared-refused` of the steps of N3 (P/09.1-R710, P/09.1-R711); `refused` of the holder's batch answer — what of `relayed` is not accepted (P/09.2-R060); `refused` of the output of `follow` — `{<cluster>: <record word>}` (P/09.1-R719). |
| `outcome` | The outcome of an edit in `domain/outcomes` — `performed`, `conflict`, `refused` (P/09.1-R377); the outcome of a family for an unreadable row (P/09.1-R050, P/09.1-R077); the outcomes of «accept» at the relay door (P/09.2-R103); the outcome of the function `keys` — took or holding (P/09.1-R106, P/09.1-R235). |
| `batch` | The relay batch — the body of `POST /api/relay/<relay>`, signed by the relay's agent (P/09.2-R005, P/09.2-R046); the batch of `join` in `domain/join`, always of the class camera (P/09.1-R092); a conditional store batch (P/09.1-R120, P/09.1-R227). |
| `standby` | A waiting agent without the turn (P/09.1-R560); the holder's answer `503 standby` — the holder is unavailable for this pass, the agent sends again at the next pass (P/09.1-R546); on a road `503 standby` — the next address (P/09.1-R425). |
| `object`, `row` | A P/05 object of the agent (`domain/reached`, `domain/reaches`, `domain/servers`, `domain/backup`, the object `domain/shared`, `domain/alarms`) (P/09.1-R557, P/09.1-R430, P/09.1-R435); a report object in the publication field `objects` (P/09.1-R004, P/09.1-R053, P/09.1-R055); a row `domain/*` of its own store, written with the guard (P/09.1-R554); `domain/shared` is both an object (the copy of the document) and a row (the pointer) (P/09.1-R040). |
| `envelope` | The ring envelope of a home secret (P/09.1-R047, P/09.1-R075); the envelope `x25519:v1` of a contribution to `book_seal` (P/09.1-R048); the envelope `m1` of the holder's answer, which the agent opens and the relay cannot open (P/09.1-R279, P/09.1-R422, P/09.2-R039). |
| `knock` | The fields `class` and `batch` of the publication until its own row confirms the admission (P/09.1-R097); the knocks of strangers at the relay door, carried in the batch (P/09.2-R048, P/09.2-R050). |
| `relay` | A member through whose agent other members report to the holder (P/09.2-R029); it is not the author of what is foreign (P/09.2-R039); between a member and the holder there is at most one relay (P/09.2-R042). |
| `cluster` | The member cluster, on every server of which an agent runs (P/09.1-R071); the holder's cluster (P/09.1-R276); a cluster of one, whose agent may run in the platform process (P/09.1-R014, P/09.1-R568). |

## What to create

- **9.1.** The agent (the role `domainagent`): the member key, the pass of N3, the publication of N1.2 whole or as a delta, the signature of N1.3,
  the application of the answer of N1.4. The command `join` on a member.
- **9.1.** The contributions in the report as objects, the slot liveness with a re-read, the secrets — `x25519:v1`, the same envelope for the same
  value; the row `domain/<sub>/<book>` at a member.
- **9.1.** The copies `domain/placed*`, the application of edits with `If-Match`, `domain/outcomes`; the holder — its own edits at itself.
- **9.1.** The local door `/tokens/<sub>/<kind>` with the identity of the role ([the local token door
  contract](../../common/contracts/local-token-door.md#the-role-socket): the role socket); the request to the holder; opening `m1`, the check of
  `request_id`, `exp`.
- **9.1.** `RELAY_URL` for a member behind a relay; `domain/reached`, `domain/reaches`; the HTTPS client by the contract `peer`.
- **9.1.** Following by `/api/held` and 409 `deposed`, the check `record`; keeping the backup copy (`domain/backup`,
  `domain/backup-taken`), its object in the report.
- **9.1.** The acceptance of the document by N3 «take the document», the refusal, the rows in the report; the alarm front once a second, the page and
  the urgent report.
- **9.1.** `members_rev` and `sign_failures` in the publication; the home row — only on a difference; the row `domain/agent`; a delta
  always with `base > 0`, do not send a whole larger than the limit; 503 `standby` — the next pass. A cluster of one: the agent in the
  process without the kit of the role — the client only to the doors of the holder and of the relay; the local door is a call (the local token
  door contract, «The call in the process»).
- **9.2.** At the agent: the relay door (`RELAY=1`) with `POST /api/member/<member>`, `GET /api/carry/<member>`,
  `POST /api/tokens/<member>/<sub>/<kind>` (byte for byte, 502 `did not answer`); the relay pass of N3. The HTTP form —
  [the OpenAPI of the lesson](09-agent.api.openapi.yaml), the tag `relay`.
- The commands of the vectors `peer`, `follow` (`agent-sig` — chapter 8.3) and the description of all the choices of the sections «Implementation decides» of the chapters —
  11 items «Implementation decides» in all — and the means of running the acceptance: the commands of the vectors and the stand directives.

## Order of work

This is a proposed order, not a mandatory structure of the code. Chapter 9.1 first: the relay is the same process and
relies on the agent pass.

### Chapter 9.1 — the agent of a member

1. The agent signature — [the agent signature contract](../../common/contracts/agent-signature.md) and the package `agent-sig`; the function
   `peer` — the package `peer`; the function `follow` — the package `follow`.
2. The agent pass of N3: `ready`, a whole after the start and after `rebase`, a delta without `ts`, `every` from the answer.
3. The home record only on a difference (N1.4); the freshness marks.
4. The contribution in the report and the envelope of a secret: AAD — the member, the row key, item, JSON Pointer; the book row at a member, the secrets — by the ring
   ([P/06.2](../../06-console/spec/06.2-console.norms.md) N1.2), a write only on a change.
5. The copies of placements at a member (sc. 01 of the acceptance of chapter 8.6); the application of edits
   by the agent and the outcomes (sc. 03 of the acceptance of chapter 8.6, sc. 04, 07, 08 of chapter 9.1); `If-Match` — [P/06.1](../../06-console/spec/06.1-console.norms.md),
   sc. 14 of the acceptance of P/06.1.
6. The local door; the envelope `m1` ([the domain envelopes contract](../../common/contracts/domain-envelopes.md), P/08.3 N1.5).
7. A member behind a relay: `domain_age` → `domain/reached`.
8. Following; the keeper's agent.
9. The acceptance of the shared document; the alarm page and the front.
10. The ceilings of the agent: `domain/agent`, `sign_failures`, `too_large`; the agent in the process.
11. The stand: the scenarios of [the acceptance of the chapter](../acceptance/1/README.md) and the agent side in the scenarios of the chapters of lesson P/08
    («Neighbours on the stand» of N5 of the chapter).

### Chapter 9.2 — the relay mode

1. The door and the relay pass of N3: its own copy and `rev` of each member (the function «accept» over its own memory — [the report
   acceptance contract](../../common/contracts/accept.md), the vectors `accept` ), the deltas
   against the confirmed base, the packages, the return of the untaken publications into the memory (step 5).
2. The check of the member signature at the door — [the agent signature contract](../../common/contracts/agent-signature.md), the key — from `keys`
   of the package answer; the vectors `agent-sig`.
3. `domain_age` in the answer to the member (N1.4).
4. The server side of the door — [the role certificate contract](../../common/contracts/role-certificate.md#the-server-side-the-class-signed).
5. The stand: the scenarios of [the acceptance of the chapter](../acceptance/2/README.md).

### The whole lesson

Run the vectors and the acceptance scenarios separately, with the preparation that the acceptance README of the chapter names: the lesson has
27 scenarios / 314 stand steps in all — chapter 9.1 (`acceptance/1/`: 01, 03–08, 11, 13–25, 27), chapter 9.2 (`acceptance/2/`:
02–06). Fill the checklists of the chapters with the evidence from N5 of the chapters.

## Pitfalls of the language and the library

| Norm | Possible error | How to keep the behaviour |
|---|---|---|
| 9.1 N1.1 | pin the root by the first set from an answer | only `join` pins the root; without it `keys` → `no_pin` |
| 9.1 N1.2 | count as changed a pulse whose only change is `ts` | the JCS comparison without `ts`; only `ts` — not a change |
| 9.1 N3 | send a new generation by a timer | only on a change; the loss of the holder memory — through 409 `rebase` |
| 9.1 N1.2 | a new envelope of a secret in every pass | the same envelope for the same value — otherwise a generation every 5 s |
| 9.1 N1.2 | the ring envelope at a member did not open — skip the row or crash | the agent carries the value as it is; the assembly — `secret_unopened` |
| 9.1 N1.4 `member_row` | a book secret in the journal | the secrets — as envelopes of the ring |
| 9.1 N1.5 | write a copy with a smaller `rev` | only a `rev` larger than its own; the copies outside the answer — delete |
| 9.1 N1.5 | count 412 as a failure and retry | 412 — the outcome `conflict`, the edit is withdrawn |
| 9.1 N1.6 | take the role from the request body | the role is the identity of the connection; only the agent writes the field `role` to the holder |
| 9.1 N1.7 | decide the road of the agent by the topology | the road is the environment (`DOMAIN_URL`/`RELAY_URL`); the topology — whom to accept |
| 9.1 N3 «follow» | follow a record from a neighbour's answer without a check | only after `record` by its own set; otherwise — the journal, do not follow |
| 9.1 N3 «follow» | move to a smaller term when the old holder came back | never go back: keep its own larger term |
| 9.1 N1.10 | take a document with a smaller `(term, rev)` after the holder is restored | never back: compare before loading |
| 9.1 N1.10 | check the signature by the set that came together with the document | only by its own set (`record`) |
| 9.1 N1.10 | assemble the alarm page every second | once a second — only the front (one index row); the page — on a new alarm |
| 9.1 N1.2 `members_rev` | take the absence of `members` in the answer as «the list is empty» and erase the copy | no field — «no change» |
| 9.1 N1.4 | write the home row on every answer «just in case» | compare with what was read; equal — do not write |
| 9.1 N1.11 | allow a process without a kit any `https://` | only the agent client to the doors of the holder and of the relay, with a server check |
| 9.1 N1.12 | stop the agent when the member key is not readable | the agent goes on and counts; the holder will see `silent`, the member — the row `domain/agent` |
| 9.1 N1.12 | count 503 `standby` as a refusal and look for another term | the holder is unavailable for this pass; the next pass — again |
| 9.2 N3 | stop relaying when its own report did not pass | the relay pass always runs |
| 9.2 N3 | lose a member publication when the holder did not answer | return it into the memory if nothing newer came |

## Boundary checks

### The agent writes only at its own member

The rows and objects of chapter 9.1 are written only by the agent of its own cluster (the paragraph «Data» of [chapter 9.1](09.1-agent.norms.md)); the holder
rows are written by the process `domain` (lesson P/08). In foreign rows — `domain/keys`, `domain/revoked`,
`domain/break-glass/<member>`, `domain/holder`, the row `domain/shared` — the agent is a participant, and at the holder cluster it writes none
of them while that cluster holds the term (N1.4 `holder_cluster`). The relay mode has no rows of its own: the memory is in the process.

### What the agent does not do for its neighbours

The agent does not issue a token and does not decide its claims — that is the holder (chapter 8.7); it does not check a token at the recipient and does not
write a contribution — that is the worker (P/03.7); it does not assemble a book — the holder (chapter 8.5); it does not choose the road by the topology.
The relay is not the author of what is foreign and does not open an envelope `m1` sealed to a member.

### Vectors and the stand

The vectors check the pure functions and nothing more: TLS between clusters, the agent in the process, the alarm front and the member signature
through a relay they do not prove. The stand without TLS does not check the server side of the relay door; there is no row of it in
the TLS stand either ([`common/acceptance/tls/`](../../common/acceptance/tls/README.md)).

## Done when

All the choices of the implementation are described (the items «Implementation decides» of both chapters), all the norms of the checklists of the chapters are fulfilled and
the ways of checking are recorded: for each id — a specific piece of evidence or an unchecked dependency. State the slice,
the commands and the stand, the observations and the limitations. The data of past runs do not replace the preparation of a new one.

- **9.1.** The acceptance scenarios of the chapter (`acceptance/1/`: 01, 03–08, 11, 13–25, 27) pass; the packages `agent-sig`, `peer`,
  `follow` give their rows; the agent side in the scenarios of chapters 8.3–8.10 and 9.2 («Neighbours on the stand» of N5) — too. The description of the
  implementation names items 1–10 «Implementation decides» of the chapter: the commands `peer`, `follow`; `join` and the launch of the agent;
  `W2C_WALL_OFFSET`; the networks `domain/reaches`; the envelope memory; the holder's edits at itself; the assembly of the alarm page; the TLS client;
  the components of the process of a cluster of one; the writes to the medium per day. The checklist P/09.1-01…36 is closed; the items
  «checked by reading» are named separately.
- **9.2.** The acceptance scenarios of the chapter 02–06 pass. The description of the implementation names the relay door and the memory
  («Implementation decides» of the chapter, item 1). The checklist P/09.2-01…09 is closed; the items «checked by reading» (P/09.2-04, -05, -07;
  the memory after a restart) are named separately.

The success of a TSV confirms only the branches it observes. It does not prove TLS between clusters, the agent in the process, a race of
the alarm front and the member signature through a relay: for them reading by N5 of the chapters or a separate stand is needed. A check of the
documents and of the OpenAPI does not run the implementation.

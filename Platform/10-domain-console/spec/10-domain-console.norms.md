# P/10 — The domain console: norms

This English text is the source; the Russian translation `ru/spec/10-domain-console.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of lesson P/10 «Консоль домена» (ADR-0080; module «Платформа» — ADR-0083). Lecture (`ru/10-domain-console.md`, for people, not in the export),
[contract](10-domain-console.api.openapi.yaml), [instructions](10-domain-console.README.md), [life
cycle](../lifecycle.md), [acceptance](../acceptance/README.md). Here is the process `domainconsole` on the holder's box: the door
of the domain operator. The cluster console of the holder forwards `/domain/*` here (transition 2 of [the forwarding
contract](../../common/contracts/forwarding.md); the consoles of members — through it, transition 1); the domain console itself answers the read doors (the view, the shadow report, the members,
the topology, the placements, the grants, the shared document, the alarm list and the function `alarms`), passes on to the process `domain` the edits,
the people doors and the login, serves the holder's page and passes the routes `door.pass` to the worker on the domain; at the entrance it holds the role door
of TLS (`server.role`), «принять консолью» and the gate by `domain/grants/domain`. The process writes no rows of its own.

The lesson is moved (stage B, ADR-0083 addendum (1): without a change of behaviour) from the lessons М11 — by doors and parts of norms (the move plan
of lesson 10, § 2):
- М11/1 — Н2 and the Н4 rows of the view doors (here Н1.2а);
- М11/3 — Н1.8 `console` and the console side of the line `pass` (here
  Н1.3), the Н2 row `GET /domain/members` (Н1.2б);
- М11/4 — the Н2 row `GET /domain/topology` (Н1.2в); М11/6 — the Н2 rows `GET /domain/placement`,
  `/domain/placement/<sub>/<ref>` (Н1.2г) (the lessons are removed by commit 9; the former text is in Git);
- М11/8 — Н1.6 `roles` and `server.role` (here Н1.4), Н1.7
  (Н1.6), Н1.8 (Н1.7), the domain console side of Н3 «принять консолью» (Н1.4; the text is the forwarding contract), the Н2 and Н4 rows
  of the domain console, sc. 05 of acceptance;
- М11/9 — Н1.5 `body_unit`, `session` at the domain console
  (Н1.5), Н1.9 `pass` (Н1.3а), the Н2 row `GET /domain/grants` (Н1.2д);
- М11/11 — Н1.6 `door` (Н1.2е), Н1.8 in full (Н1.8),
  Н3 `alarms`, the Н2 and Н4 rows of the domain console, Н5 `alarms` and `exit` in the part of `alarms`, sc. 02 and 04 (the vector `alarms`),
  «Implementation decides» item 1 in the part of `alarms`;
- М11/12 Н1.8 — the domain console side at start (the text is [P/02.4 Н1.12](../../02-installer/spec/02.4-installer.norms.md);
  here Н1.1).

What is not here and where it is: the content of the view and of the shadow report — [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md); the execution
of edits, the check of the identity and the grant at the process and the answers `deposed`, `frozen`, `standby` — the chapters of lesson
[P/08](../../08-domain/spec/08.0-domain.norms.md) by door (transition 3); the forwarding of the cluster console, its refusals, the doors that
the cluster console answers itself (`/domain/move`, `/api/held`, `/api/backup`, `/api/prepare`, `/api/take`, `/domain/keys`, books,
`at`, `/domain/shared/<sub>`), — chapter P/06.7 of the late layer and [the forwarding contract](../../common/contracts/forwarding.md); the gate
and the passing of `door.pass` as a whole — [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) (owner P/06; this lesson is a
participant); the alarm history — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) Н1.9.

The numbers of the subsections are new (the place of the source is in the brackets of the heading). A reference «P/0N[.K]» is a lesson or a chapter of the module; «chapter
8.K», «chapter 9.K» are the chapters of lessons P/08, P/09; «М11/N» is the lesson М11 (the history of the move). Norm ids are `P/10-MM`; the map to
former ids is [`id-map.tsv`](../../common/id-map.tsv).

## Н0 Vocabulary

Normative keywords follow the [course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md). The rules of the module are [P/01.1 Н0](../../01-store/spec/01.1-store.norms.md#н0-vocabulary)
(including the order of output arrays, scope — lessons 8–10).

## Н1 Form

**Time.** The lesson writes no rows and objects with time; a line of the role journal has `t` by [the event
journal contract](../../common/contracts/event-journal.md). `age` of the answer of `GET /domain` is seconds by the wall clock of the console, not a time in
a row (Н1.2а); the time of the rows of the alarm list is the domain clock (Н1.8 `clock`); the history object — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md)
Н1 «Time», the member's alarm page — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) Н1 «Time».

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/<manifest:domain.witness.report>/<имя>`;
- writes: `<корень событий>/audit/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<корень событий>/audit.alarms/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append);
- reads: `domain/relay-members/<ретранслятор>`, `domain/<sub>/<manifest:domain.kept>`, `domain/folder-units/<id>`, `domain/folder-units/<id>/<раздел>`, `domain/folder-counts/<id>`, `domain/view-rows/<раздел>`, `domain/anywhere`, `domain/folders/<id>`, `domain/memberof/<член>/<sub>/<manifest:unit.rows>/<id>`, `domain/members/<член>/tables/<sub>/<таблица>`, `domain/roles/<имя>`, `domain/groups/<имя>`, `platform/manifest/<sub>`, `platform/manifest/<sub>/rev` (the mark: a manifest change — P/02.3 Н3; В7 item 3, the Architect's decision of 2026-10-28, П3; line 19 of the list), `platform/schema`, `/etc/w2c/tls/<роль>/server.key`, `domain/view`, `domain/shadow`, `domain/holder`, `domain/keys`, `domain/root`, `domain/revoked`, `domain/member-rows/<раздел>`, `domain/members/<член>/ca-certs`, `domain/members/<член>/reports/<rev>`, `domain/members/<член>/reported`, `domain/topology`, `domain/<sub>/worker`, `domain/<sub>/heartbeat`, `domain/placement`, `domain/placement/<sub>/<ref>`, `domain/disabled`, `domain/grants/<кластер>`, `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/alarm-history/<член>`.

The domain console writes no rows of the holder: it passes the edits on to the process `domain` (Н1.3; the reception — [P/08.0](../../08-domain/spec/08.0-domain.norms.md)
Н1.8), the rights of `domainconsole` are reading `domain/*` ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) Н1.4). The family
of witness objects `<sub>/<manifest:domain.witness.report>/<имя>` belongs to this lesson by protocol (Н1.8 `witness`; the decision of
the Architect on the move plans of 8–10, item 8): the worker of the subsystem (a participant) writes it, the agent carries it in the report; the domain console
reads witnesses only from the reports of members (`domain/members/<член>/reports/<rev>`; the holder is a member too, with its own agent),
the family has no schema in `data/` (the form is the declaration `domain.witness` of the manifest, [P/02.1 Н1.2б](../../02-installer/spec/02.1-installer.norms.md)).

What each door reads: the view, the shadow report, the list of members, the topology, the placements, the grants, the shared document — the read doors
Н1.2 (the forms of the rows are in their chapters of lesson P/08); `domain/keys`, `domain/root`, `domain/revoked`, `domain/disabled`,
`domain/grants/<кластер>`, `domain/roles/<имя>`, `domain/groups/<имя>` — the gate (Н1.5; the keys and the token — [the domain token contract](../../common/contracts/domain-token.md),
`may` — [the right contract](../../common/contracts/may.md)); `domain/member-rows/<раздел>` and the rows
`domain/members/<член>/ca-certs` — the role door (Н1.4 `server.role`; the domain console does not read the copy `domain/member-list/<раздел>` — review analysis of stage B 8–10, question 4); `domain/<sub>/worker` and the heartbeat `domain/<sub>/heartbeat` —
`door.pass` on the domain (Н1.6); the member's report, the mark `reported` (`received_at`, `sent_at`), the history and `domain/member-rows/<раздел>` — the alarm
list (Н1.8); the manifest rows and `platform/schema` — the start (Н1.1); the key of the server certificate of the role `domainconsole` — the role door
of TLS. The role journal is `audit/domainconsole`, the alarm `session.debug_open` (a debug identity, Н1.5) — `audit.alarms/domainconsole`
([the event journal contract](../../common/contracts/event-journal.md), participant `append`, owner — P/05). The lines «журнал»
of the role door — the transition of the trust set into unreadable and back (the role certificate contract, class `role`, `unreadable`;
C10-ROLE-LOG-C47) and a service without a kit (`no_kit`) — are a diagnostic of the process (stderr), not events of `audit/domainconsole`:
there are no kinds for them and new ones are not introduced, the text is the implementation's, acceptance does not compare it (C10-ROLE-LOG-DIAG-01).

### Н1.1 The process and the start (М11/12 Н1.8; P/02.4 Н1.12)

The domain console is the process `domainconsole` at the holder cluster, next to the process `domain`: the unit
`w2c-domainconsole.service`, the role `domainconsole`, the port `DOMAIN_CONSOLE_HOST/PORT` 0.0.0.0:8444 — only with a role kit, TLS — by the kit (ADR-0075 addendum of 2026-10-26 (2) item 4; [P/02.4 Н1.12](../../02-installer/spec/02.4-installer.norms.md)).
Like the processes of the platform, it executes the reader's side of the manifest row ([P/02.3](../../02-installer/spec/02.3-installer.norms.md)
Н3 «Process start», «Manifest change»): it has no built-in manifest, steps 0–4 of «Process start» are as there: step 0 is
the schema check against `SCHEMA` of the platform build ([the schema contract](../../common/contracts/schema.md) «Check at start»);
step 1 — the whole catalogue; step 2 — only `sha256` of the row (there are no built-in bytes to compare with); then the environment, the kit
of TLS, the port (the Architect's decision of 2026-10-25, C10-START83); readiness is the port, it does not send `sd_notify` (the text is P/02.4 Н1.12, from М11/12 Н1.8; here it is
the domain console part, P/10-15). The environment, the exit codes and the unit are in the [life cycle](../lifecycle.md).

### Н1.2 The read doors — it answers itself

The parsing of a request is [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Request parsing and the order of checks»
(P/01.1 Н2.1 with the deviations of the console; the layout audit Б-09); there are no deviations of its own. The identity and the grants are Н1.5 (`view` for reading by `domain/grants/domain`; the view doors — «Judgement by target» of [the right contract](../../common/contracts/may.md)). Each
door is a row of the list of domain doors of [the forwarding contract](../../common/contracts/forwarding.md) «Domain doors»; a row with `GET`
also covers `HEAD` of the same path — the same code and headers without a body (ibid.; P/06.5 Н2).

**The row version at the read doors** ([P/08.0](../../08-domain/spec/08.0-domain.norms.md) Н1.9 «Versions»; ADR-0094 B4). The doors of one row — `GET /domain/members/<член>`, `GET /domain/topology`, `GET /domain/placement/<sub>/<ref>`, `GET /domain/shared` — serve an `ETag`: the index of this row (for the shared document — of the pointer) in double quotes, from the same read as the value. There is no row — the answer is without `ETag`: the condition has nothing to judge about.
`GET /domain/placement` carries `index` in each record, `GET /domain/grants` — the field `versions`: the index and `revision` stand by the row, because the answer has many rows. The values are fit for `If-Match` of the edit doors that the console passes on to the process (Н1.3).

**Н1.2а The view (М11/1 Н2, Н4).** The doors are at the domain console; the cluster console forwards them without rewriting:

| Door | Success | Refusals |
|---|---|---|
| GET `/domain[?cursor=]` | the answer is the head of `domain/view` and the non-empty parts in a row up to 1000 members, the fields `members`, `units`, `contested`, `reports`, `pending`, `outcomes` — a merge of the rows, `cursor` — the next page, `unread` — the unread parts; a small domain — one page (P/08.1 Н1.4б); for a non-viewer of the domain (the right contract `wide`) — only `as_of`, `holder`, `complete`, `members` (`servers` and `url` — only for the clusters where it has a row), `units` by record, `outcomes` — the outcomes where `by` is itself, `contested` — the refs whose cluster it sees, `age`, `url`, `withheld: <число>`; otherwise 200 — the object `domain/view` ([P/08.1](../../08-domain/spec/08.1-domain.norms.md) Н1.4) as is plus `age` — seconds since `as_of` by the wall clock of the console, `max(0, now − as_of)` (a clock gone back — 0; C10-AGE-NONNEG-01), one digit after the point; the field `url` of the view that does not read (not a string) is `null` in the answer (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 53 of the list) | 404 `{error: "no domain here", detail}` — there is no object; the object exists but does not read — 503 `{error: "unavailable"}`, not 404 (В7 item 3, the Architect's decision of 2026-10-28, П1; line 54 of the list); 401/403 — Н1.5 |
| GET `/domain/<sub>/<rows>[?cluster=<член>][&cursor=]`, `/domain/<sub>/<rows>?part=<раздел>` | 200 — `[Unit]` of the subsystem from the rows of the view, page by page by the header `X-Cursor`, with `cluster` — this member’s entire row in its one part, one page: `cursor` is not read, including an invalid opaque cursor, and there is no `X-Cursor`; with `part` — the units of one row `domain/view-rows/<раздел>`, one read and one page, `cursor` is not read, there is no `X-Cursor`, no row — `[]` (the part — P/08.3 Н1.1; ADR-0113 addendum (22)); for a non-viewer of the domain — only the records it sees, `X-Withheld: <число>`, if some are hidden because of the unread (`unavailable`) | in order: 400 — `cluster` or `part` twice or empty ([P/06.5](../../06-console/spec/06.5-console.norms.md) Н2), `part` not by the grammar of a part, `cluster` and `part` together; 404 — there is no such manifest; 404 `{error: "not in the directory"}` — the manifest has no `domain.ref`; 404 — `rows` is not its own; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read (В7 item 3, the Architect's decision of 2026-10-28, П1; line 54 of the list); 404 `{error: "no such member"}` — the member is not in the list; other parameters are not read |
| GET `/domain/<sub>/kept/<имя>` | 200 `{items, index}` of the row `domain/<sub>/<имя>`, `<имя>` — an element of `domain.kept_read` of the manifest; the mask of [P/06.2](../../06-console/spec/06.2-console.norms.md) Н1.4: an element with the name `*_secret` and a field `*_secret` at any depth of the value parsed as JSON, an envelope `enc:` — `"***"`, a value that is not JSON — as is; the domain console answers itself; the right is `view` of the domain (`wide`), judged first: a non-viewer does not tell «not declared» from «not allowed» | 401, 403 — before everything; 404 `<имя>` is not declared or there is no row; 503 `{error: "unavailable"}` — does not read |
| GET `/domain/relays/<ретранслятор>` | 200 `{relay, rev, members}` of the row `domain/relay-members/<ретранслятор>` (P/08.3 Н1.2): `members` — names in ascending order, up to 5000, the member keys do not go; there is no row — `rev` 0, `members: []`; the domain console answers itself; the right is `view` of the domain (`wide`), judged first | 401, 403 — before everything; 404 there is no such member; 503 `{error: "unavailable"}` — does not read |
| GET `/domain/<sub>/tables/<таблица>?cluster=<член>` | 200 — `{cluster, ts, rows}`, the object P/08.1 Н1.4а of this member as is, for a non-viewer of the domain — only the visible rows and `X-Withheld`; `ETag` — sha256 of the served body, separate for each answer, `If-None-Match` — 304: reading the list of members is cheap; one member per request: the object is bounded by P/04 Н1.3б, there is no list of all (ADR-0110) | in order: 400 — `cluster` is absent, twice or empty; 404 — there is no such manifest; 404 — `<таблица>` is not a key of `domain.view_tables`; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read; 404 `{error: "no such member"}` — the member is not in the list; 404 `{error: "not reported yet"}` — there is no object; 503 `{error: "unavailable"}` — the object does not read; other parameters are not read |
| GET `/domain/shadow` | 200 — the shadow report (P/08.1 Н1.6) of the last pass | 404 `{error: "no domain here"}` — there is no report; the report exists but does not read — 503 `{error: "unavailable"}` (В7 item 3, the Architect's decision of 2026-10-28, П1; line 54 of the list) |

**Pagination of `GET /domain` (G10-PAGE-CURSOR-01).** The limit is hard: at most 1000 elements of `members` per page. A part is the writer's storage/work unit, not an indivisible HTTP page; a readable part with more than 1000 members is split at a member boundary. Visit the non-empty parts in ascending order of their four-digit names (0000…4095), and the members inside each part by name in UTF-8 byte order. Select up to the remaining page budget, then continue inside this part on the next request if needed. Each returned page's `members` is itself ordered by name; its last displayed element need not identify the last visited part.

The request without cursor starts the traversal. The returned cursor is an opaque string carrying sufficient continuation state, such as the current part and last visited member. Its encoding is the implementation's; clients return the issued token unchanged as the query value. The cursor continues after the selected members, including within a part, and is omitted at the end. On unchanged readable data, following all pages returns every member exactly once, without a skip or a repeat. The API promises ordinary reads, not a new snapshot spanning concurrent changes.

The page projects the six per-member fields: `members` contains the selected members; `units` keeps Unit records whose cluster is selected; `reports`, `pending` and `outcomes` keep selected member keys. Preserve the view's required empty subsystem keys. A contested ref is a complete conflict fact: keep a ref that has a selected claimant, with its entire original claimant list, never truncate that list at the page boundary. Names used as this context are not additional MemberState elements of the page. A conflict can therefore appear on more than one page, while the members themselves do not repeat. The head's global fields stay global. Existing visibility filtering and the unread/incomplete rules still apply; pagination alone does not change the holder's round completeness.

Examples on fixed data: one part with 1001 members gives pages of 1000 and 1; consecutive parts with 999 and 2 give pages of 1000 and 1, continuing inside the second part. A conflict between members on opposite sides of that boundary keeps both claimant names wherever that conflict is included. No part-size bound is added to P/08.1 Н1.4б.

**Н1.2б Members (М11/3 Н2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/members/<член>` | the domain console (`domainconsole`) | 200 `{part, rev, term, entry}` of the row of the part of this name and `ETag`: the version for `If-Match` of the edit doors | 404 not a member; 503 does not read |
| POST, GET `/domain/batches`, DELETE `/domain/batches/<имя>` | the domain console → the process `domain` ([chapter 8.0](../../08-domain/spec/08.0-domain.norms.md)) | [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) Н1.1б: POST — 200 `{name, token, pub, n, until}`, the token is shown once; GET — the batches without the token; DELETE — 200 | 400 not by the form; 404 there is no batch; 409 such a batch exists; Н1.9 — the right `admin` of the domain |
| GET `/domain/members[?cursor=]` | the domain console (`domainconsole`) | 200 `{members, parts, knocking, count, cursor?}`: the non-empty parts in a row, up to 1000 members, a small domain — one page; `parts` — `{<раздел>: {rev, term, index}}`; `index` is the exact nonempty string Row.index of the store row read, never a JSON number or a binary64 conversion ([P/01.1](../../01-store/spec/01.1-store.norms.md) Н1 Version); `members` — a merge of the doc of the rows read by the door; `count` — `domain/member-count`, absent — no field; `knocking` — on the first page `view.knocking`, on each — `domain/knocks/<раздел>` of the parts of the page (the memory knock exists only in the view, [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md) Н1.7), the field is absent in a readable view — `[]` (the field is optional, nobody is knocking; like a view without `shared`, C10-MEMBERS-KNOCKING-ABSENT-01); `member_list` of the view is not substituted (C10-MEMBERS-SOURCE-01) | 404 `no domain here` (there is no view; there is no row `domain/member-rows/<раздел>` with a readable view — the list exists from the first start of the holder, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н3 «the holder in the list», C10-MEMBERS-SOURCE-01); the row `domain/member-rows/<раздел>` or the view exists but does not read — 503 `{error: "unavailable"}` (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 36 of the list); 401/403 — Н1.5 |

The grant `admin` for editing the list and `view` for reading are Н1.5; the console passes the edits of the list on to the process (Н1.3; their norms are
[chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) Н2).

**Н1.2в Topology (М11/4 Н2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/topology` | the domain console | 200 doc ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н1.2) — from the row `domain/topology`, not from the view: right after a PUT — the new `rev` (reconciliation of М11, T1) | 404 `no domain here` — the view is not built (Н4); there is no row `domain/topology` — not a refusal: 200 `{rev: 0, star: [], via: {}}` (P/08.3 Н1.2: rev 0 — «never written», no row — the same; C10-TOPOLOGY-ABSENT-01); the row `domain/topology` exists but does not read — 503 `{error: "unavailable"}` (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 50 of the list); 401/403 — Н1.5 |

**Н1.2г Placements (М11/6 Н2).** The doors are the domain console's; the member console forwards them (the forwarding contract «Двери домена»):

| Door | Success | Refusals |
|---|---|---|
| GET `/domain/placement` | 200 `{rev, records: {"<sub>/<ref>": Placement с index}}`; there is no row `domain/placement` — `rev` 0 (there is no counter yet, [P/08.6](../../08-domain/spec/08.6-domain.norms.md) Н1.2 `absent`), `records` — as always (C10-PLACEMENT-ABSENT-01) | the row `domain/placement` (the counter `rev`) exists but does not read — 503 `{error: "unavailable"}` (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 43 of the list); 401/403 — Н1.5 |
| GET `/domain/placement/<sub>/<ref>` | 200 Placement | 404 there is no record; the record exists but does not read — 503 `{error: "unavailable"}`, not 404 (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 42 of the list); 404 there is no manifest or it is without `domain.ref` |

The form `Placement` and the counter are [chapter 8.6](../../08-domain/spec/08.6-domain.norms.md) Н1.1; the console passes the edits of placements
on to the process (Н1.3).

**Н1.2д Grants (М11/9 Н2).**

| Door | Who | Right | Success | Refusals |
|---|---|---|---|---|
| GET `/domain/grants` | the domain console | view; to a non-viewer of the domain — only the clusters where it has `admin` on `*` (the right contract `target`, ADR-0110 Д-1), none — 403 | 200 `{grants: {<кластер>: [line…]}, versions: {<кластер>: {revision, index}}}` | 401/403 |

The grant line `line` is [chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) Н1.3; the console passes the edit `PUT /domain/grants/<кластер>`
on to the process (Н1.3).

**Н1.2е The shared document (М11/11 Н1.6 `door`).**

```yaml
door:          GET /domain/shared at the domain console (view) → 200 {doc, delivery, declared}; there is no view (domain/view) — 404
               {error: "no domain here"}, like the other read doors without a view (Н1.2а); the view exists but does not read — 503
               {error: "unavailable"} (П1; line 54 of the list; C10-SHARED-NOVIEW-01); the pointer domain/shared or its document
               exists but does not read (not by the form, not with the sha256 of the pointer) — 503 {error: "unavailable"}, not doc: null (the outcomes
               of the families shared, shared-docs)
  doc:         the document as signed (an object) | null
  delivery:    view.shared — an x-opaque field: the console does not judge the form of the delivery (the form is the writer's, the process domain, P/08.9
               Н1.6), it serves a non-empty object as is, by value (C10-SHARED-OPAQUE-COPY-01); no field or {} — 200,
               delivery = before (P/08.9 Н1.6) by the view: term 0, rev 0, holding [], behind {}, refused {}, silent — the members
               of the view not ok, sentence «rev 0 on 0 of T members» (T — the members of the view) with the tails of before; null in term and rev is not
               written (C10-SHARED-EMPTY-DELIVERY-01)
  declared:    {<sub>: [{name, type, schema?}]} — the elements domain.shared of the manifests of the catalogue, by name; schema — at the document
               (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10a, added by М11/11; the late layer P/07 Н1.6)
```

The document and the pointer are [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) Н1.2; `view.shared` is chapter 8.9 Н1.6; the declaration
`domain.shared` is [P/02.1 Н1.2б](../../02-installer/spec/02.1-installer.norms.md). The console passes the edit `PUT /domain/shared` on
to the process (Н1.3; the execution — chapter 8.9 Н1.3).

### Н1.3 Passing on to the process `domain` (М11/3 Н1.8 `console`, `pass`; М11/9 Н1.9 `pass`)

The reception of the passing, `writer` and `answers` are [P/08.0 Н1.8](../../08-domain/spec/08.0-domain.norms.md) (P/08.0-01); here is the side
of the domain console.

```yaml
console:   the domain console is a door: it checks the identity and the grant (the gate, Н1.5) and passes the edit on; it has no records of its own in
           the rows of the holder (the rights of domainconsole are reading, P/02.5 Н1.4)
pass:      every door /domain/* of the domain console, except GET and HEAD and except door.pass to the worker on the domain (Н1.6), and
           POST /api/login (P/08.4 Н1.2); the people doors of P/08.4 Н1.9 (/domain/users…, /domain/break-glass…) — with any
           method, GET too (review analysis of stage A 8–10, № 2) —
           to the process domain (SIGNER_URL of its own box; to https:// — the client of its own cluster, the role certificate contract
           own_client, role domain): the method, the path with query, the body, Authorization, Idempotency-Key, If-Match
           as they came, except the first cookie transition under the forwarding contract «First cookie transition to the domain»; X-W2C-Client — the address of the client's TCP peer: the domain console sets it; when, whom the process trusts and what
           is stripped outside — the forwarding contract Platform/common/contracts/forwarding.md «Client address» (review analysis
           of stage A 8–10, № 23; the history is there too: reconciliation of М11, cammeta-python М11-09 № 22, P16); the deadline is «Ожидание» of the row
           of the forwarding contract Platform/common/contracts/forwarding.md «Domain doors»; the answer is as it came, without parsing
           (the forwarding contract «Forwarding is one function» answer: 502 on a break and on silence); the process checks
           the identity and the grant itself (P/08.4 Н1.5) and executes Н3 of the door
```

The doors that the console
passes on are the rows of the list of domain doors of the forwarding contract «Domain doors», except its own read doors (Н1.2), the alarm list
(Н1.8) and `door.pass` (Н1.6); their norms and answers are the chapters of lesson P/08 by door ([P/08.0](../../08-domain/spec/08.0-domain.norms.md)
Н2, the summary table). The console serves the answer of the process as it came — `409 deposed`, `503 frozen`, `503 standby` too: it does not
recompute them (P/08.0 Н1.8 `answers`; the forwarding contract «Refusals by transition», transition 3).

### Н1.3а People doors (М11/9 Н1.9 `pass`)

The lines `first`, `member` are [P/08.4 Н1.9](../../08-domain/spec/08.4-domain.norms.md) (P/08.4-07); here is the passing.

```yaml
pass:      the doors /domain/users…, /domain/groups…, /domain/roles…, /domain/batch and /domain/break-glass… with any method, GET too (review analysis of stage A 8–10, № 2), the edits
           /domain/grants/… and /domain/revoke the domain console passes on to the process domain by Н1.3; the process checks
           the token and domain/grants/domain itself (ADR-0032)
```

**The path of `backend` to the domain doors** (ADR-0098 §6, ADR-0094 addendum (11), (12) item 9). The request comes by forwarding from the cluster console ([P/06.3](../../06-console/spec/06.3-console.norms.md) Н1.9 «Domain doors»): the original token of the human; the bytes of the ticket do not reach here. Further on the path does not differ from a request
of the page: the process judges the right of the human by P/08.4 Н1.5, `by` is the name of the human. Records one by one from `backend` do not go. The sign of the path is the closed header `X-W2C-Via-Worker: <sub>/<экземпляр>` ([the forwarding contract](../../common/contracts/forwarding.md)): the cluster console sets it on the forwarding by ticket, the cluster console of the holder lets it through as declared on transition 1; the domain console strips it from an external request, accepts it only from the leaf of the role of the cluster console and passes it on to the process, and the process trusts it only on the connection of its own console. It serves as neither a right nor a check: only the journal and the alarm. The journal carries `via: <sub>/<экземпляр>`.

### Н1.4 Accepting the forwarding and the role door of TLS (М11/8 Н1.6 `roles`, `server.role`; Н3 «принять консолью»)

The domain console accepts the forwarding of the cluster console (transition 2) by [the forwarding contract](../../common/contracts/forwarding.md):
«Accept by a console» (before the gate: `X-User` — strip; `X-Operator: console` byte for byte and a connection with the proven role
`console` — keep for the journal, otherwise strip; the line `x_operator` of «Forwarding is one function») and «Client address»
(the console strips an `X-W2C-Client` that came from outside, like `X-User`). The domain console part of the item М11/8-05 (P/10-10).
«For the journal» means: the lines of `audit/domainconsole` about a request with a recognized `X-Operator: console` carry the common field `role: "console"`
([the event journal contract](../../common/contracts/event-journal.md) `door_journal`: «role — роль листа»); without a recognized
header there is no field `role`; there is no new kind and no new field (C10-XOPERATOR-JOURNAL-01, the Architect's decision of 2026-10-28).

The server side is the class `role` of [the role certificate contract](../../common/contracts/role-certificate.md) (the class `signed` and
the common `server` — ibid. «The server side: the class `signed`»):

```yaml
roles:        the process domain — the kit domain; the domain console — domainconsole; the agent and the door of the relay (P/09.2: this is
              the agent) — domainagent; the cluster console — console
server:
  role:       the role door of the domain console — the class `role` of the role certificate contract «The server side: the class `role`»: the trust
              set, the handshake, the refusals no_role, wrong_role, bad_chain before the gate, without session resumption
              (moved there without a change; C10-SDK-ROLE83, the Architect's decision of 2026-10-25)
  no_kit:     there is no kit — the door serves transition 2 on the loopback over HTTP without a role check; the role is not proven: X-Operator:
              console is stripped, X-W2C-Client is not trusted; there are no refusals no_role, wrong_role, bad_chain (the role certificate
              contract, class role, no_kit; C10-ROLE-NOKIT-01)
```

`Entry.ca`, the row `ca-certs` and their reception are [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) Н1.6; the function `peer`
and its words — [the `peer` contract](../../common/contracts/peer.md) (this lesson is a participant, steps 6–7); the leaf and the signatures —
the role certificate contract `cert`, `sig`. The row `domain/member-rows/<раздел>` (the Entry.ca of the admitted members) exists but does not read —
the trust union of the role door for this pass is only its own CAs (`ca.pem`, `ca.next.pem`): a handshake of other members is a
refusal, a journal line (В7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 36 of the list). The domain console part of the item М11/8-08 (P/10-11).

### Н1.5 The gate of the domain console (М11/9 Н1.5 `body_unit`, `session`; P/08.4 Н1.5 `domain`)

The domain console is a participant of [the gate-and-pass contract](../../common/contracts/gate-and-pass.md): of the section
«Сторожевая» the lines `gate`, `identity`, `x_user`, `caps`, `scope`, `csrf`, `body`, `refusal` and `session` apply
(the table of the sides of the contract). The states `on`, `open`, `shut` and «the trace of the domain» are [P/06.3](../../06-console/spec/06.3-console.norms.md)
Н1.8. Of the steps of `identity` the domain console has steps 3 and 4; the domain console has no steps 1 and 2 — there is no emergency session and no
unit doors (the move plan of lesson 10, В12; the Architect's decision on the plans of 8–10). Step 3 is the token of a human: the function
`token` of [the domain token contract](../../common/contracts/domain-token.md) «Проверка» by the set and `domain/revoked` of its own
store with `expect {kind: person, cluster: null}` (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 7); the refusal is
401 `{error: denied, detail: "token refused: <слово>"}` (the form of P/06.3), except `no_revocations` and a row `domain/keys` that exists
but does not read (there is nothing to check the token with): the rule «Unreadable row» of the gate-and-pass contract
(503 `{error: "unavailable"}`; the Architect's decision of 2026-10-28 on the reconciliation ddc9bee1e).

The view doors, all the doors of the kept edit, reading people, roles, grants and editing the grants of a cluster are judged by the target cluster: «Judgement by target» of [the right contract](../../common/contracts/may.md) (ADR-0110 addendum (5)). The other doors — the line `domain`.

The right is the line `domain` of [P/08.4 Н1.5](../../08-domain/spec/08.4-domain.norms.md) (one line for the domain console and the process
`domain`; the text is there): `may` ([the right contract](../../common/contracts/may.md)) by `domain/grants/domain` (exists but does not read — the rule «Unreadable row» of the gate-and-pass contract,
503 `unavailable`; the Architect's decision of 2026-10-28 on the reconciliation ddc9bee1e), `need` view/admin by
door; the input `disabled` of the function `may` is the row `domain/disabled` at the holder, the read condition is the right contract (P/06.3 Н1.3 «Data», М11/9 Н1.5 `cluster`; exists but does not
read — the rule «Unreadable row», 503 `unavailable`); the input `roles` is the rows `domain/roles/*`, `domain/groups/*` of the holder, `as_of` — `null` (P/08.4 Н1.3б `roles_at_holder`;
step 4а of ADR-0100 §1; an unreadable `domain/roles/admin` or a group from its `assigned` — 503, if the direct rows did not allow); the input `iat` is the token's. The manager line (P/08.4 Н1.3в
`manager`) serves the gate only at the doors `gives`: `/domain/users…`, `/domain/groups…`, `/domain/roles…`, `/domain/batch`, `GET /domain/grants`, `PUT /domain/grants/<кластер>`, and also `/domain/break-glass…`: at this door the group is counted only so that the request reaches the process and it answers 403 `admin only` (P/08.4 Н1.5, Н1.3в `denies`); at the others its group is not counted in `may`. The domain doors have no subsystem: `sub` is `null`.

The lines `body_unit` and `session` are [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Rights by the body» (moved; stage C guess GP-G05, the Architect's decision of 2026-10-23).

The lines `body_unit` and `session` are common with the cluster console ([P/06.7](../../06-console/spec/06.7-console.norms.md), a chapter of the late layer), except the pre-check of `body_unit` before the body and the target of `door.pass` without `?unit=`: at the domain console — `"*"`, at the cluster console — a grant on anything (the contract, `body_unit`, `need` line `door.pass`; C06-BODYEDIT-SCOPE-33-01, C06-PASS-NEED-51-01);
`/session` and `/healthz` of the domain console are as at the cluster console (the gate-and-pass contract `session`; Н1.7). The domain console part
of the item М11/9-06 (P/10-13).

The target of `door.pass` with `?unit=<sub>/<id>` is `scope` of the gate-and-pass contract as is: `*` and `unit:<sub>/<id>` of the unit
itself are compared by name without a row; `labels:…` and `unit:` of an about-unit require the unit row, and the domain console does not read the unit rows of members
(they are not in its «Data», Н1; the view and the copies of reports do not serve as them) — such a grant does not cover, none
covered — 403 by `refusal`; there is no substitution from the view or the cluster (C10-PASS-SCOPE-01).

### Н1.6 `door.pass` on the domain (М11/8 Н1.7)

```yaml
route:    /domain/<sub>/<сегмент>[/…], <сегмент> ∈ door.pass of the manifest <sub> (P/06.5 Н1.8) — the domain console passes on to the worker
          on the domain of this subsystem (P/03.7 Н1.6: the holder of the slot domain/<sub>/worker, role <sub>domain) the path
          /<сегмент>[/…] and query; the headers, the body, the answer, the codes — the gate-and-pass contract «Pass of `door.pass`» (review analysis
          of stage A 8–10, № 14); the client is of the role domainconsole; a path with
          a segment `.`/`..` is not passed to the worker — 404 not a domain route (the forwarding contract «Двери домена»; added by the reconciliation of М11, D4)
address:  the url of the heartbeat of the worker on the domain — the object domain/<sub>/heartbeat (P/03.7 Н1.6 heartbeat)
holder:   the console reads the slot domain/<sub>/worker only as «a holder exists»: holder is non-empty and released = false (the slot
          contract «States»); there is no holder — «not heard» (absent below); freshness is only the heartbeat (LOST_AFTER, P/03.7 Н1.6
          heartbeat); the console does not judge whether the instance of the heartbeat matches the holder of the slot or the age of the slot version (SLOT_TERM) —
          the validity of the operation is checked by the worker with its credentials and epoch, as at the cluster console (P/06.5
          Н1.8) (C10-PASS-SLOT-01)
absent:   the worker on the domain of this subsystem is not heard — 503 {error: "unavailable", detail: "no worker of <sub> with a
          door is heard"} (the words of the gate-and-pass contract, codes)
member:   the cluster console forwards these paths to the domain console by a row of the list of domain doors of the forwarding contract
```

The matching rule (`books`, `placement`, `members`, `topology`, `shadow`, `at` are not passed on on the domain) is the forwarding
contract «Domain doors». What the worker on the domain checks at an arrived route is [P/03.7](../../03-worker/spec/03.7-worker.norms.md)
Н1.6; the console passes `Authorization` on as it came (the move plan of lesson 10, В13).

**The second kind of `door.pass` on the domain** (ADR-0094 B1, addendum (3) item 1; [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Pass of the second kind»). The domain console passes a manifest with the second kind on in the same way: a ticket instead of `Authorization`, the headers, the answer types, `refusals`, the stream. The ticket is issued by an instance of the domain console, which remembers `jti`, `kid`, `exp` of the human's token; `user`, the closing of the request and the closing of the stream on a revocation of `jti`, on disabling the human and at `exp` — by the contract. The token is checked by the domain token contract, and the grants — by `domain/grants/domain` (Н1.5). The client to the worker is of the role `domainconsole`, the addressee is the role `<sub>domain`. There is no callback on the domain yet: the closed list of [P/06.3](../../06-console/spec/06.3-console.norms.md) Н1.9 names no doors `/domain/*`, therefore the domain console accepts the header `X-W2C-Pass-Ticket` only for a refusal, 401; the doors will enter the list with the increment of rights (ADR-0094 addendum (11)).

**Callback address header (G10-PASS-CALL-URL-01).** In this pass, the outgoing `X-W2C-Pass-Console` is absent, with or without a role kit. The same header received from outside is removed by `to_worker` of the gate-and-pass contract. `CONSOLE_CALL_PORT` names the callback listener of the cluster console; neither that URL nor the main `DOMAIN_CONSOLE_HOST/PORT` address is a callback address of this domain-console instance. The ticket remains bound to the open request in memory by the contract above; an incoming `X-W2C-Pass-Ticket` at the domain console is refused with 401 as above.

### Н1.7 The holder's page (М11/8 Н1.8)

```yaml
page:     GET /, /index.html — the published page of the console module (P/06.5 Н1.1 `module`; the module contract — P/07 Н1.5), which differs only
          by the argument of the call mount: opts.sections: [domain]; CSP — by the text of the served page (P/06.5); /platform/console.js,
          /platform/console.css — the bytes of the published module as is (P/06.5 Н1.1)
manifest: GET /manifest → {"name": "", "rows": null} — there is no root
mounts:   GET /mounts → {"root": "", "mounts": {<sub>: <the description of P/06.5 Н2 /mounts>}} by the catalogue of the holder, without media;
          fields — as P/06.5 Н2 «GET /manifest»: all the fields of unit.fields, *_secret included, their default is null
          (C10-MOUNT-FIELDS-1D6, the Architect's decision of 2026-10-25)
session:  /session, /healthz — as at the cluster console (the gate-and-pass contract «Сторожевая» session; review analysis
          of stage A 8–10, № 14); server_time and timezone of GET /session — the same lines of the contract: the clock of the domain console and TIMEZONE
          of the environment of its box, empty or not by the form — a start refusal, code 2 (the environment file contract «Environment variables»; ADR-0094 B6)
module:   which doors the module calls in the mode domain, and that its nodes are member:<член>, domain — a property of the published module
          (console.js — data of the specification; the late layer P/07 Н1.6, the description — КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10a), not of implementations; the check is the module test at its
          owner; the acceptance of the lesson — only the doors of the page
```

### Н1.8 The alarm list at the holder (М11/11 Н1.8)

The console assembles the alarms of members from their reports: it opens no connections to a member. The history (chapter 8.9 Н1.9) is written only by
the process `domain`; the list only reads it. The Architect's decision on the questions of М11/11; the function `alarms` and its vector belong to this
lesson (the Architect's decision on the review analysis of stage A 8–10, № 8).

```yaml
door:          GET /domain/alarms?since=&until= at the domain console (view); the default is the day before now; not finite numbers or
               since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}; the time is by the
               grammar of the reader time of the row codec after URL decoding (the gate-and-pass contract
               «Numeric query parameters»: 1e3, -1, «+», «_», a space — a refusal; the detail of the refusal is its own, above;
               C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27), the parameter is not repeated (added by the reconciliation
               of М11, A12)
answer:        200 {since, until, events, members, complete, sentence} — the function alarms (Н3) on the page of the last report
               of each member of the list (the holder included), on the history (P/08.9 Н1.9) and on the witnesses
member_state:  ok | silent | not_reporting | never | unreadable
  silent:      the last report is older than LOST_AFTER (the observation contract «Свежесть», 45 s); silent_since = the last report + LOST_AFTER
  not_reporting: silent, and a witness heard a unit of the member later than the last report
  never:       there has never been a report
  unreadable:  the page is not by the form of P/09.1 Н1.10 (at the function alarms — the input "garbled" too)
silence_line:  a silent member — an alarm row {t: silent_since, kind: silent | not_reporting, class: alarm, member,
               subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?} — always, while it is silent
witness:       domain.witness {report, member_field} (P/02.1 Н1.2б): the objects <sub>/<report>/<name> = {ts, cluster, units: {<член>:
               seconds since the last time}} at the clusters and in the reports; the family is the keys <sub>/<report>/<name> (the name after «/»), the agent
               carries each object of the family as a report object (P/09.1 Н1.2 member_objects), the object <sub>/<report> without a name is
               not a witness (added by the reconciliation of М11, A2; the agent's side — P/09.1 Н1.10); member_field — the fixed field of the unit that carries the name of the member
               (the load refusal — P/02.1 Н1.2б); alive_at = ts − units[member], alive_via = "<cluster>/<name>"; there are several witnesses —
               the largest alive_at among those later than last_report; on a tie — the smaller alive_via in UTF-8 bytes
               (added by the reconciliation of М11, A17)
clock:         the domain clock of the alarm rows — [the alarm history contract](../../common/contracts/alarm-history.md) «Domain clock» (moved there
               without a change; the layout audit, the Architect's decision of 2026-10-25, А-13)
events_order:  by t descending, then member, id; the rows of the history — from_history: true
```

The member's alarm page and its front are [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) Н1.10; the mark `reported` —
[chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) Н1.3; the history — chapter 8.9 Н1.9 (`same_line`, `cut_before`).

---

## Н2 Doors

The HTTP contract: [10-domain-console.api.openapi.yaml](10-domain-console.api.openapi.yaml). The refusal body is `{error, detail}`.
The closed list of the doors of the domain console with the columns «Ожидание» and «Личность» is [the forwarding
contract](../../common/contracts/forwarding.md) «Domain doors» (owner P/06, participants 8.0 and this lesson; the Architect's decision
of 2026-10-20, ADR-0083 addendum (14) item 5); each row there is a door of the domain console, it has no other door `/domain/*`.
Who answers a row:

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain`, `/domain/folders`, `/domain/folders/<id>/units`, `/domain/memberof/<член>/<sub>/<rows>/<id>`, `/domain/<sub>/<rows>`, `/domain/<sub>/kept/<имя>`, `/domain/relays/<ретранслятор>`, `/domain/<sub>/tables/<таблица>`, `/domain/shadow`, `/domain/members`, `/domain/topology`, `/domain/placement`, `/domain/placement/<sub>/<ref>`, `/domain/grants`, `/domain/shared` | the domain console itself | Н1.2 | Н1.2, Н4 |
| GET `/domain/alarms` | the domain console itself | Н1.8 | 400; Н4 |
| the other rows of the list (edits, people doors with any method, `POST /api/login`) | the process `domain` — the console passes on (Н1.3) | the answer of the process as it came (the chapters of lesson P/08) | Н4; the codes of the process — the OpenAPI of lesson P/08 |
| `/domain/<sub>/<сегмент door.pass>[/…]` | the worker on the domain — the console passes on (Н1.6) | the answer of the worker as it came | [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Pass of `door.pass`» |
| GET `/`, `/index.html`, `/platform/console.js`, `/platform/console.css`, `/manifest`, `/mounts`, `/session`, `/healthz` | the domain console itself | Н1.7 | [P/06.5](../../06-console/spec/06.5-console.norms.md); `/session` — the gate-and-pass contract |

A path with a segment `.` or `..` (percent-encoded too) — 404 `not a domain route` before the gate, before the passing to
the process and to the worker on the domain (the forwarding contract «Domain doors»).

---

## Н3 Procedures

### accept the forwarding and pass on to the process (the domain console)

The lesson introduces no order of checks of its own: each place is set by its own norm. «Accept by a console» is [the forwarding
contract](../../common/contracts/forwarding.md) «Accept by a console» (Н1.4); the refusals of the role door are before the gate (Н1.4
`server.role`); a path with `.`/`..` — 404 before the gate (Н2); the gate — Н1.5; further — its own read door (Н1.2, Н1.8),
`door.pass` (Н1.6) or the passing to the process `domain` (Н1.3 `pass`): the answer of the process is as it came, a break and silence — 502.

### alarms(input) (М11/11 Н3)

The filter is at the door, the form is at the function: the alarm door assembles the input from the store and discards a broken witness (without ts and the like)
with a counter before the call — resilience; the vector alarms receives an already assembled input, and a witness not by the form in
it is an input not by the form, code 2 (H14). One does not contradict the other (added by the reconciliation of М11, cammeta-python М11-11 № 20).
A mark `domain/members/<член>/reported` whose read the store did not confirm — 503 `unavailable` of the whole door; a mark
read but not by the form — the member enters the function with `reported: "garbled"` (C10-REPORTED-OUTCOME-1D6, the Architect's decision of 2026-10-25).
The input is assembled from the store of the holder (C10-ALARMS-INPUT-01): `last_report` is `received_at` of the mark, `received_at` and
`sent_at` are the fields of the last request of the mark ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н1.3; the domain clock), not
the age of the console's observation; the members are the row `domain/member-rows/<раздел>`: there is none — 404 `no domain here` (like `GET /domain/members`,
Н1.2б), it does not read or the read is not confirmed — 503 `unavailable` of the whole door, not an empty list; the mark is read, and
the generation `reports/<rev>` of the mark does not exist or it is not with its `sha256` — `page: "garbled"` (the member is `unreadable`, the witnesses of this
report are not taken), not `page: null`: «no page» is only for a readable generation without a page.

```
input:  {now, since, until, lost_after, members: {<член>: {last_report: <domain clock> | null, received_at, sent_at, page: <P/09.1 Н1.10> |
         "garbled" | null, history: <P/08.9 Н1.9> | null} | {reported: "garbled", page?, history?}}, witnesses: [{sub, name, ts, cluster, units}]}
1. each member:
   reported = "garbled" (the mark is read, not by the form) → unreadable; there are no silence row and no page rows of this member,
                                                        no known_until and no silent_since (C10-REPORTED-OUTCOME-1D6, the Architect's decision of 2026-10-25)
   no last_report and no page                         → never
   no last_report, but a page                         → an input not by the form (code 2): a page comes only with a report
   page = "garbled" or not by the form of P/09.1 Н1.10 → unreadable; not by the form is also a row without id, class ≠ alarm, kind
                                                        empty, unit not a string, from > to (added by the reconciliation of М11, A15)
   now − last_report > lost_after                     → silent; a witness with ts − units[member] > last_report — not_reporting
   otherwise                                          → ok
   page = null with last_report — there is no page: there are no page rows, not unreadable
2. rows: the page (the clock of Н1.8 clock) ∪ the history (from_history, t as stored) without repeats by same_line — present in both,
   the page row is taken; a repeat inside one page — the first in the order of the page (reconciliation of М11, A16); the silence row — Н1.8 silence_line; the window [since, until] — for all rows, the silence
   row too
3. members: {<член>: {state, truncated?, known_until?, silent_since?, alive_at?, alive_via?, history_cut_before?}};
   truncated: true — for a readable page with truncated; known_until — last_report for silent/not_reporting;
   history_cut_before — for a history with cut_before > since
4. complete = all ok; sentence — «every member answered» or phrases joined by «; », by members (UTF-8 bytes), for a member — in
   the order of the list below:
   «<m> silent since <HH:MM> — its alarms from its last report, known up to <HH:MM> UTC; none known since»
   «… — but <alive_via> heard of it at <HH:MM>: alive, and not reporting to the domain»
   «<m> has never reported to the domain»; «<m>'s page of alarms does not read»
   «<m> had more alarms than one page holds; showing its newest»
   «<m> had an alarm storm: the domain keeps only its newest alarms, and what came before <HH:MM> UTC is not known in full»
   (the time is UTC of the domain clock)
```

`same_line`, a repeat in a page and `cut_before` are [the alarm history contract](../../common/contracts/alarm-history.md) (C10-ALARM-SAME-LINE83).

**Races.** A member without a connection and an alarm storm — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) Н3 «Races».

---

## Н4 Refusals

The codes of transition 2 are the reception and the passing ([the forwarding contract](../../common/contracts/forwarding.md) «Refusals by transition»; the decision
of the Architect on the review analysis of stage A 8–10, decision 3: each OpenAPI carries only its own codes). The codes of transition 3 (the process
`domain`: the codes of its own door, `409 deposed`, `503 frozen`, `503 standby`) the console serves as they came — the OpenAPI of lesson
[P/08](../../08-domain/spec/08-domain.api.openapi.yaml); the codes of transitions 1–2 from the forwarding side are the cluster console (chapter P/06.7).

| `error` | Code | When |
|---|---|---|
| the word of `peer`: `no_role` / `no_role`, `wrong_role`, `bad_chain` | 401 / 403 | the domain console accepts the forwarding on transition 2 (Н1.4 `server.role`; the normative client is the cluster console of the holder): at the TLS door (there is a kit) there is no client certificate — 401; without a kit (`no_kit`) the door serves on the loopback over HTTP without a role check — there are no such refusals, the role is not proven, `X-Operator: console` is stripped (the role certificate contract, class `role`, `no_kit`; C10-ROLE-NOKIT-01); the certificate chained to the union of CAs (its own `ca.pem`, `ca.next.pem` or the Entry.ca of an admitted member), but the SAN of the leaf does not have exactly one role or it is not `console` — 403; a signature of the leaf or of a CA outside the list of the role certificate contract `sig` — 403 `bad_chain` (reconciliation of М11); before the gate. A chain not by the union of CAs — a handshake refusal, there is no HTTP answer (ADR-0083 addendum (19) item 2; review analysis of ADR-0090, № 27) |
| `not a domain route` | 404 | a path with a segment `.` or `..`, percent-encoded too (the forwarding contract «Двери домена»; reconciliation of М11, D4) — before the gate, without passing on |
| `denied` | 401, 403 | the gate (Н1.5; the form of [P/06.3](../../06-console/spec/06.3-console.norms.md) Н4): there is no token or it did not pass; `may` — deny |
| (the gate `shut`) | 503 | there were keys or there is a trace of the domain, but there is nothing to check with (the gate-and-pass contract `shut`; P/06.3 Н1.8) |
| `unavailable` | 503 | the gate: a row of the access check — `domain/keys`, `domain/revoked` (`no_revocations`), `domain/grants/domain`, `domain/disabled`, `domain/roles/admin` and the groups from its `assigned` — exists but does not read (Н1.5; the rule «Unreadable row» of the gate-and-pass contract) — not 401, not 403 |
| ([P/06.5](../../06-console/spec/06.5-console.norms.md) Н4) | 413 / 400 / 408 | the body is larger than the limit of the console, chunked, read slowly (the gate-and-pass contract `body`) |
| the words of the forwarding contract `answer` | 502 | the passing to the process `domain` (Н1.3 `pass`): a break and silence — as the forwarding contract «Forwarding is one function» `answer` |
| `door.pass` | 400, 408, 413, 502, 503 | the codes of «Pass of `door.pass`» of the gate-and-pass contract (`codes`); the worker on the domain is not heard — 503 `unavailable` (Н1.6 `absent`) |
| `no domain here` | 404 | the view is not built (Н1.2а, Н1.2б, Н1.2в, Н1.2е) |
| `unavailable` | 503 | a row that a read door answers with (the view, the shadow, `domain/member-rows/<раздел>`, `domain/topology`, `domain/placement`, a placement record, the pointer `domain/shared` and its document) exists but does not read — not 404 and not «there is no row» (Н1.2а–Н1.2г, Н1.2е; В7 item 3, the Architect's decision of 2026-10-28, П1; lines 36, 42, 43, 50, 54 of the list) |
| `not in the directory` | 404 | a manifest without `domain.ref` (Н1.2а) |
| `no such member` | 404 | `?cluster=` is not a member (Н1.2а) |
| `siblings` | 409 | transition 3 — the answer of the process `domain` as it came: an edit of a ref at several units of one member without `?id=` |
| `executors` | 409 | transition 3 — the answer of the process `domain` as it came: an edit `PUT`, `DELETE` `/domain/<sub>/<rows>/<ref>` without `?cluster=`, the ref is at two executors or more; the body is `{error, detail, clusters}` ([P/08.6](../../08-domain/spec/08.6-domain.norms.md) Н3 «accept an edit» step 2а; ADR-0091 addendum (15) item 4) |
| — | 400 / 404 | the request: `cluster` twice or empty; there is no manifest; `rows` is not its own ([P/06.5](../../06-console/spec/06.5-console.norms.md) Н2); placements: there is no record, there is no manifest or it is without `domain.ref` (Н1.2г) |
| `refused` | 400 | the window of `/domain/alarms` (Н1.8 `door`) |

The words of its own doors are the closed list [`refusal-words.tsv`](../data/refusal-words.tsv) (ADR-0094 B5); the rules are [P/08.0](../../08-domain/spec/08.0-domain.norms.md) Н4. The row «—» of the table: 400 — `refused`, 404 — `no such path`, placements — `refused`. Its own doors have no `field`: they read, they have no body; at the doors of transition 3 — the answer of the process `domain` as it came.

The words of `peer` are [the `peer` contract](../../common/contracts/peer.md) «Refusal words».

---

## Н5 Acceptance

The catalogue [`acceptance/`](../acceptance/README.md): the stand of several clusters of chapter 8.3 (`hold`, `m1`, `m2`, the catalogue
`testsub`), scenarios 02 (from М11/11) and 05 (from М11/08) — the numbers and steps are the former ones; 06–09 — the coverage audit of P/10 (audit-kimi
290ae7697); 10–16 — its second pass (audit-coverage-gemini 798e11a44); 17 — ADR-0094 B4; 18, 19 — the `kept` and relay doors (new scenarios of 2026-11-02, `journal/corrections.tsv`). The alarm list is the vector
[`vectors/alarms`](../vectors/alarms/README.md) (27 rows: 15 — the former sc. 04 of the acceptance of М11/11; 16 — C10-REPORTED-OUTCOME-1D6; 17–27 — the second pass of the coverage audit).

```yaml
alarms:    the input — Н3 alarms; the output {events, members, complete, sentence}
exit:      0 — computed; 2 — an input not by the form (the rows alarms-15, alarms-17…23 — @exit 2: lost_after, a member name, page without
           last_report, sent_at null at a member with a report, history with cut_before null, a witness without ts, reported together with last_report,
           an extra field; the other cases — by reading; a page [], from > to, a row without id — 0 unreadable, the rows alarms-24…26); the exit codes are by the principle of «Стенда домена» of the common README of acceptance («Коды выхода команд-векторов»: 2 — the form of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the reconciliation of М11, H14).
           Not by the form at alarms: a member name not by the member grammar, lost_after not > 0, a history or a witness not by the form of P/08.9 Н1.9
           and Н1.8 (a history without cut_before or with cut_before null — too, P/08.9 Н1.9 A13), a page object without received_at and sent_at,
           no received_at or sent_at at a member with a report, a history as a string, a witness without ts, witnesses not a list, now not
           a number, an extra field; reported — not "garbled", or together with last_report, received_at, sent_at (C10-REPORTED-OUTCOME-1D6);
           a page that is not an object ([], a number) or not by the form of P/09.1 Н1.10 — 0 unreadable, not 2; page null with
           last_report, received_at and sent_at null at never — 0
```

| № | Scenario | Norms |
|---|---|---|
| 02 | stand: the agent `m2` is turned off — `silent` in the delivery, the alarm row `silent` in `/domain/alarms`; a window not by the grammar and `since > until` — 400; it came back — took the document | Н1.8; steps 04, 09 (delivery) — Н1.2е; step 11 (the agent signature at `/events` of the member console) — a neighbour on the stand |
| 05 | stand: the holder's page — `/`, the module, `/manifest`, `/mounts`, `/session` with `server_time`, `timezone` | Н1.7 |
| 06 | `no-domain-here` (the coverage audit of P/10, K01): the domain is not installed — the gate is `open`, there is no view; `GET /domain`, `/domain/shadow`, `/domain/members`, `/domain/topology`, `/domain/shared`, `/domain/testsub/counters` — 404 `no domain here` | Н1.2а, Н1.2б, Н1.2в, Н1.2е; Н4 |
| 07 | `view-unreadable` (the coverage audit of P/10, K01): the process `domain` is stopped, the view is spoiled — 503 `unavailable`, not 404, at `GET /domain`, `/domain/members`, `/domain/testsub/counters`, `/domain/shared`; the shadow is spoiled — 503 at `/domain/shadow` | Н1.2а, Н1.2б, Н1.2е; Н4 |
| 08 | `pass-process-down` (the coverage audit of P/10, K02): the process `domain` is stopped — an edit and a people door (and `GET`) — 502 `did not answer`, its own read door answers; after the return the same edit — `rev: 1` | Н1.3 `pass`, Н1.3а; Н4 |
| 09 | `pass-process-silent` (the coverage audit of P/10, K03): the process `domain` is frozen (`@freeze`) — an edit — 502 `did not answer`; after `@thaw` — `rev: 1` | Н1.3 `pass`; Н4 |
| 10 | `read-doors-head-and-query` (the second pass, G02): `HEAD /domain`, `/domain/topology` — 200 without a body; `?cluster=` empty or twice — 400; there is no manifest, `rows` is not its own — 404 | Н1.2, Н1.2а; Н4 |
| 11 | `topology-placement-unreadable` (G02): `domain/topology`, the counter `domain/placement`, a placement record not by the form — 503 `unavailable`, not `rev 0` and not 404; the former counter — 200; there is no record or manifest — 404 | Н1.2в, Н1.2г; Н4 |
| 12 | `shared-and-members-unreadable` (G02): the pointer `domain/shared` not by the form — 503, not `doc: null`; the row `domain/member-rows/<раздел>` not by the form — 503 at `/domain/members` and of the whole door `/domain/alarms` | Н1.2б, Н1.2е, Н3 `alarms`; Н4 |
| 13 | `alarms-query-lexemes` (G03): `since`/`until` not by the grammar of `time` (`1e3`, `-1`, `+1`, « 1», `1_000`, `1e10`) — 400 `refused`; `since` twice — 400; `%31` — accepted | Н1.8 `door`; Н4 |
| 14 | `alarms-mark-unreadable` (G03): the mark `reported` is spoiled — the door 200, the member `unreadable` without `known_until`, `silent_since` | Н3 `alarms` |
| 15 | `dot-segments-and-x-user` (G04): without a token a segment `.`/`.%2E` — 404 `not a domain route`, not 401; an arrived `X-User` is stripped — 401, `/session` is anonymous; with a token — the identity from the token, the grants in `/session` | Н2, Н1.4, Н1.5; Н4 |
| 16 | `gate-rows-unreadable` (G04): `domain/disabled`, `domain/revoked`, `domain/grants/domain`, `domain/keys` not by the form — 503 `unavailable`, not 401/403; the former value — 200 again | Н1.5; Н4 |
| 17 | `read-versions` (ADR-0094 B4): `ETag` of the doors of one row; `index` of the records and `versions` of the grants equal the index of the store; `If-Match`, `Idempotency-Key` and `ETag` go through the cluster console and the domain console | Н1.2; the forwarding contract `pass`, `answer`; P/08.0 Н1.9 |
| 18 | `kept-door`: `GET /domain/<sub>/kept/<имя>`: the mask `*_secret` in depth and `enc:`, a family and the undeclared — 404, forwarding at the member console; without an identity 401, a non-viewer 403 also on the undeclared: the right before 404 | Н1.2а; P/06.2 Н1.4 |
| 19 | `relay-door`: `GET /domain/relays/<ретранслятор>`: the names behind the relay without keys, a relay without members — empty, not a member — 404, a non-viewer — 403 also on the undeclared: the right before 404, forwarding at the member console, without an identity 401 | Н1.2а; P/08.3 Н1.2 |

The doors of the lesson on the stand of the chapters of lesson P/08 are neighbours on the stand (the rule «сценарий — главе своего исхода, соседи — на стенде»,
ADR-0083 addendum (13)):

| Norm | Scenarios |
|---|---|
| P/10-01 | sc. 05 of the acceptance of [chapter 8.3](../../08-domain/acceptance/3/README.md); sc. 06, 09 of the acceptance of [chapter 8.1](../../08-domain/acceptance/1/README.md) (М11/03 sc. 05, 06, 09) |
| P/10-02 | sc. 01, 02 of the acceptance of chapter 8.3 (М11/03); the stands of chapters 8.3 (topology), [8.6](../../08-domain/acceptance/6/README.md), [8.8](../../08-domain/acceptance/8/README.md), [8.9](../../08-domain/acceptance/9/README.md) through `holder` |
| P/10-05, P/10-13 | sc. 01, 02 of the acceptance of [chapter 8.4](../../08-domain/acceptance/4/README.md) (М11/09) |
| P/10-07 | sc. 14 step 6 and sc. 04 step 16 of the acceptance of chapter 8.3; sc. 19 of the acceptance of chapter 8.3 (the source of `members`, `knocking` by default); sc. 02 of the acceptance of chapter 8.8 |
| P/10-08 | sc. 15 step 2 of the acceptance of chapter 8.3 (М11/04 sc. 01) |
| P/10-09 | sc. 01 step 2, sc. 09 step 12 of the acceptance of chapter 8.6; sc. 01 step 7 of the acceptance of chapter 6.7 (review analysis of stage B 8–10, № 22: М-1) |
| P/10-12 | sc. 02, 08 of the acceptance of chapter 8.4 |
| P/10-14 | sc. 01 steps 2, 14 of the acceptance of chapter 8.9; sc. 02 steps 04, 09 of this lesson |

Checked by reading: `door.pass` on the domain (Н1.6) — the stand has no worker on the domain; «принять консолью» and the role door
(Н1.4) — until the TLS stand; the reader's side of the manifest row at start (Н1.1) — the domain console has no step in acceptance (the move plan
of lesson 10, В9: the scenario of a manifest change — by a separate edit of acceptance after the move); the deadline «Ожидание» of the passing (502 on
silence not earlier than the deadline) and `answer broke off` — acceptance does not measure the answer time and does not break the answer of the process (502 on
a break and on silence — sc. 08, 09); `not in the directory` — the manifests of the stand have `domain.ref`; that the domain console does not recompute `deposed`, `frozen`,
`standby` (Н1.3) — the stands of chapters 8.8, 8.10 through `holder`; the role journal — acceptance does not compare the journal; the family of witnesses in
the report (A2); there is no row `domain/placement` (C10-PLACEMENT-ABSENT-01) and there is no row `domain/keys` with a trace of the domain (`shut`) —
the door `admin.sock` cannot remove a row under `domain/` (P/01.2 Н1.3 `never`); a generation `reports/<rev>` not by the `sha256`
of the mark (C10-ALARMS-INPUT-01) — the key carries `rev` of the mark, the directive `@spoil object` takes the key as is; `X-Operator: console` at
a proven role — until the TLS stand.

The TLS stand ([`common/acceptance/tls/`](../../common/acceptance/tls/README.md)): the probes of the door `holder` (class `role`) belong to this
lesson, P/10-11: item 2 (9 rows of `holder`), item 7, «смена объединения» (2 probes), item 8 steps 2–5. The lesson gets the scenarios when
the stand is ready (ADR-0083 addendum (9)).

---

## Implementation decides

1. **the command `alarms`** — a template with `{input}` (the vector `alarms`; М11/11 «Решает реализация» item 1 in the part of `alarms`;
   the command `resolve` — the cluster console, chapter P/06.7).

---

## Readiness checklist

An implementation corresponds to the lesson when each norm is fulfilled; the norm id `P/10-MM` is what the deltas of decisions,
findings and window records refer to (ADR-0080 addendum 6). The items of the lesson are М11/1-08, М11/3-12, М11/8-10, М11/8-11, М11/9-13, М11/11-08 and
the parts «(часть)» by `note` of [id-map](../../common/id-map.tsv) (the move of lesson 10).

- [ ] **P/10-01** the view doors `GET /domain` (with `age` by the wall clock of the console), `/domain/<sub>/<rows>[?cluster=]`, `/domain/<sub>/<rows>?part=` — sc. 10, `/domain/<sub>/tables/<таблица>?cluster=` (acceptance — step 11 of the analysis of ADR-0110), `/domain/shadow` and their refusals `no domain here`, `unavailable` (an unreadable view and shadow), `not in the directory`, `no such member` (Н1.2а) — a neighbour on the stand of chapters 8.3 (sc. 05) and 8.1 (sc. 06, 09); `no domain here` — sc. 06, `unavailable` — sc. 07 (and at `/domain/members`, `/domain/shared`); `HEAD`, `?cluster=` empty or twice, there is no manifest, `rows` is not its own — sc. 10; `not in the directory` — by reading (the manifests of the stand have `domain.ref`); the content of the view — chapter 8.1
- [ ] **P/10-02** passing the edits on to the process `domain` Н1.3: the method, the path, the body, the headers as they came, `X-W2C-Client` is set by the console (the forwarding contract «Client address»), the deadline — «Ожидание» of the row, the answer as it came, 502 on a break and on silence — a neighbour on the stand of chapters 8.3 (sc. 01, 02), 8.6, 8.8, 8.9; 502 `did not answer` on a break — sc. 08, on silence — sc. 09 (`@freeze`); the deadline «Ожидание» and `answer broke off` — by reading; the reception — P/08.0-01
- [ ] **P/10-03** `door.pass` on the domain Н1.6: `route`, `address`, `absent`, the segments `.`/`..` — 404; the rule and the codes — the gate-and-pass contract «Pass of `door.pass`» — by reading (the stand has no worker on the domain); the segments `.`/`..` at the doors of the domain console — 404 `not a domain route` before the gate (Н2) — sc. 15
- [ ] **P/10-04** the holder's page Н1.7: `/`, the module, CSP, `/manifest` `{"name": "", "rows": null}`, `/mounts`, `/session` with `server_time`, `timezone`, `/healthz` — sc. 05; `TIMEZONE` not by default and the start refusal by it — by reading (the stand starts the domain console without this variable); the calls of the module in the mode `domain` — the module test at its owner ([P/07](../../07-console-module/spec/07-console-module.norms.md) Н1.6, Н5)
- [ ] **P/10-05** the people doors through the domain console to the process `domain` with any method, the edits of grants and `/domain/revoke` — the passing (Н1.3а) — a neighbour on the stand of chapter 8.4 (sc. 01, 02); the check at the process — P/08.4-09
- [ ] **P/10-06** the alarm list Н1.8: the states, the silence row, the witness, the clock `clock`, the order, the strictness of the page, the tie of witnesses, the function `alarms` Н3 — sc. 02, the vector `alarms` (codes 2, a page not by the form, the window and the silence row — rows 17–27); the grammar of `since`/`until` (A12) — sc. 13; an unreadable `domain/member-rows/<раздел>` — sc. 12, the mark `reported` — sc. 14; the family of witnesses in the report (A2) and a generation not by the `sha256` of the mark — by reading; the history is written by chapter 8.9 (P/08.9-05)
- [ ] **P/10-07** `GET /domain/members` → `{members, parts, knocking, count, cursor?}` (Н1.2б) — a neighbour on the stand of chapters 8.3 (sc. 14 step 6, sc. 04 step 16) and 8.8 (sc. 02); the source of `members` and `knocking` by default — sc. 19 of the acceptance of chapter 8.3 (`19-members-source`); the row `domain/member-rows/<раздел>` does not read — 503 — sc. 12
- [ ] **P/10-08** `GET /domain/topology` — from the row, not from the view: right after a PUT — the new `rev` (Н1.2в; T1) — a neighbour on the stand of chapter 8.3 (sc. 15 step 2); the row does not read — 503 — sc. 11
- [ ] **P/10-09** `GET /domain/placement`, `/domain/placement/<sub>/<ref>` — the console answers itself (Н1.2г) — a neighbour on the stand of chapter 8.6 (sc. 01 step 2, sc. 09 step 12) and of chapter 6.7 (sc. 01 step 7; review analysis of stage B 8–10, № 22: М-1); the counter and the record do not read — 503, there is no record or manifest — 404 — sc. 11; there is no counter (`rev` 0) — by reading
- [ ] **P/10-10** «принять консолью» at the domain console (Н1.4): `X-Operator: console` — only at a proven role, the arrived `X-User` and `X-W2C-Client` are stripped (the forwarding contract) — by reading (until the TLS stand); the stripping of `X-User` — sc. 15
- [ ] **P/10-11** the role door of TLS `server.role` (Н1.4): the union of CAs by `ca-certs` and `Entry.ca` plus its own CA, a refusal by the handshake, 401/403 `no_role`, `wrong_role`, `bad_chain` before the gate, without session resumption, EKU `clientAuth` — by reading; the TLS stand item 2 (`holder`), item 7, «смена объединения», item 8 — when the stand is ready (ADR-0083 addendum (9))
- [ ] **P/10-12** `GET /domain/grants` → `{grants: {<кластер>: [line…]}}` (Н1.2д) — a neighbour on the stand of chapter 8.4 (sc. 02, 08)
- [ ] **P/10-13** the gate of the domain console (Н1.5): the steps of `identity` 3 and 4, the token `kind: person`, `may` by `domain/grants/domain` (`as_of` null), `need` view/admin by door, `body_unit`, `grants` in `/session`; a participant of the gate-and-pass contract — a neighbour on the stand of chapter 8.4 (sc. 01, 02); `grants` in `/session` of the domain console — sc. 15; «Unreadable row» (`domain/disabled`, `domain/revoked`, `domain/grants/domain`, `domain/keys`) — sc. 16
- [ ] **P/10-14** `GET /domain/shared` → `{doc, delivery, declared}` (Н1.2е; `view.shared` is built by chapter 8.9) — sc. 02 steps 04, 09; a neighbour on the stand of chapter 8.9 (sc. 01 steps 2, 14); the pointer does not read — 503 — sc. 12
- [ ] **P/10-15** the start (Н1.1): the reader's side of the manifest row (P/02.3 Н3), the schema check (P/06.6 Н3), readiness — the port (the domain console part of the line М11/12-08; the text is P/02.4 Н1.12) — by reading (the move plan of lesson 10, В9)
- [ ] **P/10-16** `door.pass` of the second kind on the domain (Н1.6): the ticket remembers `jti`, `kid`, `exp`, the stream is closed on a revocation, on disabling and at `exp`, two tokens, one revoked — the ticket of the first is 401, of the second works; the ticket header on the domain — 401 — by reading: the stand has no worker on the domain
- [ ] **P/10-17** the row version at the read doors Н1.2 (ADR-0094 B4): `ETag` of the doors of one row, `index` and `versions` of the lists; the headers of the version and of the memory through forwarding and passing — sc. 17

## Correspondence to former lessons

The lesson is moved (stage B, commit 10 of the move of 8–10). From М11/1 — Н2 and the Н4 rows of the view doors and the item М11/1-08 (here Н1.2а,
P/10-01); from М11/3 — Н1.8 `console` and the console side of `pass` (here Н1.3; the item М11/3-12 → P/10-02, the part of 8.0 — P/08.0-01),
the Н2 row `GET /domain/members` (Н1.2б, part of М11/3-02 → P/10-07); from М11/4 — the Н2 row `GET /domain/topology` (Н1.2в,
part of М11/4-02 → P/10-08); from М11/6 — the Н2 rows `GET /domain/placement*` (Н1.2г, part of М11/6-01 → P/10-09); from М11/8 —
Н1.6 `roles`, `server.role` (Н1.4, part of М11/8-08 → P/10-11), Н1.7 (Н1.6, М11/8-10 → P/10-03), Н1.8 (Н1.7, М11/8-11 →
P/10-04), the domain console side of Н3 «принять консолью» (Н1.4, part of М11/8-05 → P/10-10), the Н2 and Н4 rows of the domain
console, sc. 05; from М11/9 — Н1.5 `body_unit`, `session` (Н1.5, part of М11/9-06 → P/10-13), Н1.9 `pass` (Н1.3а,
М11/9-13 → P/10-05), the Н2 row `GET /domain/grants` (Н1.2д, part of М11/9-04 → P/10-12); from М11/11 — Н1.6 `door` (Н1.2е, part of
М11/11-06 → P/10-14), Н1.8 and Н3 `alarms` (Н1.8, Н3; М11/11-08 → P/10-06, formerly P/08.9-04 — the number is free), the Н2 and Н4 rows
of the domain console, Н5 `alarms`, `exit` in the part of `alarms`, sc. 02 and 04 (the vector `alarms`), «Implementation decides» item 1 in the part of
`alarms`; from М11/12 — Н1.8 in the part of the domain console (Н1.1, part of М11/12-08 → P/10-15). The references «урок N» of the moved text
are written as the addresses of the chapters of lessons P/08, P/09, of the contracts and of the subsections of this lesson; «консоль держателя» — «консоль домена»
(the report of Claude 2c5e07dcc, L-5). The door of «Ожидание» and «Личность» is the forwarding contract (ADR-0083 addendum (14) item 5). М11 normed
what `М12A_Domain/03-the-api-and-what-it-refuses.md` told (step 5 — the domain console), `М12A_Domain/04-who-may-call-it.md`
(step 6 — the gate of the console and the domain doors) and `М12A_Domain/13-alarms-from-every-member.md` (steps 1–7, the list at the holder).
ADR-0032, ADR-0061, ADR-0074 C5, ADR-0075. The historical sources are kept in Git.

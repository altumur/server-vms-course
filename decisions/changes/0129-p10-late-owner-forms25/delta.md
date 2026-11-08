# Delta 0129-p10-late-owner-forms25

change: 0129-p10-late-owner-forms25 rev 1 · lesson P/10 and related P/08/P/06/P/02/common · state review

Base `33a3c2342c63adb923b84e4608fba338bea32a5c`; accepted Source429 component by8bb3 is incorporated by its exact15-owned Source delta, not by old parents/metadata. ADR0129(25) provides the remaining faithful fixes. ADR0129(29) items6/7 (fd6d0c3f) and direct Architect clarification select the narrow legacy known-build comparison/admission removal; current guards/settings writer preserved. dead_band field and requested-rebalance norm stay unchanged.

Normalized LF/trailing spaces/one final LF; same-or-higher headings outside code fences terminate req units (the immediately associated heading belongs to its unit). No new requirement ids.

## MODIFIED

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R002

old-sha256: 2b7687ebfa16fc8157b8c6e034b7dadec5c613fcb39f696483af479d0edbc416

<!-- req: P/10-R002 -->
## N1 Form

[runtime-constants.tsv](../forms/runtime-constants.tsv) projects three owned positive integer limits; RELAY_MEMBERS_MAX is read from its P/08.3 owner form with their requirement anchors; the [form grammar](../forms/README.md#inputs-and-constants) fixes units and scope. These are not additional environment settings.

**Time.** The lesson writes no rows and objects with time; a line of the role journal has `t` by [the event
journal contract](../../common/contracts/event-journal.md). `age` of the answer of `GET /domain` is seconds by the wall clock of the console, not a time in
a row (N1.2a); the time of the rows of the alarm list is the domain clock (N1.8 `clock`); the history object — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md)
N1 «Time», the member's alarm page — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1 «Time».

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/<manifest:domain.witness.report>/<name>`;
- writes: `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append);
- reads: `domain/relay-members/<relay>`, `domain/<sub>/<manifest:domain.kept>`, `domain/folder-units/<id>`, `domain/folder-units/<id>/<part>`, `domain/folder-counts/<id>`, `domain/view-rows/<part>`, `domain/anywhere`, `domain/folders/<id>`, `domain/memberof/<member>/<sub>/<manifest:unit.rows>/<id>`, `domain/members/<member>/tables/<sub>/<table>`, `domain/roles/<name>`, `domain/groups/<name>`, `platform/manifest/<sub>`, `platform/manifest/<sub>/rev` (the mark: a manifest change — P/02.3 N3; V7 item 3, the Architect's decision of 2026-10-28, P3; line 19 of the list), `platform/schema`, `/etc/w2c/tls/<role>/server.key`, `domain/view`, `domain/shadow`, `domain/holder`, `domain/keys`, `domain/root`, `domain/revoked`, `domain/member-rows/<part>`, `domain/members/<member>/ca-certs`, `domain/members/<member>/reports/<rev>`, `domain/members/<member>/reported`, `domain/topology`, `domain/<sub>/worker`, `domain/<sub>/heartbeat`, `domain/placement`, `domain/placement/<sub>/<ref>`, `domain/disabled`, `domain/grants/<cluster>`, `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/alarm-history/<member>`.

The domain console writes no rows of the holder: it passes the edits on to the process `domain` (N1.3; the reception — [P/08.0](../../08-domain/spec/08.0-domain.norms.md)
N1.8), the rights of `domainconsole` are reading `domain/*` ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) N1.4). The family
of witness objects `<sub>/<manifest:domain.witness.report>/<name>` belongs to this lesson by protocol (N1.8 `witness`; the decision of
the Architect on the move plans of 8–10, item 8): the worker of the subsystem (a participant) writes it, the agent carries it in the report; the domain console
reads witnesses only from the reports of members (`domain/members/<member>/reports/<rev>`; the holder is a member too, with its own agent),
the family has no schema in `data/` (the form is the declaration `domain.witness` of the manifest, [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md)).

What each door reads: the view, the shadow report, the list of members, the topology, the placements, the grants, the shared document — the read doors
N1.2 (the forms of the rows are in their chapters of lesson P/08); `domain/keys`, `domain/root`, `domain/revoked`, `domain/disabled`,
`domain/grants/<cluster>`, `domain/roles/<name>`, `domain/groups/<name>` — the gate (N1.5; the keys and the token — [the domain token contract](../../common/contracts/domain-token.md),
`may` — [the right contract](../../common/contracts/may.md)); `domain/member-rows/<part>` and the rows
`domain/members/<member>/ca-certs` — the role door (N1.4 `server.role`; the domain console does not read the copy `domain/member-list/<part>` — review analysis of stage B 8–10, question 4); `domain/<sub>/worker` and the heartbeat `domain/<sub>/heartbeat` —
`door.pass` on the domain (N1.6); the member's report, the mark `reported` (`received_at`, `sent_at`), the history and `domain/member-rows/<part>` — the alarm
list (N1.8); the manifest rows and `platform/schema` — the start (N1.1); the key of the server certificate of the role `domainconsole` — the role door
of TLS. The role journal is `audit/domainconsole`, the alarm `session.debug_open` (a debug identity, N1.5) — `audit.alarms/domainconsole`
([the event journal contract](../../common/contracts/event-journal.md), participant `append`, owner — P/05). The lines «journal»
of the role door — the transition of the trust set into unreadable and back (the role certificate contract, class `role`, `unreadable`;
C10-ROLE-LOG-C47) and a service without a kit (`no_kit`) — are a diagnostic of the process (stderr), not events of `audit/domainconsole`:
there are no kinds for them and new ones are not introduced, the text is the implementation's, acceptance does not compare it (C10-ROLE-LOG-DIAG-01).

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R003

old-sha256: de868c65e093bdacfa735399e28f7aaa8fbcc23fa9aa1e973ffc392ae8a3b6f3

<!-- req: P/10-R003 -->
### N1.1 The process and the start (M11/12 N1.8; P/02.4 N1.12)

The domain console is the process `domainconsole` at the holder cluster, next to the process `domain`: the unit
`w2c-domainconsole.service`, the role `domainconsole`, the implicit address defaults of `DOMAIN_CONSOLE_HOST/PORT` from [daemon-flags.tsv](../forms/daemon-flags.tsv) — only with a role kit, TLS — by the kit (ADR-0075 addendum of 2026-10-26 (2) item 4; [P/02.4 N1.12](../../02-installer/spec/02.4-installer.norms.md)).
Like the processes of the platform, it executes the reader's side of the manifest row ([P/02.3](../../02-installer/spec/02.3-installer.norms.md)
N3 «Process start», «Manifest change»): it has no built-in manifest, steps 0–4 of «Process start» are as there: step 0 is
the schema check against `SCHEMA` of the platform build ([the schema contract](../../common/contracts/schema.md) «Check at start»);
step 1 — the whole catalogue; step 2 — only `sha256` of the row (there are no built-in bytes to compare with); then the environment, the kit
of TLS, the port (the Architect's decision of 2026-10-25, C10-START83); readiness is the port, it does not send `sd_notify` (the text is P/02.4 N1.12, from M11/12 N1.8; here it is
the domain console part, P/10-15). The process environment is projected by [daemon-flags.tsv](../forms/daemon-flags.tsv) with the [form grammar](../forms/README.md#inputs-and-constants); the launcher and imported contextual contracts remain mandatory. The environment, the exit codes and the unit are in the [life cycle](../lifecycle.md).

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R004

old-sha256: 379fb833692f188f4c40aa6d682501a9dd7b4bf26753b7c7edef3987ae2be83c

<!-- req: P/10-R004 -->
### N1.2 The read doors — it answers itself

The parsing of a request is [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Request parsing and the order of checks»
(P/01.1 N2.1 with the deviations of the console; the layout audit B-09); there are no deviations of its own. The identity and the grants are N1.5 (`view` for reading by `domain/grants/domain`; the view doors — «Judgement by target» of [the right contract](../../common/contracts/may.md)). Each
door is a row of the list of domain doors of [the forwarding contract](../../common/contracts/forwarding.md) «Domain doors»; a row with `GET`
also covers `HEAD` of the same path — the same code and headers without a body (ibid.; P/06.5 N2).

**The row version at the read doors** ([P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.9 «Versions»; ADR-0094 B4). The doors of one row — `GET /domain/members/<member>`, `GET /domain/topology`, `GET /domain/placement/<sub>/<ref>`, `GET /domain/shared` — serve an `ETag`: the index of this row (for the shared document — of the pointer) in double quotes, from the same read as the value. There is no row — the answer is without `ETag`: the condition has nothing to judge about.
`GET /domain/placement` carries `index` in each record, `GET /domain/grants` — the field `versions`: the index and `revision` stand by the row, because the answer has many rows. The values are fit for `If-Match` of the edit doors that the console passes on to the process (N1.3).

**N1.2a The view (M11/1 N2, N4).** The doors are at the domain console; the cluster console forwards them without rewriting:

| Door | Success | Refusals |
|---|---|---|
| GET `/domain[?cursor=]` | the answer is the head of `domain/view` and the non-empty parts in a row up to DOMAIN_PAGE_MEMBERS members, the fields `members`, `units`, `contested`, `reports`, `pending`, `outcomes` — a merge of the rows, `cursor` — the next page, `unread` — the unread parts; a small domain — one page (P/08.1 N1.4b); for a non-viewer of the domain (the right contract `wide`) — only `as_of`, `holder`, `complete`, `members` (`servers` and `url` — only for the clusters where it has a row), `units` by record, `outcomes` — the outcomes where `by` is itself, `contested` — the refs whose cluster it sees, `age`, `url`, `withheld: <count>`; otherwise 200 — the object `domain/view` ([P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.4) as is plus `age` — seconds since `as_of` by the wall clock of the console, `max(0, now − as_of)` (a clock gone back — 0; C10-AGE-NONNEG-01), one digit after the point; the field `url` of the view that does not read (not a string) is `null` in the answer (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 53 of the list) | 404 `{error: "no domain here", detail}` — there is no object; the object exists but does not read — 503 `{error: "unavailable"}`, not 404 (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list); 401/403 — N1.5 |
| GET `/domain/<sub>/<rows>[?cluster=<member>][&cursor=]`, `/domain/<sub>/<rows>?part=<part>` | 200 — `[Unit]` of the subsystem from the rows of the view, page by page by the header `X-Cursor`, with `cluster` — this member’s entire row in its one part, one page: `cursor` is not read, including an invalid opaque cursor, and there is no `X-Cursor`; with `part` — the units of one row `domain/view-rows/<part>`, one read and one page, `cursor` is not read, there is no `X-Cursor`, no row — `[]` (the part — P/08.3 N1.1; ADR-0113 addendum (22)); for a non-viewer of the domain — only the records it sees, `X-Withheld: <count>`, if some are hidden because of the unread (`unavailable`) | in order: 400 — `cluster` or `part` twice or empty ([P/06.5](../../06-console/spec/06.5-console.norms.md) N2), `part` not by the grammar of a part, `cluster` and `part` together; 404 — there is no such manifest; 404 `{error: "not in the directory"}` — the manifest has no `domain.ref`; 404 — `rows` is not its own; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list); 404 `{error: "no such member"}` — the member is not in the list; other parameters are not read |
| GET `/domain/<sub>/kept/<name>` | 200 `{items, index}` of the row `domain/<sub>/<name>`, `<name>` — an element of `domain.kept_read` of the manifest; the mask of [P/06.2](../../06-console/spec/06.2-console.norms.md) N1.4: an element with the name `*_secret` and a field `*_secret` at any depth of the value parsed as JSON, an envelope `enc:` — `"***"`, a value that is not JSON — as is; the domain console answers itself; the right is `view` of the domain (`wide`), judged first: a non-viewer does not tell «not declared» from «not allowed» | 401, 403 — before everything; 404 `{error: "no such path"}` — `<name>` is not declared or there is no row; 503 `{error: "unavailable"}` — does not read |
| GET `/domain/relays/<relay>` | 200 `{relay, rev, members}` of the row `domain/relay-members/<relay>` (P/08.3 N1.2): `members` — names in ascending order, up to RELAY_MEMBERS_MAX ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2, [owner form](../../08-domain/forms/runtime-constants.tsv)), the member keys do not go; there is no row — `rev` 0, `members: []`; the domain console answers itself; the right is `view` of the domain (`wide`), judged first | 401, 403 — before everything; 404 `{error: "no such member"}` — there is no such member; 503 `{error: "unavailable"}` — the row does not read or exceeds its owner limit; never truncate |
| GET `/domain/<sub>/tables/<table>?cluster=<member>` | 200 — `{cluster, ts, rows}`, the object P/08.1 N1.4a of this member as is, for a non-viewer of the domain — only the visible rows and `X-Withheld`; `ETag` — sha256 of the served body, separate for each answer, `If-None-Match` — 304: reading the list of members is cheap; one member per request: the object is bounded by P/04 N1.3b, there is no list of all (ADR-0110) | in order: 400 — `cluster` is absent, twice or empty; 404 — there is no such manifest; 404 — `<table>` is not a key of `domain.view_tables`; 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read; 404 `{error: "no such member"}` — the member is not in the list; 404 `{error: "not reported yet"}` — there is no object; 503 `{error: "unavailable"}` — the object does not read; other parameters are not read |
| GET `/domain/shadow` | 200 — the shadow report (P/08.1 N1.6) of the last pass | 404 `{error: "no domain here"}` — there is no report; the report exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, P1; line 54 of the list) |
| GET `/domain/folders`, `/domain/folders/<id>/units[?cursor=&limit=]`, `/domain/memberof/<member>/<sub>/<rows>/<id>` | Own domain-console read doors by [P/08.5 N1.8](../../08-domain/spec/08.5-domain.norms.md): forms, pagination, visibility and check budget remain with that owner | N1.5 before reads; bad cursor — 400 `{error: "refused"}`, no folder — 404 `{error: "no such path"}`; unreadable source — 503 `{error: "unavailable"}` |

**Pagination of `GET /domain` (G10-PAGE-CURSOR-01).** The limit is hard: at most DOMAIN_PAGE_MEMBERS elements of `members` per page. A part is the writer's storage/work unit, not an indivisible HTTP page; a readable part with more than DOMAIN_PAGE_MEMBERS members is split at a member boundary. Visit the non-empty parts in ascending order of their four-digit names (0000…4095), and the members inside each part by name in UTF-8 byte order. Select up to the remaining page budget, then continue inside this part on the next request if needed. Each returned page's `members` is itself ordered by name; its last displayed element need not identify the last visited part.

The request without cursor starts the traversal. The returned cursor is an opaque string carrying sufficient continuation state, such as the current part and last visited member. Its encoding is the implementation's; clients return the issued token unchanged as the query value. The cursor continues after the selected members, including within a part, and is omitted at the end. On unchanged readable data, following all pages returns every member exactly once, without a skip or a repeat. The API promises ordinary reads, not a new snapshot spanning concurrent changes.

The page projects the six per-member fields: `members` contains the selected members; `units` keeps Unit records whose cluster is selected; `reports`, `pending` and `outcomes` keep selected member keys. Preserve the view's required empty subsystem keys. A contested ref is a complete conflict fact: keep a ref that has a selected claimant, with its entire original claimant list, never truncate that list at the page boundary. Names used as this context are not additional MemberState elements of the page. A conflict can therefore appear on more than one page, while the members themselves do not repeat. The head's global fields stay global. Existing visibility filtering and the unread/incomplete rules still apply; pagination alone does not change the holder's round completeness.

Examples on fixed data: one part with 1001 members gives pages of 1000 and 1; consecutive parts with 999 and 2 give pages of 1000 and 1, continuing inside the second part. A conflict between members on opposite sides of that boundary keeps both claimant names wherever that conflict is included. No part-size bound is added to P/08.1 N1.4b.

**N1.2b Members (M11/3 N2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/members/<member>` | the domain console (`domainconsole`) | 200 `{part, rev, term, entry}` of the row of the part of this name and `ETag`: the version for `If-Match` of the edit doors | 404 not a member; 503 does not read |
| POST, GET `/domain/batches`, DELETE `/domain/batches/<name>` | the domain console → the process `domain` ([chapter 8.0](../../08-domain/spec/08.0-domain.norms.md)) | the request, response bodies and status codes of [the P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml) and [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.1b, served as received; the POST token is shown once, GET omits it | 400 not by the form; 404 there is no batch; 409 such a batch exists; N1.9 — the right `admin` of the domain |
| GET `/domain/members[?cursor=]` | the domain console (`domainconsole`) | 200 `{members, parts, knocking, count, cursor?}`: the non-empty parts in a row, up to DOMAIN_PAGE_MEMBERS members, a small domain — one page; `parts` — `{<part>: {rev, term, index}}`; `index` is the exact nonempty string Row.index of the store row read, never a JSON number or a binary64 conversion ([P/01.1](../../01-store/spec/01.1-store.norms.md) N1 Version); `members` — a merge of the doc of the rows read by the door; `count` — `domain/member-count`, absent — no field; `knocking` — on the first page `view.knocking`, on each — `domain/knocks/<part>` of the parts of the page (the memory knock exists only in the view, [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md) N1.7), the field is absent in a readable view — `[]` (the field is optional, nobody is knocking; like a view without `shared`, C10-MEMBERS-KNOCKING-ABSENT-01); `member_list` of the view is not substituted (C10-MEMBERS-SOURCE-01) | 404 `no domain here` (there is no view; there is no row `domain/member-rows/<part>` with a readable view — the list exists from the first start of the holder, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N3 «the holder in the list», C10-MEMBERS-SOURCE-01); the row `domain/member-rows/<part>` or the view exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 36 of the list); 401/403 — N1.5 |

The grant `admin` for editing the list and `view` for reading are N1.5; the console passes the edits of the list on to the process (N1.3; their norms are
[chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N2).

**N1.2c Topology (M11/4 N2).**

| Door | Who answers | Success | Refusals |
|---|---|---|---|
| GET `/domain/topology` | the domain console | 200 doc ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2) — from the row `domain/topology`, not from the view: right after a PUT — the new `rev` (reconciliation of M11, T1) | 404 `no domain here` — the view is not built (N4); there is no row `domain/topology` — not a refusal: 200 `{rev: 0, star: [], via: {}}` (P/08.3 N1.2: rev 0 — «never written», no row — the same; C10-TOPOLOGY-ABSENT-01); the row `domain/topology` exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 50 of the list); 401/403 — N1.5 |

**N1.2d Placements (M11/6 N2).** The doors are the domain console's; the member console forwards them (the forwarding contract «Domain doors»):

| Door | Success | Refusals |
|---|---|---|
| GET `/domain/placement` | 200 `{rev, records: {"<sub>/<ref>": Placement with index}}`; there is no row `domain/placement` — `rev` 0 (there is no counter yet, [P/08.6](../../08-domain/spec/08.6-domain.norms.md) N1.2 `absent`), `records` — as always (C10-PLACEMENT-ABSENT-01) | the row `domain/placement` (the counter `rev`) exists but does not read — 503 `{error: "unavailable"}` (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 43 of the list); 401/403 — N1.5 |
| GET `/domain/placement/<sub>/<ref>` | 200 Placement | 404 there is no record; the record exists but does not read — 503 `{error: "unavailable"}`, not 404 (V7 item 3, the Architect's decision of 2026-10-28, on the proposal; line 42 of the list); 404 there is no manifest or it is without `domain.ref` |

The form `Placement` and the counter are [chapter 8.6](../../08-domain/spec/08.6-domain.norms.md) N1.1; the console passes the edits of placements
on to the process (N1.3).

**N1.2e Grants (M11/9 N2).**

| Door | Who | Right | Success | Refusals |
|---|---|---|---|---|
| GET `/domain/grants` | the domain console | view; to a non-viewer of the domain — only the clusters where it has `admin` on `*` (the right contract `target`, ADR-0110 D-1), none — 403 | 200 `{grants: {<cluster>: [line…]}, versions: {<cluster>: {revision, index}}}` | 401/403 |

The grant line `line` is [chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) N1.3; the console passes the edit `PUT /domain/grants/<cluster>`
on to the process (N1.3).

**N1.2f The shared document (M11/11 N1.6 `door`).**

```yaml
door:          GET /domain/shared at the domain console (view) → 200 {doc, delivery, declared}; there is no view (domain/view) — 404
               {error: "no domain here"}, like the other read doors without a view (N1.2a); the view exists but does not read — 503
               {error: "unavailable"} (P1; line 54 of the list; C10-SHARED-NOVIEW-01); the pointer domain/shared or its document
               exists but does not read (not by the form, not with the sha256 of the pointer) — 503 {error: "unavailable"}, not doc: null (the outcomes
               of the families shared, shared-docs)
  doc:         the document as signed (an object) | null
  delivery:    view.shared — an x-opaque field: the console does not judge the form of the delivery (the form is the writer's, the process domain, P/08.9
               N1.6), it serves a non-empty object as is, by value (C10-SHARED-OPAQUE-COPY-01); no field or {} — 200,
               delivery = before (P/08.9 N1.6) by the view: term 0, rev 0, holding [], behind {}, refused {}, silent — the members
               of the view not ok, sentence «rev 0 on 0 of T members» (T — the members of the view) with the tails of before; null in term and rev is not
               written (C10-SHARED-EMPTY-DELIVERY-01)
  declared:    {<sub>: [{name, type, schema?}]} — the elements domain.shared of the manifests of the catalogue, by name; schema — at the document
               (CONSOLE-MODULE.md §10a, added by M11/11; the late layer P/07 N1.6)
```

The document and the pointer are [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.2; `view.shared` is chapter 8.9 N1.6; the declaration
`domain.shared` is [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md). The console passes the edit `PUT /domain/shared` on
to the process (N1.3; the execution — chapter 8.9 N1.3).

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R005

old-sha256: 6a1149b57f7f0bf161c67164f6fdb03b59f8f55e976fffbac62bbb6de29ac62b

<!-- req: P/10-R005 -->
### N1.3 Passing on to the process `domain` (M11/3 N1.8 `console`, `pass`; M11/9 N1.9 `pass`)

The reception of the passing, `writer` and `answers` are [P/08.0 N1.8](../../08-domain/spec/08.0-domain.norms.md) (P/08.0-01); here is the side
of the domain console.

```yaml
console:   the domain console is a door: it checks the identity and the grant (the gate, N1.5) and passes the edit on; it has no records of its own in
           the rows of the holder (the rights of domainconsole are reading, P/02.5 N1.4)
pass:      every door /domain/* of the domain console, except GET and HEAD and except door.pass to the worker on the domain (N1.6), and
           POST /api/login (P/08.4 N1.2); the people doors of P/08.4 N1.9 (/domain/users…, /domain/break-glass…) — with any
           method, GET too (review analysis of stage A 8–10, № 2), and GET/HEAD /domain/batches and GET/HEAD /domain/<sub>/books/<book>/*/<part> —
           to the process domain (SIGNER_URL of its own box; to https:// — the client of its own cluster, the role certificate contract
           own_client, role domain): the method, the path with query, the body, Authorization, Idempotency-Key, If-Match
           as they came, except the first cookie transition under the forwarding contract «First cookie transition to the domain»; X-W2C-Client — the address of the client's TCP peer: the domain console sets it; when, whom the process trusts and what
           is stripped outside — the forwarding contract Platform/common/contracts/forwarding.md «Client address» (review analysis
           of stage A 8–10, № 23; the history is there too: reconciliation of M11, cammeta-python M11-09 № 22, P16); the deadline is «Wait» of the row
           of the forwarding contract Platform/common/contracts/forwarding.md «Domain doors»; the answer is as it came, without parsing
           (the forwarding contract «Forwarding is one function» answer: 502 on a break and on silence); the process checks
           the identity and the grant itself (P/08.4 N1.5) and executes N3 of the door
```

The doors that the console
passes on are the rows of the list of domain doors of the forwarding contract «Domain doors», except its own read doors (N1.2), the alarm list
(N1.8) and `door.pass` (N1.6); their norms and answers are the chapters of lesson P/08 by door ([P/08.0](../../08-domain/spec/08.0-domain.norms.md)
N2, the summary table). The console serves the answer of the process as it came — `409 deposed`, `503 frozen`, `503 standby` too: it does not
recompute them (P/08.0 N1.8 `answers`; the forwarding contract «Refusals by transition», transition 3).

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R009

old-sha256: c2a827542b8a55c636d39568859b0128403e0748ff2125ca4fd96e78892d8e78

<!-- req: P/10-R009 -->
### N1.6 `door.pass` on the domain (M11/8 N1.7)

```yaml
route:    /domain/<sub>/<segment>[/…], <segment> ∈ door.pass of the manifest <sub> (P/06.5 N1.8) — the domain console passes on to the worker
          on the domain of this subsystem (P/03.7 N1.6: the holder of the slot domain/<sub>/worker, role <sub>domain) the path
          /<segment>[/…] and query; the headers, the body, the answer, the codes — the gate-and-pass contract «Pass of `door.pass`» (review analysis
          of stage A 8–10, № 14); the client is of the role domainconsole; a path with
          a segment `.`/`..` is not passed to the worker — 404 not a domain route (the forwarding contract «Domain doors»; added by the reconciliation of M11, D4)
address:  the url of the heartbeat of the worker on the domain — the object domain/<sub>/heartbeat (P/03.7 N1.6 heartbeat)
holder:   the console reads the slot domain/<sub>/worker only as «a holder exists»: holder is non-empty and released = false (the slot
          contract «States»); there is no holder — «not heard» (absent below); freshness is only the heartbeat (LOST_AFTER, P/03.7 N1.6
          heartbeat); the console does not judge whether the instance of the heartbeat matches the holder of the slot or the age of the slot version (SLOT_TERM) —
          the validity of the operation is checked by the worker with its credentials and epoch, as at the cluster console (P/06.5
          N1.8) (C10-PASS-SLOT-01)
absent:   the worker on the domain of this subsystem is not heard — 503 {error: "unavailable", detail: "no worker of <sub> with a
          door is heard"} (the words of the gate-and-pass contract, codes)
member:   the cluster console forwards these paths to the domain console by a row of the list of domain doors of the forwarding contract
```

The matching rule (`books`, `placement`, `members`, `topology`, `shadow`, `at` are not passed on on the domain) is the forwarding
contract «Domain doors». What the worker on the domain checks at an arrived route is [P/03.7](../../03-worker/spec/03.7-worker.norms.md)
N1.6; the console passes `Authorization` on as it came (the move plan of lesson 10, V13).

**The second kind of `door.pass` on the domain** (ADR-0094 B1, addendum (3) item 1; [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Pass of the second kind»). The domain console passes a manifest with the second kind on in the same way: a ticket instead of `Authorization`, the headers, the answer types, `refusals`, the stream. The ticket is issued by an instance of the domain console, which remembers `jti`, `kid`, `exp` of the human's token; `user`, the closing of the request and the closing of the stream on a revocation of `jti`, on disabling the human and at `exp` — by the contract. The token is checked by the domain token contract, and the grants — by `domain/grants/domain` (N1.5). The client to the worker is of the role `domainconsole`, the addressee is the role `<sub>domain`. There is no callback on the domain yet: the closed list of [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.9 names no doors `/domain/*`, therefore the domain console accepts the header `X-W2C-Pass-Ticket` only for a refusal, 401; the doors will enter the list with the increment of rights (ADR-0094 addendum (11)).

**All forwarding hops.** The [domain worker pass hop policy](../../common/contracts/forwarding.md#domain-worker-pass-hop-policy) is mandatory at every console on this path, including the holder and member consoles: confirmed-policy digest, finite waits including downstream execution, and the finite-buffer and stream rules of that policy. A mismatch returns 503 without calling the worker. After exposing client headers a break propagates bytes and closure, never a new `502` body. Ordinary platform routes retain their normal limits.

**Callback address header (G10-PASS-CALL-URL-01).** In this pass, the outgoing `X-W2C-Pass-Console` is absent, with or without a role kit. The same header received from outside is removed by `to_worker` of the gate-and-pass contract. `CONSOLE_CALL_PORT` names the callback listener of the cluster console; neither that URL nor the main `DOMAIN_CONSOLE_HOST/PORT` address is a callback address of this domain-console instance. The ticket remains bound to the open request in memory by the contract above; an incoming `X-W2C-Pass-Ticket` at the domain console is refused with 401 as above.

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R011

old-sha256: 47c9681eba433410912181f7542463815359872de0e0433ed956778bbd6d1252

<!-- req: P/10-R011 -->
### N1.8 The alarm list at the holder (M11/11 N1.8)

The console assembles the alarms of members from their reports: it opens no connections to a member. The history (chapter 8.9 N1.9) is written only by
the process `domain`; the list only reads it. The Architect's decision on the questions of M11/11; the function `alarms` and its vector belong to this
lesson (the Architect's decision on the review analysis of stage A 8–10, № 8).

```yaml
door:          GET /domain/alarms?since=&until= at the domain console (view); the default is ALARMS_WINDOW before now; not finite numbers or
               since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}; the time is by the
               grammar of the reader time of the row codec after URL decoding (the gate-and-pass contract
               «Numeric query parameters»: 1e3, -1, «+», «_», a space — a refusal; the detail of the refusal is its own, above;
               C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27), the parameter is not repeated (added by the reconciliation of
               M11, A12)
answer:        200 {since, until, events, members, complete, sentence} — the function alarms (N3) on the page of the last report
               of each member of the list (the holder included), on the history (P/08.9 N1.9) and on the witnesses
member_state:  ok | silent | not_reporting | never | unreadable
  silent:      the last report is older than this member's silent_after (the observation contract «Freshness»): server — LOST_AFTER,
               camera — 3 × every of its readable confirmed mark (absent every — REPORT_EVERY, by the report reception contract); retry_in is not used here;
               silent_since = last_report + the same silent_after
  not_reporting: silent, and a witness heard a unit of the member later than the last report
  never:       there has never been a report
  unreadable:  the page is not by the form of P/09.1 N1.10 (at the function alarms — the input "garbled" too)
silence_line:  a silent member — an alarm row {t: silent_since, kind: silent | not_reporting, class: alarm, member,
               subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?} — always, while it is silent
witness:       domain.witness {report, member_field} (P/02.1 N1.2b): the objects <sub>/<report>/<name> = {ts, cluster, units: {<member>:
               seconds since the last time}} at the clusters and in the reports; the family is the keys <sub>/<report>/<name> (the name after «/»), the agent
               carries each object of the family as a report object (P/09.1 N1.2 member_objects), the object <sub>/<report> without a name is
               not a witness (added by the reconciliation of M11, A2; the agent's side — P/09.1 N1.10); member_field — the fixed field of the unit that carries the name of the member
               (the load refusal — P/02.1 N1.2b); alive_at = ts − units[member], alive_via = "<cluster>/<name>"; there are several witnesses —
               the largest alive_at among those later than last_report; on a tie — the smaller alive_via in UTF-8 bytes
               (added by the reconciliation of M11, A17); ts in the worker object is its wall time. Before computing alive_at and choosing
               or breaking a tie, the collector shifts ts by received_at − sent_at of the same confirmed report that supplied this witness.
               It never uses the mark of the member being witnessed, the current clock offset or another report
clock:         the domain clock of the alarm rows — [the alarm history contract](../../common/contracts/alarm-history.md) «Domain clock» (moved there
               without a change; the layout audit, the Architect's decision of 2026-10-25, A-13)
events_order:  by t descending, then member, id; the rows of the history — from_history: true
```

The member's alarm page and its front are [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.10; the mark `reported` —
[chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.3; the history — chapter 8.9 N1.9 (`same_line`, `cut_before`).

---

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R014

old-sha256: 55c48fb6d136a7c6f33ceaa9fea79f444405308a1de1608f65b7ac66dcb78721

<!-- req: P/10-R014 -->
### alarms(input) (M11/11 N3)

The filter is at the door, the form is at the function: the alarm door assembles the input from the store and discards a broken witness (without ts and the like)
with a counter before the call — resilience; the vector alarms receives an already assembled input, and a witness not by the form in
it is an input not by the form, code 2 (H14). One does not contradict the other (added by the reconciliation of M11, cammeta-python M11-11 № 20).
A mark `domain/members/<member>/reported` whose read the store did not confirm — 503 `unavailable` of the whole door; a mark
read but not by the form — the member enters the function with `reported: "garbled"` (C10-REPORTED-OUTCOME-1D6, the Architect's decision of 2026-10-25).
The input is assembled from the store of the holder (C10-ALARMS-INPUT-01): `last_report` is `received_at` of the mark, `received_at` and
`sent_at` are the fields of the last request of the mark ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.3; the domain clock), not
the age of the console's observation; the members are the row `domain/member-rows/<part>`: there is none — 404 `no domain here` (like `GET /domain/members`,
N1.2b), it does not read or the read is not confirmed — 503 `unavailable` of the whole door, not an empty list; the mark is read, and
the generation `reports/<rev>` of the mark does not exist or it is not with its `sha256` — `page: "garbled"` (the member is `unreadable`, the witnesses of this
report are not taken), not `page: null`: «no page» is only for a readable generation without a page.
The collector always supplies each member's `silent_after` from its accepted Entry class and confirmed mark as in N1.8. For an accepted Entry of class camera, confirmed absence of the mark or a confirmed whole unreadable mark supplies `silent_after = 3 * REPORT_EVERY` from the existing report-period owner. The collector does not read `every` partially from a rejected mark, use a cache, substitute server `LOST_AFTER`, or omit the field. This completes the input form: confirmed absence remains `never`; a whole unreadable mark remains `unreadable` at 200 without silence/page, known_until or silent_since; an unconfirmed read remains 503 `unavailable` of the whole door. It normalizes each witness's `ts` using the originating report's offset before passing it to the function; the native input's witness `ts` is already domain time. The function must not shift it again.

```
input:  {now, since, until, lost_after, members: {<member>: {last_report: <domain clock> | null, received_at, sent_at, page: <P/09.1 N1.10> |
         "garbled" | null, history: <P/08.9 N1.9> | null, silent_after} | {reported: "garbled", page?, history?, silent_after}}, witnesses: [{sub, name, ts, cluster, units}]}
silent_after: a required finite positive JSON number in either member form. The function infers no Entry class from its input.
   Validate the complete known input, including this field, before the steps; a missing or malformed value is code 2,
   even on reported = "garbled". There is no fallback to lost_after.
1. each member:
   reported = "garbled" (the mark is read, not by the form) → unreadable; there are no silence row and no page rows of this member,
                                                        no known_until and no silent_since (C10-REPORTED-OUTCOME-1D6, the Architect's decision of 2026-10-25)
   no last_report and no page                         → never
   no last_report, but a page                         → an input not by the form (code 2): a page comes only with a report
   page = "garbled" or not by the form of P/09.1 N1.10 → unreadable; not by the form is also a row without id, class ≠ alarm, kind
                                                        empty, unit not a string, from > to (added by the reconciliation of M11, A15)
   now − last_report > silent_after → silent; a witness with ts − units[member] > last_report — not_reporting
   otherwise                                          → ok
   page = null with last_report — there is no page: there are no page rows, not unreadable
2. rows: the page (the clock of N1.8 clock) ∪ the history (from_history, t as stored) without repeats by same_line — present in both,
   the page row is taken; a repeat inside one page — the first in the order of the page (reconciliation of M11, A16); the silence row — N1.8 silence_line; the window [since, until] — for all rows, the silence
   row too
3. members: {<member>: {state, truncated?, known_until?, silent_since?, alive_at?, alive_via?, history_cut_before?}};
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

**Races.** A member without a connection and an alarm storm — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N3 «Races».

---

### `Platform/10-domain-console/spec/10-domain-console.norms.md` P/10-R016

old-sha256: c4a589d8831e24a00d90859999a25b4e4830561e45cdc0f5f7a336d384212281

<!-- req: P/10-R016 -->
## N5 Acceptance

The catalogue [`acceptance/`](../acceptance/README.md): the stand of several clusters of chapter 8.3 (`hold`, `m1`, `m2`, the catalogue
`testsub`), scenarios 02 (from M11/11) and 05 (from M11/08) — the numbers and steps are the former ones; 06–09 — the coverage audit of P/10 (audit-kimi
290ae7697); 10–16 — its second pass (audit-coverage-gemini 798e11a44); 17 — ADR-0094 B4; 18, 19 — the `kept` and relay doors (new scenarios of 2026-11-02, `corrections.tsv` (historical correction record)). The alarm list is the vector
[`vectors/alarms`](../vectors/alarms/README.md) (37 rows: 15 — the former sc. 04 of the acceptance of M11/11; 16 — C10-REPORTED-OUTCOME-1D6; 17–27 — the second pass of the coverage audit; 28–35 — review C1; 36–37 — missing required silent_after).

```yaml
alarms:    the input — N3 alarms; the output {events, members, complete, sentence}
exit:      0 — computed; 2 — an input not by the form (the rows alarms-15, alarms-17…23, alarms-31…37 — @exit 2: lost_after, a member name, page without
           last_report, sent_at null at a member with a report, history with cut_before null, a witness without ts, reported together with last_report,
           an extra field, a missing or malformed silent_after in either member form; the other cases — by reading; a page [], from > to, a row without id — 0 unreadable, the rows alarms-24…26); the exit codes are by the principle of «Domain stand» of the common README of acceptance («Exit codes of vector commands»: 2 — the form of a trusted input, 0 with a word — a document of another cluster; the Architect's decision on the reconciliation of M11, H14).
           Not by the form at alarms: a member name not by the member grammar, lost_after not > 0, silent_after absent or not a finite positive number (boolean and null are not numbers), a history or a witness not by the form of P/08.9 N1.9
           and N1.8 (a history without cut_before or with cut_before null — too, P/08.9 N1.9 A13), a page object without received_at and sent_at,
           no received_at or sent_at at a member with a report, a history as a string, a witness without ts, witnesses not a list, now not
           a number, an extra field; reported — not "garbled", or together with last_report, received_at, sent_at (C10-REPORTED-OUTCOME-1D6);
           a page that is not an object ([], a number) or not by the form of P/09.1 N1.10 — 0 unreadable, not 2; page null with
           last_report, received_at and sent_at null at never — 0
```

| № | Scenario | Norms |
|---|---|---|
| 02 | stand: the agent `m2` is turned off — `silent` in the delivery, the alarm row `silent` in `/domain/alarms`; a window not by the grammar and `since > until` — 400; it came back — took the document | N1.8; steps 04, 09 (delivery) — N1.2f; step 11 (the agent signature at `/events` of the member console) — a neighbour on the stand |
| 05 | stand: the holder's page — `/`, the module, `/manifest`, `/mounts`, `/session` with `server_time`, `timezone` | N1.7 |
| 06 | `no-domain-here` (the coverage audit of P/10, K01): the domain is not installed — the gate is `open`, there is no view; `GET /domain`, `/domain/shadow`, `/domain/members`, `/domain/topology`, `/domain/shared`, `/domain/testsub/counters` — 404 `no domain here` | N1.2a, N1.2b, N1.2c, N1.2f; N4 |
| 07 | `view-unreadable` (the coverage audit of P/10, K01): the process `domain` is stopped, the view is spoiled — 503 `unavailable`, not 404, at `GET /domain`, `/domain/members`, `/domain/testsub/counters`, `/domain/shared`; the shadow is spoiled — 503 at `/domain/shadow` | N1.2a, N1.2b, N1.2f; N4 |
| 08 | `pass-process-down` (the coverage audit of P/10, K02): the process `domain` is stopped — an edit and a people door (and `GET`) — 502 `did not answer`, its own read door answers; after the return the same edit — `rev: 1` | N1.3 `pass`, N1.3a; N4 |
| 09 | `pass-process-silent` (the coverage audit of P/10, K03): the process `domain` is frozen (`@freeze`) — an edit — 502 `did not answer`; after `@thaw` — `rev: 1` | N1.3 `pass`; N4 |
| 10 | `read-doors-head-and-query` (the second pass, G02): `HEAD /domain`, `/domain/topology` — 200 without a body; `?cluster=` empty or twice — 400; there is no manifest, `rows` is not its own — 404 | N1.2, N1.2a; N4 |
| 11 | `topology-placement-unreadable` (G02): `domain/topology`, the counter `domain/placement`, a placement record not by the form — 503 `unavailable`, not `rev 0` and not 404; the former counter — 200; there is no record or manifest — 404 | N1.2c, N1.2d; N4 |
| 12 | `shared-and-members-unreadable` (G02): the pointer `domain/shared` not by the form — 503, not `doc: null`; the row `domain/member-rows/<part>` not by the form — 503 at `/domain/members` and of the whole door `/domain/alarms` | N1.2b, N1.2f, N3 `alarms`; N4 |
| 13 | `alarms-query-lexemes` (G03): `since`/`until` not by the grammar of `time` (`1e3`, `-1`, `+1`, « 1», `1_000`, `1e10`) — 400 `refused`; `since` twice — 400; `%31` — accepted | N1.8 `door`; N4 |
| 14 | `alarms-mark-unreadable` (G03): the mark `reported` is spoiled — the door 200, the member `unreadable` without `known_until`, `silent_since` | N3 `alarms` |
| 15 | `dot-segments-and-x-user` (G04): without a token a segment `.`/`.%2E` — 404 `not a domain route`, not 401; an arrived `X-User` is stripped — 401, `/session` is anonymous; with a token — the identity from the token, the grants in `/session` | N2, N1.4, N1.5; N4 |
| 16 | `gate-rows-unreadable` (G04): `domain/disabled`, `domain/revoked`, `domain/grants/domain`, `domain/keys` not by the form — 503 `unavailable`, not 401/403; the former value — 200 again | N1.5; N4 |
| 17 | `read-versions` (ADR-0094 B4): `ETag` of the doors of one row; `index` of the records and `versions` of the grants equal the index of the store; `If-Match`, `Idempotency-Key` and `ETag` go through the cluster console and the domain console | N1.2; the forwarding contract `pass`, `answer`; P/08.0 N1.9 |
| 18 | `kept-door`: `GET /domain/<sub>/kept/<name>`: the mask `*_secret` in depth and `enc:`, a family and the undeclared — 404, forwarding at the member console; without an identity 401, a non-viewer 403 also on the undeclared: the right before 404 | N1.2a; P/06.2 N1.4 |
| 19 | `relay-door`: `GET /domain/relays/<relay>`: the names behind the relay without keys, a relay without members — empty, not a member — 404, a non-viewer — 403 also on the undeclared: the right before 404, forwarding at the member console, without an identity 401 | N1.2a; P/08.3 N1.2 |

The doors of the lesson on the stand of the chapters of lesson P/08 are neighbours on the stand (the rule «scenario — in the chapter of its outcome, neighbours — on the stand»,
ADR-0083 addendum (13)):

| Norm | Scenarios |
|---|---|
| P/10-01 | sc. 05 of the acceptance of [chapter 8.3](../../08-domain/acceptance/3/README.md); sc. 06, 09 of the acceptance of [chapter 8.1](../../08-domain/acceptance/1/README.md) (M11/03 sc. 05, 06, 09) |
| P/10-02 | sc. 01, 02 of the acceptance of chapter 8.3 (M11/03); the stands of chapters 8.3 (topology), [8.6](../../08-domain/acceptance/6/README.md), [8.8](../../08-domain/acceptance/8/README.md), [8.9](../../08-domain/acceptance/9/README.md) through `holder` |
| P/10-05, P/10-13 | sc. 01, 02 of the acceptance of [chapter 8.4](../../08-domain/acceptance/4/README.md) (M11/09) |
| P/10-07 | sc. 14 step 6 and sc. 04 step 16 of the acceptance of chapter 8.3; sc. 19 of the acceptance of chapter 8.3 (the source of `members`, `knocking` by default); sc. 02 of the acceptance of chapter 8.8 |
| P/10-08 | sc. 15 step 2 of the acceptance of chapter 8.3 (M11/04 sc. 01) |
| P/10-09 | sc. 01 step 2, sc. 09 step 12 of the acceptance of chapter 8.6; sc. 01 step 7 of the acceptance of chapter 6.7 (review analysis of stage B 8–10, № 22: M-1) |
| P/10-12 | sc. 02, 08 of the acceptance of chapter 8.4 |
| P/10-14 | sc. 01 steps 2, 14 of the acceptance of chapter 8.9; sc. 02 steps 04, 09 of this lesson |

Checked by reading: `door.pass` on the domain (N1.6) — the stand has no worker on the domain; «accept by a console» and the role door
(N1.4) — until the TLS stand; the reader's side of the manifest row at start (N1.1) — the domain console has no step in acceptance (the move plan
of lesson 10, V9: the scenario of a manifest change — by a separate edit of acceptance after the move); the deadline «Wait» of the passing (502 on
silence not earlier than the deadline) and `answer broke off` — acceptance does not measure the answer time and does not break the answer of the process (502 on
a break and on silence — sc. 08, 09); `not in the directory` — the manifests of the stand have `domain.ref`; that the domain console does not recompute `deposed`, `frozen`,
`standby` (N1.3) — the stands of chapters 8.8, 8.10 through `holder`; the role journal — acceptance does not compare the journal; the family of witnesses in
the report (A2); there is no row `domain/placement` (C10-PLACEMENT-ABSENT-01) and there is no row `domain/keys` with a trace of the domain (`shut`) —
the door `admin.sock` cannot remove a row under `domain/` (P/01.2 N1.3 `never`); a generation `reports/<rev>` not by the `sha256`
of the mark (C10-ALARMS-INPUT-01) — the key carries `rev` of the mark, the directive `@spoil object` takes the key as is; `X-Operator: console` at
a proven role — until the TLS stand.

The TLS stand ([`common/acceptance/tls/`](../../common/acceptance/tls/README.md)): the probes of the door `holder` (class `role`) belong to this
lesson, P/10-11: item 2 (9 rows of `holder`), item 7, «change of union» (2 probes), item 8 steps 2–5. The lesson gets the scenarios when
the stand is ready (ADR-0083 addendum (9)).

The machine-readable kit assistance is [stages.tsv](../forms/stages.tsv) and [the CALL seams](../acceptance/seams.tsv), with the port/fixture contract in [forms/README.md](../forms/README.md). This assistance does not replace the ordinary scenarios, vectors, neighbours, the TLS stand or reading of N5.

---

### `Platform/08-domain/spec/08.3-domain.norms.md` P/08.3-R006

old-sha256: 2f1e1a97aadba1f953c932828d9f302a3e070cc4e73d3ea07d5621fa605826e0

<!-- req: P/08.3-R006 -->

```yaml
domain/topology:   {doc: <JCS text>}         # at the holder; writer — the process domain by the door of N2 (chapter 8.0), CAS
  doc:             {rev, centre?, star, relays?, by?, at?}
    rev:           an integer ≥ 0; 0 — «never written» (no row — the same); +1 per write
    centre?:       a member — the centre of the domain: the star relays reach out to it (chapter 8.7; M11/12); in PUT centre "" or null
                   removes the centre, like an empty relay in via (added by the reconciliation of M11, T2)
    star:          [<member>…] — the star relays: nobody reaches them, they take the data from the centre (chapter 8.7;
                   M11/12); ascending, without repeats
    relays?:       [<member>…] — who leads at least one member: the values of Entry.via ascending, none — nobody; the holder keeps it in the same batch as Entry.via, admission and leaving; PUT does not accept the field. Readers — the workers (V/02.9 N1.8): they do not need a summary via
    by?, at?:      who wrote it and when (wall-clock seconds of the console)
  via:             a field of Entry of the part row: the member reports through the relay; no field — it reports directly; via[m] below — Entry.via of the member m. There is no summary via: at this size the topology row does not hold it.
                   The member's copy carries doc and via only of this member: {<member>: <relay>}; GET /domain/topology and the view — doc, via is read from Entry by the list doors
  carry:           in the answer (N1.5) only topology: {at, sha256} — at of the row, sha256 — hex SHA-256 of the JCS of the body {doc, via} of this member;
                   the body — GET /api/topology/<member> at a new sha256: the agent signature and the refusals — as GET /api/anywhere (P/08.4 N1.3), 200 {doc, via},
                   429 busy; doc grows with the domain (relays), and the answer goes on every pass, hence a version and a reference, as anywhere (ADR-0113 addendum (1) item 4, addendum (47) item 3)
  domain/relay-members/<relay>: {rev, members: {<member>: <key>}} — an index, in the same batch as Entry; a row of RELAY_MEMBERS_MAX names, beyond — 409 relay full; reading an over-limit row gives the existing unavailable outcome, without truncation; no row — relay_for is empty, rev 0
  refusals:        (each — as a cause in one refusal 409, joined by «; »; the causes — in the order of this list, within one
                   row — by the name in UTF-8 bytes; a chain — one cause per pair (m, via[m]); via[m] = m — only
                   «through itself», without a chain; added by the reconciliation of M11, T3, T4)
    - a name in centre, star, via (a member or a relay) is not a member of the domain: «<what>: <name> is not a cluster of this domain»
    - star without centre: «a star relay takes its members' data from the centre, and there is no centre»
    - centre in star: «<c> is the centre and cannot be a star relay»
    - the holder in star: «<h> is the domain holder: it reaches the domain in place and is no star relay»
    - a member through itself: «<m> cannot reach the domain through itself»
    - a chain: via[via[m]] exists — «… one relay between a member and the domain»
    - through the holder: «<m> through <h>: that is the domain holder itself»; the holder in via — «<h> is the domain holder:
      it reaches the domain in place, through nobody»
put_order:         PUT /domain/topology in order: the headers and the memory of repeats (chapter 8.0 N1.9) → 400 — the body is out of form, there is neither
                   If-Match nor base_rev, or they differ (chapter 8.0 N1.9 «base_rev») → 503 {error: "unavailable"} —
                   the row exists but is not readable, nothing is written (C08-TOPOLOGY-PUT-UNREADABLE-01) → the revision before the content:
                   If-Match is not equal to the version of the row — 412 revision moved; no header and base_rev ≠ rev — 409 «the topology is at rev N;
                   this edit was made against rev M — look again» → the refusals of refusals in one 409
                   joined by «; » over the merged document: a field not given — the former one; the via of an edit names only the members that change, at most VIA_EDIT_MAX: each has a part row and two indexes, plus the row topology — 61 writes, the limit BATCH_WRITES of P/01.1 64; beyond — 409 «a via edit names at most 20 members: send the rest again»;
                   the named members are judged; the leaving of a member removes it from the index in the same batch, the Entry of a member behind a relay that left lives on, an edit of via removes it (C08-TOPOLOGY-MERGED-01) → one CAS batch: the row topology, the part rows of the named members, the indexes domain/relay-members (at most 10 conflicts; after a conflict the condition again); star is written ascending without repeats; via
                   with an empty relay — the member leaves via; by — the name proven by the gate (P/08.4 N1.5)
home:              the member's nearest door to the domain — via[member], otherwise centre, otherwise the holder (P/08.7 N1.1 `poll_home`); the holder reads Entry.via of the part row of this member
```

The member's copy `domain/member-topology` is the body of `GET /api/topology/<member>` (N1.2 `carry`) as it is, taken at a new `sha256` of the field `topology` of the holder's answer: the agent's side,
[P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.4.

Which road the agent reports by is decided by its environment (`DOMAIN_URL` or `RELAY_URL`), not by the topology; the topology
tells the holder and the relay whom to **accept** through whom. A member whose report came by the wrong road is rejected
(N3 «the holder on POST /api/relay»; the relay door — [chapter 9.2](../../09-agent/spec/09.2-agent.norms.md) N2); a direct report of a member whom the topology leads through
a relay is accepted by the holder — this is the second road (N1.3a).

### `Platform/08-domain/spec/08.6-domain.norms.md` P/08.6-R010

old-sha256: 405efafba308a6c5201f644a7d6d4f3309ae0c7f65a697e99aa5f6bef7c16676

<!-- req: P/08.6-R010 -->

Table edit forms are `components.pathItems.TableEditCollection` and `TableEditItem` of the [owner OpenAPI](08-domain.api.openapi.yaml). Concrete names come only from `domain.edit_tables` of the loaded catalogue; this is separate from the `domain.edit` unit-creation form. After literal substitution remove path parameters on both levels, preserving methods, headers, rights and operation identities.

HTTP contract: [08-domain.api.openapi.yaml](08-domain.api.openapi.yaml). The doors are the domain console's; it passes the edits to
the process `domain` ([chapter 8.0](08.0-domain.norms.md) N1.8; [forwarding contract](../../common/contracts/forwarding.md)); a member's
console forwards them ([forwarding contract](../../common/contracts/forwarding.md)). Request parsing is P/01.1 N2.1 with
the deviations of [P/06.5](../../06-console/spec/06.5-console.norms.md) N2: a body read error (chunked, short, longer,
slow) — 400/413/408 `{detail, error: denied}` by P/06.5 N4 (OpenAPI `BodyRefused`; C08-BODY-DENIED-01); a parsed body not in form —
400 of the rows of this chapter. The read doors `GET /domain/placement`,
`GET /domain/placement/<sub>/<ref>` the domain console does not pass to the process and answers itself — lesson P/10 (N1.2d; the list of doors —
the [forwarding contract](../../common/contracts/forwarding.md) «Domain doors»); the answers of the process `409 deposed`, `503 frozen`, `503 standby` —
the summary table of doors of chapter 8.0 N2.

| Door | Success | Refusals |
|---|---|---|
| PUT `/domain/placement/<sub>/<ref>` `{cluster, origin?, copies?, reason?}` | 200 Placement, `ETag`; the same content — without a new `rev`; `Idempotency-Key` optional (chapter 8.0 N1.9) | in order: 400 an extra field, a field not of its type (`cluster`, `origin` — not a string, `copies` — not a list of strings), no `cluster` or it is empty, `copies` with a repeat or with `cluster`, `ref` not by the grammar (N1.1 ref); 404 no manifest or it is without `domain.ref`; 409 a name is not a member (`cluster`, a non-empty `origin`, each of `copies`), including a name not by the member grammar — it cannot be a member (C08-PLACEMENT-NAME-409-01), such a one — without reading the list; 409 `{error: "refused", detail: "<name> is not a server"}` — `cluster` with Entry class camera (N1.1 class); 503 `unavailable` — the names are by the grammar, but `domain/member-rows/<part>` is unreadable or the read is not confirmed: «not a member» is not judged by it, nothing is written (the outcomes of `domain/member-rows/<part>`, C08-PLACEMENT-ORDER-01); 412 `revision moved`; 503 the counter was not written in 8 attempts |
| DELETE `/domain/placement/<sub>/<ref>` | 200 `{deleted: "<sub>/<ref>"}` | in order: 400 `ref` not by the grammar (N1.1 ref); 404 no manifest or it is without `domain.ref` (N3 step 1 — at DELETE too: the row is not deleted); 404 no record; 412 `revision moved`; an unreadable row is deleted (the outcomes of `domain/placement/<sub>/<ref>`); there are no names — the list of members is not read (C08-PLACEMENT-ORDER-01) |
| POST `/domain/<sub>/<rows>` | 202 kept | N1.3, N1.4; 409 «the pending edits kept changing; ask again» (N3) |
| PUT, DELETE `/domain/<sub>/<rows>/<ref>[?cluster=]` | 202 kept | N1.3, N1.4; 409 «the pending edits kept changing; ask again» (N3); 409 `executors` `{error, detail, clusters}` — ref at two executors and more without `?cluster=` (N3 step 2a; ADR-0091 addendum (15) item 4) |

`ETag`, `If-Match` and `Idempotency-Key` of the assignment doors — [chapter 8.0](08.0-domain.norms.md) N1.9: the `revision` of a record is its `rev`. `rev` is common to all records, so equality guards against any foreign edit of this record and does not guard against edits of other records. A kept edit does not enter the table of N1.9: its key is required, a repeat is `repeat` (N1.4).

---

### `Platform/06-console/spec/06.6-console.norms.md` P/06.6-R004

old-sha256: 4041be74064732de28160277a9ba13071911631dcd349f09eebbae1371642dc7

<!-- req: P/06.6-R004 -->

`platform/schema`, `SCHEMA`, `BUILD`, `schema` and `build` of the heartbeat, `check` are [the schema contract](../../common/contracts/schema.md) «Schema» (moved there without a
change of behaviour; layout audit A-02, the Architect's decision of 2026-10-25). Here — the raise of the schema by the operator:

```yaml
raise:    only the operator, PUT /schema?version=N by N3; back — a refusal; current SCHEMA, unknown-heartbeat and confirmed-read guards, then CAS
```

The sides of the check of the other processes are [P/03.2](../../03-worker/spec/03.2-worker.norms.md) N3 «schema check by the worker»,
[P/04](../../04-controller/spec/04-controller.norms.md) N3 «controller start — schema check»,
[P/05](../../05-resource/spec/05-resource.norms.md) N3 «resource start — schema check».

### `Platform/06-console/spec/06.6-console.norms.md` P/06.6-R011

old-sha256: bf1c00a5484f9cb2c14d1966e594aafa234601e671a5fe1b5ca9d8192b9d62c2

<!-- req: P/06.6-R011 -->

```
1. the string N — only ASCII [1-9][0-9]* whole (without a sign, spaces and a leading zero), the value ≥1 (N2.3)      → otherwise 400 «a version is a whole number from 1»
   If-Match — the form; the condition by the read row — before step 2 (N2.1 «Row version»)
2. the row platform/schema: not a number → 409 «mend the row first»; have > N → 409 «does not go back»
3. its own SCHEMA < N → 409; live processes (the heartbeats changed before the eyes of the reader within the last LOST_AFTER — the observation contract):
   any with an unknown schema → 409 «still running: …»; the read of the heartbeats of this pass is not confirmed
   (a non-answer, including of the listing) → 503 unavailable, no write: it does not decide by memory, not an empty membership
4. write {version: N, at, revision: the read one + 1} with cas; journal schema.raised
```

Step 3: «live» — by [the observation contract](../../common/contracts/observation.md) «Freshness» (review of stage A 6–7,
№ 1: it was «< 45 s» — a change of behaviour at the boundary step; the boundary — the vector [`fresh-age`](../../common/vectors/fresh-age/README.md), review
of stage B 6–7, № 20). The raise is a write: it decides only by the reads of its own pass; the observation memory (`lapse`) is no ground for it — by that memory
a heartbeat ages within LOST_AFTER, the process drops out of the «live» ones, and the raise would pass blindly (C06-PULSE-LAPSE-503-01, the Architect's decision of 2026-10-29).

Two admins are still protected by CAS: the loser re-reads the state and does not announce success.

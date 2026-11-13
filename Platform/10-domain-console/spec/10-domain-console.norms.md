# P/10 — The domain console: norms

This English text is the source; the Russian translation `ru/spec/10-domain-console.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The canon of lesson P/10 «Domain console», module «Platform». Lecture (`ru/10-domain-console.md`, for people, not in the export),
[contract](10-domain-console.api.openapi.yaml), [instructions](10-domain-console.README.md), [life
cycle](../lifecycle.md), [acceptance](../acceptance/README.md). Here is the process `domainconsole` on the holder's box: the door
of the domain operator. The cluster console of the holder forwards `/domain/*` here (transition 2 of [the forwarding
contract](../../common/contracts/forwarding.md); the consoles of members — through it, transition 1); the domain console itself answers the read doors (the view, the shadow report, the members,
the topology, the placements, the grants, the shared document, the alarm list and the function `alarms`), passes on to the process `domain` the edits,
the people doors and the login, serves the holder's page and passes the routes `door.pass` to the worker on the domain; at the entrance it holds the role door
of TLS (`server.role`), «accept by a console» and the gate by `domain/grants/domain`. The process writes no rows of its own.

What is not here and where it is: the content of the view and of the shadow report — [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md); the execution
of edits, the check of the identity and the grant at the process and the answers `deposed`, `frozen`, `standby` — the chapters of lesson
[P/08](../../08-domain/spec/08.0-domain.norms.md) by door (transition 3); the forwarding of the cluster console, its refusals, the doors that
the cluster console answers itself (`/domain/move`, `/api/held`, `/api/backup`, `/api/prepare`, `/api/take`, `/domain/keys`, books,
`at`, `/domain/shared/<sub>`), — chapter P/06.7 of the late layer and [the forwarding contract](../../common/contracts/forwarding.md); the gate
and the passing of `door.pass` as a whole — [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) (owner P/06; this lesson is a
participant); the alarm history — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.9.

## Index

Topics whose rules stand in several places; paths are from the lesson root unless they start with `Platform/`.

| Topic | Requirements | Files |
|---|---|---|
| `common_obligations` common operating obligations and marker confirmation | P/10-R002, P/10-R022 | `Platform/common/contracts/production-obligations.md` |
| `process_start` process and start | P/10-R003, P/10-R047, P/10-R050, P/10-R052 | `lifecycle.md`, `forms/daemon-flags.tsv`, `Platform/common/contracts/schema.md` |
| `runtime_limits` runtime limits | P/10-R024 | `forms/runtime-constants.tsv`, `forms/README.md` |
| `data_and_clocks` data ownership and clocks | P/10-R028, P/10-R030, P/10-R031, P/10-R033, P/10-R034, P/10-R035, P/10-R036, P/10-R037, P/10-R038, P/10-R039, P/10-R040, P/10-R041, P/10-R042, P/10-R043, P/10-R044, P/10-R045 | `lifecycle.md`, `Platform/common/data/catalog.tsv`, `Platform/common/contracts/event-journal.md` |
| `read_doors` read doors and refusals | P/10-R004, P/10-R012, P/10-R015, P/10-R057, P/10-R058, P/10-R060, P/10-R065, P/10-R067, P/10-R069, P/10-R070, P/10-R072, P/10-R075, P/10-R076, P/10-R077, P/10-R078, P/10-R085, P/10-R088, P/10-R089, P/10-R090, P/10-R092, P/10-R095, P/10-R096, P/10-R097, P/10-R099, P/10-R100, P/10-R102, P/10-R103, P/10-R110, P/10-R111, P/10-R112, P/10-R114, P/10-R115, P/10-R118, P/10-R121, P/10-R125, P/10-R131, P/10-R132, P/10-R136, P/10-R139, P/10-R140, P/10-R142, P/10-R145, P/10-R148, P/10-R151, P/10-R155, P/10-R159, P/10-R160, P/10-R161, P/10-R163, P/10-R164, P/10-R166, P/10-R170, P/10-R171, P/10-R178, P/10-R181, P/10-R183, P/10-R184, P/10-R185, P/10-R186, P/10-R187, P/10-R188, P/10-R189, P/10-R191, P/10-R193, P/10-R195, P/10-R196, P/10-R199, P/10-R201, P/10-R202, P/10-R204, P/10-R205, P/10-R206, P/10-R208, P/10-R209, P/10-R212, P/10-R213, P/10-R216, P/10-R218, P/10-R221 | `spec/10-domain-console.api.openapi.yaml`, `forms/refusals.tsv`, `data/refusal-words.tsv`, `Platform/08-domain/spec/08-domain.api.openapi.yaml` |
| `view_pages` view pagination and incomplete observations | P/10-R004, P/10-R118, P/10-R121, P/10-R125, P/10-R131, P/10-R132, P/10-R136, P/10-R139, P/10-R140, P/10-R142, P/10-R145, P/10-R148, P/10-R151, P/10-R155 | `forms/runtime-constants.tsv`, `spec/10-domain-console.api.openapi.yaml` |
| `domain_forwarding` passing to the domain process | P/10-R005, P/10-R006, P/10-R013, P/10-R224, P/10-R226, P/10-R227, P/10-R229, P/10-R230, P/10-R231, P/10-R232, P/10-R234, P/10-R237, P/10-R239, P/10-R242, P/10-R382, P/10-R384, P/10-R385, P/10-R387, P/10-R391, P/10-R392, P/10-R393, P/10-R394 | `lifecycle.md`, `Platform/common/contracts/forwarding.md`, `Platform/08-domain/spec/08.0-domain.norms.md` |
| `role_door` role door and accepted forwarding | P/10-R007, P/10-R249, P/10-R250, P/10-R251, P/10-R252, P/10-R253, P/10-R254, P/10-R255, P/10-R258, P/10-R261 | `Platform/common/contracts/role-certificate.md`, `Platform/common/contracts/peer.md`, `Platform/common/contracts/event-journal.md` |
| `gate` identity and grants | P/10-R008, P/10-R263, P/10-R264, P/10-R266, P/10-R268, P/10-R270, P/10-R274, P/10-R276, P/10-R277, P/10-R279, P/10-R280 | `Platform/common/contracts/gate-and-pass.md`, `Platform/common/contracts/domain-token.md`, `Platform/common/contracts/may.md` |
| `door_pass` worker routing and second-kind pass | P/10-R009, P/10-R287, P/10-R288, P/10-R292, P/10-R293, P/10-R295, P/10-R297, P/10-R299, P/10-R301, P/10-R302, P/10-R303, P/10-R305, P/10-R309, P/10-R313 | `Platform/common/contracts/gate-and-pass.md`, `Platform/common/contracts/forwarding.md` |
| `holder_page` holder page and session | P/10-R010, P/10-R318, P/10-R319, P/10-R321, P/10-R323 | `lifecycle.md`, `spec/10-domain-console.api.openapi.yaml`, `Platform/07-console-module/CONSOLE-MODULE.md` |
| `alarms` alarm collection and function | P/10-R011, P/10-R014, P/10-R016, P/10-R327, P/10-R329, P/10-R330, P/10-R332, P/10-R334, P/10-R335, P/10-R336, P/10-R339, P/10-R340, P/10-R341, P/10-R342, P/10-R344, P/10-R347, P/10-R350, P/10-R351, P/10-R353, P/10-R354, P/10-R356, P/10-R396, P/10-R398, P/10-R399, P/10-R400, P/10-R401, P/10-R402, P/10-R403, P/10-R404, P/10-R406, P/10-R407, P/10-R408, P/10-R409, P/10-R411, P/10-R412, P/10-R414, P/10-R417, P/10-R419, P/10-R420, P/10-R421, P/10-R423, P/10-R424, P/10-R425, P/10-R426, P/10-R427, P/10-R429, P/10-R431, P/10-R435, P/10-R436, P/10-R437, P/10-R438, P/10-R439, P/10-R459, P/10-R461, P/10-R462, P/10-R464, P/10-R466, P/10-R467 | `vectors/alarms/README.md`, `forms/runtime-constants.tsv`, `Platform/common/contracts/alarm-history.md`, `Platform/09-agent/spec/09.1-agent.norms.md` |
| `refusals` refusal catalogue | P/10-R015, P/10-R442, P/10-R443, P/10-R444, P/10-R449, P/10-R452, P/10-R454 | `forms/refusals.tsv`, `data/refusal-words.tsv`, `spec/10-domain-console.api.openapi.yaml` |
| `acceptance` acceptance and evidence boundaries | P/10-R016, P/10-R017, P/10-R458, P/10-R459, P/10-R461, P/10-R462, P/10-R464, P/10-R466, P/10-R467, P/10-R468, P/10-R469, P/10-R470, P/10-R471, P/10-R472, P/10-R473, P/10-R474, P/10-R475, P/10-R476, P/10-R477, P/10-R478, P/10-R479, P/10-R480, P/10-R481, P/10-R482, P/10-R484 | `acceptance/README.md`, `forms/README.md`, `forms/stages.tsv`, `vectors/alarms/README.md` |

## N0 Vocabulary

<!-- req: P/10-R001 -->
Normative keywords follow the [course canon](../../common/NORMATIVE-TERMS.md).

<!-- req: P/10-R019 -->
The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary);

<!-- req: P/10-R020 -->
the order of output arrays is P/08.0 N0 «Order of output arrays» (scope — lessons 8–10).

<!-- req: P/10-R002 -->
The [common production obligations](../../common/contracts/production-obligations.md) apply here. The selected MB3 rules in the common contracts apply here.

<!-- req: P/10-R022 -->
Use exactly one marker reread before silent: a changed marker with no exact fresh generation is temporarily unconfirmed; With a changed marker and no exact fresh generation, defer the derived snapshot and use existing 503 unavailable on a door requiring the confirmed read, not a new member state.

## N1 Form

<!-- req: P/10-R024 -->
[runtime-constants.tsv](../forms/runtime-constants.tsv) projects three owned positive integer limits; RELAY_MEMBERS_MAX is read from its P/08.3 owner form with their requirement anchors; the [form grammar](../forms/README.md#inputs-and-constants) fixes units and scope. These are not additional environment settings.

<!-- req: P/10-R028 -->
**Time.** The lesson writes no rows and objects with time; a line of the role journal has `t` by [the event journal contract](../../common/contracts/event-journal.md).

<!-- req: P/10-R030 -->
`age` of the answer of `GET /domain` is seconds by the wall clock of the console, not a time in a row (N1.2a);

<!-- req: P/10-R031 -->
the time of the rows of the alarm list is the domain clock (N1.8 `clock`); the history object — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1 «Time», the member's alarm page — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1 «Time».

<!-- req: P/10-R033 -->
**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/<manifest:domain.witness.report>/<name>`;
- writes: `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append);
- reads: `domain/relay-members/<relay>`, `domain/<sub>/<manifest:domain.kept>`, `domain/folder-units/<id>`, `domain/folder-units/<id>/<part>`, `domain/folder-counts/<id>`, `domain/view-rows/<part>`, `domain/anywhere`, `domain/folders/<id>`, `domain/memberof/<member>/<sub>/<manifest:unit.rows>/<id>`, `domain/members/<member>/tables/<sub>/<table>`, `domain/roles/<name>`, `domain/groups/<name>`, `platform/manifest/<sub>`, `platform/manifest/<sub>/rev` (the mark: a manifest change — P/02.3 N3), `platform/schema`, `/etc/w2c/tls/<role>/server.key`, `domain/view`, `domain/shadow`, `domain/holder`, `domain/keys`, `domain/root`, `domain/revoked`, `domain/member-rows/<part>`, `domain/members/<member>/ca-certs`, `domain/members/<member>/reports/<rev>`, `domain/members/<member>/reported`, `domain/topology`, `domain/<sub>/worker`, `domain/<sub>/heartbeat`, `domain/placement`, `domain/placement/<sub>/<ref>`, `domain/disabled`, `domain/grants/<cluster>`, `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/alarm-history/<member>`.

<!-- req: P/10-R034 -->
The domain console writes no rows of the holder: it passes the edits on to the process `domain` (N1.3; the reception — [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.8), the rights of `domainconsole` are reading `domain/*` ([P/02.5](../../02-installer/spec/02.5-installer.norms.md) N1.4).

<!-- req: P/10-R035 -->
The family of witness objects `<sub>/<manifest:domain.witness.report>/<name>` belongs to this lesson by protocol (N1.8 `witness`): the worker of the subsystem (a participant) writes it, the agent carries it in the report;

<!-- req: P/10-R036 -->
the domain console reads witnesses only from the reports of members (`domain/members/<member>/reports/<rev>`; the holder is a member too, with its own agent), the family has no schema in `data/` (the form is the declaration `domain.witness` of the manifest, [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md)).

<!-- req: P/10-R037 -->
What each door reads: the view, the shadow report, the list of members, the topology, the placements, the grants, the shared document — the read doors N1.2 (the forms of the rows are in their chapters of lesson P/08);

<!-- req: P/10-R038 -->
What each door reads: `domain/keys`, `domain/root`, `domain/revoked`, `domain/disabled`, `domain/grants/<cluster>`, `domain/roles/<name>`, `domain/groups/<name>` — the gate (N1.5; the keys and the token — [the domain token contract](../../common/contracts/domain-token.md), `may` — [the right contract](../../common/contracts/may.md));

<!-- req: P/10-R039 -->
What each door reads: `domain/member-rows/<part>` and the rows `domain/members/<member>/ca-certs` — the role door (N1.4 `server.role`; the domain console does not read the copy `domain/member-list/<part>`);

<!-- req: P/10-R040 -->
What each door reads: `domain/<sub>/worker` and the heartbeat `domain/<sub>/heartbeat` — `door.pass` on the domain (N1.6);

<!-- req: P/10-R041 -->
What each door reads: the member's report, the mark `reported` (`received_at`, `sent_at`), the history and `domain/member-rows/<part>` — the alarm list (N1.8);

<!-- req: P/10-R042 -->
What each door reads: the manifest rows and `platform/schema` — the start (N1.1);

<!-- req: P/10-R043 -->
What each door reads: the key of the server certificate of the role `domainconsole` — the role door of TLS.

<!-- req: P/10-R044 -->
The role journal is `audit/domainconsole`, the alarm `session.debug_open` (a debug identity, N1.5) — `audit.alarms/domainconsole` ([the event journal contract](../../common/contracts/event-journal.md), participant `append`, owner — P/05).

<!-- req: P/10-R045 -->
The lines «journal» of the role door — the transition of the trust set into unreadable and back (the role certificate contract, class `role`, `unreadable`) and a service without a kit (`no_kit`) — are a diagnostic of the process (stderr), not events of `audit/domainconsole`: there are no kinds for them and new ones are not introduced, the text is the implementation's, acceptance does not compare it.

### N1.1 The process and the start (P/02.4 N1.12)

<!-- req: P/10-R003 -->
The domain console is the process `domainconsole` at the holder cluster, next to the process `domain`: the unit `w2c-domainconsole.service`, the role `domainconsole`, the implicit address defaults of `DOMAIN_CONSOLE_HOST/PORT` from [daemon-flags.tsv](../forms/daemon-flags.tsv) — only with a role kit, TLS — by the kit ([P/02.4 N1.12](../../02-installer/spec/02.4-installer.norms.md)).

<!-- req: P/10-R047 -->
Like the processes of the platform, it executes the reader's side of the manifest row ([P/02.3](../../02-installer/spec/02.3-installer.norms.md) N3 «Process start», «Manifest change»): it has no built-in manifest, steps 0–4 of «Process start» are as there: step 0 is the schema check against `SCHEMA` of the platform build ([the schema contract](../../common/contracts/schema.md) «Check at start»); Process start, step 1: check the whole catalogue. Process start, step 2: check only `sha256` of the row (there are no built-in bytes to compare with).

<!-- req: P/10-R050 -->
After the manifest checks of process start, check the environment and the TLS kit, then open the port. readiness is the port, it does not send `sd_notify` (P/02.4 N1.12; P/10-15).

<!-- req: P/10-R052 -->
The process environment is projected by [daemon-flags.tsv](../forms/daemon-flags.tsv) with the [form grammar](../forms/README.md#inputs-and-constants); the launcher and imported contextual contracts remain mandatory. The environment, the exit codes and the unit are in the [life cycle](../lifecycle.md).

### N1.2 The read doors — it answers itself

<!-- req: P/10-R004 -->
The parsing of a request is [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Request parsing and the order of checks» (P/01.1 N2.1 with the deviations of the console); The domain console has no deviations of its own from this request parsing.

<!-- req: P/10-R057 -->
The identity and the grants are N1.5 (`view` for reading by `domain/grants/domain`; the view doors — «Judgement by target» of [the right contract](../../common/contracts/may.md)).

<!-- req: P/10-R058 -->
Each door is a row of the list of domain doors of [the forwarding contract](../../common/contracts/forwarding.md) «Domain doors»; a row with `GET` also covers `HEAD` of the same path — the same code and headers without a body (ibid.; P/06.5 N2).

<!-- req: P/10-R060 -->
**The row version at the read doors** ([P/08.0](../../08-domain/spec/08.0-domain.norms.md) N1.9 «Versions»). The doors of one row — `GET /domain/members/<member>`, `GET /domain/topology`, `GET /domain/placement/<sub>/<ref>`, `GET /domain/shared` — serve an `ETag`: the index of this row (for the shared document — of the pointer) in double quotes, from the same read as the value. There is no row — the answer is without `ETag`: the condition has nothing to judge about. `GET /domain/placement` carries `index` in each record, `GET /domain/grants` — the field `versions`: the index and `revision` stand by the row, because the answer has many rows. The values are fit for `If-Match` of the edit doors that the console passes on to the process (N1.3).

<!-- req: P/10-R065 -->
**N1.2a The view.** The doors are at the domain console; the cluster console forwards them without rewriting:

**GET `/domain[?cursor=]`**

<!-- req: P/10-R067 -->
**Success** — the answer is the head of `domain/view` and the non-empty parts in a row up to DOMAIN_PAGE_MEMBERS members, the fields `members`, `units`, `contested`, `reports`, `pending`, `outcomes` — a merge of the rows, `cursor` — the next page, `unread` — the unread parts; **Success** — a small domain — one page (P/08.1 N1.4b);

<!-- req: P/10-R069 -->
**Success** — for a non-viewer of the domain (the right contract `wide`) — only `as_of`, `holder`, `complete`, `members` (`servers` and `url` — only for the clusters where it has a row), `units` by record, `outcomes` — the outcomes where `by` is itself, `contested` — the refs whose cluster it sees, `age`, `url`, `withheld: <count>`;

<!-- req: P/10-R070 -->
**Success** — otherwise 200 — the object `domain/view` ([P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.4) as is plus `age` — seconds since `as_of` by the wall clock of the console, `max(0, now − as_of)` (a clock gone back — 0), one digit after the point; **Success** — the field `url` of the view that does not read (not a string) is `null` in the answer

<!-- req: P/10-R072 -->
**Refusals** — 404 `{error: "no domain here", detail}` — there is no object; **Refusals** — the object exists but does not read — 503 `{error: "unavailable"}`, not 404; **Refusals** — 401/403 — N1.5

**GET `/domain/<sub>/<rows>[?cluster=<member>][&cursor=]`, `/domain/<sub>/<rows>?part=<part>`**

<!-- req: P/10-R075 -->
**Success** — 200 — `[Unit]` of the subsystem from the rows of the view, page by page by the header `X-Cursor`, with `cluster` — this member’s entire row in its one part, one page: `cursor` is not read, including an invalid opaque cursor, and there is no `X-Cursor`;

<!-- req: P/10-R076 -->
**Success** — with `part` — the units of one row `domain/view-rows/<part>`, one read and one page, `cursor` is not read, there is no `X-Cursor`, no row — `[]` (the part — P/08.3 N1.1);

<!-- req: P/10-R077 -->
**Success** — for a non-viewer of the domain — only the records it sees, `X-Withheld: <count>`, if some are hidden because of the unread (`unavailable`)

<!-- req: P/10-R078 -->
**Refusals** — in order: 400 — `cluster` or `part` twice or empty ([P/06.5](../../06-console/spec/06.5-console.norms.md) N2), `part` not by the grammar of a part, `cluster` and `part` together; **Refusals** — 404 — there is no such manifest; **Refusals** — 404 `{error: "not in the directory"}` — the manifest has no `domain.ref`; **Refusals** — 404 — `rows` is not its own; **Refusals** — 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read; **Refusals** — 404 `{error: "no such member"}` — the member is not in the list; **Query** — other parameters are not read

**GET `/domain/<sub>/kept/<name>`**

<!-- req: P/10-R085 -->
**Success** — 200 `{items, index}` of the row `domain/<sub>/<name>`, `<name>` — an element of `domain.kept_read` of the manifest; **Success** — the mask of [P/06.2](../../06-console/spec/06.2-console.norms.md) N1.4: an element with the name `*_secret` and a field `*_secret` at any depth of the value parsed as JSON, an envelope `enc:` — `"***"`, a value that is not JSON — as is; **Success** — the domain console answers itself;

<!-- req: P/10-R088 -->
**Success** — the right is `view` of the domain (`wide`), judged first: a non-viewer does not tell «not declared» from «not allowed»

<!-- req: P/10-R089 -->
**Refusals** — 401, 403 — before everything;

<!-- req: P/10-R090 -->
**Refusals** — 404 `{error: "no such path"}` — `<name>` is not declared or there is no row; **Refusals** — 503 `{error: "unavailable"}` — does not read

**GET `/domain/relays/<relay>`**

<!-- req: P/10-R092 -->
**Success** — 200 `{relay, rev, members}` of the row `domain/relay-members/<relay>` (P/08.3 N1.2): `members` — names in ascending order, up to RELAY_MEMBERS_MAX ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2, [owner form](../../08-domain/forms/runtime-constants.tsv)), the member keys do not go; **Success** — there is no row — `rev` 0, `members: []`; **Success** — the domain console answers itself;

<!-- req: P/10-R095 -->
**Success** — the right is `view` of the domain (`wide`), judged first

<!-- req: P/10-R096 -->
**Refusals** — 401, 403 — before everything;

<!-- req: P/10-R097 -->
**Refusals** — 404 `{error: "no such member"}` — there is no such member; **Refusals** — 503 `{error: "unavailable"}` — the row does not read or exceeds its owner limit;

<!-- req: P/10-R099 -->
**Members** — Never truncate the relay member list.

**GET `/domain/<sub>/tables/<table>?cluster=<member>`**

<!-- req: P/10-R100 -->
**Success** — 200 — `{cluster, ts, rows}`, the object P/08.1 N1.4a of this member as is, for a non-viewer of the domain — only the visible rows and `X-Withheld`; **Success** — `ETag` — sha256 of the served body, separate for each answer, `If-None-Match` — 304: reading the list of members is cheap;

<!-- req: P/10-R102 -->
**Read scope** — one member per request: the object is bounded by P/04 N1.3b, there is no list of all

<!-- req: P/10-R103 -->
**Refusals** — in order: 400 — `cluster` is absent, twice or empty; **Refusals** — 404 — there is no such manifest; **Refusals** — 404 — `<table>` is not a key of `domain.view_tables`; **Refusals** — 404 `{error: "no domain here"}` — there is no view, 503 `{error: "unavailable"}` — the view does not read; **Refusals** — 404 `{error: "no such member"}` — the member is not in the list; **Refusals** — 404 `{error: "not reported yet"}` — there is no object; **Refusals** — 503 `{error: "unavailable"}` — the object does not read;

<!-- req: P/10-R110 -->
**Query** — other parameters are not read

**GET `/domain/shadow`**

<!-- req: P/10-R111 -->
**Success** — 200 — the shadow report (P/08.1 N1.6) of the last pass

<!-- req: P/10-R112 -->
**Refusals** — 404 `{error: "no domain here"}` — there is no report; **Refusals** — the report exists but does not read — 503 `{error: "unavailable"}`

**GET `/domain/folders`, `/domain/folders/<id>/units[?cursor=&limit=]`, `/domain/memberof/<member>/<sub>/<rows>/<id>`**

<!-- req: P/10-R114 -->
**Success** — Own domain-console read doors by [P/08.5 N1.8](../../08-domain/spec/08.5-domain.norms.md): forms, pagination, visibility and check budget remain with that owner

<!-- req: P/10-R115 -->
**Refusals** — N1.5 before reads; **Refusals** — bad cursor — 400 `{error: "refused"}`, no folder — 404 `{error: "no such path"}`; **Refusals** — unreadable source — 503 `{error: "unavailable"}`

<!-- req: P/10-R118 -->
**Pagination of `GET /domain`.** The limit is hard: at most DOMAIN_PAGE_MEMBERS elements of `members` per page. A part is the writer's storage/work unit, not an indivisible HTTP page; a readable part with more than DOMAIN_PAGE_MEMBERS members is split at a member boundary.

<!-- req: P/10-R121 -->
Visit the non-empty parts in ascending order of their four-digit names (0000…4095), and the members inside each part by name in UTF-8 byte order. Select up to the remaining page budget, then continue inside this part on the next request if needed. Each returned page's `members` is itself ordered by name; its last displayed element need not identify the last visited part.

<!-- req: P/10-R125 -->
The request without cursor starts the traversal. The returned cursor is an opaque string carrying sufficient continuation state, such as the current part and last visited member. Its encoding is the implementation's; clients return the issued token unchanged as the query value. The cursor continues after the selected members, including within a part, and is omitted at the end. On unchanged readable data, following all pages returns every member exactly once, without a skip or a repeat.

<!-- req: P/10-R131 -->
The API promises ordinary reads, not a new snapshot spanning concurrent changes.

<!-- req: P/10-R132 -->
The page projects the six per-member fields: `members` contains the selected members; `units` keeps Unit records whose cluster is selected; `reports`, `pending` and `outcomes` keep selected member keys. Preserve the view's required empty subsystem keys.

<!-- req: P/10-R136 -->
A contested ref is a complete conflict fact: keep a ref that has a selected claimant, with its entire original claimant list, never truncate that list at the page boundary. Names used as this context are not additional MemberState elements of the page. A conflict can therefore appear on more than one page, while the members themselves do not repeat.

<!-- req: P/10-R139 -->
The head's global fields stay global.

<!-- req: P/10-R140 -->
Existing visibility filtering and the unread/incomplete rules still apply; pagination alone does not change the holder's round completeness.

<!-- req: P/10-R142 -->
The existing reader field `unread` is optional `Part[]`; its named type binding is `ServedView.unread` in the [P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml), with items referring to the existing Part parameter's Schema Object. It is not a stored-head or writer field.

<!-- req: P/10-R145 -->
During one ordinary pagination sequence in the same context, omit the collected field only if every page omitted it. If any page supplied it, retain the field, possibly as `[]`, and collect each literal Part string once in first-observation order, including order within a page. Later absence or `[]` does not erase earlier observations.

<!-- req: P/10-R148 -->
Do not parse, trim, pad, sort or normalize part strings; this collector does not add `uniqueItems` or other bounds to an individual response. This reader observation does not rewrite the first head's global fields or the six projections, full contested context, empty subsystem keys, opaque cursor or visibility filtering.

<!-- req: P/10-R151 -->
Absence due to visibility does not prove completeness. Valid `200` responses with `complete: false` or `unread`, including on a later page, remain normal incomplete observations, not automatic transport errors or `domain: null`. An actual HTTP/network/body-read failure of continuation keeps the existing null/error path; no inter-page snapshot or client completeness flag is added.

<!-- req: P/10-R155 -->
Examples on fixed data: one part with 1001 members gives pages of 1000 and 1; consecutive parts with 999 and 2 give pages of 1000 and 1, continuing inside the second part. A conflict between members on opposite sides of that boundary keeps both claimant names wherever that conflict is included. No part-size bound is added to P/08.1 N1.4b.

**N1.2b Members.**

**GET `/domain/members/<member>`**

<!-- req: P/10-R159 -->
**Who answers** — the domain console (`domainconsole`)

<!-- req: P/10-R160 -->
**Success** — 200 `{part, rev, term, entry}` of the row of the part of this name and `ETag`: the version for `If-Match` of the edit doors

<!-- req: P/10-R161 -->
**Refusals** — 404 not a member; **Refusals** — 503 does not read

**POST, GET `/domain/batches`, DELETE `/domain/batches/<name>`**

<!-- req: P/10-R163 -->
**Who answers** — the domain console → the process `domain` ([chapter 8.0](../../08-domain/spec/08.0-domain.norms.md))

<!-- req: P/10-R164 -->
**Success** — the request, response bodies and status codes of [the P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml) and [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.1b, served as received; **Success** — the POST token is shown once, GET omits it

<!-- req: P/10-R166 -->
**Refusals** — 400 not by the form; **Refusals** — 404 there is no batch; **Refusals** — 409 such a batch exists; **Refusals** — N1.9 — the right `admin` of the domain

**GET `/domain/members[?cursor=]`**

<!-- req: P/10-R170 -->
**Who answers** — the domain console (`domainconsole`)

<!-- req: P/10-R171 -->
**Success** — 200 `{members, parts, knocking, count, cursor?}`: the non-empty parts in a row, up to DOMAIN_PAGE_MEMBERS members, a small domain — one page; **Success** — `parts` — `{<part>: {rev, term, index}}`; **Success** — `index` is the exact nonempty string Row.index of the store row read, never a JSON number or a binary64 conversion ([P/01.1](../../01-store/spec/01.1-store.norms.md) N1 Version); **Success** — `members` — a merge of the doc of the rows read by the door; **Success** — `count` — `domain/member-count`, absent — no field; **Success** — `knocking` — on the first page `view.knocking`, on each — `domain/knocks/<part>` of the parts of the page (the memory knock exists only in the view, [chapter 8.1](../../08-domain/spec/08.1-domain.norms.md) N1.7), the field is absent in a readable view — `[]` (the field is optional, nobody is knocking; like a view without `shared`); **Success** — `member_list` of the view is not substituted

<!-- req: P/10-R178 -->
**Refusals** — 404 `no domain here` (there is no view; there is no row `domain/member-rows/<part>` with a readable view — the list exists from the first start of the holder, [P/08.3](../../08-domain/spec/08.3-domain.norms.md) N3 «the holder in the list»); **Refusals** — the row `domain/member-rows/<part>` or the view exists but does not read — 503 `{error: "unavailable"}`; **Refusals** — 401/403 — N1.5

<!-- req: P/10-R181 -->
The grant `admin` for editing the list and `view` for reading are N1.5; the console passes the edits of the list on to the process (N1.3; their norms are [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N2).

**N1.2c Topology.**

**GET `/domain/topology`**

<!-- req: P/10-R183 -->
**Who answers** — the domain console

<!-- req: P/10-R184 -->
**Success** — 200 doc ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.2) — from the row `domain/topology`, not from the view: right after a PUT — the new `rev`

<!-- req: P/10-R185 -->
**Refusals** — 404 `no domain here` — the view is not built (N4);

<!-- req: P/10-R186 -->
**Absent topology** — there is no row `domain/topology` — not a refusal: 200 `{rev: 0, star: [], via: {}}` (P/08.3 N1.2: rev 0 — «never written», no row — the same);

<!-- req: P/10-R187 -->
**Refusals** — the row `domain/topology` exists but does not read — 503 `{error: "unavailable"}`;

<!-- req: P/10-R188 -->
**Refusals** — 401/403 — N1.5

<!-- req: P/10-R189 -->
**N1.2d Placements.** The doors are the domain console's; the member console forwards them (the forwarding contract «Domain doors»):

**GET `/domain/placement`**

<!-- req: P/10-R191 -->
**Success** — 200 `{rev, records: {"<sub>/<ref>": Placement with index}}`; **Success** — there is no row `domain/placement` — `rev` 0 (there is no counter yet, [P/08.6](../../08-domain/spec/08.6-domain.norms.md) N1.2 `absent`), `records` — as always

<!-- req: P/10-R193 -->
**Refusals** — the row `domain/placement` (the counter `rev`) exists but does not read — 503 `{error: "unavailable"}`; **Refusals** — 401/403 — N1.5

**GET `/domain/placement/<sub>/<ref>`**

<!-- req: P/10-R195 -->
**Success** — 200 Placement

<!-- req: P/10-R196 -->
**Refusals** — 404 there is no record; **Refusals** — the record exists but does not read — 503 `{error: "unavailable"}`, not 404; **Refusals** — 404 there is no manifest or it is without `domain.ref`

<!-- req: P/10-R199 -->
The form `Placement` and the counter are [chapter 8.6](../../08-domain/spec/08.6-domain.norms.md) N1.1; the console passes the edits of placements on to the process (N1.3).

**N1.2e Grants.**

**GET `/domain/grants`**

<!-- req: P/10-R201 -->
**Who** — the domain console

<!-- req: P/10-R202 -->
**Right** — view; **Right** — to a non-viewer of the domain — only the clusters where it has `admin` on `*` (the right contract `target`), none — 403

<!-- req: P/10-R204 -->
**Success** — 200 `{grants: {<cluster>: [line…]}, versions: {<cluster>: {revision, index}}}`

<!-- req: P/10-R205 -->
**Refusals** — 401/403

<!-- req: P/10-R206 -->
The grant line `line` is [chapter 8.4](../../08-domain/spec/08.4-domain.norms.md) N1.3; the console passes the edit `PUT /domain/grants/<cluster>` on to the process (N1.3).

**N1.2f The shared document.**

<!-- req: P/10-R208 -->
**door** — GET /domain/shared at the domain console (view) → 200 {doc, delivery, declared};

<!-- req: P/10-R209 -->
**door** — there is no view (domain/view) — 404 {error: "no domain here"}, like the other read doors without a view (N1.2a); **door** — the view exists but does not read — 503 {error: "unavailable"}; **door** — the pointer domain/shared or its document exists but does not read (not by the form, not with the sha256 of the pointer) — 503 {error: "unavailable"}, not doc: null (the outcomes of the families shared, shared-docs)

<!-- req: P/10-R212 -->
**doc** — the document as signed (an object) | null

<!-- req: P/10-R213 -->
**delivery** — view.shared — an x-opaque field: the console does not judge the form of the delivery (the form is the writer's, the process domain, P/08.9 N1.6), it serves a non-empty object as is, by value; **delivery** — no field or {} — 200, delivery = before (P/08.9 N1.6) by the view: term 0, rev 0, holding [], behind {}, refused {}, silent — the members of the view not ok, sentence «rev 0 on 0 of T members» (T — the members of the view) with the tails of before; **delivery** — null in term and rev is not written

<!-- req: P/10-R216 -->
**declared** — {\<sub\>: [{name, type, schema?}]} — the elements domain.shared of the manifests of the catalogue, by name; **declared** — schema — at the document (CONSOLE-MODULE.md §10a; the late layer P/07 N1.6)

<!-- req: P/10-R218 -->
The document and the pointer are [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.2; `view.shared` is chapter 8.9 N1.6; the declaration `domain.shared` is [P/02.1 N1.2b](../../02-installer/spec/02.1-installer.norms.md).

<!-- req: P/10-R221 -->
The console passes the edit `PUT /domain/shared` on to the process (N1.3; the execution — chapter 8.9 N1.3).

### N1.3 Passing on to the process `domain`

<!-- req: P/10-R005 -->
The reception of the passing, `writer` and `answers` are [P/08.0 N1.8](../../08-domain/spec/08.0-domain.norms.md) (P/08.0-01); This section defines the domain console's side of this passing.

<!-- req: P/10-R224 -->
**console** — the domain console is a door: it checks the identity and the grant (the gate, N1.5) and passes the edit on; **console** — it has no records of its own in the rows of the holder (the rights of domainconsole are reading, P/02.5 N1.4)

<!-- req: P/10-R226 -->
**pass** — every door /domain/* of the domain console, except GET and HEAD and except door.pass to the worker on the domain (N1.6), and POST /api/login (P/08.4 N1.2); the people doors of P/08.4 N1.9 (/domain/users…, /domain/break-glass…) — with any method, GET too, and GET/HEAD /domain/batches and GET/HEAD /domain/\<sub\>/books/\<book\>/*/\<part\> — to the process domain (SIGNER_URL of its own box; to https:// — the client of its own cluster, the role certificate contract own_client, role domain): the method, the path with query, the body, Authorization, Idempotency-Key, If-Match as they came, except the first cookie transition under the forwarding contract «First cookie transition to the domain»;

<!-- req: P/10-R227 -->
**pass** — X-W2C-Client — the address of the client's TCP peer: the domain console sets it; **pass** — when, whom the process trusts and what is stripped outside — the forwarding contract Platform/common/contracts/forwarding.md «Client address»;

<!-- req: P/10-R229 -->
**pass** — the deadline is «Wait» of the row of the forwarding contract Platform/common/contracts/forwarding.md «Domain doors»;

<!-- req: P/10-R230 -->
**pass** — the answer is as it came, without parsing (the forwarding contract «Forwarding is one function» answer: 502 on a break and on silence);

<!-- req: P/10-R231 -->
**pass** — the process checks the identity and the grant itself (P/08.4 N1.5) and executes N3 of the door

<!-- req: P/10-R232 -->
The doors that the console passes on are the rows of the list of domain doors of the forwarding contract «Domain doors», except its own read doors (N1.2), the alarm list (N1.8) and `door.pass` (N1.6); their norms and answers are the chapters of lesson P/08 by door ([P/08.0](../../08-domain/spec/08.0-domain.norms.md) N2, the summary table).

<!-- req: P/10-R234 -->
The console serves the answer of the process as it came — `409 deposed`, `503 frozen`, `503 standby` too: it does not recompute them (P/08.0 N1.8 `answers`; the forwarding contract «Refusals by transition», transition 3).

### N1.3a People doors

<!-- req: P/10-R006 -->
The lines `first`, `member` are [P/08.4 N1.9](../../08-domain/spec/08.4-domain.norms.md) (P/08.4-07); This section defines the domain console's passing of these people doors.

<!-- req: P/10-R237 -->
**pass** — the doors /domain/users…, /domain/groups…, /domain/roles…, /domain/batch and /domain/break-glass… with any method, GET too, the edits /domain/grants/… and /domain/revoke the domain console passes on to the process domain by N1.3; **pass** — the process checks the token and domain/grants/domain itself

<!-- req: P/10-R239 -->
**The path of `backend` to the domain doors**. The request comes by forwarding from the cluster console ([P/06.3](../../06-console/spec/06.3-console.norms.md) N1.9 «Domain doors»): the original token of the human; the bytes of the ticket do not reach here. Further on the path does not differ from a request of the page: the process judges the right of the human by P/08.4 N1.5, `by` is the name of the human. Records one by one from `backend` do not go.

<!-- req: P/10-R242 -->
The sign of the path is the closed header `X-W2C-Via-Worker: <sub>/<instance>` ([the forwarding contract](../../common/contracts/forwarding.md)): the cluster console sets it on the forwarding by ticket, the cluster console of the holder lets it through as declared on transition 1; the domain console strips it from an external request, accepts it only from the leaf of the role of the cluster console and passes it on to the process, and the process trusts it only on the connection of its own console. It serves as neither a right nor a check: only the journal and the alarm. The journal carries `via: <sub>/<instance>`.

### N1.4 Accepting the forwarding and the role door of TLS

<!-- req: P/10-R007 -->
The domain console accepts the forwarding of the cluster console (transition 2) by [the forwarding contract](../../common/contracts/forwarding.md): «Accept by a console» (before the gate: `X-User` — strip; `X-Operator: console` byte for byte and a connection with the proven role `console` — keep for the journal, otherwise strip; the line `x_operator` of «Forwarding is one function») and «Client address» (the console strips an `X-W2C-Client` that came from outside, like `X-User`) (P/10-10). «For the journal» means: the lines of `audit/domainconsole` about a request with a recognized `X-Operator: console` carry the common field `role: "console"` ([the event journal contract](../../common/contracts/event-journal.md) `door_journal`: «role — the leaf role»); without a recognized header there is no field `role`; there is no new kind and no new field.

<!-- req: P/10-R249 -->
The server side is the class `role` of [the role certificate contract](../../common/contracts/role-certificate.md) (the class `signed` and the common `server` — ibid. «The server side: the class `signed`»):

<!-- req: P/10-R250 -->
**roles** — the process domain — the kit domain;

<!-- req: P/10-R251 -->
**roles** — the domain console — domainconsole;

<!-- req: P/10-R252 -->
**roles** — the agent and the door of the relay (P/09.2: this is the agent) — domainagent;

<!-- req: P/10-R253 -->
**roles** — the cluster console — console

<!-- req: P/10-R254 -->
**server.role** — the role door of the domain console — the class `role` of the role certificate contract «The server side: the class `role`»: the trust set, the handshake, the refusals no_role, wrong_role, bad_chain before the gate, without session resumption

<!-- req: P/10-R255 -->
**server.no_kit** — there is no kit — the door serves transition 2 on the loopback over HTTP without a role check; **server.no_kit** — the role is not proven: X-Operator: console is stripped, X-W2C-Client is not trusted; **server.no_kit** — there are no refusals no_role, wrong_role, bad_chain (the role certificate contract, class role, no_kit)

<!-- req: P/10-R258 -->
`Entry.ca`, the row `ca-certs` and their reception are [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.6; the function `peer` and its words — [the `peer` contract](../../common/contracts/peer.md) (this lesson is a participant, steps 6–7); the leaf and the signatures — the role certificate contract `cert`, `sig`.

<!-- req: P/10-R261 -->
The row `domain/member-rows/<part>` (the Entry.ca of the admitted members) exists but does not read — the trust union of the role door for this pass is only its own CAs (`ca.pem`, `ca.next.pem`): a handshake of other members is a refusal, a journal line (P/10-11).

### N1.5 The gate of the domain console (P/08.4 N1.5 `domain`)

<!-- req: P/10-R008 -->
The domain console is a participant of [the gate-and-pass contract](../../common/contracts/gate-and-pass.md): of the section «The gate» the lines `gate`, `identity`, `x_user`, `caps`, `scope`, `csrf`, `body`, `refusal` and `session` apply (the table of the sides of the contract).

<!-- req: P/10-R263 -->
The states `on`, `open`, `shut` and «the trace of the domain» are [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.8.

<!-- req: P/10-R264 -->
Of the steps of `identity` the domain console has steps 3 and 4; the domain console has no steps 1 and 2 — there is no emergency session and no unit doors.

<!-- req: P/10-R266 -->
Step 3 is the token of a human: the function `token` of [the domain token contract](../../common/contracts/domain-token.md) «The check» by the set and `domain/revoked` of its own store with `expect {kind: person, cluster: null}`; A refusal of this person-token check is 401 `{error: denied, detail: "token refused: <word>"}` (the form of P/06.3), except `no_revocations` and a row `domain/keys` that exists but does not read (there is nothing to check the token with): the rule «Unreadable row» of the gate-and-pass contract (503 `{error: "unavailable"}`).

<!-- req: P/10-R268 -->
The view doors, all the doors of the kept edit, reading people, roles, grants and editing the grants of a cluster are judged by the target cluster: «Judgement by target» of [the right contract](../../common/contracts/may.md). The other doors — the line `domain`.

<!-- req: P/10-R270 -->
The right is the line `domain` of [P/08.4 N1.5](../../08-domain/spec/08.4-domain.norms.md) (one line for the domain console and the process `domain`; the text is there): `may` ([the right contract](../../common/contracts/may.md)) by `domain/grants/domain` (exists but does not read — the rule «Unreadable row» of the gate-and-pass contract, 503 `unavailable`), `need` view/admin by door; the input `disabled` of the function `may` is the row `domain/disabled` at the holder, the read condition is the right contract (P/06.3 N1.3 «Data»; exists but does not read — the rule «Unreadable row», 503 `unavailable`); the input `roles` is the rows `domain/roles/*`, `domain/groups/*` of the holder, `as_of` — `null` (P/08.4 N1.3b `roles_at_holder`; an unreadable `domain/roles/admin` or a group from its `assigned` — 503, if the direct rows did not allow); the input `iat` is the token's.

<!-- req: P/10-R274 -->
The manager line (P/08.4 N1.3c `manager`) serves the gate only at the doors `gives`: `/domain/users…`, `/domain/groups…`, `/domain/roles…`, `/domain/batch`, `GET /domain/grants`, `PUT /domain/grants/<cluster>`, and also `/domain/break-glass…`: at this door the group is counted only so that the request reaches the process and it answers 403 `admin only` (P/08.4 N1.5, N1.3c `denies`); At doors outside this list, the manager line's group is not counted in `may`.

<!-- req: P/10-R276 -->
The domain doors have no subsystem: `sub` is `null`.

<!-- req: P/10-R277 -->
The lines `body_unit` and `session` are [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Rights by the body». The lines `body_unit` and `session` are common with the cluster console ([P/06.7](../../06-console/spec/06.7-console.norms.md), a chapter of the late layer), except the pre-check of `body_unit` before the body and the target of `door.pass` without `?unit=`: at the domain console — `"*"`, at the cluster console — a grant on anything (the contract, `body_unit`, `need` line `door.pass`);

<!-- req: P/10-R279 -->
`/session` and `/healthz` of the domain console are as at the cluster console (the gate-and-pass contract `session`; N1.7) (P/10-13).

<!-- req: P/10-R280 -->
The target of `door.pass` with `?unit=<sub>/<id>` is `scope` of the gate-and-pass contract as is: `*` and `unit:<sub>/<id>` of the unit itself are compared by name without a row; `labels:…` and `unit:` of an about-unit require the unit row, and the domain console does not read the unit rows of members (they are not in its «Data», N1; the view and the copies of reports do not serve as them) — such a grant does not cover, none covered — 403 by `refusal`; there is no substitution from the view or the cluster.

### N1.6 `door.pass` on the domain

<!-- req: P/10-R009 -->
**route** — /domain/\<sub\>/\<segment\>[/…], \<segment\> ∈ door.pass of the manifest \<sub\> (P/06.5 N1.8) — the domain console passes on to the worker on the domain of this subsystem (P/03.7 N1.6: the holder of the slot domain/\<sub\>/worker, role \<sub\>domain) the path /\<segment\>[/…] and query; **route** — the headers, the body, the answer, the codes — the gate-and-pass contract «Pass of `door.pass`»; **route** — the client is of the role domainconsole; **route** — a path with a segment `.`/`..` is not passed to the worker — 404 not a domain route (the forwarding contract «Domain doors»)

<!-- req: P/10-R287 -->
**address** — the url of the heartbeat of the worker on the domain — the object domain/\<sub\>/heartbeat (P/03.7 N1.6 heartbeat)

<!-- req: P/10-R288 -->
**holder** — the console reads the slot domain/\<sub\>/worker only as «a holder exists»: holder is non-empty and released = false (the slot contract «States»); **holder** — there is no holder — «not heard» (absent below); **holder** — freshness is only the heartbeat (LOST_AFTER, P/03.7 N1.6 heartbeat); **holder** — the console does not judge whether the instance of the heartbeat matches the holder of the slot or the age of the slot version (SLOT_TERM) — the validity of the operation is checked by the worker with its credentials and epoch, as at the cluster console (P/06.5 N1.8)

<!-- req: P/10-R292 -->
**absent** — the worker on the domain of this subsystem is not heard — 503 {error: "unavailable", detail: "no worker of \<sub\> with a door is heard"} (the words of the gate-and-pass contract, codes)

<!-- req: P/10-R293 -->
**member** — the cluster console forwards these paths to the domain console by a row of the list of domain doors of the forwarding contract The matching rule (`books`, `placement`, `members`, `topology`, `shadow`, `at` are not passed on on the domain) is the forwarding contract «Domain doors».

<!-- req: P/10-R295 -->
What the worker on the domain checks at an arrived route is [P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.6; the console passes `Authorization` on as it came.

<!-- req: P/10-R297 -->
**The second kind of `door.pass` on the domain** ([the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Pass of the second kind»). The domain console passes a manifest with the second kind on in the same way: a ticket instead of `Authorization`, the headers, the answer types, `refusals`, the stream.

<!-- req: P/10-R299 -->
The ticket is issued by an instance of the domain console, which remembers `jti`, `kid`, `exp` of the human's token; `user`, the closing of the request and the closing of the stream on a revocation of `jti`, on disabling the human and at `exp` — by the contract.

<!-- req: P/10-R301 -->
The token is checked by the domain token contract, and the grants — by `domain/grants/domain` (N1.5).

<!-- req: P/10-R302 -->
The client to the worker is of the role `domainconsole`, the addressee is the role `<sub>domain`.

<!-- req: P/10-R303 -->
There is no callback on the domain yet: the closed list of [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.9 names no doors `/domain/*`, therefore the domain console accepts the header `X-W2C-Pass-Ticket` only for a refusal, 401; the doors will enter the list with the increment of rights.

<!-- req: P/10-R305 -->
**All forwarding hops.** The [domain worker pass hop policy](../../common/contracts/forwarding.md#domain-worker-pass-hop-policy) is mandatory at every console on this path, including the holder and member consoles: confirmed-policy digest, finite waits including downstream execution, and the finite-buffer and stream rules of that policy. A mismatch returns 503 without calling the worker. After exposing client headers a break propagates bytes and closure, never a new `502` body. Ordinary platform routes retain their normal limits.

<!-- req: P/10-R309 -->
**Callback address header.** In this pass, the outgoing `X-W2C-Pass-Console` is absent, with or without a role kit. The same header received from outside is removed by `to_worker` of the gate-and-pass contract. `CONSOLE_CALL_PORT` names the callback listener of the cluster console; neither that URL nor the main `DOMAIN_CONSOLE_HOST/PORT` address is a callback address of this domain-console instance.

<!-- req: P/10-R313 -->
The ticket remains bound to the open request in memory by the contract above; an incoming `X-W2C-Pass-Ticket` at the domain console is refused with 401 as above.

### N1.7 The holder's page

<!-- req: P/10-R010 -->
**page** — GET /, /index.html — the published page of the console module (P/06.5 N1.1 `module`; the module contract — P/07 N1.5), which differs only by the argument of the call mount: opts.sections: [domain]; **page** — CSP — by the text of the served page (P/06.5); **page** — /platform/console.js, /platform/console.css — the bytes of the published module as is (P/06.5 N1.1)

<!-- req: P/10-R318 -->
**manifest** — GET /manifest → {"name": "", "rows": null} — there is no root

<!-- req: P/10-R319 -->
**mounts** — GET /mounts → {"root": "", "mounts": {\<sub\>: \<the description of P/06.5 N2 /mounts\>}} by the catalogue of the holder, without media; **mounts** — fields — as P/06.5 N2 «GET /manifest»: all the fields of unit.fields, *_secret included, their default is null

<!-- req: P/10-R321 -->
**session** — /session, /healthz — as at the cluster console (the gate-and-pass contract «The gate» session); **session** — server_time and timezone of GET /session — the same lines of the contract: the clock of the domain console and TIMEZONE of the environment of its box, empty or not by the form — a start refusal, code 2 (the environment file contract «Environment variables»)

<!-- req: P/10-R323 -->
**module** — which doors the module calls in the mode domain, and that its nodes are member:\<member\>, domain — a property of the published module (console.js — data of the specification; the late layer P/07 N1.6, the description — CONSOLE-MODULE.md §10a), not of implementations; **module** — the check is the module test at its owner; **module** — the acceptance of the lesson — only the doors of the page

### N1.8 The alarm list at the holder

<!-- req: P/10-R011 -->
The console assembles the alarms of members from their reports: it opens no connections to a member.

<!-- req: P/10-R327 -->
The history (chapter 8.9 N1.9) is written only by the process `domain`; the list only reads it.

<!-- req: P/10-R329 -->
The function `alarms` and its vector belong to this lesson.

<!-- req: P/10-R330 -->
**door** — GET /domain/alarms?since=&until= at the domain console (view); **door** — the default is ALARMS_WINDOW before now;

<!-- req: P/10-R332 -->
**door** — not finite numbers or since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}; **door** — the time is by the grammar of the reader time of the row codec after URL decoding (the gate-and-pass contract «Numeric query parameters»: 1e3, -1, «+», «_», a space — a refusal; the detail of the refusal is its own, above), the parameter is not repeated

<!-- req: P/10-R334 -->
**answer** — 200 {since, until, events, members, complete, sentence} — the function alarms (N3) on the page of the last report of each member of the list (the holder included), on the history (P/08.9 N1.9) and on the witnesses

<!-- req: P/10-R335 -->
**member_state** — ok | silent | not_reporting | never | unreadable

<!-- req: P/10-R336 -->
**silent** — the last report is older than this member's silent_after (the observation contract «Freshness»): server — LOST_AFTER, camera — 3 × every of its readable confirmed mark (absent every — REPORT_EVERY, by the report reception contract); **silent** — retry_in is not used here; **silent** — silent_since = last_report + the same silent_after

<!-- req: P/10-R339 -->
**not_reporting** — silent, and a witness heard a unit of the member later than the last report

<!-- req: P/10-R340 -->
**never** — there has never been a report

<!-- req: P/10-R341 -->
**unreadable** — the page is not by the form of P/09.1 N1.10 (at the function alarms — the input "garbled" too)

<!-- req: P/10-R342 -->
**silence_line** — A silent member has an alarm row `{t: silent_since, kind: silent | not_reporting, class: alarm, member, subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?}` — always, while it is silent.

<!-- removed: P/10-R343 by ADR-0133 -->

<!-- req: P/10-R344 -->
**witness** — domain.witness {report, member_field} (P/02.1 N1.2b): the objects \<sub\>/\<report\>/\<name\> = {ts, cluster, units: {\<member\>: seconds since the last time}} at the clusters and in the reports; **witness** — the family is the keys \<sub\>/\<report\>/\<name\> (the name after «/»), the agent carries each object of the family as a report object (P/09.1 N1.2 member_objects), the object \<sub\>/\<report\> without a name is not a witness (the agent's side — P/09.1 N1.10); **witness** — member_field — the fixed field of the unit that carries the name of the member (the load refusal — P/02.1 N1.2b);

<!-- req: P/10-R347 -->
**witness** — alive_at = ts − units[member], alive_via = "\<cluster\>/\<name\>"; **witness** — there are several witnesses — the largest alive_at among those later than last_report; **witness** — on a tie — the smaller alive_via in UTF-8 bytes ;

<!-- req: P/10-R350 -->
**witness** — ts in the worker object is its wall time.

<!-- req: P/10-R351 -->
**witness** — Before computing alive_at and choosing or breaking a tie, the collector shifts ts by received_at − sent_at of the same confirmed report that supplied this witness. **witness** — It never uses the mark of the member being witnessed, the current clock offset or another report

<!-- req: P/10-R353 -->
**clock** — the domain clock of the alarm rows — [the alarm history contract](../../common/contracts/alarm-history.md) «Domain clock»

<!-- req: P/10-R354 -->
**events_order** — by t descending, then member, id; **events_order** — the rows of the history — from_history: true

<!-- req: P/10-R356 -->
The member's alarm page and its front are [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N1.10; the mark `reported` — [chapter 8.3](../../08-domain/spec/08.3-domain.norms.md) N1.3; the history — chapter 8.9 N1.9 (`same_line`, `cut_before`).

---

## N2 Doors

<!-- req: P/10-R012 -->
The HTTP contract: [10-domain-console.api.openapi.yaml](10-domain-console.api.openapi.yaml).

<!-- req: P/10-R360 -->
The refusal body is `{error, detail}`.

<!-- req: P/10-R361 -->
The closed list of the doors of the domain console with the columns «Wait» and «Identity» is [the forwarding contract](../../common/contracts/forwarding.md) «Domain doors» (owner P/06, participants 8.0 and this lesson); each row there is a door of the domain console, it has no other door `/domain/*`.

<!-- req: P/10-R363 -->
Who answers a row:

**GET `/domain`, `/domain/members/<member>`, `/domain/folders`, `/domain/folders/<id>/units`, `/domain/memberof/<member>/<sub>/<rows>/<id>`, `/domain/<sub>/<rows>`, `/domain/<sub>/kept/<name>`, `/domain/relays/<relay>`, `/domain/<sub>/tables/<table>`, `/domain/shadow`, `/domain/members`, `/domain/topology`, `/domain/placement`, `/domain/placement/<sub>/<ref>`, `/domain/grants`, `/domain/shared`**

<!-- req: P/10-R364 -->
**Who answers** — the domain console itself

<!-- req: P/10-R365 -->
**Success** — N1.2

<!-- req: P/10-R366 -->
**Refusals** — N1.2, N4

**GET `/domain/alarms`**

<!-- req: P/10-R367 -->
**Who answers** — the domain console itself

<!-- req: P/10-R368 -->
**Success** — N1.8

<!-- req: P/10-R369 -->
**Refusals** — 400; **Refusals** — N4

**the other rows of the list (edits, people doors with any method, `POST /api/login`)**

<!-- req: P/10-R371 -->
**Who answers** — the process `domain` — the console passes on (N1.3)

<!-- req: P/10-R372 -->
**Success** — the answer of the process as it came (the chapters of lesson P/08)

<!-- req: P/10-R373 -->
**Refusals** — N4; **Refusals** — the codes of the process — the OpenAPI of lesson P/08

**`/domain/<sub>/<door.pass segment>[/…]`**

<!-- req: P/10-R375 -->
**Who answers** — the worker on the domain — the console passes on (N1.6)

<!-- req: P/10-R376 -->
**Success** — the answer of the worker as it came

<!-- req: P/10-R377 -->
**Refusals** — [the gate-and-pass contract](../../common/contracts/gate-and-pass.md) «Pass of `door.pass`»

**GET `/`, `/index.html`, `/platform/console.js`, `/platform/console.css`, `/manifest`, `/mounts`, `/session`, `/healthz`**

<!-- req: P/10-R378 -->
**Who answers** — the domain console itself

<!-- req: P/10-R379 -->
**Success** — N1.7

<!-- req: P/10-R380 -->
**Refusals** — [P/06.5](../../06-console/spec/06.5-console.norms.md); **Refusals** — `/session` — the gate-and-pass contract

<!-- req: P/10-R382 -->
Every named method/path pair in the closed forwarding list has an OpenAPI operation here, including GET of one member, POST edits and stranded edits, folder/membership/role-line operations, the book-part GET and POST verify. HEAD follows every GET.

<!-- req: P/10-R384 -->
The book-part GET reaches the process domain, not the worker;

<!-- req: P/10-R385 -->
POST /domain/verify reaches /api/verify under its existing X-W2C-Ticket admission. The latter header is distinct from the forbidden X-W2C-Pass-Ticket callback.

<!-- req: P/10-R387 -->
Request forms, success forms, conditional 412, RepeatKey and writer refusals are references to their P/08 owners; the domain console does not invent another schema or swallow a writer refusal.

<!-- req: P/10-R389 -->
A path with a segment `.` or `..` (percent-encoded too) — 404 `not a domain route` before the gate, before the passing to the process and to the worker on the domain (the forwarding contract «Domain doors»).

---

## N3 Procedures

### accept the forwarding and pass on to the process (the domain console)

<!-- req: P/10-R013 -->
The lesson introduces no order of checks of its own: each place is set by its own norm. «Accept by a console» is [the forwarding contract](../../common/contracts/forwarding.md) «Accept by a console» (N1.4);

<!-- req: P/10-R391 -->
the refusals of the role door are before the gate (N1.4 `server.role`);

<!-- req: P/10-R392 -->
a path with `.`/`..` — 404 before the gate (N2);

<!-- req: P/10-R393 -->
the gate — N1.5;

<!-- req: P/10-R394 -->
further — its own read door (N1.2, N1.8), `door.pass` (N1.6) or the passing to the process `domain` (N1.3 `pass`): the answer of the process is as it came, a break and silence — 502.

### alarms(input)

<!-- req: P/10-R014 -->
The filter is at the door, the form is at the function: the alarm door assembles the input from the store and discards a broken witness (without ts and the like) with a counter before the call — resilience;

<!-- req: P/10-R396 -->
the vector alarms receives an already assembled input, and a witness not by the form in it is an input not by the form, code 2. One does not contradict the other.

<!-- req: P/10-R398 -->
A mark `domain/members/<member>/reported` whose read the store did not confirm — 503 `unavailable` of the whole door;

<!-- req: P/10-R399 -->
a mark read but not by the form — the member enters the function with `reported: "garbled"`.

<!-- req: P/10-R400 -->
The input is assembled from the store of the holder: `last_report` is `received_at` of the mark, `received_at` and `sent_at` are the fields of the last request of the mark ([P/08.3](../../08-domain/spec/08.3-domain.norms.md) N1.3; the domain clock), not the age of the console's observation;

<!-- req: P/10-R401 -->
the members are the row `domain/member-rows/<part>`: there is none — 404 `no domain here` (like `GET /domain/members`, N1.2b), it does not read or the read is not confirmed — 503 `unavailable` of the whole door, not an empty list;

<!-- req: P/10-R402 -->
the mark is read, and the generation `reports/<rev>` of the mark does not exist or it is not with its `sha256` — `page: "garbled"` (the member is `unreadable`, the witnesses of this report are not taken), not `page: null`: «no page» is only for a readable generation without a page.

<!-- req: P/10-R403 -->
The collector always supplies each member's `silent_after` from its accepted Entry class and confirmed mark as in N1.8.

<!-- req: P/10-R404 -->
For an accepted Entry of class camera, confirmed absence of the mark or a confirmed whole unreadable mark supplies `silent_after = 3 * REPORT_EVERY` from the existing report-period owner. The collector does not read `every` partially from a rejected mark, use a cache, substitute server `LOST_AFTER`, or omit the field.

<!-- req: P/10-R406 -->
This completes the input form: confirmed absence remains `never`;

<!-- req: P/10-R407 -->
a whole unreadable mark remains `unreadable` at 200 without silence/page, known_until or silent_since;

<!-- req: P/10-R408 -->
an unconfirmed read remains 503 `unavailable` of the whole door.

<!-- req: P/10-R409 -->
It normalizes each witness's `ts` using the originating report's offset before passing it to the function; the native input's witness `ts` is already domain time.

<!-- req: P/10-R411 -->
The function must not shift it again.

```text
input:  {now, since, until, lost_after, members: {<member>: {last_report: <domain clock> | null, received_at, sent_at, page: <P/09.1 N1.10> |
         "garbled" | null, history: <P/08.9 N1.9> | null, silent_after} | {reported: "garbled", page?, history?, silent_after}}, witnesses: [{sub, name, ts, cluster, units}]}
```

<!-- req: P/10-R412 -->
silent_after: a required finite positive JSON number in either member form. The function infers no Entry class from its input.

<!-- req: P/10-R414 -->
Validate the complete known input, including this field, before the steps; a missing or malformed value is code 2, even on reported = "garbled". There is no fallback to lost_after.

**1. Each member.**

<!-- req: P/10-R417 -->
reported = "garbled" (the mark is read, not by the form) → unreadable; For reported = "garbled", there are no silence row and no page rows of this member, no known_until and no silent_since.

<!-- req: P/10-R419 -->
no last_report and no page → never

<!-- req: P/10-R420 -->
no last_report, but a page → an input not by the form (code 2): a page comes only with a report

<!-- req: P/10-R421 -->
page = "garbled" or not by the form of P/09.1 N1.10 → unreadable; not by the form is also a row without id, class ≠ alarm, kind empty, unit not a string, from > to

<!-- req: P/10-R423 -->
now − last_report > silent_after → silent;

<!-- req: P/10-R424 -->
For a silent member, a witness with ts − units[member] > last_report — not_reporting.

<!-- req: P/10-R425 -->
otherwise → ok

<!-- req: P/10-R426 -->
page = null with last_report — there is no page: there are no page rows, not unreadable

<!-- req: P/10-R427 -->
2. rows: the page (the clock of N1.8 clock) ∪ the history (from_history, t as stored) without repeats by same_line — present in both, the page row is taken; a repeat inside one page — the first in the order of the page;

<!-- req: P/10-R429 -->
the silence row — N1.8 silence_line; the window [since, until] — for all rows, the silence row too

<!-- req: P/10-R431 -->
3. members: {\<member\>: {state, truncated?, known_until?, silent_since?, alive_at?, alive_via?, history_cut_before?}}; truncated: true — for a readable page with truncated; known_until — last_report for silent/not_reporting; history_cut_before — for a history with cut_before > since

<!-- req: P/10-R435 -->
4. complete = all ok;

<!-- req: P/10-R436 -->
sentence — «every member answered» or phrases joined by «; », by members (UTF-8 bytes), for a member — in the order of the list below:

```text
«<m> silent since <HH:MM> — its alarms from its last report, known up to <HH:MM> UTC; none known since»
«… — but <alive_via> heard of it at <HH:MM>: alive, and not reporting to the domain»
«<m> has never reported to the domain»; «<m>'s page of alarms does not read»
«<m> had more alarms than one page holds; showing its newest»
«<m> had an alarm storm: the domain keeps only its newest alarms, and what came before <HH:MM> UTC is not known in full»
```

<!-- req: P/10-R437 -->
(the time is UTC of the domain clock)

<!-- req: P/10-R438 -->
`same_line`, a repeat in a page and `cut_before` are [the alarm history contract](../../common/contracts/alarm-history.md).

<!-- req: P/10-R439 -->
**Races.** A member without a connection and an alarm storm — [chapter 9.1](../../09-agent/spec/09.1-agent.norms.md) N3 «Races».

---

## N4 Refusals

<!-- req: P/10-R015 -->
The codes of transition 2 are the reception and the passing ([the forwarding contract](../../common/contracts/forwarding.md) «Refusals by transition»); each OpenAPI carries only its own codes.

<!-- req: P/10-R442 -->
The codes of transition 3 (the process `domain`: the codes of its own door, `409 deposed`, `503 frozen`, `503 standby`) the console serves as they came — the OpenAPI of lesson [P/08](../../08-domain/spec/08-domain.api.openapi.yaml);

<!-- req: P/10-R443 -->
the codes of transitions 1–2 from the forwarding side are the cluster console (chapter P/06.7).

<!-- req: P/10-R444 -->
[The refusal catalogue](../forms/refusals.tsv) is the normative table: chapter=10; row is the stable N4 row number. word/outcome/cause define the refusal word, outcome and condition; a compound code has one projection per code. The [form grammar](../forms/README.md#refusal-catalogue) defines the imported startup, callback and native-command rows and the HTTP response schemas.

<!-- req: P/10-R449 -->
The words of its own doors are the closed list [`refusal-words.tsv`](../data/refusal-words.tsv); the rules are [P/08.0](../../08-domain/spec/08.0-domain.norms.md) N4. The row 15 of the form (word «—»): 400 — `refused`, 404 — `no such path`, placements — `refused`.

<!-- req: P/10-R452 -->
Its own doors have no `field`: they read, they have no body; at the doors of transition 3 — the answer of the process `domain` as it came.

<!-- req: P/10-R454 -->
The words of `peer` are [the `peer` contract](../../common/contracts/peer.md) «Refusal words».

---

## N5 Acceptance

<!-- req: P/10-R016 -->
The catalogue [`acceptance/`](../acceptance/README.md) uses the stand of several clusters of chapter 8.3 (`hold`, `m1`, `m2`, the catalogue `testsub`), scenarios 02 and 05–19. Scenario 17 checks row versions at the read doors; 18 and 19 check the `kept` and relay doors.

<!-- req: P/10-R458 -->
The alarm list is the vector [`vectors/alarms`](../vectors/alarms/README.md), 37 rows, including missing required `silent_after`.

<!-- req: P/10-R459 -->
**alarms** — the input — N3 alarms; **alarms** — the output {events, members, complete, sentence}

<!-- req: P/10-R461 -->
**exit** — 0 — computed;

<!-- req: P/10-R462 -->
**exit** — 2 — an input not by the form (lost_after, a member name, page without last_report, sent_at null at a member with a report, history with cut_before null, a witness without ts, reported together with last_report, an extra field, a missing or malformed silent_after in either member form; the other cases — by reading; a page [], from > to, a row without id — 0 unreadable, the rows alarms-24…26); **exit** — the exit codes are by the principle of «Domain stand» of the common README of acceptance («Exit codes of vector commands»: 2 — the form of a trusted input, 0 with a word — a document of another cluster).

<!-- req: P/10-R464 -->
**exit** — Not by the form at alarms: a member name not by the member grammar, lost_after not > 0, silent_after absent or not a finite positive number (boolean and null are not numbers), a history or a witness not by the form of P/08.9 N1.9 and N1.8 (a history without cut_before or with cut_before null — too, P/08.9 N1.9), a page object without received_at and sent_at, no received_at or sent_at at a member with a report, a history as a string, a witness without ts, witnesses not a list, now not a number, an extra field; **exit** — reported — not "garbled", or together with last_report, received_at, sent_at;

<!-- req: P/10-R466 -->
**exit** — a page that is not an object ([], a number) or not by the form of P/09.1 N1.10 — 0 unreadable, not 2;

<!-- req: P/10-R467 -->
**exit** — page null with last_report, received_at and sent_at null at never — 0

| № | Scenario | Norms |
|---|---|---|
| 02 | `02-silent-member` | N1.8; N1.2f |
| 05 | `05-the-holders-page` | N1.7 |
| 06 | `06-no-domain-here` | N1.2a, N1.2b, N1.2c, N1.2f; N4 |
| 07 | `07-view-unreadable` | N1.2a, N1.2b, N1.2f; N4 |
| 08 | `08-pass-process-down` | N1.3 `pass`, N1.3a; N4 |
| 09 | `09-pass-process-silent` | N1.3 `pass`; N4 |
| 10 | `10-read-doors-head-and-query` | N1.2, N1.2a; N4 |
| 11 | `11-topology-placement-unreadable` | N1.2c, N1.2d; N4 |
| 12 | `12-shared-and-members-unreadable` | N1.2b, N1.2f, N3 `alarms`; N4 |
| 13 | `13-alarms-query-lexemes` | N1.8 `door`; N4 |
| 14 | `14-alarms-mark-unreadable` | N3 `alarms` |
| 15 | `15-dot-segments-and-x-user` | N2, N1.4, N1.5; N4 |
| 16 | `16-gate-rows-unreadable` | N1.5; N4 |
| 17 | `17-read-versions` | N1.2; the forwarding contract `pass`, `answer`; P/08.0 N1.9 |
| 18 | `18-kept-door` | N1.2a; P/06.2 N1.4 |
| 19 | `19-relay-door` | N1.2a; P/08.3 N1.2 |

<!-- req: P/10-R468 -->
Detailed case descriptions and their expected outcomes are the judge's case data. The scenario numbers and names below refer to those descriptions.

<!-- req: P/10-R469 -->
Governing rules and the public acceptance scope remain in this chapter.

<!-- req: P/10-R470 -->
The doors of the lesson on the stand of the chapters of lesson P/08 are neighbours on the stand (the rule «scenario — in the chapter of its outcome, neighbours — on the stand»):

| Norm | Scenarios |
|---|---|
| P/10-01 | sc. 05 of the acceptance of [chapter 8.3](../../08-domain/acceptance/3/README.md); sc. 06, 09 of the acceptance of [chapter 8.1](../../08-domain/acceptance/1/README.md) |
| P/10-02 | sc. 01, 02 of the acceptance of chapter 8.3; the stands of chapters 8.3 (topology), [8.6](../../08-domain/acceptance/6/README.md), [8.8](../../08-domain/acceptance/8/README.md), [8.9](../../08-domain/acceptance/9/README.md) through `holder` |
| P/10-05, P/10-13 | sc. 01, 02 of the acceptance of [chapter 8.4](../../08-domain/acceptance/4/README.md) |
| P/10-07 | sc. 14 step 6 and sc. 04 step 16 of the acceptance of chapter 8.3; sc. 19 of the acceptance of chapter 8.3 (the source of `members`, `knocking` by default); sc. 02 of the acceptance of chapter 8.8 |
| P/10-08 | sc. 15 step 2 of the acceptance of chapter 8.3 |
| P/10-09 | sc. 01 step 2, sc. 09 step 12 of the acceptance of chapter 8.6; sc. 01 step 7 of the acceptance of chapter 6.7 |
| P/10-12 | sc. 02, 08 of the acceptance of chapter 8.4 |
| P/10-14 | sc. 01 steps 2, 14 of the acceptance of chapter 8.9; sc. 02 steps 04, 09 of this lesson |

<!-- req: P/10-R471 -->
Checked by reading: `door.pass` on the domain (N1.6) — the stand has no worker on the domain;

<!-- req: P/10-R472 -->
Checked by reading: «accept by a console» and the role door (N1.4) — until the TLS stand.

<!-- req: P/10-R473 -->
Checked by reading: the reader's side of the manifest row at start (N1.1) — the domain console has no step in acceptance.

<!-- req: P/10-R474 -->
Checked by reading: the deadline «Wait» of the passing (502 on silence not earlier than the deadline) and `answer broke off` — acceptance does not measure the answer time and does not break the answer of the process (502 on a break and on silence — sc. 08, 09).

<!-- req: P/10-R475 -->
Checked by reading: `not in the directory` — the manifests of the stand have `domain.ref`.

<!-- req: P/10-R476 -->
Checked by reading: that the domain console does not recompute `deposed`, `frozen`, `standby` (N1.3) — the stands of chapters 8.8, 8.10 through `holder`.

<!-- req: P/10-R477 -->
Checked by reading: the role journal — acceptance does not compare the journal.

<!-- req: P/10-R478 -->
Checked by reading: the carriage of the witness family in the member report (N1.8 `witness`).

<!-- req: P/10-R479 -->
Checked by reading: the cases with no row `domain/placement`, and no row `domain/keys` with a trace of the domain (`shut`) — the door `admin.sock` cannot remove a row under `domain/` (P/01.2 N1.3 `never`).

<!-- req: P/10-R480 -->
Checked by reading: a generation `reports/<rev>` not matching the mark's `sha256` — the key carries `rev` of the mark, the directive `@spoil object` takes the key as is.

<!-- req: P/10-R481 -->
Checked by reading: `X-Operator: console` at a proven role — until the TLS stand.

<!-- req: P/10-R482 -->
The TLS stand ([`common/acceptance/tls/`](../../common/acceptance/tls/README.md)): the probes of the door `holder` (class `role`) belong to this lesson, P/10-11: item 2 (9 rows of `holder`), item 7, «change of union» (2 probes), item 8 steps 2–5. The lesson gets the scenarios when the stand is ready.

<!-- req: P/10-R484 -->
The machine-readable kit assistance is [stages.tsv](../forms/stages.tsv) and the CALL seams, with the port/fixture contract in [forms/README.md](../forms/README.md). This assistance does not replace the ordinary scenarios, vectors, neighbours, the TLS stand or reading of N5.

---

<!-- req: P/10-R017 -->

## Implementation decides

1. **the command `alarms`** — a template with `{input}` (the vector `alarms`;
   the command `resolve` — the cluster console, chapter P/06.7).

---

## Readiness checklist

An implementation corresponds to the lesson when each norm is fulfilled; each checklist item has the stable id `P/10-MM`.

- [ ] **P/10-01** [test, stand, reading] the view doors `GET /domain` (with `age` by the wall clock of the console), `/domain/<sub>/<rows>[?cluster=]`, `/domain/<sub>/<rows>?part=` — sc. 10, `/domain/<sub>/tables/<table>?cluster=`, `/domain/shadow` and their refusals `no domain here`, `unavailable` (an unreadable view and shadow), `not in the directory`, `no such member` (N1.2a) — a neighbour on the stand of chapters 8.3 (sc. 05) and 8.1 (sc. 06, 09); `no domain here` — sc. 06, `unavailable` — sc. 07 (and at `/domain/members`, `/domain/shared`); `HEAD`, `?cluster=` empty or twice, there is no manifest, `rows` is not its own — sc. 10; `not in the directory` — by reading (the manifests of the stand have `domain.ref`); the content of the view — chapter 8.1
- [ ] **P/10-02** [test, stand, reading] passing the edits on to the process `domain` N1.3: the method, the path, the body, the headers as they came, `X-W2C-Client` is set by the console (the forwarding contract «Client address»), the deadline — «Wait» of the row, the answer as it came, 502 on a break and on silence — a neighbour on the stand of chapters 8.3 (sc. 01, 02), 8.6, 8.8, 8.9; 502 `did not answer` on a break — sc. 08, on silence — sc. 09 (`@freeze`); the deadline «Wait» and `answer broke off` — by reading; the reception — P/08.0-01
- [ ] **P/10-03** [test, reading] `door.pass` on the domain N1.6: `route`, `address`, `absent`, the segments `.`/`..` — 404; the rule and the codes — the gate-and-pass contract «Pass of `door.pass`» — by reading (the stand has no worker on the domain); the segments `.`/`..` at the doors of the domain console — 404 `not a domain route` before the gate (N2) — sc. 15
- [ ] **P/10-04** [test, reading] the holder's page N1.7: `/`, the module, CSP, `/manifest` `{"name": "", "rows": null}`, `/mounts`, `/session` with `server_time`, `timezone`, `/healthz` — sc. 05; `TIMEZONE` not by default and the start refusal by it — by reading (the stand starts the domain console without this variable); the calls of the module in the mode `domain` — the module test at its owner ([P/07](../../07-console-module/spec/07-console-module.norms.md) N1.6, N5)
- [ ] **P/10-05** [stand] the people doors through the domain console to the process `domain` with any method, the edits of grants and `/domain/revoke` — the passing (N1.3a) — a neighbour on the stand of chapter 8.4 (sc. 01, 02); the check at the process — P/08.4-09
- [ ] **P/10-06** [test, reading] the alarm list N1.8: the states, the silence row, the witness, the clock `clock`, the order, the strictness of the page, the tie of witnesses, the function `alarms` N3 — sc. 02, the vector `alarms` (codes 2, a page not by the form, the window and the silence row — rows 17–27); the grammar of `since`/`until` — sc. 13; an unreadable `domain/member-rows/<part>` — sc. 12, the mark `reported` — sc. 14; the family of witnesses in the report and a generation not by the `sha256` of the mark — by reading; the history is written by chapter 8.9 (P/08.9-05)
- [ ] **P/10-07** [test, stand] `GET /domain/members` → `{members, parts, knocking, count, cursor?}` (N1.2b) — a neighbour on the stand of chapters 8.3 (sc. 14 step 6, sc. 04 step 16) and 8.8 (sc. 02); the source of `members` and `knocking` by default — sc. 19 of the acceptance of chapter 8.3 (`19-members-source`); the row `domain/member-rows/<part>` does not read — 503 — sc. 12
- [ ] **P/10-08** [test, stand] `GET /domain/topology` — from the row, not from the view: right after a PUT — the new `rev` (N1.2c) — a neighbour on the stand of chapter 8.3 (sc. 15 step 2); the row does not read — 503 — sc. 11
- [ ] **P/10-09** [test, stand, reading] `GET /domain/placement`, `/domain/placement/<sub>/<ref>` — the console answers itself (N1.2d) — a neighbour on the stand of chapter 8.6 (sc. 01 step 2, sc. 09 step 12) and of chapter 6.7 (sc. 01 step 7); the counter and the record do not read — 503, there is no record or manifest — 404 — sc. 11; there is no counter (`rev` 0) — by reading
- [ ] **P/10-10** [test, reading] «accept by a console» at the domain console (N1.4): `X-Operator: console` — only at a proven role, the arrived `X-User` and `X-W2C-Client` are stripped (the forwarding contract) — by reading (until the TLS stand); the stripping of `X-User` — sc. 15
- [ ] **P/10-11** [reading, stand] the role door of TLS `server.role` (N1.4): the union of CAs by `ca-certs` and `Entry.ca` plus its own CA, a refusal by the handshake, 401/403 `no_role`, `wrong_role`, `bad_chain` before the gate, without session resumption, EKU `clientAuth` — by reading; the TLS stand item 2 (`holder`), item 7, «change of union», item 8 — when the stand is ready
- [ ] **P/10-12** [stand] `GET /domain/grants` → `{grants: {<cluster>: [line…]}}` (N1.2e) — a neighbour on the stand of chapter 8.4 (sc. 02, 08)
- [ ] **P/10-13** [test, stand] the gate of the domain console (N1.5): the steps of `identity` 3 and 4, the token `kind: person`, `may` by `domain/grants/domain` (`as_of` null), `need` view/admin by door, `body_unit`, `grants` in `/session`; a participant of the gate-and-pass contract — a neighbour on the stand of chapter 8.4 (sc. 01, 02); `grants` in `/session` of the domain console — sc. 15; «Unreadable row» (`domain/disabled`, `domain/revoked`, `domain/grants/domain`, `domain/keys`) — sc. 16
- [ ] **P/10-14** [test, stand] `GET /domain/shared` → `{doc, delivery, declared}` (N1.2f; `view.shared` is built by chapter 8.9) — sc. 02 steps 04, 09; a neighbour on the stand of chapter 8.9 (sc. 01 steps 2, 14); the pointer does not read — 503 — sc. 12
- [ ] **P/10-15** [reading] the start (N1.1): the reader's side of the manifest row (P/02.3 N3), the schema check (P/06.6 N3), readiness — the port (P/02.4 N1.12) — by reading
- [ ] **P/10-16** [reading] `door.pass` of the second kind on the domain (N1.6): the ticket remembers `jti`, `kid`, `exp`, the stream is closed on a revocation, on disabling and at `exp`, two tokens, one revoked — the ticket of the first is 401, of the second works; the ticket header on the domain — 401 — by reading: the stand has no worker on the domain
- [ ] **P/10-17** [test] the row version at the read doors N1.2 : `ETag` of the doors of one row, `index` and `versions` of the lists; the headers of the version and of the memory through forwarding and passing — sc. 17

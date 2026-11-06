# P/07 — Console module: norms

This English text is the source; the Russian translation `ru/spec/07-console-module.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The canon of the lesson. Lecture (`ru/07-console-module.md`, for people, not in the export), [instructions](07-console-module.README.md). The lesson has no HTTP contract
of its own: the module is a library in the browser, it has no door of its own (N2); the doors it calls are the [contract of lesson
6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer (N1.6) also the contracts of lessons
[8](../../08-domain/spec/08-domain.api.openapi.yaml) and [10](../../10-domain-console/spec/10-domain-console.api.openapi.yaml). The lesson has no acceptance catalogue (N5); it has no life cycle: a library has no process,
environment or exit codes; the publication of the module is [chapter 6.5](../../06-console/spec/06.5-console.norms.md)
(the move plan of lesson 7, V4). The lesson is moved from M10/9 (stage B,
ADR-0083 addendum (1): without a change of behaviour): N1.4 and N1.5 (the numbers of the subsections are the former numbers of M10/9), the row of N5 «module by contract»,
the checklist items M10/9-06, -07. The late layer — the domain section, `sections: [domain]` of the call `mount`, the
holder mode — is N1.6, without ids of its own (plan, V5); its text was moved by the move of lessons 8–10 (stage B, commit 10; the move plan
of lesson 8, § 5, row P/07 N1.6) from M11/8 N1.8 `module`, M11/11 N1.6 `declared` and the module description § 7, § 10a. The canon of the module is the norms N1.5 (review analysis of stage A 6–7, № 6): the published
bytes of `console.js`, `console.html` and the description [`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) were brought
to it by a change of behaviour after the commit of the lesson («Implementation decides» item 1, closed; the Architect's decision of 2026-10-21). The three parts of the console, the mounting
`PlatformConsole.mount(root, opts)`, `opts`, `never` of the module and `may`/`may_not` of the shell — [P/06.5 N1.1](../../06-console/spec/06.5-console.norms.md)
`module`, `shell`. A reference «lesson N» without a chapter is the module lesson P/NN (M10 and M11 were moved whole; review analysis of stage B 3–5, № 34); «P/06.K», «P/08.K» are the chapters of lessons 6 and 8;
«P/10» is the lesson of the domain console. Norm ids are `P/07-MM`; the map to former ids is `id-map.tsv` (historical record).

## N0 Vocabulary

Normative words follow the [course canon](../../common/NORMATIVE-TERMS.md). The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

## N1 Form

**Time.** The lesson has no time fields in rows and objects: the module writes no rows and no objects (below). Time in the answers of the doors
that it shows (`until` of the session, `expires` of the door from `where()`) has the form of [P/06.3](../../06-console/spec/06.3-console.norms.md)
and [P/06.5](../../06-console/spec/06.5-console.norms.md).

**Data.** The lesson has no rows, objects or files of its own: the module reads and writes only through the doors of the closed list N1.4 —
the doors of lesson 6, in the late layer (N1.6) also the doors of the domain: `/domain/*` and the login `login_url` (`POST /api/login`) — the doors
of the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md); the process `domain` — [lesson
P/08](../../08-domain/spec/08-domain.api.openapi.yaml)), which the cluster console forwards
([chapter P/06.7](../../06-console/spec/06.7-console.norms.md); the [forwarding contract](../../common/contracts/forwarding.md) «Domain doors»),
and the own doors of the cluster console `/api/held`, `/domain/shared/<sub>` (chapter P/06.7) (review analysis of stage B 6–7,
№ 30; Claude M-5); the forms — the [contract of lesson 6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer — the contracts
of lessons 8 and 10; the owners of the rows — the chapters of lessons 6, 8 and their catalogue.

### N1.4 What the module calls — a closed list

```yaml
reads:   /session, /manifest, /<sub>/manifest, /mounts, /changes, /<rows>, /<sub>/<rows>, /<sub>/<table> (only from servers.show; added by M10/10),
         /where/<id>, /<sub>/where/<id>, /servers, /unplaceable, /<sub>/unplaceable, /policy, /drain, /schema (added by M10/10),
         /events, /metrics (only running_gauge and workers_gauge), /domain/* (forwarding contract «Domain doors»), /api/held (P/06.7-14), /domain/shared/<sub> (P/06.7-15), /folders (only with display.tree.folders)
writes:  POST/PUT/DELETE /<rows>[/<id>] and /<sub>/<rows>[/<id>], POST /folders, PUT/DELETE /folders/<id> (only with display.tree.folders), POST /marks, PUT /policy, POST/DELETE /drain, GET/PUT/DELETE /servers/<s>/labels,
         POST/DELETE /servers/<s>/decommission, /domain/* (forwarding contract «Domain doors»), POST/DELETE /session, /session/break-glass, login_url
never:   /{sub}/requests, /api/backup (P/06.7-16), /resources, /{sub}/{table} outside show, the doors of the holders (door from where — only to the shell)
order:   /session → /manifest → /mounts → /changes (only on mounting) → per subsystem /<rows> → /folders (if at least one subsystem declared display.tree.folders) → /servers → /unplaceable → /domain/shared/<sub> (P/06.7-15) → /drain → /schema
         → /domain (+ /domain/alarms; P/10-06) → /api/held (P/06.7-14) → /metrics; polling every poll_s; /events?unit= of the selected one — every 5 s
subsystems: opts.subsystems — the names of the subsystems of the catalogue (the root and /mounts) whose units the module loads, shows as a tree and writes
         (/<rows>, /<sub>/<rows>, the card, the forms); no key — all; a list — only the named ones; [] — none (ADR-0112 addendum (23) item 2)
unplaceable: /unplaceable and /<sub>/unplaceable the module reads from all subsystems of the catalogue, regardless of opts.subsystems, and only for
         reading: an unplaced unit of a subsystem outside opts.subsystems — as a row of the section (subsystem, id, reason) without a card
         and without actions; otherwise the unplaced units of the subsystems that the page does not show are visible nowhere (ADR-0112 addendum (23) item 1)
changes: the feed GET /changes (P/06.1 N2 «Change feed»; ADR-0094 B2): the module takes a number before the first read of rows, then holds the request /changes?after=<number>&wait=15,
         a new request is issued at most once a second after an immediate return or a disconnect; this does not shorten the held wait=15 request. A reset or a message about a row of a subsystem of the page — the same load `order` at once, silently: the page sees the edit within a tick, not within poll_s.
         The message carries no value, so the module rereads the rows instead of applying the message; it need not compare revision.
         404 — the console has no feed: the module no longer calls it and lives by polling; another refusal or a dropped connection — the next attempt after poll_s, without the login window (polling raises it).
         Without `after` (no number yet) the answer counts as a reset. The holder page (N1.6 `holder`) does not call the feed: the domain console has none.
         Polling by poll_s remains: GET /<rows> also carries the heartbeats, and /servers and /metrics have no feed (ADR-0094 B2: the scope — the rows of units and of tables)
```

The list is about the module's own calls: `never` forbids them to the module, not to the page; a call of the page through `console.api`
(the VMS page — `POST /<sub>/requests`, the requests door P/06.4) is its call, not the module's (C07-API-RETRY-UNITS-ONLY-01).
The words `servers.show`, `console.running` (`running_gauge`, `workers_gauge`) and `poll_s` — [P/06.5](../../06-console/spec/06.5-console.norms.md)
N1.1, N1.2. The parts of the list that the domain introduces (`/domain/*`, `/api/held`, `/domain/shared/<sub>`, `/domain/alarms`,
`login_url`) are the late layer N1.6.

### N1.5 The contract of the module with the shell

```yaml
module:    one module object — PlatformConsole {version, features, mount}; mount(root, opts) returns the page object
           (pc — the name of the page variable in the examples, not a second object) (ADR-0091 addendum (27) item 3)
version:   console.version — an integer, the version of the shell API (P/06.5 N1.1 version); it is checked before the module is used;
           it stays 1: the new things below (features, ready, select with tab, card.closed) are only added, the load ?v=1 is the same
           (ADR-0091 addendum (25) item 1)
features:  PlatformConsole.features — a list of strings of capabilities beyond the first calls of version 1: "select.tab", "card.closed",
           "api.if-match" (ADR-0091 addendum (28), (29)), "placement.if-match", "session", "tree.repaint";
           no string — no capability; the page learns of the new by it, not by the version (ADR-0091 addendum (25) item 1)
ready:     pc.ready — a promise (Promise), no new call: it resolves with the page object after mount and the first read
           /manifest (there is no door /spec — N1.4); the answer 401 — the promise waits for the login and resolves after it; /manifest not
           read (network, 5xx) — the module reads it again by polling, the promise waits (ADR-0091 addendum (24) item 1, addendum (27) item 1)
objects:   ref: unit:<sub>/<id> | server:<s> | worker:<sub>/<w> | member:<m> | domain | person:<name> | group:<sub>/<field>/<path> | folder:<id>
           | <prefix>:<…> of the shell (the module only stores it)
api:       console.api(method, path, body, opts?) → answer | throw {status, body, retry}
           the closed door list and the ifMatch type below apply to page calls through console.api; the module
           makes its own writes by N1.4 writes (ADR-0129 addendum (7))
           opts.ifMatch — an integer ≥ 1 (revision, P/06.1 N2 «Versions») → the header If-Match; only at the doors that read it (others
           would write without CAS): PUT and DELETE of a unit row /<rows>/<id>; POST /<t> and DELETE /<t>/<name> of a subsystem table;
           PUT /policy; POST and DELETE /drain; PUT and DELETE /servers/<s>/labels; PUT /schema (ADR-0094 B4); PUT and DELETE /domain/placement/<sub>/<ref>: revision — the rev of the record, P/08.6 N2 (features "placement.if-match", C07-PLACEMENT-IF-MATCH-01). The module recognizes a table by
           the form of the path: one or two segments after the prefix of the subsystem, the first is neither unit.rows nor the name of a platform door (P/02.1 N1.2a): the view
           /manifest does not name the tables. ifMatch does not carry the index: a page that needs the index writes by the batch door with cas.
           Another method, another path, a field of opts other than ifMatch,
           ifMatch not an integer ≥ 1 — the call is refused before the request; the module sends no other headers; 412 → throw {status: 412, body —
           as received, retry: false}; the other HTTP errors and the replay rules — below, as before; a page without "api.if-match" in
           features makes no write by version (ADR-0091 addendum (28), (29))
           POST with the repeat memory of the owner (unit rows /<rows>, /<sub>/<rows> — P/06.1) — one key per logical action, not per equal bytes;
           the replays of this action keep the key and an immutable snapshot of the original serialized body, including manual Retry after the caller has changed its object or nested values. A new call — a new key. Network/timeout 20 s for each attempt through the complete response body (not only headers)/5xx/
           409 in flight allow a replay only at these doors (above): the module itself replays only unit rows; the door
           of requests (P/06.4), which the page calls through api, — not (C07-API-RETRY-UNITS-ONLY-01); the delay before a replay — the header
           Retry-After of the answer (seconds), without it — 2, 3, 5 s, after the third replay — throw (review analysis of stage B 6–7,
           № 27); 401 → the login window.
           PUT, DELETE and tables the module does not replay automatically, even with a repeat memory of the door (P/06.1 N3 «repeat memory»): on an unknown outcome — a read first.
           A completed answer closes the action; a refusal before the memory of the request is handled by the contract of the owner, it is not cached as a success
forms:     the unit form (unitForm) and the creation form: a 412 with body.row takes priority and uses the W.rowMoved screen below; other refusals 400, 409, 412 with the field field of the body (JSON Pointer, P/06.1 N2 «Refusal: error and
           field»; ADR-0094 B5) the module shows at the field: the first token of the pointer, parsed by RFC 6901 (~1 → /, ~0 → ~), is the name
           of a form element; the control gets aria-invalid="true", next to it an element .pc-field-err with the text of the refusal (detail, no
           detail — error), the control gets the focus. No such element in the form or no field in the body — the text in the common .pc-err, as
           before. A new submission removes the marks. The code does not parse the refusal: the word and field come as fields of the body
           the unit form (unitForm) sends PUT and DELETE with ifMatch — the revision of the shown row, always (ADR-0094 B4; ADR-0091 addendum (28) item 3): otherwise an edit would overwrite
           someone else's silently. A refusal 412 with body.row — a screen instead of the text: in .pc-err the words W.rowMoved, next to it .pc-moved — the values of the form fields from body.row that differ from the input
           and the button .pc-reread. A refusal without body.row follows the field/common-error rule above. The human's input stays: the module does not erase it. The button rereads the rows and draws the form anew, the input is reset
writes_via: a unit of a subsystem whose manifest (view P/02.2) carries unit.writes_via — the module offers neither a creation form nor
           «save» and «delete» in unitForm: the fields are read-only; a table with the word tables.<t>.writes_via — without a write form
           of a row. A human's session would get 403 writes via always (P/06.1 N1.1a; ADR-0119 addendum (10)); requests (P/06.4) and the other
           actions of the page — as before
may:       console.may(cap, ref, sub?) → bool by the grants of the session and the scope rule P/06.3 N1.3 (* | unit:<sub>/<id> | labels:<…> | folder:<id>;
           a grant on the unit or on its about unit; the rank of cap — none < view < edit < admin, the right contract common/contracts/may.md);
           no sub — null: a row of any sub fits; the elements of grants with role are role groups, counted by the tiers of the right contract
           («The level of a role group»), without role — a direct group; the folder chains of the unit and of its about the module gathers by a reverse walk
           of the member lists from GET /folders; not gathered — the input is unknown, as at the server, not empty: a group with such an input gives no level, a row
           folder: of a direct group does not cover it (ADR-0097 §4, ADR-0099 §6); admin: true of the session (step 4a) — true, the module hides nothing
           by it (ADR-0100 §1); via: break-glass (grants []) — true, as the server for an emergency session (the right contract common/contracts/may.md step 1,
           glass → allow); true without grants only with open: true; in a closed or unknown (/session did not answer) session the absence of grants — false; the server always checks (review analysis of stage B 6–7, № 28)
events:    on("select", (ref, obj)) | on("refresh", {units, servers, domain}) | on("logout") | on("card.closed", {ref}) | on("session", {user}) — on every read of /session with a known user: on mounting, including without a login through the module window, and after a login, ordinary and emergency; a subscription after the read gets the last value at once; user unknown — no event; another user — the page resets its own: the secrets of the former one do not go into the write of the new one (C07-SESSION-EVENT-01, the Architect's decision of 2026-11-01, the analysis of the VMS pass)
           card.closed — the card was removed: a choice of another object, the removal of the choice (a change of section, a deletion), leaving the page;
           also for a card of the shell — ref is its name as it is (streamaccounts:local, netvols); a repaint by polling of the same choice
           does not give it (ADR-0091 addendum (22) item 2, addendum (24) item 2, addendum (25) item 2)
where:     where(ref) → {worker, server, door: {url, token, expires, routes} | null, reason}
           the library turns the absent field door of the HTTP answer into null for the shell; HTTP Where stays in the form of P/06.5 (the contract of lesson 6)
words:     display(name), manifest(name), kindWord(e), eventNote(e), addEventNote; W — the dictionary of the module ru | en
           a kind in the closed W.kinds roster uses W, even when a manifest display.kinds collides with it; only other kinds use display of the event subsystem
adds:      addSection{id, label, icon, after, off, render}, addTab(kind, {id, label, render, busy}) kind ∈ unit | server |
           worker | member | domain, addTreeNodes(kind | servers | server, fn) → nodes {ref, label, icon, count, kids, badge,
           tags, dot, title, off, open, after, replaces}, repaintTree() — the tree anew by these nodes when the page's nodes have changed but the module's data have not: as polling, the scroll is intact, with a button pressed it waits for its release (features "tree.repaint", C07-TREE-REPAINT-01), addCard(prefix, render), addMenu, addDecor{icon, badge, title},
           addFieldEditor(kind, field, render(host, ref, obj, value, set)), addBlock(kind, {id, covers, render}),
           addAction, addNote, addIcons, icon, unitForm(host, ref), dialog(title, fields, ok), confirm, toast,
           select(ref, {tab?}), selected, refresh, logout, fullScreen, isFav, toggleFav
           dialog(title, fields, ok) — a promise (Promise): on pressing ok — the values of the fields {<name>: <value>}, cancel —
           null; ok — the caption of the button; confirm(q, more) — at once the human's answer true | false (a value, not a promise) to the question q
           with the explanation more (C07-DIALOG-CONFIRM-RESULT-01)
           addBlock(kind) — kind ∈ server, member, domain; addTreeNodes(kind) — kind ∈ unit (nodes under a unit), servers,
           server, member, access (what the module already gives; ADR-0091 addendum (22) item 1)
           select(ref, {tab}) — select an object (a unit or a card of the shell) and open the tab by the id given to addTab
           ("general" — the card of the module); no such tab — the card opens without a change of tab (ADR-0091 addendum (22)
           item 2, addendum (24) item 2, addendum (25) item 2)
tree:      display.tree.folders: true — the tree of the section is built from GET /folders: a node folder:<id> per live folder, the parent — parent, the children — subfolders, then the members of this subsystem in the order of members;
           the name of the folder — name; an empty folder — a node with zero units, not a filter in the browser; a unit outside folders — a special node, as «no group»;
           a member of another subsystem or a unit that the module does not see gives no node; a rename — one write PUT /folders/<id> {name}, with If-Match containing the quoted store index (P/06.8 N2), not the integer api.opts.ifMatch of a page call;
           create a folder and a subfolder — POST /folders; add and remove a unit — PUT /folders/<id> {members}, the member list whole, the order as before, a new unit at the end, with the same quoted-index If-Match;
           the rights of the buttons — may(admin, …) as for the other writes, a refusal of the server — as for all doors (P/06.8 N3 «folder rights»);
           without display.tree.folders — the tree by group_by, as before
return:    after a login through the module window (password or emergency login) the module reads the parameter return of the page address: a value exactly /<sub>/,
           where <sub> is a subsystem of the catalogue of this console (the root and /mounts), — location.replace to it; no parameter — the page
           stays; another value — location.replace to /: an absolute address, //…, a segment .. or its percent form (the parameter is already
           decoded), a subsystem outside the catalogue, an address without the final /, with a tail, a repeated parameter. The value comes by a link,
           so the exact comparison protects from an open redirect (P/06.5 N2 «Login at the shell»; ADR-0094 B7)
cards:     the markup of a card: <h1>, nav.pc-tabs, <h2> → .card, button.pc-hdbtn, span.pc-crumbs[data-crumbs], p.pc-hdsub
commands:  the kind command / command.failed — the word and the note of the module (action · outcome · answer · «by: by»; late → «late»); the fields of the event
           outcome, action, by, late, error, reply are written by the worker base (P/03.6 N3 «holder's look»)
```

The session, the grants and the login by which `may` judges — [P/06.3](../../06-console/spec/06.3-console.norms.md) (the gate,
`/session`); the server checks every request regardless of `may`. The words `display` — P/06.5 N1.2.

### N1.6 The domain section — the late layer: introduced by lessons 8 and 10 (without ids of its own)

The parts of N1.4 and N1.5 that the domain introduces are parts of P/07-01 and P/07-02 without ids of their own (the move plan of lesson 7, V5; as P/02.1
N1.2b). The text was moved by the move of lessons 8–10 (stage B, commit 10; the move plan of lesson 8, § 5, row P/07 N1.6): the parts
about the module from M11/8 N1.8 `module`, M11/11 N1.6 `declared` and the module description
[`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) § 7 (the sections `domain`, `access`, `GET /api/held`) and
§ 10a (the holder page) (review analysis of stage A 6–7, № 27, № 30). The doors that the domain console gives to the page —
[lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) (the holder page — P/10-04); the forwarding to them, `/api/held`
and `/domain/shared/<sub>` at the cluster console — [chapter P/06.7](../../06-console/spec/06.7-console.norms.md).

```yaml
reads:     /domain/* (forwarding contract «Domain doors»; the cluster console forwards them to the domain console — P/06.7-02…05),
           /api/held (P/06.7-14; the term record and the backup pair — P/08.8), /domain/shared/<sub> (P/06.7-15)
writes:    /domain/* (forwarding contract «Domain doors»); login_url — POST {user, password} to the address login_url from /session:
           the domain door POST /api/login (P/08.4 N1.2; login_url — the gate and pass contract «The gate»; the cluster
           console forwards it to the domain — «Domain doors»)
order:     /domain/shared/<sub>, /domain (+ /domain/alarms — P/10-06), /api/held
never:     /api/backup (P/06.7-16)
objects:   the reference roster is N1.5 objects; lessons 8 and 10 introduce its domain references
events:    the field domain of refresh; the section access, having read its doors, emits refresh {access}
adds:      the kinds member, domain of addTab; addBlock — member, domain; addTreeNodes — member, access (as in N1.5; ADR-0091
           addendum (24) item 6, addendum (27) item 3)
sections:  the default of opts.sections — [units, access, journal] (P/06.5 N1.1 opts): the section access of the default is the late layer
           (below); [domain] — the holder page (P/10-04)
domain:    not a section of the section strip, but the root of the layout «By servers» of the units panel: where the holder is (GET /api/held), the members, the keys,
           the topology, the move («Move the domain here» — a dialog: the recovery file as text and «the old holder was stolen»
           no/yes → POST /domain/move {recovery[, stolen: true]}; without the file the request does not go), the alarms (in the card one
           row per kind and of: the last one, «×N (since …)», the list of members), keys-view; the domain card carries the term and the handover,
           «apply again», the units by subsystems, the shared settings by declared and the edits for clusters (pending and outcomes)
access:    people, grants, break-glass — /domain/users, /domain/grants, /domain/break-glass (forwarding contract «Domain doors»)
held:      GET /api/held — the only door of the processes that the module reads: the signed public record of the holder
           {cluster, holder, term, keys, backup: {term, rev}} at the cluster console; backup — a pointer to the last copy at this
           member, comparable only by the pair {term, rev}; at a member the module shows «an old copy» when its pair lags behind
           the holder pair term.backup of GET /domain (P/08.8 N1.3), and «the holder no longer updates it» when the member is absent from term.backup_holders of that same view. Compare pairs by term first, then rev at equal term (P/08.8, the largest (term, rev)); lagging means strictly smaller. Preserve the exact number representations
holder:    with sections: [domain] the module learns the holder mode from the sections of the page: it does not load the units, /servers and
           /unplaceable, it takes the units by subsystems from the view /domain; /servers, /drain, /schema, /unplaceable, /metrics,
           /events are not needed at the holder — the module survives their absence
schema:    GET /domain/shared → {doc, delivery, declared: {<sub>: [{name, type, schema?}]}} (P/10-14): the declared fields from
           domain.shared of the manifests and their types; for a document {name, type: json} — also its schema, by it the page builds a form;
           an edit — PUT /domain/shared {base_rev, shared: {<sub>: {<field>: value | null}}}
```

The origin of the lines: `reads`, `writes` (`/domain/*`), `order`, `never`, `objects`, `adds`, the field `domain` of `refresh` — the former
N1.6 (the addresses of M11 → P/06.7, P/10); `login_url`, `refresh {access}` and the section `access` of the default `sections` — review analysis of
stage B 6–7, № 30 (Claude M-5); `domain`, `access`, `held` — the description § 7; `holder` — § 10a and M11/8 N1.8 `module`;
`schema` — M11/11 N1.6 `declared` and § 10a. The form by `schema`: an object — by `properties` (the required ones are marked), a list —
elements by `items` with adding and removing, a string, a number, an integer, yes/no, `enum` — their own fields; what the form cannot express
(an object without `properties`, a union of types, a value with keys outside the schema) — a JSON text in its place; empty fields do not
go, an empty document — `null`; the domain checks the schema on `PUT` («Implementation decides» item 2, closed; the Architect's decision of 2026-10-21).
The holder page (`/`, CSP, `/manifest`, `/mounts`, `/session`) is served by lesson P/10 (P/10-04): implementations serve the bytes of the module
as they are; what the module calls in the mode `domain` is a property of the published module, not of the implementations (M11/8 N1.8 `module`).

---

## N2 The library contract

The module is a library of the platform in the browser, one code in all implementations (ADR-0005): the lesson has no process, door or
HTTP contract of its own (ADR-0082 addendum 13). The library contract is two norms of N1: what the module calls (N1.4) and what it gives
the shell (N1.5); the late layer — N1.6. The doors that the module calls, their codes and forms — the chapters of lesson 6 and the [contract of lesson
6](../../06-console/spec/06-console.api.openapi.yaml); the publication of the module byte for byte, the version `?v=` and the page are normed by
[chapter 6.5](../../06-console/spec/06.5-console.norms.md) N1.1. The calls of N1.5 are the shell addressing the library inside its own
page, not the platform calling a subsystem: they are not hooks in the sense of the boundary (`platform/subsystem boundary note`, for the human)
§1.1 (ADR-0002, for the human); the bytes of the stream and of the archive the shell
takes from the holder by `door` from `where()`, past the console (ADR-0015, for the human).

The description of the public surface of the module (the dictionary `W`, the card markup, the calls of the shell, the look) —
[`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) (not a norm; the move plan of lesson 7, V1). Where the description or
the published bytes differ from N1.4, N1.5, the lesson is right (review analysis of stage A 6–7, № 6); the discrepancies «Implementation decides»
items 1 and 2 are removed by changes of behaviour (the Architect's decision of 2026-10-21).

---

## N3 Procedures

The lesson has no procedures of its own: the order of load and polling — N1.4 `order`; the replay of a call — N1.5 `api`. The procedures of the doors that
the module calls — N3 of the chapters of lesson 6.

---

## N4 Refusals

The lesson has no rows of N4 of its own: the refusals of the doors that the module calls — N4 of the chapters of lesson 6 (a wrong version of the module — 404 `no such
version`, [P/06.5](../../06-console/spec/06.5-console.norms.md) N4); what the module does with a refusal — N1.5 `api` (401 — the login
window; a replay — only by the rules of the owner of the repeat memory; an unknown outcome of `PUT` and of tables — a read first); a refusal with `field` —
N1.5 `forms`.

---

## N5 Acceptance

The lesson has no acceptance catalogue (the exception `P/07 no-acceptance`; the move plan of lesson 7, V2): the module is a library in the browser,
the HTTP-TSV stand does not run it. The publication of the module byte for byte with the published files and the version `?v=1` (`?v=2` — 404) —
sc. 01 of the [acceptance of chapter 6.5](../../06-console/acceptance/5/README.md) (P/06.5 N1.1). The subjects of N1.4 and N1.5 are checked
by the jsdom tests of the owner of the specification `Source/tests/console` (review analysis of stage A 6–7,
№ 31): a test mounts the published module on a page in jsdom and intercepts its requests; the module is one for all implementations
(ADR-0005), the evidence is one for all (ADR-0080 addendum 16).

For a generation line, P/07 is packaging: the published files are taken unchanged and checked byte for byte together with scenario 01 of acceptance 6.5, including `?v=1`. The line does not rewrite JavaScript and gets no separate executable module profile. The three tests `module-unplaceable-all`, `module-subsystems-none` and `module-writes-via`, and readiness items P/07-07 and P/07-08, remain an explicit debt of the owner of the published module bytes (the course canon, changed through Specification branches). They are neither PASS nor FAIL of the generation line until the owner closes the debt. The behavioural rules of N1.4 and N1.5 remain in force (the Architect's decision of 2026-11-05 under ADR-0112 and ADR-0119).

| Subject | Reason | Place of proof |
|---|---|---|
| N1.4 `reads`, `writes`, `never` — not a single call outside the list; the module does not call the doors of the holders | TSV talks to the doors, it does not see the calls of the page | jsdom test `module-calls`: every intercepted request of the module (method and path) on mounting, polling, selection and edits is compared with `reads`/`writes`, the paths of `never` and the door from `where()` are not called; the mode `domain` — the same test (review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21) |
| N1.4 `order`, polling every `poll_s`, `/events?unit=` of the selected one — every 5 s | the doors do not show the order of load | jsdom test `module-calls`: the order on mounting and on every poll, polling every `poll_s` of the page, `/events?unit=` of the selected one — after 5 s (review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21) |
| N1.4 `changes` — the number before the rows, a load on a message and on a reset, 404 removes the feed (ADR-0094 B2) | TSV does not run the page | jsdom test `module-changes`: the order on mounting, `after` and `wait`, a message about its own subsystem and a reset — a load, a foreign subsystem and an empty answer — none, 404 — one request, polling lives |
| N1.5 `version` — an integer, the shell compares it before use | the version in `?v=` is checked by the door, and the comparison is done by the page | jsdom test `platform-page`: `console.html` compares `version` before `mount`, a module of another version is not mounted; the door `?v=` — sc. 01 of acceptance 6.5 (review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21) |
| N1.5 `api` — a key of a logical action, a replay by the rules of the owner, `PUT` and tables without an automatic replay, 401 — the login window | TSV does not create a replay after a lost answer | jsdom test `module-retry` (and `module-session`: «Retry» with the same key): a new key per call, a replay only of `POST /<rows>`, `/<sub>/<rows>` with the same key and body, `Retry-After`, after the third replay — a refusal with `status`, `body`, `retry`; `PUT`, `DELETE`, `POST /marks`, `/drain`, the decommission of a server — without a replay, a read first; by the second pass of the coverage audit (Gemini, 2026-10-30): `POST`, `PUT`, `DELETE` of the tables of the root (`/testsub/<table>`) and of a mounted (`/<sub>/<table>`) subsystem — without a replay on a dropped connection and 5xx, a refusal without `retry`; 401 — the login window (the Architect's decision of 2026-10-21) |
| N1.5 `may` — by the grants of the session; without grants `true` only with `open: true` | the grants are issued by the domain, the scenarios of lesson 6 run without the domain | jsdom test `module-may`: rank and scope (`*`, `unit:` with an about unit, `labels:` at the about unit or at the unit itself), outside a unit, `via: break-glass`, an open, a closed and an unknown session (the Architect's decision of 2026-10-21); the server always checks — P/06.3 |
| N1.5 `where` — `door` or `null` when the HTTP answer has no field `door` | the conversion is done by the library, not by the door | jsdom test `module-contract`: `door` — the object `Door` of the answer, without the field `door` — `null`; HTTP `Where` without `door` — sc. 04 of acceptance 6.5 (review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21) |
| N1.5 `objects`, `events`, `words`, `adds`, `cards`, `commands`; without hooks and a foreign DOM | the subject is the behaviour of the page, not the doors | a jsdom test of the module and the shell, and reading; `objects` (`worker:<sub>/<w>`) — `module-contract`, `module-servers`, `module-calls`; `events` (`logout`) — `module-session` (review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21); by the coverage audit of P/07 (2026-10-30): `events` `refresh {units, servers, domain}` and `refresh {access}` — `module-refresh-event`; `adds` `addTreeNodes` of five kinds and the fields of a node — `module-tree-nodes`, `addNote`, `addIcons`, `fullScreen`, `isFav`/`toggleFav` — `module-page-adds`; `words` (ru and en of the same keys, the words of all event kinds; the second pass of Gemini: `display(name)` — the words of the manifest, for an unknown subsystem — empty; `eventNote` of the page after `addEventNote` — in the journal and on the events tab of the card, an event of the platform — in the words of the module) — `module-words`; the second pass of Gemini: `addSection` (`after`, `off` with a reason), `addTab` of four kinds with `select(ref, {tab})`, `busy()` — polling does not repaint, `addBlock` of a member and of the domain after its own blocks, `addAction` (`fn(ref, obj)` → the buttons of the header before the star), `dialog` (a promise of values, cancel — `null`), `confirm(q, more)` — the human's answer — `module-page-adds`; `cards` (the header, the crumbs, the tabs, the buttons; `<h2>` → `.card` — first in `.box` («Implementation decides» item 3, closed)) — `module-card-markup`; without accesses to the DOM of the frame — by reading |
| N1.5 `module`, `features`, `ready`, `select(ref, {tab})`, `card.closed` (ADR-0091 addendum (22)–(27)) | the subject is the behaviour of the page | jsdom test `module-page-calls`: `features`, version 1, `pc.ready` after `mount` and the first `/manifest` and after 401 → login, on a dropped connection and 503 of `/manifest` — it waits for the next poll without the login window and without an immediate replay (the second pass of the coverage audit, Gemini), `select` with a tab, without it, with an unknown one and `general`, `card.closed` on a change of selection, a removal of selection, leaving the page, for a card of the shell, not on polling; the VMS page without accesses to the DOM of the frame (`shell.may_not`) — the tests of the page of the VMS owner and by reading |
| N1.5 `return` — the return after a login, protection from an open redirect | a call of the page, TSV goes to the doors and does not follow a `302` | jsdom test `module-return`: `/<sub>/` of its own catalogue and of the root — a transition; outside the catalogue, absolute, `//evil`, `/%2e%2e/`, with `..`, without the final `/`, with a tail, a repeated parameter — to `/`; without the parameter the page stays |
| N1.5 `forms` — `ifMatch` of the form, the screen of 412 (ADR-0094 B4) | what the form sent and showed, TSV does not see | jsdom test `module-form-if-match`: PUT and DELETE carry `If-Match`, 412 — `.pc-moved`, the input is intact, `.pc-reread` rereads |
| N1.5 `forms` — a refusal at the field by `field` | what the form did with the refusal, TSV does not see | jsdom test `module-refusal-field`: the control of the field, `.pc-field-err`, the focus, the parsing of `~1`; without `field` and without a form element — the common `.pc-err` (ADR-0094 B5) |
| N1.5 `tree` — the tree by the folders of the cluster (ADR-0096) | TSV does not see the calls of the page | jsdom test `module-folders` (not written yet: the module does not do this, a debt of the product): the tree from `/folders`, an empty folder, a rename by one write |
| N1.4 `subsystems`, `unplaceable` (ADR-0112 addendum (23)) | TSV does not see the calls of the page; the witness `Source/w2cplatform/console.js` does not execute the rule — an open debt of the owner of the published bytes | the owner of the published module bytes closes this debt with the tests of the common module, not the unchanged witness: `module-unplaceable-all` — an unplaced unit of a subsystem outside `opts.subsystems` is visible as a row of the section (subsystem, id, reason) without a card and without actions, `/<sub>/unplaceable` is called for every subsystem of the catalogue; `module-subsystems-none` — `subsystems: []`: not a single `/<rows>`, `/<sub>/<rows>`, the tree is empty, the section of unplaced units reads all subsystems |
| N1.5 `writes_via` — forms without a write (ADR-0119 addendum (10)) | TSV does not see the calls of the page; the witness `Source/w2cplatform/console.js` does not know the word — an open debt of the owner of the published bytes | the owner of the published module bytes closes this debt with the test of the common module, not the unchanged witness: `module-writes-via` — a unit of a subsystem with `unit.writes_via` has no creation form, `unitForm` has no «save» and «delete», not a single `POST`, `PUT`, `DELETE` of the rows of this subsystem; a subsystem without the word has the forms as before |
| N1.6 the late layer (the mode `domain`, the sections `domain`, `access`, `login_url`, `refresh {access}`) | the stand of lesson 6 has no domain; TSV does not see the calls of the page | the jsdom test of the mode `domain` at the owner of the module (N1.6 `holder`; `Source/tests/console`); the doors of the holder page — the acceptance of [lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) (P/10-04), the doors of people — [the acceptance of chapter P/08.4](../../08-domain/acceptance/4/README.md); the form by `schema` — jsdom test `module-shared-schema` (the Architect's decision of 2026-10-21) |

### Accepted ADR-0127 review criteria and debt of the published module bytes

The following criteria refine the existing N1.5 obligations. Their owner is the owner of the published common module bytes (the course canon, changed through Specification branches). The published witness stays unchanged in this delivery. Each row is an open behavioural/evidence debt of that owner until an actual module test closes it; adding the criterion or copying the published files is not such evidence. Generation lines package the same bytes and do not implement a replacement module.

| Criterion | Required module test | Debt owner and evidence boundary |
|---|---|---|
| `may` (review C1), N1.5 | `module-may`: `admin: true` with empty grants; a grant for another `sub`; direct groups and role tiers including a specific `none` over a general `edit`; folder and about-unit folder chains; an unavailable chain remains unknown and grants no level; closed, open, emergency and unknown sessions | Published-byte owner; compare the existing common `may` contract, without changing the server's independent check |
| Every unit-form write, including an immediate boolean switch (C2), N1.5 `forms` | `module-form-if-match`: the shown revision is sent as `If-Match`; two quick clicks cannot bypass that revision; a concurrent change yields 412, keeps the input and shows the reread screen; an unreadable required revision permits no write | Published-byte owner; a bool switch uses the same CAS/refusal path as the rest of the form |
| Immutable request snapshot (C3), N1.5 `api` | `module-retry`: mutate the caller's original object, including a nested value, after the initial call and again before manual Retry; automatic and manual retries retain the original serialized body and the same key | Published-byte owner; a new call still gets a new key even for equal bytes |
| Complete-attempt timeout (C4), N1.5 `api` | `module-retry`: receive headers, then stall the body beyond 20 s; separately truncate the body. A unit POST retries only under the existing rule, with the same key and immutable body; PUT and table calls report an unknown outcome and reread without an automatic replay | Published-byte owner; receiving headers does not complete an attempt or turn an incomplete body into a successful null answer |
| Captions as a string or `{key, text}` (C5), N1.5 `words` | `module-words`: unit and field captions, `field_help`, enum choices and event kinds in both caption forms; resolve the localization key with text as the declared fallback | Published-byte owner; preserve the caption contract of P/06.5 and the existing localization keys |
| Hidden fields (C6), N1.5 `forms` | Module form tests: a `hidden: true` field is absent from the ordinary form and from an explicit `display.form`; visible neighbours remain present; omitted or false `hidden` keeps ordinary behaviour | Published-byte owner; open `v1showsHidden` debt, no module execution or byte change in this source delivery |
| Legal external names (C7), N1.5 | `module-words` and form/tree tests: `__proto__`, `constructor`, `toString` as unit identifiers and data names remain visible, selectable and editable according to their rights; no inherited property substitutes for a data entry | Published-byte owner; the existing identifier grammar is not narrowed |
| Platform-kind priority (M2), N1.5 `words` | `module-words`: a closed platform event kind uses `W.kinds`; a colliding `display.kinds` in either the current subsystem or another subsystem cannot replace it. Other kinds use the event's subsystem display dictionary | Published-byte owner; the closed platform roster is the existing `kinds.*` roster in the P/06 localization table |
| Default language and explicit selection (P/06 UI decision) | `module-words` and mount tests: default English, explicit `lang: "ru"`, equal key/parameter rosters; browser language does not silently select Russian | Published-byte owner; table synchronization and removal of the historical browser-language fallback remain open byte-owner debts |

Review C6 is adopted by the related P/06 `FieldView.hidden` form: an optional boolean with no default; the required roster and closed shape are unchanged. The module omits fields with `hidden: true` from generated forms, including an explicit `display.form`. This source change does not prove that the published module bytes implement it; the `v1showsHidden` debt below remains open until the byte owner supplies actual module evidence.

---

## Implementation decides

The module is one code in all implementations: an implementation does not write it and chooses nothing in it, but serves the published bytes
(P/06.5 N1.1 `module`). The items below are debts of the published module; the owner of the specification closes them (ADR-0080 addendum 16); items 1–5 are closed; items 6 and 7 remain open debts of this owner, not a separate module implementation by a generation line:

1. **closed: the bytes of `console.js`, `console.html` and the description `CONSOLE-MODULE.md` are brought to N1.4, N1.5**
   by a change of behaviour after the commit of lesson 7 (the Architect's decision of 2026-10-21; review analysis of stage A 6–7, № 6, findings A-30, A-31;
   review analysis of stage B 6–7, № 26–29; findings of Claude M-1, M-2, M-3, M-5). Before: a key by method, path and body and
   an automatic replay of `PUT` and of any `POST` («a», «e»), the body field `retry_after` instead of the header `Retry-After` («zh»), `may` without grants —
   `true` with any `open` and for an unknown session («b», «v»), no event `logout` («g»), the reference `worker:<w>` without a subsystem («d»),
   `poll_s` from the memory of the browser, `/<table>` at the root, an error without `status` and `body`, the read of `server_unsaid`, a shell without
   comparing `version` («z»). The evidence — the jsdom tests `Source/tests/console` by the table of N5. The debt
   of the product — to «Build» (ADR-0005): its copy of the module is brought to these bytes.
2. **closed: the form of the shared document by `schema`** (N1.6 `schema`) — by a change of behaviour of the owner of the specification (ADR-0080
   addendum 16; the Architect's decision of 2026-10-21): before — the document `{name, type: json}` as a JSON text without a form (the description § 10a). The evidence —
   jsdom test `module-shared-schema` (N5). The debt of the product — to «Build» (ADR-0005).
3. **closed: `<h2>` → `.card`** (N1.5 `cards`; the coverage audit of P/07, 2026-10-30) — by a change of behaviour of the owner of the specification: before —
   a section `<h2>` among other content and `<h2>` first in the host of the page gave a card without its own section. The evidence —
   jsdom test `module-card-markup` (N5). The debt of the product — to «Build» (ADR-0005).
4. **closed: a refusal at the field by `field`** (N1.5 `forms`; ADR-0094 B5, addendum (13) item 3) — by a change of behaviour of the owner of the specification: before —
   the text of the refusal only in the common `.pc-err`. The evidence — jsdom test `module-refusal-field` (N5). The debt of the product — to «Build» (ADR-0005).
5. **closed: rows by the feed** (N1.4 `changes`; ADR-0094 B2) — by a change of behaviour of the owner of the specification: before — only polling by `poll_s`. The evidence — jsdom test `module-changes` (N5). The debt of the product — to «Build» (ADR-0005).
6. **not closed: the unplaced units of all subsystems and `subsystems: []`** (N1.4; ADR-0112 addendum (23)) — the witness `Source/w2cplatform/console.js` reads `/<sub>/unplaceable` only for the subsystems of `opts.subsystems`; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; tests — N5 `module-unplaceable-all`, `module-subsystems-none`.
7. **not closed: forms without a write for `writes_via`** (N1.5 `writes_via`; ADR-0119 addendum (10)) — the witness `Source/w2cplatform/console.js` does not know the word and draws the forms; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; test — N5 `module-writes-via`.

---

## Readiness checklist

An implementation conforms to the lesson when every norm is met; the norm id `P/07-MM` is what the deltas of decisions,
findings and window records refer to (ADR-0080 addendum 6). The implementation here is the published module, one for all (N2).

- [ ] **P/07-01** the closed list of calls of the module N1.4 and the order of load — checked by a jsdom test: the calls of the module and their order — by N1.4 `reads`/`writes`/`never`/`order`; the reason — the module is one for all implementations, the doors do not show the order of load; the place of proof — the jsdom test of the owner of the specification `Source/tests/console/module-calls.test.js` (N5; review analysis of stage A 6–7, № 31; review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21); the parts of the late layer — N1.6 `reads`, `writes` (`login_url`), `order`, `never`, the mode `holder` (`sections: [domain]`)
- [ ] **P/07-02** the shell contract N1.5: `api` with a key of a logical action and replays only by the contract of the owner, `where` with `door`, the calls of the library, without hooks and a foreign DOM — checked by reading: the test of the shell (jsdom; the subject is the behaviour of the page, not the doors); the reason — TSV talks to the doors, it does not run the page; the place of proof — `Source/tests/console` (N5; analysis, № 31); `api`, `may`, `version`, `where`, `objects`, `events` — jsdom tests `module-retry`, `module-may`, `platform-page`, `module-contract`, `module-session`; `features`, `ready`, `select(ref, {tab})`, `card.closed` — `module-page-calls` (ADR-0091 addendum (22)–(27)) (N5; analysis, № 6; review analysis of stage B 6–7, № 29; the Architect's decision of 2026-10-21); the parts of the late layer — N1.6 `objects`, `events` (`refresh {access}`), `adds`, the sections `domain`, `access`, `held`, `schema` (the form by `schema` — jsdom test `module-shared-schema`); `return` — jsdom test `module-return`
- [ ] **P/07-04** the unit form always sends `ifMatch`, the screen of 412 N1.5 `forms`; `api` with `ifMatch` at tables and settings doors (ADR-0094 B4) — jsdom tests `Source/tests/console/module-form-if-match.test.js`, `module-page-calls.test.js` (N5); the reason — TSV does not see the behaviour of the page
- [ ] **P/07-05** rows by the feed N1.4 `changes` (ADR-0094 B2) — checked by jsdom tests `Source/tests/console/module-changes.test.js`, `module-calls.test.js` (N5); the reason — TSV does not run the page
- [ ] **P/07-03** a refusal at the field N1.5 `forms` (ADR-0094 B5) — checked by jsdom test `Source/tests/console/module-refusal-field.test.js` (N5); the reason — TSV does not run the page
- [ ] **P/07-06** the tree by the folders of the cluster N1.5 `tree` (ADR-0096) — checked by jsdom test `module-folders` (N5) when the module has it; the reason — TSV does not run the page
- [ ] **P/07-07** `opts.subsystems` and the unplaced units of all subsystems of the catalogue N1.4 (ADR-0112 addendum (23)) — the owner of the published common module bytes closes this debt with `module-unplaceable-all`, `module-subsystems-none` (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page
- [ ] **P/07-08** forms without a write at a subsystem with `writes_via` N1.5 (ADR-0119 addendum (10)) — the owner of the published common module bytes closes this debt with `module-writes-via` (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page

**Related byte-owner debt C6 — `v1showsHidden` (N5, alongside P/07-07 and P/07-08).** The version-1 published behaviour that shows hidden fields is not accepted as the rule. The byte owner must demonstrate omission from both the ordinary form and explicit `display.form`, with visible controls preserved. The P/06 OpenAPI property is source-form evidence only; this delivery neither edits nor executes module bytes and closes no behavioural debt.


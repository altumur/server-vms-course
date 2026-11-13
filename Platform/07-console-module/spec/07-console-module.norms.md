# P/07 — Console module: norms

This English text is the source; the Russian translation `ru/spec/07-console-module.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The canon of the lesson. Lecture (`ru/07-console-module.md`, for people, not in the export), [instructions](07-console-module.README.md). The lesson has no HTTP contract
of its own: the module is a library in the browser, it has no door of its own (N2); the doors it calls are the [contract of lesson
6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer (N1.6) also the contracts of lessons
[8](../../08-domain/spec/08-domain.api.openapi.yaml) and [10](../../10-domain-console/spec/10-domain-console.api.openapi.yaml). The lesson has no acceptance catalogue (N5); it has no life cycle: a library has no process,
environment or exit codes; the publication of the module is [chapter 6.5](../../06-console/spec/06.5-console.norms.md).
The late layer — the domain section, `sections: [domain]` of the call `mount`, the
holder mode — is N1.6, without separate readiness ids of its own.
The canon of the module is the norms N1.5. Conformance of the published
bytes of `console.js`, `console.html` and the description [`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) to N1.4 and N1.5
is not closed in full («Implementation decides» item 1). The three parts of the console, the mounting
`PlatformConsole.mount(root, opts)`, `opts`, `never` of the module and `may`/`may_not` of the shell — [P/06.5 N1.1](../../06-console/spec/06.5-console.norms.md)
`module`, `shell`. A reference «lesson N» without a chapter is the module lesson P/NN; «P/06.K», «P/08.K» are the chapters of lessons 6 and 8;
«P/10» is the lesson of the domain console. Readiness ids are `P/07-MM`; individual requirements have `P/07-RNNN` anchors.

## Index

Topics whose rules are stated in separate places; file paths identify other M text that actually discusses the topic. The N5 evidence tables map tests to these behavioural requirements.

| Topic | Requirements | Files |
|---|---|---|
| `call_scope` Module calls and page calls | P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R065, P/07-R070, P/07-R071, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R222 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `load_poll` Whole-load order and polling | P/07-R009, P/07-R010, P/07-R011, P/07-R019, P/07-R023, P/07-R029, P/07-R030, P/07-R034, P/07-R065, P/07-R205, P/07-R229 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `subsystem_scope` Unit selection and catalogue observations | P/07-R012, P/07-R016, P/07-R017, P/07-R034, P/07-R229 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `worker_profiles` Worker identity and observations by profile | P/07-R034, P/07-R038, P/07-R039, P/07-R040, P/07-R043, P/07-R045, P/07-R307 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `api_cas` API CAS and form refusal handling | P/07-R047, P/07-R070, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R095, P/07-R096, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R152, P/07-R154 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `replay` Logical action and replay | P/07-R047, P/07-R080, P/07-R081, P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `session_may` Session grants and may | P/07-R110, P/07-R113, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `session_events` Session observations and user reset | P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R172 | `CONSOLE-MODULE.md` |
| `cluster_refresh` Confirmed root and refresh observations | P/07-R045, P/07-R167, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R248, P/07-R327 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `caption_language` Captions, UI language and displayed dates | P/07-R131, P/07-R132, P/07-R133, P/07-R163, P/07-R166, P/07-R178, P/07-R180, P/07-R182, P/07-R184, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R191, P/07-R192, P/07-R333, P/07-R353 | `CONSOLE-MODULE.md`, `data/localization.tsv`, `spec/07-console-module.README.md` |
| `domain_pages` Domain continuation and unread assembly | P/07-R176, P/07-R177, P/07-R196, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R335 | `spec/07-console-module.README.md` |
| `holder_mode` Holder-page mode and reads | P/07-R029, P/07-R215, P/07-R229, P/07-R239, P/07-R343 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `folder_tree` Folder observations and tree | P/07-R113, P/07-R147, P/07-R149, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `shared_form` Shared settings and schema forms | P/07-R220, P/07-R231, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R238, P/07-R339 | `CONSOLE-MODULE.md` |
| `extensions` Shell extensions and disabled input | P/07-R054, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R211, P/07-R212, P/07-R213 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `holder_door` Passing a holder door to the shell | P/07-R008, P/07-R129, P/07-R130, P/07-R351 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `pending` Pending counts and outcomes | P/07-R194, P/07-R220 | `CONSOLE-MODULE.md`, `spec/07-console-module.README.md` |
| `byte_publication` Canonical evidence, published bytes and generation-line packaging | P/07-R059, P/07-R060, P/07-R061, P/07-R239, P/07-R258, P/07-R264, P/07-R265, P/07-R266, P/07-R289, P/07-R291, P/07-R343 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |

## N0 Vocabulary

<!-- req: P/07-R001 -->
Normative words follow the [course canon](../../common/NORMATIVE-TERMS.md).

<!-- req: P/07-R002 -->
The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

## N1 Form

<!-- req: P/07-R003 -->
**Time.** The lesson has no time fields in rows and objects: the module writes no rows or objects of its own, as defined in P/07-R005. Time in the answers of the doors that it shows (`until` of the session, `expires` of the door from `where()`) has the form of [P/06.3](../../06-console/spec/06.3-console.norms.md) and [P/06.5](../../06-console/spec/06.5-console.norms.md).

<!-- req: P/07-R005 -->
**Data.** The lesson has no rows, objects or files of its own: the module reads and writes only through the doors of the closed list N1.4 — the doors of lesson 6, in the late layer (N1.6) also the doors of the domain: `/domain/*` and the login `login_url` (`POST /api/login`) — the doors of the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md); the process `domain` — [lesson P/08](../../08-domain/spec/08-domain.api.openapi.yaml)), which the cluster console forwards ([chapter P/06.7](../../06-console/spec/06.7-console.norms.md); the [forwarding contract](../../common/contracts/forwarding.md) «Domain doors»), and the own doors of the cluster console `/api/held`, `/domain/shared/<sub>` (chapter P/06.7); the forms — the [contract of lesson 6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer — the contracts of lessons 8 and 10; the owners of the rows — the chapters of lessons 6, 8 and their catalogue.

### N1.4 What the module calls — a closed list

<!-- req: P/07-R006 -->
**`reads`.** The module's permitted reads are: /session, /manifest, `/<sub>/manifest`, /mounts, /changes, `/<rows>`, `/<sub>/<rows>`, `/<sub>/<table>` (only from servers.show), `/where/<id>`, `/<sub>/where/<id>`, /servers, `/<sub>/servers` (only loaded subsystem profiles), /unplaceable, `/<sub>/unplaceable`, /policy, /drain, /schema, /events, /metrics (only running_gauge and workers_gauge), /domain/* (forwarding contract «Domain doors»), /api/held (P/06.7-14), `/domain/shared/<sub>` (P/06.7-15), /folders (only with display.tree.folders).

<!-- req: P/07-R007 -->
**`writes`.** The module makes its own writes only through these doors: POST/PUT/DELETE `/<rows>[/<id>]` and `/<sub>/<rows>[/<id>]`; POST `/folders` and PUT/DELETE `/folders/<id>` only with `display.tree.folders`; POST `/marks`; PUT `/policy`; POST/DELETE `/drain`; GET/PUT/DELETE `/servers/<s>/labels`; POST/DELETE `/servers/<s>/decommission`; `/domain/*` under the forwarding contract «Domain doors»; POST/DELETE `/session`; `/session/break-glass`; `login_url`.

<!-- req: P/07-R008 -->
**`never`.** The module never calls `/{sub}/requests`, `/api/backup` (P/06.7-16), `/resources`, `/{sub}/{table}` outside `servers.show`, or holder doors; the module hands the door from `where` only to the shell.

<!-- req: P/07-R009 -->
**`order`.** The module loads in this order: `/session` → `/manifest` → `/mounts` → `/changes` (only on mounting) → per subsystem `/<rows>` → `/folders` (if at least one subsystem declared `display.tree.folders`) → `/servers` → `/<sub>/servers` (other catalogue profiles, in order) → `/unplaceable` → `/domain/shared/<sub>` (P/06.7-15) → `/drain` → `/schema` → `/domain` (+ `/domain/alarms`; P/10-06) → `/api/held` (P/06.7-14) → `/metrics`.

<!-- req: P/07-R010 -->
**`order`.** On each ordinary poll every `poll_s`, the module repeats the reads of P/07-R009 from per-subsystem `/<rows>` through `/metrics`; `/session`, `/manifest`, `/mounts` and `/changes` are not repeated.

<!-- req: P/07-R011 -->
**`order`.** The module reads `/events?unit=<selected unit>` every 5 s.

<!-- req: P/07-R012 -->
**`subsystems`.** `opts.subsystems` names catalogue subsystems (root and `/mounts`) whose units the module loads, shows in its tree and writes through `/<rows>`, `/<sub>/<rows>`, cards and forms. When opts.subsystems is absent, the module loads, shows and writes units of all catalogue subsystems. When opts.subsystems is a list, the module loads, shows and writes units only of the named subsystems. When opts.subsystems is [], the module loads, shows and writes no subsystem units.

<!-- req: P/07-R016 -->
**`unplaceable`.** The module reads `/unplaceable` and `/<sub>/unplaceable` at every catalogue subsystem regardless of `opts.subsystems`. The module uses `/unplaceable` and `/<sub>/unplaceable` only for reading.

<!-- req: P/07-R017 -->
**`unplaceable`.** An unplaced unit of a subsystem outside opts.subsystems appears as a section row (subsystem, id, reason), without a card or actions. Reading unplaced units only at the subsystems shown by the page would leave the other subsystems' unplaced units invisible; P/07-R016 requires reading the whole catalogue.

<!-- req: P/07-R019 -->
**`changes`.** For GET /changes (P/06.1 N2 «Change feed»), the module obtains a number before the first row read. After obtaining the change-feed number, the module holds `/changes?after=<number>&wait=15`.

<!-- req: P/07-R021 -->
**`changes`.** After an immediate return or disconnect of /changes, the module issues a new request at most once a second. The request-frequency limit does not shorten the held wait=15 request.

<!-- req: P/07-R023 -->
**`changes`.** A reset or a message about a row of a page subsystem starts the load order of P/07-R009 immediately and silently: the page sees the edit within a tick rather than poll_s. A change-feed message carries no value, so the module rereads the rows rather than applying the message. The module need not compare revision when handling a change-feed message.

<!-- req: P/07-R026 -->
**`changes`.** On a 404 response from `/changes`, the module stops calling the feed and continues by polling. On a /changes refusal other than 404, or a dropped connection, the next feed attempt is after poll_s, without the login window; polling raises that window.

<!-- req: P/07-R028 -->
**`changes`.** A /changes answer to a request without after (no number yet) counts as a reset.

<!-- req: P/07-R029 -->
**`changes`.** The holder page of P/07-R229 does not call the change feed: the domain console has none.

<!-- req: P/07-R030 -->
**`changes`.** The module retains polling every `poll_s`: GET `/<rows>` also carries heartbeats, and `/servers` and `/metrics` have no feed; the feed covers unit and table rows.

<!-- req: P/07-R031 -->
The list is about the module's own calls: `never` forbids them to the module, not to the page; a call of the page through `console.api` (the VMS page — `POST /<sub>/requests`, the requests door P/06.4) is its call, not the module's.

<!-- req: P/07-R032 -->
The words `servers.show`, `console.running` (`running_gauge`, `workers_gauge`) and `poll_s` — [P/06.5](../../06-console/spec/06.5-console.norms.md) N1.1, N1.2.

<!-- req: P/07-R033 -->
The domain-introduced calls `/domain/*`, `/api/held`, `/domain/shared/<sub>`, `/domain/alarms` and `login_url` are defined in P/07-R202…P/07-R206.

<!-- req: P/07-R034 -->
Worker observations use the existing request context of P/06.5 N2. In the servers phase, read root `/servers` once, then the other loaded catalogue profiles through `/<sub>/servers` in catalogue order. The explicit root prefix is the same profile, not another observation. `opts.subsystems` limits unit loading, not the worker-profile observations; `[]` does not make the profile catalogue empty.

<!-- req: P/07-R038 -->
An unconfirmed catalogue is unknown, not an empty or confirmed working profile.

<!-- req: P/07-R039 -->
Keep documents and their policy/ServerRow observations separate by profile.

<!-- req: P/07-R040 -->
The private worker identity is the exact `(sub, worker)` from the confirmed request context; the existing reference is `worker:<sub>/<w>`. Worker selection and callbacks use the original WorkerRow of the confirmed profile, without a synthetic `sub`. The module does not substitute the root profile for the confirmed worker profile. The module does not join worker observations by a short worker name.

<!-- req: P/07-R307 -->
The module does not read internal storage.

<!-- req: P/07-R043 -->
An unreadable, refused or unavailable profile remains unknown, without an empty-worker fact or another profile's row as fallback. A last-known observation is not a successful current read.

<!-- req: P/07-R045 -->
Public `refresh.servers` is exactly the root response's `d.servers` map, not the entire Servers document, its policy or merged profiles. Private error/last-known state of worker observations adds no public field or event.

<!-- req: P/07-R046 -->
P/06 API and WorkerRow are unchanged.

### N1.5 The contract of the module with the shell

<!-- req: P/07-R047 -->
Classify only the path before the query, using the root and mounted subsystem routes already declared by P/06.5 N2. Keep the original request address, CAS revision, logical-action key and replay rules. A query does not make a service door a table or permit `ifMatch` there.

<!-- req: P/07-R050 -->
An `int` control never truncates the input. An `int` control sends the same safely representable integer as an ordinary JSON integer, or refuses locally while retaining the text and sending no substituted number.

<!-- req: P/07-R052 -->
A list remains a typed list across display, editing another element and submission: commas inside a string, empty strings, order and duplicates are not lost by splitting, trimming or deduplication. Ordinary lists acquire no placement-label restriction.

<!-- req: P/07-R054 -->
An added section with an `off` reason remains visible with that reason. Neither mouse nor keyboard activation enters a section with an `off` reason or invokes that section's `render`. An enabled section neighbouring a section with an `off` reason continues to work. The `off` section behaviour concerns the UI rather than server permission.

<!-- req: P/07-R057 -->
**`module`.** The module has one object, `PlatformConsole {version, features, mount}`. The call `mount(root, opts)` returns the page object (`pc` — the name of the page variable in examples, not a second object).

<!-- req: P/07-R059 -->
**`version`.** `console.version` is an integer: the shell API version of P/06.5 N1.1 `version`.

<!-- req: P/07-R060 -->
**`version`.** The shell checks console.version before using the module.

<!-- req: P/07-R061 -->
**`version`.** The API version `console.version` stays 1: `features`, `ready`, `select` with `tab` and `card.closed` are additions, and the load `?v=1` is unchanged.

<!-- req: P/07-R062 -->
**`features`.** `PlatformConsole.features` is the list of strings naming capabilities beyond the initial version-1 calls: `select.tab`, `card.closed`, `api.if-match`, `placement.if-match`, `session`, `tree.repaint`. A capability absent from PlatformConsole.features is unavailable. The page discovers added capabilities through PlatformConsole.features rather than console.version.

<!-- req: P/07-R065 -->
**`ready`.** `pc.ready` is a Promise, not a new call; the promise resolves with the page object after `mount` and the first successful `/manifest` read (there is no door `/spec` — P/07-R006). On a 401 response to /manifest, pc.ready waits for login and resolves after it. When `/manifest` cannot be read because of network failure or 5xx, the module rereads `/manifest` by polling and `pc.ready` waits.

<!-- req: P/07-R068 -->
**`objects`.** The module uses `ref` strings from this roster: `unit:<sub>/<id>`, `server:<s>`, `worker:<sub>/<w>`, `member:<m>`, `domain`, `person:<name>`, `group:<sub>/<field>/<path>`, `folder:<id>`, or shell-owned `<prefix>:<…>` that the module only stores.

<!-- req: P/07-R355 -->
**`objects`.** Legal external names such as `__proto__`, `constructor` and `toString`, used as unit identifiers or data names, remain visible, selectable and editable according to their rights. No inherited property substitutes for a data entry.

<!-- req: P/07-R069 -->
**`api`.** The call `console.api(method, path, body, opts?)` returns an answer or throws `{status, body, retry}`.

<!-- req: P/07-R070 -->
**`api`.** The door list of P/07-R073 and the ifMatch type of P/07-R072 apply to page calls through console.api.

<!-- req: P/07-R071 -->
**`api`.** The module makes its own writes only by the list of P/07-R007.

<!-- req: P/07-R072 -->
**`api`.** `opts.ifMatch` is an integer ≥ 1 (the revision of P/06.1 N2 «Versions») and becomes the `If-Match` header.

<!-- req: P/07-R073 -->
**`api`.** The option `opts.ifMatch` is accepted only at doors that read it: PUT and DELETE of a unit row `/<rows>/<id>`; POST `/<t>` and DELETE `/<t>/<name>` of a subsystem table; PUT /policy; POST and DELETE /drain; PUT and DELETE `/servers/<s>/labels`; PUT /schema; PUT and DELETE `/domain/placement/<sub>/<ref>`. Other doors would write without CAS.

<!-- req: P/07-R074 -->
**`api`.** For PUT and DELETE `/domain/placement/<sub>/<ref>`, the revision is the record's rev under P/08.6 N2 (feature placement.if-match).

<!-- req: P/07-R075 -->
**`api`.** The module recognizes a table by the form of the path: one or two segments after the prefix of the subsystem, the first is neither unit.rows nor the name of a platform door (P/02.1 N1.2a): the view /manifest does not name the tables.

<!-- req: P/07-R076 -->
**`api`.** The `ifMatch` option does not carry the index: a page that needs the index writes by the batch door with `cas`.

<!-- req: P/07-R077 -->
**`api`.** For a call with `opts.ifMatch`, the module refuses before sending a request if the method or path is outside P/07-R073, or if `ifMatch` is not an integer ≥ 1. The module refuses an `opts` field other than `ifMatch` before sending the request.

<!-- req: P/07-R078 -->
**`api`.** The module sends no other headers.

<!-- req: P/07-R079 -->
**`api`.** On HTTP 412, `console.api` throws `{status: 412, body: <received body>, retry: false}`, retaining the received body.

<!-- req: P/07-R080 -->
**`api`.** Other HTTP errors and replays follow P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094.

<!-- req: P/07-R081 -->
**`api`.** A page without api.if-match in features makes no revision-based write.

<!-- req: P/07-R082 -->
**`api`.** For POST with owner repeat memory (unit rows `/<rows>` and `/<sub>/<rows>`, P/06.1), the module uses one key per logical action rather than per equal body bytes. Automatic and manual replays of the logical action keep its key and an immutable snapshot of the original serialized body, even after the caller changes its object or nested values. A new `console.api` call gets a new logical-action key.

<!-- req: P/07-R085 -->
**`api`.** Each API attempt has a 20 s timeout through the complete response body, not only headers.

<!-- req: P/07-R086 -->
**`api`.** Network failure, the 20 s complete-body timeout of P/07-R085, 5xx or 409 in flight permit replay only at doors with owner repeat memory, as in P/07-R082. The module automatically replays only unit-row POST calls.

<!-- req: P/07-R087 -->
**`api`.** The module does not automatically replay calls of the requests door P/06.4 made by the page through api.

<!-- req: P/07-R088 -->
**`api`.** The delay before a replay is the response Retry-After header in seconds; without it, the delays are 2, 3, 5 s. After the third replay, the module throws the API refusal.

<!-- req: P/07-R090 -->
**`api`.** On HTTP 401, the module opens the login window.

<!-- req: P/07-R091 -->
**`api`.** The module does not automatically replay PUT, DELETE or table calls, even when the door has repeat memory (P/06.1 N3 «repeat memory»). When a PUT, DELETE or table call has an unknown outcome, the module reads first.

<!-- req: P/07-R093 -->
**`api`.** A completed API answer closes its logical action.

<!-- req: P/07-R094 -->
**`api`.** A refusal before request repeat memory is handled by the owner's contract. The module does not cache a refusal before request repeat memory as a success.

<!-- req: P/07-R095 -->
**`forms`.** For unitForm and the creation form, a 412 with body.row takes priority and uses the W.rowMoved screen of P/07-R102.

<!-- req: P/07-R096 -->
**`forms`.** For unitForm and the creation form, the module shows a 400, 409 or 412 refusal with body `field` at the named field, except the higher-priority 412 with `body.row` of P/07-R095. For a form refusal handled at a named field, the form-control name is the first token of refusal `field`, parsed as JSON Pointer under RFC 6901 (`~1` → `/`, `~0` → `~`; P/06.1 N2 «Refusal: error and field»). For a refusal shown at a form field, the module sets `aria-invalid="true"` on that field's control. Next to a control with a field refusal, the module places `.pc-field-err` containing refusal `detail`, or `error` if `detail` is absent. The module focuses the control receiving the field refusal.

<!-- req: P/07-R098 -->
**`forms`.** For `unitForm` and the creation form, any refusal not displayed by the higher-priority `body.row` screen of P/07-R095 or at a matching field under P/07-R096 is displayed in the common `.pc-err`; this includes absent `field` and pointers naming no form element.

<!-- req: P/07-R099 -->
**`forms`.** A new form submission removes the field-refusal marks.

<!-- req: P/07-R100 -->
**`forms`.** The code does not parse the refusal: the word and field come as fields of the body.

<!-- req: P/07-R101 -->
**`forms`.** The unit form (unitForm) sends PUT and DELETE with ifMatch — the revision of the shown row, always: otherwise an edit would overwrite someone else's silently.

<!-- req: P/07-R102 -->
**`forms`.** For a 412 with `body.row` under P/07-R095, the module replaces refusal text with a screen: `.pc-err` contains `W.rowMoved`, and adjacent `.pc-moved` contains the `body.row` form-field values differing from the input and a `.pc-reread` button.

<!-- req: P/07-R103 -->
**`forms`.** A form refusal without `body.row` follows P/07-R096, P/07-R098.

<!-- req: P/07-R104 -->
**`forms`.** The W.rowMoved screen retains the human's input; the module does not erase it.

<!-- req: P/07-R105 -->
**`forms`.** The .pc-reread button rereads rows and draws the form anew, resetting the input.

<!-- req: P/07-R106 -->
**`writes_via`.** If a subsystem manifest view (P/02.2) carries `unit.writes_via`, the module offers neither a creation form nor save/delete actions in `unitForm`. Fields in `unitForm` of a subsystem with `unit.writes_via` are read-only.

<!-- req: P/07-R107 -->
**`writes_via`.** For a table with `tables.<t>.writes_via`, the module offers no row-writing form.

<!-- req: P/07-R108 -->
**`writes_via`.** A human session attempting writes governed by `writes_via` always receives 403 `writes via` under P/06.1 N1.1a.

<!-- req: P/07-R109 -->
**`writes_via`.** `writes_via` does not change requests (P/06.4) or other page actions.

<!-- req: P/07-R110 -->
**`may`.** The call `console.may(cap, ref, sub?)` returns bool by the grants of the session and the scope rule P/06.3 N1.3 (* | `unit:<sub>/<id>` | `labels:<…>` | `folder:<id>`; a grant on the unit or on its about unit; the rank of cap — none < view < edit < admin, the right contract common/contracts/may.md). An omitted sub argument of console.may is null: a row of any sub fits. Session `grants` entries with `role` are role groups evaluated by the common may-contract tiers («The level of a role group»); entries without `role` are direct groups.

<!-- req: P/07-R113 -->
**`may`.** The module gathers the folder chains of a unit and its about unit by walking member lists from GET `/folders` in reverse. If the folder chains cannot be gathered, their input is unknown rather than empty: a group with such input gives no level, and a direct group's folder: row does not cover it.

<!-- req: P/07-R115 -->
**`may`.** For a session with `admin: true`, `console.may` returns true under the common may-contract step 4a, and the module hides nothing by that result.

<!-- req: P/07-R116 -->
**`may`.** For an emergency session with `via: break-glass` and `grants: []`, `console.may` returns true, as the server does under common may-contract step 1 (`glass` → allow).

<!-- req: P/07-R117 -->
**`may`.** Without grants, `console.may` returns true only with `open: true`.

<!-- req: P/07-R118 -->
**`may`.** In a closed or unknown session (`/session` did not answer), absent grants give `console.may` false.

<!-- req: P/07-R119 -->
**`may`.** The server checks every request independently of console.may.

<!-- req: P/07-R120 -->
**`events`.** The event roster is on("select", (ref, obj)), on("refresh", {units, servers, domain}), on("logout"), on("card.closed", {ref}) and on("session", {user}).

<!-- req: P/07-R121 -->
**`events`.** The module emits `session {user}` on every `/session` read with a known user: on mounting, including without login through the module window, and after ordinary or emergency login.

<!-- req: P/07-R122 -->
**`events`.** A subscription made after the `/session` read immediately receives the last session-event value.

<!-- req: P/07-R123 -->
**`events`.** An unknown user produces no session event.

<!-- req: P/07-R124 -->
**`events`.** When `/session` reports another user, the page resets its own state so that the former user's secrets do not enter the new user's write.

<!-- req: P/07-R125 -->
**`events`.** The module emits `card.closed` when a card is removed: another object is selected, selection is cleared (a section change, a deletion), or the page is left. For card.closed of a shell card, ref is that card's original name, for example streamaccounts:local or netvols. Polling that repaints the same selection emits no card.closed.

<!-- req: P/07-R129 -->
**`where`.** `where(ref)` returns `{worker, server, door: {url, token, expires, routes} | null, reason}`. The library converts an absent HTTP Where `door` field to null for the shell.

<!-- req: P/07-R130 -->
**`where`.** HTTP Where retains the form owned by P/06.5 in the lesson-6 contract.

<!-- req: P/07-R131 -->
**`words`.** The word API exposes `display(name)`, `manifest(name)`, `kindWord(e)`, `eventNote(e)` and `addEventNote`.

<!-- req: P/07-R353 -->
**`words`.** The module accepts unit captions, field captions, `field_help`, enum-choice captions and event-kind captions in either caption form: a string or `{key, text}`. The caption contract of P/06.5 N1.2 governs `{key, text}` captions: the module displays `text`. The localization-key/fallback criterion in P/07-R296 must preserve that owning contract.

<!-- req: P/07-R132 -->
**`words`.** `W` is the module's ru/en dictionary.

<!-- req: P/07-R133 -->
**`words`.** A kind in the closed W.kinds roster uses W, even when a manifest display.kinds collides with it. Only event kinds outside the closed W.kinds roster use display of the event subsystem.

<!-- req: P/07-R135 -->
**`adds`.** The call `addSection` accepts `{id, label, icon, after, off, render}`.

<!-- req: P/07-R136 -->
**`adds`.** The call `addTab(kind, {id, label, render, busy})` accepts kind ∈ unit | server | worker | member | domain.

<!-- req: P/07-R137 -->
**`adds`.** For `addTreeNodes(kind | servers | server, fn)`, `fn` returns nodes with fields `{ref, label, icon, count, kids, badge, tags, dot, title, off, open, after, replaces}`.

<!-- req: P/07-R138 -->
**`adds`.** `repaintTree()` rebuilds the tree from page-provided nodes when those nodes changed but the module's data did not (feature `tree.repaint`). `repaintTree()` preserves scroll as polling does. When a button is pressed, `repaintTree()` waits for its release before rebuilding the tree.

<!-- req: P/07-R139 -->
**`adds`.** The remaining extension call roster is addCard(prefix, render), addMenu, addDecor{icon, badge, title}, addFieldEditor(kind, field, render(host, ref, obj, value, set)), addBlock(kind, {id, covers, render}), addAction, addNote, addIcons, icon, unitForm(host, ref), dialog(title, fields, ok), confirm, toast, select(ref, {tab?}), selected, refresh, logout, fullScreen, isFav and toggleFav.

<!-- req: P/07-R140 -->
**`adds`.** `dialog(title, fields, ok)` returns a Promise resolving to field values `{<name>: <value>}` on pressing ok, or null on cancel. The ok argument of dialog is the button caption.

<!-- req: P/07-R142 -->
**`adds`.** `confirm(q, more)` immediately returns the human's true/false answer to question q with explanation more; the result is a value, not a Promise.

<!-- req: P/07-R143 -->
**`adds`.** `addBlock(kind)` accepts `kind` in server, member, domain.

<!-- req: P/07-R144 -->
**`adds`.** `addTreeNodes(kind)` accepts unit (nodes under a unit), servers, server, member and access.

<!-- req: P/07-R145 -->
**`adds`.** `select(ref, {tab})` selects an object (a unit or shell card) and opens the tab by the id passed to `addTab`; `general` names the module card. If select(ref, {tab}) names no existing tab, the card opens without changing the tab.

<!-- req: P/07-R147 -->
**`tree`.** With `display.tree.folders: true`, the module builds the section tree from GET `/folders`. In the folder tree, every live folder has one `folder:<id>` node. The parent of a folder-tree node is the folder's `parent`. A folder-tree node lists subfolders first, then members of this subsystem in `members` order. The module uses the folder's `name` as its folder-tree label.

<!-- req: P/07-R149 -->
**`tree`.** The module shows an empty folder as a node with zero units rather than as a browser filter. The module places a unit outside folders under a special node like «no group». A member of another subsystem, or a unit invisible to the module, produces no folder-tree node.

<!-- req: P/07-R152 -->
**`tree`.** The module renames a folder with one PUT `/folders/<id>` `{name}`, using `If-Match` containing the quoted store index (P/06.8 N2), rather than the integer `api.opts.ifMatch` of a page call.

<!-- req: P/07-R153 -->
**`tree`.** The module creates a folder or subfolder through POST `/folders`.

<!-- req: P/07-R154 -->
**`tree`.** The module adds or removes a unit through PUT `/folders/<id>` `{members}`. A folder-members write carries the entire member list. A folder-members write preserves the existing member order and appends a new unit at the end. A folder-members write uses the quoted store-index `If-Match` of P/07-R152.

<!-- req: P/07-R155 -->
**`tree`.** Folder-button rights use may(admin, …), as other writes do.

<!-- req: P/07-R156 -->
**`tree`.** A server refusal of a folder write follows the common door refusal handling (P/06.8 N3 «folder rights»).

<!-- req: P/07-R157 -->
**`tree`.** Without `display.tree.folders`, the module builds the tree by `group_by`.

<!-- req: P/07-R158 -->
**`return`.** After a login through the module window (password or emergency login) the module reads the parameter return of the page address: a value exactly `/<sub>/`, where `<sub>` is a subsystem of the catalogue of this console (the root and /mounts), — location.replace to it. Without a return parameter after login, the page stays. Any return value other than exactly `/<sub>/` for a catalogue subsystem redirects with location.replace to /: an absolute address, //…, a .. segment or its percent form (the parameter is already decoded), a subsystem outside the catalogue, a missing final /, a tail or a repeated parameter. The `return` value arrives by a link, so exact comparison protects against an open redirect (P/06.5 N2 «Login at the shell»).

<!-- req: P/07-R162 -->
**`cards`.** The module's card markup is `<h1>`, `nav.pc-tabs`, `<h2>` → `.card`, `button.pc-hdbtn`, `span.pc-crumbs[data-crumbs]`, `p.pc-hdsub`.

<!-- req: P/07-R163 -->
**`commands`.** For event kinds `command` and `command.failed`, the module supplies the word and note: action · outcome · answer · «by: by», with late rendered as «late».

<!-- req: P/07-R164 -->
**`commands`.** The worker base writes event fields `outcome`, `action`, `by`, `late`, `error` and `reply` under P/03.6 N3 «holder's look».

<!-- req: P/07-R165 -->
The session, grants and login used by `may` are owned by [P/06.3](../../06-console/spec/06.3-console.norms.md) (the gate, `/session`); independent server checking is P/07-R119.

<!-- req: P/07-R166 -->
The `display` words are owned by P/06.5 N1.2.

<!-- req: P/07-R167 -->
**Cluster refresh.** A cluster load emits the existing `refresh {units, servers, domain}` only when its own root `/servers` read is confirmed. In cluster `refresh {units, servers, domain}`, `servers` is exactly the confirmed root `/servers` read's `d.servers` map, not the whole Servers document, policy or merged profiles.

<!-- req: P/07-R169 -->
A failed root `/servers` read skips the cluster `refresh {units, servers, domain}` emission of that poll. After a failed root `/servers` read, ordinary reads, local repaint and the next poll continue.

<!-- req: P/07-R170 -->
Previous `/servers` data and the initial `{}` are not fresh root-server observations.

<!-- req: P/07-R171 -->
A confirmed empty root-server map, an unchanged map and the first same-map recovery after failure each produce the ordinary cluster refresh event. Cluster refresh is not filtered to changed maps only.

<!-- req: P/07-R327 -->
The module does not replay a missed cluster refresh event as a catch-up.

<!-- req: P/07-R172 -->
The root-confirmation condition for cluster refresh does not change holder-only `refresh {domain}`, access `refresh {access}`, select, logout, card.closed, session or `pc.ready`. The session-read, last-user replay and different-user secret-reset rules P/07-R121, P/07-R122, P/07-R123 and P/07-R124 remain unchanged by the cluster-refresh exception.

<!-- req: P/07-R174 -->
While the root `/servers` read is unconfirmed, a subscriber also misses the other data of that cluster poll through `refresh {units, servers, domain}`. Absence of the cluster refresh event is not a periodic health signal.

<!-- req: P/07-R175 -->
Local last-known/error state of refresh introduces no public error, field, value type or event.

<!-- req: P/07-R176 -->
A failed domain continuation uses the existing `domain: null` error carrier rather than a successful partial prefix.

<!-- req: P/07-R177 -->
Normal HTTP 200 values of P/10 `complete`, `unread` and other declared incomplete observations retain their owner meanings. The cluster-refresh frequency exception does not automatically reclassify normal HTTP 200 incomplete observations as transport errors. The cluster-refresh frequency exception does not turn `complete` into a client traversal flag.

<!-- req: P/07-R178 -->
**UI language, caption source and display dates.** The one editable source of platform captions is [data/localization.tsv](../data/localization.tsv), with the existing `key`, `en`, `ru` columns. The published module's `WORDS` dictionaries are a deterministic materialization of `data/localization.tsv`, not a second editable vocabulary.

<!-- req: P/07-R180 -->
For a localization key without a namespace, the module selects `WORDS[language][key]`. For localization key `n.<name>`, the module selects `WORDS[language].n[<name>]`. For localization key `kinds.<event-kind>`, the module selects `WORDS[language].kinds[<event-kind>]`, retaining the entire event-kind suffix literally, including its dots. The module does not split localization keys recursively at arbitrary dots: `n.late` and `kinds.server.decommission_requested` retain the distinct bindings.

<!-- req: P/07-R182 -->
The materialized Russian strings use JSON-compatible JavaScript Unicode escapes and have exactly the table's string values after ordinary JavaScript parsing. Materializing localization captions introduces no additional runtime decoder or vocabulary alias.

<!-- req: P/07-R184 -->
For each `mount(root, opts)` instance, the selected UI language is Russian only when `opts.lang === "ru"`; otherwise it is English, including when `lang` is omitted. The browser language does not select the module's language.

<!-- req: P/07-R186 -->
Caption materialization is present in the same synchronously served `/platform/console.js?v=1`: mounting, selecting Russian and rendering a caption require no locale-table fetch, new route, query parameter, storage key, version or public call.

<!-- req: P/07-R187 -->
The language of one mounted instance does not change another instance.

<!-- req: P/07-R188 -->
Subject captions and all protocol/data values remain as supplied by their owning contracts.

<!-- req: P/07-R189 -->
The module's UI timestamp/date renderings use an explicit locale of `ru-RU` for that instance's Russian UI and `en-US` for its English UI. The explicit UI locale applies to both full timestamps and day/month/short-time renderings.

<!-- req: P/07-R333 -->
Private names of timestamp/date rendering helpers do not become public API.

<!-- req: P/07-R191 -->
Full timestamp rendering retains its existing format options. Day/month/short-time rendering retains `day: "2-digit"`, `month: "2-digit"`, `hour: "2-digit"`, `minute: "2-digit"`, `hour12: false`.

<!-- req: P/07-R192 -->
Selecting the UI locale of P/07-R189 does not add a `timeZone` override or change the existing time zone, seconds-to-milliseconds conversion, precision, absent-value/dash handling, input parsing or serialization. The module's UI language/date rules do not translate or reformat protocol timestamps, deadlines, durations, request bodies, responses or stored values.

### N1.6 The domain section — the late layer: introduced by lessons 8 and 10 (without separate readiness ids)

<!-- req: P/07-R194 -->
The current `pending` view is a member-keyed count (`integer >= 0`) or `null` for an unreadable member row; it is not a list of edit descriptions. The module displays `pending` counts and the separate `outcomes` arrays independently, including zero and unknown counts.

<!-- req: P/07-R196 -->
Both domain loaders follow the opaque cursor of `GET /domain` under P/10-R004. The view assembled by either domain loader preserves all six per-member projections, required empty subsystem keys, complete contested claimant lists and global fields. In the assembled domain view, repeated conflict context is one conflict fact, not another member or another copy of that fact.

<!-- req: P/07-R199 -->
Ordinary paginated domain reads promise no snapshot across changes.

<!-- req: P/07-R335 -->
A failed continuation of a paginated domain read is not a complete successful read.

<!-- req: P/07-R200 -->
The parts of N1.4 and N1.5 that the domain introduces are parts of P/07-01 and P/07-02 without separate readiness ids (as P/02.1 N1.2b).

<!-- req: P/07-R201 -->
The domain console provides page doors under [lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) (holder page, P/10-04); [chapter P/06.7](../../06-console/spec/06.7-console.norms.md) defines forwarding to those doors and the cluster-console `/api/held` and `/domain/shared/<sub>` doors.

<!-- req: P/07-R202 -->
**`reads`.** In the late layer, the module reads `/domain/*` under the forwarding contract «Domain doors» (cluster-console forwarding, P/06.7-02…05), `/api/held` (P/06.7-14; term record and backup pair, P/08.8) and `/domain/shared/<sub>` (P/06.7-15).

<!-- req: P/07-R203 -->
**`writes`.** In the late layer, the module writes through `/domain/*` under the forwarding contract «Domain doors».

<!-- req: P/07-R204 -->
**`writes`.** For domain login, the module sends POST `{user, password}` to the `login_url` address from `/session`: POST `/api/login` (P/08.4 N1.2; gate-and-pass contract «The gate»); the cluster console forwards that door to the domain under «Domain doors».

<!-- req: P/07-R205 -->
**`order`.** Within the late-layer load, the module reads `/domain/shared/<sub>`, then `/domain` (plus `/domain/alarms`, P/10-06), then `/api/held`.

<!-- req: P/07-R206 -->
**`never`.** The module never calls `/api/backup` (P/06.7-16).

<!-- req: P/07-R207 -->
**`objects`.** The domain layer uses the object-reference roster of P/07-R068. Lessons 8 and 10 introduce the domain references in the roster of P/07-R068.

<!-- req: P/07-R209 -->
**`events`.** Domain observations are carried in the `domain` field of `refresh`.

<!-- req: P/07-R210 -->
**`events`.** After reading its doors, the access section emits `refresh {access}`.

<!-- req: P/07-R211 -->
**`adds`.** The late layer supplies the member and domain kinds of `addTab`.

<!-- req: P/07-R212 -->
**`adds`.** The late layer supplies the member and domain kinds of `addBlock`.

<!-- req: P/07-R213 -->
**`adds`.** The late-layer addTreeNodes kinds are member and access, as in P/07-R144.

<!-- req: P/07-R214 -->
**`sections`.** The option `opts.sections` defaults to `[units, access, journal]` (P/06.5 N1.1 `opts`); its access section belongs to the late layer and is defined in P/07-R221.

<!-- req: P/07-R215 -->
**`sections`.** With `opts.sections: [domain]`, the module provides the holder page of P/10-04.

<!-- req: P/07-R216 -->
**`domain`.** Domain is the root of the units panel's «By servers» layout rather than a strip section: it shows the holder location (GET /api/held), members, keys, topology, the move action, alarms and keys-view.

<!-- req: P/07-R217 -->
**`domain`.** «Move the domain here» opens a dialog with the recovery file as text and the no/yes choice «the old holder was stolen», submitting POST /domain/move {recovery[, stolen: true]}. Without a recovery file, the domain-move request is not sent.

<!-- req: P/07-R219 -->
**`domain`.** The domain alarm card has one row per kind and of: the last alarm, «×N (since …)» and the member list.

<!-- req: P/07-R220 -->
**`domain`.** The domain card carries the term, handover, «apply again», units by subsystem, shared settings by `declared`, and cluster edits (`pending` and `outcomes`).

<!-- req: P/07-R221 -->
**`access`.** The access section uses `/domain/users`, `/domain/grants` and `/domain/break-glass` for people, grants and break-glass under the forwarding contract «Domain doors».

<!-- req: P/07-R222 -->
**`held`.** GET `/api/held` is the only process door the module reads. At the cluster console, GET `/api/held` returns the signed public holder record `{cluster, holder, term, keys, backup: {term, rev}}`.

<!-- req: P/07-R223 -->
**`held`.** The `backup` field of `/api/held` points to the last copy at that member. The `backup` pointer is comparable only by the pair `{term, rev}`.

<!-- req: P/07-R224 -->
**`held`.** At a member, show «an old copy» when its backup pair is strictly behind the holder pair term.backup of GET /domain (P/08.8 N1.3). At a member, show «the holder no longer updates it» when that member is absent from term.backup_holders of the same GET /domain view.

<!-- req: P/07-R226 -->
**`held`.** The module compares backup pairs by term first, then rev at equal term (P/08.8, the largest `(term, rev)`). A backup pair lags behind another only when it is strictly smaller under the ordering. The module preserves exact number representations.

<!-- req: P/07-R229 -->
**`holder`.** With `sections: [domain]`, the module recognizes holder mode from the page sections and does not load units, `/servers` or `/unplaceable`. In holder mode, the module takes units by subsystem from the `/domain` view. In holder mode, the module survives the absence of `/servers`, `/drain`, `/schema`, `/unplaceable`, `/metrics` and `/events`; those doors are not needed at the holder.

<!-- req: P/07-R231 -->
**`schema`.** GET `/domain/shared` returns `{doc, delivery, declared: {<sub>: [{name, type, schema?}]}}` (P/10-14), with declared manifest `domain.shared` fields and their types. For a document `{name, type: json}`, GET `/domain/shared` also supplies its schema.

<!-- req: P/07-R339 -->
**`schema`.** The page builds a form for a JSON shared document by that document's supplied schema.

<!-- req: P/07-R233 -->
**`schema`.** The module submits a shared-document edit through PUT `/domain/shared` with `{base_rev, shared: {<sub>: {<field>: value | null}}}`.

<!-- req: P/07-R234 -->
In a schema-based shared-document form, an object uses `properties`, with required fields marked. In a schema-based shared-document form, a list uses elements by `items` with adding and removing. In a schema-based shared-document form, string, number, integer, yes/no and `enum` have their own fields.

<!-- req: P/07-R235 -->
An unexpressible schema form value uses JSON text in its place: an object without properties, a type union or a value with keys outside the schema.

<!-- req: P/07-R236 -->
Empty schema-form fields are omitted from submission. An empty schema-form document is submitted as null.

<!-- req: P/07-R238 -->
The domain checks the shared-document schema on PUT.

<!-- req: P/07-R239 -->
Lesson P/10 (P/10-04) serves the holder page (`/`, CSP, `/manifest`, `/mounts`, `/session`). Implementations serve the published holder-page module bytes unchanged.

<!-- req: P/07-R343 -->
Calls made in domain mode are a property of the published module rather than of individual implementations.

<!-- req: P/07-R240 -->
Both domain loaders collect the existing optional reader field `unread` by [P/10 N1.2a](../../10-domain-console/spec/10-domain-console.norms.md) and its `ServedView.unread` type in the [P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml).

<!-- req: P/07-R241 -->
If the `unread` field is absent from every domain page, the assembled view omits `unread`. Any supplied domain-page `unread` value keeps `unread` in the assembled view, including an empty result.

<!-- req: P/07-R242 -->
Both domain loaders union literal `unread` Part strings without duplicates, preserving first-observation and in-page order. A later absent or empty domain-page `unread` value never erases earlier observed parts. While assembling domain-page `unread`, the loaders perform no parsing, trimming, padding, sorting or normalization of Part strings.

<!-- req: P/07-R244 -->
Assembling domain-page `unread` does not change the constraints on individual responses. The module does not infer domain-view completeness from an absent `unread` field.

<!-- req: P/07-R245 -->
During domain-page assembly, the module keeps the first head's globals, all six projections, complete contested lists, required empty subsystem keys, opaque continuation and visibility unchanged.

<!-- req: P/07-R246 -->
A valid `200` with a normal incomplete `complete`/`unread` state remains an ordinary observation with its owner values, not a transport error.

<!-- req: P/07-R247 -->
The module may show observed normal domain incompleteness privately. Showing normal domain incompleteness adds no public event, field or client completeness flag. Showing normal domain incompleteness promises no snapshot.

<!-- req: P/07-R248 -->
A real failed domain continuation uses `domain: null` and private last-known/error state. The failed-domain-continuation handling leaves the cluster-refresh root-confirmation rule P/07-R167 unchanged.

---

## N2 The library contract

<!-- req: P/07-R249 -->
The module is a library of the platform in the browser, one code in all implementations: the lesson has no process, door or HTTP contract of its own. The library contract is two norms of N1: what the module calls (N1.4) and what it gives the shell (N1.5); the late layer — N1.6.

<!-- req: P/07-R251 -->
The called doors, their codes and forms are owned by the lesson-6 chapters and [lesson-6 contract](../../06-console/spec/06-console.api.openapi.yaml).

<!-- req: P/07-R350 -->
[Chapter 6.5](../../06-console/spec/06.5-console.norms.md) N1.1 governs byte-for-byte module publication, `?v=` and the page.

<!-- req: P/07-R252 -->
The shell calls the library of N1.5 inside its own page; these are not platform-to-subsystem hooks.

<!-- req: P/07-R351 -->
The shell takes stream and archive bytes from the holder through the door returned by `where()`, bypassing the console.

<!-- req: P/07-R253 -->
[`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) describes the public module surface: dictionary W, card markup, shell calls and appearance; that description is not a norm. Where the public-surface description or published bytes differ from N1.4 or N1.5, the lesson norms prevail.

---

## N3 Procedures

<!-- req: P/07-R255 -->
The lesson has no separate procedures: loading and polling are P/07-R009…P/07-R011; call replay is P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094.

<!-- req: P/07-R256 -->
Lesson-6 N3 defines the procedures of the doors called by the module.

---

## N4 Refusals

<!-- req: P/07-R257 -->
The lesson has no refusal roster of its own: door refusals come from lesson-6 N4 (including 404 `no such version` under [P/06.5 N4](../../06-console/spec/06.5-console.norms.md)); module handling is P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094, P/07-R095, P/07-R096, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105.

---

## N5 Acceptance

<!-- req: P/07-R258 -->
Behavioural evidence for the published module must apply to the current canonical P/07 module files. A test that loads a frozen Source module does not establish execution of the current canonical module. Declare fixture origins separately: a frozen wrapper is not the canonical module; an instrumented navigation return and a substituted shell-short module are not unchanged-module executions.

<!-- req: P/07-R260 -->
Check path/query neighbours, safe-integer edges, lossless list edits, scoped worker identities, current pending counts, both paginated loaders and disabled-section input.

<!-- req: P/07-R261 -->
J-P07-01 is a separate holder-fixture scope on the same corrected candidate.

<!-- req: P/07-R262 -->
No old positive array, error, incomplete output, or aggregate test count closes the existing open debts: `v1showsHidden`, the open tests of N5, P/07-07 and P/07-08.

<!-- req: P/07-R263 -->
The lesson has no acceptance catalogue (the exception `P/07 no-acceptance`): the module is a library in the browser, the HTTP-TSV stand does not run it.

<!-- req: P/07-R264 -->
The publication of the module byte for byte with the published files and the version `?v=1` (`?v=2` — 404) — sc. 01 (judge-only: module publication scenario) of the [acceptance of chapter 6.5](../../06-console/acceptance/5/README.md) (P/06.5 N1.1).

<!-- req: P/07-R265 -->
The specification owner supplies common evidence for N1.4 and N1.5 using jsdom checks and reading. Existing fixture cases are mapped in P/07-R271…P/07-R282 (judge-only: owner test sources in `Source/tests/console`; their input origin determines the scope of evidence under P/07-R258). The module is one for all implementations and the evidence is one for all.

<!-- req: P/07-R266 -->
For a generation line, P/07 is packaging: the published files are taken unchanged and checked byte for byte together with scenario 01 (judge-only: checks P/07-R264) of acceptance 6.5, including `?v=1`. The line does not rewrite JavaScript and gets no separate executable module profile.

<!-- req: P/07-R268 -->
The three tests `module-unplaceable-all` (judge-only: required cases for P/07-R016, P/07-R017; open debt, no evidence of closure), `module-subsystems-none` (judge-only: required cases for P/07-R012; open debt, no evidence of closure) and `module-writes-via` (judge-only: required cases for P/07-R106, P/07-R107, P/07-R109; open debt, no evidence of closure), and readiness items P/07-07 and P/07-08, remain an explicit debt of the owner of the published module bytes (the course canon, changed through Specification branches). The open tests and readiness debts are neither PASS nor FAIL of a generation line until the byte owner closes the debt.

<!-- req: P/07-R270 -->
The behavioural rules of N1.4 and N1.5 remain in force.

<!-- req: P/07-R271 -->
Row `P/07-R271` records bounded existing fixture cases for P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R202, P/07-R205, P/07-R206, P/07-R229.

<!-- req: P/07-R272 -->
Row `P/07-R272` records the existing mount-order, ordinary-polling and selected-unit-event fixture cases for P/07-R009…P/07-R011 and P/07-R205.

<!-- req: P/07-R273 -->
Row `P/07-R273` records bounded existing fixture cases for P/07-R019, P/07-R021, P/07-R023, P/07-R026, P/07-R029.

<!-- req: P/07-R274 -->
Row `P/07-R274` records bounded existing local-guard fixture cases for P/07-R059…P/07-R060 and separate HTTP acceptance for P/07-R264.

<!-- req: P/07-R275 -->
Row `P/07-R275` records bounded existing fixture cases for P/07-R082, P/07-R086, P/07-R088, P/07-R090, P/07-R091.

<!-- req: P/07-R276 -->
Row `P/07-R276` records bounded existing fixture cases for P/07-R110, P/07-R116…P/07-R118.

<!-- req: P/07-R277 -->
Row `P/07-R277` records bounded existing library fixture cases for P/07-R129 and separate HTTP acceptance for P/07-R130.

<!-- req: P/07-R278 -->
Row `P/07-R278` records bounded existing fixture cases for P/07-R068, P/07-R120, P/07-R121, P/07-R122, P/07-R131, P/07-R132, P/07-R133, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R142, P/07-R144, P/07-R162, P/07-R163, P/07-R167, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213.

<!-- req: P/07-R279 -->
Row `P/07-R279` records bounded existing fixture cases for P/07-R059, P/07-R065, P/07-R125, P/07-R145.

<!-- req: P/07-R280 -->
Row `P/07-R280` records bounded existing fixture cases for P/07-R158.

<!-- req: P/07-R281 -->
Row `P/07-R281` records bounded existing fixture cases for P/07-R095, P/07-R101…P/07-R102, P/07-R104…P/07-R105.

<!-- req: P/07-R282 -->
Row `P/07-R282` records bounded existing fixture cases for P/07-R096, P/07-R098.

<!-- req: P/07-R283 -->
Required verification of P/07-R147, P/07-R149, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157 is recorded in row `P/07-R283`; this reference does not declare closure.

<!-- req: P/07-R284 -->
Required verification of P/07-R012, P/07-R016, P/07-R017 is recorded in row `P/07-R284`; this reference does not declare closure.

<!-- req: P/07-R285 -->
Required verification of P/07-R106, P/07-R107, P/07-R108, P/07-R109 is recorded in row `P/07-R285`; this reference does not declare closure.

<!-- req: P/07-R286 -->
Required verification of P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R226, P/07-R229, P/07-R231, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R238, P/07-R239, P/07-R339, P/07-R343 is recorded in row `P/07-R286`; this reference does not declare closure.

| Subject | Reason | Place of proof |
|---|---|---|
| `P/07-R271` — N1.4 `reads`, `writes`, `never` — not a single call outside the list; the module does not call the doors of the holders | TSV talks to the doors, it does not see the calls of the page | jsdom test `module-calls` (judge-only: observed-call, mount, ordinary-polling and selected-unit-event fixture cases for P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R229; late-layer read/order cases for P/07-R202, P/07-R205 and the no-/api/backup case for P/07-R206): every intercepted request of the module (method and path) on mounting, polling, selection and edits is compared with `reads`/`writes`, the paths of `never` and the door from `where()` are not called; the mode `domain` — the same test. |
| `P/07-R272` — N1.4 `order`, polling every `poll_s`, `/events?unit=` of the selected one — every 5 s | the doors do not show the order of load | jsdom test `module-calls` (judge-only: existing mount-order, ordinary-polling and selected-unit-event fixture cases for P/07-R009…P/07-R011, P/07-R205): the order on mounting and on each ordinary poll, polling every `poll_s` of the page, `/events?unit=` of the selected one after 5 s. |
| `P/07-R273` — N1.4 `changes` — the number before the rows, a load on a message and on a reset, 404 removes the feed | TSV does not run the page | jsdom test `module-changes` (judge-only: existing immediate-feed fixture cases for P/07-R019, P/07-R021, P/07-R023, P/07-R026, P/07-R029): the change-feed number before the first row read, `after` and `wait`, a message about its own subsystem and a reset — a load, a foreign subsystem and an empty answer — none, 404 — one request, polling lives. |
| `P/07-R274` — N1.5 `version` — an integer, the shell compares it before use | the version in `?v=` is checked by the door, and the comparison is done by the page | Existing `platform-page` (judge-only: existing local mount-version guard cases for P/07-R059…P/07-R060; HTTP publication is separate acceptance) exercises the local guard before mount. HTTP publication and `?v=2`/404 belong to scenario 01 of P/06.5 acceptance (judge-only: acceptance scenario for P/07-R264). |
| `P/07-R275` — N1.5 `api` — a key of a logical action, a replay by the rules of the owner, `PUT` and tables without an automatic replay, 401 — the login window | TSV does not create a replay after a lost answer | Required subjects and existing bounded fixtures: jsdom test `module-retry` (judge-only: existing repeat-key/cause, Retry-After, limit and read-first cases for P/07-R082, P/07-R086, P/07-R088, P/07-R090, P/07-R091; no immutable-caller or complete-body-timeout evidence) (and `module-session` (judge-only: existing creation/logout, emergency-session and late-subscriber cases for P/07-R007, P/07-R120…P/07-R122): «Retry» with the same key): a new key per call, a replay only of `POST /<rows>`, `/<sub>/<rows>` with the same key and body, `Retry-After`, after the third replay — a refusal with `status`, `body`, `retry`; `PUT`, `DELETE`, `POST /marks`, `/drain`, the decommission of a server — without a replay, a read first; `POST`, `PUT`, `DELETE` of the tables of the root (`/testsub/<table>`) and of a mounted (`/<sub>/<table>`) subsystem — without a replay on a dropped connection and 5xx, a refusal without `retry`; 401 — the login window. |
| `P/07-R276` — N1.5 `may` — by the grants of the session; without grants `true` only with `open: true` | the grants are issued by the domain, the scenarios of lesson 6 run without the domain | jsdom test `module-may` (judge-only: existing basic scope/rank and session fixture cases for P/07-R110, P/07-R116…P/07-R118): rank and scope (`*`, `unit:` with an about unit, `labels:` at the about unit or at the unit itself), outside a unit, `via: break-glass`, an open, a closed and an unknown session; the server always checks — P/06.3. |
| `P/07-R277` — N1.5 `where` — `door` or `null` when the HTTP answer has no field `door` | the conversion is done by the library, not by the door | Existing `module-contract` (judge-only: Door-handoff example of P/07-R129 and absent-door conversion P/07-R129) uses mocked fetch. Real HTTP Where is checked by scenario 04 of P/06.5 acceptance (judge-only: acceptance scenario for P/07-R130). |
| `P/07-R278` — N1.5 `objects`, `events`, `words`, `adds`, `cards`, `commands`; without hooks and a foreign DOM | the subject is the behaviour of the page, not the doors | Required subjects and existing bounded fixtures: a jsdom test of the module and the shell, and reading; `objects` (`worker:<sub>/<w>`) — `module-contract` (judge-only: existing version/absent-door cases for P/07-R059, P/07-R129 and fixed unit-reference examples of P/07-R068), `module-servers` (judge-only: existing root-profile calls and ordinary card/reference cases for P/07-R006…P/07-R007, P/07-R068), `module-calls` (judge-only: observed-call, mount, ordinary-polling and selected-unit-event fixture cases for P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R229; late-layer read/order cases for P/07-R202, P/07-R205 and the no-/api/backup case for P/07-R206); `events` (`logout`) — `module-session` (judge-only: existing creation/logout, emergency-session and late-subscriber cases for P/07-R007, P/07-R120…P/07-R122); `events` `refresh {units, servers, domain}` and `refresh {access}` — `module-refresh-event` (judge-only: existing positive refresh/access payload cases for P/07-R167, P/07-R209, P/07-R210; no failed-root or continuation evidence); `adds` `addTreeNodes` of five kinds and the fields of a node — `module-tree-nodes` (judge-only: existing callback/node/repaint/scroll fixture cases for P/07-R137, P/07-R138, P/07-R144, P/07-R213; no pressed-button or HTTP folder-tree evidence), `addNote`, `addIcons`, `fullScreen`, `isFav`/`toggleFav` — `module-page-adds` (judge-only: existing visible-off/helper/dialog/confirm fixture cases for P/07-R054, P/07-R135, P/07-R136, P/07-R139, P/07-R140, P/07-R142, P/07-R211, P/07-R212; no disabled-activation evidence); `words` (ru and en of the same keys, the words of all event kinds; `display(name)` — the words of the manifest, for an unknown subsystem — empty; `eventNote` of the page after `addEventNote` — in the journal and on the events tab of the card, an event of the platform — in the words of the module) — `module-words` (judge-only: existing string-caption, explicit-language and dictionary cases for P/07-R131, P/07-R132, P/07-R133, P/07-R163, P/07-R166); `addSection` (`after`, `off` with a reason), `addTab` of four kinds with `select(ref, {tab})`, `busy()` — polling does not repaint, `addBlock` of a member and of the domain after its own blocks, `addAction` (`fn(ref, obj)` → the buttons of the header before the star), `dialog` (a promise of values, cancel — `null`), `confirm(q, more)` — the human's answer — `module-page-adds` (judge-only: existing visible-off/helper/dialog/confirm fixture cases for P/07-R054, P/07-R135, P/07-R136, P/07-R139, P/07-R140, P/07-R142, P/07-R211, P/07-R212; no disabled-activation evidence); `cards` (the header, the crumbs, the tabs, the buttons; `<h2>` → `.card` — first in `.box` («Implementation decides» item 3, closed)) — `module-card-markup` (judge-only: existing card DOM fixture cases for P/07-R162); without accesses to the DOM of the frame — by reading. Open criteria retain their own rows R292–R301; these fixtures supply no closure evidence for them. |
| `P/07-R279` — N1.5 `module`, `features`, `ready`, `select(ref, {tab})`, `card.closed` | the subject is the behaviour of the page | Required subjects and existing bounded fixtures: jsdom test `module-page-calls` (judge-only: existing ready/card/select and local ifMatch fixture cases for P/07-R059, P/07-R065, P/07-R072, P/07-R077, P/07-R079, P/07-R125, P/07-R145): `features`, version 1, `pc.ready` after `mount` and the first `/manifest` and after 401 → login, on a dropped connection and 503 of `/manifest` — it waits for the next poll without the login window and without an immediate replay, `select` with a tab, without it, with an unknown one and `general`, `card.closed` on a change of selection, a removal of selection, leaving the page, for a card of the shell, not on polling; the VMS page without accesses to the DOM of the frame (`shell.may_not`) — the tests of the page of the VMS owner and by reading. |
| `P/07-R280` — N1.5 `return` — the return after a login, protection from an open redirect | a call of the page, TSV goes to the doors and does not follow a `302` | jsdom test `module-return` (judge-only: instrumented navigation cases for P/07-R158; not an unchanged-module navigation execution): `/<sub>/` of its own catalogue and of the root — a transition; outside the catalogue, absolute, `//evil`, `/%2e%2e/`, with `..`, without the final `/`, with a tail, a repeated parameter — to `/`; without the parameter the page stays. |
| `P/07-R281` — N1.5 `forms` — `ifMatch` of the form, the screen of 412 | what the form sent and showed, TSV does not see | Required subjects and existing bounded fixtures: jsdom test `module-form-if-match` (judge-only: existing unit-form revision/body.row/input/reread cases for P/07-R095, P/07-R101…P/07-R102, P/07-R104…P/07-R105): PUT and DELETE carry `If-Match`, 412 — `.pc-moved`, the input is intact, `.pc-reread` rereads. |
| `P/07-R282` — N1.5 `forms` — a refusal at the field by `field` | what the form did with the refusal, TSV does not see | Required subjects and existing bounded fixtures: jsdom test `module-refusal-field` (judge-only: existing unit-form field/common-error fixture cases for P/07-R096, P/07-R098): the control of the field, `.pc-field-err`, the focus, the parsing of `~1`; without `field` and without a form element — the common `.pc-err`. |
| `P/07-R283` — N1.5 `tree` — the tree by the folders of the cluster | TSV does not see the calls of the page | Required future verification: jsdom test `module-folders` (judge-only: required cases for P/07-R147, P/07-R149, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157; open debt, no evidence of closure) (not written yet: the module does not do this, a debt of the product): the tree from `/folders`, an empty folder, a rename by one write. |
| `P/07-R284` — N1.4 `subsystems`, `unplaceable` | TSV does not see the calls of the page; the published canonical module [console.js](../module/console.js) does not execute the rule — an open debt of the owner of the published bytes | Required future verification: the owner of the published module bytes closes this debt with tests of the published canonical module bytes: `module-unplaceable-all` (judge-only: required cases for P/07-R016, P/07-R017; open debt, no evidence of closure) — an unplaced unit of a subsystem outside `opts.subsystems` is visible as a row of the section (subsystem, id, reason) without a card and without actions, `/<sub>/unplaceable` is called for every subsystem of the catalogue; `module-subsystems-none` (judge-only: required cases for P/07-R012; open debt, no evidence of closure) — `subsystems: []`: not a single `/<rows>`, `/<sub>/<rows>`, the tree is empty, the section of unplaced units reads all subsystems. Nonempty-selection cases P/07-R012 also require their own evidence. |
| `P/07-R285` — N1.5 `writes_via` — forms without a write | TSV does not see the calls of the page; the published canonical module [console.js](../module/console.js) does not know the word — an open debt of the owner of the published bytes | Required future verification: the owner of the published module bytes closes this debt with the test of the published canonical module bytes: `module-writes-via` (judge-only: required cases for P/07-R106, P/07-R107, P/07-R109; open debt, no evidence of closure) — a unit of a subsystem with `unit.writes_via` has no creation form, `unitForm` has no «save» and «delete», not a single `POST`, `PUT`, `DELETE` of the rows of this subsystem; a subsystem without the word has the forms. The server refusal P/07-R108 requires a separate door check under P/06.1 N1.1a. |
| `P/07-R286` — N1.6 the late layer (the mode `domain`, the sections `domain`, `access`, `login_url`, `refresh {access}`) | the stand of lesson 6 has no domain; TSV does not see the calls of the page | The required subject is the late layer. Existing `module-domain` (judge-only: recovery-file/move-body cases for P/07-R217), `holder-page` (judge-only: pending/outcomes and backup-badge cases for P/07-R194, P/07-R219, P/07-R224, P/07-R226) and `module-shared-schema` (judge-only: existing mocked form/serialization cases for P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R339; no server schema-validation evidence) supply only those fixture cases. People/holder doors belong to P/08.4/P/10 acceptance; these fixtures provide no pagination or unread evidence. |

### Criteria and debt of the published module bytes

<!-- req: P/07-R287 -->
The following criteria refine the existing N1.5 obligations.

<!-- req: P/07-R288 -->
The owner of the published common module bytes owns the N5 criteria; those bytes are course canon changed through Specification branches.

<!-- req: P/07-R289 -->
The published witness stays unchanged.

<!-- req: P/07-R290 -->
Each row of the criteria table is an open behavioural/evidence debt of the published-byte owner until an actual module test closes it; adding a criterion or copying the published files is not evidence of closure.

<!-- req: P/07-R291 -->
Generation lines package the same bytes and do not implement a replacement module.

<!-- req: P/07-R292 -->
Required verification of P/07-R110, P/07-R113, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119 is recorded in row `P/07-R292`; this reference does not declare closure.

<!-- req: P/07-R293 -->
Required verification of P/07-R095, P/07-R101…P/07-R105 is recorded in row `P/07-R293`; this reference does not declare closure.

<!-- req: P/07-R294 -->
Required verification of P/07-R082 is recorded in row `P/07-R294`; this reference does not declare closure.

<!-- req: P/07-R295 -->
Required verification of P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094 is recorded in row `P/07-R295`; this reference does not declare closure.

<!-- req: P/07-R296 -->
Required verification of P/07-R353 is recorded in row `P/07-R296`; this reference does not declare closure.

<!-- req: P/07-R297 -->
Required verification of P/07-R303 is recorded in row `P/07-R297`; this reference does not declare closure.

<!-- req: P/07-R298 -->
Required verification of P/07-R355 is recorded in row `P/07-R298`; this reference does not declare closure.

<!-- req: P/07-R299 -->
Required verification of P/07-R133 is recorded in row `P/07-R299`; this reference does not declare closure.

<!-- req: P/07-R300 -->
Required verification of P/07-R178, P/07-R180, P/07-R182, P/07-R184, P/07-R186, P/07-R187, P/07-R188 is recorded in row `P/07-R300`; this reference does not declare closure.

<!-- req: P/07-R301 -->
Required verification of P/07-R189, P/07-R191, P/07-R192, P/07-R333 is recorded in row `P/07-R301`; this reference does not declare closure.

| Criterion | Required module test | Debt owner and evidence boundary |
|---|---|---|
| `P/07-R292` — `may`, N1.5 | Required cases: `module-may`: `admin: true` with empty grants; a grant for another `sub`; direct groups and role tiers including a specific `none` over a general `edit`; folder and about-unit folder chains; an unavailable chain remains unknown and grants no level; closed, open, emergency and unknown sessions (judge-only: required cases for P/07-R110, P/07-R113, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119; open debt, no evidence of closure) | Published-byte owner; compare the existing common `may` contract, without changing the server's independent check. |
| `P/07-R293` — Every unit-form write, including an immediate boolean switch, N1.5 `forms` | Required cases: `module-form-if-match`: the shown revision is sent as `If-Match`; two quick clicks cannot bypass that revision; a concurrent change yields 412, keeps the input and shows the reread screen; an unreadable required revision permits no write (judge-only: required cases for P/07-R095, P/07-R101…P/07-R105; open debt, no evidence of closure) | Published-byte owner; a bool switch uses the same CAS/refusal path as the rest of the form. |
| `P/07-R294` — Immutable request snapshot, N1.5 `api` | Required cases: `module-retry`: mutate the caller's original object, including a nested value, after the initial call and again before manual Retry; automatic and manual retries retain the original serialized body and the same key (judge-only: required cases for P/07-R082; open debt, no evidence of closure) | Published-byte owner; a new call still gets a new key even for equal bytes. |
| `P/07-R295` — Complete-attempt timeout, N1.5 `api` | Required cases: `module-retry`: receive headers, then stall the body beyond 20 s; separately truncate the body. A unit POST retries only under the existing rule, with the same key and immutable body; PUT and table calls report an unknown outcome and reread without an automatic replay (judge-only: required cases for P/07-R082, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093, P/07-R094; open debt, no evidence of closure) | Published-byte owner; receiving headers does not complete an attempt or turn an incomplete body into a successful null answer. |
| `P/07-R296` — Captions as a string or `{key, text}`, N1.5 `words` | Required cases: `module-words`: unit and field captions, `field_help`, enum choices and event kinds in both caption forms; resolve the localization key with text as the declared fallback (judge-only: required cases for P/07-R353; open debt, no evidence of closure) | Published-byte owner; preserve the caption contract of P/06.5 and the existing localization keys. |
| `P/07-R297` — Hidden fields, N1.5 `forms` | Required cases: Module form tests: a `hidden: true` field is absent from the ordinary form and from an explicit `display.form`; visible neighbours remain present; omitted or false `hidden` keeps ordinary behaviour (judge-only: required cases for P/07-R303; open debt, no evidence of closure) | Published-byte owner; open `v1showsHidden` debt. |
| `P/07-R298` — Legal external names, N1.5 | Required cases: `module-words` and form/tree tests: `__proto__`, `constructor`, `toString` as unit identifiers and data names remain visible, selectable and editable according to their rights; no inherited property substitutes for a data entry (judge-only: required cases for P/07-R355; open debt, no evidence of closure) | Published-byte owner; the existing identifier grammar is not narrowed. |
| `P/07-R299` — Platform-kind priority, N1.5 `words` | Required cases: `module-words`: a closed platform event kind uses `W.kinds`; a colliding `display.kinds` in either the current subsystem or another subsystem cannot replace it. Other kinds use the event's subsystem display dictionary (judge-only: required cases for P/07-R133; open debt, no evidence of closure) | Published-byte owner; the closed platform roster is the existing `kinds.*` roster in the P/07 localization table. |
| `P/07-R300` — One caption source and selected UI language, N1.5 | Existing `module-words` and mount/page tests: materialize twice from the same locale table and compare the generated WORDS bytes; match every key and substitution parameter in both languages, including `n.late` and `kinds.server.decommission_requested`; default and non-`ru` selections use English even in a Russian-language browser, and exact `lang: "ru"` uses Russian in an English-language browser. Russian JS escapes parse once to the table's original strings. No locale fetch or additional locale route/storage/query/version/API is used (judge-only: required cases for P/07-R178, P/07-R180, P/07-R182, P/07-R184, P/07-R186, P/07-R187, P/07-R188; open debt, no evidence of closure) | Owner of the new canonical module bytes; the old frozen Source bytes and a path-only copy do not prove this rule. Existing bounded canonical-module fixture of the course (judge-only: existing canonical per-mount language-selection and interleaved-instance cases for P/07-R184 and P/07-R187). |
| `P/07-R301` — UI timestamp/date locale, N1.5 | Existing module/page tests exercise actual rendered timestamps and worker-slot dates with mismatched browser/UI languages and mixed-language mounted instances. Full and short renderings receive explicit `en-US` or `ru-RU` according to their instance; date options, original epoch milliseconds, browser time zone and protocol timestamps/bodies are unchanged (judge-only: required cases for P/07-R189, P/07-R191, P/07-R192, P/07-R333; open debt, no evidence of closure) | Owner of the new canonical module bytes; inspect observable rendering and request/storage effects, without exporting private format helpers or adding a test-only public API. Existing bounded canonical-module fixture of the course (judge-only: existing instrumented Date-locale/options cases for P/07-R189, P/07-R191; no rendered worker-slot DOM or unchanged-module execution). |

<!-- req: P/07-R302 -->
The related P/06 form `FieldView.hidden`: an optional boolean with no default; the required roster and closed shape are unchanged.

<!-- req: P/07-R303 -->
The module omits fields with `hidden: true` from generated forms, including an explicit `display.form`.

<!-- req: P/07-R304 -->
The P/06 form does not prove that the published module bytes implement hidden-field omission. The `v1showsHidden` debt remains open until the byte owner supplies actual module evidence.

---

## Implementation decides

The module is one code in all implementations: an implementation does not write it and chooses nothing in it, but serves the published bytes
(P/06.5 N1.1 `module`). On a generation line the judge observes only this packaging: the three published files byte for byte at their routes, `?v=1` served and `?v=2` answered 404 — scenario 01 (judge-only: checks P/07-R264) of acceptance 6.5 under P/07-R264 and P/07-R266; no item below changes that outcome. The items below are debts of the published module; the owner of the specification closes them; item 1 is not closed in full; items 2–5 are closed; items 6 and 7 remain open debts of this owner, not a separate module implementation by a generation line:

1. **not closed in full: conformance of the canonical `console.js`, `console.html` and `CONSOLE-MODULE.md` to N1.4 and N1.5.**
   Evidence applies only to the requirements and input files actually checked under P/07-R258; existing bounded fixture cases remain mapped in N5 rows P/07-R271…P/07-R282.
   The open criteria and byte-owner debts in N5 remain open; a generation line packages the published files unchanged under P/07-R266.
   The debt of the product — to «Build»: its copy of the module is brought to these bytes.
2. **closed: the form of the shared document by `schema`** (N1.6 `schema`).
   The evidence —
   the mocked shared-form/serialization fixture in N5 row P/07-R286 (no server schema-validation evidence). The debt of the product — to «Build».
3. **closed: `<h2>` → `.card`** (N1.5 `cards`).
   The evidence —
   the card DOM fixture in N5 row P/07-R278. The debt of the product — to «Build».
4. **closed: a refusal at the field by `field`** (N1.5 `forms`).
   The evidence — the unit-form field/common-error fixture in N5 row P/07-R282. The debt of the product — to «Build».
5. **closed: rows by the feed** (N1.4 `changes`). The evidence — the immediate-feed fixture in N5 row P/07-R273. The debt of the product — to «Build».
6. **not closed: the unplaced units of all subsystems and `subsystems: []`** (N1.4) — the published canonical module [console.js](../module/console.js) reads `/<sub>/unplaceable` only for the subsystems of `opts.subsystems`; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; the required verification is N5 row P/07-R284 (open debt, no evidence of closure).
7. **not closed: forms without a write for `writes_via`** (N1.5 `writes_via`) — the published canonical module [console.js](../module/console.js) does not know the word and draws the forms; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; the required verification is N5 row P/07-R285 (open debt, no evidence of closure).

---

## Readiness checklist

An implementation conforms to the lesson when every norm is met; the norm id `P/07-MM` is what the deltas of decisions,
findings and window records refer to. The implementation here is the published module, one for all (N2).

- [ ] **P/07-01** [test] the closed list of calls of the module N1.4 and the order of load — checked by a jsdom test: the calls of the module and their order — by N1.4 `reads`/`writes`/`never`/`order`; the reason — the module is one for all implementations, the doors do not show the order of load; the place of proof — the jsdom test of the owner of the specification `Source/tests/console/module-calls.test.js` (judge-only: observed-call, mount, ordinary-polling and selected-unit-event fixture cases for P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R229; late-layer read/order cases for P/07-R202, P/07-R205 and the no-/api/backup case for P/07-R206) (N5); the parts of the late layer — N1.6 `reads`, `writes` (`login_url`), `order`, `never`, the mode `holder` (`sections: [domain]`)
- [ ] **P/07-02** [test, reading] the shell contract N1.5: `api` with a key of a logical action and replays only by the contract of the owner, `where` with `door`, the calls of the library, without hooks and a foreign DOM — checked by reading: the test of the shell (jsdom; the subject is the behaviour of the page, not the doors); the reason — TSV talks to the doors, it does not run the page; the place of proof — `Source/tests/console` (judge-only: owner test sources; existing fixture cases are mapped in N5 rows P/07-R271…P/07-R282) (N5); `api`, `may`, `version`, `where`, `objects`, `events` — jsdom tests `module-retry` (judge-only: existing repeat-key/cause, Retry-After, limit and read-first cases for P/07-R082, P/07-R086, P/07-R088, P/07-R090, P/07-R091; no immutable-caller or complete-body-timeout evidence), `module-may` (judge-only: existing basic scope/rank and session fixture cases for P/07-R110, P/07-R116…P/07-R118), `platform-page` (judge-only: existing local mount-version guard cases for P/07-R059…P/07-R060; HTTP publication is separate acceptance), `module-contract` (judge-only: existing version/absent-door cases for P/07-R059, P/07-R129 and fixed unit-reference examples of P/07-R068), `module-session` (judge-only: existing creation/logout, emergency-session and late-subscriber cases for P/07-R007, P/07-R120…P/07-R122); `features`, `ready`, `select(ref, {tab})`, `card.closed` — `module-page-calls` (judge-only: existing ready/card/select and local ifMatch fixture cases for P/07-R059, P/07-R065, P/07-R072, P/07-R077, P/07-R079, P/07-R125, P/07-R145) (N5); the parts of the late layer — N1.6 `objects`, `events` (`refresh {access}`), `adds`, the sections `domain`, `access`, `held`, `schema` (the form by `schema` — jsdom test `module-shared-schema` (judge-only: existing mocked form/serialization cases for P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R339; no server schema-validation evidence)); `return` — jsdom test `module-return` (judge-only: instrumented navigation cases for P/07-R158; not an unchanged-module navigation execution)
- [ ] **P/07-04** [test] the unit form always sends `ifMatch`, the screen of 412 N1.5 `forms`; `api` with `ifMatch` at tables and settings doors — jsdom tests `Source/tests/console/module-form-if-match.test.js` (judge-only: existing unit-form revision/body.row/input/reread cases for P/07-R095, P/07-R101…P/07-R102, P/07-R104…P/07-R105), `module-page-calls.test.js` (judge-only: existing ready/card/select and local ifMatch fixture cases for P/07-R059, P/07-R065, P/07-R072, P/07-R077, P/07-R079, P/07-R125, P/07-R145) (N5); the reason — TSV does not see the behaviour of the page
- [ ] **P/07-05** [test] rows by the feed N1.4 `changes` — checked by jsdom tests `Source/tests/console/module-changes.test.js` (judge-only: existing immediate-feed fixture cases for P/07-R019, P/07-R021, P/07-R023, P/07-R026, P/07-R029), `module-calls.test.js` (judge-only: observed-call, mount, ordinary-polling and selected-unit-event fixture cases for P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R229; late-layer read/order cases for P/07-R202, P/07-R205 and the no-/api/backup case for P/07-R206) (N5); the reason — TSV does not run the page
- [ ] **P/07-03** [test] a refusal at the field N1.5 `forms` — checked by jsdom test `Source/tests/console/module-refusal-field.test.js` (judge-only: existing unit-form field/common-error fixture cases for P/07-R096, P/07-R098) (N5); the reason — TSV does not run the page
- [ ] **P/07-06** [test] the tree by the folders of the cluster N1.5 `tree` — checked by jsdom test `module-folders` (judge-only: required cases for P/07-R147, P/07-R149, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157; open debt, no evidence of closure) (N5) when the module has it; the reason — TSV does not run the page
- [ ] **P/07-07** [test] `opts.subsystems` and the unplaced units of all subsystems of the catalogue N1.4 — the owner of the published common module bytes closes this debt with `module-unplaceable-all` (judge-only: required cases for P/07-R016, P/07-R017; open debt, no evidence of closure), `module-subsystems-none` (judge-only: required cases for P/07-R012; open debt, no evidence of closure) (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page
- [ ] **P/07-08** [test] forms without a write at a subsystem with `writes_via` N1.5 — the owner of the published common module bytes closes this debt with `module-writes-via` (judge-only: required cases for P/07-R106, P/07-R107, P/07-R109; open debt, no evidence of closure) (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page

**Related byte-owner debt `v1showsHidden` (N5, alongside P/07-07 and P/07-08).** The version-1 published behaviour that shows hidden fields is not accepted as the rule. The byte owner must demonstrate omission from both the ordinary form and explicit `display.form`, with visible controls preserved. The P/06 OpenAPI property is source-form evidence only and closes no behavioural debt.

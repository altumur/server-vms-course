# P/07 — Console module: norms

This English text is the source; the Russian translation `ru/spec/07-console-module.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The canon of the lesson. Lecture (`ru/07-console-module.md`, for people, not in the export), [instructions](07-console-module.README.md). The lesson has no HTTP contract
of its own: the module is a library in the browser, it has no door of its own (N2); the doors it calls are the [contract of lesson
6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer (N1.6) also the contracts of lessons
[8](../../08-domain/spec/08-domain.api.openapi.yaml) and [10](../../10-domain-console/spec/10-domain-console.api.openapi.yaml). The lesson has no acceptance catalogue (N5); it has no life cycle: a library has no process,
environment or exit codes; the publication of the module is [chapter 6.5](../../06-console/spec/06.5-console.norms.md).
The late layer — the domain section, `sections: [domain]` of the call `mount`, the
holder mode — is N1.6, without separate readiness ids of its own.
The canon of the module is the norms N1.5: the published
bytes of `console.js`, `console.html` and the description [`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) follow
it («Implementation decides» item 1, closed). The three parts of the console, the mounting
`PlatformConsole.mount(root, opts)`, `opts`, `never` of the module and `may`/`may_not` of the shell — [P/06.5 N1.1](../../06-console/spec/06.5-console.norms.md)
`module`, `shell`. A reference «lesson N» without a chapter is the module lesson P/NN; «P/06.K», «P/08.K» are the chapters of lessons 6 and 8;
«P/10» is the lesson of the domain console. Readiness ids are `P/07-MM`; individual requirements have `P/07-RNNN` anchors.

## Index

Topics whose requirements appear in several places. Each requirement in a row ends with the other requirement ids of its topics. File paths are from the lesson root.

| Topic | Requirements | Files |
|---|---|---|
| `library_boundary` Library boundary and ownership | P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `call_roster` Closed call list | P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `load_order` Load order and polling | P/07-R009, P/07-R010, P/07-R011, P/07-R205, P/07-R271, P/07-R272, P/07-R273, P/07-R278, P/07-R279 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `subsystems` Subsystem selection and unplaced units | P/07-R012, P/07-R013, P/07-R014, P/07-R015, P/07-R016, P/07-R017, P/07-R018, P/07-R284 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `change_feed` Change feed | P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `worker_profiles` Worker observations by profile | P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `module_api` Module object, version and readiness | P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `references` Object references | P/07-R068, P/07-R207, P/07-R208, P/07-R278 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `api_cas` API, CAS and replay | P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `form_values` Lossless form values | P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R260, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `form_refusals` Form writes and refusals | P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `writes_via` Writes through an owner | P/07-R106, P/07-R107, P/07-R108, P/07-R109, P/07-R285 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `rights` Session rights | P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `events` Public events | P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R278, P/07-R279 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `refresh` Confirmed cluster refresh | P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R245, P/07-R246, P/07-R247, P/07-R248 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `where` Holder door handoff | P/07-R128, P/07-R129, P/07-R130, P/07-R277 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `captions` Caption resolution | P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R299, P/07-R300 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md`, `data/localization.tsv` |
| `ui_language` UI language and displayed dates | P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md`, `data/localization.tsv` |
| `extensions` Shell extensions and input | P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `folders` Folder tree | P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `login_return` Return after login | P/07-R158, P/07-R159, P/07-R160, P/07-R161, P/07-R280 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `card_markup` Card markup | P/07-R162, P/07-R278 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `event_words` Command event text | P/07-R163, P/07-R164, P/07-R278 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `pending` Pending counts | P/07-R194, P/07-R195, P/07-R260 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `domain_pages` Domain pagination and unread parts | P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `domain_mode` Late layer and holder mode | P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `held_backup` Holder record and backup pair | P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `shared_schema` Shared-document form | P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R238, P/07-R239 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |
| `proof_boundary` Packaging, evidence and open debts | P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304 | `spec/07-console-module.README.md`, `CONSOLE-MODULE.md` |

## N0 Vocabulary

<!-- req: P/07-R001 -->
- Normative words follow the [course canon](../../common/NORMATIVE-TERMS.md).

See also: P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R002 -->
- The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

See also: P/07-R001, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

## N1 Form

<!-- req: P/07-R003 -->
- **Time.** The lesson has no time fields in rows and objects: the module writes no rows or objects of its own, as defined in P/07-R005.

See also: P/07-R001, P/07-R002, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R004 -->
- Time in the answers of the doors that it shows (`until` of the session, `expires` of the door from `where()`) has the form of [P/06.3](../../06-console/spec/06.3-console.norms.md) and [P/06.5](../../06-console/spec/06.5-console.norms.md).

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R005 -->
- **Data.** The lesson has no rows, objects or files of its own: the module reads and writes only through the doors of the closed list N1.4 — the doors of lesson 6, in the late layer (N1.6) also the doors of the domain: `/domain/*` and the login `login_url` (`POST /api/login`) — the doors of the domain console ([lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md); the process `domain` — [lesson P/08](../../08-domain/spec/08-domain.api.openapi.yaml)), which the cluster console forwards ([chapter P/06.7](../../06-console/spec/06.7-console.norms.md); the [forwarding contract](../../common/contracts/forwarding.md) «Domain doors»), and the own doors of the cluster console `/api/held`, `/domain/shared/<sub>` (chapter P/06.7); the forms — the [contract of lesson 6](../../06-console/spec/06-console.api.openapi.yaml), in the late layer — the contracts of lessons 8 and 10; the owners of the rows — the chapters of lessons 6, 8 and their catalogue.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

### N1.4 What the module calls — a closed list

<!-- req: P/07-R006 -->
- **`reads`.** The module's permitted reads are: /session, /manifest, `/<sub>/manifest`, /mounts, /changes, `/<rows>`, `/<sub>/<rows>`, `/<sub>/<table>` (only from servers.show), `/where/<id>`, `/<sub>/where/<id>`, /servers, `/<sub>/servers` (only loaded subsystem profiles), /unplaceable, `/<sub>/unplaceable`, /policy, /drain, /schema, /events, /metrics (only running_gauge and workers_gauge), /domain/* (forwarding contract «Domain doors»), /api/held (P/06.7-14), `/domain/shared/<sub>` (P/06.7-15), /folders (only with display.tree.folders).

See also: P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R007 -->
- **`writes`.** POST/PUT/DELETE `/<rows>[/<id>]` and `/<sub>/<rows>[/<id>]`, POST /folders, PUT/DELETE `/folders/<id>` (only with display.tree.folders), POST /marks, PUT /policy, POST/DELETE /drain, GET/PUT/DELETE `/servers/<s>/labels`, POST/DELETE `/servers/<s>/decommission`, /domain/* (forwarding contract «Domain doors»), POST/DELETE /session, /session/break-glass, login_url

See also: P/07-R006, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R008 -->
- **`never`.** /{sub}/requests, /api/backup (P/06.7-16), /resources, /{sub}/{table} outside show, the doors of the holders (door from where — only to the shell)

See also: P/07-R006, P/07-R007, P/07-R031, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R009 -->
- **`order`.** /session → /manifest → /mounts → /changes (only on mounting) → per subsystem `/<rows>` → /folders (if at least one subsystem declared display.tree.folders) → /servers → `/<sub>/servers` (other catalogue profiles, in order) → /unplaceable → `/domain/shared/<sub>` (P/06.7-15) → /drain → /schema → /domain (+ /domain/alarms; P/10-06) → /api/held (P/06.7-14) → /metrics;

See also: P/07-R010, P/07-R011, P/07-R205, P/07-R271, P/07-R272, P/07-R273, P/07-R278, P/07-R279.

<!-- req: P/07-R010 -->
- **`order`.** polling every poll_s;

See also: P/07-R009, P/07-R011, P/07-R205, P/07-R271, P/07-R272, P/07-R273, P/07-R278, P/07-R279.

<!-- req: P/07-R011 -->
- **`order`.** /events?unit= of the selected one — every 5 s

See also: P/07-R009, P/07-R010, P/07-R205, P/07-R271, P/07-R272, P/07-R273, P/07-R278, P/07-R279.

<!-- req: P/07-R012 -->
- **`subsystems`.** opts.subsystems — the names of the subsystems of the catalogue (the root and /mounts) whose units the module loads, shows as a tree and writes (`/<rows>`, `/<sub>/<rows>`, the card, the forms);

See also: P/07-R013, P/07-R014, P/07-R015, P/07-R016, P/07-R017, P/07-R018, P/07-R284.

<!-- req: P/07-R013 -->
- **`subsystems`.** When opts.subsystems is absent, the module loads, shows and writes units of all catalogue subsystems.

See also: P/07-R012, P/07-R014, P/07-R015, P/07-R016, P/07-R017, P/07-R018, P/07-R284.

<!-- req: P/07-R014 -->
- **`subsystems`.** When opts.subsystems is a list, the module loads, shows and writes units only of the named subsystems.

See also: P/07-R012, P/07-R013, P/07-R015, P/07-R016, P/07-R017, P/07-R018, P/07-R284.

<!-- req: P/07-R015 -->
- **`subsystems`.** When opts.subsystems is [], the module loads, shows and writes no subsystem units.

See also: P/07-R012, P/07-R013, P/07-R014, P/07-R016, P/07-R017, P/07-R018, P/07-R284.

<!-- req: P/07-R016 -->
- **`unplaceable`.** The module reads /unplaceable and `/<sub>/unplaceable` at every catalogue subsystem regardless of opts.subsystems; these observations are read-only.

See also: P/07-R012, P/07-R013, P/07-R014, P/07-R015, P/07-R017, P/07-R018, P/07-R284.

<!-- req: P/07-R017 -->
- **`unplaceable`.** An unplaced unit of a subsystem outside opts.subsystems appears as a section row (subsystem, id, reason), without a card or actions.

See also: P/07-R012, P/07-R013, P/07-R014, P/07-R015, P/07-R016, P/07-R018, P/07-R284.

<!-- req: P/07-R018 -->
- **`unplaceable`.** Reading unplaced units only at the subsystems shown by the page would leave the other subsystems' unplaced units invisible; P/07-R016 requires reading the whole catalogue.

See also: P/07-R012, P/07-R013, P/07-R014, P/07-R015, P/07-R016, P/07-R017, P/07-R284.

<!-- req: P/07-R019 -->
- **`changes`.** For GET /changes (P/06.1 N2 «Change feed»), the module obtains a number before the first row read.

See also: P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R020 -->
- **`changes`.** After obtaining that number, the module holds `/changes?after=<number>&wait=15`.

See also: P/07-R019, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R021 -->
- **`changes`.** After an immediate return or disconnect of /changes, the module issues a new request at most once a second.

See also: P/07-R019, P/07-R020, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R022 -->
- **`changes`.** The request-frequency limit of P/07-R021 does not shorten the held wait=15 request.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R023 -->
- **`changes`.** A reset or a message about a row of a page subsystem starts the load order of P/07-R009 immediately and silently: the page sees the edit within a tick rather than poll_s.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R024 -->
- **`changes`.** The message carries no value, so the module rereads the rows instead of applying the message;

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R025 -->
- **`changes`.** The module need not compare revision when handling a change-feed message.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R026 -->
- **`changes`.** 404 — the console has no feed: the module no longer calls it and lives by polling;

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R027 -->
- **`changes`.** On a /changes refusal other than 404, or a dropped connection, the next feed attempt is after poll_s, without the login window; polling raises that window.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R028, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R028 -->
- **`changes`.** A /changes answer to a request without after (no number yet) counts as a reset.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R029, P/07-R030, P/07-R273.

<!-- req: P/07-R029 -->
- **`changes`.** The holder page of P/07-R229 does not call the change feed: the domain console has none.

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R030, P/07-R273.

<!-- req: P/07-R030 -->
- **`changes`.** Polling by poll_s remains: GET `/<rows>` also carries the heartbeats, and /servers and /metrics have no feed (the scope of the feed — the rows of units and of tables)

See also: P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R273.

<!-- req: P/07-R031 -->
- The list is about the module's own calls: `never` forbids them to the module, not to the page; a call of the page through `console.api` (the VMS page — `POST /<sub>/requests`, the requests door P/06.4) is its call, not the module's.

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R032 -->
- The words `servers.show`, `console.running` (`running_gauge`, `workers_gauge`) and `poll_s` — [P/06.5](../../06-console/spec/06.5-console.norms.md) N1.1, N1.2.

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R033 -->
- The parts of the list that the domain introduces (`/domain/*`, `/api/held`, `/domain/shared/<sub>`, `/domain/alarms`, `login_url`) are the late layer N1.6.

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R271.

<!-- req: P/07-R034 -->
- Worker observations use the existing request context of P/06.5 N2.

See also: P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R035 -->
- In the servers phase, read root `/servers` once, then the other loaded catalogue profiles through `/<sub>/servers` in catalogue order.

See also: P/07-R034, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R036 -->
- The explicit root prefix is the same profile, not another observation.

See also: P/07-R034, P/07-R035, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R037 -->
- `opts.subsystems` limits unit loading, not these observations; `[]` does not make the profile catalogue empty.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R038 -->
- An unconfirmed catalogue is unknown, not an empty or confirmed working profile.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R039 -->
- Keep documents and their policy/ServerRow observations separate by profile.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R040 -->
- The private worker identity is the exact `(sub, worker)` from the confirmed request context; the existing reference is `worker:<sub>/<w>`.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R041 -->
- Selection and callbacks use the original WorkerRow of that profile without adding a synthetic `sub`.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R042 -->
- Do not substitute root, join on a short name or read internal storage.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R043 -->
- An unreadable, refused or unavailable profile remains unknown, without an empty-worker fact or another profile's row as fallback.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R044, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R044 -->
- A last-known observation is not a successful current read.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R045, P/07-R046, P/07-R260.

<!-- req: P/07-R045 -->
- The public `refresh.servers` remains exactly the root response's `d.servers` map, not the entire Servers document, its policy or merged profiles; private error/last-known state adds no public field or event.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R046, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R046 -->
- P/06 API and WorkerRow are unchanged.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R260.

### N1.5 The contract of the module with the shell

<!-- req: P/07-R047 -->
- Classify only the path before the query, using the root and mounted subsystem routes already declared by P/06.5 N2.

See also: P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R048 -->
- Keep the original request address, CAS revision, logical-action key and replay rules.

See also: P/07-R047, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R049 -->
- A query does not make a service door a table or permit `ifMatch` there.

See also: P/07-R047, P/07-R048, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R050 -->
- An `int` control never truncates the input.

See also: P/07-R051, P/07-R052, P/07-R053, P/07-R260, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R051 -->
- It sends the same safely representable integer as an ordinary JSON integer, or refuses locally with the text retained and no substituted number sent.

See also: P/07-R050, P/07-R052, P/07-R053, P/07-R260, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R052 -->
- A list remains a typed list across display, editing another element and submission: commas inside a string, empty strings, order and duplicates are not lost by splitting, trimming or deduplication.

See also: P/07-R050, P/07-R051, P/07-R053, P/07-R260, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R053 -->
- Ordinary lists acquire no placement-label restriction.

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R260, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R054 -->
- An added section with an `off` reason stays visible with that reason, but neither mouse nor keyboard activation enters it or invokes its `render`.

See also: P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R055 -->
- An enabled neighbouring section still works.

See also: P/07-R054, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R056 -->
- This is UI behaviour, not a server permission.

See also: P/07-R054, P/07-R055, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R057 -->
- **`module`.** one module object — PlatformConsole {version, features, mount};

See also: P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R058 -->
- **`module`.** mount(root, opts) returns the page object (pc — the name of the page variable in the examples, not a second object)

See also: P/07-R057, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R059 -->
- **`version`.** console.version — an integer, the version of the shell API (P/06.5 N1.1 version);

See also: P/07-R057, P/07-R058, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R060 -->
- **`version`.** The shell checks console.version before using the module.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R061 -->
- **`version`.** console.version stays 1: features, ready, select with tab and card.closed are additions, and the load ?v=1 is unchanged.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R062 -->
- **`features`.** PlatformConsole.features — a list of strings of capabilities beyond the first calls of version 1: "select.tab", "card.closed", "api.if-match", "placement.if-match", "session", "tree.repaint";

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R063 -->
- **`features`.** A capability absent from PlatformConsole.features is unavailable.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R064 -->
- **`features`.** The page discovers added capabilities through PlatformConsole.features rather than console.version.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R065 -->
- **`ready`.** pc.ready — a promise (Promise), no new call: it resolves with the page object after mount and the first read /manifest (there is no door /spec — N1.4);

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R066 -->
- **`ready`.** On a 401 response to /manifest, pc.ready waits for login and resolves after it.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R067 -->
- **`ready`.** /manifest not read (network, 5xx) — the module reads it again by polling, the promise waits

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R274, P/07-R279.

<!-- req: P/07-R068 -->
- **`objects`.** ref: `unit:<sub>/<id>` | `server:<s>` | `worker:<sub>/<w>` | `member:<m>` | domain | `person:<name>` | `group:<sub>/<field>/<path>` | `folder:<id>` | `<prefix>:<…>` of the shell (the module only stores it)

See also: P/07-R207, P/07-R208, P/07-R278.

<!-- req: P/07-R069 -->
- **`api`.** console.api(method, path, body, opts?) returns an answer or throws {status, body, retry}.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R070 -->
- **`api`.** The door list of P/07-R073 and the ifMatch type of P/07-R072 apply to page calls through console.api.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R071 -->
- **`api`.** The module makes its own writes only by the list of P/07-R007.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R072 -->
- **`api`.** opts.ifMatch — an integer ≥ 1 (revision, P/06.1 N2 «Versions») → the header If-Match;

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R073 -->
- **`api`.** opts.ifMatch is accepted only at doors that read it: PUT and DELETE of a unit row `/<rows>/<id>`; POST `/<t>` and DELETE `/<t>/<name>` of a subsystem table; PUT /policy; POST and DELETE /drain; PUT and DELETE `/servers/<s>/labels`; PUT /schema; PUT and DELETE `/domain/placement/<sub>/<ref>`. Other doors would write without CAS.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R074 -->
- **`api`.** For PUT and DELETE `/domain/placement/<sub>/<ref>`, the revision is the record's rev under P/08.6 N2 (feature placement.if-match).

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R075 -->
- **`api`.** The module recognizes a table by the form of the path: one or two segments after the prefix of the subsystem, the first is neither unit.rows nor the name of a platform door (P/02.1 N1.2a): the view /manifest does not name the tables.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R076 -->
- **`api`.** ifMatch does not carry the index: a page that needs the index writes by the batch door with cas.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R077 -->
- **`api`.** Another method, another path, a field of opts other than ifMatch, ifMatch not an integer ≥ 1 — the call is refused before the request.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R078 -->
- **`api`.** The module sends no other headers from api opts.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R079 -->
- **`api`.** 412 → throw {status: 412, body — as received, retry: false};

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R080 -->
- **`api`.** Other HTTP errors and replays follow P/07-R085, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R093 and P/07-R094.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R081 -->
- **`api`.** A page without api.if-match in features makes no revision-based write.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R082 -->
- **`api`.** POST with the repeat memory of the owner (unit rows `/<rows>`, `/<sub>/<rows>` — P/06.1) — one key per logical action, not per equal bytes;

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R083 -->
- **`api`.** Automatic and manual replays of the logical action of P/07-R082 keep its key and an immutable snapshot of the original serialized body, even after the caller changes its object or nested values.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R084 -->
- **`api`.** A new call — a new key.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R085 -->
- **`api`.** Each API attempt has a 20 s timeout through the complete response body, not only headers.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R086 -->
- **`api`.** Network failure, that timeout, 5xx or 409 in flight permit replay only at doors with owner repeat memory as in P/07-R082; the module automatically replays only unit rows.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R087 -->
- **`api`.** The module does not automatically replay calls of the requests door P/06.4 made by the page through api.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R088 -->
- **`api`.** The delay before a replay is the response Retry-After header in seconds; without it, the delays are 2, 3, 5 s.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R089 -->
- **`api`.** After the third replay, the module throws the API refusal.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R090 -->
- **`api`.** 401 → the login window.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R091 -->
- **`api`.** The module does not automatically replay PUT, DELETE or table calls, even when the door has repeat memory (P/06.1 N3 «repeat memory»).

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R092 -->
- **`api`.** When a PUT, DELETE or table call has an unknown outcome, the module reads first.

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R093 -->
- **`api`.** A completed answer closes the action;

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R094, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R094 -->
- **`api`.** a refusal before the memory of the request is handled by the contract of the owner, it is not cached as a success

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R260, P/07-R275, P/07-R294, P/07-R295.

<!-- req: P/07-R095 -->
- **`forms`.** For unitForm and the creation form, a 412 with body.row takes priority and uses the W.rowMoved screen of P/07-R102.

See also: P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R096 -->
- **`forms`.** other refusals 400, 409, 412 with the field field of the body (JSON Pointer, P/06.1 N2 «Refusal: error and field») the module shows at the field: the first token of the pointer, parsed by RFC 6901 (~1 → /, ~0 → ~), is the name of a form element;

See also: P/07-R095, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R097 -->
- **`forms`.** the control gets aria-invalid="true", next to it an element .pc-field-err with the text of the refusal (detail, no detail — error), the control gets the focus.

See also: P/07-R095, P/07-R096, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R098 -->
- **`forms`.** If a refusal has no field, or its first JSON Pointer token names no form element, show the refusal text in the common .pc-err.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R099 -->
- **`forms`.** A new form submission removes the field-refusal marks.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R100 -->
- **`forms`.** The code does not parse the refusal: the word and field come as fields of the body.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R101 -->
- **`forms`.** The unit form (unitForm) sends PUT and DELETE with ifMatch — the revision of the shown row, always: otherwise an edit would overwrite someone else's silently.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R102 -->
- **`forms`.** A refusal 412 with body.row — a screen instead of the text: in .pc-err the words W.rowMoved, next to it .pc-moved — the values of the form fields from body.row that differ from the input and the button .pc-reread.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R103 -->
- **`forms`.** A refusal without body.row follows the field/common-error rules P/07-R096, P/07-R097 and P/07-R098.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R104 -->
- **`forms`.** The W.rowMoved screen retains the human's input; the module does not erase it.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R105, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R105 -->
- **`forms`.** The .pc-reread button rereads rows and draws the form anew, resetting the input.

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R281, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R106 -->
- **`writes_via`.** a unit of a subsystem whose manifest (view P/02.2) carries unit.writes_via — the module offers neither a creation form nor «save» and «delete» in unitForm: the fields are read-only;

See also: P/07-R107, P/07-R108, P/07-R109, P/07-R285.

<!-- req: P/07-R107 -->
- **`writes_via`.** a table with the word `tables.<t>.writes_via` — without a write form of a row.

See also: P/07-R106, P/07-R108, P/07-R109, P/07-R285.

<!-- req: P/07-R108 -->
- **`writes_via`.** A human's session would get 403 writes via always (P/06.1 N1.1a);

See also: P/07-R106, P/07-R107, P/07-R109, P/07-R285.

<!-- req: P/07-R109 -->
- **`writes_via`.** Requests (P/06.4) and other page actions keep their existing owning contracts when writes_via suppresses forms.

See also: P/07-R106, P/07-R107, P/07-R108, P/07-R285.

<!-- req: P/07-R110 -->
- **`may`.** console.may(cap, ref, sub?) → bool by the grants of the session and the scope rule P/06.3 N1.3 (* | `unit:<sub>/<id>` | `labels:<…>` | `folder:<id>`; a grant on the unit or on its about unit; the rank of cap — none < view < edit < admin, the right contract common/contracts/may.md);

See also: P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R111 -->
- **`may`.** An omitted sub argument of console.may is null: a row of any sub fits.

See also: P/07-R110, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R112 -->
- **`may`.** the elements of grants with role are role groups, counted by the tiers of the right contract («The level of a role group»), without role — a direct group;

See also: P/07-R110, P/07-R111, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R113 -->
- **`may`.** the folder chains of the unit and of its about the module gathers by a reverse walk of the member lists from GET /folders;

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R114 -->
- **`may`.** If the folder chains of P/07-R113 cannot be gathered, their input is unknown rather than empty: a group with such input gives no level, and a direct group's folder: row does not cover it.

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R115 -->
- **`may`.** admin: true of the session (step 4a) — true, the module hides nothing by it;

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R116 -->
- **`may`.** via: break-glass (grants []) — true, as the server for an emergency session (the right contract common/contracts/may.md step 1, glass → allow);

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R117 -->
- **`may`.** true without grants only with open: true;

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R118 -->
- **`may`.** in a closed or unknown (/session did not answer) session the absence of grants — false;

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R119, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R119 -->
- **`may`.** The server checks every request independently of console.may.

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R165, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R120 -->
- **`events`.** The event roster is on("select", (ref, obj)), on("refresh", {units, servers, domain}), on("logout"), on("card.closed", {ref}) and on("session", {user}).

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R121 -->
- **`events`.** Emit session {user} on every /session read with a known user: on mounting, including without login through the module window, and after ordinary or emergency login.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R122 -->
- **`events`.** A session-event subscription after the /session read receives the last known user immediately.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R123 -->
- **`events`.** An unknown user produces no session event.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R124 -->
- **`events`.** another user — the page resets its own: the secrets of the former one do not go into the write of the new one.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R125 -->
- **`events`.** card.closed — the card was removed: a choice of another object, the removal of the choice (a change of section, a deletion), leaving the page;

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R126 -->
- **`events`.** For card.closed of a shell card, ref is that card's original name, for example streamaccounts:local or netvols.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R127 -->
- **`events`.** Polling that repaints the same selection emits no card.closed.

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R209, P/07-R210, P/07-R274, P/07-R278, P/07-R279.

<!-- req: P/07-R128 -->
- **`where`.** where(ref) → {worker, server, door: {url, token, expires, routes} | null, reason}.

See also: P/07-R129, P/07-R130, P/07-R277.

<!-- req: P/07-R129 -->
- **`where`.** The library turns the absent field door of the HTTP answer into null for the shell;

See also: P/07-R128, P/07-R130, P/07-R277.

<!-- req: P/07-R130 -->
- **`where`.** HTTP Where stays in the form of P/06.5 (the contract of lesson 6)

See also: P/07-R128, P/07-R129, P/07-R277.

<!-- req: P/07-R131 -->
- **`words`.** display(name), manifest(name), kindWord(e), eventNote(e), addEventNote;

See also: P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R299, P/07-R300.

<!-- req: P/07-R132 -->
- **`words`.** W — the dictionary of the module ru | en.

See also: P/07-R131, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R299, P/07-R300.

<!-- req: P/07-R133 -->
- **`words`.** A kind in the closed W.kinds roster uses W, even when a manifest display.kinds collides with it;

See also: P/07-R131, P/07-R132, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R299, P/07-R300.

<!-- req: P/07-R134 -->
- **`words`.** Only event kinds outside the closed W.kinds roster of P/07-R133 use display of the event subsystem.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R299, P/07-R300.

<!-- req: P/07-R135 -->
- **`adds`.** addSection accepts {id, label, icon, after, off, render}.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R136 -->
- **`adds`.** addTab(kind, {id, label, render, busy}) accepts kind ∈ unit | server | worker | member | domain.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R137 -->
- **`adds`.** addTreeNodes(kind | servers | server, fn) returns nodes {ref, label, icon, count, kids, badge, tags, dot, title, off, open, after, replaces}.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R138 -->
- **`adds`.** repaintTree() rebuilds the tree from those nodes when the page's nodes changed but the module's data did not: as in polling, it preserves scroll and waits for release of a pressed button (feature tree.repaint).

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R139 -->
- **`adds`.** The remaining extension call roster is addCard(prefix, render), addMenu, addDecor{icon, badge, title}, addFieldEditor(kind, field, render(host, ref, obj, value, set)), addBlock(kind, {id, covers, render}), addAction, addNote, addIcons, icon, unitForm(host, ref), dialog(title, fields, ok), confirm, toast, select(ref, {tab?}), selected, refresh, logout, fullScreen, isFav and toggleFav.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R140 -->
- **`adds`.** dialog(title, fields, ok) — a promise (Promise): on pressing ok — the values of the fields `{<name>: <value>}`, cancel — null;

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R141 -->
- **`adds`.** The ok argument of dialog is the button caption.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R142 -->
- **`adds`.** confirm(q, more) — at once the human's answer true | false (a value, not a promise) to the question q with the explanation more.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R143 -->
- **`adds`.** addBlock(kind) — kind ∈ server, member, domain;

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R144, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R144 -->
- **`adds`.** addTreeNodes(kind) — kind ∈ unit (nodes under a unit), servers, server, member, access (what the module already gives).

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R145, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R145 -->
- **`adds`.** select(ref, {tab}) — select an object (a unit or a card of the shell) and open the tab by the id given to addTab ("general" — the card of the module);

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R146, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R146 -->
- **`adds`.** If select(ref, {tab}) names no existing tab, the card opens without changing the tab.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R278.

<!-- req: P/07-R147 -->
- **`tree`.** display.tree.folders: true — the tree of the section is built from GET /folders: a node `folder:<id>` per live folder, the parent — parent, the children — subfolders, then the members of this subsystem in the order of members;

See also: P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R148 -->
- **`tree`.** the name of the folder — name;

See also: P/07-R147, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R149 -->
- **`tree`.** an empty folder — a node with zero units, not a filter in the browser;

See also: P/07-R147, P/07-R148, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R150 -->
- **`tree`.** a unit outside folders — a special node, as «no group»;

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R151 -->
- **`tree`.** a member of another subsystem or a unit that the module does not see gives no node;

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R152 -->
- **`tree`.** a rename — one write PUT `/folders/<id>` {name}, with If-Match containing the quoted store index (P/06.8 N2), not the integer api.opts.ifMatch of a page call;

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R153 -->
- **`tree`.** create a folder and a subfolder — POST /folders;

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R154, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R154 -->
- **`tree`.** add and remove a unit — PUT `/folders/<id>` {members}, the member list whole, the order as before, a new unit at the end, with the same quoted-index If-Match;

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R155, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R155 -->
- **`tree`.** Folder-button rights use may(admin, …), as other writes do.

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R156, P/07-R157, P/07-R283.

<!-- req: P/07-R156 -->
- **`tree`.** A server refusal of a folder write follows the common door refusal handling (P/06.8 N3 «folder rights»).

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R157, P/07-R283.

<!-- req: P/07-R157 -->
- **`tree`.** without display.tree.folders — the tree by group_by, as before

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R283.

<!-- req: P/07-R158 -->
- **`return`.** after a login through the module window (password or emergency login) the module reads the parameter return of the page address: a value exactly `/<sub>/`, where `<sub>` is a subsystem of the catalogue of this console (the root and /mounts), — location.replace to it;

See also: P/07-R159, P/07-R160, P/07-R161, P/07-R280.

<!-- req: P/07-R159 -->
- **`return`.** Without a return parameter after login, the page stays.

See also: P/07-R158, P/07-R160, P/07-R161, P/07-R280.

<!-- req: P/07-R160 -->
- **`return`.** Any return value other than exactly `/<sub>/` for a catalogue subsystem redirects with location.replace to /: an absolute address, //…, a .. segment or its percent form (the parameter is already decoded), a subsystem outside the catalogue, a missing final /, a tail or a repeated parameter.

See also: P/07-R158, P/07-R159, P/07-R161, P/07-R280.

<!-- req: P/07-R161 -->
- **`return`.** The value comes by a link, so the exact comparison protects from an open redirect (P/06.5 N2 «Login at the shell»)

See also: P/07-R158, P/07-R159, P/07-R160, P/07-R280.

<!-- req: P/07-R162 -->
- **`cards`.** the markup of a card: `<h1>`, nav.pc-tabs, `<h2>` → .card, button.pc-hdbtn, span.pc-crumbs[data-crumbs], p.pc-hdsub

See also: P/07-R278.

<!-- req: P/07-R163 -->
- **`commands`.** the kind command / command.failed — the word and the note of the module (action · outcome · answer · «by: by»; late → «late»);

See also: P/07-R164, P/07-R278.

<!-- req: P/07-R164 -->
- **`commands`.** the fields of the event outcome, action, by, late, error, reply are written by the worker base (P/03.6 N3 «holder's look»)

See also: P/07-R163, P/07-R278.

<!-- req: P/07-R165 -->
- The session, the grants and the login by which `may` judges — [P/06.3](../../06-console/spec/06.3-console.norms.md) (the gate, `/session`); the server checks every request regardless of `may`.

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R166, P/07-R276, P/07-R292.

<!-- req: P/07-R166 -->
- The words `display` — P/06.5 N1.2.

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R276, P/07-R292.

<!-- req: P/07-R167 -->
- **Cluster refresh.** A cluster load emits the existing `refresh {units, servers, domain}` only when its own root `/servers` read is confirmed.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R168 -->
- `servers` is exactly that read's root `d.servers` map, not the entire Servers document, its policy or merged profiles.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R169 -->
- A failed root read skips only this cluster emission: ordinary reads, local repaint and the next poll still continue.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R170 -->
- Previous data and the initial `{}` are not fresh observations.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R171 -->
- A confirmed empty map, an unchanged map and the first same-map recovery after failure each produce the ordinary event; there is no change-only mode or catch-up replay.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R172 -->
- This exception does not change holder-only `refresh {domain}`, access `refresh {access}`, select, logout, card.closed, session or `pc.ready`.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R173 -->
- The session-read, last-user replay and different-user secret-reset rules P/07-R121, P/07-R122, P/07-R123 and P/07-R124 remain unchanged by the cluster-refresh exception.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R174 -->
- While the root read is unconfirmed, a subscriber also misses the other data of that cluster poll through this event; absence of the event is not a periodic health signal.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R175, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R175 -->
- Local last-known/error state introduces no public error, field, value type or event.

See also: P/07-R045, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R176, P/07-R177, P/07-R209, P/07-R210, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R278, P/07-R279.

<!-- req: P/07-R176 -->
- A failed domain continuation uses the existing `domain: null` error carrier rather than a successful partial prefix.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R177 -->
- Normal `200` values of P/10 `complete`, `unread` and other declared incomplete observations retain their owner meanings; this frequency exception does not reclassify them automatically as transport errors or turn `complete` into a client traversal flag.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R178 -->
- **UI language, caption source and display dates.** The one editable source of platform captions is [data/localization.tsv](../data/localization.tsv), with the existing `key`, `en`, `ru` columns.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R179 -->
- The published module's existing `WORDS` dictionaries are a deterministic materialization of that table, not a second editable vocabulary.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R180 -->
- A key without a namespace selects `WORDS[language][key]`; `n.<name>` selects `WORDS[language].n[<name>]`; `kinds.<event-kind>` selects `WORDS[language].kinds[<event-kind>]`, keeping the entire event-kind suffix literal, including its dots.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R181 -->
- Thus `n.late` and `kinds.server.decommission_requested` retain their existing two different bindings; an arbitrary recursive dot split is not used.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R182 -->
- The materialized Russian strings use JSON-compatible JavaScript Unicode escapes and have exactly the table's string values after ordinary JavaScript parsing.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R183 -->
- No additional runtime decoder or vocabulary alias is introduced.

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R300, P/07-R301.

<!-- req: P/07-R184 -->
- For each `mount(root, opts)` instance, the selected UI language is Russian only when `opts.lang === "ru"`; otherwise it is English, including when `lang` is omitted.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R185 -->
- The browser language does not select the module's language.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R186 -->
- Caption materialization is present in the same synchronously served `/platform/console.js?v=1`: mounting, selecting Russian and rendering a caption require no locale-table fetch, new route, query parameter, storage key, version or public call.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R187 -->
- The language of one mounted instance does not change another instance.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R188 -->
- Subject captions and all protocol/data values remain as supplied by their owning contracts.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R189 -->
- The module's UI timestamp/date renderings use an explicit locale of `ru-RU` for that instance's Russian UI and `en-US` for its English UI.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R190 -->
- This includes the existing full timestamp rendering and the day/month/short-time rendering, without making their private helper names public API.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R191, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R191 -->
- Full timestamp rendering keeps its existing format options; day/month/short-time rendering keeps `day: "2-digit"`, `month: "2-digit"`, `hour: "2-digit"`, `minute: "2-digit"`, `hour12: false`.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R192, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R192 -->
- Locale selection does not add a `timeZone` override or change the existing time zone, seconds-to-milliseconds conversion, precision, absent-value/dash handling, input parsing, or serialization.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R193, P/07-R300, P/07-R301.

<!-- req: P/07-R193 -->
- Protocol timestamps, deadlines, durations, request bodies, responses and stored values are not translated or reformatted by this UI rule.

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R300, P/07-R301.

### N1.6 The domain section — the late layer: introduced by lessons 8 and 10 (without separate readiness ids)

<!-- req: P/07-R194 -->
- The current `pending` view is a member-keyed count (`integer >= 0`) or `null` for an unreadable member row; it is not a list of edit descriptions.

See also: P/07-R195, P/07-R260.

<!-- req: P/07-R195 -->
- Counts and the separate `outcomes` arrays are displayed independently, including zero and unknown counts.

See also: P/07-R194, P/07-R260.

<!-- req: P/07-R196 -->
- Both domain loaders follow the opaque cursor of `GET /domain` under P/10-R004.

See also: P/07-R176, P/07-R177, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R197 -->
- The assembled view preserves all six per-member projections, required empty subsystem keys, complete contested claimant lists and global fields.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R198 -->
- Repeated conflict context is one conflict fact, not another member or another copy of the fact.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R199 -->
- Ordinary paginated reads promise no snapshot across changes; a failed continuation is not a complete successful read.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R200 -->
- The parts of N1.4 and N1.5 that the domain introduces are parts of P/07-01 and P/07-02 without separate readiness ids (as P/02.1 N1.2b).

See also: P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R201 -->
- The doors that the domain console gives to the page — [lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) (the holder page — P/10-04); the forwarding to them, `/api/held` and `/domain/shared/<sub>` at the cluster console — [chapter P/06.7](../../06-console/spec/06.7-console.norms.md).

See also: P/07-R200, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R202 -->
- **`reads`.** /domain/* (forwarding contract «Domain doors»; the cluster console forwards them to the domain console — P/06.7-02…05), /api/held (P/06.7-14; the term record and the backup pair — P/08.8), `/domain/shared/<sub>` (P/06.7-15)

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R200, P/07-R201, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R271, P/07-R286.

<!-- req: P/07-R203 -->
- **`writes`.** /domain/* (forwarding contract «Domain doors»);

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R200, P/07-R201, P/07-R202, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R271, P/07-R286.

<!-- req: P/07-R204 -->
- **`writes`.** login_url — POST {user, password} to the address login_url from /session: the domain door POST /api/login (P/08.4 N1.2; login_url — the gate and pass contract «The gate»; the cluster console forwards it to the domain — «Domain doors»)

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R271, P/07-R286.

<!-- req: P/07-R205 -->
- **`order`.** `/domain/shared/<sub>`, /domain (+ /domain/alarms — P/10-06), /api/held

See also: P/07-R009, P/07-R010, P/07-R011, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R271, P/07-R272, P/07-R273, P/07-R278, P/07-R279, P/07-R286.

<!-- req: P/07-R206 -->
- **`never`.** /api/backup (P/06.7-16)

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R031, P/07-R032, P/07-R033, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R271, P/07-R286.

<!-- req: P/07-R207 -->
- **`objects`.** The domain layer uses the object-reference roster of P/07-R068.

See also: P/07-R068, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R278, P/07-R286.

<!-- req: P/07-R208 -->
- **`objects`.** The references `member:<m>`, domain and `person:<name>` of P/07-R068 are introduced by lessons 8 and 10.

See also: P/07-R068, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R278, P/07-R286.

<!-- req: P/07-R209 -->
- **`events`.** the field domain of refresh;

See also: P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R278, P/07-R279, P/07-R286.

<!-- req: P/07-R210 -->
- **`events`.** the section access, having read its doors, emits refresh {access}

See also: P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R278, P/07-R279, P/07-R286.

<!-- req: P/07-R211 -->
- **`adds`.** the kinds member, domain of addTab;

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R260, P/07-R278, P/07-R286.

<!-- req: P/07-R212 -->
- **`adds`.** addBlock — member, domain;

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R260, P/07-R278, P/07-R286.

<!-- req: P/07-R213 -->
- **`adds`.** The late-layer addTreeNodes kinds are member and access, as in P/07-R144.

See also: P/07-R054, P/07-R055, P/07-R056, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R260, P/07-R278, P/07-R286.

<!-- req: P/07-R214 -->
- **`sections`.** opts.sections defaults to [units, access, journal] (P/06.5 N1.1 opts); its access section belongs to the late layer and is defined in P/07-R221.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R215 -->
- **`sections`.** [domain] — the holder page (P/10-04)

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R216 -->
- **`domain`.** domain is the root of the units panel's «By servers» layout rather than a strip section: it shows the holder location (GET /api/held), members, keys, topology, the move action, alarms and keys-view.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R217 -->
- **`domain`.** «Move the domain here» opens a dialog with the recovery file as text and the no/yes choice «the old holder was stolen», submitting POST /domain/move {recovery[, stolen: true]}.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R218 -->
- **`domain`.** Without a recovery file, the domain-move request is not sent.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R219 -->
- **`domain`.** The domain alarm card has one row per kind and of: the last alarm, «×N (since …)» and the member list.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R220 -->
- **`domain`.** the domain card carries the term and the handover, «apply again», the units by subsystems, the shared settings by declared and the edits for clusters (pending and outcomes)

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R221 -->
- **`access`.** people, grants, break-glass — /domain/users, /domain/grants, /domain/break-glass (forwarding contract «Domain doors»)

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R222 -->
- **`held`.** GET /api/held — the only door of the processes that the module reads: the signed public record of the holder {cluster, holder, term, keys, backup: {term, rev}} at the cluster console;

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R223 -->
- **`held`.** backup — a pointer to the last copy at this member, comparable only by the pair {term, rev};

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R224 -->
- **`held`.** At a member, show «an old copy» when its backup pair is strictly behind the holder pair term.backup of GET /domain (P/08.8 N1.3).

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R225 -->
- **`held`.** At a member, show «the holder no longer updates it» when that member is absent from term.backup_holders of the same GET /domain view.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R226 -->
- **`held`.** Compare pairs by term first, then rev at equal term (P/08.8, the largest (term, rev));

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R227 -->
- **`held`.** A backup pair lags behind another only when it is strictly smaller under the ordering of P/07-R226.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R228 -->
- **`held`.** Preserve exact number representations when comparing and displaying the held backup record.

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R229 -->
- **`holder`.** with sections: [domain] the module learns the holder mode from the sections of the page: it does not load the units, /servers and /unplaceable, it takes the units by subsystems from the view /domain;

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R230, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R230 -->
- **`holder`.** /servers, /drain, /schema, /unplaceable, /metrics, /events are not needed at the holder — the module survives their absence

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R231, P/07-R232, P/07-R233, P/07-R286.

<!-- req: P/07-R231 -->
- **`schema`.** GET /domain/shared → {doc, delivery, declared: `{<sub>:` [{name, type, schema?}]}} (P/10-14): the declared fields from domain.shared of the manifests and their types;

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R238, P/07-R239, P/07-R286.

<!-- req: P/07-R232 -->
- **`schema`.** for a document {name, type: json} — also its schema, by it the page builds a form;

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R238, P/07-R239, P/07-R286.

<!-- req: P/07-R233 -->
- **`schema`.** an edit — PUT /domain/shared `{base_rev, shared: {<sub>: {<field>: value | null}}}`

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R238, P/07-R239, P/07-R286.

<!-- req: P/07-R234 -->
- In a schema-based form, an object uses properties with required fields marked; a list uses items with adding/removing elements; string, number, integer, yes/no and enum use their own controls.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R235, P/07-R236, P/07-R237, P/07-R238, P/07-R239.

<!-- req: P/07-R235 -->
- An unexpressible schema form value uses JSON text in its place: an object without properties, a type union or a value with keys outside the schema.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R236, P/07-R237, P/07-R238, P/07-R239.

<!-- req: P/07-R236 -->
- Empty schema-form fields are omitted from submission.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R237, P/07-R238, P/07-R239.

<!-- req: P/07-R237 -->
- An empty schema-form document is submitted as null.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R238, P/07-R239.

<!-- req: P/07-R238 -->
- The domain checks the schema on PUT; «Implementation decides» item 2 is closed.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R239.

<!-- req: P/07-R239 -->
- The holder page (`/`, CSP, `/manifest`, `/mounts`, `/session`) is served by lesson P/10 (P/10-04): implementations serve the bytes of the module as they are; what the module calls in the mode `domain` is a property of the published module, not of the implementations.

See also: P/07-R231, P/07-R232, P/07-R233, P/07-R234, P/07-R235, P/07-R236, P/07-R237, P/07-R238.

<!-- req: P/07-R240 -->
- Both domain loaders collect the existing optional reader field `unread` by [P/10 N1.2a](../../10-domain-console/spec/10-domain-console.norms.md) and its `ServedView.unread` type in the [P/08 owner OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml).

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R241 -->
- All pages absent means absent; any supplied value keeps the field, including an empty result.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R242 -->
- Union the literal Part strings without duplicates in first-observation and in-page order; a later absent or empty value never erases earlier parts.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R243 -->
- No parsing, trimming, padding, sorting or normalization is performed.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R244 -->
- This does not change individual response constraints or infer completeness from absence.

See also: P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R245 -->
- Keep the first head's globals, the six projections, complete contested lists, required empty subsystem keys, opaque continuation and visibility unchanged.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R246, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R246 -->
- A valid `200` with a normal incomplete `complete`/`unread` state remains an ordinary observation with its owner values, not a transport error.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R247, P/07-R248, P/07-R260.

<!-- req: P/07-R247 -->
- The module may show the observed normal incompleteness privately; it adds no public event/field or client completeness flag and promises no snapshot.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R248, P/07-R260.

<!-- req: P/07-R248 -->
- A real failed continuation still uses the existing `domain: null` path and private last-known/error state; the root-confirmation rule of cluster refresh stays unchanged.

See also: P/07-R045, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R176, P/07-R177, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R260.

---

## N2 The library contract

<!-- req: P/07-R249 -->
- The module is a library of the platform in the browser, one code in all implementations: the lesson has no process, door or HTTP contract of its own.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R250 -->
- The library contract is two norms of N1: what the module calls (N1.4) and what it gives the shell (N1.5); the late layer — N1.6.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R251 -->
- The doors that the module calls, their codes and forms — the chapters of lesson 6 and the [contract of lesson 6](../../06-console/spec/06-console.api.openapi.yaml); the publication of the module byte for byte, the version `?v=` and the page are normed by [chapter 6.5](../../06-console/spec/06.5-console.norms.md) N1.1.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R252 -->
- The calls of N1.5 are the shell addressing the library inside its own page, not the platform calling a subsystem: they are not hooks; the bytes of the stream and of the archive the shell takes from the holder by `door` from `where()`, past the console.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R253, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R253 -->
- The description of the public surface of the module (the dictionary `W`, the card markup, the calls of the shell, the look) — [`CONSOLE-MODULE.md`](../CONSOLE-MODULE.md) (not a norm).

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R254, P/07-R255, P/07-R256, P/07-R257.

<!-- req: P/07-R254 -->
- Where the description or the published bytes differ from N1.4, N1.5, the lesson is right; the discrepancies «Implementation decides» items 1 and 2 are closed.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R255, P/07-R256, P/07-R257.

---

## N3 Procedures

<!-- req: P/07-R255 -->
- The lesson has no procedures of its own: the order of load and polling — P/07-R009…P/07-R011; the replay of a call — P/07-R082…P/07-R094.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R256, P/07-R257.

<!-- req: P/07-R256 -->
- The procedures of the doors that the module calls — N3 of the chapters of lesson 6.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R257.

---

## N4 Refusals

<!-- req: P/07-R257 -->
- The lesson has no rows of N4 of its own: the refusals of the doors that the module calls — N4 of the chapters of lesson 6 (a wrong version of the module — 404 `no such version`, [P/06.5](../../06-console/spec/06.5-console.norms.md) N4); what the module does with a refusal — N1.5 `api` (401 — the login window; a replay — only by the rules of the owner of the repeat memory; an unknown outcome of `PUT` and of tables — a read first); a refusal with `field` — N1.5 `forms`.

See also: P/07-R001, P/07-R002, P/07-R003, P/07-R004, P/07-R005, P/07-R249, P/07-R250, P/07-R251, P/07-R252, P/07-R253, P/07-R254, P/07-R255, P/07-R256.

---

## N5 Acceptance

<!-- req: P/07-R258 -->
- The checks of N5 read the current canonical P/07 module files.

See also: P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R259 -->
- Declare fixture origins separately: a frozen wrapper is not the canonical module; an instrumented navigation return and a substituted shell-short module are not unchanged-module executions.

See also: P/07-R258, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R260 -->
- Check path/query neighbours, safe-integer edges, lossless list edits, scoped worker identities, current pending counts, both paginated loaders and disabled-section input.

See also: P/07-R034, P/07-R035, P/07-R036, P/07-R037, P/07-R038, P/07-R039, P/07-R040, P/07-R041, P/07-R042, P/07-R043, P/07-R044, P/07-R045, P/07-R046, P/07-R047, P/07-R048, P/07-R049, P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R054, P/07-R055, P/07-R056, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R176, P/07-R177, P/07-R194, P/07-R195, P/07-R196, P/07-R197, P/07-R198, P/07-R199, P/07-R211, P/07-R212, P/07-R213, P/07-R240, P/07-R241, P/07-R242, P/07-R243, P/07-R244, P/07-R245, P/07-R246, P/07-R247, P/07-R248, P/07-R258, P/07-R259, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R275, P/07-R278, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R294, P/07-R295, P/07-R297, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R261 -->
- J-P07-01 is a separate holder-fixture scope on the same corrected candidate.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R262 -->
- No old positive array, error, incomplete output, or aggregate test count closes the existing open debts: `v1showsHidden`, the open tests of N5, P/07-07 and P/07-08.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R263 -->
- The lesson has no acceptance catalogue (the exception `P/07 no-acceptance`): the module is a library in the browser, the HTTP-TSV stand does not run it.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R264 -->
- The publication of the module byte for byte with the published files and the version `?v=1` (`?v=2` — 404) — sc. 01 (judge-only: checks P/07-R266) of the [acceptance of chapter 6.5](../../06-console/acceptance/5/README.md) (P/06.5 N1.1).

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R265 -->
- The subjects of N1.4 and N1.5 are checked by the jsdom tests of the owner of the specification `Source/tests/console` (judge-only: owner tests under P/07-R265): a test mounts the published module on a page in jsdom and intercepts its requests; the module is one for all implementations and the evidence is one for all.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R266 -->
- For a generation line, P/07 is packaging: the published files are taken unchanged and checked byte for byte together with scenario 01 (judge-only: checks P/07-R266) of acceptance 6.5, including `?v=1`.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R267 -->
- The line does not rewrite JavaScript and gets no separate executable module profile.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R268 -->
- The three tests `module-unplaceable-all`, `module-subsystems-none` and `module-writes-via`, and readiness items P/07-07 and P/07-08, remain an explicit debt of the owner of the published module bytes (the course canon, changed through Specification branches).

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R269 -->
- They are neither PASS nor FAIL of the generation line until the owner closes the debt.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R270 -->
- The behavioural rules of N1.4 and N1.5 remain in force.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R271 -->
- **N1.4 `reads`, `writes`, `never` — not a single call outside the list; the module does not call the doors of the holders.** TSV talks to the doors, it does not see the calls of the page. jsdom test (judge-only: owner tests under P/07-R265) `module-calls`: every intercepted request of the module (method and path) on mounting, polling, selection and edits is compared with `reads`/`writes`, the paths of `never` and the door from `where()` are not called; the mode `domain` — the same test

See also: P/07-R006, P/07-R007, P/07-R008, P/07-R009, P/07-R010, P/07-R011, P/07-R031, P/07-R032, P/07-R033, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R272, P/07-R273, P/07-R278, P/07-R279.

<!-- req: P/07-R272 -->
- **N1.4 `order`, polling every `poll_s`, `/events?unit=` of the selected one — every 5 s.** the doors do not show the order of load. jsdom test (judge-only: owner tests under P/07-R265) `module-calls`: the order on mounting and on every poll, polling every `poll_s` of the page, `/events?unit=` of the selected one — after 5 s

See also: P/07-R009, P/07-R010, P/07-R011, P/07-R205, P/07-R271, P/07-R273, P/07-R278, P/07-R279.

<!-- req: P/07-R273 -->
- **N1.4 `changes` — the number before the rows, a load on a message and on a reset, 404 removes the feed.** TSV does not run the page. jsdom test (judge-only: owner tests under P/07-R265) `module-changes`: the order on mounting, `after` and `wait`, a message about its own subsystem and a reset — a load, a foreign subsystem and an empty answer — none, 404 — one request, polling lives

See also: P/07-R009, P/07-R010, P/07-R011, P/07-R019, P/07-R020, P/07-R021, P/07-R022, P/07-R023, P/07-R024, P/07-R025, P/07-R026, P/07-R027, P/07-R028, P/07-R029, P/07-R030, P/07-R205, P/07-R271, P/07-R272, P/07-R278, P/07-R279.

<!-- req: P/07-R274 -->
- **N1.5 `version` — an integer, the shell compares it before use.** the version in `?v=` is checked by the door, and the comparison is done by the page. jsdom test (judge-only: owner tests under P/07-R265) `platform-page`: `console.html` compares `version` before `mount`, a module of another version is not mounted; the door `?v=` — sc. 01 (judge-only: checks P/07-R266) of acceptance 6.5

See also: P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R279.

<!-- req: P/07-R275 -->
- **N1.5 `api` — a key of a logical action, a replay by the rules of the owner, `PUT` and tables without an automatic replay, 401 — the login window.** TSV does not create a replay after a lost answer. jsdom test (judge-only: owner tests under P/07-R265) `module-retry` (and `module-session`: «Retry» with the same key): a new key per call, a replay only of `POST /<rows>`, `/<sub>/<rows>` with the same key and body, `Retry-After`, after the third replay — a refusal with `status`, `body`, `retry`; `PUT`, `DELETE`, `POST /marks`, `/drain`, the decommission of a server — without a replay, a read first; `POST`, `PUT`, `DELETE` of the tables of the root (`/testsub/<table>`) and of a mounted (`/<sub>/<table>`) subsystem — without a replay on a dropped connection and 5xx, a refusal without `retry`; 401 — the login window

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R294, P/07-R295.

<!-- req: P/07-R276 -->
- **N1.5 `may` — by the grants of the session; without grants `true` only with `open: true`.** the grants are issued by the domain, the scenarios of lesson 6 run without the domain. jsdom test (judge-only: owner tests under P/07-R265) `module-may`: rank and scope (`*`, `unit:` with an about unit, `labels:` at the about unit or at the unit itself), outside a unit, `via: break-glass`, an open, a closed and an unknown session; the server always checks — P/06.3

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R292.

<!-- req: P/07-R277 -->
- **N1.5 `where` — `door` or `null` when the HTTP answer has no field `door`.** the conversion is done by the library, not by the door. jsdom test (judge-only: owner tests under P/07-R265) `module-contract`: `door` — the object `Door` of the answer, without the field `door` — `null`; HTTP `Where` without `door` — sc. 04 (judge-only: checks P/07-R130) of acceptance 6.5

See also: P/07-R128, P/07-R129, P/07-R130.

<!-- req: P/07-R278 -->
- **N1.5 `objects`, `events`, `words`, `adds`, `cards`, `commands`; without hooks and a foreign DOM.** the subject is the behaviour of the page, not the doors. a jsdom test (judge-only: owner tests under P/07-R265) of the module and the shell, and reading; `objects` (`worker:<sub>/<w>`) — `module-contract`, `module-servers`, `module-calls`; `events` (`logout`) — `module-session`; `events` `refresh {units, servers, domain}` and `refresh {access}` — `module-refresh-event`; `adds` `addTreeNodes` of five kinds and the fields of a node — `module-tree-nodes`, `addNote`, `addIcons`, `fullScreen`, `isFav`/`toggleFav` — `module-page-adds`; `words` (ru and en of the same keys, the words of all event kinds; `display(name)` — the words of the manifest, for an unknown subsystem — empty; `eventNote` of the page after `addEventNote` — in the journal and on the events tab of the card, an event of the platform — in the words of the module) — `module-words`; `addSection` (`after`, `off` with a reason), `addTab` of four kinds with `select(ref, {tab})`, `busy()` — polling does not repaint, `addBlock` of a member and of the domain after its own blocks, `addAction` (`fn(ref, obj)` → the buttons of the header before the star), `dialog` (a promise of values, cancel — `null`), `confirm(q, more)` — the human's answer — `module-page-adds`; `cards` (the header, the crumbs, the tabs, the buttons; `<h2>` → `.card` — first in `.box` («Implementation decides» item 3, closed)) — `module-card-markup`; without accesses to the DOM of the frame — by reading

See also: P/07-R009, P/07-R010, P/07-R011, P/07-R054, P/07-R055, P/07-R056, P/07-R068, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R135, P/07-R136, P/07-R137, P/07-R138, P/07-R139, P/07-R140, P/07-R141, P/07-R142, P/07-R143, P/07-R144, P/07-R145, P/07-R146, P/07-R162, P/07-R163, P/07-R164, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R205, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R260, P/07-R271, P/07-R272, P/07-R273, P/07-R279.

<!-- req: P/07-R279 -->
- **N1.5 `module`, `features`, `ready`, `select(ref, {tab})`, `card.closed`.** the subject is the behaviour of the page. jsdom test (judge-only: owner tests under P/07-R265) `module-page-calls`: `features`, version 1, `pc.ready` after `mount` and the first `/manifest` and after 401 → login, on a dropped connection and 503 of `/manifest` — it waits for the next poll without the login window and without an immediate replay, `select` with a tab, without it, with an unknown one and `general`, `card.closed` on a change of selection, a removal of selection, leaving the page, for a card of the shell, not on polling; the VMS page without accesses to the DOM of the frame (`shell.may_not`) — the tests of the page of the VMS owner and by reading

See also: P/07-R009, P/07-R010, P/07-R011, P/07-R057, P/07-R058, P/07-R059, P/07-R060, P/07-R061, P/07-R062, P/07-R063, P/07-R064, P/07-R065, P/07-R066, P/07-R067, P/07-R120, P/07-R121, P/07-R122, P/07-R123, P/07-R124, P/07-R125, P/07-R126, P/07-R127, P/07-R167, P/07-R168, P/07-R169, P/07-R170, P/07-R171, P/07-R172, P/07-R173, P/07-R174, P/07-R175, P/07-R205, P/07-R209, P/07-R210, P/07-R271, P/07-R272, P/07-R273, P/07-R274, P/07-R278.

<!-- req: P/07-R280 -->
- **N1.5 `return` — the return after a login, protection from an open redirect.** a call of the page, TSV goes to the doors and does not follow a `302`. jsdom test (judge-only: owner tests under P/07-R265) `module-return`: `/<sub>/` of its own catalogue and of the root — a transition; outside the catalogue, absolute, `//evil`, `/%2e%2e/`, with `..`, without the final `/`, with a tail, a repeated parameter — to `/`; without the parameter the page stays

See also: P/07-R158, P/07-R159, P/07-R160, P/07-R161.

<!-- req: P/07-R281 -->
- **N1.5 `forms` — `ifMatch` of the form, the screen of 412.** what the form sent and showed, TSV does not see. jsdom test (judge-only: owner tests under P/07-R265) `module-form-if-match`: PUT and DELETE carry `If-Match`, 412 — `.pc-moved`, the input is intact, `.pc-reread` rereads

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R282, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R282 -->
- **N1.5 `forms` — a refusal at the field by `field`.** what the form did with the refusal, TSV does not see. jsdom test (judge-only: owner tests under P/07-R265) `module-refusal-field`: the control of the field, `.pc-field-err`, the focus, the parsing of `~1`; without `field` and without a form element — the common `.pc-err`

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R293, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R283 -->
- **N1.5 `tree` — the tree by the folders of the cluster.** TSV does not see the calls of the page. jsdom test (judge-only: owner tests under P/07-R265) `module-folders` (not written yet: the module does not do this, a debt of the product): the tree from `/folders`, an empty folder, a rename by one write

See also: P/07-R147, P/07-R148, P/07-R149, P/07-R150, P/07-R151, P/07-R152, P/07-R153, P/07-R154, P/07-R155, P/07-R156, P/07-R157.

<!-- req: P/07-R284 -->
- **N1.4 `subsystems`, `unplaceable`.** TSV does not see the calls of the page; the published canonical module [console.js](../module/console.js) does not execute the rule — an open debt of the owner of the published bytes. the owner of the published module bytes closes this debt with tests of the published canonical module bytes: `module-unplaceable-all` — an unplaced unit of a subsystem outside `opts.subsystems` is visible as a row of the section (subsystem, id, reason) without a card and without actions, `/<sub>/unplaceable` is called for every subsystem of the catalogue; `module-subsystems-none` — `subsystems: []`: not a single `/<rows>`, `/<sub>/<rows>`, the tree is empty, the section of unplaced units reads all subsystems

See also: P/07-R012, P/07-R013, P/07-R014, P/07-R015, P/07-R016, P/07-R017, P/07-R018.

<!-- req: P/07-R285 -->
- **N1.5 `writes_via` — forms without a write.** TSV does not see the calls of the page; the published canonical module [console.js](../module/console.js) does not know the word — an open debt of the owner of the published bytes. the owner of the published module bytes closes this debt with the test of the published canonical module bytes: `module-writes-via` — a unit of a subsystem with `unit.writes_via` has no creation form, `unitForm` has no «save» and «delete», not a single `POST`, `PUT`, `DELETE` of the rows of this subsystem; a subsystem without the word has the forms as before

See also: P/07-R106, P/07-R107, P/07-R108, P/07-R109.

<!-- req: P/07-R286 -->
- **N1.6 the late layer (the mode `domain`, the sections `domain`, `access`, `login_url`, `refresh {access}`).** the stand of lesson 6 has no domain; TSV does not see the calls of the page. the jsdom test of the mode `domain` at the owner of the module (N1.6 `holder`; `Source/tests/console` (judge-only: owner tests under P/07-R265)); the doors of the holder page — the acceptance of [lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) (P/10-04), the doors of people — [the acceptance of chapter P/08.4](../../08-domain/acceptance/4/README.md); the form by `schema` — jsdom test `module-shared-schema`

See also: P/07-R200, P/07-R201, P/07-R202, P/07-R203, P/07-R204, P/07-R205, P/07-R206, P/07-R207, P/07-R208, P/07-R209, P/07-R210, P/07-R211, P/07-R212, P/07-R213, P/07-R214, P/07-R215, P/07-R216, P/07-R217, P/07-R218, P/07-R219, P/07-R220, P/07-R221, P/07-R222, P/07-R223, P/07-R224, P/07-R225, P/07-R226, P/07-R227, P/07-R228, P/07-R229, P/07-R230, P/07-R231, P/07-R232, P/07-R233.

### Criteria and debt of the published module bytes

<!-- req: P/07-R287 -->
- The following criteria refine the existing N1.5 obligations.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R288 -->
- Their owner is the owner of the published common module bytes (the course canon, changed through Specification branches).

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R289, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R289 -->
- The published witness stays unchanged.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R290, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R290 -->
- Each row is an open behavioural/evidence debt of that owner until an actual module test closes it; adding the criterion or copying the published files is not such evidence.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R291, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R291 -->
- Generation lines package the same bytes and do not implement a replacement module.

See also: P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R292 -->
- **`may`, N1.5.** `module-may`: `admin: true` with empty grants; a grant for another `sub`; direct groups and role tiers including a specific `none` over a general `edit`; folder and about-unit folder chains; an unavailable chain remains unknown and grants no level; closed, open, emergency and unknown sessions. Published-byte owner; compare the existing common `may` contract, without changing the server's independent check

See also: P/07-R110, P/07-R111, P/07-R112, P/07-R113, P/07-R114, P/07-R115, P/07-R116, P/07-R117, P/07-R118, P/07-R119, P/07-R165, P/07-R166, P/07-R276.

<!-- req: P/07-R293 -->
- **Every unit-form write, including an immediate boolean switch, N1.5 `forms`.** `module-form-if-match`: the shown revision is sent as `If-Match`; two quick clicks cannot bypass that revision; a concurrent change yields 412, keeps the input and shows the reread screen; an unreadable required revision permits no write. Published-byte owner; a bool switch uses the same CAS/refusal path as the rest of the form

See also: P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R281, P/07-R282, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R294 -->
- **Immutable request snapshot, N1.5 `api`.** `module-retry`: mutate the caller's original object, including a nested value, after the initial call and again before manual Retry; automatic and manual retries retain the original serialized body and the same key. Published-byte owner; a new call still gets a new key even for equal bytes

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R295.

<!-- req: P/07-R295 -->
- **Complete-attempt timeout, N1.5 `api`.** `module-retry`: receive headers, then stall the body beyond 20 s; separately truncate the body. A unit POST retries only under the existing rule, with the same key and immutable body; PUT and table calls report an unknown outcome and reread without an automatic replay. Published-byte owner; receiving headers does not complete an attempt or turn an incomplete body into a successful null answer

See also: P/07-R047, P/07-R048, P/07-R049, P/07-R069, P/07-R070, P/07-R071, P/07-R072, P/07-R073, P/07-R074, P/07-R075, P/07-R076, P/07-R077, P/07-R078, P/07-R079, P/07-R080, P/07-R081, P/07-R082, P/07-R083, P/07-R084, P/07-R085, P/07-R086, P/07-R087, P/07-R088, P/07-R089, P/07-R090, P/07-R091, P/07-R092, P/07-R093, P/07-R094, P/07-R260, P/07-R275, P/07-R294.

<!-- req: P/07-R296 -->
- **Captions as a string or `{key, text}`, N1.5 `words`.** `module-words`: unit and field captions, `field_help`, enum choices and event kinds in both caption forms; resolve the localization key with text as the declared fallback. Published-byte owner; preserve the caption contract of P/06.5 and the existing localization keys

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R299, P/07-R300.

<!-- req: P/07-R297 -->
- **Hidden fields, N1.5 `forms`.** Module form tests: a `hidden: true` field is absent from the ordinary form and from an explicit `display.form`; visible neighbours remain present; omitted or false `hidden` keeps ordinary behaviour. Published-byte owner; open `v1showsHidden` debt

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R260, P/07-R281, P/07-R282, P/07-R293, P/07-R298, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R298 -->
- **Legal external names, N1.5.** `module-words` and form/tree tests: `__proto__`, `constructor`, `toString` as unit identifiers and data names remain visible, selectable and editable according to their rights; no inherited property substitutes for a data entry. Published-byte owner; the existing identifier grammar is not narrowed

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R260, P/07-R297, P/07-R302, P/07-R303, P/07-R304.

<!-- req: P/07-R299 -->
- **Platform-kind priority, N1.5 `words`.** `module-words`: a closed platform event kind uses `W.kinds`; a colliding `display.kinds` in either the current subsystem or another subsystem cannot replace it. Other kinds use the event's subsystem display dictionary. Published-byte owner; the closed platform roster is the existing `kinds.*` roster in the P/07 localization table

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R296, P/07-R300.

<!-- req: P/07-R300 -->
- **One caption source and selected UI language, N1.5.** Existing `module-words` and mount/page tests: materialize twice from the same locale table and compare the generated WORDS bytes; match every key and substitution parameter in both languages, including `n.late` and `kinds.server.decommission_requested`; default and non-`ru` selections use English even in a Russian-language browser, and exact `lang: "ru"` uses Russian in an English-language browser. Russian JS escapes parse once to the table's original strings. No locale fetch or additional locale route/storage/query/version/API is used. Owner of the new canonical module bytes; the old frozen Source bytes and a path-only copy do not prove this rule

See also: P/07-R131, P/07-R132, P/07-R133, P/07-R134, P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R296, P/07-R299, P/07-R301.

<!-- req: P/07-R301 -->
- **UI timestamp/date locale, N1.5.** Existing module/page tests exercise actual rendered timestamps and worker-slot dates with mismatched browser/UI languages and mixed-language mounted instances. Full and short renderings receive explicit `en-US` or `ru-RU` according to their instance; date options, original epoch milliseconds, browser time zone and protocol timestamps/bodies are unchanged. Owner of the new canonical module bytes; inspect observable rendering and request/storage effects, without exporting private format helpers or adding a test-only public API

See also: P/07-R178, P/07-R179, P/07-R180, P/07-R181, P/07-R182, P/07-R183, P/07-R184, P/07-R185, P/07-R186, P/07-R187, P/07-R188, P/07-R189, P/07-R190, P/07-R191, P/07-R192, P/07-R193, P/07-R300.

<!-- req: P/07-R302 -->
- The related P/06 form `FieldView.hidden`: an optional boolean with no default; the required roster and closed shape are unchanged.

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R281, P/07-R282, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R293, P/07-R297, P/07-R298, P/07-R303, P/07-R304.

<!-- req: P/07-R303 -->
- The module omits fields with `hidden: true` from generated forms, including an explicit `display.form`.

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R281, P/07-R282, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R293, P/07-R297, P/07-R298, P/07-R302, P/07-R304.

<!-- req: P/07-R304 -->
- The P/06 form alone does not prove that the published module implements hidden-field omission; the byte-owner debt v1showsHidden remains open until that owner supplies actual module evidence.

See also: P/07-R050, P/07-R051, P/07-R052, P/07-R053, P/07-R095, P/07-R096, P/07-R097, P/07-R098, P/07-R099, P/07-R100, P/07-R101, P/07-R102, P/07-R103, P/07-R104, P/07-R105, P/07-R258, P/07-R259, P/07-R260, P/07-R261, P/07-R262, P/07-R263, P/07-R264, P/07-R265, P/07-R266, P/07-R267, P/07-R268, P/07-R269, P/07-R270, P/07-R281, P/07-R282, P/07-R287, P/07-R288, P/07-R289, P/07-R290, P/07-R291, P/07-R293, P/07-R297, P/07-R298, P/07-R302, P/07-R303.

---

## Implementation decides

The module is one code in all implementations: an implementation does not write it and chooses nothing in it, but serves the published bytes
(P/06.5 N1.1 `module`). The items below are debts of the published module; the owner of the specification closes them; items 1–5 are closed; items 6 and 7 remain open debts of this owner, not a separate module implementation by a generation line:

1. **closed: the bytes of `console.js`, `console.html` and the description `CONSOLE-MODULE.md` are brought to N1.4, N1.5**.
   The evidence — the jsdom tests `Source/tests/console` (judge-only: owner tests under P/07-R265) by the table of N5. The debt
   of the product — to «Build»: its copy of the module is brought to these bytes.
2. **closed: the form of the shared document by `schema`** (N1.6 `schema`).
   The evidence —
   jsdom test (judge-only: owner tests under P/07-R265) `module-shared-schema` (N5). The debt of the product — to «Build».
3. **closed: `<h2>` → `.card`** (N1.5 `cards`).
   The evidence —
   jsdom test (judge-only: owner tests under P/07-R265) `module-card-markup` (N5). The debt of the product — to «Build».
4. **closed: a refusal at the field by `field`** (N1.5 `forms`).
   The evidence — jsdom test (judge-only: owner tests under P/07-R265) `module-refusal-field` (N5). The debt of the product — to «Build».
5. **closed: rows by the feed** (N1.4 `changes`). The evidence — jsdom test (judge-only: owner tests under P/07-R265) `module-changes` (N5). The debt of the product — to «Build».
6. **not closed: the unplaced units of all subsystems and `subsystems: []`** (N1.4) — the published canonical module [console.js](../module/console.js) reads `/<sub>/unplaceable` only for the subsystems of `opts.subsystems`; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; tests — N5 `module-unplaceable-all`, `module-subsystems-none`.
7. **not closed: forms without a write for `writes_via`** (N1.5 `writes_via`) — the published canonical module [console.js](../module/console.js) does not know the word and draws the forms; this is an open debt of the owner of the published common module bytes; the generation line keeps the published bytes unchanged; test — N5 `module-writes-via`.

---

## Readiness checklist

An implementation conforms to the lesson when every norm is met; the norm id `P/07-MM` is what the deltas of decisions,
findings and window records refer to. The implementation here is the published module, one for all (N2).

- [ ] **P/07-01** [test] the closed list of calls of the module N1.4 and the order of load — checked by a jsdom test: the calls of the module and their order — by N1.4 `reads`/`writes`/`never`/`order`; the reason — the module is one for all implementations, the doors do not show the order of load; the place of proof — the jsdom test of the owner of the specification `Source/tests/console/module-calls.test.js` (judge-only: owner tests under P/07-R265) (N5); the parts of the late layer — N1.6 `reads`, `writes` (`login_url`), `order`, `never`, the mode `holder` (`sections: [domain]`)
- [ ] **P/07-02** [test, reading] the shell contract N1.5: `api` with a key of a logical action and replays only by the contract of the owner, `where` with `door`, the calls of the library, without hooks and a foreign DOM — checked by reading: the test of the shell (jsdom; the subject is the behaviour of the page, not the doors); the reason — TSV talks to the doors, it does not run the page; the place of proof — `Source/tests/console` (judge-only: owner tests under P/07-R265) (N5); `api`, `may`, `version`, `where`, `objects`, `events` — jsdom tests `module-retry`, `module-may`, `platform-page`, `module-contract`, `module-session`; `features`, `ready`, `select(ref, {tab})`, `card.closed` — `module-page-calls` (N5); the parts of the late layer — N1.6 `objects`, `events` (`refresh {access}`), `adds`, the sections `domain`, `access`, `held`, `schema` (the form by `schema` — jsdom test `module-shared-schema`); `return` — jsdom test `module-return`
- [ ] **P/07-04** [test] the unit form always sends `ifMatch`, the screen of 412 N1.5 `forms`; `api` with `ifMatch` at tables and settings doors — jsdom tests `Source/tests/console/module-form-if-match.test.js` (judge-only: owner tests under P/07-R265), `module-page-calls.test.js` (N5); the reason — TSV does not see the behaviour of the page
- [ ] **P/07-05** [test] rows by the feed N1.4 `changes` — checked by jsdom tests `Source/tests/console/module-changes.test.js` (judge-only: owner tests under P/07-R265), `module-calls.test.js` (N5); the reason — TSV does not run the page
- [ ] **P/07-03** [test] a refusal at the field N1.5 `forms` — checked by jsdom test `Source/tests/console/module-refusal-field.test.js` (judge-only: owner tests under P/07-R265) (N5); the reason — TSV does not run the page
- [ ] **P/07-06** [test] the tree by the folders of the cluster N1.5 `tree` — checked by jsdom test (judge-only: owner tests under P/07-R265) `module-folders` (N5) when the module has it; the reason — TSV does not run the page
- [ ] **P/07-07** [test] `opts.subsystems` and the unplaced units of all subsystems of the catalogue N1.4 — the owner of the published common module bytes closes this debt with `module-unplaceable-all`, `module-subsystems-none` (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page
- [ ] **P/07-08** [test] forms without a write at a subsystem with `writes_via` N1.5 — the owner of the published common module bytes closes this debt with `module-writes-via` (N5). The unchanged witness does not execute the rule; for the generation line this remains a recorded dependency, neither PASS nor FAIL; the reason — TSV does not run the page

**Related byte-owner debt `v1showsHidden` (N5, alongside P/07-07 and P/07-08).** The version-1 published behaviour that shows hidden fields is not accepted as the rule. The byte owner must demonstrate omission from both the ordinary form and explicit `display.form`, with visible controls preserved. The P/06 OpenAPI property is source-form evidence only and closes no behavioural debt.

# P/05 — Resource: norms

This English text is the source; the Russian translation `ru/spec/05-resource.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The canon of the lesson. Lecture (`ru/05-resource.md`, for people, not in the export), [contract](05-resource.api.openapi.yaml), [instructions](05-resource.README.md),
[life cycle](../lifecycle.md). The form of the event line, the event id,
the buckets, the writers of the file, the encoding of names and the writing of a line are [the event log contract](../../common/contracts/event-journal.md); the presence
lock and the count `room` are [the presence lock contract](../../common/contracts/presence-lock.md): the lesson is the owner of both. The request of N1.5, the merge, the reaper, the submission and the console doors are [chapter 6.4](../../06-console/spec/06.4-console.norms.md) (P/06);
repeat suppression and the execution of requests are [chapter 3.6](../../03-worker/spec/03.6-worker.norms.md). «P/0N» is a lesson of the
module, «P/0N.K» is its chapter. Norm ids are `P/05-MM`.

## Index

The index locates existing rules and introduces none.

| Topic | Requirements | Files |
|---|---|---|
| `local_objects` local objects | P/05-R006, P/05-R009, P/05-R010, P/05-R061, P/05-R066 | `spec/05-resource.README.md`, `Platform/common/contracts/event-journal.md` (file-names-in-shared-trees) |
| `object_keys` keys and prefixes | P/05-R007, P/05-R008, P/05-R041, P/05-R057, P/05-R060, P/05-R109 | `spec/05-resource.api.openapi.yaml`, `forms/README.md` |
| `row_objects` row objects and file objects | P/05-R006, P/05-R007, P/05-R064, P/05-R104 | `spec/05-resource.README.md`, `spec/05-resource.api.openapi.yaml` |
| `object_door` object door admission | P/05-R008, P/05-R036, P/05-R040, P/05-R065, P/05-R167, P/05-R193 | `spec/05-resource.api.openapi.yaml`, `forms/door-roles.tsv` |
| `object_listing` object listing | P/05-R008, P/05-R038, P/05-R040 | `spec/05-resource.api.openapi.yaml` |
| `cluster_objects` cluster reads and missing answers | P/05-R027, P/05-R039, P/05-R040, P/05-R059, P/05-R062, P/05-R105, P/05-R304 | `Platform/common/contracts/object-client.md` (reading-cluster-objects), `spec/05-resource.api.openapi.yaml` |
| `object_versions` object written and tombstones | P/05-R002, P/05-R015, P/05-R017, P/05-R063, P/05-R185, P/05-R187, P/05-R190 | `Platform/common/contracts/tombstone.md`, `spec/05-resource.README.md` |
| `body_copy` body copies | P/05-R005, P/05-R012, P/05-R015, P/05-R036, P/05-R065, P/05-R112, P/05-R176, P/05-R185, P/05-R187, P/05-R193 | `spec/05-resource.api.openapi.yaml`, `Platform/common/contracts/tombstone.md` |
| `ceilings` independent size and time limits | P/05-R014, P/05-R028, P/05-R035, P/05-R045, P/05-R163, P/05-R314 | `forms/runtime-constants.tsv`, `spec/05-resource.api.openapi.yaml` |
| `event_lines` event line and writing | P/05-R018, P/05-R023, P/05-R049, P/05-R259, P/05-R301 | `Platform/common/contracts/event-journal.md`, `spec/05-resource.README.md` |
| `event_query` event query and merge | P/05-R019, P/05-R021, P/05-R022, P/05-R023, P/05-R024, P/05-R037, P/05-R050, P/05-R051, P/05-R069, P/05-R071, P/05-R072, P/05-R093, P/05-R094, P/05-R095, P/05-R096, P/05-R097, P/05-R098, P/05-R118, P/05-R119, P/05-R120, P/05-R121, P/05-R123, P/05-R177, P/05-R259, P/05-R261, P/05-R299, P/05-R305 | `spec/05-resource.api.openapi.yaml`, `forms/README.md`, `spec/05-resource.README.md` |
| `index_cache` live index and cache | P/05-R020, P/05-R050, P/05-R067, P/05-R305 | `spec/05-resource.README.md`, `forms/runtime-constants.tsv` |
| `retention` retention and holds | P/05-R020, P/05-R024, P/05-R053, P/05-R073, P/05-R074, P/05-R075, P/05-R076, P/05-R077, P/05-R092, P/05-R122, P/05-R226, P/05-R227, P/05-R231, P/05-R232, P/05-R234, P/05-R263, P/05-R264, P/05-R265, P/05-R266, P/05-R301 | `data/resource-heartbeat.schema.json`, `data/resource-heartbeat.outcomes.tsv`, `forms/decision-order.tsv`, `Platform/common/contracts/event-journal.md` (retention-of-a-tree) |
| `heartbeat` resource heartbeat | P/05-R025, P/05-R026, P/05-R077, P/05-R124, P/05-R126, P/05-R127, P/05-R196, P/05-R197, P/05-R199, P/05-R201, P/05-R306, P/05-R308 | `data/resource-heartbeat.schema.json`, `data/resource-heartbeat.outcomes.tsv`, `lifecycle.md` |
| `presence` worker presence and room | P/05-R025, P/05-R026, P/05-R080, P/05-R087, P/05-R088, P/05-R090, P/05-R091, P/05-R199, P/05-R223 | `Platform/common/contracts/presence-lock.md`, `data/presence-lock.schema.json`, `data/presence-lock.outcomes.tsv`, `forms/decision-order.tsv` |
| `door_row` resource door row and freshness | P/05-R025, P/05-R027, P/05-R080, P/05-R082, P/05-R089, P/05-R196 | `data/doors.schema.json`, `data/doors.outcomes.tsv`, `Platform/common/contracts/observation.md` (resource-state-resource_state) |
| `volume_usage` volume usage | P/05-R025, P/05-R053, P/05-R079, P/05-R313 | `data/resource-heartbeat.schema.json`, `lifecycle.md` |
| `resource_pass` resource pass and stalled steps | P/05-R028, P/05-R052, P/05-R053, P/05-R054, P/05-R083, P/05-R100, P/05-R101, P/05-R102, P/05-R234, P/05-R242, P/05-R312, P/05-R313 | `lifecycle.md`, `forms/runtime-constants.tsv`, `spec/05-resource.README.md` |
| `free_ask` space and free requests | P/05-R025, P/05-R053, P/05-R054, P/05-R079, P/05-R084, P/05-R085, P/05-R101, P/05-R182, P/05-R209, P/05-R211, P/05-R212, P/05-R214, P/05-R238, P/05-R240, P/05-R306, P/05-R313 | `data/free-ask.schema.json`, `data/free-ask.outcomes.tsv`, `vectors/relieve/README.md`, `data/resource-heartbeat.schema.json` |
| `bucket_mirror` bucket mirroring | P/05-R030, P/05-R033, P/05-R034, P/05-R036, P/05-R045, P/05-R054, P/05-R086, P/05-R142, P/05-R155, P/05-R156, P/05-R159, P/05-R160, P/05-R175, P/05-R179, P/05-R180, P/05-R181, P/05-R216, P/05-R217, P/05-R220, P/05-R227, P/05-R231, P/05-R274, P/05-R314 | `spec/05-resource.api.openapi.yaml`, `data/resource-heartbeat.schema.json`, `forms/runtime-constants.tsv` |
| `restore` restore and peer attempts | P/05-R030, P/05-R128, P/05-R130, P/05-R134, P/05-R135, P/05-R138, P/05-R139, P/05-R140, P/05-R143, P/05-R146, P/05-R231, P/05-R302, P/05-R303, P/05-R307, P/05-R308, P/05-R312 | `spec/05-resource.api.openapi.yaml`, `data/resource-heartbeat.schema.json`, `lifecycle.md`, `forms/runtime-constants.tsv` |
| `wait` event hint and long poll | P/05-R031, P/05-R032, P/05-R036, P/05-R050, P/05-R148, P/05-R152, P/05-R153, P/05-R154, P/05-R246, P/05-R248, P/05-R250, P/05-R251, P/05-R299, P/05-R300, P/05-R309, P/05-R310 | `spec/05-resource.api.openapi.yaml`, `forms/decision-order.tsv`, `data/resource-heartbeat.schema.json`, `forms/runtime-constants.tsv` |
| `routing` raw paths and route matching | P/05-R033, P/05-R041, P/05-R042, P/05-R057, P/05-R168, P/05-R169, P/05-R170, P/05-R171, P/05-R280, P/05-R282, P/05-R288, P/05-R293, P/05-R294, P/05-R295, P/05-R296, P/05-R297 | `spec/05-resource.api.openapi.yaml`, `forms/README.md` |
| `http_streams` representations and stream failures | P/05-R034, P/05-R035, P/05-R036, P/05-R038, P/05-R045, P/05-R051, P/05-R157, P/05-R165, P/05-R166, P/05-R173, P/05-R174, P/05-R283, P/05-R298, P/05-R311, P/05-R314 | `spec/05-resource.api.openapi.yaml`, `forms/refusals.tsv` |
| `tls` TLS and role admission | P/05-R004, P/05-R043, P/05-R044, P/05-R126, P/05-R172, P/05-R196, P/05-R286 | `forms/door-roles.tsv`, `spec/05-resource.api.openapi.yaml`, `lifecycle.md`, `Platform/common/contracts/role-certificate.md` |
| `start` resource start | P/05-R046, P/05-R047, P/05-R048, P/05-R052, P/05-R312 | `lifecycle.md`, `forms/daemon-flags.tsv`, `Platform/common/contracts/schema.md` (check-at-start) |
| `console_owners` console-owned operations | P/05-R018, P/05-R021, P/05-R037, P/05-R055, P/05-R162 | `Platform/06-console/spec/06.4-console.norms.md`, `spec/05-resource.README.md` |
| `refusals` refusals and durability outcomes | P/05-R010, P/05-R038, P/05-R040, P/05-R042, P/05-R045, P/05-R051, P/05-R054, P/05-R055, P/05-R056, P/05-R058 | `forms/refusals.tsv`, `spec/05-resource.api.openapi.yaml`, `Platform/common/contracts/production-obligations.md` |
| `family_ownership` owned families and their readers | P/05-R003, P/05-R018, P/05-R025, P/05-R026 | `Platform/common/data/catalog.tsv`, `Platform/common/LAYERS.md` (6-data-families) |

## N0 Vocabulary

<!-- req: P/05-R001 -->

Normative keywords (MUST, MUST NOT, SHOULD, MAY by RFC 2119 and RFC 8174) follow the [course canon](../../common/NORMATIVE-TERMS.md). The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

<!-- req: P/05-R058 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner. Q1/Q5/Q6 and MB1: distinguish pre-effect refusal from unknown publication durability; retain required tombstones, defer unsafe pruning and copy bodies only from their owner. A neighbour copy is never a source for retransmission after `404`.

## N1 Form

The positive integer settings owned by this lesson are [runtime-constants.tsv](../forms/runtime-constants.tsv); it is their numeric source. HTTP bounds/defaults stay in the [OpenAPI](05-resource.api.openapi.yaml), and high/low in the existing P/02 space form. ALIVE_EVERY/LOST_AFTER belong to the observation contract; JSON_DEPTH belongs to P/01. Equal values do not merge distinct budgets. WAIT_OBSERVE_MS / 1000 is the existing observation period in seconds. A pending ms reader/validator is a delivery dependency, not a waiver or a changed physical duration.

<!-- req: P/05-R002 -->

**Time.** The time fields of the rows and objects of the lesson are time by [the canon of N0 of P/01.1](../../01-store/spec/01.1-store.norms.md#time-in-a-row): the event line — `t` ([the event log contract](../../common/contracts/event-journal.md)); the resource heartbeat object `platform/resources/<server>/heartbeat` — `ts`, `usage_at`, `pass_started`; the door row `platform/doors/<host>` — `since`, `at`; `<sub>/requests/free-<server>-<volume>` — `at`; the tombstone `.gone/<object-key>` — `written` (written by the console, [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.5).

<!-- req: P/05-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `platform/resources/<server>/heartbeat`, `platform/doors/<host>`, `<sub>/requests/free-<server>-<volume>`, `<events root>/<sub>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/<sub>.alarms/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/console/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/console.alarms/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/.mirror/<server>/<tree>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl`, `<events root>/.workers/<sub>/<instance>.lock`, `<events or objects root>/<path>/%h<sha256>.name`, `<objects root>/<dir>/~lock`, `.gone/<object-key>`, `objects/<sub>/<manifest:objects.rows>`, `objects/<sub>/<manifest:objects.rows>/*`;
- writes: `<sub>/blobs/sha256-<hex>` (put);
- reads: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `platform/schema`, `<sub>/heartbeats/<name>`, `platform/decommission/<host>`, `platform/doors/<host>`, `platform/resources/<server>/heartbeat`, `<sub>/retention`, `<sub>/alarms_retention`, `platform/space`, `platform/mirror`, `<sub>/<manifest:tables>/<name>`, `<sub>/<manifest:unit.rows>/<id>` (the unit rows of the manifest with about — the addressee of a hold, the holds contract; P/02.5 N1.4), `/etc/w2c/tls/<role>/server.key`.

<!-- req: P/05-R004 -->

The resource reads the key of its own kit with `RESOURCE_TLS=1` (N1.4 `door.mode` `mtls`, `cert_until`; «Admission to the resource doors»; [the role certificate contract](../../common/contracts/role-certificate.md) `kit`).

<!-- req: P/05-R005 -->

The resource puts body copies to a neighbour (put) and deletes its own copy older than the tombstone (delete); it confirms tombstones (cas) and removes them (delete) — N1.1 «Bodies at the resource», «Tombstones».

### N1.1 Object

<!-- req: P/05-R006 -->

The `object` form is defined by its separately identified rules: P/05-R059, P/05-R060, P/05-R061, P/05-R062, P/05-R063, P/05-R064, P/05-R065, P/05-R066.

<!-- req: P/05-R059 -->

**`client`.** The address OBJECTS, the operations (rule, api, ops), the reading of cluster objects, the outcomes and the action of the client — the object store client contract common/contracts/object-client.md.

<!-- req: P/05-R060 -->

**`key`.** `<family>`/… ; the families of the platform: heartbeats, contenders (P/03.4, P/03.2), controller (P/04), snapshot, blobs, commands (the contract of the request and its mark, «Mark» mark) — the manifest does not name them.

<!-- req: P/05-R061 -->

**`writer`.** One directory — one writer: worker → `<s>`/heartbeats/*, `<s>`/contenders/*; controller → `<s>`/snapshot/*, `<s>`/snapshot-tables/*, `<s>`/controller/*; console → `<s>`/blobs/*; resource → platform/resources/*.

<!-- req: P/05-R062 -->

**`cluster`.** A file on the server of the writer; on reading the fresh copy (written) wins; a server that did not answer is missing.

<!-- req: P/05-R063 -->

**`written`.** The mark of the keeper resource at the write of the key (X-Written of the door, written of the listing), not a time field of the body. **Object written and tombstones.** Every write of the key sets written strictly greater than the former written of the same key: the clock has not moved forward — the former + 0.001 s. A new write of the same bytes is a new version, the same (server, written) is the same version (the observation contract «changed»).

<!-- req: P/05-R185 -->

**Object written and tombstones.** A body copy (PUT .../blobs/`<digest>` with X-Written, the mirror) keeps the written of the source copy, not its own: otherwise a copy that lay before the delete would be newer than the tombstone. For a copy of the same key already lying there written does not decrease (the greater of the two).

<!-- req: P/05-R187 -->

**Object written and tombstones.** For a key deleted here the former written is the written of its tombstone `.gone/<object-key>` while it lies: a new write is strictly greater than it (otherwise the neighbours would count it older than the delete, the tombstone contract `drop`, `rewrite`). There is no separate memory — the tombstone is the mark. A write after written removes the tombstone by the same action, before the answer of the write (the tombstone contract `rewrite`). The tombstone is removed — the bound is only the former rules.

<!-- req: P/05-R190 -->

**Object written and tombstones.** The tombstone is unreadable (garbled) — the bound is not known, the write is not refused: written by the former rules, the tombstone stays (it is not removed: a write after written is not proven), the next delete of the body rewrites it.

<!-- req: P/05-R064 -->

**`row_object`.** Keys whose next writer can be on another server are store rows objects/`<key>` (objects.rows of the manifest; commands/* — always, for a manifest with requests); put_new = a write with cas "".

<!-- req: P/05-R065 -->

**`door`.** Only the families PLATFORM_DOOR (platform/resources/*, domain/* (M11), */heartbeats/*, */contenders/*, */snapshot/*, */snapshot-tables/*, */controller/*, */blobs/*) and objects.door of the manifest; anything else — 403. **Object door admission.** Tombstones .gone/`<object-key>` — read only: the listing prefix=.gone/ and GET of the body (the tombstone contract). `*` of the first part is a subsystem of the manifest catalogue: `other/heartbeats/x` without a manifest other — 403.

<!-- req: P/05-R193 -->

**Object door admission.** The resource does not parse the bodies of door objects: an object unreadable by its family (a worker heartbeat, a mark) it gives as it is, the judgement is with the reader.

<!-- req: P/05-R066 -->

**`disk`.** `<PLATFORM_DIR>`/objects/`<key>`. **Local objects.** Directory 0775, file 0644. The write — temp + rename under the directory lock `<dir>/~lock`, flock(LOCK_EX), the file is not deleted. Service names (the lock, the temporary name) — the event log contract «File names».

<!-- req: P/05-R007 -->

An object key is a non-empty relative path: non-empty segments, without exact `.`/`..`, backslash and control characters. **Keys and prefixes.** `prefix` is the beginning of such a key, also emptiness or an ending `/`; it is not a full key.

<!-- req: P/05-R104 -->

**Row objects and file objects.** The objects door does not give row objects even from an allowed prefix.

<!-- req: P/05-R105 -->

**Cluster reads and missing answers.** With equal `written` the server with the lexicographically greater name is chosen; the absence of an answer is called `missing`, not the absence of the object.

<!-- req: P/05-R008 -->

**Object listing.** A listing returns the closed form ObjectListing of N2; deleted objects are tombstones `.gone/<object-key>` (below, «Tombstones»): an ordinary listing does not show them, `prefix=.gone/` is a read-only listing of tombstones. A tombstone ObjectEntry has its object-write `written`, the server holding the selected copy, and the size of its returned body; the deletion stamp is read from the body, not from the listing. A listing gives only the keys of the door families under `prefix` — a filter, not a refusal: `prefix=testsub/`, `prefix=t`, an empty `prefix` — 200 with the keys of the door families that start with it; keys outside the door families do not enter the listing. **Keys and prefixes.** A `prefix` with which no possible key of the door families starts (`other/`) — 403. A `prefix` not in UTF-8 (`%FF`) — 400.

<!-- req: P/05-R109 -->

**Keys and prefixes.** Reading a key: a key not by the grammar (not UTF-8, Cc, Zl, Zp — including U+2028, `.`/`..`, an empty segment) — 400. A key outside the door families, including the directory `testsub/heartbeats` of two parts, — 403. A key of a family that does not exist (including a directory inside a family, `testsub/heartbeats/sub`), — 404. A key that differs from the written one only by case or normalization (`W-1` with `w-1`), is its own key: 404, not another's object.

<!-- req: P/05-R009 -->

**File names in shared trees** — one encoding for all implementations: [the event log contract](../../common/contracts/event-journal.md#file-names-in-shared-trees).

<!-- req: P/05-R010 -->

A file system error after admission is a refusal of the write, not a success and not «there is no file».

<!-- req: P/05-R012 -->

**Bodies at the resource** (the field `blob`, the digest, the bytes door of the console, the cleanup of bodies — [chapter 6.1](../../06-console/spec/06.1-console.norms.md) N1.5): **`mirror`.** Every owner-originated local body (a received copy is not a source) — to the next copies live neighbours of the ring (N1.4 mirror), always, regardless of mirror.enabled. **Body copies.** `copies` — from the row platform/mirror (an integer ≥ 0), no row or no field copies — 1. The row does not read — bodies are not copied in this pass, the reason is in the heartbeat (settings_unread: mirror).

<!-- req: P/05-R112 -->

**Body copies.** `reception`: hash while reading; PEER_FAILS; the copy door exists only for the key `<sub>/blobs/sha256-<64 lowercase hex>` of a subsystem with a blob field; another key (uppercase hex, without `sha256-`, a subsystem without a blob field) — an ordinary object, its owner writes it: 405.

<!-- req: P/05-R014 -->

Resource ceilings (the shared ceilings — [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.4; checked at the door before reading the body where possible; a refusal, not a truncation):

| What | Limit | Where | Words / code |
|---|---|---|---|
| an object at the resource door (reading, body copy, mirror piece) | `Content-Length.maximum` of the [HTTP form](05-resource.api.openapi.yaml) blob-copy operation | the resource door (N2) | `413` |
| lines in the answer of `/events` | `limit.default` and `limit.maximum` of `GET /events` in the [HTTP form](05-resource.api.openapi.yaml) | the index (N1.3) | truncation, `truncated` |
| retention term | a finite number > 0 | the resource (N1.3 `retention`) | «not known», remove nothing |
| the object store | `max_bytes` (0 — no ceiling); the store says it itself | `put` | `TooLarge` «over this store's limit» |

<!-- req: P/05-R015 -->

Body cleanup ([P/06.1](../../06-console/spec/06.1-console.norms.md) N3 «body sweep»): in the exclusive window the operator also closes the incoming mirror copies; a copy than which the tombstone of the deleter is newer is not accepted (N4, «deleted later» — 409).

<!-- req: P/05-R017 -->

**Tombstones and convergence of body copies** (the bodies, their digest, the bytes door of the console, the mirror of bodies at the console and the cleanup — [P/06.1](../../06-console/spec/06.1-console.norms.md) N1.5): **`delete`.** The tombstone .gone/`<object-key>` {written, peers, acked}, the neighbours peers, the reading by a neighbour, the confirmation 404 and the removal — [the tombstone contract](../../common/contracts/tombstone.md); the objects door has no DELETE.

### N1.2 Event

<!-- req: P/05-R018 -->

The form of the event line (`line`), the bucket and its path (`bucket`), the class (`class`), the journal `audit` (`journal`), the writers of the file (`writer`), the event id and the writer instance — [the event log contract](../../common/contracts/event-journal.md). The lesson is its owner: the resource reads buckets (N1.3), copies the closed ones (N1.4 `mirror`), removes them by term (N3 «resource pass»). Repeat suppression (`suppress`) — [chapter 3.6 N1.2](../../03-worker/spec/03.6-worker.norms.md); `older_epochs` and the operator marks (`marks`) — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.2 (the console).

<!-- req: P/05-R301 -->

**Bucket write metadata.** Before the writers are implemented, the owner of this lesson publishes in the implementation repository the local contract and library API for persisting and reading a bucket's `written`. All event writers and the resource use that contract. The representation is private to the implementation and is not decoded by the stand; acceptance observes the stamp after append, restart and restore and its retention outcome. This does not introduce a public event field or require a new common module.

<!-- req: P/05-R019 -->

`subsystem` of an index line is the name of the manifest, for the lines of the alarm tree too (`testsub`, not `testsub.alarms`). **Event query and merge.** `unit` in the answer of the index is the full reference `<tree>/<unit>`. For the journal it is `audit/<role>`, for a mark — `console/<instance>`, and its `of` is the addressee. The reference is logical: the tree is without the suffix `.alarms`, which is the layout of the writer ([the event log contract](../../common/contracts/event-journal.md) `class`); a line from `audit.alarms/<role>` answers and is selected by a query as `audit/<role>`, from `<sub>.alarms/<unit>` — as `<sub>/<unit>`, together with the observations (N3 «query» step 2).

### N1.3 Index and term

<!-- req: P/05-R020 -->

The `index` form is defined by its separately identified rules: P/05-R067, P/05-R069, P/05-R259, P/05-R071, P/05-R072, P/05-R073, P/05-R074, P/05-R075, P/05-R076.

<!-- req: P/05-R067 -->

**`index.one_per_resource`.** Over its own tree and the .mirror/`<server>`/ copies; the state is always live; there is no rebuild or separate `no_index` startup phase. **`index.cache`.** Bounded (INDEX_CACHE_BYTES), dropped without loss of correctness; a file is reread by size/mtime/inode from the place.

<!-- req: P/05-R069 -->

**`index.query`.** The query rules that the merge needs (parameters, defaults, by) — the event log merge contract «The resource query and answer»; the grammar of the parameters and the refusals — below this block.

<!-- req: P/05-R259 -->

**`index.row`.** {id, subsystem, unit, of, epoch, t, kind, server, bucket, class, epoch_is, fenced, …fields}. **Event line and writing.** `server` — the owner of the bucket. A line with its own field server (a line about a server: drain.*, server.decommission_*, workers.no_server) keeps it — in such a row server is the server the line is about, the index does not overwrite it, as class.

<!-- req: P/05-R261 -->

**Event query and merge.** `epoch_is` and fenced are set by the merger — the console or the worker by the event log merge contract; at the resource the lines are without them.

<!-- req: P/05-R071 -->

**`index.epoch_is`.** `current` | `fenced` | `earlier-run` | `unknown`   — by current_epochs from `<sub>`/epoch/* and the policy of the manifest; unknown — only at the worker for an epoch that it did not declare in worker.reads; the needed epoch is not read — a line without epoch_is, incomplete[`<sub>`/epoch] (the event log merge contract «Epochs»).

<!-- req: P/05-R072 -->

**`index.cut, answer`.** The cut, the mirror copies, truncated, partial — the event log merge contract «The resource query and answer»; the answer of the merger (the console, the worker: + complete, incomplete) — in the same place, «The answer».

<!-- req: P/05-R073 -->

**`retention.<sub>/retention`.** {days}      — the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9.

<!-- req: P/05-R074 -->

**`retention.<sub>/alarms_retention`.** {days}      — the default — the event log contract «Retention of a tree»; the form of the row — P/02.4 N1.9.

<!-- req: P/05-R075 -->

**`retention.writer`.** Of both rows — admin by the operator command w2cctl retention (P/02.4 N1.9); the resource and the console only read them (P/02.5 N1.4).

<!-- req: P/05-R076 -->

**`retention.rule`.** Per subsystem, not per unit. **Retention and holds.** `days` — a finite number > 0, anything else — «not known», remove nothing.

<!-- req: P/05-R263 -->

**Retention and holds.** The console marks live no less than the longest tree.

<!-- req: P/05-R264 -->

**Retention and holds.** The holds (holds) keep buckets (the holds contract).

<!-- req: P/05-R265 -->

**Retention and holds.** Mirror copies — an hour longer.

<!-- req: P/05-R266 -->

**Retention and holds.** What is removed — the journal events.removed.

<!-- req: P/05-R092 -->

**Retention deadline.** Use the bucket's own persisted logical `written` from the event-journal contract “Bucket write time”.

<!-- req: P/05-R226 -->

**Retention and holds.** First resolve term reads and holds conservatively; a hold or unknown dependency keeps the bucket.

<!-- req: P/05-R227 -->

**Retention and holds.** For a closed, unheld bucket with readable `written`, delete exactly when `now >= written + seconds`: normal `<sub>` uses `seconds = retention.days * 86400`; `<sub>.alarms` uses `alarms_retention.days * 86400`; `audit`/`audit.alarms` use their journal term; `console`/`console.alarms` use their term with the longest-tree floor. A mirror copy uses the corresponding tree's term plus `MIRROR_RETENTION_EXTRA`, measured from its own copy `written`. Equality deletes; a time below the deadline keeps it. Neither window start/end nor filesystem `mtime` substitutes for `written`.

<!-- req: P/05-R231 -->

**Retention and holds.** `restore` preserves the copy's `written`; it does not restart the retention clock.

<!-- req: P/05-R232 -->

**Retention and holds.** All usual conservative holds and read outcomes precede this predicate.

<!-- req: P/05-R021 -->

The merge of the resource answers by the console (`merge`) — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.3 and N3 «merge» (the console); the form of the console answer (`answer` above, `ConsoleEvents` of the contract) is common with the resource.

<!-- req: P/05-R022 -->

A query uses finite `from`/`to`, `from ≤ to`; `limit` is an integer within the HTTP form bounds: - `from`, `to` — an ASCII decimal number: an optional `-`, digits (`_` is allowed between digits), an optional dot with digits on at least one side, an optional exponent `e`/`E` with a sign; `1_0`, `.5`, `5.`, `1e3` are numbers, `1e-400` is 0; `+1`, a space (`%201`, `1%20`), non-ASCII digits (`١`), `0x10`, an overflow — 400. **Event query and merge.** `limit` — only ASCII digits (leading zeros are allowed: `01`), otherwise 400; `since` of the hint — by N1.6. `unit` — UnitRef `<sub>/<id>`: a bare id, empty, `testsub/`, `/c1` — 400. `late` — an integer ≥ 0 in decimal notation, only together with `by=occurred`: anything else — 400. An empty or repeated parameter — 400 (N2); an unknown non-empty parameter is not read (for `/events/wait` — 400, N1.6).

<!-- req: P/05-R023 -->

**Unreadable bucket line** (P/01.1 N0 «Stability of output»). A line that is not JSON, not an object, with a BOM, with a number outside JSON (`NaN`), without `kind`, `t` or `id`, with `id` not a string, and also a file not in its place (a bucket path not by N1.2, for example `e01`) is skipped: it does not enter `events` and `truncated`, the answer is 200, and the number of such lines is `lines_garbled` of the answer (the field is present only when it is greater than 0). **Event line and writing.** A torn last line is still `partial`, not `lines_garbled`.

<!-- req: P/05-R118 -->

**Event query and merge.** The console adds up the `lines_garbled` of the answering resources and itself skips a line of a resource answer not in the form EventRow, adding it to its own `lines_garbled`.

<!-- req: P/05-R119 -->

**Event query and merge.** `events` in BucketInfo is the number of whole readable lines of the bucket; 500 of a listing — only an unreadable directory or metadata.

<!-- req: P/05-R024 -->

Another query form — 400, including NaN/Infinity, a fractional limit and a bare unit. `by`, the defaults, `truncated` of the resource and of the merger — the event log merge contract «The resource query and answer».

<!-- req: P/05-R120 -->

**Event query and merge.** `fenced=true` if and only if `epoch_is=fenced`; earlier-run is not fenced.

<!-- req: P/05-R121 -->

**Event query and merge.** This lesson does not promise an atomic snapshot of several files or resources.

<!-- req: P/05-R122 -->

**Retention and holds.** An unknown read of the term or of the holds does not equal absence: a dependent tree is not deleted until a reliable read. An absent retention row gives the default, a read error does not.

<!-- req: P/05-R123 -->

**Event query and merge.** `complete`, `partial` of the merger — the event log merge contract «The answer», «The resource query and answer».

### N1.4 Resource

<!-- req: P/05-R025 -->

The `resource` form is defined by its separately identified rules: P/05-R077, P/05-R199, P/05-R079, P/05-R080, P/05-R082, P/05-R083, P/05-R084, P/05-R085, P/05-R086, P/05-R087, P/05-R088, P/05-R089. There is one resource process per server, without a controller.

<!-- req: P/05-R077 -->

**`heartbeat`.** The object platform/resources/`<server>`/heartbeat every HEARTBEAT_EVERY {server, ts, url, schema, build, usage, usage_at, space: {total, free, used, full}, volumes, units: {sub: [id]}, workers, running, short, waits, mirrors: {server: n}, pass_started, pass_stalled, restore, mirror, door, retention_garbled?: [`<sub>`…], retention_withheld?: {`<sub>`: days_garbled | unknown | holds_unread}, …}. **Resource heartbeat.** `retention_garbled`, retention_withheld — the reasons of the retention pass (N3 retain, N4; no reason — no fields). `settings_unread`?: [mirror | space] — the setting rows of the pass that did not read: the step mirror (and the body copies of N1.1) or relieve is not executed in this pass; in ascending order of bytes; none — no field.

<!-- req: P/05-R196 -->

**Resource heartbeat.** `door`: {addr, mode: loopback | mtls, cert_until} — in every heartbeat, written by the resource: addr — RESOURCE_HOST:RESOURCE_PORT. **Resource door row and freshness.** `mode` — loopback without RESOURCE_TLS (loopback only), mtls with RESOURCE_TLS=1. `cert_until` — the wall seconds of the end of the term of the server certificate of its own kit, with mtls. With mtls the server presents the leaf, then its authority (the role certificate contract server; the client — own_client, the object client contract tls); read by w2cctl tls status (P/02.4 N1.9).

<!-- req: P/05-R197 -->

**Resource heartbeat.** `waits`, restore, mirror, units — in every heartbeat: units — {`<sub>`: [`<id>`…]} of the units that the heartbeats of the workers of this box from running name in status, ids in ascending order of bytes; none — {}. A worker heartbeat is unreadable (the family heartbeats P/03.4: the whole object, for the resource also an element status[] not in form) — its units do not enter units: the unreadable does not widen.

<!-- req: P/05-R199 -->

**`workers`.** [`<sub>`/`<slot name>`…] — all the slots that the resource knows about on its box. **Worker presence and room.** `running`: [`<sub>`/`<slot name>`…] — with a live process (it holds the presence lock, the content in form with a non-empty worker). `unknown`: [`<sub>`/`<slot name>`…] — the presence did not read and the slot is known from current readable content (otherwise the whole-role unknown snapshot below): the lock file does not read or flock/stat of the lock gave an error, except «busy» and ENOENT of stat (the presence lock contract). `instances`: {`<sub>`/`<slot name>`: `<instance>`}; the key is with the subsystem: a slot name is unique only within its own subsystem (P/03.2 `<sub>/slots/<name>`), two subsystems with one `slot.prefix` have the same names.

<!-- req: P/05-R201 -->

**Resource heartbeat.** `pass_stalled`: `<seconds>`, only while the pass hangs (PULSE_LIMIT). One heartbeat form: the console gives it as ResourceRow P/06.5 (a derived output), the controller derives the presence from it (below, P/04 «fate»).

<!-- req: P/05-R079 -->

**`usage`.** An integer — the bytes of the bucket files of the trees of this server and of the copies in .mirror/. **Volume usage.** `usage_at` — the wall seconds of the measurement. `space` — the volume of the event tree: total, free, used — bytes (statfs), full — the share used/total from 0 to 1 (not a flag). `volumes` — the same per volume.

<!-- req: P/05-R080 -->

**`door_row`.** `platform/doors/<host>` {url, since, at, room.`<sub>`…, live.`<sub>`…}; at — every ALIVE_EVERY (the observation contract «Resource state»). **`room`.** The elements room.`<sub>` and live.`<sub>` — by the presence lock contract «Count room» (presence-lock.md). **Resource door row and freshness.** Do not write the door while platform/decommission/`<my server>` stands (the observation contract «Server decommissioned» narrower; the console deleted it). This restriction concerns the door row; heartbeat, HTTP service and resource passes continue.

<!-- req: P/05-R082 -->

**`lost_after`.** LOST_AFTER                      — the observation contract «Freshness»; by a change on the clock of the reader.

<!-- req: P/05-R083 -->

**`pass`.** The first — at start, right after readiness (the door row is written); then every PASS_EVERY from the end of the pass: retain → usage → relieve → mirror; each step in its own attempt; pass_stalled on a hang.

<!-- req: P/05-R084 -->

**`space`.** `platform/space` {enabled, high, low}   — shares; the typed form and defaults — P/02.4 N1.9, data/space.schema.json; enabled until switched off: **Space and free requests.** No row — enabled with high/low defaults of that space form. `enabled`: false — the resource removes its own row free-*. The row does not read — the step relieve is not executed: the high/low defaults of the space form are not substituted, its own row free-* is neither written nor removed, the reason is in the heartbeat settings_unread: space the form of the row — P/02.4 N1.9 (written by admin, w2cctl space).

<!-- req: P/05-R085 -->

**`free_ask`.** `<sub>`/requests/free-`<server>`-`<volume>` {free, volume, server, at}   — its own form: written and rewritten with cas only by the resource, not create-once, without unit/digest/family schema; for manifests with requests.free, while the volume > high. **Space and free requests.** For requests.free volume — a non-empty name of ASCII A-Z/a-z/0-9/_, 1–64 bytes, without a hyphen (a box has one volume — the file system of the event tree, the name events). `server` — a non-empty key segment of P/01.1, hyphens are allowed. The split at the last hyphen is unambiguous. Another volume is out of profile: diagnose the configuration, do not create/change the request of this volume.

<!-- req: P/05-R209 -->

**Space and free requests.** `free` = used − total·low − Σ freeing from the heartbeats (only the freeing not yet reflected in used). With free ≤ 0 (and under the mark low) the row is removed.

<!-- req: P/05-R211 -->

**Space and free requests.** Nobody executes or marks it.

<!-- req: P/05-R212 -->

**Space and free requests.** The addressee — all the workers of the subsystem `<sub>` on the server `<server>`; `<volume>` — the volume of the resource, not a place of the subsystem. Σ freeing — the sum of freeing.`<volume>` (P/03.4 N1.1) over the live heartbeats of the workers `<sub>` on this server, no field — 0 (vectors 05-resource/vectors/relieve; the VMS request freeing).

<!-- req: P/05-R214 -->

**Space and free requests.** Between low and high, while need > 0, its own row stands as it is — it is neither removed nor rewritten.

<!-- req: P/05-R306 -->

**Space and free requests.** `short` counts only volumes whose current used/total is strictly above high. At or below high it is zero even if an own request remains unchanged between low and high; the stored `free` and `at` of that request do not become the current shortfall. For qualifying volumes the family form defines the maximum need over subsystems, rounding and saturation. An unread pass input keeps the previous value, subject to the independently known disabled-space outcome.

<!-- req: P/05-R086 -->

**`mirror`.** `platform/mirror` {enabled, copies}; no row or no field enabled — enabled: false, buckets are not copied until enabled: true. **Bucket mirroring.** The row does not read — the step mirror is not executed, the reason is in the heartbeat settings_unread: mirror, `copies 1, enabled false` are not substituted; bodies — N1.1 mirror.

<!-- req: P/05-R216 -->

**Bucket mirroring.** The neighbours — the next copies live servers by name; liveness — by the door row platform/doors/`<host>`, as in the merge contract «Live resources» (the version changed within the last LOST_AFTER on the clock of this resource, the first look — as fresh), the heartbeat of the neighbour does not judge here.

<!-- req: P/05-R217 -->

**Bucket mirroring.** Only closed buckets. The copy in .mirror/`<server>`/…. A copy is never a source while the owner answers; PEER_FAILS, a bucket within the resource door byte limit (OpenAPI Content-Length.maximum) as a whole,.

<!-- req: P/05-R274 -->

**Bucket mirroring.** A copy adds MIRROR_RETENTION_EXTRA to its term.

<!-- req: P/05-R220 -->

**Bucket mirroring.** A closed bucket larger than that door limit (the mirror reception limit) is not copied: there is no assembly from pieces and no partial copy, it enters mirror.skipped of the heartbeat on every pass, the other buckets are copied. The form of the row platform/mirror — P/02.4 N1.9 (written by admin, w2cctl mirror).

<!-- req: P/05-R087 -->

**`presence`.** `runs` | `gone` | `unlisted` | `unknown`   — about the worker process of its own box — a conclusion from the heartbeat fields above: the key `<sub>`/`<name>` of the worker slot of the subsystem `<sub>`: in running — runs; in unknown — unknown; in workers, but not in running and not in unknown, — gone (the resource knew the process, it is dead); not named in workers — unlisted (not registered at the resource); a heartbeat without these fields — nothing about the worker (P/04 «fate»); an absent one of the three fields is an empty list, not unreadability: the selection is [decision-order.tsv](../forms/decision-order.tsv), procedure `presence`. **Worker presence and room.** The listing `<events root>`/.workers/`<sub>`/ is not obtained (an error, except ENOENT of a directory not yet created — that one is empty): the heartbeat has none of the three fields — nothing about the workers (P/04 wait), the former names are not carried over, there is no partial set; the rest of the heartbeat — as usual. How the resource learns the presence — the presence lock contract. `silent` is a state of the resource itself (the observation contract), not a value of the presence.

<!-- req: P/05-R088 -->

**`presence_lock`.** `<events root>`/.workers/`<sub>`/`<instance>`.lock — the presence lock contract (presence-lock.md); after flock the resource compares fstat(fd) and stat(path); if they do not match (ENOENT of stat too), it does not touch the file; the flock of the worker is blocking.

<!-- req: P/05-R223 -->

**Worker presence and room.** The content — the family presence-lock (data/presence-lock.schema.json, presence-lock.outcomes.tsv; below): {instance, sub, worker, server, pid}, worker "" before the name is captured; a busy lock with empty or out-of-form content — a live process without a number (in room, not in workers, running, live); unknown — only an unreadable file and an error of flock or stat, except «busy» and ENOENT.

<!-- req: P/05-R089 -->

**`requires`.** `placement.requires`: resource — the worker is outside the pool while the resource of its server is silent (P/04).

<!-- req: P/05-R026 -->

**Writer and reader heartbeat forms.** The current writer and reader MUST include `door`, `waits`, `restore`, `mirror` and `units`.

<!-- req: P/05-R124 -->

**Resource heartbeat.** At initialization before any operations: `units = {}`, `restore = {}` if there are no necessary neighbours, `waits = {waiting:0, held:0, full:0, replaced:0, max:LONG_POLL_WAITERS}`, and the mirror counters `skipped`, `failed`, `peer_errors`, `lines_garbled` are zero. Existing necessary neighbours still have their actual restore entries, including incomplete ones; neutral values do not erase an error or a pending attempt.

<!-- req: P/05-R126 -->

**Resource heartbeat.** `door` always has its actual `addr` and `mode`; `mtls` additionally requires the actual server-certificate `cert_until`.

<!-- req: P/05-R127 -->

**Resource heartbeat.** The ordinary root schema requires those current fields and the mtls condition in both modes. A violation has the existing unreadable-heartbeat outcome; a reader does not synthesize successful operation or TLS state from an absent field.

<!-- req: P/05-R090 -->

**Unnamed presence uncertainty.** A current lock error without a readable slot name makes the whole role snapshot unknown, even after a successful listing and at cold start. **Worker presence and room.** Apply the presence-lock contract's “An unknown role snapshot”: omit `workers`, `running`, `unknown` and snapshot-derived `instances`, set the affected `room.<sub>` to `"unknown"`, omit its `live.<sub>`, keep independently complete room/live of other roles. Do not infer a slot from the filename, prior memory, or another lock; do not interpret the omission as `unlisted` or `gone`.

<!-- req: P/05-R091 -->

**Worker presence and room.** The content of the presence lock is the family `presence-lock` of the lesson: [schema](../data/presence-lock.schema.json), [outcomes](../data/presence-lock.outcomes.tsv) (layers — [LAYERS](../../common/LAYERS.md)): an instance is `{key, file}`, the text of the file with `x-encoding: json` at the root (LAYERS § 6), the column `schema` of the catalogue row names the family, the section is «Data families» below; the meaning is [the presence lock contract](../../common/contracts/presence-lock.md).

<!-- req: P/05-R027 -->

**Cluster objects — through the resource of its own server.** A process of the platform reads the objects of other servers (the heartbeats of workers and resources, the pass reports) through the objects door of the resource of its own server (N2, `scope`); without a resource on its own server with `cluster://` — «not known», not «no» ([the object store client contract](../../common/contracts/object-client.md) `door`). A stand that needs the heartbeats of workers puts a resource on the server of the reader ([P/04](../../04-controller/spec/04-controller.norms.md) N3 «pass()» step 0).

<!-- req: P/05-R028 -->

PULSE_LIMIT is a finite positive limit of the duration of one step of the resource in seconds, chosen and declared by the implementation before the start. The duration is measured by the local monotonic clock, not by t/at of the writer; while a step runs beyond the limit, every heartbeat carries pass_stalled; it is cleared when the step ends, including before the next heartbeat. It is a diagnostic threshold, not a promise to stop a hung call or to wait for an answer.

<!-- req: P/05-R030 -->

**Bucket restore** (a server failure and `power_pull` — [P/04](../../04-controller/spec/04-controller.norms.md) N1.4a): **`restore`.** At start the resource pulls its closed buckets from the neighbours whose heartbeats mirrors name it: GET /mirrored/`<me>`, each bucket by its sum, tmp + rename.

<!-- req: P/05-R128 -->

**Restore and peer attempts.** PEER_FAILS consecutive failures — the neighbour is skipped until the end of this restore attempt; the boundary and the next attempt are P/05-R307.

<!-- req: P/05-R307 -->

**Restore and peer attempts.** A restore attempt traverses the necessary peer set and ends after the required listings/copies have been obtained and checked or the remaining peers have been skipped by PEER_FAILS. An incomplete attempt is followed by another attempt in the same process after RESTORE_RETRY, doubling the interval between incomplete attempts up to RESTORE_RETRY_MAX. The next attempt considers skipped peers again and resets only the procedure-local consecutive-failure sequence, not cumulative diagnostics. A fully done restore schedules no further restore attempt at this start. The backoff is between attempts, not an additional required interval between calls within an attempt.

<!-- req: P/05-R130 -->

**Restore and peer attempts.** `done` when the full lists are received and the copies are checked from all known necessary neighbours. The necessary neighbours — those whose readable heartbeats mirrors name this server. For the necessary door set under P/05-R303, each foreign server is to answer with a full listing GET /mirrored/`<me>` (a full empty listing and 404 — there are no copies, so that neighbour is complete). 404 of GET of an already listed bucket is a missing copy, not an empty listing: the attempt stays incomplete.

<!-- req: P/05-R303 -->

**Restore and peer attempts.** If a neighbour heartbeat is absent or unreadable, all known foreign server doors are necessary regardless of whether the local event root is empty. A nonempty root does not prove that no bucket was lost. Do not infer local completeness from the presence of another bucket or substitute an unconfirmed door set for a full listing.

<!-- req: P/05-R134 -->

**Restore and peer attempts.** A restored bucket keeps the listed copy's written as its own retention stamp, not the receive time or filesystem mtime.

<!-- req: P/05-R302 -->

**Restore and peer attempts.** Do not overwrite an existing local bucket with a checksum-valid copy of the same path whose bytes differ. Identical bytes/sum do not refresh the local retention stamp. If no local bucket exists, the first checked copy may be published; a later differing copy does not roll back the published bytes. Any such observed discrepancy keeps restore incomplete and is diagnosed through the existing diagnostics; receiver `written` does not choose a winner and lines are not merged. A checked checksum alone does not prove completeness of the restored events.

<!-- req: P/05-R135 -->

**Restore and peer attempts.** An unknown or unreadable door leaves the restore incomplete. A skipped/unreadable neighbour leaves the restore incomplete; 500 of a listing and a broken answer by N2, N4 do not count as an empty full list. If there were never any neighbours, there is no remote restore.

<!-- req: P/05-R138 -->

**Restore and peer attempts.** `restored` of the heartbeat — only the buckets actually pulled from this neighbour; a bucket already lying on the volume does not count.

<!-- req: P/05-R139 -->

**Restore and peer attempts.** Then — the reindexing of the subsystem; a copy is never a source while the owner answers (mirror above).

<!-- req: P/05-R140 -->

**Restore and peer attempts.** The local consecutive PEER_FAILS sequence resets after a successful peer operation and at the start of the next restore attempt or mirror pass. A skipped necessary peer leaves the current restore incomplete; the next attempt considers it again.

<!-- req: P/05-R142 -->

**Bucket mirroring.** A mirror peer is considered again next pass.

<!-- req: P/05-R143 -->

**Restore and peer attempts.** These are separate procedure-local sequences; cumulative diagnostic counters are not reset by either boundary. A failure in such a sequence is a transport error, an expired call deadline or a failure of a dependency; a per-row refusal 400/409/422 does not extend the sequence: only that row fails and the other rows continue. A 404 at the GET of a bucket that the peer listed is such a failure: the peer declared the copy and did not give it.

<!-- req: P/05-R308 -->

**Restore diagnostics.** The presence of optional `restore.<name>` extensions is an implementation choice and is not judged. When present, `silent` means current peer unavailability; `last_ok` and `error_at` are wall-clock seconds of the last success and error; `last_error` is the reason text; `next` is wall-clock seconds of the scheduled next attempt. The required `done`, `restored`, `missing` and `failures` fields establish the mandatory restore state; an omitted extension neither proves done nor makes an incomplete peer complete.

<!-- req: P/05-R146 -->

**Restore and peer attempts.** The order of buckets between passes is not a contract.

### N1.6 Hint and HTTP representations

<!-- req: P/05-R031 -->

`GET /events/wait` of the resource is a hint, not a delivery of events. The profile of the lesson: `want` — a non-empty comma-separated list `<sub>/<kind>[/<unit>]`; each part of ASCII letters, digits, `_`, `-`, `.`, 1…64 characters, not starting with a dot. **Event hint and long poll.** `client`, if given, — 1…128 printable ASCII characters without a space. `since` — a decimal uint64 without a sign/leading zeros, 0 by default. `timeout` — finite seconds with the bounds and default of `GET /events/wait` in the [HTTP form](05-resource.api.openapi.yaml). Empty/repeated parameters, unknown parameters (`&foo=1`), other forms and values out of range — 400; `since` and `timeout` — only ASCII digits (and a dot for `timeout`), non-ASCII digits — 400.

<!-- req: P/05-R148 -->

**Event hint and long poll.** `since=0` — the client has no position: the answer at once is `{changed: true, seq, touched}` if under want there are lines in the buckets of the resource of any age; seq is an opaque monotonic number of the resource process, the client only compares it and passes it back. With `since` equal to the `seq` last returned by this resource process and no line under `want` written after that `seq`, the wait ends at its term with `{changed: false, seq}`; a line under `want` written after that `seq` answers `{changed: true, seq, touched}`.

<!-- req: P/05-R300 -->

**Event hint and long poll.** For an unknown nonzero `since`, return `WaitQuiet` with the current `seq` immediately. Apply the `wait` procedure of [decision-order.tsv](../forms/decision-order.tsv): this branch neither enters the wait queue nor replaces an existing wait or consumes its capacity. The client still makes the ordinary pass under P/05-R248.

<!-- req: P/05-R309 -->

**Event hint and long poll.** A `seq` returned by the resource process is positive; zero is only the client's absence of a position. The implementation chooses its initial positive value, which acceptance does not judge; the uint64 bound and monotonicity within the process still apply.

<!-- req: P/05-R246 -->

**Event hint and long poll.** The hint is given by the subsystem trees of the catalogue (`<sub>`, `<sub>.alarms`); the trees `console` and `audit` give no hint. This bounded profile does not require accepting any internal unit names: the periodic pass of the client stays mandatory and works without the hint.

<!-- req: P/05-R310 -->

**Event hint and long poll.** Match `want` and form `touched` using the logical manifest subsystem name without `.alarms`; both its observation and alarm trees can give that hint. A syntactically valid `want` naming `testsub.alarms` is not normalized and matches no subsystem; it does not acquire a new 400 refusal.

<!-- req: P/05-R032 -->

The answer is one of the closed forms WaitAnswer: `{changed:true, seq, touched:[…]}`, `{changed:false, seq}`, `{changed:false, seq, full:true}` or `{changed:false, seq, replaced:true}`. **Event hint and long poll.** In touched — the sorted unique `<sub>/<kind>/<unit>` that match want; the events themselves are not there.

<!-- req: P/05-R248 -->

**Event hint and long poll.** `seq` belongs to one process of the resource; after a restart/an unknown sequence the client makes an ordinary pass. With full/replaced the client does not advance its cursor by seq, but returns to the ordinary pass.

<!-- req: P/05-R152 -->

**Event hint and long poll.** By default up to LONG_POLL_WAITERS_DEFAULT waits (the deployment parameter LONG_POLL_WAITERS); a new wait when full is answered 200/full. Apply [decision-order.tsv](../forms/decision-order.tsv), procedure `wait`, for replacement and capacity. Thus at a full effective LONG_POLL_WAITERS a replacement is admitted and the same number remain; a different CN cannot free that place.

<!-- req: P/05-R153 -->

**Event hint and long poll.** A wait does not take the /events computation lane of P/06.4 N3 merge (N3 «query»); it holds its connection of the door until the answer (changed, term, full, replaced) or until the noticed departure of the client (within WAIT_DISCONNECT_WITHIN) — the «common lane» of N2 is the connection limit of the resource door («Implementation decides» item 10).

<!-- req: P/05-R250 -->

**Event hint and long poll.** In TLS the identity is the CN of the certificate plus client; another CN does not displace a wait.

<!-- req: P/05-R154 -->

**Event hint and long poll.** Without client the deployment uses a separate wait per client address; a repeat with a busy address — full.

<!-- req: P/05-R251 -->

**Event hint and long poll.** The current buckets are observed every WAIT_OBSERVE_MS / 1000 seconds while there are waiting ones; a missed hint or a write to an old bucket is made up for by the ordinary pass, not by a promise of delivery.

<!-- req: P/05-R033 -->

Paths `/mirror/{server}/{path}`, `/mirrored/{server}[/{path}]`, `/events/{path}`: `{server}` — one segment by the grammar of a server name (P/02.4 N1.2 `SERVER_NAME`); `{path}` — a bucket path of N1.2 (`<tree>/<unit>/e<epoch>/<start>Z.events.jsonl`), no segment is empty or `.`/`..`, `%2F` is not a separator, `.tmp` is not a bucket. Otherwise: `GET /mirrored/…` and `GET /events/…` — 404 without a body, `PUT /mirror/…` — 400 without a body. **Raw paths and route matching.** The resource never reads or writes a file outside its tree (`.mirror/<server>/` for copies).

<!-- req: P/05-R155 -->

**Bucket mirroring.** `PUT /mirror` of a bucket whose end by name is later than the clock of the receiver — 400: the mirror accepts only closed buckets.

<!-- req: P/05-R156 -->

**Bucket mirroring.** `PUT /mirror/<own server>/…` (a copy from itself) — accept or refuse — «Implementation decides» item 11.

<!-- req: P/05-R157 -->

**Representations and stream failures.** The value of `X-Sum` is an HTTP field: the spaces at the edges (OWS) are dropped before the check of the form.

<!-- req: P/05-R034 -->

The HTTP representations are in the schemas of N2. `BucketInfo` is the description of one bucket, not an event; `/buckets` gives UTF-8 JSON Lines: one object per LF, without an array.

<!-- req: P/05-R159 -->

**Bucket mirroring.** `/mirrored/<server>` by the canon of this lesson gives `{copies:[{path,written,size,sum}]}`. `written` of a copy is the wall seconds (N0) when the receiver published this copy at itself (the time of the copy file or its own record): `PUT /mirror` does not carry the time of the source bucket, only `X-Sum`; the bytes of the bucket do not change; a repeated reception of the same bucket with the same sum does not shift `written`.

<!-- req: P/05-R160 -->

**Bucket mirroring.** The bytes of a copy are a separate GET. The field `sum` and the header X-Sum are 64 lowercase hex digits of the SHA-256 of the whole body.

<!-- req: P/05-R162 -->

**Console-owned operations.** The form `answered` (the mark row of a request, AnsweredMark) — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.6 (the console door).

<!-- families:begin -->
### Data families (built from the standard files)

The form of the rows and objects and JSON files that the chapter owns by the [catalog](../../common/data/catalog.tsv) is the JSON Schema 2020-12 of the family. An instance of a row is `{key, row}`, of an object `{key, object}`, of a file `{key, file}` (the text of the file in UTF-8; the root of the schema is its parse, `x-encoding`); the key is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after the [codec](../../common/data/codec.tsv): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority applies.

#### `platform/doors/<host>` — row

Schema — [`doors.schema.json`](../data/doors.schema.json), outcomes — [`doors.outcomes.tsv`](../data/doors.outcomes.tsv); form version 1; norm — P/05 N1.4 door_row; the presence lock contract; P/06.6 N3 «decommission a server» (delete by the console).

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `url` | string | required |  | the address of the resource door (RESOURCE_URL) |
| `since` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the resource start |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the last mark, every ALIVE_EVERY; judged by a change of the row version, not by the value (resource_state of the observation contract) |
| `.<name>` | string | optional |  | name: `room.<sub>` — an element for each subsystem of the catalogue whose role file `roles/<sub>worker.env` is present on the box; next to it `live.<sub>`; a decimal ≥ 0 — how many more processes of the role `<sub>worker` the server will start (the presence lock contract «Count room»), or "unknown"; the reader does not refuse an element out of form at the row level: the element is absent, unreadable or unknown — the server is not a candidate for an order of this role (P/04 N3 «order()»); for `live.<sub>` — the numbers n ≥ 2 of the live locks of the role, comma-separated, ascending, without repeats, from the same snapshot as `room.<sub>`, or empty; absent or unreadable — the server is not a candidate (the presence lock contract, live) |

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `.<name> (name)` | any value; matching `(room\|live)\.[a-z][a-z0-9_-]{0,31}` in full |
| `.<name>` | matching `0\|[1-9][0-9]*\|unknown\|([2-9]\|[1-9][0-9])(,([2-9]\|[1-9][0-9]))*\|` in full |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the server is not a candidate for an order; the fields of the unreadable row are not replaced by absence, the cause goes to the log | 0 | row | P/04 N1, N3 «order()» |
| the whole row | `console` | the whole row is unreadable: the life of the resource is judged by a change of the row version (resource_state of the observation contract), not by its fields; the fields of the unreadable row are not replaced by absence; the door row of a decommissioned server is unreadable — the console pass deletes it all the same: delete with cas by the version read, the content is not needed for the deletion; the cause goes to the log | 0 | row | observation contract resource_state; P/06.6 N3 «decommission_server» |
| the whole row | `resource` | the whole row is unreadable: restore — the door is unreadable, the restoration is incomplete; mirror — there is no address, the server is not a neighbour of this pass; the fields of the unreadable row are not replaced by absence, the cause goes to the log | 0 | row | P/05 N1.4 door_row, «Bucket restore» |
| the whole row | `<s>worker` | the door row of its own server is unreadable: the object client with a bare cluster:// — reading the cluster objects is «unknown», not «no», not a start refusal and not a refusal of writing to its own catalogue; on the next access the row is read anew | 0 | row | the object store client contract door |

#### `platform/resources/<server>/heartbeat` — object

Schema — [`resource-heartbeat.schema.json`](../data/resource-heartbeat.schema.json), outcomes — [`resource-heartbeat.outcomes.tsv`](../data/resource-heartbeat.outcomes.tsv); form version 1; norm — P/05 N1.4.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `server` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | its own server — SERVER_NAME by the grammar of the environment file contract «Environment variables», as for the presence lock; not by it or not equal to the server of the key — the heartbeat is unreadable (P/06.5 N2) |
| `box` | string | optional |  | the box (BOX_ID, the environment file contract «Environment variables») |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the heartbeat; written every HEARTBEAT_EVERY (forms/runtime-constants.tsv) |
| `url` | string | required |  | the address of the resource door |
| `schema` | integer; ≥ 1; ≤ 9007199254740991; the whole sign for the reader too (x-whole) | required |  | SCHEMA of the build (P/06.6 N1.1a heartbeat): a JSON integer without a fractional part and exponent, ≥ 1; `1.0`, `1e0`, `-1`, a string, null — the process schema is unknown |
| `build` | string | required |  | the build word (BUILD); not a string — the field is unknown: null in the console's answers |
| `usage` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes of the bucket files of the trees of this server and of the copies in .mirror/ |
| `usage_at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the usage measurement |
| `space` | by the definition `disk` | required |  | the volume of the event tree |
| `volumes` | map author names: name — string, value — by the definition `disk` | required |  | the same per volume |
| `volumes.<name>` | by the definition `disk` | optional |  |  |
| `units` | map author names: name — string; matching `[a-z][a-z0-9_-]{0,31}` in full, value — list, element — string | required |  | `{<sub>: [<id>…]}`; none such — {}; in every heartbeat |
| `units.<name>` | list, element — string | optional |  | ids of the units named in status by the heartbeats of the workers of this box from running, in ascending byte order |
| `units.<name>[]` | string | optional |  |  |
| `workers` | by the definition `slot_list` | optional |  | all slots the resource knows about on its box (by the presence locks) |
| `running` | by the definition `slot_list` | optional |  | slots with a live process (it holds the presence lock) |
| `unknown` | by the definition `slot_list` | optional |  | presence could not be read |
| `instances` | map author names: name — string; matching `[^/]+/[^/]+` in full, value — string; matching `[\s\S]+` in full | optional |  | `{<sub>/<slot name>: <instance>}` |
| `instances.<name>` | string; matching `[\s\S]+` in full | optional |  |  |
| `short` | integer; ≥ 0; ≤ 9007199254740991 | required |  | how many bytes are still needed above high (P/06.5 N3 /metrics w2c_resource_short_bytes): only volumes with current used/total > high contribute; at or below high — 0, even if an own request remains unchanged in the low–high band; Σ over qualifying volumes of the largest positive need among subsystems with effective own free requests, without summing subsystems on one volume; need — by N3 relieve, rounded up to a whole byte, saturation 2^53−1; confirmed platform/space disabled, no requests, need ≤ 0 — 0; an unread pass input — the previous value unless space is independently confirmed disabled |
| `waits` | map `{waiting, held, full, replaced, max}` | required |  | counters of the /events/wait waits (N1.6); in every heartbeat |
| `waits.waiting` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.held` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.full` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.replaced` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `waits.max` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirrors` | map author names: name — string, value — integer; ≥ 0; ≤ 9007199254740991 | required |  | `{<server>: n}` — copies of neighbours in .mirror/ |
| `mirrors.<name>` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `pass_started` | time (P/01.1 N0 «Time in a row») | optional |  | the start of the current pass (N3 «resource pass») |
| `pass_stalled` | number; ≥ 0 | optional |  | seconds, only while the pass is hung (PULSE_LIMIT) |
| `volumes_stuck` | map author names: name — string, value — number | optional |  | volumes whose probe did not answer (P/06.5 ResourceRow) |
| `volumes_stuck.<name>` | number | optional |  |  |
| `door` | map `{addr, mode, cert_until?}` | required |  | the state of the resource door (P/06.5 ResourceRow DoorState); written by the resource in every heartbeat (P/05 N1.4) |
| `door.addr` | string | required |  | the address of the resource door — RESOURCE_HOST:RESOURCE_PORT |
| `door.mode` | string; one of: `loopback`, `mtls` | required |  | loopback — without RESOURCE_TLS, loopback only; mtls — RESOURCE_TLS=1, mutual TLS |
| `door.cert_until` | number | optional |  | wall-clock seconds of the expiry of the server certificate of its own set (W2C_TLS_DIR); with mtls |
| `garbled_rows` | map author names: name — string, value — integer; ≥ 0; ≤ 9007199254740991 | optional |  | unreadable rows of the tables read by the resource (holds), per table |
| `garbled_rows.<name>` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `retention_garbled` | list, at least 1 items, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  | subsystems where any term (`<sub>/retention` or `<sub>/alarms_retention`) has a wrong days (P/05 N1.3 retention rule), regardless of retention_withheld, in ascending byte order; none such — the field is absent (P/05 N3 retain, N4) |
| `retention_garbled[]` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  |  |
| `retention_withheld` | map author names: name — string; matching `[a-z][a-z0-9_-]{0,31}` in full, value — string; one of: `days_garbled`, `unknown`, `holds_unread` | optional |  | why a dependent tree of the subsystem was not cleaned up by term in this pass — a closed list: days_garbled — a wrong days, unknown — the term row was not read (the store did not answer), holds_unread — the holds were not read (the holds contract); a subsystem has one cause, in the order unknown → days_garbled → holds_unread; each tree is held by its own term; no cause — the field is absent (P/05 N3 retain, N4) |
| `retention_withheld.<name>` | string; one of: `days_garbled`, `unknown`, `holds_unread` | optional |  |  |
| `settings_unread` | list, at least 1 items, without repeats, element — one of: `mirror`, `space` | optional |  | the settings rows of the resource pass that were not read in this pass: mirror — platform/mirror (the mirror step and the body copies are not executed), space — platform/space (the relieve step is not executed); in ascending byte order; none such — the field is absent (P/05 N1.4 mirror, space, N3) |
| `settings_unread[]` | one of: `mirror`, `space` | optional |  |  |
| `restore` | map author names: name — string, value — map `{done, silent?, last_ok?, last_error?, error_at?, restored, missing, failures, lines_garbled?, next?}` | required |  | `{<neighbour>: …}` — restoring buckets from copies of neighbours (N1.4 «Bucket restore»); in every heartbeat |
| `restore.<name>` | map `{done, silent?, last_ok?, last_error?, error_at?, restored, missing, failures, lines_garbled?, next?}` | optional |  |  |
| `restore.<name>.done` | bool | required |  |  |
| `restore.<name>.silent` | bool | optional |  | current peer unavailability; optional presence is an implementation choice, not judged |
| `restore.<name>.last_ok` | number | optional |  | wall-clock seconds of the last successful peer operation; optional presence is not judged |
| `restore.<name>.last_error` | string | optional |  | reason text of the last peer error; optional presence is not judged |
| `restore.<name>.error_at` | number | optional |  | wall-clock seconds of the last peer error; optional presence is not judged |
| `restore.<name>.restored` | integer; ≥ 0; ≤ 9007199254740991 | required |  | only the buckets actually pulled from this neighbour; a bucket already lying on the volume is not counted (N1.4 «Bucket restore») |
| `restore.<name>.missing` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.failures` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.lines_garbled` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `restore.<name>.next` | number | optional |  | wall-clock seconds of the scheduled next restore attempt; optional presence is not judged |
| `mirror` | map `{skipped, failed, peer_errors, lines_garbled, sum_refused?, peer_sum_refused?, pull_sum_bad?, unsummed?}` | required |  | mirror counters (N1.4 mirror; skipped — buckets larger than the resource door limit (OpenAPI Content-Length.maximum, P/05-R014)); in every heartbeat |
| `mirror.skipped` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.failed` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.peer_errors` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.lines_garbled` | integer; ≥ 0; ≤ 9007199254740991 | required |  | an integer from 0 to 2^53 − 1 |
| `mirror.sum_refused` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.peer_sum_refused` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.pull_sum_bad` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |
| `mirror.unsummed` | integer; ≥ 0; ≤ 9007199254740991 | optional |  | an integer from 0 to 2^53 − 1 |

**`disk`**

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<disk>` | map `{total, free, used, full}` |  |  |  |
| `<disk>.total` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes (statfs) |
| `<disk>.free` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes |
| `<disk>.used` | integer; ≥ 0; ≤ 9007199254740991 | required |  | bytes |
| `<disk>.full` | number; ≥ 0; ≤ 1 | required |  | the fraction used/total from 0 to 1 (not a flag) |

**`slot_list`**

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<slot_list>` | list, element — string; matching `[^/]+/[^/]+` in full |  |  |  |
| `<slot_list>[]` | string; matching `[^/]+/[^/]+` in full | optional |  | `<sub>/<slot name>` |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| `/schema` | * | the process schema is unknown: in processes of the door /schema — schema: null; in ResourceRow of the door /resources — schema: null; the heartbeat stays readable | 0 | field | P/06.6 N1.1a heartbeat, N2.3; P/06.5 N2 «Outputs» |
| `/build` | * | build is not a string — the field is unknown: null in ResourceRow (/resources) and in processes of the door /schema, not ""; the heartbeat stays readable | 0 | field | P/06.5 N2; P/06.6 N2.3 |
| `/retention_garbled` | * | a field out of form is unknown: null in ResourceRow, not absence (the term causes are not replaced by «no causes»); the heartbeat stays readable | 0 | field | P/05 N3 retain; P/06.5 N2 |
| `/retention_withheld` | * | a field out of form is unknown: null in ResourceRow, not absence (the term causes are not replaced by «no causes»); the heartbeat stays readable | 0 | field | P/05 N3 retain; P/06.5 N2 |
| the whole object | `<s>controller` | the heartbeat is unreadable: it does not confirm the life of the resource, nor does its change (resource_state: unreachable with a fresh door row, otherwise by the order of the rules); it gives no presence of processes | 1 | row | observation contract resource_state |
| the whole object | `console` | the heartbeat is unreadable: it does not confirm the life of the resource, nor does its change (resource_state: unreachable with a fresh door row, otherwise by the order of the rules); it does not enter /resources, it is counted in w2c_resource_heartbeats_garbled, the answer is 200 | 1 | row | observation contract resource_state; P/06.5 N2 «Outputs» |
| the whole object | `resource` | the neighbour's heartbeat is unreadable: restore of the neighbour — the heartbeat is not read, the restoration is incomplete (all known doors are required) | 1 | row | P/05 N1.4 «Bucket restore» |

#### `<sub>/requests/free-<server>-<volume>` — row

Schema — [`free-ask.schema.json`](../data/free-ask.schema.json), outcomes — [`free-ask.outcomes.tsv`](../data/free-ask.outcomes.tsv); form version 1; norm — P/05 N1.4 free_ask.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `free` | number; > 0 | required |  | need = used − total·low − Σ freeing from the heartbeats, bytes; need ≤ 0 — the row is removed, not written |
| `volume` | string; matching `[A-Za-z0-9_]{1,64}` in full | required |  | the volume name of ASCII A-Z/a-z/0-9/_, 1–64 bytes, without a hyphen; on the box there is one volume — events |
| `server` | string; matching `[\s\S]+` in full | required |  | its own server — a non-empty key segment of P/01.1, hyphens allowed; matches `<server>` of the key |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the write stamp |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>worker` | a row not in the resource's form is not a request: skipped, the cause goes to the log without the value | 0 | row | P/03.6 N3 «holder's look» |
| the whole row | `console` | a resource row without a live owner is removed by ttl | 0 | row | P/06.4 N3 «reaper» |
| the whole row | `resource` | not its own form (unit present, someone else's server/volume, a spoiled form): do not touch, log free_ask.key_taken, skip | 0 | row | P/05 N1.4 free_ask, N3 «resource pass» relieve |

#### `<events root>/<sub>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-unit.schema.json`](../data/events-unit.schema.json), outcomes — [`events-unit.outcomes.tsv`](../data/events-unit.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/<sub>.alarms/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-unit-alarms.schema.json`](../data/events-unit-alarms.schema.json), outcomes — [`events-unit-alarms.outcomes.tsv`](../data/events-unit-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-audit.schema.json`](../data/events-audit.schema.json), outcomes — [`events-audit.outcomes.tsv`](../data/events-audit.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-audit-alarms.schema.json`](../data/events-audit-alarms.schema.json), outcomes — [`events-audit-alarms.outcomes.tsv`](../data/events-audit-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/console/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-console.schema.json`](../data/events-console.schema.json), outcomes — [`events-console.outcomes.tsv`](../data/events-console.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/console.alarms/<instance>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-console-alarms.schema.json`](../data/events-console-alarms.schema.json), outcomes — [`events-console-alarms.outcomes.tsv`](../data/events-console-alarms.outcomes.tsv); form version 1; norm — P/05 N1.2; the event journal contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/.mirror/<server>/<tree>/<unit>/e<epoch>/<YYYYMMDDTHHMMSSZ>.events.jsonl` — file

Schema — [`events-mirror.schema.json`](../data/events-mirror.schema.json), outcomes — [`events-mirror.outcomes.tsv`](../data/events-mirror.outcomes.tsv); form version 1; norm — P/05 N1.4 mirror.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `t` | time (P/01.1 N0 «Time in a row») | required |  | the writer's wall-clock seconds when it was written; selects the bucket (years up to 9999) |
| `kind` | string | required |  | the event kind |
| `id` | string | required |  | `e1-<hexUTF8(tree)>-<hexUTF8(unit)>-<epoch>-<hexUTF8(instance)>-<number>`; unique, duplicate copies are removed by it |
| `of` | string | optional |  | `<sub>/<id>` — the unit it is about; set by the platform from about |
| `class` | string; one of: `alarm` | optional |  | only for an alarm; not written for observation |
| `occurred` | time (P/01.1 N0 «Time in a row») | optional |  | when it happened; optional |
| `v` | integer; ≥ 1 | optional |  | the line version — an additional field: the reader tolerates it (LAYERS.md § 6), the writer does not write it — absence = version 1; a positive integer, v = 2 is preserved, there is no choice of behaviour by v (the event log contract line) |
| `.<name>` | any value | optional |  | the subsystem's words; fields beyond the form are kept by the reader as is, the writer writes the line strictly by the form |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | a full line (with LF) out of the form line — not a JSON object, no t, kind or id, the time not by the reader's codec, deeper than JSON_DEPTH (P/01.1 N2.1; the event log contract line depth): this line is skipped and counted in garbled, the bucket is read further, not a refusal of the bucket; the last fragment without LF is not a line, counted in torn | 0 | row | the event journal contract `bucket` `torn` |

#### `<events root>/.workers/<sub>/<instance>.lock` — file

Schema — [`presence-lock.schema.json`](../data/presence-lock.schema.json), outcomes — [`presence-lock.outcomes.tsv`](../data/presence-lock.outcomes.tsv); form version 1; norm — P/05 N1.4; the presence lock contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `instance` | string; not one of: `""` | required |  | the worker instance (the instance contract common/contracts/instance.md: INSTANCE_ID or `<box>:<pid>:<6 hex>`); the lock file name is the same instance in the name encoding of the event log contract |
| `sub` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | required |  | the worker's subsystem — the directory `.workers/<sub>/` of the lock |
| `worker` | string; matching `\|[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the slot name (P/03.2 N1.4) or "" — before the name is captured and while the worker searches without a name (nobody); the number n of the name `<prefix>-<server>-<n>` — for room and live (the presence lock contract «Count room») |
| `server` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the worker's server — SERVER_NAME (P/02.4 N1.2) |
| `pid` | integer; ≥ 1; ≤ 9007199254740991; the whole sign for the reader too (x-whole) | required |  | pid of the worker process — an integer ≥ 1; for display: presence is by flock, not by pid (kill(pid, 0) is not a source) |

Outcomes of an unreadable file (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole file | `resource` | the content is empty or out of form (not a JSON object, a field missing, a field out of form, an extra field): the lock is busy — a live process without a number: it enters `room.<sub>`, does not enter workers, running, `live.<sub>`; the lock is taken by the resource and the check matched — gone by the file, there is no key `<sub>/<worker>`, the file MAY be deleted; unknown — a file that cannot be read (an open or read error), and an flock or fstat/stat error, except «busy» and ENOENT at stat, not its content | 0 | row | the presence lock contract «Lock», «Count room»; P/05 N1.4 workers, room |

#### `.gone/<object-key>` — object

Schema — [`gone.schema.json`](../data/gone.schema.json), outcomes — [`gone.outcomes.tsv`](../data/gone.outcomes.tsv); form version 1; norm — P/05 N1.1 «Tombstones»; P/06.1 N3 «body cleanup»; the tombstone contract.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `written` | time (P/01.1 N0 «Time in a row») | required |  | the moment the body was deleted at the deleter |
| `peers` | list, element — string; matching `[\s\S]+` in full | required |  | neighbours of the ring that could have had a copy of the body |
| `peers[]` | string; matching `[\s\S]+` in full | optional |  |  |
| `acked` | list, element — string; matching `[\s\S]+` in full | required |  | neighbours from `peers` that confirmed the deletion (404 on GET of the copy) |
| `acked[]` | string; matching `[\s\S]+` in full | optional |  |  |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `resource` | the whole object is unreadable: the neighbour does not drop the copy, the deleter does not append confirmations and does not remove the tombstone — an unknown outcome is not a confirmation (the tombstones contract garbled); the cause goes to the pass log | 0 | row | P/05 N1.1 «Tombstones» |
<!-- families:end -->

---

## N2 Doors

<!-- req: P/05-R035 -->

The full contract: [OpenAPI](05-resource.api.openapi.yaml).

<!-- req: P/05-R163 -->

**Independent size and time limits.** The object byte ceiling does not cap GET `/events/{path}`: it returns the whole bucket up to the size fixed for that read, subject to the common production budgets. GET of an object is limited to the resource door byte limit (OpenAPI Content-Length.maximum) by the bytes actually read: exactly the limit is allowed, +1 byte — 413 ResourceError before the success headers; until the size is confirmed the body is buffered within bounds or checked against an immutable object with a reliable size. The ceiling of the store itself can be higher and does not cancel this limit of the door. It distinguishes the resource and the console, JSON answers, a byte stream and the absence of a body.

<!-- req: P/05-R165 -->

**Representations and stream failures.** The schemas set the required fields and the allowed extensions; the checks of existence, rights, UTF-8 size and state are performed separately. An outer array does not replace JSON Lines.

<!-- req: P/05-R036 -->

| Input | Success | Application refusals |
|---|---|---|
| resource GET /v1/objects | 200 ObjectListing | 400 ResourceError; 403 ResourceError or ResourceDenied; 503 ResourceError |
| resource GET /v1/objects/{key} | 200 bytes; X-Written, X-Server, X-Missing when needed | 400/403/404/413/503 ResourceError |
| resource PUT /v1/objects/{non-blob} | none | 405 ResourceError; key/scope — 400 |
| resource GET /buckets/{sub}/{unit} | 200 JSON Lines of BucketInfo | 404/500 without a body |
| resource GET /events | 200 ResourceEvents; at the resource `HEAD` — 405 | resource 400 ResourceError (the parsing below); resource 503 ResourceError |
| resource GET /events/wait | 200 WaitAnswer, including full/replaced | 400 ResourceError; the common lane is busy — 503 ResourceError |
| resource GET /events/{path} | 200 whole bytes + X-Sum; 206 one range + Content-Range | 404/500 without a body; 416 text/plain + Content-Range |
| resource PUT /mirror/{server}/{path} | 204 without a body; the header `X-Sum` — SHA-256 of the body (64 lowercase hex), required; 204 confirms that the verified copy and the metadata it needs survive a failure within the declared fault model, the barriers are chosen by the implementation | no `X-Sum` or it is not in form — 400, the body is not accepted; the SHA-256 of the body does not match — 422; 408/413/500 — without a body |
| resource GET /mirrored/{server} | 200 MirroredListing | 404/500 without a body |
| resource GET /mirrored/{server}/{path} | 200 bytes + X-Sum | 404/500 without a body |
| resource `PUT /v1/objects/<sub>/blobs/<digest>` | 204 without a body. Required are a length ≤the resource door byte limit (OpenAPI Content-Length.maximum), `X-Written` — a non-negative time of the source copy (absent or not a number — 400), a sha256 name with 64 lowercase hex; bytes of another digest — 422; a key not of the blob form or a subsystem without a blob field — 405, as for any object (N1.1 «Bodies at the resource» `mirror`). On reading the actual limit/sum are checked | 400/404/405/408/409/411/413/422/503 — `ResourceError`, 403 — it or `ResourceDenied`. The common refusals of the console do not apply here |

<!-- req: P/05-R311 -->

**One byte range.** For a single range of `GET /events/{path}`, clamp an end beyond the fixed file size to size−1. A start at or beyond size, start greater than end, and any suffix range of an empty file give 416 with `Content-Range: bytes */size`. A positive suffix longer than a nonempty file gives the whole file as 206. Forms outside the declared single-range profile, including a malformed or multiple Range and conditional requests, are implementation choices and are not judged; no new mandatory refusal is assigned to them.

<!-- req: P/05-R037 -->

`GET /events` of the console (the merge, ConsoleEvents, `HEAD`) and the console doors `POST /marks`, `POST /{sub}/requests`, `DELETE /{sub}/asked/{sha16}` — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N2; the schemas of the answer of `/events` common to both doors (`EventRow`, `UnitRef` and below) are in the contract of this lesson.

<!-- req: P/05-R038 -->

For both listings (`/buckets/{sub}/{unit}` and `/mirrored/{server}`) all the necessary reads of the directory/metadata complete before the success headers: unknownness/an error — 500 without a body, not 404 and not an empty 200. It is an observed listing, not a snapshot of several files. A readable existing empty copies directory gives 200 `{copies:[]}`; an absent copies directory gives 404. Both complete the peer with no copies on restore.

<!-- req: P/05-R166 -->

**Representations and stream failures.** A break of an already started transfer of a listing is not a full answer; a new HTTP status is not sent after the headers.

<!-- req: P/05-R039 -->

**`scope`** Of `/v1/objects` and `/v1/objects/{key}`: `local` (the default) — only the objects directory of this server; `cluster` — the cluster objects by N1.1 `cluster` (the fresh copy by `written` wins, a server that did not answer is `missing`); another value — 400 (N4). The resource is the read door of the cluster objects for the processes of its own server (N1.4 «Cluster objects — through the resource of its own server»).

<!-- req: P/05-R304 -->

**Cluster reads and missing answers.** For `scope=cluster`, poll the local server and all foreign servers of a confirmed `platform/doors` listing; do not filter them by door-row liveness. A known server that does not answer or whose door is unreadable is `missing`. With a known poll set, a listing returns 200 with `missing` for those servers; a key read returns its ordinary result with `X-Missing` when the poll is incomplete. An unconfirmed door set or a failed local read/listing gives the existing 503 ResourceError, not a complete listing. The poll has a finite dependency deadline declared by the implementation under the common production obligations; its numeric value is not fixed by this lesson.

<!-- req: P/05-R040 -->

ResourceError is only `{error: text}`.

<!-- req: P/05-R167 -->

**Object door admission.** A refusal 404 on reading an object means «not among those who answered»; with an incomplete poll X-Missing is required, completeness is not derived from the code 404 itself.

<!-- req: P/05-R041 -->

**Query parsing.** The resource door — by P/01.1 N2.1 (query, the path byte for byte, HTTP by RFC 9112, an early refusal) with deviations: a refusal of query parsing — 400 ResourceError `{error}`. **Raw paths and route matching.** an empty or repeated parameter — 400, except an empty `prefix` of the object listing (200).

<!-- req: P/05-R280 -->

**Raw paths and route matching.** no path and an unsupported method — 404/405 without a body, including `OPTIONS`, `POST /events`, `PUT /v1/objects` (the listing), `GET`/`POST`/`DELETE` on `/mirror/…`. `PUT /v1/objects/{non-blob}` — the application 405 ResourceError (N4).

<!-- req: P/05-R282 -->

**Raw paths and route matching.** `/buckets/{sub}/{unit}` uses the Subsystem grammar without a dot: `testsub.alarms` gives 404 without a body, without normalization; alarm events remain available through the query and a known bucket path. It has exactly two non-empty segments, `/buckets/testsub/`, `/buckets/../objects`, `/buckets/testsub%2Fc1` — 404 without a body.

<!-- req: P/05-R283 -->

**Representations and stream failures.** the bodies of `PUT` are bytes, JSON is not parsed.

<!-- req: P/05-R168 -->

**Raw paths and route matching.** The shared P/01.1 R050 drain counts raw HTTP-stream bytes and its absolute monotonic interval starts after the complete refusal has been sent; chunked discard does not wait for a terminal chunk. This parsing reference does not replace the resource's own timeout outcomes or budgets with P/01 input-phase refusals, and adds no common response deadline to resource streams.

<!-- req: P/05-R042 -->

ResourceDenied (`error=refused`, detail, role on a refusal of the role) — 403 of the resource gateway, before the route handler.

<!-- req: P/05-R169 -->

**Raw paths and route matching.** A TLS refusal before HTTP does not get an invented HTTP body. Every applicable common answer is entered in the OpenAPI.

<!-- req: P/05-R170 -->

**Raw paths and route matching.** With busy — Retry-After: 1.

<!-- req: P/05-R171 -->

**Raw paths and route matching.** On an unknown path — 404; on an unsupported method of a known path — 405; at the resource both are without a body. This common rule is enough: it does not create a separate OpenAPI method for every impossible operation.

<!-- req: P/05-R057 -->

**Route matching form.** The OpenAPI path item has a unique integer `x-route-priority`: smaller is earlier.

<!-- req: P/05-R288 -->

**Raw paths and route matching.** Match the raw path exactly, with no percent-decoding of literals, path normalization or implicit trailing slash. A path parameter declares `x-path-capture` (`segment` or `remainder`, only at the end) and `x-path-decode: percent-segment`. Capture the raw remainder including an empty tail and empty inner segments; decode each captured segment separately. A decoded slash does not create a separator and is invalid. Empty or other out-of-form values are parameter errors of the selected operation, not a fallback to another route.

<!-- req: P/05-R293 -->

**Raw paths and route matching.** First filter the structurally matching templates by the HTTP method, then select their lowest priority; only when no such method exists is the answer the common bodyless 405 (no matching template: bodyless 404).

<!-- req: P/05-R294 -->

**Raw paths and route matching.** The parameter’s `x-path-error` maps each applicable HTTP method to `{status, response_schema}`: the existing OpenAPI component name or `-` for no body.

<!-- req: P/05-R295 -->

**Raw paths and route matching.** In particular the generic objects GET remains available for a blob-shaped key when the specific blob route has only PUT.

<!-- req: P/05-R296 -->

**Raw paths and route matching.** The exact priorities, capture mode and refusal projections are the OpenAPI form, not a second route list in prose.

<!-- req: P/05-R297 -->

**Raw paths and route matching.** Schema refusal and decoding refusal do not normalize a foreign or invalid key into a file path.

<!-- req: P/05-R298 -->

**Representations and stream failures.** Error text inside ResourceError remains a non-empty diagnostic, not a new fixed error word.

<!-- req: P/05-R043 -->

**Admission to the resource doors**. The resource with TLS checks the client: the chain up to the authority, the serial number not in `revoked` ([the role certificate contract](../../common/contracts/role-certificate.md) `revoke`), exactly one role of the route row, CN = `<role>.<SAN DNS>`; otherwise a refusal of the handshake or 403 `ResourceDenied` with the role and the route.

<!-- req: P/05-R172 -->

**TLS and role admission.** The client checks the role `resource` and the SAN DNS of the server against the host of the address; an IP with TLS — a refusal of the client.

<!-- req: P/05-R044 -->

For door mode `mtls`, the per-operation role table is [forms/door-roles.tsv](../forms/door-roles.tsv), with the paths and methods of the OpenAPI. **TLS and role admission.** `<sub>worker` expands only over the loaded manifest catalogue; `*` means any authenticated kit role. The role check precedes the matched operation handler; the TLS checks above remain mandatory.

<!-- req: P/05-R286 -->

**TLS and role admission.** The loopback mode keeps the admission of the role certificate contract. This does not admit unknown paths or methods.

<!-- req: P/05-R045 -->

**Profile limits.** A bucket file is read whole or by one Range; multiple Ranges and conditional HTTP requests are not part of the lesson.

<!-- req: P/05-R173 -->

**Representations and stream failures.** The size of the answer is fixed before reading; the answer does not promise a snapshot of the whole tree.

<!-- req: P/05-R174 -->

**Representations and stream failures.** After the output has started, a break of the stream does not turn into a second HTTP status: the caller does not accept incomplete bytes as a whole copy.

<!-- req: P/05-R175 -->

**Bucket mirroring.** The mirror reception is limited by the resource door byte limit (OpenAPI Content-Length.maximum) and by the read term declared by the deployment; exceeding the size — 413, the term — 408.

<!-- req: P/05-R314 -->

**Bucket mirroring.** `PUT /mirror/{server}/{path}` accepts a correctly framed chunked body without Content-Length, with the same full-body, checksum, receive-term and actual byte-limit checks. Actual bytes above the limit give the existing 413 and a cut-off body gives the existing 400, without publishing a new copy; no 411 is assigned to this route. If Content-Length is present and above the limit, refuse before reading the body as usual.

<!-- req: P/05-R176 -->

**Body copies.** `PUT /v1/objects/<sub>/blobs/<digest>` is the body copy of a neighbour (the table above; N1.1 «Bodies at the resource»); `PUT /<rows>/<id>/<blob_field>` belongs wholly to [P/06.1](../../06-console/spec/06.1-console.norms.md) N2 (the bytes door of the console); other objects the resource door does not write — a refusal of the write of a non-blob, there is no partial copy of the blobs contract.

---

## N3 Procedures

### resource start — schema check

<!-- req: P/05-R046 -->

The process input inventory is [forms/daemon-flags.tsv](../forms/daemon-flags.tsv); derived defaults and imported validation remain the linked rules. It introduces no CLI flags.

<!-- req: P/05-R047 -->

The resource side of the common block [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «console start — schema check»; the row `platform/schema` and its raising — P/06.6 N1.1a; the other processes — P/06.6, P/03.2, P/04. The order of the resource start — [life cycle](../lifecycle.md).

<!-- req: P/05-R048 -->

As its first startup step, before reading the manifest (P/02.3), the resource performs «Check at start» of [the schema contract](../../common/contracts/schema.md).

### write an event (the platform, by observe of the subsystem)

<!-- req: P/05-R049 -->

The steps of writing a line (the class, `of`, suppression, the bucket by `t`, appending and `fsync`) and their «Races» — [the event log contract](../../common/contracts/event-journal.md) «Writing a line» (the lesson is the owner of the contract). The refusals of the write — N4.

### query (resource) → {events, state, truncated}

<!-- req: P/05-R050 -->

Execute the following steps in their listed order: P/05-R093, P/05-R094, P/05-R095, P/05-R096, P/05-R097, P/05-R098.

<!-- req: P/05-R093 -->

**Step 1.** Check the parameters (N1.3)                                         → 400 (ResourceError at the resource, ConsoleRefusal at the console).

<!-- req: P/05-R094 -->

**Step 2.** Candidates: a window ≤ QUERY_NAMED_BUCKET_LIMIT buckets — names by time; wider — a listing of the directory; if a bound cannot be represented by a calendar name — a listing, without an overflow; the threshold only selects candidate search, never a query horizon or a result cap; both trees of the subsystem (and .alarms); the copies .mirror/*: the same bucket is a duplicate, it answers under the name of the owner.

<!-- req: P/05-R095 -->

**Step 3.** Read the files from the place of the last read (a cache by size/mtime/inode); a torn line — skip it (partial); an unreadable line or a file not in its place — skip it and count it in lines_garbled (N1.3), the answer is not 503.

<!-- req: P/05-R096 -->

**Step 4.** Filter: kind, subsystem, unit — the logical reference `<tree>`/`<unit>`, for a line of the tree .alarms — without the suffix (and the lines with of = unit; a parameter with the suffix .alarms — the form UnitRef allows it — is not normalized and matches no line: 200 without matches), class, the window from ≤ t < to (or likewise by occurred: buckets up to to + late, the event log merge contract `by`).

<!-- req: P/05-R097 -->

**Step 5.** `epoch_is` and fenced the resource does not set: they are set by the merger (the event log merge contract); the resource needs no rights to `<sub>`/epoch/*.

<!-- req: P/05-R098 -->

**Step 6.** Remove the id duplicates, order and take the first limit by cut (the event log merge contract); truncated = the number of candidates after deduplication minus the number given → the lines of N1.3.

<!-- req: P/05-R305 -->

**Event query and merge.** If separate files contain readable lines with the same `id` but differing contents, the implementation chooses which contents survive; acceptance does not judge that choice. It still returns at most one line per `id` and satisfies the ordinary filter, order and cache-correctness rules. Within one bucket the existing first-line rule of the event journal contract still applies. This freedom does not permit a conforming writer to reuse an id or a copy to change its source line.

<!-- req: P/05-R299 -->

**Event query and merge.** The resource answers `503 busy` with `Retry-After: 1` when the number of simultaneously computed `/events` requests exceeds the P/06.4 N3 merge lane bound. Only requests being computed now count; a held `/events/wait` does not take this lane.

<!-- req: P/05-R051 -->

**Races.** Reading an open bucket during appending: only whole lines are given, a torn one is not given and the answer carries `partial: true` (`truncated` is a number, N1); a listing does not fix the content of the files: a file that has vanished does not confirm an empty bucket.

<!-- req: P/05-R177 -->

**Event query and merge.** A read error of a file or a directory is not given as a full answer; after the HTTP stream has started — a break, before it — 503 ResourceError. An unreadable line is not a read error: it is skipped and counted (N1.3, P/01.1 N0 «Stability of output»).

### resource pass — at start, then every PASS_EVERY from the end of the pass

<!-- req: P/05-R052 -->

The first pass is right after readiness (the door row is written), not after PASS_EVERY: the reconciliation after a restart and the edges of `free_ask` do not wait for PASS_EVERY; the next one is PASS_EVERY after the end of the previous one.

<!-- req: P/05-R312 -->

**Readiness and restore.** After the start checks, start the separate restore attempt and publish the door without waiting for restore done. Heartbeat and HTTP service continue while restore is incomplete. The first resource pass starts after readiness under P/05-R052 and does not wait for restore done; how these activities are executed internally remains an implementation choice.

<!-- req: P/05-R053 -->

Execute the following steps in their listed order: P/05-R234, P/05-R100, P/05-R101, P/05-R102.

<!-- req: P/05-R234 -->

**`retain`.** For each tree: days = `<sub>`/retention | the default (tree.alarms — alarms_retention | the default; audit, console — the default; the defaults — the event log contract «Retention of a tree»). **Retention and holds.** `days` is not a number or ≤ 0 or the row did not answer → not known: remove nothing, name it in the heartbeat — a wrong days: `<sub>` in retention_garbled and retention_withheld[`<sub>`] = days_garbled; the row did not answer — retention_withheld[`<sub>`] = unknown; the holds are not read (the holds contract) — retention_withheld[`<sub>`] = holds_unread. Each tree is kept by its own term (`<sub>` — retention, `<sub>`.alarms — alarms_retention); retention_withheld[`<sub>`] — one reason selected by [decision-order.tsv](../forms/decision-order.tsv), procedure `retention`; retention_garbled — a `<sub>` for which any term (retention or alarms_retention) is wrong, regardless of retention_withheld. Apply the inclusive deadline now >= written + seconds of N1.3 retention, only to closed buckets (the console marks — not earlier than the longest; holds keep — also the buckets of the units of other subsystems whose about names the held one, and the buckets of unknown units; what a row holds, the window, an incomplete declaration and unreadable rows — the holds contract common/contracts/holds.md, P/06.4 N1.5; the mirror copies — the tree term plus MIRROR_RETENTION_EXTRA); the journal events.removed; index.forget.

<!-- req: P/05-R100 -->

**`usage`.** Measure the volumes (a probe ≤ VOLUME_PROBE_WITHIN); the heartbeat space/volumes.

<!-- req: P/05-R313 -->

**Unread volume input.** If the current volume probe fails or exceeds VOLUME_PROBE_WITHIN, do not substitute a former used/total measurement in relieve. Do not write or remove the free requests whose need depends on that unread measurement; keep the former `short` for an unread pass input. Independent steps still run; a confirmed `platform/space.enabled=false` still removes own requests and sets `short=0` without computing need. Use the existing `volumes_stuck`/journal diagnostics, not a new `settings_unread` value.

<!-- req: P/05-R101 -->

**`relieve`.** `platform/space.enabled` ∧ used/total > high → for manifests with requests.free: need = used − total·low − Σ freeing (Σ — over the live heartbeats of the workers of this subsystem on this server, freeing.`<volume>` of this volume; N1.4 free_ask). **Space and free requests.** `platform/space` does not read — the step is not executed (N1.4 space). A heartbeat of a worker of this subsystem on this server does not read — the need of this subsystem is not computed, the step neither writes nor removes its row free-*, the reason goes to the journal.

<!-- req: P/05-R238 -->

**Space and free requests.** `need` > 0 → write free-`<server>`-`<volume>` {free: need, volume, server, at}: cas "" or cas by the version of a row of ITS OWN form (without unit AND with the exact server/volume of the current volume); before the write check the grammar of N1.4 `free_ask`. Under this key a row with unit, another's server/volume or a spoiled form → do not touch it, the journal free_ask.key_taken, skip.

<!-- req: P/05-R240 -->

**Space and free requests.** `need` ≤ 0 (all that is needed is already being freed) or below low → delete the row of its own form if there is one: delete with cas of the version on which the absence of unit AND the exact match of server/volume were checked (P/01.1). `conflict` — under the key there is already another row (an ordinary request or a new own one) → do not touch it, the journal free_ask.key_taken.

<!-- req: P/05-R102 -->

**`mirror`.** `platform/mirror` does not read → the step is not executed, settings_unread: mirror (N1.4 mirror); platform/mirror.enabled → the neighbours = the next copies live ones by name (liveness — the door row, N1.4 mirror); the closed buckets that the neighbour does not have (the sum) → PUT /mirror/`<me>`/`<path>` with X-Sum = SHA-256 of the bucket; PEER_FAILS consecutive failures → the neighbour is skipped until the end of this mirror pass.

<!-- req: P/05-R242 -->

**Resource pass and stalled steps.** Each step is its own attempt; a step running longer than PULSE_LIMIT → pass_stalled in every heartbeat while it runs.

<!-- req: P/05-R054 -->

**Races.** In one pass retain precedes mirror; this is not a lock against another read/cleanup.

<!-- req: P/05-R179 -->

**Bucket mirroring.** Only a whole closed bucket with a checked sum is copied; a disappearance/an incomplete read gives a failed attempt, without the publication of a partial copy.

<!-- req: P/05-R180 -->

**Bucket mirroring.** The next pass lists the available buckets anew.

<!-- req: P/05-R181 -->

**Bucket mirroring.** The owner and the copy: a copy is never a source while the owner answers; `restore` (N1.4 «Bucket restore») pulls copies back only at the word of the owner.

<!-- req: P/05-R182 -->

**Space and free requests.** The removal of `free_ask` and an ordinary request under the same key: the resource checked the form at the version v and stopped; the reaper removed its old row by ttl, the console accepted an ordinary request with the same rid — the key has the version v′; `delete` with cas v answers conflict, the accepted request is intact; without cas it would have been deleted without an outcome.

---

## N4 Refusals

<!-- req: P/05-R055 -->

The refusals of the console doors, of requests, marks and the reaper — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N4 (the holder side — chapter 3.6); the refusals of loading `suppress` — chapter 3.6, `older_epochs` — chapter 6.4.

<!-- req: P/05-R056 -->

The closed catalogue is [forms/refusals.tsv](../forms/refusals.tsv), `chapter = 5`. It preserves the four original cells in `cause`, `outcome`, `diagnostic`, `caller`; multiple fixed HTTP projections keep the same source `row`. `response_schema` is the OpenAPI component or `-` for a bodyless/text result; no error discriminator is invented. The original Range/hint/skipped-line success outcomes remain success outcomes.

---

## N5 Acceptance

Acceptance: 35 independent scenarios, 304 steps — the objects door, the event query, the resource paths, the door row of the server and the presence lock, and the body copy at the resource. Each gets
an empty store, objects and events, all except `10-body-copy` also a new console (the scenario `10-body-copy` needs no console and no
controller); the resource srv-a ([the common acceptance README](../../common/acceptance/README.md),
«Resource») is ready before the first step, for `09-resource-door`, `10-body-copy`, `16-presence-lock`, 17–28, 31 and 37–41 a step of the scenario starts it (`@start resource`; for 31 also the resource `srv-b`); the worker `w-1` — only for `16-presence-lock`, `19-service-names`, 42 and 43, the workers of `testsub2` — for `20-door-room` and 24–28, the controller — for 42. The installed manifest
`testsub` (for `10-body-copy`, `20-door-room`, `23-object-ceiling`, 24–31, 37–41, 44 and 45 — the catalogue `testsub` and `testsub2`) is part of the preparation, not user data.

The governing rules and the public acceptance scope are in this chapter.

The existing synchronous ports separately establish completed relieve, query candidate/calendar fallback and independent peer-retry boundaries. A process pass_started mark plus a fixed sleep does not prove completion of relieve; an early process observation remains early. A seam declaration is not implementation execution. Detailed witness inputs and addresses are judge-only coverage.

TSV observes only the listed steps. The other evidence is listed separately
in the acceptance README: the writing/reading of buckets and the real fsync barriers, retention/holds, the mirror and a stream with a break, free_ask
(the computation of `relieve` with the answer of the workers `freeing` — [vectors](../vectors/relieve/README.md); the VMS request freeing),
the waits wait `full`/`replaced`, `restore` and tombstones on two resources. Reading the specification
checks the consistency of the order; reading the implementation — the corresponding branches and operations;
neither replaces the execution of timers, TLS, fsync, streams and failures on a stand.

---

## Implementation decides

An implementation is to name in its description:

1. **the object store on the box and in the cluster** — the layout on disk (directories, the delete tombstones `.gone/<object-key>` — the tombstone contract) and the size limits; the address `OBJECTS` and the access of the client — [the object store client contract](../../common/contracts/object-client.md). The stand observes whole-object reads, the selected `written`/server and `missing` under P/05-R062, P/05-R105 and P/05-R167; a write above the declared store limit gives `TooLarge` under P/05-R014.
2. ~~**how the resource learns the presence of processes**~~ — normed: [the presence lock contract](../../common/contracts/presence-lock.md) `presence_lock`;
3. **the eviction policy of the index cache** within INDEX_CACHE_BYTES (N1.3); the number of merge lanes and the term are a norm of [P/06.4](../../06-console/spec/06.4-console.norms.md) N3 «merge», not a choice. With unchanged files the stand observes the same complete query answer before and after eviction under P/05-R067.
4. **the long poll `/events/wait`**: the structure of the memory of observations and the deployable limit of waits; the forms of want/the answer and the profile of the timeout are N1.6, not a choice. The stand uses the declared effective limit and observes the closed answers, replacement before capacity and release on disconnect under P/05-R032, P/05-R152 and P/05-R153.
5. **the journal line**: the fields beyond `sub`/`target`/`addr` of the event log contract `journal`, the writer role, the epoch of the tree (`e1`). The stand reads the line through the event query and checks the required platform fields and the journal path under P/05-R018 and P/05-R049; additional fields do not replace them.
6. **streams and the reading of a body**: the term of the mirror reception, the way to check the whole body before publication, the distinction of a refusal before the headers and a break after them (the limits and terms of the POST of the console — [chapter 6.4](../../06-console/spec/06.4-console.norms.md) «Implementation decides» item 3). When reception exceeds the declared read term the stand observes the existing 408; an incomplete or wrong-sum body publishes no new copy and keeps the former one, and a started output breaks without a second status under P/05-R175, P/05-R179 and P/05-R174.
7. **PULSE_LIMIT** of the resource: a finite positive number of seconds from the declared profile, unchanged for the duration of a run; N1.4 sets the measurement and the outcome, not a particular number.
8. **the commands to write and to spoil an object** for acceptance (`@put object <key> <file>`, `@spoil object <key>` of the vocabulary of the «Stand»): an object with the bytes of the file; after spoiling, the read of the object is unreadable: the bytes of the object are spoiled, not its file or directory — the door gives the object as it is (N1.1 `door`), the reader counts it as garbled.
9. **the internal contract of a local object**: the bytes of the object file on disk (the families `heartbeats`, `contenders` and other
   objects of N1.1) are the implementation's own, not a public contract; what is observed is the norm (N1.1 «whole or nothing», N4 «object:
   the copy/listing does not read» — 503). The description and the API of the library are written in the repository of the implementation by the owner of this lesson before the
   code; the worker and the other writers of the families read only the contract and the API; a mix of languages in one box is not supported. The stand does not decode that internal file format: it observes whole-object publication and the existing 503 on an unreadable copy/listing under P/05-R066 and P/05-R056.
10. **the connection limit of the resource door** (the «common lane» of N2) for all routes: no less than DOOR_CONNECTIONS_MIN at once and DOOR_PER_ADDRESS_MIN per address (no less than
   LONG_POLL_WAITERS + the P/06.4 merge lane count with a margin, so that full and busy are reachable); beyond it — 503 busy, Retry-After: 1.
11. **`PUT /mirror/<own server>/…`** — a copy of its own bucket from itself: accept it (a copy in `.mirror/<own server>/`) or refuse
   (400 without a body); a copy from itself breaks nothing (a copy is never a source while the owner answers, N1.4 `mirror`),
   acceptance does not check it.

---

## Readiness checklist

An implementation conforms to the lesson when every norm is fulfilled:

- [ ] **P/05-01** [test, reading] the object of N1.1: whole or nothing, a writer per directory, create-once, the platform families are closed; one encoding of names ([the event log contract](../../common/contracts/event-journal.md) «File names in shared trees»: `%XX`, `%h<sha256>`; the threshold of `%h` — by the full file name: the component, the suffix of the norm, `TEMP_RESERVE` 16 bytes — checked by reading) — sc. 03 step 10 [of the acceptance of chapter 6.4](../../06-console/acceptance/4/README.md) (judge-only: file-name check of P/05-R009) (`:` of the console instance), the rest — by reading the contract/README; the presence lock ([the presence lock contract](../../common/contracts/presence-lock.md)) — sc. 16, sc. 12 [of the acceptance of P/04](../../04-controller/acceptance/README.md) (judge-only: presence check of P/05-R025); row objects for `objects.rows` and `commands/*` — sc. 29 (`testsub2/marks/*`, `commands/*` of both subsystems); sc. 05 [of the acceptance of chapter 3.6](../../03-worker/acceptance/6/README.md) (judge-only: row-object check of P/05-R006); checked by reading
- [ ] **P/05-02** [test, reading] the objects door of N2: the families `PLATFORM_DOOR`, the codes — sc. 01; the fresh copy, an equal `written` — the greater server, `missing`, `X-Missing` at 404 — sc. 31; `objects.door` of the manifest (`testsub2/tickets/*`; for a manifest without `objects` — 403) — sc. 44; the tombstones `.gone/` — read only (the listing `prefix=.gone/`, the body, `PUT` — 405) — sc. 45; spoiling the bytes of an object — the door gives it as it is — sc. 43; the listing is a filter, `*` is a subsystem of the catalogue, the grammar of the key and the parameters, `OPTIONS` — sc. 01; the case of the key — sc. 05 step 13 [of the acceptance of chapter 3.6](../../03-worker/acceptance/6/README.md) (judge-only: key-case check of P/05-R008); the service names with `~` outside the listing and not a key ([the event log contract](../../common/contracts/event-journal.md) «File names in shared trees»): the directory lock `~lock` — sc. 19; the temporary name of the writer — by the same rule of traversal, checked by reading (the stand does not stop a write between temp and rename)
- [ ] **P/05-03** [test, reading] the event line (the event log contract «The line and the bucket»): `t`, `kind`, `id`, `of` of the platform, `class` only for an alarm, without `v` — sc. 03 of the acceptance of chapter 6.4; checked by reading
- [ ] **P/05-04** [test, reading] the bucket by `t`, the bucket period of the event journal contract, the epoch in the path, the alarm tree, `fsync` of alarms and of the journal (the event log contract) — checked by reading; a torn line — sc. 22 (reading by the index)
- [ ] **P/05-05** [test, reading] the index: one per resource, without rebuild, the cache does not affect correctness; the query of N1.3 with `epoch_is`, the cut and `truncated` — sc. 02; sc. 03 of the acceptance of chapter 6.4; an id duplicate, the order `cut`, `keep`, `by=occurred`, `late`, `truncated` after deduplication, `HEAD /events` — 405 — sc. 35; `/events/{path}` 200 with `X-Sum`, 206 and 416 with `Content-Range`, `/buckets` of an unknown unit — 404 — sc. 36; the grammar of the parameters — sc. 02; the journal without `requests.journal`, BucketInfo JSON Lines, Range — sc. 04 of the acceptance of chapter 6.4; an unreadable bucket line and a file not in its place — 200 and `lines_garbled` (P/01.1 N0 «Stability of output») (sc. 08 steps 12–14); a torn tail — `partial: true`, not in `events`/`truncated`, not `lines_garbled` — sc. 22; the class from the line's class field, absence means observation; .alarms selects writer layout and retention, never overrides class, `subsystem` and `unit` of alarms without the suffix, `unit` with `.alarms` — 200 without matches — sc. 34
- [ ] **P/05-06** [test, reading] the term per subsystem: 365/1095, «not known» — do not remove, the floor of the marks, holds, the journal `events.removed` — checked by reading; the reasons in the heartbeat: a wrong `days` in `retention` and `alarms_retention` — `retention_garbled`, `retention_withheld: days_garbled` — sc. 37; a hold row without a readable window — `garbled_rows` — sc. 38
- [ ] **P/05-07** [test, reading, stand] the resource of N1.4: the heartbeat every HEARTBEAT_EVERY, the door row, its `room.<sub>` and `live.<sub>` (the numbers n ≥ 2 of the live locks) by the live locks (the presence lock contract «Count room»); the lock: the flock of the resource without waiting, ENOENT of stat — a mismatch, the delete of gone only after a matched comparison — checked by reading: a test with the worker stopped between open and flock; the content of the lock by the family presence-lock: empty or out of form at a busy one — a live one without a number (in `room.<sub>`, not in `workers`, `running`, `live.<sub>`), `unknown` — only an unreadable file — checked by reading; the pass every PASS_EVERY in the order of N3, `pass_stalled` — checked by reading; the field `door {addr, mode: loopback | mtls, cert_until}` in the heartbeat — sc. 20 (`cert_until` with mtls — checked by reading); `room.<sub>` and `live.<sub>` by the live locks: without workers, the number n ≥ 2, the base n = 1, a name without a number — sc. 20; the heartbeat fields `units`, `waits`, `restore`, `mirror` — sc. 05 step 12 of the acceptance of chapter 3.6; `units` of two units in ascending order of bytes — sc. 42; an unreadable worker heartbeat does not enter `units` — checked by reading; `mirrors` — sc. 33; `settings_unread` — sc. 39
- [ ] **P/05-08** [test, reading] the disk marks by shares (no row `platform/space` — enabled with the high/low defaults of the P/02 space form — checked by reading; disabled — its own row is removed, `short` 0 — sc. 40; between low and high with need > 0 it stands — early sc. 41 observation and the completed synchronous s63-free-ask-band-completed; the row does not read — `relieve` is not executed — sc. 39), the request `free-*` by the formula, the write with `cas` by the version of its own form, the removal under the mark only by `delete` with `cas` of the checked version (conflict — do not touch); volume without a hyphen by N1.4 `free_ask`, a row with `unit` or another's server/volume under its own key is not touched — the journal `free_ask.key_taken` (its own row and `short`, four edges of a foreign form — sc. 24–28); nobody executes or marks it; the resource itself deletes nothing except buckets — checked by reading
- [ ] **P/05-09** [test, reading, stand] the mirror: the neighbours by name and liveness by the door row (the bound — the vector `fresh-age`), closed buckets, a copy is not a source, the limits, `mirror.skipped` — checked by reading; the paths `/mirror`, `/mirrored`, `/events/{path}`, `/buckets` (`..`, `%2F`, another's tree) and the methods — sc. 08; the reception of a copy: an open bucket (a window in the future), no `X-Sum` or not in form — 400, the sum — 422 without a copy — sc. 32; 204, the listing `/mirrored`, a repeat does not shift `written`, the bytes with `X-Sum` — sc. 33; OWS of `X-Sum`, the copying of buckets on two resources — checked by reading (a bucket closes by the event journal span)
- [ ] **P/05-10** [test, reading, stand] `/events/wait` — the hint of N1.6: the forms `{changed: false, seq}` by the term and `{changed: true, seq, touched}`, `since=0` with lines under `want`, a monotonic `seq`, the cursor `since=seq` — sc. 21; the forms full/replaced, the profile of the parameters, the limit of waits and the displacement of its own identity; full/replaced does not advance the cursor; the periodic pass is mandatory — separate probes of the acceptance README, not TSV; an unknown parameter and non-ASCII digits — sc. 02; the trees console/audit without a hint — checked by reading
- [ ] **P/05-11** [test, reading, stand] the delete tombstones and the convergence of copies (N1.1 «Tombstones»): the tombstone at the deleter — outside the ordinary listing, `prefix=.gone/` and the body — reading, an older copy — 409, a newer write removes it by the same action — sc. 45; the dropping of copies by a neighbour, the confirmations and the removal by `peers ⊆ acked` — checked by reading (the stand of the [system acceptance](../../common/acceptance/system/README.md) (judge-only: convergence-check stand for P/05-R017) with two resources; there is no scenario)
- [ ] **P/05-12** [reading, stand] `restore` of events from neighbours at the resource start (N1.4 «Bucket restore»), repeats, «done» only after a full attempt, all known doors; `restored` — only the pulled buckets (step 49 of the drill `05-power-pull`)
  on the loss of the local events — checked by reading (a stand with two resources)
- [ ] **P/05-13** [test, reading] the schema check at the resource start (N3 «resource start — schema check»): no row — its own SCHEMA, not a number or version > SCHEMA — do not start, with the code 2, a read error — wait without starting work. Version above SCHEMA and not a number — the code 2, there is no door row, version 1 — it starts — sc. 17; a read error — it waits, without a restart it starts after the store returns — sc. 18; no row — its own SCHEMA — every scenario with `@start resource`; «before reading the manifest» — checked by reading
- [ ] **P/05-14** [test, reading] the body copy at the resource (N1.1 «Bodies at the resource» `mirror`, N2): the mirror of bodies always (copies 1 without the row `platform/mirror`, on the first pass to the neighbour with the source `written`) — sc. 31; the reception with a hash, the copy door only for a blob key of a subsystem with a blob field — sc. 10; `written` of a copy does not decrease — sc. 30; the refusals of the copy door (422, 400 without `X-Written`, 405) — sc. 10; 409 «deleted later» — sc. 45; 408, 411 and the closing of incoming copies in the cleanup window — checked by reading
- [ ] **P/05-15** [test, reading] the resource ceilings (N1.1 «Resource ceilings»): the resource door byte limit (OpenAPI Content-Length.maximum) at the resource door — the refusal 413, not a truncation; `limit` of `/events` — sc. 02; a body copy of exactly the resource door byte limit (OpenAPI Content-Length.maximum) — 204 and the read 200 — sc. 23, +1 byte — 413 without a write — checked by reading (413 before reading the body; the door is not obliged to drain beyond its volume — the client can get a break, P/01.1 N2.1 and item 9); GET of an object larger than the resource door byte limit (OpenAPI Content-Length.maximum) and `max_bytes` of the object store — checked by reading (the acceptance README, evidence outside TSV)
- [ ] **P/05-16** [test] the request to free space: the addressee — the workers of the subsystem on the server `<server>`, `<volume>` — the volume of the resource, `Σ freeing` — over the live heartbeats of this subsystem on this server for this volume (N1.4 `free_ask`, N3 `relieve`) — the vectors [`relieve`](../vectors/relieve/README.md): the answer `freeing: 0` and `freeing: N` (the VMS request freeing)

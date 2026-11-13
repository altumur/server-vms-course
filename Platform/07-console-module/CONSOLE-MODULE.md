> **Normative source: [P/07 Console module](spec/07-console-module.norms.md).** This describes the public surface: closed call list N1.4, shell contract N1.5, late layer N1.6. The three console parts, page and byte publication are [P/06.5](../06-console/spec/06.5-console.norms.md). Lesson norms prevail if this description differs.

# The platform console module: contract

This English text is the source; the Russian translation `ru/CONSOLE-MODULE.md` (for people, not in the export) is derived from it by translation and is not edited by hand.


The contract is public. It is read by the course (`Source/`) and by the product; the page of any subsystem is written by it.

## 1. What it is

The platform serves one module, `GET /platform/console.js`. From the manifest and the platform doors the module builds everything in the console that is common to any subsystem:

- the unit tree;
- login and the session;
- servers;
- the domain;
- rights;
- the journal.

The page of a subsystem is the **shell**. It lies next to the manifest file of the subsystem as `<sub>.shell.html` (for VMS `vms.shell.html` next to `vms.subsystem.yaml`): the page is served only by the console root (`CONSOLE_ROOT`) for its root subsystem, if the file exists, otherwise the platform page; subsystems from `/mounts` do not serve pages of their own, the module shows them on the root page; the exception is a manifest with the word `console.shell`: such a subsystem serves its shell at `/<sub>/` as a separate page, and the files of the list `console.files` at `/<sub>/<file>` (P/06.5 N1.1 `mounted`, N2 «Static files of a subsystem»). There is no option `Page` in the code; the page is a file. It includes the module, mounts its sections, adds its own and subscribes to the selection of an object. The platform page `console.html` is the same shell in its minimal form: the module and nothing else.

```
<script src="/platform/console.js?v=1"></script>
<div id="app"></div>
<script>PlatformConsole.mount(document.getElementById("app"))</script>
```

## 2. What the module does NOT do

- **It names no subsystems.** The source of the module has neither names of subsystems nor their subject words. The dictionary of forbidden words is the same as that of the boundary test (§2.7 of the boundary note): `vms`, `cam`, `camera`, `"\u043a\u0430\u043c\u0435\u0440"`, `rec`, `det`, `auto`, `live`, `archive`, `"\u0430\u0440\u0445\u0438\u0432"`, `footage`, `video`, `"\u0432\u0438\u0434\u0435\u043e"`, `rtsp`, `device`, `recorder`, `volume`, `whep`, `timeline`. The three non-ASCII dictionary entries above are JSON string literals with Unicode escapes; their decoded token values are unchanged. Captions for units and fields come from the manifest as data (§6).

  **`live` — a rule by token.** `live` as a state is a platform word: a live heartbeat, `live` and `silent` in `/servers` and `/events`, the gauges `*_live`. It is forbidden only as the name of the live video subsystem: `live_url`, `LIVE_NAME` and any `LIVE_…`, `/live/`, `livecontroller`, `liveworker`. The test checks tokens, not a substring: `live_url` in the module does not pass, `state === "live"` passes.
- **It knows no other routes.** The module goes only to the doors of the closed list [P/07 N1.4](spec/07-console-module.norms.md) (`reads`, `writes`, `never`, `order`; the domain section — the late layer P/07 N1.6). Any other route is the shell's business.
- **It loads nothing from addresses that do not belong to it.** The address of the door of a unit's holder (`/where` → `door`) the module only hands to the shell through `where()`. It does not go there itself: no timeline, no chunks, no WHEP.
- **It keeps no session of its own for the shell.** There is one session, the platform cookie (§5). The shell does not start its own.
- **It does not intercept foreign sections.** Cards and sections that the shell added the module only places, and it does not touch their DOM.

## 3. Mounting and life cycle

`PlatformConsole.mount(root, opts) → console` — the module draws the frame in `root`:
- the section strip;
- the tree;
- the inspector;
- the status line;
- the login window.

It returns the object `console` through which the shell talks to it. The module object is one — `PlatformConsole`
`{version, features, mount}`; `pc`, `console` in the examples are the variable name of the page (P/07 N1.5 `module`).

`console.ready` is a promise: it resolves with the page object after `mount` and the first read `/manifest`; on an answer 401 it
waits for login and resolves after it (`await pc.ready`; P/07 N1.5 `ready`).

The parameters `opts`, all optional:

| Parameter | What |
|---|---|
| `sections` | which platform sections to show and in which order: `["units", "access", "journal"]` by default. Servers and the domain are not sections of the strip but the second layout of the units panel, «By servers», where the domain is the root |
| `subsystems` | which manifests give units to the tree: by default all from `/mounts`; `[]` — none; the unplaced ones the section `unplaceable` reads at all subsystems of the catalogue, read-only (P/07 N1.4). A limit of the published canonical module [console.js](module/console.js): it does not execute this rule (`[]` and the unplaced — only by `opts.subsystems`), the owner of the published common module bytes closes this open debt under P/07 N5 and «Implementation decides» item 6; generation lines keep the published bytes unchanged. A subsystem whose manifest says `about` (§7) is nested as nodes under the units of the parent; without `about` — a tree of its own. The shell may narrow the list |
| `lang` | Exact `"ru"` selects Russian platform captions and UI timestamp/date formatting; every other value, including omission, selects English. Captions are materialized from [data/localization.tsv](data/localization.tsv) into the existing WORDS shape of the same module. The browser language does not select a language; subject captions and protocol/data values remain unchanged. |
| `poll_s` | the polling period of the page, 5 s by default; the module polls every `poll_s` (P/07 N1.4 `order`), it has no period of its own in browser memory; it learns of a row edit earlier — by the feed `GET /changes` (P/07 N1.4 `changes`) — and rereads the data at once |

`console.version` is the version of the contract, an integer, now `1`. An incompatible change is a new version. The shell checks the version before calls (the platform page `console.html` — before `mount`; P/07 N1.5 `version`). `PlatformConsole.features` is a list of strings of capabilities beyond the first calls of version 1: `"select.tab"`, `"card.closed"`, `"api.if-match"`; no string — no capability; the version does not change because of new calls (P/07 N1.5 `features`). The module is served as `/platform/console.js?v=<version>`; old versions are not served: backward compatibility is not kept while the system runs on one machine only.

## 4. Objects and selection

Everything that is selected in the tree is an object with a reference `ref`, a string:

| `ref` | Object |
|---|---|
| `unit:<sub>/<id>` | a unit of the subsystem `<sub>` (`<sub>` is the name of the manifest) |
| `server:<s>` | a server |
| `worker:<sub>/<w>` | a worker of the subsystem |
| `member:<m>` | a domain member |
| `domain` | the domain as a whole |
| `person:<name>` | a person of the domain |
| `<prefix>:<…>` | an object of the shell: the shell chooses the prefix, the module only keeps and hands it |

The selection API:

- `console.select(ref, {tab?})` — select: the module highlights the tree node and opens the card; `tab` is the id of a tab given by `addTab` (`"general"` — the module card); no such tab — the card without a change of tab (`features`: `"select.tab"`).
- `console.selected()` → `ref` or `null`.
- `console.on("select", (ref, obj) => …)` — after every selection. `obj` is what the module knows about the object: the unit row from `/<rows>`, the server row from `/servers`, the domain member row.
- `console.on("refresh", data => …)` — after each cluster poll with a confirmed current root `/servers` read: `{units, servers, domain}`, with the exact root `d.servers` map. A failed root read skips only this cluster emission; reads, local repaint and the next poll continue. Confirmed empty, unchanged and same-map recovery responses each emit normally, without change-only filtering or catch-up. Holder-only `{domain}`, access `{access}` (P/07 N1.6), the other events and `ready` remain unchanged.
- `console.on("logout", …)`.
- `console.on("session", ({user}) => …)` — at every read of `/session` with a known `user`: at mounting and after a login through the module window, ordinary and emergency; a subscription made after the read receives the last value at once; `user` unknown — no event; another `user` — the page resets its own state (`features`: `"session"`).
- `console.on("card.closed", ({ref}) => …)` — the card was removed: the selection of another object, the clearing of the selection, leaving the page; for a shell card `ref` is its name as is (`streamaccounts:local`); a repaint by polling does not count (`features`: `"card.closed"`).
- `console.dialog(title, fields, ok)` — a module dialog for the actions of the page; a field may be `type: "file"`: the value is the text of the chosen file, the module does not keep it. It returns a promise (`Promise`): on pressing the button `ok` — the values of the fields `{<name>: <value>}`, on cancel — `null`; `ok` is the caption of this button (P/07 N1.5 `adds`).
- `console.confirm(q, more)` — a question to the human with the explanation `more`; it returns his answer `true` / `false` at once (a value, not a promise; P/07 N1.5 `adds`).

## 5. Session and requests

- Login is the module: the login window, `login_url` from `/session`, `POST /session {token}`, break-glass, logout. After login the module reads the parameter `return` of the page address: exactly `/<sub>/` of a subsystem of its catalogue — a transition there, any other value — to `/` (P/07 N1.5 `return`; protection from an open redirect). The session cookie is set by the platform; it is common to all doors of the cluster (§6.1 of the boundary note: the same token at the worker door).
- **Command kinds.** `command` — «a command was performed», `command.failed` — «a command was not performed». The word and the note are the module's; `display.kinds` of the manifest does not name them. The note: `action` · the outcome by `outcome` — `performed` «performed», `refused: <why>` «refused: \<why>», `expired` «expired: nobody performed it in time», `unknown` «whether it was performed is unknown» · «by: `<by>`»; without `outcome` for `command.failed` — its `why` or `error`. If the event carries `late: true` (the device answer came after the deadline, and the request was already answered «did not answer»), «late: after the deadline» is added to the outcome: «performed late: after the deadline», «refused: \<why> late: after the deadline» and so on; without an outcome — only «late: after the deadline». No `display` keys are needed. The platform fields at the top level of the event: `outcome`, `action`, `by`, `late`, for `refused` and `unknown` — `error`. The target's answer as a whole is under `reply` (a dictionary). The module shows it as is — «key: value» separated by commas, without words — after the outcome: `action` · outcome · the target's answer · «by: `<by>`». For `refused` the why is taken from `error` («refused: `<error>`»), for `unknown` — «whether it was performed is unknown: `<error>`», if `error` exists.
- **Debug login.** `/session` may serve `{user, debug: true}`: the door let a person in without a token because the request came from a loopback address of the connection and the process has `W2C_DEBUG_PERSON` set (the stand only). The rights are his real grants. The module draws in the header next to the name a red mark «debug: no sign-in» while `debug` is true; «Sign out» is not shown in this mode.
- `console.api(method, path, body, opts?)` — a request with the session (P/07 N1.5 `api`). A call is one logical action: its `POST` and `PUT` carry a new `Idempotency-Key`, the repeats of this action — the same key and the same body; a new call — a new key, even with the same bytes. A lost answer (network, timeout 20 s, 5xx, 409 «in flight») is repeated automatically only at a door with the owner's repeat memory — `POST /<rows>`, `/<sub>/<rows>` (P/06.1); the delay is the header `Retry-After` of the answer, without it 2, 3, 5 s; after the third repeat — a refusal `{status, body, retry}`. `PUT`, `DELETE`, tables and `POST` of doors without memory (`/marks`, `/drain`, the decommission of a server) are not repeated automatically: the outcome is unknown — the module first rereads, then says so. The final answer closes the action. The shell sends all its writes through it, so that there is one rule. The fourth argument `opts` is only `{ifMatch: <revision, an integer ≥ 1>}`: the module sends `If-Match` at `PUT` and `DELETE` of a unit row `/<rows>/<id>`; another method or path, an extra field, a non-integer value — a refusal of the call before the request; an answer 412 — a refusal `{status: 412, body, retry: false}` with the body as is (the capability `"api.if-match"`). `opts.ifMatch` is an integer `revision`, the header `If-Match` at the doors that read it: the rows of units and tables, the settings of chapter 6.6 (P/07 N1.5 `api`). The unit form always sends it and shows 412 as a screen: the input is intact, next to it the values of the row now and the button «Reread» (P/07 N1.5 `forms`).
- The unit form and the creation form show a refusal 400, 409, 412 at the field by `field` of the body (JSON Pointer, P/06.1 N2 «Refusal: `error` and `field`»; P/07 N1.5 `forms`): the control gets `aria-invalid="true"`, next to it — `.pc-field-err`; no element or no `field` — the text in the common `.pc-err`. The published module does this (P/07 «Implementation decides» item 4 — closed, the bounded unit-form fixture in N5 row P/07-R282).
- A subsystem whose manifest carries `unit.writes_via` does not let people write rows: the module shows no creation forms, and the unit form has no «save» and «delete» — the fields are read-only; a table with the word `tables.<t>.writes_via` — without a row write form (P/07 N1.5 `writes_via`; P/06.1 N1.1a). A limit of the witness: the published module does not know the word, the owner of the published common module bytes closes the open debt defined in P/07 N5 row P/07-R285; no closure evidence is declared; generation lines keep those bytes unchanged.
- `console.kindWord(e)` and `console.eventNote(e)` — the word and the description of an event: for platform kinds (`server.*`, `worker.*`) from the module dictionary, for subsystem kinds from `display.kinds` of its manifest. The shell does not name the platform events itself.
- `console.where(ref)` → `{worker, server, door, reason}` — where the unit is and the door of its holder: `door` is an object `{url, token, expires, routes}` or `null` when the answer of `/where` has no field `door` (P/07 N1.5 `where`). The shell goes to `door` for bytes itself, with the same cookie.
- 401 from any request, of the module or of the shell through `api()`, opens the login window.
- **Rights.** `/session` serves the caller's grants: `none` / `view` / `edit` / `admin`, the subsystem `sub`, the role `role` and the scopes (`unit:<sub>/<id>`, `labels:<…>`, `folder:<id>`, `*`), for a domain administrator — `admin: true`. The module itself hides edits and actions for which there are no rights, and gives `console.may(cap, ref, sub?)` → `true | false`, so that the shell does the same for its tabs. Actions: `view`, `edit`, `admin`. The rule is one and lives in the module (P/07 N1.5 `may`; the right contract `Platform/common/contracts/may.md` steps 6–7); the shell does not repeat it: a row with a rank not below the action and a scope covering the unit (`*`; `unit:<sub>/<id>` — the unit itself or its about unit; `labels:L` — all labels L at the about unit, if there is one, otherwise at the unit itself); outside a unit — only `*`, `view` — any row. An emergency session (`via: break-glass`, grants `[]`) — yes; without grants yes only at an open console (`open: true`); a closed or unknown session (`/session` did not answer) — no. The server checks every request anyway, and `may` only does not show the human what he would be refused.

## 6. Words from the manifest: `display`

The module does not know that a unit is a camera. The manifest may carry words for display:

```yaml
display:
  unit: camera
  units: cameras
  field_help:
    labels: networks in which the camera address is visible (vlan:cctv-a)
    source: the device address
```

More keys (all are words and one flag, without logic):

```yaml
display:
  section: Cameras            # the caption of the first section of the strip
  tree:
    group_title: Folders       # the layout by group_by: the title and the hint
    group_hint: by camera folders
    filter: name, address, label  # the hint of the filter
    no_group: no folder      # the row of units without a group
    children: false          # do not nest in the tree the units of subsystems whose about points to this one
    contents_title: Folder contents   # the captions of the group card
    group_word: Folder
    no_group_suffix: no folder
    pick_note: pick a camera in the tree   # the explanation of the section overview when nothing is selected
    new_root: ＋ Folder           # and «Create a folder» in the menu «no group»
    new_sub: ＋ Subfolder         # and «Create a subfolder» in the menu of a group
    add_here: Add a camera here
    new_group_note: The folder is created — add a camera to it, otherwise it will not be saved   # without it the module writes a common one with the word from display.unit
  units_count: cameras         # the plural for counters (in Russian the genitive plural): «12 cameras», «Cameras inside»
```

A unit is created by the button «＋ \<unit>» in the header of the section overview and in the header of a group (from a group a new unit is in it at once). A card may put `<button class="pc-hdbtn">` right under its `<h1>`, the module moves such buttons to the header next to `addAction`; the path of the card is `<span class="pc-crumbs" data-crumbs='[[word, ref]]'>` inside `<h1>`, the module draws it as crumbs. The module nests the domain members in the tree itself by `topology.via`. The overview «By servers» is the block «Cluster»: counters, the unit policy on the server, the layout version from `/schema`.

The keys of the unit card (words, the layout and one flag, without logic):

```yaml
display:
  general: Camera                    # the caption of the tab of the general form
  fields: {source: Address, live: Live stream}   # the captions of fields
  options: {live: {always: always, on-demand: on demand}}   # the words of values; the SET of values is from schema.enum of the manifest field, not from here
  form:                              # the blocks of the general form in order; a field outside the blocks is not shown; without form — one block with all fields
    - {title: Device, fields: [name, source, cred_username, cred_secret], state: true}   # state — the state icon of the unit
    - {title: Placement, placement: true, note: "…"}   # placement — «Worker · server», the state, the reason from /where, «Delete»; note — an explanation under the block
    - {title: State, status: [{field: stream, since: stream_since, title: Stream}]}   # status — the fields of the worker status, read-only, «since when» from since; the words of values from options
  events: false                      # the module does not add its own tab «Events» (the unit journal and the marks): the page shows them
  tree: {not_in: "…", add_to: "Add to folder…", no_others: "…", new_group: "＋ New folder", remove: "…"}   # the words of the group block in the form; without them — the common ones
```

To a page card (`addCard`) and to its section (`addSection`) the module gives a nested container of their own: a late rendering after a request of the page lands in a detached node and does not erase a card selected later.

The behaviour of a card: the card writes `<h1>` and `nav.pc-tabs`, the module moves them to the header (the path, the star, «full screen», the tabs); sections with `<h2>` the module makes into blocks `.card`; the footer saves the form; a boolean field of an existing unit is written at once, like a switch.

And two keys:

```yaml
display:
  kinds:                 # the kinds of journal rows and of unit events, in words
    camera.clock.step_forward: the camera clock jumped forward
  tree:
    group_by: folders    # group the tree by a list field; the module does not know that these are folders
```

The module takes subject captions, field hints and kind captions from `display` without translating manifest data. For absent unit captions its platform defaults use keys `unit` and `units` of [localization.tsv](data/localization.tsv): `unit`/`units` in default English, the table's Russian captions only for explicit `lang: "ru"`. The empty-list caption uses `noRows` (`No rows` in English). A field name or kind with no declared caption stays as is. `display` is only a dictionary: it has no logic, no conditions and no routes. UI language does not change keys, enum values, errors, outcomes, journal data or defaults carried by the protocol.

The table is the only editable platform-caption source; WORDS in the published module is generated deterministically from it. `n.<name>` binds to the existing `n` dictionary and `kinds.<event-kind>` to the existing `kinds` dictionary with a literal event-kind suffix, not an arbitrary dot path. Russian values are ordinary JavaScript strings encoded with JSON-compatible Unicode escapes in the source. No locale-table fetch or separate dictionary service is added. UI dates use explicit `en-US` or `ru-RU` according to the mounted instance's selection, retaining existing date options, time zone and protocol-time values as specified in P/07 N1.5. This changes neither the synchronous `/platform/console.js?v=1` publication nor the public contract version.

## 7. Module sections

| Section | What is in it | Routes |
|---|---|---|
| `units` | the unit tree by the manifests from `opts.subsystems`; subsystems with `about` — as nodes under the units of the parent (below); grouping by `display.tree.group_by`; favourites by `ref` (localStorage); the unit card: the fields from the manifest, edit (secrets empty, only the changed fields are sent), on/off, deletion, where and why (`/where`), the unit events and the mark | `/manifest`, `/<rows>`, `/where`, `/events`, `/marks` |
| `servers` (the layout «By servers» of the units panel) | the tree «domain → server → workers»; the server card: resource, workers, labels (`platform/servers/<s>`), `servers.show` from the manifest (§8), decommission, write-off; the worker card: slot, lease, hang, name conflict, the units of the worker | `/servers`, `/servers/<s>/labels`, `/servers/<s>/decommission`, `/drain`, `/policy` |
| `domain` (the root of the layout «By servers») | where the holder is (`GET /api/held`), members, keys, topology, the move («Move the domain here» — a dialog: the recovery file as text and «the old holder was stolen» no/yes → `POST /domain/move {recovery[, stolen: true]}`; without the file the request is not sent), alarms (in the card one row per kind and `of`: the last one, «×N (since …)», the list of members, otherwise `session.debug_open` from every door at every start buries the real ones), keys-view | `/domain/*` |
| `access` | people, grants, break-glass | `/domain/users`, `/domain/grants`, `/domain/break-glass` |
| `journal` | the events of all subsystems, closed platform event kinds from `W.kinds`; other row kinds from the event subsystem manifest (`display.kinds`), without overriding a closed platform kind | `/events` |

**`GET /api/held` in the section `domain`** (the late layer, P/07 N1.6) is the only process door that the module reads: the signed public record of the holder `{cluster, holder, term, keys, backup: {term, rev}}` at the cluster console (where the holder is; there is no content of the backup in it). `backup` is the pointer of the last copy at this member, `{term, rev}`, compared by term first and rev at equal term (P/08.8, the largest (term, rev)); the holder comparison pair and roster come from `GET /domain`, `term.backup` and `term.backup_holders` (P/08.8 N1.3); the holder card (`term`) carries `backup: {term, rev}` of the last written copy next to `backup_holders` and `copies: {<member>: {term, rev}}` (the pointers of the copies of the members from their published `domain/backup-taken`, of the former holders of a copy too), so there is something to compare with: the marks are put on the domain card, and the `/api/held` of a member knows only its own pointer; the module shows at a member «an old copy» when its pair lags behind the pair of the holder, and «the holder no longer updates it» when the member is not in `backup_holders`; old copies at former holders are not dropped (a fallback path of the move), the numbers are shown as they are.

### What else the module does itself

1. **Creating a unit.** By the button «＋ \<unit>» in the header of the section overview and in the header of a group (from a group — in it at once); the general form by types for a new unit with the defaults from the manifest, `POST /<rows>`. The number of a numbered subsystem is given by the server, the new unit is selected. There is no immediate creation with a placeholder address: `source` is required and unique, a second placeholder would be refused.
2. **User, logout, emergency login.** The name of the logged-in person and «Sign out» (`DELETE /session`) in the header menu. In the login window — the emergency login: `POST /session/break-glass {who, why, password}`.
3. **«Retry» at a toast.** A write of a door with repeat memory that has exhausted its repeats is shown as a toast with a button. The button is one more repeat of the same action: the same method, path, body and key (P/07 N1.5 `api`).
4. **The layout version of the store.** `/schema` is shown in the block «Cluster»; an upgrade (`PUT /schema`) is not part of the contract.
5. **The unplaced.** The card «Unplaced» from `/unplaceable`: why each unit has no place and which labels the servers have.
6. **Table.** Not done: the module has no table view with mass editing. If the owner wants it, it is a new function of the module: a second layout of the tree with columns from `display.tree.columns`, sorting and mass editing of the manifest fields through the general form.
7. **Folders.** A subsystem with `display.tree.folders: true` gets a tree of the cluster folders (P/06.8; P/07 N1.5 `tree`). A folder node is an object with `ref` `folder:<id>` and a card of its own: the name, the parent, the contents in order. Actions:
   - rename — one own module write `PUT /folders/<id> {name}` with `If-Match` containing the quoted store index (P/06.8 N2): the field of the units is not touched;
   - create a folder and a subfolder — `POST /folders`; an empty folder lives on the server, not in the browser;
   - add a unit and remove it — the own module write `PUT /folders/<id> {members}` with the same quoted-index `If-Match`, the contents as a whole; a new unit goes to the end;
   - delete — `DELETE /folders/<id>`: the units remain, the subfolders disappear at once;
   - «no group» — a special node for the units outside folders.

   The module does not do this yet: a debt of the product to «Build». Below — the tree of subsystems without folders.

   **Groups.** A group node by `display.tree.group_by` is an object with `ref` `group:<sub>/<field>/<value>` and a card of its own: the value, the number of units, the list. Actions:
   - rename — rewrite the value in the list field at all units of the group through `console.api`, with one key per operation, with a report of what failed;
   - create — a value appears when the first unit gets it, and an empty group is only a filter;
   - «no group» — a special node.

   An empty group («＋ Folder», «＋ Subfolder») lives in the browser until a unit gets it; the menu of a group: create a subgroup, rename, add a unit here; at «no group» — create a group. All of this is the module, generalized for groups. In the menu of any unit the module gives «Delete» by `may(admin)`. The values of groups without units from the shared settings of the domain the module reads itself (`/domain/shared/<sub>`). The shell adds through `addCard`/`addMenu`/`addTab` only its own.

8. **The kind `session.debug_open`.** The platform writes it to the journal at the start of a process with `W2C_DEBUG_PERSON` set, with the field `person`. The word of the kind is the module's: «debug sign-in without a password is on» / «debug sign-in without a password is on»; the note — «as `<person>`».

Small things: the light/dark theme by hand — the module; the disabled tab «Detectors», the camera menu («Watch video», «Recording») and the shared settings of the domain — the shell.

### Dependent subsystems: `about`

Step 2 of the boundary note introduces into the manifest `about: {sub: vms, field: cam}`: the units of this subsystem are about a unit of the subsystem `vms`, linked by the field `cam`. The module uses this itself: the recordings, detectors, scenarios of one camera are shown as nodes under this camera, in the words of `display` of their own manifest, with a card by their own manifest. The shell does not need to know that recordings live under cameras: this knowledge is one and lies in the manifest. `addTreeNodes` (§9) remains for what is not a unit of any subsystem: for example, volumes, which are kept in a table and not in units.

## 8. Subsystem tables on the server card: `servers.show`

The module always draws them: this is the server card for a subsystem without a page of its own (the platform page, `testsub`). The product page may cover the same place with a block of its own (`addBlock`) with buttons and state; then the table `servers.show` for this table is not drawn. The page says so with the key `covers: "<sub>/<table>"` of `addBlock` (`addBlock("server", {id, covers: "rec/volumes", render})`). The module draws the table as a block `.card` with the title `title`, the rows `GET <base>/<table>` with `row[by] === server name`, the columns from `columns` with the captions from `display.fields` of the subsystem (otherwise the name of the field; `columns` are checked against the fields of the table in the manifest), secrets as a mask, empty — «No rows».

```yaml
servers:
  show:
    - {table: volumes, by: server, title: volumes, columns: [name, kind, quota_bytes]}
```

The module reads the table `<sub>/<table>` through `/<sub>/<table>` and shows the rows whose `by` equals the name of the server. What a volume is, it does not know: it shows the columns from `columns` and the caption from `title`.

## 9. What the shell adds

The module is a library of the platform, the shell is a product page that calls it. The calls below are the shell addressing the library inside its own page, not the platform calling a subsystem; they are not hooks in the sense of the boundary note (§1.1).

- `console.addSection({id, label, icon, after, off, render(host)})` — a section of its own in the strip: in the product «Scenarios». `after` is the id of the section after which it stands; `off` — the section is visible but disabled, with the reason in the tooltip. Mouse and keyboard activation neither enter the section nor invoke `render`; enabled neighbours still work.
- `console.addBlock(kind, {id, render(host, ref, obj)})` (`kind` — `server`, `member`, `domain`) — a block of its own on the general tab of the card of an object of the kind `kind`, after the blocks of the module, in the order of adding (in the product: «Server archives» and the disabled «Video accelerator» on the server overview).
- `console.icon(name)` — the markup of an icon by name (an icon of the module or one added through `addIcons`), so that the page's own rows look like the rows of the module.
- `console.addAction(kind, (ref, obj) => [{label, run}])` — the buttons of the page in the header of the card of an object of the kind `kind`, before the star (in the product: «＋ Camera to archive» at a server).
- The subtitle of a card: `<p class="pc-hdsub">` right after `<h1>` the module moves to the header under the title (this is how the module writes «The domain holder is …»; at a domain member — the server kind from `title` in `addDecor`).
- The key families of the domain on the tab «Keys» are NOT a call. The module captions its own families itself (members, member publications, holder networks, topology, edits pending, edit outcomes, the domain view); the families of a subsystem are the declaration of its part of the domain in the manifest (the section `domain:` — what the subsystem carries in `domain/<sub>/…`, with words in `display`), the module reads them from `/manifest`: the composition from `manifest.domain.keys` — `[{id, keys?, prefix?}]`, the words from `display.keys` — `{id: {title, about, absent?}}`, merged by `id`; a key outside the families — «Other keys». The field `domain` of the manifest in `/manifest` and `/mounts` of both doors is `{keys, shared, edit, view}`: `edit` — the unit fields that the holder lets into an edit (the others it rejects with 400), by it the module builds the unit card at the holder; `view` — the fields of the view by which the list of units by subsystems is captioned. Until the section `domain:` appears in the manifest, the shell passes the families with a temporary parameter `opts`, and this parameter is removed together with its tests when the section appears.
- `console.manifest(name)` — a copy of the subsystem manifest from `/manifest` for the code of the page (for example, the table of places from `manifest.places`); the page does not parse the manifest itself and does not fetch it separately.
- There is no `addGroupValues`: the values of groups without units the module reads itself from `/domain/shared/<sub>` by `domain.shared` of the manifest.
- `console.addNote(kind, (ref, row) => text | [text])` — the page's words about a unit that the manifest cannot say because a threshold or logic stands behind them (in the product: «opening has not completed for more than 15 s», «device fault»); they are shown as warnings under «Placement».
- `console.addEventNote((e) => text)` — the description of subsystem events in words (sums, reasons) wherever the module shows events, including «Log». The word of the kind remains from `display.kinds`, the platform events the module describes itself; the page does not call the module again for the same event (the shell has protection against reentry).
- `console.addIcons({name: svg})` — the icons of the page by name: the inside of an svg 16×16, this is page code, not data. The module draws its own icons itself (sections, server, worker, domain, folder, person, filter, search); a name that nobody drew is shown as a dot. `addDecor().icon` and `addSection({icon})` name icons by these names.
- `console.addTab(kind, {id, label, render(host, ref, obj), busy})` — a tab of its own on the card of an object of the kind `kind` (`unit`, `server`, `worker`, `member`, `domain`). In the product these are:
  - the tabs «Video» and «Archive» at `unit:/…`;
  - «Volumes» at `server:…`, if `servers.show` has not covered them.
  `busy()` is an optional function of the tab: while it returns `true`, the module does not repaint the card by polling (in the product: while the viewing and the negotiation of the live stream go on). The module does not know what exactly is busy; this is an ordinary call of the shell into the library.
- `console.repaintTree()` — the tree anew by the nodes of the shell: the page has learned something new while the data of the module has not changed, so polling will not touch the tree; the scroll stays intact, with a pressed button it waits for the release (`features`: `"tree.repaint"`).
- `console.addTreeNodes(kind, (ref, obj) => [{ref, label, icon, count, kids, badge, tags, dot, title, off, open, after, replaces}])` (`count` — the counter on the right; `kids` — nested nodes of the same form; `badge` — a badge; `tags: [text | {text, title}]`; `dot: [colour, word]`; `title` — a tooltip; `off` — disabled; `open` — expanded until collapsed; `after` — placed after the members behind a relay; `replaces` — the node stands in the place of the row of a domain member, so a camera server becomes its own camera) — the child nodes of its own objects that are not units of any subsystem (the units of dependent subsystems the module nests itself by `about`, §7): for example, volumes under a server. Their `ref` have the prefix of the shell. The selection of such a node arrives in `on("select")`, the shell draws the card in `render` of its section.
- `console.addCard(prefix, render(host, ref))` — the card of the objects of the shell (their `ref` with its prefix: `vol:<name>`, `rec:<record>`) in the inspector of the module, at the same place, with the star and full screen; without this there was nowhere to draw the card of a shell node except by climbing into the DOM of the module.
- `addTreeNodes` also accepts the top level: `addTreeNodes("servers", () => [...])` — nodes of the shell at the top level of the server tree, without a parent (objects that belong to nobody and that any server serves); `addTreeNodes("server", (ref, obj) => [...])` — nodes under a specific server; the kinds of `addTreeNodes` are `unit`, `servers`, `server`, `member`, `access` (P/07 N1.5).
- `console.addMenu(kind, (ref, obj) => [{label, run}])` — the items of the context menu of a node.
- `console.addDecor(kind, (ref, obj) => ({icon, badge, title}))` — the icon, the badge and the tooltip of a tree node and of the card title of an object of the kind `kind`. `icon` is the name of an icon from `addIcons` or from the icons of the module; `badge` and `title` are text, the module escapes it. There is no logic in the module, this is the same call of the shell into the library as `addTab`. In the product the icons of the servers (centre, office, camera) come this way.

**The unit card: the general form and a form of one's own.** The general form of the module is built from `/manifest` by the field types and is to be able to do everything that follows from the types: a field `list` keeps a typed array through display and editing, preserving commas inside strings, empty strings, order and duplicates, a field `group_by` — by the group block, a field `secret` is shown empty with the hint «set» and the rule `bound_to`, a field `labels` suggests values from the labels of the servers, «where and why» is taken from `/where`. This is platform work, and it does not go into the shell. What does not follow from the manifest remains to the shell, by two calls:
- `console.addFieldEditor(kind, field, render(host, ref, obj, value, set))` — an editor of its own for one field inside the general form (in the product: parsing `source` into the address, the vendor and the model); `set(value)` hands the value to the form, the sending remains with the form.
- `console.addTab(kind, {id: "general", label, render(host, ref, obj)})` — a card of its own instead of the general one, when another arrangement is needed; inside it the shell inserts the general form with the helper `console.unitForm(host, ref)` and does not repeat a single field of the manifest itself. The obligations are the same: edits through `console.api`, secrets empty, `bound_to`, `may()`.
- **A field of the type `json`.** The general form shows it as indented text (`JSON.stringify(v, null, 2)`, full width, monospace; the caption «— JSON»). Before sending, the module parses the text itself: not JSON — under the field «not JSON, nothing was sent: \<error>», the request is not sent, the typed text remains; JSON — the value goes into the body (an object, a list, a number or a string); a document string is written in quotes and goes as a string; an empty field, as with the others, is not sent. The door does not parse a string input as JSON. No `display` keys are needed. The shared settings of the domain (§10a) read `json` the same way.

The rule of choice: if the general form lacks something for any subsystem, it is fixed in the module; `general` is taken only for the sake of the arrangement.

**Appearance.** The look of the module is the look of the product console, common to all pages: the header with counters from the gauges of the manifest and the user menu (theme, refresh rate, «Refresh», «Sign out»), the section strip, the tree panel with the layout, the filter, the star and «⋯», a resizable width, the footer «Cancel»/«Save», cards. The common styles are the canonical module file [console.css](module/console.css), served by the platform next to `console.js`; the classes in it are neutral, the dictionary of §2 applies to the class names too. The styles of the subject tabs (video, archive, the camera card) remain in the product page. The page may override the theme, but it is obliged to nothing.

Everything that the shell has added the module places and repaints by its own polling, calling `render` again. The scroll and the focus inside the host are kept by the module (the same `paintInto` as now in the product).

## 10. Without a shell: the minimal page and `testsub`

These are the subjects of the contract checks. Evidence for the current canonical module has the input scope of P/07-R258; an existing fixture proves only its checked requirements on its actual input.

- **The platform page** ([console.html](module/console.html), the P/07 canon) — the three lines from §1 and nothing else. It adds nothing and works on any manifest.
- **`testsub`** — a fictitious subsystem (`testsub.subsystem.yaml`, §2.3 of the boundary note). The test brings up the console with it only and opens the minimal page in jsdom. It checks:
  - the unit tree;
  - adding, editing and deleting;
  - events and the mark;
  - servers, decommission and write-off;
  - login;
  - that the DOM has not a single word from the dictionary of §2;
  - that the module has made not a single request outside the closed list P/07 N1.4: the test intercepts `fetch` in jsdom and checks every path against the list. This is the check «knows no other routes».
- **The dictionary test** `Source/tests/console/platform-page.test.js` loads the frozen Source JS and HTML rather than the current canonical files (judge-only: existing page-dictionary case noSubsystemWords; local mount-version guard cases for P/07-R059…P/07-R060; no current-module execution evidence under P/07-R258).
- **The product page** (`vms/vms.shell.html` next to the manifest, in the product and in the course) includes the module and adds video, volumes, scenarios. Its test checks that it does not duplicate the platform sections: it has no login of its own, no server tree of its own, no domain of its own.

## 10a. The domain holder page

The domain holder page is the module: `PlatformConsole.mount(app, {sections: ["domain"]})` uses the English default; `PlatformConsole.mount(app, {sections: ["domain"], lang: "ru"})` explicitly chooses Russian platform captions (the option of §3). It adds no subject captions of its own. The frozen published module currently falls back to browser language when lang is absent; conforming to the English default and synchronizing captions is an explicit debt of the owner of the published PlatformConsole bytes, P/07. This normative source/table change does not implement that debt. The domain console (P/10 N1.7) serves the same paths as the cluster console:
- `GET /manifest` → `{"name": "", "rows": null}` (there is no root, there is no new key; the holder mode the module learns from `sections: ["domain"]` of the page, and in it it does not load units, `/servers` and `/unplaceable`, it takes the units by subsystems from the view `/domain`); `GET /mounts` → `{"root": "", "mounts": {<sub>: description}}` by `MANIFEST_DIR`, the description is the common `DescribeSpec` of the cluster console, without `media`;
- `GET|POST|DELETE /session`; `login_url` — `/api/login`;
- `GET /domain` (the view), `GET /domain/alarms`; `GET /domain/keys` — a door of the cluster console itself (P/06.7 N1.11), it does not go to the domain console;
- the field of the view `trust` (at both doors): `{installed, domain, rev, root, current, issuing, revoked_issuing, holder_has_keys, members: {<member>: {admitted_key, presented_key, keys_rev}}}` — fingerprints (`root`, `admitted_key`, `presented_key`), the key id (`current`), serial numbers and revisions, not a single key and not a single secret; the domain is not installed — `{installed: false}`;
- `POST /domain/members`, `DELETE /domain/members/<m>`, `PUT /domain/topology`;
- `GET|PUT /domain/shared` — `GET` serves `{doc, delivery, declared: {<sub>: [{name, type, schema?}]}}` (the declared fields from `domain.shared` of the manifests and their types; for the document `{name, type: json}` — also its `schema`, by which the page builds the form — P/10 N1.2f; the module builds it itself: an object by `properties`, a list with «add»/«remove», scalars and `enum`, what the form cannot say — JSON text in its place; P/07 N1.6 `schema`); `PUT {base_rev, shared: {<sub>: {<field>: value|null}}}`;
- `POST /domain/handover {to}`, `POST /domain/stranded/apply {path, key}` (apply anew an edit that only the replaced holder held), the emergency move `POST /domain/move {recovery, stolen?, copy?, why?}` — not a door of the domain console but of the cluster console of the target: it passes it to its signer by the same path, `/domain/move`, with the identity and the grant `admin` of this cluster (P/06.7 N1.8, P/08.8 N1.8; the limit is 90 s; a cluster that holds the domain answers 409); the target takes the neighbours from `CLUSTERS`; for the stand and drills `w2cctl domain move <door> <file> [stolen]`; the reception of a planned handover is the process route `POST /api/take {grant, keys_sealed}` at the signer of the target, not open to people;
- `GET /domain/users`, `/domain/grants`, `/domain/break-glass` and their edits;
- `/domain/<sub>/<rows>|<table>` by declaration; `/domain/<sub>/…` to the worker door of the subsystem (only settings and rows; the bytes bypass the console).

`/servers`, `/drain`, `/schema`, `/unplaceable`, `/metrics`, `/events` are not needed at the holder: the module survives their absence. Some paths literally: the cluster console forwards `/domain/X` to `/domain/X` of the holder without rewriting; by the same forwarding, but to the address of the member console from `CLUSTERS`, go `GET /domain/at/<cluster>/<sub>/where/<id>` and `GET /domain/at/<cluster>/<sub>/where/<table>/<place>?unit=<sub>/<id>`: this is how the camera page takes the door of a recording that another cluster of the domain holds; and everything under `/domain/<sub>/…` that is not the rows of the subsystem, not a table `domain.tables` and not the books `domain.books`, the domain console forwards to the domain worker of this subsystem declared by the manifest (`domain.books`/`domain.kept`), at the address from its heartbeat at the holder: the platform does not know the names of its routes (`/state`, `/cameras`, `/scenarios`, …) and does not read the answer, the rights are decided by the gate of the worker door; this is a door by declaration, like `where` at the holders, not a hook; the set of routes is not closed while this door has no token with routes; only `GET` and only `where`, a cluster from the carried list of members and not this one, one hop (`X-W2C-Via`), 5 s, the gate here is only «who it is», the gate of that cluster decides by the carried grants, the door is issued only by that console with its own key, the answer goes to the page as it came, the bytes bypass both consoles; the refusals in words: 403 of that gate, 404 «not a route handed to a member» / «no console of \<cluster> is known here (CLUSTERS)», 502 for a member console not visible over the network, 400 «one hop»; all human routes of the holder live under `/domain/*` (`members`, `topology`, `users`, `grants`, `break-glass`, `pending/`, `shared`, `alarms`, `handover`, `stranded/apply`, `<sub>/<rows>`, `<sub>/<table>`), and `/api/*` remains for the processes (`carry/`, `member/`, `relay/`, `tokens/`, `backup`, `take`, `held`, `prepare`) and for the login `/api/login` (the console forwards it to the domain, [the forwarding contract](../common/contracts/forwarding.md) «Domain doors»). Without a token the cluster console serves only what is signed and public: `GET /api/held` → `{cluster, holder, term, keys, backup: {term, rev}}` (`term` from the signed record of the holder, `backup` — the pointer of a copy as the pair `{term, rev}`, not the content); a copy of the domain backup only by `GET /api/backup` to a process that has signed the request with the key of a member from the list of this cluster; `POST /api/prepare` only by a signature with the token key of the current set of the holder ([P/08.8](../08-domain/spec/08.8-domain.norms.md) N1.7). The agent of a member follows the holder itself: it polls `/api/held` at the consoles of the domain clusters from the declaration `CLUSTERS`, takes the record from the answer of the holder and from 409 `deposed` and follows the verified record with the largest term (P/09.1 N3 «follow»); there is no separate list of candidates, the holder does not tell the members about itself. In the module the section `domain` shows the layout «By servers» with the domain at the root; the domain card carries the term and the handover, «apply again», the units by subsystems, the shared settings by `declared` and the edits for clusters (pending and outcomes).

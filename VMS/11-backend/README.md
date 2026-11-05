# V/11 Configurator backend

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** (2026-10-30, «Спецификация VMS»; the plan is accepted by «Архитектор»): chapters V/11.1–V/11.19 — norms (chapters 15–19 are the former lesson V/08, ADR-0118), chapters 9–13 moved from V/10 (ADR-0093 addendum (8) item 2; 2026-11-02); the stand —
by a candidate with the platform norms B. The basis is ADR-0094 (A1–A7, addenda (1)–(16); B1–B7, B9 — platform norms), ADR-0095–ADR-0100.
The platform is the export `cammeta-specs` `7a875c75` (the VMS pin; the increment of rights on top of the norms B, ADR-0090 addendum (17)). The manifest is [`backend.subsystem.yaml`](backend.subsystem.yaml)
(the canon; ADR-0090 addendum (6) item 8). The sources are the session «Консоль»
(a comparison with consolem, a sketch of the adapter; reference, not canon).

## What lesson V/11 is

The subsystem `backend`. The interface of the configurator consolem is our fork (ADR-0112): the WebUI and its contract with the server, the REST API
`api/openapi.json`. `backend` serves this API to the WebUI, translating each call into doors of the platform console. The translation is on the
server, but the worker has neither rights of its own nor a person's credentials: the console passes it the request with a **ticket** for this
one request, and the worker calls the console doors back by the ticket, only from a closed listing (ADR-0094 B1). The WebUI is served by the
console itself: the shell `backend.shell.html` and the files of the product set (styles, a font, a dictionary); the API is under `/backend/api/`.

## Chapters

| Chapter | What it norms | Status | Platform and lessons |
|---|---|---|---|
| V/11.1 | The unit `backend/instances/<name>` by labels next to `live`; the callback — TLS with the role `backend`, the ticket is bound to the server leaf of the instance (one per server), a socket — only without a kit (addendum (6)); the worker is without rights and without state; the WebUI — the shell [`backend.shell.html`](backend.shell.html) with a CSP of exactly the minimum of P/06.5 (`index.html` of the consolem build `0fbdd12`) and the static files of the subsystem (B7: the list in the manifest, the commit and SHA-256, outside `api/`); the handover: the route `api`, the answer JSON/SSE, the second view and the callback listing with `<sub>/policy` (B1) | norms | P/02.1, P/03, P/04, P/06.5 Н1.1, Н1.8; ADR-0094 B1, B7, addenda (6), (8) |
| V/11.2 | The contract of the consolem fork at the commit `0fbdd12` (0.2.0), the copy and SHA-256; the fate of each of the 126 operations (116 are translated, 7 — `404 NO_ROUTE`; 3 — `POST /test/reset`, `/test/clock`, `/test/stream-elsewhere` only on the stand, otherwise `404 TEST_SUPPORT_OFF`); the refusal — the contract's `Problem`; the declaration of capabilities | norms | ADR-0050; ADR-0094 A1, A5, addendum (2) item 2 |
| V/11.3 | The mapping «consolem kind ↔ VMS subsystem» by lesson data ([`data/mapping.tsv`](data/mapping.tsv)): a domain — a cluster, a camera — `cam` + `rec` + `det`, the device tree — `cam/devices`, `cam/children`, `cam/device_units`, a storage — `rec/volumes`; a rule — an `auto/scenarios` row, the library — the `auto` tables; `recordMode`, the device fields from rules — `cam/rule_state`; the version — the store index | norms | V/01, V/02, V/04, V/07; ADR-0094 A6, addendum (2) items 3, 4 |
| V/11.4 | Translation of reads and writes: device search and the question about the model (V/01.8), the device assembly, a device write by one B9 package (`cas` of the written ones, the others by guards; 412 — nothing is written), the version — a concatenation of the store indexes of the parts and of the tombstones, the repeat memory of `idempotencyKey`, group writes per element, console refusals → contract codes, id — UUID v5; folders and hidden members, group operations, the limits of the parts and of the device folders; rules, `RULE_INVALID`, cascades, the library, undo and redo `backend/undo`, streams and live, pan-tilt and presets, the unit command, accounts, server labels | norms | B3, B4, B5, B9; ADR-0095, ADR-0096, ADR-0105, ADR-0106, ADR-0112 |
| V/11.5 | The callback by ticket and the stream: `/stream` from the feed `/changes`, the table of messages, `Last-Event-ID`, `stream.reset`, `operation.*`, the descendants of a deleted folder | norms | B1, B2; ADR-0095, ADR-0096 |
| V/11.6 | The stand and acceptance: the consolem API tests in the capabilities profile, `/test/reset`, `/test/clock`, `/test/stream-elsewhere` (the key `TEST_SUPPORT` and the console loopback mark), `/test/events` — `NO_ROUTE`, `?selftest` | norms | ADR-0050 |
| V/11.7 | The configuration assistant in `backend` (ADR-0093 addendum (6), ADR-0094 addendum (10)): the streaming turn `api/assist/turns` by the contract, the model — the route `/assist/chat/<имя>/…` by ticket, the loop of V/11.9, the tools and the plan check — the canon of V/11.10, V/11.11, the translation of the plan into `DevicePatch` (anything else — a refusal), turn events, the limit `ASSIST_TURN_MAX` = 7500 s | norms | V/10; B1 |
| V/11.8 | Rights: the snapshot `Access` from the domain doors and the grant rows, the translation of levels into role lines and back, `arch` by А4, `POST /access/apply` as a difference by one domain package, the untranslatable, `SELF_LOCKOUT`, history | norms | ADR-0097–ADR-0100; P/08.4, the contract `may` |
| V/11.9 | The turn loop in `backend`: the turn and the texts of the turn, the step messages (the only `system` — the lesson's system text, the overview and the secrets — `user`), `tool_choice: required`, the window, parsing the answer, outcomes, the life of the turn | norms | V/10.2; ADR-0093 addendum (8) item 2 |
| V/11.10 | A closed set of nine tools: console doors by ticket, the selection in `backend` over full lists, the field words from `display` and lesson data, rights before the plan | norms | ADR-0093 |
| V/11.11 | The plan and its check: an own plan format, a pure function of `backend`: the form and the rights, «named» by the texts of the turn, the selection, extra and missed ones | norms | ADR-0093 |
| V/11.12 | Applying and secrets: the changes to apply, the display, the secret label; the write — by the client (chapter 7 Н1.3) | norms | ADR-0093 |
| V/11.13 | Rules in words: two harnesses by the request type, tools with `check_plan`, the catalogue of events and steps as lesson data, a neutral plan in the concepts of the contract and one translator, check layers over the V/07 row, a mandatory reconciliation with the words of the request, `ask`, `escalate` in observation, writing only by a person, display in words | norms | V/07; ADR-0093 addenda (8)–(11) |
| V/11.14 | Kind description and the move to the core: the w2c kinds model (a kind ≠ a subsystem, the kinds table is data, a composite kind is the same B9 package, a table row has its own version), the sources of the core agreements, the contract 0.2.0 as a whole without stages (ADR-0116 addendum (9)); chapters on the core; the translation of the manifest | norms | ADR-0116; ADR-0115 |
| V/11.15 | The form and the viewing tab: serving, the contract, the composition of the tab, what the form does not do, the root shell, the former page is removed and what remains of it; the witness: the camera | norms | ADR-0112; V/11.1 Н1.4; P/06.5 |
| V/11.16 | Holder doors and the timeline: `where` → `door`, a margin of 20 s, a token refusal 403 → `where` anew once, Bearer and `?t=`; the doors of recordings and seats (`?unit=<запись>`), merging of twins, the own door first, yielding (`yields`), the unavailable is named (`X-Unreachable`, `X-Unavailable`), recordings of other clusters by the book `primaries`; events on the timeline by `occurred`, the mark, «закрепить» ("pin") | norms | the door token contract; V/02.5 Н1.5; V/02.8 Н1.4, Н1.6; V/02.9 Н1.6; P/06.4 Н1.2–Н1.3; P/06.7 |
| V/11.17 | Playback and live: pieces of 60 s, each moment once, the fenced-off — by choice or over an uncovered moment, a piece not served — a caption and one repeat with a new `where`; WHEP — the first viewer (`POST /live/streams`, 409 is the norm), the window size in the offer, a repeat of 404/503 every 1.5 s up to 8 times, 500 — a repeat, the PT transfer of H.265, hang-up, reconnection with jitter, the event feed | norms | V/02.5 Н1.6; V/03.1–V/03.5 |
| V/11.18 | Archive, holds, volumes: the recording state, an edit right away by a write, the name rule of a new recording (V/02.1), the volume choice (without `incidents` and foreign cards); holds and their states, «Проверить» ("Verify"); volumes in the tree and on the cards, reducing a quota with a confirmation, withdrawal, a vanished directory | norms | V/02.1, V/02.6, V/02.7; P/06.1, P/06.5 Н1.2 |
| V/11.19 | Scenarios, the domain, accounts: the scenario form = the schema `then`, refusals = the door refusals (and the evaluator's — two fields), `unfit`/`reason`, firings per day; the domain — the recording assignments by V/02.9 (the field `ref`, the former recording is not deleted, the backup — `when: offline`); stream accounts — the password once | norms | V/07.1, V/07.3, V/07.4; V/02.9 Н1.1; V/03.6; P/08.6; P/10 |
| V/11.20 | Export: the orders of the fork window `/exports` onto the part rows of V/08 `exp` — rights `GET /me/export`, an order in one batch, the check without a write, reading, cancel and delete requests, retry, the file link, the recording days, `Reference.export`, the stream `export.*`; `area` an array, the box error `/cameras/i/area`, the time zone of the file names (the Architect's decision 2026-11-04) | norms | V/08.6–V/08.9; V/02.5; V/11.8; ADR-0117 addenda (1), (7) |

## Contract and WebUI

- **The contract** — [`consolem.openapi.json`](consolem.openapi.json): `api/openapi.json` of the fork repository
  `github.com/altumur/consolem` at the commit `0fbdd125dcc976e871f7eea17f6b9538a81e7019` (2026-11-05; the contract 0.2.0 of ADR-0116 addendum (9) with the export supervision edit `0fbdd12` — the answer to the request 082435Z), the bytes as in the
  repository; 126 operations; SHA-256 — [`consolem.openapi.json.sha256`](consolem.openapi.json.sha256) (`fe6d8d22…44`).
- **The WebUI** — a build of the fork under the console CSP at the same commit, without the section «Обучение» (`--without-learn`; repeatable; V/11.1 Н1.4).
  The entry page is the shell [`backend.shell.html`](backend.shell.html): the `index.html` of the build byte for byte (SHA-256
  `254d7b75ca172529cbdffef69152b308a8a100d2d4f15a8a1f5a74949b9aa6aa`; ADR-0094 addendum (8) item 3). The API is under
  `/backend/api/`, the static files are `/backend/<файл>` outside `api/` (addendum (8) item 2). The static files of the subsystem (B7) are
  the other files of the build's `MANIFEST.json`, seven of them (they are not part of the course, they are the fork's code):

  ```
  0d83551bec97c1ccdea86e7f1cc1f263d6718ba31283d805cdeb5cf9ddbf6bba  app.css
  2c5caec589f5301098414621984e72f60f1a8de05b4d79073587320e5a4f87e5  app.js
  3124abf37ef18068bf758a05871d761d4003d16876c58cfac6168c90f8028c77  client.js
  693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3  fonts/InterVariable.woff2
  c8a2bb48023580349758819c0cf8fe2769f416ecd2eeba20bfc349881bf0a08f  i18n-en.js
  a48013e7871aaa48748a41c4df8bb9565281c6eeeb1dac15e64988ec6f82a9fe  openapi.js
  c1e5524fbef47072be82677f4a7ac0ebf9236fe7f12998901fd9d842c6ca27e3  whep-stub.js
  ```

  The eighth file of the build, `assets/stub-piece.mp4`, is not part of the set: `.mp4` is outside `console.files` (P/02.1), the stub piece is needed only by the address `stub://`, and `backend` does not give that out.

  The SHA-256 of the set (SHA-256 of these seven lines with `\n`, the order — by path bytes):
  `20c5aa2f0d6b84bac7f61a06f1ae8c786cfa0fe5a3ab8911a733fd9642fb5f1b`. The console serves them as static files of the subsystem
  `backend` (B7, ADR-0094 addendum (1)) by the manifest listing, by name without the query string `?v=`; the deployment package
  builds them from the pinned commit and puts them next to the manifest, the console checks the SHA-256 of each when serving (V/09.3).
- **The UUID namespace** of the records (V/11.4 Н1.6): `BACKEND_NS` = `4ffc0b08-e8bd-4a4e-b7fb-d4ecc8a83ecb`.

## Assistant: decisions

The numbers are the items of addendum (1) of ADR-0093; items 1–3 — [V/10](../10-assist/README.md). The page panel is removed (addendum (8) item 2): where an item speaks of
a `PUT` write, the write is now the client's `POST /devices/update` (chapter 7 Н1.3), items 6, 10 are history.

4. **The executor** is `backend`: there is no panel; the plan check is a pure function of `backend` (addendum (8) item 2).
5. **The plan format** is V/11's own format with the note «кандидат в общий формат массовой правки» ("a candidate for the common bulk-edit format"); the selection, the checked changes and
   the reasons are separated.
6. **Applying** — the edits of a row by one `PUT` with the original `revision`; duplicates and contradictory assignments of a field — a plan refusal;
   an outcome per row; there is no repeat with a fresh `revision`.
7. **A secret** — the type of a plan value is only whole in the `to` of a declared `*_secret`; otherwise a refusal without confirmation; the password is
   a separate form field.
8. **The confirmation and «named»** — the «named» algorithm and the selection check are in the harness package; the confirmation is the admin's answer
   to `ask_admin`, not a separate pair (changed by addendum (3) item 1).
9. **Reading** — full lists, the selection in `backend`; an error or a limit — `refuse`; the right to apply is `admin`, `may` is
   preliminary.
10. **The platform** — `api(…, {ifMatch})` of the module and `features` `api.if-match` (ADR-0091 addenda (28), (29): only `PUT`, `DELETE` on
    `/<rows>/<id>`); nothing else is to be asked for.
11. **Acceptance** — the vectors are the `backend` driver (V/11.7 Н5); the model stub — V/10.2 Н5.

Accepted in the plan as is (the analysis, row 12): the targets of the plan are a closed list.

**ADR-0093 addendum (2)** (the Kimi review):
1. `assist` and lesson V/10 are written into the listings of ADR-0090 addenda (2), (3), (5) — `VMS/README.md`, `common/lessons.tsv`.
2. Reading — `GET /{rows}` whole, the selection — in `backend`; a large cluster — the list limit and `refuse`.
3. The plan check: the minimum of ADR-0093 item 5 is a normative floor, the harness package only adds to it. The selection condition is not reconciled in meaning with
   the request: completeness — against the computed selection, a substitution of the condition — «Применить» ("Apply") of the shown version with the selection
   block (addendum (3) item 2). An empty edit (`from = to`) is a plan refusal (V/11.11).
4. The model door — [V/10](../10-assist/README.md).
5. The plan format promises neither idempotency nor a check without a write — only a partial application by rows (V/11.11, V/11.12).

**ADR-0093 addendum (3)** (the harness handover package):
1. The admin's confirmation is the answer to `ask_admin`, its text is written by `backend` from the person's input; «named» = the request ∪
   the answers of this turn, the reconciliation is on every plan version; there is no separate checkbox of the pair (changes addendum (1) item 8; V/11.9 Н1.4,
   V/11.11 Н1.4).
2. A substitution of the selection condition — «Применить» ("Apply") of the shown version: the condition in words and the number of units as a separate block above the diff
   (V/11.11 Н1.7).
3. The turn limit is 25 model calls; beyond the limit — «ход не завершён» ("the turn is not finished") with the last reason, not `refuse` (V/11.9 Н1.4).
4. Measurements — one run per setting; the evaluation suite is lesson information.
5. Harness checks above the floor (the selection condition by the words of the request) are an addition, allowed by addendum (2) item 3 (V/11.11 Н1.8).
6. What the pilot did not measure is lesson information, not norms: «Measurement gaps» below.

**ADR-0093 addendum (4)** (the analysis of the review of addendum (3) and of V/11.9–V/11.11 — Codex, Claude, Kimi):
1. A secret lives with the shown plan version until applying or a reset, not until the end of the turn (V/11.12 Н1.3).
2. The limit is 25 model calls between the admin's texts; restarts on 410/404 — no more than 2 (V/11.9 Н1.2, Н1.3).
3. `bool` and the removal of a value are named by the polarity words of `words.json`; there is no exception from «the value is named» (V/11.11 Н1.4).
4. The write right is the capability of the write door (`need`): `admin` on the unit; one rule everywhere (V/11.10 Н1.2).
5. The floor is strengthened: the names of `named` and string values — «name in the text», a short word — whole, `stop` (V/11.11 Н1.2, Н1.4).
6. A call written as text is not executed (V/11.9 Н1.4).
7. The edits of the measured harness are listed in «Edits after the measurement» below.

## Assistant: harness

The pilot's handover package (ADR-0093 item 8): tools v4.0, a loop with `tool_choice: required`, the system text in English;
the model gpt-oss-20b, weights Q8_0, llama.cpp, the window 16384, reasoning `medium`. The content is moved into the lesson, without the paths and
settings of the pilot's machine:

| Lesson file | What | Norm |
|---|---|---|
| [`harness/system.md`](harness/system.md) | the system text | V/11.9 Н1.2 |
| [`harness/tools.json`](harness/tools.json) | nine tools: names, descriptions, argument schemas | V/11.10 Н1.1 |
| [`harness/words.json`](harness/words.json) | locale data: the verbs of a list edit, the polarity of `bool` and of removal, the service words `stop`, the expressions «нет прав» ("no rights"), «не найдено» ("not found"), «все» ("all"); the captions and the operator words | V/11.10 Н1.4, V/11.11 Н1.2, Н1.4 |

The check rules (the tables and the pseudocode of the package) — V/11.11 Н1.2–Н1.5; the loop policy — V/11.9 Н1.2–Н1.4; the overview — V/11.9
Н1.2.

### Edits after the measurement

The measurement is of the pilot's package as handed over; the lesson changes it (ADR-0093 addendum (3) item 6, addendum (4) item 7). The listing is the same as in
V/11.9 Н1; a repeated measurement — by an assignment to the pilot on the owner's word.

1. The cluster overview — as the first `user` message, not in `system`.
2. The secret label — `{"secret": N}` and the message «Secret N is entered» instead of a text slot; `system.md` and the note of
   `get_manifest` — about the label.
3. The admin's answer is the result of `ask_admin`, the turn does not end with it; the description of `ask_admin` and `system.md` — about the same.
4. Tool names — without the pilot's prefix; `system.md` — «Use only the tools you are given».
5. The description of `list_table` — an example of the table `rec`; `tools.json` ends with a newline.
6. A call written as text is not executed; a prompt without a call counts towards the 25 (addendum (4) item 6).
7. The «named» reconciliation is strengthened (addendum (4) items 3, 5): the names of `named` and strings — «name in the text», a word shorter than 4 letters — whole
   or with an ending from `endings` (a decision of «Архитектор» by the measurement), `stop`, the polarity of `bool` and of removal; the error words «ask the
   admin so that the answer itself names…».
8. The data of `words.json`: Russian strings; `rights`, `not_found`, `all` — with boundaries and forms; `polarity`, `endings`, `stop`;
   the VMS operator words (`fields`, `options`, `units`).
9. The right is the capability of the write door (`need`), not `edit` (addendum (4) item 4).
10. An accepted `ask_admin` stops the calls of the answer, the unexecuted ones get `not executed`; the window does not shorten the results of `ask_admin`;
    restarts on 410/404 — no more than 2.
11. The overview — without the name and the grants of the session: the model sees the rights by the `can_edit` of the units; the coverage — V/11.10 Н0 (ADR-0093 addenda (5), (6)).

**Replay without a model** (2026-10-28): all 175 tool calls of the base runs (six sets of stand 3) went
through the panel core — the tools and the lesson's check — on the console of stand 3 (the `edit` grants raised to `admin`, edit 9).
They matched the pilot's verdict in 173 of 175 before the translation of the form; after it (the mark R20) — 174, L07 differs. Both differences are due to the edits: R20 — a plan with the pilot's secret slot; with the label
`{"secret": 1}` (edit 2) it passes; L07 — `named: ["Spruce"]` for the request «Remove the label floor2 from all
counters»: the unit name is not named in the request, the plan is rejected by the rule `named` (edit 7). Without `endings`, another
five correct plans would differ («tag» against «tags»: H03, K02, L02, M07, N06). Words: «tag» ~ «tags» and «тег» ~ «теги» — yes; «все» ~
«всегда», «при» ~ «приоритет», «дня» ~ «дней», «день» ~ «дней» — no.

### Evaluation suite and measurements

Lesson information, not acceptance (ADR-0093 item 7, addendum (3) item 4). The pilot's stand 3: data and requests in English, 60 requests in
six sets — the main one (20) and the deferred ones (8 each); by kind — plan 39, refusal 9, clarification 8, «таких нет» ("there are none") 4. The evaluation is by
the accepted plan and the answer call: plan — the accepted plan equals the expected edits; refusal — there is no plan and there is `refuse` or
`ask_admin`; clarification — `ask_admin` without a plan; «таких нет» ("there are none") — there is no plan and there is an answer; ◐ — a correct clarifying question instead of
a plan. One run per setting:

| Setting | ✔ of 60 | ✔ + ◐ | Median turn |
|---|---|---|---|
| v3.8, Russian system text | 48 | 55 | 30 s |
| v3.8, harness in English | 56 | 59 | 26 s |
| v3.8 + a checker (2 returns) | 52 | 55 | 27 s |
| v4.0 | 54 (2 — a parse failure of the model server) | 59 | 29 s |
| **v4.0 + `tool_choice: required` — the lesson's base** | **56** | **59** | **29 s** |

The base by set: the main one 19/20, the deferred ones 6/8, 8/8, 8/8, 8/8, 7/8. The seconds are the pilot's laptop (≈ 39 tokens/s);
the ratios are transferable, not the seconds. Without a model: the calls of 164 past turns, rerun on v4.0 — 13 answers are no longer
accepted (all wrong, or right only by the evaluation); the expected plans pass the check 39/39. The checker and «best of
N» of the base are switched off: their failures were answers that the check accepted; the check in the tools closed them.

### Measurement gaps

Not measured by the pilot; they do not change the norms (ADR-0093 addendum (3) item 6). A new measurement — by an assignment to the pilot on the owner's word.
1. **The overview as a `user` message** within the turn, without a common cache between people (V/11.9 Н1.2) — the accuracy and the time of the turn.
2. **Language**: Russian requests on the English harness; the `display` captions of the VMS manifests are Russian; the Russian strings of
   `harness/words.json` (verbs, «нет прав» ("no rights"), «не найдено» ("not found"), «все» ("all")).
3. **The secret label** `{"secret": N}` and the message «Secret N is entered» instead of the pilot's text slot.
4. **The answer to `ask_admin`** as a result in the same turn — the pilot ended the turn with a question; «named» by the answers.
5. **The size of the overview** of eight VMS subsystems in the window 16384 and the memory of the model server (V/09).
6. **The model** (the package, «Пробелы» ("Gaps")): a word of the request linked to a label of a linked unit («second floor» — a label of
   a counter, the model looks for a shelf); «шаг по умолчанию» ("the default step") — `missing`, the model takes `eq 1`; occasionally an extra question where everything is
   named.
7. **VMS field captions**: `display.fields`, `field_help`, `options` of the manifests 01–07 and the VMS operator words in
   `harness/words.json` (`fields`, `options`, `units`; Russian and English) — the series of 2026-10-28; not measured by the pilot.
8. **Rights**: the pilot checked scopes by labels and `edit`; the lesson — `may` of the module with all scopes and the write door capability
   `admin` (P/07 Н1.5, addendum (4) item 4) — not measured: with `edit` grants the model will see `can_edit: false`.
9. **Edits after the measurement** (above) — not measured; the classes that the words reconciliation lets through — by the vectors of V/11.11 Н5 with the note
   «нарушено, но проходит» ("violated but passes"): «дней» ("days") names both `retention_days` and `min_depth_days`; «поток» ("stream") — `profile`,
   `live`; the words of the link field `rec.cam` («камера, которую пишет запись», "the camera the recording records") name the linked unit in the rule
   «как у связанной» ("as for the linked one"); `not_found` does not see «нет такой камеры» ("there is no such camera"), `all` — «весь», «вся» ("all", masculine and feminine).
10. **Numeric ids**: `cam` has a number as its id, the admin names a camera by name («Вход»); `named` (the name in the text is the id) does not
    fire for cameras, the model needs `where` by the name field — the pilot had names as ids, not measured (the vector `vms-named-id`).
11. **Coverage** (V/11.10 Н0): the assistant edits `cam`, `rec`, `det`; the others — «нет в охвате» ("not in scope").
12. **Words about rights in the overview**: `harness/system.md` and the overview header speak of the admin's rights; in the overview after edit 11 there is
    only the note `session.note`; the bytes have not changed, the model has not been measured on these words.

## Acceptance

Acceptance is the consolem API tests (`tests/api-*.js` at the pinned commit) against the stand in the capabilities profile and our own suite
[`acceptance/`](acceptance/) of what these tests do not see (ADR-0094 addendum (17); chapter 6 Н5); `?selftest` is a check of the build by the product under our CSP (ADR-0094
Confirmation; chapter 6 Н1.4). The profile is the lesson table [`data/profile-tests.tsv`](data/profile-tests.tsv) (V/11.6 Н1.2); it is reconciled at a new contract version.
The assistant — the vectors [`plan-check`](vectors/plan-check/README.md), [`turn`](vectors/turn/README.md), [`rules-words`](vectors/rules-words/README.md), [`zone-mask`](vectors/zone-mask/README.md) (the zone raster, V/11.3 Н1.3), executed by the `backend` driver (V/11.7 Н5), the model stub — V/10.2 Н5.

## Open questions

1. **The reference suite of the stand** (V/11.6 Н1.3) — our own, as lesson data **after stand B** (ADR-0094 addendum (3) item 10 (4)).
2. **What is not declared for rules**: `recordMode: sched` — the field `recordScheduleId` is in the contract, there is no recording schedule row in the norms of V/02, V/07 (V/11.3 Н1.3). A `Rule` of several clusters: `ruleCrossDomainActions` is empty, `Rule` does not express this (V/11.4 Н1.10).
4. **Questions to the product with the increment of rights**: the password of a new
   person (`AccessUser` has no field, V/11.8 Н1.5); which levels show detectors; folder management; `MON_PROT`; the pair `MON` and `ONLY_ARCHIVE`
   (ADR-0097, ADR-0099, ADR-0100, «Запрос продукту»). `kindAccess.arch: FULL` with `kindAccess.cam: MON` does not become a line and is read as `FORBID` (V/11.8 Н1.4).
5. **A version that can come back** (V/11.4 Н1.1: the parts `h`, `i` do not go by guards and can also return the concatenation; the rights snapshot of V/11.8 Н1.1 is the same if a row was created and removed): the streams of a camera and the recordings of a volume enter the version as live rows —
   their tombstones cannot be found by the camera or the volume; creating and removing such a row bypassing `backend` returns the former concatenation
   with the same visible record. The product's strict «does not come back» does not hold here.

7. **`probe` without credentials** (V/01.8 Н1.3, V/11.4 Н1.9): `DeviceProbeRequest` has no login and password, auto-detection needs them; a device that does not name the model without a login gives `model: null`. There is no answer from consolem (inquiry 9, supplement item 4).
8. **What the pinned contract does not express** (V/11.3 Н1.3): the source `replica` and the backup `backup` wait for a new commit of the contract (ADR-0107). The action `unit` of a rule (V/11.3 Н1.3): we have no place for it.

## Order of work

1. V/11.1–V/11.7 — norms (as text now, ADR-0094 «Порядок» item 3).
2. The platform norms B1–B7, B9 — exported, the repin of V/11 is done (ADR-0094 «Порядок» item 2); next — the stand and the tests
   of the product (chapter 6).

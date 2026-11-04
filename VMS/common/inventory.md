# Inventory of the VMS layer: chapters М10B, М12A, М12B → lessons `VMS/` and the platform

This English text is the source; the Russian translation `ru/inventory.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The first task of «Спецификация VMS» (ADR-0090 addendum (4)); «Архитектор» checks it. The platform is the export `cammeta-specs`
`afb1c88` (course `0d0b393de`; compiled against `c9447b3`, no difference for VMS — «ХОД»); the addresses `P/NN.K Нx.y` were checked by search, `Platform/` of the course was not read. The
inventory does not set norms: it names the owner of every chapter and step, the decision on every name with «vms», the path of the work of `vmsjobs`, the keys
of the section `domain:`, the gaps of the platform and the divergences of the lessons from its norms. The translation of a lesson takes its rows from here; anything new
found during the translation is entered here by the same change.

Notation: `V/NN` — the lesson `VMS/NN-<имя>`; `P/…` — a platform norm by reference (not carried into `VMS/`);
`P/? —` — a platform matter, the export has no norm (a candidate for a request, § 6); «drop» (Russian «снять») — not carried over (the reason is in the row).
The rules of addendum (4) are «item N»; other grounds — by ADR. Implementation code (packages, modules, classes, tests, the witness's Quadlet)
does not become a norm (ADR-0080) — such rows are gathered into one row per chapter, not by steps.

## 1. Lessons and their sources

| V | Lesson | Sources (chapters and steps) |
|---|---|---|
| 01 | `01-cam` | М10B/01 (except 4 — video retention, 7–8 — code); 03, 04 — the VMS half; 05; 09 — delivery and the holder's pipeline; 15 — the device archive and its doors; 19; 26 step 7 (the declaration `near`), step 10 — the camera pusher; 28 step 1 (the budget formula); М12A/03 — the branch, the attachment point; М12A/05 step 4 (the licence — an open question, § 6); М12A/10 — the heartbeat and the row of the camera-cluster; М12B/01 — the keys `cam.domain`; М12B/02 step 3; М12B/03 — the pusher, the tokens `stream`, `poll`, `ask`, `taken_by`, three channels |
| 02 | `02-rec` | М10B/01 step 4 (video retention); 06; 07 (except the camera events); 08; 09 — the receiver's actuator; 10 — the VMS half; 11 steps 4–5 (the declarations `holds`, `free`, the answer `freeing`); 15 steps 7–9; 16; 18; 20, 22 — the `rec` halves; 24 (except the shell); 26; 27 — the VMS half; 28 steps 2–6; М12A/10 — the card; М12A/12 — the receiver's request door; М12A/13; М12B/01 — the keys `rec.domain`; М12B/02; М12B/03 — the receiver, catch-up recording, the ring, the backup; М12B/04 — the media of the chain |
| 03 | `03-live` | М10B/13; М12A/03 — the gateway and one subscription; М12B/01 step 6а (RTSP accounts, `names`); М12B/03 step 4 (the gateway looks into the receiver), `live_road` |
| 04 | `04-det` | М10B/14 |
| 05 | `05-detjob` | М10B/20 — the `detjob` half; 21 (except steps 3–5, 7, 8 of the mechanism); 22 — by reference; 23 step 2 (`fetching`) |
| 06 | `06-detedge` | М10B/23 (the transition `survey` → `detedge`, item 7) |
| 07 | `07-auto` | М10B/25 (except steps 3, 8 of the mechanism); 11 step 6 (which `want` are named); 12 step 12 — what the form offers; М12A/12 — the shared document, the book `asks`; М12B/03 step 8 — the scenario executor, refusals; М12B/04 step 7 |
| 08 → 11 | `11-backend`, chapters 15–19 (ADR-0118) | М10B/12 — the shell and the assembly (`cam.shell.html`); 24 step 9 — playback in pieces; 25 step 4а — the form «Сценарии»; references to the doors of lessons 01–07 |
| 09 | `09-deploy` | М10B/17 — the image (step 7), the environment of the subsystems, budgets, processes as clients of services (step 6), the health check (step 10); М12A/05 steps 1, 2, 5; М10B/28 step 1 — the values of `CAPACITY`; the layout of the subsystems' environment files |

Entirely platform (by reference, not in `VMS/`): М10B/02 (P/03.3), М10B/11 (P/05, except the declarations). Navigation and notes
— § 2 «Module files outside the lessons»: М10B/README, М10B/module-design, М10B/«СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ» (V/02), М12A/README,
М12B/README and module-design. М13, М14 — outside `VMS/` (addendum (2)); step 3 of М12A/05 and the issue of the licence — М14.

## 2. Inventory by chapters

### М10B/01 «Первая подсистема»

| Step | Owner | What / basis |
|---|---|---|
| 1 | P/02.1 Н1.2; P/06.1 Н1.1; P/06.5 Н2 `metrics.prefix`; P/02.5 Н1.4 | what `name` gives |
| 1 | V/01 | `slot {prefix: w, name_env: WORKER_NAME}` (the form of P/03.2 Н1.4); the table `devices` |
| 2 | V/01 | `rows: cameras`, `id: numeric`, the words of `display` (the mechanics — P/06.1 Н1.1, Н1.3; P/06.5 Н1.2) |
| 3 | V/01 | the camera fields, `folders` without `loc:`, `ref unique` (the mechanics of fields — P/06.1 Н1.2, Н1.3) |
| 3 | P/? — | substitution of `{id}` into `default` (`cam{id}`): P/06.1 Н1.2 takes the value literally (§ 6, № 1) |
| 4 | P/02.4 Н1.9; P/05 Н1.3 | `cam/retention`, `cam/alarms_retention` (ADR-0076); video retention — V/02 |
| 5 | V/01 | the placement values of `cam`; the meaning of the keys — P/04 Н1.3; `offers` — drop (there are no spares, ADR-0084) → `grows` |
| 6 | P/04 Н1.3а | the snapshot; the list `snapshot`, `console.running` — V/01 |
| 7–8 | drop | the code of the witness's catalogue and controller — drop; the catalogue — P/02.1 Н3, the controller — P/02.4 Н1.1 (`w2c-controller@cam`) |
| «Не так» | V/01; P/06.1 | the status in the row, the cascade — P/06.1 Н1.1; a codec field, one retention — V/01 |

Divergence: the snapshot ceiling in the lesson and the manifest is 64 KiB, in P/04 Н1.3а — 64 MiB; the argument «`folders` are not in the snapshot
by measurement» is revisited by V/01 (§ 7).

### М10B/02 «Цикл сверки» — the platform in full («ГРАНИЦА» §2.8)

| Step | Owner |
|---|---|
| «Зачем» | P/03.1 Н2, «Решает реализация» item 1 (the reconciliation helper is optional, ADR-0033) |
| 1 | drop — code (`Want`, `Pass`) |
| 2–4 | P/03.3 Н3 «цикл()» step 2 (the order stop → restart → start, a restart under the same epoch) |
| 5–6 | P/03.3 Н1.2 `retry` (ADR-0091 item 6) |
| 7 | P/03.4 Н1.1 `stalled`; the states `converged`/`lagging` and the lag as a number — there is no norm, not carried over (chapter 02 is platform in full) |

### М10B/03 «`camworker` I: процесс»

| Step | Owner | What |
|---|---|---|
| 1 | P/02.4 Н1.2 | `WORKER_NAME`, `SERVER_NAME`, `LABELS`, `INSTANCE_ID`, `BOX_ID`, `RESOURCE_ROOT`, `CAPACITY` (`roles/<роль>.env`); `SLOT_INDEX`, `SPARE_FOR` — drop |
| 1 | V/01 | `SHM_DIR`, `RTSP_*`, `PLAYBACK_*`, `RTP_BASE` (the file `cam`; shared with `rec`, `live` — addendum (6) item 5); the values — V/09 |
| 1 | P/? — | a check of the words of `LABELS` against the alphabet (§ 6, № 2) |
| 2 | P/03.2 Н3 «старт()»; P/03.1 Н2 | the capture, `start_unit`/`stop_unit`; the takeover — P/03.4 Н1.1 |
| 3 | V/01 | `desired` (without `on-demand`, `held_back`); one session per device |
| 3 | P/03.3 Н3 step 2 | the assignment and the rows on every pass, the tombstone |
| 3 | P/? — | a broken unit row at the worker: «what ran keeps running» (§ 6, № 2) |
| 4 | P/03.2 Н3 «взять_эпоху»; Н1.6 | the gate, the epoch at start, bring-up under the same epoch (ADR-0091 item 6) |
| 4 | V/01 | `enrich` — the delivery addresses; the row is not `camera` |
| 4 | P/03.5 Н3 «открыть»; P/06.2 Н1.4 | opening the secret; the order (the secret before the epoch, `may_act` before the start) — by the platform (§ 7) |
| 5, code | drop | `FakeActuator`, the class attributes, the monotonic clock — code |

### М10B/04 «`camworker` II: держать камеру»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1 | V/01 | to hold, not to write; the row is not `camera`; the worker token and `worker.writes: [devices]` (the mechanics — P/02.5 Н1.4, P/06.1 Н1.6) |
| 1 | P/04 Н1.3 `group_by`; P/06.2 Н1.1 | the channels of one host — one worker (the declaration of V/01) |
| 2 | V/01 | two delivery branches, loopback, `local_only`, `live_port`; `RTSP_HOST` of the deployment — V/09; `near`/`home` — P/04 Н1.3 (the declaration of V/01, the anchor of V/02) |
| 3 | P/03.6 Н1.2 | writing an event under the epoch, suppression; `class_of`, `silent`, `observed` — V/01 |
| 3а | P/06.4 Н1.5, Н3; P/03.6 Н1.5, Н3 «взгляд держателя», «Действие устройства» | the request family, the label before the call, one call per group (ADR-0091 item 6) |
| 3а | V/01 | the section `requests:` (`output`, `preset`, 30/600, `stamp group`), `perform`, `ARG_MAX`, the number `COMMANDS_BEAT` |
| 3а | drop | the hooks `held_rows`, `request_target`, `moved_refusal` («ГРАНИЦА» §4) |
| 3а | P/? — | the event rows `command`/`command.failed` (the words — only in P/07) (§ 6, № 3) |
| 3а | § 7 | «device not open»: the lesson waits, P/03.6 — `refused`; the lesson accepts the platform |
| 3б, 4 | V/01 | queries to the device outside the loop thread, `DEVICE_GRACE`, the bus, `silent`; the pump — P/03.3 Н3 step 3, P/03.6 Н1.2 |
| 5–7 | P/03.4 Н1.1 | the platform fields in the heartbeat and `status`; `headroom` is computed by the platform |
| 5–7 | V/01 | the phase words, `devices`, `devices_slow`, `playback_key` (`heartbeat.strings`) |
| 5, 7 | P/? — | `lease: unconfirmed`, `unconfirmed_s`, `assignment_rev`, `passes`, `store_errors`, `pass_failures`, `was_fenced` in the heartbeat (§ 6, № 4); `alloc` — drop (there is no reader) |
| 8 | P/03.2 Н3 «шаг_аренды()», Н1.6 | the silence of the store; `unconfirmed_max: forever` and the argument — V/01 |
| 9 | P/03.2 Н3 «отсечь», «никто и возврат имени»; P/06.5 Н3 | the fence, the return; `fence_units` and others — drop (hooks) |
| 10 | P/03.3 Н3 «цикл()»; P/03.1 Н2 | the loop; EOS at stop, the driver host 15 s — V/01; `StopTimeout` — § 6, № 5 |

### М10B/05 «`driverpacksrc`» — V/01 in full

Parsing `driverpack://`, the real-time pace, the refusal `uri`, PTS, registration — V/01; the address mask — P/06.2 Н1.1а;
backoff — P/03.3 Н1.2; the internals of the bin — drop (code). `MEDIA_DIR` — § 3.

### М10B/06 «ObjectStorage: движок архива и клиент»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1–5, 8–11, 13–14 | V/02 | the contract `obsd`: the host process, the frame, the session, break and silence, archive time, `video()`, blocks, the ring, the epoch in the name, the timeline by windows |
| 1 | P/02.4 Н1.1; P/02.1 `parts` | the service of the part `vms-rec-obsd.service` (ADR-0091 item 5); the manifest `rec` needs `parts.obsd {exec, volumes: true}` — V/02 |
| 1 | P/? — | the recorder's access to the socket of its part (§ 6, № 6) |
| 4, 6 | V/02 | the call timeout is shorter than the lease window (the bound of P/03.2 Н1.6), the client name `rec-<слот>` |
| 7 | V/02 (acceptance) | a live daemon; the test harness — drop |
| 12 | V/02 | one writer, the grace; the uniqueness of the place — P/03.2 Н1.2, Н1.3, Н3 «место» |
| 12 | P/? — | the environment of the part (`OBSD_WRITER_GRACE_S`) and the `TimeoutStopSec` of the part (§ 6, № 5) |

«ГРАНИЦА» §2.8 item 8 (the witness's object-storage module with `video()` in the platform) is closed: the export has neither `obsd` nor ObjectStorage.

### М10B/07 «Том, блок, последовательность, поток»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1 | V/01 | the event buckets `cam/<cam>/` are written by the holder (the form — P/05 Н1.2, the writer — P/03.6 Н1.2); the cleanup — P/05 Н1.3 |
| 2–4, 6–11, 13 | V/02 | the stream name `<запись>/e<эпоха>`, `…/backfill`, a segment from the index, the refusals `wrong/away/busy`, opening a volume, `RecSink`, `appsink`, the loss of the daemon |
| 5 | P/06.2 Н1.1, Н1.1а | an address without login and password |
| 5 | P/? — | opening `access_secret` of a row of the places table (P/03.5 knows only the unit row) (§ 6, № 7) |
| 7 | P/02.1 `objects.rows`; P/05 Н1.1 | `rec/used/*` |
| 7 | P/02.4 Н1.1 `dirs` | own volume → `/data/platform/subsystems/rec/obsd/volumes/<n>` (ADR-0091 item 4) |
| 8 | P/03.2 Н1.2, Н3 «место» | not a single frame without a confirmed place in the recording window |
| 12 | P/03.4 Н3 «остановка по SIGTERM»; P/03.2 Н3 | a killed recorder, the stop order (the lesson's comment «slot → writer → place» contradicts the platform — § 7) |

### М10B/08 «Видимость, срок, таймлайн» — V/02, except:

`/where/<id>` and the door token — P/06.5 Н3, P/03.4 Н3 «токен двери у держателя»; `/where/<table>/<place>` — P/06.5 Н3;
`url` in the heartbeat — P/03.4 Н1.1 (not `0.0.0.0` — P/? —, § 6, № 8); `cam/retention/<cam>` in the text is outdated → P/05 Н1.3
(`<sub>/retention`, ADR-0076); the keeps `keeps` — V/02, the buckets are held by `holds` — P/06.4 Н1.5; `safe_segment`,
`send_route`, `stitch`, `finite`, `Table` — drop (code). Zero days with `retention_days.minimum: 1` — V/02 (§ 7).

### М10B/09 «Актуаторы и раздача»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1–8 | V/01 | the holder row, `tee`, `watchdog`, `leaky`, RTSP not multicast, delivery after `PLAYING`, `describe`, observation from its own element; the media host `ipintd` — a remark about the product, not a norm (addendum (4)) |
| 1 | P/03.2 Н3 | an epoch per unit |
| 2 | P/03.3 Н3 step 2 | bring-up of a crashed process (ADR-0091 item 6) |
| 6 | P/03.1 Н2 | the actuator surface; classes, lambdas, `MainLoop` — drop |
| 8 | P/03.6 Н1.2; P/05 Н1.2 | observation → an event row |
| «Зачем», 1, 3, 6, 9 | V/02 | the receiver's actuator: its own epoch, `appsink` without loss, the bus, `REC_SINK`, `drain`, `on_sample`, the backup ring, `REC_RANGE_DESC` |
| 9 | P/02.4 Н1.1; ADR-0091 item 5 | the shared-memory directory — a share of `cam`, at `rec` — `worker.uses` (§ 3) |

### М10B/10 «`recworker`»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1, 2 | V/02 | the recording as a unit, `id: name`, the placement values (the meaning of the keys — P/04 Н1.3; `idle_by_policy` — P/06.5 Н2; `ensure_home` — P/04 Н3 step 7) |
| 1 | P/06.1 Н1.3 | `about`, `fixed`, `ref`/`must_match`; `until` → `placement.ends` (ADR-0091 item 2) |
| 1 | V/11 | the rule for the name of the first recording on the page |
| 2 | V/01 | `near: rec`, `home: near` at the camera |
| 3 | P/03.2 Н1.2, Н1.3, Н3 «место» | a volume as a place, holding by CAS, the recording windows, own place, a place behind a name, a torn row |
| 3 | V/02 | the table `volumes`, the kinds, pinning `$VOLUME`, the quota, the volume key not in the address, `WRITER_ABANDON`, the third state |
| 3 | drop | a recorder without a volume as a «spare» (ADR-0084); the rest — `place_by: ""` (P/04 Н1.3) |
| 3 | P/? — | `access_secret` of a table row (§ 6, № 7) |
| 3, 9, 11 | P/03.2 Н3 «место»; ADR-0091 item 9 | releasing a place in the middle of work — decided by a refusal with a workaround (`inbox/2026-10-22-запрос-vms-места-в-библиотеке.md`): the lesson follows the norm (§ 7) |
| 3 | § 7 | the volume did not open: ADR-0091 item 9 — `place_by: ""`, the lesson holds the volume with zero capacity |
| 4 | P/03.2 Н1.4; P/03.3; P/03.4 Н1.1 | the slot, the loop, the heartbeat; the class and the constants — V/02 |
| 5–9, 11–13 | V/02 | the source from the heartbeat of `cam` and from the book `domain/cam/sources` (V/01), the start refusal, resubscription, mounting, refusals, leaving a volume, the writer watchdog, the depth |
| 7 | P/06.5 Н3 | a piece from a volume of another recorder through `/where/<table>/<place>` |
| 10 | P/03.4 Н3 «подмена()» | substitution extends the strict place (cas under the guard of its own slot); `may_stand_in_hold` and the lesson's `FOR` count — a divergence from the norm, the lesson follows it (§ 7) |
| 11 | P/03.4 Н3 SIGTERM | the regular stop; `TimeoutStopSec=40` — § 6, № 5 |
| 13 | P/06.5 Н3 | the series from the heartbeat; the recorder's own `/metrics` — drop (the series are declared by `metrics` of the manifest) |
| 14 | V/02 (on the domain) | the receiver and the forwarder in the recorder; the report `rec/polled` — the mechanism of P/09.1 Н1.2, P/10 Н1.8; `rec/ingest`, `rec/forwarded/*` — drop (ADR-0003) |

Open for V/02: who brings up a recorder for a volume without a holder — P/04 Н3 «нехватка(), заказать()» for `servers: distinct` with a place from the heartbeat (acceptance P/04, sc. 17) with `grows: true`; whether to declare `grows` at `rec` — a choice of the V/02 manifest;
the rights of `_held_by_the_book` on `cam/placement`, `cam/slots` (not in `worker.reads`).

### М10B/11 «Процесс ресурса» — the platform (P/05)

The process, the unit `w2c-resource`, the pass, the root, the groups — P/05 Н1.4, Н3; P/02.4 Н1.1, Н1.2. The trees `<sub>/…` — to the lesson
of the subsystem (`cam` V/01, `rec` V/02, `det` V/04, `detjob` V/05, `detedge` V/06, `live` V/03, `auto` V/07). The common retentions —
P/05 Н1.3, P/02.4 Н1.9. The declaration `holds` — V/02; its meaning — P/06.4 Н1.5 (ADR-0091 item 8). `about` — to the lesson of the manifest.
The waterline, `free-<server>-<volume>` — P/05 Н1.4; `requests.free`, the answer 0 — V/02; the form of the field `freeing` in the heartbeat —
P/? — (§ 6, № 11). `/events/wait` — P/05 Н1.6; which `want` the evaluator names — V/07. `default`/`inherit`,
`on_delete` — drop (ADR-0076); Quadlet and the entry point — drop.

### М10B/12 «Страница VMS»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1 | P/06.5 Н1.1 `root`; P/02.4 Н1.1 | the VMS console = the platform console with `CONSOLE_ROOT=cam`; the code of the witness's VMS console — drop |
| 1 (table) | V/01, V/02, V/03, V/07 | the fields and the tables — to the lesson of the manifest; server labels, decommissioning — P/06.6 Н1.1, Н3; a password in the address — P/06.2 Н1.1а; there are no byte routes — P/06.5 Н2, P/07 Н1.4 |
| 2 | P/06.5 Н1.1; P/02.3 Н1.5; P/07 Н1.5 | serving the root shell, nesting by `about` |
| 2, 3 | V/11 | the file `cam.shell.html`, `SUBS`, `mount`, `wire`, `data-act`, `esc`; CSP — P/06.5 Н1.1 |
| 4 | P/07 Н1.5 `adds` | the calls; the content of the badges, parsing `source`, the notes — V/11; the meaning of `device_state` — V/01; the event kinds — V/01, V/02 |
| 5 | V/11 | the core `whereAt`/`doorOf`/`doorFetch`; issuing the door — P/06.5 Н3; the token — P/03.4 Н3; CORS of the door (`DOOR_ORIGINS`) — P/? — (§ 6, № 12) |
| 6–11 | V/11 (rendering) | the scale, the pieces, the events, live video, «Архив», the volumes; the doors and the words — V/02 (`timeline`, `segment`, `keeps`, the volumes), V/03 (`POST /live/streams`, WHEP), V/01 (`yields`); merging the events — P/06.4 Н1.3; `/marks` — P/06.4 Н1.2 |
| 12 | V/11 (section), V/07 (`RACTIONS` = `then`, `ruleProblem`) | «Сценарии»; `/det/spec` → `GET /manifest` (P/06.5 Н2) |
| 13 | P/07 Н1.6; P/06.7 | the view `/domain`; `cam/crossings` — drop (ADR-0074, § 5); the nodes and the cards — V/11 |
| shell | V/03, P/06.7 | «Учётки потоков» (`live/accounts`), «Назначения записи» (`/domain/placement`) |

The lesson and the shell diverged (the book `primaries` at `rec`, «Назначения записи», «Учётки потоков»): the former page is removed (ADR-0112
addendum (19)), its witness is `Source/vms/cam.shell.html`; the canon `VMS/01-cam/cam.shell.html` is the root shell (V/11.15 Н1.1).

### М10B/13 «Живое видео» — V/03, except:

`slot` — P/03.2 Н1.4; 409 `exists`, the right `view` — P/06.1 «создать», P/06.3 Н1.5; `unplaced.delete_after` — P/04 Н1.3,
Н3 step 8; `offers`/`live_workers_needed` in the text → `grows`/`workers_wanted` (P/04 Н3, P/02.4 Н1.5, ADR-0084);
`worker.writes: [streams]` in the text → `worker.deletes` (the manifest canon); `DoorKeeper` — P/03.4 Н3; `take_epoch` —
P/03.2; the loop, the stop, returning the name — P/03.3, P/03.4, P/03.2; `door.issued` — P/06.5 Н3; finding the holder of a foreign
unit by the heartbeat (`holder_of`) and the limits of the door's server — P/? — (§ 6, № 12, 13); `GstPeer`, `gstvms`, `__main__` —
drop; the GStreamer packages in the image — V/09. The text of V/03 is written by the manifest (`tables: [accounts]`, `secrets`, `domain:`,
`door.pass` are not described in the lesson).

### М10B/14 «Детекторы» — V/04, except:

`about` — P/02.1, P/03.6 Н1.2; `mask: blob` — P/06.1 Н1.5; `until` → `placement.ends` (ADR-0091 item 2), `jobs.expire` —
drop; `near {by, of}` — P/04 Н1.3 (ADR-0091 item 10); `of`, `write_event` — P/03.6 Н1.2, P/05 Н1.2; `take_epoch`,
`may_act` — P/03.2; the event classes — P/05 Н1.2; the path of a detection to the screen — P/05 Н1.3, P/06.4 Н1.3; `platform_fields` —
P/03.4 Н1.1; the section `requests` (`detect`, `scan`) — drop, ordering by a row at `auto` (§ 4).

### М10B/15 «Архив, которого мы не писали»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1–6 | V/01 | `device_of`, `identity`, serial numbers, calls outside the loop, `playback_url`, `coverage`, the doors `/playback`, `/devices`, `/recordings`, reading in pieces, `max_playbacks`, `on-demand`, «the holder serves, the writer creates» (item 2) |
| 1 | P/04 Н1.3 `group_by`; P/06.3 Н1.5 | the host group, the rights by group |
| 1 | P/03.6 Н3 | one call per group (ADR-0091 item 6) |
| 3 | P/? — | protection of the holder's HTTP door (limits, timeouts) (§ 6, № 13) |
| 7–9 | V/02 | its own reading of `/spans`, `/samples`; the interval `source: device`, `yields`, subtraction (item 2, a consumer of the V/01 door) |
| 8 | P/06.5 Н3; P/03.4 Н3 | `/rec/where/<запись>`, the token |
| 8 | P/? — | the log of the holder's door (`archive.read`) (§ 6, № 14) |

Open for V/01: `DELETE /devices/<хост>` — a worker table, the console answers 403 (P/06.1 Н1.6); the lesson's advice
cannot be carried out (§ 7).

### М10B/16 «Дозапись из края» — V/02, except:

the request form (`schema`, `key`, `per_person`, `settle`, `ttl`, `stamp`, `journal`) — P/06.4 Н1.5, Н3, the request contract;
`fetched` in the heartbeat — P/03.4 Н1.1; filing by a process → filing by a worker P/03.6 Н1.5 (ADR-0091 item 7; filed by V/05, V/06);
`may_write` — P/03.2 Н1.6; `closed` for the detectors — § 4. The catch-up recording profile: the manifest `rec` has no
`requests.outcome: fetched`, while the lesson removes an unanswered catch-up recording by `ttl` — P/06.4 Н3 «жнец» says otherwise (§ 7).

### М10B/17 «На коробке»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1, 3, 4, 8, 9 | P/02.4 Н1.1, Н1.2, Н1.7 | the entry points and the units of the platform, mounts as ACL, groups, the worker template and the slot, `MANIFEST_DIR`, `CAPACITY`, memory, `/etc/<sub>` → a link, the order of the environment files, the registration of presence (P/03.2 «старт()») |
| 1 | P/02.4 Н1.1 | the worker units `vms-<sub>worker@` (§ 3) |
| 1 | P/? — | which command the worker unit starts (`parts` has `exec`, the worker does not) (§ 6, № 15) |
| 1 | drop | the verbs `python3 -m vms …`, `jobs`, `domainpart`, spares, `vms-scaler`, Quadlet |
| 2 | P/02.5 Н1.4, Н1.4а | the rights from the manifest |
| 3, 5 | V/01, V/02 + ADR-0091 item 5 | the share of `cam` for shared memory, the share of the part `obsd` (§ 3, § 6 № 6) |
| 5 | V/02 | the daemon `obsd` is one per host, not in a container, built with patches 01–07; `HELLO`; its own volume |
| 5 | P/? — | the environment and the `TimeoutStopSec` of the part; `After=` of the worker after the part (§ 6, № 5) |
| 7 | V/09 | one image, without pip; how many images and whether they exist at all under P/02.4 Н1.7 (`Source.new`, without containers) — decided by V/09 |
| 8 | P/? — | the path of the «subsystem file» (`W2C_SUB_ENV`) (§ 6, № 16) |
| 8 | V/02 | `ARCHIVE_*`, `OBSD_*` in the file `rec`; `SPOOL`, `SEGMENT_SECONDS` — drop |
| 6 | V/09; P/02.4 Н1.1 | the VMS processes are clients of the platform services (groups, setgid, umask — P/02.4; what the subsystem requires of a service — V/09) |
| 10 | V/09; V/02; P/06.5 Н3 | the health check of the deployment — V/09; the metrics `rec_*` — V/02; the mechanism of `/metrics` — P/06.5 |

### М10B/18 «Что архив отдаёт первым» — V/02, except:

`platform/space` — P/02.4 Н1.9, P/05 Н1.4; an alarm under the epoch — P/03.6 Н1.2; the metrics — P/06.5 Н3; the table `keeps`,
`stamp`, `made_at` — P/06.1 Н1.6 (the meaning of a keep — V/02); `unit_of`, `routes.edit` — P/06.3 Н1.5; `admits`, `affinity` —
P/04 Н1.3; `rec/sealed/*`, `rec/taken/*` — P/02.1 `objects`, P/05 Н1.1; issuing the door `verify` — P/06.5 Н3, the token —
P/03.4 Н3 (the door token gives read routes, `verify` is a POST: § 7); the log `archive.keep.verified` — § 6, № 14;
`holds` — P/06.4 Н1.5 (ADR-0091 item 8); the waterline — P/05 Н1.4.

### М10B/19 «Учётные данные камеры» — V/01, except:

`*_secret` not in the snapshot — P/02.1 Н1.3а, P/04 Н1.3а; `bound_to`, the refusal and the mask, `nested` — P/06.2 Н1.1, Н1.1а, Н3;
`mask_logs` — P/06.2 Н1.4; rotation through the revision — P/03.3 Н3 step 2.

### М10B/20 «Интервал архива» — split

V/02: the door `/spans`, `held_since`, `door_spans`, the rule «one moment — one epoch», `unserved_volumes`. V/05:
`recording_read`, `plan`, `Scan`, `covered`, `remaining`, `done_through`, the progress. The liveness of the door — P/03.4 Н1.1
`fresh_for`; the rights of the worker — P/02.5 Н1.4. The progress as a file `detjob/<job>/progress.jsonl` on the resource — a question for V/05
(the cursor `unit.state.cursor` or a file; § 7).

### М10B/21 «Задача — не поток»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1, 2, 8, 9 | V/05 | its own capacity, `STRETCHES_PER_PASS`, `missing`, `WAIT_MAX`, `fetching`, `following`, `VISIBLE_LAG_SECONDS`; `near {sub: rec, by: rec}` — P/04 Н1.3 |
| 3–5 | P/03.6 Н1.7; P/04 Н1.3 `retire_when`; P/02.5 Н1.4 | the result — `unit.state.result` is written by the holder under the guard of the epoch (ADR-0091 item 3); `reap`, «trust what is placed» — drop |
| 6 | P/03.6 Н1.7 | why the result is not in the heartbeat |
| 7 | P/06.4 Н1.2; P/05 Н1.3 | `older_epochs: earlier-run`; a broken epoch row — P/03.2 Н1.5 |
| 8 | P/03.6 Н1.5 | filing `ask_for_footage` by the worker `detjob` (`worker.requests: [rec]` — § 4); the execution — V/02 |
| 8 | drop | `MIRRORED`: the phase — in the heartbeat and in `state` at the console (P/06.1 Н2) |
| 9 | P/06.1 Н3 «Общая проверка строки»; P/06.3 Н1.5 | `fixed`, `must_match`, `reach` |

Lesson 21 step 9 (line 342) is a corrupted paragraph about `fixed` and `must_match`; it is restored during the translation of V/05 from the
history.

### М10B/22 «Две дыры, одна причина»

V/02 — one set of minutes, `kept == 0`, the logic of `scan_what_arrived` (which detectors, `params`, `labels`), a job per
pair «range × detector». The mechanism — ordering a row: `worker.creates` at `rec` → `detjob` (P/03.6 Н1.6, ADR-0091 item 1),
idempotence from the name, the tombstone (`made.gone` + 60); the window `CLOSED_REPORTED` and the pass `_reap_turn` — drop; merging
by `of` — P/06.4 Н1.3. V/05 — by reference. Repeating the order after `expired`/`refused` — a question for V/02 (§ 7).

### М10B/23 «Чужой архив» — V/06 (`survey` → `detedge`), except:

the placement keys, `near {sub: cam, by: cam}` — P/04 Н1.3; the index behind the door `/recordings`, the sessions `/playback` — V/01;
the object ceiling — P/06.1 Н1.4, P/05 Н1.1; the frontier `Frontier`/`frontier.json` → `unit.state.cursor` (P/03.6 Н1.7,
ADR-0091 item 3; the difference from the witness — the cursor survives a move); `keep_what_fired` — filing by the worker `detedge`
(`worker.requests: [rec]`, P/03.6 Н1.5); the execution of the request — V/02; `detjob` stopped promising `fetching` — V/05;
the timeline — V/11 (the shell), V/01 (the spans). Whether `per_person` applies to filings by a worker — a question (§ 6, № 17).

### М10B/24 «Интервал в браузере» — V/02, except:

`.device.mp4` from the holder — V/01; `/rec/where/…`, `door.routes` — P/06.5 Н3; the token in `?t=` — P/03.4 Н3; the domain member
`/domain/at/<кластер>/…` — P/06.7 Н1.6; playback in pieces (`PIECE`, `piecesFrom`, `playNext`) — V/08.

### М10B/25 «Автоматизация» — V/07, except:

| Step | Owner | What |
|---|---|---|
| 1 | P/04 Н1.3; P/03.2 Н1.5, Н1.6 | `requires`, `servers: shared`, `grows`, the epoch |
| 3 | P/06.1 Н1.2; P/02.1 Н1.3 | `schema:` json fields at the door (the mechanism) |
| 4а | V/01 | the row `cam/devices/<хост>` is written by the holder; the table — P/06.1 Н1.6, P/02.5 Н1.4 |
| 5 | P/06.4 Н1.3; P/05 Н1.3 | the merged log, `truncated`, `fenced` |
| 6 | P/03.6 Н1.7 | the cursor → `unit.state.cursor`; release and take again — P/03.2 Н3; the loop — P/03.3 |
| 8 | P/03.6 Н1.5; P/02.1 Н1.4; P/06.4 Н3; P/06.3 Н1.5; P/06.1 Н1.3 | filing a request, `valid_until`, `cluster_rows`, `names`, `must_match` (the mechanism) |
| 9 | V/01 | the relay and the preset are executed by the holder |
| 9 | P/03.6 Н1.6; P/04 Н1.3 `ends`, `retire_when.delete_after` | `record`/`detect`/`scan` — rows set up by the orderer (ADR-0091 items 1–3); the logic of the claim — V/07 (addendum (7) item 1) |
| 9 | drop | `Remembered`, `_requests_loop`, `ended_by: jobs` |
| 10 | P/05 Н1.6; P/03.3 Н1.2 | `/events/wait`, the early pass; `wants` — V/07; `COMMANDS_BEAT` — V/01; `fold` — drop |

Open for V/07 and V/05: the `key` of the job `scan` and extending a running job — the fields `key` of a row with `made` are immutable
(§ 4, question 1).

### М10B/26 «Свой резервный архив» — V/02, except:

the vocabulary of declarations — the hooks are removed, instead of them `affinity`, `near.prefer`, `must_match` (P/04 Н1.3, P/06.1 Н1.3,
ADR-0091 item 10); `/rec/where/volumes/<карта>` — P/06.5 Н3; the camera worker next to the backup one — V/01 (the declaration `near`);
`before_stop_all`, `after_stop` — P/03.1 Н2, P/03.4 Н3; the camera pusher (`CameraPusher`) — V/01; the hook `card_range`
from `domainpart` and `_fsync_dir` — drop.

### М10B/27 «Тома» — V/02, except:

holding — P/03.2 Н1.2, Н1.3, Н3, Н4; `placement.places`, `affinity`, `admits`, `near.prefer` — P/04 Н1.3; the doors and the
schema of the tables, `held_by` — P/06.1 Н1.6; volumes on disk — P/02.4 Н1.1 (ADR-0091 item 4); `type: url`, `secret_in`,
`access_secret` — P/06.2 Н1.1, Н1.1а; `rec/used/*` — P/02.1, P/05 Н1.1; the volume did not open — `place_by: ""` (ADR-0091
item 9); the table metrics, `servers.status` — P/06.5; «spare», `rec_workers_needed` → `w2c-spares.sh` — drop;
a shortage by places without a holder — P/04 Н3 «нехватка(), заказать()» with `grows: true` (a choice of the V/02 manifest).

### М10B/28 «VMS на кластере»

Step 1 — the budget formula `B + n·I` and the meaning of `CAPACITY` of the camera worker — V/01; the values of `CAPACITY` by roles — V/09; `roles/<роль>.env`, `unit_mb`/`base_mb` — P/02.4 Н1.2,
Н1.5, P/03.4 Н1.2; the spares — drop → `grows`. Steps 2–6 — V/02; holding — P/03.2; the event mirror — P/02.4, P/05 Н2;
`heartbeat.strings` — P/03.4 Н1.1; `servers.status` — P/06.5 Н1.2; `/where` — P/06.5 Н3; `free-*` — P/05;
`unconfirmed_max`, the move — P/03.2 Н1.6, P/04 Н1.4а; `older_epochs: fenced` — P/06.4 Н1.2. `ARCHIVE_PORT` — the file `rec`
(the text «the unit sets» is to be rewritten).

### М12A/03 «Шлюз и одна подписка»

The heartbeat form — P/03.4 Н1.1, P/08.1 Н1.4; `live_url`, the branch `tee`, the attachment point — V/01; the gateway, one subscription,
`reconnect`, the refusal arithmetic — V/03; `labels-subset` — P/04 Н1.3; the token — P/03.4 Н3, P/06.5 Н3; 400 `domain.edit` —
V/01 (`cam.domain.edit`), P/08.6 Н1.3; the gateway code of the witness's domain part — drop.

### М12A/05 «Упаковка, обновления, лицензия»

Steps 1, 2, 5 — V/09 (one package, the difference is a property of the server (P/04 Н1.3), delivery by pushing and by pulling, the licences
of the dependencies); the table of the domain units of step 1 — P/02.4 Н1.12; `vms-domainpart` — drop. Step 3, the issue and revocation of the licence —
М14. Step 4 (the licence cache at the consumer, «write, but do not add») — V/01, the chapter «лицензия»: the platform has no norm
(§ 6, № 18).

### М12A/10 «Камера как кластер из одного»

The box, the hot data in memory, the agent — P/02.4 Н1.10, Н1.11, P/09.1 Н1.11, P/08.10 Н1.9; the ring and the budget of the camera process,
the row `cam/cameras/1`, `ref` = the serial number, the camera heartbeat — V/01; the card — V/02; two domain objects — P/09.1 Н1.2,
P/08.1 Н1.4; a slice without secrets — P/04 Н1.3а, P/06.2; the epoch — P/03.2 Н1.5; the flash — P/02.4 Н1.11, P/09.1 Н1.4; the report
after the first publication — P/09.1 Н1.2 `ready`; the camera door after the first publication — P/? — (§ 6, № 19); its own console —
P/09.1 Н1.5, P/06.7 Н1.9. «There is no controller and no slots» — outdated (P/02.4 Н1.10).

### М12A/12 «Сценарии между камерами»

The document `auto.domain.shared[scenarios]`, the executor, the book `asks`, «scenario not executable» — V/07; the signature and the verification
of the document — P/08.9 Н1.2, Н1.3, P/06.7 Н1.14; a request with a deadline to the receiver's door, the book `polls` — V/02; the token `ask` —
V/01 (the fields — V/07, the issue — P/08.7 Н3); the edit door — P/10 Н1.2е; «a VMS worker writes `domain/cam/asks`» — drop.

### М12A/13 «Свидетель молчания»

The declaration `reports: [polled/]`, `witness`, the writer `rec/polled/<приёмник>`, an object per receiver — V/02; the mechanism —
P/09.1 Н1.10, P/10 Н1.8, P/08.9 Н1.9, P/03.7 Н1; the member name — P/08.7 Н1.4.

### М12B/01 «VMS на домене: вклад подсистемы»

| Step | Owner | What |
|---|---|---|
| «Зачем», 1 | P/02.1 Н1.2б | the domain knows the subsystem by `domain:`; the content — V/01, V/02, V/07 (item 5 of addendum (4)) |
| 2 | V/01 (`ref`, `view`, `edit`), V/02 (`rec.domain.edit`) | the mechanism — P/08.1 Н1.2, Н1.4, Н1.5; P/08.6 Н1.3; P/10 Н1.2а |
| 3 | P/08.5 Н1.3, Н1.4; P/09.1 Н1.4, Н1.2 | the books, carrying, sealing `*_secret`; what is in the books — V/01 (`sources`), V/02 (`primaries`, `polls`, `upstream`), V/07 (`asks`) |
| 4 | drop | `kept`, `tables` (`crossings`, `roads`) — ADR-0074 C2; the mechanism — P/03.7 Н1.6; `names` — V/03, P/08.5 Н1.7; the prohibitions of the agent — P/02.5 Н1.4а |
| 5 | P/08.7 Н3, Н1.4; P/02.1 Н1.2б | the token kinds; the declarations — V/01, V/02; the token socket and `vms-camdomaintokens` — drop (the local door — P/09.1 Н1.6) |
| 6 | drop | the worker `domainpart` (ADR-0074); the assembly — P/08.5 Н1.3 |
| 6а | V/03 | RTSP accounts, the book `stream-accounts`, the table `accounts`, the RTSP door of the gateway; the namespace — P/08.5 Н1.7, P/08.4 Н3; `/stream-clients` — drop |
| 7 | V/01 (`keys`, `shared`), V/02 (`reports`, `witness`) | the mechanism — P/06.7 Н1.11, Н1.14; P/09.1 Н1.2; P/10 Н1.8 |
| 8 | drop | the boundary tests — witness; acceptance — at each lesson |

### М12B/02 «Поток из другого кластера» — V/02, except:

one recording cluster per camera — P/08.6 Н1.1 (`Crossings` — drop, a transfer — `PUT` of the assignment); the element of the book
`sources` — V/01, the contribution — P/03.7 Н1.2, the assembly and carrying — P/08.5, P/09.1 Н1.4; freshness — P/09.1 Н1.7. Whether the row
`domain/rec/primaries` is needed in `rec.worker.reads` (the card and the backup recorders read the book of primaries) — a question for V/02.

### М12B/03 «Камера, до которой никто не дотягивается»

V/02 — the receiver, the subscription of the recording to the receiver, the witness and the memory of roads, the receiver addresses in `primary`, the long poll,
catch-up recording on a claim, the answer from the card, the frame time, the tee, several receivers, the door `/ask`, the book `polls`, the backup.
V/01 — the pusher (upload in pieces, the debt, `owed_spans`, `wire`), the tokens `stream`, `poll`, `ask` (the declarer),
the action on the target, `taken_by`, three channels. V/03 — the gateway looks into the receiver, `live_road`. V/07 — the book `asks`,
the executor, `rate_per_minute`, refusals. Platform: the networks `domain/reaches` — P/09.1 Н1.7; issuing tokens — P/08.7 Н3,
`placement` — P/08.6 Н1.1; a token request through the agent — P/09.1 Н1.6, P/03.7 Н1.5; the document door — P/10 Н1.2е,
P/08.9 Н1.3. Drop: «the VMS worker at the holder decides», `domain/cam/roads`, `token_secret` in the book, `/metrics` and `/catalog`
of `domainpart`. Open for V/02: the receiver's loss metrics (`lost`, `clock_steps`) by a `metrics:` declaration, or drop;
the rule «shared network — pull» without `domainpart`. For V/07: where the scenario form takes the descriptions from (`/catalog` is removed).

### М12B/04 «Цепочка: объект, ретранслятор, центр»

V/02 — the forwarder in the recorder, the book and the token `upstream`, `up_have`, the relay's archive on the centre's claim, the star,
polling a camera behind the relay, carrying the request. V/07 — a scenario between relays. Platform: control upward —
P/09.2 Н1.1, P/09.1 Н3, P/08.3 Н1.1; `star`, `star_centre` — P/08.3 Н1.2, P/08.7 Н1.1; the representative relay —
P/09.2 Н1.1, Н1.4, P/08.3 Н3; freshness — P/09.2 Н1.4, P/09.1 Н1.7; the topology — P/08.3 Н1.2, Н1.3а, P/10 Н1.2в;
`domain/reaches` — P/09.1 Н1.7. Drop: `bundle`, `MEMBER_SHARE`, `CENTRE`, `STAR` at the VMS worker, the chain code of the witness's domain part.

### Module files outside the lessons

| File | Owner | What |
|---|---|---|
| `М10B_ServerVMS/README.md` | drop | the navigation of the module; the lesson table — `VMS/README.md`, `VMS/common/lessons.tsv` |
| `М10B_ServerVMS/module-design.md` | drop by the decisions | the history of the decisions of М10B: every decision already stands in the owner chapter of § 2 (the holder — V/01, the archive and the volumes — V/02, the page — V/11, the box — V/09 and P/02.4, the hooks and the spares — drop); the open questions of the note — in § 6, § 7; the authentication of the holder's door — V/01.5 (P/03.4 Н3 «токен двери у держателя») |
| `М10B_ServerVMS/СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ.md` | V/02 | the note on the number of recordings of a camera: `rec` — `id: name`, the recording name follows the camera (`cam` is a field), two recordings of one camera (backup, network volume), `spread_by: cam` — a choice of the installation, not of the shipped manifest (the filter of P/04 Н1.3); «ГРАНИЦА» §2.8 item 8 — the platform part is already in P/04 |

#### М12A/README, М12B/README, module-design

Navigation and removed material — not carried over; they are removed with the translation of the remainders (ADR-0080 addendum (20)). The decisions of module-design: the section
`domain:` — by keys (§ 5); `domainpart`, `SIGNER_TOKENS_UNIX`, `token_secret`, `kept: crossings, roads`, `/metrics` and
`/catalog` of the worker — drop; «Что открыто» 2 is closed by P/08.6 Н1.1.

## 3. Names with «vms» (addenda (3), (5) items 1–5, (6) items 1, 4–6, (7) items 2–3; ADR-0091 items 4–5)

Allowed only: `<dep>` = `vms` before a role or a subsystem by the table of addendum (6) item 1, and «the product as a whole» (`VMS/`,
images, the package). The product's debt to «Сборка» — by ADR-0005, as a row during the translation of the owner lesson.

| Name (where) | Decision | Owner |
|---|---|---|
| **Units** `camworker@`, `recworker@`, `liveworker@`, `detworker@`, `detjobworker@`, `autoworker@` (`.container`), `vms-camworker.service`, `vms-recworker.service` | `vms-<sub>worker@.service`, instance `<prefix>-<SERVER_NAME>-<n>` | P/02.4 Н1.1; the values — V/09 |
| `surveyworker@` | `vms-detedgeworker@` — by the transition of lesson 06 | V/06 |
| `obsd.service`, `vms-obsd.service` | `vms-rec-obsd.service` (`parts.obsd`) | V/02 + P/02.4 Н1.1 |
| `vms-jobs.service`, `vmsjobs.container`, `com.w2c.vms.jobs`, `JOBS_PORT`, `JOBS_HOST` | drop (§ 4) | — |
| `vms-domainpart.service`, `DOMAINPART_PORT`, the role `camdomain`, the groups `vms-camdomain`, `vms-camdomaintokens`, `vms-autodomain`, `vms-recdomain`, `vms-livedomain` | drop (ADR-0074; addendum (6) item 2) | — |
| `vms-<роль>-spare@`, `w2c-spares*`, `SPARES_*`, `SPARE_FOR`, `SPARE_FILE`, `com.w2c.vms.<роль>.spare-<n>`, `com.w2c.spares`, `vms-scaler` | drop (ADR-0084, addendum (5) item 9); ordering — P/02.4 Н1.5 | — |
| `vms-archive-retain.timer`; the group `vms-rec` in its former meaning (the clients of `obsd`) | drop (only the mentions and the migration, addendum (6) item 10); the name `vms-rec` passes to the user and the group of the subsystem `rec` (`<dep>-<sub>`) | — |
| **Users** `vms` | `vms-<sub>`: `vms-cam`, `vms-rec`, `vms-live`, `vms-det`, `vms-detjob`, `vms-detedge`, `vms-auto` | P/02.4 `users_groups` |
| `vms-obsd` (user, group, `OBSD_CLIENT_GROUP`) | `vms-rec-obsd` | V/02 |
| **Groups** `vms-<sub>worker` | remain (`vms-surveyworker` → `vms-detedgeworker`) | P/01.2 |
| the membership of `configstore` in the groups `vms-*` | drop (P/02.4 `users_groups` rule) | — |
| **Roles** `<sub>worker` (SAN, `W2C_ROLE`, socket) | without a prefix; `surveyworker` → `detedgeworker` | P/01.2; V/06 |
| **Environment files** `vms.env`, `/etc/vms/vms.env`, `vms.env.example` | there is no common file: the platform variables — `w2c.env`, the roles — `/etc/w2c/roles/<роль>.env`, the rest — to the file of their own subsystem (`W2C_SUB_ENV`; the path — § 6, № 16) | V/09 + P/02.4 Н1.2 |
| `VMS_ENV` | `W2C_SUB_ENV` | P/02.4 Н1.2 |
| `ROLES_DIR` (`/etc/vms/roles`) | drop: `roles/` next to `w2c.env` | P/02.4 Н1.2 |
| `SPEC_DIR` (`/app/vms`) | `MANIFEST_DIR` | P/02.4 Н1.2 |
| `CONSOLE_MONITORS` | drop (addendum (6) item 6) | — |
| the product variables `VMS_*` | without `VMS_` | a debt to «Сборка» |
| **Paths** `/etc/vms`, `/data/vms/etc` | `/etc/<sub>` → `/data/platform/etc/subsystems/<sub>` | P/02.4 Н1.1 |
| `/data/vms` | `/data/platform/subsystems/<sub>` | P/02.4 Н1.1 |
| `/data/vms/obsd`, `/var/lib/vms-obsd` | `/data/platform/subsystems/rec/obsd` | V/02 |
| `/data/vms/obsd/volume`, `OWN_VOLUME` | `/data/platform/subsystems/rec/obsd/volumes/<n>` (the installer does not create it; a default volume without a mount point — a question for V/02) | V/02 |
| `/run/vms` (`SHM_DIR`, `/run/vms/<cam>.shm`) | the share `cam.shm` (`kind: dir`) → `/run/vms-cam-shm`, the group `vms-cam-shm`; `rec`, `live` — `worker.uses: [cam.shm]`; the name of the share is confirmed by V/01 | V/01 |
| `/run/vms-obsd`, `/run/vms-obsd/obsd.sock`, `/run/vms/obsd.sock`, `/tmp/vms-obsd-<uid>.sock` | the share of the part `obsd` (§ 6, № 6); the socket 0660 | V/02 |
| `vms.tmpfiles`, `/etc/tmpfiles.d/vms.conf`, `vms-nomad.sysusers` | drop: the directories and the users are built by the installer | P/02.4 Н1.1 |
| `file:///var/lib/vms/archive`, `s3://bucket/vms`, `https://s3.example.com/vms` (hints and examples) | the path by ADR-0091 item 4, a neutral bucket | V/02, V/11 |
| `/data/media` (`MEDIA_DIR`) | under `/data/platform/subsystems/cam/…` or an input of the operator — decided by V/01, V/09 | V/01 |
| **launchd labels** `com.w2c.vms.camworker`, `com.w2c.vms.recworker` | the platform has no norm (P/02.4 «Решает реализация» items 1, 3): from the name of the unit, not named in the VMS specification | — |
| **nomad** jobs, `user = "vms"`, `args = ["vms", …]` | a form of the implementation; `user` → `vms-<sub>`; `args` — drop | — |
| **Metrics** `vms_…`, `vms_<name>` (the comments of the manifest `cam`), `vms_commands_total`, `vms_event_to_device_seconds`, `vms_commands_in_flight`, `vms_commands_reanswered_total` | `cam_…` (`metrics.prefix` = the name of the subsystem, P/06.5 Н2); the command names — P/03.4 (ADR-0091 item 6) | V/01 |
| **Keys and doors** `POST /vms/requests` | `POST /cam/requests` | V/01 |
| `units.vms`, `UNITS.vms`, `edit: vms: […]` | `units.cam`, `cam.domain.edit` | V/01, V/11 |
| `vms.12.input[1]` (an anti-example of the language) | `cam.12.input…` | V/07 |
| `vms/resources/…` (an anti-example) | drop | — |
| **Event trees** `<корень>/vms/<cam>/e<epoch>`, `vms.alarms/<cam>` | `cam/<cam>/e<epoch>`, `cam.alarms/<cam>` (P/05 Н1.2) | V/01 |
| **Page classes** `.vms-src*`, `.vms-rules*`, `#vms-kinds`, `.vms-account*` | `.cam-src*`, `.auto-rules*`, `#auto-kinds`, `.live-account*` | V/11 |
| `process_name` «vms» in `HELLO` | the process name is the role (`recworker`) | V/02 |
| `Refused("a vms unit needs a source")` | words without «vms» | V/01 |
| **Entry points** `python3 -m vms <глагол>`, `w2c-run.sh vms …` | drop: the process is a unit, the worker has no runner command (Н1.9; the command of the unit — § 6, № 15) | — |
| **Images** `localhost/vmsserver`, `clustervms`, `vms/domainvms` | the product as a whole — allowed; how many images — V/09 | V/09 |
| `vmscam`, `vmssubsystem`, `ServerVMS`, «VMS» in the text | the product as a whole or a reference to the product — allowed | — |

The variables of `vms.env.example` by owners: to the platform — `CLUSTER`, `REACH_BUDGET` (`w2c.env`), `LONG_POLL_WAITERS`
(P/05, but not in the table of P/02.4 Н1.2 — § 6, № 20); `cam` — `MEDIA_DIR`, `SHM_DIR`, `PLAYBACK_PORT`, `RTP_BASE`,
`COMMANDS_BEAT`; `rec` — `ARCHIVE_VOLUME`, `ARCHIVE_QUOTA_BYTES`, `OBSD_SOCKET`, `OBSD_TIMEOUT`, `ARCHIVE_URL`,
`ARCHIVE_HOST`, `ARCHIVE_PORT`, `BACKFILL_BUDGET`, `BACKFILL_WINDOW`, `SEQUENCE_FLUSH_MS`, `BLOCK_FLUSH_S` (also read by
`detjob` — through the heartbeat or a row of `rec`, addendum (6) item 5); `detjob` — `VISIBLE_LAG_SECONDS`; `detjob`, `detedge` —
`SCAN_CAPACITY`, `SURVEY_CAPACITY` → `CAPACITY` in `roles/<роль>.env` (P/02.4 Н1.2, ADR-0070); `auto` — `LONG_POLL`
(also read by the worker runtime — § 6, № 20); `LOG_LEVEL` — to the file of each subsystem (the processes of the platform have no norm — § 6,
№ 20); `CONSOLE_MONITORS` — drop. The names of the witness's implementation code (modules, the video pipeline package, the worker and controller classes, `VMS_DATA`, tests,
the file names of the former lessons) do not become norms.

## 4. The work of `vmsjobs` (ADR-0090 addenda (3), (5) item 6, (6) item 7, (7); ADR-0091 items 1–3, 7)

The process `python3 -m vms jobs` is removed; new implementations do not get it; the product — by a debt to «Сборка», the witness — as
it is. The norms of ADR-0091 are in the export: P/02.1 Н1.2а (`worker.creates`, `shares`, `parts`), P/03.6 Н1.6 (ordering), Н1.7
(state), P/04 Н1.3 (`ends`, `retire_when.delete_after`), P/06.1 Н1.2–Н1.3 (`made`, `born`), P/01.1 (`not_after`,
`not_before`), P/02.5 Н1.4, P/03.4 Н1.1 (`creates.<outcome>`, `made_rows`, `filings`).

| The witness's duty | The platform mechanism | The application side and the lesson | The difference from the witness |
|---|---|---|---|
| `record_on_request` (`record` → `<cam>-auto`) | an order: `auto.worker.creates → rec/recordings`, `key: "{cam}"` | V/07 the logic; V/02 removes `requests.elsewhere: [record]` | the name `auto-<cam>`; `until` from the event time; the horizon 600 s; the manual `auto-7` is taken |
| `detect_on_request`, `_detect`, `_settings` | an order: `auto → det/units`, `key: "{cam}-{kind}"` | V/07 (the base — the operator's detector, `params` on top, `labels` at creation; a second detector is not set up); V/04 removes the section `requests:` | `auto-<cam>-<kind>` |
| `_scan` | an order: `auto → detjob/jobs` | V/07 (the refusal to scan a camera that nobody records; `mask_from`); V/05 the job | `auto-…`, fractional fields, `%2D`; there is no extension of a running job (question 1) |
| `scan_what_arrived` | an order: `rec → detjob/jobs` | V/02 (when and by which detectors; `worker.reads det/units/`) | `rec-…`; the window `closed` in the heartbeat is not needed |
| `expire`, `expire_recordings` | `placement.ends: {field: until, never: 0}` at `rec`, `det` | V/02, V/04 | manual rows are not deleted — `expired_kept` |
| `reap` (the phase → `state`, `ended`) | `unit.state.result`, `retire_when {state: result, …}` | V/05 (`snapshot: [name, cam, kind, state.result]`) | the result is written by the holder under the guard of the epoch, it survives a move |
| `forget_finished` | `retire_when.delete_after: 259200` | V/05 | manual jobs are deleted by the operator |
| `ask_for_footage`, `_ask_recorder` | filing by a worker (P/03.6 Н1.5) | V/05 declares `worker.requests: [rec]` (the general norm P/03.6 Н1.5) | `by: detjob/<задача>` |
| `keep_what_fired` | filing by a worker | V/06 — `worker.requests: [rec]`, `worker.reads rec/recordings/` | `by: detedge/<единица>` |
| `count_expired`, the labels `_ended`/`ENDED_BY` | `creates.<outcome>`, `made_rows` | V/07, V/02 declare the series | there are no requests and no labels |
| `Remembered`, the loops `_requests_loop`, `_reap_loop` | drop — code | — | the expiry is removed by the pass of the controller (5 s) |
| `FileLostSpans`, `SealKeeps`, `WatchGarbledKeeps` (product) | — | V/02: `SealKeeps` is already at the recorder; `FileLostSpans` — an own request family is forbidden (P/02.1 Н1.4 № 88), the path is decided by V/02; `WatchGarbledKeeps` — `holds.longest` releases, the alarm is at V/02 | a debt to «Сборка» |

New manifest keys (edited by the owner lessons): `auto` — `worker.creates` (`rec`, `det`, `detjob`),
`unit.state.cursor`, `worker.requests` narrows `[cam, rec, det]` → `[cam]` (at `det` the section `requests:` is removed — otherwise a refusal of the catalogue); `rec` — `worker.creates` (`detjob`), `placement.ends`, `parts.obsd`,
remove `elsewhere`; `det` — `placement.ends`, remove `requests:`; `detjob` — `unit.state.result`, `retire_when` with
`delete_after`, `snapshot`, `worker.requests: [rec]`, the field `mask_from`, remove the fields `state`, `ended`; `detedge` —
`unit.state.cursor`, `worker.requests: [rec]`. The texts of the `VMS/` manifests that name `vms jobs` or «the console loop» as the executor
(`rec:77–80, 245–256`; `det:40–41, 64–83, 108–111`; `detjob:24, 32–33, 41–44, 67–74`; `auto:5–7, 22–23, 57–58,
113–115`; `survey:10`) are rewritten during the translation of the lesson.

Questions (decided by the lessons, by a request if needed): (1) the `key` of the job `scan` and the extension — a new job on every firing
or suppression of a nested interval (V/07, V/05); (2) `ask_for_footage` through `worker.requests: [rec]` at `detjob` —
closed by the general norm P/03.6 Н1.5 «Подача воркером»; (3) the mask: the bodies are objects, reading is open to any role with a kit (P/05 Н1.1, Н2) — a reference suffices; (4) what is written into `result` (only `done`/`failed`, or the phases too).

## 5. Keys of the section `domain:` (addenda (4) item 5, (5) item 8, (6) item 9)

| Key | Lesson | Read by |
|---|---|---|
| `cam.domain.ref`, `view`, `edit`, `shared [folders, alarms]`, `keys (sources)` | V/01 | the platform (P/08.1, P/08.6, P/06.7) |
| `cam.domain.books.sources` | V/01 | `rec`, `auto` (`domain/cam/sources`) |
| `cam.domain.tokens.stream` (the assignment fields — P/08.6 Н1.1), `poll` (`poll_home` — V/02), `ask` (the document fields — V/07) | V/01 | the `grant` roles — `camworker`, `recworker`, `autoworker` |
| `rec.domain.books.primaries`, `upstream`, `polls`; `tokens.upstream`; `reports [polled/]`; `witness`; `edit` | V/02 | `cam` (`primaries`, `polls`), `rec` (`upstream`); the platform |
| `live.domain.books.stream-accounts`, `names.stream-accounts/` | V/03 | `live`; the platform (P/08.5 Н1.7) |
| `auto.domain.books.asks`, `shared [scenarios]` | V/07 | `rec`, `auto` |

`det`, `detjob`, `survey` have no such section. The platform keys in `worker.reads` (`domain/placed/rec/`,
`domain/member-topology`, `domain/member-list`) — P/09.1. The ones removed by ADR-0074 (`kept`, `tables`, `crossings`, `roads`,
`token_secret`) are already absent from the manifests. Open: `domain.keys` declares only `sources` — the families of the other books are
declared by each lesson itself; `rec.worker.reads` without `domain/rec/primaries` (М12B/02).

## 6. Platform gaps — candidates for requests

A request is filed as a file `decisions/inbox/<дата>-запрос-vms-<тема>.md` during the translation of the lesson that is the first to run into
the gap; until the decision — a workaround with a debt row (addendum (1)). Requests of one cause are merged.

| № | Gap (address in `afb1c88`) | Lesson | Blocks |
|---|---|---|---|
| 1 | substitution of the id into the `default` of a field (P/06.1 Н1.2) — filed `decisions/inbox/2026-10-23-запрос-vms-id-в-умолчании.md` | V/01 | no (the workaround — without substitution) |
| 2 | a broken unit row at the worker; the check of the words of `LABELS` (P/03.3, P/02.4 Н1.2) | V/01 | no |
| 3 | the event rows `command`/`command.failed` (P/03.6; the words — only P/07) | V/01 | no |
| 4 | the heartbeat fields `unconfirmed`, `assignment_rev`, `passes`, `store_errors`, `pass_failures`, `was_fenced` (P/03.4 Н1.1; the series exist in P/06.5) | V/01 | no |
| 5 | a worker stop timeout beyond 20 s (P/02.4 Н1.1 «names its own value» — there is no key); the environment, `TimeoutStopSec` and `After=` of a part (`parts` — only `{exec, volumes}`) | V/02 (and V/01) | no |
| 6 | the worker's access to the share of its part: `worker.uses` of its own subsystem is rejected (P/02.1 Н1.4 № 91), `shares` does not say «share of a part»; the coincidence of `/run/vms-rec-obsd` with the name of the part's user (P/02.4 `names`) | V/02 | no (text), yes for acceptance |
| 7 | opening `access_secret` of a row of the places table (P/03.5 Н3 — only the unit row) | V/02 | no |
| 8 | the form of `url` in the heartbeat: not the «all interfaces» address (P/03.4 Н1.1) | V/02 | no |
| 9 | ~~places in the library~~ — not a gap: decided by ADR-0091 item 9 (a refusal with a workaround, `inbox/2026-10-22-запрос-vms-места-в-библиотеке.md`); substitution and `FOR` — § 7 | — | — |
| 10 | ~~a shortage by places~~ — not a gap: P/04 Н3 «нехватка(), заказать()» for `servers: distinct` with a place from the heartbeat, acceptance P/04 sc. 17; the condition — `grows: true`, a choice of the V/02 manifest | — | — |
| 11 | the form of the field `freeing` in the heartbeat (P/05 sums it, P/03.4 Н1.1 does not describe it) | V/02 | no |
| 12 | CORS of the holder's door (`DOOR_ORIGINS`); finding the holder of a foreign unit by the heartbeat (`holder_of`) | V/11, V/03 | no |
| 13 | protection of the holder's HTTP door: connection limits, timeouts (there is no general norm) | V/01, V/03 | no |
| 14 | the log of the holder's door (`archive.read`, `archive.keep.verified`; the contract knows only `door.issued`) | V/02 | no |
| 15 | the command that the unit `<dep>-<sub>worker@` starts (`parts` has `exec`) | V/09 | no |
| 16 | the path of the subsystem file (`W2C_SUB_ENV` «is set by the unit», the unit does not name it) | V/09 | no |
| 17 | `per_person` for filing by a worker (P/03.6 Н1.5, P/06.4) | V/06 | no |
| 18 | the licence at the consumer: who counts for the whole domain (the direction of P/08.1 by `ref`), the path of the document (P/08.9); the addressee of step 3 — М14 (ADR-0090 addendum (4); P/08.4 corrected in the export `081a8f4`); filed — `decisions/inbox/2026-10-23-запрос-vms-лицензия.md` | V/01, the chapter «лицензия» | only the chapter (a decision of «Архитектор» 2026-10-23) |
| 19 | the door of a cluster of one opens after the first publication (P/09.1 Н1.2 `ready` — only the report) | V/01 | no |
| 20 | `LONG_POLL_WAITERS` in P/05, but not in the table of P/02.4 Н1.2; `LOG_LEVEL` of the platform processes; `LONG_POLL` of the worker runtime | V/09 | no |
| 21 | ~~reading bodies~~ — not a gap: the bodies `<sub>/blobs/sha256-…` are objects, reading `/v1/objects` is open to any role with a kit (P/05 Н1.1 `door`, Н2 «Допущенные роли»); V/05 refers to it | — | — |

## 7. Divergences of the lessons from the platform norms (the lesson accepts the platform and records the difference)

- The snapshot ceiling: the lesson 64 KiB, P/04 Н1.3а — 64 MiB (V/01, `folders`).
- The start gate: the secrets before the epoch, `may_act` before the start and the restart (P/03.3 Н3 step 2, P/03.2) — in lesson 03 the other way round (V/01).
- `stalled`: in the lesson after three failures, in P/03.3 Н1.2 — at `RETRY_MAX`; `converged`/`lagging` — not carried over (the chapter М10B/02 is platform in full).
- Substitution (P/03.4 Н3 «подмена()») extends the strict place by a write with cas under the guard of its own slot; `may_stand_in_hold` and the `FOR` count of the lesson М10B/10 — a divergence, the lesson follows the norm (V/02).
- An unopened device: P/03.6 — `refused` with a reason, in the lesson — to wait (V/01).
- `DELETE /devices/<хост>` — 403 at the console (a worker table, P/06.1 Н1.6) (V/01).
- The stop order of the recorder: P/03.4 Н3 — the place writers → the heartbeat → the place → the slot; the comment of lesson 07 is different (V/02).
- The volume did not open: `place_by: ""` (ADR-0091 item 9), the lesson holds the volume with zero capacity (V/02).
- The catch-up recording profile `requests.outcome: fetched` and the removal by `ttl` against P/06.4 Н3 «жнец» (V/02).
- Zero days of `retention_days` with `minimum: 1` (V/02).
- The door token — read routes, `keeps/…/verify` — POST (V/02).
- The scan progress as a file on the resource is lost on a move; the cursor `unit.state.cursor` (V/05).
- Repeating the order `rec → detjob` after `expired`/`refused` (V/02).
- The texts of lessons 13 and 12 diverge from the canon of the manifest `live` and of the shell — the text is written by the canon (V/03, V/11).

## 8. Questions to «Архитектор» and the answers (2026-10-23)

The check of the inventory — `decisions/inbox/2026-10-23-проверка-описи-VMS.md` (no blockers; changes 1–11 are entered: § 1, § 2
«Module files outside the lessons», М10B/10, 17, 28, § 3, § 4, § 6 № 9, 10, 21, § 7).


1. **VMS id-map.** М10B, М12A, М12B have no old norm ids. Answer: during the translation of a lesson, the rows `old` are the address of the step of the former
   lesson (`М10B/04 ш.3а`), `new` — `V/NN.K-MM`, the columns as in `Platform/common/id-map.tsv`.
2. **The addressee of step 3 of М12A/05 and of the issue of the licence** — М14 (ADR-0090 addendum (4), a later decision); the reference of P/08.4 to М13
   will be corrected by «Спецификация». The count of the licence per domain and the path of the document (§ 6, № 18) — by a request during the translation of the chapter
   «лицензия» of 01-cam; the rest of 01-cam — without it.
3. **Filing requests.** № 5, 6, 16 were filed as a package on 2026-10-23 (`decisions/inbox/2026-10-23-запрос-vms-остановка-и-окружение-части.md`,
   `…-доля-своей-части.md`, `…-файл-подсистемы.md`); the rest — as the lessons are translated.

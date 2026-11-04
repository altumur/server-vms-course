# V/01 Camera

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/01.1–V/01.8 (2026-10-23); the plan below is the history of the translation. Sources: the inventory
[`../common/inventory.md`](../../common/inventory.md) § 1, § 2. The platform: the export `cammeta-specs` `7a875c75`.
The manifest is [`cam.subsystem.yaml`](../cam.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8). The root shell is
[`cam.shell.html`](../cam.shell.html): a link to the form `/backend/` and to the platform module P/07 (lesson V/11, chapter 1 Н1.1); the former page is the witness `Source/vms/cam.shell.html`.

## What lesson V/01 is

The subsystem `cam`: a camera (or another device: `type` — `ipsrv`, `eventsrc`, `acfa`) as a unit; its holder is the worker `camworker`, which
opens the device with one connection, delivers the stream to the subscribers (`rec`, `live`, `det`) and answers the commands and
questions to the device; the archive of the device itself (a card, an NVR) and its doors; the camera's contribution to the domain. Everything common — the worker
runtime, the slot, the epoch, the lease, requests, events, the console doors, the domain — is platform norms by reference (P/…); the lesson does not
repeat them. `cam` has no separate HTTP contract of the console (the unit doors are P/06.1); the holder has its own door (chapter
5) — `spec/01-cam.api.openapi.yaml`.

## Chapters

| Chapter | Subject | Sources (inventory) | Platform norms it relies on |
|---|---|---|---|
| V/01.1 | The camera as a unit: fields, the address and credentials, the tables `devices`, `children`, `child_settings`, `rule_state`, placement, the snapshot, console words, event suppression | М10B/01; 19; 15 step 1 (table); 25 step 4a; 04 step 1 (`group_by`) | P/02.1; P/06.1 Н1.1–Н1.3, Н1.6; P/06.2 Н1.1, Н1.1а, Н1.4; P/04 Н1.3, Н1.3а; P/06.3 Н1.5; the contracts row-check, url-credentials, group-of, gate-and-pass; P/06.5 Н1.2; P/03.6 Н1.2; P/05 Н1.3 |
| V/01.2 | The camera holder: the desired state, the pipeline, delivery (RTSP and shared memory — the share `cam.shm`), observations → events, heartbeat and phase words, store silence, stopping, the worker budget | М10B/03; 04 steps 1–2, 3, 4–10; 09 (the holder); 28 step 1 | P/03.1 Н2; P/03.2; P/03.3; P/03.4 Н1.1, Н1.2; P/03.5; P/03.6 Н1.2; P/02.4 Н1.1, Н1.2; ADR-0091 items 5, 6 |
| V/01.3 | The source `driverpack://file/<имя>`: a file as a camera (pace, PTS, address refusal) | М10B/05 | P/03.3 Н1.2; P/06.2 Н1.1а (the contract url-credentials) |
| V/01.4 | Commands and questions to the device: the requests `output`, `preset`, one call per group, the answer, the row `cam/devices/<хост>` (what the device can do, `identity`), the device's children and the block owner (ADR-0102), arming and switching off for a time (ADR-0105) | М10B/04 steps 3a, 3b; 15 step 1; 25 step 9 (executed by the holder) | P/06.4 Н1.5, Н3; P/03.6 Н1.5, Н3 «взгляд держателя», «Действие устройства»; P/06.1 Н1.6; ADR-0091 item 6 |
| V/01.5 | The device archive and its doors: `/playback`, `/devices`, `/recordings`, `playback_url`, `coverage`, playback sessions; admission is the role certificate (class `mixed`), without a kit — loopback | М10B/15; 23 steps 2, 4; 24 step 8 (`.device.mp4`) | P/03.4 Н1.1, Н1.7; the role certificate contract (class `mixed`); P/06.5 Н3 `/where`; P/04 Н1.3 `group_by` |
| V/01.6 | The camera on the domain: `ref`, `view`, `edit`, the book `sources`, the book `licence` (the worker on the domain exists only for it), the tokens `stream`, `poll`, `ask`, `shared`, `keys`; the stream pusher into the receiver; the camera as a cluster of one; an order of recording onto the card of the server | М12B/01 (the keys `cam.domain`); М12B/02 step 3; М12B/03 (the pusher, the tokens, `taken_by`, three channels); М12A/03; М12A/10 | P/02.1 Н1.2б; P/03.7; P/08.1, P/08.5, P/08.6, P/08.7, P/08.9; P/06.7 Н1.11, Н1.14; P/09.1; P/02.4 Н1.10, Н1.11 |
| V/01.7 | The licence at the consumer: a document in the common settings of the domain, the count for the whole domain by the worker on the domain `camdomain`, the book of decisions, application at the holder | М12A/05 step 4 | P/08.9 Н1.2; P/03.7 Н1.6; P/08.1 Н1.4; P/08.5 Н1.4, P/09.1 Н1.4 `member_row`; the observation contract; P/02.1 Н1.2б |
| V/01.8 | Device search: a search row per cluster, the findings `found`, the question about the model, the entry into the driver; the result is only a finding | ADR-0103 addendum (1) | V/11.4 Н1.9 |

The subsystems that consume the door and the heartbeat of `cam` (`rec`, `live`, `det`, `detedge`) refer to chapters 2, 5; the lesson does not norm
their behaviour (addendum (4) item 2).

## Forms and doors (Н1, Н2 by chapter)

- **Rows and objects** (the catalogue `../common/data/catalog.tsv` receives the rows of the lesson): `cam/cameras/<id>`, `cam/next_id`
  (P/06.1), `cam/devices/<хост>`, `cam/children/<id>`, `cam/rule_state/<id>` (worker tables), `cam/child_settings/<id>` (a console table), `cam/sources/<…>` (the contribution to the book, P/03.7), `cam/requests/*` (P/06.4),
  `cam/retention`, `cam/alarms_retention` (P/05 Н1.3), the event buckets `cam/<id>/e<эпоха>` (P/05 Н1.2), the book of licence
  decisions `domain/cam/licence/<член>` and its copy at the member (chapter 7) — the owner of each key is per P/06.1 Н1.1; the heartbeat and the snapshot are platform forms with the fields of `cam` (chapters 2, 5).
- **Doors:** the console — P/06.1, P/06.4 (`cam` has no console routes of its own); the holder — `/playback`, `/devices`,
  `/recordings` (chapter 5, OpenAPI); the delivery RTSP is not HTTP, the form of the address is in the heartbeat (chapter 2).
- **Data families** `data/*.schema.json` (JSON Schema 2020-12) with `*.layers.tsv` and `*.outcomes.tsv` — the heartbeat words of `cam`, the fields of the rows
  of the events `cam-events`, the element of the book `sources`, the licence decision — after the pattern of `Platform/*/data/` (the layers —
  `Platform/common/LAYERS.md`, ADR-0092).
  The camera row, the rows `devices`, `children`, `child_settings`, `device_units`, `unit_next`, `rule_state`, `searches`, `found`, `probes`, `probe_replies` and the body of a request are expressed by the manifest (P/02.1) — they have no families of their own. The lesson's own content in
  the open places of the platform families is [`data/`](../data/): the heartbeat words `cam-heartbeat-words` (the place is the heartbeat root, an empty pointer),
  `value` of the element of the book `sources-entry` and the decision `licence-decision` (the place `/*/entries/*/value`) — the form, the layers, the outcomes per
  reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv) (the column `place`; decision
  «А» of «Архитектор»); the fields of the rows of the events `cam-events` (`io.input` — `port`, `value`; `source-stats` — `dropped`, `depth`; `text` — `lines`, `group`, `camera`, `word`; `unit` — `unit`, `event`, `phase`;
  the place is the root of a row of the platform events family, the trees `cam` and `cam.alarms`). The contribution `cam/sources/<слот>` is a form of the manifest (P/03.7), it is not judged by a VMS family. The vectors of the families are built by
  the builder `family-read` (`VMS/common/vectors/family-read/01.tsv`); there are none by hand.

## Inquiries of the lesson (inventory § 6) — history of the translation

Filed during the translation of their chapter (all resolved; No. 18 — a refusal with a workaround, chapter 7): No. 1 (`{id}` in `default`) — V/01.1; No. 2 (a broken unit row at the worker, the words
`LABELS`), No. 4 (the heartbeat fields), No. 13 (protection of the holder door) — V/01.2, V/01.5; No. 3 (`command`/`command.failed`) —
V/01.4; No. 19 (the door of a cluster of one after the first publication) — V/01.6; No. 18 (the licence) — V/01.7. The cross-cutting
No. 5, 6, 16 have already been filed (`decisions/inbox/2026-10-23-запрос-vms-*.md`). The camera streams (the owner's decision of 2026-10-26, V/01.1
Н1.1а) — an inquiry after stage C `decisions/inbox/2026-10-26-запрос-vms-потоки-камеры.md`: an empty `about`, a tree for `about`
on its own subsystem, the group `group_by` on several holders.

## Differences from the witness that the lesson records (inventory § 7)

The snapshot ceiling is 64 MiB (P/04 Н1.3а), not 64 KiB; there is no field `folders`: folders are cluster records (ADR-0096 §8, without a move); the start gate per P/03.3 Н3 step 2
(the secret before the epoch, `may_act` before the start); `stalled` per P/03.3 Н1.2; a device that has not been opened is `refused` (P/03.6);
`DELETE /devices/<хост>` at the console — 200 with `cas` (P/06.1 Н1.6), the holder writes the row again on the next pass (P/03.4
Н1.6, V/01.4); admission to the holder door is the role certificate, the door token `playback_key` and the secret `door/signer` are removed (chapter 5); the metrics `vms_*` → `cam_*`; `POST /vms/requests` →
`/cam/requests`; the event tree `cam/<id>/…`; `/run/vms` → the share `cam.shm` (`/run/vms-cam-shm`).

## Manifest edits during the translation

Comments that name the witness code (classes and files of the old implementation, `cam/<w>/heartbeat`, «Lesson 6»)
are replaced by references to the norms of the lesson and of the platform; `shares: {shm: {kind: dir}}`; `worker.reads` — per chapter 6; keys and
values change only where a norm requires it, with a record in the chapter; the product — by a debt row to «Сборка».

## id-map

The rows of `VMS/common/id-map.tsv`: `old` is the address of a step of the former lesson (`М10B/04 ш.3а`), `new` is `V/01.K-MM` (the answer
of «Архитектор» of 2026-10-23), per chapter at its translation.

## Order of work — history of the translation

Chapter by chapter, a commit per chapter: V/01.1 → V/01.2 → V/01.4 → V/01.5 → V/01.3 → V/01.6; V/01.7 — after the decision on the
inquiry (resolved, chapter 7 is translated). The lecture `01-cam.md` and the instructions `spec/01-cam.README.md` — with the first chapter, and they are supplemented chapter by chapter. The acceptance
is written as scenarios together with the chapter; the run — after the first stage C generation that has passed the platform acceptance (ADR-0090
addenda (8), (9)). `lessons.tsv` — `переведён` after the last chapter.

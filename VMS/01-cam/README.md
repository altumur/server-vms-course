# V/01 Camera

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/01 is

The subsystem `cam`: a camera (or another device: `type` — `ipsrv`, `eventsrc`, `acfa`) as a unit; its holder is the worker `camworker`, which
opens the device with one connection, delivers the stream to the subscribers (`rec`, `live`, `det`) and answers the commands and
questions to the device; the archive of the device itself (a card, an NVR) and its doors; the camera's contribution to the domain. Everything common — the worker
runtime, the slot, the epoch, the lease, requests, events, the console doors, the domain — is platform norms by reference (P/…); the lesson does not
repeat them. `cam` has no separate HTTP contract of the console (the unit doors are P/06.1); the holder has its own door (chapter
5) — `spec/01-cam.api.openapi.yaml`.

## Chapters

| Chapter | Subject | Platform norms it relies on |
|---|---|---|
| V/01.1 | The camera as a unit: fields, the address and credentials, the tables `devices`, `children`, `child_settings`, `rule_state`, placement, the snapshot, console words, event suppression | P/02.1; P/06.1 N1.1–N1.3, N1.6; P/06.2 N1.1, N1.1a, N1.4; P/04 N1.3, N1.3a; P/06.3 N1.5; the contracts row-check, url-credentials, group-of, gate-and-pass; P/06.5 N1.2; P/03.6 N1.2; P/05 N1.3 |
| V/01.2 | The camera holder: the desired state, the pipeline, delivery (RTSP and shared memory — the share `cam.shm`), observations → events, heartbeat and phase words, store silence, stopping, the worker budget | P/03.1 N2; P/03.2; P/03.3; P/03.4 N1.1, N1.2; P/03.5; P/03.6 N1.2; P/02.4 N1.1, N1.2; ADR-0091 items 5, 6 |
| V/01.3 | The source `driverpack://file/<name>`: a file as a camera (pace, PTS, address refusal) | P/03.3 N1.2; P/06.2 N1.1a (the contract url-credentials) |
| V/01.4 | Commands and questions to the device: the requests `output`, `preset`, one call per group, the answer, the row `cam/devices/<host>` (what the device can do, `identity`), the device's children and the block owner (ADR-0102), arming and switching off for a time (ADR-0105) | P/06.4 N1.5, N3; P/03.6 N1.5, N3 «holder view», «Device action»; P/06.1 N1.6; ADR-0091 item 6 |
| V/01.5 | The device archive and its doors: `/playback`, `/devices`, `/recordings`, `playback_url`, `coverage`, playback sessions; admission is the role certificate (class `mixed`), without a kit — loopback | P/03.4 N1.1, N1.7; the role certificate contract (class `mixed`); P/06.5 N3 `/where`; P/04 N1.3 `group_by` |
| V/01.6 | The camera on the domain: `ref`, `view`, `edit`, the book `sources`, the book `licence` (the worker on the domain exists only for it), the tokens `stream`, `poll`, `ask`, `shared`, `keys`; the stream pusher into the receiver; the camera as a cluster of one; an order of recording onto the card of the server | P/02.1 N1.2b; P/03.7; P/08.1, P/08.5, P/08.6, P/08.7, P/08.9; P/06.7 N1.11, N1.14; P/09.1; P/02.4 N1.10, N1.11 |
| V/01.7 | The licence at the consumer: a document in the common settings of the domain, the count for the whole domain by the worker on the domain `camdomain`, the book of decisions, application at the holder | P/08.9 N1.2; P/03.7 N1.6; P/08.1 N1.4; P/08.5 N1.4, P/09.1 N1.4 `member_row`; the observation contract; P/02.1 N1.2b |
| V/01.8 | Device search: a search row per cluster, the findings `found`, the question about the model, the entry into the driver; the result is only a finding | V/11.4 N1.9 |

The subsystems that consume the door and the heartbeat of `cam` (`rec`, `live`, `det`, `detedge`) refer to chapters 2, 5; the lesson does not norm
their behaviour (addendum (4) item 2).

## Forms and doors (N1, N2 by chapter)

- **Rows and objects** (the catalogue `../common/data/catalog.tsv` receives the rows of the lesson): `cam/cameras/<id>`, `cam/next_id`
  (P/06.1), `cam/devices/<host>`, `cam/children/<id>`, `cam/rule_state/<id>` (worker tables), `cam/child_settings/<id>` (a console table), `cam/sources/<…>` (the contribution to the book, P/03.7), `cam/requests/*` (P/06.4),
  `cam/retention`, `cam/alarms_retention` (P/05 N1.3), the event buckets `cam/<id>/e<epoch>` (P/05 N1.2), the book of licence
  decisions `domain/cam/licence/<member>` and its copy at the member (chapter 7) — the owner of each key is per P/06.1 N1.1; the heartbeat and the snapshot are platform forms with the fields of `cam` (chapters 2, 5).
- **Doors:** the console — P/06.1, P/06.4 (`cam` has no console routes of its own); the holder — `/playback`, `/devices`,
  `/recordings` (chapter 5, OpenAPI); the delivery RTSP is not HTTP, the form of the address is in the heartbeat (chapter 2).
- **Data families** `data/*.schema.json` (JSON Schema 2020-12) with `*.layers.tsv` and `*.outcomes.tsv` — the heartbeat words of `cam`, the fields of the rows
  of the events `cam-events`, the element of the book `sources`, the licence decision — after the pattern of `Platform/*/data/` (the layers —
  `Platform/common/LAYERS.md`, ADR-0092).
  The camera row, the rows `devices`, `children`, `child_settings`, `device_units`, `unit_next`, `rule_state`, `searches`, `found`, `probes`, `probe_replies` and the body of a request are expressed by the manifest (P/02.1) — they have no families of their own. The lesson's own content in
  the open places of the platform families is [`data/`](data/): the heartbeat words `cam-heartbeat-words` (the place is the heartbeat root, an empty pointer),
  `value` of the element of the book `sources-entry` and the decision `licence-decision` (the place `/*/entries/*/value`) — the form, the layers, the outcomes per
  reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv) (the column `place`; decision
  «A» of Architect); the fields of the rows of the events `cam-events` (`io.input` — `port`, `value`; `source-stats` — `dropped`, `depth`; `text` — `lines`, `group`, `camera`, `word`; `unit` — `unit`, `event`, `phase`;
  the place is the root of a row of the platform events family, the trees `cam` and `cam.alarms`). The contribution `cam/sources/<slot>` is a form of the manifest (P/03.7), it is not judged by a VMS family. The vectors of the families are built by
  the builder `family-read` (`VMS/common/vectors/family-read/01.tsv`); there are none by hand.

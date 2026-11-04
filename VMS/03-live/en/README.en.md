# V/03 Live video

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/03.1–V/03.6 (2026-10-23; review 2026-10-29); the sections below on the plan decisions, the inquiries,
the edits and the order are the history of the translation. Sources: the inventory [`../common/inventory.md`](../../common/inventory.md) § 1, § 2
(М10B/13; М12A/03; М12B/01 step 6a; М12B/03 step 4). The platform: the export `cammeta-specs` `7a875c75` (the VMS pin; the chapters were written
on `f6f3895` … `180c6c5` — see their heads). The manifest is [`live.subsystem.yaml`](../live.subsystem.yaml) (the canon; ADR-0090
addendum (6) item 8).

## What lesson V/03 is

The subsystem `live` is the live video gateway. The unit is the delivery of a camera to viewers («camera 7 is watched through the gateway g-2»): one per
camera; the first viewer creates it (`POST /live/streams`, the right `view` on the camera) and the gateway deletes it after a grace once the last one
has left. The workers are the gateways `liveworker`: stateless, their number is by demand, the capacity is in viewers. A gateway holds one
subscription to the camera stream for any number of viewers and gives it to browsers over WebRTC (WHEP: the offer and the answer in one exchange, without
trickle), without transcoding; to devices (a video wall, a foreign VMS) — over RTSP with the accounts of the cluster. The bytes go gateway ↔
browser past the console (the owner's decision 1, ADR-0015): the console issues the door address and a token (`GET /live/where/<cam>`).
Everything common — placement, the worker runtime, the console doors, the door token, the domain books — is platform norms by reference (P/…).

## Chapters

| Chapter | What it norms | Former steps | Platform |
|---|---|---|---|
| V/03.1 | The delivery is a unit by demand: the fields (`cam` is the row name, `labels`, `grace`), `about`, the stream is at the gateway door, creation by the first viewer (`rights.routes: {view: [streams]}`), the second one — 409 `exists`, `PUT` with `view` — 403; placement (`capacity` in viewers with `unit_mb`/`base_mb`, `headroom`, `labels-subset`, `most-free-capacity`, `grows`, `rebalance`, `unplaced.delete_after`); `lease: {unconfirmed_max: off}`; the snapshot, the words | М10B/13 steps 1–2; М12A/03 «кто обслуживает» | P/02.1; P/06.1 Н1.1, «создать» (409 `exists`); the contract gate-and-pass «Права по телу»; P/04 Н1.3, Н3 (`grows`, `unplaced`); P/02.4 Н1.5 (`workers_wanted`); P/03.2 Н1.6 (`unconfirmed_max`); ADR-0067, ADR-0070, ADR-0084 |
| V/03.2 | The source and one subscription: the camera holder on its own server — loopback RTSP (`live_url`, V/01.2 Н1.3; the joint of the subsystems is loopback RTSP, `cam.shm` is not taken); on another server, or a camera of another cluster — the receiver of its own cluster (the viewer's wish, the live edge, `LINGER`, V/02.9 Н1.3); the delivery epoch, reconciliation with the holder's heartbeat (`resets`), the count of subscriptions, two gateways on one camera | М10B/13 steps 3–4; М12A/03 «ответвление и одна подписка»; М12B/03 step 4, step 9 (`live_road`) | P/03.2 Н1.5 (the epoch); P/03.3; P/02.5 Н1.4 (`worker.reads: [cam/heartbeats/]`); V/01.2; V/02.9 |
| V/03.3 | The WHEP door: the address and the token (`/where/<cam>`, the door token contract, the route `whep`), `POST /whep/<cam>` — the stream choice by `?width=&height=`, an offer `application/sdp` → 201, an answer with candidates, `Location` of the session; `DELETE /whep/session/<id>` — its own token; the codes (400 without `m=video`, 403, 404 no subscription yet, 413 `MAX_OFFER`, 415 not SDP, 503 full); ICE ≤ 5 s; the log `live.view`, `live.view.ended`; the door limits | М10B/13 steps 3, 5, 7; М12A/03 «граница» | P/06.5 Н3 «`/where/<id>`»; P/03.4 Н1.7 (the address, the limits), Н3 «токен двери у держателя»; P/03.6 (the log); the door token contract |
| V/03.4 | The media path: a branch per viewer from the tee, a leaky queue, the payload type from the offer (96–127, `packetization-mode=1`), the pipeline at the first viewer, video without transcoding, sound (an exception: AAC, G.726, PCM, MP2 into Opus), the codec note (`codec`); H.265 | М10B/13 step 6 | — (a property of the subsystem) |
| V/03.5 | The end of demand and refusals: the grace `grace` → deletion of the row by the gateway (`worker.deletes`), a camera without a holder — `waiting` and deletion after `grace`, reconciliation (`resets`), collection of dead sessions (`CONNECT_SECONDS`, `swept`); the heartbeat (`headroom`, `subscriptions`, `sessions`, `resets`, `swept`, `codec`, `rtsp`), the row phase for `streams_live`; a stateless process; the arithmetic of refusals | М10B/13 steps 4–5, 8; М12A/03 «арифметика отказов» | P/02.1 (`worker.deletes`), P/04 Н3 step 8; P/03.3; P/03.4 Н1.1, Н3; P/06.5 (the series, `console.running`) |
| V/03.6 | Stream accounts and the RTSP door: the table `accounts` (`tables`, the gateway only), the doors `/live/accounts` through the console (`door.pass`), the password once, the book `stream-accounts` (the contribution of one gateway of the cluster, `names` with `exclusive_with: domain/users`), the grants of the accounts, the gateway's RTSP door (`RTSP_PORT` of the subsystem file, an endpoint per camera, the accounts with `view`, the log `live.rtsp.play`/`ended`) | М12B/01 step 6a (the form C5, ADR-0074) | P/02.1 (`tables`, `door.pass`); the contract gate-and-pass «Передача `door.pass`»; P/03.5; P/03.7 Н1.2; P/08.4 Н3; P/08.5 Н1.3, Н1.7; P/09.1 Н1.4 |

The neighbouring subsystems: the camera holder (V/01, delivery); the receiver (V/02.9); the page (V/11, the shell — live video and «Учётки потоков»);
the GStreamer packages and `libnice` in the image — V/09.

## Forms and doors

- **Rows and objects:** `live/streams/<cam>` (the unit), the table `live/accounts/<имя>` (`password_secret`), the contribution
  `live/stream-accounts/<слот>`, the copy of the book `domain/live/stream-accounts`; the heartbeat `live/heartbeats/<воркер>`; the gateway
  log (`live.view*`, `live.rtsp.*`).
- **Data families** (the class of VMS families, decision «А» of «Архитектор»): the delivery row, the table `accounts` and the contribution
  `live/stream-accounts/<слот>` are expressed by the manifest (P/02.1) — they have no families of their own. The lesson's own content in the open places of the platform
  families is [`data/`](../data/): `value`
  of the element of the book of accounts `stream-accounts-entry` (the place `/*/entries/*/value`; the password is only a keyring envelope) — the form, the layers,
  the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv) (the column
  `place`); the vectors are built by the builder family-read, they are not written by hand. The gateway's heartbeat words are the family
  `live/heartbeats/<имя>` ([`data/live-heartbeat-words.schema.json`](../data/live-heartbeat-words.schema.json); read by `camworker`, `expworker`); `capacity` is judged by the platform controller (the pool contract), `headroom` is shown by the console with the series `worker_headroom` and
  `headroom` (P/06.5 Н3; the controller does not read it, P/04 Н1.3).
- **Doors:** the gateway door `whep` (the page, the console door token) and `/live/accounts` through `door.pass` — the lesson's OpenAPI
  `spec/03-live.api.openapi.yaml`; the gateway's RTSP door is RTSP with Digest (not HTTP), chapter 6.

## Decisions made for the plan (made by «Архитектор» 2026-10-23)

1. **A source on another server is the receiver of its own cluster.** The holder's RTSP is loopback only (V/01.2 Н1.3, ADR-0075 window 2);
   the witness's expectation of `RTSP_HOST` is removed. A gateway on a server without the holder wants the stream from the receiver of its own
   cluster (the live edge, `LINGER` 10 s) — the same for a camera of another cluster. For this, V/02.9 is supplemented in chapter V/03.2:
   (a) the pusher of a server camera (the first recorder of the holder's server, V/02.9 Н1.2) also pushes into the receiver of **its own**
   cluster when that one wants it (not only by an assignment into a foreign one); (b) the receiver admits the processes of its own cluster by the
   role certificate (`liveworker`, `recworker`) alongside the domain token — the class `mixed`, like the archive door (ADR-0091 addendum (7)).
   The alternative — placing the gateway at the holder (`near`) — breaks the viewers' `labels` (the public address); I do not take it.
2. **The viewer's right is checked by the gateway door** by the console door token (М10B/13, `door.routes: [whep]`); «the gateway passes and does not
   authorize», the check of the right by the connection point of the cluster (М12A/03) — removed.
3. **The video codec — without transcoding, H.264 and H.265 are passed through** with the payload type from the offer (the shell moves the PT of H.265 into
   96–127). Refined by the review (question 6): the first offer opens the source before the answer and waits for the stream parameters within the budget
   `ICE_WAIT` (if they have not arrived — 404 `not yet`); the payload type of the delivery's codec is absent from the offer — 400 `bad offer`; a profile or a
   codec that the browser may fail to play — the note `codec` in the heartbeat, not a refusal (V/03.3 Н1.2, V/03.4). Transcoding,
   fMP4 and the gateway's TURN (М12A/03) are not carried over.
4. **The constants — V/03:** `MAX_OFFER` 256 KiB, ICE ≤ 5 s, `CONNECT_SECONDS` 30, `grace` 60 (a field), the RTSP latency 200 ms;
   the page's retries (1.5 s × 8, reconnection) — V/08.
5. **`door.pass` without a gateway** — 503 of the contract gate-and-pass («no worker of live with a door is heard»), not 409 of the form C5.
6. **Two graces:** a row without a holder — the controller (`unplaced.delete_after` 30); a row with a holder but without a source
   (no camera, not `running`) — the gateway, after `grace` from the first pass that saw it.
7. **`worker.reads` is supplemented with `cam/heartbeats/`** — the holder and `live_url` by the heartbeat of `cam` (P/02.5 Н1.4; `rec` does the same,
   `33d1fbde3`); finding the holder is reading the heartbeats, no platform norm of its own is needed.

## Inquiries of the lesson

None in advance: the door limits (inventory § 6 No. 13) — P/03.4 Н1.7 `door_limits`; the door address — P/03.4 Н1.7; the log and CORS —
ADR-0091 addenda (7), (8). The course has no RTSP server with Digest: the RTSP door is normed by behaviour, the server is decided by the implementation;
the acceptance of the accounts — through `/live/accounts`, playing over RTSP — by reading (the stand has no RTSP client with Digest).

## Differences from the witness that the lesson records

`worker: {writes: [streams]}` → `deletes: [streams]` (ADR-0067); `offers`/`live_workers_needed` → `grows`/`workers_wanted`
(ADR-0084); the source of a foreign server is the receiver, not RTSP; the token check by the gateway is the platform door token (P/03.4 Н3); its own
pass loop is the runtime P/03.3, P/03.4; the witness's media code and entry point, the branch `domainpart` are not carried over (the implementation);
`stream-clients`, `DOMAIN_CONSOLE_URL`, `accounts_secret` → `live/accounts`, `/live/accounts` through `door.pass`,
`password_secret` (the form C5, ADR-0074); the route `POST /whep` → `POST /whep/<cam>`.

## Manifest edits during the translation

`worker.reads` + `cam/heartbeats/`; the comments with the witness code and `live_workers_wanted` — replaced by references to the
norms; the row phase for `streams_live` — per chapter 5. The product — by a debt row to «Сборка» per chapter.

## Order of work

Chapter by chapter, a commit per chapter: V/03.1 → V/03.2 → V/03.3 → V/03.4 → V/03.5 → V/03.6. The lecture `03-live.md` and the instructions
`spec/03-live.README.md` — with the first chapter. Acceptance: 1 — the directory `acceptance/1` (creation, 409, the bounds of `grace`; the domain
stand — 403 before `exists`, `PUT` with `view`); 3 — the directory `acceptance/3` (the stream choice by size, `@manual`); 3 and 6 — with the stand of the worker `live`, as in Н5 of chapters 3 and 6 (the WHEP door without a token,
a body beyond the limit, not SDP, hang-up; the accounts through `door.pass` with the role kit), until then — by reading; the run — after the first
stage C generation that has passed the platform acceptance. `lessons.tsv` — `переведён`.

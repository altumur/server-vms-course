# V/03 Live video

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/03 is

The subsystem `live` is the live video gateway. The unit is the delivery of a camera to viewers («camera 7 is watched through the gateway g-2»): one per
camera; the first viewer creates it (`POST /live/streams`, the right `view` on the camera) and the gateway deletes it after a grace once the last one
has left. The workers are the gateways `liveworker`: stateless, their number is by demand, the capacity is in viewers. A gateway holds one
subscription to the camera stream for any number of viewers and gives it to browsers over WebRTC (WHEP: the offer and the answer in one exchange, without
trickle), without transcoding; to devices (a video wall, a foreign VMS) — over RTSP with the accounts of the cluster. The bytes go gateway ↔
browser past the console (the owner's decision 1, ADR-0015): the console issues the door address and a token (`GET /live/where/<cam>`).
Everything common — placement, the worker runtime, the console doors, the door token, the domain books — is platform norms by reference (P/…).

## Chapters

| Chapter | What it norms | Platform |
|---|---|---|
| V/03.1 | The delivery is a unit by demand: the fields (`cam` is the row name, `labels`, `grace`), `about`, the stream is at the gateway door, creation by the first viewer (`rights.routes: {view: [streams]}`), the second one — 409 `exists`, `PUT` with `view` — 403; placement (`capacity` in viewers with `unit_mb`/`base_mb`, `headroom`, `labels-subset`, `most-free-capacity`, `grows`, `rebalance`, `unplaced.delete_after`); `lease: {unconfirmed_max: off}`; the snapshot, the words | P/02.1; P/06.1 N1.1, «create» (409 `exists`); the contract gate-and-pass Rights by body; P/04 N1.3, N3 (`grows`, `unplaced`); P/02.4 N1.5 (`workers_wanted`); P/03.2 N1.6 (`unconfirmed_max`); ADR-0067, ADR-0070, ADR-0084 |
| V/03.2 | The source and one subscription: the camera holder on its own server — loopback RTSP (`live_url`, V/01.2 N1.3; the joint of the subsystems is loopback RTSP, `cam.shm` is not taken); on another server, or a camera of another cluster — the receiver of its own cluster (the viewer's wish, the live edge, `LINGER`, V/02.9 N1.3); the delivery epoch, reconciliation with the holder's heartbeat (`resets`), the count of subscriptions, two gateways on one camera | P/03.2 N1.5 (the epoch); P/03.3; P/02.5 N1.4 (`worker.reads: [cam/heartbeats/]`); V/01.2; V/02.9 |
| V/03.3 | The WHEP door: the address and the token (`/where/<cam>`, the door token contract, the route `whep`), `POST /whep/<cam>` — the stream choice by `?width=&height=`, an offer `application/sdp` → 201, an answer with candidates, `Location` of the session; `DELETE /whep/session/<id>` — its own token; the codes (400 without `m=video`, 403, 404 no subscription yet, 413 `MAX_OFFER`, 415 not SDP, 503 full); ICE ≤ 5 s; the log `live.view`, `live.view.ended`; the door limits | P/06.5 N3 «`/where/<id>`»; P/03.4 N1.7 (the address, the limits), N3 door token at the holder; P/03.6 (the log); the door token contract |
| V/03.4 | The media path: a branch per viewer from the tee, a leaky queue, the payload type from the offer (96–127, `packetization-mode=1`), the pipeline at the first viewer, video without transcoding, sound (an exception: AAC, G.726, PCM, MP2 into Opus), the codec note (`codec`); H.265 | — (a property of the subsystem) |
| V/03.5 | The end of demand and refusals: the grace `grace` → deletion of the row by the gateway (`worker.deletes`), a camera without a holder — `waiting` and deletion after `grace`, reconciliation (`resets`), collection of dead sessions (`CONNECT_SECONDS`, `swept`); the heartbeat (`headroom`, `subscriptions`, `sessions`, `resets`, `swept`, `codec`, `rtsp`), the row phase for `streams_live`; a stateless process; the arithmetic of refusals | P/02.1 (`worker.deletes`), P/04 N3 step 8; P/03.3; P/03.4 N1.1, N3; P/06.5 (the series, `console.running`) |
| V/03.6 | Stream accounts and the RTSP door: the table `accounts` (`tables`, the gateway only), the doors `/live/accounts` through the console (`door.pass`), the password once, the book `stream-accounts` (the contribution of one gateway of the cluster, `names` with `exclusive_with: domain/users`), the grants of the accounts, the gateway's RTSP door (`RTSP_PORT` of the subsystem file, an endpoint per camera, the accounts with `view`, the log `live.rtsp.play`/`ended`) | P/02.1 (`tables`, `door.pass`); the contract gate-and-pass «Transmission `door.pass`»; P/03.5; P/03.7 N1.2; P/08.4 N3; P/08.5 N1.3, N1.7; P/09.1 N1.4 |

The neighbouring subsystems: the camera holder (V/01, delivery); the receiver (V/02.9); the page (V/11, the shell — live video and «Stream accounts»);
the GStreamer packages and `libnice` in the image — V/09.

## Forms and doors

- **Rows and objects:** `live/streams/<cam>` (the unit), the table `live/accounts/<name>` (`password_secret`), the contribution
  `live/stream-accounts/<slot>`, the copy of the book `domain/live/stream-accounts`; the heartbeat `live/heartbeats/<worker>`; the gateway
  log (`live.view*`, `live.rtsp.*`).
- **Data families** (the class of VMS families, decision «A» of Architect): the delivery row, the table `accounts` and the contribution
  `live/stream-accounts/<slot>` are expressed by the manifest (P/02.1) — they have no families of their own. The lesson's own content in the open places of the platform
  families is [`data/`](data/): `value`
  of the element of the book of accounts `stream-accounts-entry` (the place `/*/entries/*/value`; the password is only a keyring envelope) — the form, the layers,
  the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv) (the column
  `place`); the vectors are built by the builder family-read, they are not written by hand. The gateway's heartbeat words are the family
  `live/heartbeats/<name>` ([`data/live-heartbeat-words.schema.json`](data/live-heartbeat-words.schema.json); read by `camworker`, `expworker`); `capacity` is judged by the platform controller (the pool contract), `headroom` is shown by the console with the series `worker_headroom` and
  `headroom` (P/06.5 N3; the controller does not read it, P/04 N1.3).
- **Doors:** the gateway door `whep` (the page, the console door token) and `/live/accounts` through `door.pass` — the lesson's OpenAPI
  `spec/03-live.api.openapi.yaml`; the gateway's RTSP door is RTSP with Digest (not HTTP), chapter 6.

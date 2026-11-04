# V/02 Recording

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/02.1–V/02.9; the sections «Decisions taken for the plan», «Inquiries of the lesson», «Differences from
the witness», «Manifest edits», «Order of work» are the history of the translation. Sources: the inventory
[`../common/inventory.md`](../../common/inventory.md) § 1, § 2. The platform: the export `cammeta-specs` `7a875c75` (the chapter headers —
on their own exports). The manifest is
[`rec.subsystem.yaml`](../rec.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8).

## What lesson V/02 is

The subsystem `rec`: the recording of a camera as a unit; its holder is the recorder `recworker`, which takes the stream from the camera
holder (V/01) and writes it into a volume of the archive engine; the engine `obsd` is a part of the subsystem with its own service; volume kinds, holds and
labels, catch-up recording from the device archive, the archive door for the page and for processes, recording on the domain (the receiver of the pushed stream,
the books, the chain). Everything common — places and captures, the worker runtime, requests, event holds, the console doors, the domain — is
platform norms by reference (P/…). The largest lesson of VMS.

## Chapters

| Chapter | Subject | Sources (inventory § 2) | Platform norms it relies on |
|---|---|---|---|
| V/02.1 | The recording as a unit: the fields (`cam`, `retention_days`, `home`, `until`), `about`, `fixed`, `ref` and the forms of `cam` (`<id>` \| `ref:<ref>`), `stream` with `must_match` (`home` has none — the guard of the card is the recorder); the tables `volumes`, `keeps`; placement (`places`, `place_by`, `affinity`, `servers: distinct`, `grows`); the snapshot, rights (`unit_of`, `reach`); the deadline `placement.ends` | М10B/10 steps 1–3; М10B/27 steps 1–2; М10B/01 step 4 (the retention of a video); М10B/26 step 5; «СКОЛЬКО-ЗАПИСЕЙ» | P/02.1; P/06.1 Н1.1–Н1.3, Н1.6 (the contract row-check); P/04 Н1.3 (`places`, `affinity`, `near`, `ends`, `grows`); P/06.3 Н1.5 (the contract gate-and-pass); ADR-0091 item 2 |
| V/02.2 | The engine `obsd` as a part of `rec`: the protocol is a separate contract of the lesson (`spec/02-rec.obsd.contract.md`; V/02.3–V/02.5 refer to it and do not repeat it — the word of «Архитектор» of 2026-10-23) (the frame, the session, a break and silence, archive time, the volume, the writer, the reader, blocks, the ring, one writer and the deferral), the part `parts.obsd`, the socket share, the environment, the timeouts | М10B/06; М10B/17 step 5; М10B/07 step 12 (the deferral) | P/02.1 `parts`, `shares.part`; P/02.4 Н1.1 (the unit and the runner of the part, `stop_timeout`, `After=`), Н1.2 (`W2C_SUB_ENV`); ADR-0091 items 4–5, addenda (2), (3) |
| V/02.3 | A stream in a volume: the stream names (`<запись>/e<эпоха>`, `…/backfill`, `…/e0`), a segment from the index, the volume refusals `wrong`/`away`/`busy`, opening a volume, putting a frame, a killed recorder, the daemon is gone | М10B/07 | P/03.2 Н1.2, Н1.3, Н3 «место»; P/03.4 Н3 SIGTERM |
| V/02.4 | The recorder: the source from the heartbeat of `cam` (`live_shm`/`live_url`, the book `domain/cam/sources`), the receiver actuator, a start refusal as a state, resubscription, holding a volume as a place, leaving a volume, the writer watchdog, depth and numbers; the close deadline SIGTERM + 33 s | М10B/09 (the receiver); М10B/10 steps 4–13; М10B/27 steps 5–9; М10B/28 steps 2–6 | P/03.1–03.4; P/03.2 Н1.2 (the place windows), Н1.6; ADR-0091 item 9 (`place_by: ""`); P/02.1 `worker.uses` (the share `cam.shm`, the share of the part `obsd`) |
| V/02.5 | Visibility, retention, the timeline and the archive door: `/spans`, `/samples` (processes), `/timeline`, `/segment` (the page, the door token), fMP4 pieces, the interval across epoch boundaries, `.device.mp4` from the holder door | М10B/08; М10B/20 (the `rec` half); М10B/24; М10B/15 steps 7–9 | P/06.5 Н3 `/where`, `door.routes`; P/03.4 Н3 «токен двери у держателя», Н1.7 the door limits; the door token contract |
| V/02.6 | Volume kinds and its own backup archive: `local`, `network`, `edge`, `backup`, `incidents`; the quota is the ring size; backup recording and pre-recording; the card of the server; `when: offline` | М10B/26; М10B/27 steps 3–4, 10–12; М10B/18 steps 1–3 | P/04 Н1.3 (`affinity`, `admits`, `near.prefer`); P/06.2 Н1.1 (`access_secret`); P/02.4 Н1.1 (the volumes of a part) |
| V/02.7 | Holds and labels: the table `keeps`, a copy in `incidents`, the seal `rec/sealed/*`, the `holds` of events, the request to free space (`free`, the answer `freeing`) | М10B/18 steps 4–8; М10B/11 steps 4–5 | P/06.4 Н1.5 (`holds`, ADR-0091 item 8); P/05 Н1.4 (`free-*`); P/06.1 Н1.6 |
| V/02.8 | Catch-up recording and the scan order: the catch-up request (the schema, `key`, `per_person`, `settle`, `ttl`, the profile `fetched`), the budget and the window, only holes, landing into its own volume; two holes of one cause — an order of `detjob` (`worker.creates`) | М10B/16; М10B/22; М10B/15 steps 7–9 | P/06.4 Н1.5, Н3; P/03.6 Н1.5, Н1.6 (ordering a row), Н3 «Дозапись»; ADR-0091 item 1 |
| V/02.9 | Recording on the domain: a stream from another cluster (the book `sources`), the books `primaries`, `ingest` (the addresses and the life of the recorders, the key is the cluster), `polls`, `upstream` (`key: relay`: the relay's element is the addresses of the centre, written by the first recorder of the centre), the token `upstream`, the report `rec/polled` and the witness, the receiver of the pushed stream, several receivers, the reserve, the chain site — relay — centre, the archive on the centre's claim | М10B/10 step 14; М12B/02, 03 (the receiver), 04; М12A/13 | P/03.7; P/08.3, P/08.5–P/08.7; P/09.1, P/09.2; P/10 Н1.8 |

The subsystems that consume the archive door are the page (V/11, the shell) and detection by interval (V/05); the camera holder is V/01
(delivery and the device archive door); the orderer of recording by scenario is `auto` (V/07).

## Forms and doors

- **Rows and objects** (the common platform families; the VMS catalogue holds only what is its own beyond them): `rec/recordings/<id>`, the tables
  `rec/volumes/*`, `rec/keeps/*`, the places `rec/holds/<том>`, the objects `rec/used/*`, `rec/sealed/*`, `rec/taken/*`,
  `rec/ingest/clock/*`, `rec/ingest/up/*` (`objects`), the order debt `rec/state/scan/*`, the requests `rec/requests/*`, the contributions to the books `rec/primaries/*`,
  `rec/upstream/*`, `rec/polls/*`, the report `rec/polled/<приёмник>`.
- **Data families** — the lesson's own content in the open places of the platform families, which other processes read and the manifest does not
  express — [`data/`](../data/): the heartbeat words `rec-heartbeat-words` (`ingest`, `url`, `volume`, `stream.lagging`, `written_through`
  of a recording element; the place is the heartbeat root, an empty pointer), `value` of the elements of the books `primaries-entry`, `ingest-entry`, `polls-entry`,
  `upstream-entry` (the place `/*/entries/*/value`; `#copy` — the copy at the member, `#member` — the member row at the domain holder; `primaries`, `ingest` have only `#member`: the books go to all, the keys are one) —
  the form, the layers, the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv)
  (the column `place`). The objects `rec/ingest/*`, `rec/sealed/*`, `rec/used/*`, `rec/taken/*` (`objects` of the manifest) and the contributions
  `rec/<книга>/<слот>` are a form of the manifest, they are not judged by a VMS family; the witness `rec/polled/<слот>` is read by the domain console per the
  declaration `witness` (P/10 Н1.8). The vectors — the builder `family-read` (`VMS/common/vectors/family-read/02.tsv`).
- **Doors:** the recorder's archive door (`/spans`, `/samples` — processes, the class `mixed`; `/timeline`, `/segment`, `/keeps` —
  the page, the door token) — the lesson's OpenAPI `spec/02-rec.api.openapi.yaml`; the receiver door (polling, the push, `/ask`) — chapter 9;
  the protocol `obsd` — the part socket (not HTTP), chapter 2.

## Decisions taken for the plan (inventory § 7 and checks) — history of the translation

- `rec` declares `grows: true` (P/04 Н3 «нехватка(), заказать()» for `servers: distinct` with the place from the heartbeat) — the recorder
  of a recording that has nowhere to be written raises an order of workers; there are no spare ones (ADR-0084); the volume — by the row `rec/wanted` (`places.wanted`, V/02.1 Н1.3).
- A stand-in extends the place (P/03.4 Н3); releasing the place in the middle of work — per ADR-0091 item 9; `may_stand_in_hold` and the countdown
  `FOR` of the witness are not carried over.
- The volume did not open — `place_by: ""` in the heartbeat (ADR-0091 item 9); the hold is released per P/03.2.
- `worker.stop_timeout: 47`; the close deadline at stopping is SIGTERM + 33 s (live recording 2, `FINISH_MEDIA` 1, the contract 30);
  closing the writers of all places at once — by the «close deadline» of V/02.4 Н1.5 (the analysis of the V/02 review, question 2; formerly «≈ 22 s fits», the word of «Архитектор»
  of 2026-10-23).
- The order of stopping — P/03.4 Н3 SIGTERM (the writers of the places → the heartbeat → the place → the slot).
- The catch-up profile is `requests.outcome: fetched` (P/06.4 Н3 «жнец»): an old claim is closed by the recorder (`fetched` with a
  refusal); if there is no one to close it — the reaper, with the label `expired` at `ttl` + `REAP_AFTER` (V/02.8 Н1.4).
- The recorder's own `/metrics` is not carried over: the series are the `metrics:` of the manifest from the heartbeat.
- `requests.elsewhere: [record]` is removed: a recording by scenario is created by `auto` (`worker.creates`, V/07); `until` →
  `placement.ends: {field: until, never: 0}`.
- The share of the part `obsd` is `shares: {obsd: {kind: socket, part: obsd}}`, its own recorder — `worker.uses: [rec.obsd]`;
  the share `cam.shm` — `worker.uses: [cam.shm]` (ADR-0091 item 5, addendum (2) item 4).
- The archive door for processes — the class `mixed` of the role certificate (ADR-0075 window 2); for the page — the console door token
  (`door.routes`).

## Inquiries of the lesson (inventory § 6) — history of the translation

Filed during the translation of their chapter: No. 7 (`access_secret` of a row of the places table is opened by the worker) — V/02.6; No. 8 (the heartbeat `url`
is not «all interfaces») — V/02.5; No. 11 (the form of `freeing` in the heartbeat) — V/02.7; No. 14 (the holder door log: `archive.read`,
`archive.keep.verified`) — V/02.5, V/02.7. The open questions of the inventory to V/02: the rights `_held_by_the_book` (`cam/placement`,
`cam/slots` — not in `worker.reads`), `domain/rec/primaries` in `rec.worker.reads`, the receiver loss metrics, the rule «a common
network — take it» without `domainpart`, the version of the engine `obsd` for acceptance (ObjectStorage, patches 01–07) — resolved in the chapters.

## Differences from the witness that the lesson records — history of the translation

The order of stopping per P/03.4; `place_by: ""` at an unopened volume; a stand-in extends the place; `grows` instead of a spare;
`/data/vms/obsd/volume` → `/data/platform/subsystems/rec/obsd/volumes/<n>`; `vms-obsd` → `vms-rec-obsd`; the socket is a share of the
part; `TimeoutStopSec` 47 — `worker.stop_timeout` with the close deadline SIGTERM + 33 s; the catch-up profile `fetched`; `elsewhere: [record]`
is removed; the HMAC key of the holder door is not used — the archive door is open to processes by the role certificate.

## Manifest edits during the translation — history of the translation

`placement.ends`, `grows: true`, `parts.obsd {exec, volumes: true, stop_timeout}`, `shares.obsd {kind: socket, part:
obsd}`, `worker.uses: [cam.shm, rec.obsd]`, `worker.stop_timeout: 47`, `unit.state.scan`, `worker.creates` to `detjob` (V/02.8),
`requests.outcome: fetched`; remove `requests.elsewhere`; comments with the witness code and the «console loopback» — replaced by references to the
norms. The product — by a debt row to «Сборка» per chapter.

## Order of work — history of the translation

Chapter by chapter, a commit per chapter: V/02.1 → V/02.2 → V/02.3 → V/02.4 → V/02.5 → V/02.6 → V/02.7 → V/02.8 → V/02.9. The lecture
`02-rec.md` and the instructions `spec/02-rec.README.md` — with the first chapter, supplemented chapter by chapter. Acceptance — as scenarios together with the
chapter (the common stand — [`../common/acceptance/README.md`](../../common/acceptance/README.md); the engine needs a live `obsd` with
patches — the stand names it by the substitution `{obsd}`); the run — after the first stage C generation that has passed the platform acceptance. `lessons.tsv` —
`переведён` after the last chapter.

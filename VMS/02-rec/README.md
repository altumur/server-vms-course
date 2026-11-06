# V/02 Recording

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/02 is

The subsystem `rec`: the recording of a camera as a unit; its holder is the recorder `recworker`, which takes the stream from the camera
holder (V/01) and writes it into a volume of the archive engine; the engine `obsd` is a part of the subsystem with its own service; volume kinds, holds and
labels, catch-up recording from the device archive, the archive door for the page and for processes, recording on the domain (the receiver of the pushed stream,
the books, the chain). Everything common — places and captures, the worker runtime, requests, event holds, the console doors, the domain — is
platform norms by reference (P/…). The largest lesson of VMS.

## Chapters

| Chapter | Subject | Platform norms it relies on |
|---|---|---|
| V/02.1 | The recording as a unit: the fields (`cam`, `retention_days`, `home`, `until`), `about`, `fixed`, `ref` and the forms of `cam` (`<id>` \| `ref:<ref>`), `stream` with `must_match` (`home` has none — the guard of the card is the recorder); the tables `volumes`, `keeps`; placement (`places`, `place_by`, `affinity`, `servers: distinct`, `grows`); the snapshot, rights (`unit_of`, `reach`); the deadline `placement.ends` | P/02.1; P/06.1 N1.1–N1.3, N1.6 (the contract row-check); P/04 N1.3 (`places`, `affinity`, `near`, `ends`, `grows`); P/06.3 N1.5 (the contract gate-and-pass); ADR-0091 item 2 |
| V/02.2 | The engine `obsd` as a part of `rec`: the protocol is a separate contract of the lesson (`spec/02-rec.obsd.contract.md`; V/02.3–V/02.5 refer to it and do not repeat it — the word of Architect of 2026-10-23) (the frame, the session, a break and silence, archive time, the volume, the writer, the reader, blocks, the ring, one writer and the deferral), the part `parts.obsd`, the socket share, the environment, the timeouts | P/02.1 `parts`, `shares.part`; P/02.4 N1.1 (the unit and the runner of the part, `stop_timeout`, `After=`), N1.2 (`W2C_SUB_ENV`); ADR-0091 items 4–5, addenda (2), (3) |
| V/02.3 | A stream in a volume: the stream names (`<record>/e<epoch>`, `…/backfill`, `…/e0`), a segment from the index, the volume refusals `wrong`/`away`/`busy`, opening a volume, putting a frame, a killed recorder, the daemon is gone | P/03.2 N1.2, N1.3, N3 «place»; P/03.4 N3 SIGTERM |
| V/02.4 | The recorder: the source from the heartbeat of `cam` (`live_shm`/`live_url`, the book `domain/cam/sources`), the receiver actuator, a start refusal as a state, resubscription, holding a volume as a place, leaving a volume, the writer watchdog, depth and numbers; the close deadline SIGTERM + 33 s | P/03.1–03.4; P/03.2 N1.2 (the place windows), N1.6; ADR-0091 item 9 (`place_by: ""`); P/02.1 `worker.uses` (the share `cam.shm`, the share of the part `obsd`) |
| V/02.5 | Visibility, retention, the timeline and the archive door: `/spans`, `/samples` (processes), `/timeline`, `/segment` (the page, the door token), fMP4 pieces, the interval across epoch boundaries, `.device.mp4` from the holder door | P/06.5 N3 `/where`, `door.routes`; P/03.4 N3 door token at the holder, N1.7 the door limits; the door token contract |
| V/02.6 | Volume kinds and its own backup archive: `local`, `network`, `edge`, `backup`, `incidents`; the quota is the ring size; backup recording and pre-recording; the card of the server; `when: offline` | P/04 N1.3 (`affinity`, `admits`, `near.prefer`); P/06.2 N1.1 (`access_secret`); P/02.4 N1.1 (the volumes of a part) |
| V/02.7 | Holds and labels: the table `keeps`, a copy in `incidents`, the seal `rec/sealed/*`, the `holds` of events, the request to free space (`free`, the answer `freeing`) | P/06.4 N1.5 (`holds`, ADR-0091 item 8); P/05 N1.4 (`free-*`); P/06.1 N1.6 |
| V/02.8 | Catch-up recording and the scan order: the catch-up recording request (the schema, `key`, `per_person`, `settle`, `ttl`, the profile `fetched`), the budget and the window, only holes, landing into its own volume; two holes of one cause — an order of `detjob` (`worker.creates`) | P/06.4 N1.5, N3; P/03.6 N1.5, N1.6 (ordering a row), N3 Backfill; ADR-0091 item 1 |
| V/02.9 | Recording on the domain: a stream from another cluster (the book `sources`), the books `primaries`, `ingest` (the addresses and the life of the recorders, the key is the cluster), `polls`, `upstream` (`key: relay`: the relay's element is the addresses of the centre, written by the first recorder of the centre), the token `upstream`, the report `rec/polled` and the witness, the receiver of the pushed stream, several receivers, the reserve, the chain site — relay — centre, the archive on the centre's claim | P/03.7; P/08.3, P/08.5–P/08.7; P/09.1, P/09.2; P/10 N1.8 |

The subsystems that consume the archive door are the page (V/11, the shell) and detection by interval (V/05); the camera holder is V/01
(delivery and the device archive door); the orderer of recording by scenario is `auto` (V/07).

## Forms and doors

- **Rows and objects** (the common platform families; the VMS catalogue holds only what is its own beyond them): `rec/recordings/<id>`, the tables
  `rec/volumes/*`, `rec/keeps/*`, the places `rec/holds/<volume>`, the objects `rec/used/*`, `rec/sealed/*`, `rec/taken/*`,
  `rec/ingest/clock/*`, `rec/ingest/up/*` (`objects`), the order debt `rec/state/scan/*`, the requests `rec/requests/*`, the contributions to the books `rec/primaries/*`,
  `rec/upstream/*`, `rec/polls/*`, the report `rec/polled/<receiver>`.
- **Data families** — the lesson's own content in the open places of the platform families, which other processes read and the manifest does not
  express — [`data/`](data/): the heartbeat words `rec-heartbeat-words` (`ingest`, `url`, `volume`, `stream.lagging`, `written_through`
  of a recording element; the place is the heartbeat root, an empty pointer), `value` of the elements of the books `primaries-entry`, `ingest-entry`, `polls-entry`,
  `upstream-entry` (the place `/*/entries/*/value`; `#copy` — the copy at the member, `#member` — the member row at the domain holder; `primaries`, `ingest` have only `#member`: the books go to all, the keys are one) —
  the form, the layers, the outcomes per reader; the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv)
  (the column `place`). The objects `rec/ingest/*`, `rec/sealed/*`, `rec/used/*`, `rec/taken/*` (`objects` of the manifest) and the contributions
  `rec/<book>/<slot>` are a form of the manifest, they are not judged by a VMS family; the witness `rec/polled/<slot>` is read by the domain console per the
  declaration `witness` (P/10 N1.8). The vectors — the builder `family-read` (`VMS/common/vectors/family-read/02.tsv`).
- **Doors:** the recorder's archive door (`/spans`, `/samples` — processes, the class `mixed`; `/timeline`, `/segment`, `/keeps` —
  the page, the door token) — the lesson's OpenAPI `spec/02-rec.api.openapi.yaml`; the receiver door (polling, the push, `/ask`) — chapter 9;
  the protocol `obsd` — the part socket (not HTTP), chapter 2.

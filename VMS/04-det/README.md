# V/04 Live detection

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/04 is

The subsystem `det`: a detector is the unit «one model on one camera» («line crossing on camera 7», `7-linecross`).
Detection workers on servers with a GPU read the camera's stream, run the model and write events into the log of their own server with `of` of the
camera: an event is not a subsystem — it has no unit of work, its place is decided by the writer. The capacity is in streams that the server
decodes and runs. Everything common — placement, the worker runtime, the event log, classes, suppression, the merging of events for the
page — is platform norms by reference (P/…).

## Chapters

| Chapter | What it norms | Platform |
|---|---|---|
| V/04.1 | The detector as a unit: the fields (`cam` `fixed`, `kind`, `params` is opaque (the general row limit), `mask` — a blob, `labels` default `[gpu]`, `alarms`, `until`), `about`, who creates it (the operator through the door; `auto` by the order `worker.creates`, the key `{cam}-{kind}`), the deadline `placement.ends` (manual rows are removed from placement, not deleted — `expired_kept`); placement (`capacity` 8, `labels-subset`, `requires: resource`, `near`, without `home`, `most-free-capacity`, `rebalance`), the headroom — the platform; the snapshot | P/02.1; P/06.1, the contract row-check (`fixed`, blob P/06.1 N1.5); P/04 N1.3 (`near`, `ends`, `unplaced`); P/03.6 N1.6 (`made`); P/03.4 N1.1 (`headroom`) |
| V/04.2 | The source and the model: the holder by the heartbeat; its own server — the share `cam.shm` (`worker.uses`), the fallback — the loopback RTSP; another server — the receiver of its own cluster (as V/03.2); reconciliation on each pass; the model — the worker's kind registry, the course's teaching model `tick`; the phases `running` / `pending` / `waiting` / `unsupported` / `failed`; the epoch before the model; a restart by `revision` (the mask, `params`); isolation of a unit | P/02.1 (`worker.uses`, `worker.reads`); P/02.5 N1.4; P/03.2; P/03.3; V/01.2 N1.3; V/02.9 N1.3; V/03.2 |
| V/04.3 | Detector events: writing under the epoch with `of: cam/<cam>`, `may_write` before each write, the class by the field `alarms` of the row (`alarm` / `observation`), suppression of `motion` 30 s, the path of a detection mark to the screen | P/03.6 N1.2; P/05 N1.2, N1.3; P/06.4 N1.3; the event log contract |
| V/04.4 | Heartbeat and numbers: the element of `status[]` (`phase`, `reason`, `events`, `via`), the top-level `events_written` and `events_refused` (`server` is a field of the platform heartbeat), the series `units_running`, `console.running`; acceptance on a stand with the teaching model | P/03.4 N1.1; P/06.5 N3 |

Neighbours: the camera holder (V/01, delivery); the receiver (V/02.9); the orderers — the recorder (V/02.8: scans by `det/units/*`),
`auto` (V/07: a detector by an event); a job by interval — V/05; the page (detection marks — V/11).

## Forms and doors

- **Rows and objects:** `det/units/<name>`, the mask body `det/blobs/sha256-<hex>` (P/06.1 N1.5), the heartbeat `det/heartbeats/<worker>`,
  events — the resource log of its own server `det/<unit>/e<epoch>/`, alarms — `det.alarms/<unit>/e<epoch>/` (P/05 N1.2).
- **Doors:** `det` has no HTTP door of its own — rows through the console door (P/06.1), events — the console's `/events` (P/06.4); the lesson has
  no OpenAPI — the registry row `V/04 no-openapi` (by an inquiry with chapter V/04.1).
- **Data families:** the fields of the detector's event rows — [`data/det-events`](data/) (the teaching `tick` — `pass`; the place — the root of the row
  of the platform's event family, the trees `det` and `det.alarms`; read by the console and the `auto` scenarios), the row — in the VMS catalogue
  [`../common/data/catalog.tsv`](../common/data/catalog.tsv); the fields of other models — the worker registry, not judged by a family.

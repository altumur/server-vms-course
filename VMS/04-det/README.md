# V/04 Live detection

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/04.1–V/04.4 (2026-10-23; review — 2026-10-29); the plan below is the history of the translation (approved — «Архитектор»
2026-10-23, decisions 1–7 accepted, 5 — with an amendment: if the epoch is not taken, there is no element). Sources: the
inventory [`../common/inventory.md`](../../common/inventory.md) § 1, § 2 (М10B/14). The platform: the export `cammeta-specs` `7a875c75` (the VMS pin).
The manifest is [`det.subsystem.yaml`](../det.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8).

## What lesson V/04 is

The subsystem `det`: a detector is the unit «one model on one camera» («line crossing on camera 7», `7-linecross`).
Detection workers on servers with a GPU read the camera's stream, run the model and write events into the log of their own server with `of` of the
camera: an event is not a subsystem — it has no unit of work, its place is decided by the writer. The capacity is in streams that the server
decodes and runs. Everything common — placement, the worker runtime, the event log, classes, suppression, the merging of events for the
page — is platform norms by reference (P/…).

## Chapters

| Chapter | What it norms | Former steps | Platform |
|---|---|---|---|
| V/04.1 | The detector as a unit: the fields (`cam` `fixed`, `kind`, `params` is opaque (the general row limit), `mask` — a blob, `labels` default `[gpu]`, `alarms`, `until`), `about`, who creates it (the operator through the door; `auto` by the order `worker.creates`, the key `{cam}-{kind}`), the deadline `placement.ends` (manual rows are removed from placement, not deleted — `expired_kept`); placement (`capacity` 8, `labels-subset`, `requires: resource`, `near`, without `home`, `most-free-capacity`, `rebalance`), the headroom — the platform; the snapshot | М10B/14 «Зачем», steps 1, 6 (headroom) | P/02.1; P/06.1, the contract row-check (`fixed`, blob P/06.1 Н1.5); P/04 Н1.3 (`near`, `ends`, `unplaced`); P/03.6 Н1.6 (`made`); P/03.4 Н1.1 (`headroom`) |
| V/04.2 | The source and the model: the holder by the heartbeat; its own server — the share `cam.shm` (`worker.uses`), the fallback — the loopback RTSP; another server — the receiver of its own cluster (as V/03.2); reconciliation on each pass; the model — the worker's kind registry, the course's teaching model `tick`; the phases `running` / `pending` / `waiting` / `unsupported` / `failed`; the epoch before the model; a restart by `revision` (the mask, `params`); isolation of a unit | М10B/14 steps 2, 3 (except writing) | P/02.1 (`worker.uses`, `worker.reads`); P/02.5 Н1.4; P/03.2; P/03.3; V/01.2 Н1.3; V/02.9 Н1.3; V/03.2 |
| V/04.3 | Detector events: writing under the epoch with `of: cam/<cam>`, `may_write` before each write, the class by the field `alarms` of the row (`alarm` / `observation`), suppression of `motion` 30 s, the path of a detection mark to the screen | М10B/14 steps 3 (the writing step), 4, 5 | P/03.6 Н1.2; P/05 Н1.2, Н1.3; P/06.4 Н1.3; the event log contract |
| V/04.4 | Heartbeat and numbers: the element of `status[]` (`phase`, `reason`, `events`, `via`), the top-level `events_written` and `events_refused` (`server` is a field of the platform heartbeat), the series `units_running`, `console.running`; acceptance on a stand with the teaching model | М10B/14 step 6, «Результат» | P/03.4 Н1.1; P/06.5 Н3 |

Neighbours: the camera holder (V/01, delivery); the receiver (V/02.9); the orderers — the recorder (V/02.8: scans by `det/units/*`),
`auto` (V/07: a detector by an event); a job by interval — V/05; the page (detection marks — V/11).

## Forms and doors

- **Rows and objects:** `det/units/<name>`, the mask body `det/blobs/sha256-<hex>` (P/06.1 Н1.5), the heartbeat `det/heartbeats/<воркер>`,
  events — the resource log of its own server `det/<unit>/e<эпоха>/`, alarms — `det.alarms/<unit>/e<эпоха>/` (P/05 Н1.2).
- **Doors:** `det` has no HTTP door of its own — rows through the console door (P/06.1), events — the console's `/events` (P/06.4); the lesson has
  no OpenAPI — the registry row `V/04 no-openapi` (by an inquiry with chapter V/04.1).
- **Data families:** the fields of the detector's event rows — [`data/det-events`](../data/) (the teaching `tick` — `pass`; the place — the root of the row
  of the platform's event family, the trees `det` and `det.alarms`; read by the console and the `auto` scenarios), the row — in the VMS catalogue
  [`../common/data/catalog.tsv`](../../common/data/catalog.tsv); the fields of other models — the worker registry, not judged by a family.

## Decisions for the plan (accepted by «Архитектор» 2026-10-23)

1. **The source on a server without a holder is the receiver of its own cluster**, as for the gateway (V/03.2 Н1.1): GPU servers without cameras are
   a regular topology, `near` is only a preference. V/02.9 Н1.3 is supplemented: the receiver admits the leaf `detworker`
   (the address «subscription», the live edge); `det` — `worker.reads: [cam/heartbeats/, rec/heartbeats/]`. On its own server —
   the share `cam.shm` (the decoder needs H.264, not RTP; `worker.uses: [cam.shm]`), the loopback RTSP is the fallback.
2. **`near: {sub: cam, by: cam}`** instead of `{sub: rec, by: cam, of: cam}`: the neighbour is the holder of the camera itself (the place of the share and of the
   source), the rule works also for a camera without recording; the manifest's argument «RTSP from anywhere» is removed (ADR-0075 window 2).
3. **The section `requests:` is removed** (inventory § 4; there is no executor of detector jobs): `auto` creates a detector by an event with a row
   (`worker.creates: [{sub: det, rows: units, key: "{cam}-{kind}"}]`, the deadline `until`, deletion by `ends` — for a row with `made`),
   a scan is the job `detjob` (V/05, V/07). So that the catalogue loads, the same edit changes the manifest of `auto`: `worker.requests: [cam,
   rec, det]` → `[cam]` and `worker.creates` to `det/units`; the norms of `auto` are lesson V/07 (a debt: the action `det.scan` without a path until
   V/05, V/07).
4. **The teaching model `tick`** is a course norm: it fires on every third pass, the event `{pass}`; an implementation MUST
   have it (acceptance without a GPU). GPU models are decided by the implementation (the worker's kind registry).
5. **The vocabulary of phases and reasons is one for VMS:** the subsystem's words are `reason`, `why` is only for the platform (as V/01.2, V/02.4);
   `failed` is only for a unit whose epoch is taken and whose start under it failed; if the epoch is not taken, there is no element (the form of P/03.4 Н1.1:
   without an epoch only the platform phases `sealed`, `unreadable`). Lesson V/03 (V/03.2, V/03.5: `why` and `refused`) is aligned
   by the same edit.
6. **Suppression of `motion`** — `by: [cam]` stays (the field is in every detector row by `about`; an absent field is the same
   group, P/03.6 Н1.2); `linecross`, `lpr` are alarms, they are not suppressed.
7. **The headroom** is the platform (by assignment, P/03.4 Н1.1); the witness's «по работающим» is a difference in «Соответствие».

## Inquiries of the lesson

The registry row `V/04 no-openapi` (`det` has no door of its own) — by an inquiry with chapter V/04.1. The lesson asks for no platform mechanisms beyond
the exported ones: the receiver with the admittance of a leaf — ADR-0091 addendum (14).

## Differences from the witness that the lesson records

`until` → `placement.ends` (manual rows — `expired_kept`, not deletion; `jobs.expire` is removed); the section `requests:` and the executor of detector jobs
are removed — orders by a row; `near` to the camera holder; the source of another server is the receiver (RTSP is the loopback); the headroom is by
assignment; the pass loop, the epoch, the stop are the runtime P/03.2–P/03.4; the code of the witness's model and worker is not carried over.

## Manifest edits during the translation

`det`: `near: {sub: cam, by: cam}`, `worker: {exec, reads: [cam/heartbeats/, rec/heartbeats/], uses: [cam.shm]}`, remove
`requests:`; the comments — the header (instead of «оператор со страницы камеры» — the door and `auto`), `until` (`ends`), `near` (without «RTSP откуда угодно»),
the end (`det/requests`). `auto`: `worker.requests: [cam]`, `worker.creates` to `det/units`. `rec` (V/02.9):
the admittance of `detworker` at the receiver. The product — by a debt line to «Сборка».

## Order of work

Chapter by chapter, a commit per chapter: V/04.1 → V/04.2 → V/04.3 → V/04.4. The lecture `04-det.md` and the instructions `spec/04-det.README.md`
— with the first chapter. Acceptance: 1 (rows, defaults, `cam` is immutable, the mask) — the console; 4 (`waiting` → `running` → an event row
on the third pass of the teaching model; `unsupported`) — a stand with the worker `det` and a file camera; the run — after the first
stage C generation that has passed the platform acceptance. `lessons.tsv` — `переведён` after the last chapter.

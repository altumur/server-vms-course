# V/05 A job over an archive interval

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/05.1–V/05.4 (2026-10-23; review — 2026-10-29); the plan below is the history of the translation (approved by
«Архитектор» 2026-10-23, decisions 1–9 accepted; what is in force is the norms of the chapters). Sources: the inventory
[`../common/inventory.md`](../../common/inventory.md) § 1, § 2 (М10B/20 — the `detjob` half; М10B/21, except the platform
mechanism; М10B/22 — by reference; М10B/23 step 2). The platform: the export `cammeta-specs` `7a875c75` (the VMS pin). The manifest is
[`detjob.subsystem.yaml`](../detjob.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8).

## What lesson V/05 is

The subsystem `detjob`: a job is one model on one interval of one recording («find this number plate on camera 7 yesterday from 10 to 11»).
The first VMS unit whose work **ends**. The job worker reads video from the archive doors of the recorders (V/02.5), runs
a model of the same registry as the detector's (V/04.2), writes events into its own tree with the camera's `of` and puts the result into the
unit state; the platform does not place a finished job, and deletes the order after three days. Its own budget: retro search does not spend the streams
of live detection. The orderers are the operator, the recorder (a scan of catch-up recorded minutes, V/02.8 Н1.5), the scenario (V/07).

## Chapters

| Chapter | What it norms | Former steps | Platform |
|---|---|---|---|
| V/05.1 | The job is a unit that ends: the fields (`cam`, `rec` — a recording of this camera, `kind`, `params`, `mask`, `mask_of`, `alarms`, `from`/`to` — media time, `labels`), who creates it (the operator; the orders of `rec` and `auto` — `made`), a repeated run is a new row; placement (`capacity` 2, `near {sub: rec, by: rec}`, without `home`); the result `unit.state.result` and `retire_when {state: result, …, delete_after: 259200}`; the snapshot | М10B/21 «Зачем», steps 1, 3–6 (by reference), 9; М10B/22 (by reference) | P/02.1; the contract row-check (`fixed`, `ref`, `must_match`); the contract gate-and-pass (`reach`); P/03.6 Н1.6, Н1.7; P/04 Н1.3, Н1.3а |
| V/05.2 | Reading the interval: `/spans` at each live archive door, `silent`/`unread`/`garbled`, «nobody answered» ≠ «there is no recording», the plan by the epoch rule (V/02.5 Н1.3), `/samples` with `stream` at the door that named the span, the lead-in from a key frame, `covered`, `written_through` | М10B/20 steps 1, 4, 5, 8; М10B/21 step 2 (reading) | V/02.5 Н1.2–Н1.4, Н2; P/03.4 Н1.1; the role certificate contract |
| V/05.3 | Work by a budget, progress, events, the result: `STRETCHES_PER_PASS`, `queued`, the cursor `unit.state.cursor` (instead of a file), the remainder by time and by recording, a model of the `det` registry (the teaching `tick` — in media time), events in `detjob/<job>/e<n>` with a media `occurred`, the class by `alarms`, `earlier-run`; the result `result` | М10B/20 steps 6–7; М10B/21 steps 2, 6, 7 | P/03.6 Н1.2, Н1.7; P/05 Н1.2; P/06.4 Н1.2; V/04.2 Н1.2, V/04.3 |
| V/05.4 | Wait, follow, ask; the heartbeat: `waiting` and `WAIT_MAX` (`partial`, `scan.partial`), `following` and `VISIBLE_LAG_SECONDS`, `fetching` — the device has the minutes (the listing of the holder door), the catch-up recording request `rec/requests` filed by the worker; the visibility ceiling is a hole, not a request; the heartbeat and the series; acceptance | М10B/21 steps 2, 8, 9; М10B/23 step 2 | P/03.6 Н1.5; V/02.8 Н1.4; V/01.5; P/03.4 Н1.1 |

Neighbours: the recorder — the archive doors (V/02.5), execution of the catch-up recording request (V/02.8 Н1.4), the scan order (V/02.8 Н1.5); the detector —
the fields and the model registry (V/04); the holder — the listing of the device archive (V/01.5); the scenario — the scan order (V/07); the page —
events (V/11).

## Forms and doors

- **Rows and objects:** `detjob/jobs/<name>`, the state `detjob/state/result/<job>`, `detjob/state/cursor/<job>` (P/03.6 Н1.7),
  the requests `rec/requests/<rid>` (filing), the heartbeat `detjob/heartbeats/<воркер>`, events — the resource log of its own server
  `detjob/<job>/e<эпоха>/`, alarms — `detjob.alarms/…`.
- **Doors:** `detjob` has no HTTP door of its own — rows through the console door (P/06.1), reading — the archive doors of the recorders (V/02.5)
  and the listing of the holder door (V/01.5) with the role certificate `detjobworker`; the lesson has no OpenAPI — the registry row
  `V/05 no-openapi` (an inquiry with chapter V/05.1).
- **Data families:** the fields of the rows of the job's events — [`data/detjob-events`](../data/) (the teaching `tick` — `pass`, `scan.partial` —
  `partial`, `waited`; the place is the root of a row of the platform events family, the trees `detjob` and `detjob.alarms`; read by the console and
  the `auto` scenarios), the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv). The rows, the state
  and the heartbeat are expressed by the manifest: no other process reads the job heartbeat.

## Decisions for the plan (accepted by «Архитектор» 2026-10-23)

1. **Reading a foreign volume:** `/spans` at each live archive door (a heartbeat of `rec/*` within 45 s, the address is `url`), each segment of the plan —
   `/samples?from&to&stream=<epoch>[/backfill]` at the door that named the span (without `stream` the door decides the epoch only by its own
   volume); the role certificate `detjobworker`; without a kit the job cannot read (process routes — 401 `no_role`) — the reading
   acceptance is only on a TLS stand. `/where` is for the page, not for a process.
2. **Models are the `det` registry** (the same worker registry of kinds, `unsupported` for an unknown one); the teaching `tick` in a job is in
   media time: the look step `STEP` = 1 s, an event on every third look (every 3 s of video), the field `pass` is the number of the
   look in the segment; the difference from V/04.2 Н1.2 (passes) is recorded.
3. **Progress is `unit.state.cursor`** (`{revision, done: [[from, to], …], events, waited?, fetch_waited?}`, a monotonically
   growing set of segments along the
   recording, not more often than `STATE_EVERY` = 10 s); a progress file on the resource is not carried over (it is lost on a move). The worker does not apply a cursor with a foreign
   `revision`: an edit of the job means a scan anew.
4. **The result is `unit.state.result`** `{end: done | failed, covered, asked, events, partial?, why?}`; `retire_when: {state: result,
   field: end, in: [done, failed], delete_after: 259200}`; phases are only in the heartbeat. The fields `state`, `ended` are removed (a load
   refusal with `unit.state`, P/02.1).
5. **A repeated run is a new row** (a new name); `earlier-run` — the rows of former epochs of the same job (a move, a substitution).
6. **The event class is the field `alarms`** of the job (the default as at `det`); the orderers copy it from the detector together with `params`,
   `labels` — V/02.8 Н1.5 is supplemented (`alarms`), V/07 likewise.
7. **Suppression of `motion`** is not declared at the job: the suppression window runs by the writer's clock (P/03.6 Н1.2), the scan goes faster than
   real time, the platform keeps no window by media time; there are as many scan rows as the model gave.
8. **The visibility ceiling is a hole, not a request:** the minutes before the recording's «visible from» (V/02.5 Н1.2) are not requested as a catch-up recording; a request is
   only `[max(from, видно с), min(to, now, written_through))` ∩ the device listing, in pieces ≤ a day (otherwise the recorder refuses).
9. **`worker.requests: [rec]` stays:** the catch-up recording request is filed by the worker (P/03.6 Н1.5, `by: detjob/<job>`); the recorder
   keeps the outcome at itself (`fetched`), the job does not wait for it forever — `fetching` is bounded by `WAIT_MAX`, then `done` with `partial`.

## Inquiries of the lesson

The registry row `V/05 no-openapi` (`detjob` has no door of its own) — an inquiry with chapter V/05.1. The lesson asks for no platform mechanisms beyond
the exported ones.

## Differences from the witness that the lesson records

The result is `unit.state.result` of the holder under the epoch guard, not the field `state` of the row that the console cleaner moved;
`forget_finished` — `retire_when.delete_after`; progress is the state cursor, not a resource file; the order is `worker.creates` of
the orderers (the names `rec-…`, `auto-…`); the request is filed by the worker (P/03.6 Н1.5), without a mirror of the phase in the row; extension of a job by
intersection is removed; the reading route is `/spans` and `/samples` for processes (the witness has `/timeline` of the page); the epoch — at taking the
unit; the reserve — the platform.

## Manifest edits during the translation

`detjob`: remove the fields `state`, `ended`; add `mask_of` (it was `mask_from`, removed by the review of V/04–V/05), `alarms`; `unit.state: {result: …, cursor: …}`; `retire_when:
{state: result, field: end, in: [done, failed], delete_after: 259200}`; `snapshot: [name, cam, kind, state.result]`;
`worker: {exec, reads: [rec/heartbeats/, rec/volumes/, rec/recordings/, cam/heartbeats/, det/units/, det/blobs/], requests: [rec]}`;
comments — without the witness code and the console cleaner, `/timeline` → `/spans`. `rec` (V/02.8 Н1.5): the copied fields + `alarms`.
The product — by a debt row to «Сборка».

## Order of work

Chapter by chapter, a commit per chapter: V/05.1 → V/05.2 → V/05.3 → V/05.4. The lecture `05-detjob.md` and the instructions
`spec/05-detjob.README.md` — with the first chapter. Acceptance: 1 (rows, `must_match` of the recording, `fixed`, the orderers' names) — the console;
the scan with the demo model — with the VMS TLS stand (role leaves, block visibility), until then — by reading; the run — after the first stage C generation that has passed the platform acceptance. `lessons.tsv` — `переведён` after the last
chapter.

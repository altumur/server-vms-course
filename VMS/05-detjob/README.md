# V/05 A job over an archive interval

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/05 is

The subsystem `detjob`: a job is one model on one interval of one recording («find this number plate on camera 7 yesterday from 10 to 11»).
The first VMS unit whose work **ends**. The job worker reads video from the archive doors of the recorders (V/02.5), runs
a model of the same registry as the detector's (V/04.2), writes events into its own tree with the camera's `of` and puts the result into the
unit state; the platform does not place a finished job, and deletes the order after three days. Its own budget: retro search does not spend the streams
of live detection. The orderers are the operator, the recorder (a scan of catch-up recorded minutes, V/02.8 N1.5), the scenario (V/07).

## Chapters

| Chapter | What it norms | Platform |
|---|---|---|
| V/05.1 | The job is a unit that ends: the fields (`cam`, `rec` — a recording of this camera, `kind`, `params`, `mask`, `mask_of`, `alarms`, `from`/`to` — media time, `labels`), who creates it (the operator; the orders of `rec` and `auto` — `made`), a repeated run is a new row; placement (`capacity` 2, `near {sub: rec, by: rec}`, without `home`); the result `unit.state.result` and `retire_when {state: result, …, delete_after: 259200}`; the snapshot | P/02.1; the contract row-check (`fixed`, `ref`, `must_match`); the contract gate-and-pass (`reach`); P/03.6 N1.6, N1.7; P/04 N1.3, N1.3a |
| V/05.2 | Reading the interval: `/spans` at each live archive door, `silent`/`unread`/`garbled`, «nobody answered» ≠ «there is no recording», the plan by the epoch rule (V/02.5 N1.3), `/samples` with `stream` at the door that named the span, the lead-in from a key frame, `covered`, `written_through` | V/02.5 N1.2–N1.4, N2; P/03.4 N1.1; the role certificate contract |
| V/05.3 | Work by a budget, progress, events, the result: `STRETCHES_PER_PASS`, `queued`, the cursor `unit.state.cursor` (instead of a file), the remainder by time and by recording, a model of the `det` registry (the teaching `tick` — in media time), events in `detjob/<job>/e<n>` with a media `occurred`, the class by `alarms`, `earlier-run`; the result `result` | P/03.6 N1.2, N1.7; P/05 N1.2; P/06.4 N1.2; V/04.2 N1.2, V/04.3 |
| V/05.4 | Wait, follow, ask; the heartbeat: `waiting` and `WAIT_MAX` (`partial`, `scan.partial`), `following` and `VISIBLE_LAG_SECONDS`, `fetching` — the device has the minutes (the listing of the holder door), the catch-up recording request `rec/requests` filed by the worker; the visibility ceiling is a hole, not a request; the heartbeat and the series; acceptance | P/03.6 N1.5; V/02.8 N1.4; V/01.5; P/03.4 N1.1 |

Neighbours: the recorder — the archive doors (V/02.5), execution of the catch-up recording request (V/02.8 N1.4), the scan order (V/02.8 N1.5); the detector —
the fields and the model registry (V/04); the holder — the listing of the device archive (V/01.5); the scenario — the scan order (V/07); the page —
events (V/11).

## Forms and doors

- **Rows and objects:** `detjob/jobs/<name>`, the state `detjob/state/result/<job>`, `detjob/state/cursor/<job>` (P/03.6 N1.7),
  the requests `rec/requests/<rid>` (filing), the heartbeat `detjob/heartbeats/<worker>`, events — the resource log of its own server
  `detjob/<job>/e<epoch>/`, alarms — `detjob.alarms/…`.
- **Doors:** `detjob` has no HTTP door of its own — rows through the console door (P/06.1), reading — the archive doors of the recorders (V/02.5)
  and the listing of the holder door (V/01.5) with the role certificate `detjobworker`; the lesson has no OpenAPI — the registry row
  `V/05 no-openapi` (an inquiry with chapter V/05.1).
- **Data families:** the fields of the rows of the job's events — [`data/detjob-events`](data/) (the teaching `tick` — `pass`, `scan.partial` —
  `partial`, `waited`; the place is the root of a row of the platform events family, the trees `detjob` and `detjob.alarms`; read by the console and
  the `auto` scenarios), the rows are in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv). The rows, the state
  and the heartbeat are expressed by the manifest: no other process reads the job heartbeat.

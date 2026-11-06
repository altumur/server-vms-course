# V/06 Detection over the device archive

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: translated. The platform export pin is `cammeta-specs` `7a875c75`.

## What lesson V/06 is

The subsystem `detedge`: a **watch** — one model looks through the archive of the **device** of one camera (a card,
an NVR) — always, without an end. The video is not copied: thirty days lie on the NVR without analytics of their own, there is no space on the server, and
detections are needed; only events go out and, optionally, the minutes around the findings (by a catch-up recording request to the recorder).
The family of detectors: `det` — the live stream (V/04), `detjob` — an interval of our archive (V/05), `detedge` — the device archive. Its own
budget: the limit is set not by the GPU but by the playback sessions of the device, which the operator and the recorder share.

## Chapters

| Chapter | What it norms | Platform |
|---|---|---|
| V/06.1 | The watch is a unit without an end: the subsystem name (file, slot, role, trees); the row `detedge/watches/<name>` and the fields (`cam`, `kind`, `params`, `mask`, `alarms`, `start`, `keep`, `pre`/`post`/`join`, `rec`); who creates it — the operator; placement (`capacity` 2, `near {sub: cam, by: cam}`, without `home`, `retire_when`, `ends`); the snapshot | P/02.1; the contract row-check; P/04 N1.3, N1.3a; ADR-0090 addenda (2), (4) item 7 |
| V/06.2 | The listing and reading of the device archive: the holder by the heartbeat (`coverage`, `index_url`, `playback_url`), the window `[frontier, min(frontier + 600, newest − SETTLE))`, the listing `/recordings` (`None` ≠ `[]`), reading `/playback` in pieces, the watch yields (any 503 — `waiting`; the reserve of sessions is held by the door, `PLAYBACK_SPARE`), the pass budget — 4 reads of 60 s of media | V/01.5 N1.1–N1.5, N2, N3; the role certificate contract |
| V/06.3 | The frontier, the model, events: the cursor `unit.state.cursor` — the edge `{through, events, overrun}`; the frontier by the window when the door is free, by the end of what was looked through when it is busy, by what was fully looked through when the model fails; what the device ring erased — a jump with a count; a model of the `det` registry (`tick` in media time — as V/05.3); events `detedge/<watch>/e<n>`, the class by `alarms`, `earlier-run` | P/03.6 N1.2, N1.7; P/06.4 N1.2; V/04.2, V/05.3 |
| V/06.4 | Look at everything, keep what is interesting; the heartbeat: `keep: hits` — segments around the findings (`pre`, `post`, `join`, only over what was looked through) — a catch-up recording request filed by the worker into the recording `rec`; phases, `lag`, series; acceptance of the row | P/03.6 N1.5; V/02.8 N1.4; P/03.4 N1.1 |

Neighbours: the holder — the doors of the device archive (V/01.5); the recorder — execution of the catch-up recording request (V/02.8 N1.4); the detector —
the model registry (V/04.2); the job — the same rules of the event and of the listing (V/05); the page — events and device spans (V/11).

## Forms and doors

- **Rows and objects:** `detedge/watches/<name>`, the cursor `detedge/state/cursor/<watch>` (P/03.6 N1.7), the requests
  `rec/requests/<rid>` (filing), the heartbeat `detedge/heartbeats/<worker>`, events — the resource log of its own server
  `detedge/<watch>/e<epoch>/`, alarms — `detedge.alarms/…`.
- **Doors:** there is no HTTP door of its own — rows through the console door (P/06.1), reading — the holder doors `/recordings`, `/playback`
  (V/01.5, the role leaf `detedgeworker`); the lesson has no OpenAPI — the registry row `V/06 no-openapi` (an inquiry with chapter V/06.1).
- **Data families:** the fields of the rows of the watch's events — [`data/detedge-events`](data/) (`tick` — `pass`; `detedge.overrun`,
  `detedge.rewound` — `from`, `to`; the place is the root of a row of the platform events family, the trees `detedge` and `detedge.alarms`;
  read by the console and the `auto` scenarios), the row is in the VMS catalogue [`../common/data/catalog.tsv`](../common/data/catalog.tsv).

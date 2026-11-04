# V/06 Detection over the device archive

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/06.1–V/06.4 (2026-10-23; review — the analysis of 2026-10-29); the plan below is the history of the translation (decisions 1–10
accepted by «Архитектор» 2026-10-23; the transition — ADR-0090 addendum (11)). Sources: the inventory [`../common/inventory.md`](../../common/inventory.md) § 1, § 2 (М10B/23).
The platform: the export `cammeta-specs` `7a875c75` (the VMS pin). The manifest is [`detedge.subsystem.yaml`](../detedge.subsystem.yaml) (the canon; ADR-0090
addendum (6) item 8).

## What lesson V/06 is

The subsystem `detedge`: a **watch** — one model looks through the archive of the **device** of one camera (a card,
an NVR) — always, without an end. The video is not copied: thirty days lie on the NVR without analytics of their own, there is no space on the server, and
detections are needed; only events go out and, optionally, the minutes around the findings (by a catch-up recording request to the recorder).
The family of detectors: `det` — the live stream (V/04), `detjob` — an interval of our archive (V/05), `detedge` — the device archive. Its own
budget: the limit is set not by the GPU but by the playback sessions of the device, which the operator and the recorder share.

## Chapters

| Chapter | What it norms | Former steps | Platform |
|---|---|---|---|
| V/06.1 | The watch is a unit without an end: the subsystem name (file, slot, role, trees); the row `detedge/watches/<name>` and the fields (`cam`, `kind`, `params`, `mask`, `alarms`, `start`, `keep`, `pre`/`post`/`join`, `rec`); who creates it — the operator; placement (`capacity` 2, `near {sub: cam, by: cam}`, without `home`, `retire_when`, `ends`); the snapshot | М10B/23 «Зачем», steps 1, 5 (the field `start`), 8 (`about`) | P/02.1; the contract row-check; P/04 Н1.3, Н1.3а; ADR-0090 addenda (2), (4) item 7 |
| V/06.2 | The listing and reading of the device archive: the holder by the heartbeat (`coverage`, `index_url`, `playback_url`), the window `[рубеж, min(рубеж + 600, newest − SETTLE))`, the listing `/recordings` (`None` ≠ `[]`), reading `/playback` in pieces, the watch yields (any 503 — `waiting`; the reserve of sessions is held by the door, `PLAYBACK_SPARE`), the pass budget — 4 reads of 60 s of media | М10B/23 steps 2, 4 (reading), 5 | V/01.5 Н1.1–Н1.5, Н2, Н3; the role certificate contract |
| V/06.3 | The frontier, the model, events: the cursor `unit.state.cursor` — the edge `{through, events, overrun}`; the frontier by the window when the door is free, by the end of what was looked through when it is busy, by what was fully looked through when the model fails; what the device ring erased — a jump with a count; a model of the `det` registry (`tick` in media time — as V/05.3); events `detedge/<watch>/e<n>`, the class by `alarms`, `earlier-run` | М10B/23 steps 3, 4 (the frontier), 6, «Что может пойти не так» | P/03.6 Н1.2, Н1.7; P/06.4 Н1.2; V/04.2, V/05.3 |
| V/06.4 | Look at everything, keep what is interesting; the heartbeat: `keep: hits` — segments around the findings (`pre`, `post`, `join`, only over what was looked through) — a catch-up recording request filed by the worker into the recording `rec`; phases, `lag`, series; acceptance of the row | М10B/23 steps 6, 7, 8 | P/03.6 Н1.5; V/02.8 Н1.4; P/03.4 Н1.1 |

Neighbours: the holder — the doors of the device archive (V/01.5); the recorder — execution of the catch-up recording request (V/02.8 Н1.4); the detector —
the model registry (V/04.2); the job — the same rules of the event and of the listing (V/05); the page — events and device spans (V/11).

## Forms and doors

- **Rows and objects:** `detedge/watches/<name>`, the cursor `detedge/state/cursor/<watch>` (P/03.6 Н1.7), the requests
  `rec/requests/<rid>` (filing), the heartbeat `detedge/heartbeats/<воркер>`, events — the resource log of its own server
  `detedge/<watch>/e<эпоха>/`, alarms — `detedge.alarms/…`.
- **Doors:** there is no HTTP door of its own — rows through the console door (P/06.1), reading — the holder doors `/recordings`, `/playback`
  (V/01.5, the role leaf `detedgeworker`); the lesson has no OpenAPI — the registry row `V/06 no-openapi` (an inquiry with chapter V/06.1).
- **Data families:** the fields of the rows of the watch's events — [`data/detedge-events`](../data/) (`tick` — `pass`; `detedge.overrun`,
  `detedge.rewound` — `from`, `to`; the place is the root of a row of the platform events family, the trees `detedge` and `detedge.alarms`;
  read by the console and the `auto` scenarios), the row is in the VMS catalogue [`../common/data/catalog.tsv`](../../common/data/catalog.tsv).

## Decisions for the plan (accepted by «Архитектор» 2026-10-23)

1. **The subsystem name `detedge` in the first commit of V/06.1** (ADR-0090 addendum (2), addendum (4) item 7 — by the word of «Архитектор» at the
   translation of lesson 06; addendum (7) item 4 — the file and `name` in one commit): `detedge.subsystem.yaml`, `name: detedge`, the slot
   `{prefix: e, name_env: DETEDGE_NAME}` (`d` is taken), `exec: /usr/lib/detedge/worker`, `rows: watches`,
   the series `detedge_watches_running`, the role `detedgeworker` (V/01.5 Н2), `lessons.tsv`; the boundary vocabulary —
   to «Архитектор»; the product — by a debt row to «Сборка». `Source/vms/*` is not touched.
2. **With `detjob` — by references, not by a copy:** the registry, `tick` in media time, the mask — V/04.2, V/05.3 Н1.3; the rules of the event
   row — V/05.3 Н1.4 (except the tree, the class); the device listing with `None` ≠ `[]` and the form of the request — V/05.4 Н1.4. What is V/06's
   own: an edge cursor instead of the set `done`, no result and no retirement, the source is the holder door, the window and `SETTLE`, the frontier rule.
3. **The watch yields:** any 503 of the holder door — `waiting` until the next pass, without a repeat within the pass; not more than one
   playback session per device at the worker; the last session is for the operator or the recorder: the reserve is held by the holder
   door (`PLAYBACK_SPARE` = 1 for `detedgeworker`, V/01.5 Н1.5, — the analysis of the V/06 review, question 3), the check of `/devices`
   (`playbacks ≥ max_playbacks − 1` — do not read) is preliminary; `max_playbacks` = 1 — the watch does not read the device; the number of
   sessions is named by the device (V/01.5 Н1.4), not by the lesson; per pass — not more than `STRETCHES_PER_PASS` = 4 reads of `READ_SECONDS`
   = 60 s of media (`PLAYBACK_PIECE` is the door's portion within an answer), reading and the model are not on the thread of the runtime loop: the budget
   bounds the time until the cursor is written and the share of the device.
4. **Catch-up recording is only `keep: hits`:** the watch does not order holes and creates no jobs; the segments around the findings — by a request into
   the recording named by the field `rec` (`ref: rec/recordings`, `must_match: {cam: cam}`, required with `keep: hits`; a camera
   may have several recordings — the witness's «first by camera» is ambiguous); pieces shorter than a second and before the recording's «visible from» are not
   filed (otherwise the refusal of V/02.8 Н1.4); `by: detedge/<watch>`.
5. **`per_person` (inventory No. 17) does not apply to filing by the worker — by the word of the norm:** the count `asked` is of people (P/06.4 Н1.5, the console
   door), filing by the worker goes past the door (P/03.6 Н1.5); no inquiry is needed.
6. **`events.older_epochs: earlier-run`**: after a move the rows of the former epoch are the only record of those minutes (a repeat is
   the work after the last cursor, without a limit in seconds of video), not a fenced-off writer; there is no suppression (the media goes faster than real time).
7. **`alarms`, default `[]`**: the findings over an old archive are observations; the operator sets an alarm explicitly by kind.
8. **What the device ring erased:** the frontier < `coverage.from` — a jump to `coverage.from`, the count `overrun` in the heartbeat
   element and one event row `detedge.overrun` (`from`, `to`) — at the witness the frontier silently crawled through what was erased.
9. **The cursor is written at the first taking** (`start: now` → `max(oldest, newest − SETTLE)`, `earliest` → `coverage.from`; the same
   formula — at a reset of a frontier that is ahead of the archive, `detedge.rewound`): at the witness a watch with
   the default `now` never began to look — the frontier was not written, each pass began from `newest`.
10. **The phase `caught_up`** — the frontier is at the edge (`newest − SETTLE`), there is nothing to read — a healthy state; `running` — only while
    reading; the series `watches_running` counts the reading ones (for a cluster that has caught up — 0, the lag is `lag`).

## Inquiries of the lesson

The registry row `V/06 no-openapi` (`detedge` has no door of its own) — an inquiry with chapter V/06.1. The lesson asks for no platform mechanisms beyond
the exported ones.

## Differences from the witness that the lesson records

The subsystem name — per ADR-0090 addenda (2), (11); the frontier is the unit state cursor, not a resource file (it survives a move,
ADR-0091 item 3); keeping the findings is filing by the worker, not the heartbeat field `hits` and a job executor; the recording — by the field `rec`;
`older_epochs: earlier-run`; `alarms`; what the ring erased — a count and an event; the cursor at the first taking (the defect of `start: now`);
the pass budget in pieces; reading with not more than one session and with a reserve session for the operator; the epoch — at taking the unit.

## Manifest edits during the translation

The subsystem name (decision 1); the fields `alarms`, `rec`; `start`, `keep` — as lists (`enum`); `unit.state.cursor`; `events.older_epochs:
earlier-run`; `worker: {exec, reads: [cam/heartbeats/, rec/recordings/], requests: [rec]}` (`det/blobs/` is removed: the watch's mask is
its own field, the analysis of the V/06 review, «Н-1»); `pre`, `post`, `join` — `schema: {minimum: 0, maximum: 600}`; the series `filings_total`;
comments — without «пишет консоль», `frontier.json`, «две сессии» as a constant. V/01.5 Н2 — remove the reservation. The product — by a debt
row to «Сборка».

## Order of work

Chapter by chapter, a commit per chapter: V/06.1 (the transition and the unit) → V/06.2 → V/06.3 → V/06.4. The lecture `06-detedge.md` and
the instructions `spec/06-detedge.README.md` — with the first chapter. Acceptance: 1 (rows, defaults, `cam` unchanged) — the console; reading the device archive — by reading (the stand has no double of a device with an archive and no VMS TLS stand,
V/01.5 Н5, V/02.8 Н5). `lessons.tsv` — `переведён` after the last chapter.

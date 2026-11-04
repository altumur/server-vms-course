# V/08 Export

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **norms of chapters V/08.6–V/08.9** (2026-11-03, «Спецификация VMS»; the plan is accepted by «Архитектор»; until the merge of ADR-0118 — lesson V/13, chapters V/13.1–V/13.4); acceptance — [`acceptance/6`](../acceptance/6/README.md); the share of V/11 (`/exports`, `reference.export`, the stream, the functions of V/11.8, the fates of V/11.2) — when the contract of the fork with
`/exports` is fixed (V/11.14 Н1.3). The basis is ADR-0117 with addenda (1)–(6). The platform is the export `cammeta-specs` `7a875c75`. The manifest is
[`exp.subsystem.yaml`](../exp.subsystem.yaml) (the canon; ADR-0090 addendum (6) item 8).

## What lesson V/08 is

The subsystem `exp`: the operator exports segments of the archive or one frame — live or from the archive — into files with an expiry. The unit is a part:
one camera, one recording, its segments and files. A part stands next to the recording, cuts the video which it reads through the recorder's doors,
holds the files on its own volume and serves them to the author through its own door by a link with a token. The bytes go neither through the console nor through
`backend` (ADR-0015).

## Chapters

| Chapter | What it norms | Status | Platform and lessons |
|---|---|---|---|
| V/08.6 | The part — the unit: the row `exp/parts/<name>` (the order — in the leading part, the common fields in each), placement `near rec` and `gpu`, the part's volume `files`, the state `cursor`, `result`, the limits `EXPORT_*`, rights (`edit` — create, `admin` — without password and mask, only the author gets the bytes), the camera log `export.*` | norms | P/03.6, P/04; V/02; ADR-0117 |
| V/08.7 | Source and assembly: the archive through the doors of `rec` as V/05.2, audio, holes — `partial`, the live frame at the gateway `live` (`/frame`), the archive frame, remuxing and transcoding, chapters, splitting, password, «в один файл» by the leading part | norms | V/02.5, V/03.3, V/05.2 |
| V/08.8 | Cancellation and deletion by requests to the holder, the expiry from the end of the part (`result.expires`), deletion of the row by the holder, a lost holder — `expired`, retry | norms | P/06.4 Н1.5 |
| V/08.9 | The file door: the link — the token `where`, the route `files` only for the author, `attachment`, `Range` 206, the log `issued`, `read`; the route `parts` for the leading part | norms | P/03.4 Н1.7, P/06.5 |

Neighbours: the recorder — the doors `/spans`, `/samples` with the role `expworker` (V/02.5); the gateway — the frame route (V/03.3 Н1.5); `backend` —
the order as one batch of parts, progress and result by reading the parts, the link (V/11).

## Forms and doors

- **Rows:** `exp/parts/<name>`, the state `exp/state/cursor/<name>`, `exp/state/result/<name>`, the requests `exp/requests/<rid>`,
  the part's event log with `of: cam/<cam>`; it sets up `live/streams/<cam>`.
- **Doors:** the worker's process door — [`spec/08-exp.api.openapi.yaml`](../spec/08-exp.api.openapi.yaml): `files` by token, `parts`
  by the role `expworker`.
- **Data families:** the lesson has no rows of its own in the VMS catalogue; the reader of the heartbeats of `rec` and `live` is `expworker` (the outcomes are in the data
  of lessons 02, 03).

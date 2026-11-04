# V/06 Detection over the device archive — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/06-detedge.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `detedge` does and how to check the result. The canon is the norms of the chapters `06.K-detedge.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75` (the VMS pin).

## Inputs and their priority

- The canon: the norms of the chapters `06.K-detedge.norms.md` (Н1–Н5 of each chapter; the addresses `V/06.K Н…`).
- The canon of the manifest: [`detedge.subsystem.yaml`](../detedge.subsystem.yaml): the bytes as they are.
- Acceptance: [chapter 1](../acceptance/1/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../common/acceptance/README.md); acceptance introduces no new requirements.
- Vectors: [`mask`](../../04-det/vectors/mask/README.md) (the package command).
- The lecture (`ru/06-detedge.md`, for people, not in the export) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/06.1 | the manifest `VMS/06-detedge/detedge.subsystem.yaml` loads with the strict loader without edits; the unit door of the console executes the watch's declarations | [acceptance 1](../acceptance/1/README.md) |
| V/06.2 | the holder by the heartbeat, the window (`SETTLE` 30, 600 s per pass), the listing `/recordings` (`None` ≠ `[]`, normalisation of the spans), reading `/playback` by 60 s of media outside the runtime loop, one session per device, 4 reads per pass, 503 (including the door's reserve `PLAYBACK_SPARE`) — waiting | by reading |
| V/06.3 | the frontier cursor (the first taking `now`/`earliest`, movement by the window, by the continuous beginning, by what was fully looked through; «события → подачи → курсор»), what the ring erased — a jump and `detedge.overrun`, a frontier ahead of the archive — `detedge.rewound`; a model of the `det` registry (`tick` on an absolute grid, the mask — the vectors `mask`), events by the rules of V/05.3 | by reading, the vectors `mask` |
| V/06.4 | `keep: hits` — segments around the findings (joining, ∩ what was counted), a catch-up recording request by filing into the recording `rec` before the cursor (whole seconds, before «visible from», pieces ≤ a day); phases; the heartbeat (`events_written`, `through`, `lag`, `overrun`) | by reading |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam`, `rec`, `det`, then `detedge` — the VMS
acceptance runs only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/06.3 Н1.2 | moving the cursor before the outcome of the filings | events → filings → cursor; the cursor — when each filing has an outcome |
| V/06.3 Н1.4 | setting the `tick` beat from the start of the pass | the absolute grid `t_n = n × 1 с` |
| V/06.3 Н1.3 | silently continuing when the cursor is ahead of the archive | a reset as at the first taking and the event `detedge.rewound` |
| V/01.5 Н1.5 | taking the last session of the device at the holder door | the reserve `PLAYBACK_SPARE` is held by the door: for the last one — 503, waiting |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapter 1 passes on a platform that has passed its own acceptance; the vectors of the lesson pass with the package command;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

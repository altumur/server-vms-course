# V/04 Live detection — instructions for an implementation

This English text is the source; the Russian [`04-det.README.md`](../04-det.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `det` does and how to check the result. The canon is the norms of the chapters `04.K-det.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75` (the VMS pin).

## Inputs and their priority

- The canon: the norms of the chapters `04.K-det.norms.md` (Н1–Н5 of each chapter; the addresses `V/04.K Н…`).
- The canon of the manifest: [`det.subsystem.yaml`](../../det.subsystem.yaml): the bytes as they are.
- Acceptance: [chapter 1](../../acceptance/1/README.md), [chapter 4](../../acceptance/4/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- Vectors: [`mask`](../../vectors/mask/README.md) (the package command).
- [The lecture](../../04-det.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/04.1 | the manifest `VMS/04-det/det.subsystem.yaml` loads with the strict loader without edits (together with `auto` — the orderer of `det` rows); the console's units door executes the detector's declarations | [acceptance 1](../../acceptance/1/README.md) |
| V/04.2 | the source by heartbeats (the share `cam.shm`, the loopback RTSP, the receiver of its own cluster by the leaf `detworker`), reconciliation; the model registry and the teaching `tick`; phases with `reason`; a restart by revision | by reading; acceptance 4 (chapter 4) |
| V/04.3 | the model's events are log rows written by the platform's writer (`of` of the camera, `may_write` before each one), the class by `alarms`, suppression of `motion` | by reading; acceptance 4 (chapter 4) |
| V/04.4 | the heartbeat (`events_written`, `events_refused`, the element `phase`/`reason`/`events`/`via`), the series `units_running`, the stop; the command that starts the worker for «Стенд» — in the implementation description | [acceptance 4](../../acceptance/4/README.md) |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam` (V/01), `rec` (V/02), then `det` —
the VMS acceptance runs only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/04.1 Н1.1 | taking the detector's mask when the order has its own non-empty `mask` | its own `mask` first, otherwise the mask of the row `mask_of` at the moment of the start; there is no detector — a start refusal |
| V/04.4 Н1.1 | naming its own heartbeat counter `events` | the top-level counter is `events_written`: the name `events` is taken by the platform |
| V/04.4 Н1.3 | losing the swallowed repeats at stop | each suppression window with repeats is closed by a summary row before the last heartbeat |
| V/04.1 Н1.1 | treating `params` as a small field with its own limit | `params` is a string, the limit is the general row limit |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapters 1, 4 passes on a platform that has passed its own acceptance; the lesson's vectors pass with the package command;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

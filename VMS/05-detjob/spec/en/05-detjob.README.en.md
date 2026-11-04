# V/05 A job over an archive interval — instructions for an implementation

This English text is the source; the Russian [`05-detjob.README.md`](../05-detjob.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `detjob` does and how to check the result. The canon is the norms of the chapters `05.K-detjob.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `05.K-detjob.norms.md` (Н1–Н5 of each chapter; the addresses `V/05.K Н…`).
- The canon of the manifest: [`detjob.subsystem.yaml`](../../detjob.subsystem.yaml): the bytes as they are.
- Acceptance: [chapter 1](../../acceptance/1/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- Vectors: [`mask`](../../../04-det/vectors/mask/README.md) (the package command).
- [The lecture](../../05-detjob.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/05.1 | the manifest `VMS/05-detjob/detjob.subsystem.yaml` loads with the strict loader without edits (together with `rec`, an orderer); the unit door of the console executes the job's declarations; the result and the retirement — the platform | [acceptance 1](../../acceptance/1/README.md) |
| V/05.2 | `/spans` at each live door (the leaf `detjobworker`), `silent`/`garbled`/`unread`, the plan by the epoch rule, `/samples` with `stream` at the span's door, `covered`, `written_through` | by reading (the VMS TLS stand — later) |
| V/05.3 | the pass budget (4 pieces), the cursor `unit.state.cursor`, a model of the `det` registry (`tick` in media time), `detjob` events with a media `occurred` and the class by `alarms`, the result `unit.state.result` | by reading (the VMS TLS stand — later) |
| V/05.4 | phases with `reason`; waiting for the missed (`WAIT_MAX`, `partial`, `scan.partial`), `following` (`VISIBLE_LAG_SECONDS` in `/etc/detjob/detjob.env`), `fetching` (the device listing, the catch-up recording request by filing); the heartbeat | by reading (the VMS TLS stand — later) |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam`, `rec`, `det`, then `detjob` — the VMS
acceptance runs only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/05.3 Н1.5 | holding back the result because of a permanent hole | permanent holes do not hold back the result (`covered < asked`) |
| V/05.3 Н1.2 | counting the wait deadlines from the clock of the pass | `waited`, `fetch_waited` — accumulated seconds in the cursor |
| V/05.3 Н1.3 | treating a mask error from a deleted detector with a backoff | the job has the result `failed`: there is no detector |
| V/05.1 Н1.2 | creating a second job for an equal window of a scenario | one job per window `(cam, rec, kind, from, to)`; a repeat — `unchanged` |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapter 1 passes on a platform that has passed its own acceptance; the vectors of the lesson pass with the package command;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

# V/07 Scenarios — instructions for an implementation

This English text is the source; the Russian [`07-auto.README.md`](../07-auto.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `auto` does and how to check the result. The canon is the norms of the chapters `07.K-auto.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `07.K-auto.norms.md` (Н1–Н5 of each chapter; the addresses `V/07.K Н…`).
- The canon of the manifest: [`auto.subsystem.yaml`](../../auto.subsystem.yaml): the bytes as they are.
- Acceptance: [chapter 1](../../acceptance/1/README.md), [chapter 6](../../acceptance/6/README.md); the vectors of the moment function — [`moment`](../../vectors/moment/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- [The lecture](../../07-auto.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/07.1 | the manifest `VMS/07-auto/auto.subsystem.yaml` loads with the strict loader without edits (the VMS catalogue as a whole); the console unit door executes the number key, the schemas `when`, `conditions`, `then` and the bounds of the fields; the form of a step inside a branch is judged by the evaluator | [acceptance 1](../../acceptance/1/README.md) |
| V/07.2 | the wants, reading the merged log (a participant of the contract `events-merge`, the epochs by `worker.reads`), the firing by the closing event, the cursor `unit.state.cursor` (the full window, `COLD_START`, a new `revision` by the cursor row), the long poll; a run by schedule and by hand; `LONG_POLL` in `/etc/auto/auto.env` | by reading |
| V/07.3 | the refusal of two fields, the reconciliation of the scenario with `can`, with the rows of devices, detectors and recordings (`unfit`, `unchecked`), the refusal texts | by reading |
| V/07.4 | the requests to `cam` (the deadline from the event, `late`), the orders to `rec`, `det` (the base, `mask_of`, a second one is not set up), `detjob` (the window, the detector's fields); the actions `arm`, `disarm`, `disable`, `alarm`; the checks before the actions, the expansion of the targets, the run row `unit.state.runs` and the waiting steps, `repeat`; the ceilings; the events `fired`, `step`, `suppressed`; the requests `run`, `retry`, the door `test`; the heartbeat and the series | by reading, `@manual` of acceptance 1 |
| V/07.5 | the document `auto.scenarios` (the form), the executor of the trigger's cluster, the contribution to the book `asks`, the request to the receiver with the token `ask` and the outcomes, carrying through the relay | by reading |
| V/07.6 | the tables of `auto`, the moment function `in_effect`, `sun`, the mode `object_mode` and the heartbeat field, the windows, `TIMEZONE` of the environment, the wall minutes at clock changes | [acceptance 6](../../acceptance/6/README.md), the vectors [`moment`](../../vectors/moment/README.md) |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam`, `rec`, `det`, `detjob`, then `auto` —
the VMS acceptance runs only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/07.2 Н1.3 | comparing an event field loosely (`"1"` and `1`) | the comparison is strict, the field type is set by the writing lesson |
| V/07.2 Н1.3 | judging a pair by the order in which the rows appeared, or by memory | the latest by `(t, id)` closes: one firing at any holder |
| V/07.4 Н1.3 | widening or changing a scan job by a repeated order | one job per window, the fields are those of the first order, a repeat is `unchanged` |
| V/07.6 Н1.3 | treating the tail of an interval as part of the next day only inside `valid` | the deadline judges by the day of the start: the tail of the last day comes, the tail of the day before the deadline does not |
| V/07.6 Н1.4 | computing `sun` in the local zone or taking the language's sign of the remainder | the offset is `utc_offset_hours` of the row, `fmod` with the sign of the dividend, rounding `⌊x + 0.5⌋` |
| V/07.6 Н1.1 | treating an unreadable table row as absent | not read is not absent: `unknown`, `cond.unread` |
| V/07.5 Н1.4 | gluing requests between cameras without `firing` | the merge is by `(by, цель, действие, firing)`; the row at the holder is `rec.ask-<firing>-<i>` |
| V/07.4 Н1.1 | giving a request a random name | the request name is `auto.<32 hex>-<i>` |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapters 1, 6 and the vectors `moment` pass on a platform that has passed its own acceptance;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

# V/10 Assistant

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **translated** — chapters V/10.1, V/10.2 (2026-10-29; started 2026-10-28, «Спецификация VMS»). The lesson plan is accepted by «Архитектор» — ADR-0093 addendum (1).
The norms — the export `35582ba`. The loop, the tools, the check, the application and the rules as text moved to V/11, chapters 9–13
(ADR-0093 addendum (8) items 2, 3; 2026-11-02). The basis is ADR-0093; the assistant pilot (outside the export) (reference, not canon).
The platform is the export `cammeta-specs` `7a875c75` (the VMS pin). The manifest is [`assist.subsystem.yaml`](assist.subsystem.yaml)
(the canon; ADR-0090 addendum (6) item 8).

## What lesson V/10 is

The subsystem `assist` is a service of a local model without rights. The unit is an instance of the model on a server with memory for it,
the holder is a platform worker with the model server as a child process. The door answers one model step; the flow, the tools,
the plan check and the display are run by `backend` ([V/11](../11-backend/README.md), chapters 7, 9–13). The model process is not part of `backend`:
a substitution in the text of a request would end up next to the tickets, and their placement differs. There is no external model in a real installation:
the subsystem is required for the assistant (ADR-0093 addendum (9) item 2, it lifts addendum (8) item 3 about an external model); the demo page of the fork with an external model is demo data, it does not concern the lesson.

## Chapters

| Chapter | What it norms | Status | Platform and lessons |
|---|---|---|---|
| V/10.1 | The model — the unit `assist/models/<name>` and the worker: fields and rights (talking to the model — `view` on the row), placement by label, one model per server, the model process — a child process of the holder on a unix socket 0700 (the command, the protocol `health`/`step`, life, shut down before giving up the slot), the heartbeat and series | norms | P/02.1; P/02.4 Н1.1; P/03.4 Н1.2, Н1.7; P/04 Н1.3; V/09 |
| V/10.2 | The model door: `door.routes: [chat]`, the token by `where`, an asynchronous step (submit, the state and the answer by a long poll ≤ 20 s, cancellation), the step owner — `claims.user`, the queue and isolation, limits, a log without texts, the model stub of acceptance | norms | the contract `door-token`; P/03.4 Н1.7; P/06.5 Н3; V/03.3 (sample) |

## Decisions (ADR-0093 addendum (1))

1. **The model door** is the holder's own door by `door` of the answer of `GET /assist/where/<name>` with the door token (`view` on the model row), not
   `door.pass`; the protocol is asynchronous (V/10.2). `backend` calls it by a console route by ticket (addendum (7)).
2. **The step owner** is `claims.user`; to a foreign one — 404; the history and the cache are not shared; a change of holder — `gone` (V/10.2).
3. **The model on a server** is a child process of the holder (unix socket 0700, shuts down on `fenced` and on giving up the holding, a loading
   phase); one model per server — by the label and the capacity; the memory numbers — from the package measurements, in V/09 (V/10.1).

The other items of addenda (1)–(5) are in [V/11](../11-backend/README.md#ассистент-решения): they are about the loop and the plan.

**ADR-0093 addendum (2)** (Kimi's review): the model door — the door token by `view` on the model row; `rights.routes` is not needed (clarified
by the norms review, Claude С-3); the door is open to any client with `view`, the step — to its owner (V/10.1 Н1.1, V/10.2 Н1.1).

## Forms and doors

- **Rows and objects:** `assist/models/<name>`, the heartbeat `assist/heartbeats/<воркер>`, the snapshot `assist/snapshot/*`; the door log
  `audit/assistworker/e1` (`assist.step`).
- **Doors:** the model rows — the units door of the console (P/06.1); the model door — the holder's route `chat` ([the lesson's OpenAPI](spec/10-assist.api.openapi.yaml));
  the address and the token — `/assist/where/<name>` of the console (P/06.5); `backend` — the route `/assist/chat/<имя>/…` by ticket (V/11.7 Н1.2).

## Acceptance

- [Acceptance 1](acceptance/1/README.md) — the units door of the console: the model row, form refusals (V/10.1).
- [Acceptance 2](acceptance/2/README.md) — a stand with the model holder and the stub `model-stub` (V/10.1 Н1.3, V/10.2).
- The model evaluation suite is not acceptance: the lesson's information from the handover package.

## Edits of other lessons

- **V/09:** the role `assistworker` (`CAPACITY=1`, anything else — a start refusal, V/10.1 Н1.2), the label of the model server — a premise, the memory by the package measurements, the delivery of the weights (≈ 12 GB),
  the installation order.
- **V/11:** the door client; chapters 9–13, `harness/`, `data/rule-catalog.json`, the vectors `plan-check`, `apply`, `turn`, `rules-words`.
- `common/lessons.tsv` — row 10; `id-map.tsv` — the norms with the source `ADR-0093`.

## Work order

1. V/10.1, V/10.2 — the norms, the lecture, the instructions, the manifest, OpenAPI, acceptance 1 and 2.
2. Chapter by chapter, a commit per chapter, `check_spec` over all VMS lessons.

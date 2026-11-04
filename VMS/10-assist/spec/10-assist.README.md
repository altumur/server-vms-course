# V/10 Assistant — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/10-assist.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `assist` does and how to check the result. The canon is the norms of the chapters `10.K-assist.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`
(the VMS pin; the norms of the chapters are reconciled at `35582ba`).

## Inputs and their priority

- The canon: the norms of the chapters `10.K-assist.norms.md` (Н1–Н5 of each chapter; the addresses `V/10.K Н…`).
- The canon of the manifest: [`assist.subsystem.yaml`](../assist.subsystem.yaml): the bytes as they are.
- [The contract](10-assist.api.openapi.yaml) expresses the forms of the HTTP inputs of the canon.
- Acceptance: [chapter 1](../acceptance/1/README.md), [chapter 2](../acceptance/2/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../common/acceptance/README.md); acceptance introduces no new requirements.
- Vectors: [`vectors/`](../vectors/) (the model stub).
- The lecture (`ru/10-assist.md`, for people, not in the export) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/10.1 | the manifest `VMS/10-assist/assist.subsystem.yaml` loads with the strict loader without edits (the VMS catalogue as a whole); the holder of the model row brings up the model process by the command `MODEL_COMMAND` on a unix socket 0700, runs the phases `loading`, `running`, `failed`, `stopped`, shuts the process down before giving up the slot; the heartbeat and series | [acceptance 1](../acceptance/1/README.md), [acceptance 2](../acceptance/2/README.md) and by reading |
| V/10.2 | the holder's door `chat`: the door token, a step `202` → the state by a long poll → cancellation, the step owner — `user` of the token, the queue, the step timeouts, the log `assist.step` without texts | [acceptance 2](../acceptance/2/README.md) and by reading |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8). The subsystem package carries
the command `/usr/lib/assist/model-server` and the weights of the pair (`model`, `quant`) of the manifest (V/09).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `assist` — the VMS acceptance runs only on such a
platform (ADR-0090 addenda (8), (9)). `assist` depends on no VMS subsystem; its client is `backend` (V/11.7); the loop, the tools and the check are there.

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/10.2 Н1.4 | giving a step to a foreign `user` | the step owner is `user` of the door token |
| V/10.2 Н1.5 | printing the texts of steps to the log | the log `assist.step` — without texts |
| V/10.1 Н1.3 | leaving the model process after giving up the slot | the model process shuts down before the slot is given up |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapters 1, 2 passes on a platform that has passed its own acceptance; the lesson's vectors pass by the package command;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

## Implementation decides

The implementation MUST name in its description: the model server of the package command (how it listens on the socket, how it does not print the texts
of steps, how a cancellation reaches the model), the path of the weights of the pair in the package, how the model server reports an overflow of the window, how the model
process shuts down with the death of the holder outside a unit, how a cache with data goes only to the same `user` and `turn` (V/10.2 Н1.4), and
the command to start the worker for «Стенд» (V/10.1, V/10.2 «Решает реализация»).

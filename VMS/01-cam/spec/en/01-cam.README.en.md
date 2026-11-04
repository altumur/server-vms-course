# V/01 Camera — instructions for an implementation

This English text is the source; the Russian [`01-cam.README.md`](../01-cam.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `cam` does and how to check the result. The canon is the norms of the chapters `01.K-cam.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`: an implementation of `cam` is a subsystem on the
platform; it neither edits nor repeats the platform's code.

## Inputs and their priority

- The canon: the norms of the chapters `01.K-cam.norms.md` (Н1–Н5 of each chapter; the addresses `V/01.K Н…`).
- The canon of the manifest: [`cam.subsystem.yaml`](../../cam.subsystem.yaml): the bytes as they are.
- [The contract](../01-cam.api.openapi.yaml) expresses the forms of the HTTP inputs of the canon.
- Acceptance: [chapter 1](../../acceptance/1/README.md), [chapter 2](../../acceptance/2/README.md), [chapter 3](../../acceptance/3/README.md), [chapter 4](../../acceptance/4/README.md), [chapter 5](../../acceptance/5/README.md), [chapter 8](../../acceptance/8/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- [The lecture](../../01-cam.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/01.1 | the manifest `VMS/01-cam/cam.subsystem.yaml` loads with the strict loader without edits; the unit door of the platform console executes the camera's declarations | [acceptance 1](../../acceptance/1/README.md) |
| V/01.2 | the holder `camworker`: the desired state, one connection, RTSP delivery and the share `cam.shm`, the heartbeat words, events; the command that starts the holder for the acceptance «Стенд» is named in the implementation description | [acceptance 2](../../acceptance/2/README.md) |
| V/01.3 | the source `driverpack://file/<имя>`: the refusals of Н1.1, a file as a camera Н1.2; an hour-long run for the monotonicity of the timestamps — in the implementation description | [acceptance 3](../../acceptance/3/README.md) |
| V/01.4 | execution of the requests `output`, `preset` by the device driver, questions to the device outside the loop, the row `cam/devices/<хост>`, the device's children, `can`, arming and switching off for a time (`cam/rule_state/<id>`) | [acceptance 4](../../acceptance/4/README.md) |
| V/01.5 | the holder door (`/devices`, `/recordings`, `/playback`) per [OpenAPI](../01-cam.api.openapi.yaml), the limits of Н1.5, the class `mixed`; the device archive driver | [acceptance 5](../../acceptance/5/README.md) |
| V/01.6 | the contribution to the book `cam/sources/<слот>`, the camera stream pusher (polling the receiver, continuation, applications), `taken_by`, the order of recording onto the card; the stream transport — in the implementation description | by reading (VMS has no domain stand); the order — V/02.4 `06-edge` |
| V/01.7 | the worker on the domain `camdomain`: checking the signature with the vendor key, the count by the domain view, the book `licence`; the holder does not hold a camera outside `licensed` | by reading (VMS has no domain stand) |
| V/01.8 | the base worker: search by the row `cam/searches`, the findings `cam/found`, the answers to the question about the model; the search driver | [acceptance 8](../../acceptance/8/README.md); a live driver — `@manual` |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8), and neither copies nor
supplements it.

## Order

First the platform (a stage C generation that has passed the platform acceptance); then `cam` over it — the VMS acceptance runs only on
such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/01.2 Н1.3 | building the share address `shm:///…/<id>-<эпоха>.shm` at the reader, or writing into a foreign epoch | the share address is taken from the heartbeat as is; the share file is deleted only by its writer, the files of a lower epoch of this camera — by the holder at the start of the unit |
| V/01.1 Н1.1, V/01.2 Н1.2 | stripping the default port in the door's canonical address, or treating `ch/02` and `ch/2` as one channel | the canonical address is per the row check contract; «the same channel» (`busy`) is only equality after stripping the scheme's default port |
| V/01.2 Н3 | repeating the opening of an address that the subsystem does not read | syntax — `refused`, without repeats; no file, or the device refused — a start failure with a backoff |
| V/01.7 Н1.3 | serving an `unlicensed` camera even partly | commands `refused`, the door — 404, no element of the book `sources` |
| V/01.4 Н1.1 | distinguishing `"1"` from `1` in a request row | the field arrived as text, an integer is a record in digits; inputs, outputs and presets — from 1 |
| V/01.5 Н2 | breaking off the handshake on a foreign role | the class `mixed` as is, the words of the class `role`: 401 `no_role`, 403 `wrong_role`, `bad_chain` |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapters 1, 2, 3, 4, 5 passes on a platform that has passed its own acceptance;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

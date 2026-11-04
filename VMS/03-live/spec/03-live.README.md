# V/03 Live video — instructions for an implementation

This English text is the source; the Russian [`03-live.README.md`](../03-live.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `live` does and how to check the result. The canon is the norms of the chapters `03.K-live.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `03.K-live.norms.md` (Н1–Н5 of each chapter; the addresses `V/03.K Н…`).
- The canon of the manifest: [`live.subsystem.yaml`](../../live.subsystem.yaml): the bytes as they are.
- [The contract](../03-live.api.openapi.yaml) expresses the forms of the HTTP inputs of the canon.
- Acceptance: [chapter 1](../../acceptance/1/README.md), [chapter 3](../../acceptance/3/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- [The lecture](../../03-live.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/03.1 | the manifest `VMS/03-live/live.subsystem.yaml` loads with the strict loader without edits; the unit door of the console executes the delivery's declarations; placement — the platform controller | [acceptance 1](../../acceptance/1/README.md) |
| V/03.2 | the source by the heartbeats (loopback RTSP of its own server, otherwise the receiver of its own cluster with a leaf of the role `liveworker`), one subscription, the epoch, reconciliation (`resets`), `waiting` with reasons | by reading |
| V/03.3 | the gateway door per [OpenAPI](../03-live.api.openapi.yaml): the route `whep`, the door token, the stream choice by size, an offer without trickle, a talk, hang-up, the limits, the log `live.view*`, the CORS of the route | by reading (the WHEP stand — later), [acceptance 3](../../acceptance/3/README.md) `@manual` |
| V/03.4 | branching (a queue ≤ 1 s, a tee without branches), the PT from the offer, H.264/H.265 without transcoding, the note `codec`, sound with the exception of Н1.5 | by reading; a test of the PT choice over offers |
| V/03.5 | the grace and the deletion of the row by `cas` (`worker.deletes`), the sweeping of sessions (`CONNECT_SECONDS`), the heartbeat (the capacity, the counters, the delivery element), `streams_live`, stopping | by reading |
| V/03.6 | the table `accounts` (the gateway only), the doors `/live/accounts` through `door.pass` per [OpenAPI](../03-live.api.openapi.yaml), the name check and the revocation of grants through its own console, the contribution to the book `stream-accounts` (one gateway of the cluster), the RTSP door with Digest and grants | by reading (the stand of the worker `live` — later) |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam` (V/01), `rec` (V/02), then `live` —
the VMS acceptance runs only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/03.5 Н1.1 | counting an RTSP client as a viewer that holds the delivery row | only WHEP viewers hold the row; an RTSP client is in `sessions`, not in `viewers` |
| V/03.3 Н1.2 | answering the first offer before the stream parameters | the first offer opens the source and waits for the parameters within `ICE_WAIT`; if they have not arrived — 404 `not yet` |
| V/03.6 Н1.2 | revoking the grants of a deleted account by the gateway | the grants are revoked by the domain reconciliation; the gateway deletes only the row |
| V/03.1 Н1.2 | merging the viewers' labels | the labels are set by the first viewer; a viewer of another network — 409 and the address of the delivery |
| V/03.4 Н1.1 | taking frames from the share `cam.shm` | the joint of the subsystems is loopback RTSP |
| V/03.4 Н1.5 | refusing a viewer when there is no sound | sound does not hold up the video: neither `not yet` nor 400 |
| V/03.3 Н1.2а | treating the token as the right to talk | the token is issued by `view`; the right is an executed request `talk` with `edit` |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapter 1 passes on a platform that has passed its own acceptance;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

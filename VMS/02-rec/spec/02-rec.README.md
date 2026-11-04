# V/02 Recording — instructions for an implementation

This English text is the source; the Russian [`02-rec.README.md`](../02-rec.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `rec` does and how to check the result. The canon is the norms of the chapters `02.K-rec.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `02.K-rec.norms.md` (Н1–Н5 of each chapter; the addresses `V/02.K Н…`).
- The canon of the manifest: [`rec.subsystem.yaml`](../../rec.subsystem.yaml): the bytes as they are.
- [The contract](../02-rec.api.openapi.yaml) expresses the forms of the HTTP inputs of the canon.
- Acceptance: [chapter 1](../../acceptance/1/README.md), [chapter 4](../../acceptance/4/README.md), [chapter 5](../../acceptance/5/README.md); the stand and the vocabulary — [the common VMS acceptance README](../../../common/acceptance/README.md); acceptance introduces no new requirements.
- [The lecture](../../02-rec.md) explains the reasons; the platform — the norms of the export of the VMS pin at the addresses `P/…` (they are edited not by VMS).

Record a contradiction with its place and a counterexample (the section «On a divergence»); an arbitrary refusal does not replace an
absent norm. The structure of the code is left to the implementation within the canon.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/02.1 | the manifest `VMS/02-rec/rec.subsystem.yaml` loads with the strict loader without edits; the unit and table door of the console executes the recording's declarations | [acceptance 1](../../acceptance/1/README.md) |
| V/02.2 | an engine client per [the contract `obsd`](../02-rec.obsd.contract.md) and the duties of Н1.5; the engine ObjectStorage with patches 01–07; the part `obsd` is installed by the platform installer per the manifest | by reading; the acceptance of chapters 4–5 on a live `obsd` (chapter 3 has no acceptance of its own) |
| V/02.3 | the streams in a volume per Н1.1, the volume refusals of Н1.4, opening a volume Н1.5, a frame into the writer Н1.6, remounting | by reading; the acceptance of chapters 4–5 |
| V/02.4 | the recorder `recworker`: the source, the recording pipeline, places-volumes, refusals, leaving a volume, stopping (`worker.stop_timeout` 47), the writer watchdog, the heartbeat; the start command for the «Стенд» — in the implementation description | [acceptance 4](../../acceptance/4/README.md) |
| V/02.5 | the archive door per [OpenAPI](../02-rec.api.openapi.yaml): visibility and the ceiling, the epoch rule, the fMP4 muxer, the address, the log, admittance | [acceptance 5](../../acceptance/5/README.md) |
| V/02.6 | the volume kinds, the quota as a ring, the volume secret, the backup `offline` with pre-recording, a copy from the backup, the card of the server (one `edge`, the recording is ordered by the holder), `incidents` | by reading |
| V/02.7 | labels: a copy in `incidents`, sealing and reconciliation (the digest function — in the implementation description), a loss, the recording side, the answer `freeing` | by reading |
| V/02.8 | catch-up recording (the plan, the budget, the window, the download, the landing), the request with the profile `fetched`, the scan order `worker.creates` to `detjob` | by reading |
| V/02.9 | a recording in the domain catalogue (`ref`, the assignment), the source of a foreign camera, the receiver (admittance by a token, polling, `have`, the frame time, the tee; the transport — in the implementation description), a range claim, the neighbours, the books `primaries`, `polls`, the reserve by the book, the transmitter and the star, the witness `rec/polled` | by reading |

The manifest is specification data: the implementation reads its bytes as they are (ADR-0090 addendum (6) item 8).

## Order

First the platform (a stage C generation that has passed the platform acceptance), then `cam` (V/01), then `rec` — the VMS acceptance runs
only on such a platform (ADR-0090 addenda (8), (9)).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/02.4 Н1.5 | counting a separate timeout for the flush, `FINISH_MEDIA` and `WRITER_CLOSE` | one deadline — the «close deadline»; not closed — `WRITER_ABANDON` |
| V/02.5 Н1.3 | serving a fenced-off epoch on a par with the senior one | the automatic choice is by the key `(epoch, live)`, the fenced-off one loses; an explicit `stream` — its frames |
| V/02.5 Н1.2 | reporting the unavailable in the headers of the answer of `/timeline` | the unavailable is in the body `{spans, unreachable, unavailable}` |
| V/02.2 Н1.1, Н1.3 | launching the engine `obsd` directly and expecting it to read the subsystem file | the part is a VMS wrapper: it reads the file per `W2C_SUB_ENV` and passes to the engine the four keys `OBSD_*` of the table of Н1.3 through the environment |
| V/02.9 Н2 | treating the local joint of one server as a contract | between servers and clusters — the six paths `/ingest/*`; the local joint is a choice of the implementation |
| V/02.1 Н1.1 | refusing a recording on the card of a foreign server | `home` has no `must_match`; the guard is the recorder of the card |

## Done when

The manifest loads with the strict loader without edits; the acceptance of chapters 1, 4, 5 passes on a platform that has passed its own acceptance;
the checklist items marked «by reading» are confirmed by the implementation description (the section «Решает реализация» of each chapter).
The checks of the schema, of the loader and of the stand do not substitute for one another.

## On a divergence

The order of the sources: the norms of the chapter → OpenAPI → acceptance and vectors → the lecture; the platform — the norms of the export of the VMS pin.
If a norm is silent or contradicts itself — a question to «Спецификация VMS» with the place, a counterexample and a proposal; a platform
norm — through «Архитектор». An acceptance defect (an expectation against a norm) — the same route; a closed decision
is entered into the canon and does not stay in these instructions.

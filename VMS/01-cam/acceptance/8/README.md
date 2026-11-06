# Acceptance V/01.8 — device search

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.8-cam.norms.md`](../../spec/01.8-cam.norms.md) N5. The stand and the vocabulary are as in [acceptance 1](../1/README.md): no workers, the manifest `cam`, the forms of the tables.
The run — after the first stage C generation that has passed the platform acceptance (ADR-0090 addenda (8), (9)).

| Scenario | Norm | What it observes |
|---|---|---|
| `01-tables` | V/01.8-01 | the search row and the question are written by the tables door, a field not per the form — 400; the operator does not write `found`, `probe_replies`: 403 «written by its worker» |
| `02-live` | V/01.8-02, -03 | `@manual`: a live search and the question about the model on a driver; a zero MAC and a matching MAC do not merge devices |

The `@manual` steps wait for a live driver and a network with cameras: the stub driver `Drivers/Virtual` gives no search of such a model, and the stand does not create a broadcast answer (ADR-0102 addendum (4) item 8, addendum (6) item 11).
By reading: the base worker, calls outside the loop. The holder double and the `backend` side — acceptance V/11.

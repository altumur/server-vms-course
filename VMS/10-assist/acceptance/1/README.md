# Acceptance V/10.1 — the model: the unit and the worker

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`10.1-assist.norms.md`](../../spec/10.1-assist.norms.md) N5. The stand and the vocabulary are [the common VMS acceptance
README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the manifest `VMS/10-assist/assist.subsystem.yaml` is installed; the console — `CONSOLE_ROOT=assist`
(the door `/models`). The controller, the workers, the resource and the domain are not started. Requests — from loopback without a domain (one identity with full
rights). A scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/10.1-01 | a model row with the defaults `enabled`, `model`, `quant`, `context`; a repeated name — 409 `exists`; without `labels` and with empty `labels` — 400; `model`, `quant` not from the list, `context` outside the bounds — 400; an edit of `context` — 200; an edit to empty `labels` — 400 |

The right «to talk to the model» (`view` on the row, the door token) — acceptance 2; placement by label and one model per server —
by reading (N5 of the norms).

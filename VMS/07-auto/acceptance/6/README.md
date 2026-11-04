# Acceptance V/07.6 — schedules, modes, windows

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`07.6-auto.norms.md`](../../spec/07.6-auto.norms.md) Н5. The stand and the vocabulary are [the common VMS acceptance
README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The stand of [acceptance 1](../1/README.md): the store and the cluster console, the VMS manifests `cam`, `rec`, `det`, `detjob`, `auto`,
`CONSOLE_ROOT=auto`; the controller, the workers, the resource and the domain are not started. Requests — from loopback, one identity with full rights.
A scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-tables` steps 1–2, 8, 10, 12, 14 | V/07.6-01 | the rows of each table are set up, the defaults and the stamps are in place |
| `01-tables` steps 3–7, 9, 11, 13, 15 | V/07.6-01 | a wrong `kind`, the form of `week`, the time, `astro`, the key; a second row of `modes` and of `mode_current` — 400 |
| `02-history` | V/07.6-08, V/07.6-09 | the form of `versions`, `answers`, the composite key; `by`, `at` — a stamp |
| `03-pulse` | V/07.6-05 | `@manual`: the heartbeat field `object_mode`; the chapter's stand has no evaluator |

The moment function — the vectors [`moment`](../../vectors/moment/README.md); the stand does not repeat them. The row `versions` of this acceptance is written
by the table door: writing as a batch with an edit — V/11.

# Acceptance V/08.6–V/08.9 — export

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norms are [`08.6-exp.norms.md`](../../spec/08.6-exp.norms.md) … [`08.9-exp.norms.md`](../../spec/08.9-exp.norms.md), sections Н5. The stand and
the vocabulary are [the common VMS acceptance README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`,
`VMS/03-live/live.subsystem.yaml`, `VMS/08-exp/exp.subsystem.yaml` are installed; the console — `CONSOLE_ROOT=exp` (the door `/parts`), `rec`
is mounted (`console2` — the prefix `/rec`). For `01-create` the controller, the workers and the resource are not started; requests — from loopback without
a domain (one identity with full rights). A scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/08.6-01 | the part row: the defaults `keep`, `labels`, no state; a recording of another camera — 409 `must_match`; `fixed` — 400 |
| `02-work` | V/08.6-03, V/08.6-06, V/08.7-01 … V/08.7-04 | the work of the parts, holes, codes, the archive frame and the live frame |
| `03-cancel` | V/08.8-01 … V/08.8-04 | the requests `cancel` and `delete`, the expiry, a restart of the holder |
| `04-door` | V/08.9-01 … V/08.9-04, V/08.7-05 | the file door and the route `parts` |

Steps with the media stand, going through the gateway and the file door are `@manual` with a description: they are judged by a run of the implementation on a stand with
a camera holder, the recorder `obsd` and the gateway (the README of the common VMS stand, «Медиа стенда»). The translation of a `backend` order is
V/11 when the contract of the fork with `/exports` is fixed.

In all, 4 independent scenarios, 13 steps.

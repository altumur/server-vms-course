# Acceptance V/12.4 — installation and the `backend` manifest assembler

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`12.4-psim.norms.md`](../../../spec/12.4-psim.norms.md) Н5; the adapter and the door — chapter 3 Н5. The stand and the vocabulary are
[the common VMS acceptance README](../../../../common/acceptance/README.md) («Плагины psim на стенде», the directives `@psim`) over the common
platform README (export `7a875c75`).

## Preparation

The store and the cluster console, the resource `srv-a`; the canon `VMS/11-backend/backend.subsystem.yaml` is installed, the controller `backend` is started, there are no rows `backend/instances`
and no worker `backend` (the assembly waits only for `served`, the common README «Плагины psim на стенде»);
there are no plugins. The console — the root `backend`, the plugin subsystems are mounted after installation (the paths `/psim-<id>/…`). Requests —
from loopback without a domain (one identity with full rights). A scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-install` | V/12.4-01, V/12.4-02, V/12.4-03 (`install` → `@traverse` → `finish`), V/12.1-01, V/12.3-01, V/12.3-03, V/12.3-04 | installation on a running stand: the row `plugin` with `version`, the full manifest `/source`, an object of the kind, `enabled` written by the door bypassing the step (V/12.4 Н1.3 «Limits»), the assembly of the `calls` of backend |
| `02-dependent` | V/12.1-06, V/12.4-03, V/12.3-05 | the reverse order: the dependent before the owner, the reassembly gives reading and the ring; a foreign plugin by the ring and by a request |
| `03-disable` | V/12.4-05 | disabling and enabling by the step, a traversal without restarts |
| `04-page` | V/12.3-06, V/12.4-02 | the controller `psim-<id>` is brought up by the installation (on the stand — the role `enable`), the worker-adapter — `@start worker`; the page token, entry by `?t=`, the cookie, the removed headers, `static` |

What the stand does not see: the plugin process, the gRPC calls and the psim pages — `@manual` with the reason in the step (they are judged by the
implementation run on the acceptance machine with the plugins built). The generator is judged by the vectors [`../../vectors/generate`](../../../vectors/generate/README.md).

In all, 4 independent scenarios, 40 steps.

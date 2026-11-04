# V/12 psim plugins — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/12-psim.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the lesson builds and how to check the result. The canon is the norms of the chapters `12.K-psim.norms.md`; these
instructions do not add to them. The platform is the export `cammeta-specs` `7a875c75`; the loader keys of ADR-0115 are P/02.1 of the course.

## Inputs and their priority

- The canon: the norms of the chapters `12.K-psim.norms.md` (Н1–Н5 of each chapter; the addresses `V/12.K Н…`).
- psim-sdk `c3d9ebb`, read-only: `schema/plugin.schema.json` (the generator's input), `proto/psim/platform/v1/*.proto`
  (the adapter's protocol), `psim_platform_emulator/` (the host's behaviour where the proto is silent), `psim_plugins/cmd/security_controller`,
  `camera` (acceptance). The bytes of `psim_platform_emulator/webui/i18n.js` — SHA-256
  `7ef4d865fbb3265c18af5ba6b0e8bb2c6c17b1838e20794592a9f4d9c5675584`.
- The adapter door — [`12-psim.api.openapi.yaml`](12-psim.api.openapi.yaml).
- The generator vectors — [`vectors/generate`](../vectors/generate/README.md).
- The lecture (`ru/12-psim.md`, for people, not in the export) explains the reasons.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/12.1 | the mapping `plugin.json` → the manifest of the subsystem `psim-<id>`: the unit `units/plugin`, the kind tables and `<т>_seen`, fields from parameters, labels `{key, text}` and `display.langs`, the events `<т>.<id>` with the class by `severity`, commands by request, the resource routes `PROXY`, reading and requests to the owners of `source` | the vectors `generate` |
| V/12.2 | the generator — a function of the plugin directory and the list of installed ones; the check by the psim schema; the manifest and the `calls` fragment for `backend`; a refusal in one line | the vectors `generate` |
| V/12.3 | the worker-adapter: the plugin process as by the psim host (`stdin`, the account in memory, readiness), the server `Platform` on loopback, `Configure`, `ChangeUnit`, commands and events, the page door with entry by `?t=`, a session cookie and `static` | stand |
| V/12.4 | the step `psim` (`install`, `enable`, `disable`, `sync`): initial values, the assembly of the `backend` manifest from the canon and the catalogue fragments, the reassembly of the dependent plugins | stand |

## Order

First the loader keys of P/02.1 (ADR-0115; `display.tables` — addendum (11)), then the generator and its vectors, then the adapter and
the install step, then the stand. `backend` builds the description of a plugin kind by V/11.

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/12.1 Н1.1 | setting `required` on parameters | readiness is judged by the adapter (`unfit`), not by the console |
| V/12.1 Н1.3 | putting `readonly` into the row fields | `unit.state` at the plugin, `<т>_seen` at the kind: the console does not write them |
| V/12.2 Н1.2 | assembling `backend` from the generator's files | the fragments — from the catalogue rows `platform/manifest/psim-*` |
| V/12.3 Н1.1 | passing the address and the account through the environment | only `stdin` frames; the psim variables are not inherited |
| V/12.3 Н1.3 | sending `x_secret` to the plugin | the psim name without the suffix, the value in plain text |
| V/12.3 Н1.4 | sending a child before its parent | the plugin silently loses it |
| V/12.3 Н1.6 | setting the CSP `sandbox` or putting the token into `#` | the psim page goes by relative `fetch` and does not read `#` |
| V/12.4 Н1.4 | accepting the secret from a file | input only; in a file — a refusal |

## Done when

The vectors `generate` pass: the manifests are loaded by the strict loader P/02.1 without edits; on the stand both psim-sdk plugins work
without edits by the scenarios of chapter 4 Н5.

## On a divergence

The order of the sources: the norms of the chapter → psim-sdk `c3d9ebb` (proto, then the emulator) → the lecture. If a norm is silent or contradicts itself —
a question to «Спецификация VMS» with the place, a counterexample and a proposal; a new manifest word — through «Архитектор» (ADR-0071).

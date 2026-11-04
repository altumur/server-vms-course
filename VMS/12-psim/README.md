# V/12 psim plugins

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Status: **norms of chapters V/12.1–V/12.4** (2026-11-03, «Спецификация VMS»; the plan accepted by «Архитектор»); the generator vectors — after
the loader key `display.tables` (ADR-0115 addendum (11)), the stand acceptance — [`acceptance/4`](acceptance/4/README.md). The basis is ADR-0071 (psim plugins
through an adapter), ADR-0115 with addenda (1)–(15). The platform is the export `cammeta-specs` `7a875c75`; the loader keys of ADR-0115 are P/02.1
of the course. psim-sdk `c3d9ebb` is read-only. The lesson has no canonical manifest: the subsystem's manifest is built by the generator
from the plugin's manifest.

## What lesson V/12 is

A psim plugin is a foreign executable file with the manifest `plugin.json`: object kinds with parameters, events, commands, pages.
With us each plugin is a subsystem `psim-<id>`. The generator builds its manifest from the plugin's manifest, the worker-adapter starts
the plugin process and plays the psim platform for it, the install step puts the manifest and reassembles the `backend` manifest so that
the VMS console sees the new kinds. The settings page of a plugin object is built automatically — by the kind description (V/11); the
plugin's own page opens alongside, through its door. The plugin itself does not change.

## Chapters

| Chapter | What it norms | Status | Platform and lessons |
|---|---|---|---|
| V/12.1 | The mapping `plugin.json` → the subsystem manifest: the name `psim-<id>`, the unit `units/plugin` (parameters, `enabled`, `readonly` in `unit.state`), the kind — a table with `id`, `plugin`, `parent`, `<т>_seen` for `readonly`, a field from a parameter, labels `{key, text}` and `display.langs`, `display.tables`, the events `<т>.<id>` and the class by `severity`, commands by request, the routes `PROXY`, the owners of `source` | norms | P/02.1; ADR-0115 |
| V/12.2 | The generator: a function of the plugin directory and the list of installed ones, the psim schema `c3d9ebb`, the manifest and the `calls` fragment with the parts `enabled` and `objects`, the owners of `source`, a refusal in one line | norms | P/02.1; V/11.1 |
| V/12.3 | The adapter: the process as at the psim host (`stdin`, the account in memory, readiness, stop), the server `Platform` on loopback, `Configure`, `ChangeUnit`, commands and events, a foreign plugin by `source`, the page door — entry by `?t=`, the session cookie, `static` | norms | P/03, P/03.4 Н1.7, P/06.4 Н1.5, P/06.5 |
| V/12.4 | The step `psim`: installation, initial values (an empty value not by the schema, the secret by input only), enabling and disabling, the assembler of the `backend` manifest from the canon and the catalogue fragments, the reassembly of the dependent ones | norms | P/02.3; V/11.1 |

Neighbours: `backend` — the kind description and `/units` for `origin: plugin` (V/11); its manifest is assembled by the step of this lesson; deployment —
the packages of the adapter and of the plugin (V/09).

## Forms and doors

- **Rows:** `psim-<id>/units/plugin`, the kind tables `psim-<id>/<т>`, `psim-<id>/<т>_seen`, the event rings `psim-<id>/<т>_events` (ADR-0115 addendum (13)), the state
  `psim-<id>/state/<имя>/plugin`, the requests `psim-<id>/requests/<rid>`, the event log of the unit `plugin`.
- **Doors:** the door of the adapter process — [`spec/12-psim.api.openapi.yaml`](spec/12-psim.api.openapi.yaml); the server `Platform` — gRPC
  on loopback, it does not go outside.
- **Data families:** the lesson has no rows of its own in the VMS catalogue — the tables are set by the plugin's manifest.

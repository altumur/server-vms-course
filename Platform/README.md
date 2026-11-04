# Platform

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The module of specification lessons of the platform, sliced by micromodules: one lesson — one process or library (ADR-0083).
The catalogue of a lesson is `NN-<процесс>`; the lesson number is the address of the owner (`P/NN`), the map — [`lessons.tsv`](lessons.tsv).
Common to all — [`common/`](common/README.md); the layers of В7 — [`common/LAYERS.md`](common/LAYERS.md), the pinned versions of the libraries — [`common/versions/`](common/versions/README.md). The design note — `Platform/module-design.md` (for people, not in the export).

| P | Catalogue | Micromodule |
|---|---|---|
| 01 | [`01-store/`](01-store/README.md) | Store |
| 02 | [`02-installer/`](02-installer/README.md) | Manifest and installer |
| 03 | [`03-worker/`](03-worker/README.md) | Worker (SDK) |
| 04 | [`04-controller/`](04-controller/README.md) | Controller |
| 05 | [`05-resource/`](05-resource/README.md) | Resource |
| 06 | [`06-console/`](06-console/README.md) | Cluster console |
| 07 | [`07-console-module/`](07-console-module/README.md) | Console module |
| 08 | [`08-domain/`](08-domain/README.md) | The process domain |
| 09 | [`09-agent/`](09-agent/README.md) | The agent (9.1) and the relay mode (9.2) |
| 10 | [`10-domain-console/`](10-domain-console/README.md) | The domain console |

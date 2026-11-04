# VMS

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The module of specification lessons of the video subsystem, sliced by subsystems: one lesson — one subsystem with its own
manifest (ADR-0090 addendum (2)). The lesson directory is `NN-<имя>`, the lesson number is the owner address (`V/NN`), the map is
[`common/lessons.tsv`](common/lessons.tsv). Common to all lessons — [`common/`](common/README.md). The lesson layout is
as in `Platform/`: the lecture `NN-<имя>.md`, the norms `spec/`, the acceptance `acceptance/`, the data `data/`, the vectors `vectors/`. The VMS data
families are JSON Schema 2020-12 with the layers of `Platform/common/LAYERS.md`, as on the platform (ADR-0092).

The VMS lessons read the platform only from the export `cammeta-specs` at a pinned commit (ADR-0090 item 2); a change of the
platform is requested by a file in the inbox (item 4). The module is written by «Спецификация VMS» per the whitelist of ADR-0090 addendum (1).

The manifests and the shell of the subsystems — **the canon is here**: `NN-<имя>/<sub>.subsystem.yaml`, `<sub>.shell.html` (ADR-0090
addendum (6) item 8). At the start they were copied byte for byte from `Source/vms/`; `Source/vms/*` are the bytes of a frozen witness,
nobody edits them (addendum (7) item 4). Lesson V/10 `assist` is new, it has no witness: the subsystem and the lesson are entered into
the listings of ADR-0090 addenda (2), (3), (5) by the decision ADR-0093 addendum (2) item 1.

| V | Directory | Subsystem | Status |
|---|---|---|---|
| 01 | [`01-cam/`](01-cam/README.md) | `cam` | translated |
| 02 | [`02-rec/`](02-rec/README.md) | `rec` | translated |
| 03 | [`03-live/`](03-live/README.md) | `live` | translated |
| 04 | [`04-det/`](04-det/README.md) | `det` | translated |
| 05 | [`05-detjob/`](05-detjob/README.md) | `detjob` | translated |
| 06 | [`06-detedge/`](06-detedge/README.md) | `detedge` | translated |
| 07 | [`07-auto/`](07-auto/README.md) | `auto` | translated |
| 08 | [`08-exp/`](08-exp/README.md) | `exp` — export, chapters V/08.6–V/08.9 | translated |
| 09 | [`09-deploy/`](09-deploy/README.md) | VMS deployment | translated |
| 10 | [`10-assist/`](10-assist/README.md) | `assist` | translated |
| 11 | [`11-backend/`](11-backend/README.md) | `backend` | translated |
| 12 | [`12-psim/`](12-psim/README.md) | psim plugins, `psim-<id>` | translated |

The composition of the lessons is preliminary: the exact distribution of the chapters М10B, М12A, М12B over the lessons is the inventory of «Спецификация VMS»
(addendum (4)), checked by «Архитектор».

**The merge of 2026-11-03** (ADR-0118): lesson 08 «Страница VMS» is merged into V/11 as chapters 15–19; the number 08 went to the export lesson (formerly 13), its chapters are V/08.6–V/08.9; V/08.1–V/08.5 always mean the former page and lead to V/11.

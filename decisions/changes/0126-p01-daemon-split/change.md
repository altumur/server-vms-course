# Change 0126-p01-daemon-split — two consecutive stages for the one-box daemon (ADR-0126)

change: 0126-p01-daemon-split rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация CT 103» · state review

**Why.** The Architect’s decision of 2026-11-05 within [ADR-0126](../../0126-этапы-реализации-урока-форма-stages.md): MiniMax
attempts 30–32 stopped at 47 of 75 checks of `daemon_box` without writing code. The plan is split into a smaller service-door
stage and a following copy stage. This changes the plan, not the norms of the store. Base: main `2c16ef7cfab80e96bf84620a6236cc43d3f84623`.

**The split.** Stage 8 `daemon_doors` selects `04-store-metrics`, `15-service-doors`, `16-status-no-api`,
`23-service-door-forms`, `24-service-door-methods`, `21-id-memory` (24 steps), and keeps the dependency on `http` (5).
Stage 9 `daemon_copy` selects `10-foreign-dir`, `11-copy`, `12-copy-refused`, `14-copy-ids` (51 steps), and depends on
`daemon_doors` (8). The old weight 4 is divided by step count: 4 × 24/75 = 1.28 and 4 × 51/75 = 2.72, rounded to integer weights 1 and 3. Both keep
kit `-`, parts `-`, and an empty `when`. The scenario sets are disjoint and their union is the old set: all 75 checks remain.

`durable` becomes stage 10, depending on `daemon_copy` (9); `group` becomes stage 11, depending on `daemon_copy` and `durable`
(9, 10). Their goals, norms, gates, weights, kit/parts and applicability remain unchanged. Stages 1–7 are unchanged.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/forms/stages.tsv` | replace: stages `daemon_box` → `daemon_doors`, `daemon_copy`; header; n/depends of `durable`, `group` | 19d60a31e397bb7d345d6bbcdc990c50b384c303 | a78561456993e960fd16d2c83a751d988f1b9e23 |
| `Platform/01-store/spec/01-store.README.md` | replace: introduce the two daemon stages in «Order of work» | 5122581dc9b97d6a062f3dee38a1138a78f021cd | 1fe10ee193b119bb0bac5af2aef8758d02461b29 |
| `Platform/01-store/ru/spec/01-store.README.md` | replace: translate the introduction in «Порядок работы» | 3398cba21d8a33a4a1c1ea41af40c1f1d78212e2 | ae2f3db184834ebbcb3ea2870bcd9dc803d76e22 |
| `decisions/adr-norms.tsv` | append: the Architect’s decision of 2026-11-05 under ADR-0126 | 5e3e6fa105c8204715b59daf7f2297b5b897bbc6 | 3b8bde658b7c8dea0ee0ad5091e9c997ca2dbc7d |
| `decisions/changes/registry.tsv` | append: this change, rev 1, state review | 2bb76e0d0a3243de3298c0ccbff63b73e02490b0 | 75a7086ca6b3dc99b095a07f18fef1c8f1455420 |

The form diff is addressed by `stage`; the blob hashes guard the whole-file replacement. The change metadata is this
`change.md` and `delta.md`; no requirement text is added, modified or removed.

## Change map

| Place | Mark |
|---|---|
| `forms/stages.tsv` | changed: two stages, header, order numbers and dependency references |
| `spec/01-store.README.md`, Russian translation | changed: introduce the split; gates and weights remain in the form |
| P/01.3 acceptance scenarios and their README | agreed: unchanged; 24 + 51 = 75 selected steps, no missing or duplicated scenario |
| `durable`, `group` and earlier stages | agreed: only the necessary order/dependency references are remapped |
| other Platform stage forms and references to `daemon_box` | agreed: no other active form or executable consumer in the course names this stage; existing decision history is retained |
| P/01 norms, OpenAPI, data, vectors, seams | not related: behavior and acceptance bytes do not change |
| runner and kit generators | agreed: existing stage/gate grammar; no new selector or kit part |
| `adr-norms.tsv`, change registry | changed: append this decision and rev 1 in state review |

## Validation

The author verified exact scenario membership, 24/51 step counts, unchanged stages, remapped dependencies, append-only
journals and all five base/result blobs in the manifest. `check_spec.py` with no arguments: PASS with 61 exceptions,
exit 0 (`stage_rows=11`). This validates the plan and course consistency; no implementation or MiniMax attempt was executed.

## History

- rev 1, 2026-11-05 — «Спецификация CT 103», branch `spec103/p01-daemon-split`: the Architect’s decision; plan split and en/ru introduction.

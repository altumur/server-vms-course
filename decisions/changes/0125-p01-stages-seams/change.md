# Change 0125-p01-stages-seams — tests:<chapter>:<scenarios>[:seams] in the gates of P/01 (ADR-0125 addendum (4) items 1, 7; ADR-0126 addendum (7))

change: 0125-p01-stages-seams rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация» · state review

**Why.** ADR-0125 addendum (4) item 1: `store_core` is checked by the tests of kit B from the scenarios of chapter 1.1 that judge
Н3; item 7: the properties of the core checked «by reading» get scenarios over the seams of the process. ADR-0126 addendum (7):
the seams in `acceptance/<chapter>/seams.tsv` (the runner does not read it), `tests:<chapter>:<scenarios|*>[:seams]` without the
name of the stage, the gate — a list by «;», no separate stages; the parts `vectors` and `stagetests`. Supersedes the kit
`0125-p01-stages-store-core` (its branch is not merged).

**The scenarios of Н3 (20 of 40).** 01-absent … 08-list (read, write, delete, list, versions), 09-guard, 10-guard-absent,
11-guard-before-cas (the guard), 12-id, 30-id-fingerprint, 31-delete-cas-id-order (the id memory), 28-admission (the admission
time), 33–37 (the batch). Not taken: the form and the order of checks (13, 14, 16, 20, 23, 24, 26, 32, 38 — the stage
`model`), the routes and the query (17, 25, 27), the limits (15, 19, 22, 29, 39), the rights (21, 40 — chapter 1.2), the refusal
body (18). All start with an HTTP step.

**The classes of «by reading»** (the Architect accepted them): the property of the core — P/01.1-11, -15, -25, -26, -31
(= P/01.3-11) — the seams; P/01.1-03 — the core, no seam (the adapter by bytes); the duty of a client — 1.1-09, -18, -19;
the premise of the environment — 1.1-27, 1.3-09; a documented choice — 1.1-16, -20, -21, -22, 1.3-05; mixed — the daemon, the
CLI, the group, chapter 1.2 (the flags are judged by `daemon-flags.tsv`).

**The seams (6).** s1-id-memory-time-alone (P/01.1-11: both conditions of Н3 — time alone does not let it forget), s2-admission-equal
(P/01.1-25), s3-admission-monotone (P/01.1-26), s4-parallel-cas (P/01.1-15) — in the gate of `store_core`; s5-reopen-id-admission
(P/01.1-26, -11 after a restart), s6-reopen-batch (P/01.1-31) — in the gate of `durable`. The directives — the header of the file;
agreed with «Генераторы» (Config.Now from 2000000000, DataDir, a concurrent Handle).

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/forms/stages.tsv` | replace: gate of `store_core` and `durable`, parts, the header | 56db08e66f40c30b2ec152cbac2daf53921d21d7 | 9329a0ccea22ff438e35228b881515f048f3aa10 |
| `Platform/01-store/acceptance/1/seams.tsv` | add | — | 3f8b0a3463d1fe8b780f1db3f09f263cd75e292e |
| `Platform/01-store/acceptance/1/README.md` | add the section «`seams.tsv`» | 40e4bb620cc5413e1942e19a98e61321f659249d | b5e994db99a86f1b4dfe60073cd4f90ecbc4e0df |
| `Platform/01-store/ru/acceptance/1/README.md` | translation | 64b94ff4c52d1f7ebc7c1f7ee06ef4ab6e10109c | 8274f8bb455bc575756ecc11adacabfc961a5362 |
| `skills/lesson-spec/scripts/check_forms.py`, `test_check_forms.py` | the gate grammar (a list, `:seams`), the parts `vectors`, `stagetests` | — | — |
| `decisions/adr-norms.tsv`, `decisions/changes/registry.tsv` | append the rows of the change | — | — |

## Change map

| Place | Mark |
|---|---|
| `spec/01-store.README.md` «Order of work» | agreed: it refers to the table |
| acceptance 1.1 `scenarios.tsv` | not related: unchanged, named by the gate |
| the checklist of chapter 1.1 («by reading» items -11, -15, -25, -26, -31) | agreed: the text stays; the seams test them in kit B |
| the runner | not related: it does not read `seams.tsv` |

## History

- rev 1, 2026-11-04 — «Спецификация»; applied in the branch `spec/0125-seams`.

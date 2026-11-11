# Manifest and installer — lesson P/02

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

A micromodule: a command process, a centre, units. What it norms and from where — the module design note `Platform/module-design.md` (judge-only: for people), the table «Lessons».

The layout of the catalogue (the English source on the canonical path, the Russian text for people in `ru/`). The installer has no OpenAPI of its own — it has no HTTP doors;
`GET /manifest`, `ManifestView` and `ConsoleRefusal` belong to [chapter 6.5](../06-console/spec/06.5-console.norms.md) of the console:

```text
README.md                            this file
spec/02.K-installer.norms.md         norms (chapters 2.1–2.5 — .K)
spec/02.1-installer.schema.json      the form source of chapter 2.1 (with .relations.json, .layers.tsv, .scalars.tsv)
spec/02.2-installer.view.schema.json the schema of the canonical view of chapter 2.2
spec/02-installer.README.md          implementation instructions
lifecycle.md                         flags, environment, exit codes, units
forms/README.md                      form columns and non-HTTP seam grammar
forms/daemon-flags.tsv                command option names, types and conditions
forms/operator-commands.tsv           command ids, argv prefixes and positional arity
forms/refusals.tsv                    the canonical refusal catalogue of chapters 2.1–2.5
forms/stages.tsv                      the implementation plan
forms/rollout-poll.machine.yaml      forms (the machine of the rollout poll with its traces rollout-poll.traces.tsv)
data/<family>.schema.json            data families the lesson owns (JSON Schema 2020-12)
vectors/<algorithm>/                 vectors of the algorithms the lesson introduces
acceptance/1/                        acceptance of chapter 2.1 (README.md, verdicts.tsv, classes.tsv, diagnostics.tsv, cases/)
acceptance/2/, acceptance/3/         acceptance of chapters 2.2, 2.3 (README.md, puts.tsv, puts/)
acceptance/5/                        acceptance of chapter 2.5 (README.md, scenarios.tsv, variants/)
acceptance/1/seams.tsv, acceptance/4/seams.tsv  supplementary core/command/poll seams for kit stagetests
ru/                                  for people, not in the export — the lecture ru/02-installer.md, translations of the English text by the same path
```

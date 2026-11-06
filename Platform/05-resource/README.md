# Resource — lesson P/05

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a process on the server. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Lessons».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                           this file
spec/05-resource.norms.md           norms (one chapter)
spec/05-resource.api.openapi.yaml   doors
spec/05-resource.README.md          implementation instructions
lifecycle.md                        flags, environment, exit codes, units
data/<family>.schema.json           data families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088), with .layers.tsv, .outcomes.tsv
vectors/relieve/                    vectors of the algorithm the lesson introduces
acceptance/                         acceptance of the lesson (README.md, scenarios.tsv, inputs/)
ru/                                 for people, not in the export — the lecture ru/05-resource.md, translations of the English text by the same path
```

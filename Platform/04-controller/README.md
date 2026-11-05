# Controller — lesson P/04

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process `<sub>controller`. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Уроки».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                        this file
spec/04-controller.norms.md      norms (one chapter)
spec/04-controller.README.md     implementation instructions
lifecycle.md                     flags, environment, exit codes, units
data/<family>.schema.json        data families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/             vectors of the algorithms the lesson introduces
acceptance/                      acceptance (README.md, scenarios.tsv)
journal/corrections.tsv          the log of AI corrections — history, not an input; not in the export
ru/                              for people, not in the export — the lecture ru/04-controller.md, translations of the English text by the same path
```

The generated-kit forms and controller test ports are [forms/README.md](forms/README.md); the optional stage plan is [forms/stages.tsv](forms/stages.tsv). The process scenarios and the reading checklist remain required.

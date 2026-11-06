# Worker (SDK) — lesson P/03

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a library in each language, the role `<sub>worker`. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Lessons».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                        this file
spec/03.K-worker.norms.md        norms (chapters 3.1–3.7 — .K)
spec/03-worker.README.md         implementation instructions
lifecycle.md                     flags, environment, exit codes, units
data/<family>.schema.json        data families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/             vectors of the algorithms the lesson introduces
acceptance/<K>/                  acceptance of chapter K (2, 3, 4, 6: README.md, scenarios.tsv)
ru/                              for people, not in the export — the lecture ru/03-worker.md, translations of the English text by the same path
```

The kit forms are [forms/README.md](forms/README.md): process inputs, the refusal catalogue, the slot capture machine and a stage plan. SDK seams in `acceptance/K/seams.tsv` supplement the process scenarios; their normalized CALL ports are not an implementation API.

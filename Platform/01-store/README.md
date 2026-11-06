# Store — lesson P/01

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a process; roles are sockets. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Lessons».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                        this file
spec/01[.K]-store.norms.md       norms (chapters — .K)
spec/01-store.api.openapi.yaml   doors
spec/01-store.library.md         library contract (if any)
spec/01-store.README.md          implementation instructions
lifecycle.md                     flags, environment, exit codes, units
forms/write-checks.tsv           forms of ADR-0120 (check tables with their probes, machines with their traces)
forms/daemon-flags.tsv           the daemon flags (ADR-0125): type, default, required, commands
forms/refusals.tsv               the refusal catalogue of N4 of chapters 1.1–1.3 (ADR-0125)
forms/stages.tsv                 the stages of the implementation (ADR-0126): a plan, not a norm
data/<family>.schema.json        data families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/             vectors of the algorithms the lesson introduces
acceptance/<K>/                  acceptance of chapter K (README.md, scenarios.tsv, inputs/)
ru/                              for people, not in the export — the lecture ru/01-store.md, translations of the English text by the same path
```

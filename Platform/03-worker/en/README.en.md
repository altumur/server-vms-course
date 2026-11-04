# Worker (SDK) — lesson P/03

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a library in each language, the role `<sub>worker`. What it norms and from where — the [module design note](../../module-design.md), the table «Уроки».

The layout of the catalogue (filled by the move, stage B):

```text
03-worker.md                     lecture
spec/03[.K]-worker.norms.md       norms (chapters — .K)
spec/03-worker.api.openapi.yaml   doors
spec/03-worker.library.md         library contract (if any)
spec/03-worker.README.md          implementation instructions
lifecycle.md                    flags, environment, exit codes, units
data/<family>.schema.json       schemas of the families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/            vectors of the algorithms the lesson introduces
acceptance/[K/]                 acceptance
```

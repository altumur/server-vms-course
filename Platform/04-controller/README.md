# Controller — lesson P/04

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process `<sub>controller`. What it norms and from where — the [module design note](../module-design.md), the table «Уроки».

The layout of the catalogue (filled by the move, stage B):

```text
04-controller.md                     lecture
spec/04[.K]-controller.norms.md       norms (chapters — .K)
spec/04-controller.api.openapi.yaml   doors
spec/04-controller.library.md         library contract (if any)
spec/04-controller.README.md          implementation instructions
lifecycle.md                    flags, environment, exit codes, units
data/<family>.schema.json       schemas of the families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/            vectors of the algorithms the lesson introduces
acceptance/[K/]                 acceptance
```

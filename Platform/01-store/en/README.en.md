# Store — lesson P/01

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a process; roles are sockets. What it norms and from where — the [module design note](../../module-design.md), the table «Уроки».

The layout of the catalogue (filled by the move, stage B):

```text
01-store.md                     lecture
spec/01[.K]-store.norms.md       norms (chapters — .K)
spec/01-store.api.openapi.yaml   doors
spec/01-store.library.md         library contract (if any)
spec/01-store.README.md          implementation instructions
lifecycle.md                    flags, environment, exit codes, units
data/<family>.schema.json       schemas of the families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/            vectors of the algorithms the lesson introduces
acceptance/[K/]                 acceptance
```

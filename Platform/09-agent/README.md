# The agent (9.1) and the relay mode (9.2) — lesson P/09

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process domainagent or a mode in a process. What it norms and from where — the [module design note](../../module-design.md), the table «Уроки».

The layout of the catalogue (the move of stage B is done; review analysis of stage B 8–10, № 22, Claude М-15):

```text
09-agent.md                     lecture
spec/09[.K]-agent.norms.md       norms (chapters — .K)
spec/09-agent.api.openapi.yaml   doors
spec/09-agent.README.md          implementation instructions
lifecycle.md                    flags, environment, exit codes, units
data/<family>.schema.json        schemas of the families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/follow/                 vectors of following the holder, the function follow (9.1)
acceptance/1/                   acceptance of chapter 9.1 (the agent of a member)
acceptance/2/                   acceptance of chapter 9.2 (the relay mode)
```

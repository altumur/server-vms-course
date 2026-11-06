# The agent (9.1) and the relay mode (9.2) — lesson P/09

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process domainagent or a mode in a process. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Lessons».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                        this file
spec/09[.K]-agent.norms.md       norms (chapters — .K)
spec/09-agent.api.openapi.yaml   doors
spec/09-agent.README.md          implementation instructions
lifecycle.md                     flags, environment, exit codes, units
data/<family>.schema.json        data families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/follow/                  vectors of following the holder, the function follow (9.1)
acceptance/1/                    acceptance of chapter 9.1, the agent of a member (README.md, scenarios.tsv, inputs/)
acceptance/2/                    acceptance of chapter 9.2, the relay mode (README.md, scenarios.tsv)
ru/                              for people, not in the export — the lecture ru/09-agent.md, translations of the English text by the same path
```

# Cluster console — lesson P/06

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process console. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Lessons».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`). Chapter 6.7 — the late layer of the cluster console — was written by the move of lessons
8–10 (review analysis of stage A 6–7, № 27; review analysis of stage B 8–10, № 22: M-15). The console has no library contract — it is a process with an HTTP door:

```text
README.md                            this file
spec/06.1-console.norms.md           norms of chapter 6.1 — the units door: rows, bodies, tables
spec/06.2-console.norms.md           norms of chapter 6.2 — the write of secrets
spec/06.3-console.norms.md           norms of chapter 6.3 — the guard and people
spec/06.4-console.norms.md           norms of chapter 6.4 — requests and events
spec/06.5-console.norms.md           norms of chapter 6.5 — observations
spec/06.6-console.norms.md           norms of chapter 6.6 — the control doors
spec/06.7-console.norms.md           norms of chapter 6.7 — the late layer: the member's book, forwarding to the domain, the move doors
spec/06.8-console.norms.md           norms of chapter 6.8 — cluster folders (ADR-0096)
spec/06.9-console.norms.md           norms of chapter 6.9 — group operations (ADR-0095)
spec/06-console.api.openapi.yaml     doors (one contract of the lesson)
spec/06-console.README.md            implementation instructions
lifecycle.md                         flags, environment, exit codes, units
data/<family>.schema.json, .layers.tsv, .outcomes.tsv data families (JSON Schema, ADR-0092; ADR-0088): next-id, sweep (6.1); requests, asked,
                                     commands (6.4); door-signer, door-keys (6.5); policy, server-labels, drain,
                                     decommission, schema (6.6); folders, memberof, memberof-gone (6.8); operations, operations-epoch,
                                     operations-turn, opsteps, opbusy, opcount, opdone (6.9)
data/refusal-words.tsv               the closed list of error words by doors (6.1, 6.4, 6.5, 6.8, 6.9; ADR-0094 B5)
vectors/<algorithm>/                 vectors: rid, requests-body, request-digest, reap (6.4); contender-projection, metrics (6.5);
                                     resolve, key-families (6.7); op-step (6.9); fault, values-by-type (6.1) and secret-in, log-mask (6.2) — in common/vectors
acceptance/1/ … acceptance/9/        acceptance of chapters 6.1–6.9 (README.md, scenarios.tsv; 5/inputs/, 5/probe-w.subsystem.yaml,
                                     5/probe-x.subsystem.yaml, 6/inputs/)
ru/                                  for people, not in the export — the lecture ru/06-console.md, translations of the English text by the same path
```

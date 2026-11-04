# Cluster console — lesson P/06

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process console. What it norms and from where — the [module design note](../module-design.md), the table «Уроки».

The layout of the catalogue (after the move, stage B). Chapter 6.7 — the late layer of the cluster console — was written by the move of lessons
8–10 (review analysis of stage A 6–7, № 27; review analysis of stage B 8–10, № 22: М-15). The console has no library contract — it is a process with an HTTP door:

```text
06-console.md                        lecture
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
data/<family>.schema.json, .outcomes.tsv schemas of families (JSON Schema, ADR-0092; ADR-0088): next-id, sweep (6.1); requests, asked,
                                     commands (6.4); door-signer, door-keys (6.5); policy, server-labels, drain,
                                     decommission, schema (6.6)
data/refusal-words.tsv               the closed list of error words by doors (6.1, 6.2, 6.5, 6.6; ADR-0094 B5)
vectors/<algorithm>/                 vectors: fault, values-by-type (6.1); secret-in, log-mask (6.2, in common/vectors); rid, requests-body,
                                     request-digest (6.4); resolve (6.7); op-step (6.9)
acceptance/1/ … acceptance/9/        acceptance of chapters 6.1–6.9 (README, scenarios.tsv, corrections.tsv; 2/fields.yaml,
                                     5/inputs/, 5/probe-x.subsystem.yaml, 6/inputs/)
```

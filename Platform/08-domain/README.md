# The process domain — lesson P/08

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: the process domain of the holder. What it norms and from where — the [module design note](../module-design.md), the table «Уроки».

The layout of the catalogue (after the move, stage B). The lesson is assembled from the holder sides of lessons М11/1–12; the sides of the agent and
of the relay — lesson P/09, of the domain console — lesson P/10, the late layer of the cluster console — [chapter 6.7](../06-console/spec/06.7-console.norms.md).
The lesson has no library contract — it is a process with an HTTP door (`SIGNER_URL`). The common algorithms of the lesson are the contracts
`common/contracts/` (`keys`, `domain-token`, `domain-envelopes`, `accept`, `may`, `record`, `ask-sig`) and their vectors
`common/vectors/`:

```text
08-domain.md                          lecture
spec/08.0-domain.norms.md             norms of chapter 8.0 — the doors of the process: one writer, acceptance of the domain console edits, the class signed
spec/08.1-domain.norms.md             norms of chapter 8.1 — the domain view and the shadow mode
spec/08.2-domain.norms.md             norms of chapter 8.2 — the root, the key set, the book acceptance key, change and revocation without a connection
spec/08.3-domain.norms.md             norms of chapter 8.3 — acceptance of reports
spec/08.4-domain.norms.md             norms of chapter 8.4 — people and grants
spec/08.5-domain.norms.md             norms of chapter 8.5 — books and the names index
spec/08.6-domain.norms.md             norms of chapter 8.6 — placement and edits
spec/08.7-domain.norms.md             norms of chapter 8.7 — the issue of worker tokens
spec/08.8-domain.norms.md             norms of chapter 8.8 — the term, the backup copy, the move and the handover
spec/08.9-domain.norms.md             norms of chapter 8.9 — the shared document and the alarm history
spec/08.10-domain.norms.md            norms of chapter 8.10 — the queue and the cost
spec/08-domain.api.openapi.yaml       doors (one contract of the lesson)
spec/08-domain.README.md              implementation instructions
lifecycle.md                          flags, environment, exit codes, units
data/<family>.schema.json, .outcomes.tsv schemas of families (JSON Schema, ADR-0092; ADR-0088): view, shadow (8.1); keys, root, signer,
                                      signer-pending, book-seal, revoked (8.2); members, member-report,
                                      member-report-delta, member-reported, member-ca-certs, topology (8.3); users,
                                      deleting, disabled, grants, break-glass (8.4); book, names-index (8.5); placement,
                                      placement-record, pending, outcomes (8.6); holder, keepers, backups, stranded (8.8);
                                      shared, shared-docs, alarm-history (8.9); signer-turn (8.10)
data/refusal-words.tsv               the closed list of error words by the doors of the process (ADR-0094 B5)
vectors/<algorithm>/                  vectors: view (8.1), assemble (8.5), issue (8.7)
acceptance/1/, 3/ … 10/               acceptance of chapters 8.1, 8.3–8.10 (README, scenarios.tsv, corrections.tsv; 3/inputs/);
                                      chapters 8.0 and 8.2 have no catalogue (8.2 — the vectors of the common packages, Н5 of the chapter)
```

Chapter 8.0 has no acceptance catalogue: its outcomes are checked by the scenarios of chapters 8.3, 8.8 and 8.10 and by reading (Н5 of the chapter).

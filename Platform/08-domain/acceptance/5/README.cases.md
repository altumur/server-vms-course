# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/5/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

[`08.5-domain.norms.md`](../../spec/08.5-domain.norms.md) N5. The scenarios were moved from the acceptances of M11/05 (01, 03, 05) and
M11/09 (05 → 11) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers and the steps are the former ones, except the scenario of M11/09:
the number 05 is taken by a scenario of M11/05, it got the number 11 — the next one after the largest number of the sources of the chapter (M11/09
sc. 10; the Architect's decision 2026-10-20, ADR-0083 addendum (14) item 14; the row of `corrections-5.tsv` (historical correction record)). In total 7 scenarios / 72 steps (sc. 14 — ADR-0097 §4, there is no dry run by an implementation; the delivery of a key with the `sub` of a book and the key `role:` — by reading: the stand does not give a row with `sub` when the book is already assembled) (sc. 13 — the coverage audit of P/08, the second pass of Gemini).

<!-- original-mixed-case-paragraph -->

The assembly on all edges without a stand is checked by the vector [`assemble`](../../vectors/assemble/README.md) (cases and their provenance: the canonical package README). Sc. 02 `notes-unique` of the acceptance of M11/05 is [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) sc. 13, sc. 04 `slot-liveness` — [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md) sc. 13.

<!-- original-mixed-case-paragraph -->

Sc. 11 has people too (the former stand of the acceptance of M11/09):

<!-- original-mixed-case-paragraph -->

- steps 5, 7, 12, 13 write the grants row of `m2` as a whole and therefore repeat the row of `root`;

<!-- original-mixed-case-paragraph -->

The format is the dictionary of the «Stand» and the domain dictionary; the expectation is a subset of fields. In sc. 01 the rows of the book at the member and at the holder
are checked for the ring envelope (`~enc:v2:`) and for the absence of the value of the secret (`!contains`); the log — by reading
([P/06.2](../../../06-console/spec/06.2-console.norms.md) N1.4).

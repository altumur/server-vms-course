# Change 0125-p01-flags-writing — the writing of the daemon flags (ADR-0125 addendum (2) and the questions of «Генераторы»)

change: 0125-p01-flags-writing rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация» · state review

**Why.** The generators № 3 (flags) and № 4 (refusals) built kit B where the forms are silent
(`cammeta-status/ADR-0125-P01-вопросы-генераторов.md`, 12 questions; the door generator № 2 — the integer of a body and
Retry-After). The decisions of «Спецификация» within ADR-0125 (the Architect's word of 2026-11-04): what a form can say goes
into the form; the prose of Н1.3/Н4 says it with it. Kit choices kept: 1–5, 7, 10–12; changed: 6 (duration — the grammar,
not that of Go), 8 (addr — a non-empty host, port 1–65535), 9 (no `-id` and no `SERVER_NAME` — a start refusal), door —
Retry-After only at the connection limit.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/spec/01.3-store.norms.md` | delta: ADDED P/01.3-R031; MODIFIED P/01.3-R006, P/01.3-R029 | 7358383e394ea37ff69418176190cb7c7e294c75 | a71bedddffc2dcfecfcaae62da90ca9e24080ae4 |
| `Platform/01-store/spec/01.1-store.norms.md` | delta: ADDED P/01.1-R146 | 1fb0c1fe23451294ee7019873876a0e3105b403c | e2b1a524dc28e7e10fe377d32943c74e0e2730d8 |
| `Platform/01-store/forms/daemon-flags.tsv` | replace (header: writing, values, CEL types) | b8e18a319fcbd8a3197b7f5d96ab526d4f78e113 | 52892e4cdec063c0669bf2615be26ebc66615a41 |
| `Platform/01-store/forms/refusals.tsv` | replace (header: log, exit !0, Retry-After) | d5b87d08578543204dfee02e1c12e7dafc2028da | b141aeb854f81dbb608e01c82f2aaf9612f9e3af |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | translation of the delta | d84489112a3f2ff2a3d7748f722ae13134aa1507 | eb414cbce0908f2a9acf5a0b2d500dc537c5fb07 |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | translation of the delta | 8037de26a1d6094113dd5458fcbf22b4d8858315 | 36ef012737fda8da82502ed798be07e27ef3da8f |
| `decisions/adr-norms.tsv` | append the row of the change | — | — |

## Change map

| Place | Mark |
|---|---|
| OpenAPI P/01 (`01-store.api.openapi.yaml`) | not related: no integer field of a request body; Retry-After — the headers of 503 named there stay |
| `forms/write-checks.tsv` | agreed: it does not judge the value of `floor` (P/01.3 Н4 row 16) |
| `lifecycle.md` «Flags», «Exit codes» | agreed: the flag list and exit 2 / ≠ 0 stand |
| acceptance 1.1–1.3, vectors | not related: no step writes a flag other than by the table or a number 20.0 |
| `check_forms` | agreed: the header lines are comments |

## History

- rev 1, 2026-11-04 — «Спецификация»; the kit applied in the branch `spec/0125-flags-writing` (no delta tool yet: the result
  above is the tree of the branch).

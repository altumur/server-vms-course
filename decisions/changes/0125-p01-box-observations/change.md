# Change 0125-p01-box-observations — specify box status and metric presentation (ADR-0125)

change: 0125-p01-box-observations rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация CT 103» · state review

**Why.** The generators need the meaning of Status.max_value and the permitted presentation of the existing box metrics.
The flag table already calls -max-value the row-weight ceiling and sc. 17 already uses lowercase metric state labels.
The change makes those links explicit while retaining the choice of current-state-only versus optional zero states and
optional TYPE metadata. It adds no process, metric series or limit. Decision within ADR-0125 addendum (5), recorded by
Specification CT 103; the Architect requested the ADR-0122 bundle on 2026-11-05. Base: 286db071c4fd915df1eca1c929793f47f4c162d9.

The normative English text is [delta.md](delta.md). The branch contains the assembled future tree and its derived Russian
translation, as in the existing P/01 changes. The previous implementation/specification pins are not switched by this bundle.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/spec/01.3-store.norms.md` | delta: ADDED P/01.3-R032; MODIFIED P/01.3-R016 | a71bedddffc2dcfecfcaae62da90ca9e24080ae4 | 15069cffabba9cd3198ffa6ff5761198d37ce4e0 |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | replace: derived translation of the delta | eb414cbce0908f2a9acf5a0b2d500dc537c5fb07 | a8849d7aa35d832dbdb09a96c6ff0dec61a90148 |
| `Platform/01-store/spec/01-store.api.openapi.yaml` | replace: description at components/schemas/Status/properties/max_value; shape unchanged | 1a66a6aa85e07188c0d0881e7514593d5d97ef5c | dbe6b9a50108f5c8fc731dce55e17d14c06b883c |
| `Platform/01-store/journal/corrections-3.tsv` | append: C01-BOX-OBSERVATIONS-01 | 1e176331e1cdfc647050c4a76627f045fb902533 | 776314c65c96a6bddd6155e68168f708ed04e63b |
| `decisions/adr-norms.tsv` | append: the Specification CT 103 decision under ADR-0125 | b345eed981e4775abcf2d47f89639d98bef57ced | 2d1336ce5249614d4469d7cbe41f48c748a2d347 |
| `decisions/changes/registry.tsv` | append: this change rev 1 state review | 75a7086ca6b3dc99b095a07f18fef1c8f1455420 | 12ee05f3cbe9a4b9e4f1234d7d3b7d3f44d1b746 |

The unit delta is addressed by requirement id; the OpenAPI artifact by component/property. Blob hashes guard the complete
artifact replacements/appends. The change metadata is this change.md and delta.md; neither is its own hashed artifact.

## Change map

| Place | Mark |
|---|---|
| P/01.3 Н1.3, new R032 | changed: explicit metric presentation; lowercase current state and optional zero states, optional correctly typed metadata |
| P/01.3 Н2, R016 | changed: max_value denotes this instance's effective -max-value row-weight ceiling, not -max-body |
| OpenAPI Status.max_value | changed: description only; type and lower bound unchanged |
| Russian source mirror | changed: translation of both units in the same bundle |
| P/01.1 row weight, P/01.3 flag table and flag form | agreed: existing row/body limit meanings and default remain unchanged |
| process scenarios, vectors, data, stages and seams | agreed: bytes unchanged; sc. 17 already supplies lowercase leader/follower evidence |
| daemon/box state machine, raft and door forwarding | agreed: behavior unchanged; a non-voting door still exposes no Raft series |
| generators and runner | agreed: no new command, transport, metric series, status field or obligation to print zero states |
| Quint/model | not related: no state transition, timing or consistency change |
| journal, adr-norms, registry | changed: append the decision, provenance and rev 1 review entry |

## Validation

The author reconstructs the complete English file from the old tree by only the ADDED R032 and MODIFIED R016 operations.
The old-unit SHA-256 and every manifest base/result blob are checked. The normalization is also verified against the known
R006 hash of 0125-p01-flags-writing. Before adding this metadata, full check_spec passed with 62 exceptions; the complete
bundle is checked again. This is structural/author review, SUT0; no learner run or acceptance result is claimed.

## History

- rev 1, 2026-11-05 — branch spec103/p01-box-observations: the normative clarification and its complete ADR-0122 bundle.

# Change 0129-p01-core-clarify — P/01.1 core clarification under ADR-0129 p5

change: 0129-p01-core-clarify rev 1 · lesson P/01 (delta_base 725653954) · author Specification CT 103 · state review

Base `62751995ba14646dac48d482d5dc394ecd9a87c2`. ADR-0129 p5 accepts prose/witness clarification and rejects the proposed typed store_core profile. The normative delta modifies only R088/R090/R132; the same commit assembles that future English source and its derived Russian mirror. No producer or implementation is supplied. Report `517c1d2cd8273eb8ca04f92f4fe5a12bb405b3d9` is read-only background; its proposed class is not accepted by this change.

## Manifest

| Artifact | Operation | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/spec/01.1-store.norms.md` | replace/append | 6a6e6396fde48ca52fd60b1dadaadfcfb816b30a | b513371c2a1859b6e86b6008e374950b1ee68c41 |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | replace/append | deb03250d5147e51e9003daa2b3b02d642bfa39d | 45b0e5f3ea24a819aff8d8176a1f2ca7211414e8 |
| `Platform/01-store/acceptance/1/seams.tsv` | replace/append | 03f5a6b6ae45ec14aa99d17365a6cf1a9631e6c2 | 0ebefda02630f637d230b58c8d284ffbe462ea26 |
| `Platform/01-store/acceptance/1/README.md` | replace/append | 9ec7a5933f66a7eb99557a5090998329b4065939 | 0b6562128868b8e893973d04efb0c5a62608530a |
| `Platform/01-store/ru/acceptance/1/README.md` | replace/append | 1a1aeb48b381a49e90810c2bb3368c36ac7df95c | 643bcff4d38ea7e0aaa9c32ef7abdad7e133b0f6 |
| `Platform/01-store/forms/stages.tsv` | replace/append | a8930f21e1bf2550806b12d170ef477d2d92f7c7 | 61a2973ed9f133f06adc7591d9204f5c32d14f79 |
| `Platform/01-store/journal/corrections-1.tsv` | replace/append | 10da15185d41606041c55a25f0f8074d22c2c4c5 | 418a62969e45648d7ccb0c218b9a7da462045d57 |
| `decisions/adr-norms.tsv` | replace/append | fdc5c22a6b9a9017312c074365cb010d164615ea | b2c46c3feeb6ae9f678aa3858a34b8ed1df90ffc |
| `decisions/changes/registry.tsv` | replace/append | f1ecc4cf8c3768499a5803d8a5197e7f8c6cfe4c | f48e968cbf6054c69ba9b3b86fd72ff0c70bcd4a |
| `Platform/01-store/journal/2026-11-06-adr0129-core-clarify.md` | add | - | 211581c3a969fbcf2a48df9f95c2d8fa3dde00ad |
| `Platform/01-store/journal/2026-11-06-adr0129-core-clarify-map.tsv` | add | - | 684baff600c6a6203a58314b5bc44461c442b4e7 |
| `Platform/01-store/journal/2026-11-06-adr0129-core-clarify-preservation.json` | add | - | 44dbd2196f188391ac369032ac0c2959719207cb |

Metadata is this change.md and delta.md; they do not hash themselves. All other artifacts of the bundle, including journal maps and append-only ledgers, are listed. Exact old-unit hashes guard each modified requirement. No new req ids, removed ids, form grammar, port or public native ABI.

## Change map

| Place | Mark |
|---|---|
| N3 R088/R132 | changed: admitted metadata is retained despite zero business effects; no change to pre-admission guards or refusal codes |
| R090; existing R019 | changed fingerprint prose to name the existing binary64 domain for both bounds and exact version strings; R019 unchanged |
| R125/R131/R134 and R116 | agreed: existing list-order/set and absent-delete rules/witnesses are complete and retained |
| Acceptance/1 seams + README/mirror | changed: six additional existing-grammar scenarios; old 73 seam steps and 345 ordinary steps preserved separately |
| Stages | changed only existing gate selectors so new witnesses are reachable; parts, kit, when and all other cells unchanged |
| OpenAPI, refusal/write-check tables, data families, common contracts, other lessons | not applicable: no wire form, refusal, family, role or imported contract changes |
| Runner implementation | not changed; these existing kit seams are not runner execution claims |
| Power loss, actual version allocation, consensus | existing implementation/read obligations; no new IO witness or guessed algorithm |
| P06-related max_body source588/Englishfb | not imported or overwritten; future independent composition belongs to coord103 |

## Validation and limits

Required: exact base/req hashes and complete artifact blobs, source map reconstruction, unchanged old coverage and unrelated reqs, existing seam/stage grammar, strict check_spec baseline, test_check_forms and test_check_spec. Full normgen/KIT is a later joint on the appointed source root. No algorithm or SUT GREEN is declared. Source-state status review is an author submission, not accepted/applied by the Architect.

## Revision history

1 — initial author source bundle on 62751995ba14646dac48d482d5dc394ecd9a87c2 for the explicit ADR-0129 p5 assignment. No prior report review or runtime result is transferred to this source change.

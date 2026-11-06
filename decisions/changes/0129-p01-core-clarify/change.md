# Change 0129-p01-core-clarify — ADR-0129 source clarification

change: 0129-p01-core-clarify rev 1 · lesson P/01 (delta_base 725653954) · author Specification CT 103 · state review

Base `62751995ba14646dac48d482d5dc394ecd9a87c2`; parked ancestor `ec48a894952ac65a493cfa1aea4b81b74d1687bb`. Source-only accepted clarifications of ADR-0129 p5 and addendum (2), items 6–9,14. The rejected store_core typed profile and cancelled pilot are not introduced. Full req units and old-sha256 guards are in delta.md; all other requirement units reconstruct byte-exact. Source588 is not imported.

## Manifest

| Artifact | Operation | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/acceptance/1/README.md` | replace/append | 9ec7a5933f66a7eb99557a5090998329b4065939 | 4e5e13bbdcbfb5f4b4b524ccfe38bd9c5ead30a8 |
| `Platform/01-store/acceptance/1/seams.tsv` | replace/append | 03f5a6b6ae45ec14aa99d17365a6cf1a9631e6c2 | 5b8958ea5cd07b1727a6e98bb6071637d880f632 |
| `Platform/01-store/forms/runtime-constants.tsv` | add | - | 6848bc76497da9948a44f03f82812a57f056b988 |
| `Platform/01-store/forms/stages.tsv` | replace/append | a8930f21e1bf2550806b12d170ef477d2d92f7c7 | eee382380a53d1fba31b1f78a9ca701f971972e1 |
| `Platform/01-store/journal/corrections-1.tsv` | replace/append | 10da15185d41606041c55a25f0f8074d22c2c4c5 | 003151b212131e816e3f9230d1efbe4de1ac81f0 |
| `Platform/01-store/lifecycle.md` | replace/append | d38ca31cd4e930db0ea83b259000b5a135d30fa7 | 2c76a4a88a038174ae823f3eb3bef3a99a120ce1 |
| `Platform/01-store/ru/acceptance/1/README.md` | replace/append | 1a1aeb48b381a49e90810c2bb3368c36ac7df95c | 5d49d7848e98464df6836593ae951d1ec245283a |
| `Platform/01-store/ru/lifecycle.md` | replace/append | e90dd3e7b66a0181fce31e95e234144018fe10a1 | b74e43cf0684000cbd9b3fb5cb718c092e43a45c |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | replace/append | deb03250d5147e51e9003daa2b3b02d642bfa39d | c61edd18740fddb83b32619ef7f10b9f60e24d5f |
| `Platform/01-store/ru/spec/01.2-store.norms.md` | replace/append | 61f7163a086d62ad9df3ba40cf336e5b9a645d81 | a7cb65c17e8bb301ffb6557c59ed20899305d3cf |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | replace/append | f7acd9c139407c4dd0c3bc2f4a0fdc5e89bedc71 | 55608e7db6fa4d239a09b1d9fd232db3ddffc74b |
| `Platform/01-store/spec/01.1-store.norms.md` | replace/append | 6a6e6396fde48ca52fd60b1dadaadfcfb816b30a | 0efab0906502308d42d58ef9ae1079312717c8ad |
| `Platform/01-store/spec/01.2-store.norms.md` | replace/append | a55a1c1f9a4b0672d6967ef7790eaaeedafb6b92 | cfa75219178b067280642cebcce9ec86e17ea202 |
| `Platform/01-store/spec/01.3-store.norms.md` | replace/append | 76484a5da6970817caebd108412cab6b569dd6df | 333f31df9590bb419b32ad9793ddbf32261f6274 |
| `decisions/adr-norms.tsv` | replace/append | fdc5c22a6b9a9017312c074365cb010d164615ea | eccc49db93299317ac7a45e3e7792b825adda965 |
| `decisions/changes/registry.tsv` | replace/append | f1ecc4cf8c3768499a5803d8a5197e7f8c6cfe4c | f48e968cbf6054c69ba9b3b86fd72ff0c70bcd4a |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-clarify-map.tsv` | add | - | 684baff600c6a6203a58314b5bc44461c442b4e7 |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-clarify-preservation.json` | add | - | 44dbd2196f188391ac369032ac0c2959719207cb |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-clarify.md` | add | - | 211581c3a969fbcf2a48df9f95c2d8fa3dde00ad |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-extended-map.json` | add | - | 8d81b74347cd7499dc9adbe23f87daf8f3b7a9cf |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-extended-preservation.json` | add | - | 5a4da9d59c8217cd6a26d818b02fd75893181f82 |
| `decisions/journal/platform/01-store/2026-11-06-adr0129-core-extended.md` | add | - | 2b4ccd240a46f708706d6664aaa37cead3b1f668 |

Metadata change.md and delta.md do not hash themselves. New rows use the existing runtime-constants class; no new port, algorithm, producer or core implementation. The appendix artifacts record exact before/after source, preserved old coverage and actual stage translation, not SUT execution. Source readiness still requires review103 source-form refusal checks and coord103 joint GATE.

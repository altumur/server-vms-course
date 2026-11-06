# Change 0129-p01-v2-norms — normative source clarification

change: 0129-p01-v2-norms rev 1 · lesson P/01 (delta_base 725653954) · author Specification CT 103 · state review

Base `a635beb6a4f5c13e04034c4dc96d14a798a035a6`. Source only, no new core form, CODE, grammar, ABI, ports or SUT claim. Full changed requirement units and exact old-sha guards are in delta.md. Other requirement units reconstruct byte-exact. Current max_body schema/fixtures from the base are preserved; no historical related source is imported.

## Manifest

| Artifact | Operation | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/acceptance/1/README.md` | replace/append | 8eea9f2a5cd9b5cd0565e6231a8fd9908827ac75 | cc6001e47f38bd76bcdee190a3edd56a0d09211d |
| `Platform/01-store/acceptance/1/seams.tsv` | replace/append | 5b8958ea5cd07b1727a6e98bb6071637d880f632 | 29116434233cd64c6a573cea3d7cbfc944a961de |
| `Platform/01-store/acceptance/3/README.md` | replace/append | 7a218c15f5101936033d1e26b1c035327f8f7364 | 4605aecb805445f952c80ba156793e42332caa9f |
| `Platform/01-store/forms/runtime-constants.tsv` | replace/append | 6848bc76497da9948a44f03f82812a57f056b988 | 54a936e06939ef4e23fd14c6b134d4987d560e3a |
| `Platform/01-store/forms/stages.tsv` | replace/append | eee382380a53d1fba31b1f78a9ca701f971972e1 | 9038fb38ad54d1aec87c82b3fe714edca080c71d |
| `Platform/01-store/forms/write-checks.tsv` | replace/append | 06a0019ece5febeffbb93742ce7934119d5b8449 | b8b8a4394eaba11a20543ea06b12a354e1bdfabe |
| `Platform/01-store/lifecycle.md` | replace/append | 2c76a4a88a038174ae823f3eb3bef3a99a120ce1 | f8f945b242e04163967a5d350c06f8d2042d66b7 |
| `Platform/01-store/ru/acceptance/1/README.md` | replace/append | b0e30defd3be96cd436f2b7f8605583b3b2ac234 | 5bdfa7dd31154c3cfd36c097cf7bd6414d5818dd |
| `Platform/01-store/ru/acceptance/3/README.md` | replace/append | 37442c6dd487de391e5eed57950bd0183e7c753c | 850299e7653a8877484eab6cb247ffa17d6056cd |
| `Platform/01-store/ru/lifecycle.md` | replace/append | b74e43cf0684000cbd9b3fb5cb718c092e43a45c | 36ea007ad038b3868f6ac7b22fbb85fc6872f80d |
| `Platform/01-store/ru/spec/01-store.README.md` | replace/append | 349f6aebb0585ea5cd3ccf8211715c0f42448e93 | 11af4e40f49b4bb6c05ebea5fca8a8dfcf2be9d7 |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | replace/append | 50eab4878b677bd506410b336ac10d3f5e627258 | a63ef5da32b5559f06e540ab45e04560e1c6f15f |
| `Platform/01-store/ru/spec/01.2-store.norms.md` | replace/append | 11b0163d3df101c80e8ebaadd6e2697ad2b3058b | 146ce615d64c500e9c5eba04238a9e705ea73c36 |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | replace/append | 858a2bd0faaf3c151a89dd3f3cc6895d463fda4b | 9d0bb6e6872a382933f242e6365c840d1f60cdad |
| `Platform/01-store/spec/01-store.README.md` | replace/append | 5d435bf7edbedc46de4acc4936eb8141b28f1b0a | 5b5c08352acbb39d16b1626ffe97527253f4d4da |
| `Platform/01-store/spec/01.1-store.norms.md` | replace/append | ad315db8d1f144aad746c17e67188e65d522f494 | 30946b8464df2233978a5ded6f699e1c15ba278a |
| `Platform/01-store/spec/01.2-store.norms.md` | replace/append | d43ea60ceefb911166454b56e60d49be9709419c | b1f66117d7c66875f3450b34968a425f0acb3277 |
| `Platform/01-store/spec/01.3-store.norms.md` | replace/append | f6365421248a5e2194fc67db7f81ddf58e6751fe | b47a2f025ef46fd272e26100ea2a31099e27338e |
| `Platform/common/contracts/store-client.md` | replace/append | 75cded35e73ce74526570e1feb73468a5d674a38 | b55e7051adf96b7079dd0c84b9cf1156dc6bf4ea |
| `Platform/common/ru/contracts/store-client.md` | replace/append | 732384bd3b89ba3a83580f0b051c669dbfda52c2 | e60d829b5a9a04c2f091a26524c6e10e63897637 |
| `decisions/adr-norms.tsv` | replace/append | 1f5437c423770269ac33c28c3404fe66d1b92361 | 57d01a8c51e9b3ecc3315bd1fc7281e2f8a3379d |
| `decisions/changes/registry.tsv` | replace/append | f48e968cbf6054c69ba9b3b86fd72ff0c70bcd4a | bd033bcf2adee4efd8a1d5bf60e6e947fcd5425f |
| `decisions/journal/platform/01-store/2026-11-06-p01-v2-constant-equalities.json` | add | - | 634541770cdb7f3d91dfaa7dd47198db300be6ce |
| `decisions/journal/platform/01-store/2026-11-06-p01-v2-preservation.json` | add | - | ba563022c5fc944b913212a5514def1565b6cb7e |
| `decisions/journal/platform/01-store/2026-11-06-p01-v2-source-map.json` | add | - | 72f509d9988111747e93e78ce30122745f682724 |
| `decisions/journal/platform/01-store/2026-11-06-p01-v2-source.md` | add | - | 2047d47b41b510d6910c03a448853cfd37a6c59b |
| `decisions/journal/platform/01-store/corrections-1.tsv` | replace/append | 003151b212131e816e3f9230d1efbe4de1ac81f0 | 176da56e01a43013f6b4be04fe9d80493f753d01 |

Metadata change.md and delta.md do not hash themselves. Equality/source maps carry file SHA values; the final external READY receipt supplies the author commit. New judges only review103 through coord103.

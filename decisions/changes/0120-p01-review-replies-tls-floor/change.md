# Change 0120-p01-review-replies-tls-floor — review of lesson P/01

change: 0120-p01-review-replies-tls-floor rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация CT 103» · state review

The Architect's decisions on the Codex lesson review (ADR-0120, main d68286f29). S1 narrows stable refusal to expired and makes same-id rechecking explicit. S2 reconciles local loopback/TLS/group startup and its CEL form. S3 excludes the input floor from Transfer, retains the first new F1 row on continuation and makes completeness explicit. M1 restores the ordinary meaning of exit !0.

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/acceptance/1/seams.tsv` | replace/append by named field, stage or scenario; translated prose | 46c4bcf43ed0db6031c316fc479f67d39aa784b5 | 03f5a6b6ae45ec14aa99d17365a6cf1a9631e6c2 |
| `Platform/01-store/acceptance/3/README.md` | replace/append by named field, stage or scenario; translated prose | af3f111fa74eab226d2b837ccbbaf1e57f46a128 | e63b89f49df471859f3ed9162f02ec2e4142e059 |
| `Platform/01-store/forms/daemon-flags.tsv` | replace/append by named field, stage or scenario; translated prose | 52892e4cdec063c0669bf2615be26ebc66615a41 | 867d69917337db78427d14bb19ecdd907890bf76 |
| `Platform/01-store/forms/refusals.tsv` | replace/append by named field, stage or scenario; translated prose | b141aeb854f81dbb608e01c82f2aaf9612f9e3af | 11dc6dc363a9441396156a43817a6cdb74df9102 |
| `Platform/01-store/forms/stages.tsv` | replace/append by named field, stage or scenario; translated prose | a78561456993e960fd16d2c83a751d988f1b9e23 | deba0a9d388ad1e7697f53fc6db16558ef55d545 |
| `Platform/01-store/ru/acceptance/3/README.md` | replace/append by named field, stage or scenario; translated prose | bdf8e3924c71abedd2dd6a70284ae679dbf19c05 | 027b8eaef9844c2275951ae8d25830f9aefe906f |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | replace/append by named field, stage or scenario; translated prose | b1a4cf98d94c98bd278226e5d867303cbd28207d | 3ff7da1849b2ee4d02c2b5ee4a0f06a9620bcb6c |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | replace/append by named field, stage or scenario; translated prose | a8849d7aa35d832dbdb09a96c6ff0dec61a90148 | cfe2fb20ff6c822430a9b485ed416dd4b5f674fd |
| `Platform/01-store/spec/01.1-store.norms.md` | delta: R088 | 01698afcaef92161757e3ef4f574db2fdbe6cf69 | f4c78df2b03008fb111aa5093e9c3f33e05d3ec3 |
| `Platform/01-store/spec/01.3-store.norms.md` | delta: R006,R007,R011,R026 | 15069cffabba9cd3198ffa6ff5761198d37ce4e0 | 67e68a385e1663209d28ccf0017386328316c3cd |
| `decisions/adr-norms.tsv` | replace/append by named field, stage or scenario; translated prose | 1ae56d089f1f47658289ff3fdfdce85e9c3eba65 | 447f070de0cb7aebd334030b9d6c1f72d74854aa |
| `decisions/changes/registry.tsv` | replace/append by named field, stage or scenario; translated prose | 12ee05f3cbe9a4b9e4f1234d7d3b7d3f44d1b746 | f1ecc4cf8c3768499a5803d8a5197e7f8c6cfe4c |
| `Platform/01-store/acceptance/3/seams.tsv` | add: ordinary implementation CALL seams | - | 86f3e1506faa278b3c85f156b3e8910ae03b3223 |

The delta is addressed by five existing req ids; forms by flag/stage/comment and seams by scenario. English source and derived Russian translation are changed together. The registry and adr-norms are append-only. The manifest excludes its own change/delta metadata. No OpenAPI shape, data family, ordinary scenario, public runner target or implementation is changed. Built families/form/canonical blocks are untouched.

## Validation

Author checks require exact old-unit hashes, complete artifact blobs, unchanged other req units, same-id early retry, startup CEL and four seam JSONs. The author course GATE passed with 62 exceptions, exit 0; the changed five req units, all 13 base/result artifact blobs, unchanged built blocks and ordinary scenarios were checked. The exact same id is present at both early and retry steps. This is a normative correction and test assistance, not SUT acceptance.

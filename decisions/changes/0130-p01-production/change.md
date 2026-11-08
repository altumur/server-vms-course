# Change 0130-p01-production — production contract

change: 0130-p01-production rev 1 · lesson P/01 · author spec103 · state review

Base `2a63643ff3f338972dda9ec32231089ad38e66ea`; authority c132, mandatory TEXT condition6cd2 satisfied. Complete Source-only change within D1-D7. No implementation core, new profile grammar, port, unknown numeric budget, old41/KIT adoption or runtime claim. Metadata state review is not accepted/applied.

## Manifest

| Artifact | Operation | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/acceptance/1/README.md` | modify | 317dd515b35e77d57d1d0f69ee513c138817e0d7 | 872091430e3bcc69c89dbd24dda6eefaa84aa770 |
| `Platform/01-store/acceptance/3/README.md` | modify | c51bad1b703d17b5156eea7f93f5b9abe618b118 | c8d1b63663671aa8120783a4122c87bf50378900 |
| `Platform/01-store/spec/production-acceptance.md` | add | - | c4b61b4a09d5da0d42d8334281d9685e34f7c705 |
| `Platform/01-store/forms/refusals.tsv` | modify | 30fba6085f48b450ac9279beadb659d8425615a2 | 9b5a671deb0872b15dd0b617ed426390f9a38271 |
| `Platform/01-store/forms/stages.tsv` | modify | 9038fb38ad54d1aec87c82b3fe714edca080c71d | f7d320fd294defd6846cf59baf56a2dccbc5036c |
| `Platform/01-store/lifecycle.md` | modify | f8f945b242e04163967a5d350c06f8d2042d66b7 | 50ba8dd284f5fc53117dc027ce592ca71593ca6d |
| `Platform/01-store/ru/acceptance/1/README.md` | modify | 47749d58ba6637d269705bef690e6bd43f69156e | 0a8cbaf1a1849ca31b5e63b849625607e002c862 |
| `Platform/01-store/ru/acceptance/3/README.md` | modify | 16e0562b8fce7b5104929f73228510370ec35430 | 283949c6ab9dad6c87cf1de7632900e3fef2f658 |
| `Platform/01-store/ru/spec/production-acceptance.md` | add | - | bf0e72f4a7c4294c10e4af7b73389e40df04f437 |
| `Platform/01-store/ru/lifecycle.md` | modify | 36ea007ad038b3868f6ac7b22fbb85fc6872f80d | 82aae873f9b5259fd082b2cfc5cde6300c3c54c6 |
| `Platform/01-store/ru/spec/01-store.README.md` | modify | 11af4e40f49b4bb6c05ebea5fca8a8dfcf2be9d7 | 8d7fc012ed541224f5f1fe5a1f6e0863f5c32f0a |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | modify | d2ee84e0e24ec21c64824e9862702fdbe78d31fb | b166e8f5140ac60f46c0de3a3a37b8d7488332ef |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | modify | 9d0bb6e6872a382933f242e6365c840d1f60cdad | d8b1943f8cd820a981ea1b59010235398eb82658 |
| `Platform/01-store/spec/01-store.README.md` | modify | 5b5c08352acbb39d16b1626ffe97527253f4d4da | db057a377fe800dafc67aeeb93c1246b2cbcdacb |
| `Platform/01-store/spec/01-store.api.openapi.yaml` | modify | 6fbb6e329927fab4eb38d330ef74ebaf3bc2ac67 | 7149a6fa1d615cd04b3ddabdfdbcec0dc974b3b9 |
| `Platform/01-store/spec/01.1-store.norms.md` | modify | 2375adc37f4af9889d2d8538288ffca080526e11 | 350c18128044a6a184a4dd63ab0a5cda8cb2f2bf |
| `Platform/01-store/spec/01.3-store.norms.md` | modify | b47a2f025ef46fd272e26100ea2a31099e27338e | 2b5c8c11df1111fb90aceca08a57ee0d65866623 |
| `Platform/05-resource/ru/spec/05-resource.norms.md` | modify | 6cfc02a3b09f9cc4134cf0414e1aa7ddc1e81c6a | 086d5b0ead2ecf9e7a7b943ffdc96b3e7e21aaca |
| `Platform/05-resource/spec/05-resource.norms.md` | modify | 715c5c397c4229bfbdeeea8136f4361e58068326 | 3a27d3494c458d0fb193a64f59fd57b3c27b1bfd |
| `Platform/common/contracts/gate-and-pass.md` | modify | cf9933ebb84566b4832c3eb77798329e8a3f72c6 | 231ac57650f5f38ff3cde2807c249164371ef690 |
| `Platform/common/ru/contracts/gate-and-pass.md` | modify | fa4acaf86c5a41739954181dce3797f7fb5199a4 | 45bfab781d31ad49a13123bfdc6014d21ef41952 |
| `decisions/history/platform/id-map.tsv` | modify | e71531ce31c4743c6c057f7780bae1359eb55a3b | 0a55a56268cbfbfd39cb0f97cfb016349223cb83 |
| `decisions/changes/registry.tsv` | modify | 81f139a2f453e95ba6c109ab68fa7fc6617601db | 39533e715089bd3c45e7997cdac9f85e21dc0ec0 |
| `decisions/adr-norms.tsv` | modify | e8de958c05148a602048e253fad17ea1a47e84f2 | 7c7f1afcbc07bb5f61012d2243360695827beb35 |
| `decisions/adr-pipeline.tsv` | modify | cc80994a7ca3c0b038e9d1bfb69952266dbb6c66 | 2fc164d7e6cd3212edb686bdd2f098bc5ad3f9f7 |
| `decisions/journal/platform/01-store/corrections-1.tsv` | modify | 176da56e01a43013f6b4be04fe9d80493f753d01 | 6ac872574b924b52c23f37d377c4361f1781ce22 |
| `decisions/journal/platform/01-store/corrections-3.tsv` | modify | 7882c113735ba38e2bee7bc156c7c47bb628acc1 | 59c28327758c8687eca33d241ff873e9ad743fd6 |
| `decisions/journal/platform/01-store/2026-11-08-z21-source-map.json` | add | - | 39eab1636b6d5bc516b2697a4d1493a09e18ac98 |
| `decisions/journal/platform/01-store/2026-11-08-z21-preservation.json` | add | - | ab78051bcb593b76d8c456e9af6081e01a24189a |
| `decisions/journal/platform/01-store/2026-11-08-z21-source.md` | add | - | 8ba43721312473a56089c955b64ce48bd2b9fb41 |
| `decisions/inbox/2026-11-08-З21-D1-D7-исполнение.md` | add | - | 8ba43721312473a56089c955b64ce48bd2b9fb41 |
| `ХОД-Спецификация.md` | modify | 4008e899d7c0be98c56eddc8ba7f51bc3817c905 | d856fcf527e28b13e6e4ba074a82ed9776b6eae0 |

The full requirement bodies and normalized old-sha guards are in delta.md. Unmarked implementation/checklist/header/lifecycle/coverage blocks remain explicit raw source-map artifacts. change.md/delta.md do not hash themselves; the external final receipt pins the author commit and every payload. Source checks, runner fixture controls and actual SUT qualification remain separate.

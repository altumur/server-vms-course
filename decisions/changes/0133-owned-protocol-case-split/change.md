# Change 0133-owned-protocol-case-split

change: 0133-owned-protocol-case-split rev 1 · lessons Platform/common,P/04 · author spec103 · state review

Publication parent `93a7f154c9e3c0e165bc9600b7617685239776c6`. ADR-0133 addenda 1 and 4: four mixed protocol README paragraphs (order, shrink-victim, shrink-allowed, journal) in both languages keep their generic rules; only named-input-to-outcome associations move to eight adjacent judge-only `README.cases.md` files. Rules for no_victim precedence and places.wanted protection are in P/04 N3 (shrink). No new norm, number, field or requirement ID.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/04-controller/ru/vectors/order/README.cases.md` | ADDED | - | 6c007bb21b941c114262364f12f877db234e151e | f69fc9bd8ecedef1b5d415c81109ca3251114e8e96c47cd0550cda21ad06fbc4 |
| `Platform/04-controller/ru/vectors/order/README.md` | MODIFIED | 76bbb8998c2f6f520efd26a3033d1c17aee29fe0 | 7acc78b16f329f686f141d64f351050aae4c2ebb | 85dc0f4e0f992e5439c8fcbb09886a4d3df1ee40eb8b856aafaca1e4ac91bbe1 |
| `Platform/04-controller/ru/vectors/shrink-allowed/README.cases.md` | ADDED | - | c9ef21a9ad6f3d94c6b49eed14c3d40e433fa14a | f335856ba9e62a3f3011220910cb6c1ab63a80fc97e95a980dc228aa6cb29ea0 |
| `Platform/04-controller/ru/vectors/shrink-allowed/README.md` | MODIFIED | 1eaee1f019d4df0fe82531d48c90f7641a580d42 | 5af893a6bcb97030c2eb645f1fc9b9cd30556037 | 051aad80ad4059793290f452be72cfa31695c890494cf809da8ae01862f7ab54 |
| `Platform/04-controller/ru/vectors/shrink-victim/README.cases.md` | ADDED | - | 558e9bd1d689b03cc739ca5d6ec71c00388c6a33 | 9429b0429d8d3c416fc5924807fe97a4a32014f4c90d4b4cb2dbfa964dc5b503 |
| `Platform/04-controller/ru/vectors/shrink-victim/README.md` | MODIFIED | e8cdc9bd3cddaf66bfd4a25fa2e2ddfd558df34f | 01eef970490a688347389ae66452eed59c21c541 | 5d09e3b11ea874091173d2db41b3b81f5e93bd9fd8c6b942063b1ce47c934478 |
| `Platform/04-controller/vectors/order/README.cases.md` | ADDED | - | be2658216b7a9da4c973e424bc8a4003243d48c6 | dc7df72fc40c808629c768ef00e9648bbdd68971e79542f7fef39f86afc5ca3e |
| `Platform/04-controller/vectors/order/README.md` | MODIFIED | b4ebe41456b74f44b78f4ed4a372347778bf19c8 | 61d9df1d0a0485d41c978106fc7f4cfb66b045df | 5cb720000612d1e496e8d73bdd19d6cbbbaf6914fe550c30bc862fb8155283f0 |
| `Platform/04-controller/vectors/shrink-allowed/README.cases.md` | ADDED | - | 4e51585acb39250033663fc2008a2e136d1d470d | 011beee54494c1ee0ec63aa666bba2714ed35f62128650ae4027341a1663f93e |
| `Platform/04-controller/vectors/shrink-allowed/README.md` | MODIFIED | 27caaa9a207a69fa010e7b8cde0cc1130ee41087 | 6148d7389756aaf875b2d78edcf9cf796836d161 | 8eefcfc02a0957fafc49036d9150ddb217e43d593c077400f50430df54fc0e23 |
| `Platform/04-controller/vectors/shrink-victim/README.cases.md` | ADDED | - | 35dcb46e2907c444192f2c5b7383eaf33e8c9117 | 57964e69a85bfec2b2e5c21aba6dcd49500bd82de50e8e8c0b44eba8fa118143 |
| `Platform/04-controller/vectors/shrink-victim/README.md` | MODIFIED | 212ac705e3fbdf794754d0dd4e07aa0c55270d01 | 5c8c4f3db26a4c8a51b8a4263e60c7bd177deff6 | 43f3ab35cd94806d2f4d85f1a544fe8e7ea0b68f21453f2445eb51fd9e898474 |
| `Platform/common/ru/vectors/journal/README.cases.md` | ADDED | - | 4a3543a427f7935e20f2bbbbbcfa3dcd43ae96c5 | c2f96322711840b09c9e45dacbd1f8f6ffb7657acfea62de234254df7995ae07 |
| `Platform/common/ru/vectors/journal/README.md` | MODIFIED | 938a26ec75dac5dce5318dcc07291b907e98ac07 | f2979af9b04ed8c6f635f0bf9b56a1220510101c | d32481605c81d57e7f6f7539200de554eed47d8128d9deb36861f9c4cb65e10f |
| `Platform/common/vectors/journal/README.cases.md` | ADDED | - | 618f1c08b27f09b01866823ad849737a24769509 | 9a73739dfcacee2a198fa828ca5ee850bafdd97c3781cedcfb727752d4a0efc9 |
| `Platform/common/vectors/journal/README.md` | MODIFIED | c4d1d1d5a1bde1d61edcfefd753342693d6c6bf9 | b9210554dc88fcdfc2d862dd5b1814b8e6d4b1d9 | 2f55511814dbf9b3f9851f3594f37c2db820f00c7e8a2fed2500b5313410ce14 |

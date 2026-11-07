# Change 0129-z10-p01-time — source B current contracts

change: 0129-z10-p01-time rev 1 · lesson P/01 · delta_base 725653954 · author spec103 · state review

Base `854681a2fcd1db12ff7db8127feee977f62be6b6`. Authority [ADR-0129](../../0129-минимум-догадок-генератор-не-больше-кода.md), addenda(23) and pre-existing B29(11), SOURCE-B8f21 plus mirrord267. This complete source component has68 source,7 append-only auxiliary and12 metadata paths. All87 artifacts are listed below; the shared manifest provides exact literal/JSON/row/cell coordinates and final hashes. No new form, class, alias, role, command or port.

## Complete artifact manifest

| Artifact | Operation | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/ru/spec/01.1-store.norms.md` | modify | d2ee84e0e24ec21c64824e9862702fdbe78d31fb | 2470c4eaa0e48d87ad43214552db46432be5613c |
| `Platform/01-store/spec/01.1-store.norms.md` | modify | 2375adc37f4af9889d2d8538288ffca080526e11 | 9f03d625f2e76f0afd771cc17d79f167ac545afc |
| `Platform/02-installer/data/canonical-row.outcomes.tsv` | modify | 9dd6b370c80e14c4625900c22c8ff17900f4b8ca | f3fa5d0d387cd372f259285e83d20964edd1ae8d |
| `Platform/02-installer/data/canonical-row.schema.json` | modify | 9f6a32954c5612f0d6298618725b6ff1407db001 | 96ae1b288e4a109f50b450408444ebbc9109c3ec |
| `Platform/02-installer/data/manifest-file.schema.json` | modify | 13c58b344bd9ae50ab2bcb892985edef545a4313 | 040e668539cc714299cce085090267e026caa788 |
| `Platform/02-installer/data/manifest-rev.schema.json` | modify | b5236d81a31cfdd113d040e48c3e346fcd112f51 | 79dc0861b072d99ba2f5a64e71ce43a00f652cfa |
| `Platform/02-installer/data/manifest-row.schema.json` | modify | de9af59373acd548a79f9fab670023ddf03800f2 | a3125b9fb2af88fce8b502b755a61b2e5d3c2fe8 |
| `Platform/02-installer/forms/refusals.tsv` | modify | c4a6492a9697d3f0105baee15ae3e66df3b23d94 | a487ff28c24b49bfe1d8b75f54a5ce2827e68661 |
| `Platform/02-installer/ru/spec/02.2-installer.norms.md` | modify | cb01347287dd6be659ecb45e50754c0b7103f241 | 5211f67a1c117b467eb59828a3b074908611f1d4 |
| `Platform/02-installer/ru/spec/02.3-installer.norms.md` | modify | b10a09e577c6e226b5750f2023fabadf38b1fed6 | 5774cad800f9818c12507958791dcd3e05216ff5 |
| `Platform/02-installer/ru/spec/02.4-installer.norms.md` | modify | 87259ae93b721f9867037c2f994b6c688dd5c5f6 | 51c9bd367b382c3dbfaeff8f5cfb25d795b5a6a8 |
| `Platform/02-installer/spec/02.2-installer.norms.md` | modify | 409129a9ffdc96c8a47e944c2d1385b662105509 | ce2659ecc6286105d16454eafa8a8b2b9fc07e81 |
| `Platform/02-installer/spec/02.2-installer.view.schema.json` | modify | 5e3543e9469f84c4c2472d374a44655666fc94c2 | aebeed8a4ac98c29fa2aa7296d96b410c369260f |
| `Platform/02-installer/spec/02.3-installer.norms.md` | modify | b29d94bd368e22ee5947ef8762794b828fcb70c1 | b7a24e1e29201ab5d158bbaa191c12e0887481e6 |
| `Platform/02-installer/spec/02.4-installer.norms.md` | modify | 95826c4c2e73e05686a5e1492dff2c7fdc367668 | 83d9ce52812a6810b6872d171ba39d8bbcc81d19 |
| `Platform/03-worker/ru/spec/03.2-worker.norms.md` | modify | 77fca87f59e8aa19570244d78ebc81812caee63f | 36000214db5328a585d84cc92506fb9402cb7eb6 |
| `Platform/03-worker/ru/spec/03.4-worker.norms.md` | modify | e5968e95dfcc7d151a4253128205715a43333b13 | 2fd2dd3ab991cd4c2792c413d85885531b4fdc38 |
| `Platform/03-worker/spec/03.2-worker.norms.md` | modify | 9977c68db36e0e6d91adebb61f38c3d31945945f | f909c734e93a1d1adb60ab7626b18fe96f3a1670 |
| `Platform/03-worker/spec/03.4-worker.norms.md` | modify | 57b7bea8c99294f8237c829bd43957737fedcbd6 | 5298e1f654e4d10379b267d315dc197f47ab4e55 |
| `Platform/06-console/data/operations.layers.tsv` | modify | 64511449010ecb5f2583d242ca40e6d2001413f5 | ac34f79011048c6e38c117824c44881d237435a7 |
| `Platform/06-console/data/operations.schema.json` | modify | 947d51ab22864046cba475a6f3d07845307473bf | 03a0f41cb6dd883e27b1a32c0f1358bb621b9c16 |
| `Platform/06-console/ru/spec/06.1-console.norms.md` | modify | 57d83655976da6408cf259fabc426674f14c294f | 9b67dd1108cdcdaf175e86353ed49a201234a0fd |
| `Platform/06-console/ru/spec/06.9-console.norms.md` | modify | d2ce562470e0e3d4078a5ed597c7da4212906121 | 24827c73307f78bbf6542a02083e1b3fc7e1d24b |
| `Platform/06-console/spec/06.1-console.norms.md` | modify | 1726edc1661c5636bed5d9dd6c12bd3e1047efd5 | b2b47751bd9f5aff27835b28125eaaf48a9074e6 |
| `Platform/06-console/spec/06.9-console.norms.md` | modify | 1ec16d2b64472050a9ff1d757855635f2d586cda | dde642f9a6245c175ec45ca098e4a981bbaf15c0 |
| `Platform/08-domain/data/issued.layers.tsv` | modify | 75cd6f1f6018b335a4599a3fbc3608f712916e9d | e3cfeb4588163a33eab53f494056770841fb509a |
| `Platform/08-domain/data/issued.schema.json` | modify | 380bee7143b27ce3544e20bd005e9119b324356e | 6f9d9f03b694467c15b93417b812545ebbb7295b |
| `Platform/08-domain/ru/spec/08.2-domain.norms.md` | modify | 43db95948b81c1baf160a40a49b21ae7bddf14f7 | 585b85fc4094497b6293d1b13ed88c16e5bd025e |
| `Platform/08-domain/spec/08.2-domain.norms.md` | modify | 1e4ec131d9a06b819b9b5217b166286656639086 | 5c4c1a429a1fa565ba7d4a1891c8df37e7eb68c9 |
| `Platform/common/contracts/event-journal.md` | modify | bd1c6cbbcc110919578a4a33ec97eac5d3e021fd | 407b96d74b79f8e8557e9d8c7a3afb6835a2c270 |
| `Platform/common/contracts/holds.md` | modify | 4e36e27ec8566438515881431e10779a7f66caef | 42557f80f6affa12b05cc997cfa0d135785baab7 |
| `Platform/common/contracts/record.md` | modify | 02378d3ab245e6052fcf4b44d3d9055c92cd2d3c | 43435e26287d942a8a11d5395d4c24d9c11dc59c |
| `Platform/common/contracts/schema.md` | modify | 3a1c18449fd84cf51f36d3c1ccf1df15a97c8eaa | a0ff02212a4dbf3d8cb08728d8f9bc497e24d7b9 |
| `Platform/common/data/README.md` | modify | e4470550093740a98abba49f08e676bbd8214b61 | bb2d6fa4182f0c967968a6b138b2cda21884ee6e |
| `Platform/common/data/catalog.tsv` | modify | e7952ff41e9d02c9d1cb50d57b4362f57ede3e08 | 7a0318c30764738c31b8f4c5808b14d7fbc6ca08 |
| `Platform/common/data/codec.tsv` | modify | 15a311ea85309baee10de7538466ac16fb2c8751 | d5ab25b2e48f73655a55d2057cc48a2fdc75a19f |
| `Platform/common/data/key-placeholders.tsv` | modify | e7c58d4f0adbcd61ae5d10cc4c96683c75839879 | 2609981e7d98ea992c47ee16cbf4ba87dde61517 |
| `Platform/common/ru/contracts/event-journal.md` | modify | 08ba379852cfbe1a4d21bd1b146e293f8c509a87 | 1949097399b1c0303d582fa419ca86381add51b0 |
| `Platform/common/ru/contracts/holds.md` | modify | a256d5529d3b6d9c99b748d83f3a88f9004fb3fa | 6a7d99ce6117840fb4187ebc5ef5589f142383e9 |
| `Platform/common/ru/contracts/record.md` | modify | f597138ad017729d75f5b09cc94f5645697674ee | db9be14e9a81546578ac886dc285b1279c1f1bf4 |
| `Platform/common/ru/contracts/schema.md` | modify | 15798d8d9ca95676ef81fc78307ab3069faa32f9 | 78d96b1b1bb0751f945b1fcb1f364533c2d7e3a6 |
| `Platform/common/ru/data/README.md` | modify | 5e7ddf4ae70ff09b5bcc4a82d8b2c2e207d4572a | db617e6e86c051b989f90b4d14e36ab2088b8af3 |
| `Platform/common/ru/vectors/heartbeat-read/README.md` | modify | b856bbd29cca6c360ed26fc01966668dc23a365b | 9657a8e39b73c74c91f7fad0d53ca7fd3e0576e2 |
| `Platform/common/ru/vectors/holds/README.md` | modify | a5202a598f94d1fe15d9639bdd3da6d1408ae3c7 | 8551cd921260ae9be15e1685110614db755942fb |
| `Platform/common/ru/vectors/may/README.md` | modify | 10593d5c44ab83a5886b41cf6e93e0066e94791b | c1e3dc8e63f288dfe86b362e63640b65b4e93979 |
| `Platform/common/ru/vectors/record/README.md` | modify | 81b16a09189d35e66c7ba91f07ca7ec9532d4e28 | c5b72eb9ca51c2dff4077dfe82a148360e29f8dd |
| `Platform/common/ru/vectors/schema/README.md` | modify | f99c32ce9895123bd86c11d0b1ed2b3c4d482815 | 7c22eb2073d50fc9c21a5cbe51839c170378fd73 |
| `Platform/common/vectors/family-read/01.tsv` | modify | fb868b012d74c8e2b31990fb62b8ee6183b03f13 | 593c0d8f17dcba1e70ad241495aaeee3d836d791 |
| `Platform/common/vectors/family-read/02.tsv` | modify | 61b5d7850c89e709f31f916e69e3861c79218cd2 | 021e69eabf68480b5e44b90b225d56ce459dbbb4 |
| `Platform/common/vectors/family-read/03.tsv` | modify | cb985d60cfcf44bf49a38e90f73e7d9c7f0cd9ca | 0ec20ec67438573268d064d8242adc8ab4418cda |
| `Platform/common/vectors/family-read/04.tsv` | modify | bdd12dbba2d754fc63e6d43eb43c4ac2a77526cd | 76caf8490bd91783cff86fa7eb8b79fc43116aff |
| `Platform/common/vectors/family-read/05.tsv` | modify | b0ee4db438457255b16f64f5648911b79a57e22b | ded44c76a80ce47cb1a823060e4a39e186a1c3e4 |
| `Platform/common/vectors/family-read/06.tsv` | modify | 109b532fa5be5e77e3818c81446a3d83b473c1d9 | d95f0d721b6d6a83312b4af30e6ceba1814154f7 |
| `Platform/common/vectors/family-read/08.tsv` | modify | b6dc4c72c6016d85620aa375b524189851049adf | de29f3cc954966d030549c3cf5948047fc924762 |
| `Platform/common/vectors/family-read/09.tsv` | modify | 8a02ef2c17893de8670b780eeb208e1add032a44 | 59ff4308ec2447f5ef24129c3dcf15d7c3803979 |
| `Platform/common/vectors/heartbeat-read/README.md` | modify | 15b92056e0fe3b0d648a406f5d821dd4c2836d82 | cc9e2d585ac655bb4e77c591a6baf06fb64de202 |
| `Platform/common/vectors/heartbeat-read/cases.tsv` | modify | 123bb11327e5320252c782996f9cba683efb2d29 | e5808bd6b5091bae2b198b064f30516881f6602f |
| `Platform/common/vectors/heartbeat-read/worker.tsv` | modify | 7dea3ca02ed48ba8a98e6765c2944b85dbaca169 | 3c52557feacb049b7bb0ead329f630d2600ad1e3 |
| `Platform/common/vectors/holds/README.md` | modify | 1ca98f08608bce99f7178a9bbb1f93a3aae81c92 | 68b205e8fd8478b5230becfbcaf7e5cf24dd5257 |
| `Platform/common/vectors/holds/cases.tsv` | modify | 8e0770d8671547e8feeb10f7c0748d0d9f03404f | f8d4392c874e1270dfe41679617646446b82f0d6 |
| `Platform/common/vectors/journal/bucket.tsv` | modify | 6adde2557d2b8493f4f976eea9c4aa45783358cc | 22ead137e768f969cd7de69bd78dc387719e8102 |
| `Platform/common/vectors/may/README.md` | modify | 7a3432af74e78ae517995eccf15216c9482f3aaa | de005a3dd96847b8e2d3253280f96b7cd8ffd043 |
| `Platform/common/vectors/may/cases.tsv` | modify | 35a4989d1ace30f452ed04e36a74569f1658cb8b | 25aad873e8902222cb8eae79bbfc6bfecb3c0ff6 |
| `Platform/common/vectors/record/README.md` | modify | 302955030326a6d2d15a519c812bc4f45db8aa25 | a943852a67f85fb1a863eed5c83705e3cdec1a28 |
| `Platform/common/vectors/record/cases.tsv` | modify | 94b91d6e09e992860f76c21f95263f5eebc5c8fd | efa3df8230a33b6177b80586bb38a32c365364c9 |
| `Platform/common/vectors/schema/README.md` | modify | e37f59103d0ed8f9e31910ff4d3b11a0d40e7f1d | 95757704b304a539e4b1fbac9e152a08cc110f0b |
| `Platform/common/vectors/schema/cases.tsv` | modify | 42bebc7475103ece1b4bb5d6e709fb445f19b9b3 | 30b61fb54d35cc91e670fa6ece666db3a9fe9f4a |
| `Platform/module-design.md` | modify | 61558f54acfd9315212237a30b3877f5e3f89e75 | e84d96c5f079310f05533fe6aa7690ec575c3de6 |
| `decisions/changes/registry.tsv` | append | 7ff8126f8557c59d79727c011940b4133a8bc4cf | bd89f0fb393935ec01f98f6478890ab48bb28047 |
| `decisions/adr-norms.tsv` | append | 1431361e8bbfb9a3a2b3d7aec8f7e4f9b8951528 | 2f1dd364629f7055e7fcb3e2e05f243cfc5b7cba |
| `decisions/journal/platform/01-store/corrections-3.tsv` | append | ebb5fd9c41d711149693692f0b51be13dd5fbf4e | 8f25e90fa0d2c86d1fb8c476a77ae5a76003f044 |
| `decisions/journal/platform/02-installer/corrections-5.tsv` | append | 941a57e19b02596004ffdde096e888651628cbe2 | 1d8df2ad03ccd3e49725c739d96ce0ae103126dc |
| `decisions/journal/platform/03-worker/corrections-7.tsv` | append | 633e69840ebdf3b63b5756c2dc4ed58377b594eb | bd8832b1e068edcdcf6350af252db744e1d3bb44 |
| `decisions/journal/platform/06-console/corrections-9.tsv` | append | 422686305620233002fe69af430323c96a891420 | f59a57114b33052e745d8efbff0a0fae03550690 |
| `decisions/journal/platform/08-domain/corrections-10.tsv` | append | 8fa1e5a8a4a22683a43e6b85094be53e888c0614 | 24328e476ebfa625dd565f5187a13938ef42578a |
| `decisions/changes/0129-z10-p01-time/delta.md` | add | - | a48799f8c70e09beee9d896db0d718c45aa82054 |
| `decisions/changes/0129-z10-p01-time/change.md` | add | - | external final FREEZE (mutual/self hash) |
| `decisions/changes/0129-z10-p01-time/source-map.json` | add | - | a0cc75caa46fa9d66ff86706f43f3a03c9b4312c |
| `decisions/changes/0129-z10-p01-time/corpus-map.json` | add | - | d11b4643b30ace99fe5864ede8efe2c7c71bb506 |
| `decisions/changes/0129-z10-p01-time/preservation.json` | add | - | 9503256757d675ab73c7c36555fc4529cc3f652e |
| `decisions/changes/0129-z10-p01-time/history.md` | add | - | c47abce6517ad8bc16192d177eac4a0ebafe66c6 |
| `decisions/inbox/2026-11-07-z10-current-source-b/REPORT.md` | add | - | external final FREEZE (mutual/self hash) |
| `decisions/inbox/2026-11-07-z10-current-source-b/source-map.json` | add | - | cbe26ed5c56d4f66b090075faab2accbc9b0f1fe |
| `decisions/inbox/2026-11-07-z10-current-source-b/corpus-map.json` | add | - | 59cbe4e50cc5b8e60964b42d417d7de46819ef3b |
| `decisions/inbox/2026-11-07-z10-current-source-b/ownership-map.json` | add | - | 4a593714adc28ffe786d502a110759cdb2e3f4f1 |
| `decisions/inbox/2026-11-07-z10-current-source-b/preservation.json` | add | - | a4e901da327cd9213443dc2be51c4a60657275f3 |
| `decisions/inbox/2026-11-07-z10-current-source-b/history.md` | add | - | 6475041339cf7b5fc95bc0aafa49748b6252785a |

Only the two mutual/self-reference manifest files defer their result blob to external FREEZE; all87 final blobs and SHA256 are sealed there. Other metadata artifacts have concrete blobs above.

## Related changes

| Related subject | Disposition | Exact boundary |
|---|---|---|
| P01 row Time | changed | only R008/R010; no new req or private admission precision restriction |
| Shared codec and family inputs | changed | literal reader equals current writer; 144 schema marker copies remain exact |
| R012 carried token fields | changed | exactly operations.iat/exp and issued.exp use existing number; all other actual Time property trees exact |
| Canonical readers | changed | canonical/1/form1, existing Reader rev/SHA/outcomes, YAML/built-in checks and publication races retained |
| Four row wrappers | changed | root allOf to existing own writer x-max-names0; existing optional fields and open inner manifest preserved |
| Current schema/layout | changed | positive layout1, current N1 raise rights/CAS/barriers and exact huge diagnostic integers retained |
| B29 pre-existing debt | changed/agreed | 13 concrete owner nodes,2 exact and11 restored; conditional int fields only |
| TableRow890 | changed/declaration only | exact EN/RU stored stamp clause; no case/fixture/IO/new exported number restriction |
| Raw protocol/JCS/signatures/placed.at | agreed unchanged | no byte normalization, token re-sign or clock truncation |
| Common15 / A / P10 / Source / VMS / code | agreed unchanged | only explicitly declared family source cells; all other tree entries pinned externally |
| P09A / tools / ms / execution / independent review | not in source delivery | no runtime or source/joint/lesson READY claim |

## Checks and limits

Own checks cover exact68 source forecasts plus4 overrides, inverse literals, declared row/cell preservation, 11 codec lexemes, 144 unchanged Time marker nodes, three own numeric nodes, four unchanged writer limit nodes, 13 B29 source/target nodes with65 isolated boundary checks and two conditional int/null/string controls per descriptor field. These checks do not execute custom codecs, family outcomes, publication/startup, adapters or IO.

The first changed-pair mirror result was baseline0 to4 messages in3 pairs. The independently authorized exact4 supplement fixes spacing, the current canonical key reference and the shared Z-10 label. Three changed pairs were checked again;16 unchanged pair results were retained, final19-pair result0. The initial diagnostics/proposal are immutable external evidence.

No strict/render/gen/Go/HTTP/IO/SUT/models/fullGATE, old archive replay or delta apply was run. B1, recovery execution, tool adoption, P09A and ms remain open/held. The only registry state written by this author is review.

## Revision history

| Rev | Source | Independent result | Change |
|---|---|---|---|
| 1 | exact author commit in external FREEZE | none borrowed | source B plus separately authorized exact4 mirror correction |

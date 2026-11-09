# Change 0133-common-rest-readme-split

change: 0133-common-rest-readme-split rev 1 · lessons Platform/common · author spec103 · state review

Authoring parent `da7d80534b0920389764dd2cbf0211ebc8e142d7`; normal publication parent `da7d80534b0920389764dd2cbf0211ebc8e142d7`. P01.10.5.6, second attempt, by the acceptance role map of 2026-11-09 (SIXTEEN-EXACT-ROLE-DECISION-MATRIX, source pin c99bc4494; all fifteen blobs are identical at the authoring parent).

Split the fifteen common vector READMEs other than `revoked` (alarm-history, family-read, heartbeat-read, hold-state, holds, log-mask, loopback, password-hash, resource-state, said-id, schema, slot, slot-name, tombstone, values-by-type) in both languages. Each README keeps its generic commands, inputs, outputs, framing, algorithms, refusals and invariants. Set-specific passages — row and case counts, case prefixes, selected corner coverage, expectation and corpus provenance, fixture-field selection — are preserved byte for byte in a new same-directory `README.cases.md` under `### Original passage N` headings. Where a source line mixed a generic clause with case data, the generic clause remains in README and the whole original line is preserved in the judge-only file.

No generic rule was selected for a judge-only file: the rules that the removed passages restate were checked by sampling, at least one per package, against the README remainder, the owning contract, LAYERS.md and codec.tsv. No number, field, code, behavior, requirement ID, `.tsv` or contract is changed. `revoked` and every `##` heading (and so every anchor, including the `wire.tsv` references) are unchanged. No pointer sentence is added to any README: the remaining sections read without one.

The English source of the `schema` passage writes `exact2^63` as one token while the Russian passage separates the number; the two passages are carried unchanged, and one sentence after the passage in both `schema/README.cases.md` files records this.

All changed artifacts are unanchored README and case documentation; normative requirement units are unchanged. Thirty new `README.cases.md` files are judge-only under the selected whole-file filter rule, as the existing `README.cases.md` files are. Actual Runner location binding is owned by Runner and not proved by Source publication.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/vectors/alarm-history/README.md` | MODIFIED | 5c86a5d931a72b233157c3b4fbe59520366e6fe1 | 57525813e88619184206a66f226607c0f9d92755 | ab06a1dd5bd4b584bc22ebcd88c013b7f95710b28367431f92c89978c9cfc0b7 |
| `Platform/common/vectors/alarm-history/README.cases.md` | ADDED | - | c26a363774548a078ff9632f472d67eb5d31d29a | 7901b17292d0c3b0915b9049eeb23efdce26b49ad4a031faa4d024c9b13057d7 |
| `Platform/common/ru/vectors/alarm-history/README.md` | MODIFIED | 721a17e9862926a87bd6f74f4f192316ab0e53e1 | 3cd0618b011a75b69175adca3cec4a69b84380d9 | 33b2a7683382f7ef55fa2b9ef2adb178951129ab50446d0e72643404974a0c46 |
| `Platform/common/ru/vectors/alarm-history/README.cases.md` | ADDED | - | 7d3fe98868d6ae86d38a156ef5ac4c1567f0dfb4 | 9ca0c6509d65152f6e69e8f98f782e32685f3bcf9c621b7261153a091d5648bb |
| `Platform/common/vectors/family-read/README.md` | MODIFIED | 387ca9a530357255b417f4fe9eb5ad14a926b7d2 | d66e270093669e28a0868c559a6e639c1a0e9442 | 0323c623e09e716102b47197c99c77bc909357ad299b528b42277697dd5be8c1 |
| `Platform/common/vectors/family-read/README.cases.md` | ADDED | - | ef104542ad5bdbe536e068e66275953d34ba5575 | 00c79bb89ebcbd527d76e31e6e200bd03d186cf033d90a0d41ca2677ed3abb83 |
| `Platform/common/ru/vectors/family-read/README.md` | MODIFIED | 34061d39041b72b388aa173ca6cf96773c69b603 | b0640cc724daf2c233e25fdad6c091b6f909dcf6 | c73f84b338eb4f0870c3935715a7793b6cbcaf2307e9f0f1940a8bf40a2d21b7 |
| `Platform/common/ru/vectors/family-read/README.cases.md` | ADDED | - | c36adccb96f43b2774c0e218ae5d307966cf2675 | ec94201adafcdbebd3d8b9e49b3e3a9c8482873393ea762df532e40ab5754537 |
| `Platform/common/vectors/heartbeat-read/README.md` | MODIFIED | cc9e2d585ac655bb4e77c591a6baf06fb64de202 | 054af5b7ef7ecf3897911fc094a5db4505766d36 | bea36615c6386ac9a2d64b9b51e025185b5dfc481f8dee73ec9748d6726d1740 |
| `Platform/common/vectors/heartbeat-read/README.cases.md` | ADDED | - | b208177f42dbcb5bffd4361d372a0e29bda2b511 | 6a7705672d8c3193605cabb40a09aec6b2ee117c50a2e8bcb4db5173401f3249 |
| `Platform/common/ru/vectors/heartbeat-read/README.md` | MODIFIED | 9657a8e39b73c74c91f7fad0d53ca7fd3e0576e2 | 6edead70dbf066162ca53f5df3f814e8cc0852cc | 71ed7f081ae7dec94645c9c343b862a997d45d52cc6c9017564539012ed90a9b |
| `Platform/common/ru/vectors/heartbeat-read/README.cases.md` | ADDED | - | f34ab32184a5cbb0b0ea9805da5920d1cd87e0f5 | 214bcb7eab38167654f76fa9be18eed43af2b7849d39b7ca128f2e6a032eae9f |
| `Platform/common/vectors/hold-state/README.md` | MODIFIED | 23cb1bcf9e0dbe388b48518a4edc75758f2e70b7 | 61147175bf2533167385d58fe6a14afc6d2e33c3 | cfe8aa12d618d5a205f8749913c286466e8f10cf1c2c9272eaefb634c339b2ac |
| `Platform/common/vectors/hold-state/README.cases.md` | ADDED | - | 1079307445be70b569b3e3c966f6fbda2cb50a54 | 75239b935de761ad11878c9429f24daab142c6d6bc29d1da28f4f6950c6c551e |
| `Platform/common/ru/vectors/hold-state/README.md` | MODIFIED | 7692e1e666aa2756db1b2bffe64f17f5fb2c0295 | 7894c24d98ec7c17d47b94aa7d78fbe17a9c0828 | 3729b11fe8b78c879eb258f27f010a3d1c04014b32b77ee25cbfbf236206922c |
| `Platform/common/ru/vectors/hold-state/README.cases.md` | ADDED | - | a5e73ee8f24226b9f1c1c37871e0310d5709f7ca | e16b5158eefabb26e7339216f58b38999a444b25c5977e1d775cb59c46074e2b |
| `Platform/common/vectors/holds/README.md` | MODIFIED | 68b205e8fd8478b5230becfbcaf7e5cf24dd5257 | 499d3b7e0476a6570c17cededbe38eed660cd539 | e656c8db067b8e1563b2a9b6b2502fb388479bd080ac1c8eff90931fa1bfcf80 |
| `Platform/common/vectors/holds/README.cases.md` | ADDED | - | 61a9631f0fb8cbd84eb6cf800fc18b001a5b9cf7 | a66f599cc76767eb358423cbde086b2769399b39f3d18efe69ffbd2fca489e5c |
| `Platform/common/ru/vectors/holds/README.md` | MODIFIED | 8551cd921260ae9be15e1685110614db755942fb | 57777aa51ed4504fa0262138fcc991afe0a65c4f | 7f5e3997c63641c523ad18f1d155b64b227f327886a29ee192c036f40426095f |
| `Platform/common/ru/vectors/holds/README.cases.md` | ADDED | - | 46accc78240046cbdfa659976c07034e1226e6c1 | 8038cd55631e2b0bc9d1d4bf8cd39efa4d9ee9cd0fb76ed11289e32f755cb656 |
| `Platform/common/vectors/log-mask/README.md` | MODIFIED | b8dcfff26ff6abf2ae8cc6c6d82aa6e0c63d1dbb | 1444cdc69f2d9324972e5900fe10af315e6586b6 | 07df5327881c56f290887b4732e8c913628e953ff6c1a39d345cf06aba034efc |
| `Platform/common/vectors/log-mask/README.cases.md` | ADDED | - | 721d9a82217c633bf78cf9dcec576554c23a6a73 | 390b2f34ee84aaa2d6f4ed74df3007382fb0bdcbaddb408525d5d14b7e0af60e |
| `Platform/common/ru/vectors/log-mask/README.md` | MODIFIED | f1e67cdb8356ead15641cfdf91aa84b20ed9ccdd | 2b5e9997e6e1448f0e213917847c184f48374e04 | 7d6e84361bfc574ce84f6f259c427160b51514abb485819b4402fed12f407f31 |
| `Platform/common/ru/vectors/log-mask/README.cases.md` | ADDED | - | 8d934e47e0e2ce14c6063184d1cab983ef670ff0 | 3ace6b208e0bb69921ea35bb31838afb32cf62f899b91f80d95a7e7439d04b78 |
| `Platform/common/vectors/loopback/README.md` | MODIFIED | 614c6992695eb81b9911a4845e0f3f0489a31691 | 972af27918b316ade03b1fc27aad1f7f990d7f66 | e3bfdd5ab7051e3343ecc401e4b35c822b2a4c9723350432369eaf6af0384708 |
| `Platform/common/vectors/loopback/README.cases.md` | ADDED | - | 4d1ea1f8fdbaf2c6e2cef705fa936d07a2cd5e86 | 842a6c831ea70da2354cfb2e2f2ea0f11b6563b754d9dccb51e83b54bf9b06ba |
| `Platform/common/ru/vectors/loopback/README.md` | MODIFIED | 39ffd8d014a72f7b76cbb7c3a95a5b44bed100f1 | 47dcbee14cb61b247df82041e4806081015e953c | 862c3052e837b434b4e132f0ef478471cf48f8d7c5239eab81fec475c6e170ff |
| `Platform/common/ru/vectors/loopback/README.cases.md` | ADDED | - | 167e162d707b1ea90a5dcc1d6d982b448085266d | 879ea29bb6bab064d74a7ada6affaa60fd43b77829a54d9a3b9168d75422a081 |
| `Platform/common/vectors/password-hash/README.md` | MODIFIED | b7ad333cddec798be17b658d3dbfc2576a9312f3 | b03fcc6add1298456c0b0ca77ea468a0f57c5285 | 34c8ff0de2061ded7d294ba9483dea9b8afe27a017a3366914023f68b8f38faa |
| `Platform/common/vectors/password-hash/README.cases.md` | ADDED | - | 6772f13ef40e1590a7f1d0b816ae28b002a0e98f | dbe5d7476629ee2c1d1342f26ed1b2c86e0d5b027d9a2152a9922b93575d0cfe |
| `Platform/common/ru/vectors/password-hash/README.md` | MODIFIED | 30eb5646f771cae21f23381bd8544363cfed50fa | b5600c9836dc30711bf997ab5261c74b5e3472ed | 85af7ff4758f7abacfff93a3e193e4b9dc011ae1d413591a193b438ae017047c |
| `Platform/common/ru/vectors/password-hash/README.cases.md` | ADDED | - | a7536d1053b1cf11e8fd8edd8fca2b2358bcc43a | 86eb50069cefbffbefaffd6c21196a6ce5c6e8af563e7d20306f60950d0add2d |
| `Platform/common/vectors/resource-state/README.md` | MODIFIED | adf515c4e8a23a7e577e2f0f3df1b5694577133c | 685a3def22b698f667b5e0a7110c9460c941b1df | 368c1e4fdd2aac356e578b27adb3ab752b2a2a741a1ea009fe539854c01aec4c |
| `Platform/common/vectors/resource-state/README.cases.md` | ADDED | - | 7c30b0974e902306622307d01ebddab10f04f7e5 | 03c656f6ddcc1540ea33bef117b6a16b2b799980408f8781ff0c2a6aa7b7676f |
| `Platform/common/ru/vectors/resource-state/README.md` | MODIFIED | 5c3efde61ecfe8b352d47bf1dc5585f46bac0093 | 35199d7a3294d4775a1d5630a9237cb0bff6df00 | 72be42edeff335aef4712cfd3873b250e30836af803d37769854758340934fbe |
| `Platform/common/ru/vectors/resource-state/README.cases.md` | ADDED | - | 002732f6e0145e05e7f52b4947dd340ac2a5d69e | 226aae7b4ef3aad3b10511ee0026578bb3bb063b059524e44e93c78005c08153 |
| `Platform/common/vectors/said-id/README.md` | MODIFIED | 3366cd3330693fa2646ae5495f6817e06bb3248c | d3270ec8982509e59a3caf4a795296571f737cbc | aa46612fdbb93a8ad9a7f314035c6ab92832944e9e538e862810758eea8ebdc9 |
| `Platform/common/vectors/said-id/README.cases.md` | ADDED | - | 6fd100010269e37d23088073381f8878efc62932 | 731ecbdb73ee9025553f3886e5930cffb00d135c1f1499762eb7127320e881c3 |
| `Platform/common/ru/vectors/said-id/README.md` | MODIFIED | 9b7fec894e73b19a7450fc4b4c2b5018c83cec57 | 7259c698926a71ea6450168ca5fa8f30bf204a00 | 34a09ed133d289d166d558bd6901ca30b342d316af86e6d3720d6766f3e163f2 |
| `Platform/common/ru/vectors/said-id/README.cases.md` | ADDED | - | 4e75703e4345fb7b244f139a06b2434d47dc3f3a | 684d10298309cdbc105dc8c5d57c7f0dbdd48feedc17726db0161495e8a41bbd |
| `Platform/common/vectors/schema/README.md` | MODIFIED | 95757704b304a539e4b1fbac9e152a08cc110f0b | 2c73ee88e4b64eb71673408a3ffcecc4f154a80e | 4d8e24d250078bca894f93c8645d3cc8b819a9359834bd78bc14562908976d7f |
| `Platform/common/vectors/schema/README.cases.md` | ADDED | - | 28bd60ddad7a4bb4ee9db2f5f243ad1b94dae70c | 08e13d6f8f9f4065fe287100f978abca92840ffe587e0c50dce066e066a7deb3 |
| `Platform/common/ru/vectors/schema/README.md` | MODIFIED | 7c22eb2073d50fc9c21a5cbe51839c170378fd73 | 6fc1d61923887b563e57fc8c9b262a95729ab0c6 | 8d9fddd2ed5adc1afd393c160508040b1bb1686dec55f8631bff97cd423a3b31 |
| `Platform/common/ru/vectors/schema/README.cases.md` | ADDED | - | b3a9511c96415e03e84e8ac5f68a673d6d939c04 | 91e0e314233bfb415467db107590d37930f81d83a33c1a602d66eb3b7c94e835 |
| `Platform/common/vectors/slot/README.md` | MODIFIED | e108537ff20462730237d28e225d3506dcbc426b | 39cbf83d379a39a1dcf828851640c63f36ecd14e | 45361de9073bed7f1c338e06acbee49f405adb37e230aa972cac68a57ded77ef |
| `Platform/common/vectors/slot/README.cases.md` | ADDED | - | 6e156ff837815c6b7a3fec47c9d0a7975a596457 | eb7bf8236cd4f8fbb628d17ce7bcec4036d8b6ac47aa986c09f27322557fb957 |
| `Platform/common/ru/vectors/slot/README.md` | MODIFIED | 0b30adac67cbdd85a47cda3c1a05a6cecac3a896 | 89f3fc555cd48a3d050be44078a49b7ea6b317a9 | a8b8127e7d3553b8605b18cae61bca38f7478ff9447055e0a0d4ce197d5745ad |
| `Platform/common/ru/vectors/slot/README.cases.md` | ADDED | - | 112c504bbc2e6ca13701a4308ac310c423e2fe0c | a153b9796928597a3b5fd5993d5ed73d75941ee95428db13f4da886f1e3c2da1 |
| `Platform/common/vectors/slot-name/README.md` | MODIFIED | 71cdbaa2cd7175a5159c7f69f5d85fc08795e6a1 | e17bd04c80ec6593f9b5c6ca1812795e82bcf522 | f110efc7681ed068929ee59d6e20d506c775271a7e76a72b4f985ecaef6ea3a0 |
| `Platform/common/vectors/slot-name/README.cases.md` | ADDED | - | 72b82ac530e3cd73295a0fb35538a35fd17fb584 | da8819b6693d1504814df803f39a3e6abe65dcb4b59ce52cc317f0b7302e4697 |
| `Platform/common/ru/vectors/slot-name/README.md` | MODIFIED | 31c25e023881bb06d60c1b1a50285ccf0302244d | 5e088c82c6e75e0a447685dfe068c70fdcbe1ed8 | 3681f1e13f46cfeb797e8f30345a27f3ca97098fd2dd7f30fba79afdc638d5fe |
| `Platform/common/ru/vectors/slot-name/README.cases.md` | ADDED | - | 2ef71ea5c5776791fdbb4443b5032f3b4ead7ee1 | e54c67f5aa1735a1f69e30f990e7794badc9af9178f0c039e50032e83dac27b6 |
| `Platform/common/vectors/tombstone/README.md` | MODIFIED | 0a29bf39a8ac8bd30ecde9d1d5d55587d0c6144f | d1e4a8e3f6ff76e40268eed7d6f3d84f7ed1b633 | c915b9fb31f572a27a02447a50ccd4d1779f8ea421379494d2a7bb09e6a47624 |
| `Platform/common/vectors/tombstone/README.cases.md` | ADDED | - | a7d1bcb8acbc0192896b3876a98ed463bb18eb45 | daf232ce2dbb79d4992bd319838777f80807dcb84c92edd6464422f4024f48e5 |
| `Platform/common/ru/vectors/tombstone/README.md` | MODIFIED | 5ecf591b669a73df193a1059959e83b2018077c4 | 71a0748acada017ddc8622d9a3d3f2ef0605026c | 9b4f9ae0d6589546735428c9cfecb1962d2058143ec8100341578a49924cc667 |
| `Platform/common/ru/vectors/tombstone/README.cases.md` | ADDED | - | d8056ab3c41ae608a9d3543a3023100266c2cd91 | 9e90627165683ee9c328d036a603c8975c4a21904a847bb2000cce12116b10a5 |
| `Platform/common/vectors/values-by-type/README.md` | MODIFIED | 6b45d62a88d790349dd4e0c803a2e8697a252f2b | ca3a924a1fb311460af55ea3b0a027646a926b18 | 0c1773b7b7e39875ebd3a1525c692df82ac3ce2dd3e9346491b44c8ad7e5d07a |
| `Platform/common/vectors/values-by-type/README.cases.md` | ADDED | - | 1df484f1015e649474e0cfa079f2b2817db09414 | 154d9ce13089d9fd1fca4f9915e4152b99061ac07ec2e7ea03b028ff01b51c6d |
| `Platform/common/ru/vectors/values-by-type/README.md` | MODIFIED | 76ebd5d6bd8b8ccb64d88aef55d4b87157577f77 | 911ff8ebb5d7e058ce875a83cd17e6315674611b | ed7b792e51d89ecda32370b0f705d5673501ada8ccc1f6339614dda237248367 |
| `Platform/common/ru/vectors/values-by-type/README.cases.md` | ADDED | - | cb9b012697e638cf76e870263a7b14aaeb05ed4d | ed9d2ebd2fb1891efabb113569e62ec06fa8bfb1d28e52d7c62149292c660fd4 |

This change record is Source/judge provenance outside model input. No filter/export/SourceREADY/GATE, native/model execution or old proof replay is claimed.

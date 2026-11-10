# Change 0133-p01-common-edit

change: 0133-p01-common-edit rev 1 · lessons P/01, P/AC, Platform/common · author spec103 · state review

Publication parent `1ee45e809e35ec7cf970cadc781c80e9d6bdb517`. Task P01.86, ADR-0133 addendum (40) item 2: the common edit of the specification before attempt 4. The Architect answered the seven questions on 2026-11-10T08:48:33Z. (1) The command `store` carries the stand flags once and the group stand appends only the member flags. (2) `wire.tsv` becomes model-visible; its three rows that name cases or input values move to the judge-side `wire.cases.tsv`; the write-checks envelope is fixed in `wire.md` and P/01.1 R055. (3) `{rights}` of rights-evaluator is a stand substitution. (4) Machine forms of the profile substitutions and keys. (5) The test-side inputs of the judge, P/AC-R050, with JSON Schemas. (6) Inventories `forms/production.tsv` and `forms/extra.tsv`. (7) The route of log-mask and secret-in for P/01. (8) The specification pin and the Source pin. (9) The refusal path of an absent required field of family-read. Also the Go build environment of `build`/`unit` (finding C1 of P01.89.2). No numeric value is added.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/3/README.md` | MODIFIED | b4938bdf68e4d589009265dc7a407ff29a4dd29b | 6cc67ef2d6d00f93a98f40db841492043710aea6 | 46fba18f355666f801d700edb92fc748e81ae4571af2f3518e2bf48cc33bdbf6 |
| `Platform/01-store/lifecycle.md` | MODIFIED | ad006c3a40d67d58b770d844cdc3bf7b4756bc3a | c13b7611a20c9e0d81f55327e12d7a6e21ea3ce7 | 92b157eeefb7e9c5e69b21a1e272d8cb07d008ce7f56dceb5fe27b0afd0fd338 |
| `Platform/01-store/ru/acceptance/3/README.md` | MODIFIED | 3c4f4c899c9e3b70d24598ce07a6ee054864bbb7 | 1489cf58fb0f7fe13be89e966a2f3b5048eef7fe | 1ccb66c7ff43e36fc8cc8de427b8570677591bae0c0fba8ff25b695fc0b7a360 |
| `Platform/01-store/ru/lifecycle.md` | MODIFIED | 4fba99f2a6e9edcd48c6b30809434cdff8f0e22f | c33e05c6dbd2a3b4061a960b2e7943de36cac0dc | 91daed9f84a4036a6326f461a9139f7534956366791965a5b692ca879fcecfe4 |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | MODIFIED | fe842478e059f9fe3fbd34ea4850ca9907ce2c42 | ee7c4915d0d69bad5ae0f70485a8d453996790d5 | 33c1dba62c235dcb664bedbabe32523a1187418af862f054cae5994d73717d0b |
| `Platform/01-store/ru/vectors/rights-evaluator/README.md` | MODIFIED | 04fab55932c1d1879772cad3f21c964497412423 | ba153b7785af12490dccb6b76057f52d2c2f365c | 1be5a08dab1516f341df2cccbde5ba26bc948adfdc7ad5beb1a5cea2f1fac692 |
| `Platform/01-store/spec/01.1-store.norms.md` | MODIFIED | bc6723dea8d2006b1eeeab29b8811766862fe2b7 | 1b12d0dafeeda36baf1f5abaa1994dfdc85b616f | 9ac8fb2ccdbc71a2a4b7ee266160439067506b00e020f4423cff141d3d2b87e8 |
| `Platform/01-store/vectors/rights-evaluator/README.md` | MODIFIED | 4b8a287ad233a2f7d68d071dda016dc28be14ac4 | 5fc2656cf458b69bcde58137e27c4f8eae9eab0f | 2c7728d92ec9cdaf5dac8e31b943eb693a9b85184e62a4dcc2c079aa18105273 |
| `Platform/common/acceptance/PROFILE.md` | MODIFIED | 9751a379c61109ba7bbc69b64dc6488d80bac69f | 9542fe771ca820dee246d622b5aac95bcd2acd93 | 7b84aa2c5a03c805ebb419a1e4912e5e0c2d21076405f4099b61359a3888522f |
| `Platform/common/acceptance/README.md` | MODIFIED | 188d4db11e191af34898ef27be0c71ed08b8b06d | f5d7abb550997952db57b272a1c923d80e3373f0 | 6c78d28a31be937303c9f62d90f5a45e738ef4fe84ae9d7870016c8b2ea26b26 |
| `Platform/common/acceptance/forms/d7.schema.json` | ADDED | - | 25101a2618c355efea1b8fb7fc93e91e2496b3f0 | 5fe99885c2b97fe308e60e06d5bf1d6b6c198d1d4466a7c5f2d58b615cc95f5d |
| `Platform/common/acceptance/forms/extra.tsv` | ADDED | - | c124c5db2a8b3347295711fe5028b13fdd7157ef | a3b7d68379022436adde892b850fcb1a50c2b8ce6fcd9f9349810601c0be1766 |
| `Platform/common/acceptance/forms/production-input.schema.json` | ADDED | - | f4d168322d6e24060c583a4ba061135041a02271 | 274774ddf4621d838d68ca808519e36f53867fbff4aef18628ce029010a5517d |
| `Platform/common/acceptance/forms/production.tsv` | ADDED | - | 7fc0a3a288670a05f85a841eb1ffbd80c9da05ff | 3c26a2db217bbf8abc2dcdebc3be15b09578f3755bb1900739d57317a7c794d0 |
| `Platform/common/acceptance/forms/profile-keys.tsv` | ADDED | - | 7cf42a6a34af78fb2c042f6dcf891046fe6327c9 | c5a6d9f94956306ab22dc268debaddfc66424a12c593a878d7e6df7906a694c8 |
| `Platform/common/acceptance/forms/profile-substitutions.tsv` | ADDED | - | 7f3175ae4571101214d90923e19f645f594813f2 | 7d96390bb4179a9526d9d44d7394463828ca2344a634947564d3bd8c692851f5 |
| `Platform/common/acceptance/forms/seam-bridge.schema.json` | ADDED | - | 1a04de21e6096736a2bf1dae12ab19cf2290608c | fc32530fe62069c8cf6a23c1da30780f42e252059cd4f25b43f41059049d6733 |
| `Platform/common/acceptance/forms/targets.routing.tsv` | MODIFIED | 27dff1e9988143f6d8b737aa9bc1aaf0c4cacafa | be8c7df16c7965d451de2115d3532af7ff7efa84 | 38f0adaae15f6969da358579f81c6aa3417ccb9103976475c129ab856333da93 |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | bc6da308ec2e6e39416fd3490c0ffdf0e3bf39a6 | a98fae6f43255795066e9789f6eccaaa0951e1f5 | 288964bde74e8da60f217c5567fa39b447ea3702558b0b4b2f78a96545a2f38b |
| `Platform/common/acceptance/spec/acceptance.norms.md` | MODIFIED | 0da2bbcc4f1349e1d39001447a81691b5e2009a8 | d4f5cb19be15f343186e0b1b94deff81671920f9 | 9ffae6e9e14ec6660f0193cca62fef3e90cc979955765ab7dae8cca120044f09 |
| `Platform/common/export-model-filter.json` | MODIFIED | 36eaa4f65a4fb9fa0e72c027e9bf3683ebbdd330 | 660cc5e5f05a1da1925f6a340300b0459dfbf567 | d9014fbff286893599656a756b8efad3117e6dbfcaa9cf90643b921e749e0624 |
| `Platform/common/ru/acceptance/PROFILE.md` | MODIFIED | cfb31d2bdde05356981804b789c2d113198b5d5e | cca609c4bb69c6997e0ea663349ac7993335ba04 | 3638af77729c9c0d68bbcff6df5570f015a8ca83730d1380fe6297d4aa889610 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 128167468a341c87a6bbca6c2d2c86ece39cf78c | 7b43a4771691ee8a065065393331776e138c56d6 | e099975ab6df1a60753a64fbd3b5a2caa7e65b2ed4e257ae15323ea3031a0fba |
| `Platform/common/ru/acceptance/spec/acceptance.norms.md` | MODIFIED | 81f6dcdc0f7006f4c1aa4d211c8b21cf326173b6 | 5c508c260cedb6ca23802ae7202101d9f7f7adbe | 436421ac98624c0334744a058d501c27006c9c79cec236e3edf0d16ab12ef31d |
| `Platform/common/ru/vectors/family-read/README.md` | MODIFIED | b0640cc724daf2c233e25fdad6c091b6f909dcf6 | 4dfed9beba3af5295c44ec70a9e1c0c5b9825cee | bb2b11828bcdc70002b1db388938e9eb8e947f0d77dfa92ec01d0b585d6becaf |
| `Platform/common/ru/vectors/log-mask/README.md` | MODIFIED | 2b5e9997e6e1448f0e213917847c184f48374e04 | da39a0c0c646006f0715cb720f23701543b4c54e | d844299208bc543196c9d51a11a4a94d1da5e8b58f2404a775b6500ee6c92392 |
| `Platform/common/ru/vectors/secret-in/README.md` | MODIFIED | a2c0dd8c3646beac08b4647538985a4fb658e58b | 30f221e2a1abbb55f932b4f62cf3b7ed963b29d6 | 4acd219eb9bf15a21b94a73d726dcffb516f38b2e5c8f70c64eda3fe2731e4ce |
| `Platform/common/ru/vectors/wire.md` | MODIFIED | 4c056b8bb87755371beb6f06042b53e420237145 | 6bef051940d5adc020ba8aaae7914b3420800c75 | 6e4d2bc97b2a069c48830d95ce4a9d19e4a6d8fab9699870aee520c526588271 |
| `Platform/common/vectors/family-read/README.md` | MODIFIED | d66e270093669e28a0868c559a6e639c1a0e9442 | ca65afcf95f5b7888786e78bf244a220f1aa2817 | 5aa196fa112423f766ddc2420f2b4b1bd132a514124bdf9d238812b9823e9380 |
| `Platform/common/vectors/log-mask/README.md` | MODIFIED | 1444cdc69f2d9324972e5900fe10af315e6586b6 | 9cdc7eed77d9790b871da0e3ff5b682e23619029 | c0056f73d3611f22410d861c3dfcb0e769cfa04cd025a3222b00aa71976b1e5d |
| `Platform/common/vectors/secret-in/README.md` | MODIFIED | d7a5c6bd35c39846da66514085ffb5a3b9bda94f | a3294e4e25403663d7a8779859ae65cc2df8f6af | aee255d8c5a294623b558294798dd62a82c95271433fe340b3ffe9d44b522946 |
| `Platform/common/vectors/wire.cases.tsv` | ADDED | - | 9b0d9ed48713d6e8a6db077c1c9a08fbf9f9e313 | 8cac4f68c04d306b2dae2715b0d8b447af2266ea56b2813145a43faf678fe42e |
| `Platform/common/vectors/wire.md` | MODIFIED | a6fba60426f496c2e54a81a08880f88816e7922a | 3d4f6c64877b8be376a0871efb5153d82671fffa | 8cfbd7eb6f402406fd193e418beb3749e2c41e36510f2e675fb3aee68c1dfbb1 |
| `Platform/common/vectors/wire.tsv` | MODIFIED | 1e321bda1270843afc16de455f18fc1fd5bc6ca0 | 2ca15f97353104142e77d3dfb4fdb9dde4faf994 | c4a8aedac56b60749da523f75a10d9a07f466a2337214e21021dc3d5415361e7 |

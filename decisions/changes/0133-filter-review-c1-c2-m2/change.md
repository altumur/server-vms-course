# Change 0133-filter-review-c1-c2-m2

change: 0133-filter-review-c1-c2-m2 rev 1 · lessons P/01,Platform/common · author spec103 · state review

Publication parent `9217a9dd3bbee0ceee6c3a65e2d2f172b8153325`. Filter review findings C1, C2 and M2: the concrete JSON of selected TLS probes, selected scenario-step to value associations in the P/01 and common acceptance README, and three wordings that named a judge-only README as the only source of a protocol. Generic rules, closed forms, commands and setup stay public; original lines are appended byte-exact to the existing `README.cases.md`, earlier bytes preserved as a prefix. No new norm, number, route or flag.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/1/README.cases.md` | MODIFIED | d43868ec8bf4a34af438840fdc528acbb6c430d4 | ebaf5856e5380b863ce064a8b804f142a4c7bbcb | 4e9ab172ff7f948f0373a37f4809b957e84819a0296a576b8f432e454d1c6fc4 |
| `Platform/01-store/acceptance/1/README.md` | MODIFIED | 1f86c36ebdb7f3c62fe2c25f36cd21d2a4ae75ff | 802fb4b7613d4fb5222b5ae8438735b0664daf32 | f71e348ff64215379bd1dae8129062deabf41bd8ba291c78d4d7e0971af7af76 |
| `Platform/01-store/acceptance/2/README.cases.md` | MODIFIED | c000dbe3ae0f42572c57933b7480e9c0008f4c91 | e9ae7f3df2ca3f81f9f9950d3ea562d4645b6fee | 5f7fb160bc4ad036c15ccd4365f4166120e74e44bc31dc289b0cd71af6609c38 |
| `Platform/01-store/acceptance/2/README.md` | MODIFIED | 45fe95f953be1929038f5b444e991aeafcb29c2b | 3aa8de950eea9a04e936d5cd3eafc0876c787b7b | ff9acb23137ddcaf0df4bdd1f63ef33cc154c31cbc3f748c6e564e1843195d72 |
| `Platform/01-store/acceptance/3/README.cases.md` | MODIFIED | aa8d6852203be1bfe897bd79a746572f0fab7d61 | 30833bd20ef1d333772bdbcd4c1cb84564e87bb8 | 68c93348ddfd853f0cb8793000f5e91086dafba30c0e3aabd0b109d6c94e706b |
| `Platform/01-store/acceptance/3/README.md` | MODIFIED | 66e821e194a0b2b4f8d55408175d04d3af0c9877 | b4938bdf68e4d589009265dc7a407ff29a4dd29b | 77a0dd6494c317db5f39e882813e40cabe8e0a6447ba5064c6e9bc2c5b6dba44 |
| `Platform/01-store/ru/acceptance/1/README.cases.md` | MODIFIED | 5c93d9261b289105a4c941f368ba5d7cf1672c61 | ea5b2c1030a2efd6284d39bbb67f9300a7d48da9 | 6b1a1e8e658be9249616ea1c3102d01a61ac304923d0f386ba2b03455913c536 |
| `Platform/01-store/ru/acceptance/1/README.md` | MODIFIED | fc609ecb4374b687a6af3f389173e04db61ec6b2 | 90f67dc4c904082800cff39752c9ca03071b7ac3 | c2776cfef51ca8da51e4a5c9c1a1ba5081a47f8ee9528abb4b12ac476c8c4d3d |
| `Platform/01-store/ru/acceptance/2/README.cases.md` | MODIFIED | 088323ee848a7c6d8b67003f1ad2d1a11cd87636 | bdbb5e401d095509fc78a68b126e88ef267ce0c1 | 86def6021bdbb49e9a83a4778d028b7228738359f5e1e67bfa315975efaca8a7 |
| `Platform/01-store/ru/acceptance/2/README.md` | MODIFIED | 80e6cc3f9e3f76fd284566f13c79a97ea5d3bb11 | 5f6c25b935e826c91bd83466991d24631d28a116 | f2b8a3d5de008b12916f9121750fdb03dfc5128905963e8d8081fdf4a0b96f96 |
| `Platform/01-store/ru/acceptance/3/README.cases.md` | MODIFIED | 5f2ac46eeae90a08a2c057000fe5b9bab989f04c | e5c863f2b83eeb0714491954525069b8cbc8e6d0 | 28016388f372061cd9d490c8514467ecc1623549cd8787a98b11ca999fff1099 |
| `Platform/01-store/ru/acceptance/3/README.md` | MODIFIED | f0ee23db08991a473d5a50d1283550034a41333e | 3c4f4c899c9e3b70d24598ce07a6ee054864bbb7 | 8bcf703425c0312688b4ed38ed26ba506554bbce5035964ca30569808185e8c0 |
| `Platform/common/acceptance/README.md` | MODIFIED | ccac3e70d07a9ea586fe6e3fe578a0a95315909a | 976d5e03d920f0d670c974cef9c1865d68cb1648 | 928d3fa40f2afc58b8ab04b3225ebd0885b8fd3d0ad2e72450150a91f0ae216b |
| `Platform/common/acceptance/tls/README.cases.md` | MODIFIED | d17d9e8c15d8f1eecdf0d7047268adbf70058ea4 | 281111bdab01f4f2a9a4653f4b782f507b290ff6 | c4303c429418629b68837e5b4571b67c3cdbab0503f887a2ce6403d6b6900df0 |
| `Platform/common/acceptance/tls/README.md` | MODIFIED | 7592a4df9d54fa0392eaf4e7b4b9ab1c4a9cd865 | 842777e7f50a556daefb9d8a58f851b6f713fbbd | 2eb8d6bfd6754585cb42d1c6d976cefc79d67f0633ade9de2f5ae6c893e52f7f |
| `Platform/common/contracts/agent-signature.md` | MODIFIED | 077c3255fd4a13d28b63f431f403d9170e9fcda0 | cb165077910ae4567c96fd17c428d51e588bd870 | ce96044c51188d186d1de6735b7d7fa6a48ee9a4efa03caaa4a9366f77b4fe90 |
| `Platform/common/contracts/request-mark.md` | MODIFIED | 68b7072f169e0e8956e83983c138bfea9f51ce2a | d9b72e2d937fd056dc070de45e518207fac60433 | a2cd82f94de812ed92e65d0b74930b5f8853dc10680e5be998002693ff6ad2e0 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | d9ecb2cd14b2776eabcd720fdb5213b755e161ca | 884923a6ebeecc6a8682b90287617a1f70c80478 | 738d59b45abfaba3a697dfee8044eedc654ff752e3b476ab4219e3b72f034be1 |
| `Platform/common/ru/acceptance/tls/README.cases.md` | MODIFIED | ce140617f2da1b7147e29b7bb4b0432bb80b5af5 | 2e90d0538e92a0ca544e9e759886ffc47e3b7841 | d4630eea8e4351b781db061496dc3c52d891cb2c4a1727dafffdd69237d6bfda |
| `Platform/common/ru/acceptance/tls/README.md` | MODIFIED | e9707a7a1370d624e81d04bfe81e816a1712a5f8 | 766e6f7f691bad05610ab73288e0be3bdd857a97 | 20d3c62f3ddae02663137af78a63e75bd8f1745afa8b0ca3190176abe19f0796 |
| `Platform/common/ru/contracts/agent-signature.md` | MODIFIED | ce3acdb9239844fd407f8920428c9f914e43549a | 1db16062baaa1465cc349723f72a1ae12bc9c8fd | edd230649fb0323f48d082a741896a84c2e2c0488e581696e06e0330b622260c |
| `Platform/common/ru/contracts/request-mark.md` | MODIFIED | 564eee4cdbde33440329046f5f6032ca71c5b3ec | 729b79dff54a7a32fcf1c6edfed7439f1b1e2972 | 758efded3861bf5978a251a5fdae39864b5e23e9486ea4cfd10df49a494f2269 |

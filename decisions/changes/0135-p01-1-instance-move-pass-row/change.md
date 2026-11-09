# Change 0135-p01-1-instance-move-pass-row

change: 0135-p01-1-instance-move-pass-row rev 1 · lessons P/01,Platform/common · author spec103 · state review

Publication parent `a620d688f502408a7d45c0f0d52bda46e8ea1631`. The Architect's decision on Q26 of task P01.29: the instance rules of acceptance 1.1 move from the common README to the chapter, the selected case and value pairs go byte-exact to the chapter's `README.cases.md`. The row `01-ticket-lives-with-request` step 15 of the pass table is judged by a JSON form, because a JSON body is no longer judged by `~text`.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/1/README.cases.md` | MODIFIED | ebaf5856e5380b863ce064a8b804f142a4c7bbcb | 7faf02ae3ac1b090fabd72c43324e4208e24bf7b | 24ad77295ab1f6ad87ea888667b7909d9aff988d32830b0d52bc51d2d50fec8c |
| `Platform/01-store/acceptance/1/README.md` | MODIFIED | 802fb4b7613d4fb5222b5ae8438735b0664daf32 | 18a2a34d183fc0f35d0c1e77ea910d6c3d8b3bca | 82b5581b4f57c28f92c7e0ac7cfd35a25c7b7e565fe0baa9a93ebe24786f5b55 |
| `Platform/01-store/ru/acceptance/1/README.cases.md` | MODIFIED | ea5b2c1030a2efd6284d39bbb67f9300a7d48da9 | d1d065d4fdb3b0ee2d1284194c94cbf5ca74238b | 392f85de5172654f43deb9d7063a7aa177e4995c9dfae8eb7de2ed85dc151afd |
| `Platform/01-store/ru/acceptance/1/README.md` | MODIFIED | 90f67dc4c904082800cff39752c9ca03071b7ac3 | 925641ed7d43150c1992ea16c0803c0f196110b9 | 797bdf2951cb70f5b701fd97fa5a533d594283f2d7dabd5235023ef18eb60676 |
| `Platform/common/acceptance/README.md` | MODIFIED | 46b8013b2bcf5861ad29dad81265a0aa1eebe3ac | 82edbbadf75b07391cf4fec978f1fcd4d6780a40 | a08c6e2ee2cbc2a5c1c0e154e9de5892d575ecba5362d7738559dbbb66dc316d |
| `Platform/common/acceptance/pass/scenarios.tsv` | MODIFIED | 9da06ce4f769f8610ce4f51582a86ebb34b5607c | 2310d893c87ace345f3c5323e9b3c293e2d02f45 | 132817646a884218d4817dd25612d9b69238d8e15f7f0b9e324768391c1babee |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 397479abec80b9f5e158326755b5d3807fb0927d | 0322bfe8622263ab71e4b08dca5e8e53b5d1d3ac | 91657358cf2e772f36d60ad777aa28b7e958a8ae99f9a268e3264431ddec4237 |

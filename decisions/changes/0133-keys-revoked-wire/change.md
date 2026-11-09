# Change 0133-keys-revoked-wire

change: 0133-keys-revoked-wire rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `2ba0fffb8af6a598fe6aaa6fe5de4c29cccd95e9`. Task KEYS.1: `consumers.tsv` declares `common/keys revoked.tsv` for `09-agent`, but `wire.tsv` had no row. One row is added by the description in `keys.md`: one JSON input cell, native code 0, the output is a JSON string compared by value. No new meaning.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/contracts/keys.md` | MODIFIED | 4bedf802b05c2275f2ec7ea1d9e0928153998857 | a9861bd3fa44b3df63b1c4ccb7a2a0d9f207cbc2 | d818adc3f5080d409ade915242145121fe0a65cc905997cadbab33fa039d71d2 |
| `Platform/common/ru/contracts/keys.md` | MODIFIED | 25df0c37799c54ec5c0f69dd469043b451a2f7ff | 51c4dced69fe82eddaf6a883a5005f7d942876a8 | c7c588d362b9b8df6ea85b490e36baed1ce7d1d917021e1e30fdacdbae445441 |
| `Platform/common/ru/vectors/keys/README.md` | MODIFIED | 6f2859980feebaa83c425439afb3ca06d7098496 | f67bfe5244c25ecd32ef7aceeedf06470423a7a8 | 437f652603b1d7ac24b1b44a028795b9e4c47a2cc946c3d11ecba834ae4075b3 |
| `Platform/common/vectors/keys/README.md` | MODIFIED | 8b7522cf6e95ae8899b2f315180b8df0e0ef8027 | 4bb86a9aa622dfac8cd711778357815d38acf9b9 | 8f45fc87f0de486392fb641bedc9cc07905999dc5954bfdcf8c15678fbfa874e |
| `Platform/common/vectors/wire.tsv` | MODIFIED | 63d9950c6bc211e3f32b2985389548be855ef591 | 1e321bda1270843afc16de455f18fc1fd5bc6ca0 | 3668e85aa08fd71764afc5f12f2754f2aa945733b92a73fb54e44f9145a8a698 |

# Change 0133-p01-code-rules-lesson

change: 0133-p01-code-rules-lesson rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `4628c89f6d04b60ca8cb7b13928fc055d4d61c56`. P01.104, after `0133-p01-code-rules`: the correction of the Architect to item 5 of the contract of the interpreter — a function or type symbol is `<import path>#<identifier>`, not split at a dot, written without quotes and without a space before `#`, since a YAML comment begins only after a space (PROFILE.md EN/RU, the header of the dictionary); the 24 rows of the code checks of P/01 `Platform/01-store/forms/code-rules.tsv` (the candidates of ADR-0133 addendum (28), the Raft library as `requires_module` of stage `group`), model and judge. The gate `code:*` in the cells of `forms/stages.tsv` follows after P01.105. No requirement unit changes; no numeric value of a norm.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/forms/code-rules.tsv` | ADDED | - | f3354db7548a7745a2d424a4529b9e4d77d4d32e | f41868aab5c9ee2e2c1f048e375b16d2d41ff49bbee5f9627c9702a4946ac93c |
| `Platform/common/acceptance/PROFILE.md` | MODIFIED | be542d3f8b1bb679c095601fa7f2e831e7889254 | 2a1320ff603e10e56ae3c0c1819a7e4de25e50a4 | caa0225b189c822c761d5d526d2ef617fe6fe23499d945f9586ebd874a37de32 |
| `Platform/common/acceptance/forms/code-rules.tsv` | MODIFIED | 6df6f46c31814314d82da101c144e45ca8e615ff | a0a91d8a160b3f85404dc28e3478792ecf035d26 | cb7a7c8210fe41cc08ce588d1179fcf4adc67fe3b0db519bcbcf52bd62ec432d |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | dd29a2ff83c0ebea7884240a7334a8b8ba62f66b | ec0fc004e242d9a441bb4042b5a226f80ae4df17 | 1bd68b0e29247593c25c50f9d9d4d14793282b5c9b1f056fe439461341d6241a |
| `Platform/common/export-model-filter.json` | MODIFIED | 3192b586cce45678073f0ed145e667481e31992c | 5b1bb97c01cabb4a7865dfd4ff18e62e3b83fd1a | b3f5661c3ff1c3b68d3ef7bd6ea3145db4158d6b3d4b6dd94186b6233438f51f |
| `Platform/common/ru/acceptance/PROFILE.md` | MODIFIED | 59ee33a0836b1a96fb2ba7ae7e0d99d4dd898af4 | 7c78acc678be9647535f9f0540f508e13c851967 | 11ec30f88a062ecf33aecc8c28cfb5cca3fbcafa60e22e97e72e34ac112422d5 |

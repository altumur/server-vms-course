# Change 0133-p01-code-rules

change: 0133-p01-code-rules rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `2c10a2d700d72f73151084fd9be7422ea1fa906e`. P01.104, first commit (ADR-0133 addendum (39) items 1, 4; review P01.103 and the decisions of the Architect on it, with the contract of the interpreter): the closed dictionary of the seven kinds of code checks `forms/code-rules.tsv` of the common acceptance (model and judge), the optional profile field `code` with the section «Code-check names» of PROFILE.md, the grammar of the gate `code:*` in the header of `forms/stages.tsv` of P/01. The rows of P/01 and `code:*` in the gate cells follow in the second commit after P01.105. No requirement unit changes; no numeric value.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/forms/stages.tsv` | MODIFIED | 98b9a7d4e57e8e5a9b5920bcc3bf8871eea20bac | bbf620c51cab0aaae1cfdb790b9ae09ebdefff0d | 93bc056249ce93b112949f27b3b8f84ddb22642961d178635aa46632ddea0066 |
| `Platform/common/acceptance/PROFILE.md` | MODIFIED | 1e493ec6bf10110a62a89140f85278d278c9ab4c | be542d3f8b1bb679c095601fa7f2e831e7889254 | eed9a6e1c2a1ba59adc62246522e34c993786db87e721084bda0b16f4faf9b96 |
| `Platform/common/acceptance/forms/code-rules.tsv` | ADDED | - | 6df6f46c31814314d82da101c144e45ca8e615ff | b20efde7ae67da0cf088b3e406fed958970ae3e41a0ff4bfa9eaecdcd3276d46 |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | a98fae6f43255795066e9789f6eccaaa0951e1f5 | dd29a2ff83c0ebea7884240a7334a8b8ba62f66b | 234ea9b09f55d70e99ee2f3070f7d8b7d69e48f89c149851c2681af79801584e |
| `Platform/common/export-model-filter.json` | MODIFIED | 0a4c7a136a460d0650cff0f24131b4a71ee9e9b5 | 3192b586cce45678073f0ed145e667481e31992c | 79f8ce357d2d8d3893706c7ebd5fd2e0e7cd5ffcb3325fd3d170298f52bd9eaa |
| `Platform/common/ru/acceptance/PROFILE.md` | MODIFIED | 6c9ff39828f32f38b8a300091ee605f64aafa56d | 59ee33a0836b1a96fb2ba7ae7e0d99d4dd898af4 | 2c7d2e3905f136ce1806a50f13cd2a26b6ce9b98464bc33548ade7ec61f86d2f |

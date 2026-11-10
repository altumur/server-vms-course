# Change 0133-p01-wire-cases-criterion

change: 0133-p01-wire-cases-criterion rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `6379b8762e19643f2d034cb79adeca9e88d87c5c`. Finding B-2 of the review P01.87, answer of the Architect: the criterion of `wire.cases.tsv` in `wire.md` is narrowed to rows whose cells carry values taken from the judge-side case tables; a reference to a field of the row by its column name keeps a row in `wire.tsv`. The composition of both files is unchanged; the comment of `wire.cases.tsv` and two filter bases follow the wording. No requirement unit changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/export-model-filter.json` | MODIFIED | 660cc5e5f05a1da1925f6a340300b0459dfbf567 | 0a4c7a136a460d0650cff0f24131b4a71ee9e9b5 | ff27003ae4f6fd7d8bc94a9cd194cf02b6f7f83d6a45fe8de52e484630e511be |
| `Platform/common/ru/vectors/wire.md` | MODIFIED | 6bef051940d5adc020ba8aaae7914b3420800c75 | 81057fc0b189e6397f3154e82be6584b05c8f98b | 47560723505dec050c640d0e563c9ac01489aff98383a2c2b42c5170e5ce179e |
| `Platform/common/vectors/wire.cases.tsv` | MODIFIED | 9b0d9ed48713d6e8a6db077c1c9a08fbf9f9e313 | 7446b343f20026041b0fdbde7ba7fc1865e592b1 | 165d885e072eb605bc27c30c31ef450d72e8f4d10b3e956d4158cf714c668403 |
| `Platform/common/vectors/wire.md` | MODIFIED | 3d4f6c64877b8be376a0871efb5153d82671fffa | 8602b14e71acfadc42f6d8c40cf40d84befe9674 | 07147545be10629b22f231987314708088a22420daa73aa96e198d6d6492e8e2 |

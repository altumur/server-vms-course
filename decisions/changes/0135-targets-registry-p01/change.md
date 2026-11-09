# Change 0135-targets-registry-p01

change: 0135-targets-registry-p01 rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `6747b095986447b929c1a3352de9166f38b105f4`. Task P01.26 (ADR-0135 addendum (2) item 2): the target registry in the common acceptance forms, one form for every lesson, with the rows of P/01 filled. `targets.tsv` carries the target, owner, stand requirements, norm anchors and flags; `targets.routing.tsv` (judge-only) carries the engine, directories, scenario range and the parts of other lessons, joined by `id`. Rows reconciled with the runner table at the pin named by the task. The cells of the public columns are byte-equal to the rows of `runner-targets.tsv`.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/forms/targets.README.md` | ADDED | - | e9f965d001d6cdf791521dafa3ebd5452232b8ed | 6afb30260c4726971cc068a4c6700c7a5407bb0e711568f10120aa43ed110f70 |
| `Platform/common/acceptance/forms/targets.routing.tsv` | ADDED | - | fca41940ca1bfe4e3dc7f709bceb2f1d50ec1c90 | 9cec37cecd1890c575244e64b4f1f418c28b00a29997e442ccd91e5c1f41a8b0 |
| `Platform/common/acceptance/forms/targets.tsv` | ADDED | - | 90d3f1c736be9af231cfc3f20e1812f75bbc8f1f | 11a6d84418c82921520685142963d08cb4c38e1c3b8af6f1e48abcaf7ea3e482 |
| `Platform/common/ru/acceptance/forms/targets.README.md` | ADDED | - | 780683b3173a37822becac06af3f3a34375104c0 | c31585995c2351aebd441fa59ece8a8f7a32066f1c797a682380dc5c58e955c2 |

# Change 0126-11-p01-seam-normalization

change: 0126-11-p01-seam-normalization rev 1 · lessons Platform/common,P/01 · author spec103 · state review

Publication parent `89d094a94d72d9c135c4fcbf25dde179a385b6fc`. ADR-0126 addendum (11) item 4 and the Architect's decision on task P01.21.3: the seam protocol of the common acceptance README gets the P/01 normalization (`store-http`, `clock`, `reopen` over `method: call`, no new bridge field or method) and the `@parallel K` exception for P/01 and P/02. The P/01.1 acceptance README and the header of its `seams.tsv` no longer name the kit or `Open`/`Config.Now`. Data rows of `seams.tsv` are unchanged. Executable receiver: runner, task P01.21.4.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/1/README.md` | MODIFIED | 14429b4fdd4e65083e362f88416d4b3f3f11489d | 780cd988a4abcf44064f3214d819f73f20ff3ac7 | 7f545938234a4e4074976ac7de76efce786b138cbaaa33e5ed7cb80369cdf7c4 |
| `Platform/01-store/acceptance/1/seams.tsv` | MODIFIED | e9e8551b0901de431f110f7f55435bfea428bf48 | 0b11167db2add7c186ea6950f8b4dd65c5d8e3c7 | f90b38073e0020cdbbf6ab7ac81e98a2f19774f6f7b453225e1ce7205403e9bf |
| `Platform/01-store/ru/acceptance/1/README.md` | MODIFIED | 6ce2f142c6a329d32576fcc2e22b4366a1fa4792 | c52c56dc8306ad1de79ba69c329add4376fec48c | 14014c7c1353b5e770b1818e223094f9d0e0551aaf0e480a7fb875ba7f7471dc |
| `Platform/common/acceptance/README.md` | MODIFIED | 1d85ee3e8f097aa103e3da4be83a1b86ce09adfc | ccac3e70d07a9ea586fe6e3fe578a0a95315909a | dd76bd0b89a4c241dc3d30bb4eaf76c39e700883bb527672a13c2595cd50cd90 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 31dd5ca18fa4a91822881860d6f5273cacd092a9 | d9ecb2cd14b2776eabcd720fdb5213b755e161ca | 7ac0db8dfb808dba1ae08df028e05383e557a88e3630008181e74c551d3b70ba |

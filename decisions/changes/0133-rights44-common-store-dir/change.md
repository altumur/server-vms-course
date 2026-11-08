# Change 0133-rights44-common-store-dir

change: 0133-rights44-common-store-dir rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `dcd531bbff840aebaf83cb197bf18be1f684b824`. ADR-0133 п. 8; Architect classification of probe 44 rights turns 9–14 (stand and task defect): the common acceptance README named the layout but did not state the store directory of a composite stand.

One sentence in EN and its RU mirror: in a composite stand the launch command of the store receives `-dir {data}/configstore`. No new key, profile field, substitution, number or requirement ID; lesson stands that run the store alone are unchanged.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | 1ab37eac8abdc13e315e4b2ffd0796a11a06be66 | 1d85ee3e8f097aa103e3da4be83a1b86ce09adfc | 7db8d017b8aba907725efaa92d2438858aea032b98a932d127815f2b3da1816d |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | c430c5ea39f8e7b616dbc0922d970ebf083360b7 | 31dd5ca18fa4a91822881860d6f5273cacd092a9 | a8fd7d96cc3d73c988debbe3ae81065d60e6cb2ad0841308003d2b76bcf7c0e7 |

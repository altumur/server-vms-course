# Change 0130-add15-replay-limit-retry-after

change: 0130-add15-replay-limit-retry-after rev 1 · lessons P/01 · author spec103 · state review

Publication parent `c8035bd60e0f2f8938cfd883f722478705c621fb`. Task P01.35, ADR-0130 Addendum (15) item 6 and the Architect's decision: the refusal above the replay-processing limit carries `Retry-After` in seconds until admission, computed by the implementation. A catalogue row `replay_limit` and an N4 line are added. In the OpenAPI response of `/v1/write` the header schema is an integer; the connection limit stays exactly 1. No new fixed number.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/forms/refusals.tsv` | MODIFIED | 884c2ec86d89e88f379c7ac77211e91308641e87 | d7a46f479b6b8e10d3d66eb689e3e5fd89395e20 | 2755a833a5b5e1430dacbba54a240b1b59003284a02c9e288bae8ebbab186c2b |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | MODIFIED | 700ddadbfe2c17d9fb0f88a6b68e89c1255feefa | 396482830adba3fcc91a7ce5673a87c9a97ed316 | c6185958d95cb5748ae520e3d32665b4fb2aabe44fca86a2e2a421a140d85ed4 |
| `Platform/01-store/spec/01-store.api.openapi.yaml` | MODIFIED | 7149a6fa1d615cd04b3ddabdfdbcec0dc974b3b9 | 4e45c855229a65e8e424b73600b1a2dbef56c0fc | bcfb11a7552bb718553729f6fc0f6700296e2e493a06f378b1ea580114699b50 |
| `Platform/01-store/spec/01.3-store.norms.md` | MODIFIED | ef2237285b202f7ee38d75aad59fc38ce52dfa08 | 726460b6ba81ad715eb8b948ea0e913d91c433f4 | 33b25f43c3e6e9ddbf00bc22a92beb8e7ce86a0c8c96ac2af7da3747fa79e6a3 |

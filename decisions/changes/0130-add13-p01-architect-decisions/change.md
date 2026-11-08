# Change 0130-add13-p01-architect-decisions

change: 0130-add13-p01-architect-decisions rev 1 · lessons P/01 · author spec103 · state review

Publication parent `34e8538aa7cace2ada3cee97cb0941c848ab5615`. The Architect's decisions of 2026-11-08 on ADR-0130 Addendum (13): a leftover of `backup` is removed by the next run of `backup` to the same target; a held writer in a group gets 503 `unavailable` and reads answer as `file://`; `box` is the store without raft, a raft group of `-group-size 1` is a group, and the rule covers `restore` because the phases are common; `ENOSPC` after the effect stays `ambiguous_*`; exceeding the `admin.sock` limit is `connection_limit`. No new number or route.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/ru/spec/01.3-store.norms.md` | MODIFIED | 4542506b17f88c26b3a8b1fb3518c4d454d68e94 | e141615b4237f21b94498e3da551ca7cb34a7df4 | 5e84a08a4ec03528a790b228109548ec69512dea387a26a8f163b49ff85855a8 |
| `Platform/01-store/spec/01.3-store.norms.md` | MODIFIED | 779ac8a785f2e0301b7fd5ef276ec290bcb43755 | 99d6c3d238b8b449b9c6a7e08218987ef4801ee2 | b474506ac18493299dc0f8c9fe53c3495578dfa1068546c4e474994b71510992 |

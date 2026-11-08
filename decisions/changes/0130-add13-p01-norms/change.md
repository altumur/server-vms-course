# Change 0130-add13-p01-norms

change: 0130-add13-p01-norms rev 1 · lessons P/01 · author spec103 · state review

Publication parent `e6ad81b77 (authoring), normal publication parent `e3db8b3f86e54d84aaed25caffbf76ae926392ff``. Records the decisions of ADR-0130 Addendum (13) items 9–14 in the norms of P/01 as stated there: an interrupted `import` in a group keeps the node running and holds writers (start refusal stays on a box), the phase mark of `recover`, the stop outcome of a request not yet admitted, removal of the temporary `backup` file, disk and descriptor budgets, the waits of the doors, the `admin.sock` limit, door attempts against `-leader-wait`, the clock forward jump and the age of the `id` memory by admission time. `production-acceptance.md` changes the phrase on unapproved budgets to the rule of Addendum (5) item 3 and gains a probe debt table. No new number, route, status field or profile key. Probes stay with Runner.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/lifecycle.md` | MODIFIED | 67f6aa6b81d4cc607e0590368e36fe6a84c3fd2e | ad006c3a40d67d58b770d844cdc3bf7b4756bc3a | e42fd53914cdee0e939bd7aeeab6aa85306fb6657030d4e811f2ac4f5a48fea3 |
| `Platform/01-store/ru/lifecycle.md` | MODIFIED | eb4240adb0f894e8db51c573b8aaee95306ab2c5 | 4fba99f2a6e9edcd48c6b30809434cdff8f0e22f | 0c1a1108e375efc8239d4b057accebd79cabc3c2b6a1824dd885754aaa325d0f |
| `Platform/01-store/ru/spec/01.1-store.norms.md` | MODIFIED | a9017dc934ee43a69e1a04f18fbf878b0f132a3a | 3e49a4f35aaa26890baec87f0e9ad0fae704da5f | 5f06928de7f0cd06b6f56680a1aa93611e18759b4b01eb224927e30dda4bdd3f |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | MODIFIED | 8e59c959ea580d000dc52b8174964025f0459707 | 4542506b17f88c26b3a8b1fb3518c4d454d68e94 | 897ff820f45e3e9dc73653269f018533886f184af11d278787d97bc053605c06 |
| `Platform/01-store/ru/spec/production-acceptance.md` | MODIFIED | 08ee3b6ec7e73477cfb27ef488b114fc7f02b3a7 | a72daa5933cab78fa803995335e53374db0a99bb | 810953867a9e4851087a99e34ba5d10b9ec216e60762d13b6ac2596b43e53e3a |
| `Platform/01-store/spec/01.1-store.norms.md` | MODIFIED | 1f7c0a676d35ea7cd608bc86d3530263e4d0e58b | 4e3aad143f1b2bd77c8314e61d27279a12c342d7 | 4b763a734f8135778057a89affb8dfaf4bb4864d0e07c08947548cdb895a5606 |
| `Platform/01-store/spec/01.3-store.norms.md` | MODIFIED | 1b43b48aa254d8a961884684b4394ce1ace261aa | 779ac8a785f2e0301b7fd5ef276ec290bcb43755 | 17d132ca37dafc97d09a21b027fe8dfb6d99783dd1c0e690161a11e24e111b76 |
| `Platform/01-store/spec/production-acceptance.md` | MODIFIED | 31410786475a41390e0b772fbfab09e0035fc617 | b80949876f2007a05c4ebbc140d6fa46cf659e7b | 998dcf92acad14545ab71bcaa001b1b5d170671e8f80b3f7dc20a11261f821be |
| `decisions/history/platform/id-map.tsv` | MODIFIED | 0a55a56268cbfbfd39cb0f97cfb016349223cb83 | 7229bfb88cb2b63e7edb488d1d308ed83597da16 | 0c361da5de750f4ba3dcb6623d0f8599de5a19101d8c06b6b9a59da7384ffd11 |

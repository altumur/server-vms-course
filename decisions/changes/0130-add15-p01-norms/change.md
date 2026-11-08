# Change 0130-add15-p01-norms

change: 0130-add15-p01-norms rev 1 · lessons P/01 · author spec103 · state review

Publication parent `e9a69b81462261f7f90171472531be94847fef14`. ADR-0130 Addendum (15) items 1–7: the hold of writers obeys the declared budget; the recover phase mark is the first changing step after checks and ownership, with a barrier, and is removed last, and the input is kept until completion; a read at a full disk needs a leader and a quorum; descriptor exhaustion and the `admin.sock` limit; door retries only with the same `id` within the caller deadline; a refusal above the replay limit before admission; budgets are declared and thresholds approved. No new number, route or flag.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/ru/spec/01.3-store.norms.md` | MODIFIED | 3ecae05637a8af665c6bcac208f189b4e820ec8f | 700ddadbfe2c17d9fb0f88a6b68e89c1255feefa | 4454993b2171b7308a7d5c2f55b1387e3287eefb9865701a40d32571085810c3 |
| `Platform/01-store/ru/spec/production-acceptance.md` | MODIFIED | 9ef328e6ad1081ac126d200c6b5b3ecf8b500a39 | 3d5a96bb22270caa9b5a29f13b658333b86756c0 | 1e82b8cf6ce1774a9f1ba414913f335120ffee3aedb00c7a7101dab1e3a8cb5e |
| `Platform/01-store/spec/01.3-store.norms.md` | MODIFIED | 41ed3b0b9faee77ace9de92965231075508eed51 | ef2237285b202f7ee38d75aad59fc38ce52dfa08 | 2e38765dadfbf8ac634a43751ec8ae8a18f3b5904f678bad429413d1ba9616dd |
| `Platform/01-store/spec/production-acceptance.md` | MODIFIED | 54bb90f62569e891a00e98a3099ad08970d93aca | b82f2b25302a0d2db879cd6513b29450e528eb05 | e4ebd1b24162e71229e764cf8bd788042ad8ed91751ef4ed3cd82fe568c9ffda |

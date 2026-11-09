# Change 0133-p04-gone-retention-torn-still

change: 0133-p04-gone-retention-torn-still rev 1 · lessons Platform/common,P/04 · author spec103 · state review

Publication parent `0b43bda3cfb887e52947126d684da671e54bc891`. Task P01.10.5.2 and the Architect's decisions of 2026-11-09: the resource keeps a gone presence file until it has observed it as gone for longer than SLOT_TERM; `TORN_STILL` applies to a capture, not to a release on gone; the catalogue row states that an unreadable assignment row is not rewritten. No new number or route.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/04-controller/forms/refusals.tsv` | MODIFIED | 33f09abb544d5b2ce52c9c10e33218851d0bb6a8 | 618d6a774ecb265243720dd58f4946c207cf7b01 | ce1a9e85f3adb97cc1df858ade6e1f464b6228cd58576a7f851ea65e95efd4d8 |
| `Platform/common/contracts/presence-lock.md` | MODIFIED | 74a13d84aa342bd7c9d06cef984162b8e124454d | 92f94bcc8a1242a46f702b96ad96afe40e06f111 | 651040df10c21437e961a24d30cb6b8ade39aa530dc90ab14a49eb68affe88e2 |
| `Platform/common/contracts/slot.md` | MODIFIED | 2ff25e0b9e8e1f12be41f2d8aa123e6c32676f27 | 39121cec80fa3c04ebcef32c7c4c046d9295a808 | 064475c1cacfbd8e0afc0dbeb094667e1088b13db881e4dc3b78675a0780fffc |
| `Platform/common/ru/contracts/presence-lock.md` | MODIFIED | 4dcd55691a6c6495e9c9f16b9781aac805dcb1ce | d12806d45754cc2c07ca7b5a6f36e4d7f7c1d54d | cf6877531b184d38a86cbd4366f73ae80ad79fd4016032fcd562af7ac0f4ffdf |
| `Platform/common/ru/contracts/slot.md` | MODIFIED | aafa6bc8bc1a4a11debf951964545da98b5c5a86 | ea3831e616b809e317b02abbbffcf205db6280c2 | 7d2f5bb956c49108e52d79912ea939263fadec560518750f1a16843690d6dc81 |

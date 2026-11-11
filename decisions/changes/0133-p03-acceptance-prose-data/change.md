# Change 0133-p03-acceptance-prose-data

change: 0133-p03-acceptance-prose-data rev 1 · lesson P/03 · author run P03.27 (Claude) · state review

Publication parent `6a224c315becee31ff10066ee2b93166b1d830f3`. Task P03.27, part 3г of the readiness audit P03.20 (`decisions/inbox/2026-11-11-P03-аудит-готовности.md`, appendices Г and Д), with the Architect's answer to its question 4 (P03.21: candidates 1–3 of appendix Д through the seam adapter, candidate 4 not taken), over the merged parts 3а (P03.21) and 3в1 (P03.25), ADR-0133 addendum (29). The prose of the acceptance of P/03 becomes data or an explicit «Not judged in this lesson» with its reason (the form of P02.35, `0c9ee948a`); no norm of a product changes and no new requirement is added.

- The READMEs of the acceptance 2, 3, 4, 6 (EN/RU) reference «Testsub process stand» and «Expectation» of the common README instead of their own sections «Scenario boundaries», «Exact preparation and completion», «Exact comparison and boundaries», «Comparison», «Preparation of each scenario», the lines «One scenario takes no longer than 3 minutes» and «Scenario 05 after performed admits 90 s»; they keep only their own roles, rights and exceptions. «the runner» of the acceptance becomes «the judge» in every file of P/03 except `forms/stages*.tsv` (part 3б); «the runner `w2c-run.sh`» of the launcher stays.
- Step 05/5 of `acceptance/6/scenarios.tsv` gets the prefix `@rid $rid` (the dictionary, P03.25) instead of the prose of the precomputed rid.
- The CALL contract of `forms/README.md` (EN/RU): the vocabulary of scripted store replies (`ok`, `again`, `guard`, `unavailable`, `ambiguous`, `badkey`) and the observation `replay_same_id`; `worker-stop` — `stop_unit_seconds`, `confirmed_age`, `release_within_budget`; `worker-capture` — `live_returns`, `final_slot_writes`, the full key; `worker-grant` — `issue_replies`; `worker-confirm` — `answered: null`, `reply`, `unconfirmed_max`, `at`; `worker-slot-write`, `worker-state-write` — `write_replies`, `replay_same_id`; the new port `worker-lease-run` (the ceilings of the heartbeat and the cursor state; the slot has none, the renewal step is «Implementation decides» item 2 of P/03.2).
- The probes of appendix Д: candidate 1 (D4, stop term) — `1/seams.tsv` `s3-stop-slow-unit`, `s4-stop-two-slow-units`; candidate 2 (D1, write cost) — `4/seams.tsv` `s14-lease-run-live`, `s15-lease-run-nobody`, `6/seams.tsv` `s7-lease-run-cursor`; candidate 3 (D5, outcome on failure) — `4/seams.tsv` `s16-slot-write-ambiguous-replay`, `s17-slot-write-unavailable-replay`, `6/seams.tsv` `s8-state-write-ambiguous-replay`. The cadence of the contender marks is already the traces of `contender-writer` («no write before due»). No new reason of the judge norms (P03.25).
- Defects of the audit: 12 (sc. 09 — `@exit 2`), 16 (the check of the `@until` bindings removed with the comparison prose). Defect 15 (`object_spoil` of `RT:68`, `:70`) lies in `Platform/common/acceptance/runner-targets.tsv`, the area of 3в2: handed to P03.26, not changed here.
- The checklist items (EN/RU) P/03.2-05, -08, -10, P/03.4-02, -05, -07, -18, P/03.6-06 name the new seams; «Evidence outside TSV» of chapter 3.4 gets the row of P/03.4-18.

## The 24 places of appendix Г

| Chapter | Place (before) | Closed by |
|---|---|---|
| 3.2 | `2/README.md:46` sc. 09 «code not compared» | `@exit 2` of the step (defect 12) |
| 3.2 | `:92–95` sc. 24 `store_errors`, `stood_in`, silence longer than the window | «Not judged»: implementation choice (store client `wait`); real-time silence — the stage of the system; the window — seams `s16`, `s44`–`s47` |
| 3.2 | `:205` server admission | sc. 22 step 4 (`@exit 2`), heartbeat `server` — step 05/11 of 3.6; the order against the presence lock — «Not judged» (OS race, system) |
| 3.2 | `:207–210` the check of `@until` bindings | removed (defect 16); the rule is «Expectation» `$name` of the dictionary |
| 3.2 | `:212–231` late answer of the issue, races with the stand-in, restart by revision | seams `s12`, `s15`, new `s39`–`s42`; restart by revision — `3/seams.tsv` `s1`, `s3`; the fence of a restart during its start — «Not judged» (reading N3) |
| 3.2 | `:233–237` producers of the marks | removed; sc. 16, 20, 28, 29, seam `s3`, the traces of `contender-writer` |
| 3.2 | `:244–253` key 1023/1024/1025, badkey in six places | new seams `s31`–`s38`, `s43`; the guard key and the place — «Not judged» (not distinguishable at the seam, no place port) |
| 3.2 | `:255–265` five rows of P/03.2-01, -02, -05, -07, -08 | seams `s2`, `s3`, `s7`, `s8`, `s9`, `s18`, new `s37`, `s44`–`s47` |
| 3.2 | `:267–274` slot deadlines | the judge of the slot is P/04 — «Not judged»; the own write — `worker-slot-write` `own_term_open`, seam `s16` |
| 3.2 | `:276–288` first lease window | seams `s12`, new `s39`, `s40`, `s41`; a CAS conflict of the issue with a new send — «Not judged» (the port has no conflict reply) |
| 3.2 | `:290–309` the capture table, the order of names | vectors `slot-name` (`order`, `next`), `forms/slot-capture.tsv`, seams `s1`–`s11`; `names_given` order and 100 nines — «Not judged» (reading) |
| 3.2 | `:311–313` a lapsed foreign row | removed; seam `s3-capture-lapsed-foreign` |
| 3.3 | `3/README.md:65–68` 06-deleted, no growth | «Not judged» (the TSV does not observe external writes; reading N3, N5) |
| 3.4 | `4/README.md:31–32` sc. 37 order of two writes | the edge `let-go-place` → `release-slot` of seams `s1-stop-order`, `s3-stop-slow-unit` of 3.1 |
| 3.4 | `:69–70` first/last heartbeat, stand-in, budget | seams `s1`–`s13` of 3.4, `s1-stop-order` of 3.1, new `s14`; the first heartbeat before the first pass — «Not judged» (reading N1.1) |
| 3.4 | `:74` server admission (duplicate) | removed; a reference to «Not judged» of 3.2 |
| 3.4 | `:78` sc. 03 does not read the heartbeat and its period | the period — new seam `s14-lease-run-live`; the content of the heartbeat of sc. 03 — «Not judged» |
| 3.6 | `6/README.md:76–77` `$rid` computed in advance | `@rid $rid` on step 05/5 |
| 3.6 | `:80` correlation of `queued`/`answered` for every POST | «Full form by door» for the form; the relation to the request of other POSTs — «Not judged» (reading P/06.4 N3) |
| 3.6 | `:89–93` evidence outside TSV: suppression, two contenders, the reaper's CAS | seams `s1`–`s4`, `s6`; suppression, two processes, the reaper (P/06.4) — «Not judged» |
| 3.6 | `:95` `refused` after a call always with `error` | «Not judged»: how an action refuses is the subsystem's handler, not a port; the refusal before the call — sc. 39 |
| 3.6 | `:97` division of `suppress`, form of `by` | «Not judged»: `events-merge` has no `suppress` rows; reading N1.2 |
| 3.6 | `:101–102` the rest of the append — by reading | sc. 07; the rest — «Not judged» (console side P/06.4-07, reading ADR-0054) |
| 3.6 | `:146–147` epoch guard and `not_after` of the order, fencing mid-write, cursor `STATE_EVERY` | the cursor — new seam `s7-lease-run-cursor`; the state guard — `s5`; the rest — «Not judged» (reading N3) |

## Open for other parts

- New seams of `2/seams.tsv` outside the gates of `forms/stages.tsv` (part 3б): `s31-capture-key-1023`, `s32-capture-key-1024`, `s33-capture-key-1025`, `s34-capture-first-write-badkey`, `s35-capture-final-write-badkey` (stage 2, `slot_capture`); `s36-slot-write-target-badkey`, `s37-guard-foreign-renewal`, `s38-issue-epoch-badkey`, `s39-epoch-answer-before-window-end`, `s40-epoch-answer-at-window-end`, `s41-gate-fence-before-accept`, `s42-gate-old-answer-after-rejoin`, `s43-confirm-badkey`, `s44-confirm-silent-off`, `s45-confirm-silent-below-ceiling`, `s46-confirm-silent-forever`, `s47-confirm-silent-ceiling-reached` (stage 3, `epochs_leases`). The new seams of 3.1, 3.4 and 3.6 fall under the gates `seams:3.1:*`, `seams:3.4:*`, `seams:3.6:*`.
- The norms P/03.2-R017…R020 (full keys and store refusal) have no item of the readiness checklist; the seams `s31`–`s36`, `s38`, `s43` therefore name no item.
- 3в2 (P03.26): the new seams change no file list of the filters (no new file); defect 15.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/03-worker/acceptance/1/README.md` | MODIFIED | 96b8fd0651d8a7d6885be15b84323888c52cb9ee | 0ccfebbb79a6556f640858025450e534a21e65d0 | 1e9b524ebe1dcda9796da257413a22ed5ccd66f4e07268f7cd5ead5f452a6cbd |
| `Platform/03-worker/acceptance/1/seams.tsv` | MODIFIED | 479d874fe03e6d629f9c5b12aed26fa93cf53e0b | f9934965ccbbaa616e95c54677c510543675f4c3 | 89598194dee1433c115574a54e9f3c94d1e4df655100970ea98c0a48dbcd33d9 |
| `Platform/03-worker/acceptance/2/README.md` | MODIFIED | 19ac07946187d7b282d7159f15ee994c93fc0bac | 6822429ec24e47131a3a1a40b4bb8cff5ad3100b | d55529b59d8aecaaa6e4a2a065e11cc5bc618ae86fc53f546896510f4ec3e58f |
| `Platform/03-worker/acceptance/2/scenarios.tsv` | MODIFIED | e9aa5abf81fd82354aee466b68b2f795bd08e94b | ea6c9900fefc780f6f69d52a1fce29aa066ba730 | 232fb26770c7f52439b711bdc862464358a95bfa6deba7e6c657bdb85e3262f1 |
| `Platform/03-worker/acceptance/2/seams.tsv` | MODIFIED | 34c944698ec2b0f5083d13679f49ee4d9d20abcd | c1e111749704c99d95f0c5b26b06a042b390463a | cecc16bd828eade8a4964202d5a9f1f97cf833a26861019281b6b02d973b0745 |
| `Platform/03-worker/acceptance/3/README.md` | MODIFIED | 56bb210106d489e65aff9adfb7a07006f6dd0f4a | 7868f4b61687d0b5178bcd79a0e04ff7d2d2c004 | c3de1939f4b00cc3bc0cb9eddece7b0f9c85fa12e1c32884922a9cd9ad7652c5 |
| `Platform/03-worker/acceptance/3/scenarios.tsv` | MODIFIED | 94deb42b79370a28fa018adec12825dff909ea6a | d74599f97066892af7ea917f4d9601ed3462eef5 | a10d79759060c7bf0a5b03f6f53904537da95b499a25fe187aeb4c3c594bea7b |
| `Platform/03-worker/acceptance/3/seams.tsv` | MODIFIED | 26d810632cba654bae5fb731640a755205f31bd3 | 46d931d7d4109e8f76604dbd727c1646fe04fb92 | b07d1556ba7086ba89ec08ecb897e17bcba8a1452e318959c499021035bfc289 |
| `Platform/03-worker/acceptance/4/README.md` | MODIFIED | 5da586442bb99ee5ef07583e64071f870744953d | 1530c27a019b546acc4a7dbc076457f4f9755b58 | e0c2ff9f864cb6b25210902f2f334bad93b8e77f4ba2db6c41af75f1c7fa54fa |
| `Platform/03-worker/acceptance/4/scenarios.tsv` | MODIFIED | 728e1a2356e849ac7d347354e7a7b5e9f4087115 | f81cd886501a42d70f385b37ddb851293838ee9a | eb70fff13b221462f47e863fead0b10a474b97a83c10ba183390677e24e290db |
| `Platform/03-worker/acceptance/4/seams.tsv` | MODIFIED | ae92dec7e6d3b207a88868bd851cdb10ea97a6ea | 0db456c80937844bf6b3bbc5ee5b69df7061d5e4 | b9b4b2b8d97f2c907d0d498f22f297cf33ff06da3de69f5c19fd0b2597ecd4ef |
| `Platform/03-worker/acceptance/5/README.md` | MODIFIED | 36613100314cd6e1f30c6dd8a42f9445503e2c6f | 069557d71fd7ef0a41223a9b8e80bfd8e083b495 | 7250ef93065335ab519a4aff3ec0baa94eea3a4951adb20777e655864d8ff6ac |
| `Platform/03-worker/acceptance/5/seams.tsv` | MODIFIED | c60200f0f71a86f778a84e0579d82800193a2db7 | 9f4dad20483e57104f23c653671dda36c52b156f | 395f09c83315bebb13904a8f4166285a799292dc9adc7f57628cd1543a4fdfca |
| `Platform/03-worker/acceptance/6/README.md` | MODIFIED | 58512697f1c4d4e6da30685cce012e162639a6dd | 1f93f3b052d4a99a6b317075d5e947eea3884839 | 6b88c06f00b62a58d321b436dbf8119b771f186558b6e1e55626b18208254a46 |
| `Platform/03-worker/acceptance/6/scenarios.tsv` | MODIFIED | d60345b2fe4580f44f086b1e0d56120fe1bf25a7 | c2f40c3bbfb7a798d69034df9edeb70f30fc21b7 | 14daadebfba530724aaf53b459bd8098d837689c23eb9d3263e6fde634f1fac8 |
| `Platform/03-worker/acceptance/6/seams.tsv` | MODIFIED | 3857dbe81d6e1094eb7a213d9849b878b4eb1038 | 84a707fe69a16587e9a0f46df3af3f55065148f0 | 972cb3a6400e5fbcd4eee335696d69206d04d1bff3bfa3ccc0e9a964c055fcee |
| `Platform/03-worker/acceptance/7/README.md` | MODIFIED | 07e37f9604f0fa1520aea073f794a5e8a1e4c126 | d6bba1b38a2ecb2d5c234a88398c665a6a73cc8e | cf5f5305ee2005c6e08dcf5a06eac71f642467b8d10fef78220f6af1068de168 |
| `Platform/03-worker/acceptance/7/seams.tsv` | MODIFIED | e88f11d9cc5892378fff9a1d95cde0431c410eea | 903987d55c7bc4c7f81aa66ac0b48fcc42b28699 | ad8114736f141522be6b4f37a4620022f90f7de688f06d660630b83f7472091e |
| `Platform/03-worker/forms/README.md` | MODIFIED | 7a465c50e31a94e098a02b1473faafdac06921b4 | b9f8cd2a248afcc4c2e0ff0ec16c39d39aec8c3d | fa42cd0dd713953b033130cdfe159f0dc2195181dac5e87bfb20605554177b58 |
| `Platform/03-worker/ru/03-worker.md` | MODIFIED | fdba89bc3271d74f5625f4efc75a2f47d53722cb | b44e759b2b8e920959eb7961d1ea71da234ea78a | c3eca20d2984f5690c534fa5aba870fb16ed21eb186ec3c31a155bd269f2e7ea |
| `Platform/03-worker/ru/acceptance/1/README.md` | MODIFIED | 1ac9a985f88890ddda7366c08dc2cb26acdc1d0f | e5686927a50ff956fd9c683cf03a2d5abb919557 | ac628b22b05dc379e93bd7c695c2ed90bf68aae45438c9a0c20a3ffab5eb0849 |
| `Platform/03-worker/ru/acceptance/2/README.md` | MODIFIED | 76504450aee005dfe4d53426830dc676b620fc83 | df12ab84f329a8cb19a2106cc26aeb58bd0dbc03 | c28efc12a08ebae7382a0a5147f277e654eac8464b56b125b91449debe99ece6 |
| `Platform/03-worker/ru/acceptance/3/README.md` | MODIFIED | 0b4312d04fadea2a5ed3fb976e98aec3dbd97d9b | 9ce0518a54ab1bf8ba728672ae2206b36b96280f | bb9b9808d553f100b3c92d4952aaf28174233a1939e6156fbbdf8ad41ae11728 |
| `Platform/03-worker/ru/acceptance/4/README.md` | MODIFIED | 43adb29bef9ac6ac73dfb1e24b91d248878f3577 | 5d90083c2dcf11d28656c8c80a0402bd8611ece5 | 73ec44b22cb73af3206349eaaef0553b93846fe1a724c3c4399b6faa9318895b |
| `Platform/03-worker/ru/acceptance/5/README.md` | MODIFIED | 1b27fe15cbe13fe7a43f7b81dc526332f1bb3d4c | e5d60b78947feff19069d031499b2a772bc91971 | dd0bc7f930a92400d4e3c22ad78145745706b4a2826bc921774d9f4e205db23a |
| `Platform/03-worker/ru/acceptance/6/README.md` | MODIFIED | 6fe5ee3509ba659ad8225431b7eaadcd6372c64d | 333a23a8f30efcac9966af6d537ecff9458d7e07 | 66aa3883851f80daf488761114555f7abc73f987939e23a68f3368dc9e7a473d |
| `Platform/03-worker/ru/acceptance/7/README.md` | MODIFIED | 38bde5a3b27c3c033ebfd50813931669588c8af7 | 8c7c3bd06b624db5802838a3be81cb078b942097 | 6586aead0bb92b2f0a91f33ff4c09f42aee202c837601a12375de09d7e91f6e5 |
| `Platform/03-worker/ru/forms/README.md` | MODIFIED | 10b3460e03de4c62d735c3d4e169930359a1a1b5 | 38b7ae24f10d1776c40e5234b02987e9226b6654 | 7bcde8cd0dbf382897277c0e3d346a8d4d686bcebf8c6c73f3069a74fd5c5e4e |
| `Platform/03-worker/ru/spec/03-worker.README.md` | MODIFIED | 92b2484a12bf938d2b39a75636b30652184627e5 | 00560cb689f4a5743db1e73dedd6e3ce123b922a | 71fd6bfb5a874a854ea16933f0e25816371f6ba0a626e14d36162502a79fbd4f |
| `Platform/03-worker/ru/spec/03.2-worker.norms.md` | MODIFIED | 675a705dd99fd6330f5855aeced62c0a8a120512 | 2cff9f82b964405eb408fc71fca51c6f9424299f | 69a0d9535fafae1950a6c08b2052c1ef3550c8211fb76af96efc66cc81148904 |
| `Platform/03-worker/ru/spec/03.3-worker.norms.md` | MODIFIED | 3eac7297dff7ea50f1a355c113ca668335010411 | cdc74831391824055cdc4340b0b380fc74a2dcd9 | 611e6ea7a2d9e02217a1a41773e945eb9cbc124fd46677404b83cb418694bf65 |
| `Platform/03-worker/ru/spec/03.4-worker.norms.md` | MODIFIED | 00f7ea93ed2509bcda6d966b95914589a6d90a04 | 0480e0903fd62aa3e42da138537e09f9936f7ca7 | 5d698ff4e97e799f249f67ab4a7a5c88fd332624c5a59f69136c0e7c88febf60 |
| `Platform/03-worker/ru/spec/03.6-worker.norms.md` | MODIFIED | ea49f2c91abf86804e6044098402ff400f4b3f74 | 48b766a41812a169e8c91d4cedee33e80f076dbf | 6c8c9debc765423ff9bd05554fafc24577d1d0bd20dd0788cdb3f66d5d1b557e |
| `Platform/03-worker/ru/vectors/creates-key/README.md` | MODIFIED | dcd63272dca27a4c80125f2a0777b7b0cbbd1fff | 3b2ee30e1330141ee26dead3d6e01110bbd99798 | e90e90d0ed867bd343b914b3b097a695155788d0d980dcd5011edc61ffa2834f |
| `Platform/03-worker/spec/03-worker.README.md` | MODIFIED | 050cf4da6f244619e6892e7230cb23985e255aa2 | 639c48cb1e9054382c6ea818c5b4cdb25edf3bc0 | 546773c7151a856a9963babd1a7613bfc2b0d0a72564bd1efd1870b57c74aac1 |
| `Platform/03-worker/spec/03.2-worker.norms.md` | MODIFIED | a125f905a54bd98dc44b75a56bb084be4332f56f | a16c2dca817372564da5e534453194fa9e7d76c2 | 10741d4e9eec11cf9bfa5d315adad94923838e55de43b8d240b510145d3a2771 |
| `Platform/03-worker/spec/03.3-worker.norms.md` | MODIFIED | e4856a4f1b1ed6b8919139321cedbf7739a80edc | 45922725b003be187d43e7229f3981304a5fac5f | d1386ba0838a68df0edc11d55bb4e68a892bd20edcc1efbae7e5160a970a8e7c |
| `Platform/03-worker/spec/03.4-worker.norms.md` | MODIFIED | 03679bb1e9fee0377d73f9702e88223acd411bac | f8c982335241c63cdd2e0cfafedfaf5f30ea44cd | 1a8fa993e01ef009873041e69946612a91470094c478dd2614621e9fe32d6700 |
| `Platform/03-worker/spec/03.6-worker.norms.md` | MODIFIED | bf9c654f8af5b4171a6fa220986c94ebad80207e | ba1dd49800c17a1562a267132b3377c4b77761a8 | 94ece422085f38608c4dde612671f6c926a052eed344a012c71d6468173addec |
| `Platform/03-worker/vectors/creates-key/README.md` | MODIFIED | 3e003dabc5ef709bf351932ca99be56b318f41a7 | b52d80bfc5a98588415049e7e8bc46d90850ece3 | 18cac8c6e6ff72fd9695ddba452559cec7ed618428073b734b2522bcbd319785 |

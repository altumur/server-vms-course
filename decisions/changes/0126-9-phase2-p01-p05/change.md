# Change 0126-9-phase2-p01-p05

change: 0126-9-phase2-p01-p05 rev 1 · lessons P/01–P/05 · author spec103 · state review

Publication parent `d310c4fc37b003cbe862af077eeadc483c0d5f0a`. ADR-0126 addendum (9) phase 2: in `forms/stages.tsv` the gates `tests:<chapter>:<scenarios>` become `accept:` and `tests:<chapter>:<scenarios>:seams` become `seams:` on the same scenarios; the columns `kit` and `parts` and package mentions leave the header and goals. Headers of `seams.tsv` no longer name package tests; the runner executes them through the seam adapter. Stage order, scenarios, physical positions of data rows and `stages.kit.tsv` are unchanged. No new norm.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/acceptance/1/seams.tsv` | MODIFIED | 29116434233cd64c6a573cea3d7cbfc944a961de | e9e8551b0901de431f110f7f55435bfea428bf48 | 98aafe907bd3807e05e64ef4577997c6cb9b1d4385d2f048575c8bf46071f149 |
| `Platform/01-store/forms/stages.tsv` | MODIFIED | f7d320fd294defd6846cf59baf56a2dccbc5036c | 98b9a7d4e57e8e5a9b5920bcc3bf8871eea20bac | 5daaeaf9402bd03009454058071e69ba51a12b26b0c9ffecffbcc6599584fdce |
| `Platform/02-installer/acceptance/1/seams.tsv` | MODIFIED | 7bbe3222bbb1c77d697bec0686d48acfdc3dc9aa | 3939040e9c379376a559e3839468ebcaad4a0388 | a312936ef578142ae0e810e0b58b75ad349f8574baca673cf4d71ca8da97b664 |
| `Platform/02-installer/forms/stages.tsv` | MODIFIED | ac2dc0b74094483952dfc7cf04b3a06098d07ffc | 35f0cb1c1233cb53cdc0ee5f84abf1d04e22373a | 9474c76c67fe52ac3b8732a4dca34484442e62f414ba072ceaf9004907265da9 |
| `Platform/03-worker/acceptance/1/seams.tsv` | MODIFIED | fc514ac32acc1763adae63d26f7959e3d56cc4a9 | bf496b4703d9349ad804904e91385c8b329328b1 | a692f9e0521377c37c48bf2e70bef8b563c9fb4b5b72f0f22433bc97f5302844 |
| `Platform/03-worker/acceptance/2/seams.tsv` | MODIFIED | 66994431f0c91bb63982d62bd1eb5bcfa3d30ffb | e535edd7449cdc0459433e549c26b2700165f718 | 85c863524b43cb70769d9c296c502de3bca9f8b2a173958c0b8ff4e2e291b124 |
| `Platform/03-worker/acceptance/3/seams.tsv` | MODIFIED | f171b97d64b0e2cbfade6f03413a471da946acfe | aaa2ac47f27d50ec64b1d31e4599a5966d4a747c | 515cc38db4afe8015684e8d813a941941210bfee4170c37385fa85663ff570ae |
| `Platform/03-worker/acceptance/4/seams.tsv` | MODIFIED | 4822dd71c3355206e6a19639412165a2bf82b06b | da3714b16fc8c8531899136369397d2470642e21 | dabe981c257914a6c81ea6d90d262fb3744525efeecd24d672dfd573ea10efba |
| `Platform/03-worker/acceptance/5/seams.tsv` | MODIFIED | fe2c3ee7708ec46ba5e1256edb750160c3e4d9fd | 86bff43e0c15dc4df7132fc29f217fdfda306200 | 1f2cc4d90e5aff369f9d9834556be7e64039f3bb8ffd58c0040e0222e6c81f52 |
| `Platform/03-worker/acceptance/6/seams.tsv` | MODIFIED | 08a3055c2f6164bf67d8730cc003457cf5721732 | 67310dcd9d2ab926f82dc6f25793daa76f32345a | adaec27c1f202ba1befe20c82022225556fbe1eea1614504a67f0e8826125824 |
| `Platform/03-worker/acceptance/7/seams.tsv` | MODIFIED | 168e94d40bc60c8063aab4be9ab013c6fd5c4b33 | 95c5af9e3730246236bc658b4a82daca2283fd3a | 455e75cf55c8b8c38c796e6a8716983acab16471e9124ae7aca1375027db19c7 |
| `Platform/03-worker/forms/stages.tsv` | MODIFIED | 19977471d9ac02aefcea96a6f261a0efa4a5fe3f | c04888db8b09bb8f4bf48fc602d50e6a209d05b2 | bba76a321acf42829f5637f51ff0d4ab07d99dfe8f64a0111f06936d95c69a03 |
| `Platform/04-controller/acceptance/seams.tsv` | MODIFIED | d7d24dbfb783f5c62c65e6bf5d6902dbd3daca9b | a55ce48bc8542d93faafac4029e459ebe56bd06c | f8520622e115debf5a4f052eb915a4f5769abb4e16a5cb1e5e74b912ab17d758 |
| `Platform/04-controller/forms/stages.tsv` | MODIFIED | 4251c2c29665f0288a9aa42cd3e74ce0909963c9 | 8d76e8b01583a7511ed1f63cbf35cf1728c38e64 | 3a030bdad6d02e5bba015b268813bd425e01434eaab94c75b493dc8855d037c5 |
| `Platform/05-resource/forms/stages.tsv` | MODIFIED | 8b91581e712ba41152f27d03c0b99cf5b9248b7b | d565df2e0f9fd3b69e6ccbcdfab09fe131771f5f | 3ec5b2cdea8bdbfcd04f866ee533521ca020a97473802a0a6c217a41e7d85971 |

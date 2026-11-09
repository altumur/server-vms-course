# Change 0135-judge-lesson-norms

change: 0135-judge-lesson-norms rev 1 · lessons Platform/common · author spec103 · state review

Publication parent `c062bfc919b75cd9b12288d8283b38bd7a30f0ec`. Task P01.29 (ADR-0135 addendum (2)): the common acceptance becomes the judge's lesson. The new lesson P/AC adds the norms and the instructions; the common README, PROFILE, the TLS README and the README of chapter 3.6 carry the decisions of the Architect (Q1–Q26): the readiness rule, the terms of the stand, the comparison, the failure classes, the report and secrets. A rule is the correct behaviour of the judge; the current runner is corrected by a separate task after the trial and is not in the credited pin (ADR-0135 addendum (1)).

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/03-worker/acceptance/6/README.md` | MODIFIED | f496b0150eea9b7aaf9baacf3ad0d9387c2915d6 | 58512697f1c4d4e6da30685cce012e162639a6dd | 8dd89defab5195aff7053d3c1b0bef665ac59e4cb79b38d1e5ae09a94910795a |
| `Platform/03-worker/ru/acceptance/6/README.md` | MODIFIED | 8c33bebb72b2e892c5fe1e935fb9b69ae9027347 | 6fe5ee3509ba659ad8225431b7eaadcd6372c64d | afdf2eac3d16520cf05599d6ac78288a8603080e42ae91a5912a1b97bab03c83 |
| `Platform/common/acceptance/PROFILE.md` | MODIFIED | 4fe9e359b033a4dd2019ba5848fd1cc63c17aae4 | ace202baf9a37d115454ad4a71a985c2eed4ed74 | b919915f65fb513c5c2787ddc8b0f430e3dda8c27e131ab35085ab1761afd515 |
| `Platform/common/acceptance/README.md` | MODIFIED | 781b4f8024d401ee462165bb0e1339b713fab36e | 46b8013b2bcf5861ad29dad81265a0aa1eebe3ac | 46bcfa49e61f8bc618e5e14350249882497ca551af03a15e30bdd5621b2bb082 |
| `Platform/common/acceptance/tls/README.md` | MODIFIED | 842777e7f50a556daefb9d8a58f851b6f713fbbd | 3d066aabc73b4a3bb55f30d37a9b71b5144ea821 | cb3579ba100de661b16016c7958c75d563965d4dfb7774240f410f5ba4e7ae91 |
| `Platform/common/ru/acceptance/PROFILE.md` | MODIFIED | 749d19d53178c0bdd076cc311d2690d904b7adf2 | f6119545ad5b5bc276f3c4244028860134a033bc | 82b1467598cc30f6936d40b9acb8913de27554c59596e44878d9f52bfdb2c832 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 4f71295b6e9b7215136e3f7c8b2466645bd42897 | 397479abec80b9f5e158326755b5d3807fb0927d | 9bbbb51eff9f7c02b88757cec5c63bdc6a8c4ec6c16776374195294e3cc93d93 |
| `Platform/common/ru/acceptance/tls/README.md` | MODIFIED | 766e6f7f691bad05610ab73288e0be3bdd857a97 | 53c758e6c03ba0a85b9c6101a187c18973cc1187 | 5ac35d75a0cc6b9e0266f9355cd9c1d881bc88d0b1cef681e30f8ccc37627569 |
| `Platform/common/acceptance/spec/acceptance.norms.md` | ADDED | - | cf5a3584c04865757ccdea14d4c88f264c938286 | 895eb2397c0064c66239970127265cc4cfe05b8503cf41876017d3585bd219dd |
| `Platform/common/acceptance/spec/acceptance.README.md` | ADDED | - | 22d687881f54df0ca7af8ce6438812a1860f1e72 | 65fb26e72409cc88302da16b98609e28ffd8665b8928f5dbba0aa56aa5847cd0 |
| `Platform/common/ru/acceptance/spec/acceptance.norms.md` | ADDED | - | c2ddbb07619845726f8f9423aed76c3f633682bd | c2efc4e6cc167210784b1d4e6be0f85f2b8d76a4ee8370aab02d774d6a9332a2 |
| `Platform/common/ru/acceptance/spec/acceptance.README.md` | ADDED | - | 09d6eceb648b0a170e185d2cce19af1dcbb87a4f | f396775a211691e2c8cce317380dc32e7c9dbefdafb73302bcc3107cdbc2e742 |

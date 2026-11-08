# Change 0133-owned-sleeps-case-split

change: 0133-owned-sleeps-case-split rev 1 · lessons Platform/common,P/03–P/05 · author spec103 · state review

Authoring parent `b2766e561baf77280d5494af31f9e0ce87c1c2ef`; normal publication parent `28a49b2bcd07266897261476f63a99149675efc8`. ADR0133 Addendum4 and explicit Architect case/Sleeps disposition (a1a89639), within existing normative-definition task3cf538.

Split five case-specific Sleeps sections in both languages into ten same-directory sleeps.cases.md judge-only files. Case instruction bytes and all case numbers/durations/reasons remain identical. Original README headings retain public common wait-protocol and judge-only case links; SDK tails outside those sections are preserved. The common README pair changes only the location phrase for case reasons. No generic wait behavior, new case, field, budget, working flag or requirement ID is introduced.

All changed artifacts are unanchored README/case documentation; normative requirement units are unchanged. Ten new *.cases.md files are judge-only under the selected whole-file filter rule. Actual Runner location binding is owned by Runner and not proved by Source publication.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/03-worker/acceptance/2/README.md` | MODIFIED | 8ccf889ea28896439391f293e3a539485c03cbbc | 19ac07946187d7b282d7159f15ee994c93fc0bac | d309c916132c071294e1b0baf915662baf11e158bd1bd2de905af382329e8dd3 |
| `Platform/03-worker/acceptance/2/sleeps.cases.md` | ADDED | - | ca2823682830b34fffe167ff97d0e310cd21ca61 | 65699e5faee2604a413c6ec2e69d976f98acdd350b2d5943bef7f0b7499c69b5 |
| `Platform/03-worker/ru/acceptance/2/README.md` | MODIFIED | ba8e82fdc1bb5a92918752e3077f93ccb524bc6a | 76504450aee005dfe4d53426830dc676b620fc83 | 2a53fbd2f5fe51105578eedcffb09e36e13b48a3b9813d61a228298cf416a954 |
| `Platform/03-worker/ru/acceptance/2/sleeps.cases.md` | ADDED | - | 10f614443ec73be2dc33d044a93f812545d0c1ac | 3034cb251d704dac62c38e51376cc34db72857a6a2b4697322056d523445d589 |
| `Platform/03-worker/acceptance/3/README.md` | MODIFIED | abbc1a72827316d898f218c6ea911c0a317f195d | 56bb210106d489e65aff9adfb7a07006f6dd0f4a | 3495280babd1a4fd248790fa00b950172dc05041b21148bae19c5507ac541063 |
| `Platform/03-worker/acceptance/3/sleeps.cases.md` | ADDED | - | f8d0a0c144d2d1fa6d18eea366c6b50f5b376cc2 | 26375cf6cc0fe2ac8e217928ebb3f7065b1b0e1573639da89a6e69e8c071e539 |
| `Platform/03-worker/ru/acceptance/3/README.md` | MODIFIED | 4965a8c5927fa3a7d355657b62ff484c42dcbf0b | 0b4312d04fadea2a5ed3fb976e98aec3dbd97d9b | 8c1d8ac21c088ac5111fdd8f9e7aa4a1ba49cf5915b613df3db50f11758b9d08 |
| `Platform/03-worker/ru/acceptance/3/sleeps.cases.md` | ADDED | - | d2ea0d560842eb7ca01e7306dc6c852dd7f2eb23 | 2e4f42369b53a77b0850aea0f7dacb8e2498c573f90537408bc4e141f7192776 |
| `Platform/03-worker/acceptance/6/README.md` | MODIFIED | 485c79b31c29725ab59563572f160d968d98e06f | f496b0150eea9b7aaf9baacf3ad0d9387c2915d6 | d8c7618b8decd62c1839f0af78105228120951501af44b4186562a72d432d6ad |
| `Platform/03-worker/acceptance/6/sleeps.cases.md` | ADDED | - | 26b5f136ec924a37edcdd474d1162c7497bfb638 | 0c87d3ef4bbd2f4f97a6917930a4c8620c3dcbe7e9b8caabc3e6af0e0ecfd3bf |
| `Platform/03-worker/ru/acceptance/6/README.md` | MODIFIED | f57dd70014d3886e2eb0e7b5037f481f645075fb | 8c33bebb72b2e892c5fe1e935fb9b69ae9027347 | 78c7514c70400f3390d22a7db224bbce5b36d929bc18daad3b794d22ac55db3c |
| `Platform/03-worker/ru/acceptance/6/sleeps.cases.md` | ADDED | - | d15d42f2da81d6e448bccb19a49315bdddae7669 | cf889ca27421f6ff33e216cd1add58e1eafe9628c4ca0f2dcdd5145f3f2718b8 |
| `Platform/04-controller/acceptance/README.md` | MODIFIED | 72e4f299e6920c87c875d090dff1e462b7d87335 | 85abe1c458d19db7ed589c5af6eedd937bcb7d6e | 02d4682be1fa113da3aeac21faa7d5715cfa2e3550ce70ffcb4a007023ed3a40 |
| `Platform/04-controller/acceptance/sleeps.cases.md` | ADDED | - | 474e662a73a48bc30062196e445e8f33edbf9c31 | 07353413729fdcc6eb979d4600d52f453a0f80c26d685f0718396219657bce3f |
| `Platform/04-controller/ru/acceptance/README.md` | MODIFIED | 76b425cde5d8fcb0aaa3bb3ea89b20e967118e78 | be78e16b45015169e2c7f693c0908d213ddc2a79 | f30ff546aba0de19ae9c7fb6a2ba05dc2a1799efcc841afd5b138afb7594e0c0 |
| `Platform/04-controller/ru/acceptance/sleeps.cases.md` | ADDED | - | 651857271610671e2d24f9eb389941c7c57960bd | fa886d3c54f7f13e6cd18d1c69988c2901bc0d476f58013890d05bb3393c3fd1 |
| `Platform/05-resource/acceptance/README.md` | MODIFIED | bdd97b0b9f8131f72f00d84eed17431ac4bc1500 | 42660fd6842d1f9a2da3700184684d8695e3511a | 215f84ba769b88b9833a43e6a8eae13103c3f737a976ec07763e8bc3471d3088 |
| `Platform/05-resource/acceptance/sleeps.cases.md` | ADDED | - | 47e97d6a296994864db466859c8cd5c654cbbb3a | d5253e7799387717d8915d2840d3b5929b09503f48e6156090b13fda9e1e50fe |
| `Platform/05-resource/ru/acceptance/README.md` | MODIFIED | 0548fabdd10da07610e86a271288bf7593296bb9 | 6aae24aa23075a025c407d8370ee8d155d682dbd | 77cdf90a83ac5027eb2fc9795dee62f031cd2bf912f2f4e37f6205b605e2c630 |
| `Platform/05-resource/ru/acceptance/sleeps.cases.md` | ADDED | - | cb565b222617416177483ee2cc99a5ca563561b7 | 0d7bfff6e8777078ba35fc3f95a853c48f4838ab555197a4e87062b404603257 |
| `Platform/common/acceptance/README.md` | MODIFIED | 1d93f62d612c9d57b634a10d21083fd36c190b32 | 1ab37eac8abdc13e315e4b2ffd0796a11a06be66 | 1c2a9fa2acb1bb65f6d25fd11229eff12ac8ffb78d44bedbc8d9e2dda8cdb495 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | fb0552fa7341817c9f830e4dd5c3c914e70d9c72 | c430c5ea39f8e7b616dbc0922d970ebf083360b7 | cf88fa635b1d2d9158f172e29490d0fd1d39bce2568fe938c491267a155aaf04 |

This change record is Source/judge provenance outside model input. No filter/export/SourceREADY/GATE, native/model execution or old proof replay is claimed.

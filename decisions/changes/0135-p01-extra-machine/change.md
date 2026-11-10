# Change 0135-p01-extra-machine

change: 0135-p01-extra-machine rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `20b617e04afbf6f7aad12cb3aec4b021a98ecd0b`. Task P01.142, ADR-0135 addendum (8) item 3; review P01.138 B1 and the Architect's answer on P01.142. The probes of `P/01.1/extra` get a machine form: `forms/extra.scenarios.tsv`, one scenario per probe in the grammar of `scenarios.tsv`, run through the column `tables` of the routing; `forms/extra.tsv` stays the inventory, with the column `kind` (`probe`, `precondition`). New words of the closed dictionary of the common README (EN/RU, M and J): `@wire`, `@halfclose`, `@rep(N,<text>)`, `@profile(<name>)` / `@profile+1(<name>)` (the name `@key` is taken by the idempotency key), the expectations `<code> @close …` and `@noreply`, the term of `@noreply` 10 s. P/AC-R030: `no_machine_form` only for a probe without a scenario (now `extra-forwarded-list`, until the stand of P/01 has the trust profile of acceptance 06, and `extra-full-key-declared`); `precondition:<id>` for the other cases when a precondition is red (`extra-parameters`). `extra-full-key` is the platform norm KEY_BYTES by steps. No numeric value of a norm is added; the numbers of the steps are the stand parameters of P/01.1 N5 and the constants of runtime-constants.tsv.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | 37835175f10623be0cb4ae4053cc21fa451f0394 | 059292e55b28a096a131a78935b1569f9f362363 | 0dfa2aef8137fc0209f290397c961a1eba89d1b34565458e8c4c1f49d416a7cb |
| `Platform/common/acceptance/forms/extra.scenarios.tsv` | ADDED | - | 5c36ef143ed828bddba897c742eb40817e3a33f9 | ff6800fec953ca56b23c6aea31835566a334472703a5040e3fc6071f1d868b94 |
| `Platform/common/acceptance/forms/extra.tsv` | MODIFIED | b7c7fc584563132c726731526ab71a05d1c90c1d | cffe209df11d5493d7c5c84db2089a6a18489863 | 7bc2349d7fdd4e07ee767f2e01684a77ef219e1be20fb09a9b53d2cc6e5c81f8 |
| `Platform/common/acceptance/forms/targets.routing.tsv` | MODIFIED | a5bb031e6460796a7f9ec36c5552dfb7f7ff2e3c | 5b710734cd32c1062ecbdeb14d1a51b23de70b6f | ccbc20bed66ed695f7f2a7250392a43ced94f22eb1a7871875ca8b415d9a6de6 |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | ca7a9563ff64365e0a2c4f3e03ba846e1fc9a438 | 6ec3fd779c79d37b23eb919c221525c171283f0c | 158c3fae0dc68d45be88690f4e0b2c5fb33ff5fc9eed35c185f2e6747e0b0f99 |
| `Platform/common/acceptance/spec/acceptance.norms.md` | MODIFIED | cfe76549872fa3fa7e5d2679a795b5ebb92b8587 | b167b193de05c77d89025bb59175195e7a7c8fe9 | fb8ea9ec2b3a63fb3500ddc8dfa1ad44303909515b6d76be2af5d22b53b50796 |
| `Platform/common/export-model-filter.json` | MODIFIED | 27efe802ef20d3b2284bfdbb190d42b85c596e2d | 55de3369c9966cab03a3ae82275fd4290bbd4b9e | f5582048ee2e1e8f5708f5993db4ee94bcb773665bb84d6d5f437ab096812b14 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | 8daf30d6822ca571fe981b4138b4abc914e99e07 | f868b4547c28db21b8d728d949d8bd1da5f36eae | e062fa5cc2ea6a273c2a70b033b68fd5c4de978b3f4183988a0fef00b57cc7dc |
| `Platform/common/ru/acceptance/spec/acceptance.norms.md` | MODIFIED | 75b19306968533131b40acd150500f6b0ec9d023 | 3b95b4df4aed426a0fab6034cdceb958d8494b9f | eed1c90cad44a3986802ad37e6f3412b35cb54a1e65c502ebc81227987a5ea0d |

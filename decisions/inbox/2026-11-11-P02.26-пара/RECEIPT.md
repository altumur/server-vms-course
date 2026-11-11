# P02.26 — пара выгрузок с паспортом M и J-вход (окно run, Claude, 2026-11-11)

Задача P02.26, ADR-0133 #27; пара общая для попытки 6 P/01 и для P/02 (Архитектор, 2026-11-11T08:03:53Z; ADR-0133 доп. (46), (47), (50)). Образец — P01.121. Рабочий каталог со всеми доказательствами: `/home/pilot/run-p0226-pair-20261111`, ход работы в `STATE.md`.

## Идентичность

| | значение |
|---|---|
| C | `4694190a178f0706d0bf8ad571991bae3c87c8bd` (origin/main после P02.42, P02.44, P01.155) |
| M | `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae`, дерево `24d47d81…`, 769 файлов, ссылка `refs/heads/model` |
| J | `31d8f11d253ca8a3b47bf6f03f275493c449d798`, дерево `b4fe7e91…`, 3515 файлов, ссылка `refs/heads/judge` |
| Пара | `pair-4694190a178f/{M.git,J.git,PASSPORT-TRUSTED-ONLY.json}` |
| Фильтр M | blob `50eb811c…` (`Platform/common/export-model-filter.json`) |
| Фильтр J-входа | blob `31e6150c…` (`Platform/common/acceptance/judge-input-filter.json`) |
| Паспорт M | `passport/PASSPORT-M-bf8462085c08.json`, sha256 `ccd61598be4d50b3ed4ddc35088b458c10a34a3ba66d0be612b0d43de27a5ec2`, формат `m-passport/1`, 769 файлов, `files_sha256` `42afe7d1…` |
| J-вход | коммит `49e622795ca96b2e73904f1da5d203f2d103b2d5`, дерево `6a3dce09…`, 1985 файлов, ссылка `refs/heads/judge-input` |
| Паспорт J-входа | `ji-4694190a17/PASSPORT-JI.json`, sha256 `a1a77c6527c3d87694cd2689a4296ffbcc6a865820883b6ac310aee5e34e4ef2` |
| Оператор пары | `b7_export_pair.py` версии P01.88 и P01.121, sha256 `654d246d…`, без правок |
| Оператор паспорта M | `m_passport.py` `c19d8f35…`, проверка `check_m_passport.py` `4c23afc9…` (P01.131), без правок |
| Оператор J-входа | `operator/judge_input_export.py` этого каталога, sha256 `4eeef782…` (две правки ниже, прежняя версия `0c86ea32…`) |

## Как получено

1. **Фильтры и их ревью.** Между ревью P01.106 (пин `b603f6479`) и C фильтры менялись в восьми коммитах. Всю дельту прочитал другой поставщик: P02.37 (Kimi) — правки P02.34, P02.41 (Kimi) — вся дельта `b603f6479..e3f65994a`, Б 0, С 0, М 0. После `e3f65994a` фильтры байт в байт прежние, а в Platform 17 файлов изменено и ни одного не добавлено и не удалено. Поэтому ревью P02.41 покрывает C. Сводка — `FILTER-REVIEWS.json`, перечень источников — `SOURCE-CLOSURE-P02-26.json`, разрешение — `AUTHORIZATION.json`.
2. **Полный check_spec на архиве точного C:** exit 0, ERROR 0, EXCEPTION 54, `PHASE PLATFORM_CURRENT PASS`; в трассировке 123 пункта норм на этапах (P/01 — 55, P/02 — 68). Вывод — `CHECK-SPEC-C.out`.
3. **Сухая проверка оператора пары** (`preflight.py`): собственные проверки оператора до записи — состав C, разметка фильтром, граница случаев, лексическая защита. Всё прошло. Вывод — `PREFLIGHT.json`.
4. **Пара** выпущена одним запуском оператора (`RUN.json`, exit 0) и проверена `verify_pair.py` (`VERIFY.json`): все проверки верны. J равна Platform C плюс маркер, M равна ровно `model_and_judge`. Таблицы случаев, сценарии и швы в M не попали. У каждой выгрузки одна ссылка и один коммит без родителей, физические объекты равны достижимым, `fsck --strict` чистый.
5. **M ⊂ J побайтно:** 769 из 769 путей с тем же режимом и blob (`M-SUBSET-J.json`). Один blob M совпадает с blob пути только для судьи — общий манифест `testsub` (`common/data/testsub/testsub.subsystem.yaml` и `02-installer/acceptance/2/puts/testsub.subsystem.yaml`), как в P01.121; ADR-0133 доп. (4) п. 6 это допускает.
6. **Паспорт M** выпущен оператором `m_passport.py` на M.git пары. Контроли `check_m_passport.py` (`passport/controls.out`): M как есть — OK; J — 2746 файлов «not in the M passport»; подмена байтов, пропажа файла, ссылка, лишний `extra.scenarios.tsv` и чужая M (`d5bd29dd`) — красные.
7. **J-вход** собран оператором `judge_input_export.py` с двумя правками (ниже) и проверен `verify_ji.py` P01.121 (`VERIFY-JI-orig-rules.out`). Его правила прежние, поэтому он отмечает ровно пять файлов, которые пропускают правки: четыре `.js`-фикстуры `testsub2` и `verdicts.tsv`. Разбор каждой отметки — `verify_ji_p0226.py`, итог `VERIFY-JI.json` OK. Вне J-входа из каталогов целей остались 148 файлов, и каждый исключён фильтром: 140 файлов корпуса `spec_verdicts` и 8 схем check_spec `01-store/forms/*.tsv.schema.json` (OBSH.39). Объекты J-входа: 2044 физических = 2044 достижимых, `fsck --strict` чистый.

## Две правки оператора J-входа

Принятый оператор `0c86ea32` отказал на J этой пары. Обе правки сделаны по ответам Архитектора; ревью дельты другим поставщиком — P02.45 (окно judge, Kimi). Дельта — `operator/judge_input_export.diff`, тесты — `operator/test_judge_input_export.diff`.

1. **Класс verdict** (ответ 2026-11-11T09:23:54Z). Прежнее правило отвергало любой путь с подстрокой `verdict`. Из-за этого не проходил `Platform/02-installer/acceptance/1/verdicts.tsv` — таблица слова движка `verdicts` цели P/02.1/load, которую P02.34 включила в J-вход. Теперь корпус — это сегмент пути или основа имени файла `spec_verdicts` или `legacy_spec_verdicts`; правило `mutant` не изменилось. Таблицу не переименовывали (тот же ответ).
2. **Класс code** (ответ 2026-11-11T09:28:46Z). Прежнее правило отвергало четыре `.js`-файла `Platform/06-console/acceptance/5/inputs/testsub2/` — фикстуры статики подсистемы, вход `# beside:` цели P/02.3/put. Теперь класс code не применяется к файлам внутри `acceptance/<n>/inputs/`. Они копируются байтами (ADR-0133 доп. (4) п. 8), а проверка на имена прежнего судьи (`FORBIDDEN_TEXT`) для них остаётся.

Контроли: новый набор — 21 из 21 OK (`OPERATOR-TESTS.out`). Новые тесты проверяют, что `acceptance/1/verdicts.tsv` проходит, а `spec_verdicts/`, `legacy_spec_verdicts/`, `spec_verdicts.tsv` и `Spec_Verdicts/` получают отказ. Они же проверяют, что `acceptance/5/inputs/…/app.js` проходит, а `acceptance/1/probe.js`, `probes/x.py`, `acceptance/inputs/x.py` и `acceptance/1/x/inputs/y.js` получают отказ. Прежний файл с 19 контролями на новом операторе — 19 из 19 OK (`OPERATOR-TESTS-ORIG19.out`).

## Хеши доказательств (sha256, первые 16 знаков, каталог `/home/pilot/run-p0226-pair-20261111`)

| файл | sha256 |
|---|---|
| `CHECK-SPEC-C.out` | `cfafbfdd5b46cda2` |
| `PREFLIGHT.json` | `58c6bfa0bd289c96` |
| `FILTER-REVIEWS.json` | `f2b978416fdb66ea` |
| `SOURCE-CLOSURE-P02-26.json` | `72b2ced5fe6416b9` |
| `AUTHORIZATION.json` | `5de4ce203918fbed` |
| `RUN.json` | `f5bc0344b8b3698c` |
| `VERIFY.json` | `7fe7e3939b28b6f3` |
| `M-SUBSET-J.json` | `67df5702083f26f7` |
| `passport/controls.out` | `38625667a435df18` |
| `OPERATOR-TESTS.out` | `e51e7a8bef4e65e5` |
| `OPERATOR-TESTS-ORIG19.out` | `4054bb87b22c8c4c` |
| `JI-RUN.out` | `4bf4fa96c6335513` |
| `VERIFY-JI-orig-rules.out` | `36ab9a163225fcb0` |
| `VERIFY-JI.json` | `a30e54307f5ee328` |
| `pair-4694190a178f/PASSPORT-TRUSTED-ONLY.json` | `54ae165fe353b5cd` |
| `delivery/setup.sh` | `e24dd301e82c8f71` |
| `delivery/verify.py` | `7bd24944695a01fc` |

## Пределы

- **Доставки на стенд и канарейки нет.** Каталоги `/srv/b11-isolation/{model-specs,judge-input}` открыты только root, у окна root нет, ops103 закрыт. По слову Архитектора (09:33:51Z) доставку и канарейку берёт P01.157 представителя. Сценарий для запуска от root готов: `delivery/setup.sh` и `delivery/verify.py`. Он раскладывает M и `PASSPORT-M.json` в `/srv/b11-isolation/model-specs/bf846208…/` (как P01.131.2), а J-вход — в `/srv/b11-isolation/judge-input/49e62279…/`. Права те же, что в P01.121.1. Он сверяет каждый файл и паспорт M на стенде и делает опись соседних каталогов до и после. Канарейку линии продукта (обход P01.129 с временной строкой на M `bf846208`) и линии судьи на J-входе `49e62279` он не делает.
- Проверки пары и J-входа писала та же сессия, что их выпускала. Независимая часть — ревью фильтров (P02.37, P02.41) и ревью дельты оператора J-входа (P02.45, после сдачи).
- J-вход P02.25 (`f48e249c`, 1985 файлов на `9305b42a9`) собран рецептом представителя на другом C. С J-входом этой пары его не сравнивали.
- Строк `trial-views` на новую M и J-вход нет: их ставит развёртывание.

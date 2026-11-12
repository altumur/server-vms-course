# P01.180 — пара выгрузок и J-вход для попытки 7 (окно run, Claude, 2026-11-12)

Задача P01.180, ADR-0133 доп. (57), шаг 31 плана. Образец — P02.26, операторы — принятые версии P02.52. Каталог со всеми доказательствами: `/home/pilot/run-p01180-pair-20261112`, ход работы — в `STATE.md` этого каталога. Конвейер выполнял фоновый агент окна; выводы ниже окно проверило само.

## Идентичность

| | значение |
|---|---|
| C | `41a9493fb08c293a570c006019995a64a599f68b` — origin/main после P01.200, то есть после P01.175, P01.177, P01.176, P01.229, P02.52, P02.57, P03.26 |
| M | `be48405e645b49985d35efc42b6d61c2f304c4d8`, дерево `6bee0529…`, 786 файлов, 892 объекта, ссылка `refs/heads/model` |
| J | `605f12bb9b4664e5e7e9517722fcf5464faf219b`, дерево `07f7d8d0…`, 3558 файлов, 3882 объекта, ссылка `refs/heads/judge` |
| Пара | `pair-41a9493fb08c/{M.git,J.git,PASSPORT-TRUSTED-ONLY.json,FILTER-M.json}` |
| Собранный фильтр M | blob `0aa6d54717d8b51bc4b0ce014908ec5f171bdb3b`. Источники: общий `export-model-filter.json` `517bbd00` и `forms/export.json` уроков 01 `a166c62d`, 02 `8566de78`, 03 `34902d0b` |
| Собранный фильтр J-входа | blob `9450e7ccc9f5452696890cf35c24efa00164bacf`. Источники: общий `judge-input-filter.json` `1c7e2f5e` и те же три списка |
| Паспорт M | `passport/PASSPORT-M-be48405e645b.json`, sha256 `0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01`, формат `m-passport/1`, 786 файлов, `files_sha256` `5407e514…` |
| J-вход | коммит `9daca227dbc08ce3d4a14c6d47c6ea3f94e55034`, дерево `8df57f6e…`, 2117 файлов, ссылка `refs/heads/judge-input` |
| Паспорт J-входа | `ji-41a9493fb0/PASSPORT-JI.json`, sha256 `e4f43d403a2a2093e4b3fd72f1cc59c4b00f9a803c807c16684322d8a715766d` |
| Оператор пары | `b7_export_pair.py` `32672672…` (P02.52), без правок |
| Оператор J-входа | `judge_input_export.py` `c046b5ac…` (P02.52), без правок |
| Оператор паспорта M | `m_passport.py` `c19d8f35…`, проверка `check_m_passport.py` `4c23afc9…` (P01.131), без правок |

После выпуска в main вошли два коммита, `efc7e74f8` и `298891558` (`m_form` и `test_m_form`). Platform они не меняют: `git diff 41a9493fb origin/main -- Platform` пуст. Пара по содержанию соответствует и текущему main.

## Как получено

1. **check_spec на архиве точного C:** exit 0, ERROR 0, EXCEPTION 54, `PHASE PLATFORM_CURRENT PASS`. `export_unlisted=0`, по 3558 записей экспорта M и J, `stage_norm_items=202`. Вывод — `CHECK-SPEC-C.out`.
2. **Проверка оператора пары до записи** (`PREFLIGHT.json`): состав C, сборка фильтра из уроков, разметка, граница случаев, лексическая защита — всё прошло, вырезать файлы без записей не понадобилось. J — 3558 файлов с маркером, M — 786, снято 157 таблиц случаев.
3. **Дельта фильтров** от C пары P02.26 (`4694190a1`) до C (`FILTER-DELTA.json`): добавлено 53 записи, убрано 10, изменено 109. Дельта поделена по шагам первого родителя main (`delta-steps/`), каждый шаг сверен с дельтой вводящего коммита (`delta-intro/`). Вместе шаги покрывают все 172 записи. Ревью каждого шага:

   | шаг | что меняет в фильтрах | ревью другим поставщиком |
   |---|---|---|
   | P02.49 | 2 записи `engine-code-rules.tsv` и схемы | judge, Codex (`478304eb5`) |
   | P02.51 | 6 файлов реестра и списков 01, 02 | judge, Codex (`365c5fc6d`) |
   | P03.26 | 4 файла реестра и списков P/03; 109 записей J-входа из `exclude` в `include` (P/03, векторы common и 06-console) | judge, Codex (`1c0de0fc4`) |
   | P02.57 | `code-rules.tsv` P/04 (M — да, J-вход — нет) | judge, Codex (`/tmp/P02.57-judge.txt`, копия в `reviews/`) |
   | P01.176 | 9 новых форм и проб P/01 в `forms/export.json` | judge (`2a4bd5102`); поставщик в отчёте не назван, по ADR-0134 он другой, чем у автора (Claude) |
   | P01.229 | деление общей приёмки на файлы тем, перенос форм в урок (22 добавлено, 19 убрано, в том числе `ru/`) | judge, Codex (квитанция P01.229, попытка 3) |
   | P01.228 | 9 схем `*.tsv.schema.json` | **ревью другим поставщиком нет**: автор Архитектор, принял владелец. Все 9 закрыты с обеих сторон: `judge_only` в M, `exclude` в J-входе |
   | операторы P02.52 | сборка фильтров из уроков | judge, Codex (`27b0dbab7`) |

   Прежняя база (P01.87, P01.106, P02.37, P02.41) — как в P02.26. Сводка — `FILTER-REVIEWS.json`, копии отчётов с хешами — `reviews/`.
4. **Разрешение оператору** — `AUTHORIZATION.json`, вместе с ним `SOURCE-CLOSURE-P01-180.json`. Поля те же, что в P02.26; `filter_blob` — блоб собранного фильтра (P02.52). Оператор ограничивает поле `filter_reviewer_provider` 80 знаками, поэтому там стоит ссылка на `FILTER-REVIEWS.json`, а полный список ревью — в самом файле.
5. **Пара** выпущена одним запуском оператора (`RUN.json`, exit 0). Сверка — `verify_pair_p01180.py` (`VERIFY.json`), все проверки верны:
   - J равна Platform C плюс маркер, M — ровно `model_and_judge`;
   - собранный `FILTER-M.json` равен сборке `export_lists` из check_spec;
   - у каждой выгрузки одна ссылка и один коммит без родителей, физические объекты равны достижимым, `fsck --strict` чистый.
6. **M ⊂ J побайтно:** 786 из 786 путей с тем же режимом и blob (`M-SUBSET-J.json`). Один blob M совпадает с blob пути только для судьи — общий манифест `testsub`, как в P01.121 и P02.26; ADR-0133 доп. (4) п. 6 это допускает.
7. **Паспорт M** выпущен `m_passport.py` на M.git пары. Контроли `check_m_passport.py` (`passport/controls.sh`, вывод `passport/controls.out`, коды выхода настоящие):
   - M как есть — OK, exit 0;
   - J — exit 1, 2772 файла «not in the M passport»;
   - подмена байтов, пропажа файла и ссылка — exit 1;
   - лишний `Platform/01-store/forms/extra.scenarios.tsv` из J — exit 1;
   - чужая M (`bf846208`, пара попытки 6) — exit 1.
8. **J-вход** собран `judge_input_export.py` с `--filter-blob 9450e7cc`: записи собранного фильтра равны сборке `export_lists` (judge) из check_spec, блоб считает `ji_filter_blob.py`. Сверка — `verify_ji_p01180.py`, разбор отметок — `verify_ji_p01180_classify.py`, итог `VERIFY-JI.json` OK:
   - прежние правила P01.121 отмечают те же пять файлов, что в P02.26: четыре `.js`-фикстуры `testsub2` и `acceptance/1/verdicts.tsv`. Их пропускают правки оператора, принятые в P02.45;
   - реестры `forms/targets.tsv` и `forms/targets.routing.tsv` уроков 01, 02, 03 в J-входе есть; `forms/export.json` уроков, корпуса `spec_verdicts` и мутантов нет;
   - из каталогов целей вне J-входа остались 158 файлов, все исключены фильтром: 140 — корпус вердиктов, 17 — схемы check_spec (8 OBSH.39 и 9 P01.228), 1 — `export.json` урока;
   - физические объекты равны достижимым (2207), `fsck --strict` чистый, ссылка одна.
9. **Тесты операторов:** 51 из 51 OK (`OPERATOR-TESTS.out`).

## Сценарии в этом каталоге

`scripts/` — копии сценариев проверки, отличных от образца P02.26:
- `verify_pair_p01180.py` — сверка идёт по собранному `FILTER-M.json`, а не по общему файлу, и этот файл сравнивается со сборкой `export_lists`;
- `verify_ji_p01180.py`, `verify_ji_p01180_classify.py` — фильтр берётся из собранного `FILTER-JI.json`, маршруты — из общего `targets.routing.tsv` и таблиц уроков; добавлены проверки реестров уроков и того, что `export.json` в J-вход не попал;
- `ji_filter_blob.py`, `filter_delta.py`, `passport/controls.sh`;
- `delivery/setup.sh` и `delivery/verify.py` — доставка для root.

## Хеши доказательств (sha256, первые 16 знаков, каталог `/home/pilot/run-p01180-pair-20261112`)

| файл | sha256 |
|---|---|
| `CHECK-SPEC-C.out` | `3a17c6b1f14e65f2` |
| `PREFLIGHT.json` | `a83405b1d562305e` |
| `FILTER-DELTA.json` | `ef26b470edf00b54` |
| `FILTER-REVIEWS.json` | `48edb5bad75898f5` |
| `SOURCE-CLOSURE-P01-180.json` | `745c2489182893d1` |
| `AUTHORIZATION.json` | `237711bed12a5b69` |
| `RUN.json` | `10aa1223c3dc62ff` |
| `VERIFY.json` | `024b0db48c2b9201` |
| `M-SUBSET-J.json` | `d87fbc54c693cd89` |
| `passport/controls.out` | `573d99bac8c05c6c` |
| `VERIFY-JI.json` | `05e72d8e9ddb0c11` |
| `OPERATOR-TESTS.out` | `009112814148278e` |
| `pair-41a9493fb08c/PASSPORT-TRUSTED-ONLY.json` | `1583010a666a54e1` |
| `pair-41a9493fb08c/FILTER-M.json` | `d05469d9f129ac57` |
| `ji-41a9493fb0/FILTER-JI.json` | `83700d4a98030c10` |
| `delivery/setup.sh` | `076ea4fc29658d8b` |
| `delivery/verify.py` | `13f9b6b767642907` |
| `HASHES.txt` (78 файлов доказательств) | `00d9942b23b68a1a` |

## Пределы

- **Доставки на стенд и канарейки нет** — их делает представитель от root (цель задачи). Сценарий `delivery/setup.sh` раскладывает M с `PASSPORT-M.json` в `/srv/b11-isolation/model-specs/be48405e…/`, а J-вход — в `/srv/b11-isolation/judge-input/9daca227…/`. Права — как в P01.121.1 и P02.26. Сценарий сверяет паспорта, каждый файл и описи соседних каталогов до и после. Окно его не запускало. Строк `trial-views` и канарейки линий продукта и судьи нет.
- 9 записей схем P01.228 не ревьюил другой поставщик; они закрыты и для модели, и для J-входа.
- Поставщик приёмщика P01.176 в его отчёте не назван.
- Проверки пары и J-входа написала та же сессия, что их выпустила. Независимы ревью фильтров и операторов (таблица выше) и будущий приём.
- Тесты операторов оставляют фикстуры в `operator/operator-fixtures` каталога доказательств; в `HASHES.txt` они не входят.

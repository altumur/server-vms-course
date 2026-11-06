# З-10: пределы reader P/06.8 по нынешнему writer

Основание — ADR-0129 доп. (12), exact base `3dd73fe5d7693acfc08943511e9cd88f37af8b90`; задание `decisions/inbox/2026-11-06-З10-перепроверка-P01-P02-без-совместимости.md`. Отдельная ветка `spec103/p06-reader-limits-z10`, без переноса авторского P02 `9ee5dc72982e8f6aa46913c52620a68815129813` в эту базу. Пределы чтения=записи — новое принятое слово, не вывод прежней арифметики.

Происхождение: более широкий reader был в9ee и в3dd до этой поставки. В частности, исходный `06-rights-8034` явно ожидал ok от списка9 при writer-пределе8. Это прежняя преднамеренная совместимость, снятая З-10, а не дефект, наведённый данной правкой. Расчёты e45f0187 и52a7e53a и их полная опись источников сохранены внешними неизменными артефактами доЗ-10; они не переписаны под новое решение.

## Источник

- `Platform/06-console/data/folders.schema.json` и `memberof.schema.json`: root `allOf` с единственной ссылкой `#/$defs/writer`. Числовые узлы `/$defs/writer/properties/members/maxItems=1000` и `/$defs/writer/properties/folders/maxItems=8`, остальные `$defs`, их байты и значения runtime-constants сохранены. Новых типов, x-полей, кодеков, listener или native command нет. Читатель теперь действительно проверяет эти пределы обычной схемой; проверка не зависит от особого reader-флага в коде.
- `spec/06.8-console.norms.md` и RU: единая полная проверка строки до R013/R014/R016/R018. Папка/memberof сверх предела — целая строка unreadable, существующий исход семьи. В edit не допускается использовать префикс или разность до проверки; в folder/unit deletion действует прежнее удаление unreadable memberof с cas, без построения folder writes из его содержимого; reaper использует прежние unreadable-ветви и полную реконструкцию с прежней проверкой писателя. Исключение для старого состояния, усечение и новый отказ/переход не вводятся. Все прежние fenced-блоки процедур, req anchors и N4 побайтно сохранены; уточняющие абзацы и reader-binding согласованы EN/RU.
- Область профиля — состояния нынешних писателей, как прямо решено З-10. Это не доказательство достаточности B, полного descriptor roster или исполнения восстановления.
- Числовой источник FOLDER_ROW_MAX, существующая отдельная проверка веса подготовленной строки, B/V, API, формы отказов/этапов, outcomes/layers и HTTP acceptance остаются прежними.

## Явно разрешённая поправка положительного ожидания

До изменения объявлены точный файл/ячейки; coord103 разрешила их по новому слову. `Platform/common/vectors/family-read/06.tsv`, physical1127, case `06-rights-8034`:

| Колонка | До | После |
|---|---|---|
| `verdict` (8) | `ok` | `refused` |
| `paths` (9) | `[]` | `["/folders"]` |
| `outcome` (10) | `{"console": [], "domainagent": []}` | `{"console": [""], "domainagent": [""]}` |
| `note` (11) | over the writer's limit | общий предел reader/writer по З-10 |

Input/case/все первые7полей этой строки точны. `06-rights-8033` целиком прежний. В остальных family-read таблицах других положительных случаев этих двух семей сверх1000/8 не найдено. Никакой другой прежний outcome таблицы не изменён. Полная точная before/after-строка — `8034-before-after.json`.

В конец той же таблицы добавлены6случаев: folder1000 writer/reader accepted; folder1001 writer/reader refused `/members`; memberof8 writer/reader accepted. Вместе с8033/8034 они дают обе стороны границ1000/1001 и8/9. Все остальные старые строки — побайтно прежние; провода/who/consumer roster не меняются. EN/RU README приёмки связывают векторы с нормой, не называют их исполнением HTTP. Прежние12 сценариев/189шагов HTTP сохранены побайтно, без нового @crash/CALL/порта.

## Авторские проверки и предел доказательства

Источник/эталон, не реализация: JSON Schema2020-12 meta check обеих схем; восемь фактически вызванных проверок существующим `v7.stack.Family` и действующими outcome-таблицами; две пары en_mirror без ошибок; `git diff --check`; Cyrillic `--shrink` с собственной копией реестра — PASS, копия реестра и исходный реестр побайтно прежние. Защищённые outcomes/layers/runtime-constants/stages/API/wire/consumers и HTTP-сценарии проверены побайтно. Точные SHA/пойнтеры — `source-map.json`, `reader-bindings.json`, `author-check.json`.

Полный авторский `check_spec --strict-coverage` выполнен на source9изменениях и дал **ровно1ERROR**: `Platform/06-console/ru/spec/06.8-console.norms.md`, generated families header line17. Старый `section.py` печатает «Только у писателя», источник уже называет общую область reader/writer. Это известная заранее согласованная отдельная правка renderer у review103 на frozen SHA; автор tools/skills не правил, ошибку не пропускал и не объявляет PASS. Counts этого прогона: verdicts947, canonical_vectors220, numeric_loader_cases9, family_read_rows10720, finite_profile_cases13, finite_profile_skeletons8, p06_folder_equalities2, p08_schema_equalities141; это факты источника, не новый полный совместный GATE. Log `/home/pilot/spec103/p06-reader-limits-z10/check-spec-source.log` сохраняется отдельно.

Независимый мутант1001, положительный контроль1000, обновление заголовка renderer и reader-binding equality — review103 через coord103. Новое ревью P01/P02 review103/Kimi — только после общего согласованного frozen среза; старые отчёты не переоцениваются. Авторское сравнение8/9 не называется независимым судьёй.

Б1 и исполнение восстановления P02 остаются OPEN. Не выбирались B/параметры профиля, не запускались Go, normgen/KIT, модель, раннер, реализация или очередь. P01/P02/прочие уроки/Source/module/VMS/пины не правились. Вливание и общий GATE — coord103. Сдача — frozen SOURCE для согласованной композиции с судьёй, не готовность урока.

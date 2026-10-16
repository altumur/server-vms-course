# Ревью спецификаций М10_Platform — прогон 37 (Gemini)

- **Срез (HEAD):** `47cc741e845eaa83f33f834cfbf05892a9154c58`
- **Дата:** 2026-10-16
- **Ревьювер:** Gemini ревью (независимый третий ревьювер, рабочее дерево `/Users/murat/w2c/wt-review-spec-37-gemini`, ветка `gemini/review-spec-37-gemini`)
- **Охват:** полный, без заморозок — все 11 уроков `М10_Platform` (`01`–`11`: лекции `М10_Platform/NN-*.md`, нормы `М10_Platform/spec/NN-*.norms.md`, HTTP-контракты `М10_Platform/spec/NN-*.api.openapi.yaml`, инструкции `М10_Platform/spec/NN-*.README.md`, приёмка `Source/tests/testdata/acceptance/М10_Platform/01..11/*`), `М10_Platform/module-design.md`, `GLOSSARY.md`, межурочные зависимости, общие данные `Source/vms/*.subsystem.yaml` и `Source/tests/testdata/platform_lists.tsv` / `testsub*.subsystem.yaml`, а также весь навык `.claude/skills/lesson-spec/` (`SKILL.md`, `references/*`, `assets/*`, `scripts/check_spec.py`, `scripts/test_check_spec.py`).

---

## Находки

### G37-01 — Урок 2: расхождение счётчиков вердиктов (`164 = 23 + 141` вместо `212 = 32 + 180`) и диапазона чеклиста (`М10/2-01…16` вместо `М10/2-01…21`) между Н5 норм, инструкцией `.README.md` и фактической приёмкой

- **Урок / норма / `файл:строка`:**
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:309` (раздел `## Н5 Приёмка`),
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:365-385` (раздел `## Чеклист готовности`, пункты `М10/2-01`…`М10/2-21`),
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md:9` (раздел `## Задача`),
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md:106,110` (раздел `## Готово, когда`),
  - `Source/tests/testdata/acceptance/М10_Platform/02/README.md:55` и `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv:1-213`.
- **Наблюдаемое противоречие:**
  1. В `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:309` записано: `` `verdicts.tsv` — 212 файлов `cases/<case>.subsystem.yaml`, каждый загружается один, ответ `ok` (23) или `refused` (141) ``. Сумма в скобках равна `23 + 141 = 164 ≠ 212`. Фактически `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv` (и описание в `Source/tests/testdata/acceptance/М10_Platform/02/README.md:55`) содержит 212 случаев: **32 `ok` и 180 `refused`** (164 прежних случая `23 ok + 141 refused` и 48 добавленных в прогоне 36 случаев `profile_*` с распределением `9 ok + 39 refused`).
  2. В `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md:9` задача урока ограничена формулировкой «закрыть чеклист `М10/2-01…16`», в строке 106 критерий «Готово, когда» требует: «Все 164 файла дают вердикт из таблицы: 23 `ok`, 141 `refused`; множества файлов и случаев совпадают», а в строке 110 — «Все 16 пунктов `М10/2-01…16` закрыты указанными в них проверками». Это прямо противоречит как фактическому набору `verdicts.tsv` (212 файлов: 32 `ok`, 180 `refused`), так и чеклисту норм `02-the-spec-and-the-strict-loader.norms.md:365-385`, который содержит 21 пункт (`М10/2-01…21`, включая добавленные `М10/2-17`…`М10/2-21`).
- **Конкретный воспроизводимый контрпример на допустимом входе:**
  Запуск приёмки урока 2 на каноническом наборе `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv` (включающем допустимые входы `cases/profile_blob_unit_ok.subsystem.yaml` → `ok` и `cases/profile_blob_table.subsystem.yaml` → `refused value tables.shelves.fields.mask`) обрабатывает 212 файлов и при полном совпадении с таблицей `verdicts.tsv` получает 32 вердикта `ok` и 180 вердиктов `refused`. Такой прогон одновременно нарушает булево условие готовности `02-the-spec-and-the-strict-loader.README.md:106` («Все 164 файла дают вердикт из таблицы: 23 `ok`, 141 `refused`») и числовую норму `02-the-spec-and-the-strict-loader.norms.md:309` (`ok (23) или refused (141)`).
- **Первичное правило / ADR:**
  `decisions/0080-лекции-как-спецификации.md` (разделы «Чеклист готовности в нормах» и «Инструкция к заданию (`spec/NN-<slug>.README.md`)»); `.claude/skills/lesson-spec/SKILL.md:121-133`; `.claude/skills/lesson-spec/references/review-checklist.md:156-185` («Инструкция не расходится с нормами по числу сценариев, формам, кодам и артефактам»; «Готово, когда проверяемо да/нет и ссылается на чеклист норм»).
- **Серьёзность:** `существенная`
- **Происхождение:** `наведена правкой 1a4fc4b9` (прогон 36, закрытие `K36-2-01`: в `verdicts.tsv` добавлены 48 случаев `profile_*`, в чеклист норм добавлены `М10/2-17…21`, в `02-the-spec-and-the-strict-loader.norms.md:309` число `164` заменено на `212`, но счётчики `(23)` / `(141)` в той же строке и все числа в `02-the-spec-and-the-strict-loader.README.md:9,106,110` остались от прежнего среза).
- **Рекомендация:** В `02-the-spec-and-the-strict-loader.norms.md:309` заменить `ok (23) или refused (141)` на `ok (32) или refused (180)`, а в `02-the-spec-and-the-strict-loader.README.md:9,106,110` обновить числа до 212 файлов (`32 ok, 180 refused`) и 21 пункта чеклиста `М10/2-01…21`.

---

### G37-02 — Урок 9: `HEAD /{sub}/` и `HEAD /{sub}/index.html` в OpenAPI объявляют невозможный ответ `200`, описания `405` в `HEAD` остались «Метод не GET.», а `Н1.2` и `Н2` противоречат друг другу по монтированию `/servers`

- **Урок / норма / `файл:строка`:**
  - `М10_Platform/spec/09-the-console.api.openapi.yaml:1935,1971-1978` (`paths./{sub}/.head`),
  - `М10_Platform/spec/09-the-console.api.openapi.yaml:2024,2060-2067` (`paths./{sub}/index.html.head`),
  - `М10_Platform/spec/09-the-console.api.openapi.yaml:69,162,1474,1559,1659,1783,1866,1949,2038` (`head.responses['405'].description`),
  - `М10_Platform/spec/09-the-console.norms.md:51-53` (`Н1.2 Двери с одним окном`) и `М10_Platform/spec/09-the-console.norms.md:108-110` (`Н1.4 Что зовёт модуль`) против `М10_Platform/spec/09-the-console.norms.md:167` (`Н2 Двери`) и `М10_Platform/spec/09-the-console.api.openapi.yaml:1421` (`paths./{sub}/servers`).
- **Наблюдаемое противоречие:**
  1. По `М10_Platform/spec/09-the-console.norms.md:53` (`Н1.2`) страницы смонтированной подсистемы `/<sub>/` и `/<sub>/index.html` отсутствуют и всегда отвечают `404 {detail: "no page at /<sub>/: this subsystem is mounted inside the console at /", error: "is mounted"}` (либо `404 NoRoute` для неизвестного `sub`), а по `09-the-console.norms.md:159` (`Н2`) `HEAD повторяет код и заголовки GET, но не тело`. В `09-the-console.api.openapi.yaml` у `GET /{sub}/` (строки 1897–1933) и `GET /{sub}/index.html` (строки 1986–2022) код `200` не объявлен, однако у `HEAD /{sub}/` (строки 1935, 1971–1978) и `HEAD /{sub}/index.html` (строки 2024, 2060–2067) оставлены `summary: 'HEAD: Страница root'` и невозможный ответ `'200'` (`description: Полный документ UTF-8; HEAD не содержит тела` с обязательным заголовком `Content-Security-Policy`). Попутно в `head.responses['405'].description` девяти маршрутов (`09-the-console.api.openapi.yaml:69,162,1474,1559,1659,1783,1866,1949,2038`) сохранена формулировка `Метод не GET.; HEAD не содержит тела`, хотя маршрут допускает и `GET`, и `HEAD`, а в остальных маршрутах того же файла она была заменена на `Метод не из объявленных для этой двери.; HEAD не содержит тела`.
  2. В `М10_Platform/spec/09-the-console.norms.md:51` (`Н1.2`) маршрут `/servers` отнесён к закрытому перечню `общие двери (/servers, /drain, /schema, /events, /marks, /session, /mounts, /healthz) без префикса` (и в `Н1.4` строке 109 указан только `/servers` без `/<sub>/servers`), тогда как `09-the-console.norms.md:167` (`Н2`) и `09-the-console.api.openapi.yaml:1421` одновременно объявляют смонтированный маршрут `/{sub}/servers` с префиксом `/<sub>`.
- **Конкретный воспроизводимый контрпример на допустимом входе:**
  На стенде приёмки урока 9 (`Source/tests/testdata/acceptance/М10_Platform/09/scenarios.tsv:16`, где `testsub2` смонтирована под `/testsub2` и `GET /testsub2/` возвращает `404` с `"error": "is mounted"`) запрос `HEAD /testsub2/` или `HEAD /testsub2/index.html` с допустимой личностью по `09-the-console.norms.md:53,159` обязан вернуть `404` (повторяя код `GET` без тела), тогда как `09-the-console.api.openapi.yaml:1971-1978,2060-2067` объявляет для него успешный ответ `200` с заголовком `Content-Security-Policy`. Для запроса `GET /testsub2/servers` норма `Н1.2` (`09-the-console.norms.md:51`) требует отсутствия префикса `/<sub>` у общей двери `/servers` (то есть `404 NoRoute` под `/testsub2/servers`), тогда как `Н2` (`09-the-console.norms.md:167`) и `09-the-console.api.openapi.yaml:1421` требуют вернуть `200` со схемой `Servers`.
- **Первичное правило / ADR:**
  `М10_Platform/spec/09-the-console.norms.md:50-54` (`Н1.2`), `М10_Platform/spec/09-the-console.norms.md:159-167` (`Н2`); `.claude/skills/lesson-spec/references/review-checklist.md:130-133` («Невозможный по Н1–Н3 успех не объявлен в 2xx (например маршрут, который по норме всегда 404)»; «Все пути, методы, query/path/header параметры и коды из Н2/Н4 присутствуют в OpenAPI и наоборот»).
- **Серьёзность:** `существенная`
- **Происхождение:** `наведена правкой 1a4fc4b9` (прогон 36, закрытие `K36-9-04` и `K36-9-09`: при добавлении семи префиксных путей в `09-the-console.api.openapi.yaml` ответ `200` был убран только из `get` у `/{sub}/` и `/{sub}/index.html`, но оставлен в `head`; в `head` новых путей и корня сохранился текст `Метод не GET.`; маршрут `/{sub}/servers` был добавлен в `Н2` и OpenAPI без согласования со списком общих беспрефиксных дверей в `Н1.2`).
- **Рекомендация:** В `09-the-console.api.openapi.yaml` удалить ответ `'200'` из `head` у `/{sub}/` и `/{sub}/index.html` (исправив `summary` и описания `405` в `head`), а в `09-the-console.norms.md` согласовать между `Н1.2` (строки 51–52), `Н1.4` (строка 109) и `Н2` (строка 167), является ли `/servers` только общей беспрефиксной дверью или также дверью под `/<sub>/servers`.

---

### G37-03 — Уроки 3, 4, 8, 9, 10: делегированные смонтированные маршруты `/<sub>/…` (в М10/3, М10/4, М10/10) и корневые маршруты `/requests`, `/asked/{sha16}` (в М10/8) не выражены в `paths` своих OpenAPI-контрактов

- **Урок / норма / `файл:строка`:**
  - `М10_Platform/spec/09-the-console.norms.md:52,84-85,108-113,167` (`Н1.2`, `Н1.3`, `Н1.4`, `Н2`),
  - `М10_Platform/spec/03-units-slots-epochs-lease.api.openapi.yaml:11-135` (`paths` содержит только `/{rows}` и `/{rows}/{id}`),
  - `М10_Platform/spec/04-the-controller-and-placement.api.openapi.yaml:8-440` (`paths` содержит только `/policy`, `/drain`, `/servers/{server}/labels`, `/servers/{server}/decommission`, `/unplaceable`, `/where/{id}`),
  - `М10_Platform/spec/08-events-resource-requests.norms.md:276-277` и `М10_Platform/spec/08-events-resource-requests.api.openapi.yaml:639-818` (`paths` содержит только `/{sub}/requests` и `/{sub}/asked/{sha16}`, без корневых `/requests` и `/asked/{sha16}`),
  - `М10_Platform/spec/10-schema-drain-snapshot-limits.api.openapi.yaml:8-195,1405` (`paths` содержит только `/drain`, `/schema`, `/{rows}/{id}/{blob_field}`, `/{table}`, `/{table}/{name}`, `/v1/objects/{sub}/blobs/{digest}` и поле `x-mounting` на строке 1405),
  - против `Source/tests/testdata/acceptance/М10_Platform/09/scenarios.tsv:12-13`, `Source/tests/testdata/acceptance/М10_Platform/10/README.md:3`, `Source/tests/testdata/acceptance/М10_Platform/10/scenarios.tsv:18-38`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:107` и `М10_Platform/spec/10-schema-drain-snapshot-limits.norms.md:129`.
- **Наблюдаемое противоречие:**
  Норма `09-the-console.norms.md:52` (`Н1.2`) устанавливает, что все двери конкретной подсистемы (`/<rows>`, `/<table>`, `/spec`, `/unplaceable`, `/where/…`, `/policy`, `/requests`, `/asked/…`, `/metrics`) доступны **как под `/<sub>/…`, так и без префикса для `root`**. Норма `09-the-console.norms.md:167` (`Н2`) прямо указывает: «Двери единиц, размещения, событий, таблиц и схемы принадлежат М10/3, 4, 8, 10... Собственные маршруты этого урока `/spec`, `/servers`, `/unplaceable`, обе формы `/where` и `/metrics` также явно объявлены с префиксом `/<sub>`; **префиксы делегированных дверей — у их владельцев**». Чеклист ревью `.claude/skills/lesson-spec/references/review-checklist.md:133` закрепляет: «Все обещанные смонтированные маршруты явно выражены в контракте своего владельца; metadata о prefix не заменяет paths». Однако в контрактах уроков-владельцев эти пути отсутствуют:
  1. **М10/10 (`10-schema-drain-snapshot-limits.api.openapi.yaml:8-195,1405`):** в `paths` объявлены только беспрефиксные маршруты консоли `/{rows}/{id}/{blob_field}`, `/{table}` и `/{table}/{name}`, а наличие префикса `/<sub>` вынесено в `x-mounting: 'Консоль: /schema и /drain общие, пути единиц и таблиц — root либо /<sub>...'` на строке 1405. Смонтированные пути `/{sub}/{rows}/{id}/{blob_field}`, `/{sub}/{table}` и `/{sub}/{table}/{name}` в `paths` отсутствуют.
  2. **М10/3 (`03-units-slots-epochs-lease.api.openapi.yaml:11-135`):** в `paths` объявлены только `/{rows}` и `/{rows}/{id}`; смонтированные `/{sub}/{rows}` и `/{sub}/{rows}/{id}` отсутствуют (а описание параметра `id` на строке 85 гласит: «Путь длиннее одного id — 404»).
  3. **М10/4 (`04-the-controller-and-placement.api.openapi.yaml:8-440`):** в `paths` объявлены только беспрефиксные `/policy`, `/unplaceable` и `/where/{id}`; смонтированные `/{sub}/policy`, `/{sub}/unplaceable` и `/{sub}/where/{id}` отсутствуют (причём для `/{sub}/policy` контракт М10/4 является единственным владельцем в курсе).
  4. **М10/8 (`08-events-resource-requests.norms.md:276-277`, `08-events-resource-requests.api.openapi.yaml:639-818`):** ситуация зеркальна — в `paths` объявлены только префиксные `/{sub}/requests` и `/{sub}/asked/{sha16}`, но отсутствуют беспрефиксные корневые маршруты `/requests` и `/asked/{sha16}` для `root`-подсистемы, хотя `09-the-console.norms.md:52,84-85,113` («`двери конкретной подсистемы (… /requests, /asked/…) под /<sub>/… (и без префикса для root)`», «`POST /requests → edit на единицу тела`», «`DELETE /asked/* → admin на *`») и `10-schema-drain-snapshot-limits.norms.md:129` (резервирующий `requests` и `asked` среди 19 первых сегментов корневых дверей консоли) требуют их наличия без префикса.
- **Конкретный воспроизводимый контрпример на допустимом входе:**
  - В приёмке урока 10 (`Source/tests/testdata/acceptance/М10_Platform/10/scenarios.tsv:19,29-38`, сценарии `04-blob` и `06-tables` против `console2`, где `testsub2` смонтирована под `/testsub2` согласно `acceptance/10/README.md:3`) выполняются допустимые запросы:
    - `PUT /testsub2/tallies/t1/mask` (ожидается `200`) — 4 сегмента пути не подходят ни под один шаблон `paths` в `10-schema-drain-snapshot-limits.api.openapi.yaml`;
    - `POST /testsub2/shelves` (ожидается `201`) и `GET /testsub2/shelves` (ожидается `200` со списком `{shelves: [...]}`) — 2 сегмента пути в `10-schema-drain-snapshot-limits.api.openapi.yaml` совпадают только с шаблоном одной строки `/{table}/{name}`, где метод `POST` отсутствует (`405`), а `GET` описывает одну строку `TableRow`, а не объект-список `TableList`;
    - `GET /testsub2/shelves/sh1` и `DELETE /testsub2/shelves/sh1` (ожидается `200`) — 3 сегмента пути в `10-schema-drain-snapshot-limits.api.openapi.yaml` совпадают только с `/{rows}/{id}/{blob_field}`, где объявлен только `PUT` (`405`).
  - В приёмке урока 9 (`Source/tests/testdata/acceptance/М10_Platform/09/scenarios.tsv:12-13`, сценарий `02-mounts`) запросы `GET /testsub2/counters` (`200`) и `POST /testsub2/counters` (`201`) имеют 2 сегмента и в `03-units-slots-epochs-lease.api.openapi.yaml` попадают только в `/{rows}/{id}`, где объявлены лишь `PUT` и `DELETE`, а `PUT /testsub2/tallies/t1` из `acceptance/10/scenarios.tsv:21` имеет 3 сегмента и по строке 85 `03-units-slots-epochs-lease.api.openapi.yaml` классифицируется как `404`.
- **Первичное правило / ADR:**
  `М10_Platform/spec/09-the-console.norms.md:52` (`Н1.2`), `М10_Platform/spec/09-the-console.norms.md:167` (`Н2`); `.claude/skills/lesson-spec/references/review-checklist.md:132-133` («Все обещанные смонтированные маршруты явно выражены в контракте своего владельца; metadata о prefix не заменяет paths»).
- **Серьёзность:** `существенная`
- **Происхождение:** `была раньше на ad149b1f` (частично затронута правкой `1a4fc4b9` прогона 36 при закрытии `K36-9-04`: в `09-the-console.norms.md:167` было добавлено утверждение «префиксы делегированных дверей — у их владельцев», однако сами контракты владельцев М10/3, М10/4, М10/8, М10/10 не были приведены в соответствие с этим правилом).
- **Рекомендация:** Явно объявить смонтированные маршруты `/{sub}/…` в `paths` контрактов-владельцев `03-units-slots-epochs-lease.api.openapi.yaml`, `04-the-controller-and-placement.api.openapi.yaml` и `10-schema-drain-snapshot-limits.api.openapi.yaml` (убрав подмену путей расширением `x-mounting`), а в `08-events-resource-requests.norms.md` и `08-events-resource-requests.api.openapi.yaml` добавить корневые `/requests` и `/asked/{sha16}` (либо явно исключить их из беспрефиксных маршрутов в `09-the-console.norms.md:52,84-85` и списка первых сегментов в М10/2 и М10/10).

---

## Итоги по урокам и артефактам

- **М10/1 (`01-storage`):** замечаний нет. Лекция, нормы `01-storage.norms.md`, контракт `01-storage.api.openapi.yaml`, инструкция `01-storage.README.md` и приёмка `acceptance/М10_Platform/01/` (22 сценария, 99 шагов) согласованы; структурная проверка `check_spec.py --lesson 01 --acceptance` проходит без ошибок.
- **М10/2 (`02-the-spec-and-the-strict-loader`):** 1 существенная находка (`G37-01` — несогласованные числа `ok (23)` / `refused (141)` в `02-the-spec-and-the-strict-loader.norms.md:309` и устаревшие объёмы `164 файла: 23 ok, 141 refused` и `М10/2-01…16` в `02-the-spec-and-the-strict-loader.README.md:9,106,110` после расширения `verdicts.tsv` до 212 случаев и чеклиста до `М10/2-01…21`). Сами 212 файлов `cases/*.subsystem.yaml` и `verdicts.tsv` (32 `ok`, 180 `refused`, 13 диагностических префиксов) непротиворечивы и проходят `check_spec.py --lesson 02 --acceptance`.
- **М10/3 (`03-units-slots-epochs-lease`):** затронут межурочной существенной находкой `G37-03` (в `03-units-slots-epochs-lease.api.openapi.yaml` отсутствуют смонтированные пути `/{sub}/{rows}` и `/{sub}/{rows}/{id}`, делегированные владельцу нормой `09-the-console.norms.md:167` и вызываемые в приёмке М10/9 и М10/10). Внутренние нормы Н1–Н5, проходы создания/правки/удаления, слоты, эпохи и аренда согласованы.
- **М10/4 (`04-the-controller-and-placement`):** затронут межурочной существенной находкой `G37-03` (в `04-the-controller-and-placement.api.openapi.yaml` отсутствуют смонтированные пути `/{sub}/policy`, `/{sub}/unplaceable` и `/{sub}/where/{id}`). Внутренние нормы двухшагового допуска `placement_turn`/`placement_intent`, пробы меток, вывода сервера и приёмка `acceptance/М10_Platform/04/` согласованы.
- **М10/5 (`05-the-worker-under-its-slot`):** замечаний нет. Лекция, нормы `05-the-worker-under-its-slot.norms.md` (включая отсечение воркера при схеме хранилища выше сборки и правило `contenders`), инструкция и приёмка `acceptance/М10_Platform/05/` согласованы.
- **М10/6 (`06-rights`):** замечаний нет. Лекция, нормы `06-rights.norms.md`, контракт `06-rights.api.openapi.yaml`, инструкция, приёмка `acceptance/М10_Platform/06/` и канонический `Source/tests/testdata/platform_lists.tsv` согласованы (известные долги внедрения и копии `platform_lists.tsv` в продукте зафиксированы в `ПАРИТЕТ-КУРС-ПРОДУКТ.md`).
- **М10/7 (`07-secrets-and-sealing`):** замечаний нет. Лекция, нормы `07-secrets-and-sealing.norms.md` (включая AAD `enc:v2` и маскирование секретов/URL), инструкция и приёмка `acceptance/М10_Platform/07/` согласованы.
- **М10/8 (`08-events-resource-requests`):** затронут межурочной существенной находкой `G37-03` (в `08-events-resource-requests.norms.md` и `08-events-resource-requests.api.openapi.yaml` объявлены только `/{sub}/requests` и `/{sub}/asked/{sha16}` без корневых `/requests` и `/asked/{sha16}`, обещанных для `root`-подсистемы в `09-the-console.norms.md:52,84-85` и зарезервированных в списке 19 первых сегментов дверей консоли в М10/2 и М10/10). Остальные нормы событий, `suppress`, объектов, зеркалирования и просьб согласованы.
- **М10/9 (`09-the-console`):** 2 существенные находки (`G37-02` — невозможный ответ `200` в `HEAD /{sub}/` и `HEAD /{sub}/index.html`, оставшиеся описания `405` «Метод не GET.» в `HEAD` и противоречие между `Н1.2` и `Н2` по монтированию `/servers`; `G37-03` — расхождение между обещанием `09-the-console.norms.md:52,167` о префиксах делегированных дверей у их владельцев и фактическими `paths` в контрактах М10/3, М10/4, М10/8, М10/10).
- **М10/10 (`10-schema-drain-snapshot-limits`):** затронут межурочной существенной находкой `G37-03` (в `10-schema-drain-snapshot-limits.api.openapi.yaml` смонтированные пути `/{sub}/{rows}/{id}/{blob_field}`, `/{sub}/{table}` и `/{sub}/{table}/{name}` подменены полем `x-mounting` на строке 1405 вместо `paths`, хотя сценарии `04-blob`, `05-ceilings`, `06-tables` в `acceptance/М10_Platform/10/scenarios.tsv` обращаются к смонтированной `testsub2` по путям `/testsub2/...`). Нормы подъёма схемы, дренажа, снимка, `sweep` блобов и таблиц внутри `.norms.md` согласованы.
- **М10/11 (`11-the-platform-on-a-box-and-a-cluster`):** замечаний нет. Лекция, нормы `11-the-platform-on-a-box-and-a-cluster.norms.md`, контракт `11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml`, инструкция и приёмка `acceptance/М10_Platform/11/` согласованы.
- **`М10_Platform/module-design.md` и `GLOSSARY.md`:** замечаний нет. Карта модуля, распределение 178 пунктов чеклиста (`М10/1`–`М10/11`) и словарь терминов согласованы с нормами уроков.
- **`.claude/skills/lesson-spec/` (`SKILL.md`, `references/*`, `assets/*`, `scripts/check_spec.py`, `scripts/test_check_spec.py`):** замечаний нет. Все 44 модульных теста `test_check_spec.py` и все проверки `check_spec.py` по урокам `01`–`11` проходят; границы автоматической проверки честно задокументированы в `SKILL.md` и `references/validation.md`.

---

## Общие причины

1. **Неполное распространение правок прогона 36 по связанным местам одного урока (`G37-01`, `G37-02`):**
   - При расширении `verdicts.tsv` урока 2 со 164 до 212 случаев и чеклиста с 16 до 21 пункта (`K36-2-01`) было обновлено общее число `212` в `02-the-spec-and-the-strict-loader.norms.md:309` и `acceptance/02/README.md:55`, но пропущены слагаемые `(23)` / `(141)` в той же строке 309 и числа `164`, `23 ok, 141 refused`, `М10/2-01…16` в `02-the-spec-and-the-strict-loader.README.md:9,106,110`.
   - При добавлении семи префиксных путей `/{sub}/...` в `09-the-console.api.openapi.yaml` (`K36-9-04`) и правке описания `405` (`K36-9-09`) ответ `200` был удалён только из `get` у `/{sub}/` и `/{sub}/index.html`, но оставлен в `head`, а `/{sub}/servers` добавлен в `Н2` и OpenAPI без сверки со списком беспрефиксных общих дверей в `Н1.2`.
2. **Незавершённое выравнивание смонтированных и корневых путей между М10/9 и контрактами уроков-владельцев М10/3, М10/4, М10/8, М10/10 (`G37-03`):**
   - В `09-the-console.norms.md:167` было явно записано правило «префиксы делегированных дверей — у их владельцев» (а в `review-checklist.md:133` — «metadata о prefix не заменяет paths»), но сами OpenAPI-файлы уроков-владельцев `03`, `04`, `08`, `10` не были проверены на наличие обоих вариантов (`/...` для `root` и `/{sub}/...` для смонтированной подсистемы).

---

## Сводный счёт по серьёзности

| Серьёзность | Количество | Идентификаторы |
|---|---:|---|
| `блокер` | 0 | — |
| `существенная` | 3 | `G37-01`, `G37-02`, `G37-03` |
| `мелкая` | 0 | — |
| **Всего** | **3** | `G37-01`…`G37-03` |

---

## Границы верификации

- Код реализаций продукта на Python (`Source/`) и Go (`vmssubsystem`) не читался и не запускался в соответствии с правилами ревью; общие YAML (`Source/vms/*.subsystem.yaml`, `Source/tests/testdata/testsub*.subsystem.yaml`) и закрытые TSV-списки (`Source/tests/testdata/platform_lists.tsv`, приёмочные `scenarios.tsv` и `verdicts.tsv`) анализировались исключительно как данные канона.
- Выполнены автоматические проверки навыка `.claude/skills/lesson-spec/`: `unittest` по `test_check_spec.py` (44 теста — `OK`), `check_spec.py` по всем 11 урокам `01`–`11` и `--acceptance` для уроков `01` и `02` (`PASS`).
- Смысловая согласованность норм Н0–Н5, OpenAPI 3.1, инструкций `.README.md`, сценариев приёмки `01`–`11`, `module-design.md` и `GLOSSARY.md` проверена чтением и сопоставлением моделей переходов/схем; такое ревью текста и схем не заменяет исполняемого тестирования живых процессов по сети, ФС, таймерам, криптографии и Raft-кворуму.

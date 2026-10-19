# Отчёт ревьювера: стадия B — перенос уроков 1–2 (`Platform/01-store`, `Platform/02-installer`) и правки приёмки по ADR-0080 доп. (17)

- **Срез курса:** `fe9f4cf46` (`= cammeta-specs 5f00a30`)
- **Ветка ревью:** `gemini/review-stage-b-1-2`
- **Охват ревью:**
  - Урок 1 (`Platform/01-store/01-store.md`, `Platform/01-store/spec/01.{1..3}-store.norms.md`, `Platform/01-store/data/*`, `Platform/01-store/acceptance/{1..3}/*`, `Platform/01-store/lifecycle.md`);
  - Урок 2 (`Platform/02-installer/02-installer.md`, `Platform/02-installer/spec/02.{1..5}-installer.norms.md`, `Platform/02-installer/spec/02.1-installer.{form.yaml,references.tsv,scalars.tsv}`, `Platform/02-installer/acceptance/{1,3,4,5}/*`, `Platform/02-installer/lifecycle.md`);
  - Общие контракты и инструменты (`Platform/common/id-map.tsv`, `Platform/common/data/catalog.tsv`, `Platform/common/DIALECT.md`, `Platform/common/manifest-rename.tsv`, `Platform/module-design.md`, `skills/lesson-spec/scripts/form_source/*`, `skills/lesson-spec/scripts/spec_schema/*`, `skills/lesson-spec/scripts/check_spec.py`);
  - Остатки в `М10_Platform/` (`01`, `02`, `03`, `06`, `07`, `11`) и замена `@sleep` на `@until` в приёмке `М10_Platform/05`, `06`, `07`, `08`, `10`, `11` и `М11_Domain/03`, `04`, `05`, `06`, `07`, `08`, `10`, `11`, `12` (`ADR-0080` доп. (17)).
- **Проверенные автоматические проверки:**
  - `check_spec.py` на `Platform/01-store/01-store.md`, `Platform/02-installer/02-installer.md`, `М10_Platform/[0-9]*.md`, `М11_Domain/[0-9]*.md`: `PASS with 51 exceptions` (`catalog_rows=121 count_phrases=281 data_paragraphs=28 diagnostics=52 form_cases=554 form_rows=110 form_rows_held=110 form_specs=9 lessons=23 local_links=812 local_refs=1528 norm_ids=320 openapi=16 scenarios=240 steps=2124 verdicts=554`).
  - `unittest` для `skills/lesson-spec/scripts/test_form_source.py` (5 тестов: `OK`).
- **Общий вывод:** **с правками**
  - Урок 1 (`Platform/01-store`): **с правками** (1 существенная в остатке `М10/11` и `id-map.tsv`, 1 мелкая по ссылкам `lifecycle.md`/`README.md`).
  - Урок 2 (`Platform/02-installer` и источник формы 2.1): **с правками** (1 блокер по схемам семей данных `ADR-0088 п. 8`, 6 существенных по самодостаточности `P/02.4`, расхождениям `DIALECT.md`/`form_source`/`textlayer.py` со сводом журналов, пробелам в `02.1-installer.form.yaml`/`.references.tsv` и выборке `spec put`, 2 мелкие).
  - Приёмка по `ADR-0080` доп. (17) (`@sleep` → `@until`): **с правками** (1 блокер — регрессия гонки в `М11/03` сц. 03 шаг 6; 2 существенные — превращение шагов ожидания в холостые 0 мс запросы и пропущенный `@sleep 12` в `М10/05` сц. 07 шаг 6; 1 мелкая — устаревший счёт шагов в `М10/08`).

---

## 1. Сводная оценка по вопросам ревью

| № | Область проверки | Оценка | Краткий итог |
|---|---|---|---|
| 1 | **Полнота переноса уроков 1–2 по `id-map.tsv`** | **С правками** | Все 23 целевых `P/01.*` и 47 целевых `P/02.*` из `id-map.tsv` присутствуют в чеклистах `01.{1..3}` и `02.{1,3,4,5}`; остатки в `М10/1,2,3,6,7,11` размечены баннерами `> Перенесено в P/...` и удалены из локальных Н6. Однако: (а) пункт `P/01.3-09` (добавленный в `01.3-store.norms.md:304` при делении `М10/6-12` и `М10/11-11`) не имеет строки в колонке `new` таблицы `id-map.tsv`; (б) вопреки шапке `id-map.tsv:5` и `ADR-0083` доп. (5) при переносе уроков 1 и 2 в `id-map.tsv` не добавлены строки сценариев, шагов и векторов (`[B12-4]`); (в) в `М10/11` сценарий `15-service-doors` перенумеровал оставшийся шаг 9 в шаг 1 в `scenarios.tsv`, рассинхронизировавшись с Н5 и `README.md` (`[B12-3]`). |
| 2 | **Ссылки после перенацеливания (`check_spec`)** | **С правками** | `check_spec.py` проходит (`local_links=812`, `local_refs=1528`), но в не проверяемых скриптом `lifecycle.md` и `README.md` приёмки остались ошибки: в `Platform/01-store/lifecycle.md:37,90` и `Platform/08-domain/lifecycle.md:10` подпись поменяли на `[P/01.3 Н1.3]` / `[P/02.4 Н1.1]`, а URL оставили на `М10_Platform/spec/11-...norms.md` (откуда эти разделы удалены); в `Platform/01-store/lifecycle.md:15,16,30,31` ссылки на `Н1.3` (`sockets`, `group.join`, «Флаги демона») ошибочно приписаны `P/02.4` вместо `P/01.3`; в `М11_Domain/01..03/README.md` сбит якорь `#стенд--общий-для-приёмки-м10` (`[B12-13]`). |
| 3 | **Самодостаточность уроков 1–2 (`ADR-0083` доп. (5)) и схемы семей данных (`ADR-0088`)** | **Блокер / С правками** | 1) **Блокер `[B12-1]`:** для урока 1 создан `Platform/01-store/data/` и обновлены строки `catalog.tsv:2-3`, но для урока 2 (`02-installer`) обязанность урока-владельца по `ADR-0088 п. 8` не выполнена — каталог `Platform/02-installer/data/` для семей `platform/spec/<sub>` и `platform/spec/<sub>/rev` (глава 2.3) не создан, в `catalog.tsv:4-5` остались старые пути `row/spec-row.schema.yaml` и `row/spec-rev.schema.yaml`.<br>2) **Существенная `[B12-5]`:** глава `02.4` (`P/02.4-14`, `w2cctl secrets new\|seal\|rotate\|status`) прямо отсылает за алгоритмом обхода `*_secret`, AAD, форматом кольца `platform.key`, конвертом `enc:v2:` и кодами возврата в прозу чужого урока `М10/7 Н1.2`, нарушая критерий чистой комнаты `ADR-0083` доп. (5). |
| 4 | **Слова «манифест» / «спека» (`ADR-0086`) и диалект (`ADR-0087`)** | **Годно (с мелкой оговоркой)** | По `ADR-0086 п. 6` и `Platform/module-design.md:52` переименование имён на проводе и в прозе отложено в единый коммит конца стадии B по `Platform/common/manifest-rename.tsv` (сейчас переименованы только суффиксы файлов `.subsystem.yaml` в корпусе `Platform/02-installer/acceptance/1/cases/`). Мелкая шероховатость: `Platform/common/DIALECT.md` уже называет раздел 2.1 «формой манифеста подсистемы», тогда как в `02.1-installer.norms.md` пока везде «спека» (`[B12-16]`). |
| 5 | **Источник формы 2.1 (`.form.yaml`, `.references.tsv`, `.scalars.tsv`) против прозы Н1.2–Н1.4 и корпуса 554** | **С правками** | Построенный раздел «Форма» (`02.1-installer.norms.md:53-926`) байт-в-байт совпадает с выходом `section.py`, все 110 строк отношений держатся на `ok`-корпусе, все 554 случая корпуса проходят `judge.py`. Однако обнаружены 4 существенных расхождения: (а) `DIALECT.md` § 5 и § 7 и генерируемая `section.py` проза Н1.2 утверждают, что числа вне пределов и пустые значения всегда дают `value`, что противоречит решению Ф1 свода журналов, `judge.py` и случаю корпуса `c9_xclass_number_overflow` (`reference`) (`[B12-6]`); (б) решение Ф18 (`depth` по дереву с умолчаниями) не отражено ни в `DIALECT.md` § 2/§ 6, ни в `judge.py` (`[B12-7]`); (в) `textlayer.py` падает с `refused:text` на одиночном `-` с пробелом в потоковой коллекции (`[ - , a ]`, `{unit: - }`), нарушая норму `word` и решение Т16 (`[B12-8]`); (г) в `.references.tsv` и `.form.yaml` не закрыты два пробела против Н1.3/Н1.4: `display.options` для полей таблиц с `enum` и запрет `schema` при `type != json` (`[B12-9]`). |
| 6 | **Выборка `spec put` (`ADR-0080` доп. (17) п. 2)** | **С правками** | В `Platform/02-installer/acceptance/1/classes.tsv` (149 строк) присутствуют только 4 класса (`text`, `key`, `value`, `reference`) и нет ни одного из 9 случаев класса `name` (`refused:name`, шаг 2 Н3). Поэтому правило «по одному отказу на каждый класс `refused:<класс>` из `classes.tsv`» вообще не проверяет класс `refused:name` через `spec put`. Кроме того, в корпусе не 3, а 6 принятых (`ok`) файлов зависят от `testsub` в каталоге и получают `refused:catalogue` в пустом хранилище (`[B12-10]`). |
| 7 | **Замена `@sleep` на `@until` и оставшиеся сны (`ADR-0080` доп. (17) п. 4)** | **Блокер / С правками** | 1) **Блокер `[B12-2]`:** в `М11/03` сц. `03-generations-and-mark` шаг 6 замена `@sleep 12` на `@until 30 ... {"rev": "@not($r1)"}` сравнивает поколение отчёта с `$r1`, снятым на шаге 3 **до** создания `c3` и ожидания снимка на шаге 5. Любой фоновый отчёт хранителя `m1` с `domain/backup-taken` во время шагов 4–5 продвигает `rev` до `$r1 + 1` без снимка `testsub/snapshot/w-1`, из-за чего шаг 6 завершается мгновенно, а шаг 9 падает.<br>2) **Существенная `[B12-11]`:** в `М10/05` сц. `01-start` шаг 4 замена `@sleep 10` на `@until 20` с условием, являющимся подмножеством шага 3, превратила шаг 4 в мгновенный холостой вызов (0 мс), сломав проверку первого продления аренды слота; в `М11/10` и `М11/12` 5 замен `@sleep` на `@until` дублируют следующий шаг.<br>3) **Существенная `[B12-12]`:** в `М10/05` сц. `07-tie-first-by-name` шаг 6 оставлен `@sleep 12`, хотя он ждёт наблюдаемого события (пульсов двух воркеров). |
| 8 | **Счёты сценариев и шагов между `scenarios.tsv`, `README.md` и Н5** | **С правками** | В перенесённых уроках 1 и 2 счёты совпадают. В `М10_Platform/spec/08-events-resource-requests.norms.md:774` и `Source/tests/testdata/acceptance/М10_Platform/08/README.md:46` остался старый счёт `121 шаг` вместо фактических `130` (`[B12-15]`). |

---

## 2. Находки (по убыванию серьёзности)

### Блокеры

#### [B12-1] `Блокер` — Вопрос к «Архитектору»: при переносе урока 2 (`Platform/02-installer`) не созданы схемы семей данных в диалекте в `Platform/02-installer/data/` и не переключён `Platform/common/data/catalog.tsv` (нарушение `ADR-0088 п. 8`)

- **Место:** `Platform/common/data/catalog.tsv:2-5`, `decisions/0088-схемы-семей-данных-источник-в-диалекте.md:111-118`, `Platform/module-design.md:52`.
- **Цитата:**
  - `decisions/0088-схемы-семей-данных-источник-в-диалекте.md:111-118`:
    > «## 8. Переход — с уроками в стадии B, без отдельной волны
    > Перевод семей в диалект не выделяется в отдельную предварительную фазу, а входит в обязанность урока при его переносе в стадии B:
    > Когда урок-владелец переносится в `Platform/<NN>-<процесс>/`:
    > 1. его семьи получают `<семья>.form.yaml` и `<семья>.outcomes.tsv` в `Platform/<NN>-<процесс>/data/`...
    > 2. строка в `Platform/common/data/catalog.tsv` переключается на новый путь; старый файл в `Platform/common/data/{row,object,payload}/` удаляется, когда на него больше нет ссылок».
  - `Platform/common/data/catalog.tsv:2-5`:
    ```tsv
    row	platform/config/doors	P/01.3	01-store	01-store	../../01-store/data/configstore-doors.form.yaml	{"doors":{"console":{"listen":"127.0.0.1:18080"}}}	{"doors":{}}
    row	platform/config/epoch_floor	P/01.2	01-store	01-store	../../01-store/data/epoch_floor.form.yaml	{"min_epoch":5}	{"min_epoch":-1}
    row	platform/spec/<sub>	P/02.3	02-installer	all processes (P/02.3)	row/spec-row.schema.yaml	{"name":"testsub","unit":{"name_field":"name"},"heartbeat":{"interval_s":10,"ttl_s":30}}	{"name":123}
    row	platform/spec/<sub>/rev	P/02.3	02-installer	all processes (P/02.3)	row/spec-rev.schema.yaml	{"spec_rev":1}	{"spec_rev":0}
    ```
- **Контрпример:** Урок 1 (`01-store`) при переносе создал `Platform/01-store/data/{configstore-doors,epoch_floor}.{form.yaml,outcomes.tsv}` и переключил строки 2–3 в `catalog.tsv`. Урок 2 (`02-installer`), владеющий строками `platform/spec/<sub>` и `platform/spec/<sub>/rev` (глава `P/02.3`, уже перенесённая в `Platform/02-installer/spec/02.3-installer.norms.md`), каталог `Platform/02-installer/data/` не создал,`.form.yaml`/`.outcomes.tsv` не добавил и оставил `catalog.tsv:4-5` на старых JSON Schema `row/spec-row.schema.yaml` и `row/spec-rev.schema.yaml` (в `Platform/module-design.md:52` до конца стадии B откладывалась только глава `2.2` канонического вида, а не глава `2.3`).
- **Нарушенный источник:** `ADR-0088` п. 8 и критерий Confirmation `ADR-0088` («100% строк `catalog.tsv` перенесённых уроков ведут в `Platform/<NN>-<процесс>/data/*.form.yaml`»).
- **Последствие:** Генератор урока 2 и читатели семей `platform/spec/<sub>` и `platform/spec/<sub>/rev` не получают схем семей данных в целевом диалекте `ADR-0088` и набора `.outcomes.tsv`.

---

#### [B12-2] `Блокер` — Регрессия гонки в `М11_Domain/03` сценарий `03-generations-and-mark` шаг 6: замена `@sleep 12` на `@until 30 ... {"rev": "@not($r1)"}` проверяет отличие от старого `$r1` (шаг 3) и срабатывает мгновенно от фонового отчёта `domain/backup-taken` без снимка `testsub/snapshot/w-1`

- **Место:** `Source/tests/testdata/acceptance/М11_Domain/03/scenarios.tsv:36-42`, `Source/tests/testdata/acceptance/М11_Domain/03/README.md:54-57,65`.
- **Цитата:**
  - `Source/tests/testdata/acceptance/М11_Domain/03/scenarios.tsv:36-42`:
    ```tsv
    03-generations-and-mark	3	resource GET /v1/objects/domain/members/m1/reported?scope=local	200 {"rev": "$r1", "keys_rev": "@any", "pinned": "@any"}
    03-generations-and-mark	4	member m1 console POST /counters {"name": "c3"}	201
    03-generations-and-mark	5	@until 30 member m1 resource GET /v1/objects/testsub/snapshot/w-1?scope=local	200
    03-generations-and-mark	6	@until 30 resource GET /v1/objects/domain/members/m1/reported?scope=local	200 {"rev": "@not($r1)"}
    03-generations-and-mark	7	resource GET /v1/objects/domain/members/m1/reported?scope=local	200 {"rev": "$r2", "base": "@not(0)"}
    03-generations-and-mark	8	ASSERT $r1 != $r2	ok
    03-generations-and-mark	9	resource GET /v1/objects/domain/members/m1/reports/$r2?scope=local	200 {"objects": {"testsub/snapshot/w-1": "@any"}}
    ```
  - `Source/tests/testdata/acceptance/М11_Domain/03/README.md:54-57`:
    > «член `m1` — хранитель, и `domain/backup-taken` в его отчёте даёт своё поколение в любой момент прогона. Поэтому шаг 5 ждёт у `m1` сам объект `testsub/snapshot/w-1` (размещение `c3`), шаг 6 — два прохода агента, и только шаг 7 берёт последнее поколение».
- **Контрпример:** Переменная `$r1` связывается на шаге 3 **до** создания счётчика `c3` (шаг 4) и **до** появления снимка `testsub/snapshot/w-1` у `m1` (шаг 5, ждёт прохода контроллера и воркера до 5–10 с). Если за время выполнения шагов 4–5 (пока `testsub/snapshot/w-1` у `m1` ещё не создан) член `m1` как хранитель примет резервную копию и отправит отчёт с обновлённым `domain/backup-taken`, то `domain/members/m1/reported` на держателе уже получит поколение `rev = $r1 + 1` (в котором ещё нет `testsub/snapshot/w-1`). Тогда шаг 6 (`@until 30 ... {"rev": "@not($r1)"}`) завершится **мгновенно (за 0 мс)** на этом промежуточном поколении, шаг 7 свяжет `$r2 = $r1 + 1`, и шаг 9 упадёт с 200 без ключа `testsub/snapshot/w-1` в `reports/$r2`. Именно эту гонку ранее закрывали коммитами `16cbc12e29` и `de017f73e9`. Кроме того, в `README.md` строка 56 («шаг 6 — два прохода агента») теперь противоречит строке 65 («сц. 03 шаг 6 ждёт нового поколения отчёта»).
- **Нарушенный источник:** `ADR-0080` доп. (17) п. 4; `skills/lesson-spec/references/review-checklist.md` («Проверка таймингов сценария», «Асинхронная гонка чтения после записи»); `Source/tests/testdata/acceptance/М11_Domain/03/README.md:54-57`.
- **Последствие:** Недетерминированное падение шага 9 сценария `03-generations-and-mark` при совпадении фонового `backup-taken` с шагами 4–5. Чтобы ждать именно отчёт со снимком без `@sleep`, нужно либо снимать промежуточное поколение `$r_snap` из `reported` сразу **после** шага 5 и ждать `rev: "@not($r_snap)"` (но и тогда во время после шага 5 может прийти ещё один `backup-taken` от другого процесса до прохода агента отчётов, хотя агент отчётов сам собирает локальные объекты и шлёт весь набор), либо ждать появления самого `testsub/snapshot/w-1` в отчёте.

---

### Существенные находки

#### [B12-3] `Существенная` — Рассинхронизация номера шага сценария `15-service-doors` в остатке `М10_Platform/11`: шаг `1` в `scenarios.tsv` против «шаг 9» в Н5 и `README.md`

- **Место:** `Source/tests/testdata/acceptance/М10_Platform/11/scenarios.tsv:40` против `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:142`, `Source/tests/testdata/acceptance/М10_Platform/11/README.md:3,50,65`, `Source/tests/testdata/acceptance/М10_Platform/11/corrections.tsv:23`.
- **Цитата:**
  - `Source/tests/testdata/acceptance/М10_Platform/11/scenarios.tsv:40`:
    ```tsv
    15-service-doors	1	console POST /counters/c1/poke {}	503 {"error": "unavailable", "detail": "@any"}
    ```
  - `Source/tests/testdata/acceptance/М10_Platform/11/README.md:3,50`:
    > «> При переносе `P/01` и `P/02` сценарии 01–07, 09, 10, 12, 13, 18, 22, 23 и шаги 1–8 сц. 15 перенесены в `Platform/01-store/acceptance/` и `Platform/02-installer/acceptance/`; номера оставшихся сценариев и шагов не меняются.»
    > «В сценарии остаётся шаг 9 (`door.pass`, `P/04.4`): `POST /counters/c1/poke {}` на консоли без живого воркера с дверью — `503 unavailable` (Н1.8, B26).»
  - `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:142`:
    > `| 15 | шаг 9: door.pass без воркера с дверью — 503 (B26) | Н1.8 |`
- **Контрпример:** В `scenarios.tsv` шаг записан под номером `1` (так как `check_spec.py` требует нумерации шагов `1..N`), тогда как `README.md:3,50,65`, `corrections.tsv:23` и таблица Н5 в `11-the-platform-on-a-box-and-a-cluster.norms.md:142` называют его «шаг 9» и утверждают, что номера шагов не менялись.
- **Нарушенный источник:** `skills/lesson-spec/references/review-checklist.md` («Таблицы, которые обязаны сходиться построчно: `scenarios.tsv` ↔ таблица сценариев в Н5 ↔ `acceptance/NN/README.md`»).
- **Последствие:** Расхождение идентификатора шага между исполняемым `scenarios.tsv` (`15-service-doors` шаг 1) и нормативной таблицей Н5 / `README.md` (шаг 9).

---

#### [B12-4] `Существенная` — Неполнота `Platform/common/id-map.tsv`: отсутствует строка для `P/01.3-09` в колонке `new`, а также не добавлены строки сценариев, шагов и векторов перенесённых уроков 1 и 2

- **Место:** `Platform/common/id-map.tsv:1-5,126,194,201-202`, `Platform/01-store/spec/01.3-store.norms.md:304`, `decisions/0083-модуль-платформа-по-процессам-и-дополнения-м10-м11.md:191`.
- **Цитата:**
  - `Platform/01-store/spec/01.3-store.norms.md:304`:
    > `- [ ] **P/01.3-09** проверка TLS-пира демоном Н1.6: до запуска воркера `GET /v1/get?key=testsub/items/a` по Unix-сокету — 200; с клиентским сертификатом `CN=intruder` на внутреннем mTLS-адресе хранилища — отказ соединения или HTTP 4xx (из М10/6-12 и М10/11-11)`
  - `Platform/common/id-map.tsv:126,194`:
    ```tsv
    norm	М10/6-12	P/06.2-08	06-security	mTLS порт, CN, hot-reload и /metrics без mTLS в P/06.2-08; проверка хранилищем по Unix-сокету и отказ чужому CN выделены в P/01.3-09
    norm	М10/11-11	P/06.2-10	06-security	сборка полного TLS-дерева и mTLS всех демонов в P/06.2-10; приём внутреннего mTLS-слушателя самим configstore — в P/01.3-09
    ```
  - `Platform/common/id-map.tsv:5`:
    > `# Строки сценариев, шагов и векторов добавит перенос урока.`
- **Контрпример:**
  1. Для разделённого пункта `М10/11-18` в `id-map.tsv:201-202` заведены две строки (`М10/11-18 -> P/06.2-12` и `М10/11-18 (часть) -> P/02.4-15`), поэтому `P/02.4-15` присутствует в колонке `new`. Для аналогично выделенного `P/01.3-09` отдельной строки с `new = P/01.3-09` и `owner = 01-store` в `id-map.tsv` нет (он упомянут только в текстовом комментарии `note` у строк `06-security`).
  2. Несмотря на завершённый перенос уроков 1 и 2 и обещание в `id-map.tsv:5` («Строки сценариев, шагов и векторов добавит перенос урока») и требование `ADR-0083` доп. (5) («Таблица `Platform/common/id-map.tsv` ведёт старые и новые идентификаторы норм, сценариев, шагов и векторов»), в `id-map.tsv` все 358 строк имеют `kind = norm` — ни одной строки для перенесённых сценариев, шагов (например, разделённого сценария `М10/11` сц. 15) и векторов не добавлено.
- **Нарушенный источник:** `ADR-0083` доп. (5) и `Platform/common/id-map.tsv:5`.
- **Последствие:** Автоматическая сверка `id-map.tsv` по колонке `new` для `owner == 01-store` не находит `P/01.3-09`, а трассировка перенесённых сценариев и векторов в `id-map.tsv` отсутствует.

---

#### [B12-5] `Существенная` — Вопрос к «Архитектору»: нарушение самодостаточности `Platform/02-installer/spec/02.4-installer.norms.md` (`P/02.4-14`) — исполняемые правила `w2cctl secrets new|seal|rotate|status` остались в прозе `М10/7 Н1.2`

- **Место:** `Platform/02-installer/spec/02.4-installer.norms.md:214-221,438`, `М10_Platform/spec/07-secrets-and-sealing.norms.md:70-108`.
- **Цитата:**
  - `Platform/02-installer/spec/02.4-installer.norms.md:217-221`:
    > «`status` и `seal` обходят `*_secret` на любой глубине (включая json-поле) по правилам урока 7 Н1.2 (`current`/`older` только при открытии со своим AAD; известный kid, который не открывает, — `?`, как чужой; `seal` доводит обход до конца и отвечает кодом 1). Коды `new`/`rotate`/`seal`/`status` и сохранение файла при отказе — урок 7 Н1.2; строки отказов — Н4 ниже.»
  - `Platform/02-installer/spec/02.4-installer.norms.md:438`:
    > `- [ ] **P/02.4-14** \`w2cctl secrets new|seal|rotate|status\` — чтением урока 7 Н1.2`
- **Контрпример:** По `ADR-0083` доп. (5) («Критерий самодостаточности»):
  > «Реализация или генератор процесса X в стадии C получает общие контракты `Platform/common/` и папку своего урока `Platform/NN-X/`. Если правило, нужное X для прохождения его приёмки или векторов, написано только в прозе другого урока — это пробел контракта: правило либо переносится в `Platform/common/`, либо входит в норму самого урока X».
  Сейчас формат файла кольца `platform.key` (`current: <kid>`, `keys: {<kid>: <base64>}`), генерация 32 случайных байт и права `0600` при `new`, выбор `k<max+1>` при `rotate`, формат конверта `enc:v2:<kid>:<nonce_b64>:<ct_b64>`, построение AAD `<полный ключ строки>\0<путь поля через точку>` (например `platform/config/doors\0doors.console.tls_key_secret`) и формат вывода `status` (`<путь поля>: <статус>`) находятся только в `М10_Platform/spec/07-secrets-and-sealing.norms.md:70-108` (и по `id-map.tsv` предназначены в `P/03.5` и `P/06.2`), но не в `Platform/common/` и не в `Platform/02-installer/`.
- **Нарушенный источник:** `ADR-0083` доп. (5) («Критерий самодостаточности»).
- **Последствие:** Генератор процесса `02-installer` (`w2cctl`) в стадии C в режиме чистой комнаты не сможет реализовать подкоманды `w2cctl secrets new|seal|rotate|status` и пройти пункт `P/02.4-14`. Контракт формата кольца `platform.key`, конверта `enc:v2:` и AAD необходимо либо вынести в `Platform/common/`, либо включить в `02.4-installer.norms.md`.

---

#### [B12-6] `Существенная` — Расхождение `Platform/common/DIALECT.md` (§ 5, § 7) и генератора прозы `section.py` с решением Ф1 свода журналов, `judge.py` и корпусом (`c9_xclass_number_overflow`) по классу отказа чисел вне пределов и пустых значений под `x-class`

- **Место:** `Platform/common/DIALECT.md:94-95,147-148`, `skills/lesson-spec/scripts/form_source/section.py:92-95`, `Platform/02-installer/spec/02.1-installer.norms.md:57,60,65,677` против `decisions/inbox/2026-10-19-диалект-по-журналам.md:45` (Ф1), `skills/lesson-spec/scripts/form_source/judge.py:135-138,144-156` и `Platform/02-installer/acceptance/1/classes.tsv:148`.
- **Цитата:**
  - `Platform/common/DIALECT.md:94-95`:
    > «Закон 4 (множество классов на дереве). Каждое нарушение формы помечает свой путь в дереве одним классом из `{key, value, reference}`:
    > - все пути из `numbers` и `empties` — отказ `value`;»
  - `Platform/common/DIALECT.md:147-148`:
    > «Числа и пустые значения из слоя текста проверяются в слое формы по схеме:
    > - целое по модулю больше `int_max`, дробное вне `float_max` и `nonfinite` — отказ `value` на пути значения;»
  - `Platform/02-installer/spec/02.1-installer.norms.md:60,65` (сгенерировано `section.py:92-95`):
    > `- \`int\` — \`-?(0|[1-9][0-9]*)\`; по модулю больше \`9007199254740991\` — отказ \`value\`.`
    > `- \`float\` — \`...\`; вне \`1.7976931348623157e+308\` или \`nonfinite\` — отказ \`value\`.`
- **Контрпример:** В `decisions/inbox/2026-10-19-диалект-по-журналам.md:45` (решение Ф1) зафиксировано: «число вне пределов — это отказ типа узла на его пути; класс отказа определяется по тому же правилу `x-class`, что и любой другой отказ типа/значения на этом узле (`value`, если нет ближайшего `x-class`). Включить случай `domain: {names: {"b/": {exclusive_with: domain/users, grant: 1e400}}}` → `reference` в корпус 2.1». Этот случай включён в корпус (`c9_xclass_number_overflow.subsystem.yaml`, `classes.tsv:148` требует `reference`), и `judge.py:135-138` выдаёт для него `x-class` ближайшего предка (`reference`). Но в `DIALECT.md:94-95,147-148` и в `section.py:92-95` (`02.1-installer.norms.md:60,65`) осталось безусловное утверждение «отказ `value`».
- **Нарушенный источник:** `decisions/inbox/2026-10-19-диалект-по-журналам.md:45` (Ф1), `ADR-0087` доп. (3), `Platform/02-installer/acceptance/1/classes.tsv:148`.
- **Последствие:** Генератор на Go или Python в чистой комнате, реализующий проверку по `DIALECT.md` и тексту `02.1-installer.norms.md`, вернёт `refused:value` вместо `refused:reference` на `c9_xclass_number_overflow`.

---

#### [B12-7] `Существенная` — Расхождение `DIALECT.md` и `judge.py` с решением Ф18 свода журналов: `depth(T(p))` вычисляется по сырому поддереву без подстановки `default`

- **Место:** `decisions/inbox/2026-10-19-диалект-по-журналам.md:62` (Ф18), `Platform/common/DIALECT.md:50,125,130`, `skills/lesson-spec/scripts/form_source/judge.py:72-78,294-298,405-406`.
- **Цитата:**
  - `decisions/inbox/2026-10-19-диалект-по-журналам.md:62`:
    > «| Ф18 | `depth`: по входному дереву или дереву с умолчаниями | Только Gemini | Узлы с `default` в `02.1` — листья на глубине ≤ 3; решение — только об умолчаниях: по дереву с умолчаниями, § 2 `default` дополнить. |»
  - `Platform/common/DIALECT.md:50`:
    > «| `default` | у поля `fields` | литерал JSON; значение условий `is`/`is_not`, `@путь` отношений и канонического вида, когда ключа нет |»
  - `skills/lesson-spec/scripts/form_source/judge.py:72-78,405-406`:
    ```python
    def _depth(v: Any) -> int:
        if isinstance(v, dict):
            return 1 + max((_depth(x) for x in v.values()), default=0)
        if isinstance(v, list):
            return 1 + max((_depth(x) for x in v), default=0)
        return 0
    ...
    if p[0] == "depth":
        return _depth(_resolve_T(root, form, p[1], env)) <= p[2]
    ```
- **Контрпример:** Если в схеме формы у вложенного поля задан `default`, а входной документ передал пустой словарь `{}` на родительском узле, `_resolve_T` возвращает сырой словарь `{}` из `root`, и `_depth({})` возвращает `1`, тогда как по дереву с умолчаниями (с подстановкой `default`-ключа внутри `{}`) глубина равна `2`. Ни `DIALECT.md` § 2 (`default`) и § 6 (`depth`), ни `_depth` в `judge.py` не были обновлены по решению Ф18.
- **Нарушенный источник:** `decisions/inbox/2026-10-19-диалект-по-журналам.md:62` (Ф18), `ADR-0087` доп. (3).
- **Последствие:** Несоответствие `DIALECT.md` и эталонного исполнителя `judge.py` принятому решению Ф18.

---

#### [B12-8] `Существенная` — Слой текста `spec_schema/textlayer.py` отвергает с `refused:text` одиночный `-` с пробелом в потоковой коллекции (`[ - , a ]`, `{unit: - }`), нарушая норму `word` и решение Т16

- **Место:** `skills/lesson-spec/scripts/spec_schema/textlayer.py:34,118-123`, `Platform/02-installer/spec/02.1-installer.norms.md:45`, `decisions/inbox/2026-10-19-диалект-по-журналам.md:27` (Т16).
- **Цитата:**
  - `Platform/02-installer/spec/02.1-installer.norms.md:45`:
    > «- `word` (голое слово) — скаляр без кавычек, не подошедший ни под один из четырёх образцов выше; ... одиночный `-` в потоковой коллекции и значении — слово.»
  - `decisions/inbox/2026-10-19-диалект-по-журналам.md:27` (Т16):
    > «Новое правило о «`-` в потоке» не вводить: оба читали по норме; расхождение пилота на `[-, a]` было багом регулярного выражения эталона.»
  - `skills/lesson-spec/scripts/spec_schema/textlayer.py:34,118-123`:
    ```python
    RE_DASH_VALUE = re.compile(r'^([ \t]*[^#\n:]+:[ \t]+)-(?=[ \t]*(?:#.*)?$)', re.M)
    ```
- **Контрпример:** Случай корпуса `c9_flow_lone_dash_ok.subsystem.yaml` проверяет `strings: [-, a]` (без пробела между `-` и `,`), где парсер YAML 1.2 сам считает `-,` частью токена до запятой. Однако если после `-` в потоковой коллекции стоит пробел — например `strings: [ - , a ]`, `strings: [a, - ]` или `display: {unit: - }` — в YAML 1.2 `-` с последующим пробелом является индикатором блочного списка (`block sequence indicator`), запрещённым в flow-контексте. Так как `RE_DASH_VALUE` в `textlayer.py:34` подменяет одиночный `-` только в конце строки блочного `ключ: -`, `ruamel.yaml` в `textlayer.py:125` падает с `ParserError: while parsing a flow node expected the node content, but found '-'`, и `parse_yaml_subset` возвращает `refused:text` вместо того, чтобы прочитать `-` как голое слово `"-"` (и затем в слое формы получить `ok` для `strings: [ - , a ]` или `refused:value` для `display: {unit: - }`).
- **Нарушенный источник:** `Platform/02-installer/spec/02.1-installer.norms.md:45` (Н1.2 `word`), `decisions/inbox/2026-10-19-диалект-по-журналам.md:27` (Т16).
- **Последствие:** Неполная реализация нормы «одиночный `-` в потоковой коллекции и значении — слово» в эталонном `textlayer.py` и отсутствие в корпусе случая с пробелом после `-` в потоковой коллекции (`[ - , a ]`).

---

#### [B12-9] `Существенная` — Вопрос к «Архитектору»: в `02.1-installer.form.yaml` и `02.1-installer.references.tsv` не закрыты два пробела против норм Н1.3 и Н1.4 (`display.options` для полей таблиц с `enum` и запрет `schema` при `type != json`)

- **Место:**
  1. `Platform/02-installer/spec/02.1-installer.references.tsv:70-71`, `Platform/02-installer/spec/02.1-installer.form.yaml:139,259-264`, `Platform/02-installer/spec/02.1-installer.norms.md:107,385-386,825-826`.
  2. `Platform/02-installer/spec/02.1-installer.form.yaml:98,100-103,140,142-145,185`, `Platform/02-installer/spec/02.1-installer.norms.md:107,688`.
- **Цитата:**
  1. В `02.1-installer.references.tsv:70-71`:
     ```tsv
     display.options.{}	reference		. in keys(unit.fields ? has enum)	поле в display.options объявлено в unit.fields с enum
     display.options.$o.{}	reference	$o in keys(unit.fields ? has enum)	. in @unit.fields.$o.enum	значение в display.options.<поле> входит в enum поля
     ```
     При этом в `02.1-installer.form.yaml:139` у `tableField` разрешён `enum: {type: array, min_items: 1, unique_items: true, items: {type: string, pattern: ident}}`, а норма `М10/9 Н1.2` (`09-the-console.norms.md:60`) гласит: `options: {<имя>: {<значение>: <слово>}} # у поля с enum — значения из enum`.
  2. В `02.1-installer.form.yaml:185` узел `jsonSchemaLite` озаглавлен `title: "Узкое подмножество JSON Schema у поля с type: json"`, и в `02.1-installer.norms.md:107` написано: «Вложенная `schema` поля с `type: json` проверяется здесь же по узкому подмножеству JSON Schema». Однако в `unitField.rules` (`02.1-installer.form.yaml:100-103`) и `tableField.rules` (`142-145`) нет правила `{when: {is_not: {type: [json]}}, forbid: [schema]}`.
- **Контрпример:**
  1. Спека с `tables: {runs: {fields: {state: {type: string, enum: [queued, done]}}}}` и `display: {options: {state: {queued: "В очереди"}}}` отвергается по строке 70 с `refused:reference`, если `state` — поле таблицы, а не `unit.fields`.
  2. Спека с `unit: {name_field: id, fields: {id: {type: string}, count: {type: int, schema: {type: object}}}}` (где `schema` указана у поля типа `int`) принимается `judge.py` с вердиктом `ok`!
- **Нарушенный источник:** `Platform/02-installer/spec/02.1-installer.norms.md:107,688` (Н1.3 `jsonSchemaLite`), `М10_Platform/spec/09-the-console.norms.md:60` (Н1.2 `display.options`), а также разбор ревью `ADR-0085`/`ADR-0087` (пункт Р5).
- **Последствие:** Источник формы 2.1 пропускает бессмысленный `schema` у не-`json` полей и запрещает `display.options` для `enum`-полей таблиц.

---

#### [B12-10] `Существенная` — Выборка `spec put` в `Platform/02-installer/acceptance/1/README.md` пропускает класс отказа `refused:name`, а описание «трёх принятых файлов» расходится с 6 файлами корпуса, зависящими от `testsub`

- **Место:** `Platform/02-installer/acceptance/1/README.md:19,53-62`, `Platform/02-installer/spec/02.1-installer.norms.md:947,961,1039-1044`, `Platform/02-installer/acceptance/1/classes.tsv`.
- **Цитата:**
  - `Platform/02-installer/acceptance/1/README.md:19`:
    > «Приёмка раздела 2.1 или проверка генератора в стадии C (`ADR-0080` доп. (17) п. 2) СЛЕДУЕТ прогонять через путь установки спеки (`spec put` реализации, глава 2.3 Н3) выборку: все случаи с вердиктом `ok`, по одному отказу на каждый класс `refused:<класс>` из `classes.tsv` (первый по имени случая), три названных ниже принятых файла и все установки `puts.tsv`.»
  - `Platform/02-installer/acceptance/1/README.md:55-62`:
    > «Три принятых файла (`bound_to_string.subsystem.yaml`, `blob_required_false.subsystem.yaml`, `secrets_reader_domainconsole.subsystem.yaml`) несут `name: testsub2` и перекрёстные ссылки на уже установленную подсистему `testsub` ... В пустом хранилище эти три файла верно получают `refused:catalogue`...»
- **Контрпример:**
  1. В `Platform/02-installer/acceptance/1/classes.tsv` (149 строк) присутствуют только 4 класса (`text`, `key`, `value`, `reference`). Все 9 случаев корпуса с вердиктом `refused:name` (`k38_sub_hyphen`, `k38_sub_leading_digit`, `k38_sub_platform`, `k38_sub_too_long`, `k38_sub_underscore`, `name_missing`, `name_reserved_platform`, `name_uppercase`, `name_with_slash`) в `classes.tsv` **не входят**. Поэтому выборка «по одному отказу на каждый класс из `classes.tsv`» даёт только 4 отказа и **вообще не проверяет шаг 2 Н3 (`refused:name`)** через `spec put`.
  2. В корпусе `verdicts.tsv` не 3, а **6** принятых (`ok`) случаев ссылаются на `testsub` в полях, проверяемых шагом 4 `загрузить_каталог` (`02.3-installer.norms.md:274-279`): помимо трёх названных файлов с `name: testsub2`, ещё и 3 файла с `name: alpha`: `c3_near_by_ok.subsystem.yaml` (`near: {sub: testsub, by: kind}`), `c3_about_sub_ok.subsystem.yaml` (`about: {sub: testsub, field: name}`) и `c6_secrets_reads_with_slash_ok.subsystem.yaml` (`secrets: {reads: [testsub/a/]}`). В пустом хранилище все 6 (а не только 3) получают `refused:catalogue` на `spec put`, а после установки `puts.tsv` шаг 1 (`put_1_testsub_v1`) все 6 проходят `spec put` с `ok`. Кроме того, формулировка «все случаи с вердиктом `ok`, ..., три названных ниже принятых файла» перечисляет эти три файла дважды, так как они уже входят во «все случаи с вердиктом `ok`».
- **Нарушенный источник:** `ADR-0080` доп. (17) п. 2 («включающий все случаи `ok`, по одному отказу каждого класса `refused:<класс>`, три принятых файла и цепочки `puts.tsv`»), `Platform/02-installer/spec/02.1-installer.norms.md:947` (пять классов отказа на шагах 1–3: `text`, `name`, `key`, `value`, `reference`).
- **Последствие:** При прогоне выборки по букве `README.md:19` класс отказа `refused:name` не тестируется в `spec put`, а прогон всех `ok`-случаев без предварительной установки `testsub` упадёт на `c3_near_by_ok`, `c3_about_sub_ok` и `c6_secrets_reads_with_slash_ok`, если прогонщик подготовит `testsub` только для «трёх названных файлов».

---

#### [B12-11] `Существенная` — Замена `@sleep` на `@until` в `М10_Platform/05` сц. `01-start` шаг 4 превратила ожидание первого продления аренды в мгновенный холостой вызов (0 мс), а в `М11_Domain/10` и `12` продублировала соседние шаги

- **Место:**
  1. `Source/tests/testdata/acceptance/М10_Platform/05/scenarios.tsv:5-10`, `Source/tests/testdata/acceptance/М10_Platform/05/README.md:146`.
  2. `Source/tests/testdata/acceptance/М11_Domain/10/scenarios.tsv:57-60,185-187,252-255`.
  3. `Source/tests/testdata/acceptance/М11_Domain/12/scenarios.tsv:16-17,32-33`.
- **Цитата:**
  - `Source/tests/testdata/acceptance/М10_Platform/05/scenarios.tsv:5-10`:
    ```tsv
    01-start	3	@until 20 store GET /v1/get?key=testsub/slots/w-1	200 {"items": {"holder": "$h1", "until": "@time", "released": "false", "gen": "1"}}
    01-start	4	@until 20 store GET /v1/get?key=testsub/slots/w-1	200 {"items": {"holder": "$h1", "released": "false", "gen": "1"}}
    01-start	5	store GET /v1/get?key=testsub/slots/w-1	200 {"items": {"holder": "$h1", "released": "false", "gen": "1", "until": "$u1"}}
    01-start	6	@until 20 store GET /v1/get?key=testsub/slots/w-1	200 {"items": {"until": "@not($u1)"}}
    ```
- **Контрпример:**
  1. В `М10/05` сц. `01-start` условие шага 4 (`holder: $h1, released: false, gen: 1`) является строгим подмножеством условия шага 3, которое только что выполнилось! Поэтому шаг 4 завершается **немедленно за 0 мс** на первой же попытке, ничего не ожидая. Чтобы проверить два продления аренды подряд без `@sleep`, шаг 3 должен связывать первоначальный `"until": "$u0"`, шаг 4 — ждать `"until": "@not($u0)"` (первое продление), шаг 5 — связывать `"until": "$u1"`, а шаг 6 — ждать `"until": "@not($u1)"` (второе продление).
  2. В `М11/10` (`02-emergency-move` шаги 13 и 16, `09-move-live-holder` шаги 7 и 9, `12-handover-then-move` шаги 8 и 11) и `М11/12` (`01-quiet-member` шаги 9 и 10, `02-members-only-to-the-lagging` шаги 2 и 3) бывший шаг `@sleep` заменён на `@until <d> <команда>`, но следующий за ним шаг (или шаг через один `ASSERT`) выполняет **в точности тот же самый HTTP-запрос с тем же самым ожиданием** (например, в `М11/12` шаг 2: `@until 10 member m3 resource GET /v1/objects/domain/members/m1?scope=local` → `200 {"role": "holder"}`, и тут же шаг 3: `member m3 resource GET /v1/objects/domain/members/m1?scope=local` → `200 {"role": "holder"}`).
- **Нарушенный источник:** `ADR-0080` доп. (17) п. 4; `Source/tests/testdata/acceptance/М10_Platform/05/README.md:146`.
- **Последствие:** В `М10/05` сц. `01-start` вместо двух продлений аренды слота проверяется только одно; в `М11/10` и `М11/12` сценарии содержат холостые дублирующиеся шаги.

---

#### [B12-12] `Существенная` — В `М10_Platform/05` сценарий `07-tie-first-by-name` шаг 6 оставлен `@sleep 12`, хотя он ждёт наблюдаемого события (появления пульсов двух воркеров)

- **Место:** `Source/tests/testdata/acceptance/М10_Platform/05/scenarios.tsv:60-64`, `Source/tests/testdata/acceptance/М10_Platform/05/README.md:155`.
- **Цитата:**
  - `Source/tests/testdata/acceptance/М10_Platform/05/scenarios.tsv:60-64`:
    ```tsv
    07-tie-first-by-name	5	@start worker-2	ok
    07-tie-first-by-name	6	@sleep 12	ok
    07-tie-first-by-name	7	console POST /counters {"name": "t7"}	201
    ```
  - `Source/tests/testdata/acceptance/М10_Platform/05/README.md:155`:
    > `| 07/6 | 12 с | время перед действием: контроллер видит пульсы обоих воркеров до создания t7 (HEARTBEAT_EVERY 10 с + проход) |`
- **Контрпример:** По `ADR-0080` доп. (17) п. 4 и `review-checklist.md:156-160`:
  > «Ожидание события — `@until` по наблюдаемому признаку (строка, ответ двери, запись журнала), не `@sleep`... `@sleep` — только когда шаг проверяет, что за срок ничего не случилось (отсутствие события, неизменность строки), или норма требует прошедшего времени перед действием, а не перед наблюдением».
  В сц. `07-tie-first-by-name` норма не требует выжидать 12 секунд перед созданием `t7` — сценарию нужно лишь, чтобы оба воркера `w-1` и `w-2` записали свои пульсы и слоты в хранилище до создания `t7` (а по `М10/5 Н3` воркер пишет первый пульс сразу при старте, не дожидаясь `HEARTBEAT_EVERY`). Это напрямую проверяется через `@until 20 store GET /v1/get?key=testsub/heartbeats/w-2` → `200` (или `console GET /servers` с обоими серверами `alive: true`), что выполняется за <1 с вместо фиксированных 12 с сна.
- **Нарушенный источник:** `ADR-0080` доп. (17) п. 4, `skills/lesson-spec/references/review-checklist.md:156-160`.
- **Последствие:** Лишние 12 секунд безусловного ожидания в каждом прогоне `М10/05` и нарушение критерия `ADR-0080` доп. (17) п. 4.

---

### Мелкие находки

#### [B12-13] `Мелкая` — Ошибочные ссылки в `lifecycle.md` уроков `01`, `04`, `05`, `08`, сбитый якорь в `М11_Domain/01..03/README.md` и устаревшая отсылка на сц. 08 в `Platform/01-store/acceptance/2/README.md`

- **Место:**
  1. `Platform/01-store/lifecycle.md:15,16,30,31,37,90` и `Platform/08-domain/lifecycle.md:10`.
  2. `Platform/04-controller/lifecycle.md:11,80,82` и `Platform/05-resource/lifecycle.md:11,55,78`.
  3. `Source/tests/testdata/acceptance/М11_Domain/01/README.md:13`, `02/README.md:12`, `03/README.md:15`.
  4. `Platform/01-store/acceptance/2/README.md:27`.
- **Цитата и контрпример:**
  1. В `Platform/01-store/lifecycle.md:37` (`[P/01.3 Н1.3](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md)`), строке `90` (`[P/02.4 Н1.1](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md)`) и `Platform/08-domain/lifecycle.md:10` (`[P/02.4 Н1.1](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md)`) текст ссылки сменили на `P/01.3` / `P/02.4`, но сам путь оставили ведущим на `11-the-platform-on-a-box-and-a-cluster.norms.md`, откуда эти разделы удалены. Кроме того, в `Platform/01-store/lifecycle.md:15,16,30,31` ссылки на `Н1.3` (`sockets`, `group.join`, «Флаги демона») подписаны как `P/02.4 Н1.3`, хотя раздел `Н1.3` перенесён в **`P/01.3 Н1.3`** (`spec/01.3-store.norms.md:36`), а в `02.4-installer.norms.md` раздела `Н1.3` нет.
  2. В `Platform/04-controller/lifecycle.md:11,80,82` и `Platform/05-resource/lifecycle.md:11,55,78` ссылки `[М10/11]` ведут в `11-the-platform-on-a-box-and-a-cluster.norms.md` за правилами `dirs` (`PLATFORM_DIR/etc/secrets/platform.key`) и `Restart=always` / `RestartSec=2`, которые уже перенесены в `Platform/02-installer/spec/02.4-installer.norms.md` (Н1.1).
  3. В `Source/tests/testdata/acceptance/М11_Domain/01/README.md:13`, `02/README.md:12`, `03/README.md:15` ссылка `[М10/01](../../../../../../Platform/common/acceptance/README.md#стенд--общий-для-приёмки-м10)` содержит битый якорь `#стенд--общий-для-приёмки-м10`, так как заголовок в `Platform/common/acceptance/README.md:3` был переименован в `## Стенд — общий для приёмки уроков модуля «Платформа», М10 и М11`.
  4. В `Platform/01-store/acceptance/2/README.md:27` осталась фраза «(сц. 08 шаг 2 — заголовок роли не читается, пересылка не на коробке)», хотя сценарий 08 перенесён в `Platform/02-installer/acceptance/5/scenarios.tsv` и в `Platform/01-store/acceptance/2/scenarios.tsv` отсутствует.
- **Нарушенный источник:** `ADR-0083` доп. (7) (перенацеливание ссылок при переносе уроков 1–2).
- **Последствие:** Читатель `lifecycle.md` и `README.md` попадает в файл `М10/11`, где соответствующих норм больше нет, либо на несуществующий якорь.

---

#### [B12-14] `Мелкая` — Ошибки номеров строк таблицы отношений, регулярного выражения `null` и слипшихся со словами чисел в `02.1-installer.norms.md` и `acceptance/1/README.md`

- **Место:**
  1. `Platform/02-installer/spec/02.1-installer.norms.md:812-816,972`.
  2. `Platform/02-installer/spec/02.1-installer.scalars.tsv:4`, `Platform/02-installer/spec/02.1-installer.norms.md:57`.
  3. `Platform/02-installer/spec/02.1-installer.norms.md:1001,1003` и `Platform/02-installer/acceptance/1/README.md:77`.
- **Цитата и контрпример:**
  1. В `02.1-installer.norms.md:972` написано: «строки 58, 61 держатся с условием «таблица объявлена», строка 84 снята». Однако в таблице раздела «Форма» (`02.1-installer.norms.md:812-816`) после удаления бывшей строки 3 условные правила `when: $t in keys(tables)` стоят на строках **59** (`rights.unit_of.$t`) и **62** (`servers.show[$i].by`), а на строках 58 и 61 стоят безусловные `. in keys(tables)`.
  2. В `02.1-installer.scalars.tsv:4` и `02.1-installer.norms.md:57` регулярное выражение для `null` записано как `null|Null|NULL|~|` (с завершающей вертикальной чертой `|`, которая в регулярном выражении матчит пустую строку `""`), и рядом дано словесное примечание «пустое значение — отдельно (сказанный ключ без значения, Н1.2а)». Без хвостового `|` (`null|Null|NULL|~`) регулярное выражение точно соответствует четырём литералам `null` и не вводит в заблуждение кодогенератор.
  3. При обновлении счётов в `02.1-installer.norms.md:1001,1003` и `Platform/02-installer/acceptance/1/README.md:77` пропали пробелы перед числами: `дополняет17`, `все21`, `содержит20`, `всех48`, `все21 слова`, `и9/39`.
- **Нарушенный источник:** Точность ссылок и типографика нормативного текста `02.1-installer.norms.md`.
- **Последствие:** Сбитые номера строк в пояснении к покрытию таблицы отношений и опечатки в прозе.

---

#### [B12-15] `Мелкая` — Устаревший счёт шагов (`121` вместо `130`) в `М10_Platform/spec/08-events-resource-requests.norms.md` и `Source/tests/testdata/acceptance/М10_Platform/08/README.md`

- **Место:** `М10_Platform/spec/08-events-resource-requests.norms.md:774`, `Source/tests/testdata/acceptance/М10_Platform/08/README.md:46,166`, `Source/tests/testdata/acceptance/М10_Platform/08/scenarios.tsv`.
- **Цитата:**
  - `М10_Platform/spec/08-events-resource-requests.norms.md:774`:
    > «Приёмка урока — таблица сценариев `Source/tests/testdata/acceptance/М10_Platform/08/scenarios.tsv` (восемь независимых сценариев, 121 шаг; конвенции и стенд — `README.md` рядом с таблицей).»
  - `Source/tests/testdata/acceptance/М10_Platform/08/README.md:46`:
    > «Всего 121 шаг: 113 HTTP, шесть `@start`, `@sleep` и `@sigterm`.»
- **Контрпример:** В `Source/tests/testdata/acceptance/М10_Platform/08/scenarios.tsv` фактически **130 шагов** (в конце того же `README.md:166` указано верно: «Всего 8 сценариев / 130 шагов», но шапка на строке 46 и норма Н5 на строке 774 остались со старым числом `121` и упоминанием `@sleep`, которого в `М10/08/scenarios.tsv` больше нет — там 4 шага `@until`).
- **Нарушенный источник:** `skills/lesson-spec/references/review-checklist.md` («Счёты в прозе»).
- **Последствие:** Противоречие в числе шагов внутри `08/README.md` (`121` против `130`) и в `08-events-resource-requests.norms.md:774`.

---

#### [B12-16] `Мелкая` — Временный разнобой терминов «манифест подсистемы» в `Platform/common/DIALECT.md` и «спека подсистемы» в `Platform/02-installer/spec/02.1-installer.norms.md`

- **Место:** `Platform/common/DIALECT.md:3,12,14,15,20` против `Platform/02-installer/spec/02.1-installer.norms.md:1,3,53`.
- **Цитата:**
  - `Platform/common/DIALECT.md:3`:
    > «На этом диалекте записаны форма манифеста подсистемы (`P/02.1`) и формы семей данных в хранилище, объектах и сообщениях (`Platform/common/data/catalog.tsv`, `ADR-0088`).»
  - `Platform/02-installer/spec/02.1-installer.norms.md:1`:
    > `# 2.1. Спека подсистемы: форма и ссылки — нормы`
- **Контрпример:** По `ADR-0086 п. 6` и `Platform/module-design.md:52` переименование прозы и имён на проводе по `Platform/common/manifest-rename.tsv` запланировано одним коммитом в конце стадии B (сейчас переименованы только суффиксы файлов корпуса `.subsystem.yaml`). Это не блокирует текущий срез, но при финальном коммите стадии B по `manifest-rename.tsv` важно убедиться, что `02.{1..5}-installer.norms.md` и `section.py` синхронизируются с `DIALECT.md`.
- **Нарушенный источник:** `ADR-0086` п. 6.
- **Последствие:** До финального коммита переименования в конце стадии B `DIALECT.md` и `02.1-installer.norms.md` используют разные термины для одного документа.

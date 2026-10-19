# Ревью стадии A (вторая редакция): готовность уроков 1 (`01-store`) и 2 (`02-installer`) к переносу в стадии B

- **Ревьювер:** Gemini («Ревью спецификации»)
- **Срез курса:** `6dc2995cf` (основной срез ревью стадии A 2) + `e455a12d3` (оценка `ADR-0088` доп. (2) в разделе урока 1 по дополнительному поручению «Архитектора»)
- **Предмет:** готовность уроков 1 (`P/01 01-store`) и 2 (`P/02 02-installer`) к поурочному переносу в стадии B (`ADR-0083` с доп. (1)–(6), `ADR-0084` с доп. (1), `ADR-0086` с доп. (1), `ADR-0087` с доп. (1)–(5), `ADR-0088` с доп. (1)–(2), `ADR-0089` с доп. (1)).
- **Вывод по уроку 1 (`P/01 01-store`):** **`с правками`** (переносить до закрытия блокеров №№ 1–4 нельзя; после их устранения урок готов к переносу одним коммитом стадии B).
- **Вывод по уроку 2 (`P/02 02-installer`):** **`с правками`** (переносить до закрытия блокеров №№ 5–10 нельзя; после их устранения урок готов к переносу одним коммитом стадии B).

---

## 1. Главный вопрос: можно ли сейчас переносить уроки 1 и 2?

**Нет, начинать коммиты переноса уроков 1 и 2 прямо со среза `6dc2995cf` / `e455a12d3` нельзя.**
Каркас деления в `Platform/module-design.md`, `Platform/common/id-map.tsv`, `Platform/common/data/catalog.tsv` и `Platform/01-store/`, `Platform/02-installer/` в основе выстроен, а принятое на срезе `e455a12d3` решение `ADR-0088` доп. (2) сняло блокер выбора слов диалекта для схем семей данных. Однако перед переносом остаются **10 блокеров** (4 у урока 1 и 6 у урока 2), без закрытия которых коммиты переноса нарушат критерий самодостаточности `ADR-0083` доп. (5) либо оставят несогласованными входы `check_spec`.

### 1.1. Свод блокеров перед переносом

| № | Урок | Где | Суть блокера |
|---|---|---|---|
| **1** | `P/01` | `Platform/common/data/catalog.tsv:25`, `Platform/common/id-map.tsv:189`, `Platform/01-store/lifecycle.md:56` | Конфликт владельца семьи `platform/epoch_floor`: в `catalog.tsv:25` `owner = М10/3` (`03-worker`), но пол `{floor, generation_at}` пишет и проверяет на `op: floor` и `import` само хранилище (`1.3`, `id-map.tsv:189` → `P/01.3-03`). По `ADR-0083` доп. (5) и `ADR-0088` п. 8 схема `epoch_floor.form.yaml` должна принадлежать `01-store` (`1.3`) и входить в коммит переноса урока 1. |
| **2** | `P/01`, `P/02` | `Platform/common/data/catalog.tsv`, `М10_Platform/spec/01-storage.norms.md` | В `catalog.tsv` пропущен межпроцессный файловый контракт `/etc/w2c/configstore-rights.json` (`02-installer` пишет → `01-store` читает), а также файлы `/etc/w2c/roles/<роль>.env` (`02-installer` пишет → `05-resource` и `w2c-workers.sh` читают) и `recovery_file` (`02-installer` пишет → `08-domain` читает); в `01-storage.norms.md` отсутствует абзац `**Данные**`. |
| **3** | `P/01` | `Platform/common/id-map.tsv:126,194`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:155,166,342-366` | Разрыв самодостаточности `01-store` (`ADR-0083` доп. (5)) по TLS и сертификатам: `М10/6-12` (`сертификат роли и роль процесса`) и `М10/11-11` (`сертификаты и отзыв`) в `id-map.tsv:126,194` отданы целиком в `2.4` (`note = -`), хотя демон `configstore` (`1.3`) сам проверяет mTLS-соединения, `SAN URI urn:w2c:role:configstore` vs `configstore-door`, `CN`, закрытый перечень алгоритмов подписи (`Н1.6 sig`), `ca.next.pem` и отзыв по содержимому `revoked`/`crl.pem`. |
| **4** | `P/01` | `decisions/0088-схемы-семей-данных-источник-в-диалекте.md:158-167` (`e455a12d3`), `М10_Platform/spec/03-units-slots-epochs-lease.norms.md:83` | Принятое `ADR-0088` доп. (2) оставляет на коммит переноса урока 1: (а) фиксацию точного имени ключевого слова `С9` (знак целого у читателя) и заголовка столбцов `.outcomes.tsv` (`С11`) в `DIALECT.md`; (б) выписку `common.unit_id` в `Platform/common/data/common.form.yaml` через диапазоны `\x{HHHH}` (`С7` вместо отвергнутого `С8` `\p{Nd}`), но `М10/3 Н1.3` не закрепляет версию Unicode для категории `Nd` вне ASCII (в отличие от `Unicode 15.0.0` в `М10/7 Н1.1а А4`). |
| **5** | `P/02` | `decisions/0087-форма-спеки-источник-в-диалекте.md:79-85`, `decisions/inbox/2026-10-19-диалект-по-журналам.md:134-151` | Не выполнены входные условия переноса урока 2 по `ADR-0087` доп. (1)–(5): в `2026-10-19-диалект-по-журналам.md` открыты 17 решений (`Т15, Т16, Т28; Ф1, Ф2, Ф9, Ф12, Ф15, Ф18, Ф23; О3, О6, О7, О9, О12, О14, О15`), не внесены в нормы и пилот 3 принятых решения владельца (`В1–В3`), не закрыты 38 из 111 строк `references.tsv` положительными и отрицательными случаями корпуса (`ADR-0087` доп. (1) Р10), а сами `DIALECT.md`, `spec.form.yaml`, `references.tsv`, `scalars.tsv` и построитель ещё не перенесены из пилота в репо курса. |
| **6** | `P/02` | `Platform/module-design.md:52`, `decisions/0089-канонический-вид-спеки-проекция-источника-формы.md:56,101-108` | Противоречие `Platform/module-design.md:52` («установщик пишет его с переноса урока 2») с `ADR-0089` доп. (1) Р11 («Запись канонического вида — отдельная правка поведения после переноса урока 2… п. 7 читать так») и отсутствие нормативной записки со сквозной описью умолчаний спеки по `ADR-0089` доп. (1) Р10 (`ХОД-Спецификация.md:58`). |
| **7** | `P/02` | `decisions/0086-манифест-подсистемы.md:97`, `ХОД-Спецификация.md:58` | Отсутствует таблица `Platform/common/manifest-rename.tsv` (`старое → новое → владелец → потребители`), обязательная по `ADR-0086` доп. (1) Р2 до переноса уроков стадии B. |
| **8** | `P/02` | `Platform/02-installer/README.md:10`, `Platform/module-design.md:52,179`, `Platform/common/id-map.tsv:46`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml` | Разрыв вокруг `GET /spec` (`SpecView`) и `ConsoleRefusal`: по `id-map.tsv:46` `GET /spec` уходит в `P/06.5` (`06-console`), а у `02-installer` собственных HTTP-дверей нет (вопреки `02-installer/README.md:10`). Но если коммит переноса урока 2 удалит `02-the-spec-and-the-strict-loader.{norms.md,api.openapi.yaml}` до переноса урока 6, пропадут норма `GET /spec` и схема `ConsoleRefusal`, на которую по `$ref` ссылаются `09-the-console.api.openapi.yaml` и `10-schema-drain-snapshot-limits.api.openapi.yaml`. |
| **9** | `P/02` | `Platform/common/id-map.tsv:121,122,127,137`, `Platform/module-design.md:52,85,89`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:326-327`, `Platform/02-installer/lifecycle.md:69` | Разрыв самодостаточности `02-installer` (`ADR-0083` доп. (5)): (а) в `М10/11 Н1.5 rules 4` и `02-installer/lifecycle.md:69` в проверку `roles/<роль>.env` скриптом `w2c-workers.sh` ошибочно вписаны `unit_mb` и `base_mb` (параметры SDK воркера из `М10/5 Н1.2`, которых нет в `roles/<роль>.env`); (б) в `id-map.tsv:127` норма `М10/6-13` («вывод прав по смыслу, роли домена») и доменные варианты `06/variants/v4,v5` лежат в `2.5` (шаг чтения 11) без выделения в поздний слой (шаг чтения 15); (в) не согласована принадлежность `w2cctl secrets` между `module-design.md:52` (не названа в `02-installer`), `catalog.tsv:29` (`proc:02-installer`), `id-map.tsv:139` (`6.2` с `note: 2.4`) и `02-installer/lifecycle.md:20` (пропущена в списке подкоманд `w2cctl`). |
| **10** | `P/02` | `Source/tests/testdata/secret_in.tsv`, `Source/tests/testdata/acceptance/М10_Platform/07/secret_in.tsv`, `log_mask.tsv`, `Platform/common/vectors/README.md:14` | Две копии векторных таблиц `secret_in.tsv` (435 vs 432 строки данных) и `log_mask.tsv` (29 vs 25 строк данных) в репозитории разошлись между собой (нарушение `ADR-0003`), а `Platform/common/vectors/README.md:14` ссылается на устаревший `Source/tests/testdata/spec_verdicts.tsv` (138 случаев) вместо корпуса `Source/tests/testdata/acceptance/М10_Platform/02/` (479 случаев). |

---

### 1.2. Что должно войти в коммит переноса каждого урока

#### Коммит переноса урока 1 (`P/01 01-store`)
1. **Общие артефакты `Platform/common/` (вводятся с первым уроком по `ADR-0088` п. 8 и доп. (1)–(2)):**
   - `Platform/common/DIALECT.md` — спецификация диалекта `ADR-0087` + расширение для схем семей данных по `ADR-0088` доп. (2) (слова `С1–С7`, зафиксированное имя слова `С9`, `С10`, формат `.outcomes.tsv` `С11`).
   - `Platform/common/data/codec.tsv` — таблица кодека хранилища (`ADR-0088` п. 3, доп. (1) Р6).
   - `Platform/common/data/common.form.yaml` — общие определения типов и грамматик (`unit_id`, `slot_name`, `sub_name`, `server_name`, `box_id`, `instance_id`, `rid`, `sha256_hex`, `envelope_v2`, `x25519_v1` по `ADR-0088` п. 4 и доп. (2) С3, С7).
   - Вынос общего раздела «Стенд» и «Словарь директив и дверей» из `Source/tests/testdata/acceptance/М10_Platform/01/README.md:3-148` в `Platform/common/acceptance/README.md` (чтобы сценарии уроков 2–10 не ссылались внутрь удаляемого `М10_Platform/01/`).
2. **Нормы, OpenAPI, лекция, инструкция и жизненный цикл `Platform/01-store/`:**
   - `Platform/01-store/01-store.md` (лекция) и `Platform/01-store/spec/01-store.README.md`.
   - `Platform/01-store/spec/01-store.norms.md` (главы `1.1`, `1.2`, `1.3` + `Н0` с правилами модуля, абзацем `**Данные**` и встроенными байт-в-байт разделами форм семей `configstore-doors` и `epoch_floor`).
   - Единый `Platform/01-store/spec/01-store.api.openapi.yaml` — слияние `01-storage.api.openapi.yaml`, `06-rights.api.openapi.yaml` (`/v1/rights`) и `11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml` (`/v1/status`, `/v1/join`, `/v1/leave`, `/metrics`) с сохранением различия `HEAD`: `404` на `/v1/get`, `/v1/list`, `/v1/write`, `/v1/rights` vs `405` на `/v1/status`, `/v1/join`, `/v1/leave`, `/metrics`.
   - Обновлённый `Platform/01-store/lifecycle.md` (перевод ссылок с `М10/*` на `P/01.1`–`P/01.3`, исправление умолчания `SERVER_NAME` и ссылки на вектор копии).
3. **Схемы семей данных `Platform/01-store/data/` (`ADR-0088` п. 8 и доп. (2)):**
   - `configstore-doors.form.yaml` + `configstore-doors.outcomes.tsv` (`platform/configstore-doors/<id>`).
   - `epoch_floor.form.yaml` + `epoch_floor.outcomes.tsv` (`platform/epoch_floor`, с переводом `owner` в `catalog.tsv:25` на `P/01`).
4. **Векторы и приёмка `Platform/01-store/`:**
   - `Platform/01-store/vectors/jcs/canonical_json.tsv` (перенос из `Source/tests/testdata/canonical_json.tsv`).
   - `Platform/01-store/vectors/rights-evaluator/` (уже на месте; добавить способ вызова в стенд).
   - `Platform/01-store/vectors/backup-copy/` (перенос `Source/tests/testdata/acceptance/М10_Platform/11/inputs/*.jsonl` с таблицей ожиданий `cases.tsv`).
   - `Platform/01-store/acceptance/` — 27 сценариев из `Source/tests/testdata/acceptance/М10_Platform/01/scenarios.tsv` + сценарии хранилища из `М10/11` (`04-store-metrics`, `08-floor-replay`, `10-foreign-dir`, `11-copy`, `12-copy-refused`, `14-copy-ids`, шаги 1–8 `15-service-doors`).
5. **Удаление старого урока 1 и обновление ссылок:**
   - Удаление `М10_Platform/01-storage.md`, `М10_Platform/spec/01-storage.{norms.md,README.md,api.openapi.yaml}`, `06-rights.api.openapi.yaml`, `11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml` и `Source/tests/testdata/acceptance/М10_Platform/01/`.
   - Замена перенесённых разделов в `М10/6` и `М10/11` ссылками на `Platform/01-store/spec/01-store.norms.md`; обновление `catalog.tsv`, `id-map.tsv` (включая строки сценариев и векторов) и `check_spec.py`.

#### Коммит переноса урока 2 (`P/02 02-installer`)
1. **Источник формы спеки и построитель (`ADR-0087` с доп. (1)–(5), `ADR-0089` с доп. (1)):**
   - `Platform/02-installer/spec/spec.form.yaml` (с закрытыми 17 вопросами и `В1–В3` из `2026-10-19-диалект-по-журналам.md`, машинными `default` по записке Р10 и `ordered: true` на `unit.fields` и `tables.<т>.fields`), `references.tsv`, `scalars.tsv`.
   - Построенная из `spec.form.yaml` схема канонического дерева `spec` (`ADR-0089` доп. (1) Р11) и построитель разделов норм / проверщиков в `skills/lesson-spec/scripts/`.
   - Удаление старых файлов `ADR-0085`: `М10_Platform/spec/02-the-spec-and-the-strict-loader.{schema.yaml,references.tsv}` и `skills/lesson-spec/scripts/spec_schema/`.
2. **Нормы, лекция, инструкция и жизненный цикл `Platform/02-installer/`:**
   - `Platform/02-installer/02-installer.md`, `Platform/02-installer/spec/02-installer.README.md`, `Platform/02-installer/README.md` (без несуществующего `02-installer.api.openapi.yaml`).
   - `Platform/02-installer/spec/02-installer.norms.md` — главы `2.1` (форма спеки и загрузчик, со встроенным построенным разделом), `2.2` (5 правил чистой проекции канонического вида по `ADR-0089` доп. (1) Р3, Р11 — **без** записи канонической строки в хранилище в этом коммите!), `2.3` (строка `platform/spec/<sub>`, `/rev`, `spec-put` и сторона читателя), `2.4` (установка, юниты, `.env`, правило адреса, `w2c-ca.sh`, `w2c-workers.sh`, `w2cctl`), `2.5` (вывод файла прав и `--check`) и выделенные главы позднего слоя («вводит урок 8»: `domain.*` в `2.1`, установка и юниты домена в `2.4`, роли и ключи домена в `2.5`).
   - **Сохранение старых имён `spec` до конца стадии B (`ADR-0086` доп. (1) Р1)** и наличие таблицы `Platform/common/manifest-rename.tsv` (`Р2`).
3. **Схемы семей данных `Platform/02-installer/data/` (`ADR-0088` п. 8):**
   - `spec.form.yaml` + `spec.outcomes.tsv` (`platform/spec/<sub>`) и `spec-rev.form.yaml` + `spec-rev.outcomes.tsv` (`platform/spec/<sub>/rev`).
4. **Векторы и приёмка `Platform/02-installer/`:**
   - `vectors/loader/` — корпус `verdicts.tsv`, `classes.tsv`, `diagnostics.tsv`, `cases/` (с полным покрытием всех 111 строк `references.tsv` и исправленной сортировкой путей в `diagnostics.tsv:4`), единая таблица `Source/tests/testdata/spec_verdicts.tsv` снята.
   - `vectors/canonical/` — чистые векторы проекции `байты спеки → байты spec без обёртки` (`ADR-0089` доп. (1) Р13, Р14).
   - `vectors/workers-script/` (расширенный случаями памяти `rules 4`), `vectors/rights-from-spec/` (`06/variants/v1..v5`), `vectors/platform-lists/` (`platform_lists.tsv`).
   - `acceptance/` — `puts.tsv` и `puts/` (с поддержкой формата `puts.tsv` в `check_spec.py`).
5. **Безопасная передача `GET /spec` и `ConsoleRefusal`:**
   - Перенос Н2 `GET /spec` (`М10/2-15`) и `02-the-spec-and-the-strict-loader.api.openapi.yaml` (`SpecView`, `ConsoleRefusal`) во временное владение `М10/9` (`09-the-console`) до переноса урока 6 (`06-console`), чтобы удаление `М10/2` не оборвало `$ref` в OpenAPI уроков 9 и 10.
6. **Что НЕ входит в коммит переноса урока 2 (идёт отдельными коммитами после него):**
   - Запись установщиком строки `platform/spec/<sub>/canonical/<форма>`, её схема `.form.yaml`, строка в `catalog.tsv`, отказ `toolarge` на канонической строке и граничные сценарии `puts.tsv` — **отдельный коммит смены поведения сразу после переноса урока 2** (`ADR-0089` доп. (1) Р11).
   - Переименование `spec` → `manifest` — **последний коммит стадии B после переноса всех уроков 1–10** (`ADR-0086` доп. (1) Р1).

---

## 2. Урок 1 (`P/01 01-store`) и оценка `ADR-0088` доп. (2) (`e455a12d3`)

### 2.1. Оценка `ADR-0088` доп. (2) на срезе `e455a12d3`

На срезе `e455a12d3` (`decisions/0088-схемы-семей-данных-источник-в-диалекте.md:154-168`) владелец принял решение по описи `decisions/inbox/2026-10-19-опись-ограничений-семей.md`:
- **ввести 7 слов:** `type: time` (`С1`), `encoding: json` (`С2`), `ref: common.<имя>` (`С3`), `max_items` (`С5`), `max_bytes` (`С6`), пометку целого знака у читателя (`С9`), поддерево ограничений писателя `writer: {…}` (`С10`);
- **расширить 2 слова:** `encoding: jcs` как проверку писателя (`С4`), шестнадцатеричный знак `\x{HHHH}` в классах `pattern` (`С7`);
- **вынести исходы в файл рядом со схемой:** `NN-<процесс>/data/<семья>.outcomes.tsv` (`С11`);
- **не вводить 7 слов:** `\p{Nd}` (`С8`), `unique_by` (`С12`), `names_by` (`С13`), `sealed` (`С14`), `json_schema` (`С15`), `from_spec` (`С16`), `cat`/`parts`/`num` (`С17`).

**1. Хватает ли принятых слов семьям уроков 1–2 и `common.form.yaml`?**
- **Для семей урока 1 (`01-store`):**
  - `platform/configstore-doors/<id>` (`М10/11 Н1.3 door`): ключ проверяется через `pattern` (`^platform/configstore-doors/[a-z0-9]+(-[a-z0-9]+)*$` или `ref: common.server_name`), поля `{api, at}` — через `properties`, `required`, `type: string` и новое слово `type: time` (`С1`), исход при нечитаемой строке («пропустить при расчёте `configstore_doors`») — через `configstore-doors.outcomes.tsv` (`С11`). **Слов полностью хватает.**
  - `platform/epoch_floor` (`М10/11 Н1.3 floor`, `М10/3 Н1.5`): поля `{floor, generation_at}` полностью описываются через `type: integer`, `minimum: 1`, `maximum: 9007194959773696` ($2^{53}-2^{32}$), новое слово `С9` (признак целого знака у читателя `import` при отвержении `1.0`, `1e2`), `type: time` (`С1`, необязательное `generation_at`), `writer: {required: [floor, generation_at]}` (`С10` — демон при `op: floor` пишет оба поля, а читатели `import` и воркер требуют только `floor`) и `epoch_floor.outcomes.tsv` (`С11`: `op: floor` и `import` → отказ, воркер в `взять_эпоху` → ждать). **Слов полностью хватает.**
- **Для семей урока 2 (`02-installer`):**
  - `platform/spec/<sub>` и `platform/spec/<sub>/rev` (`М10/2 Н1.5`): полностью описываются существующими словами диалекта (`pattern`, `properties`, `required`, `type: string`, `type: integer`, `minimum: 1`, `references: row.name = split(@key "/" 2)` и `split(@key "/" 2) not in {…}`) и файлами `.outcomes.tsv` (`С11`).
  - Будущая семья `platform/spec/<sub>/canonical/<форма>` (`ADR-0089` доп. (1) Р1, Р8): полностью описывается через `properties` (`form`, `rev`, `sha256`, `spec`), `encoding: jcs` (`С4` на поле `spec` у писателя), `ref` на построенную схему канонического дерева спеки и `references` (`row.spec.name = split(@key "/" 2)`). **Слов полностью хватает.**

**2. Верны ли отказы от `С8` и `С12–С17`?**
- **Отказы от `С12` (`unique_by`), `С13` (`names_by`), `С14` (`sealed`), `С15` (`json_schema`), `С16` (`from_spec`), `С17` (`cat`/`parts`/`num`) — безусловно верны:**
  - `С12` и `С13` встречаются в 1–2 семьях на весь курс (`domain/members`, `domain/grants/<кластер>`) и выражаются в `.references.tsv` без раздувания словаря узлов `DIALECT.md`;
  - `С14` (`sealed`) и `С15` (`json_schema`) — рантайм-проверки с внешними входами (файл кольца `platform.key` с AAD и спека подсистемы из хранилища), которые статическая схема строки заменить не может;
  - отказ от `С16` (`from_spec`) в пользу закрытого перечня правил порождения в нормах урока-владельца оболочки (`03-worker`, `06-console`, `08-domain`), исполняемого построителем над каноническим манифестом `ADR-0089`, архитектурно гораздо чище и не смешивает статический диалект с параметризацией по манифесту;
  - `С17` (`cat`/`parts`/`num`) не нужен в языке отношений: проверка целочисленного суффикса `<n>` в `<prefix>-<server>-<n>` статически закрывается регулярным выражением в `common.slot_name`, а зависимость от `slot.prefix` спеки относится к шагу порождения по манифесту (`С16`).
- **Оговорка по отказу от `С8` (`\p{Nd}`) в пользу `С7` (`\x{HHHH}`) — см. находку № 4 ниже:** сам отказ от введения Unicode-свойств в регулярные выражения диалекта оправдан (разные движки regexp в Python `re` и Go `regexp` трактуют `\p{…}` по-разному), но для записи `common.unit_id` через явные диапазоны `\x{HHHH}` в `common.form.yaml` при переносе урока 1 необходимо закрепить версию Unicode (`15.0.0`) в норме `unit.id`.

---

### 2.2. Находки по уроку 1 (`P/01 01-store`)

#### № 1. [Блокер | до переноса урока 1] Конфликт владения семьёй `platform/epoch_floor` между `catalog.tsv`, `id-map.tsv` и `01-store/lifecycle.md`
- **Где:** `Platform/common/data/catalog.tsv:25`, `Platform/common/id-map.tsv:189`, `Platform/01-store/lifecycle.md:56`.
- **Цитата:**
  - `Platform/common/data/catalog.tsv:25`:
    `platform/epoch_floor	row	М10/3	put=admin(op floor через admin.sock, только вверх; import до первой строки)	console, <s>controller, <s>worker, domain, domainagent	-	1	-	М10/3 Н1.5, М10/11 Н1.3`
  - `Platform/common/id-map.tsv:189`:
    `М10/11-06	P/01.3-03	1.3	пол эпох	3.2 — чтение пола`
  - `Platform/01-store/lifecycle.md:56`:
    `| Строки двери и пола | platform/configstore-doors/<id>, platform/epoch_floor | М10/11 Н1.3 |`
- **Контрпример:** При переносе урока 1 (`01-store`) глава `1.3` обязана содержать полную форму строки `platform/epoch_floor` (`{floor, generation_at}`, предел `2^53 − 2^32`, проверку при `op: floor` и `import`), а по `ADR-0088` п. 8 — схему `Platform/01-store/data/epoch_floor.form.yaml`. Но в `catalog.tsv:25` владельцем (`owner`) записан `М10/3` (который при переносе по `id-map.tsv` переводится в `P/03 03-worker`, причём `М10/3 Н1.5` даже не знает про поле `generation_at`). Кроме того, в `readers` `catalog.tsv:25` записаны `console, <s>controller, domain, domainagent`, которые `platform/epoch_floor` по нормам никогда не читают (аналогично в `catalog.tsv:56` у `platform/configstore-doors/<id>` в `readers` записаны `console, <s>controller, domain, domainagent, admin`, хотя по `М10/11 Н1.3 door` эту семью читает только лидер `configstore` для метрики `configstore_doors`).
- **Нарушено:** `ADR-0083` доп. (5) (`decisions/0083-микромодули-платформы.md:242-246`), `ADR-0083` доп. (6) (`:264-266`), `ADR-0088` п. 8 (`decisions/0088-схемы-семей-данных-источник-в-диалекте.md:61`).
- **Следствие:** `check_spec` при переносе урока 1 не позволит `01-store` владеть `platform/epoch_floor`, либо урок 1 получит ссылку вперёд на урок 3. В `catalog.tsv:25` нужно сменить `owner` на `М10/11` (переходит в `P/01`), а в `readers` строк `25` и `56` оставить только реальных читателей по нормам.

---

#### № 2. [Блокер | до переноса урока 1] В `catalog.tsv` пропущен файл `/etc/w2c/configstore-rights.json`, а в `01-storage.norms.md` нет абзаца `**Данные**`
- **Где:** `Platform/common/data/catalog.tsv`, `М10_Platform/spec/01-storage.norms.md:12-16`, `Platform/01-store/lifecycle.md:52`, `Platform/02-installer/lifecycle.md:54`.
- **Цитата:**
  - `Platform/01-store/lifecycle.md:52`: `| -rights | /etc/w2c/configstore-rights.json | Файл прав главы 1.2 (пишет установщик 02-installer) |`
  - `Platform/02-installer/lifecycle.md:54`: `| /etc/w2c/configstore-rights.json | Файл прав хранилища (читает 01-store) |`
- **Контрпример:** В `Platform/common/data/catalog.tsv` внесены `/etc/w2c/secrets/platform.key` (`:29`) и `/etc/w2c/tls/*` (`:57-62`), но файл `/etc/w2c/configstore-rights.json` (`kind=file`, пишет `proc:02-installer`, читают `proc:01-store, proc:02-installer`) отсутствует. Одновременно в `М10_Platform/spec/01-storage.norms.md` нет абзаца `**Данные**` (при переносе в `01-store.norms.md` он обязан перечислить `владеет: platform/configstore-doors/<id>, platform/epoch_floor` и читаемые файлы `/etc/w2c/configstore-rights.json`, `/etc/w2c/tls/*`). Также в `catalog.tsv` пропущены межпроцессные файлы `/etc/w2c/roles/<роль>.env` (пишет `02-installer`, читает `05-resource` для расчёта `room.<sub>` по `М10/8 Н1.4` и `w2c-workers.sh` по `М10/11 Н1.5`) и `recovery_file` (`М11/2 Н1.1, Н3`, пишет `02-installer` при установке домена, читает `08-domain` при смене ключей).
- **Нарушено:** `ADR-0083` доп. (3), (5), (6) (`decisions/0083-микромодули-платформы.md:186-188,244-246,275`), `Platform/module-design.md:45,166`.
- **Следствие:** Межпроцессный файловый контракт между `02-installer` и `01-store` (а также `05-resource` и `08-domain`) выпадает из каталога данных и абзацев `**Данные**`.

---

#### № 3. [Блокер | до переноса урока 1] Разрыв самодостаточности `01-store` (`ADR-0083` доп. (5)): проверка сертификатов, ролей в SAN и отзыва приписана в `id-map.tsv` только уроку 2 (`2.4`)
- **Где:** `Platform/common/id-map.tsv:126,194`, `М10_Platform/spec/06-rights.norms.md:38-45`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:155,166,342-366`.
- **Цитата:**
  - `Platform/common/id-map.tsv:126`: `М10/6-12	P/02.4-02	2.4	сертификат роли и роль процесса	-`
  - `Platform/common/id-map.tsv:194`: `М10/11-11	P/02.4-07	2.4	сертификаты и отзыв	-`
- **Контрпример:** Демон `configstore` (`01-store`, глава `1.3`) сам принимает и устанавливает TLS-соединения на `-raft` и `-api`, проверяет по `М10/11 Н1.3 identity, door` и `Н1.6 cert, sig, revoke, rotation`:
  1) `CN <роль>.<server>`, `SAN DNS <server>`, ровно один `SAN URI urn:w2c:role:<роль>`;
  2) различение ролей `configstore` (голосующий член) и `configstore-door` (дверь без голоса — `403` на `/v1/join`, `/v1/leave`, голосование Raft);
  3) закрытый список алгоритмов подписи цепочки (`ECDSA P-256/P-384`, `RSA ≥ 2048 PKCS#1 v1.5/PSS`, `Ed25519` — `Н1.6 sig`);
  4) доверие `ca.pem` и `ca.next.pem`, перечитывание `revoked` / `crl.pem` по содержимому без перезапуска и немедленный разрыв соединений отозванного сертификата.
  Если `М10/6-12` и `М10/11-11` переедут только в `2.4` (`02-installer`, `note = -`), генератор `01-store` в стадии C не узнает правил проверки сертификатов и отзыва, либо `01-store` будет ссылаться вперёд на урок 2.
- **Нарушено:** `ADR-0083` доп. (5) (`decisions/0083-микромодули-платформы.md:242-246`), `Platform/module-design.md:74`.
- **Следствие:** В `id-map.tsv:126,194` необходимо добавить деление в `note: 1.3 — проверка сертификата, алгоритмов подписи, ролей configstore/configstore-door и отзыва демоном`, а при переносе урока 1 включить сторону проверяющего TLS-пира в главу `1.3`.

---

#### № 4. [Блокер | в коммит переноса урока 1] В `ADR-0088` доп. (2) для `common.form.yaml` и `DIALECT.md` не закреплены: (а) версия Unicode для диапазонов `Nd` в `common.unit_id`, (б) имя слова `С9` и шапка `.outcomes.tsv` (`С11`)
- **Где:** `decisions/0088-схемы-семей-данных-источник-в-диалекте.md:158-167` (срез `e455a12d3`), `decisions/inbox/2026-10-19-опись-ограничений-семей.md:39,49,63`, `М10_Platform/spec/03-units-slots-epochs-lease.norms.md:83`.
- **Цитата:**
  - `decisions/0088-схемы-семей-данных-источник-в-диалекте.md:160,165` (`e455a12d3`):
    `пометку целого знака у читателя (С9; имя слова — при переносе урока 1)… не вводить в диалект семь слов из описи: \p{Nd} в pattern (С8 — покрывается диапазонами \x{HHHH} в common.form.yaml)`
  - `М10_Platform/spec/03-units-slots-epochs-lease.norms.md:83`:
    `запрещены пробел, управляющие символы категории Cc, разделители строк U+2028/U+2029, цифры Unicode категории Nd вне ASCII 0–9`
- **Контрпример:** По `ADR-0088` п. 8 файл `Platform/common/data/common.form.yaml` (включающий `common.unit_id`) создаётся **при переносе урока 1**. В отличие от `Cc` (`\x{0000}-\x{001F}\x{007F}-\x{009F}`) и `Zl`/`Zp` (`\x{2028}\x{2029}`), набор диапазонов десятичных цифр категории `Nd` вне ASCII зависит от версии стандарта Unicode (~65 блоков, включая астральные `U+104A0..U+1D7FF`). В `М10/7 Н1.1а А4` (`07-secrets-and-sealing.norms.md:90`) версия `Unicode 15.0.0` названа явно, а в `М10/3 Н1.3` — не названа. Кроме того, в `2026-10-19-опись-ограничений-семей.md:39,49` оставлены на перенос урока 1 выбор имени ключевого слова `С9` (`whole: reader` или `integer_sign: reader`) и точные имена столбцов таблицы `<семья>.outcomes.tsv` (`С11`).
- **Нарушено:** `ADR-0088` п. 4, 8 и доп. (2).
- **Следствие:** В коммите переноса урока 1 нужно: (1) в `Platform/common/DIALECT.md` зафиксировать точное имя слова `С9` и схему столбцов `.outcomes.tsv` (`С11`); (2) в `common.form.yaml` (и `М10/3 Н1.3`) явно указать `Unicode 15.0.0` для закрытого перечня диапазонов `\x{HHHH}` категории `Nd` вне ASCII.

---

#### № 5. [Существенная | в коммит переноса урока 1] Ошибка умолчания `SERVER_NAME` и отсутствие пакетов векторов `JCS` и `копия хранилища` в `Platform/01-store/`
- **Где:** `Platform/01-store/lifecycle.md:32,54`, `Platform/common/vectors/README.md:13,24`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:106,158,437`.
- **Цитата:**
  - `Platform/01-store/lifecycle.md:32`:
    `| SERVER_NAME | Умолчание -id вне группы; грамматика ^[a-z0-9]+(-[a-z0-9]+)*$ | — | М10/11 Н1.2, Н1.3 |`
  - `Platform/01-store/lifecycle.md:54`:
    `| Копия хранилища | файл backup / import / restore | Первая строка {"format": "w2c-configstore-copy", "version": 1}, дальше строки по байтам key; векторы — Platform/common/vectors/README.md |`
- **Контрпример:**
  1) По `М10/11 Н1.2` (`11-the-platform-on-a-box-and-a-cluster.norms.md:106`) у `SERVER_NAME` умолчание — **короткий hostname (`%l`)**, а не `—` (иначе `configstore` вне группы без `-id` и без явного `SERVER_NAME` не сможет вычислить свой `-id` по `Н1.3:158`).
  2) В `Platform/01-store/vectors/` сейчас лежит только `rights-evaluator/`; ни `canonical_json.tsv` (`JCS`), ни вектор `копия хранилища` (`11/inputs/*.jsonl` — 15 файлов в `Source/tests/testdata/acceptance/М10_Platform/11/inputs/`) туда ещё не перенесены, причём `01-store/lifecycle.md:54` ссылается на указатель `Platform/common/vectors/README.md`, а `vectors/README.md:24` — обратно на `приёмка М10/11 (сц. 11, 12, 14)`.
  3) При слиянии трёх OpenAPI-файлов в `01-store.api.openapi.yaml` важно сохранить различие `HEAD` из `М10/1 Н2.1` (`01-storage.norms.md:155`) и `М10/11 Н2` (`11-the-platform-on-a-box-and-a-cluster.norms.md:437`, сц. `15-service-doors` шаги 7–8): `HEAD` к `/v1/get`, `/v1/list`, `/v1/write`, `/v1/rights` возвращает **`404`**, а `HEAD` к `/v1/status`, `/v1/join`, `/v1/leave`, `/metrics` — **`405`**.
- **Нарушено:** `М10/11 Н1.2`, `ADR-0083` доп. (2) п. 3 (`decisions/0083-микромодули-платформы.md:161-163`), `Platform/module-design.md:31,133,146`.
- **Следствие:** Исправить умолчание `SERVER_NAME` в `01-store/lifecycle.md:32` и упаковать оба вектора (`jcs/` и `backup-copy/`) и объединённый `01-store.api.openapi.yaml` в коммите переноса урока 1.

---

## 3. Урок 2 (`P/02 02-installer`)

### 3.1. Находки по условиям переноса урока 2 (`ADR-0087`, `ADR-0089`, `ADR-0086`)

#### № 6. [Блокер | до переноса урока 2] Не закрыты входные условия `ADR-0087` с доп. (1)–(5) и `2026-10-19-диалект-по-журналам.md`
- **Где:** `decisions/0087-форма-спеки-источник-в-диалекте.md:79-85,152-240`, `decisions/inbox/2026-10-19-диалект-по-журналам.md:134-151`, `Source/tests/testdata/acceptance/М10_Platform/02/diagnostics.tsv:4`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md:106`.
- **Цитата:**
  - `decisions/inbox/2026-10-19-диалект-по-журналам.md:135-140`:
    `- **решение** (развилка с вариантами и рекомендацией, ждёт слова владельца) — **17**: слой текста — Т15, Т16, Т28 (3); слой формы — Ф1, Ф2, Ф9, Ф12, Ф15, Ф18, Ф23 (7); слой отношений — О3, О6, О7, О9, О12, О14, О15 (7).`
  - `Source/tests/testdata/acceptance/М10_Platform/02/diagnostics.tsv:4`:
    `unknown_multiple	[["unknown_top"],["placement","capcity"],["unit","fields","name","requried"]]	[6,11,37]`
- **Контрпример:**
  1) В `2026-10-19-диалект-по-журналам.md` 17 вопросов имеют статус `Решение: открыто`, а 3 уже принятых решения владельца (`В1–В3` в строках 142–151: `Ф22`, `О16`, `О10`) ещё не внесены в нормы, `references.tsv` и корпус.
  2) По `ADR-0087` (`:80`) и доп. (1) Р10 каждая из 111 строк `references.tsv` обязана иметь в корпусе положительный и отрицательный случай, где все прочие проверки чисты (сейчас непокрыты 38 строк).
  3) В `Source/tests/testdata/acceptance/М10_Platform/02/diagnostics.tsv:4` пути `[["unknown_top"],["placement","capcity"],["unit","fields","name","requried"]]` записаны в порядке строк файла (`[6,11,37]`), а не в лексикографическом порядке байтов UTF-8 канонического JSON Pointer `/placement/capcity`, `/unit/fields/name/requried`, `/unknown_top` (`'p' < 'u'` и `'n' < 'u'`), которого требует `ADR-0087` доп. (3) Р4 (`:227`)! (Хотя `02/README.md:64` сравнивает `paths` как множество, сама эталонная запись в `diagnostics.tsv:4` нарушает канонический порядок).
  4) В `02-the-spec-and-the-strict-loader.README.md:106` устарел счёт корпуса: написано `Все 379 файлов дают вердикт из таблицы: 69 ok, 310 refused` вместо `479 файлов: 93 ok, 386 refused` (`02-the-spec-and-the-strict-loader.norms.md:581`), а в `02/README.md:102` для `classes.tsv` написано `всего 64 строки` вместо фактических **70 случаев** (после добавления `c6_*` и `c7_*`).
- **Нарушено:** `ADR-0087` п. «Подтверждение» (`:79-85`), доп. (1) Р2–Р6, Р10, доп. (3) Р1–Р5, доп. (5).
- **Следствие:** До переноса урока 2 необходимо закрыть 17 решений `2026-10-19-диалект-по-журналам.md`, внести `В1–В3` и правки доп. (1)–(5), довести покрытие `references.tsv` в корпусе до 100% и синхронизировать счётчики корпуса в `README.md`.

---

#### № 7. [Блокер | до переноса урока 2] Противоречие `Platform/module-design.md:52` с `ADR-0089` доп. (1) Р10–Р11 по времени введения записи `platform/spec/<sub>/canonical/<форма>`
- **Где:** `Platform/module-design.md:52`, `decisions/0089-канонический-вид-спеки-проекция-источника-формы.md:56,101-108`, `ХОД-Спецификация.md:58`.
- **Цитата:**
  - `Platform/module-design.md:52`:
    `2.2 канонический вид спеки (форма решается до урока 2; установщик пишет его с переноса урока 2, читатели переходят отдельной правкой; потолок строки спеки назвать)`
  - `decisions/0089-канонический-вид-спеки-проекция-источника-формы.md:107-108` (доп. (1) Р11):
    `Запись канонического вида — отдельная правка поведения после переноса урока 2 с граничной приёмкой (меняет область принимаемых спек), а не часть переноса; п. 7 читать так.`
- **Контрпример:** `Platform/module-design.md:52` требует, чтобы установщик писал канонический вид уже в коммите переноса урока 2, тогда как `ADR-0089` доп. (1) Р11 прямо вынес запись строки `platform/spec/<sub>/canonical/<форма>` (и отказ `toolarge` на ней) в **отдельную правку поведения после переноса урока 2**, оставив в самом коммите переноса урока 2 только `ordered: true` и машинные `default` в `spec.form.yaml`, 5 правил чистой проекции в главе `2.2`, построенную схему канонического дерева `spec` и чистые векторы проекции `vectors/canonical/`. При этом нормативная записка со сквозной описью умолчаний спеки, обязательная по `ADR-0089` доп. (1) Р10 **до переноса урока 2**, ещё не написана (`ХОД-Спецификация.md:58`).
- **Нарушено:** `ADR-0089` доп. (1) Р10, Р11 (`decisions/0089-канонический-вид-спеки-проекция-источника-формы.md:101-108`).
- **Следствие:** До переноса урока 2 выпустить записку умолчаний по Р10 и привести `Platform/module-design.md:52` в соответствие с `ADR-0089` доп. (1) Р1, Р2, Р11.

---

#### № 8. [Блокер | до переноса урока 2] Не создана таблица переименования `Platform/common/manifest-rename.tsv` (`ADR-0086` доп. (1) Р2) и смешаны имена до/после перехода в `module-design.md:52`
- **Где:** `decisions/0086-манифест-подсистемы.md:97`, `Platform/module-design.md:52`, `ХОД-Спецификация.md:58`.
- **Цитата:**
  - `decisions/0086-манифест-подсистемы.md:97` (доп. (1) Р2):
    `Полная механическая таблица замен в Platform/common/manifest-rename.tsv (старое → новое → владелец → потребители); по ней — замена и проверка check_spec.`
- **Контрпример:** Файл `Platform/common/manifest-rename.tsv` в репозитории отсутствует. Кроме того, в `Platform/module-design.md:52` смешаны имена до и после перехода (`2.1 текст манифеста`, `2.3 строка platform/manifest/<sub> (до перехода — platform/spec/<sub>)`), хотя по `ADR-0086` доп. (1) Р1 перенос всех уроков 1→10 идёт целиком на старых именах (`spec`, `platform/spec/<sub>`, `w2cctl spec`, `SPEC_DIR`, `spec_rev`), а переименование делается **единым последним коммитом стадии B**.
- **Нарушено:** `ADR-0086` доп. (1) Р1, Р2 (`decisions/0086-манифест-подсистемы.md:96-97`).
- **Следствие:** Создать `Platform/common/manifest-rename.tsv` до переноса урока 2, а в коммите переноса урока 2 строго сохранить старые имена `spec`.

---

### 3.2. Находки по самодостаточности `02-installer`, каталогу данных, `id-map.tsv` и векторам

#### № 9. [Блокер | в коммит переноса урока 2] Судьба `GET /spec` (`SpecView`) и `ConsoleRefusal` при удалении `М10/2` и ложный `02-installer.api.openapi.yaml`
- **Где:** `Platform/02-installer/README.md:10`, `Platform/module-design.md:52,179`, `Platform/common/id-map.tsv:46`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml`, `М10_Platform/spec/09-the-console.api.openapi.yaml`, `10-schema-drain-snapshot-limits.api.openapi.yaml`.
- **Цитата:**
  - `Platform/02-installer/README.md:10`: `spec/02-installer.api.openapi.yaml   двери`
  - `Platform/common/id-map.tsv:46`: `М10/2-15	P/06.5-01	6.5	GET /spec — форма SpecView	2.1 — грамматика полей`
  - `Platform/module-design.md:52`: `глава позднего слоя «вводит урок 8»: domain.* и отказы загрузки (m51_*, m57_*, m59_*, m61_*), проекция domain в GET /spec`
- **Контрпример:**
  1) У микромодуля `02-installer` нет собственных HTTP-дверей — строка `spec/02-installer.api.openapi.yaml двери` в `Platform/02-installer/README.md:10` и упоминание «проекция `domain` в `GET /spec`» в главе `2.1` `Platform/module-design.md:52` ошибочны (`GET /spec` и его доменная проекция `SpecDomainView` принадлежат `06-console`, глава `6.5` / `6.7`).
  2) По `Platform/module-design.md:179` перенос урока 2 удаляет `М10_Platform/spec/02-the-spec-and-the-strict-loader.*` в том же коммите. Но урок 2 переносится на шаге 2 стадии B, а урок 6 (`06-console`) — только на шаге 6! Если удалить `02-the-spec-and-the-strict-loader.norms.md` и `02-the-spec-and-the-strict-loader.api.openapi.yaml` при переносе урока 2, то до переноса урока 6 исчезнет норма `GET /spec` (`М10/2` Н2, `:447-468`, чеклист `М10/2-15`) и оборвутся ссылки `$ref: '02-the-spec-and-the-strict-loader.api.openapi.yaml#/components/schemas/ConsoleRefusal'` в `09-the-console.api.openapi.yaml` и `10-schema-drain-snapshot-limits.api.openapi.yaml`.
- **Нарушено:** `Platform/module-design.md:31,56,179-180`.
- **Следствие:** Убрать `02-installer.api.openapi.yaml` из `Platform/02-installer/README.md:10` и «проекцию `domain` в `GET /spec`» из `2.1` в `module-design.md:52`; в коммите переноса урока 2 временно перенести Н2 `GET /spec` (`М10/2-15`) и схемы `SpecView` / `ConsoleRefusal` в `09-the-console.{norms.md,api.openapi.yaml}` до переноса урока 6.

---

#### № 10. [Блокер | до переноса урока 2] Разрывы самодостаточности `02-installer` (`ADR-0083` доп. (5)): `unit_mb`/`base_mb` в `w2c-workers.sh`, зависимость `2.5` от позднего слоя домена и рассогласование `w2cctl secrets`
- **Где:** `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:325-329`, `Platform/02-installer/lifecycle.md:20,69`, `Platform/common/id-map.tsv:121,122,127,131,137,139`, `Platform/module-design.md:52,85,89`, `Platform/common/data/catalog.tsv:18,29,55,67-69,71,83-85,98,104`.
- **Цитата:**
  - `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:325-328` (`Н1.5 rules 4`):
    `4. перед запуском — память: потолок = floor(HOST_MEMORY_MB / WORKER_MEMORY_MB) из roles/<роль>.env (разбор, не source; нет файла — роль пропуск); оба бюджета — положительные целые, CAPACITY/unit_mb/base_mb — конечные допустимые числа (CAPACITY целое >0, unit_mb >0, base_mb ≥0); ошибка/NaN/бесконечность/ноль делителя → роль пропустить с диагностикой`
  - `Platform/02-installer/lifecycle.md:69`:
    `нет roles/<роль>.env или значения памяти/ёмкости в нём не читаются (положительные целые бюджеты, конечные CAPACITY/unit_mb/base_mb, делитель > 0)`
- **Контрпример:**
  1) **Фантомные `unit_mb` и `base_mb` в `w2c-workers.sh` (`2.4`):** По `М10/11 Н1.2` (`:122`) в файле `roles/<роль>.env` живут только переменные `CAPACITY`, `WORKER_MEMORY_MB`, `HOST_MEMORY_MB`. Параметры `unit_mb` и `base_mb` — это аргументы вызова SDK воркера (`М10/5 Н1.2`, `:108-110`: `CAPACITY × unit_mb + base_mb ≤ WORKER_MEMORY_MB`), которые скрипт сервера `w2c-workers.sh` не знает и из `roles/<роль>.env` прочитать не может! Кроме того, в `Platform/02-installer/vectors/workers-script/{README.md,cases.tsv}` проверка памяти (`rules 4`) вообще исключена из векторов (`README.md:17`: «Не покрыто: память (rules 4 — потолок по `roles/<роль>.env`)»), хотя потолок `floor(HOST_MEMORY_MB / WORKER_MEMORY_MB)` — чистая детерминированная функция от `env`.
  2) **Зависимость главы `2.5` (шаг чтения 11) от позднего слоя домена (шаг чтения 15):** В `Platform/module-design.md:85,89` глава `2.5` («вывод прав») читается на шаге 11 (до уроков 8–10 на шагах 12–14 и позднего слоя на шаге 15). Но в `id-map.tsv:127` норма `М10/6-13` (`P/02.5-03`, «вывод прав по смыслу, роли домена») имеет `note = -` (не помечена как поздний слой!), а таблица `М10/6 Н1.4`, `platform_lists.tsv` и варианты `06/variants/v4-domain-kept`, `v5-secret-domainworker` требуют знания ключей `domain.kept`, `domain.books`, `domain.shared`, `domain.tokens` и ролей `domain`, `domainconsole`, `domainagent`, `<sub>domain`, `domainworker`. Доменная часть вывода прав (`P/02.5-03`, `v4`, `v5`, сц. 12 `М10/06`) должна быть явно выделена в поздний слой `2.5` («вводит урок 8»).
  3) **Рассогласование принадлежности `w2cctl secrets` и пропуски `admin(w2cctl secrets seal)` в `catalog.tsv`:** В `catalog.tsv:29` писателем `/etc/w2c/secrets/platform.key` указан `proc:02-installer(w2cctl secrets new/rotate)`, но в `id-map.tsv:131,139` нормы `М10/7-04` и `М10/7-12` (`команды w2cctl secrets`) отданы в **`6.2` (`06-console`)** (`note: 2.4 — команды оператора`), а в `Platform/02-installer/lifecycle.md:20` подкоманда `secrets` в перечне `w2cctl` пропущена! Одновременно в `catalog.tsv` участник `admin(w2cctl secrets seal)` записан у `<sub>/<spec:unit.rows>/<id>` (`:20`), но пропущен у `<sub>/<spec:tables>/<имя>` (`:55`), `door/signer` (`:50`) и секретных строк `domain/*` (`:67-69,71,83-85,98,104`).
- **Нарушено:** `ADR-0083` доп. (5), (6), `Platform/module-design.md:70-89`.
- **Следствие:** (1) Убрать `unit_mb`/`base_mb` из `rules 4` `w2c-workers.sh` в `М10/11 Н1.5:326` и `02-installer/lifecycle.md:69` (оставив их только в `memory:` старта воркера `:336`) и добавить случаи памяти в `vectors/workers-script/cases.tsv`; (2) выделить доменные правила вывода прав в поздний слой `2.5`; (3) согласовать владельца `w2cctl secrets` между `id-map.tsv`, `02-installer/lifecycle.md` и `catalog.tsv` и дописать `admin(w2cctl secrets seal)` в `catalog.tsv`.

---

#### № 11. [Блокер | до переноса урока 2] Разошедшиеся дубликаты векторных таблиц `secret_in.tsv` и `log_mask.tsv` и устаревшая ссылка на `spec_verdicts.tsv`
- **Где:** `Source/tests/testdata/secret_in.tsv` (460 строк) vs `Source/tests/testdata/acceptance/М10_Platform/07/secret_in.tsv` (448 строк); `Source/tests/testdata/log_mask.tsv` (45 строк) vs `Source/tests/testdata/acceptance/М10_Platform/07/log_mask.tsv` (36 строк); `Platform/common/vectors/README.md:14,17,18`; `Platform/module-design.md:140,142,145`; `Platform/common/id-map.tsv:134`.
- **Цитата:**
  - `Platform/common/vectors/README.md:14`:
    `| корпус спеки | Source/tests/testdata/spec_verdicts.tsv + spec_verdicts/ | М10/2 (Н1, Н4, Н5); с переносом — 02-installer |`
- **Контрпример:**
  1) В репозитории лежат две разные копии `secret_in.tsv`: в `Source/tests/testdata/secret_in.tsv:458-460` есть 3 строки (`?usr=admin&pwd=`, `?pass%3Dhunter2xyz=1`, `/x%3A//admin%3Ahunter2xyz%40h/s`) и правка шапки по ревью стадии A-1, которых нет в `Source/tests/testdata/acceptance/М10_Platform/07/secret_in.tsv`; напротив, `fields.yaml` лежит только в `acceptance/М10_Platform/07/`.
  2) Аналогично разошлись `Source/tests/testdata/log_mask.tsv` (29 случаев) и `Source/tests/testdata/acceptance/М10_Platform/07/log_mask.tsv` (25 случаев — нет `Authorization: Bearer abc.def` и ещё 3 строк).
  3) По главе владельца `secret_in.tsv` три документа противоречат друг другу: `Platform/common/vectors/README.md:17` указывает `06-console`, `Platform/module-design.md:140` — `2.1, 6.2` (а в строке `:145` отдельно пишет `разбор адреса | 2.4`), `Platform/common/id-map.tsv:134` (`М10/7-07`) — `6.2` с `note: 2.1 — объявления credentials и secret_in в загрузчике; 2.4 — разбор адреса (вектор)`.
  4) В `Platform/common/vectors/README.md:14` указан старый `Source/tests/testdata/spec_verdicts.tsv` (138 случаев) вместо актуального корпуса `Source/tests/testdata/acceptance/М10_Platform/02/{verdicts,classes,diagnostics}.tsv` (479 случаев), а пакет векторов вывода прав `Source/tests/testdata/acceptance/М10_Platform/06/variants/` (`module-design.md:144`) в `vectors/README.md` пропущен.
- **Нарушено:** `ADR-0003` (один источник тестовых данных), `ADR-0083` доп. (2) п. 3.
- **Следствие:** Слить дубликаты `secret_in.tsv` и `log_mask.tsv` в один источник, убрать устаревший `Source/tests/testdata/spec_verdicts.tsv`, исправить `Platform/common/vectors/README.md` и согласовать главу для `secret_in.tsv` (`6.2` — разбор адреса, `2.1` — только проверка объявлений в спеке).

---

#### № 12. [Существенная | до переноса урока 2] Неполные пометки деления (`note`) в `Platform/common/id-map.tsv` и пропуски в абзацах `**Данные**` смежных уроков (`М10/2, 7, 11`, `М11/2, 12`)
- **Где:** `Platform/common/id-map.tsv:51,56,121,190,197,205,225,250`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:402,406,500`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:14-17`, `М11_Domain/spec/12-small-members-and-one-node.norms.md:15-18`.
- **Цитата:**
  - `Platform/common/id-map.tsv:56`: `М10/2-25	P/02.1-21	2.1	обычная подстановка — только строка, :int — явный	-`
  - `М11_Domain/spec/12-small-members-and-one-node.norms.md:17`: `- читает: domain/member-key, domain/reached, domain/grants.`
- **Контрпример:**
  1) В `id-map.tsv` пропущены пометки деления (`note`) для:
     - `М10/2-25` (`:56`, `note = -`): вторая половина нормы задаёт рантайм-форматирование `:int` и отказ `400` на дверях (`6.1`, `6.4`, `3.6`);
     - `М10/2-20` (`:51`, `note = -`): правило исключения `server`/`secret`/`blob` из снимка по умолчанию исполняет контроллер (`4`) либо материализует канонический вид (`2.2`);
     - `М10/11-07` (`:190`, `note = -`): объединяет `import` хранилища (`1.3`) и `restore` бакетов событий ресурсом (`5`);
     - `М10/6-07` (`:121`): в `note` указан `1.2 — GET /v1/rights`, хотя маршрут `/v1/rights` относится к `М10/6-09` (`:123`);
     - `М11/1-04` (`:205`, `domain.view`), `М11/3-04` (`:225`, `domain.reports`), `М11/5-09` (`:250`, `domain.kept` и `domain.tables`): в `note` не указан `2.1 поздний слой` (и `2.5 поздний слой` для `domain.kept`).
  2) В `М10/2 Н1.5` (`02-the-spec-and-the-strict-loader.norms.md:402,406`) и `Н3` (`:500`) до записи `spec.form.yaml` и `spec-rev.form.yaml` нужно закрыть три нормативных умолчания из описи семей (`2026-10-19-опись-ограничений-семей.md`, A1 строки 7, 11, 15): строчный hex `[0-9a-f]{64}` у `sha256`, закрытость набора полей `{yaml, sha256, rev, shell}` и `{rev, sha256}` и исход `spec put` при нечитаемой существующей строке/метке в хранилище.
  3) В абзаце `**Данные**` `М11/12` (`12-small-members-and-one-node.norms.md:15-18`) семьи `domain/reached` и `domain/grants` ошибочно стоят в `читает:` вместо `пишет: ... (put)` (`М11/12 Н1.2`), а записи/чтения `domain/members`, `domain/members/<член>/reported`, `domain/signer`, `domain/view`, `domain/alarm-history/<член>` из `Н1.4–Н1.7` пропущены; в `**Данные**` `М10/11` (`11-the-platform-on-a-box-and-a-cluster.norms.md:14-17`) пропущены записи `w2cctl` (`platform/mirror`, `platform/space`, `<sub>/retention`, `<sub>/alarms_retention`) и чтение `<sub>/epoch/<id>` при `op: floor` / `import`.
  4) В `skills/lesson-spec/scripts/check_spec.py` для каталога приёмки урока требуется разрешить таблицу `puts.tsv` (после переноса `verdicts.tsv` в `02-installer/vectors/loader/` в `02-installer/acceptance/` останется `puts.tsv`).
- **Нарушено:** `Platform/module-design.md:62-65,166`, `ADR-0088` доп. (1).
- **Следствие:** Поправить `note` в `id-map.tsv`, абзацы `**Данные**`, три умолчания `М10/2 Н1.5` и поддержку `puts.tsv` в `check_spec.py` перед переносом урока 2.

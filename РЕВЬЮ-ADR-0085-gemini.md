# Отчёт ревьювера: ADR-0085 («Схема формы спеки — проверка рядом с нормой, не норма»)

**Ревьювер:** Gemini (`Ревью спецификации`)
**Срез курса:** `9104a326e`
**Ветка:** `gemini/review-adr-0085`
**Предмет ревью:**
- `decisions/0085-схема-формы-спеки-проверка-рядом-с-нормой.md`
- Основание: `/Users/murat/Downloads/ОЦЕНКА-JSON-SCHEMA-ДЛЯ-СПЕКИ.md`, `/Users/murat/w2c/cammeta-schema-pilot/REPORT.md` (и `/Users/murat/w2c/cammeta-schema-pilot/data/PROGRESS.md`)
- Исполнение на срезе `9104a326e`:
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.schema.yaml`
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.references.tsv`
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md`
  - `skills/lesson-spec/scripts/spec_schema/{run.py,textlayer.py,refs.py}`
  - `skills/lesson-spec/scripts/check_spec.py`, `skills/lesson-spec/scripts/test_check_spec.py`
  - `skills/lesson-spec/references/validation.md`, `skills/lesson-spec/references/change-map.md`

---

## Вывод: **с правками**

Архитектурное решение ADR-0085 — **оставить прозу `М10/2` и корпус `02/cases/` единственной нормой строгого загрузчика, поместить схему формы и таблицу ссылок рядом с уроком как исполняемую проверку в `check_spec`, не включать их в выгрузку реализаций и перенести центр тяжести JSON Schema на схемы семей данных (`Platform/common/data/schemas/`)** — технически обосновано, подтверждено результатами пилота и верно по существу.

Однако само исполнение на срезе `9104a326e` содержит ряд **серьёзных** расхождений между прозой норм (`М10/2`, `М10/3`, `М11`) и связкой `.schema.yaml` + `.references.tsv` + `textlayer.py` + `refs.py`, а также пробелы в охвате `check_spec.py`, из-за которых прямо на текущем срезе `9104a326e` продуктовые спеки `Source/vms/{auto,cam,live}.subsystem.yaml` не проходят новую схему (остались со старым ключом `placement.offers` после коммита `e50b37d55`), но `check_spec.py` выдаёт зелёный `PASS`.

Ниже приведены замечания по шкале `skills/lesson-spec/references/review-checklist.md` и подробный разбор по всем пяти вопросам задания.

---

## Сводка замечаний по шкале `review-checklist.md`

### Блокеры

Блокеров, требующих отмены архитектурного выбора ADR-0085 («проверка рядом с нормой, не норма»), нет. Следующие два дефекта на срезе `9104a326e` ломают согласованность репозитория и требуют обязательного исправления перед закрытием задачи:

1. **`[блокер среза]` `Source/vms/{auto,cam,live}.subsystem.yaml` отвергаются собственной схемой `02-the-spec-and-the-strict-loader.schema.yaml` на срезе `9104a326e`, а `check_spec.py` этого не видит.**
   - **Где:** `Source/vms/auto.subsystem.yaml:133`, `Source/vms/cam.subsystem.yaml:299`, `Source/vms/live.subsystem.yaml:31`; `skills/lesson-spec/scripts/check_spec.py:840`.
   - **Суть:** Коммит `e50b37d55` («ключ спеки `offers → grows` … схема формы — тем же коммитом (ADR-0085)») переименовал `placement.offers` в `placement.grows` в `М10/2.norms.md`, `02-the-spec-and-the-strict-loader.schema.yaml` и `02/cases/`, но не обновил продуктовые спеки `Source/vms/*.subsystem.yaml`. При прогоне `Runner().judge()` на них возвращается:
     - `Source/vms/auto.subsystem.yaml` → `refused:key`, line `133`, path `placement/offers`;
     - `Source/vms/cam.subsystem.yaml` → `refused:key`, line `299`, path `placement/offers`;
     - `Source/vms/live.subsystem.yaml` → `refused:key`, line `31`, path `placement/offers`.
   - **Почему `check_spec.py` молча прошёл:** `check_spec.py:840` проверяет через `Runner.judge()` только `Source/tests/testdata/acceptance/М10_Platform/02/cases/*.subsystem.yaml` и не проверяет ни `Source/vms/*.subsystem.yaml`, ни `Source/tests/testdata/testsub*.subsystem.yaml`, ни `02/puts/*.subsystem.yaml`, ни `06/variants/*/*.subsystem.yaml`, ни `09/probe-x.subsystem.yaml`.

### Серьёзные замечания

2. **`[серьёзное]` `refs.py:196–202` (`option_name`, `option_value`) отвергает `display.options.<имя>` для `enum`-полей таблиц вопреки `М10/2 Н1.4`.**
   - **Где:** `skills/lesson-spec/scripts/spec_schema/refs.py:196–202` против `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:353, 355`.
   - **Норма (`М10/2 Н1.4:353, 355`):**
     - `display.options.*`: «поле единицы (`fields:`) **или поле таблицы, если ключ стоит у таблицы**; или ключ `status` при непустом `unit.status_words`»;
     - `display.options.<имя>.*`: «значения `enum` поля единицы **или таблицы** (или слова `unit.status_words` при `<имя> = status`), без `default`; иное имя или поле без `enum` — отказ».
   - **Факт в `refs.py:196–202`:** проверяется только `v in d.unit and "enum" in (d.unit[v] or {})` (плюс `status_words`), а словари полей таблиц (`tables.*.fields`) не проверяются вовсе.
   - **Контрпример:** валидная спека с `tables.t1.fields.mode: {type: string, enum: [fast, slow], default: fast}` и `display.options.mode: {fast: Быстро}` получает ложный отказ `refused:reference` (`display/options/mode`, rule `option_name`).

3. **`[серьёзное]` `textlayer.py:39, 104` (`RE_DASH_VALUE`) нарушает `М10/2 Н1.1` в обе стороны: ложно отвергает элемент списка `- -` и портит строки внутри блочных скаляров `|` / `>`.**
   - **Где:** `skills/lesson-spec/scripts/spec_schema/textlayer.py:39, 104` против `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:61, 92`.
   - **Норма (`М10/2 Н1.1:61, 92`):** «дефис за местом значения (`«key: -»`, `«- -»`) — простой скаляр `"-"` (строка из дефиса): элемент списка не открывает в той же строке за ключом и не вкладывается в `«- -»`».
   - **Дефект А (пропуск `«- -»`):** `RE_DASH_VALUE = re.compile(r"^([ \t]*[^#\n:]+: +)-( *(?:#.*)?)$", re.M)` ищет только двоеточие ключа (`: +`) и не обрабатывает элемент списка `- -`. В результате валидный список `enum:\n  - -` разбирается `ruamel.yaml` как вложенный список `[None]` и ложно отвергается с `refused:value` (`type unit/fields/f/enum/0, empty unit/fields/f/enum/0/0`).
   - **Дефект Б (порча блочных скаляров до парсинга):** `textlayer.py:104` выполняет `RE_DASH_VALUE.sub(r'\1"-"\2', s)` по всему сырому тексту до вызова YAML-сканера. Любая строка вида `  a: -` внутри блочного скаляра `|` или `>` превращается в `  a: "-"`. Контрпример: валидная спека с `enum: ["a: -"]` и блочным `default: |-\n  a: -` ложно отвергается с `refused:value` (`in_enum`), так как `textlayer` подменил значение скаляра на `'a: "-"'`.

4. **`[серьёзное]` `textlayer.py:206–216` не проверяет экранирования `\` в строках `"..."` и пропускает запрещённые нормой экранирования YAML 1.2 (`\xXX`, `\ `, `\_` и др.).**
   - **Где:** `skills/lesson-spec/scripts/spec_schema/textlayer.py:206–216` и `02-the-spec-and-the-strict-loader.schema.yaml:24` (`§2`) против `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:68`.
   - **Норма (`М10/2 Н1.1:68`):** «в `"..."` допустимы только `\"`, `\\`, `\/`, `\n`, `\r`, `\t`, `\uXXXX` (4 hex) и `\UXXXXXXXX` (8 hex, ≤ U+10FFFF, не суррогат); иная `\` — отказ». При этом шапка `02-...schema.yaml:24` утверждает, что это правило проверяется в `§2` (`Слой текста YAML до схемы`).
   - **Факт:** `textlayer.py` вообще не инспектирует сырые escape-последовательности в `"..."`, а проверяет лишь результирующий `ev.value` через `_check_chars()`. Так как `ruamel.yaml` поддерживает все экранирования YAML 1.2 (`\x41` → `A`, `\ ` → пробел, `\_` → `\u00a0`, `\a` → `\x07`), строки `title: "Cam\x41"` и `title: "Cam\ "` проходят `Runner.judge()` как **`ok`** вместо `refused:text`.

5. **`[серьёзное]` `schema.yaml:546` + `refs.py:112–122, 205–222` (`template_parts`, `request_key`, `table_key`): неверный класс отказа на `requests.key` с незакрытой `{` после закрытой `{…}` и пропуск одиночной `}` и недопустимых знаков шаблона.**
   - **Где:** `02-the-spec-and-the-strict-loader.schema.yaml:546`, `02-the-spec-and-the-strict-loader.references.tsv:51, 88`, `skills/lesson-spec/scripts/spec_schema/refs.py:112–122, 205–222` против `М10/2 Н1.2а:220, 237` и `М10/8 Н1.1:41`.
   - **Дефект А (неверный класс отказа `reference` вместо `value`):** по `М10/2 Н1.2а:237` «незакрытая `{` (`x-{unit`) — тоже без подстановки, `refused:value`». В `schema.yaml:546` стоит `pattern: '\{[^{}]+\}'` (находит хотя бы одну `{…}`). Если в `requests.key` есть одна валидная подстановка, а за ней незакрытая `{` (например, `key: "req-{a}-{b"`), `schema.yaml` пропускает строку, а `refs.py` (`request_key` в `references.tsv:51`) отвергает её с классом **`refused:reference`** вместо **`refused:value`**. (Для `tables.*.key` в `references.tsv:88` стоит класс `value`, поэтому там случайно выходит `refused:value`, а для `requests.key` — `refused:reference`).
   - **Дефект Б (пропуск одиночной `}` и невалидных знаков ключа):** `template_parts()` в `refs.py:112–122` ищет только открывающую `{` и не проверяет ни отсутствие одиночных `}` вне `{…}`, ни допустимость статических литералов шаблона (`[A-Za-z0-9._:-]`, без префикса `free-` для `requests.key` по `М10/8 Н1.1:41`; без `/`, пробелов и управляющих для `tables.<т>.key` по `М10/2 Н1.2а:220`). В результате:
     - `requests.key: "req-{a}}"` → **`ok`**;
     - `requests.key: "free-{a}"` → **`ok`**;
     - `tables.t1.key: "k-{a}} / {a}"` → **`ok`**.

6. **`[серьёзное]` `schema.yaml:288, 314, 325–350` разрешает ключ `schema:` на полях любого типа (`int`, `string`, `bool`, `url`, `blob` и т.д.), а `jsonSchemaLite` (`schema.yaml:398–420`) не проверяет типы своих ключевых слов и синтаксис `pattern`.**
   - **Где:** `02-the-spec-and-the-strict-loader.schema.yaml:288, 314, 325–350, 398–420` против `М10/3 Н1.2:124`.
   - **Дефект А (`schema:` на не-`json` полях):** по `М10/3 Н1.2:124` под-ключ `schema` задаёт схему `json`-поля («Значение `json`-поля — любое значение JSON; его `schema` — JSON Schema 2020-12…»). В `fieldByType` (`schema.yaml:349–350`) есть запрет `credentials`/`secret_in`/`schemes` для не-`url` полей, но нет запрета `schema` для не-`json` полей. В результате `unit.fields.a: {type: int, min: 0, max: 10, default: 1, schema: {type: integer}}` проходит как **`ok`**.
   - **Дефект Б (пустые схемы `{}` внутри `jsonSchemaLite`):** в `schema.yaml:402–412` для `type`, `enum`, `const`, `required`, `minItems`, `maxItems`, `minLength`, `maxLength`, `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `pattern` заданы пустые подсхемы `{}` (любое JSON-значение), а `run.py` проверяет через `regress.Regex` только `pattern` самой `02-...schema.yaml`, но не пользовательские `pattern` в `unit.fields.*.schema` и `requests.schema`. В результате заведомо битая JSON Schema в спеке:
     `schema: {type: 123, minLength: "abc", required: "not_an_array", pattern: "["}`
     проходит `Runner.judge()` как **`ok`**.

7. **`[серьёзное]` Три расхождения проверки `domain.*` (`schema.yaml` + `refs.py`) с нормами М11, на которые ссылается `М10/2 Н1.2а:298–304`.**
   - **7а. `domain.books.<книга>.key`, `.to`, `.show[]` (`schema.yaml:240, 786–791` против `М11/5 Н1.1:29–35`, `Н1.2:46`):**
     `$defs/notSecretName` определено как `{type: string, minLength: 1, pattern: '^(?!.*_secret$)'}` без пересечения с `$defs/name` (`^[a-z0-9][a-z0-9_-]*$`). Поэтому `key: "not a valid name!"`, `to: "../bad"`, `show: ["also not a name!"]` проходят как **`ok`**, хотя по `М11/5 Н1.1:35` «`key` или `to` — секрет (`*_secret`) **или не имя**» — отказ загрузчика.
   - **7б. `domain.tokens.<вид>.unit` с явной своей подсистемой `sub: <своя>` без `domain.ref` (`refs.py:283–284` против `М11/7 Н1.1:32`):**
     По `М11/7 Н1.1:32` у `tokens.<вид>.unit`: «`sub?`: подсистема единицы (нет — своя; **своя требует `domain.ref`**)». В `refs.py:284` записано:
     `ok = (trail[-1][1] == "unit" and "sub" in v) or bool(d.domain.get("ref"))`
     То есть проверяется лишь наличие ключа `"sub"`, а не `v.get("sub") not in (None, d.name)`. Если в спеке подсистемы `cam` без `domain.ref` написать `tokens.t1.unit: {sub: cam, field: f1}`, `Runner.judge()` ошибочно вернёт **`ok`**.
   - **7в. `domain.keys` с чужой подсистемой (`schema.yaml:769–770` против `М11/9 Н1.8:241`):**
     По `М11/9 Н1.8:241` «ключи и семья — под `domain/<sub>/`» (своей подсистемы `<sub>`), как и `domain.books.<книга>.from` (`М11/5 Н1.1:35`). Для `books.*.from` в `references.tsv:94` есть проверка `book_from` (`v.startswith(f"domain/{d.name}/")`), а для `domain.keys.*` в `references.tsv` проверки нет — `schema.yaml:769` допускает любой `^domain/[a-z0-9][a-z0-9_-]*/.+$`. Поэтому в подсистеме `cam` запись `domain: {keys: {k1: "domain/foreign/row"}}` проходит как **`ok`**.

8. **`[серьёзное]` Условия ложного `PASS` в `check_spec.py:806–814, 852, 938–940` и отсутствие сверки с `02/diagnostics.tsv`.**
   - **8а. Опциональность `.schema.yaml` в `check_spec.py:939`:** вызов `self.spec_schema(...)` обёрнут в `if schema.exists() or schema_refs.exists():`. Если оба файла случайно удалены или переименованы при смене слага урока, `check_spec.py` молча пропустит проверку и вернёт `PASS (schema_cases=0)`. Для урока, у которого существует `verdicts.tsv`, наличие и `.schema.yaml`, и `.references.tsv` должно быть обязательным.
   - **8б. Неполная сверка `classes.tsv` с `verdicts.tsv` (`check_spec.py:806–814, 852`):** метод `classes()` проверяет только то, что каждый случай из `classes.tsv` имеет `refused` в `verdicts.tsv`, но **не проверяет обратное**: что каждый `refused`-случай из `verdicts.tsv` присутствует в `classes.tsv`. А в `spec_schema()` (`check_spec.py:852`) стоит `elif case in classes and got["class"] != classes[case]:`. Если добавить в `verdicts.tsv` новый `refused`-случай и забыть строку в `classes.tsv`, `check_spec.py` молча не проверит класс отказа.
   - **8в. Отсутствие сверки с `02/diagnostics.tsv`:** `Runner.judge()` уже вычисляет `got["line"]` и `got["paths"]` (и на срезе `9104a326e` они совпадают на 40 из 40 строк `02/diagnostics.tsv`), но `check_spec.py:819–855` вообще не читает `diagnostics.tsv` и не сверяет с ним вывод `Runner.judge()`.

9. **`[серьёзное]` Незакреплённые версии `ruamel.yaml`, `jsonschema`, `regress` в `validation.md` и `check_spec.py` при использовании приватного API `ruamel.yaml`.**
   - **Где:** `skills/lesson-spec/references/validation.md:20`, `skills/lesson-spec/scripts/check_spec.py:44–46`, `skills/lesson-spec/scripts/spec_schema/textlayer.py:42–53, 108–114`.
   - **Суть:** `textlayer.py` переопределяет внутренний метод `ruamel.yaml.scanner.Scanner.stale_possible_simple_keys` (читая приватные поля `self.SimpleKey`, `self.reader.index`, `self.allow_simple_key`) и полагается на то, что `DuplicateKeyError` и суррогаты в `0.19.1` бросают определённые классы исключений (`ValueError`, `ScannerError`). При этом в `validation.md:20` и `SCHEMA_INSTALL` (`check_spec.py:44–46`) команда `uv run` указана **без версий** (`--with jsonschema --with ruamel.yaml --with regress`), тогда как в пилоте версии были жёстко зафиксированы (`ruamel.yaml==0.19.1`, `jsonschema==4.26.0`, `regress==2026.9.1`).

### Косметические замечания

10. **`[косметическое]` Устаревшие числа и неполные пути в тексте `decisions/0085-схема-формы-спеки-проверка-рядом-с-нормой.md` и артефактные пометки `(добавлено пилотом JSON Schema)` в `М10/2.norms.md`.**
    - В `ADR-0085:17, 24, 59` указано «на **439** случаях корпуса», «**439/439** вердиктов», «**786** строк против 258», тогда как на этом же срезе корпус `М10/2` уже содержит **466** случаев (`М10/2 Н5:600`, `02/verdicts.tsv` после добавления 27 случаев `c5_*`), а `02-the-spec-and-the-strict-loader.schema.yaml` содержит **885** строк (786 — число строк без 99-строчной шапки).
    - В `ADR-0085:43` скрипт выгрузки назван `tools/export.sh` без указания репозитория `cammeta-specs` (в репозитории курса такого пути нет — он в `/Users/murat/w2c/cammeta-specs/tools/export.sh`).
    - В `ADR-0085:35, 64` указано, что `Platform/common/data/catalog.tsv` в колонке `schema` ссылается на `Platform/common/data/schemas/<id>.schema.json`, однако сейчас в `Platform/common/data/catalog.tsv` колонка `schema` заполнена ссылками на markdown-якоря норм (`М10_Platform/spec/03-units-slots-epochs-lease.norms.md#н14-слот`), и `check_spec.py:665` (`catalog()`) проверяет там именно `#якорь`. Стоит явно оговорить в ADR-0085, как колонка `schema` в `catalog.tsv` будет совмещать ссылку на норму и ссылку на `.schema.json`.
    - В `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md` (строки `19, 41, 49, 53, 57, 61, 65, 76, 212, 213, 237, 541, 549`) остались 13 редакционных пометок `(добавлено пилотом JSON Schema)`. Поскольку `.norms.md` входит в выгрузку для генераторов (`cammeta-specs`), временные пометки пилота в тексте нормы не нужны — история хранится в git и в `ADR-0085`.

11. **`[косметическое]` Разнобой класса отказа в `references.tsv:20–21` для `not_unit_rows`, мёртвый код в `refs.py:244–245` и противоречие в примечании `М10/7 Н1.3:282` про `domainworker`.**
    - В `02-the-spec-and-the-strict-loader.references.tsv:20–21` одна и та же проверка `not_unit_rows` для `tables.~` (когда `tables` — отображение) имеет класс `reference`, а для `tables.*` (когда `tables` — список имен до срабатывания схемы типа) — класс `value`.
    - В `skills/lesson-spec/scripts/spec_schema/refs.py:244–245` в ветке `check == "unplaced"` читается `(d.tree.get("events") or {}).get("types") or {}`, хотя в `М10/2 Н1.2а:244–246` и `schema.yaml:134–151` никакого `events.types` нет (есть `about: {sub, field}`, где `about.field` уже обязан быть `fixed`).
    - В `М10_Platform/spec/07-secrets-credentials-and-scrubbing.norms.md:282` примечание гласит: `domainworker — процесс доменного воркера из модуля М11; спеки подсистем его не включают`, тогда как `М10/2 Н1.2а:258` («из закрытых 8 урока 7 Н1.3»), `Source/tests/testdata/platform_lists.tsv:22`, `02-...schema.yaml:601` и приёмочный вариант `06/variants/v5-secret-domainworker/va.subsystem.yaml:13` явно разрешают `domainworker` в `secrets.readers`.

---

## Подробный разбор по 5 вопросам задания

### 1. Вывод пилота и решение «проверка, не норма»: сильные и слабые доводы, что упущено

#### Сильные доводы (почему решение верное)
1. **Несовместимость готовых парсеров YAML 1.2 с профилем `М10/2 Н1.1` доказана численно.** В пилоте (`/Users/murat/w2c/cammeta-schema-pilot/REPORT.md`, раздел 1 и 2) три зрелых парсера (`ruamel.yaml 0.19.1`, `gopkg.in/yaml.v3 v3.0.1`, `goccy/go-yaml v1.19.2`) разошлись между собой на **84 из 1270** входов YAML Test Suite и разошлись с профилем `М10/2 Н1.1` на `\/` в `"..."`, табуляциях в отступе блочных скаляров, лимите простого ключа в 1024 знака, непарных суррогатах `\uD800`, теге `!` и позиции ошибки (`Line`/`EndMark`). Следовательно, убрать собственный текстовый/событийный слой из реализаций нельзя даже при наличии JSON Schema.
2. **Семантический зазор JSON Schema 2020-12 на числах и ключевых словах.** По JSON Schema 2020-12 `type: integer` определяется через математическое значение (нулевая дробная часть), поэтому `1.0` и `1e2` валидны как `integer`, тогда как `М10/2 Н1.1:69` и `М10/3 Н1.2` требуют различать запись `int` (`1`) и `float` (`1.0`). Кроме того, стандартные валидаторы имеют собственные баги и особенности (`santhosh-tekuri/jsonschema/v6 v6.0.3` портит `InstanceLocation` при `propertyNames` из-за общего базового массива слайса; Python `jsonschema` использует `re`, где `$` совпадает перед `\n`, и требует подмены на `regress`).
3. **Невыразимость `М10/2 Н1.3` и `Н1.4` в чистой JSON Schema 2020-12.** Перекрёстные ссылки между ветками дерева (87 правил в `.references.tsv`) и проверка соразмерности чисел `min <= default <= max` требуют отдельного процедурного обхода (`refs.py`, `check_numbers_and_empties`). В итоге связка «шапка + схема + таблица ссылок» (`885 + 97 = 982` строки плюс `805` строк Python в `spec_schema/`) вчетверо объёмнее сводной таблицы `Н1.2а` (`258` строк) и не может заменить прозу как более компактный источник истины.
4. **Ценность обоих пилотов как перекрёстной верификации.** Пилот формы спеки выявил 14 реальных пробелов и разночтений в `М10/2` (закрытых 27 новыми случаями `c5_*`), а пилот схем семей данных (`/Users/murat/w2c/cammeta-schema-pilot/data/PROGRESS.md`) выявил 4 настоящих расхождения между нормами и кодом Go/Python (`updated_at_ms` в `format_record`, `epoch`/`url` в `worker_Assign`, `reason` и `items` в `console_audit_line`). Размещение `.schema.yaml` в `check_spec` закрепляет этот эффект для `М10/2`, а перенос основного фокуса JSON Schema на 22 семьи данных (`Platform/common/data/schemas/`) бьёт точно в цель — там входы уже являются чистым JSON без YAML-слоя и без 87 перекрёстных ссылок.

#### Слабые доводы и что упущено в ADR-0085
1. **Ложная эквивалентность «проверка схемы на корпусе = проверка согласованности прозы и корпуса» (`ADR-0085:28`).**
   В `ADR-0085:28` утверждается: *«`check_spec` прогоняет схему и таблицу ссылок на всех случаях корпуса и сверяет вердикт и класс отказа с `verdicts.tsv` и `classes.tsv`. Расхождение прозы и корпуса становится падением `check_spec`»*.
   На самом деле `check_spec` сверяет **`schema + refs + textlayer` ↔ `corpus` (`verdicts.tsv`, `classes.tsv`)**. Проза `.norms.md` в этом контуре напрямую не участвует:
   - если автор правит прозу `.norms.md` и забывает обновить `.schema.yaml` и `cases/`, `check_spec` остаётся зелёным;
   - если в `.schema.yaml` или `refs.py` допущена ошибка на правиле, для которого в `02/cases/` ещё нет негативного/позитивного случая (как в найденных нами пунктах 2–7 выше), `check_spec` также показывает `466/466 PASS`.
2. **Упущена проверка остальных `.subsystem.yaml` репозитория против схемы формы.**
   В репозитории помимо 466 файлов `02/cases/*.subsystem.yaml` есть ещё продуктовые и тестовые спеки (`Source/vms/*.subsystem.yaml`, `Source/tests/testdata/testsub*.subsystem.yaml`, `02/puts/*.subsystem.yaml`, `06/variants/*/*.subsystem.yaml`, `09/probe-x.subsystem.yaml`, `Source/tests/testdata/spec_verdicts/*.subsystem.yaml`). То, что `check_spec` не прогоняет `Runner.judge()` по ним, уже привело к поломке `Source/vms/{auto,cam,live}.subsystem.yaml` на срезе `9104a326e`.
3. **Не согласован формат колонки `schema` в `Platform/common/data/catalog.tsv` для пилота схем данных (`ADR-0085:35, 64`).**
   Сейчас `check_spec.py:665` (`catalog()`) требует, чтобы колонка `schema` в `catalog.tsv` содержала путь к `.norms.md` с `#якорем` раздела. Если при развёртывании пилота данных туда записать `Platform/common/data/schemas/<id>.schema.json` без якоря, `check_spec.py` упадёт, либо мы потеряем привязку строки каталога к нормативному разделу описания структуры.

---

### 2. Схема, `references.tsv`, `refs.py` и `textlayer.py` против норм урока 2 на срезе `9104a326e`

Ниже сведены все расхождения между нормами (`Н1.1–Н1.4`, `Н3`, `Н4`) и реализацией проверки в `02-the-spec-and-the-strict-loader.{schema.yaml,references.tsv}` и `skills/lesson-spec/scripts/spec_schema/{textlayer.py,refs.py,run.py}`, проверенные прямым запуском `Runner().judge()`:

| № | Узел нормы | Что требует норма | Что делает `.schema.yaml` / `refs.py` / `textlayer.py` | Контрпример и фактический вердикт `Runner().judge()` |
|---|---|---|---|---|
| 1 | `М10/2 Н1.1:61, 92` (`- -` и блочные скаляры) | `«key: -»` и `«- -»` на месте простого значения — строка `"-"`; внутри блочных скаляров `\|` и `>` текст не переписывается | `textlayer.py:39, 104`: `RE_DASH_VALUE` ищет только `: +-` (не знает `- -`) и делает `sub()` по всему тексту до YAML-сканера, меняя строки внутри `\|` / `>` | 1) `enum:\n  - -` → ложный `refused:value` (вместо `ok`); 2) `enum: ["a: -"]` + `default: \|-\n  a: -` → ложный `refused:value (in_enum)` (вместо `ok`) |
| 2 | `М10/2 Н1.1:68` (экранирования в `"..."`) | В `"..."` допустимы только `\"`, `\\`, `\/`, `\n`, `\r`, `\t`, `\uXXXX`, `\UXXXXXXXX`; иная `\` — отказ `refused:text` | `textlayer.py:206–216`: сырой токен `"..."` не проверяется, проверяется только декодированный `ev.value` | `title: "Cam\x41"` и `title: "Cam\ "` → ложный **`ok`** (вместо `refused:text`) |
| 3 | `М10/2 Н1.4:353, 355` (`display.options`) | `display.options.<имя>` может называть `enum`-поле единицы **или поле таблицы** | `refs.py:196–202`: `option_name` и `option_value` ищут поле только в `d.unit` и `d.status_words`, игнорируя `d.tables` | Таблица `t1` с полем `mode` (`enum: [fast, slow]`) и `display.options.mode: {fast: Fast}` → ложный `refused:reference` (вместо `ok`) |
| 4 | `М10/2 Н1.2а:237` (`requests.key` с незакрытой `{`) | Незакрытая `{` в `requests.key` — `refused:value` | `schema.yaml:546` (`pattern: '\{[^{}]+\}'`) пропускает `"req-{a}-{b"`, а `references.tsv:51` (`request_key`) даёт класс `reference` | `requests.key: "req-{a}-{b"` → **`refused:reference`** (вместо `refused:value`) |
| 5 | `М10/2 Н1.2а:220, 237`, `М10/8 Н1.1:41` (`requests.key`, `tables.*.key`) | Шаблон ключа запроса (`rid` без `free-`) и ключа таблицы (без `/`, пробелов и одиночных `}`) | `refs.py:112–122` (`template_parts`) ищет только `{` и не проверяет ни лишние `}`, ни статические части шаблона | `requests.key: "req-{a}}"`, `requests.key: "free-{a}"`, `tables.t1.key: "k-{a}} / {a}"` → ложный **`ok`** (вместо `refused:value`) |
| 6 | `М10/3 Н1.2:124`, `М10/2 Н1.2а:213` (`schema` у поля и `jsonSchemaLite`) | `schema` принадлежит только `json`-полю; ключевые слова JSON Schema имеют строгие типы (`type` — строка/массив строк, `minLength` — целое ≥ 0, `pattern` — валидная ECMA-262 регулярка и т.д.) | `schema.yaml:288, 314, 325–350` разрешает `schema` на любом типе поля (`int`, `string`, …); в `jsonSchemaLite` (`schema.yaml:402–412`) стоят пустые `{}` | 1) `unit.fields.x: {type: int, ..., schema: {type: integer}}` → ложный **`ok`**; 2) `schema: {type: 123, minLength: "abc", pattern: "["}` → ложный **`ok`** |
| 7 | `М10/2 Н1.2а:301`, `М11/5 Н1.1:29–35`, `Н1.2:46` (`domain.books`) | `key`, `to`, `show[]` в `domain.books.<книга>` — имена (`$defs/name`) и не `*_secret` | `schema.yaml:240` (`notSecretName`) проверяет только `minLength: 1` и `^(?!.*_secret$)` без шаблона имени | `key: "not a valid name!"`, `to: "../bad"`, `show: ["bad name!"]` → ложный **`ok`** (вместо `refused:value`) |
| 8 | `М10/2 Н1.2а:303`, `М11/7 Н1.1:32` (`domain.tokens.<вид>.unit`) | `sub?`: подсистема единицы (нет — своя; **своя требует `domain.ref`**) | `refs.py:283–284` проверяет только `"sub" in v`, не проверяя `v["sub"] != d.name` | В подсистеме `cam` без `domain.ref`: `tokens.t1.unit: {sub: cam, field: f1}` → ложный **`ok`** (вместо `refused:reference`) |
| 9 | `М10/2 Н1.2а:300`, `М11/9 Н1.8:241` (`domain.keys`) | Ключи в `domain.keys` лежат под `domain/<sub>/` своей подсистемы `<sub>` | `schema.yaml:769` проверяет `^domain/[a-z0-9][a-z0-9_-]*/.+$`, в `references.tsv` нет правила `<sub> == d.name` | В подсистеме `cam`: `domain.keys.k1: "domain/foreign/row"` → ложный **`ok`** (вместо `refused:reference` / `refused:value`) |
| 10 | `М10/2 Н1.4:321` (`tables` и `unit.rows`) | Имя таблицы не совпадает с `unit.rows` | В `references.tsv:20` для `tables.~` указан класс `reference`, а в `references.tsv:21` для `tables.*` — класс `value` | Несогласованность класса в таблице ссылок (хотя на `tables: [items]` раньше срабатывает схема `type: object`) |

Проверка классов отказа (`Н3`: `text`, `key`, `value`, `number`, `reference`) и детерминизма первого отказа (`Н4`):
- Иерархия приоритетов в `run.py` (`textlayer` → `schema` с весами `KEY_ERROR_KINDS`/`VALUE_ERROR_KINDS` и путём ошибки → `check_numbers_and_empties` → `refs.check_references`) на всех 466 существующих случаях корпуса `02/cases/` даёт **466/466** совпадений по `verdicts.tsv`, **337/337** по `classes.tsv` и **40/40** по `diagnostics.tsv`.
- Единственное нарушение класса отказа на новых входах — пункт 4 таблицы выше (`requests.key: "req-{a}-{b"` даёт `refused:reference` вместо `refused:value`).

---

### 3. `check_spec.py` и `test_check_spec.py`: ловит ли расхождение, нет ли ложных PASS, зависимости и тесты

1. **Поведение при отсутствии зависимостей (`jsonschema`, `ruamel.yaml`, `regress`):**
   - Проверено по коду (`check_spec.py:830–834`) и тесту `test_form_schema_without_dependencies_fails_with_the_install_command` (`test_check_spec.py:604–618`): если `.schema.yaml` существует, но хотя бы одна из библиотек не импортируется, `check_spec.py` **не пропускает** проверку, а завершается с **`FAIL`** и печатает точную команду установки `SCHEMA_INSTALL`. Это сделано правильно.
2. **Где возможны ложные `PASS`:**
   - **Пропуск остальных `.subsystem.yaml` репозитория (`check_spec.py:840`):** как показано в замечании 1, `check_spec` проверяет схемой только `02/cases/*.subsystem.yaml`, но не проверяет `Source/vms/*.subsystem.yaml` (3 файла сейчас сломаны!), `Source/tests/testdata/testsub*.subsystem.yaml` (2 файла), `02/puts/*.subsystem.yaml` (2 файла), `06/variants/*/*.subsystem.yaml` (8 файлов), `09/probe-x.subsystem.yaml` (1 файл) и `Source/tests/testdata/spec_verdicts/*.subsystem.yaml` (138 файлов).
   - **Условие `if schema.exists() or schema_refs.exists():` (`check_spec.py:939`):** если оба файла `.schema.yaml` и `.references.tsv` отсутствуют у урока с `verdicts.tsv`, `check_spec` молча выдаёт `PASS (schema_cases=0)`.
   - **Неполная проверка `classes.tsv` (`check_spec.py:806–814, 852`):** если в `verdicts.tsv` добавлен `refused`-случай без строки в `classes.tsv`, `check_spec` не требует строки в `classes.tsv` и не проверяет класс отказа этого случая.
   - **Игнорирование `02/diagnostics.tsv` (`check_spec.py:819–855`):** `Runner.judge()` возвращает `line` и `paths`, но `check_spec.py` не сверяет их с `02/diagnostics.tsv`.
3. **Версии библиотек не закреплены:**
   - В `validation.md:20` и `check_spec.py:44–46` зависимости указаны без версий (`--with jsonschema --with ruamel.yaml --with regress`). Из-за того, что `textlayer.py` вмешивается во внутренности `ruamel.yaml.scanner.Scanner`, необходимо закрепить проверенные в пилоте версии (`ruamel.yaml==0.19.1`, `jsonschema==4.26.0`, `regress==2026.9.1`) или как минимум верхние границы мажорных/минорных версий.
4. **Оценка тестов в `test_check_spec.py`:**
   - Все 82 теста в `skills/lesson-spec/scripts/test_check_spec.py` проходят (`OK`), включая 6 новых тестов `test_form_schema_*` (`строки 558–618`): приём всех `ok_*`, отказ всех `bad_*` с тем же классом, мутация `ok_minimal` лишним ключом (`refused:key`), перестановка `min > max` (`refused:number`), опечатка в ссылке `unit.rows` (`refused:reference`) и `FAIL` при отсутствии библиотеки.
   - **Минус производительности:** прогон `test_check_spec.py` занимает **~56 секунд**, потому что в каждом из десятков тестов, вызывающих `self.check()`, заново создаётся `Runner()` (компилирующий 885-строчную схему и 466 случаев корпуса). Кеширование `Runner` по `(schema_path, refs_path, mtime)` внутри процесса ускорит `test_check_spec.py` в разы.

---

### 4. Поддержка: как «Спецификация» держит схему в согласии с нормой и чего не хватает

1. **Что уже сделано:**
   - В `skills/lesson-spec/references/change-map.md:29` добавлено правило: *«Меняется форма спеки подсистемы (ключи, типы, перечни, условия, ссылки в М10/2 или `domain.*` в М11) → `М10_Platform/spec/02-the-spec-and-the-strict-loader.schema.yaml` и `.references.tsv` тем же коммитом; прогон `check_spec.py` на корпусе `02/cases/`»*.
   - В `skills/lesson-spec/references/validation.md:20, 41, 88` документированы зависимости и пункт 17 проверки `check_spec.py`.
2. **Чего не хватает для надёжного удержания согласия прозы и схемы:**
   - **Нет упоминания в `skills/lesson-spec/SKILL.md` и `skills/lesson-spec/references/review-checklist.md`:** ни в основном файле навыка `SKILL.md`, ни в чек-листе ревью `review-checklist.md` файлы `.schema.yaml` и `.references.tsv` не упомянуты. В `review-checklist.md` нужно добавить пункт: при правке `М10/2` или `М11` (`domain.*`) проверять синхронность `.schema.yaml`, `.references.tsv` и пополнение `02/cases/` позитивным и негативным случаем на каждое изменённое правило.
   - **Нет механической сверки закрытых перечней между `platform_lists.tsv`, `М10/2.norms.md` и `02-...schema.yaml`:** в `Source/tests/testdata/platform_lists.tsv` уже лежат канонические перечни (`reserved_subsystems`, `reserved_tables`, `platform_fields`, `secret_readers`, `secret_row_keys`, `heartbeat_strings`), а в `02-...schema.yaml` те же списки продублированы вручную (`$defs/subsystemName`, `$defs/tableName`, `$defs/notPlatformField`, `$defs/secretReader`, `$defs/heartbeatString`). Добавить в `check_spec.py` автоматическую сверку этих `$defs` в `02-...schema.yaml` с `Source/tests/testdata/platform_lists.tsv` стоит ~25 строк кода и полностью исключит рассинхронизацию закрытых списков.
   - **Нет автоматической проверки git-диффа / таблицы `Н1.2а`:** `check_spec.py` может проверять, что все литеральные имена ключей из первого столбца сводной таблицы `Н1.2а` в `02-the-spec-and-the-strict-loader.norms.md` присутствуют в `02-the-spec-and-the-strict-loader.schema.yaml` (и наоборот).

---

### 5. Риски: валидаторы и `regress`/`ruamel` в `check_spec`, ECMA/RE2, `1.0` как целое, выгрузка без схемы

1. **Риск `ruamel.yaml` и `jsonschema` в `check_spec`:**
   - В `textlayer.py:42–53` подменён приватный метод `Scanner.stale_possible_simple_keys` из `ruamel.yaml`, чтобы отключить лимит длины простого ключа в 1024 символа в потоковом контексте `[...]`/`{...}` (`c5_flow_long_key_1025`), сохранив его в блочном контексте (`bad_text_long_key`). Это тонкая привязка к внутреннему устройству `ruamel.yaml 0.19.1`. Без пиннинга версий в `validation.md` и `SCHEMA_INSTALL` обновление `ruamel.yaml` может тихо сломать этот перехват.
2. **Риск ECMA-262 (`regress`) против RE2:**
   - В `02-the-spec-and-the-strict-loader.schema.yaml` в трёх местах используются конструкции negative lookahead `(?!...)` (`строки 240, 256, 631`: `notSecretName`, `notPlatformField`, `secret_in.query`). В ECMA-262 (`regress`) они валидны, но в RE2 (например, в Go `regexp`) lookahead **не поддерживается**.
   - Пока `02-...schema.yaml` исполняется только в Python `check_spec` через `regress`, это работает. Но:
     - во-первых, в шапке `02-...schema.yaml:65` (`§6. Профиль JSON Schema`) стоит явно записать, что регулярные выражения схемы используют ECMA-262 lookahead и требуют движка ECMA-262 (`regress`), а не RE2;
     - во-вторых, для будущего пилота **схем семей данных** (`Platform/common/data/schemas/<id>.schema.json`), которые по `ADR-0085:33–38` могут проверяться и из Go/Python тестов, необходимо сразу запретить lookahead/lookbehind и держаться пересечения ECMA-262 ∩ RE2 (выражая исключения через `not: {pattern: ...}` вместо `(?!...)`).
3. **Риск `1.0` как целое (`integer` в JSON Schema 2020-12):**
   - В `run.py:67–72` стандартный `TYPE_CHECKER` из `jsonschema.Draft202012Validator` переопределён: `integer` проверяется как `isinstance(instance, int) and not isinstance(instance, bool)`. В сочетании с `textlayer.resolve_plain()`, который возвращает `int` только для `RE_INT` и `float` для `1.0`/`1e2`, это корректно отвергает `1.0` на целочисленных полях спеки.
   - Однако для будущего пилота **схем семей данных** (`Platform/common/data/schemas/*.schema.json`) поверх чистого JSON стандартный валидатор JSON Schema (и в Python без `redefine("integer")`, и в Go `santhosh-tekuri/jsonschema`) по стандарту Draft 2020-12 **примет `1.0` и `1e2` за `type: integer`**. Это нужно явно зафиксировать в `ADR-0085` в разделе «Схемы семей данных (пилот)»: при проверке JSON-значений данных в Go/Python либо включать кастомный `integer`-чекер (по типу JSON-токена), либо полагаться на предварительную канонизацию JCS (RFC 8785), где целое число не имеет `.0`.
4. **Риск выгрузки без схемы (`/Users/murat/w2c/cammeta-specs/tools/export.sh`):**
   - Проверено по `/Users/murat/w2c/cammeta-specs/tools/export.sh:23`: строка `rm -f "$OUT"/М10_Platform/spec/*.schema.yaml "$OUT"/М10_Platform/spec/*.references.tsv` гарантирует, что файлы схемы и таблицы ссылок не попадают в пакет выгрузки.
   - **Побочная находка в `export.sh` и `spec_verdicts.tsv`:**
     - `Source/tests/testdata/spec_verdicts.tsv` содержит только **138** строк из **466** случаев `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv` (отсутствуют 328 случаев, включая все 27 новых `c5_*`);
     - кроме того, `/Users/murat/w2c/cammeta-specs/tools/export.sh:14` копирует только плоские `Source/tests/testdata/*.tsv`, но **не копирует подкаталог `Source/tests/testdata/spec_verdicts/*.subsystem.yaml`**, на который ссылается колонка `file` в `spec_verdicts.tsv` (тогда как полный корпус 466 файлов выгружается строкой 18 в `acceptance/М10_Platform/02/`).

---

## Конкретный перечень правок для закрытия замечаний

1. **Обновить продуктовые спеки и расширить охват `check_spec.py`:**
   - В `Source/vms/auto.subsystem.yaml:133`, `Source/vms/cam.subsystem.yaml:299`, `Source/vms/live.subsystem.yaml:31` заменить устаревший ключ `placement.offers` на `placement.grows`.
   - В `skills/lesson-spec/scripts/check_spec.py` (`spec_schema`) прогонять `Runner.judge()`:
     - по всем `02/cases/*.subsystem.yaml` со сверкой не только с `verdicts.tsv` и `classes.tsv`, но и с `02/diagnostics.tsv` (`line`, `paths`);
     - по всем `Source/vms/*.subsystem.yaml`, `Source/tests/testdata/testsub*.subsystem.yaml`, `02/puts/*.subsystem.yaml`, `06/variants/*/*.subsystem.yaml`, `09/probe-x.subsystem.yaml` (ожидая `ok` для валидных спек).
   - В `check_spec.py:806–814` проверять, что **каждый** `refused`-случай из `verdicts.tsv` присутствует в `classes.tsv`, а в `check_spec.py:938–940` требовать существования `.schema.yaml` и `.references.tsv`, если у урока есть `verdicts.tsv`.
2. **Привести `textlayer.py`, `refs.py`, `02-...schema.yaml` и `02-...references.tsv` в полное согласие с нормами `М10/2`, `М10/3` и `М11`:**
   - В `refs.py:196–202` (`option_name`, `option_value`) разрешить `enum`-поля из `tables.*.fields` согласно `М10/2 Н1.4:353, 355`.
   - В `textlayer.py` убрать до-парсерную замену `RE_DASH_VALUE.sub` по сырому тексту (чтобы не портить блочные скаляры `|`/`>`), обрабатывать скаляр `"-"` для `«key: -»` и `«- -»` с учётом состояния сканера (вне блочных скаляров) и добавить проверку допустимых экранирований `\` в сырых строках `"..."` по `М10/2 Н1.1:68`.
   - В `schema.yaml:546` и `refs.py:112–122, 205–222` привести проверку шаблонов `requests.key` и `tables.*.key` в согласие с `М10/2 Н1.2а:220, 237` и `М10/8 Н1.1:41` (незакрытая `{` и лишняя `}` → `refused:value`; проверка статических символов `rid` и запрета `free-`).
   - В `schema.yaml:325–350` запретить ключ `schema` на полях с `type != "json"`, а в `jsonSchemaLite` (`schema.yaml:398–420`) задать типы для ключевых слов JSON Schema и проверять `pattern` через `regress.Regex`.
   - В `schema.yaml:240` (`notSecretName`) добавить шаблон имени `^[a-z0-9][a-z0-9_-]*$`; в `refs.py:283–284` (`need_domain_ref`) проверять `v.get("sub") not in (None, d.name)`; для `domain.keys` добавить проверку `<sub> == d.name`.
   - Добавить соответствующие случаи в `02/cases/`, `verdicts.tsv`, `classes.tsv`.
3. **Укрепить поддержку и текст `ADR-0085`:**
   - Закрепить версии `jsonschema==4.26.0`, `ruamel.yaml==0.19.1`, `regress==2026.9.1` в `validation.md:20` и `check_spec.py:44–46`.
   - Добавить правило синхронности `.schema.yaml`/`.references.tsv` в `skills/lesson-spec/SKILL.md` и `skills/lesson-spec/references/review-checklist.md`, а в `check_spec.py` — сверку закрытых списков `02-...schema.yaml` с `Source/tests/testdata/platform_lists.tsv`.
   - В `decisions/0085-схема-формы-спеки-проверка-рядом-с-нормой.md` обновить числа корпуса (`439` → `466`, `786` → `885` строк файла), уточнить путь `cammeta-specs/tools/export.sh`, описать совмещение ссылки на норму и `.schema.json` в `catalog.tsv` и оговорить проверку `1.0` и RE2 для пилота схем данных.
   - Убрать 13 временных пометок `(добавлено пилотом JSON Schema)` из `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md` и поправить примечание про `domainworker` в `М10_Platform/spec/07-secrets-credentials-and-scrubbing.norms.md:282`.

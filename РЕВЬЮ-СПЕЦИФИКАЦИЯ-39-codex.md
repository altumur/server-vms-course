# Ревью спецификации — прогон 39, Codex

- Дата: 2026-10-17 (Europe/Minsk).
- Срез курса и исходный HEAD: `bc9dcbaecfb712d2d0b3afc2944e097efe84c257`.
- Дерево: `/private/tmp/server-vms-review-spec-39`; ветка: `codex/review-spec-39-codex`.
- Назначенный охват: М10/1–11, весь `М10_Platform/spec/`, приёмка 01–11, общие данные, module-design/README/GLOSSARY и весь lesson-spec.
- **Статус задания: частично выполнено; полного PASS нет.** Доступный объём контекста этого исполнения не позволил завершить назначенное полное чтение. Ниже сохранены четыре подтверждённые причины; неполный охват перечислен отдельно. Итог служебного задания — `failed`, а не независимый полный результат.

Перед анализом HEAD проверен на точное совпадение со срезом; свидетельство — `/private/tmp/review-spec-39-codex-logs/exact-head.json` и `.stdout`. Manifest назначения `/private/tmp/spec39-scope.json` сверен с `git ls-tree` своего среза: 359 файлов, отсутствующих и лишних core-путей нет (`inventory.json`, `inventory.stdout`, `ls-tree.json`). Это инвентаризация, а не свидетельство полного чтения.

Номера ADR сверены с `decisions/README.md` (строки 17–18, 60, 86, 88). Канон — norms; инструкции и лекции проверяются на согласованность с ним. Заявленные ограничения профиля и открытый долг внедрения не включались в находки. Отдельного прохода закрытия R38 не было; отчёты и пробы других ревьюверов 39 не читались. Дополнительные ревьюверы не запускались.

## М10/1

### R39-01 — мелкая: пример проверки прав теряет различие write/delete

**Места:** `М10_Platform/spec/01-storage.README.md:36`; первичный владелец — `М10_Platform/spec/06-rights.norms.md:71`, `:96` (Н1.3–Н1.4, М10/6-07). Затронуты уроки 1 и 6; причина учитывается один раз в уроке 1.

**Противоречие.** Инструкция предлагает пример `authorize(caller, action, key)` с `action ∈ {read, write}` и пояснением «удаление — запись». Канон прав различает три действия. В частности, console имеет write, но не delete для `objects/<s>/commands/*`.

**Минимальный контрпример.** При обычных выведенных правах для роли console и ключе `objects/cam/commands/r-1` проверка put должна разрешить действие, а проверка delete — запретить. Предложенное отождествление передаёт в обе проверки один и тот же набор аргументов `(console, write, objects/cam/commands/r-1)`; функция с указанными входами не может выдать оба необходимых результата. Этот пример подтверждён также разрешёнными данными `configstore-rights.json` для данного ключа; модель не вызывает оценщик продукта.

**Основание и последствия.** ADR-0080 и `М10_Platform/module-design.md:91`–92: инструкция следует канону. Неверен пример реализации различимых прав, а не свободный выбор имени/сигнатуры функции. Поскольку пример необязателен и первичный канон однозначен, серьёзность мелкая; обязательного внутреннего API находка не требует.

**Рекомендация:** убрать отождествление удаления с write либо показать пример, сохраняющий различие разрешений; внутреннее устройство оставить реализации.

**Происхождение:** была до исправлений 38. На `294ca6c59cf871f05d781393c1a8e49aee0ccc95` есть и то же пояснение инструкции, и тот же запрет delete меток у console. Свидетельства: `final-baseline-0/1.stdout`, `final-baseline.json`; начальное происхождение не установлено.

**Проба:** `authorization_probe.py`, протокол `authorization-probe-commands.json/.stdout/.stderr`, exit 0. Это конечная модель данных и аргументов примера, не запуск реализации.

## М10/2

### R39-02 — мелкая: инструкция готовности осталась на 25 id после добавления М10/2-26

**Места:** `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md:9`, `:110`; `Source/tests/testdata/acceptance/М10_Platform/02/README.md:71`. Канон: `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:398`, М10/2-26.

**Противоречие и контрпример.** Инструкция требует закрыть М10/2-01…25, а её критерий готовности прямо называет «Все 25 пунктов». Между тем в каноне 26-й пункт: обязательность unit/rows/id и допустимость минимальной numeric-спеки. Таблица свидетельств реализации с закрытыми ровно первыми 25 id удовлетворяет написанному диапазону инструкции, но не полному нормативному чеклисту. README приёмки также оставляет старый диапазон.

Это ошибка диапазона готовности, **не** утверждение об отсутствии четырёх новых файлов приёмки: инструкция уже называет 255 файлов, и новые вердикты присутствуют.

**Основание и последствия.** ADR-0080, дополнение (3), пункт 4 (`decisions/0080-лекции-как-спецификации.md:116`), и module-design:91–92 требуют полного соответствия инструкции нормативному чеклисту. Теряется явная трассировка готовности по М10/2-26, при сохранённом каноне и самих тестовых данных.

**Рекомендация:** согласовать оба диапазона и число пунктов с актуальным чеклистом, включая М10/2-26.

**Происхождение:** наведена исправлением 38, коммит `6bb05ef81da2be23a299deb0bdc3a05ecd88063d`. Его diff добавляет М10/2-26 в norms, но не меняет диапазон инструкции. До него и на `294ca6c5` нормы заканчивались 25-м id, инструкция соответствовала этому числу. Доказательства до/после: `provenance-unit26-diff.json/.stdout`, `unit26-parent-instruction.json/.stdout`, `final-baseline-2/3.stdout`.

### R39-03 — существенная: group_by_unknown_field проверяет неверную форму вместо заявленной ссылки

**Места:** `Source/tests/testdata/acceptance/М10_Platform/02/cases/group_by_unknown_field.subsystem.yaml:15`; `02/verdicts.tsv:76` (путь относительно того же каталога приёмки). Заявленное покрытие — `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:322`, М10/2-07 (`:376`). Форма владельца — `М10_Platform/spec/04-the-controller-and-placement.norms.md:77`. Урок 4 здесь — зависимое основание, самостоятельной находки в нём нет.

**Противоречие.** Файл содержит скаляр `group_by: nosuch`. Нормативная форма — `group_by: {field, cut_at}`, а ссылка из Н1.4 — `placement.group_by.field`. Н5 относит этот случай к проверке ссылок между ключами. Скаляр уже неверен по форме и не достигает проверки имени поля.

**Воспроизводимый контрпример покрытию.** Загрузчик, который отказывает скаляру, но ошибочно принимает любую строку в `group_by.field`, проходит опубликованный `refused` для этого случая. Для целевой отрицательной пробы достаточно заменить только строку 15 на `group_by: {field: nosuch}` при прежнем корректном фоне: поле nosuch не объявлено и должно отказать по ссылке. Положительный сосед с `group_by: {field: name}` проходит именно эту проверку ссылки. Исходная скалярная форма не является допустимым положительным входом; находка касается ложного покрытия отрицательного требования, а не обязанности её принять.

**Основание и последствия.** Н1.4 урока 2 (`:133`, `:138`) требует разрешать объявленные ссылки при загрузке; ADR-0080:31–33, дополнение (3):116–118 требуют приёмку заявленной нормы. Проверка синтаксической формы вместо ссылки позволяет пропустить дефект М10/2-07. В прочитанных разбираемых случаях остальные placement.group_by — 37 отображений с существующим feed; скаляр nosuch единственный. Восьми неразбираемым специальным файлам дополнительный каталоговый скрипт PASS не приписывает.

**Рекомендация:** сделать целевой случай отображением с неизвестным field и добавить положительный сосед; скаляр при желании оставить отдельным отказом формы.

**Происхождение:** была до исправлений 38: тот же скаляр имеется на `294ca6c5` (`old-groupby.json/.stdout`). Первоначальная правка, породившая случай, не устанавливалась.

**Пробы:** `groupby_probe.py` и `groupby_catalogue.py`, протоколы `groupby-probe.*` и `groupby-catalogue.*`, exit 0; варианты `reference_negative.subsystem.yaml`, `positive.subsystem.yaml` сохранены вне репозитория. Это чтение данных и модель формы/ссылки, не исполнение штатного загрузчика и не доказательство общего ok всех свойств положительного файла.

## М10/3–11

Других подтверждённых причин в выполненной части обзора не зафиксировано. Нули ниже не означают завершённого полного обзора всех материалов этих уроков. Зависимая норма М10/6 использована в R39-01, форма М10/4 — в R39-03; причины не размножены по урокам.

## Lesson-spec

### R39-04 — существенная: YAML 1.1 merge остался в загрузчике заявленного YAML 1.2 Core

**Места:** `.claude/skills/lesson-spec/references/validation.md:13`; `.claude/skills/lesson-spec/scripts/check_spec.py:31`, `:33`, `:63`.

**Противоречие.** Инструмент обещает JSON-совместимый YAML 1.2 Core. Перенастройка SafeLoader убирает резолверы bool/int/float/timestamp, но оставляет неявный merge; `flatten_mapping` применяет его. В Core обычный скаляр `<<` — строка, как и кавыченный `"<<"`, а не команда слияния. Это следует из [YAML 1.2.2 §10.3.2](https://yaml.org/spec/1.2.2/#1032-tag-resolution): для скаляра, не совпавшего с перечисленными типами, применяется строковый тип.

**Минимальный разрешённый вход.** Полный OpenAPI из `property-plain.yaml`:

```yaml
openapi: 3.1.0
info: {title: Probe, version: '1'}
paths:
  /example:
    get:
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: {type: object, properties: {<<: {type: string}}}
```

Это схема объекта с единственным строковым свойством `<<`, без aliases или нестандартных тегов. На ней проверка получает `properties: {type: string}` после чтения и отказывает: `'string' is not of type 'object', 'boolean'`. При одной замене имени на `"<<"` тот же контракт проходит. Для аналогичного `example: {<<: {type: string}}` обе записи получают PASS, но проверяемое значение незаметно меняется: из `{"<<":{"type":"string"}}` в `{"type":"string"}`.

**Основание и последствия.** Нарушено собственное объявление validation.md:13; ADR-0080 различает контракт и инструмент его проверки. Здесь нет требования поддержать заведомо исключённый формат: вход входит в объявленный Core-профиль и использует только JSON-типы. Получаются ложный FAIL допустимой схемы и PASS над изменёнными данными примера. Одна причина — унаследованная семантика merge.

**Рекомендация:** убрать неявное разрешение merge из Core-загрузчика и проверить эквивалентность обычного/кавыченного строкового `<<` в свойствах и данных примера.

**Происхождение:** была до исправлений 38: загрузчик на `294ca6c5` так же превращает обычный `<<` в слияние (`provenance-probes.json/.stdout`, сохранённый `old-check_spec.py`). Первое возникновение причинно не устанавливалось; одна дата blame не выдаётся за происхождение.

**Проба:** `merge_probe.py`, четыре полных внешних контракта `merge-plain.yaml`, `merge-quoted.yaml`, `property-plain.yaml`, `property-quoted.yaml`; протокол `merge-probe-property.json/.stdout/.stderr`, exit 0 означает подтверждение утверждений самой пробы, а не PASS всех четырёх контрактов. Выполняется только разрешённый проверяющий инструмент навыка. Веб-источник сохранён как `yaml-official-web.json` и `yaml-core-table-web.json`.

## Сводка по областям

| Область | Блокеры | Существенные | Мелкие | Причины и граница результата |
|---|---:|---:|---:|---|
| М10/1 | 0 | 0 | 1 | R39-01 |
| М10/2 | 0 | 1 | 1 | R39-02, R39-03; cases рассмотрены представлением дельт |
| М10/3 | 0 | 0 | 0 | Полный семантический обзор OpenAPI не заявлен |
| М10/4 | 0 | 0 | 0 | Зависимость R39-03; полный семантический обзор OpenAPI не заявлен |
| М10/5 | 0 | 0 | 0 | Собственного OpenAPI по ADR нет |
| М10/6 | 0 | 0 | 0 | Зависимость R39-01; общий JSON прав рассмотрен выборочно |
| М10/7 | 0 | 0 | 0 | secret_in.tsv не прочитан; собственного OpenAPI по ADR нет |
| М10/8 | 0 | 0 | 0 | OpenAPI рассмотрен нормализованным представлением |
| М10/9 | 0 | 0 | 0 | OpenAPI только структурно и выборочно, не полностью семантически |
| М10/10 | 0 | 0 | 0 | OpenAPI только структурно, не полностью семантически |
| М10/11 | 0 | 0 | 0 | OpenAPI только структурно, не полностью семантически |
| module-design / README модуля | 0 | 0 | 0 | Тексты рассмотрены |
| lesson-spec | 0 | 1 | 0 | R39-04 |
| Общие данные / GLOSSARY | 0 | 0 | 0 | Неполный просмотр, не независимый нулевой результат |
| Межурочные отдельные причины | 0 | 0 | 0 | Зависимости R39-01/03 уже посчитаны у владельцев причины |
| **Всего уникальных причин** | **0** | **2** | **2** | **4; полный прогон не завершён** |

По происхождению: три причины были на срезе до исправлений 38; одна наведена исправлением 38 (R39-02, доказанный коммит указан выше).

Три наиболее важные: R39-04 — проверяется изменённый контракт/пример; R39-03 — приёмка не достигает заявленной проверки ссылки; R39-01 — пример проверки прав теряет различие разрешений. R39-02 остаётся ошибкой диапазона готовности.

## Реальные проверки, доказательства и ограничения

Все пути логов ниже относятся к `/private/tmp/review-spec-39-codex-logs/`. Для командных проверок сохранены точные argv, cwd, exit code и отдельные stdout/stderr в одноимённых `.json`, `.stdout`, `.stderr`. Генераторы проб лежат там же; результаты прошлых прогонов не выдаются за эти выполнения.

| Проверка, реально выполненная в 39 | Результат и предел доказательства | Протокол / генератор |
|---|---|---|
| Тесты lesson-spec: `/Users/murat/.cache/uv/archive-v0/9uaCiHCYONoJQ5u4/bin/python -I -B -m unittest discover -s .claude/skills/lesson-spec/scripts -p test_check_spec.py` | 52 теста, OK, exit 0; не исключает найденную непокрытую ветвь merge | `unittest.*` |
| Текущий CLI навыка с позиционными путями лекций 01 и 02 | exit 0, только structural PASS; 23 сценария, 105 шагов, 255 вердиктов, 13 диагностик, 49 id | `cli-01-02.*` |
| Девять действительных OpenAPI файлов через `Check.openapi` текущего навыка | Ошибок нет, 9 документов, 1068 локальных ссылок; это структурная проверка, не семантический PASS | `api-scan.*`, `api_scan.py` |
| Сравнение копий компонентов с владельцами после снятия префикса ссылок M<n>_ | 100 копий, несовпадений нет; не доказывает совпадение всех маршрутов и алгоритмов | `copies.*`, `copy_check.py` |
| Представления полных JSON-объектов API и проверенных копий | Подготовлены; семантически прочитаны не все представления, как отмечено в manifest | `api-view.*`, `api_view.py`, `api-view-manifest.json` |
| Чтение 255 cases относительно свежего общего фона | Все дельты выведены, повторяющаяся глубокая структура сверена формулой; не полное построчное чтение всех исходных файлов | `cases-view-chain.*`, `case-diff-a.*`…`case-diff-e.*`, `case-depth.*`, `cases_view.py`, `case-differences-manifest.json` |
| Четыре собственные целевые пробы и происхождение | Свидетельства приведены в находках; модели не являются запуском загрузчика/прав/HTTP | `authorization-probe-commands.*`, `groupby-probe.*`, `groupby-catalogue.*`, `merge-probe-property.*`, `final-baseline.*`, `provenance-unit26-diff.*` |

Неуспешные подготовительные команды также сохранены и не объявляются PASS: первая проба прав выбрала другой ключ и завершилась assert (`authorization-probe`, exit 1), после чего для приведённого контрпримера выполнена отдельная успешная проба; первый вывод README01 не смог записать свой manifest из-за `__file__` (`acc01-all`, exit 1), позднее повторён штатным read.py (`a01-readme-recorded`, exit 0). Поиск с неверным предполагаемым именем ADR (`final-rule-quotes`, exit 2) заменён чтением существующего файла; этот неуспех не доказывает отсутствия ADR.

**Незавершённый охват.** Семантическое чтение девяти больших/общих файлов не выполнено: семь `Source/vms/*.subsystem.yaml`, `Source/deploy/cluster/configstore-rights.json.md`, `acceptance/М10_Platform/07/secret_in.tsv`. `GLOSSARY.md` и основной JSON прав рассмотрены выборочно. У ADR-0082 просмотрены лишь отдельные места, а не все дополнения до 33; первоначальный большой вывод СЕССИИ и объединённый вывод правил были усечены, позднее перечитаны нужные основания, что не делает их полным чтением. API03/04 не получают полного семантического PASS из-за неполного просмотра нормализованных выводов; API09–11 полностью семантически не пройдены. Поэтому весь заказанный независимый прогон не исполнен, даже при свежем просмотре текстов всех одиннадцати лекций, норм и инструкций.

Точный перечень всех 359 core-файлов, размеры, SHA-256 и способ фактического рассмотрения каждого сохранены в `final-read-manifest.json`. `read-manifest.jsonl` фиксирует диапазоны, выведенные командами, а не гарантирует чтение усечённого ответа; это ограничение явно записано в итоговом manifest. Сводка ниже не приравнивает представление дельт или структурную проверку к полному чтению.

Полный CLI приёмок 03–11 **не запускался**: формат не поддержан по validation.md. HTTP/процессы, штатный загрузчик, криптография, часы, файловая система, fsync и кластер **не запускались и не проверены исполнением**. Код реализаций и продуктовые тесты не читались/не импортировались/не запускались. Материалы курса и чужие деревья не исправлялись; единственный итоговый файл в ветке — этот отчёт.

## Фактический manifest core-охвата

Ниже пути из инвентаризации собственного точного среза, а не восстановленные названия по прежним отчётам. Все 255 индивидуальных путей cases перечислены во внешнем `final-read-manifest.json`; в печатной таблице они объединены только ради размера отчёта.

| Файл core-охвата | Фактический способ рассмотрения |
|---|---|
| `.claude/skills/lesson-spec/SKILL.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/assets/api.openapi.yaml` | текстовый семантический проход |
| `.claude/skills/lesson-spec/assets/instructions.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/assets/lecture.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/assets/norms.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/references/change-map.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/references/review-checklist.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/references/templates.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/references/validation.md` | текстовый семантический проход |
| `.claude/skills/lesson-spec/scripts/check_spec.py` | текстовый семантический проход |
| `.claude/skills/lesson-spec/scripts/test_check_spec.py` | текстовый семантический проход |
| `GLOSSARY.md` | выборочно / поиск — полного чтения словаря нет |
| `Source/deploy/cluster/configstore-rights.json` | выборочно / модель данных — console и camcontroller; не полный JSON |
| `Source/deploy/cluster/configstore-rights.json.md` | не прочитан семантически |
| `Source/tests/testdata/acceptance/М10_Platform/01/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/01/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/01/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/02/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/02/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/02/diagnostics.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/03/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/03/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/03/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/04/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/04/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/04/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/05/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/05/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/05/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/06/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/06/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/06/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/07/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/07/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/07/log_mask.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/07/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/07/secret_in.tsv` | не прочитан семантически — 443 строки не прочитаны в этом исполнении |
| `Source/tests/testdata/acceptance/М10_Platform/08/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/08/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/08/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/09/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/09/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/09/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/10/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/10/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/10/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/11/README.md` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/11/corrections.tsv` | текстовый семантический проход |
| `Source/tests/testdata/acceptance/М10_Platform/11/scenarios.tsv` | текстовый семантический проход |
| `Source/tests/testdata/platform_lists.tsv` | текстовый семантический проход |
| `Source/tests/testdata/testsub.subsystem.yaml` | текстовый семантический проход |
| `Source/tests/testdata/testsub2.subsystem.yaml` | текстовый семантический проход |
| `Source/vms/auto.subsystem.yaml` | не прочитан семантически |
| `Source/vms/cam.subsystem.yaml` | не прочитан семантически |
| `Source/vms/det.subsystem.yaml` | не прочитан семантически |
| `Source/vms/detjob.subsystem.yaml` | не прочитан семантически |
| `Source/vms/live.subsystem.yaml` | не прочитан семантически |
| `Source/vms/rec.subsystem.yaml` | не прочитан семантически |
| `Source/vms/survey.subsystem.yaml` | не прочитан семантически |
| `М10_Platform/01-storage.md` | текстовый семантический проход |
| `М10_Platform/02-the-spec-and-the-strict-loader.md` | текстовый семантический проход |
| `М10_Platform/03-units-slots-epochs-lease.md` | текстовый семантический проход |
| `М10_Platform/04-the-controller-and-placement.md` | текстовый семантический проход |
| `М10_Platform/05-the-worker-under-its-slot.md` | текстовый семантический проход |
| `М10_Platform/06-rights.md` | текстовый семантический проход |
| `М10_Platform/07-secrets-and-sealing.md` | текстовый семантический проход |
| `М10_Platform/08-events-resource-requests.md` | текстовый семантический проход |
| `М10_Platform/09-the-console.md` | текстовый семантический проход |
| `М10_Platform/10-schema-drain-snapshot-limits.md` | текстовый семантический проход |
| `М10_Platform/11-the-platform-on-a-box-and-a-cluster.md` | текстовый семантический проход |
| `М10_Platform/README.md` | текстовый семантический проход |
| `М10_Platform/module-design.md` | текстовый семантический проход |
| `М10_Platform/spec/01-storage.README.md` | текстовый семантический проход |
| `М10_Platform/spec/01-storage.api.openapi.yaml` | текстовый семантический проход |
| `М10_Platform/spec/01-storage.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md` | текстовый семантический проход |
| `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml` | текстовый семантический проход |
| `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/03-units-slots-epochs-lease.README.md` | текстовый семантический проход |
| `М10_Platform/spec/03-units-slots-epochs-lease.api.openapi.yaml` | частично нормализованное представление — были усечённые выводы, полный семантический PASS не заявлен |
| `М10_Platform/spec/03-units-slots-epochs-lease.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/04-the-controller-and-placement.README.md` | текстовый семантический проход |
| `М10_Platform/spec/04-the-controller-and-placement.api.openapi.yaml` | частично нормализованное представление — были усечённые выводы, полный семантический PASS не заявлен |
| `М10_Platform/spec/04-the-controller-and-placement.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/05-the-worker-under-its-slot.README.md` | текстовый семантический проход |
| `М10_Platform/spec/05-the-worker-under-its-slot.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/06-rights.README.md` | текстовый семантический проход |
| `М10_Platform/spec/06-rights.api.openapi.yaml` | полное нормализованное представление — api-view.py; не чтение исходного YAML строка за строкой |
| `М10_Platform/spec/06-rights.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/07-secrets-and-sealing.README.md` | текстовый семантический проход |
| `М10_Platform/spec/07-secrets-and-sealing.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/08-events-resource-requests.README.md` | текстовый семантический проход |
| `М10_Platform/spec/08-events-resource-requests.api.openapi.yaml` | полное нормализованное представление — api-view.py; не чтение исходного YAML строка за строкой |
| `М10_Platform/spec/08-events-resource-requests.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/09-the-console.README.md` | текстовый семантический проход |
| `М10_Platform/spec/09-the-console.api.openapi.yaml` | только структурная проверка — семантическое чтение полного OpenAPI не закончено |
| `М10_Platform/spec/09-the-console.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/10-schema-drain-snapshot-limits.README.md` | текстовый семантический проход |
| `М10_Platform/spec/10-schema-drain-snapshot-limits.api.openapi.yaml` | только структурная проверка — семантическое чтение полного OpenAPI не закончено |
| `М10_Platform/spec/10-schema-drain-snapshot-limits.norms.md` | текстовый семантический проход |
| `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.README.md` | текстовый семантический проход |
| `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml` | только структурная проверка — семантическое чтение полного OpenAPI не закончено |
| `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md` | текстовый семантический проход |
| Все 255 путей `Source/tests/testdata/acceptance/М10_Platform/02/cases/` (точный список: внешний manifest) | представление дельт; не полное построчное чтение исходных файлов |

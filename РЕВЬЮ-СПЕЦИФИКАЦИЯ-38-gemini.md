# Ревью спецификации М10_Platform — Прогон 38 (Gemini)

- **Ревьювер:** Gemini (`gemini`, независимое окно `term_5c937cd3-57e9-4590-a975-c7346d259d35`)
- **Роль:** «Ревью спецификации» (третий независимый ревьювер вместе с Codex и Kimi)
- **Проверяемый коммит `main`:** `294ca6c59cf871f05d781393c1a8e49aee0ccc95`
- **Рабочее дерево ревью:** `/Users/murat/w2c/wt-review-spec-38-gemini` (ветка `gemini/review-spec-38-gemini`)
- **Каталог живых логов проверок:** `/private/tmp/review-spec-38-gemini-logs`
- **Дата:** 2026-10-16

---

## 1. Сводка

### 1.1. Таблица находок по срезу прогона 38

Одна корневая причина оформлена одной находкой (`G38-01`, `G38-02`). Межмодульная находка `G38-02` учтена в строке каждого затронутого урока с пометой `(общая G38-02)`, а в строке «Итого уникальных находок» посчитана один раз.

| Срез / Урок | S0 | S1 | S2 | S3 | Находки | Вердикт по срезу |
|---|---:|---:|---:|---:|---|---|
| **Урок 01** (`01-storage`) | 0 | 0 | 0 | 1 | `G38-01` | PASS с замечанием S3 |
| **Урок 02** (`02-the-spec-and-the-strict-loader`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 03** (`03-units-slots-epochs-lease`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 04** (`04-the-controller-and-placement`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 05** (`05-the-worker-under-its-slot`) | 0 | 0 | 0 | 0 | — | PASS |
| **Урок 06** (`06-rights`) | 0 | 0 | 0 | 0 | — | PASS |
| **Урок 07** (`07-secrets-and-sealing`) | 0 | 0 | 0 | 0 | — | PASS |
| **Урок 08** (`08-events-resource-requests`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 09** (`09-the-console`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 10** (`10-schema-drain-snapshot-limits`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **Урок 11** (`11-the-platform-on-a-box-and-a-cluster`) | 0 | 0 | 0 | 1 | `G38-02` (общая) | PASS с замечанием S3 |
| **`GLOSSARY.md`** | 0 | 0 | 0 | 0 | — | PASS |
| **`М10_Platform/module-design.md`** | 0 | 0 | 0 | 0 | — | PASS |
| **Скилл `.claude/skills/lesson-spec/*` + общие данные `Source/tests/testdata/*`** | 0 | 0 | 0 | 0 | — | PASS |
| **Итого уникальных находок** | **0** | **0** | **0** | **2** | **`G38-01`, `G38-02`** | **PASS с замечаниями (0 S0, 0 S1, 0 S2, 2 S3)** |

### 1.2. Выполненные команды и пути живых логов

Все перечисленные ниже команды были реально выполнены в текущей сессии на коммите `294ca6c59cf871f05d781393c1a8e49aee0ccc95` в рабочем дереве `/Users/murat/w2c/wt-review-spec-38-gemini`, а их stdout/stderr и коды возврата сохранены в `/private/tmp/review-spec-38-gemini-logs/`:

1. **Проверка рабочего дерева и фиксация целевого коммита:**
   - Команды: `git worktree list`, `git rev-parse 294ca6c59cf871f05d781393c1a8e49aee0ccc95^{commit}`, `git worktree add -B gemini/review-spec-38-gemini /Users/murat/w2c/wt-review-spec-38-gemini 294ca6c59cf871f05d781393c1a8e49aee0ccc95`, `git rev-parse HEAD`
   - Результат: `HEAD = 294ca6c59cf871f05d781393c1a8e49aee0ccc95`, `EXIT_CODE=0`
   - Логи:
     - `/private/tmp/review-spec-38-gemini-logs/00-worktree-list.log`
     - `/private/tmp/review-spec-38-gemini-logs/01-target-sha.log`
     - `/private/tmp/review-spec-38-gemini-logs/02-worktree-add.log`
     - `/private/tmp/review-spec-38-gemini-logs/03-head-sha.log`

2. **Штатный структурный чекер `check_spec.py` на уроке 01:**
   - Команда: `/Users/murat/.cache/uv/archive-v0/9uaCiHCYONoJQ5u4/bin/python -I -B .claude/skills/lesson-spec/scripts/check_spec.py "М10_Platform/01-storage.md"`
   - Вывод:
     ```text
     COUNTS lessons=1 local_links=14 local_refs=50 norm_ids=23 openapi=1 scenarios=23 steps=105
     PASS structural checks only; semantic review and implementation acceptance remain separate
     EXIT_CODE=0
     ```
   - Лог: `/private/tmp/review-spec-38-gemini-logs/10-check-spec-01.out`

3. **Штатный структурный чекер `check_spec.py` на уроке 02:**
   - Команда: `/Users/murat/.cache/uv/archive-v0/9uaCiHCYONoJQ5u4/bin/python -I -B .claude/skills/lesson-spec/scripts/check_spec.py "М10_Platform/02-the-spec-and-the-strict-loader.md"`
   - Вывод:
     ```text
     COUNTS diagnostics=13 lessons=1 local_links=20 local_refs=33 norm_ids=25 openapi=1 verdicts=234
     PASS structural checks only; semantic review and implementation acceptance remain separate
     EXIT_CODE=0
     ```
   - Лог: `/private/tmp/review-spec-38-gemini-logs/11-check-spec-02.out`

4. **Модульные тесты скилла `test_check_spec.py`:**
   - Команда: `/Users/murat/.cache/uv/archive-v0/9uaCiHCYONoJQ5u4/bin/python -I -B -m unittest discover -s .claude/skills/lesson-spec/scripts -p "test_*.py" -v`
   - Вывод: `Ran 49 tests in 14.396s`, `OK`, `EXIT_CODE=0`
   - Лог: `/private/tmp/review-spec-38-gemini-logs/12-unittest-check-spec.out`

5. **Запуск `check_spec.py` на уроках 03–11:**
   - Команда: цикл по `М10_Platform/03-units-slots-epochs-lease.md` … `М10_Platform/11-the-platform-on-a-box-and-a-cluster.md` с вызовом `/Users/murat/.cache/uv/archive-v0/9uaCiHCYONoJQ5u4/bin/python -I -B .claude/skills/lesson-spec/scripts/check_spec.py "$f"`
   - Результат: для всех уроков 03–11 `EXIT_CODE=1` (ожидаемо по архитектуре `check_spec.py`: в `03–11/scenarios.tsv` используются расширенные сценарные директивы `@key`, `@as`, `@until`, `@start`, `console`/`store`/`resource`, `@manual`, у уроков 05 и 07 по доп. 13/14 ADR-0082 нет `.api.openapi.yaml`, а в `07/` лежат таблицы `log_mask.tsv` и `secret_in.tsv`). При этом по результатам прогона подтверждено **0 ошибок** структуры Markdown, заголовков, чеклистов `М10/N-XX`, локальных ссылок и OpenAPI 3.1 в уроках 03, 04, 06, 08, 09, 10, 11.
   - Логи:
     - `/private/tmp/review-spec-38-gemini-logs/13-check-spec-03-to-11.out` (полный вывод)
     - `/private/tmp/review-spec-38-gemini-logs/14-check-spec-03-to-11-summary.out` (сводка `COUNTS`/`FAIL` и ошибок отсутствия OpenAPI у 05/07)

6. **Read-only Python-пробы ссылок, OpenAPI-контрактов, межконтрактного паритета `M1_..M9_` и таблиц приёмки:**
   - `/private/tmp/review-spec-38-gemini-logs/15-deep-audit.out` (`EXIT_CODE=0`): подсчёт сценариев и шагов во всех `acceptance/01–11` и поиск всех упоминаний количеств сценариев/шагов/вердиктов по текстам уроков, норм, README и приёмки.
   - `/private/tmp/review-spec-38-gemini-logs/16-schema-and-tsv-audit.out` (`EXIT_CODE=0`): проверка всех Markdown-ссылок и `#anchor` по всему срезу (0 битых ссылок в рабочих файлах; шаблонные плейсхолдеры `{{...}}` только в `.claude/skills/lesson-spec/assets/*.md`), прямая проверка `check_spec.Check(ROOT).openapi(...)` для всех 9 файлов `.api.openapi.yaml` (`errors=0` у всех 9 файлов), покомпонентная сверка всех дублируемых схем `M1_..M9_` против урока-владельца (0 структурных расхождений).
   - `/private/tmp/review-spec-38-gemini-logs/17-deep-contract-audit.out` (`EXIT_CODE=0`): сверка `components.responses.M*` и инспекция всех заголовков (`headers`) во всех 9 файлах `.api.openapi.yaml` (обнаружена находка `G38-02`).
   - `/private/tmp/review-spec-38-gemini-logs/18-acceptance-data-audit.out` (`EXIT_CODE=0`): проверка `corrections.tsv` во всех уроках 01–11 и проверка `strict_json` (с запретом дублирующихся ключей JSON) на всех JSON-телах `request`/`expect` в `01, 03–11/scenarios.tsv` (0 ошибок JSON).
   - `/private/tmp/review-spec-38-gemini-logs/19-openapi-consistency-probe.out` (`EXIT_CODE=0`): проверка всех путей, методов, `servers` и паритета `GET` против `HEAD` (коды ответов, заголовки, параметры) во всех 9 файлах `.api.openapi.yaml` (0 расхождений между `GET` и `HEAD`).
   - `/private/tmp/review-spec-38-gemini-logs/20-verdicts-and-lists-audit.out` (`EXIT_CODE=0`): проверка `02/verdicts.tsv` (234 случая: 37 `ok`, 197 `refused`, полное совпадение множества с `02/cases/*.subsystem.yaml`), `02/diagnostics.tsv` (13 строк, все `refused`), `07/log_mask.tsv` (19 строк, 3 колонки `raw`, `masked`, `note`), `07/secret_in.tsv` (420 строк: 131 принятая, 289 отказов, 5 колонок `field`, `raw`, `masked`, `fault`, `note`), `Source/tests/testdata/platform_lists.tsv` (37 строк, 2 колонки `list`, `value`), а также парсинга `testsub.subsystem.yaml` и `testsub2.subsystem.yaml`.

7. **Что не запускалось (явная фиксация):**
   - Код продукта и реализации курса (`Source/**/*.py`, Go/C++ и их тесты), а также живые HTTP-стенды/демоны **не запускались** и не читались в соответствии с правилами изоляции ревью спецификации.

---

## 2. Подробные находки

### `G38-01` [S3 · Sync · Урок 1] В `М10_Platform/spec/01-storage.README.md` не обновлён диапазон сценариев (`01–22` вместо `01–23`) и таблица ловушек после добавления сценария 23 (`K37-05`)

- **Серьёзность:** `S3` (рассинхронизация инструкции для реализации `.README.md` с каноном `.norms.md` и данными приёмки `01/scenarios.tsv`, `01/README.md`)
- **Тип:** `Sync` (Нормы ↔ Инструкция `.README.md` ↔ Приёмка)
- **Затронутые файлы:**
  - `М10_Platform/spec/01-storage.README.md` (строки 48, 69, 74)
  - `М10_Platform/spec/01-storage.norms.md` (строки 111–114, 265, 304–305)
  - `Source/tests/testdata/acceptance/М10_Platform/01/scenarios.tsv` (строки 102–107)
  - `Source/tests/testdata/acceptance/М10_Platform/01/README.md` (строки 58–65)

- **Суть и доказательство (точные цитаты):**
  В рамках закрытия `K37-05` в урок 1 был добавлен сценарий 23 (`23-extra-cmd`, 6 шагов; всего в `01/scenarios.tsv` стало 23 сценария и 105 шагов):
  1. В `М10_Platform/spec/01-storage.norms.md:111-114` зафиксирована норма Н2 про лишние поля верхнего уровня команды `POST /v1/write`, в таблицу Н5 (`01-storage.norms.md:265`) добавлена строка:
     > `| 23 | лишние поля команды не читаются и не входят в отпечаток put/delete; guard остаётся закрытым по сц. 20 | Н2, id |`
     а в чеклисте `М10/1-11` и `М10/1-12` (`01-storage.norms.md:304-305`) добавлены ссылки на `сц. 23`.
  2. В `Source/tests/testdata/acceptance/М10_Platform/01/scenarios.tsv:102-107` добавлены 6 шагов сценария `23-extra-cmd`, а в `Source/tests/testdata/acceptance/М10_Platform/01/README.md:58-65` — раздел `## Лишние поля команды (K37-05)`.
  3. Однако инструкция реализации `М10_Platform/spec/01-storage.README.md` осталась со старым диапазоном сценариев `01–22`:
     - `М10_Platform/spec/01-storage.README.md:48`:
       > `5. Подготовить экземпляры по README приёмки: потолок строки 524288 байт, предел тела 1048576 байт. Прогнать сценарии 01–22. Каждое падение — сверить с 01-storage.norms.md, исправить **код**.`
     - `М10_Platform/spec/01-storage.README.md:74`:
       > `- [ ] сценарии 01–22 зелёные через дверь, включая порядок имён в keys по README приёмки;`
     - Кроме того, в таблице `## Ловушки, которые зависят от языка` (`М10_Platform/spec/01-storage.README.md:69`) строка:
       > `| items у delete не читается (Н2) | строгий разбор тела отвергает лишнее поле | разбирать Cmd терпимо к items у delete |`
       упоминает только `items` у `delete`, не отражая общую норму Н2 (`01-storage.norms.md:111-114`) о том, что любые лишние поля верхнего уровня `Cmd` (`POST /v1/write`, как `put`, так и `delete`) принимаются без чтения и не входят в отпечаток `id` (при сохранении закрытости `guard`).

- **Минимальное направление исправления:**
  В `М10_Platform/spec/01-storage.README.md` обновить диапазон сценариев с `01–22` на `01–23` в строках 48 и 74, а в строке 69 таблицы ловушек уточнить, что помимо `items` у `delete` команда `Cmd` (`POST /v1/write`) терпима к любым лишним полям верхнего уровня без включения их в отпечаток `id` (в отличие от закрытого объекта `guard`).

---

### `G38-02` [S3 · OpenAPI · Уроки 2, 3, 4, 8, 9, 10, 11] Несогласованный тип схемы заголовка `Retry-After` (`type: string, const: '1'` против `const: '1'` против `type: integer, const: 1`) в ответах `503` между контрактами `.api.openapi.yaml` и внутри `10-schema-drain-snapshot-limits.api.openapi.yaml`

- **Серьёзность:** `S3` (внутренний разнобой представления одного и того же HTTP-заголовка `Retry-After: 1` в OpenAPI 3.1 контрактах)
- **Тип:** `OpenAPI` (межконтрактная и внутриконтрактная консистентность схем заголовков)
- **Затронутые файлы:**
  - `М10_Platform/spec/10-schema-drain-snapshot-limits.api.openapi.yaml` (строки 133–137, 165–169, 202–206, 1393–1397 и др.)
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml` (строки 408–412)
  - `М10_Platform/spec/03-units-slots-epochs-lease.api.openapi.yaml` (строки 414–416, 425–427)
  - `М10_Platform/spec/04-the-controller-and-placement.api.openapi.yaml` (строки 888–892)
  - `М10_Platform/spec/08-events-resource-requests.api.openapi.yaml` (строки 231–234 и аналогичные блоки `503`)
  - `М10_Platform/spec/09-the-console.api.openapi.yaml` (строки 37–41, 86–90 и остальные маршруты консоли)
  - `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml` (строки 49–53 и остальные маршруты `503`)

- **Суть и доказательство (точные цитаты):**
  Во всех перечисленных контрактах ответ `503` при перегрузке полосы (`busy`) возвращает один и тот же HTTP-заголовок `Retry-After: 1` (в частности, для маршрутов одной и той же двери консоли по норме М10/9 Н4). Однако его JSON Schema в OpenAPI 3.1 задана тремя разными способами, причём в файле урока 10 два разных типа смешаны прямо внутри одного документа:
  1. **Строковый тип (`type: string, const: '1'`)** в уроках 2, 3, 4 и в части маршрутов урока 10 (`/drain`):
     - `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml:408-412` (`components.responses.Unavailable`):
       ```yaml
       Retry-After:
         description: Обязателен со значением 1 при busy; не обещан для остальных причин.
         schema:
           type: string
           const: '1'
       ```
     - `М10_Platform/spec/03-units-slots-epochs-lease.api.openapi.yaml:414-416` (`Unavailable`) и `425-427` (`WriteUnavailable`):
       ```yaml
       Retry-After:
         description: Обязателен со значением 1 при busy; не обещан для остальных причин.
         schema: {type: string, const: "1"}
       ```
     - `М10_Platform/spec/04-the-controller-and-placement.api.openapi.yaml:888-892` (`Unavailable`):
       ```yaml
       Retry-After:
         description: Обязателен со значением 1 при busy; не обещан для остальных причин.
         schema:
           type: string
           const: '1'
       ```
  2. **Строковая константа без `type` (`const: '1'`)** в уроке 8:
     - `М10_Platform/spec/08-events-resource-requests.api.openapi.yaml:231-234` (`GET /events` `503`, а также `GET /events/wait`, `POST /marks`, `POST /{sub}/requests`, `DELETE /{sub}/asked/{sha16}`):
       ```yaml
       Retry-After:
         description: При busy обязателен со значением 1.
         schema:
           const: '1'
       ```
  3. **Целочисленный тип (`type: integer, const: 1`)** в уроках 9, 11 и в остальных маршрутах урока 10 (`/schema`, `/{rows}/{id}/{blob_field}`, `/{table}`, `/{table}/{name}`):
     - `М10_Platform/spec/09-the-console.api.openapi.yaml:37-41` (`GET /` `503` и все остальные маршруты консоли в уроке 9):
       ```yaml
       Retry-After:
         schema:
           type: integer
           const: 1
         description: Обязателен для error=busy, не обещает срок восстановления прочих отказов.
       ```
     - `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml:49-53` (`GET /v1/status` `503` и остальные маршруты `503` в уроке 11):
       ```yaml
       Retry-After:
         schema:
           type: integer
           const: 1
         description: Обязателен только для busy; остальные 503 не обещают срок.
       ```
  4. **Внутриконтрактное смешение в `М10_Platform/spec/10-schema-drain-snapshot-limits.api.openapi.yaml`:**
     - У `HEAD /drain` (`10-schema-drain-snapshot-limits.api.openapi.yaml:133-137`) и `components.responses.M4_Unavailable` (`10-schema-drain-snapshot-limits.api.openapi.yaml:1393-1397`, на который ссылаются `GET /drain`, `POST /drain`, `DELETE /drain`) заголовок описан как строка:
       ```yaml
       Retry-After:
         description: Обязателен со значением 1 при busy; не обещан для остальных причин.
         schema:
           type: string
           const: '1'
       ```
     - В том же самом файле у `GET /schema` (`10-schema-drain-snapshot-limits.api.openapi.yaml:165-169`), `PUT /schema` (`202-206`), `HEAD /schema`, `PUT /{rows}/{id}/{blob_field}`, `GET/POST/HEAD /{table}` и `GET/DELETE/HEAD /{table}/{name}` тот же заголовок консоли описан как целое число:
       ```yaml
       Retry-After:
         schema:
           type: integer
           const: 1
         description: Обязателен для error=busy, не обещает срок восстановления прочих отказов.
       ```
     (Для сравнения: у ответа `429` заголовок `Retry-After` во всех контрактах уроков 02, 03, 04, 09, 10 единообразно имеет `schema: {type: string}`.)

- **Минимальное направление исправления:**
  Привести схему заголовка `Retry-After` в ответах `503` к единой форме во всех файлах `.api.openapi.yaml` (например, к `type: string, const: '1'`, как уже сделано в `02`, `03`, `04` и для `type: string` у `429`, либо к единому выбранному канону во всех контрактах, включая выравнивание `/drain` и `/schema`/`/{table}` внутри `10-schema-drain-snapshot-limits.api.openapi.yaml`).

---

## 3. Поурочный разбор комплекта (01–11, `GLOSSARY.md`, `module-design.md`, `lesson-spec`)

### Урок 01 — `01-storage`
- **Проверенные файлы:** `М10_Platform/01-storage.md`, `М10_Platform/spec/01-storage.norms.md`, `М10_Platform/spec/01-storage.api.openapi.yaml`, `М10_Platform/spec/01-storage.README.md`, `Source/tests/testdata/acceptance/М10_Platform/01/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** `check_spec.py` проходит (`PASS`, `EXIT_CODE=0`, 23 нормы чеклиста `М10/1-01…23`, 50 `$ref` в OpenAPI, 23 сценария / 105 шагов в `01/scenarios.tsv`). Правка `K37-05` (лишние поля команды `POST /v1/write` в `Cmd`, сценарий `23-extra-cmd`) корректно отражена в `01-storage.norms.md` (Н2 строки 111–114, Н5 строка 265, чеклист `М10/1-11`, `М10/1-12`), `01/scenarios.tsv` и `01/README.md`, а `01-storage.api.openapi.yaml` разрешает дополнительные поля верхнего уровня `Cmd` (не имеет `additionalProperties: false` на `Cmd`, сохраняя `additionalProperties: false` на `Guard`).
- **Находки:** `G38-01` (`S3` — в `01-storage.README.md` остались упоминания `01–22` вместо `01–23` и не уточнена строка таблицы ловушек по лишним полям `Cmd`). Находок `S0–S2` нет.

### Урок 02 — `02-the-spec-and-the-strict-loader`
- **Проверенные файлы:** `М10_Platform/02-the-spec-and-the-strict-loader.md`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.api.openapi.yaml`, `М10_Platform/spec/02-the-spec-and-the-strict-loader.README.md`, `Source/tests/testdata/acceptance/М10_Platform/02/{README.md,verdicts.tsv,diagnostics.tsv,corrections.tsv,cases/*.subsystem.yaml}`.
- **Результат проверки:** `check_spec.py` проходит (`PASS`, `EXIT_CODE=0`, 25 норм чеклиста `М10/2-01…25`, 33 `$ref`, 234 вердикта: 37 `ok` и 197 `refused`, 13 строк `diagnostics.tsv`). Добавленные в прогоне 37 случаи `r37_*` (включая `r37_rows_cluster`, `r37_rows_worker` для полного покрытия запрета `cluster`/`worker`/`ts` в `unit.rows`, проверки `:int`, зарезервированных слов и правил каталога) полностью синхронизированы между `.norms.md`, `.README.md`, `02/README.md` и `02/verdicts.tsv`.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### Урок 03 — `03-units-slots-epochs-lease`
- **Проверенные файлы:** `М10_Platform/03-units-slots-epochs-lease.md`, `М10_Platform/spec/03-units-slots-epochs-lease.norms.md`, `М10_Platform/spec/03-units-slots-epochs-lease.api.openapi.yaml`, `М10_Platform/spec/03-units-slots-epochs-lease.README.md`, `Source/tests/testdata/acceptance/М10_Platform/03/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 19 норм чеклиста `М10/3-01…19`, 79 `$ref` в OpenAPI (`errors=0`), 11 сценариев / 44 шага в `03/scenarios.tsv` (все JSON-тела валидны). Таблицы переходов состояний захвата слота, идемпотентного создания единицы (`Idempotency-Key`, шаг 9 сохранения отказа), проверки `placement.weight.field >= 1` и `413 row too large` полностью согласованы между нормой, OpenAPI, README и приёмкой.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### Урок 04 — `04-the-controller-and-placement`
- **Проверенные файлы:** `М10_Platform/04-the-controller-and-placement.md`, `М10_Platform/spec/04-the-controller-and-placement.norms.md`, `М10_Platform/spec/04-the-controller-and-placement.api.openapi.yaml`, `М10_Platform/spec/04-the-controller-and-placement.README.md`, `Source/tests/testdata/acceptance/М10_Platform/04/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 22 нормы чеклиста `М10/4-01…22`, 168 `$ref` в OpenAPI (`errors=0`), 6 сценариев / 21 шаг в `04/scenarios.tsv`. Проходы контроллера, общий допуск `controller/placement_turn`, сохраняемое намерение `controller/placement_intent/<u>`, грамматика `WorkerName`/`UnitRef` и контракты дверей `/policy`, `/drain`, `/servers/{server}/labels`, `/servers/{server}/decommission`, `/unplaceable`, `/where/{id}` непротиворечивы.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### Урок 05 — `05-the-worker-under-its-slot`
- **Проверенные файлы:** `М10_Platform/05-the-worker-under-its-slot.md`, `М10_Platform/spec/05-the-worker-under-its-slot.norms.md`, `М10_Platform/spec/05-the-worker-under-its-slot.README.md`, `Source/tests/testdata/acceptance/М10_Platform/05/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** В соответствии с доп. 13 ADR-0082 урок не имеет собственной HTTP-двери и файла `.api.openapi.yaml`. 14 норм чеклиста `М10/5-01…14`, 6 сценариев / 53 шага в `05/scenarios.tsv`. Цикл воркера, шаг аренды, ворота `взять_эпоху`, подмена застрявшего шага (`STALL` / `FOR`), правила удержания места (`holds`) и отсечения соперника согласованы с уроками 1, 3, 4 и 8.
- **Находки:** Находок `S0–S3` нет.

### Урок 06 — `06-rights`
- **Проверенные файлы:** `М10_Platform/06-rights.md`, `М10_Platform/spec/06-rights.norms.md`, `М10_Platform/spec/06-rights.api.openapi.yaml`, `М10_Platform/spec/06-rights.README.md`, `Source/tests/testdata/acceptance/М10_Platform/06/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 12 норм чеклиста `М10/6-01…12`, 12 `$ref` в OpenAPI (`errors=0`), 9 сценариев / 40 шагов в `06/scenarios.tsv`. Правила вывода прав из спеки (включая `controller/placement_turn`, `controller/placement_intent/*`, `delete_after` → только `delete`), заголовок пересылки роли и mTLS-предметы проверки согласованы со всеми связанными уроками.
- **Находки:** Находок `S0–S3` нет.

### Урок 07 — `07-secrets-and-sealing`
- **Проверенные файлы:** `М10_Platform/07-secrets-and-sealing.md`, `М10_Platform/spec/07-secrets-and-sealing.norms.md`, `М10_Platform/spec/07-secrets-and-sealing.README.md`, `Source/tests/testdata/acceptance/М10_Platform/07/{README.md,scenarios.tsv,log_mask.tsv,secret_in.tsv,corrections.tsv}`, `Source/tests/testdata/platform_lists.tsv`.
- **Результат проверки:** В соответствии с доп. 14 ADR-0082 урок не имеет собственных HTTP-маршрутов и файла `.api.openapi.yaml` (влияние на дверь единиц отражено в контракте урока 3). 12 норм чеклиста `М10/7-01…12`, 6 сценариев / 30 шагов в `07/scenarios.tsv`, 19 строк в `07/log_mask.tsv`, 420 строк в `07/secret_in.tsv`, 37 строк в `platform_lists.tsv`. Все таблицы и сценарии консистентны.
- **Находки:** Находок `S0–S3` нет.

### Урок 08 — `08-events-resource-requests`
- **Проверенные файлы:** `М10_Platform/08-events-resource-requests.md`, `М10_Platform/spec/08-events-resource-requests.norms.md`, `М10_Platform/spec/08-events-resource-requests.api.openapi.yaml`, `М10_Platform/spec/08-events-resource-requests.README.md`, `Source/tests/testdata/acceptance/М10_Platform/08/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 18 норм чеклиста `М10/8-01…18`, 127 `$ref` в OpenAPI (`errors=0`), 6 сценариев / 38 шагов в `08/scenarios.tsv`. Проходы подачи и исполнения просьб (`asked`, `requests`, `done`, перечитка метки на шаге 5), индексация событий, зеркалирование и дверь объектов полностью согласованы.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### Урок 09 — `09-the-console`
- **Проверенные файлы:** `М10_Platform/09-the-console.md`, `М10_Platform/spec/09-the-console.norms.md`, `М10_Platform/spec/09-the-console.api.openapi.yaml`, `М10_Platform/spec/09-the-console.README.md`, `Source/tests/testdata/acceptance/М10_Platform/09/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 12 норм чеклиста `М10/9-01…12`, 329 `$ref` в OpenAPI (`errors=0`), 6 сценариев / 26 шагов в `09/scenarios.tsv`. Все маршруты `GET` и `HEAD` в `09-the-console.api.openapi.yaml` имеют полный паритет по кодам ответов, заголовкам и параметрам; схемы `M1_..M8_` в `components.schemas` структурно идентичны схемам уроков-владельцев.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### Урок 10 — `10-schema-drain-snapshot-limits`
- **Проверенные файлы:** `М10_Platform/10-schema-drain-snapshot-limits.md`, `М10_Platform/spec/10-schema-drain-snapshot-limits.norms.md`, `М10_Platform/spec/10-schema-drain-snapshot-limits.api.openapi.yaml`, `М10_Platform/spec/10-schema-drain-snapshot-limits.README.md`, `Source/tests/testdata/acceptance/М10_Platform/10/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 10 норм чеклиста `М10/10-01…10`, 184 `$ref` в OpenAPI (`errors=0`), 6 сценариев / 36 шагов в `10/scenarios.tsv`. Проходы подъёма схемы, пробы и включения дренажа, записи блобов, уборки `sweep` и публикации снимка состояния согласованы между нормой, контрактом и приёмкой.
- **Находки:** `G38-02` (`S3` — внутри `10-schema-drain-snapshot-limits.api.openapi.yaml` смешаны `type: string, const: '1'` у `/drain` и `type: integer, const: 1` у `/schema`, `/{rows}/{id}/{blob_field}`, `/{table}`). Находок `S0–S2` нет.

### Урок 11 — `11-the-platform-on-a-box-and-a-cluster`
- **Проверенные файлы:** `М10_Platform/11-the-platform-on-a-box-and-a-cluster.md`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.api.openapi.yaml`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.README.md`, `Source/tests/testdata/acceptance/М10_Platform/11/{README.md,scenarios.tsv,corrections.tsv}`.
- **Результат проверки:** 15 норм чеклиста `М10/11-01…15`, 85 `$ref` в OpenAPI (`errors=0`), 7 сценариев / 21 шаг (17 автоматических и 4 `@manual`) в `11/scenarios.tsv`. Проходы установки, вступления/выхода из группы, восстановления большинства (`recover` с подъёмом `platform/epoch_floor`) и восстановления событий (`restore`) согласованы с остальными уроками курса.
- **Находки:** только общая межконтрактная `G38-02` (`S3`). Находок `S0–S2` нет.

### `GLOSSARY.md`, `М10_Platform/module-design.md`, `.claude/skills/lesson-spec/*`, общие данные `Source/tests/testdata/*`
- **Проверенные файлы:** `GLOSSARY.md`, `М10_Platform/module-design.md`, `.claude/skills/lesson-spec/SKILL.md`, `.claude/skills/lesson-spec/references/{acceptance-formats.md,lecture-norms-split.md,openapi-rules.md}`, `.claude/skills/lesson-spec/assets/{lecture.md,norms.md,instructions.md,api.openapi.yaml}`, `.claude/skills/lesson-spec/scripts/{check_spec.py,test_check_spec.py}`, `Source/tests/testdata/{testsub.subsystem.yaml,testsub2.subsystem.yaml,platform_lists.tsv}`.
- **Результат проверки:**
  - Термины `GLOSSARY.md` и карта тем/таблица файлов `М10_Platform/module-design.md` (включая отсутствие `.api.openapi.yaml` у уроков 05 и 07 и актуальные переносы норм) полностью соответствуют комплекту `М10_Platform/01–11`.
  - Все 49 тестов `test_check_spec.py` проходят (`EXIT_CODE=0`); правила YAML 1.2 Core Schema и разрешения JSON Pointer в `check_spec.py` согласованы с `SKILL.md` и `references/openapi-rules.md`.
  - В общих спеках `testsub.subsystem.yaml` и `testsub2.subsystem.yaml` `lease: 'off'` записан строкой в кавычках, все поля соответствуют грамматике урока 2.
- **Находки:** Находок `S0–S3` нет.

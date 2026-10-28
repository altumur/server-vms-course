# Дефекты закреплённых версий библиотек (ADR-0092 п. 9)

Перечень для реализаций: дефекты библиотек закреплённых версий ([requirements.txt](requirements.txt), [go.mod](go.mod)),
которые меняют исход против нормы, и их обходы. Обход — не правило: исход тот же, что у нормы. Дефекты эталона по метке
(правка нормы после метки) сюда не входят — они в навыке `lesson-spec` (`v7/DEFECTS.tsv`).

Столбец «Вектор» — строки векторов, на которых без обхода ответ другой: `family-read:<case>` (пакет
[`family-read`](../vectors/family-read/README.md)), `yaml-suite:<id>` ([`yaml-suite`](../vectors/yaml-suite/README.md)),
`corpus:<случай>` (корпус P/02.1, `02-installer/acceptance/1/verdicts.tsv`), `canonical:<case>` (векторы P/02.2). `страж`
— дефект виден только при ошибке перевода: правильные векторы его не ловят, обход — проверка, что ошибки нет. `check_spec`
сверяет: id — как в `v7/DEFECTS.tsv` навыка, каждая строка вектора есть, у каждой записи — строка или `страж`.

| id | Библиотека, версия | Вход | Библиотека даёт | По норме | Обход (слой) | Вектор |
|---|---|---|---|---|---|---|
| D1 | jsonschema (Python) 4.26.0 | `pattern` `^(?:w)$` и строка `"w\n"`; `pattern` без якорей; `\d` на `١`; `.` на `\n` | `re.search`: частичное совпадение; `$` совпадает и перед последним `\n`; `\d`, `\w` — классы Unicode; `.` не берёт `\n` | полное совпадение, `$` — конец строки; выражение — в переносимом подмножестве (LAYERS § 3) | слой 5: полное совпадение, `$` → `\Z`; `check_spec`: `^(?:…)$`, без `\d \w` и `.` (`[\s\S]`) | `family-read:02-0031`, `corpus:f08_exec_trailing_nl`, `corpus:f09_prefix_trailing_nl` |
| D2 | jsonschema (Python) 4.26.0 | имя `"a_secret\n"` под `patternProperties` `^(?:[\s\S]*_secret)$` | имя взято шаблоном | имя не взято (полное совпадение) | слой 5: своё слово `patternProperties` с `\Z` | страж: шаблоны имён `patternProperties` есть только у манифеста, а там имя с `\n` отказано грамматикой имени на том же месте — исход не меняется |
| D3 | jsonschema (Python) 4.26.0 | схема `false` под `properties`, ключ есть | место отказа — объект, имя ключа потеряно | место — `O/<ключ>` | перевод: «ключа быть не должно» — `{"not": {}}` вместо `false` | — нужна строка: family-read `objects/<sub>/commands/<rid>` с полем, запрещённым состоянием (`commands.schema.json` `/allOf/2/then/properties/error`), — отказ `/error` |
| D4 | cel-expr-python 0.1.3 | своя функция с параметром `dyn`: `depth(doc)` на map | «No matching overloads found», значение ERROR | функция исполняется | перегрузка на каждый тип (map, list, string, int, double, bool, null) | `corpus:c8_ref12_unit_schema_depth_33`, `corpus:a91_unit_state_depth_33` |
| D5 | cel-expr-python 0.1.3 | ошибка исполнения выражения связи | значение типа ERROR, не исключение: строка молча «не срабатывает» | ошибка исполнения — авария, не «нет отказа» | раннер проверяет тип результата и падает | страж |
| D6 | cel-expr-python (cel-cpp) 0.1.3 | перебор по значению, взятому индексом: `doc["a"].exists(…)` | отказ проверки типов «dyn cannot be the range of a comprehension» | перебор исполняется | перевод: диапазон перебора — `dyn(…)` | `corpus:a91_creates_twice` |
| D7 | santhosh-tekuri/jsonschema/v6 v6.0.2 | имя не по `propertyNames` | место — корень отдельной проверки | место — `O/<имя>` | слой 4 (Go): место объекта-родителя в дереве ошибок плюс имя | `family-read:04-0887`, `corpus:c2_table_name_object_family` |
| D8 | cel-go v0.26.1 | `double(doc["a"])` под проверкой типов, значение int | «no such overload: double(int)» при исполнении | число приводится к double | перевод: `double(dyn(…))` | `corpus:c8_ref76_requests_valid_for_over_most_valid` |
| D9 | ruamel.yaml 0.19.1 | `"\UFFFFFFFF"` в двойных кавычках | OverflowError (не YAMLError): падение разбора | отказ `text` | слой 1: ValueError и OverflowError — отказ `text` | `corpus:t26_escape_U_overflow` |
| D10 | ruamel.yaml 0.19.1, go.yaml.in/yaml/v3 v3.0.5 | `{k:}` | ключ `"k:"` | ключ `k` без значения (YAML 1.2.2 [130], [147]) | правило `{k:}` тонкой проверки — отказ при любом прочтении | `corpus:c6_flow_map_empty_value` |
| D11 | ruamel.yaml 0.19.1, go.yaml.in/yaml/v3 v3.0.5 | `#` без пробела перед ним: `"a"# c`, `]#`, `,#` в потоке на несколько строк | принято как комментарий (после `,` на одной строке ruamel отказывает сам) | отказ (комментарий — после пробела) | слой 1: `#` вплотную после кавычки, `]`, `}` — отказ `text` (comment-tight); поток на несколько строк — rare | `yaml-suite:SU5Z`, `yaml-suite:9JBA`, `yaml-suite:CVW2` |
| D12 | go.yaml.in/yaml/v3 v3.0.5 | `\'` в двойных кавычках | принято | отказ (экранирования — только YAML 1.2.2) | тонкая проверка экранирований | `yaml-suite:HRE5` |
| D13 | go.yaml.in/yaml/v3 v3.0.5 | `\/` в двойных кавычках | отказ парсера | `/` (YAML 1.2.2, Н1.1) | слой 1 (Go): `\/` → `/` в двойных кавычках до разбора | `yaml-suite:3UYS` |
| D14 | go.yaml.in/yaml/v3 v3.0.5 | `># c` | принято | отказ (после индикатора — пробел или конец строки) | тонкая проверка заголовка блочного скаляра | `yaml-suite:X4QW` |
| D15 | go.yaml.in/yaml/v3 v3.0.5 | начальные пустые строки блочного скаляра глубже первой строки содержимого | принято | отказ | тонкая проверка тела блочного скаляра | `yaml-suite:S98Z` |
| D16 | ruamel.yaml 0.19.1, go.yaml.in/yaml/v3 v3.0.5 | последняя строка из пробелов без перевода строки после блочного скаляра | значение без конечного `\n` | с `\n` | слой 1: LF в конец текста без LF до разбора | `yaml-suite:L24T/01` |
| D17 | go.yaml.in/yaml/v3 v3.0.5 | `...` в конце потока | не сообщается; второй документ `Unmarshal` не читает | отказ `text` (один документ) | один документ — по байтам | `corpus:t05_doc_end` |
| D18 | cel-go v0.26.1 (свойство CEL) | `unique`/`prefix_free` с номерами элементов двух переборов одного отображения | порядок перебора случаен — исход случаен | исход от порядка не зависит | перевод: наборы из `keys()` без номеров — `filter(…).size() == 1`, сравнение по значению | `corpus:c4_readers_nested` |
| D20 | ruamel.yaml 0.19.1 | строки продолжения потока и кавычек на колонке 0 и с TAB в начале | принято | отказ (YAML 1.2.2; suite error) | слой 1: rare (поток и кавычки на несколько строк, Н1.1:95) и tab — свой отказ не нужен | `yaml-suite:9C9N`, `yaml-suite:QB6E`, `yaml-suite:DK95/01`, `yaml-suite:Y79Y/003` |
| D21 | ruamel.yaml 0.19.1 | `%TAG`/`%YAML` после содержимого без `...`; `%YAML 1.3`; `...` в конце или пустой документ | директива принята; AssertionError на `%YAML 1.3`; ParserError на `...` | отказ `text`: директивы и `...` вне формы (Н1.1:46) | слой 1: directive и doc-end — отказ по байтам до разбора | `yaml-suite:9HCY`, `yaml-suite:EB22`, `yaml-suite:RHX7`, `yaml-suite:MUS6/01`, `yaml-suite:BEC7`, `yaml-suite:HWV9`, `yaml-suite:M7A3`, `yaml-suite:QT73` |

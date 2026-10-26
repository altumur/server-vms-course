---
genre: записки
kind: замер
subject: "ADR-0087 п. 4 — готовый парсер YAML с тонкой проверкой против своего слоя текста, корпус P/02.1"
source-commit: aee6716ea
date: 2026-10-26
status: draft
---

# Готовые парсеры YAML на корпусе P/02.1: замер

Вопрос замера: что будет, если вместо своего слоя текста (разборщик YAML по ADR-0087 п. 4) взять готовый парсер и
поставить поверх него тонкую свою проверку. Здесь только факты и числа, без рекомендаций. Каждое число пересчитывается
командами из раздела «Повтор».

## Что мерили

**Вход.** Корпус [Platform/02-installer/acceptance/1/](../../../Platform/02-installer/acceptance/1/README.md):
630 файлов `cases/*.subsystem.yaml` (118 `ok`, 512 `refused`, `verdicts.tsv`); класс отказа задан у 206 случаев
(`classes.tsv`: 112 value, 62 reference, 28 text, 3 key, 1 name); пути и строки — у 52 (`diagnostics.tsv`).
Нормы текста — P/02.1 Н1.1 ([02.1-installer.norms.md](../../../Platform/02-installer/spec/02.1-installer.norms.md), около
строки 30) и [02.1-installer.scalars.tsv](../../../Platform/02-installer/spec/02.1-installer.scalars.tsv).

**Исполнитель формы и связей — один для всех.** Дерево каждого парсера подаётся в
`Loader.judge_tree` эталонного исполнителя курса
([skills/lesson-spec/scripts/form_source/judge.py](../../../skills/lesson-spec/scripts/form_source/judge.py)), собранного из
трёх файлов источника формы `02.1-installer.{form.yaml,references.tsv,scalars.tsv}`. Поэтому разница между строками
таблицы — только в слое YAML. Эталон для сравнения — `Loader.judge` того же исполнителя: свой слой текста
[textlayer.py](../../../skills/lesson-spec/scripts/manifest_schema/textlayer.py) поверх событий ruamel.yaml с правилами
E, R1–R5, K, S, T, N из его шапки.

**Конфигурации.** Для каждого парсера — две по заданию и третья (в) для записки о диалекте.

- **(а) Парсер и тонкая проверка структуры.** Отказ `text` на якоре, псевдониме, ключе слияния `<<`, явном теге,
  повторе ключа (по прочитанному значению с типом), ключе-коллекции, глубине больше 64 (корень — уровень 1, каждое
  отображение и список — ещё уровень). Ошибка самой библиотеки — тоже отказ `text`. Скаляры — как их прочёл парсер.
  Один шаг сверх списка: NaN и бесконечность уходят в `numbers` исполнителя (класс value), потому что дерево JSON их не
  держит. Ключ не строкой (`1`, `true`) передаётся исполнителю как есть.
- **(б) То же и простые скаляры по scalars.tsv.** Стиль скаляра берётся из узла парсера. Простой скаляр сверяется со
  строками таблицы сверху вниз целиком (`re.fullmatch`). В кавычках и блочный — строка. Строки `limit` (`int_max`,
  `float_max`) и вид `nonfinite` дают `numbers`. Пустой простой скаляр значением — «сказанный ключ без значения»
  (`empties`, Н1.1 empty). Простой ключ, который таблица читает не строкой, — отказ `text` (Н1.1 keys). Потерю
  значимости (`1e-400`) таблица не задаёт — она записана только прозой Н1.1, поэтому (б) её не проверяет.
- **(в) То же, что (б), и правила, которые тонкая проверка снимает без своего лексера.** Добавлена после шага 1 для
  вопроса Q4 записки о диалекте: что из отличий Н1.1 снимает проверка поверх готового парсера. Сверх (б):
  - знаки Н1.1 encoding по байтам до парсера — UTF-8, U+FEFF первым знаком, C0 кроме TAB/LF/CR, DEL, C1 (с U+0085),
    U+FFFE/FFFF, U+2028/2029, одиночный CR (то же выражение, что E в textlayer.py);
  - те же знаки в значении и ключе после экранирований (суррогаты, `\a`, `\x07`);
  - один документ (yaml.v3: число документов считает `yaml.NewDecoder`, `Unmarshal` его не сообщает);
  - корень — блочное отображение с колонки 1;
  - потеря значимости простого float — `numbers` (проза Н1.1).

  TAB вне кавычек, блочного скаляра и комментария (в textlayer.py — по границам скаляров) в (в) не входит.

**Парсеры.** Python: PyYAML 6.0.3 (`SafeLoader`, YAML 1.1, чистый Python) и ruamel.yaml 0.19.1
(`typ="safe", pure=True`, `version = (1, 2)`). Go: gopkg.in/yaml.v3 v3.0.1 — `yaml.Unmarshal` в `yaml.Node`.

**Что сверяется.**
- Вердикт — с `verdicts.tsv` (из 630).
- Класс — с `classes.tsv`: засчитан, если вердикт `refused` и класс тот же (из 206).
- Пути и строки — как в `check_spec.py` (`form_source`, около строки 1676): при верном вердикте и классе множество путей
  равно таблице, а её строки входят в названные (из 52).
- Сверх таблиц корпуса: класс против класса эталона на всех 512 отказах. Это сравнение с реализацией курса, а не с
  таблицей корпуса: у 306 отказов вне `classes.tsv` класс никто в корпусе не записал.

**Решения стенда, от которых зависят числа.**
- Python: события парсера (якорь, явный тег) и узлы компоновщика (`compose`; стиль, строка, значение). Значение
  скаляра конструктор библиотеки строит только в (а); в (б) конструктор не вызывается.
- Go: `yaml.Unmarshal` читает первый документ файла — так ведёт себя сама библиотека; второй документ стенд не
  проверяет, потому что его нет в списке (а). Значение в (а) — `node.Decode(&any)`. В (б) таблица применяется в Python
  к тексту и стилю узла yaml.v3, а не через RE2 Go; выражения таблицы в обоих движках одни и те же (только классы,
  `|`, `?`, `+`, `*`).
- Номер строки из ошибки yaml.v3 стенд не извлекает (пишет 0). На 52 случая это не влияет: ни один из них не
  отказан ошибкой yaml.v3.
- Дерево yaml.v3 глубже 70 узлов стенд усекает (декодер JSON в Python упирается в предел рекурсии). Отказ по глубине
  наступает на 65-м уровне коллекций, раньше усечения.

**Проверка стенда.** Строка «эталон» в сводке: 630/630, 206/206, 52/52 — стенд читает корпус и таблицы так же, как
`check_spec`.

## Как читать «вердикт совпал»

Вердикт часто держит посторонний отказ. В корпусе 74 файла без строки `worker:` в корне
(`LC_ALL=C grep -aL '^worker:' Platform/02-installer/acceptance/1/cases/*.subsystem.yaml | wc -l`); все 74 — отказы,
29 из них есть в `classes.tsv`. `worker.exec` обязателен с ADR-0091 доп. (4), поэтому дерево такого файла исполнитель
отказывает `value` по пути `worker`, какой бы ни была настоящая причина. Пример — `c5_value_next_line_plain`: ключ
`rows:` и слово `counters` строкой ниже. Эталон отказывает `text` (Н1.1 blocks), все шесть конфигураций читают
`rows: counters` и отказывают `value` по `worker`. Вердикт совпал, класс — нет. У случаев вне `classes.tsv`
(`bom_utf8`, `c3_escape_bel`, `c4_hash_after_quote` и другие) такое расхождение таблицы корпуса не видят: оно есть
только в столбце «вердикт совпал, класс иной, чем у эталона».

## Сводка

| парсер × конфигурация | вердикт совпал из 630 | класс совпал из 206 | пути и строки совпали из 52 | класс как у эталона из 512 отказов | вердикт совпал, класс иной, чем у эталона (из них вне classes.tsv) |
|---|---|---|---|---|---|
| эталон (textlayer.py на ruamel.yaml) | 630 | 206 | 52 | 512 | 0 (0) |
| PyYAML 6.0.3 (а) | 560 | 155 | 12 | 411 | 98 (47) |
| PyYAML 6.0.3 (б) | 626 | 194 | 51 | 486 | 25 (14) |
| PyYAML 6.0.3 (в) | 627 | 198 | 51 | 498 | 14 (6) |
| ruamel.yaml 0.19.1 (а) | 617 | 176 | 45 | 462 | 43 (17) |
| ruamel.yaml 0.19.1 (б) | 626 | 193 | 51 | 483 | 28 (16) |
| ruamel.yaml 0.19.1 (в) | 627 | 197 | 51 | 497 | 15 (6) |
| yaml.v3 v3.0.1 (а) | 616 | 179 | 45 | 464 | 41 (19) |
| yaml.v3 v3.0.1 (б) | 625 | 196 | 51 | 484 | 27 (18) |
| yaml.v3 v3.0.1 (в) | 626 | 197 | 51 | 495 | 17 (8) |

Случаев с расхождением хотя бы у одной конфигурации: 127; из них только у PyYAML (а): 86.

## Расхождения по группам (случаев; вердикт или класс)

| конфигурация | скаляры | отступы | комментарии | кодировка | структура | дефект парсера | всего |
|---|---|---|---|---|---|---|---|
| PyYAML 6.0.3 (а) | 117 | 1 | 1 | 0 | 1 | 1 | 121 |
| PyYAML 6.0.3 (б) | 5 | 4 | 2 | 3 | 1 | 0 | 15 |
| PyYAML 6.0.3 (в) | 4 | 4 | 2 | 0 | 1 | 0 | 11 |
| ruamel.yaml 0.19.1 (а) | 27 | 4 | 2 | 3 | 1 | 2 | 39 |
| ruamel.yaml 0.19.1 (б) | 5 | 4 | 2 | 3 | 1 | 1 | 16 |
| ruamel.yaml 0.19.1 (в) | 4 | 4 | 2 | 0 | 1 | 1 | 12 |
| yaml.v3 v3.0.1 (а) | 27 | 4 | 2 | 0 | 1 | 2 | 36 |
| yaml.v3 v3.0.1 (б) | 5 | 4 | 2 | 0 | 1 | 2 | 14 |
| yaml.v3 v3.0.1 (в) | 4 | 4 | 2 | 0 | 1 | 2 | 13 |

Группа случая — по причине из таблицы ниже; у PyYAML (а) случай, где срабатывает `off` общего фона, отнесён к скалярам.

## Расхождения по случаям

| случай | ждали | эталон: правило | PyYAML а | PyYAML б | PyYAML в | ruamel а | ruamel б | ruamel в | yaml.v3 а | yaml.v3 б | yaml.v3 в | группа | причина |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `c4_block_tab_content_ok` | ok | ok | value¹ | ✓ | ✓ | ✓ | ✓ | ✓ | text | text | text | дефект парсера | yaml.v3 отказывает TAB после отступа в первой строке блочного скаляра `\|` с автоотступом; YAML 1.2.2 § 8.1.2 (`nb-char` включает TAB) это допускает, Python-парсеры читают |
| `c4_default_without_value` | refused:value | form | ✓ | ✓ | ✓ | ok | ✓ | ✓ | ok | ✓ | ✓ | скаляры | `default:` без значения: парсер даёт null, норма Н1.1 empty — «сказанный ключ без значения», value |
| `c4_display_fields_numeric_key` | refused:text | text:K | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ `1` парсер читает целым; Н1.1 keys — отказ text |
| `c4_key_int_and_string` | refused:text | text:K | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | ключи `1` и `"1"` для парсера разные (int и str); Н1.1 keys — отказ text |
| `c5_bool_required_tRuE_ok` | ok | ok | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | `tRuE`: core YAML 1.2 (§ 10.3.2) — строка, таблица курса — bool |
| `c5_escape_U_surrogate` | refused:text | text:E | value¹ | value | ✓ | value | value | ✓ | ✓ | ✓ | ✓ | кодировка | `"\U0000d800"`: Python-парсеры отдают одиночный суррогат без ошибки, Н1.1 escape — отказ text; yaml.v3 отказывает сам |
| `c5_escape_surrogate` | refused:text | text:E | value¹ | value | ✓ | value | value | ✓ | ✓ | ✓ | ✓ | кодировка | `"\ud800"`: то же |
| `c5_escape_surrogate_pair` | refused:text | text:E | value¹ | value | ✓ | value | value | ✓ | ✓ | ✓ | ✓ | кодировка | `"\ud83d\ude00"`: Python-парсеры отдают строку с суррогатами без ошибки, Н1.1 escape — отказ text; yaml.v3 отказывает сам |
| `c5_key_0o7_word_ok` | ok | ok | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | ключ `0o7`: core YAML 1.2 — целое, таблица курса — слово |
| `c5_key_0x10_word_ok` | ok | ok | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | ключ `0x10`: core YAML 1.2 — целое, таблица курса — слово |
| `c5_key_long_1025_ok` | ok | ok | text | text | text | text | text | text | text | text | text | структура | неявный ключ длиннее 1024 знаков: YAML 1.2.2 § 7.4.2 и § 8.2.2 запрещают, все три парсера отказывают; Н1.1 keys снимает предел |
| `c5_key_question_mark` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | скаляры | `?x:` для YAML — простой ключ `?x`; Н1.1 keys — отказ text; вердикт держит посторонний отказ (нет `worker`) |
| `c5_unit_minus_word_ok` | ok | ok | text | text | text | text | text | text | text | text | text | скаляры | `unit: -` для YAML — элемент списка, парсер отказывает; Н1.1 string — слово `-` |
| `c5_unit_tRuE_is_bool` | refused:value | form | ✓ | ✓ | ✓ | ok | ✓ | ✓ | ok | ✓ | ✓ | скаляры | `unit: tRuE`: core — строка (форма принимает), таблица курса — bool (value) |
| `c5_value_next_line_flow` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | отступы | значение потоком на строке ниже ключа — законный YAML; Н1.1 blocks — отказ text; вердикт держит посторонний отказ (нет `worker`) |
| `c5_value_next_line_plain` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | отступы | слово на строке ниже ключа — законный YAML; Н1.1 blocks — отказ text; вердикт держит посторонний отказ |
| `c5_value_next_line_quoted` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | отступы | строка в кавычках ниже ключа — законный YAML; Н1.1 blocks — отказ text; вердикт держит посторонний отказ |
| `c5_value_question_mark` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | скаляры | значение `?x` для YAML — слово; Н1.1 string — отказ text; вердикт держит посторонний отказ |
| `c6_flow_map_empty_value` | refused:value | form | ✓ | ✓ | ✓ | key | key | key | key | key | key | дефект парсера | `{unconfirmed_max:}`: по YAML 1.2.2 [130] и [147] `:` перед `}` — указатель значения (ключ без значения); ruamel и yaml.v3 оставляют `:` в ключе (key), PyYAML читает по стандарту |
| `c7_float_max_rounded_ok` | ok | ok | value | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | YAML 1.1: `1.7976931348623158e308` — строка (float 1.1 требует знак у показателя), form ждёт число |
| `c7_float_underflow` | refused:value | form | ✓ | ok | ✓ | ok | ok | ✓ | ok | ok | ✓ | скаляры | `1e-400` все парсеры читают нулём; потеря значимости — отказ value в прозе Н1.1, в scalars.tsv её нет |
| `c7_seq_dash_scalar_below` | refused:text | text:N | value | value | value | value | value | value | value | value | value | отступы | скаляр строкой ниже голого `-` — законный YAML; Н1.1 blocks — отказ text; вердикт держит посторонний отказ |
| `c7_word_continuation_comment` | refused:text | text:N | value | value | value | value | value | value | value | value | value | комментарии | ` # c` в строке продолжения слова для YAML — комментарий; Н1.1 blocks — отказ text; вердикт держит посторонний отказ |
| `c8_int_4301_digits` | refused:value | form | text | ✓ | ✓ | text | ✓ | ✓ | ✓ | ✓ | ✓ | дефект парсера | конструктор Python-библиотеки зовёт `int()` CPython: предел 4300 цифр — ValueError (text вместо value); в (б) значение не строится, расхождения нет |
| `c8_json_default_overflow` | refused:value | form | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ok | ✓ | ✓ | скаляры | `1e999` в значении поля json: yaml.v3 не читает числом (вне диапазона float64) и отдаёт строку — поле json её принимает; Python-парсеры дают бесконечность |
| `c8_word_hash_space` | refused:text | text:N | value¹ | value | value | value | value | value | value | value | value | комментарии | `counter# c`: для YAML `#` после знака — часть слова; Н1.1 comment — отказ text; путь и вердикт — посторонние |
| `c9_flow_lone_dash_spaced` | ok | ok | text | text | text | text | text | text | text | text | text | скаляры | `[ - , a ]`: для YAML — ошибка разбора; Н1.1 string (Т16) — слово `-` |
| `display_options_bool_plain_key` | refused:text | text:K | value¹ | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ `true` парсер читает bool; Н1.1 keys — отказ text |
| `display_options_yes_key` | ok | ok | value¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | YAML 1.1: ключ `yes` и значение `Yes` — bool; в enum `yes` тоже bool |
| `display_word_On_Off_unquoted` | ok | ok | value¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | YAML 1.1: значения `On`/`Off` — bool, подпись ждёт строку |
| `float_finite_defaults` | ok | ok | value¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | YAML 1.1: `1.7976931348623157e308` — строка (показатель без знака), form ждёт число |
| `float_finite_inherit` | ok | ok | value¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | то же, `inherit` |
| `lease_1_000` | refused | form | ok | ✓ | ✓ | ok | ✓ | ✓ | ok | ✓ | ✓ | скаляры | `1_000`: ruamel (версия 1.2) и yaml.v3 читают целым 1000, core YAML 1.2.2 § 10.3.2 — строкой; таблица курса — слово |
| `lease_hex_0x10` | refused | form | ok | ✓ | ✓ | ok | ✓ | ✓ | ok | ✓ | ✓ | скаляры | `0x10`: core YAML 1.2 — целое 16 (форма принимает), таблица курса — слово |
| `lease_huge_int` | refused | form | ok | ✓ | ✓ | ok | ✓ | ✓ | ✓ | ✓ | ✓ | скаляры | 23 цифры: ruamel — целое Python без предела (принято), yaml.v3 — float64; предел 2^53−1 только в таблице |
| `m49_int_2p53` | refused:value | form | ✓ | ✓ | ✓ | ok | ✓ | ✓ | ok | ✓ | ✓ | скаляры | 2^53: парсер читает целым; предел int_max только в таблице |
| `profile_table_key_bool` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `true` — bool; Н1.1 keys — отказ text |
| `profile_table_key_float` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1.5` — float; Н1.1 keys — отказ text |
| `profile_table_key_integer` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1` — int; Н1.1 keys — отказ text |
| `profile_table_key_integer_string_pair` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1` и `"1"` — int и str; Н1.1 keys — отказ text |
| `profile_table_key_null` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `null` — null; Н1.1 keys — отказ text |
| `profile_unit_key_bool` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `true` — bool; Н1.1 keys — отказ text |
| `profile_unit_key_float` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1.5` — float; Н1.1 keys — отказ text |
| `profile_unit_key_integer` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1` — int; Н1.1 keys — отказ text |
| `profile_unit_key_integer_string_pair` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `1` и `"1"` — int и str; Н1.1 keys — отказ text |
| `profile_unit_key_null` | refused:text | text:K | value | ✓ | ✓ | value | ✓ | ✓ | value | ✓ | ✓ | скаляры | простой ключ: парсер читает `null` — null; Н1.1 keys — отказ text |

¹ — у PyYAML (а) среди путей отказа есть `lease.unconfirmed_max`: срабатывает и `off` общего фона (ниже).

81 случаев только у PyYAML (а) с одной причиной — `lease: {unconfirmed_max: off}` общего фона: YAML 1.1 читает `off` как false, форма ждёт слово или число (скаляры): `base`, `c2_crlf`, `c2_cut_at_host`, `c2_depth_64`, `c2_display_events_true`, `c2_form_fields_platform_id`, `c2_form_without_title`, `c2_leading_marker`, `c2_merge_override`, `c2_metrics_name_repeat`, `c2_null_upper`, `c2_plain_folded`, `c2_schema_known_keywords`, `c2_worker_deletes_own_rows`, `c3_about_sub_ok`, `c3_escape_ok`, `c3_near_by_ok`, `c3_schemes_ok`, `c3_tab_block_ok`, `c3_tab_in_comment_ok`, `c3_tab_quoted_ok`, `c4_dash_extra_spaces_ok`, `c4_display_fields_quoted_numeric_key`, `c4_door_pass_rows`, `c4_indentless_ok`, `c4_key_quoted_in_json_ok`, `c4_plain_apostrophe_ok`, `c5_default_tilde_ok`, `c5_rebalance_empty_ok`, `c8_options_enum_text_canonical`, `c8_options_enum_text_ok`, `c8_paths_canonical_order`, `c8_ref53_metrics_where_unit_field_unknown`, `c8_ref55_metrics_unless_table_unknown`, `c8_ref57_metrics_count_table_unknown`, `c8_ref58_rights_unit_of_table_unknown`, `c8_ref60_rights_reach_group_without_group_by`, `c8_ref61_servers_show_table_unknown`, `c8_ref64_servers_status_of_unknown`, `c8_ref78_console_running_not_metric`, `c8_ref83_worker_writes_table_unknown`, `c8_ref84_worker_writes_unit_rows`, `c8_requests_key_nested_brace`, `c9_flow_lone_dash_ok`, `c9_word_hash_inside_ok`, `c9_xclass_number_overflow`, `delete_after_with_about`, `display_fields_status_field`, `display_options_bool_enum`, `display_options_status_field`, `fields_affinity_known`, `fields_servers_show_known`, `inherit_map`, `int_field_boundaries`, `json_default_map`, `m49_int_2p53_minus_1_ok`, `m51_books_carried_ok`, `m51_books_merged_ok`, `m57_tokens_placement_ok`, `m57_tokens_scenario_ok`, `m57_tokens_unit_ok`, `m59_keys_display_unknown_id`, `m59_keys_ok`, `m59_names_exclusive_other`, `m59_names_grant_word`, `m59_names_no_book`, `m59_names_no_exclusive`, `m59_names_no_grant_ok`, `m59_names_no_slash`, `m59_names_ok`, `m59_names_on_carried_book`, `m59_names_on_kept`, `m59_names_unknown_key`, `m61_shared_ok`, `r39_group_by_known_field`, `requests_outcome_fetched_ok`, `requests_outcome_mark_ok`, `requests_stamp_group_without_group_by`, `unit_id_numeric`, `unplaced_delete_after_about_its_id`, `unplaced_delete_after_fixed_field`.

## Пути и строки (diagnostics.tsv) — не совпали

- PyYAML 6.0.3 (а): 40 — 40 случаев
- PyYAML 6.0.3 (б): 1 — `c8_word_hash_space`
- PyYAML 6.0.3 (в): 1 — `c8_word_hash_space`
- ruamel.yaml 0.19.1 (а): 7 — `m49_int_2p53`, `c4_key_int_and_string`, `c4_display_fields_numeric_key`, `c4_default_without_value`, `c8_int_4301_digits`, `c8_word_hash_space`, `c9_seq_dash_dash`
- ruamel.yaml 0.19.1 (б): 1 — `c8_word_hash_space`
- ruamel.yaml 0.19.1 (в): 1 — `c8_word_hash_space`
- yaml.v3 v3.0.1 (а): 7 — `m49_int_2p53`, `c4_key_int_and_string`, `c4_display_fields_numeric_key`, `c4_default_without_value`, `c8_json_default_overflow`, `c8_word_hash_space`, `c9_seq_dash_dash`
- yaml.v3 v3.0.1 (б): 1 — `c8_word_hash_space`
- yaml.v3 v3.0.1 (в): 1 — `c8_word_hash_space`

## Python и Go на одних файлах

### ruamel.yaml 0.19.1 (а) × yaml.v3 v3.0.1 (а): исход различен у 13, исход тот же при разном дереве — 3 (`c9_xclass_number_overflow`, `float_default_overflow`, `float_inherit_negative_overflow`)

| случай | ruamel.yaml 0.19.1 (а) | yaml.v3 v3.0.1 (а) |
|---|---|---|
| `c2_control_nel` | value required | text Y line 0: yaml: line 26: could not find expected ':' |
| `c3_tab_before_comment` | text Y line 1: while scanning for the next token | value required |
| `c3_tab_plain` | text Y line 25: while scanning for the next token | value required |
| `c3_u2028_plain` | value required | text Y line 0: yaml: line 26: could not find expected ':' |
| `c4_block_tab_content_ok` | ok  | text Y line 0: yaml: line 25: found a tab character where an indentation space is exp |
| `c4_doc_two_markers` | text Y line 2: expected a single document in the stream | value type: expected object |
| `c5_escape_U_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate_pair` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c8_int_4301_digits` | text Y line 0: library ValueError: Exceeds the limit (4300 digits) for integer string | value type: expected integer\|null |
| `c8_json_default_overflow` | value number out of scalars.tsv limits | ok  |
| `lease_huge_int` | ok  | value type: none of the variants |
| `yaml_two_documents` | text Y line 36: expected a single document in the stream | value required |

### ruamel.yaml 0.19.1 (б) × yaml.v3 v3.0.1 (б): исход различен у 10, исход тот же при разном дереве — 0

| случай | ruamel.yaml 0.19.1 (б) | yaml.v3 v3.0.1 (б) |
|---|---|---|
| `c2_control_nel` | value required | text Y line 0: yaml: line 26: could not find expected ':' |
| `c3_tab_before_comment` | text Y line 1: while scanning for the next token | value required |
| `c3_tab_plain` | text Y line 25: while scanning for the next token | value required |
| `c3_u2028_plain` | value required | text Y line 0: yaml: line 26: could not find expected ':' |
| `c4_block_tab_content_ok` | ok  | text Y line 0: yaml: line 25: found a tab character where an indentation space is exp |
| `c4_doc_two_markers` | text Y line 2: expected a single document in the stream | value key without a value |
| `c5_escape_U_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate_pair` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `yaml_two_documents` | text Y line 36: expected a single document in the stream | value required |

### PyYAML 6.0.3 (б) × yaml.v3 v3.0.1 (б): исход различен у 9, исход тот же при разном дереве — 0

| случай | PyYAML 6.0.3 (б) | yaml.v3 v3.0.1 (б) |
|---|---|---|
| `c3_tab_before_comment` | text Y line 1: while scanning for the next token | value required |
| `c3_tab_plain` | text Y line 25: while scanning for the next token | value required |
| `c4_block_tab_content_ok` | ok  | text Y line 0: yaml: line 25: found a tab character where an indentation space is exp |
| `c4_doc_two_markers` | text Y line 2: expected a single document in the stream | value key without a value |
| `c5_escape_U_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c5_escape_surrogate_pair` | value required | text Y line 0: yaml: line 25: found invalid Unicode character escape code |
| `c6_flow_map_empty_value` | value key without a value | key unknown key |
| `yaml_two_documents` | text Y line 36: expected a single document in the stream | value required |

### PyYAML 6.0.3 (б) × ruamel.yaml 0.19.1 (б): исход различен у 3, исход тот же при разном дереве — 0

| случай | PyYAML 6.0.3 (б) | ruamel.yaml 0.19.1 (б) |
|---|---|---|
| `c2_control_nel` | text Y line 27: while scanning a simple key | value required |
| `c3_u2028_plain` | text Y line 27: while scanning a simple key | value required |
| `c6_flow_map_empty_value` | value key without a value | key unknown key |

### ruamel.yaml 0.19.1 (в) × yaml.v3 v3.0.1 (в): исход различен у 3, исход тот же при разном дереве — 0

| случай | ruamel.yaml 0.19.1 (в) | yaml.v3 v3.0.1 (в) |
|---|---|---|
| `c3_tab_before_comment` | text Y line 1: while scanning for the next token | value required |
| `c3_tab_plain` | text Y line 25: while scanning for the next token | value required |
| `c4_block_tab_content_ok` | ok  | text Y line 0: yaml: line 25: found a tab character where an indentation space is exp |

### PyYAML 6.0.3 (в) × yaml.v3 v3.0.1 (в): исход различен у 4, исход тот же при разном дереве — 0

| случай | PyYAML 6.0.3 (в) | yaml.v3 v3.0.1 (в) |
|---|---|---|
| `c3_tab_before_comment` | text Y line 1: while scanning for the next token | value required |
| `c3_tab_plain` | text Y line 25: while scanning for the next token | value required |
| `c4_block_tab_content_ok` | ok  | text Y line 0: yaml: line 25: found a tab character where an indentation space is exp |
| `c6_flow_map_empty_value` | value key without a value | key unknown key |

### PyYAML 6.0.3 (в) × ruamel.yaml 0.19.1 (в): исход различен у 1, исход тот же при разном дереве — 0

| случай | PyYAML 6.0.3 (в) | ruamel.yaml 0.19.1 (в) |
|---|---|---|
| `c6_flow_map_empty_value` | value key without a value | key unknown key |


### Чем Python и Go расходятся — по видам

Сводка таблиц выше; числа — случаи корпуса.

| вид | случаи | Python (PyYAML, ruamel) | yaml.v3 | конфигурации |
|---|---|---|---|---|
| второй документ в файле | `c4_doc_two_markers`, `yaml_two_documents` | отказ «expected a single document» | `Unmarshal` молча берёт первый документ | а, б |
| TAB в простом слове и перед комментарием | `c3_tab_plain`, `c3_tab_before_comment` | отказ сканера | читает | а, б |
| TAB после отступа в первой строке блочного `\|` | `c4_block_tab_content_ok` | читает | отказ «found a tab character…» | а, б |
| U+0085 (NEL) и U+2028 в простом слове | `c2_control_nel`, `c3_u2028_plain` | ruamel читает; PyYAML отказывает | отказ | а, б |
| экранирование суррогата `\ud800`, `\U0000d800`, пара | `c5_escape_surrogate`, `c5_escape_U_surrogate`, `c5_escape_surrogate_pair` | читают в строку | отказ | а, б |
| `{k:}` в потоке | `c6_flow_map_empty_value` | PyYAML — ключ `k` без значения; ruamel — ключ `k:` | ключ `k:` | а, б |
| `1e999` в значении поля `json` | `c8_json_default_overflow` | бесконечность (`numbers`, отказ value) | строка `1e999` — поле json её принимает | только а |
| целое из 23 цифр | `lease_huge_int` | целое Python | float64 | только а |
| целое из 4301 цифры | `c8_int_4301_digits` | ValueError конструктора (предел `int()` CPython) | строка | только а |
| `1e309`, `-1e309`, `1e999` вне json | `float_default_overflow`, `float_inherit_negative_overflow`, `c9_xclass_number_overflow` | бесконечность | строка | только а; исход тот же, дерево разное |

В (б) деревья ruamel.yaml и yaml.v3 совпали на всех файлах, где оба парсера дали дерево; исходы разошлись на 10
файлах, все — отказ одного парсера и дерево другого (таблица «ruamel (б) × yaml.v3 (б)»).

В (в) ruamel.yaml и yaml.v3 расходятся на 3 файлах — все про TAB (`c3_tab_plain`, `c3_tab_before_comment`,
`c4_block_tab_content_ok`); PyYAML и ruamel.yaml — на 1 (`c6_flow_map_empty_value`). Общий остаток (в) у всех трёх
парсеров — 11 случаев, где норма Н1.1 отступает от YAML 1.2.2: `c5_key_long_1025_ok`, `c5_key_question_mark`,
`c5_value_question_mark`, `c5_unit_minus_word_ok`, `c9_flow_lone_dash_spaced`, `c5_value_next_line_flow`,
`c5_value_next_line_plain`, `c5_value_next_line_quoted`, `c7_seq_dash_scalar_below`, `c7_word_continuation_comment`,
`c8_word_hash_space`. Сверх них — дефекты парсеров: `c6_flow_map_empty_value` (ruamel.yaml, yaml.v3) и
`c4_block_tab_content_ok` (yaml.v3). Ещё 6 отказов вне `classes.tsv` у всех трёх парсеров в (в) получают класс,
иной, чем у эталона: `profile_blob_empty`, `c2_flow_map_key_without_colon`, `c2_flow_seq_pair`, `c4_hash_after_flow`,
`c4_hash_after_quote`, `c4_flow_word_with_colon` (у yaml.v3 ещё `c3_tab_plain`, `c3_tab_before_comment`).

### Поддерживаемый форк yaml.v3

`gopkg.in/yaml.v3` в архиве (README: «THIS PROJECT IS UNMAINTAINED»); поддерживаемый форк — `go.yaml.in/yaml/v3`
(v3.0.5, «Stable, frozen API; security fixes only», <https://github.com/yaml/go-yaml>, открыт 2026-10-26). Тот же
адаптер с форком (`go2/`, `measure.py --go-dir go2 --out results-go2.json`) дал на всех 630 файлах в (а), (б) и (в)
те же вердикт, класс и дерево, что и `gopkg.in/yaml.v3` v3.0.1: расхождений 0.

## Повтор

Скрипт и данные лежат вне репозитория: `~/.cache/yaml-corpus-pilot/` на машине замера
(`/home/slava/.cache/yaml-corpus-pilot/`): `measure.py` (стенд), `go/main.go`, `go/go.mod`, `go/go.sum` (адаптер
yaml.v3), `tables.py` (таблицы этой записки из `results.json`), `README.md`, копия YAML 1.2.2 `ext/yaml122.html`.

```sh
cd ~/.cache/yaml-corpus-pilot/go && go build -o yamlgo .
cd ~/.cache/yaml-corpus-pilot && UV_CACHE_DIR=~/.cache/uv uv run --no-project \
    --with 'ruamel.yaml==0.19.1' --with 'pyyaml==6.0.3' python -I measure.py
python3 tables.py > tables.md
```

Форк yaml.v3: `cd go2 && go build -o yamlgo .`, затем `measure.py --go-dir go2 --out results-go2.json`
(`go.sum`: `go.yaml.in/yaml/v3 v3.0.5 h1:N6y/pJk8buWs9NY5ERU2HSMfm+IuD/OtfdAnq6kESPw=`).
`measure.py --no-go` — только Python; `--course <путь>` — другой путь к курсу. Прогон занимает около 25 секунд.

Версии: курс — коммит `aee6716ea`; CPython 3.12.11 (через uv 0.13.5); ruamel.yaml 0.19.1; PyYAML 6.0.3;
go1.25.4 linux/amd64; gopkg.in/yaml.v3 v3.0.1 (`go.sum`: `h1:fxVm/GzAzEWqLHuvctI91KS9hhNmmWOoWu0XTYJS7CA=`).
Ссылки на стандарт — YAML 1.2.2, <https://yaml.org/spec/1.2.2/>, открыт 2026-10-26: § 7.3.3 продукция [130]
`ns-plain-char`, § 7.4.2 [147] `c-ns-flow-map-separate-value` и предел 1024 знаков неявного ключа, § 8.1.2
(`nb-char` [27] включает TAB), § 8.2.2 (тот же предел у блочного ключа), § 10.3.2 (разрешение тегов core).

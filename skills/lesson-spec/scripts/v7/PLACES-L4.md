# Место отказа по ключевому слову — стек В7 (V7-APPLICATOR-PATH-01; для LAYERS § 2 слой 4 и § 6)

Источник — `v7/stack.py` (`py_records`, `norm`, `canonical`): по нему построены набор А и векторы. Место — JSON Pointer
экземпляра; ответ — множество мест (повторы сливаются, порядок не важен). Ошибки библиотеки берутся верхнего уровня
(`iter_errors`, без `context` ветвей applicator). Ниже `O` — место узла, где стоит ключевое слово.

| Ключевое слово | Место отказа | Набор А: строк family-read / корпуса P/02.1 |
|---|---|---|
| `anyOf` (ни одна ветвь не прошла) | `O` — узел с applicator; места внутри ветвей не выдаются | 0 / 3 (`c2_metrics_neither`, `m57_tokens_no_scope`, …) |
| `oneOf` (ни одной или больше одной ветви) | `O` — как `anyOf` | 0 / 0 — слово в схемах не встречается |
| `not` | `O` | 25 / 53 |
| `required` | `O/<поле>` — каждое недостающее поле | 1279 / 18 |
| `additionalProperties: false` | `O/<ключ>` — каждый ключ вне `properties` и вне `patternProperties` (полное совпадение, слой 5) | 10 / 22 |
| `additionalProperties: {схема}` | прозрачно: места ошибок схемы на значении лишнего ключа | — |
| `propertyNames` (любая ошибка под ним, в т. ч. `anyOf`/`pattern`/`enum` внутри) | `O/<имя>`; места ниже отказанного имени (`O/<имя>/…`) не выдаются | 62 / 64 |
| схема `false` (ветвь `patternProperties`, дополнение `name_not_pattern`) | место значения: `O/<ключ>` | 0 / 5 (`profile_blob_65`, …) |
| `uniqueItems` | `O/<i>` — каждый элемент, равный более раннему (V7-UNIQUEITEMS-PAIR-01) | 8 / 7 — у всех один повтор; трёх равных нет |
| `type`, `enum`, `const`, `pattern`, `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `minItems`, `maxItems`, `minProperties`, `maxProperties` | `O` (`instanceLocation` ключевого слова по выходу JSON Schema 2020-12) | `type` 331 / 33, `enum` 148 / 34, `pattern` 556 / 34, `minimum` 78 / 5, `maximum` 52 / 3, `exclusiveMinimum` 0 / 1, `minItems` 0 / 4, `maxItems` 1 / 0, `maxProperties` 0 / 0; `const`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `minProperties` в схемах не встречаются |
| `dependentRequired`, `contains`, `unevaluatedProperties`, `unevaluatedItems` | `O` | в схемах не встречаются |
| `allOf`, `$ref`, `if`/`then`/`else`, `properties`, `patternProperties`, `items`, `prefixItems`, `dependentSchemas` | прозрачно: места ошибок подсхем на своих местах | есть: family-read — через `items` и `allOf`/`then`; корпус — через `allOf`/`then`, `items`, `patternProperties` |

Вне ключевых слов (не слой 4):
- слои 2–3 — место значения (кодек поля, время, целое по записи, `max_bytes`, имена сверх предела, число вне binary64): 457 / 14;
- строка не объект, текст объекта или файла не JSON (не UTF-8) — `""`: 223 / 0;
- ключ строки не по шаблону каталога — `""`, значение не судится (V7-FAMILY-KEY-PLACEHOLDER-01): строки `key: …` пакета;
- у писателя с `$defs.writer` — объединение мест обеих схем.

Пробелы набора А (по словам, что есть в схемах семей):
- `anyOf` вне `propertyNames` — одно место во всех семьях: `member-reported` (P/08, `sign_failures`: `anyOf` из двух
  `required`) — место `O`, не недостающее поле; таблица P/08 отложена (exceptions.tsv `family-read`), строки нет;
- `minItems` (108 в схемах семей) и `maxProperties` (2) — строк family-read нет, у `minItems` есть 4 строки корпуса;
- `uniqueItems` с тремя равными (два места) — строки нет ни в одном пакете;
- отброс мест ниже отказанного имени `propertyNames` — отдельной строки нет.

Счёт — по выгрузке main b2f143ab6 (family-read 01–06: 4739 строк без строк ключа; корпус P/02.1: 684 входа, отказ
слоя формы — 296). Строка попадает в счёт слова, если хотя бы одно её место дала ошибка этого слова.

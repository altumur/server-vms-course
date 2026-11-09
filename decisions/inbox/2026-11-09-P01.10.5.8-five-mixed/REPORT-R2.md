# P01.10.5.8, возврат: строка agent-carry в P/09 forms

**Вывод.** Из строки 52 таблицы портов P/09 (EN и RU) в судейский файл ушла только одна фраза с конкретными значениями фикстуры возраста relay. Общий договор порта не тронут. Новых полей нет, вопрос Архитектору не нужен.

Родитель в main: `56408a4a111e5ffa7d75002939841d0a985f5885`. Основание: возврат SRC, запись `P011058-C803-SRC-COMPONENT-AND-REMAINING-P09-DISPOSITION-20261109.json`.

## Что перенесено

| Было в README | Стало в README |
|---|---|
| The relay-age fixture has prior as_of 100, receipt 200, domain_age 100 and unchanged content. | The relay-age fixture gives the prior as_of, the receipt time and domain_age, with unchanged content. |

Исходная фраза лежит побайтно в `Platform/09-agent/forms/README.cases.md`, русская — в `Platform/09-agent/ru/forms/README.cases.md`. Обе — точные подстроки исходных строк.

## Почему это не константы порта

Эти числа приходят во входе самого шва: строка `s18-relay-age` файла `acceptance/1/seams.tsv` несёт поля `prior_as_of`, `received_at`, `domain_age`. Значит, это значения случая, а не обязательные константы, и адаптеру не нужны новые поля. Названия величин в README сохранены.

## Что осталось публично

Вся остальная строка без изменений: настоящий копировщик и CAS, сырые байты, хеш, метка, наблюдения при отказе и все имена полей (`at_lexeme`, `item_at_bytes`, `copy_writes`, `marker_confirmed`, `initial`, `attempts`, `advertised`, `computed_sha256`, `copy_items`, `copy_index`, `taken_sha256`, `related_edits`).

## Проверки

`en_mirror.compare` по двум парам — 0 ошибок. `check_cyrillic` — PASS. Изменены только четыре файла и файлы этого отчёта. Полная проверка, native, модели и выгрузки не запускались.

Новых путей только для судьи нет: дополнены уже переданные файлы. Новые блобы: `RELOCATION-MAP-R2.json`.

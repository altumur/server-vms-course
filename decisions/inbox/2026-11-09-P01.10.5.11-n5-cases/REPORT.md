# P01.10.5.11: N5 P/06–P/10 — та же граница нормы и случаев, что у P/01–P/05

**Вывод.** В разделах N5 и чеклистах готовности 23 норм P/06, P/08, P/09, P/10 и их зеркал описания случаев и пары сценарий/шаг → исход перенесены побайтно в соседние `*.n5.cases.md`. Нормы, параметры стенда, критерии готовности и ссылки на сценарии остались публично. Новых норм, чисел, форматов, маршрутов и флагов нет. Данные `scenarios.tsv` и `seams.tsv` не менялись. Проб и полной проверки не было.

База: `05d135a6f2745798ab21fc0b2d29e92572ee2693`.

## Что изменено

| Норма | Было | Стало | Отрывков |
|---|---|---|---|
| `06.1-console` | `3e96b3524f` | `4c36d28413` | 19 |
| `06.2-console` | `0eb481f389` | `3b8fd81ec0` | 1 |
| `06.3-console` | `b640e16705` | `09c1a4ac59` | 3 |
| `06.4-console` | `856d291e00` | `9e14b71081` | 4 |
| `06.5-console` | `765653726c` | `e890c8e3ec` | 10 |
| `06.6-console` | `dfb3afb2f3` | `4e3c1ec520` | 5 |
| `06.7-console` | `ef2e0009b8` | `ded19a8380` | 4 |
| `06.8-console` | `65620280d5` | `2199a30d04` | 10 |
| `06.9-console` | `de21909e7b` | `2e4a48467d` | 2 |
| `08.1-domain` | `416db13471` | `233d6d34aa` | 2 |
| `08.10-domain` | `f66252e121` | `49f8b692d4` | 1 |
| `08.2-domain` | `2b3d912958` | `788dc1788d` | 1 |
| `08.3-domain` | `39a5485547` | `7aaf2e732e` | 1 |
| `08.4-domain` | `73d92b9f9a` | `7335e9c35f` | 2 |
| `08.5-domain` | `1e943855b8` | `6c848b38f9` | 1 |
| `08.6-domain` | `543f978d4d` | `ab9a21d2db` | 3 |
| `08.7-domain` | `c18cf26f17` | `faf9e3de3b` | 4 |
| `08.8-domain` | `bb0c504a19` | `1fa4aff3b2` | 3 |
| `09.1-agent` | `61036d4342` | `3f1363407a` | 2 |
| `09.2-agent` | `210f6618eb` | `4f5a8086bc` | 1 |
| `10-domain-console` | `74e2c3a102` | `4ccf88f74b` | 1 |

`08.0` и `08.9`: снимать нечего, файлы не правились. У русских зеркал то же разделение. Точные блобы, хэши и каждый вынесенный отрывок: `RELOCATION-MAP.json`, текста случаев в карте нет.

## Единое правило

Правило то же, что у P/01–P/05 (коммит `dcd531bbf`):

- **Осталось публично.** Правило с кодом и ссылка на сценарий («… — 503 — sc. 13»), имена и число сценариев (ADR-0133 доп. (4) п. 3), таблицы N5 вида имя → якорь нормы без описания случая, причины «checked by reading», идентификаторы пунктов чеклиста.
- **Ушло.** Пары шаг → исход с номером шага, описания и подготовка конкретных случаев, столбцы покрытия векторов.
- **Места из С1:** `09.1` и `10` (таблицы имя → якорь сохранены, описание шагов строки 02 снято), `06.5` (пара шаг → 503 снята, код остаётся в общей норме `/where`).
- Таблицы N5 не оставлены частично: `check_spec` требует всю таблицу или ни одной строки.

## Проверки

| Проверка | Итог | Предел |
|---|---|---|
| Сверка с базой | вне названных строк без изменений; отрывки равны исходным | только байты |
| `en_mirror.compare`, 42 пары (нормы и `*.n5.cases.md`) | 0 ошибок | факты и форма, не перевод |
| идентификаторы чеклиста и указатель на `*.n5.cases.md` | порядок сохранён, указатель один на файл | счётчики |
| `check_cyrillic` | PASS | только буквы |

Содержательные правки сделаны фоновым агентом, итоговый текст прочитан мной.

## На что смотреть при приёме

- В чеклистах остаются пары «правило — код — sc. N» без номера шага: так же сделано у P/01. Если нужно строже, это единое решение для всех уроков.
- `06.4` P/06.4-06, `06.1` строки 1055–1056 и 1060–1062: сняты привязки подготовки к конкретным сценариям.

## Новые файлы только для судьи

- `Platform/06-console/spec/06.1-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.1-console.n5.cases.md`
- `Platform/06-console/spec/06.2-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.2-console.n5.cases.md`
- `Platform/06-console/spec/06.3-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.3-console.n5.cases.md`
- `Platform/06-console/spec/06.4-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.4-console.n5.cases.md`
- `Platform/06-console/spec/06.5-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.5-console.n5.cases.md`
- `Platform/06-console/spec/06.6-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.6-console.n5.cases.md`
- `Platform/06-console/spec/06.7-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.7-console.n5.cases.md`
- `Platform/06-console/spec/06.8-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.8-console.n5.cases.md`
- `Platform/06-console/spec/06.9-console.n5.cases.md`
- `Platform/06-console/ru/spec/06.9-console.n5.cases.md`
- `Platform/08-domain/spec/08.1-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.1-domain.n5.cases.md`
- `Platform/08-domain/spec/08.10-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.10-domain.n5.cases.md`
- `Platform/08-domain/spec/08.2-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.2-domain.n5.cases.md`
- `Platform/08-domain/spec/08.3-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.3-domain.n5.cases.md`
- `Platform/08-domain/spec/08.4-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.4-domain.n5.cases.md`
- `Platform/08-domain/spec/08.5-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.5-domain.n5.cases.md`
- `Platform/08-domain/spec/08.6-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.6-domain.n5.cases.md`
- `Platform/08-domain/spec/08.7-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.7-domain.n5.cases.md`
- `Platform/08-domain/spec/08.8-domain.n5.cases.md`
- `Platform/08-domain/ru/spec/08.8-domain.n5.cases.md`
- `Platform/09-agent/spec/09.1-agent.n5.cases.md`
- `Platform/09-agent/ru/spec/09.1-agent.n5.cases.md`
- `Platform/09-agent/spec/09.2-agent.n5.cases.md`
- `Platform/09-agent/ru/spec/09.2-agent.n5.cases.md`
- `Platform/10-domain-console/spec/10-domain-console.n5.cases.md`
- `Platform/10-domain-console/ru/spec/10-domain-console.n5.cases.md`

# P01.10.5.10: случаи из 21 README приёмки P/06–P/10 только в J

**Вывод.** Все 21 английский README и 21 русское зеркало прочитаны. В каждом нашлись случаи или привязки к сценариям. Общий протокол стенда, формы, команды и обязанности остались публично. Описания выбранных сценариев, привязки шаг → исход, литералы ожиданий и приватные хэши перенесены побайтно в соседние `README.cases.md`. Новых норм, чисел, форматов, маршрутов и флагов нет. Проб, полной проверки, моделей и выгрузок не было.

База разделения и карты: `a4983156707648ad2d189357ba18d4659acb90d7`. Опубликовано поверх main `d2811d86c07b98f37e9ffaab5167e1e8cc7d4bc7`; 84 файла разделения между этими коммитами не менялись.

## Что изменено

| README приёмки | Было | Стало | Отрывков |
|---|---|---|---|
| `06-console/acceptance/1` | `19ad38625e` | `0c637a69c0` | 16 |
| `06-console/acceptance/2` | `4e03ed51b3` | `0eb5be4ce5` | 4 |
| `06-console/acceptance/3` | `11b5301e4c` | `18efd75571` | 1 |
| `06-console/acceptance/4` | `514d6b66e6` | `3aac336ef7` | 6 |
| `06-console/acceptance/5` | `a1f258a3c3` | `c1047f7907` | 18 |
| `06-console/acceptance/6` | `7d903f315a` | `9f547c8e56` | 14 |
| `06-console/acceptance/7` | `d177ff7e7a` | `afed5cf085` | 7 |
| `06-console/acceptance/8` | `dc2367b14c` | `6d9c4b9a65` | 4 |
| `06-console/acceptance/9` | `599fffc417` | `a8436ba1b8` | 1 |
| `08-domain/acceptance/1` | `c3108a8434` | `42289c5888` | 3 |
| `08-domain/acceptance/10` | `1c0589f8c4` | `c36cc74328` | 1 |
| `08-domain/acceptance/3` | `fa25103523` | `f6827286f7` | 8 |
| `08-domain/acceptance/4` | `c986da9f78` | `b86c7e78de` | 4 |
| `08-domain/acceptance/5` | `9cfa07275e` | `c9cab7062d` | 5 |
| `08-domain/acceptance/6` | `0f98a5dc31` | `2f39270f76` | 4 |
| `08-domain/acceptance/7` | `365cf5a11d` | `a0a8ef0da3` | 4 |
| `08-domain/acceptance/8` | `6ea31ca046` | `718f251637` | 5 |
| `08-domain/acceptance/9` | `54656975b0` | `1b1f5b85bb` | 2 |
| `09-agent/acceptance/1` | `9825351283` | `86903b3d55` | 7 |
| `09-agent/acceptance/2` | `c19dd93059` | `2ee229bf08` | 1 |
| `10-domain-console/acceptance` | `deb67db12d` | `ecd0d72ee1` | 9 |

У каждого русского зеркала то же разделение. Точные блобы, хэши и каждый вынесенный отрывок: `RELOCATION-MAP.json`. Карта содержит только хэши, текста случаев в ней нет.

## Как проходила граница

- **Осталось публично:** как поднять стенд, общие подготовка и порядок, директивы и двери, общие правила проверки, что читается вручную и почему, ссылки на договоры и отчётливо общие обязанности.
- **Вынесено:** номера сценариев с их содержанием, связи шаг → исход, значения фикстур и ожиданий. Три литерала из ревью ушли полностью.
- **Счёт сценариев и шагов** оставлен: ADR-0133 доп. (4) п. 3 допускает число случаев.
- **Имена швов** `s05…s08` из `06/8` вынесены: по ADR-0126 доп. (11) п. 6 открыто только имя в ячейке gate, а там `*`.
- **Пароль стенда** оставлен в трёх файлах как общая подготовка, он не привязан к сценарию.
- **Заголовки.** Разделы, ставшие пустыми, сняты; входящих ссылок на них нет. Заголовки с номерами сценариев заменены такими же без номеров. Якорь `#forwarding-credential-seams` не менялся.

## Проверки

| Проверка | Итог | Предел |
|---|---|---|
| Сверка с родителем | вне названных строк без изменений; отрывки равны исходным | только байты |
| `en_mirror.compare`, 42 пары (README и `README.cases.md`) | 0 ошибок | факты и форма, не перевод |
| `check_cyrillic` | PASS | только буквы |

Содержательные правки сделаны фоновым агентом и прочитаны мной целиком в виде итогового текста. Четыре места я поправил: одна формулировка была шире исходной, в трёх оставались имена швов, исход шага и число векторов.

## Что нужно от других

1. **Новые файлы только для судьи** (передать составителю фильтра):

- `Platform/06-console/acceptance/1/README.cases.md`
- `Platform/06-console/ru/acceptance/1/README.cases.md`
- `Platform/06-console/acceptance/2/README.cases.md`
- `Platform/06-console/ru/acceptance/2/README.cases.md`
- `Platform/06-console/acceptance/3/README.cases.md`
- `Platform/06-console/ru/acceptance/3/README.cases.md`
- `Platform/06-console/acceptance/4/README.cases.md`
- `Platform/06-console/ru/acceptance/4/README.cases.md`
- `Platform/06-console/acceptance/5/README.cases.md`
- `Platform/06-console/ru/acceptance/5/README.cases.md`
- `Platform/06-console/acceptance/6/README.cases.md`
- `Platform/06-console/ru/acceptance/6/README.cases.md`
- `Platform/06-console/acceptance/7/README.cases.md`
- `Platform/06-console/ru/acceptance/7/README.cases.md`
- `Platform/06-console/acceptance/8/README.cases.md`
- `Platform/06-console/ru/acceptance/8/README.cases.md`
- `Platform/06-console/acceptance/9/README.cases.md`
- `Platform/06-console/ru/acceptance/9/README.cases.md`
- `Platform/08-domain/acceptance/1/README.cases.md`
- `Platform/08-domain/ru/acceptance/1/README.cases.md`
- `Platform/08-domain/acceptance/10/README.cases.md`
- `Platform/08-domain/ru/acceptance/10/README.cases.md`
- `Platform/08-domain/acceptance/3/README.cases.md`
- `Platform/08-domain/ru/acceptance/3/README.cases.md`
- `Platform/08-domain/acceptance/4/README.cases.md`
- `Platform/08-domain/ru/acceptance/4/README.cases.md`
- `Platform/08-domain/acceptance/5/README.cases.md`
- `Platform/08-domain/ru/acceptance/5/README.cases.md`
- `Platform/08-domain/acceptance/6/README.cases.md`
- `Platform/08-domain/ru/acceptance/6/README.cases.md`
- `Platform/08-domain/acceptance/7/README.cases.md`
- `Platform/08-domain/ru/acceptance/7/README.cases.md`
- `Platform/08-domain/acceptance/8/README.cases.md`
- `Platform/08-domain/ru/acceptance/8/README.cases.md`
- `Platform/08-domain/acceptance/9/README.cases.md`
- `Platform/08-domain/ru/acceptance/9/README.cases.md`
- `Platform/09-agent/acceptance/1/README.cases.md`
- `Platform/09-agent/ru/acceptance/1/README.cases.md`
- `Platform/09-agent/acceptance/2/README.cases.md`
- `Platform/09-agent/ru/acceptance/2/README.cases.md`
- `Platform/10-domain-console/acceptance/README.cases.md`
- `Platform/10-domain-console/ru/acceptance/README.cases.md`

2. **`check_spec`.** Перечень `supported` в `acceptance()` не содержит `README.cases.md`; строка уже нужна P/02 acceptance/2–5, а теперь и этим 21 каталогу. Правка — у владельца проверок. Я `check_spec` не запускал и не правил.

C и M/J не выбирались.

# Предварительное ревью черновика фильтра выгрузки: Claude

Задача `P01.34`. Предмет: `Platform/common/export-model-filter.json`, редакция sha256 `afa97e6e28ebeb28c9466ade9ac0e5f9718e80e3cc111492e4a6ddd36859dfad` (коммит `95a4c77ba`, ветка `coord103-src/p011072-filter-da7d8053-20261109`, срез Source `da7d80534`). Отдельный раздел: дельта к редакции `f5f39057` (коммит `06c94551c`). Основание: ADR-0133 доп. (3), (4), (6) п. 2; ADR-0126 доп. (11) п. 5; ADR-0135 доп. (2) п. 2. Код черновика, его валидаторы и пробы не запускались; выполнялись только чтение данных и счётчики над ними. Отчёты других рецензентов не читались.

**Вывод: черновик нужно поправить в одном классе файлов до окончательного ревью `P01.10.8`; механика фильтра годна.** Счёт: **Б1 / С4 / М1.**

Механика: 3300 записей, ровно 3298 файлов `Platform` на срезе плюс объявленные `Platform/COURSE_COMMIT` и сам фильтр; лишних и пропавших нет; пути `VMS/` и `Source/` не встречаются. Фильтр — J-only, в M нет упоминаний фильтра, `stages.kit` и `tools/normgen`.

## Блокер

### Б1. README приёмки P/06, P/08–P/10 (21 файл) идут в M; в 16 подтверждены случаи, в трёх — ожидаемые ответы

**Место.** Записи `Platform/06-console/acceptance/{1..9}/README.md`, `Platform/08-domain/acceptance/{1,3..10}/README.md`, `Platform/09-agent/acceptance/{1,2}/README.md`, `Platform/10-domain-console/acceptance/README.md`, `disposition: model_and_judge`, основа «Reused accepted semantic role inventory». Ни один из них нет в `UNRESOLVED-CURRENT-MEMBERSHIP-CONDITIONS.json` и в `CURRENT-KNOWN-MIXED-M-BLOCKERS.json`.

**Нарушенный источник.** ADR-0133 доп. (4) п. 3: README приёмки идёт в M «да, если без случаев»; «Файл, где правило смешано со случаями: случаи выносятся, файл идёт в M»; «Ожидаемые ответы недопустимы». Доп. (1) п. 1: «Векторы и сценарии — только у судьи».

**Контрпример, сверено с `scenarios.tsv` на срезе.**

| Файл:строка в M | Цитата | Та же величина в J |
|---|---|---|
| `06-console/acceptance/5/README.md:42` | «Sc. 27 step 4: the hash `sha256-Fv4QBmn4e5D3uUQvTmVKsZm0dTPMrjp+nycLTD2M1wc=`» | `06-console/acceptance/5/scenarios.tsv:251`, столбец ожидания шага 4 сценария `27-mounted-shell` |
| `06-console/acceptance/6/README.md:59` | «sc. 08 waits for `understood: 1`, sc. 11 — `understood: 1`, `can_raise_to: 1`» | `06-console/acceptance/6/scenarios.tsv:67`, `:97`, столбец ожидания |
| `09-agent/acceptance/1/README.md:74` | «sha256 `eec6d36c2e9636846f2d335daf072c791c8022e1e714091f05fe56e4b2380434` — in the row `domain/backup-taken` of step 5» | `09-agent/acceptance/1/scenarios.tsv:157`, `:160`: шаг 8 ожидает ту же строку |

Остальное прочитанное — описание случаев по номерам: подготовка стенда для сценария, что наблюдает шаг. Например `08-domain/acceptance/4/README.md:27`: «Scenario 29 step 13: moving `root` to an assignment through a group gives a new `at`, and the former token does not serve step 4a»; `06-console/acceptance/9/README.md:20`: «Sc. 04–06, 08–13 of the plan table — by reading».

Тот же вид файла в P/01, P/03–P/05 и в `common/acceptance/{ops,pass,system,tls}` черновик сам относит к смешанным и уводит в J (`Proposed whole mixed case/acceptance`), у P/02 acceptance/2–5 случаи вынесены в `README.cases.md`. P/06–P/10 остались на основе, взятой из прежней описи ролей: граница проходит по уроку, а не по содержимому.

| Файл | Упоминаний `sc.`/шагов | Как проверен |
|---|---|---|
| 06/1, 06/2, 06/4, 06/5, 06/6, 06/7, 06/8, 06/9 | 16/9, 6/0, 3/0, 39/8, 22/5, 10/0, 4/1, 2/0 | строки по шаблону, случаи подтверждены; 06/5 и 06/6 — с литералами |
| 08/3, 08/4, 08/6 | 16/5, 10/9, 9/3 | то же |
| 09/1, 10 | 17/3, 14/3 | то же; 09/1 — с литералом |
| 08/5, 08/7, 08/8 | 9/1, 1/4, 3/0 | строки по шаблону при приёме отчёта: случаи подтверждены, например `08/7:28` «step 02/3 — a foreign role asks for a kind that was not given to it», `08/8:24` «Step 13 waits (`@until`) for its forgotten keys» |
| 06/3, 08/1, 08/9, 08/10, 09/2 | 1/0, 2/0, 0/3, 0/0, 4/0 | строки по шаблону при приёме отчёта: номера сценариев, ссылки и подготовка стенда, исходов шагов в найденных строках нет; решать при разделении, файл целиком не читан |

**Последствие.** Модель получает литералы ожиданий и описание сценариев, которых по доп. (1) у неё быть не должно. Проба на такой M недействительна по классу «M несёт материал только для судьи» (ADR-0133 доп. (6) п. 4). Отдельный риск: нормы и README, на которые модель опирается, опираются на те же сценарии.

**Рекомендация.** Для всех 21 файла тот же приём, что у P/02: случаи — в `README.cases.md` (`judge_only`), общее описание стенда — в `README.md` (`model_and_judge`), либо весь файл `judge_only` с названным публичным носителем, как у P/03–P/05. До этого добавить их в перечень условий черновика. Три литерала выше вычистить в любом случае. Указатели 08/0, 08/2, 03/1, 03/7 (по 400–500 байт) по счётчику случаев не содержат, содержимым не читаны; остаются в M, если проверка это подтвердит.

## Существенные

### С1. Деление N5 разное по урокам: таблицы «сценарий → норма» у P/01–P/05 в J, у P/06–P/10 в M

**Место.** `*.n5.cases.md` (`judge_only`) есть только у P/01–P/05: 12 файлов (без `ru/`); ни одного у `06-console`, `08-domain`, `09-agent`, `10-domain-console`. `01-store/spec/01.1-store.n5.cases.md:5`: «These case descriptions and their outcomes are judge-only data.»

**Контрпример.** Таблица случаев N5 остаётся в M у `09-agent/spec/09.1-agent.norms.md:1584` («| 01 | `01-quiet-member` | N1.4 `home_write`, `fresh`; …») и `10-domain-console/spec/10-domain-console.norms.md:499` («| 02 | `02-silent-member` | N1.8; steps 04, 09 (delivery) …»), тогда как такая же таблица P/01 вынесена. Чек-листы N5 связывают шаг с исходом: `06-console/spec/06.5-console.norms.md:844`: «in TSV only the absence, sc. 04 step 5, and an unreadable intent — 503, sc. 07 step 3».

**Нарушенный источник и граница.** ADR-0133 доп. (4) п. 3 допускает «Имена и число случаев в нормах». Поэтому имена сами по себе не утечка, и блокером это не считаю. Но исход шага рядом с его номером — уже «случай или ожидаемый ответ» по тому же пункту, а `.n5.cases.md` прямо называют такие описания материалом судьи.

**Рекомендация.** Выбрать одно правило на все уроки. Либо провести деление N5 и в P/06–P/10 (норма в `*.norms.md`, таблицы и пары «шаг → исход» в `*.n5.cases.md`), либо записать, что имена и исходы норм в N5 допустимы, и тогда объяснить, зачем вынесены таблицы P/01–P/05. Решает автор деления (ADR-0083 (151)), спорное — Архитектор.

### С2. В M лежат хэши файлов, которые есть только в J

**Место.** `08-domain/vectors/assemble/README.md:40–41`, `08-domain/vectors/view/README.md:44–45`, `model_and_judge`.

**Цитата.** «| `testsub` | [`Platform/common/data/testsub/testsub.subsystem.yaml`](…) | `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b` |».

**Нарушенный источник.** ADR-0133 доп. (3) п. 4: «В M нет объектов J, ссылок на него, перечня фильтра и хэшей случаев судьи»; доп. (4) п. 6: «Перечня фильтра и хэшей случаев в M нет». Манифесты `testsub` у черновика `judge_only`.

**Контрпример.** Сверка sha256 всех файлов J с 40- и 64-значными токенами M находит эти два манифеста в двух файлах и `backup-foreign-term.json` в `09-agent/acceptance/1/README.md:74` (закрывается Б1). Токен `e3b0c442…` в `common/data/README.md:65` — хэш пустой строки, совпадение случайное, не находка.

**Рекомендация.** Вынести таблицы хэшей в `README.cases.md` этих пакетов. `check_spec` сверяет хэши в README векторов с байтами, на которые они ссылаются (`check_spec.py`, правило `C08-VEC-MANIFEST-SHA-01`), поэтому перенос затронет эту проверку. Либо, если манифесты `testsub` признают правилом, а не случаем, перевести их в M и записать это решение; тогда нужен общий пересмотр `common/data/testsub/*`.

### С3. Маркер и состав J не сходятся с действующей раскладкой выгрузки

**Место.** Запись `Platform/COURSE_COMMIT`, основа: «Existing declared export marker equals selected full source C SHA plus LF in both views». `own_export_markers: []`.

**Контрпример.** В голом хранилище выгрузок (`/home/pilot/cammeta-specs`, ветка `exports`) маркер лежит в корне: `COURSE_COMMIT`; пути `Platform/COURSE_COMMIT` там нет. В корне той же выгрузки также `README.md`, `Source/`, `VMS/`, `tools/`, `changes/`, `.gitignore`, `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md`, `НОРМАТИВНЫЕ-СЛОВА.md`. Перечень фильтра содержит только `Platform/**`. ADR-0133 доп. (4) п. 4 требует: «Фильтр над J даёт дерево M», «Маркер `COURSE_COMMIT` обеих выгрузок равен C».

**Предел вывода.** Раскладка новой J могла быть решена иначе; такого решения в прочитанных основаниях нет.

**Последствие.** Либо проверка пары не найдёт маркер, либо J с нынешней раскладкой не пройдёт сверку полноты перечня.

**Рекомендация.** Записать путь маркера и точный корень J. Если J остаётся в нынешнем виде, назвать корневые файлы в перечне или в правиле области действия фильтра.

### С4. В дельте `f5f39057` столбцы и якоря судьи идут в M вопреки делению ADR-0135

Вынесено отдельно, см. раздел ниже. Считается одной находкой.

## Мелкая

### М1. `01-store/probes/README.md` называет публичными код, которого в M нет

`01-store/probes/README.md:3`, `model_and_judge`: «These are the public observation checkers of [production acceptance]». Строки ниже дают команды `python3.12 -B -m store_probes …`, а `01-store/probes/{copy_stream,store_fitness,store_probe_http,store_probes}.py` — `judge_only`. Правило само по себе (читать наблюдения) остаётся, но модель получает инструкцию, которую не может выполнить, и слово «public» неверно для M. Рекомендация: оставить в M только договор наблюдений либо убрать команды запуска.

## Дельта к редакции `f5f39057`: `runner-targets.tsv` и `runner-targets.README.md`

Две новые записи `model_and_judge` (коммит `06c94551c`). Проверено против ADR-0135 доп. (2) п. 2: `targets.tsv` в M — «цель, владелец, `stand.*`, keys, абзац нормы, флаги для модели»; `targets.routing.tsv` в J — «движок, каталог, диапазон, части других уроков»; «столбец принадлежит одному файлу». Таблица разобрана целиком: 224 строки, 18 столбцов.

Что соблюдено: столбцов каталога, диапазона и глав нет; `conditional_requirements` (31 непустая строка, просмотрены две) несёт режимы команд, а не перечень случаев.

**С4.** Что расходится:

1. **`driver` — это движок.** Значения `store-door`, `store-extra`, `console-2`, `pass-stand`, 126 различных. По ADR-0135 движок принадлежит J.
2. **`runner_anchors`** — 1077 якорей в код раннера, путь, диапазон строк, sha256 и пин: `runner/c_targets.py`, `runner/c_execute.py`, `runner/c_vector_packages.py`, … Пример: `{"header": "STORE_TARGETS", "path": "runner/c_targets.py", "physicalLF": [61, 81], "role": "public-reader-code"}`. В перечне столбцов M у ADR-0135 этого нет. По существу это подсказка к внутреннему устройству судьи: ADR-0133 п. 1 не даёт модели реализаций, а ADR-0135 доп. (2) п. 1 исключает код раннера даже из входа линии судьи.
3. **`readme_anchors` ведут в J:** 93 якоря на 5 файлов `judge_only` (`01-store/acceptance/{1,2,3}/README.md`, `02-installer/acceptance/1/README.md`, `common/vectors/door-token/README.md`) с `rawSHA256`. ADR-0135 разрешает «абзац нормы», а не адрес и хэш файла, закрытого от модели; ADR-0133 доп. (3) п. 4 запрещает хэши случаев судьи. Сам файл README приёмки не случай, поэтому формально это слабее, чем С2, но модели эти якоря бесполезны.
4. **Имя файла** `runner-targets.tsv`, у ADR-0135 — `targets.tsv`. Файл routing отсутствует.

Запись карты коммита указывает, что эти два файла выбраны корнем по явному сообщению («Explicit Root message 2026-11-09: exact2boundedpubliccarriers»); поэтому находка оформлена как **вопрос Архитектору**, а не требование правки. Рекомендация: разделить таблицу по ADR-0135 доп. (2) п. 2: в M цель, владелец, `stand_commands`, `stand_addresses`, `vectors`, `adapters`, `keys`, `requires_any`, `conditional_*`, якоря только к M; в J `driver`, `runner_anchors`, якоря к J, служебные столбцы регистрации.

## Проверено, находок нет

- **`stages.kit.tsv` (ADR-0126 доп. (11) п. 5):** 9 файлов, все `judge_only`; в P/07 такого файла на срезе нет; в M упоминаний нет.
- **Переводы `ru/`:** 300 файлов, все `judge_only`, ни одного пути `ru/` в M. Расхождения диспозиции «источник ↔ перевод» в опасную сторону (перевод случая в M) нет. В M кириллица заметна только в `07-console-module/data/localization.tsv`, это данные интерфейса.
- **Формы в M:** заголовки всех `.tsv` в `forms/`, `data/`, `spec/` — правила (`refusals`, `daemon-flags`, `runtime-constants`, `stages`, `write-checks`, `*.outcomes`, `*.layers`, `catalog`, `codec`…). `key-placeholders.tsv` со столбцом `example` — именованные примеры нормы. JSON-схемы без `examples`.
- **Потеря норм для M.** Из `judge_only` без отметки в UNRESOLVED просмотрены кандидаты: `common/vectors/may/README.md` (правило уже в `contracts/may-input.md`), `common/vectors/secret-in/fields.yaml` («Acceptance data»), `common/data/cell-json-sha256.tsv`, `06-console/forms/deletion-body-witnesses.json`, `01-store/forms/write-checks.probes.tsv` (правило в `write-checks.tsv`, входы — случаи), `02-installer/forms/finite-profile-skeletons/*`, `module-design.md`, `common/data/testsub/README.md`, `common/acceptance/system/inputs/cluster.json`. Правила, которого нет в M, в прочитанной части не нашёл. Ссылки M на J (115 целей, 492 вхождения) — текстовые ссылки на снятые файлы; доп. (4) п. 6 их допускает.
- **Литералы между M и J вне С2 и Б1** — в основном идентификаторы находок (`C06-…`) и имена метрик/случаев, которые нормы называть могут.

## Уже названо SRC и не считается

15 общих README `common/vectors/*` (`P01.10.5.6`); абзац P03 forms LF103 (`P01.10.5.7`); условия `UNRESOLVED`: 44 записи `PUBLIC_GENERIC_ABI_AND_ROOT_WHOLE_J_CHOICE_REQUIRED` (в том числе `common/acceptance/{ops,pass,system,tls}/README.md`, README P/01, P/03–P/05, 06-console и 10-domain-console spec README), 7 `ROOT_CURRENT_PUBLIC_AFTERBLOB_ROLE_CONFIRMATION`, 4 `ROOT_EXPLICIT_NORMATIVE_EXAMPLE_OR_LIBRARY_DOCUMENT_ROLE_CHOICE`.

## Покрытие и пределы

Счётчики над данными (не чтение): все 734 файла M, существующие на срезе (`COURSE_COMMIT` в дереве нет), — заголовки таблиц, ключи `examples` в JSON, упоминания `sc./step`, токены-хэши; все файлы J — sha256; файлы J без `ru/` — токены.

Прочитано содержимым, не целиком, а заголовками и строками по шаблону:

- **M — 43 файла:** 21 README приёмки Б1 (строки), N5 шести норм (`01.1`, `06.1`, `06.5`, `08.4`, `09.1`, `10`), 5 README векторов (`store-client`, `journal`, `fault`, `platform-lists`, `secret-in`), `may-input.md`, `source-cells.md`, `probes/README.md`, строки `common/acceptance/README.md`, хэш-строка `common/data/README.md`, строки `08-domain/vectors/{assemble,view}/README.md`, строки `06.8` и `02.3`, начала `write-checks.tsv` и `consumers.tsv`.
- **J — 13 файлов:** 10 перечисленных кандидатов на потерю норм, `01.1-store.n5.cases.md`, три `scenarios.tsv` для сверки литералов.

Только классифицировано по пути и счётчикам: остальные 692 файла M (данные `data/` — только заголовки) и 2552 файла J. Поэтому раздел «Потеря норм для M» относится только к 13 прочитанным файлам J: из 44 записей «Proposed whole mixed» содержимым прочитаны не все; это предварительное ревью, полная проверка остаётся за `P01.10.8`.

При приёме отчёта отдельно перепроверены: sha256 редакции; диспозиция `model_and_judge` всех 21 файла Б1 и их отсутствие в `UNRESOLVED`; три литерала Б1 по файлам; отсутствие `Platform/COURSE_COMMIT` в ветке `exports`.

Не проверено: остальные README векторов в M — только сверка литералов с их `cases.tsv`; прочие нормы и контракты целиком; наличие ожидаемых значений, записанных не литералом. Фактических M/J нет, поэтому объекты Git и изоляция не проверялись. Вывод о раскладке J в С3 опирается на нынешнюю ветку `exports`.

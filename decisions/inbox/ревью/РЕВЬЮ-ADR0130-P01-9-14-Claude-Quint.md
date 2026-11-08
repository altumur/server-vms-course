adr: 0130 (P/01 пп. 9–14, Quint)

# Модель Quint боевых свойств P/01, пп. 9–14 — review103-claude

**Фаза после независимых находок.** Автор тот же, что у отчёта с находками; независимость этой модели не заявляется. Не вход для приёмки кандидата. READY/GATE не заявляется.

- Срез: `244355d161139bd6fe65fd68c7e5134598c21ba3`. Вход: count-only SRC `P01-INDEPENDENT-SUBMISSIONS-COMPLETE-COUNT-ONLY.json` (sha256 `fb7dfea5…419e5`).
- Старт фактический: 2026-11-08 15:46:49 UTC (`date -u` при начале работы).
- Источник вопросов: свой замороженный отчёт `РЕВЬЮ-ADR0130-P01-9-14-Claude.md` (коммит `f30ca507`) и записка-уточнение (коммит `bf44dff7`).
- Читались только публичные нормы и формы среза. Отчёты других рецензентов, смысловой common-пакет, реализация, кандидат, captures, частные судьи и `probes/*.py` не читались. Старые модели не запускались и не копировались.
- Модель не исполняет ни нормы, ни реализацию. «Нарушение» значит: при названных допущениях из текста нормы следует такое состояние. Это не дефект реализации и не доказательство о Source.

Сокращения: `01.1`, `01.3` — `Platform/01-store/spec/01.N-store.norms.md`; `prod` — `spec/production-acceptance.md`; `const` — `forms/runtime-constants.tsv`; `flags` — `forms/daemon-flags.tsv`; `02.4` — `Platform/02-installer/spec/02.4-installer.norms.md`.

Каталог: `decisions/inbox/ревью/quint-p01-9-14-244355d1/` (`*.qnt`, `run.py`, `results.tsv`, `run.log`, `runs/`, `anchors.tsv`, `check_anchors.py`, `verify_results.py`).

## Итог

143 финальных запуска (111 Apalache `quint verify`, 32 симуляции rust): 63 свойства, 37 свидетелей, 24 мутанта, 19 контролей. Все 143 совпали с ожиданием; 24 из 24 мутантов пойманы. `run.log` хранит и отладочные проходы (см. раздел «История»). Все 59 якорей сверены по байтам среза (`check_anchors.py`), все строки `results.tsv` — с sha256 текста модели (`verify_results.py`).

Снятых находок нет. Подтверждены при названных допущениях: С1, С2, С9, С12, М1, М3. Уточнены: С1, С2, С12. Без изменений, так как это находки о пробах или нормах, которые модель не проверяет: С3, С10, С11.

## Что смоделировано

Границы всех прогонов — в таблице ниже и в шапке каждого `.qnt`. Числа в моделях — параметры, не значения норм, кроме случаев, названных явно.

### 1. Время допуска: `admission.qnt`, `admission_wit.qnt`

Нормы: `01.1:451`, `01.1:456`, `01.1:458`, `01.1:463`, `01.1:464`, `01.1:470`, `01.1:473`, `01.1:534`, `01.1:537`, `01.1:539`, `01.1:541`, `01.1:690`, `01.1:694`, `01.3:91`, `01.3:92`, `01.3:96`.

Граница: 3 узла, журнал до 5 записей, часы 0..9, 2 id. Шаги: `verify` 8–10 (свойства — 10), симуляция 30 шагов на 20 000 трасс.

Инварианты:

- `inv_admNonDec`: время допуска не убывает вдоль журнала.
- `inv_metaLast`: последнее время допуска лидера равно времени последней записи при любом исходе.
- `inv_noBusiness`, `inv_oneOkPerId`, `inv_idMatchesOk`, `inv_idOccupied`: отказ и повтор не дают бизнес-эффекта; id занимает только запись с исходом `ok`.
- `inv_expiredSticky`: `expired` — тот же отказ при том же сроке и неубывающем времени.
- `inv_catchUp`: при часах не меньше последнего времени допуска запись со сроком не раньше часов не получает `expired`.
- `inv_sameOutcome`: исход по времени один на всех серверах.
- `inv_r071`: гонка `delete`/`write` с границей T.
- `inv_order`: `expired` раньше `conflict`.

Свидетели: `expired` на будущей записи (`not_w_futureExpired`), он держится (`not_w_expiredHolds`), новый лидер с отстающими часами (`not_w_leaderLower`), продолжение из снимка выше часов (`not_w_snapContinue`), рост метаданных отказом (`not_w_refusalRaises`), ответ повтора после срока (`not_w_againLate`). Посылки инвариантов проверены отдельными свидетелями в `admission_wit.qnt`.

Допущения:

- A1: абстракция Raft, лидером становится узел с полным журналом; журнал один на группу. Не норма, известное условие Raft.
- A2: порядок проверок как `01.1:534`; поля строк и форма запроса не моделируются.

Не моделируется: binary64 (`01.1:466`), `box`, сброс времени после `import` (`01.1:463`), пакет как отдельная форма — исход R132 по тексту тот же.

### 2. Группа и `import`: `import_group.qnt`

Нормы по тексту: `01.3:40`, `01.3:104`, `01.3:109`, `01.3:110`, `01.3:120`, `01.3:134`, `01.3:150`, `01.3:151`, `02.4:48`.

Граница: 3 узла (`BOX`: 1), 2 строки входа, `verify` 12–14 шагов, симуляция 40 шагов.

Текст против допущений разделён флагами:

- Базовый вариант — буквальное чтение: `01.3:40` и `01.3:151` не ограничены `box`, а маршрут в группе — только `admin.sock` живого лидера (`01.3:104`).
- `READING_BOX_ONLY` — чтение, где отказ старта только на box. В тексте такого ограничения нет.
- `ALLOW_REBUILD_GROUP` — допущение: оператор удаляет каталоги и собирает свежую группу. По отдельности `01.3:132` и `01.3:150` это позволяют, но как выход этот маршрут нормой не назван.
- `BOX` — отдельная конфигурация из одного узла с офлайн-продолжением.

Предикат `namedExit` описывает в коде модели, что считается законным выходом: `admin.sock` живого лидера, возможность старта большинства, офлайн-продолжение на box.

Инварианты: писатель не допущен до `Done` (`inv_noWriterBeforeDone`, основание `01.3:134`), `Done` только при полном переносе, floor раньше первой строки, floor постоянен в попытке.

Абстракция G1: общая фаза группы, лидер только из большинства с состоянием группы. Не моделируются строки, сеть, сроки.

### 3. Прерванный `recover`: `recover.qnt`

Нормы: `01.3:331`, `01.3:332`, `01.3:114`, `01.3:123`, `01.3:40`, `01.3:353`, `01.3:346`.

Текст не задаёт порядка шагов дампа, журнала и floor, атомарности и правила повтора. Поэтому шаги в модели свободного порядка, а прерывание возможно между ними. Свидетели читаются как «текст не исключает», а не как свойство какой-либо реализации. Граница: 1 узел, до 3 запусков, 10 шагов.

Флаги `ATOMIC_PUBLISH` и `REFUSE_ON_PARTIAL` — контрольные варианты, не нормы.

### 4. Память `id`: `id_memory.qnt`

Нормы: `01.1:733`, `01.1:735`, `01.1:501`, `01.1:766`, `prod:15`, `prod:62`, `const:9`, `const:10`.

Граница: 3 id, `MIN_AGE`=2, `MIN_RECORDS`=2 (параметры, не 120 с и 50000), часы до 6, 12 шагов.

Допущение M3: основание возраста нормой не названо. `AGE_BASE` принимает значения `wall` (стенные часы, подвержены скачку) и `mono` (монотонные).

Инварианты: забывание только при обоих условиях строго (`inv_forgetBoth`, `inv_strictAge`), одна версия за «жизнь» id (`inv_oneVersionPerLife`), ответ повтора — первый (`inv_againSameAnswer`). Емкость кэша и GC не моделируются.

### 5. Штатная остановка R034: `stop.qnt`

Нормы: `01.3:366`, `01.3:368`, `prod:50`, `prod:69`, `01.1:751`, `01.1:764`.

Граница: до 2 единиц работы, 1 копия, до 3 соединений, 10–12 шагов. Шаги абстрактные, не секунды. Допущение T1: каждый шаг остановки снимает определённое число единиц меры; конечность выражена рангом `inv_rank`.

Инварианты: нет приёма после `SIGTERM`, копия вне замка мутаций, выход только чистый, вся принятая работа классифицирована, снимок равен наличию копии, ранг. Сеть, менеджер служб и секунды `BUDGET_STOP` не моделируются. RUN-L03 модель не исполняет.

### 6. Дверь и ожидание лидера: `door.qnt`

Нормы: `01.3:51`, `01.3:59`, `01.3:70`, `01.3:160`, `01.1:766`, `01.1:738`, `const:11`, `const:12`, `flags:37`.

Граница: одна запись, повторы до 2, время до 10, 12 шагов. `T_ATTEMPT`=3 соответствует `DOOR_REQUEST_TIMEOUT`+`DOOR_REQUEST_MARGIN` (`const:11`, `const:12`), `LEADER_WAIT`=5 — умолчанию `-leader-wait` (`flags:37`). Это те же значения, но в модели они только параметры.

Допущения D1–D3 (шапка файла): без сетевых задержек; один запрос и его повторы; порядок потери лидера и отправки свободен. Реальные задержки только расширят окно `ambiguous`, что допущением и обозначено.

Не моделируются: число попыток двери и общий предел (нормы нет, и выдумывать её модель не должна), несколько голосующих как отдельные узлы.

## Прогоны

Легенда: ожидание/факт `hold` — нарушений в пределе нет; `violated` — найдено состояние, опровергающее условие. Для свидетеля `violated` означает, что состояние достижимо. `hold` у симуляции — не доказательство, а отсутствие контрпримера в выборке.

| Модуль | Инвариант | Тип | Инструмент, шаги | Ожидание / факт | Подстановки | Файл (в `runs/`) |
|---|---|---|---|---|---|---|
| admission | inv_admNonDec | мутант | Apalache, 9 | violated / violated | MUT_NO_MAX=true | admission__inv_admNonDec__MUT_NO_MAX__verify.txt |
| admission | inv_admNonDec | мутант | Apalache, 9 | violated / violated | MUT_SNAP_NO_ADM=true | admission__inv_admNonDec__MUT_SNAP_NO_ADM__verify.txt |
| admission | inv_admNonDec | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_admNonDec__sim.txt |
| admission | inv_admNonDec | контроль | Apalache, 9 | hold / hold | ALLOW_SKEW=false,ALLOW_JUMP=false,ALLOW_LEADER_CHANGE=false,MUT_NO_MAX=true | admission__inv_admNonDec__sync_nomax__verify.txt |
| admission | inv_admNonDec | свойство | Apalache, 10 | hold / hold | — | admission__inv_admNonDec__verify.txt |
| admission | inv_catchUp | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_catchUp__sim.txt |
| admission | inv_catchUp | свойство | Apalache, 10 | hold / hold | — | admission__inv_catchUp__verify.txt |
| admission | inv_expiredSticky | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_expiredSticky__sim.txt |
| admission | inv_expiredSticky | свойство | Apalache, 10 | hold / hold | — | admission__inv_expiredSticky__verify.txt |
| admission | inv_idMatchesOk | мутант | Apalache, 9 | violated / violated | MUT_EXPIRED_TAKES_ID=true | admission__inv_idMatchesOk__MUT_EXPIRED_TAKES_ID__verify.txt |
| admission | inv_idMatchesOk | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_idMatchesOk__sim.txt |
| admission | inv_idMatchesOk | свойство | Apalache, 10 | hold / hold | — | admission__inv_idMatchesOk__verify.txt |
| admission | inv_idOccupied | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_idOccupied__sim.txt |
| admission | inv_idOccupied | свойство | Apalache, 10 | hold / hold | — | admission__inv_idOccupied__verify.txt |
| admission | inv_metaLast | мутант | Apalache, 9 | violated / violated | MUT_REFUSE_ROLLBACK=true | admission__inv_metaLast__MUT_REFUSE_ROLLBACK__verify.txt |
| admission | inv_metaLast | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_metaLast__sim.txt |
| admission | inv_metaLast | свойство | Apalache, 10 | hold / hold | — | admission__inv_metaLast__verify.txt |
| admission | inv_noBusiness | мутант | Apalache, 9 | violated / violated | MUT_AGAIN_NEW_VERSION=true | admission__inv_noBusiness__MUT_AGAIN_NEW_VERSION__verify.txt |
| admission | inv_noBusiness | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_noBusiness__sim.txt |
| admission | inv_noBusiness | свойство | Apalache, 10 | hold / hold | — | admission__inv_noBusiness__verify.txt |
| admission | inv_oneOkPerId | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_oneOkPerId__sim.txt |
| admission | inv_oneOkPerId | свойство | Apalache, 10 | hold / hold | — | admission__inv_oneOkPerId__verify.txt |
| admission | inv_order | мутант | Apalache, 9 | violated / violated | MUT_CAS_BEFORE_TIME=true | admission__inv_order__MUT_CAS_BEFORE_TIME__verify.txt |
| admission | inv_order | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_order__sim.txt |
| admission | inv_order | свойство | Apalache, 10 | hold / hold | — | admission__inv_order__verify.txt |
| admission | inv_r071 | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_r071__sim.txt |
| admission | inv_r071 | свойство | Apalache, 10 | hold / hold | — | admission__inv_r071__verify.txt |
| admission | inv_sameOutcome | мутант | Apalache, 9 | violated / violated | MUT_APPLY_OWN_CLOCK=true | admission__inv_sameOutcome__MUT_APPLY_OWN_CLOCK__verify.txt |
| admission | inv_sameOutcome | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | admission__inv_sameOutcome__sim.txt |
| admission | inv_sameOutcome | свойство | Apalache, 10 | hold / hold | — | admission__inv_sameOutcome__verify.txt |
| admission | not_w_againLate | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_againLate__verify.txt |
| admission | not_w_expiredHolds | контроль | Apalache, 9 | hold / hold | ALLOW_SKEW=false,ALLOW_JUMP=false,ALLOW_LEADER_CHANGE=false | admission__not_w_expiredHolds__sync__verify.txt |
| admission | not_w_expiredHolds | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_expiredHolds__verify.txt |
| admission | not_w_futureExpired | контроль | Apalache, 9 | hold / hold | ALLOW_SKEW=false,ALLOW_JUMP=false,ALLOW_LEADER_CHANGE=false | admission__not_w_futureExpired__sync__verify.txt |
| admission | not_w_futureExpired | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_futureExpired__verify.txt |
| admission | not_w_leaderLower | контроль | Apalache, 9 | hold / hold | ALLOW_SKEW=false,ALLOW_JUMP=false,ALLOW_LEADER_CHANGE=false | admission__not_w_leaderLower__sync__verify.txt |
| admission | not_w_leaderLower | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_leaderLower__verify.txt |
| admission | not_w_refusalRaises | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_refusalRaises__verify.txt |
| admission | not_w_snapContinue | свидетель | Apalache, 9 | violated / violated | — | admission__not_w_snapContinue__verify.txt |
| admission_wit | not_w_catchUpAnte | свидетель | Apalache, 9 | violated / violated | — | admission_wit__not_w_catchUpAnte__verify.txt |
| admission_wit | not_w_idAnte | свидетель | Apalache, 9 | violated / violated | — | admission_wit__not_w_idAnte__verify.txt |
| admission_wit | not_w_r071Ante | свидетель | Apalache, 9 | violated / violated | — | admission_wit__not_w_r071Ante__verify.txt |
| admission_wit | not_w_stickyAnte | свидетель | Apalache, 9 | violated / violated | — | admission_wit__not_w_stickyAnte__verify.txt |
| door | inv_ambigWindow | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | door__inv_ambigWindow__sim.txt |
| door | inv_ambigWindow | свойство | Apalache, 12 | hold / hold | — | door__inv_ambigWindow__verify.txt |
| door | inv_idAtMostOne | мутант | Apalache, 12 | violated / violated | MUT_DOUBLE_APPLY_WITH_ID=true | door__inv_idAtMostOne__MUT_DOUBLE_APPLY_WITH_ID__verify.txt |
| door | inv_idAtMostOne | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | door__inv_idAtMostOne__sim.txt |
| door | inv_idAtMostOne | свойство | Apalache, 12 | hold / hold | — | door__inv_idAtMostOne__verify.txt |
| door | inv_unavailableNotApplied | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | door__inv_unavailableNotApplied__sim.txt |
| door | inv_unavailableNotApplied | свойство | Apalache, 12 | hold / hold | — | door__inv_unavailableNotApplied__verify.txt |
| door | inv_voter503NotApplied | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | door__inv_voter503NotApplied__sim.txt |
| door | inv_voter503NotApplied | свойство | Apalache, 12 | hold / hold | — | door__inv_voter503NotApplied__verify.txt |
| door | not_w_allVotersDown503 | свидетель | Apalache, 12 | violated / violated | — | door__not_w_allVotersDown503__verify.txt |
| door | not_w_ambigNotForwarded | мутант | Apalache, 12 | violated / violated | T_ATTEMPT=3,LEADER_WAIT=3,MUT_VOTER_NEVER_ANSWERS=true | door__not_w_ambigNotForwarded__MUT_VOTER_NEVER_ANSWERS__verify.txt |
| door | not_w_ambigNotForwarded | контроль | Apalache, 12 | hold / hold | T_ATTEMPT=3,LEADER_WAIT=3 | door__not_w_ambigNotForwarded__T=L__verify.txt |
| door | not_w_ambigNotForwarded | контроль | Apalache, 12 | hold / hold | T_ATTEMPT=3,LEADER_WAIT=2 | door__not_w_ambigNotForwarded__T>L__verify.txt |
| door | not_w_ambigNotForwarded | свидетель | Apalache, 12 | violated / violated | — | door__not_w_ambigNotForwarded__verify.txt |
| door | not_w_noIdDouble | контроль | Apalache, 12 | hold / hold | ALLOW_NO_ID=false | door__not_w_noIdDouble__only_id__verify.txt |
| door | not_w_noIdDouble | свидетель | Apalache, 12 | violated / violated | — | door__not_w_noIdDouble__verify.txt |
| door | not_w_reachedAmbig | свидетель | Apalache, 12 | violated / violated | — | door__not_w_reachedAmbig__verify.txt |
| door | not_w_voter503 | свидетель | Apalache, 12 | violated / violated | — | door__not_w_voter503__verify.txt |
| id_memory | inv_againSameAnswer | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | id_memory__inv_againSameAnswer__sim.txt |
| id_memory | inv_againSameAnswer | свойство | Apalache, 12 | hold / hold | — | id_memory__inv_againSameAnswer__verify.txt |
| id_memory | inv_forgetBoth | мутант | Apalache, 12 | violated / violated | MUT_AGE_ONLY=true | id_memory__inv_forgetBoth__MUT_AGE_ONLY__verify.txt |
| id_memory | inv_forgetBoth | мутант | Apalache, 12 | violated / violated | MUT_FORGET_ANY=true | id_memory__inv_forgetBoth__MUT_FORGET_ANY__verify.txt |
| id_memory | inv_forgetBoth | мутант | Apalache, 12 | violated / violated | MUT_RECORDS_ONLY=true | id_memory__inv_forgetBoth__MUT_RECORDS_ONLY__verify.txt |
| id_memory | inv_forgetBoth | свойство | Apalache, 12 | hold / hold | AGE_BASE="mono" | id_memory__inv_forgetBoth__base_mono__verify.txt |
| id_memory | inv_forgetBoth | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | id_memory__inv_forgetBoth__sim.txt |
| id_memory | inv_forgetBoth | свойство | Apalache, 12 | hold / hold | — | id_memory__inv_forgetBoth__verify.txt |
| id_memory | inv_oneVersionPerLife | мутант | Apalache, 12 | violated / violated | MUT_REPLAY_NEW_VER=true | id_memory__inv_oneVersionPerLife__MUT_REPLAY_NEW_VER__verify.txt |
| id_memory | inv_oneVersionPerLife | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | id_memory__inv_oneVersionPerLife__sim.txt |
| id_memory | inv_oneVersionPerLife | свойство | Apalache, 12 | hold / hold | — | id_memory__inv_oneVersionPerLife__verify.txt |
| id_memory | inv_strictAge | мутант | Apalache, 12 | violated / violated | MUT_EQ_AGE=true | id_memory__inv_strictAge__MUT_EQ_AGE__verify.txt |
| id_memory | inv_strictAge | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | id_memory__inv_strictAge__sim.txt |
| id_memory | inv_strictAge | свойство | Apalache, 12 | hold / hold | — | id_memory__inv_strictAge__verify.txt |
| id_memory | not_w_ageMetByJump | контроль | Apalache, 12 | hold / hold | AGE_BASE="mono" | id_memory__not_w_ageMetByJump__base_mono__verify.txt |
| id_memory | not_w_ageMetByJump | свидетель | Apalache, 12 | violated / violated | — | id_memory__not_w_ageMetByJump__base_wall__verify.txt |
| id_memory | not_w_ambiguousRetry | свидетель | Apalache, 12 | violated / violated | — | id_memory__not_w_ambiguousRetry__verify.txt |
| id_memory | not_w_earlyReforget | контроль | Apalache, 12 | hold / hold | AGE_BASE="mono" | id_memory__not_w_earlyReforget__base_mono__verify.txt |
| id_memory | not_w_earlyReforget | свидетель | Apalache, 12 | violated / violated | — | id_memory__not_w_earlyReforget__base_wall__verify.txt |
| id_memory | not_w_forgottenNewWrite | свидетель | Apalache, 12 | violated / violated | — | id_memory__not_w_forgottenNewWrite__verify.txt |
| import_group | inv_doneComplete | мутант | Apalache, 12 | violated / violated | MUT_DONE_EARLY=true | import_group__inv_doneComplete__MUT_DONE_EARLY__verify.txt |
| import_group | inv_doneComplete | свойство | симуляция, 40 / 20000 трасс | hold / hold | — | import_group__inv_doneComplete__sim.txt |
| import_group | inv_doneComplete | свойство | Apalache, 12 | hold / hold | — | import_group__inv_doneComplete__verify.txt |
| import_group | inv_floorFirst | свойство | симуляция, 40 / 20000 трасс | hold / hold | — | import_group__inv_floorFirst__sim.txt |
| import_group | inv_floorFirst | свойство | Apalache, 12 | hold / hold | — | import_group__inv_floorFirst__verify.txt |
| import_group | inv_floorStableInAttempt | мутант | Apalache, 12 | violated / violated | MUT_REPLAY_NEW_FLOOR=true | import_group__inv_floorStableInAttempt__MUT_REPLAY_NEW_FLOOR__verify.txt |
| import_group | inv_floorStableInAttempt | свойство | симуляция, 40 / 20000 трасс | hold / hold | — | import_group__inv_floorStableInAttempt__sim.txt |
| import_group | inv_floorStableInAttempt | свойство | Apalache, 12 | hold / hold | — | import_group__inv_floorStableInAttempt__verify.txt |
| import_group | inv_noWriterBeforeDone | мутант | Apalache, 12 | violated / violated | MUT_NO_HOLD=true | import_group__inv_noWriterBeforeDone__MUT_NO_HOLD__verify.txt |
| import_group | inv_noWriterBeforeDone | контроль | Apalache, 12 | hold / hold | BOX=true,NODES=Set("a") | import_group__inv_noWriterBeforeDone__box_single__verify.txt |
| import_group | inv_noWriterBeforeDone | свойство | симуляция, 40 / 20000 трасс | hold / hold | — | import_group__inv_noWriterBeforeDone__sim.txt |
| import_group | inv_noWriterBeforeDone | свойство | Apalache, 12 | hold / hold | — | import_group__inv_noWriterBeforeDone__verify.txt |
| import_group | not_w_allDownUnfinished | свидетель | Apalache, 12 | violated / violated | — | import_group__not_w_allDownUnfinished__verify.txt |
| import_group | not_w_doneAfterOutage | свидетель | Apalache, 14 | violated / violated | ALLOW_REBUILD_GROUP=true | import_group__not_w_doneAfterOutage__assume_rebuild__verify.txt |
| import_group | not_w_doneAfterOutage | контроль | симуляция, 40 / 50000 трасс | hold / hold | — | import_group__not_w_doneAfterOutage__literal__sim.txt |
| import_group | not_w_doneAfterOutage | контроль | Apalache, 14 | hold / hold | — | import_group__not_w_doneAfterOutage__literal__verify.txt |
| import_group | not_w_doneAfterOutage | свидетель | Apalache, 14 | violated / violated | READING_BOX_ONLY=true | import_group__not_w_doneAfterOutage__reading_box_only__verify.txt |
| import_group | not_w_refusedAfterDone | контроль | Apalache, 12 | hold / hold | READING_BOX_ONLY=true | import_group__not_w_refusedAfterDone__reading_box_only__verify.txt |
| import_group | not_w_refusedAfterDone | свидетель | Apalache, 12 | violated / violated | — | import_group__not_w_refusedAfterDone__verify.txt |
| import_group | not_w_resumeAfterFullOutage | свидетель | Apalache, 12 | violated / violated | ALLOW_REBUILD_GROUP=true | import_group__not_w_resumeAfterFullOutage__assume_rebuild__verify.txt |
| import_group | not_w_resumeAfterLeaderLoss | свидетель | Apalache, 12 | violated / violated | — | import_group__not_w_resumeAfterLeaderLoss__verify.txt |
| import_group | not_w_sameGen | свидетель | Apalache, 12 | violated / violated | ALLOW_REBUILD_GROUP=true | import_group__not_w_sameGen__assume_rebuild__verify.txt |
| import_group | not_w_stuck | контроль | Apalache, 12 | hold / hold | BOX=true,NODES=Set("a") | import_group__not_w_stuck__box_single__verify.txt |
| import_group | not_w_stuck | контроль | Apalache, 12 | hold / hold | READING_BOX_ONLY=true | import_group__not_w_stuck__reading_box_only__verify.txt |
| import_group | not_w_stuck | свидетель | Apalache, 12 | violated / violated | — | import_group__not_w_stuck__verify.txt |
| recover | inv_completeConsistent | мутант | Apalache, 10 | violated / violated | MUT_COMPLETE_EARLY=true | recover__inv_completeConsistent__MUT_COMPLETE_EARLY__verify.txt |
| recover | inv_completeConsistent | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | recover__inv_completeConsistent__sim.txt |
| recover | inv_completeConsistent | свойство | Apalache, 10 | hold / hold | — | recover__inv_completeConsistent__verify.txt |
| recover | inv_floorGrows | мутант | Apalache, 10 | violated / violated | MUT_FLOOR_DOWN=true | recover__inv_floorGrows__MUT_FLOOR_DOWN__verify.txt |
| recover | inv_floorGrows | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | recover__inv_floorGrows__sim.txt |
| recover | inv_floorGrows | свойство | Apalache, 10 | hold / hold | — | recover__inv_floorGrows__verify.txt |
| recover | inv_noStartOnPartial_control | контроль | Apalache, 10 | hold / hold | ATOMIC_PUBLISH=true,REFUSE_ON_PARTIAL=true | recover__inv_noStartOnPartial_control__atomic+refuse__verify.txt |
| recover | inv_noStartOnPartial_control | контроль | Apalache, 10 | violated / violated | ATOMIC_PUBLISH=true | recover__inv_noStartOnPartial_control__atomic_only__verify.txt |
| recover | inv_noStartOnPartial_control | контроль | Apalache, 10 | violated / violated | — | recover__inv_noStartOnPartial_control__baseline__verify.txt |
| recover | inv_noStartOnPartial_control | контроль | Apalache, 10 | hold / hold | REFUSE_ON_PARTIAL=true | recover__inv_noStartOnPartial_control__refuse_only__verify.txt |
| recover | not_w_dumpNewWalOld | свидетель | Apalache, 10 | violated / violated | — | recover__not_w_dumpNewWalOld__verify.txt |
| recover | not_w_floorOnlyRaised | свидетель | Apalache, 10 | violated / violated | — | recover__not_w_floorOnlyRaised__verify.txt |
| recover | not_w_retryNewGen | свидетель | Apalache, 10 | violated / violated | — | recover__not_w_retryNewGen__verify.txt |
| recover | not_w_startOnOldWithFloor | свидетель | Apalache, 10 | violated / violated | — | recover__not_w_startOnOldWithFloor__verify.txt |
| recover | not_w_startOnPartialDump | свидетель | Apalache, 10 | violated / violated | — | recover__not_w_startOnPartialDump__verify.txt |
| stop | inv_copyNoLock | мутант | Apalache, 12 | violated / violated | MUT_COPY_HOLDS_LOCK=true | stop__inv_copyNoLock__MUT_COPY_HOLDS_LOCK__verify.txt |
| stop | inv_copyNoLock | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_copyNoLock__sim.txt |
| stop | inv_copyNoLock | свойство | Apalache, 10 | hold / hold | — | stop__inv_copyNoLock__verify.txt |
| stop | inv_exitClean | мутант | Apalache, 12 | violated / violated | MUT_EXIT_WITH_INFLIGHT=true | stop__inv_exitClean__MUT_EXIT_WITH_INFLIGHT__verify.txt |
| stop | inv_exitClean | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_exitClean__sim.txt |
| stop | inv_exitClean | свойство | Apalache, 10 | hold / hold | — | stop__inv_exitClean__verify.txt |
| stop | inv_noAdmitAfterStop | мутант | Apalache, 12 | violated / violated | MUT_ADMIT_AFTER_STOP=true | stop__inv_noAdmitAfterStop__MUT_ADMIT_AFTER_STOP__verify.txt |
| stop | inv_noAdmitAfterStop | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_noAdmitAfterStop__sim.txt |
| stop | inv_noAdmitAfterStop | свойство | Apalache, 10 | hold / hold | — | stop__inv_noAdmitAfterStop__verify.txt |
| stop | inv_pinsMatchCopy | мутант | Apalache, 12 | violated / violated | MUT_LEAK_PIN_ON_CANCEL=true | stop__inv_pinsMatchCopy__MUT_LEAK_PIN_ON_CANCEL__verify.txt |
| stop | inv_pinsMatchCopy | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_pinsMatchCopy__sim.txt |
| stop | inv_pinsMatchCopy | свойство | Apalache, 10 | hold / hold | — | stop__inv_pinsMatchCopy__verify.txt |
| stop | inv_rank | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_rank__sim.txt |
| stop | inv_rank | свойство | Apalache, 10 | hold / hold | — | stop__inv_rank__verify.txt |
| stop | inv_workClassified | мутант | Apalache, 12 | violated / violated | MUT_DROP_ADMITTED=true | stop__inv_workClassified__MUT_DROP_ADMITTED__verify.txt |
| stop | inv_workClassified | свойство | симуляция, 30 / 20000 трасс | hold / hold | — | stop__inv_workClassified__sim.txt |
| stop | inv_workClassified | свойство | Apalache, 10 | hold / hold | — | stop__inv_workClassified__verify.txt |
| stop | not_w_ambiguousAtStop | свидетель | Apalache, 12 | violated / violated | — | stop__not_w_ambiguousAtStop__verify.txt |
| stop | not_w_stalledCancel | свидетель | Apalache, 12 | violated / violated | — | stop__not_w_stalledCancel__verify.txt |
| stop | not_w_stop503 | свидетель | Apalache, 12 | violated / violated | — | stop__not_w_stop503__verify.txt |
| stop | not_w_stopNoCopy | свидетель | Apalache, 12 | violated / violated | — | stop__not_w_stopNoCopy__verify.txt |
| stop | not_w_stopReset | свидетель | Apalache, 12 | violated / violated | — | stop__not_w_stopReset__verify.txt |

## Мутанты и контроли

Мутанты (24 из 24 пойманы, для каждого ожидаемый инвариант нарушен):

| Модуль | Мутант | Нарушаемый инвариант |
|---|---|---|
| admission | убрать `max` по журналу (`MUT_NO_MAX`) | `inv_admNonDec` |
| admission | отказ откатывает метаданные (`MUT_REFUSE_ROLLBACK`) | `inv_metaLast` |
| admission | снимок не несёт время допуска (`MUT_SNAP_NO_ADM`) | `inv_admNonDec` |
| admission | применение по своим часам (`MUT_APPLY_OWN_CLOCK`) | `inv_sameOutcome` |
| admission | `expired` занимает id (`MUT_EXPIRED_TAKES_ID`) | `inv_idMatchesOk` |
| admission | повтор выдаёт новую версию (`MUT_AGAIN_NEW_VERSION`) | `inv_noBusiness` |
| admission | CAS раньше времени (`MUT_CAS_BEFORE_TIME`) | `inv_order` |
| import_group | писатель допущен при переносе | `inv_noWriterBeforeDone` |
| import_group | `Done` без полного переноса | `inv_doneComplete` |
| import_group | replay берёт новую генерацию | `inv_floorStableInAttempt` |
| recover | повтор понижает floor | `inv_floorGrows` |
| recover | завершение раньше шагов | `inv_completeConsistent` |
| id_memory | забыть при одном возрасте | `inv_forgetBoth` |
| id_memory | забыть при одном счёте | `inv_forgetBoth` |
| id_memory | забыть без условий | `inv_forgetBoth` |
| id_memory | нестрогий возраст | `inv_strictAge` |
| id_memory | повтор создаёт версию | `inv_oneVersionPerLife` |
| stop | приём после остановки | `inv_noAdmitAfterStop` |
| stop | копия держит замок | `inv_copyNoLock` |
| stop | выход с принятой работой | `inv_exitClean` |
| stop | утечка снимка при отмене | `inv_pinsMatchCopy` |
| stop | потеря принятой работы | `inv_workClassified` |
| door | повтор с id применяется заново | `inv_idAtMostOne` |
| door | голосующий не отвечает 503 при T≥L | `not_w_ambigNotForwarded` |

Контроли (19):

- `admission`, sync: при общих часах без скачка и смены лидера `expired` на будущей записи, его удержание и отстающий лидер недостижимы; `MUT_NO_MAX` при этом не нарушает `inv_admNonDec`. То есть мутант и свидетель действительно зависят от расхождения часов.
- `import_group`, reading_box_only и box_single: застревания нет; `not_w_doneAfterOutage` в буквальном чтении — `hold` (14 шагов Apalache и 40 шагов / 50 000 трасс симуляцией), а при box-only и при допущении пересборки — достижим.
- `recover`: `refuse_only` и `atomic+refuse` дают `hold`; `atomic_only` и базовая — `violated` (см. С2).
- `id_memory`, base_mono: раннее забывание недостижимо.
- `door`, T=L и T>L: лишний `ambiguous` недостижим; `only_id`: двойного применения нет.

Невакуумность: у большинства инвариантов посылка задета мутантом или свидетелем, а `admission_wit.qnt` задаёт посылки `inv_r071`, `inv_expiredSticky`, `inv_catchUp` и наличие успешной записи с id напрямую. Для `inv_oneOkPerId` отдельного свидетеля с двумя успешными записями нет; свидетель `not_w_idAnte` показывает одну успешную запись с id.

## Находки отчёта в свете модели

Снято: ничего. Модель не добавляет проб и не отменяет нормы; всё ниже — следствия текста при допущениях.

**С1 — подтверждено при буквальном чтении; уточнено.**

- `not_w_stuck` достижим уже на 4 состояниях: попытка в `Floor`, два из трёх узлов down, живой один, лидера нет. По `01.3:40` и `01.3:151` упавшие узлы не стартуют, а маршрут только через `admin.sock` живого лидера (`01.3:104`). Достаточно потери большинства, полная остановка всех узлов не нужна.
- `not_w_doneAfterOutage` при буквальном чтении — `hold` (14 шагов, симуляция 40/50 000): из потери всех узлов до `Done` модель не доходит.
- `not_w_refusedAfterDone`: при живом большинстве и `Done` узел с незавершённой попыткой в каталоге остаётся отказанным.
- Контроли: при чтении «только box», на box и при допущении пересборки застревания нет. Значит, вывод зависит ровно от объёма отказа старта.
- Уточнение 1 к формулировке «Решение» отчёта: удержание писателей в группе уже названо (`01.3:134`: «waits for Done»). Новой нормы удержания не требуется; решать нужно только объём отказа старта на группе либо офлайн-маршрут.
- Уточнение 2: фраза отчёта «законного пути, кроме не названной сборки заново, нет» читается узко — не назван выход. `recover` (`01.3:331`) применим к остановленному демону, а про незавершённую попытку текст молчит. Его действие на состояние попытки не определено, поэтому в модели он не вошёл; при выборе нормы его надо назвать или исключить.
- Сопутствующее при допущении пересборки: `not_w_sameGen` — новая попытка в том же часу получает ту же генерацию, так как свежая группа не несёт `upper` (`01.3:114`). Ни один писатель не был допущен, вреда модель не показывает. Формула не гарантирует буквальное «a new generation» (`01.3:150`) для этого допущения; это не новая находка, а уточнение формулировки.

**С2 — подтверждено как «текст не исключает»; уточнено.** Достижимы старт на частичном дампе, новый дамп при старом журнале, поднятый только floor, повтор с новой генерацией. Текст гарантирует только `inv_floorGrows` (`01.3:123`) и согласованность завершённого запуска (`01.3:332`). Свидетели основаны на молчании текста: модель лишь перечисляет комбинации, которые он не запрещает. Уточнение к «Решению»: `atomic_only` (атомарна запись каждого файла отдельно) — `violated`, прерывание между дампом и журналом остаётся. Атомарность должна охватывать весь результат, либо нужен отказ старта (`refuse_only` — `hold`). Новая генерация при повторе при этом не нарушает `01.3:123`.

**С3 — без изменений.** Находка о пробе, модель не исполняет RUN-L03 и пробы не создаёт. Инварианты R034 в модели выполняются; `not_w_stopNoCopy` показывает путь остановки без копии (охват шире `prod:69`), что было сказано отчётом и так.

**С9 — следствие подтверждено; выход моделью не исследован.** `not_w_futureExpired` и `not_w_expiredHolds` достижимы: `expired` на будущей записи держится; `inv_catchUp` — пока часы не догонят. Контроль sync показывает, что без скачка и расхождения случай недостижим. Смена лидера не помогает (`not_w_leaderLower`: новый лидер с отстающими часами продолжает из журнала, `01.1:458`). Вопрос об операторском выходе (`backup` и `import`, сброс `01.1:463`) остаётся нормативным: модель сброс не включает.

**С10 — без изменений.** Находка об отсутствии пробы. Модель показывает только, какие сценарии проба должна покрыть: смену лидера с разными часами, снимок, рост на отказах; соответствующие мутанты пойманы. Заменой пробы модель не является.

**С11 — без изменений.** Стоимость не моделировалась. Модель фиксирует только то, что и так в тексте: каждый принятый повтор и отказ — запись журнала (`01.1:537`, `01.1:690`).

**С12 — подтверждено и уточнено.** `not_w_ambigNotForwarded` достижим при `T_ATTEMPT` < `LEADER_WAIT`: дверь отвечает `ambiguous` на запись, не дошедшую до лидера и не применённую. Это соответствует тексту `01.3:160`: нарушения нет, это следствие окна. Уточнение (`inv_ambigWindow`, `hold`): `-leader-wait` считается от потери лидера, а не от запроса (`01.3:51`), поэтому лишний `ambiguous` возможен только для запроса, отправленного менее чем через `LEADER_WAIT − T_ATTEMPT` после потери лидера (при значениях модели — 2 единицы времени). Фраза отчёта «при выборах двери дают лишние `ambiguous`» уже: не все запросы в окне выборов, а только его начало. Безопасность повтора с тем же id выполняется (`inv_idAtMostOne`), без id возможно двойное применение (`not_w_noIdDouble`, основание `01.1:766`). Контроль T≥L: окно исчезает. Число попыток двери и общий предел нормой не заданы и не моделировались.

**М1 — подтверждено как молчание текста.** Запрос при остановке в модели может получить и 503, и разрыв (`not_w_stop503`, `not_w_stopReset`). Оба исхода введены недетерминизмом из молчания `01.1:751` и `01.1:764`; модель их не обнаруживает, а только фиксирует.

**М3 — подтверждено при допущении.** При `AGE_BASE`=`wall` скачок вперёд выполняет условие возраста раньше фактического: след имеет `wallAge`=3, `monoAge`=0 (`not_w_ageMetByJump`), а повтор становится новой записью (`not_w_earlyReforget`). При `mono` оба недостижимы. Запись «Qualified clock/application-count» в `prod:62` основания не называет, поэтому находка стоит. Какое из двух оснований подразумевается, модель не решает.

Находки С4–С8, С13, М2, М4, М5 моделью не затрагивались.

## Не вошло

- Обычные числа: `ID_REPLAY_MIN_AGE` 120 с, `ID_REPLAY_MIN_RECORDS` 50000, секунды `BUDGET_STOP`, значение `CLOCK_SKEW` (`const:7`).
- binary64 и округление времени допуска.
- `box` в модели времени допуска, форма пакета, манифесты, права.
- `recover` как выход из С1 (текст молчит о незавершённой попытке).
- Число попыток двери, общий предел двери, несколько голосующих как отдельные узлы, сетевые задержки (D1).
- Диски, дескрипторы, медленный читатель, шторм повторов (С4–С7, С11): норм или бюджетов нет, модель их не придумывает.
- Сами исполнимые пробы и реализация.

## Допущения и пределы

- Все выводы ограничены пределом шагов и малыми областями из таблицы; `hold` — отсутствие нарушения до предела, а не доказательство для произвольных размеров.
- Симуляция — случайная выборка с seed `0xadc0130` в `run.py`.
- A1, G1 — абстракция Raft; D1–D3, T1, M3, `ATOMIC_PUBLISH`, `REFUSE_ON_PARTIAL`, `READING_BOX_ONLY`, `ALLOW_REBUILD_GROUP` — названные допущения, не нормы; каждое в шапке или у флага в `.qnt`.
- Подстановки значений выполняются текстовой заменой `pure val` во временной копии; sha256 фактического текста записан в каждый файл `runs/`, сверяется `verify_results.py`.
- Модель не сверялась ни с реализацией, ни с кандидатом.

## История прогонов (честно)

`run.log` содержит и отладочные проходы. Первый полный проход выявил две ошибки модели, не норм: в `door` не пересылался ожидающий запрос при возврате лидера; в `id_memory` инвариант ответа не сбрасывал прошлый ответ при новой «жизни» id. Промежуточный проход второй правки `import_group` падал на проверке типов (25 строк `error` в `run.log`), после чего модуль исправлен и перезапущен. Ещё одна строка `error` — обрыв соединения с сервером Apalache на пробном прогоне; повторные запуски добавлены в `run.py`. Итоговые 143 строки `results.tsv` соответствуют текущему тексту моделей; для них `verify_results.py` сверяет sha256.

Одна строка отладочного прогона (`baseline_no_rebuild`) убрана из `results.tsv` и таблицы: контроль был вакуумным и заменён на `not_w_doneAfterOutage`.

## Воспроизведение

```
JAVA_HOME=/opt/quint/jdk PATH=/opt/quint/jdk/bin:$PATH
# два сервера Apalache на портах 8931, 8932 (Xmx 4g), затем:
python3 run.py            # все прогоны, HOLD-файл останавливает новые
python3 check_anchors.py  # якоря по байтам среза
python3 verify_results.py # results.tsv против текста моделей
```

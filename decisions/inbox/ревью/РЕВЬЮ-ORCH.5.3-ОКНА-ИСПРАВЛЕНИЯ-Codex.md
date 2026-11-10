# ORCH.5.3 — ревью ремонта окон под задачу

**Нужны правки. FULL по объёму поручения, не приёмка реализации.** Из 11 порученных причин: **6 CLOSED, 5 PARTIAL, 0 NOT_FIXED**. Новых корней ремонта: **Б0 / С1 / М0**. Старые остатки отдельно и повторно в новый счёт не включены. Пять ранее закрытых причин ORCH.5.1 не перепроверялись старым набором; новый путь первого prompt затронул их фазовое ограждение и проверен отдельно.

## Точный предмет и источники

Subject `/home/pilot/git/cammeta-watch.git` — `8735ba0e737da7a6cb3c2234fd0582fe06dd0373`, sole parent `2d7a827d3308ab339c475587006e01426fca082a`, tree `686e07e823e6d8988ae41ec99a7a05720fcec97f`. Проверены parent/tree и обе стороны merge `baf68a2098549cc4a8431e4a6956ca46223c25e9` + `c21482bf5af31c4b8ea4382642762c7fc80ca8ee`. Поздняя вершина ветки и развёрнутые файлы не читались.

Три frozen diff побайтно совпали с Git: merge-context, 52266 байт, SHA256 `162029c714e7705509e51c4b533d45ecc58d544c727522e0c7412390de50ae4b`; repair-only, 70105 байт, `567b4066010753bb50cdb57edef97b30e4e6304c108fe186ab871b6af2216b8e`; baseline→endpoint, 122278 байт, `38de94bbbfba0fb983ffed98f141d127b4888fc165a034473cfbc71f0a65d7b5`. Авторский ремонт — только `tasks.py`, `taskwindows.py`, `test_taskwindows.py`. Изменения групп, очереди и Gantt в merge отделены как контекст; прежние ORCH10/11 не переоткрывались.

TASK.yaml прочитан полностью только после проверки SHA256 `f6cdba39a12189eda41f0d57687ccbd9c8ce35238675cbe21259d7be14e61b35`. Assignment, ORCH.5.yaml и собственный опубликованный ORCH.5.2 из `20b617e04afbf6f7aad12cb3aec4b021a98ecd0b` прочитаны полностью; raw последнего `06d3ab49bfc54852f2c68dd3917fb06aae356df3ee65ff3ba888fa3dfe7a8588`, 41604 байта. Родительские qualifications из отдельного disposition приняты: старый rejected helper не доказывает запрета уточнений; база report-worktree может отличаться от точного предмета review. Эти снятые доводы не возвращаются в счёт.

Норма — frozen ADR0134 на course `e19b627bcb799423b42f25a435fe4694b65bd5d7`, 81529 байт, SHA256 `232322799af94a2d76f7b77b54a25cdf6cfdb2c25b28e6e16df6accd9fcb97cf`: полностью Add18–30 (353–469). Frozen ORCH6 prompt прочитан полностью: 13302 байта, SHA256 `fa2dd10c85134a3fe9d508f3451d348d7fb2840222b50ef2c4d0760fcdf6aadf`. Идентичности/modes/blob из assignment проверены до смыслового чтения. ORCH.5 note `2026-11-10T19:03:09Z` однозначно задаёт Q1 — standalone review оставляет последнее judge-место; Q2 — отказ в то же живое окно, gone replacement с тем же cwd. В коде эти ветви сохранены, новых вопросов смысла нет.

## Матрица всех 11 причин

`CLOSED` относится к исходной причине и указанным доказательствам, не к полной эксплуатационной безопасности. Префикс `53-` отличает новые case-ID от прежних результатов. Старые 46/45 и авторские наборы не исполнялись.

| Причина | Итог | Endpoint код | Новые controls |
| --- | --- | --- | --- |
| Б1 | PARTIAL | `taskwindows.py:385–394,625–644,828–864,972–975` | `53-N06,N07,N08,R01` |
| Б3 | PARTIAL | `taskwindows.py:705–742,751–792,1043–1052` | `53-N22,N23,N24,R03` |
| Б4 | PARTIAL | `taskwindows.py:721–728,777–784` | `53-N25,N26,R04` |
| С1 | CLOSED | `tasks.py:1773–1793; queues.py:759–774` | `53-N18,N19,N20,N21` |
| С2 | CLOSED | `taskwindows.py:378–384,1035–1042,794–798` | `53-N11,N12,N13` |
| С3 | PARTIAL | `taskwindows.py:218–257,432–434,539–541` | `53-N09,N10,R02` |
| С5 | CLOSED | `taskwindows.py:476–491,509–519,580–603,461–464` | `53-N14,N15` |
| М1 | CLOSED | `taskwindows.py:872–906,957–965; collector.py:278–284; cammeta-windows:39–41` | `53-N27` |
| Н-Б1 | PARTIAL — условие одного PID | `taskwindows.py:333–335,988–993,1026–1056,812–820` | `53-N01,N02,N03,N04,N29,R05` |
| Н-С1 | CLOSED | `taskwindows.py:828–839,909–920,923–985` | `53-N05` |
| Н-С2 | CLOSED | `tasks.py:1652–1659; taskwindows.py:476–480,580–603` | `53-N16,N17` |

**Б1: PARTIAL.** В reserved до create сохраняется prompt path; потерянный reply остаётся CREATE_UNKNOWN. Найденный Kimi получает первый prompt после готовности, без повторного create. Строка списка без handle и truncated-list не доказывают отсутствие.

Остаток: Опись с handle, но без title, проходит; duplicate handle молча схлопывается dict-comprehension. Если теряется строка с op-id, find возвращает None, apply_reconcile освобождает резерв. R01 показывает оба malformed-input пути, а не факт выдачи такого ответа native Orca.

Предел: Файловый fsync добавлен; fsync каталога после replace нет. Авария машины и native listing/create/restart NOTEXEC; durability не объявляется доказанной. Новый обход фаз при восстановлении учтён отдельно как 5.3-С1.

Рекомендация: Для отрицательного результата проверять пригодность всей описи к поиску op-id: необходимые поля и уникальность handle; неполнота/неоднозначность должны сохранять CREATE_UNKNOWN.

**Б3: PARTIAL.** Перед follow-up _execute передаёт fresh=True; новая incarnation i2 вместо i1 больше не наследует ready. Пустой box, provider, busy/shell/service guards сохраняются. Busy без собственного prompt marker больше не объявляется стартом.

Остаток: В confirm marker и incarnation запоминаются отдельно: после наблюдения marker в i1 последующий busy i2 всё ещё возвращает started с i1, поскольку ветка 771–773 не проверяет соответствие текущей incarnation. R03 — детерминированный mock последовательности допустимых observe-результатов; не наблюдение native замены.

Предел: Нормальный same-incarnation marker+busy проверен первым. Атомарность native read/list/send, смена агента между отдельными вызовами и настоящий первый prompt NOTEXEC.

Рекомендация: Не подтверждать start по screen другого agent incarnation; после смены сбрасывать marker/фазу и возвращать unproven либо явно восстанавливать ту же операцию.

**Б4: PARTIAL.** Обычный saved draft под цитатой Update available больше не считается startup; штатная объявленная форма меню распознаётся.

Остаток: menu_cursor вновь разрешает state=typed, если последний ввод начинается «› 1. …». Вывод-пример Update available / 2. Skip над обычным набранным «› 1. ordinary draft» вызывает keys("2"). Числовое начало draft не доказывает служебный UI.

Предел: R04 сохраняет synthetic screen и fake key event; native rendering не квалифицировался. Ограничение данных/команд — ORCH6:10,23 и условия startup из задания, не новая политика UI.

Рекомендация: Не превращать typed composer в разрешение по одному номеру/цитируемым словам. Использовать квалифицированное отличие текущего меню от пользовательского box; если различия нет, оставить unproven и не нажимать.

**С1: CLOSED.** Отмена собственной задачи и cancelled ancestor не дают нового @accept mark. Текущая попытка сравнивается с handed; frozen acceptor сохраняется при смене raw accept. Нормальный приёмщик ставит отдельный mark, авторский не затрагивается.

Предел: Закрыт однозначный остаток cancelled acceptance-start с учётом решения родителя. Старый rejected handed helper сам по себе не принимается за доказательство запрета уточняющих вопросов; новое нормативное правило о таких вопросах здесь не устанавливается. Проверен actual task Model/owned files, не live task CLI.

Рекомендация: Сохранять единый guard текущей попытки/отмены и отдельный протокол приёма.

**С2: CLOSED.** Pending снимается лишь при совпадении request_id той же записи окна. Чужая квитанция даёт still pending. При отсутствии ID есть явный hold/нужно решение, а не слепая повторная доставка и не ложный success.

Предел: Квитанции поддельные и полные по внутреннему договору адаптера. Проверка не утверждает, что native Orca присылает неверные ID, и не доказывает реальную доставку.

Рекомендация: Сохранять корреляцию receipt с token/handle/ID и явную неизвестность.

**С3: PARTIAL.** Root требует windows/closed без неизвестных полей; kind/purpose/status/rid и handle открытого окна проверяются. Первичный неполный JSON больше не становится пустым журналом.

Остаток: Проверка записи не требует area живого run writer. После удаления только area из корректной записи A load_ledger принимает её, busy_areas её теряет, и plan открывает B того же P/01. Неизвестная область не должна доказывать свободного писателя.

Предел: Это owned malformed-ledger control, не утверждение о повреждении живого журнала. Legacy запись без нового rid теперь явно отказывает; автоматическая миграция/нативное восстановление здесь не доказаны и не объявляются новым требованием.

Рекомендация: Проверять обязательные поля по фазе/назначению записи или удерживать неизвестную область до восстановления; не считать пропуск area отсутствием занятого участка.

**С5: CLOSED.** Без author.commit отдельное review удерживается. Точный commit review_of явно передаётся в prompt; известный автор получает другого provider. Проверка отдельно допускает origin/reports как базу report-worktree при проверяемом commit a…a.

Предел: Родительское уточнение соблюдено: inspected commit не обязан совпадать с базой дерева отчёта. Native Git-доказательство commit/публикации не исполнялось; не вводилось обязательного нового публичного subject DSL.

Рекомендация: Сохранять явную связь author/subject/edition, не выводить provider из имени роли.

**М1: CLOSED.** Проход сохраняет phase и observed. public без нового screen показывает «по наблюдению <время>», а не прежнее универсальное «не прочитано» и не старую активность как текущий busy. Collector получает ту же сохранённую фазу; background-команда сохраняется.

Предел: Проверен JSON-маршрут actual window_publish с fake module boundaries; не реальный collector loop/страница/--list CLI. Не заявляется полнота всего UI.

Рекомендация: Сохранять timestamp/freshness отдельно от текущего состояния, не называть давний busy текущим.

**Н-Б1: PARTIAL.** Старые close/send для rid-A/term_A не направляются в новую B; late close result не retire B; lookup сверяется по rid/op_id. Closing reservation не допускает обычный второй close.

Остаток: В stale ветке 1029–1033 выполняется мутация НОВОЙ записи: sent[key] удаляется, если pid совпал с текущим процессом. При перекрывающихся вызовах в одном PID у B может быть собственный sending first-prompt; stale A удаляет его и следующий plan снова выдаёт B prompt. В R05 ни send, ни close не вызываются, но reservation B потерян.

Предел: Остаток условен для scheduling: R05 — function-level overlap одного PID, подобный допущенной в тестах реентерабельности. У отдельных штатных oneshot CLI PID различаются, и возникновение этого остатка в развёрнутом запуске НЕ доказано. Основная межпроцессная ABA-close/send причина исправлена. Новый отдельный Б не начисляется.

Рекомендация: При несовпадении токена вообще не менять запись следующего владельца; очистку связывать с rid/action-id конкретной резервации, а не общим PID и ключом.

**Н-С1: CLOSED.** Lookup, screen, model_source и merge proof выполняются до locked; в критической секции применяются проверенные результаты и локальные резервации. Реальный owned flock свободно берётся внутри всех четырёх callbacks; заклинивающего общего lock на Git/Orca-подобном ожидании нет.

Предел: Callback transport/Git поддельны, lock настоящий в owned FS. Snapshot задачи не является транзакцией со всеми task-командами; абсолютная линейность любой внешней мутации не заявляется.

Рекомендация: Сохранять snapshot/token/apply разделение и ограниченные внешние операции.

**Н-С2: CLOSED.** Creator отвергает review_of=self; resolver использует seen task IDs, self/двухузловые циклы получают локальный hold; независимая A продолжает выдачу. Защитный resolve также превращает ошибку разрешения в hold этой задачи.

Предел: Это проверка валидности метаданных и устойчивости прохода, а не аутентификация --from и не пересмотр Owner trust. Не запускается live creator/окно.

Рекомендация: Сохранять проверку ссылок как в create, так и в reader для сохранённых файлов.

Ни неизвестная доставка, ни malformed listing/ledger не считаются semantic kill. Остатки Б1 и С3 описывают fail-closed границы повреждённых входов, а не доказанные события развёрнутого backend. Остаток Н-Б1 в одном PID отдельно ограничен; основной запрет закрытия/ввода в чужой handle теперь работает. Если эксплуатационный договор жёстко ограничен отдельными oneshot PID, этот остаток имеет более узкую достижимость, но сама stale-ветка всё равно не должна менять запись другого rid.

## Новая находка

### 5.3-С1. Восстановленный первый prompt обходит проверку фазы и наличия задачи

Код: `taskwindows.py:385–403,967–979,1043–1067`. Основание: ADR0134 Add18.4 (hold/wait), Add21 (окно под готовую задачу), Add22 (вопрос держит окно), ORCH.5 цель и условия безопасного восстановления; отсутствие входа не разрешает исполнение.

1. Готовая Kimi-задача K получает reserved; launch создаёт окно, но ответ потерян. Код сохраняет CREATE_UNKNOWN и prompt path. Никакой Native Orca-операции в доказательстве не было: это fake reply-loss boundary.
2. До восстановления владелец удерживает/отменяет задачу либо файл становится недоступен. В 53-D03 поле owner:true с answered даёт настоящий tasks.Model.state_of(K)=OWNER_WAIT; в D04 получены настоящий CANCELLED и отсутствие K в Model.tasks.
3. Сверка находит term_K. На следующем проходе пустой idle composer даёт ready. plan добавляет prompt в строках 385–394 ДО task is None, CANCELLED, ERROR/UNKNOWN и без предиката допустимости продолжения.
4. Резерв first-prompt исполняется через _execute: проверяется token/готовность терминала, но не фаза задачи. В cancelled варианте список даже содержит prompt, затем close; при пропавшей задаче — prompt, затем hold. Guard, добавленный после prompt, уже не отменяет действие.

Последствие: Оркестратор начинает новый первый ход по удержанной/отменённой или непрочитанной задаче. Это не доказательство реальных записей продукта и не Native start: воспроизведён ошибочный выбор действия и fake-send. Реальный busy после send мог бы отложить последующий close; это не устраняет первый незаконный prompt.

Доказательство: UNIT_AST_EXACT+actual tasks.Model owned file fixtures: 53-N06,N28 normal; 53-D01,D02,D03,D04; before-plan causal control 53-B01.

Новизна: Новая ветка delivery=adopted/op=prompt добавлена в repair-only. В before-plan такой ветки нет: 53-B01 для CANCELLED имеет только close. Это регрессия фазового ограждения прежней С8/защиты отсутствующего task, не повторное начисление старых листинговых причин Б1/С3. Четыре NEW_REPRO case-ID — один корень.

Рекомендация: Разрешать восстановление первого prompt только после проверки наличия/достоверности текущей задачи и допустимой фазы; держать guard общим для первоначальной выдачи и recovery, отдельно от доставки разрешённого ответа на вопрос. Повторно проверять применимость в execute при изменении задачи между планом и действием.

Предел: Первые D01/D02 задают task-view строку непосредственно. Для исключения предубеждения фикстуры отдельный новый program использует actual parser/load_files/_quick_model/Model; его raw результаты заморожены независимо. D03 также показывает прежнюю общую answered→continue строку: её не начисляю как новый дефект. Однозначные CANCELLED/absent варианты из D04 и baseline не зависят от этой прежней ветки.

## Полнота чтения и путь исполнения

`taskwindows.py:1–1079` и `test_taskwindows.py:1–993` прочитаны полностью. В `tasks.py` прочитаны обе полные изменённые функции (`add_task`, `on_acceptance_by`), parser/load/read acceptance/handed/marks, lock/write, frozen attempt, ask/quick model и релевантные части Model. Все новые непустые строки repair-only покрыты чтением. Новые Model-методы из merge прочитаны как необходимые caller dependencies; неизменные методы разрешены к повторному использованию только после AST equality с уже прочитанными собственными байтами. Это не новый запуск старых доказательств.

Неизменённые watchcfg/windows/automation/collector/CLIs/inbox/cammeta-accept сверены побайтно с ранее лично прочитанным scope; точные current Git blobs/modes/SHA дополнительно удержаны в этом worker. Повторно прочитаны критические callers `queues._mark_started_locked:759–789`, `turn_view/task_source/task_section:889–946`, `collector.window_publish:278–284`, весь `cammeta-windows`. AGENTS в subject отсутствует — запись `absent:true`, не выдуманный blob; subject CLAUDE и course AGENTS→CLAUDE/doc rules сверены, применимое чтение §1 использовано после byte equality. Ни история состава сессий, ни текущие peer reports не нужны и не читались.

Путь: `cammeta-windows.main→model→queues.turn_view/tasks.build→run_pass`; затем snapshot→reconcile_lookups/observe_all/model_source/_merged_proofs вне lock; locked apply_reconcile/plan/reserve; `_execute` сверяет rid/handle и записывает результат только той же записи. Начальный prompt проходит confirm, найденный create — новый op=prompt. Именно этот новый переход не проверяет фазу до планирования. Collector отдельно читает load_ledger/public и не выполняет pass. CLI не запускались; трасса статическая и по exact AST-функциям, не installed/runtime-наблюдение.

Для протокола приёма прочитан вызов start→on_acceptance_by→frozen_attempt/Model; отдельно проверены actual files, current acceptor mark, own cancellation, ancestor cancellation и edited raw accept. Это проверка текущего протокола, не аутентификация объявленного --from. Роль/протоколы, конфиг конечных ожиданий, проверка repo/base и task-branch/check_spec gate вне repair scopes не объявляются вновь принятыми тестами. Проверка существующего cwd и Git proofs замещены/статически прослежены, реальные fetch/checkout/worktree/check_spec не выполнялись.

Не заявляется полный аудит всех 2131 строк tasks.py, всей очереди, dashboard/Gantt или установленного расписания. Точные spans, raw/AST equality и виды reuse — `COVERAGE.json`, `REUSED-READS.json`, `INSTRUCTION-REUSE.json`, `READS.frozen.jsonl`. Исходный before taskwindows целиком совпадает с собственной ранее прочитанной проекцией; удалённые ветви можно сопоставить с repair diff без перепроигрывания старого набора.

## Исполненные проверки и ограничения

| Программа | Case executions | Итог |
| --- | ---: | --- |
| `controls.py` | 34 | 28 PASS guards, 4 RESIDUAL_REPRO, 2 NEW_REPRO |
| `controls_model_recovery.py` | 3 | 1 PASS actual Model normal, 2 NEW_REPRO того же корня на actual Model |
| `control_stale_pending.py` | 2 | 1 PASS current reservation, 1 RESIDUAL_REPRO с явной same-PID предпосылкой |

Всего **3 UNIT-процесса, 39 исполнений, 39 уникальных case-ID**: 30 PASS controls (включая 1 ограниченный before-plan case), 5 воспроизведений старых остатков, 4 воспроизведения **одной** новой причины. На current endpoint — 38 cases; before case `53-B01` исполняет только exact `plan` родителя с проверенными support globals и не является полным запуском before environment. Это причинное сравнение новой ветки, не старый regression suite. N29 — общий positive владельца резерва в _execute, а не доказательство достижимости Kimi-prompt для provider=claude его фикстуры; корректные Kimi-положительные пути отдельно даны N06/N28. Это ограничение данных normal control не меняет воспроизведённую R05 мутацию записи B/kimi. Case-ID не равен числу внутренних подвариантов: например D01 перечисляет семь phase values, R01 — два malformed listings; подробности сохранены. Свежие author tests — 0, старые suite replay — 0, semantic kills — 0.

Все три процесса: `/opt/check-env/lesson-spec/bin/python -B` (3.12.15), конечный outer timeout 60 с, собственный TMPDIR. Checking/harness/utility errors — **0**. Поддельная потеря reply — заранее заданный transport fault boundary, не ошибка harness/semantic kill. Статус NEW_REPRO означает наблюдение ошибочного выбора действия в UNIT, не отрицательный результат реальной модели/кандидата. 68 явно сохранённых fake backend/key event entries — не полный счёт всех stubs и не native calls. Каждый actual немедленно deep-copy сериализуется в raw stdout до следующей мутации; aliases между cases не используются.

Полные stdout/stderr/argv/cwd/start/end/exit всех трёх процессов удержаны: `captures/cee92fb2c463422083e1d5fc1287006b.*`, `captures/ef7c393a1e624ff1907f72bc93cba3de.*`, `captures/ece72f62410346e7ae1978428364910a.*`. Полные outputs прочитаны небольшими диапазонами; объёмный intake display не считался прочитанным целиком — необходимые code/authority тексты прочитаны отдельно. Первые assignment cat/mkdir сохранены только CLI transcript, отдельные времена/streams не сочинялись. Поздние audit-команды имеют немедленные captures.

Программы компилируют exact AST выбранных удержанных функций, с raw/AST SHA под тем же Python. **До AST exec** все default roots перенаправлены в owned scratch; project imports не выполняются. Native process/network/signal backend и выход FS за owned root блокируются audit guard; неожиданное внешнее действие останавливает процесс как checking error. Не было таких попыток. Перед неблагоприятным соседом выполнен нормальный control. Положительный нормальный recovery использует настоящий run_pass reserved→unknown→adopted→prompt маршрут; отдельно корректность phase fixtures проверена actual parser/load_files/_quick_model/Model. Это работа функций инструмента в owned данных, не производство, не реальный stand и не task CLI.

Native Orca terminal list/create/send/close, agent UI/incarnation guarantees, настоящий запуск/рестарт процесса после crash, delivery на живое окно, collector loop/страница/службы, Git worktree/main merge/check_spec — **NOT_EXECUTED**. Adversarial transport fixtures не доказывают, что native API выдаёт такие ответы. Нет доказательства пригодности развёрнутого окружения или полного lifecycle по сумме PASS. Ни Source/J/candidate/Go/model/full9/GATE, ни секреты/full environment не читались/не исполнялись. HOME/CODEX_HOME не переназначались.

## Сохранность и передача родителю

Все новые программы, code copies и доказательства — `/home/pilot/review103/orch5-3-repair-8735ba0/worker`. Code/authorities/TASK before-after identity, native modes/blob/size/SHA и initial/final WT HEAD/branch/index/staged-empty/status — `CODE-IDENTITIES.json` и `PRESERVATION.json`. Symlink/absence Git-запись отличается от mode=0644 собственных проекций. Оригинальные inputs, bare Git, старые отчёты и evidence не изменялись. Единственный файл в course WT — этот unstaged отчёт; external REPORT.md побайтно равен ему. Ни stage, commit, push, merge, live task operation, сообщение, selfaccept или публикация worker не выполнялись.

`INDEX.json` перечисляет только стабильные artifacts с size/SHA; активные CALLS/READS, scratch/cache, self и последующие READY/RESULT исключены, frozen snapshots включены. READY содержит точные pins, matrix/counts/limits и хеш отчёта/индекса; RESULT — пути и квитанцию передачи. Пробела нормативного входа нет; FULL означает завершённое независимое bounded review. Принимает результат, публикует report-only MAIN и выполняет taskdone родитель после личного чтения.


## Личная приёмка родителем review103

Полный отчёт, матрица одиннадцати причин и первичная новая находка прочитаны лично. Проверены соответствующие удержанные ветви `plan`, `_execute`, восстановления create, `confirm`, terminal-list, разделения lock/callbacks и допуска приёма; собственные программы actual-Model recovery и stale-pending также прочитаны. Наличие нового `prompt` до проверки `task is None`/CANCELLED подтверждено исходными байтами. Однозначный контрпример — настоящий parsed Model с отменённой либо действительно отсутствующей задачей; прежняя общая ветка answered→continue не включена в новый счёт. Четыре NEW_REPRO означают один корень **Б0/С1/М0**, а не четыре дефекта.

Матрица остаётся **6 CLOSED / 5 PARTIAL / 0 NOT_FIXED** на уровне проверенных функций. У Н-Б1 основная межпроцессная ABA-close/send причина исправлена; оставшийся PARTIAL относится только к перекрывающимся вызовам одного PID. Его достижимость через штатные отдельные oneshot CLI не установлена. Это четыре других частичных причины и один отдельно оговорённый условный остаток; новой блокирующей находки из него не сделано. Никаких реальных окон/запусков оркестратора эти проверки не доказывают.

Независимый metadata-audit родителя сверил **246 файлов** worker-индекса по size/SHA256, **20 записей Git input** (19 blobs и одно отсутствие AGENTS.md), subject parent/tree, обе стороны merge и три полных diff. Под тем же Python 3.12.15 проверены **960 raw/AST записей**: 165 проекций и 795 записей function-map; это проверка соответствия байтов, не заявление о новом полном смысловом чтении всех функций. Все **39 case records** трёх процессов сопоставлены с первичным полным stdout, сохранёнными cases, итоговыми summary и argv/cwd/exit. Расхождений изменяемых aliases не найдено; checking/harness errors сохранённого набора — 0. Начальный/final Git index hash, HEAD, branch и отсутствие tracked/staged изменений подтверждены. Родитель не исполнял reviewed code или тесты повторно и не повторял старые suite/архивы.

Один усечённый интерфейсом фрагмент чтения не принят за полное прочтение; пропущенный хвост отчёта прочитан отдельно. Worker report/READY/INDEX остаются неизменными; финальная разница сохранена во внешнем `parent-final/PARENT-REPORT.diff`. Доказательства родительской приёмки — `WORKER-RECEIPT.json`, `RAW-CASE-AUDIT.json`, `AST-AUDIT.json`, `GIT-PIN-AUDIT.json`; публикация одного файла и remote/clean — `PUBLICATION.json`. Принимающий задания ORCH.5.3 — Архитектор; родительская проверка собственного worker не подменяет этот приём. Финальная квитанция — `parent-final/FINAL-PACKET.json`, taskdone отдельно записан в `parent-final/taskdone/`.

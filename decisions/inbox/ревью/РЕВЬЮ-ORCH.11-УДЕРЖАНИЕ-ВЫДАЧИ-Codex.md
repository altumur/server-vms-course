# ORCH.11 — ревью снятия выдачи при удержании

**С правками: Б0 / С1 / М0. FULL по назначенному объёму ревью.** Прежний ended_at больше не оставляет owner/event-held строку открытой: узкий дефект закрытия устранён. Но полный договор release не выполнен: вместо новой выдачи используется старый ID/entry. Старая start-mark блокирует доставку уже начатой задачи, а старая граница STOP может оказаться концом новой фазы. Эти проявления сведены к одной причине.

## Точный срез и основание

Subject `0a6e11bac61d6e6cca0e22d2016995f7b5ee7de4`, sole parent `16f447e22415e4425b5f91e0f0edac6648807821`, tree `b73f506b59f81232cd871beb390c4a7a6da5ea3b`, readonly bare `/home/pilot/git/cammeta-watch.git`. Только queues.py/test_tasks.py; raw patch4309B, SHA256 `c0b5e008f92f756b9fb5bf8d1131c23f29d3272733cb8310ab61264ce65f5fae` совпал с frozen input. Ветка — label, поздние children и deployed bytes не читались.

Полностью прочитаны frozen ORCH.11 и авторитетный goal ORCH.9. Случай P01.B2 используется только как предоставленный рассказ, живой task/queue не читался. Goal требует снять owner/event строку даже после конца хода и после release выдать новую строку/номер, не потеряв историю. Прямое поручение ревью отдельно уточняет **NEW issue ID**, не повтор старого закрытого ID. Author note про811 тестов — разрешённый вход, не мои результаты и не semantic oracle.

ADR-0134 на pin `e3f1ca2d756ee1256d41e6b6e54c3c52db47d44f`, raw81529B, SHA256 `232322799af94a2d76f7b77b54a25cdf6cfdb2c25b28e6e16df6accd9fcb97cf` проверен до чтения. Нужные Add2.1/4–7 разделяют доставку, начало и факты ожидания; Add14 задаёт owner hold после ответа; Add18.4 — команды hold/release. Никакой новой нормы, таймера или протокола actor auth я не добавляю.

ORCH.10 имеет другой endpoint и отдельный отчёт; его находки не входят в этот счёт. Прежние ORCH-отчёты/кейсы не переоткрывались. Peer reports/CONTROLS/candidate verdicts не читались. Применены subject CLAUDE, course AGENTS→CLAUDE/необходимый §1/doc rules. Работник не выполнял business CLI и не публиковал.

## Нормальный путь: что исправлено

`queues.close_withdrawn:838–864` больше не исключает entry с ended_at. Для issued строки held/event/cancelled строится кандидат. Под tasks/.lock читается fresh `_quick_model`; отпускание задачи, завершённое после старого snapshot, не даёт записать withdrawal. Потом close_line под done-lock атомарно добавляет закрытие from architect с withdrawn:true. Факт конца хода не объявляется сдачей или acceptance.

В нормальном UNIT owner-held entry с записанным концом хода закрыта, не досылается, старый end сохранён. То же показала отдельная матрица owner/event × started/unstarted × ongoing/ended. В каждом случае old work/start file остаётся. Exact predecessor на отдельной fixture не создал withdrawal для ended entry — BASE01 подтверждает причинность изменённого guard, без старой suite.

`release` берёт task-lock, затем done-lock. `_reopen_withdrawn` переносит именно системное withdrawn закрытие в reopen_history, не удаляет свой done работника. Новая apply_reopened:828–833 сохраняет ended_at/end_line/turn_seen в reopened_turns, очищает текущую тройку и unobserved_epoch, один раз сдвигает send_base. Список sends остаётся. Повтор apply по тому же history не обнуляет бюджет заново. Эти положительные свойства H02/H07–H10 и C02/C03 действительно проверены на owned FS.

Подтверждены соседние отсечения: stale held snapshot после completed release не закрывает строку повторно; own done остаётся закрытым; accepted/cancelled работа не release-ится; второй законченный hold/release сохраняет оба history records. Task lock используется для admission/reservation, **не удерживается во время fake sender** — в C02 тот же lock удалось взять заново перед каждым simulated send. Реальные sender/Orca не вызывались.

## С1. Release не создаёт отдельную выдачу и отдельную границу хода

**Код:** новая `queues.apply_reopened:814–835`, новый caller-path через `close_withdrawn:850–861`; связанная прежняя `tasks._reopen_withdrawn:1797–1823`, `release:1826–1843`; потребители `queues.unstarted:230–255`, `Plan.may_resend:965–976`, `reserve:1010–1018`, `resend_admission:1057–1061`, `record_turns:169–194`, `plan:1276–1295`. **Мерило:** goal ORCH.9: новая строка/номер после release и прямое уточнение NEW issue ID/fresh turn. **Доказательство:** H03/H04/H06(owner,event), положительные H01/H02 и C01/C02, STATIC caller trace.

### Положительная часть и незакрытая граница ID

Для неначатой A.1 после ended turn, owner hold и release новая отправка действительно планируется и доходит до fake transport. Но это `queue_resend`, ключ снова A.1; в ledger остаётся только A.1, её sends увеличивается с1 до2. Отдельной строки/issue ID нет. Закрытие A.1 убрано из текущего closed, хотя сохранено в reopen_history. `issued_at/issued_epoch/line_at_issue` и привязка к старой start-mark остаются от первой выдачи.

Это не подмена «новой выдачи» количеством send receipt. `attempt` работы также не нужно искусственно считать отказом: delivery identity и номер попытки принятия — разные вещи. Требуется отдельная delivery incarnation при сохранении работы/истории, а не увеличение attempts через фальшивый rejection.

### Начатая до удержания работа не получает новое сообщение

Конечная допустимая последовательность:

1. A.1 выдана роли; роль отмечает start, выполняет часть работы и заканчивает ход вопросом. Mark A.1.json остаётся фактом прежнего начала.
2. Owner ставит hold либо event wait. Новый close_withdrawn правильно закрывает issued line, в том числе при ended_at.
3. Release удаляет hold/event и переносит withdrawal в историю. apply_reopened очищает конец хода, но оставляет тот же ID и старую mark.
4. `unstarted` исключает entry из redelivery по with_mark.started_mark. Model после очистки ended считает старую строку WORKING; fresh issuable также не создаётся. Plan.may_resend дополнительно отверг бы ту же старую mark.

H06 отдельно для owner и event получил **0 новых fake deliveries**, state=`идёт`, keys=[A.1]. Это не утверждение, что фоновая работа исчезла: её факт сохранён. Нарушено требование сообщить о release свежим ходом/выдачей. Подлинные bytes/marks нельзя просто удалять ради обхода: они нужны истории.

### Старый STOP снова становится концом «нового» хода

H04 не меняет остановившееся окно после release. На первом проходе apply_reopened снимает old ended. Следующий `record_turns` сравнивает всё ещё старые issued_epoch и line_at_issue с прежним STOP вопроса. Он записывает новый ended_at, хотя после release ни нового наблюдённого хода, ни нового STOP не было. UNIT получил after-release end=None, на следующем проходе end=12:21, при старом issue epoch12:00 и старом line_at_issue. Это следствие той же переиспользованной записи, не второй счёт находки. Без start-mark это может оставаться advisory ended field, а не state TURN_ENDED — это различие учтено.

**Что новое, а что старое:** сама схема reopen старого ID уже существовала для unended строки. Не выдаю это за заново написанную строку или общий старый definition bug. Дельта добавляет обработку именно завершённого хода и объявляет fresh-turn repair; в этом новом требуемом пути старые marks/граница оказываются неприменимы. Узкий hold-guard исправлен, задача release остаётся неполной. Это продолжение цели текущего ORCH.9, не наследованный вердикт другого review.

**Рекомендация:** сохранять закрытую delivery как историю и создавать после release новую delivery identity с собственной границей issue/turn/receipt и отображением на ту же работу/попытку. Старый start не должен служить proof нового получения и не должен запрещать новое уведомление. До доставки проверять свежее held/accepted/cancelled состояние под коротким task-lock; отправлять вне lock. Не стирать историю и не ослаблять unknown/composer/permission guards ради повторной отправки.

## Матрица обязанностей

| Требование | Статус и evidence |
|---|---|
| Owner/event закрывает issued line после finished turn | Закрыто в пределах компонента: H01, восемь H05; predecessor BASE01 имел нужный gap |
| Ongoing/started/unstarted различаются без утраты фактов | Снятие строки работает во всех восьми соседях, mark/work сохраняются; новая доставка после started — С1 |
| Release снова доставляет | Неначатая owner и event доставляются, H02/C02; начатая owner/event не получает fresh line, H06 — С1 |
| Новый номер/ID и новая граница turn | Не выполнено: H03/H04 — С1, а не ещё две причины |
| История sends/withdrawal/ended и cap reset | Список sends и closure/ended history сохраняются; H08 проверяет применение один раз и send_base, C03 — второй цикл |
| Snapshot race release→withdrawal | Fresh read под task-lock не закрывает уже отпущенную задачу, H07 |
| Accepted/cancelled/own done | H09/H10 сохраняют отсечения; исход actual hand-in/acceptance CLI не переисполнялся |
| Не удерживать task-lock на send | Критическая секция заканчивается в reserve; C02 получает lock внутри fake transport, actual automation.run inspected only |
| Clear/retry/start/done/selectors | Прочитаны соответствующие точные функции и caller; старые права не объявляются новой уязвимостью. Бюджет resend15min/3 взят из существующего кода, новых чисел не требую |

## Изоляция, результаты и действительные ограничения

Полностью прочитан queues.py1434 строки на exact endpoint, оба changed function и все новые tests/helpers. В test_tasks прочитаны новые методы и необходимая Case/ReleaseResumes fixture область, не все3238 строк. Необходимые тела tasks parser/Model/hold/wait/release/marks/start/done/accept и caller automation.run/collector привязаны к точным blobs. Tasks на0a6 побайтно совпадает с parent16f; это явно проверенная common dependency, а не подмена endpoint. Точные ranges, SHA/mode/blob и raw/AST guards — COVERAGE/CODE-IDENTITIES/DEPENDENCIES/PROTECTED-BLOCKS.

**Три Python test-process attempts:** первый остановлен с CheckingError до завершения первого case; два последующих завершены. **23 уникальных completed control cases /23 исполнения:18 MATCH,4 MISMATCH,1 BASELINE_GAP_CONFIRMED.** Из них22 относятся к subject, один к exact predecessor причинного guard. Четыре mismatch сведены к одной причине С1. Основной завершённый процесс записал16 simulated queue transport events, новый caller-context процесс3; это не реальные sends. Первый процесс успел выполнить первоначальную fake issue до остановки, но массив событий не был заморожен: сохранены исходные scratch bytes и traceback, он не засчитан как completed control.

Первый CheckingError: time.strptime попытался лениво загрузить stdlib _strptime за пределами worker, защитный hook остановил чтение. Полный traceback/start/end/argv/stdout/stderr сохранён; исходный harness controls-attempt1.py и failed scratch оставлены. Исправлен **только own harness**: preload stdlib до guard, новые scratch-v2 roots. Subject/semantic expectations не менялись. Это не finding/kill и не PASS исчезнувшей ошибки.

Первые component fixtures намеренно имели fake registry/receipt predicates; это не доказательство actual automation input acceptance. После чтения caller добавлены **только три новых** controls C01–C03: правильные fake term_* + ct103:path, exact environment/excluded/submission/started_proof и exact may_resend. Они проходят с полным нормальным stage receipt и без старой suite. Никакой настоящий terminal handle не использовался. В main fixtures переданные времена логические, а close_line без now пишет wall-clock UTC; выводы не основаны на монотонности этих fixture timestamps. Legal static sequence выше требует обычного порядка действий, не точных времён фикстуры.

AST nodes — точные, без project imports. Все persistent roots заданы в собственных каталогах до exec; process/network/window calls запрещены. Для Plan изолированы вторичные alert/check/held-notification builders; обычные notices не транспортировались. Поэтому это UNIT-компонент, **не запуск полного automation/collector, не интеграция inbox/Orca и не доказательство фактической доставки модели**. Fake transport — memory event + локальная lock-проба; read readiness/receipts — контролируемый ввод, не SUT.

Author tests0, старые811/прочие suite0, реальные CLI/Orca/network/services/check_spec/Go0, semantic kills0. Общий для job utility launch error rg описан в FIRST-UTILITY-ERROR, не считается ещё одним ORCH.11 test error. Неизвестные тайминги его logger не реконструированы. Все test-process streams сохранены; original first failure не очищался. Source/deployed state/другие отчёты неизменны.

Отчёт — завершённый bounded review с незакрытым требованием release, не вердикт о живой P01.B2 или всех очередях. Нужны правки С1; принятие/публикация/два taskdone принадлежат родителю. Worker stage/commit/push/merge/task/send/deploy0.


## Личная приёмка родителем

Родитель прочитал весь отчёт, лично сопоставил apply_reopened/close_withdrawn, выбор unstarted/may_resend/record_turns и release с мерилом ORCH.9. Подтверждён Б0/С1/М0: снятие строки после ended исправлено, а новая delivery identity и корректная новая turn/start граница остаются невыполненными. Различены живой work/start факт и новая доставка; старую start-mark нельзя просто удалить для получения повтора. Вывод не перенесён на живую P01.B2 и не стал новой оценкой всех очередей.

Лично сверены507 файлов общего worker INDEX, включая173 записи предметной описи ORCH.11; обе предметные описи/READY и Git-происхождение исходных байтов проверены. В общем пакете25 blob-записей, два отсутствия и два caller Git-объекта сверены с точными pinned объектами. AST2622 записи/185 различных tuple и JS22 slices — общая проверка сохранённых доказательств, не дополнительный runtime/test счёт ORCH.11; отсутствие filename в каждой AST-строке не превращено в доказательство уникального источника.

При сопоставлении raw stdout с финальными контрольными файлами найден один дефект собственной evidence-записи: C02 хранил ссылку на общий список fake_calls. При завершении C02 первичный stdout содержит два события; после C03 в итоговом CALLER-CONTROL-RESULTS.json список внутри C02 уже содержит третье, хотя его sends остаётся2. Исходные stdout/файл/INDEX не переписаны. Третье событие принадлежит последующему C03, общий caller итог3 верен. Личная оценка C02 опирается на его полный первичный raw frame с двумя событиями; все прочие поля/статусы и остальные22 completed cases совпали. Для аудита сохранены `parent-final/RAW-UNIT-SNAPSHOTS.json`, `UNIT-SNAPSHOT-ALIAS-DISPOSITION.json` и первый отказ metadata audit. Это ошибка фиксации снимка в review harness, не новый дефект queues и не скрытый повтор ради PASS.

Счёт остаётся23 completed controls:18 MATCH,4 MISMATCH,1 BASELINE_GAP_CONFIRMED; отдельный первый failed fixture дал0 completed cases и сохранён. Проверки и subject не повторялись. Тестовый CheckingError1, общая utility-ошибка1 и обнаруженная ошибка снимка1 разделены; ни одна не semantic kill и не стала дополнительной находкой оркестратора.

Отдельная сдача — report-only normal-коммит в main с `/home/pilot/review103/orch10-11-groups-hold-20261110/parent-final/orch11/FINAL-PACKET.json`. Общий личный аудит — `parent-final/CUSTODY-AUDIT.json`; immutable worker INDEX SHA256 `b6ed7b106b1c1b24885dd6504c1e9db9933db5461874c5e58984c68372d14370`. Publication receipt содержит точные commit/sole parent/report SHA/blob/mode/remote equality/clean tree. Квитанция сдачи не самоприёмка; изменений развёрнутого кода и живых служебных данных, кроме штатных start/done собственных задач, не было.

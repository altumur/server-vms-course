# ORCH.5.4 — узкое ревью дельты окон

**FULL по объёму поручения. Пять причин CLOSED, одна PARTIAL. Новых корней: Б0 / С0 / М0.** Остаток относится к прежней Б3: после утраты свежего доказательства incarnation функция `confirm` ещё может объявить `started`. Это проверенный переход функций на изолированных входах, а не наблюдение неисправности живого Orca. Полная эксплуатационная готовность здесь не устанавливается.

## Предмет и основания

Проверен только `8735ba0e737da7a6cb3c2234fd0582fe06dd0373..28818633ca8b1c0ffa3fe58ab3d37996b04a5edb` в bare `/home/pilot/git/cammeta-watch.git`. Endpoint: sole parent `8735ba0e737da7a6cb3c2234fd0582fe06dd0373`, tree `19ac8b7270f13a194b1a727c81ea573f9c0d18bf`. Parent/tree проверены точным Git. Дельта только `taskwindows.py` и `test_taskwindows.py`; frozen diff совпал побайтно с Git: 23752 байта, SHA256 `baef44f408765e1ed82539fc9312bdf5c0577a68d499003f10f13db3316399b2`. Поздняя ветка и развёрнутые файлы не использованы.

TASK прочитан полностью после проверки SHA256 `9c91ce4083bcaef5961e7f9bad1c1974d9c41799ebf419f59422cbcb77df9f0b`. Assignment и собственный опубликованный ORCH.5.3 прочитаны полностью, включая личную приёмку родителя. Последний удержан из `557fcb8e95b9b46192c78f8d7448671113aab615`: 37983 байта, SHA256 `405ba1492c42e2e68fac5a1352a3de91f2e47c1a354311bee1218ea9181ede9a`. Его final disposition имеет приоритет над ранним worker wording. Первичная межпроцессная ABA-причина ранее была исправлена; оставался лишь условный same-PID случай. Его достижимость в native oneshot не предполагается.

Норма — frozen ADR0134 на том же course pin: 81529 байт, SHA256 `232322799af94a2d76f7b77b54a25cdf6cfdb2c25b28e6e16df6accd9fcb97cf`. Add18–30 (строки 353–469) прочитаны полностью. ORCH6 prompt, 13302 байта, SHA256 `fa2dd10c85134a3fe9d508f3451d348d7fb2840222b50ef2c4d0760fcdf6aadf`, повторно использован только после точного сравнения с собственными ранее прочитанными байтами. ORCH.5.yaml прочитан полностью: Q1: самостоятельное review оставляет последнее judge-место под приём; Q2 направляет отказ в то же живое RUN, заменяет только gone, с тем же cwd. Эти решения не переоткрыты.

Текущий TASK прямо исключает шесть live-window ограничений из findings и требует проверять безопасный fallback при недоступном доказательстве. Именно этот внутренний переход проверен для Б3. Новая native гарантия, формат UI или протокол не требуются.

## Все шесть причин

`CLOSED` означает исправление указанной причины в удержанных функциях и перечисленных границах. Это не live qualification. Case-ID относятся только к новому запуску `54-*`.

| Причина | Итог | Endpoint и доказательство | Остаток / предел |
| --- | --- | --- | --- |
| 5.3-С1: recovery-prompt до проверки задачи/фазы | CLOSED | `taskwindows.py:340–347,397–418,1002–1009,1064–1067`; 54-01…05 | До планирования проверяются наличие, отмена, ERROR/UNKNOWN и допустимая фаза; перед исполнением prompt задача читается заново вне lock. Недоступный fresh source возвращает false. UNIT использует явный task-view и exact `run_pass`; не утверждается транзакция со всеми внешними task-командами. |
| Б1: непригодная опись как отрицательное доказательство | CLOSED | `taskwindows.py:639–660,846–882`; 54-06/07 | Нет title, duplicate handle, truncated=true или неверный тип handle не дают lookup-результата. Резерв остаётся CREATE_UNKNOWN, не освобождается. Native полнота описи и directory durability исключены из findings. |
| Б3: marker одной incarnation подтверждается другой | PARTIAL | `taskwindows.py:745–758,779–791`; 54-08…11,22/23 | Явная смена i1→i2 теперь даёт unproven. Но исчезновение свежего доказательства i1 не блокирует started по сохранённому marker; подробности ниже. Это остаток прежнего корня, не новый Б. |
| Б4: номер в typed draft принимается за startup menu | CLOSED | `taskwindows.py:738–744,795–808`; `windows.py:101–138`; 54-12…14 | Исключение menu_cursor удалено. Для typed box startup пуст, ready=false. Нераспознанный или неотрендеренный источник не даёт startup-разрешения. Положительная no-box фикстура проверяет существующий словарь, не реальный вид меню Codex. |
| С3: RUN без area освобождает writer | CLOSED | `taskwindows.py:222–236,255–258,963–965`; 54-15…17 | Area обязательна как непустая строка. Missing/empty/bool/int останавливают pass с ошибкой ledger до observe/send, actions пуст. Judge без writer-area остаётся допустим. Это owned повреждённый вход, не событие живого журнала. |
| Н-Б1: stale action того же PID чистит резерв следующего окна | CLOSED | `taskwindows.py:994–997,1022–1027,1060–1084,1091–1096`; 54-18…21 | Stale rid/handle теперь вообще не меняет новую запись. Очистка sending связана с action op-id, не PID; defer/phase-hold не удаляют чужой op. Native same-PID overlap прежде не был доказан и теперь не объявляется наблюдённым. |

Для 5.3-С1 положительные READY/WORKING дают один first-prompt. OWNER_WAIT, EVENT_WAIT, DECISION, WAITING, CANCELLED, ERROR, UNKNOWN, REVIEW/DONE у work-window и отсутствующая задача first-prompt не получают. Для acceptance нормальная фаза — REVIEW, а READY не разрешает первый prompt. Изменение WORKING→OWNER_WAIT между планом и исполнением в exact `run_pass` даёт held, ноль fake sends и снимает только собственный резерв. Право доставить разрешённый ответ на вопрос не подменялось запретом всех follow-up.

Для Н-Б1 нормальная собственная резервация записывает результат fake delivery. Старое действие A при уже установленной B/rid-B/term_B с тем же PID не вызывает transport и не меняет журнал. При not-ready удаляется только `op=mine`; `op=other` сохраняется. Это проверка заявленного остатка в функциях, без повторного начисления исправленной межпроцессной ABA-причины.

## Остаток Б3: отсутствие свежего доказательства не сохраняет unproven

**Код:** `Orca.observe`, `taskwindows.py:745–750,754–758`; `Orca.confirm`, `779–791`. **Класс:** прежняя Б3, PARTIAL; новых findings не добавляет. Основание — текущий TASK: при недоступном доказательстве не переходить к действию/подтверждению, сохранять unproven/hold/pending. Исходная причина также связывала marker и start с одним агентом.

Положительный путь проверен первым: собственный marker задачи K наблюдается с incarnation i1, затем busy с той же i1 даёт `('started', 'ход начался', 'i1')`. Смена на известную i2 даёт unproven. Эти guards работают.

Оставшийся конечный сценарий:

1. `confirm` видит marker K и пригодную строку списка с i1. Он сохраняет `shown=True` и `incarnation='i1'`.
2. Следующее чтение screen успешно и показывает busy. Но свежий вызов terminal-list возвращает ошибку. Изолированный runner возвращает ненулевой код с `OWNED list unavailable`; никакой Orca-процесс не запускается.
3. Точный `observe` ловит RuntimeError, устанавливает пустой row, возвращает `ok=True`, `busy=True`, `incarnation=''`, `ready=False`.
4. Guard строки 781 срабатывает только при непустом текущем `seen.incarnation`; пустое значение его обходит. Строка 783 сохраняет старую i1, строка 784 — прежний marker. Ветка 789–791 возвращает started.

54-10 показывает этот возврат с полным observe-результатом. Дополнительная композиция **exact observe + exact confirm** в 54-22/23 отличается только успехом второго fake terminal-list: normal возвращает started; при ошибке списка результат остаётся тем же started вместо unproven. Полные три поля результата и все чтения сохранены. Возвращаемый detail не является оракулом смысла: отрицательная проверка требует только unproven, не конкретного текста диагностики.

Это не утверждение, что native incarnationId отсутствует или native API обязан гарантировать новый формат. Ошибка свежего чтения — уже обрабатываемый кодом путь; вопрос в том, что делает функция после неё. Физическая смена агента в сценарии не предполагается: достаточного доказательства той же i1 на новом busy просто нет. Не показаны ошибочный live send, реальный чужой ход или развёрнутая авария. Рекомендуется не подтверждать start по сохранённому marker, если текущая свежая выборка не подтверждает ту же incarnation; сохранить unproven без нового API/DSL.

## Шесть исключённых live-ограничений

Они **не входят в счёт findings**. Таблица отделяет имеющиеся guards от неисполненной квалификации.

| Предел | Guard и fallback по удержанному коду | Собственное доказательство / NOTEXEC |
| --- | --- | --- |
| Форма экрана Codex | `windows.composer:124–136`, `observe:740–755`: неизвестная форма не даёт ready; typed не становится startup по номеру | 54-12…14; реальные меню и отрисовка Codex NOTEXEC. No-box fixture не утверждает native форму. |
| incarnationId | `observe:745–755` требует текущую identity для ready; `confirm:781–782` отвергает известную замену | 54-08/09/22; при потере свежего доказательства остаётся описанный Б3, 54-10/23. Native гарантия identity NOTEXEC и не finding сама по себе. |
| retry-request receipt | `plan:390–396` без ID удерживает pending; `_execute:1068–1075` принимает только тот же request_id | Статическое чтение точного кода, unchanged guard после AST equality; новых receipt-тестов не запускалось. Native receipt-договор NOTEXEC. |
| Полная terminal list | `terminals:645–653` проверяет list, truncated=false, handle/title и уникальность; `reconcile_lookups:853–857` при ошибке не доказывает отсутствие | 54-06/07. Признак completeness и реальная опись native NOTEXEC; не требуются новые поля/квалификация как условие этого ревью. |
| Composer трёх providers | `windows.composer:101–138` имеет существующие closed shapes; `observe:754–755` требует empty и ожидаемого provider, без busy/service/shell | Точное composer AST, numeric/draft neighbours 54-13 и unrendered 54-14; parse_screen/terminal transport — явные stubs. Полная live-проверка всех трёх providers NOTEXEC. |
| Directory fsync | `save_ledger:262–270`: file flush/fsync до replace; вызывающий locked не доходит до последующего действия при ошибке записи | Unchanged raw/AST и статическая трасса; own нормальные файловые записи есть, fault/power crash и directory durability NOTEXEC. Отсутствие directory fsync не начисляется как дефект этой задачи. |

## Полнота чтения и проверок

Прочитан полный 315-строчный delta, все полные изменённые production-функции и необходимые соседние helpers: `_record_problem`, новый `may_continue`, `plan`, `Orca.terminals/observe/confirm`, `run_pass`, новый `_drop_reservation`, `_execute`. Прочитаны полные изменённые author-методы и весь добавленный `Repair3`; author tests не выполнялись. Для unchanged зависимостей `tasks/windows/automation/watchcfg/collector/cammeta-windows` сначала подтверждено равенство собственным ранее прочитанным байтам. Повторно прочитаны composer/read-terminal/parse-screen context и нужные constants. Нет заявления о новом полном чтении всех queues/tasks/dashboard или о повторе 795-function inventory.

Статическая трасса: `cammeta-windows.main → run_pass → snapshot/reconcile/observe/model → locked apply/plan/reserve → _execute`. Длинные callbacks остаются вне ledger lock; phase source перед recovery-prompt также читается вне lock. Результаты привязаны к rid/handle и новому operation-id. Остальные прежние CLOSED причины и чужие merge-context причины не переоткрывались.

`FUNCTION-DELTA.json` содержит raw/AST двух сторон для функций двух изменённых файлов, отдельно показывает unchanged; `AST-PROJECTIONS.json` — действительно выбранные для UNIT узлы под Python3.12.15. `CODE-IDENTITIES.json` удерживает exact Git mode/blob/size/SHA. Subject AGENTS отсутствует (`absent:true`), а не выдуманный blob; subject CLAUDE прочитан. Course AGENTS — link blob к CLAUDE; применимые инструкции/§1/doc rules использованы после byte equality. Усечённый интерфейсом длинный вывод не принимался за новое полное чтение; для повторно используемых §1 норм имеется отдельная byte-equality запись.

### Свежие исполнения

Только `/opt/check-env/lesson-spec/bin/python -B`, Python3.12.15, outer timeout60с. Все default paths в AST globals направлены в owned scratch до exec. Project modules не импортируются. Реальные subprocess/network/signal и файловые пути вне worker блокирует audit guard до AST exec. Exact Orca runner, terminal read и task model transport замещены. `windows.composer` — exact AST; `parse_screen` — явно заданный busy/service boundary, не проверка полноты parser. Own ledger/lock/fsync выполняются на owned FS.

| Процесс | Завершённые case executions | Итог |
| --- | ---: | --- |
| `controls54.py` | 3 | 3 PASS; затем CheckingError собственного AST support: пропущены RECORD_FIELDS/STATUSES |
| `controls54_v2.py` | 18 новых | 17 PASS, 1 воспроизведение остатка Б3; первые три records перенесены без повторного исполнения |
| `confirm54_boundary.py` | 2 | 1 PASS normal composition, 1 воспроизведение того же Б3 |

Итого **3 UNIT-попытки процессов, 2 успешно завершённых; 23 исполнения / 23 уникальных case-ID / 43 перечисленных подварианта; 21 PASS control и 2 RESIDUAL_REPRO одного прежнего корня**. Эти counts не складываются с прежними 39/46 или author suites. Новых author-test executions0, old-suite replays0, semantic kills0. Неожиданных внешних эффектов0. В 54-22/23 удержаны четыре fake runner calls; это не полный счёт всех stubs в остальных cases и не native calls.

Сохранены две собственные ошибки: один utility FileNotFoundError из неверного пути `instructions/doc-language.mdc` вместо `.cursor/rules/...`; один CheckingError harness из пропуска actual constants. Первые stdout/stderr не исправлялись. Исправлен только owned harness; subject/ожидания не менялись. Первые три успешных cases не повторялись ради зелёного результата. Все completed cases немедленно deep-copy сериализованы в raw JSON; итоговый `raw_vs_cases_equal=true` сверен с сохранёнными records. Полные argv/cwd/UTC start/end/exit/stdout/stderr каждого logged процесса удержаны.

Native Orca/list/create/send/close, настоящие окна/agent starts, работа collector/services, Git worktree/check_spec, реальные task-команды — **NOTEXEC**. Никаких candidate/J/Source/Go/model/full9/GATE действий. Это UNIT/static review инструментов, а не доказательство правильности живого backend либо продукта. Полезная работа завершена раньше начальной оценки; искусственного ожидания нет.

## Сохранность и передача

Новые artifacts находятся только в `/home/pilot/review103/orch5-4-delta-2881863/worker`. Оригинальные inputs, bare Git, старые отчёты/доказательства и развёрнутые файлы не менялись. В course WT разрешён только этот untracked отчёт; external REPORT.md равен ему побайтно. Начальный/final HEAD, branch, raw index SHA, отсутствие staged/tracked изменений и input/code identities — `PRESERVATION.json`. Проверки Git используют exact-root wrapper; optional index refresh отключён.

Матрица — `CLOSURE-MATRIX.json`, старый остаток и новый нулевой счёт — `FINDINGS.json`, чтение — `COVERAGE.json`, ошибки — `ERRORS.json`, точный счёт и raw captures — `TEST-ACCOUNTING-FINAL.json` и `captures/`. INDEX содержит только замороженные artifacts с size/SHA, исключает себя, READY/RESULT, active journals, scratch и незавершённый finalizer capture. Нет циклического self-hash. READY связывает pins, отчёт, индекс, dispositions и пределы.

Пробела входа нет. FULL означает законченное узкое поручение при одном явно описанном остатке. Worker не выполнял stage/commit/push/merge/taskops, сообщения, selfaccept или публикацию. Лично принимает результат, публикует один report-only main commit и делает taskdone родитель.


## Личная проверка родителем review103

Полный отчёт и матрица прочитаны лично. По удержанному коду проверены фазовое ограждение recovery-prompt и повторное чтение перед исполнением, связь резерва с rid/op-id, а также `observe`→`confirm` при ошибке свежего terminal-list. Изолированная программа 54-22/23 использует точные оба метода и fake runner, а ожидаемый смысл берёт из TASK: отсутствие достаточного подтверждения должно оставаться unproven. Родитель подтверждает **5 CLOSED / 1 PARTIAL (Б3), новых Б0/С0/М0**. Это внутренний fallback после уже предусмотренной ошибки чтения, а не новый дефект от отсутствия live-квалификации. Все шесть исключений владельца остаются ограничениями доказательства.

Независимый metadata-audit сверил **185 файлов** worker-индекса по SHA256/size; **15 pinned Git records** (14 blobs и одно отсутствие AGENTS.md), parent/tree и полный two-file diff. Под тем же Python 3.12.15 проверены **382 raw/AST записи**: 57 UNIT projections и 325 отдельных before/after function records. Это соответствие байтов, не новое полное смысловое чтение неизменённых зависимостей. Все **23 первичные case-записи** сопоставлены с полными stdout/stderr/argv/cwd/exit и сохранёнными cases: три завершились в первом процессе до harness NameError; следующие 18 исполнены в исправленном own harness; последние два — отдельная normal/error композиция. Первые три записи перенесены во второй summary без повторного исполнения; суммирование summary21 с этими тремя повторно не производилось. Исходные один harness CheckingError и один utility error сохранены и не превращены в дефект subject/kill.

В собственном metadata-audit родителя первая попытка завершилась TypeError при формировании записи с повторным ключом file. Она и исходный script сохранены. Исправлено только формирование собственного metadata-record; завершённые неизменяемые Git captures переиспользованы, reviewed code/tests повторно не запускались. Проверка завершена в audit2; index/HEAD/branch и отсутствие tracked/staged изменений до публикации подтверждены. Новых subject/test процессов родителя — **0**. Усечённые интерфейсом чтения не считались полным чтением; критические ветви прочитаны отдельно. Уточнена только контекстная формулировка Q1, решение по нему не пересматривалось.

Worker REPORT/READY/INDEX неизменны; финальная разница — `parent-final/PARENT-REPORT.diff`. Личная приёмка worker служит подготовкой независимого отчёта к сдаче, не самоприёмом ORCH.5.4. Единственный принимающий — Архитектор. Normal report-only publication и remote/clean фиксируются в `parent-final/PUBLICATION.json`; квитанция — `parent-final/FINAL-PACKET.json`, taskdone — в отдельном `parent-final/taskdone/`. Проверяемый код и живое состояние не менялись.

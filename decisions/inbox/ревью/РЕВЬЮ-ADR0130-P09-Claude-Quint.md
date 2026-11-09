adr: 0130 (P/09, Quint)

# Модель Quint боевых свойств P/09 (агент) — review103-claude

Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется.

- Срез: `491b42822c64d74a3054be183ad50d4b9d875f03`. Источник вопросов: собственный замороженный отчёт `РЕВЬЮ-ADR0130-P09-Claude.md`, коммит `b05d2b0f` (не менялся).
- Фактический старт: 2026-11-09T00:29:15Z (`date -u`). Основной прогон завершён 2026-11-09T01:12:33Z, дополнительные строки — 01:13Z.
- Не читалось: отчёты других рецензентов, `review103-kimi*`, смысловой common-пакет, `Source`, кандидат 41, captures, runtime, частные судьи. Запускались только Quint/Apalache над моделями этого каталога; SUT, native и кандидат не исполнялись.
- Модели — это чтения текста норм при явных допущениях. Нарушение означает: текст допускает такой ход событий при этих допущениях. Ни одно утверждение не относится к `Source` или реализации.
- Проект: `decisions/inbox/ревью/quint-p09-491b4282/` (`keeper_backup.qnt`, `relay_turn.qnt`, `timing.qnt`, `outcomes.qnt`, `run.py`, `results.tsv`, `run.log`, `runs/`, `trial-mismatches.tsv`, `check_anchors.py`).

Итог: **91 запуск** (rust 85, Apalache 6; property 38, control 27, witness 18, mutant 8); совпало 88, не совпало 3 (k23, t03, t09 — объяснены ниже, строки оставлены). Семь мутантов пойманы все, один (t09) — только со второй попытки. Находки: Б1 подтверждена; С3, С7, С8, С11 подтверждены, у С7 и С8 уточнены; С6, С12, С14 уточнены, у С6 и С12 часть снята. Целиком не снята ни одна.

## Что смоделировано

Сокращения: `09.1`, `09.2` — `Platform/09-agent/spec/09.N-agent.norms.md`; `turn`, `acc`, `ev` — `Platform/common/contracts/{turn,accept,event-journal}.md`; `const09`, `const08`, `const06` — `forms/runtime-constants.tsv` глав 09, 08, 06; `08.4`, `08.8`, `08.10`, `06.1`, `06.7` — нормы этих глав; `A1` — `Platform/09-agent/acceptance/1/README.md`.

| Модуль | Находка | Что выражено | Граница |
|---|---|---|---|
| `keeper_backup` | Б1, С11, часть С14 | голова, указатель, объект и строка у хранителя, части по двери, шаг 3 передачи, потеря держателя | 1 хранитель; 2 секции (одна ссылочная); MAXH=2, для С11 MAXH=7 при BACKUP_HEADS=5 |
| `relay_turn` | С7, С6 | строка очереди, два агента, продление, перехват, пауза, kill, SIGTERM, дверь, запрос члена, запись под охраной, принятая работа | 2 агента, 1 член; шаг времени TURN_RENEW; TURN_TERM=45, TURN_RENEW=10 |
| `timing` / `pass_base` | С3 | последовательное или параллельное следование, отчёт, правило пометки `acc:302` | до 60 консолей; единица — полсекунды, детерминированно |
| `timing` / `clock_asof_base` | С8 | скачок вперёд и возврат, `as_of`, `reached`, обещание `GRANT_LIFETIME` | один скачок J=7200 (параметр модели, не норма) |
| `timing` / `clock_alarm_base` | С8 | фронт тревог, штамп журнала, `to` страницы, проверка раз в секунду | один скачок J=20 (параметр), одна тревога в ожидании |
| `timing` / `storm_base` | С12 | когорта 409 `rebase`, затем целое | счётчики, детерминированно |
| `outcomes` / `report_base` | С14 | дельта против базы, потеря ответа, 409 `rebase`, целое | 2 ключа документа |
| `outcomes` / `edit_base` | С14 | правка с ключом, потерянный ответ, падение до и после записи цели, срок памяти ответа | одна правка, до 12 посылок |

Времена и пределы взяты из норм с якорями: `TURN_TERM`, `TURN_RENEW` (`turn:32-33`); 3 с на консоль (`09.1:1468`); `REPORT_EVERY`, `FRESH_EVERY`, `URGENT_GAP` (`const09:3,7,15`); `LOST_AFTER` 45 с и `MARK_REFRESH` 22.5 с (`A1:40`); `BACKUP_HEADS`, `GRANT_LIFETIME`, `REPORT_RATE` (`const08:49,18,36`); `CLAIM_TAKEOVER_AFTER`, `DONE_ANSWER_KEEP` (`const06:32,33`). Величина скачка J и число консолей — параметры модели, новых нормативных чисел отчёт не вводит.

Там, где норма допускает разные прочтения, они заведены как константы и не сведены к одному: `RULE` у хранителя, `READ`/`PERIOD` у прохода, `DOOR_RULE`, `STOP_RULE`. Значения «гипотеза» (`parts_first`, `referenced`, `close`, `drain`, `clamp`, `mono`) нормой не заданы и служат контролями, предложением нормы не являются.

## Таблица прогонов

Полностью с параметрами — `results.tsv`. `violated` у property означает: текст допускает нарушение при допущениях.

| id | модуль | инвариант | вид | инстр. | шаги | выборки | ожидание | факт | совп. | с |
|---|---|---|---|---|---|---|---|---|---|---|
| k01 | keeper_head_only | TakenHasParts | property | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k02 | keeper_head_only | HandoverTargetComplete | property | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k03 | keeper_head_only | RestoreAfterLoss | property | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k04 | keeper_head_only | TakenBehindObject | property | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k05 | keeper_all_parts | TakenHasParts | property | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k06 | keeper_all_parts | HandoverTargetComplete | property | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k07 | keeper_all_parts | RestoreAfterLoss | property | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k08 | keeper_all_parts | LastCopyServable | property | rust | 15 | 30000 | violated | violated | yes | 0.6 |
| k09 | keeper_parts_first | LastCopyServable | control | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k10 | keeper_parts_first | TakenHasParts | control | rust | 15 | 30000 | ok | ok | yes | 0.6 |
| k11 | keeper_head_only | witHeadOnlyHandover | witness | rust | 14 | 40000 | violated | violated | yes | 0.6 |
| k12 | keeper_all_parts | witAllPartsTaken | witness | rust | 14 | 40000 | violated | violated | yes | 0.6 |
| k13 | keeper_mut_somepart | TakenHasParts | mutant | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k14 | keeper_mut_count | TakenHasParts | mutant | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k15 | keeper_mut_eager | TakenHasParts | mutant | rust | 14 | 30000 | violated | violated | yes | 0.6 |
| k16 | keeper_disk_text | KeeperDiskBounded | property | rust | 40 | 20000 | violated | violated | yes | 0.6 |
| k17 | keeper_disk_ctrl | KeeperDiskBounded | control | rust | 40 | 20000 | ok | ok | yes | 0.8 |
| k18 | keeper_disk_text | witDisk | witness | rust | 40 | 20000 | violated | violated | yes | 0.6 |
| k19 | keeper_all_parts | witTaken | control | rust | 12 | 20000 | violated | violated | yes | 0.6 |
| k23 | keeper_all_parts | witCopyReplaced | witness | rust | 16 | 60000 | violated | violated | no | 0.6 |
| k20 | keeper_all_parts | TakenHasParts | property | apalache | 12 | 0 | ok | ok | yes | 3.0 |
| k21 | keeper_head_only | TakenHasParts | property | apalache | 8 | 0 | violated | violated | yes | 1.2 |
| k22 | keeper_parts_first | LastCopyServable | control | apalache | 12 | 0 | ok | ok | yes | 2.0 |
| t01 | relay_text | DoorOnlyActive | property | rust | 60 | 200000 | violated | violated | yes | 1.0 |
| t02 | relay_text | NoStaleObserved | property | rust | 60 | 200000 | violated | violated | yes | 1.0 |
| t03 | relay_text | witStaleObserved | witness | rust | 60 | 300000 | violated | violated | no | 1.0 |
| t04 | relay_close | NoStaleObserved | control | rust | 60 | 200000 | ok | ok | yes | 15.8 |
| t05 | relay_close | NoStaleUnobserved | property | rust | 60 | 200000 | violated | violated | yes | 1.1 |
| t06 | relay_text | GuardNoLateWrite | property | rust | 30 | 100000 | ok | ok | yes | 8.4 |
| t07 | relay_mut_noguard | GuardNoLateWrite | mutant | rust | 24 | 60000 | violated | violated | yes | 1.0 |
| t08 | relay_text | HandoverBound | property | rust | 45 | 100000 | ok | ok | yes | 10.3 |
| t09 | relay_mut_slowwait | HandoverBound | mutant | rust | 45 | 60000 | violated | ok | no | 7.6 |
| t10 | relay_text | NoDroppedOnSigterm | property | rust | 24 | 40000 | violated | violated | yes | 0.9 |
| t11 | relay_drain | NoDroppedOnSigterm | control | rust | 24 | 40000 | ok | ok | yes | 3.1 |
| t12 | relay_text | witDropped | witness | rust | 20 | 40000 | violated | violated | yes | 0.9 |
| t13 | relay_text | witReleaseLost | witness | rust | 20 | 40000 | violated | violated | yes | 1.5 |
| t14 | relay_text | witWaiterTook | witness | rust | 45 | 100000 | violated | violated | yes | 6.1 |
| t15 | relay_text | OneActiveByRow | property | rust | 30 | 60000 | ok | ok | yes | 5.8 |
| t16 | relay_text | witServed | control | rust | 20 | 40000 | violated | violated | yes | 0.9 |
| t17 | relay_text | GuardNoLateWrite | property | apalache | 12 | 0 | ok | ok | yes | 177.2 |
| t18 | relay_text | HandoverBound | property | apalache | 16 | 0 | ok | ok | yes | 312.5 |
| p01 | pass_seq_0 | GapBelowLost | control | rust | 40 | 5 | ok | ok | yes | 0.6 |
| p02 | pass_seq_14 | GapBelowLost | property | rust | 60 | 5 | ok | ok | yes | 0.6 |
| p03 | pass_seq_15 | GapBelowLost | property | rust | 60 | 5 | violated | violated | yes | 0.6 |
| p04 | pass_seq_15 | MarkFresh | property | rust | 60 | 5 | violated | violated | yes | 0.6 |
| p05 | pass_seq_14 | MarkFresh | property | rust | 60 | 5 | ok | ok | yes | 0.6 |
| p05b | pass_end_14 | GapBelowLost | property | rust | 60 | 5 | violated | violated | yes | 0.6 |
| p06 | pass_par_60 | GapBelowLost | control | rust | 60 | 5 | ok | ok | yes | 0.6 |
| p07 | pass_par_60 | MarkFresh | control | rust | 60 | 5 | ok | ok | yes | 0.6 |
| p08 | pass_seq_16 | witGapOver | witness | rust | 60 | 5 | violated | violated | yes | 0.6 |
| p09 | pass_seq_0 | witSent | control | rust | 10 | 5 | violated | violated | yes | 0.6 |
| c01 | clock_asof_nojump | AsOfNotFuture | control | rust | 20 | 40000 | ok | ok | yes | 0.9 |
| c02 | clock_asof_nojump | ReachedFresh | control | rust | 20 | 40000 | ok | ok | yes | 0.9 |
| c03 | clock_asof_nojump | RevokeBound | control | rust | 20 | 40000 | ok | ok | yes | 1.0 |
| c04 | clock_asof_text | AsOfNotFuture | property | rust | 20 | 40000 | violated | violated | yes | 0.6 |
| c05 | clock_asof_text | ReachedFresh | property | rust | 20 | 40000 | violated | violated | yes | 0.6 |
| c06 | clock_asof_text | RevokeBound | property | rust | 24 | 60000 | violated | violated | yes | 0.6 |
| c07 | clock_asof_text | witFutureAsOf | witness | rust | 20 | 40000 | violated | violated | yes | 0.6 |
| c08 | clock_asof_text | witStaleSkip | witness | rust | 20 | 60000 | violated | violated | yes | 0.6 |
| c09 | clock_asof_clamp | AsOfNotFuture | control | rust | 20 | 40000 | ok | ok | yes | 0.9 |
| c10 | clock_asof_clamp | RevokeBound | control | rust | 24 | 60000 | violated | violated | yes | 0.6 |
| c10b | clock_asof_mono | AsOfNotFuture | control | rust | 20 | 40000 | ok | ok | yes | 1.0 |
| c10c | clock_asof_mono | RevokeBound | control | rust | 24 | 60000 | ok | ok | yes | 1.6 |
| c11 | clock_asof_nojump | witCarry | control | rust | 8 | 5000 | violated | violated | yes | 0.9 |
| c12 | alarm_nojump | AlarmBound | control | rust | 40 | 60000 | ok | ok | yes | 2.8 |
| c13 | alarm_text | AlarmBound | property | rust | 40 | 100000 | violated | violated | yes | 0.6 |
| c14 | alarm_text | ToNotFuture | property | rust | 30 | 60000 | violated | violated | yes | 0.6 |
| c15 | alarm_text | witAlarmStuck | witness | rust | 40 | 100000 | violated | violated | yes | 0.6 |
| c16 | alarm_mono | AlarmBound | control | rust | 40 | 100000 | ok | ok | yes | 3.1 |
| c17 | alarm_mut_nocheck | AlarmBound | mutant | rust | 20 | 30000 | violated | violated | yes | 0.6 |
| c18 | alarm_nojump | witPageBuilt | control | rust | 15 | 20000 | violated | violated | yes | 0.6 |
| s01 | storm_sync_200 | BurstWithinRate | control | rust | 10 | 5 | ok | ok | yes | 0.6 |
| s02 | storm_sync_201 | BurstWithinRate | property | rust | 10 | 5 | violated | violated | yes | 0.6 |
| s03 | storm_uni_1000 | BurstWithinRate | control | rust | 10 | 5 | ok | ok | yes | 0.6 |
| s04 | storm_uni_1001 | BurstWithinRate | property | rust | 10 | 5 | violated | violated | yes | 0.6 |
| s05 | storm_sync_201 | PerMemberBounded | property | rust | 10 | 5 | ok | ok | yes | 0.6 |
| s06 | storm_sync_201 | witBurst | witness | rust | 10 | 5 | violated | violated | yes | 0.6 |
| s07 | storm_sync_200 | witFired | control | rust | 10 | 5 | violated | violated | yes | 0.6 |
| o01 | report_text | ConfirmedMatches | property | rust | 18 | 60000 | ok | ok | yes | 0.9 |
| o02 | report_text | BaseNotAhead | property | rust | 18 | 60000 | ok | ok | yes | 0.8 |
| o03 | report_mut_nobase | ConfirmedMatches | mutant | rust | 16 | 60000 | violated | violated | yes | 0.5 |
| o04 | report_text | witRebaseConverge | witness | rust | 18 | 80000 | violated | violated | yes | 0.5 |
| o05 | report_text | ConfirmedMatches | property | apalache | 10 | 0 | ok | ok | yes | 457.4 |
| o06 | edit_text | AtMostOnce | property | rust | 16 | 60000 | violated | violated | yes | 0.5 |
| o07 | edit_inf | AtMostOnce | control | rust | 16 | 60000 | ok | ok | yes | 0.9 |
| o08 | edit_inf | witSaved | witness | rust | 12 | 20000 | violated | violated | yes | 0.5 |
| o09 | edit_text | witAppliedTwice | witness | rust | 16 | 60000 | violated | violated | yes | 0.5 |
| k23r | keeper_all_parts | witCopyReplaced | witness | rust | 16 | 60000 | violated | violated | yes | 0.6 |
| t03r | relay_text | witStaleObserved | witness | rust | 60 | 300000 | violated | violated | yes | 1.0 |
| t08r | relay_text | HandoverBound | property | rust | 45 | 200000 | ok | ok | yes | 13.8 |
| t09r | relay_mut_slowwait | HandoverBound | mutant | rust | 45 | 200000 | violated | violated | yes | 12.6 |

Несовпадения основного прогона (строки оставлены):

- **k23** — нарушение найдено, но проверка порядка не прошла: заданный порядок требовал `newHead` после `writeTaken`, а новая голова может появиться раньше, важен лишь указатель. Ошибка спецификации порядка, не модели. Повтор k23r с порядком «строка головы 1, затем указатель, затем объект головы 2» совпал.
- **t03** — та же причина: `resume` может идти до перехвата очереди в ту же секунду. Трасса при этом показала заявленный эффект (`runs/t03.itf.json`). Повтор t03r с порядком «взял, пауза, чужой взял, потеря увидена, POST» совпал.
- **t09** — мутант `WAIT_X=2` не пойман случайной симуляцией на шаге `stepBound` при 60 000 выборок (в пробе тот же запуск его ловил: семя не фиксировано). Это предел метода, а не свойство мутанта. Повтор t09r на фокусном шаге `stepKill` при 200 000 выборок поймал. Следствие: «ok» у t08 на `stepBound` слабое свидетельство; опираться следует на t08r (тот же шаг, что t09r) и t18 (Apalache).

Пробные расхождения и их причины — `trial-mismatches.tsv`: их показания использованы в уточнениях ниже (уборка частей, детектор фронта по штампу).

## Мутанты и контроли

| Мутант | Что сломано | Инвариант | Результат |
|---|---|---|---|
| k13 `some_part` | строка при любой части головы | `TakenHasParts` | пойман |
| k14 `count_only` | счёт частей без тождества | `TakenHasParts` | пойман |
| k15 `eager` | уборка при записи объекта | `TakenHasParts` | пойман |
| t07 `GUARD_ON=false` | охрана записей снята | `GuardNoLateWrite` | пойман |
| t09/t09r `WAIT_X=2` | ожидающий ждёт вдвое дольше | `HandoverBound` | t09 не пойман, t09r пойман |
| c17 тик без проверки | фронт не читается каждую секунду | `AlarmBound` | пойман |
| o03 шаг 3 выключен | дельта принимается на чужой базе | `ConfirmedMatches` | пойман |

Контроли невакуумности (запуски, где достижимость проверяется нахождением состояния): k19, t16, p09, c11, c18, s07. Контроли прочтений и гипотез, где свойство держится: k09, k10, k17, k22, t04, t11, p01, p06, p07, c01–c03, c09, c10b, c10c, c12, c16, s01, s03, o07. Контроль c10 задан с ожиданием нарушения: он показывает, что `clamp` обещания срока не закрывает.

Свидетели (k11, k12, k18, k23r, t03r, t12, t13, t14, p08, c07, c08, c15, s06, o04, o08, o09) проверены не по конечному флагу: `run.py` читает ITF трассы и требует заявленную последовательность действий; при её отсутствии строка считается несовпавшей (так были пойманы k23 и t03).

Проверка, что свойство ограничивает завершённое действие: `GapBelowLost` считается на отправке отчёта, а не в простое; `ReachedFresh` — на доставленном ответе; `AlarmBound` — по истинному времени с момента тревоги при обязательной проверке каждой секунды; `HandoverBound` — по времени с последнего изменения строки.

## Что подтвердило, сняло, уточнило находки

**Б1 подтверждена как следствие текста.** При чтении `09.1:590,1525` строка `domain/backup-taken` пишется без частей, и шаг 3 передачи пропускает цель без единой части (k01–k03, k21; порядок в k11: объект, строка, передача, потеря держателя при пустом `kParts`). При чтении `08.8:204` те же свойства держатся (k05–k07; Apalache k20 до 12 шагов). Модель не выбирает прочтение: противоречие глав остаётся. **Уточнение решения:** добавить условие «все части» в шаг 4 мало. Порядок `09.1:1525` пишет объект новой головы раньше её частей, а объект один (`09.1:53`, и `08.10:94-95` с `rev-*` относится к держателю): подтверждённая целая копия заменяется неполной (k08, k23r), вопреки `09.1:591` «нет выбрасывания». Контроль `parts_first` (объект и строка после всех частей) это закрывает (k09, k10, k22). Как именно менять порядок, решает владелец нормы. Неизвестный исход записи объекта не ломает порядок строки и объекта (k04).

**С3 подтверждена условно.** При последовательном следовании ложный `silent` достижим: `GapBelowLost` нарушено при 15 молчащих консолях, если `every` считается от начала прохода (p03, p04, p08), и уже при 14 — если от конца (p05b); при 14 от начала держится (p02, p05). При параллельном следовании нет даже при 60 консолях (p06, p07). Норма не называет ни параллельность, ни начало отсчёта `every`. Правило пометки `acc:302` порог не сдвигает. Прежний пример «20 консолей, 15 молчат» верен, порог 14–15 точнее. Это арифметика детерминированного хода, а не поиск гонки.

**С6 уточнена, часть снята.** Снимается следствие «уход с незапущенной передачей очереди без срока»: при живом ожидающем на сетке `TURN_RENEW` очередь переходит не позднее `TURN_TERM + 2·TURN_RENEW` = 65 с от последнего изменения строки (t08r; Apalache t18 до 16 шагов, что едва достигает этой границы; t14 kill). Там же новая деталь: SIGTERM, попавший на продление без ответа, даёт конфликт CAS, снятия не будет (`turn:56`, без повтора), и очередь уходит уже только по сроку (t13). Остаётся: судьба принятой работы и срок остановки. t10/t12 показывают брошенную работу, но это прямое следствие отсутствия правила, а не открытая гонка; контроль `drain` (t11) показывает только, что правило возможно. Срок остановки не моделировался: нормативного числа нет.

**С7 подтверждена, уточнена.** По буквальному тексту дверь остаётся открытой после того, как агент сам увидел потерю, и отвечает 200, так что член не уходит на следующий адрес (t01, t02, t03r). Закрытие при наблюдаемой потере снимает ответы после наблюдения (контроль t04), но не сводит инвариант «дверь открыта ⇒ очередь моя»: между потерей очереди и первым проходом после паузы окно остаётся (t05). В трассе t03 в одну секунду виден и второй активный по ролям; по строке активный один (t15). Норме нужно назвать и закрытие, и окно. Охрана записей держится (t06, t17; мутант t07) — это охрана стора, не внешних эффектов (М4 не затронута).

**С8 подтверждена, уточнена.** После скачка вперёд и возврата `as_of` остаётся в будущем (c04, c07), ответ не освежает `reached` при истинном прошедшем `FRESH_EVERY` (c05, c08), права отключённого члена живут дольше `GRANT_LIFETIME` от настоящей сборки (c06), новая тревога не пересобирает страницу (c13–c15). Без скачка всё держится (c01–c03, c12). **Уточнение решения:** снятие будущей метки при возврате недостаточно: обещание срока так не выполняется (`clamp`, c10), нужно считать `as_of` без влияния скачка (контроль `mono`, c10b, c10c). Сравнение фронта по штампу тоже ненадёжно, поскольку штамп нестрого возрастает (`ev:216`, пробное расхождение c16); контроль по счётчику строк держится. Обещание `08.4:898` прочитано как «от настоящего момента сборки» по определению `09.1:360`; буквально `as_of` определяет его сам.

**С11 подтверждена.** Без удаления (`09.1:54` — только `put`) части растут сверх живых у `BACKUP_HEADS` голов (k16, k18). Контроль-уборка держит предел (k17), причём проба показала: уборка только при записи строки недостаточна, части копятся и при движении указателя. Байты не моделировались.

**С12 уточнена, часть снята.** Снимается сценарий самоусиления: на событие rebase член шлёт не более 2 POST (`09.1:1437`: один повтор; s05), шторм не нарастает. Снимается и формулировка причины «держатель перезапустился, память потеряна»: это чтением, не моделью — поколения лежат объектами (`acc:37`), простой рестарт их не теряет; массовый 409 требует отсутствия или несовпадения метки (`acc:296`), за реле — его рестарта (`09.2:246`). Остаётся: при совпавшем старте всплеск целых равен числу серверов (s02 при 201 против `REPORT_RATE` 200; при равномерном разбросе порог 1001, s04). `REPORT_RATE` здесь лишь мерка: класс server под него не подпадает (`acc:218`), статус значения «unmeasured». Находка об отсутствии разброса (`09.1:270`) остаётся.

**С14 уточнена.** Логика отчёта корректна: потерянный ответ приводит к 409 `rebase` и целому, копия сходится (o01, o02, o05; порядок в o04), мутант без шага 3 ломается (o03). Находка о пробе остаётся: модель не заменяет шов. По правкам: при памяти ответов повтор применяет правку один раз (o07, o08). **Новая граница:** `09.1:458` не ограничивает повтор, а `DONE_ANSWER_KEEP` 86400 с — минимум; если ответы теряются дольше этого срока, правка без `If-Match` применяется второй раз (o06, o09). Достижимо только при суточной потере ответов консоли, поэтому это ограничение, а не новая серьёзная находка; `If-Match` не моделировался.

## Не вошло

| Находка | Причина |
|---|---|
| С1, С2, С4, С5, С9, С10, С13, С15, М1, М3, М5, М6 | статика: привязка к договорам, бюджеты, размер, форма и наличие проб, гонки не выражают |
| С2 в части зависшего вызова | «нет срока» не гонка; в модели С3 принято обратное допущение: каждая консоль укладывается в 3 с |
| М2 | выбор шкалы часов — вопрос текста; связанная часть про скачок — в С8 |
| М4 | внешний забор отсутствует по тексту; модель показывает только границу охраны стора |
| С7, занятый порт | один агент на сервер в модели, нормативного исхода нет |
| С6, порядок закрытия и срок | чисел и порядка в нормах нет, модель лишь изобрела бы их |

## Допущения и пределы

- Rust — случайная симуляция без фиксированного семени: «ok» значит «не найдено в N выборках», не доказательство; t09 это показал. Apalache — ограниченный поиск до указанного числа шагов (8–16), тоже не доказательство. Память: один процесс Apalache, `-Xmx4g`, порт 18827, строго последовательно, сервер остановлен по PID; падений нет.
- `keeper_backup`: окно `BACKUP_FETCH` (`08.8:203`) не моделируется, живость частей только по головам (в пользу хранителя); ответ `/api/backup` с разными указателем и объектом (`06.7:70`, `06.7:331`) не моделируется; порядок проверок `09.1:1521-1524` свёрнут до требования пары; подпись и сумма не моделируются.
- `relay_turn`: шаг времени равен `TURN_RENEW`, живой агент обязан пройти к сроку (допущение планирования); пауза двери без ответа не моделируется (пересекается с С2); часы процесса считаются идеальными; неизвестный исход записи строки очереди (`turn:58`) не моделируется, продление разделено только на применение и ответ; один адрес на сервер, занятый порт не рассматривался.
- `HandoverBound` проверен только для паузы и смерти держателя и при непрерывно живом ожидающем.
- `timing/pass`: ответы консолей ровно по 3 с и нулевая сеть. Другие затраты прохода (`09.1:334`, `09.1:442`) не включены: их добавление только снижает порог числа молчащих консолей, поэтому 14–15 — верхняя оценка порога.
- `clock_*`: один скачок, ответ прямой (`domain_age` 0), реле не моделируется; целые секунды и исключена коллизия тревоги и сборки страницы в одну секунду (артефакт шкалы); одна тревога в ожидании; скачок сам по себе не отличается от постоянного расхождения часов, и свойство судится только после возврата.
- `storm_base`: абстрактные когорты, нагрузка держателя и размер тела не моделируются; момент совпадения старта задан параметром `SPREAD`.
- `report_base`: линейный один член, отсутствие реле, `via`, `same_sent_at` и `busy`. `edit_base`: одна правка, без `If-Match` и порядка правок; `applied` считается по записи цели, повтор после потери ответа — следующим шагом, а не проходом.
- Якоря проверены `check_anchors.py` по байтам среза: 85 из 85 совпали. Перечень в скрипте.

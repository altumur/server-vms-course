adr: 0130 (P/02 службы и запуск, Quint)

# Модель Quint боевых свойств P/02: службы и запуск — review103-claude

Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется.

- Срез: `244355d161139bd6fe65fd68c7e5134598c21ba3`. Вход подтверждён SRC: `P02-INDEPENDENT-SUBMISSIONS-COMPLETE-COUNT-ONLY.json`, sha256 `f572348524f64744776c157f8ae49eba049fc2ea234f6020964fafb73c1643a1`.
- Фактический старт: 2026-11-08T16:46:00Z (`date -u`).
- Источник вопросов — только мой отчёт `РЕВЬЮ-ADR0130-P02-services-Claude.md` (коммит `ce5c2822`). Чужие отчёты, смысловой common-пакет, реализация Source, кандидат 41, captures, runtime, частные судьи не читались. systemd, юниты, SUT, native и кандидат не исполнялись: запускались только Quint и Apalache над моделями этого каталога.
- Результат «нарушение» — следствие текста нормы при допущениях ниже. О Source, реализации и настоящем systemd модель ничего не доказывает.
- Итог: 87 запусков, 86 совпали с ожиданием. Несовпадение одно (TR03), в ожидании ошибся я, разбор ниже. Мутанты: 15 из 15 пойманы. Якоря: скрипт `anchors.py`, 51 из 51 по байтам среза.

Сокращения те же, что в исходном отчёте: `02.N` — `Platform/02-installer/spec/02.N-installer.norms.md`; `machine` — `forms/rollout-poll.machine.yaml`; `pres`, `sc` — `Platform/common/contracts/presence-lock.md`, `store-client.md`; `03.2` — `Platform/03-worker/spec/03.2-worker.norms.md`.

Каталог проекта: `decisions/inbox/ревью/quint-p02-services-244355d1/` (`*.qnt`, `run.py`, `gen_traces.py`, `anchors.py`, `results.tsv`, `run.log`, `runs/`).

## Что смоделировано

| Модуль | Что | Находка | Граница | Инструмент |
|---|---|---|---|---|
| `workerstart.qnt` | Цепочка старта `Type=notify`: раннер, программа, `flock`, захват имени, `READY=1` или `nobody`, срок старта, перезапуск | С1, С2, часть С3 | Один юнит, до 2 запусков; время — целые секунды; один шаг = одно ожидание целиком | Apalache, 8–18 шагов |
| `workertimer.qnt` | `oneshot` и таймер: чтение, план, действия, повтор, сверка `uncertain` | С4 | Один раннер, 2–3 номера, 2 прохода | Apalache, 8–14 шагов |
| `socketact.qnt` | Сокет-активация против кода 2 и остановки оператора, `TriggerLimit` | С5 | Одна служба, один сокет, 8 действий | Apalache, 6–10 шагов |
| `rolloutsteps.qnt` | Шаги `rollout` вне машины опроса, барьер, прерывание и повтор, `W2C_HOLD` | С6 | Одна подсистема, до 3 попыток | Apalache, 10–12 шагов |
| `pollbound.qnt` | Оговорка `02.4:530`: рестарт по `RestartSec=2` виден хотя бы одной пачке | поддержка `machine` | 4 пачки, сотые секунды | Apalache |
| `rolloutpoll.qnt` | Перенос `machine` как есть: все переходы и действия, таймеры, порядок одного момента | сроки опроса | 3 голосующих, `ROLLOUT_WAIT` 4 с, до 6 пачек, 60 шагов | симулятор (rust), 20000 трасс |
| `rolloutpoll_traces.qnt` | 44 канонические трассы `rollout-poll.traces.tsv` как `run`, все `expect` как `assert` | сверка переноса | 249 строк трасс | `quint test` |

Времена из норм: `START_WAIT` 60 (`02.3:213`), `RestartSec` 2 (`02.4:49`), `OnUnitActiveSec` 60 (`02.4:105`), старение 60 (`02.4:224`, `02.4:225`), `stop_timeout` 20 и 50 (`02.4:88`, `02.1:235`), `BATCH`, `READ`, `ROLLOUT_WAIT` (`machine:38`, `machine:39`, `machine:40`, `02.4:560`). Значения не из норм названы зондами и не выдаются за норму: `TS=90` — умолчание `DefaultTimeoutStartSec` из man; `READ_OVER`, `FLOCK_MAX`, `START_MAX`, `READ_MAX`, `BARRIER_READ`, `ACT_BOUND` — параметры, которых норма не задаёт, причём в этом и состоит вопрос; пороговые значения 30/29 и 120/121 выведены из `START_WAIT` и `TS`.

Как задано время: один шаг модели — ожидание целиком, ограниченное срочным событием (`TS` убивает, ничья в пользу `Killed`). Для сроков этого достаточно: важны суммы и границы, а не число попыток.

## Таблица прогонов

Полная таблица — `results.tsv` (колонки `id,module,invariant,kind,tool,max_steps,samples,overrides,expect,actual,match,secs,file`), полный вывод — `runs/<id>.log`, контрпримеры — там же. Запусков 87: property 25, witness 16, mutant 15, control 31. Суммарно 587 с, самый долгий 16,7 с.

| id | модуль | инвариант | вид | инстр. | шаги | выборка | ожид. | факт | совп. | с | что проверяет |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WS01 | `ws_a` | `inv_noKill` | property | verify | 8 | 0 | violated | violated | yes | 6.8 | С1 START_WAIT у программы от exec, TS=90, чтение≤срока |
| WS02 | `ws_b` | `inv_noKill` | control | verify | 14 | 0 | holds | holds | yes | 7.8 | контроль: START_WAIT от старта юнита (exec), TS=90 |
| WS03 | `ws_c` | `inv_noKill` | property | verify | 8 | 0 | violated | violated | yes | 5.5 | С1 последнее чтение за START_WAIT на 30 (READ_OVER=TS−START_WAIT), база юнита |
| WS04 | `ws_c0` | `inv_noKill` | control | verify | 12 | 0 | holds | holds | yes | 6.8 | контроль: READ_OVER=29 — на границу нет |
| WS05 | `ws_d` | `inv_noKill` | property | verify | 8 | 0 | violated | violated | yes | 5.8 | С1 flock без срока (pres:32) при TS=90 |
| WS06 | `ws_e` | `inv_noKill` | property | verify | 8 | 0 | violated | violated | yes | 5.3 | граница: TS=120, база exec — ничья в пользу kill |
| WS07 | `ws_f` | `inv_noKill` | control | verify | 14 | 0 | holds | holds | yes | 6.3 | контроль: TS=121, база exec — минимальный безопасный срок |
| WS08 | `ws_g` | `inv_noKill` | control | verify | 14 | 0 | holds | holds | yes | 7.4 | контроль: TS=∞, база unit, flock ограничен — нет kill |
| WS09 | `ws_n` | `inv_nobodyNotKilled` | property | verify | 10 | 0 | violated | violated | yes | 6.8 | С2 nobody без READY до TS=90 |
| WS10 | `ws_nr` | `inv_nobodyNotKilled` | control | verify | 14 | 0 | holds | holds | yes | 8.5 | контроль: READY=1 при входе в цикл nobody |
| WS11 | `ws_ni` | `inv_nobodyNotKilled` | control | verify | 14 | 0 | holds | holds | yes | 9.0 | контроль: TS=∞ в ветке nobody |
| WS12 | `ws_n` | `killsLT2` | witness | verify | 18 | 0 | violated | violated | yes | 6.9 | С2 цикл перезапусков nobody: ≥2 убийства сроком |
| WS13 | `ws_h` | `inv_activatingBound` | property | verify | 8 | 0 | violated | violated | yes | 5.3 | С1/С2 TS=∞ + flock без срока: activating без предела |
| WS14 | `ws_hb` | `inv_activatingBound` | control | verify | 12 | 0 | holds | holds | yes | 6.5 | контроль: TS=∞, но flock≤60 — activating конечен |
| WS15 | `ws_b` | `notReady` | witness | verify | 10 | 0 | violated | violated | yes | 7.0 | достижимость Ready |
| WS16 | `ws_b` | `notExit1` | witness | verify | 8 | 0 | violated | violated | yes | 5.4 | достижимость exit 1 по START_WAIT |
| WS17 | `ws_b` | `notExit2` | witness | verify | 8 | 0 | violated | violated | yes | 5.1 | достижимость exit 2 |
| WS18 | `ws_n` | `notNobody` | witness | verify | 10 | 0 | violated | violated | yes | 6.0 | достижимость nobody |
| WS19 | `ws_m1` | `inv_readyAfterCapture` | mutant | verify | 10 | 0 | violated | violated | yes | 6.6 | мутант: READY=1 до захвата имени |
| WS20 | `ws_m2` | `inv_exit1Deadline` | mutant | verify | 8 | 0 | violated | violated | yes | 5.4 | мутант: конец START_WAIT не соблюдён |
| WS21 | `ws_m3` | `inv_noRestartAfter2` | mutant | verify | 10 | 0 | violated | violated | yes | 5.3 | мутант: перезапуск после exit 2 |
| WS22 | `ws_a` | `inv_exit1Deadline` | property | verify | 12 | 0 | holds | holds | yes | 5.9 | exit 1 не позже START_WAIT+READ_OVER своей базы |
| WS23 | `ws_b` | `inv_exit1Deadline` | property | verify | 12 | 0 | holds | holds | yes | 6.3 | то же, база unit |
| WS24 | `ws_n` | `inv_readyAfterCapture` | property | verify | 12 | 0 | holds | holds | yes | 8.0 | READY только после захвата имени |
| WS25 | `ws_b` | `inv_noRestartAfter2` | property | verify | 12 | 0 | holds | holds | yes | 7.2 | exit 2 не перезапускает |
| WT01 | `wt_a` | `inv_passBounded` | property | verify | 8 | 0 | violated | violated | yes | 5.7 | С4 3 номера × START_MAX 90 > период 60 |
| WT02 | `wt_a` | `inv_opsFresh` | property | verify | 8 | 0 | violated | violated | yes | 5.7 | С4 данные действия старше минуты |
| WT03 | `wt_a` | `inv_serial` | control | verify | 12 | 0 | holds | holds | yes | 14.0 | контроль: oneshot+таймер — проходы не параллельны |
| WT04 | `wt_a` | `inv_noStartWhileUncertain` | control | verify | 12 | 0 | holds | holds | yes | 16.0 | контроль: uncertain занят (правило 5) |
| WT05 | `wt_b` | `inv_passBounded` | control | verify | 12 | 0 | holds | holds | yes | 11.9 | контроль: 3 × 20 = период (STOP/START=20) |
| WT06 | `wt_b` | `inv_opsFresh` | control | verify | 12 | 0 | holds | holds | yes | 12.8 | контроль: то же, данные свежи |
| WT07 | `wt_c` | `inv_opsFresh` | control | verify | 12 | 0 | holds | holds | yes | 16.7 | контроль: перепроверка возраста перед каждым действием (не норма) |
| WT08 | `wt_d` | `inv_passBounded` | property | verify | 8 | 0 | violated | violated | yes | 5.5 | С4 чтение /metrics без срока |
| WT09 | `wt_e` | `inv_passBounded` | control | verify | 12 | 0 | holds | holds | yes | 11.9 | контроль: --no-block (не норма) |
| WT10 | `wt_e` | `inv_opsFresh` | control | verify | 12 | 0 | holds | holds | yes | 11.2 | контроль: --no-block, свежие данные |
| WT11 | `wt_m1` | `inv_noStartWhileUncertain` | mutant | verify | 14 | 0 | violated | violated | yes | 7.5 | мутант: план игнорирует uncertain |
| WT12 | `wt_m2` | `inv_serial` | mutant | verify | 8 | 0 | violated | violated | yes | 5.6 | мутант: два механизма (таймер и рука) параллельно |
| WT13 | `wt_a` | `notAct` | witness | verify | 8 | 0 | violated | violated | yes | 6.1 | достижимость действия |
| WT14 | `wt_b` | `notCompleted` | witness | verify | 14 | 0 | violated | violated | yes | 7.3 | достижимость двух завершённых проходов |
| SA01 | `sa_a` | `inv_code2NoRestart` | property | verify | 6 | 0 | violated | violated | yes | 5.7 | С5 сокет запускает службу после кода 2 |
| SA02 | `sa_a` | `inv_opStopHolds` | property | verify | 6 | 0 | violated | violated | yes | 4.5 | С5 окно оператора нарушено сокетом |
| SA03 | `sa_a` | `inv_sockNotFailed` | property | verify | 6 | 0 | violated | violated | yes | 4.7 | С5 TriggerLimit переводит сокет в failure |
| SA04 | `sa_a` | `inv_restartPrevent2` | control | verify | 10 | 0 | holds | holds | yes | 6.5 | контроль: путь Restart= кодом 2 закрыт (A1 не затрагивает) |
| SA05 | `sa_nosock` | `inv_code2NoRestart` | control | verify | 10 | 0 | holds | holds | yes | 6.1 | контроль: без активации сокета A1 не нарушено |
| SA06 | `sa_nosock` | `inv_opStopHolds` | control | verify | 10 | 0 | holds | holds | yes | 6.5 | контроль: без активации сокета окно держится |
| SA07 | `sa_fix2` | `inv_code2NoRestart` | control | verify | 10 | 0 | holds | holds | yes | 5.4 | контроль: код 2 останавливает сокеты (вариант лечения) |
| SA08 | `sa_fixop` | `inv_opStopHolds` | control | verify | 10 | 0 | holds | holds | yes | 5.3 | контроль: стоп оператора охватывает .socket |
| SA09 | `sa_notrig` | `inv_sockNotFailed` | control | verify | 8 | 0 | holds | holds | yes | 5.1 | контроль: TriggerLimit выключен |
| SA10 | `sa_m1` | `inv_restartPrevent2` | mutant | verify | 8 | 0 | violated | violated | yes | 5.0 | мутант: Restart= перезапускает код 2 |
| SA11 | `sa_a` | `notFailed2` | witness | verify | 6 | 0 | violated | violated | yes | 5.1 | достижимость exit 2 |
| SA12 | `sa_a` | `notRunning` | witness | verify | 6 | 0 | violated | violated | yes | 5.8 | достижимость работающей службы |
| RS01 | `rs_read` | `inv_barrierWithinWait` | property | verify | 10 | 0 | violated | violated | yes | 6.1 | С6 чтение барьера без срока — ROLLOUT_WAIT превышается |
| RS02 | `rs_bound` | `inv_barrierWithinWait` | control | verify | 10 | 0 | holds | holds | yes | 5.6 | контроль: чтение обрезается остатком ROLLOUT_WAIT (не норма) |
| RS03 | `rs_a` | `inv_noEnableBeforeEnd` | control | verify | 12 | 0 | holds | holds | yes | 5.4 | контроль: W2C_HOLD удерживает включение до конца (норма) |
| RS04 | `rs_m1` | `inv_noEnableBeforeEnd` | mutant | verify | 10 | 0 | violated | violated | yes | 5.0 | мутант: на повторе HOLD считают как при первой установке |
| RS05 | `rs_a` | `inv_doneAfterBarrier` | control | verify | 12 | 0 | holds | holds | yes | 6.4 | контроль: Done только с барьером в этой попытке |
| RS06 | `rs_m2` | `inv_doneAfterBarrier` | mutant | verify | 10 | 0 | violated | violated | yes | 4.8 | мутант: повтор завершается без барьера |
| RS07 | `rs_a` | `notDone` | witness | verify | 10 | 0 | violated | violated | yes | 4.5 | достижимость Done |
| RS08 | `rs_a` | `notRepeated` | witness | verify | 12 | 0 | violated | violated | yes | 6.1 | достижимость повтора |
| PB01 | `pb_ok` | `inv_seen` | property | verify | 1 | 0 | holds | holds | yes | 4.6 | 02.4:530 простой 2 с замечен пачкой: DOWN=2.00 |
| PB02 | `pb_ok201` | `inv_seen` | control | verify | 1 | 0 | holds | holds | yes | 5.5 | контроль: простой 2.01 с |
| PB03 | `pb_198` | `inv_seen` | mutant | verify | 1 | 0 | violated | violated | yes | 4.5 | мутант (RestartSec короче): простой 1.98 с не замечается |
| PB06 | `pb_199` | `inv_seen` | control | verify | 1 | 0 | holds | holds | yes | 4.2 | контроль: простой 1.99 с — граница целочисленной сетки (см. отчёт) |
| PB04 | `pb_short` | `inv_seen` | mutant | verify | 1 | 0 | violated | violated | yes | 4.6 | мутант: RestartSec=1, простой 1.00 с |
| PB05 | `pb_ok` | `inv_sanity` | witness | verify | 1 | 0 | holds | holds | yes | 5.2 | наблюдения не пусты (невакуумность) |
| RP01 | `rp_3f` | `inv_machine` | property | run | 60 | 20000 | holds | holds | yes | 12.6 | 8 инвариантов машины (machine: invariants) |
| RP02 | `rp_3f` | `inv_pollBounded` | property | run | 60 | 20000 | holds | holds | yes | 10.1 | опрос закрывается не позже ROLLOUT_WAIT |
| RP03 | `rp_3f` | `inv_lastAnswerThisBatch` | property | run | 60 | 20000 | holds | holds | yes | 10.2 | живой — только по ответу этого батча (late ignored) |
| RP04 | `rp_3f` | `inv_aliveReplyLive` | property | run | 60 | 20000 | holds | holds | yes | 10.3 | живой — только по живому ответу |
| RP05 | `rp_3f` | `inv_oneReadPerBatch` | property | run | 60 | 20000 | holds | holds | yes | 9.8 | одно чтение целей на батч |
| RP06 | `rp_3f` | `inv_lateCommitIgnored` | property | run | 60 | 20000 | holds | holds | yes | 9.8 | поздний commit игнорируется |
| RP07 | `rp_3f` | `inv_passQuorum` | property | run | 60 | 20000 | holds | holds | yes | 10.1 | pass только при живых ≥ quorum+1 |
| RP08 | `rp_3f` | `notPassed` | witness | run | 60 | 20000 | violated | violated | yes | 1.4 | достижимость passed |
| RP09 | `rp_3f` | `notRefused` | witness | run | 60 | 20000 | violated | violated | yes | 1.3 | достижимость refused |
| RP10 | `rp_3f` | `notBreakAll` | witness | run | 60 | 20000 | violated | violated | yes | 1.3 | достижимость обрыва всех |
| RP11 | `rp_3f` | `notExpired` | witness | run | 60 | 20000 | violated | violated | yes | 1.3 | достижимость wait_expired |
| RP12 | `rp_m1` | `inv_aliveReplyLive` | mutant | run | 60 | 20000 | violated | violated | yes | 1.3 | мутант: любой ответ живой |
| RP13 | `rp_m2` | `inv_lastAnswerThisBatch` | mutant | run | 60 | 20000 | violated | violated | yes | 1.4 | мутант: ответ чужой пачки учтён |
| RP14 | `rp_m3` | `inv_lateCommitIgnored` | mutant | run | 60 | 20000 | violated | violated | yes | 1.3 | мутант: read_expired не снимает чтение |
| RP15 | `rp_m4` | `inv_pollBounded` | mutant | run | 60 | 20000 | violated | violated | yes | 1.4 | мутант: нет wait_expired |
| RP16 | `rp_m5` | `inv_passQuorum` | mutant | run | 60 | 20000 | violated | violated | yes | 1.4 | мутант: судья quorum без запаса |
| TR01 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | holds | holds | yes | 10.5 | трассы канона rollout-poll.traces.tsv (44) |
| TR02 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | violated | violated | yes | 10.5 | негативный контроль: трассы на мутанте 1 (любой ответ живой) |
| TR03 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | violated | holds | NO | 10.5 | чувствительность трасс: мутант 2 (ответ чужой пачки учтён); ожидание не подтвердилось, см. отчёт |
| TR04 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | violated | violated | yes | 10.5 | чувствительность трасс: мутант 3 (read_expired не снимает чтение) |
| TR05 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | violated | violated | yes | 10.7 | чувствительность трасс: мутант 4 (нет wait_expired) |
| TR06 | `rolloutpoll_traces` | `traces(44)` | control | test | 0 | 1 | violated | violated | yes | 10.7 | чувствительность трасс: мутант 5 (судья без запаса) |

«holds» — нет нарушения в указанной границе шагов, а не доказательство для произвольной длины. Конфигурации `workerstart` без ветки `nobody` с `MAXSTARTS=1` (WS02, WS04, WS07, WS08, WS14) исчерпывающие: длина пути не больше 6 шагов при границе 12–14. Остальные — ограниченная проверка.

## Мутанты и контроли

Мутанты: 15 из 15 пойманы.

| Модуль | Мутант | Инвариант | id |
|---|---|---|---|
| start | `READY=1` до захвата имени | `inv_readyAfterCapture` | WS19 |
| start | Ожидание не ограничено `START_WAIT` | `inv_exit1Deadline` | WS20 |
| start | Перезапуск после кода 2 | `inv_noRestartAfter2` | WS21 |
| timer | План игнорирует `uncertain` | `inv_noStartWhileUncertain` | WT11 |
| timer | Два механизма запуска параллельно | `inv_serial` | WT12 |
| socket | `Restart=` перезапускает код 2 | `inv_restartPrevent2` | SA10 |
| rollout | На повторе `W2C_HOLD` считают как при первой установке | `inv_noEnableBeforeEnd` | RS04 |
| rollout | Повтор завершается без барьера | `inv_doneAfterBarrier` | RS06 |
| bound | Простой 1,98 с и 1,00 с вместо 2 с | `inv_seen` | PB03, PB04 |
| poll | Любой ответ живой | `inv_aliveReplyLive` | RP12 |
| poll | Учтён ответ чужой пачки | `inv_lastAnswerThisBatch` | RP13 |
| poll | `read_expired` не снимает чтение | `inv_lateCommitIgnored` | RP14 |
| poll | Нет `wait_expired` | `inv_pollBounded` | RP15 |
| poll | Судья без запаса: `quorum` вместо `quorum+1` | `inv_passQuorum` | RP16 |

Отрицательные контроли не дают ложной тревоги: это те же инварианты при исправленном параметре, результат `holds` (WS02, WS04, WS07, WS08, WS10, WS11, WS14, WT03–WT07, WT09, WT10, SA04–SA09, RS02, RS03, RS05, PB02, PB06). Свидетели невакуумности: 16 строк `witness`, в том числе достижимость Ready, кода 1, кода 2, `nobody`, действия таймера, двух завершённых проходов, работы и отказа службы, Done, повтора, `passed`, `refused`, обрыва всех, `wait_expired`.

Часть контролей проверяет правило, записанное в модель напрямую: RS03, RS05, SA05, SA06 держатся по построению. Они показывают, что нарушение появляется только с соответствующим допущением, а не проверяют норму отдельно.

### Несовпадение TR03 и чувствительность трасс

Проверка: те же 44 трассы на варианте машины с мутантом.

| id | Мутант | Трассы | Итог |
|---|---|---|---|
| TR02 | Любой ответ живой | 42 прошли, 2 упали | пойман |
| TR03 | Учтён ответ чужой пачки | 44 прошли | **не пойман** |
| TR04 | `read_expired` не снимает чтение | 40 прошли, 4 упали | пойман |
| TR05 | Нет `wait_expired` | 38 прошли, 6 упали | пойман |
| TR06 | Судья без запаса | 35 прошли, 9 упали | пойман |

Я ожидал, что TR03 упадёт; строка оставлена в `results.tsv` с `match=NO`. Ошибка в моём ожидании, а не в переносе: в трассах только два опоздавших ответа (`late-status-ignored`, `answer-at-tick-instant`), оба — `status 0 c` раньше `self 1`, и оба сверяют лишь `replied` и `need`. Мутант кладёт такой ответ в `held`, и эти поля не меняются. Опоздавшего `self` в трассах нет. Симулятор тот же мутант ловит (RP13), так что мутант не эквивалентен.

Наблюдение, не находка и в счёт не идёт: снятие проверки `self_status-1` и `status-1` канонические трассы не замечают. Закрыть можно одной трассой, где опоздавший ответ приходит после ответа `self` новой пачки. Статус «ПП» строки опроса в исходной матрице это не снимает: контролируемые сроки (`machine:73`) трассы ловят, TR04 и TR05 это показывают.

## Что подтвердило, сняло, уточнило находки

Статусы условны: «подтверждена» значит «следует из текста норм при перечисленных допущениях».

**С1 — подтверждена, формулировка уточнена.** Сквозного срока нет, но сценарий из отчёта «цепочка легко больше 90 с» верен только при одном из трёх условий:

| Условие | Результат | id |
|---|---|---|
| `START_WAIT` считается заново от exec программы (чтение `02.3:213`, спор С3) | Сумма до 120 с, убийство при `TS=90`. Граница точная: `TS=120` убивает (WS06), `TS=121` нет (WS07) | WS01 |
| Общий отсчёт от старта юнита, чтение в пределах остатка | Исход кода 1 к 60 с, убийства нет при `TS=90` | WS02 |
| Общий отсчёт, но последнее чтение выходит за `START_WAIT` (срок чтения — решение клиента, `sc:89`) | Убийство при выходе на 30 с и больше (`TS − START_WAIT`), при 29 — нет | WS03, WS04 |
| `flock` без срока (`pres:32`, `03.2:537`) | Убийство при `TS=90` | WS05 |

Значит, главная причина — не величина 90 с, а «чей старт» и несвязанность срока чтения с остатком окна. Формулировку С1 в разделе «Сценарий» следует читать так; предложенное там решение (единый срок от старта юнита с остатком для каждого чтения) модель поддерживает: это контроль WS02.

**С2 — подтверждена, решение уточнено.** Законный `nobody` при `READY=1` только после захвата имени (`02.4:116`, `03.2:555`) убивается сроком старта (WS09), и цикл повторяется: в контрпримере WS12 два убийства, 90 с и 182 с от начала. Контроли: `READY=1` при входе в цикл (WS10) и `TS=∞` (WS11) убийство снимают. Уточнение к «Решению» С2: вариант `TimeoutStartSec=infinity` сам по себе небезопасен, потому что при `flock` без срока юнит остаётся в `activating` без предела (WS13, контроль WS14 с конечным `flock`). С1 и С2 надо решать вместе; вариант `READY=1` при входе в цикл `nobody` от этой связи не зависит.

**С3 — уточнена часть «чей старт».** Выбор базы прямо меняет исход (WS01 против WS02). Остальное в С3 — exec или дочерний процесс, передача сигналов и кода, `NotifyAccess` — не моделировалось.

**С4 — подтверждена, уточнён характер ущерба.**
- Проход длиннее периода таймера при блокирующих `systemctl` (WT01); чтение `/metrics` без срока — то же (WT08).
- Наложения проходов при одном `oneshot`-юните и таймере нет (WT03, мутант WT12). Ущерб — задержка и остановка масштабирования, а не параллельные проходы. Это соответствует тому, что сериализация `02.4:236` держится на единственности юнита.
- Действия плана могут идти по данным старше минуты (WT02) — но только при чтении «правило 2 проверяется один раз на проход». При перепроверке перед каждым действием нарушения нет (WT07); норма (`02.4:224`) выбора не делает.
- Норма не говорит, ждёт ли скрипт задание `systemctl`: с `--no-block` проход мгновенный (WT09, WT10). Это отдельное непрописанное решение, важное для С4.
- Правило 5 про `uncertain` в модели держится (WT04, мутант WT11).

**С5 — подтверждена как следствие допущений A1–A3.** Служба после кода 2 снова поднимается сокетом (SA01), окно остановки оператора нарушается (SA02). Без активации сокета нарушений нет (SA05, SA06): связка держится только на A1, как и было сказано в отчёте. Сам путь `Restart=` кодом 2 закрыт (SA04, мутант SA10). Варианты лечения снимают нарушение: код 2 останавливает сокеты (SA07), оператор останавливает и `.socket` (SA08).

Часть про `TriggerLimit` ослабляю: SA03 показывает `failed` только при 21 и более срабатываниях за окно 2 с, а достижимость такого темпа модель не устанавливает. При паузе клиента 1 с (`02.3:212`) это условие на число клиентов и на длительность цикла запуска, которых норма не называет. В отчёте «уходит в отказ по `TriggerLimit`» следует читать как возможность при таком темпе, а не как установленное следствие.

**С6 — подтверждена в части чтения барьера; остальное не моделировалось.** `ROLLOUT_WAIT` не ограничивает опрос, если чтение барьера висит: в RS01 превышение на 99700 с при зонде 100000 с. Важна не величина, а отсутствие границы. Обрезка чтения остатком `ROLLOUT_WAIT` снимает нарушение (RS02). Машина опроса, в отличие от барьера, ограничена (RP02). Шаги `install` и остальные шаги `rollout` без срока — утверждение чтения, модель с параметром-длительностью дала бы тавтологию, поэтому не строилась. Прерывание и повтор: W2C_HOLD на повторе (`02.4:534`) и завершение только с барьером этой попытки держатся; мутанты пойманы (RS04, RS06). Правила записаны в модель прямо, поэтому это проверка согласованности маршрута повтора, а не новое свойство нормы.

**Машина опроса и оговорка `02.4:530` — подтверждены, находок нет.** Перенос совпал со всеми 44 трассами (TR01); инварианты машины и поведенческие свойства держатся в 20000 симуляциях по 60 шагов (RP01–RP07). Простой не короче 2 с виден хотя бы одной пачкой (PB01, PB02, с 1,98 с — нет, PB03). Граница модели — 1,99 с из-за целочисленной сетки в сотых (PB06): наблюдение берётся в `[k, k+0,99]`; в непрерывном времени граница равна 2 с.

Снято: ничего из находок модель не опровергла полностью. Ослаблены: формулировка С1 о сумме больше 90 с; часть С5 о `TriggerLimit`.

## Не вошло

| Находка | Причина |
|---|---|
| Б1 | Статика: `ProtectSystem=strict`, список записываемых путей. Гонки нет, модель времени не помогает |
| С3 (кроме «чей старт») | Поведение процессов и уведомлений, а не сроки; без реального исполнения модель ничего не добавит |
| С7 | Нет числа срока у консоли, ресурса, контроллера, доменных; модель свелась бы к сравнению параметра с параметром |
| С8, С9 | Бюджеты и пробы, вне модели |
| М1, М5, М6, М7 | Статика норм или стоимость |
| М2 | Вид часов не моделировался: одно монотонное время |
| М3, М4 | Шторм и macOS; разброс и массовый запуск в модель не включены |
| `install` и шаги `rollout` вне барьера | См. С6 |
| Манифест, данные и прочий остаток P/02 | Вне задания; второй проект по P/02 не создан |

## Допущения и пределы

Допущения о systemd — **не нормы курса**; сверены только по `man` systemd 252 на CT 103 (`systemd.service(5)`, `systemd.socket(5)`, `systemd.timer(5)`, `systemd-system.conf(5)`), настоящим исполнением не проверены.

| Модуль | Допущение |
|---|---|
| start | У `Type=notify` действует `DefaultTimeoutStartSec`, если `TimeoutStartSec` не задан: в нормах P/02 и P/03 и в общих договорах на срезе его нет ни в одной строке (`git grep`; строка юнита воркера — `02.4:87`). Истечение срока завершает службу, `Restart=always` перезапускает после `RestartSec`. Только главный процесс шлёт `READY=1`. Ничья «исход ровно на сроке» — в пользу убийства |
| timer | Один `oneshot`-юнит не запускается параллельно; пока он активен, таймер новый запуск не создаёт; следующий срок считается от прошлого запуска (`systemd.timer(5)`). Что таймер не создаёт параллельный запуск — вывод из единственности юнита, в man прямо не сказано и на настоящем systemd не проверено |
| timer | `systemctl start` ждёт завершения задания, для `Type=notify` — готовности или срока (`BLOCK`); норма `02.4:239` этого не говорит |
| socket A1 | Новое соединение при неактивной службе запускает её (`02.4:58` + man); код выхода на это не влияет. **Связка «сокет + код 2» выведена рассуждением** |
| socket A2 | Сокет продолжает слушать после кода 2 и после `systemctl stop` службы |
| socket A3 | `TriggerLimit`: 20 за 2 с при `Accept=no`, затем `failure`; норма его не называет |
| socket A4 | Срабатывание считается только при неработающей службе |
| poll | Ответы приходят не более раза, порядок одного момента — как в `machine:73` |

Пределы:

- `rolloutpoll.qnt` проверен только симулятором: внутреннее представление модели превышает лимит строки JSON RPC Apalache (20 МБ). Симуляция выборочная, не исчерпывающая, и только для конфигурации из 3 голосующих без `-last`. Ветки `-last` и не более 2 голосующих проверены только трассами.
- `pollbound.qnt` — проверка на одной конфигурации, 4 пачки.
- Числа `TS=90` и зонды в таблице сравнивают варианты, а не утверждают реальные величины.
- Время одного ожидания модель не разделяет на попытки с паузой 1 с; для сроков это не влияет, для нагрузки на store — не проверялось.
- Ветка кода 0 при смене метки, watchdog после старта, `StartLimit`, launchd и macOS, `TimeoutStopSec` не моделировались.
- Проба с удалением `read_done` (пробный прогон, в таблицу не включён) не поймана: при ответах не более одного раза вторая `read_commit` в пачке недостижима, защита оказывается избыточной. Заменён мутантом судьи (RP16).
- Модель не доказывает Source, реализацию или systemd и не является приёмкой. READY и GATE не заявляются. Выводы ограничены срезом `244355d1`.

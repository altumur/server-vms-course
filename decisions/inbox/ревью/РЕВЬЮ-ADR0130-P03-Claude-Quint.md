adr: 0130 (P/03, Quint)

# Модель Quint P/03 (воркер, 14 пунктов) на срезе 244355d1 — review103-claude

**Шапка.** Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется. Модель — следствие текста норм при перечисленных допущениях; она не доказывает ни Source, ни реализацию и не является сведением о них. Результат «нарушение» — достижимая в модели последовательность, разрешённая текстом нормы при допущениях; не дефект реализации.

- Срез: `244355d161139bd6fe65fd68c7e5134598c21ba3`. Вход подтверждён SRC: `P03-INDEPENDENT-SUBMISSIONS-COMPLETE-COUNT-ONLY.json`, sha256 `3038fd4e06b25ad67a847828639e9f9100084995bf406f87b5ea0213b9b7abb9`.
- Фактический старт: 2026-11-08 17:24:09 UTC (`date -u`).
- Источник вопросов: собственный замороженный отчёт `РЕВЬЮ-ADR0130-P03-Claude.md`, коммит `21dbe871`, находки С1–С15, М1–М5.
- Не читал: отчёты других рецензентов, файлы Kimi, смысловой common-пакет, реализацию Source, кандидат 41, captures, runtime, приватных судей. SUT, native и кандидат не исполнялись; запускались только Quint и Apalache над этими моделями.
- Каталог: `quint-p03-244355d1/` (`*.qnt`, `inst/`, `run.py`, `gen_traces.py`, `check_anchors.py`, `results.tsv`, `run.log`, `runs/`).
- Итог: **95 запусков**, итоговый прогон без несовпадений (0); пробные несовпадения: 18, см. `trial-mismatches.tsv`. Мутанты 14 из 14 пойманы. Снятых находок нет; подтверждены и уточнены С4, С5, С10, С11, С13, С14, С15 (раздел 4).

## 1. Что смоделировано

Время — параметр; в аренде один тик 1/12 с, чтобы `LEASE_EVERY` = 25/3 с, `STALL` = 25/2 с, `WAKE` ≤ 25/4 с были точными целыми; в действиях один тик 100 мс. Значения норм с якорем, прочие величины — входы (см. раздел 6).

### `p03_lease.qnt` — цикл, заместитель, шаг аренды, тишина, часы (С5, С11, С13, С15)

- Один процесс: поток цикла (шаги reconcile, pump, heartbeat, pause, `spec/03.3:80-106`) и поток заместителя (`03.4:374-385`). Шаг аренды: продление слота, чтение пола, подтверждения единиц по очереди (`03.2:568-575`). Операции с хранилищем — с задержкой; `t0` — момент посылки (`03.2:171`, `03.2:496`). Автомат `confirm`: `03.2:496-504`; `may_act`/`may_write`: `03.2:162,165`; `lost` на конце шага: `03.2:575`.
- Граница: `N` до 4 единиц, `FAULTS` переключений связи, один скачок стенных часов, горизонт времени 3000 тиков (250 с). Экземпляры — `inst/*.qnt`, см. параметры в `results.tsv`.
- Инварианты: `NoLost`, `LostOnlyPastCeiling`, `ActWithinWindowFromSend`, `ActWithinSlotTerm`, `FencedStays`, `LostStays`, `MissedIsLost`, `WriteOnlyInWindowOrCeiling`, `NoZenoAgain`, `StepsBounded`.

### `p03_stop.qnt` — штатная остановка (С4)

- Шаги `03.4:412-417`: остановка заместителя и опроса, `before_stop_all` и остановка единиц (одна фаза на единицы), последний пульс, отпуск места, отдача слота, `after_stop`. `stop_timeout` 20…50 с (`02.1:235`), обрыв по сроку без записей (`03.4:421`). Отпуск места — запись под слотом до отдачи (`03.2:429-430`). Заместитель перечитывает строку и видит `released` (`03.2:428`). Сводка окон подавления — под `may_write` (`03.6:77`).
- Граница: 8 фаз, 12 шагов Apalache.
- Инварианты: `NoWriteAfterRelease`, `PlaceBeforeSlot`, `NoStandinWriteAfterRelease`, `DoneReleased`, `KilledImpliesReleased`, `FinalFlushInMayWrite`, `PlaceBudgetGuaranteed` (арифметика `03.4:510`).

### `p03_perform.qnt` — действия группы (С10, С14)

- Одна группа, два держателя (передача эпохи), два запроса группы. Порядок проверок: `03.6:272-291`. Один незавершённый вызов на группу у держателя: `03.6:315`. Ожидание нового держателя: `03.6:317`. Закрытие чужого `begun` по `at` писателя: `03.6:275-277`. Срок заявки: `03.6:278,288`. Перекрытие вызовов двух держателей допускается нормой: `03.6:318`.
- Граница: 2 запроса, 2 держателя, смещения часов — параметры, 60 шагов симуляции, 12 шагов Apalache.
- Инварианты: `OnePerGroupOfHolder`, `TakeoverWaitHonored`, `OrderInGroup`, `NoEarlyForeignClose`, `NoEarlyExpire`, `NoSelfForeignClose`, `HungDoesNotBlockForever`.

### `p03_forms.qnt` — формы `contender-writer` и `token-cache`

- Перенесены как есть; 20 трасс `forms/*.traces.tsv` (8 и 12) преобразованы `gen_traces.py` в тесты Quint и пройдены (`forms-01-traces`). Смысл строк `transitions`: `forms/README.md:114,125-127`; часы и день — входы, а не обязанность формы (`forms/README.md:120`). Инварианты форм (`FormsInv`) держатся; мутанты трасс пойманы.
- Форма времени сама не считает (нет таймеров), поэтому гонок сроков формы не добавляют; проверяется только соответствие трассам и инвариантам форм.

## 2. Таблица прогонов

Сводка (95):

- control, ожидание holds, факт holds: 15
- mutant, ожидание violated, факт violated: 14
- property, ожидание holds, факт holds: 22
- property, ожидание violated, факт violated: 16
- witness, ожидание violated, факт violated: 28

Несовпадений ожидания с фактом нет.

В пробных запусках (до итогового) было 18 несовпадений ожидания с фактом и один остановленный вручную запуск; все строки, причины и решения: `quint-p03-244355d1/trial-mismatches.tsv`. Ни одно из них не отменено правкой ожиданий или нормы: причины — конфигурация запуска, распределение симуляции, модельные артефакты начального состояния (всё исправлено в экземплярах, не в ожидании), и один контроль (`lease-09`) показал, что нарушение давал другой эффект — он выделен отдельно в `lease-01`. Сырые выводы пробных запусков хранятся вне коммита в scratchpad этой сессии.

Строки `results.tsv` с `kind=witness` — инварианты-отрицания: нарушение значит «состояние достижимо» (свидетели невакуумности).

| id | модуль/экземпляр | инвариант | вид | инструмент | шаги | образцы | ожид. | факт | совп. | c |
|---|---|---|---|---|---|---|---|---|---|---|
| forms-01-traces | traces_ok | traces-all | control | quint-test |  |  | holds | holds | yes | 1.6 |
| forms-02-inv-sim | F_ok | FormsInv | property | quint-run-rust | 40 | 5000 | holds | holds | yes | 1.1 |
| forms-02b-inv-verify | F_ok | FormsInv | property | quint-verify | 10 |  | holds | holds | yes | 12.0 |
| forms-w1-cooldown | F_ok | W_cooldown | witness | quint-run-rust | 30 | 20000 | violated | violated | yes | 0.8 |
| forms-w2-nameless | F_ok | W_namelessPublished | witness | quint-run-rust | 20 | 5000 | violated | violated | yes | 0.8 |
| forms-m1-since-reset | traces_since_reset | traces-all | mutant | quint-test |  |  | violated | violated | yes | 1.8 |
| forms-m2-no-back | traces_no_back | traces-all | mutant | quint-test |  |  | violated | violated | yes | 1.8 |
| forms-m3-persist-early | traces_persist_early | traces-all | mutant | quint-test |  |  | violated | violated | yes | 1.7 |
| lease-01-stepsum-sim | L_stepsum | NoLost | property | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.9 |
| lease-01b-stepsum-verify | L_stepsum | NoLost | property | quint-verify | 18 |  | violated | violated | yes | 23.6 |
| lease-02-stepsum-ctl-sim | L_stepsum_ctl | NoLost | control | quint-run-rust | 60 | 5000 | holds | holds | yes | 1.2 |
| lease-02b-stepsum-ctl-verify | L_stepsum_ctl | NoLost | control | quint-verify | 16 |  | holds | holds | yes | 63.8 |
| lease-03-hung | L_hung | NoLost | property | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.9 |
| lease-04-hung-fix-ctl | L_hung_ctl_fix | NoLost | control | quint-run-rust | 40 | 5000 | holds | holds | yes | 1.2 |
| lease-05-slowN | L_slowN | NoLost | property | quint-run-rust | 60 | 5000 | violated | violated | yes | 0.9 |
| lease-06-slowN-noStandin | L_slowN_noStandin | NoLost | property | quint-run-rust | 60 | 5000 | violated | violated | yes | 0.9 |
| lease-07-slowN-ctl | L_slowN_ctl | NoLost | control | quint-run-rust | 60 | 5000 | holds | holds | yes | 1.2 |
| lease-08-silN | L_silN | LostOnlyPastCeiling | property | quint-run-rust | 60 | 5000 | violated | violated | yes | 0.9 |
| lease-09-silN-ctl | L_silN_ctl | LostOnlyPastCeiling | control | quint-run-rust | 60 | 5000 | holds | holds | yes | 1.1 |
| lease-10-silOff | L_silOff | LostOnlyPastCeiling | property | quint-run-rust | 60 | 5000 | holds | holds | yes | 1.2 |
| lease-11-silCeil | L_silCeil | LostOnlyPastCeiling | property | quint-run-rust | 60 | 5000 | holds | holds | yes | 1.3 |
| lease-12-wallCad | L_wallCad | NoLost | property | quint-run-rust | 100 | 8000 | violated | violated | yes | 1.0 |
| lease-13-wallCad-ctl | L_wallCad_ctl | NoLost | control | quint-run-rust | 100 | 5000 | holds | holds | yes | 1.4 |
| lease-14-wallAge | L_wallAge | NoLost | property | quint-run-rust | 80 | 5000 | violated | violated | yes | 1.0 |
| lease-15-wallAge-ctl | L_wallAge_ctl | NoLost | control | quint-run-rust | 80 | 5000 | holds | holds | yes | 1.4 |
| lease-16-zeno | L_zeno | NoZenoAgain | property | quint-verify | 18 |  | violated | violated | yes | 16.0 |
| lease-17-zeno-ctl | L_zeno_ctl | StepsBounded | control | quint-verify | 18 |  | holds | holds | yes | 18.6 |
| lease-17b-zeno-ctl-sim | L_zeno_ctl | StepsBounded | control | quint-run-rust | 200 | 2000 | holds | holds | yes | 1.4 |
| lease-20-window | L_any | ActWithinWindowFromSend | property | quint-run-rust | 80 | 8000 | holds | holds | yes | 1.7 |
| lease-20b-window-verify | L_small | ActWithinWindowFromSend | property | quint-verify | 12 |  | holds | holds | yes | 150.7 |
| lease-21-slotterm | L_any | ActWithinSlotTerm | property | quint-run-rust | 80 | 8000 | holds | holds | yes | 1.6 |
| lease-22-fencedstays | L_any | FencedStays | property | quint-run-rust | 80 | 8000 | holds | holds | yes | 1.6 |
| lease-23-loststays | L_any | LostStays | property | quint-run-rust | 80 | 8000 | holds | holds | yes | 1.5 |
| lease-24-missedlost | L_any | MissedIsLost | property | quint-run-rust | 80 | 8000 | holds | holds | yes | 1.6 |
| lease-25-writealg | L_small | WriteOnlyInWindowOrCeiling | property | quint-verify | 12 |  | holds | holds | yes | 48.9 |
| lease-w1-lost | L_any | W_lost | witness | quint-run-rust | 80 | 8000 | violated | violated | yes | 1.3 |
| lease-w2-silent | L_any | W_silent | witness | quint-run-rust | 80 | 8000 | violated | violated | yes | 1.1 |
| lease-w3-recovered | L_recover | W_recovered | witness | quint-run-rust | 100 | 8000 | violated | violated | yes | 0.9 |
| lease-w4-standin | L_any | W_standin | witness | quint-run-rust | 80 | 8000 | violated | violated | yes | 0.9 |
| lease-w5-fenced | L_any | W_fenced | witness | quint-run-rust | 80 | 8000 | violated | violated | yes | 0.9 |
| lease-w6-nobody | L_foreign | W_nobody | witness | quint-run-rust | 60 | 3000 | violated | violated | yes | 0.9 |
| lease-w7-slotterm | L_writefault | W_slot_term_over | witness | quint-run-rust | 100 | 8000 | violated | violated | yes | 0.9 |
| lease-w8-silent-ctl-nonvacuous | L_silCeil | W_silent | witness | quint-run-rust | 60 | 5000 | violated | violated | yes | 0.9 |
| lease-w9-silN-silent | L_silN | W_silent | witness | quint-run-rust | 60 | 5000 | violated | violated | yes | 0.9 |
| lease-w10-lost-silOff | L_silOff | W_lost | witness | quint-run-rust | 80 | 8000 | violated | violated | yes | 0.9 |
| lease-w11-lost-silCeil | L_silCeil | W_lost | witness | quint-run-rust | 100 | 8000 | violated | violated | yes | 1.0 |
| lease-w12-steps-ctl | L_stepsum_ctl | W_leaseStep | witness | quint-run-rust | 60 | 3000 | violated | violated | yes | 0.9 |
| lease-w13-silent-silN-ctl | L_silN_ctl | W_silent | witness | quint-run-rust | 60 | 3000 | violated | violated | yes | 0.9 |
| lease-w14-standin-fix | L_hung_ctl_fix | W_standin | witness | quint-run-rust | 40 | 3000 | violated | violated | yes | 0.9 |
| lease-m1-last-at-answer | L_m_lastAns | ActWithinWindowFromSend | mutant | quint-run-rust | 40 | 5000 | violated | violated | yes | 1.0 |
| lease-m2-slot-at-answer | L_m_slotAns | ActWithinSlotTerm | mutant | quint-run-rust | 100 | 8000 | violated | violated | yes | 1.1 |
| lease-m3-revive-fenced | L_m_fenced | FencedStays | mutant | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.9 |
| lease-m4-revive-oversleep | L_m_oversleep | MissedIsLost | mutant | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.9 |
| stop-01-ok-verify | S_ok | NoWriteAfterRelease | property | quint-verify | 12 |  | holds | holds | yes | 4.6 |
| stop-02-order | S_ok | PlaceBeforeSlot | property | quint-verify | 12 |  | holds | holds | yes | 4.6 |
| stop-03-standin | S_ok | NoStandinWriteAfterRelease | property | quint-verify | 12 |  | holds | holds | yes | 4.6 |
| stop-04-done | S_ok | DoneReleased | property | quint-verify | 12 |  | holds | holds | yes | 4.6 |
| stop-05-hang-killed | S_hang | KilledImpliesReleased | property | quint-verify | 12 |  | violated | violated | yes | 4.5 |
| stop-06-hang50-killed | S_hang50 | KilledImpliesReleased | property | quint-verify | 12 |  | violated | violated | yes | 4.5 |
| stop-07-budget-ctl | S_budget_ctl | KilledImpliesReleased | control | quint-verify | 12 |  | holds | holds | yes | 4.6 |
| stop-08-budget-used | S_budget_ctl | W_budget_used | witness | quint-verify | 12 |  | violated | violated | yes | 4.5 |
| stop-09-flush | S_flush | FinalFlushInMayWrite | property | quint-verify | 12 |  | violated | violated | yes | 5.5 |
| stop-10-flush-ctl | S_flush_ctl | FinalFlushInMayWrite | control | quint-verify | 12 |  | holds | holds | yes | 5.6 |
| stop-11-budget-healthy | S_ok | PlaceBudgetGuaranteed | property | quint-verify | 4 |  | holds | holds | yes | 4.5 |
| stop-12-budget-stuck | S_age_stuck | PlaceBudgetGuaranteed | property | quint-verify | 4 |  | violated | violated | yes | 4.4 |
| stop-w1-done | S_ok | W_done | witness | quint-verify | 12 |  | violated | violated | yes | 5.4 |
| stop-w2-killed | S_hang | W_killed | witness | quint-verify | 12 |  | violated | violated | yes | 4.6 |
| stop-m1-slot-first | S_m_slotfirst | NoWriteAfterRelease | mutant | quint-verify | 12 |  | violated | violated | yes | 4.6 |
| stop-m1b-slot-first-order | S_m_slotfirst | PlaceBeforeSlot | mutant | quint-verify | 12 |  | violated | violated | yes | 4.9 |
| stop-m2-standin-noreread | S_m_standin | NoStandinWriteAfterRelease | mutant | quint-verify | 12 |  | violated | violated | yes | 6.0 |
| stop-c1-standin-reread | S_standin_reread_ctl | NoStandinWriteAfterRelease | control | quint-verify | 12 |  | holds | holds | yes | 4.5 |
| perf-01-one-per-group | P_ok | OnePerGroupOfHolder | property | quint-verify | 12 |  | holds | holds | yes | 27.3 |
| perf-01b-one-per-group-sim | P_ok | OnePerGroupOfHolder | property | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-02-takeover-wait | P_ok | TakeoverWaitHonored | property | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-02b-takeover-wait-verify | P_ok | TakeoverWaitHonored | property | quint-verify | 12 |  | holds | holds | yes | 26.4 |
| perf-03-order | P_ok | OrderInGroup | property | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-04-noearly-close-0skew | P_ok | NoEarlyForeignClose | control | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-05-early-close-skew | P_skew | NoEarlyForeignClose | property | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-06-noearly-expire-0 | P_ok | NoEarlyExpire | control | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-07-early-expire-filer | P_fskew | NoEarlyExpire | property | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-08-noself-close | P_ok | NoSelfForeignClose | property | quint-run-rust | 60 | 10000 | holds | holds | yes | 1.0 |
| perf-09-hung-blocks | P_hang_noexpire | HungDoesNotBlockForever | property | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-w1-overlap | P_ok | W_overlap | witness | quint-run-rust | 60 | 20000 | violated | violated | yes | 0.7 |
| perf-w2-late | P_ok | W_late | witness | quint-run-rust | 60 | 20000 | violated | violated | yes | 0.7 |
| perf-w3-second-expired-during-hang | P_hang | W_secondExpiredDuringHang | witness | quint-run-rust | 60 | 20000 | violated | violated | yes | 0.7 |
| perf-w4-begun | P_ok | W_begun | witness | quint-run-rust | 30 | 2000 | violated | violated | yes | 0.7 |
| perf-w5-unknown | P_ok | W_unknown | witness | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-w6-performed | P_ok | W_performed | witness | quint-run-rust | 30 | 2000 | violated | violated | yes | 0.7 |
| perf-w7-taken | P_ok | W_taken | witness | quint-run-rust | 10 | 500 | violated | violated | yes | 0.7 |
| perf-w8-foreign-close | P_ok | W_foreignClose | witness | quint-run-rust | 60 | 20000 | violated | violated | yes | 0.7 |
| perf-w9-expired | P_ok | W_expired | witness | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-m1-no-busy | P_m_busy | OnePerGroupOfHolder | mutant | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.7 |
| perf-m2-no-wait | P_m_wait | TakeoverWaitHonored | mutant | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |
| perf-m3-order | P_m_order | OrderInGroup | mutant | quint-run-rust | 40 | 5000 | violated | violated | yes | 0.7 |
| perf-m4-self-close | P_m_selfclose | NoSelfForeignClose | mutant | quint-run-rust | 60 | 10000 | violated | violated | yes | 0.7 |


Логи команд и трассы контрпримеров: `quint-p03-244355d1/runs/<id>.out`. Экземпляры с параметрами: `quint-p03-244355d1/inst/<name>.qnt`.

## 3. Мутанты и контроли

Мутанты аренды, остановки, действий и трасс форм (все 14 пойманы, см. таблицу, `kind=mutant`):

| Мутант | Изменение | Нарушаемый инвариант |
|---|---|---|
| `lease-m1-last-at-answer` | `last` по ответу, а не по посылке | `ActWithinWindowFromSend` |
| `lease-m2-slot-at-answer` | срок слота по ответу | `ActWithinSlotTerm` |
| `lease-m3-revive-fenced` | чужой номер не закрепляет `fenced` | `FencedStays` |
| `lease-m4-revive-oversleep` | проспанное окно не даёт `lost` | `MissedIsLost` |
| `stop-m1-slot-first`, `stop-m1b` | слот отдан до отпуска места | `NoWriteAfterRelease`, `PlaceBeforeSlot` |
| `stop-m2-standin-noreread` | заместитель не перечитывает строку после отдачи | `NoStandinWriteAfterRelease` |
| `perf-m1-no-busy` | нет проверки занятого вызова | `OnePerGroupOfHolder` |
| `perf-m2-no-wait` | нет ожидания нового держателя | `TakeoverWaitHonored` |
| `perf-m3-order` | нет порядка в группе | `OrderInGroup` |
| `perf-m4-self-close` | свой `begun` закрывается как чужой | `NoSelfForeignClose` |
| `forms-m1`, `m2`, `m3` | `since` сбрасывается, нет `name_back`, `persist` раньше принятия | трассы форм |

Контроли (kind=control, ожидание holds, факт см. таблицу) проверяют, что нарушение исчезает, когда снята причина, и что модель не нарушает инвариант по построению:

| Контроль | Что снято | Цель |
|---|---|---|
| `lease-02-stepsum-ctl`(-sim, -b) | сумма шагов укладывается в окно | причина `lease-01` — сумма шагов |
| `lease-04-hung-fix-ctl` | условие заместителя от последнего подтверждения (не норма) | причина `lease-03` — условие по шагу |
| `lease-07-slowN-ctl` | малая задержка ответов | причина `lease-05` — произведение `N × ответ` |
| `lease-09-silN-ctl` | `N=1` | причина `lease-08` — последовательное чтение при тишине |
| `lease-13-wallCad-ctl`, `lease-15-wallAge-ctl` | монотонные часы | причина `lease-12`, `lease-14` — стенные часы |
| `lease-17-zeno-ctl`(-b) | ненулевая пауза | причина `lease-16` — пауза 0 |
| `stop-07-budget-ctl` | объявленный бюджет шага (не норма) | причина `stop-05`, `stop-06` — отсутствие бюджета |
| `stop-10-flush-ctl` | короткие шаги | причина `stop-09` — окно истекает при остановке |
| `stop-c1-standin-reread` | перечитывание заместителя | норма защищает от записи после отдачи |
| `perf-04`, `perf-06` | нулевое смещение | причина `perf-05`, `perf-07` — расхождение часов |
| `forms-01-traces` | мутаций нет | соответствие форм трассам |

Свидетели невакуумности: `lease-w1`…`w14`, `stop-w1`, `w2`, `perf-w1`…`w9`, `forms-w1`, `w2`, `stop-08-budget-used` — состояния, которые инварианты контролируют, достижимы.

## 4. Что подтвердило, сняло, уточнило находки

Статус «подтверждена» значит: модель даёт достижимую последовательность, разрешённую текстом нормы при допущениях. Модель не меняет класс находки и не усиливает её.

### С5 — подтверждена, уточнена

- `lease-05`, `lease-06`: при 4 единицах и ответе хранилища в 5 с (параметр) единица в конце шага теряет окно без `silent` (`03.2:496-504`, `03.3:104`); заместитель не спасает (`lease-05` с заместителем, `lease-06` без). Контроль `lease-07` при ответе 1 с держится. Предел зависит от произведения числа чтений и задержки; норма этой связи не называет. Подтверждено.
- **Уточнение (новое наблюдение, следствие текста норм):** `lease-01` (симуляция и verify 18 шагов): без единого зависшего шага, при шагах 149 тиков (меньше `STALL`, 150), хранилище отвечает мгновенно, `N=1`, сумма шагов цикла между проверками шага 4 перекрывает окно. Шаг аренды идёт только на шаге 4 цикла (`03.3:104`), а условие заместителя — возраст одного текущего шага (`03.3:107`, `03.4:374`). Контроль `lease-02` (шаги не больше 33 тиков; verify 16 шагов, симуляция 5000 образцов) — нарушения нет. Находка С5 шире своей формулировки «O(N)»: ограничение суммы шагов между шагами аренды в норме не задано.
- `lease-03`: зависший шаг, начатый не раньше `W − STALL − WAKE_max` (6,25 с) после `last`, при `WAKE` на границе `03.4:169` приводит к `lost`: первое действие заместителя после `STALL` может прийти позже конца окна. Контроль `lease-04` (условие заместителя от последнего подтверждения, не норма) — нарушения нет. Граница `WAKE <= W/4` сама по себе от `lost` не защищает.

### С11 — уточнена

- `lease-08`: при тишине, `forever`, двух единицах и ожидании 5 с (параметр) вторая единица получает `lost` без потолка: её `t0` позже `last + W`, `silent` ещё не присвоен. Формулировка `03.2:592` («nothing is lost until the ceiling») верна только при условии, что `t0` каждой единицы укладывается в окно, то есть зависит от `wait × N`. Контроль `lease-09` (`N=1`) — нарушения нет. Находка С11 (проверки процесса нет) остаётся; модель уточняет, что сама формулировка условна. Просьба к Архитектору: либо назвать условие, либо связать его с конечным бюджетом шага (С5).
- `lease-10`, `lease-11`, свидетели `lease-w10`, `w11`, `w3`: `off` и конечный потолок дают `lost` только после окна/потолка; возврат после `silent` (`03.2:500`) достижим. Здесь нормы согласованы.

### С4 — подтверждена, уточнена

- `stop-05`, `stop-06`: зависший шаг до `stop_timeout` при 20 и 50 с завершается обрывом без отдачи слота и места (`03.4:421`). Контроль `stop-07` (бюджет шага, не норма) — слот отдаётся. Бюджет и переход к шагу 4 нормой не заданы.
- `stop-09`: шаг остановки единиц длиннее окна — сводка окон подавления `03.6:77` уходит на момент, когда `may_write` по окну уже закрыт. Контроль `stop-10` — без нарушения. Цена не отмечена нормой: при `off` сводка может потеряться. Это уточнение С4, не новый класс.
- `stop-11`/`stop-12`: `03.4:510` утверждает гарантированный запас ≥ `WRITE_WINDOW − RENEW_EVERY` (~31 с). Арифметика верна при давности последнего подтверждения ≤ `RENEW_EVERY`; при цикле, подпираемом заместителем, давность может быть 18,75 с (`STALL + WAKE_max`), запас ≈ 21,25 с. Здесь модель добавляет только арифметику; условие «цикл здоров» стоит назвать.
- Порядок шагов нормы держится: `stop-01`…`stop-04` holds; мутанты порядка пойманы.

### С10 — подтверждена

`perf-09`: зависший вызов занимает группу без ограничения. Это прямое следствие отсутствия в тексте перехода (тривиальное, нарушение показывает ровно это, глубины нет). `perf-w3`: второй запрос той же группы истекает, пока первый висит; норма разрешает. Решение владельца об одном вызове не затрагивается.

### С13 — подтверждена как зависимость от чтения нормы

`lease-12`: если каденция шага аренды читает стенные часы (норма `clock` не называет, `03.3:104`), скачок назад 30 с сдвигает шаг и даёт `lost`. `lease-14`: то же для возраста шага заместителя. Контроли `lease-13`, `lease-15` (монотонные) — нарушения нет. Обе реализации допустимы текстом; модель показывает цену стенного чтения. Числа скачка — параметр.

### С14 — подтверждена

`perf-05`: при расхождении часов держателей 15 с (параметр) `begun` закрыт чужим `unknown` раньше фактического `PERFORM_TIMEOUT + PERFORM_GRACE`. `perf-07`: `expired` по часам подающего раньше истинного срока. Контроли `perf-04`, `perf-06` при нулевом смещении — нарушения нет. `perf-w2`: поздний ответ заменяет `unknown` на `late` (`03.6:306`) — смягчает, но требует человеческого решения; не снимает находку.

### С15 — подтверждена

`lease-16` (verify): при паузе 0, мгновенном отказе соединения (`store-client:87`) шаги аренды идут многократно в одной точке времени: `again` «at once» (`03.2:46`). Контроль `lease-17` при паузе ≥ 1 тик: число шагов ограничено `1 + now/POLL`. Нижней границы у паузы норма не задаёт (`03.3:42`). Шторм нескольких воркеров не моделировался.

### Снято

Ни одна находка моделью не снята. Части, не подтверждённые и не опровергнутые моделью, перечислены ниже как не моделировавшиеся.

## 5. Не вошло

| Находка | Причина |
|---|---|
| С1 (адрес двери) | статическая: отсутствует тело нормы, времени и гонок нет |
| С2 (простой, медленный читатель, кадрирование) | статическая: нормы нет; без нормы модель нечего проверять |
| С3 (проба двери) | о наличии проверки, не о свойстве модели |
| С6 (стоимость прохода) | статическая: зависимость от R арифметическая; модель шага аренды измеряет сходную связь для `N` (С5) |
| С7 (RAM), С8 (дескрипторы), С9 (рост эпох) | ресурсные бюджеты, не гонки времени |
| С12 (сбой `append`) | статическая: отсутствует ветка исхода |
| М1–М3 | статические (файловый носитель, рост, проба) |
| М4 | о пробе `ambiguous`, а не о гонке; перепосылка с тем же `id` не моделировалась |
| М5 | «конец дня» токена: в форме день — вход, часы вне формы (`forms/README.md:120`); скачок дня не моделировался |
| Слот в гонке двух держателей и `cas`, потеря захвата | атомарность `cas` принята как контракт хранилища; частичный случай — `lease-w6` (`give_up_name`) и свидетель при потерянных записях `lease-w7` |
| Заместитель: блокировка слота `03.4:394`, ветка «дольше `FOR`» | неблокирующий замок не влияет на сроки в этой модели; ветка `FOR` (300 с) вне горизонта |
| Заказ строк и повторы `conflict` (`03.6:350`, `03.2:46` для заказа) | вне выбранных гонок, относятся к С15; отдельной модели нет |
| Кворум, лидер, `@cut` и прочие директивы приёмки | модель хранилища — одноканальная связь: ответ или `no_reply` |

## 6. Допущения и пределы

Верифицировано скриптом `quint-p03-244355d1/check_anchors.py` по байтам среза `244355d1`: 73 якоря, несовпадений 0.

1. Аренда. Подтверждения единиц в шаге — последовательно (одна нить цикла, `03.3:112`; параллельность норма не запрещает и не задаёт — С5). Шаги цикла в указанном порядке; пауза шага 6 — `POLL` (`03.3:42`). Заместитель читает единицы тем же порядком. Чтение — атомарно на момент ответа; `t0` — момент посылки. Значения `last`, `slotSend` в начальном состоянии равны 0 (единицы только что подтверждены); первый шаг в момент начала либо сразу (`INIT_DUE`, только для `L_zeno`).
2. Задержки, `POLL`, длительности шагов, величины скачка часов, смещения часов и `N` — параметры; норма их не задаёт либо передаёт реализации (`03.3:42`, `store-client:89`, `03.4:169` как граница). Значения 5 с, 1 с, 30 с, 15 с и подобные — входы для показа зависимости, а не утверждения о типичном значении. Константы норм: `LEASE_TTL`, `LEASE_MARGIN` (`runtime-constants.tsv:4,5`), `SLOT_TERM`, `HOLD_SKEW`, `FOR`, `PERFORM_TIMEOUT`, `PERFORM_GRACE` (`20,21`), `02.1:235`.
3. Остановка. `before_stop_all` и остановка единиц — одна фаза, разные единицы не различаются; `lastRenew` общий для окна и слота, потолок `off`; после `SIGKILL` записей нет (`03.4:421`). Сводка подавления — условие `may_write` окна, без потолка.
4. Действия. Одна группа, два держателя, два запроса; смещение часов постоянно, дрейф не моделируется; порядок запросов — старший раньше; `at` пишется держателем; передача эпохи атомарна, прежний держатель теряет допуск. Отказ `refused` и журнал событий не моделируются.
5. Формы. Перенесены вручную из YAML; согласованность проверена только тестами трасс форм и инвариантами форм. Строка `transitions` без `to` не завершает событие (`forms/README.md:125`) — это прочтение, подтверждается трассами.
6. Пределы инструментов. Симуляция (`quint run --backend=rust`) и `quint verify --max-steps=K` ограничены; результат «holds» значит «контрпример не найден в этих границах», не доказательство. Параметры границ — в `results.tsv`. Apalache запускался один процесс, `-Xmx4g`, порт вне 8822.
7. Результаты симуляции свидетелей зависят от случайного зерна (зерно каждого запуска — в `runs/*.out`); итоговый прогон выполнен один раз целиком и не отобран; повторные запуски свидетелей `lease-w1`, `w3`, `w10`, `w11` на других зёрнах могут не найти состояние при прежнем числе образцов.
8. Команда `rm` над пробными выводами в каталоге проекта была отклонена проверкой безопасности; выводы пробных запусков перемещены в scratchpad, обхода не делалось.
9. Экземпляр `L_any` (много событий) для `quint verify` оказался тяжёлым; первый запуск `verify` на нём с 14 шагами остановлен вручную (больше четырёх минут без результата) и заменён экземпляром `L_small` (`lease-20b`, `lease-25`). Это снижает охват `verify` для событий; симуляция на `L_any` оставлена.

Итог по срезу: модель не даёт вывода о готовности, о реализации и о кандидате; приёмочный смысл имеет только то, что перечислено как проверка текста норм в указанных границах.

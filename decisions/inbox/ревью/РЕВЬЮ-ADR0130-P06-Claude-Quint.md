adr: 0130 (P/06, Quint)

# Модель Quint боевых свойств P/06 — review103-claude

**Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется.**

- Срез: `862455715be8e155e0c80566d6f60d443a8b2650`. Фактический старт (`date -u`): 2026-11-08 20:32:58 UTC; окончание прогонов: 2026-11-08 23:10 UTC (последний — один добавленный свидетель; основная пачка закончилась в 22:13, повторы `claim_put`, `claim_post`, `ops_leader` — в 22:36 и 22:52).
- Источник вопросов — собственный замороженный отчёт, коммит `7a32915f`, находки С1–С16, М1–М5. Он не менялся и этой моделью не правится.
- Не читал: отчёты других рецензентов и Kimi, смысловой common-пакет, реализацию Source, кандидата 41, captures, runtime, частных судей, код вне реестра. SUT, native и кандидат не исполнялись; запускались только Quint/Apalache над своими моделями.
- Результат «нарушение» ниже — следствие текста нормы при названных допущениях, не дефект реализации. Модель не доказывает ни Source, ни кандидата. Результат «держится» — только в пределах указанной границы (ограниченная проверка или симуляция).
- Каталог проекта: `decisions/inbox/ревью/quint-p06-86245571/` (`*.qnt`, `run.py`, `results.tsv`, `run.log`, `runs/`, `anchors.tsv`, `check_anchors.py`, `trial-mismatches.tsv`). Инструменты: Quint 0.33.0, Apalache 0.62.1, симулятор rust.

**Итог прогона: 100 запусков** — 27 свойств (17 держатся, 10 нарушаются при тексте нормы), 33 свидетеля достижимости (все достижимы), 18 мутантов (17 пойманы, 1 нет — разбор ниже), 22 контроля (13 держатся, 9 ожидаемо нарушаются). Несовпадений ожидания с фактом в итоговой таблице — одно (`post-mut-no-guard`), оно оставлено и объяснено. Сводка находок: С13, С7, С15 подтверждены и уточнены; С6 уточнена, одна её часть снята; С5, С2, С12 сужены до того, что модель может проверить; остальные — не модель, причины ниже.

Сокращения те же, что в независимом отчёте: `06.N` — `Platform/06-console/spec/06.N-console.norms.md`; `life` — `lifecycle.md`; `const` — `forms/runtime-constants.tsv`; `gate` — `common/contracts/gate-and-pass.md`; `turn` — `common/contracts/turn.md`; `mark` — `common/contracts/request-mark.md`. Якоря проверены скриптом `check_anchors.py` по байтам среза: 79 строк `anchors.tsv`, расхождений 0.

## Что смоделировано

Восемь модулей, каждый на свой вопрос. Числа `CLAIM_TAKEOVER_AFTER`, `DONE_ANSWER_KEEP`, `OPS_RUN_MAX`, `OPS_KEEP`, `OPS_TICK`, `OPS_STEP_WAIT`, `OPS_STEP_TRIES`, `CHANGES_HISTORY` — из `const:32`, `const:33`, `const:23`, `const:24`, `const:22`, `const:20`, `const:21`, `const:6`. Скачок часов, длительность перечитывания и темп изменений — параметры противника и среды, не нормы и не утверждение о реальной системе.

Каждое «свойство» ограничивает завершённое действие: призрачная переменная записывается в момент действия (`falseSuccess`, `cancelAge`, `reapAge`, `staleLanded`, `silentSkip`), поэтому правда простаивающего состояния не может сделать свойство истинным вхолостую. Состояние-граница используется только там, где оно и есть утверждение: `runBounded` (незавершённая операция) и `removedInBound` (ещё лежащая строка claim).

### `claim_put.qnt` — продолжение PUT после перехвата

Вопрос: С6, С5 (судьба claim при SIGTERM). Граница: одна строка, ключ K, процессы A и B, один посторонний писатель C с другим ключом, ≤ 1 его правка, шаги 12–14. Шаги: claim, чтение, намерение 5a (`06.1:830`), запись `cas` + guard (`06.1:831`), неизвестный исход (`06.1:783`), перехват после `CLAIM_TAKEOVER_AFTER`, сначала взгляд на цель (`06.1:714`), ответ.

- `noFalseSuccess` — ответ `done` только если тело этого ключа действительно записывалось. **Нарушается** за 9 шагов: A сделал 5a, не успел записать (падение, SIGTERM или неизвестный исход без записи), C поднял ту же строку до намеченной ревизии, B перехватил и по правилу `06.1:714` принял её за свою.
- `atMostOneLand` — запись ключа не более одного раза. **Нарушается** при посторонней правке между записью и перехватом: ревизия уже другая, B идёт процедурой заново. Без постороннего писателя держится.

Допущения: C — обычная запись по `cas`; `born` при правке не меняется (`06.1:831`). Не моделировалось: `If-Match`, ссылки (шаги 4, 5), запись таблицы (`06.1:715`, там проверка только по ревизии, без `born` — текстом слабее, но отдельно не проверялось), точные байты ответа.

### `claim_post.qnt` — POST

Вопрос: С6. Граница: ключ K, процессы A и B, посторонний создатель C, шаги 14. Свойства `atMostOneLand`, `noFalseSuccess`, `noFalse409`, `doneMatches` держатся. Сюда же перехват с намерением (`06.1:713`, `06.1:763`) и исключение шага 5 (`06.1:754`). Не моделировалось: числовые id и `next_id`, надгробия, ответы 409/422 на повтор.

### `claim_retention.qnt` — срок claim

Вопрос: С7. Граница: один done-claim, две консоли, ≤ 2 перезапуска, шаг времени 3600 с (параметр), шаги 8–12. Допущения: уборка — разрешённое реализации действие (`06.1:1136`) и срабатывает, как только разрешена; возраст — от первого наблюдения (`06.1:182`, `06.1:183`), перезапуск его теряет.

- `removedNotEarly` (удаление не раньше `DONE_ANSWER_KEEP`) держится при перезапусках.
- `removedInBound` (удалено не позже `KEEP` + запас) **нарушается**, когда все консоли перезапускаются чаще суток: первое наблюдение каждый раз новое. Перезапуск всех консолей — обычный шаг смены манифеста (`life:65`). Запас `2·DT` — модельный, не норма.

Не моделировалось: pending. Нормы очистки pending нет (`06.1:772`), поэтому и в модели такого действия нет: это отсутствие действия, а не результат проверки, свойством не утверждается.

### `ops_clock.qnt` — стенные часы операций

Вопрос: С13. Граница: одна операция из 2 шагов, лидер и уборщик, ≤ 1 скачок (`JUMPS`, параметр), шаги 8–12. Допущение A1: лидер ходит каждые `OPS_TICK`, уборщик — как только условие выполнено (`06.9:395`); потерянные и запоздавшие такты не проверяются. Время движется с шагом, не перепрыгивающим срок больше чем на такт.

- `cancelNotEarly` (отмена по сроку не раньше истинного возраста `OPS_RUN_MAX`) **нарушается** скачком вперёд (`06.9:405`).
- `stepNotClockCancelled` (шаг не получает `cancel` от одного скачка) **нарушается**, это прямая проверка фразы `06.9:28` «ни шаг, ни право от этого не зависят»: шаги получают исход `cancel` через `finish` (`06.9:440`) и при истинном возрасте 0.
- `reapNotEarly` (`06.9:494`) **нарушается** скачком вперёд уборщика.
- `runBounded` **нарушается** скачком назад: незавершённая операция держит корни дольше `OPS_RUN_MAX` по истинному времени.
- Контроль без скачков — все держатся. Контроль с монотонным счётом (`MONO`, предложение С13, не норма) — держатся.

Не моделировалось: `exp`/токены, пауза, перепривязка, исходы `fail`, `opbusy`, транспорт вызова шага. Что именно ломает ранний reap (повтор, `retry`), не проверялось — только срок удаления.

### `ops_leader.qnt` — передача лидера, поздний батч, SIGTERM

Вопрос: С5 (очередь), С6 (шаг операции). Граница: одна операция с одним шагом, лидеры L1, L2, ≤ 8 внешних событий, Apalache 16 шагов (`noStaleLanding` — 12: при 16 шагах прогон занял 27 минут), симуляция 3000 трасс по 40 шагов. Допущение: истечение турна абстрагировано (`steal` разрешён в любой момент) — завышение; безопасность здесь держится на cas и guard, а не на сроке аренды. SIGTERM — в две фазы (`life:92`, `06.9:397`): сдача турна, затем выход; билет живёт только в памяти процесса (`06.9:541`).

Свойства держатся: `outcomeOnce`, `okOnce`, `doneHasOutcome`, `outcomeOkIsBatch`, `noStaleLanding` (батч с билетом старше перезаписи эпохи не садится, `06.9:320`, `06.9:399`, `06.9:508`). Свидетели передачи при SIGTERM (держатель турна сдаёт его при шаге без исхода, завершает другой лидер, `handedOver`): `lead-w-second-call` — другой лидер сам делает вызов и получает `ok`; `lead-w-sigterm-handover` — исход `ok` садится батчем ещё не вышедшего процесса до перезаписи эпохи, другой лидер только завершает. Трассы, где вызывали оба лидера и садится второй, отдельно не требовалось. Ещё: путь `fail not_run` (`06.9:424`), отмена.

Наблюдение: «один исход» держится и без generation guard (`lead-c-allsafe-nogen`) — на `cas ""` исхода (`06.9:451` сам называет оба слоя). Guard даёт отдельное свойство: поздний билет не садится после перезаписи эпохи. Это слой защиты, не дефект; о внешнем эффекте воркера (`turn:98`) модель не говорит.

Не моделировалось: несколько шагов и корней, целевые строки подсистемы, сам срок аренды и задержка подхвата.

### `feed.qnt` — сброс ленты

Вопрос: С15. Счётчиковая модель на настоящем числе `CHANGES_HISTORY` = 256, N = 2 клиента, ≤ 8 тактов, шаги 6–14. Допущения: клиент берёт позицию до чтения (`06.1:549`) и спрашивает `after` после него; чтение длится D тактов (параметр среды). B (внимательный клиент): такт идёт, только если клиент читает до срока или догнал конец истории; это благоприятный случай, нарушение при нём — чистый результат темпа.

- `noSilentSkip` держится (`06.1:553`, `06.1:555`): вытесненное даёт сброс, а не дыру.
- `noResetLoop` (не более одного сброса подряд) **нарушается** при устойчивом темпе, где `RATE·D > CHANGES_HISTORY`: 257 в такт при D = 1 и 129 при D = 2.
- Контроли на границе `RATE·D ≤ 256` (256 при D = 1, 128 при D = 2) и одна вспышка без перезапусков — держатся.
- `noStorm` **нарушается**: все клиенты получают сброс в одном такте вспышки (свидетель синхронного перечитывания).

Не моделировалось: фильтры прав и сбросы 3–5, долгий опрос `wait`, `Retry-After`, стоимость самого чтения.

### `lanes.qnt` — лейны

Вопрос: С2. Счётчики, `L_COMMON`, `L_CB` — значения реализации, нормативного числа нет (`06.5:824`); взяты малые, утверждение структурное. Шаги 8.

- `noDeadlock` и `callbackEverAdmissible` держатся: проход ждёт обратного вызова на отдельном лейне (`06.5:255`). Контроль: при `L_CB < L_COMMON` проверка падает — условие `06.5:824` нужно.
- Свидетель: застывшие читатели занимают общий лейн и операторские двери получают отказ. В модели нет действия освобождения, потому что нормы простоя нет (`gate:596`, условия закрытия `gate:614`): это структура и отсутствие действия, а не вывод о времени. Сроки, в том числе `PASS_WAIT_MAX` (`gate:645`), не моделировались.

### `reseal.qnt` — повторное запечатывание

Вопрос: С12. Граница: одна строка, две консоли, ≤ 1 правка оператора, шаги до 10. `noEditLost` держится (`cas` по прочитанному, `06.2:215`). Не моделировалось: сбой листинга и срок прохода, связь завершения прохода с готовностью (`life:91`, порядок старта `life:27`) — их нет в норме, модель не решает ни одну из ветвей.

## Таблица прогонов

Значения «violated» у свидетелей значит «достижимо»; у контролей с `c_false` — инструмент сообщает о заведомо ложном инварианте. Apalache — ограниченная проверка по числу шагов, при `hold` гарантия только в этой границе.

| id | Модуль | Инвариант | Вид | Шаги/выборки | Переопределения | Ожидание | Факт | Совпало | с |
|---|---|---|---|---|---|---|---|---|---|
| `put-false-success` | claim_put | `noFalseSuccess` | property | 12 | — | violated | violated | yes | 12.1 |
| `put-at-most-once` | claim_put | `atMostOneLand` | property | 14 | — | violated | violated | yes | 44.2 |
| `put-false-success-noforeign` | claim_put | `noFalseSuccess` | control | 14 | FOREIGN_MAX=0 | hold | hold | yes | 133.9 |
| `put-at-most-once-noforeign` | claim_put | `atMostOneLand` | control | 14 | FOREIGN_MAX=0 | hold | hold | yes | 129.2 |
| `put-repair-content` | claim_put | `noFalseSuccess` | control | 14 | REPAIR=true | hold | hold | yes | 88.9 |
| `put-w-done` | claim_put | `w_done_after_unknown` | witness | 14 | — | violated | violated | yes | 10.3 |
| `put-w-takeover` | claim_put | `w_takeover_reached` | witness | 8 | — | violated | violated | yes | 5.4 |
| `put-w-foreign` | claim_put | `w_foreign_seen` | witness | 14 | — | violated | violated | yes | 2.1 |
| `put-w-crash` | claim_put | `w_done_after_crash` | witness | 14 | FOREIGN_MAX=0 | violated | violated | yes | 20.9 |
| `put-w-land` | claim_put | `w_land` | witness | 6 | — | violated | violated | yes | 1.4 |
| `put-c-false` | claim_put | `c_false` | control | 2 | — | violated | violated | yes | 4.7 |
| `put-mut-no-guard` | claim_put | `atMostOneLand` | mutant | 14 | FOREIGN_MAX=0;MUT="no_guard" | violated | violated | yes | 21.3 |
| `put-mut-no-intent` | claim_put | `atMostOneLand` | mutant | 14 | FOREIGN_MAX=0;MUT="no_intent" | violated | violated | yes | 17.0 |
| `put-mut-blind` | claim_put | `atMostOneLand` | mutant | 14 | FOREIGN_MAX=0;MUT="takeover_blind" | violated | violated | yes | 18.2 |
| `post-w-cont` | claim_post | `w_done_cont` | witness | 12 | — | violated | violated | yes | 15.6 |
| `post-w-409` | claim_post | `w_409_foreign` | witness | 8 | — | violated | violated | yes | 6.4 |
| `post-w-ok` | claim_post | `w_done_ok` | witness | 8 | — | violated | violated | yes | 6.2 |
| `post-w-foreign` | claim_post | `w_foreign_row` | witness | 3 | — | violated | violated | yes | 5.3 |
| `post-w-takeover` | claim_post | `w_takeover` | witness | 8 | — | violated | violated | yes | 6.0 |
| `post-w-crash` | claim_post | `w_done_after_crash` | witness | 14 | — | violated | violated | yes | 26.7 |
| `post-c-false` | claim_post | `c_false` | control | 2 | — | violated | violated | yes | 6.1 |
| `post-mut-no-intent` | claim_post | `noFalse409` | mutant | 14 | MUT="no_intent" | violated | violated | yes | 24.9 |
| `post-mut-fresh-born` | claim_post | `noFalse409` | mutant | 14 | MUT="fresh_born" | violated | violated | yes | 37.4 |
| `post-mut-rev-only` | claim_post | `noFalseSuccess` | mutant | 14 | MUT="rev_only" | violated | violated | yes | 16.5 |
| `post-mut-no-guard` | claim_post | `atMostOneLand` | mutant | 14 | MUT="no_guard" | violated | hold | no | 91.4 |
| `post-mut-no-proof` | claim_post | `noFalse409` | mutant | 14 | MUT="no_proof" | violated | violated | yes | 35.4 |
| `ret-min` | claim_retention | `removedNotEarly` | property | 10 | — | hold | hold | yes | 5.4 |
| `ret-bound-restarts` | claim_retention | `removedInBound` | property | 12 | — | violated | violated | yes | 4.8 |
| `ret-bound-norestart` | claim_retention | `removedInBound` | control | 12 | MAX_RESTARTS=0 | hold | hold | yes | 5.9 |
| `ret-w-removed` | claim_retention | `w_removed` | witness | 8 | MAX_RESTARTS=0 | violated | violated | yes | 4.4 |
| `ret-w-restart` | claim_retention | `w_restart_used` | witness | 8 | — | violated | violated | yes | 4.3 |
| `ret-mut-wall` | claim_retention | `removedNotEarly` | mutant | 10 | MUT="wall_age";WALL_JUMP=86400 | violated | violated | yes | 4.3 |
| `ret-c-false` | claim_retention | `c_false` | control | 2 | — | violated | violated | yes | 4.1 |
| `clk-cancel-early-fwd` | ops_clock | `cancelNotEarly` | property | 8 | JUMPS=Set(86405) | violated | violated | yes | 4.9 |
| `clk-step-depends-fwd` | ops_clock | `stepNotClockCancelled` | property | 8 | JUMPS=Set(86405) | violated | violated | yes | 4.9 |
| `clk-reap-early-fwd` | ops_clock | `reapNotEarly` | property | 10 | JUMPS=Set(86405);MAX_JUMPS=1 | violated | violated | yes | 5.2 |
| `clk-run-bounded-back` | ops_clock | `runBounded` | property | 12 | JUMPS=Set(-86400) | violated | violated | yes | 4.9 |
| `clk-cancel-early-nojump` | ops_clock | `cancelNotEarly` | control | 12 | MAX_JUMPS=0 | hold | hold | yes | 7.0 |
| `clk-reap-early-nojump` | ops_clock | `reapNotEarly` | control | 12 | MAX_JUMPS=0 | hold | hold | yes | 7.0 |
| `clk-run-bounded-nojump` | ops_clock | `runBounded` | control | 12 | MAX_JUMPS=0 | hold | hold | yes | 7.0 |
| `clk-mono-early-fwd` | ops_clock | `cancelNotEarly` | control | 12 | JUMPS=Set(86405);MONO=true | hold | hold | yes | 8.5 |
| `clk-mono-reap-fwd` | ops_clock | `reapNotEarly` | control | 12 | JUMPS=Set(86405);MONO=true | hold | hold | yes | 8.6 |
| `clk-mut-run-ge0` | ops_clock | `cancelNotEarly` | mutant | 8 | MAX_JUMPS=0;MUT="run_ge0" | violated | violated | yes | 4.8 |
| `clk-mut-reap-nokeep` | ops_clock | `reapNotEarly` | mutant | 10 | MAX_JUMPS=0;MUT="reap_nokeep" | violated | violated | yes | 5.0 |
| `clk-w-cancel` | ops_clock | `w_cancel_by_time` | witness | 10 | MAX_JUMPS=0 | violated | violated | yes | 5.0 |
| `clk-w-reap` | ops_clock | `w_reap` | witness | 12 | MAX_JUMPS=0 | violated | violated | yes | 5.1 |
| `clk-w-ok-step` | ops_clock | `w_ok_step` | witness | 6 | MAX_JUMPS=0 | violated | violated | yes | 4.9 |
| `clk-w-early` | ops_clock | `w_early_cancel` | witness | 6 | JUMPS=Set(86405) | violated | violated | yes | 5.0 |
| `clk-w-steps` | ops_clock | `w_steps_cancelled` | witness | 8 | JUMPS=Set(86405) | violated | violated | yes | 4.9 |
| `clk-c-false` | ops_clock | `c_false` | control | 2 | — | violated | violated | yes | 5.8 |
| `lead-w-done-ok` | ops_leader | `w_done_ok` | witness | 10 | — | violated | violated | yes | 3.3 |
| `lead-w-sigterm-handover` | ops_leader | `w_after_sigterm_handover` | witness | 16 | — | violated | violated | yes | 13.4 |
| `lead-w-second-call` | ops_leader | `w_handover_by_second_call` | witness | 16 | — | violated | violated | yes | 7.1 |
| `lead-w-sigterm-done` | ops_leader | `w_sigterm_then_done` | witness | 14 | — | violated | violated | yes | 7.3 |
| `lead-w-two-calls` | ops_leader | `w_two_calls` | witness | 16 | — | violated | violated | yes | 4.1 |
| `lead-w-cancel` | ops_leader | `w_cancel` | witness | 8 | — | violated | violated | yes | 6.6 |
| `lead-w-fail` | ops_leader | `w_fail` | witness | 14 | — | violated | violated | yes | 32.9 |
| `lead-w-handover-gen` | ops_leader | `w_handover_gen` | witness | 14 | — | violated | violated | yes | 8.4 |
| `lead-c-false` | ops_leader | `c_false` | control | 2 | — | violated | violated | yes | 5.9 |
| `lead-sim-allSafe` | ops_leader | `allSafe` | property | 40/3000 | — | hold | hold | yes | 0.9 |
| `lead-mut-no-cas` | ops_leader | `outcomeOnce` | mutant | 16 | MUT="no_outcome_cas" | violated | violated | yes | 9.6 |
| `lead-mut-finish-nocas` | ops_leader | `outcomeOnce` | mutant | 16 | MUT="finish_no_cancel_cas" | violated | violated | yes | 7.1 |
| `lead-noStaleLanding` | ops_leader | `noStaleLanding` | property | 12 | — | hold | hold | yes | 170.0 |
| `lead-sim-noStale` | ops_leader | `noStaleLanding` | property | 40/3000 | — | hold | hold | yes | 0.9 |
| `lead-c-allsafe-nogen` | ops_leader | `allSafe` | control | 16 | MUT="no_gen_guard" | hold | hold | yes | 144.8 |
| `lead-mut-no-gen` | ops_leader | `noStaleLanding` | mutant | 16 | MUT="no_gen_guard" | violated | violated | yes | 8.1 |
| `lead-mut-no-bump` | ops_leader | `noStaleLanding` | mutant | 16 | MUT="no_bump" | violated | violated | yes | 7.9 |
| `feed-noskip` | feed | `noSilentSkip` | property | 12 | MODE="burst" | hold | hold | yes | 7.6 |
| `feed-known` | feed | `knownSound` | property | 12 | — | hold | hold | yes | 15.7 |
| `feed-loop-rate257` | feed | `noResetLoop` | property | 14 | D=1;RATE=257 | violated | violated | yes | 5.6 |
| `feed-loop-rate129-d2` | feed | `noResetLoop` | property | 14 | D=2;RATE=129 | violated | violated | yes | 6.1 |
| `feed-loop-ok-rate128-d2` | feed | `noResetLoop` | control | 14 | D=2;RATE=128 | hold | hold | yes | 6.3 |
| `feed-loop-ok-rate256-d1` | feed | `noResetLoop` | control | 14 | D=1;RATE=256 | hold | hold | yes | 6.4 |
| `feed-loop-ok-burst` | feed | `noResetLoop` | control | 14 | BURST=257;MODE="burst";RESTARTS_MAX=0 | hold | hold | yes | 17.2 |
| `feed-storm-burst` | feed | `noStorm` | property | 8 | BURST=257;MODE="burst" | violated | violated | yes | 5.0 |
| `feed-w-reset` | feed | `w_reset` | witness | 6 | MODE="burst" | violated | violated | yes | 4.9 |
| `feed-w-delivered` | feed | `w_delivered` | witness | 6 | RATE=1 | violated | violated | yes | 4.8 |
| `feed-w-allread` | feed | `w_all_read` | witness | 8 | MODE="burst" | violated | violated | yes | 5.0 |
| `feed-mut-no-reset` | feed | `noSilentSkip` | mutant | 10 | MODE="burst";MUT="no_reset" | violated | violated | yes | 4.8 |
| `feed-c-false` | feed | `c_false` | control | 2 | — | violated | violated | yes | 4.6 |
| `lane-deadlock` | lanes | `noDeadlock` | property | 8 | — | hold | hold | yes | 4.3 |
| `lane-callback` | lanes | `callbackEverAdmissible` | property | 8 | — | hold | hold | yes | 4.2 |
| `lane-mut-common` | lanes | `noDeadlock` | mutant | 8 | MUT="callback_on_common" | violated | violated | yes | 4.0 |
| `lane-c-cb-small` | lanes | `callbackEverAdmissible` | control | 8 | L_CB=1;L_COMMON=2 | violated | violated | yes | 5.1 |
| `lane-w-common-full` | lanes | `w_common_full_stalled` | witness | 6 | — | violated | violated | yes | 4.0 |
| `lane-w-pass` | lanes | `w_pass_ok` | witness | 4 | — | violated | violated | yes | 4.1 |
| `lane-c-false` | lanes | `c_false` | control | 2 | — | violated | violated | yes | 3.9 |
| `reseal-noedit-lost` | reseal | `noEditLost` | property | 10 | — | hold | hold | yes | 5.0 |
| `reseal-w-done` | reseal | `w_done` | witness | 8 | — | violated | violated | yes | 4.4 |
| `reseal-w-edit` | reseal | `w_edit_and_seal` | witness | 8 | — | violated | violated | yes | 4.4 |
| `reseal-mut-no-cas` | reseal | `noEditLost` | mutant | 8 | MUT="no_cas" | violated | violated | yes | 4.3 |
| `reseal-c-false` | reseal | `c_false` | control | 2 | — | violated | violated | yes | 4.2 |
| `lead-doneHasOutcome` | ops_leader | `doneHasOutcome` | property | 16 | — | hold | hold | yes | 152.0 |
| `lead-okOnce` | ops_leader | `okOnce` | property | 16 | — | hold | hold | yes | 164.5 |
| `lead-outcomeOkIsBatch` | ops_leader | `outcomeOkIsBatch` | property | 16 | — | hold | hold | yes | 165.9 |
| `lead-outcomeOnce` | ops_leader | `outcomeOnce` | property | 16 | — | hold | hold | yes | 177.4 |
| `post-atMostOneLand` | claim_post | `atMostOneLand` | property | 14 | — | hold | hold | yes | 110.3 |
| `post-doneMatches` | claim_post | `doneMatches` | property | 14 | — | hold | hold | yes | 106.9 |
| `post-noFalse409` | claim_post | `noFalse409` | property | 14 | — | hold | hold | yes | 200.5 |
| `post-noFalseSuccess` | claim_post | `noFalseSuccess` | property | 14 | — | hold | hold | yes | 102.7 |

## Мутанты и контроли

**Мутанты: 18, поймано 17.** Единственный непойманный — `post-mut-no-guard` (POST без guard claim): строка оставлена, ожидание было «нарушается», факт «держится». Причина: у POST цель пишется `cas ""`, намерение при перехвате сохраняется, значит поздняя запись A либо конфликтует, либо равна той же строке; guard здесь в данной абстракции лишний. Для PUT, где `cas` идёт по прочитанной версии, тот же мутант пойман (`put-mut-no-guard`), то есть guard не лишний вообще. Это наблюдение об ограниченной модели POST (без надгробий и удалений, без `next_id`), а не утверждение, что нормативный guard можно убрать.

Остальные: `put-mut-no-intent` и `put-mut-blind` (двойная запись без намерения и без взгляда на цель), `post-mut-no-intent`, `post-mut-fresh-born`, `post-mut-rev-only`, `post-mut-no-proof` (неверные доказательства своей строки), `ret-mut-wall` (уборка по стенному возрасту), `clk-mut-run-ge0`, `clk-mut-reap-nokeep` (мутанты сроков при отсутствии скачка показывают, что свойства не пустые), `lead-mut-no-cas`, `lead-mut-finish-nocas`, `lead-mut-no-gen`, `lead-mut-no-bump`, `feed-mut-no-reset`, `lane-mut-common`, `reseal-mut-no-cas`.

**Контроли: 22.** Восемь с ложным инвариантом (`*-c-false`) — инструмент сообщает нарушение на этой форме; условия, снимающие причину (без постороннего писателя, без скачков, без перезапусков, монотонный счёт, доказательство содержимым как проверка исправления, граничный темп ленты); `lane-c-cb-small` — ожидаемое нарушение при `L_CB < L_COMMON`; `lead-c-allsafe-nogen` — свойство, не зависящее от guard.

**Пробные расхождения** — `trial-mismatches.tsv`, 8 строк с причинами: два сбоя соединения с сервером; мутант `no_look_first` не менял поведения (шаг 5 тоже доказывает свою строку) и заменён на `no_proof`; `allSafe` не различала guard, добавлено отдельное свойство; у мутанта `no_bump` своя ошибка; у ленты не было внимательности клиента; один `deadlock` Apalache считался как нарушение (`run.py` теперь различает, добавлен шаг простоя; других таких случаев в пробных выводах не было).

После окончательного прогона в `*.qnt` правились только комментарии-якоря (сверка с `runs/*.qnt` без комментариев: 0 расхождений). Строки `results.tsv` писались двумя параллельными процессами; порядок и единственный заголовок восстановлены после прогона (100 строк). Один запуск (`post-noFalseSuccess`) упал на сбое соединения с сервером Apalache (`run.log`), запись с `error` удалена и он повторён; в таблице результат повтора.

## Что подтвердило, сняло и уточнило находки

| Находка | Вывод модели | Запуски |
|---|---|---|
| **С13** — подтверждена, уточнена | Скачок вперёд отменяет принятую операцию при истинном возрасте 0 и удаляет завершённую раньше `OPS_KEEP` (`06.9:405`, `06.9:494`); фраза `06.9:28` ограничена: исход шага зависит от часов. Новое по сравнению с находкой: скачок **назад** отодвигает отмену и держит корни дольше `OPS_RUN_MAX`. Монотонный счёт снимает всё это в модели; это контроль исправления, не решение. | `clk-*` |
| **С5** — сужена | Судьба принятой работы при SIGTERM в модели подтверждается: лидер, державший турн, получает SIGTERM при шаге без исхода и сдаёт турн, другой лидер завершает операцию, исход один (`ops_leader`; свидетели `lead-w-sigterm-*`, `lead-w-second-call` требуют именно передачи — призрак `handedOver`: завершает другой процесс, не тот, что сдал турн). Для claim: после потери исполнителя при pending claim повтор сходится к ответу — `put-w-crash` показывает порядок потеря → перехват → ответ, `post-w-crash` — ответ 201 при потере исполнителя (в найденной трассе потеря случилась уже после перехвата); для claim падение и SIGTERM по `life:92` неразличимы. Остальная часть С5 — **срок остановки, отмена внешних ожиданий, освобождение ресурсов — не моделировалась**: это отсутствие входа, а не гонка. Находка в этой части без изменений. | `lead-*`, `put-w-*`, `post-w-cont` |
| **С6** — уточнена, часть снята | Сверх пробной находки: при PUT **текст нормы даёт ложный успех** — `06.1:714` принимает чужую правку на намеченной ревизии за свою. Для POST это исключено прямо (`06.1:719`) и подтверждено; для PUT и, судя по `06.1:715`, таблиц — нет; норма сама оставляет «свои правила подтверждения» другим дверям. Снята часть про лишнюю ревизию при простом повторе: без постороннего писателя запись одна (`put-at-most-once-noforeign`); лишняя ревизия требует чужой правки между записью и перехватом. «Ложный 412» не моделировался. Неизвестный исход шага операции держится (`lead-*`). Сам класс находки о пробе остаётся. | `put-*`, `post-*`, `lead-*` |
| **С7** — подтверждена, уточнена | Нижняя граница 24 ч держится даже при перезапусках; верхней нет: перезапуски всех консолей чаще суток откладывают уборку бессрочно даже у реализации, которая убирает. Механизм — `06.1:183`. Pending не проверялся (нет действия). | `ret-*` |
| **С15** — подтверждена, уточнена | Сброс безопасен (`noSilentSkip`), шторм реален в смысле одновременности. Новое: кроме вспышки есть устойчивый режим — при `RATE·D > CHANGES_HISTORY` клиент не выходит из цикла «сброс — перечитать — сброс» даже при внимательном опросе, граница проверена контролями. Норма не задаёт D, поэтому это условие, а не число. | `feed-*` |
| **С2** — сужена | Отдельный лейн обратных вызовов и условие `06.5:824` снимают взаимоблокировку проходов — в модели держится и условие необходимо. Занятие лейна застывшими — только структура; утверждение о сроке моделью не даётся, находка как недостающий вход остаётся. | `lane-*` |
| **С12** — без изменения | Гонка по `cas` чиста (`noEditLost`). Сбой листинга, срок и связь с готовностью в норме не описаны и не моделировались. | `reseal-*` |

Снятых целиком находок нет. Сняты: «лишняя ревизия при простом повторе» из С6 (в случае без посторонней записи). Новых находок сверх названных уточнений модель не добавляет; вывод о PUT относится к С6 и записан здесь как следствие текста при допущениях, а не как решение Архитектора или владельца.

## Не вошло

- **С1, С3, С4, С14** — находки о пробе и об отсутствующих сроках и шагах: гонки нет, проверить можно только исполнением на стенде.
- **С8, С9, С10, С11, С16, М1** — бюджеты, стоимость и единицы; это статика, модель на абстрактных числах ничего не добавила бы, а новых чисел брать нельзя.
- **М2** — арифметика одного абзаца (`n−1` при `n` параллельных), отдельная модель не нужна; остаётся как в отчёте. **М3, М4, М5** — вес тела, старт на занятом порту, стенд двух ресурсов: вне гонок и времени.
- Срок остановки, отмена и освобождение (С5), срок прохода и связь с готовностью (С12): нормы нет, моделировать нечего.

## Допущения и пределы

1. Все «держится» — ограниченная проверка: шаги, число процессов, число событий указаны в таблице и в описании модулей. Это не доказательство для произвольного числа консолей, строк и шагов.
2. Симуляция (`quint run`) — статистическая проверка, её результат не утверждение о всех трассах.
3. Параметры противника и среды (`JUMPS`, `D`, `RATE`, число событий, шаг времени в `claim_retention`, запас `removedInBound`) выбраны моделью и не являются нормой, как и малые значения `L_COMMON`, `L_CB`.
4. Модели абстрагируют: одна строка или операция, ограниченный состав процессов, крах и SIGTERM для claim совпадают, истечение турна завышено до «в любой момент», время ходит крупным шагом при условии, что срок не перепрыгивается больше чем на такт.
5. `born` модели — абстрактный уникальный идентификатор (случайность и столкновения не моделируются).
6. Модель связана с нормой только прочтением автора: связи с реализацией нет, вывод о Source и кандидате не делается.
7. Вывод о PUT зависит от прочтения `06.1:714` как достаточного условия при совпадении ревизии и `born`; иное прочтение нормы (например, неявная сверка содержимого) сняло бы этот вывод, в тексте такого условия нет.
8. В итоговой таблице перечислены все запуски окончательного прогона; единственное несовпадение объяснено выше, ни один запуск окончательного прогона не прерывался. Первая пробная пачка прервана вручную (её результаты в таблицу не входят); модули `claim_put`, `claim_post` прогнаны заново после добавления призрачной переменной `crashed`, `ops_leader` — дважды (`giveUps`, затем `handedOver`: первая редакция свидетеля SIGTERM оказалась слабой, его выполняла трасса, где лидер получал SIGTERM уже после завершения, операция на другого лидера не переходила). Последним добавлен `lead-w-second-call`: в `ops_leader.qnt` это одна новая строка-определение (`val`), состояние и действия те же (сверка с `runs/*.qnt`: различие только в этой строке), остальные запуски `ops_leader` не повторялись. Отметки «rerun» — в `run.log`, прежние выводы перенесены в черновой каталог.

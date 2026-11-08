adr: 0130 (P/05, Quint)

# Модель Quint P/05 (ресурс): гонки и время — review103-claude

Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется. Срез норм: `d21ed721d0c5690cbbf151a77d0fe2f366b34215`. Вход подтверждён count-only: `/home/pilot/coord103-src/adr0083-144-tools-handoff-20261108/background-p05-paired-intake-20261108/P05-INDEPENDENT-SUBMISSIONS-COMPLETE-COUNT-ONLY.json`, sha256 `91ab3cbbd9bf2d6d56eabe7071f14389934f99cac47aa4d1651157bc35b4f26e`. Фактический старт: 2026-11-08 19:45 UTC (`date -u`); итоговый прогон завершён 2026-11-08 20:30 UTC. Источник вопросов — мой отчёт `decisions/inbox/ревью/РЕВЬЮ-ADR0130-P05-Claude.md` (коммит `26d8c6a9`, находки С/М).

Прочитаны только нормы и формы среза и мой отчёт. Отчёты других рецензентов, реализация, кандидат 41, captures, runtime, частные судьи и код вне реестра не открывались. Запускались только Quint/Apalache над этими моделями.

Что значит результат: все «violated/holds» — про модель при названных допущениях. Нарушение — следствие текста нормы, а не дефект реализации; утверждений о Source или реализации нет. Проверка ограничена max_steps (Apalache) и числом образцов (симулятор rust); для properties приведён свидетель, что завершённые проходы действительно входят в проверенную глубину.

## Что смоделировано

Каталог проекта: `decisions/inbox/ревью/quint-p05-d21ed721/` (модели `p05_pass.qnt`, `p05_retain.qnt`, `p05_crash.qnt`, `p05_retry.qnt`, `p05_stall.qnt`; конфигурации `cfg/`; `run.py`, `results.tsv`, `run.log`, `runs/`, `trial-mismatches.tsv`, `check_anchors.py`).

| Модель | Вопрос | Находки | Граница модели |
|---|---|---|---|
| `p05_pass` | Проход: retain, затем mirror; зависший и медленный сосед; подсчёт PEER_FAILS; построчные отказы | С1, М1 | 2 соседа, 6 ведер (NB); PASS_EVERY=600, PEER_FAILS=3; срок вызова BUDGET параметр (0 = нет, 5, 10), `STEP_BUDGET` — гипотеза поправки (не норма); порядок вызовов последовательный |
| `p05_retain` | Предикат retain на границе против скачков часов и Q6 | С15 | одно закрытое ведро; срок 86400 (`seams:52`); настенные/монотонные часы; скачки — среда; `MODE` LETTER/DEFER |
| `p05_crash` | Копия: 204 против потери питания; rewrite: снятие надгробия против публикации тела | С17, М6 | два независимых конечных автомата; порядок операций перебирается |
| `p05_retry` | Повторы `restore`: удвоение без разброса при старте вместе/со сдвигом | С18 | 2 сервера, RETRY=10, RETRY_MAX=600; разброс — мутант (норма не задаёт) |
| `p05_stall` | PULSE_LIMIT и пульс: «в следующем пульсе» против «только пока висит»; независимость пульса от прохода | М9, рядом С1 | один шаг, HEARTBEAT_EVERY=10, L=20 (значение порога — параметр; норма не задаёт) |

Границы инвариантов: `inv_passBounded` ограничивает и идущий проход (`now − passStart ≤ PASS_BOUND`), и завершённый (`lastPassDur ≤ PASS_BOUND`, поле пишется только при завершении прохода), чтобы простой не маскировал границу. `inv_retainGap` — интервал между запусками retain. `wit_tight` подтверждает, что граница достигается точно завершённым проходом (не вакуумна), `p04` — что при PASS_BOUND=59 нарушается. `inv_noEarly`/`inv_noEarlyNetZero` меряют реальное прошедшее время (монотонное) от последней записи до удаления. Все инварианты — safety; живость не моделировалась (симулятор длинных трасс только как контроль непротиворечивости шагов).

## Таблица прогонов (75 запусков; сумма 763.6 с)

Все строки — фактические результаты итоговых файлов моделей; расхождений ожидания и факта в итоговой таблице: 0. Виды: property — проверка следствий нормы или гипотезы; witness — свидетель достижимости (ожидается violated); mutant — мутант модели с ожидаемым нарушением; control — отрицательный контроль/контроль чувствительности.

| id | модель | инвариант | вид | сред. | шагов | overrides | ожид. | факт | сек |
|---|---|---|---|---|---|---|---|---|---|
| p01a-hang-nobudget | p05_pass | inv_passBounded | property | apalache | 16 | BUDGET=0;PASS_BOUND=6000 | violated | violated | 5.2 |
| p01b-hang-nobudget-gap | p05_pass | inv_retainGap | property | apalache | 16 | BUDGET=0;PASS_BOUND=6000 | violated | violated | 5.2 |
| p01w-hung-reach | p05_pass | wit_hung | witness | apalache | 8 | BUDGET=0;PASS_BOUND=6000 | violated | violated | 4.8 |
| p02a-budget-expfail | p05_pass | inv_passBounded | property | apalache | 34 | base | holds | holds | 6.2 |
| p02b-budget-expfail-gap | p05_pass | inv_retainGap | property | apalache | 34 | base | holds | holds | 6.1 |
| p02w-tight | p05_pass | wit_tight | witness | apalache | 20 | base | violated | violated | 5.4 |
| p02w2-twopasses | p05_pass | wit_twoPasses | witness | apalache | 34 | base | violated | violated | 6.1 |
| p02c-consulted-control | p05_pass | inv_consulted | control | apalache | 34 | base | holds | holds | 6.2 |
| p03a-budget5-expfail | p05_pass | inv_passBounded | property | apalache | 34 | BUDGET=5;PASS_BOUND=30 | holds | holds | 6.2 |
| p03w-budget5-tight | p05_pass | wit_tight | witness | apalache | 20 | BUDGET=5;PASS_BOUND=30 | violated | violated | 5.4 |
| p04-bound-sensitivity | p05_pass | inv_passBounded | control | apalache | 20 | PASS_BOUND=59 | violated | violated | 5.4 |
| p05-expiry-not-failure | p05_pass | inv_passBounded | property | apalache | 24 | EXPIRY_FAIL=false | violated | violated | 5.5 |
| p06-slow-success | p05_pass | inv_passBounded | property | apalache | 24 | KINDS=Set(SLOW) | violated | violated | 5.6 |
| p07-percall-hang-ok | p05_pass | inv_passBounded | property | apalache | 26 | KINDS=Set(HANG,OK);PER_CALL=true | violated | violated | 17.9 |
| p08a-stepbudget-fix | p05_pass | inv_passBounded | control | apalache | 34 | KINDS=Set(HANG,SLOW,OK);PASS_BOUND=70;PER_CALL=true;STEP_BUDGET=60 | holds | holds | 517.0 |
| p08w-stepbudget-completes | p05_pass | wit_completedPass | witness | apalache | 30 | KINDS=Set(HANG,SLOW,OK);PASS_BOUND=70;PER_CALL=true;STEP_BUDGET=60 | violated | violated | 9.5 |
| p09a-healthy-bound0 | p05_pass | inv_passBounded | control | apalache | 34 | KINDS=Set(OK);PASS_BOUND=0 | holds | holds | 6.2 |
| p09w-healthy-twopasses | p05_pass | wit_twoPasses | witness | apalache | 34 | KINDS=Set(OK);PASS_BOUND=0 | violated | violated | 6.2 |
| p10-m1-letter-refusecount | p05_pass | inv_behindCopied | property | apalache | 14 | BUDGET=10;KINDS=Set(OK);REFUSAL_FAIL=true;REFUSE_HEAD=3 | violated | violated | 5.1 |
| p11a-m1-refuse-notcounted | p05_pass | inv_behindCopied | property | apalache | 20 | KINDS=Set(OK);REFUSAL_FAIL=false;REFUSE_HEAD=3 | holds | holds | 5.7 |
| p11w-m1-completed | p05_pass | wit_completedPass | witness | apalache | 20 | KINDS=Set(OK);REFUSAL_FAIL=false;REFUSE_HEAD=3 | violated | violated | 6.5 |
| p12-m1-head2-control | p05_pass | inv_behindCopied | control | apalache | 20 | KINDS=Set(OK);REFUSAL_FAIL=true;REFUSE_HEAD=2 | holds | holds | 5.7 |
| p12w-m1-head2-completed | p05_pass | wit_completedPass | witness | apalache | 20 | KINDS=Set(OK);REFUSAL_FAIL=true;REFUSE_HEAD=2 | violated | violated | 5.5 |
| m01-noskip | p05_pass | inv_passBounded | mutant | apalache | 24 | MUT_NO_SKIP=true | violated | violated | 5.3 |
| m02-keepskip | p05_pass | inv_consulted | mutant | apalache | 24 | MUT_KEEP_SKIP=true | violated | violated | 5.7 |
| m03-noskip-nb3-control | p05_pass | inv_passBounded | control | apalache | 34 | MUT_NO_SKIP=true;NB=3 | holds | holds | 5.7 |
| r01a-letter-nojump-q6 | p05_retain | inv_noEarly | property | apalache | 8 | base | holds | holds | 0.9 |
| r01b-letter-nojump-s50 | p05_retain | inv_s50 | property | apalache | 8 | base | holds | holds | 0.8 |
| r01c-letter-nojump-s49 | p05_retain | inv_s49 | property | apalache | 8 | base | holds | holds | 0.8 |
| r01w1-removed | p05_retain | wit_removed | witness | apalache | 8 | base | violated | violated | 0.8 |
| r01w2-boundary-eq | p05_retain | wit_boundaryEq | witness | apalache | 8 | base | violated | violated | 0.7 |
| r01w3-below | p05_retain | wit_retainBelow | witness | apalache | 8 | base | violated | violated | 0.7 |
| r02-letter-forward-q6 | p05_retain | inv_noEarly | property | apalache | 8 | JUMPS=Set(0,86400) | violated | violated | 0.7 |
| r02w-jumped | p05_retain | wit_jumped | witness | apalache | 4 | JUMPS=Set(0,86400) | violated | violated | 0.7 |
| r03-letter-back-then-correct | p05_retain | inv_noEarlyNetZero | property | apalache | 12 | CAN_APPEND=true;JUMPS=Set(0,-600,600) | violated | violated | 0.8 |
| r03c-letter-back-no-append-control | p05_retain | inv_noEarlyNetZero | control | apalache | 8 | CAN_APPEND=false;JUMPS=Set(0,-600,600) | holds | holds | 1.8 |
| r04a-letter-qualified-eps1jump | p05_retain | inv_noEarly | control | apalache | 10 | ALLOWED=1;JUMPS=Set(0,1);MAX_JUMPS=1 | holds | holds | 2.0 |
| r04b-letter-qualified-eps-unbounded | p05_retain | inv_noEarly | control | apalache | 10 | ALLOWED=1;JUMPS=Set(0,1) | violated | violated | 0.7 |
| r05a-defer-forward-q6 | p05_retain | inv_noEarly | property | apalache | 10 | JUMPS=Set(0,86400);MODE=DEFER | holds | holds | 1.0 |
| r05b-defer-forward-s50 | p05_retain | inv_s50 | property | apalache | 10 | JUMPS=Set(0,86400);MODE=DEFER | violated | violated | 0.7 |
| r05w-defer-removes-after-term | p05_retain | wit_removedAfterTerm | witness | apalache | 10 | JUMPS=Set(0,86400);MODE=DEFER | violated | violated | 0.7 |
| r06a-defer-seam-controlled | p05_retain | inv_s50 | control | apalache | 10 | MODE=DEFER | holds | holds | 0.9 |
| r06b-defer-seam-q6 | p05_retain | inv_noEarly | control | apalache | 10 | MODE=DEFER | holds | holds | 0.8 |
| r06w-defer-seam-removes | p05_retain | wit_removedAfterTerm | witness | apalache | 10 | MODE=DEFER | violated | violated | 0.7 |
| r07w-defer-back-removes | p05_retain | wit_removedAfterTerm | witness | apalache | 12 | CAN_APPEND=true;JUMPS=Set(0,-600,600);MODE=DEFER | violated | violated | 0.7 |
| r07-defer-back-correct | p05_retain | inv_noEarly | control | apalache | 12 | CAN_APPEND=true;JUMPS=Set(0,-600,600);MODE=DEFER | holds | holds | 1.1 |
| r08-watermark-not-enough | p05_retain | inv_noEarly | control | apalache | 12 | CAN_APPEND=true;JUMPS=Set(0,-600,600);WRITTEN_WATERMARK=true | violated | violated | 0.7 |
| rm1-strict | p05_retain | inv_s50 | mutant | apalache | 8 | MUT_STRICT=true | violated | violated | 0.7 |
| rm2-early | p05_retain | inv_s49 | mutant | apalache | 8 | MUT_EARLY=true | violated | violated | 0.7 |
| rm3-defer-no-mono | p05_retain | inv_noEarly | mutant | apalache | 8 | JUMPS=Set(0,86400);MODE=DEFER;MUT_NO_MONO=true | violated | violated | 0.6 |
| k01-letter-no-barrier | p05_crash | inv_ackDurable | property | apalache | 6 | base | violated | violated | 3.7 |
| k02a-barrier-fix | p05_crash | inv_ackDurable | property | apalache | 10 | BARRIER=true | holds | holds | 3.8 |
| k02w-barrier-ack-crash | p05_crash | wit_ackThenCrash | witness | apalache | 8 | BARRIER=true | violated | violated | 3.7 |
| k03-order-any | p05_crash | inv_noResurrect | property | apalache | 8 | base | violated | violated | 3.7 |
| k04a-body-first | p05_crash | inv_noResurrect | property | apalache | 12 | ORDER=BODY_FIRST | holds | holds | 3.9 |
| k04w1-rewrite-done | p05_crash | wit_rewriteDone | witness | apalache | 8 | ORDER=BODY_FIRST | violated | violated | 3.7 |
| k04w2-crash-mid | p05_crash | wit_crashMid | witness | apalache | 8 | ORDER=BODY_FIRST | violated | violated | 3.8 |
| k05-tomb-first-mut | p05_crash | inv_noResurrect | mutant | apalache | 8 | ORDER=TOMB_FIRST | violated | violated | 3.8 |
| t01a-together | p05_retry | inv_alwaysTogether | property | apalache | 12 | base | holds | holds | 4.2 |
| t01b-gap | p05_retry | inv_gapPreserved | property | apalache | 12 | base | holds | holds | 4.2 |
| t01w-coincide | p05_retry | wit_coincide | witness | apalache | 10 | base | violated | violated | 4.0 |
| t02a-offset-gap | p05_retry | inv_gapPreserved | property | apalache | 16 | STARTS=Set(0,5) | holds | holds | 5.3 |
| t02w-offset | p05_retry | wit_nonzeroGap | witness | apalache | 12 | STARTS=Set(0,5) | violated | violated | 4.1 |
| t03-jitter-mut-together | p05_retry | inv_alwaysTogether | mutant | apalache | 10 | JITTER=Set(0,3) | violated | violated | 4.0 |
| t04-jitter-mut-gap | p05_retry | inv_gapPreserved | mutant | apalache | 10 | JITTER=Set(0,3) | violated | violated | 4.0 |
| s01-rules-conflict | p05_stall | inv_rulesAgree | property | apalache | 12 | base | violated | violated | 0.6 |
| s01b-rules-conflict-strict | p05_stall | inv_rulesAgreeStrict | property | apalache | 12 | base | violated | violated | 0.6 |
| s01w-shown | p05_stall | wit_shown | witness | apalache | 12 | base | violated | violated | 0.6 |
| s02-visible-bound | p05_stall | inv_visible | property | apalache | 16 | base | holds | holds | 0.8 |
| s02w-running-past-edge | p05_stall | wit_runningPastEdge | witness | apalache | 16 | base | violated | violated | 0.6 |
| s02m-hb-blocked | p05_stall | inv_visible | mutant | apalache | 16 | BLOCK_HB=true | violated | violated | 0.6 |
| s03-no-exceed-control | p05_stall | inv_rulesAgree | control | apalache | 12 | DURS=Set(19) | holds | holds | 0.6 |
| s03w-short-completes | p05_stall | wit_noExceed | witness | apalache | 10 | DURS=Set(19) | violated | violated | 0.6 |
| sim01-budget-long | p05_pass | inv_passBounded | control | rust | 400 | PASS_BOUND=60 | holds | holds | 1.3 |
| sim02-m1-long | p05_pass | inv_behindCopied | control | rust | 400 | KINDS=Set(OK);REFUSAL_FAIL=true;REFUSE_HEAD=2 | holds | holds | 1.4 |

Сводка видов: property 27, witness 23, mutant 9, control 16.

Пробные расхождения вынесены в `trial-mismatches.tsv` с причинами (ошибка объёма запроса к Apalache; `r03c` на 12 шагах — таймаут, глубина снижена до 8 шагов; контроль r04 первого вида — среда допускала многократные скачки, поэтому контроль разделён на r04a/r04b; `rm2` первой версии недостижим из-за шага времени; `r03c` первой версии считал сумму скачков не в момент удаления). После правок запуски `p05_retain` и `p05_stall` повторены целиком.

## Мутанты и контроли

Мутанты (9 шт., поймано 9): `m01` снятие skip после PEER_FAILS — нарушается граница `inv_passBounded`; `m02` skip переносится на следующий проход — нарушается обращение к соседу следующего прохода (`s67`, `seams:69`); `rm1` строгое `>` на границе — нарушается `inv_s50`; `rm2` удаление на 1 с раньше — нарушается `inv_s49`; `rm3` откладывание без проверки монотонного времени — нарушается Q6; `k05` порядок «снять надгробие, затем тело» — воскрешение копии; `s02m` пульс блокируется проходом — нарушается видимость затяжного шага; `t03`, `t04` разброс задержек — совпадение и сохранение сдвига перестают быть инвариантами (разброс — мутант, в норме его нет).

Отрицательные контроли: `p04` (граница 59 ниже точной 60 — нарушается, граница не ослаблена); `p09a` здоровый сосед при границе 0, `p02c` — обращение к соседу без мутанта; `p08a` гипотетический срок шага закрывает нарушения p05/p06/p07 (не норма — проверка, что нарушения устранимы и модель не ложно-красная); `p12` порог PEER_FAILS для отказов строк; `m03` мутант без эффекта при NB=PEER_FAILS; `r03c` нет дозаписи после отката — нет раннего удаления; `r04a` один скачок в пределах допуска (квалифицированная среда) — Q6 держится; `r04b` без предела числа скачков — нет: предел должен быть суммарным; `r06a`, `r06b` DEFER с контролируемым монотонным источником шва — выполняются и s50, и Q6; `r07` откат с возвратом при DEFER; `r08` watermark `written` не закрывает прямой скачок; `s03` шаг короче порога — правила пульса совпадают; `sim01`, `sim02` — симулятор rust на длинных трассах (контроль, не доказательство).

## Находки: подтвердило, сняло, уточнило

Счёт отчёта (С19/М10) не меняется; ниже — только уточнения формулировок, новых находок для счёта модель не вводит.

**С1 — подтверждена с уточнением формулировки и решения.**
- Если следовать тексту P/05 (срока вызова к соседу нет, PULSE_LIMIT — только диагностический порог, `norms:371`), зависший сосед на шаге mirror держит проход вечно: `inv_passBounded` нарушается при любой конечной границе (`p01a`), нарушается и период retain (`p01b`). Следующий проход планируется только от конца прежнего (`norms:299`), поэтому retain и последующие шаги не запускаются: цепочка следствий формулировки С1 при этом допущении есть.
- Уточнение последствия: общая обязанность `prod:9` требует объявить конечный бюджет ожидания зависимости, и `norms:29` распространяет её на P/05. При объявленном сроке вызова и засчитывании истечения как неуспеха PEER_FAILS проход конечен и точно ограничен: не больше (число соседей) × PEER_FAILS × срок вызова, независимо от числа ведер (`p02a`, `p02b`, `p03a`; граница достигается: `p02w`, `p03w`; чувствительность: `p04`). Вместо «останавливает проход» корректнее: «при отсутствии объявленного срока — останавливает; при конечном сроке — задерживает на названную величину».
- Уточнение решения. Предложенного в С1 (срок вызова плюс засчитывание истечения) недостаточно, чтобы ограничить проход: (а) если истечение не засчитывается как неуспех (норма не называет) — длительность растёт с числом ведер (`p05`); (б) даже при засчитывании сосед, отвечающий успехом чуть раньше срока, не набирает PEER_FAILS (серия сбрасывается успехом, `norms:985`, s67 `seams:69`) — проход растёт с числом ведер (`p06`); то же при чередовании истечения и успеха по вызовам (`p07`). Гипотетический срок шага закрывает все три случая (`p08a`, witness `p08w`; `STEP_BUDGET=60` — параметр поправки, граница 70 = STEP_BUDGET + один вызов) — это проверка устранимости, а не предложение нормы. Нужна отдельная граница шага или прохода, а не только срока вызова.

**М1 — подтверждена.** Если построчный отказ (400/409/422) считается неуспехом соседа, то при стабильном порядке ведер PEER_FAILS постоянных отказов в голове списка отсекают ведра за ними на каждом проходе: `inv_behindCopied` нарушается (`p10`). Если отказ строки не считается неуспехом соседа — выполняется (`p11a`, `p11w`); порог именно PEER_FAILS (`p12`, `p12w`). Допущение: порядок ведер стабилен между проходами; норма его не называет; при ротации порядка голодание не вечное (не моделировалось).

**С15 — подтверждена, уточнена.** Текст R020 при неопределённом скачке вперёд удаляет ведро раньше реально прошедшего срока, это прямо против Q6 `ej:216`: `inv_noEarly` нарушается (`r02`). Новый оттенок, который модель показала отдельно: откат часов назад перед последней дозаписью с последующей коррекцией тоже приводит к раннему удалению (до величины отката; в следе модели — 1 с при откате 600): `written` взят из отката (`ej:154`, `r03`; контроль без дозаписи `r03c`); прямой скачок после дозаписи так тоже не закрывается (`r08`). Откладывание с проверкой монотонного времени выполняет Q6 (`r05a`, `r07`), но красит шов s50, если шов двигает только настенные часы и среда считает скачок неопределённым (`r05b`; шов — «controlled wall clock», `forms:58`). С контролируемым вместе монотонным источником оба утверждения совместимы (`r06a`, `r06b`, witness `r06w`). Поэтому находка С15 точнее так: конфликта «R020 или s50» нет безусловно; не хватает входа, определяющего, что считать неопределённым скачком для шва — то самое решение, которое предлагал отчёт. Контроль: скачок в пределах квалифицированной границы — ранее срока не более этой границы (`r04a`); многократные скачки без суммарного предела это не гарантируют (`r04b`) — значит «граница часов» из `prod:11` должна быть суммарной для окна, а не единичной.

**С17 — подтверждена при допущении.** Если публикация копии и ответ 204 не разделены барьером (норма не требует, `norms:819`, стойкость не доказывается `forms:40`) и потеря питания отбрасывает несброшенную публикацию, то 204 не гарантирует наличие копии (`k01`). С барьером перед 204 выполняется (`k02a`, witness `k02w`). Допущение о семантике потери питания — вне норм, оговорено.

**М6 — подтверждена.** «Тем же действием» (`norms:78`, `tomb:82`) не задаёт порядка при сбое: порядок перебирается и есть сбой посреди rewrite, где надгробия уже нет, тела ещё нет, а у соседа живёт старая копия (`k03`). При порядке «тело, затем надгробие» (`k04a`, свидетели `k04w1`, `k04w2`) случай недостижим. Мутант `k05` снимает надгробие первым — нарушение.

**С18 — подтверждена как арифметика; вывод о шторме не сделан.** При равном старте без разброса все повторы совпадают по времени, при сдвиге старта сохраняется сдвиг (`t01a`, `t01b`, `t01w`, `t02a`, `t02w`). Разброс (мутант) разрушает совпадение (`t03`, `t04`). Величина всплеска и влияние на соседа в модели нет: Quint не выражает нагрузку.

**М9 — уточнена, новое наблюдение вне счёта.** R028 `norms:370` требует `pass_stalled` в следующем пульсе после превышения порога; `norms:288`, `norms:524` — «только пока проход висит». Шаг, превысивший порог и завершившийся до следующего пульса, по первому правилу в поле попадает, по второму нет: `inv_rulesAgree` нарушается (`s01`), в том числе строго, когда шаг закончился раньше пульса (`s01b`). Контроль без превышения: совпадают (`s03`). Шаг, идущий дольше L + HB, виден в пульсе (`s02`, witness `s02w`) при условии, что пульс не блокируется проходом (`s02m` — мутант).

Снято: находок, снятых моделью полностью, нет. Формулировка «останавливает проход» С1 сужена уточнением выше.

## Не вошло

| Находка | Причина |
|---|---|
| С2, С3, С4, С5 | Нет своего исхода фазы или замка, общая обязанность `prod:9` при этом есть; как гонка ничего не добавляет: модель пересказала бы отсутствие нормы (и С3 — отсутствие начала отсчёта) |
| С6 | Два процесса на одном `PLATFORM_DIR`: отсутствует механизм захвата; для гонки нужна модель файловой системы и присутствия (объём вне поручения, находка статична) |
| С7, С9, С11, С12, М3, М8 | Бюджеты памяти/диска/дескрипторов и стоимость — статичные объёмы, не гонка |
| С8 | Отмена при уходе клиента: нормы нет, модель лишь повторила бы отсутствие |
| С10 | Штатная остановка: нормы нет ни по одной из четырёх частей |
| С13, С14, М7, М10 | Форма и пробы; М10 — расхождение часов для PUT mirror: при опережении отправителя сводится к отказам строки (p10), отдельной временной логики нет |
| С16 | Выбор источника истины при расхождении сумм — решение, а не гонка/время |
| С19 | Состав опрашиваемых серверов и исход неизвестного множества — форма и норма, не время |
| М2, М4, М5 | Утечка временных файлов, противоречие `mtime` и текста R034, канал неустановимой метки — статично |
| Параллельный обход соседей, выбор `copies` живых соседей (`LOST_AFTER`), `settings_unread` | Вне вопроса С1: параллелизм меняет только множитель суммы, зависание шага остаётся |
| Живость, удержание, restore с копиями, надгробия как GC, живость часов | Только safety на ограниченной глубине |

Запрещённые области соблюдены: другие рецензенты, смысловой common-пакет, Source, кандидат 41, captures, runtime, частные судьи, код вне реестра не читались и не запускались; модели других единиц не запускались; SUT, native и кандидат не исполнялись.

## Допущения и пределы

- Граница проверки — max_steps/samples из таблицы; это ограниченная проверка, а не доказательство для всех трасс. Для property указан свидетель (достижимость) и чувствительность (`p04`).
- Значения: PASS_EVERY (`const:6`), PEER_FAILS (`const:7`), HEARTBEAT_EVERY (`const:5`), RESTORE_RETRY/MAX (`const:8`, `const:9`) и срок 86400 (`seams:52`) взяты из форм; срок вызова BUDGET (10 и 5), порог L, число ведер NB, разброс и размеры скачков — параметры модели без значения в норме, значения норм не подменяют (`prod:11`, `norms:368`).
- `p05_pass`: retain/usage/relieve длительностью 0 (оптимистично), порядок вызовов последовательный, сосед висит либо отвечает `FAIL`/`OK`/медленно; поведение соседа между проходами постоянно, кроме PER_CALL. PEER_FAILS — серии подряд, успех сбрасывает (`norms:985`, s67 `seams:69`). PASS от конца прохода `norms:299`, порядок шагов `norms:300`, каждый шаг своя попытка `norms:986`.
- `p05_retain`: одно ведро, без удержаний, без перезапуска (монотонные часы перезапуск не переживают — предикат DEFER с перезапуском не проверен); `written` берётся из настенных часов на добавлении (`ej:154`); зеркальная добавка `MIRROR_RETENTION_EXTRA` не менялась, предикат тот же (`norms:224`). «Неопределённость» скачка — вход среды (`ej:216`, `prod:11`), шов — «controlled wall clock» (`forms:58`).
- `p05_crash`: семантика потери питания — допущение; отдельные действия шагов приёма и rewrite — абстракция.
- `p05_stall`: пульс независим от прохода (`norms:268`, допущение); порог L — параметр, норма значения не задаёт (`norms:368`).
- Якоря: `check_anchors.py` сверил 38 якорей `файл:строка` по байтам среза, расхождений 0. Сокращения как в отчёте: `norms` — `Platform/05-resource/spec/05-resource.norms.md`, `const` — `forms/runtime-constants.tsv`, `forms`, `seams` — `acceptance/seams.tsv`, `ej`, `tomb`, `prod`, `pv` — `Platform/common/contracts/{event-journal,tombstone,production-obligations}.md`, `Platform/common/vectors/production-obligations/README.md`.
- Ограничение: заявления только о моделях при названных допущениях; не вход приёмки; READY/GATE не заявляется.

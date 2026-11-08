adr: 0130 (P/01 пп. 9–14, Quint — позднее чтение модели)

# P/01 пп. 9–14 после публикации модели Quint — позднее независимое чтение — review103-kimi

**Поздняя фаза.** Это отдельный report-only нормальный child коммита `5e07b65bb6577d527c8443529c2c5f3e4a82d188`. Собственные frozen-документы этой сессии — отчёт P01 пп. 9–14 (`2c6b19dd8`) и bounded note (`c845c203d`, ветка `kimi103/review-p01-points9-14-244355`) — **не переписываются и не переоткрываются**: coverage/counts в них не меняются, ни одна находка из них не отменяется и не переформулируется этим текстом. Позднее чтение common-модели `c022` — другая единица, здесь не повторяется. Peer later-reading (Codex) не читался.

## Основание и целостность входа

- Задание: `KIMI-P01-POSTMODEL-LITERAL-READING-TASK.json`, sha256 `096961ac5ae7141757b7e6b6ad02fa7d346579d98937dc30c0e35697a0a40865` (совпал при сверке).
- Квитанция приёма: `P01-MODEL-SRC-SINGLE-ACCEPTANCE.json` (coord103-src, 2026-11-08T16:54:55Z), статус `ACCEPTED_BOUNDED_MODEL_ARTIFACT_WITH_Q1_Q6_LIMITS`.
- Модель: `5e07b65bb`, parent = Source `244355d161139bd6fe65fd68c7e5134598c21ba3` (подтверждено `git log`). 157 добавленных путей = 143 прогона + 7 `.qnt` + 3 Python + `anchors.tsv` + `results.tsv` + `run.log` + отчёт.
- Статистика `results.tsv` по байтам совпала с квитанцией: 111 verify / 32 sim; kinds 63 property / 37 witness / 24 mutant / 19 control; expect 80 hold / 63 violated; match 143 ok; по модулям admission 39, import_group 25, stop 22, id_memory 20, door 18, recover 15, admission_wit 4. Маркер обрезки stdout в `run.py:179` (>24000 символов → first 12000 + last 8000), обрезанных файлов 16 (15 sim + 1 verify) — как в квитанции. Якорей 59, сверка `check_anchors.py` — подстрока по `git show <pin>:<path>`; `verify_results.py` сверяет sha256 подставленного текста модели с шапкой прогона и не парсит содержимое трасс.
- Только чтение: rerun модели, новые модели/прогоны/окна, правки Source/проб не выполнялись и не заказываются.

## Прочитанный объём

Отчёт автора модели целиком (363 строки). Все 7 модулей Quint целиком. `run.py`, `check_anchors.py`, `verify_results.py`, `anchors.tsv`. Точные нормативные блоки Source 244 по фактическим ссылкам модели: `01.3:36–76` (refuse_start, leader_wait, door), `01.3:85–99` (admission в журнале и снимке), `01.3:100–169` (admin_ops, floor, import, metrics, box), `01.3:325–374` (recover R021–R028, фазы R026, stop R034), `01.1:80–99` (CLOCK_SKEW «do not check it»), `01.1:445–544` (R068–R089), `01.1:685–774` (batch R132–R135, R141–R142, R144), `production-acceptance.md:10–20,45–75`, `runtime-constants.tsv` целиком, `daemon-flags.tsv:37`, `02.4-installer.norms.md:40–55`. Трассы выборочно, по семантическим вопросам (3): `stop__not_w_stalledCancel`, `id_memory__not_w_ambiguousRetry`, `import_group__not_w_stuck`. Без blanket-аудита 143 ожиданий, без header/hash/code-аудита, без replay приёмки.

## Оценка faithful / unfaithful по модулям

**admission.qnt — faithful.** Формула `max(часы, prev)` — точно `01.1:451`. Проверка по сохранённому времени и единый исход на всех серверах (`01.1:456–458`) — `replicate` применяет по `r.adm`, `inv_sameOutcome`, мутант `MUT_APPLY_OWN_CLOCK` пойман. Неубывание и продолжение с последней записи включая снимок (`:458`, `01.3:91–92`) — `inv_admNonDec`, `restoreAdm`, `restart`, `MUT_SNAP_NO_ADM`. Порядок проверок id → not_after/not_before → guard → cas, first-violation (`:534–537`) — `outcomeOf`, `MUT_CAS_BEFORE_TIME`. Рост метаданных на отказах (`:537, :541, :694`) — `inv_metaLast`, `MUT_REFUSE_ROLLBACK`, `not_w_refusalRaises`. R071 (`:473–477`) — `inv_r071` (delete ok с `not_before=T` ⇒ поздняя запись с `not_after=T` не ok, так как adm не убывает и > T). `expired` — тот же отказ при том же сроке (`:539`) — `inv_expiredSticky`. Catch-up (`:463–465`) — `inv_catchUp` с посылкой «часы записи ≥ времени допуска предыдущей записи» (чуть слабее буквального «часы догнали последнее время допуска», но эквивалентно при неубывании; overclaim нет). binary64 (`:466`) не моделируется — заявлено в границах.

**admission_wit.qnt — faithful.** Невакуумность посылок проверяется отдельно; автор честно отметил отсутствие свидетеля с двумя ok-записями для `inv_oneOkPerId`.

**import_group.qnt — faithful при абстракции G1.** Отказ старта на незавершённой попытке «после floor, до Done», код 2 (`01.3:40–42`) — `startRefusedBy`, узел остаётся down (`02.4:48` «without a restart, until an action of the operator») — `refused` навсегда. Маршрут только через `admin.sock` живого лидера (`:104`) — `importRouteOpen`. Завершённая — отказ, незавершённая — replay (`:109–110`), floor первая запись (`:120`), писатель ждёт Done (`:134`), полнота Done (`:147–148`), replay сохраняет F1 (`:149–150`, `:353`), новая попытка — новая генерация (`:150`) — всё покрыто инвариантами и пойманными мутантами. Кворум на действиях import не требуется: `importRouteOpen` проверяет только `leader != "" and up.get(leader)`; `elect` требует большинства, но лидер сохраняется при потере не-лидеров. Это квитанция Q4 — подтверждаю по тексту модели.

**recover.qnt — faithful как «текст не исключает».** Шаги дамп/журнал/удаление строк/floor (`:331–332`) — `inv_completeConsistent`; floor только растёт (`:123`) — `inv_floorGrows`, `MUT_FLOOR_DOWN`; генерация из upper и часов (`:112–114`) — `stepFloor = max(floorGen+1, HOUR)`. Текст молчит о порядке шагов, атомарности и старте на незавершённом recover — модель перечисляет комбинации, которые не запрещены; `ATOMIC_PUBLISH`/`REFUSE_ON_PARTIAL` — контроли, не нормы. recover как выход из С1 в модель не входит — честный gap (см. вопросы ниже).

**id_memory.qnt — faithful.** Оба условия и строгость «more than» (`01.1:733`, `prod:15,62`: равенство возраста не подходит) — `inv_forgetBoth`, `inv_strictAge`, мутанты `MUT_AGE_ONLY/RECORDS_ONLY/FORGET_ANY/EQ_AGE` пойманы. Счётчик — только успешные более поздние применения (`prod:15` «do not invent a counting rule from unadmitted requests, admitted refusals or replays») — `recordsOk` по `applyNew`. Повтор — первый ответ без новой версии (`01.1:501–502`) — `inv_againSameAnswer`, `MUT_REPLAY_NEW_VER`. M3 (`AGE_BASE` wall/mono) — названное допущение, выбор нормы не сделан.

**stop.qnt — faithful как bounded safety.** Копия вне замка, stalled receiver не держит замок, любое завершение освобождает снимок и транспорт (`01.3:366`) — `inv_copyNoLock`, `inv_pinsMatchCopy`, `MUT_LEAK_PIN_ON_CANCEL`. Перестать принимать, классифицировать принятую работу по definite/ambiguous, снять снимки/соединения/слушатели (`:368`) — `inv_noAdmitAfterStop`, `inv_workClassified`, `inv_exitClean`, мутанты пойманы. Ранг — бухгалтерия меры, по построению действий.

**door.qnt — faithful.** `leader_wait` от потери лидера, не от запроса (`01.3:51`), попытка `DOOR_REQUEST_TIMEOUT+MARGIN` (`:59`, const 2+1 с), все голосующие недоступны → 503 (`:70`), исходы answered/unavailable/ambiguous (`:158–161`: answered — ответ с любым кодом). `voterAnswer503` передаёт 503 как исход «answered» — согласуется с `:158` («any code»). Окно лишнего ambiguous — `LEADER_WAIT − T_ATTEMPT` от потери лидера (`inv_ambigWindow`, hold) — формализация уточнения С12. Повтор с тем же id дедуплицируется (`01.1:766`) — `inv_idAtMostOne`; без id двойное применение достижимо — `not_w_noIdDouble`. D1–D3 названы; число попыток двери нормой не задано и моделью не выдумано.

## Новые meaningful gaps (norm / probe)

**Не выявлено.** Позднее чтение подтвердило квитанцию Q1–Q6 и не добавило новых смысловых разрывов поверх frozen `2c6`/`c845`. Проверенные кандидаты и почему они не новые:

- recover как выход из С1 не смоделирован — уже отмечено автором модели (С1, уточнение 2); передан как вопрос, не как находка.
- `namedExit` в import_group — конструкция автора для формализации «законного выхода», озвучена в отчёте; не норма и не новая норма.
- Вторая половина R142 (`01.1:738`: new write с тем же id и другим содержимым → 400) не смоделирована — `applyNew` недоступен для applied id; покрытие не заявлено, overclaim нет.
- Кворум-gating на import — квитанция Q4.
- Окно ambiguous двери — уточнение С12 в отчёте модели.
- Пределы шагов/`hold` симуляции, durability метаданных (`01.1:461–462`), binary64, GC/ёмкость, стоимость (С11), пробы (С3/С10) — честно не заявлены.

## Смоделированные альтернативы (какие чтения нормы выбраны; выбор новой нормы не сделан)

1. `01.3:40` — три чтения: буквальное (отказ на любой незавершённой попытке), `READING_BOX_ONLY`, `ALLOW_REBUILD_GROUP` (пересборка свежей группы; маршрут нормой не назван) + отдельная конфигурация `BOX`.
2. `not_w_doneAfterOutage`: literal — hold (14 шагов Apalache, симуляция 40/50000), box_only — violated, assume_rebuild — violated.
3. M3 `AGE_BASE`: wall (свидетели достижимы) vs mono (контроль hold) — оба прочтения перечислены, норма не выбрана.
4. recover: `ATOMIC_PUBLISH` × `REFUSE_ON_PARTIAL` — четыре контроля; `atomic_only` и baseline — violated, `refuse_only` и `atomic+refuse` — hold.
5. stop M1: исход запроса при остановке 503/reset — оба введены из молчания `01.1:751/764`; модель фиксирует, не выбирает.
6. door: контроли `T=L`, `T>L`, `only_id`, мутант «голосующий не отвечает 503» — границы окна ambiguous.
7. A1/G1 — абстракция Raft (лидер с полным журналом; общая фаза группы), известное условие, не норма.

## Overclaim покрытия против фактического Source

Существенный overclaim один и тот же, что в квитанции, — в именах двух свидетелей, подтверждён трассами:

- `stop__not_w_stalledCancel`: предикат — `Stopped and everCopyCancelled`, антецедент stalled в предикат не входит; выбранная трасса — `copyState: none → streaming → none`. Это достижимость отмены копии при остановке, не stalled-antecedent.
- `id_memory__not_w_ambiguousRetry`: предикат — `lastAgain/lifetimeVer/applied/issued`, `ambiguousAwaiting` в него не входит; в выбранной трассе `ambiguousAwaiting=false` во всех состояниях. Это обычный same-id replay, не ambiguous-antecedent.

Содержательные выводы отчёта автора на эти два имени не опираются; квитанция это зафиксировала, позднее чтение подтверждает. Прочих противоречий Source не найдено: заявленные инварианты следуют из текста при названных допущениях; отчёт держит пределы шагов и границы «не моделируется».

## Обязательные пределы (сохранены)

- 143 expectation matches ≠ 143 PASS; 111 verify = 32 sim/16 trimmed stdout.
- stop rank accounting — safety, не fairness/liveness/доказательство дедлайна 15s.
- stalledCancel — выбранная трасса streaming-cancel, не stalled-antecedent.
- ambiguousRetry — трасса ordinary same-id replay, не named ambiguous-antecedent.
- import quorum абстрагирован / без Raft-qualification.
- wall/mono/order/recover — альтернативы, не выбор новой нормы.

## Вопросы SRC→Architect (новые смысловые акценты позднего чтения — вопросы, не правки)

1. Выход из С1: replay на живом лидере через `admin.sock` — законный путь; пересборка группы нормой не названа; `recover` (`01.3:331`) к незавершённой попытке import текстом не применён — при выборе нормы его надо назвать или исключить явно.
2. Окно ambiguous у двери: лишний `ambiguous` возможен для запросов в первые `LEADER_WAIT − T_ATTEMPT` после потери лидера — намеренное следствие `01.3:51` + `01.3:59`, или текст стоит сузить?
3. Старт демона на незавершённом recover: текст молчит (отказ старта `01.3:40` называет только import/restore) — нужна атомарность публикации результата целиком либо отказ старта на частичном результате.

## Сводка

Позднее независимое чтение опубликованной модели Quint (`5e07b65bb`, Source `244355d1`) целиком: отчёт, 7 модулей, якоря, харнессы, точные нормативные блоки Source 244 по фактическим ссылкам, 3 выбранные трассовых фрагмента. Статистика артефактов совпала с квитанцией по байтам. Faithfulness: все 7 модулей faithful к тексту Source при их названных допущениях и абстракциях; противоречий норме не выявлено. Новых meaningful norm/probe gaps нет; кандидаты уже зафиксированы квитанцией Q1–Q6 или frozen `2c6`/`c845`. Overclaim — в именах двух свидетелей (Q2/Q3), подтверждён трассами; выводы отчёта им не опираются. Frozen-документы этой сессии не переоткрыты. Rerun/новые модели/прогоны/Source-правки не выполнялись.

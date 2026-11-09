adr: 0130 (P/08, Quint)

# Модель Quint P/08 (домен) на срезе a058c99b — review103-claude

**Фаза после независимых находок; автор тот же, независимость не заявляется; не вход приёмки кандидата; READY/GATE не заявляется.** Модель проверяет следствия текста норм при явных допущениях, а не Source и не реализацию: о реализации вывода нет.

- Срез: `a058c99b05116c5e77f2ce62ec0685e7b01efe65`. Фактический старт: 2026-11-08 23:12:08 UTC (`date -u`). Окончание счёта: 2026-11-09 00:24 UTC.
- Источник вопросов: мой замороженный отчёт из коммита `edbac97c` (находки С1–С20, М1–М6), копия использована только для чтения.
- Вход подтверждён: `P08-INDEPENDENT-SUBMISSIONS-COMPLETE-COUNT-ONLY.json`, sha256 `ae6feb30fc4f1a5f425ca5171681e289ee178a04c86c3cc722d740343252b1af`.
- Не читал: отчёты других рецензентов, смысловой common-пакет, реализацию Source, кандидата 41, captures, runtime, частных судей.
- Инструменты: Quint 0.33.0, Apalache 0.62.1 (`--max-steps` N — проверка до границы N шагов, не доказательство без границы), `quint run --backend=rust` (случайные трассы). Числа норм взяты из форм с якорем; времена среды — параметры модели.

Сокращения: `08.N` — `Platform/08-domain/spec/08.N-domain.norms.md`; `const` — `forms/runtime-constants.tsv`; `acc` — `common/contracts/accept.md`; `turn` — `common/contracts/turn.md`; `prod` — `common/contracts/production-obligations.md`; `token` — `common/contracts/domain-token.md`; `life` — `lifecycle.md`. Все якоря сверены скриптом `quint-p08-a058c99b/check_anchors.py` по байтам среза (78, расхождений 0).

## Что смоделировано

Девять файлов `quint-p08-a058c99b/*.qnt`; 115 пар «экземпляр/свойство», каждая проверена двумя инструментами: 230 запусков.

| Файл | О чём | Находки | Граница (узлы/шаги/CONST) | Что НЕ моделируется |
|---|---|---|---|---|
| `p08_turn` | очередь `domain/signer-turn`, запись с guard, неизвестный исход и барьер, объект без указателя (`get_at`/CAS/`put_at`), SIGTERM и принятая работа, локальная секция восстановления | С4, С15, С18 | 2 процесса A,B; 1 строка, 1 объект; ≤4 сообщения в сети; Apalache 11, rust 18 | реальное время (`TURN_TERM`, `TURN_RENEW` сведены к разрешённому захвату, `turn:98`), содержимое строк, HTTP |
| `p08_accept` | приём отчёта одного участника: запись report, delta, mark; отказ, неизвестный исход, недоступность store; повтор с тем же `sent_at` | С15, С18 | sent_at {1,2}, дороги d/r, по одному запросу; 12/14 | мьютекс (модельное допущение), base>0, чистка, road_quiet, carry |
| `p08_locks` | мьютекс участника, RW-замок заморозки с приоритетом писателя, секция восстановления | С3, С4 | секунды скачками; 1 ждущий мьютекса, 1 держатель и 1 ждущий общей стороны; 14/20 | содержимое записей, шаги handover после заморозки |
| `p08_parts` | восстановление копии частями, исход неполного чтения, срок | С6, С7 | 3 части (малая размерность), `PART_S` 20 и 40 с — параметр среды; 14 | смена головы (`behind`), несколько соседей, секреты |
| `p08_partgc` | жизнь части при выборке и рестарте держателя | С7, М3 | `BACKUP_HEADS`=5, `BACKUP_EVERY_MIN`=30, `BACKUP_FETCH`=600 по форме; 16/24 | учёт на keeper, связывание неизменённых частей |
| `p08_gather` | сбор «from nothing», второй переезд, `removed` | С7 | 1 имя, 1 секция; 8 | подписи, source (term, rev), close |
| `p08_clock` | скачок настенных часов: удержание имени, окно книг, ожидание смены ключа | С16 | `TOKEN_LIFETIME`=900, `TOKEN_SKEW`=60, `LOST_AFTER`=45; 12/12 | рестарт, несколько держателей, `until` партий (`08.3:109`) |
| `p08_age` | локальный монотонный возраст и частые рестарты | М5, С7 (`PARTIAL_QUIET`) | `IDEM_KEEP`=86400, `PARTIAL_QUIET`=10800; потолок 2 строки вместо 4096 (малая размерность); 14/20 | частота прохода, слово оператора |
| `p08_storm` | `busy`, порог, первые целые отчёты после смены держателя | С13, С14 | 3 камеры, 3 сервера, порог 2 вместо `REPORT_RATE` 200 (малая размерность: форма, не оценка); 10 | retry_in, разброс проходов P/09.1, размеры тел, батчи реле |

### Допущения с якорем
- Порядок и барьер: `turn:81`, `turn:83`, `08.10:210`, `08.10:211`, guard `08.10:90`, объект `08.10:98`, `08.10:99`, `08.10:101`.
- SIGTERM: `08.10:87`, `08.10:208`, `life:74`. Принятая работа: `prod:9` называет «shutdown and accepted-work completion» как обязанность объявить бюджет, но числа и порядка в P/08 нет.
- Приём отчёта: `acc:289` (мьютекс), `acc:292` (same/heard), `acc:307` (порядок записи), `08.3:685`, `08.3:686`, `08.3:687` (нечитаемо → 503 без записи), `08.3:702`, `08.3:704` (барьер, принятое не откатывается).
- Заморозка: `08.8:299` (общий срок 90 с), `08.8:308` (приоритет писателя, ожидание входит в срок). Секция: `08.8:385`. Эталон «90» для мьютекса — только линейка из `08.8:299`, не норма для мьютекса.
- Копия частями: `08.8:203`, `08.8:204`, `08.8:205`, `08.8:206`, срок move `08.8:393`, «state = copy» `08.8:463`, разрыв до claim `08.8:810`, сосед и голова `08.8:414`, `08.8:445`, исключение split `08.8:408`. Точка, где текст молчит (исход неполного чтения и срока после шага 5), смоделирована как недетерминированный выбор; контроли `parts_c_*` реализуют предложение С6 и **не являются нормой на срезе**.
- Сбор: `08.8:517` (потеря `removed` названа пределом), `08.8:923` (второй переезд не смоделирован), `08.8:541`. Удержание имени: `08.4:79`, `08.4:80`; строго после `until` (допущение: граница равенства не трактуется как нарушение). Токен: `token:45`, `token:86`. Посылка о часах `08.2:83` в тексте — только про часы держателей. Книги `08.5:55`. Смена ключа `08.2:78`, `08.2:80`, `08.2:81`.
- Числа форм: `const:14`, `const:30`, `const:31`, `const:36`, `const:46`, `const:48`, `const:49`, `const:50`.

Вид запуска: property — свойство (ожидаемое «violated» значит следствие текста при допущениях, не дефект реализации); witness — достижимость заявленного порядка (инвариант-отрицание, нарушение и есть трасса свидетеля, порядок задан штампами `seq`, а не конечным флагом); mutant — ожидаемое нарушение; control — ожидаемое выполнение в варианте.

## Таблица прогонов

`results.tsv` — 230 строк, `match`=yes у всех 230. Итог по видам: property 88 (ok 46, violated 42), witness 76 (violated 76), mutant 30 (violated 30), control 36 (ok 36). Инструменты: quint-run-rust 115, apalache 115; расхождений между инструментами на итоговых строках нет.

| Экземпляр | Свойство | Вид | Ожидание | rust (шаги/выборки) | Apalache (шаги) |
|---|---|---|---|---|---|
| turn_norm | inv_guard | property | ok | ok (18/100000) | ok (11) |
| turn_norm | inv_no_late_apply | property | ok | ok (18/100000) | ok (11) |
| turn_norm | inv_no_reorder | property | ok | ok (18/100000) | ok (11) |
| turn_norm | inv_no_drop | property | violated | violated (18/100000) | violated (11) |
| turn_norm | inv_no_stale_restore_obj | property | violated | violated (18/100000) | violated (11) |
| turn_norm | wit_unknown_barrier_refuse | witness | violated | violated (18/100000) | violated (11) |
| turn_norm | wit_barrier_only | witness | violated | violated (18/100000) | violated (11) |
| turn_norm | wit_takeover_confirm_fails | witness | violated | violated (18/100000) | violated (11) |
| turn_norm | inv_no_overwrite | property | ok | ok (18/100000) | ok (11) |
| turn_norm | wit_sigterm_inflight_refused | witness | violated | violated (18/100000) | violated (11) |
| turn_norm | wit_restore_overlap | witness | violated | violated (18/100000) | violated (11) |
| turn_norm | wit_applied_write | witness | violated | violated (18/100000) | violated (11) |
| turn_m_nobump | inv_no_late_apply | mutant | violated | violated (18/100000) | violated (11) |
| turn_m_blind | inv_no_reorder | mutant | violated | violated (18/100000) | violated (11) |
| turn_m_noguard | inv_guard | mutant | violated | violated (18/100000) | violated (11) |
| turn_c_drain | inv_no_drop | control | ok | ok (18/100000) | ok (11) |
| accept_norm | inv_mark_points | property | ok | ok (14/100000) | ok (12) |
| turn_c_restore | inv_no_stale_restore_obj | control | ok | ok (18/100000) | ok (11) |
| accept_norm | inv_no_dup_gen | property | ok | ok (14/100000) | ok (12) |
| accept_norm | inv_no_write_over_unreadable | property | ok | ok (14/100000) | ok (12) |
| accept_norm | inv_503_means_nothing_accepted | property | violated | violated (14/100000) | violated (12) |
| accept_norm | wit_store_down_reached | witness | violated | violated (14/100000) | violated (12) |
| accept_norm | wit_503_with_mark_then_same | witness | violated | violated (14/100000) | violated (12) |
| accept_norm | wit_mark_set | witness | violated | violated (14/100000) | violated (12) |
| accept_m_norepeat | inv_no_dup_gen | mutant | violated | violated (14/100000) | violated (12) |
| accept_m_absent | inv_no_write_over_unreadable | mutant | violated | violated (14/100000) | violated (12) |
| accept_m_markfirst | inv_mark_points | mutant | violated | violated (14/100000) | violated (12) |
| locks_text | inv_r2_wait_le_deadline | property | violated | violated (20/100000) | violated (14) |
| locks_text | inv_e2_wait_le_deadline | property | ok | ok (20/100000) | ok (14) |
| locks_text | inv_section_bounded | property | violated | violated (20/100000) | violated (14) |
| locks_text | wit_freeze_blocks_then_calledoff | witness | violated | violated (20/100000) | violated (14) |
| locks_text | wit_r2_waits_long | witness | violated | violated (20/100000) | violated (14) |
| locks_text | inv_no_stale_after_release | property | ok | ok (20/100000) | ok (14) |
| locks_text | wit_e2_waits_nonzero | witness | violated | violated (20/100000) | violated (14) |
| locks_text | wit_e2_wait_tight | witness | violated | violated (20/100000) | violated (14) |
| locks_text | wit_section_io_alive_old | witness | violated | violated (20/100000) | violated (14) |
| locks_dep30 | wit_frozen_then_e2_refused | witness | violated | violated (20/100000) | violated (14) |
| locks_dep30 | inv_e2_wait_le_deadline | property | ok | ok (20/100000) | ok (14) |
| locks_dep120 | inv_e2_wait_le_deadline | property | ok | ok (20/100000) | ok (14) |
| locks_text | wit_frozen_then_e2_refused | control | ok | ok (20/100000) | ok (14) |
| locks_c_budget | wit_r2_refused_by_budget | witness | violated | violated (20/100000) | violated (14) |
| locks_c_budget | wit_r2_budget_tight | witness | violated | violated (20/100000) | violated (14) |
| locks_c_budget | inv_r2_wait_le_deadline | control | ok | ok (20/100000) | ok (14) |
| locks_c_budget | inv_section_bounded | control | ok | ok (20/100000) | ok (14) |
| locks_m_nocalloff | inv_e2_wait_le_deadline | mutant | violated | violated (20/100000) | violated (14) |
| locks_c_budget | inv_no_stale_after_release | property | ok | ok (20/100000) | ok (14) |
| locks_m_release | inv_no_stale_after_release | mutant | violated | violated (20/100000) | violated (14) |
| parts_text | inv_claim_complete | property | violated | violated (14/100000) | violated (14) |
| parts_text | wit_claim_after_failed_part | witness | violated | violated (14/100000) | violated (14) |
| parts_text | inv_answer_by_deadline | property | ok | ok (14/100000) | ok (14) |
| parts_text_slow | inv_answer_by_deadline | property | violated | violated (14/100000) | violated (14) |
| parts_text_slow | wit_past_deadline_running | witness | violated | violated (14/100000) | violated (14) |
| parts_text_slow | inv_answered_within | property | violated | violated (14/100000) | violated (14) |
| parts_text_slow | wit_claim_past_deadline | witness | violated | violated (14/100000) | violated (14) |
| parts_incremental_abort | inv_no_mixed_visible | property | violated | violated (14/100000) | violated (14) |
| parts_text | inv_answered_within | property | ok | ok (14/100000) | ok (14) |
| parts_incremental_abort | inv_claim_complete | property | ok | ok (14/100000) | ok (14) |
| parts_incremental_abort | wit_part_failed_then_mix | witness | violated | violated (14/100000) | violated (14) |
| parts_incremental_abort | wit_abort_clean | witness | violated | violated (14/100000) | violated (14) |
| parts_c_fetchfirst | inv_claim_complete | control | ok | ok (14/100000) | ok (14) |
| parts_c_fetchfirst | inv_no_mixed_visible | control | ok | ok (14/100000) | ok (14) |
| parts_c_fetchfirst | wit_claim_full | witness | violated | violated (14/100000) | violated (14) |
| parts_c_fetchfirst | inv_answer_by_deadline | control | ok | ok (14/100000) | ok (14) |
| parts_c_fetchfirst_slow | inv_answer_by_deadline | control | ok | ok (14/100000) | ok (14) |
| parts_c_fetchfirst_slow | wit_refusal_before_deadline | witness | violated | violated (14/100000) | violated (14) |
| parts_c_fetchfirst_slow | inv_answered_within | control | ok | ok (14/100000) | ok (14) |
| turn_norm | wit_takeover_conflict | witness | violated | violated (18/2000000) | violated (11) |
| parts_c_fetchfirst | inv_answered_within | control | ok | ok (14/100000) | ok (14) |
| parts_m_claimearly | inv_claim_complete | mutant | violated | violated (14/100000) | violated (14) |
| parts_c_fetchfirst_slow | wit_claim_full | control | ok | ok (14/100000) | ok (14) |
| gc_text_memory | inv_no_gc_under_young_fetch | property | violated | violated (24/100000) | violated (16) |
| gc_text_memory | wit_restart_gc_read | witness | violated | violated (24/100000) | violated (16) |
| gc_c_durable | wit_gc_happens | witness | violated | violated (24/100000) | violated (16) |
| gc_m_ignore | inv_no_gc_under_young_fetch | mutant | violated | violated (24/100000) | violated (16) |
| gather_text | inv_deleted_not_returned | property | violated | violated (8/100000) | violated (8) |
| gather_text | wit_del_move_back | witness | violated | violated (8/100000) | violated (8) |
| gc_c_durable | inv_no_gc_under_young_fetch | control | ok | ok (24/100000) | ok (16) |
| gather_text | wit_merge_reachable | witness | violated | violated (8/100000) | violated (8) |
| gather_one_move | inv_deleted_not_returned | property | ok | ok (8/100000) | ok (8) |
| gather_m_ignore | inv_deleted_not_returned | mutant | violated | violated (8/100000) | violated (8) |
| gather_c_keep | inv_deleted_not_returned | control | ok | ok (8/100000) | ok (8) |
| hold_j0_checker_behind60 | inv_hold_covers_token | property | violated | violated (12/100000) | violated (12) |
| hold_j60_checker_true | inv_hold_covers_token | property | violated | violated (12/100000) | violated (12) |
| hold_j0_slow | inv_hold_covers_token | property | ok | ok (12/100000) | ok (12) |
| hold_j600 | inv_hold_covers_token | property | violated | violated (12/100000) | violated (12) |
| hold_j600_anytime | inv_hold_covers_token | property | violated | violated (12/100000) | violated (12) |
| hold_m_noskew | inv_hold_covers_token | mutant | violated | violated (12/100000) | violated (12) |
| hold_j600 | wit_jump_free_alive | witness | violated | violated (12/100000) | violated (12) |
| hold_c_q6 | inv_hold_covers_token | control | ok | ok (12/100000) | ok (12) |
| hold_j0_slow | wit_free_after_issue | witness | violated | violated (12/100000) | violated (12) |
| books_nojump | inv_assembly_after_real_window | property | ok | ok (12/100000) | ok (12) |
| books_forward | inv_assembly_after_real_window | property | violated | violated (12/100000) | violated (12) |
| books_back | wit_assembly_blocked_past_3x | witness | violated | violated (12/100000) | violated (12) |
| books_nojump | wit_assembly_blocked_past_3x | control | ok | ok (12/100000) | ok (12) |
| rev_nojump | wit_waited | witness | violated | violated (12/100000) | violated (12) |
| rev_nojump | inv_wait_le_skew | property | ok | ok (12/100000) | ok (12) |
| rev_nojump | wit_waited_tight | witness | violated | violated (12/100000) | violated (12) |
| rev_jump_big | inv_wait_le_skew | property | violated | violated (12/100000) | violated (12) |
| idem_restart_frequent | inv_cleaned_by_2keep | property | violated | violated (20/100000) | violated (14) |
| idem_restart_frequent | inv_not_early | property | ok | ok (20/100000) | ok (14) |
| idem_restart_frequent | wit_full_stale_past_keep | witness | violated | violated (20/100000) | violated (14) |
| idem_restart_rare | wit_cleaned | witness | violated | violated (20/100000) | violated (14) |
| quiet_restart_frequent | inv_cleaned_by_2keep | property | violated | violated (20/100000) | violated (14) |
| idem_restart_rare | inv_cleaned_by_2keep | property | ok | ok (20/100000) | ok (14) |
| idem_c_survive | inv_cleaned_by_2keep | control | ok | ok (20/100000) | ok (14) |
| idem_m_early | inv_not_early | mutant | violated | violated (20/100000) | violated (14) |
| storm_text | inv_whole_srv_le_rate | property | violated | violated (10/100000) | violated (10) |
| quiet_restart_rare | inv_cleaned_by_2keep | property | ok | ok (20/100000) | ok (14) |
| storm_text | inv_camera_admitted | property | ok | ok (10/100000) | ok (10) |
| storm_text | inv_sigwork_le_rate | property | violated | violated (10/100000) | violated (10) |
| storm_text | wit_whole_burst | witness | violated | violated (10/100000) | violated (10) |
| storm_text | wit_camera_refused_with_sig | witness | violated | violated (10/100000) | violated (10) |
| storm_c_servers | inv_whole_srv_le_rate | control | ok | ok (10/100000) | ok (10) |
| storm_m_nothreshold | inv_camera_admitted | mutant | violated | violated (10/100000) | violated (10) |
| turn_m_get_after | inv_no_overwrite | mutant | violated | violated (18/2000000) | violated (11) |


Перед итоговой пачкой пробные расхождения сняты и записаны в `trial-mismatches.tsv` (26 строк с причиной): 2 строки редкой перестановки в случайной симуляции при 100 000 выборок (для этих двух свойств подняты выборки до 2 000 000); 2 строки тупика Apalache, ошибочно засчитанного как нарушение, в модели без холостого шага (добавлен шаг, разбор вывода исправлен); 22 строки потери сервера Apalache («Connection dropped»). По сообщению координатора причиной потерь был OOM на CT 103 (15 убийств 23:38–00:01 UTC); мои два сервера по 4 ГБ работали в это окно, поэтому этот прогон мог быть частью нагрузки. После предела Архитектора остаток посчитан на одном сервере порта 18825, строго последовательно: досчитана одна строка `r004-a` (ok, 36,5 с). Посчитанные строки при досчёте не менялись.

## Мутанты и контроли

Мутанты с ожидаемым нарушением: 15 экземпляров × 2 инструмента = 30/30 пойманы.

| Мутант | Что сломано | Что поймано |
|---|---|---|
| turn_m_nobump | барьер не меняет версию (`turn:81`) | позднее применение старой записи, `inv_no_late_apply` |
| turn_m_blind | после неизвестного исхода работа без барьера | переупорядочение записей, `inv_no_reorder` |
| turn_m_get_after | `get_at` после подтверждающего CAS (запрет `08.10:101`) | перезапись новой активной, `inv_no_overwrite` |
| turn_m_noguard | запись не проверяется guard | `inv_guard` |
| accept_m_norepeat, accept_m_absent, accept_m_markfirst | нет шага 2; нечитаемое как отсутствие; mark раньше объектов | дубликат поколения; генерация поверх; mark без поколения |
| locks_m_nocalloff | нет общего срока заморозки | ожидание за заморозкой сверх 90 с |
| locks_m_release | секция отпускается при живом старом I/O | запись после освобождения |
| parts_m_claimearly | claim сразу после чтения частей | claim без записанных частей |
| gc_m_ignore | чистка не смотрит на выборку | удаление под молодой выборкой |
| gather_m_ignore | merge не читает `removed` | возврат удалённого имени |
| hold_m_noskew | удержание без `TOKEN_SKEW` | имя свободно при живом токене без скачка |
| idem_m_early | чистка при половине `IDEM_KEEP` | раннее удаление |
| storm_m_nothreshold | нет порога `busy` | допущено камер сверх порога |

Контроли (все ok): `turn_c_drain`, `turn_c_restore`, `locks_c_budget`, `parts_c_fetchfirst`, `parts_c_fetchfirst_slow`, `gc_c_durable`, `gather_c_keep`, `hold_c_q6`, `idem_c_survive`, `storm_c_servers`, а также отрицательные на тексте: `locks_text wit_frozen_then_e2_refused` (при зависшем держателе общей стороны заморозка не наступает), `books_nojump wit_assembly_blocked_past_3x`. Контроли, закрывающие дыру, — проверка предлагаемого исправления, а не утверждение, что норма так написана; `locks_c_budget inv_section_bounded` верен по построению (рестарт принят как допущение), `secAge` — абстрактные шаги, а не секунды.

Невакуумность: свидетели порядка показаны в трассах (`runs/`); привязка ограничений к завершённым действиям — `e2Wait`, `r2Wait` и `answerAt` фиксируются при выдаче, отказе или claim, рядом со свидетелями `wit_e2_wait_tight`, `wit_r2_budget_tight`, `wit_waited_tight`, `wit_claim_past_deadline`, `wit_refusal_before_deadline`, чтобы свойство не было истинным только в простаивающем состоянии.

## Что подтвердило, сняло или уточнило находки

Снятых находок нет. Уточнения сужают отдельные формулировки; счёт замороженного отчёта не меняется.

- **С3 подтверждена, уточнена.** Мьютекс участника: ждущий сверх линейки 90 с при зависшей зависимости (нет срока в тексте P/08; следствие отсутствия нормы, модель это фиксирует, а не открывает). Уточнение: новые правки за ожидающей заморозкой ждут не больше общего срока 90 с (`08.8:299`, `08.8:308`), граница плотная (`wit_e2_wait_tight`), в том числе при зависшем навсегда держателе общей стороны; формулировка отчёта «копится за заморозкой» — не без границы. Без срока остаётся держание общей стороны и мьютекса самим владельцем (`prod:9`, `prod:11`: обязанность объявить бюджет). По секции `08.8:385`: она не отпускается, пока старый I/O может писать, и текст P/08 не даёт срока; мутант «отпустить по таймауту» ломает исключение записи, поэтому конечный бюджет здесь достижим только завершением процесса (срок остановки и `prod:11`). Напряжение норм названо, решения модель не предлагает.
- **С4 подтверждена, сужена.** Принятая работа при SIGTERM остаётся без исхода (`inv_no_drop` нарушено). Сужение: старая запись после освобождения отказывается guard — вреда данным нет (`inv_guard`, свидетель порядка `wit_sigterm_inflight_refused`). Итог находки — срок и исход клиенту, не целостность. Контроль слива `turn_c_drain` закрывает потерю исхода, но слив не норма на срезе.
- **С6 подтверждена, сужена.** Исход неполного чтения и срока после шага 5 не назван. Ветка с пропуском части приводит к неполному claim, что противоречит `08.8:463` (`parts_text`, это ветка трактовки молчания, а не требование текста); ветка с остановкой при пошаговой записи оставляет смешанное состояние, которое видно только у обслуживающего держателя, то есть в исключении split (`08.8:408`, `08.8:810`) — у обычной цели state не обслуживается до claim, поэтому формулировка «частичный откат доменного состояния» относится к split. Предложение С6 (сначала прочитать всё) закрывает эти два случая и даёт определённый ответ до срока; контроль не покрывает сбой записи state внутри шага 7. При суммарном времени чтения выше 90 с (`PART_S` 40 × 3) текст доводит claim после срока (`inv_answered_within`), контроль завершает отказом (`parts_c_fetchfirst_slow`); само превышение — арифметика параметров среды.
- **С7 подтверждена как находка о пробе.** Второй переезд: удалённое имя возвращается, предел назван самой нормой (`08.8:517`, `08.8:923`); без второго переезда свойство держится. Учёт выборки (`08.8:203`, М3): при учёте в памяти и рестарте держателя часть удаляется под молодой выборкой (`gc_text_memory`), при устойчивом учёте — нет; место учёта норма не называет. `PARTIAL_QUIET` при рестартах чаще 3 ч молчанием не закрывается (`08.8:541`), выход — слово оператора. Модель не заменяет пробу.
- **С13 подтверждена** (по определению текста): `busy` после подписи и только для камер, работа подписи за секунду превышает порог, серверы не ограничены; камеры допускаются не больше порога (`acc:217`, `acc:218`, `acc:219`).
- **С14 подтверждена в форме, не в объёме**: первые целые отчёты серверов одной секундой превышают порог при одновременном прибытии (`08.1:101`, `acc:218`); разброс проходов P/09.1 N1.2a не читался и не моделировался.
- **С15, С18 подтверждены как находки о пробе; норма по модели держится.** При недоступности store и неизвестном исходе свойства порядка выполняются (`inv_mark_points`, `inv_no_dup_gen`, `inv_no_write_over_unreadable`, `inv_no_late_apply`, `inv_no_reorder`, `inv_no_overwrite`), мутанты ловятся; 503 при применённой метке достижимо и разрешено текстом (`08.3:704`), повтор даёт same или heard без второго поколения. Модель не заменяет отсутствующую пробу приёмки.
- **С16 подтверждена, уточнена.** Скачок вперёд освобождает имя при живом токене (`hold_j60_checker_true` при J=60, `hold_j600`), окно книг закрывается раньше (`books_forward`), обратный скачок держит окно дольше (`books_back`), ожидание смены ключа после скачка и коррекции равно величине скачка (`rev_jump_big`) при границе `TOKEN_SKEW`+2 без скачка. Уточнение: при отстающем на 60 с проверяющем токен живёт после удержания и без скачка (`hold_j0_checker_behind60`), запас `TOKEN_SKEW` один; посылка `08.2:83` — про часы держателей, про часы проверяющего норма говорит только допуском (`token:45`). Контроль Q6 закрывает только скачок после метки; токен, выданный в момент скачка, этим контролем не проверялся.
- **М5 подтверждена.** Раннего удаления нет (`inv_not_early`), при рестартах чаще `IDEM_KEEP` строка не чистится до 2×`IDEM_KEEP`, а новые ключи получают 503 на потолке (`wit_full_stale_past_keep`, малая размерность потолка); редкие рестарты и контроль сохранения возраста чистят.
- **Новое наблюдение модели (не входит в счёт, кандидат на уточнение):** запись объектов копии при восстановлении идёт «by value» (`08.8:484`), а правило `get_at`/CAS/`put_at` для изменяемых объектов (`08.10:98`) называет запись прохода и двери приёма, не восстановление. Секция восстановления локальна для процесса (`08.8:385`), поэтому два процесса могут восстанавливать одновременно: старая запись объекта затирает новую (`inv_no_stale_restore_obj` нарушено, контроль условной записи держит). Нарушение относится к объектам без условной записи; строки защищены guard.

## Не вошло (причина)

- С1, С2, С8–С12, С17, С19, С20, М4, М6: статичные бюджеты, стоимость, размер, форма, связность документов — нет порядка событий, модель ничего не добавляет.
- С5 (режим записи частей и порядок относительно головы), М1 (кадрирование), М2 (занятый порт): не моделировались — С5 требует модели записи объектов частями с конфликтами, М1 и М2 статичны; остаются чтением и пробой.
- М3 смоделирована только как развилка места учёта (устойчиво или память); где учёт хранится, норма не определена.
- `TURN_TERM`/`TURN_RENEW` как числа, `behind`, смена ключа копии, секреты, relay-батчи, `road_quiet`, разброс P/09.1 не входят.

## Допущения и пределы

- Результат «нарушение» — следствие текста норм при перечисленных допущениях; результат «ok» — проверка до указанной границы (Apalache) или на случайных выборках (rust), не доказательство без границы.
- Малая размерность (2 процесса, 3 части, порог 2, потолок 2) и скачки времени выбраны для проверки порядка событий, а не нагрузки; выводы о производительности не делаются.
- Времена среды (`PART_S`, `RESTART_GAP`, величины скачков, `WAIT_BUDGET` 45 в контроле) — параметры модели, не числа норм.
- Часть «подтверждений» С3, С4, С13, М5 фиксирует отсутствие нормы: при выбранном допущении результат близок к определению и не должен читаться как самостоятельное открытие.
- Модель не сравнивает себя со спецификационными моделями других единиц: их не запускал и не читал; упоминания «Quint model of M11» в нормах — часть текста среза, не проверялись.
- Отчёт не заявляет готовности кандидата и не является входом приёмки.

## Ход и отклонения

Пробные пачки (`trial0`, прерванная ошибкой собственной команды, и `trial1`–`trial3`) сохранены вне проекта; итог — `results.tsv`, причины расхождений — `trial-mismatches.tsv`. Выводы Apalache (`_apalache-out`) и временные файлы — вне проекта. После предела Архитектора: один сервер на порту 18825, досчитана одна строка, сервер остановлен. Запретов на чтение не нарушал. При записи первой версии отчёта незаквоченный heredoc подставил обратные кавычки как команды оболочки; ни одна не изменила файлы (`rm` и `pkill` остановились на ошибке отсутствия аргументов, `git status` показывает только свои файлы проекта), версия переписана.

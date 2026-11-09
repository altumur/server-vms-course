adr: 0130 (P/10, Quint)

# Модель Quint боевых свойств P/10 (консоль домена) — review103-claude

Задача P10.5, приём src103-claude. Фаза после независимых находок: автор тот же, независимость не заявляется. Это не вход приёмки кандидата, READY и GATE не заявляются.

- Срез: `cbf02230bf9a6a2cb69fb72bdbee7704b94914f7`. Источник вопросов: собственный замороженный отчёт `РЕВЬЮ-ADR0130-P10-Claude.md`, коммит `db4680b9d`. Он не менялся, его счёт Б1/С15/М5 здесь не пересчитывается.
- Модели — это чтения текста норм при явных допущениях. Нарушение значит: текст допускает такой ход событий при этих допущениях. О реализациях вывода нет.
- Проект: `decisions/inbox/ревью/quint-p10-cbf02230/`: семь моделей `.qnt`, `run.py`, `results.tsv`, `run.log`, `runs/` (62 трассы ITF), `trial-mismatches.tsv`, `check_anchors.py`, копии первой попытки `results-attempt1.tsv` и `run-attempt1.log`.
- Инструменты: Quint 0.33.0, Apalache 0.62.1 (один сервер, порт 18827, `-Xmx4g`, запуски строго по очереди), rust-бэкенд для симуляции. `check_anchors.py`: 52 якоря, 0 неверных на срезе.

**Итог: 99 запусков, совпало 99.** 91 запуск Apalache (`verify`), 8 симуляций rust. По видам: property 17, control 21, witness 49, mutant 12. По исходу: 37 `ok`, 62 `violation`. Таймаутов и неподтверждённых трасс нет; 17 трасс с заявленным порядком событий проверены отдельно по последнему состоянию ITF, все подтвердили порядок.

**Что изменили модели.** Подтверждены С6, С11, С13. Сужены С5, С7, С8, С15; ниже по каждой — что именно. Главное: у застрявшего читателя срок удержания полосы конечен (С5), двойной эффект после 502 есть только у правки без ключа и `If-Match` (С7), для ложного `unreadable` нужны две публикации и чистка внутри одного чтения (С8).

## Как шёл прогон

Прогон состоит из двух частей на одних и тех же файлах: модели и `run.py` не менялись с 01:36:25Z, до первого запуска.

| Часть | Время (UTC, 2026-11-09) | Запуски | Итог |
|---|---|---|---|
| 1 | 01:36:29–01:39:11 | S01–S10, D01–D12 | 22 результата; на E01 сервер перестал отвечать (`ECONNREFUSED`) |
| 2 | 21:17–21:25:31 | E01–Z08 | 77 результатов |

Между частями сервер запущен заново. Строка E01 с `error` была ошибкой связи, а не результатом проверки: она осталась в `run.log` и `results-attempt1.tsv`, а из `results.tsv` убрана перед повторным запуском, иначе `run.py` её пропустил бы. Остальные 22 строки первой попытки не пересчитывались и совпадают побайтово.

Причина обрыва журналами не установлена: журнал сервера заканчивается штатным разбором предыдущего запуска. По времени она совпадает с гибелью прежнего окна при пределе памяти 2 ГиБ, но это предположение.

Поправка к прежним сообщениям: Архитектору я писал «22 из 100, осталось 78». Верно 22 из 99, оставалось 77: мой подсчёт принял `C11` из комментария `run.py` за запуск.

Первый пробный прогон (до основного) дал четыре расхождения, причины и правки — в `trial-mismatches.tsv`:
- D08, J06, J10 — неточности модели (задержка доставки ответа; срок, считавшийся только у застрявшего запроса);
- D11 — пустой инвариант: `exitProc` сам писал `break`, поэтому условие всегда выполнялось; усилено до `clientSaw in {200, 502}`.

## Что смоделировано

Сокращения: `norms` — `Platform/10-domain-console/spec/10-domain-console.norms.md`; `gp`, `fw`, `acc`, `ej`, `prod` — `Platform/common/contracts/{gate-and-pass,forwarding,accept,event-journal,production-obligations}.md`; `080` — `Platform/08-domain/spec/08.0-domain.norms.md`.

| Модель | Находка | Что выражено | Граница |
|---|---|---|---|
| `stream_lane` | С5 | полоса потоков, застрявший читатель, закрытие по `exp`, контрольный срок простоя | 2 слота (256 масштабировано), 3 потока, настоящие 900 с и 5 с |
| `shutdown` | С6 | SIGTERM при пересланной правке и открытом потоке; молчание текста как недетерминизм | одна правка, один поток |
| `edit_after_502` | С7 | заморозка процесса, 502, оттаивание, повтор; ключ, `If-Match`, ни того ни другого | один пользователь, один ключ, две посылки |
| `alarms_mark_race` | С8 | метка, поколение, публикация в два шага, чистка, перечитывание МБ-3 | один член, поколения до 6 |
| `alarms_completeness` | С11 | формула `complete` и исходы истории и свидетелей; не гонка | 2 члена, все в состоянии `ok` |
| `silence_clock` | С13 | шаг настенных часов консоли, один или два бокса | 2 члена, один шаг |
| `journal_lock` | С15 | `flock`, застрявший держатель, ошибка ввода-вывода, исход двери | 2 запроса, 1 внешний держатель |

Константы из норм: `TOKEN_LIFETIME` 900, `PASS_TICKET_CHECK` 5, `FORWARD_WAIT` 5, `REPORT_EVERY` 5, `LOST_AFTER` 45. Параметры модели, а не предлагаемые числа: контрольный срок простоя 30, бюджет остановки 6, бюджет замка 30, зазор двери 4, 10 и 20.

## Что подтвердило, сняло, уточнило находки

### С5 сужена: срок удержания конечен

Слово «бессрочно» в заголовке С5 не подтверждается: сам `gp:615` закрывает поток по `exp`. При настоящих константах застрявший читатель не держит слот дольше 905 с (S02, 12 шагов; S03). Мутант без правила `exp` удерживает дольше (S09), то есть границу задаёт именно это правило.

Остаётся: срока простоя нет, слот занят до `exp`. Удержание дольше половины срока (450 с) достижимо (S04), вся полоса застрявших отказывает новому клиенту (S05), поток закрывается по `exp` после почти всего срока (S06). Контрольное правило со сроком простоя даёт границу 35 при параметре 30 (S07, S08).

Допущения: токен свежий на момент открытия, проверка `exp` применяется и к застрявшему потоку, продления билета нет, `TOKEN_SKEW` не учтён (иначе граница больше на 60 с). Повторное открытие тем же клиентом после `exp` не моделировалось, а удерживать полосу дольше можно именно так.

### С6 подтверждена, добавлено условие на бюджет

Текст допускает и обрыв клиенту при уже применённой правке (D02), в обоих порядках (D03, D04), и остановку без границы, в том числе на открытом потоке (D05, D06). Эти запуски показывают только, что текст этого не исключает: молчание нормы закодировано недетерминизмом.

Новое здесь — результат контроля: слив и бюджет дают ответ клиенту и ограниченный выход (D07–D10), но при бюджете ниже `FORWARD_WAIT` правка снова обрывается (мутант D11, D12). Значит, если норма появится, бюджет остановки должен быть больше `FORWARD_WAIT`. При равенстве выход и 502 сталкиваются в один момент, поэтому контроль взят с 6 при 5. Контроль также предполагает, что готовый ответ пересылается сразу.

### С7 сужена: двойной эффект только без ключа и `If-Match`

- С `Idempotency-Key` эффект один (E01, 14 шагов), повтор получает прежний ответ (E11) или 409 в работе (E10).
- С `If-Match` эффект один (E02), повтор получает 412 (E12).
- Без того и другого повтор даёт два эффекта (E08, E09). Это прямое следствие `080:130` («a repeat is a new write»), а не дефект связки. Без повтора эффект один (E03).

Подтверждено, что проба нужна: применение после 502 достижимо (E06, E16), как и 502 без применения (E07), и клиент эти случаи различить не может. Мутанты без памяти и без пакета дают два эффекта (E13, E14).

Не проверено: истечение памяти ответа и переезд держателя (`080:156`, память не переносится). Именно там повтор с ключом может потерять защиту. E04 и E05 не несут сведений о норме: поздний ответ и ранний 502 исключены построением модели; мутант E15 показывает лишь, что инвариант способен нарушиться.

### С8 уточнена: нужны две публикации внутри чтения

На одном тексте P/10 ложный `unreadable` достижим (A01, A02 с проверкой порядка: две новые метки после чтения, чистка, промах; A04 при `every` = 1).

Сценарий С8 в замороженном отчёте неточен: одной публикации мало, чистка хранит два последних поколения (`acc:376`). Нужно, чтобы метка сдвинулась дважды за одно чтение. При зазоре 4 с и `REPORT_EVERY` 5 с за чтение сдвигается не больше одной метки и ложного вывода нет (A03, A19, 14 шагов). Граница проверена только в точках 4 и 10 с; значение между ними не исследовано. Связка с С1 сохраняется: чем дольше собирается дверь, тем вероятнее гонка.

С перечитыванием МБ-3 (`acc:378`) ложного `unreadable` нет (A05, 20 шагов, с настоящей потерей объекта), перечитывание одно (A06), страница называет своё поколение (A07), сдвинувшаяся метка не даёт `unreadable` (A08). Достижимы 503 (A09), свежая страница (A10) и настоящий `unreadable` (A11). Четыре мутанта ломают свойство (A13–A16).

Допущение: исход `silent` из `acc:378` перенесён на `unreadable` двери P/10, а сдвинувшаяся метка даёт 503, как предлагает С8.

### С11 подтверждена и уточнена

При `complete = all ok` (`norms:442`) ответ `complete: true` достижим при неизвестном исходе чтения истории (C02), при нечитаемой истории (C03) и в общем виде (C01). Это прямое следствие формулы, а не гонка.

Уточнение: 503 на неизвестное чтение одной проблемы не закрывает: названные исходы всё равно теряются молча (контроль C05 нарушен, C06 при этом закрывает только сам неизвестный случай). Закрывает учёт отброшенного в `complete` (C07), и `complete: true` остаётся достижимым (C08, C04).

### С13 подтверждена, найден порог

Шаг часов консоли вперёд даёт массовую ложную тишину (K01, K02). Порог: 40 с безопасно (K07), 41 с нет (K08), то есть `LOST_AFTER − REPORT_EVERY`.

На разных боксах ложная тишина длится, пока не исправлены часы (K03, K13). На одном боксе она проходит за один период отчёта (K09), но возникает (K10). Шаг назад скрывает настоящую тишину в обоих случаях (K11, K12). Без шага ложных выводов нет (K04–K06).

Порог зависит от допущения, что живой член успевает с отчётом за `REPORT_EVERY`, без дрожания.

### С15 сужена: при общем бюджете остаётся только исход двери

Без бюджета ожидание не ограничено и застрявший держатель блокирует оба запроса (J01, J02). Но `ej:222` ссылается на общие бюджеты, а `prod:9`, `prod:11` требуют конечного ожидания и удержания замка. Если эта ссылка действует для P/10, ожидание ограничено (J06), и часть С15 про срок замка сводится к М1 (P/10 не подключает общие бюджеты).

Остаётся то, чего нет в тексте: что отвечает дверь при сбое журнала. Ответ 403 с потерянной строкой журнала достижим и без бюджета (J03, J04), и с ним (J07, J08). Контроль с названным исходом 503 потери не даёт (J09, J10, J13), мутант с необеспеченным бюджетом ломает границу (J11).

## Мутанты и контроли

12 мутантов, все нарушили ожидаемое свойство: S09, S10, D11, D12, E13, E14, E15, A13, A14, A15, A16, J11. 21 контроль. Контроль C05 ожидаемо нарушен, он показывает недостаточность частичной правки; остальные дают ожидаемый исход.

## Таблица прогонов

Полностью с параметрами — `results.tsv`. `violation` у property и witness значит: текст допускает ход событий при допущениях. У вида witness нарушение и есть цель запуска.

| id | модуль | инвариант | вид | инстр. | шаги | ожидание | факт | с |
|---|---|---|---|---|---|---|---|---|
| S01 | stream_norm | inv_lane_cap | property | apalache | 8 | ok | ok | 2.6 |
| S02 | stream_norm | inv_stalled_hold_bounded | property | apalache | 12 | ok | ok | 124.1 |
| S03 | stream_norm | inv_open_hold_bounded | property | apalache | 8 | ok | ok | 6.5 |
| S04 | stream_norm_h450 | inv_stalled_hold_bounded | witness | apalache | 8 | violation | violation | 1.0 |
| S05 | stream_norm | wit_lane_full_of_stalled_refuses | witness | apalache | 8 | violation | violation | 1.3 |
| S06 | stream_norm | wit_stalled_closed_by_exp | witness | apalache | 8 | violation | violation | 1.1 |
| S07 | stream_ctrl_term | inv_stalled_hold_bounded | control | apalache | 8 | ok | ok | 10.4 |
| S08 | stream_ctrl_term | wit_stalled_closed_by_term | witness | apalache | 8 | violation | violation | 1.1 |
| S09 | stream_mut_noexp | inv_stalled_hold_bounded | mutant | apalache | 8 | violation | violation | 1.1 |
| S10 | stream_mut_nocap | inv_lane_cap | mutant | apalache | 8 | violation | violation | 0.9 |
| D01 | shutdown_norm | inv_no_early_502 | property | apalache | 10 | ok | ok | 1.3 |
| D02 | shutdown_norm | inv_no_break_on_applied | witness | apalache | 8 | violation | violation | 0.9 |
| D03 | shutdown_norm | wit_term_break_then_applied | witness | apalache | 8 | violation | violation | 0.9 |
| D04 | shutdown_norm | wit_applied_then_term_break | witness | apalache | 8 | violation | violation | 1.0 |
| D05 | shutdown_norm | inv_stop_bounded | witness | apalache | 8 | violation | violation | 1.0 |
| D06 | shutdown_norm | wit_stop_hangs_on_stream | witness | apalache | 8 | violation | violation | 1.0 |
| D07 | shutdown_ctrl | inv_stop_bounded | control | apalache | 10 | ok | ok | 1.3 |
| D08 | shutdown_ctrl | inv_no_break_on_applied | control | apalache | 10 | ok | ok | 1.6 |
| D09 | shutdown_ctrl | inv_edit_answered_at_exit | control | apalache | 10 | ok | ok | 1.4 |
| D10 | shutdown_ctrl | wit_drained_exit | witness | apalache | 10 | violation | violation | 1.0 |
| D11 | shutdown_mut_short | inv_edit_answered_at_exit | mutant | apalache | 10 | violation | violation | 1.0 |
| D12 | shutdown_mut_short | inv_no_break_on_applied | mutant | apalache | 10 | violation | violation | 1.0 |
| E01 | edit502_keyed | inv_one_effect | property | apalache | 14 | ok | ok | 15.0 |
| E02 | edit502_ifmatch | inv_one_effect | property | apalache | 12 | ok | ok | 6.8 |
| E03 | edit502_bare_noretry | inv_one_effect | property | apalache | 12 | ok | ok | 4.4 |
| E04 | edit502_keyed | inv_no_late_answer | property | apalache | 12 | ok | ok | 7.0 |
| E05 | edit502_keyed | inv_502_not_early | property | apalache | 12 | ok | ok | 19.7 |
| E06 | edit502_keyed | wit_applied_after_502 | witness | apalache | 10 | violation | violation | 2.2 |
| E07 | edit502_keyed | wit_502_never_applied | witness | apalache | 10 | violation | violation | 1.9 |
| E08 | edit502_bare | wit_double_effect_after_502 | witness | apalache | 12 | violation | violation | 3.2 |
| E09 | edit502_bare | inv_one_effect | witness | apalache | 12 | violation | violation | 2.8 |
| E10 | edit502_keyed | wit_retry_409_in_flight | witness | apalache | 12 | violation | violation | 2.3 |
| E11 | edit502_keyed | wit_retry_replay_one_effect | witness | apalache | 12 | violation | violation | 3.7 |
| E12 | edit502_ifmatch | wit_retry_412 | witness | apalache | 12 | violation | violation | 5.0 |
| E13 | edit502_mut_nomem | inv_one_effect | mutant | apalache | 12 | violation | violation | 3.1 |
| E14 | edit502_mut_nobatch | inv_one_effect | mutant | apalache | 12 | violation | violation | 4.2 |
| E15 | edit502_mut_late | inv_no_late_answer | mutant | apalache | 12 | violation | violation | 2.4 |
| E16 | edit502_bare_noretry | wit_applied_after_502 | witness | apalache | 10 | violation | violation | 2.0 |
| A01 | alarmrace_norm | inv_no_false_unreadable | witness | apalache | 12 | violation | violation | 1.8 |
| A02 | alarmrace_norm | wit_false_unreadable_ordered | witness | apalache | 12 | violation | violation | 1.8 |
| A03 | alarmrace_norm_shortgap | inv_no_false_unreadable | property | apalache | 14 | ok | ok | 7.1 |
| A04 | alarmrace_norm_every1 | inv_no_false_unreadable | witness | apalache | 12 | violation | violation | 1.8 |
| A05 | alarmrace_ctrl | inv_no_false_unreadable | control | apalache | 20 | ok | ok | 183.4 |
| A06 | alarmrace_ctrl | inv_reread_once | control | apalache | 16 | ok | ok | 10.7 |
| A07 | alarmrace_ctrl | inv_page_named | control | apalache | 16 | ok | ok | 22.8 |
| A08 | alarmrace_ctrl | inv_changed_never_unreadable | control | apalache | 16 | ok | ok | 11.4 |
| A09 | alarmrace_ctrl | wit_503_changed_marker | witness | apalache | 18 | violation | violation | 4.0 |
| A10 | alarmrace_ctrl | wit_fresh_after_reread | witness | apalache | 12 | violation | violation | 1.7 |
| A11 | alarmrace_ctrl | wit_genuine_unreadable | witness | apalache | 8 | violation | violation | 1.5 |
| A12 | alarmrace_norm | inv_page_named | property | apalache | 12 | ok | ok | 3.3 |
| A13 | alarmrace_mut_keep1 | inv_no_false_unreadable | mutant | apalache | 10 | violation | violation | 1.5 |
| A14 | alarmrace_mut_nocmp | inv_no_false_unreadable | mutant | apalache | 18 | violation | violation | 27.2 |
| A15 | alarmrace_mut_loop | inv_reread_once | mutant | apalache | 10 | violation | violation | 1.6 |
| A16 | alarmrace_mut_markfirst | inv_no_false_unreadable | mutant | apalache | 8 | violation | violation | 1.5 |
| A17 | alarmrace_norm | wit_page_served | witness | apalache | 6 | violation | violation | 1.4 |
| A18 | alarmrace_norm_shortgap | wit_one_mark_in_gap | witness | apalache | 8 | violation | violation | 1.5 |
| A19 | alarmrace_norm_shortgap | inv_at_most_one_mark_in_gap | property | apalache | 14 | ok | ok | 7.7 |
| C01 | alarmcomp_norm | inv_complete_is_whole | witness | apalache | 6 | violation | violation | 0.7 |
| C02 | alarmcomp_norm | wit_complete_with_unknown_history | witness | apalache | 6 | violation | violation | 0.7 |
| C03 | alarmcomp_norm | wit_complete_with_unreadable_history | witness | apalache | 6 | violation | violation | 0.7 |
| C04 | alarmcomp_norm | wit_complete_true_reachable | witness | apalache | 6 | violation | violation | 0.7 |
| C05 | alarmcomp_ctrl_unk503 | inv_complete_is_whole | control | apalache | 6 | violation | violation | 0.7 |
| C06 | alarmcomp_ctrl_unk503 | wit_complete_with_unknown_history | control | apalache | 6 | ok | ok | 0.8 |
| C07 | alarmcomp_ctrl_field | inv_complete_is_whole | control | apalache | 6 | ok | ok | 0.9 |
| C08 | alarmcomp_ctrl_field | wit_complete_true_reachable | witness | apalache | 6 | violation | violation | 0.7 |
| K01 | clock_sep | inv_no_false_silent | witness | apalache | 6 | violation | violation | 0.7 |
| K02 | clock_sep | wit_mass_false_silent | witness | apalache | 6 | violation | violation | 0.8 |
| K03 | clock_sep | wit_false_silent_persists | witness | apalache | 8 | violation | violation | 1.0 |
| K04 | clock_nojump | inv_no_false_silent | control | apalache | 8 | ok | ok | 1.3 |
| K05 | clock_nojump | inv_no_false_ok | control | apalache | 8 | ok | ok | 1.2 |
| K06 | clock_nojump | wit_true_silent_seen | witness | apalache | 8 | violation | violation | 0.8 |
| K07 | clock_sep_40 | inv_no_false_silent | control | apalache | 8 | ok | ok | 2.3 |
| K08 | clock_sep_41 | inv_no_false_silent | witness | apalache | 8 | violation | violation | 0.8 |
| K09 | clock_co | inv_false_silent_transient | property | apalache | 10 | ok | ok | 4.9 |
| K10 | clock_co | inv_no_false_silent | witness | apalache | 8 | violation | violation | 0.7 |
| K11 | clock_co_back | wit_false_ok_hides_silence | witness | apalache | 8 | violation | violation | 0.8 |
| K12 | clock_sep_back | wit_false_ok_hides_silence | witness | apalache | 8 | violation | violation | 0.9 |
| K13 | clock_sep | inv_false_silent_transient | witness | apalache | 8 | violation | violation | 1.0 |
| J01 | journal_norm | inv_wait_bounded | witness | apalache | 8 | violation | violation | 1.2 |
| J02 | journal_norm | wit_stuck_blocks_both | witness | apalache | 8 | violation | violation | 1.3 |
| J03 | journal_norm | inv_no_silent_loss | witness | apalache | 8 | violation | violation | 1.2 |
| J04 | journal_norm | wit_io_then_403_lost | witness | apalache | 8 | violation | violation | 1.2 |
| J05 | journal_norm | wit_line_written_answered | witness | apalache | 8 | violation | violation | 1.1 |
| J06 | journal_budget | inv_wait_bounded | property | apalache | 10 | ok | ok | 15.2 |
| J07 | journal_budget | inv_no_silent_loss | witness | apalache | 10 | violation | violation | 1.2 |
| J08 | journal_budget | wit_timeout_then_403_lost | witness | apalache | 10 | violation | violation | 1.5 |
| J09 | journal_ctrl | inv_no_silent_loss | control | apalache | 10 | ok | ok | 9.7 |
| J10 | journal_ctrl | inv_wait_bounded | control | apalache | 12 | ok | ok | 34.2 |
| J11 | journal_mut_unenforced | inv_wait_bounded | mutant | apalache | 10 | violation | violation | 1.1 |
| J12 | journal_ctrl | wit_line_written_answered | witness | apalache | 8 | violation | violation | 1.2 |
| J13 | journal_ctrl | wit_timeout_503 | witness | apalache | 10 | violation | violation | 1.4 |
| Z01 | stream_norm | inv_stalled_hold_bounded | property | rust | 25 | ok | ok | 1.3 |
| Z02 | shutdown_ctrl | inv_no_break_on_applied | control | rust | 25 | ok | ok | 1.2 |
| Z03 | edit502_keyed | inv_one_effect | property | rust | 25 | ok | ok | 2.1 |
| Z04 | alarmrace_norm_shortgap | inv_no_false_unreadable | property | rust | 25 | ok | ok | 1.5 |
| Z05 | alarmrace_ctrl | inv_no_false_unreadable | control | rust | 25 | ok | ok | 1.4 |
| Z06 | clock_nojump | inv_no_false_silent | control | rust | 25 | ok | ok | 1.0 |
| Z07 | journal_ctrl | inv_no_silent_loss | control | rust | 25 | ok | ok | 1.6 |
| Z08 | alarmcomp_ctrl_field | inv_complete_is_whole | control | rust | 12 | ok | ok | 0.6 |

## Не вошло

- Находки Б1, С1–С4, С9, С10, С12, С14, М1–М5 не моделировались. Б1, С1–С4 и С14 говорят об объёме, пределах и страницах, а С9, С10, С12 — о названных исходах и пробах; порядок событий в них не главное. Отдельного обоснования отбора в носителях не сохранилось: это моё чтение состава моделей.
- Внутри С5: повторное открытие после `exp`, продление, `TOKEN_SKEW`, отзыв и `may`.
- Внутри С6: отказ новым запросам при остановке, порт, падение процесса `domain`.
- Внутри С7: истечение памяти ответа, переезд держателя, шаг через консоль кластера, 422 при другом отпечатке.
- Внутри С8: несовпадение sha256 как отдельный путь, дельты, несколько членов.
- Внутри С13: дрожание, дрейф, `silent_after` камеры.
- Внутри С15: журнал тревог, другие двери, порванный хвост файла.

## Допущения и пределы

- Apalache — ограниченный поиск на указанную глубину (6–20 шагов). `ok` значит «не найдено до этой глубины», а не доказательство. Простые инварианты `S01`, `D01`, `E05` обеспечены защитными условиями самой модели и проверяют её согласованность, а не норму.
- Симуляции Z01–Z08 — случайный поиск (3000 выборок), вторичное свидетельство; семя не фиксировано.
- Масштаб: слоты, потоки, запросы и члены уменьшены. Выводы относятся к одному потоку, полосе, члену или запросу, арифметики над 256 нет.
- Числа контролей — параметры модели, новых числовых бюджетов отчёт не предлагает.
- Модели и пробный прогон написаны фоновым агентом предыдущего окна 2026-11-09 до 01:39Z; его бриф недоступен. Этот отчёт написан в окне после перезапуска: семь моделей, `run.py`, `results.tsv` и хвост `run.log` прочитаны целиком, разделы замороженного отчёта — С5–С8, С11, С13, С15 и шапка.
- Норму `gp:615` для застрявшего потока и `acc:378` для P/10 я читал как применимые; это прочтения текста.
- Не читались реализации Source и кандидатов, свидетели, native, runtime, частные судьи и отчёты других рецензентов. Запускались только Quint и Apalache.
- Журнал сервера Apalache второй части (`apalache-server-2.log`) и каталог его вывода лежат в рабочем каталоге прогона вне репозитория и в коммит не входят.
- Хеши sha256 (начало): `stream_lane` `a14fa059`, `shutdown` `25d50c04`, `edit_after_502` `e242cfc4`, `alarms_mark_race` `daa28bf5`, `alarms_completeness` `572feb71`, `silence_clock` `297bca77`, `journal_lock` `883f88ff`, `run.py` `df269b23`.

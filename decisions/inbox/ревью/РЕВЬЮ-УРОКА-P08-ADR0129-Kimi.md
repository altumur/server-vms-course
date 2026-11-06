# РЕВЬЮ-УРОКА-P08-ADR0129-Kimi

Дата: 2026-11-06. Ревьювер: Kimi (второй читатель, доля P/06–P/10 по ADR-0129).

Предмет: урок P/08 (домен) по ADR-0129, пункты (а)–(г). Читался английский
источник `Platform/08-domain/spec/`: главы 08.0–08.10 целиком, README,
forms/README.md и все пять форм (runtime-constants.tsv, daemon-flags.tsv,
stages.tsv, versioned-doors.tsv, refusals.tsv), векторные наборы view,
assemble, issue (README + cases.tsv), acceptance/README. ru/ не читался.
Код и нормы не правились — только чтение.

**Итог: Б 0 / С 1 / М 4.**

## (а) Места догадок и двусмысленности нормы

- **А1 (С): фраза «The named numeric constants above are declared by
  forms/runtime-constants.tsv» в конце каждой главы фактически неверна.**
  Форма объявляет ровно 26 констант (SHADOW_STALL, SHADOW_CLEAN, OLD_KEYS,
  KEEP_OLD, REPORT_EVERY, BODY_LIMIT, ROAD_QUIET, PASSWORD_MIN,
  TOKEN_LIFETIME, LOGIN_BODY, GUARD_RETRIES, ANYWHERE_MAX, GRANT_LIFETIME,
  GROUP_TITLE_MAX, COMMENT_MAX, ROLES_TABLE_MAX, ADMIN_ASSIGNED_MAX,
  ADMIN_TABLE_MAX, GLASS_MIN, DOMAIN_FOLDERS_MAX, KEPT_LIMIT,
  BACKUP_HOLDERS, HANDOVER_WAIT, ENTRY_MAX, IDEM_KEEP, IDEM_MAX). Проза глав
  при этом называет десятки других имён с числами, которых в форме нет и
  которые нигде больше не объявлены. Свои константы P/08 без места объявления:
  VIEW_EVERY (3 s, инлайн в 08.1), VIEW_MEMBERS (2000, «to be measured»,
  08.1), KNOCKS (32, 08.1 и 08.3), BATCH_LIMIT (accept contract), REPORT_RATE
  (200/с, 08.3), SERVERS_MAX (500, нормирован в 08.10 N1.5), MEMBERS_MAX
  (08.10), MISSING_SHOWN (500, 08.5, с требованием «keep it equal to
  SERVERS_MAX»), NEAR_CEILING (419430, 08.5), BOOK_PARTS_SHOWN (64),
  BOOK_PARTS_PASS (8), BOOK_WANT_EVERY (86400), BOOK_WANT_TTL (259200) —
  все в 08.5, UNITS_PAGE_CHECKS (200, 08.5), FOLDERS_MEMBERS_MAX,
  FOLDER_ROW_MAX, FOLDER_NAME_MAX (255, 08.5), OWN_MAX (1 MiB, 08.5),
  BACKUP_EVERY и BACKUP_RATE (1 MiB/s, «to be measured», 08.8), BACKUP_FETCH
  (600, 08.8), PARTIAL_QUIET (10800, 08.8), OUTCOMES_LIMIT (50, 08.6),
  VIA_EDIT_MAX (20, 08.3), REVOKED_WORDS (08.2). Чужие имена (контракты и
  другие уроки — TURN_TERM/TURN_RENEW, TOKEN_HOLDER_BODY/TOKEN_BODY,
  HISTORY_LINES, FRESH_EVERY/SAY_EVERY) фразу тоже не покрывают: читателю
  не сказано, что они объявлены вне урока. MARK_REFRESH намеренно оставлен
  в прозе (заголовок формы: «stays derived in prose») — но и это читатель
  узнаёт только из формы. Генератору приходится догадываться, какие имена
  брать из формы, а какие искать по прозе. Правка: либо внести свои
  константы урока в runtime-constants.tsv (по прецеденту 26 уже там), либо
  заменить фразу на точный перечень («объявленные формой константы этой
  главы — …; прочие именованные числа объявлены инлайн / в контрактах»).
  Отдельный подпункт: **FOLDERS_PER_UNIT_MAX** назван в прозе N1.8 главы
  08.5 без значения, а само значение 8 живёт только в схеме writer
  (`at most 8 items` у `memberof`) — в прозе генератору значения нет
  вообще. Правка: назвать значение в норме или перенести константу в форму.
- **А2 (М): счётчики строк векторов в N5 глав расходятся с cases.tsv.**
  08.1 N5: «45 rows — 28 steps of sc. 01–16, 5 rows 10-*, 10 rows
  17-*…21-*»: сумма частей 43 ≠ 45, а фактически в `vectors/view/cases.tsv`
  51 кейс (30 базовых 01–16, 7 строк 10-*, 14 строк 17-*…23-*). README
  векторов при этом верен («51 rows: 20 only view, 19 only shadow, 8 both,
  4 @exit 2»). 08.5 N5: «vector assemble (22 rows)» против фактических 23
  кейсов (README assemble: «23 rows: 22 computed, 1 @exit 2» — норма считает
  только computed). 08.7 N5: «vector issue (38 rows…)» против фактических 40
  (README issue: «40 rows: 13 ok, 24 refused, 3 @exit 2»; issue-39/40
  добавлены после фразы «all 38 rows»). Генератору теста придётся выбирать,
  чему верить. Правка: актуализировать числа в N5 трёх глав или убрать
  счётчики из прозы, оставив каноном README векторов.
- **А3 (М): чеклист P/08.1-03 инлайнит значение LOST_AFTER.**
  В чеклисте приёмки 08.1 значение «LOST_AFTER 45» написано числом, тогда
  как константа объявлена в observation contract (45 s). Дубль значения в
  прозе чеклиста — при смене контракта приёмка начнёт требовать старое.
  Правка: ссылка на константу без числа.

## (б) Кандидаты в генерацию по Т1–Т5

Новых кандидатов не нашёл. Алгоритмы урока (pass, accept, сборка книг
членов, move юнитов, reconciliation вида) по п. 3 ADR-0129 остаются прозой:
это поведение процессов, не формы. Криптография и байтовые форматы уже
покрыты векторами и подпадают под Т5 (record, ask-sig, keys, domain-token,
domain-envelopes, accept, agent-sig, may, view, assemble, issue — выход
существующих генераторов). Распределённая корректность (барьеры, held,
переизбрание) — тоже Т5 и векторами не заменяется. Оценка строк
генератора/выхода/судьи для гипотетических новых кандидатов не требуется:
существующий перечень форм урока исчерпан.

## (в) Формы, дублирующие прозу

- **В1 (М): стоимость PBKDF2 600000 в трёх местах.** Проза 08.4 («a dummy
  hash of the same cost (600000)»), data-схема users и схема break-glass
  (`pbkdf2-sha256$600000$…` в примерах/ограничениях). Смена стоимости
  потребует трёх правок; при расхождении генератору неясно, какое число
  канон. Правка: константа в форме или схемы ссылаются на прозу без числа.
- **В2 (М): пределы title/comment дублируют константы формы.** Проза N1.1 и
  N1.3a главы 08.4 («title 0..200», «comment 0..2000») повторяет
  GROUP_TITLE_MAX 200 и COMMENT_MAX 2000 из runtime-constants.tsv; схема
  users повторяет «0..200 characters» ещё раз. Тот же класс: ENTRY_MAX 1240
  повторён в текстах отказов (N1.5 комментарий, таблица N2 главы 08.10,
  сценарий 07 N5), «the last 5 objects/documents» — безымянные числа в
  08.8 и 08.9, HISTORY_LINES 2000 — дубль contract ↔ колонка meaning схемы
  08.9. Правка: в прозе и схемах — имена констант вместо чисел.

## (г) Генераторы tools/normgen больше своего выхода

Выход урока лежит в `tools/normgen/out/p08/` (1254 файла, 90 файлов
.go/.py, 28403 непустые строки кода). Непустые строки продюсеров:
gen_flags.py 1036, gen_refusals.py 510, gen_families.py 610,
gen_versioned_doors.py 240, gen_stagetests.py 1236, gen_vectors.py 1512,
gen_cmdtests.py 1489, gen_door_lesson.py 658, yamlsub.py 444,
wire.py+wire_vectors.py+wire_draft.py 1681. Ни один продюсер не больше
суммарного выхода урока (максимум — gen_vectors+wire* ≈ 3,2 тыс. строк
кода против 28,4 тыс. выхода). Поэтапную атрибуцию по kit.manifest не
проверить: пакеты удалены (ADR-0083 доп. (111)). Нарушений Т-бюджета не
вижу.

## Что проверено и сходится

- `refusals.tsv`: ровно 178 проекций (185 строк − 6 комментариев −
  заголовок), как обещает forms/README («154 original rows + 2
  first-admin» проецируются в этот объём). Разложение по главам: 8.0:10,
  8.1:5, 8.2:11, 8.3:39, 8.4:45 (включая 2 cli first-admin), 8.5:3, 8.6:21,
  8.7:19, 8.8:10, 8.9:8, 8.10:7 — ссылки N4 глав («Source rows 1–K»)
  совпадают.
- `versioned-doors.tsv`: 19 проекций из 16 строк — сходится с forms/README.
- `daemon-flags.tsv`: 20 входов + first-admin, как обещает forms/README.
- `stages.tsv`: 13 стадий, kit=- везде.
- `runtime-constants.tsv`: 26 строк = обещание forms/README (но см. А1 —
  обещание глав шире формы).
- README векторов view/assemble/issue точны по числам и разложению —
  расходятся именно фразы N5 в главах (А2), а не наборы.

## Вывод

Блокирующих нет. Серьёзная А1 — системная: фраза-обещание о форме констант
расходится с формой почти в каждой главе; закрывается либо пополнением
runtime-constants.tsv (предпочтительно, это же усилит Т1), либо точной
формулировкой перечня. Малые А2–А3, В1–В2 — фразовые и числовые правки.
Пункты (б) и (г) нарушений не дали.

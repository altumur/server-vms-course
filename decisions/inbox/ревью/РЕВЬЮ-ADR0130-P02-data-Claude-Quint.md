adr: 0130 (P/02 манифест и данные, Quint)

# Модель Quint боевых свойств P/02 (манифест и данные) — review103-claude

Задача P02.4 курса ServerVMS, итог принимает окно, запустившее эту работу. Фаза после независимых находок: автор тот же, независимость не заявляется. Это не вход приёмки кандидата, READY и GATE не заявляются. Счёт находок замороженного отчёта (Б0/С11/М8) не пересчитан.

- Срез: `ff32d483f6a099d05c9d06df8436e7745c2b4366`. Источник вопросов: собственный замороженный отчёт `РЕВЬЮ-ADR0130-P02-data-Claude.md`, коммит `63fe1c3c1`; он не менялся.
- Модели — это чтения текста норм при явных допущениях. Нарушение значит: текст допускает такой ход событий при этих допущениях. О реализациях вывода нет.
- Проект: `decisions/inbox/ревью/quint-p02-data-ff32d483/`: девять моделей `.qnt`, каталог `instances/` (по файлу на экземпляр: один файл со всеми экземплярами превышает лимит 20 МБ JSON сервера Apalache; параметры — таблица `MODS` в `run.py` и столбец `overrides` в `results.tsv`), `run.py`, `results.tsv`, `run.log`, `runs/` (89 трасс ITF), `trial-mismatches.tsv`, `report_tables.py`, `check_anchors.py`.
- Инструменты: Quint 0.33.0, Apalache 0.62.1 (один сервер, порт 18828, `-Xmx4g`, запуски строго по очереди), rust-бэкенд для симуляции в один поток. `check_anchors.py`: 69 якорей, 0 неверных на срезе. Сокращения якорей — как в замороженном отчёте.

**Итог: 148 запусков, совпало 147, не совпал 1 (Z07, разбор ниже).** 141 запуск Apalache (`verify`), 7 симуляций rust. По видам: witness 76, property 40, control 23, mutant 9. По исходу: 90 `violation`, 58 `ok`. Таймаутов нет. Для 18 трасс порядок событий или числа проверены отдельно по последнему состоянию ITF (`CHECKS` в `run.py`), все подтвердили.

**Что изменили модели.** Подтверждены С2, С5, С6, С7, М1, М4, М5; С9 и С10 подтверждены только в той части, что текст сам по себе не противоречит заявленному (находка о пробе осталась и моделью не решается); С4 подтверждена для поднятых пределов, случай при значениях по умолчанию зависит от кодировщика клиента; сужены С3, С8; С1 показана подсчётом операций, время не выражено. Главное новое: предложение С6 «удалять только дайджесты вытесненных ревизий» не закрывает гонку (R12, R13, R17) — закрывает условие на версию строки при удалении вместе с повторной записью частей после строки, и только для ревизии, опубликованной меткой (R14, R16). Новое наблюдение вне списка находок: шаг 17 не задаёт порядок перечитывания строки и вида, и при чтении строки первой вид уходит ниже опубликованной метки (R31–R33, R34).

## Как шёл прогон

Основной прогон — 2026-11-09 23:23:51 — 2026-11-10 00:11:05 UTC, 47 минут одного последовательного прогона на одном сервере; сумма времён запусков 2841 с. Цель в задании была около 30 минут: не уложился, основное время — запуски семейства гонок (R и B, 2737 с), на два запуска пришлось 400 с (R11, 13 шагов полной гранулярности) и 203 с (B02). Сервер остановлен, порт 18828 свободен, других JVM нет.

Пробный прогон шёл в рабочем каталоге вне проекта, каталог проекта он не задел. Его расхождения записаны в `trial-mismatches.tsv` (id, этап, причина, правка). Кратко: 11 записей — G01, G02, T03, P06, O07, O13, O16, G15, M10, H03 (два раза), R12, B01: ошибки параметров, ожиданий и неточности модели. Первый вариант гонки без склейки шагов и начальное состояние `MID` на трёх активных установщиках оказались слишком медленными: R03 не кончился за 4,5 минуты на глубине 15, R31 — за 3 минуты на глубине 12, H03 — на глубине 52. Эти запуски прерваны вручную, результатом не считались; модель в рабочем виде — с режимом COARSE, `MID` на двух активных установщиках и экземплярами в отдельных файлах. Таймаутов (900 с) не было ни в пробе, ни в основном прогоне.

## Что смоделировано

Сокращения: `23`, `22`, `21`, `24`, `25` — `Platform/02-installer/spec/02.N-installer.norms.md`; `cl` — `Platform/common/contracts/store-client.md`; `ref` — `Platform/02-installer/forms/refusals.tsv`; `p011`, `p012`, `p013` — главы P/01.

| Модель | Находка | Что выражено | Граница |
|---|---|---|---|
| `put_race` | С6, С2, С10, новое про шаг 17 | шаги 9–19 установщиков одного имени, CAS строки, вида, метки, параметры порядка перечитывания, атомарности шага 19, правила удаления, разрыв с повтором | 1–3 установщика, дайджест — один элемент множества; режим COARSE склеивает шаг 9 с 15 и вид с меткой |
| `catalogue_window` | С7 | проверка каталога и запись двух разных имён, читатель всего каталога, повторная сверка и замок окна | 2 имени, один конфликт имени с таблицей |
| `put_outcome` | С3, неконфликтная часть С10 | запись с исходом `ok`/`ambiguous`/`unavailable`, память `id`, реакция: молчание текста, контроль, мутант | 1 установщик, 1 часть, повтор оператора один раз |
| `put_weight` | С4, С5 | веса строки и вида, `max_value`, `max_body`, части без строки, повтор при `toolarge`, разрыв | 1 установщик; `ENV` и экранирование — параметры модели |
| `reader_start` | С9, М1 | старт, повтор чтения, `START_WAIT` 60 с, коды 1 и 2, часы | 1 процесс, шаг времени грубый, пропуск срока запрещён защитным условием |
| `reader_mark` | М5, М1 | опрос метки, восстановление хранилища, новые `manifest put`, часы | 1 процесс |
| `reader_herd` | С8 | волна перезапусков одной смены метки и повторы чтения | 3 процесса, период 30 с масштабирован в 4 с |
| `file_publish` | М4 | атомарный rename без барьера и с барьером, потеря питания | семантика ФС — параметр `FS_EMPTY`, не утверждение о реальной ФС |
| `put_cost` | С1 (цена M4) | число чтений, записей, удалений, сравнений по шагам | счёт по фазам |

Константы из норм: `START_WAIT` 60 (`23:213`), пауза 1 с (`23:212`), период 30 с (`23:311`), `FILE_PART` 262144 и `FILES_TOTAL_MAX` 33554432 (`23:44`, `23:46`, отсюда не более 128 частей на файловый набор), `-max-value` 524288 и `-max-body` 1048576 (`daemon-flags.tsv:38-39`). Параметры модели, не предлагаемые числа: бюджет конфликтов 3 (R42), `ENV` 256, экранирование, смещения процессов.

## Что подтвердило, сняло, сузило находки

### С6 подтверждена; предложение замороженного отчёта не закрывает гонку

Сценарий достижим и доводит опубликованную строку до отсутствующих частей: A завершил `put`, B прочитал строку A и написал свои части, A на шаге 19 удаляет их (`23:307-308`), B пишет строку (R01–R03). R02 проверяет порядок `tParts(B) < tDel(A) < tRow(B)`; в R03 метка равна строке и частей нет. Гонка не зависит от промежутка между перечитыванием строки и удалением: при атомарном шаге 19 она та же (R04). Заголовок С6 верен; `23:329` эту гонку сам признаёт, срока и пробы нет.

Поправка к предложению замороженного отчёта. «Удалять только дайджесты вытесненных ревизий, известные текущему вызову» не закрывает гонку: B, проигравший конфликт и повторяющий с тем дайджестом, который A вытеснил, теряет части (R12), то же при возврате к байтам прежней ревизии (R13, R17). Ожидание `ok` в R12 было моей ошибкой, в пробе дало расхождение и исправлено на `violation`; разбор трассы R12: установщик 2 вытесняет строку установщика 1 (digest 2) и удаляет этот дайджест, установщик 1 проигрывает конфликт вида и повторяет с тем же digest 2.

Контроль, который закрывает: удаление под условием версии строки (`guard`, `cl:41`) плюс повторная запись частей после строки (R14, R16). Каждая половина по отдельности ломается (мутанты R18, R19). Закрывается только свойство «опубликованная меткой ревизия имеет части»: между записью строки и повторной записью частей строка всё равно называет отсутствующие части (R15). Прочтение `23:326` «строка никогда не называет несуществующие части» справедливо именно для порядка «части до строки», а не для гонки удаления; `23:329` это честно разделяет.

Не проверено: реальный цикл «следующий `put` чинит» после гонки удаления как отдельный свидетель (проверены лишь разрывы, С10); удаление покусочно внутри дайджеста; более двух установщиков.

### Новое наблюдение: шаг 17, порядок перечитывания

`23:301` и `22:778` велят при конфликте вида «перечитать строку и вид», если `rev` строки мой — повторить. Порядок двух чтений не задан. Если строка читается первой, отстающий установщик (его строка уже вытеснена третьим писателем) перезаписывает вид своим старым `rev` поверх новой версии: итог `row 4, view 3, mark 4`, вид никогда не совпадёт с меткой, читатель вида уходит кодом 1 до следующего `put` (`22:793-794`). Трасса R33, порядок проверен R32; достижимость начального состояния — R30 (полная модель на трёх установщиках, 8 шагов). Если первым читается вид, регресса нет (R34, 11 шагов, control). Параметр `VIEW_FIRST`.

Для метки проверено по одному свойству на вариант, до глубины 9: при чтении вида первым держится `inv_mark_le_row` (R35), при чтении строки первой — `inv_mark_never_fell` (R36). Остальные две пары «вариант и свойство» не запускались. В замороженном отчёте этого нет; в счёт не добавляется, это чтение одного неуточнённого места.

### С2 подтверждена

Конфликты строки не ограничены: 3 и 5 конфликтов достижимы (R40, R41), и вращение не ломает ни метку, ни строку (R45, R46). Контроль с конечным бюджетом даёт ограниченный итог с отказом (R42, R43), мутант без применения бюджета нарушается (R44). Бюджет 3 — параметр модели, число не предлагается.

### С3 сужена: вред в коде выхода, не в состоянии хранилища

Текст не называет исхода `unavailable` и `ambiguous` записи на шагах 15–18, поэтому молчание закодировано недетерминизмом реакции. Код 0 при незаписанной метке и при записанной только части достижим (O01–O03), повторный запуск команды тоже может завершиться ложным успехом (O07). Это показывает только, что текст не исключает. Но порядок записей сохраняет согласованность хранилища при любой реакции: `mark ≤ row`, `view ≤ row`, части до строки (O04–O06; это прямое следствие порядка шагов, заложенного в модель из нормы), повтор тем же `id` при рабочей памяти даёт один `rev` (O13, O16).

Закрывает правило «только повтор тем же `id` или код не 0» (O08, O09). Показанное здесь следствие норм: при потере памяти `id` повтор уходит в конфликт, а затем в шаг 11 и даёт лишний `rev` (O12). Лишний `rev` без потери памяти даёт и обычный повтор оператора после сбоя вида (O17), это прямо разрешено `23:276` и важно лишь как лишний перезапуск. Мутант «считать сбой успехом» ведёт к метке выше строки (O14, O15): нарушение `23:350`, что и показывает необходимость правила `cl:94`.

### С10 подтверждена в части текста; находка о пробе остаётся

После разрыва на любом шаге и повторного `put` того же или другого файла состояние восстанавливается (B02, B03, 13 шагов); до записи строки прежняя ревизия цела (B01). Достижимы строка без вида и вид без метки (B04, B05). Восстановление в этих двух случаях идёт разными путями: строка без вида поднимает `rev` на лишнюю единицу (B06), вид без метки — без подъёма (B07). Разрыв после метки оставляет старые части, не снимаемые путём «unchanged» (B08).

Текст здесь внутренне согласован: разрывы приводят к восстановимым состояниям, как норма и обещает. Сама находка С10 — об отсутствии исполняемой пробы, модель её не снимает.

### С5 подтверждена

Части строки с `toolarge` на шаге 16 остаются (G09), количество осиротевших дайджестов растёт с попытками (G10, G11). Контроль: сравнить вес строки до шага 15 — части при `toolarge` не появляются (G12). Разрыв между шагами 15 и 16 контроль не лечит (G13, G14). Успешный следующий вызов снимает все осиротевшие (G15); по размеру один дайджест — до 32 МиБ файлов, «43 MiB of rows» в формулировке самой нормы `23:384`. Срока, бюджета и наблюдаемой уборки нет.

### С4 подтверждена для поднятых пределов; при значениях по умолчанию зависит от кодировщика

При поднятом `-max-value` вид в пределах `max_value` получает 413 на шаге 17 уже после записи строки: G01, G02. Строка новой ревизии без вида; повтор поднимает `rev` и снова падает (G08). Контроль: сравнивать тело до записи (G04, G05, G06).

Сценарий замороженной С4 — как раз поднятый `-max-value` (к чему подталкивает `ref:31`), здесь он подтверждён. На значениях по умолчанию (`524288`, `1048576`) при `ENV` 256 тело превышает предел, только если экранирование добавляет к виду наибольшего веса больше 524032 байт (G03: `VE=524288`, тело 1048832). Экранирование кавычек и обратной косой черты такого роста на обычном JSON-виде не даёт. Но `p011:552` оставляет способ экранирования строк свободным: клиент, пишущий не-ASCII через `\uXXXX`, утраивает двухбайтовый символ UTF-8, и вид из таких символов превысит предел при весе около 350 КиБ. Модель кодировщики не различает и задаёт рост числом `VE`; содержимое реальных видов не проверялось. Для исходной строки `yaml` повышенное экранирование возможно, но это шаг 16 с названным `toolarge` (G09 в другом параметре). `ENV` 256 и экранирование — параметры модели.

### С7 подтверждена, контроль «защитная строка окна» требует условия о снятии

Разные имена обходят проверку каталога: обе записи прошли, состояние нарушает правило (W01, W02), процессы всего каталога получают код 2 (W03). При соблюдённом окне нарушения нет (W04). Контроль повторной сверки сообщает о конфликте, но состояния не лечит: W06 — сообщение обязательно, W07 — нарушение всё равно достижимо. Контроль защитной строкой предотвращает (W08), но при падении держателя строка остаётся и блокирует окно (W09): замороженное решение нуждается в правиле снятия, иначе оно меняет одну потерю на другую. W10 — итог без какого-либо отчёта о нарушении, что и есть суть С7.

### С8 сужена: модель выражает совпадение, не величину шторма

Текст допускает все процессы в одну секунду повторов (H01, H02). Заданный разброс снимает совпадение (H03, H04), его отсутствие возвращает (мутант H05). Период масштабирован с 30 до 4 с, чтобы вывод был по совпадению, не по абсолютному времени. Модель не выражает случайный разброс как вероятностный: проверка достижимости ищет наихудшее, поэтому контроль смоделирован как заданные смещения. Величину шторма, нагрузку на хранилище и реальный разброс `RestartSec` модель показать не может; это оставлено за словом «всплеск» в замороженном С8.

### С9: только согласованность текста

Ветви старта внутренне согласованы: код 2 только при подтверждённом ответе (T04), код 1 не раньше срока (T02), старт после простоя (T05), оба кода достижимы (T06, T07). T01 и T03 обеспечены защитными условиями самой модели (T01 — сама реализация условия чтения; T03 — запрет пропустить срок) и свидетельствуют только о согласованности модели; это отмечено отдельно. Сама С9 — о том, что проба чтением заменяет исполняемую пробу: моделью не решается.

### М1 подтверждена при чтении «часы настенные»

Текст не называет часы (параметр `CLOCK`). Прыжок вперёд приводит к коду 1 раньше срока (T08, T09), прыжок назад затягивает ожидание (T10, T11) и опрос метки (M09). Для монотонных часов нарушений нет (T02, T03, M10).

### М5 подтверждена и усилена

Метка ниже запомненной работающий процесс не сочтёт изменением и останется на новой ревизии, тогда как новый процесс стартует на старой (M01, M02). При дальнейших `put` метка вернётся к запомненному `rev`, но с другим содержимым: `23:314` сравнивает только `rev`, и процесс не перезапускается никогда при `rev` равном запомненному (M04, M05, проверка по трассе). Замороженный отчёт этого не заметил: М5 формулировала только «ниже». Если метка поднимается выше запомненной, перезапуск есть (M03). Контроль сравнением `sha256` при равном `rev` закрывает равенство (M06, M07), случай «ниже» остаётся (M08).

### М4 подтверждена только при параметре ФС

При `FS_EMPTY = true` пустой файл после потери питания достижим (P01, P02), публикация может потеряться после сообщения об успехе (P04); при `FS_EMPTY = false` пустого файла нет (P03). Барьер данных и каталога закрывает (P05, P06, P07), каждая половина необходима (мутанты P08, P09). Это условная находка: поведение конкретной ФС модель не проверяет.

### С1: цена `manifest put` (из плана «M4 manifest-put»)

Ярлык M4 в плане здесь не разобран и никаких других сведений не имеет; с находкой М4 (барьер носителя) он не связан и к ней не притягивается. Показано другое: сколько обращений к хранилищу задаёт сам текст. Подсчёт по шагам `23:264`–`23:309`, `S` — манифесты в каталоге, `P` — части кандидата, `W` — записываемые части (не считая совпавших), `D` — удаляемые, `C` — конфликты строки (повтор со шага 9):

- чтений: `(1 + S) + 1 + (3 + P)(C + 1) + 2` (2 — перечитывание строки и листинг шага 19; в пути «unchanged» их нет);
- записей: `W + (C + 1) + 2`, в пути «unchanged» — только `W`;
- удалений: `D` (по одной строке на удаляемую часть);
- попарных сравнений `load_catalogue`: `S²` (`21:1190`, «any subsystems A and B»).

Счёт проверен дважды: инвариантами Quint (L1–L7, Q1–Q7) и независимым пересчётом по трассе (`CHECKS` для K1–K7).

| прогон | S | P | W | C | чтений | записей (в т.ч. CAS с конфликтом) | удалений | сравн. пар S^2 |
|---|---|---|---|---|---|---|---|---|
| K1 | 2 | 4 | 4 | 0 | 13 | 7 | 4 | 4 |
| K2 | 8 | 4 | 4 | 0 | 19 | 7 | 4 | 64 |
| K3 | 64 | 4 | 4 | 0 | 75 | 7 | 4 | 4096 |
| K4 | 2 | 32 | 32 | 0 | 41 | 35 | 32 | 4 |
| K5 | 2 | 128 | 128 | 0 | 137 | 131 | 128 | 4 |
| K6 | 8 | 128 | 128 | 3 | 536 | 134 | 128 | 64 |
| K7 | 64 | 128 | 0 | 0 | 197 | 0 | 0 | 4096 |

Таким образом при действующих нормах стоимость одной установки растёт линейно с `S` и `P`, каждый конфликт повторяет все `P` чтений и 3 чтения шага 9 (K6), а сравнений каталога квадратично; вариант «unchanged» экономит только 2 чтения (K7: 197 вместо 199). Время операции, объём читаемых строк и `load` модель не выражает: она считает только число обращений. Следовательно ни бюджета времени, ни рост памяти процессов отсюда не следует; это остаётся находкой С1 как есть.

## Мутанты и контроли

Мутанты: 9 (R11, R18, R19, R44, O14, O15, H05, P08, P09), все нарушили ожидаемое свойство. Контроли: 23, из них 18 дали `ok`; 4 с ожидаемым `violation` показывают, что частичное правило недостаточно: R12, R13, R17 (знать вытесненный дайджест мало), W07 (сверка находит, но не предотвращает); Z07 — несовпадение, см. ниже.

### Несовпадение основного прогона: Z07

`Z07 race_known inv_row_names_parts` — симуляция rust, ожидание `ok`, факт `violation`, `match=NO`, строка оставлена. Причина: при правке ожидания R12 в пробе (контроль `race_known` недостаточен) я не поправил ожидание симуляции Z07 — той же модели и инварианта. Симуляция нашла то же нарушение, что Apalache в R12. Модель и вывод это не меняет; это ошибка таблицы ожиданий.

## Таблица прогонов

Полностью с параметрами — `results.tsv`. `violation` у property и witness значит: текст допускает ход событий при допущениях. У вида witness нарушение и есть цель запуска.

| id | модуль | инвариант | вид | инстр. | шаги | ожидание | факт | с |
|---|---|---|---|---|---|---|---|---|
| R01 | race_norm | inv_row_names_parts | witness | apalache | 8 | violation | violation | 7.9 |
| R02 | race_norm | wit_foreign_parts_deleted | witness | apalache | 9 | violation | violation | 8.0 |
| R03 | race_norm | wit_published_row_no_parts | witness | apalache | 11 | violation | violation | 17.9 |
| R04 | race_atomic19 | inv_row_names_parts | witness | apalache | 8 | violation | violation | 4.8 |
| R05 | race_fine | inv_mark_le_row | property | apalache | 9 | ok | ok | 41.8 |
| R06 | race_fine | inv_mark_never_fell | property | apalache | 9 | ok | ok | 34.9 |
| R07 | race_fine | inv_view_never_fell | property | apalache | 9 | ok | ok | 37.1 |
| R08 | race_atomic19 | inv_quiescent_published | property | apalache | 11 | ok | ok | 107.5 |
| R09 | race_seq | wit_two_installers_finish | witness | apalache | 15 | violation | violation | 7.5 |
| R10 | race_atomic19 | wit_lagging_mark_not_lowered | witness | apalache | 10 | violation | violation | 8.6 |
| R11 | race_nomark_cas | inv_mark_never_fell | mutant | apalache | 13 | violation | violation | 400.2 |
| R12 | race_known | inv_row_names_parts | control | apalache | 11 | violation | violation | 76.8 |
| R13 | race_known_revert | inv_row_names_parts | control | apalache | 9 | violation | violation | 6.7 |
| R14 | race_guard_post | inv_published_whole | control | apalache | 11 | ok | ok | 228.0 |
| R15 | race_guard_post | inv_row_names_parts | witness | apalache | 9 | violation | violation | 15.7 |
| R16 | race_guard_post_rev | inv_published_whole | control | apalache | 11 | ok | ok | 126.0 |
| R17 | race_known_revert | inv_published_whole | control | apalache | 11 | violation | violation | 11.0 |
| R18 | race_mut_guard_only | inv_published_whole | mutant | apalache | 10 | violation | violation | 19.6 |
| R19 | race_mut_post_only | inv_row_names_parts | mutant | apalache | 10 | violation | violation | 14.2 |
| R20 | race_guard_post | wit_step19_race | witness | apalache | 9 | violation | violation | 10.1 |
| R30 | race_three_full_rowfirst | wit_mid_state | witness | apalache | 8 | violation | violation | 10.5 |
| R31 | race_three_mid_rowfirst | inv_view_never_fell | witness | apalache | 9 | violation | violation | 22.2 |
| R32 | race_three_mid_rowfirst | wit_three_install_order | witness | apalache | 9 | violation | violation | 23.5 |
| R33 | race_three_mid_rowfirst | wit_view_fell_mark_row | witness | apalache | 11 | violation | violation | 91.8 |
| R34 | race_three_mid_viewfirst | inv_view_never_fell | control | apalache | 11 | ok | ok | 281.5 |
| R35 | race_three_mid_viewfirst | inv_mark_le_row | property | apalache | 9 | ok | ok | 77.6 |
| R36 | race_three_mid_rowfirst | inv_mark_never_fell | property | apalache | 9 | ok | ok | 63.5 |
| R40 | race_foreign | wit_conflicts_3 | witness | apalache | 13 | violation | violation | 6.9 |
| R41 | race_foreign | wit_conflicts_5 | witness | apalache | 21 | violation | violation | 31.9 |
| R42 | race_foreign_budget | inv_conflicts_bounded | control | apalache | 16 | ok | ok | 16.3 |
| R43 | race_foreign_budget | wit_refused_by_budget | witness | apalache | 13 | violation | violation | 5.6 |
| R44 | race_foreign_budget_mut | inv_conflicts_bounded | mutant | apalache | 17 | violation | violation | 12.8 |
| R45 | race_foreign | inv_mark_le_row | property | apalache | 12 | ok | ok | 8.2 |
| R46 | race_two_budget | inv_mark_never_fell | property | apalache | 10 | ok | ok | 51.1 |
| B01 | race_break | inv_prev_whole | property | apalache | 10 | ok | ok | 92.2 |
| B02 | race_break | inv_recovered | property | apalache | 13 | ok | ok | 202.8 |
| B03 | race_break_other | inv_recovered | property | apalache | 13 | ok | ok | 317.3 |
| B04 | race_break | wit_row_without_mark_after_break | witness | apalache | 7 | violation | violation | 5.2 |
| B05 | race_break | wit_view_without_mark_after_break | witness | apalache | 8 | violation | violation | 6.3 |
| B06 | race_break | wit_recovery_rev_jumps | witness | apalache | 13 | violation | violation | 138.4 |
| B07 | race_break | wit_recovery_unchanged | witness | apalache | 11 | violation | violation | 32.3 |
| B08 | race_break | wit_old_parts_left_unchanged | witness | apalache | 13 | violation | violation | 54.3 |
| W01 | cat_norm | inv_catalogue_valid | witness | apalache | 8 | violation | violation | 0.9 |
| W02 | cat_norm | wit_both_checked_clean | witness | apalache | 8 | violation | violation | 0.9 |
| W03 | cat_norm | wit_reader_code2 | witness | apalache | 8 | violation | violation | 1.0 |
| W04 | cat_window | inv_catalogue_valid | property | apalache | 10 | ok | ok | 1.2 |
| W05 | cat_window | wit_second_refused | witness | apalache | 6 | violation | violation | 0.8 |
| W06 | cat_recheck | inv_bad_reported | control | apalache | 10 | ok | ok | 2.2 |
| W07 | cat_recheck | inv_catalogue_valid | control | apalache | 8 | violation | violation | 0.8 |
| W08 | cat_lock | inv_no_bad_writes_with_lock | control | apalache | 10 | ok | ok | 1.1 |
| W09 | cat_lock_crash | wit_lock_stuck | witness | apalache | 8 | violation | violation | 0.8 |
| W10 | cat_norm | wit_all_ok_no_report | witness | apalache | 8 | violation | violation | 0.9 |
| O01 | out_silent | inv_no_false_success | witness | apalache | 10 | violation | violation | 1.0 |
| O02 | out_silent | wit_code0_row_applied_mark_missing | witness | apalache | 10 | violation | violation | 1.0 |
| O03 | out_silent | wit_code0_parts_only | witness | apalache | 8 | violation | violation | 1.0 |
| O04 | out_silent | inv_mark_le_row | property | apalache | 12 | ok | ok | 5.4 |
| O05 | out_silent | inv_view_le_row | property | apalache | 12 | ok | ok | 4.6 |
| O06 | out_silent | inv_parts_before_row | property | apalache | 12 | ok | ok | 2.7 |
| O07 | out_silent | inv_rerun_converges | witness | apalache | 14 | violation | violation | 1.1 |
| O08 | out_ctrl | inv_no_false_success | control | apalache | 14 | ok | ok | 2.9 |
| O09 | out_ctrl | inv_rerun_converges | control | apalache | 14 | ok | ok | 2.6 |
| O10 | out_ctrl | wit_ambiguous_applied_retry | witness | apalache | 8 | violation | violation | 0.9 |
| O11 | out_ctrl | wit_rerun_after_exit1 | witness | apalache | 16 | violation | violation | 1.2 |
| O12 | out_ctrl_nomem_norerun | inv_rev_one_step | witness | apalache | 14 | violation | violation | 1.1 |
| O13 | out_ctrl_norerun | inv_rev_one_step | property | apalache | 14 | ok | ok | 1.3 |
| O14 | out_mut_continue | inv_mark_le_row | mutant | apalache | 10 | violation | violation | 1.0 |
| O15 | out_mut_continue | wit_mark_above_row | mutant | apalache | 10 | violation | violation | 1.0 |
| O16 | out_silent_norerun | inv_rev_one_step | property | apalache | 12 | ok | ok | 1.8 |
| O17 | out_ctrl | inv_rev_one_step | witness | apalache | 14 | violation | violation | 1.2 |
| G01 | wgt_raised | inv_nothing_on_toolarge | witness | apalache | 8 | violation | violation | 0.8 |
| G02 | wgt_raised | wit_view413_after_row | witness | apalache | 8 | violation | violation | 0.8 |
| G03 | wgt_default_view | wit_view413_after_row | witness | apalache | 8 | violation | violation | 0.8 |
| G04 | wgt_ctrl | inv_nothing_on_toolarge | control | apalache | 8 | ok | ok | 0.8 |
| G05 | wgt_ctrl | inv_no_row_without_view | control | apalache | 8 | ok | ok | 0.8 |
| G06 | wgt_ctrl | wit_refused_precheck | witness | apalache | 6 | violation | violation | 0.8 |
| G07 | wgt_raised | inv_no_row_without_view | witness | apalache | 8 | violation | violation | 0.8 |
| G08 | wgt_raised | wit_rev_climbs | witness | apalache | 12 | violation | violation | 0.8 |
| G09 | wgt_row413 | wit_row413_after_parts | witness | apalache | 6 | violation | violation | 0.8 |
| G10 | wgt_row413 | inv_orphans_le_1 | witness | apalache | 14 | violation | violation | 0.8 |
| G11 | wgt_row413 | inv_orphans_le_2 | witness | apalache | 18 | violation | violation | 0.8 |
| G12 | wgt_ctrl_row | inv_no_orphan_at_all | control | apalache | 12 | ok | ok | 0.8 |
| G13 | wgt_ctrl_crash | wit_crash_orphan | witness | apalache | 6 | violation | violation | 0.8 |
| G14 | wgt_ctrl_crash | inv_no_orphan_at_all | witness | apalache | 6 | violation | violation | 0.8 |
| G15 | wgt_ctrl_crash | wit_orphans_cleared | witness | apalache | 14 | violation | violation | 0.8 |
| G16 | wgt_fine | wit_published | witness | apalache | 8 | violation | violation | 0.8 |
| T01 | start_mono | inv_no_serve_unconfirmed | property | apalache | 8 | ok | ok | 0.8 |
| T02 | start_mono | inv_code1_only_after_wait | property | apalache | 8 | ok | ok | 0.9 |
| T03 | start_mono | inv_wait_real_bounded | property | apalache | 8 | ok | ok | 0.9 |
| T04 | start_mono | inv_code2_confirmed | property | apalache | 8 | ok | ok | 0.8 |
| T05 | start_mono | wit_serve_after_outage | witness | apalache | 8 | violation | violation | 0.7 |
| T06 | start_mono | wit_code1 | witness | apalache | 8 | violation | violation | 0.6 |
| T07 | start_mono | wit_code2 | witness | apalache | 6 | violation | violation | 0.6 |
| T08 | start_wall_fw | inv_code1_only_after_wait | witness | apalache | 6 | violation | violation | 0.6 |
| T09 | start_wall_fw | wit_wall_jump_premature_code1 | witness | apalache | 6 | violation | violation | 0.6 |
| T10 | start_wall_back | inv_wait_real_bounded | witness | apalache | 8 | violation | violation | 0.7 |
| T11 | start_wall_back | wit_wall_jump_long_wait | witness | apalache | 8 | violation | violation | 0.7 |
| M01 | mark_norm | wit_stale_after_restore_lower | witness | apalache | 8 | violation | violation | 0.7 |
| M02 | mark_norm | wit_new_differs | witness | apalache | 9 | violation | violation | 0.7 |
| M03 | mark_norm | wit_stop_on_rise | witness | apalache | 10 | violation | violation | 0.7 |
| M04 | mark_norm | wit_equal_rev_other_content | witness | apalache | 12 | violation | violation | 0.7 |
| M05 | mark_norm | inv_no_stale_at_equal_rev | witness | apalache | 12 | violation | violation | 0.7 |
| M06 | mark_ctrl | inv_no_stale_at_equal_rev | control | apalache | 14 | ok | ok | 3.0 |
| M07 | mark_ctrl | wit_stops_on_equal_rev_ctrl | witness | apalache | 12 | violation | violation | 0.7 |
| M08 | mark_ctrl | wit_stale_after_restore_lower | witness | apalache | 8 | violation | violation | 0.7 |
| M09 | mark_wall | wit_poll_delayed_by_backward_jump | witness | apalache | 8 | violation | violation | 0.7 |
| M10 | mark_norm | inv_stop_within_period | property | apalache | 10 | ok | ok | 1.3 |
| H01 | herd_norm | wit_all_at_once | witness | apalache | 8 | violation | violation | 0.5 |
| H02 | herd_norm | inv_burst_le_1 | witness | apalache | 8 | violation | violation | 0.5 |
| H03 | herd_stagger | inv_burst_le_1 | control | apalache | 23 | ok | ok | 2.3 |
| H04 | herd_stagger | wit_spread_max_one | witness | apalache | 23 | violation | violation | 0.6 |
| H05 | herd_mut_zero | inv_burst_le_1 | mutant | apalache | 8 | violation | violation | 0.5 |
| P01 | pub_norm | inv_no_empty_after_crash | witness | apalache | 5 | violation | violation | 0.5 |
| P02 | pub_norm | wit_empty_file_after_crash | witness | apalache | 5 | violation | violation | 0.5 |
| P03 | pub_noempty | inv_no_empty_after_crash | property | apalache | 6 | ok | ok | 0.5 |
| P04 | pub_norm | wit_lost_publication | witness | apalache | 6 | violation | violation | 0.5 |
| P05 | pub_ctrl | inv_no_empty_after_crash | control | apalache | 6 | ok | ok | 0.5 |
| P06 | pub_ctrl | inv_reported_survives | control | apalache | 6 | ok | ok | 0.5 |
| P07 | pub_ctrl | wit_normal_publish | witness | apalache | 6 | violation | violation | 0.5 |
| P08 | pub_mut_nodata | inv_no_empty_after_crash | mutant | apalache | 5 | violation | violation | 0.5 |
| P09 | pub_mut_nodir | inv_reported_survives | mutant | apalache | 6 | violation | violation | 0.5 |
| K1 | cost_s2_p4 | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L1 | cost_s2_p4 | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q1 | cost_s2_p4 | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| K2 | cost_s8_p4 | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L2 | cost_s8_p4 | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q2 | cost_s8_p4 | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| K3 | cost_s64_p4 | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L3 | cost_s64_p4 | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q3 | cost_s64_p4 | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| K4 | cost_s2_p32 | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L4 | cost_s2_p32 | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q4 | cost_s2_p32 | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| K5 | cost_s2_p128 | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L5 | cost_s2_p128 | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q5 | cost_s2_p128 | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| K6 | cost_s8_p128_c3 | wit_done | witness | apalache | 19 | violation | violation | 0.6 |
| L6 | cost_s8_p128_c3 | inv_reads_expected | property | apalache | 19 | ok | ok | 0.5 |
| Q6 | cost_s8_p128_c3 | inv_writes_expected | property | apalache | 19 | ok | ok | 0.5 |
| K7 | cost_s64_p128_unch | wit_done | witness | apalache | 10 | violation | violation | 0.5 |
| L7 | cost_s64_p128_unch | inv_reads_expected | property | apalache | 10 | ok | ok | 0.5 |
| Q7 | cost_s64_p128_unch | inv_writes_expected | property | apalache | 10 | ok | ok | 0.5 |
| Z01 | race_norm | inv_mark_never_fell | property | rust | 40 | ok | ok | 1.8 |
| Z02 | race_norm | inv_mark_le_row | property | rust | 40 | ok | ok | 1.8 |
| Z03 | race_guard_post | inv_published_whole | control | rust | 40 | ok | ok | 1.9 |
| Z04 | race_guard_post_rev | inv_published_whole | control | rust | 40 | ok | ok | 1.8 |
| Z05 | race_three_mid_viewfirst | inv_view_never_fell | control | rust | 40 | ok | ok | 1.8 |
| Z06 | race_break | inv_recovered | property | rust | 40 | ok | ok | 2.0 |
| Z07 | race_known | inv_row_names_parts | control | rust | 40 | ok | violation | 1.1 |

## Не вошло

- С11, М2, М3, М6, М7, М8: по списку приоритетов задачи не входили; ход событий в них не главное (объём обхода, отсутствие нормы, отсутствие операции, форма команды, диагностика, проба).
- Внутри С1: `load`, `load_catalogue` как вычисление CEL, проекция, файл прав, `manifest get`, размеры прочитанных строк, рост памяти, время. Проба роста со входом от среды моделью не заменяется.
- Внутри С2: конфликт на шаге 15, конфликты шагов 17 и 18 как независимые циклы, задержка и разброс повторов, SIGTERM как отмена.
- Внутри С3: `unavailable` и `ambiguous` чтений шага 15; `no_reply` как отдельное событие (свёрнуто в ambiguous).
- Внутри С4: вес строки части на шаге 8 и шаге 15; шаг 8 считался проходящим.
- Внутри С5: рост журнала хранилища; перенос в журнал не моделируется.
- Внутри С6: поочерёдное удаление частей, сбой посреди удаления, отказ `delete` с диагностикой, восстановление следующим `put` как отдельный свидетель.
- Внутри С7: иные пересечения по `21:1190` (группы, виды токенов, метрики); гонка внутри окна при нарушении операторского условия не отделена.
- Внутри С8: `RestartSec`, реальная волна, рост повторов из-за кода 1, отдельные запуски служебных частей.
- Внутри С9: шаг 0, читатель вида `22:794` как отдельная ветка, директивы стенда (проба).
- Внутри С10: неконфликтные отказы чтения шагов 5, 6, 9 (тривиально обеспечены построением), проба с внедрением отказов.
- Внутри М1: дрейф, сдвиг на другом сервере, `START_WAIT` читателя вида.
- Внутри М4: реальная ФС, журнал ext4/XFS, барьер диска.
- Внутри М5: подтверждённое восстановление как событие, различение «установщик ещё не поднял» и «откат хранилища».

## Допущения и пределы

- Apalache — ограниченный поиск на заданную глубину. `ok` значит «не найдено до этой глубины», а не доказательство. Глубины указаны в таблице; для полной гранулярности с двумя установщиками достигнуто 9 шагов (R05–R07), для режима COARSE 11 (R08, R14, R16), для разрывов с последовательным повтором 13 (B02, B03).
- Режим COARSE склеивает шаг 9 с шагом 15 и (при успешном CAS) вид с меткой. Гонка шага 19 с записью чужой строки при этом сохраняется; выводы, зависящие от промежутка между записью вида и метки, снимались на моделях полной гранулярности (R05–R07, R11, R30–R36).
- Трём установщикам (R31–R36) задано среднее состояние `MID`; его достижимость из начального состояния показана отдельно (R30), но свойства R34–R36 проверены только от него и только на 2 активных установщиках. Вывод о шаге 17 ограничен этим начальным состоянием.
- Дайджест — элемент множества: части одной ревизии не различаются. Шаг 8 считается пройденным.
- Симуляции Z01–Z07 — случайный поиск, 3000 выборок, семя не фиксировано, вторичное свидетельство.
- Чтения текста, закодированные параметром или реакцией: `VIEW_FIRST` (`23:301`), `ATOMIC19`, путь «unchanged» завершает `put` без шага 19 (`23:275` «exit 0», параметром не заведён), значение метки на шаге 18 — это `rev` строки этого вызова (`23:305` говорит «of the row»; другое прочтение не проверялось), исход записи `unavailable`/`ambiguous` (`REACT`), часы (`CLOCK`), ФС (`FS_EMPTY`), размер экранирования и `ENV`. Прочтение «вызов переходит к шагу 19, если метка поднята этим вызовом» взято для ветки новой ревизии.
- T01, T03, W08, M10 обеспечены защитными условиями самой модели, O04–O06 — порядком шагов, заложенным в модели: это проверка согласованности модели, а не независимое свойство нормы. Реакция `silent` в С3 — только запись молчания текста.
- Масштаб: 1–3 установщика, 2 имени, 3 процесса; период 30 с масштабирован до 4 с в `reader_herd`. Абсолютные величины волн и задержек не выводятся.
- Не читались реализации `Source` и кандидатов, свидетели, native, runtime, частные судьи, отчёты других рецензентов (включая отчёт о службах P/02: раздел «Не вошло» брать не понадобилось), общий смысловой пакет. Запускались только Quint и Apalache.
- Журнал сервера и рабочие каталоги Apalache лежат вне репозитория (`/tmp/claude-1001/-home-pilot-review103-claude/8c59e25c-bfa6-49af-82e9-3a98557bbf75/scratchpad/p02q/`) и в коммит не входят.
- Хеши sha256 (начало): `catalogue_window` `46079bc6`, `file_publish` `65968a77`, `put_cost` `82a255a6`, `put_outcome` `82028248`, `put_race` `520b39a8`, `put_weight` `16f0785c`, `reader_herd` `6d789dc4`, `reader_mark` `ffcc0d08`, `reader_start` `3835a765`, `run.py` `96e0d755`.

## Покрытие чтения

Прочитано целиком: `02.3-installer.norms.md`, `common/contracts/store-client.md`, замороженный отчёт, образец проекта P/10 (`run.py`, одна модель, `check_anchors.py`, начало `trial-mismatches.tsv`, отчёт).

Частично: `02.2-installer.norms.md` — строки 745–850 и якоря; `02.1` — строки 1170–1195 с усечением, якоря 1174 и 1190; `forms/refusals.tsv` — первые 60 строк с усечением до 600 знаков (все строки главы 2.3); `02.4` — только строки 28, 228, 339, 400, 453, 455, 457 с усечением; `02.5` — строка 184; `01.1` — 278–296, 550–554 (дочитаны при приёме), 760–770, якорь 290; `01.2` — якорь 241; `01.3` — 130–140, 298; `production-obligations.md` — строка 9; `common/data/catalog.tsv` — первые 12 строк; `daemon-flags.tsv` — строки 38–39; `06-console/spec/06.5` — 391–405. Остальное обращение к этим файлам — поиск по ключевым словам. Якоря сверены `check_anchors.py` по байтам среза.

Не читались: схемы `02.1`, `02.2`, отношения, `acceptance/*`, остальная часть `02.4`, отчёт и модель служб P/02.

## Приём итога окном

Модель строил фоновый агент, итог принимало запустившее его окно того же автора; независимой проверкой это не является. Пересчитаны из `results.tsv`: 148 запусков, виды, инструменты, исходы, сумма времён, состав мутантов и контролей. Трассы R12, R33, M04, W09 прочитаны по состояниям. Цитаты 23:212, 213, 264, 275, 276, 301, 305, 307, 308, 314, 326, 329, 350, 384, 22:778, 793, 794, 21:1190, cl:41, 94 сверены со срезом вручную. Формула чтений и записей пересчитана для K1, K6, K7. Повторно запущены в отдельной копии шесть запусков, все дали прежний исход: Z07 (rust), R13, W09, G03, M04, P05 (Apalache). `results.tsv`, модели и `run.py` при приёме не менялись.

Исправлено при приёме только в тексте отчёта и в `check_anchors.py` (добавлен якорь `p011:552`): вывод о С4 при значениях по умолчанию (агент писал о «нереальном» случае, не учитывая свободу экранирования); номер дайджеста в разборе R12; утверждение об «обоих вариантах» для R35 и R36, шире запущенного; экономия пути «unchanged» в K7.

## Поправки к замороженному отчёту (сам он не менялся)

- С6, решение: «удалять только дайджесты вытесненных ревизий» недостаточно (R12, R13, R17).
- С7, решение: защитная строка окна требует правила снятия при падении держателя (W09).
- С4: сценарий с поднятыми пределами подтверждён (G01, G02, G08). При значениях по умолчанию случай вида требует роста тела от экранирования больше чем на 524032 байта (G03); достижимость зависит от кодировщика клиента, способ экранирования норма оставляет свободным (`p011:552`).
- С3: последствие уже названного; состояние хранилища при этих исходах остаётся согласованным (O04–O06), вред в коде выхода и диагностике.
- М5: формулировка неполная, опасный случай — равный запомненному `rev` с другим содержимым (M04, M05).

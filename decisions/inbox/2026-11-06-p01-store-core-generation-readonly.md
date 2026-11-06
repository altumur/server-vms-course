---
status: report-only
date: 2026-11-06
author: Генераторы (Codex), по поручению coord103 / Архитектора
report-base: 60258f4a5747e77fa9186a5d2c7034a3c08cce49
source-export: 58da260536cb2a24007ea1ad5ade68e716722c9a
source-course: 5a355d41ba49239726e89997609b135db5268d73
generator-reference: c81dd35d5ff850c687c94d251cdc84269e28730d
actual-kit-export: ce8d6db6219dbd38d358acbc81e3d429e7789950
actual-kit-code: 60cc85a3a7abbbb3528d8f8fcad9eb9aaf47999e
---

# P/01.1 store_core: границы генерации и предложение формы применения записи

Рекомендация Архитектору: рассмотреть узкий класс формы **решений применения записи к одному снимку состояния**. Он может закрыть выбор отказа, нормализацию отпечатка повтора и построение полного набора изменений. Принятые формы сейчас дают проверки входа, типы, каталог отказов, тесты и заготовки подключения. Они не задают исполнение CAS, guard, памяти id или атомарного commit.

Даже после такой формы способ захвата снимка, публикация изменений, выдача неповторяющихся версий, durability и консенсус останутся отдельной реализацией. Чистый план изменений сам по себе не закрывает `store_core` и не доказывает свойства IO. Предложение не выбирает storage algorithm, новый публичный ABI или новый KIT part.

## 1. Статус и точные входы

Это аналитический отчёт по ADR-0083 доп. (112), ADR-0127 пп. 2–3 и доп. (4), (5). Статус MiniMax40 `milestone_stalled` — контекст из опубликованного ADR-0083(112), не результат моего чтения реализации. Рабочий код модели, старые пробы и их деревья не читались. Причину конкретных ошибок модели по этому отчёту установить нельзя.

Читал исходники через `git show` и файлы неизменённого пакета. Выполнил только статическое чтение, сравнение байтов/SHA и подсчёты строк. Builds, tests, native commands, генераторы, KIT builder, runner и SUT не запускались. Source, forms, tools, out, пакеты и официальные пины не менялись. Единственный артефакт этой ветки — этот файл.

| Вход | Точная фиксация | Роль |
|---|---|---|
| Официальный source | export `58da260536cb2a24007ea1ad5ade68e716722c9a`, bare `/home/pilot/git/cammeta-specs.git` | Нормативная база анализа |
| Его курс | `COURSE_COMMIT` содержит `5a355d41b`; полный SHA `5a355d41ba49239726e89997609b135db5268d73` | Источник норм и принятых форм |
| Actual40 KIT | `/home/pilot/kits/p01-en-ce8d6db6-minimax40`, module `p01store/01-store` | Реальный исходный пакет попытки40, без изменений |
| Его собственные пины | export `ce8d6db6219dbd38d358acbc81e3d429e7789950`, code `60cc85a3a7abbbb3528d8f8fcad9eb9aaf47999e` | Не заменены на 58da/5a355 |
| `kit.manifest.json` | SHA256 `ddd77996713572afc2b7f5c0e34874bb81af41c06e661b40b5b20ca8973027df` | Независимо совпал при чтении |
| `SOURCE.txt` | SHA256 `a128c4471579e1ca05f6a30d0aff4b9e821e9794f9047e3d9a204aa148ababab` | Независимо совпал; перечисляет старые пины actual40 |
| Опись | `/home/pilot/generate-inventory.md`, SHA256 `b22035585f49da525c220773ba037389440e8c143fd92448a3270edd885afa9d` | Исторические оценки и кандидаты P/01 |
| Дополнительный code reference | published `c81dd35d5ff850c687c94d251cdc84269e28730d` | Чтение producer и closed runtime; не код модели |
| Основание ветки отчёта | `60258f4a5747e77fa9186a5d2c7034a3c08cce49` | Содержит ADR-0127(5), будущие судьи — review-claude |

Дерево `tools/normgen` у c81 и основания отчёта одинаково: git tree `c4869cc25c88b75e93612fc51476cc750cc87836`. Это позволяет ссылаться на c81 при чтении producer. Это не делает actual40 пакетом c81: его собственные code/source pins остаются указанными выше.

### 1.1. Что различается у двух source pins

| Источник | ce8 actual40 SHA256 | 58da SHA256 / наблюдение |
|---|---|---|
| `Platform/01-store/spec/01.1-store.norms.md` | `ee3340d65c5f2ca10ec717ae701a34af29e4a1a6235aa1f3e59d318f25febdbe` | `03f962021e09a1b4df5f958fe44dbea96a732648db3431eb7aa87671d73a50e4` |
| `spec/01-store.api.openapi.yaml` | `b4f17f97d5c931cb5efe741279108b304cb718ecba419fdff485db26da3f1e2a` | Тот же SHA, 855 LF-строк |
| `forms/write-checks.tsv` | `ff8857eb04db915f7763a41d04ae99777f428575a40a27a2b7383fac8daa53c6` | `74430e7db8abc9b07af565d6b5a2be80a273650d2cc3c9e4b4f7b3a2d10fbafb` |
| `forms/stages.tsv` | `45bb100b65f95868131706a2d2b400449de9ea90de1aec83d693502819305b41` | `00b8de10314e13fdd197bff2c46ba631a03e3216034b42ccb368ecddeea73394` |
| `acceptance/1/scenarios.tsv` | `33223918e0b8729335f3577061913a8b76747f59a83ef28494c59d266ef2d188` | `a60cbcd2c429cc6464daa228320097ce6d15d26253239e34602f6fd1bf31bcde` |
| `acceptance/1/seams.tsv` | `d717b76be360aa3e8d2df2d3fe67011cbf3b9e73c01951463a3fab33fd538922` | Тот же SHA, 73 события в шести сценариях |

Статически установлено:

- Весь раздел между `## N3 Procedures` и `## N4 Refusals` у ce8 и 58da побайтно одинаков. SHA256 именно этого фрагмента: `210a3134703cec417aa8d5935dcaca5d4f85e98e19b1077713ed2d3c867d5b23`. Изменения остальной главы — английские названия/ссылки и метки; это не основание переносить результаты исполнения.
- У `write-checks.tsv` осталось 34 записи. Все колонки данных, кроме `norm`, одинаковы; во всех 34 `norm` заменены ссылки Н→N. Изменились также комментарии/описания заголовка.
- У `stages.tsv` осталось 11 этапов. Изменились `norms` и четыре `goal`; gate, kit, parts, depends и when сохранились. В обоих источниках `store_core` имеет `kit=-` и `parts=door,refusals,stagetests`.
- `scenarios.tsv` позиционный, с четырьмя именами `scenario/step/request/expect` в комментарии. В ce8 первая data row находится на физической строке2; в 58da — на строке3 после `# cell-json: request`. Во всех 345 строках все четыре значения совпали после **одного** outer JSON-string decode колонки request. Inner HTTP/JSON payload не переписывался и не парсился для этого сравнения. Первая строка `01-absent/1` сохранена.
- Реестр `Platform/common/data/cell-json-sha256.tsv` на 58da имеет SHA256 `93c74b67ecb06ec58359118647209567eb20207cadba92f4c5bcb4ac7b4892ac`. Для всех 345 P01 request cells статический SHA декодированных UTF-8 байтов совпал с обоими столбцами before/decoded.
- Между code60cc и c81 менялись readers, provenance и fixtures. Например, SHA producer `gen_checks.py` в actual40 provenance — `0603e5ca643308efcbe897913307f1670117b242c53cccc9a3a4d2ef3c296f38`, у c81 — `9ba4d80f1d9e63f651222fb93f413288da5a9acc0252941cc430e5f23cc1b4e1`. Старый producer не читает новый transport автоматически.

Эта сверка сохраняет смысл исследуемого N3 и request payload. Она не является GO/FULL, тестом пакета на 58da или повтором результата MiniMax40. Пакет ce8/code60cc не пересобирался и не переименовывался.

## 2. Что реально даёт принятая форма сегодня — категория A

Пути в этом разделе без другого указания относятся к exact export58da. Producer/runtime относятся к code reference c81; сведения о начальном пакете — к actual40.

| Принятый источник и адрес | Producer / runtime inputs | Реальный результат сейчас | Граница |
|---|---|---|---|
| `forms/write-checks.tsv`, 34 строки, `wc-body_object`…`wc-guard_elem_rights`; 4 `#var`, 3 `#lim`, 4 `#fn` | `gen_checks.py`; `runtime/go/runtime.go`, `prims/go/prims.go`; `kit/go/jsonstrict/jsonstrict.go`, `kit/go/writecheck/writecheck.go` | Строгий JSON-разбор; порядок формы/key/weight/rights; выбранный отказ и разобранное тело. `allowed` — переданный callback | Input — только body, sock, lone, lim. Состояния строк, текущих версий, id memory и last_admitted нет |
| `spec/01-store.api.openapi.yaml`, Key/Row/Cmd/BatchCmd/Written/*Fault | `gen_door.py`, `doorrt/go/runtime.go` | Типы двери, route/dispatch, схемы/ответы и кодирование; вызов Handler | Не выдаёт версию и не реализует Handler.Write/Get/List или commit |
| `forms/refusals.tsv`, N4, `P/01.1-R143/R144` | `gen_refusals.py`; значения статуса, kind, полей | Каталог и построение формы отказа | Не выбирает отказ по состоянию и не получает actual current index |
| `common/data/catalog.tsv`; P01 строки `platform/epoch_floor`, `platform/configstore-doors/<id>`; их schema/layers/outcomes | `gen_families.py`, `famrt/go/runtime.go`; на 58da также key-placeholders/outcome-units и physical input provenance | Валидаторы, типы, Read/Items/key этих двух семей | P/01.1-R017: сама глава владеет **нулём** семейств. Произвольные строки store — map string→string; каталог не задаёт CAS, id или состояние batch |
| `vectors/jcs`, `vectors/rights-evaluator`; common vectors по consumers | `gen_tests.py`, `common_vectors.py`, соответствующие test engine и adapters | Тесты и интерфейсы адаптеров; часть common adapters подключает handwritten contracts | Expected/canonical/traces не становятся алгоритмом. В actual40 `vectoradapter.Canonical` — YOURS stub; JCS сам не определяет набор fingerprint fields |
| `forms/stages.tsv`, n4 `store_core`; `acceptance/1/scenarios.tsv` и `seams.tsv` | `gen_stagetests.py`, `gen_tests.py`; `coreadapter.Handle`, clock/reopen/parallel test engine | В actual40 — 24 test wrappers, 235 событий проекции; выбор 20 обычных сценариев и s1–s4 | `kit=-`: алгоритм ядра не поставлен. Тесты вызывают обычный Core, не возвращают expect вместо него |
| N3 anchors + Handler signatures | `gen_core.py`, таблица OPS и extraction `sections/find/pick` | YOURS Store/Open и файлы методов с req-комментариями | Текст N3 вставляется как комментарии; Write отвечает `notImplemented`, Get показывает пустой store. Это scaffolding |

На входе `writecheck.Check` уже различаются `cas` без поля/null и неверные типы. `wc-cas` и `wc-write_cas` пропускают отсутствие/null либо допустимую строку; `wc-guard_form`/`wc-guard_elem_form` требуют закрытый объект и строковый index, допускающий `""`. Guard null запрещён; guards null запрещён, отсутствие списка допустимо. Это **проверка типа условия**, а не проверка, держится ли оно на строке.

Приёмка store_core выбирает `01–12`, `28`, `30`, `31`, `33–37` и четыре шва `s1-id-memory-time-alone`, `s2-admission-equal`, `s3-admission-monotone`, `s4-parallel-cas`. В actual40 это 175 обычных событий и 60 событий швов. Числа — чтение generated wrappers, не счёт выполненных или зелёных шагов. Швы reopen s5/s6 относятся к последующему `durable`, а real power loss вообще не воспроизводится этими directives.

### 2.1. Почему нельзя просто дописать «состоянийные» строки в нынешний write-checks

`gen_checks.Table` требует ровно переменные `{body,sock,lone,lim}`. Заголовок формы прямо исключает store state, cas/guard по значению и id memory. Строка таблицы вычисляет первый отказ; её effects — ответ, а не запись нескольких строк/метаданных.

Добавление `state`, `snapshot`, `admitted`, id lookup и state effects меняет домен и обязанности класса. Прятать их в `allowed` или в несуществующих полях body нельзя: это смешивает права с CAS и даёт неверные коды/приоритеты. Разрешение добавить новый класс/профиль должен дать Архитектор, форму пишет spec103.

Принятые машины остаются полезной основой. `gen_machine.py` выдаёт Step/Apply с YOURS действиями; primitive #var — bool/int/double/string, и snapshot/commit он не выполняет. `gen_policy_machines.py` и `policyrt/go` дают локальное состояние и intentions без IO; текущая поставка закреплена за двумя P03 policies. На них можно построить часть чистых решений, если Архитектор выберет переиспользование machine grammar. Само наличие общего CEL не означает, что типы store snapshot и эффекты transaction уже приняты. Ни новый общий DSL, ни скрытый storage callback в CEL здесь не предлагаются.

## 3. Разбор частей ядра: A / B / C

Здесь **A** — существующий вывод по принятым формам; **B** — предложенный новый семантический класс/закрытый профиль формы, ещё не принятый; **C** — реализация по прозе ADR-0127 п.2. Одна часть может содержать все три слоя. Оценки каждой части даны отдельно в §7.

### 3.1. CAS и guard

**Нормы:** P/01.1-R019, R028, R032/R033, R081–R083, R108–R110, R115/R116, R125/R126. Проверки типа — `wc-cas`, `wc-write_cas`, `wc-guard_form`, `wc-guard_key`, `wc-guard_elem_form`, `wc-guard_elem_key`; batch guard-on-write — `wc-guard_on_write`.

**A.** Форма и примитивы проверяют тип, key grammar и печатную форму index. Дверь знает форму `409 conflict`/`412 guard`. Нынешний producer не получает `current` и не сравнивает состояние.

**B.** Нужна закрытая таблица решений над типизированным снимком. CAS-domain: `Unconditional` для отсутствия/null; `Equal("")` для absent; `Equal(version)` для непустой допустимой строки. Guard-domain: `None` либо `{key,expected: VersionOrAbsent}`. Null guard отсекает A, он не равен отсутствию guard. Нужны отдельные правила guard mismatch и CAS mismatch с actual version из снимка и исходным list order.

Версия остаётся строкой, сравниваемой точно. `"0"` не равно `""`; 20 цифр не следует пропускать через float64 или int64. Существующая строка с unreadable items и сохранённым index существует для CAS/guard. Потерянный index не превращается в absent из-за lookup default.

**C.** Получить согласованные actual versions и применить изменение под той же транзакцией должен store. Механизм блокировки, CAS на диске/в log и решение caller после mismatch форма предиката не выполняет. Нельзя сначала отдельно проверить guard, отпустить защиту, а потом написать строку.

### 3.2. Один снимок, приоритет отказов и нулевые частичные эффекты

**Нормы:** R055 (A), R056, R072–R089, R100–R114, R120–R132. Порядок: form → weight → rights → id memory → not_after → not_before → guards → CAS → application.

**A.** Первую часть порядка уже задаёт write-checks. `refusals.tsv` задаёт код/поля результата, stages/seams — примеры конфликтующих условий. Ни один из этих источников не задаёт transactional snapshot или publishing step.

**B.** Входом чистого применения должен быть один immutable snapshot: нужные target/guard rows с presence/index, id entry и last admission metadata. Порядок guard/CAS берётся из исходных списков; pure function не перечитывает store. Результат — отказ/replay либо полный план row/id/version changes, с явной отдельной категорией admission metadata.

`expired`, `early`, `guard`, `conflict` не меняют строки, не занимают id и не расходуют версии. Но R088 и R132 требуют сохранить admission time уже admitted отказанной записи как last admission, с durability. Поэтому «отказ = никаких изменений всего state» неверно. Для replay/id-content mismatch форма должна явно связать metadata policy с R070 и соответствующей веткой N3; выводить blanket rollback всех метаданных по слову «отказ» нельзя.

**C.** Захват снимка и commit должны иметь одну границу сериализации; правильный вызов чистого helper на старом произвольном snapshot этого не доказывает. Locks/transactions и управление их временем жизни остаются store. Pre-admission form/rights refusal и отказ уже admitted record — разные точки процесса; новый helper не должен незаметно передвинуть права внутрь/наружу log admission.

### 3.3. Batch: все writes или ни одного

**Нормы:** R019/R020, R117–R140; особенно R125–R135. A-строки: `wc-writes_form`, `wc-write_*`, `wc-guards_form`, `wc-guard_elem_*`, `wc-writes_twice`, `wc-guards_twice`, `wc-guard_on_write`.

**A.** Готовы closed elements, keys, duplicate/overlap checks, поэлементный вес и права, limits с исключениями ролей console/domain. Всё это исполняется до N3. Families не описывают общий batch произвольных ключей.

**B.** Новый профиль обязан сначала проверить **все guards**, затем **все CAS**, и только после успеха выдать полный набор эффектов. Guard и target versions принадлежат одному snapshot. Одна новая версия операции идёт всем put rows; delete расходует ту же версию. Для delete absent row остаётся отсутствующей: нельзя ввести видимый tombstone с этой версией, иначе изменится CAS-empty поведение R116.

План строит копии items, удаления и id-record целиком; ошибочный поздний элемент не оставляет ранее применённых строк. Повторное использование ключа write и guard на записываемом ключе уже запрещены A. Сортировать writes или guards для выбора первого отказа нельзя. При этом guards в replay fingerprint — множество: порядок исполнения и порядок семантического сравнения повтора различаются.

**C.** Исполнение плана как одной публикации и сохранение всего/ничего при power loss — storage algorithm. Mutex защищает от наблюдения половины batch внутри живого процесса, но не от половины файлов после отключения питания. Выбор WAL/transactional engine/другого способа, durability barriers и consensus log не выводится из списка ожидаемых ответов. Для группы batch остаётся одним log record по R135; распределённую корректность нельзя объявить из локального автомата.

### 3.4. Id: fingerprint, replay, unknown outcome и срок памяти

**Нормы:** R078, R086, R088–R098, R105, R113, R122/R129/R134/R135, R140–R142. A-строки: `wc-id`, `wc-batch_id`; JCS/rights vectors и s1 — только ограниченные свидетели.

**A.** Проверяется id как 1–64 lowercase hex digits; null запрещён. Есть тесты сохранённого ответа, повторов A/B/A, deadline/id priority и fingerprint equivalences. Полный нормализатор fingerprint и id memory сейчас не порождаются. Даже готовый CanonicalJSON не выбирает, какие поля сравнивать.

**B.** Нужны два связанных закрытых описания: projection/normalization fingerprint и переходы replay memory. Для put — op/key/items/cas/guard/bounds; для delete items исключён независимо от его JSON-типа; для batch writes сохраняют порядок, guards сравниваются как множество, отсутствие guards равно `[]`. Cas null равен отсутствию. Неизвестные top-level поля исключены. Порядок items и JSON escape spelling несущественны; ключи и строковые values не нормализуются по Unicode.

Bounds сравниваются и входят в fingerprint по **binary64 value**, как требует R019/C01-TIME-NUMBER-EXACT-01. Bool не число; `10` и `10.0` равны; absence bounds не равен числу. Нельзя заменить это raw-body hash, произвольным JSON marshal или общим сравнением точных рациональных чисел без учёта binary64-domain bounds.

Для id memory нужны состояния `absent`/`applied` с нормализованным record, сохранённым answer и данными минимального срока. Same id + same fingerprint возвращает первоначальный index с again=true; different fingerprint — badrequest. Refusals early/conflict/guard не занимают id: следующая попытка снова оценивает время и state. Успешный batch занимает одно id в общей памяти с single write; отдельный «batch cache» нарушит R134. Интеграция floor P/01.3 должна сохранить ту же общую память; семантику floor в форму store_core из воздуха не добавлять.

R141 разрешает забыть только когда **прошло больше двух минут И применено не менее 50 000 записей с id после первой**. Это MAY, не требование удалять запись сразу. Отсутствие eviction допустимо для ограниченного RAM helper; срок/объём сверх минимума выбирает реализация. Автор формы должен закрепить точный счётчик applied-id-records и источник elapsed time, не подменять их всеми HTTP запросами, временем последнего replay или значением deadline/admitted. В этой записке нового clock/counting правила нет.

**C.** Мапа памяти, исключение двойного concurrent apply, сохранение rows/id/answer вместе, recovery и завершение повторного durability barrier остаются store. Unknown outcome — знание о выполнении/ответе, а не `conflict`. При bytes-on-medium + barrier error нельзя удалить id и выдать новый index на replay; N4 требует ambiguous и повтор barrier, затем прежний answer/again без новой версии. Выбор того, как storage доказывает «не применится» для unavailable, остаётся по «Implementation decides» п.7.

### 3.5. Admission time, bounds и physical clock

**Нормы:** R019 not_after/not_before; R068–R071, R077/R079/R080/R088, R104/R106/R107, R121/R123/R124/R132. Швы s2/s3 — существующие свидетели дробных границ и хода часов назад.

**A.** `wc-not_after`, `wc-not_before`, batch counterparts проверяют finite nonnegative JSON numbers. Config.Now и engine `@clock` сохраняют дробную часть. Schema codecs умеют поле time строки; это другой контракт, а не сохранённый admission state.

**B.** Чистое правило `admitted=max(wall_at_admission,last_admitted)` и проверки `A>not_after` / `A<=not_before` поддаются маленькой закрытой форме. Typed domain — finite nonnegative binary64 seconds с различением absent bound. Дроби не отбрасываются. На apply подаётся **сохранённое A**, а не новый `cfg.Now()` каждого applying server. Проекция `admission_ahead` относится к P/01.3 N1.3 admission/двери status: отдельное правило относительно часов и порога source, не дополнительное условие успешности CAS.

**C.** Кто считал часы и в какой момент, как A попало в log record и snapshot, как restart/новый leader продолжают last A, как box сохраняет A под той же блокировкой/barrier — обязанности реализации. Отказанная admitted запись тоже продвигает last A. Copy/import — отдельная граница: P/01.3 не переносит admission из copy, новая группа начинает от часов своего leader; snapshot переносит его. `generation_at` floor — wall clock raiser, не admission. Formatter time из famrt ограничивает запись дроби миллисекундами и не подходит для хранения/сравнения admission по R070.

Следовательно, исторические «admit.Next/Expired/Early/Ahead — 25 строк, препятствий нет» означают маленький детерминированный кандидат, но не уже принятую форму или законченный temporal/storage runtime.

### 3.6. Версии, read/list и mutable aliases

**Нормы:** R019, R056–R067, R084/R085/R089, R111–R116, R127/R128/R133/R139; «Implementation decides» пп.1–5, 11.

**A.** Есть wire types, формы Row/Listing/Written, codec/checks и test cases. `gen_core` даёт Get/List/Write signatures. P/01.1 не имеет family-schema, из которой можно вывести общий map-store.

**B.** Можно включить в закрытый профиль ограничения эффектов: отказ — 0 allocations; successful operation — 1 issued version; all batch puts — тот же token; input/output items копируются. Это ограничения плана, а не выбор способа выдачи версии. Read/list oracle должен различать absent, unreadable body с index и потерянный index. Привязки схемы не определяют detection повреждения.

**C.** Фактический allocator, хранение already-issued state через restart/import, линейризуемое чтение, обход listing и защита aliases остаются реализацией. Два отдельных GET могут видеть разные стороны batch по R139; тест не должен ошибочно требовать одного snapshot от двух разных операций. Напротив, одна List или одна операция применения обязана видеть согласованный state. Wire serialization скрывает aliases, поэтому нужны owned-SDK checks изменения входного/возвращённого map либо независимое чтение кода, как прямо говорит N5.

## 4. Конкретный эскиз нового класса формы — категория B

Это proposal для решения **о классе**, не новые active filenames/нормы и не разрешение писать producer. Ни одна строка этого эскиза не внедрена. Служебные имена ниже обозначают внутреннюю модель судьи/генератора, не команды native protocol и не публичный Go ABI.

### 4.1. Закрытые typed domains

| Domain | Состав / ограничения | Основание |
|---|---|---|
| ValidatedCommand | put/delete/batch после A; single нормализуется в один ordered write; floor не выводится неявно | R072–R075, R100–R102, R117–R119 |
| Key | Декодированная UTF-8 строка по существующей Key grammar, без нормализации | R019/R029–R033 |
| VersionOrAbsent | `""` либо допустимая непустая version string; exact equality | R019, R081–R083 |
| CasCondition | tagged Unconditional либо Equal(VersionOrAbsent); missing/null → Unconditional | R019 cas |
| GuardCondition | None либо key + required VersionOrAbsent | R019 guard; form A |
| SnapshotRow | Absent либо Present(index, readable/unreadable items); отсутствие index — отдельная ошибка получения snapshot | R028 и N3 read |
| StoreSnapshot | Immutable target/guard rows, id entry, last admitted metadata одной границы операции | R056/R076/R120 |
| OptionalBound / Admitted | Absent либо finite nonnegative binary64 seconds; Admitted — stored number без округления дроби | R019/R068–R070 |
| ReplayEntry | Absent либо Applied(record fingerprint, initial answer, first-application metadata); одна память для всех операций | R078/R105/R134/R141 |
| PureResult | refusal/replay либо полный plan; отдельно business changes и admission metadata | R088/R127–R135 |

В domain не входят методы IO, произвольные native calls, clock reads, retry loops, locks, recovery callbacks или expected answers. Snapshot должен копироваться либо иметь доказанный immutable lifetime; передача живых map aliases не удовлетворяет этому контракту. Сам helper не доказывает, что caller действительно захватил такой снимок.

### 4.2. Таблица приоритетов и эффектов

Предлагаемая запись таблицы: `n | id | ops | phase | each | predicate | outcome | fields | effects | norm`.

- `phase` — только `id`, `not_after`, `not_before`, `guards`, `cas`, `apply`; начальные A checks не дублируются.
- `each` — `none`, `guards_in_source_order`, `writes_in_source_order`. Нет произвольных циклов и перестановок.
- `predicate` — закрытые typed операции: fingerprint same/different; bound present + binary64 comparison; snapshot version != expected guard; conditional CAS != snapshot version; завершающее true. Нельзя спрятать алгоритм в `store_ok()`/callback.
- `outcome` — только существующие replay, badrequest, expired, early, guard, conflict, apply; code/kind связываются с существующим refusals/OpenAPI.
- `fields` — только уже нормированные поля: key и **actual** index, прежний answer/again либо successful index. Requested cas/guard.index не выдаётся вместо actual.
- `effects` — typed plan: zero business changes, копии put items, удаления, один будущий version token, одна запись id; отдельная обязанность сохранить admitted metadata. План не содержит `commit()` как непрозрачного эффекта, якобы уже исполнившего IO.

Static checker должен отвергать unknown columns/words/types, повторные priority/id, несогласованный domain, неописанный терминальный исход, повторный/непоследний default и изменение source list order. Несколько одновременно нарушенных условий допустимы: именно для них норма задаёт first-match priority. Гарантия «все проверки до effects» должна быть свойством класса, а не комментарием одной строки. Нужна проверка полного покрытия допустимых normalized states и детерминированности результата.

Допустимый более полный pure output — вычисленный next-state снимок вместе с answer, если автор формализует и state transformations. Он всё равно не публикует live state. Вариант «план + общий исполнитель изменений» тоже возможен: если loop применения строк/id написан вручную один раз в closed runtime, его строки относятся к handwritten пакету, а не к generated. Оценки §7 относятся к варианту плана; нельзя одновременно записать одно применение state и в G, и в H.

### 4.3. Fingerprint projection и admission rules того же профиля

Для projection предлагаются закрытые поля `variant | source-field | presence | normalization | ordering | norm`. Selectors ограничены названными полями put/delete/batch; normalizers — cas missing/null, string-map by values, ordered writes, guard-set, optional binary64 bounds, ignored delete.items/top-level extras. Нельзя ссылаться на expect/canonical columns. Serializer или hash внутренней projection не задаётся публичным протоколом; должна сохраняться ровно нормированная эквивалентность, включая отсутствие bound и `+0/-0` по числовому значению.

Для admission достаточно явной typed max rule и двух правил границ в нормированном порядке. Last A на входе восстановлен store; stored A на apply пришло из record. Это не форма часов/консенсуса. Автор должен отдельно заполнить metadata effects для всех веток по R070/R088/R132; generator не выбирает их по эвристике.

Общую YAML machine grammar можно переиспользовать для этой конечной части, если Архитектор так решит. Тогда нужно принять store-specific typed/effect profile и независимого судью, а не называть добавление P01 в список P03 PARTS готовым store. Альтернатива — отдельная таблица закрытого профиля выше. Этот отчёт не выбирает между двумя вариантами за Архитектора.

## 5. Независимый judge: дизайн, отрицательные случаи, мутанты и IO

Новые формы пишет spec103 **после** решения класса. По ADR-0127(5), commit `60258f4a5`, новых судей пишет review-claude; Архитектор задаёт форму/свидетели/мутации и принимает класс. Ни judge, ни fixture, ни навыки в этой ветке не меняются.

### 5.1. Уровни независимости

| Уровень | Откуда oracle | Что реально доказывает | Чего не доказывает |
|---|---|---|---|
| Grammar / source | Независимый checker формы + чтение строк против указанных req; автор judge не producer | Закрытый vocabulary/types/coverage/priority; форма соответствует выбранной части прозы | Исполнение generated helper, реальный IO |
| Pure policy | Отдельная reference model из req с явной матрицей случаев; без импорта producer/helper | Actual result/plan на заданном snapshot; порядок ошибок; нормализация | Правильность snapshot, locking и commit |
| SDK / integration | Неподменённый ordinary Core через существующие Open/Handle и входы Config; наблюдение state после вызовов | Результаты реальных методов, replay, zero row/id effects, concurrent CAS | Power loss, log admission/consensus, shared-memory alias через один HTTP roundtrip |
| Durability / group | Реальный backend, restart/crash/fault injection и log/snapshot evidence, затем чтение исходов | Связь rows/id/admission/versions с persistence и log ordering | Из одних intentions/local traces такой вывод не следует |

Expected outputs остаются на стороне judge. Positive control по выписанным expected пригоден для engine, но не как oracle алгоритма Core. Генератор не должен возвращать эталон из таблицы или вызывать судью как runtime. До mutant kills обязателен baseline compile + выполненные oracle checks; invalid form, compile error, panic, skip и missing adapter считаются отдельными неуспехами, не убийством семантического мутанта.

### 5.2. Матрица proposed checks и мутантов

| Часть | Позитив/негатив | Компилируемые семантические мутанты |
|---|---|---|
| CAS/guard | absent/present/unreadable row; missing/null/empty/nonempty cas; absent guard, guard on absent row; exact long version strings; оба условия ложны | Unconditional=empty CAS; numeric conversion version; guard после CAS; missing map key=absent при lost index; actual index заменён requested |
| Priority / snapshot | id+expired+guard+cas нарушения вместе; ранняя/поздняя ошибка; две guard версии изменяются конкурентно; сохранность всех остальных строк/id | reread guard вне snapshot; emit write до позднего отказа; запомнить id отказа; выделить версию до проверок; откатить last A при отказе |
| Batch | первый/последний guard или cas false; guards source order против writes source order; все puts одной версии; mixed create/edit/delete; delete absent | применить первые writes до проверки остальных; версия на каждую строку; sort guards/writes; потерять одно удаление; commit rows и id раздельно |
| Replay | A/B/A; concurrent same id; same id different content; put/delete/batch единая память; equivalent cas null/missing, items order/escapes, reordered guards; ordered writes | raw-body fingerprint; включить delete.items/extra top fields; сортировать writes; отдельный batch cache; replay проверяется после deadline/CAS; новый index на replay |
| Retention | обе границы elapsed/count; время одно, count один; equality 120 s и 50 000; допускается сохранить дольше | OR вместо AND; >=120 вместо >120; забыть только по времени; считать каждый replay новой первой записью |
| Admission | A чуть до/на/после bound, в т.ч. .125/.25; wall rollback; later apply с иными часами; отказ продвинул last A | floor/round to seconds; codec milliseconds вместо A; `>=` вместо `>` у expired; `<` вместо `<=` у early; cfg.Now на apply; потеря A после reopen/snapshot |
| Versions / aliases | successful delete absent расходует одну issued version, но row остаётся absent; batch один token; входной/возвращённый map затем изменён | переиспользовать issued version после restart/delete; alias items; tombstone превращает absent в present; two GET считаются одной операцией |

Retention-model не должен ожидать обязательного eviction после обеих границ: это MAY. Fingerprint-model обязан отдельно учесть binary64 bounds, а не взять точное сравнение JSON numbers из CALL engine как универсальный нормализатор. Форму плохого JSON/type проверяет A; успешный parse сам не является N3 oracle.

### 5.3. Какие actual observations обязательны

1. **Zero partial business effects:** до/после отказанного batch прочитать все touched rows и listing, повторить id с допустимыми изменившимися условиями. Admission metadata проверять отдельно; blanket сравнение всего state на равенство здесь неверно. Отсутствие потраченной версии по opaque wire versions нельзя доказать разностью чисел — нужен внутренний witness allocator либо чтение реализации.
2. **Один snapshot / atomic visibility:** реально конкурентные операции guard-change/CAS/batch и одно наблюдение списка. Подставной storage, который лишь вернул «snapshot taken», не доказывает согласованность actual Core. Два последовательных GET не заменяют одну атомарную операцию наблюдения.
3. **Id и unknown:** операция с потерянным ответом, затем реальный повтор с тем же id; проверка прежнего index/again и неизменности rows. Для barrier failure необходим реально отказавший IO barrier и повтор его завершения, а не `reply=ambiguous` из таблицы.
4. **Admission persistence:** controlled Now на входе ordinary Core, отдельно сохранённое значение record; apply при иных часах; close/reopen, snapshot/log recovery и last A после уже admitted refusal. `@clock` не читает сохранённое A сам по себе; `@reopen` — graceful close/open, не power cut.
5. **Power loss batch:** остановка/ошибка на границах реально выбранного write/barrier/publication механизма и чтение после восстановления: весь batch либо ни одной его строки, id вместе с ним. Нужен отдельный approved witness способа IO; текущие s1–s6 не предоставляют детерминированный power-cut порт.

Существующий SDK ABI Open/Config/Core/Handle и класс seams могут быть оболочкой этих проверок. Недостающую наблюдаемость можно добавить только согласованным автором швом/внутренним judge adapter либо закрыть чтением реализации, как требует текущая N5. Новый native command или публичный storage API этим отчётом не назначается. `copyrt` обслуживает backup/import, а не transaction API live store_core; его наличие не доказывает atomic commit ядра.

## 6. Интеграция и оставшийся алгоритм — категория C

Достаточная будущая поставка чистого helper должна использовать существующие части: writecheck для A, core для закрытых typed decision helpers и YOURS подключения ordinary Store, stagetests для исполняемых свидетелей. Новые closed файлы и provenance можно добавить в существующий core part после назначения scope. Уже изменённые YOURS файлы нельзя перезаписывать при сборке. Нынешние `Open(Config)`, `Core`, `Answer` и door protocol сохраняются; внутренний тип плана в §4 не предписывает публичную сигнатуру.

Оставшийся алгоритм включает:

- получение согласованного состояния и владение блокировкой/transaction от snapshot до публикации;
- actual row map/storage и defensive copies при входе/выходе;
- выдачу уникальных версий, восстановление её состояния и связь с import/restore;
- atomic rows + id + admitted metadata, durability и повтор barrier при unknown;
- clocks at admission, log/snapshot/restart и физическую причину unavailable/ambiguous;
- rights evaluator и identity integration из P/01.2, файловую раскладку и выбранный consensus backend.

Если Архитектор захочет поставлять готовый handwritten storage runtime в KIT, это отдельная поставка с источником в прозе и IO judge. Её происхождение будет `handwritten`, даже при закрытых файлах и шапке DO NOT EDIT. Называть такой runtime mechanically generated из нынешних write-checks/families нельзя.

## 7. LOC: метод, измеренный baseline и оценки

### 7.1. Метод и предел меры

Статическая мера использует **LF**, не `splitlines()`: U+2028/VT внутри литералов не создают физическую строку. L = количество LF плюс незавершённая последняя строка; B = пустые/whitespace строки; C = comment-only; K = строка с хотя бы одним некомментарным токеном. Строка с кодом и хвостовым комментарием относится к K. Сумма L=B+C+K.

Для Go применён маленький лексический проход с состояниями block comment/raw string и учётом escaped quoted strings/runes; `//` и `/*` внутри литерала не удаляются. Данные массивов и JSON/raw literals считаются K: это **не** число statements или бизнес-веток. Для Python дополнительно читались AST/tokenize, docstrings отнесены к C, многострочные template strings — к K и отмечены отдельно. Это измерение исходного текста, без исполнения модулей.

105 файлов actual40 прочитаны по путям manifest; все 105 payload SHA совпали. Go-файлов 104; vendor отсутствует. Единственный non-Go payload — generated `stagetests/inventory.tsv`, 254 LF-строки; он не включён в код. `*_test.go` отделены от runtime. Editable начальное содержимое выделено отдельно: среди него есть stubs и рабочие common bridges; всё editable не объявляется ни алгоритмом, ни кодом модели.

Оставшийся код модели **не измерялся**: реализации читать запрещено. Все H-оценки ниже — будущий handwritten объём по обязанностям, не строки текущей MiniMax40. Ни доля от общего KIT, ни сумма огромных validators/Unicode tables не используется как процент готовности store_core.

### 7.2. Измеренный actual40, по конечным байтам manifest

| Категория Go | Файлов | L | B | C | K |
|---|---:|---:|---:|---:|---:|
| Closed generated, без tests | 15 | 15844 | 530 | 615 | 14699 |
| Closed handwritten, без tests | 43 | 12005 | 752 | 715 | 10538 |
| Editable generated initial content | 26 | 1049 | 89 | 735 | 225 |
| Editable handwritten common bridges | 4 | 162 | 17 | 15 | 130 |
| Generated tests | 16 | 3345 | 366 | 338 | 2641 |
| **Все Go** | **104** | **32405** | **1754** | **2418** | **28233** |

Проверка physical totals: Go32405 + metadata254 = manifest32659 = generated20492 + handwritten12167. Эти числа включают множество других contracts и закрытые таблицы; это не оценка ядра. В частности, label `generated` у 413 строк core scaffolding не означает 413 строк реализации CAS/commit.

| Существенный файл actual40 под `01-store/internal/` | L | B | C | K | Что считать |
|---|---:|---:|---:|---:|---|
| `checks/checks.go` | 2170 | 55 | 91 | 2024 | 34 pre-state checks, не state algorithm |
| `checks/runtime.go` | 518 | 39 | 14 | 465 | Handwritten CEL primitives/runtime |
| `checks/prims.go` | 65 | 7 | 9 | 49 | Handwritten key/weight/finite/allowed binding |
| `jsonstrict/jsonstrict.go` | 457 | 22 | 29 | 406 | Handwritten strict JSON decoder |
| `writecheck/writecheck.go` | 57 | 6 | 12 | 39 | Handwritten wrapper над checks |
| `apidoor/door.go` | 3687 | 278 | 231 | 3178 | Generated HTTP/type/schema code |
| `apidoor/runtime.go` | 469 | 42 | 33 | 394 | Handwritten HTTP/schema runtime |
| `families/families.go` | 118 | 13 | 33 | 72 | Две P01.3 семьи |
| `families/runtime.go` | 569 | 42 | 34 | 493 | Handwritten family reader/codec |
| `coreadapter/coreadapter.go` | 94 | 13 | 17 | 64 | Closed SDK boundary/dispatch |
| `coreadapter/core.go` | 79 | 8 | 48 | 23 | Initial constructor/context/helpers, состояние ещё комментарий |
| `coreadapter/write.go` | 93 | 3 | 85 | 5 | Package/import/signature/return/brace; тело — один notImplemented return |
| `coreadapter/open.go` | 17 | 3 | 5 | 9 | Constructor bridge |
| `coreadapter/get.go` | 28 | 3 | 16 | 9 | Empty-store stub |
| `coreadapter/list.go` | 17 | 3 | 9 | 5 | NotImplemented stub |
| `coreadapter/seams.go` | 22 | 2 | 15 | 5 | CALL stub ErrNotImplemented |
| `stagetests/store_core_test.go` | 125 | 26 | 25 | 74 | 24 wrappers, не store implementation |
| `stagetests/engine_test.go` | 837 | 40 | 21 | 776 | HTTP/CALL/clock/reopen/parallel test engine |
| `stagetests/scenarios_1_1_test.go` | 222 | 2 | 2 | 218 | Generated scenario data |
| `stagetests/seams_1_1_test.go` | 92 | 2 | 2 | 88 | Generated seam data |

У actual40 Write нет веток применения CAS/guard/id/admission/batch. Это вывод чтения её короткого тела, не результат запуска и не характеристика уже написанного моделью рабочего кода.

### 7.3. Существующие producer/judge: размер общего инструмента на c81

| Файл `tools/normgen/` | L | B | C | K | Из K: multiline templates |
|---|---:|---:|---:|---:|---:|
| `gen_checks.py` | 1230 | 141 | 33 | 1056 | 143 |
| `gen_core.py` | 532 | 77 | 36 | 419 | 118 |
| `gen_stagetests.py` | 1337 | 101 | 40 | 1196 | 977 |
| `gen_families.py` | 694 | 84 | 36 | 574 | 48 |
| `gen_tests.py` | 1013 | 126 | 54 | 833 | 450 |
| `gen_machine.py` | 739 | 83 | 32 | 624 | 0 |
| `gen_policy_machines.py` | 494 | 49 | 10 | 435 | 11 |
| `test_gen_checks.py` | 540 | 75 | 35 | 430 | 0 |
| `test_gen_core.py` | 305 | 32 | 13 | 260 | 37 |
| `test_gen_stagetests.py` | 451 | 32 | 12 | 407 | 160 |
| `scenario_judge.py` | 142 | 12 | 18 | 112 | 0 |
| `family_judge.py` | 256 | 26 | 17 | 213 | 0 |

Это общие файлы для нескольких частей/уроков. Их целиком нельзя записать в «стоимость добавления CAS». Существующие judges не запускались. `test_gen_checks` сверяет вывод с независимым CEL reader формы; `scenario_judge` сопоставляет inventory и actual step outcomes; ни один не синтезирует storage algorithm из prose N3.

### 7.4. Будущая оценка по частям

P — добавочный producer K; F — semantic declarations/rules формы (одна запись/объявление на строку, без шапок/пояснений); J — новый judge/test K; G — новый closed generated executable/helper K, **без** tests, stubs, комментариев и пустых строк; H — оставшийся handwritten algorithm/integration K. Typed glue включён отдельно в общую строку. Существующие большие validators не прибавлены повторно.

Диапазоны получены разложением на domains, ordered checks, projections, effect builders и SDK boundary; ориентиры масштаба — измеренные файлы §7.2–7.3. Это design estimate до author form и producer prototype. Для F/G/P уверенность средняя-низкая; для H и real-IO judge — низкая. Диапазоны не являются резервом CODE или обещанием готового KIT.

| Часть | P | F | J | G | H после helper | Основание / риск |
|---|---:|---:|---:|---:|---:|---|
| Общий typed/profile/provenance слой B | 180–300 | 18–28 | 180–280 | 50–80 | 30–60 | Fail-closed schema, connection к existing parts; reuse machine может сократить P |
| CAS/guard, §3.1 | 80–140 | 8–12 | 160–260 | 20–40 | 15–30 | Exact versions и absence; H — извлечь факты из snapshot, без locking, учтённого ниже |
| Priority/snapshot/metadata, §3.2 | 100–170 | 10–16 | 180–300 | 35–65 | 50–90 | H — atomic scope и согласованный snapshot; риск смешения admitted refusal с pre-admission |
| Batch effects, §3.3 | 100–180 | 10–16 | 180–320 | 50–90 | 50–110 | H — единая публикация в RAM, не disk; data copies/one version |
| Fingerprint + id policy, §3.4 | 150–250 | 18–28 | 240–400 | 70–130 | 60–120 | H — cache ownership/common namespace/replay integration; durability ниже |
| Admission/deadlines, §3.5 | 60–110 | 6–10 | 140–240 | 20–40 | 25–55 | H — clock point и metadata link; persistence ниже |
| Versions/read/list/aliases, §3.6 | 0–30 | 0–4 | 100–180 | 0–20 | 80–160 | Основной механизм C, не вывожу allocator/общий row store из family schema |
| Дополнительно durable backend / recovery | 0 | 0 | 300–700 | 0 | +250–650 | C: выбранные IO/barriers/layout, atomic rows+id+A, real crash witness; consensus сюда не включён |

Для ограниченного RAM пути первые семь строк дают порядок P670–1180, F70–114, J1180–1980, G245–465, H310–625. Это не прогноз размера нынешней MiniMax реализации и не сумма независимых «выигрышей»: при общей таблице/машине часть служебных строк объединится. Durable строка — отдельный добавочный диапазон, не обещание универсального файлового storage. Consensus/group algorithm здесь не оценён: его механизм не выбран и код не читался.

### 7.5. Воспроизводимость статического счёта

Достаточные входы для повторения: manifest SHA, корень actual40, code c81, список файлов в таблицах и определения L/B/C/K выше. Файлы берутся по **уникальным** `manifest.files[].path`; origin/editable/component — из manifest; `*_test.go` отделяются до подсчёта, `/vendor/` исключается. SHA считается до классификации. Число LF можно воспроизвести без lexer:

```python
L = data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))
```

Для C/K лексер проходит каждую LF-строку, сохраняя между строками состояния `/*...*/` и raw backtick string. Вне комментария первый не-whitespace token помечает строку K; quote/rune escape пропускает следующий символ; `//` прекращает проход вне строки. Blank имеет приоритет отдельной категории B. Это важно: обычный `splitlines()` дал бы ложные строки для литералов U+2028/VT в heartbeat/JCS fixtures. В конечных числах §7.2 использован LF-only счёт.

Источник можно независимо читать так (без checkout/regen):

```sh
git --git-dir=/home/pilot/git/cammeta-specs.git show \
  58da260536cb2a24007ea1ad5ade68e716722c9a:Platform/01-store/spec/01.1-store.norms.md
git show c81dd35d5ff850c687c94d251cdc84269e28730d:tools/normgen/gen_core.py
```

## 8. Сверка со всеми позициями inventory P/01

Левые подписи — существующие строки pinned inventory, не новые canonical IDs. Исторические LOC не считаются текущим остатком. «Кандидат» не означает принятую форму, занятый scope или задачу на CODE.

| Позиция описи / прежняя оценка | Класс сейчас | Что подтверждается/меняется этим разбором | Что остаётся |
|---|---|---|---|
| Apply(state,rec), R076–R085/delete/batch, 150 | A prechecks; **B новый state/effect profile**; C commit | Подтверждён кандидат и препятствие «состоянийная половина». Это не простое добавление строк к нынешнему write-checks; оценка150 не включает обоснованный IO/judge и не текущий замер | §§3.1–3.4, snapshot, публикация, durability |
| rights.Allowed/Never, 110 | Existing vectors/test class; алгоритм по прозе C | Expected tests не генерируют evaluator; отдельная существующая кандидатура, не CAS form | P/01.2 precedence/never/identity, подключение Allowed callback |
| Дверь без голоса, Status/freshness/metrics, 80 | Existing door/box/contracts; частичный готовый helper, отдельный кандидат | `gen_box` Status/Metrics относится к box; нельзя выдать его за group Door и real freshness IO | P/01.3 role=door, publication/query и actual indices; вне store_core |
| member.Decide join/repeat/leave, 70 | Existing box/door/refusals; кандидат таблицы membership | Box Join/Leave/Admit helpers уже есть, это не готовый group membership algorithm | Consensus membership/IO; не новое ядро CAS |
| Fingerprint/MayForget, 60 | **B projection/replay profile**, C cache/storage | Кандидат подтверждён; отметка «—» не означает accepted machine form. JCS не задаёт field projection, retention — AND/MAY | Shared id memory, first answer, unknown/barriers, минимум R141 |
| rights.Load, 60 | Existing OpenAPI/schema class, кандидат producer; C policy | Schema RightsFile годится для формы, но parsing schema не равно Allowed/Never | Реальный загрузчик/identity/pattern semantics; вне текущего scope |
| FORMAT Check/Encode, 50 | **Уже handwritten пакет** `launch.CheckFormat/readMark/writeMark` | Историческую повторную реализацию нельзя снова засчитать как новую генерацию; current helper делает tmp+rename | Параметры формата/версии и actual durable state store |
| LISTEN_FDNAMES/sockets, 40 | **Уже handwritten пакет** `launch.Listen` | Сопоставление имён, admin0600/role0660 поставлены; это готовый пакетный IO-код, не output нового state form | Интеграция процесса и реальные сокеты, вне store_core |
| wtime.Format/Parse, R006–R010, 40 | Existing codec/runtime; отдельный кандидат выделения | Famrt содержит time parsing/writer formatting. Выделение полезно без повторного алгоритма; нельзя этим formatter округлять admission | Раздельные row-time и admission contracts |
| Floor write-checks, 30 | Existing write-check class + box/copy helpers; state C | `wc-floor_socket` уже есть; прочие pure rows пишет spec103 при необходимости. Floor-state/id не следует из этой строки | Общая память id, floor upward/IO и P/01.3, без переноса copy floor |
| startcheck.Refuse, 30 | Existing flags/launch/box и seams; частичный кандидат | Startup helpers и три flags CALL уже поставлены, но declaration не доказывает реальный startup admission | Cert/CN/directory/import IO; не предмет store_core |
| -peers/-upper bad CEL, 25 | Existing flag class | В 58da typed rows `-peers list:id@addr/addr`, `-upper int:0..9007199254740991` уже есть. Новая state grammar ради них не нужна | Точные contextual checks и actual recover остаются своим scope |
| admit.Next/Expired/Early/Ahead, 25 | A number validation; **B temporal profile**; C persistence | Малый pure candidate подтверждён; «нет препятствий» уточняется: нет новой accepted P01 temporal формы, пока лишь prose rule | Stored A/log/snapshot/restart, fractional boundary, refused-record A |
| alarms/metrics, 25 | Existing constants/metrics vocabulary частично; отдельный кандидат | Нужны typed threshold/source и approved rule/profile; это не CAS/batch generation | Sampling/events/process IO; вне анализа core |
| Прочее: version, JSON_DEPTH, tuning, 403, Canonical, 70 | Смешано: A generated/handwritten checks, candidates и C | JSON_DEPTH/JSON parser уже пакет; Canonical vector adapter actual40 — stub; codec/validator не выдаёт versions | Allocator, tuning/публичные тексты/связки; не суммировать со всеми validators |

Новых строк inventory здесь не добавлено. Для решения Архитектора предлагается уточнить первую строку и связанные Fingerprint/Admission кандидаты как один ограниченный state-application profile с отдельно учитываемым C. Остальные строки P01 не резервируются и не смешиваются с текущими English/C2 поставками.

## 9. Что требуется решить до любых forms/code

1. Принять или отклонить узкий store state/effect class; определить, используется существующая machine syntax с новым typed profile либо отдельная конечная таблица. Общий DSL на все нормы не предлагается.
2. Закрепить в форме normalizers fingerprint, ordered priority, immutable snapshot, business/admission effects и точный предел pure helper. Вопросы metadata replay/id-mismatch и elapsed/count retention явно связать с req, не выбирать генератором.
3. Назначить spec103 автором формы и review-claude автором независимого judge; negative forms и compiled semantic mutants развести. Existing235 event projection остаётся обязательной совместимостью, не oracle power loss.
4. Отдельно назначить наблюдение actual Core/IO и способ приёмки C. Не объявлять storage выполненным по входным checks, emitted plan или fixture reply. Будущий exact code/source/private pin, минимальные пути integration и fresh output состав назначаются отдельно.

**Одна строка Архитектору:** P/01.1 store_core сейчас формами не реализован: готовы stateless checks/SDK/tests; предлагается узкий typed state/effect profile для CAS/guard/id/admission/batch с независимым judge, а snapshot ownership, actual commit/durability/consensus остаются алгоритмом; actual40 ce8/code60cc неизменён, source58da исследован отдельно, исполнения не было.

# Данные случаев только для судьи

Этот русский текст — производный от `acceptance/5/README.cases.md`, руками не правится (ADR-0121).

Общие правила остаются в [README.md](README.md). Следующие исходные отрывки сохраняют прежние связи именованных случаев как происхождение только для судьи.

### Исходный отрывок 1

В файле 8 сценариев / 70 шагов (сц. 12 шаги 12–18 — `domainagent` не пишет `domain/root`, `view`, `shadow`, `backups/rev-1`, `shared-docs/rev-1`, `alarm-history/m1`, `idem/k1`, 403, C02-LOCAL-BINDING240-ROOT; мутационная проверка 7cecaf2 № 29, 49: строки допуска контроллера без delete, отрицание `idem` у воркера; сц. 13 — заказ и состояние, ADR-0091, сц. 02 шаг 8 — удаление строки `testsub2` контроллером теперь 200: у неё `retire_when.delete_after` и `ends`); роли и файл прав генерируются из `testsub` и `testsub2`

### Исходный отрывок 2

Сверка python и go M10/6–11 (R1–R5, R7): сц. 04 шаги 4–7 — ресурс читает сроки обеих манифестов (строк нет: `items:
null`); сц. 12 — роли домена.

### Исходный отрывок 3

названная роль. Сценарий 09 проверяет право чтения door/signer: строку создавать не нужно,
разрешённое чтение отсутствующей строки возвращает Row с items null по главе P/01.1.

### Исходный отрывок 4

| Вариант | Манифесты | Что проверяет |
|---|---|---|
| `v1-base` | `va` без `requests`, с `delete_after` | роли платформы и манифеста; `requests/*` консоли нет (R8); пустой `<y>` и `never` эпохи (R12); `retention` ресурса (R2); `domain/grants` консоли — точный ключ и семья `domain/grants/*` (`domain/grants/c1` — да: след домена P/06.3 N1.8; разбор ревью стадии A 8–10, план 8 V7, правка поведения), `domain/view` — нет (R5); `domain/holder` воркера (R7); роли `vadomain` нет; `door/signer` читает консоль, не воркер, без объявления в манифесте (разбор ревью стадии B 6–7, № 36) |
| `v2-requests` | `va` с `requests`, `vb` с `worker.requests: [va]` | `requests/*` консоли только у `va`; подача `vbworker` в `va`; метки `objects/va/commands/*` (R8, R9) |
| `v3-objects-rows` | `va` с `objects.rows: [marks/]` | `marks/` → `objects/va/marks/*` (R10) |
| `v4-domain-kept` | `va` с `domain.kept: [ledger, badges/]` | `vadomain` пишет слот и `kept`; `domainagent` — по форме объявления и без слота и пульса воркера на домене (R4, R3) |
| `v6-near-about-ref` | `va`; `vb` с `placement.near.sub: va`, `vc` с `about.sub: va`, `vd` с полем `ref: va/items` | контроллер читает строки `va` по каталогу (`placement`, `workers`, `slots`, `holds`, строки единиц, `policy`, `placement_turn`), не эпоху, `idem`, `next_id` и не пишет; обратной связи нет (решение «Архитектора» 2026-10-27; P/03 Go 084a3ee9, P/03.6 сц. 07) |
| `v7-must-match` | `va` (поле `shelf` — `ref: va/shelves`, `must_match: {zone: zone}`; таблица `shelves`); `vb` с `worker.creates` на `va/items` (`key: "{code}"`); `vc` с таблицей `links`, поле `of` — `ref: va/items`, `must_match: {zone: zone}` | заказчик `vbworker` читает цели проверки строки — `va/shelves/*` (прямая ветвь) и `vc/links/*` (обратная ветвь `must_match`), пишет только `va/items/vb-*` без удаления; чужие строки `va/items` и прочие семьи `vc` — нет; контроллер `va` обратную семью не читает (аудит покрытия P/02, B07) | P/02.5 N1.4 `<s>worker` «reads of the common row check»; договор проверки строки |
| `v8-worker-writes-deletes` | `va` с таблицами `shelves`, `gauges`, `worker.writes: [gauges]`, `worker.deletes: [items]` | таблица `worker.writes`: воркер пишет, читает и удаляет, консоль читает и только удаляет; обычная таблица: консоль пишет и удаляет, воркер только читает; `worker.deletes`: воркер удаляет строки единиц без записи, контроллер без `delete_after` — нет (аудит покрытия P/02, второй проход) | P/02.5 N1.4 `console`, `<s>worker`, N3 шаг 2 |
| `v9-asked-free-resource` | `va` с `requests` без `per_person` и `free`; `vb` с `about.sub: va`, таблицами `notches` (`holds.table`) и `shelves`, `requests` с `per_person` и `free: true` | консоль пишет `vb/asked/*`, не `va/asked/*`; `!vb/asked/*` у воркера и контроллера `vb`; ресурс пишет, читает, удаляет `vb/requests/free-*`, не `vb/requests/<rid>` и не `va/requests/free-*`; ресурс читает таблицу `holds.table` (`vb/notches/*`) и строки единиц манифеста с `about` (`vb/things/*`), не прочие таблицы, не строки `va` без `about` и не семью места `<s>/holds/*` ни у `vb`, ни у `va` (договор удержаний; C02-RESOURCE-HOLDS-TABLE-01) (там же) | P/02.5 N1.4 общие правила, `console`, `resource` |
| `v10-worker-domain-reads` | `va` с `worker.reads: [domain/placed/va/, domain/va/tallies]`, книгами `tallies` (переносимая), `notes` (`from: va/notes/`), `rolls` (`from: va/rolls`), `domain.shared`, видом токена с `unit`, `door.routes`; `vb` без них | `domain/placed/va/` даёт и `domain/placement/va/*`; копия своей книги — и точный ключ `domain/va/tallies/local` (`CLUSTER` не задан — `local`), не префикс; запись источников собираемых книг — префикс и точный ключ; `domain/shared`, `domain/topology`, `domain/member-topology`, `domain/grants` — только у `vaworker` (там же) | P/02.5 N1.4 `<s>worker`, N2, N3 шаг 3 (C02-OWN-BOOK-HOLDER-01) |
| `v11-controller-cross-tables` | `vb`, `vc`, `vd` — как в `v6-near-about-ref`; `va` с таблицей `shelves` и `requests` (`per_person`) | контроллер связной подсистемы читает таблицы `va`, `va/decommissioned/*`, `va/controller/placement_intent`, не читает `va/requests/*`, `va/asked/*` и не пишет таблицу `va` (там же) | P/02.5 N1.4 `<s>controller` (решение «Архитектора» 2026-10-27) |
| `v12-check-rights` | `va` — байт в байт `v1-base`; `check.tsv` | `--check`: ровно вывод прав по N1.4 (`same`) — код 0; вывод без роли `vaworker`, с записью строк единиц воркером, с иной группой воркера, без `delete` контроллера, с лишним полем файла — код не 0 (аудит Gemini P/02, свойство 24; `same` — решения «Архитектора» 2026-10-30, P/02 пп. 1, 2) | P/02.5 N1.4, N2, N3 шаг 4, «установить», N4 |
| `v13-refused-idem-read` | `va` — байт в байт `v2-requests`; `vb` с `worker.reads: [va/idem/k1]`; `refused` | объявление воркера прямо называет строку внутри `va/idem/` — отказ генерации до файла, код 2, манифест `vb` (свойство 25) | P/02.5 N1.4 общие правила, N4 (C02-IDEM-ASKED-EXPLICIT-READ-01) |
| `v14-refused-secrets-reads-nested` | `va` с `secrets.readers: {va/vault/: [worker]}`; `vb` с `secrets.reads: [va/vault/public/]`; `refused` | элемент `secrets.reads` строго вкладывается в секретный префикс другого манифеста — отказ генерации до файла, код 2, манифест `vb` (свойство 25) | P/02.5 N3 шаг 4, N4 (C02-SECRETS-READS-INTERSECTION-01) |
| `v5-secret-domainworker` | `va` с `secrets.readers: {va/vault: [domainworker]}` и `kept` | `domainworker` → `vadomain` читает, прочие — нет (R6) |

### Исходный отрывок 5

Проверка R36-05 (с 2026-10-30 — случаи `worker_writes_unit_rows`, `worker_writes_undeclared` — refused, `worker_writes_declared_ok`, `worker_writes_declared_list_ok` — ok приёмки главы 2.1; аудит покрытия P/02, B06): worker.writes с именем собственного unit.rows даёт refused:reference, без генерации прав. Объявленная таблица воркера допустима, console для неё только читает; это не распространяется на строку единицы. Сверить все общие манифесты и все пути генератора, включая списковую форму tables; в текущей TSV нет запуска загрузчика на таком изменённом манифесте.

### Исходный отрывок 6

Сценарий 11 — метки просьб `objects/<s>/commands/*` (P/06.4 N1.5 mark): воркер манифеста с `requests` пишет, читает и
удаляет свою, чужого манифеста — 403, контроллер — 403 (N1.4; журнал cammeta-go, урок 8 № 4).

### Исходный отрывок 7

`--check` и отказы генератора до файла — формы «Архитектора» `check.tsv` и `refused` (выше): `v12-check-rights`,
`v13-refused-idem-read`, `v14-refused-secrets-reads-nested`. Случай `check.tsv` с кодом `0` — `same` варианта `v12-check-rights`:
ровно вывод прав по N1.4 после решений «Архитектора» 2026-10-30 (вопросы норм аудита Gemini, P/02): ресурсу — `<M>/<holds.table>/*`
только у манифеста с `holds`, `<s>/holds/*` не выдаётся (п. 1, C02-RESOURCE-HOLDS-TABLE-01); отрицание секрета нечитателю — только
если после уже выданных отрицаний его права ещё достают образец (п. 2, C02-NONREADER-DENY-AFTER-01); метки
`objects/<s>/commands/*` консоли — только у манифеста с `requests` (как у воркера; у `va` их нет). Прочие файлы `check/` — этот вывод с
одной правкой. Чтением остаются: неравенство

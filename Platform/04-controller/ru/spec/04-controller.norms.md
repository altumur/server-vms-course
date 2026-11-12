# P/04 — Контроллер: нормы

Текст производный от `spec/04-controller.norms.md`, руками не правится: источник — английский [`spec/04-controller.norms.md`](../../spec/04-controller.norms.md), правка идёт в него, русский пересобирается переводом.

Канон урока. Лекция (`ru/04-controller.md`, для человека, в выгрузку не входит), [инструкция](04-controller.README.md), [жизненный цикл](../lifecycle.md),
векторы [`order`](../vectors/order/README.md),
[`shrink-victim`](../vectors/shrink-victim/README.md) и [`shrink-allowed`](../vectors/shrink-allowed/README.md). Своего HTTP-контракта у урока нет (`P/04 no-openapi`): двери, через
которые оператор говорит с контроллером, — двери консоли ([P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N2; `/where` — [глава 6.5](../../../06-console/ru/spec/06.5-console.norms.md)). Действующие зависимости — [договор наблюдения](../../../common/ru/contracts/observation.md), нынешние семейства данных ниже и связанные двери консоли. Идентификаторы требований и чеклиста сохранены; полный состав завершения задают файлы приёмки.

## Указатель

| Тема | Требования | Файлы |
|---|---|---|
| `input_owners` | P/04-R003, P/04-R004, P/04-R005, P/04-R006, P/04-R024, P/04-R076, P/04-R459, P/04-R460 | `forms/README.md`, `lifecycle.md`, `Platform/common/data/catalog.tsv` |
| `time_fields` | P/04-R002, P/04-R076, P/04-R087, P/04-R089, P/04-R091, P/04-R094, P/04-R107, P/04-R113, P/04-R174, P/04-R217 | `Platform/common/contracts/env-file.md`, `Platform/common/contracts/observation.md` |
| `turn_fence` | P/04-R026, P/04-R032, P/04-R036, P/04-R038, P/04-R069, P/04-R209, P/04-R212, P/04-R222 | `Platform/common/contracts/turn.md`, `data/placement-turn.schema.json` |
| `intent_read` | P/04-R020, P/04-R021, P/04-R076, P/04-R214, P/04-R217, P/04-R500 | `Platform/common/contracts/observation.md`, `data/placement-intent.schema.json` |
| `admission_reserve` | P/04-R022, P/04-R023, P/04-R149, P/04-R155, P/04-R232, P/04-R243, P/04-R288, P/04-R517, P/04-R520, P/04-R521 | `data/placement-intent.schema.json`, `Platform/common/contracts/pool.md` |
| `intent_commit` | P/04-R027, P/04-R036, P/04-R037, P/04-R038, P/04-R243, P/04-R244, P/04-R245, P/04-R246, P/04-R247, P/04-R248, P/04-R253, P/04-R254, P/04-R259, P/04-R301, P/04-R490, P/04-R517, P/04-R520, P/04-R521 | `Platform/common/contracts/turn.md`, `data/workers.schema.json` |
| `group_atomicity` | P/04-R023, P/04-R029, P/04-R156, P/04-R235, P/04-R237, P/04-R239, P/04-R245, P/04-R246, P/04-R247, P/04-R261 | `Platform/common/contracts/group-of.md`, `data/placement-intent.schema.json` |
| `placement_key_size` | P/04-R028, P/04-R031, P/04-R250 | `data/placement-intent.schema.json`, `forms/refusals.tsv` |
| `manifest_revision` | P/04-R058, P/04-R076, P/04-R094, P/04-R116, P/04-R212, P/04-R214, P/04-R262, P/04-R405 | `data/placement.schema.json`, `data/placement-turn.schema.json`, `data/placement-intent.schema.json` |
| `pool_labels` | P/04-R005, P/04-R034, P/04-R081, P/04-R083, P/04-R150, P/04-R152, P/04-R160, P/04-R287, P/04-R288, P/04-R337 | `Platform/common/contracts/labels.md`, `Platform/common/contracts/pool.md` |
| `home_preference` | P/04-R158, P/04-R268, P/04-R290 | `Platform/common/contracts/pool.md` |
| `near_preference` | P/04-R034, P/04-R133, P/04-R157, P/04-R262 | `vectors/near-of/README.md`, `Platform/common/contracts/pool.md` |
| `affinity_places` | P/04-R159, P/04-R288, P/04-R334, P/04-R527, P/04-R528, P/04-R529, P/04-R531 | `Platform/common/contracts/pool.md` |
| `choice_ranks` | P/04-R033, P/04-R035, P/04-R151, P/04-R286, P/04-R287, P/04-R288, P/04-R290, P/04-R291, P/04-R292 | `Platform/common/contracts/pool.md`, `data/placement.schema.json` |
| `slot_observation` | P/04-R014, P/04-R015, P/04-R039, P/04-R046, P/04-R196, P/04-R197, P/04-R208, P/04-R313 | `Platform/common/contracts/observation.md`, `forms/slot-fate.tsv` |
| `release_permission` | P/04-R040, P/04-R041, P/04-R042, P/04-R043, P/04-R044, P/04-R045, P/04-R046, P/04-R117, P/04-R119, P/04-R198, P/04-R310, P/04-R311, P/04-R318 | `forms/slot-fate.tsv`, `forms/slot-release.tsv`, `data/controller-pass.schema.json` |
| `leaving` | P/04-R035, P/04-R047, P/04-R048, P/04-R267, P/04-R287, P/04-R322 | `forms/README.md`, `Platform/common/contracts/pool.md` |
| `placeable_set` | P/04-R025, P/04-R162, P/04-R163, P/04-R165, P/04-R325, P/04-R327, P/04-R479, P/04-R481 | `vectors/order/README.md`, `vectors/shrink-allowed/README.md` |
| `unit_cleanup` | P/04-R025, P/04-R120, P/04-R124, P/04-R134, P/04-R269, P/04-R276 | `Platform/common/contracts/row-check.md`, `data/controller-pass.schema.json` |
| `order_absolute` | P/04-R050, P/04-R052, P/04-R107, P/04-R339, P/04-R355, P/04-R356, P/04-R494, P/04-R541 | `vectors/order/README.md`, `data/want.schema.json` |
| `growth_room` | P/04-R085, P/04-R330, P/04-R332, P/04-R333, P/04-R337, P/04-R357 | `vectors/order/README.md`, `Platform/common/contracts/presence-lock.md` |
| `shortage_estimate` | P/04-R053, P/04-R130, P/04-R139, P/04-R149, P/04-R325, P/04-R327, P/04-R334, P/04-R527, P/04-R528, P/04-R529, P/04-R531, P/04-R532 | `vectors/order/README.md`, `data/controller-pass.schema.json` |
| `want_deadline` | P/04-R107, P/04-R131, P/04-R191, P/04-R329, P/04-R330, P/04-R340, P/04-R356, P/04-R482 | `forms/runtime-constants.tsv`, `data/want.schema.json` |
| `shrink` | P/04-R051, P/04-R111, P/04-R194, P/04-R327, P/04-R341, P/04-R343, P/04-R348, P/04-R349, P/04-R350, P/04-R351, P/04-R352, P/04-R353, P/04-R482, P/04-R499 | `forms/README.md`, `vectors/shrink-victim/README.md`, `vectors/shrink-allowed/README.md` |
| `decommission_plan` | P/04-R054, P/04-R055, P/04-R056, P/04-R089, P/04-R091, P/04-R094, P/04-R359, P/04-R361, P/04-R363, P/04-R369, P/04-R371, P/04-R495, P/04-R504 | `data/decommission-pending.schema.json`, `data/decommissioned.schema.json` |
| `decommission_release` | P/04-R094, P/04-R101, P/04-R376, P/04-R378, P/04-R381 | `data/decommission-pending.schema.json`, `Platform/common/contracts/turn.md` |
| `decommission_cleanup` | P/04-R094, P/04-R103, P/04-R384, P/04-R385, P/04-R386, P/04-R387, P/04-R388, P/04-R390, P/04-R392, P/04-R393, P/04-R395, P/04-R507, P/04-R510, P/04-R511, P/04-R513 | `data/decommission-pending.schema.json`, `Platform/common/contracts/turn.md` |
| `decommission_finish` | P/04-R054, P/04-R055, P/04-R056, P/04-R091, P/04-R094, P/04-R105, P/04-R353, P/04-R395, P/04-R399, P/04-R401, P/04-R403, P/04-R404, P/04-R495 | `data/decommissioned.schema.json`, `data/decommission-pending.schema.json` |
| `snapshot_fields` | P/04-R011, P/04-R064, P/04-R137, P/04-R167, P/04-R168, P/04-R169, P/04-R170, P/04-R413, P/04-R415, P/04-R417, P/04-R498, P/04-R548, P/04-R549 | `data/snapshot.schema.json`, `data/snapshot-unplaced.schema.json` |
| `snapshot_ceiling` | P/04-R068, P/04-R171, P/04-R182, P/04-R419, P/04-R421 | `forms/refusals.tsv`, `data/snapshot.schema.json` |
| `table_snapshot` | P/04-R012, P/04-R013, P/04-R062, P/04-R174, P/04-R175, P/04-R177, P/04-R178, P/04-R181, P/04-R182, P/04-R183, P/04-R411, P/04-R412, P/04-R555, P/04-R556 | `data/snapshot-tables.schema.json`, `forms/runtime-constants.tsv` |
| `report_cycle` | P/04-R007, P/04-R113, P/04-R124, P/04-R134, P/04-R137, P/04-R139, P/04-R142, P/04-R279 | `data/controller-pass.schema.json`, `forms/README.md` |
| `startup_schema` | P/04-R059, P/04-R060 | `forms/daemon-flags.tsv`, `lifecycle.md`, `Platform/common/contracts/schema.md` |
| `power_pull` | P/04-R016, P/04-R017, P/04-R065, P/04-R066, P/04-R202, P/04-R203, P/04-R204, P/04-R205, P/04-R206, P/04-R207, P/04-R208, P/04-R430, P/04-R431 | `Platform/common/contracts/observation.md`, `lifecycle.md` |
| `refusals` | P/04-R067, P/04-R068 | `forms/refusals.tsv` |

В N5 и чеклистах `sc. NN` или `scenario NN` обозначает номерной сценарий, а идентификатор `s…` — шов CALL; это имена приёмочных доказательств этого урока, если не назван другой владелец. Абзац с началом «**Scope: production.**» относится только к боевой квалификации; каждое требование без метки обязательно любой реализации. Метки чеклиста `[test]`, `[reading]` и `[stand]` имеют смысл P/01.1-R151.

## N0 Словарь слов

Нормативные слова — по [канону курса](../../../common/ru/NORMATIVE-TERMS.md).

Правила модуля — [P/01.1 N0](../../../01-store/ru/spec/01.1-store.norms.md#n0-словарь-слов).

Для этого владельца действуют [общие эксплуатационные обязанности](../../../common/ru/contracts/production-obligations.md). MB4: ход защищает только записи хранилища с условием; внешние действия требуют независимого забора, объявленного их владельцем. Действуют также Q4 о владельце повторов и Q5 об ограничении ресурсов.

## N1 Форма

**Время.** Поля времени строк и объектов урока — время по [канону N0 P/01.1](../../../01-store/ru/spec/01.1-store.norms.md#время-в-строке): `<sub>/placement/<id>` — `at`; `platform/doors/<host>` — `since`, `at`; `platform/drain` — `at`; `platform/decommission/<host>` — `at`; `<sub>/decommissioned/<host>` — `asked_at`, `at`; `<sub>/decommission-pending/<host>` — `asked_at`, `at`; `<sub>/controller/placement_intent` — `at`; `<sub>/want/<host>` — `at`; объект `<sub>/controller/pass` — `at`, `last_success`; объект `<sub>/snapshot/<worker>` — `ts`.

**Данные** ([каталог](../../../common/data/catalog.tsv)):
- владеет: `<sub>/placement/<id>`, `<sub>/workers/<name>`, `<sub>/want/<host>`, `<sub>/decommissioned/<host>`, `<sub>/decommission-pending/<host>`, `<sub>/controller/placement_turn`, `<sub>/controller/placement_intent`, `<sub>/controller/pass`, `<sub>/snapshot/<worker>`, `<sub>/snapshot/unplaced`, `<sub>/snapshot-tables/<table>`;
- пишет: `<sub>/slots/<name>` (cas), `<sub>/<manifest:unit.rows>/<id>` (delete), `<sub>/<manifest:domain.books.from>/<slot>` (delete), `<sub>/state/<name>/<id>` (delete), `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events or objects root>/<path>/%h<sha256>.name` (create), `<objects root>/<dir>/~lock` (create);
- читает: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `<sub>/heartbeats/<name>`, `<sub>/slots/<name>`, `<sub>/holds/<place>`, `<sub>/<manifest:unit.rows>/<id>`, `<sub>/state/<name>/<id>`, `platform/schema`, `platform/resources/<server>/heartbeat`, `<sub>/policy`, `platform/servers/<host>`, `platform/doors/<host>`, `platform/drain`, `platform/decommission/<host>`, `<sub>/<manifest:tables>/<name>`, `/etc/w2c/tls/<role>/server.key`.

Таблицы мест и связей (`places.table`, `places.wanted`, `affinity.table`, N1.3) и таблицы `domain.view_tables` (N1.3b) контроллер читает строками `<sub>/<manifest:tables>/<name>`.

Контроллер пишет журнал `unit.unplaced_deleted` (N3 шаг 8 прохода) и тревоги (`workers.raise_failed` в N1.4; hung/unsure на шаге 3) в `audit/<role>` и `audit.alarms/<role>`; `%h<sha256>.name` он пишет по [договору журнала событий](../../../common/ru/contracts/event-journal.md), `journal`, `writer`, «File names».

Контроллер использует ключ своего набора для дверей ресурса по HTTPS ([P/02.4 N1.6](../../../02-installer/ru/spec/02.4-installer.norms.md), `roles`).

Строки `<sub>/policy`, `platform/servers/<host>`, `platform/drain`, `platform/decommission/<host>` (пишет консоль, P/06.6) и `platform/doors/<host>` (пишет ресурс, P/05) в N1.1 — форма, которую читает контроллер; владелец строки — процесс-писатель (каталог).

### N1.1 Строки контроллера

Строки контроллера и заимствованные строки используют формы и правила полей ниже.

**`<sub>/placement/<id>`**: — решение; писатель — контроллер. **`<sub>/placement/<id> — worker`**: \<имя воркера\> | "" — "" — не размещена; при active intent действует общее решение N1.5. **`<sub>/placement/<id> — reason`**: \<строка для человека\> — непустая; грамматика — N3 «причина». **`<sub>/placement/<id> — at`**: \<стенные секунды контроллера\>. **`<sub>/placement/<id> — rev`**: \<десятичное целое ≥ 1\> — +1 на каждую запись. **`<sub>/placement/<id> — manifest_rev`**: \<ревизия манифеста, под которой принято решение\> — обязательно для нынешнего решения; отсутствие нечитаемо и не дописывается (P/02.3)

**`<sub>/workers/<имя>`**: — назначение; производное от строк размещения. **`<sub>/workers/<имя> — units`**: \<список id по правилу списка P/06.1 N1.2 (через запятую, иначе массив JSON)\> — отсортирован. **`<sub>/workers/<имя> — rev`**: \<десятичное целое ≥ 1\> — +1 только при изменении списка

**`<sub>/policy`**: — писатель — консоль; читает контроллер. **`<sub>/policy — servers`**: shared | distinct — иное значение или ключ при чтении — умолчание манифеста; при записи — отказ

**`platform/servers/<host>`**: — писатель — консоль. **`platform/servers/<host> — labels`**: \<метки через запятую\> — "" — ни одной; строка побеждает метки узла

**`platform/doors/<host>`**: — писатель — ресурс сервера; форма — P/05 N1.4 door_row (семья doors). **`platform/doors/<host> — room.<sub>, live.<sub>`**: — читает контроллер — свободно(s) N3 «нехватка()»; элемента нет, не читается или unknown — сервер не кандидат в заказ

**`platform/drain`**: — писатель — консоль; одна строка на кластер. **`platform/drain — server`**: \<сервер\>; at: \<момент\>

**`platform/decommission/<host>`**: — писатель — консоль. **`platform/decommission/<host> — by`**: \<кто\>; at: \<момент\>; why: \<слова\>; gone: "true"? — gone — подтверждение «сервера нет», когда ресурс никогда не слышали

**`<sub>/decommissioned/<host>`**: — писатель — контроллер; снимается при отзыве запроса. **`<sub>/decommissioned/<host> — asked_at, at`**: \<стенные секунды запроса консоли и отметки контроллера\>. **`<sub>/decommissioned/<host> — slots, units, holds`**: имена отданных слотов, id снятых единиц и места удержаний по правилу списка P/06.1 N1.2; "" означает отсутствие элементов. Элементы — соответственно имена слотов (P/03.2 N1.4), id единиц (P/06.1 N1.3), имена мест удержания (P/03.2 N1.3). Это имена, а не числа; "0" не является элементом.

**`<sub>/decommission-pending/<host>`**: — unfinished controller progress, never the final decommission mark. **`<sub>/decommission-pending/<host> — state`**: prepared | cleaning | finalizing. **`<sub>/decommission-pending/<host> — request_index`**: `<version>` — exact fixed platform/decommission/`<host>` index. **`<sub>/decommission-pending/<host> — asked_at, at`**: `<time>` — request at and plan acceptance time. **`<sub>/decommission-pending/<host> — manifest_rev`**: `<revision>`. **`<sub>/decommission-pending/<host> — remaining`**: [{name: \<slot name\>, index: `<version>`}, ...] — JSON; original versions, no later substitution. **`<sub>/decommission-pending/<host> — from`**: [\<owned from prefix\>, ...] — fixed full prefixes, each ending in /

**`<sub>/decommission-pending/<host> — released, skipped`**: [\<slot name\>, ...]. **`<sub>/decommission-pending/<host> — current`**: [\<slot name\>, ...] — at most BATCH_WRITES - 1, the confirmed release chunk

**`<sub>/decommission-pending/<host> — cleanup_index`**: "" | `<version>` — empty means the progress row's own index, before its first cleanup rewrite. **`<sub>/decommission-pending/<host> — slot_cursor, from_cursor`**: `<count>` — next current slot and its next from prefix

**`<sub>/decommission-pending/<host> — units, holds`**: `<lists>` — fixed final-mark metadata, same form as decommissioned

**`<sub>/want/<host>`**: — писатель — контроллер, cas со стражем placement_turn (N1.5). **`<sub>/want/<host> — want`**: \<десятичное 1…WANT_NUM_MAX\> — абсолютная цель числа процессов роли на сервере, базовый `<prefix>`-\<сервер\>-1 входит. **`<sub>/want/<host> — at`**: \<момент записи\> — диагностика; сроки — по наблюдению версии строки (N1.4 сроки). **`<sub>/want/<host> — by`**: \<экземпляр контроллера\> — диагностика; полномочие — cas и страж placement_turn. **`<sub>/want/<host> — why`**: \<непустая причина\> — грамматика N3 «shortage(), order()…»

**`<sub>/want/<host> — retiring?`**: необязательное имя воркера, выбранного для сокращения (N3 «сократить»).

Строка `<sub>/want/<host>` существует, кроме pending/окончательного вывода, для установленной роли на сервере манифеста с `grows: true` (N3 «строка заказа»). Удаляют эту строку только вывод сервера или удаление роли; сокращение пишет want 1. Строку читают контроллер и консоль (`workers_wanted`, P/06.5).

### N1.2 Отчёт прохода

Объект `<sub>/controller/pass`, пишется в конце каждого прохода; читают консоль (ряды `<sub>_reconcile_last_pass_age_seconds`, `<sub>_reconcile_pass_seconds`, `<sub>_reconcile_failures`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — текст») и воркеры (`names_given`, `hung_move_after` — P/03.2). Поля ниже ДОЛЖНЫ быть; реализация МОЖЕТ добавлять свои счётчики. Отчёт прохода использует все поля и значения полей, заданные ниже.

**`pass — at`**: \<момент конца управляющей части, до публикации снимков\>. **`pass — ok`** — boolean: true означает, что управляющая часть дошла до конца, все её входы прочитаны и ни в одной управляющей записи не отказано; иначе false. **`pass — error`** — текст последней ошибки или "". **`pass — failures`** — число ошибок. **`pass — last_success`** — момент последнего успешного завершения управляющей части. **`pass — seconds`**: \<длительность управляющей части, без последующей публикации снимков и отчёта\>

**`pass — manifest_rev`** — ревизия манифеста этого контроллера. **`pass — manifest_behind`** считает строки, запись которых нынешний проход откладывает из-за отставшего манифеста; строку считают один раз за проход.

**`pass — names_given`**: {\<имя слота\>: \<версия строки слота, при которой имя отдано\>}

**`pass — hung_move_after`**: \<секунды предела зависания, действующего у этого контроллера\>

**`pass — fates`** — `{<name>: {fate, server, why, rev, since}}` только занятых неотданных слотов: holder непуст, released — false, не true и не taking (договор слота, States). У каждого элемента `pass.fates` значение `since` — момент входа слота в эту судьбу по часам контроллера: смена судьбы меняет since; первая встреча слота не является этим моментом.

**`pass — diverged`**: \<назначений, исправленных sync\>. **`pass — unplaced`**: \<единиц без воркера, кроме снятых с эксплуатации\>. **`pass — garbled`**: \<строк единиц, которые не читаются\>. **`pass — expired_kept`**: \<ручных строк с прошедшим сроком, которые срок снял, но не удалил: адресат с fixed-полями или about не по id (N3 «проход()» шаг 8)\>

**`pass — snapshot_state_garbled`**: \<состояний единиц, не вошедших в шард снимка нынешнего цикла: строка состояния не читается своим типом (N1.3a; P/03.6 N1.7 unreadable)\>. **`pass — state_swept_total`**: \<строк состояния, снятых уборкой осиротевшего и после удаления строки единицы (N3 шаг 8a)\>. **`pass — snapshot_tables_refused`**: \<таблиц N1.3b, которые нынешний цикл заменил заглушкой: объект больше SNAPSHOT_TABLE_MAX\>. **`pass — snapshot_rows_garbled`**: \<строк единиц, не вошедших в шард снимка нынешнего цикла: поле snapshot: не читается своим типом (N1.3a garbled)\> — P/01.1 N0 «Stability of output»

**`pass — reach_moves_total, slots_released_total, unplaced_deleted_total, servers_decommissioned_total, workers_hung, workers_hung_moved_total, workers_unsure_moved_total, name_conflicts`**: \<числа\>

**`pass — unplaceable`**: {`<id>`: `<why>`} — единицы без места этого прохода и непустая причина; из него консоль берёт why /unplaceable и reason 404 /where/`<id>` у неразмещённой (N2.2)

**`pass — short`**: — только при placement.grows: true; элемент на каждый набор меток с ждущими - {labels: [\<метки\>], units: \<точная неотрицательная целая сумма весов ждущих единиц\>, workers: \<нужно процессов сверх живых и ёмкости в пути\>, groups: \<ждущих групп\>, ordered: \<заказано этим проходом\>, withheld?: \<слова, почему не заказано\>} labels — каноническая запись: уникальные метки по возрастанию, повтор схлопывается; groups — всегда, 0 тоже (обязателен в форме); свои счётчики элемента МОЖНО по прежней форме count; стандартные поля сохраняют формы; приёмка сравнивает названные поля; пустой набор в словах why — any labels; набор без вычислимого per — тот же элемент: workers 0, ordered 0, withheld «no positive capacity estimate»; ряд `<sub>`_workers_withheld{labels} (P/06.5 /metrics) — у каждого набора отчёта прохода, ноль тоже

**`pass — wants`**: {\<сервер\>: {want, live, pending, retiring?, why, state}} — только при grows: true; live — живые процессы роли сервера, pending — в пути(s) по пульсам (N3); state: ok | raising | raise_failed | no_base. **`pass — raise_failed`**: {\<сервер\>: {since, times}} — сервер «failed to raise»: since — момент снятия заказа, times — подряд

**`pass — near_waiting`**: [\<подсистема\>…] — только при placement.near, чьего near.sub нет в каталоге манифестов этого прохода: сродство ждёт её установки (N1.3 near); иначе поля нет

Нынешние reader и writer одинаково требуют expired_kept, snapshot_state_garbled и state_swept_total как неотрицательные count. Если в нынешнем отчёте прохода отсутствует или неверен `expired_kept`, `snapshot_state_garbled` или `state_swept_total`, действует прежний исход unreadable для этих обязательных счётчиков. В отчёте прохода `expired_kept` и `snapshot_state_garbled` принадлежат нынешнему циклу; `state_swept_total` накапливает подтверждённые удаления с нуля этого процесса.

Нынешние reader и writer снимка одинаково требуют ровно один допустимый массив unit.rows, включая пустой; отсутствие массива или несколько массивов нечитаемы. Отсутствие объекта снимка до его первой публикации — отдельный случай от нечитаемого нынешнего объекта снимка.

Весовые агрегаты short[].units, waiting и load — точные неотрицательные целые без потолка common.uint53; их JSON-выход имеет целочисленную запись, без округления или насыщения через binary64/int64. Отдельные веса/ёмкости и прочие count сохраняют формы. Собственные счётчики short остаются count; расширение агрегата не меняет предела записи полного сериализованного объекта.

Цикл завершает управляющую часть и отдаёт placement turn, затем пытается опубликовать unit snapshots и table snapshots и только потом пишет один отчёт с их счётчиками этого же цикла. At, seconds, last_success, ok и failures описывают только управляющую часть. Ошибки снимков сохраняют нынешние исходы/журнал/счётчики и не становятся failures управления. Три снимочных счётчика начинают с нуля каждый цикл; следующий не сбрасывает и не забирает незаконченный предыдущий. После возврата подтверждённых, отказных, ошибочных или неподтверждённых исходов попыток публикации окончательный отчёт пишется один раз, без позднего дописывания. state_swept_total не сбрасывается.

### N1.3 Ключи размещения и их смысл

Форма ключей — P/02.1 (N1.2). Здесь — что каждый значит для контроллера и умолчание. Ключи размещения имеют смысл и умолчания ниже; их входной формой владеет P/02.1.

**`capacity: {from, default, unit_mb, base_mb}`.** ёмкость — [договор пула](../../../common/ru/contracts/pool.md) `capacity`; причина — поле `fates.<worker>.why` отчёта прохода (N1.2). Умолчание: `from: capacity`; `default` обязателен.

**`headroom: {from}`.** запас — поле пульса, которое называет подсистема; контроллер его не читает (ни подбор, ни судьба слота, ни отчёт прохода); его показывает консоль — ряды `worker_headroom{worker,server}` и `headroom` ([P/06.5](../../../06-console/ru/spec/06.5-console.norms.md) N3 «/metrics — текст»). Умолчание: `from: headroom`.

**`weight: {field, default}`.** вес единицы — `int`-поле строки ≥ 1, при отсутствии поля — weight.default ≥ 1; неверное присутствующее значение не заменяется default: строка единицы нечитаема (`garbled` отчёта прохода), единица не размещается и не снимается, причина — в `unplaceable`; нагрузка = Σ весов. Умолчание: без ключа — вес 1 у всех.

**`constraint`.** `none` \| `labels-subset`: метки единицы ⊆ меток воркера. Метки единицы — её поле `labels` типа `list` (поля нет — пустой набор, ограничение выполнено); метка — по [азбуке меток](../../../common/ru/contracts/labels.md); метки воркера — строка `platform/servers/<host>` или метки узла. Умолчание: `none`.

**`tie_break`.** `most-free-capacity` — единственное слово. Умолчание: оно же.

**`servers`.** `shared` \| `distinct`: при `distinct` на одно место нести единицы может один воркер — с наибольшей нагрузкой, при равенстве первый в слотовом порядке P/03.2 N1.4; остальные простаивают. Умолчание: `shared`; строка `policy` переопределяет. **`place_by`.** что считать местом при `distinct` — [договор пула](../../../common/ru/contracts/pool.md) `place`, хранитель — `keeper`; единицы `distinct` получает только хранитель непустого места. Умолчание: `server`.

**`places: {table, where, server_field, lease, wanted}`.** таблица мест и строка удержания `<sub>/holds/<place>` (P/03.2 N1.3); `lease: strict` — строгое место; `wanted` — таблица подсистемы: строка с именем места говорит, что месту нужен держатель, причину знает подсистема (N3 «нехватка()»). Умолчание: —.

**`spread_by`.** поле: две единицы с одним значением не на одном сервере; отсутствующее или пустое значение в разведении не участвует — единица без значения не ограничивает и не ограничивается (пара к `group_by`: пустое — не группа). Умолчание: —.

**`group_by: {field, cut_at}`.** группа — одно значение поля (для `url` — хост по `cut_at: host`); размещается только целиком на одном воркере. Что такое группа, хост в одном написании, `none`, нечитаемый хост, «not in a group» и отказ — [договор группы по хосту](../../../common/ru/contracts/group-of.md) (вектор [`group-of`](../../../common/ru/vectors/group-of/README.md)). Умолчание: —.

**`near: {sub, by, of, prefer}`.** предпочтение: рядом с держателем соседа — единицы подсистемы `sub` (каталог манифестов). Умолчание: `none`. **`near: {sub, by, of, prefer}`.** Моё значение — поле `by` моей строки, без `by` — мой id; значение соседа — его поле `of`, без `of` — его id; соседи — живые строки `sub`, чьё значение равно моему. **`near: {sub, by, of, prefer}`.** Среди нескольких соседей сначала те, что совпали с `prefer` — И по полям, ИЛИ по списку значений; значение поля — скаляр (равенство) или список (как `affinity.strict`); поле `prefer` — путь: сегмент через `.` — шаг по полю-ссылке соседа к строке, которую оно называет (`home.kind` — поле `kind` строки, названной полем `home` соседа); среди равных — по id соседа (байты UTF-8). **`near: {sub, by, of, prefer}`.** Предпочтителен воркер, держащий выбранного соседа; держателя нет — предпочтения нет (векторы [`near-of`](../vectors/near-of/README.md)). **`near: {sub, by, of, prefer}`.** Манифеста `sub` нет в каталоге — сродство не действует, единица размещается без него, строки `sub` контроллеру не нужны; подсистема — в `near_waiting` отчёта прохода (N1.2); сродство включается с прохода, на котором манифест `sub` появился в каталоге (N3 «проход()» шаг 1)

**`home`.** предпочтение, не фильтр: поле строки, называющее дом (значение — у первого члена в порядке UTF-8; значения нет — дома нет), или `near` — дом у соседа; следовать может лишь одна сторона пары. Умолчание: —. **`home`.** Поле — ссылка `ref` на таблицу мест `places.table`: дом — держатель названного места, воркер, чьё место (`place_by`, договор пула `place`) — имя этой строки; держателя среди пригодных нет (N3 «выбрать») — воркеры сервера из поля `places.server_field` этой строки, если поле непусто; иначе дома нет. **`home`.** Пустое поле сервера при держателе дому не мешает: дом — держатель (том без сервера). **`home`.** Другой воркер того же сервера при держателе — не дом: единица у него едет к держателю (N3 «проход()», шаг 7). **`home`.** Причина: `place_by` называет то, где лежат данные единицы; сравнение с сервером отдало бы её держателю другого места этого сервера, и шаг 7 её бы не вернул. **`home`.** Строки нет или она не читается — дома нет. **`home`.** Поле без `ref` — его значение и есть сервер: дом — воркеры, чей `server` равен значению. **`home`.** `ref` на иную таблицу (или `places` у манифеста нет) — дома нет: значение — id чужой строки, не сервер, и `places.server_field` у неё не назван.

**`affinity: {field, table, server_field, strict, exclusive}`.** фильтр: место из таблицы, которое принимает единицу; `admits: false` не берёт никого; связывающая строка ведёт единицу только на своё место. Умолчание: —. **`affinity: {field, table, server_field, strict, exclusive}`.** Место единицы — строка `table`, которую называет её `field` (значения нет или строки нет — affinity не действует). **`affinity: {field, table, server_field, strict, exclusive}`.** `strict` — предикат, который выбирает связывающие строки: строка связывающая, когда каждое поле `strict` равно значению или входит в список значений (И по полям, ИЛИ по списку); `strict` нет или `{}` — связывают все строки таблицы, несвязывающих нет. **`affinity: {field, table, server_field, strict, exclusive}`.** Связывающая строка ведёт единицу только к держателю своего места — воркеру, чьё место (`place_by`, P/03.2 N1.3) — имя строки; при непустом `server_field` строки — ещё и только если сервер воркера — этот (оба условия; другой воркер того же сервера с другим местом не годится); несвязывающая — предпочтение сервера `server_field`, не фильтр. **`affinity: {field, table, server_field, strict, exclusive}`.** `admits` проверяется у фактического места единицы. **`affinity: {field, table, server_field, strict, exclusive}`.** `exclusive: true` (только при `strict`, P/02.1) — связывающее место исключительное: его держатель принимает только единицы, связанные с этим местом, прочие на него не размещаются (как `admits` для чужих); воркер с таким местом других мест не берёт (P/03.2 N3 «place: take»); связывающая строка с пустым `server_field` — строгость по держателю места без проверки сервера

**`requires`.** `none` \| `resource`: при `resource` воркер пригоден, только пока ресурс его сервера не молчит. Умолчание: `none`.

**`grows`.** `true` — роль растёт по требованию: контроллер считает нехватку и заказывает процессы роли по серверам строкой `<sub>/want/<host>` (N3 «shortage(), order()…»). Умолчание: `false`.

**`retire_when: {state?, field, in, delete_after?}`.** единица со значением поля из `in` не размещается и снимается с причиной — значением. Умолчание: —. **`retire_when: {state?, field, in, delete_after?}`.** Без `state` поле — строки единицы; со `state` — поле значения действующего состояния `unit.state.<state>` (договор проверки строки «Состояние единицы» acts; нет действующего — не законченная).

**`retire_when: {state?, field, in, delete_after?}`.** `delete_after` — через N с после снятия по `retire_when` по часам контроллера строку удалить (N3 шаг 8): отсчёт — от первого прохода, на котором контроллер увидел единицу снятой по `retire_when`; проход, на котором она уже не снята (правка оператора сняла значение или действующее состояние), отсчёт снимает, новое снятие считает заново; после перезапуска контроллера отсчёт заново, как у `unplaced.delete_after`

**`ends: {field, never}`.** срок единицы: поле строки `field` (секунды Unix) ≠ `never` и не позже часов контроллера — единица не размещается, снимается с причиной `ends`, строка удаляется (N3 шаг 8); `never` — без срока. Умолчание: без ключа — срока нет; `never: 0`.

**`rebalance: {dead_band}`.** перебалансировка по запросу: пока разброс нагрузки меньше — не двигать. Умолчание: `0.10`.

**`unplaced: {delete_after}`.** строку единицы, которую никто не держит дольше N с по часам контроллера, контроллер удаляет; снятая по `retire_when` — тоже: её никто не держит. Умолчание: без ключа — никогда. **`unplaced: {delete_after}`.** У таблицы с `fixed`-полями (кроме поля-источника id) или с `about` не по id физически удаляются только строки с `made` (имя держит шаблон `key` заказчика, P/03.6 N1.6) — так же по `retire_when.delete_after` и `ends`; ручные строки такой таблицы срок не удаляет: `ends` снимает и не размещает, `delete_after` не удаляет, счёт `expired_kept` отчёта прохода; удаляет их оператор дверью.

**`unplaced: {delete_after}`.** Свои строки единиц МОЖЕТ удалять и воркер подсистемы по ключу `worker.deletes` — удаление с `cas` без права записи

### N1.3a Снимок

Объекты снимков единиц используют оболочку, состав и правила публикации ниже. **`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced`**: — объекты; писатель — контроллер; имя воркера unplaced — отказ {cluster, worker: \<имя\> | null, ts, `<rows>`: [{id, revision, \<поля snapshot:\>, state?, worker, server}]} worker: имя воркера шарда; null — у шарда unplaced и у шарда ушедшего воркера. **`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — cluster`**: имя установки — CLUSTER окружения (договор файла окружения «Переменные окружения»; имя члена домена, [P/08.1](../../../08-domain/ru/spec/08.1-domain.norms.md) N1.1); не задано — "local" (вне домена)

**Поля снимка единиц.** Список snapshot манифеста выбирает поля: без ключа входят все поля, кроме *_secret, blob и авторского server; [] не включает ни одного из этих полей, но id, revision, worker и server остаются. Секрет, blob или server, явно названные в списке snapshot, дают отказ загрузки манифеста.

Адреса снимка единиц используют маску вывода P/06.2 N1.1a, как консоль: password → ***.

Объявленные поля единицы не включают platform_fields P/06.1 N1.2, включая deleted/worker: загрузчик P/02.1 отказывает такому манифесту. unit.rows отличается от cluster, worker и ts; пересечение с оболочкой снимка — отказ загрузки refused:form P/02.1.

**Состояние снимка единиц.** При объявленном unit.state поле state сопоставляет имена значениям действующего состояния по договору проверки строки, Unit state, как P/06.1 N2 State in the answer. Берут state.\<name\> из списка snapshot манифеста; без snapshot входят все состояния кроме cursor, [] не включает ни одного; нет действующего значения — нет имени, нет имён — нет поля state. Если строка состояния не читается своим типом, единица входит в снимок без этого состояния, snapshot_state_garbled отчёта прохода увеличивается.

**`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — publish`**: после отдачи turn управляющей частью и до одного окончательного отчёта этого цикла (N3 «проход()»); шарды ушедших воркеров — пустые; без единиц — пустой unplaced пустой шард — одна форма для всех: {cluster, worker: null, ts, `<rows>`: []} — поле `<rows>` есть, список пуст (как свидетель)

**`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — garbled`**: строка единицы, чьё поле snapshot не читается своим типом по values_by_type P/06.1 N1.2, в шард не входит; шард публикуется с остальными единицами, строка лога раз на серию и счёт `snapshot_rows_garbled` отчёта прохода N1.2 (P/01.1 N0 «Stability of output»)

До записи шарда единиц контроллер проверяет предел L двери ресурса P/05. max_bytes хранилища он не вычисляет: хранилище держит этот предел на put; TooLarge хранилища даёт тот же исход N4, сохраняя прежний шард. Размер шарда единиц — число байтов полного сериализованного объекта, включая оболочку, пустые шарды и фактическую запись ts, длина которой входит в размер. Ровно L байтов разрешено; выше L дают TooLarge до put_durable, не заменяя прежний шард. Для этого отказа размера диагностика — "N units on \<shard\>; snapshot is B bytes, limit is L bytes"; увеличение OBJECTS не поднимает предел двери ресурса.

### N1.3b Снимок таблиц

Вид домена показывает единицы с `domain.ref`; прочие строки единиц и таблицы консоли чужого кластера домену без этого объекта не видны. Манифест без `domain.ref` и единица без значения `ref` здесь видны.

Объекты снимков таблиц используют оболочку, состав и правила публикации ниже. **`<sub>/snapshot-tables/<table>`**: — объект; писатель — контроллер; \<таблица\> — ключ domain.view_tables манифеста (P/02.1, P/08.1 N1.4a): таблица tables или unit.rows {cluster, ts, refused?, rows: [{key, revision, fields, secrets?, labels?, about?, worker?, server?, phase?, status?}]}. **`<sub>/snapshot-tables/<table> — cluster`**: как у шарда, N1.3a

**`<sub>/snapshot-tables/<table> — ts`**: момент записи объекта; rows не менялись — объект не пишется, ts прежний: живость — не ts, а members[].state вида

**`<sub>/snapshot-tables/<table> — rows`**: строки хранилища, порядок — key в байтах UTF-8; key — имя строки (P/06.1 N1.6) или id единицы, revision — версия строки (P/06.1 N2 «Row revision»); снятой строки и надгробия в rows нет. **`<sub>/snapshot-tables/<table> — fields`** содержит только список domain.view_tables манифеста; значения используют свой тип по values_by_type P/06.1 N1.2. Отсутствующее исходное поле остаётся отсутствующим, без умолчания.

У снимка таблицы held_by таблицы мест следует P/06.1 N1.6 held_by.

Адреса снимка таблиц используют маску P/06.2 N1.1a. Ключи *_secret вырезают из JSON-значений полей на любой глубине (P/06.2 N1.4); сам список манифеста не называет поля *_secret (P/02.1).

**`<sub>/snapshot-tables/<table> — secrets`**: имена полей *_secret строки с непустым значением, по возрастанию в байтах UTF-8; нет таких — поля нет; значений нет: домену нужно знать, задан ли секрет

**`<sub>/snapshot-tables/<table> — labels, about`**: только у строк единиц — поле labels и значение поля about.field манифеста, названы они в списке или нет: ими судит право (договор права «Суд по цели»); нет значения — поля нет. **`<sub>/snapshot-tables/<table> — worker, server`**: только у строк единиц — из назначения; нет назначения — полей нет. **`<sub>/snapshot-tables/<table> — phase, status`**: только у строк единиц — phase и поля domain.view_status манифеста из элемента status[] пульса этой единицы (P/08.1 N1.4 status); элемента нет — полей нет

**`<sub>/snapshot-tables/<table> — garbled`**: строка, чьё поле из списка не читается своим типом, в rows не входит; счёт snapshot_rows_garbled, как N1.3a garbled

**`<sub>/snapshot-tables/<table> — ceiling`**: SNAPSHOT_TABLE_MAX из forms/runtime-constants.tsv полного сериализованного объекта; больше — вместо объекта заглушка {cluster, ts, refused: "too_large", rows: []} и snapshot_tables_refused отчёта прохода (N1.2). Заглушка, а не прежний объект: старый снимок выглядел бы живым. Бюджеты таблиц члена и общего состава — у агента (P/09.1 N1.2 tables_budget и связанные пределы приёма P/08); контроллер не задаёт вторые числа серверов, камер или измеренный общий потолок байтов домена.

**`<sub>/snapshot-tables/<table> — scope`**: объект есть у манифеста с domain.view_tables; domain.ref для него не нужен; ключ убран из манифеста — объект не снимается, агент его больше не несёт (договор приёма отчёта member_objects). **`<sub>/snapshot-tables/<table> — reader`**: только агент домена (P/09.1 N1.2); консоль кластера свои таблицы читает строками

### N1.4 Сроки и состояния судьи

Сроки и бюджеты ниже берутся из названных договоров-владельцев или `forms/runtime-constants.tsv`. **`constants — LOST_AFTER`**: договор наблюдения «Freshness» (значение там) — свежесть пульса («в последние LOST_AFTER») и запас после SLOT_TERM наблюдения неизменной версии слота. **`constants — HUNG_MOVE_AFTER`**: договор файла окружения «Константы и юниты» (значение там) — с; возраст наблюдаемой версии слота до предела hung/unsure/wait; из окружения контроллера, публикуется в отчёте

**`constants — ALIVE_EVERY`**: договор наблюдения «Состояние ресурса» (значение там) — ресурс переписывает at своей двери

**`constants — REACH_BUDGET`**: договор файла окружения «Константы и юниты» (значение там) — единиц за проход на переезды по достижимости; из окружения

**`constants — WRITE_CONFLICT_LIMIT`**: forms/runtime-constants.tsv — последовательные conflict одного изменения; после предела прежний отказ шага, без лишней попытки; барьеры сохраняются

**`constants — HOME_BUDGET`**: forms/runtime-constants.tsv — единица за проход на переезды домой

**`constants — WANT_GRACE`**: forms/runtime-constants.tsv — с; заказ, не поднятый сервером, снимается (N3 «снять по сроку»). **`constants — RAISE_QUIET`**: forms/runtime-constants.tsv — с; сервер «failed to raise» не получает заказов. **`constants — RAISE_FAILS_LOUD`**: forms/runtime-constants.tsv — отказов подряд — тревога workers.raise_failed повышенной важности

**`constants — SHRINK_AFTER`**: договор файла окружения «Константы и юниты» (значение там) — с; без нехватки — сокращение (N3 «shrink»); только у стенда — W2C_SHRINK_AFTER=\<с\> окружения контроллера: при заданной переменной контроллер пишет громкую строку журнала при старте; вне стенда переменная не задаётся. **`constants — SHRINK_BUDGET`**: forms/runtime-constants.tsv — единица за проход на перенос с сокращаемого воркера (как HOME_BUDGET)

сроки заказа и сокращения — стартовые значения политики; отсчёт — местные монотонные часы контроллера от первого наблюдения версии строки заказа (у SHRINK_AFTER — от первого прохода без нехватки), новый контроллер начинает с 0, повторная запись той же цели срок не продлевает, at — диагностика. WANT_GRACE — от первого прохода, где в пути(s) > 0 (N3), сброс — когда в пути(s) = 0: заказ поднят, затем процесс номера умер без смены версии строки — отсчёт с прохода, где номер снова в пути, не от прежней версии

**`resource_state`**: — ресурс сервера — live | unreachable | unknown | silent: одно определение для всех наблюдателей (контроллер, консоль) по их монотонным часам, правила по порядку — договор наблюдения (common/contracts/observation.md «Состояние ресурса»); исключает и двигает только silent

**`process_presence`**: — что ресурс говорит о процессе воркера: вывод [P/05 N1.4](../../../05-resource/ru/spec/05-resource.norms.md) `presence` по ключу `<sub>`/\<имя слота\> своей подсистемы; только из пульса ресурса в состоянии live: устаревший пульс со словом runs присутствия не даёт, и слот судится по resource_state; отсутствующее из полей workers, running, unknown — пустой список (частичный набор: running без workers — runs, workers без running — gone) runs | gone | unlisted | unknown — unknown — неподтверждённое чтение; silent — только состояние ресурса выше

**`fate`**: alive | wait | hung | hung_moved | unsure | unsure_moved | move | release. **`NAME_FATES`**: [move, hung_moved, unsure_moved, release] — + wait за пределом HUNG_MOVE_AFTER. **`MOVED_FATES`**: [move, hung_moved, unsure_moved]

Наблюдение версии, свежесть `LOST_AFTER` («в последние LOST_AFTER» — одно отношение `≤`) и `resource_state` — [договор наблюдения](../../../common/ru/contracts/observation.md); здесь — что они значат для судьи и пула контроллера (N3 «выбрать», «судьба»).

### N1.4a Отказ сервера: переезд

Исходы отказа сервера и наблюдение нового контроллера заданы ниже. **`power_pull — moves`**: единицы — по двум молчаниям (пульс воркера и слово ресурса), по допускам N3; (SLOT_TERM + LOST_AFTER) + проход — ориентир исправного стенда с заранее известными пульсами, доступным хранилищем и ёмкостью, не общий deadline; новый держатель берёт следующую эпоху; при shared и distinct одинаково; назад само не едет, кроме объявленного `home` (N3 «проход()», шаг 7, HOME_BUDGET)

**`power_pull — stays`**: архив на томе сервера — под старой эпохой, недоступен до возврата, не перестраивается, не теряется; единицы зависшего живого воркера — у него (один писатель)

**`power_pull — lost`**: открытый бакет и закрытые бакеты без подтверждённой зеркальной копии; один голос группы. RPO в длину бакета допустим лишь при подтверждённом зеркале всех закрытых; иначе потеря больше

**`power_pull — store`**: 1 из 3 — выборы за секунды; 2 из 3 — 503 unavailable через действующий P/01 -leader-wait, воркеры живут на последнем назначении по аренде и unconfirmed_max; восстановление — recover рукой (P/01.3 N3 «восстановить хранилище»)

**`power_pull — restore`**: P/05 N1.4 «Bucket restore»

**`power_pull — return`**: ресурс тянет бакеты; воркеры берут свободные имена; имя с истёкшим слотом — только по слову контроллера (P/03.2)

**`power_pull — presence`**: договор замка присутствия (common/contracts/presence-lock.md)

**`fresh_controller`**: впервые увиденное — только что изменилось; ничего не двигает первые LOST_AFTER (N3 «проход()», шаг 0). Это ограничивает суждения по молчанию и срокам; подтверждённый gone от живого ресурса — положительное свидетельство и важнее, гонку закрывает CAS

`stays`, `lost`, `store` и `return` описывают исходы отказа сервера; проход «вырвать питание» находится в N3.

### N1.5 Допуск размещения между контроллерами

У подсистемы один изменяющий размещение контроллер в каждый момент. Право задаётся строкой, а не наличием процесса: поздние записи прежнего держателя отсекаются guard хранилища.

Две служебные строки `<sub>/controller/placement_turn` и `<sub>/controller/placement_intent` принадлежат роли контроллера; читатели размещения также читают эти две строки. Двери хранилища и словарь операций остаются P/01.1.

Очередь размещения и намерение используют формы строк ниже. **`<sub>/controller/placement_turn`**: — строка; писатель — контроллер. **`<sub>/controller/placement_turn — holder`**: \<уникальная метка попытки захвата\> | "" — новая попытка не повторяет метку прежней. **`<sub>/controller/placement_turn — manifest_rev`**: \<ревизия манифеста\> — не убывает; старый контроллер не захватывает новую ревизию

**`<sub>/controller/placement_intent`**: — строка; после создания не удаляется. **`<sub>/controller/placement_intent — state`**: active | idle. **`<sub>/controller/placement_intent — manifest_rev`**: \<ревизия принятого решения\>. Поля `members`, `target`, `reason` и `at` ниже принадлежат active `placement_intent`; `manifest_rev` обязателен в обоих состояниях.

**`<sub>/controller/placement_intent — members`**: \<JSON-массив всех id решения; уникальны, отсортированы\>. **`<sub>/controller/placement_intent — target`**: \<имя воркера\> | "" — одна цель всей группы; "" — снять размещение. **`<sub>/controller/placement_intent — reason`**: \<непустая причина\>. **`<sub>/controller/placement_intent — at`**: \<стенные секунды принятия решения\>

**`constants — TURN_TERM, TURN_RENEW`**: договор очереди писателя «Terms»

Нечитаемая строка turn/intent — отказ изменения размещения с failures, не пустая строка. Намерение вне формы (`state` не `active`/`idle`; у active нет `members`, `target`, `reason`, `at` либо их значения вне формы) нечитаемо: контроллер отказывает изменению размещения с failures; читатели (`/where`, `/unplaceable`, прогнозы меток) возвращают 503 `unavailable`, а не idle.

Исходное отсутствие строк turn и intent допустимо; после создания ни одна из этих двух строк не удаляется. Turn сохраняет нижнюю границу manifest_rev, idle сохраняется, чтобы версия intent не возвращалась к версии отсутствия между двумя чтениями; это необходимо читателям ниже.

Active intent — принятое общее решение для members, пока отдельные placement и workers доводятся до него. Для каждого его id решают target/reason/at/manifest_rev intent; остальные id решаются своими placement. Читатель (/where, unplaceable, прогнозы и контроллер) читает решение по [договору наблюдения](../../../common/ru/contracts/observation.md) «Чтение решения: intent → placement → intent». При idle все строки завершённого решения уже доведены.

Для допуска нагрузка цели считается консервативно: сумма весов уникальных id, уже назначенных ей **или** направленных туда эффективным решением. Двойной учёт одного id у одного воркера исключён; ещё не снятое старое назначение удерживает место у прежнего воркера. Та же совокупность учитывается для spread_by. Active intent резервирует всех members у target ещё до workers. Показатели фактического назначения по-прежнему считают workers; резерв — условие допуска, а не утверждение, что единица уже работает.

Перед новым допуском незавершённый intent доводится.

Группа принимается одним intent со всеми её членами из свежего взгляда и одной общей целью; предпочтения выбираются по первому id в порядке UTF-8, ограничения и вес — по всем членам. Воркеры никогда не получают назначения членов этой операции одновременно на разных целях: сначала снимаются все прежние назначения всех members, затем добавляются на одну цель. Промежуточное отсутствие части назначений допустимо и чинится; частичное решение о вместимости — нет.

Изменения полей единиц, состава группы, ёмкости, политики и жизни после взгляда обрабатываются следующим проходом: они не атомарны с допуском. При неизменных входах конкуренция контроллеров не превышает ёмкость, не нарушает spread_by и не расщепляет группу.

Если после изменения состава группа размещена лишь частично и целиком на прежнюю цель не помещается, её сначала целиком снимают intent с target ""; она ждёт или выбирает новую общую цель следующим решением. Размещённую полностью группу без причины ухода не пересматривают.

<!-- families:begin -->
### Семьи данных (построены из стандартных файлов)

Форма строк и объектов, которыми глава владеет по [каталогу](../../../common/data/catalog.tsv), — JSON Schema 2020-12 семьи. Экземпляр строки — `{key, row}`, объекта — `{key, object}`; ключ — грамматика колонки `key` каталога. Поля `row` — значения `items` после [кодека](../../../common/data/codec.tsv): писатель проверяет схему и её `$defs.writer`, читатель — схему (слой 3 — слова `x-*` схемы). Нечитаемо — строка не раскодировалась или не прошла схему в режиме читателя; исход — по таблице исходов семьи: путь — префикс пути отказа (пустой — строка целиком), при нескольких путях отказа действует исход с наименьшим приоритетом.

#### `<sub>/placement/<id>` — строка

Схема — [`placement.schema.json`](../../data/placement.schema.json), исходы — [`placement.outcomes.tsv`](../../data/placement.outcomes.tsv); версия формы 1; норма — P/04 N1.1, N1.5.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `worker` | строка; целиком `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` | обязателен |  | the worker name — a slot name, P/03.2 N1.4 (`<prefix>-<suffix>`; prefix of its own manifest — a check of the lesson, not of the form); "" — not placed |
| `reason` | строка | обязателен |  | The current nonempty human reason, required for readers and writers (P/04 N3 Reason). |
| `at` | время (P/01.1 N0 «Время в строке») | обязателен |  | the controller's wall-clock seconds at the moment of the decision |
| `rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | a decimal integer ≥ 1; +1 for each write of the row |
| `manifest_rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | Required manifest revision under which the current intent completion wrote this decision. A missing value is unreadable and is never stamped or repaired; newer-revision protection remains P/04 N3 manifest_rev. |

Пределы читателя и писателя (`$defs.writer`, применены корневым `allOf`):

| Ключ | Ещё и |
|---|---|
| `reason` | не из: `""` |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable: the controller — an error of a pass step (failures + 1), the unreadable is not replaced by absence and is not rewritten as unplaced (N3 «pass()»: «data from such a read are not replaced by empty ones»); the cause goes to the log | 0 | row | P/04 N3 «pass()» |
| строка целиком | `console` | the whole row is unreadable: the effective placement (/where, /unplaceable, label forecasts) — an unconfirmed read, not «not placed» | 0 | row | P/04 N1.5 |

#### `<sub>/workers/<name>` — строка

Схема — [`workers.schema.json`](../../data/workers.schema.json), исходы — [`workers.outcomes.tsv`](../../data/workers.outcomes.tsv); версия формы 1; норма — P/04 N1.1.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `units` | список, без повторов, элемент — строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | обязателен |  | ids of the assigned units by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array; codec array), sorted; "" — none |
| `units[]` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | необязателен |  | the unit id (P/06.1 N1.3); a numeric id — also by this grammar |
| `rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | a decimal integer ≥ 1; +1 only when the list changes |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable: the worker is not in the pool, does not enter garbled of the pass report (N4 «heartbeat/slot/assignment is unreadable») | 0 | row | P/04 N4 |
| строка целиком | `<s>worker` | the whole row is unreadable: the worker reading its own assignment does not change its set of units (takes no new ones, does not give away the ones held by this row), the log | 0 | row | P/03.3 N3 «loop()» step 2 |
| строка целиком | `console` | the whole row is unreadable: drain — `GET /drain` 503 `unavailable` | 0 | row | P/06.6 N1.2 |

#### `<sub>/want/<host>` — строка

Схема — [`want.schema.json`](../../data/want.schema.json), исходы — [`want.outcomes.tsv`](../../data/want.outcomes.tsv); версия формы 1; норма — P/04 N1.1.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `want` | целое; ≥ 1; ≤ 99 | обязателен |  | the absolute target of the number of processes of the role on the server, the base `<prefix>-<server>-1` is included; maximum WANT_NUM_MAX is defined by P/04 forms/runtime-constants.tsv; numeric minimum/maximum carriers stay unchanged. |
| `at` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment of the write; diagnostics — the terms go by the observation of the row version (N1.4 terms) |
| `by` | строка | обязателен |  | the controller instance; diagnostics — the authority is given by cas and the guard placement_turn |
| `why` | строка | обязателен |  | a non-empty reason; the grammar of N3 «shortage(), order()…» |
| `retiring` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | необязателен |  | the worker chosen for shrinking (N3 «shrink»); a slot name, P/03.2 N1.4 |

Только у писателя (`$defs.writer`):

| Ключ | Ещё и |
|---|---|
| `why` | не из: `""` |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable: the unreadable is not replaced by absence and is not rewritten: an error of step 9 (failures + 1), the order rules (retiring, «number above want») are not applied to the processes of the server (the pool contract want_rule), the cause goes to the pass log | 0 | row | P/04 N3 «pass()»; pool contract want_rule |
| строка целиком | `console` | the whole row is unreadable: there is no series workers_wanted{server} of this server, the server's script starts and stops nothing by it (P/02.4 N1.5) | 0 | row | P/06.5 N3 «/metrics — text» |

#### `<sub>/decommissioned/<host>` — строка

Схема — [`decommissioned.schema.json`](../../data/decommissioned.schema.json), исходы — [`decommissioned.outcomes.tsv`](../../data/decommissioned.outcomes.tsv); версия формы 1; норма — P/04 N1.1.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `asked_at` | время (P/01.1 N0 «Время в строке») | обязателен |  | wall-clock seconds of the console request (`platform/decommission/<server>` at) |
| `at` | время (P/01.1 N0 «Время в строке») | обязателен |  | wall-clock seconds of the controller's mark |
| `slots` | список, элемент — строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | names of the given-away slots by the list rule of P/06.1 N1.2; "" — none; names, not a number |
| `slots[]` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | необязателен |  | the name of the given-away slot, P/03.2 N1.4 |
| `units` | список, элемент — строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | обязателен |  | ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | необязателен |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | список, элемент — строка | обязателен |  | the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | строка | необязателен |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable: the controller does not remove or rewrite the mark at revocation, the cause goes to the pass log; the mark of the subsystem about.sub, near.sub or ref of the unit being placed is unreadable — the server is not confirmed for this placement: not a candidate, a step error (failures + 1), the cause goes to the log; it counts neither as decommissioned nor as not decommissioned | 0 | row | P/04 N3 «choose(unit)»; P/04 N1.1 |
| строка целиком | `<s>domain` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value | 0 | row | P/03.7 N1.6 start; P/03.2 N3 «start()» step 3 |
| строка целиком | `<s>worker` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value | 0 | row | P/03.2 N3 «start()» step 3 |
| строка целиком | `console` | the whole row is unreadable: `/servers` — `decommissioned: null` (the general rule of output: a field with an unreadable source — null, if required) | 0 | row | P/06.6 N2.1; P/04 N3 «decommission_server» |

#### `<sub>/decommission-pending/<host>` — строка

Схема — [`decommission-pending.schema.json`](../../data/decommission-pending.schema.json), исходы — [`decommission-pending.outcomes.tsv`](../../data/decommission-pending.outcomes.tsv); версия формы 1; норма — P/04 N1.1; N3 decommission_server.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `state` | строка; одно из: `prepared`, `cleaning`, `finalizing` | обязателен |  | prepared: release the next original candidates; cleaning: remove contributions for the confirmed current release chunk; finalizing: publish the final mark last |
| `request_index` | строка; не из: `""` | обязателен |  | the immutable index of platform/decommission/\<host> for this plan |
| `asked_at` | время (P/01.1 N0 «Время в строке») | обязателен |  | at of the fixed console request |
| `at` | время (P/01.1 N0 «Время в строке») | обязателен |  | the controller time at plan acceptance |
| `manifest_rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | the manifest revision used to freeze the owned from prefixes |
| `remaining` | список, без повторов, элемент — отображение `{name, index}`; в `items` — текст JSON (x-encoding: json) | обязателен |  | ordered immutable slot names and original observed versions still to release; never replace a version after conflict |
| `remaining[]` | отображение `{name, index}` | необязателен |  |  |
| `remaining[].name` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | the name of the given-away slot, P/03.2 N1.4 |
| `remaining[].index` | строка; не из: `""` | обязателен |  | the exact opaque store version; compare only for equality |
| `from` | список, без повторов, элемент — строка; целиком `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` | обязателен |  | distinct ordered owned family prefixes from this manifest domain.books declarations; full prefixes including final slash; never a foreign subsystem |
| `from[]` | строка; целиком `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` | необязателен |  |  |
| `released` | список, без повторов, элемент — строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | slot names confirmed released by this plan, in release order; historical names, never an authority to touch a later holder |
| `released[]` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | необязателен |  | the name of the given-away slot, P/03.2 N1.4 |
| `skipped` | список, без повторов, элемент — строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | original candidates whose version changed; never reread/adopt a newer version for release |
| `skipped[]` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | необязателен |  | the name of the given-away slot, P/03.2 N1.4 |
| `current` | список, не длиннее 63, без повторов, элемент — строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | the current atomic release chunk; at most BATCH_WRITES-1 slots; exact shared release index from cleanup_index or the progress row index |
| `current[]` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | необязателен |  | the name of the given-away slot, P/03.2 N1.4 |
| `cleanup_index` | строка | обязателен |  | empty only before the first progress rewrite of a confirmed release chunk: then the progress row index is the exact release index; otherwise its preserved value, never a later slot reread |
| `slot_cursor` | целое; ≥ 0; ≤ 9007199254740991 | обязателен |  | zero-based current slot being cleaned; compared with current length by the procedure |
| `from_cursor` | целое; ≥ 0; ≤ 9007199254740991 | обязателен |  | zero-based next from prefix for the current slot; conflict discards the remainder of this slot |
| `units` | список, элемент — строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | обязателен |  | final mark metadata fixed before plan acceptance: ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | необязателен |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | список, элемент — строка | обязателен |  | final mark metadata fixed before plan acceptance: the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | строка | необязателен |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Правила:

- `<корень>`: если `state` — `prepared`: `current` — ещё и любое значение; `cleanup_index` — ещё и одно из: `""`; `slot_cursor` — ещё и одно из: `0`; `from_cursor` — ещё и одно из: `0`; `remaining` — ещё и любое значение.
- `<корень>`: если `state` — `finalizing`: `current` — ещё и любое значение; `cleanup_index` — ещё и одно из: `""`; `slot_cursor` — ещё и одно из: `0`; `from_cursor` — ещё и одно из: `0`; `remaining` — ещё и любое значение.
- `<корень>`: если `state` — `cleaning`: `current` — ещё и любое значение; `from` — ещё и любое значение.

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the progress row is unreadable: do not infer completion, recreate the plan, release slots or delete contributions; keep progress and final mark unchanged, record a step error and retry only after a readable source is restored | 0 | row | P/04 N1.1; N3 decommission_server, progress and recovery |

#### `<sub>/controller/placement_turn` — строка

Схема — [`placement-turn.schema.json`](../../data/placement-turn.schema.json), исходы — [`placement-turn.outcomes.tsv`](../../data/placement-turn.outcomes.tsv); версия формы 1; норма — P/04 N1.5.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `holder` | строка | обязателен |  | a unique mark of the capture attempt or "" — the turn is free; a new attempt does not repeat the mark of the previous one |
| `manifest_rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | the manifest revision (P/02.3 N1.5 rev); does not decrease — an old controller does not capture a new revision |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable: a refusal of the placement change with failures and a cause, not an empty row; without a new admission; restore the service row | 0 | row | P/04 N1.5, N3 «get and hold the placement turn» step 1, N4 |

#### `<sub>/controller/placement_intent` — строка

Схема — [`placement-intent.schema.json`](../../data/placement-intent.schema.json), исходы — [`placement-intent.outcomes.tsv`](../../data/placement-intent.outcomes.tsv); версия формы 1; норма — P/04 N1.5.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `state` | строка; одно из: `active`, `idle` | обязателен |  | active — the decision is still being carried through; idle — all rows of the completed decision have been carried through |
| `manifest_rev` | строка; целиком `[1-9][0-9]*` | обязателен |  | the manifest revision of the decision made |
| `members` | список, без повторов, элемент — строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+`; в `items` — текст JSON (x-encoding: json) | необязателен |  | a JSON array of all ids of the decision; unique, sorted (the order is a rule of the lesson, not of the form); only when active |
| `members[]` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | необязателен |  | the id of a unit of the decision (P/06.1 N1.3) |
| `target` | строка; целиком `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` | необязателен |  | one target of the whole group — a worker name (slot, P/03.2 N1.4); "" — remove the placement; only when active |
| `reason` | строка | необязателен |  | A nonempty human reason when state is active, for reader and writer alike. The idle form does not require reason. |
| `at` | время (P/01.1 N0 «Время в строке») | необязателен |  | wall-clock seconds of making the decision; only when active |

Правила:

- `<корень>`: если `state` — `active`: обязательны `members`, `target`, `reason`, `at` (путь — недостающий ключ); `reason` — ещё и любое значение; не из: `""`.

Только у писателя (`$defs.writer`):

| Ключ | Ещё и |
|---|---|
| `reason` | не из: `""` |

Исходы нечитаемой строки (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| строка целиком | `<s>controller` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): the controller — a refusal of the placement change with failures, not an empty row and not idle | 0 | row | P/04 N1.5, N4 «intent row out of the form of N1.5» |
| строка целиком | `console` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): /where, /unplaceable, label forecasts — 503 unavailable, not idle | 0 | row | P/04 N1.5 |

#### `<sub>/controller/pass` — объект

Схема — [`controller-pass.schema.json`](../../data/controller-pass.schema.json), исходы — [`controller-pass.outcomes.tsv`](../../data/controller-pass.outcomes.tsv); версия формы 1; норма — P/04 N1.2.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `at` | время (P/01.1 N0 «Время в строке») | обязателен |  | Wall time when this cycle control part ended; frozen before snapshot publication, not the final object put time. |
| `ok` | bool | обязателен |  | The control part completed with its confirmed inputs/writes and no control-step failure; snapshot outcomes are recorded separately. |
| `error` | строка | обязателен |  | the text of the last error or an empty string |
| `failures` | по определению `count` | обязателен |  | Independent control-step failures of this cycle; snapshot publication outcomes do not increment this field. |
| `last_success` | время (P/01.1 N0 «Время в строке») | обязателен |  | Last successful control-part completion time, unchanged by a later snapshot publication failure. |
| `seconds` | число; ≥ 0 | обязателен |  | Duration of this cycle control part only, excluding snapshot and final-report publications. |
| `manifest_rev` | строка или целое | обязателен |  | the manifest revision of the controller |
| `manifest_behind` | по определению `count` | обязателен |  | rows of this pass whose write was postponed because of a lagging manifest; a row — once per pass |
| `names_given` | отображение имена автора: имя — по определению `slot_name`, значение — строка; не из: `""` | обязателен |  | names given away by the fate; the worker reads them at capture (P/03.2 N3 «capture») |
| `names_given.<имя>` | строка; не из: `""` | необязателен |  | the version of the slot row (index P/01.1 N1, an opaque string) at which the name was given away (N3 «fate» names_given) |
| `hung_move_after` | число; ≥ 0 | обязателен |  | seconds of the hang limit in force at this controller (N1.4 HUNG_MOVE_AFTER); the worker reads it |
| `fates` | отображение имена автора: имя — по определению `slot_name`, значение — отображение `{fate, server, why, rev, since}` | обязателен |  | only taken slots not given away (holder non-empty, released false) |
| `fates.<имя>` | отображение `{fate, server, why, rev, since}` | необязателен |  |  |
| `fates.<имя>.fate` | строка; одно из: `alive`, `wait`, `hung`, `hung_moved`, `unsure`, `unsure_moved`, `move`, `release` | обязателен |  |  |
| `fates.<имя>.server` | строка | обязателен |  |  |
| `fates.<имя>.why` | строка | обязателен |  |  |
| `fates.<имя>.rev` | строка или целое | обязателен |  | the version of the judgment about the slot |
| `fates.<имя>.since` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment the slot entered this fate by the controller's clock |
| `diverged` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `unplaced` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `garbled` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `snapshot_tables_refused` | по определению `count` | обязателен |  | Tables replaced by the too_large stub during this cycle at SNAPSHOT_TABLE_MAX; included in this same final report, outside control-step failures. |
| `snapshot_rows_garbled` | по определению `count` | обязателен |  | Unreadable snapshot fields omitted by unit/table publications of this same cycle; reset only for the next cycle after this final report. |
| `reach_moves_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `slots_released_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `unplaced_deleted_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `servers_decommissioned_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `workers_hung` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `workers_hung_moved_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `workers_unsure_moved_total` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `name_conflicts` | по определению `count` | обязателен |  | a counter ≥ 0 |
| `unplaceable` | отображение имена автора: имя — строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+`, значение — строка; не из: `""` | обязателен |  |  |
| `unplaceable.<имя>` | строка; не из: `""` | необязателен |  | a non-empty reason — why of /unplaceable and reason of 404 `/where/<id>` |
| `short` | список, элемент — отображение `{labels, units, workers, groups, ordered, withheld?}` и прочие имена автора: имя — строка, значение — по определению `count` | необязателен |  | only when placement.grows true |
| `short[]` | отображение `{labels, units, workers, groups, ordered, withheld?}` и прочие имена автора: имя — строка, значение — по определению `count` | необязателен |  |  |
| `short[].labels` | список, элемент — строка | обязателен |  | the label set — the canonical notation in ascending order (N3 «set order») |
| `short[].labels[]` | строка | необязателен |  |  |
| `short[].units` | целое; ≥ 0; целый знак и у читателя (x-whole) | обязателен |  | Exact nonnegative sum of waiting unit weights, in integer JSON notation, without an upper common.uint53 bound. Preserve the whole serialized-report limit; never round or saturate through binary64/int64 (P/04-R007). |
| `short[].workers` | по определению `count` | обязателен |  | processes needed beyond the live ones and the capacity in flight |
| `short[].groups` | по определению `count` | обязателен |  | waiting groups; always, 0 too |
| `short[].ordered` | по определению `count` | обязателен |  | ordered by this pass |
| `short[].withheld` | строка | необязателен |  | words for why it was not ordered |
| `short[].<имя>` | по определению `count` | необязателен |  | An own counter of the short element; standard properties keep their declared forms. |
| `wants` | отображение имена автора: имя — по определению `server_name`, значение — отображение `{want, live, pending, retiring?, why, state}` | необязателен |  | only when placement.grows true |
| `wants.<имя>` | отображение `{want, live, pending, retiring?, why, state}` | необязателен |  |  |
| `wants.<имя>.want` | целое; ≥ 1; ≤ 99 | обязателен |  |  |
| `wants.<имя>.live` | по определению `count` | обязателен |  | live processes of the role of the server |
| `wants.<имя>.pending` | по определению `count` | обязателен |  | capacity in flight |
| `wants.<имя>.retiring` | по определению `slot_name` | необязателен |  | a slot name, P/03.2 N1.4 |
| `wants.<имя>.why` | строка | обязателен |  |  |
| `wants.<имя>.state` | строка; одно из: `ok`, `raising`, `raise_failed`, `no_base` | обязателен |  |  |
| `raise_failed` | отображение имена автора: имя — по определению `server_name`, значение — отображение `{since, times}` | обязателен |  |  |
| `raise_failed.<имя>` | отображение `{since, times}` | необязателен |  |  |
| `raise_failed.<имя>.since` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment the order was removed |
| `raise_failed.<имя>.times` | по определению `count` | обязателен |  | refusals in a row |
| `near_waiting` | список, не короче 1, без повторов, элемент — строка; целиком `[a-z][a-z0-9_-]{0,31}` | необязателен |  | the subsystems of placement.near.sub that are not in the manifest catalog of this pass: the affinity waits for their installation (N1.3 near); otherwise there is no field |
| `near_waiting[]` | строка; целиком `[a-z][a-z0-9_-]{0,31}` | необязателен |  |  |
| `expired_kept` | по определению `count` | обязателен |  | Manual rows retained after ends removed them; required nonnegative count for current reader and writer, zero when none. |
| `snapshot_state_garbled` | по определению `count` | обязателен |  | Unreadable unit states omitted by the unit snapshot publications of this same cycle; reset only for the next cycle after this final report. |
| `state_swept_total` | по определению `count` | обязателен |  | Cumulative confirmed orphan-state deletions from this process start; not reset between cycles. |
| `.<имя>` | любое значение | необязателен |  | the implementation's own counters (N1.2 — MAY add) |

**`count`** — a counter ≥ 0

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `<count>` | целое; ≥ 0; ≤ 9007199254740991 |  |  |  |

**`server_name`** — the server name — the grammar of SERVER_NAME (P/02.4 N1.2)

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `<server_name>` | строка; целиком `[a-z0-9]+(-[a-z0-9]+)*` |  |  |  |

**`slot_name`** — a slot name, P/03.2 N1.4

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `<slot_name>` | строка; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` |  |  |  |

Исходы нечитаемого объекта (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| `/names_given` | * | the worker at capture (P/03.2 N3 «capture» step 1): without a readable names_given there is no permission by it — the name is taken only when released or free, the cause goes to the log | 0 | field | P/04 N1.2; P/03.2 N3 «capture» |
| `/short` | * | short out of form (an element without a required field of N1.2, including groups): the console does not give the series units_short, workers_withheld and groups_waiting of this pass, /metrics — 200 (P/01.1 N0 «Stability of output»); the rest of the report is read | 1 | field | P/04 N1.2; P/06.5 N3 «/metrics — text» |
| `/hung_move_after` | * | the worker (P/03.2): keeps the previous hang limit (the last one read); if none was read — does not judge itself hung by the limit of the report; the cause goes to the log once per pass | 1 | field | P/04 N1.2 |
| объект целиком | `<s>worker` | the whole object is unreadable: the worker at capture — as /names_given: there is no permission by it, the name is taken only when released or free, the cause goes to the log; the hang limit — as /hung_move_after: the previous one read, without one read it does not judge itself hung by the limit of the report | 2 | row | P/04 N1.2; P/03.2 N3 «capture» |
| объект целиком | `console` | the whole object is unreadable: the console removes the series from the pass report rather than dropping the /metrics answer (P/01.1 N0 «Stability of output»); /where of an unplaced one — reason without why: «not placed: no worker holds it» | 2 | row | P/06.5 N3 «/metrics — text»; P/06.6 N2.2 |

#### `<sub>/snapshot/<worker>` — объект

Схема — [`snapshot.schema.json`](../../data/snapshot.schema.json), исходы — [`snapshot.outcomes.tsv`](../../data/snapshot.outcomes.tsv); версия формы 1; норма — P/04 N1.3a.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `cluster` | строка | обязателен |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | строка или null; целиком `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` | обязателен |  | the worker name of the shard (slot, P/03.2 N1.4); for the shard of a gone worker — null |
| `ts` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment of publication |
| `.<имя>` | список, элемент — отображение `{id, revision, worker, server}` и прочие имена автора: имя — строка, значение — любое значение | необязателен |  | имя: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<имя>[]` | отображение `{id, revision, worker, server}` и прочие имена автора: имя — строка, значение — любое значение | необязателен |  |  |
| `.<имя>[].id` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | обязателен |  | the unit id (P/06.1 N1.3) |
| `.<имя>[].revision` | строка или целое | обязателен |  | revision of the unit row |
| `.<имя>[].worker` | строка или null | обязателен |  | the worker of the assignment; unplaced has none |
| `.<имя>[].server` | строка или null | обязателен |  | the worker's server |
| `.<имя>[].<имя>` | любое значение | необязателен |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Пределы читателя и писателя (`$defs.writer`, применены корневым `allOf`):

| Ключ | Ещё и |
|---|---|
| `<корень>` | не больше 1 имён (x-max-names) |
| `.<имя> (имя)` | строка; не из: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; целиком `[a-z][a-z0-9_-]{0,31}` |

Исходы нечитаемого объекта (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| объект целиком | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output») | 0 | row | P/06.5 N1.3 age, metrics |
| объект целиком | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot/unplaced` — объект

Схема — [`snapshot-unplaced.schema.json`](../../data/snapshot-unplaced.schema.json), исходы — [`snapshot-unplaced.outcomes.tsv`](../../data/snapshot-unplaced.outcomes.tsv); версия формы 1; норма — P/04 N1.3a.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `cluster` | строка | обязателен |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | null | обязателен |  | for the shard of the unplaced — null |
| `ts` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment of publication |
| `.<имя>` | список, элемент — отображение `{id, revision, worker, server}` и прочие имена автора: имя — строка, значение — любое значение | необязателен |  | имя: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<имя>[]` | отображение `{id, revision, worker, server}` и прочие имена автора: имя — строка, значение — любое значение | необязателен |  |  |
| `.<имя>[].id` | строка; не из: `.`, `..`; целиком `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` | обязателен |  | the unit id (P/06.1 N1.3) |
| `.<имя>[].revision` | строка или целое | обязателен |  | revision of the unit row |
| `.<имя>[].worker` | строка или null | обязателен |  | an unplaced one has no worker |
| `.<имя>[].server` | строка или null | обязателен |  | the worker's server; an unplaced one has none |
| `.<имя>[].<имя>` | любое значение | необязателен |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Пределы читателя и писателя (`$defs.writer`, применены корневым `allOf`):

| Ключ | Ещё и |
|---|---|
| `<корень>` | не больше 1 имён (x-max-names) |
| `.<имя> (имя)` | строка; не из: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; целиком `[a-z][a-z0-9_-]{0,31}` |

Исходы нечитаемого объекта (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| объект целиком | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output») | 0 | row | P/06.5 N1.3 age, metrics |
| объект целиком | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot-tables/<table>` — объект

Схема — [`snapshot-tables.schema.json`](../../data/snapshot-tables.schema.json), исходы — [`snapshot-tables.outcomes.tsv`](../../data/snapshot-tables.outcomes.tsv); версия формы 1; норма — P/04 N1.3b.

| Ключ | Тип и границы | Обязательность | Урок | Смысл |
|---|---|---|---|---|
| `cluster` | строка | обязателен |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `ts` | время (P/01.1 N0 «Время в строке») | обязателен |  | the moment of the write of the object; rows did not change — the previous one |
| `refused` | строка; одно из: `too_large`, `whole_too_large` | необязателен |  | a stub instead of rows: the table did not fit (P/04 N1.3b ceiling, P/09.1 N1.2 tables_budget) |
| `rows` | список, элемент — отображение `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | обязателен |  | the rows of the table by key in UTF-8 bytes (the order is a rule of the lesson, not the form) |
| `rows[]` | отображение `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | необязателен |  |  |
| `rows[].key` | строка; не из: `""` | обязателен |  | the row name (P/06.1 N1.6) |
| `rows[].revision` | целое; ≥ 1; ≤ 9007199254740991 | обязателен |  | the row version |
| `rows[].fields` | отображение, opaque | обязателен |  | fields of the list domain.view_tables of the manifest; values of their own type; no secrets |
| `rows[].secrets` | список, элемент — строка | необязателен |  | names of the set *_secret fields; no values |
| `rows[].secrets[]` | строка | необязателен |  |  |
| `rows[].worker` | строка | необязателен |  | for unit rows — from the assignment |
| `rows[].server` | строка | необязателен |  | for unit rows — from the assignment |
| `rows[].phase` | строка | необязателен |  | for unit rows — from the heartbeat |
| `rows[].status` | отображение, opaque | необязателен |  | fields of domain.view_status from the element of status[] of the heartbeat |
| `rows[].labels` | список, элемент — строка | необязателен |  | for unit rows — the field labels |
| `rows[].labels[]` | строка | необязателен |  |  |
| `rows[].about` | строка | необязателен |  | for unit rows — the id of the about unit |

Исходы нечитаемого объекта (читатель — роль; `*` — все читатели семьи):

| Путь отказа | Читатель | Исход | Приоритет | Единица | Норма |
|---|---|---|---|---|---|
| объект целиком | `domainagent` | the whole object is unreadable (not JSON or not an object of the family): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log (P/09.1 N1.2) | 1 | row | P/09.1 N1.2 |
<!-- families:end -->

Писатель и читатель проверяют схему готовым валидатором JSON Schema 2020-12 закреплённой версии ([закреплённые версии](../../../common/ru/versions/README.md)); сами файлы схем — норма, не выбор.

---

## N2 Двери

Своих HTTP-дверей у урока нет (`P/04 no-openapi`). Двери консоли, через которые оператор говорит с контроллером (`/policy`, `/drain`, `/servers/{server}/labels`, `/servers/{server}/decommission`, `/unplaceable`, `/where/{id}`), их проходы и отказы — [P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N2 (`/where` — [глава 6.5](../../../06-console/ru/spec/06.5-console.norms.md) N2); их записи контроллер исполняет строками N1.1 на своём проходе (N3).

---

## N3 Проход

delete_after применяется только к named id: numeric вместе с этим ключом отвергается загрузчиком P/02.1. Контроллер не заменяет физическое удаление надгробием и не уничтожает историю числовых выдач.

### получить и удерживать очередь размещения

Шаги 1–6, барьер и «Гонки» — [договор очереди писателя](../../../common/ru/contracts/turn.md) «Получить и удерживать очередь», «Барьер». Строка очереди контроллера — `<sub>/controller/placement_turn` (N1.5), `holder` — новая уникальная метка попытки; изменяющие записи под стражем (шаг 5 договора) — каждая запись/удаление placement/*, workers/* и placement_intent, а также удаление строки единицы по delete_after; очередь отдаётся в конце прохода (шаг 6 договора).

### принять и довести решение(members, target, reason)

Принятие и доведение решения следует шагам 0–6 ниже по порядку.

0. очередь моя; active intent → сначала довести его, новых решений пока не принимать; manifest_rev intent > моя → не изменять его и размещения; строки его members — в manifest_behind (N1.2)

1. До нового решения заново читают единицы, действующие решения, назначения и свойства кандидатов. Если manifest_rev хотя бы одного размещения членов новее ревизии контроллера, нового intent не принимают, строки членов учитывают в manifest_behind (N1.2).

До принятия решения проверяют целую группу или единицу по свободной ёмкости с резервами N1.5, spread_by и всем прочим ограничениям. При оценке переезда собственные прежние резервы членов не считают второй копией на цели. Допуск проверяет итоговый набор: прежние id без members плюс ВСЕ members, включая spread_by внутри группы и по всем воркерам целевого сервера.

Нет общей цели — нет нового допуска; снятие использует target "".

Если полный ключ `<sub>/placement/<id>` хотя бы одного члена превышает предел P/01.1, решения и записи intent нет; эти члены входят в unplaceable с why.

2. записать active intent с cas прочитанного idle (или cas "" при исходном отсутствии) и guard turn; toolarge до подтверждённого active → отказ шага, placement/workers не менять, группу не делить

3. после подтверждённого intent свежо перечислить/прочитать ВСЕ workers; снять ВСЕ members из ВСЕХ назначений, включая target, каждой записью cas + guard turn; только подтверждённое завершение всех снятий разрешает идти дальше

4. каждой placement members присвоить target/reason/at/manifest_rev intent с cas + guard turn, rev + 1; строка уже содержит эти поля → не переписывать; отсутствующая начинается с rev 1

5. target непуст → добавить ВСЕ members в его назначение одной записью cas + guard turn; target пуст → добавления нет; пока 3–4 не завершены, шаг 5 запрещён

6. только после подтверждения 3–5 записать intent {state: idle, manifest_rev} с cas + guard turn

Каждая группа занимает одну запись intent; она не дробится ради потолка строки или назначения. Вес обеих будущих строк (intent и полного назначения цели) проверяется до шага 2; превышение — отказ шага с причиной и failures, без частичного размещения.

До шага 2 так же проверяется, что полный ключ `<sub>/placement/<id>` каждого из members представим в пределе ключа хранилища (P/01.1 N1): id, допустимый P/06.1 N1.3 для строки единицы, может не поместиться в более длинный ключ размещения. Непредставимый ключ — решения нет, intent не пишется, группа не делится; эти members попадают в `unplaceable` с `why`, остальные решения прохода продолжаются. Поэтому недоводимого из-за длины ключа intent не бывает, и одна такая единица не останавливает размещение подсистемы.

Неполное чтение также запрещает допуск.

При смене держателя active intent восстанавливается **с шага 3**; новое решение и другое направление для его members до завершения запрещены. Состав, цель и правило зафиксированы в intent; изменения входов после его принятия обрабатываются следующим решением после восстановления. После доведения все новые расчёты делают свежий взгляд, поэтому резерв предыдущего решения уже виден.

**Гонки.** Два допуска разных единиц не используют один остаток: B получает turn после A и видит решение/назначение A либо его active intent, который обязан сначала довести. При двух допусках разными контроллерами и capacity=1 второй вес 1 не проходит; при spread_by занятое первым допуском значение уже видно. Два разных первых члена группы не создают разные решения: один active intent фиксирует всех и одну цель.

После обрыва посреди снятий добавления не начинаются; после обрыва посреди placement новый держатель повторяет снятия и доводит ту же цель. До добавления членов на новую цель их прежние назначения воркеров уже не содержат ни одного из этих членов.

Гарантия переноса относится к строкам и назначениям; действия прежних процессов останавливают согласование и аренды (P/03.3, P/03.2), а не одна правка карты размещения.

### проход() — каждые PASS_EVERY

Каждый проход следует упорядоченным шагам ниже через PASS_EVERY, с заданной там обработкой ошибок независимых шагов. Каждый шаг прохода исполняется в своей попытке: ошибка шага увеличивает failures на 1, остальные шаги продолжаются.

0. Память наблюдаемых пульсов, слотов и ресурсов обновляют по собственным часам контроллера; первая встреча версии означает, что она только что изменилась. Объекты кластера (пульсы воркеров/ресурсов и отчёты) читают через ресурс своего сервера. Без своего ресурса `cluster://` даёт unknown, а не отсутствие ([клиент объектов](../../../common/ru/contracts/object-client.md), door).

До изменяющего прохода получают очередь размещения: busy означает отсутствие изменяющего прохода и повтор через TURN_BUSY_RETRY; при своей очереди сначала доводят active intent.

После допуска по очереди и доведения intent берут свежий вид единиц, размещений, назначений и свойств кандидатов. Перед каждым новым решением вид обновляют с учётом предыдущего решения.

1. ревизия: прочитать ревизию манифеста; placement без обязательного manifest_rev нечитаема; не дописывать и не исправлять её; прочесть каталог манифестов (platform/manifest/*) — каждым проходом: манифест near.sub появился — сродство (N1.3 near) действует с этого прохода; нет его — сродства нет, near_waiting

2. вывод серверов: возобновить pending или принять план неслышимого сервера по N3 «decommission_server»; отдача/уборка кусками, `<sub>`/decommissioned/`<s>` только последним шагом; до приёма плана слышный сервер оставляет запрос стоять

3. судьба слотов (ниже); release → записать слот отданным; names_given; тревоги hung/unsure; брошенный захват — снять строки под ним (ниже)

4. разместить: снять удалённые (reason deleted) → снять retire_when (по действующему состоянию при retire_when.state) → снять ends (поле ≠ never и ≤ часов контроллера; причина ends) → sync назначений с размещениями (diverged) → каждую неразмещённую единицу из placeable (N3 нехватка; без удалённых, ends и retire_when) — выбрать (ниже), группу целиком у первого члена; каждая в своей попытке; порядок неразмещённых — по id в байтах UTF-8 (группа — по id первого члена); тот же порядок у переездов шагов 5–7

5. достижимость: единицы, чей сервер больше не достаёт до их меток, — переезд в пределах REACH_BUDGET; группа — целиком, первая группа идёт и сверх бюджета; некуда — снять с причиной

6. уход: единицы воркеров, которые уходят (ниже), — переезд без бюджета; группа целиком или ждёт

7. дом: не больше HOME_BUDGET единиц — домой, если там есть место; дом судится как в «выбрать» (N1.3 home): держатель названного места пригоден — дом он один, единица у другого воркера, в том числе того же сервера, едет к нему; держателя нет — дом сервер места, и единица на этом сервере уже дома; дома нет, он без свободного места или не пригоден — единица стоит: предпочтение фильтром не становится

8. неразмещённые дольше delete_after: под своим turn заново прочитать единицу и её эффективное размещение по N1.5; есть назначение, intent active (при любой цели) или чтение не подтверждено → не удалять. Всё ещё неразмещена и срок подтверждён → удалить строку с cas её свежей версии И guard своей версии placement_turn (допуск шага 5 выше); conflict/412/неответ → барьер и новый план по правилу очереди, журнал unit.unplaced_deleted только при успехе.

Физическое удаление по шагу 8 применяется и к единице, всё ещё снятой по retire_when дольше retire_when.delete_after; отсчёт идёт от первого увиденного снятия и сбрасывается при отмене снятия или перезапуске контроллера. Перепроверяют свежую строку и, при retire_when.state, её действующее состояние; если уже не снята, не удаляют, сохраняя правку оператора.

Единицу, снятую по ends, физически удаляют сразу после снятия по тем же правилам удаления шага 8 и исключению ручных строк.

У таблицы с fixed-полями или about не по id удаляется только строка с made; ручная строка не удаляется — expired_kept + 1 (N1.3 unplaced). Строка с made удаляется по договор проверки строки «Customer row: made» `delete` (строго позже made.keep, not_before = max(0, made.keep − 60)): 409 early — не удалено, без барьера и журнала, следующим проходом; keep предотвращает только заведомо раннюю попытку удаления; поздно пришедшее удаление по-прежнему удерживает not_before при приёме хранилищем. Проверка made.keep никогда не разрешает удаление раньше keep.

Строка удаляется физически, без надгробия (P/01.1 удалить): строка первой, с cas прочитанной версии и guard своей версии placement_turn; правка или продление между чтением и удалением — conflict: удаление отменено, состояние не трогается; только после подтверждённого удаления строки — её состояния (шаг 8a); журнал unit.unplaced_deleted {reason: unplaced | retired | ends}

8a. уборка состояния (unit.state объявлен): перечислить `<sub>`/state/; для каждой строки состояния прочитать строку единицы: нет её, надгробие или её born ≠ born состояния → осиротевшее: удалить одной операцией с cas версии состояния и guard {key: строка единицы, index: прочитанная версия — у надгробия его версия, "" — строки нет}; строка, созданная или изменённая после чтения, уборку отменяет (412 — оставить до следующего прохода); действующее и прочее неосиротевшее (born совпал, revision другой) не трогать; state_swept_total + 1 за каждую снятую

9. нехватка и заказ (grows: true): строки заказа, ёмкость в пути, short, заказать, снять по сроку

9a. сократить (grows: true): жертва, retiring, перенос не больше SHRINK_BUDGET, конец или отмена; дренаж — N3 ниже

10. Завершить управляющую часть и её ok/failures/at/seconds/last_success; отдать очередь; затем попытаться опубликовать снимки единиц и таблиц вне очереди и записать один окончательный `<sub>/controller/pass` этого цикла.

Определённый badkey полного ключа хранилища — ошибка соответствующего шага, а не отсутствие строки; данные по такому чтению не подменяются пустыми. Если ошибка не позволяет довести active intent, новое решение не принимается: действует правило восстановления N1.5/N3.

Проход проверяет размещение и назначения; `unique`/`ref`/`must_match` полей единиц проверяются предварительно дверью единиц P/06.1. Фоновый аудит и журналирование нарушения этих ограничений после гонки отдельных записей этот проход не гарантирует (P/06.1 N3).

**Гонки.** Цель размещения/назначения изменяются только под очередью и через intent; один cas строки единицы не заменяет общего допуска. Обрыв очереди/хранилища прекращает весь изменяющий проход, а не только одну единицу; ошибки остальных независимых шагов учитываются обычным failures. Следующий держатель сначала чинит незавершённое решение, затем принимает свои. Отсутствующий manifest_rev — нечитаемая нынешняя строка, не право дописать её; прежние барьеры очереди/intent сохраняются.

### выбрать(единица) → воркер | нет

Подбор воркера следует правилам пригодности и рангов ниже. размещена (worker ≠ "") → как есть; не пересматривать

retire_when (по действующему состоянию при retire_when.state); ends ≠ never и ≤ часов контроллера → нет

живой воркер, пул, хранитель места при distinct — договор пула (common/contracts/pool.md): живые − отданные слоты − дренируемый и выведенные серверы − (requires: resource ∧ ресурс silent) − retiring − номер выше want − нечитаемое назначение − (distinct: все кроме хранителя места)

пригодные = пул ∩ constraint ∩ spread_by ∩ affinity ∩ (группа уже у воркера → только он) ∩ (воркер держит исключительное место → только единицы, связанные с ним; N1.3 affinity.exclusive). группа из нескольких ждущих: пригодные ∩ {принимает всех ∧ свободно ≥ Σ весов}; пусто → ждать, сказать

порядок: дом → предпочтение → все; дом — среди пригодных (N1.3 home): держатель названного места, держателя нет — воркеры сервера этого места; держателю не хватает свободного — ранг пуст, сервер дома его не заменяет; предпочтение — один ранг: воркер рядом с соседом (near) или на сервере несвязывающей строки affinity (N1.3) — любое из двух, оба сразу ранг не поднимают; внутри ранга — свободно = ёмкость − нагрузка с резервами N1.5, свободно ≥ вес единицы ∧ строго больше прежнего лучшего; равенство — первый по имени (ASCII, P/03.2 N1.4)

нашли → принять и довести решение для единицы или всей группы по N3 выше; уже размещена за время получения очереди → не принимать прежний выбор, свежий взгляд

нет → строка не пишется (или reason, почему), единица в unplaced; тяжелее любого — в unplaceable со словами

Метка вывода `<sub>/decommissioned/<s>` подсистемы, которую называют `about.sub`, `near.sub` или `ref` размещаемой единицы, не читается — сервер `s` для этого размещения не подтверждён: он не кандидат, ошибка шага (failures + 1), причина в журнал; выведенным или невыведенным он не считается.

**Причина** (для человека, ДОЛЖНА быть непустой; СЛЕДУЕТ грамматике): `most free capacity (<свободно>) among <n> worker(s)` — `<n>` — число пригодных (после фильтров), не всех живых + `; weight <w>` — только у манифеста с `placement.weight` + ` reaching <метки>` + `; on <server>` + `, whose resource is <state>` + пометка выбора по рангу выбранного воркера: ранг дома — `, at home on <s>`, при `home: near` — `, beside <их id> holding it`; ранг соседа — `, beside <их id> holding it`, и если дом объявлен, но ранг его пуст, — ещё ` (home <s> has no room)`; ранг «все» при `near`, чей сервер не выбран, — `, away from <их id> on <сервер соседа> (no room there)`, и при объявленном `home`, кроме `home: near`, вне дома — ещё `; away from home <s>`; `<s>` пометок дома — чем назван дом: место держателя или сервер. Для человекочитаемой причины действует рамка выше: MUST непустая, SHOULD по этой грамматике; Уход: `slot <имя> released`, `slot <имя> capture did not finish`, `resource on <s> silent`, `server <s> draining`, `server <s> decommissioned`, `<w> holds no <place_by> now`, `<w>'s <place_by> <место> admits no unit` (`<place_by>` — имя поля `placement.place_by`, \<место\> — id места воркера: `w-1 holds no shard now`, `w-1's shard s3 admits no unit`). Для человекочитаемой причины действует рамка выше: MUST непустая, SHOULD по этой грамматике; Достижимость: `<s> no longer reaches <метка>; …` / `; nothing live reaches it`. Для человекочитаемой причины действует рамка выше: MUST непустая, SHOULD по этой грамматике; Группа: `with <id>, one <group_by>: <why>; on <s>`. Для человекочитаемой причины действует рамка выше: MUST непустая, SHOULD по этой грамматике; Удалённая: `deleted`.

**Материализация и sync.** Они используют тот же intent и очередь. Даже если правильное решение уже есть, починка сначала фиксирует его для единицы/группы, снимает прежние назначения и доводит одну цель. Частичного добавления по снимку начала прохода нет. Единственный guard целевой записи — версия turn; стабильность решения обеспечивает исключительное владение очередью, свежая проверка и неизменяемый до завершения intent.

### переехать(единица, от, к) → ok | уже перевезли

1. очередь текущего прохода моя и подтверждена; вне прохода сначала получить её; заново захватывать уже удерживаемую очередь не нужно; довести прежний active intent; свежо прочитать эффективное размещение; worker != от → Moved, не трогать; у группы проверить всех членов и общую цель

2. проверить к по всем ограничениям и свободной ёмкости с резервами; принять intent для всей единицы/группы и довести его шагами 2–6 выше

**Гонки.** A задержался после решения w-2, B получил очередь и довёл его, затем перевёз на w-3. Каждая поздняя запись A имеет старый guard turn и отказана. Опоздавший писатель A не может ни добавить к w-2, ни снять с уже нового w-3. Если A успел добавить до захвата B, B видит назначение при свежем снятии. У одной единицы не возникает двух назначений; у группы до добавления новой цели сняты все старые назначения. Мгновение без назначения и отставание directory остаются допустимы.

Во всех ветвях hung/unsure/wait HUNG_MOVE_AFTER отсчитывается от первого наблюдения этим судьёй неизменной версии слота (возраст 0), не от until, конца SLOT_TERM или входа в fate. Диагностическое fates.since не переносит этот срок. Новый судья начинает наблюдение заново.

### судьба(слот) → fate — по часам контроллера

Упорядоченная машина решения — [forms/slot-fate.tsv](../../forms/slot-fate.tsv). Типизированные входы — наблюдения этого судьи, не `until` писателя. Выбирается первая подходящая строка; результат — судьба и, когда разрешено, точная версия суждения для `names_given`. Ветка release вызывает [forms/slot-release.tsv](../../forms/slot-release.tsv): только подтверждённый ответ CAS публикует версию после release. Действие `-` — YOURS по якорю, его нельзя пропускать. Правила записи, очистки брошенного захвата и разрешения остаются ниже.

Запись отдачи, уборка брошенного захвата и разрешения захвата следуют правилам ниже. запись release: записать слот released (cas), holder/until/gen/server сохранить; порванную — целиком отданной и ничьей с сохранением читаемого gen и записывая until как нулевой Time в прежней записи писателя, не now; server сохранить только если читается по нынешней схеме поля слота; иначе поле опустить, без пустого заменителя. При сохранении или пропуске server в release не проверяют живость или реестр. Если gen существующего слота нечитаемо, строку не меняют и разрешения захвата не дают (P/03.2 N1.4).

брошенный захват: released = "taking", версия неизменна ≥ SLOT_TERM на часах контроллера (захватчик умер между записями P/03.2 N3 «capture» шаги 3 и 4) → снять строки под слотом: вклады `<sub>`/`<from>`/\<слот\> каждой книги манифеста с from-семьёй (P/03.7 N1.2) пакетом с guards по `<sub>`/slots/\<слот\> с версией этого суждения, слот не писать; строки нет — пропуск; отказ стража (412 guard, 409 conflict) — живой захват сменил версию: не повторять; с выводом сервера и без: брошенный захват несёт server захватившего, по server = s шаг 2 «decommission_server» его не узнаёт, а сирота под taking держал бы вклад stale навсегда

names_given[имя] = версия строки слота, на которой имя берётся: для move, hung_moved, unsure_moved и wait ≥ HUNG_MOVE_AFTER — версия в момент суждения (контроллер строку не пишет); для release — версия ПОСЛЕ записи отдачи (ответ этой записи): отданный слот берут по ней, и как «свободный» он тоже кандидат (P/03.2 N3 «capture» шаг 2c)

Нечитаемое gen существующего слота не заменяется нулём при release; такую строку сохраняют и не включают в names_given до восстановления поколения. Переназначение единиц по судьбе не означает разрешения переписать повреждённое поколение слота.

**Переходы `release`.** Ветвь `release` достижима строкой «gone без назначенных единиц»: живой ресурс говорит о процессе одним из `runs`, `gone`, `unlisted`, `unknown` (P/05 N1.4; `silent` — состояние ресурса, не присутствие); правила с более высоким приоритетом по-прежнему выполняются первыми.

Две замыкающие строки достижимы, когда server/slot известны, версия слота наблюдается неизменной не меньше SLOT_TERM + LOST_AFTER, свежесть воркера не подтверждена, resource_state — unknown: при назначениях выбирается move, без назначений — процедура release. Две замыкающие строки выбора судьбы используют прежнюю политику замыкающих строк, а не ожидание недостижимого ресурса HUNG_MOVE_AFTER; resource_state unknown не доказывает ни молчания, ни недостижимости.

Выбор перехода — [forms/slot-release.tsv](../../forms/slot-release.tsv). Выбор перехода slot-release получает выбранную судьбу; после его действия YOURS CAS машине передают подтверждённый ответ или конфликт. Сохранены пять свидетельств: gone без единиц, конкурирующее продление, gone с единицами, unlisted без единиц и runs без единиц. Конкурирующее продление отказывает release, следующий проход судит изменившуюся версию как `alive`.

Порядок правил нормативен: более определённое знание раньше менее определённого; запас раньше суждений.

Контроллер не пишет слот ни при каком исходе, кроме `release` и вывода сервера, и снимает строки под брошенным захватом (выше).

**Гонки.** Держатель продлил слот между суждением и захватом имени новым процессом: `names_given` привязан к версии, захват с `cas` по ней не пройдёт — имя остаётся. Два контроллера могут иметь разные истории наблюдения и потому разные суждения; каждый использует свой возраст версии по P/03.2 N1.4. Записи `release` идут с `cas` прочитанной версии, поэтому два решения не перезаписывают продление или чужой захват. Сдвиг часов писателя при одинаковой истории наблюдения не меняет судьбу.

### уходит(воркер) → причина | нет

Первое из: слот отдан (released = true — сразу); брошенный захват (released = taking, версия неизменна SLOT_TERM на часах контроллера — захватчик умер между записями; раньше — не уходит, захват довершится); ресурс сервера silent — только при `requires: resource` и живом воркере (договор пула): он работает, а единицам нужен ресурс, которого нет; не держит место (`distinct`); место не принимает; сервер дренируется; сервер выведен; исход из MOVED_FATES — его `why`.

Единицы уходящего — переезд (шаг 6) по правилам выбора; группа целиком или остаётся с тревогой `units.left_on_leaving`; строка размещения не очищается, пока не найдено новое место, — кроме отданного слота и брошенного захвата: их единицы, которым некому достаться, снимаются записью `worker: ""`, причина `slot <w> released; nothing live can take it` (`slot <w> capture did not finish; nothing live can take it`) (воркер ушёл навсегда, строка с его именем говорила бы «размещена»; приёмка P/03.4, сц. 03). Молчание хранилища не двигает ничего. Без `requires: resource` молчание ресурса уходом не считается, и воркер, молчащий вместе с ресурсом, уходит только по судьбе: единицы ведёт её исход `move`, SLOT_TERM + LOST_AFTER наблюдения неизменной версии слота (N3 «судьба», [P/03.2-08](../../../03-worker/ru/spec/03.2-worker.norms.md)).

**Гонки.** Уход и оживший воркер: решение — по снимку прохода; воркер, вернувшийся после переезда, читает назначение без единицы и останавливает её (P/03.3 N3 «loop()», шаг 2: ведомой нет в назначении → `stop_unit`); переезд не откатывается.

### нехватка(), заказать(), снять заказ, сократить() — при grows: true

Роль растёт по требованию: контроллер заказывает число процессов роли на конкретном сервере строкой `<sub>/want/<host>`, скрипт сервера приводит к ней число процессов (P/02.4 N1.5); контроллер процессов не запускает. Нехватка, создание и распределение заказа и его отзыв следуют правилам ниже.

строка заказа: у каждого сервера, где роль установлена и нет pending/окончательного вывода (в строке двери есть room.`<sub>`, N1.1), — строка `<sub>`/want/\<сервер\>; нет — создать want 1 записью с cas "" и guard своей версии placement_turn

placeable = читаемые живые строки единиц без удалённых/надгробий и всех снятых по ends или retire_when на шаге 4; ручная просроченная строка может оставаться в хранилище, но не входит в это множество. Набор placeable читаемых живых единиц без удалённых/надгробий, ends и retire_when используют до группировки и подсчёта веса.

ждущие = placeable ∩ (единицы без размещения ∪ единицы уходящих ∪ вне достижимости); группа — одна штука. Только эти единицы участвуют в нехватке, росте, таймере отсутствия нехватки и сокращении; сохранённые просроченные и garbled не вызывают заказа и не задерживают сокращение.

живые(s) = живые процессы роли сервера s (живой воркер N3 «выбрать»), включая базовый `<prefix>`-`<s>`-1 и жертву сокращения (retiring): для «в пути» и «failed to raise» жертва — живой процесс, want её включает, пока она жива; из пула размещения она исключена (сократить); номер n имени — целым (P/03.2 N1.4)

в пути(s) = число номеров 2…want(s), у которых нет живого процесса роли сервера s (по пульсам, живые(s)) — заказанные и ещё не поднявшиеся, пока не снят заказ по сроку; базовый `<prefix>`-`<s>`-1 не заказывается и в пути не бывает; по пульсам — для нужно, порядка кандидатов, условия сокращения, снятия по сроку и wants.`<s>`.pending; кандидат и доля — по двери (свободно(s) ниже); при номерах подряд — max(0, want(s) − живые(s)). no_base: базовый `<prefix>`-`<s>`-1 мёртв — wants.`<s>`.state no_base, тревога; сервер не кандидат; базового в пути нет, поэтому сокращение роли на других серверах он не держит

свободно(s) = room.`<sub>`(s) − |{2…want(s)} ∖ live.`<sub>`(s)| — по строке двери platform/doors/`<s>` одного снимка (P/05 N1.4 door_row): live.`<sub>` — номера n ≥ 2 живых замков присутствия, по которым посчитан room.`<sub>`; считается один раз за проход до цикла наборов и уменьшается на каждую долю (заказать); нет live.`<sub>` или он нечитаем — сервер не кандидат

порядок наборов: воркер или сервер, подходящий нескольким наборам меток, отдаёт свою ёмкость (свободно воркера), свободно(s) сервера и в пути наборам по очереди — в порядке байт UTF-8 канонической записи набора (уникальные метки по возрастанию через запятую, повтор схлопывается — набор меток есть множество; пустой набор — первым); каждая единица ёмкости, свободно(s) и в пути расходуется одним набором один раз; набор берёт свободное, свободно(s) и в пути только до своей потребности (min): взятое набором в пути — min(Σ в пути, процессов), остаток — следующему набору

Для набора меток воркер без названной ёмкости использует placement.capacity.default; названный 0 на default не заменяют. per — наименьшая положительная ёмкость пригодных живых воркеров, названная или умолчальная; если такой нет, placement.capacity.default используют только при положительном значении. Если положительной оценки и умолчания нет, набору ничего не заказывают и дают withheld "no positive capacity estimate". Вектор order возвращает обычные поля: per null и нули processes/in flight/needed/withheld, плюс why; отчёт всё равно показывает short[] с workers 0 и словами withheld, в том числе нехватку веса и групп. Ноль означает отсутствие вычислимой оценки, а не нехватки; это не ошибка шага.

Иначе processes = ceil(max(0, сумма весов ждущих − свободное у пригодных живых) / per) плюс один на каждую группу, которой нигде нет места; needed = max(0, processes − сумма in flight(s) пригодных серверов). Ёмкость в пути вычитают и для групп, чтобы следующий проход не заказал тот же рост снова.

Воркер, держащий исключительное место (N1.3 affinity.exclusive), не даёт свободной ёмкости прочим единицам.

Ждущие единицы, связанные с исключительным местом без держателя, вызывают заказ для этого места: сервер из server_field рассматривают вне очереди с долей 1; пустое server_field заказа не даёт, место ждёт держателя. Если секрет этого места не открылся, заказа нет, withheld "\<place_by\> \<place\> is sealed". Sealed берут из place_error.\<place\> = sealed в пульсах живых воркеров роли сервера места (P/03.4 N1.1); если живых там нет, дают один обычный заказ.

У манифеста с places.wanted место без держателя даёт ждущую штуку веса 1, если строка места проходит places.where, удержание не действует и `<sub>/<wanted>/<place>` существует и читается. Месту не обязательно ждать запись или единицу: без держателя никто не читает его архив. Для повода places.wanted Сервер — из строки места, как у исключительного места: server_field непуст — этот сервер кандидат вне порядка, доля 1, поверх общей проверки кандидата; не годен — заказа нет, место ждёт; Sealed — withheld, как там. server_field пуст — место на любом сервере: штука идёт пустым набором меток обычной пробой; предел: новый процесс возьмёт первое свободное место, не обязательно это, лишний процесс живёт до сокращения. Для повода places.wanted нечитаемая строка wanted не даёт причины заказывать; пишут строку журнала без значения. Другое пустое место само по себе заказа не вызывает.

При servers: distinct и place_by из пульса свободное у пригодных живых учитывает только хранителей мест. Для такого набора distinct с местом из пульса сервер-кандидат имеет in flight(s) = 0 и не имеет живого пригодного процесса без места. Для такого набора distinct с местом из пульса за проход заказывают не больше одного пробного процесса, на сервере — не больше одной незаконченной пробы: место неизвестно до старта. Для такого набора distinct с местом из пульса отсутствие кандидата или исчерпанный рост оставляют остаток needed в withheld с "no free \<place_by\>" (N4). Проба одного сервера не мешает росту на другом.

кандидат s: строка заказа есть; базовый `<prefix>`-`<s>`-1 жив (иначе no_base выше: сервер не кандидат); свободно(s) > 0; want(s) < WANT_NUM_MAX (иначе причина «`<s>` has no instance numbers left», тревога workers.no_server); метки сервера подходят набору (constraint), requires: resource — ресурс не silent; не дренируется, не decommission-pending и не выведен; не «failed to raise» (RAISE_QUIET); servers: distinct — по месту place_by: при place_by: server сервер с живым воркером роли не кандидат, при поле пульса место нового процесса до старта неизвестно — выбор сервера не ограничивает. порядок: меньше живые(s) + в пути(s) — по пульсам (не по двери), затем имя сервера в байтах UTF-8

Нужное needed набора распределяют по кандидатам в их порядке; доля не больше min(free(s), WANT_NUM_MAX − want(s)). У манифеста с непустым door.pass.calls потолок want(s) — 1 вместо WANT_NUM_MAX: билет привязан к листу сервера, а лист один на роль и сервер (gate-and-pass, пропуск второго рода). После каждой доли заказа её вычитают из free(s) прохода. want(s) увеличивают на долю записью строки заказа с CAS прочитанной версии и guard своей версии placement_turn; why использует "\<n\> more for \<labels\> on \<s\>: \<waiting\> waiting", с каноническим набором меток и "any labels" для пустого набора. want — абсолютная цель: повторный проход или новый держатель очереди пересчитывает needed с ёмкостью в пути, не повторяя прироста; на штуку нехватки (набор меток) действует один логический заказ. После всех долей нераспределённый остаток needed набора удерживается, как при нехватке кандидатов; без кандидатов остаётся всё needed. Число удержанных процессов — в workers_withheld{labels} (P/06.5), слова — в short.withheld отчёта (N1.2), тревога — workers.no_server {server, labels, want, why}.

Конкуренция подсистем разных ролей за последнее место сервера — допустимая задержка; общий потолок памяти сервера по всем ролям остаётся пределом схемы.

снять по сроку: в пути(s) > 0 дольше WANT_GRACE (N1.4 сроки) → want(s) := 1 + |живые номера ∩ {2…want(s)}|; скрипт затем перенумерует: номер выше want остановит, недостающий ниже — запустит; остановка воркера с назначением — переезд единиц; сервер «failed to raise» на RAISE_QUIET, raise_failed.`<s>`.times + 1, тревога workers.raise_failed {server, labels, want, why}; после RAISE_FAILS_LOUD подряд — повышенной важности; снимается, когда сервер поднял заказ; нехватка заказывается на следующем кандидате в том же проходе; базовый в счёт «failed to raise» не входит

номер выше want: живой процесс роли сервера s (имя и номер N — договор имени слота, «Имя процесса роли и его номер»; не процесс роли — правило не применяется) с номером больше want(s) (поднялся после снятия, жертва сокращения до остановки, остаток гонки двери) — не в пуле (как retiring) и единиц не получает; его останавливает скрипт сервера (P/02.4 N1.5 rules 3); want(s) контроллер не поднимает

Шаг сокращения 9a следует условиям, выбору жертвы и переходам ниже. [Проверки сокращения](../forms/README.md#проверки-сокращения) выбирают первую прежнюю причину отказа; только `ok` разрешает сокращение. Правила жертвы, защиты нужного места, переноса и завершения ниже остаются в силе.

жертва: кандидат — только живой воркер с n = want(s) > 1 своего сервера s; выбирается наибольший допустимый n (целым); живой номер выше want(s) — не жертва: его останавливает скрипт, конец сокращения его не гасит; при равенстве номеров на разных серверах — меньшее имя сервера в байтах UTF-8 первым, как порядок кандидатов; каждая её единица (группа — целиком) проходит выбрать(единица) на пуле без жертвы; иначе не сокращать, причина в отчёте. wanted: жертвой может быть только верхний заказанный номер n = want(s) сервера. Если этот воркер держит место с читаемой строкой places.wanted, пропустить весь сервер и искать верхнего кандидата другого сервера по прежнему порядку номера/сервера. К меньшему номеру этого сервера не переходить: уменьшение want остановило бы защищённый верхний процесс. Снятое wanted-место тут же заказало бы процесс.

retiring: записать retiring = \<жертва\> в строку заказа её сервера (cas, guard turn); жертва — вне пула всех шагов (выбрать, переезд, дом, достижимость), и у нового держателя очереди — по строке; одна жертва на роль за раз; в живых(s) для «в пути» и «failed to raise» она остаётся, пока жива

перенос: не больше SHRINK_BUDGET единиц за проход, причина «`<w>` is retiring: the role shrinks on `<s>`»; первая неделимая группа идёт и сверх бюджета (как достижимость, шаг 5)

конец: назначение жертвы пусто → want := want − 1 (не ниже 1) и retiring снят — одной записью; скрипт сервера останавливает процесс с наибольшим n (P/02.4 N1.5) — это и есть жертва: в пути нет (условие), номера 2…want(s) живы, и жертва — номер want(s)

отмена: нехватка вернулась до конца → retiring снят, жертва снова в пуле

дренаж: сервер в platform/drain — новых заказов не получает; его дополнительные процессы сокращаются по одному без выдержки и гистерезиса (единицы и так уходят, «server `<s>` draining»), want − 1 при пустом назначении жертвы, до 1

вывод: шаг 2 — строку заказа сервера удалить с cas и guard turn; новых заказов сервер не получает

**Гонки.** Два контроллера пишут одну строку заказа: cas по версии и guard `placement_turn` пропускают одного, второй перечитывает и пересчитывает от абсолютной цели. Отдельного вида записи в `placement_intent` заказ не имеет: абсолютная цель под cas со стражем `placement_turn` и ёмкость в пути закрывают повтор прироста — повторный проход и новый контроллер доводят цель, а не прибавляют.

Заказ против скрипта: скрипт читает ряд раз в минуту (P/02.4 N1.5) и отстаёт — процесс, поднятый после снятия заказа, с номером выше want не в пуле и останавливается скриптом; процесс, остановленный скриптом при непустом назначении (рассинхрон), отдаёт слот штатно (P/03.4 N3 «stop») — это переезд, не потеря единиц.

Сокращение и смена держателя очереди: `retiring` в строке, новый держатель продолжает перенос, а не выбирает новую жертву.

Дверь против пульсов: кандидат и доля считаются по `live.<sub>` двери, нехватка — по пульсам; остаток гонки — процесс с номером больше want, поднятый после отметки двери, не дольше периода отметки (ALIVE_EVERY): его ловит проверка памяти скрипта воркеров (P/02.4 N1.5, потолок по памяти).

**Пробный процесс при `distinct`.** Воркер без места единиц не несёт и на чужой сервер не уходит: место на его сервере освобождается только уходом хранителя, до того он простаивает. При servers: distinct и месте из пульса новый пробный процесс имеет место "" до первого пульса с занятым местом. В этом окне его сервер не кандидат; он не кандидат и пока проба заказана, но не поднялась. Задержанный старт не даёт этому серверу второй пробы; другие серверы остаются кандидатами, с одним пробным процессом за проход.

### вывести_сервер(s) — запрос консоли, исполнение контроллером

Вывод сервера контроллером следует процедуре приёма, отдачи, уборки и завершения ниже.

console: запрос, 409 server answers, platform/decommission/`<host>`, снятие двери и отзыв — по-прежнему P/06.6 N3.

есть действительная окончательная отметка и стоящий запрос: не переписывать отметку, её слоты или оставшиеся вклады; новая очистка не разрешена.

0. Читаемый pending возобновить до нового плана. Фиксированный request_index строки pending по-прежнему должен обозначать нынешний запрос.

До изменений проверить инварианты: имена remaining различны и не входят в released/skipped; released и skipped не пересекаются; current — упорядоченное подмножество released. До мутации проверяют, что slot_cursor < len(current), а from_cursor <= len(from), когда план pending вывода сервера находится в cleaning. До мутации проверяют, что каждый from-префикс плана pending принадлежит своей подсистеме. Список from фиксируется при приёме плана по объявленным собственным книгам и не пересобирается из нового манифеста. Повреждённый план хода pending — ошибка шага: сохранить его; не выводить завершение, ничего не отдавать/снимать и не заменять свежим планом. Одной читаемости по схеме недостаточно.

Если строки pending и окончательной отметки нет, а сервер слышен по обычному правилу наблюдения, запрос вывода оставляют без изменений; иначе полностью читают запрос, собственные слоты и нужные метаданные. Неполный или нечитаемый источник при подготовке плана вывода не означает пустой список.

Зафиксировать читаемые исходные слоты с server = s как упорядоченные {name,index}, свои from-префиксы, asked_at, manifest_rev, метаданные units/holds. До приёма проверить полные ключи, наибольший возможный сериализованный progress и окончательную отметку, вес строк и настоящее ограничение тела batch. Для cleanup_index учесть ширину wire index P/01; непрозрачную версию не разбирать. Непредставимый план — ошибка шага до изменения слотов/заказа, не частичная окончательная отметка.

1. Принять pending с cas "" и удалить имеющийся want с прочитанным cas одним условным пакетом. Пакет приёма плана использует guards своей версии placement_turn и фиксированного request_index. Учитывают обе записи пакета приёма плана. Prepared имеет remaining; нет кандидатов — finalizing. Pending-сервер вне пула размещения, новых заказов и автоматического создания want для него нет.

После приёма продолжать только этот план, также после обрыва или ответа сервера; нового держателя не добавлять/не усваивать.

2. Prepared: читать очередного кандидата только для подтверждения исходного index и получения тех же читаемых items. Иной index (включая отсутствие) — устаревший кандидат: имя в skipped, новую версию не подставлять для отдачи. Нет ответа — отложить шаг; это не устаревание.

При отдаче запланированного читаемого слота в prepared сохраняют holder/gen/server/until и ставят released = "true"; gen не выдумывают. Записать до BATCH_WRITES - 1 слотов с исходными cas и pending с его cas, под guards очереди и запроса. Атомарно внести имена в released/current и перейти к cleaning; общий index ответа — версия ВСЕХ отданных слотов И pending.

После потери ответа cleaning с пустым cleanup_index несёт эту точную версию в собственном index строки: нового чтения слота не нужно.

Если from-семейств нет, пакет отдачи слотов сразу переводит в prepared или finalizing с пустыми current/cursors.

Отказ пакета отдачи не меняет ни слоты, ни progress: барьер/перечитка pending; отбрасывать лишь кандидатов с доказанно изменившимся исходным index, не повторять отдачу против новой версии слота.

Пропущенных кандидатов сохраняют под CAS pending и guards turn/request; когда оставшихся кандидатов отдачи нет, сразу переходят в finalizing.

3. Cleaning обрабатывает по одному слоту current, from-префиксы в фиксированном порядке, с разбиением на ограниченные пакеты. Полномочие уборки нынешнего слота — cleanup_index, если непусто, иначе нынешний индекс строки pending. До ЛЮБОЙ перезаписи хода точное полномочие отдачи сохраняют в cleanup_index; позднейший индекс pending его не заменяет.

Существующие вклады удаляют по их прочитанным CAS вместе с ходом pending одним пакетом, под guards своей очереди, фиксированного запроса и точного индекса отдачи этого слота. У каждого пакета уборки учитывают все удаления И записи хода/служебные записи, каждый guard, веса строк и полное сериализованное тело. Пакет уборки не использует ключ guard как ключ записи.

Подтверждённое отсутствие вклада продвигает курсор уборки; неизвестное чтение не продвигает.

409 conflict или 412 guard отбрасывает ВСЕ оставшиеся удаления этого слота, без нового чтения слота и повтора. Продвижение курсора уборки записывают под guards turn/request; вклад нового держателя не удаляют.

Только подтверждённое продвижение курсора разрешает следующий слот current, затем следующий кусок отдачи. После завершения одного слота current продвигают slot_cursor и сбрасывают from_cursor. После завершения всего куска current очищают current, cleanup_index и оба курсора; защищённой записью хода ставят prepared при непустом remaining, иначе finalizing.

4. Каждый prepared/cleanup/final пакет укладывается в BATCH_WRITES, BATCH_GUARDS и настоящий потолок тела. Не помещается даже одна неделимая операция с обязательными служебными записями — ошибка шага, progress сохраняется, завершение не публикуется.

Очередь продлевать по обычному правилу; неизвестность записи или потеря очереди прекращает изменения за прежним барьером.

Новый держатель после захвата очереди перечитывает pending и продолжает его фазу, не начинает отдачу заново по именам слотов.

5. Только когда remaining пуст и допустимые снятия нынешнего куска подтверждены либо консервативно сброшены — finalizing. Атомарно записать отсутствующую окончательную `<sub>`/decommissioned/`<host>` из released/units/holds и asked_at (at = now), удалить pending с cas и остаточный want с cas при наличии, под guards очереди/запроса. В пакете завершения учитывают КАЖДУЮ служебную запись. Окончательная отметка — ПОСЛЕДНИЙ атомарный шаг, не приём плана и не первый отданный кусок.

Отказ/неизвестность финального пакета не доказывает завершения: барьер и подтверждение настоящего pending/final состояния перед продолжением.

6. Отозванный/заменённый запрос отменяет прежний pending с cas и guards нынешнего состояния запроса и своей очереди; это не откатывает подтверждённые отдачи/снятия, не выдумывает окончательную отметку и не разрешает старый пакет новому запросу. Отзыв по-прежнему снимает имеющуюся окончательную отметку.

Ресурс вновь пишет дверь; вклады возвращает обычный start/capture cleanup, не откат.

Новый запрос требует нового допуска и свежего плана.

Сторона консоли (отказ 409 `server answers` по [договору наблюдения](../../../common/ru/contracts/observation.md), запись запроса, удаление строки двери, отзыв) — [глава P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N3 «вывести_сервер(s) — сторона консоли»; здесь — исполнение контроллером.

**Гонки.** Вывод сервера и возврат его воркеров: `decommissioned/*` пишется с `cas`; воркер этого сервера при захвате проверяет вывод (P/03.2 N3 «start()», шаг 3: `platform/decommission/<s>` или `<sub>/decommissioned/<s>`) и имя не берёт; запрос консоли и проход контроллера разделены строкой — повтор запроса идемпотентен.

### manifest_rev — страж правила

Каждая запись размещения следует защите ревизии манифеста ниже. перед каждой записью placement (разместить, перенести, снять): отсутствие manifest_rev нечитаемо и не дописывается; row.manifest_rev > моя ревизия → не трогать; строка — в manifest_behind. manifest_behind (N1.2): число строк этого прохода, запись которых отложена из-за отставшего манифеста; каждая строка — один раз за проход, сколько бы попыток записи её ни коснулось

---

**Гонки.** Смена манифеста во время прохода: `rev` читается раз на проход, решения пишутся с этим `manifest_rev`; смену `rev` контроллер видит проверкой метки (P/02.3) и останавливается с кодом 0; новый экземпляр с новой `rev` перечитывает всё; строка с прежним `manifest_rev` — снимок решения, не правило.

### старт контроллера — проверка схемы

Окружение и аргумент запускателя перечислены в [forms/daemon-flags.tsv](../../forms/daemon-flags.tsv). Вычисляемые умолчания и проверки общих договоров остаются их правилами; CLI-флагов не добавляется.

Нынешняя проверка старта контроллера — общий блок [P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N3 «старт консоли — проверка схемы». Строка platform/schema, SCHEMA и подъём остаются P/06.6 N1.1a, N3 «поднять_схему». старт: договор схемы «Проверка при старте» ([договор схемы](../../../common/ru/contracts/schema.md))

### снимок таблиц — после снимка единиц, до окончательного отчёта

Снимки таблиц следуют процедуре ниже после снимков единиц и до окончательного отчёта. по каждой таблице из domain.view_tables манифеста: строки таблицы → rows по N1.3b, порядок — key; строка, чьё поле не читается своим типом, — пропустить, счёт snapshot_rows_garbled; rows совпали с теми, что этот процесс уже записал, — не писать, ts прежний;

сериализовать; больше SNAPSHOT_TABLE_MAX → записать заглушку N1.3b ceiling, snapshot_tables_refused + 1, строка лога раз на серию;

ошибка чтения таблицы — объект не писать, строка лога раз на серию: пустой объект вместо непрочитанного не публикуется

### снимок — после управляющей части, до окончательного отчёта

Снимки единиц следуют процедуре ниже после управляющей части и до окончательного отчёта. по воркеру: строки единиц его назначения → [{id, revision, поля snapshot (маска адресов), worker, server}];

Строку единицы, поле снимка которой не читается своим типом, пропускают; раз за серию пишут журнал и увеличивают `snapshot_rows_garbled` отчёта прохода (N1.2; N1.3a garbled).

неразмещённые → unplaced; шард, который был и не заполнен → пустой; без единиц → пустой unplaced; пустой шард — {cluster, worker: null, ts, `<rows>`: []} (N1.3a);

Каждая единица снимка несёт состояние по N1.3a (действующие состояния из списка снимка); нечитаемое состояние пропускают у этой единицы и увеличивают `snapshot_state_garbled`.

сериализовать каждый шард; проверить размер по N1.3a до записи; больше L → TooLarge, этот шард не писать; допустимый шард записать; TooLarge хранилища → тот же отказ; ошибка публикации — одна строка лога на серию;

TooLarge до записи сохраняет прежний шард и его время; неизвестный исход записи не доказывает, что шард остался прежним. При любой ошибке не публиковать пустой шард вместо непроверенных данных

**Гонки.** На одном сервере один контроллер манифеста; разные серверы могут публиковать разные локальные копии одного логического ключа шарда. Выбор по written не создаёт общий момент чтения. Строки и шарды публикуются по отдельности: снимок — наблюдённая конфигурация, не согласованная резервная копия. Ошибка чтения строк/списка не разрешает публиковать пустой шард; ошибка одной записи не откатывает уже опубликованные. Потребитель проверяет revision и не выводит отсутствие из неполного набора.

### вырвать питание (ничего не делать) — учение

t = 0 сервер выключен; его демон — минус голос; его пульсы и дверь перестают меняться. В этом учении примерно через 45 s контроллеры с заранее известными пульсами наблюдают истёкшие слоты и молчащий ресурс, с допусками N3. В этом учении контроллеры с заранее известными пульсами переносят единицы через SLOT_TERM + LOST_AFTER при всех допусках N3 и свободной ёмкости; новый держатель берёт следующую эпоху. В этом учении при unknown/unavailability/нехватке места общего срока переезда нет; архив остаётся на томе сервера.

В этом учении отказа у соседей есть только подтверждённые зеркальные копии.

возврат демон рестартует с сохранённым member.json (не повторяет join); ресурс тянет бакеты (restore); воркеры берут свободные имена; имена с истёкшими слотами — по слову контроллера; ничего не едет назад, кроме объявленного `home` (N3 «проход()», шаг 7, HOME_BUDGET)

**Гонки.** Отказ совпадает с продлением, записью и зеркалированием; границы — этот урок, [P/03.2](../../../03-worker/ru/spec/03.2-worker.norms.md), [P/05](../../../05-resource/ru/spec/05-resource.norms.md). Отсутствие действий оператора не превращает наблюдение в снимок. Указанные сроки — профиль учения, не гарантия произвольного отказа.

---

## N4 Отказы

Отказы дверей консоли (политика, дренаж, метки, вывод сервера, `/where`, общие коды консоли) — [P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N4 и [P/06.5](../../../06-console/ru/spec/06.5-console.norms.md) N4. Строка «intent не по форме N1.5» — здесь целиком: 503 у читателей-дверей консоли, failures у контроллера.

Закрытый каталог — [forms/refusals.tsv](../../forms/refusals.tsv), `chapter = 4`. Столбцы `cause`, `outcome`, `diagnostic`, `caller` задают причину, исход, диагностику и действие вызывающего; фиксированные машинные коды дополняют эти поля. `peer` ссылается на договор консоли, не на HTTP API контроллера.

---

## N5 Приёмка

Приёмка использует стенд из воркеров и контроллера `testsub` и `testsub2` реализации под управлением раннера на каталоге из двух манифестов ([общий README приёмки](../../../common/ru/acceptance/README.md), раздел «Стенд»); сц. 12, 14–17 — с ресурсом P/05 на сервере контроллера; чтение строк через дверь хранилища P/01.1, двери консоли (`/where`, `/unplaceable`, `/servers`, `/metrics`) и объекта отчёта прохода дверью ресурса. Приёмка содержит 37 сценариев / 533 шага. В сценарии 11 шаги 7–12 готовят полку. Сценарии 07, 11 и 13 начинаются с `@start resource`; сценарий 25 использует `@cut role`/`@mend role`, а сценарии 26 и 27 — `@freeze`/`@thaw`.

Сценарии 03 и 08 проверяют снимок без шагов `/metrics` консоли; сторона читателя — [глава 6.5](../../../06-console/ru/spec/06.5-console.norms.md).

Подробные описания случаев и ожидаемые исходы записаны в данных судьи о случаях. Правила и публичная область приёмки остаются в этой главе.

Двери консоли без воркеров (единица без воркера, `/unplaceable`, политика, дренаж, метки, вывод сервера) — сц. 01–07 [приёмки P/06.6](../../../06-console/ru/acceptance/6/README.md).

Снимок — сц. 03 и 08; возраст шарда и испорченный шард в `/metrics` консоли — приёмка [P/06.5](../../../06-console/ru/acceptance/5/README.md); шарды ушедшего воркера — N3 «snapshot»: пустой шард — сц. 40, размер шарда с `ts` — N1.3a `ceiling` — чтением.

Отказ сервера (N1.4a) покрывает учение 05 [системной приёмки](../../../common/ru/acceptance/system/README.md). Свидетели отказа сервера также включают сценарий `09-resource-door` [приёмки P/05](../../../05-resource/ru/acceptance/README.md) (judge-only: проверки P/04-R065, P/04-R066). Свидетели отказа сервера также включают сценарий `14-resource-silent` [приёмки P/06.5](../../../06-console/ru/acceptance/5/README.md).

Отказ старта по схеме — N3 «старт контроллера — проверка схемы»: `version` выше SCHEMA и не число, код 2 — сц. 23; ошибка чтения — ждать — сц. 25; «before reading the manifest» — чтением.

Векторы [`order`](../vectors/order/README.md) (нехватка набора меток и заказ по серверам), [`shrink-victim`](../vectors/shrink-victim/README.md) (жертва сокращения) и [`shrink-allowed`](../vectors/shrink-allowed/README.md) (разрешено ли сокращение и порядок причин отказа) — N3 «shortage(), order()…», «shrink».

Проверяются чтением и стендом (нужны воркеры с пульсами — сц. 02-unit приёмки P/03.3, 03-sigterm — P/03.4, 05-sigkill — P/03.2; стенд системной приёмки): выбор воркера и причина; группа целиком (кроме «место на всех или ждут все» на одном воркере — сц. 22); вес и свободная ёмкость; `distinct` и хранитель места; спред, соседство, дом, сродство (кроме спреда по непустой зоне, связывающей полки, переезда домой и `admits: false` — сц. 36–39, дома у держателя при двух местах сервера — сц. 43, на месте без сервера — сц. 44); судьба слота по каждому правилу и `names_given` с версией (кроме release слота без единиц и записи release по строке слота — сц. 21; запаса и `hung` живого молчащего воркера с единицей и без — сц. 26, 27; `wait` до HUNG_MOVE_AFTER — сц. 42); переезд через intent и починка `sync` (кроме восстановления intent одним держателем, `sync` одного назначения и нечитаемого intent — сц. 28–30); уход по каждой причине (дренаж — сц. 33, место не принимает — сц. 39); дренаж с живыми воркерами (кроме переезда и `safe` — сц. 33); вывод с живыми воркерами, `gone: true`; группа url без хоста (без значения и с нечитаемым значением, а с ними `spread_by: zone` без значения — сц. 11; дренаж «назначение ∪ `status`» — сц. 07 приёмки P/06.6); `fates` и `since`; присутствие только из live пульса ресурса; заказ, снятие по сроку, номер выше want и сокращение, кроме условия сокращения по входу прохода — с ветвью «live workers without a place are not shrunk while units wait» при `servers: distinct`, которую сц. 17 от гистерезиса не отличает, оно проверяется вектором `shrink-allowed`; удаление по `delete_after`; `manifest_rev` и `manifest_behind` при двух ревизиях манифеста (строки и очередь, решённые более новой ревизией, без смены манифеста — сц. 31, 32); отчёт прохода.

**Обязательства прохода.** Приёмка содержит 50 CALL-швов. Публичные обязательства охватывают состояние ресурса и судьбу слота, верхний номер и защиту wanted-места совместно с планом остановки скрипта P/02, исключённые просроченные ручные строки, завершённый вывод сервера и долговечное восстановление под точными guards, ограничения имён штатного загрузчика и проверку прогресса до изменения. Публичные свидетельства прохода используют существующие порты controller-pass/fate и фактические наблюдения IO из README форм, а не новые команды или части пакета. Подробные входы и исходы именованных свидетелей — покрытие только для судьи.

Источник нынешних reader/writer — формы семейств, включая три счётчика отчёта, один массив снимка, обязательный manifest_rev решения и непустую причину active. Pending recovery, точные непрозрачные guards и нынешние именованные свидетели сохраняются.

Проекции source/schema не доказывают OS-остановку, восстановление процесса или runtime-приёмку; проверки генераторов/раннера и совместный GATE остаются отдельно.

### Свидетельства вне TSV

Сценарии 01–06 [приёмки P/06.6](../../../06-console/ru/acceptance/6/README.md) наблюдают пустой пул и несколько отказов, не доказывают остальные ветви.
«Чтение» ниже означает проверку переходов реализации владельцем реализации с указанными
вмешательствами; в окне перевода автор читает только документы и не заявляет прохождение кода.

| Нормы | Предмет и вмешательство | Что должно быть показано |
|---|---|---|
| P/04-01…03, 12, 16 | два контроллера, пауза/обрыв после каждого чтения и записи placement/workers; более новая manifest_rev | cas/guard по своим версиям, повторная проверка мутатором, починка sync, старое правило не пишет |
| P/04-04, 05 | первый взгляд, сдвиг ts, отсутствие/порча/пустая строка меток (строка, пустая и нечитаемая строка при метках узла — на стенде сц. 24) | жизнь по местному наблюдению; метки не угадываются при неответе |
| P/04-06…09, 18 | два веса, равенство, группа, distinct, несовместимые constraint/home; вес строки `"7x"` и ёмкость пульса `"2x"` | допустимый кандидат и непустая причина; предпочтение не обходит фильтр; испорченный вес — единица в `garbled` и `unplaceable`, испорченная ёмкость — воркер без новых единиц, причина в отчёте, не `default` |
| P/04-10, 11 | каждый исход судьбы до/на/после границы; продление между суждением и захватом; gen повреждено; `gone` без назначенных единиц и с ними (без единиц и запись release — на стенде сц. 21) | порядок судьи, версия names_given, неизвестное поколение не сбрасывается; `release` раньше `move` у слота без единиц (таблица переходов N3) |
| P/04-13, 14, 15 | все причины ухода; заказ двумя контроллерами, снятие по сроку, номер выше want, сокращение со сменой держателя очереди; отсчёт delete_after | бюджеты/группа, один логический заказ на кусок нехватки, retiring переживает смену держателя, удаление по версии и местному времени |
| P/04-17 | успешный/частично отказанный проход, grows включён/выключен | обязательные поля отчёта, failures, short и wants соответствуют выполненным шагам |
| P/04-20 | единица, чей ключ `<sub>/placement/<id>` на 1 байт длиннее предела ключа хранилища, при свободной ёмкости; та же единица в группе | intent не записан; единица в `unplaceable` с `why`; другие единицы той же подсистемы размещаются |
| P/04-19 | два контроллера допускают разные единицы при capacity 1; spread_by; группа с разными home; смена держателя после каждого шага intent | одно общее решение, нет перегрузки/расщепления от конкуренции; поздние записи отсекаются turn; неполный перенос доводится до следующего допуска |

---

## Решает реализация

Реализация обязана назвать в своём описании:

1. **как кэш и повторы исполняют фиксированные источники** — PASS_EVERY, TURN_BUSY_RETRY и WRITE_CONFLICT_LIMIT заданы forms/runtime-constants.tsv, не выбор реализации;
2. **кэш между проходами** — что держится по версии строки, и как это не меняет решений (решают строки, не кэш);
3. **как ресурс сервера сообщает присутствие процесса** (форма поля `workers` пульса ресурса — P/05 N1.4) и замок присутствия ([договор замка присутствия](../../../common/ru/contracts/presence-lock.md));
4. **как читаются действующие входы** — канал и умолчания у именованных владельцев lifecycle/forms/common, не второй местный выбор;
5. **как запрашивается перебалансировка** и кто её зовёт; бюджет;
6. **дополнительные поля отчёта** сверх N1.2 и как из него делаются метрики (ряды `<sub>_reconcile_*`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — текст»);
7. **точные тексты** причин и отказов сверх грамматики N3/N4;
8. **что делает манифест без `grows`** с нехваткой (ничего не считает) и где живёт скрипт сервера (`w2c-workers.sh`, P/02.4 N1.5 `script`);
9. **команду печати отчёта прохода** `<sub>/controller/pass` для приёмки — по разделу «Стенд» общего README приёмки.
10. **как публикуется снимок** при отказе хранилища (лог раз на серию); период — после каждого прохода (N1.3a `publish`), выбора нет;
11. ~~**откуда берётся `cluster` снимка**~~ — нормировано: `CLUSTER` окружения (N1.3a; P/02.4 N1.2), не задано — `local`.

---

## Чеклист готовности

Реализация соответствует уроку, когда выполнена каждая норма; id нормы `P/04-MM` — то, на что ссылаются дельты решений,
находки и записи окон:

- [ ] **P/04-01** [test, reading] эффективное решение — active intent для members, иначе placement; назначение производное; `rev` растёт; `sync` чинит оборванное — сц. 01 [приёмки P/06.6](../../../06-console/ru/acceptance/6/README.md); снятие всех members до добавления и доведение новым держателем после обрыва посередине — шов `s18-intent-removals-before-add`, нет нового допуска после неизвестного исхода — шов `s19-intent-unknown-barrier` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R006, P/04-R021, P/04-R027, P/04-R036) (`CALL controller-complete-intent`); восстановление active intent новым держателем — сц. 28, `sync` одного назначения и `diverged` — сц. 29, нечитаемый intent у контроллера — сц. 30 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R006, P/04-R021, P/04-R027, P/04-R036); двойное чтение intent — проверяется чтением
- [ ] **P/04-02** [test, reading] решения и незавершённый intent сохраняются в хранилище; каждая запись с `cas`; изменения размещения проходят через общий turn с CAS/guard по N1.5/N3; локальная история наблюдения начинается заново после перезапуска и не заменяет чтение решения — перезапуск контроллера: решение и эпоха прежние, новый экземпляр размещает — сц. 20 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R209, P/04-R212, P/04-R027, P/04-R030); незавершённый intent из хранилища доводит новый держатель — сц. 28, в логическом времени — шов `s18-intent-removals-before-add` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R209, P/04-R212, P/04-R027, P/04-R030) (`CALL controller-complete-intent`); прочее проверяется чтением
- [ ] **P/04-03** [test, reading] порядок прохода N3 — проверяется чтением; попытка на шаг: ошибка одного шага даёт `ok: false` и `failures` 1, а последующие шаги всё равно идут — шов `s33-pass-report-partial-failure` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R030) (`CALL controller-pass`)
- [ ] **P/04-04** [test, reading] картина мира: ёмкость, сервер, метки узла — без срока; жизнь — по изменению пульса за 45 с по часам контроллера; впервые увиденное — только что изменилось — проверяется чтением (стенд P/03.3, сц. 02-unit; срок 45 с ни один сценарий не наблюдает); граница `≤ LOST_AFTER` — вектор [`fresh-age`](../../../common/ru/vectors/fresh-age/README.md); чтение пульса по форме его семьи — векторы [`heartbeat-read`](../../../common/ru/vectors/heartbeat-read/README.md)
- [ ] **P/04-05** [test] метки сервера: строка побеждает узел, пустая — «ничего не достаёт», нечитаемая — последние и без суждения; азбука меток — векторы [`labels`](../../../common/ru/vectors/labels/README.md) и сц. 05 приёмки P/06.6 (отказы формы); приоритет строки над узлом, пустой список, нечитаемая строка — сц. 24 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R005, P/04-R030) (на стенде приёмки P/06.6 (сц. 01–07) воркеров нет)
- [ ] **P/04-06** [test, reading] пул, ограничения, предпочтения в порядке N3; размещённое не пересматривается — проверяется чтением; предпочтение не обходит ограничение — шов `s21-preference-respects-filter` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R009, P/04-R030, P/04-R033) (`CALL controller-choose`); пул и пригодность сервера — векторы [`pool`](../../../common/ru/vectors/pool/README.md) (judge-only: проверки P/04-R009, P/04-R030, P/04-R033); нечитаемое назначение вне пула — сц. 41; `spread_by` с непустым значением — сц. 36; связывающая полка ведёт к своему держателю — сц. 37; дом (шаг 7) — сц. 38, держатель места при двух местах сервера — сц. 43, на месте без сервера — сц. 44 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R009, P/04-R030, P/04-R033); запас на сервер места при воркере другого сервера — чтением: у выбора воркера нет векторов, а сц. 43 стоит на одном сервере;
  `affinity.strict` выбирает связывающие строки, несвязывающая полка — предпочтение: `tallies` на полке `plain` при
  `strict.kind: [reserve]` размещаются — сц. 07 [приёмки P/03.6](../../../03-worker/ru/acceptance/6/README.md) (judge-only: проверки P/04-R009, P/04-R030, P/04-R033)
- [ ] **P/04-07** [test, reading] вес и свободная ёмкость: Σ весов, строго больше, первый по имени — равенство ёмкости: сц. 07; тяжелее любого — `unplaceable` — проверяется чтением
- [ ] **P/04-08** [test] группа целиком: место на всех или ждать все — сц. 22; значения `group_by` нет, оно пусто, не читается
  или без хоста — не группа — векторы [`group-of`](../../../common/ru/vectors/group-of/README.md) и сц. 11; `spread_by` без значения не разводит — сц. 11 (стенд двух манифестов, `testsub2`)
- [ ] **P/04-09** [test, reading] `distinct`: один хранитель на место, наибольшая нагрузка, при равенстве слотовый порядок P/03.2 N1.4 для всех допустимых имён; политика строкой, чтение мягкое, запись строгая — сц. 03 приёмки P/06.6; слотовый порядок имён — векторы [`slot-name`](../../../common/ru/vectors/slot-name/README.md) (`op: order`); единицы только у хранителя непустого места — сц. 11, одна полка: один хранитель, пробный процесс без места единиц не несёт — сц. 17 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R009, P/04-R033); наибольшая нагрузка и порядок при равенстве между хранителями — чтением по [README приёмки](../acceptance/README.md) (judge-only: проверки P/04-R009, P/04-R033) («Checks by reading»)
- [ ] **P/04-10** [test, reading] судьба слота N3: исходы, порядок правил, присутствие только из live пульса ресурса, сроки SLOT_TERM/LOST_AFTER/HUNG_MOVE_AFTER, контроллер не пишет слот кроме `release`; нечитаемое gen не сбрасывает и не разрешает его захват — исходы и точные границы сроков: швы `s1-fate-before-term`, `s3-fate-gone-with-units`, `s4-fate-margin`, `s5-fate-two-silences`, `s6-fate-gone-before-fresh-beat`, `s7-fate-hung-young`, `s8-fate-hung-boundary`, `s9-fate-wait-no-units`, `s10-fate-wait-boundary`, `s11-fate-runs-no-units`, `s12-fate-presence-unknown`, `s13-fate-unreachable-boundary`, `s34-fate-resource-never-seen-assigned`; запись release слота без единиц с прежними полями — `s2-fate-release-term`, `s35-fate-resource-never-seen-empty`; проигранный CAS release — `s15-release-cas-race`; нечитаемое gen — ни записи, ни разрешения — `s14-fate-no-permission-bad-gen`, `s16-release-unreadable-gen` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R039–P/04-R046) (`CALL controller-fate`); суждение о строке слота — векторы [`slot`](../../../common/ru/vectors/slot/README.md), состояние ресурса — векторы [`resource-state`](../../../common/ru/vectors/resource-state/README.md); на полном стенде: release слота без единиц (не move), запись release читаемого слота, порванного `until` и нечитаемого gen — сц. 21 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R039–P/04-R046); запас SLOT_TERM + LOST_AFTER и `hung` при присутствии `runs` (имя не отдано, слот не отдан, единица не уходит; без единиц — не release) — сц. 26, 27; `wait` при `unlisted` (имя не отдано, слот не отдан) — сц. 42; сроки при настоящем отказе сервера — P/04-22
- [ ] **P/04-11** [test] `names_given` привязан к версии строки слота; только NAME_FATES и `wait` за пределом; строка с нечитаемым gen не входит до восстановления поколения — версия разрешения `permission_version` швов `s2-fate-release-term`, `s3-fate-gone-with-units`, `s8-fate-hung-boundary`, `s35-fate-resource-never-seen-empty`; `wait` отдаёт имя только за пределом — `s9-fate-wait-no-units`, `s10-fate-wait-boundary`; нечитаемое gen и проигранный CAS release — разрешения нет — `s14-fate-no-permission-bad-gen`, `s16-release-unreadable-gen`, `s15-release-cas-race` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R040, P/04-R041, P/04-R042, P/04-R046) (`CALL controller-fate`); на полном стенде: имя отданного слота в `names_given`, нечитаемое gen вне его — сц. 21; `wait` до предела имени не отдаёт — сц. 42
- [ ] **P/04-12** [test, reading] переезд/первичное добавление/sync — один intent: снять всех members из всех назначений, довести placement, добавить на одну цель и лишь затем idle; каждое изменение с cas и guard turn, 412 прекращает попытку; снятие до добавления — шов `s18-intent-removals-before-add`, нет записи после неизвестного исхода и несостоявшегося барьера — шов `s19-intent-unknown-barrier` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R027, P/04-R036, P/04-R037) (`CALL controller-complete-intent`); доведение active intent (снятие, строка, добавление, idle) — сц. 28, `sync` — сц. 29 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R027, P/04-R036, P/04-R037); `Moved` при уже иной исходной цели (N3 «переехать», шаг 1) и прочее — проверяется чтением
- [ ] **P/04-13** [test, reading] уход: причины по порядку, без бюджета, группа целиком или остаётся — проверяется чтением; `silent` — только при `requires: resource` и живом воркере, иначе судьба SLOT_TERM + LOST_AFTER — P/04-30; отданный слот — единицы без места снимаются (`worker: ""`) — сц. 03 [приёмки P/03.4](../../../03-worker/ru/acceptance/4/README.md) (judge-only: проверки P/04-R047, P/04-R322); захват в работе (`taking`) уводит только после SLOT_TERM неизменной версии — сц. 13; дренаж — сц. 33, место не принимает (`admits: false`) — сц. 39; достижимость: сервер больше не достаёт меток единицы, единица снимается с причиной о достижимости — сц. 24 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R047, P/04-R322); бюджет REACH_BUDGET — проверяется чтением
- [ ] **P/04-14** [test, reading] заказ: per — положительная наблюдаемая ёмкость, иначе положительный capacity.default, иначе withheld без деления; нехватка по наборам меток и весу за вычетом ёмкости в пути; строка заказа всегда, `want` 1…WANT_NUM_MAX абсолютной целью, cas и guard turn; кандидаты (базовый жив, room, номера, distinct по place_by, дренаж, вывод); снятие по сроку `WANT_GRACE`, «failed to raise» `RAISE_QUIET`; сокращение — `SHRINK_AFTER`, гистерезис, кандидат только живой верхний n=want(s)>1 сервера; защищённый верхний пропускает весь сервер (номер выше want — не жертва), `retiring`, `SHRINK_BUDGET`, отмена; тревоги `workers.no_server`, `workers.raise_failed`; в пути — номера 2…want без живого процесса по пульсам, кандидат и доля — по двери (`live.<sub>` номерами, свободно один раз за проход), номер выше want вне пула (его остановка скриптом на хосте — P/04-31), снятие по сроку — номерами, `distinct` с местом из пульса — сервер без живого подходящего без места, без пробы в пути (в пути(s) = 0), не больше одного пробного за проход, и `no free <place_by>`, ёмкость — наименьшая положительная, формы `short[]` — векторы `order`, `shrink-victim`, `shrink-allowed` (условие сокращения и порядок причин отказа, в том числе живые без места при ждущих); срок `WANT_GRACE` начинается заново, когда номер снова пропал, — шов `s32-want-grace-restarts` (`CALL controller-want`); защищённый верхний пропускает свой сервер — `s36-shrink-wanted-top-prefix`, жертва на другом сервере — `s37-shrink-wanted-other-server`; конец роста при ручной строке не мешает сокращению — `s38-growth-ended-manual-row`; `short[]` у границы 2^53 — `s51-short-weight-max53`, `s52-short-weight-at53`, `s53-short-weight-odd53` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R050, P/04-R051, P/04-R052, P/04-R053) (`CALL controller-pass`); на полном стенде — сц. 14–17 после P/05 (`@grow`); прочее чтением
- [ ] **P/04-15** [test, reading] `delete_after` по часам контроллера от первого взгляда, свежая проверка эффективного размещения, `cas` единицы и guard своего turn, журнал: отсчёт от снятия — шов `s22-retire-counter-reset`; отказанное удаление единицы не удаляет состояния и не пишет журнал — `s23-delete-cas-then-state`; `409 early` без барьера и журнала — `s25-made-delete-early` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R030) (`CALL controller-delete-after`); бакет журнала и имена — векторы [`journal`](../../../common/ru/vectors/journal/README.md); свежая проверка эффективного размещения и guard своего turn — проверяется чтением
- [ ] **P/04-16** [test, reading] нынешний manifest_rev обязателен, отсутствующая ревизия не дописывается; страж и manifest_behind более новой строки — сц.31; очередь более новой ревизии не берётся — сц.32 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R405, P/04-R058); смена манифеста/код0 по-прежнему проверяются чтением
- [ ] **P/04-17** [test, reading] отчёт прохода N1.2 с обязательными полями; `fates` — только занятые неотданные слоты, `since` — вход в
  fate; `short[]` и `wants` при `grows`, ждущие без снятых и нечитаемых — ошибка одного шага: `ok: false`, `failures`, последующие шаги идут — шов `s33-pass-report-partial-failure`; счётчики того же цикла — `s57-snapshot-state-garbled-same-cycle`, `s58-snapshot-rows-garbled-same-cycle`, `s59-snapshot-tables-refused-same-cycle`; `state_swept_total` накопительный — `s60-sweep-total-cumulative`; одна запись отчёта после публикаций — `s61-publication-read-failure`, `s62-publication-store-too-large`, `s63-publication-reply-lost` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R007) (`CALL controller-pass`); поля `diverged` (сц. 29), `manifest_behind` (сц. 31),
  `unplaced` без снятых по `retire_when` (сц. 34), `state_swept_total` (сц. 35), `garbled` без назначений (сц. 41)
  [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R007); прочее проверяется чтением
- [ ] **P/04-18** [reading] причина решения ДОЛЖНА быть непустой и СЛЕДУЕТ грамматике N3 «выбрать» (`among` — число пригодных, `weight` —
  только с `placement.weight`) — проверяется чтением: предмет — поле `reason` строки размещения и ответа `/where/<id>` у размещённой единицы; сц. 02-unit приёмки P/03.3, шаг 6, читает строку `testsub/placement/c1` с `"reason": "@any"` — наличие поля, а не его непустоту или грамматику; `/where/<id>` там не читается; на стенде приёмки P/06.6 (сц. 01–07) воркеров нет
- [ ] **P/04-19** [test, reading] общий допуск N1.5/N3: turn с cas/guard, новый взгляд после захвата и между решениями; резерв всей группы intent, восстановление до нового допуска; барьер после неизвестного исхода, idle сохраняется для читателей; конкуренция не обходит ёмкость/spread_by/группу — два контроллера не обходят ёмкость — шов `s17-admission-capacity` (`CALL controller-admit`); снятие до добавления и восстановление новым держателем — `s18-intent-removals-before-add`, барьер после неизвестного исхода — `s19-intent-unknown-barrier` (`CALL controller-complete-intent`); предел конфликтов записи — `s54-conflict-nine-then-success`, `s55-conflict-ten-stops` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R209, P/04-R027, P/04-R028, P/04-R029) (`CALL controller-pass`); последовательности над строкой очереди — векторы [`turn`](../../../common/ru/vectors/turn/README.md) (judge-only: проверки P/04-R209, P/04-R027, P/04-R028, P/04-R029); на полном стенде: восстановление active intent и idle без удаления строки — сц. 28, нечитаемый intent — отказ без допуска — сц. 30; прочее проверяется чтением и моделями N5
- [ ] **P/04-20** [test] до записи intent полный ключ `<sub>/placement/<id>` каждого из members представим в пределе ключа хранилища; иначе решения нет, members — в `unplaceable` с `why`, размещение остальных единиц подсистемы не останавливается — шов `s20-long-key-group-no-intent` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R028, P/04-R031) (`CALL controller-key-admission`: ни записи intent, ни записи размещения для группы, группа не делится, оба члена в `unplaceable`, независимая единица размещена); на стенде приёмки P/06.6 (сц. 01–07) воркеров нет
- [ ] **P/04-21** [test, reading] снимок: шарды по воркеру, содержимое N1.3a, пустые шарды, `unplaced`, маска, после прохода — сц. 03 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R011, P/04-R498, P/04-R064); шард воркера, пустой `unplaced` и пустой шард ушедшего воркера — сц. 40; нечитаемая строка единицы вне шарда, шард опубликован — сц. 08 (шаги 1–6); ошибка чтения сохраняет опубликованное — шов `s26-snapshot-error-keeps-data`, предел байтов и предел хранилища — `s27-snapshot-byte-boundary`, `s28-snapshot-over-boundary`, `s29-snapshot-store-ceiling` (`CALL controller-snapshot`); счётчики того же цикла — `s57-snapshot-state-garbled-same-cycle`, `s58-snapshot-rows-garbled-same-cycle`; публикации до отчёта: сбой чтения, `TooLarge`, потерянный ответ — `s61-publication-read-failure`, `s62-publication-store-too-large`, `s63-publication-reply-lost` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R011, P/04-R498, P/04-R064) (`CALL controller-pass`); возраст и испорченный шард в `/metrics` консоли — [глава 6.5](../../../06-console/ru/spec/06.5-console.norms.md); прочее чтением
- [ ] **P/04-23** [test, reading] проверка схемы при старте контроллера (строка схемы и подъём — [P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N1.1a): N3 «старт контроллера — проверка схемы» — нет строки — своя SCHEMA, не число или выше SCHEMA — не стартовать, код 2 до чтения манифеста, ошибка чтения — ждать — исходы проверки — векторы [`schema`](../../../common/ru/vectors/schema/README.md); не число и выше SCHEMA, код 2 — сц. 23 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R060); ошибка чтения — ждать — сц. 25; «before reading the manifest» — проверяется чтением
- [ ] **P/04-24** [test, reading] срок `ends`, `retire_when.state` и `retire_when.delete_after`, удаление строки первой без надгробия и состояния после, уборка осиротевшего (шаг 8a), ручные строки — `expired_kept`: `ends`, уборка, `expired_kept` — сц. 18; `retire_when` по действующему состоянию (снятие с причиной-значением, вне `unplaced`) — сц. 34; отсчёт снимается, когда снятие отменено, — шов `s22-retire-counter-reset` (`CALL controller-delete-after`); уборка под guard строки единицы, отказанная уборка ждёт следующего прохода — `s24-sweep-unit-guard` (`CALL controller-state-sweep`); ручная строка после `ends` — `expired_kept` — `s38-growth-ended-manual-row` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R009, P/04-R025, P/04-R030) (`CALL controller-pass`); действующее состояние — векторы [`row-check`](../../../common/ru/vectors/row-check/README.md) (judge-only: проверки P/04-R009, P/04-R025, P/04-R030); уборка состояния с чужим `born` и `state_swept_total` — сц. 35; отсчёт `delete_after` от снятия на полном стенде (600 с у `testsub2`, после перезапуска заново), отменённое удаление и уборка, отменённая строкой после чтения, — проверяется чтением: стенд не выдерживает срок и не вклинивается между чтением и удалением
- [ ] **P/04-25** [test, reading] защита повтора при удалении: строка с `made` — строго позже `made.keep`, с `not_before`; `409 early` — без барьера и журнала — шов `s25-made-delete-early` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R030) (`CALL controller-delete-after`); удаление в сц. 18 (`keep` в 2001); `keep` в будущем — строка не удалена, сц. 18 шаги 15–19; граница равенства — чтением (стенд не двигает часы)
- [ ] **P/04-26** [test, reading] снимок таблиц N1.3b: заглушка `too_large` с пустыми строками — шов `s30-table-too-large-stub`, неизменная таблица не переписывается, `ts` сохраняется — `s31-table-unchanged-no-rewrite` (`CALL controller-table-snapshot`); `snapshot_tables_refused` того же цикла — `s59-snapshot-tables-refused-same-cycle` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R013, P/04-R062) (`CALL controller-pass`); прочее N1.3b — чтением; снимок со `state` (N1.3a) — сц. 19; `snapshot_state_garbled` — сц. 18
- [ ] **P/04-27** [test, reading] `near`: `by`/`of`, `prefer` (И, ИЛИ, путь), порядок по id соседа (N1.3) — векторы [`near-of`](../vectors/near-of/README.md); предпочтение воркера держателя — чтением; манифеста `near.sub` нет в каталоге — сродства нет, `near_waiting` в отчёте прохода, включение с прохода, на котором он появился, — чтением: стенд ставит каталог `testsub` + `testsub2` до старта, директивы установки манифеста посреди сценария в словаре «Стенда» нет
- [ ] **P/04-28** [reading] исключительное место (N1.3 `affinity.exclusive`): держатель принимает только связанные единицы, его ёмкость вне счёта нехватки прочих; заказ под место — сервер места, пустой `server_field` — без заказа, `Sealed` по `place_error` живых воркеров — `withheld`, живых нет — один обычный заказ — стенд не готовит исключительного места и строки места с неоткрывающимся секретом — чтением; сценарии P/04 и P/03.2 — когда учебная подсистема получит такое место (долг)

- [ ] **P/04-29** [test, reading] вывод сервера контроллером (N3 «вывести_сервер(s)»): возобновляемый план, закреплённый при принятии, порции release в пределах хранилища, уборка вкладов под точным guard индекса release, окончательная отметка `<sub>/decommissioned/<host>` последним атомарным шагом; неправильный план хода — ошибка шага без изменений; действительная окончательная отметка при стоящем запросе — новой уборки нет — порции и пределы — швы `s39-decommission-62-slots`, `s40-decommission-63-slots`, `s41-decommission-65-contributions`; возобновление из хранилища и сохранённый новый держатель — `s42-decommission-restart-before-cleanup`, `s43-decommission-new-holder`; отказанная или потерянная окончательная порция — `s44-decommission-final-refusal`, `s45-decommission-final-reply-lost`; неправильный ход — `s48-decommission-bad-progress-duplicate-remaining-name`, `s49-decommission-bad-progress-cursor-past-chunk`, `s50-decommission-bad-progress-foreign-from-prefix`; действительная окончательная отметка — `s56-valid-final-no-cleanup` [урока](../../acceptance/seams.tsv) (judge-only: проверки P/04-R054, P/04-R056) (`CALL controller-pass`); имя семьи `decommission-pending` занято: штатный загрузчик P/02.1, которым пользуется контроллер, отказывает манифесту, объявляющему его, — `s46-loader-reserved-pending-rows`, `s47-loader-reserved-pending-table` (`CALL controller-pass`, `fixture=loader_reserved_name`; отказ — отказ загрузчика P/02.1); сторона консоли — [P/06.6](../../../06-console/ru/spec/06.6-console.norms.md) N3 «вывести_сервер(s) — сторона консоли»

## Перечень урока системы

Пункты урока, которым нужны ОС, хост или несколько уроков: они не стоят ни на одном этапе
этого урока (`forms/stages.tsv`) и уходят в урок системы. Id — прежние id чеклиста готовности; часть, отделённая от пункта
чеклиста, получает новый id, и пункт с частью называют друг друга.

- [ ] **P/04-22** [stand] отказ сервера N1.4a (`stays`, `lost`): переезд по допускам двух молчаний без общего deadline, архив остаётся, неперезеркалированные бакеты потеряны, ничего назад, кроме `home` (N3 «проход()», шаг 7); сроки SLOT_TERM/(SLOT_TERM + LOST_AFTER) N1.4a при настоящем отказе (P/04-10) — учение `05-power-pull` [системной приёмки](../../../common/ru/acceptance/system/README.md); сц. 01 — `09-resource-door` приёмки [P/05](../../../05-resource/ru/acceptance/README.md) (judge-only: проверки P/04-R016, P/04-R065, P/04-R066), сц. 02 — `14-resource-silent` приёмки [главы 6.5](../../../06-console/ru/acceptance/5/README.md)
- [ ] **P/04-30** [stand] уход `silent` (N3 «уходит»; P/04-13): только при `requires: resource` и живом воркере, у чьего сервера ресурс молчит, иначе судьба SLOT_TERM + LOST_AFTER — пульс воркера читается через ресурс его сервера, и стенд урока живого воркера при молчащем ресурсе не держит; срок судьбы — учение `05-power-pull` [системной приёмки](../../../common/ru/acceptance/system/README.md)
- [ ] **P/04-31** [stand] воркеры заказа на хосте (P/04-14): systemd не поднимает экземпляр юнита по заказу (код 2 процесса); номер выше want, поднявшийся после снятия по сроку, останавливает скрипт на хосте, want не поднимается — стенд урока поднимает процесс по `@grow` сразу или не поднимает вовсе (сц. 15 [приёмки урока](../acceptance/README.md) (judge-only: проверки P/04-R050, P/04-R052), долг стенда); юниты P/02.4 и скрипт воркеров на хосте
- [ ] **P/04-32** [stand] жизненный цикл процесса контроллера ([lifecycle.md](../lifecycle.md) «Сигналы и готовность»): `READY=1` после проверки схемы и чтения манифеста, `WATCHDOG=1` на границах завершённых решений и хода прохода, не от независимого таймера; SIGTERM — штатный выход, незавершённый intent доводит следующий держатель очереди; `Restart=always`, кроме кода 2, по юниту P/02.4 — systemd и юниты P/02.4 на хосте; перезапуск после `@sigterm` на стенде урока — P/04-02; срока остановки нормы не задают

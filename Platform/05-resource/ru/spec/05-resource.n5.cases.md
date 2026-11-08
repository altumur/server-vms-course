# Покрытие случаев N5 только для судьи

Этот русский текст — производный от `spec/05-resource.n5.cases.md`, руками не правится (ADR-0121).

Описания случаев и их исходы — данные только для судьи. Каноническая нормативная глава — [`05-resource.norms.md`](05-resource.norms.md). Общие правила и явно сохранённые нормативные примеры остаются там.

### Блок случаев 1

| № | Сценарий | Нормы |
|---|---|---|
| 01 | `01-objects-door` (М10/08): дверь объектов: листинг пустой семьи, 400 на scope, 403 на семью вне двери, 404 на отсутствующий, 405 на PUT не-блоба; листинг — фильтр (`prefix=testsub/` — 200), `other/` — 403, пустой параметр и не-UTF-8 — 400, каталог из двух частей — 403, U+2028 в ключе — 400, `OPTIONS` и `PUT` листинга — 405 (сверка python и go М10/6–11) | N1.1, N2 |
| 02 | запрос событий: 400 на keep/by/class/голый unit; пустой ответ `{events: [], state: "live"}`; грамматика `from`/`limit`/`unit`, пустой и повторённый параметр, незнакомый параметр подсказки, не-ASCII цифры — 400, `1_0` — число; `POST /events` — 405 (сверка python и go М10/6–11); у консоли `from` по грамматике читателя времени: `+1`, `%2B1`, `%201`, `1e3` — 400, `%31` — 200 (C06-EVENTS-QUERY-LEXEME-162-01, решение «Архитектора» 2026-10-27) | N1.3, N1.6, N2, N4 |
| 08 | пути ресурса: `..`, `%2F`, чужое дерево в `/mirrored`, `/mirror`, `/events/{path}` — 404/400; `GET` на `/mirror/…` — 405; `/buckets` не из двух сегментов — 404 (сверка python и go М10/6–11, E26, E27, E29–E31, E36); строка `{bad` в бакете — `/events` ресурса и консоли 200 с `lines_garbled: 1` (E19); тревога в дереве `audit/console` (не `.alarms`) — `class: alarm` по полю (второй пилот, N-2) | N1.3, N1.6, N2, N4; договор журнала событий |
| 09 | `09-resource-door` (М10/11): ресурс: пульс и строка двери `platform/doors/srv-a` с `at`, который меняется; `/servers` видит ресурс `live`; `w2c_resources_live 1` | N1.4 `door_row`; P/02.4 N1.1, N3 «старт сервера»; P/04 |
| 10 | `10-body-copy` (М10/10): копия тела у ресурса: 204, копия читается; не тот дайджест — 422; без `X-Written` — 400; заглавные hex и подсистема без blob-поля — 405 | N1.1 «Bodies at the resource» `mirror`, N2 (сверка python и go М10/6–11, T10, T11) |
| 16 | `16-presence-lock` (М10/11): замок присутствия — ресурс и воркер `w-1`: `running: [testsub/w-1]`; `@sigkill` — `running: []`; новый старт того же имени — снова `running` (второй пилот, N-1) | N1.4 `presence`; [договор замка присутствия](../../../common/ru/contracts/presence-lock.md) |
| 17 | `17-schema-refusal`: `platform/schema` с `version` выше SCHEMA или не числом — `@start resource` выходит с кодом 2, строки двери нет; `version` 1 — стартует (аудит покрытия P/05, F01) | N3 «старт ресурса — проверка схемы»; [договор схемы](../../../common/ru/contracts/schema.md) «Проверка при старте» |
| 18 | `18-schema-read-wait`: хранилище молчит ресурсу (`@cut role resource store`) — ошибка чтения схемы: ресурс ждёт, не выходит; хранилище отвечает — строка двери без перезапуска (аудит покрытия P/05, F01) | N3 «старт ресурса — проверка схемы»; договор схемы «Проверка при старте», «Граница» |
| 19 | `19-service-names`: замок каталога `~lock` записи пульса воркера — вне листинга двери объектов, ключ `~lock` — 404 (аудит покрытия P/05, F02) | N1.1 `disk`, N2; [договор журнала событий](../../../common/ru/contracts/event-journal.md) «Имена файлов в общих деревьях» |
| 20 | `20-door-room`: поле `door` в пульсе ресурса; `room.testsub2`, `live.testsub2` строки двери по живым замкам — номер n ≥ 2 в `live`, базовый n = 1 и имя без номера — только в `room` (аудит покрытия P/05, F03) | N1.4 `heartbeat`, `door_row`, `room`; [договор замка присутствия](../../../common/ru/contracts/presence-lock.md) «Счёт `room`» |
| 21 | `21-events-wait`: `/events/wait` — по сроку `{changed: false, seq}`; `since=0` при строке под `want` — сразу `changed` с `touched`; `seq` монотонен; курсор `since=seq` — без изменений (аудит покрытия P/05, F05) | N1.6, N2 |
| 22 | `22-torn-tail`: хвост бакета без LF — не в `events` и `truncated`, `partial: true`, не `lines_garbled` (аудит покрытия P/05, F06) | N1.3 «Unreadable bucket line», N3 «запрос» шаг 3; договор журнала событий `torn` |
| 23 | `23-object-ceiling`: копия тела ровно байтового потолка двери ресурса (OpenAPI Content-Length.maximum) — 204 и чтение 200 (аудит покрытия P/05, F07); +1 байт — 413 — чтением (C05-CEILING-PLUS-ONE-READING-01) | N1.1 «Resource ceilings», N2, N4 |
| 24 | края `free_ask` на первом проходе (C05-PASS-FIRST-AT-START-01; аудит покрытия P/05, F04): ресурс пишет свою строку просьбы `free-srv-a-events`, в пульсе `short` ≥ 1 | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 25 | под своим ключом строка с `unit` — не тронута (та же версия), событие `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 26 | под своим ключом строка с чужим `server` — не тронута, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 27 | под своим ключом строка с чужим `volume` — не тронута, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 28 | под своим ключом строка с томом вне профиля (`b-c`) — не тронута, `free_ask.key_taken` | N1.4 `free_ask`, `space`, `heartbeat`; N3 «resource pass» `relieve` |
| 29 | `29-row-objects`: строки-объекты `objects.rows` и `commands/*` — 403 и при записанной строке `objects/<ключ>`, на любом `scope`; их `prefix` — 403; `prefix=testsub2/` — 200 без них (аудит покрытия P/05, второй проход, G01) | N1.1 `row_object`, `door`; N2; N4 |
| 30 | `30-copy-written-max`: `written` копии тела — исходный, уже лежащий не уменьшается — большее из двух (G01) | N1.1 `written` (C05-COPY-WRITTEN-SOURCE-01), «Bodies at the resource»; N2 |
| 31 | `31-objects-cluster`: два ресурса — копия тела соседу первым проходом с исходным `written`; `scope=cluster`: равный `written` — больший сервер, свежая копия побеждает; молчащий сервер — `missing`, `X-Missing` у 404 (G03) | N1.1 `cluster`, «Bodies at the resource» `mirror`; N1.4 `pass`; N2 `scope`, `X-Missing` |
| 32 | `32-mirror-put-refusals`: `/mirrored` без копий — 404; `PUT /mirror` открытого бакета, без `X-Sum`, `X-Sum` не по форме — 400, сумма не та — 422, копии нет (G04) | N1.6; N2; N4 «зеркало» |
| 33 | `33-mirror-put-read`: копия закрытого бакета — 204, `/mirrored` — `{copies}`, повтор `written` не сдвигает, байты с `X-Sum`; пульс `mirrors` (G04) | N1.6 (R05-G04); N1.4 `heartbeat`; N2 |
| 34 | `34-events-alarms-unit`: строка дерева `testsub.alarms` — `subsystem` и `unit` без суффикса, `class: alarm`; `unit` с `.alarms` — 200 без совпадений (G05) | N1.2 (E32); N3 «запрос» шаг 4 (C05-QUERY-UNIT-ALARMS-01) |
| 35 | `35-events-cut-order`: `HEAD /events` — 405; дубль id — первая строка; порядок `cut` (класс, `keep`, равное время — id), `by=occurred`, `late`, граница `to`, `truncated` после дедупликации (G05) | N1.3 `query`, `cut`; N2; N3 «запрос» шаг 6; договор слияния журнала событий |
| 36 | `36-events-bucket-stream`: `/events/{path}` — 200 с `X-Sum`, 206 и 416 с `Content-Range`; `/buckets` неизвестной единицы — 404 (G05) | N2; N4 «бакеты», «бакет» |
| 37 | `37-retention-garbled`: неверный `days` в `retention` и в `alarms_retention` — `retention_garbled`, `retention_withheld: days_garbled` на первом проходе (G06) | N3 `retain`; N1.4 `heartbeat`; N4 (C05-RETENTION-PULSE-33, R05-RETENTION-MIXED-51-01) |
| 38 | `38-holds-garbled-row`: строка удержания без читаемого окна — `garbled_rows.notches` (G06) | N3 `retain`; N1.4 `heartbeat`; [договор удержаний](../../../common/ru/contracts/holds.md) |
| 39 | `39-settings-unread`: нечитаемые `platform/space` и `platform/mirror` — `settings_unread: [mirror, space]`, своя строка `free-*` не пишется (G06) | N1.4 `space`, `mirror`, `heartbeat`; N3 |
| 40 | `40-space-disabled`: `enabled: false` — своя строка `free-*` снята, `short` 0 (G07) | N1.4 `space` (E45), `heartbeat.short`; N3 `relieve` |
| 41 | `41-space-band`: раннее наблюдение своей строки в полосе; завершение отдельно подтверждает синхронный s63-free-ask-band-completed (G07) | N1.4 `free_ask` (E44); N3 `relieve` |
| 42 | `42-heartbeat-units`: `units` пульса ресурса — id единиц из `status` живого воркера по возрастанию байтов (G08) | N1.4 `heartbeat` (E39), `running` |
| 43 | `43-spoiled-object-door`: испорченный объект — дверь отдаёт как есть: листинг и `GET` 200 (G08) | N1.1 `door`; «Решает реализация» п. 8 (C05-SPOIL-OBJECT-BYTES-01) |
| 44 | `44-objects-door-family`: `objects.door` манифеста — `testsub2/tickets/t1` (`@put object` из `inputs/`) — `GET` 200 и в листинге; `testsub/tickets/t1` без `objects` у манифеста — 403 (G01) | N1.1 `door`; N2; N4 |
| 45 | `45-gone-door`: надгробие `.gone/<object-key>` (`@put object` из `inputs/`) — вне обычного листинга, `prefix=.gone/` и `GET` тела — чтение, `PUT` — 405; копия старше — 409, ключа нет; новее — 204 с исходным `written`, надгробие снято тем же действием (G02) | N1.1 `written` (C05-GONE-REWRITE-AT-WRITE-01), `door` (C05-GONE-BODY-READ-01); N4 «deleted later»; [договор надгробий](../../../common/ru/contracts/tombstone.md) `listing`, `rewrite` |

### Блок случаев 2


Дополнительные исходные швы s63–s67 в [acceptance/seams.tsv](../../acceptance/seams.tsv) используют существующие синхронные порты: завершённый relieve в полосе; действительный выбор кандидатов на 144/145 и календарный fallback; отдельные границы повторов соседей. Неизменённый процессный сценарий 41 наблюдает лишь перечисленное раннее состояние; pass_started с фиксированным сном не доказывает завершение relieve. Объявление шва не является исполнением реализации.

Конец покрытия случаев N5 только для судьи.

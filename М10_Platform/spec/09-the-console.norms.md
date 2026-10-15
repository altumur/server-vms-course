# М10/9 — Консоль: нормы

Канон урока. [Лекция](../09-the-console.md), [HTTP-контракт](09-the-console.api.openapi.yaml),
[инструкция](09-the-console.README.md), [приёмка](../../Source/tests/testdata/acceptance/М10_Platform/09/README.md).

## Н0 Словарь слов

Нормативные слова — по [общему канону Н0](01-storage.norms.md#н0-словарь-слов).

## Н1 Форма

### Н1.1 Три части

```yaml
console_process:                              # платформа; один на сервер; из каталога спек (строки platform/spec/*, урок 2)
  root:     CONSOLE_ROOT — подсистема, чья оболочка отдаётся на /; остальные — /mounts, без страницы
  shell:    <sub>.shell.html — в строке спеки (shell, урок 2 Н1.5) | файл рядом со спекой; нет — console.html платформы
  module:   /platform/console.js, /platform/console.css — один код у всех реализаций (байт в байт, ADR-0005, ADR-0019)
  version:  ?v=<n>; MODULE_VERSION = 1; иная — 404 no such version; console.version — целое, оболочка сверяет
  page:     CSP script-src 'self' 'sha256-…' (хэши встроенных скриптов); object-src 'none'; base-uri 'none';
            атрибутов on…= нет; экранирование h()
module:                                        # PlatformConsole.mount(root, opts) → console
  opts:     {sections: [units, access, journal] | [domain], subsystems: [<из /mounts>], lang: ru | en, poll_s: 5}
  never:    не называет подсистем (закрытый список запрещённых слов — тест границы, ADR-0001); не зовёт адресов вне своих;
            не трогает DOM оболочки; не держит сессии за оболочку; не показывает таблиц целиком
  calls:    закрытый список — Н1.4
shell:                                         # подсистема
  may:      вызовы библиотеки (Н1.5); свои двери к держателю по door из where(); свои слова
  may_not:  хуки; чужой DOM; свой вход; байты через консоль (ADR-0015)
```

### Н1.2 `display`, `servers`, `console`

Форма — урок 2 (закрытые ключи). Здесь — смысл каждого слова для модуля.

```yaml
display:
  unit, units, units_count:  слово единицы: одна, много, род. падеж множ. (для счётчиков); нет — «единица»
  section:                   подпись рейки раздела единиц
  general:                   заголовок первой вкладки; только раскладка
  fields:        {<поле>: <подпись>}            # поле строки, id, phase/worker/server/revision/observed_revision, поле status
  field_help:    {<поле>: <подсказка>}
  options:       {<имя>: {<значение>: <слово>}}                 # у поля с enum — значения из enum; у слова пульса из form.status[] — любые строки (подписи значений); иное — отказ (урок 2 Н1.4)
  form:          [{title, state?, placement?, fields?, note?, status?: [{field, since?, title?}]}]
                 # блоки карточки по порядку; state — бейдж состояния; placement — воркер·сервер, причина из /where;
                 # status — поля, сказанные воркером, только чтение, с «с …» по since; поле вне блоков не показывается;
                 # без form — один блок со всеми полями
  events:        false — у модуля нет вкладки журнала единицы
  kinds:         {<вид события>: <слово>}        # слова видов подсистемы; виды платформы — словарь модуля
  keys:          {<id семьи ключей домена>: {title, about, absent?}}   # М11
  tree:
    group_by:    <поле> — чем группировать дерево; nested_by: <разделитель> — значение group_by с разделителем даёт вложенные группы;
                 columns: [{field, title, width}]; children: false — не вкладывать about-единицы
    group_title, group_hint, filter, no_group, children, contents_title, group_word, no_group_suffix, pick_note,
    new_root, new_sub, add_here, new_group_note, remove, not_in, add_to, no_others, new_group:   слова
  # display.actions — снят: модуль и оболочки его не читают (мёртвый ключ, ADR-0003)
servers:
  show:    [{table, by, title, columns}]         # строки таблицы table, у которых row[by] == сервер; заголовки — display.fields;
                                                 # секреты — маской; пусто — «Нет строк»; оболочка может накрыть addBlock(covers)
  status:  [{field, title, of?}]                 # значение пульса воркера по пути field — в строку сервера как есть (строка
                                                 # из heartbeat.strings, число, карта, список; слово на месте числа — garbled,
                                                 # пропуск); of — таблица, по которой страница сопоставляет ключи (ADR-0064)
console:
  running: <метрика спеки> → running_gauge: <sub>_<name>; workers_gauge: <sub>_workers_live
```

### Н1.3 Сторожевая

```yaml
gate:
  on:       в хранилище есть domain/keys → каждая дверь, кроме открытых, спрашивает личность и грант
  open:     ключей нет и следов домена нет → консоль открыта: только с петли (иначе 403), имя — operator
  shut:     ключи были или след домена есть, а проверить нечем / хранилище не ответило → 503, не открыта
  identity: # по порядку
    1. кука аварийного входа w2c_glass (сессия в памяти, 15 мин)
    2. X-Agent-Signature — агент домена: только двери единиц (урок М11)
    3. Authorization: Bearer <токен> | кука w2c_token → домен: {user, until, grants}
    4. отладочная личность ADR-0050 — только с петли
    5. иначе 401
  x_user:   заголовок X-User стирается всегда; вписывается доказанное имя
  caps:     view < edit < admin
  need:     # что требует дверь; решается по пути ДО чтения тела
    GET/HEAD                         → view (на единицу из пути или ?unit=; без единицы — любой грант)
    /marks, POST /requests           → edit на единицу тела
    DELETE /asked/*                  → admin на *
    метки сервера, вывод, policy, drain, schema PUT → admin на *
    строки единиц: POST → admin на * | по rights.routes view/edit на единицу about | cluster_rows → *
                   PUT/DELETE        → admin на единицу | по rights.routes
    таблицы                          → по rights.routes (view | edit | admin)
    по телу — rights.unit_of, reach, names добавляют единицы (урок 6)
  scope:    грант на * | unit:<sub>/<id> | labels:<…>; грант на единицу или на её about-единицу
  csrf:     действующий запрос по куке с чужим Origin → 403
  body:     предел тела (≥ 1 MiB; blob — урок 10); chunked → 400; медленно → 408; больше → 413
  refusal:  {detail, error: denied}; 403 → журнал access.denied
open_routes: [/, /index.html, /platform/console.js, /platform/console.css, /metrics, /healthz, /session, /session/break-glass,
              /api/held, /api/backup, /api/prepare, /api/take]
session:
  GET  /session  → {open, login_url, user?, until?, via?, debug?, grants?: [{cap, scope}]}   # grants — чтобы may() решал локально
  POST /session {token} → {user, until} + кука w2c_token (HttpOnly, SameSite=Strict, Secure за https)
  DELETE /session → {out: true}; POST /session/break-glass {who, why, password} → кука w2c_glass; 429 по пределу
  login_url: дверь домена /api/login (М11); консоль токенов людей не выдаёт
```

### Н1.4 Что зовёт модуль — закрытый список

```yaml
reads:   /session, /spec, /<sub>/spec, /mounts, /<rows>, /<sub>/<rows>, /<sub>/<table> (только из servers.show),
         /where/<id>, /servers, /unplaceable, /<sub>/unplaceable, /policy, /drain, /schema, /events, /metrics
         (только running_gauge и workers_gauge), /domain/*, /api/held, /domain/shared/<sub>
writes:  POST/PUT/DELETE /<rows>[/<id>], POST /marks, PUT /policy, POST/DELETE /drain, GET/PUT/DELETE /servers/<s>/labels,
         POST/DELETE /servers/<s>/decommission, /domain/* (М11), POST/DELETE /session, /session/break-glass, login_url
never:   /requests, /api/backup, /resources, /<sub>/<table> вне show, двери держателей (door из where — только оболочке)
order:   /session → /spec → /mounts → по подсистеме /<rows> → /servers → /unplaceable → /domain/shared/<sub> → /drain → /schema
         → /domain (+ /domain/alarms) → /api/held → /metrics; опрос каждые poll_s; /events?unit= выбранной — каждые 5 с
```

### Н1.5 Контракт модуля с оболочкой

```yaml
objects:   ref: unit:<sub>/<id> | server:<s> | worker:<sub>/<w> | member:<m> | domain | person:<name> | group:<sub>/<поле>/<путь>
           | <prefix>:<…> оболочки (модуль только хранит)
api:       console.api(method, path, body) → ответ | throw {status, body, retry}
           POST/PUT — один Idempotency-Key на (method, path, body); повтор тем же ключом при сетевой ошибке, таймауте 20 с,
           5xx, 409 in flight (2, 3, 5 с или retry_after); 2xx/4xx закрывают ключ; 401 → окно входа
may:       console.may(cap, ref) → bool по grants сессии (* | unit:); нет grants — true; сервер проверяет всегда
events:    on("select", (ref, obj)) | on("refresh", {units, servers, domain}) | on("logout")
where:     where(ref) → {worker, server, door: {url, token, expires, routes} | null, reason}
words:     display(name), spec(name), kindWord(e), eventNote(e), addEventNote; W — словарь модуля ru | en
adds:      addSection{id, label, icon, after, off, render}, addTab(kind, {id, label, render, busy}) kind ∈ unit | server |
           worker | member | domain, addTreeNodes(kind | servers | server, fn) → узлы {ref, label, icon, count, kids, badge,
           tags, dot, title, off, open, after, replaces}, addCard(prefix, render), addMenu, addDecor{icon, badge, title},
           addFieldEditor(kind, field, render(host, ref, obj, value, set)), addBlock("server", {id, covers, render}),
           addAction, addNote, addIcons, icon, unitForm(host, ref), dialog(title, fields, ok), confirm, toast, select,
           selected, refresh, logout, fullScreen, isFav, toggleFav
cards:     разметка карточки: <h1>, nav.pc-tabs, <h2> → .card, button.pc-hdbtn, span.pc-crumbs[data-crumbs], p.pc-hdsub
commands:  вид command / command.failed — слово и заметка модуля (action · исход · ответ · «кто: by»; late → «поздно»)
```

---

## Н2 Двери

Двери консоли платформы — закрытый список; у подсистемы своих дверей на консоли нет, кроме таблиц и просьб из спеки и `door.pass` (урок 11). Коды дверей единиц — урок 3, контроллера — урок 4, событий и просьб — урок 8.

HTTP-контракт: [09-the-console.api.openapi.yaml](09-the-console.api.openapi.yaml).

Общие коды: неизвестный путь — `404 NoRoute`; неверный метод — `405 {detail: method, error: method}`; `/<rows>/<id>/<ещё>` — 404 «a unit's path names one unit»; полоса занята — `503 busy`, `Retry-After: 1`; `/session`, `/healthz` — резервная полоса; `/metrics`, `/healthz` — полоса монитора.

---

## Н3 Проход

### запрос → ответ (консоль)

```
1. полоса: резервная / монитора / общая; занята → 503 busy
2. тело не больше предела (по заголовку); chunked → 400
3. /session* → сессия (Н1.3), до всего
4. X-User стереть; домена нет → не петля и не открытый путь → 403
5. путь → дверь и что она требует (Н1.3 need); пути нет → 404
6. кто звонит (Н1.3 identity) → 401; грант по пути → 403 + журнал
7. прочитать тело; по телу — unit_of / reach / names → ещё гранты → 403
8. дверь: единицы (урок 3), контроллер (урок 4), события и просьбы (урок 8), /spec, /mounts, /servers, /where, /metrics
   X-User = доказанное имя для журнала
```

**Гонки.** Два запроса одной сессии разом — независимы; запись и чтение одной строки — `cas` (урок 3); смена спеки — консоль останавливается с кодом 0 и перезапускается (урок 2), `SpecView` ревизии не несёт; модуль видит обрыв и перезагружает страницу.

### /servers — картина для человека

```
воркеры: пульсы семьи (любого возраста) → state live, если менялся < 45 с по часам консоли, иначе stale;
         слот → released, slot_until (null — нечитаем), slot_garbled; удержания → holds;
         судьба контроллера (отчёт прохода) → hung, hung_since, hung_why, presence_unknown; соперники → name_conflict;
         servers.status → status {поле: значение как есть}
серверы: ресурс (пульс + дверь) → resource live | silent | unreachable | unknown, resource_heard_at, space;
         platform/servers/<s> → labels, labels_source console | node | unknown; дренаж; вывод и его отказ; достижимость
         (placeable, why — по меткам и requires); lost — единицы ушедшего
неизвестный сервер — "?"; реестра машин нет
```

**Гонки.** Нет: чтение снимка пульсов и строк; пульс, пришедший во время сборки, — в следующем ответе.

### /where/<id>

```
строка размещения: worker "" или нет → 404 {reason: причина из строки | «not placed»}
пульс воркера → server, url двери (door.routes спеки) → door: {url, token (door1.<kid>…, Ed25519 ключом door/signer,
TTL 120 с, в токене user, unit, holder, routes только чтения), expires, routes}; token выдаётся по view на единицу,
каждая выдача — журнал door.issued; directory — где единицу видят (5 с кэш), scans
```

**Гонки.** Переезд единицы во время ответа: строка размещения читается раз, ответ называет воркера на этот момент, `door` — из его пульса на тот же момент.

### /metrics — текст

```
на подсистему (<sub>_…): workers_live; worker_headroom{worker,server}; headroom; worker_load{worker}; spare_workers;
  epoch_conflicts{worker}; failover_seconds{kind=worst|last,worker}; failovers_unmeasured; heartbeats_garbled;
  heartbeat_skew_seconds_max|min; workers_hung; workers_unjudged; units_unjudged; reconcile_last_pass_age_seconds;
  reconcile_last_success_age_seconds; reconcile_pass_seconds; reconcile_failures; units_unplaced; units_diverged;
  reach_moves_total; reach_unplaced_total; unplaced_deleted_total; servers_decommissioned_total; slots_released_total;
  decommission_requests_standing; name_conflicts; groups_waiting; servers_labels_unread; workers_needed{labels};
  units_short{labels}; spare_offers{labels}; spares_withheld{labels}; server_labels{server,labels,source};
  worker_fenced{worker}; worker_store_errors{worker}; worker_pass_failures{worker}; snapshot_age_seconds;
  snapshot_ahead_shards; audit_failures; garbled_rows; idempotency_store_failures; requests_ledger_garbled;
  <running> (console.running); ряды metrics: спеки (<sub>_<name>, gauge | counter | histogram)
metrics[]:  закрытый перечень ключей элемента (загрузчик урока 2 отказывает иным): name, type, from, agg, equals, when, default,
            live, labels, count, where, unheld, unless {table, where}, buckets, label, values; смысл и грамматика значений — М13
платформы, один раз (root): w2c_resources_live; w2c_resource_heartbeats_garbled; w2c_resource_full{server};
  w2c_resource_short_bytes{server}; w2c_resource_waits*; w2c_resource_rows_garbled; w2c_resource_restore_*; w2c_resource_mirror_*;
  w2c_requests_expired_total{sub}; w2c_requests_unknown_total{sub}
значения — по ADR-0055; подписи экранированы
```

**Гонки.** Нет: консоль читает и показывает; её записи — двери уроков 3, 4, 8 со своими `cas` и ключами.

---

## Н4 Отказы

| Причина | Код | Тело | Что делает вызывающий |
|---|---|---|---|
| нет такого пути | 404 | `{detail: no such route, error: no such path}` | ошибка клиента |
| метод не тот | 405 | `{detail: method, error: method}` | ошибка клиента |
| версия модуля не та | 404 | `{error: no such version}` | обновить страницу вместе с модулем |
| страница у смонтированной подсистемы | 404 | «is mounted» | идти на root |
| не личность | 401 | `{detail: "this console asks who is calling: …", error: denied}` | войти (login_url) |
| гранта нет | 403 | `{detail: "<кто> may not <cap> <единица \| here>", error: denied}`; журнал | — |
| нет домена, не петля | 403 | `{detail: "this cluster is in no domain … loopback", error: denied}` | подключить домен |
| ключи были, проверить нечем | 503 | `{detail: "…admits nobody", error: denied}` | восстановить доверие |
| чужой Origin на действующем запросе по куке | 403 | `denied` | — |
| `/session POST` у открытой консоли | 400 | слова | — |
| аварийный вход: предел | 429 | `Retry-After` | ждать |
| тело: chunked / больше / медленно / коротко | 400 / 413 / 408 / 400 | слова | ошибка клиента |
| полоса занята | 503 | `busy`, `Retry-After: 1` | повторить |
| `/where`: не размещена / не id | 404 / 400 | `{reason}` / слова | — |
| `/domain/<rest>` к держателю: держатель не ответил / нет домена или ключей | 502 / 503 | слова | — |
| `/where/<t>/<p>`: место не держат | 404 | `{unreachable: place@server}`, `X-Unreachable` | — |
| `/events` без индекса ресурса | 503 | слова | — |
| `/spec`: `display` называет не поле; `options` не у enum и не у слова пульса; `console.running` не метрика; `servers.status` платформенное поле | спека не грузится | слова (урок 2) | править спеку |

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М10_Platform/09/` ([README](../../Source/tests/testdata/acceptance/М10_Platform/09/README.md)): двери консоли `testsub` без воркеров и без домена (консоль открыта, с петли).

| № | Сценарий | Нормы |
|---|---|---|
| 01 | страница и модуль: `/` 200 html с `PlatformConsole.mount` и CSP; `/platform/console.js?v=1` 200, `?v=2` 404; `/healthz` | Н1.1, Н2 |
| 02 | `/spec` — форма SpecView с `running_gauge`, `workers_gauge`, `display` как написано; `/mounts` — `{root: testsub}` | Н2, урок 2 |
| 03 | сессия открытой консоли: `GET /session` → `{open: true}`; `POST /session` → 400 | Н1.3 |
| 04 | `/servers` → `{policy: {servers: shared}, servers: {}}`; `/unplaceable` пуст; `/where/<id>` у неразмещённой — 404 с `reason` | Н2, Н3 |
| 05 | `/metrics` — текст с `testsub_workers_live 0`, `testsub_units_unplaced`, `testsub_counters_running`, `w2c_resources_live` | Н3 |
| 06 | отказы: неизвестный путь 404 `no such path`; метод 405; `/counters/c1/x` 404; смонтированная `/testsub2/` 404 | Н4 |

Проверяются чтением и структурно: модуль — jsdom-тесты контракта (закрытый список вызовов, словарь, `may`, `api` с ключом, дерево, форма, серверы, домен) — один набор у обеих сторон на одном `console.js`; сторожевая с доменом (401/403/503, порядок, CSP) — стенд М11; `/where` с дверью — стенд М12A; `servers.status`/`show` — стенд рекордера; правило адреса без домена — стенд урока 11.

---

## Решает реализация

Реализация обязана назвать в своём описании:

1. **откуда берётся оболочка** (строка спеки `shell` — урок 2; файл рядом со спекой) и `CONSOLE_ROOT`;
2. **пределы**: тело (≥ 1 MiB), блоб, сессия (16 KiB), полосы и их размеры, таймауты;
3. **кэши** `/where` (directory 5 с), эпох (3 с), `/domain` пересылки;
4. **отладочная личность** ADR-0050 и аварийный вход — предел попыток;
5. **дополнительные ряды `/metrics`** сверх Н3;
6. **пересылка `/domain/*`** держателю: заголовки, один переход;
7. **CSP** сверх минимума Н1.1.

---

## Чеклист готовности

- [ ] **М10/9-01** три части и хозяева; страница — три строки; модуль один код у всех (структурный тест байт в байт); версия без совместимости назад — сц. 01
- [ ] **М10/9-02** оболочка только у root; смонтированные без страницы; `/mounts` — сц. 01, 02, 06
- [ ] **М10/9-03** `display`, `servers.show/status`, `console.running` — слова по Н1.2; `display.actions` снят; `/spec` отдаёт `display` как написано — сц. 02; урок 2
- [ ] **М10/9-04** сторожевая Н1.3: порядок, `need` по пути до тела, `X-User` никогда, открыта только с петли, закрыта при потере доверия, `{detail, error: denied}`, журнал — сц. 03; стенд М11
- [ ] **М10/9-05** `/session` с `grants` — чтением (стенд М11); модуль `may` по ним
- [ ] **М10/9-06** закрытый список вызовов модуля Н1.4 и порядок загрузки — проверяется чтением: тест контракта модуля (`Source/tests/console/`, jsdom; предмет — вызовы и их порядок); причина — модуль один у всех реализаций, двери порядок загрузки не показывают
- [ ] **М10/9-07** контракт оболочки Н1.5: `api` с одним ключом и повторами, `where` с `door`, вызовы библиотеки, без хуков и чужого DOM — проверяется чтением: тест оболочки (jsdom; предмет — поведение страницы, не двери)
- [ ] **М10/9-08** `/servers` и `WorkerRow` по Н2/Н3 — сц. 04; стенд урока 5
- [ ] **М10/9-09** `/where`: 404 с `reason`, `door` только по view, токен Ed25519 120 с, журнал `door.issued` — сц. 04; стенд М12A
- [ ] **М10/9-10** `/metrics` по Н3: ряды подсистемы, платформенные `w2c_*` один раз, ADR-0055 — сц. 05
- [ ] **М10/9-11** общие коды Н4, полосы, пределы тела — сц. 06; чтением
- [ ] **М10/9-12** байты мимо консоли: ни одного маршрута потока/архива в консоли платформы (ADR-0015) — проверяется чтением: тест границы реализации (список маршрутов консоли против слов потока и архива); причина — отсутствие маршрута запросом не показать

## Соответствие прежним урокам

Нормирует `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` (контракт модуля — разделы 1–10 как Н1.1, Н1.4, Н1.5; раздел 10a — М12A; расхождения контракта с кодом сняты в пользу урока: имя оболочки `<sub>.shell.html`, список вызовов модуля дополнен `/schema`, `/unplaceable`, `/policy`, `/servers/<s>/labels`), `М10A_Platform/15-SpecConsole.md` (шаги 1, 3, 6, 8 (коды), 9–14: описание, чтения, `/servers`, `/metrics`, объявленное, сторожевая, ключ, монтирование; шаг 4 — урок 3; 7 — урок 8), `М10A_Platform/16-HTML.md` (целиком: страница, модуль, слова, наложение, форма, `api`, вызовы оболочки, CSP). Прежние уроки получают пометку «нормативно: М10/9» и уходят, когда последний из забирающих их уроков ляжет в main; контракт модуля остаётся описанием публичной поверхности до переноса `W` и разметки в урок.

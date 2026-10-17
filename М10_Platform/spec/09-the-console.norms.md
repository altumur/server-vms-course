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
  shell:    поле shell строки спеки platform/spec/<sub> (урок 2 Н1.5); пусто или нет поля — console.html платформы;
            файла рядом со спекой консоль не ищет: она читает каталог из хранилища
  module:   /platform/console.js, /platform/console.css — один код у всех реализаций (байт в байт, ADR-0005, ADR-0019);
            файлы модуля — опубликованные данные спецификации Source/w2cplatform/console.js, console.css и
            console.html (страница платформы, shell выше; ADR-0080 доп. 16): реализация отдаёт их байт в байт и своего
            модуля не пишет; переписывание по контракту КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md — проверка полноты контракта,
            не способ реализации
  version:  ?v=<n>; MODULE_VERSION = 1; v нет, повторён или не 1 — 404 {error: "no such version"}; console.version —
            целое, оболочка сверяет
  page:     CSP — минимум script-src 'self' 'sha256-…' (хэши встроенных скриптов страницы, от её текста при отдаче);
            object-src 'none'; base-uri 'none'; директивы сверх минимума — решает реализация, называет их;
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
  form:          [{title?, state?, placement?, fields?, note?, status?: [{field, since?, title?}]}]   # title необязателен
                 # блоки карточки по порядку; state — бейдж состояния; placement — воркер·сервер, причина из /where;
                 # status — поля, сказанные воркером, только чтение, с «с …» по since; поле вне блоков не показывается;
                 # без form — один блок со всеми полями
  events:        bool; false — у модуля нет вкладки журнала единицы; true и отсутствие — есть
  kinds:         {<вид события>: <слово>}        # слова видов подсистемы; виды платформы — словарь модуля
  keys:          {<id семьи ключей домена>: {title, about, absent?}}   # М11
  tree:
    group_by:    <поле> — чем группировать дерево; nested_by: <разделитель> — значение group_by с разделителем даёт вложенные группы;
                 columns: [{field, title, width}] — field: поле единицы или платформенное имя модуля (worker, server,
                 revision, observed_revision, phase, id; урок 2 Н1.4); children: false — не вкладывать about-единицы
    group_title, group_hint, filter, no_group, contents_title, group_word, no_group_suffix, pick_note,
    new_root, new_sub, add_here, new_group_note, remove, not_in, add_to, no_others, new_group:   слова
  # display.actions — снят: модуль и оболочки его не читают (мёртвый ключ, ADR-0003)
servers:
  show:    [{table, by, title?, columns?}]       # строки таблицы table, у которых row[by] == сервер; заголовки — display.fields;
                                                 # секреты — маской; пусто — «Нет строк»; оболочка может накрыть addBlock(covers)
  status:  [{field, title?, of?}]                # field не называет ключ пульса, который читает платформа (перечень — М10/2 Н1.2а, урок 5 Н1.1); иначе refused:value при загрузке; значение пульса воркера по пути field — в строку сервера как есть (строка
                                                 # из heartbeat.strings, число, карта, список; слово на месте числа — garbled,
                                                 # пропуск); of — таблица, по которой страница сопоставляет ключи (ADR-0064)
console:
  running: <метрика спеки> → running_gauge: <sub>_<name>; workers_gauge: <sub>_workers_live
           # без console.running — running_gauge: null и metrics.running: null (урок 2 Н2)
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
    4. отладочная личность (ADR-0050): задан W2C_DEBUG_PERSON=<имя>, запрос без токена и без куки, адрес TCP-соединения
       127.0.0.1 или ::1 (заголовки адреса не читаются) → этот человек со своими grants из domain/grants; человека нет
       или он выключен — как без входа; с другого адреса — как без переменной; доверенный прокси на петле и заданная
       переменная → процесс не стартует; видно: /session отдаёт debug: true, при старте тревога session.debug_open,
       каждая правка — в журнал с debug: true
    5. иначе 401
  x_user:   заголовок X-User стирается всегда; вписывается доказанное имя
  caps:     view < edit < admin
  need:     # что требует дверь; решается по пути ДО чтения тела
    GET/HEAD                         → view (на единицу из пути или ?unit=; без единицы — любой грант)
    /marks, POST /{sub}/requests     → edit на единицу тела
    DELETE /{sub}/asked/*            → admin на *
    метки сервера, вывод, policy, drain, schema PUT → admin на *
    строки единиц: POST → admin на * | по rights.routes view/edit на единицу about | cluster_rows → *
                   PUT/DELETE        → admin на единицу | по rights.routes
    таблицы                          → по rights.routes (view | edit | admin)
    по телу — rights.unit_of, reach, names добавляют единицы (урок 6)
  scope:    грант на * | unit:<sub>/<id> | labels:<…>; грант на единицу или на её about-единицу
  csrf:     действующий запрос по куке с чужим Origin → 403
  body:     предел тела (≥ 1 MiB; blob PUT /<rows>/<id>/<blob_field> — 32 МиБ, урок 10 Н1.4); chunked → 400; медленно → 408; больше → 413
            (ответ раннего отказа — урок 1 Н2.1)
  refusal:  {detail, error: denied}; 403 → журнал access.denied
open_routes: [/, /index.html, /platform/console.js, /platform/console.css, /metrics, /healthz, /session, /session/break-glass,
              /api/held, /api/backup, /api/prepare, /api/take]
session:
  GET  /session  → открыта: {open: true, login_url}; закрыта анонимному: {open: false, login_url};
                   доказанной личности: {open: false, login_url, user, until, via, grants: [{cap, scope}], debug?}
  POST /session {token} → {user, until} + кука w2c_token (HttpOnly, SameSite=Strict, Secure за https)
  DELETE /session → {out: true}; POST /session/break-glass {who, why, password} → {user, until} + кука w2c_glass; 429 по пределу
  login_url: дверь домена /api/login (М11); консоль токенов людей не выдаёт
```

### Н1.4 Что зовёт модуль — закрытый список

```yaml
reads:   /session, /spec, /<sub>/spec, /mounts, /<rows>, /<sub>/<rows>, /<sub>/<table> (только из servers.show; добавлено М10/10),
         /where/<id>, /<sub>/where/<id>, /servers, /unplaceable, /<sub>/unplaceable, /policy, /drain, /schema (добавлено М10/10),
         /events, /metrics (только running_gauge и workers_gauge), /domain/*, /api/held, /domain/shared/<sub> (эти три — М11)
writes:  POST/PUT/DELETE /<rows>[/<id>] и /<sub>/<rows>[/<id>], POST /marks, PUT /policy, POST/DELETE /drain, GET/PUT/DELETE /servers/<s>/labels,
         POST/DELETE /servers/<s>/decommission, /domain/* (М11), POST/DELETE /session, /session/break-glass, login_url
never:   /{sub}/requests, /api/backup (М11), /resources, /{sub}/{table} вне show, двери держателей (door из where — только оболочке)
order:   /session → /spec → /mounts → по подсистеме /<rows> → /servers → /unplaceable → /domain/shared/<sub> (М11) → /drain → /schema
         → /domain (+ /domain/alarms; М11) → /api/held (М11) → /metrics; опрос каждые poll_s; /events?unit= выбранной — каждые 5 с
```

### Н1.5 Контракт модуля с оболочкой

```yaml
version:   console.version — целое версии API оболочки (Н1.1); проверяется до использования модуля
objects:   ref: unit:<sub>/<id> | server:<s> | worker:<sub>/<w> | member:<m> | domain | person:<name> | group:<sub>/<поле>/<путь>
           | <prefix>:<…> оболочки (модуль только хранит)
api:       console.api(method, path, body) → ответ | throw {status, body, retry}
           POST с памятью повторов владельца (единица/просьба) — один ключ на логическое действие, не на одинаковые байты;
           повторы этого действия сохраняют ключ и исходное тело. Новый вызов — новый ключ. Сеть/таймаут 20 с/5xx/
           409 in flight допускают повтор по правилам владельца (2, 3, 5 с или retry_after); 401 → окно входа.
           PUT и таблицы без памяти повторов автоматически не повторяются: при неизвестном исходе сначала чтение.
           Завершённый ответ закрывает действие; отказ до памяти заявки разбирается по контракту владельца, не кэшируется как успех
may:       console.may(cap, ref) → bool по grants сессии (* | unit:); true без grants только при open: true; в закрытой/неизвестной сессии отсутствие grants — false; сервер проверяет всегда
events:    on("select", (ref, obj)) | on("refresh", {units, servers, domain}) | on("logout")
where:     where(ref) → {worker, server, door: {url, token, expires, routes} | null, reason}
           библиотека превращает отсутствующее поле door HTTP-ответа в null для оболочки; HTTP Where остаётся формой М10/4
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

Общие коды: неизвестный путь — `404 NoRoute`; неверный метод — `405 {detail: method, error: method}`; `/<rows>/<id>/<ещё>` — 404 «a unit's path names one unit», кроме двери байтов `/<rows>/<id>/<blob_field>` урока 10 (иной метод, чем `PUT`, — 405); полоса занята — `503 busy`, `Retry-After: 1`; `/session`, `/healthz` — резервная полоса; `/metrics`, `/healthz` — полоса монитора.

---

### Полные формы и границы Н2

Все JSON-ответы собственных дверей описаны компонентами OpenAPI. Каждый `GET` консоли — своих дверей и дверей других уроков, которые консоль отдаёт (`/spec` — урок 2; `/<rows>`, `/<rows>/<id>` — 3; `/policy`, `/drain`, `/unplaceable`, `/where/<id>` — 4; `/events` — 8; `/schema`, `/<table>` — 10), — отвечает и на `HEAD`: тот же код и заголовки, без тела; каждый контракт, объявляющий такой URL, перечисляет `head`. HTML, JS, CSS и метрики — строки соответствующего media type, а не JSON. Успешный `/healthz` — ровно `{ok: true}`. `/mounts` — `{root, mounts: {имя подсистемы: SpecView}}`. `SpecView` взят из М10/2 без ослабления.

`Servers` — `{policy, servers: {имя: ServerRow}, status?}`. `ServerRow` содержит обязательные `resource`, `resource_heard_at`, `resource_url`, `space`, `labels`, `labels_node`, `labels_source`, `draining`, `decommission`, `decommissioned`, `decommission_refusal`, `decommission_warning`, `decommissionable`, `lost`, `requires_resource`, `placeable`, `why`, `workers`. Неизвестные адрес/место/время/причина и отсутствующая просьба вывода представлены `null` по схеме. `lost` — массив `{unit, place?, worker?}`; `decommission` — `{at, by, gone?}`. Метки — массивы слов. `WorkerRow` требует `worker, load, capacity, labels, state, idle_by_policy, hung, name_conflict`; `name_conflict` — boolean. Необязательные детали и их типы закрыто перечислены в схеме. `status` выводит объявленные спецификацией значения JSON, не произвольные секретные поля.

**Выдачи консоли — вывод из строк и пульсов** (часы — монотонные часы консоли; первый взгляд на версию — как свежий):

| Выдача | Правило |
|---|---|
| `/metrics` у root | ряды всех подсистем каталога и ряды платформы `w2c_*` (Н3); у `/<sub>/metrics` — ряды только этой подсистемы, без `w2c_*` |
| ряд `<sub>_<console.running>` | число единиц из прочитанных пульсов воркеров; пульсы прочитаны и живых нет — `0`; неответ хранилища — 503 на весь `/metrics` |
| `ServerRow.resource` | пульс ресурса менялся < 45 с — `live`; пульс старше, строка `platform/doors/<s>` менялась < 45 с — `unreachable`; нет ни пульса, ни строки двери — `unknown`; иначе — `silent` |
| `WorkerRow.state` | пульс воркера менялся < 45 с — `live`, иначе `stale` |
| `WorkerRow.capacity` | поле пульса `placement.capacity.from`; поля нет — `capacity.default`; поле не число — `null`: воркер не принимает новых единиц (урок 4 Н1.3) |
| `WorkerRow.idle_by_policy` | `true`, когда при `servers: distinct` воркер на месте не хранитель (урок 4 Н3 «выбрать»), иначе `false` |
| `/resources` | серверы с прочитанным пульсом ресурса; `state` — `live` (< 45 с) или `silent`; `workers`, `running`, `unknown`, `instances`, `pass_stalled` — из пульса урока 8 Н1.4 как есть; нечитаемый пульс в ответ не входит, его считает `w2c_resource_heartbeats_garbled` |
| `WherePlace` без подписанта двери | поля `door` нет совсем (не `null`) |

`/resources` — объект по имени сервера с полными `ResourceRow`: обязательны `server, ts, url, schema, build, usage, usage_at, space, volumes, units, mirrors, short, state`; диагностические расширения перечислены в контракте. Это наблюдение пульсов ресурса, а не удостоверение доступности каждого объекта. `/where/<table>/<place>?unit=<id>` возвращает `{worker, place, server, door?}` либо 404 `{unreachable}` с одноимённым значением заголовка `X-Unreachable`. Неизвестная таблица — 404 до проверки `unit`, известная без `unit` — 400.

Общие отказы консоли — формы М10/2: `{detail, error}` с установленными значениями `error`; 503 включает `denied` при потере доверия и `busy` с `Retry-After: 1` при заполнении полосы. 429 имеет `Retry-After`. Специальные тела: `NoVersion` — `{error: "no such version"}`; `MountedPage` — `{detail, error: "is mounted"}`; `NotPlaced` — `{reason}`. 400/408/413 описывают отказ чтения; тело ограничено по реально принятым байтам, короткое даёт 400. `/session` GET анонимному даёт 200 с состоянием; плохая попытка POST — 401, открытый режим — 400, неверный аварийный вход — 403. DELETE снимает обе куки. Полоса, framing, доверие/петля, личность, Origin по куке, гранты и чтение проверяются в порядке Н3; отказ не имеет побочных записей двери.

Двери единиц, размещения, событий, таблиц и схемы принадлежат М10/3, 4, 8, 10. `/domain/*` и открытые `/api/*` — контракт М11/ADR-0066; успешное тело пересылки принадлежит ему. Они перечислены как зависимости, без фиктивной схемы «любой объект». Собственные маршруты этого урока `/spec`, `/servers`, `/unplaceable`, обе формы `/where` и `/metrics` также явно объявлены с префиксом `/<sub>`; префиксы делегированных дверей — у их владельцев; общие `/session`, `/mounts`, `/platform` не монтируются. Отсутствующий `v` или иная строка, включая нечисловую, — 404 `NoVersion`.

Короткие пути единиц, таблиц, blob-полей, /policy, /spec, /servers, /unplaceable,
/where и /metrics выбирают CONSOLE_ROOT; форма /{sub}/… явно выбирает загруженную
подсистему, включая root. В OpenAPI владельца полный URL может быть задан парой
стандартных servers + paths: origin консоли без завершающего / либо origin/{sub},
затем путь операции. Это исполнимое описание URL, а не пояснение x-mounting.
Общие /drain, /schema, /session, /mounts, /healthz, /resources, /platform/*,
/servers/{server}/labels и /servers/{server}/decommission не получают такой префикс.
События /events и отметки /marks следуют формам владельца8. Просьбы и учёт человека
всегда именуют подсистему: /{sub}/requests и /{sub}/asked/{sha16}, включая CONSOLE_ROOT;
короткие /requests и /asked/{sha16} вне профиля, неизвестный маршрут —404 по Н2/Н4.

Область монтирования допущена загрузчиком М10/2: имя подсистемы не из 21 зарезервированных слов, а ни одно имя подсистемы не пересекает unit.rows/tables каталога, включая собственные. Недопущенный каталог не запускает консоль; приоритета, скрывающего одну из двух обещанных дверей, нет.

## Н3 Проход

### запрос → ответ (консоль)

```
1. полоса: резервная / монитора / общая; занята → 503 busy
2. X-User стереть; framing и предел по заголовку; chunked → 400
3. определить доверие gate: неизвестно → 503; домена нет и не петля → 403 ДЛЯ ВСЕХ путей,
   включая открытые и /session*; ни одна такая дверь ещё не исполнена
4. /session* → процедура Н1.3: после установления личности, если запрос действует по куке,
   чужой Origin → 403 до изменения сессии/кук; иначе ответ процедуры
5. путь → дверь и что она требует (Н1.3 need); пути нет → 404
6. кто звонит, если дверь требует личность (Н1.3 identity) → иначе 401
7. личность выбрана по куке и Origin чужой → 403; затем единицы из пути и требуемая возможность → грант или 403 + журнал
8. прочитать тело с фактическим пределом и таймаутом; если единица определяется телом, проверить её здесь;
   unit_of / reach / names добавляют проверки. Ни одного изменения до завершения всех проверок
9. дверь: единицы (урок 3), контроллер (урок 4), события и просьбы (урок 8), /spec, /mounts, /servers, /where, /metrics
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

**Граница наблюдения.** Строки, пульсы и отчёт контроллера могут быть прочитаны в разные моменты. Ответ не является транзакционным снимком и не разрешает запись или остановку процесса. Возраст — от изменения, увиденного консолью, по её монотонным часам; первое наблюдение начинает возраст с нуля. Сбой обязательного чтения — 503; недоступный отдельный ресурс — `unknown`/`unreachable`, не пустые воркеры или доказательство отсутствия. Необязательная диагностика может отсутствовать, но обязательные поля ответа сохраняются.

### `/where/<id>`

```
прочитать intent → placement нужной единицы → intent по М10/4 Н1.5; версия intent изменилась → повторить;
обязательное чтение не подтверждено → 503. При неизменном active и id в members взять target/reason intent,
иначе worker/reason строки placement; отсутствие placement не отменяет target активного intent.
эффективный worker "" или нет → 404 {reason: эффективная причина | «not placed»}
пульс воркера → server, url двери (door.routes спеки) → door: {url, token (door1.<kid>…, Ed25519 ключом door/signer,
TTL 120 с, в токене user, unit, holder, routes только чтения), expires, routes}; token выдаётся по view на единицу,
каждая выдача — журнал door.issued; directory — где единицу видят (5 с кэш), scans
```

**Гонки.** Двойное чтение intent отсеивает смену принятого решения; при стабильном active целевой воркер берётся из него, даже до записи placement. Эффективное размещение и пульс читаются отдельно. Ответ называет наблюдённого держателя; переезд может завершиться до использования двери. Нельзя обещать один момент для всех полей. Нет достоверной двери — поле `door` отсутствует; null в HTTP-ответе не допускается; ошибка чтения назначения — 503, а не 404. Действительность операции повторно проверяет держатель по эпохе/аренде. Формы `Where`, `NotPlaced`, `Door` — точные формы владельца М10/4.

### `/where/<table>/<place>?unit=<id>`

После общих framing/доверия/личности: таблица не объявлена или не таблица мест — 404
текстовым отказом; это проверяется до обязательности/формы unit. Затем unit обязателен,
имеет форму id единицы выбранной подсистемы (иначе 400); нужен view на эту единицу.
После гранта прочитать строку места, удержание `<sub>/holds/<place>` и пульс держателя
по М10/5 (логическое имя worker = hold.by, не экземпляр hold.holder). Неподтверждённое обязательное чтение — 503; достоверно нет действующего
удержания — 404 `{unreachable: place@server}` с X-Unreachable того же значения.
Есть удержание — `{worker, place, server}`. Достоверная дверь держателя с объявленными
door.routes, доступным подписантом и подтверждённым адресатом unit добавляет door:
тот же Ed25519-токен на 120 с, пользователь/unit/holder/читающие routes и door.issued,
что в проходе `/where/<id>`. Нельзя выдать токен иному или неподтверждённому держателю;
когда дверь подтвердить нельзя, поле отсутствует, не null, местоположение остаётся ответом.

**Гонки.** Удержание/пульс не общий снимок; ответ не продлевает аренду. Изменившийся
держатель после ответа отсекается проверкой эпохи/аренды у двери. Ошибка чтения не
объявляется отсутствием места, отсутствие токена не объявляется отсутствием удержания.


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
  # reconcile_last_pass_age_seconds — сколько секунд объект <sub>/controller/pass (урок 4 Н1.2) не менялся на глазах
  # консоли (её монотонные часы, первый взгляд — 0), объекта нет — −1; reconcile_last_success_age_seconds — то же от
  # последней увиденной смены его поля last_success, успешного прохода не было — −1; второй читает скрипт запасных
  # (урок 11 Н1.5 правило 2)
metrics[]:  закрытый перечень ключей элемента (загрузчик урока 2 отказывает иным): name, type, from, agg, equals, when, default,
            live, labels, count, where, unheld, unless {table, where}, buckets, label, values; смысл и грамматика значений — М13
платформы, один раз (root); источник — пульсы ресурсов урока 8 Н1.4 и уборка просьб этой консоли:
  w2c_resources_live — ресурсов, чей пульс менялся < 45 с; w2c_resource_heartbeats_garbled — нечитаемых пульсов ресурсов
  с запуска процесса консоли; w2c_resource_full{server} — 1 при space.full пульса; w2c_resource_short_bytes{server} — поле
  short: сколько байтов отметка просила освободить и не смогла; w2c_resource_waits{server} — ожиданий /events/wait сейчас,
  w2c_resource_waits_held_total, _full_total, _replaced_total{server} — с запуска ресурса (поле waits, урок 8 Н3
  «/events/wait»); w2c_resource_rows_garbled{server,table} — нечитаемых строк таблиц, прочитанных ресурсом;
  w2c_resource_restore_left{server}, w2c_resource_restore_failures_total{server} — поле restore (восстановление
  событий с копий соседей, урок 8 Н1.4 mirror); w2c_resource_mirror_failures_total{server},
  w2c_resource_mirror_too_big_total{server} — поле mirror (урок 8 Н1.4 mirror, PEER_FAILS);
  w2c_requests_expired_total{sub}, w2c_requests_unknown_total{sub} — просьб, которые уборка этой консоли закрыла
  expired и unknown с запуска процесса (урок 8 Н3 sweep)
значения — по значению, не по написанию в пульсе: целое — целым (61, не 61.0; age тоже 10), нецелое — кратчайшей
  записью, читаемой обратно в то же число (7.5; экспонента допустима: 1e+21, 1e-07); одно правило для отсчёта,
  le корзины и слова equals (ADR-0055); подписи экранированы
```

**Граница наблюдения.** Ряды могут относиться к разным моментам; отсутствие достоверных данных не заменяется нулём. Отказ обязательного сбора — 503; диагностические ряды могут отдельно показывать неизвестность по своему контракту. Записи — двери уроков 3, 4, 8 со своими `cas` и ключами.

---

## Н4 Отказы

| Причина | Код | Тело | Что делает вызывающий |
|---|---|---|---|
| аварийный вход: пароль/условия неверны | 403 | `{detail, error: denied}` | не создавать сессию; общий журнал отказа доступа |
| нет такого пути | 404 | `{detail: no such route, error: no such path}` | ошибка клиента |
| метод не тот | 405 | `{detail: method, error: method}` | ошибка клиента |
| версия модуля не та | 404 | `{error: no such version}` | обновить страницу вместе с модулем |
| страница у смонтированной подсистемы | 404 | `MountedPage` Н2 | идти на root |
| не личность | 401 | `{detail: "this console asks who is calling: …", error: denied}` | войти (login_url) |
| гранта нет | 403 | `{detail: "<кто> may not <cap> <единица \| here>", error: denied}`; журнал | — |
| нет домена, не петля | 403 | `{detail: "this cluster is in no domain … loopback", error: denied}` | подключить домен |
| ключи были, проверить нечем | 503 | `{detail: "…admits nobody", error: denied}` | восстановить доверие |
| чужой Origin на действующем запросе по куке | 403 | `{detail, error: denied}` | — |
| `/session POST` у открытой консоли | 400 | `{detail, error: "this console is open"}` | — |
| `/session GET` и `DELETE` у открытой консоли | 200 | GET — `{open: true, login_url}`; DELETE — `{out: true}` | — |
| общий предел входа консоли: запросов одной личности больше предела | 429 | ConsoleRefusal `{detail, error}`, `Retry-After` | ждать срока; значение предела — решает реализация (п. 2) |
| аварийный вход: предел | 429 | `Retry-After` | ждать |
| тело: chunked / больше / медленно / коротко | 400 / 413 / 408 / 400 | `{detail, error}` Н2 | ошибка клиента |
| полоса занята | 503 | `{detail, error: busy}`, `Retry-After: 1` | повторить |
| обязательное чтение для /servers, /resources, /where или /metrics не подтверждено | 503 | ConsoleRefusal `{detail, error}` | повторить чтение; отсутствие/пустоту не выводить |
| `/where`: не размещена / не id | 404 / 400 | `{reason}` / `{detail, error}` | — |
| `/domain/<rest>` к держателю: держатель не ответил / нет домена или ключей | 502 / 503 | контракт М11/ADR-0066 | — |
| `/where/<t>/<p>`: место не держат | 404 | `{unreachable: place@server}`, `X-Unreachable` | — |
| `/events` без индекса ресурса | 503 | контракт М10/8 | — |
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
| 06 | отказы: неизвестный путь 404 `no such path`; метод 405; `/counters/c4/x` 404; смонтированная `/testsub2/` 404 | Н4 |

Проверяются чтением и структурно: модуль — по контракту `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` (закрытый список вызовов, словарь, `may`, `api` с ключом, дерево, форма, серверы, домен) — одно свидетельство для всех реализаций, потому что модуль у них один (ADR-0005); сторожевая с доменом (401/403/503, порядок, CSP) — стенд М11; `/where` с дверью — testsub2 (`door: {routes: [read, play]}`), чтением (стенд урока 11: воркера testsub2 в его сценариях нет); `servers.status`/`show` — testsub2 (`servers.show` по `shelves`, `servers.status`), чтением (стенд урока 11, сценария нет); правило адреса без домена (Н1.3 `open`; урок 11 Н1.6 `roles`) — чтением (стенд урока 11, сценария нет).

---

## Решает реализация

Реализация обязана назвать в своём описании:

1. **как задаётся `CONSOLE_ROOT`**; источник оболочки — норма Н1.1 (поле `shell` строки спеки);
2. **пределы**: тело (≥ 1 MiB), блоб, сессия (16 KiB), полосы и их размеры, таймауты, общий предел входа (429, Н4);
3. **кэши** `/where` (directory 5 с), эпох (3 с), `/domain` пересылки;
4. **отладочная личность** (Н1.3 `identity` п. 4) и аварийный вход — предел попыток;
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
- [ ] **М10/9-06** закрытый список вызовов модуля Н1.4 и порядок загрузки — проверяется чтением: вызовы модуля и их порядок — по Н1.4 `reads`/`writes`/`never`/`order`; причина — модуль один у всех реализаций, двери порядок загрузки не показывают
- [ ] **М10/9-07** контракт оболочки Н1.5: `api` с ключом логического действия и повторами только по контракту владельца, `where` с `door`, вызовы библиотеки, без хуков и чужого DOM — проверяется чтением: тест оболочки (jsdom; предмет — поведение страницы, не двери)
- [ ] **М10/9-08** `/servers`, `/resources` и `WorkerRow` по Н2/Н3 — сц. 04; стенд урока 5; ResourceRow — чтением обязательных полей Н2: сц.04/6 видит только пустой объект
- [ ] **М10/9-09** `/where`: эффективное размещение через intent/placement/intent по М10/4 (чтением по README приёмки 09, в TSV только отсутствие); 404 с `reason`, `door` только по view, токен Ed25519 120 с, журнал `door.issued` — сц. 04; стенд М12A; where(table,place) — чтением этого Н3: TSV04 проверяет лишь неизвестную таблицу, не удержание и токен
- [ ] **М10/9-10** `/metrics` по Н3: ряды подсистемы, платформенные `w2c_*` один раз, число по значению (Н3 «/metrics — текст», ADR-0055) — сц. 05
- [ ] **М10/9-11** общие коды Н4, полосы, пределы тела — сц. 06; чтением
- [ ] **М10/9-12** байты мимо консоли: ни одного маршрута потока/архива в консоли платформы (ADR-0015) — проверяется чтением: тест границы реализации (список маршрутов консоли против слов потока и архива); причина — отсутствие маршрута запросом не показать

## Соответствие прежним урокам

Нормирует `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` (контракт модуля — разделы 1–10 как Н1.1, Н1.4, Н1.5; раздел 10a — М12A; расхождения контракта с кодом сняты в пользу урока: имя оболочки `<sub>.shell.html`, список вызовов модуля дополнен `/schema`, `/unplaceable`, `/policy`, `/servers/<s>/labels`), `М10A_Platform/15-SpecConsole.md` (шаги 1, 3, 6, 8 (коды), 9–14: описание, чтения, `/servers`, `/metrics`, объявленное, сторожевая, ключ, монтирование; шаг 4 — урок 3; 7 — урок 8), `М10A_Platform/16-HTML.md` (целиком: страница, модуль, слова, наложение, форма, `api`, вызовы оболочки, CSP). Исторические исходники сохранены в Git; контракт модуля остаётся описанием публичной поверхности до переноса `W` и разметки в урок.

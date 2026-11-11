# C3 — `admin@<id>` движок шлёт в `admin.sock` стендового хранилища, а не участника; `@until` без повторов

**Случаев:** 28 шагов `red implementation expectation` цели P/01.3/group и 6 ложных GREEN.
- red: строки 9, 13, 16, 17 (сц. 07); 100, 101, 102, 106, 107, 110, 114 (сц. 17); 153, 168, 169, 174 (сц. 18); 217, 219 (сц. 25); 224, 226 (сц. 26); 235, 237 (сц. 27); 246, 255, 256 (сц. 28); 261, 266 (сц. 29); 281, 283 (сц. 31). Все они — запросы `admin@<id>`, 20 из них под `@until`.
- GREEN не по существу: строки 10, 11, 111, 112 (`admin@s1 POST /v1/join|leave` → 409 `refused`), 160 (`admin@s1 POST /v1/write` → 200), 170 (`admin@s1 GET /v1/get` → 200).

## Наблюдение движка
- `scenario_verdict.go:207–211`: `admin@s1` разбирается в `door = "admin"`, `member = "s1"`.
- `scenario_verdict.go:377–383` (`doorSocket`): для двери `admin` и `restored` сначала `if _, err := os.Stat(c.socket); err == nil { return c.socket }`. Это `admin.sock` стендового хранилища цели, оно поднято до сценариев (`:58–68`). До поиска участника (`:392`) движок не доходит. Поэтому каждый `admin@<id>` уходит в одно стендовое хранилище коробки.
- `scenario_verdict.go:189–190`: префикс `@until <s>` отбрасывается, запрос шлётся один раз. Повтора до совпадения в течение срока нет.
- Итог: ответы стендового хранилища (коробка, один голосующий, без группы) сравниваются с ожиданиями участника группы: `"state": "Follower"`, `"Door"`, метрики raft, строка двери `platform/configstore-doors/d1`, `epoch_floor` после `recover`. Отсюда `red implementation`. Отказ `409 refused` на `join`/`leave` у коробки совпал с ожиданием случайно (GREEN 10, 11, 111, 112). Запись и чтение `testsub/epoch/u1` в коробке — тоже (160, 170).

**Повтор replay188** (`trace/P_01_3_group.jsonl`; запрос — `request_sent`, ответ — `observation`). На все 28 красных и 6 GREEN отвечало стендовое хранилище цели: процесс `stand.store` кандидата в режиме коробки, в stderr `configstore: started box srv-a, store …/data/configstore`. Ни один участник не поднялся (C1).
- **Статус, 17 шагов** — :9, :13, :100, :114, :153, :168, :174, :217, :219, :224, :226, :235, :246, :255, :261, :281, :283. Запросы `admin@s3|d1|s1|s5 GET /v1/status`, ответ один и тот же: 200 `{"id":"srv-a","state":"Leader","leader_id":"srv-a","term":1,…,"voters":["srv-a"],"members":{},"tls":false,…}`. Строка ждёт `"state": "Follower"`/`"Door"`/`"Leader"` с `"leader_id": "s1"`. Даже :168 и :255 (`Leader`) красные из-за `leader_id` `srv-a` ≠ `s1`.
- **Метрики, 3 шага** — :17, :101, :102: `admin@s1|s3 GET /metrics` → 200 `configstore_raft_term 1`, `configstore_raft_state{state="leader"} 1` (у :102 строка ждёт `follower`, у :17 — `configstore_doors 1`).
- **Чтение строк, 5 шагов** — :16, :237 (`GET /v1/get?key=platform/configstore-doors/d1`), :169, :256, :266 (`GET /v1/get?key=platform/epoch_floor`) → 200 `{"items":null,"index":""}`. В коробке нет строки двери и нет поднятого `recover` пола.
- **Состав, 3 шага** — :106 `POST /v1/leave {"id":"s3"}` → 409 `{"kind":"refused","error":"the last voter"}` (строка ждёт 200); :107, :110 `POST /v1/join {"id":"s3",…}` → 409 `{"kind":"refused","error":"the box has no group: a foreign member is not admitted"}` (строки ждут 403 и 200).
- **GREEN не по существу, 6 шагов** — :10, :11, :111 (`join` → 409 «the box has no group …»), :112 (`leave s9` → 409 «the last voter»), :160 (`write testsub/epoch/u1` → 200 `{"index":"1"}`), :170 (`get testsub/epoch/u1` → 200 `{"items":{"epoch":"429496729600005"},"index":"1"}`). Это ответы коробки, а не участника.

Число попыток под `@until` трасса не пишет. Что запрос ушёл один раз — по чтению кода (`scenario_verdict.go:189–190`). На вердикт это не влияет: коробка отвечает одно и то же.

Ответы коробки кандидата сами по себе разумны: `leave` последнего голосующего — отказ, `join` чужого участника в коробку — отказ. Красного кандидата в них нет.

## Норма
J-вход `49e62279`, `Platform/common/acceptance/README.md`:
- `:640–641` «Member doors: `store@<id> <request>` — the door of P/01.1 through the socket of the role of the scenario of the member …; `admin@<id> <request>` — through its `admin.sock` (not forwarded …)»;
- `:303` `@until <seconds> <request>` — «repeat the request, at least once per second, until it matches `expect`, no longer than the term».

## Код кандидата
Группа кандидата этими шагами не вызывалась: участники не стартовали (C1). Отвечало стендовое хранилище: профиль `stand.store`, режим коробки.

## Что видела модель
Не относится к модели. Раздел «Member doors» модель прочла (журнал, вызов 32).

## Мнение
Исход — **движок**. Норма однозначна (README:640–641, :303). Все 28 красных `implementation` цели group — не красные кандидата: суд мерил не тот процесс. Повтор подтвердил это телом ответа: `"id":"srv-a"`, `"voters":["srv-a"]`, коробка. Вторая причина — **цикл линии судьи**: ворота не подавали заглушку, у которой стендовое хранилище и участник отвечают по-разному.

Тот же дефект маршрута, вероятно, есть и в других целях с `admin@<id>` (трёхсерверный стенд P/04). Это вне участка.

## Вопросы ревьюеру
1. `@until` без повторов задевает и цели без группы (P/01.3/daemon, главы 1.1–1.2). Вынести это в отдельный класс общего пакета?

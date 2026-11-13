# Векторы: чтение пульса ресурса и воркера по форме семьи

Текст производный от `vectors/heartbeat-read/README.md`, руками не правится: источник — английский [`vectors/heartbeat-read/README.md`](../../../vectors/heartbeat-read/README.md), правка идёт в него, русский пересобирается переводом (ADR-0121; ADR-0124 доп. (1) п. 4).

Владелец — [договор наблюдения](../../contracts/observation.md) «Форма», «Состояние ресурса» (догадка стадии C
C04-DEP-OBS-HEARTBEAT-01, решение «Архитектора» 2026-10-25). Форма — `Platform/05-resource/data/resource-heartbeat.schema.json`,
исходы — `Platform/05-resource/data/resource-heartbeat.outcomes.tsv` (семья `platform/resources/<server>/heartbeat` урока
P/05). Участники — наблюдатели `resource_state`: контроллер и консоль. Байты пишет «Спецификация».

## `cases.tsv`

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок
`case<TAB>object<TAB>expect<TAB>note`.

Основа каждого случая — пульс со всеми обязательными полями, включая `door`, `waits`, `restore` и `mirror`.
В основе дверь работает в режиме `loopback`, счётчики ожиданий и зеркалирования равны нулю, `waits.max: 16`, карта `restore` пуста.
Каждый случай меняет только названный предмет; числовые лексемы в `object` — часть входа, их нужно сохранять.

| Поле | Значение |
|---|---|
| `object` | пульс ресурса — объект JSON под ключом `platform/resources/srv-a/heartbeat` |
| `expect` | `{"readable": false}` — объект целиком нечитаем (исход «объект целиком»: жизни не подтверждает); `{"readable": true, "fields": [<поле>…]}` — пульс читаем, у перечисленных полей (в порядке строк `outcomes.tsv`) действует их исход поля из `outcomes.tsv` (`build` — читается как `""`, `retention_garbled`, `retention_withheld` — отсутствующим), пустой список — исходов поля нет |

## `worker.tsv`

Чтение пульса воркера `<sub>/heartbeats/<name>` по форме `Platform/03-worker/data/heartbeats.schema.json` и исходам
`Platform/03-worker/data/heartbeats.outcomes.tsv` (урок P/03.4 N1.1; C08-HEARTBEAT-READER-99-VECTORS, решение «Архитектора» 2026-10-26). Читатели — консоль (`GET /{rows}`, `/servers`,
`/metrics`, `/where`, door.pass, `/schema`), контроллер, дренаж, теневой отчёт домена. Те же правила файла; поля `case`,
`key` (ключ объекта), `object`, `expect`, `note`.

| `expect` | Значение |
|---|---|
| `rows` | читатель `GET /{rows}` (P/06.1 N2 «rows»): `"unreadable"` — пульс целиком нечитаем, элементы не читаются; `{"skip": [<индекс>…]}` — элементы `status[]` не по форме пропускаются, остальные идут в rows |
| `others` | прочие читатели (`/servers`, `/metrics`, `/where`, контроллер, дренаж): `"unreadable"` — пульса нет (воркер не показан, пульс в `<sub>_heartbeats_garbled`); при элементе `status[]` не по форме — тоже `"unreadable"` (исход `/status`); `"readable"` — читаем |
| `fields` | при `others: "readable"` — поля с исходом поля в порядке строк `outcomes.tsv` (`build` — `""`, `schema` — `null` в processes, `pending_writes` — не сказан); иначе `[]` |

## Прогон

Без стенда: сторона читает объект своим читателем пульса (у ресурса — тот, что даёт `resource_state`; у воркера — каждый
читатель из `expect` своей частью) и сравнивает: читаем ли пульс, какие элементы пропущены и к каким полям применён исход поля. Состояние по истории наблюдения — пакет [`resource-state`](../resource-state/README.md).
Кто исполняет: `cases.tsv` — наблюдатели `resource_state`: контроллер (`04-controller`) и консоль (`06-console`);
`worker.tsv` — консоль (`06-console`) весь `expect`; контроллер (`04-controller`) и теневой отчёт домена (`08-domain`) —
части `others` и `fields` (ACC-VECTORS-CONNECT-03: строку исполняет роль, чья норма вызывает её функцию; решение «Архитектора» 2026-10-26).

## Провод векторов

Провод `cases.tsv`, `worker.tsv` задают строки `common/heartbeat-read` [единой формы](../../../vectors/wire.tsv); [грамматика](../wire.md). Форма — источник шапки, выбранных входов, фикстур, кадра нативного ответа и сравнения. Смысл входов и выходов, обязанности потребителей, проверка нативной формы и проверки вне функции остаются здесь. Layout — исключение из вызовов функции, а не доказательство отдельной приёмки.

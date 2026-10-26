# Векторы: чтение пульса ресурса и воркера по форме семьи

Владелец — [договор наблюдения](../../contracts/observation.md) «Форма», «Состояние ресурса» (догадка стадии C
C04-DEP-OBS-HEARTBEAT-01, решение «Архитектора» 2026-10-25). Форма — `Platform/05-resource/data/resource-heartbeat.form.yaml`,
исходы — `Platform/05-resource/data/resource-heartbeat.outcomes.tsv` (семья `platform/resources/<server>/heartbeat` урока
P/05). Участники — наблюдатели `resource_state`: контроллер и консоль. Байты пишет «Спецификация»; ожидания получены судьёй
схем семей навыка (режим читателя, DIALECT § 8–9), не кодом реализаций.

## `cases.tsv`

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок
`case<TAB>object<TAB>expect<TAB>note`.

| Поле | Значение |
|---|---|
| `object` | пульс ресурса — объект JSON под ключом `platform/resources/srv-a/heartbeat` |
| `expect` | `{"readable": false}` — объект целиком нечитаем (исход «объект целиком»: жизни не подтверждает); `{"readable": true, "fields": [<поле>…]}` — пульс читаем, у перечисленных полей действует их исход поля из `outcomes.tsv` (`build` — читается как `""`, `retention_garbled`, `retention_withheld` — отсутствующим), пустой список — исходов поля нет |

12 строк: 9 читаемых (из них 6 с исходом поля), 3 нечитаемых.

## `worker.tsv`

Чтение пульса воркера `<sub>/heartbeats/<имя>` по форме `Platform/03-worker/data/heartbeats.form.yaml` и исходам
`Platform/03-worker/data/heartbeats.outcomes.tsv` (урок P/03.4 Н1.1; C08-HEARTBEAT-READER-99-VECTORS, решение «Архитектора» 2026-10-26). Читатели — консоль (`GET /{rows}`, `/servers`,
`/metrics`, `/where`, door.pass, `/schema`), контроллер, дренаж, теневой отчёт домена. Те же правила файла; поля `case`,
`key` (ключ объекта), `object`, `expect`, `note`.

| `expect` | Значение |
|---|---|
| `rows` | читатель `GET /{rows}` (P/06.1 Н2 «rows»): `"unreadable"` — пульс целиком нечитаем, элементы не читаются; `{"skip": [<индекс>…]}` — элементы `status[]` не по форме пропускаются, остальные идут в rows |
| `others` | прочие читатели (`/servers`, `/metrics`, `/where`, контроллер, дренаж): `"unreadable"` — пульса нет (воркер не показан, пульс в `<sub>_heartbeats_garbled`); при элементе `status[]` не по форме — тоже `"unreadable"` (исход `/status`); `"readable"` — читаем |
| `fields` | при `others: "readable"` — поля с исходом поля (`build` — `""`, `schema` — `null` в processes, `pending_writes` — не сказан); иначе `[]` |

13 строк: по форме; не объект, нет `instance`, `status` не список, `worker` ≠ имени в ключе (правило прозы P/03.4 Н1.1, исход
«объект целиком») — нечитаем; элемент без `phase`, с нецелым `epoch`, `sealed` с `epoch`, `id` не по грамматике — пропуск у
`GET /{rows}`, прочим нечитаем; `unreadable` с `why` — по форме; исходы полей `build`, `schema`, `pending_writes`; путь `""`
раньше `/status` — нечитаем всем. Ожидания — судьёй схем семей навыка (режим читателя), правило `worker` — по прозе.

## Прогон

Без стенда: сторона читает объект своим читателем пульса (у ресурса — тот, что даёт `resource_state`; у воркера — каждый
читатель из `expect` своей частью) и сравнивает: читаем ли пульс, какие элементы пропущены и к каким полям применён исход поля. Состояние по истории наблюдения — пакет [`resource-state`](../resource-state/README.md).
Кто исполняет: `cases.tsv` — наблюдатели `resource_state`: контроллер (`04-controller`) и консоль (`06-console`);
`worker.tsv` — консоль (`06-console`) весь `expect`; контроллер (`04-controller`) и теневой отчёт домена (`08-domain`) —
части `others` и `fields` (ACC-VECTORS-CONNECT-03: строку исполняет роль, чья норма вызывает её функцию; решение «Архитектора» 2026-10-26).

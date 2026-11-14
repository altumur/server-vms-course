# Ресурс — жизненный цикл (урок P/05)

Контракт жизненного цикла процесса `resource`. Строки ссылаются на нормы урока и их не
пересказывают.

Текст производный от `lifecycle.md`, руками не правится: источник — английский [`lifecycle.md`](../lifecycle.md), правка идёт в него, русский пересобирается переводом.

[P/02.3]: ../../02-installer/ru/spec/02.3-installer.norms.md
[P/02.4]: ../../02-installer/ru/spec/02.4-installer.norms.md
[P/02.5]: ../../02-installer/ru/spec/02.5-installer.norms.md
[P/05]: spec/05-resource.norms.md
[журнал событий]: ../../common/ru/contracts/event-journal.md
[замок присутствия]: ../../common/ru/contracts/presence-lock.md
[Стенд]: ../../common/ru/acceptance/README.md
[каталог]: ../../common/data/catalog.tsv

## Запуск

- **Юнит** — `w2c-resource.service`, один процесс на сервер, без контроллера; `User=w2c`,
  `SupplementaryGroups=w2c-store w2c-events` ([P/02.4] N1.1, [P/05] N1.4).
- **Запуск** — через раннер `w2c-run.sh resource` с `W2C_ROLE=resource` ([P/02.4] N1.1 — юнит его ставит; N1.9).
- **Порядок старта** — проверка схемы `platform/schema` и чтение строки манифеста до первой записи ([P/05] N3 «старт ресурса
  — проверка схемы», [P/02.3] N3 «Старт процесса»); затем пульс сразу, поток пульса, `restore` бакетов в своей попытке,
  строка двери `platform/doors/<host>` ([P/02.4] N3 «старт сервера», шаг 2). Запуск restore не ждёт done перед публикацией двери; HTTP, пульс и первый проход после readiness продолжаются независимо (P/05-R312). Неполные попытки restore повторяются в том же процессе по P/05-R307.

## Окружение

Окружение собирает раннер `w2c-run.sh` в порядке P/02.4 N1.2: значения юнита → `roles/<W2C_ROLE>.env` → `w2c.env` →
файл подсистемы, раньше прочитанное побеждает; файлы — разбором, не `source` ([договор файла окружения](../../common/ru/contracts/env-file.md); [02-installer/lifecycle.md](../../02-installer/ru/lifecycle.md)).

| Переменная | Смысл и фаза | Источник входа | Норма |
|---|---|---|---|
| `W2C_ROLE` | роль `resource`; не та роль команды раннера — код 2 | [daemon-flags.tsv](../forms/daemon-flags.tsv), `W2C_ROLE` | [P/02.4] N1.2 |
| `PLATFORM_STORE` | дверь хранилища — сокет роли `configstore:///run/configstore/resource.sock` | [daemon-flags.tsv](../forms/daemon-flags.tsv), `PLATFORM_STORE` | [P/02.4] N1.2 |
| `PLATFORM_DIR` | корень состояния | [daemon-flags.tsv](../forms/daemon-flags.tsv), `PLATFORM_DIR` | [P/02.4] N1.2 |
| `RESOURCE_ROOT` / `EVENTS` | корень деревьев событий; в нём же замки присутствия `.workers/` | [daemon-flags.tsv](../forms/daemon-flags.tsv), `RESOURCE_ROOT` / `EVENTS` | [P/02.4] N1.2 «Канал настройки», [журнал событий], [замок присутствия] |
| `OBJECTS` / `PLATFORM_OBJECTS` | корень объектов двери объектов и копий тел | [daemon-flags.tsv](../forms/daemon-flags.tsv), `OBJECTS` / `PLATFORM_OBJECTS` | [P/02.4] N1.2, [P/05] N1.1 |
| `RESOURCE_HOST`, `RESOURCE_PORT` | адрес двери ресурса; юнит не пишет — умолчание процесса; задан в `w2c.env` — адрес привязки (вне петли — только с комплектом); при `mtls` цепочка — лист, затем его центр ([договор сертификата роли](../../common/ru/contracts/role-certificate.md) `server`) | [daemon-flags.tsv](../forms/daemon-flags.tsv), `RESOURCE_HOST`, `RESOURCE_PORT` | [P/02.4] N1.1, N1.2, N1.6 |
| `RESOURCE_URL` | адрес двери, который ресурс пишет в строку двери; IP-литерал вне петли (порог петли [договора сертификата роли](../../common/ru/contracts/role-certificate.md) `loopback`: `ip`) — ресурс при старте пишет строку журнала; у `https://` клиенты откажут `ip_address`, у `http://` — ошибка настройки, видимая отказом соединения | [daemon-flags.tsv](../forms/daemon-flags.tsv), `RESOURCE_URL` | [P/02.4] N1.2, [P/05] N1.4 `door_row` |
| `RESOURCE_TLS` | дверь по TLS | [daemon-flags.tsv](../forms/daemon-flags.tsv), `RESOURCE_TLS` | [P/02.4] N1.2, N1.6 |
| `SERVER_NAME` | свой сервер: ключ пульса и строки двери; не по грамматике — код 2 | [daemon-flags.tsv](../forms/daemon-flags.tsv), `SERVER_NAME` | [P/02.4] N1.2 |
| `BOX_ID` | коробка | [daemon-flags.tsv](../forms/daemon-flags.tsv), `BOX_ID` | [P/02.4] N1.2 |
| `BUILD` | слово сборки в пульсе | [daemon-flags.tsv](../forms/daemon-flags.tsv), `BUILD` | [P/02.4] N1.2 |
| `W2C_TLS_DIR` | корень комплектов; свой — `<W2C_TLS_DIR>/resource` | [daemon-flags.tsv](../forms/daemon-flags.tsv), `W2C_TLS_DIR` | [P/02.4] N1.2, N1.6 |
| `W2C_ENV` | файл общих настроек | [daemon-flags.tsv](../forms/daemon-flags.tsv), `W2C_ENV` | [P/02.4] N1.2 |

## Флаги

Нет: канал настройки — только окружение ([P/02.4] N1.2 «Канал настройки и раскладка `PLATFORM_DIR`»).

## Каталоги и файлы

- **Корень событий** — бакеты всех деревьев сервера `<корень событий>/<дерево>/<unit>/e<эпоха>/<start>Z.events.jsonl`;
  ресурс — владелец файлового контракта журнала событий, пишут в него воркеры и консоль ([журнал событий], [P/05] N1.2, [каталог]).
  Копии бакетов соседей — `<корень событий>/.mirror/<server>/…`, пишет только ресурс.
- **Замки присутствия** — `<events root>/.workers/<sub>/<instance>.lock`: ресурс берёт `flock` без ожидания и выводит
  `runs`, `gone`, `unknown`; файл `gone` МОЖЕТ удалить под своим `flock` ([замок присутствия] `presence_lock`, [каталог]).
- **Корень объектов** — дверь объектов, копии тел `<sub>/blobs/sha256-<hex>` от соседей кольца, надгробия `.gone/<object-key>`, замки каталогов `<каталог>/~lock`
  ([P/05] N1.1, N1.1 «Tombstones»). Имена файлов в обоих корнях — одно кодирование `%XX` / `%h<sha256>` ([журнал событий]
  «Имена файлов в общих деревьях»; порог `%h` — по полному имени файла с суффиксом нормы и запасом временного имени).
- **Строки хранилища** — пульс `platform/resources/<server>/heartbeat` (объект), строка двери `platform/doors/<host>`,
  просьбы освобождения `<sub>/requests/free-<server>-<volume>`; читает `platform/space`, `platform/mirror`,
  `<sub>/retention`, `<sub>/alarms_retention`, `platform/decommission/*`, `platform/schema`, `platform/manifest/<sub>` и метку
  `/rev` ([каталог], [P/02.5] N1.4).
- **Свой журнал** — `<корень событий>/audit/resource/e1/…` под исключительной блокировкой файла ([журнал событий]
  `journal`, `writer`).

## Коды выхода

| Код | Когда | Норма |
|---|---|---|
| 0 | смена манифеста — стоп, супервизор запускает снова | [P/02.3] N3 «Смена манифеста» |
| 2 | метка манифеста не по форме у работающего — остановка, рестарт отказывает до исправления метки оператором | [P/02.3] N3 «Смена манифеста», N4 |
| 2 | схема хранилища выше своей или не число | [P/05] N3 «старт ресурса — проверка схемы» |
| 2 | строка манифеста не читается или отказана | [P/02.3] N3 «Старт процесса» |
| 2 | файл окружения не по грамматике; `SERVER_NAME` не по грамматике; `W2C_ROLE` не роль команды | [P/02.4] N1.2, N4 |
| ≠ 0 | иной отказ старта — строка лога называет источник | [P/02.3] N3 «Старт процесса» |

Вне петли ресурс слушает только с комплектом (`door.mode` `mtls`): без комплекта — только петля, адрес вне петли — отказ
старта, код 2 ([P/02.4] N1.6 `process`).

## Сигналы и готовность

- **Готовность** — порт `RESOURCE_PORT` и строка `platform/doors/<host>`; раннер стенда ждёт обоих ([Стенд], [P/05]
  N1.4).
- **Пульс** — каждые HEARTBEAT_EVERY; строка двери — каждые ALIVE_EVERY договора наблюдения; проход — каждые PASS_EVERY, шаг дольше `PULSE_LIMIT` даёт
  `pass_stalled` ([P/05] N1.4, «Решает реализация» п. 7 — значение `PULSE_LIMIT`).
- **SIGTERM/SIGKILL** — состояние в строках и файлах; после возврата сервера ресурс тянет свои закрытые бакеты от соседей
  (`restore`, [P/05] N1.4 «Bucket restore»).
- **Перезапуск** — `Restart=always`, `RestartSec=2`, кроме кода 2 ([P/02.4] N1.1).

## Стенд

Корни `{data}/config`, `objects`, `events` до старта процесса создаёт команда запуска роли профиля — [общий README
приёмки](../../common/ru/acceptance/README.md) «Стенд без root»; процесс корней не создаёт ([P/02.4](../../02-installer/ru/spec/02.4-installer.norms.md) N1.1 `dirs`).

- Команда «Стенда» с подстановками `{rport}` — порт двери, `{server}` — имя сервера (`srv-a`; у стенда М11 —
  `srv-<кластер>`) ([Стенд] «Ресурс»).
- `{data}` — это `PLATFORM_DIR`: стенд ставит `PLATFORM_DIR={data}`, `RESOURCE_PORT={rport}`, `SERVER_NAME`, `BOX_ID`;
  корень событий — `{data}/events`, отдельного ключа нет ([Стенд] «One data directory»).

## Открыто

- Корень событий у стенда нескольких серверов на одном `{data}` — ни один стенд так не устроен: у каждого сервера свой
  `{data}`.
- Значение `PULSE_LIMIT` — решает реализация ([P/05] «Решает реализация» п. 7).

Числовой источник собственных уставок — [runtime-constants.tsv](../forms/runtime-constants.tsv). Типы и умолчания входов — только названные строки daemon-flags, без второго реестра.

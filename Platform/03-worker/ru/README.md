# Воркер (SDK) — урок P/03

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом.

Микромодуль: библиотека на каждом языке, роль <sub>worker. Договоры перечислены ниже.

Раскладка каталога (английский источник — на каноническом пути, русский текст для человека — в `ru/`):

```text
README.md                        этот файл
spec/03.K-worker.norms.md        нормы (главы 3.1–3.7 — .K)
spec/03-worker.README.md         инструкция реализации
lifecycle.md                     флаги, окружение, коды выхода, юниты
data/<семья>.schema.json         семьи данных, которыми урок владеет (JSON Schema 2020-12)
vectors/<алгоритм>/              векторы алгоритмов, которые урок вводит
acceptance/<K>/                  приёмка главы K (2, 3, 4, 6: README.md, scenarios.tsv)
ru/                              для человека, в выгрузку не входит — лекция ru/03-worker.md, переводы английского текста тем же путём
```

Формы пакета — [forms/README.md](forms/README.md): входы процесса, каталог отказов, машина захвата слота и план этапов. Швы SDK в `acceptance/K/seams.tsv` (только для судьи: тесты швов SDK) дополняют сценарии процесса; нормализованные порты CALL не задают API реализации.

## Что урок берёт из common

Эти общие файлы задают определения, на которые опираются главы, инструкция реализации, lifecycle и формы. Нормы глав остаются каноном; указатель не добавляет требований. Данные векторов и случаи швов SDK не заменяют требования в M.

| Файл | Разделы и назначение |
|---|---|
| [Нормативные слова](../../common/ru/NORMATIVE-TERMS.md) | N0: сила MUST, SHOULD и MAY |
| [Клиент хранилища](../../common/ru/contracts/store-client.md) | Адрес, запрос, ответ и исходы — чтения SDK, CAS, стражи и неоднозначная запись |
| [Клиент объектов](../../common/ru/contracts/object-client.md) | Адрес, операции и исходы — чтение объектов единиц и мест без замены неответа отсутствием |
| [Наблюдение](../../common/ru/contracts/observation.md) | Наблюдение версии, свежесть, удержание места, «Сервер выведен» и «Свежесть метки соперника» — часы читателя, возраст версии и вывод сервера |
| [Слот](../../common/ru/contracts/slot.md) | Форма, состояния и сроки — общий смысл слота и состояний его отдачи |
| [Имя слота](../../common/ru/contracts/slot-name.md) | Грамматика, выбор «по имени», порядок слотов и следующее число — имена кандидатов и их порядок |
| [Instance](../../common/ru/contracts/instance.md) | Instance — идентификатор процесса и часть holder, которая называет коробку |
| [Замок присутствия](../../common/ru/contracts/presence-lock.md) | Замок и боевые обязательства — владение именем процесса, повторы inode, конечная отмена |
| [Метки](../../common/ru/contracts/labels.md) | Метка и список меток — алфавит входа и грамматика списка |
| [Файл окружения](../../common/ru/contracts/env-file.md) | Грамматика, файлы, порядок чтения, переменные, «Константы и юниты» — входы запуска и сроки, которые использует SDK |
| [Схема](../../common/ru/contracts/schema.md) | Схема и проверка при старте — старт воркера и проверка после продления |
| [Запечатывание](../../common/ru/contracts/sealing.md) | Конверт, путь AAD и файл кольца — получатель открывает секреты до взятия эпохи |
| [Просьба и метка](../../common/ru/contracts/request-mark.md) | Просьба, метка, состояния исполнения и fetched — допуск, единственный вызов и неизвестный исход |
| [Журнал событий](../../common/ru/contracts/event-journal.md) | Строка и корзина, id события и instance писателя, запись строки — события и подавление |
| [Группа просьбы](../../common/ru/contracts/group-of.md) | Группа — последовательное исполнение просьб держателем |
| [Токен двери](../../common/ru/contracts/door-token.md) | Токен и ключи `door/keys` — держатель проверяет просьбу от консоли |
| [Токен домена](../../common/ru/contracts/domain-token.md) | Токен, проверка и слова отказов — кэш токена и проверки вида и адресата у получателя |
| [Ключи домена](../../common/ru/contracts/keys.md) | Набор `domain/keys`, отзывы `domain/revoked` и функция `keys` — принятые ключи и отзывы |
| [Местная дверь токена](../../common/ru/contracts/local-token-door.md) | Сокет роли, дверь, отказы и вызов в процессе — доступ к токену domain-worker |
| [Сертификат роли](../../common/ru/contracts/role-certificate.md) | Серверная сторона классов `role` и `mixed` — допуск в дверь процесса |
| [Боевые обязательства](../../common/ru/contracts/production-obligations.md) | Конечные бюджеты, наблюдаемое завершение, публичная приёмка и недостающие привязки — бюджеты операций и свидетельства завершения |
| [Каталог данных](../../common/data/catalog.tsv) | Файлы, ключи и читатели — разделы семей данных глав |
| [Кодек данных](../../common/data/codec.tsv) | Хранение значений семей — строковые поля строк и JSON-значения объектов |
| [Общая приёмка](../../common/ru/acceptance/README.md) | Стенд и словарь директив и дверей — общий стенд процессов и грамматика сценариев |
| [Удержание соединений](../../common/ru/acceptance/command-tables.md#удержание-соединений) | Удержание соединений — наблюдение принятых сокетов двери процесса воркера |
| [Профиль приёмки](../../common/ru/acceptance/PROFILE.md) | Команды, ключи, подстановки, команды векторов и имена проверок кода — реализация задаёт свой профиль |
| [Швы SDK](../../common/ru/acceptance/seams.md) | Порядок и владение peer, вход и наблюдение CALL, явный мост на стороне теста — нормализованные тестовые порты над настоящим SDK |
| [Стенд учебной подсистемы](../../common/ru/acceptance/testsub-stand.md) | Стенд процессов testsub — приёмка процесса с учебной подсистемой |
| [Приёмка pass](../../common/ru/acceptance/pass/README.md) | Подменный воркер прохода второго рода — граница подмены и настоящей двери воркера |
| [Приёмка TLS](../../common/ru/acceptance/tls/README.md) | Двери и клиенты пробы, исход и ожидания — проверки сертификата и цепочки |
| [Системная приёмка](../../common/ru/acceptance/system/README.md) | Стенд, сценарии и их границы — восстановление, потеря хоста и доменные зависимости |
| [Версии зависимостей](../../common/ru/versions/README.md) | «Закреплённые версии»: таблица версий и правила кэша модулей перед «Библиотека Raft и граница реализации» — валидатор семей и зависимости SDK |
| [Протокол векторов](../../common/ru/vectors/wire.md) | Строки и источники, выбор входа и групп, сравнение и утверждения — назначенные общие пакеты |
| [Общие определения схем](../../common/data/common.schema.json) | `$defs` семей урока — общие формы скаляров и объектов |
| [Потребители векторов](../../common/vectors/consumers.tsv), [таблица wire](../../common/vectors/wire.tsv) | Назначенные общие пакеты потребителя `03-worker` и их привязки входа и выхода |
| [Проверка строки](../../common/ru/contracts/row-check.md) | Строка единицы; Строка заказчика: `made`; Состояние единицы; Подготовка полей; Идентификатор и ограничения полей — типы строк, id жизни, заказанные строки и стражи состояния |
| [Пул](../../common/ru/contracts/pool.md) | Живой воркер; Пул; Хранитель места при `distinct`; Пригодность сервера: `placeable`, `why` — ёмкость, вес, остаток и допуск мест |
| [Пересылка](../../common/ru/contracts/forwarding.md) | Адрес клиента; Политика hop передачи доменному воркеру — `X-W2C-Client` и граница пересылки доменного воркера |
| [Доменные конверты](../../common/ru/contracts/domain-envelopes.md) | Вклад; Содержимое `sealed` — вход `entry` и конверт вклада |
| [Слияние событий](../../common/ru/contracts/events-merge.md) | Участник; Слияние; Эпохи; Ответ — `worker.reads`, ошибки эпох и неполная выдача событий |
| [Словарь проверок кода](../../common/acceptance/forms/code-rules.tsv) | Шапка и строки видов — замкнутые виды, аргументы и типы имён проверок кода урока |
| [Общий реестр целей](../../common/acceptance/forms/targets.tsv) | Заголовок столбцов — общая форма строки цели из описи целей урока |
| [Закреплённые модули Go](../../common/versions/go.mod) | Требуемые модули — источник имени и версии модуля строки проверки кода `json_schema` |

### Остальные внешние файлы и точные разделы

Публичные внешние файлы и разделы, которые использует M урока.

| Файл | Разделы и граница |
|---|---|
| `Platform/01-store/spec/01-store.api.openapi.yaml` | [файл](../../01-store/spec/01-store.api.openapi.yaml) |
| `Platform/01-store/spec/01.1-store.norms.md` | [файл](../../01-store/ru/spec/01.1-store.norms.md), [`#n0-vocabulary`](../../01-store/ru/spec/01.1-store.norms.md#n0-словарь-слов), [`#time-in-a-row`](../../01-store/ru/spec/01.1-store.norms.md#время-в-строке) |
| `Platform/01-store/spec/01.3-store.norms.md` | [файл](../../01-store/ru/spec/01.3-store.norms.md) |
| `Platform/02-installer/lifecycle.md` | [файл](../../02-installer/ru/lifecycle.md) |
| `Platform/02-installer/spec/02.1-installer.norms.md` | [файл](../../02-installer/ru/spec/02.1-installer.norms.md) |
| `Platform/02-installer/spec/02.3-installer.norms.md` | [файл](../../02-installer/ru/spec/02.3-installer.norms.md) |
| `Platform/02-installer/spec/02.4-installer.norms.md` | [файл](../../02-installer/ru/spec/02.4-installer.norms.md) |
| `Platform/02-installer/spec/02.5-installer.norms.md` | [файл](../../02-installer/ru/spec/02.5-installer.norms.md) |
| `Platform/04-controller/spec/04-controller.norms.md` | [файл](../../04-controller/ru/spec/04-controller.norms.md) |
| `Platform/05-resource/spec/05-resource.norms.md` | [файл](../../05-resource/ru/spec/05-resource.norms.md), [`#n2-doors`](../../05-resource/ru/spec/05-resource.norms.md#n2-двери) |
| `Platform/05-resource/vectors/relieve/README.md` | [файл](../../05-resource/ru/vectors/relieve/README.md) |
| `Platform/06-console/acceptance/1/README.md` | [файл](../../06-console/ru/acceptance/1/README.md) — сценарии 20 и 21: состояние единицы в ответе и таблицы воркера; свидетельство пункта P/03.6-06 |
| `Platform/06-console/spec/06-console.api.openapi.yaml` | [файл](../../06-console/spec/06-console.api.openapi.yaml) |
| `Platform/06-console/spec/06.1-console.norms.md` | [файл](../../06-console/ru/spec/06.1-console.norms.md) |
| `Platform/06-console/spec/06.2-console.norms.md` | [файл](../../06-console/ru/spec/06.2-console.norms.md) |
| `Platform/06-console/spec/06.4-console.norms.md` | [файл](../../06-console/ru/spec/06.4-console.norms.md) |
| `Platform/06-console/spec/06.5-console.norms.md` | [файл](../../06-console/ru/spec/06.5-console.norms.md) |
| `Platform/06-console/spec/06.6-console.norms.md` | [файл](../../06-console/ru/spec/06.6-console.norms.md) |
| `Platform/06-console/spec/06.7-console.norms.md` | [файл](../../06-console/ru/spec/06.7-console.norms.md) |
| `Platform/06-console/vectors/requests-body/README.md` | [файл](../../06-console/ru/vectors/requests-body/README.md) |
| `Platform/08-domain/README.md` | [файл](../../08-domain/ru/README.md) |
| `Platform/08-domain/acceptance/5/README.md` | [файл](../../08-domain/ru/acceptance/5/README.md) |
| `Platform/08-domain/acceptance/7/README.md` | [файл](../../08-domain/ru/acceptance/7/README.md) — сценарий 01: проверка токена у получателя; свидетельство пункта P/03.7-06 |
| `Platform/08-domain/data/holder.outcomes.tsv` | [файл](../../08-domain/data/holder.outcomes.tsv) |
| `Platform/08-domain/data/keys.outcomes.tsv` | [файл](../../08-domain/data/keys.outcomes.tsv) |
| `Platform/08-domain/spec/08.2-domain.norms.md` | [файл](../../08-domain/ru/spec/08.2-domain.norms.md) |
| `Platform/08-domain/spec/08.3-domain.norms.md` | [файл](../../08-domain/ru/spec/08.3-domain.norms.md) |
| `Platform/08-domain/spec/08.5-domain.norms.md` | [файл](../../08-domain/ru/spec/08.5-domain.norms.md) |
| `Platform/08-domain/spec/08.7-domain.norms.md` | [файл](../../08-domain/ru/spec/08.7-domain.norms.md) |
| `Platform/09-agent/README.md` | [файл](../../09-agent/ru/README.md) |
| `Platform/09-agent/acceptance/1/README.md` | [файл](../../09-agent/ru/acceptance/1/README.md) |
| `Platform/09-agent/spec/09.1-agent.norms.md` | [файл](../../09-agent/ru/spec/09.1-agent.norms.md) |
| `Platform/10-domain-console/spec/10-domain-console.norms.md` | [файл](../../10-domain-console/ru/spec/10-domain-console.norms.md) |
| `Platform/common/acceptance/seams.md` | [`#seam-adapter-protocol`](../../common/ru/acceptance/seams.md#протокол-адаптера-швов) |
| `Platform/common/contracts/sealing.md` | [файл](../../common/ru/contracts/sealing.md), [`#aad-path`](../../common/ru/contracts/sealing.md#путь-aad), [`#envelope`](../../common/ru/contracts/sealing.md#конверт), [`#ring-file`](../../common/ru/contracts/sealing.md#файл-кольца) |
| `Platform/common/vectors/values-by-type/README.md` | [файл](../../common/ru/vectors/values-by-type/README.md) |
| `Platform/01-store/spec/01.2-store.norms.md` | [файл](../../01-store/ru/spec/01.2-store.norms.md) — Права и роли доменного воркера |
| `Platform/04-controller/lifecycle.md` | [файл](../../04-controller/ru/lifecycle.md) — Договор соседнего процесса контроллера |
| `Platform/06-console/spec/06.3-console.norms.md` | [файл](../../06-console/ru/spec/06.3-console.norms.md) — Владелец консольной двери и прохода |
| `Platform/08-domain/spec/08.1-domain.norms.md` | [файл](../../08-domain/ru/spec/08.1-domain.norms.md) — Заявки, отчёты членов и читатели нечитаемого пульса |
| [`common/modules.md`](../../common/ru/modules.md), [`common/contracts/json.md`](../../common/ru/contracts/json.md), [`common/versions/go.mod`](../../common/versions/go.mod), [`common/versions/go.sum`](../../common/versions/go.sum) | файлы целиком | Общие модули кода и места пинов; правила употребления и граница договоров. |
| [`01-store/README.md`](../../01-store/ru/README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/acceptance/1/README.md`](../../01-store/ru/acceptance/1/README.md), [`01-store/acceptance/2/README.md`](../../01-store/ru/acceptance/2/README.md), [`01-store/acceptance/3/README.md`](../../01-store/ru/acceptance/3/README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/data/configstore-doors.outcomes.tsv`](../../01-store/data/configstore-doors.outcomes.tsv), [`01-store/data/configstore-doors.schema.json`](../../01-store/data/configstore-doors.schema.json), [`01-store/data/epoch_floor.outcomes.tsv`](../../01-store/data/epoch_floor.outcomes.tsv), [`01-store/data/epoch_floor.schema.json`](../../01-store/data/epoch_floor.schema.json) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/forms/code-rules.tsv`](../../01-store/forms/code-rules.tsv), [`01-store/forms/daemon-flags.tsv`](../../01-store/forms/daemon-flags.tsv), [`01-store/forms/metrics.tsv`](../../01-store/forms/metrics.tsv), [`01-store/forms/read-checks.tsv`](../../01-store/forms/read-checks.tsv), [`01-store/forms/refusals.tsv`](../../01-store/forms/refusals.tsv), [`01-store/forms/rights-checks.tsv`](../../01-store/forms/rights-checks.tsv) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/forms/runtime-constants.tsv`](../../01-store/forms/runtime-constants.tsv), [`01-store/forms/service-checks.tsv`](../../01-store/forms/service-checks.tsv), [`01-store/forms/stages.tsv`](../../01-store/forms/stages.tsv), [`01-store/forms/status-fields.tsv`](../../01-store/forms/status-fields.tsv), [`01-store/forms/targets.tsv`](../../01-store/forms/targets.tsv), [`01-store/forms/write-checks.tsv`](../../01-store/forms/write-checks.tsv) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/lifecycle.md`](../../01-store/ru/lifecycle.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/probes/README.md`](../../01-store/ru/probes/README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`01-store/spec/01-store.README.md`](../../01-store/ru/spec/01-store.README.md), [`01-store/spec/production-acceptance.md`](../../01-store/ru/spec/production-acceptance.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/acceptance/1/README.md`](../../02-installer/ru/acceptance/1/README.md), [`02-installer/acceptance/2/README.md`](../../02-installer/ru/acceptance/2/README.md), [`02-installer/acceptance/3/README.md`](../../02-installer/ru/acceptance/3/README.md), [`02-installer/acceptance/4/README.md`](../../02-installer/ru/acceptance/4/README.md), [`02-installer/acceptance/5/README.md`](../../02-installer/ru/acceptance/5/README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/data/alarms-retention.outcomes.tsv`](../../02-installer/data/alarms-retention.outcomes.tsv), [`02-installer/data/alarms-retention.schema.json`](../../02-installer/data/alarms-retention.schema.json), [`02-installer/data/canonical-row.outcomes.tsv`](../../02-installer/data/canonical-row.outcomes.tsv), [`02-installer/data/canonical-row.schema.json`](../../02-installer/data/canonical-row.schema.json), [`02-installer/data/manifest-file.outcomes.tsv`](../../02-installer/data/manifest-file.outcomes.tsv), [`02-installer/data/manifest-file.schema.json`](../../02-installer/data/manifest-file.schema.json) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/data/manifest-rev.outcomes.tsv`](../../02-installer/data/manifest-rev.outcomes.tsv), [`02-installer/data/manifest-rev.schema.json`](../../02-installer/data/manifest-rev.schema.json), [`02-installer/data/manifest-row.outcomes.tsv`](../../02-installer/data/manifest-row.outcomes.tsv), [`02-installer/data/manifest-row.schema.json`](../../02-installer/data/manifest-row.schema.json), [`02-installer/data/mirror.outcomes.tsv`](../../02-installer/data/mirror.outcomes.tsv), [`02-installer/data/mirror.schema.json`](../../02-installer/data/mirror.schema.json) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/data/retention.outcomes.tsv`](../../02-installer/data/retention.outcomes.tsv), [`02-installer/data/retention.schema.json`](../../02-installer/data/retention.schema.json), [`02-installer/data/space.outcomes.tsv`](../../02-installer/data/space.outcomes.tsv), [`02-installer/data/space.schema.json`](../../02-installer/data/space.schema.json) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/forms/README.md`](../../02-installer/ru/forms/README.md), [`02-installer/forms/daemon-flags.tsv`](../../02-installer/forms/daemon-flags.tsv), [`02-installer/forms/finite-profile.schema.json`](../../02-installer/forms/finite-profile.schema.json), [`02-installer/forms/operator-commands.tsv`](../../02-installer/forms/operator-commands.tsv), [`02-installer/forms/refusals.tsv`](../../02-installer/forms/refusals.tsv), [`02-installer/forms/rollout-poll.machine.yaml`](../../02-installer/forms/rollout-poll.machine.yaml) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/forms/stages.tsv`](../../02-installer/forms/stages.tsv), [`02-installer/forms/targets.tsv`](../../02-installer/forms/targets.tsv) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/spec/02-installer.README.md`](../../02-installer/ru/spec/02-installer.README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/spec/02.1-installer.layers.tsv`](../../02-installer/spec/02.1-installer.layers.tsv), [`02-installer/spec/02.1-installer.relations.json`](../../02-installer/spec/02.1-installer.relations.json), [`02-installer/spec/02.1-installer.scalars.tsv`](../../02-installer/spec/02.1-installer.scalars.tsv), [`02-installer/spec/02.1-installer.schema.json`](../../02-installer/spec/02.1-installer.schema.json), [`02-installer/spec/02.2-installer.norms.md`](../../02-installer/ru/spec/02.2-installer.norms.md), [`02-installer/spec/02.2-installer.view.schema.json`](../../02-installer/spec/02.2-installer.view.schema.json) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |
| [`02-installer/vectors/canonical/README.md`](../../02-installer/ru/vectors/canonical/README.md), [`02-installer/vectors/exec/README.md`](../../02-installer/ru/vectors/exec/README.md), [`02-installer/vectors/install-order/README.md`](../../02-installer/ru/vectors/install-order/README.md), [`02-installer/vectors/platform-lists/README.md`](../../02-installer/ru/vectors/platform-lists/README.md), [`02-installer/vectors/workers-script/README.md`](../../02-installer/ru/vectors/workers-script/README.md) | файлы целиком | Зависимости договоров предыдущих уроков: формы, схемы и публичные описания читаются целыми файлами. |

# Воркер (SDK) — урок P/03

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом.

Микромодуль: библиотека на каждом языке, роль <sub>worker. Что нормирует и откуда — записка модуля `Platform/module-design.md` (только для судьи: для человека), таблица «Lessons».

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

Эти общие файлы задают определения, на которые опираются главы, инструкция реализации, lifecycle и формы. Нормы глав остаются каноном; указатель не добавляет требований. Места вне M помечены «только для судьи». Данные векторов и случаи швов SDK не заменяют требования в M.

| Файл | Разделы и назначение |
|---|---|
| [Нормативные слова](../../common/ru/NORMATIVE-TERMS.md) | N0: сила MUST, SHOULD и MAY |
| [Клиент хранилища](../../common/ru/contracts/store-client.md) | Адрес, запрос, ответ и исходы — чтения SDK, CAS, стражи и неоднозначная запись |
| [Клиент объектов](../../common/ru/contracts/object-client.md) | Адрес, операции и исходы — чтение объектов единиц и мест без замены неответа отсутствием |
| [Наблюдение](../../common/ru/contracts/observation.md) | Наблюдение версии, свежесть, удержание места и свежесть метки претендента — часы читателя и возраст версии |
| [Слот](../../common/ru/contracts/slot.md) | Форма, состояния и сроки — общий смысл слота и состояний его отдачи |
| [Имя слота](../../common/ru/contracts/slot-name.md) | Грамматика, выбор «по имени», порядок слотов и следующее число — имена кандидатов и их порядок |
| [Instance](../../common/ru/contracts/instance.md) | Instance — идентификатор процесса и часть holder, которая называет коробку |
| [Замок присутствия](../../common/ru/contracts/presence-lock.md) | Замок и боевые обязательства — владение именем процесса, повторы inode, конечная отмена |
| [Метки](../../common/ru/contracts/labels.md) | Метка и список меток — алфавит входа и грамматика списка |
| [Файл окружения](../../common/ru/contracts/env-file.md) | Грамматика, файлы, порядок чтения и переменные — входы запуска, которые использует SDK |
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
| [Боевые обязательства](../../common/ru/contracts/production-obligations.md) | Конечные бюджеты, наблюдаемое завершение, публичная приёмка и недостающие привязки — боевая квалификация |
| [Каталог данных](../../common/data/catalog.tsv) | Файлы, ключи и читатели — разделы семей данных глав |
| [Кодек данных](../../common/data/codec.tsv) | Хранение значений семей — строковые поля строк и JSON-значения объектов |
| [Общая приёмка](../../common/ru/acceptance/README.md) | Стенд и словарь директив и дверей — общий стенд процессов и грамматика сценариев |
| [Профиль приёмки](../../common/ru/acceptance/PROFILE.md) | Команды, ключи, подстановки, команды векторов и имена проверок кода — реализация задаёт свой профиль |
| [Швы SDK](../../common/ru/acceptance/seams.md) | Порядок и владение peer, вход и наблюдение CALL, явный мост на стороне теста — нормализованные тестовые порты над настоящим SDK |
| [Стенд учебной подсистемы](../../common/ru/acceptance/testsub-stand.md) | Стенд процессов testsub — приёмка процесса с учебной подсистемой |
| [Приёмка pass](../../common/ru/acceptance/pass/README.md) | Подменный воркер прохода второго рода — граница подмены и настоящей двери воркера |
| [Приёмка TLS](../../common/ru/acceptance/tls/README.md) | Двери и клиенты пробы, исход и ожидания — проверки сертификата и цепочки |
| [Системная приёмка](../../common/ru/acceptance/system/README.md) | Стенд, сценарии и их границы — восстановление, потеря хоста и доменные зависимости |
| [Версии зависимостей](../../common/ru/versions/README.md) | Закреплённые модули — валидатор семей данных и прочие назначенные зависимости |
| [Протокол векторов](../../common/ru/vectors/wire.md) | Строки и источники, выбор входа и групп, сравнение и утверждения — назначенные общие пакеты |
| [Общие определения схем](../../common/data/common.schema.json) | `$defs` семей урока — общие формы скаляров и объектов |
| [Потребители векторов](../../common/vectors/consumers.tsv), [таблица wire](../../common/vectors/wire.tsv) | Назначенные общие пакеты потребителя `03-worker` и их привязки входа и выхода |
| [Векторы запечатывания](../../common/ru/vectors/sealing/README.md), [векторы токена двери](../../common/ru/vectors/door-token/README.md), [векторы токена домена](../../common/ru/vectors/domain-token/README.md) | только для судьи: определения пакетов и таблицы векторов; проверки P/03.5-R005 (открытие), P/03.4-R026 (токены двери) и P/03.7-R009 (токены домена) |

### Остальные внешние файлы и точные разделы

Файлы и разделы, на которые ссылается M урока. Пометка у закрытого файла называет проверяемое правило в M.

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
| `Platform/06-console/acceptance/1/README.md` | [файл](../../06-console/ru/acceptance/1/README.md) |
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
| `Platform/08-domain/acceptance/7/README.md` | [файл](../../08-domain/ru/acceptance/7/README.md) |
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
| `Platform/common/vectors/sealing/open.tsv` | [файл](../../common/vectors/sealing/open.tsv) (только для судьи: проверки P/03.5-R005) |
| `Platform/common/vectors/sealing/ring.tsv` | [файл](../../common/vectors/sealing/ring.tsv) (только для судьи: проверки P/03.5-R005) |
| `Platform/common/vectors/values-by-type/README.md` | [файл](../../common/ru/vectors/values-by-type/README.md) |

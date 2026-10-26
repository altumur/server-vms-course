# Консоль домена — жизненный цикл (урок P/10)

Контракт жизненного цикла процесса консоли домена `domainconsole` (ADR-0083 доп. (2) п. 1): запуск, настройка, диск, выход. Нормы —
[P/10](spec/10-domain-console.norms.md) (стадия B).

## Запуск

- Юнит `w2c-domainconsole.service`, роль `domainconsole`, раннер `w2c-run.sh domainconsole`, `W2C_ROLE=domainconsole`,
  `User=w2c`, группы `w2c-store w2c-events` (разбор ревью стадии A 8–10, № 33); кольца и группы `w2c-secrets` нет —
  [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md); общее юнитов — P/02.4 Н1.1 `common`
  ([P/02.4](../02-installer/spec/02.4-installer.norms.md)).
- У кластера-держателя, рядом с процессом `domain`. Строк держателя консоль не пишет: правки передаёт процессу
  `domain` ([P/10 Н1.3](spec/10-domain-console.norms.md) — передача; приём —
  [P/08.0 Н1.8](../08-domain/spec/08.0-domain.norms.md)); очередь `domain/signer-turn` ей не нужна
  ([P/08.10 Н1.7](../08-domain/spec/08.10-domain.norms.md) `guard`).
- При старте — сторона читателя строки манифеста и проверка схемы, готовность — порт ([P/10 Н1.1](spec/10-domain-console.norms.md),
  P/10-15; текст — P/02.4 Н1.12).

## Окружение

Канал настройки — только окружение P/02.4 Н1.2 и раскладка `PLATFORM_DIR` (второй пилот, Н-4).

| Переменная | Смысл | Умолчание | Норма |
|---|---|---|---|
| `W2C_ROLE` | роль `domainconsole` | юнит | P/02.4 Н1.2 |
| `PLATFORM_DIR`, `PLATFORM_STORE`, `OBJECTS`, `RESOURCE_ROOT` / `EVENTS` | состояние, дверь хранилища, корни объектов и событий (журнал роли пишется) | P/02.4 Н1.2 | P/02.4 Н1.2 «Канал настройки и раскладка» |
| `DOMAIN_CONSOLE_HOST`, `DOMAIN_CONSOLE_PORT` | дверь оператора домена; консоли членов пересылают сюда; TLS — по комплекту роли (P/02.4 Н1.6, [договор сертификата роли](../common/contracts/role-certificate.md) `kit`; ADR-0075 доп. 2026-10-26 (2) п. 4) | `0.0.0.0:8444` — только с комплектом | [P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md) |
| `SIGNER_URL` | дверь процесса `domain` своей коробки — передача правок | `http://localhost:8445` (стенд одной машины, как [жизненный цикл P/08](../08-domain/lifecycle.md); разбор ревью стадии A 8–10, № 33) | [P/10 Н1.3](spec/10-domain-console.norms.md) (передача; приём — P/08.0 Н1.8); [P/08.2 Н1.3](../08-domain/spec/08.2-domain.norms.md) |
| `LOGIN_URL` | вход людей, значение `login_url` в `/session` | `/api/login` | [договор сторожевой и передачи](../common/contracts/gate-and-pass.md) `session` `login_url`; [P/08.4 Н1.2](../08-domain/spec/08.4-domain.norms.md); P/02.4 Н1.2 |
| `W2C_TLS_DIR` | комплект роли `domainconsole` и свои `ca.pem`, `ca.next.pem` — объединение центров двери роли | P/02.4 Н1.6 | [P/10 Н1.4](spec/10-domain-console.norms.md) `roles`, `server.role`; [договор сертификата роли](../common/contracts/role-certificate.md) `kit` |
| `CLUSTER`, `BOX_ID`, `SERVER_NAME` | кластер, коробка, сервер | P/02.4 Н1.2 | P/02.4 Н1.2 |

## Флаги

Нет: канал настройки — только окружение (P/02.4 Н1.2).

## Каталоги и файлы

- Читает строки держателя (`domain/*` кроме `!domain/signer*`, P/02.5 Н1.4); своих строк не пишет; чтения — абзац
  «Данные» [P/10 Н1](spec/10-domain-console.norms.md) и каталог данных [`common/data/catalog.tsv`](../common/data/catalog.tsv),
  читатель `domainconsole`.
- Кольца нет ([P/02.4 Н1.12](../02-installer/spec/02.4-installer.norms.md)).
- Страница держателя — та же страница модуля консоли, `sections: [domain]` ([P/10 Н1.7](spec/10-domain-console.norms.md));
  поставка модуля — с бинарником консоли, не из `$CAMMETA_SPECS` ([P/06.5](../06-console/spec/06.5-console.norms.md) Н1.1 `module`).
- Журнал роли — `<корень событий>/audit/domainconsole/e1/…`, тревога `session.debug_open` — `audit.alarms/domainconsole`
  ([договор журнала событий](../common/contracts/event-journal.md) `journal`).

## Коды выхода

| Код | Когда | Норма |
|---|---|---|
| 2 | отказ старта по манифесту, правам, схеме — без перезапуска | P/02.4 Н1.1 `common`; P/10 Н1.1 |
| ≠ 0 | иной сбой; юнит перезапускает | P/02.4 Н1.1 |

## Сигналы и готовность

- Процесс `domain` своей коробки ждущий или недоступен — правки получают его ответ (`503 standby`) как есть
  ([P/08.10 Н1.7](../08-domain/spec/08.10-domain.norms.md) `standby`; [P/08.0 Н1.8](../08-domain/spec/08.0-domain.norms.md) `answers`);
  обрыв и молчание — 502 ([P/10 Н1.3](spec/10-domain-console.norms.md) `pass`).
- Готовность — порт, `sd_notify` нет ([P/10 Н1.1](spec/10-domain-console.norms.md)); перезапуск — по юниту (P/02.4 Н1.1 `common`).

## Стенд

Стенд нескольких кластеров ([общий README приёмки](../common/acceptance/README.md#стенд-домена), раздел «Стенд домена»): `@start domain` поднимает процессы `domain` и консоли домена на
`hold`; дверь `holder <запрос>` — консоль домена на `hold`, `holder@<кластер>` — на другом кластере после переноса;
`Idempotency-Key` у `POST`, `PUT`, `DELETE` — по правилу `@key`. `{data}` — `PLATFORM_DIR` кластера ([общий README
приёмки](../common/acceptance/README.md) «Стенд»; разбор ревью стадии B 3–5, № 33).

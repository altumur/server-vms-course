# Хранилище — жизненный цикл (урок P/01)

Контракт жизненного цикла процесса хранилища (ADR-0083 доп. (2) п. 1): запуск, настройка, файлы на диске, коды выхода,
сигналы. Стадия A — поверх нынешних норм М10. Нормы здесь не пересказываются: каждая строка ведёт к своей норме.

Нормы: [М10/11](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md) (Н1.1 юниты, Н1.2 окружение,
Н1.3 демон, Н1.4 отказ сервера, Н3 «старт сервера», Н4), [P/01.1](spec/01.1-store.norms.md) (дверь,
барьеры долговечности), [М10/6](../../М10_Platform/spec/06-rights.norms.md) (файл прав, сокеты ролей).

## Запуск

| Что | Как | Норма |
|---|---|---|
| демон группы | юнит `configstore.service`: `User=configstore`, `UMask=0077`, `-dir /data/platform/configstore`, `-sockets /run/configstore`, `-rights`, `-tls`, `-group-size`; раннер `w2c-run.sh configstore` | М10/11 Н1.1 `units` |
| сокеты | юниты `configstore-admin.socket` и `configstore-<роль>.socket`, `FileDescriptorName=admin \| <роль>`, `Service=configstore.service` | М10/11 Н1.1, Н1.3 `sockets` |
| первый старт и рестарт | есть `member.json` — рестарт, иначе `-bootstrap` (первый сервер) или `-join` (остальные) | М10/11 Н3 «старт сервера» шаг 1, Н1.3 `group.join` |
| хранилище коробки | сборка без raft, один голосующий (`box`) | P/01.3 Н1.3 `box` |
| хранилище в процессе | профиль `file://` «вся коробка — одна реализация», без двери; формат на диске не контракт | М10/11 Н1.2 `PLATFORM_STORE`, P/01.1 Н2 |

## Окружение

Настройку демона задают флаги (ниже): файл `configstore.env` читает раннер и собирает из него флаги. Сам демон читает
только окружение systemd — переданные сокеты (`LISTEN_FDS`, `LISTEN_FDNAMES`) и сторожа (`NOTIFY_SOCKET`): переданный
сокет флагом не заменить (P/01.3 Н1.3 `sockets`).
Порядок файлов окружения раннера — значения юнита → `roles/<W2C_ROLE>.env` → `w2c.env` → `configstore.env`
(М10/11 Н1.2; [02-installer/lifecycle.md](../02-installer/lifecycle.md)).

| Переменная | Смысл | Умолчание | Норма |
|---|---|---|---|
| `CONFIGSTORE_ID`, `_RAFT`, `_API`, `_GROUP_SIZE`, `_JOIN`, `_FLAGS`, `_TUNING` | флаги демона из `configstore.env`; читает раннер | `configstore.env` ставит `tuning` `lan`; умолчание самого флага `-tuning` — `default` | М10/11 Н1.2, Н1.3 «Флаги демона» |
| `SERVER_NAME` | умолчание `-id` вне группы | короткий hostname | М10/11 Н1.2, Н1.3 «Флаги демона» `-id` |
| `LISTEN_FDS`, `LISTEN_FDNAMES` | унаследованные сокеты (`sd_listen_fds`); читает сам демон | — | P/01.3 Н1.3 `sockets` |
| `NOTIFY_SOCKET` | сторож systemd | — | М10/11 Н1.2 |

## Флаги

Закрытая таблица «Флаги демона» — [P/01.3 Н1.3](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md):
`-dir` (обязателен), `-id`, `-sockets`, `-rights`, `-tls`, `-raft`, `-raft-bind`, `-api`, `-bootstrap`, `-join`,
`-group-size`, `-force`, `-door`, `-voters`, `-tuning`, `-leader-wait`, `-max-value`, `-max-body`, `-max-conns`,
`-api-conns`, `-api-per-address`, `-index-base`. Флаг вне таблицы — отказ старта, код 2. Административные команды —
`configstore status | join | leave | admit | backup | restore | import | recover | rights` (P/01.3 Н1.3 `admin_ops`,
Н1.9).

## Каталоги и файлы

| Путь | Что | Норма |
|---|---|---|
| `<PLATFORM_DIR>/configstore` (`-dir`) | каталог данных демона; формат на диске — решает реализация (P/01.1 «Решает реализация» п. 3) | М10/11 Н1.2 «Канал настройки и раскладка» |
| `<-dir>/FORMAT` | метка формата `{format, version, impl}`: пишется первой в пустой каталог; чужая или нет при непустом каталоге — отказ, код 2 | P/01.3 Н1.3 `format` |
| `<-dir>/member.json` | партнёры и `how` после вступления; рестарт — не вступление | P/01.3 Н1.3 `group.join` (путь внутри `-dir` — решает реализация) |
| `/run/configstore/admin.sock`, `/run/configstore/<роль>.sock` | плоско; унаследованные от юнитов `.socket`: `admin.sock` 0600, сокет роли 0660 с группой роли (`SocketGroup=`); сокет, которого не передали, демон создаёт сам в `-sockets`: `admin.sock` 0600, сокет роли 0660 с группой процесса | P/01.3 Н1.3 `sockets`, Н1.1 `dirs` |
| `/etc/w2c/configstore-rights.json` (`-rights`) | файл прав; без файла — только `admin.sock`; живой перезагрузки нет | P/01.2 Н1.2 |
| `/etc/w2c/tls` (`-tls`) | корень комплектов: внутри — комплект роли `configstore` или `configstore-door` | P/01.3 Н1.3 «Флаги демона» `-tls`, Н1.6 |
| файл копии (`backup <файл>`) | JSON Lines `copy`, 0600, tmp + rename, вне `-dir` | P/01.3 Н1.3 `copy`, `admin_ops`; вектор — `Platform/common/vectors/README.md` |
| строка `platform/configstore-doors/<id>` | пишет дверь без голоса раз в 30 с | [каталог](../common/data/catalog.tsv) |
| строка `platform/epoch_floor` | поднимается только `op: floor` на `admin.sock` лидера (`restore`, `import`, `recover`) | P/01.3 Н1.3 `floor`, [каталог](../common/data/catalog.tsv) |

## Коды выхода

| Код | Когда | Норма |
|---|---|---|
| 0 | упорядоченная остановка | — |
| 2 | отказ старта: нет `-dir`; нет `-id` в группе; флаг вне таблицы; `-max-value` или `-max-body` не > 0; чужая или пропавшая метка `FORMAT`; унаследованный сокет чужого имени; хранилище коробки с `-group-size 3`/`5` или `-join`; `recover` на коробке | P/01.3 Н1.3 `refuse_start`, Н4 |
| ≠ 0 | отказ старта без своего кода: `-bootstrap` с `-join`, размер не 1/3/5, адрес вне петли без `-tls`, сертификат двери у голосующего | М10/11 Н4 |
| ≠ 0 | административная команда отказана: `backup` внутрь `-dir`, повтор `import`, вход не по `copy`, часы раньше `generation_at` | М10/11 Н4 |

## Сигналы и готовность

| Что | Как | Норма |
|---|---|---|
| SIGTERM | остановка; `TimeoutStopSec` 20–30 | М10/11 Н1.1 |
| перезапуск | `Restart=always`, `RestartSec=2`, `RestartPreventExitStatus=2` | М10/11 Н1.1 `common` |
| готовность | сокет открыт; `After=configstore.service` у остальных — порядок, не готовность: каждый процесс сам ждёт достоверного чтения | М10/11 Н3 «старт сервера», «Гонки» |
| долговечность | барьеры не выключаются ни окружением, ни флагом эксплуатации | P/01.3 Н1.3 `durability`, P/01.1 «Решает реализация» п. 3 |
| отказ большинства | 503 `unavailable` через 5 с; восстановление — `recover` рукой | М10/11 Н1.4, Н3 «восстановить хранилище» |

## Стенд

«Стенд» — [README приёмки М10/01](../common/acceptance/README.md):
- команда хранилища получает `{data}` (`PLATFORM_DIR`, хранилище — `{data}/configstore`), `{socket}` (`admin.sock`,
  сокеты ролей рядом), `{rights}`, `{body_limit}` → `-max-body`, `{row_ceiling}` → `-max-value`; спек не кладёт;
- `{rights}`: в P/01.1 — файл роли `acc`, в уроках 4–11 — вывод прав из спек стенда командой вывода прав;
- директивы `@restart store`, `@foreign store`, `@backup store`, `@import store`, дверь `restored`;
- флаг стенда, выключающий барьеры ради скорости, реализация называет в своей команде «Стенда».

## Открыто

- Путь `member.json` внутри `-dir` и формат каталога данных — решает реализация (P/01.1 «Решает реализация» п. 3); между
  реализациями переносит только копия `copy`.
- Готовность демона — сокет: `sd_notify` он не шлёт, `Type=notify` — только у контроллера и воркера ([М10/11 Н1.1](../../М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md) `notify`; Решено «Архитектором» 2026-10-18 (второй пилот)).

# Урок 21 — Платформа на коробке

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `w2cplatform/host.py` — точку входа платформы, `python3 -m w2cplatform controller <sub> | resource | console`, и `stores`, которым каждый процесс открывает свои хранилища; в `deploy/` — юниты процессов платформы (шаблон `w2c-controller@.container`, `w2c-resource.container`, `w2c-console.container`), пользователя и каталоги платформы (`w2c.sysusers`, `w2c.tmpfiles`), её половину окружения (`w2c.env.example`), скрипт запасных `w2c-spares.sh` с его службами и таймерами; и платформенную половину `tests/test_deploy_units.py`.
**Время:** ~80 минут.

## Зачем этот урок

Двадцать уроков написали три процесса платформы — контроллер, ресурс и консоль — и ни разу не поставили их на машину. Тесты поднимали их внутри своего процесса, а «коробка» урока 1 была каталогом в `/tmp`. Этот урок ставит их на коробку из М9: одна машина, podman и systemd, A/B-корень под RAUC и раздел данных, который обновление не трогает.

Новых механизмов в уроке нет. Есть склейка, и в ней три утверждения, ради которых он написан.

**Коробка платформы не знает подсистемы.** Три юнита платформы называют подсистему только именем экземпляра (`w2c-controller@%i`) и словом развёртывания (`CONSOLE_ROOT`), а код за ними — `python3 -m w2cplatform` — работает от спек в `SPEC_DIR` и ни от чего больше. Подсистема ставит рядом свои юниты и не трогает этих: в М10B так встаёт VMS ([урок 17 М10B](../М10B_ServerVMS/17-on-the-box.md)).

**Процессы платформы работают от своего пользователя.** Это `w2c`: не root и не пользователь подсистемы (ADR 0023, ADR 0030). Кто пишет в каталоги служб платформы, тот её клиент, и клиентом его делает группа.

**Всё изменяемое — под одним корнем на разделе данных.** Состояние платформы лежит в `/data/platform`, конфигурация — в `/etc/w2c`, а это ссылка туда же. Обновление ОС не должно менять, членом какого хранилища является коробка.

> **Проверка без железа.** Тесты урока читают юниты как код, запускают скрипты в песочнице с подменёнными командами и поднимают точку входа платформы на `testsub` (`tests/test_host.py`). Настоящий запуск — коробка из М9 с podman; генератор Quadlet проверяет файлы на стенде (`deploy/check-quadlet.sh`).

## Что нужно знать заранее

- **Урок 1** — роли и коробка в `/tmp`: здесь та же раскладка, только на разделе данных.
- **Уроки 2, 3 и 20** — хранилище, его ACL, фабрика по схеме URL и файл прав `configstore`: здесь каждый процесс открывает хранилище своей ролью.
- **Урок 7** — слот и `runtime.py`: имя экземпляра systemd — предпочтение, слот в хранилище — доказательство.
- **Уроки 14, 15 и 16** — ресурс и консоль: здесь у каждого из них свой юнит.
- **Урок 17** — осушение и схема: что из этого работает, когда сервер один.
- **Урок 18** — ключ кластера: здесь он становится файлом с группой.
- **М9, урок 5** — A/B-корень и раздел данных.

## Чему вы научитесь

1. Запускать процессы платформы от каталога спек и отказывать без него — словами.
2. Давать каждому процессу его роль в хранилище, на коробке и в кластере одинаково.
3. Писать юнит Quadlet так, чтобы он читался сам по себе и проверялся тестом.
4. Запускать службу от своего пользователя, а её клиентов пускать по группе.
5. Держать состояние и конфигурацию на разделе данных и объяснять, почему `/etc/w2c` — ссылка.
6. Класть секрет файлом, видимым ровно тем, кому он нужен.
7. Запускать процессы с хоста по числу, а не по команде.
8. Обновлять коробку, на которой осушать не к кому.

---

## Шаг 1 — Точка входа: `python3 -m w2cplatform`

```python
USAGE = "python3 -m w2cplatform controller <sub> | resource | console   (SPEC_DIR: the directory of <sub>.subsystem.yaml)"


def main(argv: list[str], env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    if not env.get(catalog.SPEC_DIR):
        log.error("%s is not set: the platform runs from the specs it is given and from nothing else — %s",
                  catalog.SPEC_DIR, USAGE)
        return 2
    catalog.load_dir(env[catalog.SPEC_DIR])
    if argv[:1] == ["controller"] and len(argv) == 2:
        controller(argv[1], env)
        return 0
    if argv == ["resource"]:
        resource(env)
        return 0
    if argv == ["console"]:
        try:
            console(env)
        except ValueError as e:                          # what is at `/` the deployment did not say: said, not a trace
            log.error("%s", e)
            return 2
        return 0
    log.error("%s", USAGE)
    return 2
```

Три глагола, и ни один не называет подсистему. `controller <sub>` — это `SpecController` из урока 10, собранный по `<sub>.subsystem.yaml`. Своего контроллера у подсистемы нет, есть спека, которую она положила в каталог. `resource` — ресурс урока 14. Что держит отметка «сохранить», говорит `holds:` каждой спеки каталога, а не код подсистемы. `console` — консоль урока 15 над **всеми** спеками каталога: одна в корне, остальные под своими именами.

**Без `SPEC_DIR` не запускается ничего.** Процесс выходит с кодом 2 и говорит, чего ему не хватает. Каталог без единой спеки — отказ при старте (`catalog.load_dir`: `no <sub>.subsystem.yaml there`). Контроллер подсистемы, чьей спеки в каталоге нет, — тоже отказ. «Запустился и ничего не делает» — худший из возможных ответов: на коробке он выглядит как работающая система.

**Что лежит в корне консоли, решает развёртывание, а не платформа.** `CONSOLE_ROOT` называет спеку, которая встанет на `/`. Если такой спеки в каталоге нет, `build_console` бросает `ValueError` со списком того, что есть, а `main` превращает его в строку журнала и код 2 — не в трассу.

Сигналы ставит `__main__.py`, и только когда модуль запущен, а не импортирован тестом. SIGTERM и SIGINT поднимают флаг `host.stop`, и каждый цикл платформы его видит. Штатная остановка, которую урок 17 разбирал для воркера, у процессов платформы начинается здесь же.

Тест — платформы, без единого пакета подсистемы, на `tests/testdata/testsub.subsystem.yaml`:

```python
def test_the_platforms_entry_point_runs_from_the_specs_it_is_given_and_from_nothing_else():
    root = tempfile.mkdtemp(prefix="host-")
    assert host.main(["resource"], {"PLATFORM_DIR": root}) == 2
    try:
        host.main(["resource"], {"PLATFORM_DIR": root, "SPEC_DIR": tempfile.mkdtemp(prefix="empty-")})
        raise AssertionError("ran from a directory with no spec in it")
    except ValueError as e:
        assert "no <sub>.subsystem.yaml there" in str(e)
    assert host.main(["nonsense"], {"PLATFORM_DIR": root, "SPEC_DIR": TESTDATA}) == 2
    …
```

Рядом в `tests/test_host.py` — `test_the_platforms_resource_comes_up_heartbeats_and_says_its_tree_through_the_exported_readers`: ресурс, поднятый той же точкой входа, пишет heartbeat под именем из `SERVER_NAME` и закрывает свою дверь по `stop`.

## Шаг 2 — Хранилища процесса: `file://` на коробке, роль у каждого

```python
def stores(env: dict, writer: str | None = None, acl: list | None = None):
    from .objects import FsObjectStore
    from .variables import open_vars, store_url
    root = runtime.platform_dir(env)
    url = store_url(env, "file://" + os.path.join(root, "config"))
    vars_ = open_vars(url, writer=writer, acl={writer: acl} if writer else None) if writer else open_vars(url)
    if env.get("OBJECTS"):
        from .cluster.objectstore import open_store
        return vars_, open_store(env["OBJECTS"], vars_=vars_)    # the create-only keys: rows in THIS store, its rights
    return vars_, FsObjectStore(os.path.join(root, "objects"))
```

Одна функция на все процессы платформы и на воркеры подсистем: VMS открывает свои хранилища через неё же (`test_the_vms_processes_open_their_stores_through_the_platforms_one_function`).

**На коробке хранилище — файлы.** Если `PLATFORM_STORE` не задан, `store_url` даёт `file://<PLATFORM_DIR>/config`, то есть `FileVariables` урока 2. Объекты без `OBJECTS` — `FsObjectStore` под тем же корнем. Демона нет, сетевого перехода нет, кворума тоже нет: на одной машине им нечего защищать (ADR 0022). Реплицированное хранилище `configstore` на raft — форма кластера (ADR 0021), и коробка переходит в него один раз, импортом ([урок 2 М11](../М11_Cluster/02-the-store-becomes-replicated.md), шаг 2). Код процессов при этом не меняется: меняется одна строка URL.

**Роль у каждого процесса своя**, и она вырезана из спеки:

| Процесс | Писатель | Права |
|---|---|---|
| `controller <sub>` | `<sub>controller` | `spec.acl_controller()` — размещение, слоты, снимок |
| `console` | `console` | `acl_console()` каждой спеки каталога и ключи двери (`door/signer`, `door/keys`) |
| `resource` | — | на коробке без роли; в кластере роль `resource` |

На коробке роль проверяет сам клиент (`FileVariables.as_writer`, урок 2). Урок 20 сказал прямо, чего стоит такая проверка: это подсказка процессу, открывшему не то, а не защита от процесса, который её обходит. В кластере та же роль становится сокетом: `PLATFORM_STORE=configstore:///run/configstore/<role>.sock`, демон спрашивает файл прав раньше, чем что-нибудь применит, и пускает к сокету только группу роли ([урок 5 М11](../М11_Cluster/05-rights-by-who-is-calling.md)). Имена ролей при этом не меняются, а группы у процессов платформы — платформенные: `w2c-console`, `w2c-<sub>controller`, `w2c-resource` (ADR 0014, ADR 0030).

Тест, что консоль поднимает схему своими правами, а не правами тестового хранилища без ограничений, проверяет обе формы сразу: `test_host.py::test_the_console_raises_the_schema_through_its_own_grants_on_a_box_and_in_a_cluster`. Консоль, собранная `build_console`, пишет `platform/schema` через свой `console`, и та же строка есть в правах `console`, которые генератор выводит для кластера.

## Шаг 3 — Три юнита платформы

Quadlet делает из каждого файла `/etc/containers/systemd/<имя>.container` службу `<имя>.service`:

| Юнит | `Exec=` | Слушает | Пишет |
|---|---|---|---|
| `w2c-controller@.container` → `w2c-controller@vms`, `@rec`, … | `python3 -m w2cplatform controller %i` | ничего | размещение своей подсистемы и снимок; свой журнал в архиве событий |
| `w2c-resource.container` | `python3 -m w2cplatform resource` | `127.0.0.1:8090` | heartbeat, `platform/doors/<сервер>`, архив событий |
| `w2c-console.container` | `python3 -m w2cplatform console` | `0.0.0.0:8080` и `/run/w2c-console/console.sock` | строки оператора, отметки в архиве событий |

Шаблон контроллеров целиком:

```ini
[Unit]
Description=w2c controller — the only writer of placement of %i
After=network.target

[Container]
Image=localhost/vmsserver:latest
Exec=python3 -m w2cplatform controller %i
User=2100
Group=2100
EnvironmentFile=/etc/w2c/w2c.env
EnvironmentFile=/etc/vms/vms.env
Volume=/data/platform/config:/data/platform/config:z
Volume=/data/platform/objects:/data/platform/objects:z
GroupAdd=2103
PodmanArgs=--umask=0007
Volume=/data/platform/events:/data/platform/events:z
GroupAdd=2102
Network=host

[Service]
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

**Имя экземпляра — имя спеки.** `systemctl start w2c-controller@vms` запускает контроллер спеки `vms.subsystem.yaml` из `SPEC_DIR` образа. Подсистема, которая добавит спеку, получит контроллер ещё одним экземпляром того же шаблона, и ни одного нового файла в `deploy/` для этого не понадобится. Контроллера с именем подсистемы среди юнитов нет ни одного, и тест это держит:

```python
    platform = {"w2c-controller@.container": "%i"}
    …
    assert not [n for n in os.listdir(DEPLOY) if n.endswith("controller.container")]   # no controller of a subsystem's name
```

**Контроллер — вычисление, а не состояние.** Порта у него нет: ему никто ничего не говорит, он читает хранилище и пишет в него. Перезапускать его можно когда угодно. Два экземпляра над одним хранилищем безвредны, потому что каждая запись — CAS урока 8 (`test_lesson6_controller.py::test_two_controllers_agree_by_cas`). Перезапуск, который на секунду наложился на старый экземпляр, замка не требует. Архив событий контроллер монтирует ради одного — своего журнала: какой слот он освободил и почему, `units.left_on_leaving` (`host.controller_loop` пишет его туда, куда указывает `RESOURCE_ROOT` из `w2c.env`). Пишет он туда как любой клиент архива, членом `w2c-events`, а не хозяином, и бакеты удаляет только ресурс. Тест держит обе половины: «ACL говорит, какие строки пишет токен, а монтирование — какие байты»:

```python
    assert vols("w2c-controller@.container")[EVENTS] == f"{EVENTS}:z" and "2102" in groups("w2c-controller@.container")
    assert "RESOURCE_ROOT=" in open(os.path.join(DEPLOY, "w2c.env.example")).read()     # …which the unit's env file says
```

(`test_deploy_units.py::test_who_may_write_where_is_in_the_mounts_too`.)

**Ресурс — процесс, а не таймер.** Шапка его юнита называет, что он заменил: *the policy pass now runs every 600 s from the process's loop, and a oneshot could not hold a heartbeat.* Разовая задача раз в десять минут давала тот же проход, но у неё не было трёх вещей: heartbeat'а (между запусками её не видно), порта (к ней нельзя обратиться) и индекса событий с его кэшем (ему негде жить). Тест держит `Restart=always` с комментарием *a process, not a timer*. Индекс при этом ничего своего не хранит (урок 13), и перезапуск теряет только кэш. `RESOURCE_HOST=127.0.0.1`: на одной коробке к ресурсу обращается только консоль. В кластере он слушает адрес сервера, потому что соседи присылают туда зеркала.

**Консоль — на порту и на сокете.** `CONSOLE_HOST=0.0.0.0`, `CONSOLE_PORT=8080`: страницу открывают с машины оператора, обычным HTTP, и консоль говорит об этом в журнале при каждом старте. С прокси перед ней сюда ставят `127.0.0.1`. Второй вход — сокет `CONSOLE_UNIX=/run/w2c-console/console.sock`, дверь самой коробки: через него идут аварийный вход и собственные соединения на случай, когда порт залит. Кто «на коробке», определяет режим каталога, а не адрес: `0700 w2c` (шаг 5), то есть root и процессы платформы. Корень консоли — `Environment=CONSOLE_ROOT=vms`. Тест `test_the_console_unit_builds_the_vms_at_its_root_and_every_other_spec_under_its_name` собирает консоль по этому окружению и спекам образа и проверяет, что остальные спеки встали под своими именами. Ничего своего консоль не держит: ключи идемпотентности лежат в хранилище, и повтор, попавший в перезапущенный экземпляр, получает тот же ответ.

Имя файла консоли на коробке — `w2c-console.container`, служба — `w2c-console.service`: то же имя, что у этого процесса в кластере (ADR 0023).

**Что в этих трёх файлах называет VMS.** Три слова, и все три — развёртывания, а не кода. `Image=localhost/vmsserver:latest`: коробка ставит один образ, и в нём спеки VMS (`SPEC_DIR=/app/vms`). `CONSOLE_ROOT=vms`: что стоит на `/`, решает развёртывание. `EnvironmentFile=/etc/vms/vms.env`: каждый юнит коробки читает обе половины окружения (шаг 7). Положите в образ спеку `counter` из урока 9 — и те же три файла поднимут её: поменяются имя экземпляра и `CONSOLE_ROOT`, и ничего больше.

## Шаг 4 — Пользователь `w2c` и группы его клиентов

```
u w2c          2100     "w2c platform (the resource)" /data/platform -
g w2c-events   2102     -
g w2c-store    2103     -
g w2c-secrets  2104     -
m w2c          w2c-events
m w2c          w2c-store
```

`deploy/w2c.sysusers` ставится в `/etc/sysusers.d/w2c.conf` и применяется `systemd-sysusers`. Пользователь платформы — `w2c`, его домашний каталог — корень состояния. У него три группы клиентов, по одной на службу:

- **`w2c-events`** — архив событий, `/data/platform/events`. Он принадлежит `w2c`, а бакеты в нём удаляет, зеркалит и восстанавливает только ресурс. Кто пишет туда свои бакеты, входит в группу.
- **`w2c-store`** — два файловых хранилища, `config/` и `objects/`. Их открывает каждый процесс.
- **`w2c-secrets`** — ключ кластера (шаг 6). В неё входят только процессы, которые печатают или открывают секрет.

**Процесс платформы никогда не работает от пользователя подсистемы и не состоит в её группах** (ADR 0030). Права процесса платформы не должны зависеть от того, какие подсистемы стоят на сервере (ADR 0001), и подсистема не должна получать доступ к файлам платформы через общую группу. Исключение одно — группа сокета движка, который процесс читает по спеке, — и ключа спеки, который называл бы такой сокет, сегодня нет. Значит, нет и исключения.

**Номера фиксированы, все четыре.** Процессы коробки работают в контейнерах, а у контейнера нет `/etc/passwd` и `/etc/group` хоста: юнит говорит `User=2100` и `GroupAdd=2102` числами. Имя, созданное раньше с другим номером, означало бы ресурс, который не может удалить написанное клиентами. Поэтому установщик коробки, увидев такое, останавливается и называет имя и номер (шаг 5).

**Маска — аргументом podman.** `PodmanArgs=--umask=0007` стоит в каждом юните коробки. Ключа для маски у Quadlet нет, а `UMask=` в `[Service]` задал бы маску самому podman, а не процессу в контейнере. С маской 0007 в каталогах с setgid всё, что создаёт клиент, принадлежит группе каталога и открыто ей на запись: файлы 0660, каталоги 2770.

Строки юнитов держит один тест:

```python
def test_the_platforms_processes_run_as_w2c_and_every_writer_is_a_client_of_its_group():
    …
        assert vols.get(CONFIG) == f"{CONFIG}:z" and vols.get(OBJECTS) == f"{OBJECTS}:z" and W2C_STORE in groups, n
        assert "--umask=0007" in _list(c.get("PodmanArgs")), n
        platform = n in ("w2c-resource.container", "w2c-console.container", "w2c-controller@.container")
        assert (EVENTS in vols and n != "w2c-console.container") == (W2C_EVENTS in groups), n
        …
        assert ("User" in c) == platform, n
        if platform:
            assert (c["User"], c["Group"]) == (W2C, W2C), n
    …
    r = unit("w2c-resource.container")["Container"]
    assert (r["User"], r["Group"]) == (W2C, W2C) and W2C_SECRETS not in _list(r.get("GroupAdd"))   # it opens no secret
```

Три процесса платформы — `User=2100`, `Group=2100`, и это единственные контейнеры коробки, где пользователь назван: процессы подсистемы в своих контейнерах работают от root. Каждый юнит входит в `w2c-store` с маской 0007. В `w2c-events` входят ровно те, кто монтирует архив событий, кроме консоли: ресурс, который там удаляет, контроллер, чей журнал ложится в общий каталог `audit/`, и клиенты подсистем, пишущие бакеты. Консоль — нет: её отметки ложатся в архив, хозяин которого — её собственный пользователь. Ресурс не входит в `w2c-secrets`: секретов он не открывает.

**Права проверены так, как их проверило бы ядро.** Второго uid без root в тесте нет, поэтому `test_the_resource_as_w2c_deletes_a_bucket_a_client_of_w2c_events_wrote` проверяет режимы для процесса **другого** uid, связанного с деревом только группой. Клиент пишет бакеты под маской 0007 в дерево 2770 этой группы. Каждый созданный им каталог — группы и с `rwx` для неё (на Linux ещё и setgid), каждый файл — с `rw`. Проход хранения ресурса удаляет старый бакет. А под маской 0022 та же проверка говорит, что удалить он бы не смог: маска — половина правила.

С хранилищами так же, и здесь нашлась одна неправда библиотеки. `FsObjectStore` писал объект через `tempfile.mkstemp`, а тот создаёт файл 0600 при любой маске — heartbeat, который другой uid той же группы не прочтёт. Теперь файл в полёте создаётся под маской процесса (`events.new_temp`, `O_EXCL`), как всегда создавались строки. Тест `test_a_platform_stores_files_are_its_groups_under_the_units_umask`: под маской 0007 объект, метка «только создать», строка, замок и счётчик — все 0660, и в полёте не осталось ничего.

## Шаг 5 — `/data/platform` и ссылка `/etc/w2c`

```python
DATA = "/data/platform"                          # PLATFORM_DIR unset
ETC = "/etc/w2c"                                 # → /data/platform/etc: w2c.env, configstore-rights.json, tls/, secrets/
KEY_FILE = ETC + "/secrets/platform.key"         # the cluster's key ring (`sealing.py`): 0640, group `w2c-secrets`


def platform_dir(env: dict) -> str:
    return env.get(PLATFORM_DIR) or DATA


def events_root(env: dict, given: str | None = None) -> str:
    return given or events_said(env) or os.path.join(platform_dir(env), "events")
```

Раскладка платформы в `w2cplatform/runtime.py`, и каждое умолчание сказано один раз. Архив событий спрашивают у одной функции, `events_root`: ресурс, консоль для своих отметок и каждый писатель бакетов, воркеры подсистем тоже. Двух умолчаний, которые развели бы архив коробки по двум местам, нет. Свои пути подсистема держит в своём коде (`/data/<sub>/…`, `/etc/<sub>`).

Каталоги делает `deploy/w2c.tmpfiles` → `/etc/tmpfiles.d/w2c.conf`, при каждой загрузке, кто бы ни стартовал первым:

```
d /data/platform              0755 root root        -
d /data/platform/etc          0755 root root        -
d /data/platform/etc/secrets  2710 root w2c-secrets -
d /data/platform/config       2770 w2c  w2c-store   -
d /data/platform/objects      2770 w2c  w2c-store   -
d /data/platform/events       2770 w2c  w2c-events  -
d /run/w2c-console            0700 w2c  w2c         -
```

**Всё изменяемое — под одним корнем** (ADR 0023): хранилище строк, объекты, архив событий, а в кластере ещё журнал `configstore/`. Корень принадлежит root, и пишут в нём только каталоги ниже. `/run/w2c-console` — сокет консоли, процесса платформы (ADR 0014), поэтому каталог лежит здесь. Свой каталог, а не `/run/vms`: тот целиком монтируется в контейнеры процессов VMS, а дверь консоли не им открывать.

**`/etc/w2c` — ссылка в `/data/platform/etc`.** На A/B-коробке `/etc` лежит в слоте корня, который обновление ОС заменяет целиком (М9, урок 5). Файл в `/etc`, переживший одно обновление, при следующем переключении слота заменится файлом нового образа. А в `/etc/w2c` лежит то, что делает эту коробку этой коробкой: `w2c.env`, ключ, а в кластере ещё файл прав хранилища и `tls/`. Поэтому сами файлы — на разделе данных, а юниты и код называют `/etc/w2c/…` и никогда не называют цель ссылки. Ссылку на A/B-коробке продукта кладёт образ, на обычном сервере — установщик.

На коробке курса установщик один — `deploy/install-obsd.sh`. Он общий с движком архива VMS: у платформы своего установщика на коробке нет (у продукта это его `install.sh`). Для платформы скрипт делает четыре вещи. Ставит и применяет `w2c.sysusers` и `w2c.tmpfiles`. Проверяет номера и отказывается, если `w2c` или одна из групп уже есть с другим номером. Кладёт ссылку `link_etc "$R/etc/w2c" "$R/data/platform/etc"`, предварительно перенеся настоящий каталог `/etc/w2c` под `/data`, ничего не удаляя. И один раз отдаёт содержимое хранилищ группе `w2c-store`, архива событий — группе `w2c-events`, ключ — 0640 `w2c-secrets`. Остальное при каждой загрузке делает systemd. Тест запускает скрипт в песочнице (`INSTALL_ROOT`) и проверяет ссылки, каждый файл и повторный запуск, после которого ничего не двигается: `test_install_obsd_moves_the_old_layout_into_data_and_links_etc_deleting_nothing`.

**Ни один юнит не монтирует корень целиком.** Только `config/`, `objects/` и, кому нужно, `events/`:

```python
            # the two stores, never /data/platform whole: its etc/secrets holds the key ring
            assert "/data/platform" not in vols(n) and not any(v.startswith("/data/platform/etc") for v in vols(n)), n
```

Корень целиком дал бы каждому контейнеру `etc/secrets/platform.key`. Процессы подсистем в своих контейнерах могут быть root, и права на файл их не остановят.

Что каждый пользователь, группа и каталог, которые называет юнит, создаётся файлами установки, держит `test_every_user_group_and_directory_a_unit_names_is_made_by_the_install_files`. Его платформенная половина — словарь `w2c.tmpfiles`, строка в строку как выше, и номера `w2c.sysusers`:

```python
    assert (users["w2c"], groups["w2c"], groups["w2c-events"], groups["w2c-store"], groups["w2c-secrets"]) == \
        (W2C, W2C, W2C_EVENTS, W2C_STORE, W2C_SECRETS)
```

## Шаг 6 — `platform.key`

Ключ кластера из урока 18 — не значение в файле окружения, а файл: `/etc/w2c/secrets/platform.key`, 0640, группа `w2c-secrets` (ADR 0023). Его пишет только root при установке, потому что ни один работающий процесс его не пишет:

```bash
python3 -m w2cplatform.sealing new /etc/w2c/secrets/platform.key
```

`sealing new` отказывается класть ключ внутрь хранилища (`config/`, `objects/`, `configstore/`): ключ, который копируется с каждой копией хранилища, — уже не ключ (урок 18).

**Каталог `secrets/` — 2710 `root:w2c-secrets`.** Член группы проходит к файлу, путь которого ему назвали, но не видит, что ещё лежит в каталоге: `x` без `r`. Setgid даёт новому ключу группу каталога без отдельного `chgrp`.

**На коробке ключ монтируется одним файлом**, и только в юниты, которые открывают запечатанные поля. Из процессов платформы это консоль — она печатает:

```ini
Volume=/etc/w2c/secrets/platform.key:/run/secrets/platform.key:ro,z
GroupAdd=2104
Environment=SECRETS_KEY=/run/secrets/platform.key
```

Остальные юниты, которым нужен ключ, — воркеры подсистемы, открывающие секрет. Кто они, решает подсистема: у VMS это держатель камеры и регистратор ([урок 17 М10B](../М10B_ServerVMS/17-on-the-box.md)). Тест перечисляет их всех и требует у каждого и монтирование, и группу:

```python
    keyed = {n for n in os.listdir(DEPLOY) if n.endswith(".container")
             and "SECRETS_KEY=/run/secrets/platform.key" in unit(n)["Container"].get("Environment", [])}
    assert keyed == {"w2c-console.container", "vmsworker@.container", "recworker@.container"}, keyed
    for n in keyed:
        assert f"{KEY}:/run/secrets/platform.key:ro,z" in unit(n)["Container"]["Volume"], n
        assert W2C_SECRETS in _list(unit(n)["Container"]["GroupAdd"]), n                 # 0640, its group: the clients of the key
```

**В кластере ключ — учётные данные systemd.** Юниты М11 не контейнеры, и монтировать нечего. Консоль получает ключ так:

```ini
LoadCredential=platform.key:/etc/w2c/secrets/platform.key
Environment=SECRETS_KEY=%d/platform.key
```

systemd читает файл от root и кладёт копию в каталог учётных данных службы (`%d`), который видит только этот процесс. Группа `w2c-secrets` у юнита при этом остаётся, и тест М11 проверяет, что она стоит ровно там, где стоит `LoadCredential`. Интерфейс процесса одинаков в обоих местах — `SECRETS_KEY=<путь>`. Код не знает, смонтирован файл или выдан systemd.

## Шаг 7 — `w2c.env`: половина платформы

```
PLATFORM_DIR=/data/platform
RESOURCE_ROOT=/data/platform/events
# PLATFORM_STORE=file:///data/platform/config
# SERVER_NAME=
# LABELS=
# BOX_ID=
# the spares' script: where the console answers, and how many spares of each role this server may run
# CONSOLE=http://127.0.0.1:8080
# MAX_RECORDERS=8
…
```

Окружение коробки — два файла. `/etc/w2c/w2c.env` — то, что процессу нужно, чтобы быть членом платформы: где её состояние, где архив событий, какое хранилище, кто этот сервер, что он достаёт (`LABELS`), какая это машина (`BOX_ID`). Этот файл не меняется, когда на коробку добавляют подсистему. Настройки подсистем — в её файле (у VMS — `/etc/vms/vms.env`). Каждый юнит называет оба, платформу первой:

```ini
EnvironmentFile=/etc/w2c/w2c.env
EnvironmentFile=/etc/vms/vms.env
```

Имя, заданное в обоих файлах, берётся из второго. Поэтому каждое имя должно жить в своей половине и только там: `PLATFORM_DIR`, попавший в файл подсистемы, молча переопределил бы платформу. Тест:

```python
    platform, vms = _env_names("w2c.env.example"), _env_names("vms.env.example")
    assert {"PLATFORM_DIR", "RESOURCE_ROOT", "PLATFORM_STORE", "SERVER_NAME", "LABELS", "BOX_ID"} <= platform
    …
    assert not platform & vms, platform & vms
```

На коробке `SERVER_NAME`, `LABELS` и `BOX_ID` закомментированы. Имя хоста и есть сервер, меток нет, а имена, которые `runtime.py` раздаёт процессам (урок 7), берут умолчания. Чего в этом файле нет: имени слота — оно в юните (`WORKER_NAME=%i`), потому что это настройка экземпляра, а не коробки; ключа — он файлом (шаг 6); адреса и порта консоли — они в её юните. Настройка коробки — в файле окружения, настройка экземпляра — в юните.

## Шаг 8 — Скрипт запасных и его таймер

Шаблон отвечает на вопрос «как запустить ещё одного воркера», но не на вопрос «кто заметит, что он нужен». Контроллер знает, скольких воркеров не хватает, и публикует число на странице метрик консоли — `<sub>_workers_needed{labels="…"}`. Запустить процесс он не может, и консоль тоже: процесс, который умеет говорить с systemd, — это процесс с правом запускать что угодно на своей машине. «Платформа не запускает процессов» стало бы предложением с исключением.

Запускает скрипт на хосте, который оператор поставил нарочно, по таймеру:

```ini
# w2c-spares.timer
[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=30s

# w2c-spares.service
[Service]
Type=oneshot
User=w2c
Group=w2c
ExecStart=/usr/local/bin/w2c-spares.sh recworker
EnvironmentFile=-/etc/w2c/w2c.env
EnvironmentFile=-/etc/vms/vms.env
ProtectSystem=strict
…
RuntimeDirectory=w2c-spares
```

Скрипт и таймеры — платформы, поэтому `w2c-spares*`. Работают они от `w2c` (ADR 0030), без единой дополнительной группы. На каждую роль, для которой развёртывание держит запасных, — своя пара `w2c-spares[-<роль>].{service,timer}`.

Три правила скрипта, и все общие.

**Он берёт число, а не команду.** Выполнять на хосте строку, пришедшую по HTTP, — удалённое исполнение кода с лишними шагами, каким бы дружественным ни был источник. Скрипт читает со страницы `…_workers_needed` и решает сам.

**Молчащая консоль — повод не запускать ничего.**

```sh
    text=$(curl -fsS --max-time 5 "$CONSOLE$page" 2>/dev/null) || {
        echo "$ME: no answer from $CONSOLE$page — nothing started for $role" >&2
        continue                                    # the console being down is not a reason to start anything
    }
```

Числа нет и тогда, когда проход контроллера устарел: страница его не показывает, и скрипт говорит `says no number … nothing started`.

**У него свой потолок.** `MAX_*` на роль, и уже работающие запасные считаются против него. Ошибка на той стороне, сообщившая «не хватает девятисот», обязана стоить строки в журнале, а не девятисот процессов. И скрипт ничего не останавливает: решение, что запасных слишком много, — человеческое.

**Запасной запускается только как юнит своей роли.** Это шаблон `<sub>-<роль>-spare@.service`, строка в строку юнит роли без имени, с тем же пользователем, группами и ключом. Шаблона нет — скрипт не запускает ничего и говорит почему:

```sh
    if ! template "$role"; then
        echo "$ME: no spare template for $role on $SERVER ($NAME-$role-spare@.service, or com.w2c.$NAME.$role.plist on macOS) — nothing started: a spare runs as its role's unit or not at all" >&2
        continue
    fi
```

Polkit разрешает `w2c` ровно одно действие — `systemctl start` экземпляра шаблона запасных: ни `stop`, ни другого юнита, ни `reset-failed`. Это правило ставит кластер М11 (`w2c-spares.rules`, [урок 4 М11](../М11_Cluster/04-a-name-is-a-slot.md), шаг 5), там же лежат шаблоны запасных. **На коробке шаблонов запасных нет**, и скрипт там только говорит число и почему ничего не запустил. Запускает оператор, по тому же числу, экземпляром шаблона роли. Механизмов три — рука, этот таймер и автоскейлер там, где он есть, — и в одной установке работает ровно один: два агента с мнением об одном числе дерутся.

Тесты запускают скрипт с подменёнными `curl` и `systemctl`: `test_the_spares_script_starts_spares_for_the_sets_its_server_covers_up_to_its_ceiling_and_stops_nothing`, `test_a_spare_systemd_refuses_to_start_is_said_and_the_next_number_is_tried`, `test_the_spares_script_takes_the_hosts_labels_without_a_console_row_and_starts_nothing_on_a_silent_or_stale_console`, `test_a_spare_is_started_only_as_its_roles_unit_and_never_as_root_without_one`. Строки юнитов держит `test_every_spares_unit_runs_the_script_for_its_role`: каждая служба — `oneshot` от `w2c` без `SupplementaryGroups`, каждый таймер — раз в минуту.

**Долг границы, и он открыт.** Таблица ролей в самом скрипте называет роли VMS и страницы их метрик (`recworker` → `/rec/metrics`, `vmsworker` → `/metrics`, …) и префикс `NAME=vms`. Это скрипт платформы, который знает подсистему по имени, а не по спеке. Правильная форма — роли из спек каталога: страница и префикс у каждой спеки свои, `<sub>_workers_needed`. Сегодня этого нет, и тест границы долга не видит: он читает `w2cplatform/`, а скрипт лежит в `deploy/`.

## Шаг 9 — Осушение и обновление на одной коробке

Урок 17 научил обновлять кластер по одной машине: `POST /drain?server=…`, ждать `safe`, гасить. На коробке машина одна, и осушать её не к кому.

Платформа отвечает на это правдой, а не тишиной. `POST /drain` на единственный сервер пишет строку, `_pool` выкидывает воркеров этого сервера, `leaving` называет причину — и `redistribute` не находит, куда увести ни одной единицы:

```python
                if best is None:
                    # THIS unit (or group) waits, listed where it was — and the next one is looked at: …
                    self.last_leaving_waiting += max(1, len(group))
                    …
                        log.warning("%s: %s stay on %s (%s): no live worker takes %s — moved when one does, asked again "
                                    "every pass", self.sub.name, what, gone, why, "all of them" if len(group) > 1 else "it")
                        …
                        self.journal.say("units.left_on_leaving", ALARM, sub=self.sub.name, unit=str(uid), …
```

Единицы остаются на своих воркерах, и работа не останавливается. Но `GET /drain` говорит `would_strand` по каждой единице каждой подсистемы, и `safe` не наступит никогда. Контроллер один раз за серию скажет о каждой единице в журнал процесса (`journalctl -u w2c-controller@<sub>`: `… stay on … no live worker takes it`) и поднимет тревогу `units.left_on_leaving`. Новая единица, созданная в это время, неразмещаема: пул пуст. Поэтому на коробке осушение не зовут. Обновление коробки — плановый перерыв, и платформа делает его коротким и чистым.

Тревога ложится туда же, куда весь журнал контроллера (`Journal`): в архив событий, который назвал `RESOURCE_ROOT` и который юнит контроллера монтирует (шаг 3). Её видит таймлайн консоли, а строку `log.warning` — `journalctl`.

```bash
podman build -f deploy/Containerfile -t localhost/vmsserver:latest .    # из Source/: один образ на всю коробку
systemctl daemon-reload                                                  # если поменялись файлы юнитов
systemctl restart w2c-controller@vms w2c-controller@rec w2c-console w2c-resource
systemctl restart <юниты подсистем>                                      # урок 17 М10B
curl localhost:8080/schema                                               # can_raise_to: что понимает каждый живой процесс
curl -X PUT 'localhost:8080/schema?version=2'                            # только если новая сборка подняла SCHEMA
```

Маршруты консоли за воротами (урок 15): `GET /schema` — с токеном просмотра, `PUT` — с токеном администратора; заголовки здесь опущены.

Каждый перезапуск — служба Quadlet, которая создаёт контейнер из образа под тем же тегом, то есть из нового образа. И каждый процесс платформы переживает его без потерь, по причинам, которые модуль уже написал. Контроллер — вычисление без состояния (шаг 3). Ресурс теряет только кэш индекса. Консоль ничего не держит: ключи идемпотентности в хранилище. Воркер останавливается штатно: SIGTERM, `StopTimeout` его юнита, последний heartbeat, `release_slot` с пометкой `released` (урок 17, шаг 5). Перезапущенный экземпляр берёт тот же слот по имени из юнита, потому что systemd — авторитет по вопросу, кто сейчас `w-1` (урок 7). Контроллеру при этом некуда и незачем переразмещать: слот отпущен и сразу взят тем же именем.

**Схема и на коробке поднимается последней.** Новый процесс против старого хранилища — норма, старый против нового — отказ (урок 17, шаг 6). На коробке все процессы перезапускаются из одного образа, и смешанных сборок почти не бывает. Почти — потому что процесс, который вы забыли перезапустить, остаётся старым. `GET /schema` перечисляет каждый процесс с его схемой и сборкой (`builds`), и `PUT` откажет с именами отстающих (`still running: …`). Подъём — отдельный шаг оператора: необратимый, он остаётся в журнале строкой `schema.raised`. Строку `platform/schema` пишет только роль `console` (шаг 2).

Чего на коробке нет и не будет: работы без перерыва во время обновления. Это свойство второй машины, а не платформы, и о нём [М11](../М11_Cluster/README.md).

## Результат

```bash
deploy/install-obsd.sh                                       # w2c (2100) и группы клиентов, /data/platform, /etc/w2c → /data/platform/etc
python3 -m w2cplatform.sealing new /etc/w2c/secrets/platform.key   # из Source/, root: 0640, группа от каталога
podman build -f deploy/Containerfile -t localhost/vmsserver:latest .
cp deploy/w2c-controller@.container deploy/w2c-resource.container deploy/w2c-console.container /etc/containers/systemd/
systemctl daemon-reload
systemctl start w2c-resource w2c-console w2c-controller@vms w2c-controller@rec
```

Юниты Quadlet не включают через `systemctl enable`: их `[Install]` читает генератор Quadlet при `daemon-reload`. Экземпляр шаблона на загрузку ставят ссылкой рядом с шаблоном, `w2c-controller@vms.container` → `w2c-controller@.container` (podman-systemd.unit(5)).

```bash
systemctl status w2c-resource w2c-console 'w2c-controller@*'    # три процесса платформы, все от w2c
ls -l /etc/w2c                                              # ссылка в /data/platform/etc
stat -c '%a %U:%G' /data/platform/{config,objects,events}   # 2770 w2c:w2c-store, w2c:w2c-store, w2c:w2c-events
curl localhost:8080/schema                                  # с токеном просмотра: кто запущен, какая схема, до чего можно поднять
```

Воркеров пока нет — ставить их будет подсистема, — и контроллеру некого размещать. Платформа при этом работает: ресурс бьётся, консоль показывает спеки, контроллеры проходят каждые пять секунд по пустому пулу.

## Что может пойти не так

| Симптом | Скорее всего |
|---|---|
| Процесс платформы перезапускается каждые две секунды, в журнале `SPEC_DIR is not set` | Образ без `SPEC_DIR` или юнит, который его переопределил пустым. Платформа работает от спек и ни от чего больше. |
| Консоль выходит с кодом 2 сразу после старта | `CONSOLE_ROOT` называет спеку, которой нет в каталоге; журнал перечисляет, какие есть. |
| Хранение молча перестало удалять бакеты | Клиент архива пишет с маской 0022: его каталоги 2755, и ресурс (`w2c`) из них не удалит. Маска — `PodmanArgs=--umask=0007`, не `UMask=` в `[Service]`. |
| Ресурс не читает heartbeat'ы воркеров | Файл объекта 0600: написан мимо `new_temp`, или юнит не входит в `w2c-store`. |
| Контейнер не открывает хранилище, хотя группа «та же» | Группа создана с другим номером. `install-obsd.sh` останавливается и называет имя и номер. |
| После обновления ОС коробка «забыла» хранилище и ключ | `/etc/w2c` — настоящий каталог в слоте корня, а не ссылка в `/data/platform/etc`. |
| Ключ виден каждому контейнеру | Юнит монтирует `/data/platform` целиком, и с ним `etc/secrets`. Монтируются `config/`, `objects/`, `events/` — по одному. |
| Ключ в `w2c.env` значением | Этот файл читает каждый юнит. Ключ — файлом, в три юнита. |
| Процесс платформы читает файлы подсистемы | Юнит платформы с её пользователем или в её группе. ADR 0030 не оставляет исключения, пока его не назвала спека. |
| Скрипт запасных поднял сотню процессов | Потолка нет, или скрипт верит строке со страницы, а не числу. |
| На коробке после `POST /drain` — тревога на каждую единицу | Осушали единственный сервер: увести некуда, `safe` не наступит. На коробке обновляют перезапуском. |
| Половина коробки в цикле перезапусков после обновления | Схему подняли раньше, чем перезапустили всё: незапущенный процесс остался старым и теперь отказывается стартовать. |

## Итог

- Точка входа платформы одна — `python3 -m w2cplatform controller <sub> | resource | console`, — и работает она от `SPEC_DIR` и ни от чего больше. Без спек — отказ словами, а не процесс, который ничего не делает.
- Каждый процесс открывает хранилища одной функцией, `stores`, своей ролью из спеки. На коробке это `file://` с проверкой в клиенте, в кластере — сокет роли у `configstore`. Код не меняется, меняется URL (ADR 0021, ADR 0022).
- Три юнита платформы: шаблон контроллеров, где имя экземпляра — имя спеки; ресурс — процесс, а не таймер; консоль на порту и на сокете коробки. VMS в них называют только образ, `CONSOLE_ROOT` и второй файл окружения — слова развёртывания.
- Процессы платформы — `w2c`, никогда не пользователь подсистемы и не её группы (ADR 0023, ADR 0030). Клиенты служб платформы — по группам `w2c-events`, `w2c-store`, `w2c-secrets`, с фиксированными номерами и маской 0007.
- Всё изменяемое — под `/data/platform`, конфигурация — `/etc/w2c`, ссылка туда, потому что обновление ОС не должно менять, членом какого хранилища является коробка. Ни один юнит не монтирует корень целиком.
- Ключ — файл 0640 группы `w2c-secrets` в каталоге 2710: на коробке монтируется одним файлом туда, где открывают секреты; в кластере его выдаёт `LoadCredential`. Интерфейс один — `SECRETS_KEY`.
- Запасных запускает скрипт на хосте от `w2c`: число, а не команда; молчащая консоль — ничего; свой потолок; только как юнит своей роли.
- Осушать на коробке не к кому. Обновление — короткий плановый перерыв: процессы платформы переживают перезапуск без потерь, а схему поднимают последней.

## Упражнения

1. Запустите `python3 -m w2cplatform console` с `SPEC_DIR`, где лежит только `tests/testdata/testsub.subsystem.yaml`, и `CONSOLE_ROOT=testsub`. Что из того, что вы видите на странице, пришло из кода платформы, а что — из спеки?
2. Уберите `PodmanArgs=--umask=0007` из юнита ресурса и оставьте у клиентов. Что сломается, а что нет? Теперь наоборот.
3. Добавьте консоли `GroupAdd=2102`. Какой тест упадёт и почему он прав, хотя писать в архив консоль может и так?
4. Замените ссылку `/etc/w2c` настоящим каталогом с тем же `w2c.env` и проведите обновление ОС через RAUC. Что увидит `PLATFORM_DIR` после переключения слота — и что увидит `PLATFORM_STORE` в кластере?
5. Смонтируйте в юнит контроллера `/data/platform` целиком. Перечислите, что теперь может прочесть ошибка в размещении.
6. Верните ресурс таймером. Перечислите, что при этом пропадёт, и как консоль будет отвечать на `/events`.
7. Перепишите таблицу ролей `w2c-spares.sh` так, чтобы роли брались из спек каталога. Что скрипту нужно знать о спеке, чтобы найти страницу и префикс, — и нужен ли ему для этого Python?
8. Осушите единственный сервер коробки, на которой стоит `counter`. Что скажут `GET /drain` и журнал, и что станет с единицей, созданной после этого?
9. Поднимите схему, забыв перезапустить один контроллер. Что он напишет в журнал и что покажет `GET /schema`?

## Что дальше

Модуль закончен: платформа написана и стоит на коробке, не зная ни одной подсистемы. Подсистемы ставит [М10B](../М10B_ServerVMS/README.md): VMS кладёт свои спеки в образ и свои юниты рядом с этими — воркеры, `vmsjobs`, движок архива `obsd` на хосте ([урок 17 М10B](../М10B_ServerVMS/17-on-the-box.md)). Дальше — [**М11**](../М11_Cluster/README.md): строки уходят в реплицированное хранилище, и права из спеки проверяет демон по сокету роли ([урок 5](../М11_Cluster/05-rights-by-who-is-calling.md)); те же процессы платформы встают юнитами systemd на каждом сервере ([урок 3](../М11_Cluster/03-units-on-every-server.md)); объекты остаются файлами — теперь на сервере писателя, читаемыми через ресурс ([урок 6](../М11_Cluster/06-what-stays-on-the-server.md)).

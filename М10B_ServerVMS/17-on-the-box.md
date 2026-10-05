# Урок 17 — На коробке

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/__main__.py` — точки входа VMS: её воркеры и `jobs`, каждая со своим токеном; `deploy/` — по юниту Quadlet на процесс VMS рядом с юнитами платформы из [урока 21 М10A](../М10A_Platform/21-Platform-on-the-Box.md), `obsd.service` для движка архива, `Containerfile`, `vms.env.example`, пользователь движка и каталоги VMS (`obsd.sysusers`, `vms.tmpfiles`), `install-obsd.sh`; `tests/test_deploy_units.py` — тесты, читающие юниты VMS как код.
**Время:** ~75 минут.

## Зачем этот урок

Последний урок модуля, и новых мыслей в нём почти нет. Всё, что в нём есть, — склейка написанного: какой процесс с каким токеном, что куда монтируется, что говорит `systemctl`.

Платформа на коробке уже стоит: [урок 21 М10A](../М10A_Platform/21-Platform-on-the-Box.md) поставил её контроллеры, ресурс и консоль от пользователя `w2c`, с состоянием под `/data/platform`, ключом файлом группы `w2c-secrets`, половиной окружения `w2c.env` и скриптом запасных. Этот урок ставит рядом VMS — её спеки в образе, её процессы своими юнитами, её движок архива на хосте — и платформенного не повторяет.

Проектная записка объясняет, почему это один урок, а не три:

> *Всё, что в нём есть, — это склейка уже написанного. Растягивать её на три урока значило бы объяснять `Volume=` трижды.*

Но одна вещь в уроке важнее склейки, и ради неё он написан: **монтирования повторяют ACL**.

Токен контроллера не пишет ни строк камер, ни событий — и архива у него нет вовсе. Регистратор никогда не открывает камеру — и файлов камер ему не смонтировано. Видео не смонтировано никому: оно в томах, за демоном движка. Одно и то же разграничение выражено дважды: в хранилище и в файловой системе.

Тест `test_who_may_write_where_is_in_the_mounts_too` проверяет это буквально, и его название — тезис урока: **«кто где может писать — это и в монтированиях тоже»**.

Второе: **юниты читаются как код**. Тесты разбирают юниты и сверяют их с пакетами. Развёртывание перестаёт быть тем, что «правится на месте», и становится тем, что ломает сборку.

И третье, новое: **одна вещь на коробке — не контейнер**. Движок архива, `obsd`, — демон хоста со своим юнитом systemd. Почему не контейнер образа и почему один на коробку — шаг 5.

> **Проверка без железа.** Тесты урока — да: они читают файлы, импортируют модули и запускают скрипты установки в песочнице. Настоящий запуск — коробка из М9 с podman и `obsd`, собранным из исходников ObjectStorage (шаг 5).

## Что нужно знать заранее

- **Уроки 1–14** — все четыре подсистемы: урок их расставляет.
- **М10A, урок 21** — [платформа на коробке](../М10A_Platform/21-Platform-on-the-Box.md): её юниты, пользователь `w2c` и группы клиентов, `/data/platform` и `/etc/w2c`, ключ, `w2c.env`, скрипт запасных. Здесь процессы VMS встают рядом и становятся клиентами её служб.
- **М10A, урок 2** — ACL и токены: то, что здесь повторяется монтированиями.
- **М9, урок 5** — A/B-корень и раздел данных: почему конфигурация лежит там, где лежит.
- **Урок 6** — [`obsd`](06-objectstorage-the-engine.md): движок архива — процесс, один писатель на том на хосте, отцепленный писатель ждёт своего владельца.
- **Урок 10** — [`after_stop`](10-recworker.md): писатель закрывается после сброса, и только потом отпускается захват тома.

## Чему вы научитесь

1. Давать каждому процессу токен уже, чем весь префикс подсистемы.
2. Выражать одно разграничение двумя механизмами.
3. Читать шаблонный юнит и понимать, что означает имя экземпляра.
4. Ставить на хост демон, которым пользуются контейнеры, и решать, что в контейнере, а что нет.
5. Выводить сроки остановки из того, что процесс делает при остановке.
6. Проверять развёртывание тестами, а не глазами.
7. Собирать один образ на все процессы.

---

## Шаг 1 — Точки входа VMS

```python
"""python3 -m vms worker|recorder|gateway|detworker|detjobworker|surveyworker|autoworker|jobs|domainpart —
the VMS's processes on a box. Every subsystem's controller is the platform's, run from its spec
(`python3 -m w2cplatform controller vms|rec|live|det|detjob|survey|auto`, `w2cplatform/host.py`; …), and so are the
resource (`python3 -m w2cplatform resource`: what a keep holds is the spec's `holds:`) and the console (`python3 -m
w2cplatform console`, `CONSOLE_ROOT=vms`: the specs' rows, tables, requests and doors). What is left of the VMS's own
beside its workers is its housekeeping, `jobs`: the requests turned into work and the work into closed rows.
```

У процессов коробки **два хозяина**:

| Чьи | Точка входа | Юнит |
|---|---|---|
| платформы | `python3 -m w2cplatform controller <sub>`, `resource`, `console` | `w2c-controller@vms`, `@rec`, `@live`, `@det` (и `@detjob`, `@survey`, `@auto` уроков 21–25), `w2c-resource`, `console` — [урок 21 М10A](../М10A_Platform/21-Platform-on-the-Box.md) |
| VMS | `python3 -m vms worker`, `recorder`, `gateway`, `detworker` (уроки 4, 10, 13, 14) | `vmsworker@`, `recworker@`, `liveworker@`, `detworker@` |
| VMS | `python3 -m vms detjobworker`, `surveyworker`, `autoworker` (уроки 21, 23, 25) | `detjobworker@`, `surveyworker@`, `autoworker@` |
| VMS | `python3 -m vms jobs` — хозяйство VMS: заявки, ставшие работой, и закрытая законченная работа | `vmsjobs.container` |

`domainpart` — тоже глагол VMS, но держателя домена, а не коробки: его юнит — `deploy/domain/systemd/vms-domainpart.service` (М12B).

**Контроллеры, ресурс и консоль коробки — процессы платформы по спекам VMS.** Своих у VMS нет: она кладёт в образ семь спек (`SPEC_DIR=/app/vms`), и платформа работает по ним. Контроллер каждой подсистемы — экземпляр шаблона `w2c-controller@.container`, и имя экземпляра — имя спеки: восьмая спека получит контроллер ещё одним экземпляром того же шаблона. Ресурс держит то, что велят `holds:` спек (М10A, урок 14). Консоль ставит VMS в корень (`CONSOLE_ROOT=vms`), остальные спеки — под своими именами, `/rec/…`, `/live/…` (`test_the_console_unit_builds_the_vms_at_its_root_and_every_other_spec_under_its_name`). Как устроены их юниты, — урок 21 М10A, шаги 1 и 3. У VMS остаются её воркеры и `jobs`.

Докстрока `vms/__main__.py` — **справочник по окружению**, и стоит заметить одну строку:

```
CAPACITY=50                      cameras this worker can carry — exported as headroom for the autoscaler
RECORDER_NAME=r-1                a recorder's slot (systemd: %i); CAPACITY here is recordings — this server's disks and NIC
GATEWAY_NAME=g-1                 its slot (systemd: %i); CAPACITY here is viewers
DET_NAME=d-1                     a detector worker's slot; CAPACITY here is streams; NOMAD_META_labels=gpu says where it is
```

**Одна переменная, четыре значения.** Примечание к файлу это подчёркивает: `CAPACITY` означает разное в зависимости от глагола.

Спорно ли это? Немного: `WORKER_CAPACITY`, `RECORDER_CAPACITY` были бы однозначнее. Выигрыш от одного имени — в том, что оно **общее для воркера платформы**: воркер, регистратор, шлюз и детектор читают одну переменную, потому что все они — `Worker` платформы, и ёмкость — её слово (`placement.capacity: {from: capacity}`). Различие — не в имени переменной, а в том, что каждая подсистема считает своей единицей ёмкости (уроки 4, 10, 13, 14).

Комментарий в файле окружения снимает двусмысленность: он говорит, чем ёмкость является для каждого.

```python
# ### `if __name__ == "__main__"`
# Dispatch table on `sys.argv[1]`
```

Диспетчер — словарь. Ни `argparse`, ни подкоманд, ни справки: имена глаголов, одно из них первым аргументом.

И примечание к модулю: **`__main__.py` — это склейка и ничего больше.** Никакой своей логики за пределами сборки. Это видно по тому, что все предыдущие уроки написали работающие объекты, не зная, кто их создаст.

## Шаг 2 — Токен уже, чем префикс

```python
# - Three tokens, three processes: `vmsworker` (epochs, slots), `vmscontroller` (placement), `console`
#   (the operator's rows). Together they partition `vms/*`; none of them can do another's job.
```

Три токена **разбивают** `vms/*` на три непересекающиеся части:

| Роль (процесс) | Что пишет |
|---|---|
| `vmscontroller` (`w2c-controller@vms`) | `vms/workers/*`, `vms/placement/*`, `vms/slots/*`, `vms/decommissioned/*` |
| `console` (`console`) | `vms/cameras/*`, `vms/next_id`, `vms/idem/*`, `vms/retention/*`, `vms/requests/*`, … и `platform/drain`, `platform/schema` |
| `vmsworker` (`vmsworker@`) | `vms/epoch/*`, `vms/slots/*`, `vms/holds/*`, `vms/devices/*` (`worker: {writes: [devices]}`; `config.WORKER_ACL`) |

**Ни один не может делать работу другого.** Консоль, у которой завёлся бы код размещения, получила бы `Forbidden` (урок 3 М10A). Воркер, попытавшийся поправить строку камеры, — тоже.

**И читает каждый не шире, чем ему нужно.** Дверь воспроизведения держателя спрашивает только, в домене ли кластер, — токенов она не проверяет (`Gate.gated`). А читала она все строки, которыми домен метит своего члена, и политика держателя в М11 разрешала ему читать `domain/break_glass` — хеш аварийного пароля — и гранты (девятое ревью, minor). Теперь `gated` читает набор ключей `domain/keys` и, пока его нет, одну строку членства `domain/member` (`MEMBER_MARK`): её агент домена пишет на каждом проходе, и у кластера, потерявшего ключи, она остаётся. Остальные метки читает консоль, которой они нужны для проверки токена. В списке чтения роли `vmsworker` файла прав кластера (`configstore-rights.json`) из `domain/*` остались эти две строки. Тест М11: `test_policies.py::test_the_holder_reads_no_more_of_the_domain_than_its_door_asks` — из `domain/*` роль держателя читает ровно эти две, и дверь в открытом кластере и у члена без ключей прочла ровно их.

Обе ACL вырезаны из **одной спецификации** (`SPEC.acl_console()`, `SPEC.acl_controller()`, урок 10 М10A). Добавили поле — обе обновились; нового места для рассинхронизации не появилось.

То же правило у регистратора, и урок 10 рассказал, как его однажды нарушили: процесс `recorder` открывал хранилище со списком прав, написанным руками, и без `rec/holds/*` не мог взять собственный том. Теперь его права — `REC_SPEC.acl_worker_role()`, выведенные из спецификации (`test_the_recorder_process_holds_a_token_that_can_take_a_volume`).

И примечание договаривает:

> *The mounts in `deploy/` repeat the same split in bytes.*

## Шаг 3 — Монтирования как вторая ACL

Вот тест — он короче, чем объяснение:

```python
def test_who_may_write_where_is_in_the_mounts_too():
    """The ACL says which rows each token writes; the mounts say which bytes.
    The controller writes its journal into the events archive (`host.controller_loop`, by `RESOURCE_ROOT`), so the
    archive is mounted for it, as a client of it (`w2c-events`) — unmounted, its lines lay in the container's layer;
    footage is mounted nowhere — it is behind the host's obsd."""
    vols = lambda n: dict(v.split(":", 1) for v in (lambda x: x if isinstance(x, list) else [x])(unit(n)["Container"]["Volume"]))
    groups = lambda n: (lambda x: x if isinstance(x, list) else [x])(unit(n)["Container"].get("GroupAdd", []))
    assert vols("w2c-controller@.container")[EVENTS] == f"{EVENTS}:z" and "2102" in groups("w2c-controller@.container")
    assert "RESOURCE_ROOT=" in open(os.path.join(DEPLOY, "w2c.env.example")).read()     # …which the unit's env file says
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert "/data/spool" not in vols(n), n                                       # there is no spool: footage goes through obsd
            # the two stores, never /data/platform whole: its etc/secrets holds the key ring
            assert "/data/platform" not in vols(n) and not any(v.startswith("/data/platform/etc") for v in vols(n)), n
    assert vols("vmsworker@.container")[EVENTS] == f"{EVENTS}:z"                       # its events, vms/<cam>/, on this box's resource
    assert vols("vmsworker@.container")["/data/media"].endswith(":ro,z")
    assert vols("recworker@.container")[EVENTS] == f"{EVENTS}:z"                      # its events; its volume is the daemon's
    assert "/data/media" not in vols("recworker@.container")                          # it never reads a camera: it subscribes to the fan-out
    assert vols("vmsworker@.container")["/run/vms"] == "/run/vms:z" == vols("recworker@.container")["/run/vms"]   # the tee's shared memory
    # the daemon's socket: the recorder's alone, never the holder's — the process with a vendor's DriverPack in it
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert ("/run/vms-obsd" in vols(n)) == (n == "recworker@.container"), n
    rec_env = dict(e.split("=", 1) for e in unit("recworker@.container")["Container"]["Environment"])
    assert rec_env["OBSD_SOCKET"] == "/run/vms-obsd/obsd.sock" and rec_env["SECRETS_KEY"] == "/run/secrets/platform.key"   # it opens a volume's secret
    assert vols("w2c-resource.container")[OBJECTS] == f"{OBJECTS}:z"                  # the heartbeat is written, and its door's row
    assert unit("recworker@.container")["Container"]["StopTimeout"] == "40"          # the writer's close waits for its flush (30 s)
    assert "obsd.service" in unit("recworker@.container")["Unit"]["After"]
    # …ordered after the host's engine, never starting it (the product's r28-ops2) … No unit wants another.
    for n in os.listdir(DEPLOY):
        if n.endswith((".container", ".service")):
            assert "Wants" not in unit(n).get("Unit", {}) or unit(n)["Unit"]["Wants"] in ("network-online.target",), n
    assert unit("w2c-resource.container")["Service"]["Restart"] == "always"         # a process, not a timer: the database lives in it
```

Каждая строка — утверждение из модуля, выраженное монтированием.

**У контроллера — только его журнал.** Контроллер пишет свой журнал — какой слот он освободил и почему (`host.controller_loop`, `journal.py`) — в `audit/controller/` архива событий, который назвал `RESOURCE_ROOT`, и шаблон платформы монтирует ему этот архив клиентом (`w2c-events`, `GroupAdd=2102`; урок 21 М10A, шаг 3). Видео не смонтировано ему ни в одной копии шаблона, контроллеру записей тоже: ошибка в размещении записей не может испортить запись — не потому, что код правильный, а потому что видео у контроллера нет.

**Спула нет ни у кого.** Это не строка про один юнит, а цикл по всем `.container` каталога. Видео не пишется в файлы, которые можно смонтировать: регистратор отдаёт кадры демону `obsd` через сокет, а демон пишет в том (урок 10). Цикл сторожит, чтобы локальная очередь не вернулась «на время» ни в одном юните.

**Воркеру архив на запись — только ради событий.** `vms/<cam>/`, бакеты событий камеры. В `rec/` он не пишет никогда, и это уже не монтирование, а дисциплина кода. Видео он не пишет вовсе (урок 4): стока в том в его конвейере нет (урок 9).

**Медиа воркеру только на чтение**, регистратору — **не смонтированы вовсе**, и комментарий объясняет: *он никогда не читает камеру, он подписывается на раздачу.* Регистратор, у которого нет доступа к файлам камер, физически не может открыть второе соединение.

**Регистратору архив на запись — ради его событий**: `archive.shallow`, `archive.keep.*` под `rec/` на ресурсе этого сервера. Видео здесь нет. Собственный том сервера лежит у VMS, в `/data/vms/obsd/volume` (урок 10, шаг 8; `config.OWN_VOLUME`), и регистратор его не монтирует: он называет путь демону, а том открывает демон на хосте. Объявленный локальный том — тоже путь на хосте, который открывает демон, и монтировать его регистратору не нужно вовсе.

**Сокет демона — в своём каталоге и только у регистратора.** До третьего ревью сокет `obsd` лежал в `/run/vms` рядом с разделяемой памятью воркеров, и процесс воркера — тот, где работает сторонний DriverPack, — мог читать запись всех камер коробки мимо прав и аудита, а в окно ожидания писателя — забрать его. Воркеру `obsd` не нужен вовсе. Теперь сокет — `/run/vms-obsd/obsd.sock`, монтирует его один `recworker@` (`OBSD_SOCKET`, `GroupAdd`), а демон работает своим пользователем (`User=vms-obsd`) и пускает, кроме себя, только группу `OBSD_CLIENT_GROUP` (нужна сборка демона, которая этот параметр знает). Чего по-прежнему нет: клиенты группы доверены одинаково, а владелец писателя — имя, не секрет. Ключ печатей у регистратора теперь тоже есть: ему открывать секрет сетевого тома (урок 10).

**`/run/vms` — и у воркера, и у регистратора**, одинаково на запись. Там разделяемая память раздачи (урок 4): воркер пишет, регистратор на том же сервере читает. Сокета демона там больше нет — он в `/run/vms-obsd`, и монтирует его один регистратор (ниже). Оба — tmpfs, а не состояние, и обновление системы не обязано их сохранять.

**Хранилища — двумя монтированиями, а не `/data/platform` целиком.** Под корнем платформы лежит `etc/`, а в нём ключ кластера (урок 21 М10A, шаги 5 и 6). Каталог целиком дал бы ключ каждому контейнеру VMS: процессы VMS в них — root, и права на файл их не остановят. Поэтому юнит VMS монтирует `config/` и `objects/`, а кто пишет события — ещё `events/`, и ничего больше; цикл теста держит это для каждого юнита каталога.

Ещё три проверки — про регистратор и его остановку: `StopTimeout=40`, `After=obsd.service` и то, что ни один юнит не хочет (`Wants=`) другой. Откуда эти числа и этот порядок — шаг 5.

Каждое утверждение — **вторая линия обороны**. Первая — токен в хранилище, вторая — файловая система. Ошибка должна пробить обе.

## Шаг 4 — Шаблон и слот

```ini
[Unit]
Description=VMS worker %i — holds its cameras: DriverPack, the fan-out, the events

[Container]
Image=localhost/vmsserver:latest
Exec=python3 -m vms worker
Environment=WORKER_NAME=%i
Environment=RTSP_PORT=auto
Environment=PLAYBACK_PORT=auto
EnvironmentFile=/etc/w2c/w2c.env
EnvironmentFile=/etc/vms/vms.env
Volume=/data/platform/config:/data/platform/config:z
Volume=/data/platform/objects:/data/platform/objects:z
GroupAdd=2103
PodmanArgs=--umask=0007
Volume=/etc/w2c/secrets/platform.key:/run/secrets/platform.key:ro,z
GroupAdd=2104
Environment=SECRETS_KEY=/run/secrets/platform.key
Volume=/data/platform/events:/data/platform/events:z
GroupAdd=2102
Volume=/data/media:/data/media:ro,z
Volume=/run/vms:/run/vms:z
Network=host
StopTimeout=20

[Service]
Restart=always
RestartSec=2
```

`vmsworker@.container` — **шаблон**. `systemctl start vmsworker@w-1`, и `%i` подставляется как `w-1`.

```ini
Environment=WORKER_NAME=%i
```

**Имя экземпляра systemd — это слот.** И комментарий в юните формулирует то, ради чего в уроке 3 слот брался именно так:

> *`claim_slot(prefer=…)` takes exactly that slot by CAS, even from a holder that has not lapsed — systemd is the authority on which process is the current `w-1`, and the old one finds out at its next `renew_slot` and fences.*

**Супервизор — авторитет по вопросу, кто сейчас `w-1`.** Не хранилище, не предыдущий держатель. Systemd перезапустил воркера — новый забирает слот, старый (если он ещё жив) обнаружит это при следующем продлении и отсечётся (урок 4). У регистратора то же самое, и урок 10 добавил к этому том — с одной оговоркой после шестого ревью. Идёт ли захват места за именем, решает одно правило платформы, `Worker.hold_follows_name` (М10A, урок 7), по `placement.places.server_field` спеки и строке самого места. Захват **диска** идёт за именем только на сервере этого диска (`self.server == row.server`): писать в него может только эта коробка, и писателя тома демон держит для того же владельца. Захват **сетевого** тома за именем следует, только если прежний держатель был на **этой же** коробке (седьмое ревью: перезапуск под systemd снова пишет сразу; один демон держит одного писателя тома). Держателя с другой коробки ждут: его следующий держатель может быть на другой коробке, а прежний экземпляр — замороженным, не мёртвым, с подмонтированным писателем (воспроизведено: два `r-1` на двух демонах, тридцать кадров рядом). Ограда движка держится на том, что претендент **ждёт** `slot_ttl + HOLD_SKEW` неизменной строки, — и для такого тома ждут все, кто пришёл с другой коробки, то же имя включительно; ждут и место, чья строка не читается. Только захват, отпущенный нарочно — писатель закрыт первым (`leave_volume`, `after_stop`), — берётся сразу.

`StopTimeout=20` — двадцать секунд на штатную остановку: SIGTERM даёт актуатору остановить конвейеры (EOS перед `NULL`, урок 9), а воркеру — отпустить слот. SIGKILL после двадцати секунд **оставляет слот протухать**, то есть выглядит как падение, которое контроллер не перераспределяет (урок 4). Видео у воркера нет, поэтому ни одного кадра этот срок не сторожит; у регистратора срок другой, и считается он от другого (шаг 5).

`Network=host` — RTSP-раздача слушает свой порт на адресе коробки. Прокидывать порты бессмысленно: их столько, сколько воркеров.

### Дверь в шаблоне не может быть числом

И вот здесь шаблон легко испортить одной строкой. `Environment=GATEWAY_PORT=8082` в шаблоне шлюза читается безобидно — ровно до второго экземпляра: `systemctl start liveworker@g-2` займёт уже занятый сокет, упадёт, а `Restart=always` с `RestartSec=2` будет поднимать его **каждые две секунды до утра**. То же у воркера: раздача и дверь воспроизведения — два порта, а масштабирование воркеров на одной коробке штатно, ёмкость же считается в камерах.

Ломается это не сразу и навсегда, и в журнале выглядит как `bind: address already in use` без единого намёка на то, что виноват шаблон, а не машина.

Лечится тем, что у нас и так есть:

```ini
Environment=RTSP_PORT=auto
Environment=PLAYBACK_PORT=auto
```

**Номер спрашивают у операционной системы, а адрес берут из heartbeat'а.** Ни один подписчик никогда не знал числа: регистратор, шлюз, детектор и дверь записи читают `live_url` и `playback_url` из статуса камеры — с четвёртого урока. Значит число может быть нулём, а публиковать надо то, что дала система:

```python
    def serve_playback(self, host="127.0.0.1", port=None):
        srv = ThreadingHTTPServer((host, self.playback_port if port is None else port), self.playback_handler())
        self.playback_port = srv.server_address[1]          # что дал сокет, то и публикуем
```

С раздачей то же самое, только спросить надо у того, кто её открыл: `GstRtspServer` знает свой порт (`get_bound_port()`), актуатор его сообщает, воркер публикует. Дверь архива регистратора устроена так же: `ARCHIVE_PORT` по умолчанию — что даст система, а адрес уходит в heartbeat словом платформы `url` (его же `/rec/where` отдаёт странице с токеном). Правило общее и стоит того, чтобы его назвать: **процесс, открывший дверь, — единственный, кто знает её номер; остальные читают адрес.**

Умолчания при этом прежние (`8554`, `8083`, `8082`), так что коробка с одним воркером ведёт себя ровно как раньше; `auto` — это то, что делает второй экземпляр возможным, а drop-in с числом остаётся для того, кто хочет предсказуемый порт.

`Restart=always`, `RestartSec=2` — и комментарий: *процесс супервизирует конвейеры, systemd супервизирует процесс.* Перезапущенный экземпляр берёт тот же слот и поднимает свои камеры с новой эпохой — **без участия контроллера**.

`:z` на каждом томе — пересылка меток SELinux. На коробке с включённым SELinux без этого контейнер не прочитает ничего.

`GroupAdd=2103`, `GroupAdd=2102`, `GroupAdd=2104` и `PodmanArgs=--umask=0007` — воркер **клиент** служб платформы: хранилищ (группа `w2c-store`), архива событий (`w2c-events`) и ключа (`w2c-secrets`). Группы — числами, маска — аргументом podman; почему так, — урок 21 М10A, шаг 4. Зачем всё это процессу, который и так root, — шаг 6.

### Кто запускает экземпляр, которого не хватает

Шаблон отвечает на вопрос «как запустить ещё одного», но не на вопрос «кто заметит, что он нужен». На коробке автоскейлера нет, и это место, где правило «платформа не запускает процессов» оказывается неудобным: оператор завёл в консоли сетевой архив, а держать его некому.

Первый ответ — **цифра**. Контроллер записей — платформенный — знает, скольких держателей не хватает: тома объявлены, а держать их некому. Он публикует число на `/rec/metrics` — `rec_workers_needed{labels=""}`, гейдж платформы `<подсистема>_workers_needed`, — и оператор запускает юнит сам: `systemctl start recworker@r-4`.

Кнопки при этом нет намеренно. Кнопка означала бы, что у консоли есть право говорить с systemd, то есть root на своей машине — у процесса, который слушает HTTP. Цена кнопки — не строчка кода, а то, что «платформа не запускает процессов» превращается в предложение с исключением.

Второй ответ, если нажимать руками не хочется, — **таймер на хосте**: скрипт запасных платформы, `w2c-spares.sh`, от её пользователя `w2c` (ADR 0030), раз в минуту. Он берёт со страницы консоли число, а не команду, держит свой потолок и ничего не останавливает; его правила и тесты — в [уроке 21 М10A](../М10A_Platform/21-Platform-on-the-Box.md), шаг 8. Для регистраторов его запускает `w2c-spares.service`:

```ini
ExecStart=/usr/local/bin/w2c-spares.sh recworker
```

Для регистраторов это то самое `rec_workers_needed{labels=""}`: места, которые никто не держит, без меток и без предложения слота (запасной регистратор сам берёт свободный том), а потолок — `MAX_RECORDERS`.

Что добавляет VMS — **шаблон запасного своей роли**. Запасной запускается только как юнит своей роли: из шаблона `vms-<роль>-spare@.service`, строка в строку юнита роли без имени, с тем же пользователем, группами и ключом (двенадцатое ревью, блокер 6: запасной от `systemd-run` был root без ключа, и запечатанная камера на нём не стартовала). Такие шаблоны есть у юнитов кластера М11 ([урок 4 М11](../М11_Cluster/04-a-name-is-a-slot.md), шаг 5). У контейнеров коробки их нет: на коробке скрипт ничего не запускает, а говорит почему, и остаётся число, по которому оператор запускает юнит сам.

Механизмов таких три — рука, этот таймер и (в кластере) автоскейлер или `vms-scaler`, — и в одной установке работает **ровно один**: два агента с мнением об одном числе дерутся. Сравнение целиком, с тем, что у всех трёх общего, — в [уроке 4 М11](../М11_Cluster/04-a-name-is-a-slot.md), шаг 4.

## Шаг 5 — Движок архива: демон хоста, а не контейнер

```ini
[Unit]
Description=ObjectStorage daemon — the archive's engine, one per host
After=local-fs.target network.target

[Service]
ExecStart=/usr/local/bin/obsd --socket /run/vms-obsd/obsd.sock
User=vms-obsd
Group=vms-obsd
Environment=OBSD_CLIENT_GROUP=vms-obsd
RuntimeDirectory=vms-obsd
RuntimeDirectoryMode=0750
RuntimeDirectoryPreserve=yes
Environment=OBSD_WRITER_GRACE_S=90
Environment=OBSD_LOG_LEVEL=warning
Restart=always
RestartSec=2
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
```

Шапка юнита говорит главное одной фразой:

> *Not a container and not one of the VMS's processes: the engine the recorders write their footage through, over a unix socket in /run/vms-obsd (`vms/obsd.py`). One per host — it keeps one writer per volume, and that rule means something only if every recorder on the box asks the same daemon.*

**Почему один на коробку.** Правило «один писатель на том» держит демон (урок 6). Второй демон на той же коробке о писателях первого не знает: два регистратора, спросившие два разных демона, получили бы двух писателей одного тома — и порчу вместо отказа. Поэтому демон — не часть процесса регистратора и не контейнер рядом с каждым регистратором, а роль хоста, как файловая система. Второй экземпляр на том же сокете демон и сам не запустит: README говорит, что он берёт `flock` на `<socket>.lock`.

**Почему не контейнер образа.** Образ — это Python-пакеты курса (шаг 7), а `obsd` — программа на C++ из исходников ObjectStorage. И у демона другой жизненный цикл: регистраторы перезапускаются при каждом обновлении курса, а демон — нет, и пока он жив, писатели томов переживают перезапуски регистраторов.

Теперь каждая строка.

**`--socket /run/vms-obsd/obsd.sock`** (до третьего ревью — `/run/vms/obsd.sock`, см. шаг 3). Сокет был в том же tmpfs, что разделяемая память воркеров, и потому был виден и воркеру с драйвером; теперь у него свой каталог, `/run/vms-obsd`, который монтирует только `recworker@`. `OBSD_SOCKET=/run/vms-obsd/obsd.sock` задан в юните регистратора, и умолчание клиента на Linux (`vms.obsd.default_socket`) совпадает; на macOS умолчание — собственное демона, `/tmp/vms-obsd-<uid>.sock`.

**Имена — продукта: `vms-obsd`.** Курс звал каталог `/run/obsd`, пользователя `obsd`, группу клиентов `vms-rec`. Продукт развёл имена так: платформа — `w2c` (хранилище, ресурс, запасные, установщик, общий CA), а движок архива — часть VMS-приложения и остаётся `vms`: служба `vms-obsd.service`, пользователь и группа `vms-obsd`, сокет `/run/vms-obsd/obsd.sock`. Курс взял те же имена, кроме имени юнита (`obsd.service`): одна группа — и демона, и его клиентов, номер прежний, 2101. Сессия, которую вызывающий не назвал, говорит в `HELLO` имя процесса (`process_name`: `python3 -m vms` — `vms`, `tests/run.py` — `run`), а не `"vms"` за любой процесс. Тест: `test_deploy_units.py::test_a_session_named_by_nobody_says_its_process_name_and_not_a_subsystems`.

**`User=vms-obsd`, `Group=vms-obsd`, `OBSD_CLIENT_GROUP=vms-obsd`.** Демон работает своим пользователем и пускает, кроме себя, только группу клиентов — регистраторы входят в неё по номеру (`GroupAdd=2101` в `recworker@.container`: у контейнера нет `/etc/group` хоста). Пир без группы демон отвергает сам, пир не из группы не пройдёт и права на сокет. На Linux группа учитывается любая, и дополнительная тоже; на macOS — только основная (так ответила сессия, которая ведёт движок). Нужна сборка `obsd`, которая этот параметр знает: изменение исходников от 2 октября 2026, не патч.

**`RuntimeDirectory=vms-obsd`, `RuntimeDirectoryMode=0750`, `RuntimeDirectoryPreserve=yes`.** Каталог сокета, `vms-obsd:vms-obsd`, systemd создаёт **до** демона: сам демон создал бы его 0700, и ни один регистратор в него бы не вошёл. И не уносит при перезапуске. `/run/vms` этот юнит больше не создаёт — он общий для коробки (ниже).

### Подготовка коробки: пользователь, группа, каталоги

Юнит, который называет несуществующего пользователя, не стартует (217/USER), а без демона не пишет никто. И `/run/vms` создавал только он — без демона не стартовали ни `vmsworker@`, ни `recworker@`, которые его монтируют (четвёртое ревью, блокер 2: после третьего ревью коробку под нового пользователя не готовил никто). Поэтому у коробки пять файлов установки, и два из них — платформы:

- `deploy/obsd.sysusers` → `/etc/sysusers.d/obsd.conf`: группа `vms-obsd` с **фиксированным** номером 2101 (по нему её находят контейнеры) и пользователь `vms-obsd`, для которого она основная (`u vms-obsd -:vms-obsd`).
- `deploy/w2c.sysusers` и `deploy/w2c.tmpfiles` — пользователь платформы `w2c` и группы её клиентов, её каталоги под `/data/platform` и сокет консоли; их разбирает урок 21 М10A, шаги 4 и 5. У продукта та же пара — `w2c.conf` и `vms.conf`, только пути в `/var/lib` и `/run`.
- `deploy/vms.tmpfiles` → `/etc/tmpfiles.d/vms.conf`: каталоги **VMS** — `/run/vms` 0755 root (разделяемая память воркеров), `/run/vms-obsd` 0750 `vms-obsd:vms-obsd` (для регистратора, который стартует раньше демона), `/data/vms` и его `etc/` (это `/etc/vms`), `/data/vms/obsd` и `/data/vms/obsd/volume` 0750 `vms-obsd:vms-obsd` (собственный том сервера — его открывает демон, значит, он и владелец).
- `deploy/install-obsd.sh`: ставит все четыре (другого установщика у коробки нет; у продукта это его `install.sh`), отказывается, если `vms-obsd` или одно из имён платформы уже есть с другим номером — на коробке со старыми именами курса называет, что убрать: `userdel obsd; groupdel vms-rec`, — переносит старую раскладку курса на раздел данных и кладёт ссылки `/etc/w2c` и `/etc/vms` (шаг 8), **один раз** отдаёт содержимое хранилищ группе `w2c-store`, архива событий — группе `w2c-events`, а `vms-obsd:vms-obsd` — кольца, отформатированные, когда демон работал от root — `/data/vms/obsd/volume`, пути, переданные аргументами, и тома, **объявленные для этой коробки** в её собственном хранилище (строки `rec/volumes/*` с `server` этой машины и каталогом в `url`; каждый найденный называется, а когда хранилище не каталог, как в М11, скрипт говорит, что не нашёл ни одного, и ждёт путей аргументами), — и включает `obsd.service`, перезапуская его только когда что-то под ним изменилось.

**Сначала остановить демон, потом отдавать тома, потом перезапустить.** Первая версия скрипта делала `chown -R`, пока работал прежний демон от root, а в конце звала `systemctl enable --now obsd.service`. На обновляемой коробке root-демон продолжал писать во время передачи и создавал за спиной `chown` новые блоки — снова root'а, которых новый демон потом не открыл бы. А `enable --now` запускает остановленный юнит и не трогает работающий: старый демон оставался под старым юнитом, с сокетом там, где регистраторы его больше не ищут, и все тома стояли `away`, пока кто-нибудь не перезапустил демон руками (пятое ревью, major, по скрипту; создание файлов проверено запуском). Теперь порядок такой: `systemctl stop obsd.service` до передачи томов, затем юнит, `daemon-reload`, `systemctl enable obsd.service` и `systemctl restart obsd.service` — юнит в том виде, в каком он написан сейчас, что бы ни работало до него. Тест: `test_deploy_units.py::test_install_obsd_stops_a_running_daemon_before_the_volumes_change_hands_and_restarts_it_after` запускает сам скрипт, подменив каждую команду записывающей заглушкой, и проверяет порядок, а не подстроку: остановка, передача томов, установка юнита, `enable`, `restart` — и ни одного `enable --now`.

**Останавливать только ради передачи, и убедиться, что демон встал.** Та версия глушила ошибку `stop` (`2>/dev/null || true`) и делала `chown` под демоном, который не остановился; повторный запуск на коробке, где всё в порядке, останавливал и перезапускал демон всё равно — каждая запись рвалась ни за что; а объявленные тома скрипт знал только те, что ему назвали (шестое ревью, minor). Теперь демон останавливается, только если есть что передать (`find` нашёл в томе не `vms-obsd`'ово), и после `stop` проверяется, что он стоит — юнит не активен и нет процесса `obsd` (`running`): иначе скрипт кончается кодом 3, ничего не передав, и говорит, что сделать. Юнит ставится, когда отличается от установленного (`cmp`); демон перезапускается, когда юнит сменился или его останавливали; стоящий — запускается; остальное остаётся как есть, и скрипт так и говорит. Новый **бинарник** на месте скрипт не замечает — это `systemctl restart obsd.service` руками. И слово: перезапуск демона — не `reattached`. `reattached` — это тот же демон, подобравший писателя, чья сессия оборвалась (регистратор перезапустился); с перезапуском **демона** его писатели уходят вместе с ним, и каждый регистратор монтирует том заново: `away`, потом `remounted` (урок 10, шаг 10). Тест: `test_deploy_units.py::test_install_obsd_stops_the_daemon_only_to_hand_a_volume_over_and_does_not_go_on_if_it_did_not_stop` — коробка в порядке: ни `stop`, ни `restart`; демон стоит: `start`; новый юнит: `restart` без `stop`; демон не остановился: код 3 и ни одного `chown`; том, объявленный для этой коробки, найден в хранилище и передан, чужой и бакет — нет.

Почему не `StateDirectory=`, как у продукта (`/var/lib/vms-obsd`): `/var/lib` лежит на слоте корневого раздела, который обновление системы заменяет, а архив курса — на разделе данных (М9, урок 5). Прогон на Linux (Debian 13, systemd первым процессом) был под прежними именами курса: обновление с демона под root на `obsd` — кольца переданы, демон работает от `obsd`/`vms-rec`, регистратор с группой пишет, root без группы и пользователь не из группы получают отказ, `/run/vms` и `/run/obsd` создаются при остановленном демоне. С именами продукта (`vms-obsd`, `/run/vms-obsd`) коробку заново не прогоняли — это открыто; тесты ниже проверяют файлы и скрипт, а не systemd. Тест: `test_deploy_units.py::test_every_user_group_and_directory_a_unit_names_is_made_by_the_install_files` — каждый пользователь, группа и каталог, которые называет юнит, создаются файлами установки.

**`OBSD_WRITER_GRACE_S=90`** — сколько писатель, чей регистратор пропал, ждёт того же владельца (`rec:<том>`). Захват тома умершего процесса истекает за 45 секунд, и тот, кто возьмёт том следующим, назовёт того же владельца (урок 10, шаг 8). Ожидание длиннее — значит, он подберёт писателя целиком. У самого демона по умолчанию 60 секунд, у продукта на ящике было 20 — и писатель хозяина не дождался. Тест проверяет неравенство, а не число: `int(env["OBSD_WRITER_GRACE_S"]) > 45`. Подберёт — на этом хосте. Сетевой том после истечения захвата может взять другая коробка со своим демоном. Тогда конец отсрочки здесь закрывает писателя через `CloseLease`, и движок с патчем 07 — сборка, которую курс требует, — никогда не удаляет чужой замок и останавливает писателя, чей замок потерян (`WRITER_STOPPED`, `WRITER_ABANDON`; урок 6, шаг 12; урок 10, шаг 11).

**`Restart=always`.** Демон, который ушёл, для каждого регистратора — `away`: тома остаются за ними, а следующий проход открывает их заново (урок 10, шаг 10).

**`TimeoutStopSec=60`.** По SIGTERM демон закрывает каждого писателя чисто, и каждый может сбрасываться до 30 секунд. README демона так и просит: дайте супервизору не меньше 60 секунд на остановку.

И одна строка README, которую стоит знать на коробке: пиру с другим uid демон отказывает, если тот не в `OBSD_CLIENT_GROUP`. До четвёртого ревью это выполнялось само — контейнеры и демон работали от root, — и сокет мог открыть любой процесс коробки, процесс воркера со сторонним драйвером тоже. Теперь демон — `vms-obsd`, регистраторы — члены группы `vms-obsd`, а воркер сокета не видит вовсе.

Тест читает юнит так же, как контейнеры:

```python
def test_the_archives_engine_is_the_hosts_own_daemon():
    """One obsd per host, not a container of the image: it keeps one writer per volume, and that means something
    only if every recorder on the box asks the same one. Its socket is where the recorder already looks."""
    from vms.obsd import default_socket
    u = unit("obsd.service")
    assert u["Service"]["ExecStart"] == "/usr/local/bin/obsd --socket /run/vms-obsd/obsd.sock"
    assert u["Service"]["RuntimeDirectory"] == "vms-obsd" and u["Service"]["RuntimeDirectoryPreserve"] == "yes"
    assert u["Service"]["RuntimeDirectoryMode"] == "0750"                              # its group gets in; the daemon's own 0700 would not let it
    env = dict(e.split("=", 1) for e in u["Service"]["Environment"])
    assert int(env["OBSD_WRITER_GRACE_S"]) > 45                                         # the writer outlasts a hold that lapses
    assert u["Service"]["User"] == "vms-obsd" and env["OBSD_CLIENT_GROUP"] == u["Service"]["Group"]   # its own user; the recorders' group
    import sys
    from unittest import mock
    with mock.patch.dict(os.environ, {"OBSD_SOCKET": ""}), mock.patch.object(sys, "platform", "linux"):
        assert default_socket() == "/run/vms-obsd/obsd.sock"                            # where the unit puts it: the product's path
    with mock.patch.dict(os.environ, {"OBSD_SOCKET": ""}), mock.patch.object(sys, "platform", "darwin"):
        assert default_socket() == f"/tmp/vms-obsd-{os.getuid()}.sock"                 # the daemon's own default on macOS
```

### Откуда берётся `/usr/local/bin/obsd`

Из исходников ObjectStorage, без SDK продукта и без сборочной системы монорепозитория:

```bash
ObjectStorage/standalone-build/build.sh /tmp/obsd-build          # копирует исходники движка, применяет патчи к копии, собирает
install -m 755 /tmp/obsd-build/build/obsd /usr/local/bin/obsd
deploy/install-obsd.sh                                          # пользователь и группа, каталоги, кольца под root — vms-obsd, юнит
```

Скрипт не трогает дерево ObjectStorage: он копирует то, что нужно движку, в `<out>/src`, применяет патчи из `patches/` к копии — все, 01–07; коробке нужен `obsd`, собранный с патчами 01–07, и именно его курс требует: без 07 движок не ограждает собственный замок, — и собирает `<out>/build/obsd` через CMake. С `--tests` он заодно собирает и прогоняет тесты демона (`obsd_ut`) и движка (`os_engine_ut`). Тот же бинарник нужен тестам курса: без него они падают с подсказкой — `OBSD_BIN=<out>/build/obsd` или `obsd` в `PATH`.

### Регистратор ждёт сброса писателя

Юнит регистратора называет демон в своём `[Unit]` и выводит срок остановки из того, что делает `after_stop` (урок 10, шаг 11):

```ini
[Unit]
Description=VMS recorder %i — the recordings of its assignment, into this box's archive
After=network.target obsd.service

[Container]
…
# SIGTERM: the pipelines stop, then the writer is closed — after its flush, up to thirty seconds by the
# protocol — and only then is the hold let go (`RecWorker.after_stop`).
StopTimeout=40
```

**`After=obsd.service` — и никакого `Wants`.** Регистратор, поднятый раньше демона, не сломается — он просто назовёт том `away` и откроет его на следующем проходе. Порядок убирает этот лишний круг при каждой загрузке. А `Wants=obsd.service` стоял здесь, чтобы поднять демон, если его забыли включить, — и поднимал его, когда не надо: администратор остановил демон, чтобы передать тома, регистратор упал, `Restart=always` поднял его — и с ним демон посреди передачи (продукт, r28-ops2). Демон запускает тот, кто его ставит (`install-obsd.sh`), и ни один юнит коробки не хочет другого — это держит тест выше.

**`StopTimeout=40`.** Штатная остановка регистратора — это конвейеры, последний heartbeat, слот, а потом закрытие писателя, которое ждёт сброса: до тридцати секунд по протоколу (`WRITER_CLOSE` ждёт `long_timeout`). Сорок — это тридцать на сброс и запас на всё остальное. Срок короче — и SIGKILL придёт посреди сброса: остановка станет падением, захват не отпустится, и следующий держатель тома будет ждать 45 секунд.

**Осушение спрашивает `pending_writes`, и регистратор говорит ноль.** Перед плановым выключением сервера оператор его осушает (М10A, урок 17): `safe` истинно, когда на сервере не осталось единиц и каждый воркер сказал в heartbeat'е `pending_writes: 0`. Регистратор этого числа не переопределяет — у него ноль базы: кадры уходят в писателя тома в демоне, а не в очередь на диске процесса, и то, что ещё в писателе, `after_stop` сбрасывает до того, как отпустить захват. Очередь в самом процессе — спул файлового архива — удалена (ADR 0023), а с ней и причина говорить не ноль.

**`Environment=BOX_ID=%m` — какая это коробка.** Холд сетевого тома переходит к перезапущенному регистратору сразу, без 50 секунд ожидания, только если тот на **той же коробке**: тогда это тот же демон, и демон держит одного писателя на том (урок 10, `hold_follows_name`). «Та же коробка» определялась по хосту в имени экземпляра, `host:pid:rnd`, а хост был `socket.gethostname()`. На двух коробках с одним именем (`localhost`, `fedora`, два клона одной ВМ) второй экземпляр брал холд сразу и монтировал том через шесть секунд. Двух писателей не было — их остановила ограда движка (патч 07), — но и запаса ожидания не оставалось (восьмое ревью, minor). Теперь хост в имени — `BOX_ID`, если среда его задала (`box_instance`), иначе по-прежнему имя хоста. Юнит задаёт machine id systemd: `%m` подставляет сам systemd на хосте, когда разворачивает `ExecStart`, который Quadlet собрал из `Environment=`. В кластере М11 юнит регистратора задаёт то же (`Environment=BOX_ID=%m` в `vms-recworker.service`). Клон ВМ, у которого `/etc/machine-id` скопирован вместе с диском, для этого правила — та же коробка; `systemd-machine-id-setup` при первой загрузке это исправляет. Тест: `test_rec_volume.py::test_the_host_a_hold_follows_the_name_on_is_the_box_not_its_hostname`.

**Какое имя хоста видит контейнер Quadlet с `Network=host`** (вопрос восьмого ревью). `Network=host` отдаёт контейнеру сетевое пространство имён хоста, но не пространство UTS — то, где живёт имя хоста. В документации podman `--hostname` применим только при собственном UTS (`--uts=private`, по умолчанию), а имя хоста коробки контейнер получает при `--uts=host`. Если podman не копирует имя хоста в собственный UTS при сети хоста, контейнер видит своё имя по умолчанию, то есть id контейнера. Тогда до `BOX_ID` каждый перезапуск регистратора снова ждал бы 50 секунд, и обратная связь CF не вернулась бы. Проверить это поведение podman без podman не на чем, и курс на него больше не опирается: хост берётся из `BOX_ID`, а не из имени.

## Шаг 6 — Процессы VMS — клиенты служб платформы

Ресурс, консоль и контроллеры — процессы платформы от `w2c`, и в группах VMS они не состоят (ADR 0023, ADR 0030; урок 21 М10A, шаг 4). Архив событий — тоже платформы: `/data/platform/events` принадлежит `w2c`, режим 2770, группа `w2c-events`, setgid, и бакеты в нём удаляет, зеркалит и восстанавливает только ресурс. Процессы VMS пишут свои бакеты как **клиенты** этой службы.

**Каждый пишущий процесс VMS входит в `w2c-events`.** Держатель, регистратор, детектор, скан, наблюдение, вычислитель — `GroupAdd=2102` и маска 0007 в юните. И шлюз, хотя событий он не пишет: каждый процесс со слотом **регистрируется** в архиве (`.workers`, `vms/__main__._present`), и ресурс по этой регистрации говорит, жив ли процесс. У шлюза архив не был смонтирован — регистрация ложилась в слой контейнера, ресурс её не видел, и зависший шлюз считался «не числится»: слот отпускался, на камеры вставал второй шлюз (двенадцатое ревью, major 5). Теперь `liveworker@.container` монтирует архив и входит в его группу, а тест сверяет каждую точку входа VMS, которая зовёт `_present`, с её контейнером: `test_deploy_units.py::test_every_process_that_registers_with_the_resource_mounts_the_events_archive`.

**Процессы VMS — root в своих контейнерах, и группы им всё равно нужны.** Root проходит мимо прав, но файлы, которые он создаёт под маской 0007 в каталоге с setgid, — группы каталога и открыты ей на запись: каталоги 2770, файлы 0660. Ресурс от `w2c`, член группы, удаляет их, хотя файл не его. Без маски каталоги клиента выходят 2755, и хранение молча перестаёт удалять. Тест платформы `test_the_resource_as_w2c_deletes_a_bucket_a_client_of_w2c_events_wrote` проверяет это на бакетах камеры и регистратора — так, как проверило бы ядро для процесса другого uid, связанного с деревом только группой. Хранилища устроены так же: `config/` и `objects/` — группы `w2c-store`, и каждый юнит VMS в ней с той же маской.

**Видео в архиве событий нет.** Оно в томах, за демоном хоста, а ресурс платформы не знает, что такое видео. Собственный том сервера — у VMS, в `/data/vms/obsd/volume` (`config.OWN_VOLUME`), а не под `/data/platform/events`: там обходы ресурса приняли бы кольцо за дерево событий и посчитали бы его блоки занятым местом.

## Шаг 7 — Один образ

```dockerfile
FROM docker.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-gi python3-yaml python3-cryptography \
        gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
        gir1.2-gst-plugins-base-1.0 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY w2cplatform w2cplatform
COPY vms vms
COPY gstvms gstvms
ENV PYTHONPATH=/app
ENV SPEC_DIR=/app/vms
CMD ["python3", "-m", "vms", "worker"]
```

**Один образ на все процессы** — и платформы, и VMS. Не образ на глагол: различие между процессами — в аргументе и в токене, а не в содержимом. `SPEC_DIR` говорит процессам платформы, где спеки, по которым они работают: в образе это спеки VMS.

Публиковать надо одно; версия одна; обновление атомарно для всей коробки.

`COPY` три раза, и тест это проверяет:

```python
    copied = re.findall(r"^COPY (\S+) ", cf, re.M)
    assert copied == ["w2cplatform", "vms", "gstvms"]
    assert "postgres" not in cf.lower()                                                # the per-box database is gone (М10 Lesson 1)
```

**Три пакета — и это граница модуля, проверяемая сборкой.** Появился четвёртый — тест падает, и надо объяснить, зачем он.

**`obsd` в образе нет, и это тоже граница.** Клиент демона — `vms/obsd.py`, чистый Python над unix-сокетом, и он в образе: движок архива — VMS, и клиент его тоже. Сам движок — на хосте (шаг 5). Положи бинарник в образ — и каждый контейнер получит возможность запустить свой демон, то есть ровно то, от чего шаг 5 защищает.

`postgres` в образе не должно быть ни в каком виде. В М9 на коробке был свой Postgres, хранивший желаемое состояние; М10 его убрала (правда теперь в хранилищах платформы). Тест сторожит, чтобы он не вернулся «на время».

Ни `pip install`, ни `requirements.txt`, ни виртуального окружения: **всё из системных пакетов Debian**. `python3-yaml` вместо `pyyaml` из PyPI. Зависимости обновляются с системой, и сборка не ходит в интернет за пакетами.

`CMD` по умолчанию — `worker`, и юниты всё равно повторяют `Exec=` явно. Дублирование намеренное: юнит должен читаться сам по себе, не требуя заглянуть в образ.

## Шаг 8 — `vms.env` на разделе данных, `/etc/vms` — ссылка

```
# /etc/vms/vms.env — the VMS subsystems' half of this box's environment: capacity, media, the recorder's volume
# and the evaluator's knobs. Every unit reads it after `w2c.env` (the platform's half). /etc/vms is a LINK to
# /data/vms/etc: on the data partition, never in a rootfs slot (М9 Lesson 5) — an OS update must not change which
# volume this box records into.
```

Последняя фраза — и за ней весь урок 5 М9.

Коробка имеет **A/B-корень под RAUC**: два слота операционной системы, обновление пишет в неактивный и переключает. Файл в корне при переключении слота **заменяется файлом из нового образа**.

Конфигурация коробки — какая ёмкость, какой архив, какое имя — переживать обновление обязана. Поэтому она на разделе данных, который обновление не трогает.

**Файлов два: платформы и VMS** (правило продукта о платформенных именах, 3 октября). `/etc/w2c/w2c.env` — половина платформы: её каталог, архив событий, хранилище, имя сервера, метки, номер коробки (урок 21 М10A, шаг 7). `/etc/vms/vms.env` — настройки подсистем VMS. Каждый юнит называет оба, платформы — первым: `EnvironmentFile=/etc/w2c/w2c.env`, затем `EnvironmentFile=/etc/vms/vms.env`; имя, заданное в обоих, берётся из второго.

**Пути — продукта, а файлы — на разделе данных** (ADR 0023). Конфигурация VMS — в `/data/vms/etc/` (`vms.env`), и `/etc/vms` — **ссылка** туда, так же как `/etc/w2c` — ссылка в `/data/platform/etc` (урок 21 М10A, шаг 5). Юниты и код называют `/etc/vms/…`, а не то, куда ведёт ссылка. Ссылку на обычном сервере кладёт `install-obsd.sh` (`link_etc "$R/etc/vms" "$R/data/vms/etc"`; на A/B-коробке продукта — образ) и ничего не удаляет: настоящий каталог сначала **переносится** в `/data`, `/data/config/vms.env` — в `/etc/vms/vms.env`. Файл, который уже лежит на месте, остаётся, а перенесённый ложится рядом как `<имя>.from-config`. Кольцо на `/data/volume` под демоном не переносится: скрипт пишет в `vms.env` `ARCHIVE_VOLUME=file:///data/volume`, и коробка пишет туда, где её записи. Тест: `test_deploy_units.py::test_install_obsd_moves_the_old_layout_into_data_and_links_etc_deleting_nothing` — запускает скрипт в песочнице (`INSTALL_ROOT`), проверяет ссылки и каждый файл и запускает второй раз: ничего не движется и не повторяется.

**На macOS `/data` нет, и коробка там — каталог** (тринадцатое ревью, major 15). Установщик М11 требует `--box <каталог>` и кладёт под него код, оба файла окружения, ключ и состояние; plist'ы называют каталог и работают от пользователя. Подробно — урок 3 М11, шаг 6.

**Свои пути VMS — в своём коде.** Архив событий процессы VMS спрашивают у функции платформы, `runtime.events_root` (урок 21 М10A, шаг 5): база воркера (`Worker`, а с ней каждый класс воркеров VMS, регистратор тоже) и каждая точка входа. Свои пути VMS держит в `vms/config.py` (`VMS_DATA`, `OWN_VOLUME`). Регистратор, которому не сказали ничего, пишет события в архив платформы, а свой том форматирует там, где VMS держит тома: `test_a_recorder_told_nothing_keeps_its_events_in_the_platforms_archive_and_its_volume_where_the_vms_keeps_volumes`.

**Ключ кластера — файл платформы**, `/etc/w2c/secrets/platform.key` (урок 21 М10A, шаг 6). Из процессов VMS его монтируют двое, которые открывают запечатанное: держатель — пароль камеры (урок 19) — и регистратор — секрет сетевого тома (урок 10). У обоих `/run/secrets/platform.key`, `SECRETS_KEY` и группа `w2c-secrets`; остальным воркерам VMS ключ не нужен и не смонтирован. Юниты запасных читают ту же пару файлов окружения и её же отдают запасному.

`w2c.env.example` и `vms.env.example` — то, что `install-obsd.sh` кладёт на коробку, где файлов ещё нет, с комментарием у каждой переменной. Тест сторожит обязательные — и то, чего быть не должно:

```python
    env = open(os.path.join(DEPLOY, "vms.env.example")).read()
    platform = open(os.path.join(DEPLOY, "w2c.env.example")).read()
    assert "PLATFORM_DIR=/data/platform" in platform and f"RESOURCE_ROOT={EVENTS}" in platform   # the events archive is the platform's
    assert "CAPACITY=" in env
    assert "SPOOL=" not in env and "SEGMENT_SECONDS=" not in env
```

А что каждое имя — в своей половине и только там (`RESOURCE_ROOT` — платформы), что юниты запасных читают обе и что ключ — в трёх юнитах и ни в одном больше, сторожит `test_deploy_units.py::test_the_platforms_settings_and_the_vmss_are_two_files_every_unit_reads`.

`SPOOL` и `SEGMENT_SECONDS` ушли вместе с файловым архивом: очереди на диске нет, а длину куска решает движок — блоками и последовательностями (урок 7). Вторая строка теста не даёт им вернуться в пример, который копируют на коробки.

Пришли четыре переменные архива, все закомментированы — у каждой есть разумное умолчание:

```
# the server's own volume, where a recorder with nothing declared writes: a volume of ObjectStorage, opened by
# the host's obsd (`obsd.service`) as `vms-obsd`. Unset: `/data/vms/obsd/volume` (`vms/config.py`, `OWN_VOLUME`):
# the archive engine is the VMS's, and so are its volumes — under `/data/vms/obsd`, never inside the platform's
# events archive, where the resource's walks would take the ring for events. A box set up before this layout keeps
# its ring where it is: `install-obsd.sh` writes `ARCHIVE_VOLUME=file:///data/volume` here when it finds one there.
# ARCHIVE_VOLUME=file:///data/vms/obsd/volume
# its size when it is first formatted — a ring: it never grows past it, and gives up its oldest minutes when
# full. Unset: four fifths of what is free, leaving two gigabytes and the disk under the watermark's low mark
# once the ring is full — of the disk the volume is on as the DAEMON sees it (`VOLUME_SPACE`), not the recorder's
# container, where the volume is not mounted. A volume that exists keeps its size until a declaration
# (`rec/volumes/<name>`) says another.
# ARCHIVE_QUOTA_BYTES=
# the host's ObjectStorage daemon: /run/vms-obsd/obsd.sock, where `obsd.service` puts it — set in the recorder's own
# unit, the one process that mounts that directory. How long a recorder waits for one answer from it: shorter
# than a lease, or a silent daemon fences every recording.
# OBSD_SOCKET=/run/vms-obsd/obsd.sock
# OBSD_TIMEOUT=10
```

**`ARCHIVE_VOLUME`** — где собственный том сервера. Движок архива — VMS, а не платформы, и его тома — у VMS, под `/data/vms/obsd` (ADR 0023), а не в архиве событий платформы: там обходы ресурса приняли бы кольцо за дерево событий и посчитали бы его блоки занятым местом. Умолчание говорит точка входа регистратора (`config.OWN_VOLUME`), а не сам регистратор: его запасное «рядом с деревом событий» теперь означало бы каталог платформы.

**`ARCHIVE_QUOTA_BYTES`** — размер собственного тома сервера, когда он форматируется впервые. Квота — это размер кольца (урок 10, шаг 3), и спрашивается она один раз: отформатированный том свой размер не меняет, пока объявление не скажет другой. Без неё — четыре пятых свободного места, но не больше, чем держит диск под нижней отметкой ватерлинии, когда кольцо заполнится.

**`OBSD_SOCKET`** — где демон: `/run/vms-obsd/obsd.sock`. Его задаёт юнит регистратора — единственного процесса, который этот каталог монтирует; умолчание клиента совпадает. Размер нового тома без `ARCHIVE_QUOTA_BYTES` спрашивается у демона (`VOLUME_SPACE` того каталога, куда он будет писать), а не у диска контейнера: на коробке с системным SSD и HDD под данные доля SSD дала бы пару часов архива (четвёртое ревью).

**`OBSD_TIMEOUT`** — сколько регистратор ждёт одного ответа демона. Десять секунд — треть аренды. Поставь больше аренды — и один молчащий демон отсечёт регистратор со всеми записями (урок 10, шаг 10).

Примечание перечисляет, чего **нет** в файле VMS и почему: `WORKER_NAME=%i` — в юните воркера (это слот, а не настройка коробки); `CONSOLE_HOST`/`CONSOLE_PORT` — в юните консоли; `SECRETS_KEY` — в трёх юнитах, куда смонтирован ключ; `OBSD_SOCKET` — в юните регистратора; имена платформы — в `w2c.env`.

**Настройка коробки против настройки экземпляра** — разделение, которое стоит держать: первое в файле окружения, второе в юните. Демон движка в общий файл не смотрит вовсе: его настройки — в его юните, потому что он не процесс VMS.

## Шаг 9 — Юниты как код

```python
def test_the_units_run_the_entrypoints_the_package_has():
    from vms import __main__ as m  # noqa: F401  (imports the module without running it: no __name__ == "__main__")
    from w2cplatform import host
    entrypoints = set(re.findall(r'"(\w+)": \w+', open(os.path.join(HERE, "vms", "__main__.py")).read().split("__main__")[-1]))
    assert entrypoints == {"worker", "recorder", "gateway", "detworker", "detjobworker", "surveyworker", "autoworker",
                           "jobs", "domainpart"}
    …
    # every subsystem's controller is an instance of the platform's one template (ADR 0023): `w2c-controller@<sub>`
    platform = {"w2c-controller@.container": "%i"}
    assert {f[:-len(".subsystem.yaml")] for f in os.listdir(os.path.join(HERE, "vms")) if f.endswith(".subsystem.yaml")} \
        == {"vms", "rec", "live", "det", "detjob", "survey", "auto"}                    # the instances the image has specs for
    assert not [n for n in os.listdir(DEPLOY) if n.endswith("controller.container")]   # no controller of a subsystem's name
    …
    for name, entry in [("vmsworker@.container", "worker"), ("w2c-resource.container", "resource"),
                        ("w2c-console.container", "console"), ("vmsjobs.container", "jobs"), …, *platform.items()]:
        u = unit(name)
        assert u["Container"]["Image"] == "localhost/vmsserver:latest"                 # one image, one thing to publish
        …                                                                              # the platform's: `python3 -m w2cplatform …`
        else:
            assert u["Container"]["Exec"] == f"python3 -m vms {entry}"
        # /etc/w2c and /etc/vms, links into the data partition; the platform's half first, the VMS's after it
        assert u["Container"]["EnvironmentFile"] == ["/etc/w2c/w2c.env", "/etc/vms/vms.env"]
        for vol in …:
            assert vol.startswith(("/data/", "/run/vms:", "/run/vms-obsd:", "/run/w2c-console:",   # sockets on a tmpfs, not state
                                   f"{KEY}:")), vol                                              # the key ring: one file
```

**Таблица диспетчера извлекается регулярным выражением из исходника** и сверяется с юнитами. Здесь видны все девять глаголов VMS — четыре воркера этого урока, три воркера уроков 21–25, `jobs` и `domainpart` держателя домена, — а рядом глаголы платформы, которые знает её хост (`host.USAGE`: `controller <sub>`, `resource`, `console`). Контроллера с именем подсистемы среди юнитов нет ни одного: только экземпляры шаблона платформы, по одному на спеку образа.

Приём грубый — и он ловит то, что иначе не ловится ничем: юнит, зовущий несуществующий глагол, или глагол, которому не соответствует ни один юнит. Обе ошибки обнаруживаются при запуске на коробке, то есть в худший момент.

`from vms import __main__ as m` — импорт **без запуска**: в модуле есть `if __name__ == "__main__"`, и при импорте он не срабатывает. Проверяется, что модуль вообще импортируется — то есть все подсистемы собираются.

И последнее утверждение: **каждый том начинается с `/data/`, `/run/vms:`, `/run/vms-obsd:`, `/run/w2c-console:` — или это файл ключа**. Ни одного монтирования из корня, ни `/var`, ни сокета докера. Всё состояние коробки — на разделе данных, плюс три tmpfs: разделяемая память воркеров, сокет демона (с четвёртого ревью — свой каталог, правило пришлось расширить) и сокет консоли. Единственный путь под `/etc` — `/etc/w2c/secrets/platform.key`, одним файлом, и он тоже на разделе данных: `/etc/w2c` — ссылка в `/data/platform/etc`.

Это правило, за которым стоит следить в любой системе: **если контейнер монтирует что-то из корня, объясните зачем.** Обычно объяснения нет.

## Шаг 10 — Проверка здоровья

Последнее соединение модуля: что читает проверка здоровья коробки.

Своей проверки в `deploy/` нет. `curl` в образе положен ровно для неё — для `podman healthcheck` или ручной проверки `/metrics`, — а читать ей предлагается число, которое называет спецификация регистратора:

```yaml
console:
  running: recordings_running          # rec_recordings_running: recordings whose pipeline is writing — what the health check reads
```

`rec_recordings_running` — сколько записей **действительно пишутся**, а не сколько настроено. Консоль платформы считает его по heartbeat'ам всех живых регистраторов, как велит `metrics:` спеки, и отдаёт на `/rec/metrics` (урок 10, шаг 13).

Смотреть на файлы архива, чтобы убедиться, что он пополняется, теперь не на что: видео в томе, за демоном, и каталог тома — не дерево файлов, которое кто-то обходит. Зато «пополняется» стало числами, которые регистратор публикует сам, и консоль отдаёт их рядом:

- `rec_last_frame_age_seconds` — сколько секунд назад запись последний раз что-то получила от источника;
- `rec_writer{state}` — доходит ли отданное писателю до кольца: `ok`, `stuck`, `losing`;
- `rec_archive_failure{kind}` и `rec_archive_away_seconds` — том не берёт кадры, по какой причине и как долго;
- `rec_volume_error` — регистратор держит том, который не открывается.

**Интерфейс наблюдаемости пережил полную перестройку системы — и стал точнее.** М9 знала один процесс, пишущий видео в файлы; М10 разложила его на воркер, регистратор, ресурс, контроллеры и демон движка. Метрика «пишется» осталась той же, а вопрос «доходит ли» получил собственные числа вместо взгляда на каталог.

## Результат

```bash
deploy/install-obsd.sh                       # vms-obsd (2101), w2c (2100) и группы клиентов, /etc/w2c и /etc/vms — ссылки в /data, каталоги, кольца — vms-obsd, юнит
systemctl start w2c-resource w2c-console w2c-controller@vms w2c-controller@rec vmsjobs
systemctl start vmsworker@w-1 recworker@r-1
systemctl start w2c-controller@live liveworker@g-1
systemctl start w2c-controller@det detworker@d-1
```

Ключ, образ и юниты платформы ставятся, как в «Результате» урока 21 М10A; юниты Quadlet не включают `systemctl enable` — на загрузку их ставит генератор Quadlet.

Одиннадцать процессов — шесть платформы от `w2c` (ресурс, консоль, четыре экземпляра контроллера) и пять VMS, — один образ, два файла окружения (платформы и VMS) и один демон хоста под ними.

```bash
curl -X POST localhost:8080/cameras -H 'Idempotency-Key: a1' \
     -d '{"source":"driverpack://file/lobby.mp4"}'
```

За один проход камера держится; heartbeat говорит `live_url: rtsp://box:8554/1`. И одна строка, которую стоит знать после установки: сетевой том регистратор берёт только на `obsd` с патчем 07 (`WRITER_ABANDON`: движок, который умеет отдать том, когда его взяла другая коробка). На коробке со старым демоном регистратор говорит это в своём heartbeat'е под `refused`, словами, по которым можно действовать, — `obsd on <сервер> is too old to write <том> safely …`; собственные диски коробки это не трогает. Нажали «Запись» — регистратор форматирует том сервера `/data/vms/obsd/volume` и пишет поток `1/e1`. Записанные минуты видны, когда закрывается их блок (урок 8).

```bash
systemctl stop w2c-controller@vms      # ничего работающее не останавливается
systemctl kill -s KILL vmsworker@w-1    # регистратор переподписывается под новой эпохой
systemctl kill -s KILL recworker@r-1    # писатель ждёт в демоне; поднятый регистратор подбирает его целиком
systemctl restart obsd                  # регистраторы держат тома как away и открывают их заново
```

Четыре команды — четыре свойства, обещанные в модуле.

## Что может пойти не так

- **Новый `obsd` поверх запущенного файла на macOS.** `cp -p` новым бинарником поверх прежнего — и процесс убивается при старте (SIGKILL, код 137): ядро держит кеш подписи прежнего файла. Класть новым файлом — удалить, потом копировать (обратная связь CP).

- **`vms.env` в корневом разделе.** Обновление системы поменяет, в какой том пишет коробка. `/etc/vms` — ссылка в `/data/vms/etc`, а не каталог.
- **Процесс VMS, монтирующий `/data/platform` целиком.** Ключ кластера достанется root'у в контейнере с драйвером стороннего производителя. Монтируются `config/`, `objects/`, `events/` — по одному.
- **Клиент архива с маской 0022.** Его каталоги — 2755, и ресурс (`w2c`) не удалит из них ни одного бакета: хранение молча перестаёт удалять.
- **Процесс со слотом без архива событий.** Его регистрация ляжет в слой контейнера, ресурс скажет «не числится», и на его единицы встанет второй.
- **Образ на глагол.** Дюжина публикаций, дюжина версий и дюжина способов рассинхронизироваться.
- **Токен на подсистему вместо токена на процесс.** Ошибка в консоли сможет переразместить камеры.
- **Медиа, смонтированные регистратору.** Второе соединение к камере станет возможным — и однажды случится.
- **Демон движка внутри контейнера регистратора.** Два регистратора — два демона, два писателя одного тома и порча вместо отказа.
- **Юнит без `RuntimeDirectoryMode=0750`.** Демон сам создаст каталог сокета 0700, и ни один регистратор до сокета не дойдёт.
- **Пользователь из юнита, которого никто не создал.** 217/USER, демона нет, запись стоит; на обновлённой коробке — кольца root, которых демон не откроет. Для этого `install-obsd.sh`.
- **`chown` под работающим демоном и `enable --now` в конце.** Старый демон досоздаёт блоки root'а за спиной `chown` и остаётся работать под старым юнитом; тома `away`, пока его не перезапустят руками. Сначала `stop`, в конце `restart`.
- **`/run/vms` из юнита демона.** Без демона не стартуют ни воркер, ни регистратор; каталог — коробки (`vms.tmpfiles`).
- **Имя платформы в файле VMS или наоборот.** `PLATFORM_DIR` в `vms.env` переопределит `w2c.env` молча: второй файл побеждает. Тест держит каждое имя в своей половине.
- **`OBSD_WRITER_GRACE_S` короче истечения захвата.** Следующий держатель тома не застанет писателя.
- **`StopTimeout` регистратора короче сброса писателя.** Штатная остановка станет падением, и том 45 секунд никто не возьмёт.
- **`TimeoutStopSec` демона короче шестидесяти секунд.** Писатели не успеют закрыться чисто, и тома после остановки придётся восстанавливать. «Чисто» здесь — для томов этого хоста: писателя сетевого тома, который уже взяла другая коробка, движок с патчем 07 — сборка, которую курс требует, — останавливает, не сбрасывая в чужой том и не трогая чужого замка.
- **Путь собственного тома, смонтированный в контейнер по другому пути.** Регистратор назовёт демону путь, которого на хосте нет.
- **Монтирование из корня.** Состояние коробки перестанет быть на разделе данных, и обновление начнёт его трогать.
- **Юниты, не проверяемые тестом.** Опечатка в `Exec=` обнаружится на коробке.
- **`pip install` в образе.** Сборка пойдёт в интернет, а зависимости перестанут обновляться с системой.

## Итог

- У процессов коробки два хозяина: контроллеры всех подсистем, ресурс и консоль — платформы, от `w2c`, по спекам (урок 21 М10A); у VMS — её воркеры и `jobs` и её спеки в образе. Контроллер подсистемы — экземпляр одного шаблона платформы, `w2c-controller@<sub>`.
- Три токена разбивают `vms/*` на непересекающиеся части, и обе ACL вырезаны из одной YAML.
- Монтирования повторяют ACL в байтах: у контроллера только архив событий для его журнала, у регистратора нет медиа, спула нет ни у кого — видео за демоном.
- Имя экземпляра systemd — это слот, и супервизор является авторитетом по вопросу, кто сейчас `w-1`.
- Движок архива — демон хоста, один на коробку: правило «один писатель на том» значит что-то, только если все регистраторы спрашивают один демон.
- Сроки выводятся из того, что делает остановка: ожидание писателя (90 с) длиннее истечения захвата (45 с), остановка регистратора (40 с) длиннее сброса (30 с), остановка демона (60 с) — по README.
- Один образ, три пакета, ни одного `pip install` и ни одного `obsd`; `vms.env` на разделе данных, а `/etc/vms` — ссылка туда, потому что обновление не должно менять, куда пишет коробка.
- Пишущие процессы VMS — клиенты служб платформы: группа `w2c-events`, setgid, маска 0007; бакеты удаляет только ресурс, а каждый процесс со слотом монтирует архив, чтобы ресурс видел его регистрацию.
- Юниты читаются тестами: опечатка в `Exec=` ломает сборку, а не коробку.

## Упражнения

1. Замените ссылку `/etc/vms` настоящим каталогом с тем же `vms.env`. Проведите обновление системы через RAUC и посмотрите на `CAPACITY` и `ARCHIVE_VOLUME`.
2. Смонтируйте регистратору `/data/media`. Опишите, чем это опасно через год.
3. Поставьте `StopTimeout=10` у `recworker@`. Остановите регистратор посреди записи и посмотрите, сколько ждал следующий держатель тома и что он нашёл в томе.
4. Поставьте `OBSD_WRITER_GRACE_S=20`. Убейте регистратор `kill -9` и проследите, кто и когда возьмёт том.
5. Уберите `RuntimeDirectoryMode=0750` из `obsd.service`, удалите `/run/vms-obsd` и перезапустите демон. Что видит регистратор и что говорит его `volume_error`?
6. Уберите `ARCHIVE_VOLUME` и умолчание `OWN_VOLUME` из точки входа регистратора. Где он отформатирует том сервера и что об этом скажет обход ресурса?
7. Уберите `PodmanArgs=--umask=0007` из юнита детектора. Через сутки посмотрите, что удалил проход хранения ресурса и что осталось под `det/`.
8. Соберите образ с `obsd` внутри и запустите демон в каждом контейнере регистратора. Объявите сетевой том и поднимите два регистратора на одной коробке. Что пойдёт не так и почему ни один из двух этого не заметит?
9. Соберите отдельный образ для консоли. Перечислите, что теперь надо делать при выпуске новой версии.
10. Дайте консоли токен всей подсистемы. Напишите в ней вызов `place` и посмотрите, что произойдёт.
11. Добавьте в `Containerfile` четвёртый `COPY`. Запустите тесты.
12. Смонтируйте `/var/run/docker.sock`. Объясните зачем — и если объяснения нет, сформулируйте правило.

## Что дальше

Коробка собрана: строка камеры, цикл сверки из М9, воркер, который держит устройство и не пишет его, элемент GStreamer, движок архива за демоном, регистратор, ресурс, консоль, живое видео, детекторы, чужой архив и дозапись из края — и всё это как процессы платформы и VMS и один демон на коробке из М9.

Граница, проведённая в М10A, выдержала четыре подсистемы: `test_lesson1_platform.py::test_the_platform_knows_nothing_about_its_subsystems` зелёный. Ни одного импорта из `vms/` под `w2cplatform/`, а процессы платформы на коробке — контроллеры, ресурс, консоль — работают по спекам из `SPEC_DIR`. Клиент движка архива, `obsd.py`, лежит по эту сторону границы, у VMS: движок архива — VMS, и клиент его тоже.

Остался один вопрос, который коробка задаёт раньше кластера: что архив отдаёт первым, когда кольцо замкнулось. [**Урок 18**](18-what-the-archive-gives-up-first.md) отвечает на него за подсистему.

[**М11 — кластер платформы**](../М11_Cluster/README.md) начинает с того, что коробок несколько: хранилище — `configstore` на raft (ADR 0021), те же контроллеры, воркеры и ресурс — юнитами systemd на каждом сервере, и запасные, которых поднимает скрипт по тому самому запасу, который воркеры публикуют с урока 4.

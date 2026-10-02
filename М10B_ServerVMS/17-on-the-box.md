# Урок 17 — На коробке

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/__main__.py` — десять точек входа, каждая со своим токеном; `deploy/` — по юниту Quadlet на процесс, `obsd.service` для движка архива, `Containerfile`, `vms.env.example`; `tests/test_deploy_units.py` — четыре теста, читающие юниты как код.
**Время:** ~85 минут.

## Зачем этот урок

Последний урок модуля, и новых мыслей в нём почти нет. Всё, что в нём есть, — склейка написанного: какой процесс с каким токеном, что куда монтируется, что говорит `systemctl`.

Проектная записка объясняет, почему это один урок, а не три:

> *Всё, что в нём есть, — это склейка уже написанного. Растягивать её на три урока значило бы объяснять `Volume=` трижды.*

Но одна вещь в уроке важнее склейки, и ради неё он написан: **монтирования повторяют ACL**.

Токен контроллера не пишет ни строк камер, ни событий — и архива у него нет вовсе. Регистратор никогда не открывает камеру — и файлов камер ему не смонтировано. Видео не смонтировано никому: оно в томах, за демоном движка. Одно и то же разграничение выражено дважды: в хранилище и в файловой системе.

Тест `test_who_may_write_where_is_in_the_mounts_too` проверяет это буквально, и его название — тезис урока: **«кто где может писать — это и в монтированиях тоже»**.

Второе: **юниты читаются как код**. Четыре теста разбирают юниты и сверяют их с пакетом. Развёртывание перестаёт быть тем, что «правится на месте», и становится тем, что ломает сборку.

И третье, новое: **одна вещь на коробке — не контейнер**. Движок архива, `obsd`, — демон хоста со своим юнитом systemd. Почему не контейнер образа и почему один на коробку — шаг 5.

> **Проверка без железа.** Четыре теста урока — да: они читают файлы и импортируют модуль. Настоящий запуск — коробка из М9 с podman и `obsd`, собранным из исходников ObjectStorage (шаг 5).

## Что нужно знать заранее

- **Уроки 1–14** — все четыре подсистемы: урок их расставляет.
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

## Шаг 1 — Десять точек входа

```python
"""python3 -m vms worker|controller|recorder|reccontroller|console|resource|gateway|livecontroller|detworker|detcontroller — the box's processes.
```

Четыре подсистемы дают **десять процессов**:

| Подсистема | Контроллер | Воркер | Особый |
|---|---|---|---|
| `vms` | `controller` | `worker` | `console`, `resource` |
| `rec` | `reccontroller` | `recorder` | — |
| `live` | `livecontroller` | `gateway` | — |
| `det` | `detcontroller` | `detworker` | — |

Четыре контроллера, четыре воркера, консоль и ресурс. **Шесть из десяти — один и тот же класс с другой спецификацией**: контроллеры это `SpecController`, различающиеся строкой YAML. Уроки 20–25 добавят ещё три пары — сканы, наблюдение за чужими архивами, автоматизацию — тем же способом, и тест в шаге 9 перечисляет уже все шестнадцать.

Докстрока модуля — **справочник по окружению**, и стоит заметить одну строку:

```
CAPACITY=50                      cameras this worker can carry — exported as headroom for the autoscaler
RECORDER_NAME=r-1                a recorder's slot (systemd: %i); CAPACITY here is recordings — this server's disks and NIC
GATEWAY_NAME=g-1                 its slot (systemd: %i); CAPACITY here is viewers
DET_NAME=d-1                     a detector worker's slot; CAPACITY here is streams; NOMAD_META_labels=gpu says where it is
```

**Одна переменная, четыре значения.** Примечание к файлу это подчёркивает: `CAPACITY` означает разное в зависимости от глагола.

Спорно ли это? Немного: `WORKER_CAPACITY`, `RECORDER_CAPACITY` были бы однозначнее. Выигрыш от одного имени — в том, что оно **общее для шаблона подсистемы**: воркер, регистратор, шлюз и детектор читают одну переменную, потому что они один класс. Различие — не в имени переменной, а в том, что каждая подсистема считает своей единицей ёмкости (уроки 4, 10, 13, 14).

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

| Процесс | Что пишет |
|---|---|
| `vmscontroller` | `vms/workers/*`, `vms/placement/*`, `vms/slots/*` |
| `console` | `vms/cameras/*`, `vms/next_id`, `vms/retention/*`, `vms/idem/*` |
| `vmsworker` | `vms/epoch/*`, `vms/slots/*`, `vms/holds/*`; с урока 25 — ещё `vms/devices/*` (`config.WORKER_ACL`) |

**Ни один не может делать работу другого.** Консоль, у которой завёлся бы код размещения, получила бы `Forbidden` (урок 3 М10A). Воркер, попытавшийся поправить строку камеры, — тоже.

Обе ACL вырезаны из **одной спецификации** (`SPEC.acl_console()`, `SPEC.acl_controller()`, урок 10 М10A). Добавили поле — обе обновились; нового места для рассинхронизации не появилось.

То же правило у регистратора, и урок 10 рассказал, как его однажды нарушили: процесс `recorder` открывал хранилище со списком прав, написанным руками, и без `rec/holds/*` не мог взять собственный том. Теперь его права — `REC_SPEC.sub.acl_worker()`, выведенные из спецификации (`test_the_recorder_process_holds_a_token_that_can_take_a_volume`).

И примечание договаривает:

> *The mounts in `deploy/` repeat the same split in bytes.*

## Шаг 3 — Монтирования как вторая ACL

Вот тест — он короче, чем объяснение:

```python
def test_who_may_write_where_is_in_the_mounts_too():
    """The ACL says which rows each token writes; the mounts say which bytes.
    The controller has no archive at all; footage is mounted nowhere — it is behind the host's obsd."""
    vols = lambda n: dict(v.split(":", 1) for v in (lambda x: x if isinstance(x, list) else [x])(unit(n)["Container"]["Volume"]))
    assert "/data/archive" not in vols("vmscontroller.container")
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert "/data/spool" not in vols(n), n                                       # there is no spool: footage goes through obsd
    assert vols("vmsworker@.container")["/data/archive"] == "/data/archive:z"          # its events, vms/<cam>/, on this box's resource
    assert vols("vmsworker@.container")["/data/media"].endswith(":ro,z")
    assert vols("recworker@.container")["/data/archive"] == "/data/archive:z"         # its events, and its own volume's path
    assert "/data/media" not in vols("recworker@.container")                          # it never reads a camera: it subscribes to the fan-out
    assert vols("vmsworker@.container")["/run/vms"] == "/run/vms:z" == vols("recworker@.container")["/run/vms"]   # the tee's shared memory
    # the daemon's socket: the recorder's alone, never the holder's — the process with a vendor's DriverPack in it
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert ("/run/obsd" in vols(n)) == (n == "recworker@.container"), n
    rec_env = dict(e.split("=", 1) for e in unit("recworker@.container")["Container"]["Environment"])
    assert rec_env["OBSD_SOCKET"] == "/run/obsd/obsd.sock" and rec_env["SECRETS_KEY"] == "/run/secrets/vms.key"   # it opens a volume's secret
    assert "/data/archive" not in vols("reccontroller.container")
    assert vols("resource.container")["/data/platform"] == "/data/platform:z"       # the heartbeat is written; rows are only read
    assert unit("recworker@.container")["Container"]["StopTimeout"] == "40"          # the writer's close waits for its flush (30 s)
    assert "obsd.service" in unit("recworker@.container")["Unit"]["After"]
    assert unit("resource.container")["Service"]["Restart"] == "always"             # a process, not a timer: the database lives in it
```

Каждая строка — утверждение из модуля, выраженное монтированием.

**У контроллера нет архива.** Он вычисление над хранилищами (урок 1); ни событий, ни видео он не касается. Ошибка в контроллере не может испортить архив — не потому, что код правильный, а потому что архива у него нет.

**Спула нет ни у кого.** Это не строка про один юнит, а цикл по всем `.container` каталога. Видео не пишется в файлы, которые можно смонтировать: регистратор отдаёт кадры демону `obsd` через сокет, а демон пишет в том (урок 10). Цикл сторожит, чтобы локальная очередь не вернулась «на время» ни в одном юните.

**Воркеру архив на запись — только ради событий.** `vms/<cam>/`, бакеты событий камеры. В `rec/` он не пишет никогда, и это уже не монтирование, а дисциплина кода. Видео он не пишет вовсе (урок 4): стока в том в его конвейере нет (урок 9).

**Медиа воркеру только на чтение**, регистратору — **не смонтированы вовсе**, и комментарий объясняет: *он никогда не читает камеру, он подписывается на раздачу.* Регистратор, у которого нет доступа к файлам камер, физически не может открыть второе соединение.

**Регистратору архив на запись — ради его событий**: `archive.shallow`, `archive.keep.*` под `rec/` на ресурсе этого сервера. Видео здесь нет. Собственный том сервера лежит рядом, в `/data/volume` (урок 10, шаг 8), и регистратор его не монтирует: он называет путь демону, а том открывает демон на хосте. Объявленный локальный том — тоже путь на хосте, который открывает демон, и монтировать его регистратору не нужно вовсе.

**Сокет демона — в своём каталоге и только у регистратора.** До третьего ревью сокет `obsd` лежал в `/run/vms` рядом с разделяемой памятью воркеров, и процесс воркера — тот, где работает сторонний DriverPack, — мог читать запись всех камер коробки мимо прав и аудита, а в окно ожидания писателя — забрать его. Воркеру `obsd` не нужен вовсе. Теперь сокет — `/run/obsd/obsd.sock`, монтирует его один `recworker@` (`OBSD_SOCKET`, `GroupAdd`), а демон работает своим пользователем (`User=obsd`) и пускает, кроме себя, только группу `OBSD_CLIENT_GROUP` (нужна сборка демона, которая этот параметр знает). Чего по-прежнему нет: клиенты группы доверены одинаково, а владелец писателя — имя, не секрет. Ключ печатей у регистратора теперь тоже есть: ему открывать секрет сетевого тома (урок 10).

**`/run/vms` — и у воркера, и у регистратора**, одинаково на запись. Там две вещи. Разделяемая память раздачи (урок 4): воркер пишет, регистратор на том же сервере читает. И сокет демона, `obsd.sock`: через него регистратор говорит с движком. Это tmpfs, а не состояние — единственное монтирование вне `/data`, и обновление системы не обязано его сохранять.

**У контроллера записей нет архива.** Он тоже только вычисление, хотя его подсистема — про тома.

**Ресурсу хранилище платформы на запись** — ради heartbeat'а; строки он только читает.

Две последние проверки — про регистратор и его остановку: `StopTimeout=40` и `After=obsd.service`. Откуда эти числа и этот порядок — шаг 5.

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
EnvironmentFile=/data/config/vms.env
Volume=/data/platform:/data/platform:z
Volume=/data/secrets/vms.key:/run/secrets/vms.key:ro,z
Environment=SECRETS_KEY=/run/secrets/vms.key
Volume=/data/archive:/data/archive:z
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

**Супервизор — авторитет по вопросу, кто сейчас `w-1`.** Не хранилище, не предыдущий держатель. Systemd перезапустил воркера — новый забирает слот, старый (если он ещё жив) обнаружит это при следующем продлении и отсечётся (урок 4). У регистратора то же самое, и урок 10 добавил к этому том: захват идёт за слотом, а писателя тома демон держит для того же владельца.

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

**Номер спрашивают у операционной системы, а адрес берут из heartbeat'а.** Ни один подписчик никогда не знал числа: регистратор, шлюз, детектор и консоль читают `live_url` и `playback_url` из статуса камеры — с четвёртого урока. Значит число может быть нулём, а публиковать надо то, что дала система:

```python
    def serve_playback(self, host="127.0.0.1", port=None):
        srv = ThreadingHTTPServer((host, self.playback_port if port is None else port), self.playback_handler())
        self.playback_port = srv.server_address[1]          # что дал сокет, то и публикуем
```

С раздачей то же самое, только спросить надо у того, кто её открыл: `GstRtspServer` знает свой порт (`get_bound_port()`), актуатор его сообщает, воркер публикует. Дверь архива регистратора устроена так же: `ARCHIVE_PORT` по умолчанию `0`, а адрес уходит в heartbeat как `archive_url`. Правило общее и стоит того, чтобы его назвать: **процесс, открывший дверь, — единственный, кто знает её номер; остальные читают адрес.**

Умолчания при этом прежние (`8554`, `8083`, `8082`), так что коробка с одним воркером ведёт себя ровно как раньше; `auto` — это то, что делает второй экземпляр возможным, а drop-in с числом остаётся для того, кто хочет предсказуемый порт.

`Restart=always`, `RestartSec=2` — и комментарий: *процесс супервизирует конвейеры, systemd супервизирует процесс.* Перезапущенный экземпляр берёт тот же слот и поднимает свои камеры с новой эпохой — **без участия контроллера**.

`:z` на каждом томе — пересылка меток SELinux. На коробке с включённым SELinux без этого контейнер не прочитает ничего.

### Кто запускает экземпляр, которого не хватает

Шаблон отвечает на вопрос «как запустить ещё одного», но не на вопрос «кто заметит, что он нужен». На коробке автоскейлера нет, и это место, где правило «платформа не запускает процессов» оказывается неудобным: оператор завёл в консоли сетевой архив, а держать его некому.

Первый ответ — **цифра и команда**. Консоль знает, сколько процессов не хватает, и знает, чем её саму запустили, поэтому пишет строку целиком:

```
served 3/4 · 0 spare — 1 more recorder(s) needed: systemctl start recworker@r-4
```

Кнопки при этом нет намеренно. Кнопка означала бы, что у консоли есть право говорить с systemd, то есть root на своей машине — у процесса, который слушает HTTP. Цена кнопки — не строчка кода, а то, что «платформа не запускает процессов» превращается в предложение с исключением.

Второй ответ, если нажимать руками не хочется, — **таймер на хосте**:

```ini
# vms-spares.timer: раз в минуту
ExecStart=/usr/local/bin/vms-spares.sh
```

Скрипт спрашивает у консоли `/rec/volumes`, берёт оттуда **число** и сам решает, какой юнит поднять. Два правила в нём стоит прочитать, потому что они общие.

**Он берёт число, а не команду.** В ответе есть и готовая строка `how` — та самая, что показана на экране, — и скрипт её игнорирует. Выполнять под root строку, пришедшую по HTTP, — это удалённое исполнение кода с лишними шагами, каким бы дружественным ни был источник.

**У него свой потолок.** `MAX_RECORDERS` ограничивает его собственными силами: ошибка на той стороне, сообщившая «не хватает девятисот», обязана стоить строчки в журнале, а не девятисот контейнеров. Доверять числу, которое пришло снаружи, ровно настолько, насколько оно проверено, — то же правило, что у `claim_hold`, где кандидаты приходят из чужих строк.

И он ничего не останавливает. Запасной стоит несколько мегабайт и именно он превращает «завели архив» в один проход вместо одного деплоя; решение, что на коробке их слишком много, — человеческое.

Механизмов таких три — рука, этот таймер и (в кластере) автоскейлер или `vms-scaler`, — и в одной установке работает **ровно один**: два агента с мнением об одном числе дерутся. Сравнение целиком, с тем, что у всех трёх общего, — в [уроке 2 М11](../М11_ClusterVMS/04-a-name-is-a-slot.md), шаг 3.

## Шаг 5 — Движок архива: демон хоста, а не контейнер

```ini
[Unit]
Description=ObjectStorage daemon — the archive's engine, one per host
After=local-fs.target network.target

[Service]
ExecStart=/usr/local/bin/obsd --socket /run/obsd/obsd.sock
User=obsd
Group=vms-rec
Environment=OBSD_CLIENT_GROUP=vms-rec
RuntimeDirectory=obsd
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

> *Not a container and not one of the VMS's processes: the engine the recorders write their footage through, over a unix socket in /run/obsd (`w2cplatform/obsd.py`). One per host — it keeps one writer per volume, and that rule means something only if every recorder on the box asks the same daemon.*

**Почему один на коробку.** Правило «один писатель на том» держит демон (урок 6). Второй демон на той же коробке о писателях первого не знает: два регистратора, спросившие два разных демона, получили бы двух писателей одного тома — и порчу вместо отказа. Поэтому демон — не часть процесса регистратора и не контейнер рядом с каждым регистратором, а роль хоста, как файловая система. Второй экземпляр на том же сокете демон и сам не запустит: README говорит, что он берёт `flock` на `<socket>.lock`.

**Почему не контейнер образа.** Образ — это Python-пакеты курса (шаг 7), а `obsd` — программа на C++ из исходников ObjectStorage. И у демона другой жизненный цикл: регистраторы перезапускаются при каждом обновлении курса, а демон — нет, и пока он жив, писатели томов переживают перезапуски регистраторов.

Теперь каждая строка.

**`--socket /run/obsd/obsd.sock`** (до третьего ревью — `/run/vms/obsd.sock`, см. шаг 3). Сокет был в том же tmpfs, который каждый регистратор уже монтирует ради разделяемой памяти воркеров (шаг 3). Нового монтирования не понадобилось. `OBSD_SOCKET` не задан нигде, потому что это и есть путь по умолчанию на Linux — и у демона, и у клиента (`w2cplatform.obsd.default_socket`).

**`User=obsd`, `Group=vms-rec`, `OBSD_CLIENT_GROUP=vms-rec`.** Демон работает своим пользователем и пускает, кроме себя, только группу клиентов — регистраторы входят в неё по номеру (`GroupAdd=2101` в `recworker@.container`: у контейнера нет `/etc/group` хоста). Пир без группы демон отвергает сам, пир не из группы не пройдёт и права на сокет. На Linux группа учитывается любая, и дополнительная тоже; на macOS — только основная (так ответила сессия, которая ведёт движок). Нужна сборка `obsd`, которая этот параметр знает: изменение исходников от 2 октября 2026, не патч.

**`RuntimeDirectory=obsd`, `RuntimeDirectoryMode=0750`, `RuntimeDirectoryPreserve=yes`.** Каталог сокета, `obsd:vms-rec`, systemd создаёт **до** демона: сам демон создал бы его 0700, и ни один регистратор в него бы не вошёл. И не уносит при перезапуске. `/run/vms` этот юнит больше не создаёт — он общий для коробки (ниже).

### Подготовка коробки: пользователь, группа, каталоги

Юнит, который называет несуществующего пользователя, не стартует (217/USER), а без демона не пишет никто. И `/run/vms` создавал только он — без демона не стартовали ни `vmsworker@`, ни `recworker@`, которые его монтируют (четвёртое ревью, блокер 2: после третьего ревью коробку под нового пользователя не готовил никто). Поэтому у коробки три файла установки:

- `deploy/obsd.sysusers` → `/etc/sysusers.d/obsd.conf`: группа `vms-rec` с **фиксированным** номером 2101 (по нему её находят контейнеры), пользователь `obsd`, член этой группы.
- `deploy/vms.tmpfiles` → `/etc/tmpfiles.d/vms.conf`: `/run/vms` 0755 root (разделяемая память воркеров), `/run/obsd` 0750 `obsd:vms-rec` (для регистратора, который стартует раньше демона), `/data/volume` 0750 `obsd:vms-rec` (собственный том сервера — его открывает демон, значит, он и владелец).
- `deploy/install-obsd.sh`: ставит оба, отказывается, если `vms-rec` уже есть с другим номером, **один раз** отдаёт `obsd:vms-rec` кольца, отформатированные, когда демон работал от root (`/data/volume` и пути, переданные аргументами, — объявленные локальные тома), и включает `obsd.service`.

Почему не `StateDirectory=`, как у продукта (`/var/lib/vms-obsd`): `/var/lib` лежит на слоте корневого раздела, который обновление системы заменяет, а архив курса — на разделе данных (М9, урок 5). Прогон на Linux (Debian 13, systemd первым процессом): обновление с демона под root на `obsd` — кольца переданы, демон работает от `obsd`/`vms-rec`, регистратор с группой пишет, root без группы и пользователь не из группы получают отказ, `/run/vms` и `/run/obsd` создаются при остановленном демоне. Тест: `test_deploy_units.py::test_every_user_group_and_directory_a_unit_names_is_made_by_the_install_files` — каждый пользователь, группа и каталог, которые называет юнит, создаются файлами установки.

**`OBSD_WRITER_GRACE_S=90`** — сколько писатель, чей регистратор пропал, ждёт того же владельца (`rec:<том>`). Захват тома умершего процесса истекает за 45 секунд, и тот, кто возьмёт том следующим, назовёт того же владельца (урок 10, шаг 8). Ожидание длиннее — значит, он подберёт писателя целиком. У самого демона по умолчанию 60 секунд, у продукта на ящике было 20 — и писатель хозяина не дождался. Тест проверяет неравенство, а не число: `int(env["OBSD_WRITER_GRACE_S"]) > 45`.

**`Restart=always`.** Демон, который ушёл, для каждого регистратора — `away`: тома остаются за ними, а следующий проход открывает их заново (урок 10, шаг 10).

**`TimeoutStopSec=60`.** По SIGTERM демон закрывает каждого писателя чисто, и каждый может сбрасываться до 30 секунд. README демона так и просит: дайте супервизору не меньше 60 секунд на остановку.

И одна строка README, которую стоит знать на коробке: пиру с другим uid демон отказывает, если тот не в `OBSD_CLIENT_GROUP`. До четвёртого ревью это выполнялось само — контейнеры и демон работали от root, — и сокет мог открыть любой процесс коробки, процесс воркера со сторонним драйвером тоже. Теперь демон — `obsd`, регистраторы — члены `vms-rec`, а воркер сокета не видит вовсе.

Тест читает юнит так же, как контейнеры:

```python
def test_the_archives_engine_is_the_hosts_own_daemon():
    """One obsd per host, not a container of the image: it keeps one writer per volume, and that means something
    only if every recorder on the box asks the same one. Its socket is where the recorder already looks."""
    from w2cplatform.obsd import default_socket
    u = unit("obsd.service")
    assert u["Service"]["ExecStart"] == "/usr/local/bin/obsd --socket /run/obsd/obsd.sock"
    assert u["Service"]["RuntimeDirectory"] == "obsd" and u["Service"]["RuntimeDirectoryPreserve"] == "yes"
    assert u["Service"]["RuntimeDirectoryMode"] == "0750"                              # its group gets in; the daemon's own 0700 would not let it
    env = dict(e.split("=", 1) for e in u["Service"]["Environment"])
    assert int(env["OBSD_WRITER_GRACE_S"]) > 45                                         # the writer outlasts a hold that lapses
    assert u["Service"]["User"] == "obsd" and env["OBSD_CLIENT_GROUP"] == u["Service"]["Group"]   # its own user; the recorders' group
    import sys
    if sys.platform != "darwin":
        assert default_socket() == "/run/obsd/obsd.sock"                                # where the unit puts it, not the daemon's own default
```

### Откуда берётся `/usr/local/bin/obsd`

Из исходников ObjectStorage, без SDK продукта и без сборочной системы монорепозитория:

```bash
ObjectStorage/standalone-build/build.sh /tmp/obsd-build          # копирует исходники движка, применяет патчи к копии, собирает
install -m 755 /tmp/obsd-build/build/obsd /usr/local/bin/obsd
deploy/install-obsd.sh                                          # пользователь и группа, каталоги, кольца под root — obsd, юнит
```

Скрипт не трогает дерево ObjectStorage: он копирует то, что нужно движку, в `<out>/src`, применяет патчи из `patches/` к копии и собирает `<out>/build/obsd` через CMake. С `--tests` он заодно собирает и прогоняет тесты демона (`obsd_ut`) и движка (`os_engine_ut`). Тот же бинарник нужен тестам курса: без него они падают с подсказкой — `OBSD_BIN=<out>/build/obsd` или `obsd` в `PATH`.

### Регистратор ждёт сброса писателя

Юнит регистратора называет демон в своём `[Unit]` и выводит срок остановки из того, что делает `after_stop` (урок 10, шаг 11):

```ini
[Unit]
Description=VMS recorder %i — the recordings of its assignment, into this box's archive
After=network.target obsd.service
Wants=obsd.service

[Container]
…
# SIGTERM: the pipelines stop, then the writer is closed — after its flush, up to thirty seconds by the
# protocol — and only then is the hold let go (`RecWorker.after_stop`).
StopTimeout=40
```

**`After=obsd.service` и `Wants=obsd.service`.** Регистратор, поднятый раньше демона, не сломается — он просто назовёт том `away` и откроет его на следующем проходе. Но порядок убирает этот лишний круг при каждой загрузке, а `Wants` поднимает демон, если его забыли включить.

**`StopTimeout=40`.** Штатная остановка регистратора — это конвейеры, последний heartbeat, слот, а потом закрытие писателя, которое ждёт сброса: до тридцати секунд по протоколу (`WRITER_CLOSE` ждёт `long_timeout`). Сорок — это тридцать на сброс и запас на всё остальное. Срок короче — и SIGKILL придёт посреди сброса: остановка станет падением, захват не отпустится, и следующий держатель тома будет ждать 45 секунд.

## Шаг 6 — Ресурс: процесс вместо таймера

```ini
Description=VMS resource — the policy pass, the heartbeat, the event index
Exec=python3 -m vms resource
Environment=RESOURCE_HOST=127.0.0.1
Environment=RESOURCE_PORT=8090
Volume=/data/platform:/data/platform:z
Volume=/data/archive:/data/archive:z

[Service]
Restart=always
```

Шапка юнита называет замену:

> *It replaced vms-archive-retain.timer: the policy pass now runs every 600 s from the process's loop, and a oneshot could not hold a heartbeat.*

Было: таймер systemd, раз в десять минут запускающий разовую задачу. Стало: процесс с циклом (урок 11).

**Тот же проход, та же периодичность** — и три вещи, которых у разовой задачи быть не может: heartbeat (её не видно между запусками), порт (к ней нельзя обратиться) и индекс событий с его кэшем (ему негде жить).

Тест проверяет `Restart=always` с комментарием: *процесс, а не таймер: база живёт в нём.*

Видео — не его дело, и примечание к юниту говорит это прямо: *Footage is not its business: it is in volumes, behind the host's obsd.* Под `/data/archive` лежит и собственный том сервера (`volume/`), но это том демона, а не бакет, и обход ресурса его не открывает.

`RESOURCE_HOST=127.0.0.1` — на одной коробке к ресурсу обращается только консоль. Примечание говорит, что в М11 задача слушает адрес сервера, потому что соседи шлют туда зеркала.

И примечание про индекс событий:

> *The event index keeps nothing of its own: it reads the buckets where they lie at each query and caches what it read (64 MiB by default). A restart loses the cache and nothing else; there is nothing to rebuild and no `EVENTDB` to set.*

**«Ничего, кроме кэша»** — проверка того, что у индекса нет ничего своего (урок 13 М10A). Пока здесь стояла база SQLite, примечание говорило, что перезапуск пересобирает её за секунды, — на годе хранения это были не секунды.

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
CMD ["python3", "-m", "vms", "worker"]
```

**Один образ на все процессы.** Не образ на глагол: различие между процессами — в аргументе и в токене, а не в содержимом.

Публиковать надо одно; версия одна; обновление атомарно для всей коробки.

`COPY` три раза, и тест это проверяет:

```python
    copied = re.findall(r"^COPY (\S+) ", cf, re.M)
    assert copied == ["w2cplatform", "vms", "gstvms"]
    assert "postgres" not in cf.lower()                                                # the per-box database is gone (М10 Lesson 1)
```

**Три пакета — и это граница модуля, проверяемая сборкой.** Появился четвёртый — тест падает, и надо объяснить, зачем он.

**`obsd` в образе нет, и это тоже граница.** Клиент демона — `w2cplatform/obsd.py`, чистый Python над unix-сокетом, и он в образе. Сам движок — на хосте (шаг 5). Положи бинарник в образ — и каждый контейнер получит возможность запустить свой демон, то есть ровно то, от чего шаг 5 защищает.

`postgres` в образе не должно быть ни в каком виде. В М9 на коробке был свой Postgres, хранивший желаемое состояние; М10 его убрала (правда теперь в хранилищах платформы). Тест сторожит, чтобы он не вернулся «на время».

Ни `pip install`, ни `requirements.txt`, ни виртуального окружения: **всё из системных пакетов Debian**. `python3-yaml` вместо `pyyaml` из PyPI. Зависимости обновляются с системой, и сборка не ходит в интернет за пакетами.

`CMD` по умолчанию — `worker`, и юниты всё равно повторяют `Exec=` явно. Дублирование намеренное: юнит должен читаться сам по себе, не требуя заглянуть в образ.

## Шаг 8 — Конфигурация на разделе данных

```
# /data/config/vms.env — what every VMS unit on this box reads. On the data
# partition, never in a rootfs slot (М9 Lesson 5): an OS update must not
# change which archive this box records into.
```

Одна фраза, и за ней весь урок 5 М9.

Коробка имеет **A/B-корень под RAUC**: два слота операционной системы, обновление пишет в неактивный и переключает. Файл в корне при переключении слота **заменяется файлом из нового образа**.

Конфигурация коробки — какая ёмкость, какой архив, какое имя — переживать обновление обязана. Поэтому она на разделе данных, который обновление не трогает.

`vms.env.example` — то, что копируют на коробку, с комментарием у каждой переменной. Тест сторожит обязательные — и то, чего быть не должно:

```python
    env = open(os.path.join(DEPLOY, "vms.env.example")).read()
    assert all(k in env for k in ("PLATFORM_DIR=/data/platform", "ARCHIVE=/data/archive", "CAPACITY="))
    assert "SPOOL=" not in env and "SEGMENT_SECONDS=" not in env
```

`SPOOL` и `SEGMENT_SECONDS` ушли вместе с файловым архивом: очереди на диске нет, а длину куска решает движок — блоками и последовательностями (урок 7). Вторая строка теста не даёт им вернуться в пример, который копируют на коробки.

Пришли четыре переменные архива, все закомментированы — у каждой есть разумное умолчание:

```
# the server's own volume, where a recorder with nothing declared writes: a volume of ObjectStorage, opened by
# the host's obsd (`obsd.service`). Unset: `volume` BESIDE `$ARCHIVE` — `/data/volume` — and not inside the
# tree, where the resource's walks would take the ring for events and count its blocks as the tree's usage.
# ARCHIVE_VOLUME=file:///data/volume
# its size when it is first formatted — a ring: it never grows past it, and gives up its oldest minutes when
# full. Unset: four fifths of what is free, leaving two gigabytes and the disk under the watermark's low mark
# once the ring is full. A volume that exists keeps its size until a declaration (`rec/volumes/<name>`) says
# another.
# ARCHIVE_QUOTA_BYTES=
# the host's ObjectStorage daemon: /run/obsd/obsd.sock, where `obsd.service` puts it — set in the recorder's own
# unit, the one process that mounts that directory. How long a recorder waits for one answer from it: shorter
# than a lease, or a silent daemon fences every recording.
# OBSD_SOCKET=/run/obsd/obsd.sock
# OBSD_TIMEOUT=10
```

**`ARCHIVE_VOLUME`** — где собственный том сервера. Рядом с деревом ресурса, а не внутри: внутри обходы ресурса приняли бы кольцо за дерево событий и посчитали бы его блоки занятым местом.

**`ARCHIVE_QUOTA_BYTES`** — размер собственного тома сервера, когда он форматируется впервые. Квота — это размер кольца (урок 10, шаг 3), и спрашивается она один раз: отформатированный том свой размер не меняет, пока объявление не скажет другой. Без неё — четыре пятых свободного места, но не больше, чем держит диск под нижней отметкой ватерлинии, когда кольцо заполнится.

**`OBSD_SOCKET`** — где демон: `/run/obsd/obsd.sock`. Его задаёт юнит регистратора — единственного процесса, который этот каталог монтирует; умолчание клиента совпадает. Размер нового тома без `ARCHIVE_QUOTA_BYTES` спрашивается у демона (`VOLUME_SPACE` того каталога, куда он будет писать), а не у диска контейнера: на коробке с системным SSD и HDD под данные доля SSD дала бы пару часов архива (четвёртое ревью).

**`OBSD_TIMEOUT`** — сколько регистратор ждёт одного ответа демона. Десять секунд — треть аренды. Поставь больше аренды — и один молчащий демон отсечёт регистратор со всеми записями (урок 10, шаг 10).

Примечание перечисляет, чего **нет** в общем файле и почему: `WORKER_NAME=%i` — в юните воркера (это слот, а не настройка коробки); `CONSOLE_HOST`/`CONSOLE_PORT` — в юните консоли; `NOMAD_*` — их даёт М11.

**Настройка коробки против настройки экземпляра** — разделение, которое стоит держать: первое в файле окружения, второе в юните. Демон движка в общий файл не смотрит вовсе: его настройки — в его юните, потому что он не процесс VMS.

## Шаг 9 — Юниты как код

```python
def test_the_units_run_the_entrypoints_the_package_has():
    from vms import __main__ as m  # noqa: F401  (imports the module without running it: no __name__ == "__main__")
    entrypoints = set(re.findall(r'"(\w+)": \w+', open(os.path.join(HERE, "vms", "__main__.py")).read().split("__main__")[-1]))
    assert entrypoints == {"worker", "controller", "recorder", "reccontroller", "console", "resource", "gateway",
                           "livecontroller", "detworker", "detcontroller", "detjobworker", "detjobcontroller",
                           "surveyworker", "surveycontroller", "autoworker", "autocontroller"}
    for name, entry in [("vmsworker@.container", "worker"), ("vmscontroller.container", "controller"), …]:
        u = unit(name)
        assert u["Container"]["Image"] == "localhost/vmsserver:latest"                 # one image, one thing to publish
        assert u["Container"]["Exec"] == f"python3 -m vms {entry}"
        assert u["Container"]["EnvironmentFile"] == "/data/config/vms.env"             # the data partition, never a rootfs slot
        for vol in …:
            assert vol.startswith("/data/") or vol.startswith("/run/vms:") or vol.startswith("/run/obsd:"), vol   # sockets on a tmpfs, not state
```

**Таблица диспетчера извлекается регулярным выражением из исходника** и сверяется с юнитами. Здесь видны все шестнадцать глаголов — десять этого урока и шесть, которые добавят уроки 20–25.

Приём грубый — и он ловит то, что иначе не ловится ничем: юнит, зовущий несуществующий глагол, или глагол, которому не соответствует ни один юнит. Обе ошибки обнаруживаются при запуске на коробке, то есть в худший момент.

`from vms import __main__ as m` — импорт **без запуска**: в модуле есть `if __name__ == "__main__"`, и при импорте он не срабатывает. Проверяется, что модуль вообще импортируется — то есть все подсистемы собираются.

И последнее утверждение: **каждый том начинается с `/data/` или `/run/vms:`**. Ни одного монтирования из корня, ни `/etc`, ни `/var`, ни сокета докера. Всё состояние коробки — на разделе данных, плюс один tmpfs. Сокет демона живёт в том же tmpfs, поэтому правило не понадобилось менять, когда появился `obsd`.

Это правило, за которым стоит следить в любой системе: **если контейнер монтирует что-то из корня, объясните зачем.** Обычно объяснения нет.

## Шаг 10 — Проверка здоровья

Последнее соединение модуля: что читает проверка здоровья коробки.

Своей проверки в `deploy/` нет. `curl` в образе положен ровно для неё — для `podman healthcheck` или ручной проверки `/metrics`, — а читать ей предлагается число, которое называет спецификация регистратора:

```yaml
console:
  running: recordings_running          # rec_recordings_running: recordings whose pipeline is writing — what the health check reads
```

`rec_recordings_running` — сколько записей **действительно пишутся**, а не сколько настроено. Консоль считает его по heartbeat'ам всех живых регистраторов и отдаёт на своём `/metrics` (урок 10, шаг 13).

Смотреть на файлы архива, чтобы убедиться, что он пополняется, теперь не на что: видео в томе, за демоном, и каталог тома — не дерево файлов, которое кто-то обходит. Зато «пополняется» стало числами, которые регистратор публикует сам, и консоль отдаёт их рядом:

- `rec_last_frame_age_seconds` — сколько секунд назад запись последний раз что-то получила от источника;
- `rec_writer{state}` — доходит ли отданное писателю до кольца: `ok`, `stuck`, `losing`;
- `rec_archive_failure{kind}` и `rec_archive_away_seconds` — том не берёт кадры, по какой причине и как долго;
- `rec_volume_error` — регистратор держит том, который не открывается.

**Интерфейс наблюдаемости пережил полную перестройку системы — и стал точнее.** М9 знала один процесс, пишущий видео в файлы; М10 разложила его на воркер, регистратор, ресурс, контроллеры и демон движка. Метрика «пишется» осталась той же, а вопрос «доходит ли» получил собственные числа вместо взгляда на каталог.

## Результат

```bash
systemctl enable --now obsd
systemctl enable --now resource vmscontroller reccontroller console
systemctl enable --now vmsworker@w-1 recworker@r-1
systemctl enable --now livecontroller liveworker@g-1
systemctl enable --now detcontroller detworker@d-1
```

Десять процессов, один образ, один файл окружения — и один демон хоста под ними.

```bash
curl -X POST localhost:8080/cameras -H 'Idempotency-Key: a1' \
     -d '{"source":"driverpack://file/lobby.mp4"}'
```

За один проход камера держится; heartbeat говорит `live_url: rtsp://box:8554/1`. Нажали «Запись» — регистратор форматирует том сервера `/data/volume` и пишет поток `1/e1`. Записанные минуты видны, когда закрывается их блок (урок 8).

```bash
systemctl stop vmscontroller            # ничего работающее не останавливается
systemctl kill -s KILL vmsworker@w-1    # регистратор переподписывается под новой эпохой
systemctl kill -s KILL recworker@r-1    # писатель ждёт в демоне; поднятый регистратор подбирает его целиком
systemctl restart obsd                  # регистраторы держат тома как away и открывают их заново
```

Четыре команды — четыре свойства, обещанные в модуле.

## Что может пойти не так

- **Новый `obsd` поверх запущенного файла на macOS.** `cp -p` новым бинарником поверх прежнего — и процесс убивается при старте (SIGKILL, код 137): ядро держит кеш подписи прежнего файла. Класть новым файлом — удалить, потом копировать (обратная связь CP).

- **Конфигурация в корневом разделе.** Обновление системы поменяет, в какой архив пишет коробка.
- **Образ на глагол.** Шестнадцать публикаций, шестнадцать версий и шестнадцать способов рассинхронизироваться.
- **Токен на подсистему вместо токена на процесс.** Ошибка в консоли сможет переразместить камеры.
- **Медиа, смонтированные регистратору.** Второе соединение к камере станет возможным — и однажды случится.
- **Демон движка внутри контейнера регистратора.** Два регистратора — два демона, два писателя одного тома и порча вместо отказа.
- **Юнит без `RuntimeDirectoryMode=0750`.** Демон сам создаст каталог сокета 0700, и ни один регистратор до сокета не дойдёт.
- **Пользователь из юнита, которого никто не создал.** 217/USER, демона нет, запись стоит; на обновлённой коробке — кольца root, которых демон не откроет. Для этого `install-obsd.sh`.
- **`/run/vms` из юнита демона.** Без демона не стартуют ни воркер, ни регистратор; каталог — коробки (`vms.tmpfiles`).
- **`OBSD_WRITER_GRACE_S` короче истечения захвата.** Следующий держатель тома не застанет писателя.
- **`StopTimeout` регистратора короче сброса писателя.** Штатная остановка станет падением, и том 45 секунд никто не возьмёт.
- **`TimeoutStopSec` демона короче шестидесяти секунд.** Писатели не успеют закрыться чисто, и тома после остановки придётся восстанавливать.
- **Путь собственного тома, смонтированный в контейнер по другому пути.** Регистратор назовёт демону путь, которого на хосте нет.
- **Монтирование из корня.** Состояние коробки перестанет быть на разделе данных, и обновление начнёт его трогать.
- **Таймер вместо процесса ресурса.** Ни heartbeat'а, ни порта, ни индекса.
- **Юниты, не проверяемые тестом.** Опечатка в `Exec=` обнаружится на коробке.
- **`pip install` в образе.** Сборка пойдёт в интернет, а зависимости перестанут обновляться с системой.

## Итог

- Четыре подсистемы дают десять процессов; шесть из них — один класс с другой спецификацией.
- Три токена разбивают `vms/*` на непересекающиеся части, и обе ACL вырезаны из одной YAML.
- Монтирования повторяют ACL в байтах: у контроллера нет архива, у регистратора нет медиа, спула нет ни у кого — видео за демоном.
- Имя экземпляра systemd — это слот, и супервизор является авторитетом по вопросу, кто сейчас `w-1`.
- Движок архива — демон хоста, один на коробку: правило «один писатель на том» значит что-то, только если все регистраторы спрашивают один демон.
- Сроки выводятся из того, что делает остановка: ожидание писателя (90 с) длиннее истечения захвата (45 с), остановка регистратора (40 с) длиннее сброса (30 с), остановка демона (60 с) — по README.
- Ресурс — процесс, а не таймер: у таймера не может быть ни heartbeat'а, ни порта, ни индекса.
- Один образ, три пакета, ни одного `pip install` и ни одного `obsd`; конфигурация на разделе данных, потому что обновление не должно менять, куда пишет коробка.
- Юниты читаются тестами: опечатка в `Exec=` ломает сборку, а не коробку.

## Упражнения

1. Перенесите `vms.env` в `/etc`. Проведите обновление системы через RAUC и посмотрите на `CAPACITY`.
2. Смонтируйте регистратору `/data/media`. Опишите, чем это опасно через год.
3. Поставьте `StopTimeout=10` у `recworker@`. Остановите регистратор посреди записи и посмотрите, сколько ждал следующий держатель тома и что он нашёл в томе.
4. Поставьте `OBSD_WRITER_GRACE_S=20`. Убейте регистратор `kill -9` и проследите, кто и когда возьмёт том.
5. Уберите `RuntimeDirectoryMode=0750` из `obsd.service`, удалите `/run/obsd` и перезапустите демон. Что видит регистратор и что говорит его `volume_error`?
6. Смонтируйте регистратору `/data/archive` как `/archive` и задайте `ARCHIVE=/archive`. Что регистратор назовёт демону и что ответит демон?
7. Соберите образ с `obsd` внутри и запустите демон в каждом контейнере регистратора. Объявите сетевой том и поднимите два регистратора на одной коробке. Что пойдёт не так и почему ни один из двух этого не заметит?
8. Соберите отдельный образ для консоли. Перечислите, что теперь надо делать при выпуске новой версии.
9. Дайте консоли токен всей подсистемы. Напишите в ней вызов `place` и посмотрите, что произойдёт.
10. Верните ресурс таймером. Перечислите, что при этом пропадёт, и как консоль будет получать события.
11. Добавьте в `Containerfile` четвёртый `COPY`. Запустите тесты.
12. Смонтируйте `/var/run/docker.sock`. Объясните зачем — и если объяснения нет, сформулируйте правило.

## Что дальше

Коробка собрана: строка камеры, цикл сверки из М9, воркер, который держит устройство и не пишет его, элемент GStreamer, движок архива за демоном, регистратор, ресурс, консоль, живое видео, детекторы, чужой архив и дозапись из края — и всё это как десять процессов и один демон на коробке из М9.

Граница, проведённая в М10A по линии импорта, выдержала четыре подсистемы: `test_the_platform_knows_nothing_about_video` зелёный — ни одного импорта из `vms/` под `w2cplatform/`. Клиент движка архива, `obsd.py`, лежит по ту сторону границы, в платформе: он говорит о томах, писателях и сэмплах, а не о камерах.

Остался один вопрос, который коробка задаёт раньше кластера: что архив отдаёт первым, когда кольцо замкнулось. [**Урок 18**](18-what-the-archive-gives-up-first.md) отвечает на него за подсистему.

[**М11 — ClusterVMS**](../М11_ClusterVMS/README.md) начинает с того, что коробок несколько: те же контроллеры над Nomad Variables, те же воркеры под планировщиком, тот же ресурс системной задачей на каждом сервере — и автомасштабирование, суммирующее тот самый запас, который воркеры публикуют с урока 4.

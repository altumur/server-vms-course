# Урок 3 — `vmsworker` I: процесс

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** первую половину `vms/worker.py` — `FakeActuator`, `labels_from_environment`, конструктор `VmsWorker` (то, что VMS кладёт поверх базы воркера платформы), `desired`, `refresh`, работу VMS у ворот платформы — `_actuate` и `enrich` — и `now`.
**Время:** ~70 минут.

## Зачем этот урок

Контроллер размещает, цикл сверяет. Между ними нет процесса — и урок его делает.

Почти всё, что делает процесс воркером, уже написано, и написано не здесь. Имя, взятое захватом слота, эпоха и аренда на каждую единицу, ограда, возвращение после неё, heartbeat с полями платформы, цикл, который всё это крутит, — рантайм воркера платформы (`w2cplatform/worker.py`; М10A, уроки 7 и 8). Воркер VMS — его наследник, и **главное в уроке — граница**: что VMS пишет сама, а что получает, не написав ни строки. Сама она пишет немного: какие строки — камеры, что поднять, пройдя ворота платформы (новая эпоха на новый запуск, та же — на правку, адрес раздачи, пароль устройства в последний момент), и что значит остановить.

И третье, самое неожиданное для читателя: докстрока класса говорит, что воркер **ничего не записывает**. Он держит камеру, раздаёт её, пишет события — и не сохраняет ни секунды видео. Запись делает другой процесс. Урок объясняет, почему, а урок 10 показывает как.

> **Проверка без железа.** Весь урок. `FakeActuator` заменяет GStreamer, окружение подаётся словарём, часы — поддельные. Семь тестов М9 и тесты `test_lesson4_worker.py` гоняют этот класс без единого кадра видео.

## Что нужно знать заранее

- **М10A, урок 7** — захват имени: `claim_slot`, `claim_at_start`, имена, которые рантайм сообщает процессу (шаг 9).
- **М10A, урок 8** — база `Worker`: что он помнит (шаг 7), ворота (шаг 8: `take_epoch`, `may_act`, `may_write`) и рантайм (шаг 9).
- **М10A, урок 6** — эпоха и аренда; шаг 8а — два вопроса аренды: действие и данные.
- **Урок 2** — `Reconciler`, помощник сверки платформы: этот класс даст ему желаемое и три функции — запуск, стоп и перезапуск.

## Чему вы научитесь

1. Отделять то, что процесс получает от платформы, от того, что добавляет подсистема.
2. Читать назначение и строки так, чтобы свежий процесс ничего не помнил и всё вывел.
3. Ставить работу подсистемы за воротами платформы, не повторяя их проверок.
4. Различать новую эпоху и переиспользованную и говорить, что означает каждая.
5. Понимать, почему воркер держит камеру и не пишет её.

---

## Шаг 1 — Что процесс получает от мира

```
What the environment hands a process, on a box or in an allocation:

    WORKER_NAME / SLOT_INDEX     -> the slot to claim: w-<index>. The index is the preference;
                                    the claim (CAS on vms/slots/w-N) is the proof
    SERVER_NAME (or the hostname) -> `server` in the heartbeat: whose resource its events go to, and the host in `live_url`
    LABELS                        -> `labels` in the heartbeat: what this server can reach; the controller places by them
    INSTANCE_ID                   -> the instance; CAPACITY -> the worker's own number, from М9 Lesson 7's probe

Not one of those names an orchestrator, and that is deliberate: a Quadlet, a
systemd unit or a container's environment each map their own names into these
five (`w2cplatform/runtime.py`), and the loop never learns which did.
```

Пять имён в докстроке, и четыре из них — платформы. `WORKER_NAME`, `SLOT_INDEX`, `SERVER_NAME`, `LABELS`, `INSTANCE_ID` (и рядом `SPARE_FOR`, `BOX_ID`, `RESOURCE_ROOT`) читает `w2cplatform/runtime.py` для любой подсистемы; что значит каждое и почему **индекс — предпочтение, а захват — доказательство**, разобрано в М10A, урок 7, шаги 5 и 9. Здесь повторять нечего: процесс VMS получает эти имена так же, как воркер `testsub`.

Своё у VMS — то, что знает только она:

- `CAPACITY` — число, измеренное зондом из урока 7 М9 **на этом железе**. Ёмкость — слово воркера, и только воркер VMS знает, сколько конвейеров потянет эта машина.
- `SHM_DIR` — где ветвь разделяемой памяти (`/run/vms` по умолчанию, урок 4).
- `RTSP_PORT`, `RTSP_HOST`, `PLAYBACK_PORT`, `PLAYBACK_HOST`, `RTP_BASE` — двери этого экземпляра и то, к чему они привязаны (урок 4).

И одно правило поверх `LABELS`:

```python
def labels_from_environment(env: dict) -> list[str]:
    from w2cplatform.spec import LABEL_WORD
    out = runtime.labels(env)
    bad = [l for l in out if not LABEL_WORD.fullmatch(l)]
    if bad:
        log.warning("LABELS holds %s, which is not a label (letters, digits and _ . : -, starting with a letter or a "
                    "digit): no camera can be given it any more and the console cannot write it for a server; write it "
                    "in those characters", ", ".join(repr(l) for l in bad))
    return out
```

Разбирает `LABELS` платформа (`runtime.labels`: по запятым, пустые выкинуты; нет переменной — пустой список, и сервер без меток — обычный сервер). VMS добавляет одно: слово вне алфавита меток говорится при старте. Не отказ — камере, сохранённой с таким словом раньше, всё ещё нужен сервер, — а предупреждение: ни новой камере, ни строке сервера его больше не дать.

## Шаг 2 — Конструктор: база, захват, и что сверху

```python
class VmsWorker(Worker):
    SUB = VMS                       # the subsystem whose assignment and rows this worker runs
    REQUEST_TARGET = "the device"   # what a request's refusal calls what was called
    ROWS = "cameras"                # <sub>/<ROWS>/<id>
    parse_row = staticmethod(row)

    def __init__(self, name: str | None, vars_: Variables, objects: ObjectStore, actuator=None,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 server: str | None = None, capacity: int | None = None, instance: str | None = None, slot_ttl: float = 45.0,
                 resource_root: str | None = None, bucket_seconds: int = 600, env: dict | None = None,
                 device_factory=None):
        env = dict(os.environ if env is None else env)
        instance = instance or runtime.instance_on_box(env)   # the box in it: whose a name is (`Worker._may_take_by_name`)
        super().__init__(self.SUB, None, vars_, objects, lease_ttl, lease_margin, clock, wall, instance, slot_ttl,
                         resource_root, env)
        self.sealer = Sealer.from_env(env)                    # opens a device's password for the pipeline, and nothing else does
        …
        self.server = runtime.server(env, server)             # before the claim: a process on a decommissioned server gets no slot
        # …or, started as a spare (`SPARE_FOR`), an offer of its set — none: nobody, waiting (`Worker.claim_at_start`)
        self.claim_at_start(name, env)                        # no name: the runtime's, by the spec's `slot`
        self.shm_dir = env.get("SHM_DIR", SHM_DIR)                                 # the tee's shared-memory branch, for subscribers on this server
        …
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "50"))   # М9 Lesson 7's B + n·I, measured on ITS server
        self.actuator = actuator or FakeActuator()
        self.rows: list[dict] = []
        …
        self.assignment_rev = 0
        self._pass_now: float | None = None               # a test's own `now` for one pass (`reconcile_once(now)`)
        self.reconciler = self.new_reconciler()
        self.labels = labels_from_environment(env)
        self.alloc = runtime.instance(env) or ""          # published as `alloc` for the readers that already know that name
        self.started_at = clock()
```

Пропущены двери этого экземпляра (урок 4), сессии устройств и их учёт (уроки 4 и 15) — всё это VMS, но не про процесс.

`env = dict(os.environ if env is None else env)` — окружение **аргументом с умолчанием**. Тесты подают словарь и получают воркера с любым сервером, любыми метками и любой ёмкостью, не трогая процесс. Копия (`dict(...)`) — чтобы не писать в чужой словарь.

`super().__init__(self.SUB, None, …)` — базовый класс получает **`None` вместо имени**: имени ещё нет, оно появится из захвата. Остальное база ставит сама, и подсистема не может об этом забыть (М10A, урок 8, шаг 7): дерево ресурса своего сервера, куда пойдут события (`resource_root`, `runtime.events_root`), спецификацию подсистемы — из каталога процесса, куда её положил `SubsystemSpec.load` (урок 1), — и потолок неподтверждённой записи из неё. Спеки в каталоге нет — воркера нет (`NoSpec`; ADR 0013): ключи спеки исполняет платформа, и воркер без них работал бы по чужим умолчаниям.

`self.server = runtime.server(env, server)` — **до** захвата: процесс на списанном сервере слота не получает (М10A, урок 7, шаг 4).

`self.claim_at_start(name, env)` — захват, и он платформы. Без имени — то, что дал рантайм, по слову спеки `slot` (`Worker.given_name`: `WORKER_NAME`, иначе `w-$SLOT_INDEX`, иначе любой свободный, просроченный первым); запущенный запасным (`SPARE_FOR`) берёт только предложение своего набора, а без него — никто и ждёт (М10A, урок 11). Правило «**создание объекта есть захват слота**» VMS наследует, не написав его: не взялся — исключение из конструктора, объекта нет; процесс без личности не существует ни секунды. `name` аргументом сильнее окружения: тесты передают `"w-1"`, процесс не передаёт ничего.

**Атрибуты класса — то, что подсистема говорит о себе в Python, и их немного.** `SUB` — чьё назначение и чьи строки, `ROWS` — каталог строк, `parse_row` — как строка становится словарём, `REQUEST_TARGET` — как отказ команды называет то, во что её не выполнили (урок 4). Ни префикса слота, ни переменной имени, ни спеки в классе нет: имя — слово спеки (`slot: {prefix: w, name_env: WORKER_NAME}`, урок 1), спеку база берёт из каталога. В уроке 10 регистратор скажет `SUB = REC`, `ROWS = "recordings"`, `parse_row = rec_row` — и унаследует всё остальное, в том числе этот класс целиком.

Строка, которую стоит перечитать:

```python
    def new_reconciler(self) -> Reconciler:
        r = Reconciler(lambda uid, want: self._actuate("start", want.body), lambda uid: self._actuate("stop", {"id": uid}),
                       restart=lambda uid, want: self._actuate("restart", want.body))
        r.now = lambda: self.now() if self._pass_now is None else self._pass_now
        return r
```

**Все три функции цикла — один метод воркера.** Помощник платформы (урок 2) зовёт `start`, `stop` и `restart`; воркер отвечает на все три своим `_actuate` с глаголом (шаг 4), и у стопа строка урезана до `{id}` — останавливая, знать о единице больше нечего. Перезапуск дан **своим**, а не стопом со стартом: правка камеры сохраняет эпоху и аренду — ни нового писателя, ни разрыва потока `<id>/e<эпоха>`, ни вопроса к молчащему хранилищу. Часы задержек — часы воркера (`now`, секунды с его старта), а тест может подать проходу свои (`reconcile_once(now)`). Цикл не знает ничего ни о воркере, ни о воротах; он видит две функции и третью.

`self.server` заканчивается именем хоста (`runtime.server`: аргумент, `SERVER_NAME`, иначе `socket.gethostname()`) — то, ради чего в М10 всё работает и на одной коробке: **кластер из одного, и снимок всё равно говорит, какой сервер, — это имя хоста.**

**Подхват мерит платформа.** Сколько прошло между последним heartbeat'ом прежнего жильца имени и первым heartbeat'ом нового, — `failover_seconds` контроллера, и прежний heartbeat читает база, до первого своего под этим именем (`Worker.previous_said`: `previous_hb`, `previous_instance`, `previous_server` в каждом heartbeat'е; М10A, урок 8, шаг 9). Битый прежний heartbeat — как будто его нет: мерить нечего, и это вся цена. Тесты держателя камер: `test_vms_workers_survive.py::test_a_worker_whose_slot_left_a_garbled_heartbeat_starts_all_the_same`, `test_lesson4_worker.py::test_the_failover_on_metrics_is_the_one_the_workers_measured` (31 секунда на одной коробке, по одним часам); два сервера — М11, `test_lesson4_failover.py::test_a_restart_is_measured_on_one_clock_and_a_name_taken_elsewhere_by_the_readers`.

## Шаг 3 — Что воркер считает желаемым

```python
    def desired(self) -> list[dict]:
        """What the reconciler runs. A row with `live: on-demand` is NOT here: its device is
        still held (see `_refresh_devices`) and its archive still served, but no pipeline is
        built for it. Holding the device is what the row buys; the live fan-out is what `live`
        asks for."""
        back = self.held_back()
        return [r for r in self.rows if r.get("live", "always") != "on-demand" and str(r["id"]) not in back]
```

Желаемое цикла — поле с двумя вычитаниями. Камера `live: on-demand` держится, но конвейера у неё нет (урок 15). И `held_back` — камеры, которые воркер не откроет: второй камеры на тот же канал устройства, записанный иначе (`…/ch/02` и `…/ch/2` — один канал, а различить это может только VMS: так она читает свои адреса), и источника, который VMS не может прочесть. Платформа такую строку принимает — это адрес по RFC 3986; воркер её не набирает и говорит почему в статусе камеры (`device busy`, `not opened: …`). Вся настоящая работа — в `refresh`. А из `desired()` проход (`reconcile_once`) собирает то, что просит у помощника, — включённые строки по их ревизии, `{r["id"]: Want(r["revision"], r) for r in self.desired() if r["enabled"]}`, — и переводит `Pass` обратно в список `(глагол, камера)`: стопы первыми, потом перезапуски, старты и неудачи в порядке камер. Этот список и возвращает проход, его тесты и читают.

```python
    def refresh(self) -> None:
        """Read the assignment and the rows it names. A fresh worker knows
        nothing and reads everything; nothing about what is running is stored."""
        a = self.assignment()                         # …which forgets what the lease step let go before it (`lost_to_epoch`)
        self.assignment_rev = a.rev
        rows, errors = [], {}
        for unit in a.units:
            try:
                …
                items, _ = self.vars.get(self.SUB.config(self.ROWS, unit))
                if not items or items.get("deleted") == "true":
                    continue
                rows.append(self.parse_row(items))
                self.row_parsed(unit)
            except PARSE_ERRORS as e:                    # `Infinity` in an int field too (the tenth round's sweep)
                …
                errors[unit] = self.row_garbled(unit, e)
                last = next((r for r in self.rows if str(r["id"]) == unit), None)
                if last is not None:
                    rows.append(last)
        self.rows, self.row_errors = rows, errors
        self._refresh_devices()
```

Два чтения на проход: назначение и по строке на каждую названную единицу. Назначение читает база (`Worker.assignment`): что в нём, она запоминает для своих ворот (`take_epoch` берёт эпоху только на единицу назначения, которое ответило последним), и это же чтение возвращает в оборот камеры, которые шаг аренд отпустил новому держателю (М10A, урок 8, шаг 9; урок 4). Строки читает VMS: что такое строка камеры, платформа не знает.

**Свежий воркер ничего не знает и читает всё.** Это та же мысль, что работающее в памяти цикла (урок 2), применённая к конфигурации: процесс не кэширует строки между проходами, потому что правка могла случиться в любую секунду, и единственный способ узнать о ней — прочитать.

Дорого ли? Назначение плюс `N` строк каждые две секунды. На сорока камерах — сорок одно чтение локального файлового хранилища или сорок одно чтение из raft-кэша. Дёшево ровно настолько, чтобы не заводить кэш с инвалидацией, который и есть источник ошибок этого класса.

`items.get("deleted") == "true"` — **удалённые строки пропускаются здесь**. Контроллер не стирает строку, а помечает (урок 10 М10A), и воркер, увидевший маркер, просто не кладёт её в желаемое. Дальше работает цикл остановки из урока 2: единица выпала из желаемого — значит, останавливается.

Заметьте, чего нет: обработки отсутствующей строки. `if not items …: continue` — назначение называет единицу, строки нет, воркер молча пропускает. Это не глотание ошибки: назначение и строки пишутся разными записями, между ними бывает окно, и следующий проход через две секунды прочитает согласованное состояние. Паниковать из-за нормальной гонки — значит шуметь на каждом создании камеры.

А вот строка, которая есть и не читается, — беда одной камеры, и не «камеру забрали». Что идёт по строке, прочитанной последней, идёт дальше, камера, которую воркер целой не читал ни разу, не стартует, а в её статусе — почему. Слова для этого даёт база (`row_garbled`, `row_parsed`: строка говорится в логе один раз; все читаемые строки одной таблицей — М10A, урок 8, шаг 5); решает, что значит «шло — идёт», подсистема. Чтение стоит внутри той же защиты: оборванный файл — это ошибка самого хранилища ещё до разбора (`tests/test_garbled_rows.py::test_one_torn_camera_row_does_not_freeze_its_holders_reconcile`).

`assignment_rev` сохраняется не для работы, а для heartbeat'а: по нему видно, какую версию назначения воркер видел, и разошёлся ли он с контроллером. `_refresh_devices` — одна сессия на устройство, сколько бы его каналов ни было назначено (урок 4).

## Шаг 4 — У ворот платформы

```python
    def _actuate(self, verb: str, cam: dict) -> bool:
        unit = str(cam["id"])
        if verb in ("start", "restart"):
            if not self.writing_allowed:
                return False
            if verb == "start" or unit not in self.epochs:
                try:
                    …
                    if unit in self.lost_to_epoch:
                        raise NotReadThisPass(…)
                    cam = dict(cam, epoch=self.take_epoch(unit))   # a new epoch for a new writer
                except (OSError, NotReadThisPass) as e:
                    …
                    if unit in self.epochs and self.may_write(unit):
                        …
                        cam = dict(cam, epoch=self.epochs[unit])
                    else:
                        …
                        return False
                except Exception as e:                          # noqa: BLE001
                    …
                    self.epoch_errors[unit] = str(e)
                    return False
                self.epoch_errors.pop(unit, None)
            else:
                cam = dict(cam, epoch=self.epochs[unit])
            if not self.may_write(unit):                       # data: a lease that ran out in silence still records
                return False
            cam = self.enrich(cam)                              # what the pipeline needs beyond the row: the fan-out here, the source for a recorder
            if cam is None:
                return False                                    # not startable now (a recorder whose camera nobody holds): the reconciler retries
            # The device's password, opened at the last moment and only for the pipeline (`w2cplatform/sealing.py`):
            # the row in the store, in this process's memory and in its heartbeat stays sealed.
            try:
                cam = open_row(self.sealer, cam, self.SUB.config(self.ROWS, str(cam["id"])))
            except Sealed as e:
                …
                self.sealed_errors[unit] = str(e)               # in its status, not only in this log (feedback CD)
                return False
            self.sealed_errors.pop(unit, None)
            return self.actuator(verb, cam)
        ok = self.actuator("stop", cam)
        self.release(unit)
        return ok
```

Центральная функция урока, и в ней две половины. **Вопросы задаёт платформа**: `writing_allowed` — не огорожен ли экземпляр (М10A, урок 8, шаг 9); `take_epoch` — эпоха и аренда по CAS, со своими отказами: имя отдано (`NoSlot`), единицы нет в назначении, прочитанном последним (`NotReadThisPass`), шаг пережил своего «подменщика» (М10A, урок 7, шаг 7; урок 8, шаг 8); `may_write` — вопрос аренды о **данных** (М10A, урок 6, шаг 8а). Что каждый из них значит и почему, — там, и одинаково для всех подсистем. **Решает, что делать с ответом, VMS** — и вот что она решает.

**Новый писатель или тот же.** Ключевое различение модуля:

```python
            if verb == "start" or unit not in self.epochs:
                …
                    cam = dict(cam, epoch=self.take_epoch(unit))   # a new epoch for a new writer
            else:
                cam = dict(cam, epoch=self.epochs[unit])
```

`start` — **новый писатель, новая эпоха.** CAS на `vms/epoch/<id>`, число растёт, всё, что писал предыдущий держатель, становится отсечённым.

`restart` с уже удерживаемой эпохой — **та же эпоха.** Оператор поправил имя камеры, ревизия выросла, цикл велел перезапустить конвейер — писатель не сменился, и повышать эпоху было бы вредно: каждая правка обесценивала бы уже записанное.

Тест формулирует это одной фразой: *перезапуск сохраняет эпоху 1* (`test_lesson4_worker.py::test_worker_runs_its_assignment_and_takes_an_epoch_per_camera`).

Условие `unit not in self.epochs` в первой ветке страхует случай `restart` без эпохи: процесс перезапустился, конвейер считается работающим (не считается — работающее у цикла пусто), эпохи нет. Формально сюда не попасть, но ветка стоит копейку и закрывает класс ошибок.

**Эпохи не дали — а своя есть.** Хранилище не ответило на запрос эпохи (`OSError`) или назначение в этом проходе не ответило (`NotReadThisPass`). Если эпоху этой камеры воркер уже держит и аренда отвечает на вопрос данных, упавший конвейер поднимается **под ней**: это тот же писатель, и дать кому-то другой номер молчащее хранилище не могло (обратная связь BK; урок 4, шаг 8). Если не держит — старта нет, и только этой камеры: цикл повторит со своим откатом. Камеру, которую шаг аренд отпустил новому держателю, проход назад не берёт, пока назначение не прочитано заново (`lost_to_epoch`; М10A, урок 8, шаг 9).

**Битая строка эпохи — неудавшийся старт одной камеры.** Строка `vms/epoch/<камера>`, которая не разбирается, — это `ValueError` из `take_epoch`; ушёл бы через цикл — оборвал бы проход для всех камер после этой. Поэтому неудача старта, повтор с откатом, и причина в статусе камеры (`epoch_errors`: `its epoch could not be taken: …`).

**Данные, а не действие.** После эпохи — `may_write`, а не строгий `may_act`. Конвейер камеры — это данные: кадры и события под эпохой, которая стоит в их имени. Запуск без аренды не пускают к железу никогда, но аренда, истёкшая, пока хранилище молчало, у держателя камер данные не останавливает — так объявлено в его спеке (`lease: {unconfirmed_max: forever}`; почему именно так для камер — урок 4, шаг 8). Проверка стоит **после** взятия эпохи, и это важно: эпоху взять надо в любом случае, потому что взятие эпохи — это и есть объявление себя писателем; а вот пускать к железу без аренды нельзя.

Тест: через 26 секунд без продления `may_act` ложно, а более поздний запуск берёт эпоху 2 (`test_lesson4_worker.py::test_lease_expiry_without_renewal_stops_starts`).

**То, что нужно конвейеру сверх строки.** `enrich` — для воркера это адреса раздачи; `None` означает «сейчас запустить нельзя», и цикл повторит. В уроке 10 рекордер вернёт `None`, когда камеру никто не держит.

```python
    def enrich(self, cam: dict) -> dict | None:
        if cam.get("kind") == "io":
            return dict(cam)
        return dict(cam, live_url=live_url(announce_host(self.rtsp_host, self.server), cam["id"], self.fanout_port()), live_port=live_port(cam["id"], self.rtp_base),
                    live_shm=live_shm(cam["id"], self.shm_dir))
```

Пока — просто три адреса (и ни одного у устройства без картинки, `kind: io`). Что они означают, почему их два разных и почему хост — то, к чему дверь привязана, разбирает урок 4; здесь достаточно заметить, что **строка камеры не содержит ни одного из них**. Они не настройка, а следствие того, где воркер оказался.

**Пароль устройства — в последний момент.** `open_row` вскрывает запечатанный `cred_secret` только для конвейера: строка в хранилище, в памяти процесса и в heartbeat'е остаётся запечатанной (урок 19). Не вскрылся — неудача старта этой камеры с причиной в её статусе.

И ветка остановки:

```python
        ok = self.actuator("stop", cam)
        self.release(unit)
        return ok
```

Сначала остановить, **потом** отпустить эпоху и аренду. Обратный порядок открыл бы окно, в котором процесс уже не считается писателем, а конвейер ещё пишет.

```python
    def now(self) -> float:
        return self.clock() - self.started_at
```

Время для откатов — монотонное и от старта процесса. Не настенное: перевод часов не должен превращать откат в час ожидания или в мгновенный залп.

## Шаг 5 — Поддельный актуатор

```python
class FakeActuator:
    def __init__(self, failing=frozenset()):
        ...
    def __call__(self, verb: str, cam: dict) -> bool:
        ...
    def pump(self) -> tuple[list[int], list[tuple[int, str, dict]]]:
        ...
    def stop_all(self) -> None:
        ...
```

Четыре метода, и они задают **контракт настоящего актуатора** раньше, чем он появится (урок 9).

`__call__(verb, cam) -> bool` — сделать и сказать, получилось ли.
`pump()` — вернуть «что умерло» и «что наблюдалось»: две вещи, за которыми воркер приходит на каждом проходе.
`stop_all()` — остановить всё разом, для отсечения и аккуратной остановки.

Множество `failing` — камеры, на которых поддельный актуатор отказывает. Им проверяются откат, джиттер и `stalled` без единого настоящего конвейера. (Остальное в нём — `feed`, `record_range`, кольцо предзаписи — понадобится регистратору, уроки 10, 16 и 26.)

**Поддельная реализация, написанная раньше настоящей** — не заглушка, а способ зафиксировать интерфейс, пока он ещё не оброс подробностями GStreamer. Когда в уроке 9 появится `GstActuator`, ему придётся уложиться в эти четыре метода.

## Результат

```python
w = VmsWorker(None, vars_, objects, env={"WORKER_NAME": "w-1", "SERVER_NAME": "box-a", "CAPACITY": "8"})
w.name                    # 'w-1' — взят по CAS, при создании
w.reconcile_once()        # [] — назначения нет, воркер ничего не выдумывает
w.heartbeat_once()        # контроллер увидел воркера с ёмкостью 8

ctl.create_camera({"source": "driverpack://file/lobby.mp4"}); ctl.ensure_placed()
w.reconcile_once()        # [('start', 1)]
w.epochs["1"]             # 1

ctl.update_camera(1, {"name": "Вход"})
w.reconcile_once()        # [('restart', 1)]
w.epochs["1"]             # 1 — та же: писатель не сменился
```

Семь тестов М9 гоняют помощник платформы через `FakeActuator` (`tests/test_lesson4_worker.py`), а рядом с ними тот же актуатор стоит под этим классом. Новых понятий не появилось — появился процесс, в котором цикл живёт.

## Что может пойти не так

- **Своя проверка ограды или аренды в подсистеме.** Вторая копия правила платформы, которая однажды разойдётся с первой. Спрашивайте базу (`writing_allowed`, `take_epoch`, `may_write`) и решайте только то, что значит ответ для камеры.
- **Новая эпоха на `restart`.** Каждая правка имени камеры будет обесценивать уже записанное; на таймлайне всё старое станет отсечённым.
- **`may_act` вместо `may_write` перед конвейером.** Камеры встанут на первой же паузе хранилища, хотя их записи несут эпоху в имени и второму писателю нечего испортить.
- **Проверка аренды до взятия эпохи.** Процесс, у которого аренда протухла на миллисекунду, не объявит себя писателем — и другой возьмёт ту же эпоху.
- **`release` до `stop`.** Окно, в котором конвейер пишет, а процесс уже не писатель. Ровно то, от чего эпоха защищает.
- **Кэш строк между проходами.** Правка оператора доедет тогда, когда кэш решит протухнуть, и объяснить это будет нечем.
- **Паника при отсутствующей строке.** Назначение и строки пишутся разными записями; шум на каждое создание камеры.
- **Настенные часы для откатов.** Перевод времени превратит откат в час или в залп.

## Итог

- Имя, захват, ворота, ограда и цикл — рантайм воркера платформы (М10A, уроки 7 и 8); воркер VMS наследует их и пишет свою работу.
- Из окружения VMS читает своё — `CAPACITY`, `SHM_DIR`, двери экземпляра; имена слота, сервера, меток и экземпляра — платформы.
- В классе подсистемы нет ни имени слота, ни спеки: имя — слово спеки, спеку база берёт из каталога; без спеки воркера нет.
- Свежий воркер ничего не помнит и читает всё: назначение и строки на каждом проходе, удалённые пропускаются по маркеру, битая строка — беда одной камеры.
- У ворот вопросы задаёт платформа, а VMS решает: новый запуск — новая эпоха, правка — та же; упавший конвейер при молчащем хранилище — под эпохой, которая есть; конвейер — данные, поэтому `may_write`.
- Останавливают до того, как отпускают.

## Упражнения

1. Перенесите захват из конструктора в отдельный метод. Напишите код, который использует объект до захвата, и опишите, что он испортит.
2. Сделайте `restart` берущим новую эпоху. Поднимите камеру, запишите минуту, трижды поправьте имя и посмотрите на таймлайн.
3. Поменяйте местами `take_epoch` и `may_write`. Смоделируйте двух воркеров, у одного из которых аренда просрочена на миг. Кто окажется писателем?
4. Поставьте `release` перед `stop`. Опишите окно и то, что в него попадёт.
5. Закэшируйте строки на десять проходов. Измерьте, через сколько секунд доезжает правка, и сравните с обещанием на экране.
6. Уберите проверку `deleted` из `refresh`. Удалите камеру и скажите, что будет делать воркер.
7. Запустите воркера с `env={}` — без `WORKER_NAME` и `SLOT_INDEX` — дважды подряд. Какие слоты взяты и почему именно эти? Что изменится, если спека скажет `slot: {prefix: cam}`?

## Что дальше

Процесс есть, единицы поднимаются, эпохи берутся — но чем именно воркер занят, пока не сказано ни слова.

[**Урок 4**](04-vmsworker-holding-the-camera.md) отвечает на это и даёт модулю его главное решение: **воркер держит камеру, а не записывает её.** Одно соединение, одна раздача двумя ветвями — по сети и через разделяемую память, — `observe`, шина, команда устройству, `status`, heartbeat — и то, что держатель камер пишет в крючки рантайма платформы: как остановить одну камеру, все, и что забыть.

# Урок 11 — Процесс ресурса

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/resource.py` — `vms_resource` (платформенный `Resource` с индексом событий и удержаниями VMS) и `kept_buckets`; плюс `__main__.resource` — цикл процесса, у которого нет контроллера.
**Время:** ~45 минут.

## Зачем этот урок

Урок короткий, потому что почти всё уже написано. Ресурс как понятие появился в уроке 1 М10A («то, что не может переехать»), как класс — в уроке 14 М10A: heartbeat, бакеты по HTTP, зеркало, хранение по строкам подсистем, ватерлиния, восстановление. Здесь всё это соединяется в процесс.

Раньше VMS приносила на ресурс два маршрута (`/manifest`, `/segment`) и один проход (`ArchivePolicy`). Теперь не приносит ни одного маршрута и ни одного прохода. Видео ушло с дерева ресурса в тома ObjectStorage, и шапка `vms/resource.py` говорит, что из этого следует:

```
Its tree is EVENTS: the camera's buckets under `vms/<cam>/`, a recorder's under
`rec/<name>/`, the alarms', the journal's. Footage is not here any more. It is
in volumes of ObjectStorage, written through the host's `obsd` by the recorder
that holds each one (`vms/archive.py`): a volume is a ring, formatted at its
quota, that gives up its oldest minutes by itself — there is nothing on this
tree to repair, to retain by days or to free under a watermark, and no media
door here. A camera's timeline and its frames are asked of the recorders.
```

Что осталось от VMS — одна вещь, которую платформа знать не может:

```
What the VMS adds is the one thing the platform cannot know: which event
buckets somebody said to KEEP (`kept_buckets`, from `rec/keeps/*`).
```

Второй сюжет урока не изменился: **процесс без контроллера**. Цикл из двадцати строк, в котором нет ни сверки, ни назначения, ни эпохи.

> **Проверка без железа.** Весь урок, и даже без `obsd`: на дереве ресурса только бакеты событий. Тесты: `test_keeps.py::test_deleting_the_camera_does_not_erase_the_events_somebody_marked`, `test_alarm_tree.py::test_a_keep_holds_the_alarms_tree_as_it_holds_the_other`, `test_doors.py::test_the_resources_doors_name_nothing_outside_the_tree`, `test_lesson10_events.py::test_three_subsystems_events_reach_one_timeline_through_the_resource_process_and_the_console`, `test_lesson10_events.py::test_a_pass_longer_than_the_pulse_keeps_the_resources_heartbeat_fresh`. Маршруты проверяются настоящим HTTP на `port=0`.

## Что нужно знать заранее

- **М10A, урок 14** — `Resource`: heartbeat, `pass_`, `retain`, `relieve`, `mirror`, `restore`, `serve`, `kept`.
- **М10A, урок 13** — `EventIndex`: дерево бакетов, прочитанное там, где лежит.
- **М10A, урок 12** — бакеты событий и чей бакет под каким деревом.
- **[Урок 8](08-visibility-retention-timeline.md)** — почему видео больше не нужно удалять по сроку.

## Чему вы научитесь

1. Приносить подсистему на чужой процесс одним атрибутом.
2. Отдавать платформе знание, которого у неё нет, не отдавая решения.
3. Разделять в цикле две работы так, чтобы отказ одной не останавливал другую.
4. Писать цикл процесса, у которого нет ни контроллера, ни назначения.
5. Читать имена ключей как утверждение о принадлежности.

---

## Шаг 1 — Что ресурс делает и чего не делает

```
It has no controller: it has a policy pass on a timer, a heartbeat, its HTTP, and
the event index over its own tree.
```

Четыре вещи, и ни одной из них не нужен контроллер.

**Проход политики на таймере** — не решение, а правило (урок 14 М10A). Удалить бакеты старше срока, сказать, сколько места не хватает, отправить закрытые бакеты соседу. Решать тут нечего.

**Heartbeat** — ресурс рассказывает о себе: адрес, место на диске, какие подсистемы на нём лежат, чьи копии он держит. По нему ресурс находят консоль и индекс событий.

**HTTP** — чтение бакетов и запись копий соседей. Единственный способ добраться до событий сервера с другой машины.

**Индекс событий** — ответ на `GET /events` над собственным деревом.

Чего нет: размещения (ресурс там, где он есть), эпохи (у него нет конкурентов за его дерево), слота (он один на сервер и назван сервером), назначения (никто ему ничего не назначает).

И теперь нет ещё одного: **видео**. Таймлайн камеры и её кадры отвечают двери регистраторов ([урок 8](08-visibility-retention-timeline.md), [урок 12](12-the-vms-console.md)).

## Шаг 2 — Чьё дерево

Имена ключей в шапке — доказательство границы:

```
    platform/resources/<server>/heartbeat   {server, ts, url, usage, units, mirrors} — how the console finds it
    GET <url>/events?from&to&cam&kind&subsystem&unit   the platform's: this resource's EventIndex
    GET <url>/buckets/<sub>/<unit>, /events/<path>, /mirrored/<server>; PUT /mirror/<server>/<path>
```

`platform/resources/<server>/heartbeat`, а не `vms/resources/…`. Все маршруты — платформенные. Если бы ресурс был частью VMS, ключ назывался бы иначе, и детекторы (урок 14) не могли бы писать бакеты на тот же ресурс, не спросив VMS.

На дереве лежат бакеты нескольких писателей:

- `vms/<cam>/e<epoch>/…` — события камеры, их пишет воркер, держащий её эпоху;
- `vms.alarms/<cam>/…` — тревоги камеры, со своим сроком;
- `rec/<name>/e<epoch>/…` — то, что регистратор пишет о записи: `archive.shallow`, `archive.keep.copied`, `archive.keep.lost`;
- `console/<instance>/…` и `audit/console/…` — отметки оператора и журнал консоли.

Каждый срок хранения задаёт контроллер своей подсистемы строкой `<sub>/retention/<unit>`. Ресурс читает строки и удаляет файлы, ничего не понимая в их смысле (урок 14 М10A).

Почему видео здесь больше нет — три причины, и каждая снимает целый механизм.

**Чинить нечего.** У тома нет манифеста рядом: индекс ведёт движок.

**Удалять по сроку нечего.** Том — кольцо, оно само отдаёт старейшие блоки. `retention_days` записи стал потолком видимости, и его применяет дверь регистратора, а не ресурс.

**Освобождать под ватерлинией нечего.** Кольцо никогда не вырастает больше своей квоты. Платформенная ватерлиния (`relieve`) осталась и по-прежнему измеряет диск. Но просить освободить место ей некого:

```python
            for sub, h in self.hooks.items():
                free = getattr(h, "free", None)
                if free is None:
                    continue                                 # a subsystem that keeps only buckets: `retain` is its whole policy
```

VMS теперь именно такая подсистема: у неё только бакеты.

Тест `test_doors.py::test_the_resources_doors_name_nothing_outside_the_tree` фиксирует уход видео буквально:

```python
        assert _get(f"{url}/segment/{secret}")[0] == 404               # and footage is not a resource's any more
```

Остальные проверки того же теста — платформенные: `/events/<path>`, `/buckets/<sub>/<unit>`, `/mirrored/<server>` и `PUT /mirror/…` не называют ничего за пределами дерева.

## Шаг 3 — Сборка ресурса

```python
def vms_resource(root: str, server: str, url: str, vars_, objects, wall=None, peers=None,
                 bucket_seconds: int = 600) -> Resource:
    """The platform's resource for this server, with the event index over its tree and the VMS's keeps."""
    import time
    wall = wall or time.time
    r = Resource(root, server, url, vars_, objects, bucket_seconds, wall, peers)
    r.index = EventIndex(root, server, wall, bucket_seconds)
    r.kept = kept_buckets(vars_)
    return r
```

Три строки, и каждая — соединение с тем, что написано раньше.

`Resource(...)` — платформенный класс из урока 14 М10A. Первый аргумент теперь корень дерева, а не архив: архива у ресурса больше нет.

`r.index = EventIndex(...)` — **присвоение атрибута, а не аргумент конструктора**. Платформенный `Resource` не обязан держать индекс событий, а этот держит. Запускать индекс не нужно: он ничего не строит и читает дерево бакетов в момент каждого запроса (урок 13 М10A). Ни файла базы, ни переменной окружения для него нет.

`r.kept = kept_buckets(vars_)` — единственное, что VMS добавляет к ресурсу. И это не проход, а **ответ на вопрос**: какие бакеты держит удержание.

Регистрации прохода (`r.register("rec", ArchivePolicy(...))`) больше нет. Дверь `register` в платформе осталась: подсистема со своими файлами на дереве по-прежнему может принести свой проход. В курсе сейчас в неё никто не входит.

## Шаг 4 — Удержания: знание без решения

Оператор отметил десять минут камеры 7 как улику (`rec/keeps/<id>`, `vms/keeps.py`). Видео этих минут регистратор тома `incidents` копирует к себе (урок 8). А события этих минут лежат в бакетах на ресурсе и уйдут по сроку — если ресурс не узнает, что их держат.

Ресурс не знает, что такое удержание. Поэтому платформа открыла дверь в форме функции:

```python
        # What somebody said to keep (feedback BH). The resource does not know what a keep is: whoever built
        # it may set `self.kept` — called once a pass, it returns `(subsystem, unit, start, end) -> bool`.
        # It matters most for `{days: 0}`, which is what a deleted unit's retention becomes: without this,
        # deleting the unit erased the very events somebody had marked. If it raises, the pass fails and
        # nothing is swept: not knowing what is kept is not "nothing is". It reads the store row by row, so it is
        # handed `progressed` like a subsystem's pass, if it takes one (the review's sixth pass).
        kept = _call_hook(self.kept, progressed=self._progressed) if self.kept is not None else None
```

VMS отвечает на этот вопрос:

```python
# Which event buckets a keep holds (`vms/keeps.py`), for the platform's retention pass. The camera's events
# are in `vms/<cam>/`; whatever a recorder wrote about a recording is in `rec/<name>/`. Read once a pass.
def kept_buckets(vars_):
    from . import keeps

    def once(progressed=None):
        store = vars_ if progressed is None else _Marked(vars_, progressed)
        # A keep whose row does not parse is held as far as it reads (`keeps.as_far_as_read`; the review's seventh pass:
        # it raised out of here, and the resource's whole `retain` — every unit, every server — swept nothing while it
        # stood). Its camera's buckets only: a unit of no one camera is held by the keeps that read (`sound`), and not
        # by an interval open to the start or the end of time (the review's eighth pass, part 4).
        unread: list = []
        all_ = keeps.declared(store, unread) + unread
        sound = [k for k in all_ if not k.garbled]
        if not all_:
            return lambda sub, unit, start, end: False
        cams = cameras_of_units(store)
        recs = {u: str(it.get("cam") or u) for u, it in _rows(store, "rec", "recordings").items()}

        def kept(sub: str, unit: str, start: float, end: float) -> bool:
            from w2cplatform.events import tree_owner
            sub = tree_owner(sub)[0]                 # a keep holds the alarms' tree as it holds the other
            if sub == "vms":
                return keeps.held(keeps.spans_of_cam(all_, str(unit)), start, end)
            if sub == "rec":                         # named in the keep, or a recording of its camera made since
                return keeps.held(keeps.spans_of(all_, str(unit), recs.get(str(unit), "")), start, end)
            if sub in ("det", "survey", "detjob", "auto"):
                of = cams.get((sub, str(unit)), ANY)
                spans = [(k.since, k.until) for k in sound] if of is ANY else \
                    [sp for cam in of for sp in keeps.spans_of_cam(all_, cam)]
                return keeps.held(spans, start, end)
            return False
        return kept
    return once
```

**Не только `vms` и `rec`.** Так удержание держало два дерева — а тревоги детекторов, обзора, сканов и сценариев внутри отмеченного интервала уходили по своему сроку (ревью платформы, B10; четвёртое ревью). Теперь раз за проход `cameras_of_units` читает строки единиц — и удалённые тоже — и узнаёт, о какой камере каждая: детектор, обзор и скан — по полю `cam`, сценарий — по единицам в `when` и `then`. Единица, чью камеру не узнать (триггер на любую камеру, нет строки, JSON не разбирается), держится **каждым** удержанием, интервал которого читается (`sound`): не знать, чья, — не значит ничья. Удержание с испорченной границей такие единицы не держит — следующий абзац. Тест: `test_keeps.py::test_a_keep_holds_every_subsystems_events_about_its_camera`.

**И читает она под пульсом прохода.** Чтобы ответить, `once` читает из хранилища удержания и строки пяти таблиц — по одной, и между ними не было ни одной отметки прогресса: часть прохода, которая всё время движется, выглядела стоящей (шестое ревью, сосед находки про `usage()` и удаления; М10A, урок 14). Теперь ресурс передаёт ей `progressed`, и все чтения идут через обёртку `_Marked`: отметка после каждой строки и каждого списка. Тест: `test_lesson10_events.py::test_reading_what_is_kept_marks_every_row_it_reads` — 600 строк на хранилище, где каждое чтение стоит десятую долю предела.

**Одна испорченная метка держит свою камеру настолько, насколько читается, а не останавливает хранение.** `keeps.declared` разбирал каждую строку `rec/keeps/*` голым `float`. Метка камеры 9 с `since: "yesterday"` бросала исключение из `once`, а платформенный `retain` по своему правилу («не знаю, что удержано, — не удаляю ничего») не удалял ничего ни у кого. Три прохода подряд у камер 7 и 8 осталось 20 из 20 старых вёдер, и диск заполнялся (седьмое ревью, часть 2, воспроизведено запуском). Теперь метки читает общий читатель строк (`keeps.KEEPS`, М10A, урок 8, шаг 5). Строка, которая не разбирается, пропускается, считается один раз, пока снова не станет читаться, и один раз попадает в лог. Ресурс говорит о таких строках в heartbeat'е (`rows_garbled`) и на `/metrics` консоли (`<p>_resource_rows_garbled{server,table}`). Строка без камеры не удерживает ничего: метка, не называющая камеры, ничья, и это сказано в логе.

**Что значит «насколько читается»** (восьмое ревью, часть 4, воспроизведено запуском). Седьмое ревью приводило такую строку к `keeps.whole` — метке её камеры от начала времён до их конца, — какое бы поле ни было испорчено, даже `at`, время постановки. И каждая единица, которая ни о какой одной камере (сценарий на любую камеру, детектор без строки), держалась ею целиком: с `at: "yesterday"` удалилось 10 вёдер там, где исправная метка отпускала 37, а у трёх таких единиц осталось 10 из 10, и ватерлиния их не освобождала. Правило теперь такое. Сделать метку нечитаемой может только интервал: `at` — метаданные, слово там читается как «не сказано» (`rows.number`), и метка держит то, что говорит. Граница, которая разбирается, остаётся; потерянная открыта в свою сторону: без `from` — от начала времён до `to`, без `to` — от `from` дальше, без обеих — камера целиком (`keeps.as_far_as_read`). Такая метка держит бакеты **своей** камеры — `vms`, `rec` и единиц, чья строка называет эту камеру, — и ничего из единиц ни одной камеры: их держат метки, которые читаются (`sound`), потому что исправная метка — короткий интервал, а испорченная — нет, и держать такие единицы вечно из-за одного слова — значит заполнять диск. Копирующий регистратор такую метку не копирует — открытый интервал не диапазон для копии — и сохраняет то, что уже скопировал по ней, до её починки (урок 18). Чего здесь нет: в `GET /keeps` битая метка не показывается, и тревоги по возрасту битой метки нет — консоль не входит в этот урок. Тесты: `test_row_reader.py::test_one_garbled_keep_holds_its_camera_whole_and_the_others_are_swept`, `test_row_reader.py::test_a_garbled_keep_holds_its_camera_as_far_as_it_reads_and_nothing_of_the_units_of_no_camera`.

**Две функции, а не одна.** Внешняя `once` зовётся раз за проход и читает все удержания одним запросом. Внутренняя `kept` зовётся на каждый бакет и только сравнивает интервалы. Читать хранилище на каждый бакет означало бы тысячи запросов за проход на годовом архиве.

**Решение остаётся у ресурса.** VMS не удаляет и не запрещает удалять. Она отвечает «да» или «нет» на вопрос о бакете, а удаляет или оставляет ресурс.

**Отказ хранилища не равен «удержаний нет».** `keeps.declared` поднимает исключение, если хранилище не ответило. Проход тогда падает целиком и ничего не удаляет. Обратное решение стёрло бы именно отмеченное, и именно тогда, когда хранилище недоступно.

**Два дерева, два способа сопоставления.** Бакеты `vms/<cam>/` названы камерой, и удержание сопоставляется по камере (`spans_of_cam`). Бакеты `rec/<name>/` названы записью, и удержание сопоставляется по имени записи (`spans_of`). `tree_owner` приводит дерево тревог `vms.alarms` к `vms`: тревоги камеры держатся так же, как её события.

Самый важный случай — удалённая камера. Её срок становится `{days: 0}`, и следующий проход удалил бы все её бакеты. Тест `test_keeps.py::test_deleting_the_camera_does_not_erase_the_events_somebody_marked` проверяет: у камер 7 и 8 срок ноль, удержание стоит на минуте камеры 7, и `retain()` удаляет два бакета — камеры 8 и камеры 7 вне удержания. Тест `test_alarm_tree.py::test_a_keep_holds_the_alarms_tree_as_it_holds_the_other` проверяет то же для дерева тревог.

## Шаг 5 — Цикл процесса

```python
def resource() -> None:
    """The resource process: no controller — a policy pass, a heartbeat, its HTTP,
    and the event index over its own tree."""
    import socket
    import time
    from w2cplatform.resource import serve
    from .resource import vms_resource
    vars_ = open_vars(CONFIG_URL)
    objects = FsObjectStore(os.path.join(root, "objects"))
    host, port = os.environ.get("RESOURCE_HOST", "127.0.0.1"), int(os.environ.get("RESOURCE_PORT", "8090"))
    res = vms_resource(os.environ.get("ARCHIVE", "/data/archive"), socket.gethostname(),
                       os.environ.get("RESOURCE_URL", f"http://{host}:{port}"), vars_, objects)
    srv = serve(res, host, port)
```

Имя ресурса — **имя хоста**. Не слот и не индекс: ресурс один на сервер, а у сервера уже есть имя. Взятие слота по CAS здесь было бы ритуалом, который ничего не защищает.

`RESOURCE_URL` отдельно от `host:port`, потому что адрес снаружи может отличаться от адреса прослушивания. Этот адрес попадает в heartbeat, и по нему консоль ходит за событиями.

`serve(res, host, port)` — без `extra`. Раньше здесь стояло `extra=vms_routes(archive)`. Теперь своих маршрутов у VMS на ресурсе нет, и платформенный сервер отвечает 404 на всё, чего не знает сам.

**Дверь ресурса ограничена, как остальные, и копию бакета не держит в памяти целиком.** Защиты двери — предел соединений, срок на заголовки — были только у консоли, а `PUT /mirror/…` читал в память `Content-Length` байт, сколько бы там ни стояло, на двери, которая никого не спрашивает (шестое ревью, обход всех мест, где читается тело). Теперь `serve` строит сервер через `door_server`: не больше 64 соединений сразу и 32 с одного адреса, следующее — 503 на месте, а строка запроса и заголовки должны прийти целиком в срок (`Deadlined`). Удержанные запросы (`WAITERS_MAX`, 16) и одновременные `/events` (`EVENTS_INFLIGHT`, 8) помещаются в долю одного адреса с запасом: это вычислители и консоль одного сервера. Копия бакета больше `MIRROR_MAX` (64 МиБ — десять минут событий, со штормом) — 413, и ничего не читается; меньше — пишется во временный файл кусками по 64 КиБ, а тело, оборвавшееся раньше объявленной длины, — 400 и никакой копии: прежняя остаётся, половины новой нет. Кто стучится в эту дверь, она по-прежнему не спрашивает: аутентификация дверей между процессами отложена до mTLS — решение владельца (обратная связь DL). Тест: `test_console_load.py::test_the_resources_door_is_bounded_and_a_mirrored_bucket_is_never_held_whole`.

**И у тела копии есть срок, а бакет уходит кусками** (седьмое ревью, воспроизведено запуском). После заголовков тело `PUT /mirror` читалось только под таймаутом сокета на каждое чтение. 32 соединения, объявившие по 60 МБ и шлющие по байту раз в двадцать секунд, держали долю адреса вечно, а с двух адресов — всю дверь. Теперь тело должно прийти целиком за `timeout` двери плюс секунду на каждые `BODY_RATE` байт (`body_deadline`). Не пришло — 408, и копии нет. В обратную сторону `GET /events/<бакет>` отдавал бакет одним `f.read()`. Теперь он идёт кусками по `STREAM_PIECE` с названной длиной, под темпом `Paced`, и медленный сосед получает его целым, а не никогда. Свой клиент зеркала у ресурса тоже больше не держит бакет целиком: `mirror` отдаёт соединению открытый файл (`PeerClient.put_file`), `restore` пишет ответ в файл кусками (`get_into`, урок 14 М10A). Тесты: `test_console_load.py::test_the_resources_door_gives_a_mirrored_body_a_deadline_whole_and_a_subsystems_write_too`, `test_a_bucket_goes_out_in_pieces_to_a_slow_reader_and_is_never_held_whole`, `test_the_mirror_sends_and_takes_back_a_bucket_in_pieces_never_whole`.

```python
    try:                                                                  # a store away at the start does not end the process
        res.heartbeat()                                                   # (the review's eighth pass, beside М11's minor)
    except Exception:                                                     # noqa: BLE001
        logging.exception("resource heartbeat failed")
    # Outside the loop and in a try of its own (the review's seventh pass): a peer whose heartbeat or copy does not
    # parse raised out of here, and the resource process ended at every start — no door, no heartbeat, no pass.
    try:
        logging.info("restore: %s", res.restore())
    except Exception:                                                     # noqa: BLE001
        logging.exception("restore failed — the buckets peers hold of this server stay with them; the process goes on")
```

**Порядок из двух шагов, и он строгий.**

`heartbeat()` первым: заявить о себе до всякой работы. Восстановление может занять минуты (копирование бакетов от соседей после замены диска, урок 14 М10A). Всё это время консоль и контроллеры должны видеть, что ресурс есть.

**Одного heartbeat'а до восстановления мало — оно бьётся само.** Первый heartbeat живёт `lost_after`, 45 секунд, а 2000 вёдер по 50 мс тянутся 100 секунд. Всё это время ресурс для индекса событий молчал: окно неполное, курсор автоматики стоит, консоль показывает ресурс молчащим, хотя его дверь отвечает (седьмое ревью, часть 1, M4). Теперь `restore` идёт под тем же пульсом, что проход (`Resource._pulsing`, урок 14 М10A). Каждое ведро — отметка прогресса, и пока восстановление движется, последний heartbeat уходит со свежим временем каждые десять секунд. Тест: `test_row_reader.py::test_restore_beats_under_the_same_pulse_as_the_pass`.

`restore()` вторым: забрать с соседей бакеты, которые они держали в копиях, пока этот сервер лежал. Индексу событий отдельный шаг не нужен: он читает дерево в момент запроса, и вернувшиеся бакеты видны, как только легли на диск.

```python
    last_policy = 0.0
    while not stop.is_set():
        # Two jobs, two tries (feedback BI): a pass that reads the store must not stop the heartbeat — with the
        # store away the resource stopped HEARTBEATING, was called silent, and the recordings were moved off a
        # server that was perfectly well.
        try:
            res.heartbeat()
        except Exception:                                                 # noqa: BLE001
            logging.exception("resource heartbeat failed")
        try:
            if time.time() - last_policy >= 600:
                last_policy = time.time()                                 # a pass that raised is tried in ten minutes, not in ten seconds
                logging.info("policy: %s", res.pass_())
        except Exception:                                                 # noqa: BLE001
            logging.exception("resource pass failed")
        # What the restore left with peers — a peer that did not answer, a bucket that did not come — is asked for again,
        # its pause doubling up to ten minutes (`Resource.restore_due`; the review's eighth pass): it ran once, at the start.
        try:
            if res.restore_due():
                logging.info("restore again: %s", res.restore())
        except Exception:                                                 # noqa: BLE001
            logging.exception("restore failed again; asked again later")
        stop.wait(10)
    srv.shutdown()
```

Heartbeat каждые десять секунд, проход политики каждые десять минут, а восстановление, оставившее вёдра у соседей, — снова, когда пройдёт его пауза.

**Восстановление спрашивается снова, пока не вернётся всё** (восьмое ревью, часть 4). `restore` шёл один раз, до цикла, в одном `try`, и всё, что не пришло — сосед отказал, ведро оборвалось, — оставалось у соседей, пока копии там не старели и не выметались. Теперь `Resource.restore` берёт у каждого соседа и каждое ведро отдельно, а то, что осталось, делает восстановление должным (`restore_due`): через 10 секунд, потом через 20, 40 — до десяти минут. Цикл спрашивает об этом на каждом обороте, в своём `try`. Состояние — в heartbeat'е ресурса (`restore`) и на `/metrics` (`vms_resource_restore_left`). Как это устроено — урок 14 М10A, шаг 6. Первый heartbeat тоже в своём `try`: хранилище, не ответившее при старте, больше не обрывает процесс до цикла. Тест: `test_row_reader.py::test_a_restore_takes_what_every_peer_gives_and_asks_again_for_what_did_not_come`.

**Почему периоды разные.** Heartbeat дёшев и нужен часто: по нему решают, жив ли сервер. Проход обходит дерево бакетов; чаще чем раз в десять минут в этом нет смысла.

**Почему два `try`, а не один.** Так было: один `try` на обе работы. Проход читает хранилище, а без хранилища он падал — и heartbeat вместе с ним. Ресурс переставал заявлять о себе, его объявляли молчащим, и записи уводили с сервера, у которого всё было в порядке (обратная связь BI). Две работы отказывают независимо и значат разное, поэтому у каждой своя попытка.

**Почему `last_policy` ставится до прохода.** Проход, упавший с исключением, повторится через десять минут, а не через десять секунд. Иначе ресурс при недоступном хранилище обходил бы дерево шесть раз в минуту и каждый раз падал.

Платформенный `pass_` идёт по порядку: проходы подсистем (у VMS их нет), `retain` с удержаниями, `relieve`, `mirror` (урок 14 М10A). Пока он идёт, отдельный поток повторяет последний heartbeat с новым временем. На годовом архиве проход длиннее срока, после которого ресурс считают молчащим, и без этого пульса сервер объявили бы мёртвым посреди прохода. Это проверяет `test_lesson10_events.py::test_a_pass_longer_than_the_pulse_keeps_the_resources_heartbeat_fresh`. Пульс повторяется, только пока проход движется: каждое ведро в обходах `retain` и `mirror` отмечает прогресс, а список закрытых вёдер читается по именам, без разбора файлов (пятое ревью; урок 14 М10A). Так же отмечаются каждый файл, измеренный в `usage()`, каждое удаление в `retain` и каждая строка, которую читает `kept_buckets` (шестое ревью: по модели теста 2000 вёдер давали 399,8 с без отметки в `usage` и 371 с в `retain` при пределе 2 с; тест `test_measuring_the_tree_and_removing_what_is_old_keep_the_pulse_with_a_mark_per_file`).

`srv.shutdown()` на выходе. Слота нет, отпускать нечего, и различения «аккуратная остановка против падения» здесь тоже нет: ресурс никуда не переезжает.

## Шаг 5а — Запрос, который держат

**Читатель событий может попросить дверь сказать, когда записана строка, которую он смотрит.** До 2 октября 2026 читатель узнавал о новой строке одним способом: спрашивал `/events` на своём проходе, раз в две секунды. Теперь у той же двери есть маршрут, который не отвечает сразу, — `GET /events/wait?want=vms/io.input/12,det/motion&timeout=30&client=<экземпляр>`: запрос **держится**, пока под корнем этого ресурса не появится строка названного вида в названной подсистеме — у названной единицы (`vms/io.input/12` — контакты камеры 12) или у любой (`det/motion`), — и тогда получает `{"changed": true, "seq": …, "touched": ["vms/io.input/12"]}`; за `timeout` секунд ничего — `{"changed": false, …}`. В ответе нет ни одного события — только какие из названных единиц изменились: читатель следующим делом задаёт свой обычный вопрос `/events` и читает то, что прочёл бы и так. Кто этим пользуется и зачем — урок 25, шаг 10; здесь — что это стоит ресурсу.

```python
            if self.path == "/events/wait" or self.path.startswith("/events/wait?"):
                q = {k: v[0] for k, v in urllib.parse.parse_qs(self.path.partition("?")[2]).items()}
                try:
                    timeout = float(q.get("timeout", WAIT_MAX))
                    since = int(q["since"]) if q.get("since") not in (None, "") else None
                    wants = parse_wants(q.get("want", ""))       # nothing, not a name, too many: 400 (the review's seventh pass)
                except ValueError as e:
                    return self._raw(400, json.dumps({"error": str(e)}).encode(), [("Content-Type", "application/json")])
                rep = resource.watch.wait(wants, timeout, since, gone=lambda: client_gone(self.connection),
                                          client=q.get("client") or None)   # one held request per evaluator
```

**Что нельзя попросить, получает 400, а не догадку.** `parse_wants` молча выбрасывал всё, что не похоже на `подсистема/вид`: пустой `want` держал место тридцать секунд и ни на что не отвечал, `want=../../x/k` отправлял наблюдателя листать каталог вне томов, а число пар не ограничивал никто (седьмое ревью). Теперь каждое из трёх — `ValueError`, и дверь отвечает 400: ничего не названо; подсистема или единица — не одно имя (`safe_segment`: обе — сегменты пути под томом); названо больше `WANTS_MAX` (64). Тест: `test_long_poll.py::test_a_want_is_refused_when_it_is_empty_not_a_name_or_too_many`.

**Та же дверь и те же права, что у `/events`.** Маршрут стоит в том же обработчике, перед разбором `/events/<путь>`, и спрашивает ровно столько же, сколько `/events`: ничего нового не открыто, и тот, кто мог читать события, может ждать их. Слот запросов (`events_slots`, восемь одновременных `/events`) он не занимает: удержанный запрос тридцать секунд ничего не делает, и шестнадцать таких не должны закрыть дверь тем самым вопросам, которые они ускоряют.

**Как ресурс замечает строку: смотрит на файлы, и только пока кто-то ждёт.** Ресурсу никто не говорит, что строка записана: писатели дописывают файлы и никого не зовут. Поэтому, пока есть хоть один ждущий, один поток раз в `WATCH_TICK` (0,1 с) делает `stat` файлам, куда новая строка может лечь, — текущему бакету каждой **названной** единицы (каждой единицы подсистемы — для желания без единицы), в самой новой эпохе, в дереве подсистемы и в дереве её тревог (и предыдущему бакету первые пять секунд после границы):

```python
        for sub, unit, d in self._dirs:
            first = (sub, unit) not in self._based   # a unit first looked at: from here
            based.add((sub, unit))
            for name in names:
                p = os.path.join(d, name)
                self.stats += 1
                try:
                    size = os.stat(p).st_size
                except OSError:
                    size = 0
                old = size if first else self._sizes.get(p, 0)
                if size > old:
                    kinds, old = self._kinds(p, old, size)
                    seen.update((sub, k, unit) for k in kinds)
                sizes[p] = min(old, size)
```

Имя текущего бакета вычисляется, а не ищется, поэтому файл, которого ещё нет, — это `stat` с ошибкой, а первая строка в нём — рост от нуля. Выросший файл читается с того места, где стоял, и только целыми строками; из каждой берётся `kind`, единица — из того, чей это каталог, и ждущие, назвавшие эту единицу (или любую), получают ответ вместе со списком тронутых (`touched`). Нет ждущих — нет потока и ни одного `stat`: `test_long_poll.py::test_with_nobody_waiting_the_watcher_looks_at_nothing`.

**Цена — то, о чём спросили, а не всё, что лежит на ресурсе.** Наблюдатель смотрел каждую единицу каждой ожидаемой подсистемы, хотя ждали одну: тысяча камер — 7 % ядра при одном ждущем, пять тысяч — 31 % и такт дольше 100 мс (седьмое ревью). Теперь желание с единицами смотрит только их каталоги, а каталог перечитывается, только когда сдвинулось его mtime (появилась единица или эпоха) — или он менялся последние `MTIME_SLACK` (2 с), на случай файловой системы с грубыми часами:

```python
    def _listed_dir(self, path: str, used: set, make):
        try:
            mtime = os.stat(path).st_mtime_ns
        except OSError:
            return None
        used.add(path)
        now = time.time()                            # the file system's clock, which is what an mtime is in
        have = self._dircache.get(path)
        if have is not None and have[0] == mtime and now - mtime / 1e9 > MTIME_SLACK:
            return have[2]
        try:
            got = make(os.listdir(path))
        except OSError:
            return None
        self._dircache[path] = (mtime, now, got)
        return got
```

Измерено на тысяче камер, у каждой и дерево тревог: желание `vms/io.input/7` — два `stat` на такт, сотые доли миллисекунды; желание `vms/io.input` без единицы — 2040 `stat` и около 9 мс на такт, почти 9 % ядра при десяти тактах в секунду. Вычислитель называет единицу всегда, когда её называет триггер сценария (урок 25, шаг 10), так что полную цену платит только сценарий на «любую камеру» — и она остаётся такой, какой была. Новая эпоха названной единицы по-прежнему замечается: её каталог сдвинул mtime, и первая строка в новой эпохе — рост от нуля. Тест: `test_the_watcher_looks_at_the_units_it_was_asked_about_and_lists_a_directory_again_when_it_changed`.

**Чего он не замечает — и почему это не дыра.** Строки, записанные в **старые** бакеты: скан архива и обзор чужого архива ставят событиям время кадра, а оно часы назад (уроки 21 и 23). За ними наблюдатель не смотрит — это были бы все бакеты дерева, тот самый «хвост», от которого индекс ушёл 28 сентября (М10A, урок 13). Строки старой эпохи — их пишет отсечённый писатель, и читатель по ним не действует. И первая строка новой единицы или эпохи замечается с опозданием до секунды. Во всех трёх случаях читатель не теряет ничего, кроме времени: его собственный проход раз в две секунды никуда не делся, и он — страховка для всего, чего ожидание не видит.

**Границы.** Клиент — экземпляр вычислителя, `client=` — держит у ресурса **один** запрос: второй от него же заканчивает первый (тот получает `{"changed": false, "replaced": true}`). Всего удержанных не больше `WAITERS_MAX` — шестнадцать, вдвое больше восьми вычислителей, которые закладываются на ресурс (решение 2 октября 2026), или сколько скажет `LONG_POLL_WAITERS`; следующий получает ответ сразу — `{"changed": false, "full": true}`, и его отправитель возвращается к своему проходу. Раньше предел был один на ресурс без доли клиента, и семнадцатый вычислитель почти всегда получал `full` и молча оставался на двухсекундном проходе (седьмое ревью). Молча — больше нет: сколько держится сейчас и сколько с запуска удержано, отказано и заменено, ресурс говорит в своём heartbeat'е (`waits`, `Watch.counts`), а консоль отдаёт в `/metrics` — `vms_resource_waits`, `vms_resource_waits_held_total`, `vms_resource_waits_full_total`, `vms_resource_waits_replaced_total`. Тест: `test_a_client_holds_one_wait_the_total_is_a_setting_and_the_counts_are_on_the_pulse_and_metrics`. Один запрос держится не дольше `WAIT_MAX` (30 с), что бы он ни просил. Ждущий, чей клиент ушёл, отбрасывается за секунду: раз в секунду проверяется, не закрыто ли соединение (`client_gone`). Проверяется это через `selectors`, а не `select.select`: тот не берёт дескриптор от 1024 и бросает `ValueError`, который читался как «клиент ушёл», — на занятом процессе каждое удержание превращалось в опрос раз в секунду; дескриптор, за которым смотреть не получается, теперь значит «не знаю», и запрос держится до своего таймаута (`test_a_held_request_on_a_descriptor_above_1024_is_still_watched_and_not_taken_for_gone`). А дверь, которая закрывается, отпускает всех, кого держит, — ответом `closed`, сейчас, чтобы читатель не досиживал свой таймаут на ресурсе, которого уже нет: `serve` оборачивает `srv.shutdown()`, и первым делом тот зовёт `resource.watch.close()`. У сервера ресурса поток на запрос, а общий срок — только на строку запроса и заголовки (`Deadlined`, шаг 5); дальше срок есть у каждого чтения, но удержанный запрос ничего не читает, так что удержание ни во что не упирается. Тесты: `test_the_seventeenth_waiter_is_answered_full_at_once_and_the_door_still_serves_events`, `test_shutting_the_door_releases_the_waiters_and_a_client_that_left_is_dropped`, `test_a_wait_with_nothing_happening_is_answered_unchanged_at_its_timeout`.

**Между двумя ожиданиями строка не теряется.** Читатель, получивший ответ, спрашивает снова, и строка, записанная в этот промежуток, упала бы в щель. Щель закрыта дважды. Ответ несёт `seq` — номер, который растёт с каждым замеченным изменением, — и следующий запрос говорит `since=<seq>`: если названный вид менялся после этого номера, ответ приходит сразу. Номер берётся **под замком**, в тот же момент, что и то, что сказано ждущему: раньше его читали после ухода ждущего и вне замка, и изменение, замеченное между двумя этими моментами, попадало в номер, а не в ответ, — подсказка пропадала до обычного прохода читателя (седьмое ревью). И ответы `full` и `closed` номер у читателя больше не двигают: число в отказе ничего не говорит о том, что читателю сказали. Тест: `test_what_a_reader_asks_again_with_never_skips_a_change_and_a_refusal_does_not_move_it`. Чтобы номеру было о чём сказать, подсистему, которую только что ждали, наблюдатель смотрит ещё `LINGER` (2 с) — пока ждёт хоть кто-то другой. А когда уходит последний ждущий и смотреть перестают вовсе, размеры файлов помнятся те же две секунды: строка, дописанная, пока никто не ждал, замечается первым же взглядом после того, как кто-то пришёл (`test_a_line_written_between_two_waits_is_not_lost_between_them`).

## Шаг 6 — Один процесс, две топологии

На коробке это один процесс под systemd (`deploy/resource.container`). В М11 тот же `vms_resource` работает системной задачей на каждом сервере, и `clustervms/cluster/resource.py` его только реэкспортирует:

```python
from vms.resource import vms_resource as cluster_resource  # noqa: F401
```

Ни один файл не переписан. Это и есть проверка, ради которой ресурс писался в М10A как работа платформы, а не как «архив VMS»: сущность, привязанная к серверу, ведёт себя одинаково при одном сервере и при многих.

## Результат

```bash
python3 -m vms resource
```

```
GET /events?from&to&cam=7               → платформенный: индекс событий этого ресурса
GET /events/wait?want=vms/io.input&timeout=30
                                        → платформенный: держится до строки такого вида, потом {changed, seq}
GET /buckets/vms/7                      → платформенный: закрытые бакеты камеры
GET /events/vms/7/e3/…events.jsonl      → платформенный: один бакет
PUT /mirror/box-b/vms/7/e3/…            → платформенный: сосед оставляет копию
GET /segment/…                          → 404: видео отвечают регистраторы
```

```
platform/resources/box-a/heartbeat
    {server: box-a, ts: …, url: http://box-a:8090, usage: …, space: {total, free, …},
     units: {vms: ["7", "8"], rec: ["7", "7-cloud"], console: […]}, mirrors: {box-b: 12}}
```

Ни одного маршрута и ни одного прохода от VMS — один атрибут `kept`.

## Что может пойти не так

- **Heartbeat и проход в одном `try`.** Хранилище недоступно — ресурс молчит, и записи уводят с исправного сервера.
- **Повтор упавшего прохода через десять секунд.** Обход дерева шесть раз в минуту, и каждый раз впустую.
- **Heartbeat после восстановления.** Пока сервер поднимается, его считают мёртвым.
- **Читать удержания на каждый бакет.** Тысячи запросов к хранилищу за один проход.
- **Считать отказ хранилища пустым списком удержаний.** Проход удалит именно отмеченное, и как раз при удалённой камере со сроком ноль.
- **Сопоставлять дерево `rec/` по камере.** Бакет записи `7-cloud` не найдёт удержание, поставленное на камеру 7.
- **Вернуть видео на дерево ресурса.** Появится второй срок хранения рядом с кольцом и второй путь чтения рядом с дверью регистратора, и они разойдутся.
- **Ресурс со слотом и эпохой.** Ритуал без защиты: конкурентов за дерево сервера нет.
- **Удержанный запрос под слотом `/events`.** Восемь ждущих заняли бы все восемь слотов, и дверь отвечала бы 503 тем самым вопросам, ради которых ждут.
- **Смотреть на файлы всегда, а не пока ждут.** Двенадцать тысяч `stat` в секунду на ресурсе, у которого никто ничего не спрашивал.
- **Положить событие в ответ ожидания.** Появится второй путь чтения журнала — без окна, курсора и отсечения по эпохе, — и он разойдётся с первым.

## Итог

- Дерево ресурса — только события; видео лежит в томах и отвечает дверями регистраторов.
- VMS приносит на ресурс один атрибут: `kept`, ответ на вопрос «держит ли удержание этот бакет». Решение об удалении остаётся у ресурса.
- Удержания читаются раз за проход; отказ хранилища останавливает проход, а не превращается в «удержаний нет».
- Ресурс не имеет контроллера: проход по таймеру, heartbeat, HTTP и индекс над своим деревом.
- Порядок старта строгий: заявить о себе, потом восстановить.
- Heartbeat и проход — две работы с двумя попытками; упавший проход повторяется через десять минут.
- Читатель событий может держать у двери запрос (`/events/wait`) и получить ответ, когда записана строка, которую он смотрит. Ответ — подсказка, не события; ресурс смотрит на файлы только пока кто-то ждёт, держит не больше шестнадцати запросов и отпускает их, закрываясь.
- Один и тот же процесс работает на коробке и на каждом сервере кластера; М11 его только реэкспортирует.

## Упражнения

1. Объедините heartbeat и проход в один `try`. Сделайте хранилище недоступным на две минуты и посмотрите, что скажет консоль о ресурсе.
2. Перенесите `last_policy = time.time()` после `res.pass_()`. Сделайте проход падающим и посчитайте обходы дерева за минуту.
3. Читайте `keeps.declared` внутри `kept`, а не в `once`. Посчитайте запросы к хранилищу за проход на ста камерах с бакетами по десять минут за месяц.
4. Поймайте в `once` исключение хранилища и верните пустой список. Удалите камеру с удержанием, сделайте хранилище недоступным и запустите проход.
5. Уберите `tree_owner` из `kept`. Какой тест упадёт и почему?
6. Перенесите `heartbeat()` после `restore()`. Сделайте восстановление долгим и опишите, что увидит консоль.

## Что дальше

Ресурс отдаёт события, двери регистраторов отдают видео. Смотреть на это по-прежнему нечем: консоль из М10A ничего не знает ни о таймлайне камеры, ни об экспорте интервала, ни о живом видео.

> **Утверждение с оговоркой.** Здесь и в уроке 12 чтение нашего архива идёт через двери регистраторов, которые держат тома. Для архива, записанного **не нами** — на карте камеры или на NVR, — появляются состояние, ограниченная достижимость и потолок одновременных чтений. [Урок 15](15-the-archive-we-did-not-write.md) эту оговорку раскрывает.

[**Урок 12**](12-the-vms-console.md) пишет `vms/console.py`: `/timeline/<cam>` из дверей регистраторов, `/export/<cam>` из кадров, дверь WHEP, `LiveFront` — и дерево монтирования, после которого страница из урока 16 М10A показывает VMS целиком.

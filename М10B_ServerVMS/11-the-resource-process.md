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
        all_ = keeps.declared(store)

        def kept(sub: str, unit: str, start: float, end: float) -> bool:
            from w2cplatform.events import tree_owner
            sub = tree_owner(sub)[0]                 # a keep holds the alarms' tree as it holds the other
            if sub == "vms":
                return keeps.held(keeps.spans_of_cam(all_, str(unit)), start, end)
            if sub == "rec":
                return keeps.held(keeps.spans_of(all_, str(unit)), start, end)
            return False
        return kept
    return once
```

**Не только `vms` и `rec`.** Так удержание держало два дерева — а тревоги детекторов, обзора, сканов и сценариев внутри отмеченного интервала уходили по своему сроку (ревью платформы, B10; четвёртое ревью). Теперь раз за проход `cameras_of_units` читает строки единиц — и удалённые тоже — и узнаёт, о какой камере каждая: детектор, обзор и скан — по полю `cam`, сценарий — по единицам в `when` и `then`. Единица, чью камеру не узнать (триггер на любую камеру, нет строки, JSON не разбирается), держится **каждым** удержанием: не знать, чья, — не значит ничья. Тест: `test_keeps.py::test_a_keep_holds_every_subsystems_events_about_its_camera`.

**И читает она под пульсом прохода.** Чтобы ответить, `once` читает из хранилища удержания и строки пяти таблиц — по одной, и между ними не было ни одной отметки прогресса: часть прохода, которая всё время движется, выглядела стоящей (шестое ревью, сосед находки про `usage()` и удаления; М10A, урок 14). Теперь ресурс передаёт ей `progressed`, и все чтения идут через обёртку `_Marked`: отметка после каждой строки и каждого списка. Тест: `test_lesson10_events.py::test_reading_what_is_kept_marks_every_row_it_reads` — 600 строк на хранилище, где каждое чтение стоит десятую долю предела.

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

```python
    res.heartbeat(); logging.info("restore: %s", res.restore())
```

**Порядок из двух шагов, и он строгий.**

`heartbeat()` первым: заявить о себе до всякой работы. Восстановление может занять минуты (копирование бакетов от соседей после замены диска, урок 14 М10A). Всё это время консоль и контроллеры должны видеть, что ресурс есть.

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
        stop.wait(10)
    srv.shutdown()
```

Heartbeat каждые десять секунд, проход политики каждые десять минут.

**Почему периоды разные.** Heartbeat дёшев и нужен часто: по нему решают, жив ли сервер. Проход обходит дерево бакетов; чаще чем раз в десять минут в этом нет смысла.

**Почему два `try`, а не один.** Так было: один `try` на обе работы. Проход читает хранилище, а без хранилища он падал — и heartbeat вместе с ним. Ресурс переставал заявлять о себе, его объявляли молчащим, и записи уводили с сервера, у которого всё было в порядке (обратная связь BI). Две работы отказывают независимо и значат разное, поэтому у каждой своя попытка.

**Почему `last_policy` ставится до прохода.** Проход, упавший с исключением, повторится через десять минут, а не через десять секунд. Иначе ресурс при недоступном хранилище обходил бы дерево шесть раз в минуту и каждый раз падал.

Платформенный `pass_` идёт по порядку: проходы подсистем (у VMS их нет), `retain` с удержаниями, `relieve`, `mirror` (урок 14 М10A). Пока он идёт, отдельный поток повторяет последний heartbeat с новым временем. На годовом архиве проход длиннее срока, после которого ресурс считают молчащим, и без этого пульса сервер объявили бы мёртвым посреди прохода. Это проверяет `test_lesson10_events.py::test_a_pass_longer_than_the_pulse_keeps_the_resources_heartbeat_fresh`. Пульс повторяется, только пока проход движется: каждое ведро в обходах `retain` и `mirror` отмечает прогресс, а список закрытых вёдер читается по именам, без разбора файлов (пятое ревью; урок 14 М10A). Так же отмечаются каждый файл, измеренный в `usage()`, каждое удаление в `retain` и каждая строка, которую читает `kept_buckets` (шестое ревью: по модели теста 2000 вёдер давали 399,8 с без отметки в `usage` и 371 с в `retain` при пределе 2 с; тест `test_measuring_the_tree_and_removing_what_is_old_keep_the_pulse_with_a_mark_per_file`).

`srv.shutdown()` на выходе. Слота нет, отпускать нечего, и различения «аккуратная остановка против падения» здесь тоже нет: ресурс никуда не переезжает.

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

## Итог

- Дерево ресурса — только события; видео лежит в томах и отвечает дверями регистраторов.
- VMS приносит на ресурс один атрибут: `kept`, ответ на вопрос «держит ли удержание этот бакет». Решение об удалении остаётся у ресурса.
- Удержания читаются раз за проход; отказ хранилища останавливает проход, а не превращается в «удержаний нет».
- Ресурс не имеет контроллера: проход по таймеру, heartbeat, HTTP и индекс над своим деревом.
- Порядок старта строгий: заявить о себе, потом восстановить.
- Heartbeat и проход — две работы с двумя попытками; упавший проход повторяется через десять минут.
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

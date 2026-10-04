# Урок 12 — Консоль VMS

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/console.py` — `vms_routes` (`/timeline/<cam>`, `/export/<cam>`, `/segment?cam=`, `/whep`), `recorder_doors`, `unserved_volumes`, `_rec_epoch`, `device_spans`, `recordings_of`, `LiveFront` (дверь WHEP: `offer`, `where`, `hangup`, `status`), `make_console` (дерево монтирования) и `serve`.
**Время:** ~80 минут.

## Зачем этот урок

Страница из урока 16 М10A умеет всё: список, формы, таймлайн, плеер, живое видео, отметки. Она просит `/timeline/<id>`, медиа каждого спана и `/whep/<cam>` — и до сих пор их никто не отдаёт.

Урок их отдаёт, и шапка файла говорит, сколько для этого нужно:

```
    GET  /timeline/<cam>?from&to          every recording of the camera, from every recorder's archive door,
                                          fenced epochs marked; the device's own where ours has nothing
    GET  /export/<cam>?rec&from&to        the frames of an interval as a fragmented MP4 — what the page plays
```

И сразу — откуда берутся байты:

```
Footage is not on this box's disk to be served by path. It is in volumes of ObjectStorage, each written by the
recorder that holds it, and every recorder serves its own (`archive_routes`, `vms/recworker.py`): the console
asks them, the way it asks the resources for events.
```

Четыре вещи, ради которых урок стоит читать.

**Консоль не читает диск.** Раньше она отдавала файл сегмента по пути. Теперь видео лежит в томах, и каждый том отвечает через дверь регистратора, который его держит ([урок 8](08-visibility-retention-timeline.md)). Консоль спрашивает двери так же, как спрашивает ресурсы о событиях.

**Недоступно — не значит потеряно.** Дверь, которая не ответила, и том, который сейчас никто не держит, консоль называет по имени, а не рисует на их месте дыру.

**Консоль не носит живое медиа.** `LiveFront` создаёт единицу вещания, находит шлюз, передаёт ему предложение и переписывает адрес сессии на себя. Дальше RTP идёт шлюз → браузер, минуя консоль.

**Дерево монтирования.** `Mount` из урока 15 М10A получает своё применение: VMS на корне, остальные подсистемы — путями. Один процесс, один порт, одна страница.

> **Проверка без железа.** Весь урок. Таймлайн и экспорт идут против настоящего `obsd` (`conftest.py`: `store`, `footage`, `door` — дверь регистратора над томом и heartbeat, который её объявляет); GStreamer не нужен. Тесты: `test_lesson6_controller.py::test_the_console_over_http` (вся поверхность на настоящем порту), `test_rec_volume.py::test_a_volume_nobody_serves_is_named_on_the_timeline_and_not_drawn_as_a_hole`, `test_slot_and_read.py::test_archive_read_says_what_left_and_the_digest_of_what_left`, `test_slot_and_read.py::test_an_export_takes_each_moment_from_the_epoch_that_owns_it_whichever_door_holds_it`, `test_review_remainder.py::test_who_read_the_archive_is_an_event_and_once_a_minute`, `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path`; в М11 — `Source/tests/cluster/test_lesson3_resources.py::test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves`.

## Что нужно знать заранее

- **М10A, уроки 15 и 16** — `SpecConsole`, `Mount`, `extra`, страница.
- **[Урок 8](08-visibility-retention-timeline.md)** — дверь архива (`/timeline/<unit>`, `/samples/<unit>`), отсечённые спаны, `authoritative`.
- **[Урок 10](10-recworker.md)** — регистратор держит один том и объявляет `archive_url` и `volume` в heartbeat.
- **[Урок 11](11-the-resource-process.md)** — ресурс отдаёт события и больше не отдаёт видео.
- **М10A, урок 13** — `MergedIndex`: почему у консоли нет своего индекса событий.

## Чему вы научитесь

1. Добавлять подсистеме маршруты, не трогая платформу.
2. Собирать один ответ из многих источников и называть те, что не ответили.
3. Отсекать по строке эпохи в хранилище, когда источник знает только свою.
4. Отличать «недоступно» от «потеряно» в ответе и в коде.
5. Превращать интервал архива в файл, который играет браузер, и записывать, что ушло.
6. Проксировать установление сессии, не становясь на путь данных.
7. Собирать несколько подсистем в один процесс и одну страницу.

---

## Шаг 1 — Что VMS добавляет к консоли

```python
def vms_routes(media: bool = True, live: LiveFront | None = None, ctl=None, rec_ctl=None):
    """What the VMS adds to the generic console: the footage — from every recorder's archive and from the
    device's own — and the WHEP door to the live gateways. Returns None when a route is not ours, so the
    console answers 404."""
```

Протокол `extra` из урока 15 М10A: `None` — не мой маршрут, `()` — я ответил сам, кортеж — ответ.

**`extra`, а не наследование.** Маршруты VMS регистрируются функцией, а не добавляются подклассом `SpecConsole`. Подкласс знал бы о платформе изнутри, функция знает только форму ответа. Следующая правка платформы не сломает VMS.

**`media` — флаг «есть ли видео за этой консолью».** Раньше вместо него передавался объект архива на диске. Теперь видео за дверями регистраторов, и консоли нужно знать одно: показывать ли его.

```python
        if method != "GET" or not media:
            return None
```

Консоль без видео отвечает на маршруты видео 404. Так построена вторая консоль в тесте идемпотентности (`serve(b, None, …)`): она создаёт камеры, показывает список и не отдаёт видео. Подсистема, которая не всё умеет, выражает это отсутствием маршрута, а не флагом в каждом ответе.

`ctl` и `rec_ctl` — контроллеры, которые у консоли и так есть. `ctl` даёт хранилище (heartbeat'ы регистраторов, строки эпох) и часы. `rec_ctl` переводит камеру в её записи.

## Шаг 2 — Двери регистраторов

```python
# Every recorder that serves its archive, live: `[(name, url, heartbeat)]`. A recorder holds ONE volume and its
# door answers for it — a camera recorded into two volumes, or one whose recording moved, is answered by two.
def recorder_doors(objects, now: float, lost_after: float = 45.0) -> list:
    out = []
    for name, hb in sorted(heartbeats(objects, "rec/").items()):
        url = str(hb.extra.get("archive_url") or "")
        if url and now - hb.ts <= lost_after:
            out.append((name, url.rstrip("/"), hb))
    return out
```

Список дверей — из heartbeat'ов, тем же приёмом, каким регистратор находит камеру, а шлюз — свою подписку. Каталога дверей нет, и поддерживать его некому.

**Почему спрашиваются все двери, а не одна.** Один регистратор держит один том. Запись камеры за свою жизнь может оказаться в нескольких томах: запись переехала на другой сервер, у камеры две записи (`7` на дисках и `7-cloud` в сетевом хранилище), удержание скопировано в том `incidents`. Каждый том отвечает за своё, и полный ответ — это ответы всех.

**Почему 45 секунд.** Регистратор старше этого молчит, и спрашивать его дверь — ждать таймаута на каждом вопросе. Молчащие регистраторы нужны консоли для другого вопроса (шаг 4).

## Шаг 3 — Таймлайн камеры

```python
    def timeline(cid: str, q: dict):
        t0, t1 = float(q.get("from", 0)), float(q.get("to", 1e12))
        ours, unreachable = [], []
        doors = recorder_doors(ctl.objects, con_wall()) if ctl is not None else []
        for unit in recordings_of(rec_ctl, cid):
```

Маршрут спрашивают про камеру, а том знает записи. Перевод делает одна функция:

```python
def recordings_of(rec_ctl, cam) -> list[str]:
    if rec_ctl is None:
        return [str(cam)]                      # no rec controller mounted: the old assumption, said out loud
    units = [str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == str(cam)]
    return units or [str(cam)]                 # nothing declared: the camera's own name, so old footage still shows
```

Два запасных ответа — обычные состояния, а не красота. Консоль без подсистемы `rec` собирают в тестах и в М11. Камера без строки записи могла записываться раньше под своим именем. В обоих случаях честный ответ «спроси поток с именем камеры» лучше пустого списка: видео прошлой конфигурации никуда не делось.

`cid` — строка. Сравнение идёт с полем `cam` строки записи, тоже строкой, и запись `7-cloud` проходит так же, как `7`.

Дальше каждая запись спрашивается у каждой двери:

```python
            # Fenced against the RECORDING's epoch, which the store holds — a door knows only its own recorder's,
            # and the zombie's stream may be in another volume than the survivor's. A copy (`e0`, a keep's) is
            # nobody's writer and is never fenced.
            cur = _rec_epoch(ctl, unit)
            for name, url, hb in doors:
                try:
                    body = json.loads(_door(f"{url}/timeline/{unit}?from={t0}&to={min(t1, 1e11)}", DOOR_TIMEOUT))
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                for sp in body.get("spans", []):
                    fenced = bool(sp.get("fenced")) or (cur is not None and 0 < int(sp.get("epoch", 0)) < cur)
                    ours.append({**sp, "fenced": fenced, "recording": unit, "recorder": name,
                                 "volume": hb.extra.get("volume", ""), "media": f"/export/{cid}?rec={unit}"})
```

**Отсечение по строке эпохи записи.** Дверь помечает `fenced` по эпохе своего регистратора ([урок 8](08-visibility-retention-timeline.md)). Этого мало. Регистратор упал на сервере A, запись взял регистратор на сервере B под следующей эпохой. Поток зомби лежит в томе A, и дверь A сравнивает его со своей же эпохой — для неё он не отсечён. Сравнить его с эпохой выжившего может только тот, кто прочитает строку `rec/epoch/<unit>` в хранилище:

```python
def _rec_epoch(ctl, unit) -> int | None:
    from w2cplatform.epoch import current_epoch
    try:
        return current_epoch(ctl.vars, f"rec/epoch/{unit}") or None
    except OSError:
        return None                                # the store did not answer: the doors' own word stands
```

Хранилище не ответило — консоль не выдумывает эпоху и оставляет пометки дверей как есть. Тест М11 `test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves` строит ровно этот случай: эпоха 3 на сервере A, эпоха 4 на сервере B, строка `rec/epoch/7` говорит 4. Таймлайн даёт `[("r-1", 3, True), ("r-1", 3, True), ("r-2", 4, False)]`.

**Копия удержания не отсекается.** Условие `0 < epoch` пропускает поток `<запись>/e0`. Копию в томе `incidents` пишет регистратор этого тома, а не держатель записи; эпоха ноль значит «ничья аренда», и отсекать в ней нечего.

**Каждый спан говорит, чей он и как его играть.** `recording`, `recorder`, `volume` — чтобы страница могла подписать спан. `media` — маршрут экспорта этой записи; минуты к нему добавит страница (шаг 6).

**Дверь, которая не ответила, называется.** `DOOR_TIMEOUT = 5.0`: дверь, которая не ответила за пять секунд, попадает в `unreachable`, и консоль идёт дальше. Комментарий над `timeline` объясняет выбор: *таймлайн с дырой, которую страница объясняет, лучше таймлайна, который не приходит.*

Тест `test_lesson6_controller.py::test_the_console_over_http` проверяет простой случай: одна дверь, десять минут записи, и таймлайн камеры — `[(t, t + 600, "/export/1?rec=1")]`.

## Шаг 4 — Недоступно, не потеряно

Регистратор, который молчит, не попадает в список дверей. Но его том никуда не делся.

```python
# The volumes nobody serves right now: a recorder went silent holding one, and no live recorder holds it since —
# the server is down, its disk with it, or a network archive is waiting for a spare. Its footage is not LOST: it is
# in that volume, and it is unavailable until a recorder holds the volume again. `[{volume, server, since}]`, from
# the recorders' last heartbeats; the timeline names them instead of drawing a hole where they are (М11 lesson 8).
def unserved_volumes(objects, now: float, lost_after: float = 45.0) -> list[dict]:
    live, stale = set(), {}
    for name, hb in heartbeats(objects, "rec/").items():
        vol = str(hb.extra.get("volume") or "")
        if not vol:
            continue                               # a spare holds nothing
        if now - hb.ts <= lost_after:
            live.add(vol)
        elif vol not in stale or hb.ts > stale[vol]["since"]:
            stale[vol] = {"volume": vol, "server": str(hb.extra.get("server", "")), "recorder": name, "since": hb.ts}
    return [v for k, v in sorted(stale.items()) if k not in live]
```

Том попадает в список, если его последний держатель молчит и ни один живой регистратор его не держит. Если том уже взял другой регистратор — например, сетевой том подхватил запасной, — он не «никем не обслуживается», и консоль о нём молчит.

Без этой функции страница нарисовала бы дыру там, где лежит видео недоступного сервера. Оператор решил бы, что записи нет, и стал бы искать её на карте камеры или списывать как потерянную. С ней ответ говорит, где видео и почему его сейчас не видно:

```python
        if unreachable or gone:
            notes = []
            if unreachable:
                notes.append("a recorder's archive door did not answer: its footage is missing from this picture")
            if gone:
                notes.append("footage in " + ", ".join(f"{g['volume']} (on {g['server']})" for g in gone) +
                             " is unavailable until a recorder holds it again — not lost")
            return 200, {"segments": spans, "unreachable": sorted(set(unreachable)), "unavailable": gone,
                         "note": "; ".join(notes)}
        return 200, spans
```

**Две формы ответа.** Всё ответило — простой список. Что-то не ответило — объект с `segments`, `unreachable`, `unavailable` и `note`. Страница принимает обе формы и показывает `note` над таймлайном. Простой случай остаётся простым, а сложный не притворяется простым.

Тест `test_rec_volume.py::test_a_volume_nobody_serves_is_named_on_the_timeline_and_not_drawn_as_a_hole` записывает heartbeat регистратора `r-a` с томом `disks-a` десятиминутной давности и поднимает живую дверь `r-b` над томом `disks-b`. Таймлайн даёт спан от `r-b`, в `unavailable` — `disks-a` на `srv-a`, а в `note` — «unavailable» и «not lost». Когда `r-a` снова присылает heartbeat, ответ опять становится простым списком.

Та же формулировка — «недоступен, не потерян» — стоит в ответе `LiveFront` про шлюз, который не отвечает (шаг 7). Это одно правило в двух местах: консоль сообщает «сейчас нельзя», а не «этого нет», и ничего не удаляет.

## Шаг 5 — Что есть на устройстве

К нашим спанам консоль добавляет то, что записало само устройство, — там, где у нас ничего нет:

```python
def coverage_of(found) -> tuple[float, float] | None:
    if found is None:
        return None
    cov = found[2].get("coverage")
    if not cov:
        return None
    key = f"vms/{HEARTBEATS}/{found[0]}#coverage"
    try:
        return finite(cov["from"]), finite(cov["to"])
    except PARSE_ERRORS as e:
        FIELDS.garbled(key, e)
        return None


def device_spans(objects, cam, ours: list[dict], t0: float, t1: float, now: float, eyes=None) -> list[dict]:
    cov = coverage_of(holder_of(objects, "vms/", cam, now, field="coverage", eyes=eyes))
    if cov is None:
        return []
    want = (max(cov[0], t0), min(cov[1], t1))
    if want[1] <= want[0]:
        return []
    have = [(s["start"], s["end"]) for s in ours]
    return [{"start": a, "end": b, "media": None, "epoch": 0, "source": "device",
             "fenced": False, "device": True} for a, b in subtract(want, have)]
```

`eyes` — глаза контроллера консоли (М10A, урок 7, шаг 7, «Чьи часы»; тринадцатое ревью, блокер 4): держатель — тот, чей heartbeat **менялся** за 45 с по часам консоли, а не тот, чей `ts` близок к ним. Держатель на сервере с часами на 50 с позади был «никто» — у камеры не было ни спанов устройства, ни `/segment` («nobody holds this camera right now»), пока он её держал. Без глаз (`eyes=None`) — прежнее сравнение, для разового взгляда.

`subtract` — та же функция, по которой регистратор решает, что дозаписывать (урок 16). Одно правило в двух местах, поэтому картинка и работа не могут разойтись. Такой спан исчезнет первым: наш архив держит недели, карта камеры — дни.

**Покрытие держателя читается в одном месте — `coverage_of`.** Раньше `float(cov["from"])` стоял голым в трёх маршрутах: здесь, в `/segment` и в нижней границе `POST /backfill`. Слово в покрытии одного держателя — и таймлайн камеры уходил без ответа, а кусок с её устройства тоже (ответ на девятое ревью, «следующим заходом»; воспроизведено запуском). Теперь покрытие, которое не читается, — то же, что держатель, который покрытия не объявляет: спанов устройства нет, кусок держится одним потолком `SEGMENT_MAX`. Поле посчитано один раз (`vms/heartbeats/<держатель>#coverage` в таблице `field`). Слово в самом запросе — `/timeline/7?from=yesterday`, `nan` в `/export` — теперь 400; раньше `float` бросал мимо всего, и ответа не было. Тест: `test_one_bad_element.py::test_a_holders_coverage_that_is_a_word_costs_its_spans_and_not_the_timeline_or_the_segment`.

Сыграть такой спан консоль не может: у неё нет кадров устройства. Маршрут `/segment` теперь отвечает только про устройство — адрес двери воспроизведения у воркера, который держит камеру сейчас:

```python
        if (path == "/segment" or path == "/segment/") and ctl is not None:                 # the device's own footage, through its holder
            return segment(handler, q)
```

```python
    def segment(handler, q: dict):
        from . import playback as pb
        cam, raw0, raw1 = str(q.get("cam") or ""), q.get("from", 0), q.get("to", 1e12)
        try:
            t0, t1 = pb.times(raw0, raw1)
        except (TypeError, ValueError):
            return 400, {"detail": "from and to are unix seconds, and to is after from", "error": "bad range"}
        found = holder_of(ctl.objects, "vms/", cam, con_wall(), field="playback_url", eyes=ctl.eyes)   # by change (13th)
        if found is None:
            return 503, {"detail": "nobody holds this camera right now", "error": "unheld"}
        url, key = found[2]["playback_url"], found[1].extra.get("playback_key") or None
        cov = coverage_of(found)                          # a word in it: held to the ceiling alone, as an older build
        lo, hi = float(t0), float(t1)
        if cov is not None:
            lo, hi = max(lo, cov[0]), min(hi, cov[1])
            if hi <= lo:
                return 404, {"detail": f"the device holds nothing of camera {cam} in that interval (it holds "
                                       f"{cov[0]:.0f}..{cov[1]:.0f})", "error": "nothing there"}
        if hi - lo > SEGMENT_MAX:
            return 400, {"detail": f"a piece of the device's footage is at most {SEGMENT_MAX:.0f} s; this one is "
                                   f"{hi - lo:.0f} s of what the device holds — ask for less", "error": "range too long"}
        if (lo, hi) != (float(t0), float(t1)):
            (t0, t1), raw0, raw1 = pb.times(lo, hi), lo, hi
        who = handler.headers.get("X-User", "operator")
        ...
        if key is None:
            return 200, {"playback": f"{url}?from={raw0}&to={raw1}"}
        return 200, {"playback": f"{url}?{pb.signed_query(key, cam, t0, t1, who, con_wall())}", "until": round(until)}
```

Держатель ищется в момент запроса, а не записывается в спан при рисовании. Камера, переехавшая между рисованием и щелчком, иначе дала бы 404. Подробно этот путь разбирает [урок 15](15-the-archive-we-did-not-write.md).

**А сама дверь — по подписи.** Консоль проверяла `view` и писала журнал — а потом отдавала браузеру голый адрес двери держателя, и зритель камеры 1, поменяв в адресе `1` на `2`, забирал запись камеры 2 с её карты мимо ворот и журнала (четвёртое ревью, блокер 4). Токен в адрес класть нельзя — в нём все права человека, а `<video src>` заголовка не пошлёт. Поэтому консоль выдаёт **короткоживущий подписанный адрес**: камера, интервал, срок (300 с) и зритель, подписанные ключом самой двери (`vms/playback.py`). Ключ держатель создаёт, когда открывает дверь, и объявляет в heartbeat'е (`playback_key`) — не в статусе камеры, который виден странице; настраивать и менять его руками не нужно. Регистратор и обзор читают дверь по возможности на камеру, выведенной из того же ключа (`/playback/<cam>/<cap>`). Дверь спрашивает, только когда кластер в домене (`Gate.gated`), и сама пишет в журнал: `archive.read source=device` на подписанное чтение и `access.denied` на отказ. Тест: `test_console_gate.py::test_the_devices_own_door_opens_only_to_what_the_console_signed` — правленая камера, растянутый интервал, чужое имя, без подписи, чужая возможность, просроченный адрес — все 403.

**Подписывается только то, что у устройства есть, и не больше часа.** Консоль подписывала любой интервал — сутки карты, `0..1e12`, — а дверь держателя читала его одним `read` в один буфер. Держатель — процесс, который держит все камеры своего сервера: на запуске 1000 с карты при 100 кБ/с дали 100 МБ в его памяти, и зрителю с `view` на одну камеру хватало запросить сутки, чтобы держатель упал (пятое ревью, major, воспроизведено на `FakeDevice`). Теперь `segment` до подписи подрезает интервал по покрытию, которое держатель объявляет в heartbeat'е (`coverage`): ничего в интервале — 404, а длиннее `SEGMENT_MAX = 3600.0` после подрезки — 400, как экспорт с его `EXPORT_MAX`. Сама дверь (`VmsWorker.playback_pieces`) просит у устройства не больше `PLAYBACK_PIECE = 60.0` секунд за раз, по одной сессии устройства, и отдаёт каждый кусок, как только прочла. Клиенту HTTP/1.1 ответ идёт кусками (chunked), и последний кусок пишется, только когда прошли все: устройство, отказавшее посреди, даёт ответ, оборванный на виду. Первый кусок читается до заголовков, поэтому 404 «архива нет» и 503 «устройство занято» по-прежнему ответы, а не обрыв. Тест: `test_console_gate.py::test_a_segment_is_signed_for_what_the_device_holds_and_the_door_streams_it_a_piece_at_a_time` — сутки, запрошенные у карты на 1000 с, подписаны как `0..1000`; интервал вне покрытия — 404; `0..1e12` у карты на 10 000 с — 400; ответ двери chunked, без `Content-Length`, целиком, ни один `read` не больше минуты, и открыта одна сессия за раз.

**Срок адреса — по часам консоли, а проверяет его держатель по своим.** Если часы двух машин расходились больше чем на `TTL`, любой адрес был «просрочен» в момент выдачи, и отказ не говорил почему (пятое ревью, minor). Теперь адрес несёт момент подписи (`at`, под подписью), и `check_signed` прощает расхождение до `SKEW = 60.0` секунд в обе стороны. Дальше отказ называет разницу, как её измерила дверь, и говорит, что чинить надо часы (NTP), а не спрашивать консоль заново. Адрес, подписанный в будущем двери дальше `SKEW`, тоже отказ: иначе консоль со спешащими часами выдавала бы адреса, живущие дольше `TTL`. Тест: `test_console_gate.py::test_the_doors_expiry_forgives_clocks_a_little_apart_and_names_the_difference_when_they_are_not` — консоль на 400 с впереди и на 700 с позади получает отказ с этими числами и словом NTP; адрес без `at` — «не подписан», правленый `at` — «не совпадает».

**И это чтение архива — строка журнала.** Консоль не отдаёт кадров устройства, но отдаёт адрес двери, где их взять, — и раньше не писала об этом ничего (третье ревью). Теперь выдача адреса — `archive.read` с `source=device`, камерой, интервалом, именем и адресом вызывающего. Тест: `test_review_remainder.py::test_the_door_to_a_devices_own_footage_is_said_when_it_is_handed_out`.

Файла по пути консоль не отдаёт больше никогда. Тест `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path` проверяет, что `/segment/<абсолютный путь>` — 404.

## Шаг 6 — Экспорт интервала

Спан на таймлайне говорит `media: "/export/7?rec=7"`. Страница режет спан на куски по десять минут и для каждого просит экспорт:

```javascript
function segmentURL(s, p) {
  return `${s.media}${s.media.includes('?') ? '&' : '?'}from=${p.from}&to=${p.to}`;
}
```

```javascript
const PIECE = 600;
```

Один кусок играет, следующий ставится, когда этот кончился. Непрерывное воспроизведение через MSE и всё, что браузер делает с файлом, — [урок 24](24-an-interval-in-the-browser.md).

На стороне консоли:

```python
    def export(handler, cid: str, q: dict):
        who = (getattr(handler, "headers", None) or {}).get("X-User", "operator")
        mine = max(1, int(os.environ.get("EXPORTS_PER_USER", EXPORTS_PER_USER)))
        with per_user_lock:
            if per_user.get(who, 0) >= mine:
                return busy(f"{who} is making {per_user[who]} export(s) already, as many as one person makes at once — retry")
            per_user[who] = per_user.get(who, 0) + 1
        whole = []                                       # the last chunk, held back until the slots are free again
        try:
            if not exporting.acquire(blocking=False):
                return busy("this console is making as many exports as it makes at once — retry")
            try:
                return _export(handler, cid, q, whole)
            finally:
                exporting.release()
        finally:
            with per_user_lock:
                per_user[who] -= 1
                if not per_user[who]:
                    del per_user[who]
            # The file is whole, its line is in the journal and its slots are given back: only now is the client told
            # it is done — a client that asks for the next export the moment this one ends finds its slot free.
            for b in whole:
                try:
                    handler.wfile.write(b)
                except OSError:
                    pass
```

`export` — только слоты: один человек, все сразу, и последний кусок, отложенный до их возврата. Сам экспорт — `_export`, ниже.

**И не держать слот вечно.** Клиент, который запросил экспорт и не читает ответ, держал слот до перезапуска консоли, а у её соединений не было срока вовсе (четвёртое ревью, воспроизведено двумя молчащими сокетами). Теперь у каждого соединения консоли срок сокета (`CONSOLE_TIMEOUT`, 30 с на каждое чтение и запись, и не только на тело экспорта; строка запроса и заголовки после пятого ревью приходят целиком за те же 30 с — `DeadlineReader`, М10A, урок 15), у экспорта — предел по темпу клиента (`EXPORT_MIN_RATE`, ниже; оборванный — `broken` в строке журнала), и один человек держит один слот (`EXPORTS_PER_USER`). Экспорт камеры с двумя записями без `rec` падал на замыкании генератора — теперь поток каждой записи строится со своими значениями (`stream_of`). Тесты: `test_a_client_that_reads_nothing_lets_its_export_go_and_one_person_holds_one_slot`, `test_an_export_of_a_camera_with_two_recordings_and_no_rec_is_both_of_them`. И каждая целая выгрузка — строка журнала всегда; склеиваются по минуте только куски для плеера.

**Предел экспорта — темп клиента, а не часы, и обрыв виден.** После четвёртого ревью у экспорта был бюджет `EXPORT_BUDGET` — 900 с на интервал до 3600 с. Час камеры на 8 Мбит/с — 3,6 ГБ, так что бюджет молча закладывал канал 32 Мбит/с. Честный оператор за VPN на 10 Мбит/с получал первые девятнадцать минут часа как `200` и файл, который просто кончался, будто это всё (пятое ревью, major, воспроизведено клиентом на 1 МБ/с: 4,7 из 9,85 МБ и никакой ошибки). Теперь бюджета нет: экспорт идёт, пока клиент берёт в среднем не меньше `EXPORT_MIN_RATE` (64 КиБ/с), считая после `EXPORT_GRACE` (60 с на первые ответы дверей). Тот же час через тот же VPN идёт около пятидесяти минут и приходит целым, а клиент, читающий по байту в минуту, обрывается через минуту, как раньше. И обрыв видно: клиенту HTTP/1.1 файл идёт кусками (`Transfer-Encoding: chunked`), а последний, нулевой кусок `export` пишет только для целого файла — после строки журнала и после того, как отдал слоты. Ответ без него — ошибка для curl, браузера и `http.client` (`IncompleteRead`), а не короткий фильм. У клиента HTTP/1.0 такой разметки нет: конец соединения для него — конец файла, и отличить обрыв от целого может только `broken` в журнале. Тест: `test_slot_and_read.py::test_an_honest_slow_client_gets_the_whole_export_and_a_cut_one_is_seen_as_cut` — медленный клиент выше предела получает файл целиком с последним куском, клиент ниже предела — ответ без него, а журнал пишет `broken` без суммы.

**И не больше двух сразу.** Экспорт часа камеры на 8 Мбит/с — около 3,6 ГБ кадров в памяти плюс MP4; два-три таких запроса от любого, у кого есть `view`, роняли консоль, а с ней — цикл заявок (третье ревью). Теперь экспорты идут через семафор (`EXPORTS_AT_ONCE`, по умолчанию 2), лишний получает 503 с `Retry-After: 5`. И каждый — потоком: экспорт читает каждый отрезок у двери кусками по минуте (`EXPORT_PIECE`, по ключевым кадрам, как дозапись), сводит записи камеры по времени (`heapq.merge`, около куска на запись в памяти) и пишет MP4 фрагмент за фрагментом (`fmp4.Writer`). Заголовки уходят на первом ключевом кадре — 404 «нечего отдать» и 415 «не играется» по-прежнему отвечаются до первого байта; `Content-Length` нет, конец файла — последний кусок chunked для HTTP/1.1 (выше) и конец соединения для HTTP/1.0; дверь, отказавшая посреди, называется в журнале (`archive.read`, поле `unreachable`), а sha256 считается по мере отдачи. Тест: `test_an_export_is_read_a_minute_at_a_time_and_written_as_it_is_made` — файл тот же байт в байт, что собранный целиком. Тест: `test_slot_and_read.py::test_exports_held_in_memory_at_once_are_bounded_and_the_next_one_is_told_when_to_come_back`.

**Интервал, и ограниченный.** `EXPORT_MAX = 3600.0`: страница просит минуты, человек — до часа. Экспорт собирался в памяти целиком, и запрос «с 1970 года» без потолка был бы способом уронить консоль; теперь он идёт потоком (выше), а потолок остался — час видео это и час чтения у двери. Концы в неправильном порядке и интервал длиннее часа — 400. И `nan` — тоже 400 (`finite`): как `float` он проходил обе проверки, потому что любое сравнение с ним ложно (десятое ревью, обход).

**Кадр, который не становится MP4, — беда этого кадра.** `FRAME_ERRORS = (ValueError, struct.error, IndexError, OverflowError)`: размер, не влезающий в поле `>I` или `>H` (`struct.error`), пустой NAL (`IndexError`). До первого байта это 415 «не играется», после — файл, оборванный на виду, со строкой `broken` в журнале. Раньше ловился один `ValueError`, а `struct.error` уходил мимо строки журнала (ответ на девятое ревью, «узкие наборы исключений»).

```python
    def _export(handler, cid: str, q: dict, whole: list | None = None):
        import hashlib
        import heapq
        import struct
        from . import fmp4
        try:                                             # `nan` passed both checks below as `float` (the tenth round)
            t0, t1 = finite(q.get("from", 0)), finite(q.get("to", 0))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        if t1 <= t0 or t1 - t0 > EXPORT_MAX:
            return 400, {"detail": f"an export is an interval of at most {EXPORT_MAX:.0f} s", "error": "bad range"}
        # Each moment from the EPOCH that owns it, across every door — a door applies `authoritative` to the
        # volume it holds, and a fenced writer's stream may be in another volume than the survivor's. So the doors'
        # timelines are asked first, the rule is run over all of them, and each stretch is read from the door that
        # holds its owner. A door that does not answer is named in the reply's headers: a piece with a hole the
        # caller can see.
        from w2cplatform.obsd import Sample, unix_s
        from .archive import Span, authoritative
        units = recordings_of(rec_ctl, cid)
        if q.get("rec"):
            units = [u for u in units if u == str(q["rec"])]
            if not units:
                return 404, {"detail": f"recording {q['rec']} is not a recording of camera {cid}", "error": "not hers"}
        doors = recorder_doors(ctl.objects, con_wall()) if ctl is not None else []
        unreachable: list[str] = []

        def frames_of(name: str, url: str, unit: str, lo: float, hi: float):
            at = lo
            while at < hi:
                top = min(hi, at + EXPORT_PIECE)
                try:
                    got = sorted(Sample.decode_all(_door(f"{url}/samples/{unit}?from={at}&to={top}", 30.0)),
                                 key=lambda s: s.begin)
                except (OSError, ValueError, struct.error):
                    unreachable.append(name)
                    return
                nxt = top
                if top < hi:
                    cut = next((i for i in range(len(got) - 1, -1, -1) if got[i].key and unix_s(got[i].begin) > at), None)
                    if cut is not None:
                        nxt, got = unix_s(got[cut].begin), got[:cut]
                yield from got
                at = nxt

        def stream_of(unit: str, where: dict, stretches: list):
            for span, lo, hi in stretches:
                yield from frames_of(*where[span], unit, lo, hi)

        streams = []
        for unit in units:
            spans, where = [], {}
            for name, url, _ in doors:
                try:
                    body = json.loads(_door(f"{url}/timeline/{unit}?from={t0}&to={t1}", DOOR_TIMEOUT))
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                for sp in body.get("spans", []):
                    span = Span(unit, int(sp.get("epoch", 0)), float(sp["start"]), float(sp["end"]), int(sp.get("bytes", 0)),
                                str(sp.get("source", "live")))
                    spans.append(span)
                    where.setdefault(span, (name, url))
            stretches = sorted(authoritative(spans, t0, t1), key=lambda x: x[1])
            streams.append(stream_of(unit, where, stretches))
```

`frames_of` читает отрезок кусками по `EXPORT_PIECE` и режет кусок по последнему ключевому кадру, как регистратор режет то, что сажает (`RecWorker._pieces`): следующий кусок начинается с этого кадра. `stream_of` — функция, а не генераторное выражение в цикле, чтобы `unit` и `where` были этой записи (четвёртое ревью, выше). `rec` выбирает одну из записей **этой** камеры — запись другой камеры 404 (второе ревью).

**Каждый момент — от эпохи, которая им владеет, через все двери.** Интервал записи может лежать в двух томах: поток отсечённого писателя в одном, поток выжившего в другом. Каждая дверь применяет `authoritative` только к своему тому (`Archive.samples`, урок 8). Спроси консоль `/samples` у всех дверей и возьми кадры того, кто отсортировался первым, — минуты перекрытия пришли бы от зомби, если его дверь стоит в списке раньше. Поэтому консоль сначала спрашивает таймлайны всех дверей (быстро, `DOOR_TIMEOUT`), запускает `authoritative` над всеми спанами сразу и запоминает, какая дверь держит какой спан (`where`). Потом каждый отрезок читается у двери его владельца. Таймаут чтения кадров — 30 секунд, а не 5: дверь читает кадры, а не индекс.

`test_slot_and_read.py::test_an_export_takes_each_moment_from_the_epoch_that_owns_it_whichever_door_holds_it` кладёт `e1` зомби в том `a`, а `e2` выжившего — в том `b`, с минуты 5 по 10 и с кадрами крупнее. С одной дверью `a` экспорт берёт всё из `e1`. С обеими он длиннее больше чем на 25 крупных кадров: минуты 5–10 пришли из `e2`, хотя дверь `r-a` стоит в списке первой.

**Дверь, которая не ответила до первого байта, названа; дверь, отказавшая после него, обрывает файл.** Имя двери попадает в `unreachable` — и когда не ответил таймлайн, и когда не пришли кадры отрезка. Пока не ушёл ни один байт, экспорт отдаётся с тем, что есть, а заголовок `X-Archive-Unreachable` перечисляет молчавшие двери: кусок с дырой, о которой вызывающий знает, лучше отказа целиком. Но дверь, отказавшая **после** первого байта, в заголовок уже не попадёт, — и до шестого ревью она лишь заканчивала свой отрезок, а файл шёл до конца: экспорт 9,85 МБ, чья дверь встала после 1 МБ, приходил как `200` в 1,9 МБ с правильным последним куском, и в журнале стоял sha256, как у целого файла (шестое ревью, major, воспроизведено запуском). Дыра, которую нельзя сказать заголовком, говорится единственным оставшимся способом — **как обрыв**: `frames_of` поднимает ошибку, ответ кончается без последнего куска (клиенту HTTP/1.1 это `IncompleteRead`), а строка журнала пишется с `broken`, с именем двери в `unreachable` и без sha256. Тест: `test_slot_and_read.py::test_a_door_that_stops_answering_after_the_first_byte_breaks_the_export_and_the_journal_says_so`.

Тот же класс стоял этажом ниже, у самой двери регистратора, и ревью его не называло. `/samples/<unit>` шёл без разметки, только до конца соединения, и по **последовательности** за раз — так что том, отказавший между двумя последовательностями, оставлял читателю целые записи и ничего, что отличило бы их от всех: укороченный диапазон, принятый за всё, что есть у источника, — и экспортом консоли, и регистратором, копирующим из резервной записи. Теперь дверь пишет кадры chunked и последний кусок — только когда поток кончился целым (`send_route`), а оба читателя берут ответ без него за то, что он есть: `IncompleteRead` — ошибка (`RecWorker.read_samples`, `vms.console._door`). Тест: `test_slot_and_read.py::test_a_recorders_door_cut_between_two_sequences_is_an_error_to_its_readers_never_a_shorter_range`.

**Ответ без рамки — не целый ответ.** Куски или длина — то, по чему короткий ответ отличается от целого; ответ без того и другого — дверь, говорящая на HTTP/1.0, или прокси, снявший разметку, — кончается там, где кончилось соединение, и дверь, отказавшая посреди, выглядела ровно как дверь, которой больше нечего дать (седьмое ревью, minor). `_door` теперь требует `Transfer-Encoding: chunked` или `Content-Length` и иначе поднимает `ConnectionError`: экспорт говорит, что дверь не ответила, а не пишет фильм короче. Так же читает кадры регистратор, копирующий из резервной записи (`RecWorker.read_samples`). **Но заголовок — ещё не рамка** (восьмое ревью, minor). Проверялось, есть ли заголовок, и `Content-Length: ten`, `-1` или `Transfer-Encoding: gzip, chunked` на ответе, оборванном закрытием, принимались за целый ответ. Теперь оба читателя спрашивают `http.client`, прочёл ли он из ответа длину или куски (`w2cplatform.console.framed`: `r.chunked` — только при `chunked` без других кодировок, `r.length` — только при длине-числе не меньше нуля). Тест: `test_slot_and_read.py::test_an_answer_with_neither_chunks_nor_a_length_is_not_taken_for_a_whole_one` — все три заголовка на ответе, оборванном посередине, отказ у обоих читателей.

**Ответ, который не разбирается, — дверь, которая не ответила, что бы ни бросил разборщик.** `door_timeline` ловил `ValueError` и `OSError`, а дверь — или прокси перед ней, — ответившая скобками, вложенными глубже, чем идёт разборщик, давала `RecursionError`, которого не ловил никто. Таймлайн камеры и её экспорт были 500, и минуты хорошей двери терялись вместе с ними (девятое ревью, minor, воспроизведено запуском; насколько глубоко идёт разборщик, зависит от стека потока — у ревью хватило 100 000 скобок). Теперь разбор ответа и его отрезков ловит `PARSE_ERRORS` и превращает в отказ этой двери. Дверь попадает в `unreachable`, остальные рисуются и выгружаются. Тот же список — у ответа шлюза на `DELETE` живой сессии (`LiveFront.hangup`: 502 вместо 500) и у `keep_missing` из heartbeat регистратора на `/metrics`. Тест: `test_slot_and_read.py::test_a_door_whose_timeline_is_brackets_past_the_parsers_depth_is_a_door_that_did_not_answer` — миллион скобок от одной двери, таймлайн и экспорт — 200, дверь названа (до правки — `RecursionError`).

```python
        sent = {"bytes": 0, "sha": hashlib.sha256(), "head": False}
        chunked = getattr(handler, "request_version", "") == "HTTP/1.1"

        class Out:
            def write(self, b: bytes) -> None:
                if not b:
                    return
                handler.wfile.write(b"%x\r\n%s\r\n" % (len(b), b) if chunked else b)
                sent["bytes"] += len(b); sent["sha"].update(b)

        writer, frag, end, broken, said = None, [], None, None, 0
        floor = float(os.environ.get("EXPORT_MIN_RATE", EXPORT_MIN_RATE))
        grace = float(os.environ.get("EXPORT_GRACE", EXPORT_GRACE))
        began = time.monotonic()
        try:
            for smp in heapq.merge(*streams, key=lambda s: s.begin):
                took = time.monotonic() - began
                if sent["head"] and took > grace and sent["bytes"] < floor * took:
                    raise TimeoutError(f"the client took {sent['bytes']} bytes in {took:.0f} s, slower than the "
                                       f"{floor:.0f} bytes a second an export is given (EXPORT_MIN_RATE)")
                if end is not None and smp.begin < end:
                    continue                             # this moment came from another door already
                if writer is None:
                    if not smp.key:
                        continue
                    try:
                        sps, pps = fmp4.param_sets(smp.body)
                        width, height = struct.unpack("<II", smp.sub[:8]) if len(smp.sub) >= 8 else (0, 0)
                        writer = fmp4.Writer(Out(), sps, pps, width, height)
                    except ValueError as e:
                        return 415, {"detail": str(e), "error": "not playable"}
                    if chunked:
                        handler.protocol_version = "HTTP/1.1"
                    handler.send_response(200)
                    handler.send_header("Content-Type", "video/mp4")
                    if unreachable:
                        handler.send_header("X-Archive-Unreachable", ",".join(sorted(set(unreachable))))
                    if chunked:
                        handler.send_header("Transfer-Encoding", "chunked")
                    handler.send_header("Connection", "close")
                    handler.end_headers()
                    handler.close_connection = True
                    sent["head"], said = True, len(unreachable)
                if smp.key and frag:
                    writer.write_fragment(frag)
                    frag = []
                frag.append(fmp4.Sample(fmp4.to_avcc(smp.body), max(1, int(smp.end - smp.begin)), smp.key))
                end = smp.end
            if writer is None:
                return 404, {"detail": f"no footage of camera {cid} in that interval", "error": "nothing recorded"}
            writer.write_fragment(frag)
            if chunked:
                if whole is None:
                    handler.wfile.write(b"0\r\n\r\n")
                else:
                    whole.append(b"0\r\n\r\n")
```

**Каждый момент — один раз.** Кадры всех записей сводятся по времени (`heapq.merge`: в памяти около куска на запись). Кадр, который начинается раньше конца уже взятого, пропускается: этот момент уже пришёл. Нужно это и после `authoritative`: дверь начинает каждый отрезок с ключевого кадра на его первом моменте или раньше (урок 8), и подводка следующего отрезка ложится на конец предыдущего.

**Файл начинается с ключевого кадра.** Иначе плеер ничего не покажет до первого ключевого.

**Пусто — 404, а не пустой файл.** Пустой MP4 плеер покажет как испорченный файл. 404 с `nothing recorded` говорит, что записи в этом интервале нет.

**Заголовки — на первом ключевом кадре.** До него ответом ещё может быть 404 «нечего отдать» или 415 «не играется»; после — уже нет. `fmp4.Writer` пишет фрагментированный MP4 фрагмент за фрагментом — фрагмент на группу кадров, параметры потока (`param_sets`) из первого ключевого кадра, ничего не декодируется и не перекодируется. Кадры доходят до браузера ровно такими, какими их отдала камера. `fmp4.from_samples`, который собирает тот же файл целиком в памяти, экспорт больше не зовёт; урок 24 разбирает устройство файла на нём, потому что там оно видно целиком. Почему фрагментированный и как устроены коробки — урок 24.

```python
        except (OSError, ValueError) as e:              # the caller went away, or a frame would not convert
            if not sent["head"]:
                raise
            broken = str(e)
            log.warning("an export of camera %s stopped after %d bytes: %s", cid, sent["bytes"], e)
        late = sorted(set(unreachable[said:]))
        if late:
            log.warning("an export of camera %s was cut: %s did not answer after the first byte", cid, ",".join(late))
        note_read(handler, f"rec/{','.join(units)}/{t0:.0f}-{t1:.0f}",
                  {"status": 200, "bytes": sent["bytes"], "whole": broken is None,
                   **({"sha256": sent["sha"].hexdigest()} if broken is None else {"broken": broken}),
                   **({"unreachable": ",".join(late)} if late else {})})
        return ()
```

`TimeoutError` от предела по темпу — подкласс `OSError`, поэтому медленный клиент кончается так же, как ушедший: `broken` в строке журнала, без суммы.

`return ()` — вторая форма протокола `extra`: ответ уже отправлен, платформа ничего не дописывает.

**Кто читал архив.** Видео уходит через эту дверь, и раньше об этом не оставалось ничего (ревью платформы, блокер 1 — та его часть, которой не нужен вход по паролю; обратная связь BI). `note_read` пишет событие `archive.read` в журнал консоли — `audit/console/…`, рядом с «кто удалил» и «кто поставил метку», — и строку в лог: кто, какой интервал, с какого адреса. Записи в имени — все, из которых собран экспорт (`rec/7,7-cloud/…`), а не первая: экспорт без `rec` берёт все записи камеры.

**Что ушло, а не что спросили.** Строка пишется после ответа и говорит статус, число байт и sha256 отданного (обратная связь BU). Тогда на вопрос «этот ли файл вы выдали» отвечает журнал: у кого файл, тот считает сумму и сравнивает. Сумма есть у целого экспорта; оборванный пишется с `broken` и без суммы — сумма недоставленного файла ничего не подтверждает.

**Раз в минуту.** Плеер просит один и тот же кусок несколько раз. Один и тот же интервал тем же человеком отмечается раз в минуту (`READ_NOTE_EVERY = 60.0`), иначе журнал заполнился бы повторами. Склеиваются только куски плеера: целая выгрузка — строка всегда (четвёртое ревью), и оборванная от `READ_NOTE_BYTES = 1 << 20` (1 МиБ) — тоже. Раньше две выгрузки одного интервала, оборванные после 3,6 МБ, давали одну строку, и вторая копия почти всех тех минут уходила без следа (пятое ревью, остаток Ч-m5, воспроизведено запуском). Тест: `test_slot_and_read.py::test_every_download_cut_off_after_real_footage_is_a_line_of_its_own` — две оборванные выгрузки больше мегабайта дают две строки, каждая со своим числом байт.

«Кто» — заголовок `X-User`, то есть имя, которое назвал вызывающий. Аутентификации в курсе нет, и журнал не делает вид, что она есть; когда появится, писать будет туда же.

Тесты:

- `test_slot_and_read.py::test_archive_read_says_what_left_and_the_digest_of_what_left` — экспорт начинается с `ftyp`, тот же интервал даёт тот же файл, `anna` дважды за минуту — одна строка, `boris` через минуту — вторая строка с тем же sha256;
- `test_review_remainder.py::test_who_read_the_archive_is_an_event_and_once_a_minute` — три чтения одной минуты дают одну строку `("anna", "rec/7/…", "7", digest)`, через минуту строка пишется снова;
- `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path` — `400` на перевёрнутый интервал и на интервал длиннее часа, `404` там, где ничего не записано;
- `test_slot_and_read.py::test_an_export_takes_each_moment_from_the_epoch_that_owns_it_whichever_door_holds_it` — минуты двух эпох в двух томах: каждая берётся у двери своего владельца, а `X-Archive-Unreachable` нет, когда ответили все.

## Шаг 7 — Дверь в живое видео

```python
class LiveFront:
    """The console's side of live video: the WHEP door. `POST /whep/<cam>`
    creates the fan-out unit `live/streams/<cam>` if nobody is watching yet
    (the console's token may write the operator's rows of the subsystem it
    fronts), finds which gateway the live controller placed it on, and
    proxies the offer there. Nothing here touches a worker, and the console
    never carries media: the answer names the gateway, and the browser's
    RTP goes gateway → browser from then on."""
```

**Единицу вещания создаёт первый зритель.** Живое вещание — подсистема (урок 13), и её единица появляется не по настройке, а по спросу. Первый зритель нажал «Live» — появилась строка `live/streams/<cam>`; последний ушёл — шлюз её удалит. Это третий способ появления единицы в курсе: камеру создаёт оператор, запись — оператор кнопкой, вещание — первый зритель.

**Консоль не несёт медиа.** Через неё проходит только установление сессии. Пятьдесят зрителей, чей RTP шёл бы через консоль, сделали бы её узким местом: это один процесс на сервер, который не размещается по ёмкости зрителей.

```python
    def where(self, cam: str) -> tuple[str | None, str | None]:
        pl = self.live.placement(cam)
        if not pl:
            return None, None
        hb = self.gateways().get(pl.worker)
        return pl.worker, (hb.extra.get("url") if hb else None)
```

Два шага, и оба могут не сработать. Размещения нет — контроллер вещания ещё не прошёл. Heartbeat'а нет — шлюз размещён, но ещё не поднялся. Оба состояния значат «подождите», а не «сломалось».

`gateways()` намеренно берёт и устаревшие heartbeat'ы. Шлюз, который замолчал, всё ещё держит размещение. Отфильтруй его здесь — и ответ станет «никакой шлюз не держит вещание», а правда в том, что шлюз лежит.

```python
    def offer(self, cam: str, sdp: str, labels: list[str], token: str | None = None):
        if self.ctl.camera(cam) is None:
            return 404, {"error": f"no camera {cam}", "detail": f"no camera {cam}"}
        if self.live.unit(cam) is None:
            try:
                self.live.create({"cam": str(cam), "labels": labels})
            except Refused as e:
                if "exists" not in str(e):
                    return 400, {"error": str(e), "detail": str(e)}
```

Камеры нет — 404 до всего остального: запрос несуществующей камеры не должен создавать строку вещания.

**Гонка обработана проглатыванием.** Два зрителя нажали «Live» одновременно, оба зовут `create`. Один выигрывает CAS, второй получает `Refused("exists")` — и это нормальный исход: единица есть, чего и добивались. Проверка по подстроке груба; отдельный класс исключения потребовал бы правки платформы ради одного случая. Любой другой `Refused` — настоящая ошибка, и он возвращается как 400.

```python
        g, url = self.where(cam)
        if not g or not url:
            return 503, {"error": "no gateway holds this stream yet — retry", "detail": "placed on the live controller's next pass", "retry_after": 2}
```

**`503` с объяснением.** Не 500 (ничего не сломано), не 404 (единица есть), не 202 (браузер не умеет по нему ждать). Сообщение говорит, что произойдёт, а `retry_after: 2` — сколько ждать. Страница повторяет до восьми раз и пишет «live: waiting for a gateway…». Ожидание размещения — штатное состояние распределённой системы; ответ ошибкой заставил бы нажимать «Live» дважды.

```python
        req = urllib.request.Request(f"{url}/whep/{cam}", data=sdp.encode(), method="POST",
                                     headers={"Content-Type": "application/sdp", **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data, status, loc = r.read(), r.status, r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace").strip()
            if e.code == 404:
                return 503, {"error": f"the fan-out is not up on {g} yet — retry",
                             "detail": f"placed on {g}; it subscribes on its next pass", "retry_after": 2}
            return e.code, {"error": f"gateway {g} said {e.code}", "detail": body}
        except OSError:
            return 503, {"error": f"gateway {g} is not answering — unavailable, not lost", "detail": g}
```

**Токен зрителя идёт дальше.** Шлюз проверяет его сам (`LiveWorker.handler`): консоль — не единственный, кто может достучаться до этой двери.

**404 шлюза не доезжает до браузера.** Между размещением и проходом шлюза лежит окно до двух секунд, и первое нажатие Live попадает в него всегда. Шлюз жив и честно отвечает 404: подписки у него ещё нет (урок 13). А страница повторяет только на 503. Переданный как есть, этот 404 обрывал бы попытку на первом круге. Поэтому он превращается в 503, а собственное слово шлюза остаётся в `detail`.

**Два вида отказа.** `HTTPError` — шлюз ответил отказом, и его код передаётся как есть. `OSError` — шлюз не ответил, и текст говорит: *недоступен, не потерян*. Консоль не удаляет строку вещания. Иначе зритель, повторивший через секунду, создал бы новую единицу, контроллер разместил бы её заново, и вместо паузы вышла бы перетасовка.

```python
        sid = loc.rsplit("/", 1)[-1]
        return status, data, [("Content-Type", "application/sdp"), ("Location", f"/whep/session/{sid}?gateway={g}")]
```

**Переписывание `Location`.** Браузер не должен знать адресов шлюзов: они внутренние, и их состав меняется. `?gateway=<g>` — состояние, вынесенное в URL. Консоль не помнит, какая сессия на каком шлюзе; это знает адрес, который держит браузер. Перезапустили консоль — сессии живы, потому что помнить было нечего.

**Трубку кладёт тот, кто её взял.** `DELETE /whep/session/<id>` ворота проверяли как маршрут единицы — единицей выходило `session`, и зритель с правом на одну камеру не мог положить трубку. Теперь `/whep/session/` не называет единицу (`NO_UNIT`), а консоль помнит сессии, которые выдала (`id → кто, камера, шлюз`): чужая — 403 и `access.denied`, неизвестная — 404, а шлюз берётся из записи, не из `?gateway=` (третье ревью). Тест: `test_lesson8_live.py::test_a_viewer_granted_one_camera_hangs_up_its_own_session_and_nobody_elses`.

**Сессию, которой консоль не помнит, она ищет в журнале — окнами, с памятью о промахах и с пределом на звонящего.** Память консоли — последние `SESSIONS_KEPT` сессий процесса; сессию, выданную до перезапуска, консоль ищет в строках `live.view` за `SESSION_LOOKBACK` (сутки) (четвёртое ревью). Но любой id запускал запрос к журналам всех серверов за сутки, каждый раз, а при числе просмотров за сутки больше `MAX_LIMIT` старая сессия уже не находилась — 404 (пятое ревью, minor, воспроизведено запуском). Теперь `session_of` читает сутки окнами от новых к старым, пока не найдёт сессию или не кончатся сутки. Ненайденный id запоминается на `SESSION_MISS_TTL = 60.0` секунд, и тот же неверный id не спрашивает никого. А у каждого звонящего `SESSION_MISSES = 10` поисков в журнале в минуту. Дешёвым один поиск сделал бы фильтр по `session` в самом индексе событий; сейчас индекс фильтрует по виду и подсистеме, остальное читает консоль.

**Найденное тоже помнится, и считается каждый поиск.** Запоминались и считались только промахи. Сессия, которая **есть** в журнале, но чужая, находилась, получала 403 — и на следующем запросе искалась снова, все сутки, без предела: тридцать `DELETE` на чужую старую сессию — шестьсот окон (шестое ревью, minor, воспроизведено запуском). Теперь найденная сессия кладётся в таблицу консоли, и следующий запрос находит её там без журнала; а бюджет звонящего тратится **до** поиска, чем бы тот ни кончился. Сверх бюджета ответ — 429 с `Retry-After: 60`, а не «нет такой сессии»: журнал не спрашивали. Тест: `test_lesson8_live.py::test_a_hang_up_of_an_unknown_session_reads_the_whole_day_once_and_then_asks_nobody`.

`hangup` — обратный путь: имя шлюза из параметра, адрес из heartbeat'а, `DELETE` туда. Без него шлюз держал бы соединение до таймаута, и счётчик зрителей, по которому считается его ёмкость, врал бы.

**Кто смотрел — строка в журнале.** Чтение архива пишется с шага 6; просмотр вживую не писался, а ради него аутентификация и делается (обратная связь CL). Консоль пишет `live.view` — кто (`X-User`), камера, сессия, шлюз, откуда, — когда шлюз ответил на предложение, и `live.view.ended`, когда зритель ушёл через `hangup`. Зритель, закрывший вкладку без `DELETE`, строки конца не оставляет: о нём знает шлюз, не консоль. Тест — `test_lesson8_live.py::test_who_watched_a_camera_live_is_a_line_in_the_journal`.

## Шаг 8 — Дерево монтирования

```python
def make_console(ctl: VmsController, archive_root: str | None, wall=None, live_ctl: SpecController | None = None,
                 mounts: dict[str, SpecController] | None = None, index=None, media: bool | None = None) -> Mount:
    live = LiveFront(ctl, live_ctl) if live_ctl is not None else None
    index = index or MergedIndex(ctl.objects, wall=wall or time.time)   # no database here: the resource process's, asked over HTTP
    rec_ctl = (mounts or {}).get("rec")                                  # the console fronts it anyway: the page's Record toggle
    media = archive_root is not None if media is None else media         # footage to show: the recorders' doors
    root = SpecConsole(ctl, marks_root=archive_root, wall=wall,
                       extra=vms_routes(media, live, ctl, rec_ctl), media=media, index=index,
                       metrics_extra=vms_metrics(ctl))
    m = Mount(root)
```

**VMS на корне**, остальные подсистемы — путями. Оператор открывает `/` и видит камеры; `/rec/`, `/det/`, `/live/` — та же страница над другими спецификациями.

`archive_root` — теперь только корень дерева ресурса, куда пишутся отметки оператора и журнал консоли. Видео там нет. Консоль на сервере с ресурсом показывает видео; консоль без ресурса (тест идемпотентности) — нет, если не сказано иначе параметром `media`.

`media` попадает в `/spec` как `media: true`. Страница по нему рисует таймлайн и плеер или не рисует. Одно поле в описании решает, как выглядит интерфейс.

`index` — один `MergedIndex` на все монтирования. У консоли нет своего индекса событий: она спрашивает ресурсы по HTTP и сливает ответы (урок 13 М10A). События камеры, детекторов и отметки приходят одним запросом.

`root.extra.journal = root.journal` (в `wire_vms`, ниже) — куда `note_read` пишет `archive.read`. Журнал один на процесс: монтирования получают тот же (`con.journal = root.journal`), потому что «кто удалил запись 7» стоит рядом с «кто удалил камеру 7».

Ворота доступа (урок 15 М10A) узнают маршруты VMS — в `wire_vms`, одной функции на всякую сборку консоли VMS:

```python
    root.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/backfill",)
    root.UNIT_ROUTES = SpecConsole.UNIT_ROUTES + ("timeline", "export", "whep")
    root.NO_UNIT = ("/whep/session/",)                                   # a live session is not a camera: its route checks it
    root.VIEW_POSTS = ("/whep/",)
    # A camera's `source` moved to another channel or device reaches every camera of both devices (`source_cams`);
    # their labels are read from their own rows, as a mount reads a camera's.
    # …and, moved to another device, every camera of every scenario that commands it (the eighth pass).
    controllers = {name: con.ctl for name, con in m.mounts.items()}
    auto = controllers.get("auto")
    root.moved_cams = source_cams(ctl, (auto.units, scenario_cams(auto.vars, controllers, ctl)) if auto is not None else None)
    # …and a command to a device reaches every camera of the device (`command_cams`).
    root.body_cams = command_cams(ctl)
    root.labels_of = cam_labels
```

Таймлайн, экспорт и вещание называют камеру в пути, и право на них — право на эту камеру. Запрос на дозапись действует, поэтому нужен `edit`. `POST /whep/` ничего не меняет и проходит по праву `view`. Смена `source` камеры касается каждой камеры устройства, которое строка покидает, и устройства, на которое приходит, а смена `ref` — всего кластера (`source_cams`; М10A, урок 15, шаг 12а).

**Смена `labels` камеры, у устройства которой есть другие камеры, — право на каждую из них** (дополнение продуктовой команды к десятому ревью; minor ревью про DQ). Каналы одного устройства переезжают вместе (`ensure_reach`, `group_by`). Новые метки одной камеры двигали на другой держатель весь регистратор, а спрашивалось право на одну эту камеру. Теперь `source_cams` добавляет все камеры устройства, когда меняются метки; камера, которая у своего устройства одна, ничего сверх прежнего не спрашивает.

**В адресе источника нет `#`, `?` у `driverpack://` и логина нигде** (то же дополнение, воспроизведено запуском). `urlsplit` останавливается на `#`: у `driverpack://acme/cam7#@10.0.0.50/ch/2` права спрашивались у устройства `acme/cam7` — ничьего, хватало `admin` на свою камеру-файл, — а драйвер, читающий дальше `#`, открыл бы регистратор. То же с `?` у `driverpack://`. Логин в пути (`driverpack://acme/admin:pw@10.0.0.50/…`) проходил проверку, которая смотрела только `netloc`, — пароль уходил в снимок. Теперь `SubsystemSpec.refuse` отказывает в поле-адресе в `#` и в логине — в `netloc` и в пути (имя файла `driverpack://file/…` может держать `@`: это имя), а `config.source_refusal` — в `?` у `driverpack://` (кроме того же файла). Отказ пароля не повторяет: с тринадцатого ревью `source_refusal` не цитирует адрес вовсе («the port of the source is not a port…») — источник вызывающий набрал сам, а скрытие через `config.shown_source` не видело хоста в пути, и `driverpack://acme/admin:Hunter2/ch/1` возвращался в словах отказа с паролем на месте порта; в ошибке `gstvms.uri.resolve` адрес скрыт (`hide_in_url`). Курс открывает устройство по ключу `device_of`, тому же, по которому спрашиваются права, поэтому строки, записанные раньше, читаются одинаково везде. Тест: `test_console_gate.py::test_a_fragment_or_a_login_in_a_source_names_no_other_device_and_a_labels_change_asks_for_the_whole_device`.

**Пароль в параметрах адреса не проходит и не показывается** (одиннадцатое ревью, блокер, воспроизведено запуском). `http://10.0.0.5/videostream.cgi?usr=admin&pwd=…` проходил мимо правила про логин: 201, и `GET /cameras` показывал пароль каждому, у кого есть просмотр камеры. Теперь `SubsystemSpec.refuse` отказывает адресу, у которого есть параметр с именем учётных данных (`pwd`, `password`, `token`, `auth`, `user`, `api_key`, `;password=` в пути — список в М10A, урок 9), и называет параметр, не значение. Строка, записанная раньше, нигде не говорит пароля: страница и ответы на правку — через `mask_secrets`, осколки снимка — через `hide_in_url`, ключ устройства (`device_of`: он в пульсе, на `/devices` и в логе), слова отказа (`shown_source`) и ошибка элемента (`gstvms.uri.resolve`) прячут значения таких параметров. Тест: `test_credentials.py::test_a_credential_in_an_addresss_parameters_is_refused_and_a_stored_one_is_said_nowhere`.

**И в пути, и в цепочке XMeye — тоже** (двенадцатое ревью, блокер, воспроизведено запуском). `rtsp://10.0.0.9:554/user=admin_password=…_channel=1_stream=0.sdp?real_stream` — так берут логин регистраторы XMeye/Xiongmai — проходил с 201. Пароль стоял в ответах на POST и PUT, в `GET /cameras`, в снимке для домена, в ключе устройства (пульс, `/devices`, `vms/devices/<ключ>`) и в `vms/requests/*`. Пары теперь читаются в сегментах пути и в цепочках `имя=значение_имя=значение`, сегмент-имя пароля отдаёт следующий (`/password/<значение>/`), список пополнен (`pw`, `psd`, `user_id`, `X-Amz-Signature`, `AWSAccessKeyId`) — правила в М10A, урок 9. Ключ `device_of` у `driverpack://` отбрасывает у хоста в пути логин до `@`, `;параметры` и порт, который не число. Слова отказа никогда не цитируют пароль: адрес, который `urlsplit` не читает, — это `NOT_AN_ADDRESS`, а не «Port could not be cast … as '…'» (major того же ревью: пароль с неэкранированным `?`, `#` или `/` читается как порт, и эти слова шли в ответ и в копию ответа под ключом идемпотентности, `vms/idem/*`). Копия ответа и сама проходит через `hide_in_reply`. Тесты: `test_credentials.py::test_a_login_in_any_part_of_an_address_is_refused_and_a_stored_one_is_said_nowhere` (43 написания: было отказано 33, теперь 43; ответ команды, её строка, страница, снимок, ключ устройства, слова отказа и ошибка элемента — без пароля), `test_credentials.py::test_a_refusal_never_quotes_a_password_and_the_idempotency_copy_keeps_none`.

**Адрес с логином внутри параметра и хост в пути с паролем вместо порта — тоже** (тринадцатое ревью, блокер и два major, воспроизведено запуском). `http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3A…%40cam%2Fs` создавал камеру: правило поля-адреса было своей копией в спеке и не звало общее `secrets.address_refusal`; теперь зовёт, а общее правило читает вложенный адрес как адрес (правила в М10A, урок 9). `driverpack://acme/admin:Hunter2%4010.0.0.5/ch/1` получал 400 с паролем в словах отказа и в копии ответа для повтора на сутки: хост `driverpack://` стоит в пути, и его порт не читал никто. Теперь он «не адрес» уже в спеке, а `source_refusal` адреса не цитирует. И строка старой сборки больше не держит пароля в ключе устройства: `device_of` говорит ключ так, как страница говорит адрес (`hide_in_url`), — `acme:hunter2/10.0.0.5` теперь `acme:***/10.0.0.5`, `acme/10.0.0.5&password=hunter2` — `acme/10.0.0.5&password=***`; ключ без учётных данных остаётся прежним, так что права и группировка каналов у обычных камер не сдвигаются. Ключ уходит в `POST /requests`, `vms/requests/*`, пульс и `vms/devices/<ключ>`. Тесты: `test_credentials.py::test_an_address_inside_a_parameter_is_an_address_and_a_camera_asks_the_platforms_one_rule`, `test_credentials.py::test_a_host_in_the_path_is_read_for_its_port_and_neither_a_refusal_nor_a_device_key_says_the_password`. Ворота закрытой консоли (в домене) в курсе пароля не цитировали и раньше — у продукта они цитировали пароль, прочитанный как порт; это теперь закреплено тестом по всем формам файла и трём вызывающим: `test_credentials.py::test_a_closed_consoles_gate_never_quotes_a_source_it_refuses`. Что остаётся открытым: поле `json` спеки (сценарий, тревоги) правило адресов не спрашивает — адрес с логином внутри него пройдёт.

**Тело, которое не объект JSON, — 400 тому, кто его прислал.** `POST /requests` и `POST /backfill` разбирали тело как есть: не JSON, список или вложенность глубже, чем читает JSON, ронял обработчик, и вызывающий не получал ответа вовсе (ответ на девятое ревью, «следующим заходом»; воспроизведено запуском). Теперь тело проверяется до того, как берётся ключ идемпотентности: 400, ничего не записано, ключ не потрачен. То же у платформенных маршрутов (`object_body`, М10A, урок 15). Тест: `test_one_bad_element.py::test_a_body_that_is_no_json_object_is_refused_on_every_write_route`.

**Команда устройству — это право на каждую камеру устройства.** `POST /requests` проверял `edit` на одну камеру, названную в `unit`, а держатель выполняет команду на **устройстве**: `perform` зовёт `dev.output(port, …)` и `dev.preset(n)`, канала нет ни там, ни там. Охранник с `edit` на камеру 1 шестнадцатиканального видеорегистратора послал `output` на порты 1–4 и `preset 5` — 202, и устройство выполнило всё, в том числе замок зоны камеры 2 (седьмое ревью, major, воспроизведено запуском). Привязаны ли выходы и пресеты к каналам где-нибудь в описании драйвера — нет: `capabilities()` говорит `rays`, `relays`, `ptz`, `presets` — числа, и это числа устройства (`config.describe`, строка `vms/devices/<устройство>`). Поэтому реле и пресет — каждой камеры устройства: ворота спрашивают `edit` на каждую, как смена `source` спрашивает `admin` на каждую (`source_cams`). Спрашивает платформа: у `SpecConsole` есть `body_cams(path, body)` — камеры, до которых действие из тела достаёт сверх названной, — и `dispatch` после чтения тела спрашивает право маршрута на каждую (`admit_body_cams`); VMS ставит туда `command_cams`. Камера, которая у своего устройства одна (камера с картой, файл), не спрашивает ничего сверх прежнего. Сценарий, который командует устройством (`vms.output`, `vms.preset`), — тот же охват через автоматику: `scenario_cams` добавляет все камеры устройства, и правка сценария требует `admin` на каждую.

**Аргумент команды — число или слово** (сверка продукта с одиннадцатым ревью: у аргумента не было размера). `port`, `state`, `pulse_ms`, `n` копировались в строку как пришли, и `state` в пять тысяч знаков доходил до драйвера. Теперь аргумент длиннее `config.COMMAND_ARG_MAX` (32 знака) — 400 у двери (`file_request`), поле названо, значение не повторено, строка не записана; держатель отказывает такой строке, если она всё же есть (урок 4). Тест: `test_group_by.py::test_the_console_files_a_command_and_refuses_the_ones_it_cannot`.

```python
def device_cams(ctl, cam) -> set:
    from .config import device_of, one_device
    row = ctl.camera(cam)
    src = str((row or {}).get("source") or "")
    if not src:
        return {str(cam)}
    same = one_device(ctl.vars)
    dev = same(device_of(src))
    return {str(cam)} | {str(r["id"]) for r in ctl.cameras() if r.get("source") and same(device_of(str(r["source"]))) == dev}


def command_cams(ctl):
    def cams(path: str, body) -> set:
        if path != "/requests" or not isinstance(body, dict) or str(body.get("action", "")) not in ("output", "preset"):
            return set()                                 # not a command to a device (`file_request` refuses the rest)
        unit = str(body.get("unit") or "")
        return device_cams(ctl, unit) if unit and ctl.camera(unit) is not None else set()
    return cams
```

Выход для объекта, где охраннику нужно нажимать одно реле регистратора, — привязка в описании устройства (`реле → канал`, `пресет → канал`), которую `device_cams` читала бы; ни один драйвер курса её пока не даёт. Чего это не делает: камера, добавленная к устройству **после** того, как сценарий записан, не спрашивается — сценарий продолжает действовать на устройство с ней, как и с `source_cams`. Тест: `test_console_gate.py::test_a_command_to_a_device_is_asked_of_every_camera_of_the_device_by_hand_and_through_a_scenario` — `output` и `preset` с `edit` на одну камеру регистратора — 403, с `edit` на обе — 202, у камеры-файла с правом на неё — 202; сценарий с `vms.output` на камеру регистратора правит и удаляет только тот, у кого `admin` на обе.

**Устройство — по одному написанию и по слову самого устройства.** «Устройство» в `device_cams` и `source_cams` было строкой адреса как есть. Тот же регистратор под другим написанием — регистр, порт по умолчанию, точка в конце имени, DNS-имя вместо IP — считался другим устройством. Пользователь с `admin` только на файловую камеру 3 ставил ей `source` `driverpack://ACME/10.0.0.50/ch/2`. PUT отвечал 200, затем `output` на порт 1 — 202. Держатель открывал канал 2 под именем камеры 3, и регистратор выполнял импульс (восьмое ревью, major, воспроизведено запуском). Так снова открылась закрытая в шестом ревью находка про `source` на канал чужой камеры. Теперь обе функции сравнивают устройства по каноническому ключу `device_of` (урок 15, шаг 1). А где держатель уже открыл устройство, они сравнивают по тому, что устройство сказало о себе (`identity`, `config.one_device`). Правило «один канал — одна камера» (`volumes.refuse_camera`) с девятого ревью сравнивает только по ключу: серийный номер не уникален, и по нему отказывали камере клона (решение владельца; урок 15). Тесты: `test_console_gate.py::test_one_device_under_another_spelling_is_one_device_to_every_right_asked_of_it` и `test_console_gate.py::test_a_dns_name_and_its_address_are_one_device_once_a_holder_has_opened_it`.

**Устройство, которое не открывал ни один держатель, — грант на кластер** (решение владельца по девятому ревью). Восьмое ревью закрыло второе имя у держателя: узнав `identity`, он отказывал имени, под которым устройство уже известно. Но в сборке курса фабрики устройств нет, `device_factory` пустой, и держатель не узнаёт `identity` никогда. Пользователь с `admin` на камеру 3 ставил ей `source` `nvr50.local/ch/2` — регистратор, который другая камера держит как `10.0.0.50`, — получал 200, и его команда жала реле регистратора: 202 (девятое ревью, major, воспроизведено запуском). Синтаксис не скажет, что `nvr50.local`, `010.000.000.050`, `１０.０.０.５０` и `10。0。0。50` — один адрес. Поэтому переезд на устройство, `identity` которого не записал ни один держатель (`Devices.known`), требует гранта на весь кластер — `"*"` в `source_cams`, в каком бы написании ни пришёл адрес:

```python
        if volumes.source_key(a) != volumes.source_key(b):
            same = one_device(ctl.vars, ctl.objects, ctl.wall)       # known: held by a live holder now (the tenth pass)
            devices = {same(device_of(s)) for s in (a, b) if s}
            out |= {str(r["id"]) for r in ctl.cameras() if r.get("source") and same(device_of(str(r["source"]))) in devices}
            if device_of(a) != device_of(b):
                if b and not same.known(device_of(b)):
                    out.add("*")                         # nobody can say which device that is: the cluster's grant
                if scenarios is not None:
                    rows, reach = scenarios
                    for row in rows():
                        if str(old.get("id")) in commanded(row):
                            out |= reach(row)
```

Как только держатель открыл устройство и сказал, что оно такое, переезд на него спрашивает `admin` на каждую камеру этого устройства — под любым ключом с той же `identity`, — как и раньше. Переезд внутри одного ключа (другой канал того же регистратора) гранта на кластер не просит. Сдвинулся ли источник и тот ли это ключ, решает ключ, а не `identity`: камера, перенесённая с одного клона на другой, переехала. Держатель сам больше ничему не отказывает и только предупреждает о совпадении серийного номера (урок 15). Тест: `test_console_gate.py::test_a_camera_is_moved_onto_a_device_nobody_has_opened_only_by_a_grant_on_the_cluster` — без фабрики устройств шесть написаний (DNS-имя, ведущие нули, полноширинные цифры, идеографическая точка, другой драйвер, `rtsp://`) — 403 тому, у кого `admin` на камеру; после того как держатель записал `identity` устройства, переезд на него — 200; администратору кластера — 200. Что остаётся открытым: камеру, которую администратор кластера сам направил на второе имя, охранник с `edit` на неё может командовать, пока ни один держатель не узнал `identity`: без неё консоль не знает, что это то же устройство.

**Известно — значит держится сейчас** (десятое ревью, major, воспроизведено запуском). Строки устройств не удаляются, и строка говорит, чем устройство под этим ключом **было**, когда его держали в последний раз. Старый регистратор `nvr50.local` (строка `SN-OLD`, камеры удалены) заменили, имя теперь вело на новый, а в конфигурации тот стоял по IP. Админ камеры 3 ставил ей `source` `nvr50.local/ch/2` — 200 по устаревшей строке, — держатель открывал новый регистратор, и камера 3 показывала и писала канал чужого. Теперь `Devices.known` — это строка с `identity` **и** живой держатель, который держит это устройство и в этом процессе слышал, как оно себя описало (`can` в его `devices` в heartbeat'е): то, что он слышит, он в том же проходе пишет в строку. Строка, которую сейчас никто не держит, — прошлое и снова грант на кластер; держатель замолчал дольше жизни heartbeat'а — тоже. Heartbeat'ы читаются раз за запрос, при первом `known` (`one_device(ctl.vars, ctl.objects, ctl.wall)`). Адрес, из которого устройство не прочесть вовсе (`device_of` отдаёт текст как есть), строки не имеет и тоже требует гранта на кластер — путь открытым не бывает (сосед, найденный командой продукта). Тест: `test_console_gate.py::test_a_device_row_nobody_holds_now_is_not_known_and_a_move_onto_it_asks_the_cluster`; хелпер `_opened` в тестах пишет теперь и строку, и heartbeat держателя.

**Порт или канал, которые нельзя прочесть, — 400 у двери и беда одной камеры в хранилище** (десятое ревью, major). `isdigit()` и затем `int()` на `²` или `①` в порту или канале `source`: строка камеры с `…:8²/ch/1`, сохранённая до канонического ключа, роняла держателя в `reconcile_once` и `heartbeat_once` на каждом проходе — ни статуса, ни команд по всем его камерам, — а консоль не могла создать ни одной камеры (500: «один канал — одна камера» читает все строки). Теперь разбор идёт через `doors.numeric` (`_host`, `channel_key`), а `rtsp://[…` без `]` больше не бросает из `urlsplit`: такой источник — ключ сам по себе. Новый такой `source` отвергается словами (`config.source_refusal` в `volumes.refuse_camera`; `url`-поле платформы — `Refused` вместо `ValueError`), а не принимается с 200. Тот же шаблон закрыт в `vms/auto.py` (порт реле, номер пресета сценария), в М12 `domain/scenario.py` и в `archive.parse_stream`. Тесты: `test_console_gate.py::test_a_port_or_channel_in_digits_that_are_not_ascii_stops_neither_the_holder_nor_the_console`, `::test_a_relay_port_written_in_a_digit_that_is_not_ascii_is_a_misfit_and_not_a_500`.

**Строки устройств читаются по ключу и раз за запрос.** `one_device` читал все строки `vms/devices/*` на каждую команду, переезд камеры и правку сценария. Строки устройств не удаляются, и при тысяче строк одно нажатие реле стоило 1009 чтений хранилища, а в М11 — тысячу HTTP-вызовов к Nomad (девятое ревью, minor). Теперь `one_device(vars_)` — объект `Devices`: строку устройства он читает, когда его спрашивают об этом устройстве, один раз за запрос, и больше ничего. `refuse_camera` не читает строк устройств вовсе. Тест: `test_console_gate.py::test_a_press_of_a_relay_and_a_move_of_a_camera_read_the_rows_of_their_devices_not_every_device_row` — тысяча старых строк, все чтения процесса: нажатие реле 1013 → 14, переезд камеры 2019 → 19; потолок в тесте — 40 и 50.

**Права на действие спрашиваются ещё раз, когда камера переезжает и когда команда исполняется.** Права на действие спрашиваются при записи. Сценарий с `output` на камеру — единственный канал своего устройства — записал тот, у кого `admin` на неё. Потом камеру перенесли на канал регистратора, и тот же сценарий стал жать реле **регистратора**, выбранное человеком без прав на регистратор (восьмое ревью, minor). Так же ручная команда: её `valid_until` — до `MAX_VALID`, 600 с. Закрыто с двух сторон, у каждой своё окно:

- **сценарий живёт без срока — его спрашивает переезд.** Кто переносит камеру на другое устройство, отвечает за каждый сценарий, который ею командует: `source_cams` добавляет все камеры такого сценария (`commanded`, `scenario_cams`), и нужен `admin` на каждую. Сценарий без `unit` в триггере — `"*"`, то есть грант на кластер. Перенос внутри одного устройства ничего сверх прежнего не спрашивает. Команда сценария, поданная до переезда, живёт свой `valid_for` (30 с по умолчанию) — это окно остаётся;
- **ручная команда — с устройством, на котором спросили права.** `file_request` пишет в строку `device` — ключ устройства камеры в момент подачи. Держатель исполняет команду только на нём, иначе отказывает простыми словами: «camera 3 was moved to another device after this command was given: it was not performed — give it again if it is still wanted» (`VmsWorker.requests`). Строка без `device` — сценария или консоли старой сборки — исполняется, как раньше.

Почему держатель, а не консоль: в момент исполнения у держателя есть строка камеры, а прав человека у него нет, и носить их ему незачем. Сравнить устройство из строки команды с устройством камеры сейчас — достаточно. Тесты: `test_console_gate.py::test_a_camera_moved_to_another_device_asks_for_every_camera_of_the_scenarios_that_command_it` и `test_long_poll.py::test_a_command_is_performed_only_on_the_device_it_was_given_for`.

**Одна функция для обеих сборок.** До шестого ревью всё это стояло внутри `make_console`, а консоль М11 собирается своей функцией (`cluster/console.py`) — и не получала ничего: `/timeline/<cam>` и `/export/<cam>` не были там маршрутами, называющими единицу, и в кластере, который спрашивает, кто звонит, зритель камеры 1 получал таймлайн и кадры камеры 2 за любой грант; метка записи была её меткой размещения; и то, что уходило через эту консоль, не попадало в журнал. Теперь то, что консоли VMS нужно у ворот и в журнале, — `wire_vms(m, ctl, index)`, и её зовут обе сборки. Тест: М11, `test_lesson5_controller.py::test_the_clusters_console_asks_about_the_camera_a_route_names_exactly_as_the_boxes_does`.

```python
    for name, c in (mounts or {}).items():
        con = SpecConsole(c, wall=wall, index=index,                     # every mount answers /events from the same merge
                          extra=(rec_routes(c) if name == "rec" else          # …and `rec` answers for the archives too,
                                 auto_routes(c) if name == "auto" else None),  # `auto` for its catalogue
                          metrics_extra=(rec_metrics(c) if name == "rec" else
                                         auto_metrics(c) if name == "auto" else None))
```

**Лента событий отсекает и подсистему, которой не увидел её скан, — а ту, что прочесть нельзя, называет** (двенадцатое ревью, «Вопросы», найдено запусками). `/events` помечает события отсечёнными по строкам эпох (`current_epochs`, М10A, урок 15) и собирает эти строки сканом пустого префикса. Хранилище, которое отвечает только тем, что консоли можно читать (права М11), оставляло вне скана каждую подсистему за пределами этих прав — `live/`, `det/`, — и их события стояли «текущими», какой бы ни была их эпоха. Теперь единицы такой подсистемы в этом ответе читаются по имени (`epochs_of(pairs, refused)`), а подсистема, чьи строки консоль не может читать вовсе, названа в ответе — `epochs_unread`; её события остаются такими, какими их пометил ресурс. Что остаётся открытым: в правах консоли М11 нет эпох `live/*` и `det/*`. Лента теперь об этом говорит, а сам файл прав (`cluster/rights.py`) — дело М11. Тест: `tests/test_lesson10_events.py::test_the_timeline_fences_a_subsystem_its_scan_did_not_list_and_says_one_it_may_not_read`.

**`extra` у монтирования** — тот же протокол, что на корне. У `rec` есть вопросы, которых нет у генеричной консоли. `GET /rec/volumes` отвечает списком заявленных томов и тем, кто их держит; `POST` заводит том, `DELETE` убирает **заявление**, а не видео — так и сказано в ответе. Строка тома, которая не разбирается, в списке есть — названная, с `garbled` и причиной (`served`), — и `DELETE` её удаляет, а не отвечает 404; `POST` с `quota_bytes` или `shrink_confirmed`, которые не целое число, — отказ словами (`volumes.refuse`; седьмое ревью, урок 27). `/rec/keeps` ставит, показывает и снимает удержания. Три числа рядом важнее списка:

```
served 3/4 · 0 spare        объявлено четыре, обслуживаются три, свободных процессов нет
```

`spare: 0` при `serving < wanted` — единственное состояние, которому нужен человек: том заведён, и взять его некому. Консоль это называет и пишет команду, которой оператор поднимет недостающий процесс (`scale_hint`), но сама её не выполняет. Платформа не запускает процессов — она обязана сказать число. Тома и удержания подробно разбирают [урок 10](10-recworker.md) и [урок 27](27-volumes.md).

`rec_metrics` кладёт на `/metrics` то, что регистраторы говорят о себе в heartbeat'ах: `rec_archive_failure` по виду (`away` или `wrong`), `rec_archive_depth_days`, `rec_archive_shallow` и остальное. Алерт ставится на число, а не на строку в логе.

Тест `test_lesson6_controller.py::test_the_console_over_http` проходит всю поверхность:

- идемпотентный POST даёт одну камеру;
- токен консоли не может `place`;
- `PUT {"worker": "w-9"}` — 400;
- отметка попадает в `console/<unit>/e1/…`, а не в `vms/1/`, у чьего бакета один писатель;
- страница не говорит «camera» нигде, кроме HTML-комментария;
- таймлайн камеры приходит из двери регистратора, экспорт его минуты — `video/mp4`, начинающийся с `ftyp`, а интервал без записи — 404.

## Шаг 9 — Монтирования контейнера

Шапка `deploy/console.container`:

```
# created here is placed by the controller's next pass. It holds no footage: a
# timeline and an export are asked of the recorders' archive doors. The archive
# is writable because an operator's marks are the console's own buckets,
# console/<instance>/…, on it.
```

Раньше консоль монтировала архив, чтобы отдавать сегменты, и спул — только на чтение. Теперь консоли не нужен ни один том. Сокет `obsd` в её контейнер не монтируется, и открыть том через движок она не может: видео она получает только через двери регистраторов. Права в хранилище (токен консоли не пишет размещение) и права процесса (консоль не говорит с движком) выражают одно и то же двумя механизмами.

Архив событий (`/data/platform/events`) в контейнере консоли смонтирован на запись, и причина названа в шапке: отметки оператора — собственные бакеты консоли на ресурсе; консоль в нём клиент, как и воркеры (`w2c-events`, урок 17, шаг 6). Видео там нет: собственный том сервера лежит у VMS, в `/data/vms/obsd/volume` ([урок 10](10-recworker.md)), и консоли он не смонтирован вовсе.

## Шаг 10 — Что видит сервер: метки из консоли

**Метка сервера правится там, где правятся камеры (обратная связь продукта, DQ).** Камера говорит, из какого VLAN её видно (`labels` в её строке); сервер — какие VLAN он достаёт. Вторую половину знал только узел: `LABELS`, на кластере `meta.labels` из `client.hcl`, прочитанные воркером при старте. Камера, чей сервер VLAN потерял, оставалась на нём, и никто её не записывал. Теперь это маршрут консоли — платформенный, у каждой смонтированной подсистемы свой (`/servers/…` у VMS, `/rec/servers/…` у регистратора):

```python
    # WHAT A SERVER REACHES, FROM THE CONSOLE (feedback DQ): `/servers/<server>/labels`.
    #
    #   GET     ?labels=a,b — what it reaches now and from where, and which units would move if it reached `a,b`
    #           (`would_move`; no `labels`: back to its node's) — the page asks before it writes, and warns
    #   PUT     {"labels": ["vlan:cctv-a", …]} — the administrator's labels; [] reaches nothing. A server nobody has
    #           announced (`servers_known`), a name that is not a host's, a body that is not JSON, a label that is not a
    #           string: 400, in words (the review's tenth pass)
    #   DELETE  back to the node's (`LABELS` in the server's environment)
    #
    # A path that names no unit: `admin` on the whole cluster to write (`needs`) — a server's labels decide where every
    # unit may go. Each write is a journal line with the name and the labels; the controller moves what it decides on
    # its next pass (`ensure_reach`), and the reply says which units that will be.
    def server_labels_route(self, h, method: str, path: str, q: dict) -> tuple:
```

**Права — `admin` на весь кластер.** Путь не называет камеры, поэтому ворота спрашивают грант на кластер: метки одного сервера решают, куда может встать любая камера. Админ одной камеры, грант по метке и `view` получают 403; посмотреть — `GET /servers` и что увезёт правка — может любой грант (`tests/test_server_labels.py::test_only_an_admin_of_the_whole_cluster_writes_a_servers_labels`).

**Строка, журнал, и ничего сверх.** `PUT` пишет `vms/servers/<сервер> {labels}` целиком (метка — строка из букв, цифр и `_ . : -`, до 64 знаков; иначе 400), `DELETE` строку удаляет; каждая запись — строка журнала `server.labels.set` или `server.labels.cleared` с автором. Перемещает камеры не консоль, а контроллер на своём следующем проходе (М10A, урок 11, `ensure_reach`, десять за проход); ответ `PUT` называет, какие камеры это будут (`will_move`).

**Плохой запрос — 400 словами, а не обрыв, фантом или путь к файлу** (десятое ревью, minor). Тело не JSON роняло обработчик, и соединение рвалось без ответа; `[null]`, `[true]`, `[1]` становились метками; имена `*`, `srv%2Fa`, с переводом строки и любая опечатка давали 200 и строку, которую не читает ни один сервер; имя в 300 знаков отвечало 503 с локальным путём хранилища в тексте. Теперь: тело не JSON — 400; метка не строка — 400; имя сервера — имя хоста (`SERVER_WORD`: буквы, цифры, `. - _`, до 253); `PUT` пишет строку только серверу, о котором кто-то сообщил — воркер подсистемы, ресурс или уже существующая строка (`servers_known`), иначе «no server srv-x is known here … check the name»; хранилище, не принявшее запись, — 503 без своих слов, они уходят в лог консоли. Страница проверяет ответ предпросмотра и показывает отказ, а у сервера с непрочитанной строкой пишет, что с него ничего не снимают. Тест: `tests/test_server_labels.py::test_the_labels_route_answers_a_bad_body_a_bad_label_and_an_unknown_server_with_words`.

**Тело, вложенное глубже, чем читает JSON, — тоже 400, и не только здесь.** Одиннадцатое ревью, minor. `PUT /servers/<s>/labels` ловил только `ValueError`, а тело из сотен тысяч скобок бросает `RecursionError`. `POST /rec/keeps` и `POST /rec/volumes` читали тело голым `json.loads`: тело не JSON или слишком глубокое рвало соединение без ответа. Все три теперь читают тело через `object_body`, тот же, что у строк и политики: тело не JSON, слишком глубокое или список — 400 словами, ничего не записано. Сосед того же рода, найденный при обходе: предложение живого просмотра (WHEP), которое не текст (байты не UTF-8), рвало соединение и в консоли, и в самом шлюзе; теперь 400. Тест: `tests/test_one_bad_element.py::test_a_body_that_is_no_json_object_is_refused_on_keeps_volumes_and_server_labels_and_an_offer_that_is_no_text_too`.

**Ключ, которым хранилище не может назвать файл, — 413 словами на любом маршруте.** Тот же заход: запись или том с именем в 100 000 символов, сохранение для такой камеры, ключ идемпотентности из сотни `%` — каждый становился именем файла длиннее, чем позволяет диск. Ответом было 503 с локальным путём хранилища или обрыв. Файловое хранилище отказывает такому ключу при записи (`KeyTooLong`, предел `KEY_BYTES` = 246 байт имени файла; М10A, урок 2). Консоль отвечает на это 413 с пределом в тексте — в одном месте для всех маршрутов (`Mount._answered`, рядом с `do_GET`…`do_DELETE`), потому что отказ приходит до записи, и из ответа ещё ничего не ушло. Тест: `tests/test_garbled_rows.py::test_a_key_the_file_store_cannot_name_a_file_is_refused_at_the_write_in_words_and_is_no_row_at_a_read`.

**Id, который не id этой подсистемы, — 400 словами на каждом маршруте, который берёт id** (двенадцатое ревью, находка координатора). `parse_id` бросал `ValueError` из `dispatch`: `GET /where/None` рвал соединение без ответа, а `PUT` и `DELETE /cameras/x` отвечали 500 «the write failed». Теперь `SpecConsole._uid` превращает это в `Refused` — 400 с текстом вроде `'None' is not an id of vms: its ids are whole numbers` (у подсистемы с именами вместо чисел — `names`); `/where/<id>` ловит его сам и отвечает 400 с `error: "not an id"`. Обход проверил 835 запросов — пять монтирований, их семейства маршрутов и методы: ни одного обрыва и ни одного 5xx. Тест: `tests/test_console_gate.py::test_an_id_that_is_no_id_is_a_400_in_words_on_every_route_that_takes_one`.

**…и имя — один сегмент ключа** (тринадцатое ревью, minor, воспроизведено обходом ревьюера `fuzz_routes`). У подсистемы с именами вместо чисел `..` проходило `parse_id` как имя, хранилище отказывало в ключе, который из него получался (`not a key: 'rec/recordings/..'`), и `PUT`/`DELETE` на `/rec/recordings/..`, `/detjob/jobs/..`, `/auto/scenarios/..` отвечали 500 «the write failed» — 6 из 2688 запросов обхода. Теперь `_uid` проверяет имя тем же правилом, что держат пути (`doors.safe_segment`: не пусто, не `.`, не `..`, без разделителей): 400 «a name is one segment, not '.', '..' or a path». Тот же обход на новом коде — 2688 запросов, 0 пятисотых. В тест добавлены `..` и `.`.

**Пятисотые и 503 говорят, что случилось, а не где лежит диск** (тринадцатое ревью, minor; сверка продукта (c)). `detail` пятисотой и 503 записи был `str(e)` — «[Errno 13] Permission denied: '/data/platform/vars/vms/cameras/7'»: раскладка диска сервера для любого, кто умеет сделать так, чтобы запись не прошла. Теперь ответ берёт слова ошибки (`console.no_paths`: у `OSError` — его `strerror`, у остальных абсолютные пути вырезаны), а полная ошибка остаётся в логе консоли. То же у заявки команды (`vms/console.py`) и у двери объектов ресурса (М10A, урок 14; копия, которую сервер не может прочесть или сохранить, — 503 словами, а не оборванное соединение или 408 с путём). Тесты: `tests/test_resource_objects.py::test_a_write_the_store_refuses_says_why_without_the_disks_layout`, `::test_a_copy_that_cannot_be_read_or_kept_is_a_503_in_words_with_no_path`.

**`GET /servers` говорит обе правды.** У каждого сервера теперь `labels` (по чему размещают), `labels_node` (что говорят его воркеры) и `labels_source` — `console` или `node`; `labels_unread: true` — строка есть, но не прочиталась, и с сервера ничего не снимают (М10A, урок 11). Страница показывает это строкой «reaches …» в блоке сервера, с *edit* и *back to the node's*; перед записью она спрашивает `GET …/labels?labels=…` и называет в подтверждении камеры, которые переедут или встанут неразмещёнными. Тест: `tests/test_server_labels.py::test_the_page_is_told_which_cameras_an_edit_will_move`. Та же правда нужна была ещё в одном месте — проверке `?labels=` зрителя живого видео: она читала метки шлюза из heartbeat'а, теперь спрашивает `labels_of`, как размещение (`tests/test_lesson8_live.py::test_the_labels_a_viewer_may_ask_for_are_what_placement_reads_the_consoles_row_over_the_gateways_own`).

## Шаг 11 — Сервер, который не вернётся

**Оператор управляет серверами, а не воркерами** (решение владельца курса после одиннадцатого ревью). Здесь была дверь `POST /workers/<w>/retire` — «этот процесс не вернётся», — и ревью показало, во что она обходится. Цикл воркера завис, конвейеры писали, ресурс сервера отвечал; страница видела молчащий воркер с истёкшим слотом, предлагала *retire*, и после нажатия у камер 1 и 3 было два писателя. Оператор не может знать, умер процесс или завис, — а дверь спрашивала именно это. Её больше нет. Что делать со слотом, который перестал продлеваться, контроллер решает сам, по одному правилу (`slot_fate`, М10A, урок 7, шаг 7): зависший на отвечающем сервере остаётся со своими камерами — тревога `worker.hung`, — умерший отдаёт их, незнакомый серверу освобождается.

Человеку остаются два слова, оба о машине. Дренаж (М10A, урок 17) — сервер вернётся. Списание — не вернётся. Маршрут живёт на `Mount`, рядом с `/drain`: сервер несёт все подсистемы, и спросить, отвечает ли он, надо у каждой. Имена — те же, что в продукте:

```python
    # THE OPERATOR'S DOOR TO A SERVER'S END: `POST /servers/<server>/decommission {"why": "…"}`, `DELETE` to withdraw it or
    # to bring the machine back. On the Mount, as `/drain`: a machine carries every subsystem, and whether it still answers
    # is asked of each (the product's door).
    def decommission_route(self, h, method: str, path: str, user: str = "operator") -> tuple:
```

**Права — `admin` на весь кластер, как у дренажа.** Путь не называет камеры, а уедут все камеры сервера. Тело — объект JSON, иначе 400; сервер, о котором никто здесь не слышал, — 404.

**Тело просьбы читается так же, как у любой другой двери** (двенадцатое ревью, minor, воспроизведено запуском). Дверь списания читала тело голым чтением: `Content-Length: -1` держал поток 30 секунд и отвечал 503 «the store did not take it», а 20 МБ читались целиком. Теперь `POST` сначала проходит `read_body` с пределом `CONSOLE_MAX_BODY`: отрицательная длина — 400 сразу, тело больше предела — 413. Тест: `tests/test_slot_fate.py::test_the_decommission_door_reads_its_body_as_every_door_and_a_refusal_is_journalled`.

**Пока сервер отвечает, ответ — 409, и признак назван.** Три признака, каждого достаточно (`decommission_refusal` у каждой подсистемы): ресурс сервера слышали в последние 45 с; воркера этого сервера слышали в последние 45 с; воркер этого сервера продлевает слот или перестал меньше 45 с назад. Ответ словами: `srv-1 answers: its resource was heard 3 s ago — take the server out of service and switch it off first`. Ничего не пишется. Ресурс «слышали» и тогда, когда его heartbeat отсюда не виден, а строка его двери в хранилище свежая (`unreachable`, М10A, урок 7, шаг 7): `srv-1 answers: its resource said it is there 7 s ago — …` (двенадцатое ревью, major 9). Сервер, чей ресурс не слышали никогда — ни heartbeat'а, ни строки двери, — проходит с `warning`: выключен ли он, сказать нельзя, и платформа верит оператору. Отказ 409 — не только строка в логе консоли: в журнале он теперь стоит рядом со сделанными списаниями, `server.decommission_refused` с пользователем и причиной (двенадцатое ревью, minor). Тесты: `tests/test_slot_fate.py::test_a_resource_whose_door_cannot_be_reached_is_not_a_silent_server`, `tests/test_slot_fate.py::test_the_decommission_door_reads_its_body_as_every_door_and_a_refusal_is_journalled`.

**Замолчавший — 202, и дальше работают контроллеры.** Консоль пишет одну строку `platform/decommission/<server> {by, at, why}` (её пишет только консоль) и строку журнала `server.decommission_requested`. Ответ по каждой подсистеме называет воркеров сервера, единицы, которые уедут, и занятые места: освобождение слота их не отпускает, и `note` советует отозвать том, если он сгорел вместе с сервером. Каждый контроллер на следующем проходе (`apply_decommissions`) проверяет признаки заново, освобождает слоты этого сервера и пишет отметку `<sub>/decommissioned/<server> {asked_at, at, slots, units, holds}`; в журнале — `server.decommissioned`. `redistribute` увозит камеры. На этот сервер больше ничего не размещается, а процессу на нём не дают слот (`ServerDecommissioned`), пока `DELETE /servers/<server>/decommission` не вернёт его — `200`, строка журнала `server.decommission_withdrawn`; отметку контроллер убирает сам.

**Страница показывает обе вещи.** `GET /servers` говорит про каждый сервер `decommission` (просьба), `decommissioned` (отметка контроллера), `decommissionable`, `decommission_refusal` (какой признак), `decommission_warning`, `lost` (места, которые остались заняты), `resource` (`live`, `silent`, `unreachable` — пишет в хранилище, но heartbeat отсюда не виден, — или `unknown`) и `resource_heard_at`; про каждого воркера — `hung` и `hung_since`, `slot_garbled` и `slot_until` (у строки слота, которая не разбирается, — `null`), `name_conflict` — кто ещё просит его имя (решение владельца 4 октября: `{holder, holder_box, contenders: [{state, box, hostname, server, …}]}` из меток `vms/contenders/<имя>/<коробка>`, `null`, пока никто; М10A, урок 7, шаг 5). В блоке сервера — ссылка *decommission* (или почему нельзя сейчас), «decommissioned by …» с *bring back*, а у зависшего воркера — красная строка `hung: …`. Метрики: `vms_servers_decommissioned_total`, `vms_slots_released_total`, `vms_decommission_requests_standing`, `vms_workers_hung`, `vms_name_conflicts` (имён, которые просит ещё кто-то; тревога контроллера — `worker.name_conflict`, тест `test_names.py::test_a_live_holder_on_another_box_keeps_its_name_and_the_refused_process_is_seen`). Тесты: `tests/test_slot_fate.py::test_a_server_is_decommissioned_only_once_it_is_silent_and_then_never_placed_on_until_it_is_brought_back`, `…::test_a_server_whose_resource_was_never_heard_is_decommissioned_with_a_warning`, `…::test_a_hung_worker_on_a_server_that_answers_keeps_its_cameras_and_no_second_holder_is_made`.

**На `/metrics` — то, чего контроллер сделать не смог, числом** (двенадцатое ревью). Консоль читает отчёт прохода (М10A, урок 11, шаг 9) и кладёт новые поля как метрики: `vms_workers_unjudged` и `vms_units_unjudged` — слоты, о которых нельзя сказать, работает ли процесс (`wait`, `unsure`), с единицами на них, и сколько единиц так никто не пишет (блокер 5); `vms_workers_presence_unsaid` — живые воркеры, не записавшие имя рядом со своей блокировкой (блокер 3); `vms_workers_hung_moved_total` — зависшие воркеры, чьи камеры уехали по пределу, счётчиком (minor); `vms_workers_unsure_moved_total` — то же для воркеров, о которых нельзя было сказать всего (`unsure`): их камеры уезжают по тому же пределу (М10A, урок 7, шаг 7); `vms_units_left_on_leaving` — камеры, которые не удалось унести с уходящего воркера, в том числе группа, которую не берёт целиком ни один живой (блокер 7); `vms_spares_withheld{labels}` — 1 у набора меток, которому не хватает воркеров, а предложить запасной некуда (вопросы ревью; М11, урок 10). Раньше `unjudged` и `left_on_leaving` не были ничем, кроме строки лога, а то и её не было. Тесты: `tests/test_slot_fate.py::test_a_controller_started_after_a_server_died_moves_its_cameras`, `tests/test_server_labels.py::test_a_leaving_worker_hands_a_channel_group_on_whole_or_keeps_it_whole_and_says_so`, `tests/test_spares.py::test_no_offer_where_no_server_could_carry_a_spare`, `tests/test_slot_fate.py::test_an_unsure_worker_keeps_its_cameras_and_name_until_HUNG_MOVE_AFTER_then_they_move_with_an_alarm`.

## Результат

```bash
python3 -m vms console
```

```
GET  /                            → страница
GET  /spec                        → rows: cameras, media: true
GET  /cameras                     → rows + configured
GET  /timeline/7?from&to          → спаны всех записей камеры из дверей регистраторов
                                    (или {segments, unreachable, unavailable, note})
GET  /export/7?rec=7&from&to      → video/mp4, фрагментированный, каждая минута от своей эпохи;
                                    X-Archive-Unreachable: r-2, если дверь не ответила; 404, если ничего не записано
GET  /segment?cam=7&from&to       → {playback: …} — дверь воспроизведения устройства
POST /whep/7                      → 201 + SDP, Location: /whep/session/<id>?gateway=g-1
                                    (или 503 «no gateway holds this stream yet»)
GET  /whep/7                      → строка вещания, шлюз, его статус
DELETE /whep/session/<id>?gateway=g-1
GET  /rec/recordings              → записи
GET  /rec/volumes                 → тома: заявленные, кто их держит, сколько запасных
GET  /rec/keeps                   → удержания
GET  /det/units                   → детекторы
GET  /live/streams                → вещания
POST /servers/srv-c/decommission  → 202 {state: requested, subsystems: {vms: {workers, units, holds}, …}} — слоты
                                    освободят контроллеры; 409, пока сервер отвечает (признак назван)
```

Один процесс, один порт, одна страница — и все подсистемы.

## Что может пойти не так

- **Подкласс `SpecConsole` вместо `extra`.** Подсистема начнёт зависеть от внутренностей платформы.
- **Спрашивать одну дверь.** Минуты, которые лежат в другом томе, пропадут с таймлайна и из экспорта.
- **Отсекать по пометке двери.** Поток зомби в томе другого сервера будет нарисован как законная запись.
- **Ждать неответившую дверь.** Таймлайн не придёт вовсе вместо того, чтобы прийти с объяснением.
- **Рисовать молчащий том как дыру.** Оператор будет искать на карте камеры или списывать как потерянное видео, которое лежит на выключенном сервере.
- **Брать кадры у первой ответившей двери.** Минуты, которые две эпохи держат в двух томах, придут от зомби, если его дверь стоит в списке раньше.
- **Молча пропустить неответившую дверь в экспорте.** Файл с дырой выглядит как запись без дыры.
- **Экспорт без потолка длины.** Один запрос «за год» соберёт в памяти консоли год видео.
- **Пустой файл вместо 404.** Плеер покажет испорченный файл там, где записи просто нет.
- **Писать `archive.read` до ответа.** Журнал скажет, что видео ушло, когда оно не ушло, и не скажет, что именно ушло.
- **Медиа живого видео через консоль.** Один нераспределяемый процесс на пути всех зрителей.
- **Адреса шлюзов в браузере.** Внутренние адреса наружу, и смена состава шлюзов ломает открытые вкладки.
- **Сессии в памяти консоли.** Перезапуск консоли обрывает всё живое видео.
- **`404` вместо `503` при неразмещённой единице.** Пользователь нажмёт «Live» ещё раз вместо того, чтобы подождать две секунды.
- **Разные `index` у монтирований.** Каждая подсистема увидит только свои события, и таймлайн распадётся.

## Итог

- VMS добавляет к консоли видео: таймлайн камеры и экспорт интервала. Всё остальное — платформа, читающая YAML.
- Видео консоль берёт у дверей регистраторов, найденных по heartbeat'ам, — у всех, потому что запись может лежать в нескольких томах.
- Отсечение — по строке эпохи записи в хранилище: дверь знает только эпоху своего регистратора. Копия удержания `e0` не отсекается.
- Дверь, которая не ответила, и том, который никто не держит, называются в ответе: недоступно, не потеряно.
- Экспорт — интервал не длиннее часа: таймлайны всех дверей, `authoritative` над ними всеми, каждый отрезок у двери его владельца, каждый момент один раз, с ключевого кадра, в фрагментированный MP4. Неответившие двери названы в `X-Archive-Unreachable`. Экспорт идёт, пока клиент берёт не меньше `EXPORT_MIN_RATE`; клиенту HTTP/1.1 обрыв виден по отсутствию последнего куска. После ответа в журнал уходит `archive.read` с sha256 отданного.
- `/segment` отвечает только про устройство: подписанный адрес двери воспроизведения его держателя, на интервал, подрезанный по покрытию устройства и не длиннее часа; дверь отдаёт его кусками по минуте.
- Консоль не несёт живое медиа; `503` с `retry_after` — ответ на «ещё не разместили»; состояние сессии вынесено в URL.
- `Mount` даёт один процесс, один порт и одну страницу; общий `MergedIndex` и общий журнал сводят подсистемы вместе.
- Консоль не говорит с `obsd`: видео она получает только через двери регистраторов.

## Упражнения

1. Спрашивайте в `timeline` только первую дверь из `recorder_doors`. Перенесите запись на другой сервер и посмотрите на таймлайн за последний час.
2. Уберите `_rec_epoch` и оставьте пометки дверей. Повторите тест М11 `test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves` и объясните, какое утверждение упало.
3. Уберите условие `0 < epoch` из отсечения. Поставьте удержание и посмотрите, как страница нарисует его копию.
4. Ждите неответившую дверь без таймаута. Остановите один регистратор процессом `kill -STOP` и откройте таймлайн.
5. Уберите `unserved_volumes` из ответа. Выключите сервер с локальным томом и опишите, что увидит оператор и что он сделает.
6. Поставьте `EXPORT_PIECE` больше `EXPORT_MAX`, чтобы экспорт снова читал интервал одним куском. Попросите час и замерьте память консоли — потом верните минуту и замерьте снова.
7. Верните экспорту прежний путь: `/samples` у каждой двери за весь интервал, без таймлайнов и `authoritative`. Запустите `test_an_export_takes_each_moment_from_the_epoch_that_owns_it_whichever_door_holds_it` и объясните, чьи кадры консоль взяла за минуты 5–10 и почему.
8. Пишите `archive.read` до отправки. Оборвите соединение на середине и прочитайте журнал.
9. Отвечайте 404 вместо 503 при неразмещённой единице вещания. Опишите, что сделает страница из урока 16 М10A.

## Что дальше

Дверь WHEP есть, а за ней пока никого: `live/streams/<cam>` — строка в подсистеме, которой не существует.

> **Ещё одна оговорка.** Наш архив консоль читает через двери регистраторов, а архив устройства — пока только адресом его двери воспроизведения. В [уроке 15](15-the-archive-we-did-not-write.md) у консоли появляется второй путь чтения — к архиву, которого мы не писали, — и маршрутизировать она начнёт по источнику спана.

[**Урок 13**](13-live-video.md) пишет `live.subsystem.yaml`, `LiveWorker` и `webrtc.py`: подсистему, чья единица — раздача камеры, чья ёмкость измеряется в зрителях, и чьи единицы создаются спросом и уходят вместе с ним.

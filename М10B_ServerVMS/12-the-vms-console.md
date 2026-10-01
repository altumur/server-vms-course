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

> **Проверка без железа.** Весь урок. Таймлайн и экспорт идут против настоящего `obsd` (`conftest.py`: `store`, `footage`, `door` — дверь регистратора над томом и heartbeat, который её объявляет); GStreamer не нужен. Тесты: `test_lesson6_controller.py::test_the_console_over_http` (вся поверхность на настоящем порту), `test_rec_volume.py::test_a_volume_nobody_serves_is_named_on_the_timeline_and_not_drawn_as_a_hole`, `test_slot_and_read.py::test_archive_read_says_what_left_and_the_digest_of_what_left`, `test_review_remainder.py::test_who_read_the_archive_is_an_event_and_once_a_minute`, `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path`; в М11 — `clustervms/tests/test_lesson3_resources.py::test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves`.

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
def device_spans(objects, cam, ours: list[dict], t0: float, t1: float, now: float) -> list[dict]:
    found = holder_of(objects, "vms/", cam, now, field="coverage")
    if found is None:
        return []
    cov = found[2]["coverage"]
    want = (max(float(cov["from"]), t0), min(float(cov["to"]), t1))
    if want[1] <= want[0]:
        return []
    have = [(s["start"], s["end"]) for s in ours]
    return [{"start": a, "end": b, "media": None, "epoch": 0, "source": "device",
             "fenced": False, "device": True} for a, b in subtract(want, have)]
```

`subtract` — та же функция, по которой регистратор решает, что дозаписывать (урок 16). Одно правило в двух местах, поэтому картинка и работа не могут разойтись. Такой спан исчезнет первым: наш архив держит недели, карта камеры — дни.

Сыграть такой спан консоль не может: у неё нет кадров устройства. Маршрут `/segment` теперь отвечает только про устройство — адрес двери воспроизведения у воркера, который держит камеру сейчас:

```python
        if (path == "/segment" or path == "/segment/") and ctl is not None:                 # the device's own footage, through its holder
            url = device_playback(ctl.objects, q.get("cam"), con_wall())
            if url is None:
                return 503, {"detail": "nobody holds this camera right now", "error": "unheld"}
            return 200, {"playback": f"{url}?from={q.get('from', 0)}&to={q.get('to', 1e12)}"}
```

Держатель ищется в момент запроса, а не записывается в спан при рисовании. Камера, переехавшая между рисованием и щелчком, иначе дала бы 404. Подробно этот путь разбирает [урок 15](15-the-archive-we-did-not-write.md).

Файла по пути консоль не отдаёт больше никогда. Тест `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path` проверяет, что `/segment/<абсолютный путь>` — 404.

## Шаг 6 — Экспорт интервала

Спан на таймлайне говорит `media: "/export/7?rec=7"`. Страница режет спан на куски по десять минут и для каждого просит экспорт:

```javascript
function segmentURL(s, p) {
  if (s.media && s.media.startsWith('/')) return `${s.media}${s.media.includes('?') ? '&' : '?'}from=${p.from}&to=${p.to}`;
```

```javascript
const PIECE = 600;
```

Один кусок играет, следующий ставится, когда этот кончился. Непрерывное воспроизведение через MSE и всё, что браузер делает с файлом, — [урок 24](24-an-interval-in-the-browser.md).

На стороне консоли:

```python
    def export(handler, cid: str, q: dict):
        from .fmp4 import from_samples
        try:
            t0, t1 = float(q.get("from", 0)), float(q.get("to", 0))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        if t1 <= t0 or t1 - t0 > EXPORT_MAX:
            return 400, {"detail": f"an export is an interval of at most {EXPORT_MAX:.0f} s", "error": "bad range"}
```

**Интервал, и ограниченный.** `EXPORT_MAX = 3600.0`: страница просит минуты, человек — до часа. Экспорт собирается в памяти целиком, и запрос «с 1970 года» без потолка стал бы способом уронить консоль. Концы в неправильном порядке и интервал длиннее часа — 400.

```python
        units = [str(q["rec"])] if q.get("rec") else recordings_of(rec_ctl, cid)
        got = []
        for unit in units:
            for name, url, _ in (recorder_doors(ctl.objects, con_wall()) if ctl is not None else []):
                try:
                    from w2cplatform.obsd import Sample
                    got += Sample.decode_all(_door(f"{url}/samples/{unit}?from={t0}&to={t1}", 30.0))
                except (OSError, ValueError):
                    continue
```

**Кадры — от всех дверей.** По той же причине, что таймлайн: интервал записи может лежать в двух томах. Каждая дверь отдаёт свои кадры, уже выбранные по старшей эпохе внутри своего тома (`Archive.samples`, урок 8). Таймаут здесь 30 секунд, а не 5: дверь читает кадры, а не индекс.

```python
        frames, end = [], None
        for smp in sorted(got, key=lambda s: s.begin):
            if end is not None and smp.begin < end:
                continue                                 # this moment came from another door already
            if not frames and not smp.key:
                continue
            frames.append(smp)
            end = smp.end
        if not frames:
            return 404, {"detail": f"no footage of camera {cid} in that interval", "error": "nothing recorded"}
```

**Каждый момент — один раз.** Кадры всех дверей сортируются по времени. Кадр, который начинается раньше конца уже взятого, пропускается: этот момент уже пришёл.

**Файл начинается с ключевого кадра.** Иначе плеер ничего не покажет до первого ключевого.

**Пусто — 404, а не пустой файл.** Пустой MP4 плеер покажет как испорченный файл. 404 с `nothing recorded` говорит, что записи в этом интервале нет.

```python
        try:
            data = from_samples(frames)
        except ValueError as e:
            return 415, {"detail": str(e), "error": "not playable"}
```

`fmp4.from_samples` превращает кадры в фрагментированный MP4: фрагмент на группу кадров, параметры потока из первого ключевого кадра, ничего не декодируется и не перекодируется. Кадры доходят до браузера ровно такими, какими их отдала камера. Почему фрагментированный и как устроены коробки — урок 24.

```python
        handler.send_response(200)
        handler.send_header("Content-Type", "video/mp4")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        note_read(handler, f"rec/{units[0]}/{t0:.0f}-{t1:.0f}", {"status": 200, "bytes": len(data), "whole": True, "data": data})
        return ()
```

`return ()` — вторая форма протокола `extra`: ответ уже отправлен, платформа ничего не дописывает.

**Кто читал архив.** Видео уходит через эту дверь, и раньше об этом не оставалось ничего (ревью платформы, блокер 1 — та его часть, которой не нужен вход по паролю; обратная связь BI). `note_read` пишет событие `archive.read` в журнал консоли — `audit/console/…`, рядом с «кто удалил» и «кто поставил метку», — и строку в лог: кто, какой интервал, с какого адреса.

**Что ушло, а не что спросили.** Строка пишется после ответа и говорит статус, число байт и sha256 отданного (обратная связь BU). Тогда на вопрос «этот ли файл вы выдали» отвечает журнал: у кого файл, тот считает сумму и сравнивает. Экспорт всегда уходит целиком, поэтому сумма у него есть всегда.

**Раз в минуту.** Плеер просит один и тот же кусок несколько раз. Один и тот же интервал тем же человеком отмечается раз в минуту (`READ_NOTE_EVERY = 60.0`), иначе журнал заполнился бы повторами.

«Кто» — заголовок `X-User`, то есть имя, которое назвал вызывающий. Аутентификации в курсе нет, и журнал не делает вид, что она есть; когда появится, писать будет туда же.

Тесты:

- `test_slot_and_read.py::test_archive_read_says_what_left_and_the_digest_of_what_left` — экспорт начинается с `ftyp`, тот же интервал даёт тот же файл, `anna` дважды за минуту — одна строка, `boris` через минуту — вторая строка с тем же sha256;
- `test_review_remainder.py::test_who_read_the_archive_is_an_event_and_once_a_minute` — три чтения одной минуты дают одну строку `("anna", "rec/7/…", "7", digest)`, через минуту строка пишется снова;
- `test_doors.py::test_the_consoles_export_asks_for_an_interval_and_never_a_path` — `400` на перевёрнутый интервал и на интервал длиннее часа, `404` там, где ничего не записано.

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

`hangup` — обратный путь: имя шлюза из параметра, адрес из heartbeat'а, `DELETE` туда. Без него шлюз держал бы соединение до таймаута, и счётчик зрителей, по которому считается его ёмкость, врал бы.

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
    root.extra.journal = root.journal    # where `archive.read` goes: the journal, `audit/console/…`
```

**VMS на корне**, остальные подсистемы — путями. Оператор открывает `/` и видит камеры; `/rec/`, `/det/`, `/live/` — та же страница над другими спецификациями.

`archive_root` — теперь только корень дерева ресурса, куда пишутся отметки оператора и журнал консоли. Видео там нет. Консоль на сервере с ресурсом показывает видео; консоль без ресурса (тест идемпотентности) — нет, если не сказано иначе параметром `media`.

`media` попадает в `/spec` как `media: true`. Страница по нему рисует таймлайн и плеер или не рисует. Одно поле в описании решает, как выглядит интерфейс.

`index` — один `MergedIndex` на все монтирования. У консоли нет своего индекса событий: она спрашивает ресурсы по HTTP и сливает ответы (урок 13 М10A). События камеры, детекторов и отметки приходят одним запросом.

`root.extra.journal = root.journal` — куда `note_read` пишет `archive.read`. Журнал один на процесс: монтирования получают тот же (`con.journal = root.journal`), потому что «кто удалил запись 7» стоит рядом с «кто удалил камеру 7».

Ворота доступа (урок 15 М10A) узнают маршруты VMS:

```python
    root.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/backfill",)
    root.UNIT_ROUTES = SpecConsole.UNIT_ROUTES + ("timeline", "export", "whep")
    root.VIEW_POSTS = ("/whep/",)
```

Таймлайн, экспорт и вещание называют камеру в пути, и право на них — право на эту камеру. Запрос на дозапись действует, поэтому нужен `edit`. `POST /whep/` ничего не меняет и проходит по праву `view`.

```python
    for name, c in (mounts or {}).items():
        con = SpecConsole(c, wall=wall, index=index,                     # every mount answers /events from the same merge
                          extra=(rec_routes(c) if name == "rec" else          # …and `rec` answers for the archives too,
                                 auto_routes(c) if name == "auto" else None),  # `auto` for its catalogue
                          metrics_extra=(rec_metrics(c) if name == "rec" else
                                         auto_metrics(c) if name == "auto" else None))
```

**`extra` у монтирования** — тот же протокол, что на корне. У `rec` есть вопросы, которых нет у генеричной консоли. `GET /rec/volumes` отвечает списком заявленных томов и тем, кто их держит; `POST` заводит том, `DELETE` убирает **заявление**, а не видео — так и сказано в ответе. `/rec/keeps` ставит, показывает и снимает удержания. Три числа рядом важнее списка:

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

`/data/archive` в контейнере консоли смонтирован на запись, и причина названа в шапке: отметки оператора — собственные бакеты консоли на ресурсе. Видео там нет: собственный том сервера лежит рядом, в `/data/volume` ([урок 10](10-recworker.md)), и консоли он не смонтирован вовсе.

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
GET  /export/7?rec=7&from&to      → video/mp4, фрагментированный; 404, если ничего не записано
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
```

Один процесс, один порт, одна страница — и все подсистемы.

## Что может пойти не так

- **Подкласс `SpecConsole` вместо `extra`.** Подсистема начнёт зависеть от внутренностей платформы.
- **Спрашивать одну дверь.** Минуты, которые лежат в другом томе, пропадут с таймлайна и из экспорта.
- **Отсекать по пометке двери.** Поток зомби в томе другого сервера будет нарисован как законная запись.
- **Ждать неответившую дверь.** Таймлайн не придёт вовсе вместо того, чтобы прийти с объяснением.
- **Рисовать молчащий том как дыру.** Оператор будет искать на карте камеры или списывать как потерянное видео, которое лежит на выключенном сервере.
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
- Экспорт — интервал не длиннее часа, кадры от всех дверей, каждый момент один раз, с ключевого кадра, в фрагментированный MP4. После ответа в журнал уходит `archive.read` с sha256 отданного.
- `/segment` отвечает только про устройство: адрес двери воспроизведения его держателя.
- Консоль не несёт живое медиа; `503` с `retry_after` — ответ на «ещё не разместили»; состояние сессии вынесено в URL.
- `Mount` даёт один процесс, один порт и одну страницу; общий `MergedIndex` и общий журнал сводят подсистемы вместе.
- Консоль не говорит с `obsd`: видео она получает только через двери регистраторов.

## Упражнения

1. Спрашивайте в `timeline` только первую дверь из `recorder_doors`. Перенесите запись на другой сервер и посмотрите на таймлайн за последний час.
2. Уберите `_rec_epoch` и оставьте пометки дверей. Повторите тест М11 `test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves` и объясните, какое утверждение упало.
3. Уберите условие `0 < epoch` из отсечения. Поставьте удержание и посмотрите, как страница нарисует его копию.
4. Ждите неответившую дверь без таймаута. Остановите один регистратор процессом `kill -STOP` и откройте таймлайн.
5. Уберите `unserved_volumes` из ответа. Выключите сервер с локальным томом и опишите, что увидит оператор и что он сделает.
6. Снимите потолок `EXPORT_MAX`. Попросите экспорт за сутки и замерьте память консоли.
7. Сравните экспорт минут, которые две двери отдают под разными эпохами. Чьи кадры возьмёт консоль и почему? Сравните с тем, что сделал бы `authoritative` внутри одного тома.
8. Пишите `archive.read` до отправки. Оборвите соединение на середине и прочитайте журнал.
9. Отвечайте 404 вместо 503 при неразмещённой единице вещания. Опишите, что сделает страница из урока 16 М10A.

## Что дальше

Дверь WHEP есть, а за ней пока никого: `live/streams/<cam>` — строка в подсистеме, которой не существует.

> **Ещё одна оговорка.** Наш архив консоль читает через двери регистраторов, а архив устройства — пока только адресом его двери воспроизведения. В [уроке 15](15-the-archive-we-did-not-write.md) у консоли появляется второй путь чтения — к архиву, которого мы не писали, — и маршрутизировать она начнёт по источнику спана.

[**Урок 13**](13-live-video.md) пишет `live.subsystem.yaml`, `LiveWorker` и `webrtc.py`: подсистему, чья единица — раздача камеры, чья ёмкость измеряется в зрителях, и чьи единицы создаются спросом и уходят вместе с ним.

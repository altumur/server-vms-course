# Урок 27 — Тома: local, network, edge, backup, incidents

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/volumes.py` целиком — пять видов тома, `on_a_box` и `any_box`, `refuse`, `write`, `servable`, `suggest`, `served`, `admit_recording` и `rank_near_recording`; в `vms/recworker.py` — то, что регистратор делает с томом: `volume_pass`, `_write_into`, `_place_kind`, `leave_volume`, `after_stop` и ветку томов в `lease_pass`; в `vms/archive.py` — `volume_params`.
**Время:** ~90 минут.

## Зачем этот урок

Тома появлялись в курсе по частям. Урок 10 ввёл строку тома и захват. Урок 26 добавил резервные виды. Урок 18 — кольцо и его глубину. М11 — том, который никто не обслуживает, потому что его сервер лежит. Каждый урок говорил о своём, и ответа на простой вопрос «что меняет вид тома» не было ни в одном.

Этот урок собирает ответ в одном месте. Вид тома решает пять вещей, и все пять — в коде, а не в договорённостях:

| Вопрос | Где ответ |
|---|---|
| где том: на одном сервере или по адресу | `server` в строке, `on_a_box` / `any_box` |
| кто может его обслуживать | `servable` |
| что делать, когда хранилище конфигурации молчит | `lease_pass` |
| что можно на него поставить | `admit_recording` |
| как читать отказ при открытии | `_write_into` |

Остальное у видов общее: строка-заявление, захват по CAS, квота как размер кольца, открытие через `obsd`. Кроме одного вида: `edge`, карта камеры, — место, но не том движка. Её открывает и пишет регистратор самой камеры, обычными файлами, а квота у неё — бюджет карты (урок 26, шаг 10; как в продукте).

> **Проверка без железа.** Всё в этом уроке идёт против настоящего `obsd`. Набор тестов поднимает демон сам (`tests/conftest.py`, `ObsdDaemon`), а без бинарника тест падает с подсказкой: собрать `ObjectStorage/standalone-build/build.sh` и указать `OBSD_BIN`. GStreamer не нужен: кадры пишет `FakeActuator`. Чего тесты не покрывают: настоящий S3. Сетевой том в них — каталог, «который `obsd` открывает как бакет» (`_net` в `tests/test_volumes.py`).

## Что нужно знать заранее

- **Уроки 6–8** — движок: том, блок, последовательность, поток; читатель видит только закрытые блоки; кольцо.
- **Урок 10** — регистратор, `place_by: volume`, `home` как предпочтение.
- **Урок 26** — резервная запись, `when: offline`, дверь архива.
- **М10A, урок 7** — слот и захват места (`claim_hold`, `renew_hold`, `release_hold`).
- **М10A, урок 11** — фильтры размещения и именованные двери `register_admit`, `register_near_rank`.
- **М10A, урок 18** — секреты: суффикс `_secret` и запечатывание.

## Чему вы научитесь

1. Отличать заявление о томе от факта, что его кто-то обслуживает.
2. Говорить, где том и кто вправе его обслуживать, по одному полю строки.
3. Объяснять, почему локальный диск при молчащем хранилище остаётся за регистратором, а сетевой том отпускается.
4. Читать квоту как размер кольца, а не как потолок поверх свободного места.
5. Открывать том через `obsd` так, чтобы ключ не попал ни в один адрес.
6. Различать «неверно», «недоступно» и «занято» — и объяснять, почему вид тома меняет приговор.
7. Делать `home` фильтром для резервного тома и держать том происшествий вне записи.

---

## Шаг 1 — Заявление и факт

```python
SUB = "rec"
TABLE = "volumes"
KINDS = ("local", "network", "backup", "edge", "incidents")
FIELDS = ("kind", "url", "server", "quota_bytes", "access_key", "access_secret", "enabled")
```

Том — это две записи, и держать их врозь и есть решение:

```
rec/volumes/<имя>    ЗАЯВЛЕНИЕ: kind, url, server, quota_bytes, access_key, access_secret, enabled   ← пишет консоль
rec/holds/<имя>      ФАКТ: кто пишет туда сейчас                                                      ← пишет регистратор
```

Строку пишут на консоли. Кто именно обслуживает том в эту секунду — факт о кластере, и консоль его знать не может. Поэтому факт — отдельная запись того же вида, что слот воркера: держатель, срок, флаг «отпущен», поколение, CAS (М10A, урок 7). Заголовок `volumes.py` говорит так:

> *Nobody assigns, nobody starts a process: the controller places recordings on the places that exist, and a place exists because somebody is holding it.*

Отсюда первое следствие для оператора. Удалить строку — не удалить видео. Консоль отвечает на `DELETE /volumes/<имя>` словами *the footage already written is untouched*, а регистратор, державший том, на следующем проходе останавливает записи этого тома и берёт другой (`test_volumes.py::test_the_console_declares_a_volume_and_says_who_serves_it`).

То же у записи, одним этажом ниже: удалённая строка `rec/recordings/<имя>` оставляет в томах поток `<имя>/e<n>`, и читатели находят его по имени. Поэтому имя удалённой записи возвращается только её камере: надгробие хранит `cam`, и запись другой камеры под тем же именем консоль не создаёт (пятое ревью: пересозданная «1-cloud» камеры 2 отдавала кадры камеры 1; [`СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ.md`](СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ.md), тест `test_console_gate.py::test_a_deleted_recordings_name_comes_back_only_for_its_own_camera`).

## Шаг 2 — Где том и кто может его обслуживать

```python
def on_a_box(v: "Volume") -> bool:
    return v.kind in ("local", "edge") or (v.kind in ("backup", "incidents") and bool(v.server))


def any_box(v: "Volume") -> bool:
    return v.kind == "network" or (v.kind in ("backup", "incidents") and not v.server)
```

Два предиката, и каждый вид попадает ровно в один.

**`local`** — диск. Писать на него может только регистратор на его сервере, поэтому `server` обязателен.

**`edge`** — карта в камере, которая сама работает на платформе. Камера и есть сервер, поэтому `server` тоже обязателен. Это единственный вид, который не открывается движком. На камере около 32 МБ памяти, движку нужно 20–25 МБ на писателя (обратная связь CB, DG; записка продукта о прошивке, §12 и §14), и продукт сделал карту буфером: каталог с файлами сегментов и бюджетом в байтах. Пишет его только регистратор камеры (`vms/card.py`, `CardRecorder`); регистратор движка карту не берёт, даже на той же коробке. Поэтому `url` карты — каталог на камере, без ключа: адрес или ключ `refuse` не примет. Движок на камере — NAS или мини-диск — был бы томом `local` или `network`, а не `edge`.

**И карта называет свою камеру.** `server` у карты — коробка, на которой работает её регистратор, и он ничего не говорит о том, чьи кадры на неё ложатся. Регистратор карты пишет кольцо своей камеры в любую запись, которую ему дали, и запись камеры 1 с `home` на карте камеры 2 получала кадры камеры 2 из бюджета камеры 2 (шестое ревью, major). Теперь у `edge` обязательное поле `cam` — id камеры в `vms/cameras` этого кластера (`Volume.cam`; `declare_card(..., cam=…)`), а у остальных видов `refuse` его не принимает: диск и бакет — ничьи. Карту, на которой уже стоят записи, нельзя объявить заново картой другой камеры: `write` отвечает, какую запись сначала перенести. Что из этого следует для записей — запись ложится на карту, только если она этой камеры, и права спрашиваются на обе камеры, — урок 26, шаг 6. Тест: `test_console_gate.py::test_a_recording_is_homed_on_a_card_only_by_whoever_may_act_on_that_cards_camera_and_only_its_own`.

**`network`** — адрес. Дотянуться может любая коробка, поэтому `server` запрещён: `refuse` отвечает *a network volume is served by whichever box takes it — leave `server` empty*.

**`backup`** и **`incidents`** — то или другое. С сервером это диск того сервера. Без сервера это адрес, как сетевой том. Комментарий объясняет, почему резервному тому это позволено: второе хранилище где-то ещё так же независимо от сервера основной записи, как второй диск.

Правила формы — в `refuse`, единственной двери, через которую строка попадает в хранилище:

```python
    if kind == "local" and not str(fields.get("server", "")):
        raise Refused("a local volume is a disk on one server: name it")
    if kind == "edge" and not str(fields.get("server", "")):
        raise Refused("an edge volume is the card in one camera: name it")
    # …and names the camera too — `cam`, its id among this cluster's cameras; `server` is the box the card's recorder
    # runs on, which says nothing of whose frames it writes (the review's sixth pass, major: a recording of camera 1
    # homed on camera 2's card was written from camera 2's ring). No other kind is a camera's.
    if kind == "edge" and not str(fields.get("cam", "") or ""):
        raise Refused("an edge volume is the card in one camera: say which — `cam`, the camera's id here; only that "
                      "camera's recordings are homed on it")
    if kind != "edge" and str(fields.get("cam", "") or ""):
        raise Refused(f"`cam` is an edge volume's — the camera whose card it is; a {kind} volume is no camera's")
    # A card is a directory on the camera, written by the camera's recorder without an engine (`vms/card.py`): an
    # address — a bucket, a share — or a key to one is something no card reader can open.
    if kind == "edge" and ("://" in str(fields.get("url", "")).replace("file://", "", 1)
                           or fields.get("access_secret") or fields.get("access_key")):
        raise Refused("an edge volume is the card in a camera — a directory on it, with no key: an address is a "
                      "local or network volume")
    if kind == "network" and str(fields.get("server", "")):
        raise Refused("a network volume is served by whichever box takes it — leave `server` empty")
```

Кто что может взять, считает `servable`:

```python
def servable(vols: list[Volume], server: str) -> list[str]:
    mine = [v.name for v in vols if v.enabled and on_a_box(v) and v.server == server]
    net = [v.name for v in vols if v.enabled and any_box(v)]
    return mine + net
```

**Порядок — часть ответа.** Сначала свои диски, потом адреса. У диска ровно один сервер, который может его обслуживать. Регистратор, который взял бы сначала сетевой том, оставил бы свой диск без писателя, и запасной на другом сервере этот диск взять не смог бы никогда. Сетевой том подождёт: его может взять любой.

Отключённый том не достаётся никому. Его выключил администратор.

Из асимметрии выходит вся арифметика запасных. Один запасной регистратор на коробку принимает один **сетевой** том на коробку: тот, кто его возьмёт, может стоять где угодно.

Тесты: `test_volumes.py::test_who_may_serve_what` (свой диск первым, коробка без дисков всё равно кандидат, отключённый ничей) и `test_backup_archive.py::test_a_backup_volume_is_a_box_or_an_address` (резервный том с сервером обслуживает только этот сервер, без сервера — любой).

## Шаг 3 — Когда не объявлено ничего

Строк может не быть вовсе. Тогда регистратор пишет в **собственный том сервера**:

```python
        self.pinned = bool(env.get("VOLUME"))
        self.pin = str(env.get("VOLUME") or "")      # …its name, which `volume` is not while the hold is another's
        self.volume_wait = ""                        # pinned, and waiting for the hold: why (`_wait_for_pin`)
        self.default_volume = str(self.server or "default")
        beside = os.path.join(os.path.dirname(os.path.abspath(events_root)), "volume")
        self.default_url = env.get("ARCHIVE_VOLUME") or f"file://{beside}"
        self.default_quota = default_quota if default_quota is not None else int(env.get("ARCHIVE_QUOTA_BYTES", "0") or 0)
        # 0: sized at its first FORMAT by the disk the DAEMON writes to (`_share_of_space`, `VOLUME_SPACE`)
```

Имя тома — имя сервера, путь — `volume` рядом с деревом событий ресурса: `/data/volume` возле `/data/archive`. Рядом, а не внутри, потому что внутри обходы ресурса приняли бы кольцо за подсистему и посчитали бы его блоки занятым местом дерева. Комментарий называет, зачем том вообще такой: это то, что значила любая коробка с одним диском до появления строк, — одно место, `home: srv-a` остаётся верным, а `place_by: volume` ведёт себя в точности как `place_by: server`.

Размер — `ARCHIVE_QUOTA_BYTES`, а без неё четыре пятых свободного места, но не больше, чем держит диск под нижней отметкой ватерлинии:

```python
    # A volume nobody declared, on a disk nobody measured: four fifths of what is free, leaving two gigabytes —
    # the product's rule (feedback BM) — and never so much that the disk ends above the watermark's low mark
    # (`space_settings`, 0.75 by default) once the ring is full. The disk is shared with the resource's events,
    # and a ring that filled it past the mark would leave the watermark short for good: nothing of the VMS's
    # answers `free` any more. At least a gigabyte, whatever the arithmetic says. Asked once, when it is first
    # formatted; a volume that exists keeps the size it has.
    @staticmethod
    def _share_of_space(space: dict, low: float = 0.75) -> int:   # (was `_share_of_free(root)`: the container's disk, not the daemon's — урок 10)
        ...
        return max(1 << 30, min(int(u.free * 0.8), u.free - (2 << 30), int(u.total * low) - u.used))
```

Спрашивается это **один раз**, при форматировании. Существующий том хранит свой размер, и перезапуск регистратора на заполненном диске не сожмёт кольцо.

Третий путь — `$VOLUME` в юните: том прибит к этому экземпляру. Так говорят про диск, который знает юнит-файл. Прибитый к диску регистратор захвата не берёт и не отдаёт. Но если его том не открывается (`wrong`), он сообщает нулевую ёмкость, как и незакреплённый со сломанным томом (шаг 9):

```python
                if self.store is None or self.engine_lost:
                    self.volume_error = str(self._write_into(vol) or "")
                    self.capacity = 0 if self.volume_error else self.full_capacity    # will not open: not a place to put a recording
```

Отдать диск ему некуда, а место, куда нельзя писать, не должно получать записей.

**Прибитый к сетевому тому — под тем же холдом, что все** (седьмое ревью, блокер 2). Прибитый регистратор не брал захвата и у сетевого тома: свободный регистратор другой коробки видел том незанятым, брал его и монтировал, писатель прибитого останавливал движок, а записи пропадали молча; второй экземпляр с тем же `$VOLUME` монтировал том через секунду. Теперь `$VOLUME` выбирает, **какой** том писать, а писать ли — решает захват: сетевой том прибитый регистратор берёт тем же путём, что незакреплённый (шаг 6), только кандидат у него один, и на собственный диск сервера он не уходит. Пока захват у другого, он сообщает `volume: ""`, нулевую ёмкость и причину в `volume_wait` (на `/metrics` — `rec_volume_wait{worker} 1`, восьмое ревью): *net is being written by r-2: this recorder is pinned to it and starts writing it once r-2 lets it go or stops* (урок 10, шаг 3).

Тесты: `test_volumes.py::test_nothing_declared_is_the_box_as_it_always_was` и `test_rec_volume.py::test_a_recorder_with_nothing_declared_formats_its_servers_volume_and_records_into_it` — регистратор форматирует том сервера рядом с деревом ресурса (`file://<корень коробки>/volume`) и пишет в него поток `1/e<эпоха>`.

### Предложение консоли

Первый том оператор не должен набирать руками. Коробка уже говорит, куда пишет и какого размера её том: `archive` и `archive_quota` в heartbeat'е регистратора. Консоль это и предлагает:

```python
        # The size the volume HAS, from the recorder that formatted it — not the whole partition, which it shares
        # with the resource's events: declared at the partition's size, the ring would be resized past the room.
        total = int(hb.extra.get("archive_quota") or ((res.get(server) or {}).get("space") or {}).get("total", 0))
        out[server] = {"name": server, "kind": "local", "url": root, "server": server, "quota_bytes": total,
                       "why": "this box records here and the disk is not declared as a volume"}
```

Размер раздела из heartbeat'а ресурса остался запасным ответом — для регистратора, который своего размера не сказал. Предложить весь раздел было бы ошибкой: объявление поменяло бы размер кольца, и оно выросло бы за место, которое делит с деревом событий.

**Предложение, а не строка.** Комментарий над `suggest`: *nothing here writes configuration on a process's behalf.* Оператор нажимает кнопку, и с этой минуты диск — том с числом. Число можно уменьшить, а остаток отдать второму тому.

И главное свойство: **объявление ничего не двигает**. Имя предложения — имя сервера, то есть то же, под которым регистратор уже пишет. Тот же владелец писателя — `rec:<имя>`. Регистратор берёт объявленную строку и продолжает писать туда же, тем же открытым томом:

```python
    first = r.store
    assert r.volume_pass() == "srv-a" and r.hold == "srv-a" and r.store is first and first.url == own
```

Тест — `test_volumes.py::test_the_console_offers_the_disk_this_box_already_records_into`. Он же объявляет рядом второй том `cold` на том же диске.

## Шаг 4 — Квота — размер кольца

```python
    for f in ("quota_bytes", "shrink_confirmed"):
        try:
            int(fields.get(f, 0) or 0)
        except (ValueError, TypeError):
            raise Refused(f"`{f}` is a whole number of bytes, not {fields.get(f)!r}") from None
    if int(fields.get("quota_bytes", 0) or 0) <= 0:
        raise Refused("a volume needs `quota_bytes` — its size in bytes: the ring the engine formats it as "
                      "(the console offers the size the box's own volume already has)")
```

**Число проверяется как число, у двери.** `"1e12"` или `"64M"` бросали из этой проверки голый `ValueError`: строка не писалась, но консоль отвечала ошибкой, а не отказом; `shrink_confirmed` не проверялся вовсе и падал по дороге к строке (седьмое ревью). Теперь оба поля — целое число байт, иначе `Refused` со словами *is a whole number of bytes*. Тест: `test_row_reader.py::test_one_garbled_volume_row_stops_no_recorder_and_is_named_on_the_volumes_page` (его последняя часть).

Квота нужна **каждому** объявленному тому, локальному тоже. Причина — в том, что такое том для движка. Новый том `obsd` форматирует ровно на этот размер, и дальше он кольцо: заполнился — отдаёт старейшие блоки (урок 7). Без числа форматировать нечем:

```python
            if not vol.exists():
                if not self.quota:
                    raise ArchiveError("wrong", f"{self.name}: no volume there and no quota to format one with")
                vol.format(self.quota, max_block=self.block, optimal_read=self.read, label=self.name)
```

У сетевого тома спросить свободное место нельзя вообще: `statvfs` у бакета отвечает про машину, а не про бакет. У двух томов на одном разделе свободное место одно на двоих, и каждый счёл бы его своим. Число на каждом — то, что делает их двумя томами, а не двумя именами одного.

Поменять квоту можно на ходу. Регистратор замечает новое число на следующем проходе и меняет размер кольца, не останавливая записи:

```python
            if vol.quota_bytes and vol.quota_bytes != self.store.quota:
                try:
                    self.store.resize(vol.quota_bytes)   # a new quota is a new size of the ring, without stopping
```

`Archive.resize` говорит, что значит уменьшение: *shrinking frees the oldest*. Поэтому консоль пишет уменьшение квоты в журнал — `archive.volume.shrink_requested`, кто, с какого числа на какое и подтверждено ли (М10A, урок 15), — а `archive.volume.shrunk` пишет регистратор, когда движок уменьшение применил. Сначала консоль писала «сжат» в момент просьбы, хотя без `shrink_confirmed` регистратор ничего не сжимал, и страница показывала квоту, а не размер кольца (четвёртое ревью). Теперь `/rec/volumes` и страница показывают **настоящий** размер кольца из heartbeat'а держателя и пометку «не сжат», а в форме есть галочка подтверждения. Отдать тому меньше — значит отдать самые старые минуты, и об этом спросят.

Чего квота **не** делает: не удаляет по сроку. Срок записи — `retention_days` — потолок того, что показывают двери (урок 8). Что ещё лежит в томе, решает кольцо.

## Шаг 5 — Как том открывается

`obsd` открывает том по **параметрам**, а не по строке с ключом:

```python
# Where a volume is, as `obsd` opens it: PARAMETERS, never a URI with a key in it — a URI is printed, logged,
# published in heartbeats; the key travels separately (`access_secret`, sealed in the store, opened only by the
# process that mounts the volume: М10A Lesson 18).
def volume_params(url: str, secret: str = "", access_key: str = "") -> dict:
    if "://" not in url:
        return {"schema": "file", "path": url}           # a local volume's row names its directory
    u = urlsplit(url)
    if u.scheme == "file":
        return {"schema": "file", "path": unquote(u.path)}
    if u.scheme.startswith("s3"):
        ...
        return {"schema": u.scheme, "host": u.hostname or "", **({"port": str(u.port)} if u.port else {}),
                "region": parts[0], "bucket": parts[1], "path": "/".join(parts[2:]),
                "access_key": access_key, "secret_key": secret}   # the key's id from the row's `access_key`, never the url
    raise ValueError(f"{url}: not an archive this course opens (file://, s3://)")
```

Три формы адреса: голый путь, `file://` и `s3://<host>/<region>/<bucket>[/<path>]`. Всё остальное — `ValueError`, а `classify` читает его как `wrong`: адрес, который курс не умеет открыть, сам не починится.

**Ключ никогда не идёт в адрес.** `url` печатается на странице, уходит в heartbeat регистратора полем `archive` и лежит в строке. Ключ внутри него оказался бы в трёх публичных местах сразу, и правило суффикса `_secret` не помогло бы: поле, которое оно охраняет, — не то, что несёт ключ. Поэтому `refuse` отказывает адресу с `@` в части хоста:

```python
    if "@" in url.split("//", 1)[-1].split("/", 1)[0]:
        raise Refused("a volume's url names the archive, never the key to it: the credentials go in "
                      "`access_secret` — this string is printed on the page and published in heartbeats")
```

У ключа бакета две части, и строка тома держит их в двух полях. **Какой** это ключ — `access_key`, идентификатор ключа. Он не секрет, поэтому показывается, как логин камеры:

```python
    access_key: str = ""          # a bucket's key ID — which key, not the key: shown, like a camera's login
```

Сам ключ — `access_secret`, значение среди значений. Консоль кладёт его в хранилище запечатанным, как пароль камеры (`write(..., sealer=…)`, обратная связь CD). Распечатывает его только процесс, который прямо сейчас открывает том, и оба поля доходят до демона параметрами:

```python
        secret = self.sealer.open("access_secret", vol.access_secret) if vol.access_secret and self.sealer else vol.access_secret
        store = Archive(vol.url, vol.name, vol.quota_bytes or self.default_quota, f"rec:{vol.name}", self.session, self.wall,
                        secret=secret, access_key=vol.access_key, ...)
```

Раньше идентификатора ключа в строке не было, а `volume_params` искал его в адресе до `@` — там, куда `refuse` его не пускает. Объявленный s3-том доходил до демона без `access_key`. Теперь идентификатор — поле строки, и адрес по-прежнему не несёт ничего, кроме того, где архив.

Тесты: `test_volumes.py::test_the_key_never_goes_into_the_address`, `test_a_network_volume_needs_a_quota_and_a_local_one_needs_a_server` — заодно проверяет, что `served` не отдаёт `access_secret` никогда, — и `test_a_bucket_names_its_key_in_a_field_and_its_secret_sealed_never_in_the_address`:

```python
    p = volume_params(v.url, "wJalr", v.access_key)
    assert (p["access_key"], p["secret_key"], p["bucket"], p["path"]) == ("AKIAEXAMPLE", "wJalr", "vms", "site-7")
    shown = volumes.served(box.vars, REC_SPEC.sub, box.wall())["volumes"][0]
    assert shown["access_key"] == "AKIAEXAMPLE" and "access_secret" not in shown
```

## Шаг 6 — Захват, запасной и возврат по имени

Регистратор без `$VOLUME` берёт том сам, из того, что может обслуживать (`servable`), в том же порядке. Берёт — значит захватывает `rec/holds/<имя>` по CAS:

```python
            taken = self.claim_hold(candidates) if candidates else None
            if taken is None:
                ...
                self.volume, self.capacity = "", 0             # a spare is not a place to put a recording
                return self.volume
```

**Всё занято — это запасной, а не ошибка.** Процесс работает, ничего не несёт, говорит `volume: ""` и нулевую ёмкость. Ровно поэтому следующий сетевой том, объявленный на консоли, обслуживается за один проход, а не за одно развёртывание (`test_a_declared_volume_is_taken_by_one_recorder_and_the_other_is_a_spare`).

**Захват — аренда, а не назначение.** Держатель замолчал — захват истёк через `slot_ttl` (45 секунд), и том взял запасной. Никто ничего не решал (`test_a_spare_picks_up_a_volume_whose_recorder_went_silent`).

**Потерять том — не потерять слот.** Слот говорит, какой это процесс; захват — в какой архив он пишет. Процесс, у которого забрали том, останавливает его записи и остаётся собой: не отсечён, слот при нём, на следующем проходе берёт другой (`test_a_withdrawn_volume_stops_the_recordings_and_leaves_the_process_running`).

### Том идёт за именем (обратная связь CF), сетевой — только на хосте держателя

Регистратор, убитый `kill -9` и поднятый systemd под тем же именем, — тот же воркер. Слот он забирает сразу (урок 17). Том раньше ждал истечения захвата: 45 секунд без записи на томе, который этот же процесс держал минуту назад. Теперь захват помнит, **чей слот** его держит (`by`), и воркер этого слота забирает его сразу, раньше других кандидатов:

```python
            mine = [c for c in candidates if self.name and held[c].by == self.name]
            slot = read_slot(self.sub.slot_key(self.name), self.name, self.vars.get(self.sub.slot_key(self.name))[0]) if mine else None
            named = slot is not None and slot.holder == self.instance      # (a slot row that does not parse proves nothing)
            mine = mine if named else []
            for cand in mine + [c for c in candidates if c not in mine]:
                key, now = self.sub.hold_key(cand), self.wall()
                idx, cur = rows[cand][1], held[cand]
                ours = named and cur.by == self.name and cur.holder != self.instance and self.hold_follows_name(cand, cur.holder)
                if not ours and not self._hold_stale(cand, cur, idx):
                    continue                                   # somebody live is writing there
```

`named` — условие, без которого правило было бы опасным. Забрать том назад можно, только пока слот и правда у этого экземпляра. Экземпляр, которого systemd заменил, носит то же имя и не должен по дороге отобрать том у преемника. Всем остальным том по-прежнему достаётся после истечения захвата (`test_a_recorder_started_again_under_its_name_takes_its_volume_back_at_once`). `held` — строки холдов, прочитанные через `read_hold`: строка, которая не разбирается, — не кандидат и никому не мешает взять другой том (урок 10, шаг 3).

**Сетевой том идёт за именем только на хосте своего держателя.** `hold_follows_name(cand, cur.holder)` — вопрос платформы к подсистеме: идёт ли место за именем, если его держит экземпляр `holder`. Регистратор отвечает «да» для диска — с другого хоста его не запишешь. Для сетевого тома — только когда прежний держатель на этом же хосте. Экземпляр, взявший имя, может оказаться на **другой** коробке, а прежний — замороженным со смонтированным писателем. На двух демонах это воспроизведено (шестое ревью, блокер 2): второй `r-1` брал холд сетевого тома сразу, монтировал через 13 секунд, первый просыпался внутри своего окна записи — и оба писали. Окно записи прежнего держателя отмерено от того, что претендент ждёт `slot_ttl + HOLD_SKEW`, и экземпляр с другого хоста это ожидание не снимает.

Шестое ревью закрыло это ожиданием для всех, и перезапуск на той же коробке стал стоить 50 секунд без записи (седьмое ревью, «Открытое»). На той же коробке ждать не нужно. `holder` в строке холда — `host:pid:rnd`, тот же хост — тот же демон, а демон держит на томе одного писателя: монтирование нового экземпляра получает `ALREADY_LOCKED`, пока писатель старого прицеплен, и подхватывает его (`reattached`), когда тот отцеплен. Экземпляр без хоста в имени (`INSTANCE_ID`, у М11 — `NOMAD_ALLOC_ID`) ждёт. Сразу берётся и холд, отпущенный намеренно (`released`): его писатель закрыт до отпускания. Тесты: `test_rec_volume.py::test_a_network_volumes_hold_follows_the_name_on_its_holders_host_and_waits_on_another`, `test_volumes.py::test_the_same_name_waits_out_a_network_volumes_hold_unless_it_was_let_go`, `test_rec_volume.py::test_a_second_instance_of_the_same_slot_on_another_box_does_not_take_a_network_volume_from_a_frozen_one`.

Писатель идёт за томом тем же способом. Регистратор монтирует том под владельцем `rec:<том>`. Демон держит писателя исчезнувшей сессии *отсоединённым* `OBSD_WRITER_GRACE_S` (в `deploy/obsd.service` — 90 секунд, дольше, чем истекает захват) и отдаёт его тому, кто назовёт того же владельца: `reattached: true`, без ожидания блокировки и без восстановления. Отдаёт — на этом хосте: регистратор другой коробки, взявший сетевой том, писателя первого хоста не получит, и конец отсрочки там закроет его со сбросом. В чужой том этот сброс не попадёт: движок с патчем 07, который курс требует, не даёт писать писателю, чей замок стал чужим, и чужой lock-файл не снимает (урок 6, шаг 12). Тесты: `test_rec_volume.py::test_a_recorder_killed_and_started_again_picks_up_the_writer_it_left` и `test_volumes.py::test_a_restart_takes_its_volumes_writer_back_and_never_opens_the_local_one` — второй заодно проверяет, что перезапущенный регистратор смотрит на объявленные тома **до** того, как откроет что-нибудь своё, и собственный том сервера не форматируется.

Заметьте, кто за что отвечает. Демон обещает одного писателя на том **на хосте** (README `obsd`: *one writer per volume on the host*). Один писатель на том **в кластере** даёт только захват. Отсюда шаг 8.

## Шаг 7 — Отпустить: сначала писатель, потом захват

```python
        # The writer is closed while the volume is still ours — its flush is what puts the last minutes on the
        # volume — and only then is the hold let go: released first, the next holder would mount a volume with
        # our writer still in it. Waited one call's timeout, on the leases' thread (Т-M1): a flush longer than that
        # goes on in the daemon, and whoever mounts the volume next finds it busy until it is done — the daemon keeps
        # one writer per volume, and on another host the engine's own lock holds it. A network volume whose hold is
        # already lost is not closed at all: its writer is given up (`_close_store`; the review's fifth pass, blocker 1).
        self._leaving = True
        try:
            self._close_store(quiet=True, wait=self.session.timeout)
        finally:
            self._leaving = False
        try:
            self.release_hold()
        except OSError:                              # the store is silent: the hold lapses by itself
            self.hold = None
```

Это `leave_volume`: том отозвали, отключили или забрали. То же в `after_stop`, при штатной остановке (обратная связь BR). Порядок — весь смысл. Отпущенный захват берут сразу, и взявший монтирует том на запись. Писатель закрывается, пока том ещё наш: его сброс кладёт последние минуты в том. Отпусти захват первым — следующий регистратор найдёт в томе нашего писателя.

Порядок верен, пока том наш. Сетевой том, чей холд уже потерян, закрывать нельзя: закрытие — сброс, а том, может быть, уже держит другая коробка. Такого писателя бросают — `WRITER_ABANDON`, без единой записи, — а что он взял и не успел записать, считают: тревога `archive.footage.dropped` в журнале записи (шаг 8, урок 10, шаг 11).

Тесты: `test_rec_volume.py::test_leaving_a_volume_closes_its_writer_before_the_hold_goes` (следующий монтирует чистый том, `reattached` ложно, и видит всё, что было записано), `test_volumes.py::test_the_recorder_writes_into_the_volume_it_took` (отозванный том хранит записанное, в новый не попало ничего из старого) и `test_orderly_stop.py::test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it`.

## Шаг 8 — Когда хранилище молчит

`volume_pass` читает строки томов и продлевает захват. Хранилище, которое не ответило, бросает исключение, и регистратор из-за этого **ничего не отпускает**. Не прочитать список — не значит «ничего не объявлено». Не прочитать захват — не значит «его держит другой» (обратная связь BK). Сколько так можно, зависит от вида:

```python
    #   a disk of this server     stays this recorder's for as long as the silence lasts. Nobody else can write
    #                             to it: it is here
    #   a network archive         any box may serve it, and one that can reach the store will take the hold when
    #                             it lapses. Two writers in one archive is not a duplicate, it is damage — so
    #                             when the hold has gone `slot_ttl − margin` unconfirmed, it is let go, and its
    #                             recordings stop. The one case where silence still stops a recording
    #
    # From that moment the fence refuses every sample (`_may_write_volume`; the review's fifth pass, blocker 1), and the
    # writer is still closed — its flush is the last minutes — while nobody else may have taken the hold: until
    # `slot_ttl + HOLD_SKEW`, what a claimant waits (`_may_close_volume`). A pass that comes later than that — the box
    # was frozen — gives the writer up instead (`_close_store`).
```

```python
            except OSError as e:
                self.store_errors += 1
                quiet = self.clock() - self._hold_confirmed
                if self.hold is not None and self.hold in self._shared and quiet >= self.slot_ttl - self.lease_margin:
                    self.leave_volume(f"the hold on network archive {self.hold} has not been confirmed for {quiet:.0f} s "
                                      f"(the store does not answer: {e})")
```

**Диск остаётся.** Взять его не может никто, кроме регистратора этого сервера. Молчание хранилища здесь ничего не меняет, и запись продолжается.

**Адрес отпускается.** Захват истечёт через `slot_ttl`, и коробка, которая хранилище видит, возьмёт том. Регистратор, который хранилища не видит, не может узнать, что это случилось. Поэтому он уходит сам, раньше: за `lease_margin` до истечения (45 − 5 = 40 секунд по умолчанию). Два писателя кадров под разными эпохами дают перекрытие, которое таймлайн разбирает. Два писателя в одном томе на двух хостах — порча, и демон одного хоста не видит писателя другого.

**Отпустить — ещё не значит перестать писать.** Пока отпускание ждало прохода, конвейеры писали: холд проверялся только перед монтированием, и коробка, замороженная целиком, просыпалась с писателем, который клал кадры в чужое кольцо, а её проход закрывал его со сбросом и удалял чужой lock-файл (пятое ревью, блокер 1; урок 10, шаг 11). Теперь холд проверяется перед каждым кадром: с `slot_ttl − margin` без подтверждения в том не уходит ничего, прошёл проход или нет. Закрывается писатель, только пока холд подтверждён моложе `slot_ttl + HOLD_SKEW`, — раньше этого срока никто другой том не возьмёт. Проход, пришедший позже (коробка спала), писателя не закрывает, а бросает (`WRITER_ABANDON`): ни одной записи больше, а взятое и не записанное — тревога `archive.footage.dropped` с секундами. Проверка холда — не ограда: один кадр замороженного процесса она пропустит. Ограждает том движок с патчем 07 — писатель, чей замок стал чужим, не пишет ничего, кто бы его ни закрывал, — и другого движка курс не поддерживает (урок 10, шаги 3 и 11). Тест: `test_rec_volume.py::test_a_box_frozen_whole_writes_nothing_into_the_network_volume_another_box_took_and_closes_nothing_there`.

`self._shared` — какие тома адресные, по последнему удачному чтению. Спросить в момент молчания уже не у кого. В множество попадает всё, что `any_box`: сетевой том, резервный и происшествий без сервера.

Тест: `test_store_outage.py::test_a_recorders_own_disk_stays_its_own_and_a_network_archive_is_let_go` — одна ошибка хранилища ничего не отпускает; через 72 секунды молчания локальный том при регистраторе, сетевой отпущен.

## Шаг 9 — Когда том не открывается: неверно, недоступно, занято

Открыть том — единственная честная проверка. Строка может называть путь, которого нет, или бакет, до которого не дотянуться, и в строке этого не видно. Отказ читается по **виду** (`vms/archive.py`):

```python
    wrong   only a person changes it: a path that is not a volume, no permission, a bucket that refuses the key.
            The volume is handed back
    away    a timeout, a network that is down, the daemon itself gone. Kept: it is back in a minute, and handing
            it back would reshuffle every recording on it for a link that returns. `SESSION_LOST` is away too —
            and more: every handle is dead, and the volume is mounted again (`Archive.lost`)
    busy    another writer holds it on this host (`ALREADY_LOCKED`) — a recorder of the same volume that has
            not let go yet, or one whose grace the daemon is still waiting out

    `away` and `busy` have NO deadline for a disk of this server, on purpose (the review's fifth pass, its third
    question): nobody else can write there, and handing it back for a daemon that is restarted in a minute reshuffles
    every recording on it. So the recorder keeps it, and while this host's engine stays broken its recordings are
    written nowhere. That is the cost, and it is said, not hidden: `archive_failure` and `archive_away_since` in the
    heartbeat show the operator since when, and the operator decides.

    A volume ANY box may serve has one (the review's sixth pass): while this host's engine answers nothing, the hold is
    renewed for `RecWorker.ENGINE_SILENT_FOR` and no longer — then the volume is let go, for a box whose engine does
    answer (`RecWorker.volume_pass`). And `busy` under this recorder's own hold — another host's writer that does not
    let go — lasts `RecWorker.BUSY_FOR` and no longer (the seventh pass): let go, with an alarm.
```

`classify` раскладывает статусы движка: `PERMISSION_DENIED`, `NOT_A_VOLUME`, `READ_ONLY` и ещё пять — `wrong`; `ALREADY_LOCKED` — `busy`; молчание демона (`Unavailable`) и всё прочее — `away`.

### Вид тома меняет приговор

Движок говорит про локальный диск, который не откроется, теми же словами, что про упавшую сеть. `VOLUME_EXISTS` отвечает «да» для пути под обычным файлом, и монтирование падает с `GENERIC_ERROR`. Путь, который нельзя создать, роняет форматирование с `IO_ERROR`. По классификации это `away` — «вернётся через минуту». Для диска на этой коробке это неправда:

```python
            # A DISK on this box that cannot be formatted or mounted — a file where the directory should be, a
            # path nobody may create — is not a link that comes back in a minute. The engine says it as an I/O or
            # a generic error, the same words a network volume uses for a network that is down, so the kind of
            # volume decides: on a box, wrong; at an address, away.
            if e.kind == "away" and e.name in ("IO_ERROR", "GENERIC_ERROR") and volumes.on_a_box(vol):
                e = ArchiveError("wrong", e.detail, e.name)
```

Те же два статуса у тома по адресу остаются `away`: сеть правда возвращается.

### Что регистратор делает с каждым

**`wrong` — отдать, если есть куда.** Регистратор отпускает том и пробует следующий из `servable`. Если взять больше нечего, он **забирает сломанный обратно** и остаётся на нём с нулевой ёмкостью и причиной в `volume_error`. Комментарий в `volume_pass` объясняет выбор: писать в сломанный архив и говорить об этом плохо, не писать совсем из-за диагностики — хуже. Починили — следующий проход открывает том, ошибка исчезает, ёмкость возвращается (`test_volumes.py::test_a_volume_held_and_unwritable_is_not_served`, где на месте каталога лежит файл).

**`wrong` посреди работы — отдать и не брать сразу назад.** Движок начал отказывать в кадрах: ключ отозвали, том стал только для чтения. `RecSink` сообщает об этом, и следующий проход отдаёт том. Открыть его снова, скорее всего, получится, а первая запись опять упадёт. Поэтому том оставляют в покое на `REFUSED_FOR` — десять минут: достаточно, чтобы не мигать между «взял» и «отдал», и достаточно мало, чтобы починенный ключ подхватился без перезапуска (`test_an_archive_that_refuses_writes_mid_run_is_handed_back`).

**`away` — держать.** Том остаётся местом, с полной ёмкостью, а регистратор говорит `archive_error` и `archive_failure: away` и пробует на следующем проходе. Отдать его значило бы перетасовать все записи тома ради связи, которая вернётся (`test_an_archive_that_is_away_at_open_is_kept`, `test_rec_volume.py::test_a_recorder_with_no_daemon_says_the_archive_is_away_and_keeps_its_place`).

**`busy` — держать.** Писателя держит демон: прошлый регистратор ещё не отпустил его, или идёт отсрочка. Это пройдёт само. Heartbeat при этом говорит `archive_failure: busy`, а не `away`:

```python
            self.archive_error, self.archive_failure = e.detail, e.kind
```

(`RecWorker._away`, общий для `away` и `busy` при открытии.) Ответ один — держать и пробовать снова, — а причины разные. «Демона нет» ищут на хосте, «том держит другой писатель» — у прошлого регистратора этого тома. Метрика `rec_archive_failure{kind}` разводит их по виду.

**`busy` под своим же владельцем — не всегда «пройдёт само».** Если демон называет в `ALREADY_LOCKED` нашего владельца `rec:<том>`, писатель не отсоединён, и так дольше `OWN_LOCK_FOR` (10 с), это, скорее всего, сирота нашей же сессии: монтирование, ответ на который потерялся. Регистратор оставляет сессию, и новая подхватывает писателя (пятое ревью, блокер 2; урок 6, шаг 4). Оставляет один раз: если блокировка осталась и после этого — или если в `STATS` демона есть сессия с именем этого регистратора и чужим pid, — том пишет другой процесс на этом сервере, и `archive_error` говорит это прямо: кто ещё подключён к `obsd` и что один из двух регистраторов надо остановить (шестое ревью).

**Диск в `away`/`busy` держат без срока. Сетевой том при молчащем демоне — пять минут, в `busy` — десять.** Пятое ревью спросило, почему сетевой том не уходит на другой хост, когда `obsd` этого хоста сломан надолго, и ответом было «решение: отдать том из-за демона, которого перезапускают за минуту, значит перетасовать все его записи». Шестое показало цену запуском: демон заморожен на 320 секунд, холд продлевается все 320, на томе не пишется ничего, а коробка с живым демоном взять его не может. Теперь срок есть: через молчащий демон холд сетевого тома продлевается `ENGINE_SILENT_FOR` — 300 секунд, — потом том отпускается, оставляется в покое на `REFUSED_FOR`, и коробка, чей демон отвечает, берёт его сразу (урок 10, шаг 3). Минуту перезапуска демона том по-прежнему переживает на месте. Диск этого сервера не отпускается никогда: его некому записать, кроме этого регистратора, и пока демон не вернулся, его записи не пишутся нигде — это видно (`archive_failure`, `archive_away_since`), и решает человек. `busy` у сетевого тома под своим холдом — `BUSY_FOR`, десять минут **непрерывного** `busy` (седьмое ревью; восьмое — непрерывного: отсчёт сбрасывает любой отказ, который не `busy`, иначе один `busy` и десять минут лежащей сети отпускали просто недоступный том с ложной тревогой): демон отвечает, замок держит чужой писатель — регистратор другой коробки завис с открытым томом. Потом том отпускается на `REFUSED_FOR`, с тревогой `archive.volume.busy` и причиной для оператора; другому хосту не делается ничего. У диска `busy` срока не имеет. Тесты: `test_rec_volume.py::test_a_network_volume_is_given_up_when_this_hosts_obsd_has_answered_nothing_for_five_minutes`, `test_a_frozen_daemon_under_a_network_volume_costs_a_pass_one_wait_and_the_volume_goes_to_a_box_that_answers`, `test_a_network_volume_busy_under_this_recorders_hold_for_ten_minutes_is_let_go_with_an_alarm`, `test_one_busy_pass_and_then_a_network_down_for_ten_minutes_lets_no_volume_go_and_the_recorder_writes_when_it_is_back`.

**Сетевой том на слишком старом `obsd` — `wrong`, и регистратор его не берёт.** Том, который может взять другая коробка, требует от демона умения его бросить (`WRITER_ABANDON`, движок с патчем 07). Демон без этого регистратор проверяет один раз (`Session.abandons`) и такой том не заявляет вовсе; причина — в `refused` его heartbeat'а и на странице томов: *obsd on srv-a is too old to write net safely — a volume any server may take: this obsd cannot give a volume up when another server takes it. Update obsd on srv-a; volumes on its own disks are not affected* (урок 10, шаг 3; `test_lock_lost.py::test_a_recorder_takes_no_network_volume_on_an_obsd_that_cannot_give_one_up`).

### Молчащий демон не останавливает жизнь регистратора

Каждый вызов к `obsd` ждёт не больше `OBSD_TIMEOUT` — десять секунд, меньше аренды. Проходы идут в том же потоке, что продлевает аренды, и демон, который принял запрос и замолчал, иначе держал бы поток дольше аренды: регистратор отсечён, все записи остановлены из-за одного молчащего процесса. Дольше ждёт только `WRITER_CLOSE` — его сброс протокол разрешает растянуть. Тесты в `test_archive_outage.py`: `test_a_daemon_that_is_not_there_does_not_stop_the_recorder`, `test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living`, `test_the_recorders_calls_wait_less_than_a_lease_and_only_a_close_waits_for_its_flush`, `test_when_the_daemon_answers_again_the_volume_opens_and_the_outage_is_over` и `test_backfill_waits_while_the_volume_is_taking_nothing` — пока том ничего не берёт, дозаписи некуда класть то, что она принесёт.

## Шаг 10 — `backup` и `edge`: `home` становится фильтром

Резервный и краевой тома держат вторую запись камеры (урок 26). Внутри кластера правила у них общие, поэтому код берёт оба:

```python
STANDBY = ("backup", "edge")


def backups(vars_) -> set[str]:
    """The names of the enabled standby volumes — backup and edge."""
    return {v.name for v in declared(vars_) if v.kind in STANDBY and v.enabled}
```

Везде `home` — предпочтение: дом лёг, запись пишется на соседнем томе и вернётся сама. Для резервного тома предпочтение неверно в обе стороны. Основная запись, переехавшая на резервный том, пока её сервер перезагружается, оставляет одну копию там, где оператор платил за две, а на карте камеры ещё и съедает её канал. Резервная, уехавшая с резервного тома, — уже не копия. Поэтому для `rec` это фильтр:

```python
def admit_recording(ctl, row: dict, worker: str) -> bool:
    names, kept = backups(ctl.vars), incidents(ctl.vars)
    if not names and not kept:
        return True
    place = ctl.place_of(worker)
    if place in kept:
        return False                                  # a place for what somebody kept, never one to record into
    home = str(row.get("home") or "")
    if home in names:
        return place == home
    return place not in names
```

Запись с домом на резервном томе идёт на этот том или никуда. На резервный том не идёт больше ничего. «Никуда» — честный ответ: запись попадает в `/unplaceable`, и оператор читает, что карты нет (`test_backup_archive.py::test_a_backup_volume_holds_its_own_recordings_and_nothing_else`). А на карту запись не ставится вовсе, если она не камеры этой карты: такую строку контроллер не принимает (`volumes.refuse_recording`, урок 26, шаг 6).

Вторая дверь — `rank_near_recording`: воркер камеры с двумя записями встаёт рядом с **резервной**. Рядом с основной он упал бы вместе с её сервером, и резервная потеряла бы поток ровно в ту минуту, ради которой существует (`test_the_camera_stands_beside_the_backup_recording`).

Третье, что дают эти два вида, — `when: offline`. Резервная запись с этим полем пишет только пока основная должна писаться и не пишется: за сбой, никогда за решение (`_offline_backup` требует и поле, и дом на резервном томе; `test_an_offline_backup_stands_in_for_a_failure_and_never_for_a_decision`).

Названы виды врозь потому, что через границу кластеров они ведут себя врозь. Комментарий в `volumes.py`: резервный том получает поток по сети, а карта пишет то, что видит её собственный сенсор, и сеть между ними не стоит. И пишутся и читаются они врозь: `backup` — движком и через дверь архива, `edge` — буфером камеры и её ответом на запрос диапазона (урок 26, шаги 3 и 10). Внутри кластера это видно в источниках дозаписи основной записи: резервная помечается `edge` или `backup` по виду своего тома (`backup_sources`), и карта источником становится, только если есть кому спросить камеру (`card_range`).

## Шаг 11 — `incidents`: место для улик, а не для записи

Том — кольцо, и кольцо не умеет пощадить диапазон: отмеченное «сохранить» перезапишется со всем остальным. Поэтому метка удержания — не флаг на видео на месте, а **копия** в том отдельного вида:

```python
# `incidents`, which only keeps go into. The recorder that holds it copies every keep's minutes out of whichever
# recorder's door holds them (`RecWorker.keep_pass`), and nothing is ever recorded into it: it is a place for
# evidence, not a place to put a camera (`admit_recording`).
```

Поставить туда запись нельзя, и защищено это дважды. `admit_recording` отказывает месту `incidents` для любой строки. А регистратор, взявший такой том, говорит нулевую ёмкость, как запасной:

```python
    def _place_kind(self, vol) -> None:
        self.incidents = vol.kind == "incidents"
        if self.incidents:
            self.capacity = 0
```

Вместо записи он раз в минуту копирует интервалы меток из дверей тех регистраторов, у кого они есть, потоком `<запись>/e0`. Эпоха ноль — ничья аренда: где живое видео ещё есть, минутами владеет его собственная эпоха (`authoritative`), а где кольцо его уже забрало, копия — всё, что осталось. Что проход скопировал, он называет событием `archive.keep.copied` с sha256 кадров, как они лежат в томе.

Дверь такого тома показывает всё, без потолка видимости: `_visible_from` отвечает нулём, потому что всё в нём лежит там, потому что кто-то это отметил.

И том происшествий — тоже кольцо. Отмеченное, которое оно забрало, — тревога `archive.keep.lost` с числом секунд. Ответ — квота больше или выгрузка.

Тесты в `test_keeps.py`: `test_an_incidents_volume_is_a_place_for_evidence_and_never_one_to_record_into` (ёмкость ноль, запись не размещается), `test_a_keep_is_copied_into_the_incidents_volume_and_outlives_the_recordings_ring` и `test_kept_footage_the_incidents_ring_took_is_an_alarm`.

## Шаг 12 — Что видит оператор

У тома три состояния, а не два. «Обслуживается» и «никто не взял» скрывали худшую поломку: захват свежий, консоль считает том обслуживаемым, записи нет, все числа зелёные. Поэтому регистратор говорит, если том не открылся (`volume_error`), и `served` такой том обслуживаемым не считает:

```python
        why = (None if live and not err else
               f"held by {slot.holder}, which cannot write there: {err}" if err else
               "disabled by the administrator" if not v.enabled else
               f"its hold row ({sub.name}/holds/{v.name}) does not parse, so no recorder can take it: mend the row or "
               f"delete it" if v.name in garbled else
               "declared, and no recorder has taken it" if slot is None or slot.holder == "" else
               "the recorder that held it let go" if slot.released else
               "the recorder that held it went silent")
        if why and v.enabled and not err and v.name in refusing:
            why += "; " + "; ".join(refusing[v.name])   # …and the recorders that will not take it say why not
```

Две строки — от шестого ревью. «Никто не взял» без причины оставляло оператора гадать: регистраторы пишут в heartbeat, какой том они **не берут** и почему (`refused`: том отказал в записи, отдан за молчащий демон, `obsd` слишком стар для сетевого тома), и раньше это было видно только в JSON heartbeat'а. Теперь `served` дописывает эти причины к строке тома (`_refusing`): *declared, and no recorder has taken it; r-1 does not take it: obsd on srv-a is too old to write net safely…*. И строка холда, которая не разбирается, больше не роняет весь список: том назван, причина сказана (`holders` читает через `read_hold`).

**Строка самого тома, которая не разбирается, тоже на странице — названная.** Строка, написанная руками или старой сборкой (`quota_bytes: "1e12"`), бросала из `declared`, а под ним — шаг аренд каждого регистратора, эта страница, карта камеры и скан (седьмое ревью, часть 2, блокер 1; что было с регистраторами — урок 10). Теперь `declared(vars_, garbled)` пропускает такую строку, считает её один раз (`VOLUMES`, `volumes_garbled`) и кладёт её имя в `garbled`. `served` показывает её отдельной строкой с `garbled: True` и причиной *its row (rec/volumes/…) does not parse, so no recorder takes it and the console cannot show it: mend the row — declare the volume again — or delete it*; если регистратор всё ещё держит этот том, к причине дописано, что он пишет по строке, прочитанной последней. В `wanted` такой том считается: его объявили, а включён ли он, сказать нельзя. Удалить его можно: `DELETE /rec/volumes/<имя>` находит имя и среди нечитаемых строк и не отвечает 404. Запись на такой том не садится: `volume_named` бросает `Unreadable` (это `Refused`), и `refuse_recording` отказывает записи с `home` на нём, а права на такой том консоль спрашивает как на карту без камеры — грант на весь кластер (`volume_cam` отвечает `"*"`). Тесты: `test_row_reader.py::test_one_garbled_volume_row_stops_no_recorder_and_is_named_on_the_volumes_page`, `test_row_reader.py::test_a_recording_is_not_homed_on_a_volume_whose_row_does_not_parse`.

Рядом — `writing`: открыт, но пишет плохо, по сторожу писателя (урок 10). И пара чисел: `wanted` — сколько процессов нужно объявленному списку, `serving` — сколько есть. `spare: 0` при `serving < wanted` — единственное состояние, которому нужен человек. Консоль его называет и пишет команду словами того оркестратора, который запустил её саму (`systemctl start recworker@r-2` или `nomad job scale recworker 3`), но не выполняет (`test_the_console_says_which_archives_nobody_is_writing_into`, `test_the_console_writes_out_the_command_and_does_not_run_it`, `test_the_numbers_a_scaling_policy_reads`).

### Том, который никто не обслуживает: недоступно, а не потеряно

Сервер упал вместе с диском. Регистратор, державший `disks-a`, молчит, а взять диск чужого сервера не может никто. Видео в томе не потеряно: оно там и недоступно, пока сервер не вернётся. Таймлайн камеры так и говорит, по имени тома и сервера, вместо того чтобы рисовать на этом месте дыру (`unserved_volumes` в `vms/console.py`):

> *footage in disks-a (on srv-a) is unavailable until a recorder holds it again — not lost*

Сервер вернулся — его том вернулся с дисками. Ничего не перестраивали и не копировали. Тесты: `test_rec_volume.py::test_a_volume_nobody_serves_is_named_on_the_timeline_and_not_drawn_as_a_hole` и в М11 `test_lesson3_resources.py::test_a_timeline_spans_two_volumes_and_names_the_one_nobody_serves`.

---

## Виды томов одной таблицей

| | `local` | `network` | `backup` | `edge` | `incidents` |
|---|---|---|---|---|---|
| **где** | диск сервера; `server` обязателен | адрес; `server` запрещён | с `server` — диск того сервера, без — адрес | карта камеры; `server` (коробка камеры) и `cam` (её id) обязательны | как `backup` |
| **кто обслуживает** | регистратор этого сервера | любой | с сервером — этот сервер, без — любой | только регистратор самой камеры (`CardRecorder`); регистратор движка — никогда | как `backup` |
| **хранилище молчит** | остаётся за регистратором | через `slot_ttl − margin` кадры не пишутся и том отпускается; писатель позже `slot_ttl + HOLD_SKEW` не закрывается | с сервером — остаётся, без — отпускается | остаётся | как `backup` |
| **размещение** | `home` — предпочтение | `home` — предпочтение | фильтр в обе стороны | фильтр в обе стороны | не ставится ничего |
| **чем открывается** | движком | движком | движком | каталог на камере, без движка | движком |
| **не открылся** | `IO_ERROR`/`GENERIC_ERROR` — `wrong` | `away` | с сервером `wrong`, без — `away` | ёмкость ноль, `volume_error`, новая попытка через 30 с | как `backup` |
| **квота** | размер кольца | размер кольца | размер кольца | бюджет карты: полна — уходят старейшие сегменты | размер кольца |
| **`when: offline`** | — | — | да | да | — |
| **что пишется** | записи | записи | резервные записи | резервные записи камеры, файлами сегментов | копии меток, `<запись>/e0` |
| **как читается** | дверь архива | дверь архива | дверь архива | ответ камеры на запрос диапазона | дверь архива |

Общее у всех, кроме `edge`: строка `rec/volumes/<имя>` с `quota_bytes` больше нуля, захват `rec/holds/<имя>`, владелец писателя `rec:<имя>`, открытие через `volume_params`, отказ `wrong` — отдать, `away` и `busy` — держать. У `edge` из этого — строка и захват; остальное — урок 26, шаг 10.

## Что может пойти не так

- **Регистратор берёт сначала сетевой том.** Свой диск остаётся без писателя, и запасной на другом сервере его не возьмёт. Порядок в `servable` — свои диски первыми.
- **Ошибка чтения хранилища как пустой ответ.** Регистратор бросает том со всеми записями при первом же сбое хранилища. Не прочитать — не значит «нет».
- **Сетевой том держат, сколько молчит хранилище.** Захват истёк, том взяла другая коробка, и в одном томе два писателя на двух хостах.
- **Холд сетевого тома проверяют только перед монтированием.** Проснувшийся писатель пишет в чужое кольцо, пока проход не дошёл до отпускания. Проверка — перед каждым кадром.
- **Писателя сетевого тома с потерянным холдом закрывают.** Сброс ложится на том другой коробки. Писателя бросают.
- **Сетевой том отдают экземпляру того же слота сразу.** Прежний экземпляр мог быть заморожен на другой коробке, а его окно записи отмерено от ожидания претендента: два писателя в одном томе.
- **Сетевой том держат, сколько молчит демон.** На нём не пишется ничего, а коробка с живым демоном взять его не может. Срок — `ENGINE_SILENT_FOR`.
- **Сетевой том дают демону без `WRITER_ABANDON`.** Он закроет писателя со сбросом в том, который уже чужой. Регистратор такой том не берёт и говорит, какой `obsd` обновить.
- **Одна битая строка холда роняет захват.** Регистратор не берёт никакого тома, список томов в консоли не открывается. Битая строка — беда одного тома.
- **Захват отпущен раньше, чем закрыт писатель.** Следующий регистратор найдёт том с чужим писателем, а последние минуты не сброшены.
- **Локальный диск, который не открылся, считают `away`.** Регистратор держит сломанный диск вечно, его записи никуда не уходят, а на экране «вернётся через минуту».
- **Сетевой том, который не открылся, считают `wrong`.** Каждый обрыв сети перетасовывает все записи тома.
- **Сломанный том отдают, даже когда больше некуда.** Коробка перестаёт писать совсем из-за диагностики.
- **Отказавший посреди работы том берут назад на следующем проходе.** Регистратор мигает между «взял» и «отдал». Нужна пауза `REFUSED_FOR`.
- **Ключ в адресе тома.** Он на странице, в heartbeat'е и в строке. `refuse` не пропускает `@` в части хоста.
- **Идентификатор ключа из адреса.** Адрес с `@` не пройдёт `refuse`, и s3-том дойдёт до демона без `access_key`. Идентификатор — своё поле строки.
- **Закреплённый регистратор с неоткрывшимся томом сообщает полную ёмкость.** Контроллер ставит записи туда, где писать нельзя.
- **`home` предпочтением для резервного тома.** Основная переезжает на него при перезагрузке своего сервера, и копий становится одна.
- **Запись на томе `incidents`.** Камера крутит кольцо улик своим потоком, и отмеченное уходит за часы. Двойная защита: `admit_recording` и нулевая ёмкость.
- **Квота во весь раздел.** `refuse` её пропустит, но кольцо делит раздел с деревом событий ресурса и уведёт диск выше отметки ватерлинии. Консоль поэтому предлагает тот размер, который у тома уже есть.
- **Том недоступного сервера рисуют дырой.** Оператор ищет потерянное видео, которое лежит на месте. Таймлайн называет том и сервер.
- **Карту камеры монтирует движок.** На камере ему не хватит памяти, а на сервере это не его том. `_write_into` отвечает на `edge` отказом, `volume_pass` карту не предлагает.
- **Регистратор камеры берёт любой объявленный том.** Сетевой том на консоли камеры уводит его с карты, и карта перестаёт быть резервной (обратная связь DH). Регистратор камеры берёт только свою карту.
- **Карта не называет камеру.** `server` — коробка, а не камера, и запись другой камеры с `home` на этой карте пишется кольцом этой карты под чужим именем. У `edge` поле `cam` обязательно.

## Итог

- Том — заявление (`rec/volumes/<имя>`) и факт (`rec/holds/<имя>`). Заявление пишет консоль, факт — регистратор, и место существует, потому что его держат.
- `server` в строке решает, где том: на одной коробке или по адресу. `local` и `edge` — всегда коробка, `network` — всегда адрес, `backup` и `incidents` — по полю.
- Регистратор берёт сначала свои диски, потом адреса. Всё занято — запасной: процесс без места и с нулевой ёмкостью.
- Ничего не объявлено — собственный том сервера, `/data/volume` рядом с деревом ресурса, на четыре пятых свободного места и не выше нижней отметки ватерлинии. Консоль предлагает его объявить с тем размером, который у него есть, и объявление ничего не двигает.
- Квота — размер кольца. Новый том форматируется на неё, новая квота меняет размер на ходу, уменьшение отдаёт старейшее и попадает в журнал.
- Том открывается по параметрам. Какой ключ — поле `access_key`, его показывают; сам ключ — значение `access_secret`, запечатанное. Ни то ни другое в адрес не попадает никогда.
- Захват диска идёт за именем слота; захват сетевого тома — только на хосте прежнего держателя, иначе ждёт срока, если его не отпустили намеренно. Прибитый (`$VOLUME`) сетевой том берётся под тем же захватом. Писатель идёт за владельцем `rec:<том>`. Отпускают в обратном порядке: сначала писатель, потом захват.
- При молчащем хранилище диск остаётся, адрес отпускается через `slot_ttl − margin`: два писателя в одном томе — порча. С того же срока в сетевой том не отправляется ни кадра, а писателя, чей холд старше `slot_ttl + HOLD_SKEW`, не закрывают — бросают (`WRITER_ABANDON`) и считают, что он не успел записать. Это проверка, а не ограда: ограждает том движок (патч 07), и на демоне без него регистратор сетевой том не берёт.
- Через молчащий `obsd` холд сетевого тома продлевается `ENGINE_SILENT_FOR` (300 с) и не дольше, непрерывный `busy` под своим холдом держится `BUSY_FOR` (600 с); диск за молчащий демон и за `busy` не отпускается.
- `wrong` — отдать (закреплённый диск не отдаёт, но сообщает нулевую ёмкость), `away` и `busy` — держать, и heartbeat называет каждый своим словом. Для тома на коробке `IO_ERROR` и `GENERIC_ERROR` — `wrong`, для тома по адресу — `away`.
- Для `backup` и `edge` `home` — фильтр в обе стороны, воркер камеры стоит у резервной записи, `when: offline` пишет за сбой.
- `edge` — место, но не том движка: карту пишет регистратор камеры обычными файлами с бюджетом, а читают её, спрашивая камеру (урок 26, шаг 10; как в продукте). Карта называет свою камеру (`cam`), и на ней стоят только записи этой камеры.
- На `incidents` не ставится ничего: туда копируются метки, и это тоже кольцо.
- Том, который никто не обслуживает, недоступен, а не потерян, и таймлайн говорит это словами.

## Упражнения

1. Поменяйте порядок в `servable`: сначала адреса, потом свои диски. Два сервера, по диску на каждом, один сетевой том и по одному регистратору на сервере. Какой диск останется без писателя и почему его не возьмёт никто?
2. Уберите проверку `self.hold in self._shared` из `lease_pass`. Что станет с локальным диском, пока хранилище молчит пять минут? А с записями на нём?
3. Уберите поправку вида в `_write_into`. Объявите локальный том на пути под обычным файлом и прочитайте `heartbeat_extra()`: что скажет `archive_failure`, и куда уйдут записи?
4. Поставьте `REFUSED_FOR = 0` и повторите `test_an_archive_that_refuses_writes_mid_run_is_handed_back`. Сколько раз за десять проходов регистратор возьмёт и отдаст `vol-a`?
5. Отпустите захват в `leave_volume` до закрытия писателя. Какой тест из шага 7 упадёт и на какой строке?
6. Объявите том `incidents` без сервера и два регистратора на разных серверах. Кто его возьмёт, что будет с ёмкостью и что покажет `/volumes`?
7. Уменьшите квоту тома с записью вдвое через консоль. Что появится в журнале, и какие минуты записи исчезнут первыми?
8. Резервный том без сервера (адрес) и молчащее хранилище. Что сделает его регистратор через 40 секунд, и что станет с `when: offline`-записью, которую он вёл?

## Что дальше

Двери архива, через которые консоль собирает таймлайн из всех томов, — [урок 12](12-the-vms-console.md). Как основная запись закрывает дыры из резервной — [урок 26](26-a-backup-archive-of-our-own.md). Как устроено само кольцо, блок и последовательность — [уроки 6–8](07-volume-block-sequence-stream.md). На кластере те же тома берут регистраторы задания `recworker` — М11, урок 3.

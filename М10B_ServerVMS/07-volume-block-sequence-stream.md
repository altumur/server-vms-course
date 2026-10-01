# Урок 7 — Том, блок, последовательность, поток

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** первую половину `vms/archive.py` — имена потоков (`stream_name`, `parse_stream`), `event_log`, `volume_params`, `Span`, `ArchiveError` и `classify`, `Archive` (`open`, `put`, `finish`, `resize`, `seal`, `close`, `reader`, `units`, `spans`); и путь записи регистратора — `RecSink` в `vms/recworker.py` и колбэк `appsink` в `GstRecActuator._before_play` (`gstvms/actuator.py`).
**Время:** ~85 минут.

## Зачем этот урок

Урок 6 дал слова движка: том, блок, последовательность, поток. Том — кольцо размером с квоту. Блок — кусок тома фиксированного размера, который читатель видит, только когда тот закрыт. Последовательность — кадры от ключевого, единица индекса. Поток — именованная череда последовательностей, и имя — единственное, что у потока есть.

Этот урок даёт слова курса поверх них. Начнём с картинки, которая объясняет модуль лучше текста, — **два места, два писателя, одна камера**:

```
том (через obsd)    <запись>/e<эпоха>                         видео: пишет РЕГИСТРАТОР, под своей эпохой
                    <запись>/e<эпоха>/backfill                дозапись в дыру (урок 16)
том incidents       <запись>/e0                               копия удержания (урок 18)
ресурс сервера      vms/<cam>/e<epoch>/<start>Z.events.jsonl  события: пишет ДЕРЖАТЕЛЬ камеры
```

Видео пишет регистратор, события — держатель камеры. Это два разных процесса, у каждого своя эпоха, и они могут работать на разных серверах. Отсюда три нормальных состояния:

- камеру смотрят и не пишут: бакеты событий есть, потока в томе нет;
- регистратор переехал: видео лежит в двух томах под двумя эпохами, консоль сливает ответы их дверей;
- держатель переехал: бакеты лежат на двух серверах, консоль сливает ответы их индексов событий.

Вторая половина урока — **путь записи**. Кадр уходит из `appsink` в писателя тома, и у этого пути три исхода: кадр взят, кадр отвергнут, движка нет. На каждый исход регистратор отвечает по-своему. И отдельно — убитый регистратор: что остаётся на томе и кто это подбирает.

> **Проверка без железа.** `vms/archive.py`, `RecSink` и регистратор целиком проверяются против живого `obsd` (урок 6) с поддельным актуатором: `FakeActuator.feed` кормит приёмник кадрами, как камера. Колбэк `appsink` в `GstRecActuator` написан к биндингу GStreamer и в обычном прогоне не исполняется; проверяется то, что он зовёт, — `RecSink` и движок.

## Что нужно знать заранее

- **Урок 6** — `obsd`, клиент `w2cplatform/obsd.py` и свойства движка: этот урок опирается на каждое.
- **Урок 4** — почему видео пишет не тот процесс, что держит камеру.
- **М10A, урок 6** — эпоха: число, которое здесь попадёт в имя потока.
- **М10A, урок 12** — `EventLog` и бакеты: дерево событий, которое остаётся на ресурсе.

## Чему вы научитесь

1. Разносить видео и события по местам так, чтобы у каждого места был один писатель.
2. Класть отсекающую величину в имя потока и отделять записи зомби одним сравнением чисел.
3. Читать индекс движка как источник истины, ничего не храня рядом с ним.
4. Называть отказ тома по виду — `wrong`, `away`, `busy` — потому что ответ на каждый свой.
5. Открывать том: форматировать новый по квоте и монтировать писателя под владельцем.
6. Делать записанное видимым и задавать каждый вопрос свежему читателю.
7. Отвечать на отказ кадра пропуском до ключевого, а на пропавший демон — перемонтированием.
8. Отличать аккуратную остановку от убийства по тому, что осталось на томе.

---

## Шаг 1 — Два места, два писателя

Комментарий в начале `vms/archive.py` начинается с отказа от файлов:

> *Footage is not files. It is ObjectStorage — the product's engine — behind the host's daemon `obsd` (`w2cplatform/obsd.py`), and what a volume holds is STREAMS of samples, cut by the engine into sequences that open on a key frame, packed into blocks of a size fixed when the volume was formatted. This module is the course's vocabulary over that, and nothing more.*

И кончается тем, что в томе не лежит:

> *Events are not here. They stay what they were — buckets of lines on the resource's tree, `vms/<cam>/` and `rec/<name>/` (`event_log`, the platform's `EventLog`) — a file tree the platform retains, mirrors and indexes, on the server of whoever wrote them.*

```python
SUB = "rec"          # the recorder's subsystem: its streams in the volume, its event buckets on the resource
EVENTS_SUB = "vms"   # the worker's tree: the camera's event buckets


def event_log(root: str, cam, epoch: int, bucket_seconds: int = 600) -> EventLog:
    """The camera's event log on this resource: what the worker holding the
    camera's epoch writes into, recording or not — `vms/<cam>/`, not `rec/`."""
    return EventLog(root, EVENTS_SUB, str(cam), epoch, bucket_seconds)
```

`event_log` — функция в одну строку, которая существует ради докстроки. Читающий код видит: события идут в `vms/`, и пишутся они независимо от записи.

Правило «один писатель на префикс» из М10A здесь держат две разные вещи. В томе — движок: один писатель на том на хосте (урок 6, шаг 12). На ресурсе — дерево: в `vms/<cam>/` пишет только держатель камеры. Координации между регистратором и держателем не нужно, потому что их места не пересекаются.

`test_events_are_buckets_on_the_resource_recording_or_not` проверяет всю картинку. Докстрока:

> *Two places, two writers, one camera: a camera that is watched and never recorded has buckets and no stream; the volume's index answers for media, the resource's event index for the buckets; each is kept by its own rule. No controller wrote any of it.*

Три строки теста стоит увидеть:

```python
    assert subsystems_under(box.archive) == {"vms": ["7"]} and st.units() == []   # watched, not recorded
    ...
    assert subsystems_under(box.archive) == {"vms": ["7"]}         # the resource's tree holds no footage at all
    ...
    assert st.coverage("7") == [(t0 + 600, t0 + 1200)]             # the footage, untouched: the ring decides for it
```

Платформа удаляет старые бакеты по своему сроку хранения (`Resource.retain`). Видео на её дереве нет, поэтому трогать ей нечего. Сколько видео помнит том, решает кольцо.

## Шаг 2 — Эпоха в имени потока

```python
def stream_name(unit, epoch: int, backfill: bool = False) -> str:
    return f"{unit}/e{int(epoch)}" + ("/backfill" if backfill else "")


def parse_stream(name: str) -> tuple[str, int, str] | None:
    """`(unit, epoch, source)` — `live` or `backfill` — or None for a stream that is not a recording's."""
```

У потока нет метаданных, кроме имени (урок 6, шаг 13). Поэтому всё, что регистратору нужно знать о потоке без чтения кадров, лежит в имени: чья это запись, под какой эпохой, откуда кадры.

Первая часть — **запись**, а не камера. `test_a_stream_is_named_by_its_recording_and_its_epoch` говорит об этом в комментарии:

```python
    # The first part is the RECORDING, and it comes back as a string: the grammar never knew that a recording
    # tended to be named after a camera, and `7-backup` parses exactly the same way.
```

У камеры бывает две записи, например основная и резервная (урок 26). Тогда потоки — `7/e3` и `7-backup/e1`, и грамматика не меняется ни на символ. Платформа знает единицу, подсистема знает, что единица — запись камеры. Имя потока ничего не знает о камерах.

`parse_stream` возвращает `None` для всего, что не похоже на поток записи: `"7"`, `"7/5"`, `"7/e5/x"`. Это нормальный ответ, а не ошибка: в томе могут лежать потоки, которые не курс писал, и читать их не наше дело.

**Что даёт эпоха в имени.** Процесс A завис, его сочли мёртвым, подняли B. B взял эпоху 4. Пока A не заметил своей смерти, он пишет — в `7/e3`. B пишет в `7/e4`. Кадры не смешиваются и не перезаписывают друг друга: это два потока одного тома.

Отсечение — сравнение чисел. Таймлайн сравнивает эпоху из имени потока с текущей эпохой записи:

```python
    def timeline(self, unit, t0: float, t1: float, current_epoch: int | None = None) -> list[dict]:
        """Spans overlapping `[t0, t1)`, each marked `fenced` when its epoch is older than the current one — how
        the page shows a zombie's footage, kept and told apart."""
        return [{"start": s.start, "end": s.end, "epoch": s.epoch, "source": s.source, "bytes": s.bytes,
                 "fenced": current_epoch is not None and s.epoch < current_epoch}
```

Ни базы, ни запроса, ни консультации с кем-либо: число в имени потока против числа в хранилище. `test_the_timeline_marks_a_fenced_epoch_and_spans_two_volumes` пишет зомби в `7/e3` поверх минут `7/e4` и получает `[(3, 0, 900, True), (4, 600, 1200, False)]`. `test_a_recording_started_twice_writes_two_streams_and_overwrites_nothing` делает то же через регистратор: старый приёмник пишет после перезапуска конвейера, и в томе остаются `1/e1` и `1/e2`.

**Ничего не удаляется.** Записи зомби остаются в томе и видны на таймлайне отсечёнными. Это настоящее видео настоящей камеры; его писал процесс, у которого в тот момент не было права. Удалить его — потерять то, что может понадобиться. Какая эпоха владеет минутой, которую писали обе, решает правило «старшая эпоха» — [урок 8](08-visibility-retention-timeline.md) и урок 20.

## Шаг 3 — Ещё два потока: дозапись и копия

Комментарий модуля называет оба:

> *Footage fetched into a gap is `<recording>/e<epoch>/backfill`: where it came from is in the name too — there is no manifest line to carry it. A keep's copy in an incidents volume is `<recording>/e0`: nobody's lease, so wherever the live footage still exists its own epoch owns those minutes (`RecWorker.keep_pass`)*

**`…/backfill`.** Кадры, скачанные с карты камеры в дыру записи, — наши: наш том, наша эпоха. Но откуда они пришли, тоже надо знать: дозапись не должна выдавать себя за живую запись. Других мест для этого знания нет, поэтому оно в имени. Как дыры находятся и заполняются — [урок 16](16-backfill-from-the-edge.md).

**`…/e0`.** Копия удержанного интервала в томе вида `incidents`. Эпоха 0 меньше любой настоящей. Поэтому там, где живая запись ещё есть, её эпоха владеет минутами, а копия отвечает только за то, что кольцо уже перезаписало. Удержания — [урок 18](18-what-the-archive-gives-up-first.md).

## Шаг 4 — Отрезок: из индекса каждый раз

```python
@dataclass(frozen=True)
class Span:
    unit: str             # the recording — `7`, or `7-cloud`: the operator's name
    epoch: int
    start: float          # unix seconds
    end: float
    bytes: int
    source: str = "live"  # `live` (written from the fan-out) or `backfill` (fetched into a gap — Lesson 16)

    @property
    def stream(self) -> str:
        return stream_name(self.unit, self.epoch, self.source == "backfill")
```

Комментарий модуля говорит главное об отрезке:

> *read from the engine every time, never kept beside it*

Индекс тома — единственный источник истины о том, что записано. Курс не держит рядом с томом ни списка, ни кэша. Любая копия индекса расходится с ним при первом же сбое между двумя записями, и тогда нужен код, который их сверяет. Нет копии — нечего сверять.

Время в `Span` — секунды Unix. Перевод из миллисекунд архива происходит в `spans` одним вызовом `unix_s` (урок 6, шаг 5), и остальной курс времени архива не видит.

## Шаг 5 — Где том: параметры, а не адрес с ключом

```python
# Where a volume is, as `obsd` opens it: PARAMETERS, never a URI with a key in it — a URI is printed, logged,
# published in heartbeats; the key travels separately (`access_secret`, sealed in the store, opened only by the
# process that mounts the volume: М10A Lesson 18).
def volume_params(url: str, secret: str = "") -> dict:
    if "://" not in url:
        return {"schema": "file", "path": url}           # a local volume's row names its directory
```

Адрес тома печатают на странице, пишут в лог, публикуют в heartbeat. Ключ в адресе оказался бы во всех трёх местах. Поэтому регистратор передаёт демону параметры, а ключ добавляет отдельно: `secret_key` открывает только процесс, который монтирует том. Демон, со своей стороны, узнаёт том по `schema://host/path` и никогда не по учётным данным (урок 6, шаг 12).

`file://` и голый путь — локальный том, `s3://<host>/<region>/<bucket>[/<path>]` — бакет. Всё остальное — `ValueError`, а значит `wrong` (шаг 6). Виды томов и кто какой держит — [урок 27](27-volumes.md).

## Шаг 6 — Отказ по виду

```python
class ArchiveError(Exception):
    """A volume that will not open or take writes, by KIND — the recorder answers each differently:

    wrong   only a person changes it: a path that is not a volume, no permission, a bucket that refuses the key.
            The volume is handed back
    away    a timeout, a network that is down, the daemon itself gone. Kept: it is back in a minute, and handing
            it back would reshuffle every recording on it for a link that returns
    busy    another writer holds it on this host (`ALREADY_LOCKED`) — a recorder of the same volume that has
            not let go yet, or one whose grace the daemon is still waiting out"""
```

Вид нужен потому, что ответы противоположны. Неверный том регистратор отдаёт: писать туда некому, пока человек не исправит. Недоступный том регистратор держит: связь вернётся через минуту, а отдача тома перетасовала бы все записи на нём. Занятый том тоже держит: писатель вот-вот освободится или вернётся к своему владельцу.

```python
WRONG = {"PERMISSION_DENIED", "NOT_A_VOLUME", "UNSUPPORTED_FORMAT", "READ_ONLY", "PATH_NOT_EMPTY",
         "INVALID_ARGUMENT", "PROTECTED_VOLUME", "INVALID_CIPHER_KEY"}


def classify(e: Exception) -> ArchiveError:
    if isinstance(e, ArchiveError):
        return e
    if isinstance(e, Unavailable):
        return ArchiveError("away", f"obsd is not answering: {e.detail}", e.name)
    if isinstance(e, ObsdError):
        if e.name == "ALREADY_LOCKED":
            return ArchiveError("busy", str(e), e.name)
        return ArchiveError("wrong" if e.name in WRONG else "away", str(e), e.name)
    if isinstance(e, ValueError):
        return ArchiveError("wrong", str(e))
    return ArchiveError("away", str(e))
```

`wrong` — закрытый список. Всё, чего в нём нет, считается `away`. Ошибиться в эту сторону дешевле: недоступный том регистратор попробует снова на следующем проходе, а ошибочно отданный том стоит перетасовки записей.

Одно исключение живёт не здесь, а в `RecWorker._write_into`, потому что требует знать вид тома:

```python
            # A DISK on this box that cannot be formatted or mounted — a file where the directory should be, a
            # path nobody may create — is not a link that comes back in a minute. The engine says it as an I/O or
            # a generic error, the same words a network volume uses for a network that is down, so the kind of
            # volume decides: on a box, wrong; at an address, away.
            if e.kind == "away" and e.name in ("IO_ERROR", "GENERIC_ERROR") and volumes.on_a_box(vol):
                e = ArchiveError("wrong", e.detail, e.name)
```

Движок ведёт себя так на живом демоне. `VOLUME_EXISTS` отвечает «есть» для пути под обычным файлом, и монтирование потом падает с `GENERIC_ERROR`. Путь, который нельзя создать, роняет форматирование с `IO_ERROR`. Те же слова сетевой том говорит, когда сеть лежит. Различает их не статус, а вид тома. `test_a_volume_held_and_unwritable_is_not_served` объявляет том по пути, где вместо каталога лежит файл, и регистратор отдаёт его, раз есть куда идти.

Как регистратор отвечает на каждый вид — проходы, аренда тома, `REFUSED_FOR` — [урок 10](10-recworker.md).

## Шаг 7 — Открыть том

```python
    # Opening is the only honest test: a row can name a path that does not exist, a mount that is gone or a
    # bucket nobody can reach. A volume that is not there yet is FORMATTED — at its quota, which is the size of
    # the ring — and then mounted for writing under `owner`.
    def open(self, write: bool = True) -> "Archive":
        try:
            vol = self._open_volume()
            if not vol.exists():
                if not self.quota:
                    raise ArchiveError("wrong", f"{self.name}: no volume there and no quota to format one with")
                vol.format(self.quota, max_block=self.block, optimal_read=self.read, label=self.name)
                self.formatted = True
            if write and self.writer is None:
                self.writer = vol.mount_rw(self.owner)
                self.reattached = self.writer.reattached
        except (ObsdError, ValueError) as e:
            raise classify(e) from None
        return self
```

**Открытие — единственная честная проверка.** Строка тома может назвать что угодно. Пока демон не открыл том, ничего о нём не известно.

**Нового тома нет — его форматируют по квоте.** Квота — размер кольца, и задать его можно только сейчас. Нет квоты — нечем форматировать, и это `wrong`: исправит только человек. Блок и размер чтения берутся из `BLOCK, READ = 8 << 20, 1 << 20` — блок должен вмещать размер чтения плюс одну группу кадров (урок 6, шаг 10).

**Писатель монтируется под владельцем.** Регистратор передаёт `rec:<том>`, и докстрока класса объясняет зачем:

> *`owner` is what the daemon remembers a writer by — the recorder passes `rec:<volume>`, which the platform's hold makes unique — and what gets a vanished writer back.*

Два флага говорят, что произошло: `formatted` — том был новым, `reattached` — демон вернул писателя, которого оставил исчезнувший процесс (шаг 12). Читателям писатель не нужен: консоль и другие открывают том с `open(write=False)`.

`test_a_recorder_with_nothing_declared_formats_its_servers_volume_and_records_into_it`: ничего не объявлено, регистратор форматирует том своего сервера — `volume` рядом с деревом ресурса, `file:///data/volume` возле `/data/archive` (урок 10), — и пишет в него поток `1/e<эпоха>`.

## Шаг 8 — Положить кадр, закончить поток, изменить размер

```python
    def put(self, unit, epoch: int, sample: Sample, backfill: bool = False) -> str:
        """One sample into the recording's stream: `OK`, or `SEQUENCE_LOST` (taken — an earlier sequence was
        lost). Raises `ObsdError` for a sample NOT taken — the caller skips to the next key frame — and
        `Unavailable` when this volume is not open for writing any more (closed, or the engine went away)."""
        if self.writer is None:
            raise Unavailable("PUT_MEDIA", f"{self.name} is not open for writing")
        return self.writer.put(stream_name(unit, epoch, backfill), sample)

    def finish(self, unit, epoch: int, backfill: bool = False) -> bool:
        return self.writer.finish(stream_name(unit, epoch, backfill)) if self.writer is not None else False
```

`put` — имя потока и вызов писателя. Граница «взят — не взят» из урока 6 проходит сквозь него без изменений: статус — кадр на томе, исключение — нет. Закрытый том (`writer is None`) — не отказ кадра, а `Unavailable`: писать больше некуда, и тот, кто пишет, должен узнать это как «движка нет», а не как «пропусти до ключевого» (шаг 13).

```python
    def resize(self, quota: int) -> None:
        """A new quota is a new size of the ring, at once and without stopping: shrinking frees the oldest."""
```

Новая квота — новый размер кольца, сразу и без остановки записи. `RecWorker._write_into` зовёт `resize`, когда квота в строке тома изменилась, а писатель уже открыт.

## Шаг 9 — Сделать видимым, спросить свежего

Читатель видит только закрытые блоки, и только те, что были закрыты, когда он смонтирован (урок 6, шаг 8). Из этого правила — два метода.

```python
    def seal(self) -> None:
        """Close the writer and take it again: its last block is closed, and what was written is readable. What
        a recorder does when the minutes it just wrote must be an answer now — a copied range, a stop."""
        if self.writer is not None:
            self.writer.close()
            self.writer = self._open_volume().mount_rw(self.owner)
```

`flush` блок не закрывает. Закрывают его заполнение, период сброса после конца последовательности (урок 6, шаг 8) или закрытие писателя. Периоды задаёт `_configure`, вызванный после каждого `mount_rw`: `sequenceFlushPeriodMs` и `blockFlushPeriodSec` — числа продукта, 10 000 и 5, из окружения регистратора (`SEQUENCE_FLUSH_MS`, `BLOCK_FLUSH_S`); ноль оставляет движку его собственные (минута на блок). Отказ `WRITER_CONFIGURE` — предупреждение в лог, не ошибка: писатель остаётся на своих настройках, и запись идёт. Но и пять секунд — не «сейчас». Поэтому, когда записанное должно стать ответом сейчас, регистратор закрывает писателя и берёт его снова. `test_written_is_readable_once_its_block_is_closed`:

```python
    footage(st, "7", 3, t, t + 600, seal=False)
    assert st.coverage("7") == []                                  # written, in an open block
    st.seal()
    assert st.coverage("7") == [(t, t + 600)]
```

```python
    def reader(self):
        if self._reader is not None:
            try:
                self._reader.close()
            except ObsdError:
                pass
        try:
            self._reader = self._open_volume().mount_ro()
        except ObsdError as e:
            raise classify(e) from None
        return self._reader
```

**Свежий читатель на каждый вопрос.** Читатель, смонтированный минуту назад, держит картину минутной давности и не увидит блоков, закрытых после. Старый читатель закрывается, новый монтируется. `spans` берёт одного читателя на один вопрос, а вызывающий, который спрашивает больше, передаёт своего: `spans(..., reader=r)`.

`units()` — список записей тома: имена потоков, разобранные `parse_stream`. Тот же принцип, что у отрезка: никакого списка рядом, том сам знает, что в нём.

Что из этого следует для плана регистратора — дыры считаются по видимому, только что скачанное помнится как «в пути», таймлайн спрашивается окнами — [урок 8](08-visibility-retention-timeline.md).

## Шаг 10 — `RecSink`: три исхода кадра

```python
# What a recording's pipeline writes into: the volume's writer, under this recording's name and epoch. A
# sample the engine did not take raises, and the pipeline skips to the next key frame. A daemon that stopped
# answering is not an answer about the sample: the recorder is told, and remounts on its next pass (feedback CF).
#
# `store` is the recorder's CURRENT volume — a callable, asked on every sample — not the one open when the
# pipeline started. A remount replaces the `Archive`; a sink that kept the old one would write into a closed
# volume for as long as the pipeline ran, and nothing restarts a pipeline for a remount. Asked each time, the
# next key frame after a remount opens a sequence in the new writer, and the recording goes on.
class RecSink:
    def __init__(self, store, unit, epoch: int, on_lost=None, backfill: bool = False, on_wrong=None):
        self.store_of = store if callable(store) else (lambda: store)
        self.unit, self.epoch, self.on_lost, self.backfill = str(unit), int(epoch), on_lost, backfill
        self.on_wrong = on_wrong                     # the volume refuses writes for good: told once per sample, acted on per pass
        self.taken = self.refused = 0

    def put(self, sample: Sample) -> str:
        try:
            store = self.store_of()
            if store is None:
                raise Unavailable("PUT_MEDIA", "no volume open")
            st = store.put(self.unit, self.epoch, sample, self.backfill)
            self.taken += 1
            return st
        except Unavailable:
            if self.on_lost is not None:
                self.on_lost()
            raise
        except ObsdError as e:
            self.refused += 1
            if e.name == "WRITER_STOPPED" and self.on_lost is not None:
                self.on_lost()                       # the engine stopped this writer: a new one, on the next pass
            elif self.on_wrong is not None and classify(e).kind == "wrong":
                self.on_wrong(e)
            raise
```

**Приёмник спрашивает текущий том на каждом кадре.** `store` — не `Archive`, а функция, которая возвращает том, открытый у регистратора сейчас. Перемонтирование (шаг 13) заменяет `Archive` целиком. Приёмник, запомнивший том на старте конвейера, писал бы в закрытый том, пока конвейер жив, а перемонтирование конвейер не перезапускает. С функцией первый ключевой кадр после перемонтирования открывает последовательность в новом писателе, и запись идёт дальше. Нет тома вовсе — это тоже `Unavailable`.

Приёмник получает регистратор в `enrich`, вместе с эпохой записи:

```python
        # The sink: this volume's writer, as the stream `<recording>/e<epoch>`. The epoch is in the stream's
        # NAME — a fenced writer and its successor write two streams, and nothing is overwritten.
        out = dict(cam, source=src[1], source_server=src[0], via="shm" if src[1].startswith("shm://") else "rtsp",
                   sink=RecSink(lambda: self.store, cam["id"], cam.get("epoch", 0), on_lost=self._lost_engine,
                                on_wrong=self._volume_refuses))
```

Три исхода.

**Взят.** `OK` или `SEQUENCE_LOST`. Оба означают, что этот кадр на томе. `SEQUENCE_LOST` сообщает о потере в прошлом потока, и пропускать ничего не нужно.

**Отвергнут.** `ObsdError`, и приёмник пробрасывает его конвейеру, а тот пропускает до ключевого кадра (шаг 11). Отказ кадра — обычное дело: `SEQUENCE_NEEDS_KEY_SAMPLE` после обрезанной группы, `SEQUENCE_TOO_LARGE`. Один отказ — особый: `WRITER_STOPPED` значит, что движок остановил самого писателя, и этот писатель больше ничего не возьмёт. Пропускать до ключевого бесполезно — следующий ключевой получит тот же отказ. Поэтому приёмник зовёт `on_lost`, как при пропавшем демоне, и на следующем проходе регистратор открывает нового писателя. Если отказ — `wrong` (`PERMISSION_DENIED`, `READ_ONLY`), том больше не возьмёт ничего. Приёмник говорит об этом регистратору через `on_wrong`, и на следующем проходе регистратор отдаёт том. Говорит здесь, на потоке конвейера, а действует там, в проходе. `test_an_archive_that_refuses_writes_mid_run_is_handed_back` доказывает и отдачу, и паузу `REFUSED_FOR`, без которой регистратор взял бы тот же сломанный том обратно.

**Движка нет.** `Unavailable` — не ответ о кадре (урок 6, шаг 4). Приёмник зовёт `on_lost`, это `RecWorker._lost_engine`, и пробрасывает исключение — для конвейера это тоже «не взят». Шаг 13 разбирает, что дальше.

```python
    def finish(self) -> None:
        store = self.store_of()
        if store is None:
            return
        try:
            store.finish(self.unit, self.epoch, self.backfill)
        except ObsdError:
            pass
```

`finish` глотает ошибку и молча возвращается, если тома нет. Его зовут при остановке конвейера, и остановка не должна падать из-за тома, который уже ушёл.

## Шаг 11 — `appsink`: кадр, время захвата, пропуск до ключевого

В конвейере регистратора кадры выходят из `appsink`, и колбэк кладёт каждый в приёмник. Строку конвейера целиком собирает [урок 9](09-actuators-and-the-fan-out.md). Здесь — только колбэк из `GstRecActuator._before_play`:

```python
    # A pipeline that starts on hold: block the ring's source pad before the first buffer can pass. And on every
    # recorder pipeline: count what reaches the sink — the writer watch's "offered" (Lesson 10) — and hand each
    # access unit to the volume's writer, with the time it was CAPTURED: the pipeline's running time turned into
    # the wall clock, so a released ring lands thirty seconds back where it belongs, not now. A sample the engine
    # refused makes the sink skip to the next key frame — the engine opens a sequence on nothing else.
```

```python
            skipping = {"until_key": False}

            def on_sample(appsink, cid=cam["id"]):
                smp = appsink.emit("pull-sample")
                buf = smp.get_buffer()
                data = buf.extract_dup(0, buf.get_size())
                self.offered_bytes[cid] += len(data)
                key = not buf.has_flags(Gst.BufferFlags.DELTA_UNIT)
                clock = p.get_clock()
                running = (clock.get_time() - p.get_base_time()) if clock is not None else 0
                ago = max(0, running - buf.pts) / Gst.SECOND if buf.pts != Gst.CLOCK_TIME_NONE else 0.0
                begin = _time.time() - ago
                dur = buf.duration / Gst.SECOND if buf.duration != Gst.CLOCK_TIME_NONE else 0.04
                if skipping["until_key"] and not key:
                    return Gst.FlowReturn.OK
                try:
                    writer.put(video(archive_ms(begin), archive_ms(begin + dur), data, key))
                    skipping["until_key"] = False
                except ObsdError:
                    skipping["until_key"] = True          # refused: the rest of this group is lost, the next key opens anew
                return Gst.FlowReturn.OK
```

**Время — когда кадр сняли, а не когда он дошёл.** `running - buf.pts` — сколько кадр шёл по конвейеру. Обычно это доли секунды. Но резервная запись держит в памяти кольцо последних тридцати секунд (урок 26), и при его открытии кадры выходят с опозданием в полминуты. Время прихода положило бы их «сейчас», время захвата кладёт их туда, где они были сняты.

**Отвергнутый кадр — пропуск до ключевого.** После отказа движок не откроет последовательность ни на чём, кроме ключевого кадра (урок 6, шаг 9). Слать ему остаток группы — получить столько же отказов. Колбэк ставит `until_key` и молча пропускает зависимые кадры, а первый ключевой снова идёт в писателя.

**Колбэк всегда возвращает `Gst.FlowReturn.OK`.** Отвергнутый кадр — потеря одной группы, а не причина останавливать конвейер. Конвейер, остановленный из-за тома, потерял бы всё, что идёт следом.

`offered_bytes` считает, что дошло до приёмника. Сторож писателя сравнивает это с `totalWritten` тома и замечает писателя, который берёт меньше, чем ему дают (урок 10).

При остановке и перезапуске записи актуатор закрывает открытую последовательность:

```python
        if verb in ("stop", "restart") and cam["id"] in getattr(self, "sinks", {}):
            # The open sequence closed: what was taken is kept — and a restart (back on hold, a new source) must not
            # let the next frames continue it after a gap: a hole inside a sequence is drawn as footage.
            self.sinks.pop(cam["id"]).finish()
```

Перезапуск — тоже конец последовательности. Конвейер вернулся на удержание или сменил источник, и между последним кадром до перезапуска и первым после — промежуток. Если бы следующие кадры продолжили ту же последовательность, дыра оказалась бы внутри неё, и таймлайн нарисовал бы эту дыру как запись.

В тестах камеру заменяет `FakeActuator.feed`. Он шлёт в приёмник кадры `fake_samples` с ключевым каждые две секунды, считает статусы и в конце зовёт `finish`. Поэтому `r.actuator.feed("1", t - 120, t)` возвращает `{"OK": 120}`.

## Шаг 12 — Убитый регистратор

Регистратор убит `kill -9` посреди записи. Что на томе?

`test_a_recorder_killed_and_started_again_picks_up_the_writer_it_left`:

```python
    """No stale lock to wait out and nothing to recover: the daemon kept the writer DETACHED, and the recorder
    started again under the same slot names the same owner, `rec:<volume>`."""
    ...
    r.actuator.feed("1", box.wall() - 60, box.wall())
    r.session.vanish()                                                 # kill -9: no BYE, no close
    time.sleep(OBSD_LINGER_MS / 1000 + 0.3)                            # the daemon notices the session is gone
    box.wall.advance(5)
    again = recorder(box)
    again.lease_pass()
    assert again.store is not None and again.store.reattached and again.store.formatted is False
    again.store.seal()
    assert again.our_coverage("1") == [(box.wall() - 65, box.wall() - 5)]   # nothing the dead one wrote was lost
```

Сессия убитого процесса исчезла без `BYE`. Демон закрыл её открытые последовательности, как сделал бы `FINISH_MEDIA`, и оставил писателя отсоединённым (урок 6, шаг 12). Новый процесс под тем же слотом открывает тот же том под тем же владельцем `rec:<том>` и получает того же писателя: `reattached`, не `formatted`. Минута, записанная убитым, на месте целиком.

Сравните с регистратором, который сам пишет видео файлами-сегментами. Убийство теряет у него открытый сегмент: файл, у которого не дописан индекс. Чем длиннее сегмент, тем больше потеря, и длину сегмента приходится выбирать между потерей при убийстве и числом файлов. Здесь выбирать нечего. Последовательности держит демон, и при исчезновении сессии он их закрывает. Теряется только то, что не успело дойти до сокета, — кадры в памяти самого регистратора.

`test_a_restart_takes_its_volumes_writer_back_and_never_opens_the_local_one` повторяет это на объявленном томе. Новый процесс сначала смотрит на тома, а потом открывает: берёт ту же аренду, называет того же владельца и получает писателя назад. Том сервера по умолчанию при этом не форматируется вовсе.

А если регистратор не вернулся? Аренда тома истекает за 45 секунд, следующий регистратор берёт том под тем же `rec:<том>` и получает писателя — отсрочка в `obsd.service` девяносто секунд, дольше аренды. Отсрочка истекла, а никто не пришёл — демон закрывает писателя чисто, и взятое остаётся на томе (`test_after_the_grace_the_volume_is_clean_for_anybody`).

**Аккуратная остановка** — другая история, и в ней важен порядок:

```python
    # The ORDER is the point. A released place is taken at once, and whoever takes it mounts the volume for
    # writing. So the hold goes LAST: the pipelines are stopped, the last heartbeat said so, the slot is
    # released — and then the writer is closed, its flush putting the last minutes on the volume, and only then
    # is the hold let go. Released together with the slot, the next recorder would find our writer still there.
```

Сначала писатель закрывается — его сброс кладёт последние минуты на том, — и только потом аренда отпускается. `Archive.close` держит тот же порядок внутри себя: сначала читатель и писатель, потом том. На закрытие юнит даёт `StopTimeout=40`: протокол разрешает `WRITER_CLOSE` до тридцати секунд. `test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it` проверяет порядок `["close", "release"]` и то, что следующий регистратор монтирует чистый том (`not b.store.reattached`) и видит последние минуты. Аренды томов, спейры и передача тома — [урок 10](10-recworker.md).

## Шаг 13 — Демон пропал

`RecSink` получил `Unavailable` и позвал `_lost_engine`:

```python
    # A sink found the daemon gone. Nothing is torn down here, on the pipeline's thread: the next pass closes
    # what is left of the store and opens it again (`volume_pass`) — at once, not after the writer watch's ten
    # minutes, because there is nothing to wait for: the engine is not there, a new session is (feedback CF).
    def _lost_engine(self) -> None:
        if not self.engine_lost:
            log.warning("%s: obsd stopped answering — remounting %s on the next pass", self.name, self.volume)
        self.engine_lost = True
```

На потоке конвейера ничего не разбирается: там только флаг. Следующий проход видит `engine_lost`, закрывает остатки хранилища и открывает том заново. Сразу, а не через десять минут сторожа писателя: ждать нечего. Конвейеры при этом не останавливаются: их приёмники спрашивают текущий том (шаг 10) и со следующего ключевого кадра пишут в нового писателя. `test_rec_volume.py::test_a_recording_goes_on_into_the_volume_opened_again_after_the_engine_was_lost` проверяет оба пути. Минута записана, `_lost_engine` и проход перемонтировали том — у старого `Archive` писателя нет, а тот же конвейер пишет следующую минуту в новый, и видна вся запись целиком: `[(t - 120, t)]`:

```python
    first = r.store
    r._lost_engine(); r.lease_pass()                                   # the next pass remounts
    assert r.store is not first and first.writer is None
    assert r.actuator.feed("1", t - 60, t) == {"OK": 60}               # the same pipeline, into the new writer
```

Во второй половине теста писатель отвечает `WRITER_STOPPED`, и `engine_lost` снова поднят: новый писатель — на следующем проходе.

Пока демона нет, том остаётся местом регистратора. Это `away`, а не `wrong`: том не отдаётся, ёмкость не обнуляется. `test_a_recorder_with_no_daemon_says_the_archive_is_away_and_keeps_its_place` проверяет это на сокете, где никто не слушает. `test_a_daemon_that_is_not_there_does_not_stop_the_recorder` гоняет минуту цикла без демона: аренды продлеваются, heartbeat идёт и говорит `archive_failure: away`. `test_when_the_daemon_answers_again_the_volume_opens_and_the_outage_is_over` — обратный конец: демон вернулся, следующий проход открыл том, ошибка очистилась.

## Результат

Что лежит где после дня работы одной камеры с одним перезапуском конвейера и одной дырой, заполненной с карты:

```
том srv-1, писатель rec:srv-1
  7/e3              живая запись до перезапуска — и минута зомби после него:
                    на таймлайне отсечена, в томе цела
  7/e4              живая запись после перезапуска
  7/e4/backfill     дыра, скачанная с карты камеры
ресурс srv-1
  vms/7/e<n>/<start>Z.events.jsonl    события держателя камеры, под его эпохой
```

Убейте регистратор посреди записи — новый процесс под тем же слотом получит того же писателя, и минуты до убийства на месте. Остановите аккуратно — писатель закроется со сбросом, и только потом том получит следующий.

## Что может пойти не так

- **Эпоха рядом с потоком, а не в имени.** У потока нет другого места для метаданных: зомби и выживший пишут в один поток, и кадры смешиваются.
- **Удалять отсечённые потоки.** Это настоящее видео настоящей камеры. Отметьте и оставьте.
- **Хранить список записей рядом с томом.** Он разойдётся с индексом при первом сбое, и понадобится код, который их сверяет.
- **Ключ в адресе тома.** Секрет окажется на странице, в логе и в heartbeat.
- **Считать неизвестный статус `wrong`.** Сетевой том, у которого на минуту пропала сеть, отдаётся, и записи на нём перетасовываются.
- **Статус вместо вида тома для локального диска.** `IO_ERROR` от диска, на котором вместо каталога файл, считается `away`, и регистратор держит том, в который никогда не запишет.
- **Монтировать писателя без владельца.** Перезапущенный регистратор получает `ALREADY_LOCKED` и ждёт отсрочку вместо того, чтобы забрать своего писателя.
- **Переиспользовать старого читателя.** Он не видит блоков, закрытых после его монтирования, и регистратор считает дырой то, что уже записано.
- **Слать движку остаток группы после отказа.** Каждый кадр будет отвергнут, и лог заполнится отказами без пользы.
- **Останавливать конвейер на отвергнутом кадре.** Потеря одной группы превращается в потерю всего, что идёт следом.
- **Время прихода вместо времени захвата.** Открытое кольцо резервной записи ляжет на полминуты позже, чем было снято.
- **Отпустить аренду тома раньше, чем закрыт писатель.** Следующий регистратор найдёт в томе чужого писателя.
- **Приёмник с томом, запомненным на старте.** После перемонтирования конвейер пишет в закрытый том, пока его не перезапустят, а перемонтирование его не перезапускает.
- **`WRITER_STOPPED` как обычный отказ кадра.** Приёмник пропускает до ключевого, ключевой получает тот же отказ, и запись стоит, пока кто-то не перезапустит писателя.

## Итог

- Видео и события — в разных местах и у разных писателей. Видео — потоки в томе, их пишет регистратор. События — бакеты на ресурсе, их пишет держатель камеры.
- Поток — `<запись>/e<эпоха>`. Эпоха в имени, потому что у потока нет других метаданных. Записи зомби отделены одним сравнением чисел и не удаляются.
- `…/backfill` говорит, откуда кадры, а `…/e0` — копия удержания, уступающая любой живой эпохе.
- Отрезок читается из индекса каждый раз. Рядом с томом не лежит ничего, что могло бы с ним разойтись.
- Отказ тома имеет вид: `wrong` отдают, `away` и `busy` держат. Для локального диска вид тома решает больше, чем статус.
- Открытие — единственная честная проверка. Новый том форматируется по квоте, писатель монтируется под владельцем `rec:<том>`.
- Записанное становится видимым, когда закрыт блок. `seal` закрывает писателя и берёт его снова; каждый вопрос задаётся свежему читателю.
- Отвергнутый кадр — пропуск до ключевого, без остановки конвейера. Пропавший демон и `WRITER_STOPPED` — перемонтирование на следующем проходе, а приёмник спрашивает текущий том на каждом кадре и продолжает запись в новый.
- Убитый регистратор не теряет записанного: демон закрывает последовательности и отдаёт писателя тому же владельцу. Аккуратная остановка закрывает писателя раньше, чем отпускает том.

## Упражнения

1. Положите эпоху в метку тома вместо имени потока. Смоделируйте зомби, как в `test_the_timeline_marks_a_fenced_epoch_and_spans_two_volumes`, и опишите, как теперь отличить его кадры.
2. Добавьте `"NO_SPACE"` в `WRONG`. Что станет с регистратором, если сетевое хранилище на минуту переполнится?
3. Уберите исключение для локального диска из `_write_into` и запустите `test_a_volume_held_and_unwritable_is_not_served`. Что сломалось и почему?
4. Монтируйте писателя с `owner=""`. Запустите `test_a_recorder_killed_and_started_again_picks_up_the_writer_it_left` и назовите вид отказа, который получил новый процесс.
5. Сделайте `Archive.reader` ленивым: монтировать один раз и переиспользовать. Найдите тест, который это ловит.
6. Уберите `until_key` из колбэка `appsink`. Сколько отказов движок вернёт на одну обрезанную группу из двадцати пяти кадров?
7. Поменяйте местами `_close_store` и `release_hold` в `after_stop`. Запустите `test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it` и опишите, что увидел следующий регистратор.
8. Убейте регистратор, подождите дольше отсрочки демона и запустите новый. Что на томе и чем это отличается от случая внутри отсрочки?

## Что дальше

Кадры ложатся в поток, эпоха в имени, отказы разобраны по видам. Но читатель видит не всё записанное, срок хранения больше ничего не удаляет, а на экране нужен таймлайн, где каждая минута принадлежит одной эпохе.

[**Урок 8**](08-visibility-retention-timeline.md) разбирает видимость, срок хранения как потолок того, что показывают двери, и таймлайн из индекса тома.

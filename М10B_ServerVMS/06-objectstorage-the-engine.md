# Урок 6 — ObjectStorage: движок архива и клиент к нему

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `w2cplatform/obsd.py` — клиент протокола `obsd` версии 1: кадр, `Session` (`HELLO`/`BYE`, переподключение под тем же токеном, `vanish`, таймаут), `Volume`, `Writer`, `Reader`, `Sample`, `video()`, `archive_ms`/`unix_s`, `ObsdError`/`Unavailable`; и в `tests/conftest.py` — `ObsdDaemon`, `obsd_session`, `obsd_volume`: настоящий демон на собственном сокете тестов.
**Время:** ~90 минут.

## Зачем этот урок

Курс больше не пишет архив сам. Видео пишет ObjectStorage — движок хранения продукта, библиотека на C++. Библиотека живёт в отдельном процессе `obsd`, по одному на хост. Регистратор и все, кто читает архив, говорят с ним через unix-сокет.

У урока две половины.

**Первая — клиент.** Протокол описан в README демона (`ObjectStorage/mmss/ObjectStorage/obsd/README.md`). Модуль `w2cplatform/obsd.py` — этот README на Python, и ничего больше. Вы разберёте кадр, сессию, дескрипторы, запись кадра видео `SMPL`, время архива и коды статуса. И два решения клиента, которые потом держат регистратор живым: обрыв соединения повторяется под тем же токеном, кроме записи, которую демон мог уже выполнить, а молчание демона не повторяется.

**Вторая — свойства движка.** Клиент их не содержит, и комментарий в начале модуля говорит это прямо:

> *What the engine IS — a volume that is a ring, blocks fixed at format time, sequences that open on a key frame, a reader that sees only closed blocks — is not here.*

Эти свойства принадлежат движку. Курс их не моделирует, а проверяет на живом демоне в `tests/test_obsd.py`. Каждое правило регистратора в уроках 7, 8, 10 и 18 выводится из одного из них. Поэтому здесь каждое свойство — отдельный шаг со своим тестом.

> **Проверка без железа.** Весь урок идёт против живого `obsd`: тесты запускают настоящий демон на своём сокете, тома лежат во временных каталогах. GStreamer не нужен ни одной строке урока. Без `obsd` тесты архива не проходят молча, а падают с подсказкой, как его собрать: `ObjectStorage/standalone-build/build.sh <out>` и `OBSD_BIN=<out>/build/obsd`.

## Что нужно знать заранее

- **Урок 4** — эпоха на единицу и почему видео пишет регистратор, а не держатель камеры.
- **М10A, урок 6** — эпоха и аренда: сколько живёт аренда и почему ни один вызов не должен держать поток, который её продлевает.
- **Урок 5** — ключевой кадр и группа кадров (GOP, *group of pictures* — ключевой кадр и зависящие от него кадры до следующего ключевого). Достаточно знать, что декодер начинает только с ключевого кадра.

## Чему вы научитесь

1. Объяснять, почему движок архива — процесс на хосте, а не библиотека в регистраторе.
2. Читать и писать кадр протокола: заголовок, JSON и двоичный хвост.
3. Отличать сессию от соединения и знать, что демон делает с писателем исчезнувшей сессии.
4. Различать обрыв и молчание и отвечать на них по-разному.
5. Переводить время между Unix и архивом и кодировать кадр видео записью `SMPL`.
6. Запускать настоящий демон в тестах так, чтобы он не трогал демон машины.
7. Называть шесть свойств движка и тест, который доказывает каждое.

---

## Шаг 1 — Процесс, а не библиотека

Комментарий в начале `w2cplatform/obsd.py` называет причины. Это причины продукта (обратная связь CF):

> *a fault in the engine takes down `obsd`, not every recorder on the box; the recorder's own memory is all the recorder's; and the writer — with the volume's lock — lives in the daemon, so a recorder that dies and comes back picks up the writer it left instead of waiting out a stale lock.*

Разберём три довода по одному.

**Сбой движка роняет один процесс.** Библиотека на C++ внутри регистратора разделяет с ним адресное пространство. Ошибка памяти в движке убила бы регистратор, а на коробке с тремя дисками — все три регистратора сразу. Отдельный процесс падает один, и супервизор его поднимает.

**Память регистратора принадлежит регистратору.** README демона говорит это о регистраторе продукта на Go: его `GOMEMLIMIT` видит всю кучу. Библиотека, выделяющая память мимо рантайма, этот предел обходит.

**Писатель живёт в демоне.** Это главный довод, и курс к нему вернётся в шаге 12 и в уроке 7. Блокировка тома на запись принадлежит процессу демона, а не регистратору. Регистратор умер — блокировка не осиротела, её держит живой процесс. Регистратор вернулся — он забирает своего писателя обратно, без ожидания чужой блокировки и без восстановления тома.

Демон один на хост, и юнит `deploy/obsd.service` объясняет почему:

> *One per host — it keeps one writer per volume, and that rule means something only if every recorder on the box asks the same daemon.*

Запускает демон супервизор ОС (systemd, launchd, задание Nomad типа `system`), а не его клиенты. Клиент, не нашедший демон, не пытается его поднять. Он говорит «движок недоступен» и спрашивает снова на следующем проходе (шаг 4).

## Шаг 2 — Кадр

Каждое сообщение в обе стороны — один кадр. Комментарий модуля держит формат в одной строке:

```
#   frame      u32 len | u32 id | u16 op | u16 flags | i32 status | u32 jsonLen | json | tail   (little-endian)
```

```python
HEADER = struct.Struct("<IHHiI")          # id, op, flags, status, jsonLen — after the u32 length
REPLY = 1
```

`len` считает байты после себя. `id` выбирает клиент, и ответ несёт `id` своего запроса. `flags` бит 0 — `REPLY`. `status` в запросе равен нулю, в ответе ноль означает успех. Дальше JSON-объект длины `jsonLen` и хвост — двоичные данные операции до конца кадра.

Управляющая часть едет в JSON, кадр видео — в хвосте. Так кадр видео не перекодируется в текст, а поля операции читаются без отдельного двоичного формата на каждую из них. `PUT_MEDIA` и `FINISH_MEDIA` вовсе не несут JSON, только хвост:

```python
def _tail(writer: int, stream: str, sample: Sample | None = None) -> bytes:
    s = stream.encode()
    return struct.pack("<QH", writer, len(s)) + s + (sample.encode() if sample is not None else b"")
```

Писатель, длина имени потока, имя потока и одна запись кадра. Это самая частая операция протокола: двадцать пять раз в секунду на каждую запись.

Ответы приходят не обязательно по порядку, и клиент сопоставляет их по `id`. Клиент курса шлёт один запрос за раз, но всё равно проверяет `id`:

```python
            got, _op, flags, status, jl = HEADER.unpack_from(frame)
            if got != rid:
                continue                                  # a reply to a request we stopped waiting for
```

Ответ с ненулевым статусом превращается в исключение, и его JSON — `{detail}`, слова самого движка о том, что пошло не так:

```python
            if status != 0:
                raise ObsdError(status, op, str(reply.get("detail", "")))
```

## Шаг 3 — Сессия и дескрипторы

Первый кадр на каждом соединении — `HELLO`:

```python
        self.server = self._exchange("HELLO", {"proto": [PROTO, PROTO], "client": self.client, "pid": os.getpid(),
                                               "session": self.token, "logLevel": self.log_level})[0]
```

`session` — токен, который выбрал клиент: `f"{client}-{os.getpid()}-{uuid.uuid4().hex[:8]}"`, если его не передали. **Сессия и соединение — разные вещи.** Дескрипторы принадлежат сессии. Соединение — только провод, по которому сессия говорит. README разрешает несколько соединений в одной сессии: клиент продукта на Go даёт каждому писателю своё соединение, чтобы большое чтение не задерживало кадры записи.

Сессия кончается двумя способами, и разница между ними — суть следующих уроков:

- **`BYE`** — всё, чем владеет сессия, закрывается чисто, писатели тоже, и только потом приходит ответ;
- **исчезновение** — последнее соединение пропало и не вернулось за `OBSD_SESSION_LINGER_MS` (по умолчанию 3000 мс). Читатели и тома освобождаются, а писатели становятся *отсоединёнными* (шаг 12).

У клиента для этого два метода:

```python
    def bye(self) -> None:
        """End the session cleanly: every handle closed, writers included, before the reply."""

    def vanish(self) -> None:
        """Drop the connection WITHOUT `BYE` — what a process that dies does. Its writers are detached and wait."""
```

`vanish` в работающем коде не нужен. Он нужен тестам: так выглядит `kill -9` со стороны демона, и тест может убить регистратор, не убивая процесс тестов.

**Дескриптор** — `u64`, старший байт которого — вид: 1 том, 2 читатель, 3 писатель. Остальное — счётчик, который не повторяется. Дескриптор не того вида получает `WRONG_HANDLE_KIND`, чужой или закрытый — `UNKNOWN_HANDLE`. Писатель держит свой том живым, поэтому закрыть том раньше писателя безвредно.

## Шаг 4 — Обрыв и молчание

`Session.call` — двадцать строк, и в них два разных ответа на два разных отказа:

```python
    def call(self, op: str, js: dict | None = None, tail: bytes = b"", long: bool = False) -> tuple[dict, bytes]:
        with self._lock:
            for attempt in (0, 1):
                self._sent = None
                try:
                    if self._sock is None:
                        self._connect()
                    self._sock.settimeout(self.long_timeout if long else self.timeout)
                    return self._exchange(op, js, tail)
                except ObsdError:
                    raise
                except socket.timeout:
                    self._drop()
                    raise Unavailable(op, f"no answer in {self.long_timeout if long else self.timeout:g} s") from None
                except (OSError, ConnectionError) as e:
                    self._drop()
                    if attempt or (self._sent == op and op in NOT_RESENT):
                        raise Unavailable(op, str(e)) from None
        raise AssertionError("unreachable")
```

**Ответ с ошибкой — это ответ.** `ObsdError` уходит наверх сразу: движок сказал своё слово о томе или кадре, и спрашивать снова незачем.

**Обрыв соединения повторяется один раз, под тем же токеном.** Соединение порвалось — клиент открывает новое, шлёт `HELLO` с тем же `session` и повторяет запрос. Демон держит сессию без соединения `OBSD_SESSION_LINGER_MS`, с дескрипторами и писателями. Значит, переподключение возвращает ту же сессию, и дескриптор писателя всё ещё действителен. Не удалось и со второй попытки — демона нет, и это `Unavailable`.

**Но не всякий запрос можно послать дважды.** Соединение могло порваться уже после того, как запрос ушёл. Тогда демон, возможно, его выполнил, и ответ просто не дошёл. Для чтения это безвредно: тот же вопрос — тот же ответ. Для записи нет: повторный кадр записан дважды, повторный формат форматирует том ещё раз. Поэтому `_exchange` запоминает, какой запрос ушёл на этой попытке (`self._sent = op` сразу после `sendall`), а список того, что не повторяется, — константа модуля:

```python
# What is not sent a second time after the connection broke with the request already out: the daemon may have
# done it, and done twice it is not the same thing (`Session.call`).
NOT_RESENT = frozenset({"PUT_MEDIA", "FINISH_MEDIA", "VOLUME_FORMAT", "VOLUME_MOUNT_RW", "WRITER_CLOSE", "WRITER_RESIZE"})
```

Такой запрос, ушедший до обрыва, сразу даёт `Unavailable`, и решает вызывающий. Регистратор на `Unavailable` перемонтирует том (урок 10): так кадр не попадёт в архив дважды, а потеря видна как потеря. Обрыв до отправки — например, на `HELLO` при переподключении — по-прежнему повторяется: `_sent` тогда не равен `op`.

**Молчание не повторяется.** Демон принял запрос и ничего не сказал за `timeout` — это тоже `Unavailable`, но второго запроса нет. Докстрока класса объясняет:

> *a broken connection is a reason to resend, a silence is not, and asking twice would double the wait of whoever is waiting.*

Кто ждёт — важно. Регистратор делает вызовы проходом на том же потоке, что продлевает аренды. Демон, зависший на мёртвом сетевом томе, без таймаута держал бы этот поток дольше аренды. Регистратор потерял бы эпохи, и все записи на нём остановились бы из-за одного молчащего демона. Поэтому регистратор создаёт сессию с `OBSD_TIMEOUT` — десять секунд, треть аренды (урок 10).

Один запрос протокол разрешает выполнять долго: `WRITER_CLOSE` отвечает после сброса писателя на носитель, до тридцати секунд. Для него `long=True`:

```python
    def close(self) -> None:
        """After the flush — up to 30 s. What was written becomes readable: the last block is closed."""
        self.session.call("WRITER_CLOSE", {"writer": self.handle}, long=True)
```

`long_timeout` никогда не меньше обычного: `self.long_timeout = max(long_timeout, timeout)`. Оба числа проверяет `test_the_recorders_calls_wait_less_than_a_lease_and_only_a_close_waits_for_its_flush`: у регистратора `timeout == 10.0`, меньше `lease_ttl - lease_margin`, а `long_timeout >= 30.0`. Что регистратор живёт при молчащем демоне, доказывает `test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living`: минута цикла против сокета, который принимает соединения и никогда не отвечает, и аренды продлеваются.

`Unavailable` наследует `ObsdError`, но значит другое:

```python
class Unavailable(ObsdError):
    """The daemon is not there: no socket, or it closed the connection. Not an answer about the volume."""
```

«Не ответ о томе» — ключ к уроку 7. Отказ движка взять кадр означает «пропусти до ключевого кадра». `Unavailable` означает «движка нет», и регистратор перемонтирует том на следующем проходе (обратная связь CF).

## Шаг 5 — Время архива и запись `SMPL`

**Часы архива начинаются в 1900 году.** Время в протоколе — миллисекунды с 1 января 1900 года, не секунды Unix:

```python
EPOCH_OFFSET_MS = 2208988800000          # 1900-01-01 to 1970-01-01, in milliseconds: the archive's clock starts in 1900


def archive_ms(unix_s: float) -> int:
    """Unix seconds → the archive's milliseconds since 1900."""
    return int(round(float(unix_s) * 1000)) + EPOCH_OFFSET_MS


def unix_s(archive: int) -> float:
    """The archive's milliseconds since 1900 → unix seconds."""
    return (int(archive) - EPOCH_OFFSET_MS) / 1000.0
```

Весь остальной курс считает в секундах Unix. Перевод живёт в двух функциях на границе с движком, и больше нигде. Число, забывшее перевод, ошибается на семьдесят лет, и такую ошибку видно сразу. `test_the_archives_clock_starts_in_1900` проверяет смещение и обратимость.

**Кадр — запись платформы.** Кадры идут в той же записи, которой платформа уже обменивается между процессами (`storagewrapper/samplewire.go`):

```python
SMPL = struct.Struct(">4sIIIQQII")        # magic, major, subtype, flags, begin, end, subLen, bodyLen
```

Заголовок кадра протокола — little-endian, а запись `SMPL` — big-endian. Это не небрежность: запись не придумана для демона, она уже была. Демон принял существующий формат, и кадр проходит от источника до тома без перекладывания.

```python
@dataclass
class Sample:
    """One frame as the engine stores it. `begin`/`end` are the archive's milliseconds; `sub` the coded header."""
    ...
    @property
    def key(self) -> bool:
        """Can open a sequence: needs neither an earlier key frame nor the frame before it."""
        return not self.flags & (FLAG_NEED_KEY_FRAME | FLAG_NEED_PREVIOUS_FRAME)
```

Ключевой кадр в движке — не отдельный флаг, а отсутствие двух флагов зависимости. Кадр, которому не нужен ни предыдущий ключевой, ни предыдущий кадр, может открыть последовательность (шаг 9).

`video()` собирает кадр видео так, как его хранит движок:

```python
def video(begin: int, end: int, body: bytes, key: bool, width: int = 1920, height: int = 1080,
          subtype: int = SUBTYPE_H264) -> Sample:
    """A coded video frame: the coded header is width and height, two little-endian u32."""
    return Sample(MAJOR_VIDEO, subtype, 0 if key else FLAG_NEED_KEY_FRAME, begin, end,
                  struct.pack("<II", width, height), body)
```

`subtype` — четыре символа кодека в одном числе (`H264`, `H265`). Типы и флаги взяты из `storagewrapper/mediatype` продукта: движок их хранит, и курс не вправе их менять.

## Шаг 6 — Том, писатель, читатель

Три класса — три вида дескриптора.

**`Volume`** — открытый том. `Session.open_volume` принимает либо `uri`, либо `params`; курс всегда передаёт параметры (урок 7 объясняет почему: ключ не должен попасть в адрес). Дальше:

- `exists()` — `VOLUME_EXISTS`;
- `format(size, max_block, optimal_read, label)` — `VOLUME_FORMAT`: размер тома и размер блока задаются здесь, один раз;
- `mount_rw(owner)` — `VOLUME_MOUNT_RW`: писатель и признак `reattached`;
- `mount_ro()` — `VOLUME_MOUNT_RO`: читатель.

**`Writer`** — единственный писатель тома на хосте. Его `put` возвращает статус только тогда, когда кадр взят:

```python
    def put(self, stream: str, sample: Sample) -> str:
        """One sample. Returns `OK` or `SEQUENCE_LOST` (taken — an EARLIER sequence was refused and lost);
        raises `ObsdError` when it was NOT taken (`SEQUENCE_TOO_LARGE`, `WRITER_STOPPED`, `SEQUENCE_*`)."""
```

Граница проведена по вопросу, на который вызывающему надо ответить: **взят этот кадр или нет**. README даёт таблицу ровно в этих словах:

| статус | кадр |
|---|---|
| `OK` | взят |
| `SEQUENCE_LOST` | взят — а более ранняя последовательность потока, закрытая автоматически, отвергнута и потеряна |
| `WRITER_STOPPED` | не взят; писатель больше ничего не возьмёт |
| `SEQUENCE_TOO_LARGE`, `SEQUENCE_*` | не взят |

`SEQUENCE_LOST` — не исключение, потому что текущий кадр на томе. Потеря касается прошлого, и вызывающему не надо ничего пропускать. Исключение означает «этот кадр не на томе», и вызывающий пропускает до следующего ключевого кадра (урок 7). Писатель считает статусы в `put_counts`.

`finish(stream)` закрывает открытую последовательность потока и возвращает `False`, если открытой не было (`EMPTY_RESULT`). `flush()` сбрасывает хвост на носитель, `resize(size)` меняет размер тома на ходу, `close()` закрывает писателя после сброса.

**`Reader`** — читатель: `streams()`, `timeline(stream, t0, t1)` — интервалы потока, `sequences(...)` — записи индекса, `find(stream, t, backwards)` — ближайшая последовательность, `read(entry)` — кадры последовательности, `status()` — состояние кольца (`firstBlockId`, `numBlocks`, `usedSize`, `availableSize`, `totalWritten`).

**Коды статуса** — словарь `STATUS`. Коды движка от 0 до 131 перенесены из его C-интерфейса без изменений, коды демона начинаются с 1000:

```python
# The engine's status codes, unchanged from its C interface, and the daemon's own.
```

`ObsdError` несёт три вещи: `status` (число), `name` (имя из `STATUS`) и `detail` (слова движка). Весь курс ветвится по `name`, а не по числу: `e.name == "ALREADY_LOCKED"` читается без таблицы.

## Шаг 7 — Настоящий демон в тестах

Тесты не имитируют движок. Комментарий в `tests/conftest.py`:

> *The tests do not imitate it: they start the real daemon, once, on a socket of their own, with volumes in temp directories — never the box's daemon, never its socket. Without the daemon the archive cannot be tested, and the tests that need it say how to get it rather than pass for want of it.*

Модель движка на Python доказывала бы свойства модели. Все свойства шагов 8–14 найдены на живом демоне, а одно из них (шаг 14) в README демона не описано вовсе. Модель такого не нашла бы.

`ObsdDaemon` — один демон на прогон:

```python
        binary = os.environ.get("OBSD_BIN") or shutil.which("obsd")
        if not binary or not os.access(binary, os.X_OK):
            raise RuntimeError(OBSD_HINT)
```

Нет бинарника — тест падает с `OBSD_HINT`: как собрать (`ObjectStorage/standalone-build/build.sh <out>`) и куда указать (`OBSD_BIN=<out>/build/obsd`). Пропуск теста за отсутствием демона выглядел бы как зелёный прогон, в котором архив не проверен.

```python
        self.dir = tempfile.mkdtemp(prefix="obsd-")              # the system's temp dir: a unix socket path is short
        self.socket = os.path.join(self.dir, "run", "obsd.sock")
        if len(self.socket.encode()) > 100:
            raise RuntimeError(f"the socket path {self.socket} is longer than unix sockets allow; set TMPDIR shorter")
```

Путь unix-сокета ограничен примерно сотней байтов. Временный каталог проекта бывает глубоким, поэтому демон получает каталог системы. Слишком длинный путь — внятная ошибка с советом, а не загадочный отказ `bind`.

```python
OBSD_GRACE_S = 3
OBSD_LINGER_MS = 300
...
        env = dict(os.environ, OBSD_WRITER_GRACE_S=str(OBSD_GRACE_S), OBSD_SESSION_LINGER_MS=str(OBSD_LINGER_MS),
                   OBSD_LOG_LEVEL=os.environ.get("OBSD_LOG_LEVEL", "error"))
```

Два числа короче, чем в работе: отсрочка писателя три секунды вместо девяноста (`obsd.service`), жизнь сессии без соединения 300 мс вместо 3000. Так тест отсрочки не ждёт полторы минуты. Сами числа — константы модуля, и тесты импортируют их, а не повторяют: `time.sleep(OBSD_LINGER_MS / 1000 + 0.5)`.

Дальше демон стартует с `--socket`, тест ждёт появления сокета до десяти секунд, а `atexit` останавливает демон по `SIGTERM` с ожиданием до 60 секунд — столько README велит дать демону, чтобы каждый писатель закрылся со сбросом.

Две маленькие функции строят всё остальное:

```python
def obsd_session(client: str = "test", token: str | None = None):
    from w2cplatform.obsd import Session
    return Session(ObsdDaemon.get().socket, client=client, token=token)


def obsd_volume(session, size: int = 64 << 20, max_block: int = 4 << 20, optimal_read: int = 512 << 10, label: str = "test"):
    """A fresh volume in a temp directory, formatted: `(volume, path)`."""
```

Том на 64 МБ с блоком 4 МБ — достаточно мал, чтобы тест кольца переполнил его за секунды.

---

Дальше — свойства движка. Каждое проверяет тест в `tests/test_obsd.py` на живом демоне. Докстрока файла перечисляет их одним предложением:

> *a reader sees only closed blocks, a sequence opens on a key frame, a group of pictures longer than a block is cut, the volume is a ring that gives up its oldest minutes first, a volume has one writer on a host, and a writer whose process vanished waits for its owner before anybody else may have the volume.*

## Шаг 8 — Читатель видит только закрытые блоки

`test_a_reader_sees_only_closed_blocks_and_only_what_was_there_when_it_mounted`:

```python
    w = vol.mount_rw("rec:t2")
    _frames(w, "7/e1", 250)
    early = vol.mount_ro()
    assert early.streams() == [] and _spans(early, "7/e1") == []
    w.flush()
    assert _spans(vol.mount_ro(), "7/e1") == []                             # flushed is not closed
    w.close()
    assert _spans(vol.mount_ro(), "7/e1") == [(0, 6), (6, 10)]             # closed: visible to a reader mounted now
    assert _spans(early, "7/e1") == []                                      # …and not to the one mounted before
```

Три факта в шести строках.

- **Записанное — не видимое.** Десять секунд кадров взяты, а читатель не видит ни потока.
- **Сброс не закрывает блок.** `flush` кладёт хвост на носитель, но блок остаётся открытым, и читатель его не видит.
- **Читатель держит свою картину.** Читатель, смонтированный до закрытия, не видит закрытого и после. Видит только смонтированный заново.

**Закрытый — значит записанный на том, а не «после которого начался следующий».** Блок уходит на носитель, когда заполнен (`maxBlockSize`) — или через `blockFlushPeriodSec` после того, как законченная последовательность легла в очередь движка; последовательность, которую кадры сами не заканчивают, движок режет по `sequenceFlushPeriodMs`. Оба периода — настройки писателя (`WRITER_CONFIGURE`), и у тонкого потока от них зависит всё: при 7 КБ/с блок в 4 МБ заполняется десять минут, и без таймера столько же живая запись не видна. Тест `test_a_thin_stream_is_visible_after_the_flush_periods_and_not_when_its_block_fills` пишет кадры по сто байт и находит их у свежего читателя через периоды, а не через блок. Демон до патча 04 этот тест не проходит: таймер срабатывал, но рабочий цикл просыпался только от целого блока (обратная связь CP).

Докстрока теста называет это правилом, из которого следует половина логики регистратора. Из него вырастают три вещи. `Archive.seal` закрывает писателя и берёт его снова, когда записанное нужно видеть сейчас (урок 7). Каждый вопрос к тому задаётся свежему читателю (урок 7). Регистратор планирует по тому, что видит, а не по тому, что записал (урок 8).

## Шаг 9 — Последовательность открывается ключевым кадром

`test_a_sequence_opens_on_a_key_frame`: первый кадр потока — не ключевой, и движок отвечает `SEQUENCE_NEEDS_KEY_SAMPLE`.

Последовательность — единица индекса: с неё начинается чтение. Последовательность, начатая с зависимого кадра, не декодируется, поэтому движок её не открывает.

`test_what_is_written_is_read_back_by_stream_and_time` показывает, где движок режет поток сам:

```python
    assert _spans(r, "7/e1") == [(0, 6), (6, 10)]                          # sequences cut by the read size, on key frames
```

Двести пятьдесят кадров, ключевой каждые 25 кадров (раз в секунду), размер чтения 512 КБ. Движок закрыл первую последовательность на ключевом кадре шестой секунды, когда она достигла размера чтения. Первая последовательность — 150 кадров, начинается с ключевого.

## Шаг 10 — GOP длиннее блока режется

`test_a_group_of_pictures_longer_than_a_block_is_cut_and_the_rest_waits_for_a_key`:

```python
    """One key frame and then six megabytes of the rest, into four-megabyte blocks: the sequence is closed where
    the block is full, and every frame after it is refused until a key frame opens a new one — lost, not queued."""
    ...
    said = _frames(w, "7/e1", 2100, gop=10 ** 6)
    assert said["OK"] < 2100 and said["SEQUENCE_NEEDS_KEY_SAMPLE"] == 2100 - said["OK"]
```

Последовательность не переходит границу блока. Блок полон — движок закрывает последовательность, и следующий кадр должен открыть новую. Он зависимый, поэтому отвергнут. И все за ним, до ключевого кадра. Кадры не ждут в очереди, они **потеряны**.

Отсюда правило размера блока в `vms/archive.py` (инцидент продукта, обратная связь Y):

```python
# How a volume is formatted, unless its row says otherwise: the block, and the read size the engine cuts
# sequences by. A block must hold a sequence — the read size plus up to one group of pictures — or a long group
# is cut where the block is full and the rest is refused until the next key frame (the product's incident,
# feedback Y): block ≥ read + 3 MB.
BLOCK, READ = 8 << 20, 1 << 20
```

## Шаг 11 — Том — кольцо

`test_the_volume_is_a_ring_and_its_oldest_minutes_go_first`:

```python
    vol, _ = obsd_volume(s, size=16 << 20, max_block=4 << 20)
    ...
    assert _frames(w, "7/e1", 6000) == {"OK": 6000}
    ...
    assert st["totalWritten"] > 16 << 20 and st["firstBlockId"] > 0 and st["numBlocks"] == 4
    assert _spans(r, "7/e1")[0][0] > 0                                       # the first seconds are not there any more
```

Шестнадцать мегабайт, четыре блока, записано около двадцати двух. Ни один кадр не отвергнут. Никто ничего не удалял, а первых секунд нет: кольцо перезаписало самые старые блоки.

Два числа из `READER_STATUS` курс читает дальше постоянно. `totalWritten` — сколько том принял за всё время. `firstBlockId > 0` значит, что кольцо **замкнулось** и уже перезаписывает.

Размер, заданный при форматировании, решает, сколько архив помнит. Поэтому квота тома — это размер кольца. `retention_days` ничего не удаляет и только ограничивает, что показывают двери ([урок 8](08-visibility-retention-timeline.md)). Регистратор следит за глубиной и поднимает тревогу, когда замкнувшееся кольцо держит меньше обещанного ([урок 18](18-what-the-archive-gives-up-first.md)).

## Шаг 12 — Один писатель, и отсрочка для того же владельца

`test_one_writer_per_volume_and_a_vanished_one_waits_for_its_owner` — урок в одном тесте:

```python
    w = vol.mount_rw("rec:vol1")
    _frames(w, "7/e1", 50)
    other = obsd_session("other").open_volume(params={"schema": "file", "path": path})
    try:
        other.mount_rw("rec:other")
        raise AssertionError("two writers on one volume")
    except ObsdError as e:
        assert e.name == "ALREADY_LOCKED"
    a.vanish()
    time.sleep(OBSD_LINGER_MS / 1000 + 0.5)
    try:
        other.mount_rw("rec:other")
        raise AssertionError("somebody else took a writer waiting for its owner")
    except ObsdError as e:
        assert e.name == "ALREADY_LOCKED"
    again = obsd_session("recorder").open_volume(params={"schema": "file", "path": path}).mount_rw("rec:vol1")
    assert again.reattached
    _frames(again, "7/e1", 50, start=50)
    again.close()
    reader = obsd_session().open_volume(params={"schema": "file", "path": path}).mount_ro()
    assert _spans(reader, "7/e1") == [(0, 2), (2, 4)]                        # one recording, no seam
```

**Один писатель на том на хосте.** Второй `VOLUME_MOUNT_RW` получает `ALREADY_LOCKED`. Демон узнаёт том по URI или по `schema://host/path` его параметров — никогда по учётным данным.

**Писатель исчезнувшей сессии ждёт своего владельца.** По README демон делает три вещи. Закрывает каждую открытую последовательность, как сделал бы `FINISH_MEDIA`, — поэтому ничего, что клиент успел отправить, не теряется. Оставляет писателя смонтированным, *отсоединённым*, и помнит `owner`. Ждёт `OBSD_WRITER_GRACE_S`.

**Тот же владелец получает его обратно.** `mount_rw` с тем же непустым `owner` отвечает `reattached: true`: блокировка не берётся заново, том не восстанавливается. Любой другой получает `ALREADY_LOCKED`, пока отсрочка не истекла. Сто кадров, убийство посередине — и на томе одна запись без шва.

Владелец — не секрет: все клиенты демона работают под одним uid. Это заявление личности. Регистратор передаёт `rec:<том>`, а уникальность этого имени обеспечивает аренда тома платформы (урок 10).

`test_after_the_grace_the_volume_is_clean_for_anybody` — другая сторона. Отсрочка истекла — демон закрывает писателя чисто, и следующий `mount_rw` под любым владельцем получает чистый том (`not w2.reattached`). Взятое до убийства на месте.

Почему девяносто секунд в `obsd.service`:

> *Longer than a hold takes to lapse (45 s), so whoever takes the volume next picks the writer up whole (feedback CF).*

Убитый регистратор не отпускает аренду тома. Она истекает сама через 45 секунд, и следующий регистратор берёт том под тем же `rec:<том>`. Отсрочка должна пережить это ожидание, иначе писатель закроется раньше, чем его заберут.

## Шаг 13 — Две эпохи — два потока

`test_two_writers_epochs_are_two_streams_in_one_volume`:

```python
    """The epoch is part of the stream's NAME — the only metadata a stream has. A fenced writer's frames and the
    survivor's are told apart by which stream they are in, not by a directory."""
    ...
    _frames(w, "7/e1", 50)
    _frames(w, "7/e2", 50, start=25)
    ...
    assert sorted(r.streams()) == ["7/e1", "7/e2"]
    assert _spans(r, "7/e1") == [(0, 2)] and _spans(r, "7/e2") == [(1, 3)]  # the minutes both held: two streams, both kept
```

У потока нет метаданных, кроме имени. Значит, эпоха может жить только в имени. Две эпохи одной записи — два потока одного тома, и секунда, которую писали обе, хранится дважды. Урок 7 строит на этом словарь курса.

## Шаг 14 — Таймлайн за шесть дней и окна

`test_a_recording_a_month_deep_is_answered_whole`:

```python
    """Seen, and not in the protocol's README: `READER_TIMELINE` over six days of footage or more is sometimes
    answered `INTERNAL_ERROR` — the same question refused by one daemon and answered by the next. A recording is
    a month deep, so `Archive` asks five days at a time, halves a window refused anyway, and puts the intervals
    back together (`Archive._timeline`)."""
```

Это свойство нашли на живом демоне, в README его нет. Ответ — `INTERNAL_ERROR` с `detail` вида `[volume-error:6]`. И не всегда: один демон отказывает, следующий на тот же вопрос отвечает.

Курс не ждёт исправления движка. `Archive._timeline` спрашивает окнами по пять дней (`TIMELINE_WINDOW`) — пятидневный вопрос не отказывался ни разу. Окно, отказанное всё же, делится пополам, вплоть до часа. Интервалы на стыках окон склеиваются. Тест пишет месяц записи и получает два интервала и глубину ровно тридцать дней. Как из этих интервалов строится таймлайн — [урок 8](08-visibility-retention-timeline.md).

## Результат

```bash
cd vmsserver
OBSD_BIN=<out>/build/obsd python3 tests/run.py
```

```
test_obsd.py::test_a_group_of_pictures_longer_than_a_block_is_cut_and_the_rest_waits_for_a_key ... OK
test_obsd.py::test_a_reader_sees_only_closed_blocks_and_only_what_was_there_when_it_mounted ... OK
test_obsd.py::test_a_recording_a_month_deep_is_answered_whole ... OK
test_obsd.py::test_a_sequence_opens_on_a_key_frame ... OK
test_obsd.py::test_after_the_grace_the_volume_is_clean_for_anybody ... OK
test_obsd.py::test_one_writer_per_volume_and_a_vanished_one_waits_for_its_owner ... OK
test_obsd.py::test_the_archives_clock_starts_in_1900 ... OK
test_obsd.py::test_the_volume_is_a_ring_and_its_oldest_minutes_go_first ... OK
test_obsd.py::test_two_writers_epochs_are_two_streams_in_one_volume ... OK
test_obsd.py::test_what_is_written_is_read_back_by_stream_and_time ... OK
```

Без `OBSD_BIN` и без `obsd` в `PATH` тесты архива падают с подсказкой, как собрать демон.

## Что может пойти не так

- **Движок библиотекой в регистраторе.** Сбой движка роняет все регистраторы коробки, а блокировка тома умирает вместе с убитым процессом, и её приходится пережидать.
- **Повторять запрос после молчания.** Ожидание того, кто ждёт, удваивается, и поток, продлевающий аренды, переживает аренду.
- **Повторять после обрыва кадр или формат, который уже ушёл.** Демон мог его выполнить: кадр записан дважды, том отформатирован дважды.
- **Таймаут вызова длиннее аренды.** Один молчащий демон отсекает регистратор и останавливает все его записи.
- **`WRITER_CLOSE` с обычным таймаутом.** Закрытие обрывается посреди сброса, и последние минуты не становятся видимыми.
- **Новый токен при переподключении.** Демон видит новую сессию, а дескрипторы старой становятся чужими (`UNKNOWN_HANDLE`).
- **Секунды Unix в протоколе.** Время ошибается на семьдесят лет.
- **Считать `SEQUENCE_LOST` отказом.** Регистратор выбросит до ключевого кадра то, что движок уже взял.
- **Модель движка вместо демона.** Тесты доказывают модель, а свойство из шага 14 не находится вообще.
- **Пропускать тест, когда демона нет.** Прогон зелёный, архив не проверен.
- **Отсрочка писателя короче, чем истекает аренда тома.** Писатель убитого регистратора закрывается раньше, чем следующий успевает его забрать.

## Итог

- Движок архива — процесс `obsd`, один на хост: сбой движка роняет один процесс, память регистратора остаётся его, а писатель с блокировкой тома живёт в демоне.
- Кадр — заголовок little-endian, JSON для управления, двоичный хвост для кадров видео. Ответ находят по `id`.
- Дескрипторы принадлежат сессии, а не соединению. `BYE` закрывает всё чисто, исчезнувшая сессия оставляет писателей отсоединёнными.
- Обрыв повторяется один раз под тем же токеном — кроме запроса из `NOT_RESENT`, который ушёл до обрыва: демон мог его выполнить. Молчание — `Unavailable` без повтора, потому что повтор удваивает ожидание. Долго ждать разрешено одному `WRITER_CLOSE`.
- Время архива — миллисекунды с 1900 года, и переводят его две функции на границе. Кадр — запись платформы `SMPL`, big-endian.
- Тесты запускают настоящий демон на своём сокете с короткой отсрочкой и падают с подсказкой, если демона нет.
- Свойства движка: читатель видит только закрытые блоки — заполненные или сброшенные по `blockFlushPeriodSec`; последовательность открывается ключевым кадром, а кадр с `DISCONTINUITY` режет её и посреди группы — флаг, выставленный по сбою часов, а не потока, стоит группы кадров (обратная связь CP); GOP длиннее блока режется и теряется до ключевого; том — кольцо; один писатель на том, и писатель исчезнувшей сессии ждёт своего владельца; эпоха — в имени потока; таймлайн за шесть дней и больше спрашивают окнами.

## Упражнения

1. Уберите `except socket.timeout` из `Session.call`, чтобы молчание шло веткой `OSError` и повторялось. Запустите `test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living` с `timeout=0.05` и посчитайте, сколько длится один вызов.
2. Генерируйте новый токен в `_connect` при каждом подключении. Порвите соединение между `mount_rw` и `put` и назовите статус, который вернёт демон.
3. Перепишите `test_a_reader_sees_only_closed_blocks_and_only_what_was_there_when_it_mounted` так, чтобы после `close` спрашивать читателя `early`. Объясните, почему регистратор задаёт каждый вопрос свежему читателю.
4. Отформатируйте том с блоком 2 МБ и размером чтения 1 МБ и пишите GOP по три мегабайта. Сколько кадров потеряно на каждой группе?
5. Запустите тест кольца с томом на 32 МБ. Когда `firstBlockId` станет больше нуля?
6. Поставьте `OBSD_GRACE_S = 0` в `conftest.py` и запустите `test_one_writer_per_volume_and_a_vanished_one_waits_for_its_owner`. Что увидел второй монтирующий?
7. Спросите `READER_TIMELINE` за весь месяц из `test_a_recording_a_month_deep_is_answered_whole` одним вопросом. Повторите на перезапущенном демоне. Совпали ли ответы?

## Что дальше

Клиент говорит с движком, и свойства движка известны. Пока нет слов курса: что такое поток записи, куда ложится эпоха, что делать с отвергнутым кадром и с пропавшим демоном.

[**Урок 7**](07-volume-block-sequence-stream.md) пишет `vms/archive.py` — словарь курса над движком — и путь записи регистратора: `RecSink` и `appsink` в `GstRecActuator`. И разбирает убитый регистратор: писатель, которого тот же владелец получает обратно целиком.

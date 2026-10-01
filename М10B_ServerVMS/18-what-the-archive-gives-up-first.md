# Урок 18 — Что архив отдаёт первым

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `Archive.resize` и `Archive.depth_days` в `vms/archive.py`; `RecWorker.depth_pass` — глубину записи и тревогу `archive.shallow`; `vms/keeps.py` и `RecWorker.keep_pass` с `_copy_in` — копию отмеченного в том `incidents`; две метрики консоли.
**Время:** ~60 минут.

## Зачем этот урок

В уроке 14 М10A платформа научилась мерить диск и говорить: *освободи сто пятьдесят мегабайт*. Чем освобождать, она сознательно не знает. Раньше этот урок отвечал за подсистему, которая знает: какую камеру резать, у кого запас над полом, куда увезти чужое.

Теперь отвечать нечего. Видео лежит в томе ObjectStorage (урок 6), а том — кольцо фиксированного размера (урок 7). Когда кольцо полно, оно само перезаписывает свои самые старые блоки. Прохода, который удаляет видео, в курсе больше нет, и никто не выбирает, чем пожертвовать.

Вопрос от этого не исчез, он сдвинулся. «Что удалить» решает кольцо. Человеку остаются три других вопроса, и урок отвечает на них.

**Какого размера кольцо.** Размер тома — это и есть глубина архива. Его задают квотой, и его можно поменять без остановки записи.

**Сколько архива на самом деле и меньше ли это обещанного.** Кольцо не знает обещаний. Регистратор их не исполняет — он за ними следит и говорит, когда кольцо зашло за пол записи. Главное здесь — отличить молодой архив от обрезанного.

**Как сохранить то, что должно пережить кольцо.** Кольцо не умеет пощадить диапазон. Поэтому отмеченный интервал нельзя оставить на месте — его копируют в отдельный том.

> **Проверка без железа.** Всё, кроме самой записи с камеры. Тесты урока идут против живого `obsd` (фикстура `ObsdDaemon` в `tests/conftest.py`): кольцо замыкается по-настоящему, когда в том пишут больше квоты, а копия метки ложится в настоящий второй том. Источник копии — дверь архива другого регистратора, поднятая тестом (`door`). GStreamer не нужен: кадры — это `fake_samples`. Два теста ватерлинии в `test_disk_full.py` не трогают `obsd` вовсе. Без собранного `obsd` архивные тесты падают с подсказкой, как его собрать (`ObjectStorage/standalone-build/build.sh`, `OBSD_BIN`).

## Что нужно знать заранее

- **[Урок 6](06-objectstorage-the-engine.md)** — движок ObjectStorage и демон `obsd`: сессия, писатель, читатель.
- **[Урок 7](07-volume-block-sequence-stream.md)** — том, блок, последовательность, поток; почему том — кольцо и что значит `firstBlockId`.
- **[Урок 8](08-visibility-retention-timeline.md)** — видимость, `retention_days` как потолок того, что показывают двери, и таймлайн.
- **[Урок 10](10-recworker.md)** — регистратор и удержание тома: кто пишет в том и под каким владельцем.
- **[Урок 27](27-volumes.md)** — виды томов, среди них `incidents`.
- **М10A, урок 14** — ресурс, ватерлиния, `relieve` и недостача.

## Чему вы научитесь

1. Объяснять, почему в архиве нет прохода удаления и что решает, сколько архив держит.
2. Менять размер кольца без остановки записи.
3. Мерить фактическую глубину записи и отличать молодой архив от обрезанного.
4. Поднимать тревогу о невыполненном обещании, не пытаясь его исполнить.
5. Сохранять отмеченный интервал копией, когда кольцо не умеет щадить диапазон.
6. Проверять копию дайджестом и замечать, когда кольцо копий дошло и до неё.
7. Понимать, что осталось от ватерлинии и зачем.

---

## Шаг 1 — Чего больше нет

Прошлая версия этого урока была лестницей из четырёх ступеней. Отдать чужое серверу, который теперь пишет запись. Резать у камеры с самым большим запасом над полом. Срезать отмеченное, когда больше нечего. Назвать недостачу вслух. Каждое удаление шло строкой в журнал удалений.

Всё это ушло вместе с файловым архивом, и причина одна. Вот как `vms/archive.py` описывает кольцо:

```python
#   the ring       a volume is formatted at its quota and overwrites its oldest blocks when full. Nothing is
#                  deleted by age: `retention_days` is a CEILING on what the doors show (`visible_from`), and
#                  how deep the archive really is, is read off the index (`depth_days`)
```

Удалять по возрасту некому и незачем: самые старые блоки кольцо перезапишет само. Резать под давлением тоже незачем: том не растёт больше своей квоты, поэтому диск под ним не переполняется. Журнал удалений описывал решения политики — а решений больше нет, есть свойство тома.

Тест `test_obsd.py::test_the_volume_is_a_ring_and_its_oldest_minutes_go_first` показывает это без всякого кода курса. Том на шестнадцать мегабайт, в него пишут двадцать два. Никто ничего не удалял, а первых секунд в индексе нет.

Из этого следуют два правила, которые стоит запомнить до всего остального.

**Сколько архив держит, решает размер тома.** Не `retention_days` и не политика. `retention_days` остался, но он только потолок того, что показывают двери (урок 8).

**Внутри одного тома у записей общее время.** Кольцо отдаёт самый старый блок целиком, а в блоке лежат последовательности всех потоков тома вперемешку. Камера с высоким битрейтом укорачивает глубину всем соседям по тому. Если двум записям обещано разное, развести их можно только по разным томам.

## Шаг 2 — Размер кольца: квота

Том, которого ещё нет, регистратор форматирует при первом открытии. Размер — квота из строки тома:

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
```

Без квоты том не форматируется: кольцо без размера — не кольцо, и угадывать его некому. Ошибка вида `wrong`, потому что исправить её может только человек (урок 10).

Для собственного тома сервера — того, что регистратор берёт, когда ничего не объявлено, — квоту берут из `ARCHIVE_QUOTA_BYTES`, а без неё считают от свободного места:

```python
    # A volume nobody declared, on a disk nobody measured: four fifths of what is free, leaving two gigabytes —
    # the product's rule (feedback BM) — and never so much that the disk ends above the watermark's low mark
    # (`space_settings`, 0.75 by default) once the ring is full. The disk is shared with the resource's events,
    # and a ring that filled it past the mark would leave the watermark short for good: nothing of the VMS's
    # answers `free` any more. At least a gigabyte, whatever the arithmetic says. Asked once, when it is first
    # formatted; a volume that exists keeps the size it has.
    @staticmethod
    def _share_of_free(root: str, low: float = 0.75) -> int:
```

Спрашивают один раз. Том, который уже существует, сохраняет свой размер, иначе каждый перезапуск мерил бы диск заново и получал бы другое число.

**Новая квота — новый размер кольца, сразу.** Администратор меняет `quota_bytes` в строке тома (урок 27), и регистратор на следующем проходе видит разницу:

```python
    def _write_into(self, vol) -> ArchiveError | None:
        if self.store is not None and self.store.url == vol.url and self.store.writer is not None and not self.engine_lost:
            if vol.quota_bytes and vol.quota_bytes != self.store.quota:
                try:
                    self.store.resize(vol.quota_bytes)   # a new quota is a new size of the ring, without stopping
                except ObsdError as e:
                    log.warning("%s: could not resize %s to %d bytes: %s", self.name, vol.name, vol.quota_bytes, e)
            return None
```

```python
    def resize(self, quota: int) -> None:
        """A new quota is a new size of the ring, at once and without stopping: shrinking frees the oldest."""
        if self.writer is not None and quota and quota != self.quota:
            self.writer.resize(quota)
        self.quota = quota or self.quota
```

Писатель не закрывают и запись не останавливают. Это важно: закрыть писателя значит оборвать последовательности всех записей тома, а ради числа в строке так делать незачем. Уменьшение квоты сразу освобождает самые старые блоки — ровно те, что кольцо и так отдало бы первыми.

Отказ движка не останавливает запись. Он остаётся строкой в логе, и том пишется дальше в старом размере. Квота — желание администратора, а запись идёт сейчас.

## Шаг 3 — Сколько архива на самом деле

До кольца в системе было обещание (`retention_days`) и не было факта. Факт берётся из индекса тома:

```python
    def coverage(self, unit, gap: float = STITCH) -> list[tuple[float, float]]:
        return stitch(((s.start, s.end) for s in self.spans(unit)), gap)

    def depth_days(self, unit, now: float) -> float:
        cov = self.coverage(unit)
        return max(0.0, (now - cov[0][0]) / 86400) if cov else 0.0
```

Глубина — от начала самого старого куска записи до сейчас. Её не ограничивает `retention_days`: потолок прячет старое от дверей, но не от этого подсчёта. Так и задумано. Глубина отвечает на вопрос «что ещё есть в кольце», а не «что показывают».

Дыры внутри не вычитаются. Глубина говорит, докуда архив достаёт, а не сколько в нём часов. Дыры видны на таймлайне, и это другой вопрос.

## Шаг 4 — Пол записи: следить, а не исполнять

`retention_days` — потолок: старше ничего не показывают. Сколько архива **должно быть**, долго не говорил никто, и запись, которой обещали тридцать дней, на томе, вмещающем четыре, выглядела здоровой (обратная связь, BM). Поэтому у строки записи есть поле:

```yaml
    min_depth_days: {type: float,  default: 0}
```

Исполнить его нельзя. Кольцо отдаёт самые старые минуты, что бы им ни обещали. Остановить запись сегодня, чтобы сберечь прошлый месяц, никто не выбирал. Поэтому регистратор за полом **следит**:

```python
    # HOW DEEP EACH RECORDING IS, AND WHETHER THAT IS LESS THAN IT WAS PROMISED (feedback BM).
    #
    # `retention_days` is a ceiling on what is shown. The row's `min_depth_days` is the floor — and nothing
    # enforces it: the volume is a ring, and a ring gives up its oldest minutes when it is full, whatever was
    # promised. So the recorder WATCHES. Once a minute it reads, per recording:
    #
    #   depth_days   from the index: how far back the footage goes. In the status and on `/metrics`
    #   shallow      the ring has CLOSED — it has begun to overwrite (`firstBlockId` past nought) — and the
    #                recording holds less than its floor. A young archive is shallow because it is young, and
    #                that is not this: nothing was overwritten yet
```

```python
    def depth_pass(self, now: float | None = None) -> dict:
        from w2cplatform.events import ALARM, EventLog
        if self.store is None or self.clock() - self._depth_at < self.DEPTH_EVERY:
            return self.depths
        self._depth_at, now = self.clock(), self.wall() if now is None else now
        try:
            closed = int(self.store.status().get("firstBlockId", 0)) > 0
            depths = {str(r["id"]): round(self.store.depth_days(str(r["id"]), now), 2) for r in self.rows}
        except ArchiveError:                         # a volume that is away says nothing about depth
            return self.depths
        self.depths = depths
        for row in self.rows:
            unit, floor = str(row["id"]), float(row.get("min_depth_days") or 0)
            if not floor or not closed or depths[unit] >= floor:
                self.shallow.pop(unit, None)
                continue
            if now - self.shallow.get(unit, -1e18) < self.SHALLOW_AGAIN or unit not in self.epochs:
                continue
            self.shallow[unit] = now
            EventLog(self.archive_root, REC.name, unit, self.epochs[unit]).append(
                now, "archive.shallow", cls=ALARM, cam=row.get("cam"), depth_days=depths[unit], min_depth_days=floor)
```

**Почему не просто «глубина меньше пола».** Запись, которую завели три дня назад с полом семь дней, мелкая — потому что молодая. Тревога по ней каждое утро научит оператора не читать тревоги. Отличить два случая можно по одному числу состояния тома: `firstBlockId`. Пока оно ноль, кольцо не сделало ни одного оборота и ничего не перезаписало. Мелко — значит молодо. Когда оно больше нуля, кольцо уже отдаёт старое, и мелкая запись — это запись, у которой кольцо забрало обещанное.

Прошлая версия различала эти случаи журналом удалений: была ли строка «ватерлиния срезала внутри пола». Журнала больше нет, а вопрос остался тот же. Ответ на него теперь даёт сам том, без бухгалтерии рядом.

**Почему тревога, а не строка в логе.** Запись, которая держит четыре дня из обещанных тридцати, — то, о чём потом спросят. Тревога `archive.shallow` пишется классом `alarm` в бакет записи `rec/<запись>/` под её эпохой — один раз, когда началось, и раз в сутки (`SHALLOW_AGAIN`), пока длится. Каждую минуту было бы шумом; один раз навсегда — забылось бы.

**Почему только держатель эпохи.** Условие `unit not in self.epochs` — то же правило, что у любых событий (М10A, урок 12): в бакет записи пишет тот, кто держит её эпоху. Иначе два регистратора, видящие один том, подняли бы две тревоги.

Ответ на тревогу комментарий называет прямо: квота больше или меньше записей на томе. Система своё сделала — сказала.

Глубина уходит в статус записи (`depth_days`, `shallow`) и оттуда — в метрики консоли:

```python
    # How far back each recording goes, and whether its volume's ring has closed inside the floor it was promised
    # (`min_depth_days`; feedback BM).
    out.append("# TYPE rec_archive_depth_days gauge")
    out += [f'rec_archive_depth_days{{unit="{st["id"]}"}} {st["depth_days"]}' for w, hb in hbs for st in hb.status if "depth_days" in st]
    out.append("# TYPE rec_archive_shallow gauge")
    out += [f'rec_archive_shallow{{unit="{st["id"]}"}} {1 if st.get("shallow") else 0}' for w, hb in hbs for st in hb.status if "depth_days" in st]
```

Тест `test_disk_full.py::test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_ring_does_not` проходит всё целиком. Запись `7` с полом семь дней держит десять, кольцо не замкнуто — тревоги нет. В том пишут поток `flood` больше квоты, кольцо замыкается, глубина `7` падает ниже семи — одна тревога, а запись `8` без пола молчит. Через минуту — всё ещё одна. Через сутки — вторая. Пол сняли — `shallow` пропадает. В конце консоль отдаёт `rec_archive_depth_days` и `rec_archive_shallow` по heartbeat'у.

`min_depth_days` — не `min_days` из `platform/space`. Тот — пол ватерлинии на диске ресурса (шаг 8). Имена разные намеренно: два разных пола под одним именем пришлось бы объяснять каждому заново.

## Шаг 5 — Метка: строка `rec/keeps/<id>`

Ни кольцо, ни потолок не знают, что десять минут камеры 7 в прошлый вторник — доказательство (ревью платформы, блокер 10; обратная связь, BH). Об этом говорит **метка удержания** (дальше — просто метка). Это вторая таблица подсистемы `rec` после томов:

```python
@dataclass(frozen=True)
class Keep:
    id: str
    cam: str
    since: float                  # unix seconds
    until: float
    note: str = ""
    by: str = ""                  # who set it
    at: float = 0.0               # when
    recordings: tuple = ()        # the names of the camera's recordings when it was set
```

Камера, интервал, заметка, кто поставил и когда. В строке и на двери границы называются `from` и `to`, как во всех дверях архива и у продукта (обратная связь, BQ). Строки, записанные до переименования, читаются по старым именам `since`/`until` (обратная связь, BV; `test_a_keep_written_before_its_fields_were_renamed_still_holds`).

**Идентификатор — сам интервал:** `<камера>-<с>-<по>` в целых секундах. Повторный POST пишет ту же строку, и двое, отметившие одни и те же десять минут, отметили их один раз.

**Имена записей пишутся в строку.** Том знает видео по имени записи (`7`, `7-cloud`), а чья это запись, говорит её строка. Удалите запись — и ничто больше не связывает поток `7-cloud` с камерой 7. Поэтому метка запоминает имена, которые нашла при постановке, а запись той же камеры, созданная позже, находится по своей строке. Тест — `test_a_keep_holds_a_recording_whose_row_is_gone_and_one_made_after_it`.

Метку ставит и снимает консоль: `GET /rec/keeps`, `POST /rec/keeps`, `DELETE /rec/keeps/<id>`. И то и другое — строка в журнале с именем: `archive.keep.made`, `archive.keep.lifted` (М10A, урок 15). Кто поставил, написано в самой метке. Кто **снял**, без журнала не узнать: строки уже нет. Список меток консоль отдаёт только по тем камерам, которые спрашивающий видит (обратная связь, CG; `test_the_list_of_keeps_is_what_the_caller_may_see`).

Метка держит две вещи. События — на месте, это шаг 7. Видео — копией, это шаг 6.

## Шаг 6 — Видео: копия в томе `incidents`

Кольцо не умеет пощадить диапазон. Когда очередь дойдёт до блока с отмеченными минутами, он будет перезаписан вместе с остальными. Поэтому метку нельзя держать на месте — её содержимое **копируют** в отдельный том. Так устроен и продукт:

```python
    # -- keeps: a COPY in the incidents volume (feedback BH; the product's design) ---------------------------
    #
    # A volume is a ring, and a ring cannot spare a range: when its turn comes, kept footage is overwritten with
    # the rest. So the recorder holding an INCIDENTS volume copies every keep's minutes into it — out of whichever
    # recorder's door holds them, every recording of the keep's camera (`Keep.recordings` and any row naming the
    # camera now), as the stream `<recording>/e0`. Epoch nought: a copy is nobody's lease, and where the live
    # footage still exists its own epoch owns those minutes (`authoritative`); where the ring took it, the copy
    # is what is left. What one pass could not get — a door that is down, a recorder that moved — the next asks for
    # again: the keep stands until somebody lifts it.
```

**Том `incidents` — место для доказательств, а не для записи.** Регистратор, взявший такой том, объявляет нулевую ёмкость, как запасной:

```python
    def _place_kind(self, vol) -> None:
        self.incidents = vol.kind == "incidents"
        if self.incidents:
            self.capacity = 0
```

И контроллер не размещает на нём записи, сколько бы места там ни было (`volumes.admit_recording`):

```python
    place = ctl.place_of(worker)
    if place in kept:
        return False                                  # a place for what somebody kept, never one to record into
```

Обе половины нужны. Ёмкость ноль говорит «я не место для записи» в heartbeat'е. Фильтр не даёт контроллеру ошибиться, если heartbeat устарел. Тест — `test_an_incidents_volume_is_a_place_for_evidence_and_never_one_to_record_into`. Как такой том объявляют, разбирает [урок 27](27-volumes.md).

**Проход копирования.** Раз в минуту (`KEEP_EVERY`), в своём потоке, как дозапись (урок 16), регистратор тома `incidents` проходит по меткам и по записям каждой метки:

```python
                for a, b in subtract((k.since, k.until), self.store.coverage(rec)):
                    for name, url in doors:
                        try:
                            samples = self.read_samples(url, rec, a, b)
                        except OSError:
                            continue                     # that door is down: another may have it, the next pass asks again
                        if samples and self._copy_in(rec, samples):
                            touched.append(rec)
                            break
                if rec in touched:
                    self.store.seal()                    # what was copied is readable now — and counted below
```

Копирует он только то, чего в томе ещё нет: интервал метки минус покрытие (`subtract`, та же функция, что у дозаписи). Источник — двери архивов других регистраторов (`recorder_doors`), по очереди, до первой, которая отдала кадры. Дверь, которая не ответила, — не повод останавливаться: может ответить следующая, а если нет — спросит следующий проход.

`seal` закрывает писателя и берёт его снова. Читатель видит только закрытые блоки (урок 7), а проход сразу после копии считает, сколько метки лежит в томе. Без `seal` он посчитал бы ноль.

**Кадры ложатся последовательностями, а не одним куском:**

```python
    # Frames from another recorder's door into this volume, as `<recording>/e0`, one sequence per stretch — a hole
    # inside a sequence would be drawn as footage. What the door handed over starts on a key frame.
    def _copy_in(self, rec: str, samples: list) -> bool:
```

Индекс рисует последовательность сплошной. Если между двумя кусками метки не было видео, а копия легла одной последовательностью, таймлайн нарисует там запись, которой не было. Поэтому разрыв больше `stitch` закрывает последовательность (`finish`), а следующая открывается только на ключевом кадре — другого начала движок не принимает (`SEQUENCE_NEEDS_KEY_SAMPLE`, урок 7).

**Почему эпоха ноль.** Копия — ничья аренда. Пока живое видео ещё в кольце записи, его минуты принадлежат его собственной эпохе: `authoritative` отдаёт каждый промежуток старшей эпохе, а любая настоящая старше нуля. Когда кольцо записи забрало их, копия — то, что осталось. Консоль при этом не помечает `e0` как отсечённую: она сравнивает только эпохи больше нуля (`0 < epoch < cur` в `timeline`).

**Потолок не прячет отмеченное.** Дверь регистратора тома `incidents` показывает всё:

```python
    def _visible_from(self, unit) -> float:
        from .archive import visible_from
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
```

Тест `test_a_keep_is_copied_into_the_incidents_volume_and_outlives_the_recordings_ring` проходит путь целиком. Десять минут отмечены и скопированы, `copied == 600`, в томе один поток `7/e0`. Второй проход ничего не копирует и событие не повторяет. Потом дверь исходной записи закрывают — её кольцо ушло дальше или сервера больше нет. Дверь тома `incidents` по-прежнему отдаёт таймлайн с эпохой ноль и кадры, начинающиеся с ключевого.

## Шаг 7 — Что копия обещает и чего не обещает

**Дайджест того, что скопировано.** Проход, который что-то скопировал, пишет событие:

```python
    #   archive.keep.copied   an event, when a pass copied something: the recording, the seconds, and the sha256
    #                         of the frames as the incidents volume now holds them — "is this what was kept"
```

Дайджест считается по кадрам в томе `incidents` после копии, а не по тому, что пришло из двери. Это ответ на вопрос «то ли это, что отметили»: тот, кто через месяц выгрузит интервал, сравнит. Дайджест остаётся и в heartbeat'е регистратора (`keeps`), когда проход ничего нового не копировал.

**Копия — не «навсегда».** Том `incidents` — тоже кольцо. Отличие одно: в него пишут только метки, поэтому оно крутится так медленно, как ставят метки. Когда и оно полно, самые старые копии уходят — и это тревога:

```python
                # First what is GONE — before anything is copied, or a copy taken again from the recording's own
                # volume would hide that the incidents ring is too small to hold what it was given.
                now_in, before = inside(k, rec), self.keep_held.get((k.id, rec), 0.0)
                if now_in + 1.0 < before:
                    lost = round(before - now_in, 1)
                    EventLog(self.archive_root, REC.name, rec, 0).append(
                        now, "archive.keep.lost", cls=ALARM, cam=k.cam, keep=k.id, recording=rec, seconds=lost,
                        volume=self.volume)
```

**Порядок здесь и есть правило.** Сначала проход проверяет, что пропало, и только потом копирует недостающее. В обратном порядке он перекопировал бы пропавшее из кольца записи — пока оно там ещё есть — и никто не узнал бы, что кольцо `incidents` мало для того, что ему дали. Через неделю кольцо записи тоже ушло бы дальше, и копии не стало бы без единого слова.

Тревога одна на пропажу. `keep_held` запоминает, сколько лежит сейчас, и следующий проход сравнивает уже с этим числом: пропавшее не теряется дважды. Тест — `test_kept_footage_the_incidents_ring_took_is_an_alarm`: кольцо `incidents` на шестнадцать мегабайт, метки на двадцать два, первая уходит, тревога `archive.keep.lost` класса `alarm` с секундами, и повторный проход её не повторяет.

Ответ на тревогу — квота тома `incidents` больше или выгрузка (урок 24). Метка покупает время, а не вечность. Доказательство, которое должно пережить том, выгружают.

**Не прочитал — не значит «меток нет».** Проход читает метки в начале, и это чтение не в `try`:

```python
        declared = keeps.declared(self.vars)             # a store that does not answer RAISES: unread is not "none"
```

Хранилище не ответило — проход падает и не делает ничего. Здесь обратное правило стоило бы меньше, чем в старой лестнице: проход только копирует. Но `keep_state` в heartbeat'е, прочитанный как «меток нет», сказал бы оператору, что его доказательства нигде не держат. Тест — `test_not_being_able_to_read_the_keeps_is_not_there_are_none`.

**События держатся на месте.** Бакеты событий лежат на ресурсе, и их хранит по дням ресурс платформы. Что такое метка, он не знает. Тот, кто его собрал, даёт ему функцию `kept`:

```python
# Which event buckets a keep holds (`vms/keeps.py`), for the platform's retention pass. The camera's events
# are in `vms/<cam>/`; whatever a recorder wrote about a recording is in `rec/<name>/`. Read once a pass.
def kept_buckets(vars_):
```

Важнее всего это для `{days: 0}` — того, во что превращается срок удалённой камеры. Без `kept` удаление камеры стирало бы ровно те тревоги, которые кто-то отметил. Тест — `test_deleting_the_camera_does_not_erase_the_events_somebody_marked`. Для событий нужна строка, а не копия: файловое дерево ресурса умеет оставить один бакет и удалить соседний, а кольцо так не умеет.

## Шаг 8 — Что осталось от ватерлинии

Ватерлиния из урока 14 М10A никуда не делась. Она меряет диск **ресурса** и спрашивает подсистемы, зарегистрировавшие `free`, что они могут отдать. Подставной класс `_Files` из `test_disk_full.py` говорит, кому она теперь нужна:

```python
class _Files:
    """A subsystem that keeps files on the resource's disk and can give some up: two thousand bytes above its
    floor. The VMS has none any more — footage is in volumes, rings that never outgrow their quota — and the
    watermark is the platform's, for whatever a subsystem keeps on that disk."""
```

VMS держит на диске ресурса только события, и их хранят по дням (`retain`). Отдать по требованию ей нечего, поэтому `free` она не регистрирует. Два правила ватерлинии при этом остаются в силе, и первые два теста `test_disk_full.py` их держат:

- `test_the_watermark_is_on_until_somebody_turns_it_off` — без строки `platform/space` ватерлиния работает на умолчаниях. `enabled: false` — решение, которое кто-то принял, а не умолчание.
- `test_what_could_not_be_freed_is_a_number_anybody_can_read` — недостача уходит в heartbeat ресурса и в метрику консоли `vms_resource_short_bytes{server}`, а не в строку лога.

Учтите одно: собственный том сервера (`/data/volume`, рядом с деревом ресурса) лежит на том же диске. Для ватерлинии его байты — занятое место, и отдать их ей некому: кольцо не растёт сверх квоты и не уменьшается по просьбе. Поэтому квота по умолчанию кончается раньше нижней отметки ватерлинии (`_share_of_free` выше). Если ватерлиния на коробке всё же говорит о недостаче, смотрите сначала на квоту тома: её задали руками или объявили больше.

**Дозапись больше не ждёт диска.** Раньше у неё был второй предохранитель: не тянуть с карты то, что ватерлиния собирается удалить. Теперь гоняться некому:

```python
    # What it does NOT wait for is a full disk. The footage is in a ring formatted at its quota: it never grows
    # past it, and a range fetched now is written at the ring's head, the newest block, overwritten last. The
    # chase the watermark used to guard against — the resource freeing hours, backfill fetching the same hours
    # back — has nothing to chase.
    def archive_busy(self) -> bool:
        return bool(self.archive_error) or self.store is None or self.store.writer is None
```

Дозапись ждёт одного: тома, который ничего не принимает. Тест — `test_lesson11_edge.py::test_backfill_into_a_ring_waits_for_the_volume_and_not_for_the_disk`.

---

## Что может пойти не так

| Симптом | Скорее всего |
|---|---|
| Тревога `archive.shallow` на записи | Кольцо тома замкнулось, и запись держит меньше `min_depth_days`. Том мал для обещанного: квота больше или записей на томе меньше. |
| Тревога `archive.shallow` на новой коробке каждое утро | Проверка «глубина меньше пола» без условия `firstBlockId > 0`. Молодой архив мелок, потому что молод. |
| Две тревоги `archive.shallow` на одну запись | Тревогу пишет не только держатель эпохи записи. |
| Камера с длинным сроком хранения держит три дня | Она делит том с камерами, которые пишут больше. Внутри кольца у всех общее время; разведите записи по томам. |
| Квоту уменьшили, а глубина не изменилась | Регистратор не дошёл до `_write_into` или движок отказал в `resize`: строка `could not resize` в логе. |
| Отмеченный интервал есть в метке, а в томе `incidents` пусто | Регистратора тома `incidents` нет, или ни одна дверь не отдала эти минуты. Смотрите `missing` в `keeps` его heartbeat'а. |
| Метка поставлена на минуты старше `retention_days` записи, и копии нет | Копия идёт через двери, а двери не показывают старше потолка, даже если кольцо их ещё держит. |
| На таймлайне видео там, где его не было | Копия легла одной последовательностью поверх разрыва. Разрыв должен закрывать последовательность. |
| Отмеченный интервал исчез из тома `incidents` | Его кольцо дошло до него: тревога `archive.keep.lost`. Квота больше или выгрузка. |
| Копия пропала, а тревоги не было | Проход сначала перекопировал из кольца записи, потом считал пропажу. Порядок обратный. |
| На том `incidents` разместили запись | Нет фильтра в `admit_recording`; ноль в ёмкости его не заменяет. |
| `vms_resource_short_bytes` не ноль на коробке | Над отметкой, а отдать ватерлинии нечего. Часто это сам том архива на том же диске: смотрите его квоту. |
| Удаление камеры стёрло отмеченные тревоги | Ресурсу не дали `kept`. |

## Итог

- Прохода, удаляющего видео, нет. Том — кольцо, и самые старые блоки он отдаёт сам.
- Сколько архив держит, решает размер тома. `retention_days` — только потолок того, что показывают двери.
- Внутри одного тома у записей общее время. Разное обещание — разные тома.
- Квота — размер кольца. Новая квота применяется сразу, без остановки писателя.
- Глубина записи читается из индекса. Пол записи не исполняют, за ним следят.
- Мелкий архив тревожен только тогда, когда кольцо замкнулось (`firstBlockId > 0`). До этого он мелок, потому что молод.
- Метку нельзя держать на месте в кольце. Её копируют в том `incidents`, куда ничего не записывают.
- Копия проверяема: `archive.keep.copied` с sha256. Копия не вечна: когда кольцо `incidents` дошло до неё, это тревога `archive.keep.lost`.
- Сначала проверить пропажу, потом копировать — иначе пропажа незаметна.
- События держатся на месте строкой метки: дерево ресурса умеет то, чего не умеет кольцо.
- Ватерлиния осталась для того, что подсистемы держат на диске ресурса. Дозапись больше не ждёт диска — только тома.

## Упражнения

1. Возьмите `test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_ring_does_not` и уберите условие `not closed`. Что увидит оператор новой коробки в первую неделю?
2. Две записи на одном томе: одна пишет 2 Мбит/с, другая 8. Квота — 1 ТБ. Посчитайте глубину каждой. Затем посчитайте, какой должна быть квота, чтобы у первой было тридцать дней.
3. Напишите тест на `Archive.resize`: том на 32 МБ, запись на 30 МБ, квота 16 МБ. Что покажут `firstBlockId` и глубина до и после?
4. Поменяйте порядок в `keep_pass`: сначала копировать, потом проверять пропажу. Повторите `test_kept_footage_the_incidents_ring_took_is_an_alarm`, оставив дверь исходной записи открытой. Поднимется ли тревога?
5. Уберите `seal` после копии. Что посчитает `inside` в том же проходе и что попадёт в heartbeat?
6. Сделайте копию одной последовательностью, без `finish` на разрыве. Отметьте интервал, внутри которого пять минут не было записи, и посмотрите на таймлайн тома `incidents`.
7. Запишите копию под текущей эпохой записи, а не под нулём. Что покажет таймлайн консоли, когда эпоха записи сменится?
8. Уберите из `_share_of_free` третье слагаемое — то, что держит диск под нижней отметкой. Диск занят на 30 % до первого форматирования. Посчитайте, где окажется ватерлиния (`high: 0.85`), когда кольцо заполнится. Что скажет `vms_resource_short_bytes` — и что из курса могло бы его уменьшить?

## Что дальше

Архив теперь говорит, сколько держит, и сохраняет то, что велели сохранить. Следующий урок — **[урок 19](19-the-cameras-credential.md)**: пароль камеры, единственное поле строки, которое нельзя показать даже тому, кто вправе её редактировать.

Как отмеченный интервал выгрузить и отдать тому, кто будет разбираться, — **[урок 24](24-an-interval-in-the-browser.md)**.

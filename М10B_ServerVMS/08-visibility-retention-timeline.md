# Урок 8 — Видимость, срок хранения, таймлайн

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** вторую половину `vms/archive.py` — `visible_from`, `authoritative`, `Archive.spans` с `_timeline` (вопрос окнами по пять дней), `Archive.timeline`, `coverage`, `depth_days`, `samples`; и в `vms/recworker.py` — дверь архива `archive_routes`, `RecWorker.serve_archive`, `RecWorker._visible_from` и `RecWorker._kept_of`.
**Время:** ~75 минут.

## Зачем этот урок

Прежний урок 8 отвечал на три вопроса, которые возникают после месяца работы. Индекс разошёлся с файлами — как починить? Диски кончаются — как удалять старое? Что видит оператор — как построить таймлайн? Видео теперь лежит в томах ObjectStorage (уроки 6 и 7), и ответы на два первых вопроса поменялись целиком.

**Чинить нечего.** Индекс тома ведёт движок, а не курс. Рядом с томом курс не хранит ни одной строки, которая могла бы с ним разойтись.

**Удалять по сроку тоже нечего.** Том — кольцо: заполнился — отдаёт старейшие блоки сам. Поле `retention_days` теперь значит другое: это **потолок видимости**, то есть насколько далеко назад двери показывают запись. Что в томе ещё есть, решает кольцо.

**Таймлайн остался, и он стал интереснее.** Его строят из индекса тома, по всем потокам записи, а индекс отвечает только про закрытые блоки. Две эпохи над одними минутами таймлайн показывает обе, а при чтении кадров каждую минуту получает одна эпоха — старшая.

И последнее: всё это выходит наружу через **дверь архива** — HTTP регистратора над томом, который он держит. Её читают консоль (урок 12), скан (урок 20), резервная запись (урок 26) и копирование удержаний.

> **Проверка без железа.** Весь урок идёт против настоящего `obsd`: `tests/conftest.py` поднимает демон (`ObsdDaemon`) с коротким `OBSD_WRITER_GRACE_S`, а без бинарника тест падает с подсказкой, как его собрать (`ObjectStorage/standalone-build/build.sh`, `OBSD_BIN`). GStreamer не нужен: кадры даёт `vms.worker.fake_samples`, а `footage` из `conftest.py` пишет их в поток. Тесты урока: `test_lesson3_archive.py`, `test_obsd.py`, `test_rec_volume.py::test_the_archive_door_hands_out_timelines_and_frames`, `test_review_remainder.py::test_a_store_that_did_not_answer_is_not_a_knob_that_is_off_nor_thirty_days`, `test_review_remainder.py::test_the_door_cuts_a_span_at_the_ceiling_and_shows_what_a_keep_holds_behind_it`, `test_review_remainder.py::test_a_read_starts_on_the_key_frame_before_the_moment_asked_for`, `test_scan.py::test_two_epochs_over_the_same_minutes_the_later_one_owns_them`, `test_doors.py::test_a_recorders_archive_door_names_a_recording_and_nothing_else`.

## Что нужно знать заранее

- **[Урок 6](06-objectstorage-the-engine.md)** — `obsd`, сессия, `Volume`, `Writer`, `Reader`, `Sample`; время архива в миллисекундах с 1900 года (`archive_ms`, `unix_s`).
- **[Урок 7](07-volume-block-sequence-stream.md)** — том, блок, последовательность, поток; `stream_name`, `parse_stream`, `Span`, `Archive.open`.
- **[Урок 10](10-recworker.md)** — регистратор держит один том; его эпохи (`self.epochs`) и порядок ухода с тома.
- **М10A, урок 6** — эпоха: то, что здесь становится бледным интервалом.
- **М10A, урок 14** — ресурс и срок хранения бакетов: события живут по своему правилу, и в этом уроке их нет.

## Чему вы научитесь

1. Отличать «записано» от «видно» и строить планы по тому, что видно.
2. Объяснять, почему курсу нечего чинить в томе.
3. Отделять «сколько показываем» от «сколько есть».
4. Отвечать по последней прочитанной строке, когда хранилище молчит, а не по умолчанию.
5. Строить таймлайн из индекса тома окнами, которые движок не отвергает.
6. Показывать обе эпохи над одними минутами и при этом отдавать каждую минуту одной.
7. Открывать том наружу дверью, которая называет запись и ничего больше.

---

## Шаг 1 — Чинить нечего

Прежний `repair` сверял две вещи: строки манифеста и файлы на диске. Расхождение было возможно, потому что индекс лежал рядом с данными и писался отдельным шагом.

Теперь отдельного индекса у курса нет. Шапка `vms/archive.py` говорит это одной строкой:

```python
#   a span         what the index says one stream holds, `(unit, epoch, start, end, bytes, source)` — read
#                  from the engine every time, never kept beside it
```

Спан (то, что индекс тома говорит об одном потоке) курс каждый раз спрашивает у движка и нигде не сохраняет. Значит, сохранённой копии, которая разошлась бы с томом, не существует.

Остаётся вопрос, который `repair` закрывал вторым: что с записью, если процесс упал посреди неё. Его закрывает демон. Тест `test_obsd.py::test_one_writer_per_volume_and_a_vanished_one_waits_for_its_owner` убивает сессию регистратора без `BYE` и проверяет три вещи:

- демон закрывает открытые последовательности сам, и взятое не теряется;
- писатель остаётся смонтированным, *отсоединённым*, и ждёт `OBSD_WRITER_GRACE_S` того же `owner`;
- регистратор, запущенный заново с `rec:<volume>`, получает того же писателя (`reattached: true`), и шва в записи нет.

Если владелец не вернулся, демон по истечении срока закрывает писателя чисто, и следующий монтирующий **на этом хосте** находит чистый том (`test_after_the_grace_the_volume_is_clean_for_anybody`). Для сетевого тома, который за это время взяла другая коробка, это закрытие пришлось бы на чужой том — и его останавливает сам движок: с патчем 07, который курс требует, писатель, чей замок стал чужим, не пишет ничего, и чужой lock-файл не снимается (урок 6, шаг 12). Том, который не был чисто размонтирован, движок сам не восстанавливает: монтирование отвечает `VOLUME_UNCLEAN`. Раньше это было `away` навсегда, и `VOLUME_RECOVER` не звал никто (пятое ревью). Теперь его зовёт регистратор, который держит том, — только под холдом, подтверждённым в эту секунду, и с тревогой `archive.volume.recovered` (урок 10, шаг 11).

На долю курса остаётся порядок ухода с тома. Его держит `Archive.close`:

```python
    def close(self, timeout: float | None = None) -> bool:
        """The writer closed — after its flush — and the volume let go. In that order: closing is what makes the
        last minutes readable, and a volume released first would be somebody else's with a writer still in it.
        …
```

Сначала закрыть писателя, потом отпустить удержание тома. Обратный порядок даёт два писателя в одном томе. `False` значит, что писатель, может быть, ещё жив в сессии (закрытие или монтирование без ответа), и сессию надо оставить (урок 6, шаг 4). А писателя сетевого тома, чей холд уже потерян, регистратор не закрывает, а бросает (`WRITER_ABANDON`), и считает, сколько взятого тот не успел записать (урок 10, шаг 11). Подробно это разобрано в [уроке 10](10-recworker.md) (`test_rec_volume.py::test_leaving_a_volume_closes_its_writer_before_the_hold_goes`).

## Шаг 2 — Записано не значит видно

Это правило движка, и половина логики регистратора выводится из него. Шапка `archive.py`:

```python
#   visibility     a reader sees only CLOSED blocks, and only those closed when it mounted. So every question
#                  is asked of a fresh reader, and what was written a minute ago may not be an answer yet: the
#                  recorder plans by what it can SEE (`RecWorker.gaps`), and a writer is closed and opened again
#                  (`Archive.seal`) when the minutes just written have to be readable now
```

Читатель видит только закрытые блоки. Блок закрывается, когда заполнен, когда писателя закрывают — или через `blockFlushPeriodSec` после того, как законченная последовательность легла в очередь движка (урок 6, шаг 8; периоды задаёт `Archive._configure`, урок 7). `WRITER_FLUSH` кладёт хвост на носитель, но блок не закрывает. Тест `test_obsd.py::test_a_reader_sees_only_closed_blocks_and_only_what_was_there_when_it_mounted` проверяет это по шагам: после `flush` читатель не видит ничего, после `close` новый читатель видит всё, а читатель, смонтированный раньше, по-прежнему не видит ничего.

Из последнего пункта следует первое решение: **каждый вопрос задаётся свежему читателю**.

```python
    @contextmanager
    def reading(self):
        try:
            r = self._open_volume().mount_ro()
        except (ObsdError, ValueError) as e:
            raise self._classified(e) from None
        try:
            yield r
        except ObsdError as e:
            raise self._classified(e) from None
        finally:
            try:
                r.close()
            except ObsdError:
                pass
```

Держать одного читателя долго было бы дешевле. Но такой читатель застыл бы в моменте своего монтирования, и таймлайн через час показывал бы часовой давности картинку. И читатель у каждого вопроса свой, а закрывается он в `finally`: общий читатель, которого закрывал следующий вопрос, обрывал дверь посреди ответа (третье ревью, блокер 5; урок 7, шаг 9). Вызывающий пишет `with store.reading() as r:`.

Второе решение — `seal`, для случаев, когда только что записанное нужно увидеть сейчас:

```python
    def seal(self) -> None:
        """Close the writer and take it again: its last block is closed, and what was written is readable. What
        a recorder does when the minutes it just wrote must be an answer now — a copied range, a stop."""
        if self.writer is None:
            return
        self._fenced("WRITER_CLOSE")               # a close is the writer's last write: under the same fence
        w, self.writer = self.writer, None
        self.taken, self._recent = {}, {}          # the close is the flush: what was taken is written
        try:
            w.close()
        …
        try:
            self.writer = self._mount_rw(self._open_volume())
        …
        self._configure()
```

Что `seal` делает, когда закрытие не вернулось, и почему писатель забывается до закрытия, — урок 7, шаг 9.

В коде регистратора `seal` зовёт копирование удержаний: скопированное должно быть видно, чтобы его посчитать и взять от него sha256.

```python
                if rec in touched:
                    self.store.seal()                    # what was copied is readable now — and counted below
```

Тесты зовут `seal` постоянно, и `footage` из `conftest.py` делает это по умолчанию. Тест `test_lesson3_archive.py::test_written_is_readable_once_its_block_is_closed` показывает разницу в две строки: после записи `coverage("7") == []`, после `seal()` — `[(t, t + 600)]`.

Третье следствие касается того, как регистратор планирует. Его собственный взгляд на запись — `our_coverage`, и это тоже вопрос свежему читателю:

```python
    def our_coverage(self, unit) -> list[tuple[float, float]]:
        if self.store is None:
            return []
        try:
            return self.store.coverage(str(unit), self.stitch)
        except ArchiveError:
            return []
```

Дыры для дозаписи (урок 16) регистратор ищет только до конца видимого покрытия. Комментарий над `gaps` объясняет почему:

```python
    # Not newer than what we can SEE (the feedback's Q). A reader sees only closed blocks, and a block closes
    # when the next begins — minutes, at a low bitrate. Everything after the end of our visible coverage is
    # either being written this minute or written and not yet visible, and there is no need to tell the two
    # apart: neither is a gap.
```

Без этой границы регистратор принимал бы за дыру то, что сам пишет прямо сейчас, и тянул бы эти минуты с карты камеры повторно. Та же причина у памяти `landing`: только что скопированный диапазон невидим, пока не закрылся его блок, и он не дыра (`test_rec_volume.py::test_footage_fetched_into_a_gap_goes_into_the_backfill_stream_and_waits_to_be_seen`).

## Шаг 3 — Срок хранения — это потолок

Тест `test_obsd.py::test_the_volume_is_a_ring_and_its_oldest_minutes_go_first` пишет 22 МБ в том на 16 МБ. Никто ничего не удалял, а первых секунд в томе больше нет: кольцо перезаписало свои старейшие блоки. Признак замкнутого кольца — `firstBlockId > 0` в `READER_STATUS`.

Шапка `archive.py`:

```python
#   the ring       a volume is formatted at its quota and overwrites its oldest blocks when full. Nothing is
#                  deleted by age: `retention_days` is a CEILING on what the doors show (`visible_from`), and
#                  how deep the archive really is, is read off the index (`depth_days`)
```

Движок по сроку ничего не удаляет. Сколько дней видео лежит в томе, решает его размер — квота, заданная при форматировании. Поэтому поле `retention_days` в строке записи больше не управляет удалением. Оно задаёт, насколько далеко назад двери **показывают** запись:

```python
CEILINGS = Table("ceiling", "nothing of that recording is shown, and nothing fetched for it, until it is mended",
                 "recording's retention_days")


def visible_from(row: dict | None, now: float) -> float:
    """`retention_days` is a ceiling on what the doors show — the ring decides what is still THERE."""
    raw = (row or {}).get("retention_days")
    if not raw or str(raw).strip() in ("", "None"):
        return now - 30 * 86400
    key = f"rec/recordings/{(row or {}).get('id', '?')}#retention_days"
    try:
        days = finite(raw)
        if days < 0:
            raise ValueError(f"{raw!r} is not a number of days")
    except PARSE_ERRORS as e:
        CEILINGS.garbled(key, e)
        return now
    CEILINGS.parsed(key)
    return now - days * 86400
```

Зачем потолок, если удалить по нему нельзя? У части установок обещание звучит так: «никто не видит больше недели». Это обещание о видимом, и дверь может его сдержать, даже когда кольцо держит месяц.

Записи без строки достаются тридцать дней, а не «всё». Строки нет, например, когда запись только что удалили. Показать всё, что ещё лежит в кольце, значило бы открыть то, что строка ограничивала. Тридцать дней достаются и строке, где поле не задано.

**Срок, который не читается, прячет всё старше «сейчас», а не откатывается к тридцати дням.** Раньше функция читала поле через `float(...)`. Слово вылетало исключением из двери и из плана дозаписи, `nan` давал потолок, под которым и над которым нет ни одного момента, `inf` открывал всё кольцо, а `-1` прятал даже сутки вперёд. Тридцать дней тоже не годятся как запасной ответ: строка с неделей обещала «не больше недели», и откат нарушил бы это обещание. Поэтому `visible_from` принимает только конечное неотрицательное число (`finite` из `w2cplatform/rows.py`). На всё остальное она возвращает `now`: дверь не показывает ничего старше текущего момента, дозапись ничего не планирует, а само видео в кольце не трогается. Такая строка учитывается один раз в таблице `CEILINGS` (в heartbeat регистратора это `ceilings_garbled`), её имя попадает в журнал, а исправленная строка выходит из списка через `CEILINGS.parsed`. Тест `test_garbled_rows.py::test_a_recordings_ceiling_that_is_no_number_of_days_hides_and_does_not_fall_back_to_thirty` проверяет `"ten"`, `"nan"`, `"inf"`, `"-1"` и список `["7"]`: на каждый ответ — `now`, счётчик — один, а `"0"` — ровно `now`, потому что ноль дней — это то, что сказано.

Дверь применяет потолок к **ответу**, а не к вопросу. Сначала она собирает, что можно показывать: всё от `visible_from` и всё, что держат удержания:

```python
            # Retention is a ceiling on what the door shows: from `visible_from` on, and whatever a keep holds. A span
            # that began before the ceiling is CUT at it — drawn from its start, it would be footage the page shows
            # and the door then refuses to play.
            shown = stitch([(visible_from(unit), float("inf"))] + [tuple(k) for k in kept(unit)], 0.0)
```

Потом каждый спан таймлайна обрезается по этим интервалам, а кадры читаются только внутри них (шаг 7).

Почему не обрезать начало вопроса, `t0 = max(t0, visible_from(unit))`? Так дверь работала раньше, и у этого была дыра. Движок отдаёт интервал целиком, если тот пересекает окно. Непрерывная запись, начавшаяся раньше потолка, возвращалась одним спаном со своим настоящим началом. Страница рисовала двенадцать дней, а `/samples` за первые четыре не отдавал ни кадра: видео на экране есть, а играть нечего.

Тест `test_lesson3_archive.py::test_retention_is_a_ceiling_on_what_is_shown_and_the_ring_decides_what_is_there` пишет три отрезка: 1, 10 и 19 октября. При `retention_days: 8` и «сейчас» 20 октября дверь показывает один отрезок, а `st.spans("7")` по-прежнему находит три. Там же проверено умолчание: `visible_from(None, now) == now - 30 * 86400`.

`test_review_remainder.py::test_the_door_cuts_a_span_at_the_ceiling_and_shows_what_a_keep_holds_behind_it` пишет двенадцать дней одним спаном и ставит `retention_days: 8`:

```python
    assert spans() == [(now - 8 * DAY, now)]                           # cut at the ceiling, not drawn from twelve days ago
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] == b""
```

Три исключения из потолка стоит знать.

**Удержание видно за потолком.** Удержание — слово оператора, что эти минуты важнее срока записи:

```python
    # The intervals of a recording somebody said to keep (`vms/keeps.py`): the door shows them whatever the ceiling,
    # because a keep is the operator's word that those minutes matter longer than the recording's days — and the
    # recorder copying keeps into an incidents volume reads them through this very door. Not readable is none:
    # the ceiling stands, which hides, and hiding is the side to err on.
    def _kept_of(self, unit) -> list[tuple[float, float]]:
        from . import keeps
        try:
            declared = keeps.declared(self.vars)
        except OSError:
            return []
        row = self._rows_seen.get(str(unit)) or {}
        return keeps.spans_of(declared, str(unit), str(row.get("cam", "")))
```

Через эту же дверь регистратор тома `incidents` копирует удержания. Поэтому удержание старше срока записи тоже доходит до копии, пока кольцо его не перезаписало ([урок 18](18-what-the-archive-gives-up-first.md)). Удержания не прочитались — их нет, и потолок стоит: спрятать безопаснее, чем показать лишнее. Вторая половина того же теста ставит удержание на минуты одиннадцать–десять дней назад, и дверь показывает его отдельным спаном и отдаёт его кадры:

```python
    keeps.write(box.vars, {"cam": "7", "from": now - 11 * DAY, "to": now - 10 * DAY}, ["7"], "anna", now)
    assert spans() == [(now - 11 * DAY, now - 10 * DAY), (now - 8 * DAY, now)]
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] != b""
```

**Том `incidents` показывает всё:**

```python
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
```

Всё, что лежит в таком томе, кто-то отметил к удержанию. Прятать это по сроку обычной записи значило бы прятать улики.

**И потолок не обещает глубины.** Сколько дней запись должна **держать**, говорит поле `min_depth_days`, и его никто не исполняет: кольцо отдаёт старое, что бы ни обещали. Регистратор это наблюдает и поднимает тревогу `archive.shallow`, когда кольцо замкнулось, а запись держит меньше обещанного (`depth_pass`; [урок 18](18-what-the-archive-gives-up-first.md)).

События живут по третьему правилу, и в `archive.py` их нет. Бакеты событий удаляет платформенный ресурс по строке `vms/retention/<cam>` (М10A, урок 14; [урок 11](11-the-resource-process.md)). Тест `test_lesson3_archive.py::test_events_are_buckets_on_the_resource_recording_or_not` проверяет обе стороны: проход ресурса удаляет два старых бакета, а покрытие записи после него то же, что было до.

## Шаг 4 — Строка, которую хранилище не отдало

Дверь читает строку записи на каждый вопрос: её срок могли поменять минуту назад. Значит, хранилище может не ответить посреди вопроса. Наивный код прочитал бы отказ как «строки нет» и показал бы тридцать дней.

```python
    # A row the store did not GIVE is not a row that is gone (feedback BI). Read as "gone" it would show a week's
    # recording for thirty days, or hide ninety days' recording past thirty, for as long as the store blinked. So
    # the door answers on what the row said last; thirty days only for a recording it has never read.
    def _visible_from(self, unit) -> float:
        from .archive import visible_from
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
        try:
            items, _ = self.vars.get(self.SUB.config(self.ROWS, str(unit)))
            row = self._rows_seen[str(unit)] = items if items and items.get("deleted") != "true" else None
        except OSError:
            row = self._rows_seen.get(str(unit))
        return visible_from(row, self.wall())
```

Ошибка по умолчанию стоила бы двух разных неприятностей. Запись со сроком в неделю на время сбоя показала бы тридцать дней, и обещание «не больше недели» нарушилось бы. Запись со сроком в девяносто дней спрятала бы два месяца, и оператор решил бы, что их нет.

Поэтому три случая различаются явно:

- хранилище ответило, строка есть — её срок, и строка запоминается в `_rows_seen`;
- хранилище ответило, строки нет (или она помечена `deleted`) — тридцать дней, и это тоже запоминается;
- хранилище не ответило — последняя прочитанная строка; тридцать дней только для записи, которую дверь не читала ни разу.

Тест `test_review_remainder.py::test_a_store_that_did_not_answer_is_not_a_knob_that_is_off_nor_thirty_days` пишет по сорок дней записей `7` и `8`. У `7` срок девяносто дней, у `8` строки нет. Потом хранилище перестаёт отдавать `rec/recordings/*`, а дверь по-прежнему показывает `7` и не показывает `8`. Первая половина того же теста проверяет то же правило у ватерлинии ресурса (М10A, урок 14): «не прочитал настройку» не значит «настройка выключена».

## Шаг 5 — Таймлайн из индекса

```python
    def spans(self, unit=None, t0: float | None = None, t1: float | None = None, reader=None) -> list[Span]:
        """What the index holds — of one recording, or of all — as spans, in time order. One question, one
        reader: `reader` is the one the caller already mounted, if it is asking more than this."""
        if reader is None:
            with self.reading() as r:
                return self.spans(unit, t0, t1, reader=r)
        r = reader
        lo = archive_ms(t0) if t0 is not None else NEVER
        hi = archive_ms(t1) if t1 is not None else FOREVER
        out = []
        for name in r.streams():
            p = parse_stream(name)
            if p is None or (unit is not None and p[0] != str(unit)):
                continue
            for iv in self._timeline(r, name, lo, hi):
                out.append(Span(p[0], p[1], unix_s(iv["start"]), unix_s(iv["end"]), int(iv.get("size", 0)), p[2]))
        return sorted(out, key=lambda s: (s.start, s.epoch))
```

**Все потоки записи.** У одной записи в томе может быть несколько потоков: `7/e3` и `7/e4` после смены владельца, `7/e4/backfill` с дозаписанным из карты, `7/e0` с копией удержания. Таймлайн записи — это все они. `parse_stream` отсеивает потоки, которые не принадлежат записям; имя записи сравнивается как строка, поэтому `7-cloud` работает так же, как `7`.

**Один вопрос — один читатель.** Параметр `reader` нужен `samples`: он спрашивает спаны и тут же читает кадры, и оба шага должны видеть одну и ту же картину тома.

**Сортировка по `(start, epoch)`.** Один интервал может быть записан дважды разными эпохами, и порядок обязан быть определённым.

Теперь `_timeline` — место, где курс обходит поведение движка, которого нет в документации протокола.

```python
    # A stream's timeline, asked IN WINDOWS. The engine answers `INTERNAL_ERROR` to some timeline questions over
    # six days of footage or more (obsd protocol v1 — seen, not documented, and not every time: the same question
    # is refused by one daemon and answered by the next). Five days has never been refused. A recording is a
    # month deep, so the question is cut to what the stream holds — its first and last sequence — and asked five
    # days at a time; a window refused anyway is asked again in halves, down to an hour. Intervals that touch
    # across a cut are put back together.
    def _timeline(self, r, name: str, lo: int, hi: int) -> list[dict]:
        first, last = r.find(name, lo), r.find(name, hi, backwards=True)
        if first is None or last is None:
            return []
        lo, hi = max(lo, min(first.start, hi)), min(hi, max(last.end, lo))
```

`READER_TIMELINE` над шестью днями записи и больше иногда отвечает `INTERNAL_ERROR`. Иногда — то есть один демон отказывает, а следующий на тот же вопрос отвечает. Повторять тот же вопрос поэтому бесполезно: нельзя знать, повезёт ли.

Решение в три части, и у каждой своя причина.

**Сначала вопрос обрезается по самому потоку.** `READER_FIND` находит первую и последнюю последовательность. Вопрос «с 1900 года до бесконечности» превращается в вопрос о том, что поток держит на самом деле, и окон становится столько, сколько нужно.

**Потом окна по пять дней.** `TIMELINE_WINDOW = 5 * 86400 * 1000` — миллисекунды архива. Окно длиннее отвергал демон до патча 05 — `INTERNAL_ERROR [volume-error:6]` на шести днях, — и это была ошибка движка, не правило протокола: таймлайн читает индекс по срезу на каждый час окна и отдавал все чтения в очередь пула разом, а очередь — 128; пять дней — 120 срезов, шесть — 144 (обратная связь CQ). Патч отдаёт чтения порциями, и длина окна больше ничем не ограничена. Окна остались как страховка от демона без патча: лишний вопрос стоит одного обращения, а отказ на нём стоил бы таймлайна.

**Отвергнутое окно спрашивается половинами, до часа:**

```python
        def ask(a: int, b: int) -> None:
            try:
                got = r.timeline(name, a, b)
            except ObsdError as e:
                if e.name != "INTERNAL_ERROR" or b - a <= 3600_000:
                    raise
                ask(a, (a + b) // 2); ask((a + b) // 2, b)
                return
```

Половинить имеет смысл только этот отказ и только на длинном окне. Любой другой статус и `INTERNAL_ERROR` на окне в час — уже не тот случай, и ошибка поднимается дальше: прятать её значило бы рисовать дыру, которой нет.

Последняя часть — склейка. Интервал, разрезанный границей окна, приходит двумя кусками. Код соединяет куски, которые касаются, и складывает их размеры. Без этого месячная непрерывная запись рисовалась бы шестью отрезками с подозрительными швами каждые пять дней.

Тест `test_obsd.py::test_a_recording_a_month_deep_is_answered_whole` пишет тридцать дней с одной дырой и проверяет, что покрытие — ровно два отрезка, а `depth_days` — ровно `30.0`.

Над спанами строятся три ответа.

```python
    def timeline(self, unit, t0: float, t1: float, current_epoch: int | None = None) -> list[dict]:
        """Spans overlapping `[t0, t1)`, each marked `fenced` when its epoch is older than the current one — how
        the page shows a zombie's footage, kept and told apart."""
        return [{"start": s.start, "end": s.end, "epoch": s.epoch, "source": s.source, "bytes": s.bytes,
                 "fenced": current_epoch is not None and s.epoch < current_epoch}
                for s in self.spans(unit, t0, t1) if s.end > t0 and s.start < t1]
```

**`timeline`** — для страницы. Пересечение с окном строгое с обеих сторон: спан, кончившийся ровно в `t0`, в окно не попадает. Отсечение — одно сравнение чисел: эпоха потока меньше текущей эпохи записи. Эпоха лежит в имени потока, и другого места для неё нет. Без `current_epoch` ничего не помечается: если текущая эпоха неизвестна, честнее показать всё, чем объявить что-то недостоверным.

**`coverage`** — для регистратора: спаны всех потоков, склеенные `stitch` с зазором `STITCH = 2.0` секунды.

```python
STITCH = 2.0         # seconds: two spans closer than this are one run — the seam between two sequences is no gap
```

Шов между двумя последовательностями — не дыра. Без допуска каждый шов стал бы задачей для дозаписи.

**`depth_days`** — сколько дней назад уходит запись, от первого отрезка покрытия. Это число регистратор кладёт в статус и на `/metrics` (`rec_archive_depth_days`).

## Шаг 6 — Две эпохи над одними минутами

Регистратор, отсечённый посреди записи, ещё какое-то время пишет свой поток. Рядом выживший пишет свой, под следующей эпохой. Тест `test_lesson3_archive.py::test_the_timeline_marks_a_fenced_epoch_and_spans_two_volumes` строит ровно это: `7/e3` с 0 до 900 секунд и `7/e4` с 600 до 1200.

```python
    tl = st.timeline("7", t + 300, t + 1800, current_epoch=4)
    assert [(x["epoch"], x["start"] - t, x["end"] - t, x["fenced"]) for x in tl] == [(3, 0, 900, True), (4, 600, 1200, False)]
```

**Таймлайн показывает обе эпохи.** Ничего не перезаписано: это два потока одного тома. Минуты зомби — настоящее видео настоящей камеры, у писавшего просто не было на них права. Страница рисует их бледным интервалом. Спрятать их значит потерять запись, которая может оказаться единственной.

Вторая половина теста — второй том, с записью под эпохой 5. Таймлайны двух томов складываются и сортируются, и получается `[3, 4, 5]`. Так консоль собирает таймлайн из дверей нескольких регистраторов ([урок 12](12-the-vms-console.md)).

**Кадры же нужны по одному на момент.** Экспорт, скан и копия удержания не могут взять минуты 600–900 дважды. Это решает `authoritative`:

```python
# Every stretch of `[t0, t1)` the spans cover, each given to the HIGHEST EPOCH there. Two epochs overlap
# whenever a writer was fenced with footage in flight; read both and those minutes come twice, drop every
# older epoch and the minutes only it held disappear. So the unit of the decision is the stretch:
# `[(span, lo, hi)]`, in time order.
def authoritative(spans: list[Span], t0: float, t1: float) -> list[tuple[Span, float, float]]:
    edges = sorted({t0, t1} | {s.start for s in spans} | {s.end for s in spans})
    edges = [e for e in edges if t0 <= e <= t1]
    out: list[list] = []
    for lo, hi in zip(edges, edges[1:]):
        if hi <= lo:
            continue
        covering = [s for s in spans if s.start <= lo and s.end >= hi]
        if not covering:
            continue
        best = max(covering, key=lambda s: (s.epoch, s.source == "live"))
```

Комментарий называет оба неверных решения. Взять все эпохи — минуты перекрытия придут дважды, и скан посчитает каждую машину два раза. Отбросить старшие эпохи целиком — исчезнут минуты 0–600, которые держала только эпоха 3.

Поэтому единица решения — **отрезок** (часть спана, отданная одному читателю): интервал между двумя соседними границами любых спанов. Каждый отрезок получает старшую эпоху из покрывающих его. При равной эпохе живой поток побеждает дозаписанный. Соседние отрезки одного спана склеиваются.

У этого правила есть следствие для удержаний. Копия в томе `incidents` пишется в поток `<запись>/e0`. Эпоха ноль — ничья аренда. Где живая запись ещё существует, её эпоха старше и владеет этими минутами. Где кольцо её уже забрало, остаётся копия.

`stream` читает кадры по этим отрезкам, `samples` собирает их в список:

```python
    def samples(self, unit, t0: float, t1: float) -> list[Sample]:
        """The frames of `[t0, t1)`, each stretch from the epoch that owns it, each starting on the key frame AT
        OR BEFORE its first moment — what an export, a scan or a copy into another volume takes. A stretch that
        opens at 10:05 is inside a group of pictures that opened at 10:04:58, and without that key frame nothing
        of 10:05 decodes: the lead-in comes along, and whoever asked clips it (`Scan.accepts`). All of it, in a
        list: for a short range. A long one is `stream`ed."""
        return list(self.stream(unit, t0, t1))

    def stream(self, unit, t0: float, t1: float):
        with self.reading() as r:
            for span, lo, hi in authoritative(self.spans(unit, t0, t1, reader=r), t0, t1):
                a, b = archive_ms(lo), archive_ms(hi)
                lead: list[Sample] = []                  # since the last key frame, until the stretch's first moment
                started = False
                for e in r.sequences(span.stream, a, b):
                    for smp in r.read(e):
                        if smp.begin >= b:
                            break
                        if started:
                            yield smp
                            continue
                        if smp.key:
                            lead = []
                        lead.append(smp)
                        if smp.end > a:                  # the first moment: from the key frame at or before it
                            started = True
                            k = next((i for i, x in enumerate(lead) if x.key), None)
                            yield from (lead[k:] if k is not None else [])
                            if k is None:                # no key frame at or before: the stretch opens on its next one
                                started = False
                            lead = []
                    else:
                        continue
                    break
```

**Кадры идут потоком, по последовательности.** Сутки камеры — десятки гигабайт, и список всех кадров держал бы их в памяти целиком (третье ревью, блокер 6): `stream` держит последовательность и подводку от ключевого кадра, а читатель — пока кадры берут, и закрывается, когда их взяли или перестали брать.

**Отрезок начинается с ключевого кадра на его первом моменте или раньше.** Момент, о котором спросили, лежит внутри группы кадров, открытой раньше. Декодер не начнёт с промежуточного кадра, а движок не примет последовательность без ключевого (`SEQUENCE_NEEDS_KEY_SAMPLE`), если эти кадры копируют в другой том. Начать со следующего ключевого — значит потерять начало отрезка: до целой группы кадров на каждом стыке эпох и в начале каждого вопроса. Поэтому `stream` (а `samples` — тот же поток, собранный в список, для короткого промежутка) отступает назад до ключевого кадра, и подводка приходит вместе с ответом. Обрезает её тот, кто спросил: скан считает только то, что попало в `[t0, t1)` (`Scan.accepts`, урок 20). Следующий ключевой берётся, только если раньше ключевого нет вовсе.

`test_review_remainder.py::test_a_read_starts_on_the_key_frame_before_the_moment_asked_for` пишет сто секунд с ключевым кадром каждые две и спрашивает с `t - 51`:

```python
    got = st.samples("7", t - 51, t - 40)
    assert got[0].key and unix_s(got[0].begin) == t - 52               # the group's key frame, a second before
```

Правило проверяет `test_scan.py::test_two_epochs_over_the_same_minutes_the_later_one_owns_them`: план скана строится тем же `authoritative` (урок 20).

## Шаг 7 — Дверь архива

Регистратор держит том, и только он открывает его на запись. Читать нужно многим: консоли, скану, резервной записи, копированию удержаний. Дверь архива — HTTP регистратора над его томом:

```python
# A recorder's archive door, over the volume it holds: what a primary copies from a backup, and what the console
# draws and plays. Two reads, both from a FRESH reader — a reader sees what was closed when it mounted:
#
#   GET /timeline/<unit>?from&to   {"spans": [{start, end, epoch, source, bytes, fenced}], "current_epoch"}
#   GET /samples/<unit>?from&to    the frames, SMPL records one after another — each stretch from the epoch that
#                                  owns it, from a key frame (`Archive.samples`)
def archive_routes(store_of, wall, current_epoch=lambda unit: None, visible_from=lambda unit: 0.0, kept=lambda unit: []):
```

Почему регистратор, а не ресурс сервера, как раньше? Том открывается через `obsd` того хоста, где он смонтирован, а держит его один регистратор. Читатель в другом процессе того же хоста тоже был бы возможен. Но регистратор уже держит том, знает эпохи своих записей и читает их строки. Дверь в нём пользуется этим, а не заводит второй источник тех же сведений, который мог бы с первым разойтись.

Разбор пути:

```python
        for prefix in ("/timeline/", "/samples/"):
            if not u.path.startswith(prefix):
                continue
            unit = u.path[len(prefix):]
            if not safe_segment(unit):
                return 404, b"", "text/plain"
            store = store_of()
            if store is None:
                return 503, b'{"error": "no volume open here"}', "application/json"
            try:
                t0, t1 = float(q.get("from", 0)), float(q.get("to", wall() + 86400))
            except ValueError:
                return 400, b'{"error": "from and to are unix seconds"}', "application/json"
```

**Путь называет запись, и только её.** `safe_segment` (из `w2cplatform/doors.py`) пропускает одно имя без слэшей и без `..`. Ни одна часть пути не доходит до диска: регистратор спрашивает том про поток записи. Тест `test_doors.py::test_a_recorders_archive_door_names_a_recording_and_nothing_else` проверяет `404` на `/timeline/..` и `/samples/a/b`, `400` на `from=x` и `404` на старый `/manifest/7`.

**Тома нет — `503`, а не `404`.** Регистратор может стоять запасным или ждать удержания. Это «сейчас нельзя», а не «записи нет».

`store_of` — функция, а не том. Регистратор меняет том (переоткрывает после потери демона, отдаёт неверный, берёт новый), и дверь каждый раз спрашивает текущий.

Ответы:

```python
            shown = stitch([(visible_from(unit), float("inf"))] + [tuple(k) for k in kept(unit)], 0.0)
            try:
                if prefix == "/timeline/":
                    cur = current_epoch(unit)
                    spans = []
                    for sp in store.timeline(unit, t0, t1, cur):
                        for a, b in shown:
                            lo, hi = max(sp["start"], a), min(sp["end"], b)
                            if hi > lo:
                                spans.append({**sp, "start": lo, "end": hi})
                    body = {"unit": unit, "spans": spans, "current_epoch": cur}
                    return 200, json.dumps(body).encode(), "application/json"
                frames = b""
                for a, b in shown:
                    lo, hi = max(t0, a), min(t1, b)
                    if hi > lo:
                        frames += b"".join(smp.encode() for smp in store.samples(unit, lo, hi))
                return 200, frames, "application/octet-stream"
            except ArchiveError as e:
                return 503, json.dumps({"error": str(e)}).encode(), "application/json"
```

Таймлайн и кадры режутся одними и теми же интервалами `shown`. Поэтому всё, что страница нарисовала, дверь и сыграет, а за потолком нет ни спана, ни кадра — кроме удержанного.

`/samples` отдаёт записи `SMPL` подряд — тот же формат, что ходит между процессом и `obsd`. Получатель разбирает их `Sample.decode_all` и получает кадры с теми временами, с которыми они были записаны. Резервная запись кладёт их в свой том как есть, консоль собирает из них MP4 (урок 12).

`current_epoch` двери — эпоха **этого** регистратора для записи: `lambda unit: self.epochs.get(str(unit))` в `serve_archive`. Дверь знает только свою эпоху. Запись, которую держит другой регистратор, дверь не отсекает; это делает консоль по строке эпохи записи в хранилище (урок 12).

`serve_archive` поднимает дверь со всеми функциями регистратора и объявляет её адрес:

```python
        routes = archive_routes(lambda: self.store, self.wall, lambda unit: self.epochs.get(str(unit)), self._visible_from,
                                self._kept_of)
        self.archive_url = f"http://{announce_host(host, self.server)}:{srv.server_address[1]}"   # what it bound: loopback, or this server's name — never `0.0.0.0`
```

Адрес уходит в heartbeat регистратора как `archive_url`, рядом с именем тома. По нему двери находят все читатели — тем же приёмом, каким регистратор находит камеру. Регистратор с другого сервера не пойдёт на дверь, объявленную на loopback чужого сервера (`local_only` в `backup_sources`).

Тест `test_rec_volume.py::test_the_archive_door_hands_out_timelines_and_frames` проходит дверь целиком: таймлайн за двести секунд даёт один спан без отсечения, а `/samples` за сорок секунд начинается с ключевого кадра и кончается не позже чем через секунду после конца окна.

## Результат

```
GET /timeline/7?from=…&to=…   (дверь регистратора r-1, том srv-1)
→ {"unit": "7", "current_epoch": 4,
   "spans": [{"start": …, "end": …, "epoch": 3, "source": "live", "bytes": …, "fenced": true},
             {"start": …, "end": …, "epoch": 4, "source": "live", "bytes": …, "fenced": false},
             {"start": …, "end": …, "epoch": 4, "source": "backfill", "bytes": …, "fenced": false}]}

GET /samples/7?from=…&to=…
→ SMPL SMPL SMPL …   каждая минута от своей эпохи, первый кадр — ключевой
```

```python
st.coverage("7")          # [(…, …), (…, …)] — склеено через швы последовательностей
st.depth_days("7", now)   # 30.0 — из индекса, а не из настройки
st.spans("7")             # всё, что в кольце, — и то, что дверь уже не показывает
```

## Что может пойти не так

- **Один долгоживущий читатель.** Он видит том на момент своего монтирования, и таймлайн стареет вместе с ним.
- **Считать записанное видимым.** Регистратор примет за дыру то, что пишет сейчас, и потянет те же минуты с карты.
- **Удалять по `retention_days`.** Движок по сроку не удаляет, а кольцо уже держит ровно столько, сколько помещается.
- **Считать потолок обещанием глубины.** Запись с потолком в тридцать дней на маленьком томе держит четыре, и узнать об этом можно только по `archive.shallow`.
- **Тридцать дней, когда хранилище не ответило.** Неделя показана месяцем или девяносто дней спрятаны за тридцатью, пока хранилище моргает.
- **Один вопрос таймлайна на весь месяц.** Движок иногда отвечает `INTERNAL_ERROR`, и запись выглядит пустой.
- **Половинить любую ошибку.** Настоящий отказ тома превратится в пустой таймлайн вместо ошибки.
- **Прятать отсечённое.** Потеряете единственную запись момента, ради которого архив держат.
- **Отбрасывать старшие эпохи целиком при чтении кадров.** Исчезнут минуты до смены владельца, которые держала только старая эпоха.
- **Брать все эпохи при чтении кадров.** Скан посчитает минуты перекрытия дважды.
- **Путь двери, доходящий до диска.** Через имя записи можно будет прочитать любой файл машины.
- **Потолок на начало вопроса, а не на спаны ответа.** Запись, начавшаяся до потолка, нарисована целиком, а дверь не играет ничего до потолка.
- **Потолок и для удержаний.** Оператор удержал минуты, а дверь их прячет, и копия в томе `incidents` не получает того, что старше срока записи.
- **Начинать отрезок со следующего ключевого кадра.** На каждом стыке и в начале каждого вопроса пропадает до целой группы кадров.

## Итог

- Курсу нечего чинить: спан читается у движка каждый раз и нигде не хранится, вернувшегося писателя отдаёт демон, нечистый том восстанавливает движок.
- Читатель видит только закрытые блоки и только те, что были закрыты при его монтировании. Поэтому каждый вопрос — свежему читателю, регистратор планирует по видимому, а `seal` делает записанное видимым сейчас.
- Том — кольцо: что в нём есть, решает квота. `retention_days` — потолок того, что показывают двери: спан, начавшийся раньше, обрезается по нему, а удержанное видно и за ним. `min_depth_days` — пол, который наблюдают, а не исполняют.
- Строка, которую хранилище не отдало, — не отсутствующая строка: дверь отвечает по последней прочитанной.
- Таймлайн строится по всем потокам записи, окнами по пять дней — страховка от демона без патча 05, — с половинением отвергнутого окна до часа.
- Таймлайн показывает обе эпохи и помечает отсечённую. Кадры каждого отрезка берутся от старшей эпохи, начиная с ключевого кадра на его первом моменте или раньше; подводку обрезает тот, кто спросил.
- Дверь архива называет запись и ничего больше; её адрес лежит в heartbeat регистратора.

## Упражнения

1. Держите одного читателя на всё время жизни `Archive`. Запишите десять минут, закройте писателя и спросите таймлайн. Что вы увидите и почему?
2. Уберите `seal()` из `keep_pass`. Что станет с `archive.keep.copied` и его sha256 после первого прохода?
3. Уберите из `gaps` границу по видимому концу покрытия. Опишите, что регистратор будет тянуть с карты каждую минуту.
4. Замените в `_visible_from` ветку `except OSError` на `row = None`. Повторите вторую половину `test_a_store_that_did_not_answer_is_not_a_knob_that_is_off_nor_thirty_days` и объясните, какое из двух утверждений упало.
5. Спросите `READER_TIMELINE` о тридцати днях одним вопросом на нескольких запусках демона. Запишите, сколько раз он отказал.
6. Верните в `archive_routes` старую строку `t0 = max(t0, visible_from(unit))` вместо `shown`. Запустите `test_the_door_cuts_a_span_at_the_ceiling_and_shows_what_a_keep_holds_behind_it` и объясните оба упавших утверждения: что увидит страница и чего не получит копия удержаний.
7. Замените в `authoritative` выбор старшей эпохи на выбор младшей. Какие минуты экспорт возьмёт у зомби?
8. Отдайте отсечённые спаны из `timeline` без пометки `fenced`. Опишите, что увидит оператор после смены владельца посреди записи.

## Что дальше

Том пишется, читается и открыт наружу дверью. Писать в него пока нечем: строку конвейера, которая превращает поток камеры в кадры для `RecSink`, никто не собирает.

[**Урок 9**](09-actuators-and-the-fan-out.md) пишет `gstvms/actuator.py` и `gstvms/livesrv.py`: актуаторы, раздачу и путь кадра от камеры до тома.

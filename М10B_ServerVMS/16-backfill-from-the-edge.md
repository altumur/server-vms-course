# Урок 16 — Дозапись из края

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** расширение `vms/recworker.py` — `our_coverage` по индексу тома, `gaps`, `backfill(budget)` и окно; `fetch` и `_land` — посадку выкачанного в поток `<запись>/e<эпоха>/backfill` по последовательности на отрезок; заявки оператора (`requests`, отказы `_range_refusal`) и фоновую нить (`backfill_in_background`); `archive_busy` — когда дозаписи ждать; и границы, найденные, когда этот код стал продуктом: память о том, чего нет нигде, конец видимого вместо отстоя, дыры только внутри записанного, и память о том, что уже отдано, но ещё не видно.
**Время:** ~90 минут.

## Зачем этот урок

Урок 15 показал чужой архив. Этот забирает из него то, что нам нужно, — и превращает в своё.

Начать стоит с вопроса, зачем карта в камере вообще существует. Ответ канонический и один: **камера писала, пока не могли мы.** Пропала сеть между площадкой и сервером, лежал регистратор, перезагружалась коробка, менялся диск. На карте — ровно та дыра, которой у нас нет.

Из этого следует форма работы. Репликация — **не «скопировать всё»**, а «закрыть дыры». А «закрыть дыры» — это сверка двух покрытий: желаемое — непрерывная запись, действительное — то, что показывает индекс нашего тома, разница — что забрать.

**Это цикл сверки из урока 2, применённый ко времени.** Желаемое персистентно, действительное выводится, разница сводится к нулю — та же формула, другой предмет. И это, пожалуй, лучшая проверка того, что цикл был написан достаточно общо: он переносится на задачу, которой при его написании не существовало.

Второе, ради чего урок нужен, — **граница между чужим и нашим**, проведённая одним правилом: лежит в нашем томе или нет. Урок 15 рисует интервалы устройства отдельно и нашими их не называет. Этот урок говорит, что дозаписанное — **уже наше**: наш том, наша эпоха, наши двери.

> **Проверка без железа.** Всё, кроме настоящей выкачки, идёт против живого `obsd` (фикстура в `tests/vmsconftest.py`): у регистратора свой том, кадры поддельного исполнителя (`FakeActuator.record_range`) ложатся в него и читаются обратно из индекса. Тесты урока — в `test_lesson11_edge.py` и `test_backfill_bounds.py`. Настоящий исполнитель (`GstRecActuator.record_range`: `souphttpsrc ! qtdemux ! h264parse ! appsink`) тестами не прогоняется: в наборе нет GStreamer.

## Что нужно знать заранее

- **Урок 15** — `playback_url`, покрытие, вычитание.
- **Урок 2** — цикл сверки: желаемое, действительное, разница.
- **Урок 7** ([том, блок, последовательность, поток](07-volume-block-sequence-stream.md)) — поток `<запись>/e<эпоха>`, последовательность открывается ключевым кадром.
- **Урок 8** ([видимость, хранение, таймлайн](08-visibility-retention-timeline.md)) — читатель видит только закрытые блоки; `retention_days` — потолок того, что показывают двери; кольцо.
- **Урок 10** ([регистратор](10-recworker.md)) — его эпоха, его том, `enrich → None → waiting`.

## Чему вы научитесь

1. Сверять два покрытия и получать список работы вычитанием.
2. Делать фоновую работу ограниченной по объёму и по времени суток.
3. Писать чужие кадры как свои, не путая их происхождение.
4. Не рисовать дыру как запись: последовательность на каждый отрезок.
5. Отличать «не записано» от «записано и ещё не видно».
6. Сказать, что из показанного переживёт ночь.

---

## Шаг 1 — Чья это работа

Две оси снова расходятся: читать карту — сеть камер, писать — том. Тот самый случай, ради которого воркер и регистратор разделены (урок 4).

И разрешается он **тем же способом, каким уже разрешена живая запись**: держатель выставляет, регистратор потребляет.

| | Живая запись | Дозапись |
|---|---|---|
| Держатель публикует | `live_url` | `playback_url` + `coverage` |
| Регистратор подписывается | на поток | на диапазон |
| Пишет | поток `<запись>/e<n>` в свой том | поток `<запись>/e<n>/backfill` в тот же том |
| Дальше | кольцо тома, двери, видимость | то же самое |

**Ни новой подсистемы, ни нового размещения.** Камеру никто не держит — нет и `playback_url`, источников у записи нет (`sources_of` возвращает пусто), и дозаписывать не из чего.

## Шаг 2 — Наше покрытие

```python
    # The card exists because the camera kept recording while we could not, so replication is not "copy
    # everything" — it is the difference between two coverages. Desired: continuous. Actual: what the volume's
    # index shows, every stream of the recording — live and fetched, every epoch. The difference is the work.
    # Lesson 2's loop, over time instead of pipelines.
    def our_coverage(self, unit) -> list[tuple[float, float]]:
        if self.store is None:
            return []
        try:
            return self.store.coverage(str(unit), self.stitch)
        except ArchiveError:
            return []
```

Действительное **выводится из индекса тома** — снова, как везде в курсе: то, что можно посчитать, не хранят. `Archive.coverage` спрашивает свежего читателя о каждом потоке записи (`<запись>/e1`, `<запись>/e2`, `<запись>/e2/backfill`…) и склеивает ответы.

`self.stitch` — допуск на склейку, две секунды (`STITCH = 2.0` в `vms/archive.py`), и без него ничего не работает. Между двумя потоками записи — смена эпохи, перезапуск — и между двумя последовательностями бывает шов: доли секунды на то, чтобы закрыть одно и открыть другое. Считая шов дырой, вы получите десятки «дыр» в сутках и будете дозаписывать по полсекунды каждую.

Допуск в пару секунд склеивает швы и не склеивает настоящие обрывы. Число, которое стоит назвать явно, потому что оно **не очевидно и решает всё**.

И главное свойство этого покрытия: оно **видимое**. Читатель видит только закрытые блоки, а блок закрывается, когда заполнен или через период сброса после конца последовательности (урок 8) — секунды у настроенного движка и минуты у движка до патча 04 (обратная связь CP). Последние минуты живой записи в нашем покрытии ещё не числятся. Шаг 10 вернётся к этому дважды.

## Шаг 3 — Дыры вычитанием

```python
    def gaps(self, unit, coverage: dict, now: float, planned: bool = True, source: str = "device") -> list[tuple[float, float]]:
        from .archive import visible_from
        ours = self.our_coverage(unit)
        row = self._row_of(unit)
        ...
        c = coverage if isinstance(coverage, dict) else {}
        start = number(f"rec/coverage/{source}/{unit}#from", c.get("from"), float, None)
        end = number(f"rec/coverage/{source}/{unit}#to", c.get("to"), float, None)
        if start is None or end is None:
            return []
        lo = max(start, now - self.keep_days * 86400, visible_from(row, now))
        hi = min(end, now - self.settle, ours[-1][1] if ours else now)
        ...
        holes = subtract((lo, hi), ours)
```

**То же правило вычитания, по которому страница рисует шкалу** в уроке 15: наше побеждает. Одно правило, два применения: там оно решает, что показать (страница, по `yields`), здесь — что забрать (`subtract` из `vms/archive.py`). У каждой половины свой тест, и оба держат одно и то же правило.

Начнём с простых границ; остальное в `gaps` — находки с коробки, им посвящён шаг 10.

**Строка записи берётся из словаря, а не обходом.** `_row_of(unit)` собирает словарь «id → строка» один раз на каждый новый список `self.rows` и отвечает из него. Раньше `gaps` искал строку обходом всех строк. Обход на каждую запись — квадрат числа записей за проход, и всё это на Python (проход масштабирования). Тот же `_row_of` даёт строку и заявкам (шаг 8). Тест: `test_recorder_reads.py::test_a_recorders_pass_reads_each_recording_once_not_once_per_recording` — при вдвое большем числе записей проход дозаписи читает хранилище не больше чем вдвое больше раз.

**Сводка источника читается через `rows.number`.** Начало и конец покрытия приходят из чужого heartbeat. Слово в них бросало исключение из дозаписи всех записей после этой (седьмое ревью). Теперь значение, которое не читается, считается «не сказанным»: тогда брать у источника нечего, и `gaps` возвращает пустой список.

`now - self.keep_days * 86400` и `visible_from(row, now)` — **не тащить старше того, что двери покажут.** Комментарий над методом: *Not older than what the doors would SHOW — the row's `retention_days` (`visible_from`) — nor than `keep_days`: a range fetched past the ceiling is a range nobody will be shown.* `keep_days` в процессе берётся из `RETENTION_DAYS` (30 по умолчанию). Но у записи может быть свой срок, `retention_days` в её строке, и он бывает короче: дверь обрежет по нему всё, что старше (урок 8). Без второй границы запись со сроком в неделю тянула бы с карты тридцатидневные часы, которых никто никогда не увидит. Каждый такой час — сессия устройства, потраченная впустую. Срок, который не читается как число дней, `visible_from` превращает в `now` (урок 8). Тогда `lo` не меньше `now`, `hi` меньше `lo`, и для такой записи дозапись не планирует ничего, пока строку не поправят.

`now - self.settle` — **не тащить самое свежее.** Последние минуты пишутся прямо сейчас, и с точки зрения `our_coverage` их нет. Без отступа регистратор стал бы дозаписывать то, что сам же записывает. `settle = 900` секунд по умолчанию. Шаг 10 покажет, почему этого отступа мало и чем его заменили.

## Шаг 4 — Бюджет и окно

```python
    @one_look
    def backfill(self, budget: int = 1, now: float | None = None, force: bool = False) -> list[dict]:
        now = self.wall() if now is None else now
        windowed = force or self.in_window(now)
        if self.archive_busy() or not (windowed or self._look().edges()):
            return []                                    # (outside the window only a camera's card may say "now")
        done: list[dict] = []
        names = self._look().backups()
        for row in self.rows:
            if len(done) >= budget:
                break
            if volumes.is_backup(row, names=names):
                continue
            for src in self.sources_of(row):
                says = self._uplink_says(src)
                if not (force or (windowed if says is None else says)):
                    continue
                for (t0, t1) in self.gaps(row["id"], src["coverage"], now, source=src["key"])[:budget - len(done)]:
                    # RANGE_CAP of a gap a pass: what is left of it is a gap on the next one
                    done.append(self.fetch_from(row["id"], row["cam"], src, t0, min(t1, t0 + self.RANGE_CAP)))
                if len(done) >= budget:
                    break
        return done
```

Дозапись конкурирует с живым на аплинке устройства (урок 15), значит идти «сколько получится» она не может.

**Бюджет** — прецедент есть: `rebalance(budget)` из урока 13, ограниченная работа по требованию, а не в обычном проходе. Здесь то же: не более `budget` диапазонов за проход. В процессе — `BACKFILL_BUDGET` (1); ноль значит «только то, что попросил оператор». И каждый диапазон не длиннее `RANGE_CAP` (600 с): от дыры берётся `min(t1, t0 + self.RANGE_CAP)`, а остаток останется дырой и попадёт в следующий проход (шаг 5). Тест: `test_lesson11_edge.py::test_backfill_closes_our_gaps_and_what_it_fetches_is_ours` — дыра в 6400 секунд закрывается за несколько проходов, по `RANGE_CAP` за проход.

**Один взгляд за проход.** `@one_look` даёт проходу один `Look` — то, что проход прочёл о кластере, каждую часть один раз: строки записей, heartbeat подсистем, имена резервных (`backups()`) и пограничных (`edges()`) томов. Раньше `volumes.backups(self.vars)` и источники каждой записи читали хранилище заново. На тысяче записей и пятистах резервных один проход дозаписи читал хранилище 3 032 003 раза. Прочитанное живёт не дольше прохода и не дольше `Look.FRESH` (10 с): выкачка, потратившая минуты на один диапазон, спрашивает источники следующей записи по свежим heartbeat. Тест: `test_recorder_reads.py::test_a_pass_reads_the_rows_and_heartbeats_once_and_the_next_pass_reads_them_again`.

**Окно** — новое, и его в курсе ещё не было. Закрывать суточную дыру в час пик — худшее, что можно сделать: канал занят живым, оператор смотрит, а мы качаем позавчерашнее.

```python
    def in_window(self, now: float) -> bool:
        if not self.window:
            return True
        h = time.localtime(now).tm_hour
        a, b = self.window
        return a <= h < b if a < b else (h >= a or h < b)
```

Ветка `a < b else` — окно через полночь: `(22, 6)` означает «с десяти вечера до шести утра», и без этой ветки оно бы никогда не наступало. В процессе — `BACKFILL_WINDOW=22-6`.

**Местное время, а не UTC.** Единственное место в курсе, где местное время правильно: «ночью» — это ночь там, где стоит камера, а не там, где сервер. Везде остальное — UTC, и урок должен сказать, почему здесь исключение.

**Окно — для аплинка, о котором никто ничего не знает.** Окно держит дозапись подальше от аплинка устройства по часам, потому что регистратор не знает, занят ли этот аплинк. Камера, которая сама шлёт поток на сервер, это знает. Она говорит об этом в heartbeat своего рекордера карты: `stream.lagging` (`CameraPusher._judge_lag`, урок 26). Девятое ревью спросило, задумано ли окно 22–6 для карты камеры, и владелец ответил «нет»: то, что отстающий поток пропустил, ждало ночи, а карта, заполненная вечерним отставанием, теряла это раньше. Теперь для такого источника слово камеры заменяет окно. `backup_sources` кладёт в источник вида `edge` поле `lagging`, если камера его сказала, а `_uplink_says(src)` переводит его в ответ: `True` — аплинк свободен, `False` — поток отстаёт, `None` — источник о своём аплинке молчит. Карту просят, как только камера сказала, что аплинк снова несёт поток, в любой час. Пока камера говорит, что поток отстаёт, карту не просят, даже внутри окна. Источники, которые о своём аплинке молчат, остаются под окном: архив устройства, дверь резервного сервера, карта камеры, которая не шлёт поток. Поэтому вне окна проход вообще идёт дальше первой строки, только когда объявлены тома `edge` (`self._look().edges()`). `force` по-прежнему обходит и окно, и слово камеры. Тест: `test_camera_card.py::test_what_a_lagging_stream_skipped_is_backfilled_as_soon_as_the_camera_says_its_uplink_is_free_whatever_the_hour` — без слова камеры вне окна не просят ничего; в окне, пока камера говорит `lagging: True`, тоже ничего; днём, после `lagging: False`, дыра в сто секунд приходит с `edge:1-card`.

Источников у записи бывает несколько: сначала устройство, потом резервные записи той же камеры (`sources_of`, урок 26). Резервная запись сама не дозаписывается ни из кого — это правило урока 26, и здесь оно стоит первой строкой цикла.

**Выкачка идёт не на нити аренд.** Выкачка с карты — это минуты, а проход регистратора продлевает аренды и шлёт heartbeat. Карта, которая отдавала диапазон дольше аренды, отсекала регистратор и останавливала живую запись всех его камер ради часа одной (ревью платформы, обратная связь BE):

```python
    BACKFILL_WAIT = 0.5

    def backfill_in_background(self) -> None:
        if self._backfiller is not None and self._backfiller.is_alive():
            return                                       # one range at a time: the device has one uplink
        ...
        self._backfiller = threading.Thread(target=fetch, name=f"{self.name}-backfill", daemon=True)
        self._backfiller.start()
        self._backfiller.join(timeout=self.BACKFILL_WAIT)
```

Одна выкачка за раз, на своей нити; проход ждёт её полсекунды и идёт дальше. У настоящего исполнителя есть и свой срок: `max(300, длина диапазона + 60)` секунд, после которого он сообщает ошибку (`range_error`), а не висит, пока TCP не сдастся.

## Шаг 5 — Дозаписанное — наше

```python
    # One range from the device: its frames, landed as OURS — our epoch, our volume, the backfill stream.
    def fetch(self, unit, cam, url: str, t0: float, t1: float) -> dict:
        unit = str(unit)
        if not self.may_write(unit):
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "skipped": "no lease"}
        self.actuator.range_error = ""
        samples = self.actuator.record_range(unit, f"{url}?from={t0}&to={t1}", t0, t1)
        return self._land(unit, cam, samples, t0, t1, "device")
```

**Кусками, а не целиком.** Диапазон любой длины когда-то читался одним запросом и держался в памяти целиком; сутки дозаписи с резервной — около 43 ГБ, оба регистратора падали по памяти, заявка оставалась, и после рестарта всё повторялось (третье ревью, блокер 6). Теперь `RecWorker._pieces` берёт у источника около минуты за раз (`PIECE` = 60 с), режет по ключевым кадрам — ничего не берётся дважды и ничего не пропускается между кусками, — и каждый кусок садится, прежде чем просят следующий; дверь архива отдаёт `/samples` потоком (`Archive.stream`, по последовательности). А один проход берёт у одного диапазона не больше `RANGE_CAP` (600 с): заявку на сутки обслуживают много проходов, прогресс помнится (`_requested`), и консоль видит её сделанной только целиком. Тесты: `test_rec_volume.py::test_a_long_range_is_fetched_from_a_backup_a_minute_at_a_time_and_lands_whole`, `test_backfill_bounds.py::test_a_long_request_is_fetched_in_pieces_over_several_passes_and_reported_once_whole`.

Исполнитель возвращает **кадры** — `Sample` со временем съёмки, ключевым флагом и байтами одного кадра. Пишет их в том `_land`:

```python
        epoch = self.epochs.get(unit, 0)
        ...
                for smp in g:
                    self.store.put(unit, epoch, smp, backfill=True)
```

`self.epochs.get(unit, 0)` — **эпоха регистратора, текущая.** Не эпоха того времени, когда запись велась: писателем этих кадров является этот процесс сейчас. Без аренды на запись (`may_write`, М10A, урок 8, шаг 8) выкачка не начинается вовсе: писать под эпохой, которую мы уже не держим, нельзя.

Может показаться странным: поток называется `1/e7/backfill`, а содержит позавчерашнее. Но эпоха отвечает не на вопрос «когда снято», а на вопрос «кто это записал» (урок 6). Индекс держит время каждого кадра, и на таймлайне дозаписанный час встаёт на своё место — при этом никогда не отсечённым, потому что эпоха текущая.

**Происхождение — в имени потока.** `stream_name(unit, epoch, backfill=True)` даёт `<запись>/e<эпоха>/backfill`. Имя — единственные метаданные, какие у потока есть, и на таймлайне такой пролёт приходит с `source: backfill`. Зачем помечать: у дозаписанного другое качество. Карта часто пишет другим битрейтом, другим разрешением, иногда другим кодеком, и оператор, глядя на час, должен понимать, почему он выглядит иначе.

Свой поток нужен и по второй причине. Писать позавчерашнее в поток живой записи значит перемешать в одном потоке старые кадры с новыми, и движок закрывал бы последовательность на каждом переключении (обратная связь R). Два потока одной эпохи друг другу не мешают, а где они описывают одни минуты, `authoritative` отдаёт их живому: при равной эпохе побеждает `source == "live"`.

**И дальше всё уже написано:** кольцо тома, двери, видимость, срок показа. Ничего нового. Тест: `test_backfill_closes_our_gaps_and_what_it_fetches_is_ours` — две записи с часом между ними, `gaps` находит час, выкачка ложится в `1/e<эпоха>/backfill` под текущей эпохой, и после того как блок закрыт, `our_coverage` — один непрерывный отрезок.

Закрытый диапазон регистратор ещё и называет в heartbeat (`closed`): ни один детектор не смотрел камеру, пока её никто не писал, и процесс заданий VMS (`python3 -m vms jobs`, `jobs.scan_what_arrived`) превращает каждый такой диапазон в прогон детекторов ([урок 22](22-two-holes-one-cause.md)).

## Шаг 6 — Последовательность на каждый отрезок

Выкачка возвращает кадры, но не обязательно сплошные. У карты бывают свои дыры, а часть групп кадров `_land` отбросит сам (шаг 7). Писать всё, что осталось, одной последовательностью нельзя:

```python
                # A sequence is CONTINUOUS to the index: a hole inside one is drawn as footage. So what the source
                # did not have — or what was dropped above — ends the sequence, and the next group opens another.
                if last is not None and span[0] - last > self.stitch:
                    self.store.finish(unit, epoch, backfill=True)
                last = span[1]
```

Индекс описывает последовательность её началом и концом. Дыра внутри неё на таймлайне выглядит записью, и страница предложит сыграть то, чего нет. Поэтому разрыв длиннее допуска на шов закрывает последовательность (`finish`), а следующая группа открывает новую — с ключевого кадра, как движок и требует (`SEQUENCE_NEEDS_KEY_SAMPLE`, урок 7).

Это правило нашлось, когда курс переписывали на ObjectStorage: первая версия `_land` писала всё выкачанное одной последовательностью и закрывала её в конце. Тест: `test_the_backups_volume_decides_what_is_copied_not_its_summary` (урок 26) — источник с сорокасекундной дырой внутри диапазона, и в томе две последовательности дозаписи, а не одна.

## Шаг 7 — Только дыры

Заполнять поверх уже записанного нельзя. Два потока на одно время лягут внахлёст, и объяснить это оператору будет нечем.

`gaps` уже вычитает — но между вычислением дыры и записью проходит время, и регистратор мог за эти минуты записать туда живьём. Поэтому `_land` проверяет ещё раз, по группе кадров — от ключевого до ключевого:

```python
        have = stitch(self.our_coverage(unit) + self.landing.get(unit, []), self.stitch)   # landing is ours: not twice
        kept, groups = 0, []
        ...
        for g in groups:
            span = (unix_s(g[0].begin), unix_s(g[-1].end))
            if overlaps(have, span):
                ours.append(span)                        # live recording got there while we were fetching: ours already
                continue
            if not g[0].key:
                continue                                 # no key frame to open on: a hole, asked for again
```

**И под своей арендой, в свой том.** Выкачка идёт минуты, а за минуты том могли отдать и взять другой, аренду — отпустить. Первая версия `_land` писала в тот том, что открыт **сейчас**, и под эпохой `epochs.get(unit, 0)` — после отпускания это ноль, эпоха копий удержаний, не дозаписи (второе ревью). Теперь `fetch` запоминает том, для которого выкачивает, и `_land` пишет только в него, только пока он открыт и пока аренда на запись есть; иначе — `skipped`, и диапазон остаётся дырой до следующего прохода. `leave_volume` даёт выкачке в полёте несколько секунд закончить группу, а не режет её посередине. Тест: `test_a_fetched_range_lands_under_its_lease_into_the_volume_it_was_fetched_for_and_landing_is_what_landed`.

Вычитание **дважды**: при планировании и при посадке. Дёшево и снимает гонку, которая иначе воспроизводилась бы раз в месяц. Группа, которая не начинается с ключевого кадра, тоже отбрасывается: последовательность с неё не открыть.

«Уже наше» — это видимое покрытие **и** то, что садится (`landing`, шаг 10): только что скопированное, которое том ещё не показывает. Без второго слагаемого заявка и плановый проход, скопировавшие один и тот же диапазон один за другим, записали бы его дважды: видимое покрытие у второго ещё не изменилось.

Тест: `test_a_fetch_that_brought_nothing_new_queues_no_scan` — выкачка диапазона, который уже наш, сажает ноль групп и ничего не объявляет закрытым, иначе детекторы прогнали бы те же минуты второй раз.

## Шаг 8 — Кнопка «закрепить»

Не всё нужно дозаписывать по расписанию. Чаще нужно обратное: оператор смотрит вчерашний инцидент, интервал есть только на карте — и он **должен успеть** до того, как кольцо карты его перезапишет. Урок 15 привёл эту кнопку туда, где ей место: на промежуток устройства.

Маршрута дозаписи у консоли нет: дозапись — **заявка** регистратору, строка семейства `requests` платформы (М10A, урок 15, шаг 12; путь строки — урок 14, шаг 14). Спека записи говорит её форму:

```yaml
requests:
  schema:
    type: object
    required: [unit, from, to]
    additionalProperties: false
    properties: {unit: {type: string}, from: {type: number}, to: {type: number}}
  key: "{unit}-{from:int}-{to:int}"
  per_person: 7
  settle: 60
  ttl: 86400
  stamp: [by, at, about]
  journal: archive.backfill.asked
```

```
POST /rec/requests {"unit": "rec/41", "from": …, "to": …}            + Idempotency-Key  →  202, строка rec/requests/41-<from>-<to>
POST /rec/requests {"unit": "rec/41-cloud", "from": …, "to": …}      + Idempotency-Key  →  202, в названную запись
POST /rec/requests {"unit": "rec/41", "from": NaN, "to": …}                             →  400: не по схеме
POST /rec/requests {"unit": "rec/41", "from": false, "to": true}                        →  400: true и false — не числа
POST /rec/requests …восьмая неотвеченная заявка того же человека                        →  429
```

Заявку подают на **запись**, а не на камеру: дозапись кладёт кадры в поток записи, а у камеры их может быть несколько — по одной на архив, в который её пишут (урок 10). Какую из них закрывать, говорит проситель, и запись, которой нет, — 404. Имя строки — из диапазона (`key`): повторный POST того же диапазона — та же строка, под каким ключом идемпотентности его ни пошли, а не вторая выкачка. Всё остальное о подаче — платформа и её урок: схема не пропускает `NaN`, `inf`, слово и `true`/`false` (400; пятое и седьмое ревью находили их запуском); неотвеченных заявок одного человека не больше `per_person` — учёт одной строкой `rec/requests/asks-<хеш имени>` по CAS, и сорок POST разом дают семь заявок и тридцать три 429 (шестое ревью); каждая принятая — строка `archive.backfill.asked`. Тесты: `test_console_gate.py::test_a_backfill_is_two_finite_numbers_a_handful_at_a_time_and_a_line`, `::test_forty_backfills_asked_at_once_are_seven`.

**Что может решить только регистратор, он и отказывает — в heartbeat'е.** Платформа подаёт заявку по форме и о диапазоне ничего не знает. Диапазон в тридцать один год (четвёртое ревью), в доли секунды, ещё не наступивший час (шестое), `{"from": 0, "to": 600}` — 1970 (седьмое) проходят схему, а выкачать их не может никто:

```python
    BACKFILL_MAX, BACKFILL_MIN, BACKFILL_AHEAD = 86400.0, 1.0, 60.0

    def _range_refusal(self, unit: str, t0: float, t1: float, now: float) -> str | None:
        from .archive import visible_from
        if t1 <= t0:
            return "a backfill's range ends after it starts"
        if t1 - t0 > self.BACKFILL_MAX:
            return f"a backfill is a range of at most {self.BACKFILL_MAX:.0f} s (a day): ask for a longer hole a day at a time"
        if t1 - t0 < self.BACKFILL_MIN:
            return f"a backfill is at least {self.BACKFILL_MIN:.0f} s of footage"
        if t1 > now + self.BACKFILL_AHEAD:
            return f"a backfill is a hole in what HAS been recorded: this range ends {t1 - now:.0f} s from now"
        floor = visible_from(self._row_of(unit), now)
        if t1 <= floor:
            return f"this range ends before anything the recording shows (from {floor:.0f}): nothing could fetch it"
        return None
```

Не длиннее суток, не короче секунды (регистратор выкачивает целые секунды), не дальше минуты вперёд от его часов (расхождение двух часов, а не минуты вперёд), не целиком старше того, что запись показывает (`visible_from` по её `retention_days`: двери никогда не покажут выкачанное). Отказ — ответ: id уходит в `fetched`, и уборка консоли убирает строку, а место человека освобождается; почему — в heartbeat'е (`requests_refused`) и в событиях записи (`archive.backfill.refused`, с `of: vms/<камера>`, как остальные строки регистратора). Тест: `test_console_gate.py::test_a_backfill_nobody_could_answer_is_refused_by_the_recorder_in_its_heartbeat`.

**Заявка, на которую некому ответить, места не держит вечно.** У дозаписи, поданной у двери консоли, `valid_until` нет — час, выкачанный с опозданием, тот же час, — поэтому строку, простоявшую `ttl` спеки (сутки), кончает уборка платформы и считает в `w2c_requests_expired_total{sub="rec"}`; список заявок человека, которого сутки никто не касался, уходит туда же. Задача, которой эти минуты ещё нужны, попросит снова (`ask_for_footage`); человек увидит, что дыра на месте, и тоже может. Тест: `test_jobs.py::test_a_backfill_nobody_answered_for_a_day_is_ended_and_a_record_request_is_not_its_business` — заявка старше суток уходит и считается, младшая остаётся, `record` со своим `valid_until` не тронут.

Заявку, которую подаёт сама VMS — задача или обзор карт (`jobs._ask_recorder`, уроки 21 и 23), — она подаёт так, как подаёт строку семейство просьб (М10A, урок 14): `unit: rec/<запись>` и срок `valid_until`. Регистратор читает обе формы единицы и чтит срок, где его дали: не начатая к сроку заявка получает ответ «просрочена» (`expired`), а не выкачивается — кто просил, попросит снова; начатая доводится до конца. Тест: `test_backfill_bounds.py::test_a_request_filed_as_the_family_files_one_is_fetched_and_one_past_its_deadline_unbegun_is_answered_expired`.

Регистратор читает заявки в каждом проходе:

```python
    def requests(self, budget: int = 2, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        if self.archive_busy():
            return []
        mine = {str(r["id"]) for r in self.rows}
        done: list[dict] = []
        keys = sorted(self.vars.list(REC.requests_prefix()))
        # A request answered is remembered while its ROW stands, and not after — the base worker's rule (`VmsWorker.
        # requests`), which this override did not keep: `fetched` grew by one id per request for the life of the
        # process, and a request whose row the console had not reaped yet was fetched again from its start (the
        # review's fourth pass, Т-m13). The same for how far each one got.
        present = {k.rsplit("/", 1)[1] for k in keys}
        self.fetched = [r for r in self.fetched if r in present]
        self._requested = {r: v for r, v in self._requested.items() if r in present}
        self._requests_read = {r: v for r, v in self._requests_read.items() if r in present}
        for key in keys:
            ...
            if not it or str(it.get("unit", "")) not in mine or key.rsplit("/", 1)[1] in self.fetched:
                continue                                     # another recorder's recording, or answered already
            ...
            unit, cam = str(it["unit"]), str(it.get("cam", it["unit"]))
            rid = key.rsplit("/", 1)[1]
            if not self.may_act(unit):
                continue                                     # a lease that lapsed answers nothing, a refusal neither
            try:
                t0, t1 = finite(it["from"]), finite(it["to"])
            except (KeyError, TypeError, ValueError):
                log.error("%s: request %s refused: from=%r to=%r is not a range", self.name, rid, it.get("from"), it.get("to"))
                self._refuse_request(rid, unit, cam, "`from` and `to` are not a range", done)
                continue
            why = self._range_refusal(unit, t0, t1, now)
            if why:
                self._refuse_request(rid, unit, cam, why, done)
                continue
            ours = self.our_coverage(unit)
            if unit in self.reconciler.running():
                t1 = min(t1, ours[-1][1] if ours else now - self.settle)
            ...
            srcs = self.sources_of({"id": unit, "cam": cam, "home": (self._row_of(unit) or {}).get("home", "")})
            if not srcs:
                continue                                     # nobody holds the device and no backup answers; ask again next pass
            upto = min(t1, t0 + self.RANGE_CAP)
            # Each source in turn until one serves it. A source that FAILED says nothing about the range — the
            # request stays, for the next pass; reported as fetched, the console would delete what nobody served.
            r = {}
            for src in srcs:
                r = self.fetch_from(unit, cam, src, t0, upto)
                if not r.get("error"):
                    break
            if r.get("skipped") or r.get("error"):
                continue
            ...
            self._requested.pop(rid, None)
            self.fetched.append(rid)                         # the heartbeat says so; the console removes the row
            done.append({**r, "request": rid})
        return done
```

Заявка — работа **вне бюджета обычного прохода и вне окна**: её попросил человек, и она срочна по определению. Отвечает на неё только держатель с подтверждённой арендой (`may_act`): аренда, истёкшая при молчащем хранилище, не отвечает ни выкачкой, ни отказом. Бюджет и окно — для фоновой уборки, не для ответа на запрос. Нижней границы по первой записанной секунде (шаг 10) у заявки тоже нет: человек может попросить любой час.

**Заявка, диапазон которой не разбирается, — отказ ей одной.** Схема не пропустит `NaN` и слова (выше), но строка в хранилище — это строка: её можно поправить руками или записать другой сборкой. `requests` читал `from` и `to` голым `float`, и одна такая заявка бросала исключение из всего метода на каждом проходе: ни одна заявка за ней — любой записи этого регистратора — не выкачивалась (шестое ревью; тот же класс, что команда к единице с битой эпохой, М10B, урок 4, шаг 8). Теперь она отвечена отказом (`_refuse_request`) — id уходит в `fetched`, и уборка консоли убирает строку, — в логе сказано почему, а проход идёт к следующей. Тест: `test_epoch_refused.py::test_the_recorder_refuses_one_request_whose_range_does_not_parse_and_serves_the_next`. После шестого ревью оставался один вид такой строки: целое из четырёхсот цифр, которое JSON хранит как есть. `float` даёт на нём `OverflowError`, а этот `except` его не ловил, и проход снова падал. Теперь `from` и `to` читает `finite` (`rows.finite`): переполнение, `nan` и `inf` для него — `ValueError`. Тест: `test_one_bad_element.py::test_a_moment_of_four_hundred_digits_in_a_request_is_that_requests_in_the_holder_and_the_recorder`.

**Но не дальше видимого, пока запись идёт.** Минуты после конца видимого покрытия лежат в блоке, который пишется прямо сейчас (шаг 10, Q). Выкачай их с карты — и они лягут в том второй раз. Поэтому у живой записи конец заявки обрезается по концу видимого (или по `settle`, если видимого нет). Запись, которая не идёт, можно просить за любые минуты: дописывать в неё некому.

**Источники — по очереди, пока один не обслужит.** Сначала устройство, потом резервные записи (`sources_of`, урок 26). Устройство не отдало — спрашивается следующий источник, а не бросается заявка.

**Не в потоке цикла.** Заявка — час с карты камеры, минуты выкачки; базовый `pump_once` обслуживает заявки на потоке цикла (`serve_requests`), и для воркера это верно — импульс реле мгновенен. У регистратора `serve_requests` ничего не делает, а `requests()` зовётся первым делом в потоке дозаписи (`backfill_in_background`), перед плановыми диапазонами: проход ждёт его `BACKFILL_WAIT` и идёт дальше, аренды продлеваются, heartbeat уходит (ревью платформы, B3; шов — платформенный `Worker.serve_requests`). Тест: `test_an_operators_request_is_served_off_the_loops_thread`.

Удалить строку регистратор не может: токен воркера не пишет конфигурацию (урок 10 М10A). Поэтому он **сообщает** сделанное в heartbeat (`fetched`), а строку убирает уборка процесса консоли — платформенная (`requests.clear_requests` из `host.requests_loop`; весь путь строки — М10A, урок 14, шаг 14): отвеченные — каждые `CLEAR_EVERY` (2 с), не читая ни одной строки, а заявки старше `ttl` — её более редкий обход. Heartbeat несёт каждый отвеченный id, от старых к новым, сколько влезает в `FETCHED_BYTES` (8 КиБ) — это тоже база (`Worker.fetched_said`); убранная строка уходит и из `fetched`, и следующий heartbeat несёт следующие. Тест: `test_long_poll.py::test_at_three_commands_a_second_the_rows_stay_bounded_and_a_restart_declares_nothing_failed`. Заявку, которую он не смог обслужить — аренда истекла, источника нет, все источники ответили ошибкой, — он не называет сделанной, иначе консоль удалила бы то, чего никто не выкачал. Ошибка источника ничего не говорит о диапазоне: сессию отказали, сеть оборвалась. Строка остаётся и ждёт следующего прохода.

Тесты: `test_a_request_is_fetched_outside_the_window_and_the_budget`, `test_a_request_for_somebody_elses_recording_is_left_alone`, `test_a_request_the_recorder_could_not_serve_is_not_reported_as_served`, `test_backfill_bounds.py::test_a_request_a_source_failed_to_serve_stays_for_the_next_pass` — исполнитель, у которого выкачка падает с `range_error`: `requests` ничего не сделал, `fetched` пуст, а строка `rec/requests/1-x` на месте.

## Шаг 9 — Когда ждать: том, а не диск

Дозаписи — и плановой, и заявке — есть куда не садиться в одном случае: том ничего не принимает.

```python
    # The volume is taking nothing: it said so (`archive_error`), or nothing is open. Backfill — planned or asked
    # for — waits then: there is nowhere to land what it would fetch.
    #
    # What it does NOT wait for is a full disk. The footage is in a ring formatted at its quota: it never grows
    # past it, and a range fetched now is written at the ring's head, the newest block, overwritten last. ...
    def archive_busy(self) -> bool:
        return bool(self.archive_error) or self.store is None or self.store.writer is None
```

Том ушёл (`obsd` молчит, сеть к бакету легла) или не открыт вовсе — выкачивать некуда. Сессию устройства в этот момент тратить незачем, а заявку оператора — нельзя терять. Поэтому заявка **ждёт**: строка остаётся, и тот проход, в котором том снова отвечает, её выкачивает. Даже `force` эту дверь не открывает.

Полного диска дозапись не ждёт, и это не упущение. Том — кольцо, отформатированное по своей квоте (урок 8): он не растёт дальше неё и диск переполнить не может. Выкачанное сейчас ложится в голову кольца — в самый новый блок, который будет перезаписан последним. Гнаться тут нечему: дозапись не вытесняет то, что потом пришлось бы дозаписывать снова. Одно следствие стоит знать: позавчерашний час, дозаписанный сегодня, кольцо отдаст позже вчерашнего, потому что блоки у него новее.

Тесты: `test_backfill_into_a_ring_waits_for_the_volume_and_not_for_the_disk`, `test_a_request_waits_while_the_volume_takes_nothing`.

## Шаг 10 — Границы, найденные на коробке

Всё выше прошло тесты курса и не прошло первую неделю на настоящем ящике. Продукт вернул находки (`ОБРАТНАЯ-СВЯЗЬ-ИЗ-ПРОДУКТА.md`, пункты P, Q, S и AE), и каждая — граница, которой не хватало `gaps`.

**Чего нет нигде, запоминается (P).** Покрытие устройства в heartbeat — сводка: начало, конец, число фрагментов. Урок 15 выбрал это сознательно и правильно, но из сводки нельзя узнать, где у карты дыры. Площадка потеряла питание — лежали и мы, и камера, — и двадцать минут нет ни у нас, ни на карте. `gaps` видит их как работу, выкачка приносит ноль кадров, покрытие не меняется, и следующий проход планирует те же двадцать минут. В курсе это ограничивали бюджет и окно: одна пустая выкачка за ночь. На ящике без окна продукт видел её раз в две секунды — и каждая открывала сессию устройства, которых у камеры одна-две.

Поэтому то, что после **чистой** выкачки источник не отдал, запоминается по паре (запись, источник) и вычитается из следующих дыр:

```python
        failed = getattr(self.actuator, "range_error", "")
        if not failed:
            missing = subtract((t0, t1), delivered)
            if missing:
                self.nowhere[(unit, source)] = sorted(self.nowhere.get((unit, source), []) + missing)
```

Чистой — это важно. Конвейер, упавший на середине, ничего не говорит о том, что есть на карте; запомнить его диапазон как «нигде» значит молча потерять то, что на карте ещё лежит. Поэтому настоящий исполнитель не только пишет ошибку в журнал, но и сообщает её (`range_error`). Сумма запомненного уходит в heartbeat как `nowhere_seconds` — число, которое оператору полезно само по себе: «из пропущенного нами на карте не нашлось 1200 секунд». Тесты: `test_a_range_the_card_does_not_have_is_fetched_once_and_then_remembered`, `test_a_fetch_that_failed_half_way_is_not_remembered_as_nowhere`.

Ключ — пара, а не имя записи. Продукт ключевал память по имени записи, а оно на карте у всех камер одинаковое, и то, чего не было на карте одной камеры, вычиталось из плана соседней (AE).

Это и есть четвёртая строка таблицы из шага 11 — «пусто, не записано нигде» — сделанная состоянием, а не только подписью.

**Отданное — уже наше, пока том его не покажет (AE).** «Не нашлось» — это то, чего источник **не отдал**, а не то, чего после выкачки не видно у нас. Разница появляется ровно на нашем движке: только что скопированный диапазон лежит в открытом блоке, а читатель видит только закрытые. Первая версия этой строки вычитала из диапазона видимое покрытие и запоминала весь скопированный диапазон как «на карте нет» — навсегда.

```python
        delivered = stitch([(unix_s(g[0].begin), unix_s(g[-1].end)) for g in groups], self.stitch)
        ...
        self.landing[unit] = stitch(self.landing.get(unit, []) + ours, self.stitch)
```

Отданное (`delivered`) — всё, что вернул источник, и по нему считается «не нашлось». Садящееся (`landing`) — уже: то, что **легло**, и то, что отброшено, потому что живая запись уже это имела. Не одно и то же (второе ревью): первая версия клала в `landing` всё отданное — и группу, которую движок отверг, и группу без ключевого кадра, — и `gaps` вычитал их до перезапуска процесса, хотя в томе их не было и не будет. Такая группа — дыра, и её спрашивают снова. Но не вечно: кусок, который движок отвергает по содержимому (без ключевого кадра, больше блока, потерянная последовательность), отвергнет и в следующий раз. После трёх отказов одного куска (`REFUSED_TIMES`) дозапись его бросает: лог, `given_up` — как `nowhere` для того, чего нет у источника, — и `gaps` его больше не планирует; heartbeat говорит, сколько брошено (`backfill.refused_seconds`). А кусок, который сел, счёт по нему сбрасывает (так у продукта, обратная связь DD). И после каждого отказа открытая последовательность закрывается — иначе следующая группа продолжала её, и индекс рисовал отвергнутый кусок записью (найдено на живом демоне). Тесты: `test_a_piece_the_engine_always_refuses_is_fetched_three_times_and_then_given_up`, `test_a_refused_group_ends_its_sequence_and_a_lost_sequence_is_not_landed`. `gaps` вычитает садящееся, пока том его не покажет:

```python
        pending = [sp for sp in self.landing.get(str(unit), []) if subtract(sp, ours)]   # still not shown by the volume
        self.landing[str(unit)] = pending
```

Без этого следующий проход скопировал бы тот же диапазон второй раз. По той же причине `_land` считает `landing` своим (шаг 7): что уже садится, второй раз не пишется. Писателя ради видимости дозапись не трогает: `Archive.seal` закрыл бы и снова взял писателя тома — того самого, в который сейчас пишут все живые записи регистратора. Тест: `test_a_range_just_copied_is_neither_copied_again_nor_taken_for_what_the_source_lacked` — сразу после выкачки покрытие не изменилось, `nowhere` пуст и дыры в плане нет; после `store.seal()` том показывает копию, и `landing` пустеет.

**Верхняя граница — конец видимого, а не догадка (Q).** `settle = 900` держался на неравенстве, которое нигде не было записано: блок должен закрываться быстрее пятнадцати минут. Блок закрывается, когда заполнен, и на низком битрейте или с большим блоком это дольше. Тогда дозапись начнёт тащить с карты то, что регистратор пишет прямо сейчас. Проверка из шага 7 этого не поймает: открытого блока не видно, перекрываться не с чем. Продукт увидел это сразу: блок в 1 МБ на низком битрейте закрывался за две с лишним минуты, а `settle` там был 120 секунд.

Не угадывать задержку, а мерить её: конец нашего видимого покрытия и есть задержка. Всё после него либо пишется сейчас, либо уже записано и ещё не видно, и отличать одно от другого не нужно — ни то ни другое не дыра:

```python
        hi = min(float(coverage["to"]), now - self.settle, ours[-1][1] if ours else now)
```

`settle` остаётся нижним порогом и единственной границей для записи, у которой видимого нет вовсе. Тест: `test_backfill_stops_at_what_is_visible_not_at_a_guess` — `settle` две минуты, последний видимый кадр двадцать минут назад, и план пуст.

**По плану — только дыры внутри записанного (S).** `gaps` вычитал наше покрытие из всего, что держит устройство, в пределах `keep_days`. Для записи, которая идёт постоянно, это верно. Но урок 25 заводит записи по событию, и для них всё, что устройство держит до первой секунды записи, выглядит дырой: следующая ночь зальёт с карты весь день, и запись по детектору станет постоянной — только с опозданием и через аплинк камеры. То же с записью, созданной вчера.

Правило одно: **прикрывается сбой, а не решение.** Дозапись по плану начинается с первой видимой секунды записи:

```python
        if planned:
            if not ours:
                return []
            lo = max(lo, ours[0][0])
```

До первой секунды запись не шла по замыслу, а не по сбою. Заявка оператора этим не ограничена: её попросил человек, и он может попросить любой час. Тест: `test_planned_backfill_fills_holes_inside_what_was_recorded_and_not_before_it`.

У этой границы есть и вторая польза. Когда кольцо тома закрылось, первая видимая секунда ползёт вперёд вместе с его хвостом, и плановая дозапись никогда не пытается вернуть то, что кольцо уже отдало.

## Шаг 11 — Что это даёт оператору

Различение, ради которого весь урок:

| Что видно | Что это значит |
|---|---|
| наш промежуток (эпоха записи, без `source`) | записано нами, держит наше кольцо, показывают наши двери |
| наш промежуток, `source: backfill` | было на устройстве, теперь наше — то же кольцо, те же двери |
| промежуток устройства (`source: device`, `yields: true`) | **есть только там**, исчезнет по его кольцу |
| пусто | не записано нигде, и уже не появится |

Четвёртая строка — то, чего до урока 15 система сказать не могла: она умела показать только «не записано нами», а это не одно и то же. Оператор, ищущий вчерашний инцидент, должен отличать «не искали» от «искать негде».

## Результат

```python
r = RecWorker("r-1", vars_, objects, window=(22, 6), keep_days=30)

r.our_coverage("41")   # [(t0, t1), (t2, t3)] — две записи с дырой между ними
r.gaps("41", cov, now) # [(t1, t2)] — дыра, покрытая картой

r.backfill(budget=1, now=noon)     # [] — не в окне
r.backfill(budget=1, now=night)    # [{'unit': '41', 'cam': '41', 'from': t1, 'to': t2, 'groups': …, 'source': 'device'}]
```

```
том srv-1 (file:///data/vms/obsd/volume)
    41/e7              ← живая запись
    41/e7/backfill     ← дозаписано: текущая эпоха, позавчерашнее время

GET <дверь записи>/timeline/41
    {"start_ms": t1·1000, "end_ms": t2·1000, "epoch": 7, "source": "backfill"}
```

`rec_groups_backfilled` на `/metrics` считает посаженные группы кадров. Двери будут показывать этот час, пока он моложе `retention_days`, а держать — пока его не перезапишет кольцо: **потому что он наш**.

## Что может пойти не так

- **Считать шов дырой.** Десятки дозаписей по полсекунды в сутки на камеру.
- **Тащить старше того, что мы показываем.** Сессии устройства уходят на часы, которых наши двери никому не покажут. Граница — и `keep_days`, и срок самой записи (`visible_from`).
- **Тащить самое свежее.** Регистратор начнёт дозаписывать то, что сам же пишет прямо сейчас.
- **Дозапись без бюджета.** Одна суточная дыра забьёт аплинк камеры и уронит живое у всех, кто её смотрит.
- **Дозапись без окна.** То же самое, но в час пик.
- **Окно в UTC.** «Ночью» станет ночью на сервере, а не на площадке; для сети из двух часовых поясов это ровно наоборот.
- **Окно без ветки через полночь.** `(22, 6)` не наступит никогда.
- **Выкачка на нити аренд.** Медленная карта отсечёт регистратор и остановит живую запись всех его камер.
- **Эпоха «того времени» вместо текущей.** Эпоха отвечает, кто записал, а не когда снято; выдуманная эпоха либо совпадёт с чужой, либо окажется отсечённой.
- **Дозапись в поток живой записи.** Старые и новые кадры в одном потоке, последовательность рвётся на каждом переключении, и происхождение негде сказать.
- **Одна последовательность на весь диапазон.** Дыра карты внутри неё нарисуется записью.
- **Проверять перекрытие только при планировании.** Живая запись успеет в ту же дыру, и два потока лягут внахлёст.
- **Бюджет и окно на заявку оператора.** Он просит час, который исчезнет завтра, а вы ставите его в ночную очередь.
- **Отказывать заявке, пока том не отвечает.** Строка пропадёт, и час с карты не вернётся никогда; заявка должна ждать.
- **Ждать полного диска.** Кольцо его не заполнит; ждать надо тома, который ничего не принимает.
- **Не помнить пустое.** Дыра, которой нет и на карте, планируется каждый проход и каждый раз занимает сессию устройства.
- **Помнить пустое после сбоя.** Упавшая выкачка — не ответ карты; запомнив её, вы молча отказываетесь от того, что на карте есть.
- **Считать «нет на источнике» по видимому у нас.** Только что скопированное ещё не видно, и весь диапазон навсегда станет «нигде».
- **Держать верхнюю границу на `settle`.** Она верна, пока блок закрывается быстрее отстоя; на низком битрейте дозапись пишет поверх живого.
- **Планировать дозапись до первой секунды записи.** Запись по событию становится постоянной, только ночью и через аплинк камеры.
- **Отчитать заявку, которую источник не обслужил.** Консоль удалит строку, и диапазон не придёт никогда.
- **Спрашивать только первый источник.** Устройство отказало сессией, а резервная запись с тем же часом так и не спрошена.
- **Заявка живой записи дальше видимого.** Минуты из открытого блока лягут в том второй раз.
- **Не считать садящееся своим при посадке.** Два прохода подряд запишут один диапазон дважды.

## Итог

- Карта существует ради дыр, поэтому дозапись — не копирование, а сведение двух покрытий: цикл сверки из урока 2, применённый ко времени.
- Наше покрытие выводится из индекса тома, все потоки записи; допуск на шов — число, без которого всё рассыпается. Покрытие видимое: открытого блока в нём нет.
- Дыры получаются тем же правилом вычитания, по которому страница в уроке 15 рисует шкалу: одно правило, два применения.
- Диапазон ограничен с обеих сторон: не старше `keep_days` и потолка видимости записи (`visible_from`), не свежее конца видимого (иначе гонка с самим собой) — и, по плану, не раньше первой видимой секунды (иначе запись по событию станет постоянной). Заявка живой записи тоже обрезается по концу видимого.
- Заявка пробует источники по очереди; ошибка источника оставляет её на следующий проход, а не отчитывает как сделанную. Садящееся считается нашим и при посадке: дважды одно не пишется.
- То, чего источник после чистой выкачки не отдал, запоминается по паре (запись, источник) и больше не планируется; отданное помнится как садящееся, пока том его не покажет.
- Бюджет ограничивает объём, окно — время суток, и окно единственное в курсе считается по местному времени. Карта камеры, которая сама говорит о своём аплинке (`stream.lagging`), окна не ждёт: её слово заменяет часы. Выкачка идёт на своей нити.
- Дозаписанное пишется текущей эпохой регистратора в поток `<запись>/e<эпоха>/backfill` его тома и **является нашим**: кольцо, двери, срок показа — как у всего остального.
- Разрыв в выкачанном закрывает последовательность: дыра внутри неё нарисовалась бы записью.
- Перекрытие проверяется дважды: при планировании и при посадке, по группе кадров.
- Заявка оператора идёт вне бюджета и окна, а пока том не принимает ничего, — ждёт. Полного диска дозапись не ждёт: кольцо его не заполнит.
- Оператор наконец может отличить «не записано нигде» от «записано, но не у нас».

## Упражнения

1. Поставьте `stitch = 0`. Посчитайте «дыры» в сутках непрерывной записи, которую дважды перезапускали.
2. Уберите нижнюю границу по `keep_days`, по `visible_from` и по первой видимой секунде. Возьмите источник с девяностодневным архивом и посчитайте сессии, которые уйдут на часы, невидимые для наших дверей.
3. Уберите отступ по свежести и границу по видимому концу. Запустите дозапись при работающей записи и найдите минуты, записанные дважды.
4. Поставьте `budget=1000`. Закройте суточную дыру днём и замерьте живое видео этой камеры.
5. Считайте окно в UTC. Разнесите две площадки на восемь часов и скажите, когда пойдёт дозапись на каждой.
6. Уберите ветку через полночь. Поставьте `(22, 6)` и подождите.
7. Ставьте эпоху по времени съёмки. Найдите на таймлайне, что стало отсечённым.
8. Пишите выкачанное в поток живой записи. Что увидит оператор на таймлайне и что скажет движок на первом же кадре?
9. Уберите `finish` на разрыве в `_land`. Выкачайте диапазон с дырой на карте и посмотрите на таймлайн.
10. Проверяйте перекрытие только при планировании. Смоделируйте живую запись, попавшую в ту же дыру.
11. Проведите заявку оператора через бюджет и окно. Опишите его день.
12. Уберите `nowhere`. Сделайте на карте дыру внутри нашей и посчитайте, сколько сессий устройства откроется за сутки без окна.
13. Считайте «нет на источнике» как `subtract((t0, t1), self.our_coverage(unit))`. Выкачайте час и посмотрите, что запомнилось.
14. Заведите запись по событию (урок 25) и уберите нижнюю границу по первой секунде. Сколько часов запишет она за первую ночь?

## Что дальше

Всё написано: четыре подсистемы, чужой архив, дозапись. Живёт это пока в тестах. Второй источник для той же дозаписи — наш собственный резервный архив — появится в [уроке 26](26-a-backup-archive-of-our-own.md).

[**Урок 17**](17-on-the-box.md) ставит написанное на коробку из М9: точки входа VMS в `vms/__main__.py` рядом с процессами платформы, юниты Quadlet и то, что говорят их монтирования, `test_deploy_units.py` — и проверка здоровья из М9, которая читает архив этого регистратора.

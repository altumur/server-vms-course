# Урок 18 — Что архив отдаёт первым

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `Archive.resize` и `Archive.depth_days` в `vms/archive.py`; `RecWorker.depth_pass` — глубину записи и тревогу `archive.shallow`; `vms/keeps.py` и `RecWorker.keep_pass` с `_copy_in` — копию отмеченного в том `incidents`; `RecWorker._seal` — печать копии, один раз; `RecWorker.verify_keep` и маршрут двери `keeps` — сверку копии с её печатью; две метрики в спеке записи.
**Время:** ~60 минут.

## Зачем этот урок

В уроке 14 М10A платформа научилась мерить диск и говорить: *освободи сто пятьдесят мегабайт*. Чем освобождать, она сознательно не знает. Раньше этот урок отвечал за подсистему, которая знает: какую камеру резать, у кого запас над полом, куда увезти чужое.

Теперь отвечать нечего. Видео лежит в томе ObjectStorage (урок 6), а том — кольцо фиксированного размера (урок 7). Когда кольцо полно, оно само перезаписывает свои самые старые блоки. Прохода, который удаляет видео, в курсе больше нет, и никто не выбирает, чем пожертвовать.

Вопрос от этого не исчез, он сдвинулся. «Что удалить» решает кольцо. Человеку остаются три других вопроса, и урок отвечает на них.

**Какого размера кольцо.** Размер тома — это и есть глубина архива. Его задают квотой, и его можно поменять без остановки записи.

**Сколько архива на самом деле и меньше ли это обещанного.** Кольцо не знает обещаний. Регистратор их не исполняет — он за ними следит и говорит, когда кольцо зашло за пол записи. Главное здесь — отличить молодой архив от обрезанного.

**Как сохранить то, что должно пережить кольцо.** Кольцо не умеет пощадить диапазон. Поэтому отмеченный интервал нельзя оставить на месте — его копируют в отдельный том.

> **Проверка без железа.** Всё, кроме самой записи с камеры. Тесты урока идут против живого `obsd` (фикстура `ObsdDaemon` в `tests/vmsconftest.py`): кольцо замыкается по-настоящему, когда в том пишут больше квоты, а копия метки ложится в настоящий второй том. Источник копии — дверь архива другого регистратора, поднятая тестом (`door`). GStreamer не нужен: кадры — это `fake_samples`. Два теста ватерлинии в `test_disk_full.py` не трогают `obsd` вовсе. Без собранного `obsd` архивные тесты падают с подсказкой, как его собрать (`ObjectStorage/standalone-build/build.sh`, `OBSD_BIN`).

## Что нужно знать заранее

- **[Урок 6](06-objectstorage-the-engine.md)** — движок ObjectStorage и демон `obsd`: сессия, писатель, читатель.
- **[Урок 7](07-volume-block-sequence-stream.md)** — том, блок, последовательность, поток; почему том — кольцо и что значит `firstBlockId`.
- **[Урок 8](08-visibility-retention-timeline.md)** — видимость, `retention_days` как потолок того, что показывают двери, и таймлайн.
- **[Урок 10](10-recworker.md)** — регистратор и удержание тома: кто пишет в том и под каким владельцем.
- **[Урок 27](27-volumes.md)** — виды томов, среди них `incidents`.
- **М10A, урок 14** — ресурс, ватерлиния, `relieve` и недостача; что держит строка таблицы (`holds:`) и просьба освободить место (`requests: {free: true}`).

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
    def _share_of_space(space: dict, low: float = 0.75) -> int:   # the space is the daemon's answer, `VOLUME_SPACE` (урок 10)
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

Тест — `test_obsd.py::test_a_new_quota_resizes_the_ring_without_stopping_the_writer`. Десять минут записаны в том на 64 МБ без закрытия блока, квота становится 128 МБ (`WRITER_RESIZE`), и следующие десять минут идут в того же писателя. Покрытие — одни двадцать минут подряд:

```python
    st.resize(128 << 20)
    assert st.quota == 128 << 20 and st.writer is not None
    footage(st, "7", 1, t, t + 600, step=10)
    assert st.coverage("7") == [(t - 600, t + 600)]
```

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
        from w2cplatform.events import ALARM
        if self.store is None or self.engine_lost or self.clock() - self._depth_at < self.DEPTH_EVERY:
            return self.depths                       # (an engine found lost is not asked again on the leases' thread)
        self._depth_at, now = self.clock(), self.wall() if now is None else now
        try:
            closed = int(self.store.status().get("firstBlockId", 0)) > 0
            depths = {str(r["id"]): round(self.store.depth_days(str(r["id"]), now), 2) for r in self.rows}
        except ArchiveError:                         # a volume that is away says nothing about depth
            return self.depths
        self.depths = depths
        for row in self.rows:
            # `rows.number`: `nan` or `inf` days passed the row's `float` and raised `archive.shallow` every day for a
            # floor no depth meets (the ninth pass, sibling A's table) — read as not said, counted once and logged
            unit = str(row["id"])
            floor = number(f"rec/recordings/{unit}#min_depth_days", row.get("min_depth_days") or None, float, 0.0)
            if not floor or not closed or depths[unit] >= floor:
                self.shallow.pop(unit, None)
                continue
            if now - self.shallow.get(unit, -1e18) < self.SHALLOW_AGAIN or unit not in self.epochs:
                continue
            self.shallow[unit] = now
            self.write_event(unit, now, "archive.shallow", ALARM, cam=row.get("cam"), depth_days=depths[unit],
                             min_depth_days=floor)
```

**Почему не просто «глубина меньше пола».** Запись, которую завели три дня назад с полом семь дней, мелкая — потому что молодая. Тревога по ней каждое утро научит оператора не читать тревоги. Отличить два случая можно по одному числу состояния тома: `firstBlockId`. Пока оно ноль, кольцо не сделало ни одного оборота и ничего не перезаписало. Мелко — значит молодо. Когда оно больше нуля, кольцо уже отдаёт старое, и мелкая запись — это запись, у которой кольцо забрало обещанное.

Прошлая версия различала эти случаи журналом удалений: была ли строка «ватерлиния срезала внутри пола». Журнала больше нет, а вопрос остался тот же. Ответ на него теперь даёт сам том, без бухгалтерии рядом.

**Почему тревога, а не строка в логе.** Запись, которая держит четыре дня из обещанных тридцати, — то, о чём потом спросят. Тревога `archive.shallow` пишется классом `alarm` в бакет записи `rec/<запись>/` под её эпохой — один раз, когда началось, и раз в сутки (`SHALLOW_AGAIN`), пока длится. Каждую минуту было бы шумом; один раз навсегда — забылось бы.

**Почему только держатель эпохи.** Условие `unit not in self.epochs` — то же правило, что у любых событий (М10A, урок 12): в бакет записи пишет тот, кто держит её эпоху. Иначе два регистратора, видящие один том, подняли бы две тревоги. Пишет платформенный `write_event` — под эпохой записи и с `of` её камеры, которую база читает из строки записи (`about`).

Ответ на тревогу комментарий называет прямо: квота больше или меньше записей на томе. Система своё сделала — сказала.

**Пол, который не число, — не повод тревожить каждый день** (девятое ревью: команда продукта нашла у себя, что слово или `nan` в сроке читались как число; в курсе проверены три читателя дней: сроки ресурса, потолок двери регистратора и этот пол). Поле типа `float` пропускает `"nan"` и `"inf"`: такой пол не встречает ни одна глубина, и `archive.shallow` поднималась бы раз в сутки по записи, которой ничего не обещали. Теперь пол идёт через `rows.number`: `nan`, `inf` или слово читаются как «не сказано» (0 — пола нет), строка считается один раз (`fields_garbled`) и попадает в лог с именем записи. У потолка правило обратное, и оно описано в уроке 8: потолок `retention_days`, который не читается, прячет всё старше «сейчас», а не падает на тридцать дней по умолчанию (`archive.visible_from`, таблица `CEILINGS`). Пол, прочитанный как «нет пола», ничего не удаляет и не показывает лишнего; потолок, прочитанный как тридцать дней, показал бы больше обещанного. Отдельного теста у пола нет — открыто. Тест потолка: `test_garbled_rows.py::test_a_recordings_ceiling_that_is_no_number_of_days_hides_and_does_not_fall_back_to_thirty`.

Глубина уходит в статус записи (`depth_days`, `shallow`) и оттуда — в метрики. Кода метрик у VMS нет: две строки в `metrics:` спеки записи, и консоль платформы считает их по heartbeat'ам регистраторов (М10A, урок 15, шаг 11):

```yaml
  - {name: archive_depth_days, from: status.depth_days}
  - {name: archive_shallow, from: status.shallow, agg: flag, when: depth_days}
```

Тест `test_disk_full.py::test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_ring_does_not` проходит всё целиком. Запись `7` с полом семь дней держит десять, кольцо не замкнуто — тревоги нет. В том пишут поток `flood` больше квоты, кольцо замыкается, глубина `7` падает ниже семи — одна тревога, а запись `8` без пола молчит. Через минуту — всё ещё одна. Через сутки — вторая. Пол сняли — `shallow` пропадает. В конце консоль отдаёт `rec_archive_depth_days` и `rec_archive_shallow` по heartbeat'у.

`min_depth_days` — пол записи, слово подсистемы. У ватерлинии платформы пола нет вовсе: её строка `platform/space` — это `{enabled, high, low}` (шаг 8), а что у подсистемы есть пол, знает только подсистема.

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

Камера, интервал, заметка, кто поставил и когда. В строке и на двери границы называются `from` и `to`, как во всех дверях архива и у продукта (обратная связь, BQ).

Таблицу объявляет спека записи, и обслуживает её консоль платформы (М10A, урок 15, шаг 12):

```yaml
  keeps:
    key: "{cam}-{from:int}-{to:int}"
    fields:
      cam:  {type: string, required: true}           # whose: the camera `about` names (`rights.unit_of`)
      from: {type: float, required: true, schema: {exclusiveMinimum: 0}}
      to:   {type: float, required: true, schema: {exclusiveMinimum: 0}}
      note: {type: string, schema: {maxLength: 500}}
      recordings: {type: list}
    stamp: [by, at, made_at]
    journal: {written: archive.keep.made, deleted: archive.keep.lifted}
```

**Идентификатор — сам интервал:** `key` шаблоном `<камера>-<с>-<по>` в целых секундах. Повторный POST пишет ту же строку, и двое, отметившие одни и те же десять минут, отметили их один раз.

**Имена записей пишутся в строку.** Том знает видео по имени записи (`7`, `7-cloud`), а чья это запись, говорит её строка. Удалите запись — и ничто больше не связывает поток `7-cloud` с камерой 7. Поэтому метка запоминает имена, которые нашла при постановке, а запись той же камеры, созданная позже, находится по своей строке. Тест — `test_a_keep_holds_a_recording_whose_row_is_gone_and_one_made_after_it`.

Метку ставит и снимает консоль платформы — маршрутами объявленной таблицы: `GET /rec/keeps`, `POST /rec/keeps`, `DELETE /rec/keeps/<id>`. Ставит её оператор: таблица названа в `rights.routes.edit`, и права спрашиваются на камеру метки (`rights.unit_of: {keeps: cam}`). И постановка, и снятие — строка в журнале с именем: `archive.keep.made`, `archive.keep.lifted`. Кто поставил, написано в самой метке (`stamp`). Кто **снял**, без журнала не узнать: строки уже нет.

**Метка без тома `incidents` — метка, и это видно.** `POST /rec/keeps` отвечал 201 и тогда, когда тома вида `incidents` не объявлено: `keep_pass` выходил сразу, видео никто не копировал, оператор думал, что доказательство защищено (ревью платформы, B10). Ответ остаётся 201 — метка верна, двери её показывают, — а `rec_keeps_unprotected` на `/rec/metrics` считает такие метки, пока тома нет. Это тоже строка `metrics:` спеки, без кода: `{name: keeps_unprotected, count: table keeps, unless: {table: volumes, where: {kind: incidents, enabled: true}}}`. Тест — `test_keeps.py::test_the_console_sets_a_keep_lists_it_and_lifts_it`.

Снятие метки ничего не стирает. События снова живут по своему сроку, с ближайшего прохода ресурса. Копия видео в томе `incidents` остаётся, пока её не перезапишет кольцо этого тома: удалять из кольца нечем (шаг 1), и копировать её больше никто не будет. Список меток консоль отдаёт только по тем камерам, которые спрашивающий видит (обратная связь, CG; `test_the_list_of_keeps_is_what_the_caller_may_see`).

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

И контроллер не размещает на нём записи, сколько бы места там ни было. Кода для этого у VMS нет: строка тома `incidents` обязана сказать `admits: false` — так велит схема таблицы `volumes`:

```yaml
        - if: {properties: {kind: {const: incidents}}}
          then: {properties: {admits: {const: false}}, required: [admits]}
```

— а размещение платформы по `affinity` место с `admits: false` не берёт (М10A, урок 11, шаг 6). А том, который стал `incidents`, когда на нём уже стояли записи, их отдаёт: регистратор жив, но его место больше никого не принимает, и `leaving` уводит его записи с причиной `r-1's volume v1 admits no unit` (М10A, урок 11, шаг 17; ADR 0056). Иначе запись крутила бы своё кольцо в архиве улик, пока жив регистратор. Обе половины нужны. Ёмкость ноль говорит «я не место для записи» в heartbeat'е. Фильтр не даёт контроллеру ошибиться, если heartbeat устарел. Тест — `test_an_incidents_volume_is_a_place_for_evidence_and_never_one_to_record_into`. Как такой том объявляют, разбирает [урок 27](27-volumes.md).

**Проход копирования.** Раз в минуту (`KEEP_EVERY`), в своём потоке, как дозапись (урок 16), регистратор тома `incidents` проходит по меткам и по записям каждой метки:

```python
                gaps = subtract((k.since, k.until), self.store.coverage(rec))
                shown, speaks = self._doors_show(rec, k.since, k.until, doors) if gaps else ({}, [])
                for a, b in gaps:
                    for name, url in doors:
                        # Only what this door shows of the gap (the fifth pass): asked for the rest, it answered
                        # nothing, every minute, for ever.
                        have = [(max(a, x), min(b, y)) for x, y in shown.get(url, []) if min(b, y) > max(a, x)]
                        try:                             # in pieces (blocker 6): an hour's keep is not an hour in memory
                            copied = [self._copy_in(rec, smp) for lo, hi in have for _, _, smp in
                                      self._pieces(lambda x, y: self.read_samples(url, rec, x, y), lo, hi) if smp]
                        except OSError:
                            copied = []                  # that door is down: another may have it, the next pass asks again
                        if any(copied):
                            touched.append(rec)
                            break
                if rec in touched:
                    self.store.seal()                    # what was copied is readable now — and counted below
                self.keep_held[(k.id, rec)] = held = inside(k, rec)
                took = self.keep_took[(k.id, rec)] = max(self.keep_took.get((k.id, rec), 0.0), held)
                if took - held >= self.LOSS_SLACK:             # taken, and not here now: its ring wrote over it
                    lost_of[k.id] = lost_of.get(k.id, 0.0) + took - held
                got += held
                short = self._keep_short_of((k.id, rec), subtract((k.since, k.until), self.store.coverage(rec)), shown,
                                            speaks)
                missing += short
                if held > 0 and short <= 0:
                    whole.append(rec)                    # the copy of this recording is whole: what may be sealed
```

Копирует он только то, чего в томе ещё нет: интервал метки минус покрытие (`subtract`, та же функция, что у дозаписи) — и из этого только то, что дверь источника показывает на своём таймлайне (`_doors_show`, ниже). Источник — двери архивов других регистраторов (`recorder_doors`), по очереди, до первой, которая отдала кадры. Дверь, которая не ответила, — не повод останавливаться: может ответить следующая, а если нет — спросит следующий проход.

**Хранилище проход копирования читает один раз, а двери спрашивает по каждой паре.** Масштабный проход проверил, растёт ли его цена как квадрат числа записей, как у дозаписи и шлюза (урок 26, шаги 3 и 8). Не растёт: строки всех записей проход читает один раз (`_recordings()`, из взгляда прохода `Look`, урок 26) и раскладывает по камере, метки — один раз (`keeps.declared`), двери — один раз (`recorder_doors`). На каждую пару (метка, запись) остаются запросы по сети — таймлайн у каждой двери, когда в томе дыра (`_doors_show`), — то есть число дверей на число записей меток. Хранилище здесь ни при чём, а метки редки. Счётчика чтений на этот проход в тестах нет: он проверен чтением кода, а не замером.

`seal` закрывает писателя и берёт его снова. Читатель видит только закрытые блоки (урок 7), а проход сразу после копии считает, сколько метки лежит в томе. Без `seal` он посчитал бы ноль.

**Несделанная копия видна.** Метка, которую ни одна дверь не может дополнить — дверь источника на петлевом интерфейсе другого сервера, — каждый проход давала `copied = []`, а `rec_keeps_unprotected` оставался нулём: кольцо доходило до отмеченного молча (четвёртое ревью). Теперь двери на чужом loopback пропускаются (`local_only`), у метки — `missing_since` (в `keeps` heartbeat'а, когда держатель о ней говорит), общий `keep_missing` (`{метка: секунды}`) и `rec_keep_missing_seconds{keep}` в `/metrics`; метка, недокопированная дольше пяти проходов (`KEEP_UNCOPIED_AFTER`, 300 с), — тревога `archive.keep.uncopied`, повтор раз в сутки. А перезапущенный регистратор тома `incidents` восстанавливает, что держал, по **покрытию самого тома** для каждой записи каждой метки, а не только по событиям `archive.keep.copied`, которые уходят по сроку. Тесты: `test_a_keep_no_door_from_here_can_fill_is_counted_and_then_an_alarm`, `test_a_restarted_recorder_starts_from_what_the_incidents_volume_holds_for_every_recording_of_a_keep`.

**«Не хватает» — только того, что есть у источника.** Сразу после этого тревога загорелась у любой камеры со второй записью: каждая запись камеры считалась по всему интервалу метки. Камера писала час как `7` и минуту как `7-ev`, десятиминутная метка скопирована целиком — и `7-ev` навсегда «не хватало» девяти минут, с тревогой, с `rec_keep_missing_seconds` и с вопросом к дверям каждую минуту (пятое ревью; воспроизведено запуском). Теперь проход один раз спрашивает промежутки записи (`/spans/<запись>`) у каждой двери, которая отвечает (`_doors_show`), и копирует только то, что дверь показывает. В `missing` (`_keep_short_of`) идёт только то, что показывает отвечающий источник и чего нет в томе `incidents`. Если не отвечает ни одна дверь, считается весь пробел, как раньше: никто не может сказать, что этих минут нет. Тест: `test_keeps.py::test_a_second_recording_of_the_camera_that_holds_a_minute_of_the_keep_is_not_short_of_the_rest`.

**«У источника нет» дверь говорит только за то, что её том мог держать.** Пятое ревью верило любой ответившей двери, и это оказалось регрессией (шестое ревью; воспроизведено запуском). Дверь записи недостижима, а дверь регистратора **другой** камеры ответила «у меня этой записи нет». Это правда про любую дверь, кроме нужной, — а читалось как «у источника нет»: `copied 0, missing 0`, тревоги нет, и кольцо записи молча шло к отмеченным минутам. Шестое ревью поверило двери регистратора, который держит запись **сейчас**, — и запись, которая переехала, дала тот же отказ снова (седьмое ревью). Отмеченные минуты лежат на томе `v1`, его дверь молчит; запись `7` держит теперь `r-v2` на `v2`, и только с момента после метки. `r-v2` честно отвечает «ничего», и метка считалась целой: `copied 0, missing 0`, тревог ноль — ровно тогда, когда метка важнее всего.

Теперь дверь говорит за отрезки, когда её том был местом записи (`_speaks_for`). Это, во-первых, каждая эпоха записи, которую дверь показывает, от первого до последнего её мгновения живого видео: одна эпоха — один писатель в одном томе, и дыра внутри неё — настоящая дыра. Во-вторых, для регистратора, который держит запись сейчас, — всё с момента, когда он взял её эпоху: дверь говорит это сама, полем `held_since` в ответе `/spans/`. Дозаписанные куски (`…/backfill`) границ не двигают: дозапись кладёт в поток эпохи минуты, которые эпоха не записывала. Копия метки (эпоха ноль) не двигает тоже. То, за что не говорит ни одна отвечающая дверь, остаётся недостающим: ни один отвечающий том не мог этого держать, и никто не может сказать, что этих минут нет:

```python
    def _keep_short_of(self, key: tuple[str, str], short: list, shown: dict, speaks: list) -> float:
        everything = stitch([sp for spans in shown.values() for sp in spans], 0.0)
        gone = [p for g in self._keep_nowhere.get(key, []) for p in subtract(g, everything)]
        said = [(max(a, x), min(b, y)) for a, b in short for x, y in speaks if min(b, y) > max(a, x)]
        gone = stitch(gone + [p for want in said for p in subtract(want, everything)], 0.0)   # the source does not have these either
        self._keep_nowhere[key] = gone
        return sum(b - a for want in short for a, b in subtract(want, gone))
```

```python
    @staticmethod
    def _speaks_for(spans: list[dict], held) -> list[tuple[float, float]]:
        runs: dict[int, tuple[float, float]] = {}
        for sp in spans:
            e = sp["epoch"]                              # read by `scan.door_spans`: an int
            if e <= 0 or sp.get("source", "live") != "live":
                continue
            a, b = runs.get(e, (sp["start"], sp["end"]))
            runs[e] = (min(a, sp["start"]), max(b, sp["end"]))
        return list(runs.values()) + ([(float(held), float("inf"))] if held is not None else [])

    def _door_timeline(self, url: str, unit: str, t0: float, t1: float) -> tuple[list[dict], float | None]:
        import json
        import urllib.parse
        import urllib.request
        from w2cplatform.rows import answer, number
        from .scan import door_spans
        q = urllib.parse.urlencode({"from": t0, "to": t1})
        try:
            with urllib.request.urlopen(f"{url}/spans/{urllib.parse.quote(str(unit))}?{q}", timeout=10) as r:
                body = json.loads(answer(r) or b"{}")
        except RecursionError as e:
            raise ValueError(f"{url}: a timeline nested too deep to read") from e
        spans, _ = door_spans(f"{REC.name}/doors/{url}#{unit}", body)
        held = number(f"{REC.name}/doors/{url}#held_since", body.get("held_since"), float, None)
        said_at = number(f"{REC.name}/doors/{url}#now", body.get("now"), float, None)
        if held is not None and said_at is not None:
            held = self.wall() - max(0.0, said_at - held)
        return spans, held
```

**Ответ двери читается по отрезку** (восьмое ревью, часть 4). `_speaks_for` читал `int(sp["epoch"])` вне `try` двери, и одна дверь другой сборки или прокси, ответившие `{"epoch": "e3"}`, роняли весь `keep_pass`: ни одна метка не копировалась и не проверялась, `archive.keep.lost` не поднимался. Теперь ответ двери разбирает тот же разборщик, что у скана (`scan.door_spans`, урок 21): отрезок, который не разбирается, пропускается и считается (`DOOR_SPANS`), остальные стоят. Дверь тогда показывает меньше и говорит за меньшее, и то, что она покрыла бы, остаётся недостающим — в ту сторону, в которую метке и надо ошибаться. Ответ, который вовсе не `{spans: [...]}` или длиннее `rows.ANSWER_MAX` (16 МиБ), — дверь не ответила. Тест: `test_row_reader.py::test_a_door_that_answers_a_span_another_build_writes_stops_no_keep_from_being_copied_or_checked`.

**`held_since` — по часам двери, и дверь называет свои часы** (восьмое ревью, часть 2, minor). Это момент по стенным часам регистратора-держателя, а сравнивается он с интервалом метки по часам копирующего. Новый держатель, отстающий на 1200 секунд, говорил, что держит запись на 1200 секунд раньше, чем на самом деле, и «говорил за» минуты, которых у него не было: недостача занижалась вдвое. Теперь дверь кладёт рядом свои `now`, и `now - held_since` — возраст, который не искажают ничьи часы, — откладывается от часов копирующего, прочитанных после ответа: позже момента двери, так что дверь говорит за меньшее, а не за большее. Дверь старой сборки без `now` принимается как есть. Тест: `test_row_reader.py::test_a_doors_held_since_is_laid_on_this_recorders_clock_by_the_doors_own_now`.

`held_since` — момент, когда регистратор взял эпоху записи (`RecWorker._held_since`). Эпоха отдаётся вместе с томом (`leave_volume`), поэтому двух томов она не охватывает никогда. `gone` — чего у источника нет. Он помнится по паре (метка, запись): запись на события, у которой в интервале метки ничего не было, потом удалили, держателя у неё больше нет — а сказанное её дверью остаётся, и ложная тревога пятого ревью не возвращается. Если дверь позже покажет это видео, оно из `gone` уходит. Тесты: `test_keeps.py::test_a_recording_that_moved_is_not_said_to_be_missing_from_its_source_by_its_new_holder` (метка на `v1` с молчащей дверью — 600 секунд недостаёт, потом тревога, копия целиком, когда дверь вернулась; дыра внутри эпохи нового держателя — «нет у источника»), `test_a_door_that_does_not_hold_the_recording_does_not_say_its_source_has_none`, `test_the_recordings_own_recorder_saying_it_has_nothing_is_believed_and_remembered`.

Что остаётся. Память `gone` — в процессе: после перезапуска регистратора тома `incidents` запись без держателя и без видео снова считается недостающей, и тревога придёт. Запись, за чей интервал не говорит никто, недостаёт целиком — так и должно быть. Дверь, которая `held_since` не присылает, говорит только за эпохи, которые показывает: пустой ответ такой двери — не «нет».

**Копия, которая не запечаталась, не оставляет мёртвого писателя.** `seal` после копии, не дождавшийся ответа демона, раньше оставлял в томе `incidents` закрытый хэндл: копии больше не ложились, а через 300 секунд поднималась ложная тревога `keep.uncopied`. Теперь `seal` забывает писателя до закрытия, и следующий проход монтирует том заново (урок 7, шаг 9; `test_rec_volume.py::test_a_seal_that_did_not_come_back_leaves_no_dead_writer_and_the_next_pass_mounts_again`).

Метка на час копируется не одним чтением, а кусками по минуте (`_pieces`, урок 16), каждый садится до следующего, и sha256 считается по ходу; читатель у каждого куска свой (урок 7) — общий читатель, которого закрывал проход, не давал часовой копии получиться никогда (третье ревью, блокеры 5–6). И `archive.keep.copied` пишется с барьером и несёт `seconds`: регистратор тома `incidents`, перезапущенный, восстанавливает, что держал (`_keeps_held_before` — последнее `copied` минус `lost` после него), и тревога `archive.keep.lost` о минутах, которые кольцо забрало, пока он был выключен, всё равно приходит. Тест: `test_keeps.py::test_kept_footage_the_ring_took_while_the_recorder_was_restarting_is_still_an_alarm`. Строка событий, в которой `seconds` или момент не число (слово, `nan`, четыреста цифр от ручной правки ведра), или строка, которая вовсе не объект, раньше бросала исключение из всего прохода по меткам. Ни одна метка тома в этом проходе не смотрелась (сосед десятого ревью). Теперь такая строка читается как «не сказано» и считается (`fields_garbled`), а остальные складываются как раньше. Тест: `test_one_bad_element.py::test_a_keep_line_whose_seconds_or_moment_is_no_number_is_that_lines`.

**Кадры ложатся последовательностями, а не одним куском:**

```python
    # Frames from another recorder's door into this volume, as `<recording>/e0`, one sequence per stretch — a hole
    # inside a sequence would be drawn as footage. What the door handed over starts on a key frame.
    def _copy_in(self, rec: str, samples: list) -> bool:
```

Индекс рисует последовательность сплошной. Если между двумя кусками метки не было видео, а копия легла одной последовательностью, таймлайн нарисует там запись, которой не было. Поэтому разрыв больше `stitch` закрывает последовательность (`finish`), а следующая открывается только на ключевом кадре — другого начала движок не принимает (`SEQUENCE_NEEDS_KEY_SAMPLE`, урок 7).

**Почему эпоха ноль.** Копия — ничья аренда. Пока живое видео ещё в кольце записи, его минуты принадлежат его собственной эпохе: `authoritative` отдаёт каждый промежуток старшей эпохе, а любая настоящая старше нуля. Когда кольцо записи забрало их, копия — то, что осталось. Дверь записи при этом не помечает `e0` как отсечённую: она сравнивает только эпохи больше нуля (`0 < sp["epoch"] < cur` в `timeline`, `vms/footage.py`).

**Потолок не прячет отмеченное.** И с обеих сторон копии. Дверь регистратора, который держит запись, показывает отмеченные минуты за потолком `retention_days` (`_kept_of`, урок 8):

```python
    # The intervals of a recording somebody said to keep (`vms/keeps.py`): the door shows them whatever the ceiling,
    # because a keep is the operator's word that those minutes matter longer than the recording's days — and the
    # recorder copying keeps into an incidents volume reads them through this very door. Not readable is none:
    # the ceiling stands, which hides, and hiding is the side to err on.
```

Поэтому метка на минуты старше срока записи тоже копируется, пока кольцо записи их держит: обрежь дверь вопрос по потолку, и такая метка в том `incidents` не попала бы вовсе. Тест — `test_review_remainder.py::test_the_door_cuts_a_span_at_the_ceiling_and_shows_what_a_keep_holds_behind_it`: без метки дверь не отдаёт кадров одиннадцатидневной давности, с меткой — отдаёт.

А дверь регистратора тома `incidents` показывает всё:

```python
    def _visible_from(self, unit) -> float:
        from .archive import visible_from
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
```

Тест `test_a_keep_is_copied_into_the_incidents_volume_and_outlives_the_recordings_ring` проходит путь целиком. Десять минут отмечены и скопированы, `seconds == 600`, в томе один поток `7/e0`. Второй проход ничего не копирует и событие не повторяет. Потом дверь исходной записи закрывают — её кольцо ушло дальше или сервера больше нет. Дверь тома `incidents` по-прежнему отдаёт таймлайн с эпохой ноль и кадры, начинающиеся с ключевого.

## Шаг 7 — Что копия обещает и чего не обещает

**Дайджест того, что скопировано.** Проход, который что-то скопировал, пишет событие:

```python
    #   archive.keep.copied   an event, when a pass copied something: the recording, the seconds, and the sha256
    #                         of the frames as the incidents volume now holds them — "is this what was kept"
```

Дайджест считается по кадрам в томе `incidents` после копии, а не по тому, что пришло из двери. Это ответ на вопрос «то ли это, что отметили»: тот, кто через месяц выгрузит интервал, сравнит. Дайджест остаётся и в heartbeat'е регистратора (`keeps`), когда проход ничего нового не копировал.

**Печать ставят один раз.** Дайджест в `archive.keep.copied` сдвигается с каждой копией и стареет вместе с событием. Печатью он поэтому быть не может: печать, которая идёт за томом, ничего не доказывает. Печать ставят по записи и один раз — когда том `incidents` впервые держит копию целиком (`whole`: лежит и ничего не недостаёт из того, что есть у источника). Пишет её регистратор тома `incidents`: он держит копию и считает её дайджест (ADR-0057, дополнение п. 3: пишет рекордер тома incidents). Это `RecWorker._seal`, как `SealKeeps` продукта:

```python
        have = seal.of(k) if seal is not None else {}
        fresh = {rec: d for rec, d in sums.items() if rec not in have}
        if not fresh:
            return
```

Печать живёт не в строке метки, а в своём семействе `rec/sealed/<метка>`. Это запись подсистемы о своём архиве, как метка просьбы. Спека записи называет семейство строками хранилища:

```yaml
objects: {rows: [ingest/clock/*, ingest/up/*, sealed/*, used/*], door: [taken/*]}
```

На кластере это строка хранилища, а не файл сервера, который её написал. Писать её может роль регистратора, консоль её только читает: так права генерируются из `objects.rows` (`configstore-rights.json`). Дверь таблиц семейство не обслуживает, и оператор записать печать не может по построению. В записи — `recordings: <запись>=<sha256>,…`, `from`, `to`, `keep_made_at`, `sealed_at`. `keep_made_at` — штамп `made_at` строки метки: когда её **создали**. Консоль ставит его при создании строки и переносит без изменений через каждую перезапись; `at` — время последней записи, и правка заметки сняла бы печать. Печать считается за метку, только пока её `made_at`, `from` и `to` те же. Метку сняли и поставили снова под тем же именем на те же минуты — это новая метка с новым `made_at`, и старая печать за неё не говорит: иначе новая читалась бы запечатанной копией, которую никто не проверял (ADR-0057, дополнение 2026-10-07). Печать, чьей метки нет или чья метка создана заново, регистратор тома incidents удаляет своим проходом раньше, чем печатает (`keeps.drop_stale_seals`). Первая запись создаётся только если её нет (`put_new`), дальше — CAS по прочитанным байтам (`put_at`). Кто записал её в это время, тот выиграл, и остальное печатает следующий проход. Запись, у которой печать уже есть, второй раз не запечатывается, что бы регистратор ни насчитал потом. Метку, чей интервал не читается, не запечатывают никогда. Каждая печать — событие `archive.keep.sealed` с дайджестом.

**Печать привязана к интервалу.** Оператор переписал строку метки на другие минуты — печать говорит о прежних (`Seal.of`). Сверка тогда отвечает «не запечатано», а следующий проход заменяет печать по CAS печатью интервала, как он стоит.

**Печать проверяют у двери, где лежит копия.** Сверить с печатью то, что том держит сейчас, нужно до того, как видео отдадут следователю: «вчера было в порядке» ему не ответ. Сверку делает регистратор тома `incidents`, у своей двери:

```
POST <дверь>/keeps/<метка>/verify?recording=<запись>
```

Консоль такого маршрута не имеет. Байты идут мимо неё без исключений (ADR-0015), и вопрос о байтах тоже: в продукте печать проверяла консоль, теперь это дверь регистратора (ADR-0057, пункт 3). Страница спрашивает у консоли, где держат том, для одной записи — `GET /rec/where/volumes/<том>?unit=rec/<запись>` (урок 12) — и получает дверь с токеном. В токене маршруты спеки, и `keeps` среди них потому, что спека записи его называет:

```yaml
door: {routes: [timeline, segment, keeps]}
```

Дверь пускает по тому же правилу, что `timeline` и `segment`. Только метод — POST: сверку спрашивают, а не пишут. Единица — запись из `?recording=`:

```python
        rec = str(q.get("recording", "") or "")
        if rec and not safe_segment(rec):
            return 404, {"detail": f"keep {kid} holds no recording {rec}", "error": "no such recording in the keep"}
        who = ""
        if keeper is not None:
            admitted = keeper.admit(handler, "keeps", f"rec/{rec}")
```

Токен без `keeps`, токен другой записи, запрос без `?recording=` — 401 с причиной (`route`, `unit`) от сторожа платформы (`w2cplatform/door.py`). GET — 405. Дверь, чья спека `keeps` не называет, такого маршрута не знает вовсе.

Саму сверку делает `RecWorker.verify_keep`. Дайджест «сейчас» считает та же функция, что считала печать, — `keep_digest`, одна на оба случая, чтобы они не разошлись:

```python
            elif not sealed:
                row.update(now=now, samples=samples, result="pending"); every = False   # nothing to compare with
                unknown.append(f"{rec}: not sealed yet")
            elif now == sealed:
                row.update(now=now, samples=samples, result="ok")
            else:
                row.update(now=now, samples=samples, result="damaged"); every = False
                broken.append(f"{rec}: the copy does not hash to its seal")
```

Ответ — слова продукта: `{keep, integrity, ok, recordings: {<запись>: {sealed, now, samples, result}}}`. Запись без печати, у которой в томе нет кадров интервала, интервал кончился и ни один живой регистратор не говорит на своей стороне метки, что кадры у него есть (`_empty_of`, `emptyOf` продукта, ffc94a6), — `result: empty` и `detail: "<запись> holds no footage in the interval"`. Это не отказ: метка `unknown`, но печати ждать нечего. `pending` («not sealed yet») — только когда кадры есть или ещё могут прийти. `integrity` — `ok`, `broken: <почему>` (копия не сходится с печатью или не читается, хотя печать есть) или `unknown: <почему>` (копии ещё нет, сравнивать не с чем). `ok` — только когда сравнили и сошлось. Печать читается из `rec/sealed/<метка>` (`keeps.read_seal`), и перезапущенный регистратор сверяет с той же. Каждый ответ — строка `archive.keep.verified` в журнале двери (`audit/door-<регистратор>`), с тем, кому выдан токен.

Отказы тоже как в продукте. 503 `cannot verify` — регистратор не держит тома `incidents`. Если он держит обычный том, ответ говорит, кого спросить: держателя тома `incidents`. 503 и причина — хранилище не ответило на чтение меток. Причина сказана как `StoreFault` продукта, без путей этой коробки (`console.store_fault`): путь в ответе двери снаружи никому не нужен. 409 — не читается любая часть интервала метки, не только конец. Такой метке ничего не копировали, печати нет, а хэш наполовину прочитанного интервала — догадка (ADR-0057, дополнение п. 3). 404 — нет такой метки или такой записи в ней. Тесты — в `test_keeps.py`, от `test_a_keeps_seal_is_checked_at_the_door_of_the_recorder_that_holds_its_copy` до `test_the_recorder_seals_only_a_whole_copy_of_a_keep_that_reads_and_only_once`.

**Копия — не «навсегда».** Том `incidents` — тоже кольцо. Отличие одно: в него пишут только метки, поэтому оно крутится так медленно, как ставят метки. Когда и оно полно, самые старые копии уходят — и это тревога:

```python
                # First what is GONE — before anything is copied, or a copy taken again from the recording's own
                # volume would hide that the incidents ring is too small to hold what it was given.
                now_in, before = inside(k, rec), self.keep_held.get((k.id, rec), 0.0)
                if before - now_in >= self.LOSS_SLACK:
                    lost = round(before - now_in, 1)
                    self.write_event(rec, now, "archive.keep.lost", ALARM, epoch=0, cam=k.cam, keep=k.id, recording=rec,
                                     seconds=lost, volume=self.volume)
```

`epoch=0` — строка под эпохой копий, а `of` у неё — камера записи: база читает его из строки записи. Запись, чьей строки уже нет, `of` не даёт, и строка пишется без него.

**Порядок здесь и есть правило.** Сначала проход проверяет, что пропало, и только потом копирует недостающее. В обратном порядке он перекопировал бы пропавшее из кольца записи — пока оно там ещё есть — и никто не узнал бы, что кольцо `incidents` мало для того, что ему дали. Через неделю кольцо записи тоже ушло бы дальше, и копии не стало бы без единого слова.

Тревога одна на пропажу. `keep_held` запоминает, сколько лежит сейчас, и следующий проход сравнивает уже с этим числом: пропавшее не теряется дважды. Тест — `test_kept_footage_the_incidents_ring_took_is_an_alarm`: кольцо `incidents` на шестнадцать мегабайт, метки на двадцать два, первая уходит, тревога `archive.keep.lost` класса `alarm` с секундами, и повторный проход её не повторяет.

**Что том взял, записано при томе, а не при сервере** (ADR-0057; продукт — `saveTaken`/`loadTaken`/`pruneTook` в `recproc/keeper.go`, 0ae8365). События `archive.keep.copied` лежат в дереве того сервера, который копировал. Регистратор, который взял тот же том на другой коробке, их не видит: он начинал с того, что кольцо ещё держит, и отмеченное, которое кольцо перезаписало, пока том переезжал, тревогой не становилось. Теперь `keep_pass` ведёт `took` — по каждой записи слитые отрезки, взятые в том, — и пишет его объектом `rec/taken/<том>`: `{"took":{"<запись>":[[from,to],…]},"wrapped":<bool>,"formatted":<unix s>}`, байт в байт как продукт. Объект — из `objects.door` спеки записи (`door: [taken/*]`): его отдаёт дверь ресурса, и любой следующий держатель тома читает его через своё хранилище объектов (`resource.door_readable`). Читается раз на том и формат (`_taken_read`), раньше событий: событие этого сервера, говорящее меньше, — пропажа, о которой здесь уже сказали, второй раз её не говорят. Пишется на каждую копию и в конце прохода, если изменилось, и при записи подрезается метками, которые стоят (`_taken_pruned`): отрезок вне всех меток уходит, запись, которую не называет ни одна метка, уходит целиком, снятая метка уносит свои отрезки. Метка, чей интервал не читается, держит отрезки своих записей целиком; метки не прочитались — не подрезается ничего. `wrapped` — кольцо уже переписывало взятое; это третье слово «кольцо замкнулось» для `incidents_at_risk`. `formatted` — когда том отформатирован (`createdAtUnixSec` движка, `Archive.formatted_at`): запись другого формата или без него — не этого тома и не берётся, а том, переформатированный под работающим регистратором, забывает `took`, `wrapped` и что держали метки. Тесты: `test_what_an_incidents_volume_took_outlives_its_recorder_and_its_box` и следующие за ним в `test_keeps.py`.

**Пропажа и угроза — в heartbeat'е, каждый проход** (ADR-0064, дополнение; слова продукта). Тревога говорит о пропаже один раз, а `keeps` — только сколько метка держит сейчас. Ни то ни другое не говорит из прохода в проход, что метка **короче того, что ей дали**, и что следующим кольцо перезапишет отмеченное. Это говорят два поля heartbeat'а регистратора тома `incidents` (`_incidents_said`), их строки `/servers` по спеке `rec` (`servers.status` с `of: keeps`):

- `incidents_lost` — `{метка: секунды}`. Сколько метки том когда-либо держал (`keep_took`, в цикле копирования выше; после перезапуска — вместе с `keep_held`, из `archive.keep.copied` без вычета пропаж) минус сколько держит сейчас, по каждой записи от `LOSS_SLACK` (3 с) и больше. Перекопировали — число меньше; сняли метку или её строка не разбирается — метки в поле нет.
- `incidents_at_risk` — `[метка]`. Кольцо замкнулось (`firstBlockId > 0`, как у `archive.shallow`, или уже что-то потеряло), и самые старые кадры записи в нём лежат в интервале действующей метки. Старейшее под снятой меткой — нормальная работа кольца, не угроза.

Секунды целые, список по порядку, пустые поля не пишутся — как у продукта. Своей тревоги у угрозы в курсе нет: у продукта это `archive.incidents.full` (ADR-0064, долг «Лекций»). Тесты — `test_kept_footage_the_incidents_ring_wrote_over_is_in_the_heartbeat_with_its_seconds_every_pass`, `test_a_closed_incidents_ring_whose_oldest_footage_is_kept_says_that_keep_is_at_risk`, `test_nothing_lost_and_nothing_at_risk_is_not_said`, `test_servers_shows_the_incidents_recorders_keeps_lost_and_at_risk_as_they_are`.

**Состояние метки — словами продукта, у того, кто его знает** (ADR-0064; страница читает `keeps` каждого регистратора в строках `GET /rec/servers`). Держатель тома `incidents` говорит, что держит **он** (`keep_pass`), и только одно слово — `kept`: держит кадры метки, запечатал её или знает, что у записи кадров нет (`seconds`, `sha256`, `empty: [<запись>]`). И только о метке, чей интервал читается: о битой ему сказать нечего, её называет сторона записи. Метку, о которой ему сказать нечего, он не называет; `keeps` без единой метки в heartbeat'е нет. Что лежит в томе записи и есть ли это уже в архиве инцидентов, знает только регистратор тома записи. Раз в минуту он проходит по меткам над своими кадрами (`keep_side_pass`) и говорит одну запись на метку — последнюю, как продукт: `{recording, seconds, leaves_in_s, state}`.

- `here` — лежит здесь, архив инцидентов показывает не всё, до края кольца или до `retention_days` записи больше `KEEP_MARGIN` (шесть часов).
- `pushing` — архив инцидентов есть и показывает ещё не всё: его регистратор скопирует на своём проходе. У продукта это значит «отдано толчком»: он толкает отсюда, когда срок подходит. Курс копирует сразу, тягой.
- `pushed` — архив инцидентов показывает всё.
- `at risk` — близко к краю, а копировать некому (`why`: архива инцидентов нет, или его дверь не ответила — тогда и `error`).
- `lost` — `lost_seconds`, `why`: из тома ушло, а архив инцидентов этого так и не показал — кольцо записи успело раньше. Тревога `archive.keep.lost`, раз в сутки, пока метка стоит. Держатель тома `incidents` этого сказать не мог: ни одна дверь этих минут больше не показывает, значит, и не хватает их ни у кого.
- `garbled` — `why`, `garbled_since`: строка метки не разбирается. Какие кадры она имеет в виду, неизвестно, поэтому не копируется ничего, а дверь показывает её камеру за потолком, насколько метка читается.

**Чего в курсе нет** (ADR-0064, долг «Лекций»). `released` с `why` и `released_at` — тоже слово стороны записи у продукта: битую метку, которая давно ничего не защищает, консоль отпускает, и её больше не показывают за потолком и не толкают. Курс битую метку сам не отпускает — поднимает `archive.keep.garbled` и ждёт руки, — поэтому `released` не говорит. И тревоги `archive.incidents.full` рядом с `incidents_at_risk` у курса нет: только поле.

Что показывает архив инцидентов, регистратор спрашивает у его двери (`/spans/`), той же, из которой копирует держатель, — не угадывает. Тесты — `test_the_recordings_recorder_says_its_side_of_a_keep_here_at_risk_pushing_pushed`, `test_kept_footage_the_recordings_ring_took_before_any_copy_is_lost_and_an_alarm`, `test_a_garbled_keep_over_a_recording_this_volume_holds_is_said_garbled_on_its_side`, `test_a_recording_with_no_footage_in_an_interval_that_is_over_is_empty_not_pending`.

Ответ на тревогу — квота тома `incidents` больше или выгрузка (урок 24). Метка покупает время, а не вечность. Доказательство, которое должно пережить том, выгружают.

**Не прочитал — не значит «меток нет».** Проход читает метки в начале, и это чтение не в `try`:

```python
        # A store that does not answer RAISES: unread is not "none". A keep whose row does not parse is skipped and
        # counted (`keeps.KEEPS`; the seventh pass) — it raised out of this pass, and no keep of anybody's was copied —
        # and what was copied of it is carried as it stands below, so its losses are still seen when it is mended.
        unread: list = []
        declared = keeps.declared(self.vars, unread)
```

Хранилище не ответило — проход падает и не делает ничего. Здесь обратное правило стоило бы меньше, чем в старой лестнице: проход только копирует. Но `keep_state` в heartbeat'е, прочитанный как «меток нет», сказал бы оператору, что его доказательства нигде не держат. Тест — `test_not_being_able_to_read_the_keeps_is_not_there_are_none`.

**Метка, чья строка не разбирается, — беда этой метки, а не всех.** `from: "yesterday"` в одной метке бросал из `keeps.declared`, а он стоял под копированием каждой метки, под дверью каждого регистратора и под сроком хранения событий каждой единицы на каждом сервере («не знаю, что отмечено» — не «ничего не отмечено», поэтому не удалялось ничего, и диски наполнялись; седьмое ревью, часть 2). Теперь строки меток читает общий читатель `rows.Table` (`KEEPS`; М10A, урок 8, шаг 5): битая строка пропускается, считается один раз, пока снова не разберётся (`keeps_garbled` в heartbeat'е), и пишется в лог один раз. Тому, кто не должен прочитать её как «метки нет», `declared(vars_, garbled)` отдаёт её через список `garbled` как метку её камеры **настолько, насколько она читается** — `keeps.as_far_as_read` (восьмое ревью уточнило седьмое, у которого это была вся камера от нуля до бесконечности при любом испорченном поле). Испортить метку может только интервал: `at` — метаданные, читается как «не сказано». Граница, которая разбирается, остаётся, потерянная открыта в свою сторону, без обеих — вся камера. Срок хранения ресурса держит бакеты этой камеры в этих пределах и удаляет остальные по их дням (`w2cplatform/holds.py` читает таблицу так же); единицы ни одной камеры такая метка не держит. Копировать для неё проход ничего не копирует — открытый интервал не диапазон для копии, — но её состояние переносит как было, с пометкой `garbled: True` (`state[k.id] = {**self.keep_state.get(k.id, {}), "garbled": True}`), и `keep_held` по ней не забывается: когда строку починят, пропажа из кольца `incidents` по-прежнему будет видна. Строка, в которой нет даже камеры, не держит ничего — она только посчитана и названа в логе. Тесты: `test_row_reader.py::test_one_garbled_keep_holds_its_camera_whole_and_the_others_are_swept`, `test_row_reader.py::test_a_garbled_keep_holds_its_camera_as_far_as_it_reads_and_nothing_of_the_units_of_no_camera`.

**Битая метка через час — тревога** (восьмое ревью, часть 4). Такую метку показывал только список консоли: `GET /rec/keeps` отдаёт каждую строку таблицы, битую — как она написана (`test_a_garbled_keep_is_shown_as_it_holds`). Больше её не называл никто, и строка, испорченная правкой руками, держала футаж камеры с начала времён, пока оператор не откроет список. Теперь регистратор тома `incidents` в своём проходе (`keep_pass`, `_keep_unreadable`) кладёт в heartbeat, с какого момента видит метку битой (`garbled_since`; в heartbeat'е её называет сторона записи — `state: garbled` с `why` и своим `garbled_since`). Через `KEEP_GARBLED_AFTER` (час — время починить строку руками) поднимается тревога `archive.keep.garbled` с камерой, меткой и `since`. Она одна на метку и эпизод, и повторяется раз в сутки, пока эпизод длится (`SHALLOW_AGAIN`), — как `archive.keep.uncopied`. Метка, которая снова разобралась или снята, эпизод кончает, и следующая порча — новый эпизод со своим часом. В логе — простыми словами: метку не прочитать столько-то минут, футаж её камеры держится, насколько метка читается, и ничего из него не копируется; почините метку или снимите и поставьте заново. «С какого момента» — это то, что видел этот регистратор: перезапущенный считает час заново. Тома `incidents` нет — проход не идёт, и тревоги нет; метку тогда показывает консоль, а регистратор тома записи, у которого есть кадры её камеры, говорит `garbled` на своей стороне (`keep_side_pass`, ниже). Тест: `test_keeps.py::test_a_keep_that_stays_garbled_for_an_hour_is_an_alarm_once_per_episode_and_again_once_a_day`.

**События держатся на месте.** Бакеты событий лежат на ресурсе, и их хранит по дням ресурс платформы. Что такое метка, он не знает — и знать не должен: что держит строка таблицы, говорит спека записи одной декларацией (М10A, урок 14, шаг 7, «Что удержано»):

```yaml
holds: {table: keeps, unit: cam, since: from, until: to, longest: 604800}
```

Строка `rec/keeps/*` держит события единицы, названной в её поле `cam`, — камеры — и каждой единицы, которая `about` её (записи, детекторы), на отрезок метки, но не дольше недели от его начала. Ни строки кода VMS ресурс не зовёт. Важнее всего это для `{days: 0}` — того, во что превращается срок удалённой камеры. Без `holds:` удаление камеры стирало бы ровно те тревоги, которые кто-то отметил. Тест — `test_deleting_the_camera_does_not_erase_the_events_somebody_marked`. Для событий нужна строка, а не копия: файловое дерево ресурса умеет оставить один бакет и удалить соседний, а кольцо так не умеет.

## Шаг 8 — Что осталось от ватерлинии

Ватерлиния из урока 14 М10A никуда не делась. Она меряет диск **ресурса**, и когда он выше отметки, ресурс просит освободить байты на томе своего сервера — строкой семейства запросов у каждой подсистемы, чья спека говорит `requests: {free: true}` (М10A, урок 14, шаги 12 и 14). Тест ватерлинии в `test_disk_full.py` придумывает себе такую подсистему сам — `files`, которой есть что отдать, — потому что у VMS ничего такого нет:

```python
def _files():
    """A subsystem that keeps files on the resource's disk and can give some up — `requests: {free: true}`, made up here:
    the watermark is the platform's, for whatever a subsystem keeps on that disk, and a test of it needs no product."""
```

Спека записи это говорит (`free: true`), и регистратор, держащий том этого сервера, отвечает на просьбу `rec/requests/free-<сервер>-<том>` в своём heartbeat'е: `freeing` — ноль. Его видео — кольцо того размера, что дали тому, и самые старые минуты оно отдаёт само; отдать раньше срока регистратору на диске нечего. События VMS хранятся по дням (`retain`). Два правила ватерлинии при этом остаются в силе, и первые два теста `test_disk_full.py` их держат:

- `test_the_watermark_is_on_until_somebody_turns_it_off` — без строки `platform/space` ватерлиния работает на умолчаниях. `enabled: false` — решение, которое кто-то принял, а не умолчание.
- `test_what_could_not_be_freed_is_a_number_anybody_can_read` — недостача уходит в heartbeat ресурса и в метрику консоли `w2c_resource_short_bytes{server}`, а не в строку лога. Что подсистема ещё освобождает — удалено, а на томе не видно, — она говорит в heartbeat'е (`freeing`), и ресурс этого снова не просит.

Учтите одно: собственный том сервера (`/data/vms/obsd/volume`) лежит на том же разделе данных, что и дерево ресурса. Для ватерлинии его байты — занятое место, и отдать их ей некому: кольцо не растёт сверх квоты и не уменьшается по просьбе. Поэтому квота по умолчанию кончается раньше нижней отметки ватерлинии (`_share_of_space` выше). Если ватерлиния на коробке всё же говорит о недостаче, смотрите сначала на квоту тома: её задали руками или объявили больше.

**Дозапись не ждёт диска.** Предохранитель «не тянуть с карты то, что ватерлиния собирается удалить» ей не нужен — гоняться некому:

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
| Отмеченный интервал есть в метке, а в томе `incidents` пусто | Регистратора тома `incidents` нет, или ни одна дверь не отдала эти минуты. Смотрите `keep_missing` в его heartbeat'е и состояние метки у регистратора записи (`at risk`, `lost`). |
| Метка поставлена на минуты старше `retention_days` записи, и копии нет | Дверь показывает отмеченное за потолком, значит, этих минут уже нет в кольце записи. Или дверь не смогла прочитать метки (`_kept_of` вернул пусто), и потолок устоял: следующий проход спросит снова. |
| Метку сняли, а копия в томе `incidents` осталась | Так и задумано: снятие возвращает события под их срок, а копию забирает только кольцо `incidents`. |
| На таймлайне видео там, где его не было | Копия легла одной последовательностью поверх разрыва. Разрыв должен закрывать последовательность. |
| У регистратора записи метка `lost` | Кольцо тома записи перезаписало отмеченное раньше, чем его скопировали: держателя тома `incidents` не было или его дверь не отвечала. Тревога `archive.keep.lost` с томом записи. |
| Отмеченный интервал исчез из тома `incidents` | Его кольцо дошло до него: тревога `archive.keep.lost`, а в heartbeat'е его регистратора — `incidents_lost` с секундами, пока метка стоит. Квота больше или выгрузка. |
| В heartbeat'е регистратора `incidents` есть `incidents_at_risk` | Кольцо `incidents` замкнулось, и самое старое в нём — под действующей меткой: следующий блок перезапишет отмеченное. Квота больше или снять метки, которые уже не нужны. |
| Копия пропала, а тревоги не было | Проход сначала перекопировал из кольца записи, потом считал пропажу. Порядок обратный. |
| На том `incidents` разместили запись | Строка тома без `admits: false` — схема таблицы `volumes` такую не пропустит; ноль в ёмкости регистратора фильтра не заменяет. |
| `w2c_resource_short_bytes` не ноль на коробке | Над отметкой, а отдать ватерлинии нечего. Часто это сам том архива на том же диске: смотрите его квоту. |
| Удаление камеры стёрло отмеченные тревоги | В спеке записи нет `holds:` — ресурсу никто не сказал, что держит метка. |

## Итог

- Прохода, удаляющего видео, нет. Том — кольцо, и самые старые блоки он отдаёт сам.
- Сколько архив держит, решает размер тома. `retention_days` — только потолок того, что показывают двери.
- Внутри одного тома у записей общее время. Разное обещание — разные тома.
- Квота — размер кольца. Новая квота применяется сразу, без остановки писателя.
- Глубина записи читается из индекса. Пол записи не исполняют, за ним следят.
- Мелкий архив тревожен только тогда, когда кольцо замкнулось (`firstBlockId > 0`). До этого он мелок, потому что молод.
- Метку нельзя держать на месте в кольце. Её копируют в том `incidents`, куда ничего не записывают. Двери показывают отмеченное и за потолком, поэтому копируется и метка старше срока записи. Снятая метка оставляет копию до тех пор, пока её не перезапишет кольцо `incidents`.
- Копия проверяема: `archive.keep.copied` с sha256. Копия не вечна: когда кольцо `incidents` дошло до неё, это тревога `archive.keep.lost` и `incidents_lost` в heartbeat'е; когда дойдёт следующим — `incidents_at_risk` (ADR-0064).
- Сначала проверить пропажу, потом копировать — иначе пропажа незаметна.
- События держатся на месте строкой метки и декларацией `holds:` в спеке: дерево ресурса умеет то, чего не умеет кольцо, а что держит метка, ресурс читает из спеки, не из кода VMS.
- Ватерлиния — платформы, для того, что подсистемы держат на диске ресурса; на её просьбу освободить (`free: true`) регистратор отвечает нулём. Дозапись не ждёт диска — только тома.

## Упражнения

1. Возьмите `test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_ring_does_not` и уберите условие `not closed`. Что увидит оператор новой коробки в первую неделю?
2. Две записи на одном томе: одна пишет 2 Мбит/с, другая 8. Квота — 1 ТБ. Посчитайте глубину каждой. Затем посчитайте, какой должна быть квота, чтобы у первой было тридцать дней.
3. Переделайте `test_a_new_quota_resizes_the_ring_without_stopping_the_writer` на уменьшение: том на 32 МБ, запись на 30 МБ, квота 16 МБ. Что покажут `firstBlockId` и глубина до и после?
4. Поменяйте порядок в `keep_pass`: сначала копировать, потом проверять пропажу. Повторите `test_kept_footage_the_incidents_ring_took_is_an_alarm`, оставив дверь исходной записи открытой. Поднимется ли тревога?
5. Уберите `seal` после копии. Что посчитает `inside` в том же проходе и что попадёт в heartbeat?
6. Сделайте копию одной последовательностью, без `finish` на разрыве. Отметьте интервал, внутри которого пять минут не было записи, и посмотрите на таймлайн тома `incidents`.
7. Запишите копию под текущей эпохой записи, а не под нулём. Что покажет шкала страницы, когда эпоха записи сменится?
8. Уберите из `_share_of_space` третье слагаемое — то, что держит диск под нижней отметкой. Диск занят на 30 % до первого форматирования. Посчитайте, где окажется ватерлиния (`high: 0.85`), когда кольцо заполнится. Что скажет `w2c_resource_short_bytes` — и что из курса могло бы его уменьшить?

## Что дальше

Архив теперь говорит, сколько держит, и сохраняет то, что велели сохранить. Следующий урок — **[урок 19](19-the-cameras-credential.md)**: пароль камеры, единственное поле строки, которое нельзя показать даже тому, кто вправе её редактировать.

Как отмеченный интервал выгрузить и отдать тому, кто будет разбираться, — **[урок 24](24-an-interval-in-the-browser.md)**.

# Урок 10 — `recworker`

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/rec.subsystem.yaml` — четвёртую подсистему, единственную с настоящим домом; и `vms/recworker.py` — `RecWorker`: `source` из чужого heartbeat'а, `enrich`, `status`, `resubscribe`; том и его захват (`volume_pass`, `_write_into`, `_place_kind`); `RecSink` — то, во что пишет конвейер; ответы на отказы тома (`_volume_refuses`, `_lost_engine`); уход с тома (`leave_volume`, `after_stop`) и сторож писателя (`writer_pass`).
**Время:** ~95 минут.

## Зачем этот урок

Первая подсистема заняла четыре урока. Эта занимает один — и убывание **и есть доказательство**, что шаблон существует.

Сама подсистема — тот же класс воркера над другими строками: четыре константы и три переопределённых метода, ни одного переопределённого метода цикла сверки. Всё остальное в файле отвечает на вопросы, которых у воркера не было: куда писать и что делать, когда туда писать нельзя.

Четыре вещи, ради которых урок стоит читать внимательно.

**`home` — и почему якорь пары именно здесь.** Регистратор — единственное, что тут двигаться не может: он приколочен к тому, в который пишет. Поэтому место называет строка записи, а камера приходит к ней (`near: rec` в спецификации VMS). Пара всё равно оказывается на одном сервере, и регистратор читает разделяемую память вместо сети; но решает тот, у кого том.

**Источник берётся из чужого heartbeat'а.** Регистратор узнаёт, куда подписаться, прочитав объект, который опубликовал воркер VMS. Не спросив его, не спросив контроллер — прочитав. Ради этого адрес раздачи с самого начала лежал в heartbeat'е (урок 4).

**Переподписка при переезде.** Держатель камеры переехал на другой сервер — регистратор замечает это сравнением адресов и переподписывается под новой эпохой. Видео, записанное до переезда, остаётся в томе под старой эпохой, в своём потоке; таймлайн консоли сливает оба.

**Писатель живёт не в регистраторе.** Видео пишет движок ObjectStorage, и движок — отдельный процесс на хосте, `obsd` (урок 6). Регистратор открывает том через демон, держит его писателя, а когда демон пропал — открывает заново. Каждый отказ тома он называет по виду, и на каждый вид отвечает по-своему.

> **Проверка без железа.** Весь урок, кроме конвейера GStreamer. Регистратор, том, захват, писатель, отказы и остановка проверяются против настоящего `obsd`: тесты сами поднимают его на своём сокете (`tests/vmsconftest.py`, `ObsdDaemon`), а без него падают с подсказкой, как его собрать (`ObjectStorage/standalone-build/build.sh <out>`, затем `OBSD_BIN=<out>/build/obsd`). Кадры в том подаёт поддельный актуатор (`FakeActuator.feed`). Настоящий конвейер с `appsink` (урок 9) требует GStreamer.

## Что нужно знать заранее

- **Урок 4** — две ветви раздачи, `live_url` и `live_shm` в heartbeat'е.
- **Урок 6** — [`obsd`](06-objectstorage-the-engine.md): почему движок — процесс, сессия, писатель, `Unavailable`.
- **Урок 7** — [том, блок, последовательность, поток](07-volume-block-sequence-stream.md); имя потока `<запись>/e<эпоха>`.
- **Урок 8** — [видимость](08-visibility-retention-timeline.md): читатель видит только закрытые блоки, `retention_days` — потолок того, что показывают.
- **Урок 9** — `GstRecActuator`: `appsink`, каждый кадр — сэмпл в писатель тома.
- **Урок 27** — [виды томов](27-volumes.md): `local`, `network`, `backup`, `edge`, `incidents`. `edge` — карта камеры, и это место, а не том движка: её пишет регистратор камеры обычными файлами ([урок 26](26-a-backup-archive-of-our-own.md), шаг 10).
- **М10A, урок 7, шаг 11** — слот, захват места, запасной, место за именем; **урок 8, шаг 9** — рантайм воркера: цикл, шаг аренд, подменщик; **урок 11** — `home`, `near`, `holder_near`, `ensure_home`, `servers: distinct` и `idle_by_policy`, места `placement.places` (шаг 13); **урок 15, шаг 6** — `/where/<table>/<place>`, у кого место сейчас.

## Чему вы научитесь

1. Описывать подсистему, чья единица — производная от единицы другой подсистемы.
2. Ставить аффинность и понимать, что она даёт и чего не гарантирует.
3. Находить, куда подписаться, чтением чужого heartbeat'а.
4. Отказываться стартовать, когда нельзя, — так, чтобы это было состоянием, а не ошибкой.
5. Замечать переезд держателя и переподписываться.
6. Отличать заявление о месте от факта, что его кто-то обслуживает, — и захватывать место так же, как имя.
7. Открывать том через демон, держать его писателя и открывать заново, когда демон пропал.
8. Отвечать на отказ тома по его виду: `away`, `wrong`, `busy`.
9. Уходить с тома в правильном порядке: сначала писатель, потом захват.
10. Проверять, что писатель пишет: сравнивать отданное с дошедшим и называть «застрял» и «теряет» по-разному.

---

> **Две личности одной строки.** У записи есть `id` — какая это запись: её эпоха `rec/epoch/<id>`, её слот, её поток `<id>/e<эпоха>` в томе. И есть поле `cam` — чьей раздаче она подписывается. В коде они разведены с самого начала: `source(cam["cam"])` ищет держателя камеры, `sources[cam["id"]]` помнит подписку **этой** записи. Долгое время спека говорила `id: cam`, и обе личности совпадали: запись камеры 7 называлась `7`. Перестали совпадать они не ради избыточности, а из-за второго архива — об этом Шаг 1 и записка [`СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ.md`](СКОЛЬКО-ЗАПИСЕЙ-У-КАМЕРЫ.md). Ни одна строка Python при этом не изменилась — именно потому, что разведены они были не про запас.

## Шаг 1 — Единица, названная чужой единицей

```yaml
name: rec
…
about: {sub: vms, field: cam}
unit:
  rows: recordings                   # rec/recordings/<name>
  id: name                           # "7", "7-cloud" — the operator's name for THIS recording
  fields:
    name:           {type: string, required: true}   # which recording this is: its key, its epoch, its streams
    cam:            {type: string, required: true, fixed: true}   # WHOSE footage it holds — the VMS camera id
    retention_days: {type: int,    default: 30}      # media: how far back its door shows it — a ceiling, the ring decides what is there
    enabled:        {type: bool,   default: true}
    labels:         {type: list}                     # where it may run: a recorder whose server has these labels
    …
    home:           {type: string, ref: rec/volumes, must_match: {cam: cam}}
    …
```

Полей больше шести (`min_depth_days` — урок 18, `until` — урок 25, `when` — урок 26), но первое решение — в строке `id: name`.

Остальное в этом листинге — декларации, которые исполняет платформа (ADR 0002, М10A, урок 9). `about` говорит, что запись — про камеру: её события — и события камеры, грант на камеру 7 включает её записи. `fixed: true` у `cam` — запись не переезжает на другую камеру. `ref` и `must_match` у `home` — дом записи должен быть строкой `rec/volumes`, а том-карта камеры (`cam` в строке тома) принимает записи только своей камеры.

**Единица — это одна запись, а не одна камера.** Пока у сервера был единственный архив, разница не проявлялась: «писать камеру 7» была ровно одна строка, и звать её `7` ничего не стоило. Спека так и говорила: `id: cam`.

Разницу создаёт **второй архив**. Добавьте том — сетевое хранилище рядом с локальным диском, — и «писать 7 на диск, хранить неделю» и «писать 7 в сетевой архив, хранить год» становятся двумя записями одной камеры. У каждой свой потолок видимости, свой поток, своя эпоха, свой писатель. Два ряда. А ключ `rec/recordings/7` один, и вместить оба не может.

Отсюда `id: name`, и заметьте, чего в этом решении **нет**: числового идентификатора. Номер не сказал бы, какая из записей перед вами, и оператору пришлось бы искать это в полях; имя `7-cloud` говорит само. Ровно та же форма, что у детекторов (`id: name`, `<cam>-<kind>`), и по той же причине: сущностей на одну камеру больше одной.

Простой случай при этом остался простым. Правило имени живёт в одном видимом месте — на странице VMS: первая запись камеры называется номером камеры, а если это имя занято — `<номер>-<том>` (урок 12). Установка с одним томом пишет `rec/recordings/7` и поток `7/e1`. Умолчания **внутри спеки** нет намеренно: его никто не прочитает, а опираться начнут сразу.

`retention_days: 30` — **сколько дней видео показывают, и это свойство записи, а не камеры.** Разделение из урока 1, доведённое до конца. Удалять по сроку в томе нечего: том — кольцо, и старое он отдаёт сам, когда заполнен. Поэтому `retention_days` — потолок того, что показывают двери архива (`visible_from`, урок 8), а не срок удаления.

Заголовок файла формулирует то, ради чего всё это:

> *Created by the operator: a camera exists without a recording (watched: live, detected, its events kept), and records when a row is here — from the page's Record form, which POSTs `/rec/recordings`.*

**Запись — отдельная сущность, создаваемая отдельно.** Камера без записи полностью работоспособна: её смотрят вживую, на ней работают детекторы, её события пишутся и хранятся год. Нажали «Запись» — появилась строка в другой подсистеме, и контроллер записи её разместил.

Сравните с формой, где запись — флаг на камере. Тогда «писать или нет» решается в подсистеме `vms`, размещается по её ограничениям, и мы возвращаемся к процессу, которому нужны и камера, и том.

## Шаг 2 — Размещение: три ограничения и одно предпочтение

```yaml
placement:
  capacity:   {from: capacity, default: 50}         # cameras a recorder can write — its own number, from its heartbeat: disks and NIC
  headroom:   {from: headroom}
  constraint: labels-subset
  …
  requires:   resource                               # the only subsystem that must be where the archive is
  # what a recorder holds, one each; a volume any box may serve is let go when its hold goes unconfirmed (`lease`)
  places:     {table: volumes, where: {enabled: true}, server_field: server, lease: strict}
  place_by:   volume                                 # WHAT `distinct` and `home` count in: the disk, not the box —
  …
  servers:    distinct                               # one recorder per VOLUME carries recordings (the others idle)
  tie_break:  most-free-capacity
  …
  home:       home                                   # the row's field naming the volume whose archive holds it
  …
  affinity:   {field: home, table: volumes, server_field: server, strict: {kind: [backup, edge], enabled: true}}
  rebalance:  {dead_band: 0.10}
```

`places` — какие строки служат местами регистратора и как их держать сквозь молчание хранилища (шаг 3). `affinity` — фильтр, а не предпочтение: запись с домом на резервном томе или карте камеры становится только туда, и больше никто туда не становится (урок 26). Обе строки исполняет платформа; кода VMS для них нет.

`requires: resource` — *единственная подсистема, которая обязана быть там, где архив.* Регистратор пишет на ресурс своего сервера события записи (`archive.shallow`, `archive.keep.*`), а собственный том сервера лежит на тех же дисках, вне дерева ресурса (на коробке `/data/vms/obsd/volume`, шаг 8). Нет ресурса — некуда писать события, и нет дисков для тома.

`servers: distinct` **по умолчанию**, и обоснование в заголовке файла:

> *a second recorder on the same disk is no second place to record, while a second one on another disk of the same box is exactly that.*

Два регистратора на одном томе ёмкости не добавляют: писатель у тома на хосте один (урок 6), и второй получил бы отказ. Поэтому единицы несёт один на том, а второй простаивает по политике (М10A, урок 11, шаг 13). На экране это видно флагом `idle_by_policy` и не выглядит поломкой.

Политику можно сменить на `shared` из консоли: бывают конфигурации, где это осмысленно.

### «Тот же сервер» и «тот же том» — разные вещи

Коробка с тремя дисками — это три места записи, и один регистратор на ней отдавал бы под запись треть купленного железа. Поэтому подсистема считает места в **томах**: `place_by: volume`, и `servers: distinct` значит «один регистратор на том». Строка записи в `home` называет том, а не сервер.

Откуда регистратор узнаёт свой том — шаг 3, и коротко: диск ему называют окружением, объявленный том он **берёт сам**.

**Умолчание — имя сервера, и это не заглушка.** У коробки, где ничего не объявлено, том и сервер — одно и то же место, поэтому `home: srv-a` продолжает значить то, что значил, а `place_by: volume` ведёт себя в точности как `place_by: server`. Конфигурация, написанная до томов, не ломается и не требует правки.

**Какая запись на каком томе** — поле `home` в строке записи, то есть та же страница, где оператор включает запись. Предпочтение, а не фильтр: том, который недоступен, означает, что запись пишется в соседний и вернётся сама, когда том встанет на место (`ensure_home`), а не что камера перестала писать.

И главное — то, чего в этом файле **нет**:

```yaml
  # No `near`. A recorder does not follow a camera around: it is the one thing here that CANNOT move, being
  # pinned to disks (`requires: resource` above), and a fan-out can be read from any server over RTSP.
```

Строчка «регистратор садится рядом с держателем камеры» звучит разумно ровно до того момента, пока не спросишь, кто из двоих может двигаться. Регистратор не может: он приколочен к тому. Раздачу же читают с любого сервера по RTSP — значит переехать способна камера, и следовать должна она. В `vms.subsystem.yaml` поэтому стоит `near: rec` и `home: near`, а здесь — настоящий дом.

Оператор отвечает на вопрос «где лежит запись камеры 7», и это ответ про том, а не про сеть. Пустой дом — обычное дело: тогда запись едет туда, где больше всего запаса.

**Даёт:** когда пара сошлась на одном сервере, запись идёт через разделяемую память. Ни упаковки в RTP, ни петлевого интерфейса, ни процесса раздачи на пути записи, ни сети. На сорока камерах это разница в загрузке, которую видно.

**Не даёт:** гарантии. Дом лёг, ёмкость кончилась, метки не совпали — запись станет где придётся и пойдёт по RTSP. Работать будет, просто дороже, и вернётся домой одним переездом за проход, когда дом поднимется (`ensure_home`, М10A, урок 11).

Правило, сформулированное в уроке 4 и здесь применённое: **быстрый путь — предпочтение, медленный — гарантия.** Сделай дом жёстким — меткой — и первая же авария на сервере остановит запись вместо того, чтобы увести её на соседа.

`capacity` — записи, которые тянут **диски и сетевая карта этого сервера**. Число измеряет регистратор, и к ёмкости воркера на той же машине оно отношения не имеет: одно — про сеть к камерам, другое — про запись в том.

## Шаг 3 — Откуда берётся том

Том-железо — диск примонтирован, путь прописан в юните, по юниту на диск — работает ровно до того дня, когда «том» перестаёт быть диском. Сетевой архив заводят **в консоли**, и юнит-файл под него никто править не пойдёт.

Поэтому том — **место** в смысле платформы: его строку объявляет оператор, а берёт процесс. Механизм целиком платформенный — объявленная строка места, холд по CAS (тот же `Slot`, та же аренда и то же отсечение, что у имени воркера), запасной, место за именем, отпускание ([М10A, урок 7, шаг 11](../М10A_Platform/07-Slot-and-Runtime.md)). Регистратор включает его одной строкой спеки — `places` из шага 2 — и получает на каждый том две строки:

```
rec/volumes/<имя>    ЗАЯВЛЕНИЕ оператора: kind, url, server, quota_bytes,   ← таблица `volumes` спеки:
                     access_secret, enabled                                     пишет консоль платформы
rec/holds/<имя>      ФАКТ: кто пишет туда прямо сейчас                      ← холд места: пишет база воркера
```

Что из этого делает VMS: какие поля у строки тома и что значит её `server` (урок 27), как открыть том через демон и что делать, когда открыть нельзя. Это и разбирает урок дальше.

Три способа узнать свой том, и комментарий в конструкторе называет их в порядке старшинства:

```python
        # `$VOLUME` — PINNED. A disk is bolted to one machine, so the unit file that knows which disk this
        # instance mounts is the right place to say so, the way `$RECORDER_NAME` says which slot it is.
        # A pinned DISK takes no hold: nobody else can write it. A pinned volume any box may serve takes the hold,
        # the fence and the wait an unpinned recorder does (the review's seventh pass, blocker 2): pinning says WHICH
        # volume this recorder writes, and never that nobody else may — a free recorder on another box saw it unheld,
        # took it and mounted it, and the pinned one's footage went on into a writer the engine had stopped.
        #
        # Nothing pinned and volumes DECLARED (`rec/volumes/*`) — the recorder takes one, by CAS, and is
        # that volume's recorder until it stops or lapses (`volume_pass`). This is what makes a network
        # archive created on the console get served without anybody starting a process for it.
        #
        # Nothing pinned and nothing declared — the SERVER's own volume, named after the server: what every
        # single-disk box meant before any of this existed — one place, `home: srv-a` still true, `place_by:
        # volume` behaving exactly like `place_by: server`. It is the VMS's, where the VMS keeps its engine's volumes
        # (`config.OWN_VOLUME`, `/data/vms/obsd/volume`; WP-E) — never inside the resource's tree, whose walks would
        # take the ring for a subsystem, count its blocks as the tree's usage and mirror nothing of it
        # (`ARCHIVE_VOLUME` to put it elsewhere). A caller that names its tree (a bench, a test: `resource_root`) gets
        # it beside that tree, as before: one directory of its own, never the box's.
```

И проход, который решает это раз за проход, после слота и аренд:

```python
    def volume_pass(self) -> str:
        self._check_lost()
        …                                                                   # the engine says the lock is another writer's (шаг 11)
        rows = None
        if self.pinned:
            # A pinned DISK: nothing to decide — opened if it is not open, and nobody else's. A pinned volume any box may
            # serve goes on below, the way an unpinned recorder takes one, with nothing else to take.
            last = self._vol_last if self.store is not None else None
            if last is not None and not self.engine_lost and not volumes.any_box(last) and self.hold is None:
                return self.volume
            rows = self._declared()
            vol = rows.get(self.pin) or self._own_volume(self.pin)
            if not volumes.any_box(vol) and not (last is not None and volumes.any_box(last)) and self.hold is None:
                self.volume, self.volume_wait = self.pin, ""
                if self.store is None or self.engine_lost:
                    self.volume_error = str(self._write_into(vol) or "")
                    self.capacity = 0 if self.volume_error else self.full_capacity    # will not open: not a place to put a recording
                    self._place_kind(vol)
                return self.volume
        if rows is None:
            rows = self._declared()
        self._shared = {n for n, v in rows.items() if volumes.any_box(v)}   # remembered: asked between passes
        # A camera's card is not this recorder's to take: it is the camera's buffer, and only the camera's own recorder
        # (`vms/card.py`, `CardRecorder`) writes it — a recorder of the engine on the camera's box included.
        free = [n for n in volumes.servable(list(rows.values()), self.server) if rows[n].kind != "edge"]
        if self.pinned:
            free = [n for n in free if n == self.pin]   # pinning chooses which volume; the hold still decides whether
        …                                                                   # a volume that refuses writes is handed back (шаг 9)
        …                                                                   # busy for too long under our own hold (ниже)
        answers = self._engine_pass(rows, free, now)   # the volumes any box may serve, and the engine they need
        self.refused = {n: v for n, v in self.refused.items() if v[0] > now}
        free = [n for n in free if n not in self.refused and n not in self.unservable]
        if self._engine_silent_since is not None:    # an engine that answers nothing takes no volume another box could
            free = [n for n in free if n == self.hold or n not in self._shared]
        held = self.hold
        if held is not None and (held not in free or not self.renew_hold()):
            # withdrawn, disabled, taken from us — or one this host's engine may not write
            self.leave_volume(self.unservable.get(held) or f"volume {held} is not this recorder's any more")
        if self.hold is not None and self.hold in self._shared and not answers:
            # Kept, and not mounted in this pass: the ping was this pass's one wait on a silent daemon (Т-M1).
            self._away(rows[self.hold], ArchiveError("away", "obsd is not answering: no answer to a ping", "UNAVAILABLE"))
            return self.volume
        if self.hold is None and not free and self.pinned:
            return self._wait_for_pin(rows)
        if self.hold is None and not free:
            …
            err = self._write_into(self._own_volume(self.default_volume))
            self.volume, self.capacity, self.volume_error = self.default_volume, self.full_capacity, str(err or "")
            return self.volume
        …                                                                   # take one, and then OPEN it (ниже)
```

Строки про `_engine_pass`, `unservable` и `_engine_silent_since` — про движок под сетевым томом; их разбирает раздел «Сетевой том и движок под ним» ниже.

Ветка «ничего не объявлено» стоит **после** отпускания захвата, и комментарий в коде говорит зачем: снятие последнего объявленного тома не должно оставить процесс, тихо пишущий в него дальше.

**Закреплённый регистратор, чей том не открылся, — не место.** Отдать закреплённый диск ему некуда: `VOLUME` назначил его сюда. Но ёмкость он обнуляет так же, как незакреплённый со сломанным томом (ниже): иначе контроллер ставил бы записи туда, где писать нельзя. Том открылся — ёмкость полная снова.

**Закрепление выбирает том, но не даёт его.** Закреплённый регистратор холда не брал вообще, и сетевой том это ломало (седьмое ревью, блокер 2; воспроизведено двумя пробами на двух демонах). Первая проба: закреплённый A пишет в `net`. Свободный B на другой коробке видит `net` без холда и берёт его. Демон A стоит шесть секунд — B монтирует том. У A `WRITER_STOPPED` и `FENCED`, `lock_lost`, а `archive_failure`, `volume_error` пусты и потерянных секунд ноль: записи A пропали, и это нигде не сказано. Вторая проба: два экземпляра `r-1` с одним `VOLUME=net`; второй смонтировал том через секунду, и 30 кадров первого, принятых с `OK`, пропали без счёта. Теперь закреплённый **диск** по-прежнему без холда: писать в него больше некому. Закреплённый сетевой том идёт тем же путём, что у незакреплённого регистратора, только кандидат один — свой том: холд, проверка перед каждым кадром (`_may_write_volume`), подтверждение перед монтированием (`_confirm_hold`) и ожидание чужого холда. Запасного пути на собственный диск сервера у него нет. Пока холд у другого, регистратор не пишет ничего, сообщает `volume: ""` и нулевую ёмкость, как запасной, и говорит, чего ждёт:

```python
    def _wait_for_pin(self, rows: dict) -> str:
        name, vol = self.pin, rows.get(self.pin)
        why = self.refused.get(name, (0, ""))[1] or self.unservable.get(name, "")
        if not why and (vol is None or not vol.enabled):
            why = f"{name} is {'not declared' if vol is None else 'disabled by the administrator'}: nothing is recorded into it"
        if not why:
            try:
                key = self.sub.hold_key(name)
                cur = read_hold(key, name, self.vars.get(key)[0])
            except OSError:
                cur = None
            who = cur.by if cur is not None and cur.by else "another recorder"
            why = (f"{name} is being written by {who}: this recorder is pinned to it and starts writing it once {who} "
                   f"lets it go or stops")
        if why != self.volume_wait:
            log.warning("%s: pinned to %s and not writing it: %s", self.name, name, why)
        self.volume, self.capacity, self.volume_wait = "", 0, why
        return self.volume
```

Причина — в heartbeat'е, поле `volume_wait`, а на `/metrics` — `rec_volume_wait{worker} 1` у консоли и `rec_volume_wait 1` у самого регистратора (восьмое ревью, minor: второй закреплённый экземпляр с пустым `volume_error` раньше был виден только по нулевой ёмкости). На странице томов этой строки пока нет: страница — консоли. Имя тома здесь — `self.pin`, а не `self.volume`: пока холд чужой, места у регистратора нет. `_confirm_hold` теперь не монтирует сетевой том без своего холда вообще: раньше «холда нет» читалось как «это собственный диск сервера, подтверждать нечего», и закреплённый том проходил этой дорогой. `lock_lost` у закреплённого тома — ошибка тома, как у любого сетевого (шаг 11). Тесты на двух живых демонах: `test_rec_volume.py::test_a_pinned_network_volume_is_held_and_a_free_recorder_on_another_box_does_not_take_it` (проба p8: шесть секунд остановленного демона A ничего не дают B), `test_a_second_instance_pinned_to_the_same_network_volume_on_another_box_waits_for_the_hold` (проба p7), `test_a_pinned_network_volume_whose_lock_another_writer_took_is_a_volume_error_counted_said_and_mounted_again`.

**Кто какой том может взять — асимметрия, и в ней вся арифметика.** Том на коробке (`local`, `edge`, а также `backup` и `incidents` с названным сервером — `volumes.on_a_box`) может взять только регистратор **его сервера**. Карту камеры (`edge`) — и того уже: только регистратор самой камеры. Это не том движка, а буфер камеры из обычных файлов, и регистратор движка её не берёт, даже стоя на той же коробке (урок 26, шаг 10; так в продукте). Том по адресу (`network`, а также `backup` и `incidents` без сервера — `volumes.any_box`) может взять любой, а пишет ровно один, потому что `servers: distinct` над `place_by: volume` — это один регистратор на место. Поэтому один запасной на коробку принимает один сетевой том на коробку: кластер из пяти коробок впитывает пять новых архивов, не раскатывая ничего. Виды томов целиком — [урок 27](27-volumes.md); проверяет это `test_who_may_serve_what`.

Регистратор, которому тома не досталось, — **запасной**, нормальное состояние платформы ([М10A, урок 7, шаг 11](../М10A_Platform/07-Slot-and-Runtime.md)): процесс работает, не несёт ничего, сообщает `volume: ""` и нулевую ёмкость и ждёт (`test_a_declared_volume_is_taken_by_one_recorder_and_the_other_is_a_spare`).

И считается он по **двум** источникам, а не по одному: запасной — тот, у кого пустое место **и нет захвата**. Взять том и открыть его — два разных момента, и на томе, чей прошлый писатель ещё отпускает его, между ними бывает почти минута. Процесс, посчитанный в эту щель запасным, — это запасной, обещанный оператору, и процесс, которого не попросит политика масштабирования. Обе цифры неверны, и обе починятся сами, то есть никто не заметит (`test_a_recorder_that_holds_an_archive_is_not_a_spare`). Заметьте, что «поля нет» и «поле пустое» здесь значат разное. Нет — старый воркер, который читается как место по имени сервера. Пусто — «я не место».

**Потерять том — не то же самое, что потерять слот** — правило платформы (там же). Потеряв холд, регистратор останавливает записи тома, отпускает холд и **остаётся собой**: не отсечён, слот при нём, на следующем проходе может взять другой том (`test_a_withdrawn_volume_stops_the_recordings_and_leaves_the_process_running`).

**Зато том идёт за слотом** (обратная связь CF). Регистратор, убитый `kill -9` и поднятый systemd под тем же именем, — тот же воркер: свой слот он забирает сразу (урок 17). Холд тома ждал бы, пока истечёт, — 45 секунд, в которые на этом томе не писалось бы ничего. Поэтому в холде записано, **чей слот** его держит (`by`), и экземпляр этого слота забирает его раньше других кандидатов, а экземпляр, которого systemd заменил, по дороге его у преемника не заберёт. Это механизм платформы ([М10A, урок 7, шаг 11](../М10A_Platform/07-Slot-and-Runtime.md)); всем остальным том достаётся только после истечения холда (`test_a_recorder_started_again_under_its_name_takes_its_volume_back_at_once`). Писателя этого тома демон тем временем держит для того же владельца — об этом шаг 8.

**Сразу ли — решает платформа, по строке тома.** Экземпляр, взявший имя, может стоять на **другой** коробке, а прежний — быть замороженным, а не мёртвым, со смонтированным писателем. Запуском (шестое ревью, блокер 2): `r-1` на коробке A заморожен, второй `r-1` поднят на коробке B; B брал холд сразу и монтировал том через 13 секунд, A просыпался внутри своего окна записи — и все 30 кадров `OK` рядом с писателем B. Окно записи отмерено от того, что претендент **ждёт** `slot_ttl + HOLD_SKEW` (раздел «Квота» ниже), а «том идёт за слотом» это ожидание снимает. Поэтому место идёт за именем по одному правилу платформы — `Worker.hold_follows_name`, по `server_field` спеки и строке места; подсистема его не переопределяет ([М10A, урок 7, шаг 11](../М10A_Platform/07-Slot-and-Runtime.md), таблица). Для томов три его случая значат вот что:

| Строка тома | Идёт ли за именем |
|---|---|
| называет сервер (`local`; `backup` и `incidents` с сервером) — диск | только на этом сервере: там демон держит на томе одного писателя |
| сервера не называет (`network`; `backup` и `incidents` без сервера) — том любой коробки | только на коробке прежнего держателя: `holder` — `<коробка>:<pid>:<хвост>`, коробку читает `runtime.box_of`. Экземпляр того же имени с другой коробки ждёт неизменную строку холда `slot_ttl + HOLD_SKEW` по своим часам |
| не читается сейчас | ждёт, как чужой |

На той же коробке новый экземпляр берёт холд сразу. Его монтирование получает `ALREADY_LOCKED`, пока писатель старого прицеплен, замороженный старый или нет, и подхватывает писателя (`reattached`), когда тот отцеплен (шаг 8). Экземпляр, чьё имя коробки не называет (`INSTANCE_ID`), ждёт — безопасная сторона. Холд, отпущенный намеренно (`leave_volume`, штатная остановка: писатель сначала закрыт), берётся сразу, кем угодно. Тесты: `test_rec_volume.py::test_a_network_volumes_hold_follows_the_name_on_its_holders_host_and_waits_on_another` (на одном демоне: холд взят сразу, монтирование отказано, пока писатель старого прицеплен, и через пять секунд писатель подхвачен; экземпляр того же имени с другого хоста ждёт), `test_a_second_instance_of_the_same_slot_on_another_box_does_not_take_a_network_volume_from_a_frozen_one` (два демона, заморозка), `test_volumes.py::test_the_same_name_waits_out_a_network_volumes_hold_unless_it_was_let_go`, `test_stand_in.py::test_a_place_another_host_may_write_does_not_follow_the_name_and_a_released_one_is_taken_at_once`.

**Битая строка холда — беда одного тома** (`read_hold` платформы, М10A, урок 7, шаг 11). Захват разбирал строку холда каждого кандидата как есть: одна строка `rec/holds/<том>` со словом вместо числа — правка руками — роняла весь захват, и регистратор не брал **никакого** тома; список томов в консоли падал на той же строке (шестое ревью, рядом с битой строкой слота — М10A, урок 7). Теперь `read_hold` такую строку пропускает: этот том — не кандидат, пока строку не починят, остальные берутся как обычно. Пропуск считается (`holds_garbled` в heartbeat'е), пишется в лог один раз, а страница томов называет причину: *its hold row (rec/holds/a-bad) does not parse, so no recorder can take it: mend the row or delete it*. Строка тома, который регистратор **держит**, испорченная под ним, — не «держит другой»: продление и отпускание записывают её целиком заново (`_own_hold`), как строку слота. Тест: `test_volumes.py::test_one_garbled_hold_row_is_that_volumes_trouble_and_nobody_elses`.

**Битая строка тома — тоже беда одного тома, и держателя она не лишает тома.** `quota_bytes: "1e12"` или `"64M"` в **одной** строке `rec/volumes/*` — чужого сервера, правка руками, старая сборка — бросал из `volumes.declared`, а он стоит под шагом аренд каждого регистратора (`volume_pass`). Шаг аренд и heartbeat стояли в одном `try`, и heartbeat после упавшего шага не уходил: все регистраторы кластера через 45 секунд мертвы для контроллера, холды сетевых томов не подтверждены, ограда движка отвергает каждый кадр (седьмое ревью, часть 2, блокер 1; воспроизведено: 150 секунд без heartbeat'а). Теперь сделано три вещи. `volumes.declared(vars_, garbled)` читает строки общим читателем `rows.Table` (`VOLUMES`; М10A, урок 8, шаг 5): битая строка пропускается, считается один раз, пока не разберётся (`volumes_garbled` в heartbeat'е, `rec_worker_volumes_garbled` и `rec_console_rows_garbled{table="volume"}` в `/metrics`), а её имя уходит в `garbled`. `RecWorker._declared` не читает пропуск как «том снят»: том, который регистратор держит (или к которому закреплён), остаётся при нём по строке, прочитанной последней (`_vol_last`, ей он том и открыл) — но не молча без конца: через `ROW_UNREAD_AFTER` (10 минут) это тревога `archive.volume.unreadable`, раз в сутки, пока длится, со словами, что регистратор пишет том, как тот был настроен при последнем чтении, и изменение — выключение, новый размер — до него не доходит (восьмое ревью, minor: строку испортили вместе с `enabled: false`, и регистратор через три часа всё писал в том при `rec_volume_error 0`); закреплённому, который ни разу не прочитал строку целиком, открывать нечего — `ValueError` со словами «mend the row». И `lease_pass` ловит ошибки разбора (`PARSE_ERRORS`) отдельно от `OSError`: регистратор пишет, куда писал, причина — в `volume_error` и один раз в логе, `_remount_by_last` и `depth_pass` идут всё равно. Сам цикл делает шаг аренд и heartbeat в разных `try` (цикл `run` базы воркера, М10A, урок 8, шаг 9). Тесты: `test_row_reader.py::test_one_garbled_volume_row_stops_no_recorder_and_is_named_on_the_volumes_page` (чужая битая строка, три прохода — один счёт, регистратор берёт свой диск, страница томов называет строку, `/metrics` цел), `test_row_reader.py::test_a_recorder_keeps_writing_into_its_volume_when_that_volumes_row_stops_parsing`, `test_row_reader.py::test_every_loop_heartbeats_when_its_lease_step_raises`.

### Третье состояние: держит и писать не может

Двух состояний — «обслуживается» и «никто не взял» — мало, и не по теоретическим соображениям: так уже ломалось на живом ящике. Заявили сетевой архив с недоступным адресом; регистратор взял его по CAS, открыть не смог — и остался на нём стоять. Здоровый локальный диск при этом лежал необслуженным, а на экране было `wanted 2 / serving 2 / spare 0`. **Худший вид поломки: все числа зелёные, а записи нет.**

Захват — это утверждение «я за него отвечаю», и оно ничего не говорит о том, **открылся ли том**. Проверить это может только тот, кто его открывает: строка может называть путь, которого нет, монтирование, которое отвалилось, или бакет, до которого не дотянуться, и ни одно из трёх в строке не видно.

Поэтому открытие — часть захвата, а не то, что случится когда-нибудь потом:

```python
        while True:
            if self.hold is None:
                candidates = [n for n in free if n not in skipped]
                taken = self.claim_hold(candidates) if candidates else None
                if taken is None:
                    if broken and self.claim_hold([broken[0][0]]) is not None:
                        self.volume, self.capacity, self.volume_error = self.hold, 0, broken[0][1]
                        …
                        return self.volume
                    self.volume, self.capacity = "", 0             # a spare is not a place to put a recording
                    return self.volume
            name = self.hold
            err = self._write_into(rows[name])
            if err is None:
                self.volume, self.capacity, self.volume_error = self.hold, self.full_capacity, ""
                self.volume_wait = ""
                self._place_kind(rows[self.hold])
                return self.volume
            if err.name == "HOLD_LOST":                            # taken from us between the renewal and the mount
                self.leave_volume(f"volume {name} is not this recorder's any more: {err.detail}")
                return self.volume
            logging.warning("%s: %s will not open (%s) — looking for another", self.name, self.hold, err)
            skipped.add(self.hold)
            broken.append((self.hold, str(err)))
            self.volume_error = str(err)
            self.release_hold()                                    # so somebody who CAN write there may take it
```

Дальше три правила, и третье — то, без которого первые два делают хуже.

**Не открылся — не обслуживается.** `served()` читает `volume_error` из heartbeat'а держателя и такой том в `serving` не считает, а рядом пишет причину: *held by …, which cannot write there: …*. Оператор видит `1/2`, а не зелёное `2/2`.

**Не открылся — не место.** Ёмкость обнуляется той же строкой. Том, в который нельзя писать, не должен получать новых записей, и контроллеру для этого ничего знать не нужно: он просто не ставит туда, где нет свободной ёмкости.

**Отдавать — только если есть куда пойти.** Регистратор отпускает сломанный том и пробует другие; если взять больше нечего, он **забирает его обратно** и остаётся на нём с ошибкой. Иначе диагностика приводит к тому, что коробка перестаёт писать совсем: отпустил единственный архив — и стоит пустой. Писать в сломанный и говорить об этом плохо; не писать вообще — хуже.

Лечится оно само: том вернулся — следующий проход открывает его, ошибка исчезает, ёмкость возвращается. Ни кнопки, ни перезапуска. Всё это — `test_a_volume_held_and_unwritable_is_not_served`: в нём файл лежит там, где объявлен каталог, а потом его убирают.

Одно уточнение меняет, к чему это правило применяется. «Не открылся — отдать» верно, когда том **неверен** (`wrong`), и неверно, когда он **недоступен** (`away`) или **занят** (`busy`). Как их различать — шаг 9.

### Ключ — значение, а не часть адреса

Строка тома несёт `access_secret`, и правило суффикса (М10A, урок 18) держит его подальше от ответов консоли; в хранилище он лежит запечатанным ключом кластера. Но открыть том без ключа нельзя, и есть один очевидный способ всё испортить: собрать адрес вида `s3://KEY:SECRET@host/bucket` и отдать его движку.

После этого ключ оказывается сразу в нескольких местах, и ни одно из них не защищено правилом суффикса, потому что поле называется `url`: в heartbeat'е регистратора (`archive`), в сообщениях об ошибке открытия, которые попадают в журнал, и на странице, где список томов печатает `url` как есть.

Правило, которое стоит запомнить одной фразой: **ключ собирается только в том процессе, который прямо сейчас открывает том, и никогда не попадает в адрес** — он значение среди значений. В коде это две строки. `_write_into` распечатывает ключ перед открытием:

```python
            secret = open_row(self.sealer, {"access_secret": vol.access_secret}, volumes.key(vol.name))["access_secret"]
```

**Открыть — с ключом строки, и это ошибка тома.** Консоль запечатывает секрет тома, связывая шифртекст со строкой `rec/volumes/<имя>` (М10A, урок 18), — и регистратор должен открывать его с той же строкой. Первая версия открывала без неё, а ключа печатей у регистратора в юнитах не было вовсе: сетевой том получал шифртекст вместо секрета, и не писал никто (третье ревью, блокер 3). Теперь у `recworker@` есть `SECRETS_KEY`, `open_row` требует строку (умолчания нет — забыть её нельзя), а `Sealed` — ошибка **тома**: он не берётся, `volume_error` говорит почему, а аренды и heartbeat идут дальше. Тест: `test_volumes.py::test_a_network_volumes_secret_sealed_by_the_console_is_opened_by_the_recorder_with_the_key`.

А `vms/archive.py` отдаёт демону **параметры**, а не адрес:

```python
# Where a volume is, as `obsd` opens it: PARAMETERS, never a URI with a key in it — a URI is printed, logged,
# published in heartbeats; the key travels separately (`access_secret`, sealed in the store, opened only by the
# process that mounts the volume: М10A Lesson 18). Its refusals say the url as a page does (`hide_in_url`): a row stored
# before `volumes.refuse` took a key with `/` in it went into `volume_error`, the heartbeat and the log (the twelfth review).
def volume_params(url: str, secret: str = "", access_key: str = "") -> dict:
```

Идентификатор ключа бакета (`access_key`) — тоже поле строки, а не часть адреса. Он не секрет и показывается, как логин камеры; сам ключ остаётся в `access_secret` ([урок 27](27-volumes.md), `test_a_bucket_names_its_key_in_a_field_and_its_secret_sealed_never_in_the_address`).

Всё, что том показывает, показывает его **имя**. `volumes.refuse` отказывает адресу, который несёт ключ, — `@` где угодно после `://`, порт, который не число, пара с именем учётных данных в запросе или в пути (`secrets.address_refusal`; двенадцатое ревью, блокер: раньше `@` искали только до первого `/`, и секрет AWS с `/` проходил). Это единственное место, где систему ещё можно об этом предупредить; а строка, записанная до правила, видна регистратору и странице только скрытой (`hide_in_url`: поле `archive` в heartbeat'е, строка «writing into» в логе, слова ошибок `volume_params`) — [урок 27](27-volumes.md), `test_the_key_never_goes_into_the_address`, `test_a_key_in_a_volumes_url_is_refused_whatever_its_characters_and_an_old_row_is_said_nowhere`.

### Квота — размер кольца

У каждого объявленного тома есть `quota_bytes`, и у локального тоже: без неё `refuse` строку не примет. Квота — это размер кольца. Том форматируется на неё при первом открытии и дальше не растёт; заполненный, он отдаёт старейшие блоки (уроки [7](07-volume-block-sequence-stream.md) и [18](18-what-the-archive-gives-up-first.md)).

Это и снимает негласное правило «один том на раздел». Том — **доля** раздела, а не раздел. Два тома на одном диске — архив на год и архив на неделю — это два кольца, каждое своего размера.

**Размер уже отформатированного тома — у демона, не в расчёте.** Собственный том сервера без объявления получал размер по формуле — 80 % свободного — **на каждом старте**, и консоль предлагала это число как настоящий размер: заполненный диск давал «1 GiB», оператор объявлял 6 ТБ, и `resize` сжимал восьмитерабайтное кольцо, стирая два терабайта записи (третье ревью). Теперь размер тома, который уже есть, читается у демона (`READER_INFO.maxVolumeSize` → `Archive.size()`), heartbeat несёт настоящий (`archive_quota`), а **уменьшение** квоты применяется, только если строка тома несёт ещё и `shrink_confirmed` с тем же числом; иначе heartbeat говорит `quota_note`. Увеличение — сразу. Тест: `test_volumes.py::test_the_boxs_own_volume_keeps_the_size_it_has…`.

**«Том мой» — в момент монтирования, а не после прохода.** Подтверждение удержания засекалось, когда кончался весь проход; перемонтирование сетевого тома могло идти минуту, удержание за это время истекало, том брал другой хост — и `MOUNT_RW` уходил вслепую. Замок движка на s3-томе — аренда без ограждения (неатомарный захват, часы двух машин, проснувшийся держатель перезаписывает замок): вторая линия, а не первая. Теперь отметку ставит база воркера внутри `claim_hold`/`renew_hold` (платформенные, М10A, урок 7, шаг 11), а `Archive(confirm=…)` — `RecWorker._confirm_hold` — перед **каждым** `VOLUME_MOUNT_RW` (и в `seal`) продлевает холд и монтирует, только если хранилище его подтвердило; нет — том не монтируется и отпускается (третье ревью). Поколение удержания в `owner` не кладётся: оно растёт и при перезахвате своим же перезапущенным регистратором и сломало бы подхват отсоединённого писателя. Тест: `test_volumes.py::test_a_network_volume_is_mounted_only_on_a_hold_confirmed_at_the_mount`. И при молчащем хранилище перезапуск демона больше не оставляет регистратор без тома: последняя прочитанная строка тома (`_vol_last`) монтируется снова — свой диск сразу, сетевой — пока последнее подтверждённое удержание длиннее монтирования.

**«Том мой» — на каждом кадре, а не только в момент монтирования.** Проверка перед `MOUNT_RW` закрывала монтирование и ничего больше: коробка, замороженная целиком, просыпалась с уже смонтированным писателем, конвейер клал 30 кадров (все `OK`) в сетевой том, который за это время взяла другая коробка, а потом проход закрывал этого писателя со сбросом в чужое кольцо (пятое ревью, блокер 1; воспроизведено на двух демонах над одним каталогом). Теперь каждый кадр, каждый `finish` и каждый `seal` в сетевой том проходит `Archive(fence=…)` — `RecWorker._may_write_volume`, обёртку в одну строку над платформенным `Worker.may_write_place`: в место, которое держится строго, пишется, только пока холд этого регистратора подтверждён моложе `slot_ttl − lease_margin`. Так же устроен `Lease.may_act` у аренды (М10A, урок 6). Регистратор, который возьмёт том следующим, ждёт `slot_ttl + HOLD_SKEW` неизменной строки по своим часам, поэтому запись здесь кончается раньше, чем там может начаться. Отметку подтверждения база ставит по часам **до** запроса к хранилищу, как у аренды: продление, которое шло десять секунд, подтверждает холд таким, каким он был в момент вопроса; продления подменщика тоже засчитываются (`note_hold_confirmed`). Строго держится всё, кроме диска, чья строка называет сервер этого регистратора (`held_strictly`; ADR 0029): писать туда больше некому, и он не проверяется. Закреплённый сетевой том проверяется, как любой (седьмое ревью). Неотправленный кадр — `Fenced`, счётчик `FENCED` у записи, не потеря движка и не перемонтирование (урок 7, шаг 8). Это проверка перед отправкой, а не ограда: процесс, замороженный между проверкой и отправкой, один кадр всё же пошлёт (шестое ревью; воспроизведено). Ограждает том движок — патч 07, который курс требует: писатель с чужим замком не запишет ни блока. Проверка холда только сужает окно — с ближайшего блока движка до десяти секунд **до** того, как том может взять другой. Тесты: `test_rec_volume.py::test_every_sample_into_a_network_volume_needs_a_hold_confirmed_within_its_write_window`, `test_a_box_frozen_whole_writes_nothing_into_the_network_volume_another_box_took_and_closes_nothing_there`. Что бывает с писателем, когда холд уже потерян, — шаг 11.

Новая квота в строке — новый размер кольца, без остановки записи: регистратор, который уже держит этот том, вызывает `Archive.resize` (шаг 8). Уменьшение освобождает старейшее.

Первый том страница томов предлагает сама (`volumes.suggest`): известно, куда коробка пишет (поле `archive` в heartbeat'е регистратора), и подставляется размер, на который регистратор отформатировал свой том (`archive_quota`), а без него — размер раздела (`test_reader_clock.py::test_a_volume_is_served_by_a_holder_behind_and_no_longer_by_a_dead_one_ahead`, вторая половина). Дальше оператор уменьшает число и ставит рядом второй том.

**Процессы по-прежнему запускает планировщик.** Консоль показывает `served N/M · K spare`; `spare: 0` при `serving < wanted` — единственное состояние, которому нужен человек, и консоль его называет, а не исправляет сама. Это то же правило урока 4: платформа не запускает процессов — но обязана сказать число.

### Том, пока хранилище молчит

`volume_pass` читает объявленные тома и продлевает холд — из хранилища платформы, не из демона. Хранилище, которое не ответило, бросает исключение, и из-за этого регистратор **ничего не отпускает**. Не прочитать список — не значит «ничего не объявлено»; не прочитать холд — не значит «его держит другой» (обратная связь BK). `lease_pass` ловит `OSError`, регистратор пишет, куда писал, а если за это время пропал демон — монтирует том по строке, прочитанной последней (`_remount_by_last`).

Сколько место держится сквозь молчание, решает платформа: шаг аренд базы воркера (`_strict_place_pass`) по `placement.places.lease: strict` и по строке места (ADR 0012, ADR 0029; [М10A, урок 7, шаг 11](../М10A_Platform/07-Slot-and-Runtime.md)). Для томов это значит:

| Том | Пока хранилище молчит |
|---|---|
| диск, чья строка называет сервер этого регистратора (`SERVER_NAME` → `Worker.server`) | остаётся за регистратором по потолку `lease.unconfirmed_max` — у регистратора `forever`, сколько бы молчание ни длилось: писать в него больше некому, он здесь |
| всё остальное: том по адресу, диск другого сервера, любой том регистратора, не назвавшего своего сервера | с `slot_ttl − margin` без подтверждения ни один кадр не отправляется, и том отпускается; записи на нём останавливаются. Писатель закрывается, только пока холд подтверждён моложе `slot_ttl + HOLD_SKEW`; позже — бросается (`WRITER_ABANDON`, шаг 11) |

Отпускает платформа: её шаг аренд идёт раньше шага регистратора и зовёт `leave_place`, а регистратор переопределяет его одной строкой — `leave_volume` (шаг 11). Запись сквозь молчание включена только там, где второго писателя быть не может, — на своём сервере. Том по адресу может взять любая коробка, и та, что до хранилища дотягивается, возьмёт холд, когда он истечёт. Писатель у тома один **на хосте**: две коробки — два демона, и ни один не знает о писателе другого. Два писателя кадров под разными эпохами дают дубль; два писателя в один том — это уже не дубль.

Где лежит место, база помнит по строке, прочитанной при взятии и при каждом удачном продлении: в молчании спрашивать уже не у кого. Регистратор без своего сервера говорит это в heartbeat'е (`server_unsaid`) и один раз в логе при взятии тома: каждое место он отпустит в молчание, как том по адресу, — это ошибка развёртывания.

### Сетевой том и движок под ним

У тома, который может обслуживать любая коробка, есть два вопроса к демону этого хоста. `volume_pass` задаёт их раз за проход, и только когда такой том объявлен (`_engine_pass`).

**Умеет ли демон бросить том.** Когда том уходит к другой коробке, писателя здесь надо отпустить, **ничего больше не записав**: это `WRITER_ABANDON`, операция движка с патчем 07 (урок 6, шаг 6). Демон без неё закрывает писателя одним способом — сброс, статус, lock-файл по пути, — и всё это ложится в том, который к этому времени чужой. Такому демону сетевой том не дают вовсе:

```python
    def _engine_refuses(self, vol) -> ArchiveError | None:
        if not volumes.any_box(vol):
            return None
        try:
            if self.session.abandons():
                return None
        except ObsdError as e:
            return classify(e)
        return ArchiveError("wrong", f"obsd on {self.server} is too old to write {vol.name} safely — a volume any server "
                                     f"may take: this obsd cannot give a volume up when another server takes it. Update "
                                     f"obsd on {self.server}; volumes on its own disks are not affected", "ENGINE_TOO_OLD")
```

Регистратор такой том **не берёт** — холд не заявляет, ничего не монтирует — и говорит почему: `unservable`, в heartbeat'е вместе с `refused`, а страница томов дописывает это к причине «никто не взял» (`volumes.served`: *r-1 does not take it: obsd on srv-a is too old to write net safely…*). Том берёт регистратор коробки, чей демон умеет. Сообщение написано для оператора: что не так, что это значит и что делать, — без номеров патчей и имён операций. Номер патча — в комментарии рядом, для того, кто читает код. Закреплённый (`$VOLUME`) сетевой том получает тот же отказ: холд не заявлен, ёмкость ноль, причина — в `volume_wait`. Том, который регистратор уже держал, а демон заменили старой сборкой, отпускается. Диски этого сервера не затронуты.

Раньше для демона без операции был запасной режим — писатель «парковался»: оставался смонтированным и ничего не получал. Ревью показало запуском, что режим небезопасен (шестое ревью, блокер 1): процесс регистратора A стоял 51 секунду (GC, swap, `SIGSTOP`) при живом демоне; B взял холд, но монтирование отвечало `ALREADY_LOCKED` — замок движка освежал демон A; A проснулся и запарковал писателя; через 41 секунду B всё ещё был `busy`, и навсегда. Режим убран целиком. Тест: `test_lock_lost.py::test_a_recorder_takes_no_network_volume_on_an_obsd_that_cannot_give_one_up` (проба подменена: набор идёт только на движке с патчем 07).

**Отвечает ли демон вообще.** Регистратор продлевал холд, пока работал сам, что бы ни делал его демон: демон заморожен на 320 секунд — холд продлён все 320 (шестое ревью; воспроизведено запуском), на томе не пишется ничего, и коробка с живым демоном взять его не может. Теперь проход раз за проход шлёт демону `PING` (`_hear_engine`) и помнит, с какого момента тот молчит (`_engine_silent_since`; молчание при монтировании считается тоже — `_away`). Через молчание холд продлевается `ENGINE_SILENT_FOR` — 300 секунд, тот же срок, что у подменщика, по той же причине: демон обычно возвращается быстрее, — и не дольше:

```python
        held = self.hold
        silent = 0.0 if self._engine_silent_since is None else self.clock() - self._engine_silent_since
        if held in shared and silent >= self.ENGINE_SILENT_FOR:
            why = (f"obsd on {self.server} has not answered for {silent:.0f} s, so nothing is being recorded into "
                   f"{held}: this recorder gives the volume up, and a server whose obsd answers takes it. Check obsd "
                   f"on {self.server}; this recorder tries {held} again in {self.REFUSED_FOR / 60:.0f} minutes")
            self.refused[held] = (now + self.REFUSED_FOR, why)
            log.error("%s: %s", self.name, why)
            self.leave_volume(why)
```

Том отпущен — холд помечен `released`, и коробка с живым демоном берёт его сразу — и оставлен в покое на `REFUSED_FOR`, как том, который отказывает в записи. Через молчащий демон регистратор не берёт и новых сетевых томов. Подменщик холд через молчание не продлевает **вовсе** (`may_stand_in_hold`): раньше он смотрел только на эту секунду — и между двумя вызовами зависшего шага, когда соединение формально не молчит, продлевал. Диск этого сервера за молчащий демон не отпускается: его никто другой не запишет (`ArchiveError`, шаг 9).

Проход при этом ждёт молчащий демон **один** раз: `PING` — единственный вызов прохода, монтировать том в этом проходе он уже не пробует (Т-M1). Тесты: `test_rec_volume.py::test_a_network_volume_is_given_up_when_this_hosts_obsd_has_answered_nothing_for_five_minutes`, `test_a_frozen_daemon_under_a_network_volume_costs_a_pass_one_wait_and_the_volume_goes_to_a_box_that_answers` (два живых демона, первый заморожен: около сорока проходов, каждый — одно ожидание, том уходит ко второй коробке и остаётся чистым), `test_the_stand_in_renews_no_hold_while_the_pass_has_found_the_engine_silent`.

**`busy` под своим холдом — со сроком** (открытое шестого ревью, седьмое ревью). Демон, который отвечает `ALREADY_LOCKED`, не молчит: замок держит чужой писатель, и раньше том оставался за регистратором навсегда. Холд у этого регистратора, а смонтировать том он не может: замок движка освежает живой демон. Например, регистратор на другой коробке завис со смонтированным писателем или так и не отпустил том. Обычно это кончается само: замороженный проснётся, будет огорожен и бросит писателя, или демон закроет его после отсрочки. Но навсегда зависший регистратор держал том навсегда, а этот держал холд, не писал ничего и говорил `busy` бессрочно. Теперь через `BUSY_FOR` — десять минут — том отпускается и оставляется в покое на `REFUSED_FOR`, как том, который отказывает в записи:

```python
    def _busy_too_long(self, now: float) -> None:
        from w2cplatform.events import ALARM
        name, quiet = self.hold, self.clock() - self._busy_since
        why = (f"{name} has been in use by another writer for {quiet / 60:.0f} minutes although this recorder holds it, so "
               f"nothing is being recorded into it. A recorder on another server may be stuck with {name} still open: "
               f"check obsd and the recorders on the other servers. This recorder lets {name} go and tries it again in "
               f"{self.REFUSED_FOR / 60:.0f} minutes")
        self.write_event(name, now, "archive.volume.busy", ALARM, epoch=0, volume=name, seconds=round(quiet),
                         detail=self.archive_error)
        log.error("%s: %s", self.name, why)
        self.refused[name] = (now + self.REFUSED_FOR, why)
        self.leave_volume(why)
```

Тревога `archive.volume.busy` пишется через базу воркера (`write_event`), причина — в `refused` heartbeat'а и на странице томов. Другому хосту не делается ничего: его писатель — дело его движка. Незакреплённый регистратор тем временем пишет в другой свободный том или в собственный диск сервера. Отсчёт идёт с первого `busy` при монтировании (`_busy_since`) и сбрасывается удачным монтированием, уходом с тома и **любым отказом, который не `busy`** (`_away`). Последнего не было, и восьмое ревью это воспроизвело: один проход `busy` — писатель предшественника ещё закрывается, — потом сеть до хранилища лежит (`away`, его ждут без срока). Через десять минут холд отпускался, том уходил в `refused` со словами «in use by another writer for 10 minutes», а тревога `archive.volume.busy` посылала оператора искать чужой регистратор. Закреплённый регистратор после возврата хранилища не писал ещё десять минут. Теперь `BUSY_FOR` считает непрерывный `busy`. Тест: `test_rec_volume.py::test_one_busy_pass_and_then_a_network_down_for_ten_minutes_lets_no_volume_go_and_the_recorder_writes_when_it_is_back` (закреплённый и нет: одиннадцать минут `away` после одного `busy` — том при регистраторе, тревоги нет, запись — на проходе, когда хранилище ответило). Диск этого сервера за `busy` не отпускается: взять его больше некому. Тест: `test_rec_volume.py::test_a_network_volume_busy_under_this_recorders_hold_for_ten_minutes_is_let_go_with_an_alarm`.

## Шаг 4 — Класс: три константы

```python
class RecWorker(VmsWorker):
    """A recorder: `VmsWorker` over `rec/recordings/*`, its pipelines fed by the
    worker's fan-out, writing into the volume it holds."""

    SUB = REC
    ROWS = "recordings"
    …
    parse_row = staticmethod(rec_row)
```

**Три константы — и подсистема готова**: чья спека, какие строки, как их читать — та же форма, что у воркера камер (урок 3). Префикс слота и переменную с его именем говорит спека — `slot: {prefix: r, name_env: RECORDER_NAME}` в `rec.subsystem.yaml`, — и читает их база.

Слот, назначение, эпоха на единицу, аренда, отсечение на слоте, холд места, heartbeat, цикл `run` — платформенные (база `Worker`, М10A, уроки 7 и 8); цикл сверки и ворота `_actuate` — от воркера камер. Регистратор добавляет к ним свои шаги, а не заменяет чужие: `lease_pass` дописывает шаг тома (шаг 3), `reconcile_once` — переподписку (шаг 7), `pump_once` — дозапись (урок 16), `_actuate` перед остановкой выпускает кольцо резервной записи (урок 26).

Докстрока модуля договаривает:

> *Same class as the worker (`VmsWorker` over the `rec` rows): the same reconciler, the same gate (an epoch per unit, a lease, the fence at the slot), the same heartbeat. What differs is what the pipeline needs — a source, not a camera — and a sink: the volume's one writer on this host.*

**Отличий два**, и оба будут ниже: чем кормить конвейер и во что он пишет.

Конструктор добавляет то, что нужно для второго:

```python
        # Every call waits at most `OBSD_TIMEOUT` — ten seconds, a third of a lease. …
        self.session = obsd or Session(client=f"rec-{self.name}", timeout=float(env.get("OBSD_TIMEOUT", "10")))
        …
        self.pinned = bool(env.get("VOLUME"))
        self.pin = str(env.get("VOLUME") or "")      # …its name, which `volume` is not while the hold is another's
        self.volume_wait = ""                        # pinned, and waiting for the hold: why (`_wait_for_pin`)
        self.default_volume = str(self.server or "default")
        from .config import OWN_VOLUME
        beside = os.path.join(os.path.dirname(os.path.abspath(events_root)), "volume")
        self.default_url = env.get("ARCHIVE_VOLUME") or (f"file://{beside}" if resource_root else OWN_VOLUME)
        # Its size when it is new: `ARCHIVE_QUOTA_BYTES`, or — 0 — a share of the disk it will be on, which the DAEMON
        # measures when it formats it (`_share_of_space`; …)
        self.default_quota = default_quota if default_quota is not None else int(env.get("ARCHIVE_QUOTA_BYTES", "0") or 0)
        self.volume = str(env.get("VOLUME") or self.default_volume)
        self.store: Archive | None = None            # the volume open for writing, if one is
```

**Одна сессия с демоном на процесс.** Каждый том, который регистратор открывает, каждый писатель и каждый читатель — дескрипторы этой сессии, и демон знает её по токену. Почему у каждого вызова срок, и почему именно десять секунд, — шаг 10.

`self.sources` и `self.waiting` — **что слушает каждый работающий конвейер и кого никто не держит**. Первое существует ради переподписки (шаг 7), второе — ради экрана (шаг 6).

И то, чего в конструкторе **нет**: подбора за предыдущим экземпляром. Подбирать нечего: кадры уходят в демон по мере прихода, а писателя, которого оставил убитый процесс, демон отдаёт сам (шаг 8).

## Шаг 5 — Источник из чужого heartbeat'а

```python
    def source(self, cam) -> tuple[str, str] | None:
        """`(server, source)` of the worker holding the camera, from its heartbeat; None if nobody does.
        The source is the worker's shared-memory branch (`live_shm`, shm://…) when that worker is on
        THIS server — the same bytes with no RTSP hop, no fan-out process on the recording path — and
        its RTSP fan-out (`live_url`) otherwise."""
        # The store that does not answer says nothing — not "nobody holds it". …
        try:
            found = self._look().holder("vms", cam, self.wall(), phase="running", field="live_url")
        except OSError as e:
            self.store_errors += 1
            last = self.last_source.get(str(cam))
            log.warning("%s: the store did not answer for camera %s's holder (%s): %s", self.name, cam, e,
                        f"its last source {last[1]} stands" if last else "and it was never read")
            return last
        if found is None:
            held = self._held_by_the_book(cam)
            if held is not None:
                return held
            self.last_source.pop(str(cam), None)
            self.last_holder.pop(str(cam), None)
            return None
        holder, hb, st = found
        …
        self.last_holder[str(cam)] = holder
        server = hb.extra.get("server", "?")
        if server == self.server and st.get("live_shm"):
            self.last_source[str(cam)] = (server, st["live_shm"])
            return server, st["live_shm"]
        from .config import local_only
        if local_only(st["live_url"], server, self.server):
            # Announced truthfully and not for us: the fan-out is bound to loopback on ANOTHER server. …
            self.behind_loopback[str(cam)] = server
            return None
        self.behind_loopback.pop(str(cam), None)
        self.last_source[str(cam)] = (server, st["live_url"])
        return server, st["live_url"]
```

Тридцать строк, и в них — форма, к которой курс шёл с урока 4 М10A.

**Перебираются heartbeat'ы чужой подсистемы.** `self._look().holder("vms", cam, …)` ищет среди объектов воркеров VMS того, кто держит камеру — по тем же правилам, что `holder_of` консоли: первый живой воркер по имени, чей статус называет камеру. Ни запроса контроллеру, ни вызова воркера, ни специального ключа «где камера»: регистратор читает то, что воркеры и так публикуют.

**Читает их раз за проход, а не раз на запись.** `source` спрашивают о каждой работающей записи на каждом проходе (`resubscribe`, шаг 7) и о каждой строке в каждом heartbeat'е (`status_extra`, шаг 6). Пока каждый вопрос заново перечитывал все heartbeat'ы держателей (`holder_of`), регистратор тысячи камер при держателях по пятьдесят читал хранилище 22 001 раз за проход и 24 000 раз за heartbeat (масштабный проход, измерено счётчиком на `get` и `list`). Двадцать heartbeat'ов на каждую из тысячи записей — квадрат числа камер. Теперь проход один раз смотрит в хранилище (`Look`, декоратор `one_look` на `reconcile_once`, `status`, `resubscribe`, `backfill`, `requests`, `gate_pass`, `keep_pass`). Heartbeat'ы держателей читаются при первом вопросе и раскладываются по камере (`Look.units`), а `holder` берёт ответ из этого словаря. Тот же проход — 1022 чтения (это сами строки записей), heartbeat — 24. Тест: `test_recorder_reads.py::test_a_recorders_pass_reads_each_recording_once_not_once_per_recording`.

Докстрока модуля это подчёркивает: *found the way a gateway finds it — never by calling a worker, never a second connection to the camera.* Шлюз в уроке 13 будет искать так же. **Один способ на всех подписчиков.**

Условия на статус переданы `holder`:

- `phase="running"` — **конвейер действительно работает**, а не «размещён» или «ждёт». Подписываться на камеру, которую держат номинально, бессмысленно;
- `field="live_url"` — воркер опубликовал адрес.

**Выбор источника — три строки.** Сервер воркера совпал с моим и есть адрес разделяемой памяти — берём его. Иначе — RTSP.

Вот здесь дом и превращается из строки YAML в экономию: регистратор стоит на названном томе, камера пришла к нему, `server == self.server` истинно, и запись идёт мимо сети. Обратите внимание на порядок: сошлись они не потому, что регистратор кого-то искал, а потому, что камера — та из двоих, кто может приехать.

**Адрес, который правдив, но не для нас.** Раздача, привязанная к петлевому интерфейсу на **другом** сервере, объявлена честно, но идти по ней значило бы стучаться на свою же машину. `local_only` это узнаёт, и статус говорит «откройте `RTSP_HOST` на srv-b», а не «камеру никто не держит».

`return None` — **никто не держит камеру**. Не ошибка: камеру могли только что создать, её воркер мог упасть, контроллер мог не успеть разместить. Обычное преходящее состояние.

**Хранилище, которое молчит, — не «никто не держит».** Heartbeat'ы держателей — объекты, и на кластере это то же хранилище, что строки: пока оно не отвечало, `source` поднимал `OSError`, проход регистратора кончался на первой строке, и запись, упавшая во время сбоя, не поднималась всё время сбоя (второе ревью, блокер 4). Теперь `OSError` считается (`store_errors`), а ответом служит источник, прочитанный **последним** (`last_source`): воркер камеры никуда не делся, делась книга. Камера, которую не читали ни разу, остаётся нестартуемой — врать ей нечем. Тест: `test_holders_through_a_silent_store.py::test_a_recorder_whose_store_is_away_restarts_a_fallen_pipeline_on_the_source_it_read_last`.

**Держатель, которого не слышно, — не держатель, которого нет** (двенадцатое ревью, major 10). В кластере heartbeat держателя — объект на его сервере, и читают его через дверь ресурса того сервера. Дверь ушла (порт закрыт, ресурс перезапускается) — heartbeat старше 45 секунд, `holder` никого не находит, а воркер камеру держит и раздача работает. Поэтому `_held_by_the_book` спрашивает хранилище: размещение называет того же воркера, его слот держится и не истёк — источник, прочитанный последним, остаётся, и это сказано в логе один раз. Молчание проход тоже помнит: каждый вопрос получает ту же ошибку и считается, как раньше, а хранилище за проход спрашивают один раз, а не по разу на каждую из сотни записей (`test_recorder_reads.py::test_a_store_that_does_not_answer_is_asked_once_a_pass_and_every_recording_keeps_its_last_source`).

Обратите внимание, чего нет: **кэша** дольше прохода. Взгляд прохода — не кэш: следующий проход перечитывает объекты заново, а проход, который затянулся, перечитывает их через `Look.FRESH` (10 секунд, период heartbeat'а). `last_source` отвечает только когда объекты не отвечают. Так переезд обнаруживается без всякого механизма уведомлений — на следующем проходе (`test_a_pass_reads_the_rows_and_heartbeats_once_and_the_next_pass_reads_them_again`).

## Шаг 6 — Отказ стартовать как состояние

```python
    def enrich(self, cam: dict) -> dict | None:
        src = self.source(cam["cam"])
        if src is None:
            self.waiting.add(cam["id"])
            return None
        if self.store is None or self.store.writer is None:
            self.waiting.add(cam["id"])
            return None                                  # no volume open to write into: the reconciler retries
        self.waiting.discard(cam["id"])
        self.sources[cam["id"]] = src[1]
        # The sink: this volume's writer, as the stream `<recording>/e<epoch>`. The epoch is in the stream's
        # NAME — a fenced writer and its successor write two streams, and nothing is overwritten.
        out = dict(cam, source=src[1], source_server=src[0], via="shm" if src[1].startswith("shm://") else "rtsp",
                   sink=RecSink(lambda: self.store, cam["id"], cam.get("epoch", 0), on_lost=self._lost_engine,
                                on_wrong=self._volume_refuses, tally=self._tally))
        …
        return out
```

Вот для чего `enrich` в уроке 3 умел возвращать `None`.

**Стартовать нельзя по двум причинам.** Камеру никто не держит — подписываться не на что. Или тома, открытого на запись, нет — писать некуда: демон недоступен, том ещё не открылся. Ворота `_actuate` получают `None`, возвращают `False`, цикл сверки засчитывает неудачу и уходит в откат. Через две секунды, четыре, восемь — пока причина не уйдёт.

Никакого специального механизма ожидания. Уже написанный откат делает ровно то, что нужно.

**Сток конвейера — объект, а не путь.** `enrich` отдаёт актуатору не каталог, куда элемент GStreamer писал бы файлы сам, а `RecSink` — писателя тома под именем и эпохой этой записи. Том сток получает функцией, `lambda: self.store`, а не значением: после перемонтирования (шаг 8) он пишет в новый том, а не в закрытый. Что с ним делает актуатор, — урок 9; что делает сам сток, — шаг 8.

Одна вещь добавлена ради экрана — **множество `waiting`**:

```python
    @one_look
    def status(self) -> list[dict]:
        out = super().status()
        for st in out:
            if st["phase"] != "running" and st["id"] in self.waiting and st["enabled"]:
                st["phase"] = "waiting"
        …
        return out
```

А `status_extra` пишет рядом причину: `why: "camera held by nobody"`. Без этого запись, ждущая камеру, показывалась бы как `failed`, и оператор искал бы неисправность там, где её нет (`test_a_recording_waits_while_nobody_holds_the_camera_and_records_when_someone_does`).

`via` — `shm` или `rtsp`, прямо в статусе. На странице VMS (урок 12) это строка `· via shm`, по которой видно, сошлась ли пара на одном сервере. Без неё выигрыш был бы невидим, а невидимую экономию невозможно ни проверить, ни защитить.

## Шаг 7 — Переподписка

```python
    @one_look
    def resubscribe(self, now: float | None = None) -> list[int]:
        now = self.now() if now is None else now
        moved = []
        cams = {str(r["id"]): str(r.get("cam") or r["id"]) for r in self.rows}
        for cid in list(self.reconciler.actual):
            src = self.source(cams.get(str(cid), cid))
            if src is not None and self.sources.get(cid) not in (None, src[1]):
                self._release_if_broken(cid)                      # the ring is the only copy of the break (CB): written before the stop
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, now)
                self.sources.pop(cid, None)
                moved.append(cid)
                log.info("%s: camera %s is held elsewhere now (%s): re-subscribing", self.name, cid, src[1])
        return moved

    @one_look
    def reconcile_once(self, now: float | None = None) -> list[tuple[str, int]]:
        self.resubscribe(now)
        out = super().reconcile_once(now)
        for part in (self.gate_pass, self.writer_pass):
            try:
                part()
            except OSError as e:
                self.store_errors += 1
                log.warning("%s: %s skipped: the store did not answer (%s)", self.name, part.__name__, e)
        return out
```

**Чей источник.** `reconciler.actual` держит id **записей**, а держателя ищут по **камере** — `cam` из строки записи. Первая версия передавала в `source` id записи: для записи `1`, названной по камере, это одно и то же, и тест проходил; запись `7-cloud` не переподписывалась никогда (найдено при разборе второго ревью). Перед остановкой — `_release_if_broken`: кольцо резервной записи — единственная копия обрыва (урок 26), и остановка в обход сверки не должна его терять.

**Четыре части, и хранилище не роняет остальные.** `gate_pass` читает строки, `writer_pass` — том; то, что часть не смогла прочитать, она называет в логе и считает, а не уносит проход с собой.

**Один взгляд на четыре части.** `@one_look` — проход смотрит в хранилище один раз (шаг 5): `resubscribe`, `enrich` при каждом старте и `gate_pass` внутри `reconcile_once` берут взгляд внешнего прохода, а не открывают свой. Новые heartbeat'ы и строки проход увидит на следующем проходе.

Держатель камеры переехал. Старый адрес больше не отвечает, а новый регистратору никто не сообщил.

**Обнаружение — сравнение строк.** Для каждого работающего конвейера: какой адрес он слушает (`self.sources`) и какой адрес сейчас в heartbeat'ах (`self.source(cid)`). Разошлись — переезд.

`src is not None` — важная оговорка: **временное отсутствие держателя не считается переездом**. Воркер перезапускается, его heartbeat на секунду стареет, `source` возвращает `None` — и конвейер не трогается. Он ещё может ожить на том же адресе. Переподписка только тогда, когда есть **новый** адрес.

Реакция: остановить, `lost` (то есть забыть и оштрафовать откатом), забыть адрес. Дальше цикл сверки поднимет заново — уже через `enrich`, который возьмёт новый адрес.

И тонкость, названная в комментарии: *under a new rec epoch (a start is a new writer)*. Перезапуск идёт через `start`, а не `restart` (конвейер выпал из `actual`), значит ворота берут **новую эпоху записи** (урок 3). Видео после переезда ляжет в поток `7/e2`, а записанное раньше останется в `7/e1` того же тома.

Правильно ли это? Да, и по причине из урока 7: **эпоха — часть имени потока, единственное, что у потока есть кроме кадров**. Это буквально другой конвейер, читающий другой источник. Зомби, дописавший секунду под старой эпохой, пишет свой поток, а не поверх преемника; индекс говорит, какой эпохе принадлежат какие минуты (`authoritative`, урок 8). Это и проверяет `test_a_recording_started_twice_writes_two_streams_and_overwrites_nothing`: в томе остаются оба потока, `1/e1` и `1/e2`, и таймлайн помечает первый отсечённым.

Записанное до переезда остаётся в томе, куда было записано, под старой эпохой. Если переехал сам регистратор — тома разные; дверь страницы у регистратора записи спросит двери обоих регистраторов и склеит шкалу (`vms/footage.py`, урок 12). А кусок записи из тома, который держит теперь другой регистратор, страница берёт у **его** двери: адрес и токен даёт `GET /rec/where/volumes/<том>?unit=rec/<запись>` — платформенный `/where/<table>/<place>` по `places` спеки ([М10A, урок 15, шаг 6](../М10A_Platform/15-SpecConsole.md)). Тома не держит никто — 404 и `X-Unreachable: <том>@<сервер>`: страница называет, чего не хватает на шкале.

`resubscribe` вызывается **перед** сверкой: сначала убрать устаревшее, потом поднимать. В обратном порядке проход поднял бы то, что через секунду сам же остановит.

## Шаг 8 — Открыть том, держать писателя, перемонтировать

Вот второе отличие от воркера. Ни спула, ни переноса закрытых сегментов: кадр уходит в писатель тома, как только пришёл. Работа регистратора — три глагола: открыть том, держать его писателя, открыть заново, когда демон пропал.

### Открыть

```python
    def _write_into(self, vol) -> ArchiveError | None:
        # A camera's card is the camera's buffer, written by its own recorder as plain segment files (`vms/card.py`;
        # the product's camera has no engine) — never mounted by the engine, here or anywhere.
        if vol.kind == "edge":
            return ArchiveError("wrong", f"{vol.name} is a camera's card: its camera's recorder writes it, the engine "
                                         f"never does (vms/card.py)", "NOT_AN_ENGINE_VOLUME")
        …
        self._vol_last = vol
        if self.store is not None and self.store.url == vol.url and self.store.writer is not None and not self.engine_lost:
            self._apply_quota(vol)
            return None
        if self.store is not None:
            …
            if self._close_store(quiet=True, wait=self.session.timeout):
                return self._away(vol, ArchiveError("away", "the writer's close did not come back: mounted again on "
                                                            "the next pass", "UNAVAILABLE"))
        refuses = self._engine_refuses(vol)              # a volume any box may serve, and an engine that cannot give it up
        if refuses is not None:
            return refuses if refuses.kind == "wrong" else self._away(vol, refuses)
        secret = …
        store = Archive(vol.url, vol.name, vol.quota_bytes or self.default_quota, f"rec:{vol.name}", self.session, self.wall,
                        secret=secret, access_key=vol.access_key,
                        …
                        sequence_flush_ms=self.sequence_flush_ms, block_flush_s=self.block_flush_s,
                        confirm=lambda: self._confirm_hold(vol), share=self._share_of_space,
                        fence=lambda: self._may_write_volume(vol),
                        on_unclean=lambda result, detail: self._unclean(vol, result, detail),
                        may_format=lambda: self._may_format(vol),
                        …)
        store.row = vol                                  # what `_close_store` asks whether its writer may be closed by
        try:
            store.open()
        except ArchiveError as e:
            if store.orphan and store.session is self.session:
                self._leave_session(f"the mount of {vol.name} was not answered: the writer the daemon made is an orphan")
            elif self._own_lock(store, e):
                self._leave_session(…)
            …                                            # by its KIND (шаг 9)
        self._own_lock_since, self._own_lock_left, self._engine_silent_since = 0.0, False, None
        …
        self.store, self.engine_lost = store, False
        try:
            self._landed_before, self._landed = self._landed_before + self._landed, 0
            self._written_at_open = int(store.status().get("totalWritten", 0))
        except ArchiveError:
            self._written_at_open = 0
        …
        return None
```

Комментарий над методом называет главное: *Opening is the only honest test.* Строка может назвать путь, которого нет, монтирование, которого больше нет, или бакет, до которого не дотянуться, и ничего из этого в строке не видно.

Первая ветка — **тот же том уже открыт**. Тогда открывать нечего, и единственное, что может измениться, — квота (`_apply_quota`). Новая квота — новый размер кольца, сразу и без остановки (`Archive.resize`): увеличение — сразу, уменьшение — только со вторым словом оператора (`shrink_confirmed`, раздел «Квота»). Это и делает квоту рычагом, который оператор двигает на работающей коробке.

Иначе — открыть через демон: `Archive.open` из `vms/archive.py` (урок 7, шаг 7).

**Тома нет — он форматируется, на квоту.** Объявили том в консоли — первый же регистратор, который его взял, его и создал. Без квоты форматировать не на что, и это `wrong`: исправит только человек. Но том, который уже был по этому адресу и пропал, заново не форматируется: `may_format` — `RecWorker._may_format` — читает отметку `rec/used/<том>` (её пишет `_mark_used` при первом открытии) и отвечает `wrong` с `VOLUME_MISSING`: диск не примонтирован после перезагрузки — это не повод форматировать пустой том на корневом диске и прятать недели записи. Записи тома уходят на другой, тревога `volume.missing` — один раз за эпизод; примонтировали диск обратно — том открывается каким был.

**Писатель монтируется под владельцем `rec:<том>`.** Не `rec:r-1`, не токен процесса — имя тома. Почему так — ниже, в «Держать».

`_written_at_open` — сколько кольцо уже записало к моменту открытия (`totalWritten`). От этой отметки сторож писателя считает «дошедшее» (шаг 12). А дошедшее под прежними писателями этого регистратора копится в `_landed_before`: счёт идёт дальше через переоткрытие, а не начинается с нуля.

### Какой том открыть, когда ничего не объявлено

Свой том сервера, с именем сервера: `ARCHIVE_VOLUME`, а без него — `config.OWN_VOLUME`, `/data/vms/obsd/volume`: дерево событий — `/data/platform/events`, каталог платформы, а тома движка — у VMS (урок 17, шаг 8). Точка входа на коробке задаёт `ARCHIVE_VOLUME` той же строкой; тест, назвавший регистратору своё дерево, получает `volume` рядом с этим деревом. Не внутри дерева: внутри дерева ресурса обходы ресурса приняли бы кольцо за подсистему и посчитали бы его блоки занятым местом дерева. Квота — `ARCHIVE_QUOTA_BYTES`, а если её нет — доля свободного места:

```python
    # A volume nobody declared, on a disk nobody measured: four fifths of what is free, leaving two gigabytes —
    # the product's rule (feedback BM) — and never so much that the disk ends above the watermark's low mark
    # (`space_settings`, 0.75 by default) once the ring is full. …
    @staticmethod
    def _share_of_space(space: dict, low: float = 0.75) -> int:
        free, total = int(space.get("available") or 0), int(space.get("capacity") or 0)
        if not total:
            return 0
        used = total - int(space.get("free") or free)
        return max(1 << 30, min(int(free * 0.8), free - (2 << 30), int(total * low) - used))
```

**Диск — тот, куда пишет демон.** Доля считалась от диска, который видит **контейнер** регистратора, а кольцо лежит там, куда пишет демон хоста: на коробке с системным SSD и HDD под данные том форматировался на долю SSD — пара часов архива вместо дней, и дальше этот размер считался настоящим (четвёртое ревью). Теперь перед `FORMAT` регистратор спрашивает у демона `VOLUME_SPACE` каталога тома (или ближайшего существующего над ним) и считает долю от ответа. И heartbeat держателя говорит о томе правду: `volume_quota` — настоящий размер от демона; `shrink_pending` — объявленный меньший размер, пока он не применён (без `shrink_confirmed` он не применится); `resize_error` — почему движок отказал в новом размере (повтор каждый проход); применённое уменьшение — событие `archive.volume.shrunk`. Консоль показывает это на странице томов (урок 27). Тест: `test_a_new_volume_without_a_quota_is_sized_by_the_disk_the_daemon_writes_to`.

Третье слагаемое появилось после того, как его нашли на расчёте. Диск общий с событиями ресурса, а ватерлиния ресурса включена по умолчанию. Кольцо, заполнившее диск выше её отметки, оставило бы недостачу навсегда: у VMS больше нечем ответить на «освободи». Поэтому кольцо по умолчанию кончается раньше нижней отметки.

Обратите внимание на «asked once». Том, который уже есть, своего размера не меняет: отформатированное кольцо открывается каким было. Регистратор на коробке, где ничего не объявляли, форматирует свой том при первом проходе и пишет в него (`test_a_recorder_with_nothing_declared_formats_its_servers_volume_and_records_into_it`).

### Какой это том: место записи или место для удержанного

```python
    # An INCIDENTS volume is a place for kept footage and never one to record into: the recorder holding it says
    # so with its capacity — nought, like a spare — and copies keeps instead (`keep_pass`).
    def _place_kind(self, vol) -> None:
        self.incidents = vol.kind == "incidents"
        if self.incidents:
            self.capacity = 0
```

Том вида `incidents` держат так же, как любой другой: захватом и писателем. Но записей на него не ставят, и сказать это контроллеру проще всего ёмкостью — нулём, как у запасного. Что такой регистратор делает вместо записи — копирует удержанное, — [урок 18](18-what-the-archive-gives-up-first.md).

### Держать

**Писатель идёт за захватом.** Взял другой том — пишешь в другой. Иначе запасной, взявший сетевой архив, продолжал бы заполнять локальный диск, и объявление было бы табличкой ни на чём. Снятый посреди работы том сохраняет записанное: писатель закрывается — его сброс кладёт последние минуты в том — и только потом открывается следующий (`test_the_recorder_writes_into_the_volume_it_took`).

**Писатель переживает процесс.** Писатель тома живёт в демоне, а не в регистраторе. Регистратор, убитый `kill -9`, уходит без `BYE`, и демон делает с его писателем три вещи (README демона): дописывает открытые последовательности, оставляет писателя смонтированным — *detached* — с владельцем, под которым тот был смонтирован, и ждёт `OBSD_WRITER_GRACE_S`. Кто смонтирует том под тем же владельцем, получит этого писателя обратно (`reattached: true`): ни блокировки, ни восстановления.

Отсюда владелец `rec:<том>`. Следующим том возьмёт либо тот же регистратор, поднятый systemd под тем же именем, либо другой, когда истечёт захват. Оба назовут одного владельца, и оба подберут писателя целиком. Захват платформы и так делает имя тома уникальным, поэтому имя тома — правильная личность для писателя. Комментарий в коде: *no lock waited out, nothing recovered (feedback CF)*.

Ожидание демона обязано быть **длиннее**, чем захват возвращается хозяину. Захват умершего процесса истекает за 45 секунд, на коробке демону дано 90 (урок 17). У продукта при двадцати секундах ожидания писатель своего хозяина не дождался.

**Подхват — на одном хосте.** «Другой, когда истечёт захват» подберёт писателя, только если он на том же хосте: писатель живёт в демоне этого хоста. Сетевой том после умершего регистратора может взять коробка с **другим** демоном, и тогда отсрочка на первом хосте кончается закрытием писателя — со сбросом, который пришёлся бы на чужой том (урок 6, шаг 12). Этого не даёт сделать сам движок (патч 07): писатель, чей замок стал чужим, не пишет ничего, и чужой lock-файл остаётся на месте. Поэтому на демоне без этого патча регистратор сетевой том не берёт (шаг 3).

Два теста показывают это на настоящем демоне: `test_a_recorder_killed_and_started_again_picks_up_the_writer_it_left` (свой том сервера) и `test_a_restart_takes_its_volumes_writer_back_and_never_opens_the_local_one` (объявленный том). Во втором есть и вторая половина: перезапущенный процесс сначала смотрит на объявленные тома и только потом открывает что-либо, поэтому свой том сервера он не форматирует вовсе.

### Во что пишет конвейер

```python
class RecSink:
    def __init__(self, store, unit, epoch: int, on_lost=None, backfill: bool = False, on_wrong=None, tally=None):
        self.store_of = store if callable(store) else (lambda: store)
        …
    def put(self, sample: Sample) -> str:
        try:
            store = self.store_of()
            if store is None:
                raise Unavailable("PUT_MEDIA", "no volume open")
            st = store.put(self.unit, self.epoch, sample, self.backfill)
            self.taken += 1
            self.tally(self.unit, st)
            return st
        except Fenced as e:
            …
            self.refused += 1
            self.tally(self.unit, e.name)
            raise
        except Unavailable:
            self.tally(self.unit, "UNAVAILABLE")
            if self.on_lost is not None:
                self.on_lost()
            raise
        except ObsdError as e:
            self.refused += 1
            self.tally(self.unit, e.name)
            if e.name == "WRITER_STOPPED" and getattr(store, "lock_lost", False):
                pass                                 # the volume's lock is another writer's: the place lost, not the engine
            elif e.name == "WRITER_STOPPED" and self.on_lost is not None:
                self.on_lost()                       # the engine stopped this writer: a new one, on the next pass
            elif self.on_wrong is not None and classify(e).kind == "wrong":
                self.on_wrong(e)
            raise
```

Комментарий над классом: *A sample the engine did not take raises, and the pipeline skips to the next key frame.* Движок открывает последовательность только на ключевом кадре (урок 7), поэтому остаток группы кадров после отказа бесполезен.

И второй абзац того же комментария:

> *`store` is the recorder's CURRENT volume — a callable, asked on every sample — not the one open when the pipeline started. A remount replaces the `Archive`; a sink that kept the old one would write into a closed volume for as long as the pipeline ran, and nothing restarts a pipeline for a remount.*

Отказ отказу рознь, и сток различает три случая (и ещё два, где движок не потерян: `Fenced` — холд не подтверждён, кадр не отправлен, — и `WRITER_STOPPED` при `lock_lost`; оба — урок 7, шаг 10). Демон перестал отвечать (`Unavailable`, в том числе «том закрыт» из `Archive.put`) — это ответ не про кадр, а про движок: сток говорит регистратору `on_lost`. Движок остановил самого писателя (`WRITER_STOPPED`) — тоже `on_lost`: этот писатель больше ничего не возьмёт, нужен новый. Том отказал по-настоящему (`wrong`) — сток говорит `on_wrong`. Сам сток ничего не чинит: он работает на потоке конвейера, а решает регистратор, на своём проходе.

### Перемонтировать

```python
    # A sink found the daemon gone — or a handle of the store answered that the daemon no longer knows this session
    # (`SessionLost`: …). Nothing is torn down here, on the pipeline's thread: the next pass closes what is left of the
    # store and opens it again (`volume_pass`) — at once, not after the writer watch's ten minutes, because there is
    # nothing to wait for: the engine is not there, a new session is (feedback CF). And it is SAID: until the remount,
    # `archive_error`; after it, `archive_remounted`.
    def _lost_engine(self) -> None:
        if self.store is not None and not self.store.lost and not self._may_write_volume(getattr(self.store, "row", None)):
            return                                   # fenced, not lost (`Fenced`): the hold is the pass's to answer
        …
        self.engine_lost = True
```

Флаг и слова для heartbeat'а, и больше ничего (полностью — урок 7, шаг 13). Следующий `_write_into` видит `engine_lost`, закрывает то, что осталось от старого тома, и открывает том заново, новой сессией. Сразу, а не через десять минут, которые выдерживает сторож писателя (шаг 12): у сторожа причина может быть в том, чем кормят писателя, а здесь ждать нечего — движка просто нет.

Конвейеры перемонтирование не трогает. Их стоки спрашивают текущий том на каждом кадре, и первый ключевой кадр после перемонтирования открывает последовательность в новом писателе. `test_rec_volume.py::test_a_recording_goes_on_into_the_volume_opened_again_after_the_engine_was_lost` пишет минуту, перемонтирует том (`_lost_engine` и проход) и пишет вторую тем же конвейером: у старого `Archive` писателя больше нет, а покрытие — обе минуты, `[(t - 120, t)]`. Вторая половина теста отвечает стоку `WRITER_STOPPED` и проверяет, что `engine_lost` поднят.

На ящике продукта это выглядело так: `kill -9` демона, все восемь регистраторов заметили его за 5–10 секунд и перемонтировали тома за 16–20.

## Шаг 9 — Нет, неверно, занято

Том, который не открывается или не берёт кадры, бывает в трёх состояниях, и отвечать на них надо по-разному. Слова для них даёт `vms/archive.py`:

```python
class ArchiveError(Exception):
    """A volume that will not open or take writes, by KIND — the recorder answers each differently:

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
    let go — lasts `RecWorker.BUSY_FOR` and no longer (the seventh pass): let go, with an alarm."""


WRONG = {"PERMISSION_DENIED", "NOT_A_VOLUME", "UNSUPPORTED_FORMAT", "READ_ONLY", "PATH_NOT_EMPTY",
         "INVALID_ARGUMENT", "PROTECTED_VOLUME", "INVALID_CIPHER_KEY"}
```

Решает статус движка. `wrong` — короткий список того, что исправит только человек. `busy` — ровно один статус, `ALREADY_LOCKED`. Всё остальное, в том числе всё, чего никто не перечислил, — `away`.

Почему неизвестное — недоступность, а не постоянный отказ: цена ошибки несимметрична. Недоступный том, который отдали, перекладывает все записи на нём ради связи, вернувшейся через минуту. Неверный том, который оставили, — это регистратор, который пишет в никуда и говорит об этом в heartbeat'е, и это видно.

Ответы:

- **`wrong`** — том отдаётся (если есть куда идти — шаг 3), его записи уходят туда, где всё работает;
- **`away`** — том остаётся за регистратором, с полной ёмкостью; heartbeat говорит `archive_error` и с какого момента (`archive_away_since`); следующий проход пробует снова (`test_an_archive_that_is_away_at_open_is_kept`);
- **`busy`** — то же, что `away`: писателя держит предыдущий регистратор этого тома, и он вот-вот его отпустит. Но heartbeat называет его своим словом, `archive_failure: busy`, а не `away`: «демона нет» и «том держит другой писатель» лечатся по-разному, и оператор должен видеть, какой из двух случаев перед ним.

**`away` и `busy` у диска этого сервера — без срока, и это решение.** Пятое ревью спросило: если `obsd` одного хоста сломан надолго, регистратор держит сетевой том в `away`/`busy` сколько угодно, и том не уходит на другой хост — так задумано? Для диска — да, и это записано в докстроке `ArchiveError` (выше). У сетевого тома срок появился у обоих: молчащий демон — `ENGINE_SILENT_FOR` (шестое ревью), `busy` под своим холдом — `BUSY_FOR` (седьмое ревью; шаг 3). Холд регистратор продлевает, пока хранилище ему отвечает, и сам его не отдаёт из-за молчащего демона. Причина та же, что у таблицы выше: демон, перезапущенный за минуту, — обычное дело, а отдать том значит перетасовать все записи на нём. Цена тоже названа: пока демон этого хоста не вернулся, записи тома не пишутся нигде, хотя другой хост мог бы их взять. Heartbeat это говорит — `archive_failure: away` и `archive_away_since`, — а решает человек: остановить регистратор или снять его с тома. Подменщик, правда, такой холд за висящий шаг не продлевает (шаг 10).

### Диск на коробке, который не открывается, — неверен

Одна поправка к таблице пришла с живого демона. Движок называет некоторые поломки локального диска теми же словами, что и упавшую сеть. `VOLUME_EXISTS` отвечает «да» для пути внутри обычного файла, и тогда монтирование падает с `GENERIC_ERROR`. Путь, который нельзя создать, проваливает форматирование с `IO_ERROR`. Оба статуса — `away` по таблице выше, и том по адресу с такими словами действительно стоит подождать.

Диск на этой коробке — нет. Файл на месте каталога сам не исчезнет. Поэтому решает вид тома:

```python
            # A DISK on this box that cannot be formatted or mounted — a file where the directory should be, a
            # path nobody may create — is not a link that comes back in a minute. The engine says it as an I/O or
            # a generic error, the same words a network volume uses for a network that is down, so the kind of
            # volume decides: on a box, wrong; at an address, away.
            if e.kind == "away" and e.name in ("IO_ERROR", "GENERIC_ERROR") and volumes.on_a_box(vol):
                e = ArchiveError("wrong", e.detail, e.name)
            if e.kind == "wrong":
                return e
            return self._away(vol, e)
```

```python
    # `away` or `busy` at open: the volume is kept, and said as what it is. A daemon that did not answer at all, under a
    # volume any box may serve, is the engine silent since now (`_engine_pass`).
    def _away(self, vol, e: ArchiveError) -> None:
        if not self.archive_error:
            self.archive_away_since = self.wall()
            log.warning("%s: %s is %s at open (%s) — keeping it and trying again", self.name, vol.name, e.kind, e.detail)
        self.archive_error, self.archive_failure = e.detail, e.kind
        if self._taken_over:                         # what happened before the wait is still the news (`volume_pass`)
            self.archive_error = f"{self._taken_over}. Now: {e.detail}"
        # `BUSY_FOR` counts UNBROKEN busy (the review's eighth pass, part 2): the mark was set by a `busy` and cleared only
        # by a mount or by leaving, so one `busy` pass — a predecessor's writer still closing — followed by ten minutes of
        # a network that is down (`away`, waited for without a deadline) let a volume that was merely unreachable go with
        # an alarm sending the operator to look for somebody else's recorder, and a pinned recorder wrote nothing for ten
        # minutes after the store came back. Any refusal that is not `busy` ends the count.
        self._busy_since = (self._busy_since or self.clock()) if e.kind == "busy" else 0.0
        if e.name == "UNAVAILABLE" and volumes.any_box(vol) and self._engine_silent_since is None:
            self._engine_silent_since = self.clock()
        return None
```

Предпоследняя строка — счёт непрерывного `busy` (`BUSY_FOR`, шаг 3): любой другой отказ его обнуляет (восьмое ревью). Последние две — счёт молчания движка под сетевым томом (шаг 3): `away` без ответа демона ставит отметку, с которой идёт `ENGINE_SILENT_FOR`.

Без этой поправки `test_a_volume_held_and_unwritable_is_not_served` и шёл бы по худшему пути: регистратор держал бы сломанный диск как «недоступный», с полной ёмкостью, и зелёные числа вернулись бы.

### Отказ посреди работы

Том открылся, а потом начал отказывать: ключ отозвали, том сделали только для чтения. Узнаёт об этом сток, на потоке конвейера, кадр за кадром. Действует регистратор, раз за проход:

```python
    def _volume_refuses(self, e) -> None:
        if self.archive_failure != "wrong":
            log.error("%s: %s refuses writes: %s", self.name, self.volume, e)
            self.archive_error, self.archive_failure = str(e), "wrong"
            self.archive_away_since = self.archive_away_since or self.wall()
```

```python
        now = self.wall()
        if self.hold is not None and self.archive_failure == "wrong":
            why = self.archive_error
            self.refused[self.hold] = (now + self.REFUSED_FOR, why)
            logging.error("%s: %s refuses writes (%s) — handing it back", self.name, self.hold, why)
            self.leave_volume(f"volume {self.hold} refuses writes")
        answers = self._engine_pass(rows, free, now)   # the volumes any box may serve, and the engine they need
        self.refused = {n: v for n, v in self.refused.items() if v[0] > now}
        free = [n for n in free if n not in self.refused and n not in self.unservable]
```

Том отдаётся, и записи на нём свободны уйти туда, где всё работает. Но сразу обратно регистратор его **не берёт**. Открытие вполне может пройти — каталоги на месте, — а первая запись снова упасть, и регистратор метался бы между захватом и сдачей одного и того же сломанного тома. Том оставляется в покое на `REFUSED_FOR` — 600 секунд. Достаточно долго, чтобы не метаться, и достаточно коротко, чтобы исправленный ключ подхватился без перезапуска. Heartbeat перечисляет такие тома в `refused` с причиной (`test_an_archive_that_refuses_writes_mid_run_is_handed_back`).

## Шаг 10 — Демон, которого нет или который молчит

Демон — отдельный процесс. Его перезапускают, его убивают, он может принять запрос и ничего не ответить. Ничто из этого не должно останавливать **жизнь** регистратора. Регистратор, который перестал продлевать аренды, теряет эпохи; тот, что перестал слать heartbeat, контроллер объявляет мёртвым. В обоих случаях кончаются все записи на нём — из-за единственного компонента, которого ему велели ждать.

**Демона нет.** Вызов падает сразу: сокет не отвечает, `Session` бросает `Unavailable`, `classify` называет это `away`. Регистратор держит том, говорит в heartbeat'е `archive_error: obsd is not answering…` и `archive_failure: away`, а следующий проход пробует снова (`test_a_recorder_with_no_daemon_says_the_archive_is_away_and_keeps_its_place`). Минута работы цикла без демона — несколько продлений и несколько heartbeat'ов, место за регистратором (`test_a_daemon_that_is_not_there_does_not_stop_the_recorder`). Демон вернулся — том открывается, и `archive_error` гаснет, потому что том действительно открылся (`test_when_the_daemon_answers_again_the_volume_opens_and_the_outage_is_over`).

**Демон молчит.** Хуже, потому что ловить нечего: нет исключения, есть вызов, который не вернулся. Демон, застрявший на мёртвом сетевом томе, принимает запрос и молчит. А вызовы прохода идут на том же потоке, что продлевает аренды.

Поэтому у каждого вызова срок, и он короче аренды:

```python
        # Every call waits at most `OBSD_TIMEOUT` — ten seconds, a third of a lease. The calls a pass makes run on
        # the thread that renews the leases, and a daemon that took a request and went quiet would otherwise hold
        # that thread past the lease: the recorder fenced, every recording stopped, for one silent daemon. Silent
        # is `away` (`ArchiveError`): the volume is kept, the pass goes on, the next one asks again.
```

Две детали в `vms/obsd.py` делают это правдой. Молчание — `Unavailable`, и его **не переспрашивают**: оборванное соединение — повод отправить запрос ещё раз, а тишина нет, и второй вопрос удвоил бы ожидание. Да и после обрыва не всякий запрос повторяется: кадр, формат или монтирование, ушедшие до обрыва, демон мог уже выполнить, и они дают `Unavailable` (`NOT_RESENT`, урок 6) — а сток на это перемонтирует том; неотвеченное монтирование оставляет ещё и сессию (шаг 11). И один запрос протокол разрешает длинный: `WRITER_CLOSE` возвращается после сброса, до тридцати секунд (README демона). Только он ждёт `long_timeout`. Оба числа проверяет `test_the_recorders_calls_wait_less_than_a_lease_and_only_a_close_waits_for_its_flush`, а минуту работы против демона, который принимает соединения и не отвечает никогда, — `test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living`.

**И если работа повисла, а не упала.** Регистратор, повисший внутри вызова к `obsd`, — тот случай, ради которого сделан «подменщик» (М10A, урок 8): он наследует цикл воркера, и пока шаг висит, отдельный поток продлевает его аренды, слот **и холд тома** — сетевой том истекает так же быстро, как слот, — не дольше пяти минут.

**Но не за шаг, который стоит на молчащем движке.** Подменщик держал холд сетевого тома пять минут, даже когда шаг висел на демоне, который уже ответил `Unavailable`, а каждый новый долгий шаг давал ещё пять (пятое ревью). Шаг, застрявший на демоне, который ничего не отвечает, ничего и не пишет, а пять минут холда — это пять минут, когда том не может взять коробка, чей демон отвечает. Теперь платформа спрашивает `may_stand_in_hold()`, и регистратор отвечает «нет», пока движок потерян (`engine_lost`), сессия только что не дождалась ответа (`Session.silent()`) или проход нашёл движок молчащим (`_engine_silent_since`). Третье условие добавил шестой проход: первые два смотрят на эту секунду, и между двумя вызовами зависшего шага — или когда том ещё не открыт и о потере движка никто не сказал — оба ложны, а подменщик холд продлевал. Что нашёл проход, стоит, пока демон не ответит. Аренды и слот подменщик продлевает по-прежнему: жизнь регистратора от движка не зависит. И `STAND_IN_FOR` считается от последнего продления **циклом** перед первым зависшим шагом, а не от начала каждого шага и не от продления внутри шага, который потом повис (М10A, урок 8). Продление холда, которое подменщик всё-таки сделал, засчитывается проверке кадров с момента до запроса (`note_hold_confirmed`). А сам цикл продлевает холд сетевого тома через молчащий демон не дольше `ENGINE_SILENT_FOR` (шаг 3). Тесты: `test_stand_in.py::test_the_stand_in_does_not_hold_the_place_for_a_step_on_a_silent_engine_and_says_what_it_renewed`, `test_STAND_IN_FOR_counts_from_the_loops_last_renewal_and_a_new_step_does_not_start_it_again`, `test_STAND_IN_FOR_is_not_started_again_by_a_renewal_inside_the_step_that_then_hangs`, `test_rec_volume.py::test_the_stand_in_renews_no_hold_while_the_pass_has_found_the_engine_silent`.

**Поддержание жизни не разделяет судьбу с работой.** Это правило цикла `run` базы воркера (М10A, урок 8, шаг 9), и записано оно буквально: каждый шаг в своём `try`. Сверка, `pump_once`, шаг аренд (с шагом тома регистратора) и heartbeat — каждый в своём. Ошибка, которой никто не ждал, в любой работе не выключает продления (`test_no_failure_in_the_work_can_stop_the_recorder_living` — с `RuntimeError`, а не `OSError`, намеренно: гарантия для того, что никто не предвидел).

**Дозапись ждёт.** Она существует, чтобы принести в том **больше**, а том сейчас не берёт ничего:

```python
    def archive_busy(self) -> bool:
        return bool(self.archive_error) or self.store is None or self.store.writer is None
```

Скачанному диапазону негде лечь, а сама выборка стала бы ещё одним вызовом к молчащему движку (`test_backfill_waits_while_the_volume_is_taking_nothing`). И выборка идёт в своём потоке: диапазон с медленной карты камеры — это минуты, и на потоке цикла он отсекал бы регистратор ради часа одной камеры (`test_a_fetch_from_a_slow_card_does_not_hold_the_pass`; подробно — урок 16). Заявки оператора (`rec/requests/*`) регистратор читает там же, и одна битая заявка — `from` или `to`, которые не разбираются как числа, — отказ этой заявки, а не конец прохода: `RecWorker.requests` отвечает на неё ошибкой и берёт следующую (шестое ревью; `test_epoch_refused.py::test_the_recorder_refuses_one_request_whose_range_does_not_parse_and_serves_the_next`).

Чего здесь больше нет — очереди на локальном диске, которая копилась бы, пока архив недоступен. Кадры, которые демон не взял, не взяты. В томе от них остаётся дыра, и её закрывает дозапись (урок 16) с карты устройства, если у устройства есть свой архив.

## Шаг 11 — Уйти с тома: сначала писатель, потом захват

С тома уходят по двум причинам: его забрали (сняли в консоли, захват истёк, том отказал) или процесс останавливается. Порядок в обоих случаях один.

```python
    def leave_volume(self, why: str) -> None:
        logging.warning("%s: %s — stopping its recordings", self.name, why)
        for uid in list(self.reconciler.actual):
            self._release_if_broken(uid)
            self.actuator("stop", {"id": uid})
            self.reconciler.actual.pop(uid, None)
            self.release(str(uid))
        …
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
        …
```

**Порядок — и есть урок.** Отпущенное место берут сразу, и взявший монтирует том на запись. Поэтому захват уходит **последним**: конвейеры остановлены, писатель закрыт — его сброс кладёт последние минуты в том и делает их читаемыми, — и только потом захват отпущен. Отпусти его раньше — и следующий держатель найдёт в томе нашего писателя: получит `ALREADY_LOCKED`, а последние минуты окажутся в блоке, который ещё никто не закрыл. `test_leaving_a_volume_closes_its_writer_before_the_hold_goes` проверяет обе половины: следующий монтирует том начисто (`reattached` ложно), и записанное нами в нём видно.

### Сетевой том, чей холд уже потерян: писателя не закрывают, а бросают

**Закрыть писателя — это ещё одна запись в том.** «Сначала писатель, потом захват» верно, пока том наш. Закрытие — последняя запись писателя: сброс очереди и `volume.status`. На сетевом томе, который за это время взяла другая коробка, это запись в её том. Коробка, замороженная целиком, просыпалась, её проход видел, что холд чужой, закрывал писателя — и каждое следующее монтирование законного держателя было `VOLUME_UNCLEAN`, а `VOLUME_RECOVER` не звал никто: 10 проходов подряд `away`/`busy`, том потерян (пятое ревью, блокер 1; воспроизведено на двух демонах, а с SIGKILL вместо заморозки том монтировался снова — портит именно проснувшийся писатель).

Теперь `_close_store` сначала спрашивает `_may_close_volume` — обёртку над платформенным `Worker.may_close_place`: можно ли закрыть, пока холд ещё наш и никто другой не мог его взять. Окно шире окна записи: холд подтверждён моложе `slot_ttl + HOLD_SKEW` — столько претендент ждёт неизменной строки. А замок движка, который продлевает незамёрзший демон, держит претендента, пока закрытие его не отпустило. Внутри окна писатель закрывается со сбросом, как раньше: последние минуты на томе. За окном — или когда движок сам сказал, что замок чужой (`lock_lost`), — писатель **не закрывается, а бросается**:

```python
        if st.writer is not None and (st.lock_lost or not self._may_close_volume(getattr(st, "row", None))):
            self.store = None
            answered = st.abandon(wait)
            log.error("%s: volume %s may be another server's by now (%s): this recorder stops writing it and gives its "
                      "writer up without writing anything more%s", self.name, st.name,
                      "the engine found its lock taken" if st.lock_lost else "its hold was not confirmed in time",
                      "" if answered else " — obsd did not answer, so the writer is left for obsd to close")
            self._say_dropped(st, answered)
            if not answered and st.session is self.session:
                self._leave_session(f"the writer of {st.name} could not be given up (the daemon did not answer)")
                return True
            return False
```

**Бросить — `WRITER_ABANDON`.** `Archive.abandon` шлёт операцию 36 (урок 6, шаг 6): писатель отпущен, не записав ничего — ни очереди, ни статуса, — а lock-файл удаляется, только если он ещё его. Чужой том цел.

**Безопасным это делает движок, и курс его требует.** ObjectStorage с патчем 07 перед каждым блоком, статусом и удалением проверяет замок тома по пути, останавливает писателя, чей замок стал чужим, и чужой lock-файл не снимает — кто бы ни закрывал писателя: этот регистратор, демон по концу отсрочки умершего регистратора, супервизор, останавливающий демон. Проверка холда в курсе (шаг 3) — не ограда, она сужает окно перед оградой движка. Поэтому демону без `WRITER_ABANDON` сетевой том не дают вовсе (шаг 3, `_engine_refuses`), а запасного режима для него — «запаркованного» писателя из пятого прохода — больше нет: он сам делал том `busy` навсегда (шестое ревью, блокер 1).

**Демон не ответил на `WRITER_ABANDON`.** Тогда писатель остаётся в сессии, и регистратор её оставляет (`_leave_session`). Демон отсоединит писателя и через отсрочку закроет сам; запишет ли тот что-нибудь, решит движок: с замком, который всё ещё его, — допишет своё, с чужим — ничего.

**Взятое и не записанное — потеря, и она считается.** Кадры, на которые писатель ответил `OK`, ещё лежали в его очереди или в открытом блоке; брошенный писатель их не запишет. Раньше они терялись без счёта (шестое ревью). Теперь после `abandon` в `Archive.dropped` лежит, что именно потеряно по каждому потоку (урок 7, шаг 8), и `_say_dropped` говорит это по каждой записи:

```python
            self.write_event(p[0], self.wall(), "archive.footage.dropped", ALARM, epoch=p[1], volume=st.name,
                             seconds=round(b - a, 1), since=a, until=b, exact=known)
            log.error("%s: %s%.0f s of recording %s are lost (%.0f–%.0f): the writer had taken them and not yet "
                      "written them when volume %s was given up. A backup recording or the camera's own archive may "
                      "still hold them — ask for a backfill of that stretch", self.name, "" if known else "up to ",
                      b - a, p[0], a, b, st.name)
```

Тревога `archive.footage.dropped` — в журнале записи, через базу воркера (`write_event`), и строка несёт `of: vms/<камера>`, которую ставит платформа по `about`: том, секунды, отрезок. Сумма — в heartbeat'е (`archive_dropped_seconds`) и в метрике регистратора `rec_footage_dropped_seconds_total`. `exact: true` — демон ответил, и отрезок посчитан по тому, что видит читатель. `exact: false` — демон молчал, посмотреть было некому, и отрезок — оценка сверху: кадры, взятые за периоды сброса движка до последнего взятого. Так же говорится о закрытии, которое не вернулось, когда сетевой том оставляют насовсем (`_leaving`): следующим писателем может быть другая коробка, и что допишет наш, неизвестно.

**Движок сам сказал «замок чужой».** Движок перед каждым блоком проверяет свой замок по пути. Чужой — писатель остановлен, и `put` отвечает `WRITER_STOPPED` с «volume lock lost». `Archive.put` ставит `lock_lost`, приёмник не считает это потерей движка (перемонтирование нашло бы тот же чужой замок), а `volume_pass` отдаёт том (`leave_volume`), что бы ни говорила строка холда, — и писатель бросается. Закреплённый том — тоже: раньше его писатель оставался, остановленный, и ничего не говорилось (седьмое ревью, блокер 2). Потеря сказана: взятое и не записанное — `archive.footage.dropped`, а `archive_error` и `archive_failure` говорят, что том взял другой писатель, пока регистратор снова не смонтирует его — под своим холдом и когда движок пустит. После этого то же говорит `archive_remounted` (`why`: *another writer took net*), как после потерянного движка. Тесты: `test_lock_lost.py::test_a_writer_whose_lock_another_writer_took_is_stopped_by_the_engine_and_given_up_writing_nothing`, `test_rec_volume.py::test_a_pinned_network_volume_whose_lock_another_writer_took_is_a_volume_error_counted_said_and_mounted_again`.

**`VOLUME_UNCLEAN` восстанавливает тот, кто держит том.** Монтирование, на которое движок отвечает `VOLUME_UNCLEAN`, было `away` навсегда, и `VOLUME_RECOVER` не вызывался нигде (пятое ревью, второй вопрос). Теперь `Archive._mount_rw` ещё раз спрашивает `confirm()`: регистратор, чей холд не подтверждён в эту секунду, не восстанавливает ничего. Потом `VOLUME_RECOVER`, тревога `archive.volume.recovered` (класс `alarm`, с результатом — видео могло пропасть: сбой посреди блока) и монтирование заново. Восстановление, которое не удалось, — `wrong`: это исправит только человек. Тест: `test_rec_volume.py::test_an_unclean_volume_is_recovered_only_under_a_hold_confirmed_this_second`.

Тест на двух живых демонах над одним каталогом: `test_rec_volume.py::test_a_box_frozen_whole_writes_nothing_into_the_network_volume_another_box_took_and_closes_nothing_there`. Коробка A заморожена целиком, B берёт том; A просыпается: её 30 кадров — `FENCED`, проход бросает писателя, у демона A писателей тома нет, в журнале записи — `archive.footage.dropped` на 30 секунд (`exact: true`), а том B чист — без восстановления и с записью B целиком.

### Писатель без хэндла: сессию оставляют

Другой путь к тому же `busy`: писатель, который есть в сессии, а хэндла у регистратора нет. `MOUNT_RW`, ответ на который не пришёл (`Unavailable.sent`), или `seal`, чьё закрытие не вернулось, ставят `Archive.orphan`. Тогда `_write_into` оставляет сессию (`_leave_session`: `abandon` и `successor`), и следующее монтирование под тем же владельцем подхватывает писателя. Так же поступают с `ALREADY_LOCKED`, где демон называет нашего владельца дольше `OWN_LOCK_FOR` (10 с) (пятое ревью, блокер 2; урок 6, шаг 4) — но один раз на блокировку, и не тогда, когда в `STATS` демона есть сессия с нашим именем клиента и чужим pid: владелец — имя тома, и носить его может другой процесс (шестое ревью; урок 6, шаг 4; `test_a_lock_under_our_owner_held_by_another_process_is_not_this_sessions_orphan`). Писателей другого тома в оставляемой сессии нет: у регистратора один том, и к этому моменту он закрыт, брошен или это тот самый, кого оставляют. Закрытие, которое не вернулось на потоке аренд, — последний вызов прохода: том монтируется снова на следующем (Т-M1). Тесты: `test_a_mount_whose_answer_was_lost_leaves_its_session_and_the_next_one_picks_the_writer_up`, `test_a_volume_locked_by_our_own_owner_longer_than_a_linger_is_an_orphan_of_this_session`, `test_a_remount_on_a_frozen_daemon_costs_the_pass_one_call_and_not_three`.

### При штатной остановке

Регистратор, который останавливался, отпускал слот, а захват тома — нет. Том оставался «занятым», пока захват не истекал, и тот, кто должен был писать туда следующим, ждал `slot_ttl` — сорок пять секунд без записи на каждом перезапуске и каждом плавном обновлении. Ни за что: процесс уже попрощался. Продукт измерил на своём ящике: от запуска до «все записи идут» было 62 секунды, стало 5 (обратная связь BR).

```python
    def after_stop(self) -> None:
        held = self.hold
        self._leaving = True
        try:
            self._close_store()
        finally:
            self._leaving = False
        if held is None:
            return
        try:
            self.release_hold()
            logging.info("%s: released %s on the way out", self.name, held)
        except OSError as e:                         # the store does not answer: the hold lapses by itself
            logging.warning("%s: could not release %s (%s); it lapses in %.0f s", self.name, held, e, self.slot_ttl)
```

Его зовёт конец `run`, и весь хвост остановки читается одним списком: конвейеры остановлены, последний heartbeat сказал об этом, слот отпущен, писатель закрыт после своего сброса, захват отпущен. `test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it` записывает этот порядок (`["close", "release"]`), а потом проверяет: следующий регистратор берёт том сразу, монтирует начисто и видит всё, что успел записать прежний.

Сброс писателя может занять до тридцати секунд, и это число переходит в юнит: `StopTimeout=40` у `recworker@` (урок 17). Убей процесс раньше — и остановка станет падением.

**Падение ничего этого не делает.** Холд истекает сам. А писатель ждёт в демоне, отцепленный, дольше, чем истекает захват, и тот, кто возьмёт том следующим под тем же владельцем `rec:<том>`, подберёт его целиком (шаг 8). Тот же тест кончается этим: третий регистратор ждёт, пока живой второй держит том, и получает его, когда захват истёк.

**Попутная находка, и она хуже самой задачи.** Процесс регистратора (`python -m vms recorder`) открывал хранилище со списком прав, написанным руками до того, как регистратор начал брать тома: эпохи и слот — и без захвата. На коробке с объявленным томом токен процесса отказывал ему в собственном месте. Тесты этого не видели: они строили регистратор на хранилище без ACL. Теперь права берутся из платформы (`REC_SPEC.sub.acl_worker()`), как у воркера камер (`test_the_recorder_process_holds_a_token_that_can_take_a_volume`). Это ещё один довод за правило «права выводятся из спецификации, а не пишутся рядом с ней» (М11, урок 5).

## Шаг 12 — Пишет ли писатель

`volume_error` отвечает на вопрос «держит том и может в него писать». Продукт показал, что этого мало: запись шла пятнадцать и двадцать семь минут подряд и не сохранила ни кадра, а все признаки говорили «пишет» (обратная связь U). Строка `running`, счётчики стока растут, heartbeat свежий. Сторож конвейера (`watchdog`) видит только то, что кадры **приходят**. Что с ними стало **после** стока, не проверял никто. Между «взял» и «лежит на томе» — очередь движка и его собственная политика: последовательность, которую он потерял, группа кадров, которую он обрезал.

Поэтому регистратор сравнивает два числа, которые видит сам:

```python
        measure = getattr(self.actuator, "offered", None)
        …
        try:
            if self.store:
                self._landed = int(self.store.status().get("totalWritten", 0)) - self._written_at_open
            landed = self._landed_before + self._landed
        except ArchiveError:
            if self.store is not None and self.store.lost:
                self._lost_engine()                  # the daemon no longer knows the session: remount, not wait
            return self.writer.state                 # a volume that does not answer measures nothing this pass
        for c, v in zip(running, vals):
            if v is None:
                continue
            seen = self._offered_seen.get(c)
            self._offered_total += v - seen if seen is not None and v >= seen else v
            self._offered_seen[c] = v
        state = self.writer.observe(self._offered_total + self._offered_extra, landed, wall)
```

**И по каждой записи, а не только по тому.** Наблюдатель смотрит на том целиком, и одна камера из тридцати, у которой группа кадров длиннее блока, не писалась совсем, а том показывал `ok` (третье ревью). Теперь сток считает ответы движка по записи (`RecSink.tally`): статус каждой записи несёт `samples_refused {статус: n}` — всё, кроме `OK`, включая `SEQUENCE_LOST`, — `/metrics` консоли `rec_samples_refused_total{unit,status}`, а `last_frame_at` значит **последний кадр, который писатель взял**, а не последний отданный. Тест: `test_recorder_metrics.py::test_a_recording_the_engine_refuses_is_counted_by_itself_and_its_last_frame_stops`.

**Отдано** — сколько байт конвейеры передали стокам, суммой **приращений** по каждой записи, а не суммой текущих счётчиков: запись, которая остановилась, уносила свой счётчик из суммы, `outstanding` уходил в минус, и том, не взявший из этих мегабайт ничего, застрявшим не назывался (второе ревью). К отданному прибавляется и то, что регистратор пишет в писателя сам — выкачанные диапазоны и копии удержаний (`_offered_extra`), иначе садящаяся дозапись маскировала бы застрявшую живую запись. Тест: `test_what_was_offered_stays_offered_when_a_recording_stops`. `GstRecActuator` считает отданное на `appsink` (урок 9). **Дошло** — что сказало само кольцо: `totalWritten` из `READER_STATUS` минус отметка на момент открытия, плюс то, что дошло под прежними писателями этого регистратора (`_landed_before`). Без этой суммы каждое переоткрытие обнуляло бы «дошло», а «отдано» — нет, и сторож увидел бы потерю, которой не было. Решает чистая логика в `vms/writerwatch.py`:

| Состояние | Когда | Почему так |
|---|---|---|
| **застрял** | отдано больше трёх блоков, а том не сдвинулся дольше минуты | нужны оба условия: тихая камера долго наполняет блок, и это не поломка |
| **теряет** | том двигается, но за пять минут дошло меньше 90 % отданного | сторож «том не двигается» этого не видит вообще, а на ящике продукта доходило 66–69 % |
| **в порядке** | всё остальное, включая «ничего не отдано» | резервная запись на удержании и тихая камера ничего не отдают — и они здоровы |

Состояние уходит в heartbeat отдельным полем `writer`, а консоль пишет его на томе: *writing stuck: 8 MB not landed for 61 s*, *losing writes: 67 % landing over 300 s*.

Лечение одно — открыть писателя заново:

```python
        if self.writer.reopen_due(wall):
            log.warning("%s: the writer is %s (%s) — reopening it", self.name, state["state"], state)
            for cid in running:
                self._release_if_broken(cid)
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, self.now())
            self.engine_lost = True                  # …and the writer itself: closed and opened again on the next pass
            self._lost_why, self._lost_at = f"the writer was {state['state']}: reopened", wall
```

Конвейеры останавливаются и считаются потерянными, сверка поднимает их с новой эпохой. А сам писатель закрывается и открывается снова на следующем проходе — тем же путём, что после пропавшего демона (`engine_lost`): новый писатель под тем же владельцем. Остановить одни конвейеры мало: если застрял писатель, новые конвейеры писали бы в него же. И не чаще раза в десять минут (`REOPEN_EVERY`). Если причина не в писателе, а в том, что ему дают, перезапуск каждую минуту только добавит к потере время, за которое писатель отпускает том. Heartbeat при этом говорит правду на каждом проходе. Исполнитель, который не умеет считать отданное, не говорит ничего: молчание здесь значит «не измерено», а не «всё хорошо».

Тесты — `tests/test_writer_watch.py`: `test_a_quiet_camera_is_not_stuck_and_a_standing_volume_with_megabytes_waiting_is`, `test_a_volume_that_moves_but_takes_two_thirds_is_losing`, `test_the_writer_is_reopened_once_in_ten_minutes_however_long_it_stays_wrong`, `test_the_recorder_says_it_in_its_heartbeat_reopens_the_writer_and_the_console_says_it_on_the_volume` (в нём после переоткрытия `engine_lost` поднят, а следующий `lease_pass` открывает новый `Archive` с писателем), `test_an_actuator_that_does_not_measure_says_nothing`.

## Шаг 13 — Глубина и числа

Ещё один проход, раз в минуту, — `depth_pass`. Он читает из индекса, на сколько дней назад уходит каждая запись (`depth_days`), и поднимает тревогу `archive.shallow`, когда кольцо тома **замкнулось** — `firstBlockId` больше нуля, старое уже перезаписывается — а запись держит меньше обещанного `min_depth_days`. Молодой том мелок потому, что молод, и тревоги не даёт. Зачем это и что с этим делать — [урок 18](18-what-the-archive-gives-up-first.md).

```python
    def metrics_text(self) -> str:
        from w2cplatform.console import label
        keeps = "".join(f'rec_keep_missing_seconds{{keep="{label(kid)}"}} {e.get("missing", 0)}\n'
                        for kid, e in sorted(self.keep_state.items()))
        return (f"# TYPE rec_recordings_running gauge\nrec_recordings_running {len(self.reconciler.actual)}\n"
                f"# TYPE rec_volume_wait gauge\nrec_volume_wait {1 if self.volume_wait else 0}\n"
                f"# TYPE rec_groups_backfilled counter\nrec_groups_backfilled {self.backfilled}\n"
                f"# TYPE rec_footage_dropped_seconds_total counter\nrec_footage_dropped_seconds_total {self.dropped_seconds:.1f}\n"
                + (f"# TYPE rec_keep_missing_seconds gauge\n{keeps}" if keeps else ""))
```

`rec_recordings_running` — сколько записей **действительно пишутся**, а не сколько настроено. Это число спецификация объявляет в `metrics` (`recordings_running`, по `status.phase`) и называет в `console: running`, и его же консоль считает по heartbeat'ам всех регистраторов: то, что читает проверка здоровья коробки (урок 17).

`rec_volume_wait` — ждёт ли закреплённый регистратор свой том (шаг 3). Имя метки удержания — строка, которую кто-то записал, и в `{keep="…"}` она идёт через `w2cplatform.console.label`: `\`, `"` и перевод строки экранированы, как требует текстовый формат Prometheus (восьмое ревью, часть 4: запись с именем `7"x` делала строку, из-за которой Prometheus отвергал весь скрейп `rec`). Так же экранируются все значения меток на `/metrics` консоли (урок 15 М10A). Тест: `test_row_reader.py::test_a_name_with_a_quote_or_a_newline_is_escaped_on_every_metrics_page`.

Всё остальное о регистраторе консоль берёт из его heartbeat'а и отдаёт на своём `/metrics`: `rec_volume_error`, `rec_volume_wait`, `rec_archive_away_seconds`, `rec_archive_failure{kind}`, `rec_writer{state}`, `rec_last_frame_age_seconds`, `rec_archive_depth_days`, `rec_archive_shallow`. Регистратору никто не звонит: консоль читает то, что он опубликовал, как и всё остальное (`test_a_recorders_troubles_are_numbers_not_only_a_heartbeat`).

## Результат

```python
r = recorder(box)                       # RecWorker("r-1", …, server="srv-1"), своя сессия с obsd
rec_con.create({"name": "1", "cam": "1"})   # оператор нажал «Запись», том не выбирал
rec_ctl.ensure_placed()
r.lease_pass()                          # ничего не объявлено: том сервера, отформатирован на квоту
r.reconcile_once()                      # [('start', '1')]
r.volume, r.store.url                   # ('srv-1', 'file://<box.root>/volume') — рядом с деревом ресурса <box.root>/tree

r.actuator.feed("1", t - 120, t)        # {'OK': 120} — сто двадцать кадров взяты
r.our_coverage("1")                     # [] — взято не значит видно: блок открыт
r.store.seal()                          # закрыть писателя и взять снова
r.our_coverage("1")                     # [(t - 120, t)]
[s.stream for s in r.store.spans("1")]  # ['1/e1'] — эпоха в имени потока
```

Камеру никто не держит:

```python
r.reconcile_once()                      # [('failed', '2')]
status["phase"], status["why"]          # ('waiting', 'camera held by nobody')
```

Держатель переехал на `srv-2`:

```python
r.resubscribe()                         # ['1']
r.reconcile_once()                      # [('start', '1')] — через rtsp://srv-2:8554/1, эпоха 2
```

В томе два потока, `1/e1` до переезда и `1/e2` после. Шкала страницы покажет одну линию.

Регистратора убили и подняли:

```python
again = recorder(box)
again.lease_pass()
again.store.reattached                  # True — писатель, которого оставил убитый, подобран целиком
```

**Одна подсистема, один урок.** Первая стоила четырёх.

## Что может пойти не так

- **Числовой идентификатор записи вместо имени.** Две записи одной камеры станут возможны, и придётся объяснять, что они значат.
- **Флаг «писать» на строке камеры.** Возврат к процессу, которому нужны и камера, и том.
- **Дом как жёсткое требование (метка).** Первая же авария на сервере остановит запись вместо того, чтобы увести её на соседа.
- **`near` у регистратора.** Он приколочен к тому и следовать не может.
- **Спросить у контроллера, где камера.** Связь, которой не было; лежит контроллер — не подписаться.
- **Подписаться, не проверив `phase == "running"`.** Адрес есть, потока за ним нет.
- **Кэшировать `source`.** Переезд держателя не заметится, пока кэш не протухнет.
- **Считать переездом `source() is None`.** Каждый перезапуск воркера будет ронять запись, которая могла бы просто подождать.
- **Считать молчание хранилища `source() is None`.** Упавшая во время сбоя запись не поднимется, пока хранилище не вернётся; ответ — источник, прочитанный последним.
- **Искать держателя по id записи.** Запись, названная не по камере, не переподпишется никогда.
- **Переподписка с той же эпохой.** Кадры двух разных конвейеров лягут в один поток.
- **Захват без открытия.** Все числа зелёные, а записи нет.
- **Отдавать единственный сломанный том.** Коробка перестанет писать совсем.
- **Отдавать недоступный том.** Записи перекладываются ради связи, которая вернулась через минуту.
- **Считать сломанный локальный диск недоступным.** Регистратор держит его с полной ёмкостью, и зелёные числа возвращаются.
- **Владелец писателя — имя процесса, а не тома.** Следующий держатель тома не подберёт писателя и будет ждать конца ожидания демона.
- **Ожидание демона короче истечения захвата.** Хозяин места его не застанет.
- **Вызов к демону без срока.** Один молчащий демон отсекает регистратор со всеми записями.
- **Отпустить захват раньше, чем закрыт писатель.** Следующий держатель найдёт в томе чужого писателя.
- **Проверять холд сетевого тома только перед монтированием.** Проснувшийся писатель пишет в кольцо, которое уже взяла другая коробка. Проверка — перед каждым кадром, `finish` и `seal`.
- **Считать проверку холда оградой.** Это проверка перед отправкой: один кадр замороженного процесса она пропустит. Ограда — у движка, и курс работает только с движком, у которого она есть (патч 07).
- **Давать сетевой том демону, который не умеет его бросить.** Он закроет писателя со сбросом — в том, который уже чужой. Регистратор такой том не берёт и говорит оператору, какой `obsd` обновить.
- **Отдавать сетевой том экземпляру того же слота с другого хоста сразу.** Прежний экземпляр мог быть заморожен на другой коробке, и окно его записи отмерено от ожидания претендента. Сразу берётся диск, сетевой том с прежним держателем на этом же хосте и отпущенный холд.
- **Считать закреплённый сетевой том своим без холда.** Его возьмёт свободный регистратор другой коробки, и запись закреплённого пропадёт молча. Закрепление выбирает том, холд решает, писать ли в него.
- **Держать `busy` под своим холдом бессрочно.** Регистратор не пишет ничего, а оператор видит только слово `busy`. Срок — `BUSY_FOR`, потом тревога и отпустить.
- **Продлевать холд сетевого тома, пока демон молчит, без срока.** На томе не пишется ничего, а коробка с живым демоном взять его не может. Срок — `ENGINE_SILENT_FOR`.
- **Закрывать писателя сетевого тома, чей холд потерян.** Сброс ляжет на чужой том. Писателя бросают (`WRITER_ABANDON`), а что он взял и не записал — считают.
- **Терять взятые кадры без счёта.** `OK` — это «взят», не «записан»; брошенный писатель очередь не допишет. Потеря — тревога `archive.footage.dropped` с секундами.
- **Восстанавливать том без свежего холда.** `VOLUME_RECOVER` перепишет статус тома, который, может быть, держит другой.
- **Подменщик держит холд за шаг на молчащем движке.** Том простаивает пять минут, хотя его могла бы взять коробка с живым демоном.
- **Верить счётчикам стока.** Они растут, когда кадры приходят, а не когда ложатся в том.
- **Перезапускать писателя на каждом проходе.** Если виноват не он, каждая минута добавит к потере время на его остановку.
- **Лечить застрявшего писателя одними конвейерами.** Новые конвейеры пишут в того же застрявшего писателя; закрыть и открыть надо и его.
- **Сток с томом, запомненным на старте конвейера.** После перемонтирования конвейер пишет в закрытый том, пока его кто-нибудь не перезапустит.

## Итог

- Запись — единица другой подсистемы, названная оператором: у камеры столько записей, во сколько томов её пишут, и у каждой свой ключ, своя эпоха, свой поток, свой потолок видимости.
- `requires: resource` — обязательство, `home` — предпочтение: быстрый путь вероятен, медленный гарантирован.
- Якорь пары — запись: она приколочена к тому. Следует камера, потому что её раздачу читают откуда угодно.
- `servers: distinct` над `place_by: volume`: второй регистратор на том же томе — не второе место для записи, а на соседнем диске той же коробки — именно оно.
- Том — место платформы: заявление оператора (строка таблицы `volumes`, `rec/volumes/*`) и холд того, кто его обслуживает (`rec/holds/*`), объявленные одной строкой `places`; диск прибивается окружением, объявленный том берётся по CAS, процесс без тома — запасной, а не поломка. Место за именем, строгий холд и молчание по виду места исполняет база воркера (ADR 0029).
- Открытие — часть захвата: не открылся — не обслуживается и не место; отдают только тогда, когда есть куда идти.
- Квота — размер кольца, и у локального тома тоже: поэтому на одном разделе их может быть два.
- Адрес подписки берётся из чужого heartbeat'а, тем же способом, каким его найдёт шлюз.
- «Камеру никто не держит» и «тома нет» — состояния, а не ошибки: `enrich` возвращает `None`, откат делает остальное, фаза `waiting` объясняет.
- Переезд держателя обнаруживается сравнением адресов и приводит к новой эпохе — новому потоку в томе.
- Писатель тома живёт в демоне под владельцем `rec:<том>`: убитый регистратор оставляет его отцепленным, следующий держатель подбирает целиком.
- Отказ тома называют по виду: `wrong` отдают и не берут обратно `REFUSED_FOR`, `away` и `busy` держат и называют в heartbeat'е каждый своим словом; диск на коробке, который не открывается, — `wrong`, и закреплённый регистратор с таким томом сообщает нулевую ёмкость. Сетевой том в `busy` под своим холдом держат не дольше `BUSY_FOR`.
- Каждый вызов к демону ждёт меньше аренды; пропавший демон и `WRITER_STOPPED` — перемонтирование на следующем проходе, а стоки спрашивают текущий том на каждом кадре и пишут дальше в новый.
- С тома уходят в одном порядке: конвейеры, писатель со своим сбросом, захват. Писатель тома, который держится строго, пишет только под холдом, подтверждённым моложе `slot_ttl − margin`, и закрывается только моложе `slot_ttl + HOLD_SKEW` (`may_write_place`, `may_close_place` платформы); позже его бросают (`WRITER_ABANDON`), а взятое и не записанное считают (`archive.footage.dropped`). `VOLUME_UNCLEAN` восстанавливает держатель под свежим холдом, с тревогой. Ограда тома — у движка (патч 07), и другого движка курс не поддерживает: демону без `WRITER_ABANDON` регистратор сетевой том не даёт. Сетевой том идёт за слотом только на коробке своего держателя (правило платформы), закреплённый сетевой том берётся под тем же холдом, что незакреплённый, а холд не продлевается через молчащий демон дольше `ENGINE_SILENT_FOR`.
- «Держит и может писать» ещё не «пишет»: регистратор сравнивает отданное писателю с дошедшим до кольца и говорит «застрял» или «теряет»; лечение — новые конвейеры и новый писатель, а счёт дошедшего идёт дальше через переоткрытие.

## Упражнения

1. Сделайте идентификатор записи числовым. Создайте две записи камеры 7 и опишите, что будут делать два конвейера.
2. Выразите дом меткой вместо `home`. Погасите этот сервер и опишите, что покажет `/unplaceable` и что при этом происходит с записью.
3. Уберите проверку `phase="running"` из `source`. Разместите камеру, не поднимая её воркер, и посмотрите на конвейер записи.
4. Считайте `source() is None` переездом. Перезапустите воркер и опишите, что произошло с записью.
5. Переподписывайтесь с той же эпохой. Переместите держателя и прочитайте таймлайн записи: какие минуты чьи?
6. Уберите `_write_into` из цикла захвата в `volume_pass`: пусть захват сразу считается местом. Объявите том с путём внутри обычного файла и посмотрите, что покажет консоль.
7. Монтируйте писателя под владельцем `rec:<имя регистратора>`. Убейте регистратор, дайте захвату истечь и посмотрите, что получит второй регистратор, взявший том.
8. Поставьте `OBSD_WRITER_GRACE_S=20` в тестовом демоне и `slot_ttl=45` регистратору. Убейте регистратор посреди записи. Кто подберёт писателя?
9. Уберите поправку «диск на коробке — `wrong`» из `_write_into`. Какой тест упадёт и что он увидит вместо ожидаемого?
10. Уберите `REFUSED_FOR`. Пусть том отказывает в `PUT_MEDIA`, но открывается. Что регистратор делает с ним проход за проходом?
11. Поставьте `OBSD_TIMEOUT=60`. Запустите `test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living` и объясните, сколько продлений аренды уложилось в минуту и почему.
12. Поменяйте местами `_close_store` и `release_hold` в `leave_volume`. Что получит следующий держатель тома и что он не увидит?
13. Оставьте сторожу записи только условие «том не двигается минуту». Подайте ему поток, из которого до тома доходит две трети, и посчитайте, сколько часов записи пропадёт, прежде чем кто-нибудь заметит.
14. Перезапускайте писателя каждый раз, когда сторож говорит «застрял». Причина — источник, который отдаёт мусор. Сколько времени за час регистратор провёл, отпуская том?

## Что дальше

Три процесса есть: контроллер, воркер, регистратор. Видео лежит в томах, за демоном; на ресурсе остались события.

[**Урок 11**](11-the-resource-process.md) — процесс ресурса, у которого нет контроллера. Он платформенный, и VMS не даёт ему ни строки кода: только декларации — сроки событий, удержания, ответ регистратора на просьбу освободить место.

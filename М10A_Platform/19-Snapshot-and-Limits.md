# Урок 19 — Снимок по воркеру, потолок хранилища и тишина, в которой это ломалось

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `Subsystem.snapshot_key` и `snapshot_prefix`; `SpecController.snapshot_shards` вместо одного объекта; пустой шард для воркера, которого больше нет; и читателя в М12, который сливает шарды и не врёт про их возраст. Затем `limits.py` — `max_bytes` как свойство стора, `TooLarge` и `check`; восьмой пункт контракта; `blobs.py` — дайджест вместо имени; тип поля `blob`, два отказа спеки, маршрут консоли и 413. И наконец — публикацию отдельным шагом прохода контроллера (`host.placement_pass`); `snapshot_age()`, читающий возраст из хранилища; метрику `<sub>_snapshot_age_seconds`; `ReadView.rpo()` в домене.
**Время:** ~145 минут.

## Зачем этот урок

Снимок контроллера (урок 11) — единственное, что покидает кластер. Он публикуется каждым проходом, то есть раз в пять секунд. Начнём с самой прямой его формы — **один объект на весь кластер** — и посмотрим, где она ломается; урок 11 уже показывает то, к чему этот урок придёт.

Посмотрите на это рядом с остальным, что платформа кладёт в объектное хранилище:

| объект | сколько их | что в каждом |
|---|---|---|
| `<sub>/heartbeats/<worker>` | по одному на воркера | что знает один воркер |
| `platform/resources/<server>/heartbeat` | по одному на сервер | что знает один ресурс |
| `<sub>/snapshot` | **один** | **все единицы кластера** |

Снимок — единственное место во всей платформе, где данные растут в **одном** объекте. Всё остальное нарезано по писателю и поэтому масштабируется вместе с кластером: больше единиц ⇒ больше воркеров ⇒ больше объектов, а каждый остаётся размером с то, что знает один писатель.

А у хранилища бывает потолок. Хранилище кластера М11 — `configstore://`, raft-группа демонов (урок 3) — не берёт строку тяжелее `storemachine.MAX_VALUE`:

```python
MAX_VALUE = 512 << 10      # what a row's items may weigh (`items_bytes`): see the notes above
```

512 КиБ на строку, ключи и значения вместе. Число выбрано не на глаз: строка весит пару сотен байт, а строка в 32 МиБ уходила в журнал raft — каждый член группы держал её в памяти, писал в свой журнал и слал отстающему, и пока такая запись шла по сети, heartbeat'ы лидера ждали за ней. Демон отказывает дважды: на двери (413 `toolarge`, прежде чем что-либо попало в журнал) и в самой машине состояний, чей отказ — функция одной команды, поэтому все члены группы отказывают одинаково. Объект, который на кластере лежит строкой (`VariablesObjectStore`, шаг 8), наследует этот потолок; объекты-файлы (`cluster://`) потолка не объявляют; любое другое объектное хранилище, которое назовёт установка, может объявить свой.

Теперь арифметика, и её стоит взять не из таблицы, а из теста (шаг 6):

```
600 камер: один объект 252 КиБ (потолок 64), крупнейший шард 21.1 КиБ — запас x3.0
```

Один объект на 600 единиц — уже половина потолка строки configstore; около 1200 единиц он перестаёт в неё помещаться и дальше растёт вместе с кластером. Тест меряет против потолка ещё в восемь раз ниже, 64 КиБ: там один объект не влезает уже сейчас, а крупнейший шард держит тройной запас. Где именно потолок — решает хранилище; что один объект на весь кластер однажды в него упрётся — решает форма.

И ломалось это тихо. `publish_snapshot()` стоял последним в общем `try` цикла контроллера: размещение к этому моменту уже отработало, в лог уходило «placement pass failed» — про единственное, что **не** упало, — а домен М12 продолжал отдавать вчерашний снимок. Починено в **шаге 17**, и до него эта тишина — часть задачи.

Потолок у хранилища есть, и мы про него знаем — но до этого урока платформа его не **спрашивает**: вызывающий не знает, сколько держит стор, в который пишет. `FsObjectStore` не падает никогда, поэтому на коробке этот дефект не воспроизводится: его пришлось считать руками.

Первая половина урока нарезала снимок по воркеру, и потолок перестал быть проблемой снимка. Он не перестал быть **потолком**. Вопрос, который остаётся, ровно два:

**Первый: почему предел сработал бы только для снимка?** Не должен. Потолок принадлежит хранилищу, а не вызывающему, и в конфигурации он опаснее: строка, которая не влезла, — это отказ **правки оператора**, а не устаревший каталог у домена.

**Второй: а если конфигурация одной единицы больше, чем держит строка?** NVR на сотню каналов, панель СКУД, охранная панель из будущих подсистем — всё это выглядит как «конфигурация, которая в строку не поместится».

Начнём со второго, потому что половина ответа на него уже написана.

И третье, чем этот урок кончается. Обе поломки выше — и переполненный снимок, и слишком большая строка — ломались **тихо**, и это отдельный дефект, который стоит починить один раз для обеих.

Цикл контроллера в самой прямой форме (тот, что получится к концу этого урока, — в шаге 17):

```python
    while not stop.is_set():
        try:
            ctl.ensure_placed()                       # deleted rows unplaced; new units onto the workers it sees
            ctl.redistribute()                        # units of a RELEASED slot (scale-in) onto the rest
            ctl.ensure_home(1)                        # ONE unit a pass back to the server its row names, if it is back
            ctl.publish_snapshot()
        except Exception:                             # noqa: BLE001
            logging.exception("placement pass failed")
        stop.wait(5)
```

Четыре вызова, один `try`, одна фраза в логе. Выглядит аккуратно. На деле это **две разные работы**, и склеены не только их обработчики, но и то, что о них узнаёт человек.

**Первое: фраза называет не то.** `publish_snapshot()` стоит последним. Когда падает он, три предыдущих вызова уже отработали — размещение прошло. А в лог уходит «placement pass failed»: про единственное, что не падало. Дежурный идёт разбираться с размещением.

**Второе: отказы прячут друг друга, и во вторую сторону хуже.** Упал `ensure_placed()` — `publish_snapshot()` не выполняется вовсе. Слой выше тихо начинает читать вчерашнюю копию, и слова «snapshot» в логе нет ни разу.

**Третье: возраст копии негде увидеть.** `DomainDirectory.ages()` написан в М12 с урока 1 и считает ровно это — насколько домен отстал. До сегодняшнего дня его **не вызывало ничто, кроме тестов**. Единственное число, которое показало бы проблему, было вычислимо и не вычислялось.

И за последние уроки у `publish_snapshot()` **прибавилось способов упасть**: `TooLarge` на шарде сверх потолка (шаг 8), `ValueError` на воркере по имени `unplaced` (шаг 3), отказ политики (урок 20). Все они читались одинаково.

## Что нужно знать заранее

- **Урок 2** — `Variables` и строка как одна запись с полями.
- **Урок 4** — объектное хранилище: пишется целиком, читается целиком, `list(prefix)`, и «удаления нет».
- **Урок 3** — шов «хранилище выбирается URL-ом» и контракт, гоняемый против любого бэкенда: он понадобится, чтобы объяснить, почему правильный ответ **не** «сменить хранилище».
- **Урок 11** — heartbeat: почему он один на воркера, и что это была не эстетика; `snapshot()` и `publish_snapshot()` в том виде, в каком мы их здесь ломаем.
- **Урок 15** — консоль и `/metrics`: кто вообще отвечает на вопросы про состояние.
- **М12, урок 3** — модель чтения домена и то, как она показывает устаревшее.
- **М10B, урок 19** — `cred_secret` в строке: «отдельное хранилище покупает изоляцию на чтении, а ротацию продаёт обратно». Вторая половина этого урока — та же мысль, доведённая до механизма.

## Чему научитесь

- Отличать вопрос «где это лежит» от вопроса «какого размера то, что мы кладём».
- Шардировать по писателю и видеть, что это даёт не только место.
- Писать пустой объект как способ сказать «здесь больше ничего нет».
- Читать нарезанное так, чтобы не соврать про возраст целого.
- Спрашивать у хранилища, что оно может, вместо того чтобы помнить число.
- Отличать три разных «большого конфига» друг от друга — и обнаруживать, что два из трёх не требуют нового механизма.
- Класть непрозрачный блоб так, чтобы ревизия продолжала работать.
- Писать объект раньше указателя и понимать, что случится при падении между ними.
- Видеть, когда общий `try` склеивает не обработку ошибок, а смыслы.
- Отдавать наблюдаемость не логу, а числу, которое растёт.
- Хранить такое число там, где его сможет прочитать кто угодно, а не в процессе, который его породил.
- Отличать два разных молчания и не показывать их одинаково.

---

## Шаг 1 — Сначала — почему это не вопрос хранилища

Соблазн очевидный: объектное хранилище называется URL'ом (`OBJECTS`), а значит, положить снимок туда, где потолка нет, — одна переменная окружения, без единой правки выше. На кластере М11 такое хранилище уже стоит: `OBJECTS=cluster://…` — файлы на каждом сервере, `max_bytes = 0` (М11, урок [6](../М11_Cluster/06-what-stays-on-the-server.md)); для арендованного кластера есть `s3+https://…`. Шов для этого и сделан (урок 3).

Но он покупает не то, что кажется.

**Лимит — это сигнализация, а не болезнь.** Болезнь вот — `publish_snapshot` в прямой форме, одним объектом (сегодняшний — в шаге 4):

```python
    def publish_snapshot(self) -> None:
        import json
        self.objects.put(self.sub.config("snapshot"), json.dumps(self.snapshot()).encode())
```

Безусловная запись каждые пять секунд, без сравнения с предыдущей. Конфигурация единиц меняется, когда её правит оператор, то есть почти никогда. 252 КиБ каждые 5 с — это ~50 КБ/с на кластер, круглосуточно, при нуле изменений. Убрав потолок, вы снимете будильник, а счёт останется и будет расти вместе с числом единиц и числом кластеров.

**И второе: хранилище без потолка — не бесплатное.** Арендованный S3 или MinIO на пограничной коробке с двадцатью пятью единицами — новая зависимость, которую надо ставить, бэкапить и мониторить, ради задачи, которой у этой коробки нет: её снимок весит около десяти килобайт. Файлы кластера ничего нового не разворачивают, но и они не отменяют счёта: 252 КиБ, переписанные каждые пять секунд при нуле изменений, остаются 252 КиБ, сколько бы ни держало хранилище.

Стоит взять это как правило шире одного случая. **Вопрос «куда это положить» задаётся вторым.** Первым — «какой оно формы»: сколько объектов, кто каждый из них пишет и от чего каждый растёт. Ответ на первый вопрос лежал в этой же платформе, в соседнем файле, и был написан тремя уроками раньше.

## Шаг 2 — Ключ, и имя, которое приходится зарезервировать

```python
    # `<name>/snapshot/<worker>` — one object per worker, the same shape the heartbeat key already has.
    # …
    def snapshot_key(self, worker: str | None) -> str:
        if worker == UNPLACED:
            raise ValueError(f"a worker may not be called {UNPLACED!r}: that key is the shard for the units "
                             f"no worker holds")
        return f"{self.name}/snapshot/{worker or UNPLACED}"

    # `<name>/snapshot/` — what a reader lists to find every shard.
    def snapshot_prefix(self) -> str:
        return f"{self.name}/snapshot/"
```

`<name>/snapshot/<worker>` — ровно форма `heartbeat_key`, и это не совпадение, а цель.

Единицы, которые **никто не держит**, тоже должны уезжать наверх: строка без воркера — это именно то, что домен обязан увидеть. Значит, им нужен свой шард, и его имя попадает в то же пространство, что и имена воркеров. Отсюда отказ: `unplaced` зарезервировано, и **зарезервированному имени нужно правило, которое его резервирует**, а не надежда, что воркера так не назовут.

Почему нельзя положить их в сам `<name>/snapshot`, рядом с каталогом? Потому что `FsObjectStore` — это дерево каталогов, и файл `<sub>/snapshot` не может сосуществовать с каталогом `<sub>/snapshot/`; на кластере объекты — те же файлы (`cluster://`). Ограничение одной реализации, но реализация в курсе есть, и «на файловой системе не соберётся» — достаточная причина не делать так нигде.

## Шаг 3 — Сборка шардов

```python
    def snapshot_shards(self) -> dict[str, dict]:
        """The snapshot as one object per worker, keyed by shard name."""
        with one_pass(self):                          # `server_of` per unit read every heartbeat per unit (the scaling pass)
            return self._snapshot_shards()

    def _snapshot_shards(self) -> dict[str, dict]:
        keep = ["id"] + [f for f in self.spec.snapshot if f != "id"] + ["revision"]
        now, out = self.wall(), {}
        for r in self.units():
            w = self.where(r["id"])
            self.sub.snapshot_key(w)              # refuses a worker named `unplaced` before it shadows the shard
            sh = out.setdefault(w or UNPLACED, {"cluster": self.cluster, "worker": w, "ts": now, self.spec.rows: []})
            # An address leaves with no credential in it (`hide_in_url`; the eleventh review, blocker 4): a row stored before
            # the refusal, or by another build, carried its `?pwd=` into the domain's directory.
            sh[self.spec.rows].append({**{k: hide_in_url(r[k]) for k in keep if k in r}, "worker": w,
                                       "server": self.server_of(w or "")})
        return out
```

Отбор полей — тот же, что в уроке 11, и список `snapshot:` из YAML продолжает решать, что уезжает. Изменилась только **раскладка по объектам**. Две поздние добавки не меняют формы: обёртка `one_pass` держит прочитанное на проход, чтобы `server_of` на каждую единицу не перечитывал каждый heartbeat (проход масштабирования, урок 8), а `hide_in_url` вынимает пароль из адреса, прежде чем строка уедет в каталог домена (одиннадцатое ревью).

`now` берётся один раз на весь проход, а не на каждый шард: у всех шардов одного прохода один и тот же `ts`. Это не косметика — читатель ниже на него опирается.

Обратите внимание, чего здесь **нет**: воркер с нулём единиц не получает шарда. Объект, которого никогда не было, создавать незачем. А вот объект, который был, — совсем другая история.

## Шаг 4 — Пустой шард — это способ сказать «здесь больше ничего нет»

```python
    def publish_snapshot(self) -> None:
        with one_pass(self):
            self._publish_snapshot()

    def _publish_snapshot(self) -> None:
        import json
        shards = self.snapshot_shards()
        prefix = self.sub.snapshot_prefix()
        # A worker that is GONE — scaled in, or its units moved away — keeps its last shard forever: nothing
        # in the platform deletes an object. Its units would go on being reported to М12 from a worker that
        # no longer exists. So every shard already in the store that this pass did not fill is written EMPTY.
        for key in self.objects.list(prefix):
            shards.setdefault(key[len(prefix):], {"cluster": self.cluster, "worker": None, "ts": self.wall(),
                                                  self.spec.rows: []})
        # A cluster with no units at all — … — would publish NOTHING, and "published that there are none" would read as
        # "never published" (feedback AA). М12's member that has not published does not report (Lesson 10),
        # so such a cluster stayed "never reported" for ever. An empty `unplaced` shard is the statement.
        if not shards:
            shards[UNPLACED] = {"cluster": self.cluster, "worker": None, "ts": self.wall(), self.spec.rows: []}
        for name, shard in shards.items():
            try:
                self.objects.put(prefix + name, json.dumps(shard).encode())
            except TooLarge as e:
                # …
```

Что делает ветка `except TooLarge` — в шаге 10.

Вот цена, которую платит шардирование, и её стоит понять до конца.

Пока снимок был одним объектом, «единицы больше нет на w-2» выражалось само собой: следующая запись перетирала весь объект, и строки в нём просто не оказывалось. Нарезав на объекты, вы получаете **состояние, размазанное по ключам**, а в уроке 4 записано прямым текстом: *«No delete: nothing in the platform removes an object»*.

Значит, воркер, которого убрали при scale-in, оставляет свой последний шард **навсегда**, и домен продолжит читать из него единицы, которых там нет, от воркера, которого нет. Лечится это не удалением, а записью: шард, который этот проход не заполнил, пишется **пустым**.

Именно поэтому `objects.list(prefix)` в этом методе — не оптимизация и не удобство. Это единственный способ узнать, что когда-то было написано.

Та же мысль с другого конца — кластер, у которого единиц нет вовсе. Ему нечего публиковать, и «опубликовал, что их нет» читалось бы как «не публиковал ни разу» (отзыв AA). Поэтому такой кластер пишет пустой шард `unplaced`: пустой объект и здесь — утверждение.

> **Проверено снятием.** Уберите цикл `for key in self.objects.list(prefix)` — и `test_a_worker_that_is_gone_stops_reporting_its_cameras` падает, а остальные тесты набора проходят. Уберите вызов `self.sub.snapshot_key(w)` — падает `test_a_worker_may_not_be_called_unplaced`, и снова только он.

## Шаг 5 — Читатель: слить, не соврав про возраст

В М12 `Cluster.snapshot()` (`Source/domain/federation.py`) читал один ключ. Теперь он читает префикс — ровно тем же движением, каким `heartbeats()` рядом читает heartbeat'ы. Домен — слой над VMS и читает её снимок (`vms/snapshot/`), поэтому строки у него называются `cameras`; сам приём от подсистемы не зависит:

```python
        keys = self.objects.list(SNAPSHOT)
        if not keys:
            return None
        best: dict[str, tuple[float, dict]] = {}
        oldest = None
        for key in keys:
            raw = self.objects.get(key)
            if not raw:
                continue
            shard = published(self.name, key, raw, _a_shard)
            if shard is None:
                oldest = 0.0                       # a shard nobody can read has no age: the copy is as old as can be
                continue
            ts = float(shard.get("ts", 0))
            oldest = ts if oldest is None else min(oldest, ts)
            for row in shard.get("cameras", []):
                uid = str(row.get("id"))
                if uid not in best or ts > best[uid][0]:
                    best[uid] = (ts, row)
        return {"cluster": self.name, "ts": oldest or 0, "cameras": [r for _, r in best.values()]}
```

Два решения, и оба стоят объяснения.

**Возраст целого — возраст самого старого шарда.** Единого мгновения, в которое весь кластер был в этом состоянии, больше нет: объекты читаются по одному. `ts` снимка — это RPO домена, то, насколько он отстал; складывать туда самый свежий шард значило бы показывать RPO лучше, чем он есть. Каталог свеж настолько, насколько свежа его самая несвежая часть. Отсюда и шард, который не читается (`published` с проверкой `_a_shard`: не JSON, `ts` не конечное число, строка единицы не объект): он пропускается и считается один раз, а копия кластера становится самой старой, какая бывает, — `oldest = 0.0`, а не «свежая без этого шарда».

**Единица, пойманная на переезде, читается один раз, из более свежего шарда.** Домен читает шарды по очереди, и писатель может оказаться между двумя `put` — тогда единица окажется и в старом шарде, и в новом. Это **не** та авария, которую `where()` домена отвечает как спорную (`contested`, со списком кластеров): там два разных **кластера** заявляют права на единицу, и это действительно отказ размещения. Здесь — обычный переезд внутри одного кластера, и правильный ответ на него «она на w-1», а не исключение.

Стоит заметить, чего шардирование **не** дало. У heartbeat'ов N писателей, и нарезка даёт им независимость записи. У снимка писатель один — контроллер, — и он пишет все шарды подряд в одном проходе. Форма куплена ради **размера**, а не ради параллелизма, и разорванное чтение, от которого защищает выбор по `ts`, — единственное, что эта форма добавила к рискам.

## Шаг 6 — Замер после

```python
    ctl = _cluster(box, 600, workers=12, capacity=50)                 # …
    ctl.ensure_placed()
    ctl.publish_snapshot()
    shards = box.objects.list("vms/snapshot/")
    assert len(shards) == 12
    biggest = max(len(box.objects.get(k)) for k in shards)
    one_object = len(json.dumps(ctl.snapshot()).encode())             # what it used to publish
    assert one_object > CAP, f"the single object fits after all ({one_object} B) — this test proved nothing"
    assert biggest <= CAP // 3, f"a shard is {biggest} B: the margin the heartbeat has is gone"
```

Двенадцать воркеров по пятьдесят единиц: 600 единиц, у каждой поля, которые оператор действительно заполняет. Оба числа берутся из настоящего публикатора, против объявленного потолка. Первая проверка защищает тест от самого себя: если однообъектная версия однажды перестанет превышать потолок, тест обязан об этом сказать, а не молча пройти.

Вторая формулирует цель не как «влезает», а как «с тем же запасом, что у heartbeat'а». Влезть впритык — значит вернуться сюда, как только у `ref` вырастет соглашение об именовании.

`CAP` в тесте — `64 * 1024`, объявленный потолок в восемь раз ниже потолка строки configstore (512 КиБ). Меряют против него нарочно: форма, которая держит тройной запас под 64 КиБ, держит его под любым потолком выше, а один объект на 600 единиц (252 КиБ) не влезает под ним уже сейчас — и не влезет под 512 КиБ, как только кластер перерастёт 1200 единиц. Объявленный потолок — пункт контракта (шаг 9), а не свойство одного бэкенда, поэтому и тест его не берёт у бэкенда, а объявляет сам.

## Шаг 6а — Почему шарды остаются, когда потолка нет

Объекты кластера — файлы, `max_bytes = 0`, и шард в мебибайт пишется на одном сервере и читается целиком на другом (`test_a_shard_of_a_megabyte_is_an_object_like_any_other`, `tests/cluster/test_cluster_objects.py`, М11). Казалось бы, можно вернуть один объект. Не нужно, и причина — та же, что в шаге 1, только теперь она главная, а не вторая.

**Шард — это то, что задевает одно изменение.** Единица переехала — изменились два шарда, двух воркеров; остальные десять в этом проходе байт в байт те же, что в прошлом. Один объект на кластер менялся бы целиком от любой правки и переписывался бы целиком каждые пять секунд — те самые 50 КБ/с при нуле изменений из шага 1, только без будильника, который о них напомнит. Нарезка по воркеру делает возможным писать **только то, что изменилось**.

Скажем честно, где это сегодня: `publish_snapshot` всё ещё пишет каждый шард каждым проходом, без сравнения (`spec.py`, `_publish_snapshot`). Шард — файл на сервере контроллера, и переписать его дешевле, чем переписать строку raft на трёх серверах; но запись только изменившихся шардов — следующий шаг, и это упражнение 3. Форма для него уже есть, а один объект её бы отнял.

И две причины поменьше. Потолок может объявить любое хранилище, которое установка назовёт в `OBJECTS` (шаг 8), и шард держит снимок под ним, сколько бы единиц ни было. А читатель в М12 (шаг 5) и протокол пустого шарда (шаг 4) уже написаны и проверены: возвращаться к одному объекту значило бы переписать их без выигрыша.

## Шаг 7 — Три вопроса к «большому конфигу»

**Это коллекция?** Тогда её элементы — единицы, а не поле. Пример из подсистемы, которая стоит на этой платформе, — VMS (М10B): NVR на сто каналов там — сто строк-камер, а сам NVR существует только в её коде, в `vms/config.py`:

```python
def device_of(source: str) -> str:
    """The thing DriverPack connects to. Cameras sharing it share one session:
    `driverpack://acme/10.0.0.50/ch/17` and `…/ch/18` are two channels of one NVR;
    a camera with an SD card is a device with one channel. Pure parsing — the
    vendor's own addressing stays opaque, only the grouping is ours — and one
    spelling for one address (`_host`)."""
```

Устройство существует только как **группировка** на воркере подсистемы: одна сессия, общий лимит воспроизведений. Платформа о нём не знает ничего — она видит сто строк, и потолок у неё на строку (пара сотен байт: `test_the_size_a_store_charges_is_keys_and_values` держит строку между 100 и 400), а не на NVR. Платформа шардирует конфигурацию по единице с самого начала — тот же ход, что сделан со снимком в первой половине урока.

Замер на СКУД, против потолка строки configstore (524 288 Б):

```
таблица 5000 пропусков в одном поле  : 492 780 Б  влезает впритык (94 % потолка)
те же 5000 как отдельные строки      :      91 Б каждая  влезает
```

Поле растёт вместе с числом пропусков: следующая тысяча пробивает потолок, и правка оператора становится отказом. Строка не растёт вовсе. И у строк попутно появляется то, чего у поля нет: ревизия на пропуск, свой CAS, своя запись «кто изменил».

**Это вопрос представления?** Тогда чинится представление, а не хранилище:

```
маска полигонами, 4 зоны x 20 точек :        883 Б  влезает
маска сеткой 80x45, base64          :        600 Б  влезает
маска попиксельно 1920x1080, base64 :    345 600 Б  влезает, две трети потолка
маска попиксельно 3840x2160, base64 :  1 382 400 Б  НЕ влезает
```

Последние две строки — арифметика: бит на пиксель, base64 добавляет треть. Полигоны и сетка не замечают разрешения камеры; попиксельная маска растёт с ним квадратично.

**Остаётся третье: один непрозрачный блоб**, который платформа не интерпретирует и который правда нужен целиком. Прошивка панели, обученная модель, попиксельная маска. У детектора VMS (`det.subsystem.yaml`, М10B) под это уже есть поле — и оно молча упрётся в тот же потолок:

```yaml
    params:    {type: string}                      # the model's settings, opaque to the platform — and SMALL
```

Ради третьего и делается всё остальное в этом уроке.

## Шаг 8 — Потолок объявляет хранилище

```python
NO_CEILING = 0


class TooLarge(Exception):
    """A write over the store's declared ceiling.

    Carries the numbers rather than a sentence about them: the caller that
    knows what it was writing (a snapshot shard, a unit's row) adds the part
    a person needs — how many units that was, and what to do instead."""

    def __init__(self, key: str, size: int, limit: int, detail: str = ""):
        self.key, self.size, self.limit, self.detail = key, size, limit, detail
        super().__init__(f"{key}: {size} bytes over this store's limit of {limit}"
                         + (f" — {detail}" if detail else ""))


def check(key: str, size: int, limit: int, detail: str = "") -> None:
    """Raise `TooLarge` when `limit` is set and `size` is over it."""
    if limit and size > limit:
        raise TooLarge(key, size, limit, detail)
```

Двадцать строк, и они закрывают дефект целого класса. До них потолок жил в прозе: `FsObjectStore` и `FileVariables` не отказывали никогда, поэтому запись, которую хранилище кластера отвергнет, была зелёной в каждом тесте, а платформа находила свой потолок так, как находят потолок в темноте. Снимок из первой половины нашли арифметикой на бумаге, а не падающим тестом.

**Отказ, а не обрезание.** Половина строки хуже, чем отсутствие строки, а стор, который молча роняет хвост объекта, — это стор, который врёт про `get`. На `get`, говорящем правду, построен каждый цикл CAS в платформе.

Как измеряется размер — тоже решение, и оно одно на все хранилища (`w2cplatform/variables.py`):

```python
def items_bytes(items: dict) -> int:
    return sum(len(str(k).encode()) + len(str(v).encode()) for k, v in items.items())
```

Ключи и значения вместе, а не JSON вокруг них — так меряют строку все бэкенды платформы, и так демон configstore взвешивает её на двери и в машине состояний (`w2cplatform/storemachine.py`):

```python
        elif cmd["op"] == "put" and items_bytes(cmd.get("items") or {}) > MAX_VALUE:
            res = {"toolarge": items_bytes(cmd["items"])}      # the door refuses it first; the log must agree anyway
```

А настоящее число живёт там, где ему место, — в самом хранилище, и объявляется вместе с тем, **какое** это хранилище. Ручка configstore объявляет потолок демона своим `max_bytes`, и строку сверх него отказывает сама, ещё до сокета; 413 `toolarge` от демона она превращает в тот же `TooLarge`. URL может объявить меньше, как у `memory://` (шаг 9) (`w2cplatform/configstorevars.py`):

```python
# `configstore:///run/configstore/<role>.sock[?max_bytes=n&timeout=s]` — this server's daemon, by the role's socket.
def _open(url: str, writer: str | None = None, acl: dict[str, list[str]] | None = None) -> ConfigstoreVariables:
```

```python
        # The daemon's ceiling, or less when the URL declares less, like `memory://` (twelfth pass).
        self.max_bytes = min(max_bytes, MAX_VALUE) if max_bytes else MAX_VALUE
```

У объектов кластера — ответ «нет потолка», и это тоже ответ (`ClusterObjectStore`, `Source/cluster/objectstore.py`):

```python
    max_bytes = 0                       # files on a disk: no ceiling worth naming …
```

А объекты, которые лежат **строками** — ключи, которые спека объявляет строками (`objects: {rows: […]}`): их создают один раз на весь кластер, — наследуют потолок строки и говорят об этом сами (`VariablesObjectStore`): `self.max_bytes = max(0, getattr(vars_, "max_bytes", 0) - len("data"))`.

## Шаг 9 — Восьмой пункт контракта

```
8.  the store SAYS what it can hold (`max_bytes`, 0 meaning no ceiling), and a write over
    that is refused, not truncated. …
```

Пункт из двух половин, потому что первая есть у каждого бэкенда, а вторая — не у каждого. **Каждый стор отвечает** на вопрос `max_bytes`; каталог отвечает «0», и это ответ, а не отсутствующий атрибут. **Стор, объявивший потолок,** отказывает и оставляет прежнее значение на месте. Среди бэкендов курса потолок объявляют двое: `configstore://` — `MAX_VALUE`, 512 КиБ на строку, или меньше, если так скажет `?max_bytes=n`, — и `memory://…?max_bytes=n`; `file://` отвечает «0», если тест не передал свой `max_bytes`.

Чтобы вторая половина не осталась теорией, у `memory://` появился параметр:

```python
    # `memory://<name>?max_bytes=<n>`: the ceiling is part of WHICH STORE THIS IS, so it belongs in the
    # URL beside the name, exactly as the backend itself does (Lesson 20).
```

Потолок — часть того, **какое это хранилище**, поэтому он в URL рядом с именем. Тот же второй бэкенд, который в уроке 3 нашёл недостающий седьмой пункт, теперь гоняет восьмой.

> **Ловушка, на которую я напоролся.** В контрактном наборе этот пункт ловит `TooLarge` **по имени класса, а не по `except TooLarge`**. Рядом живёт `test_portability`, который перестраивает `sys.modules`, чтобы доказать, что платформа импортируется без юниксовых модулей, — и после него класс, пойманный при импорте тестового модуля, уже не тот класс, который поднимает стор. `except` молча перестаёт ловить. Пункт про то, что стор **делает**, и записан он в форме, которая переживает набор, в котором живёт.

## Шаг 10 — Кто получает отказ и в каком виде

Стор отказывает байтами. Тот, кто знал, что это были за байты, добавляет остальное:

```python
            except TooLarge as e:
                # The store refuses with bytes; the caller knows what those bytes WERE. A shard is one
                # worker's assignment, so an oversized shard is not a shape problem any more — it is a
                # store too small to hold what a single worker carries, and `OBJECTS` is what names it.
                raise TooLarge(e.key, e.size, e.limit,
                               f"{len(shard[self.spec.rows])} units on {name}; the snapshot is already one "
                               f"object per worker, so the store is the thing to change (OBJECTS=…)") from e
```

А правка оператора получает **413, и получает её человек, который её набрал**:

```python
        # 413, and to the person who typed it. The store's ceiling used to be a number in a document and a
        # surprise in production; now the edit that does not fit is refused at the console, with the size
        # and the limit in the sentence, before anything is written.
        except TooLarge as e:
            return 413, {"detail": str(e), "error": str(e)}
```

## Шаг 11 — Почему «положить конфигурацию в objects» — не ответ

Это самое место, где легче всего ошибиться, и ошибка выглядит как упрощение.

Строка в Variables имеет CAS, одного писателя и `revision`, за которым следит реконсайлер: поменяли поле — единица перезапустилась с новым значением. У объекта нет ничего из этого. Перенесите конфигурацию туда целиком — ревизия не сдвинется, ничто не перезапустится, и вы начнёте строить механизм, который у платформы уже был.

Ровно это записано в М10B, уроке 19, про `cred_secret`: отдельное хранилище **покупает изоляцию на чтении, а ротацию продаёт обратно**.

## Шаг 12 — Дайджест в строке, байты в сторе

```python
def digest(data: bytes) -> str:
    """The name these bytes have, and the only name they have."""
    return f"{ALGO}-{hashlib.sha256(data).hexdigest()}"
```

Ссылка — **дайджест, а не имя**, и из этого одного выбора следует всё остальное:

- другие байты — другой дайджест — другая строка — `revision` двигается — реконсайлер перезапускает единицу. Ротация тем механизмом, который уже был;
- ключ-дайджест пишется один раз и никогда не перезаписывается, поэтому last-writer-wins объектного хранилища больше нечего решать;
- воркер может кэшировать по дайджесту вечно и быть правым;
- одна и та же маска на ста единицах хранится один раз.

```python
    def blob_key(self, d: str) -> str:
        if not is_digest(d):
            raise ValueError(f"not a digest: {d!r} — a blob field holds `sha256-<hex>`, and the bytes go "
                             f"to the object store first")
        return f"{self.name}/{BLOBS}/{d}"
```

Написание — `sha256-<hex>`, через дефис. Эта строка одновременно ключ, ключ становится путём на файловой системе, а двоеточие — не везде допустимый символ пути (урок 14). Одно написание, везде — шестой пункт контракта, применённый к себе.

## Шаг 13 — Объект первым, строка второй

```python
    def put_blob(self, data: bytes) -> str:
        """Store the bytes; return the digest to put in the row."""
        import json
        d = blob_digest(data)
        # …
        # On the platter before the row names it (`FsObjectStore.put_durable`); a store without the barrier puts as it can.
        getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
        return d
```

Пропущенное на месте `# …` — снятие этих байтов со списка уборки (урок 20): к этому уроку его нет. `put_durable` — запись с барьером: объект на диске раньше, чем строка его назовёт.

Порядок — не стилистика. Падение между двумя записями оставляет **объект, на который никто не показывает**: безвредно и собираемо. Обратный порядок оставляет **строку, показывающую в никуда**, — единицу, которая не может стартовать.

Тот же порядок, которым публикуется хранилище личностей в М12 (`identity/rev-N`, потом `identity/pointer`), и по той же причине.

> **Это единственное утверждение урока, которое не проверено снятием.** Падение между двумя записями в тесте не воспроизводится. Проверено рассуждением, а не измерением, и сказать это честнее, чем сделать вид.

## Шаг 14 — Два отказа спеки

```python
        heavy = [n for n, f in fields.items() if f.type == "blob" and n in spec.snapshot]
        if heavy:
            raise ValueError(f"spec {spec.name}: a blob may not be in the snapshot: {heavy} — the snapshot "
                             f"is one object per worker under a ceiling, and a blob is what does not fit "
                             f"in a row in the first place")
```

Первый — при **загрузке**, как у секрета: подсистема, написанная через год, не сможет сделать эту ошибку.

```python
        for name, f in self.fields.items():
            if f.type == "blob" and fields.get(name) and not is_digest(fields[name]):
                raise Refused(f"{name} takes a digest, not the bytes ({len(str(fields[name]))} of them): "
                              f"PUT the bytes to /{self.rows}/<id>/{name} and the row gets the digest back")
```

Второй — на **записи**. Самое естественное, что сделает клиент, — вставит блоб прямо в строку; это же и положит строку за потолок. Отказ называет маршрут, а не просто говорит «велико».

## Шаг 15 — Маршрут, который возит не JSON

```python
    def blob_route(self, h, path: str) -> None:
        field = path.split("/")[3]
        f = self.spec.fields.get(field)
        if f is None or f.type != "blob":
            h.close_connection = True
            return h._send(404, {"detail": f"{field} is not a blob field", "error": "no such blob field"})
        try:
            known = self.ctl.unit(self._uid(path)) is not None
        except PARSE_ERRORS:
            known = False
        if not known:
            h.close_connection = True
            return h._send(404, {"detail": "no such unit", "error": "no such unit"})
        if not blobs_slots().acquire(blocking=False):
            h.close_connection = True
            h._extra_headers = (("Retry-After", "1"),)
            return h._send(503, {"detail": "this console takes so many blobs at once (BLOBS_AT_ONCE) — retry", "error": "busy"})
        try:
            if not self.read_body(h, int(os.environ.get("CONSOLE_MAX_BLOB", MAX_BLOB))):
                return
            n = int(h.headers.get("Content-Length", 0) or 0)
            return h._send(*self.put_blob(self._uid(path), field, h.rfile.read(n), h.headers.get("X-User", "operator")))
        finally:
            blobs_slots().release()
```

Id единицы маршрут берёт через `_uid` — тот же `path_id`, по которому её проверили ворота (урок 15, третье ревью). Сюда запрос доходит уже **допущенным**: ворота спросили право `admin` на единицу по пути до того, как прочитан хоть байт тела (урок 15, шестое ревью — токен без гранта слал 32 МиБ восемь раз подряд, и консоль держала 331 МиБ до своего 403). Поле не блоб-поле этой спеки или единицы нет — 404, и тело не читается. Потолок `MAX_BLOB` (32 МиБ, `CONSOLE_MAX_BLOB`) — только у этого маршрута, у остальных `MAX_BODY` (1 МиБ); блоб, чей `Content-Length` больше, получает 413 до первого прочитанного байта — и клиент этот 413 читает, а не получает сброс соединения: сокет с непрочитанным телом закрывается в два шага, `SHUT_WR` и дочитывание до секунды (`linger`; урок 15, седьмое ревью). И читается не больше `BLOBS_AT_ONCE` (2) блобов сразу — каждый это `MAX_BLOB` памяти, пока его читают и кладут, — следующему 503 с `Retry-After`, как лишнему экспорту. `h.rfile.read(n)` здесь уже не читает сокет: тело прочитано в `read_body` и лежит в памяти. Это потолок запроса к консоли; у хранилища потолок свой: у файлов кластера его нет, а стор, объявивший `max_bytes`, может держать и меньше. Тест: `test_console_load.py::test_what_the_path_decides_is_asked_before_the_body_and_a_blobs_ceiling_is_a_blob_routes`.

И единственное место во всей системе, где «смените объектное хранилище» — правильный ответ:

```python
            # The blob is bigger than the STORE will hold — which is the one case where changing the store
            # is the answer, because a blob is exactly the class of data an object store exists for. The cluster's
            # objects are files on each server (`OBJECTS=cluster://…`, `cluster/objectstore.py`) with no ceiling; a
            # store that declares one (`?max_bytes=`) is what refused this.
            return 413, {"detail": f"{e} — a blob is what an object store is for: this one declares a ceiling; the "
                                   f"cluster's file objects (OBJECTS=cluster://…) have none", "error": str(e)}
```

Объект-блоб получает этот 413 только от стора, который потолок объявил: в курсе это объекты-строки (`VariablesObjectStore`, потолок строки configstore) или `FsObjectStore(max_bytes=…)` теста (`test_a_blob_over_the_stores_ceiling_names_the_store`).

Разница со снимком из первой половины урока стоит того, чтобы её проговорить. Снимок был **проблемой формы**: один объект рос вместе с кластером, и смена хранилища сняла бы будильник, а не счёт. Блоб — **класс данных, ради которого объектные хранилища существуют**. Тот же совет, диаметрально разная обоснованность.

## Шаг 16 — Мусор, которого никто не собирает

```python
    # Every digest any row currently names: what the sweep keeps (`sweep_blobs`, below).
    def blobs_referenced(self) -> set[str]:
```

Заменённая маска остаётся в сторе. В этом уроке уборки нет, и `blobs_referenced` — та половина, которую можно написать честно уже здесь: список, который скажет сборщику, что оставить. Сам сборщик (`sweep_blobs`: пометить, подождать, снести) пишет урок 20, и комментарий в коде уже ссылается на него. Тест называет мусор своим именем:

```python
    assert stored == {old, new}                                  # both still there
    assert ctl.blobs_referenced() == {new}                       # one of them referenced
    assert stored - ctl.blobs_referenced() == {old}              # and this is the garbage nobody collects
```

## Шаг 17 — Два `try`

Цикл контроллера — платформенный: `controller_loop` в `w2cplatform/host.py`, тот, что запускает `python3 -m w2cplatform controller <sub>` для любой подсистемы из каталога спек. Сам цикл короткий — проход и пять секунд ожидания, — а проход вот:

```python
def placement_pass(ctl, what: str | None = None) -> None:
    what = what or f"{ctl.spec.name} placement"
    with ctl.one_pass():
        step(ctl, what, "pass", lambda: ctl.pass_once(1),
             f"{what}: the pass raised (its own steps say what they could not do) — tried again on every pass")
        # What the layer above loses when this fails: its copy stops ageing forward. The age itself is on `/metrics`
        # (`<sub>_snapshot_age_seconds`), read from the store, so it survives a restart and any console can answer it.
        step(ctl, what, "publish", ctl.publish_snapshot,
             f"{what}: publishing the snapshot failed — the layer above is now reading a stale copy")
```

`step` — один шаг прохода в своём собственном `try`:

```python
def step(owner, what: str, name: str, fn, failed: str | None = None) -> bool:
    """One step: True when it went. A failure is said with its trace the first time of a spell, "works again" after."""
    failing = owner.__dict__.setdefault("_host_failing", set())
    try:
        fn()
    except Exception:                                    # noqa: BLE001
        if name not in failing:
            failing.add(name)
            log.exception("%s", failed or …)
        return False
    …
```

Два вызова `step`, два `try`, две фразы — и это не аккуратность. Публикация — последний вызов прохода: когда она падала внутри общего блока, размещение уже прошло, а лог говорил «placement pass failed» — про единственное, что не падало. Обратное прятало вторую половину: упавшее размещение пропускало публикацию, слой выше тихо устаревал, а слова «snapshot» в логе не было нигде. Две работы, два отказа, две фразы.

**Размещение и публикация — внутри одного `one_pass`** (урок 8, шаг 1). Снимок спрашивает строку, размещение и сервер каждой единицы — то, что проход размещения только что прочитал; удержанные на проход, эти ответы стоят снимку ноль чтений, а написанное проходом читается обратно из хранилища. После ожидания следующий проход читает всё заново. Тест: `test_read_budget.py::test_an_idle_controller_pass_over_a_thousand_cameras_reads_each_row_once`.

Фраза публикации говорит о последствии, а не о вызове: «publishing the snapshot failed — the layer above is now reading a stale copy». Разница между «publish_snapshot failed» и этой строкой — разница между «сломался вызов» и «вот что теперь неправда». Второе — то, что нужно человеку в три часа ночи.

И говорит её `step` **один раз за полосу отказов**: трейс — на первом упавшем проходе, «works again» — на первом удавшемся после. Публикация, падающая каждые пять секунд неделю, — одна запись в логе, а не сто двадцать тысяч одинаковых.

Побочный эффект, который стоит заметить: размещение **продолжается**, даже если публикация падает каждый проход. В общем `try` это было так случайно — потому что публикация стояла последней. Теперь это сказано.

Внутри первого шага та же мысль идёт глубже: `pass_once` (урок 11) держит каждое своё действие — `ensure_placed`, `redistribute`, `ensure_home` и остальные — в отдельном `try`, говорит про упавшее «placement pass failed at <шаг>» и оставляет отчёт о проходе. Поэтому `step` вокруг него почти никогда не срабатывает: он ловит то, что `pass_once` не смог сказать сам. Причина та же, что у этого шага, с другой стороны: свежий снимок не значит, что размещение работает. Возраст снимка и возраст успешного прохода — два разных числа, и у каждого своя метрика.

## Шаг 18 — Возраст читается из хранилища, а не хранится в процессе

```python
    def snapshot_age(self, now: float | None = None) -> float | None:
        import json
        from .rows import FIELDS
        now = self.wall() if now is None else now
        oldest = None
        prefix = self.sub.snapshot_prefix()
        for key in self.objects.list(prefix):
            raw = self.objects.get(key)
            if not raw:
                continue
            try:
                ts = finite(json.loads(raw).get("ts", 0))   # `nan` passes every `min` and read as fresh (the review's eighth pass)
            except PARSE_ERRORS as e:
                FIELDS.garbled(f"{key}#ts", e)
                return now                            # a shard that does not parse has no age: the oldest there can be
            FIELDS.parsed(f"{key}#ts")
            age = self.eyes.age(key, ts, ts, self.sub.name)
            oldest = age if oldest is None else max(oldest, age)
        return oldest
```

Соблазн — завести в контроллере поле `last_published_at`. Не годится, и по трём причинам сразу:

- **у контроллера нет порта.** Он «holds nothing, two instances are harmless» (урок 11) — некому спросить;
- **его перезапускают свободно.** Поле обнулится, и метрика соврёт в самый интересный момент;
- **их может быть двое.** У каждого своё поле, и они разойдутся.

А из хранилища на этот вопрос ответит **кто угодно, кто может читать объекты**, — и поэтому его может отдать консоль, у которой порт есть.

**Возраст шарда — сколько этот читатель видит его неподвижным, по своим часам.** Не `now − ts`: так сравнивались бы часы двух машин, контроллера и читателя. `ts` шарда здесь — **жетон**, который меняется с каждой публикацией, а не время; `self.eyes` (`Eyes` в `contract.py`, тот же судья, которым контроллер решает, жив ли воркер) помнит, когда впервые увидел шард с этим жетоном, и возраст — сколько с тех пор прошло по монотонным часам читателя. Время писателя читается для одного: когда жетон сменился, расхождение часов уходит в `SKEW_MAX` подсистемы — в `<p>_heartbeat_skew_seconds_max`, где часы, ушедшие вперёд, уже измеряются. Контроллер, чьи часы ушли на час вперёд и остановились, писал шарды на час вперёд — его копия стареет на минуту за минуту. Контроллер, отстающий на 100 с и публикующий каждый проход, не старый никогда. Тест: `test_garbled_rows.py::test_a_snapshot_written_by_a_clock_running_ahead_is_not_fresh_and_its_lead_is_measured`.

Цена — у читателя нет памяти дольше его жизни. Консоль, запущенная минуту назад, наблюдала минуту, и её возрасты начинаются с нуля: остановившийся контроллер она увидит старым через столько, сколько сама на него смотрит, а не сразу. Так поступает каждый судья платформы, и это сознательный выбор — лучше подождать окно, чем поверить чужим часам.

**Возраст целого — возраст самого старого шарда** (`max` по возрастам). То же правило, что у читателя в М12: один шард, переставший переписываться, **и есть** отставание кластера, а самый свежий показал бы RPO лучше настоящего. Число такого рода имеет право ошибаться только в пессимистичную сторону.

**Шард, у которого нет времени, делает старой всю копию.** Шард, который не разбирается, поднимал исключение, а вместе с ним падал весь `/metrics`; теперь `PARSE_ERRORS` дают возраст `now` — старше не бывает, — и ключ один раз записывается как испорченное поле `<ключ>#ts` (`FIELDS.garbled`, на `/metrics` — `<p>_console_rows_garbled{table="field"}`). То же для `ts`, который не число: `finite` не пропускает `nan`, `inf` и `-inf` (восьмое ревью), а `nan` иначе проходил бы любое сравнение и читался бы как свежий. Следующая публикация чинит: шард разбирается, `FIELDS.parsed` снимает с ключа отметку. Тест: `test_garbled_rows.py::test_a_garbled_snapshot_shard_makes_the_published_copy_old_and_never_fresh`.

## Шаг 19 — Метрика, которая растёт

```python
        age = self.ctl.snapshot_age(now)
        lines += [f"# TYPE {p}_snapshot_age_seconds gauge",
                  f"{p}_snapshot_age_seconds {-1 if age is None else round(age, 1)}"]
```

`-1` — не отсутствие данных, а **отдельное состояние**: «не публиковалось ни разу». Ноль означал бы «опубликовано только что», и кластер, чей контроллер не справился ни разу с момента установки, выглядел бы здоровее всех.

Строка лога живёт на хосте, куда никто не смотрит. Число на `/metrics` растёт, и на него вешается порог.

## Шаг 20 — В домене — своё молчание, и оно другое

```python
    def rpo(self) -> dict[str, float | None]:
        """{cluster: seconds behind}, `None` for a cluster that did not answer."""
```

Два молчания, и оператор делает по ним **разное**:

| что молчит | что это значит | где видно |
|---|---|---|
| воркер | его единицы не работают | `causes()` |
| снимок кластера | кластер работает, картина домена не двигается | `rpo()` |

`rpo()` берёт числа у `DomainDirectory.ages()` — того самого, которого до сих пор не вызывало ничто, кроме тестов (`Source/domain/readview.py`, `Source/domain/federation.py`). Второе молчание коварнее: ломаться нечему там, куда пойдут смотреть. Тест домена ставит это рядом — домен читает снимки VMS, поэтому его тест говорит о камерах (`tests/domain/test_lesson3_readview_api_gateway.py`):

```python
    assert view.list()["rpo"] == {"north": 120.0, "south": 0.0}
    assert view.causes() == [], "a stale snapshot is not a silent worker, and must not be reported as one"
    assert all(r["worker_state"] == "live" for r in view.list()["rows"]), "the cameras are fine, and the list says so"
```

## Шаг 21 — Тест гоняет настоящий цикл

Соблазн — вызвать методы руками и проверить логи. Тогда тест проверял бы пересказ, а предмет здесь — **сами блоки `try`**. Поэтому вызывается `controller_loop` из `w2cplatform/host.py`, тот же, что запускает `python3 -m w2cplatform controller <sub>`, а останавливается он собственным ожиданием цикла (`tests/test_pass_failures.py`, `_one_pass`):

```python
    def wait_once(timeout=None):
        stop.set()
        return True

    stop.wait = wait_once
```

Один проход, и выход по `while`. А дальше — две проверки, зеркальные друг другу. В первой публикация падает на сторе с потолком в 64 байта (`FsObjectStore(…, max_bytes=64)`: шард не влезает), во второй падает `ensure_placed`:

```python
    lines = _one_pass(ctl)
    assert any("publishing the snapshot failed" in ln for ln in lines), lines
    assert not any("placement pass failed" in ln for ln in lines), lines
    # …and the placement it did is still there: the pass did its first job
    assert ctl.where(1) == "w-1"
```

```python
    ctl.ensure_placed = boom
    lines = _one_pass(ctl)
    assert any("placement pass failed" in ln for ln in lines), lines
    assert not any("publishing the snapshot failed" in ln for ln in lines), lines
    assert box.objects.list("vms/snapshot/"), "the publish was skipped because placement failed"
```

Обратите внимание на `assert not` в обеих. Проверить, что нужная фраза есть, — половина; вся суть в том, что **лишней нет**. Во второй «placement pass failed» говорит уже `pass_once` («… at ensure_placed»), и снимок при этом опубликован: упавший шаг размещения не остановил ни остальные шаги, ни публикацию.

## Что может пойти не так

- **Нарезали и забыли про удаление.** Самая дорогая ошибка урока, и тихая: домен месяцами показывает единицы на воркере, которого нет. В хранилище без удаления состояние стирается только записью.
- **Взяли самый свежий `ts` как возраст целого.** RPO домена начинает выглядеть лучше, чем он есть, ровно в тот момент, когда один из шардов перестал обновляться.
- **Подняли исключение на единице в двух шардах.** Это переезд, а не авария. Отказ размещения — это два разных **кластера**, заявляющих права на одну единицу.
- **Собрали `ts` внутри цикла по единицам.** Тогда у шардов одного прохода разные метки, «самый старый» начинает гулять, и разорванное чтение становится неотличимо от отставшего шарда.
- **Решили, что теперь можно и heartbeat'ы сложить в один объект «для консистентности».** Это тот же дефект с другого конца: N писателей одного объекта — гонка последнего писателя, и каждая запись переписывает чужое.
- **Вернули один объект снимка, раз потолка больше нет.** Каждая правка переписывает весь кластер, и запись только изменившегося становится невозможной (шаг 6а).
- **Перенесли конфигурацию в объекты целиком.** Ревизия не двигается, реконсайлер ничего не замечает, и единица работает со старым значением, пока её не перезапустит что-нибудь другое.
- **Сослались на блоб именем, а не дайджестом.** Возвращается всё, что дайджест снимал: перезапись по одному ключу, кэш, который нельзя доверять, и правка, которую ревизия не видит.
- **Написали строку раньше объекта.** Падение между ними оставляет единицу, которая не стартует, вместо мусора, который никому не мешает.
- **Обрезали вместо отказа.** `get` начинает возвращать то, чего `put` не писал, и каждый цикл CAS выше построен на обратном.
- **Положили блоб в `snapshot:`.** Отказано при загрузке — но если бы не было отказано, снимок перестал бы публиковаться, а увидели бы это по устаревшему каталогу у домена.
- **Решили, что теперь всё большое — это блоб.** Первые два вопроса шага 7 закрывают большинство случаев без нового механизма, и они задаются первыми.
- **Написали общий `try` и «улучшили» текст.** «pass failed» вместо «placement pass failed» честнее, но человеку по-прежнему нечего делать: непонятно, что именно неправда.
- **Положили возраст в поле процесса.** Перезапуск обнулит, второй экземпляр разойдётся, а спросить всё равно некого.
- **Посчитали возраст как `now − ts`.** Часы писателя, ушедшие вперёд, делают остановившуюся копию «свежей» на всё своё опережение; отстающие — делают живую старой.
- **Взяли самый свежий шард.** RPO станет выглядеть лучше настоящего ровно тогда, когда один шард отстал.
- **Сделали `0` для «не публиковалось».** Кластер, не опубликовавший ни разу, выглядит самым свежим.
- **Смешали `rpo` и `causes`.** Устаревший снимок начнёт показываться как молчащие воркеры, и оператор пойдёт чинить работающее.
- **Проверили только наличие нужной строки в логе.** Старый код прошёл бы половину таких тестов.

## Итог

Снимок лежал там же, где heartbeat'ы, — в объектном хранилище, за тем же швом, с тем же URL бэкенда. Разница между ними была не в хранилище, а в **форме**: heartbeat нарезан по писателю и растёт вширь, снимок был один и рос вглубь — под любым потолком, какой объявит хранилище, от 512 КиБ строки configstore до 64 КиБ теста. У файлов кластера потолка нет, а форма остаётся, потому что шард — это то, что задевает одно изменение.

Нарезка по воркеру убирает потолок как класс — 252 КиБ в одном объекте против 21.1 КиБ в крупнейшем шарде, запас втрое даже под 64 КиБ, — и не требует ни новых полей, ни отказа от существующих, ни второго хранилища. Платит она одним: состояние теперь размазано по ключам, а хранилище не умеет удалять, поэтому пустой объект становится частью протокола.

И остаётся правило, которое переживёт этот конкретный снимок. Когда упирается в лимит, первым делом стоит спросить не «какое хранилище взять побольше», а «сколько здесь объектов и от чего каждый растёт». Второй вопрос обычно уже отвечен где-то рядом, в том же коде.

Потолок хранилища перестал быть числом из документа. Стор отвечает, сколько он держит, отказывает сверх этого, и отказ доезжает до человека: 413 на правке, «20 единиц на w-1» на шарде. Восьмой пункт контракта гоняет это против любого бэкенда, а `memory://…?max_bytes=n` делает вторую половину пункта наблюдаемой на одной коробке.

Конфигурация, которая не влезает в строку, распадается на три случая, и только третий требовал чего-то нового. Коллекции — это единицы, и платформа шардирует их по единице с самого начала. Представление чинится представлением. А непрозрачный блоб получает поле типа `blob`: байты в объектном хранилище под своим дайджестом, дайджест в строке, объект пишется первым.

Главное здесь не в блобах. Ссылка сделана дайджестом, и из этого одного выбора выпали ротация, кэш, дедупликация и неизменяемость ключа — ни одного из них не пришлось строить. Так выглядит выбор представления, который платит за себя, и он стоит того, чтобы его искать.

Честный остаток записан двумя строчками: порядок записи проверен рассуждением, а не тестом, и уборки осиротевших блобов в этом уроке нет (её пишет урок 20).

Один `try` вокруг двух работ — это не экономия трёх строк, это потеря различия. Размещение и публикация падают по разным причинам, значат разное и требуют разного, а сообщение было одно и называло не то.

Теперь их два, и второе говорит о последствии: «слой выше читает устаревшую копию». Возраст этой копии читается из хранилища — оттуда на него может ответить любой, у кого есть порт, и по своим часам, а не по часам писателя, — и выходит числом, которое растёт, а не строкой на хосте, куда никто не смотрит. `-1` отделяет «ни разу» от «только что». В домене то же число наконец поднято на поверхность, рядом и **отдельно** от молчащих воркеров, потому что это разные аварии.

И маленькое общее правило, которое стоит унести: **сообщение об отказе называет не вызов, который упал, а утверждение, которое перестало быть верным.**

## Упражнения

1. **Верните один объект** и запустите `test_the_shard_fits_where_the_one_object_did_not`. На каком числе единиц он падает у вас против объявленного потолка в 64 КиБ? А против `MAX_VALUE` configstore — сходится ли с прикидкой «около 1200» из начала урока?
2. **Уберите запись пустого шарда**, отмасштабируйте кластер в меньшую сторону и посмотрите на `holdings()` домена. Сколько проходов пройдёт, прежде чем кто-нибудь заметит?
3. **Сделайте запись условной** — пишите шард, только если он изменился с прошлого прохода. Что взять за признак изменения, чтобы это не превратилось в сравнение JSON-строк? Сколько записей файлов это снимет на кластере в 600 единиц за сутки — и что станет с `ts` шарда, по которому домен считает возраст (шаг 5)?
4. **Придумайте, как шардировать иначе** — по диапазону `id`, по странице фиксированного размера. Что ломается в шаге 4 при каждом варианте и почему «по писателю» оказалось дешевле остальных?
5. **Найдите в платформе ещё один объект, который растёт не вширь.** Если нашли — посчитайте, на каком масштабе он упрётся. Если не нашли, запишите, почему остальные растут правильно.
6. **Поставьте `max_bytes` на файловый стор** — сначала в размер строки configstore (`MAX_VALUE`, 524 288), потом в восемь раз меньше (65 536) — и прогоните весь набор. Что упадёт первым? Это дефект или тест, писавший больше, чем такой прод позволил бы?
7. **Уберите `check` из `put`** — по одному в трёх сторах — и посмотрите, какие тесты падают в каждом случае. Почему это три разных теста, а не один?
8. **Сделайте ссылку именем вместо дайджеста** (`mask: "perron.png"`) и попробуйте написать тест «маска поменялась — единица перезапустилась». В какой момент вы упрётесь?
9. **Напишите сборщик мусора** для `<sub>/blobs/*`: что он должен прочитать, чего ему не хватает в объектном хранилище, и почему «удалить всё, на что никто не ссылается» опасно ровно между двумя записями шага 13.
10. **Возьмите панель СКУД на 5000 пропусков** и разложите её по трём вопросам шага 7. Сколько подсистем получится и где окажется расписание доступа?
11. **Прикиньте блоб на 50 МБ** — прошивку. Влезает ли она в `s3+https://`? Что в этом уроке ломается при таком размере, а что нет?
12. **Верните общий `try`** и прогоните `test_pass_failures.py`. Какие два `assert` падают и почему это именно `assert not`?
13. **Сломайте публикацию навсегда** (потолок в 64 байта) и дайте циклу поработать. Что делает размещение? Что показывает `/metrics` через минуту, через час?
14. **Перенесите `snapshot_age` в поле контроллера** и напишите тест на перезапуск процесса. На какой строке он сломается?
15. **Поднимите `rpo` на страницу** домена. Как показать «кластер жив, картина устарела» так, чтобы это не выглядело аварией единиц?
16. **Найдите в платформе ещё один общий `try`** вокруг разнородных работ. Что он склеивает и какое сообщение выдаёт?
17. **Придумайте порог на `<sub>_snapshot_age_seconds`.** От чего он должен зависеть — от интервала публикации, от `SYNC_INTERVAL` домена, от обоих?

## Что дальше

[**Урок 20**](20-ObjectACL-and-Sweep.md) закрывает то, что этим уроком открыто. У строк права выводятся из спеки с первых уроков; у объектного хранилища `FsObjectStore` не знает ни писателя, ни префиксов. Пока в объектах лежали только heartbeat'ы и шарды снимка, это было безобидно. С этого урока там лежит конфигурация — байты блобов. Урок 20 выводит права на объекты из той же спеки (`acl_objects_worker`, `acl_objects_controller`, `acl_objects_console`: у каждого каталога один писатель), показывает, что для этого пришлось переложить ключи, и находит у блоба защиту сильнее любого права на запись — его дайджест. И пишет уборку, которой в этом уроке нет.

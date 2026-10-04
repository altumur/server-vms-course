# Урок 14 — Ресурс как работа платформы: хранение, зеркало, ватерлиния и две ОС

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `w2cplatform/resource.py` целиком — heartbeat, сроки хранения по строке каждой подсистемы, зеркало к соседу без всякой карты, возвращение домой после замены диска, регистрацию чужих проходов и HTTP. Единственный процесс курса, у которого нет контроллера. А потом допишете тот же проход на случай, когда срок выполнить нельзя: `disk_space` и `Resource.space()` — измерение диска, а не дерева; ручку `platform/space` с двумя отметками; `relieve()`, который говорит подсистемам, сколько байт освободить; и дверь `hook.free(need, now, min_days)`, за которой подсистема решает, чем именно.
**Время:** ~170 минут.

## Зачем этот урок

В уроке 1 роль ресурса была названа одной фразой: **то, что не может переехать.** Архив на дисках этого сервера, GPU в этом корпусе, сетевая карта в этом VLAN. Всё остальное в системе движется — воркеры переезжают, единицы перераспределяются, контроллер безразличен к тому, на какой машине он идёт; ресурс привязан физикой.

Из этого следует вещь, которая сначала выглядит упущением: **у ресурса нет контроллера, и это не потому, что до него не дошли руки.** Контроллер нужен, чтобы решать, где что работает. Про ресурс решать нечего: он там, где он есть. Единственное, что с ним делают, — это политика (сколько дней хранить) и починка. А политика — не решение, а правило, которое выполняется на таймере.

Это один из тех случаев, когда правильный ответ — не заводить сущность. Смоделируй архив подсистемой — и у диска появится строка размещения, а `redistribute` однажды попробует его переместить, когда слот лапсируется. В проектной записке М11 этот сценарий отвергнут с прямой ссылкой на чужие грабли (Nomad #12118, CSI-тома).

Второе, что делает этот урок, — вводит единственный механизм отказоустойчивости, который в курсе есть **для данных**, а не для процессов: копию закрытых бакетов на соседнем сервере. Без карты, без координатора и без реестра — по правилу, которое и есть назначение.

Шаг 2 научил ресурс удалять по сроку: у каждой единицы есть `retention_days`, и то, что старше, уходит. Это **обещание оператору** — тридцать дней камеры 7, — и пока места хватает, обещание выполняется само.

Этот урок про то, что происходит, когда его выполнить нельзя.

Случай не экзотический и даже не аварийный. Сервер вернулся из простоя, и на соседе временно вдвое больше единиц, и все пишут сюда. Оператор добавил двадцать камер с детекторами, не добавив дисков. На том же разделе выросло то, чего ресурс не писал вовсе: журналы, хранилище конфигурации, чужие файлы. Во всех трёх случаях ретенция по дням честно продолжает удалять старое — и честно не успевает, потому что она считает **время**, а кончается **место**.

Поэтому здесь появляется вторая, совсем другая вещь. Ретенция — контракт; ватерлиния — предохранитель. Их легко спутать и дорого путать: предохранитель, притворяющийся контрактом, молча отдаёт вчерашние данные важной единицы, а оператор об этом узнаёт через месяц.

Три решения, ради которых урок стоит читать внимательно.

**Мерить диск, а не своё дерево.** У ресурса уже есть `usage()` — сумма размеров файлов под корнем. Для этого решения она не годится дважды.

**Платформа не удаляет ни одного файла подсистемы.** Она измеряет и называет число байт. Что отдать — знает только тот, кто знает, что его файлы значат.

**Две отметки, и зазор между ними измеряется в часах записи, а не в процентах.**

И третье, чем этот проход кончается. Всё, что написано выше, держится на двух системных вызовах, которых на Windows не существует, — и до этого места платформа туда не ставилась вообще. Не «работала хуже»: не запускалась.

Оператор ставит коробку там, где у него камеры, и иногда эта коробка — Windows. До этого урока платформа туда не ставилась вообще. Не «работала хуже» и не «теряла функцию»: **не запускалась**.

Причин ровно две, и обе — по одному вызову:

| где | вызов | где вводится | что на Windows |
|---|---|---|---|
| блокировка хранилища | `fcntl.flock` / `syscall.Flock` | урок 2 | нет такой функции |
| водяной знак на диске | `os.statvfs` / `syscall.Statfs` | шаг 10 | нет такой функции |

Две функции на пятнадцать тысяч строк — и весь модуль не поднимается. Стоит на это посмотреть внимательно, потому что **форма отказа в двух языках разная**, и из этого следует, какими должны быть тесты.

В Go это ошибка компиляции: `undefined: syscall.Flock`. Не собирается — значит не запустится, и об этом узнаёшь на сборке.

В Python — хуже. `import fcntl` стоит в шапке `variables.py`, и на Windows **не импортируется сам модуль**. Ни одна функция не существует, чтобы упасть. Любой процесс, который трогает `Variables`, умирает до первой строчки работы, с трассировкой, показывающей на `import`, а не на то, что вы пытались сделать. Тест, который вызывает функции, этого не увидит никогда: вызывать нечего.

> **Что можно проверить без железа.** Всё, включая зеркало, восстановление и полный диск: два ресурса в одном процессе, два каталога, поддельный клиент вместо HTTP. В М10B это `test_lesson1_platform.py::test_the_resource_is_a_platform_job_that_mirrors_any_subsystems_buckets` — и слово *camera* в нём не встречается. Заполненность диска тест подделать не может, поэтому измерение сделано швом: `Resource(space_probe=...)`, в тестах `lambda root: (1_000_000, 100_000)`, и девяносто процентов наступают мгновенно и ровно тогда, когда нужно. А вот переносимость проверяется только **частично**, и это тот редкий случай, когда о границе надо сказать вслух: компиляция под Windows проверяется здесь и сейчас, поведение `LockFileEx` и `GetDiskFreeSpaceExW` — нет. См. «Что здесь не проверено».

## Что нужно знать заранее

- **Урок 12** — бакеты, `buckets_under`, `subsystems_under`: то, из чего ресурс узнаёт, что у него лежит.
- **Урок 13** — индекс событий: ресурс его держит и сообщает ему об удалениях.
- **Урок 4** — heartbeat: у ресурса он свой, под своим префиксом.
- **Урок 2** — `FileVariables` и сериализация записи блокировкой файла `<root>/lock`.
- **Урок 11** — `register_constraint`: та же дверь «код под именем», что откроется здесь; и предпочтение против фильтра — тот же ход мысли повторится в ступенях освобождения.

## Чему вы научитесь

1. Говорить, почему у ресурса нет контроллера, и что сломалось бы, если бы был.
2. Хранить по правилу каждой подсистемы, не зная ни одной из них.
3. Заменять карту соседей правилом и объяснять, что при этом упрощается.
4. Копировать только закрытые данные и говорить, что именно остаётся незащищённым.
5. Возвращать данные владельцу и давать подсистемам переиндексировать вернувшееся.
6. Пускать чужие проходы в свой таймер, не узнав о них ничего.
7. Отличать ретенцию от ватерлинии и говорить, почему одна — обещание, а другая — предохранитель.
8. Мерить свободное место так, чтобы ответ не зависел от размера дерева и не врал про чужие данные на том же томе.
9. Выбирать зазор между отметками в единицах притока, а не в процентах.
10. Отдавать решение «что удалить» подсистеме, оставляя платформе «сколько».
11. Объяснять, почему честная недостача лучше тихого удаления, и как её видит оператор.
12. Отличать две формы отказа переносимости и подбирать тест под форму, а не под симптом.
13. Держать различие ОС в **одном** месте, а не в ветвлении у каждого вызова.
14. Проверять, что стандартная библиотека уже сделала шов за вас, прежде чем писать свой.
15. Звать функцию Windows без единой зависимости — и понимать, когда так делать нельзя.
16. Отделять «собирается» от «работает» и писать это в документе, а не надеяться.

---

## Шаг 1 — Что ресурс знает

```
    <root>/<subsystem>/<unit>/e<epoch>/...          each subsystem's tree: its buckets, and whatever else it
                                                    keeps beside them (a scan's progress, say — its own)
    <root>/.mirror/<server>/<subsystem>/<unit>/...  copies of another server's closed buckets (the knob)

    platform/resources/<server>/heartbeat   {server, ts, url, usage, units, mirrors}
    platform/mirror                         the knob: {enabled, copies}
    <sub>/retention, <sub>/retention/<unit> {days}: each subsystem's policy, written by ITS controller
```

Форма — и ничего о содержании. Ресурс знает, что подсистемы кладут своё под своим именем, что внутри — единицы, эпохи и бакеты (урок 12), и что рядом бывает что-то ещё, чего он не трогает. В М10B рядом с бакетами лежит, например, прогресс скана (`detjob/<job>/progress.jsonl`); ресурс его не понимает и не должен. Видео на этом дереве нет вовсе: регистратор пишет его в тома ObjectStorage через демон `obsd` на хосте (М10B, уроки 6–8).

Префикс у него **свой**, платформенный: `platform/resources/<сервер>`, не `<подсистема>/…`. Ресурс не принадлежит подсистеме — он принадлежит серверу, и на одном ресурсе живут все.

И сразу — строка про сроки хранения, в которой видна вся конструкция: `<sub>/retention/<unit> {days}`, **написанная контроллером этой подсистемы**. Ресурс её читает. Он не знает, откуда взялось число и что оно значит для подсистемы, — он знает, что для этой единицы столько дней.

## Шаг 2 — Срок хранения

```python
def retention_days(vars_, subsystem: str, unit: str, default: float = 365.0) -> float:
    """The unit's days if its subsystem set them, else the subsystem's, else a year."""
    for path in (f"{subsystem}/retention/{unit}", f"{subsystem}/retention"):
        items, _ = vars_.get(path)
        if items and "days" in items:
            return float(items["days"])
    return default
```

В настоящем коде у функции есть вторая ветка — для **дерева тревог** (урок 12). `vms.alarms/<единица>` живёт по своей цепочке: `vms/alarms_retention/<единица>`, потом `vms/alarms_retention`, потом **три года** (`ALARM_DAYS = 1095`). Три года достаются и подсистеме, у которой своей строки нет: тревога регистратора `archive.shallow` лежит в `rec.alarms/…` и хранится столько же. Тот же срок у журнала `audit` — записи о том, кто что удалил и кому что выдали (урок 15): она нужна не меньше, чем тревоги удалённой камеры.

Побочная польза: срок наблюдений теперь можно уменьшать, не теряя тревог. Год статистики драйвера хранился только потому, что тревоги лежали в тех же бакетах.

Три уровня, от частного к общему. Строка этой единицы — производная строка из урока 9, написанная контроллером подсистемы. Строка подсистемы — умолчание для всех её единиц. И год, если не сказано ничего.

Год как последнее умолчание — выбор в пользу **сохранения**. Ошибка в конфигурации приведёт к тому, что данные проживут дольше нужного (дорого, но поправимо), а не к тому, что они исчезнут (непоправимо). То же соображение, что и с удалением строк в уроке 10: пометить, а не стереть.

Этот поиск и есть весь язык, на котором ресурс разговаривает с подсистемами о хранении. Ни регистрации, ни схемы, ни согласования — одна строка в известном месте.

### Одно исключение: записи консоли — пол, а не настройка

У консоли тоже есть бакет — `console/<instance>/`, куда уходят отметки оператора (урок 15, шаг 9). По общему правилу он подметался бы своими днями, и это единственное место, где общее правило неверно.

Причина — в **односторонней ссылке**. Запись оператора ссылается на события: отметка называет единицу, квитанция тревоги (когда она появится) назовёт тревогу. Обратной ссылки нет. Отсюда асимметрия:

- запись, пережившая то, на что ссылается, — безвредный мусор;
- событие, пережившее запись **о себе**, тихо возвращается в состояние «никто не ответил».

Второе и происходило бы: камера с двухлетним сроком, консоль с годовым — и через год строка «принято, дежурный Анна» исчезает, а тревога остаётся, выглядя непринятой. Заметить это можно только в тот день, когда записи не хватает, то есть при разборе инцидента.

```python
def console_floor(days_of: dict[tuple[str, str], float]) -> float:
    others = [d for (sub, _), d in days_of.items() if sub != CONSOLE]
    return max(others) if others else 0.0
```

Дни консоли становятся **полом**: что бы кто ни хранил дольше всех, её записи хранятся не меньше. Стоит это почти ничего — оператор пишет несколько строк в день против тысяч у воркера, — и это тот редкий случай, когда правило вводят **раньше** механизма, который оно защищает: квитанций ещё нет, а порядок хранения для них уже верный. Почему решено именно так и что будет, когда квитанции появятся, — в [`СОСТОЯНИЕ-ТРЕВОГИ.md`](../СОСТОЯНИЕ-ТРЕВОГИ.md).

## Шаг 3 — Правило вместо карты

```python
def peers_of(server: str, live: list[str], copies: int) -> list[str]:
    """The rule that replaces a map: the next `copies` live resources after mine, in sorted order."""
    others = sorted(s for s in live if s != server)
    if not others:
        return []
    after = [s for s in others if s > server] + [s for s in others if s < server]
    return after[:copies]
```

Соседи — это следующие `copies` живых ресурсов после моего, в отсортированном порядке, по кольцу. `srv-a` кладёт копии на `srv-b`, `srv-b` на `srv-c`, `srv-c` обратно на `srv-a`.

Docstring называет суть: **правило, заменяющее карту.** Альтернатива — таблица «кто кому сосед», которую кто-то поддерживает: её надо создать при добавлении сервера, поправить при удалении, согласовать между всеми и восстановить после сбоя. Правило не надо поддерживать: каждый вычисляет его сам из списка живых, и все вычисляют одинаково, потому что сортировка одна.

Из этого получается ещё одно свойство, за которое не пришлось платить. Сервер выбыл — соседи пересчитались сами: тот, кто клал ему копии, на следующем проходе положит их следующему по кольцу. Сервер вернулся — вернулся и в кольцо. Никто ничего не перенастраивал.

`live` — не «все известные», а именно живые (по возрасту heartbeat'а). Класть копии на молчащий сервер бессмысленно.

## Шаг 4 — Heartbeat ресурса

```python
    def heartbeat(self) -> dict:
        hb = {"server": self.server, "ts": self.wall(), "url": self.url, "usage": self.usage(), "units": self.units(),
              "mirrors": {s: len(mirrored_buckets(self.root, s, self.bucket_seconds)) for s in mirrored_servers(self.root)}}
        self.objects.put(f"{RESOURCES}/{self.server}/heartbeat", json.dumps(hb).encode())
        return hb
```

Шесть полей, и каждое кто-то читает.

`server`, `ts` — кто и когда; отсюда `resource_state` контроллера из урока 11 берёт свои три состояния. `url` — куда стучаться: по нему консоль спрашивает события, а соседи кладут копии. **Адрес ресурса нигде не настраивается — он объявляется.**

`usage` — сколько занято байт: страница показывает, оператор смотрит. `units` — какие подсистемы и единицы здесь лежат (`subsystems_under` из урока 12); это же поле в М11 отвечает на вопрос, у кого искать записи камеры 7.

`mirrors` — сколько чужих копий я держу, по серверам. Ради этого поля и существует шаг 6: владелец, вернувшийся с пустым диском, ищет по нему, у кого забрать своё.

## Шаг 5 — Зеркало

```python
    def mirror(self) -> dict:
        """The knob. Every CLOSED bucket on this server — any subsystem — is
        copied to the next live resource(s) after it, exactly once each (the
        peer says what it already holds), by the server that owns it."""
        knob = mirror_settings(self.vars)
        if not knob["enabled"]:
            return {"enabled": False, "mirrored": 0, "peers": []}
        live = {s: hb for s, hb in self.live_resources().items() if hb.get("url")}   # a peer that says no address takes nothing
        peers = peers_of(self.server, list(live), knob["copies"])
        n, closed, failed = 0, None, []
        for peer in peers:
            url = live[peer]["url"]
            try:
                have = {b.path for b in self.peers.mirrored(url, self.server)}
            except Exception as e:                           # noqa: BLE001 — that peer's trouble, not the next one's
                self.mirror_failed += 1
                failed.append(peer)
                log.warning("%s: %s did not say what it holds (%s): nothing copied to it this pass", self.server, peer, e)
                continue
            self._progressed()
            if closed is None:
                closed = self.closed_buckets()               # the walk once a pass, not once per peer
            fails = 0
            for b in closed:
                if b.path in have or b.path in self._too_big:
                    continue
                if fails >= PEER_FAILS:
                    break                                    # its door is down: the rest on a later pass
                try:
                    with open(self.path_of(b.path), "rb") as f:
                        size = os.fstat(f.fileno()).st_size
                        if size > MIRROR_MAX:
                            raise _TooBig(f"{size} bytes, over the {MIRROR_MAX} a peer takes")
                        put_file = getattr(self.peers, "put_file", None)     # in pieces, never the bucket whole (the seventh pass)
                        if put_file is not None:
                            put_file(url, self.server, b.path, f, size)
                        else:
                            self.peers.put(url, self.server, b.path, f.read())
                except FileNotFoundError:
                    continue                                 # swept between the walk and here: nothing to copy
                except Exception as e:                       # noqa: BLE001
                    if isinstance(e, _TooBig) or getattr(e, "code", None) == 413:
                        self._too_big.add(b.path)
                        self.mirror_too_big += 1
                        log.error("%s: %s is too big to mirror (%s): it is copied nowhere — the buckets after it are",
                                  self.server, b.path, e)
                        continue
                    fails += 1
                    self.mirror_failed += 1
                    log.warning("%s: %s did not take %s (%s)", self.server, peer, b.path, e)
                    if fails == PEER_FAILS:
                        failed.append(peer)
                        log.warning("%s: %s refused %d buckets in a row: the rest go to it on a later pass",
                                    self.server, peer, PEER_FAILS)
                    continue
                fails = 0
                n += 1
                # Each copy the peer took is progress (the review's fourth pass): the FIRST mirroring of a server
                # sends a year of buckets, and without a mark per bucket a mirror that moved the whole time was
                # "stuck" to the pulse after four `lost_after` — the resource silent, its recordings moved.
                self._progressed()
        self.mirror_peers_failed = failed
        return {"enabled": True, "mirrored": n, "peers": peers, **({"peers_failed": failed} if failed else {})}
```

**Один сосед и одно ведро — их собственная беда, а не всего зеркала** (восьмое ревью, часть 4). Раньше зеркало целиком было одной частью прохода в одном `try`. Сосед, чья дверь отказала в списке, бросал исключение из цикла — и второму соседу не копировалось ничего. Ведро больше `MIRROR_MAX` получало 413 на каждом проходе, и ни одно ведро после него не уезжало никуда, никогда. Теперь сосед, не ответивший списком, пропускается до следующего прохода и считается (`mirror_failed`). Ведро больше `MIRROR_MAX` не отправляется вовсе, а ведро, на которое сосед ответил 413, не отправляется снова; оба считаются (`mirror_too_big`), и ведра после них уходят. Любой другой отказ на ведро считается, и идёт следующее ведро; `PEER_FAILS` (3) отказов подряд оставляют соседа до следующего прохода — его дверь лежит, и год вёдер не должен превращаться в год таймаутов. Повтор зеркала — это сам проход: недоставленное ведро сосед по-прежнему не называет в своём списке, и оно уйдёт через десять минут. Счётчики и соседи, которым не всё доставлено, — в heartbeat'е ресурса (`mirror`) и на `/metrics` (`w2c_resource_mirror_failures_total`, `w2c_resource_mirror_too_big_total`). Тест: `test_row_reader.py::test_a_mirror_copies_to_every_peer_past_one_that_refuses_and_past_a_bucket_too_big_for_any`.

**Бакет не держится в памяти целиком ни с одной стороны зеркала.** Первая версия отправляла `f.read()`: шестьдесят мегабайт шторма — одним куском, по разу на бакет, а `restore` писал на диск то, что `PeerClient.get` прочитал целиком (седьмое ревью, рядом с находкой «ресурс отдаёт бакет целиком»). Теперь у клиента зеркала два метода. `put_file` отдаёт соединению открытый файл с его длиной (`Content-Length`), и `http.client` шлёт файл блоками. `get_into` пишет ответ в файл кусками по `PIECE` (64 КиБ) и сверяет с длиной, которую назвал сосед: ответ, оборвавшийся раньше, — ошибка, а не бакет поменьше, и половины копии на диске не остаётся. Клиент, которого подставляет тест, может иметь только `put` и `get`: тогда идёт прежний путь. Тест: `test_console_load.py::test_the_mirror_sends_and_takes_back_a_bucket_in_pieces_never_whole` — два настоящих ресурса по HTTP, бакет в 16 МБ туда и обратно байт в байт, а пик памяти Python на каждой стороне меньше 4 МБ.

Выключено по умолчанию: ручка `platform/mirror`, которую ставит инсталлятор. Включено — каждый сосед спрашивается, что у него уже есть, и досылается недостающее.

**`copies`, которое не разбирается, — одна копия.** `mirror_settings` разбирал `copies` голым `int`, и `copies: "two"` бросал исключение из зеркала на каждом проходе: зеркало, которое оператор включил, не копировало ничего (седьмое ревью, рядом с ватерлинией). `enabled` — слово, сравниваемое со словом, оно читается всегда. Число теперь идёт через общий читатель строк (урок 8, шаг 5):

```python
def mirror_settings(vars_) -> dict:
    items, _ = vars_.get(MIRROR_KEY)
    return {"enabled": bool(items) and items.get("enabled") == "true",
            "copies": MIRROR.read(MIRROR_KEY, lambda: int(finite((items or {}).get("copies", 1))), 1)}
```

Не разобралось — одна копия: меньше, чем попросил выключатель, который прочитан, быть не может. Строка считается один раз, пока снова не станет читаться, и один раз попадает в лог. Тест: `test_row_reader.py::test_a_mirror_whose_copies_do_not_parse_mirrors_to_one_peer`.

**Сосед — источник истины о том, что у него лежит.** Не отметка «я это отправлял», хранимая у отправителя: она разошлась бы при потере диска у получателя, и копии считались бы существующими, не существуя. Спросить — это один запрос на проход, и он делает операцию идемпотентной: тест показывает два скопированных бакета на первом проходе и ноль на втором.

```python
    def closed_buckets(self) -> list[Bucket]:
        out = []
        for sub, units in self.units().items():
            for unit in units:
                self._progressed()
                for path in self.volumes.values():
                    out += [b for b in bucket_names_under(path, sub, unit, self.bucket_seconds, self._progressed)
                            if b.end <= self.wall()]
        return out
```

Обход — **по именам**: зеркалу нужны только пути закрытых бакетов, и ни один файл здесь не открывается (`bucket_names_under`, а не `buckets_under`, который разбирает каждую строку). И отметка прогресса — на каждое ведро (ниже).

**Только закрытые** — те, чей промежуток кончился. Открытый бакет ещё дописывается (урок 12), и копировать его пришлось бы снова и снова, каждый раз целиком.

Отсюда честная цена, названная своим числом: **в худшем случае теряется один промежуток.** Десять минут наблюдений сервера, который исчез, не успев закрыть текущий бакет. Это RPO зеркала, и он записан в проектной записке именно так: не «данные защищены», а «теряется до десяти минут».

Заметьте, чего в методе нет: ни слова о подсистемах. Копируется **любой** бакет любой подсистемы — тест на это и построен: два ресурса, бакеты подсистем, которых не существует, зеркалируются и восстанавливаются, и слово *camera* в файле не встречается ни разу.

## Шаг 6 — Возвращение домой

```python
    def restore(self) -> dict:
        """The reverse, run by the owner: pull my buckets from whoever holds
        copies, then let each subsystem's hook re-index what came back."""
        with self._pulsing():
            try:
                return self._restore()
            except Exception:
                wait = self._restore_later()
                log.warning("%s: restore did not run through: tried again in %.0f s", self.server, wait)
                raise

    def _restore(self) -> dict:
        pulled, left, failed, peers_failed = 0, 0, 0, []
        now, seen = self.wall(), resources_seen(self.objects)
        live = {s: hb for s, hb in seen.items()
                if s != self.server and is_live("platform", float(hb["ts"]), now, self.lost_after)}
        for peer, hb in live.items():
            if peer in self._restored_from or not self._holds_mine(peer, hb):
                continue
            try:
                listed = self.peers.mirrored(hb["url"], self.server)
            except Exception as e:                           # noqa: BLE001 — that peer's trouble, not the next one's
                failed += 1
                peers_failed.append(peer)
                log.warning("%s: %s did not list the copies it holds of this server (%s): asked again later",
                            self.server, peer, e)
                continue
            self._progressed()
            fails, left_before = 0, left
            for path in sorted(str(b.path) for b in listed):
                self._progressed()
                if not _bucket_path(path):
                    PEER_LINES.garbled(f"platform/restore/{peer}#{path}", "not a bucket's path")
                    continue                                 # never written: it could name a place outside the tree
                dest = self.path_of(path)              # back onto the volume that held it, or the emptiest
                if os.path.exists(dest):
                    continue
                if fails >= PEER_FAILS:
                    left += 1
                    continue                                 # this peer is left for this try: counted, asked again
                try:
                    self._pull(hb["url"], path, dest)
                except Exception as e:                       # noqa: BLE001
                    fails += 1
                    failed += 1
                    left += 1
                    log.warning("%s: %s did not give back %s (%s): asked again later", self.server, peer, path, e)
                    if fails == PEER_FAILS:
                        peers_failed.append(peer)
                    continue
                fails = 0
                pulled += 1
                self._progressed()
            if left == left_before:
                self._restored_from.add(peer)                # all it listed is here: not asked again
        self.restore_failed += failed
        self.restore_left, self.restore_peers_failed = left, peers_failed
        if not left and not peers_failed and (live or not any(s != self.server for s in seen)):
            self._restore_ok = True
        if left or peers_failed:
            wait = self._restore_later()
            log.warning("%s: restore left %d buckets with peers%s: tried again in %.0f s", self.server, left,
                        f" ({', '.join(peers_failed)} did not answer whole)" if peers_failed else "", wait)
        elif not self._restore_ok:
            wait = self._restore_later()
            log.warning("%s: no other resource is live to give back what it holds of this server: asked again in "
                        "%.0f s", self.server, wait)
        else:
            self._restore_tries, self._restore_next = 0, self.clock() + RESTORE_RETRY_MAX   # the next look for a late peer
        hooks = {sub: _call_hook(h.pass_, self.wall(), progressed=self._progressed)
                 for sub, h in self.hooks.items()} if pulled else {}
        return {"pulled": pulled,
                **({"left": left, "failed": failed} if left or failed else {}),
                **({"peers_failed": peers_failed} if peers_failed else {}),
                **{f"{s}.{k}": v for s, r in hooks.items() for k, v in r.items()}}

    def _holds_mine(self, peer: str, hb: dict) -> bool:
        return peer != self.server and self.server in hb.get("mirrors", {}) and bool(hb.get("url"))

    def _restore_later(self) -> float:
        wait = min(RESTORE_RETRY_MAX, RESTORE_RETRY * 2 ** min(self._restore_tries, 10))
        self._restore_tries += 1
        self._restore_next = self.clock() + wait
        return wait

    def _pull(self, url: str, path: str, dest: str) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        get_into = getattr(self.peers, "get_into", None)      # in pieces, never the bucket whole (the seventh pass)
        try:
            with open(dest + ".tmp", "wb") as f:
                if get_into is not None:
                    get_into(url, self.server, path, f)
                else:
                    f.write(self.peers.get(url, self.server, path))
        except BaseException:
            with suppress(FileNotFoundError):
                os.remove(dest + ".tmp")
            raise
        os.replace(dest + ".tmp", dest)

    def restore_due(self) -> bool:
        if self.clock() < self._restore_next:
            return False
        if not self._restore_ok or self.restore_left or self.restore_peers_failed:
            return True
        self._restore_next = self.clock() + RESTORE_RETRY_MAX     # the next look, whatever this one finds or raises
        return any(peer not in self._restored_from and self._holds_mine(peer, hb)
                   for peer, hb in self.live_resources().items())
```

**Один сосед и одно ведро — их беда, а то, что не вернулось, спрашивается снова** (восьмое ревью, часть 4). `restore` шёл один раз, при старте, в одном `try`. Сосед с живым heartbeat'ом и отказывающей дверью возвращал 0 вёдер из 20, обрыв на четвёртом — 3 из 20. И больше никто не спрашивал, а копии тем временем старели у соседей и выметались там. Теперь сосед, не ответивший списком, пропускается, и спрашивается следующий. Ведро, которое не пришло, считается, и тянется следующее; после `PEER_FAILS` неудач подряд сосед оставлен до следующей попытки. Путь, который сосед называет, но который не путь ведра (`..`, не `.events.jsonl`), не пишется никогда: он мог бы указать за пределы дерева (`_bucket_path`). То, что известно лежащим у соседей и не вернувшимся (`left`), и сосед, не давший списка, делают восстановление снова должным (`restore_due`): через `RESTORE_RETRY` (10 с), с удвоением до `RESTORE_RETRY_MAX` (600 с). Спрашивает цикл ресурса, каждый свой оборот (`vms/__main__.py`, М11 — `cluster/__main__.py`), пока не останется ничего. Состояние — в heartbeat'е (`restore`: `left`, `failed`, `peers_failed`, `next_in`) и на `/metrics` (`w2c_resource_restore_left`, `w2c_resource_restore_failures_total`). `.tmp` удаляется при любой неудаче, а `.tmp`, который не успел появиться, больше не прячет настоящую причину за своим `FileNotFoundError` (`_pull`). Тест: `test_row_reader.py::test_a_restore_takes_what_every_peer_gives_and_asks_again_for_what_did_not_come` — 20 вёдер, одно не приходит: вернулось 19, сосед с отказавшим списком не помешал, через паузу недостающее ведро спрошено снова и вернулось, остальные второй раз не спрашивались.

**Ответ соседа — только 200 и только до предела.** Ответ, который не 200 (204, 206), бакетом не пишется (`_ok`); 4xx и 5xx `urlopen` и раньше превращал в исключение. Список `/mirrored` читается не больше `LISTING_MAX` (64 МиБ), копия — не больше `MIRROR_MAX`, и строка списка, которая не разбирается, — беда этой строки: она пропускается и считается (`PEER_LINES`), а остальной список стоит. Тест: `test_row_reader.py::test_the_peer_client_writes_only_a_whole_200_as_a_bucket_and_skips_a_garbled_line_of_a_listing`.

**Восстановление не сделано, пока хоть одна попытка не прошла с кем-то, кого можно спросить** (девятое ревью, major, воспроизведено пробой). Восьмое ревью сделало повтор, но должным `restore` становился только тогда, когда что-то осталось у соседа, до которого он достучался. Попытка, которая упала целиком (хранилище не ответило при старте с новым диском), и попытка, не заставшая ни одного живого соседа (после общего отключения питания сервер встал раньше соседей), не оставляли ничего известного — и больше не повторялись. За 20 минут вернулось 0 вёдер из 20, а `w2c_resource_restore_left` показывал 0. Теперь `_restore_ok` становится истиной только после попытки без ошибок, в которой был живой сосед — или не нашлось ни одного другого ресурса, когда-либо писавшего heartbeat: одному серверу копии держать некому, и его восстановление сделано с первой попытки, а не повторяется всю жизнь коробки. Пока не сделано, `restore_due` истинно после паузы (`_restore_later`: те же 10 с с удвоением до 600 с), а в heartbeat'е — `restore: {done: false, left: -1}`; −1 значит «не известно»: ни один сосед не спрошен. Попытка, бросившая исключение, ставит паузу до того, как исключение уходит из `restore`. И сосед, который появился позже — лежал во время восстановления, пока другой сосед был жив, — спрашивается, когда его увидят: сделанное восстановление раз в `RESTORE_RETRY_MAX` читает heartbeat'ы и ищет живого соседа, который держит копии этого сервера и ещё их не отдал. Сосед, отдавший всё, что назвал (`_restored_from`), больше не спрашивается: всё, что у него появилось потом, пришло от этого же сервера. Тесты: `test_row_reader.py::test_a_restore_that_met_no_live_peer_or_raised_whole_is_asked_again_and_a_late_peer_is_asked` (0 вёдер, пока соседи молчат; 10 от первого соседа, когда он встал; 10 от второго, когда встал он, — первый второй раз не спрошен; хранилище, не ответившее при старте, — повтор после паузы), `test_one_server_alone_is_restored_once_and_not_asked_again_for_ever`.

**Пауза не переполняется** (девятое ревью, minor). `RESTORE_RETRY * 2 ** tries` на 1024-й попытке больше любого `float`, и `OverflowError` вылетал раньше, чем ставилась пауза, — дальше `restore` шёл каждые 10 секунд с трейсом. Показатель теперь ограничен: `2 ** min(self._restore_tries, 10)`. Тест: `test_row_reader.py::test_the_restores_pause_does_not_overflow_after_a_thousand_tries`.

**Целым считается только ответ с рамкой** (девятое ревью, minor, и соседний путь). Ответ без длины и без чанков — прокси, снявший рамку, — кончается там, где кончилось соединение. Дверь соседа, упавшая на половине, давала бакет покороче, и он записывался навсегда; `Content-Length: ten` бросал голый `ValueError` уже после того, как тело записано. Теперь `get_into` спрашивает `framed` (тот же вопрос, что задаёт консоль дверям регистраторов) до первого байта, берёт длину у самого `http.client` — число или ничего — и превращает оборванные чанки в `IOError`: ведро спрашивается снова. Тот же читатель (`_whole`) стоит на списке `/mirrored` и на `get`/`get_raw`: список, оборванный на середине, выглядел бы соседом, у которого меньше копий, а `restore` теперь считает соседа, отдавшего всё названное, отработанным. Тест: `test_row_reader.py::test_the_peer_client_takes_no_answer_without_a_frame_and_no_length_that_is_not_a_number`.

**Возвращение домой — под тем же пульсом, что проход.** `restore` идёт при старте процесса, на том же потоке, что heartbeat, до цикла. Седьмое ревью посчитало цену: замена диска, 2000 вёдер по 50 мс каждое — 100 секунд без heartbeat'а (часть 1, M4). Всё это время ресурс для индекса событий молчит, окно считается неполным, и автоматика держит курсор. Консоль тоже показывает ресурс молчащим, хотя его дверь отвечает. Теперь пульс прохода (шаг 7) вынесен в `_pulsing`, и `restore` бьётся под ним так же, как `pass_`. Отметка прогресса ставится на каждый список соседа и на каждое ведро, вытянутое или уже лежащее на месте. Восстановление, которое движется, держит пульс. Застрявшее на соседе, который ничего не отдаёт, пульс останавливает. Тест: `test_row_reader.py::test_restore_beats_under_the_same_pulse_as_the_pass` — шесть вёдер по 30 секунд часов ящика, heartbeat свежий во время каждого.

Обратная операция, и запускает её **владелец при старте**. Сценарий: сервер вернулся после замены диска, его дерево пусто, а копии его закрытых бакетов лежат у соседей.

Кого спрашивать — видно из чужих heartbeat'ов: `self.server not in hb["mirrors"]` пропускает тех, у кого моих копий нет. Что уже есть — не тянется (`if os.path.exists`). Запись — через `.tmp` и `os.replace`, потому что тянется по сети и может оборваться (урок 4).

Последняя строка — то, ради чего у метода вообще есть возвращаемое значение сложнее числа. Если что-то вернулось, **прогоняются все зарегистрированные проходы подсистем**. Причина: подсистема могла вести свой индекс рядом с бакетами, и вернувшиеся файлы в нём не значатся. VMS в М10B своего индекса на дереве ресурса не ведёт и проходов не регистрирует, так что для неё эта строка ничего не делает; дверь оставлена для подсистемы, у которой такой индекс есть. Ресурс не знает, что именно делают проходы, — он знает, что после возврата данных им надо дать посмотреть.

Никто никем не управляет: владелец сам решил, что ему чего-то не хватает, соседи сами держат то, что держат, и спросили их по правилу.

## Шаг 7 — Чужие проходы

```python
    def register(self, subsystem: str, hook) -> None:
        self.hooks[subsystem] = hook
```

Одна строка, и это третья дверь «код под именем» в курсе — после `register_constraint` (урок 11) и подсистем вообще. Объект должен уметь `pass_(now) -> dict`; больше от него не требуется ничего.

В курсе эту дверь открывают тесты: `res.register("counter", hook)` — подсистема, которая только считает тики и умеет отдать несколько (`test_lesson1_platform.py::test_the_watermark_asks_and_never_deletes`). Ресурс про тики не знает; он знает, что в его таймере есть чужая функция под именем `counter`.

VMS этой дверью не пользуется. Её видео лежит не на дереве ресурса, а в томах ObjectStorage, и каждый том — кольцо, отформатированное на свою квоту: оно само отдаёт старейшие минуты и не растёт за свой размер (`vms/resource.py`). Чинить, удалять по сроку и освобождать на диске ресурса VMS нечего. Добавляет она к ресурсу одно — предикат `kept`, о нём ниже.

```python
    def pass_(self) -> dict:
        out = {}
        for sub, h in self.hooks.items():                    # a subsystem's own pass first
            out.update({f"{sub}.{k}": v for k, v in h.pass_(self.wall()).items()})
        out["removed"] = self.retain()
        out.update(self.mirror())
        return out
```

Тело таймера, и порядок в нём — решение.

**Проход сам несёт свой пульс.** Он идёт в том же потоке, что heartbeat, и читает каждый бакет, который хранит. На годовом архиве проход длится дольше `lost_after`: ресурс считается молчащим, и контроллер уводит записи со здорового сервера (ревью платформы, блокер 6). Второй поток, зовущий `heartbeat()`, гонялся бы с проходом за то самое состояние, которое heartbeat читает, — кэш занятости, тома. Поэтому, пока проход идёт, раз в десять секунд (`PULSE_SECONDS`) уходит **последний** heartbeat со свежим временем: байты, которые уже были опубликованы, и ничего из того, что проход меняет (решение продукта, обратная связь BE).

**Пульс — по прогрессу, и одна ошибка его не убивает.** Первая версия предела мерила общее время прохода по настенным часам и умирала на первом исключении записи пульса: хранилище моргнуло во время пятиминутного прохода — ресурс `silent`, и записи уводили с исправного сервера (третье ревью). Теперь каждый удар — в своём `try`, часы — монотонные (`Resource(clock=)`), а предел — 4 × `lost_after` **без прогресса**: обход `usage`, каждая единица в `retain` и каждая часть прохода отмечают прогресс (`_progressed`). Долгий проход, который идёт, бьётся сколько угодно; стоящий — замолкает. `usage()` — тоже часть прохода, исчезнувший файл пропускается (`FileNotFoundError`), а `part` ловит любое исключение. Тесты в `test_lesson10_events.py`.

**Прогресс отмечает каждая часть, а не только обход.** После третьего ревью прогресс отмечали обход бакетов и удаление по сроку — а зеркало, хуки подсистем и `relieve` нет: живая четырёхсекундная часть останавливала пульс, и первое зеркалирование года бакетов в М11 делало исправный ресурс молчащим (четвёртое ревью, воспроизведено запуском). Теперь `mirror` отмечает прогресс после списка каждого соседа и после каждого отправленного бакета, `relieve` — по каждому тому и после `free` каждой подсистемы, а хуки зовутся через `_call_hook`, который передаёт `progressed=` (и `volume=`), если хук его принимает. Сосед, повисший на одном бакете, по-прежнему останавливает пульс — так и задумано. Тест: `test_a_mirror_a_hook_and_relieve_that_keep_moving_keep_the_pulse_and_one_that_hangs_stops_it`.

**И отметка — на каждое ведро, а не на единицу.** После четвёртого ревью обход отмечал прогресс раз на единицу, а список закрытых бакетов в зеркале разбирал каждую строку каждого файла: 5000 вёдер по 300 строк шли 3,2 с при пределе 2 с, и ресурс выглядел молчащим; год камеры — 52 560 вёдер — на холодном HDD шёл бы дольше 180 с, и `redistribute` снимал бы записи с исправного сервера (пятое ревью). Теперь `bucket_names_under` зовёт `progressed` на каждый каталог и каждое ведро, `retain` отмечает каждое ведро в обоих обходах (свои бакеты и копии соседей), а зеркало обходит свои бакеты один раз за проход, а не на каждого соседа. Тест `test_a_walk_over_many_buckets_keeps_the_pulse_with_a_mark_per_bucket_and_opens_none_of_them`: 2000 вёдер на медленном диске при пределе 2 с — пульс жив, ни один файл не открыт.

**И на каждый файл, и на каждое удаление.** Пятое ревью закрыло обходы по именам, а две части рядом остались с прежним шагом. `usage()` ставил отметку раз на каталог — а все вёдра одной эпохи лежат в одном каталоге. Удаления в `retain` не отмечались вовсе: имена отмечались, пока строился список, а потом файлы уходили один за другим. По модели того же теста 2000 вёдер — это 399,8 с без отметки в `usage` и 371 с в `retain` при пределе 2 с (шестое ревью; первое число воспроизведено тестом до исправления). Теперь отметка стоит после каждого измеренного файла и после каждого удаления — своего ведра и копии соседа:

```python
    def usage(self, volume: str | None = None) -> int:
        roots = [self.volumes[volume]] if volume is not None else list(self.volumes.values())
        total = 0
        for root in roots:
            for d, _, files in os.walk(root):
                self._progressed()
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(d, f))
                    except FileNotFoundError:
                        continue
                    finally:
                        self._progressed()
        return total
```

```python
                    for b in bucket_names_under(path, sub, unit, self.bucket_seconds, self._progressed):
                        if b.end < self.wall() - days * 86400:
                            if kept is not None and kept(sub, unit, b.start, b.end):
                                continue                                # somebody said to keep it: past its days, and here
                            os.remove(os.path.join(path, b.path)); removed.append(b.path)
                            self._progressed()
```

Тест `test_lesson10_events.py::test_measuring_the_tree_and_removing_what_is_old_keep_the_pulse_with_a_mark_per_file`: 2000 своих вёдер и 2000 копий соседа, каждый `stat` и каждое удаление стоят десятую долю предела — пульс жив во всех трёх местах.

**Тот же вопрос — каждому циклу прохода.** Три раза подряд исправление закрывало названный обход и оставляло соседний, поэтому вот все циклы `pass_`, которые идут по файлам, вёдрам, строкам или удаляют:

| Цикл | По чему идёт | Отметка на элемент |
|---|---|---|
| хуки подсистем (`pass_`, `free`) | своё | получают `progressed` и зовут сами (четвёртое ревью) |
| `retain`: сроки единиц | строка хранилища на единицу | да (шестое; был один словарь без отметок) |
| `retain`: что удержано (`self.kept`) | строки хранилища | получает `progressed`, если принимает (шестое) |
| `retain`: свои вёдра | имена; удаления | да (пятое); да (шестое) |
| `retain`: строки журнала `events.removed` | запись на единицу | да (шестое) |
| `retain`: копии соседей | имена; удаления | да (пятое); да (шестое) |
| `usage` и `usage(том)` | каждый файл дерева | да (шестое; была отметка на каталог) |
| `relieve` | том; ответ каждой подсистемы | да (четвёртое) |
| `mirror` | список каждого соседа; каждое отправленное ведро | да (четвёртое) |
| `closed_buckets` | имена вёдер | да (пятое) |
| `index.forget` | память | не нужна |
| `units()` | один `listdir` на подсистему, `isdir` на единицу | нет: ограничен числом единиц, а не вёдер |

Чего отметки не закрывают. Один `os.walk` читает каталог одним списком — внутри листинга каталога в пятьдесят тысяч имён отметку поставить некуда. И всё, что вне `pass_` и `restore`, пульса не имеет вовсе: счёт копий в heartbeat'е (`mirrored_count`), двери `/buckets` и `/mirrored`. `restore` под пульсом с седьмого ревью (шаг 6), и его повторы тоже.

**Пульс не вечен.** Проход, застрявший на диске, который никогда не ответит, бился бы пульсом сколько угодно — ресурс `live`, числа замороженные. Через `PULSE_LIMIT` × `lost_after` (четыре срока) пульс прекращается, и ресурс становится тем, чем он есть, — молчащим; пока бьётся, в heartbeat есть `pass_seconds` — сколько проход уже идёт (второе ревью). Тест: `test_a_pass_longer_than_the_pulse_keeps_the_resources_heartbeat_fresh`.

**Сначала чужие проходы, потом своё хранение.** Причина в том, что чужой проход может добавить строки в свой индекс, а потом ресурс удалит файлы по сроку — и индекс окажется впереди файлов на один проход, что подсистема поправит на следующем. Обратный порядок дал бы худшее: подсистема проиндексировала бы файлы, которые прямо сейчас исчезли.

**Хранение перед зеркалом.** Не копировать то, что через секунду удалишь.

Результаты складываются в один словарь: ключи проходов с префиксом подсистемы (у тестового счётчика — `counter.ticks`), потом `removed`, `usage`, `space`, `mirrored`, `peers`. Это то, что уходит в лог раз в десять минут и оказывается первым, что читают при разборе.

```python
    def retain(self) -> int:
        removed = []
        for sub, units in self.units().items():
            for unit in units:
                days = retention_days(self.vars, sub, unit)
                for b in buckets_under(self.root, sub, unit, self.bucket_seconds):
                    if b.end < self.wall() - days * 86400:
                        os.remove(os.path.join(self.root, b.path)); removed.append(b.path)
        if removed and self.index is not None:
            self.index.forget(self.server, removed)                     # out of its cache with the file
        return len(removed)
```

**Проход говорит, что унёс.** Раньше — одно число в логе. Теперь по каждой единице строка `events.removed` в журнале (`audit/resource/…`, урок 15): чьи бакеты, сколько, за какой период, по какому сроку. Вопрос «куда делись события камеры 7 за март» получает ответ, а не догадку.

**Проход не читает то, что метёт.** В настоящем коде вместо `buckets_under` стоит `bucket_names_under`: тот же список, но из одних имён. Путь бакета говорит всё, что нужно политике, — чей он, какая эпоха, когда начался, — а конец равен началу плюс длина бакета. `buckets_under` ещё и открывает каждый файл, чтобы посчитать строки; это нужно маршруту `/buckets` и не нужно никому, кто удаляет. Проход хранения читал год архива, каждый раз, чтобы удалить файлы одного дня; heartbeat так же пересчитывал все зеркальные копии каждые десять секунд (ревью платформы; обратная связь, BI). Теперь ни тот, ни другой не открывает ни одного бакета.

**Срок, который не прочитать, — не ноль дней.** Сроки всех единиц читаются одним циклом, до первого удаления, и `retention_days` разбирает `days` голым `float`. Одна строка `<подсистема>/retention/<единица>` со словом вместо числа бросала исключение из всего `retain`: ничьи бакеты не удалялись, каждый проход (шестое ревью, обход соседей битой строки). Теперь такая единица в этом проходе не метётся — её срок считается бесконечным, — она названа в `retention_garbled` и в логе, а остальные метутся по своим срокам; то же для копий соседей. Тест: `test_garbled_rows.py::test_one_units_garbled_retention_row_keeps_that_units_buckets_and_the_rest_are_swept`.

**`nan`, `inf` и `-1` — тоже не число дней** (девятое ревью: команда продукта нашла это у себя, и в курсе было то же). `float("nan")` — число, и слово-проверка его пропускала: `nan` дней не проходили ни одного сравнения, ничего не удалялось и ничего не говорилось. `-1` удалял все бакеты единицы, текущий тоже, а `inf` не пишет ни один контроллер. Теперь `retention_days` пропускает `days` через `_days_of`: только конечное число не меньше нуля, иначе исключение. `_days` ловит всё, что бросает разбор (`PARSE_ERRORS`: строка-список без `.get` тоже), держит бакеты единицы, считает строку один раз, пока она снова не станет читаться (`RETENTION`, `rows_garbled.retention` в heartbeat'е и на `/metrics`), и называет единицу в heartbeat'е (`retention_garbled`). Раньше здесь было предупреждение в логе на каждом проходе и ни одного счётчика. `days: 0` остаётся тем, чем был, — сроком удалённой единицы, и метёт. Тест: `test_garbled_rows.py::test_days_that_are_no_number_of_days_keep_the_units_buckets_and_nought_still_sweeps` — `"ten"`, `"nan"`, `"inf"`, `"-1"`, `"-inf"` держат, `"0"` метёт, починенная строка метётся по своим дням.

**Копии тоже стареют.** `.mirror/<сервер>/…` не входит ни в один обход: `units()` пропускает скрытые каталоги, и намеренно — копия не данные этого сервера. Поэтому при включённом зеркале каталог только рос. Теперь `retain` проходит и по нему: копия живёт столько дней, сколько её единица, как оригинал, и метка удержания защищает её так же. Удаляется она на час позже оригинала (`MIRROR_GRACE`): у двух серверов двое часов, и копию, убранную чуть раньше оригинала, владелец на следующем проходе прислал бы снова.

В настоящем коде перед `os.remove` стоит ещё одна проверка: `if kept is not None and kept(sub, unit, b.start, b.end): continue`. Ресурс не знает, что такое «сохранить»; тот, кто его собрал, может положить в `self.kept` функцию, которая раз в проход возвращает такой предикат. Зовётся она через `_call_hook(self.kept, progressed=self._progressed)`: чтобы ответить, она читает хранилище строка за строкой, и если принимает `progressed` — отмечает каждую (шестое ревью; М10B, урок 11). Если она бросает исключение, проход падает и ничего не удаляет: не знать, что оставить, — не то же, что «оставлять нечего». Зачем это нужно, показывает М10B, урок 18: удаление единицы превращает её срок в `{days: 0}`, и без предиката вместе с ней уходили бы события, которые кто-то отметил.

**Поэтому предикат не бросает из-за одной строки.** Правило «бросила — не удаляем ничего» верно для молчащего хранилища и неверно для одной испорченной метки. У VMS метка `since: "yesterday"` у камеры 9 бросала исключение из её предиката. Три прохода подряд `retain` стоял в ошибках, и у камер 7 и 8 осталось 20 из 20 старых вёдер — диск заполнялся (седьмое ревью, часть 2, воспроизведено запуском). Теперь метку, которая не разбирается, предикат читает как удержание её камеры настолько, насколько метка читается: граница, которая разбирается, остаётся, а потерянная открыта в свою сторону (восьмое ревью уточнило правило седьмого, по которому камера держалась целиком при любом битом поле). Остальные камеры метутся по своим срокам, а строка считается и попадает в heartbeat ресурса (`rows_garbled`) и на `/metrics` консоли (`w2c_resource_rows_garbled{server,table}`; восьмое ревью, minor: раньше только в heartbeat'е). Как это устроено у VMS — М10B, урок 11. Тесты: `test_row_reader.py::test_one_garbled_keep_holds_its_camera_whole_and_the_others_are_swept`, `test_row_reader.py::test_a_garbled_keep_holds_its_camera_as_far_as_it_reads_and_nothing_of_the_units_of_no_camera`.

По подсистемам и единицам, у каждой свой срок. Удаляются **только файлы бакетов**: то, что подсистема хранит рядом (прогресс скана, свой индекс), — её забота, и удаляет она это в своём проходе, по своему сроку. Разделение записано в docstring: *files only; a subsystem that indexes its buckets drops the lines in its own pass.*

И последняя пара строк — стык с уроком 13: индекс узнаёт об удалении и выбрасывает бакеты из кэша. Правильность от этого не зависит — запрос делает `stat` каждому файлу, который читает, — но память да.

## Шаг 8 — HTTP

```python
        def do_GET(self):
            if self.path.startswith("/buckets/"): …        # какие бакеты есть у этой единицы
            if self.path.startswith("/mirrored/"): …       # чьи копии я держу
            if self.path == "/events" or self.path.startswith("/events?"): …   # запрос к индексу
            if self.path.startswith("/events/"): …         # один бакет, кусками (`_bucket`)
            if extra is not None: …                        # маршруты подсистемы
            self._raw(404, b"")
```

Пять веток. Первые две — межресурсный разговор (зеркало). Третья — то, что спрашивает консоль (урок 13). Четвёртая — выдача файла: по ней сосед тянет копию, и по ней же отдаются копии обратно владельцу.

Файл уходит **кусками**, с названной длиной. Раньше это был `f.read()` в один ответ: восемь нечитающих читателей бакета в 60 МБ держали в ресурсе 400 МБ, а сосед медленнее 2 МБ/с не получал бакет никогда — таймаут сокета покрывает весь `sendall`, и `restore` такого бакета падал на каждом повторе (седьмое ревью, воспроизведено запуском). Теперь `_bucket` шлёт `Content-Length` и затем по `STREAM_PIECE` (128 КиБ) байт, каждый кусок под таймаутом сокета, читателю, который держит в среднем `STREAM_MIN_RATE` (`Paced`) — как двери держателя и регистраторов. Ответ, который кончился раньше названной длины, читатель видит ошибкой. Тест: `test_console_load.py::test_a_bucket_goes_out_in_pieces_to_a_slow_reader_and_is_never_held_whole`.

```python
            if resource.index is None:
                return self._raw(503, b'{"error": "this resource runs no event index"}', …)
```

Ресурс без индекса честно отвечает 503 с объяснением, а не пустым списком. Тот же принцип, что `truncated` в уроке 13: **не отвечать коротко.**

И второй 503, стоящий дороже, чем кажется: **«занят»**. Сервер заводит поток на каждый запрос и никогда не говорит «нет», поэтому без предела всплеск читателей — очередь без конца: каждый ответ всё позже, память растёт, а читатель, у которого истёк таймаут, не отличит «медленно» от «нет его». Больше `EVENTS_INFLIGHT` (восьми) запросов `/events` одновременно ресурс не отвечает: сверх — 503 с `Retry-After: 1`. Слияние читает это как «не ответил», окно становится неполным, и вычислитель автоматизации держит курсор, а не теряет то, что этот ресурс хранит (урок 25 М10B). Перегрузка становится видимой ошибкой, а не растущей задержкой.

```python
            if extra is not None:
                r = extra(self.path, self.headers)
                if r is not None:
                    return self._raw(*r)
```

Вторая дверь для подсистемы, парная к `register`: та добавляла проход в таймер, эта — маршруты в сервер. `extra` получает путь и заголовки, возвращает `(статус, байты[, заголовки])` или `None`, если маршрут не её. VMS через неё не добавляет ничего — комментарий над `serve` так и говорит: *the VMS adds none: its footage is behind the recorders' doors*. Таймлайн и кадры камеры спрашивают у регистраторов, у двери архива каждого (М10B, урок 10). Дверь ресурса остаётся для подсистемы, у которой на его диске есть свои файлы для чтения.

```python
        def do_PUT(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return self._raw(400, b"")
            if not self.path.startswith("/mirror/"):
                …                                               # a subsystem's own write (`extra_put`), under the same deadline
            rel = self.path[len("/mirror/"):]
            server, _, path = rel.partition("/")
            if not safe_segment(server) or not safe_rel(path) or not path.endswith(".events.jsonl"):
                return self._raw(400, b"")
            if n < 0 or n > MIRROR_MAX:
                self.close_connection = True
                return self._raw(413, b"")
            dest = os.path.join(root, MIRROR_DIR, server, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            left, late = n, False
            body_deadline(self, n)
            with open(dest + ".tmp", "wb") as f:
                try:
                    while left > 0:
                        part = self.rfile.read(min(left, 1 << 16))
                        if not part:
                            break
                        f.write(part); left -= len(part)
                except (TimeoutError, OSError):
                    late = True
            if left:
                os.remove(dest + ".tmp")
                self.close_connection = True
                return self._raw(408 if late else 400, b"")
            os.replace(dest + ".tmp", dest)                     # a copy appears whole or not at all
            self._raw(204, b"")
```

**Что запрос может назвать — в одном месте** (`w2cplatform/doors.py`). Каждая дверь проверяла путь сама и по-своему: `".." in rel` у большинства, ничего у `/buckets/<sub>/<unit>` и `/mirrored/<server>`, и нигде — того, чего эта проверка не ловит: **абсолютного пути**. `os.path.join(root, "/etc/hosts")` — это `/etc/hosts`: второй слэш после префикса двери читал любой файл машины, в том числе строку единицы с учётными данными (ревью платформы; двери продукта, BD). Правило, написанное у каждой двери отдельно, — правило, которого у какой-то двери нет. Теперь их два на всех: `safe_segment` — одно имя (не пустое, не `.` и не `..`, без разделителя) и `safe_rel` — относительный путь, каждый сегмент которого такое имя. Через них проходят все маршруты, которые превращают URL или заголовок в имя или место на диске: `/buckets`, `/mirrored`, `/events/<путь>`, `/mirror`, а в М10B — запись в пути двери архива регистратора (`archive_routes`) и метка удержания. Там же `byte_range` и `MAX_LIMIT` — сколько запрос может попросить. Тесты — `tests/test_doors.py`, на живом сервере ресурса.

Единственный `PUT` во всей платформе — приём копии. Три проверки: имя сервера и путь проходят `doors`, расширение не бакета. Последняя существенна: без неё сосед мог бы положить что угодно куда угодно под видом копии.

Запись — снова через `.tmp` и `os.replace`: копия появляется целиком или не появляется вовсе.

**Тело копии ограничено и по размеру, и по времени.** Копия больше `MIRROR_MAX` (64 МиБ — десять минут событий, со штормом) получает 413, и ничего не читается. Меньше — пишется во временный файл кусками по 64 КиБ, а память держит кусок, не бакет (шестое ревью). И у тела есть срок целиком: `timeout` двери плюс секунда на каждые `BODY_RATE` байт (`body_deadline`, правило `read_body` консоли). Раньше после заголовков тело читалось только под таймаутом сокета на каждое чтение. 32 соединения, объявившие 60 МБ и шлющие по байту раз в двадцать секунд, держали долю адреса вечно, а с двух адресов — всю дверь: `/events`, `/events/wait` и зеркало получали 503 (седьмое ревью, воспроизведено запуском). Тело, не пришедшее в срок, — 408, и копии нет. Тот же срок у собственных записей подсистемы (`extra_put`). Тесты: `test_console_load.py::test_the_resources_door_is_bounded_and_a_mirrored_bucket_is_never_held_whole`, `test_the_resources_door_gives_a_mirrored_body_a_deadline_whole_and_a_subsystems_write_too`.

## Шаг 9 — Тест: две подсистемы, которых нет

```python
def test_the_resource_is_a_platform_job_that_mirrors_any_subsystems_buckets():
    """Two resources on one box (two roots), one raft. The knob is one Variable;
    the peers are a rule, not a map; only closed buckets travel."""
```

Вот что делает этот тест. Два ресурса в одном процессе, каждый со своим каталогом. Подсистемы, которых в курсе не существует, — просто имена каталогов. Ручка включается одной записью в хранилище. Проход первого ресурса кладёт закрытые бакеты на второй; повторный проход не копирует ничего. Потом первый теряет дерево, `restore` тянет своё обратно, и открытый бакет не возвращается — он и не уезжал.

И то, ради чего тест стоит в уроке 1 платформы: **в файле нет слова *camera*.** Весь механизм отказоустойчивости данных проверен на подсистемах, про которые известно только их имя.

## Шаг 10 — Измерение

```python
def disk_space(root: str) -> tuple[int, int]:
    """(total, free) bytes of the filesystem `root` is on."""
    u = shutil.disk_usage(root)
    return u.total, u.free
```

Две строки, и в них два выбора. Оба — про то, **какое** число мы берём, а не про то, чем его взять: `shutil.disk_usage` — это `statvfs` на Unix и `GetDiskFreeSpaceExW` на Windows, и оба выбора ниже стандартная библиотека уже сделала за нас так, как нам нужно (шаг 15 — про то, почему это тот редкий случай, когда шов писать не надо).

**`statvfs`, а не обход дерева.** `usage()` из шага 4 отвечает на вопрос «сколько занимаем **мы**». Для решения «резать или нет» нужен другой: «сколько осталось **на диске**». Это разные числа, и разница — не педантизм: на том же разделе лежат журналы, хранилище конфигурации, чужие данные, и если их стало больше, ватерлиния обязана сработать, хотя наше дерево не выросло ни на байт.

К тому же `usage()` обходит всё дерево — в первой версии на каждом heartbeat'е, теперь раз за проход политики, и heartbeat берёт число из кэша (`usage_cached`). У пятидесяти единиц с десятиминутными бакетами за год набирается больше двух с половиной миллионов файлов, и это заметно. `statvfs` стоит константу — один системный вызов, независимо от того, сколько файлов под корнем.

**`f_bavail`, а не `f_bfree`.** Файловая система резервирует часть блоков под привилегированного пользователя; они свободны, но не для нас. Считать их своими — значит однажды упереться в «нет места» при «десять процентов свободно» на графике. Именно это `shutil.disk_usage` и возвращает в `free` (`f_bavail * f_frsize`), а на Windows — «доступно вызывающему», то есть долю квоты, а не свободное место тома: одна и та же мысль — сколько **нам** можно потратить.

Заметьте ещё, чего в этой функции нет: она не знает ни про архив, ни про бакеты, ни про подсистемы. Это про **том**, и больше ни про что.

```python
    def space(self, volume: str | None = None) -> dict:
        names = [volume] if volume is not None else list(self.volumes)
        total = free = 0
        for n in names:
            t, f = self.space_probe(self.volumes[n])
            q = self.quotas.get(n, 0)
            if q:
                left = max(0, q - self.usage_of(n))           # что оставляет ПОТОЛОК
                t = min(t, q) if t else q                     # `t == 0`: за этим путём нет диска (бакет)
                f = min(f, left) if t else left               # …и тогда потолок — единственная правда
            total += t; free += f
        return {"total": total, "free": free, "used": total - free,
                "full": (total - free) / total if total else 0.0}
```

`space_probe` — шов. По умолчанию это `disk_space`; тест подставляет функцию, возвращающую любые два числа. Без шва весь этот урок проверялся бы только на настоящем полном диске, то есть не проверялся бы.

**`quotas` — потолок тома, и он понадобился дважды.** Сетевой архив спрашивать нечего: `disk_usage` по точке монтирования отвечает про машину, а не про бакет. И два тома на **одном** разделе — так оператор делит диск между архивом на год и архивом на неделю — иначе оба прочитали бы одно и то же свободное место и оба сочли бы его своим: ватерлиния одного освобождала бы место, которое тут же забирает другой.

И отдельно — **как ватерлиния меряет бакет**, потому что это единственный ответ на этот вопрос во всём курсе. У сетевого архива `space_probe` возвращает ноль: за этим путём нет файловой системы, которую можно спросить. Ветка `if t else` читается именно так — когда диска нет, потолок и есть вся правда о томе, и `used` считается обходом дерева, а не вычитанием из `total`. Уберите квоту у такого тома — и `space()` честно скажет «ноль из нуля», то есть ватерлиния на нём перестанет значить что-либо.

Не путайте эти тома ресурса с томами ObjectStorage из М10B. Там `quota_bytes` значит другое — размер кольца, на который движок форматирует том (М10B, урок 27). Ресурс такие тома не меряет и не освобождает.

Важно, чем потолок **не** является: это не резервирование. Том получает **меньшее** из двух — сколько оставляет его квота и сколько на самом деле есть на диске. Никто ничего не откладывает, и диск, забитый кем-то посторонним, остаётся забитым, что бы ни было написано в квоте. Обратная сторона: `usage_of(<том>)` — это обход поддерева, поэтому он кэшируется рядом с общим числом и обновляется проходом, а спрашивают его только тома, у которых потолок есть.

`space` уезжает в heartbeat ресурса рядом с `usage` и `units`. Это не украшение. Консоль отдаёт его по каждому серверу метрикой `w2c_resource_full{server}`. А в М10B из него берётся размер раздела, когда консоль предлагает оператору объявить первый том (`volumes.suggest`, М10B урок 27).

## Шаг 11 — Две отметки

```python
def space_defaults() -> dict:
    return {"enabled": os.environ.get("WATERMARK_DEFAULT", "on") != "off", "high": 0.85, "low": 0.75, "min_days": 3.0}


def space_settings(vars_, last: dict | None = None) -> dict:
    """The watermark's settings; with `garbled: [field, …]` when a number of the row does not parse."""
    items, _ = vars_.get(SPACE_KEY)
    d = items or {}
    dflt = space_defaults()
    out = {"enabled": d.get("enabled") == "true" if "enabled" in d else dflt["enabled"]}
    garbled, errors = [], []
    for f in ("high", "low", "min_days"):
        try:
            out[f] = finite(d.get(f, dflt[f]))
        except (ValueError, TypeError) as e:
            out[f] = (last or dflt).get(f, dflt[f])
            garbled.append(f); errors.append(f"{f}: {e}")
    if garbled:
        SPACE.garbled(SPACE_KEY, "; ".join(errors))
        out["garbled"] = garbled
    else:
        SPACE.parsed(SPACE_KEY)
    return out
```

**Включена, пока её не выключили.** Первая версия делала наоборот, как у зеркала: нет строки — ватерлинии нет. Разница между двумя ручками в том, что происходит, если о них забыли. Забытое зеркало — это отсутствие копий, о котором спросят при первом отказе диска. Забытая ватерлиния — это полный диск без всякой политики: запись регистратора падает, а вместе с ней хранилище конфигурации и журнал событий на том же разделе, и никто ничего не решал (ревью платформы, «поведение при заполнении диска выбирает код»; обратная связь, BM). Поэтому без строки ватерлиния работает на умолчаниях, а `enabled: false` — решение её не иметь, и его кто-то принимает. Строка, которая только подстраивает отметки, её не выключает.

`WATERMARK_DEFAULT=off` — для тестов, и сказано окружением, как `STORE_VOLATILE` в уроке 2: набор тестов идёт на диске разработчика, заполненном как придётся, и не должен из-за этого резать свои заготовки.

Ручка той же формы, что `platform/mirror` из шага 5: строка в хранилище, значения по умолчанию в коде, а не в YAML подсистемы. Место — свойство железа, а не подсистемы. И ставит её тот же человек: `platform/space` — ключ платформы, а не подсистемы, писать в него не может ни один процесс курса, поэтому отметки выставляет инсталлятор управляющим токеном при развёртывании.

`high` и `low` — доли **занятого**. Выше `high` ресурс начинает освобождать, останавливается на `low`.

Почему отметки две, видно, если попробовать обойтись одной. Освободили один файл — ушли под порог. Через минуту записали новый — снова над ним. Освободили ещё один. Это пила: постоянная мелкая работа, график, по которому ничего не понять, и удаление, растянутое навсегда вместо одного внятного акта.

**Зазор надо задавать в часах записи, а не в процентах.** Пример из комментария в коде: пятьдесят камер по четыре мегабита пишут около 2.2 ТБ в сутки. Десять процентов диска на 20 ТБ — это 2 ТБ, то есть **меньше одних суток**: проход будет запускаться почти непрерывно. Скорость притока лучше всех знает тот, кто пишет, — и именно от неё, а не от ёмкости диска, стоит отсчитывать зазор.

`min_days` — пол: количество дней, ниже которого не режут никого. Ресурс передаёт его в `free` подсистемы; резать ниже пола она не должна, а если выше пола отдать нечего — это недостача.

**Недостача — число, которое видно.** Выше отметки, а отдать нечего: все на полу, или на этом диске вообще нет ничего, что подсистемы согласны отдать. Это единственное состояние, которое ватерлиния не чинит, и оно было строкой в логе прохода. Теперь ресурс помнит недостачу последнего прохода по томам (`self.short`) и говорит сумму в heartbeat'е (`short`), а консоль отдаёт её по каждому серверу: `w2c_resource_short_bytes{server}`, рядом с `w2c_resource_full{server}`. Не ноль — диск надо добавить или хранить меньше; сама система уже сделала, что могла.

**Хранилище не ответило — это не «ручка выключена».** Настройки — одна строка. Проход, который не смог её прочитать, останавливался на исключении, и полный диск оставался полным всё время, пока хранилища не было, — то есть ровно тогда, когда никто не смотрит (обратная связь, BI). Ресурс помнит настройки, которые прочитал последними, и действует по ним. Если он не читал их ни разу, он отвечает `{"space": "unknown"}` и не освобождает ничего: угадывать он не станет.

**Строка, которая не разбирается, — тоже не «выключена».** `high: "85%"` бросал исключение из `space_settings`, и `relieve` падал на каждом проходе. На диске, занятом на 98 %, не освобождалось ничего, а последняя прочитанная настройка (`_space_knob`) лежала в руках без дела (седьмое ревью, часть 2). Строку пишет только инсталлятор управляющим токеном, мимо всякой двери, и проверить её при записи некому. Поэтому теперь каждое число читается отдельно. Число, которое не разбирается, как и `nan` или `inf` (`finite`), берётся из настроек, прочитанных последними, а если их не было — из умолчаний. Остальные числа строки остаются как есть. Строка считается один раз, пока снова не станет читаться, и один раз попадает в лог. Heartbeat ресурса говорит, по чему ватерлиния действует сейчас: `space_garbled: "platform/space does not parse (high): acting on the settings read last for it"`, а `/metrics` консоли — `w2c_resource_space_garbled{server} 1` (восьмое ревью, minor: раньше это было только в heartbeat'е). В отличие от молчащего хранилища, ждать здесь незачем: хранилище ответило, и ответ ясен. Тест: `test_row_reader.py::test_a_garbled_watermark_row_acts_on_the_settings_read_last_and_says_so`.

## Шаг 12 — Проход, который не удаляет

```python
    def relieve(self) -> dict:
        knob = space_settings(self.vars, self._space_knob)   # упрощено: в коде ещё молчащее хранилище и `space_garbled`
        if not knob["enabled"]:
            return {"space": "off"}
        for name in self.volumes:                      # по томам: место не усредняется
            sp = self.space(name)
            if not sp["total"] or sp["used"] <= sp["total"] * knob["high"]:
                continue
            need, freed = int(sp["used"] - sp["total"] * knob["low"]), 0
            for sub, h in self.hooks.items():
                free = getattr(h, "free", None)
                if free is None:
                    continue
                rep = _ask_to_free(free, need - freed, self.wall(), knob["min_days"], name)
            freed += int(rep.get("freed", 0))
            out.update({f"{sub}.{k}": v for k, v in rep.items()})
            if freed >= need:
                break
        return {"space": "over", "full": round(sp["full"], 3), "need": need, "freed": freed,
                "short": max(0, need - freed), **out}
```

Посмотрите, чего этот метод **не делает**: он не открывает ни одного файла подсистемы, не знает, что эти файлы значат, ничего не знает про камеры и не удаляет ничего.

Он делает ровно три вещи: меряет, считает `need` и зовёт чужие проходы через `getattr(h, "free", None)`.

**`need` считается до низкой отметки, а не до высокой.** Освободить ровно столько, чтобы уйти под `high`, — значит вернуться к нему через минуту. Это и есть зазор в арифметике.

**`getattr`, а не обязательный метод.** Подсистема, которая держит только бакеты, ничего не переопределяет: для неё `retain` по дням — вся политика, и она в этом проходе не участвует. Дверь открыта, но входить не обязательно.

**Порядок в `pass_`.** Хуки подсистем, потом `retain`, потом `relieve`, потом `mirror`:

```python
    def pass_(self) -> dict:
        out, errors = {}, []
        def part(name, fn, into=None):
            try:
                r = fn()
                out.update(r if into is None else {into: r})
            except OSError as e:
                errors.append(f"{name}: {e}")
        for sub, h in self.hooks.items():
            part(sub, lambda h=h, sub=sub: {f"{sub}.{k}": v for k, v in h.pass_(self.wall()).items()})
        part("retain", self.retain, "removed")
        part("relieve", self.relieve)
        part("mirror", self.mirror)
        if errors:
            out["errors"] = errors
        return out
```

**Каждая часть — в своём `try`.** `retain` читает строки сроков и меток удержания, и при молчащем хранилище падает — намеренно: не знать, что удержано, не значит «ничего не удержано», и удалять по сроку нельзя. Но в одном блоке с ним падали и `relieve`, и `mirror`: ватерлиния над деревом событий не работала, пока молчало хранилище (второе ревью). Теперь часть, которая не смогла, названа в `errors`, а остальные идут; следующий проход попробует снова.

Сначала обещание, потом предохранитель. `retain` удаляет то, что и так пора удалить, — и вполне возможно, что после него `relieve` увидит `space: ok` и не сделает ничего. Обратный порядок резал бы живое, не забрав сначала мёртвое.

### Почему цикл по томам, а не одно число

У сервера бывает не один диск, и это не экзотика: коробка с тремя дисками — обычная поставка. Ресурс при этом **остаётся одним на сервер** — достижимость есть свойство машины, у тома нет адреса, и молчать отдельно от сервера он не может, — но тома становятся его внутренним устройством:

```python
res = Resource(None, "srv-1", url, vars_, objects,
               volumes={"vol-a": "/data/a", "vol-b": "/data/b", "vol-c": "/data/c"})
```

А вот **ватерлиния усреднения не терпит**, и это главное, что стоит унести из шага. Коробка, заполненная на 50% по двум дискам, один из которых на 98%, — это коробка, которая **перестала писать**: единица, которой некуда писать, лежит на полном томе, а байты, освобождённые на пустом, не закрывают ничего. Одно число на сервер здесь врёт ровно в ту сторону, в которую врать нельзя.

Поэтому проход идёт по томам, и **том едет в хук**:

```python
def _ask_to_free(free, need, now, min_days, volume):
    try:
        return free(need, now, min_days, volume=volume)
    except TypeError:
        return free(need, now, min_days)
```

Подсистема знает, какие её файлы что значат; ресурс знает, какому диску тесно. Ни одна из этих двух вещей не выводится из другой — поэтому в вызове теперь обе.

Падение на старую форму — не вежливость, а миграция: подсистема, у которой все файлы на одном диске, выбирать не из чего, и переписывать её в день, когда в коробку добавили второй диск, незачем. Тот же приём, что с правилом свежести в уроке 15: новое знание не должно ломать тех, кому оно не нужно.

**В продукте то же самое написано на Go, и разница ровно в одном:** там, где в Python вызов пробуется и падает в старую форму по `TypeError`, в Go это две двери, и компилятор сам выбирает:

```go
type Freer interface {        // подсистема с одним диском
    Free(need int64, now, minDays float64) map[string]any
}
type VolumeFreer interface {  // …и с несколькими
    FreeOn(need int64, now, minDays float64, volume string) map[string]any
}
```

`askToFree` спрашивает богатую дверь первой, а бедную — если богатой нет. Утиная типизация и утверждение типа приходят к одному и тому же, и миграция в обоих портах бесплатная.

### Какой том держит единицу

Нигде не записано — и это сознательно:

```python
    def volume_of(self, sub: str, unit: str) -> str | None:
        for name, path in self.volumes.items():
            if os.path.isdir(os.path.join(path, sub, str(unit))):
                return name
        return None
```

Каталог единицы **и есть** ответ, ровно как `subsystems_under` выводит, что на ресурсе вообще лежит. Карта «единица → том» была бы второй правдой о дисках, и она бы разошлась — в тот день, когда кто-то перенёс каталог руками или том вернулся из бэкапа не тем.

Новая единица уезжает на самый свободный том (`place_volume`) и больше не переезжает: перенос между дисками — это копирование терабайтов, и оно не должно быть побочным эффектом прохода.

## Шаг 13 — Кто сегодня отвечает на `free`

Платформа сказала «освободи N байт». Что именно отдать, решает тот, кто знает, что его файлы значат. Дверь для этого — `free(need, now, min_days, volume=…)` на проходе подсистемы, и ресурс зовёт её только у тех, у кого она есть.

В М10B её нет ни у одной подсистемы, и это не упущение. Тест недостачи говорит об этом прямо:

```python
class _Files:
    """A subsystem that keeps files on the resource's disk and can give some up: two thousand bytes above its
    floor. The VMS has none any more — footage is in volumes, rings that never outgrow their quota — and the
    watermark is the platform's, for whatever a subsystem keeps on that disk."""
```

Видео — самое большое, что пишет VMS, — лежит в томах ObjectStorage. Том форматируется на свою квоту и дальше не растёт: заполнился — движок сам отдаёт старейшие блоки. На дереве ресурса остаются бакеты событий (их срок — `retain`, шаг 2) и мелочь вроде прогресса скана. Освобождать под давлением VMS нечего.

Поэтому на коробке курса ватерлиния мерит раздел и говорит, сколько байт лишних, а позвать `free` ей не у кого. Всё, что надо было освободить, становится недостачей: `short` в heartbeat'е ресурса и `w2c_resource_short_bytes{server}` на консоли (`test_disk_full.py::test_what_could_not_be_freed_is_a_number_anybody_can_read`, `test_lesson1_platform.py::test_the_watermark_asks_and_never_deletes` — его последняя часть ставит подсистему без `free` и видит `short == need`).

Это тот же выбор, что у `spread_by` в уроке 11: когда честного варианта нет, честный ответ — сказать это, а не выбрать тихий. Недостача не ноль — значит, на разделе растёт то, чего ни одна подсистема не отдаёт, и диск надо добавить или найти, кто его съел.

А сколько дней видео на самом деле в томе, ресурс не знает и знать не должен. Это считает регистратор по индексу тома, и мелкую запись он называет тревогой `archive.shallow` (М10B, урок 27).

## Шаг 14 — Python: шов внутри, ветка — в импорте

```python
def _try_lock(f) -> bool:
    try:
        import fcntl
    except ImportError:                                   # Windows
        import msvcrt
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
```

Импорт уехал из шапки модуля внутрь функции — и это, а не сама ветка, главное изменение. Модуль теперь импортируется где угодно; ошибка, если она случится, случится в момент блокировки и назовёт блокировку.

Вызывающий не изменился совсем:

```python
def _locked(self):
    f = open(self.lock_file, "a+")
    _lock_exclusive(f)
    return f
```

Ветка по операционной системе — в `_try_lock`, а ожидание написано один раз, над обеими: `_lock_exclusive` спрашивает блокировку каждые пять миллисекунд и через `LOCK_WAIT` бросает `StoreBusy` (урок 2, шаг 5). Так две платформы ведут себя одинаково. Раньше было иначе, и этот абзац остался как объяснение, почему предел вынесен наверх.

Первая версия звала `msvcrt.locking(LK_LOCK)` — не перевод, а близкий эквивалент, и разницу надо знать, а не прятать: он повторяет попытку около десяти секунд и потом бросает исключение, тогда как `flock(LOCK_EX)` ждёт сколько угодно. Хранилище, занятое десять секунд, — это коробка в беде в обоих случаях, и исключение с именем блокировки лучше процесса, который ждёт вечно. Но это **разница**, и в тот день, когда она сработает, сообщение будет единственным, что скажет, на какой вы ОС.

Блокируется один байт от нулевой позиции: файл `lock` существует, чтобы **быть** блокировкой, содержимое его никто не читает.

## Шаг 15 — Python: диск — и приятный случай

```python
u = shutil.disk_usage(root)
return u.total, u.free
```

Всё. `shutil.disk_usage` есть на обеих ОС, **и сохраняет смысл**: на POSIX его `free` — это `f_bavail * f_frsize`, ровно та строчка, которую он заменил; на Windows — первый выходной параметр `GetDiskFreeSpaceExW`, «доступно вызывающему». Это одна и та же идея — сколько нам можно потратить, а не сколько существует, — поэтому водяному знаку над ним не нужен ни один `if`.

Прежде чем писать свой шов, посмотрите, нет ли его в стандартной библиотеке. Здесь был.

## Шаг 16 — Go: ветку берёт компилятор

В Go импортов внутри функции нет, зато есть теги сборки, и это лучше: различие исчезает до запуска.

```go
// flock_unix.go
//go:build !windows
func flockFile(f *os.File) error { return syscall.Flock(int(f.Fd()), syscall.LOCK_EX) }

// flock_windows.go
//go:build windows
var procLockFileEx = syscall.NewLazyDLL("kernel32.dll").NewProc("LockFileEx")

func flockFile(f *os.File) error {
	var ol syscall.Overlapped
	r1, _, err := procLockFileEx.Call(f.Fd(), uintptr(lockfileExclusiveLock), 0, 1, 0, uintptr(unsafe.Pointer(&ol)))
	if r1 == 0 {
		return err
	}
	return nil
}
```

Так же разнесён `DiskSpace`: `space_unix.go` — прежний `Statfs`, `space_windows.go` — `GetDiskFreeSpaceExW`, и там опять первый выходной параметр, тот же выбор, что `f_bavail`.

Три вещи стоит заметить.

**Ноль зависимостей.** `go.mod` этого модуля пуст, и это утверждение курса: тесты запускаются без сети. Один вызов Windows — не повод заводить первую зависимость, поэтому `kernel32` зовётся через `syscall.NewLazyDLL`, а не через `golang.org/x/sys/windows`.

**И почему так можно именно здесь.** В `x/sys/windows` есть `NewLazySystemDLL`, которая грузит DLL строго из системного каталога; в стандартном `syscall` её нет — только `NewLazyDLL`, которая ищет по обычному порядку поиска. Обычно это дыра: подсунутая рядом с бинарником DLL с нужным именем будет загружена. Для `kernel32` — нет: она загружена в каждый процесс Windows до того, как выполнится первая строка Go, и `LoadLibrary` для уже загруженного модуля возвращает его, не трогая путь. **Не копируйте эту строчку для DLL, которой в процессе ещё нет** — там `NewLazyDLL` это подмена порядка поиска, и правильный ответ `x/sys`.

**`LockFileEx` обязательная, `flock` рекомендательная.** Для файла, который никто не читает, разница не видна. Освобождаются обе закрытием дескриптора, поэтому вызывающий на обеих ОС пишет `defer l.Close()`.

## Шаг 17 — Тест под форму отказа

Форма отказа разная — значит и тесты разные. Это и есть главный урок здесь.

**В Python отказ — это несостоявшийся импорт**, поэтому тест **импортирует, и больше ничего не делает**:

```python
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split(".")[0] in names:
        raise ImportError(f"no module named {name!r} on this platform")
    return real_import(name, globals, locals, fromlist, level)
```

Ничего не подменяется внутри модулей: системе импорта говорят правду про платформу, где `fcntl` нет, и пакет либо переживает это, либо нет.

(`level` здесь не формальность. `from .resource import …` приходит сюда как голое имя `resource` с `level=1`, а в платформе есть свой модуль `resource`. Без проверки уровня тест «находит» несуществующую проблему в двух файлах — я это и увидел с первого запуска.)

**В Go отказ — это несостоявшаяся сборка**, поэтому тест **собирает**:

```go
var portable = []string{"./w2cplatform/...", "./vms/...", "./cmd/..."}

cmd := exec.Command(goBin, append([]string{"build", "-o", os.DevNull}, portable...)...)
cmd.Env = append(os.Environ(), "GOOS="+goos, "GOARCH=amd64", "CGO_ENABLED=0")
```

под `windows`, `linux` и `darwin` — кроме той, на которой вы сейчас, её доказывает сам факт, что тест запустился.

**Список пакетов, а не `./...`, — и это не осторожность, а формулировка.** Пока порт состоит из чистого Go, разницы нет: соберётся всё. Разница появляется в тот день, когда в продукте заводится медиапуть — cgo поверх GStreamer и вендорского драйверпака. Он не кросс-компилируется **никуда**, и `./...` начнёт краснеть всегда, о платформе при этом не говоря ничего: тест перестанет что-либо проверять и станет тем, что отключают.

Поэтому переносимость — **свойство, которое пакет заявляет**, попав в этот список, а не то, что случайно получилось. Добавление строки сюда — решение, которое кто-то принимает осознанно, и ровно поэтому оно видно в диффе.

И второй тест — про то, что шов один: файлы с тегами существуют, а ни один файл без тега не называет `syscall.Flock`, `syscall.Statfs` или `syscall.NewLazyDLL`. Шов, протёкший в вызывающих, — это не шов, а одинаковый `if`, повторённый в N местах; в день появления третьей платформы одно из них забудут.

## Что здесь не проверено

Скажите это прямо, иначе зелёный набор начнёт означать больше, чем означает.

Ни одна строчка из последних четырёх шагов **не запускалась на Windows**. Проверено:

- кросс-сборка под `windows`, `linux`, `darwin` — вызовы существуют и типы сходятся;
- полный набор на Unix — и шов не сломал то, что работало;
- Python импортируется без `fcntl` и `statvfs`, а блокировка и замер диска отвечают.

Не проверено: что `LockFileEx` действительно берёт блокировку и что `GetDiskFreeSpaceExW` возвращает то, что мы думаем. Это разные утверждения, и первое не доказывает второго.

Отдельно стоит записать известный риск, который курс закрыть не может: `FileVariables` пишет через `.tmp` + `os.replace`, а читает без блокировки. Go на Windows открывает файлы без `FILE_SHARE_DELETE`, поэтому замена файла, который в этот момент читает другой процесс, может упасть с «Access is denied». Не воспроизведено; лечится либо повтором `Rename`, либо чтением под блокировкой; проверяется нагрузочным тестом нескольких процессов на одном `PLATFORM_DIR` — и до тех пор это строчка в списке рисков, а не в списке возможностей.

**Результат:** `resource.py` целиком; работающее зеркало между двумя каталогами; восстановление после стёртого дерева; сработавшая на поддельном зонде ватерлиния, которая не удалила ни одного файла сама; `_lock_exclusive` и `disk_space`, за которыми спрятаны две системные функции, а в Go-порте — четыре файла с тегами сборки; и ответ своими словами на вопрос, почему у ресурса нет контроллера.

---

## Что может пойти не так

| Симптом | Скорее всего |
|---|---|
| Копии не появляются | Ручка `platform/mirror` не включена — по умолчанию выключено. Или соседи молчат: копии кладутся только на живых. |
| Одно и то же копируется каждый проход | Не спрашивается `mirrored` у соседа, а ведётся своя отметка об отправке. Источник истины — получатель. |
| Копируется открытый бакет | Потеряна проверка `b.end <= wall()`. Он будет пересылаться целиком при каждом проходе. |
| После возврата диска подсистема не видит вернувшихся файлов | `restore` не прогнал зарегистрированные проходы — или подсистема не зарегистрировала свой. |
| Из базы не исчезают удалённые события | `retain` не зовёт `forget`. Проход по файлам исчезнувшего не заметит. |
| Подсистема проиндексировала файлы, которых уже нет | Порядок в `pass_` обратный: хранение раньше чужих проходов. |
| Сосед положил копию не туда | Ослаблена проверка `.events.jsonl` или `..` в `do_PUT`. |
| Ресурс не находится консолью | `url` в heartbeat'е не тот, по которому он доступен снаружи: адрес объявляется, а не настраивается. |
| Данные живут вечно | Ни одной строки хранения нет, и сработало умолчание в год. Это выбор в пользу сохранения. |
| Ватерлиния не срабатывает, хотя диск полон | Меряется дерево (`usage`), а не том. Чужие данные на том же диске так и останутся невидимыми. |
| Пила: освободили — записали — освободили | Одна отметка вместо двух, или `need` считается до `high`, а не до `low`. |
| Проход запускается каждую минуту | Зазор выбран в процентах. Пересчитайте его в часах записи. |
| Вчерашние данные важной единицы исчезли | Подсистема режет ниже пола, или пол ниже, чем думает оператор: обещание тихо превратилось в предохранитель. |
| Недостача есть, оператор не знает | `short` не доехал до heartbeat'а и до метрики. Молчащий предохранитель хуже сработавшего. |

А это уже не симптомы, а решения, которые кажутся разумными ровно до того, как их примешь:

- **Оставили `import` в шапке.** Классика: на своей машине всё зелено, на целевой ОС не существует ничего. Тест на импорт.
- **Разветвились у вызывающего.** `if os.name == "nt"` в `_locked`, потом ещё в трёх местах, потом в четвёртом — забыли.
- **Написали свой `statvfs` для Windows,** не посмотрев, что `shutil.disk_usage` уже есть и сохраняет смысл.
- **Взяли `f_bfree` вместо `f_bavail`** — и водяной знак считает нашими блоки, зарезервированные для root. На Windows тот же промах — взять третий выходной параметр вместо первого.
- **Скопировали `NewLazyDLL` для не-системной DLL.** Для `kernel32` безопасно, для вашей — подмена порядка поиска.
- **Прочитали зелёный набор как «работает на Windows».** Он говорит «собирается».

## Итог

- У ресурса нет контроллера, потому что решать про него нечего: он там, где он есть. Сделать его подсистемой значило бы дать диску строку размещения.
- Хранение — три уровня (единица, подсистема, год) и одна строка в известном месте; ресурс не знает, откуда взялось число.
- Последнее умолчание — год: ошибка должна приводить к лишним данным, а не к потерянным.
- Соседи — правило, а не карта: следующие по кольцу среди живых. Никто ничего не перенастраивает при изменении состава.
- Копируются только закрытые бакеты; цена названа числом — до одного промежутка потерь.
- Получатель — источник истины о том, что у него есть; поэтому зеркало идемпотентно.
- Восстановление запускает владелец, и после него подсистемы получают шанс переиндексировать вернувшееся.
- Две двери для подсистемы: проход в таймер (`register`) и маршруты в HTTP (`extra`). Обе — «код под именем».
- Порядок прохода: чужое, хранение, зеркало. Каждый порядок обоснован.
- Ресурс не знает ни одной подсистемы, и тест на зеркало написан на подсистемах, которых не существует.
- Ретенция по дням — обещание; ватерлиния — что делать, когда обещание невыполнимо. Разные вещи, и путать их дорого.
- Мерить надо том (`statvfs`, `f_bavail`), а не своё дерево: чужие данные на том же диске так же кончают место.
- Две отметки, зазор между ними — в единицах притока. Одна отметка даёт пилу.
- Платформа считает, сколько байт; подсистема решает, чем. Ни одного файла подсистемы платформа не удаляет.
- Отдать нечего — это число в отчёте и в heartbeat'е, а не тихий рез: тот же выбор, что «разместить негде» в уроке 11.
- В М10B на `free` не отвечает никто: видео VMS лежит в томах ObjectStorage — кольцах, которые не растут за свою квоту, — и ватерлиния остаётся платформенной, для того, что подсистемы держат на диске ресурса.
- Две функции решали, поедет платформа на Windows или нет, и обе спрятаны за одним швом каждая: `_lock_exclusive` в Python, файл с тегом сборки в Go. Вызывающий не знает, на какой он ОС, и не должен.
- Форма отказа определяет тест: в Python отказ — это импорт, поэтому тест импортирует; в Go отказ — это сборка, поэтому тест собирает. Симптом в обоих случаях был бы «ничего не работает», и на симптом теста не напишешь.
- А граница между «собирается» и «работает» записана в уроке, а не подразумевается.
- Два шва — «хранилище это URL» и «блокировка по ОС» — решают одну задачу на разной глубине. В М11 хранилище становится `NomadVariables`, и ни `flock`, ни `statvfs` в этом пути нет вообще: шов этой главы нужен ровно тем установкам, где хранилище — файлы на диске оператора.

## Упражнения

1. Замените правило соседства картой в хранилище. Перечислите операции, которые теперь нужны при добавлении и удалении сервера, и что делать при расхождении.
2. Начните копировать и открытые бакеты. Посчитайте трафик за сутки при десятиминутных бакетах, проходе раз в десять минут и пятидесяти единицах.
3. Ведите отметку об отправке у отправителя вместо опроса получателя. Опишите состояние после замены диска у получателя.
4. Поменяйте порядок в `pass_` местами. Найдите проход, на котором подсистема проиндексирует исчезнувшее, и скажите, что покажет её индекс.
5. Уберите `forget` из `retain`. Через сколько дней база начнёт отвечать событиями, которых нет на диске?
6. Сделайте умолчание хранения нулевым вместо года. Опишите первый запуск подсистемы, забывшей написать свою строку.
7. Зарегистрируйте на ресурсе проход для `counter` — скажем, удаляющий бакеты единиц, которых больше нет. Сколько строк и что он должен знать о счётчике?
8. Замените `f_bavail` на `f_bfree` и заполните диск до отказа на тестовой машине. На каком проценте «свободного» встанет запись?
9. Сделайте отметку одну (`low == high`) и нарисуйте график занятости за час при постоянной записи. Сколько раз запустится проход?
10. Посчитайте для своей установки: сколько ТБ в сутки пишут ваши камеры и каким должен быть зазор, чтобы проход запускался не чаще раза в шесть часов.
11. Оставьте на ресурсе только подсистему без `free` и поставьте зонд на 90 % занятости. Что скажут `relieve`, heartbeat и `/metrics`, и почему ресурс при этом не удалил ни одного файла?
12. **Верните `import fcntl` в шапку** и посмотрите, какой именно тест падает и с каким сообщением. Потом верните `os.statvfs` — падает другой.
13. **Третья платформа.** Что нужно, чтобы платформа собралась под FreeBSD? Проверьте `GOOS=freebsd go build ./...` и объясните результат.
14. **Оцените риск `Rename`.** Напишите тест на несколько процессов, читающих и пишущих один `PLATFORM_DIR`. Что он покажет на Unix? Что он **не** покажет?
15. **`msvcrt` против `flock`.** Десять секунд и исключение против бесконечного ожидания — какое поведение правильнее для хранилища конфигурации, и почему ответ может отличаться для контроллера и для воркера?

## Что дальше

Платформа умеет всё, кроме одного: показать человеку. [**Урок 15**](15-SpecConsole.md) строит консоль из той же спецификации, из которой построен контроллер, — и первое, что делает, — отдаёт странице описание подсистемы, чтобы та собрала себя сама.

Подсистемы, которая отвечала бы на `free`, в М10B нет: видео лежит в томах ObjectStorage, и каждый том сам отдаёт старейшее. Какие тома бывают, кто их обслуживает и что делает с ними регистратор — [**урок 27 в М10B**](../М10B_ServerVMS/27-volumes.md). Платформа по-прежнему не знает ничего из этого.

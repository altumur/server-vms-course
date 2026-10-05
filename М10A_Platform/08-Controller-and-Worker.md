# Урок 8 — Два базовых класса

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `Controller` (`w2cplatform/contract.py`) — с методом `write`, который станет образцом каждой записи в курсе, — и `Worker` (`w2cplatform/worker.py`) с воротами: эпоха на старт, аренда перед записью и перед действием, heartbeat после. И рантайм воркера, общий для всех подсистем: цикл процесса, шаг аренд, ограду экземпляра и возвращение. Два класса, от которых наследуется всё остальное; YAML они ещё не читают.
**Время:** ~120 минут.

## Зачем этот урок

Хранилища есть, эпохи есть, слоты есть. Каждое из этих средств само по себе — несколько функций; чтобы ими пользоваться, нужно помнить порядок: сначала захвати слот, потом читай назначение, перед стартом возьми эпоху, перед записью спроси аренду, после прохода продли то и другое, раз в десять секунд напиши о себе. Забыть любой шаг — значит получить дефект, который проявится только при отказе.

Два класса этого урока собирают порядок в код. Наследник не может «забыть взять эпоху» — метод, который стартует единицу, берёт её сам. Не может «забыть проверить аренду» — она проверяется внутри тех же ворот. Не может «забыть продлить» — цикл процесса, шаг аренд и heartbeat принадлежат базе, а не ему. Не может «написать конфигурацию из воркера» — у воркера нет такого метода, а токен не дал бы права.

И оба класса не знают ни одной вещи о предметной области. `Controller` умеет назначать «единицы» — строки, — и не знает, что они означают. `Worker` умеет читать назначение, брать эпохи, держать их, огораживаться и отчитываться; что делать с единицей, он не знает вовсе: `reconcile_once` объявлен и **не реализован**, а «остановить единицу» — крючок `stop_unit`, который пишет подсистема. Спецификация здесь ещё не нужна: со следующего урока появится YAML, а воркер спрашивает у неё только то, что она объявила (места — урок 7, шаг 11; потолок неподтверждённой записи — шаг 7; ёмкость по умолчанию и подавление повторов событий — шаг 9; просьбы — урок 14), и без неё работает со строгими умолчаниями.

> **Что можно проверить без железа.** Оба класса целиком: `test_controller_and_worker_bases_speak_only_the_contract` строит контроллер и воркера для подсистемы `thing`, гоняет назначение, эпоху, heartbeat и возраст — и в тесте не встречается ни одного слова предметной области. А рантайм — на подсистеме `testsub`: тест границы (`tests/test_boundary.py`, часть `_piece_worker`) крутит настоящий `run` воркера, который написал только `reconcile_once`, `status`, `held_rows` и `perform`.

## Что нужно знать заранее

- **Урок 5** — `Subsystem`, `Assignment`, `Heartbeat`: чем эти классы обмениваются.
- **Урок 6** — эпоха и аренда: воркер их здесь соединяет.
- **Урок 7** — слот и место: методы захвата уже написаны и лежат в этом же классе, `Worker`.

## Чему вы научитесь

1. Писать «прочитать-изменить-записать по CAS» один раз и пользоваться этим везде.
2. Писать мутатор и объяснять, почему он вызывается внутри цикла повторов, а не до него.
3. Понимать приём «мутатор вернул `None`» и говорить, от чего он спасает.
4. Выводить существование воркеров из фактов, а не хранить их список.
5. Собирать ворота старта так, чтобы эпоху и аренду нельзя было обойти.
6. Объяснять, почему эпоха берётся на **единицу**, а не на воркера.
7. Называть всё, что база воркера оставляет наследнику, и почему именно это.
8. Собирать цикл процесса так, чтобы поддержание жизни не зависело от успеха работы, и говорить, что значит потерянная аренда, а что — отнятое имя.

---

## Шаг 1 — Контроллер: то, чего у него нет

```python
class Controller:
    """The only writer of <name>/*. Holds nothing: every method reads the
    store, decides, and writes by CAS. Two instances are harmless."""

    # Keeps the `Subsystem`, the two stores and a wall clock (tests inject a fake).
    def __init__(self, sub: Subsystem, vars_: Variables, objects: ObjectStore, wall=time.time):
        self._pass_local = threading.local()
        self.sub, self.vars, self.objects, self.wall = sub, vars_, objects, wall
        …
        self.eyes = Eyes(judge_clock(wall), wall)
        check_schema(vars_)                       # a build older than the store does not run at all
```

Конструктор — строка присваиваний и проверка схемы, и в нём четыре поля, ни одно из которых не состояние. Подсистема (имя), два хранилища, часы. Пятое — `eyes`: что контроллер видел меняющимся и когда, по своим часам (урок 7, шаг 7, «Чьи часы»); это память о наблюдениях этого процесса, а не о мире, и свежий контроллер начинает её с нуля. `check_schema` не даёт сборке старше хранилища даже начать работу (урок 17). Между проходами у контроллера нет ни кэша, ни списка воркеров, ни соединений, ни фонового потока.

**Кэш есть, но живёт один проход и умирает с ним.** Проход контроллера задаёт на каждую единицу дюжину вопросов — её строка, её размещение, на каком сервере воркер, отвечает ли ресурс того сервера, — и каждый был чтением хранилища, заданным заново для следующей единицы: тысяча единиц на двадцати воркерах стоила одному холостому проходу около 64 000 чтений. Внутри прохода ответ не может быть старше прохода, поэтому `with one_pass(ctl):` (или `ctl.one_pass()`) подставляет вместо хранилищ `_PassStore`: каждый `get` и `list` спрашивает настоящее хранилище один раз и держит ответ до конца прохода — не дольше. Поле `_pass_local` — это `threading.local()`: подмена видна только потоку, открывшему проход, а двери консоли из своих потоков видят само хранилище. Свойства `vars` и `objects` отдают либо чтения прохода, либо хранилище; присваивание задаёт хранилище:

```python
    @property
    def vars(self):
        r = self._reads()
        return r[0] if r is not None else self.__dict__["_vars"]
    ...
    def one_pass(self):
        return one_pass(self)
```

Запись идёт в хранилище как раньше и **забывает** то, чего коснулась, — ключ и каждый листинг, в который он мог попасть, — так что проход читает обратно написанное, а не прочитанное до записи. Проигравший CAS тоже забывает: `write` повторяет его по хранилищу, а не по копии, которая проиграла. Тесты: `test_read_budget.py::test_an_idle_controller_pass_over_a_thousand_cameras_reads_each_row_once` и `test_read_budget.py::test_a_pass_reads_back_what_it_wrote_and_a_lost_cas_asks_the_store_again`.

Из этого следует то, что написано в docstring: **два экземпляра безвредны.** Не «допустимы при условии», а безвредны — потому что нечему разойтись. Каждый метод начинается с чтения и заканчивается записью по CAS; два процесса, делающие один и тот же проход, придут к одному выводу, и второй проиграет гонку на записи, обнаружив, что работа уже сделана.

`count = 1` для контроллера — это **экономия, а не корректность**. Формулировка стоит того, чтобы её запомнить: второй экземпляр не опасен, он просто повторяет ту же пятисекундную работу.

## Шаг 2 — Образец записи

```python
    def write(self, path: str, mutate, retries: int = 10) -> dict:
        """Read-modify-write by CAS: `mutate(items or {}) -> new items`.
        A conflict means another instance wrote; re-read and go again."""
        for attempt in range(retries):
            try:
                items, idx = self.vars.get(path)
            except Garbled as e:                     # a row the store cannot read is written whole: from nothing, under TORN
                items, idx = None, e.index
            new = mutate(dict(items or {}))
            if new is None:
                return dict(items or {})
            try:
                self.vars.put(path, new, cas=idx)
                return new
            except Conflict:
                cas_pause(attempt)                   # a random pause, growing: tried again at once, the same writers meet again
                continue
        raise RuntimeError(f"{path}: {retries} conflicts")
```

Тот же цикл, что в `next_epoch` из урока 6, но вынесенный в метод и принимающий **функцию изменения** — мутатор. Дальше в курсе через `write` пойдёт почти каждая запись: назначение, размещение, строки оператора, политики, производные строки. Два решения стоит назвать прямо здесь, остальные — в следующем шаге, который весь про мутатор.

**Строку, которую хранилище не может прочесть, `write` пишет целиком.** `Garbled` (урок 2, шаг 7) — это строка, которая есть, но не читается; мутатор получает пустой словарь, а запись идёт с `cas=TORN` — «я видел нечитаемую». Кто успел её переписать, тот выиграл: `Conflict`, и попытка начинается заново.

**Десять попыток, потом `RuntimeError`.** Меньше, чем двести у эпох, и по причине: здесь конкурентов не может быть много. Контроллеров один-два, и они соперничают за ключ, который больше никто не пишет. Десять конфликтов подряд на таком ключе означают неисправность, а не гонку.

## Шаг 3 — Что делает мутатор

`write` умеет «прочитать — изменить — записать по CAS», и **изменить** — единственная часть, которую он не знает. Её приносит вызывающий, функцией:

```python
def mutate(items: dict) -> dict | None:
    ...
```

На входе — содержимое строки словарём, каким оно лежит в хранилище **прямо сейчас**. На выходе — то, что должно лежать вместо него. Или `None`, если менять ничего не надо.

Самый маленький пример, какой бывает, — счётчик:

```python
def bump(items):
    items["n"] = str(int(items.get("n", 0)) + 1)
    return items

ctl.write("thing/counter", bump)          # +1, атомарно, с повтором при конфликте
```

Суть не в том, что это «колбэк для удобства», а в том, **где** он вызывается: внутри цикла повторов. При конфликте `write` перечитывает ключ и зовёт мутатор **заново, на свежих данных**. Вычисли вызывающий новое значение заранее и передай готовым — повтор записал бы результат, посчитанный по устаревшему снимку, и потерянное обновление вернулось бы через заднюю дверь, мимо CAS.

Отсюда два свойства, и оба видны прямо в строках `write` выше.

**Мутатор получает копию.** `mutate(dict(items or {}))` — не сам словарь и не `None` для отсутствующего ключа. Мутатор всегда видит словарь, пусть пустой, и может менять его как хочет, не портя ничего снаружи. Это убирает две ветви из каждого вызывающего.

**Мутатор, вернувший `None`, отменяет запись.** Вот приём, который стоит понять до конца, потому что он встречается в курсе десятки раз. Мутатор — это место, где принимается решение, и иногда решение оказывается «ничего не надо». `assign_add` для единицы, которая уже в списке. `free_slot` для слота, который уже отпущен. `place` для единицы, которую другой экземпляр разместил, пока мы думали.

Если бы `None` не был предусмотрен, вызывающему пришлось бы проверять условие **до** `write` — то есть читать ключ, проверять, потом вызывать `write`, который прочитает его ещё раз. Между этими двумя чтениями состояние могло измениться, и проверка ничего бы не гарантировала. Внутри мутатора проверка выполняется **на тех данных, которые будут записаны**, — то есть она атомарна с записью.

Возвращается при этом текущее содержимое, а не `None`, — вызывающий получает «вот что там лежит» и обычно строит из него объект. Отмена записи не должна выглядеть как ошибка.

## Шаг 4 — Кто существует

```python
    def workers_seen(self, max_age: float = 45.0) -> dict[str, Heartbeat]:
        """Which workers exist: those that heartbeat recently. Never a list
        the controller keeps — a fact it reads."""
        out = {}
        for hb in self._heartbeats():
            # …by whether its heartbeat CHANGED within `max_age` of this controller's clock (`Eyes`; the thirteenth pass,
            # blocker 4): a worker whose clock runs behind is not taken for gone, nor one ahead for alive
            if self.eyes.fresh(self.sub.heartbeat_key(hb.worker), hb.token, max_age, hb.ts, self.sub.name):
                out[hb.worker] = hb
        return out

    def _heartbeats(self) -> list[Heartbeat]:
        def read():
            out = []
            # One prefix, no filter: `<name>/heartbeats/` holds heartbeats and nothing else.
            for key in self.objects.list(self.sub.heartbeats_prefix()):
                raw = self.objects.get(key)
                hb = parse_heartbeat(key, raw) if raw else None
                if hb is not None:
                    out.append(hb)
            return out
        return self._per_pass(self.sub.heartbeats_prefix(), read, "heartbeats")
```

Читает пульсы `_heartbeats`, один раз за проход (`_per_pass` — память прохода из шага 1): у пульсов свой префикс, `<name>/heartbeats/`, и фильтр по концу ключа не нужен. Разбирает каждый `parse_heartbeat`:

```python
def parse_heartbeat(key: str, raw: bytes, parse=None):
    """The object parsed, or None — skipped, counted, and logged once."""
    try:
        hb = (parse or Heartbeat.from_bytes)(raw)
        # …and its status is a list of OBJECTS (the review's seventh pass, the walk over every reader): an entry that
        # is a word parsed, and raised `AttributeError` in every reader that asks an entry `.get` — `holder_of`, the
        # read model, the running gauge — each a loop over every worker.
        if isinstance(hb, Heartbeat) and not all(isinstance(s, dict) for s in hb.status):
            raise TypeError("a status entry is not an object")
        _named(hb)
    except PARSE_ERRORS:                          # `OverflowError` (`ts: 10**400`) and `RecursionError` too (the ninth review's sweep)
        sub = key.split("/", 1)[0]
        GARBLED[sub] = GARBLED.get(sub, 0) + 1
        if key not in _garbled_keys:
            _garbled_keys.add(key)
            log.warning("%s: heartbeat does not parse; skipped", key)
        return None
    _garbled_keys.discard(key)
    return hb
```

`_named` — проверка десятого ревью: `worker` и `server` пульса должны быть непустыми строками (таблица ниже).

**Heartbeat, который не разбирается, — беда одного воркера, не прохода.** Объект обрывается на полуслове — питание, зомби, писавший в тот же файл до BD, — и `Heartbeat.from_bytes` поднимал `ValueError` посреди `workers_seen`: ни одного воркера контроллер не видел, пока кто-нибудь не удалит объект (ревью платформы, M6; второе ревью). `parse_heartbeat` пропускает такой объект, считает его (`contract.GARBLED[sub]` → `<sub>_heartbeats_garbled` в `/metrics`) и пишет в лог один раз на ключ, пока тот не станет читаться; то же у `builds`, у `heartbeats` консоли и у `resources_seen` ресурса. Тест: `test_placement_decides.py::test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs`.

**Живость — по смене, на часах контроллера, а не по часам воркера** (тринадцатое ревью, блокер 4; решение владельца 4 октября). Первая версия сравнивала `now - hb.ts`: часы контроллера с часами воркера, и при перекосе в минуту живой воркер «молчал», а мёртвый был «жив». Второе ревью (M9) поставило порог — `is_live`: heartbeat из будущего дальше `FUTURE_TOLERANCE` (5 с) живым не считался. Тринадцатое показало, что порог — тот же суд по чужим часам: сервер, чьи часы на 50 с позади, был мёртв, пока работал, и его единицы уезжали. Теперь контроллер помнит, когда **сам** впервые увидел heartbeat таким, какой он сейчас (`self.eyes`, урок 7, шаг 7, «Чьи часы»): метка — `ts` и контрольная сумма байтов (`Heartbeat.token`), не время. Изменился в последние `max_age` секунд по часам контроллера — воркер есть. Того, чего контроллер ещё не видел, он считает только что записанным: новый контроллер выжидает окно, прежде чем назвать кого-то молчащим. `max_age=1e12` по-прежнему значит «перечислить всех, кого видели».

**Перекос — число и тревога, не решение.** Время писателя теперь читается для сдвига часов — там, где перемена замечена (первый взгляд не в счёт: это может быть метка давно умершего): `<sub>_heartbeat_skew_seconds_max` видит часы, ушедшие **вперёд**, `<sub>_heartbeat_skew_seconds_min` — отставшие. Дальше `SKEW_ALARM` — тревога `clock.skew` раз за эпизод (`Controller.say_skews`), в отчёте прохода `clock_skew`. Ничего не переносится. `is_live` остался для тех, у кого нет глаз (разовый взгляд: скан, предложение томов). Тест: `test_review_remainder.py::test_a_writers_clock_ahead_or_behind_neither_holds_nor_drops_it_and_the_skew_is_said`, `test_review_remainder.py::test_a_clock_running_behind_is_a_number_too`.

Перечислить объекты префикса, отобрать heartbeat'ы, прочитать, отбросить те, что не менялись сорок пять секунд. Всё определение «воркер существует» — в этих шести строках, и вторая строка docstring объясняет, почему они такие: **не список, который контроллер ведёт, а факт, который он читает.**

Разница видна, когда что-то ломается. Список пришлось бы пополнять при регистрации и чистить при уходе — то есть иметь протокол регистрации, обработку повторной регистрации, уборку записей о тех, кто ушёл не попрощавшись. Каждый из этих путей может разойтись с реальностью, и когда разойдётся, контроллер будет размещать работу на воркера, которого нет.

Здесь расходиться нечему: воркер, который пишет о себе, — есть; который перестал — через сорок пять секунд по часам контроллера перестаёт быть. Ключ при этом не удаляется, и это намеренно: последний heartbeat умершего воркера остаётся на диске и отвечает на вопрос «что с ним было перед смертью». Из него же новый экземпляр под этим именем берёт `previous_hb` — время последнего сигнала предыдущего, из которого вычисляется измеренное время переключения, — `previous_instance` и `previous_server`, сервер, на котором тот работал: вычитать `previous_hb` из своего `started` можно, только если оба времени — по одним часам. Читает их база воркера, один раз на имя, до своего первого heartbeat'а под ним, и кладёт в каждый heartbeat любой подсистемы (`previous_said`, шаг 9); меряет контроллер (`failover_seconds`, урок 11).

`raw` может оказаться пустым (`if raw`) — между `list` и `get` объект мог исчезнуть. Пропускаем.

## Шаг 5 — Назначение

```python
    def assignment(self, worker: str) -> Assignment:
        items, _ = stored(self.vars, self.sub.assignment(worker), ASSIGNMENTS)
        return self._assignment(worker, items)

    def _assignment(self, worker: str, items) -> Assignment:
        return read_assignment(self.sub.assignment(worker), worker, items)

    def assign(self, worker: str, units: list[str]) -> Assignment:
        def mutate(items):
            rev = self._assignment(worker, items).rev + 1
            return Assignment(worker, sorted(set(units), key=str), rev).to_items(self.sub.assignment(worker))
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))
```

(`stored` — чтение, при котором строка, которую не прочло само хранилище, — битая строка таблицы, а не исключение; урок 7, шаг 4. `to_items` получает ключ, чтобы назвать его, если в списке окажется имя, которое в список не кладут.)

Полная замена списка. `set` убирает дубликаты, `sorted(…, key=str)` даёт устойчивый порядок (по строковому виду, потому что единицы — строки, и числовые идентификаторы сортируются как `"1", "10", "2"`; для хранения это неважно, важна только стабильность). Ревизия растёт.

```python
    def assign_add(self, worker: str, unit: str) -> Assignment:
        """Read-modify-write: two controllers adding different units to one
        worker at once both land."""
        def mutate(items):
            a = self._assignment(worker, items)
            if unit in a.units:
                return None
            if LIST_SEPARATOR in str(unit):                 # never into the list (`Assignment.to_items`): no write either
                UNLISTED.garbled(f"{self.sub.assignment(worker)}#{unit}", f"{LIST_SEPARATOR!r} in its name")
                return None
            return Assignment(worker, sorted(set(a.units) | {unit}, key=str), a.rev + 1).to_items(self.sub.assignment(worker))
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))
```

Добавление **одной** единицы — и docstring объясняет, зачем отдельный метод, когда есть `assign`. Два контроллера, размещающие две разные единицы на один воркер одновременно: с `assign` каждый записал бы свой список, и второй затёр бы единицу первого (его список был прочитан до). С `assign_add` каждый добавляет своё к тому, что нашёл **внутри мутатора**, то есть к свежим данным, — и обе единицы остаются.

Правило, которое из этого следует: *пиши то, что меняешь, а не то, что получилось.* Оно применимо далеко за пределы этого метода.

Имя с запятой в список не попадает вовсе: список хранится строкой через запятую, и `1,9` прочитался бы как `1` и `9` (девятое ревью); такое имя посчитано (`UNLISTED`) и не записано. `if unit in a.units: return None` — тот самый приём. Повторное добавление не создаёт ревизию: проход контроллера, ничего не изменивший, не должен выглядеть как изменение, иначе `assignment_rev` в консоли будет расти сам по себе и потеряет смысл.

`assign_remove` — зеркальный, с той же отменой при отсутствии.

**Строка назначения, которая не разбирается, — беда одного воркера.** В строке одно число, `rev`, и первая версия разбирала его голым `int`. `rev` со словом вместо числа (правка руками, оборванная запись) бросал `ValueError` из `assignments()` — а на нём стоит весь проход контроллера: сверка назначений со строками размещения, каждый перенос, `/where`. Одна строка одного воркера, и ни одна единица подсистемы не размещалась; сам воркер падал на ней каждый проход (шестое ревью, найдено при обходе соседей битой строки слота). Теперь строку читает `read_assignment`:

```python
ASSIGNMENTS = Table("assignment", "read for the units it names")
ASSIGNMENTS_GARBLED, _garbled_assignments = ASSIGNMENTS.counts, ASSIGNMENTS.bad


def read_assignment(key: str, worker: str, items) -> "Assignment":
    """The row parsed — or, when its `rev` does not parse, its units with `rev 0`: counted, and logged once."""
    return ASSIGNMENTS.read(key, lambda: Assignment.from_items(worker, items),
                            Assignment(worker, [u for u in str((items or {}).get("units", "")).split(",") if u]))
```

`Table` — общий читатель строк платформы (`w2cplatform/rows.py`), о нём в конце шага.

То, что строка **решает**, — список `units`, а список имён не может не разобраться. Он читается как есть, с `rev 0`; строка считается (`assignments_garbled` в отчёте прохода и в heartbeat'е воркера) и один раз попадает в лог. Следующая запись контроллера в эту строку пишет её целиком, и `rev` начинается заново — это ничего не стоит: ревизию публикуют, но нигде не сравнивают между записями. Тесты: `test_garbled_rows.py::test_a_garbled_assignment_row_is_that_workers_trouble_and_the_pass_goes_on`, `test_a_worker_whose_own_assignment_row_is_garbled_carries_out_what_it_names`.

**Тот же вопрос — каждой строке хранилища, кто бы её ни читал.** Битая эпоха, потом битый слот, потом битое назначение. Шестое ревью закрыло строки контроллера и воркера, а седьмое нашло тот же отказ в строках, которых таблица не перечисляла: `platform/space`, `<подсистема>/next_id`, числа heartbeat'ов в `/metrics` — и строки подсистем (в М10B одна строка тома гасила пульс всех регистраторов кластера; седьмое ревью, часть 2, блокер 1). Таблица ниже — строки и объекты **платформы**, составленные обходом кода `w2cplatform/`: каждое место, где к прочитанному из `vars` или `objects` применяется `from_items`, `int`, `float`, `json.loads` или обязательный ключ. Правило одно: что строка ещё говорит — используется; строка считается и один раз попадает в лог; проход идёт дальше; и ничто не читается как «нет» только потому, что не разобралось.

**Один читатель на все таблицы** — `w2cplatform/rows.py`. Таблица — это `Table(имя, что значит не прочитать)`. `read(key, parse, default)` вызывает `parse()`. Если разбор бросает одно из `PARSE_ERRORS` — `ValueError` (это и `JSONDecodeError`), `TypeError`, `KeyError`, `AttributeError`, `OverflowError` или `RecursionError`, — строка считается испорченной. `RecursionError` добавлен в восьмом ревью: JSON, вложенный на десять тысяч уровней, помещается в переменную, а `json.loads` на нём сдаётся этим исключением, и оно уходило мимо всех `except`. Тогда возвращается `default`, строка считается **один раз**, пока снова не станет читаться (`counts`, по подсистеме — первому сегменту ключа), и один раз попадает в лог, а её ключ лежит в `bad` для того, кто называет её на странице. Раньше три читателя считали чтения, а не строки: одна строка, прочитанная на каждом проходе, выглядела тысячей строк (седьмое ревью, minor про `SLOTS_GARBLED`, `ASSIGNMENTS_GARBLED` и `HOLDS_GARBLED`). Что значит `default`, решает вызывающий: «не кандидат», «последняя прочитанная», «единица удержана целиком», «настройки, прочитанные последними». Числа в строках и в heartbeat'ах читает `rows.number` через таблицу `field`, и слово, `nan` и `inf` там — «не сказано». Счёт каждой таблицы уходит в heartbeat воркера (`<имя>s_garbled`), а на `/metrics` консоли — как `<подсистема>_worker_<имя>s_garbled{worker}` и `<подсистема>_console_rows_garbled{table}`.

| Строка или объект | Кто читает | Не разбирается — что теперь | Тест |
|---|---|---|---|
| слот `<подсистема>/slots/<имя>` | захват (`_claim_slot`), контроллер (`slots()`) | не кандидат; считается (`SLOTS`, `slots_garbled`) | `test_slot_fence.py::test_one_garbled_slot_row_does_not_leave_a_seeker_nobody_and_is_counted` |
| слот | своя строка: продление, уход (`_own_slot`) | читается как записанная последней; продление пишет её целиком | `test_slot_fence.py::test_a_garbled_slot_row_stops_neither_placement_nor_the_worker_it_names` |
| слот | контроллер: `free_slot` | пишется целиком: отпущен, ничей | `test_garbled_rows.py::test_freeing_a_slot_whose_row_is_garbled_writes_it_released` |
| слот или холд, чей файл не прочло само хранилище (`Garbled`) | захват имени, своя строка, захват и продление места, подменщик, строка списания при захвате (`stored`) | то же, что строка, которая не разбирается: не кандидат, своя — как записанная последней. Двенадцатое ревью, major 19: голое чтение бросало `Garbled` из захвата, и пока файл был оборван, не стартовал ни один процесс подсистемы | `tests/test_garbled_rows.py::test_one_torn_slot_row_does_not_stop_a_process_of_the_subsystem_from_starting` |
| слот зависшего воркера, неподвижный срок | захват без имени и по имени от юнита (`_garbled_stale` и `_held(n, None)`) | не берётся, пока контроллер не перенёс бы его единицы. Двенадцатое ревью, major 4: строка стоит и у зависшего, и её брали вместе с его единицами | `tests/test_slot_fate.py::test_a_garbled_slot_row_of_a_hung_worker_is_not_taken_when_it_stands_still` |
| назначение `<подсистема>/workers/<имя>`: `rev` | контроллер, воркер (`read_assignment`) | читается список единиц, `rev 0`; одна строка — один счёт | `test_garbled_rows.py::test_a_worker_whose_own_assignment_row_is_garbled_carries_out_what_it_names` |
| назначение: имя, которое не id | `SpecController.redistribute` | это имя пропускается и считается; остальные единицы уходящего слота переезжают (обрывало весь шаг) | `test_row_reader.py::test_a_name_in_an_assignment_that_is_no_units_id_stops_no_move` |
| холд `<подсистема>/holds/<место>` | захват места (`read_hold`, таблица `HOLDS` контракта) | не кандидат; файл, который даже не JSON, — тоже | — |
| эпоха `<подсистема>/epoch/<единица>` | `next_epoch`, вызовы `take_epoch`, `Lease.renew`, консоль | отказ одной единицы или команды; эта аренда отсечена; события не помечаются отсечёнными. С десятого ревью `Lease.renew` ловит `PARSE_ERRORS`: `epoch: 1e999`, записанный правкой файла руками, давал `int(inf)` → `OverflowError` мимо `(ValueError, KeyError, TypeError)`, а значит из `renew_leases` — у воркера не продлевалась ни одна аренда | `test_epoch_refused.py`, `test_garbled_rows.py::test_a_lease_whose_epoch_row_stops_parsing_is_lost_alone`, `test_one_bad_element.py::test_infinity_in_a_rows_integer_stops_no_workers_pass_and_no_lease` |
| heartbeat (объект) | `workers_seen`, `builds`, `heartbeats`, `resources_seen` (`parse_heartbeat`) | пропускается, считается; статус, в котором не объекты, — тоже (раньше `AttributeError` у каждого, кто спрашивает `.get`); после девятого ревью — и `[` в десять тысяч уровней (`RecursionError`), и `ts: 10**400` (`OverflowError`): свой список исключений `parse_heartbeat` их пропускал, теперь там `PARSE_ERRORS`. После десятого ревью — и имена: `worker` и `server` пульса воркера и ресурса — непустые строки, иначе пульс не разбирается (`contract._named`). `"server": ["srv-x"]` разбирался, и падал каждый, кто кладёт его ключом или сортирует: `/servers`, `/unplaceable`, `/drain`, `/metrics` консоли, `restore` и зеркало ресурса, `ensure_reach`, `redistribute`, `ensure_home` контроллера | `test_placement_decides.py::test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs`, `test_row_reader.py::test_a_status_entry_that_is_not_an_object_or_names_no_unit_stops_no_reader`, `test_garbled_rows.py::test_a_heartbeat_with_a_number_past_any_number_or_nested_ten_thousand_deep_stops_no_placement`, `test_one_bad_element.py::test_a_heartbeat_whose_server_or_worker_is_no_name_is_that_heartbeats_and_no_route_falls` |
| heartbeat ресурса `platform/resources/<сервер>/heartbeat` | `Controller.resource_state` | ресурс известный и не живой — `silent`, а не `unknown`, если только его строка двери (`at`) не свежая. Двенадцатое ревью, minor: `ts: NaN` был `unknown`, и единицы его сервера ждали навсегда | `tests/test_slot_fate.py::test_a_resource_heartbeat_that_does_not_parse_is_a_silent_server_not_an_unknown_one` |
| строка двери ресурса `platform/doors/<сервер>` | объекты кластера через ресурс (таблица `door`) | объекты этого сервера не спрашиваются, пока строку не починят | — |
| регистрации воркеров у ресурса: каталог `.workers`, блокировки и `.json` рядом с ними | ресурс (`presence_here`) | не «не числится»: каталог не читается — `presence_error` и нет списков; блокировка не открылась или `.json` живой блокировки не читается — счёт `presence_unread`; живой держатель узнаётся по имени блокировки (`running_instances`). Двенадцатое ревью, блокер 3: всё это читалось пустым списком, и слот зависшего освобождался | `tests/test_slot_fate.py::test_what_the_resource_cannot_read_of_its_workers_is_not_taken_for_their_end` |
| `schema` и `build` в пульсе | `/schema` (`builds`), `set_schema` | схема, которая не читается (`1e999`), — `null`, «не известна»: процесс в списке, `can_raise_to` стоит там, где хранилище, поднять схему нельзя, пока он жив. `build` списком — `?`; строка `platform/schema` словом — `version: null` (десятое ревью, обход маршрутов) | `test_one_bad_element.py::test_schema_lists_a_process_whose_schema_does_not_read_and_raises_past_nobody` |
| элемент статуса без `id` | `read_model` (список консоли), метрики из спецификации | ничего не говорит о единице, пропускается | `test_row_reader.py::test_a_status_entry_that_is_not_an_object_or_names_no_unit_stops_no_reader` |
| числа внутри heartbeat'а | `capacity_of`, `headroom`, `failover_seconds` (`_number`) | «не сказал»: ёмкость по умолчанию. С девятого ревью `_number` читает через `rows.number`: `headroom: Infinity` (JSON его читает) давал `int(inf)` → `OverflowError` мимо своего `(ValueError, TypeError)`, и не размещалась ни одна единица; `inf` больше не число, счёт — один раз на поле | `test_garbled_rows.py::test_a_heartbeat_whose_numbers_are_words_is_that_workers_trouble`, `test_a_heartbeat_with_a_number_past_any_number_or_nested_ten_thousand_deep_stops_no_placement` |
| числа heartbeat'ов и отчёта прохода на `/metrics` | `SpecConsole.metrics_text` и метрики, объявленные спецификацией (`metrics.py`; `rows.number`) | «не сказано»: 0 или -1 для возраста; страница целая и вся из чисел | `test_row_reader.py::test_one_word_in_one_heartbeat_field_does_not_take_the_metrics_page` |
| heartbeat ресурса без `url` | `Resource.mirror`, `restore` | такой сосед не берёт и не отдаёт; `restore` при старте ещё и в своём `try` (процесс падал на каждом старте) | `test_row_reader.py::test_a_resource_comes_up_over_a_peer_whose_heartbeat_names_no_address` |
| схема `platform/schema` | `check_schema` | работающий держит последнюю прочитанную; новый не стартует (урок 17) | `test_lesson1_platform.py::test_a_schema_row_that_does_not_parse_fences_nobody_who_is_running_and_starts_nobody_new` |
| `platform/drain`, `platform/decommission/<сервер>` | контроллер, консоль (таблицы `drain`, `decommission`) | слив — как будто не сливается никто, пока строку не перепишут; списание — как будто оно ещё стоит, пока его не перепишут или не отзовут | — |
| метки сервера `<подсистема>/servers/<сервер>` | контроллер (таблица `server_labels`) | сервер держит метки, прочитанные последними; не прочитав ни разу, не берёт единиц, которым нужна метка; и ничего с него не уезжает | — |
| размещение `<подсистема>/placement/<единица>` | `placement()` и всё, что на нём стоит | читается `worker`; `at` и `rev` — нули (урок 10). С десятого ревью — и `rev: 1e999` от правки руками: `int(inf)` давал `OverflowError` мимо `(ValueError, KeyError, TypeError)`, и `placement()` падал под каждым шагом прохода и каждым маршрутом | `test_garbled_rows.py::test_a_garbled_placement_row_still_says_where_its_unit_is_and_stops_no_pass`, `test_one_bad_element.py::test_a_placement_row_counting_past_any_number_still_says_where_its_unit_is` |
| строка единицы | контроллер: `units()`, `_parsed` | пропускается, считается (урок 10) | `test_placement_decides.py::test_a_row_that_does_not_parse_is_one_unit_nobody_serves_and_the_three_steps_run_each` |
| строка единицы | воркеры: цикл по своим единицам (`Worker.row_garbled`) | единица идёт по строке, прочитанной последней; остальные идут. С десятого ревью у каждого воркера курса — `PARSE_ERRORS`, а не свой кортеж: число `1e999` в целом поле (`int(inf)`, `OverflowError`) и поле, вложенное глубже, чем читает JSON (`RecursionError`), проходили мимо, и проход воркера кончался на этой строке | `test_garbled_rows.py::test_the_holder_goes_on_with_the_row_it_read_last_and_runs_the_rest` и три соседних, `test_one_bad_element.py::test_infinity_in_a_rows_integer_stops_no_workers_pass_and_no_lease` |
| значение поля-списка (`labels` и другие поля типа `list`) | все читатели строки (`Field.parse`: строка делится по `,`) | значение с запятой отказывается при записи (`SubsystemSpec.refuse`, 400); хранится строкой через запятую — её читает каждый читатель | `test_one_bad_element.py::test_a_value_of_a_list_field_with_a_comma_is_refused_and_the_joined_string_is_taken` |
| строка единицы: её `labels` | ворота `/events` консоли (`SpecConsole.dispatch`, `may_see`, таблица `unit`) | события этой единицы не показываются гранту по меткам — какие у неё метки, не известно; грант на саму единицу и на весь кластер их видит; в ответе — `withheld` по единицам; считается (`<подсистема>_console_rows_garbled{table="unit"}`). Раньше — 400 на всю ленту | `test_console_gate.py::test_one_garbled_camera_row_costs_that_cameras_events_and_not_the_timeline` |
| строка события в ответе ресурса: `t`, `epoch`, `unit`, `server`, `id`, `bucket` | слияние `/events` (`eventdatabase._event_line`, таблица `peer_event`) | строка берётся в тех типах, в которых её проверили (`"t": "1700000000"` — число), а не как пришла: строка рядом с числами роняла сортировку слияния, список в `unit` или `id` — множества, по которым слияние отсекает и убирает копии; строка, которая не переводится, пропускается и считается | `test_row_reader.py::test_a_line_whose_values_only_convert_is_merged_as_converted_and_stops_no_timeline`, `test_one_resource_answering_another_shape_costs_its_window_and_not_the_merge` |
| счётчик `<подсистема>/next_id` | `SpecController._next_id` | следующий номер — за наибольшим id, удалённые тоже; строка пишется целиком (отказывал в создании любой единицы) | `test_row_reader.py::test_a_garbled_id_counter_gives_the_next_number_past_the_largest_id` |
| отчёт прохода (объект) | `pass_report`, `pass_once` | `None`, проход пишет его заново; `failures: 1e400` — счёт с нуля (было `int(inf)` → `OverflowError` до первого шага, а отчёт пишется только в конце прохода: контроллер подсистемы не размещал ничего навсегда — девятое ревью, обход) | `test_garbled_rows.py::test_a_garbled_pass_report_does_not_stop_the_controllers_loop`, `test_a_pass_report_counting_past_any_number_stops_no_pass_and_a_step_that_fails_every_pass_is_said_once` |
| срез снимка (объект) | `snapshot_age` | возраст «старше некуда» (урок 19); `ts` `nan`/`inf` — тоже (`finite`, восьмое ревью). `ts` из будущего дальше `FUTURE_TOLERANCE` (5 с) — тоже «старше некуда», а не возраст 0 (девятое ревью, minor); посчитано (`fields_garbled`), а опережение — в `<sub>_heartbeat_skew_seconds_max` | `test_garbled_rows.py::test_a_garbled_snapshot_shard_makes_the_published_copy_old_and_never_fresh`, `test_a_snapshot_written_by_a_clock_running_ahead_is_not_fresh_and_its_lead_is_measured` |
| список сборки блобов `<подсистема>/sweep` | `put_blob`, `sweep_blobs`, `/metrics` | списка нет, по его слову ничего не удаляется; элемент, который не digest, не метётся (`blob_key` ронял каждую сборку) | `test_garbled_rows.py::test_a_garbled_sweep_list_stops_no_upload_and_deletes_nothing_on_its_word`, `test_row_reader.py::test_a_sweep_list_entry_that_is_no_digest_stops_no_reclaiming` |
| ключ идемпотентности `<подсистема>/idem/*`: `at` | `IdempotencyKeys.prune` | возраст неизвестен — строка остаётся, считается; остальные чистятся (обрывало чистку и POST, который её запустил) | — |
| дни событий `<подсистема>/retention[/<единица>]` | ресурс: `retain` (таблица `retention`) | бакеты этой единицы не метутся, пока строку не починят (урок 14) | `test_garbled_rows.py::test_one_units_garbled_retention_row_keeps_that_units_buckets_and_the_rest_are_swept` |
| строка таблицы, которую спецификация объявила удерживающей (`holds:`), и строка единицы, о которой она говорит | ресурс: `retain` (`holds.py`, таблицы `hold` и `unit_row`) | удержание держит свою единицу настолько, насколько читается его отрезок времени; единицу, чью строку не прочесть, держит каждое читаемое удержание — как ничью | — |
| ватерлиния `platform/space` | `Resource.relieve` (`space_settings`) | число — из прочитанного последним или умолчание; сказано в heartbeat ресурса (`space_garbled`) | `test_row_reader.py::test_a_garbled_watermark_row_acts_on_the_settings_read_last_and_says_so` |
| зеркало `platform/mirror`: `copies` | `Resource.mirror` | одна копия | `test_row_reader.py::test_a_mirror_whose_copies_do_not_parse_mirrors_to_one_peer` |
| строка ведра под длинным опросом | `longpoll.Watch._kinds` | пропускается, как рваная. Кортеж `(ValueError, AttributeError)` пропускал `RecursionError`: осмотр падал, размеры не двигались, и каждый следующий читал ту же строку и падал снова — длинный опрос мёртв для всех (десятое ревью, обход) | `test_one_bad_element.py::test_a_bucket_line_nested_past_jsons_depth_does_not_stop_the_watch` |
| листинг пира `/mirrored/<сервер>` в `restore` | `PeerClient.mirrored` (`Listing.skipped`), `Resource._restore` | пропущенные строки и пути не вёдер считаются в `left`: пир не «отдал всё», его спрашивают снова, `restore_left` не падает, пока пир другой сборки так отвечает (девятое ревью, minor) | `test_one_bad_element.py::test_a_restore_whose_listing_skipped_lines_asks_that_peer_again` |
| имя из строки как значение метки на `/metrics` | `SpecConsole.metrics_text`, метрики из спецификации | значение экранируется одной функцией (`w2cplatform.console.label`: `\`, `"`, перевод строки); имя `7"x` ломало строку, и Prometheus отвергал весь скрейп. Новые имена с `"`, `|` и управляющими символами отказываются при создании (`doors.unnamable`, урок 10) | `test_row_reader.py::test_a_name_with_a_quote_or_a_newline_is_escaped_on_every_metrics_page` |

**Строки подсистем читает тот же читатель.** Тома и удержания записи, заявки, строки в каталоге автоматизации, описания устройств, ответы демона архива, книги домена — это строки и объекты подсистем, и каждая читает их тем же `rows.Table`, по тому же правилу: что строка ещё говорит — используется, строка считается и один раз попадает в лог, проход идёт дальше. Их перечень — в уроках М10B и М12, рядом с кодом, который их читает. Платформе из него не нужно ничего: она даёт читателя, а не знает читаемое.

**Обход девятого ревью: каждый свой кортеж исключений вместо `PARSE_ERRORS`.** Ревью нашло один, обход нашёл остальные. Безопасен узкий кортеж только там, где разбирается строка хранилища: значения строк — всегда строки, а `int()`/`float()` строки бросают только `ValueError`. Там, где разбирается настоящий JSON — пульс, ответ двери, тело запроса, свой файл, — `1e400` приходит как `inf` (`int()` бросает `OverflowError`), `10**400` как целое (`float()` бросает `OverflowError`), а `[` в десять тысяч уровней даёт `RecursionError`. В платформе закрыты: `parse_heartbeat`, `SpecController._number`, `pass_once`/`pass_report`, `units`/`_parsed`, `_sweep_list`, чтение строки на воротах консоли; `rows.finite` превращает `OverflowError` в `ValueError`, так что и вызывающие с `(TypeError, ValueError)` не пропускают `10**400`. Строку ведра длинного опроса, которую тот обход оставил открытой, закрыл обход десятого ревью (строка выше).

Только свою строку или свой запрос останавливают, громко, с ошибкой этому запросу: `Mount.schema_route` (`GET /schema`), правка и удаление строки, которая не разбирается (`create`, `update`, `delete`, `put_blob` консоли), `IdempotencyKeys.claim` повторённого запроса. И остаются осознанные отказы: `set_schema` на битой строке схемы бросает исключение оператору — поднять версию поверх строки, которую не прочитать, значит не знать, не понижаешь ли.

## Шаг 6 — Чтение слотов и назначений

```python
    def assignments(self) -> dict[str, Assignment]:
        out = {}
        for path in self.vars.list(self.sub.name + "/workers/"):
            worker = path.rsplit("/", 1)[1]
            out[worker] = self.assignment(worker)
        return out
```

Все назначения подсистемы — перечисление плюс чтение каждого. `N + 1` обращений к хранилищу, и это осознанная цена: на коробке — это `listdir` и `N` открытий файла, в кластере — `N + 1` запросов к сокету демона своего сервера, при десяти воркерах незаметно. В проходе контроллера память прохода (шаг 1) делает их одним чтением на ключ; а в М11 у той же выборки появляется кэш на время (`Directory`) — потому что её дёргает каждый запрос «где единица 7», а не потому, что дорого контроллеру.

`slots()` устроен так же. Оба метода — чистое чтение: контроллер смотрит на мир и ничего про него не помнит.

`released_slots()`, `free_slot()` и `slot_fate()` разобраны в уроке 7; здесь достаточно заметить, что `free_slot` — единственный метод контроллера, который пишет **слот**, и это не противоречит «слоты захватывают воркеры»: захват — воркеров, освобождение снаружи — контроллера, по фактам, которые сообщает сервер, или по списанию сервера оператором.

**Слот, о котором судить нельзя, не молчит: он считается, и о нём звучит тревога** (двенадцатое ревью, блокер 5, воспроизведено пробой ревьюера). Шаг прохода `release_unlisted` спрашивает `slot_fate` о каждом слоте (урок 7, шаг 7) и делает то, что из ответа следует:

```python
    def release_unlisted(self) -> dict:
        released, hung, moved, unjudged, units, doubted = {}, {}, [], {}, 0, {}
        for worker, (fate, server, why) in self.fates().items():
            if fate == "hung":
                hung[worker] = why
            elif fate == "hung_moved":
                moved.append(worker)
            elif fate == "unsure_moved":
                doubted[worker] = why
            elif fate == "release" and self.free_slot(worker):
                released[worker] = why
                log.warning("%s: slot %s released: %s", self.sub.name, worker, why)
                self.journal.say("worker.released_by_controller", sub=self.sub.name, worker=worker, server=server, why=why)
            elif fate in ("wait", "unsure") and (n := len(self.assignment(worker).units)):
                unjudged[worker], units = why, units + n
        self._said_unjudged(unjudged)
        return {"released": released, "hung": hung, "hung_moved": self._said_hung(hung, moved), "unjudged": unjudged,
                "units_unjudged": units, "unsure_moved": self._said_unsure_moved(doubted)}
```

Ветка `wait`/`unsure` — ради единиц сервера, о котором ресурс ничего не сказал или не смог сказать: они ждут, и это должно быть видно. Такой слот с единицами попадает в `unjudged` со своим `why`. `_said_unjudged` говорит тревогу `worker.unjudged` один раз за эпизод, а «can be judged again» — в лог. Отчёт прохода несёт `workers_unjudged` и `units_unjudged`, консоль — `<p>_workers_unjudged` и `<p>_units_unjudged` на `/metrics`. Тут же второе число: перенос зависшего воркера по пределу — не только тревога в журнале, отчёт считает его с тех пор, как хранилище новое (`workers_hung_moved_total`, на `/metrics` — `<p>_workers_hung_moved_total`), по одному на эпизод (двенадцатое ревью, minor). Тесты: `tests/test_slot_fate.py::test_a_controller_started_after_a_server_died_moves_its_units` (вторая половина: тревога одна на два прохода), `tests/test_slot_fate.py::test_the_decommission_door_reads_its_body_as_every_door_and_a_refusal_is_journalled` (счётчик).

**`unsure` после предела зависания — уже не «судить нельзя», а перенос** (решение владельца о «середине» для `hung`, применённое к `unsure`; урок 7, шаг 7): иначе слот в `unsure` оставался бы в `unjudged` вечно — тревога есть, единицы не исполняет никто. Через `hung_move_after` после конца слота `slot_fate` отвечает `unsure_moved`. Такой слот в `unjudged` не попадает, его единицы уносит `redistribute`, а тревогу говорит отдельная функция, один раз за эпизод, как `_said_hung` для `hung_moved`:

```python
    def _said_unsure_moved(self, moved: dict) -> list:
        gone = self.__dict__.setdefault("_unsure_moved", set())
        new = sorted(set(moved) - gone)
        for w in new:
            log.error("%s: %s", self.sub.name, moved[w])
            self.journal.say("worker.unsure_moved", ALARM, sub=self.sub.name, worker=w, after=self.hung_move_after,
                             why=moved[w])
        gone.clear(); gone.update(moved)
        return new
```

Что она вернула — воркеры, перенесённые в этом эпизоде впервые, — отчёт прохода считает в `workers_unsure_moved_total`, а консоль отдаёт как `<p>_workers_unsure_moved_total`. Тест: `tests/test_slot_fate.py::test_an_unsure_worker_keeps_its_units_and_name_until_HUNG_MOVE_AFTER_then_they_move_with_an_alarm`.

**Состояние ресурса — четыре слова, а не три.** `Controller.resource_state(server)` отвечал `live`, `silent` или `unknown` по heartbeat'у ресурса. Теперь, где heartbeat не свежий, он спрашивает второе мнение — строку двери ресурса в хранилище, `at` на `platform/doors/<server>`, которую ресурс переписывает каждые `ALIVE_EVERY` (15 с). Строка свежая — `unreachable`: ресурс есть, не виден только его heartbeat, и ничего не переносится. Строка тоже старая — `silent`. Heartbeat, который лежит и не разбирается, — тоже `silent`, а не `unknown`. Раньше дверь, закрытая для контроллера, читалась как молчащий сервер, а контроллер, запущенный после смерти сервера, не видел его молчания вовсе (двенадцатое ревью, блокер 5, major 9 и minor; подробности — урок 7, шаг 7). Тесты: `tests/test_slot_fate.py::test_a_resource_whose_door_cannot_be_reached_is_not_a_silent_server`, `tests/test_slot_fate.py::test_a_resource_heartbeat_that_does_not_parse_is_a_silent_server_not_an_unknown_one`.

## Шаг 7 — Воркер: что он помнит

```python
    def __init__(self, sub: Subsystem, name: str | None, vars_: Variables, objects: ObjectStore,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 instance: str | None = None, slot_ttl: float = 45.0, resource_root: str | None = None,
                 env: dict | None = None):
        self.sub, self.vars, self.objects = sub, vars_, objects
        …
        self.resource_root = runtime.events_root(os.environ if env is None else env, resource_root)
        self.schema_seen = check_schema(vars_)    # a build older than the store does not run at all; kept for `renew_slot`
        self.clock, self.wall = clock, wall
        self.started_wall = wall()                # this instance's start, by this box's wall clock: `started` in the heartbeat
        self.lease_ttl, self.lease_margin = lease_ttl, lease_margin
        …
        self.unconfirmed_max: float | None = getattr(self.spec, "unconfirmed_max", 0.0)
        self.epochs: dict[str, int] = {}          # unit -> epoch this worker holds
        self.leases: dict[str, Lease] = {}
        …
        self.instance = instance or f"{runtime.box(os.environ)}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.slot_ttl = slot_ttl
        self.slot: Slot | None = None
        self.name = name                          # None until claim_slot(); a fixed name is a slot claimed by that name
        self.seeking: str | None = None
        self.given: str | None = None
        …
        self.hold: str | None = None              # the PLACE this worker took, if its subsystem has places to take
        …
```

Воркер живёт в своём файле, `w2cplatform/worker.py`: класс большой — захват имени и места (урок 7), ворота, «подменщик», рантайм (шаг 9) и семейство просьб (урок 14), — а контроллер остаётся в `contract.py`. В отличие от контроллера, воркер **помнит**, и стоит точно назвать что: две карты — какую эпоху он держит на каждую единицу и какая у неё аренда — плюс свой слот, свой экземпляр, место, если он его взял, и то, что связано с именем: какое имя ему дал юнит (`given`) и не отдал ли он его (`seeking`, шаг 8). `unconfirmed_max` — потолок неподтверждённой записи данных (урок 6, шаг 8а), и он не память и не настройка процесса: его говорит спецификация подсистемы, `lease: {unconfirmed_max: forever | <секунды> | off}`, которую называет класс воркера подсистемы (`spec`). Нет спецификации или ключа — 0, строго; переменной окружения для потолка нет: ослабить «один писатель» может только объявление. И больше ничего.

Два поля — не память, а сведения о самом процессе. `resource_root` — дерево ресурса своего сервера, куда идут события воркера (`observe`, шаг 9) и его журнал: что дал вызывающий, иначе `RESOURCE_ROOT`, иначе `<PLATFORM_DIR>/events` (`runtime.events_root`, урок 7, шаг 9). Ставит его база, до захвата имени, так что подсистема не может о нём забыть. `started_wall` — когда экземпляр стартовал, по настенным часам своей коробки: `started` в heartbeat'е (шаг 9).

Ключевое: он **не помнит назначения** и не кэширует строки. Каждый проход начинается с чтения. Это дословно правило из М9, урока 6 — *желаемое персистентно, фактическое выводится*, — и именно оно делает перезапуск безопасным: свежий процесс ничего не знает и всё выясняет заново.

Карты эпох и аренд — не исключение из правила, а его следствие. Эпоха, которую он взял, — это не конфигурация, а **факт о нём самом**: «я — тот, кто сейчас пишет эту единицу». Потеряв память, он потеряет и это право — и возьмёт новую эпоху, что и правильно, потому что новый процесс — новый писатель.

`instance` — коробка (`runtime.box`: `BOX_ID`, идентификатор машины или имя хоста, урок 7, шаг 9), pid и шесть случайных символов. Случайный хвост нужен, потому что pid переиспользуются: перезапущенный процесс может получить тот же pid на том же хосте, и без хвоста старая строка слота выглядела бы как своя.

`name` может быть `None` до захвата (урок 7). Именованный воркер (`%i`) получает имя сразу и всё равно проходит через захват — просто с предпочтением.

## Шаг 8 — Ворота

```python
    def take_epoch(self, unit: str) -> int:
        """Called when the worker STARTS a unit: a new epoch, by CAS, and a
        lease on it. A second worker starting the same unit gets the next
        number, and the first one's lease will fence on renewal."""
        if self.seeking is not None:
            raise NoSlot(f"{self.instance} gave slot {self.seeking} up and holds no other: no epoch for {unit}")
        …
        if self.step_abandoned():
            raise NoSlot(…)
        …
        if self.assigned_now is not NEVER_READ and (self.assigned_now is None or str(unit) not in self.assigned_now):
            raise NotReadThisPass(…)
        epoch, _ = next_epoch(self.vars, self.sub.epoch_key(unit))
        self.epochs[unit] = epoch
        self.leases[unit] = Lease(self.vars, self.sub.epoch_key(unit), epoch, self.lease_ttl, self.lease_margin, self.clock,
                                  self.unconfirmed_max)
        return epoch
```

Три отказа сначала: имя отдано и другого нет (шаг 8, ниже), шаг пережил своего подменщика, единицы нет в назначении, прочитанном последним, — все три разобраны в уроке 7, шаг 7. Потом четыре строки, соединяющие два механизма урока 6: взять номер и **тут же** завести на него аренду. Раздельно их не берут нигде — эпоха без аренды была бы правом без срока.

Слово STARTS в docstring выделено не зря. Эпоха берётся, когда воркер **начинает** держать единицу, а не когда перезапускает уже идущую. Разница проявится в М10B: правка камеры перезапускает конвейер, сохраняя эпоху (тот же писатель, тот же каталог), а настоящий старт берёт следующую (новый писатель — новый каталог).

```python
    def may_act(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_act()

    def may_write(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_write()
```

Два вопроса аренды из урока 6, шаг 8а, — теперь на единицу. **Действие** спрашивает `may_act`: просьба, которую держатель исполняет (`Worker.requests`, урок 14), команда устройству, срабатывание сценария. **Данные** спрашивают `may_write`: подсистема, поднимающая работу единицы, пишущая её события, — шире ровно на аренду, истёкшую при молчащем хранилище, и только если спецификация подсистемы подняла потолок, `lease.unconfirmed_max`, выше нуля. Единица, на которую аренды нет, — не наша: оба вопроса для неё `False`. Никаких умолчаний.

```python
    def renew_leases(self) -> list[str]:
        """Returns the units whose lease was lost — fenced or expired."""
        self._loop_renewed = self.clock()         # what the stand-in measures a hung step's danger from
        lost = []
        for u, lease in list(self.leases.items()):
            errors = lease.store_errors
            if not lease.renew():
                lost.append(u)
            if lease.store_errors > errors:
                self.unanswered += 1              # the store did not answer this one (`unanswered`)
        return lost
```

(Первая строка запоминает, когда цикл продлевал сам, — `_loop_renewed`, ниже; `unanswered` считает продления, на которые хранилище не ответило.)

Продлить все и вернуть **потерянные**. Обратите внимание, что метод не решает, что с ними делать, и даже не различает причины — отсечена аренда или просто истекла. Решает шаг аренд той же базы, `lease_pass` (шаг 9), и решает одинаково для всех подсистем: потерянная аренда — дело одной единицы, её работа останавливается и эпоха отдаётся; экземпляр целиком огораживает только строка слота, которая называет другого. А что значит «остановить единицу» — оборвать конвейер, закрыть файл, забыть задачу, — знает только подсистема: это её крючок `stop_unit`.

Это и есть граница между базой и наследником, проведённая по месту: **база решает жизненный цикл — по общим правилам и одинаково для всех; наследник — что значит его единица.**

**Цикл, который работает, — тот же, что продлевает.** Шаг, повисший на хранилище или на внешней системе — проход, прокачка, вызов движка подсистемы (в М10B — регистратора в `obsd`), — перестаёт и продлевать, и через TTL единицы ушли бы соседу, хотя процесс жив и вот-вот вернётся (обратная связь DD). Поэтому каждый шаг цикла отмечает начало и конец (`with self.guarded("pass")`), а рядом работает **«подменщик»** (`start_stand_in`): раз в `STAND_IN_WAKE` (2 с) он смотрит, не висит ли шаг дольше половины того, что позволяет аренда (`stand_in_after()`, 12,5 с при TTL 30 и запасе 5, — от более раннего из начала шага и последнего продления циклом), и если висит — продлевает аренды, строку слота и место (холд) — строку и холд по CAS и только пока они называют этот экземпляр, по тем же правилам, что цикл. Не дольше `STAND_IN_FOR` (5 минут): шаг, зависший навсегда, не держит единицы вечно, и после этого они честно уходят. Огороженного он не оживляет (`may_stand_in`), слот, занятый другим экземпляром, не переписывает, отпущенную аренду не продлевает; в heartbeat — `stand_in_renewals`. Тесты: `test_stand_in.py` на воркере `testsub` — в том числе настоящий `run` базы с настоящим потоком подменщика и проходом, повисшим дольше аренды (`test_the_loop_has_a_stand_in_for_a_pass_that_hangs`). Что каждый вид воркера М10B идёт тем же циклом, показывает сама подсистема (`tests/test_vms_worker_loops.py`).

**Подменщик повторяет последний heartbeat цикла — и говорит, что это повтор.** Строить heartbeat самому — значит читать состояние, которое висящий цикл меняет на своём потоке. Но молчание heartbeat'а единицы переносит: через `lost_after` (45 с) контроллер и читатели держателя считают его мёртвым — в М10B регистраторы теряли бы раздачу, с которой пишут, — и контроллер отдаёт единицы другому. И всё это при продлённых арендах: пять минут подменщика кончались бы на сорок пятой секунде (проход масштаба после восьмого ревью). Поэтому `Worker.heartbeat` запоминает, что написал цикл (`_last_heartbeat`: статус, поля, `ts`). Пока подменщик стоит за шаг и уже подтвердил в этом шаге, что слот — этого экземпляра, он пишет heartbeat всякий раз, когда последнему исполнилось `STAND_IN_HEARTBEAT` (10 с — ритм цикла) (`_stand_in_heartbeat`). Что ему можно сказать, решено так: только то, что сказал цикл. Тот же статус и те же поля, новый `ts` и `stood_in` — шаг, сколько он идёт и `as_of`, `ts` heartbeat'а, чей это статус. Свой статус он не собирает: это было бы вторым писателем состояния цикла. Пустой не шлёт: пустой сказал бы каждому читателю, что у единиц нет держателя, — ровно тот отказ, ради которого всё это сделано. Читателю, которому нужно «жив, и где раздача», этого хватает. Тот, кому важна свежесть статуса, читает `as_of`. Цена сказана прямо: конвейер, упавший под висящим шагом, в повторённом статусе — `running`, пока цикл не вернётся, но не дольше `STAND_IN_FOR`; потом подменщик уходит, heartbeat стареет, единицы честно уходят. Запись — под замком (`_heartbeat_lock`): свежий heartbeat цикла подменщик старым статусом не перезаписывает, а пока цикл сам пишет, подменщик молчит. Тесты: `test_stand_in.py::test_a_hung_step_does_not_make_the_holder_look_dead_and_the_heartbeat_says_whose_words_it_repeats` — минута висящего прохода, и heartbeat ни разу не старше `lost_after`; `…::test_the_stand_in_says_no_heartbeat_over_a_fresh_one_nor_under_a_name_another_instance_took`; `…::test_the_loops_stand_in_says_its_last_heartbeat_again_for_a_pass_that_hangs` — настоящий `run` с настоящим подменщиком: в повисшем проходе heartbeat под именем воркера передатирован, и `stood_in` называет проход.

**Подменщик смотрит, движется ли цикл, а не сколько идёт шаг.** `STAND_IN_FOR` отсчитывался от начала шага: цикл, вернувшийся из одного долгого шага в другой и ничего не продливший, получал ещё пять минут, и так сколько угодно (пятое ревью). Теперь срок считается от последнего продления **циклом** (`_loop_renewed`): новый шаг его не обнуляет, и в логе видно оба числа — сколько идёт шаг и сколько цикл ничего не продлевал. Холд подменщик продлевает, только если подсистема говорит, что за этот шаг место стоит держать (`may_stand_in_hold()`; по умолчанию да). Регистратор отвечает «нет», пока его движок молчит: шаг, застрявший на демоне, который не отвечает, ничего не пишет, а пять минут холда сетевого тома — пять минут, когда его не возьмёт коробка с живым демоном (М10B, урок 10, шаг 10). Продление холда, которое подменщик всё-таки сделал, сообщается подсистеме с отметкой времени до запроса (`note_hold_confirmed`), и регистратор проверяет по ней свои кадры. Тесты: `test_stand_in.py::test_STAND_IN_FOR_counts_from_the_loops_last_renewal_and_a_new_step_does_not_start_it_again`, `test_the_stand_in_does_not_hold_the_place_for_a_step_on_a_silent_engine_and_says_what_it_renewed`.

**Пять минут не начинаются заново от продления внутри шага, который потом повис.** Шаг аренд сначала продлевает, потом работает. Повиснув там, цикл по собственному счёту «продлевал только что», и каждый такой шаг получал свои пять минут: шесть подряд держали единицы и место 1680 секунд (шестое ревью; симуляция). Теперь `STAND_IN_FOR` идёт от продления перед **первым** шагом, за который пришлось подменять (`_stood_in_since`), и начинается заново только после шага, в котором цикл продлил сам и вернулся раньше, чем понадобился подменщик (`guarded`):

```python
        quiet = now - min(mark["at"], self._loop_renewed)
        if quiet <= self.stand_in_after():
            return False
        since = self._stood_in_since if self._stood_in_since is not None else now - quiet
        if now - since > self.STAND_IN_FOR:
            mark["done"] = True
```

Цикл, который виснет в каждом шаге аренд, теряет единицы через пять минут и срок аренды, а не держит их вечно. Тест: `test_stand_in.py::test_STAND_IN_FOR_is_not_started_again_by_a_renewal_inside_the_step_that_then_hangs`. У регистратора к этому добавлены два правила про холд сетевого тома (М10B, урок 10, шаг 3): подменщик не продлевает его, пока проход нашёл движок молчащим, а сам цикл продлевает через молчащий движок не дольше `ENGINE_SILENT_FOR`.

**И строку слота продлевает каждый цикл.** Воркер, который взял слот один раз при старте и не продлевает его, теряет имя в обычной работе: строка протухает через `slot_ttl`, и имя живого воркера берёт запасной (найдено рядом с «подменщиком»). Поэтому продление слота — первая строка шага аренд базы, а шаг аренд зовёт цикл базы, `Worker.run`, — у подсистемы своего цикла нет. Путей, которыми воркер отдаёт имя, два, и оба в базе. Основной — `lease_pass` (шаг 9): строка слота называет другой экземпляр — имя отдано, экземпляр огорожен, на следующем проходе `rejoin` берёт слот с нуля. Второй — `keep_slot(let_go)`, всё в одном шаге: продлить, а если имя чужое — отдать его, отпустить единицы (`let_go`), освободить эпохи и сразу искать слот; его зовёт подсистема, чей шаг аренд свой и которой нечего останавливать (в М10B — вычислитель сценариев). Молчащее хранилище слот оставляет и там, и там: «всё ещё я», и счёт `unanswered`. Тест: `test_stand_in.py::test_the_loop_keeps_its_slot_row_and_a_name_another_instance_took_is_given_up` — девяносто секунд настоящего `run`, строка продлена циклом; `keep_slot` над строкой чужого экземпляра отпускает единицы, отдаёт эпохи, и процесс, названный юнитом, другого имени не берёт.

**Пока нового слота нет — он никто.** Захват свободного слота тоже может не удаться: хранилище моргнуло, все кандидаты заняты. Воркер без слота, но со **старым** именем — опасный воркер: продление без слота отвечало бы «это я», следующий проход читал бы назначение другого экземпляра и брал эпохи его единиц, а heartbeat ложился бы поверх законного — два процесса по очереди держали одни единицы (пятое ревью, блокер 3). Поэтому отданное имя — `seeking`, пока не взято другое, и всё это время экземпляр огорожен: `renew_slot` — `False`, «подменщик» за него ничего не продлевает, `take_epoch` бросает `NoSlot`, назначение пустое, heartbeat под чужим именем не пишется, а захват повторяется на каждом шаге аренд — и в `keep_slot`, и в `rejoin` одной функцией, `_seek_slot` (`test_slot_fence.py`).

**Проход раньше срока — подсказкой, и не чаще раза в четверть секунды.** Цикл находит работу тем, что смотрит: проход раз в `poll` секунд. Воркер, чья работа начинается со строки в журнале событий, может попросить ресурсы сказать, когда такая строка записана: запрос, который ресурс **держит** и на который отвечает в этот момент (`GET /events/wait` у двери ресурса — урок 14, шаг 8; подробно — М10B, урок 11, шаг 5а; `w2cplatform/longpoll.py`). Ответ говорит «посмотри сейчас» и больше ничего: следующий проход читает то же, что прочёл бы в конце ожидания. Решает база только то, что касается нагрузки, а не смысла. Цикл `Worker.run` после ожидания, которое ответ оборвал, делает досрочный проход, `early_pass(touched)`, где `touched` — что ответы назвали изменившимся; обычный проход по всему идёт всё равно не реже раза в `poll`, будили или нет (шаг 9). И досрочные проходы не идут чаще, чем позволяет нагрузка (`Wake`, ниже). Остальное — крючки: `wants()` — что воркер смотрит, тройки `(подсистема, вид, единица)`, где пустая единица — любая, говорит наследник; `early_pass(touched)` — по умолчанию обычный `reconcile_once`, а наследник, который умеет посмотреть меньше, смотрит меньше; `poll_events(resources)` — процесс просит длинный опрос до цикла (`LONG_POLL=0` — не просит, и всё остаётся как было); `wait_next(poll, stop)` — ожидание между проходами:

```python
    def wait_next(self, poll: float, stop) -> bool:
        """The loop's wait between passes. True when it was cut short — the pass that follows began early."""
        if self.wake is None:
            stop.wait(poll)
            return False
        if self.long_poll is not None:
            self.long_poll.sync()                 # a held request at every resource asked now: once a pass, never raises
        return self.wake.wait_next(poll, stop)
```

Воркер, который длинный опрос не просил, ждёт `stop.wait(poll)`, как ждал. Остальное — в `Wake`:

```python
    def wait_next(self, poll: float, stop) -> bool:
        self._watch(stop)
        woken = self.event.wait(poll)
        if stop.is_set():
            return False
        if woken:
            rest = self._began + self.gap - self.clock()
            if rest > 0 and stop.wait(rest):
                return False
            self.event.clear()
            self.early += 1
        self._began = self.clock()
        return woken
```

Два правила в двенадцати строках. Досрочный проход начинается не раньше чем через `WAKE_GAP` (0,25 с) после **начала** предыдущего: тысяча ответов в секунду — четыре прохода в секунду, и это весь предел нагрузки, которую подсказка может создать. И событие сбрасывается **перед** проходом, а не после: ответ, пришедший, пока проход идёт, — о строке, которую этот проход мог уже не увидеть, и он остаётся взведённым для следующего ожидания. Шаги, которые идут по часам, — аренды, heartbeat — остаются по часам: досрочный проход их не приближает, и это проверяет тест с потоком событий (`test_long_poll.py::test_a_flood_of_changes_is_one_early_pass_per_gap_and_the_lease_step_stays_on_its_clock`). Потерянный ответ стоит ожидания, которое он сберёг бы, — и ничего больше; что именно будит и кого, решает наследник (М10B, урок 25, шаг 10).

**Промежуток следует за нагрузкой, а не стоит на четверти секунды.** Четверти секунды как предела при любой нагрузке мало: проход, который шёл секунду, сразу сменялся бы следующим досрочным, а ресурс, отвечающий на запросы 503, спрашивали бы четыре раза в секунду всё равно — дыры держали бы курсоры, а досрочные проходы делали бы новые дыры (седьмое ревью, M8). Поэтому `Wake` после каждого прохода узнаёт, сколько он шёл и отказал ли ему какой-нибудь ресурс:

```python
    def pace(self, seconds: float, refused: bool) -> float:
        self.backoff = min(self.gap_max, max(self.base, 2 * self.backoff)) if refused else 0.0
        self.gap = min(self.gap_max, max(self.base, PASS_SHARE * max(0.0, float(seconds)), self.backoff))
        return self.gap
```

Промежуток — не меньше `PASS_SHARE` (двух) длин прохода: досрочные проходы занимают не больше половины цикла. Каждый проход, которому отказали, удваивает его, до `WAKE_GAP_MAX` (2 с — это и есть обычный проход); первый проход без отказа возвращает к четверти секунды. Зовёт `pace` цикл базы после каждого прохода, досрочного или обычного (`Worker.run`, шаг 9): сколько шёл проход и флаг `pass_refused`. Флаг выставляет в своём проходе наследник — что значит «ресурс отказал», знает он: у вычислителя М10B это сервер в окне прохода с причиной `did not answer` (М10B, урок 25, шаг 10). Тест: `test_long_poll.py::test_the_gap_widens_with_a_long_pass_and_with_a_resource_that_refuses`.

```python
    def keep_slot(self, let_go) -> list[str]:
        if self.seeking is not None:
            self._seek_slot()
            return []
        try:
            mine = self.renew_slot()
        except OSError as e:
            self.unanswered += 1
            log.warning("%s: the store did not answer for the slot (%s); still %s", self.name, e, self.name)
            return []
        except SchemaTooNew:
            if not self.name_taken():
                raise
            mine = False
        if mine:
            return []
        lost = list(self.epochs)
        self.give_up_name()                       # fenced from this line, whatever `let_go` does
        try:
            let_go()
        finally:
            self.release_all()
        self._seek_slot()
        return lost

    def give_up_name(self) -> str:
        with self._slot_lock:
            if self.seeking is None:
                self.seeking = self.name
            self.slot = None
            self.assigned_now = None              # what it read was the list of the name given up (`take_epoch`)
            return self.seeking

    def _seek_slot(self) -> bool:
        was = self.seeking
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))   # nobody to be on a store past this build
            if self.given is not None and self.spare_for is None:
                with self._slot_lock:
                    self._claim_slot(self.given, 50, steal=False)
            else:
                self.claim_slot()
        except NoOffer:
            return False                          # a spare with no offer of its set: it waits, as it said at its start
        except _NameTaken as e:
            self._name_taken_by(e)
            return False
        except Exception as e:                    # noqa: BLE001
            log.warning("%s: gave slot %s up and no other could be claimed (%s): nobody, taking nothing; trying again "
                        "on the next step", self.instance, was, e)
            return False
        self.seeking = None
        self._name_back()
        if was:                                   # a spare that never had a name has said what it took (`_claim_offer`)
            log.warning("%s: gave slot %s up, its units let go; going on as %s", self.instance, was, self.name)
        return True
```

**Ограда и возвращение отдают имя той же строкой.** У основного пути — отсечение экземпляра (`fence`) и возвращение на следующем проходе (`rejoin`; шаг 9) — правило «никто, пока нет слота» должно стоять так же, как у `keep_slot`. Без него `rejoin`, который сбрасывает слот и зовёт захват, ловит не всё: хранилище моргнуло на захвате — `OSError` уходит наружу, экземпляр остаётся без слота и со старым именем, `renew_slot` без слота отвечает «это я», и heartbeat с `fenced: true` ложится поверх heartbeat'а законного держателя имени, проход за проходом; между отсечением и первым `rejoin` — так же (шестое ревью; тот же класс, что блокер 3 пятого, на соседнем пути). Поэтому `lease_pass`, прочитав в строке слота чужой экземпляр, сначала зовёт `give_up_name()` — и только потом `fence`, а `rejoin` берёт слот через тот же `_seek_slot`. Что огорожено, пока `seeking`, — один список на всех воркеров:

| Что делается под именем | Чем закрыто, пока слота нет |
|---|---|
| продление строки слота (`renew_slot`), цикл и «подменщик» | `False`: слота нет, имя отдано |
| «подменщик»: аренды, слот, холд (`stand_in_once`) | `may_stand_in()` — `False` |
| чтение назначения (`assignment`) | пустое, хранилище не спрашивается |
| взятие эпохи (`take_epoch`) | `NoSlot` |
| heartbeat (`heartbeat`) | не пишется |
| отпускание слота при остановке (`release_slot`) | ничего не пишет: слота нет |
| возврат холда «по имени» (`_claim_hold`, `named`) | строка слота называет другой экземпляр — как любой чужой, ждёт срок |

`_seek_slot` ловит любое исключение захвата, а не только `OSError` и `RuntimeError`: что бы ни случилось, экземпляр остаётся никем и пробует на следующем шаге. И сначала сверяет схему — на хранилище новее своей сборки имён не берут. Тест: `test_slot_fence.py::test_a_fenced_worker_whose_rejoin_failed_says_nothing_under_the_name_another_instance_holds` — на воркере `testsub`, который идёт этим путём базы: хранилище моргает на захвате, все кандидаты заняты, имя держит живой — и всё это время никто; оборот настоящего `run` с аккуратной остановкой: чужой heartbeat цел, чужая строка слота не отпущена; отпустил — `rejoin` берёт своё имя с его назначением. То же на воркерах М10B (держатель камер, регистратор, регистратор на камере) — `tests/test_vms_worker_loops.py`.

**«Другой слот» — только у процесса без имени** (решение владельца 4 октября; продукт — `RejoinSlot`). Процесс, которому имя дал юнит (`given`: `WORKER_NAME`, `<ROLE>_NAME`, `SLOT_INDEX` — урок 7, шаг 5), в `_seek_slot` просит только это имя, и только свободным или истёкшим (`steal=False`). Возьми он любой свободный — отсечённый `w-srv-a-1` стал бы `w-2`, вторым воркером на сервере, о котором юнит не знает, а контроллер давал бы ему единицы. Пока имя держит живой экземпляр, захват отвечает `_NameTaken`, и процесс остаётся никем — с тем же списком огороженного, что выше, — и говорит об этом сам:

```python
    def _name_taken_by(self, e: "_NameTaken") -> None:
        now = self.wall()
        holder_box = runtime.box_of(e.holder) or ""
        if self.nameless is None:
            self.nameless = {"name": e.slot, "holder": e.holder, "holder_box": holder_box, "since": now}
            log.error("%s: its name %s/%s is held by %s (box %s) — another process started under the same name took it. "
                      "This one is nobody now: it holds nothing, and takes its name back when that is free; it takes no "
                      "other", self.instance, self.sub.name, e.slot, e.holder or "?", holder_box or "not said")
            self.journal.say("worker.name_taken", ALARM, sub=self.sub.name, worker=e.slot, holder=e.holder,
                             holder_box=holder_box, holder_until=e.until, instance=self.instance, box=self._box(),
                             server=self.server or "", since=now)
            self._contend_at = -1e18
        self.nameless.update(holder=e.holder, holder_box=holder_box)
        if self.clock() - self._contend_at >= CONTEND_EVERY:
            self._contend(e.slot, e.holder, NAMELESS)
            self._contend_at = self.clock()
```

Тревога — раз за эпизод, в журнал воркера (`journal`: дерево ресурса его сервера, если оно есть, иначе лог). Метка `<sub>/contenders/<имя>/<коробка>` — раз в `CONTEND_EVERY` (10 с): пока heartbeat под именем чужой, это единственный пульс старого процесса, и `/servers` показывает его у строки держателя (`name_conflict`, урок 15). Имя освободилось — `_seek_slot` берёт его, метку убирает и пишет `worker.name_back` (`_name_back`). Живой держатель имени не отдаёт никогда: два живых процесса одного имени на одной коробке отнимали бы его друг у друга вечно. Запасной (`SPARE_FOR`) имени от юнита не имеет и по-прежнему берёт только предложение своего набора. Тесты: `test_names.py`; `test_slot_fence.py` — воркер `testsub` обоими путями, `keep_slot` и `lease_pass` с `rejoin`, с именем от юнита: после моргания хранилища он возвращается под **своим** именем, когда чужой держатель его отпустил.

**Огороженный со слотом в руках узнаёт, что имя заняли.** Сосед того же класса, которого ревью не называло. Хранилище, поднятое выше сборки, отсекает воркер, а строка слота остаётся его: `renew_slot` бросает `SchemaTooNew` раньше, чем читает строку. Продлений нет, строка протухает, новая сборка берёт имя — а старый процесс строку больше не читал и продолжал писать heartbeat поверх нового держателя. На пути `keep_slot` то же: отказ продления уходит из шага аренд, а heartbeat идёт в своём `try`. Теперь на каждом шаге аренд такой экземпляр читает свою строку (`name_taken`), и с шага, который видит в ней чужой экземпляр, он никто:

```python
    def name_taken(self) -> bool:
        with self._slot_lock:
            if self.slot is None:
                return self.seeking is not None
            try:
                cur, _ = self._own_slot()
            except OSError:
                return False
            if cur.holder == self.instance:
                return False
            self.seeking, self.slot = self.name, None
            return True
```

Пока строка его — он говорит под своим именем, что отсечён; молчащее хранилище ничего не значит. Тесты: `test_slot_fence.py::test_a_holder_fenced_for_the_schema_stops_speaking_when_another_instance_takes_its_name` и `test_a_worker_on_a_store_raised_past_its_build_is_nobody_once_another_instance_takes_its_name`. Открытым остаётся окно в один шаг аренд (около восьми секунд): heartbeat, ушедший между захватом имени другим экземпляром и следующим чтением строки, ляжет поверх чужого один раз, и следующий heartbeat законного держателя его перепишет. Так же, как у неотсечённого воркера: о потере слота он узнаёт на шаге аренд, а не перед каждым heartbeat'ом.

```python
    def conflicts(self) -> int:
        return sum(l.conflicts for l in self.leases.values()) + self.__dict__.get("conflicts_carried", 0)

    def heartbeat(self, status: list[dict], **extra) -> None:
        if self._presence is not None:
            self._say_present()
            extra.setdefault("present", True)     # registered with its server's resource (`present`)
            if getattr(self, "_presence_unsaid", None):
                extra.setdefault("presence_unsaid", self._presence_unsaid)   # …but its name is not beside its lock
        extra.setdefault("schema", SCHEMA)
        extra.setdefault("build", BUILD)
        # …and `pending_writes`: what a drain waits for besides the units (`SpecConsole.drain_state`, `safe`)
        extra.setdefault("pending_writes", self.pending_writes())
        if self.stand_in_renewals:
            extra.setdefault("stand_in_renewals", self.stand_in_renewals)     # a step hung, and somebody held its units
        # Rows of this subsystem this process could not read, by table (`rows.Table`): `slots_garbled` (`read_slot`),
        # `assignments_garbled` (its own assignment), `holds_garbled` (`read_hold`), and those of a subsystem's own
        # tables — `<table>_garbled` each.
        for name, n in garbled_counts(self.sub.name).items():
            extra.setdefault(name, n)
        if self.seeking is not None:
            return                                # the name is another instance's, and so is what is said under it (`keep_slot`)
        with self._heartbeat_lock:                # …and what a stand-in says again for a hung step (`_stand_in_heartbeat`)
            ts = self.wall()
            self.objects.put(self.sub.heartbeat_key(self.name), Heartbeat(self.name, ts, status, extra).to_bytes())
            self._last_heartbeat, self._heartbeat_at = (status, extra, ts), self.clock()
```

Сумма конфликтов по всем арендам — то, что уходит в heartbeat и в метрику; к ней прибавлены конфликты, которые экземпляр насчитал под именем, отнятым у него (`conflicts_carried`, шаг 9). И сама публикация: `**extra` принимает что угодно, потому что платформа это не разбирает (урок 4). Сама платформа кладёт в каждый heartbeat схему и сборку (урок 17), `pending_writes` — сколько записей процесс держит у себя и ещё не сделал прочными (по умолчанию 0: кто пишет сразу в хранилище, которое не держит, ничего не должен; дренаж сервера `safe`, только когда у всех его воркеров здесь 0 — урок 17), счётчик «подменщика» и число испорченных строк по таблицам. `SLOTS_GARBLED` теперь — это `SLOTS.counts`, счёт таблицы `rows.Table("slot", …)`, и heartbeat не перечисляет таблицы руками: `rows.garbled_counts(sub)` отдаёт `<таблица>s_garbled` для каждой таблицы, у которой в этом процессе есть испорченная строка подсистемы (`slots_garbled`, урок 7; `assignments_garbled`, `holds_garbled`, у подсистемы с таблицами — `<таблица>_garbled` по каждой).

**Имя рядом с блокировкой пишется с каждым heartbeat'ом, и неудача говорится в нём же.** Первые строки — регистрация у ресурса сервера (урок 7, шаг 7): воркер, взявший блокировку (`present`), с каждым heartbeat'ом снова пишет своё имя рядом с ней (`_say_present`) и говорит `present: True`. Раньше неудача этой записи — ENOSPC на дереве ресурса — была только строкой лога: `.json` оставался без имени, ресурс читал воркера как «не числится», и слот освобождался под процессом, который ещё писал (двенадцатое ревью, блокер 3, воспроизведено пробой ревьюера). Теперь heartbeat несёт `presence_unsaid` с причиной, лог говорит это один раз за эпизод, а следующий heartbeat пробует записать снова; контроллер судит такого воркера как `unsure` и считает в отчёте прохода (`workers_presence_unsaid`). Тест: `tests/test_slot_fate.py::test_a_worker_that_cannot_write_its_name_beside_its_lock_says_so_and_tries_again`.

**Запись heartbeat'а — под `_heartbeat_lock`, и написанное запоминается.** `_last_heartbeat` — статус, поля и `ts` последнего heartbeat'а цикла, `_heartbeat_at` — когда он написан по монотонным часам. Из них подменщик за висящий шаг повторяет сказанное (`_stand_in_heartbeat`, выше); замок не даёт ему положить старый статус поверх свежего, который цикл пишет в ту же секунду. Тест: `test_stand_in.py::test_the_stand_in_says_no_heartbeat_over_a_fresh_one_nor_under_a_name_another_instance_took`.

```python
    def reconcile_once(self, now: float | None = None) -> list:
        raise NotImplementedError
```

Две строки, и они — объявление границы. (`now` необязателен: цикл базы зовёт проход без него, тест может дать свой.) **Что делать с единицей работы, база не знает.** Она знает, как получить право на неё, как его подтвердить, как его потерять и как о себе отчитаться — и, в шаге 9, как жить процессу, который всё это делает. Что именно значит «гнать конвейер» или «считать секунды», начинается в наследнике: в тесте границы это десяток строк `CounterWorker` поверх той же базы (урок 1; с просьбами — шаг 9), а настоящие подсистемы — в М10B.

## Шаг 9 — Рантайм воркера: цикл, шаг аренд, ограда и возвращение

Ворота, «подменщик», отдача имени — части. Процесс, который их крутит, тоже общий, и он целиком в базе: цикл `run`, шаг аренд `lease_pass`, ограда `fence`, возвращение `rejoin`, heartbeat `heartbeat_once`, взгляд на просьбы `pump_once` и `beat_once`. Подсистема пишет свою работу и ничего из этого. Что именно она пишет, сказано в голове этой части `worker.py`:

```python
    #   reconcile_once()     one pass: what runs equals what is assigned (abstract, above)
    #   status()             what the heartbeat says of each unit
    #   heartbeat_fields()   …and of itself, beyond the platform's own fields (`heartbeat_once`)
    #   stop_unit(unit)      stop the local work of one unit whose lease was lost
    #   stop_all_units()     stop everything local: an orderly stop
    #   fence_units()        …and when the instance is fenced (default: `stop_all_units`)
    #   forget_units()       forget what it held when it rejoins under another name
    #   perform(target, row, it), held_rows(), request_target(row)   a subsystem whose units take requests (below)
```

Обязателен один `reconcile_once`; у остальных есть умолчание, которое не делает ничего или делает самое малое. Рядом ещё несколько крючков того же рода: `before_stop_all` и `after_stop` (последние слова при аккуратной остановке и то, что отпускается после слота), `unit_word` (как лог называет единицу — в М10B «camera 7»), `class_of` (какие виды событий единицы — тревоги; по умолчанию все — наблюдения, ниже), `pending_writes` (шаг 8), `wants` и `early_pass` (длинный опрос и досрочный проход, шаг 8), `may_stand_in_hold` и `note_hold_confirmed` («подменщик» и место). И одно число: `capacity` — сколько единиц воркер возьмёт, если подсистема знает это лучше спецификации (ниже). Крючок — это вопрос «что значит моя единица», а не «когда продлевать»: на второй база отвечает одна.

**Шаг аренд — три правила** (обратная связь BC):

```python
    def lease_pass(self) -> list[str]:
        """Renew the slot and every lease. Another holder on my slot: the instance
        fences. A lost lease: that one unit stops and gives its epoch up."""
        self._life()
        if self.writing_allowed and self.waiting_for_offer():
            self._seek_slot()                         # a spare with no offer yet: nobody, holding nothing — not a fence
            return []
        try:
            mine = self.renew_slot()
        except OSError as e:
            self.unanswered += 1
            self.store_errors += 1
            log.warning("%s: the store did not answer for the slot (%s); still %s", self.name, e, self.name)
            mine = True
        except SchemaTooNew as e:
            …
        if not mine:
            self.give_up_name()
            self.fence(f"slot {self.name} is held by another instance now")
            return list(self.epochs)
        waiting = {u: l.epoch for u, l in self.leases.items() if l.unconfirmed() > 0}
        lost = self.renew_leases()
        …
        for unit in lost:
            …
            log.warning("%s: %s stopped: %s", self.name, self.unit_word(unit), why)
            self.stop_unit(unit)
            self.release(unit)
            self.lost_to_epoch.add(unit)
        return lost
```

*Слот говорит, кто я.* Он проверяется первым, до любой эпохи (урок 6, шаг 11): если имя перехвачено, смотреть эпохи незачем — ответ известен, и экземпляр огораживается целиком. Но огораживает только **прочитанная** строка с чужим держателем. Хранилище, которое не ответило, этой строкой не является: «всё ещё я», и ошибка считается (`store_errors`, `unanswered`). Слот — это имя; право писать дают аренды, а они кончаются сами. Хранилище, поднятое выше сборки (`SchemaTooNew`), огораживает так же — до перезапуска новой сборкой (урок 17).

*Аренда — дело одной единицы, чем бы она ни была потеряна.* Причин три, и выглядят они одинаково: контроллер отдал единицу другому воркеру, и тот взял эпоху; единица на секунды оказалась в двух назначениях, пока контроллер сверяет их со строкой размещения (урок 11); аренда истекла без установленного молчания хранилища или вышел потолок `unconfirmed_max`. Реакция одна: остановить работу этой единицы (`stop_unit`), отдать эпоху и аренду (`release`) и **продолжать работать с остальными**. Если единица всё ещё моя, следующий проход поднимет её под новой эпохой; если нет — она у другого, и делать нечего. Причину лог называет словами (`why`: «a newer epoch was issued for it», «unconfirmed for longer than its ceiling», «the store did not confirm the lease in time»).

Различать причины чтением назначения — «единицы в нём нет — переезд, есть — меня двое, огородить экземпляр» — соблазнительно и неверно: слот продлён строкой выше, значит другого экземпляра меня нет. А цена была бы высокой: одна единица в двух назначениях или полминуты без хранилища останавливали бы всю работу воркера. Продукт проверил это правило на ящике, отняв у кластера хранилище: через 16 секунд единица пишется под той же эпохой, через 36 — остановлена с «хранилище не подтвердило аренду вовремя», экземпляр не огорожен, и через двадцать секунд после возврата хранилища единица снова пишется под следующей эпохой.

*Молчащее хранилище — не потеря* (обратная связь BK). Аренда, истёкшая, пока хранилище молчало, в `lost` не попадает: `renew` отвечает `may_write()` (урок 6, шаг 8а), данные идут, действия ждут — просьбы спрашивают строгий `may_act`. Хранилище вернулось: эпоха та же — в логе «the store confirms epoch N of … again; nothing was stopped» (для этого и запомнены `waiting`); эпоха другая — единица останавливается, как при любом переназначении.

*Отпущенное назад не берут без назначения.* Шаг аренд нашёл эпоху новее и отпустил единицу; следующий взгляд на просьбы, через четверть секунды, видит её без аренды и взял бы следующую эпоху CAS-ом — отсекая нового держателя, к которому единица честно уехала, такт за тактом (найдено гонкой рядом с набором тестов М12, воспроизведено запуском). Поэтому отпущенная единица запоминается (`lost_to_epoch`), и `requests` её не берёт: своя ли она ещё, говорит только проход, прочитавший назначение. Забывает её само чтение назначения базы, `Worker.assignment()`, когда оно ответило, — и забывает только то, что шаг аренд отпустил **до** чтения: отпущенное, пока чтение шло, остаётся до следующего.

```python
        lost_before = set(self.lost_to_epoch)
        try:
            items, _ = stored(self.vars, key, ASSIGNMENTS)  # one the store cannot read: no unit, counted (the eleventh review)
        except OSError:
            self.assigned_now = None
            raise
        a = read_assignment(key, self.name, items)
        self.assigned_now = frozenset(str(u) for u in a.units)
        self.lost_to_epoch -= lost_before
        return a
```

Правило стоит в чтении, а не в проходе подсистемы: какую бы работу проход ни делал и где бы ни упал, единица возвращается в оборот ровно тогда, когда назначение ответило. Тесты: `test_worker_life.py::test_a_unit_the_lease_step_let_go_is_forgotten_by_the_assignment_read_that_answers` (на воркере `testsub`: чтение, которое не ответило, не забывает ничего; ответившее — забывает); на держателе камер М10B — `test_long_poll.py::test_a_camera_the_lease_step_let_go_is_not_taken_back_on_a_beat_only_by_the_pass_that_reads_the_assignment` и `…::test_a_camera_the_lease_step_let_go_is_not_taken_back_by_a_pass_whose_assignment_did_not_read`.

**Ограда и возвращение.**

```python
    def fence(self, why: str) -> None:
        self._life()
        if not self.writing_allowed:
            return
        log.error("%s: FENCED (%s). Stopping every unit.", self.name, why)
        self.writing_allowed, self.fenced_reason = False, why
        self.fence_units()
```

Идемпотентно: второй вызов выходит сразу, и лог не шумит в ту минуту, когда его будут читать. Сначала флаг, потом работа: параллельный шаг, случись он, уже видит запрет. `writing_allowed` — флаг на весь экземпляр, и его спрашивают все, кто начинает что-то под именем: подсистема перед стартом единицы, `observe` перед строкой события, `requests` перед просьбой, «подменщик» перед продлением (`may_stand_in`). Heartbeat говорит `fenced: true`, пока имя ещё его (огороженный за схему), и не говорит ничего, когда имя чужое (шаг 8).

```python
    def rejoin(self) -> str | None:
        self._life()
        if self.writing_allowed:
            return self.name
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))
        except SchemaTooNew:
            return None
        except OSError:
            return None                               # not known: a fenced instance can wait a pass
        was = self.name
        self.conflicts_carried += sum(l.conflicts for l in self.leases.values())
        self.release_all()
        self.forget_units()
        self.give_up_name()
        if not self._seek_slot():
            return None
        name = self.name
        log.warning("%s: was fenced as %s (%s); rejoined as %s", self.instance, was, self.fenced_reason, name)
        self.writing_allowed, self.was_fenced, self.fenced_reason = True, self.fenced_reason, None
        return name
```

**Ограда не навсегда.** Супервизор не перезапускает процесс, который не упал, и огороженный экземпляр, оставленный жить, слал бы `fenced: true` и не делал ничего до ручного перезапуска (Go-воркер продукта, обратная связь BC). Поэтому на следующем проходе цикла он начинает с нуля: без эпох, без строк (`forget_units` подсистемы), с тем назначением, какое есть у слота, который он возьмёт, — безымянный берёт свободный, названный юнитом ждёт своё имя (шаг 8). Прежний слот принадлежит тому, кто его занял. Конфликты эпох, набранные зомби, уходят с ним под новое имя (`conflicts_carried`): аренды, которые их считали, отпущены, а под потерянным именем экземпляр молчит — без переноса число `<sub>_epoch_conflicts` не показал бы никто. В heartbeat под новым именем остаётся `was_fenced` — почему.

**Цикл как процесс.**

```python
    def run(self, poll: float = 2.0, stop=None, beat: float = 0.0) -> None:
        """One box: the loop as a process. systemd or launchd restarts it."""
        self._life()
        stop = stop or threading.Event()
        lease_every = self.LEASE_EVERY or max(1.0, (self.lease_ttl - self.lease_margin) / 3)
        stand_in = self.start_stand_in()
        with self.guarded("heartbeat"):
            self.heartbeat_once()
        last_lease, last_hb, again = 0.0, self.clock(), False
        last_full, woken, touched = -1e18, False, None
        while not stop.is_set():
            full = not woken or touched is None or self.clock() - last_full >= poll
            began = self.clock()
            try:
                with self.guarded("pass"):
                    if not self.writing_allowed:
                        self.rejoin()                      # a fence is not for ever: a free slot, from nothing
                    if full:
                        self.reconcile_once()
                    else:
                        self.early_pass(touched)
                if full:
                    last_full = began
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1                    # …and counted: a loop that raises every pass is alive and says so
                log.exception("%s: pass failed; will retry", self.name)
            if self.wake is not None:                      # the next early pass no sooner than the load allows
                self.wake.pace(self.clock() - began, self.pass_refused)
            try:
                with self.guarded("pump"):
                    self.pump_once()
            except Exception:                              # noqa: BLE001
                …
            try:
                if again or self.clock() - last_lease >= lease_every:
                    unanswered, started = self.unanswered, self.clock()
                    with self.guarded("lease"):
                        self.lease_pass()
                    last_lease, again = started, self.unanswered > unanswered
            except Exception:                              # noqa: BLE001
                …
            try:
                if self.clock() - last_hb >= self.HEARTBEAT_EVERY:
                    with self.guarded("heartbeat"):
                        self.heartbeat_once()
                    last_hb = self.clock()
            except Exception:                              # noqa: BLE001
                log.exception("%s: heartbeat failed; will retry", self.name)
            woken = self.between(poll, stop, beat)         # `stop.wait(poll)`, with a look at the requests every `beat`
            touched = self.long_poll.take_touched() if woken and self.long_poll is not None else None
        stand_in.set()
        self.stop_polling()                           # no request is held at a resource for a loop that ended
        self.before_stop_all()
        self.stop_all_units()
        self.heartbeat_once()
        self.release_slot()                           # an orderly stop says so; a crash says nothing
        self.after_stop()
```

Четыре дела с тремя периодами, каждое в своём `guarded` (для «подменщика», шаг 8) и в своём `try`. Проход — обычный (`reconcile_once`) или досрочный (`early_pass(touched)`), если ожидание оборвал ответ длинного опроса и с обычного прошло меньше `poll` (шаг 8); после каждого цикл говорит `Wake`, сколько он шёл и отказал ли ресурс (`pace`).

*Поддерживать жизнь и делать работу — разные вещи, и первое не зависит от успеха второго.* Проход, который упал, — проход, который надо повторить; процесс, который его выполнял, по-прежнему держит свои единицы, и сказать об этом — не то, что сбой в другом месте вправе выключить. Один `try` на всё выглядит аккуратно и ломается ровно тогда, когда нужнее всего: сбой, повторяющийся каждый проход, выбрасывает из `try` раньше, чем очередь доходит до аренды и heartbeat'а. Так было в М10B дважды. Регистратор с оборванной связью к сетевому архиву за минуту не продлил аренду ни разу и отправил два heartbeat'а вместо шести — через 30 секунд терял эпохи, через 45 контроллер объявлял его мёртвым. А шаг аренд и heartbeat в одном `try`: одна строка тома со словом вместо числа роняла шаг аренд, и 150 секунд пульс ни одного регистратора кластера не обновился (седьмое ревью, часть 2, блокер 1). Поэтому упавший шаг считается (`pass_failures` в heartbeat'е: растущее число у живого воркера — повод читать его лог, обратная связь BG) и повторяется на следующем круге (`last_lease` не сдвигается), а heartbeat уходит в любом случае. Тесты: `test_pass_failures.py::test_a_pass_that_raises_half_way_still_renews_the_leases_and_heartbeats` — воркер `testsub`, проход падает посередине, аренды продлены и heartbeat ушёл; `test_row_reader.py::test_every_loop_heartbeats_when_its_lease_step_raises` — настоящий `run` каждого вида воркера М10B с шагом аренд, который бросает исключение.

*Первый heartbeat — сразу*, до первого прохода: процесс, который только поднялся, уже есть для контроллера и для тех, кто читает держателя.

*Шаг аренд — раз в треть окна*: `(30 − 5) / 3 ≈ 8,3` секунды. Аренда позволяет 25 секунд, и деление на три даёт **два пропущенных продления подряд** до потери: единичный сбой сети не должен ронять работу. Период отсчитывается от **начала** прошлого шага, а после шага, в котором хранилище не ответило хоть на одно продление, следующий идёт сразу, на ближайшем круге (`again`; находка прототипа на raft): иначе к паузе хранилища прибавлялись период и `poll`, и аренда истекала внутри окна, которое она должна была пережить.

*Heartbeat — раз в `HEARTBEAT_EVERY`* (10 с) при `lost_after` 45: четыре пропуска подряд до того, как воркера сочтут умолкшим. Все три периода — про одно: **между «сбой» и «умер» должно быть несколько попыток.**

*Между проходами — `between`.* В конце каждого круга супервизор узнаёт, что цикл крутится (`runtime.notify()`, сторожевой таймер systemd): шаг, который **виснет**, сюда не доходит, и после `WatchdogSec` юнит перезапускается. Потом ожидание: `stop.wait(poll)` — или короче, если воркер просил длинный опрос (`wait_next`, шаг 8), — а внутри него, раз в `beat` секунд, взгляд на просьбы (`beat_once`). Это не проход: назначение не перечитывается, ничего не сверяется. Хранилище, которое не ответило взгляду, пережидается и называется в логе один раз за отказ (`_beat_failed`), а не четыре раза в секунду. `beat` по умолчанию ноль — только на проходе; подсистема, у которой просьбы — команды устройствам, просит четверть секунды (в М10B — `COMMANDS_BEAT`).

*Прокачка — `pump_once`.* У базы в ней два дела. Первое — сводки повторов, которые подавила спецификация и чьё окно закрылось (`flush_suppressed`, ниже): без него вспышка, которая **кончилась**, не была бы посчитана никем. Второе — просьбы: если спецификация объявила `requests:`, держатель смотрит на `<sub>/requests/` и исполняет свои — один раз, под `may_act`, с ответом в heartbeat'е (`fetched`). «Один раз» держит метка, которую воркер пишет перед вызовом, — `<sub>/commands/<id>`, только созданием: из двух держателей в одну секунду хранилище скажет, чья метка легла. Эти метки — семейство платформы, а не подсистемы: каталог выводит `commands/*` в строки хранилища у каждой спецификации с `requests:` (`catalog.rows_of`), а права их писать — у воркера подсистемы (`Subsystem.acl_objects_worker`); спецификации повторять это не нужно. Взгляд на просьбы, который бросил не `OSError`, а что-то другое, — беда этого взгляда: считается в `pass_failures`, в лог один раз за полосу, прокачка идёт дальше. Весь путь просьб — урок 14, шаг «Семейство запросов». Подсистема добавляет своё и зовёт базу (в М10B держатель сначала вычерпывает шину конвейеров). Тесты: `test_worker_life.py::test_the_request_marks_are_rows_for_every_spec_whose_units_take_requests`, `test_worker_life.py::test_a_request_look_that_raises_something_else_is_that_looks_trouble`.

*Аккуратная остановка говорит об этом; падение молчит.* На выходе — «подменщик» снят, длинный опрос закрыт (`stop_polling`: ни одного запроса у ресурсов за циклом, который кончился), последние слова подсистемы (`before_stop_all`), вся работа остановлена, последний heartbeat (состояние на момент ухода остаётся в объекте), строка слота отпущена (`release_slot`) и `after_stop`. На отпускании контроллер и различает масштабирование вниз и аварию (урок 7, шаг 7): отпущенный слот с назначением он перераспределяет, просроченный — нет.

Heartbeat цикла собирает база:

```python
    def heartbeat_once(self) -> None:
        self._life()
        self.heartbeat(self.status(), **{**self.platform_fields(), **self.heartbeat_fields()})

    def platform_fields(self) -> dict:
        cap = self.capacity_said()
        return {"server": self.server, "instance": self.instance, "labels": ",".join(getattr(self, "labels", None) or []),
                **({"capacity": cap, "headroom": self.headroom()} if cap is not None else {}),
                "conflicts": self.conflicts(), "started": self.started_wall, **self.previous_said(),
                **({"fenced": True} if not self.writing_allowed else {}),
                **({"fetched": self.fetched_said()} if self.fetched else {})}
```

Поля, которые платформа читает по именам — где воркер, что он достаёт и сколько ещё возьмёт (размещение, урок 11), огорожен ли, сколько конфликтов эпох, на какие просьбы ответил, когда стартовал этот экземпляр (`started`) и что оставил под этим именем предыдущий (`previous_hb`, `previous_instance`, `previous_server`: из них контроллер меряет переключение, шаг 4), — кладёт база; подсистема добавляет своё (`heartbeat_fields`). Два словаря сливаются в один, и на ключе, который говорят оба, остаётся слово подсистемы. Воркеру никто не звонит: он рассказывает о себе периодически, и все, кому нужно, читают один объект.

**Ёмкость говорится, только когда она известна.** `capacity_said()` — число, которое поставила подсистема (`capacity`), иначе умолчание спецификации (`placement.capacity.default`), иначе ничего. Сказанное число контроллер читает как слово воркера (`capacity_of`), и сказанный ноль значил бы «не клади на меня ничего»; поэтому воркер, который своей ёмкости не знает, её не говорит, и действует запасное значение контроллера (урок 11). Тесты: `test_worker_life.py::test_a_worker_whose_subsystem_sets_no_capacity_says_the_specs_default_and_is_placed_by_it`, `test_worker_life.py::test_every_workers_failover_is_measured_from_the_heartbeat_its_name_left`.

И событие о единице — тоже платформенная строка:

```python
    def observe(self, unit, kind: str, **fields) -> str | None:
        from .rows import number
        epoch = self.epochs.get(str(unit))
        if epoch is None or not self.resource_root or not self.__dict__.get("writing_allowed", True):
            return None
        t = self.wall()
        occurred = number(f"{self.sub.name}/{unit}#occurred", fields.pop("occurred", None), default=None)
        lines = self.suppressor.lines(t, str(unit), kind, fields)
        if lines and occurred is not None:            # the observation is the last line; a summary before it has its own times
            lt, lk, lf = lines[-1]
            lines[-1] = (lt, lk, {**lf, "occurred": occurred})
        return self._write_lines(unit, epoch, lines, self.class_of(unit, kind))
```

Под эпохой, которую воркер держит, в бакет единицы в дереве ресурса своего сервера (`resource_root` — его ставит база, шаг 7; бакеты — урок 12). Единица без эпохи — не его, огороженный не говорит ничего, и больше никому не сообщается: ни строки в хранилище, ни сообщения контроллеру. Три вещи по пути — тоже платформы. Повторы гасит правило спецификации, `events.suppress` (`suppressor`: вид, окно и поля, которые говорят «это то же самое»): повтор внутри окна не пишется, а когда окно закрылось — одна сводка с числом повторов; окна, о которых никто больше не напомнит, закрывает `flush_suppressed` на каждой прокачке. `occurred` — когда это случилось по часам источника — читается через `rows.number` (слово, `nan`, `inf` теряют только этот момент), ложится на записанную строку и в «то же самое» не входит. Класс строки — `class_of`: наблюдение, если подсистема не сказала, какие её виды — тревоги. Тесты: `test_worker_life.py::test_a_worker_that_names_no_resource_tree_writes_its_events_where_the_runtime_says`, `test_worker_life.py::test_the_specs_suppressed_repeats_are_the_platforms_observe`.

Всё это вместе проверяет тест границы на `testsub`. Подсистема в нём — семнадцать строк:

```python
    class CounterWorker(Worker):
        def reconcile_once(self, now=None):
            units = self.assignment().units
            for u in units:
                if u not in self.epochs:
                    self.take_epoch(u)
                    self.counts.setdefault(u, 0)
            return units

        def status(self):
            return [{"id": u, "phase": "running", "count": self.counts.get(u, 0)} for u in self.assignment().units]

        def held_rows(self):
            return {u: {"id": u} for u in self.assignment().units}

        def perform(self, target, row, it):
            self.counts[str(row["id"])] += int(it["add"])
            return {"added": int(it["add"])}
```

А дальше — платформа: один оборот настоящего `run` и аккуратная остановка (heartbeat с `pending_writes: 0`, строка слота `released`); просьба исполнена один раз и не исполнена второй, просроченная — `expired`, обе убраны консолью; чужой экземпляр в строке слота — `lease_pass` огораживает, `rejoin` ждёт своё имя, пока его держат, и берёт его, когда отпустили:

```python
    vars_.put(spec.sub.slot_key("w-1"), Slot("w-1", "B", wall() + 45, False, 9).to_items())   # another instance's now
    w.lease_pass()
    assert not w.writing_allowed and w.fenced_reason
    assert w.rejoin() is None and not w.writing_allowed           # started under its name: it waits for that one
    vars_.put(spec.sub.slot_key("w-1"), Slot("w-1", "B", wall() + 45, True, 10).to_items())   # …which B let go
    assert w.rejoin() == "w-1" and w.writing_allowed and w.epochs == {} and w.was_fenced
```

(`tests/test_boundary.py`, `_piece_worker`.) Подсистемы М10B стоят на том же рантайме: держатель камер, детектор, скан, обзор и шлюз зовут базовые `run` и `lease_pass` и пишут только свои крючки; регистратор добавляет к шагу аренд свой шаг томов (через `super().lease_pass()`); вычислитель сценариев тоже идёт базовым `run` — его собственный `run` только ставит период прохода и heartbeat'а (`PASS_SECONDS`) и зовёт `super().run`, — досрочный проход переопределяет (`early_pass`: только сценарии, которых коснулся ответ), а шаг аренд собирает из базовых `keep_slot` и `renew_leases`: останавливать ему нечего. Тесты рантайма платформы — на воркере `testsub`: `test_stand_in.py`, `test_slot_fence.py`, `test_store_outage.py`, `test_pass_failures.py`, `test_worker_life.py` (всё, что база делает за каждую подсистему: дерево ресурса, вызов прохода без `now`, ёмкость из спецификации, `lost_to_epoch`, подавление повторов, досрочный проход, переключение, метки просьб). Что их настоящие циклы держатся тех же правил, показывает М10B: `test_vms_worker_loops.py`, `test_vms_workers_survive.py`, `test_row_reader.py::test_every_loop_heartbeats_when_its_lease_step_raises`.

## Шаг 10 — Тест: обе базы без единого слова о предметной области

```python
def test_controller_and_worker_bases_speak_only_the_contract():
    box = Box()
    sub = Subsystem("thing")
    ctl = Controller(sub, box.vars, box.objects, wall=box.wall)
    w = Worker(sub, "t-1", box.vars, box.objects, clock=box.clock, wall=box.wall)
    assert ctl.workers_seen() == {}                            # nobody has heartbeaten
    w.heartbeat([{"id": 1, "phase": "running"}], server="srv-1")
    seen = ctl.workers_seen()
    assert list(seen) == ["t-1"] and seen["t-1"].extra["server"] == "srv-1"
    a = ctl.assign("t-1", ["3", "1", "2"])
    assert a.units == ["1", "2", "3"] and a.rev == 1 and w.assignment().units == ["1", "2", "3"]
    assert ctl.assign("t-1", ["1"]).rev == 2
    assert w.take_epoch("1") == 1 and w.may_act("1")
    box.wall.advance(100)
    assert ctl.workers_seen(max_age=45) == {}                  # a silent worker is not a worker
```

Прочитаем как историю. Никто не бился — воркеров нет: пустая карта, а не ошибка и не пустой реестр. Воркер написал о себе — он появился, и `server` из `extra` дошёл нетронутым.

Контроллер назначил три единицы в произвольном порядке — получил отсортированные, ревизия 1. Воркер тут же прочитал то же самое, через свой ключ и свой метод. Переназначение на одну единицу дало ревизию 2.

Воркер взял эпоху для единицы `"1"` — получил 1 (первая) — и сразу может действовать (`may_act`): аренда заведена внутри `take_epoch`.

Часы уходят на сто секунд. Воркер молчит. `workers_seen()` пуст — **никто ничего не удалял**, изменилось только время.

И последнее, ради чего этот тест существует: подсистема называется `thing`, единицы — `"1"`, `"2"`, `"3"`, а в теле нет ни одного слова, которое сообщало бы, чем эта система занимается. Всё, что выше, — механика, и она закончена.

**Результат:** `Controller` в `contract.py`, `Worker` и его рантайм в `worker.py`; оба теста зелёные; и объяснение своими словами, почему `write` принимает функцию, а не значение, что означает `None` из неё и почему потерянная аренда останавливает одну единицу, а чужая строка слота — весь экземпляр.

---

## Что может пойти не так

| Симптом | Скорее всего |
|---|---|
| Ревизия назначения растёт при неизменном составе | Мутатор не возвращает `None`, когда менять нечего. Проход, ничего не изменивший, не должен выглядеть как изменение. |
| Два контроллера теряют размещения друг друга | Где-то `assign` вместо `assign_add`: полная замена списка, прочитанного до чужой записи. Пишите то, что меняете. |
| Воркер «существует» после остановки | `max_age` больше, чем период heartbeat'а, умноженный на разумный запас. Сорок пять секунд против десяти — это четыре пропущенных сигнала. |
| Воркер не может писать сразу после `take_epoch` | Аренда заводится внутри метода; если её создают отдельно и позже, между ними есть окно, в котором права нет. |
| Перезапущенный процесс считает чужой слот своим | Экземпляр — только хост и pid, без случайного хвоста. Pid переиспользуются. |
| `RuntimeError: 10 conflicts` | На ключ, который пишет один-два процесса, пришло десять конфликтов подряд. Это не гонка, это неисправность — ищите третьего писателя. |
| Наследник забыл проверить аренду перед записью | Так не должно быть возможно: в М10B ворота — единственный путь к актуатору. Если путь есть в обход, его надо убрать, а не задокументировать. |
| Действие выполнилось при молчащем хранилище | Действие спросило `may_write`. Просьбы, команды, срабатывания спрашивают `may_act`; `may_write` — для данных. |
| Одна единица в двух назначениях остановила всю работу воркера | Потерянную аренду читают как «меня двое» и огораживают экземпляр. Экземпляр огораживает только чужая строка слота; аренда — дело одной единицы (шаг 9). |
| Heartbeat перестаёт уходить, когда падает работа или шаг аренд | Шаги цикла в одном `try`. У каждого — свой, и упавший считается в `pass_failures`. |
| Огороженный экземпляр так и висит с `fenced: true` до ручного перезапуска | Нет `rejoin` в начале прохода: супервизор не перезапускает процесс, который не упал. |
| Аренды теряются при паузе хранилища, которую они должны пережить | Шаг аренд отсчитывается от конца прошлого шага или ждёт полный период после неотвеченного продления. От начала — и сразу после неотвеченного (`again`). |
| Единица, отпущенная шагом аренд, тут же снова взята, и новый держатель отсечён | Взгляд на просьбы взял эпоху единице из `lost_to_epoch`, или `lost_to_epoch` стирают не там. Отпущенное назад берёт только проход, прочитавший назначение: стирает его чтение назначения базы, которое ответило, и только отпущенное до чтения. |
| Контроллер после остановки воркера ничего не перераспределяет | Процесс выходит без `release_slot`: аккуратная остановка обязана сказать о себе, иначе она выглядит как падение. |

## Итог

- Контроллер не хранит ничего: каждый метод читает, решает, пишет по CAS. Два экземпляра безвредны; `count = 1` — экономия, не корректность.
- `write(path, mutate)` — образец каждой записи в курсе: мутатор видит свежие данные и решает атомарно с записью.
- Мутатор, вернувший `None`, отменяет запись. Это то, что позволяет не создавать ревизию, когда менять нечего.
- Пиши то, что меняешь, а не то, что получилось: `assign_add` вместо `assign` там, где двое могут добавлять одновременно.
- Существование воркеров выводится из heartbeat'ов и их возраста. Реестра нет, потому что реестр расходится с реальностью.
- Воркер помнит только свои эпохи, аренды, слот и экземпляр. Назначение он перечитывает каждый проход.
- `take_epoch` соединяет номер и аренду: права без срока не бывает. Действие спрашивает `may_act`, данные — `may_write`.
- `renew_leases` сообщает потерянные единицы; что это значит, решает `lease_pass` базы, одинаково для всех: чужая строка слота огораживает экземпляр, потерянная аренда останавливает одну единицу, молчащее хранилище — не потеря.
- Ограда не навсегда: на следующем проходе `rejoin` начинает с нуля под слотом, который возьмёт; пока слота нет, экземпляр — никто и ничего не говорит под чужим именем.
- Цикл процесса — базы: первый heartbeat сразу, каждый шаг в своём `try`, шаг аренд раз в треть окна и сразу после неотвеченного продления, heartbeat раз в 10 секунд, досрочный проход по ответу длинного опроса (обычный — не реже раза в `poll`), взгляд на просьбы между проходами, аккуратная остановка отпускает слот. За каждую подсистему база помнит и дерево ресурса, и ёмкость из спецификации, и прежний heartbeat имени, и подавление повторов.
- Граница: база решает жизненный цикл, наследник пишет, что значит его единица, — `reconcile_once`, `status`, `stop_unit` и ещё несколько крючков. `reconcile_once` не реализован: что делать с единицей работы, платформа не знает и не узнает.

## Упражнения

1. Уберите ветку `if new is None` из `write` и прогоните сюиту. Какие ревизии начнут расти сами по себе и что это ломает в консоли?
2. Замените `assign_add` на «прочитать, добавить, `assign`». Напишите тест с двумя потоками, который ловит потерянное размещение.
3. Заведите контроллеру реестр воркеров с регистрацией и отпиской. Перечислите состояния, в которых он расходится с реальностью, и напишите, что делает система в каждом.
4. `workers_seen` читает все heartbeat'ы на каждом вызове. Прикиньте стоимость при двухстах воркерах в М11 и решите, где кэш уместен, а где превратится в ту же расходящуюся картину.
5. Сделайте эпоху одной на воркера вместо одной на единицу. Какие два случая перестанут различаться (подсказка: урок 6, шаг 11)?
6. Верните в `lease_pass` разбор по назначению: «единицы нет в назначении — переезд; есть — меня двое, огородить экземпляр». Положите одну единицу на секунды в два назначения и опишите, что стало с остальными единицами воркера.
7. Напишите наследника `Worker`, который считает секунды: единица — интервал, `reconcile_once` печатает тик. Запустите его `run`. Сколько строк понадобилось, сколько из них про платформу, и что из шага 9 вы получили, не написав?
8. Объедините шаг аренд и heartbeat в цикле в один `try` и сделайте так, чтобы `lease_pass` бросал на каждом круге. Через сколько секунд контроллер сочтёт воркер умолкшим?

## Что дальше

Платформа закончена как механика. Дальше начинается то, ради чего она такая: [**урок 9**](09-SubsystemSpec.md) читает десять строк YAML в датакласс — и с этого момента контроллер подсистемы перестаёт быть кодом, который кто-то пишет, и становится файлом, который кто-то заполняет.

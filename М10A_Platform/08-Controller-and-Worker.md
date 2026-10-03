# Урок 8 — Два базовых класса

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `Controller` — с методом `write`, который станет образцом каждой записи в курсе, — и `Worker` с воротами: эпоха на старт, аренда перед записью, heartbeat после. Два класса, от которых наследуется всё остальное, и последний файл платформы, который ничего не знает даже про YAML.
**Время:** ~100 минут.

## Зачем этот урок

Хранилища есть, эпохи есть, слоты есть. Каждое из этих средств само по себе — несколько функций; чтобы ими пользоваться, нужно помнить порядок: сначала захвати слот, потом читай назначение, перед стартом возьми эпоху, перед записью спроси аренду, после прохода продли то и другое, раз в десять секунд напиши о себе. Забыть любой шаг — значит получить дефект, который проявится только при отказе.

Два класса этого урока собирают порядок в код. Наследник не может «забыть взять эпоху» — метод, который стартует единицу, берёт её сам. Не может «забыть проверить аренду» — она проверяется внутри тех же ворот. Не может «написать конфигурацию из воркера» — у воркера нет такого метода, а токен не дал бы права.

И оба класса не знают ни одной вещи о предметной области. `Controller` умеет назначать «единицы» — строки, — и не знает, что они означают. `Worker` умеет читать назначение, брать эпохи и отчитываться; что делать с единицей, он не знает вовсе: `reconcile_once` объявлен и **не реализован**. Это последний файл платформы, свободный даже от понятия спецификации: со следующего урока появится YAML, а здесь ещё ничего нет, кроме имени подсистемы.

> **Что можно проверить без железа.** Оба класса целиком: `test_controller_and_worker_bases_speak_only_the_contract` строит контроллер и воркера для подсистемы `thing`, гоняет назначение, эпоху, heartbeat и возраст — и в тесте не встречается ни одного слова предметной области.

## Что нужно знать заранее

- **Урок 5** — `Subsystem`, `Assignment`, `Heartbeat`: чем эти классы обмениваются.
- **Урок 6** — эпоха и аренда: воркер их здесь соединяет.
- **Урок 7** — слот: три метода захвата уже написаны и лежат в этом же классе.

## Чему вы научитесь

1. Писать «прочитать-изменить-записать по CAS» один раз и пользоваться этим везде.
2. Писать мутатор и объяснять, почему он вызывается внутри цикла повторов, а не до него.
3. Понимать приём «мутатор вернул `None`» и говорить, от чего он спасает.
4. Выводить существование воркеров из фактов, а не хранить их список.
5. Собирать ворота старта так, чтобы эпоху и аренду нельзя было обойти.
6. Объяснять, почему эпоха берётся на **единицу**, а не на воркера.
7. Называть всё, что база воркера оставляет наследнику, и почему именно это.

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
        check_schema(vars_)                       # a build older than the store does not run at all
```

Конструктор — строка присваиваний и проверка схемы, и в нём четыре поля, ни одно из которых не состояние. Подсистема (имя), два хранилища, часы. `check_schema` не даёт сборке старше хранилища даже начать работу (урок 17). Между проходами у контроллера нет ни кэша, ни списка воркеров, ни соединений, ни фонового потока.

**Кэш есть, но живёт один проход и умирает с ним.** Проход контроллера задаёт на каждую единицу дюжину вопросов — её строка, её размещение, на каком сервере воркер, отвечает ли ресурс того сервера, — и каждый был чтением хранилища, заданным заново для следующей единицы: тысяча камер на двадцати воркерах стоила одному холостому проходу около 64 000 чтений. Внутри прохода ответ не может быть старше прохода, поэтому `with one_pass(ctl):` (или `ctl.one_pass()`) подставляет вместо хранилищ `_PassStore`: каждый `get` и `list` спрашивает настоящее хранилище один раз и держит ответ до конца прохода — не дольше. Поле `_pass_local` — это `threading.local()`: подмена видна только потоку, открывшему проход, а двери консоли из своих потоков видят само хранилище. Свойства `vars` и `objects` отдают либо чтения прохода, либо хранилище; присваивание задаёт хранилище:

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
            items, idx = self.vars.get(path)
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

Тот же цикл, что в `next_epoch` из урока 6, но вынесенный в метод и принимающий **функцию изменения** — мутатор. Дальше в курсе через `write` пойдёт почти каждая запись: назначение, размещение, строки оператора, политики, производные строки. Одно решение стоит назвать прямо здесь, остальные — в следующем шаге, который весь про мутатор.

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

**Мутатор, вернувший `None`, отменяет запись.** Вот приём, который стоит понять до конца, потому что он встречается в курсе десятки раз. Мутатор — это место, где принимается решение, и иногда решение оказывается «ничего не надо». `assign_add` для единицы, которая уже в списке. `retire` для слота, который уже отпущен. `place` для единицы, которую другой экземпляр разместил, пока мы думали.

Если бы `None` не был предусмотрен, вызывающему пришлось бы проверять условие **до** `write` — то есть читать ключ, проверять, потом вызывать `write`, который прочитает его ещё раз. Между этими двумя чтениями состояние могло измениться, и проверка ничего бы не гарантировала. Внутри мутатора проверка выполняется **на тех данных, которые будут записаны**, — то есть она атомарна с записью.

Возвращается при этом текущее содержимое, а не `None`, — вызывающий получает «вот что там лежит» и обычно строит из него объект. Отмена записи не должна выглядеть как ошибка.

## Шаг 4 — Кто существует

```python
    def workers_seen(self, max_age: float = 45.0) -> dict[str, Heartbeat]:
        """Which workers exist: those that heartbeat recently. Never a list
        the controller keeps — a fact it reads."""
        out = {}
        now = self.wall()
        for key in self.objects.list(self.sub.name + "/"):
            if key.endswith("/heartbeat"):
                raw = self.objects.get(key)
                hb = parse_heartbeat(key, raw) if raw else None    # garbled: skipped, counted, said once
                if hb is not None and is_live(self.sub.name, hb.ts, now, max_age):
                    out[hb.worker] = hb
        return out
```

**Heartbeat, который не разбирается, — беда одного воркера, не прохода.** Объект обрывается на полуслове — питание, зомби, писавший в тот же файл до BD, — и `Heartbeat.from_bytes` поднимал `ValueError` посреди `workers_seen`: ни одного воркера контроллер не видел, пока кто-нибудь не удалит объект (ревью платформы, M6; второе ревью). `parse_heartbeat` пропускает такой объект, считает его (`contract.GARBLED[sub]` → `<sub>_heartbeats_garbled` в `/metrics`) и пишет в лог один раз на ключ, пока тот не станет читаться; то же у `builds`, у `heartbeats` консоли и у `resources_seen` ресурса. Тест: `test_placement_decides.py::test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs`.

**Перекос — в обе стороны.** `<sub>_heartbeat_skew_seconds_max` видит часы, ушедшие **вперёд**; отставшие он не видел — их ловит `<sub>_heartbeat_skew_seconds_min`, наибольший отрицательный перекос среди живых heartbeat'ов (окна шире 300 с, вроде перечислений за всё время, не считаются). И проверки живости, написанные руками в регистраторе и скане, теперь идут через тот же `is_live` (третье ревью).

**Живость — по чужим часам, и это сказано.** `now - hb.ts` сравнивает часы контроллера с часами воркера; при перекосе в минуту живой воркер «молчит» или мёртвый «жив». `is_live` делает две вещи, которых не делало сравнение (ревью платформы, M9): heartbeat **из будущего** дальше `FUTURE_TOLERANCE` (5 с) живым не считается — часы одного из двух врут, и действовать по ним нельзя, — а наибольший перекос запоминается и уходит в `/metrics` как `<sub>_heartbeat_skew_seconds_max`: число, по которому видно, что NTP на сервере умер, раньше, чем по размещению. Допуск записан в `module-design.md`; сроки слотов и команд (`slot.until`, `valid_until`) по-прежнему сравниваются с часами читателя — метрика скажет, когда это станет проблемой. Тест: `test_review_remainder.py::test_a_heartbeat_from_the_future_is_not_live_and_the_skew_is_a_number`.

Перечислить объекты префикса, отобрать heartbeat'ы, прочитать, отбросить старше сорока пяти секунд. Всё определение «воркер существует» — в этих шести строках, и вторая строка docstring объясняет, почему они такие: **не список, который контроллер ведёт, а факт, который он читает.**

Разница видна, когда что-то ломается. Список пришлось бы пополнять при регистрации и чистить при уходе — то есть иметь протокол регистрации, обработку повторной регистрации, уборку записей о тех, кто ушёл не попрощавшись. Каждый из этих путей может разойтись с реальностью, и когда разойдётся, контроллер будет размещать работу на воркера, которого нет.

Здесь расходиться нечему: воркер, который пишет о себе, — есть; который перестал — через сорок пять секунд перестаёт быть. Ключ при этом не удаляется, и это намеренно: последний heartbeat умершего воркера остаётся на диске и отвечает на вопрос «что с ним было перед смертью». В М10B из него берут ещё и `previous_hb` — время последнего сигнала предыдущего экземпляра, из которого вычисляется измеренное время переключения, — и `previous_server`, сервер, на котором тот экземпляр работал: вычитать `previous_hb` из своего `started` можно, только если оба времени — по одним часам (урок 11).

`raw` может оказаться пустым (`if raw`) — между `list` и `get` объект мог исчезнуть. Пропускаем.

## Шаг 5 — Назначение

```python
    def assignment(self, worker: str) -> Assignment:
        items, _ = self.vars.get(self.sub.assignment(worker))
        return self._assignment(worker, items)

    def _assignment(self, worker: str, items) -> Assignment:
        return read_assignment(self.sub.assignment(worker), worker, items)

    def assign(self, worker: str, units: list[str]) -> Assignment:
        def mutate(items):
            rev = self._assignment(worker, items).rev + 1
            return Assignment(worker, sorted(set(units), key=str), rev).to_items()
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))
```

Полная замена списка. `set` убирает дубликаты, `sorted(…, key=str)` даёт устойчивый порядок (по строковому виду, потому что единицы — строки, и числовые идентификаторы сортируются как `"1", "10", "2"`; для хранения это неважно, важна только стабильность). Ревизия растёт.

```python
    def assign_add(self, worker: str, unit: str) -> Assignment:
        """Read-modify-write: two controllers adding different units to one
        worker at once both land."""
        def mutate(items):
            a = self._assignment(worker, items)
            if unit in a.units:
                return None
            return Assignment(worker, sorted(set(a.units) | {unit}, key=str), a.rev + 1).to_items()
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))
```

Добавление **одной** единицы — и docstring объясняет, зачем отдельный метод, когда есть `assign`. Два контроллера, размещающие две разные камеры на один воркер одновременно: с `assign` каждый записал бы свой список, и второй затёр бы камеру первого (его список был прочитан до). С `assign_add` каждый добавляет своё к тому, что нашёл **внутри мутатора**, то есть к свежим данным, — и обе камеры остаются.

Правило, которое из этого следует: *пиши то, что меняешь, а не то, что получилось.* Оно применимо далеко за пределы этого метода.

`if unit in a.units: return None` — тот самый приём. Повторное добавление не создаёт ревизию: проход контроллера, ничего не изменивший, не должен выглядеть как изменение, иначе `assignment_rev` в консоли будет расти сам по себе и потеряет смысл.

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

То, что строка **решает**, — список `units`, а список имён не может не разобраться. Он читается как есть, с `rev 0`; строка считается (`assignments_garbled` в отчёте прохода и в heartbeat'е воркера) и один раз попадает в лог. Следующая запись контроллера в эту строку пишет её целиком, и `rev` начинается заново — это ничего не стоит: ревизию публикуют, но нигде не сравнивают между записями. Тесты: `test_garbled_rows.py::test_a_garbled_assignment_row_is_that_workers_trouble_and_the_pass_goes_on`, `test_a_worker_whose_own_assignment_row_is_garbled_carries_out_what_it_names`; каталог М11 читает те же строки тем же `read_assignment`.

**Тот же вопрос — каждой строке хранилища, кто бы её ни читал.** Битая эпоха, потом битый слот, потом битое назначение. Шестое ревью закрыло строки контроллера и воркера, а седьмое нашло тот же отказ в строках, которых таблица не перечисляла: тома, метки удержания, заявки, `platform/space`, `<подсистема>/next_id`, числа heartbeat'ов в `/metrics` и в циклах консоли, срезы в М12. Хуже всего вышло с томами: одна строка тома гасила пульс всех регистраторов кластера (седьмое ревью, часть 2, блокер 1). Эта таблица составлена заново — не по памяти, а обходом кода. Перебраны все места в `w2cplatform`, `vms`, кластере М11 и домене М12, где к прочитанному из `vars` или `objects` применяется `from_items`, `int`, `float`, `json.loads` или обязательный ключ: 238 мест. Правило одно: что строка ещё говорит — используется; строка считается и один раз попадает в лог; проход идёт дальше; и ничто не читается как «нет» только потому, что не разобралось.

**Один читатель на все таблицы** — `w2cplatform/rows.py`. Таблица — это `Table(имя, что значит не прочитать)`. `read(key, parse, default)` вызывает `parse()`. Если разбор бросает одно из `PARSE_ERRORS` — `ValueError` (это и `JSONDecodeError`), `TypeError`, `KeyError`, `AttributeError`, `OverflowError` или `RecursionError`, — строка считается испорченной. `RecursionError` добавлен в восьмом ревью: JSON, вложенный на десять тысяч уровней, помещается в переменную, а `json.loads` на нём сдаётся этим исключением, и оно уходило мимо всех `except`. Тогда возвращается `default`, строка считается **один раз**, пока снова не станет читаться (`counts`, по подсистеме — первому сегменту ключа), и один раз попадает в лог, а её ключ лежит в `bad` для того, кто называет её на странице. Раньше три читателя считали чтения, а не строки: одна строка, прочитанная на каждом проходе, выглядела тысячей строк (седьмое ревью, minor про `SLOTS_GARBLED`, `ASSIGNMENTS_GARBLED` и `HOLDS_GARBLED`). Что значит `default`, решает вызывающий: «не кандидат», «последняя прочитанная», «камера удержана целиком», «настройки, прочитанные последними». Числа в строках и в heartbeat'ах читает `rows.number` через таблицу `field`, и слово, `nan` и `inf` там — «не сказано». Счёт каждой таблицы уходит в heartbeat воркера (`<имя>s_garbled`), а на `/metrics` консоли — как `<подсистема>_worker_<имя>s_garbled{worker}` и `<подсистема>_console_rows_garbled{table}`.

| Строка или объект | Кто читает | Не разбирается — что теперь | Тест |
|---|---|---|---|
| слот `<подсистема>/slots/<имя>` | захват (`_claim_slot`), контроллер (`slots()`) | не кандидат; считается (`SLOTS`, `slots_garbled`) | `test_slot_fence.py::test_one_garbled_slot_row_does_not_leave_a_seeker_nobody_and_is_counted` |
| слот | своя строка: продление, уход (`_own_slot`) | читается как записанная последней; продление пишет её целиком | `test_slot_fence.py::test_a_garbled_slot_row_stops_neither_placement_nor_the_worker_it_names` |
| слот | оператор: `retire` | пишется целиком: отпущен, ничей | `test_garbled_rows.py::test_retiring_a_slot_whose_row_is_garbled_writes_it_released` |
| назначение `<подсистема>/workers/<имя>`: `rev` | контроллер, воркер, каталог М11 (`read_assignment`) | читается список единиц, `rev 0`; одна строка — один счёт | `test_garbled_rows.py::test_a_worker_whose_own_assignment_row_is_garbled_carries_out_what_it_names` |
| назначение: имя, которое не id | `SpecController.redistribute` | это имя пропускается и считается; остальные единицы уходящего слота переезжают (обрывало весь шаг) | `test_row_reader.py::test_a_name_in_an_assignment_that_is_no_units_id_stops_no_move` |
| холд `<подсистема>/holds/<место>` | захват места, страница томов (`read_hold`, `volumes.holders`) | не кандидат; назван на странице; файл, который даже не JSON, — тоже | `test_volumes.py::test_one_garbled_hold_row_is_that_volumes_trouble_and_nobody_elses` |
| эпоха `<подсистема>/epoch/<единица>` | `next_epoch`, вызовы `take_epoch`, `Lease.renew`, консоль | отказ одной единицы или команды; эта аренда отсечена; события не помечаются отсечёнными. С десятого ревью `Lease.renew` ловит `PARSE_ERRORS`: `epoch: 1e999`, записанный правкой файла руками, давал `int(inf)` → `OverflowError` мимо `(ValueError, KeyError, TypeError)`, а значит из `renew_leases` — у воркера не продлевалась ни одна аренда | `test_epoch_refused.py`, `test_garbled_rows.py::test_a_lease_whose_epoch_row_stops_parsing_is_lost_alone`, `test_one_bad_element.py::test_infinity_in_a_rows_integer_stops_no_workers_pass_and_no_lease` |
| heartbeat (объект) | `workers_seen`, `builds`, `heartbeats`, `resources_seen` (`parse_heartbeat`) | пропускается, считается; статус, в котором не объекты, — тоже (раньше `AttributeError` у каждого, кто спрашивает `.get`); после девятого ревью — и `[` в десять тысяч уровней (`RecursionError`), и `ts: 10**400` (`OverflowError`): свой список исключений `parse_heartbeat` их пропускал, и одно такое сердцебиение роняло каждого читателя пульсов, теперь там `PARSE_ERRORS`. После десятого ревью — и имена: `worker` и `server` пульса воркера и ресурса — непустые строки, иначе пульс не разбирается (`contract._named`). `"server": ["srv-x"]` разбирался, и падал каждый, кто кладёт его ключом или сортирует: `/servers`, `/unplaceable`, `/drain`, `/metrics` консоли, `restore` и зеркало ресурса, `ensure_reach`, `redistribute`, `ensure_home` контроллера; `5` среди строк ронял каждый `sorted` (воспроизведено запуском) | `test_placement_decides.py::test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs`, `test_row_reader.py::test_a_status_entry_that_is_not_an_object_or_names_no_unit_stops_no_reader`, `test_garbled_rows.py::test_a_heartbeat_with_a_number_past_any_number_or_nested_ten_thousand_deep_stops_no_placement`, `test_one_bad_element.py::test_a_heartbeat_whose_server_or_worker_is_no_name_is_that_heartbeats_and_no_route_falls` |
| `schema` и `build` в пульсе | `/schema` (`builds`), `set_schema` | схема, которая не читается (`1e999`), — `null`, «не известна»: процесс в списке, `can_raise_to` стоит там, где хранилище, поднять схему нельзя, пока он жив. Раньше такой пульс пропускался, а процесса, которого `/schema` не видит, «не было» — поднять было можно, и он оказывался запертым. `build` списком — `?` (был `TypeError` на весь маршрут); строка `platform/schema` словом — `version: null` (десятое ревью, обход маршрутов) | `test_one_bad_element.py::test_schema_lists_a_process_whose_schema_does_not_read_and_raises_past_nobody` |
| элемент статуса без `id` | `read_model` (список консоли, уборщик задач, просьбы о кадрах), метрики регистраторов | ничего не говорит о единице, пропускается | там же |
| числа внутри heartbeat'а | `capacity_of`, `headroom`, `failover_seconds` (`_number`) | «не сказал»: ёмкость по умолчанию. С девятого ревью `_number` читает через `rows.number`: `headroom: Infinity` (JSON его читает) давал `int(inf)` → `OverflowError` мимо своего `(ValueError, TypeError)`, и не размещалась ни одна единица; `inf` больше не число, счёт — один раз на поле | `test_garbled_rows.py::test_a_heartbeat_whose_numbers_are_words_is_that_workers_trouble`, `test_a_heartbeat_with_a_number_past_any_number_or_nested_ten_thousand_deep_stops_no_placement` |
| числа heartbeat'ов и отчёта прохода на `/metrics` | `SpecConsole.metrics_text`, `rec_metrics`, `vms_metrics`, `auto_metrics` (`rows.number`, `_histogram`) | «не сказано»: 0 или -1 для возраста; гистограмма, где не числа, не выводится; страница целая и вся из чисел | `test_row_reader.py::test_one_word_in_one_heartbeat_field_does_not_take_the_metrics_page` |
| числа heartbeat'ов в циклах консоли: `closed`, `hits`, `to`/`covered`/`events`, `from`/`to` | `jobs.scan_what_arrived`, `keep_what_fired`, `reap`, `ask_for_footage` | этот отрезок или эта задача пропускается; остальные идут. Считается **поле**, а не текст отрезка (восьмое ревью, minor, закрыт в девятом): ключ счёта держал текст отрезка, и регистратор со словом в `closed` давал новую «строку» на каждое движение списка — 8640 в сутки от одного поля. Теперь один ключ на пульс и поле (`<пульс>#closed`, `jobs._spans`): посчитано один раз, пока хоть один отрезок не читается, и снято, когда таких не осталось | `test_row_reader.py::test_one_word_in_a_recorders_closed_spans_stops_no_scan_and_no_keep`, `test_a_recorders_closed_spans_with_a_word_in_them_are_one_garbled_field_however_often_the_list_moves` |
| `writer`, `refused`, `archive_quota` в heartbeat регистратора | страница томов (`_writing`, `_refusing`, `suggest`), `as_held` | этот регистратор «не сказал»; страница целая | `test_row_reader.py::test_a_status_entry_that_is_not_an_object_or_names_no_unit_stops_no_reader` |
| heartbeat ресурса без `url` | `Resource.mirror`, `restore` | такой сосед не берёт и не отдаёт; `restore` при старте ещё и в своём `try` (процесс падал на каждом старте) | `test_row_reader.py::test_a_resource_comes_up_over_a_peer_whose_heartbeat_names_no_address` |
| схема `platform/schema` | `check_schema` | работающий держит последнюю прочитанную; новый не стартует (урок 17) | `test_lesson1_platform.py::test_a_schema_row_that_does_not_parse_fences_nobody_who_is_running_and_starts_nobody_new` |
| размещение `<подсистема>/placement/<единица>` | `placement()` и всё, что на нём стоит | читается `worker`; `at` и `rev` — нули (урок 10). С десятого ревью — и `rev: 1e999` от правки руками: `int(inf)` давал `OverflowError` мимо `(ValueError, KeyError, TypeError)`, и `placement()` падал под каждым шагом прохода и каждым маршрутом | `test_garbled_rows.py::test_a_garbled_placement_row_still_says_where_its_unit_is_and_stops_no_pass`, `test_one_bad_element.py::test_a_placement_row_counting_past_any_number_still_says_where_its_unit_is` |
| строка единицы | контроллер: `units()`, `_parsed` | пропускается, считается (урок 10) | `test_placement_decides.py::test_a_row_that_does_not_parse_is_one_unit_nobody_serves_and_the_three_steps_run_each` |
| строка единицы | воркеры: цикл по своим единицам (`row_garbled`) | единица идёт по строке, прочитанной последней; остальные идут. С десятого ревью у всех семи читателей (держатель, регистратор, детектор, скан, обзор, шлюз, вычислитель) — `PARSE_ERRORS`, а не свой кортеж: число `1e999` в целом поле (`int(inf)`, `OverflowError`) и `when` сценария, вложенный глубже, чем читает JSON (`RecursionError`), проходили мимо, и проход воркера кончался на этой строке | `test_garbled_rows.py::test_the_holder_goes_on_with_the_row_it_read_last_and_runs_the_rest` и три соседних, `test_one_bad_element.py::test_infinity_in_a_rows_integer_stops_no_workers_pass_and_no_lease`, `test_a_scenario_nested_past_jsons_depth_stops_neither_the_retain_nor_the_evaluator` |
| строка сценария `auto/scenarios/*` в удержании | ресурс: `kept_buckets` (`cameras_of_units`) | юнит ни одной камеры — его держат все читаемые метки. Свой кортеж `(ValueError, TypeError, AttributeError)` пропускал `RecursionError`, и `retain` всего сервера не убирал ничего (десятое ревью, major) | `test_one_bad_element.py::test_a_scenario_nested_past_jsons_depth_stops_neither_the_retain_nor_the_evaluator` |
| значение поля-списка (`labels`, `alarms`, `folders`) | все читатели строки (`Field.parse`: строка делится по `,`) | значение с запятой отказывается при записи (`SubsystemSpec.refuse`, 400); хранится по-прежнему строкой через запятую — её читает каждый читатель, М11 и М12 тоже. Раньше `["zone 1,2"]` читался назад двумя метками. Строки, записанные до этого, уже разделены и читаются как есть | `test_one_bad_element.py::test_a_value_of_a_list_field_with_a_comma_is_refused_and_the_joined_string_is_taken` |
| строка единицы: её `labels` | ворота `/events` консоли (`SpecConsole.dispatch`, `may_see`, таблица `unit`) | события этой единицы не показываются гранту по меткам — какие у неё метки, не известно; грант на саму единицу и на весь кластер их видит; в ответе — `withheld` по единицам; считается (`vms_console_rows_garbled{table="unit"}`). Раньше — 400 на всю ленту, а строка без `id` — ответа не было вовсе (проход масштаба после восьмого ревью) | `test_console_gate.py::test_one_garbled_camera_row_costs_that_cameras_events_and_not_the_timeline` |
| строка события в ответе ресурса: `t`, `epoch`, `unit`, `server`, `id`, `bucket` | слияние `/events` (`eventdatabase._event_line`) | строка берётся в тех типах, в которых её проверили (`"t": "1700000000"` — число), а не как пришла: строка рядом с числами роняла сортировку слияния, список в `unit` или `id` — множества, по которым слияние отсекает и убирает копии, и ответа не было ни одному таймлайну (тот же проход, обход `/events`); строка, которая не переводится, пропускается и считается (`peer_event`) | `test_row_reader.py::test_a_line_whose_values_only_convert_is_merged_as_converted_and_stops_no_timeline`, `test_one_resource_answering_another_shape_costs_its_window_and_not_the_merge` |
| счётчик `<подсистема>/next_id` | `SpecController._next_id` | следующий номер — за наибольшим id, удалённые тоже; строка пишется целиком (отказывал в создании любой единицы) | `test_row_reader.py::test_a_garbled_id_counter_gives_the_next_number_past_the_largest_id` |
| отчёт прохода (объект) | `pass_report`, `pass_once` | `None`, проход пишет его заново; `failures: 1e400` — счёт с нуля (было `int(inf)` → `OverflowError` до первого шага, а отчёт пишется только в конце прохода: контроллер подсистемы не размещал ничего навсегда — девятое ревью, обход) | `test_garbled_rows.py::test_a_garbled_pass_report_does_not_stop_the_controllers_loop`, `test_a_pass_report_counting_past_any_number_stops_no_pass_and_a_step_that_fails_every_pass_is_said_once` |
| срез снимка (объект) | `snapshot_age` | возраст «старше некуда» (урок 19); `ts` `nan`/`inf` — тоже (`finite`, восьмое ревью). `ts` из будущего дальше `FUTURE_TOLERANCE` (5 с) — тоже «старше некуда», а не возраст 0: контроллер, чьи часы убежали на час и который остановился, час выглядел «свежим» (девятое ревью, minor); посчитано (`fields_garbled`), а опережение — в `<sub>_heartbeat_skew_seconds_max` | `test_garbled_rows.py::test_a_garbled_snapshot_shard_makes_the_published_copy_old_and_never_fresh`, `test_a_snapshot_written_by_a_clock_running_ahead_is_not_fresh_and_its_lead_is_measured` |
| список сборки блобов `<подсистема>/sweep` | `put_blob`, `sweep_blobs`, `/metrics` | списка нет, по его слову ничего не удаляется; элемент, который не digest, не метётся (`blob_key` ронял каждую сборку) | `test_garbled_rows.py::test_a_garbled_sweep_list_stops_no_upload_and_deletes_nothing_on_its_word`, `test_row_reader.py::test_a_sweep_list_entry_that_is_no_digest_stops_no_reclaiming` |
| ключ идемпотентности `<подсистема>/idem/*`: `at` | `IdempotencyKeys.prune` | возраст неизвестен — строка остаётся, считается; остальные чистятся (обрывало чистку и POST, который её запустил) | — |
| срок хранения `<подсистема>/retention[/<единица>]` | ресурс: `retain` | эта единица не метётся (урок 14) | `test_garbled_rows.py::test_one_units_garbled_retention_row_keeps_that_units_buckets_and_the_rest_are_swept` |
| ватерлиния `platform/space` | `Resource.relieve` (`space_settings`) | число — из прочитанного последним или умолчание; сказано в heartbeat ресурса (`space_garbled`) | `test_row_reader.py::test_a_garbled_watermark_row_acts_on_the_settings_read_last_and_says_so` |
| зеркало `platform/mirror`: `copies` | `Resource.mirror` | одна копия | `test_row_reader.py::test_a_mirror_whose_copies_do_not_parse_mirrors_to_one_peer` |
| том `rec/volumes/<имя>` | регистратор (`volume_pass`, `_declared`), карта камеры, страница томов, скан (`volumes.declared`, `read_volume`) | пропускается, считается (`volumes_garbled`), назван на странице; том, который регистратор держит, — по строке, прочитанной последней; запись на такой том — отказ; консоль такую строку не пишет | `test_row_reader.py::test_one_garbled_volume_row_stops_no_recorder_and_is_named_on_the_volumes_page` и три следующих |
| метка удержания `rec/keeps/<id>` | ресурс (`kept_buckets`), регистратор `incidents` (`keep_pass`), двери (`_kept_of`), консоль | интервал держится, насколько читается (`keeps.as_far_as_read`, `Keep.garbled`): граница, которая разобралась, стоит, неразобранная открыта на свою сторону; `at` — метаданные, слово там читается как «не сказано»; держатся только вёдра камеры метки, а юниты ни одной камеры (сценарий на любую камеру, детектор без строки) держат только читаемые метки (`sound` в `vms/resource.kept_buckets`); не копируется, скопированное помнится; считается (`keeps_garbled`); в `GET /keeps` с `garbled` и `garbled_since`; через час — тревога `archive.keep.garbled` | `test_row_reader.py::test_a_garbled_keep_holds_its_camera_as_far_as_it_reads_and_nothing_of_the_units_of_no_camera`, `test_keeps.py::test_a_keep_that_stays_garbled_for_an_hour_is_an_alarm_once_per_episode_and_again_once_a_day` |
| заявка `rec/requests/*`, `det/requests/*`: `valid_until`, `minutes`, `at`, `before`, `after` | консоль: `record_on_request`, `detect_on_request` | отказ этой заявке: считается (`request`), снимается; запуск и снятие по сроку — в разных `try` | `test_row_reader.py::test_one_garbled_request_row_is_refused_alone_and_the_recordings_are_started_and_ended`, `test_a_detector_request_whose_numbers_are_words_is_refused_and_not_tried_for_ever`, `test_the_console_loop_ends_timed_recordings_when_starting_them_fails` |
| заявка `vms/requests/*`: `valid_until` | держатель (`requests`), консоль (`POST /requests`) | отказ этой команде; `nan` и `inf` — тоже отказ (раньше команда без срока) | `test_row_reader.py::test_a_command_whose_deadline_is_nan_or_inf_is_refused_by_the_holder_and_at_the_console` |
| `until` строки записи или детектора | `jobs.expire`, `_detect`, `record_on_request` | конца нет, считается; остальные кончаются | `test_row_reader.py::test_one_garbled_request_row_is_refused_alone_and_the_recordings_are_started_and_ended` |
| книга основных `domain/primaries`, отметка `domain/seen` | регистратор (`carried_primary`) | книге никто не ручается — резерв пишет (обрывало сверку регистратора) | `test_row_reader.py::test_a_book_of_primaries_nobody_can_read_makes_the_backup_record` |
| покрытие источника в heartbeat держателя | регистратор (`gaps`), скан (`device_has`), обзор (`device`); с десятого ревью и консоль — `/timeline/<камера>`, `/segment`, нижняя граница `POST /backfill` (`vms/console.coverage_of`) | «не сказано»: из него ничего не берётся; остальные записи и задачи идут. В консоли `float(cov["from"])` стоял голым в трёх маршрутах: слово в покрытии одного держателя — таймлайн и кусок с устройства камеры без ответа | `test_row_reader.py::test_a_devices_counts_and_a_holders_coverage_that_are_words_are_that_devices_and_that_cameras`, `test_one_bad_element.py::test_a_holders_coverage_that_is_a_word_costs_its_spans_and_not_the_timeline_or_the_segment` |
| строка ведра под длинным опросом | `longpoll.Watch._kinds` | пропускается, как рваная. Кортеж `(ValueError, AttributeError)` пропускал `RecursionError`: осмотр падал, размеры не двигались, и каждый следующий читал ту же строку и падал снова — длинный опрос мёртв для всех юнитов (десятое ревью, обход) | `test_one_bad_element.py::test_a_bucket_line_nested_past_jsons_depth_does_not_stop_the_watch` |
| `frontier.json` обзора и вычислителя, `waiting.json` скана | `scan.Frontier.read`, `ScanLog.waiting` | файла как нет: откуда начинать, решает строка. Список (`TypeError`), число больше float, вложенность глубже JSON роняли проход обзора и вычислителя на каждом проходе | `test_one_bad_element.py::test_a_frontier_or_a_waiting_file_that_does_not_read_is_not_there` |
| листинг пира `/mirrored/<сервер>` в `restore` | `PeerClient.mirrored` (`Listing.skipped`), `Resource._restore` | пропущенные строки и пути не вёдер считаются в `left`: пир не «отдал всё», его спрашивают снова, `restore_left` не падает, пока пир другой сборки так отвечает (девятое ревью, minor) | `test_one_bad_element.py::test_a_restore_whose_listing_skipped_lines_asks_that_peer_again` |
| ответ движка obsd (поле, хэндл) | `Archive.open`, `Archive.reading` (`classify`) | том `wrong` со словами «движок ответил то, что эта сборка не читает»: `int(reply["writer"])` без поля или с `Infinity` уходил голым `KeyError`/`OverflowError` мимо `(ObsdError, ValueError)` | `test_one_bad_element.py::test_an_engine_answer_this_build_cannot_read_is_a_wrong_volume_and_not_a_crash` |
| описание устройства `vms/devices/*` | `parse_device_row`: каталог сценариев, вычислитель | счётчик, который не число, — 0 | там же |
| ответ двери пира `/timeline/<запись>` (не строка хранилища, но тот же класс: чужой JSON) | скан (`scan.recording_read`), копировщик удержаний (`RecWorker._door_timeline`), таймлайн и экспорт камеры (`console.door_timeline`) | тело читается не больше `rows.ANSWER_MAX` (16 МиБ, `rows.answer`); ответ больше или не `{spans: [...]}` — дверь не ответила; каждый спан разбирается отдельно (`scan.door_spans`): неразобранный пропускается, считается (`door_span`), дверь названа в `garbled`, и скан не кончается `done` без этих минут, а удержание остаётся недосчитанным | `test_row_reader.py::test_a_door_that_answers_a_span_another_build_writes_costs_that_span_and_not_the_scan`, `test_a_door_that_answers_a_span_another_build_writes_stops_no_keep_from_being_copied_or_checked`, `test_slot_and_read.py::test_a_span_a_door_answered_that_does_not_parse_costs_that_door_and_not_the_cameras_timeline_or_its_export` |
| имя из строки как значение метки на `/metrics` | `SpecConsole.metrics_text`, `rec_metrics`, `vms_metrics`, `auto_metrics`, `RecWorker.metrics_text` | значение экранируется одной функцией (`w2cplatform.console.label`: `\`, `"`, перевод строки); имя записи `7"x` ломало строку, и Prometheus отвергал весь скрейп. Новые имена с `"`, `|` и управляющими символами отказываются при создании (`doors.unnamable`, урок 10) | `test_row_reader.py::test_a_name_with_a_quote_or_a_newline_is_escaped_on_every_metrics_page` |
| `cam` задачи скана (`ref:…`) | скан: события задачи | камера пишется как есть | там же |
| эпоха в статусе держателя | шлюз (`rtp_source`) | 0 для этой камеры, остальные идут | — |
| объекты члена домена: срезы, heartbeat'ы, отметки, страницы, копии строк (М12) | `federation.published`, `ReadView.refresh`/`rows`/`_try`, `uplink`, `crossing`, `members` | пропускается, считается (`member_object`); порванный срез делает копию кластера старейшей; член, чтение которого бросило, — как не ответивший в этот проход, с причиной (`ReadView.why`); список членов, который не разбирается, — «не написан» и не перезаписывается. После восьмого ревью сюда же: `can` камеры, который не объект, — «не сказал» (`crossing`); имя, которое не строка, — строка (`readview._text`); камера, которую называют два члена, — `contested`, а не 500. После девятого ревью: в М12 нет своих списков исключений — `{"id": 1e400}` в срезе давал `OverflowError` мимо кортежа `readview` и морозил `/api/cameras` и вид домена; пульс с `worker` списком — беда этого пульса, а не «член недоступен»; `archive_url` и `coverage` регистратора в книгах читаются по записи, объявление ingest — через `_urls` (строка вместо списка больше не дорога), `taken_by` — через `_names`; элемент статуса в теневом отчёте — его беда | `test_lesson3_readview_api_gateway.py::test_one_torn_object_of_one_cluster_freezes_neither_the_view_nor_the_directory`, `test_foreign_data.py::test_a_name_that_is_not_a_string_stops_no_search_and_a_camera_claimed_twice_is_contested`, `test_a_camera_whose_description_is_words_stops_no_book_and_reads_as_not_said`, `test_a_camera_id_of_1e400_in_a_members_copy_freezes_no_list_and_no_view_of_the_domain`, `test_one_heartbeat_whose_worker_is_a_list_is_that_heartbeats_and_not_the_whole_member_unreachable`, `test_a_recorders_archive_url_that_is_a_list_stops_no_source_book_and_a_string_of_urls_takes_no_road_away`, `test_one_status_entry_that_is_not_numbers_stops_no_shadow_report` |
| пакет ретранслятора, доверие кластера, проход агента, книги, пользователи, ключ signer (М12, восьмое ревью) | `BundleView`, `ClusterAccess.who`, `agent.py`, `Books.pass_once`, `identity.users`, `signer.py`, `signer_service.py` | порванный пакет — молчание членов этого ретранслятора, со словами; пакет старой сборки (список) — отказ по имени; строки доверия, которые не разбираются, — 503 «не могу проверить»; проход агента, проход книг и цикл signer идут по шагам (`domain/steps.py`, `Steps`): упавший шаг сказан один раз и посчитан, остальные идут; запись пользователя, которая не разбирается, — её беда; signer с неразобранной строкой ключа не стартует и новых ключей не делает | `test_foreign_data.py::test_a_torn_relay_bundle_is_its_members_silence_and_the_rest_of_the_domain_is_answered_and_its_books_written`, `test_a_cluster_whose_trust_rows_do_not_parse_answers_503_with_why_and_its_agent_mends_them`, `test_the_agents_pass_goes_on_past_a_row_of_the_domain_that_does_not_parse_and_leaves_its_report`, `test_the_signers_loop_runs_each_step_and_says_the_one_that_failed_once`, `test_one_users_record_that_does_not_parse_stops_neither_the_publication_nor_a_federated_login`, `test_a_signer_whose_key_row_does_not_parse_does_not_start_and_does_not_make_new_keys` |

**Что остаётся открытым — сказано по месту.** Седьмой проход оставил здесь шесть пунктов. Пять из них закрыло слияние М12 восьмого ревью (`f75adc6`; строка про М12 выше): читатели доверия кластера, проход агента, шаги `Books.pass_once`, `identity.users`, старт signer. Ворота `/events` закрыты после восьмого ревью (строка «строка единицы: её `labels`» выше). Шестой — `snapshot_age` при `ts: "nan"` — закрыт в восьмом (`finite`), а в девятом закрыт и его сосед, `ts` из будущего (строка «срез снимка» выше).

**Обход девятого ревью: каждый свой кортеж исключений вместо `PARSE_ERRORS`.** Ревью нашло один (`readview`), обход нашёл остальные. Безопасен узкий кортеж только там, где разбирается строка хранилища: значения строк — всегда строки, а `int()`/`float()` строки бросают только `ValueError`. Там, где разбирается настоящий JSON — пульс, ответ двери, тело запроса, свой файл, — `1e400` приходит как `inf` (`int()` бросает `OverflowError`), `10**400` как целое (`float()` бросает `OverflowError`), а `[` в десять тысяч уровней даёт `RecursionError`. Закрыты: `parse_heartbeat`, `SpecController._number`, `pass_once`/`pass_report`, `units`/`_parsed` (поле `json` у сценариев), `_sweep_list`, чтение строки на воротах консоли платформы; `rows.finite` теперь превращает `OverflowError` в `ValueError`, так что и вызывающие с `(TypeError, ValueError)` не пропускают `10**400`; в М12 переведены на `PARSE_ERRORS` `readview`, `shadow`, `tokens`, `shared`, `term`, `signer`, `agent`, тела запросов консоли домена; свои кортежи там остались только вокруг `finite` в `ingest` (его `OverflowError` теперь `ValueError`), вокруг `float` строки (`tokens.RevocationList`) и вокруг проверки подписи лицензии и ваучера — там кортеж покрывает всё, что тело может бросить. **Открытыми остаются** — найдены обходом, в файлах других проходов этого же раунда, и названы им: `vms/resource.py` (`json.loads` сценария в `cameras_of_units` — `RecursionError` останавливает `retain` всех серверов), `vms/keeps.py` (`_names` в `as_far_as_read`), `vms/console.py` (`door_timeline` — `RecursionError` от одной двери снимает таймлайн и выгрузку всех камер; тела `POST /backfill`, `/requests`, `/keeps`, `/rec/volumes` и покрытие из пульса — `OverflowError`), `w2cplatform/longpoll.py` (строка ведра), `vms/scan.py` (свои файлы `frontier.json`, `waiting.json`), `vms/autoworker.py` (строка сценария), `vms/archive.py` (ответы `obsd`).

Только свою строку или свой запрос останавливают, громко, с ошибкой этому запросу: `Mount.schema_route` (`GET /schema`), правка и удаление строки, которая не разбирается (`create`, `update`, `delete`, `put_blob` консоли, `DetJobController.update`, `AutoController.update`), `IdempotencyKeys.claim` повторённого запроса, `/timeline/<камера>` (`device_spans`), `/whep/<камера>`, `domain_view`. И остаются осознанные отказы: `set_schema` на битой строке схемы бросает исключение оператору — поднять версию поверх строки, которую не прочитать, значит не знать, не понижаешь ли.

## Шаг 6 — Чтение слотов и назначений

```python
    def assignments(self) -> dict[str, Assignment]:
        out = {}
        for path in self.vars.list(self.sub.name + "/workers/"):
            worker = path.rsplit("/", 1)[1]
            out[worker] = self.assignment(worker)
        return out
```

Все назначения подсистемы — перечисление плюс чтение каждого. `N + 1` обращений к хранилищу, и это осознанная цена: на коробке — это `listdir` и `N` открытий файла, в М11 — `N + 1` HTTP-запросов, при десяти воркерах незаметно. В М11 появится `Directory` — та же выборка с кэшем на время, — но только потому, что её дёргает консоль на каждый запрос «где камера 7», а не потому, что дорого контроллеру.

`slots()` устроен так же. Оба метода — чистое чтение: контроллер смотрит на мир и ничего про него не помнит.

`released_slots()` и `retire()` разобраны в уроке 7; здесь достаточно заметить, что `retire` — единственный метод контроллера, который пишет **слот**, и это не противоречит «слоты захватывают воркеры»: захват — воркеров, освобождение снаружи — операторское.

## Шаг 7 — Воркер: что он помнит

```python
    def __init__(self, sub: Subsystem, name: str | None, vars_: Variables, objects: ObjectStore,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 instance: str | None = None, slot_ttl: float = 45.0):
        self.sub, self.vars, self.objects = sub, vars_, objects
        self.clock, self.wall = clock, wall
        self.lease_ttl, self.lease_margin = lease_ttl, lease_margin
        self.epochs: dict[str, int] = {}          # unit -> epoch this worker holds
        self.leases: dict[str, Lease] = {}
        self.instance = instance or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.slot_ttl = slot_ttl
        self.slot: Slot | None = None
        self.name = name
```

В отличие от контроллера, воркер **помнит**, и стоит точно назвать что: две карты — какую эпоху он держит на каждую единицу и какая у неё аренда — плюс свой слот и свой экземпляр. И больше ничего.

Ключевое: он **не помнит назначения** и не кэширует строки. Каждый проход начинается с чтения. Это дословно правило из М9, урока 6 — *желаемое персистентно, фактическое выводится*, — и именно оно делает перезапуск безопасным: свежий процесс ничего не знает и всё выясняет заново.

Карты эпох и аренд — не исключение из правила, а его следствие. Эпоха, которую он взял, — это не конфигурация, а **факт о нём самом**: «я — тот, кто сейчас пишет эту единицу». Потеряв память, он потеряет и это право — и возьмёт новую эпоху, что и правильно, потому что новый процесс — новый писатель.

`instance` — хост, pid и шесть случайных символов. Случайный хвост нужен, потому что pid переиспользуются: перезапущенный процесс может получить тот же pid на том же хосте, и без хвоста старая строка слота выглядела бы как своя.

`name` может быть `None` до захвата (урок 7). Именованный воркер (`%i`) получает имя сразу и всё равно проходит через захват — просто с предпочтением.

## Шаг 8 — Ворота

```python
    def take_epoch(self, unit: str) -> int:
        """Called when the worker STARTS a unit: a new epoch, by CAS, and a
        lease on it. A second worker starting the same unit gets the next
        number, and the first one's lease will fence on renewal."""
        epoch, _ = next_epoch(self.vars, self.sub.epoch_key(unit))
        self.epochs[unit] = epoch
        self.leases[unit] = Lease(self.vars, self.sub.epoch_key(unit), epoch, self.lease_ttl, self.lease_margin, self.clock)
        return epoch
```

Четыре строки, соединяющие два механизма урока 6: взять номер и **тут же** завести на него аренду. Раздельно их не берут нигде — эпоха без аренды была бы правом без срока.

Слово STARTS в docstring выделено не зря. Эпоха берётся, когда воркер **начинает** держать единицу, а не когда перезапускает уже идущую. Разница проявится в М10B: правка камеры перезапускает конвейер, сохраняя эпоху (тот же писатель, тот же каталог), а настоящий старт берёт следующую (новый писатель — новый каталог).

```python
    def may_write(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_write()
```

Единица, на которую аренды нет, — не наша: `may_write` для неё `False`. Никаких умолчаний.

```python
    def renew_leases(self) -> list[str]:
        """Returns the units whose lease was lost — fenced or expired."""
        return [u for u, l in self.leases.items() if not l.renew()]
```

(Теперь первая строка ещё и запоминает, когда цикл продлевал сам, — `_loop_renewed`; ниже.)

Продлить все и вернуть **потерянные**. Обратите внимание, что метод не решает, что с ними делать, и даже не различает причины — отсечена аренда или просто истекла. Решает наследник, и в М10B это решение занимает восемь строк: если единицы больше нет в моём назначении — её переназначили, надо остановить только её; если есть — значит, её держит другой экземпляр меня, и я зомби.

Это и есть граница между базой и наследником, проведённая по месту: **база сообщает факты, наследник принимает решения о предметной области.**

**Цикл, который работает, — тот же, что продлевает.** И это была дыра: шаг, повисший на хранилище или движке — проход, прокачка, вызов регистратора в `obsd`, — переставал и продлевать, и через TTL единицы уходили соседу, хотя процесс был жив и вот-вот вернулся бы (обратная связь DD; открытый пункт четвёртого ревью). Теперь каждый шаг цикла отмечает начало и конец (`with self.guarded("pass")`), а рядом работает **«подменщик»** (`start_stand_in`): раз в `STAND_IN_WAKE` (2 с) он смотрит, не висит ли шаг дольше половины того, что позволяет аренда (`stand_in_after()`, 12,5 с при TTL 30 и запасе 5, — от более раннего из начала шага и последнего продления циклом), и если висит — продлевает аренды, строку слота и место (холд) — строку и холд по CAS и только пока они называют этот экземпляр, по тем же правилам, что цикл. Не дольше `STAND_IN_FOR` (5 минут): шаг, зависший навсегда, не держит единицы вечно, и после этого они честно уходят. Огороженного он не оживляет (`may_stand_in`), слот, занятый другим экземпляром, не переписывает, отпущенную аренду не продлевает; в heartbeat — `stand_in_renewals`. Тесты: `test_stand_in.py` — в том числе настоящий `run` всех шести воркеров с повисшим проходом.

**Подменщик повторяет последний heartbeat цикла — и говорит, что это повтор.** Сначала heartbeat он не писал: строить его значит читать состояние, которое висящий цикл меняет на своём потоке. Но молчание heartbeat'а единицы переносит: через `lost_after` (45 с) контроллер и регистраторы считали держателя мёртвым, регистраторы теряли раздачу, с которой пишут, контроллер отдавал камеры другому. И всё это при продлённых арендах — пять минут подменщика кончались на сорок пятой секунде (проход масштаба после восьмого ревью). Теперь `Worker.heartbeat` запоминает, что написал цикл (`_last_heartbeat`: статус, поля, `ts`). Пока подменщик стоит за шаг и уже подтвердил в этом шаге, что слот — этого экземпляра, он пишет heartbeat всякий раз, когда последнему исполнилось `STAND_IN_HEARTBEAT` (10 с — ритм цикла) (`_stand_in_heartbeat`). Что ему можно сказать, решено так: только то, что сказал цикл. Тот же статус и те же поля, новый `ts` и `stood_in` — шаг, сколько он идёт и `as_of`, `ts` heartbeat'а, чей это статус. Свой статус он не собирает: это было бы вторым писателем состояния цикла. Пустой не шлёт: пустой сказал бы каждому читателю, что у единиц нет держателя, — ровно тот отказ, ради которого всё это сделано. Читателю, которому нужно «жив, и где раздача», этого хватает. Тот, кому важна свежесть статуса, читает `as_of`. Цена сказана прямо: конвейер, упавший под висящим шагом, в повторённом статусе — `running`, пока цикл не вернётся, но не дольше `STAND_IN_FOR`; потом подменщик уходит, heartbeat стареет, единицы честно уходят. Запись — под замком (`_heartbeat_lock`): свежий heartbeat цикла подменщик старым статусом не перезаписывает, а пока цикл сам пишет, подменщик молчит. Тесты: `test_stand_in.py::test_a_hung_step_does_not_make_the_holder_look_dead_and_the_heartbeat_says_whose_words_it_repeats` — минута висящего прохода, и heartbeat ни разу не старше `lost_after`; `…::test_the_stand_in_says_no_heartbeat_over_a_fresh_one_nor_under_a_name_another_instance_took`; `…::test_every_workers_stand_in_says_its_last_heartbeat_again_for_a_pass_that_hangs` — настоящий `run` каждого вида воркера.

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

**И строку слота продлевает каждый цикл.** Воркеры детекторов, сканов, обзора и шлюз брали слот один раз при старте и не продлевали его вовсе — строка протухала через `slot_ttl` и в обычной работе, и имя живого воркера мог взять запасной (найдено рядом с «подменщиком»). Теперь их шаг аренд зовёт `keep_slot`: молчащее хранилище слот оставляет, строка с другим экземпляром — имя отдано: единицы отпускаются, эпохи освобождаются, берётся свободный слот (`test_every_loop_keeps_its_slot_row_and_a_name_another_instance_took_is_given_up`).

**Пока нового слота нет — он никто.** Захват свободного слота тоже может не удаться: хранилище моргнуло, все кандидаты заняты. Раньше воркер оставался без слота, но со **старым** именем, а продление без слота отвечало «это я» — и следующий проход читал назначение другого экземпляра и брал эпохи его единиц, а heartbeat ложился поверх законного: два процесса по очереди держали одни детекторы (пятое ревью, блокер 3). Теперь отданное имя — `seeking`, пока не взято другое, и всё это время экземпляр огорожен: `renew_slot` — `False`, «подменщик» за него ничего не продлевает, `take_epoch` бросает `NoSlot`, назначение пустое, heartbeat под чужим именем не пишется, а захват повторяется на каждом шаге аренд — как `VmsWorker.rejoin` у огороженного держателя. Вычислитель сценариев, у которого была своя копия этого кода, идёт теперь через `keep_slot` (`test_slot_fence.py`).

**Проход раньше срока — подсказкой, и не чаще раза в четверть секунды.** Цикл находит работу тем, что смотрит: проход раз в `poll` секунд. Воркер, чья работа начинается со строки в журнале событий, может попросить ресурсы сказать, когда такая строка записана: запрос, который ресурс **держит** и на который отвечает в этот момент (`GET /events/wait` у двери ресурса — М10B, урок 11, шаг 5а; `w2cplatform/longpoll.py`). Ответ говорит «посмотри сейчас» и больше ничего: следующий проход — обычный проход, он читает то же, что прочёл бы в конце ожидания. Поэтому у базы три крючка и ни одного решения: `wants()` — что воркер смотрит, тройки `(подсистема, вид, единица)`, где пустая единица — любая, говорит наследник; `poll_events(resources)` — процесс просит длинный опрос до цикла (`LONG_POLL=0` — не просит, и всё остаётся как было); `wait_next(poll, stop)` — ожидание между проходами:

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

**Промежуток следует за нагрузкой, а не стоит на четверти секунды.** Четверть секунды была пределом при любой нагрузке: проход, который шёл секунду, сразу сменялся следующим досрочным, а ресурс, отвечавший на запросы 503, спрашивали четыре раза в секунду всё равно — дыры держали курсоры, а досрочные проходы делали новые дыры (седьмое ревью, M8). Теперь `Wake` после каждого прохода узнаёт, сколько он шёл и отказал ли ему какой-нибудь ресурс:

```python
    def pace(self, seconds: float, refused: bool) -> float:
        self.backoff = min(self.gap_max, max(self.base, 2 * self.backoff)) if refused else 0.0
        self.gap = min(self.gap_max, max(self.base, PASS_SHARE * max(0.0, float(seconds)), self.backoff))
        return self.gap
```

Промежуток — не меньше `PASS_SHARE` (двух) длин прохода: досрочные проходы занимают не больше половины цикла. Каждый проход, которому отказали, удваивает его, до `WAKE_GAP_MAX` (2 с — это и есть обычный проход); первый проход без отказа возвращает к четверти секунды. Зовёт `pace` наследник — у вычислителя это `run`, а «отказал» значит, что в окне прохода есть сервер с причиной `did not answer` (М10B, урок 25, шаг 10). Тест: `test_long_poll.py::test_the_gap_widens_with_a_long_pass_and_with_a_resource_that_refuses`.

```python
    def keep_slot(self, let_go) -> list[str]:
        if self.seeking is not None:
            self._seek_slot()
            return []
        try:
            mine = self.renew_slot()
        except OSError as e:
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
            return self.seeking

    def _seek_slot(self) -> bool:
        was = self.seeking
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))   # nobody to be on a store past this build
            self.claim_slot()
        except Exception as e:                    # noqa: BLE001
            log.warning("%s: gave slot %s up and no other could be claimed (%s): nobody, taking nothing; trying again "
                        "on the next step", self.instance, was, e)
            return False
        self.seeking = None
        log.warning("%s: gave slot %s up, its units let go; going on as %s", self.instance, was, self.name)
        return True
```

**Держатель камер и регистратор отдают имя той же строкой.** У них свой путь: не `keep_slot`, а отсечение экземпляра (`fence`) и возвращение на следующем проходе (`rejoin`; М10B, урок 4, шаг 9). Правило «никто, пока нет слота» до этого пути не дошло. `rejoin` сбрасывал слот, звал `claim_slot` и ловил только `RuntimeError`: хранилище моргнуло на захвате — `OSError` уходил наружу, экземпляр оставался без слота и со старым именем, `renew_slot` без слота отвечал «это я», и heartbeat с `fenced: true` ложился поверх heartbeat'а законного держателя имени, проход за проходом. Между отсечением и первым `rejoin` он писался так же (шестое ревью; тот же класс, что блокер 3 пятого, на соседнем пути). Теперь `lease_pass`, прочитав в строке слота чужой экземпляр, сначала зовёт `give_up_name()` — и только потом `fence`; `rejoin` берёт слот через тот же `_seek_slot`. Что огорожено, пока `seeking`, — один список на всех воркеров:

| Что делается под именем | Чем закрыто, пока слота нет |
|---|---|
| продление строки слота (`renew_slot`), цикл и «подменщик» | `False`: слота нет, имя отдано |
| «подменщик»: аренды, слот, холд (`stand_in_once`) | `may_stand_in()` — `False` |
| чтение назначения (`assignment`) | пустое, хранилище не спрашивается |
| взятие эпохи (`take_epoch`) | `NoSlot` |
| heartbeat (`heartbeat`) | не пишется |
| отпускание слота при остановке (`release_slot`) | ничего не пишет: слота нет |
| возврат холда «по имени» (`_claim_hold`, `named`) | строка слота называет другой экземпляр — как любой чужой, ждёт срок |

`_seek_slot` ловит любое исключение захвата, а не только `OSError` и `RuntimeError`: что бы ни случилось, экземпляр остаётся никем и пробует на следующем шаге. И сначала сверяет схему — на хранилище новее своей сборки имён не берут. Тест: `test_slot_fence.py::test_a_fenced_holder_or_recorder_whose_rejoin_failed_says_nothing_under_the_name_another_instance_holds` — `VmsWorker`, `RecWorker` и регистратор на камере (`CardRecorder`, он наследует этот путь), включая оборот настоящего `run` с аккуратной остановкой: чужой heartbeat цел, чужая строка слота не отпущена.

**Огороженный со слотом в руках узнаёт, что имя заняли.** Сосед того же класса, которого ревью не называло. Хранилище, поднятое выше сборки, отсекает воркер, а строка слота остаётся его: `renew_slot` бросает `SchemaTooNew` раньше, чем читает строку. Продлений нет, строка протухает, новая сборка берёт имя — а старый процесс строку больше не читал и продолжал писать heartbeat поверх нового держателя. У пяти воркеров на `keep_slot` то же: отказ продления уходит из шага аренд, а heartbeat идёт в своём `try`. Теперь на каждом шаге аренд такой экземпляр читает свою строку (`name_taken`), и с шага, который видит в ней чужой экземпляр, он никто:

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
        return sum(l.conflicts for l in self.leases.values())

    def heartbeat(self, status: list[dict], **extra) -> None:
        extra.setdefault("schema", SCHEMA)
        extra.setdefault("build", BUILD)
        if self.stand_in_renewals:
            extra.setdefault("stand_in_renewals", self.stand_in_renewals)     # a step hung, and somebody held its units
        # Rows of this subsystem this process could not read, by table (`rows.Table`): `slots_garbled` (`read_slot`),
        # `assignments_garbled` (its own assignment), `holds_garbled` (`read_hold`), and those of a subsystem's own
        # tables — a recorder's `volumes_garbled`, `keeps_garbled`.
        for name, n in garbled_counts(self.sub.name).items():
            extra.setdefault(name, n)
        if self.seeking is not None:
            return                                # the name is another instance's, and so is what is said under it (`keep_slot`)
        with self._heartbeat_lock:                # …and what a stand-in says again for a hung step (`_stand_in_heartbeat`)
            ts = self.wall()
            self.objects.put(self.sub.heartbeat_key(self.name), Heartbeat(self.name, ts, status, extra).to_bytes())
            self._last_heartbeat, self._heartbeat_at = (status, extra, ts), self.clock()
```

Сумма конфликтов по всем арендам — то, что уходит в heartbeat и в метрику. И сама публикация: `**extra` принимает что угодно, потому что платформа это не разбирает (урок 4). Сама платформа кладёт в каждый heartbeat схему и сборку (урок 17), счётчик «подменщика» и число испорченных строк по таблицам. `SLOTS_GARBLED` теперь — это `SLOTS.counts`, счёт таблицы `rows.Table("slot", …)`, и heartbeat не перечисляет таблицы руками: `rows.garbled_counts(sub)` отдаёт `<таблица>s_garbled` для каждой таблицы, у которой в этом процессе есть испорченная строка подсистемы (`slots_garbled`, урок 7; `assignments_garbled`, `holds_garbled`, у регистратора — `volumes_garbled`, `keeps_garbled`).

**Запись heartbeat'а — под `_heartbeat_lock`, и написанное запоминается.** `_last_heartbeat` — статус, поля и `ts` последнего heartbeat'а цикла, `_heartbeat_at` — когда он написан по монотонным часам. Из них подменщик за висящий шаг повторяет сказанное (`_stand_in_heartbeat`, выше); замок не даёт ему положить старый статус поверх свежего, который цикл пишет в ту же секунду. Тест: `test_stand_in.py::test_the_stand_in_says_no_heartbeat_over_a_fresh_one_nor_under_a_name_another_instance_took`.

```python
    def reconcile_once(self, now: float) -> list:
        raise NotImplementedError
```

Последняя строка файла, и она — объявление границы. **Что делать с единицей работы, база не знает.** Она знает, как получить право на неё, как его подтвердить, как его потерять и как о себе отчитаться. Что именно значит «держать камеру» или «считать секунды», начинается в наследнике — и первый наследник появится только в М10B.

## Шаг 9 — Тест: обе базы без единого слова о видео

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
    assert w.take_epoch("1") == 1 and w.may_write("1")
    box.wall.advance(100)
    assert ctl.workers_seen(max_age=45) == {}                  # a silent worker is not a worker
```

Прочитаем как историю. Никто не бился — воркеров нет: пустая карта, а не ошибка и не пустой реестр. Воркер написал о себе — он появился, и `server` из `extra` дошёл нетронутым.

Контроллер назначил три единицы в произвольном порядке — получил отсортированные, ревизия 1. Воркер тут же прочитал то же самое, через свой ключ и свой метод. Переназначение на одну единицу дало ревизию 2.

Воркер взял эпоху для единицы `"1"` — получил 1 (первая) — и сразу может писать: аренда заведена внутри `take_epoch`.

Часы уходят на сто секунд. Воркер молчит. `workers_seen()` пуст — **никто ничего не удалял**, изменилось только время.

И последнее, ради чего этот тест существует: подсистема называется `thing`, единицы — `"1"`, `"2"`, `"3"`, а в теле нет ни одного слова, которое сообщало бы, чем эта система занимается. Всё, что выше, — механика, и она закончена.

**Результат:** `contract.py` целиком — 294 строки кода, шесть классов; оба теста зелёные; и объяснение своими словами, почему `write` принимает функцию, а не значение, и что означает `None` из неё.

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

## Итог

- Контроллер не хранит ничего: каждый метод читает, решает, пишет по CAS. Два экземпляра безвредны; `count = 1` — экономия, не корректность.
- `write(path, mutate)` — образец каждой записи в курсе: мутатор видит свежие данные и решает атомарно с записью.
- Мутатор, вернувший `None`, отменяет запись. Это то, что позволяет не создавать ревизию, когда менять нечего.
- Пиши то, что меняешь, а не то, что получилось: `assign_add` вместо `assign` там, где двое могут добавлять одновременно.
- Существование воркеров выводится из heartbeat'ов и их возраста. Реестра нет, потому что реестр расходится с реальностью.
- Воркер помнит только свои эпохи, аренды, слот и экземпляр. Назначение он перечитывает каждый проход.
- `take_epoch` соединяет номер и аренду: права без срока не бывает.
- `renew_leases` сообщает потерянные единицы и не решает, что это значило. Решение — у наследника; граница проходит здесь.
- `reconcile_once` не реализован: что делать с единицей работы, платформа не знает и не узнает.

## Упражнения

1. Уберите ветку `if new is None` из `write` и прогоните сюиту. Какие ревизии начнут расти сами по себе и что это ломает в консоли?
2. Замените `assign_add` на «прочитать, добавить, `assign`». Напишите тест с двумя потоками, который ловит потерянное размещение.
3. Заведите контроллеру реестр воркеров с регистрацией и отпиской. Перечислите состояния, в которых он расходится с реальностью, и напишите, что делает система в каждом.
4. `workers_seen` читает все heartbeat'ы на каждом вызове. Прикиньте стоимость при двухстах воркерах в М11 и решите, где кэш уместен, а где превратится в ту же расходящуюся картину.
5. Сделайте эпоху одной на воркера вместо одной на единицу. Какие два случая перестанут различаться (подсказка: урок 6, шаг 11)?
6. Перенесите разбор «зомби или переназначение» из наследника в `renew_leases`. Что базе придётся узнать о предметной области, чтобы это стало возможно?
7. Напишите наследника `Worker`, который считает секунды: единица — интервал, `reconcile_once` печатает тик. Сколько строк понадобилось и сколько из них про платформу?

## Что дальше

Платформа закончена как механика. Дальше начинается то, ради чего она такая: [**урок 9**](09-SubsystemSpec.md) читает десять строк YAML в датакласс — и с этого момента контроллер подсистемы перестаёт быть кодом, который кто-то пишет, и становится файлом, который кто-то заполняет.

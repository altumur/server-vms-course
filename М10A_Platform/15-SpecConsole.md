# Урок 15 — Консоль как данные: чтения, записи и `Mount`

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `w2cplatform/console.py` целиком. Сначала `SpecConsole`, собранную из той же спецификации, что и контроллер; идемпотентные ключи, которые живут в хранилище, а не в памяти процесса; и чтения: описание подсистемы, модель чтения, «где эта единица» и «у кого это место», события. Потом записи (`create`, `update`, `delete`, `mark`), `/servers`, `/policy`, `/metrics`, то, что подсистема объявила в спеке (таблицы, заявки, дверь держателя), ворота, ветки POST/PUT/DELETE в `dispatch` — и класс `Mount`, после которого новая подсистема становится путём.
**Время:** ~180 минут.

## Зачем этот урок

У платформы есть всё, кроме экрана. И вопрос, с которого этот урок начинается, тот же, что в уроке 9: **четыре подсистемы — четыре консоли?**

Ответ снова «нет», и по той же причине. Консоли нужно знать: как называются строки, какие у них поля и каких типов, чем опознаётся единица, что считать работающим. Всё это уже написано — в YAML, из которой сделан контроллер. Значит, консоль строится из неё же, и четыре подсистемы получают четыре консоли **бесплатно**.

Дальше — вторая мысль, посильнее. Если консоль знает поля из спецификации, то и **страница** может их узнать: пусть спросит по HTTP и построит список и формы сама. Тогда добавление поля в YAML меняет контроллер, консоль и экран одним движением, и ни одной строки HTML править не надо. Страницу разбирает урок 16; здесь строится то, что отдаёт странице описание.

И третье, что сильно влияет на форму файла: консолей **несколько**. По одной на сервер, все равноправные, ни балансировщика, ни выбора главной. Значит, повторный POST может прийти на другую консоль, чем первый, — и должен получить тот же ответ. Заявка, которая это обеспечивает, лежит не в памяти процесса.

Консоль, собранная до сих пор, умеет только смотреть. Это половина: оператор создаёт единицы, администратор крутит политику, страница просит метрики. Все эти записи короткие, и почти все они — один и тот же жест: позвать метод контроллера, поймать `Refused`, вернуть код.

Интересно в них не это, а то, **чего в них нет**. Ни одна запись консоли не размещает. `create` возвращает строку с `worker: None` — не потому, что ещё не успели посчитать, а потому что консоли нечем: у её токена нет прав на `*/assignment/*` (урок 9). Размещение случится на следующем проходе контроллера, и это видно прямо в ответе.

Вторая половина урока — `Mount`, несколько десятков строк, ради которых написано всё остальное. Подсистем на одном кластере несколько (в М10B под одной консолью их будет семь: `vms`, `rec`, `live`, `det`, `detjob`, `survey`, `auto`). Вариантов было три: процесс на подсистему, каждый на своём порту (оператору столько же вкладок), одна консоль, знающая про все (обратно к монолиту), или **один процесс, в котором каждая подсистема — путь**. Третий вариант и выбран: консоль платформы (`python3 -m w2cplatform console`) читает каталог спек, ставит в корень ту, что назвал `CONSOLE_ROOT`, а остальные монтирует под их именами — без единой правки ни в консоли, ни в странице.

> **Что можно проверить без железа.** Всё, на настоящем порту с `port=0`: `test_spec_declarations.py::test_the_console_is_the_platforms_built_from_a_directory_of_specs_and_the_deployment_says_what_is_at_the_root` собирает консоль из каталога спек; в М10B `test_lesson6_controller.py::test_the_console_over_http` гоняет через консоль весь список маршрутов, а `…::test_a_retry_that_lands_on_another_console_is_one_camera` поднимает **две** и шлёт один и тот же POST в обе. `Mount` проверяется так же: поднять, сходить `GET /mounts`, создать единицу с `Idempotency-Key`, повторить тот же POST, сравнить ответы. Ни камеры, ни GStreamer.

## Что нужно знать заранее

- **Урок 9** — спецификация: поля, типы, `refuse`, два ACL; почему ошибка поля приходит именно оттуда.
- **Урок 10 и 11** — контроллер: `create`/`update`/`delete`, `read_model`, `unplaceable`, `policy`/`set_policy`, `POLICY_CHOICES`, `resource_state`, `idle_by_policy`.
- **Урок 13** — `MergedIndex`: то, чем консоль отвечает про события.
- **Урок 4** — heartbeat и его `extra`: `/servers` и `/metrics` читают воркеров только оттуда.

## Чему вы научитесь

1. Строить консоль из спецификации и объяснять, что при этом перестаёт дублироваться.
2. Отдавать описание подсистемы так, чтобы страница построила себя сама.
3. Делать идемпотентность, работающую между процессами, а не внутри одного.
4. Отвечать на «где эта единица» двумя способами и говорить, зачем оба.
5. Показывать устаревшее с его возрастом вместо того, чтобы прятать.
6. Собирать эпохи всех подсистем, ничего не зная ни об одной.
7. Писать запись, которая ничего не решает, и объяснять, почему `worker: None` — это ответ, а не заглушка.
8. Отличать 400 от 404 и 503 по тому, кто виноват, а не по тому, что удобнее.
9. Собирать вид «по серверам» из одних heartbeat'ов — без реестра машин.
10. Отдавать метрики в формате Prometheus, не притащив Prometheus.
11. Обслуживать то, что подсистема объявила в спеке (таблицы, заявки, права, метрики, дверь держателя), не зная, что за этим стоит, — и не пропускать через консоль ни одного байта держателя.
12. Монтировать несколько подсистем в один процесс и один порт.

---

## Шаг 1 — Консоль из спецификации

```python
class SpecConsole:
    """One console for every subsystem. `ctl` is the subsystem's SpecController
    holding the console's token."""

    def __init__(self, ctl: SpecController, marks_root: str | None = None, index=None, worst_failover: float = 0.0,
                 wall=None, lost_after: float = 45.0, per_minute: float = 0.0):
        self.ctl, self.spec, self.index = ctl, ctl.spec, index
        self.worst_failover, self.wall, self.lost_after = worst_failover, wall or ctl.wall, lost_after
        self.instance = f"{socket.gethostname()}:{os.getpid()}"
        self.marks_root = marks_root
        …
        self.marks = EventLog(marks_root, CONSOLE_MARKS, self.instance, 1) if marks_root else None   # the console's own log: one writer, so epoch 1
        self.journal = Journal(marks_root, "console", self.wall)   # what was done through this console, and by whom (`journal.py`)
        from .door import Signer
        # signs the holders' door tokens with the key in the store (`door/signer`, sealed with the cluster's key ring);
        # None without a ring to seal one with: the doors' open mode
        self.door_signer = Signer.for_console(ctl.vars, getattr(ctl, "sealer", None))
        self.gate = Gate(ctl.vars, self.wall, lambda: self.journal)   # who is calling, and may they (`access.py`)
        self.seen = IdempotencyKeys(ctl.vars, f"{self.spec.name}/idem/", self.wall,   # in the store: any instance answers a retry
                                    sealer=getattr(ctl, "sealer", None))                 # its digests under the cluster's key
        …
        self.units: dict[str, "SpecConsole"] = {self.spec.name: self}
```

Консоль принимает **контроллер**, а не хранилище. Тому есть причина, и она про права: контроллер, переданный сюда, построен на дескрипторе с **токеном консоли** (урок 9), то есть умеет писать строки оператора и не умеет писать размещение. Тот же класс `SpecController`, другой токен — и консоль физически не может сделать того, чего ей нельзя. Не «не вызывает метод», а получает `Forbidden`.

`index` — то, чем отвечать про события: `MergedIndex` из урока 13. Может быть `None` — тогда `/events` честно отвечает 503.

`door_signer` — то, чем консоль подписывает токены дверей держателей. Сама консоль байтов не отдаёт и не проводит: она только выдаёт адрес двери держателя и токен к ней (шаг 12). Ключ лежит **в хранилище**, а не в окружении процесса: `door/signer` — закрытая половина, запечатанная кольцом ключей кластера (её читает только консоль), `door/keys` — открытые половины, которые читает каждый держатель (`door.py`). Нет кольца, которым запечатать ключ, — `door_signer` равен `None`, и двери открыты; это режим, о котором говорят вслух.

`journal` — журнал «кто что сделал» (шаг 8), `gate` — ворота (шаг 12а), `units` — каталог подсистем процесса по имени: одна консоль знает только себя, в `Mount` все консоли делят один словарь (шаг 14). По нему ворота находят строку единицы, названной ссылкой `<sub>/<id>`, даже если это единица соседней подсистемы.

`marks` — собственный журнал событий консоли, и вот это стоит остановить и объяснить.

## Шаг 2 — Консоль наблюдает как все

Оператор нажал «отметить момент». Это наблюдение — ровно в том смысле, в каком наблюдения определены в уроке 12: нечто, замеченное в некоторое время. Куда его писать?

Соблазн: в бакет той единицы, о которой отметка. Нельзя. У бакета один писатель, определённый эпохой (урок 12), и эпоху единицы держит **воркер**, а не консоль. Консоль, пишущая в чужой бакет, — это второй писатель, то есть ровно то, от чего вся конструкция защищается.

Поэтому:

```python
        self.marks = EventLog(marks_root, CONSOLE_MARKS, self.instance, 1) if marks_root else None
```

Консоль пишет **под своим именем**: дерево `CONSOLE_MARKS` (`"console"`, `events.py`), единица — экземпляр (`хост:pid`), эпоха 1. Спека с таким именем не загрузится: `console`, `audit`, `platform` и `domain` — имена платформы (`spec.RESERVED_NAMES`, урок 9). Эпоха единица навсегда и без CAS, потому что писателем этой единицы является один процесс по построению — экземпляр в имени и есть гарантия.

А связь с единицей, о которой отметка, — через **поле** `of` внутри события, ссылку `<sub>/<id>` (урок 13: вторая колонка индекса), а не через путь. Своё `of` отметка называет сама: это одно из двух деревьев платформы, которым так можно (второе — журнал `audit`, шаг 8; `events.OWN_OF_TREES`). Похоже устроена единица, чья спека объявила `about` (урок 9): её события лежат в её собственном бакете, а индекс относит их и к единице, о которой она, — только `of` её строкам ставит база воркера по строке единицы, а строку подсистемы, которая называет своё `of`, лог отказывает (урок 12). В М10B так пишет детектор: его событие лежит в его бакете и найдётся по запросу о камере.

Это красивый случай, где правило «одна единица — один писатель» не обходят исключением, а применяют: у консоли появляется своя единица.

`marks_root` может быть `None` — консоль на сервере без ресурса. Тогда отметки отвечают 503 с объяснением, а всё остальное работает.

## Шаг 3 — Описание

```python
# `GET /spec`: a spec as the page reads it — of the spec alone, so the domain holder's door, which runs no controller,
# says the same of every spec it loaded (`/mounts` there, the contract's §10a).
def describe(s) -> dict:
    return {"name": s.name, "rows": s.rows, "id": s.id,
            "fields": [{"name": f.name, "type": f.type, "default": f.default_value(), "required": f.required,
                        **({"inherit": f.inherit, "merge": f.merge} if f.inherits else {}),
                        **({"fixed": True} if f.fixed else {}),
                        **({"bound_to": list(f.bound_to)} if f.bound_to else {}),   # a secret asked anew when they change
                        **({"enum": list(f.enum)} if f.enum else {})} for f in s.fields.values()],
            **({"about": {"sub": s.about_sub, "field": s.about_field}} if s.about_sub else {}),
            …
            **({"display": s.display} if s.display else {}),
            **({"servers": {"show": s.servers_show}} if s.servers_show else {}),
            **({"door": {"routes": list(s.door_routes)}} if s.door_routes else {}),
            **({"places": {"table": s.places["table"]}} if s.places else {}),   # `/where/<table>/<place>`
            # its part of the domain, as the page reads it (the contract, §10a): the key families (`domain.keys`; their
            # words are `display.keys`), the shared fields, the fields the holder lets into an edit, the view's fields
            **({"domain": {"keys": [{"id": f["id"], "keys": list(f["keys"]), **({"prefix": f["prefix"]} if f["prefix"] else {})}
                                    for f in s.domain.keys], "shared": list(s.domain.shared),
                           "edit": list(s.domain.edit), "view": list(s.domain.view)}}
               if s.domain else {}),
            "running_gauge": f"{s.name}_{s.running_gauge}" if s.running_gauge else None,
            "workers_gauge": f"{s.name}_workers_live",
            "metrics": {"prefix": s.name, "running": s.running_gauge or None}}
```

Это функция модуля, а не метод: описание — только о спеке, и дверь держателя домена, у которой контроллера нет, отвечает им так же (`SpecConsole.describe` зовёт её с `self.spec`).

Спецификация, пересказанная в JSON. Для `testsub` — подсистемы, на которой платформа гоняет свои тесты (`tests/testdata/testsub.subsystem.yaml`), — получится (запуск на коде, длинные строки `about` укорочены):

```json
{"name": "testsub", "rows": "counters", "id": "name",
 "fields": [{"name": "name", "type": "string", "default": "", "required": true},
            {"name": "start", "type": "int", "default": 0, "required": false},
            {"name": "labels", "type": "list", "default": [], "required": false},
            {"name": "step", "type": "int", "default": null, "required": false, "inherit": 1, "merge": "override"},
            {"name": "marks", "type": "list", "default": null, "required": false, "inherit": [], "merge": "union"}],
 "display": {"keys": {"tallies": {"title": "tallies", "about": "a member's tally book: …"},
                      "ledger": {"title": "ledger", "about": "the ledger the holder keeps for the domain",
                                 "absent": "nothing ledgered yet"}}},
 "domain": {"keys": [{"id": "tallies", "keys": ["domain/testsub/tallies"], "prefix": "domain/testsub/tallies/"},
                     {"id": "ledger", "keys": ["domain/testsub/ledger"]}],
            "shared": ["step", "marks"], "edit": ["start", "labels"], "view": ["start"]},
 "running_gauge": "testsub_counters_running", "workers_gauge": "testsub_workers_live",
 "metrics": {"prefix": "testsub", "running": "counters_running"}}
```

Этого достаточно, чтобы построить экран. Список единиц — по `rows` (и путь к ним тот же: `/counters`). Форма создания — по `fields`: строковое поле даёт текстовый ввод, `bool` — галочку, `list` — поле через запятую, `enum` — выпадающий список, `required` — звёздочку и проверку, `fixed` — поле, которое после создания не правится, `bound_to` — секрет, который форма спрашивает заново, когда меняются названные поля (урок 9). Поле с `inherit` (у `testsub` это `step` и `marks`) своего умолчания не имеет — `default: null`: пустое, оно берёт значение домена, а без домена — то, что написано в `inherit`; `merge` говорит, заменяет ли своё значение доменное или складывается с ним. Строка состояния — по именам метрик `running_gauge` и `workers_gauge`; `running_gauge` — `null`, если спека не назвала свою метрику `console: {running: …}` (шаг 11).

Остальные ключи появляются, только когда спека их объявила. `about` — о какой единице другой подсистемы каждая единица этой (урок 9). `display` — словарь слов для страницы: как назвать единицу, подсказки к полям, слова для видов событий, дерево групп, слова для семейств ключей, карточку единицы (`form`). Что эти слова значат, платформа не знает — она их передаёт. Проверяет она только форму: разделы закрыты (`spec.DISPLAY_KEYS`, неизвестный раздел — отказ при загрузке), а слово, сказанное о поле, должно называть поле строки (или поле статуса, которое карточка показывает, `form[].status`), и слово о значении поля строки — значение из его `enum` (урок 9). `servers.show` — строки каких таблиц подсистемы показать под сервером, который назван в их поле. `door` — какие маршруты держатель единицы открывает странице сам (шаг 12); по ним — у самой подсистемы или у той, что `about` её единицы, — страница решает, рисовать ли шкалу и плеер (урок 16). `places` — таблица, строки которой — места подсистемы (`placement.places`, урок 11): у кого место сейчас, страница спрашивает `/where/<table>/<place>` (шаг 6). `domain` — её часть домена, у каждой спеки с разделом `domain:`: семейства ключей подсистемы в домене, поля, чьё общее значение держит домен, поля, которые держатель пускает в правку (`edit`), и поля вида домена (`view`) (М12A).

Вот что здесь важно осознать. Страница **не знает** ни одной подсистемы: ни камер, ни счётчиков. Она умеет отрисовать «подсистему вообще» — и потому одна и та же на все. Слова, которыми страница говорит с оператором, тоже из спеки (`display`), а не из страницы. Страницу разбирает урок 16; сейчас достаточно, что описание содержит ровно то, из чего экран собирается.

Обратите внимание на `default`: отдаётся `default_value()`, то есть уже вычисленное значение (умолчание поля или умолчание типа — у строки `name` это `""`), а не то, что написано в YAML. Странице нужно, чем заполнить форму, а не как это было объявлено.

## Шаг 4 — Заявка в хранилище

```python
class IdempotencyKeys:
    """A retried POST must be the same POST whichever console answers it, so
    the key lives in the store, not in a process: `<sub>/idem/<key>` is
    claimed by a create-only CAS before the write and filled with the reply
    after it. A second instance that sees the claim waits for the reply and
    serves it; it never repeats the write. Keys older than `ttl` are pruned
    on the way past, at most once a minute."""
```

Задача: клиент послал «создать единицу», ответ не дошёл (сеть, вкладка закрылась), клиент повторил. Нужно, чтобы вторая попытка **не создала вторую единицу**, а вернула тот же ответ, — и чтобы это работало, когда попытки попали на разные консоли.

```python
    def claim(self, key: str, sub=None, body=None):
        """None: ours to answer — do the write, then store(). Else the reply to serve."""
        path, tag = self._path(key), self._tag(sub, body)
        try:
            self._rev[path] = self.vars.put(path, {"state": "pending", "at": self.wall(), **tag}, cas=0)   # create-only: the first claimant wins
            self._mine[path] = tag
            self.prune()
            return None
        except Conflict:
            pass
```

`cas=0` — «создать, только если нет» (урок 2). Кто записал, тот и обслуживает; остальные получают `Conflict`. Консоль запоминает ревизию, которую записала сама (`_rev`), — она понадобится ниже.

```python
        for _ in range(40):                                              # another instance holds it: its reply, when it lands
            items, idx = self.vars.get(path)
            if items is None:
                self._seen.pop(path, None)
                return self.claim(key, sub, body)                        # pruned or crashed mid-flight: claim again
            wrong = self._mismatch(items, tag, body)
            if wrong is not None:
                return wrong                                             # somebody else's key, or another body under it: not this reply
            if items.get("state") == "done":
                self._seen.pop(path, None)
                return int(items["status"]), parse_json(items["body"])
            first = self._seen.get(path)
            if first is None or first[0] != idx:
                first = self._seen[path] = (idx, self.clock())
            if self.clock() - first[1] >= self.PENDING_TTL:
                kept = {"id": items["id"]} if "id" in items else {}       # the id the first attempt reserved: ours to create under
                try:
                    self._rev[path] = self.vars.put(path, {"state": "pending", "at": self.wall(), **tag, **kept}, cas=idx)
                    …
                    return None
                except Conflict:
                    continue
            self.sleep(0.05)
        …
        return 409, {"detail": "the same request is in flight on another console", "error": "in flight"}

    PENDING_TTL = 30.0
```

Проигравший **ждёт ответа победителя** — до двух секунд, опрашивая ключ. Дождался — отдаёт **тот же самый ответ**: тот же код, то же тело, тот же идентификатор созданной единицы. Клиент не отличит.

Две детали, каждая из которых закрывает свой случай. Ключ **исчез** — заявку убрали по сроку или победитель упал, не дописав: заявляемся заново. Ответ **не пришёл за две секунды** — 409 с текстом «тот же запрос выполняется на другой консоли»: не ложь и не выдуманный ответ.

**Заявка, на которую никто не ответит.** Консоль взяла ключ и упала до ответа — или её запись бросила исключение. Заявка оставалась `pending` на все сутки жизни ключа, и каждый правильный повтор получал 409 (ревью платформы; обратная связь, BG). Клиент делал ровно то, для чего ключ придуман, и не мог создать единицу до завтра. Правила, которые это закрывают:

- **Заявка, которая не меняется `PENDING_TTL`, — ничья.** Тридцать секунд: запись в хранилище столько не длится. Но «старше» считается **по своим часам и по ревизии**, а не по чужому `at` (второе ревью): `at` писала другая консоль, и перекос часов в минуту отдавал её живую заявку перехватчику. Перехват идёт, когда ЭТА консоль видела одну и ту же ревизию заявки (`idx`) неизменной `PENDING_TTL` по своим монотонным часам (`_seen`); новая ревизия начинает отсчёт заново. Из двух перехватывающих выигрывает один — тот же CAS, что и при первой заявке. И номер новой единицы **резервируется в заявке** до строки (`IdempotencyKeys.reserve` → `SpecController.create(body, uid=…, reserve=…)`; решение продукта, обратная связь CS): перехвативший создаёт под тем же номером — или находит единицу уже созданной и отвечает ею. Без этого «ответ потерян» и «запись не сделана» неразличимы, и перехват после сбоя записи ответа заводил вторую единицу; теперь ответ отправляется, даже если `store` не удался (`_remember`), заявка остаётся с номером, и повтор находит единицу. Тест: `test_a_claim_is_stale_by_standing_still_on_this_consoles_clock_and_not_by_another_consoles_at`.
- **Перехватили — значит, прежний владелец больше не пишет.** Перехват по своим часам решал, когда заявку можно взять; но консоль A, простоявшая тридцать секунд и проснувшаяся после перехвата B, дописывала заявку поверх и создавала вторую единицу на тот же ключ (третье ревью). Теперь `reserve`, `store` и `release` пишут по CAS на ревизию, которую консоль записала сама: проигравший `reserve` — 409 «taken over», и единицу он не создаёт; проигравший `store` после записи всё равно отвечает 201 — перехвативший найдёт единицу под зарезервированным номером; `release` не удаляет заявку, которую взял другой. Тест: `test_a_console_whose_claim_was_taken_over_while_it_stood_still_writes_nothing`.
- **Ключ — одного вызывающего и одного тела.** Заявка несёт `sub` (имя, которое оставили ворота) и отпечаток тела; повтор под тем же ключом с другим телом или от другого человека — 422 `key reused`, а не чужой ответ (второе ревью; `_mismatch`). Тест: `test_an_idempotency_key_is_one_callers_for_one_body`. Отпечаток — **не голый sha256 тела** (тринадцатое ревью): тело строки может нести пароль, и словарь из семи слов, подставленных в известное тело, находил его по хэшу в заявке. При ключах кластера это HMAC тела (`mac`, ключ хранилище не видит), и рядом `digest` — sha256 тела, в котором каждое `*_secret` и каждый адрес замаскированы (`mask_secrets`).
- **Ответ 5xx под ключом не запоминается.** «Хранилище недоступно» — не ответ на запрос, а запомненный, он сутки возвращался на каждый повтор. `store` с кодом от 500 снимает заявку (`release`), и повтор выполняется.
- **Отказ хранилища при самой заявке — 503, а не 400.** Клиент, которому сказали 400, не повторяет: ему сказали, что запрос неверен.

```python
    def store(self, key: str, resp: tuple[int, dict]) -> None:
        if int(resp[0]) >= 500:
            return self.release(key)
        path = self._path(key)
        tag, rev = self._mine.get(path, {}), self._rev.get(path, 0)
        try:
            self.vars.put(path, {"state": "done", "status": resp[0], "body": json.dumps(hide_in_reply(resp[1])), "at": self.wall(),
                                 **tag}, cas=rev)
        except Conflict:
            raise ClaimLost(f"the claim on {key} was taken over by another console before the reply was kept") from None
        finally:
            self._lose(path)
```

Копия ответа под ключом проходит через `hide_in_reply`: ответ, процитировавший адрес с паролем, иначе лежал бы сутки в хранилище под ключом, на который никто не смотрит (двенадцатое ревью).

Перехват имеет цену, и её надо назвать. Консоль, простоявшая дольше `PENDING_TTL`, теряет заявку: её `reserve` проигрывает CAS, и она ничего не пишет. Окно, которое остаётся, открывается, только если хранилище откажет дважды: ответ не лёг под ключ (`_remember` пишет это в лог и отправляет ответ всё равно), и перехват после `PENDING_TTL` тоже не нашёл, что записано. Граница выбрана так, чтобы это было редкостью, а сутки отказов — невозможны.

```python
    def prune(self) -> int:
        if self.clock() - self._pruned < 60:
            return 0
        …
```

Уборка старше суток, не чаще раза в минуту на процесс, **по пути** — внутри `claim`. Без отдельного потока и без задачи по расписанию: то, что делается редко и дёшево, можно делать попутно. Монотонные часы для интервала, настенные для возраста заявки (урок 6).

И ключевая фраза из docstring: **заявка живёт в хранилище, а не в процессе.** Идемпотентность, сделанная словарём в памяти, работает ровно до второй консоли — то есть не работает.

## Шаг 5 — Диспетчер

```python
    def dispatch(self, h, method: str, path: str, q: dict) -> None:
        """Answer one request for this subsystem. `path` is the route (`/<rows>`, `/where/7`), the mount
        prefix already removed; `h` is the handler (its `_send`, `_body`, `headers`, `rfile`)."""
        con, ctl, spec = self, self.ctl, self.spec
        rows_path = "/" + spec.rows
```

Один метод на все маршруты, и первое, что он делает, — вычисляет **путь строк из спецификации**: `/counters` у `testsub`, `/cameras` у VMS. Ни одного захардкоженного имени.

Сигнатура необычна: `dispatch` принимает обработчик `h` как аргумент, а не является его методом. Так сделано ради монтирования (шаг 14): один HTTP-сервер обслуживает несколько консолей, и обработчик у них общий, а `dispatch` — у каждой свой. Путь приходит уже без префикса монтирования.

`_send` и `_body` живут в `SendMixin` — четыре строки, добавленные к обработчику: отправить JSON (или текст, если `raw`) и прочитать тело.

## Шаг 6 — Чтения

```python
            if path in ("/", "/index.html"):
                return send_file(h, PAGE, "text/html; charset=utf-8", headers=(("Content-Security-Policy", page_csp()),))
            if path == "/healthz":                      # alive: what the reserve and the monitors' lane answer besides
                return h._send(200, {"ok": True})
            if path == "/spec":
                return h._send(200, con.describe())
            if path == rows_path:
                rows, configured = ctl.read_model(con.lost_after), mask_secrets(ctl.units())
                sees = self._visible(h)
                if sees is not None:                     # gated: the list is what THIS caller may look at, not the cluster's
                    ok = {str(r["id"]) for r in ctl.units() if sees(*self.target_of_row(self, r, spec.ref(r["id"])))}
                    rows = [r for r in rows if str(r.get("id")) in ok]
                    configured = [r for r in configured if str(r.get("id")) in ok]
                return h._send(200, {"rows": rows, "configured": configured})
```

Корень — страница, файлом, с политикой содержимого, которая разрешает браузеру только собственный скрипт страницы (по его хэшу, `page_csp`). `/healthz` — «жив» для мониторинга. `/spec` — описание. Список строк отдаёт секреты замаскированными и, при воротах, только те единицы, которые этому человеку можно видеть (шаг 12а). И маршрут, который стоит разобрать: **две вещи под одним ключом**.

`rows` — модель чтения (урок 11): что **наблюдается**, собранное из heartbeat'ов воркеров, с возрастом и состоянием. `configured` — что **настроено**, то есть строки из хранилища.

Зачем оба. Потому что разница между ними — самое информативное, что есть на экране. Единица настроена, но её нет в наблюдениях: не размещена, или её воркер не бился ни разу. Единица наблюдается, но её нет в настроенных: её только что удалили, а воркер ещё не дошёл до следующего прохода. Страница показывает первое как «не размещена», а второе — как строку, которая вот-вот исчезнет.

Консоль, отдающая только одно из двух, вынуждала бы додумывать.

```python
            if self.place_path(method, path):
                return h._send(*con.where_place(h, path.split("/")[3], q))
            if path.startswith("/where/"):
                try:
                    uid = self._uid(path)
                except Refused as e:
                    return h._send(400, {"detail": str(e), "error": "not an id"})
                pl = ctl.placement(uid)
                return h._send(200 if pl else 404, {"worker": pl.worker if pl else None,
                                                    "server": ctl.server_of(pl.worker) if pl else None,
                                                    "reason": pl.reason if pl else ctl.unplaced_reason(uid),   # nowhere, and why (DQ)
                                                    "directory": con.where(uid), "scans": con.scans,
                                                    **con.door_of(h, uid)})
```

Первая ветка — «где это место», о ней ниже. Вторая — «где эта единица», и её ответ содержит **два ответа** (и, у подсистемы с дверью, третий — о нём в шаге 12).

`worker` и `reason` — из строки размещения: что решил контроллер и почему (урок 11), `server` — на каком сервере этот воркер, по его heartbeat'у; у неразмещённой единицы `reason` — почему её нигде нет (`unplaced_reason`). `directory` — из скана назначений: в чьих списках она сейчас числится. Id, который не id этой подсистемы (`/where/None`, слово там, где номера), — 400 словами (`_uid`), а не оборванное соединение.

```python
    def directory(self) -> dict[str, list[str]]:
        now = time.monotonic()
        if now - self._scan[0] >= 5.0:
            self._scan = (now, {w: a.units for w, a in self.ctl.assignments().items()}); self.scans += 1
        return self._scan[1]

    def where(self, uid) -> str | None:
        hits = sorted(w for w, units in self.directory().items() if str(uid) in units)
        return "+".join(hits) if hits else None                       # a reassignment window shows as both
```

Скан всех назначений, кэшированный на пять секунд (страница дёргает это часто, а контроллер меняет раз в проход). Счётчик сканов отдаётся наружу — честность в том, чего стоил ответ.

И последняя строка — причина, по которой ответов два. Во время перемещения (урок 11, `move`) единица недолго числится **у обоих** воркеров, и `where` вернёт `"w-1+w-2"`. Строка размещения при этом уже называет нового. Оператор, спросивший в эту секунду, увидит оба ответа и поймёт, что происходит переезд, — вместо того чтобы получить один ответ и удивляться, почему воркер не совпадает.

**Где место.** У подсистемы, чьи места — строки её таблицы (`placement.places`, урок 11), есть второй вопрос того же рода: у кого это место сейчас. Единица переехала, а то, что она оставила на прежнем месте, лежит там и обслуживается тем, кто держит место теперь. Отвечает тот же маршрут с таблицей и именем вместо id — `GET /where/<table>/<place>?unit=<sub>/<id>`:

```python
    def place_path(self, method: str, path: str) -> bool:
        segs = path.split("/")
        return (method == "GET" and len(segs) == 4 and segs[1] == "where" and bool(self.spec.places)
                and segs[2] == self.spec.places["table"] and bool(segs[3]))
```

Таблица после `/where/` — только таблица мест спеки; всё остальное после `/where/<x>/` — по-прежнему 404 до ворот (`route_id`). Единицы этот путь не называет: она приходит в `?unit=`, и ворота спрашивают `view` на ней, как на `/where/<id>` (шаг 12а).

```python
    def where_place(self, h, place: str, q: dict) -> tuple:
        …
        if row is None or not matches(row, t["where"]):
            return 404, {"worker": None, "place": place, "door": None, "detail": …, "error": "no such place"}
        server = str(row.get(t["server_field"]) or "") if t["server_field"] else ""
        …
        found = self.place_holder(place)
        if found is None:
            gone = f"{place}@{server}"
            h._extra_headers = (("X-Unreachable", gone),)
            return 404, {"worker": None, "place": place, "server": server, "door": None, "unreachable": gone,
                         "reason": f"nobody holds {place} now: what is there is unavailable until a worker takes it"}
        worker, url = found
        door = self.door_at(h, uid, worker, url, place=place) if uid is not None and self.spec.door_routes else None
        return 200, {"worker": worker, "place": place, "server": server, "door": door}
```

Место — строка таблицы, которая отвечает `where` из `placement.places`; другая строка — 404 `no such place`. Держатель места — живой воркер, чей heartbeat называет это место в поле `place_by` и объявляет дверь (`place_holder`); два таких heartbeat'а сразу (умерший держатель и его преемник, оба свежие для консоли на миг) различает живая аренда места `<sub>/holds/<place>`. Ответ — тот же, что у `/where/<id>`: воркер и дверь с токеном (шаг 12), токен — на ЭТОГО держателя и единицу из `?unit=`. Без `?unit=` — только воркер, `door: null`: токен всегда одной единицы. Места не держит никто — 404, `door: null` и место словом `<place>@<server>` (сервер — из поля строки, которое назвал `server_field`) в теле и в заголовке `X-Unreachable`: страница называет оператору, чего не хватает в её картине, а не рисует пустоту. Запуск на `testsub2` (места — полки `shelves`, `where: {enabled: true}`; полка `s1` на `srv-1` с живым держателем `t-1`, `s2` на `srv-2` без держателя, `s3` выключена):

```
GET /testsub2/where/shelves/s1?unit=testsub2/t1
  → 200 {"worker": "t-1", "place": "s1", "server": "srv-1",
         "door": {"url": "http://holder-1:9000", "token": "door1.kc53d72980d6a.…", "expires": …, "routes": ["read", "play"]}}
GET /testsub2/where/shelves/s1                    → 200 {"worker": "t-1", "place": "s1", "server": "srv-1", "door": null}
GET /testsub2/where/shelves/s2?unit=testsub2/t1
  → 404 {"worker": null, "place": "s2", "server": "srv-2", "door": null, "unreachable": "s2@srv-2",
         "reason": "nobody holds s2 now: what is there is unavailable until a worker takes it"}   X-Unreachable: s2@srv-2
GET /testsub2/where/shelves/s3?unit=testsub2/t1   → 404 {…, "error": "no such place"}
```

Тесты: `test_where_place.py::test_a_places_holder_is_found_and_its_door_opens_for_the_unit_asked_and_that_holder_alone`, `…::test_a_place_nobody_holds_is_said_with_its_server_in_the_unreachable_header`, `…::test_a_places_door_is_asked_with_the_rights_of_the_unit_it_is_for`.

```python
            if path == "/resources":
                now = con.wall()
                return h._send(200, {s: {**hb, "state": "live" if ctl.resource_state(s, con.lost_after) == "live" else "silent"}
                                     for s, hb in resources_seen(ctl.objects).items()})
            …
            if path == "/unplaceable":
                return h._send(200, ctl.unplaceable())
```

Ресурсы — их heartbeat'ы (урок 14) с добавленным состоянием; состояние судит тот же `resource_state`, по которому решает размещение, а не своё сравнение возраста. Опять: **молчащие показываются**, помеченные, а не скрываются. Та же линия, что модель чтения с её `stale` и ответ базы с `catching up`.

`/unplaceable` — отдельный вопрос про единицы, которых никто живой не может взять (урок 11).

## Шаг 7 — События всех подсистем

```python
            if path == "/events":
                if con.index is None:
                    return h._send(503, {"error": "no event index behind this console"})
                unit = q.get("unit") or None
                narrow = unit is not None
                cur = {} if narrow else con.epochs()
                try:
                    t0, t1 = float(q.get("from", 0)), float(q.get("to", 1e12))
                    rep = con.index.query(t0, t1, q.get("kind"), q.get("subsystem"), unit, cur,
                                          limit=min(int(q.get("limit", 1000)), MAX_LIMIT),
                                          epoch_policy=con.epoch_policy, keep=q.get("keep", "newest"),
                                          cls=q.get("class"), by=q.get("by", "t"))
                    if narrow:
                        refence(rep["events"], con.epochs_of({(e["subsystem"], unit_id(e)) for e in rep["events"]}), con.epoch_policy)
                    else:
                        …                                     # a subsystem the scan did not see: its units asked by name
                    sees = self._visible(h)
                    if sees is not None:
                        …                                     # a unit's events, to whoever may view that unit (step 12a)
                    …
                    return h._send(200, con.timeline(rep, t0, t1))
                except ValueError as e:
                    return h._send(400, {"error": str(e)})
```

`cur` — самая плотная строка маршрута, и она решает задачу из урока 13: база не знает текущих эпох, их приносит спрашивающий.

`unit` — ссылка `<sub>/<id>`: строки самой единицы и строки каждой единицы, которая о ней (их `of`). Голый id — 400 (`check_query` индекса): чей это был бы `7`? Других способов назвать единицу у маршрута нет — ни номера «особой» подсистемы, ни догадки по виду строки.

**Список ресурсов — тоже.** Слияние `/events` перечисляло пульсы всех ресурсов на каждый запрос — List и Get на ресурс при каждом опросе страницы; теперь список читается не чаще раза в 2 с (`MergedIndex.seen`, `SEEN_FOR`), а сами ресурсы спрашиваются, как раньше (обратная связь DD; тест `test_a_burst_of_timeline_requests_lists_the_resources_once_in_two_seconds`).

**Не на каждый запрос.** Так было в первой версии — и при тысяче единиц, опросе страницы раз в три-пять секунд и десятке операторов это тысячи чтений в секунду к raft, которые замедляли CAS аренд (второе ревью). Теперь карта эпох живёт в консоли `EPOCH_CACHE` = 3 с по монотонным часам (`SpecConsole.epochs`), а таймлайн **одной** единицы эпох не перечисляет вовсе: ответ индекса отсекается заново по эпохам только тех единиц, которые в нём есть (`epochs_of`, `eventdatabase.refence`). Три секунды — меньше одного опроса страницы: эпоха, сменившаяся сейчас, на таймлайне единицы видна сразу, на общем — через окно. Тест: `test_lesson10_events.py::test_the_timeline_reads_every_epoch_once_in_a_while_and_a_cameras_timeline_only_its_own`.

Консоль перечисляет **все** ключи хранилища и берёт те, в которых есть `/epoch/`. Получается словарь `{(подсистема, единица): эпоха}` — по всем подсистемам сразу, включая те, о которых эта консоль ничего не знает. Подсистему, чьих строк эпох скан не увидел (хранилище отвечает консоли только то, что ей можно читать), консоль спрашивает по имени — только про единицы, которые есть в ответе; подсистема, чьи эпохи читать нельзя вовсе, названа в ответе (`epochs_unread`), и её события стоят так, как их пометил ресурс.

Почему по всем. Потому что таймлайн одной единицы показывает события **разных** подсистем: её собственные, события единиц, которые о ней (`about`), отметки оператора. Каждое отсекается по эпохе **своей** единицы своей подсистемы, и консоль одной подсистемы не может знать текущую эпоху другой — но может прочитать все ключи и передать их базе, которая просто сравнит. (В М10B на таймлайне камеры так встречаются наблюдения её держателя, срабатывания детектора и отметки оператора.)

Ключ разбирается из пути: `testsub/epoch/c1` → `("testsub", "c1")`. Никакого знания о подсистемах — разбор строки по известной раскладке (урок 5). Журнал и отметки консоли пишет один писатель под эпохой 1, строк эпох у них нет, и их не спрашивают.

### Норматив потока: число, за которым экран считает, а не перечисляет

У оператора есть пропускная способность, и она кончается раньше, чем у базы. Шторм не столько теряет тревоги, сколько превращает их в обои: все одинаковые, все мелькают, и через десять минут на них перестают смотреть. Это тот же провал, ради которого построен весь путь события, только пришедший через парадную дверь, а не через потерянную запись.

Поэтому у консоли есть **норматив** — сколько событий в минуту ожидается от одного читателя, — и, что важнее, **за ним что-то происходит**:

```python
    def timeline(self, rep: dict, t0: float, t1: float) -> dict:
        events = rep.get("events", [])
        minutes = max((min(t1, self.wall()) - t0) / 60.0, 1 / 60.0)
        rate = len(events) / minutes
        out = {**rep, "rate_per_minute": round(rate, 1), "per_minute": self.per_minute, "aggregated": False}
        if rate <= self.per_minute or not events:
            return out
        …                                         # (subsystem, unit, kind, class) → count, since, until
        return {**out, "aggregated": True, "events": [], "groups": ordered}
```

Норматив без действующей половины — комментарий в файле. Записанное и ни разу не прочитанное число не предотвращает ничего: буря идёт ровно так же, обои получаются ровно те же. Поэтому в курсе он не константа в политике, а поле консоли (`per_minute`, `EVENTS_PER_MINUTE`, по умолчанию 60), за которым стоит `timeline`.

Агрегат — это `(подсистема, единица, вид, класс)` со счётчиком и границами: **те же три числа**, которыми отчитывается подавленное окно в уроке 12. Тот же вопрос, заданный этажом выше: что происходило, сколько раз, между когда и когда. Тревоги идут отдельными группами и первыми — экран в режиме счёта не должен прятать их среди шума.

И граница, которую стоит назвать: **это живёт на консоли, а не в индексе.** Индекс отвечает процессам, а процесс читает тысячу строк так же легко, как десять. Процесс, который действует по событиям (в М10B это вычислитель сценариев, урок 25), спрашивает то же слияние и обязан получать **каждую** строку: правило, не увидевшее своё событие, — ровно тот провал, от которого всё это построено, и было бы странно прийти к нему, оберегая внимание машины. Счётчики получает только тот читатель, который устаёт.

Число — поле, а не константа, по той же причине: пультовая с четырьмя экранами и охранник с телефоном — не один читатель.

## Шаг 8 — Четыре записи

```python
    def create(self, body: dict, key: str | None = None, user: str = "operator") -> tuple[int, dict]:
        try:
            r = self.ctl.create(body, uid=self.seen.reserved(key) if key else None,
                                reserve=(lambda uid: self.seen.reserve(key, uid)) if key else None)
            self.journal.say("unit.created", sub=self.spec.name, target=str(r.get("id")), user=user,
                             fields=",".join(sorted(str(k) for k in body)))
            return 201, {**mask_secrets([r])[0], "worker": None}      # placed by the controller's next pass, never by the console
        except Exists as e:
            return 409, {"detail": str(e), "error": "exists"}
        except Refused as e:
            return 400, {"detail": str(e), "error": str(e)}
        except TooLarge as e:
            return 413, {"detail": str(e), "error": str(e)}
        except ClaimLost as e:                                        # taken over while this console stood still: the
            return 409, {"detail": str(e), "error": "taken over"}     # other one answers the key, and nothing was written
        …
```

Несколько строк, и в них решения, каждое на своей строке.

`201`, а не `200`: создано нечто новое, у него есть идентификатор, и он в теле. Обычный HTTP.

`uid`/`reserve` — номер, зарезервированный в заявке ключа идемпотентности (шаг 4): перехвативший создаёт под ним. `unit.created` — строка журнала с именами полей, не значениями (пароль — одно из них).

`mask_secrets` — потому что этот ответ ещё и копия под ключом: незамаскированный, он положил бы второй экземпляр секрета в хранилище.

`{**…, "worker": None}` — та самая честность. Контроллер вернул строку такой, какой она легла в хранилище: с `id`, `revision`, полями по умолчанию. Поля `worker` в ней нет вовсе — размещение живёт в другом ключе (урок 5). Консоль дописывает его явным `None`, чтобы страница не гадала: единица есть, воркера у неё пока нет, приходите через секунду.

`Refused` → `400`. Исключение приходит из `refuse` (урок 9): оператор прислал поле, которого нет в спецификации, или значение не того типа, или нарушил ограничение. Это ошибка клиента, и текст в ней уже человеческий — его не надо переводить, его надо передать.

`Exists` → `409 {error: "exists"}`. Id уже занят единицей (`spec.Exists` — подкласс `Refused`, поэтому ветка стоит первой): запрос правильный, но опоздал — то, что он создаёт, уже есть. Страница читает это как «уже там» и идёт к существующей строке, а не исправляет форму. Тот же POST под **тем же** ключом идемпотентности сюда не доходит — он получает сохранённый 201 (шаг 4); 409 получает второй POST под другим ключом:

```
POST /counters {"name": "zz"} + Idempotency-Key: z1   → 201 {"id": "zz", …, "worker": null}
POST /counters {"name": "zz"} + Idempotency-Key: z2   → 409 {"detail": "testsub unit zz exists", "error": "exists"}
```

Тест: `test_worker_life.py::test_a_create_under_a_name_a_unit_has_is_409_exists`.

Почему `detail` и `error` — одно и то же дважды? Потому что страница читает `detail`, а тесты и внешние клиенты М12 читают `error`. Дублирование в четыре символа дешевле, чем согласовывать два потребителя.

```python
    def update(self, uid, body: dict, user: str = "operator") -> tuple[int, dict]:
        try:
            row = self.ctl.update(uid, body)
            self.journal.say("unit.changed", sub=self.spec.name, target=str(uid), user=user,
                             fields=",".join(sorted(str(k) for k in body)), revision=row.get("revision"))
            return 200, mask_secrets([row])[0]
        except Refused as e:
            return 400, {"detail": str(e), "error": str(e)}
        except TooLarge as e:
            return 413, {"detail": str(e), "error": str(e)}
        except KeyError:
            return 404, {"detail": "no such unit", "error": "no such unit"}
```

То же самое плюс одна ветка. (`TooLarge` — 413: правка, которая не помещается в строку хранилища, отказывается у консоли, с размером и пределом в тексте, до того как что-то записано. Поле `fixed` после создания не меняется — это 400 от контроллера: ворота спрашивают право на единицу, о которой строка сейчас, и правка не должна уводить строку мимо этой проверки.) `KeyError` — единицы нет — это `404`, не `400`: клиент ничего не написал неправильно, он обратился к тому, чего нет. Разница видна оператору: при `400` надо исправить форму, при `404` — обновить страницу.

`update` не возвращает `worker: None`. Единица уже жила, размещение у неё могло быть, и затирать его выдумкой было бы хуже, чем не упомянуть.

```python
    def delete(self, uid, user: str = "operator") -> tuple[int, dict]:
        if self.ctl.unit(uid) is None:
            return 404, {"detail": "no such unit", "error": "no such unit"}
        self.journal.say("unit.deleted", sub=self.spec.name, target=str(uid), user=user)
        try:
            self.ctl.delete(uid)
        except Exception as e:
            self.journal.say("unit.delete.failed", sub=self.spec.name, target=str(uid), user=user, error=str(e))
            raise
        return 200, {"deleted": uid}
```

**Кто удалил.** От удалённой единицы остаются надгробие и номер ревизии; имени среди них нет, и на вопрос «кто удалил единицу 7» ответа не было (ревью платформы; обратная связь, BN). Теперь консоль пишет строку в **журнал** — `w2cplatform/journal.py`:

```python
from .events import AUDIT, OBSERVATION, EventLog   # the journal's tree: one of the platform's own (`OWN_OF_TREES`)
…

class Journal:
    """One role's line into `audit/<role>/e1/…` on this server's resource. With no resource: the log only."""

    def __init__(self, root: str | None, role: str, wall):
        self.role, self.wall = role, wall
        self.log = EventLog(root, AUDIT, role, 1) if root else None

    def say(self, kind: str, cls: str = OBSERVATION, **fields) -> str | None:
        log.info("%s: %s %s", self.role, kind, fields)
        if self.log is None:
            return None
        try:
            return self.log.append(self.wall(), kind, cls, durable=True, **fields)
        except OSError:
            log.exception("%s: %s could not be written to the journal", self.role, kind)
            return None
```

Журнал — не отдельный механизм, а **семейство видов** в том журнале событий, который уже есть: дерево платформы `audit` (спека с таким именем не загрузится), единица — роль писателя (`console`, `resource`, `controller`). Всё, что умеет журнал событий, достаётся ему даром: его читает таймлайн, хранит проход хранения, копирует зеркало, отдаёт индекс.

Виды, которые консоль платформы пишет сама:

| Вид | Что значит |
|---|---|
| `unit.created`, `unit.changed` | единица создана; изменены поля (имена полей, не значения) — и кто (третье ревью) |
| `unit.deleted` | удалена единица любой подсистемы: какая и кто. Пишется **до** удаления — удалённая единица уже не свидетель самой себе; неудача — `unit.delete.failed` |
| `policy.changed`, `drain.started`, `drain.ended`, `schema.raised` | политика размещения, вывод сервера, номер схемы — кто и что (третье ревью) |
| `server.labels.set`, `.cleared`; `server.decommission_requested`, `_withdrawn`, `_refused` | что сервер видит, по слову администратора; списание сервера — кто, какого и почему |
| `door.issued` | токен двери держателя выдан: кому, на какую единицу, у какого держателя, до когда (шаг 12) — то, что консоль может сказать о байтах, которых не видит |
| `access.denied`, `access.break_glass` | отказ по праву; действие под аварийной сессией — **тревога** (шаг 12а) |
| `access.break_glass.opened`, `.refused`, `.limited` | **тревога:** аварийная сессия открыта, в ней отказано, дверь под потоком попыток (М12, урок 4) |
| `<table>.written`, `<table>.deleted` | строка объявленной таблицы записана или удалена (шаг 12); спека может назвать виды сама: `journal: {written: …, deleted: …}` |
| вид из `requests.journal` | заявка подана (шаг 12), если спека назвала вид |

Последние две строки — виды, которые называет **спека**, а не консоль: платформа пишет строку, не зная, что она значит. В М10B, например, спека регистратора называет запись строки удержания `archive.keep.made`, а её удаление — `archive.keep.lifted`. Свои строки журнала пишут и другие роли: ресурс — `events.removed` (проход хранения удалил бакеты, урок 14), контроллер — то, что он сделал со слотами и воркерами. Дверь держателя пишет в журнал своего процесса то, что отдала; консоль этих байтов не видит и о них не пишет.

Три решения, каждое в одну строку. **О чём строка** — в полях `sub` и `target`, а не `subsystem` и `unit`: эти два — собственные поля строки (кто её написал), и поле с тем же именем отвечало бы за них у каждого читателя. И не `of`: это собственная колонка индекса (ссылка `<sub>/<id>`, шаг 2). **`say` не бросает исключений:** сделанное сделано, и журнал, который не записался, не должен ни отменить его, ни скрыть — он говорит об этом в логе процесса. **Срок** — как у тревог, по умолчанию три года (урок 14).

Чего в журнале нет: того, что воркер подсистемы теряет по собственному правилу, тысячами и без участия человека. Строка на каждую такую потерю была бы шумом, сквозь который журнал пришлось бы читать. То, о чём человеку надо узнать, — тревога в собственных событиях подсистемы. В М10B так поступает регистратор: минуты, которые перезаписало кольцо тома, в журнал не идут, а сохранённое, которое кольцо всё-таки забрало, — тревога `archive.keep.lost` в его событиях (урок 27).

«Кто» — имя, которое назвал вызывающий (`X-User`), или — при включённых воротах (шаг 12а) — имя, которое доказал токен и которым ворота заменили заголовок. Вне домена аутентификации нет, и журнал не делает вид, что она есть.

**Строка журнала — на носителе.** `EventLog.append` пишет наблюдение с `flush` и без барьера — потеря питания теряет его, и это принятая цена (урок 12). Для «кто удалил единицу» цена другая: удаление на диске, а строки о нём нет. Поэтому `Journal.say` пишет каждую строку с барьером (`append(durable=True)`), не меняя класса — журнал не уходит в дерево тревог, он просто не теряется (второе ревью).

«Есть ли такая» спрашивается **до** удаления, а не узнаётся из исключения (`try` вокруг `ctl.delete` — только ради строки `unit.delete.failed`). `ctl.delete` из урока 10 идемпотентен по построению: он снимает строку, размещение, эпоху и слот, и ему всё равно, было ли что снимать. Если бы консоль просто звала его, второй `DELETE` вернул бы `200` — и оператор, дважды нажавший на крестик, не узнал бы, что второй раз был вхолостую.

Здесь курс сознательно выбирает **не** идемпотентность: у `DELETE` нет ключа идемпотентности (дальше в `dispatch` это видно), и второй удар честно отвечает `404`. Формула, которой стоит держаться: «пропало — значит пропало». Между гонкой двух операторов и молчаливым «ок» на удаление несуществующего выбрано второе как более вредное.

## Шаг 9 — Отметка оператора

```python
    def mark(self, body: dict, user: str) -> tuple[int, dict]:
        if self.marks is None:
            return 503, {"detail": "no resource on this server to write marks into", "error": "no resource on this server to write marks into"}
        why = ref_fault(body.get("unit")) if "unit" in body else "a mark names the unit it is about, <sub>/<id>"
        if why:
            return 400, {"detail": why, "error": "a mark names a unit"}
```

Третий код состояния в уроке, и снова по вине, а не по удобству. `503` — «не я и не ты»: консоль поднята на сервере, где нет ресурса, писать некуда, и это состояние машины, а не запроса. Клиенту имеет смысл повторить позже; на `400` повторять бессмысленно.

`400` — отметка без единицы или с единицей, названной не ссылкой. Отметка оператора — это «здесь что-то было» **про что-то**; без ссылки она не событие, а запись в дневнике. И ссылка — только `<sub>/<id>` (`doors.ref_fault`): голый `7` не говорит, чья это единица.

```python
        path = self.marks.append(self.wall(), "mark", user=user, note=str(body.get("note", "")), **{OF: str(body["unit"])})
        return 201, {"subsystem": "console", "unit": self.instance, "bucket": os.path.relpath(path, self.marks_root)}
```

`OF` — это поле `of`, **вторая колонка индекса событий** (урок 13). Запрос `/events?unit=testsub/c1` находит строки самой единицы и все строки, у которых `of` — эта единица: отметка оператора ляжет на таймлайн единицы рядом с её собственными событиями и событиями единиц, которые о ней. Одно поле и один формат для всех подсистем — платформе не нужно знать, какая из них «главная» и каким типом она нумерует единицы.

Пишет консоль **в свой собственный бакет**: `console/<instance>/e1/…`, обоснованное в шаге 2. Ответ возвращает путь относительно корня ресурса — то, что тест сравнивает, и то, что можно показать оператору без утечки абсолютных путей.

## Шаг 10 — Вид по серверам

> **Два вопроса к одним и тем же heartbeat'ам, и путать их дорого.** `heartbeats(objects, prefix)` отвечает «что каждый из них сказал в последний раз» — это то, что нужно **экрану**: устаревшее показывается с возрастом, а не прячется. `holders(objects, prefix, now, lost_after=45.0, eyes=None)` отвечает «с кем я могу разговаривать» — это то, что нужно **подписчику**, и разница между ними ровно одно сравнение.
>
> Функция стоит в платформе, а не у каждого вызывающего, по той же причине, по которой Consul поставил `?passing=true` в запрос: **фильтр, который вызывающие применяют руками, — это фильтр, который вызывающие забывают.** Так и было: рекордер, шлюз и детектор опирались на `phase: running` из последнего heartbeat'а мёртвого воркера, а маршрут воспроизведения не проверял ничего.
>
> Кому положено `holders`/`holder_of`, а не `heartbeats`: **всем, кто после поиска пойдёт с найденным разговаривать** — подписаться на раздачу, спросить дверь архива, послать предложение. В М10B это рекордер, шлюз живого видео, детектор, детджоб, обзор и маршрут воспроизведения. `heartbeats` остаётся у консоли и у страницы — им как раз нужен мёртвый воркер с его возрастом.

Страница показывает не только единицы, но и машины: где есть воркеры, где живой ресурс, куда контроллер сейчас поставил бы, а куда нет и почему. Этого нет ни в одном ключе — это собирается из heartbeat'ов.

```python
    def servers(self) -> dict:
        with self.ctl.one_pass():
            return self._servers()

    def _servers(self) -> dict:
        ctl, now = self.ctl, self.wall()
        out: dict[str, dict] = {}
        for w, hb in heartbeats(ctl.objects, ctl.sub.name + "/").items():
            s = out.setdefault(hb.extra.get("server", "?"), {"resource": "unknown", "workers": []})
            s["workers"].append({"worker": w, "load": ctl.load(w), "capacity": ctl.capacity_of(w), "labels": hb.extra.get("labels", ""),
                                 "place": ctl.place_of(w),
                                 "state": "live" if ctl.eyes.fresh(ctl.sub.heartbeat_key(w), hb.token, self.lost_after, hb.ts,
                                                                   ctl.sub.name) else "stale", "idle_by_policy": False})
```

`one_pass` — один взгляд на хранилище на весь ответ (`contract.one_pass`): ниже каждый сервер и каждый воркер спрашивают heartbeat'ы и ресурсы, и вне прохода каждый такой вопрос был бы новым перечислением.

**Реестра машин нет.** Список серверов получается перечислением того, что билось: `hb.extra["server"]` — строка, которую воркер положил в свой heartbeat (урок 4). Сервер, с которого никто не бился, в ответе не появится, и это правильно: с точки зрения системы его нет.

`"?"` для воркера без поля `server` — не заглушка ради красоты, а видимая аномалия: если в ответе появился сервер `?`, значит кто-то бьётся, не сказав откуда.

**Чего здесь нет: ни одного поля подсистемы.** Платформа не знает, что подсистема держит на сервере. Если подсистеме есть что показать под сервером — строки своей таблицы, у которых поле называет сервер, — она объявляет это в спеке (`servers: {show: [{table, by, title, columns}]}`), и страница читает объявление из `/spec` (шаг 3) и строки из таблицы (шаг 12). В М10B так под сервером показываются тома регистратора: `{table: volumes, by: server, …}`. Консоль при этом не прочитала ни одного поля heartbeat'а, которое знала бы только одна подсистема.

`state` — `live` или `stale`, и судит его не сравнение чужого `ts` со своими часами, а то, что **эта консоль видела, как heartbeat менялся**, по своим часам (`ctl.eyes.fresh`; тринадцатое ревью). Не «мёртв»: консоль не выносит приговоров, это дело контроллера и его `failover_seconds`.

`place` — **где** воркер, в том, в чём подсистема считает места (`place_by`, урок 11). Для почти всех это сервер, и поле повторяет ключ словаря. У подсистемы, которая считает места по-другому, `place` — единственное, что различает её воркеров на одном сервере (в М10B у регистратора место — том: коробка с тремя дисками держит трёх регистраторов). Страница берёт отсюда места, которые можно предложить оператору: имя, за которым стоит живой воркер, вместо строки, которую никто не подтверждает.

```python
        for w in ctl.idle_by_policy(list(heartbeats(ctl.objects, ctl.sub.name + "/"))):    # servers: distinct — one worker per server carries units
            for s in out.values():
                for row in s["workers"]:
                    if row["worker"] == w:
                        row["idle_by_policy"] = True
```

`idle_by_policy` из урока 11: при `servers: distinct` единицы несёт один воркер на сервер, остальные живы и пусты. Без этого флага оператор видит воркер с нулевой нагрузкой и решает, что тот сломан. Флаг переводит «пустой» в «пустой по правилу».

Три вложенных цикла на десятке воркеров — не проблема, и переписывать их в словарь ради красоты не стоит; но если вы поднимете счёт до сотен, это первое место, куда смотреть.

```python
        for server in resources_seen(ctl.objects):
            out.setdefault(server, {"resource": "unknown", "workers": []})
        …                                                # servers with a labels row, a decommission asked or done
        for server, s in out.items():
            …                                            # labels: the node's and the administrator's; draining; decommission
            s["resource"] = ctl.resource_state(server, self.lost_after)
            …
            s["requires_resource"] = ctl.spec.requires == "resource"
            s["placeable"] = (not (s["requires_resource"] and s["resource"] == "silent") and not s["draining"]
                              and server not in asked)
            s["why"] = (f"server {server} decommissioned" if server in asked else
                        f"server {server} draining" if s["draining"] else
                        f"resource on {server} silent" if not s["placeable"] else None)
            s["workers"].sort(key=lambda x: x["worker"])
        return {"policy": ctl.policy(), "servers": dict(sorted(out.items()))}
```

Первый цикл добавляет серверы, у которых **бьётся ресурс, но нет воркеров**. Такой сервер существует для системы — на нём живёт ресурс — и должен быть на экране, пусть и с пустым списком. Так же попадает в ответ сервер, о котором есть слово администратора: строка меток (что сервер видит, урок 11) или списание (урок 7).

Пропущенное в середине — то, что платформа знает о машине сама: метки узла и метки администратора рядом (`labels_node`, `labels`, `labels_source` — `console`, `node` или `unknown`, когда строка меток есть и не читается или консоль строк ни разу не прочла; ответ — `server_labels_of` контроллера, урок 11), вывод (`draining`), что ресурс говорит о себе (`resource_heard_at`, адрес `resource_url`, диск под ним `space: {total, free}` в байтах), списание и его отказ словами (`decommission`, `decommission_refusal`), у каждого воркера — завис ли он и с какого времени (`hung`, `hung_since`) и не просит ли его имя другой процесс (`name_conflict`). Всё это — ответы контроллера, пересказанные для показа.

`placeable`/`why` — то же правило, по которому решает `_pool` (урок 11), пересчитанное для показа. Дублирование логики? Да, и намеренное: контроллер отвечает решением, консоль — объяснением, и объяснение должно существовать до того, как решение понадобится. Если правило меняется, оно меняется в двух местах — и в уроке 11 у него один тест на оба.

Сортировка — чтобы экран не дрожал между обновлениями.

## Шаг 11 — Метрики

```python
    def metrics_text(self) -> str:
        p = self.spec.name
        hbs = heartbeats(self.ctl.objects, p + "/"); now = self.wall()
        live = {w: hb for w, hb in hbs.items()            # by what this console saw change (the thirteenth pass)
                if self.ctl.eyes.fresh(self.ctl.sub.heartbeat_key(w), hb.token, self.lost_after, hb.ts, p)}
        hk = self.ctl.sub.heartbeat_key
        failover = self.ctl.failover_seconds()

        def n(w: str, field: str, kind=float, default=0):                # a worker's field
            return number(f"{hk(w)}#{field}", hbs[w].extra.get(field), kind, default)
```

**Каждое число heartbeat'а здесь читается через `n` (у ресурса — через `rn`, в `platform_metrics` ниже), а числа отчёта о проходе — через `r`** (седьмое ревью, часть 2). Голое `int(headroom)` или `float(space.full)` бросало на одном слове в одном поле одного heartbeat'а, и пропадала вся страница метрик подсистемы — а с ней каждый алерт. `rows.number(key, value, kind, default)` (урок 8) отдаёт конечное число нужного вида; слово, `nan` или `inf` — «не сказано»: `default` (0, у возрастов −1), посчитано один раз на объект и поле (ключ `<объект>#<поле>`, таблица `field`), остальная страница стоит. Отсутствующее поле — тоже `default`, но не считается. Тест: `test_row_reader.py::test_one_word_in_one_heartbeat_field_does_not_take_the_metrics_page`.

Формат Prometheus — это текст. Никакой библиотеки, никакого реестра, никакого клиента: `# TYPE`, имя, метки в фигурных скобках, число. Двадцать строк кода вместо зависимости, которую пришлось бы тащить на коробку.

Каждое имя начинается с `p = spec.name`: `testsub_workers_live`, `vms_workers_live`, `rec_workers_live`. **Имена метрик выводятся из спецификации**, как и всё остальное в этой консоли; добавив подсистему, вы получаете её метрики бесплатно.

```python
        lines = [f"# TYPE {p}_workers_live gauge", f"{p}_workers_live {len(live)}",
                 f"# TYPE {p}_worker_headroom gauge",
                 *[f'{p}_worker_headroom{{worker="{label(w)}",server="{label(hb.extra.get("server", "?"))}"}} {n(w, self.spec.headroom_from, int)}' for w, hb in live.items()],
                 f"{p}_headroom {sum(n(w, self.spec.headroom_from, int) for w in live)}",
```

`headroom_from` — имя поля heartbeat'а, взятое из YAML (урок 9). Платформа не знает, в чём подсистема считает запас своего воркера; она знает, что поле называется так, как сказано в спецификации (`placement.headroom.from`; у `testsub` это `headroom`).

Сумма запаса по живым воркерам — метрика без меток: именно её читает автомасштабирование в М11. Метрика с метками — для глаз, метрика без меток — для решения.

```python
                 f"# TYPE {p}_worker_load gauge",              # assigned / capacity: what a target-value policy scales on
                 # …over the workers that ARE a place. A worker holding no place (`place_of` empty) is a
                 # spare: it carries nothing and reports zero capacity, which this formula would read as
                 # fully loaded — and a target-value policy would then scale out for ever, one spare
                 # demanding the next. A spare is counted below instead, as what it is.
                 *[f'{p}_worker_load{{worker="{label(w)}"}} {1 - n(w, self.spec.headroom_from, int) / max(1, n(w, self.spec.capacity_from, int, 1)):.3f}'
                   for w in live if self.ctl.place_of(w) != ""],
                 f"# TYPE {p}_spare_workers gauge",            # running, holding no place, ready to take one
                 f'{p}_spare_workers {sum(1 for w in live if self.ctl.place_of(w) == "")}',
```

Нагрузка как `1 - запас/ёмкость`. `max(1, …)` — защита от деления на ноль, которая случается ровно один раз: у воркера, успевшего ударить heartbeat'ом до того, как он посчитал свою ёмкость.

```python
                 f"# TYPE {p}_epoch_conflicts counter",
                 *[f'{p}_epoch_conflicts{{worker="{label(w)}"}} {n(w, "conflicts", int)}' for w in hbs],
```

Первая метрика, которая считается по **всем** heartbeat'ам, а не только по живым: конфликты эпох — это история, и умерший воркер свой счёт уже не поправит, но рассказать о нём успел. Ненулевые конфликты означают, что двое держали одну единицу и отсечение сработало — то, ради чего написан урок 6.

```python
                 f"# TYPE {p}_failover_seconds gauge",
                 f'{p}_failover_seconds{{kind="worst"}} {max([self.worst_failover, getattr(self.ctl, "failover_worst", 0.0), *failover.values()])}',
                 *[f'{p}_failover_seconds{{kind="last",worker="{label(w)}"}} {s}' for w, s in sorted(failover.items())],
                 f"# TYPE {p}_failovers_unmeasured gauge", f"{p}_failovers_unmeasured {getattr(self.ctl, 'failovers_unmeasured', 0)}",
                 # What the readers of heartbeats skipped and measured (the review's second pass, M6, M9): objects that did
                 # not parse, since this process started; and the furthest a heartbeat's clock has been AHEAD of this
                 # one's — at `FUTURE_TOLERANCE` such a worker stops counting as live.
                 f"# TYPE {p}_heartbeats_garbled counter", f"{p}_heartbeats_garbled {GARBLED.get(p, 0)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_max gauge", f"{p}_heartbeat_skew_seconds_max {round(SKEW_MAX.get(p, 0.0), 1)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_min gauge", f"{p}_heartbeat_skew_seconds_min {round(SKEW_MIN.get(p, 0.0), 1)}"]
```

`failover_seconds` **измеряется**, а не только называется (восьмое ревью, найдено координатором). Раньше `kind="worst"` был числом, с которым собрали консоль, — арифметикой урока 11; в кластере его не передают, и после любого failover там стоял `0.0`. Теперь последний failover каждого воркера меряется (`SpecController.failover_seconds`, урок 11) и называется по воркеру — `kind="last",worker=…`. Меряется он на одних часах (девятое ревью): на том же сервере — начало этого экземпляра минус последний heartbeat предыдущего, по тому, что они написали (`previous_server` равен `server`); на другом сервере — то, что консоль сама видела по своим часам между последним сдвигом heartbeat'а старого экземпляра и появлением нового. А `kind="worst"` — наибольшее из числа, данного консоли (`worst_failover`: цифра учений, паспорт), из всего, что этот процесс измерил за время работы (`failover_worst`), и из последних: более короткий второй failover того же воркера худший не стирает. Разница между измеренным и данным — самое полезное на этом графике. Переключение, которое на одних часах не измерить (другой сервер, а консоль не видела предшественника живым; отрицательный промежуток), числом не становится, а считается: `<p>_failovers_unmeasured` — сколько воркеров сейчас с неизмеренным переключением. Тест: `tests/cluster/test_lesson4_failover.py::test_a_restart_is_measured_on_one_clock_and_a_name_taken_elsewhere_by_the_readers` (М11).

**Значение каждой метки экранируется** (`label`: `\`, `"`, перевод строки; восьмое ревью, часть 4). Имя записи `7"x` ломало строку `/metrics`, и Prometheus отвергал весь скрейп. Новые имена с `"`, `|` и управляющими символами отказываются при создании (`doors.unnamable`), а уже записанные проходят через `label`.

**Сколько единиц идёт — тоже объявление, а не строка консоли.** Счётчик работающих единиц, который страница показывает в строке состояния, подсистема объявляет как любое своё число (ниже) и называет его один раз в `console: {running: …}`. У `testsub`:

```yaml
metrics:
  - {name: counters_running, from: status.phase, agg: count, equals: running, live: true}   # the running gauge (`console.running`)
console:
  running: counters_running
```

Строка выходит `testsub_counters_running`: записи статуса с `phase: running` по всем живым воркерам — то есть **не** «сколько настроено», а «сколько на самом деле идёт». Умолчания нет: спека, которая не назвала метрику, счётчика не имеет (`running_gauge: null` в `/spec`), а `console.running`, который называет не свою метрику, — отказ при загрузке спеки («declare it under `metrics:`»). Одно число объявлено в одном месте, и консоль его не считает отдельно.

Дальше в `lines` идут возраст снимка, проход контроллера и строки, которые не разбираются (таблица ниже), очередь сборщика блобов, если у подсистемы есть блобы, числа для скрипта запасных, если спека говорит `placement.offers: true`, число нужных воркеров у подсистемы, размещаемой по строкам (`placement.places`), числа, которые подсистема объявила сама (ниже), и — один раз на процесс консоли — числа платформы. Ответ (`return "\n".join(lines) + "\n"` в конце метода) заканчивается переводом строки: Prometheus на это не жалуется, а `curl` без него печатает промпт впритык.

```python
        places = self.places_needed(live) if self.spec.places else None
        spares = self.spares_lines(rep, now, hbs, places or 0) if self.spec.offers else []
        lines += spares or (self.places_lines(places) if places is not None else [])   # one `workers_needed` series
        from . import metrics
        lines += metrics.lines(self.spec, self.ctl, hbs, live, now)   # the subsystem's own numbers, as its spec declares them
        if self.says_platform:
            lines += self.platform_metrics(now)                # the platform's, once per console process
        return "\n".join(lines) + "\n"
```

`spares_lines` — то, что читает скрипт запасных узла: `<p>_workers_needed{labels}`, `<p>_units_short`, `<p>_spare_offers` из отчёта прохода контроллера и метки серверов, и только пока отчёт не старше `SPARES_FRESH` (60 с): скрипт, читающий число остановившегося контроллера, запускал бы процессы под нехватку, которой давно нет. `places_lines` — то же первое число для подсистемы, чьи места — строки её таблицы (урок 11): `<p>_workers_needed{labels=""}` — места, которые подходят под `where` и которых не держит ни один живой воркер, минус живые воркеры без места (`places_needed`). Оно считается здесь, на каждом скрейпе, из хранилища и пульсов, которые консоль читает и так, — от `place_by` не зависит. **Серия одна, кто бы её ни говорил.** У спеки и с `offers`, и с `places` обе половины печатали бы `<p>_workers_needed{labels=""}` со своей строкой `# TYPE` — две строки типа и повторённая серия, и Prometheus отвергает весь скрейп. Поэтому свободные места прибавляются к строке пустого набора в `spares_lines` (`places_needed` — её аргумент), а отдельно `places_lines` печатает их, только когда строк запасных нет: отчёт прохода устарел или спека не говорит `offers`.

**Числа подсистемы — объявления, а не код.** Платформа не знает, что у подсистемы стоит считать. Подсистема говорит это в спеке, списком `metrics:`, а консоль печатает строки из того, что уже читает: строки таблиц и heartbeat'ы (`w2cplatform/metrics.py`). Форм две:

| Форма | Что считает |
|---|---|
| `count: table <t>` (и `where: {поле: значение}`, `unheld: true`, `unless: {table, where}`) | строки одной из таблиц спеки: с таким значением поля; ещё и те, которых не держит ни один живой воркер; ноль, пока в другой таблице есть такая строка |
| `from: heartbeat.<путь>` или `status.<путь>`, `agg` | поле heartbeat'а воркера или каждой записи его статуса: само число (`value`), флаг (`flag`, с `equals` — равно ли одному из значений), возраст, метка, число записей по значению (`count`; с `equals` — одна строка по всем воркерам), сумма или максимум по всем воркерам, гистограмма; сегмент пути `<имя>` проходит по всем ключам карты и становится меткой; `live: true` — только живые воркеры, `when` — только записи, где поле сказано |

Строка выходит `<sub>_<name>` (`type` — `gauge` по умолчанию, `counter` или `histogram`; `labels` — постоянные метки), с меткой `worker` у поля heartbeat'а и `unit` у записи статуса; каждое число — через `rows.number`, как выше. Объявление проверяется при загрузке спеки: неизвестный ключ, неизвестная форма, неизвестный `agg`, таблица, которой у спеки нет, — спека не загружается. Каждую форму и каждый ключ объявляет `tests/testdata/testsub2.subsystem.yaml` — вторая подсистема для тестов платформы, которая говорит всё, что платформа читает в спеке, по разу:

```yaml
metrics:
  - {name: tallies_running, from: status.phase, agg: count, equals: running, live: true}
  - {name: shelves_open, count: table shelves, where: {enabled: true}, unheld: true}
  - {name: notches_unshelved, count: table notches, unless: {table: shelves, where: {kind: reserve}}}
  …
  - {name: jam, from: heartbeat.jam, agg: flag, equals: [stuck, "yes"]}
  …
  - {name: adds_total, from: "heartbeat.adds.<outcome>", agg: sum, type: counter, labels: {kind: add}}
  …
  - {name: wait_seconds, from: heartbeat.wait, agg: histogram, type: histogram, buckets: [1.0, 5.0]}
```

**Число печатается по значению, а не по тому, как его написал воркер** (ADR 0055). У Prometheus отсчёт — float64, и `61` и `61.0` для него одно число. Продукт читает heartbeat во float64 и этих двух написаний не различает. Курс же печатал число так, как его написал воркер: целое в JSON — целым, дробное — дробным, `61.0` оставалось `61.0`. Так одно значение получало в двух деревьях два текста, а то, как heartbeat записал число, просачивалось в строку метрики. Теперь правило одно (`metrics.value_text`, в продукте `sampleText`):

- целое значение печатается целым: `61`, возраст (`agg: age`) тоже `10`, а не `10.0`;
- нецелое — кратчайшей записью, которая читается обратно в то же значение: `7.5`, `0.1`. Где запись с экспонентой короче, она и печатается, и Prometheus её читает: `1e-07`, `1e+21`, `1.2345675e+06`. Граница та же, что у `strconv.FormatFloat(f, 'g', -1, 64)` в Go: экспонента ниже 1e-4 и от 1e6, а целое от 1e15.

По этому правилу печатается отсчёт, граница корзины (`le="1"`; `le="1000000"`, где прежний `%g` давал `1e+06`) и слово, с которым сравнивает `equals`: `equals: [1]` совпадает и с `1`, и с `1.0` в heartbeat'е. Дашборд, который матчил `61.0`, надо поправить. Тесты: `test_recorder_metrics.py`, `test_spec_declarations.py::test_a_subsystems_own_numbers_are_declared_and_the_console_prints_them_from_the_store_and_the_heartbeats`.

Каждый ключ и каждый оператор, который платформа читает в спеке, должен быть в ходу — у двух подсистем продукта или у тестовой подсистемы платформы; ключ, нужный одной подсистеме, — это её код в одежде платформы. Это проверяет `tests/test_spec_rule.py::test_every_key_and_operator_the_platform_reads_is_used_by_two_subsystems_or_by_a_test_subsystem`. В М10B те же формы объявляет, например, регистратор: `volumes_declared` (`count: table volumes`), `recordings` (`from: status.phase, agg: count`), `keeps_unprotected` (`unless`). Тест: `test_spec_declarations.py::test_a_subsystems_own_numbers_are_declared_and_the_console_prints_them_from_the_store_and_the_heartbeats`.

**Ресурсы — числа платформы, и говорятся они один раз, под именем `w2c`** (решение курса о платформенных именах, по правилу продукта: платформа — `w2c`, VMS — одна из её подсистем). Ресурс — один на сервер, что бы в него ни писали подсистемы. А каждая смонтированная консоль повторяла его числа под своим префиксом — `<sub>_resources_live` у каждой подсистемы процесса: один факт столько раз, сколько подсистем смонтировано, и алерт на диск, написанный по префиксу одной подсистемы, молчал бы на консоли без неё. Теперь живые ресурсы, их диски, ожидания, нечитаемые строки, зеркало и восстановление — в `platform_metrics`, с префиксом `w2c`:

```python
    # THE PLATFORM'S OWN NUMBERS: the resources, under the platform's name `w2c` — one resource per server, whatever
    # subsystems write into it, so one set of lines per console process and not one per subsystem (`metrics_text`).
    # Every number of a heartbeat through `rn`, as above (the review's seventh pass).
    PLATFORM = "w2c"

    def platform_metrics(self, now: float) -> list[str]:
        p, res = self.PLATFORM, resources_seen(self.ctl.objects)

        def rn(server: str, field: str, value, kind=float):               # a resource's field
            return number(f"platform/resources/{server}/heartbeat#{field}", value, kind)
        lines = [f"# TYPE {p}_resources_live gauge",
                 f"{p}_resources_live {sum(1 for s in res if self.ctl.resource_state(s, self.lost_after) == 'live')}",
                 # resource heartbeats that did not parse, since this process started (the review's second pass, M6)
                 f"# TYPE {p}_resource_heartbeats_garbled counter", f"{p}_resource_heartbeats_garbled {GARBLED.get('platform', 0)}"]
```

Метод кончается числами семейства запросов (`requests.metrics_lines()`): `w2c_requests_expired_total{sub}` и `w2c_requests_unknown_total{sub}` — заявки, которые уборка этого процесса закончила без ответа (никто не исполнил к сроку; держатель начал и пропал, не сказав, чем кончилось). Это тоже числа процесса, а не подсистемы: уборку заявок ведёт процесс консоли (`host.requests_loop`), а что она делает, разбирает [урок 14](14-Resource.md), шаг «Семейство запросов».

Кто их говорит, решает `Mount` (шаг 14): консоль, которая работает одна, — сама; в `Mount` — только корень, в том числе когда подсистему смонтировали позже (`console.says_platform = console is self.root` в `Mount._adopt`). Скрейп всех страниц процесса видит каждое число ресурса один раз. Тест: `test_one_bad_element.py::test_the_resources_are_said_once_per_console_under_the_platforms_name`.

**Проход контроллера — тоже отсюда.** У контроллера нет порта, и спросить его не о чем. Он оставляет отчёт о проходе в хранилище объектов (урок 11), а консоль его отдаёт — по каждой подсистеме, с её префиксом:

| Метрика | Что говорит |
|---|---|
| `<p>_reconcile_last_pass_age_seconds` | давно ли проход шёл; `-1` — ни разу |
| `<p>_reconcile_last_success_age_seconds` | давно ли он прошёл без исключения |
| `<p>_reconcile_pass_seconds`, `<p>_reconcile_failures` | сколько занял последний; сколько проходов упало |
| `<p>_units_unplaced` | единицы, которые должны где-то быть и нигде не стоят |
| `<p>_units_diverged` | назначения, которые последний проход привёл к строкам размещения |
| `<p>_units_moved_for_reach`, `<p>_units_moved_for_reach_total` | единицы, которые проход увёз или снял с размещения, потому что их сервер их больше не видит (`ensure_reach`, урок 11, шаг 17; обратная связь DQ): за последний проход — и с начала хранилища, счётчиком (десятое ревью: gauge последнего прохода скрейп раз в 15 с видел только на трети переездов; `test_server_labels.py::test_moves_for_reach_are_counted_since_the_store_was_new_and_said_in_the_log`) |
| `<p>_units_waiting_for_reach` | единицы групп (`group_by`, у VMS — каналы одного устройства), которые последний проход оставил целыми на сервере, их больше не видящем: везти всю группу некуда, или она больше бюджета прохода (урок 11, шаг 17; одиннадцатое ревью — это была строка лога, и только). Не ноль надолго — единицы, которые никто не обслуживает: поднять `REACH_BUDGET`, дать место или увезти группу руками |
| `<p>_servers_labels_unread` | серверы, чья строка меток не прочиталась при последнем чтении прохода: их единицы не двигаются, пока строка не прочтётся (урок 11, шаг 1; одиннадцатое ревью — непрочитанная днями строка была видна только на странице); `-1` — контроллер строк ни разу не прочёл и не знает меток ни одного сервера (как в продукте). Тесты: `test_server_labels.py::test_one_row_that_cannot_be_read_is_that_servers_alone`, `::test_a_process_that_never_read_the_rows_knows_no_servers_labels` |
| `<p>_worker_fenced{worker}` | воркер жив, ничего не держит и ждёт: его сборка не понимает схему хранилища (урок 17). Воркер, чей **слот** забрал другой экземпляр, здесь не виден — он молчит, пока не найдёт слот (нет heartbeat'а под этим именем), а когда снова встал в строй, говорит `was_fenced` |
| `<p>_worker_store_errors{worker}`, `<p>_worker_pass_failures{worker}` | сколько раз хранилище ему не ответило; сколько раз часть его цикла упала |
| `<p>_worker_slots_garbled{worker}` | сколько строк слотов воркер не смог разобрать, когда искал слот: каждая — имя, которое никто не возьмёт и никого под ним не увидят (шестое ревью) |
| `<p>_worker_<table>s_garbled{worker}` | то же по другим таблицам, которые знает процесс консоли (`rows.counts`): `holds_garbled` — место, которое никто не возьмёт; `assignments_garbled`; у регистратора — `volumes_garbled`, `keeps_garbled`. Строки, каждая один раз, пока снова не разберётся, — не чтения (седьмое ревью: `holds_garbled` был в heartbeat'е, а здесь не был) |
| `w2c_resource_rows_garbled{server,table}`, `w2c_resource_space_garbled{server}` (числа платформы, один раз на процесс) | строки, которые не разобрал ресурс сервера, по таблицам, и испорченная `platform/space` (тогда водяная отметка — по последней настройке или умолчаниям); раньше были только в heartbeat'е ресурса (восьмое ревью) |
| `w2c_resource_restore_left{server}`, `w2c_resource_restore_failures_total{server}`, `w2c_resource_mirror_failures_total{server}`, `w2c_resource_mirror_too_big_total{server}` (числа платформы) | что ресурс ещё не привёз при `restore` (он повторяет его в своём цикле, по пиру и ведру), сколько раз пир или ведро не отдались, сколько копий зеркала не легло и сколько вёдер больше `MIRROR_MAX` пропущено (восьмое ревью) |
| `w2c_requests_expired_total{sub}`, `w2c_requests_unknown_total{sub}` (числа платформы) | заявки подсистемы, закрытые уборкой без ответа: просроченные никем и начатые держателем, который пропал (урок 14) |
| `<p>_requests_ledger_garbled` (у спеки с `requests.per_person`) | сколько людей, чей список открытых заявок эта консоль нашла нечитаемым: каждый из них ничего не подаёт (429), пока администратор не удалит строку (шаг 12) |
| `<sub>_<name>` из `metrics:` спеки | числа, которые подсистема объявила сама (выше): какие из полей heartbeat'а выводить и под каким именем, решает она, а платформа только печатает. В М10B так объявлены, например, `rec_volume_wait`, `rec_stream_behind_seconds`, `auto_wants_folded`, `vms_devices_slow`, `vms_commands_in_flight` — что каждое из них говорит, разбирают уроки М10B. Само число может говорить и платформа: `commands_in_flight` — поле heartbeat'а, которое пишет базовый воркер (`Worker.requests_fields`, урок 14), а спека VMS его только объявляет |
| `<p>_console_rows_garbled{table}` | строки, которые не смогла разобрать сама консоль, по таблицам (`rows.counts`): поля heartbeat'ов, прочитанные выше как «не сказано» (`table="field"`), строки единиц, которые ворота `/events` читают ради меток (`table="unit"`, шаг 12а), единицы, чьи фильтры упали, когда `/unplaceable` или `/drain` их проверяли (`table="unit_judged"`; урок 11) |

Четыре строки таблицы от `fenced` до `<table>s_garbled` — из heartbeat'ов. Размещение их не читает: ограждённый воркер и так ничего не держит. Их читает человек, которому иначе не отличить «воркер пуст» от «воркер ограждён» — и не заметить, что ёмкость уходит в строки, которые не читаются.

## Шаг 12 — Что подсистема объявляет, и дверь держателя

Платформа не знает ни одной подсистемы — а у подсистемы, кроме единиц, бывают свои списки (места, отметки «сохранить»), свои просьбы к держателю единицы (сделай, принеси) и свои байты, которые держатель отдаёт странице. Соблазн один и тот же для всех трёх: дать подсистеме вставить в консоль свой код — функцию, которой консоль отдаёт непонятые маршруты. Такая функция — крюк, и делает она то, что делает любой крюк: консоль платформы становится консолью тех подсистем, чей код в неё вставили, а байты идут через процесс, который не должен их видеть.

Правило, которое её заменило: **у подсистемы три места, и консоли среди них нет.** Что строка значит и кто её может писать — в спеке. Что сделать с данными — в воркере подсистемы. Что показать — в странице. Консоль обслуживает только объявленное и ни одного маршрута подсистемы кодом не добавляет:

```python
    def _declared(self, h, method: str, path: str, q: dict) -> bool:
        segs = path.strip("/").split("/")
        if segs and segs[0] in self.spec.table_specs and len(segs) <= 2:
            self._table_route(h, method, segs[0], segs[1] if len(segs) == 2 and segs[1] else None)
            return True
        if path.rstrip("/") == "/requests" and method == "POST" and self.spec.requests:
            self._request_route(h)
            return True
        if method == "DELETE" and len(segs) == 2 and segs[0] == "requests" and segs[1].startswith(LEDGER) \
                and "per_person" in self.spec.requests:
            h._send(*self._delete_ledger(segs[1], h.headers.get("X-User", "operator")))
            return True
        return False
```

`dispatch` спрашивает `_declared` в конце каждой ветки метода, перед 404. Объявлений, которые консоль обслуживает, три (третья ветка — ремонт учёта заявок, о нём ниже).

Имя объявленного семейства не может совпасть с маршрутом самой консоли. Первые сегменты путей, на которые `dispatch` и `Mount` отвечают сами, — закрытое множество `spec.CONSOLE_ROUTES` (`session`, `healthz`, `index.html`, `spec`, `where`, `resources`, `servers`, `domain`, `policy`, `unplaceable`, `events`, `metrics`, `marks`, `requests`, `mounts`, `drain`, `schema`). Спека, у которой `unit.rows` или объявленная таблица названы одним из них, не загружается: ни один запрос до такого семейства не дошёл бы — таблица `marks` никогда не писалась бы по HTTP, `POST /marks` — это отметка оператора. Таблица, только названная (`tables: [x]`), маршрута не имеет, и её это правило не касается. Что множество равно маршрутам диспетчера, держит тест: `test_spec_declarations.py::test_a_table_or_rows_named_like_a_route_of_the_console_is_refused_at_load_and_the_routes_are_the_dispatchs`.

**Таблицы** (`tables:`, `w2cplatform/tables.py`) — семейства строк `<sub>/<table>/<name>`, которые не единицы: на них ничего не размещается, у них нет эпохи и воркера. Спека говорит, чем строка названа (`key`: поле или шаблон `"{a}-{b:int}"`), какие у неё поля, общая схема строки (JSON Schema), что консоль штампует (`by`, `at`) и как назвать строки журнала. Консоль отдаёт `GET /<table>` и `GET /<table>/<name>` (секреты не показываются; при воротах — только строки тех единиц, которые человеку можно видеть), `POST /<table>` пишет строку целиком, `DELETE /<table>/<name>` её удаляет; каждая запись — строка журнала с именем. Объявление из `testsub2`:

```yaml
tables:
  shelves:
    key: name
    fields:
      name:    {type: string, required: true}
      zone:    {type: string}
      server:  {type: string}
      kind:    {type: string, default: plain, enum: [plain, reserve, closed]}
      …
    schema:
      if: {properties: {kind: {const: closed}}}
      then: {properties: {admits: {const: false}}, required: [admits]}
    stamp: [by, at]
    journal: {written: shelf.declared, deleted: shelf.withdrawn}
  notches:                            # not `marks`: `/marks` is the console's own route (spec.CONSOLE_ROUTES)
    key: "{of}-{from:int}-{to:int}"
    …
```

Тест: `test_spec_declarations.py::test_a_declared_table_is_written_listed_and_deleted_by_the_console_and_each_write_is_a_line`.

**Заявки** (`requests:`, семейство платформы) — `POST /requests {unit: <sub>/<id>, …}`, в `Mount` — `POST /<sub>/requests`: просьба к держателю единицы сделать ограниченную работу, поданная строкой `<sub>/requests/<id>`. Здесь консоль **подаёт**. Исполняет держатель, один раз, и отвечает в своём heartbeat'е (`fetched`) и в метке `<sub>/commands/<id>`; убирает строку уборка процесса консоли (`requests.clear_requests` из `host.requests_loop`). Её жнец пишет и метку — итог просьбы, которую никто не исполнил: `expired` только-если-нет, `unknown` в метку ушедшего держателя по прочитанному индексу; метку с итогом держателя он не трогает (ADR 0054). Весь путь строки — [урок 14](14-Resource.md), шаг «Семейство запросов». Подаёт заявку не только человек: воркер другой подсистемы, чья спека говорит `worker: {requests: [<sub>]}` (урок 9), пишет такую же строку сам.

Подача — то место, где повтор опасен. Строка единицы, созданная дважды, — заметная ошибка; заявка, поданная дважды, — два нажатия одного реле, и второе никто не увидит. Поэтому подача **идемпотентна**:

```python
    def _request_route(self, h) -> None:
        key = self._idem(h)
        if key is None:
            return
        try:
            resp = self._file_request(h, key)
        except Exception as e:                                       # noqa: BLE001
            return h._send(*self._failed(key, e))
        if resp[0] == 202:
            self._remember(key, resp)
        else:
            self.seen.release(key)                                  # a refusal is not a request: the key is not spent
        return h._send(*resp)
```

Три слоя, и каждый закрывает свой повтор.

- **Ключ обязателен** — тот же `_idem`, что у `POST /<rows>` (шаг 13): без `Idempotency-Key` — 400; ключ — одного человека и одного тела (повтор с другим телом — 422 `key reused`). Ответ 202 запоминается под ключом (`_remember`), и повтор после того, как строку уже исполнили и убрали, получает тот же 202, а не вторую работу: ключ живёт сутки, строка — секунды. Отказ ключа не тратит (`release`): исправленное тело под тем же ключом подаётся.
- **Имя строки — из спеки.** Шаблон `key` из полей тела (у регистратора М10B — `"{unit}-{from:int}-{to:int}"`: тот же диапазон — та же заявка, под каким ключом её ни пошли), иначе `id` тела, иначе сам ключ. Строка пишется create-only (`cas=0`); `Conflict` значит «эта заявка уже подана», и ответ — её строка.
- **Что консоль проверяет до записи** (`_file_request`): тело — объект и отвечает схеме (`schema`); `NaN` и бесконечности в значении — 400 «bad body», в JSON их нет; каждое значение пишется по правилу ниже, и `maxLength` схемы держит записанный текст, числа тоже (`port: -1e40` — сорок один знак, отказ); единица названа ссылкой своей подсистемы и существует (иначе 400 и 404); имя — имя, а не путь; срок `valid_until` — конечное число секунд, не дальше `most_valid` (не сказан — `now + valid_for`); неотвеченных заявок одного человека не больше `per_person` — их список одна строка `<sub>/requests/asks-<sha256 имени, 16 знаков>`, меняемая по CAS, так что сорок POST разом не насчитают одно и то же; id держится в нём, пока стоит строка заявки, и `settle` секунд после добавления, но не дольше `ttl` (при `ttl: 0` срока нет: id держится, пока стоит строка, или `settle`; `ttl` с `per_person` обязателен, своего числа у консоли нет); сверх — 429. Штампы (`stamp`: `by`, `at`, группа единицы, единица, о которой она) и строка журнала (`journal`) — тоже по спеке.

**Учёт, который не читается, останавливает своего человека — и говорит об этом.** Строка `asks-…`, которую хранилище держит и прочитать не может, читалась бы как пустой список и перезаписывалась по CAS: предел человека тихо обнулялся бы, и ничего не считалось. Поэтому такая строка — 429 этому человеку и никому больше, со словами «учёт не читается» (`_ledger_garbled`); тревога `request.ledger_garbled` в журнале — один раз на строку, а не на каждую заявку; на `/metrics` — `<sub>_requests_ledger_garbled` (шаг 11). Чинит администратор: `DELETE /requests/asks-<…>` (в `Mount` — `/<sub>/requests/asks-<…>`, право `admin`) удаляет строку, в журнале — `request.ledger_deleted`, и следующая заявка человека начинает учёт заново. Удалить так можно только список: строка заявки — дело её держателя и уборки (урок 14). Тест: `test_worker_life.py::test_a_persons_request_ledger_that_does_not_read_stops_that_person_and_says_so_once`.

Запуск на `testsub` (его спека: `requests: {schema: {required: [unit, add], …}, valid_for: 30, most_valid: 600}`):

```
POST /requests {"unit": "testsub/c1", "add": 5}      + Idempotency-Key: r1
  → 202 {"queued": {"id": "r1", "add": "5", "unit": "c1", "valid_until": "1791190227.77943"},
         "detail": "whoever holds the unit answers it on its next look at the requests, in its heartbeat;
                    after valid_until it expires unperformed"}
POST /requests {"unit": "testsub/c1", "add": 5}      + Idempotency-Key: r1   → 202, тот же ответ; строка одна
POST /requests {"unit": "testsub/c1", "add": 6}      + Idempotency-Key: r1   → 422 key reused
POST /requests {"unit": "testsub/c1", "add": 5}                              → 400 Idempotency-Key header is required
POST /requests {"unit": "c1", "add": 5}              + Idempotency-Key: r2   → 400 a unit is named <sub>/<id> …
POST /requests {"unit": "testsub/c1", "add": "x"}    + Idempotency-Key: r3   → 400 the request.add is integer, not string 'x'
POST /requests {"unit": "testsub/c1", "add": 1}      + Idempotency-Key: r3   → 202: отказ ключа не потратил
POST /requests {…, "valid_until": 1e12}              + Idempotency-Key: r4   → 400 a request's `valid_until` is at most 600 s away
```

В хранилище после этого две строки: `testsub/requests/r1` и `testsub/requests/r3`. Значения полей в строке — слова (`"add": "5"`), и правило у них одно на платформу (`field_text`, `w2cplatform/canonical.py`): строка — как есть, `true`/`false`, целое — ровно своими цифрами, остальное число — кратчайшей десятичной записью без экспоненты, `null` — поля нет вовсе, список и словарь — каноническим JSON (компактно, ключи по порядку, UTF-8 как есть). `valid_until` и `at` — по тому же правилу чисел: целая секунда пишется `1757500000`, а не `1757500000.0`. Одно правило нужно затем, чтобы одна заявка из двух писателей — курса и продукта, двери и повтора по `Idempotency-Key` — была одной строкой; таблица случаев — `Source/tests/testdata/requests_body.tsv`. Число из слова держатель читает сам. Что может решить только держатель — что диапазон длиннее, чем он выкачивает, что аргумент больше, чем есть у его единицы, — его, и отказ он говорит в heartbeat'е. Тесты: `test_spec_declarations.py::test_a_request_is_a_row_named_by_its_key_stamped_with_its_group_and_held_to_its_schema_and_deadline`, `test_review_remainder.py::test_a_command_retried_is_one_command`, `test_requests_body_table.py`.

**Дверь держателя** (`door: {routes: [...]}`, `w2cplatform/door.py`) — байты. **Байты консоль не проводит** (ADR 0002, ADR 0015): то, что держатель единицы отдаёт странице, идёт от держателя к браузеру, а консоль говорит только, где дверь, и впускает. Это и есть третий ответ `/where/<id>` из шага 6:

```python
    def door_of(self, h, uid) -> dict:
        routes = self.spec.door_routes
        if not routes:
            return {}
        pl = self.ctl.placement(uid)
        hb = holders(self.ctl.objects, f"{self.spec.name}/", self.wall(), self.lost_after, self.ctl.eyes).get(pl.worker) if pl else None
        holds = hb is not None and any(str(st.get("id")) == str(uid) for st in hb.status)
        url = str(hb.extra.get("url") or "").rstrip("/") if holds else ""
        if not url:
            return {"door": None}
        return {"door": self.door_at(h, uid, pl.worker, url)}

    def door_at(self, h, uid, holder: str, url: str, **said) -> dict:
        routes = self.spec.door_routes
        if self.door_signer is None:
            return {"url": url, "token": None, "expires": None, "routes": list(routes)}
        user, unit = h.headers.get("X-User", "operator"), self.spec.ref(uid)
        token, exp = self.door_signer.issue(user, unit, holder, routes, self.wall())
        self.journal.say("door.issued", sub=self.spec.name, target=str(uid), user=user, holder=holder,
                         routes=",".join(routes), until=round(exp), **said)
        return {"url": url, "token": token, "expires": exp, "routes": list(routes)}
```

Держатель — тот воркер, на котором единица **размещена**, живой (`holders`, шаг 10) и говорящий в heartbeat'е, что держит её: не любой heartbeat, где она ещё числится. Адрес двери держатель объявляет в своём heartbeat'е сам, словом `url`, и страница идёт на `<url>/<маршрут>/<id>`. Нет такого держателя — `door: null`, и страница спросит снова. `door_at` — общая половина: ею же `/where/<table>/<place>` открывает дверь держателя **места** для единицы из `?unit=` (шаг 6), и строка `door.issued` тогда называет и место (`place=`). Так страница читает то, что единица оставила на месте, которое держит теперь другой воркер, — у того, кто держит место, а не через консоль; место без держателя консоль называет `X-Unreachable: <place>@<server>`, и страница говорит, чего в её картине нет. Ворота спросили `view` на единице до этой строки — это право и несёт токен `door1.<kid>.<тело>.<подпись>`: кому выдан, какая единица, какой держатель, какие маршруты, до когда (`door.TTL`, 120 с). Подпись асимметричная (Ed25519): консоль **подписывает**, держатель только **проверяет** по открытому ключу (`Signer`, `Ring`), и ни один держатель не держит того, чем токен выпускают.

Ключи — в хранилище кластера. Первый ключ консоль делает сама, когда у неё впервые просят дверь (`Signer.current`): сначала открытая половина в `door/keys` — токен никогда не подписан ключом, которого не знает ни одна дверь, — потом закрытая, запечатанная, в `door/signer`. `python3 -m w2cplatform.door new` выпускает новый ключ: им подписывают все консоли в пределах `SIGNER_REREAD` (30 с), а старая открытая половина остаётся в `door/keys` для токенов, которые она подписала. Держатель, увидевший незнакомый `kid`, перечитывает `door/keys`, но не чаще раза в секунду. Нет кольца ключей, которым запечатать закрытую половину, — консоль ключа не держит и отдаёт дверь с `token: null`; держатель, у которого `door/keys` пуст, впускает всякого и один раз говорит об этом в логе. Отказ двери — всегда 401 `{error, reason}` с `WWW-Authenticate`, и `reason` — одно слово, по которому страница действует: `token` (токена нет), `signature`, `expired`, `holder`, `unit`, `route`. Единица переехала — у неё другой держатель, и старый токен не его (`holder`): страница спросит `/where` ещё раз и повторит один раз. Тесты: `test_spec_declarations.py::test_a_door_token_opens_one_holders_door_to_one_unit_for_its_routes_until_it_ends`, `…::test_where_hands_out_the_holders_door_with_a_token_and_only_the_placed_live_holder_has_one`.

Что платформа делает для двери — выпуск токена, ключи, проверка, CORS только для источников консолей (`DOOR_ORIGINS`), маскировка `?t=` в логах. Что маршрут **отдаёт** — решение воркера подсистемы: держатель зовёт `DoorKeeper.admit(handler, route, unit)` и отвечает, как отвечает. В М10B так регистратор отдаёт шкалу и куски записи (`door: {routes: [timeline, segment]}`; минуты записи на томе, который держит теперь другой регистратор, — у его двери, `GET /rec/where/volumes/<том>?unit=rec/<запись>`), а шлюз принимает предложение живого потока (`door: {routes: [whep]}`); строку потока создаёт первый зритель сам, `POST /live/streams` по праву `view` на камеру. Своих маршрутов для байтов у консоли нет ни одного.

Обратите внимание, чего в этом шаге нет: ни одной функции подсистемы, которую звала бы консоль. Подсистема говорит словами спеки, а консоль, страница и держатель делают по этим словам каждый своё.

## Шаг 12а — Ворота: кто пришёл и можно ли ему

До этого места всякий, кто дошёл до консоли, был администратором — под тем именем, которое сам поставил в `X-User` (ревью платформы, блокер 1; порядок согласован с продуктом, обратная связь BP). Диспетчер теперь начинается с ворот:

```python
        in_body = method in ("POST", "PUT") and (path.startswith(self.EDIT_ROUTES)
                                                 or path.strip("/").split("/")[0] in self.spec.unit_of)
        asked: set = set()
        if path not in OPEN_ROUTES:                     # the gate: open while this cluster has no key set, shut when it cannot check
            try:
                self.gate.caller(h.headers)              # who is calling: from the headers, before a byte of the body
                if in_body:
                    self.gate.admit(h.headers, "view")   # any grant here at all
                    asked.add(("view", None))
                else:
                    need = self.needs(method, path, self._named(h, method, path, q))
                    if not (need[1] is None and self._table_targets(method, path)):
                        self.gate.admit(h.headers, *need)
                        asked.add(need[:2])
                self.admit_rows(h, method, path, asked, body=False)
            except Denied as e:
                h.close_connection = True                # refused before the body: what follows the headers is not read
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        # A blob's bytes are the one body larger than `MAX_BODY`, and only where the spec has a blob to put them
        # (`blob_route`): `PUT /<rows>/<id>/<a blob field>`, by somebody admitted on that unit.
        if method == "PUT" and path.startswith(rows_path + "/") and len(path.split("/")) == 4:
            return self.blob_route(h, path)
        if not self.read_body(h, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
            return
        if in_body and path not in OPEN_ROUTES:
            try:
                parse_json(h.rfile.getvalue() or b"{}")  # `read_body` put it back as memory: read, and still there
            except PARSE_ERRORS as e:
                return h._send(400, {"detail": f"the body is not JSON that can be read ({type(e).__name__})",
                                     "error": "bad body", "fault": getattr(e, "fault", "") or "not_json"})
        if path not in OPEN_ROUTES:
            try:
                if in_body:
                    need = self.needs(method, path, self._named(h, method, path, q))
                    if need[:2] not in asked and not (need[1] is None and self._table_targets(method, path, self._sent(h))):
                        self.gate.admit(h.headers, *need)
                        asked.add(need[:2])
                    if self.spec.reach.get("requests"):
                        self._admit_each(h, need[0], self._sent_reach(h, path), asked)
                self.admit_rows(h, method, path, asked)
            except Denied as e:
                return h._send(e.status, {"detail": e.why, "error": "denied"})
```

**Кто — до тела, и тело — с потолком.** Первая версия ворот звала одно `admit`, а оно через `_named` читало тело, чтобы найти единицу, которую называет действие, — читало целиком, сколько бы ни заявлял `Content-Length`. `POST /marks` без токена с `Content-Length: 400 MiB` раздувал консоль на 806 МиБ и только потом получал 401 (пятое ревью, major, воспроизведено запуском); несколько таких запросов роняли консоль. Теперь вызывающий доказывается по одним заголовкам (`Gate.caller`): нет токена — 401, и тело не читается вовсе, а соединение закрывается. Потом `read_body` смотрит на `Content-Length` до первого байта: больше `MAX_BODY` (1 МиБ, `CONSOLE_MAX_BODY`; строки, отметки, команды — это JSON) — 413, для байтов блоб-поля потолок `MAX_BLOB` (32 МиБ, `CONSOLE_MAX_BLOB`: маска, а не фильм). Остаток не дочитывается — соединение закрывается. Длина, которая не число, — 400. Тело читается один раз, со своим сроком — `CONSOLE_TIMEOUT` плюс секунда на каждые `BODY_RATE` (64 КиБ), не успело — 408, — и кладётся обратно в память (`io.BytesIO`), так что `_named`, ключ идемпотентности и маршрут читают его, как будто до них никто не читал. Только после этого `admit` спрашивает, что вызывающему можно на названной единице. Тест: `test_console_load.py::test_a_body_is_not_read_before_the_caller_is_known_nor_past_its_ceiling` — 400 МиБ без токена получают 401 сразу, не отправив тела; с токеном — 413, тоже без единого прочитанного байта.

**Тело кусками — не пустое тело** (сверка продукта с одиннадцатым ревью). Ни одна дверь курса не читает `Transfer-Encoding: chunked`, а без `Content-Length` `read_body` считал, что тела нет: маршрут получал `{}` — `PUT` ничего не менял и отвечал 200, `POST` писал значения по умолчанию, а куски оставались в соединении и читались как следующий запрос. Теперь `read_body` отвечает на любой `Transfer-Encoding` 400 словами («a body sent whole, with a Content-Length») и закрывает соединение. Это одно место: через `read_body` идут консоль каждой подсистемы, консоль домена, служба подписи и шлюз живого. Тест: `test_one_bad_element.py::test_a_body_sent_in_chunks_is_refused_in_words_and_not_read_as_an_empty_one`.

**Сначала то, что решает путь, — и только потом тело.** «Кто» проверялось до тела, а «можно ли ему» — после: токен без единого гранта слал `PUT /<rows>/<id>/<поле-блоб>` с 32 МиБ, восемь штук сразу, и консоль держала 331 МиБ, прежде чем ответить 403; в М11 четыре таких запроса — её предел памяти (шестое ревью, major, воспроизведено запуском). Теперь всё, что решается по одному пути, спрашивается **до** тела: право маршрута, единица в пути, единица строки таблицы, какой строка **есть** (`admit_rows(…, body=False)`). Маршрут, у которого единица в теле (`EDIT_ROUTES` — отметка и заявка, — и строка таблицы, чью единицу называет поле, `rights.unit_of`), сначала спрашивается о любом гранте вообще — и у чужого тело не читается; после тела — о названной единице, о строке, какой она **станет**, и о том, до чего дотягивается само изменение (ниже). Множество `asked` помнит, о чём уже спросили: ни один вопрос не задаётся — и не пишется в журнал — дважды. Потолок `MAX_BLOB` остался только у маршрута блоба (`blob_route`): `PUT /<rows>/<id>/<поле>` при поле, которого в спеке нет или которое не блоб, — 404 без тела, у несуществующей единицы — тоже; строка остаётся JSON под `MAX_BODY`. И блобов читается не больше `BLOBS_AT_ONCE` (2) сразу — каждый это `MAX_BLOB` памяти, пока его читают и кладут, — следующему 503 с `Retry-After`. Телу `/session`, которое может прислать кто угодно, — свой потолок `SESSION_BODY` (16 КиБ): токен или имя с паролем, а не мегабайт. Тест: `test_console_load.py::test_what_the_path_decides_is_asked_before_the_body_and_a_blobs_ceiling_is_a_blob_routes`.

**Платформа не знает, как доказывают человека.** Это дело домена (М12, урок 4): пользователи живут у держателя домена, короткий токен называет субъект и больше ничего, а что субъекту можно — таблица в хранилище **этого** кластера, которую приносит агент домена. Платформа (`w2cplatform/access.py`) знает три вещи.

**Когда спрашивать** — когда в хранилище кластера лежит набор ключей (`domain/keys`). У кластера, который никто не ввёл в домен, набора нет, и его консоль открыта, как была, — и говорит об этом в логе, один раз. М10A и М10B читаются и запускаются без М12; одну коробку не заставляют носить подписывающего.

**Что спрашивать** — интерфейс из двух вопросов (и третьего, необязательного):

```python
class Access(Protocol):
    def who(self, token: str) -> dict: ...                       # the token's payload (`sub`, …), or `Denied(401)`
    def may(self, payload: dict, capability: str, unit: str | None, labels: list) -> bool: ...
    def by_labels(self, payload: dict, capability: str) -> bool: ...
```

Отвечает тот, кто умеет проверить токен. Его называет `ACCESS_IMPL` (по умолчанию `domain.access:cluster_access`), и загружается он только тогда, когда есть ключи, по которым проверять. Криптографии в платформе нет. `unit` — ссылка `<sub>/<id>`, `"*"` (любая единица: только грант на весь кластер) или `None` (никакая в отдельности). Что грант на единицу покрывает и единицы, которые **о ней**, спрашивает не реализация, а сама платформа (`may_on`): у единицы с `about` её спека так и говорит.

```python
def may_on(access, payload: dict, capability: str, unit: str | None, labels, of: str | None = None) -> bool:
    labels = list(labels or [])
    if access.may(payload, capability, unit, labels):
        return True
    return bool(of) and of != unit and access.may(payload, capability, of, labels)
```

**Что нужно маршруту:**

| Право | Что открывает |
|---|---|
| `view` | любой `GET`; и запись в семейство, которое спека назвала в `rights.routes.view` (в М10B так создаётся строка живого потока: смотреть — не менять) |
| `edit` | действие через систему, которое не меняет того, чем она является: отметка, заявка, строка таблицы из `rights.routes.edit` |
| `admin` | всё остальное, что пишет: единицы, строки остальных таблиц, политика, дренаж, списание сервера (`POST /servers/<s>/decommission`, урок 7) |

`edit` включает `view`, `admin` — оба. Право выдаётся на единицу, на единицы с заданными метками или на весь кластер. Единицу маршрут называет в пути (`/<rows>/<id>`, `/where/<id>`) или, если это действие, — в теле, ссылкой `unit: <sub>/<id>`: отметка и заявка относятся к одной единице, и оператор, которому дали её, должен мочь их делать. Тело читается один раз, после того как вызывающий доказан (`read_body`, выше), и лежит в памяти — обработчик читает его, как будто до него никто не читал. Маршруту, который единицы не называет, чтобы **смотреть**, хватает любого права субъекта, а чтобы **действовать**, нужно право на весь кластер. Единица, о которой спека говорит `about`, спрашивается вместе с той, о которой она: грант на любую из двух годится, а метки для гранта по меткам — той, о которой (свои метки единицы говорят, где ей работать, а не чья она; `target`).

**Единица — и в запросе.** Маршрут, который называл единицу в строке запроса, а не в пути, проходил ворота за «любое право»: оно годится для списка, а это не список, и данные одной единицы уходили охраннику другой (второе ревью, блокер 1). Теперь `_named` читает `?unit=` у любого GET так же, как тело у действия. Имя, которое не ссылка, — голый id — 400 **до** проверки прав: чей `7` спрашивать у ворот?

**Единицу читают один раз — и ворота, и маршрут.** Ворота брали единицу из третьего сегмента пути (`segs[2]`), а маршруты — из последнего: `DELETE /<rows>/1/2` с правом `admin` на единицу 1 удалял единицу 2. Ревью проверило это запуском (третье ревью, блокер 1). Теперь путь разбирает одна функция, `path_id`, и её ответ берут и `needs`, и маршрут (`_uid`, `/where`, строки таблиц); всё, что стоит в пути **после** id, — 404 до ворот, кроме `PUT /<rows>/<id>/<поле-блоб>`. Тест: `test_console_gate.py::test_the_gate_and_the_route_read_the_unit_from_the_same_segment`.

**Чья строка — и до чего дотягивается изменение: это говорит спека.** Ворота проверяют единицу, которую называет путь. Но запись может дотянуться до других единиц через поля строки, которую пишет, — и каждое ревью находило новое такое поле (четвёртое, пятое, шестое; major, воспроизведены запуском): строку переводили на чужую единицу правкой одного поля; правка адреса уводила единицу на чужой канал, чьи учётные данные общие; правило, названное по гранту на его метки, действовало на единицы, на которые у правившего прав нет. Платформа не знает, что значат эти поля. Кода, вставленного в консоль, у подсистемы нет; она говорит это словами спеки, и консоль спрашивает ворота по словам:

| Объявление | Что значит для ворот |
|---|---|
| `about: {sub, field}`, поле `fixed: true` | строка — о единице другой подсистемы, и это не меняется: правка поля после создания — 400 для всех, а спрашивается грант на ту единицу |
| `rights.unit_of: {<table>: <field>}` | строка таблицы — единицы, которую называет её поле: писать её — право маршрута на эту единицу, и на старую, и на новую, если запись строку переводит (`_table_targets`) |
| `rights.reach.group: [<field>]` | правка этих полей задевает каждую другую единицу группы (`placement.group_by`), которую единица покидает, и той, куда приходит; группа, где ещё никого нет, — грант на весь кластер (`"*"`) |
| `rights.reach.cluster: [<field>]` | правка этих полей — дело всего кластера |
| `rights.reach.requests: [<action>]` | заявка с таким действием задевает каждую единицу группы своей единицы |
| `rights.cluster_rows: true` | запись в единицу этой подсистемы — дело всего кластера, что бы ни говорили её поля и метки |
| `rights.names: [{field, unit, sub \| of}]` | единицы, которые строка называет внутри json-поля: за них отвечает переезд названной единицы в другую группу (`named_with`); строка, которую не прочесть, называет любого — `"*"` |

Всё это `admit_rows` спрашивает дважды: до тела — о строке, какая она **есть**, после — о строке, какой она **станет**, и о том, до чего дотянется изменение (`reach_of_change`, `reach_of_request`). Старое значение — чтобы строку нельзя было увести у единицы, которой человек не может касаться; новое — чтобы её нельзя было на такую единицу направить. Правка, которая не трогает объявленных полей, не спрашивает ничего сверх прежнего. Тест на нейтральных подсистемах: `test_spec_declarations.py::test_what_a_change_or_a_request_reaches_is_the_specs_group_the_cluster_or_the_units_a_row_names`.

Пример — объявления VMS из М10B. Регистратор: `rights: {unit_of: {keeps: cam}, routes: {edit: [keeps]}}` — отметка «сохранить» принадлежит камере, и ставит её оператор. Камера: `rights: {reach: {group: [source, labels], cluster: [ref], requests: [output, preset]}}` — смена адреса задевает все камеры обоих устройств, имя, под которым камеру знает домен, — кластера, реле и пресет — каждой камеры устройства. Сценарии: `cluster_rows: true` и `names` по полям `when` и `then`. Тесты М10B: `test_console_gate.py::test_a_row_cannot_be_moved_to_another_camera_by_an_edit`, `…::test_a_cameras_source_is_moved_only_by_whoever_administers_every_camera_of_the_device_and_is_nobody_elses`, `…::test_a_scenario_is_the_whole_clusters_to_write_whatever_its_labels_say`.

И это только половина правила — **кто может**. Что **может быть**, решает контроллер для любого писателя строк (урок 10): спека объявляет, на что поле может указывать и что должно совпасть (`ref`, `must_match`, `unique`), и запись, которая этому не отвечает, отказывается, кто бы её ни прислал. А чтобы следующее поле не осталось без ответа, в М10B есть тест, который перечисляет **каждое поле каждой спеки** VMS и говорит, на что оно указывает — или что ни на что: `test_console_gate.py::test_every_field_of_every_spec_that_points_at_something_else_is_asked_about`; новое поле его не пройдёт, пока кто-то не скажет, какое оно.

И ещё одно о том же классе, найденное на соседней двери (шестое ревью). Две сборки консоли — две возможности забыть: сборка консоли кластера (М11) своей функцией не подключила того, что подключала сборка коробки, и в кластере, который спрашивает, кто звонит, зритель одной камеры получал данные другой за любой грант. Поэтому сборка одна: консоль кластера — `python3 -m w2cplatform.cluster console`, то есть тот же `host.console` с окружением кластера, и `host.spec_console` собирает те же `SpecConsole` и `Mount` (шаг 14); всё, что ворота знают о единицах, приходит из спек, и второй сборке нечего забыть. Тест: М11, `test_lesson5_controller.py::test_the_clusters_console_asks_about_the_camera_a_route_names_exactly_as_the_boxes_does`.

**Ворота закрываются, когда не могут проверить.** Набор ключей есть, а проверить токен нечем — реализация не установлена, хранилище не отвечает: каждый запрос получает 503, а не открытую консоль. «Не могу проверить» — не «проверять нечего»; это то же правило, что у аренд и меток удержания, в третий раз. И в четвёртый: набор ключей, который ворота уже видели, **пропал** — удалили или откатили хранилище из копии, сделанной до вступления в домен. Это не «кластер не в домене», это «кто-то убрал проверку», и ворота закрыты (503), пока агент не принесёт набор снова (второе ревью). Открытой консоль бывает только у кластера, который набора не видел никогда. «Видел» сначала жило в памяти ворот, и перезапущенная консоль после такого отката снова была открыта (третье ревью). Теперь членство в домене читается из самого хранилища: если есть хоть одна строка, которую пишет только агент домена (`domain/member` — её агент пишет на каждой синхронизации, так что она есть у каждого члена, — и `domain/root`, `domain/grants`, `domain/revoked`, `domain/break_glass`; всё вместе — `DOMAIN_MARKS`), а набора ключей нет, — 503 и после перезапуска. А удалить `domain/*` не может никто, кроме писателя-агента (`refuse_delete`, М10A, урок 2). Что остаётся: откат **всего** хранилища на время до вступления уносит и метки, и консоль открыта, пока агент не принесёт их снова. Тест: `test_a_cluster_that_is_in_a_domain_stays_shut_without_its_keys_after_a_restart_too`.

**`X-User` снаружи выбрасывается.** При включённых воротах заголовок заменяется именем, которое доказал токен:

```python
        del headers["X-User"]                            # whatever the caller called themselves
        headers["X-User"] = name                         # …is replaced by what the token proved
```

Ни одну строку, читающую `X-User`, менять не пришлось, а журнал (`unit.deleted`, `door.issued`, строки таблиц и заявки) начал называть того, кого проверили. Отказ по праву — тоже строка журнала (`access.denied`); **действие** под аварийной учёткой — тревога (`access.break_glass`) с именем человека. Чтение под ней тревогой не пишется: сессия открывалась тревогой, а страница опрашивает `/events` раз в три секунды — тысяча строк за четверть часа похоронила бы ту, что важна (второе ревью). И у самой аварийной двери есть предел: пять отказов с одного адреса или двадцать со всех за пятнадцать минут — 429 до конца окна, верному паролю тоже, и одна тревога `access.break_glass.limited` на срабатывание, а не по тревоге на догадку. Единственная учётка с правами на всё — единственный пароль, который стоит перебирать (М12, урок 4, шаг 7). Предел сначала обходили двое: тридцать одновременных попыток все проходили проверку до того, как первая успевала посчитаться, а адресом считался адрес прокси перед консолью (третье ревью). Теперь попытка **резервируется под блокировкой** до проверки пароля — верный пароль возвращает резерв, неверный оставляет, — а адрес берётся из `X-Forwarded-For`, только если запрос пришёл от прокси, названного в `TRUSTED_PROXY`. Пока окно адреса полно, 429 получает и верный пароль с этого адреса: предел, который пропускает верную догадку, не останавливает перебор. А общий предел — **темп, а не запрет** (четвёртое ревью: двадцать неверных паролей с разных адресов закрывали аварийную дверь всем, а один пароль раз в 45 секунд с четырёх адресов держал её закрытой всегда — у продукта так и было). Теперь процесс проверяет не больше десяти паролей в минуту с запасом в десять; проверка сверх темпа ждёт своей очереди до десяти секунд, и только более долгое ожидание — 429 с `Retry-After` и одной тревогой. Ручеёк темп не заполняет никогда, а при потоке с десятков адресов верный пароль борется за каждую очередь наравне — и получает её. Тест: `test_the_emergency_doors_limit_across_addresses_is_a_pace_and_a_trickle_cannot_hold_it_shut`. Тест: `test_an_emergency_attempt_is_reserved_before_its_password_and_counted_by_the_callers_own_address`. Но «наравне» держало ручеёк, а не поток: отказ по темпу не тратит попыток адреса, и сорок адресов, каждый в пределах своих пяти, занимали все очереди постоянно — в симуляции ревьюера оператор не вошёл за час (пятое ревью, остаток Ч-M3). Теперь у коробки своя полоса темпа: вызывающий **с коробки** стоит в своей очереди, которую сеть не занимает; перебор из сети остаётся ровно таким же медленным. Кто «с коробки» — тот, кто пришёл через unix-сокет консоли (`CONSOLE_UNIX`, `access.is_local`: пир с именем `unix…`). До шестого ревью это был TCP-пир 127.0.0.1, не названный в `TRUSTED_PROXY`, — и за прокси на той же машине таким пиром был каждый вызывающий (прокси не назван) или никто (назван), а полосу мог занять любой процесс коробки (шестое ревью, minor). Сокет — файл: кто может его открыть, решают права каталога (0700) и самого файла (0660), прокси через него не ходит, а чей это процесс, говорит ядро (`SO_PEERCRED`). Подробно — М12, урок 4, шаг 7, и шаг 14 ниже. Тест: `test_console_gate.py::test_forty_addresses_flooding_the_emergency_door_do_not_keep_the_operator_on_the_box_out`.

Открытыми остаются сама страница (`/`, `/index.html`) и модуль консоли, из которого она строится (`MODULE_ROUTES`: окно входа рисует он), `/metrics` и `/healthz`, которые читает мониторинг, и дверь входа — `/session` и `/session/break-glass` (`access.OPEN_ROUTES`).

**Список показывает то, что можно этому человеку.** Маршрут-список единицы не называет, и ворота пускают к нему любого, у кого есть хоть какое-то право. Дальше решает сам список: строки единиц фильтруются по правам вызывающего (`_visible`), события — так же. Событие, которое единицы не называет, — журнал `audit` — видит тот, у кого право на весь кластер: «кто удалил единицу» не показывают оператору одной единицы. Событие единицы видит тот, у кого грант на неё или на единицу, о которой она (`of`), — с метками той, о которой.

**Битая строка одной единицы — это события одной единицы, а не вся лента.** Чтобы спросить грант по меткам, ворота `/events` читают метки единицы из её строки. Читали они её напрямую (`ctl.unit`): строка, которая не разбирается, давала `ValueError` и 400 на весь таймлайн каждому, кого проверяют ворота. Строка без `id` давала `KeyError`, и тогда ответа не было вовсе (проход масштаба после восьмого ревью). Теперь строка читается через общий читатель (`rows.Table`, таблица `unit` — `UNIT_LABELS`): считается один раз, один раз попадает в лог и видна на `/metrics` как `<sub>_console_rows_garbled{table="unit"}`. Её единица судится без меток. Грант на саму единицу и грант на весь кластер события видят, как видели. Грант по меткам не видит: что в строке, не известно, а «не известно» у ворот — не «можно». То, что вызывающий не получил по этой причине, ответ называет по единицам: `withheld: [{unit, events, why}]`. Так же — если хранилище не ответило за строку. Единица подсистемы, которую этот процесс не обслуживает, строки здесь не имеет: судится без меток, и ничего не придержано. Тест (М10B): `test_console_gate.py::test_one_garbled_camera_row_costs_that_cameras_events_and_not_the_timeline` — строка со словом в `revision` и строка без `id`: охранник по меткам получает 200 и события третьей единицы, две другие названы в `withheld`; зритель второй по её гранту видит её события, администратор — все; на `/metrics` — 2.

**`withheld` говорится только тому, у кого есть грант по меткам.** Придержано то, что такой грант мог бы покрыть. Грант на одну единицу другую не покрывает никогда, а `withheld` называл ему id чужой единицы и число её событий: охранник второй единицы узнавал о третьей (десятое ревью, minor). Теперь консоль сначала спрашивает доступ, есть ли у вызывающего грант по меткам (`Access.by_labels`, `SpecConsole._by_labels`). В М12 это `ClusterAccess.by_labels`; доступ, который ответить не умеет, считается «нет». Тот же тест: у зрителя второй единицы `withheld` в ответе нет.

Тот же обход нашёл соседний отказ на этом же маршруте, на стороне слияния: строку события из ответа ресурса проверяли на то, что значения переводятся, а оставляли как пришла. `"t": "1700000000"` проходил проверку и ронял сортировку слияния — строка рядом с числами. Ответа тогда не было ни одному таймлайну. Теперь `eventdatabase._event_line` отдаёт строку в тех типах, в которых её проверил (урок 8, таблица строк; тест `test_row_reader.py::test_a_line_whose_values_only_convert_is_merged_as_converted_and_stops_no_timeline`).

**Дверь входа: `/session`.** Ворота просят токен; этот маршрут — то, как его начинает носить **браузер**.

| Метод | Что делает |
|---|---|
| `GET` | `{open, login_url, user?, until?, via?}`: закрыта ли консоль, кто я здесь и где входят (`LOGIN_URL` — подписант домена, дверь `<LOGIN_URL>/api/login`) |
| `POST {token}` | проверяет токен ровно так, как проверили бы ворота, и ставит cookie `w2c_token` на срок жизни токена: `{user, until}` |
| `DELETE` | cookie уходит, и аварийная сессия с ней: `{out: true}` |
| `POST /session/break-glass {who, why, password}` | аварийный вход (`Gate.open_glass`): сессия в памяти этого процесса под своей cookie: `{user, until}` |

У открытой консоли входить некуда и ломиться не во что: `POST` на обе двери — 400, `GET` — `{open: true, login_url}`.

```python
# access.py
def session_cookie(token: str, seconds: float, secure: bool = False) -> str:
    return (f"{COOKIE}={token}; Path=/; Max-Age={max(0, int(seconds))}; HttpOnly; SameSite=Strict"
            + ("; Secure" if secure else ""))
```

Три свойства, и каждое закрывает свой случай. **Пароль сюда не приходит:** страница несёт его к двери входа домена и возвращается только с токеном — консоль токенов не выпускает и паролей не хранит (М12, урок 4), и N консолей, не видевших пароля, — N мест, откуда его не унести. **`HttpOnly`:** скрипт страницы cookie обратно не прочтёт, и скрипт, внедрённый в страницу, токен не унесёт. **`SameSite=Strict` и второй замок:** браузер шлёт cookie с каждым запросом к консоли, в том числе с тем, который его заставила послать страница чужого сайта. Поэтому запрос, который **действует**, несёт доказательство в cookie и называет чужой `Origin`, получает 403. Вызывающий с токеном в заголовке — не браузер, которым управляют, и его не спрашивают.

Модуль консоли на странице (урок 16) начинает с `GET /session`: открыта консоль — работает без входа; закрыта и человека не знают — показывает окно входа. Имя и пароль уходят на `login_url`, вернувшийся токен — в `POST /session`. Если `LOGIN_URL` не задан, окно так и говорит: держатель домена кластеру не известен, войти можно только аварийно.

**Тело двери входа — то, что прислал кто угодно.** Тело-список, токен-список или число, не JSON вовсе — обработчик падал на разборе или на `token.split`, и вместо ответа соединение обрывалось (девятое ревью, minor, воспроизведено запуском). Теперь `session` разбирает тело под `PARSE_ERRORS` и принимает на `/session` только объект со строкой `token`, а на `/session/break-glass` — объект из трёх строк `who`, `why`, `password`; всё остальное — 400, и воротам ничего не задаётся. Тело, которое не читается как JSON, несёт в этом 400 и слово `fault` (`not_json`, `not_number` — шаг 13). Токен, который строка, но не наш, — заголовок-список, `kid`-список, `exp` словом, `NaN` или 10**400 — проверяет `tokens.verify` домена, и это 401 (М12, урок 4).

**Аварийная сессия — только у консоли.** Продукт нашёл у себя: `POST /session/break-glass` отвечали все двери, которые подключают общие ворота, — регистратор и шлюз живого видео (сверка с девятым ревью). Здесь `/session` маршрутизирует только `SpecConsole.dispatch`, и обход дверей это подтвердил: дверь воспроизведения держателя, шлюз, дверь архива регистратора и ресурс на `POST /session` и `/session/break-glass` отвечают 404 или 501 и сессии не открывают. Но ворота любой двери читали cookie аварийной сессии, а сессии лежат в памяти процесса (`Gate._glass`, общий для класса): дверь, запущенная в процессе консоли, приняла бы сессию, открытую там. Теперь у ворот есть `glass`: шлюз и дверь держателя строят их с `Gate(..., glass=False)` — такие ворота аварийную сессию не открывают (`open_glass` — 404) и не принимают, только токен. Тест: `test_console_gate.py::test_the_door_in_is_the_consoles_alone_and_takes_a_token_or_an_emergency_entry_and_nothing_else` — обход четырёх дверей; сессия, открытая у консоли, в том же процессе пускает к консоли и не пускает к шлюзу (401, до правки шлюз пускал); пять мусорных тел — 400.

**Чего ворота не закрывают.** Двери между процессами — ресурс и то, что процессы кластера спрашивают друг у друга, — никого не спрашивают. Это взаимный TLS между процессами, отложенный до своего шага (ADR 0034), и до него кластер из нескольких машин стоит за своей сетью. Двери держателей, которые открываются **странице**, проверяют токен двери, выданный консолью (шаг 12).

## Шаг 13 — Ключ идемпотентности в диспетчере

```python
    def _idem(self, h, required: bool = True):
        key = h.headers.get("Idempotency-Key")
        if not key:
            if required:
                h._send(400, {"detail": "Idempotency-Key header is required", "error": "Idempotency-Key required"})
            return None
        raw = h.rfile.read(int(h.headers.get("Content-Length", 0) or 0))
        h.rfile = io.BytesIO(raw)
        try:
            prior = self.seen.claim(key, h.headers.get("X-User", "operator"), raw)
        except Refused as e:
            h._send(400, {"detail": str(e), "error": str(e)}); return None
        except OSError as e:                                             # the store, not the request: a client told 400 does not retry
            h._send(503, {"detail": f"the store did not answer: {no_paths(e)}", "error": "store unavailable"}); return None
        if prior is not None:
            h._send(*prior); return None
        return key
```

Ключ **обязателен** для POST. Не «поддерживается» — обязателен: клиент без ключа получает 400 и не создаёт ничего. Это невежливо к тем, кто пробует систему из `curl`, и это осознанно: создание без ключа при повторе даёт вторую единицу, а вторая единица с тем же содержимым — худшая ошибка, чем неудобный `curl`.

Заявка получает имя вызывающего и тело (шаг 4); тело читается здесь и кладётся обратно, как в воротах. Возврат `None` во всех случаях, кроме «ключ наш», и во всех ответ уже отправлен (или ключа нет, а он и не требовался). Идиома неприятная, но её альтернатива — исключение на управляющий поток; здесь вызывающий — несколько строк ниже, и разглядеть их можно целиком.

```python
        if method == "POST":
            if path not in (rows_path, "/marks"):
                if self._declared(h, "POST", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            key = self._idem(h)
            if key is None:
                return
            try:
                if path == "/marks":
                    resp = con.mark(object_body(h), h.headers.get("X-User", "operator"))
                else:
                    resp = con.create(object_body(h), key, h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp); return h._send(*resp)
```

Порядок: сначала маршрут, потом ключ. Запрос на несуществующий путь получает 404, не 400 про заголовок — иначе опечатка в URL выглядела бы как проблема с идемпотентностью. Путь, который не строки и не отметки, может быть объявленным (шаг 12) — строка таблицы или заявка; заявка зовёт тот же `_idem` и так же обязательно, но имя её строки говорит спека.

`object_body` — тело, которое не JSON-объект (список, вложенное глубже, чем читает JSON), — 400, ничего не записано. Тело читает `canonical.parse_json`, как каждая дверь платформы: не UTF-8, одинокий суррогат (`\ud800` в JSON-экране), `NaN` — не JSON, число, которого не держит float64 (`1e400`), — не число. Тогда 400 несёт рядом со словами двери слово закрытого словаря, `fault: not_json` или `not_number` (`console.fault_of`, словарь — урок 9); тело, которое прочлось, но не объект, — 400 без `fault`: это не тот вид, а не нечитаемый текст. У маршрутов, где единица в теле (`EDIT_ROUTES` и строки таблиц с `unit_of`, шаг 12а), нечитаемое тело отказывается ещё до ворот (`dispatch`, `error: "bad body"`): такое тело не называет единицу, и спрашивать у вызывающего грант на весь кластер незачем. Ключ идемпотентности при любом из этих отказов не тратится. Запись, которая бросила, — `_failed`: заявка ключа снимается (записано ничего, за что ключ мог бы отвечать), хранилище — 503, клиент повторит, остальное — 500. Тест: `test_body_fault_doors.py::test_the_consoles_doors_refuse_a_body_that_is_no_json_with_its_fault`.

`_remember` **до** отправки. Если процесс умрёт между ними, клиент не получит ответа, повторит — и получит сохранённый. Обратный порядок в той же аварии создал бы вторую единицу. А если ответ не лёг под ключ, `_remember` пишет об этом в лог и отправка идёт всё равно: запись сделана, и 503 отправил бы клиента делать вторую.

`X-User` со значением по умолчанию `operator` — имя, под которым консоль пишет журнал и заявку. При открытой консоли это то, что назвал вызывающий; при воротах — имя, которое доказал токен и которым ворота заменили заголовок (шаг 12а).

```python
        if method == "PUT":
            if path == "/policy":                                        # the administrator's knobs: one row, no idempotency needed (a PUT is)
                try:
                    body = object_body(h)
                    out = ctl.set_policy(body)
                except (Refused, Forbidden) as e:
                    return h._send(400 if isinstance(e, Refused) else 403, {"detail": str(e), "error": str(e)})
                con.journal.say("policy.changed", sub=spec.name, user=h.headers.get("X-User", "operator"),
                                policy=json.dumps(body, sort_keys=True))
                return h._send(200, out)
```

Комментарий договаривает мысль за код: **PUT идемпотентен сам по себе.** Поставить `servers: distinct` дважды — это то же состояние. Ключ нужен там, где повтор создаёт, а не там, где он перезаписывает. Ручка, которая двигает каждую единицу подсистемы, — строка журнала с именем и новыми значениями: значения политики — выбор, а не секрет.

Две ошибки, два кода: `Refused` — 400 (администратор выбрал значение не из `POLICY_CHOICES`), `Forbidden` — 403 (токен не имеет права на `<sub>/policy`, урок 9). Первое — «вы не так написали», второе — «вам нельзя». Свалить их в один код означало бы скрыть от администратора, что дело в правах.

Парный ему GET отдаёт и значения, и варианты:

```python
            if path == "/policy":
                return h._send(200, {**ctl.policy(), "choices": ctl.POLICY_CHOICES})
```

Страница строит из `choices` выпадающий список, ничего не зная о политиках. Тот же приём, что и с `/spec` в шаге 3: **вариант выбора — это данные**, а не разметка.

```python
            key = self._idem(h, required=False)                         # optional here: a PUT is its own retry
            if key is None and h.headers.get("Idempotency-Key"):
                return                                                   # a prior reply, a refused key or 503: already sent
            try:
                resp = con.update(self._uid(path), object_body(h), h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp)
            return h._send(*resp)
```

Для `PUT /<rows>/<id>` ключ **необязателен**: PUT и так идемпотентен. Но если клиент его прислал — та же заявка и то же сохранение. Зачем? Ради ответа: повтор без ключа пройдёт по контроллеру заново и вернёт новую `revision`, а клиент, который сравнивает ответы, решит, что кто-то ещё правил строку. С ключом он получит тот же ответ, что и в первый раз.

```python
        if method == "DELETE":
            if not path.startswith(rows_path + "/"):
                if self._declared(h, "DELETE", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            try:
                return h._send(*con.delete(self._uid(path), h.headers.get("X-User", "operator")))
            except Exception as e:                                       # noqa: BLE001 — said in the journal already
                return h._send(*self._failed(None, e))
        h._send(405, {"detail": "method", "error": "method"})
```

У `DELETE` ключа нет вовсе — решение из шага 8, теперь видное в коде. И последняя строка: `405` для всего, что не GET/POST/PUT/DELETE.

## Шаг 14 — `Mount`

```python
class Mount:
    """One console process, several subsystems. The root console answers at `/`
    (the page, `/<rows>`, its tables); every other subsystem is a path: `/<sub>/spec`,
    `/<sub>/<rows>`, `/<sub>/where/<id>` — the same SpecConsole class, its routes
    under its name, its own token-scoped controller. A person opens one page;
    the machines (a host's spares script, М12's read model) find every subsystem
    on one port; a new subsystem is a YAML, a worker, and a path."""

    def __init__(self, root: SpecConsole, mounts: dict[str, SpecConsole] | None = None):
        self.root, self.mounts = root, dict(mounts or {})
        self.epoch_policy: dict[str, str] = {}
        self.units: dict[str, SpecConsole] = {}
        for c in (self.root, *self.mounts.values()):
            self._adopt(c)

    def _adopt(self, console: SpecConsole) -> None:
        self.epoch_policy[console.spec.name] = console.spec.older_epochs
        console.epoch_policy = self.epoch_policy
        self.units[console.spec.name] = console
        console.units = self.units
        console.says_platform = console is self.root         # the platform's lines once per process: the root's page
        console.serves_page = console is self.root           # one page per process, the root's: `/<sub>/` is none

    def mount(self, name: str, console: SpecConsole) -> "Mount":
        self.mounts[name] = console
        self._adopt(console)
        return self
```

Корневая консоль и словарь остальных. `_adopt` делает общими для всех консолей процесса два словаря, **по ссылке**: что значит старая эпоха в каждой подсистеме (`/events` сливает все подсистемы, и отвечающая консоль должна знать это и о чужих), и каталог `units` (ссылка `<sub>/<id>` называет единицу любой подсистемы процесса, и ворота любой консоли читают её строку, её `about` и её метки). `mount` возвращает `self`, чтобы сборка читалась одной цепочкой. Настоящая сборка — `host.build_console`, из каталога спек:

```python
def build_console(env: dict):
    """The console's `Mount` and its controllers, from `SPEC_DIR` and `CONSOLE_ROOT` — not served yet."""
    …
    specs = {s.name: s for s in catalog.load_dir(env[catalog.SPEC_DIR])}   # the deployment's directory: what this console fronts
    root_name = env.get("CONSOLE_ROOT", "")
    …
    from .door import KEYS_KEY, SIGNER_KEY
    vars_, objects = stores(env, "console", [a for s in specs.values() for a in s.acl_console()] + [SIGNER_KEY, KEYS_KEY])
    ctls = {n: SpecController(s, vars_, objects) for n, s in specs.items()}
    m = spec_console(ctls, root_name, runtime.events_root(env))
    …
```

а сам `Mount` — `host.spec_console`, общая для обеих сборок, коробки и кластера (шаг 12а):

```python
def spec_console(ctls: dict, root_name: str, marks_root: str | None = None, index=None, wall=None, worst_failover: float = 0.0):
    …
    root_ctl = ctls[root_name]
    index = index or MergedIndex(root_ctl.objects, wall=wall or root_ctl.wall)
    m = Mount(SpecConsole(root_ctl, marks_root=marks_root, index=index, wall=wall, worst_failover=worst_failover))
    for n, c in ctls.items():
        if n != root_name:
            m.mount(n, SpecConsole(c, index=index, wall=wall))
            m.mounts[n].journal = m.root.journal                  # one journal for the process
    return m
```

Один токен хранилища — консольные гранты всех спек и две строки ключа двери (`door/signer`, `door/keys`, шаг 12), один журнал, один индекс. `CONSOLE_ROOT`, который не называет ни одной спеки каталога, — отказ словами: что стоит в корне, говорит развёртывание, а не платформа. Запуск — `python3 -m w2cplatform console` с `SPEC_DIR` и `CONSOLE_ROOT`; рядом с сервером `host.console` пускает уборку блобов (`sweep_loop`) и уборку заявок (`requests_loop`, урок 14).

Асимметрия — корень отдельно, остальные в словаре — не случайна. Страница есть только у корня, одна на процесс: `<sub>.shell.html` рядом со спекой корня (у VMS — `vms/vms.shell.html` рядом с `vms.subsystem.yaml`), а нет такого файла — платформенная `console.html` (урок 16). `/` должен вести к ней, а не к списку подсистем. Оператор открывает подсистему, которую развёртывание поставило в корень (в М10B это камеры, `CONSOLE_ROOT=vms`); всё остальное — под своими именами.

```python
    def resolve(self, path: str) -> tuple[SpecConsole, str]:
        head = path.split("/", 2)
        if len(head) >= 2 and head[1] in self.mounts:
            return self.mounts[head[1]], "/" + (head[2] if len(head) > 2 else "")
        return self.root, path
```

Вся маршрутизация — семь строк. `split("/", 2)` с ограничением: `/pick/where/a` даёт `["", "pick", "where/a"]`. Если второй элемент — имя смонтированной подсистемы, отдаём её консоль и остаток пути, начатый со слэша; иначе — корень и путь целиком.

`/pick` без остатка даёт `"/"` подсистемы `pick` — и 404 «pick is mounted: the page is the console root's»: своей страницы у смонтированной подсистемы нет, её единицы показывает модуль на странице корня, читая её `/pick/spec` (`test_only_the_consoles_root_serves_a_page_and_a_mounted_subsystem_none`).

И главное: **консоль не знает, что она смонтирована.** Её `dispatch` получает путь уже без префикса и работает так же, как если бы сидела на своём порту. Ради этого `dispatch` в шаге 5 принимает обработчик аргументом, а не является его методом. Два знания `Mount` ей всё же передаёт: общий каталог единиц (выше) и корень ли она. От второго зависят две вещи: числа платформы (`w2c_resources_live`, `w2c_resource_*`, шаг 11) говорит только корень (`says_platform`), и страницу на `/` отдаёт только корень (`serves_page`). `Mount._adopt` ставит оба каждой консоли, смонтированной сразу или позже.

Коллизия имён возможна: подсистема с именем `spec` или `metrics` перехватила бы маршрут корня. Внутри подсистемы она закрыта — строки и объявленные таблицы, названные маршрутом консоли, спека не загрузит (`CONSOLE_ROUTES`, шаг 12). Имя самой подсистемы против маршрутов не проверяется — есть соглашение, что имя подсистемы совпадает с её префиксом в хранилище, а префиксы и так должны быть различны.

```python
    def describe(self) -> dict:
        return {"root": self.root.spec.name, "mounts": {n: c.describe() for n, c in self.mounts.items()}}
```

`GET /mounts` — маршрут самого `Mount`, как `/drain`, `/schema`, списание сервера (`POST`/`DELETE /servers/<s>/decommission`) и метки сервера (`GET`/`PUT`/`DELETE /servers/<s>/labels`): сервер несёт все подсистемы, и вопрос о нём задаётся всем консолям сразу. До третьего ревью эти маршруты отвечали **до** `dispatch`, где стоят ворота: `POST /drain?server=…` без токена уводил с сервера все единицы, а необратимый `PUT /schema` был открыт (блокер 2). Теперь `Mount.admit` спрашивает ворота корневой консоли: `admin` на изменение, `view` на чтение — `GET /mounts` отдаёт описание подсистем, а `/spec` каждой и так за воротами. Тест: `test_drain_schema_and_mounts_ask_the_gate_too`.

**Один плохой элемент — не весь маршрут.** Заход по масштабу нашёл маршруты консоли, которые падали целиком на одном элементе, и десятое ревью добавило к ним сырой `server` в пульсе. Воспроизведено запуском на каждом:

| Маршрут | Что делал один плохой элемент | Теперь |
|---|---|---|
| `/servers` | `"server": ["srv-x"]` в пульсе воркера — `TypeError` (ключ словаря); `5` среди строк — `TypeError` в `sorted` | пульс не разбирается (`contract._named`), пропущен и посчитан; остальные серверы на месте |
| `/unplaceable` | тот же пульс; адрес, по которому единицы группируются (`group_by` с `cut_at`), `rtsp://[::1/x` — `ValueError: Invalid IPv6 URL` | пульс — его; адрес, у которого хоста не прочесть, — без группы (`spec.url_host`), ни с кем; записать такой дверь не даст: 400 с `fault: bad_url` (ADR 0053) |
| `/drain` | то же и `worker` списком — `TypeError` | то же |
| `/metrics` | `server` списком или числом в пульсе ресурса — `resources_seen` и `sorted(res.items())` | пульс ресурса не разбирается, посчитан в `w2c_resource_heartbeats_garbled`; 400-значный `started` закрыт в девятом (`rows.number`) |
| `/schema` | `build` списком — `TypeError` (множество сборок); строка `platform/schema` словом — `ValueError`; `schema: 1e999` — процесс пропускался | `build` — `?`; `version: null`; схема `null`, `can_raise_to` не выше хранилища, `set_schema` отказывает |
| `/domain` | `domain/view` рваный, списком — 500; `ts: Infinity` — вид «свежий» навсегда | 503 «вид домена прочитать нельзя» |
| `POST /<rows>`, `PUT /<rows>/<id>`, `POST /marks`, `PUT /policy` | тело не JSON, список, вложенное глубже, чем читает JSON — 500 или вовсе без ответа; отметка, чья единица не ссылка, — 500 | 400 (`object_body`, `ref_fault`), ничего не записано; ключ идемпотентности не тратится; тело, которое не читается (не UTF-8, одинокий суррогат, `NaN`, `1e400`), — с `fault` (`not_json`/`not_number`, `console.fault_of`) |
| ворота: тело `POST /marks`, `/requests`, строки таблиц (`_named`, `admit_rows`) | `RecursionError` мимо `except ValueError` — без ответа | тело, которое не читается, — 400 до ворот (`dispatch`: `error: "bad body"`, `fault`), ключ не заявлен; ворота спрашивают только тело, которое прочлось |

Тесты: `test_one_bad_element.py::test_a_heartbeat_whose_server_or_worker_is_no_name_is_that_heartbeats_and_no_route_falls`, `test_schema_lists_a_process_whose_schema_does_not_read_and_raises_past_nobody`, `test_a_domain_view_that_does_not_read_is_said_and_not_a_500`, `test_a_source_that_does_not_parse_costs_its_camera_not_drain_unplaceable_or_the_catalogue`, `test_a_body_that_is_no_json_object_is_refused_on_every_write_route`. Обходы `_unplaceable` и `_would_strand` сначала закрыли только корни (пульс, адрес группы), и новый вид битого элемента в строке единицы снова уронил бы маршрут целиком. Теперь у обоих есть защита на единицу (`_eligible_or_none`, уроки 11 и 17): единица, чьи фильтры упали, стоит в ответе как та, которую никто не примет, и считается (`table="unit_judged"`), а остальные проверяются. Тест: `test_one_bad_element.py::test_a_unit_whose_filters_raise_is_one_nothing_can_serve_and_the_others_are_judged`.

**Метки сервера — тоже у корня** (ADR-0026, добавление «Архитектора»). Строка меток одна на сервер (`platform/servers/<сервер>`, урок 11), поэтому и маршрут один: `GET`/`PUT`/`DELETE /servers/<сервер>/labels` отвечает `Mount.labels_route`, а не консоль подсистемы. Раньше маршрут был у каждой подсистемы, и `PUT /<sub>/servers/<сервер>/labels` писал смонтированной подсистеме её собственную строку; теперь такого пути нет — 404, и псевдонима не будет (ADR-0003). Писать — `admin` на весь кластер, смотреть — любой грант (`admit`, как у `/drain`). Сервер должен быть известен хоть одной подсистеме: воркер любой из них, ресурс, строка меток, списание (`Mount.servers_known`); иначе 400 словами, как опечатка в имени. Каждая запись — строка журнала (`server.labels.set`, `server.labels.cleared`, шаг 8). Что правка увезёт, страница спрашивает до записи, и ответ — один список по всем спекам, каждая единица ссылкой `<sub>/<id>`, только те, что вызывающему можно видеть:

```python
    def would_move(self, h, server: str, labels) -> list[str]:
        sees = self.root._visible(h)
        out = []
        for c in (self.root, *self.mounts.values()):
            for uid in c.ctl.would_move(server, labels):
                target = self.root.target_in(c, uid)
                if sees is None or sees(*target):
                    out.append(target[0])
        return out
```

Охранник с грантом на `vlan:b` не узнаёт номеров единиц на `vlan:a`, а голый номер `7` без подсистемы ничего не говорил бы странице, у которой в одном списке единицы разных подсистем. Тесты: `test_server_labels.py::test_one_row_a_server_for_every_subsystem_and_the_edit_names_the_units_of_each`, `::test_a_server_known_to_any_subsystem_takes_a_row`, `::test_only_an_admin_of_the_whole_cluster_writes_a_servers_labels`.

`GET /mounts` — единственный маршрут `Mount`, который ничего не меняет и ничего не спрашивает у контроллеров. Ответ содержит **полное описание каждой подсистемы** (шаг 3), а не только имена: клиент, пришедший на порт впервые, за один запрос узнаёт, что здесь живёт и какие у каждого поля. Так читающая модель М12 открывает узел, ничего не зная о нём заранее.

```python
    def handler(self):
        mnt = self

        class H(SendMixin, Deadlined, BaseHTTPRequestHandler):
            timeout = float(os.environ.get("CONSOLE_TIMEOUT", CONSOLE_TIMEOUT))

            def log_message(self, *a): pass

            def _route(self, method):
                u = urlsplit(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
                # A connection of the reserve is for the door in and for monitoring, whichever subsystem's (`Bounds`).
                if self.busy_unless(RESERVE_ROUTES, mnt.resolve(u.path)[1]):
                    return
                if method in ("POST", "DELETE") and u.path.startswith("/servers/") and \
                        u.path.endswith("/decommission") and u.path.count("/") == 3:
                    user = mnt.admit(self, method)               # `admin`: every unit of a server moves
                    if user is None:
                        return
                    if method == "POST" and not read_body(self, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
                        return
                    return self._send(*mnt.decommission_route(self, method, u.path, user))
                if method in ("GET", "PUT", "DELETE") and u.path.startswith("/servers/") and \
                        u.path.endswith("/labels") and u.path.count("/") == 3:
                    user = mnt.admit(self, method)
                    if user is None:
                        return
                    if method == "PUT" and not read_body(self, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
                        return
                    return self._send(*mnt.labels_route(self, method, u.path, user))
                if u.path in mnt.MOUNT_ROUTES:
                    user = mnt.admit(self, method)
                    if user is None:
                        return                                           # refused, and said so
                    if u.path == "/mounts":
                        return self._send(200, mnt.describe())
                    if u.path == "/drain":
                        return self._send(*mnt.drain_route(method, q, user))
                    return self._send(*mnt.schema_route(method, q, user))
                con, path = mnt.resolve(u.path)
                con.dispatch(self, method, path, q)

            def _answered(self, method):
                try:
                    self._route(method)
                except TooLarge as e:
                    self._send(413, {"detail": str(e), "error": "too large for the store"})

            def do_GET(self): self._answered("GET")
            def do_POST(self): self._answered("POST")
            def do_PUT(self): self._answered("PUT")
            def do_DELETE(self): self._answered("DELETE")

        return H
```

`_answered` — то, чего хранилище не может вместить, говорится на любом маршруте: ключ длиннее, чем хранилище может назвать файл (строка таблицы или метки сервера под именем в сто тысяч символов), бросал мимо маршрутов, знавших только размер строки, и соединение обрывалось без ответа (одиннадцатое ревью, minor). Теперь — 413 словами хранилища; бросается это до записи, так что ничего из ответа ещё не отправлено.

Класс обработчика **один на все подсистемы** — он и не может быть другим, `ThreadingHTTPServer` принимает ровно один. Отсюда и форма `dispatch`: обработчик общий, диспетчер у каждой свой.

`mnt = self` — замыкание вместо атрибута класса: обработчик создаётся заново для каждого `Mount`, и связь идёт через область видимости.

`q` схлопывает повторяющиеся параметры к первому: `?unit=testsub/a&unit=testsub/b` даёт `testsub/a`. Ни один маршрут курса не принимает списков, а разбираться в них в четырёх местах не хочется.

`log_message` замолчан: `BaseHTTPRequestHandler` по умолчанию печатает каждую строку запроса в `stderr`, и на нагруженной коробке это десятки строк в секунду в журнал, где нужны совсем другие.

**Срок — у запроса, а не у одного чтения.** `timeout` — срок сокета на каждое чтение и запись (четвёртое ревью: без него полстроки запроса держали поток до перезапуска). Но он ограничивал одно чтение, а не запрос: клиент, присылавший байт заголовка раз в полторы секунды при сроке в две, держал соединение сколько хотел, и всё это до ворот (пятое ревью, major, воспроизведено запуском двумя ревьюерами). Теперь чтения обработчика идут через `DeadlineReader` (его подмешивает `Deadlined` — половина обработчика, общая для всех дверей курса, см. ниже): каждому даётся остаток срока запроса, но не больше срока сокета, а после срока чтение — `TimeoutError`, и `BaseHTTPRequestHandler` закрывает соединение. Строка запроса и заголовки получают на всё вместе **`CONSOLE_HEADER_TIMEOUT`** (5 с), а не срок сокета: соединение, о котором ещё никто ничего не знает, держит место пять секунд, не тридцать (шестое ревью; раньше — `CONSOLE_TIMEOUT`, и шестьдесят четыре полустроки держали шестьдесят четыре места по полминуты). Тело — свой срок, когда его читает `read_body`. Только чтения: то, что дверь пишет в ответ потоком, остаётся сроку сокета и правилу самой отдачи (`Paced`, ниже; у консоли таких ответов нет — байты держателей идут мимо неё). Тесты: `test_console_load.py::test_a_request_that_trickles_its_headers_is_closed_at_its_deadline`, `test_console_load.py::test_a_connection_nobody_knows_yet_has_seconds_for_its_headers_not_the_sockets_timeout`.

```python
    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        return open_doors(host, port, self.handler())
```

```python
def open_doors(host: str, port: int, handler, unix_env: str = "CONSOLE_UNIX", say: bool = True) -> ConsoleServer:
    if say:
        say_where(host)
    srv = ConsoleServer((host, port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    path = os.environ.get(unix_env) or ""
    if path:
        try:
            srv.unix = UnixConsoleServer(path, handler, srv.bounds)
            threading.Thread(target=srv.unix.serve_forever, daemon=True).start()
            log.info("the box's own door is %s: the emergency entry's own turns and connections are there", path)
        except OSError as e:
            log.error("the box's own door %s could not be opened (%s): this console has no lane for the caller on the "
                      "box — the emergency entry competes with the network", path, e)
    else:
        log.info("no door of the box's own (%s is not set): the emergency entry has the network's turns only", unix_env)
    return srv
```

`unix_env` и `say` — для двух других дверей, где входит человек: консоли домена и подписчика (М12). У них переменная сокета своя (`DOMAIN_CONSOLE_UNIX`, `SIGNER_UNIX`), а предупреждение про токены по открытому HTTP — консольное.

**И одновременно — не больше `CONSOLE_CONNECTIONS`.** `ThreadingHTTPServer` заводил поток на каждое соединение без предела: триста медленных клиентов — триста потоков. `ConsoleServer` обслуживает `CONSOLE_CONNECTIONS` (64) соединений сразу, а следующему принимающий поток сразу пишет 503 с `Retry-After: 1`, ничего из сокета не читая и не ожидая дольше секунды, и отдаёт сокет на закрытие (`linger`, ниже). Тест: `test_console_load.py::test_past_its_bound_on_connections_the_console_answers_503_at_once` — три полустроки при пределе 3 держат все места, четвёртое соединение получает 503, а когда место освобождается, консоль отвечает снова.

**Но один предел на всех, взятый до того, как кто-то известен, закрывал дверь всем.** Шестьдесят четыре соединения без токена, переподключающиеся, — и 99,3 % запросов получали 503, в том числе верный аварийный пароль с коробки и `/metrics` для Prometheus (шестое ревью, major, воспроизведено запуском). Соединение считается в момент `accept`, когда о нём известен только адрес, — и предел теперь режется по тому, что известно (`Bounds`):

| Полоса | Что это |
|---|---|
| общая | `CONSOLE_CONNECTIONS` (64) мест, и **один адрес держит не больше `CONSOLE_PER_ADDRESS`** (8) из них — с токеном или без; IPv6-адрес считается своей /64; пир, названный в `TRUSTED_PROXY`, не считается — его соединения общие, и предел на вызывающего тогда держит прокси |
| резерв | `CONSOLE_RESERVE` (16) соединений сверх общих — **только когда общие места кончились все**, не больше `RESERVE_PER_ADDRESS` (1) на адрес; на заголовки — `RESERVE_HEADERS` (2 с); отвечают только вход и `/healthz` (`RESERVE_ROUTES`), всё остальное — 503 |
| мониторы | `CONSOLE_MONITOR_RESERVE` (4) соединений сверх общих для адресов из `CONSOLE_MONITORS` (адреса или сети через запятую), и только для них, **не больше `MONITOR_PER_ADDRESS` (2) на адрес**; отвечают `/metrics` и `/healthz` (`MONITOR_ROUTES`) |
| коробка | `CONSOLE_BOX_RESERVE` (4) соединений для того, кто пришёл через unix-сокет консоли (`CONSOLE_UNIX`, `UnixConsoleServer`), — его никто с сети не откроет; отвечают на любой маршрут: оператор, вошедший аварийно, пришёл работать |

Оба сервера — TCP и unix — делят одни `Bounds`.

**Очередь ядра держит столько, сколько обслуживает дверь, со всеми полосами.** Пока поток приёма не забрал соединение, оно ждёт в очереди ядра, а `socketserver` открывает её на 5 мест (`request_queue_size`). Всплеск больше пяти, пришедший раньше, чем проснулся поток приёма, дверью не считался и 503 не получал. Unix-сокет на macOS отказывал в `connect` сразу. TCP ронял SYN, и клиент ждал повтора секунду. Нашлось это на сокетах ролей хранилища (М11, урок 2): их тест падал в трёх запусках из семи. Теперь очередь — это сумма полос из `Bounds` (`w2cplatform/console.py`, `Bounded`):

```python
    @property
    def request_queue_size(self) -> int:
        b = self.bounds
        return b.limit + b.reserve + b.monitor + b.box
```

`ConsoleServer` и `UnixConsoleServer` ставят `bounds` до `super().__init__`, то есть до `listen`. То же получают двери из `door_server`: держатель, регистратор, шлюз и ресурс. Тест: `test_console_load.py::test_every_bounded_door_queues_as_many_connections_as_it_serves_before_it_accepts_one`. Дверь, которая не принимает ни одного соединения, берёт в очередь все места: по TCP через `door_server`, по unix через `UnixConsoleServer` со всеми четырьмя полосами. На очереди в пять мест тест падает.

**Четыре адреса закрывали консоль целиком, вместе с резервом** (седьмое ревью, major, воспроизведено запуском). При шестнадцати общих местах на адрес и двух резервных четыре адреса, шлющие полстроки и переподключающиеся, держали все 64 общих места и все 8 резервных, и честный адрес не получил ни одного 200 — ни `/metrics`, ни `/healthz`, ни входа, ни `/cameras`. В этом уроке и в ответе на шестое ревью было написано «десятки адресов»; на деле — четыре. Теперь доля адреса — 8 (параллельные запросы одной страницы, а не четверть двери), резерв берётся только когда общие места кончились все — адрес, исчерпавший свою долю при свободных общих, получает 503, а не резерв, — и держит одно соединение адреса. `/metrics` из резерва ушёл: Prometheus известен заранее, и для него своя полоса, которую никто другой не займёт. `/healthz` раньше был назван в резерве, а маршрута не было — консоль отвечала на него 404; теперь он есть.

Честные числа при умолчаниях. До семи адресов потопа общие места не кончаются, и все обслуживаются как обычно. С восьми до пятнадцати общие места заняты: честный адрес получает вход и `/healthz` с резерва, по одному соединению, и больше ничего. С шестнадцати занят и резерв: по TCP отвечают только мониторам из списка, а коробке через её сокет — на любой маршрут. Различить честного и многих до чтения запроса дверь не может; она может сделать «многих» числом, которое записано. Настоящий ответ на распределённый потоп — по-прежнему прокси или фильтр перед портом. Тесты: `test_console_load.py::test_four_or_eight_addresses_flooding_keep_neither_an_honest_door_in_nor_a_listed_monitor_out` — при четырёх адресах честный адрес получает и вход, и `/cameras`; при восьми — вход с резерва, `/cameras` и `/metrics` без списка — 503; при шестнадцати — 503 и на вход; монитор из `CONSOLE_MONITORS` получает `/metrics` во всех трёх случаях; и `test_console_load.py::test_a_flood_from_one_address_keeps_neither_the_emergency_entry_at_the_box_nor_monitoring_out` — потоп с одного адреса берёт свои восемь мест и ни одного больше; с коробки через сокет открывается аварийная сессия и под ней работает любой маршрут.

**Полоса мониторов — тоже с долей адреса, а список мониторов — это доверие** (восьмое ревью, major, воспроизведено запуском). Задание М11 перечисляло `10.0.0.0/8`, а у полосы мониторов предела на адрес не было. Восемь адресов сети кластера, шлющие полстроки, занимали общие места, резерв и все четыре места полосы, и у честного Prometheus `/metrics` отвечал 503 в 15 из 15; автоскейлер, читающий `/metrics`, слеп. Теперь адрес держит не больше `MONITOR_PER_ADDRESS` (2) мест полосы — скрейпер и проверку здоровья с одной коробки. Чтобы занять полосу, нужно два адреса из списка. Список — это адреса, которые скрейпят, а не сеть, в которой они живут, и адрес из списка — доверенный: задание М11 перечисляет loopback узла, адрес узла и то, что оператор назовёт в переменной `monitors` (Prometheus автоскейлера), М12 — то же для консоли домена и подписчика. Тест: `test_console_load.py::test_one_listed_monitor_holds_two_places_of_its_lane_and_another_listed_one_is_answered` — адрес из списка открывает четыре полустроки при занятых общих местах, полоса держит две из них, и другой адрес из списка получает `/metrics`.

**Отказ, который клиент может прочитать** (седьмое ревью, minor; на macOS — шесть запусков из шести). 503 записывался, и сокет закрывался с непрочитанным запросом внутри, а сокет, закрытый с непрочитанными байтами, ядро не завершает, а сбрасывает (RST): клиент на macOS получал `ECONNRESET` вместо лежащего в его буфере 503 с `Retry-After`. Теперь соединение закрывается в два шага: `SHUT_WR` — наш ответ окончен, — потом то, что клиент ещё шлёт, читается и выбрасывается, пока он не закроет сам или не пройдёт `LINGER` (1 с). Делает это один поток на процесс (`linger`), а не принимающий: поток отказов не должен тормозить приём следующих. Каждый сокет читается не дальше `LINGER_BYTES`. **Поток отказов не занимает комнату ожидания** (восьмое ревью, minor, воспроизведено запуском). Атакующий продолжал слать после своих 503, 256 мест очереди были все его, и следующие отказы закрывались сразу — сбросом, у честного клиента тоже (`ConnectionResetError` в 30–35 из 48 при шестнадцати адресах). Теперь, когда комната занята наполовину (256 из `LINGER_MAX`, 512), адрес больше не добавляет мест сверх `LINGER_PER_ADDRESS` (4): вторая половина — другим адресам. До половины доли нет: клиент, который быстро повторяет, или параллельные запросы страницы ждут, как раньше. Первая версия держала долю всегда, и тест седьмого ревью — десять отказов подряд с одного адреса — снова получал сброс (`test_a_refusal_is_read_by_the_client_not_reset_under_it`). Отказ сверх них тоже не бросается как есть (`_drain_close`): присланное к этому моменту читается и выбрасывается, и сокет закрывается. Если непрочитанного не осталось, клиент получает FIN, и 503 остаётся читаемым. Обрыв (`SO_LINGER` 0) — только клиенту, который шлёт дальше `LINGER_BYTES`: его закрытие сбросило бы и так, а обрыв сразу освобождает ядро. Место в очереди стоит сокета и строки словаря: присланное читается и выбрасывается, а не хранится. Чего это не делает: сто тридцать адресов займут и вторую половину. Так же закрывается соединение, на которое обработчик ответил, не дочитав тело (413, 503 резерва): `Bounded.shutdown_request` смотрит, есть ли непрочитанное. Тесты: `test_console_load.py::test_a_refusal_is_read_by_the_client_not_reset_under_it` и `test_console_load.py::test_sixteen_addresses_that_go_on_sending_after_their_refusal_leave_the_honest_refusal_readable` — шестнадцать адресов по двадцать соединений шлют после отказа и не закрывают; потоп занимает свою половину комнаты, и 48 отказов честному клиенту (повтор через 0,1 с) читаются все, без сброса (на прежнем коде — 25 сбросов из 48); в М12 `test_the_domains_console_is_a_door_like_the_others_bounded_and_with_a_ceiling_on_a_body` прошёл десять запусков подряд на macOS.

**Та же дверь — у каждой двери.** Защиты были только у консоли, а дверь держателя (`/playback`, М10B, урок 15), дверь регистратора, шлюз живого видео, ресурс и обе двери домена (М12) оставались `ThreadingHTTPServer` без предела и срока: триста медленных соединений к держателю — триста два потока в процессе, который держит все камеры сервера (шестое ревью, major). Поэтому обе половины вынесены и подмешиваются: сервер — `door_server` (тот же `ConsoleServer` с `Bounds` по умолчанию на 64 соединения и 32 на адрес — пир такой двери это процесс кластера, который спрашивает многое сразу — без резерва, без полосы мониторов и без полосы коробки: сюда никто не входит), обработчик — `Deadlined` (срок на строку запроса и заголовки). Числа у дверей не одни: дверь держателя передаёт свои — `PLAYBACK_CONNECTIONS` 32 и `PLAYBACK_PER_ADDRESS` 8, — потому что её потоки это потоки процесса со всеми камерами сервера; регистратор, шлюз и ресурс — 64 и 32. Тело читают не все двери, и читают по-разному: консоль, шлюз (предложение WebRTC), консоль домена и подписчик — через `read_body` (потолок, срок `timeout + n/BODY_RATE`); ресурс в `PUT /mirror` пишет тело в файл кусками и даёт ему тот же срок через `body_deadline`, а не через `read_body` — до седьмого ревью срока у этого тела не было вовсе, и правило теперь такое: кто читает тело после заголовков, ставит ему срок; двери держателя и регистратора тел не читают, у них только `GET`.

**У тела — пол темпа, а не только срок** (восьмое ревью, воспроизведено запуском). Срок был пропорционален длине, которую тело **объявило**, без пола скорости. 60 МБ получали 945 с, 64 МиБ — 1054 с, и отправитель байта раз в несколько секунд держал соединение всё это время. 32 таких соединения занимали долю адреса у двери ресурса, а два адреса — всю дверь (`/events`, `/events/wait`, зеркала) примерно на 17 минут за цикл. Теперь после льготы тело приходит не медленнее `BODY_RATE` в среднем, иначе чтение опоздало (`DeadlineReader.pace`, его ставит `body_deadline` для каждой двери, читающей тело): к `timeout + got / BODY_RATE` секундам от начала тела должны прийти `got` байтов. Телу, которое идёт с тем темпом, на который срок всегда рассчитывал, ничего не меняется — прежний срок и есть последняя точка этого пола. Струйку дверь отпускает на льготе, а не в конце объявленного. Чтобы держать долю двери, теперь нужно **слать** `BODY_RATE` на соединение. Тест: `test_console_load.py::test_a_body_that_trickles_is_let_go_at_its_grace_whatever_length_it_declared` — 60 МБ, объявленные и поданные струйкой в `PUT /mirror`, получают 408 меньше чем за 4 с при льготе 1 с, и копии нет; так же тело `POST /marks` у консоли; бакет, поданный втрое быстрее пола, ложится целым. Что дверь **отдаёт потоком**, идёт через `Paced` и `start_stream` — об этом в М10B, уроке 15. Консоль домена и подписчик (М12) с седьмого ревью — не `door_server`, а консольные двери: те же `Bounds`, что у консоли, с резервом, полосой мониторов и сокетом коробки (`open_doors`). Тесты: `test_console_load.py::test_the_holders_door_is_bounded_and_deadlined_like_the_consoles`, `…::test_the_gateways_offer_is_bounded_and_its_door_is_the_consoles`, `…::test_the_resources_door_is_bounded_and_a_mirrored_bucket_is_never_held_whole`, `…::test_the_resources_door_gives_a_mirrored_body_a_deadline_whole`; М12, `test_lesson3_readview_api_gateway.py::test_the_domains_console_is_a_door_like_the_others_bounded_and_with_a_ceiling_on_a_body` и `…::test_the_domains_console_has_the_consoles_reserve_and_a_listed_monitor_is_answered_whoever_floods`. Отдельного теста двери подписчика нет: она собирается в `main()` из окружения и идёт тем же `open_doors`, что консоль домена.

**После заголовков пол есть всегда, даже если обработчик не поставил срок телу** (двенадцатое ревью, major 8). После заголовков срок запроса становился годом (`365 * 86400`), и пол получал только тот, кто звал `body_deadline`. Обработчик, читающий клиента без него, — дверь подсистемы, написанная позже, маршрут, который дочитывает часть тела сам, — ждал по байту, пока клиент капал, и соединение с потоком принадлежали клиенту. Теперь первое чтение после заголовков, не нашедшее пола, ставит его само (`DeadlineReader.lazy`): льгота — `timeout` обработчика, дальше `BODY_RATE`, кто бы ни читал.

```python
    def parse_request(self):
        ok = super().parse_request()
        self.deadline = float("inf")
        reader = getattr(self.rfile, "raw", None)
        if isinstance(reader, DeadlineReader):
            reader.lazy = True
        return ok
```

Чего срок соединения не делает и не может: поток, который ждёт не клиента, а устройство или соседа, не кончит никакой срок сокета. Такие ожидания каждая дверь ограничивает сама — у держателя это `_door_ask` для вопросов и `_door_read` для чтений сессий (М10B, урок 15). Тест: `test_console_load.py::test_past_its_headers_a_door_reads_its_client_with_a_floor_even_where_no_body_deadline_was_set` — обработчик читает тело без `body_deadline`, клиент шлёт байт раз в 0,2 с, и чтение обрывается меньше чем за 3 с при льготе 0,5 с; тело, поданное вчетверо быстрее пола, приходит целым.

И зеркальный ему метод одиночной консоли, ради которого всё сошлось:

```python
    def handler(self):
        """The request handler class for this console alone — a Mount with no other subsystems."""
        return Mount(self).handler()
```

**Одиночная консоль — это `Mount` без смонтированных подсистем.** Один путь кода вместо двух: то, что работает для семи, работает для одной, и тест, поднимающий одну консоль, проверяет ту же маршрутизацию, что и рабочий процесс.

`daemon=True` — чтобы тест, забывший остановить сервер, не подвесил прогон. `port=0` в тестах: ядро выдаёт свободный порт, и он читается из `srv.server_address[1]`.

## Результат

`SpecConsole`, собранная из спецификации: описание и чтения, идемпотентные ключи в хранилище, четыре записи, `/servers`, `/policy`, `/metrics`, объявленные таблицы, идемпотентная подача заявок и дверь держателя, ворота — и `Mount`, после которого подсистема становится путём. Ниже — запуск на `testsub` (ответы укорочены).

```python
from w2cplatform.console import SpecConsole, Mount

root = SpecConsole(SpecController(testsub, vars_, objects), marks_root=events_root)
srv  = Mount(root).serve(port=0)
port = srv.server_address[1]
```

```
GET  /mounts            → {"root": "testsub", "mounts": {}}
GET  /spec              → имя, строки, поля, имена метрик
GET  /counters          → {"rows": [...], "configured": [...]}
POST /counters {"name": "c1"} + Idempotency-Key: a1   → 201 {"id": "c1", …, "worker": null}
POST /counters {"name": "c1"} + Idempotency-Key: a1   → 201 тот же ответ, вторая единица не создана
POST /marks {"unit": "testsub/c1", "note": "…"} + Idempotency-Key: m1 → 201 {"subsystem": "console", …}
POST /marks {"unit": "c1"}  + Idempotency-Key: m2   → 400 a unit is named <sub>/<id> …
POST /requests {"unit": "testsub/c1", "add": 5} + Idempotency-Key: r1 → 202 {"queued": {"id": "r1", …}, …}
POST /requests {"unit": "testsub/c1", "add": 5} + Idempotency-Key: r1 → 202 тот же ответ, строка одна
PUT  /policy            {"servers": "distinct"} → 200
GET  /metrics           → testsub_workers_live 0 … testsub_counters_running 0 … w2c_requests_expired_total …
DELETE /counters/c1     → 200 {"deleted": "c1"}
DELETE /counters/c1     → 404
```

Платформа, которая ничего не знает ни об одной подсистеме, получила консоль, одну на все: что показать, что можно писать, кому и куда идут байты — говорят спеки.

---

## Что может пойти не так

| Симптом | Скорее всего |
|---|---|
| Повторный POST создаёт вторую единицу | Заявка живёт в памяти процесса. Работает до второй консоли, то есть не работает. |
| Повторный POST висит две секунды и отвечает 409 | Победитель не дошёл до `store` — упал или отвечает дольше. Ответ честный; повтор заявится заново. |
| Идемпотентные ключи копятся вечно | `prune` не вызывается — он живёт внутри `claim` и срабатывает не чаще раза в минуту. |
| Страница не показывает поле, добавленное в YAML | Процесс консоли не перезапущен: спецификация читается при старте. |
| `/where` показывает воркера, не совпадающего с размещением | Идёт перемещение. Для того и два ответа; `directory` покажет обоих через `+`. |
| `/where` отвечает `door: null` | Единицу сейчас никто живой не держит, или держатель не объявил адрес двери. Страница спросит снова. У `/where/<table>/<place>` — ещё и `?unit=` не назван: токен всегда одной единицы. |
| `/where/<table>/<place>` отвечает 404 с `X-Unreachable: <place>@<server>` | Места сейчас не держит ни один живой воркер с дверью: то, что на нём лежит, недоступно, пока его кто-нибудь не возьмёт. 404 с `no such place` — строка не отвечает `where` из `placement.places` (выключена) или её нет. |
| `POST /<rows>` отвечает 409 `exists` | Id уже занят единицей: второй POST пришёл под другим ключом идемпотентности. Под тем же ключом повтор получил бы сохранённый 201. |
| `POST /requests` отвечает 429 «учёт не читается» | Строка `<sub>/requests/asks-…` этого человека не читается. Остальные подают как обычно; администратор удаляет строку (`DELETE /requests/asks-…`). |
| Спека не загружается: «a route the console answers itself» | Строки или объявленная таблица названы маршрутом консоли (`marks`, `events`, …): ни один запрос до них не дошёл бы. Назовите иначе. |
| `POST /requests` отвечает 429 | У человека уже `per_person` неотвеченных заявок: держатель не успевает или единицу никто не держит (`/where`). Заявки уходят из счёта, когда их строки убраны, но не позже `ttl` (при `ttl: 0` — только когда убраны). |
| `POST /requests` повторили — и работа сделана дважды | Строка названа не входами и не ключом (`id` из тела, меняющийся от попытки к попытке). Имя заявки — шаблон `key` спеки или `Idempotency-Key`. |
| `/where` отвечает медленно | Кэш скана меньше пяти секунд или отключён: это скан всех назначений. |
| События одной подсистемы не отсекаются | В словарь эпох не попал её префикс: перечисление идёт по всем ключам с `/epoch/`, а то, чего скан не увидел, спрашивается по имени — проверьте `epochs_unread` в ответе. |
| `/events?unit=7` отвечает 400 | Единица названа голым id. Ссылка — `<sub>/<id>`. |
| Отметка оператора попала в бакет чужой единицы | Кто-то пишет в чужую единицу. У консоли своя: `console/<экземпляр>/e1`. |
| `/events` отвечает 503 | Индекс не передан. Так и задумано: лучше сказать, чем вернуть пустой список. |
| `python3 -m w2cplatform console` не стартует | `CONSOLE_ROOT` не называет ни одной спеки каталога: что в корне, говорит развёртывание. |

А это уже не симптомы, а решения, которые кажутся разумными ровно до того, как их примешь:

- **`store` после отправки ответа.** Кажется естественнее — сначала ответить, потом записать. При падении процесса между ними повтор создаст вторую единицу. Записывайте до.
- **Ключ идемпотентности у `DELETE`.** Соблазнительно ради единообразия. Результат: второй `DELETE` возвращает `200` из сохранённого ответа, и оператор не узнаёт, что удалять было нечего.
- **`Forbidden` через тот же 400, что и `Refused`.** Администратор будет искать ошибку в значении, а проблема в токене.
- **Маршрут подсистемы в консоли «на один раз».** Функция подсистемы, которой консоль отдаёт непонятые маршруты, удобна ровно до второй сборки консоли, которая забудет её подключить, — и до первого байта, который пойдёт через процесс, не должный его видеть. Что строка значит — в спеку; что сделать с данными — в воркер; что показать — в страницу.
- **Подсистема, смонтированная под именем существующего маршрута** (`spec`, `metrics`, `mounts`, `policy`). Маршрут корня исчезает молча. Имена подсистем — те же, что префиксы хранилища; держитесь этого.
- **Реестр серверов «чтобы было надёжнее».** Появится вторая правда о машинах, и она разойдётся с heartbeat'ами ровно тогда, когда правда нужнее всего.
- **Регистрация метрик через клиентскую библиотеку.** Зависимость, процесс-коллектор, формат, который всё равно текст. Двадцать строк f-строк делают то же и читаются.
- **Норматив потока, записанный и не прочитанный.** Число в конфиге, за которым ничего не происходит, — комментарий: буря идёт ровно так же. Либо у него есть действующая половина, либо его нет.
- **Агрегация, сделанная в индексе.** Тогда её получит и процесс, который действует по событиям, и его правило перестанет видеть своё событие. Внимание бережём человеку, а не процессу.
- **Тело до ворот, срок на чтение вместо срока на запрос, поток на каждое соединение.** Каждое по отдельности выглядит безобидно; вместе они дают любому, кто дошёл до порта, без токена, занять память и потоки консоли. Сначала кто, потом тело с потолком; срок на весь запрос; предел соединений с 503.
- **Права только по единице в пути.** Строка, которая называет другие единицы своими полями, обходит ворота через эти поля. Спека говорит, чья строка (`about` с `fixed`, `rights.unit_of`) и до чего дотягивается изменение (`rights.reach`, `rights.names`), и ворота спрашивают про каждую такую единицу, до правки и после.
- **Байты держателя через консоль.** Консоль становится узким местом и процессом, который видит то, что не должен; страница идёт на дверь держателя сама, с токеном, который консоль выдала вместе с адресом.
- **Один предел соединений на всех.** До чтения запроса известен только адрес — и предел надо резать по адресу, с резервом для входа и мониторинга и своей полосой для коробки, иначе шестьдесят четыре полустроки с одного адреса закрывают консоль всем, включая аварийный вход.
- **Защиты только у консоли.** Любая дверь, которую открывает процесс, — та же дверь: тот же сервер с пределом, тот же срок на заголовки, тот же потолок на тело. Иначе класс отказа переезжает на соседний порт.

## Итог

- Консоль строится из той же спецификации, что контроллер; сколько подсистем в каталоге спек, столько консолей в одном процессе, без единой новой строки.
- Консоль принимает контроллер с **токеном консоли**: то, чего ей нельзя, не запрещено соглашением, а невозможно.
- `/spec` отдаёт описание, достаточное, чтобы страница собрала список, формы и строку состояния сама; слова для страницы тоже из спеки.
- Отметка оператора — наблюдение консоли, в её собственной единице; связь с единицей, о которой она, — полем `of`, а не путём.
- Идемпотентная заявка лежит в хранилище: любая консоль узнаёт повтор и отдаёт тот же ответ; ключ — одного вызывающего и одного тела.
- Проигравший ждёт ответа победителя и не повторяет запись; не дождался — честный 409; перехваченная заявка своему прежнему владельцу уже не принадлежит.
- Под одним ключом отдаются наблюдаемое и настроенное: разница между ними — самое информативное на экране.
- «Где единица» отвечается дважды — решением и фактом, — потому что во время переезда они расходятся, и это надо видеть; у подсистемы с дверью — ещё и адрес держателя с токеном; у подсистемы с местами тот же маршрут отвечает, кто держит место (`/where/<table>/<place>`), а место без держателя называет `X-Unreachable`.
- Эпохи всех подсистем собираются перечислением ключей: база сравнивает, консоль приносит.
- Запись консоли ничего не решает: `create` отвечает `worker: None`, потому что размещает контроллер, и у консоли нет на это прав.
- Код ответа выбирается по виновнику: 400 — форма запроса, 403 — права, 404 — нет такого, 409 — такое уже есть, 503 — нет ресурса на этой машине или хранилище не ответило.
- Единица вне своих маршрутов называется одной ссылкой `<sub>/<id>` — в `/events`, в отметке, в заявке, в гранте; голый id — 400.
- Вид по серверам собран из одних heartbeat'ов: реестра машин в системе нет, и сервер, с которого никто не бился, не существует; поля подсистемы в нём нет — что показать под сервером, говорит спека.
- Метрики — текст, а имена метрик выведены из спецификации; собственные числа подсистема объявляет в спеке, и консоль печатает их, не зная, что они значат.
- Подсистема не добавляет в консоль ни строки кода: таблицы, заявки, права, метрики и дверь — объявления спеки; байты держателя идут мимо консоли, своих маршрутов для байтов у неё нет.
- Заявка подаётся идемпотентно: ключ обязателен, имя строки — из спеки или ключ, запись create-only, ответ помнится под ключом, отказ ключа не тратит; исполняет её держатель, а убирает уборка (урок 14).
- `Mount` — несколько десятков строк, после которых новая подсистема становится путём; одиночная консоль реализована как `Mount` без смонтированных.
- Соединения считаются по адресу, у входа и мониторинга резерв, у коробки — unix-сокет; права по пути спрашиваются до тела; тот же сервер и тот же срок — у каждой двери курса.

## Упражнения

1. Сделайте идемпотентность словарём в памяти. Поднимите две консоли и пошлите один POST в обе. Что получит клиент?
2. Уберите `configured` из ответа и оставьте только `rows`. Какие два состояния единицы станут неразличимы на экране?
3. Пусть `where` отвечает только строкой размещения. Проведите перемещение и опишите, что увидит оператор, спросивший в эту секунду.
4. Уменьшите кэш скана до нуля и замерьте `/where` при сорока единицах и трёх воркерах. Сколько обращений к хранилищу на запрос?
5. Пишите отметки оператора в бакет единицы, о которой отметка. Опишите, что окажется в файле, когда воркер этой единицы переедет.
6. Соберите словарь эпох только для своей подсистемы. Что перестанет отсекаться на таймлайне единицы, о которой есть единицы других подсистем?
7. Добавьте в `describe` поле, которого нет в спецификации (например, «сортировать по умолчанию»). Где оно должно жить, чтобы не пришлось править консоль?
8. Поменяйте местами `_remember` и `_send` в ветке POST. Убейте процесс между ними (`os._exit` во временной строке) и повторите запрос. Сколько единиц в хранилище?
9. Сделайте ключ идемпотентности необязательным для POST. Отправьте один и тот же запрос дважды из двух вкладок. Что увидит оператор на странице?
10. Уберите из `servers()` цикл по `resources_seen`. Опишите, что перестанет быть видно на сервере, где живёт ресурс и нет воркеров.
11. Снимите флаг `idle_by_policy`. Поставьте `servers: distinct` на трёх воркерах и опишите экран глазами оператора, который не читал урок 11.
12. Замените в `metrics_text` `self.spec.headroom_from` на строковый литерал. Какие подсистемы М10B перестанут отдавать осмысленные метрики?
13. Смонтируйте подсистему под именем `spec`. Какой запрос сломается и почему его не поймает ни один тест?
14. Объявите в копии `testsub` таблицу `pins` (`key: name`, поля `name` и `note`) и пошлите `POST /pins {"note": "x"}` — без `name`. Какой код вернётся, где именно в коде отказ, и появится ли строка в журнале?
15. Напишите `GET /mounts` для семи подсистем и посчитайте размер ответа. Что стоит из него убрать, если консолей на узле станет двадцать?
16. У `testsub` заявка названа ключом идемпотентности, у `testsub2` — шаблоном `"{unit}-{add:int}"`. Пошлите одно и то же тело дважды под двумя разными ключами в каждую. Сколько строк окажется в `<sub>/requests/` у каждой, и что это значит для оператора, который дважды и намеренно просит прибавить 5 — пока первую ещё не исполнили?

## Что дальше

Порт отвечает, маршруты есть, JSON правильный — а смотреть не на что. [**Урок 16**](16-HTML.md) — о странице, которая читает эти ответы.

# Урок 20 — Объектное хранилище: права и уборка

**Модуль:** М10A — Платформа (ServerVMS, часть первая)
**Вы напишете:** `heartbeats/` как каталог, а не как суффикс; три `acl_objects_*`, выведенные из спеки, — по каталогу с одним писателем на каждый; `verify` на чтении блоба. Затем `delete` у объектного хранилища; `sweep_blobs` в два прохода с отсрочкой и CAS, где решение записано раньше, чем удалён первый байт; снятие пометки в `put_blob`; две метрики; и тест, который ловит гонку изнутри одного прохода.
**Время:** ~110 минут.

## Зачем этот урок

Спросите себя: **нужен ли объектному хранилищу ACL?**

У строк он есть с урока 2, и он выводится из спеки — `acl_controller()`, `acl_console()`, `acl_worker()`. На одной коробке его проверяет сам клиент (`FileVariables.as_writer`), в М11 — демон хранилища: процесс приходит через сокет своей роли, `/run/configstore/<role>.sock`, и демон спрашивает файл прав раньше, чем что-нибудь применит. У объектного хранилища нет ничего: `FsObjectStore` не знает ни писателя, ни префиксов, и в `objects.py` про это сказано прямо — «No CAS, no index». Каталог объектов на коробке — `2770 w2c:w2c-store` (`deploy/w2c.tmpfiles`), и каждый юнит платформы открывает его как член группы `w2c-store`: любой процесс может записать любой объект.

Соблазн — дописать `writer`/`acl` в `FsObjectStore` по образцу `FileVariables`. Не надо, и довод есть в самом курсе, в клиенте реплицированного хранилища (`configstorevars.py`):

```python
# The socket IS the identity: the daemon opens one per role (`/run/configstore/<role>.sock`, its group
# `configstore.socket_group`) and checks the role's rights before anything is forwarded (`storemachine.Rights`). `as_writer` stays as a second,
# client-side check, as in `FileVariables` — a process that opened the wrong socket learns it here first.
```

Клиентская проверка — подсказка, а не защита: процесс, который хочет её обойти, просто её не вызывает. Защищает тот, кто стоит **между** процессом и данными и сам знает, кто звонит. У строк такой есть — демон с сокетом на роль. У объектов его нет ни на коробке, ни в М11: там объект — файл на сервере своего писателя, соседям его отдаёт ресурс (`/v1/objects`), и ни одно право хранилища его не называет, кроме ключей, которые спека подсистемы объявила строками (`objects: {rows: […]}`).

Поэтому вопрос распадается на три других. **Можно ли вообще сказать, кто пишет каждый объект**, — это вопрос раскладки ключей. **Где это сказано один раз** — в спеке, рядом со строковыми правами. И **что защищает байты там, где никакой ACL не стоит**, — дайджест.

Права разложены — и тем самым назван последний писатель каждого каталога. Остаётся долг, записанный в уроке 19 и до сих пор не отданный.

Урок 19 закончился честным остатком: блобы копятся, уборки нет. Вот чем это отличается от всего остального в объектном хранилище.

Ключ блоба — дайджест его байтов, поэтому **каждая правка поля `blob` создаёт новый вечный объект**. У heartbeat'а ключ один на слот и переписывается следующим экземпляром; у снапшота — один на воркера. Блобы растут по числу **правок за всю жизнь системы**, и до сих пор их не забирал никто.

Прежде чем писать уборку, стоит проверить встречное подозрение: а не копятся ли и heartbeat'ы? Нет, и это важно:

```python
                order = lapsed + free + [nxt]
```

`_claim_slot` берёт сначала слоты, чьё имя можно взять (просроченные), потом свободные, и только потом придумывает новое имя `nxt`. Множество имён сходится к пику одновременно живших воркеров.

И устаревший heartbeat **несущий**:

```python
        try:
            raw = objects.get(self.sub.heartbeat_key(self.name)) if self.name else None
        except OSError as e:
            raw = None
            …
        if raw:
            from w2cplatform.contract import parse_heartbeat
            old = parse_heartbeat(self.sub.heartbeat_key(self.name), raw)
            if old is not None and old.extra.get("instance") != self.instance:
                self.previous_hb, self.previous_instance = old.ts, old.extra.get("instance", "")
```

Воркер на старте читает heartbeat предыдущего экземпляра своего слота — из этого считается измеренное переключение (урок 11). Подметёте их — уберёте измерение. Так что уборка касается **только** `blobs/`, и это не осторожность, а требование.

## Кто стоит между процессом и объектом

| | строки | объекты |
|---|---|---|
| одна коробка | `FileVariables` и `as_writer` — проверка в клиенте | `FsObjectStore`; каталог `2770 w2c:w2c-store` — пишет любой член группы |
| кластер (М11) | демон `configstore`: роль — это сокет, который процесс смог открыть; права из `/etc/w2c/configstore-rights.json` спрашиваются до применения | файл на сервере писателя; соседям — через ресурс, который из объектов принимает только блоб (`PUT` — проверенный по дайджесту, и `DELETE`); ключи `objects.rows` — строки `objects/<key>` с правами роли |

Одно и то же правило — «у каждого каталога один писатель» — в левой колонке **проверяется** (на коробке — самим клиентом, в М11 — демоном), в правой — **соблюдается кодом**. Вот вся проверка демона:

```python
    def allows(self, role: str, action: str, key: str) -> bool:
        if action == "delete" and (epoch_row(key) or (key.startswith("domain/") and role not in DOMAIN_ROLES)):
            return False                          # nobody, `admin` included (`variables.refuse_delete`)
        if role == ADMIN:
            return True                           # `PEER` is no role of the file: no grant on any row (twelfth pass)
        pats = self.roles.get(role, {}).get(action, [])
        if any(_hit(p[1:], key) for p in pats if p.startswith("!")):
            return False                          # a denial wins over every grant, wherever it stands in the list
        return any(_hit(p, key) for p in pats if not p.startswith("!"))
```

Роль — это **сокет**: демон открывает `<role>.sock` с правами `0660` и группой `socket_group(role)`, юнит процесса состоит в этой группе (`SupplementaryGroups=`), и другой сокет ему не открыть. Дверь между серверами, `-api`, — только для демонов, взаимный TLS обязателен, и у демона нет права ни на одну строку: данные по этой двери — `403`. Объектам такой двери не досталось, и этот урок не пытается её построить. Он делает то, что можно сделать в платформе: **раскладку, в которой писателя каждого объекта можно назвать**, и **список, где он назван**.

## Что нужно знать заранее

- **Урок 2** — ACL у `Variables`: писатель и префиксы, и почему их два.
- **Урок 4** — объектное хранилище и записанное там «удаления здесь нет».
- **Урок 5** — раскладка ключей и `heartbeat_key`.
- **Урок 15** — `IdempotencyKeys.prune`: уже существующая в платформе уборка, с которой стоит сравнить.
- **Урок 19** — снапшот нарезан по воркеру; `blob`: байты в объектном хранилище, дайджест в строке; потолок, который объявляет хранилище.
- **М11, урок 5** — [права по тому, кто звонит](../М11_Cluster/05-rights-by-who-is-calling.md): файл прав и сокеты ролей (заглянуть вперёд; здесь хватит таблицы выше).

## Чему научитесь

- Отличать «ACL отсутствует» от «ACL есть, но невыразим» — и видеть, что второе лечится раскладкой ключей.
- Выводить права из спеки и знать про каждое, кто его проверяет — а где не проверяет никто.
- Понимать, чего ACL не может дать в принципе, и что ставить туда вместо него.
- Видеть, почему «удалить всё, на что никто не ссылается» — неверно, и во сколько приёмов это чинится.
- Получать отсрочку из структуры, а не из меток времени, которых в контракте хранилища нет.
- Ставить необратимое действие **после** обратимого, чтобы проигранный CAS ничего не стоил.
- Писать тест, который ловит гонку внутри одного прохода, а не рядом с ним.

---

## Шаг 1 — Что можно сказать, когда имя воркера стоит первым

Шаблон права в курсе — это **ключ** или **префикс с одной звёздочкой в конце**, с `!` впереди — запрет. Так считает и `FileVariables` (урок 2), и файл прав демона:

```python
# A pattern: a key, or a prefix with one trailing `*`; with a leading `!` it denies what it names.
def _pattern(p) -> bool:
    if not isinstance(p, str):
        return False
    body = p[1:] if p.startswith("!") else p
    return bool(body) and "!" not in body and "*" not in body[:-1]
```

Положите heartbeat по ключу `<name>/<worker>/heartbeat` — имя воркера в **первом** сегменте после подсистемы — и попробуйте записать «воркеры пишут свои heartbeat'ы и больше ничего». Самый узкий шаблон, который их покрывает, — `testsub/*`, и он означает:

| ключ | что это значит |
|---|---|
| `testsub/w-9/heartbeat` | подделать чужой heartbeat: ёмкость, `headroom`, единицы как `running` |
| `testsub/snapshot/<любой>` | **писать снимок**, который читает слой выше (М12) |
| `testsub/blobs/<дайджест>` | подменить байты под существующим дайджестом |

Комментарий сказал бы «свой heartbeat», шаблон — вся подсистема.

## Шаг 2 — Почему это нельзя было сузить

И вот главное в уроке. Дело **не** в том, что шаблонам не хватает выразительности.

Имя воркера берётся в рантайме: `claim_slot()` выдаёт `w-1`. Файл прав — статический текст, сгенерированный до того, как кластер запустился (`python3 -m cluster rights` → `/etc/w2c/configstore-rights.json`, М11). А ключ устроен так:

```
testsub/<worker>/heartbeat
        ^^^^^^^^ первый сегмент — и он неизвестен заранее
```

Написать «может писать свой heartbeat и больше ничего» **нечем**: звёздочки в середине нет, а самый узкий префикс — вся подсистема.

Запреты не спасают. `testsub/*` плюс `!testsub/snapshot/*` и `!testsub/blobs/*` — это право **по исключению**: каждый новый каталог под подсистемой (`contenders/`, `used/`, `controller/pass`) становится воркерским по умолчанию, и забытый запрет — это выданное право. Право, которое открывается, когда о нём забыли, — не право.

Это не дефект ACL. Это дефект **раскладки ключей**. Довод «пусть объекты одного воркера лежат в одном каталоге» разумен ровно до тех пор, пока этот каталог никому не надо выдавать.

## Шаг 3 — Имя воркера уезжает в конец

```python
HEARTBEATS = "heartbeats"
```

```python
    def heartbeat_key(self, worker: str) -> str:
        return f"{self.name}/{HEARTBEATS}/{worker}"
```

Каталоги-сиблинги под подсистемой, **по одному писателю у каждого**:

```
testsub/heartbeats/<worker>        воркеры
testsub/contenders/<slot>/<box>    воркеры
testsub/used/<place>               воркеры
testsub/snapshot/<worker>          контроллер
testsub/controller/pass            контроллер
testsub/blobs/<digest>             консоль
```

И право становится выразимым: `testsub/heartbeats/*` — ровно heartbeat'ы, и больше ничего. Подделку соседнего heartbeat'а это не убирает — `w-1` и `w-2` в одном каталоге, — но радиус падает с «весь кластер плюс снимок домена» до «соседний воркер», а поверх уже работают эпохи и лизы.

**Попутно исчез фильтр, который несли все читатели.** Список `<name>/` возвращал бы heartbeat'ы вперемешку со снимком и блобами, и каждый читатель отбирал бы своё по суффиксу. Теперь:

```python
            # One prefix, no filter: `<name>/heartbeats/` holds heartbeats and nothing else.
            for key in self.objects.list(self.sub.heartbeats_prefix()):
```

Фильтр никогда не был смыслом — он был бы **ценой раскладки**. Читатель домена в М12 (`Cluster.heartbeats()`) перечисляет тот же префикс — листинг и `get`, без фильтра.

## Шаг 4 — Права на объекты выводятся из спеки

```python
    def acl_objects_worker(self) -> list[str]:
        """The workers write their own heartbeats, their claims to a name another instance holds, and the places
        they opened."""
        return [f"{self.name}/{HEARTBEATS}/*", f"{self.name}/{CONTENDERS}/*", f"{self.name}/{USED}/*"]

    …
    def acl_objects_controller(self) -> list[str]:
        """The controller publishes the snapshot shards — the only thing that leaves the cluster — and its pass report."""
        return [f"{self.name}/snapshot/*", f"{self.name}/{CONTROLLER_PASS}"]

    def acl_objects_console(self) -> list[str]:
        """The console stores the bytes of a `blob` field, beside the row that names them."""
        return [f"{self.name}/{BLOBS}/*"]
```

Рядом с `acl_worker()` в `Subsystem` (`contract.py`), а `acl_controller()` и `acl_console()` — в `SubsystemSpec`, из той же спеки. Ни слова о том, что за подсистема: имя приходит из спеки. На тестовой подсистеме платформы (`tests/testdata/testsub.subsystem.yaml`) выходит:

```
acl_objects_worker()      ['testsub/heartbeats/*', 'testsub/contenders/*', 'testsub/used/*']
acl_objects_controller()  ['testsub/snapshot/*', 'testsub/controller/pass']
acl_objects_console()     ['testsub/blobs/*']
```

**Контроллер пишет не только шарды, но и отчёт о проходе.** `pass_once` пишет `<name>/controller/pass` (`CONTROLLER_PASS = "controller/pass"` в `contract.py`; урок 11) — единственный объект, из которого `/metrics` берёт `<name>_units_unplaced` и последний проход. Список, который назвал бы только шарды, соврал бы о писателе каталога ровно там, где ошибка не видна: отчёт пишется, метрики читают, все списки сходятся друг с другом.

Кто эти списки **читает** — честно:

- **Уборка.** Блобы — каталог консоли (`acl_objects_console`), поэтому их собирает консоль (шаг 13): `host.py` так и говорит — «the blob sweep the console owns BECAUSE THE ACL SAYS SO».
- **Генератор прав хранилища в М11.** Из объектных списков право получают только ключи, которые спека объявила строками (`objects: {rows: […]}`), — `objects/<key>`; каждый другой объект — файл на сервере писателя, и ни одно право его не называет. Генератор пока живёт в пакете М11, `Source/cluster/rights.py`:

```python
def _rows(objects: list[str]) -> list[str]:
    """Of a list of object prefixes, the ones that are rows in the store: `objects/<key>` for the create-only keys."""
    return [OBJECTS + p for p in objects if is_row(p)]
```

У `testsub` строк среди объектов нет, и `_rows` от любого его списка пуст. Пример — в М10B: спека записей объявляет `objects: {rows: [used/*]}`, и из `acl_objects_worker()` её воркер получает в файле прав ровно `objects/rec/used/*`.

`acl_objects_controller()` и `acl_objects_console()` строк сегодня не содержат, и права по ним не выдаёт никто. Они — запись о том, **кто пишет**, и на ней стоят уборка и тест «никто не пишет объект, который файл» (шаг 5). Проверки, что объектные записи процессов совпадают с этими списками, в курсе нет — это упражнение 13.

## Шаг 5 — Тест, который сверяет файл прав с кодом

Строковые права записаны в двух местах: в коде (`acl_*` из спеки) и в файле, который читает демон. Второй в курсе не пишут руками — его генерирует `python3 -m cluster rights`, коммитят как `deploy/cluster/configstore-rights.json` и ставят как `/etc/w2c/configstore-rights.json` (`configstore.RIGHTS_FILE`). Между ними стоит тест М11, `tests/cluster/test_policies.py`, и его подсистемы — VMS: здесь это пример, механизм тот же для любой спеки.

Первое, что ему нужно, — семантика шаблона. Она одна у демона и у теста, `storemachine._hit`:

```python
def _hit(pattern: str, key: str) -> bool:
    return key == pattern or (pattern.endswith("*") and key.startswith(pattern[:-1]))
```

и закреплена отдельным случаем — шаблон без звёздочки — это **один ключ**, запрет сильнее права:

```python
    r = Rights.parse({"roles": {"c": {"write": ["objects/vms/snapshot/*", "vms/policy", "vms/*", "!vms/epoch/*"]}}})
    assert r.allows("c", "write", "objects/vms/snapshot/w-1") and not r.allows("c", "write", "objects/vms/snapshot")
```

Дальше — проверки, и они разной силы.

**Файл — это то, что генерирует спека сейчас.** `test_the_committed_file_is_what_the_spec_generates`: правка руками или спека, изменённая без перегенерации, падают здесь.

**В обе стороны против списков кода, и ни одного права на объект-файл.** `test_every_write_grant_is_one_the_code_asked_for_and_every_one_it_asked_for_is_there`:

```python
    got = {role: set(g["write"]) for role, g in doc()["roles"].items()}
    assert got == _expected_writes()
    for role, g in doc()["roles"].items():
        assert set(g["delete"]) == set(g["write"]), role                         # a role deletes what it writes
        assert all(not p.startswith(OBJECTS) or is_row(p[len(OBJECTS):]) for p in g["write"]), role
```

Равенство множеств — это обе стороны сразу: нет ни права, которого код не просил, ни просьбы без права. Именно его не прошло бы право на всю подсистему из шага 1 — `objects/vms/*` у воркера VMS.

**Никто не пишет того, что ему не положено** — по именам, `test_nothing_writes_what_it_has_no_business_writing`. В том числе ни одна роль — объект, который файл:

```python
    for role in r.roles:
        denied += [(role, OBJECTS + k) for k in ("vms/heartbeats/w-1", "vms/snapshot/w-1", "vms/controller/pass",
                                                 "platform/resources/srv-a/heartbeat")]
```

**Самая сильная: всё, что процессы делают, разрешено.** Списки кода — тоже ручная работа: контроллер может писать отчёт, который не назван ни в одном списке, и все сверки «файл против списков» согласятся. Поэтому `test_every_write_the_code_makes_is_granted` прогоняет каждую сцену стенда М11, где каждый процесс ходит через сокет своей роли с правами этого файла, и проверяет **каждую** запись и удаление, которые процесс сделал:

```python
    for role, made in sorted(writes.items()):
        for action, key, status in sorted(made):
            if status == 403:
                refused.append(f"{role}: {action} {key}")
            if not r.allows(role, action, key):
                outside.append(f"{role}: {action} {key}")
```

Его брат, `test_every_row_the_code_reads_is_granted`, делает то же с чтениями и листингами.

## Шаг 6 — Чего ACL не даёт, и что ставить вместо него

```python
    def blob(self, d: str, check_digest: bool = True) -> bytes | None:
        data = self.objects.get(self.sub.blob_key(d))
        if data is None or not check_digest:
            return data
        return verify(d, data)
```

Дайджест в ключе делал его неизменяемым **по договорённости**. Теперь — проверяемо:

```python
def verify(d: str, data: bytes) -> bytes:
    """`data` if it hashes to `d`; otherwise `BlobMismatch`. Never a silent pass."""
    actual = digest(data)
    if actual != d:
        raise BlobMismatch(f"{d}: the bytes stored there hash to {actual} — "
                           f"the object was replaced by someone who could write that key")
    return data
```

**Адресация по содержимому — это обещание; обещание, которое никто не проверяет, — это комментарий.**

И вот в чём разница классов. ACL — утверждение о том, **кто написал** байты. Проверка дайджеста — утверждение о том, **что это за** байты. Второе сильнее и держится там, где первое не держится вовсе:

- писатель, которому никто не мешает писать, — на коробке любой член `w2c-store`, в М11 любой процесс на сервере, где лежит файл;
- хранилище, доступное шире, чем задумано (`OBJECTS=s3+…` с общим бакетом);
- объект, скопированный между сторами или между серверами;
- обрезанный объект и подгнивший диск — тут ACL не при чём вообще.

Проверка стоит на **чтении**, где байты сейчас пойдут в дело. Проверять только на записи — значит снова поверить писателю, то есть ровно тому, что заменяем. В М11 тот же `verify` стоит ещё в двух местах: ресурс хеширует копию блоба от соседа до того, как её оставить (`take_blob`), а `ClusterObjectStore.get` проверяет копию своего сервера и при несовпадении читает с другого:

```python
        if is_blob_key(key):
            data = self.local.get(key)
            if data is not None:
                try:
                    return verify(key.rsplit("/", 1)[1], data)
                except BlobMismatch as e:
                    log.error("objects: this server's copy of %s is not the blob (%s): read from another server", key, e)
```

Тест: `test_blobs.py::test_a_poisoned_blob_is_caught_on_the_read_and_not_trusted`.

## Шаг 7 — `delete` — у стора, политика — у вызывающего

```python
    # Removes one object; `True` if it was there. A capability of the STORE — a store can either delete or
    # it cannot — and deliberately not "delete, but only under `blobs/`": that would be policy welded into
    # the seam, and policy lives with the caller that has it (`SpecController.sweep_blobs`) …
    def delete(self, key: str) -> bool: ...
```

Соблазн — сделать `delete_blob(digest)` и «обезопасить» шов. Это тот же ход, от которого курс ушёл в уроке 19: потолок объявляет стор, а решает вызывающий. Стор умеет удалять или не умеет; **что именно** можно удалять — знание уборщика.

А **кому** можно — смотря что удаляют. Строку — по файлу прав: роль удаляет то, что пишет (генератор кладёт в `delete` то же, что в `write`), а эпоху и `domain/*` чужими ролями не удаляет никто, что бы ни было в файле (`Rights.allows`, первая строка). Объект — ничьё знание: на коробке файл удалит любой член `w2c-store`, а дверь ресурса в М11 удаляет блоб по просьбе любого, кто до неё дотянулся, — двери между процессами там пока закрывает только сеть кластера (М11, урок 5, шаг 7). Что `delete` объекта вызывает один уборщик — свойство кода, а не запрет, и сказать это стоит именно так.

Инвариант урока 4 переписан честно, а не вычеркнут:

```
# - `delete` exists, and exactly one caller uses it: the blob sweep (…). Everything else in the
#   platform still relies on objects NEVER going away — a stale heartbeat simply ages and readers filter by
#   `ts`, and a worker restarting reads the heartbeat its previous instance left to measure its own
#   failover. That is not an accident waiting to be tidied up: sweep the heartbeats and the measurement
#   goes with them. The rule is therefore not "nothing deletes" any more but the narrower and truer one:
#   an object is deleted only by a caller that can prove nothing refers to it, and only the blob sweep can.
```

## Шаг 8 — Почему очевидная реализация неверна

Объект пишется **раньше** строки, которая его называет (урок 19). Уборка, попавшая между этими двумя записями, видит блоб без ссылок и удаляет байты, на которые строка сейчас сошлётся. Оператор загрузил маску, всё прошло без ошибок, а единица не стартует.

Поэтому **замечать и удалять — разные проходы**:

```python
    #   mark   nothing is deleted. The digests that no row names are written to `<name>/sweep` with the
    #          time. A blob created after this moment is not on the list, which is where the grace period
    #          comes from — no timestamps on objects required, …
    #   sweep  one pass later, and only after `grace`: the marked digests are checked AGAIN, the decision is
    #          written by CAS on the index just read — the doomed digests, `state: deleting` — and only then
    #          are the objects removed, each one read back from the row the moment before.
```

Блоб, появившийся между проходами, **в списке не лежит** — отсрочка получается из структуры. Метки времени на объектах не нужны, и это существенно: в контракте `ObjectStore` их нет — `put`, `get`, `list`, `delete`, и всё.

## Шаг 9 — Порядок действий — и есть всё доказательство

```python
        self.vars.put(key, {"at": str(now), "digests": json.dumps(doomed), "state": "deleting"}, cas=idx)   # Conflict here deletes nothing
        deleted = 0
        for d in doomed:
            items, idx = self.vars.get(key)                                 # still doomed? `put_blob` takes a digest off this list
            if d not in _sweep_list(items)[0]:
                continue
            data = self.objects.get(self.sub.blob_key(d))
            if data is None or not self.objects.delete(self.sub.blob_key(d)):
                continue
            items, idx = self.vars.get(key)                                 # …and after: taken off meanwhile is being uploaded
            if d not in _sweep_list(items)[0]:
                getattr(self.objects, "put_durable", self.objects.put)(self.sub.blob_key(d), data)
                continue
            deleted += 1
        try:
            self.vars.put(key, {"at": str(now), "digests": "[]"}, cas=idx)
        except Conflict:
            pass                                                            # a digest left the list under us: the rest wait for the next pass
```

Три слоя, и каждый закрывает окно, которое оставил предыдущий.

**Сначала обратимое — и под CAS.** Решение (`state: deleting`, `digests` — обречённые) записывается по индексу, прочитанному при пометке. Проигранный CAS означает «пока мы думали, решение кто-то опроверг», и на этот момент **не удалено ни одного объекта**. Переставьте запись решения и удаление — и то же стечение обстоятельств уничтожит байты.

**Решение остаётся на строке, пока байты уходят.** Если бы строка очищалась сразу после решения, `put_blob` помеченного дайджеста в секунды удаления нашёл бы пустой список, ничего бы с него не снял — и его байты ушли бы под строкой, которая вот-вот их назовёт. Поэтому строка держит решение, перед каждым `delete` перечитывается одним `get`, и дайджест, который `put_blob` успел снять, пропускается. Тест: `test_sweep.py::test_a_blob_uploaded_again_while_the_sweep_is_deleting_is_not_deleted`.

**Байты читаются до удаления, строка — после.** Между последним «всё ещё обречён» и `delete` остаётся окно в два вызова: `put_blob` снимает дайджест и пишет объект, а уборщик его удаляет. Закрыто тем, что ключ блоба — дайджест его байтов: если дайджест за это время ушёл со списка, объект **кладётся обратно** — те же байты под тем же ключом, в каком бы порядке ни легли восстановление и загрузка. Тест: `test_sweep.py::test_an_upload_between_the_sweepers_last_look_and_its_delete_is_put_back`.

Очистка — последним CAS; проигранная очистка оставляет остаток следующему проходу. Строка в `deleting` читается как помеченная, так что уборщик, умерший на середине, достраивается следующим.

## Шаг 10 — Гонка, которую закрывает `put_blob`

Тот же дайджест можно загрузить для второй единицы, пока копия первой помечена. Тогда помеченный дайджест — ровно тот, который строка сейчас назовёт:

```python
        # These exact bytes may be sitting on the sweep's list right now — the same mask uploaded again
        # for a second unit, while the copy the first unit stopped naming is marked for collection.
        # Taking it off the list makes the sweep's own CAS fail, and a sweep that loses that CAS deletes
        # nothing at all. The alternative is a lock, for a window two store calls wide.
        key = self.sub.sweep_key()

        def off_the_list(it):
            marked = _sweep_list(it)[0]
            return {**it, "digests": json.dumps([x for x in marked if x != d])} if d in marked else None

        self.write(key, off_the_list)                 # by CAS, tried again on a conflict: the sweeper writes this row too
```

Обратите внимание, что здесь не понадобилось ничего нового: **это история согласованности самой платформы**, применённая к её собственной бухгалтерии. И `put_blob` пишет строку уборки — значит, право на `<name>/sweep` нужно тому, кто загружает блобы: консоли (шаг 14).

## Шаг 11 — Уборка ограничена, потому что её бухгалтерия — строка

```python
    SWEEP_LIMIT = 64
    SWEEP_GRACE = 300.0
```

`<name>/sweep` — строка, а над строкой стоит потолок, который объявляет хранилище (урок 19). У `configstore` это `MAX_VALUE`, 512 КиБ: дайджест весит 71 байт, с кавычками и запятой в JSON-списке — 75, то есть около семи тысяч кандидатов; хранилище, объявившее меньше, упрётся раньше. Значит, уборка обязана брать не больше `limit` за проход — как `ensure_home(1)`. Правило, записанное в уроке 19, применяется к тому, что написано под ним. Тест: `test_sweep.py::test_the_sweep_is_bounded_because_its_own_bookkeeping_is_a_row`.

## Шаг 12 — Тест, который ловит гонку изнутри прохода

Три первых теста пишутся легко: пометил — не удалил; появился между проходами — выжил; перезалили помеченный — уборка отменилась. Четвёртый — про порядок из шага 9 — так не пишется: снаружи прохода переставленные строки ведут себя одинаково.

Нужно вмешаться **в середине**:

```python
    real = ctl.blobs_referenced
    def racing():
        ctl.blobs_referenced = real                       # once, in the middle of the pass
        # The real interleaving: the OBJECT is written and the row naming it is still in flight, so the
        # digest is genuinely unreferenced at the re-check — and the only thing between it and deletion
        # is that `put_blob` took it off the list, which the CAS is about to notice.
        other.put_blob(MASK_A)
        return real()
    ctl.blobs_referenced = racing
```

`blobs_referenced` вызывается после чтения строки и до записи решения — ровно там, где живёт гонка. Тест (`test_sweep.py::test_the_decision_is_cleared_before_anything_is_deleted`) ждёт `Conflict` от записи решения и байты на месте.

> **Ловушка, в которую легко попасть.** Сделайте в `racing()` не `put_blob`, а `put_blob` + `update` — и тест пройдёт **одинаково при обоих порядках**: строка уже называет дайджест, на перепроверке он оказывается сославшимся, `doomed` пустеет, и удалять нечего. Утверждение «порядок — это всё доказательство» стоит в комментарии, а проверяет его тест, который его не проверяет. Ловится это только снятием: переставьте строки — и посмотрите, покраснеет ли тест. Если нет — он проверяет что-то другое.

## Шаг 13 — Кто это запускает

Консоль — потому что `blobs/` принадлежит ей (`acl_objects_console`, шаг 4), и строка уборки `<name>/sweep` — в `acl_console()`, а не в `acl_controller()`. В М11 это уже не соглашение: контроллеру, пришедшему через свой сокет записать решение уборки, демон ответит `403`.

Цикл — платформенный, в `w2cplatform/host.py`, и его запускает консоль платформы (`python3 -m w2cplatform console`) для каждой спеки, которую она обслуживает (`list(ctls.values())`):

```python
def sweep_turn(controllers) -> None:
    for c in controllers:
        def sweep(c=c):
            r = c.sweep_blobs()
            if r["deleted"]:
                log.info("swept %d blob(s) nothing names in %s", r["deleted"], c.spec.name)
        step(c, "the blob sweep", "sweep", sweep, f"the blob sweep failed in {c.spec.name} — nothing is reclaiming its blobs")


def sweep_loop(controllers, every: float = 60.0) -> None:
    while not stop.is_set():
        sweep_turn(controllers)
        stop.wait(every)
```

Свой шаг и своя строка лога — урок 19, применённый **до** того, как ошибка сделана второй раз: `step` говорит об отказе один раз за полосу и «works again», когда отпустило. Тест: `test_sweep.py::test_the_console_process_actually_runs_the_sweep`. Спека без поля `blob` не метит, не решает и не пишет строку (`test_a_subsystem_with_no_blob_field_is_not_swept_at_all`) — у `testsub` такого поля нет, и уборка проходит по нему впустую.

И две метрики, устроенные так, чтобы их можно было опрашивать раз в пятнадцать секунд:

```python
        # The sweep's backlog, for subsystems that have blobs to collect. Two cheap reads — a prefix
        # listing and one row — deliberately NOT `blobs_referenced()`, which walks every unit's row: a
        # gauge scraped every fifteen seconds must not cost a full scan of the configuration.
```

`<sub>_blobs_total` и `<sub>_blobs_marked` — только у спек с полем `blob`.

## Шаг 14 — Право на учёт уборки, и где его проверяют

```python
               f"{self.name}/sweep",                                                          # what the blob sweep marked, and when
```

Строка в `acl_console()`. Удалять объект право хранилища не даёт и не может: удаление блоба — не строка, его нет в файле прав. Право здесь одно — на **решение** уборки, и оно у консоли.

Тест из шага 5 сверяет права **всех** ключей, которые роль пишет, а не тех, ради которых его писали. Это важно ровно здесь: строку уборки и `platform/drain` — «эта машина сейчас остановится», которую консоль пишет для всех подсистем сразу (урок 17), — проверка одних объектных ключей не увидела бы вовсе, а без права на кластере консоль получила бы `403` на первом же проходе уборки, а плановая остановка — отказ: машина, которую оператор собирался вывести аккуратно, ушла бы молчанием.

Вывод, который стоит унести: проверка, написанная наполовину, находит половину. Направление «всё, что код пишет, разрешено» применяется ко **всем** ключам — а у объектов, где проверяет не хранилище, его ещё предстоит написать (упражнение 13).

## Что может пойти не так

- **Дописали ACL в `FsObjectStore` и успокоились.** Клиентская проверка — подсказка; и это второе место, где записано правило, которое разойдётся со списками спеки так же, как разошёлся бы с ними файл прав, если бы его вели руками.
- **Сравнили шаблон со строкой.** `objects/vms/snapshot` и `objects/vms/snapshot/*` выглядят одинаково, пока не проверишь их на конкретном ключе.
- **Написали только первое направление.** «Всё, что нужно, разрешено» — это половина; вторая половина, «и больше ничего», и есть то, ради чего права существуют.
- **Сузили право запретами.** `!` закрывает то, что вы вспомнили; каталог, о котором забыли, остаётся открытым.
- **Решили, что объекты защищены файлом прав.** Файл называет только объекты-строки (`objects.rows`); heartbeat'ы, шарды, отчёт прохода и блобы — файлы, и их пишет тот, кто до них дотянулся.
- **Проверили дайджест на записи.** Записывающий и так знает, что кладёт. Смысл — на чтении.
- **Решили, что имя воркера можно подставить в файл прав.** Оно появляется после старта кластера; файл существует до.
- **Удалили в том же проходе, где заметили.** Это гонка с `put_blob`, и выглядит она как «оператор загрузил маску, ошибок нет, единица не стартует».
- **Переставили запись решения и удаление.** Проигранный CAS начинает стоить байтов.
- **Очистили строку до удаления.** `put_blob` найдёт пустой список и ничего с него не снимет.
- **Забыли снять пометку в `put_blob`.** Остаётся узкое окно шириной в два вызова, и закрывать его придётся блокировкой.
- **Сделали уборку неограниченной.** Её собственная строка упрётся в потолок, и уборка сломается на том, что убирает.
- **Подмели heartbeat'ы «заодно».** Измеренное переключение исчезает, и `builds()` перестаёт отвечать, что здесь вообще работает.
- **Написали тест на гонку снаружи прохода.** Он пройдёт при любом порядке, и вы узнаете об этом только снятием — если повезёт.

## Итог

Вопрос «нужен ли ACL объектному хранилищу» распался на три разных, и ответы разные.

**Нужен ли механизм в клиенте платформы?** Нет. Проверка, которую процесс может не вызвать, ничего не защищает. Защищает тот, кто стоит между процессом и данными и знает, кто звонит: у строк это демон `configstore`, который узнаёт роль по сокету и спрашивает файл прав до применения. У объектов такого нет ни на коробке, ни в М11, и урок не делает вид, что есть.

**Можно ли хотя бы назвать писателя каждого объекта?** Да, и это оказалось не вопросом ACL. Префикс, который нельзя ограничить шаблоном, — это дефект раскладки ключей. Имя воркера стоит в последнем сегменте, каждый каталог подсистемы получил одного писателя, и права стали выразимыми: `acl_objects_worker()`, `acl_objects_controller()`, `acl_objects_console()` выводятся из спеки рядом со строковыми. Попутно из каждого читателя ушёл фильтр по суффиксу. Генератор прав М11 из этих списков выдаёт право только объектам-строкам, а тест М11 сверяет файл прав с кодом в обе стороны и с каждой записью стенда.

**Нужно ли что-то, чего ACL не даёт?** Да — проверка дайджеста. Она про другое утверждение и держится там, где никакой ACL не держится — а у объектов курса, где ACL не стоит вовсе, это и есть защита.

Уборка понадобилась одному классу объектов из трёх, и разница не в том, что блобы «мусорнее», а в том, что их **ключ адресуется содержимым**: новый набор байтов — новый вечный ключ. У heartbeat'а ключ переиспользуется и его устаревшая версия работает на измерение; у снапшота ключ на воркера. Поэтому `delete` появился у стора, а вызывает его ровно один вызывающий — и про это честно сказано, что это свойство кода, а не запрет.

Само же решение оказалось не про удаление, а про **разнесение во времени**: заметить и убрать нельзя в один приём, потому что объект пишется раньше строки. Отсрочка вышла из структуры — кандидат, которого нет в списке, уже поэтому в безопасности, — а не из меток времени, которых в контракте хранилища нет. Обратимое действие поставлено перед необратимым, чтобы проигранный CAS ничего не стоил; решение держится на строке, пока байты уходят; и `put_blob` этот CAS умеет проиграть нарочно.

И два побочных урока, оба про тесты. Утверждение, которое проверяет тест, не проверяющий его, — хуже отсутствия теста: оно выглядит проверенным. А проверка, написанная для одной половины ключей, найдёт дефекты только в этой половине.

## Упражнения

1. **Дайте воркеру VMS `objects/vms/*`** в генераторе (`cluster/rights.py`), перегенерируйте файл и посмотрите, какие проверки шага 5 падают и почему разные.
2. **Добавьте подсистему с блобами** и посмотрите, сколько строк файла прав придётся написать руками. Ноль — его генерирует `python3 -m cluster rights`. А сколько строк **кода** придётся поправить в `cluster/rights.py`, и что должно измениться, чтобы генератор брал спеки из каталога, а не по именам?
3. **Подделайте heartbeat соседа** из теста: запишите `testsub/heartbeats/w-2` процессом `w-1` и проследите, куда это доедет. Что останавливает такого воркера дальше по цепочке?
4. **Уберите `verify` и подмените блоб.** Через сколько шагов это заметит человек? А с `verify`?
5. **Прочитайте `cluster/rights.py`** и найдите, что генератор берёт не из спеки, а из списков, названных по имени (`SPECS`, `WORKER_ACL`, `WORKER_OBJECTS`). Что из этого платформа могла бы вывести сама — и что принадлежит подсистеме по праву?
6. **Проверьте `platform/resources/<server>/heartbeat`** по тому же критерию: выразимо ли его право, и почему у него имя в середине никого не смущает.
7. **Уберите отсрочку** (`grace=0`) и попробуйте воспроизвести потерю блоба. Сколько попыток нужно и от чего это зависит?
8. **Переставьте запись решения и удаление** и посмотрите, какой тест падает. Потом уберите из него `other.put_blob` — и объясните, почему он снова проходит.
9. **Посчитайте потолок строки `sweep`** при дайджесте в 71 байт для `configstore` и для хранилища с потолком 64 КиБ. Какой `limit` вы бы поставили и почему не больше?
10. **Напишите уборку для `platform/resources/<server>/heartbeat`** — единственного ключа, который действительно растёт с оборотом железа. Что должно быть верно, чтобы её можно было запустить?
11. **Перенесите уборку в контроллер** и посмотрите, на чём она сломается. Что именно об этом говорит файл прав — и чего он не говорит?
12. **Придумайте порог** на `<sub>_blobs_total` и `<sub>_blobs_marked`. Что означает растущий `marked` при неподвижном `total`?
13. **Напишите проверку объектных записей:** на стенде перехватите каждый `put` и `delete` объекта и убедитесь, что ключ лежит под `acl_objects_*` роли, которая его пишет. Что она найдёт, если из `acl_objects_controller()` убрать `controller/pass`?

## Что дальше

Модуль закончен. Дальше — **М11**: строки уходят в реплицированное хранилище, и права из спеки проверяет демон по сокету роли ([урок 5](../М11_Cluster/05-rights-by-who-is-calling.md)); объекты остаются файлами — теперь на сервере писателя, читаемыми через ресурс ([урок 6](../М11_Cluster/06-what-stays-on-the-server.md)), — и блоб там проверяется дайджестом на каждом чтении, а уборщик удаляет его на каждом сервере, который ответил.

# Урок 1 — VMS на домене: вклад подсистемы

**Модуль:** М12B — DomainVMS: VMS на домене платформы
**Вы напишете:** раздел `domain:` в `vms.subsystem.yaml` и `rec.subsystem.yaml`, в котором видеопродукт говорит домену всё, что домену о нём нужно знать: как зовут камеру во всём домене, что показывать в общем виде, какие поля пускать в правку, какие книги держатель пишет для каждого члена, что он хранит для всего домена, какие токены подписывает. И воркер `domainpart`, который у держателя пишет эти книги своими правами и просит токены у подписывающего. Ни одного крючка: платформа читает объявления и переносит объявленное, не зная, что в нём.
**Время:** ~80 минут.

## Зачем этот урок

[М12A](../М12A_Domain/README.md) построил домен платформы: каталог каталогов, держатель со сроком, подписывающий, агент, который уносит домой своё, дверь держателя, общие настройки, тревоги, перенос. В нём нет ни камеры, ни записи, ни приёмника. Он собирается и проверяется на `testsub` (`tests/test_domain_platform.py`), а `w2cplatform/domain` не импортирует `vms` (тест границы `tests/test_boundary.py::test_the_platform_crosses_the_boundary_nowhere_but_where_the_debt_says_and_the_debt_only_shrinks`).

Видеопродукту над кластерами нужно своё: поток камеры из другого кластера (урок 2), камера, до которой не дотянуться (урок 3), цепочка «объект — ретранслятор — центр» (урок 4). Всё это — строки у держателя, которые кто-то пишет, члены уносят домой, а держатель хранит и переносит. Вопрос урока: **как подсистема даёт это домену, если домен о ней ничего не знает?**

Очевидный ответ — объект подсистемы с методами, который домен зовёт: «опубликуй книги», «какие префиксы твои», «какие маршруты», «какие виды токенов». Это крючок, и ADR 0002 его запрещает: смысл крючка уходит в одно из трёх мест — в спеку, в воркер или в страницу. Для домена это решено отдельно (ADR 0010): **что** подсистема даёт — декларации раздела `domain:` её спеки; **работа** — воркер подсистемы у держателя со своими правами на `domain/<sub>/…`; **показ** — страница продукта. Домен служба платформы, вклад подсистемы лежит под `domain/<sub>/`, а секреты домена запечатаны (ADR 0024).

> **Что проверяется без железа.** Всё. Платформенная половина — на `testsub`, без единой строки VMS: `tests/test_domain_platform.py`. Половина VMS — `tests/domainvms/`: каждый ключ, который VMS пишет на домене, попадает в объявленную семью (`test_domain_secrets_vms.py`), член получает через дверь только своё, ретранслятор отдаёт камере только её, агент не трогает ключ подписывающего; дверь воркера с `/metrics` (`test_lesson17_chain.py`). Юнит воркера и глагол `python3 -m vms domainpart` — `tests/test_deploy_units.py`.

## Что нужно знать заранее

- **М10A, урок 9, шаг 20** — [словарь спеки](../М10A_Platform/09-SubsystemSpec.md): закрытое множество ключей, отказ при загрузке.
- **М12A, урок 3** — [дверь держателя](../М12A_Domain/03-the-api-and-what-it-refuses.md): список единиц, пересылка правки владельцу.
- **М12A, урок 4** — [агент](../М12A_Domain/04-who-may-call-it.md): несёт строку `<путь>/<кластер>` в `<путь>`.
- **М12A, урок 12** — [общие настройки](../М12A_Domain/12-shared-settings-without-a-database.md): подписанный документ за указателем.
- **М12A, урок 14** — [держатель на одном узле](../М12A_Domain/14-a-domain-holder-on-one-node.md): резервная копия и перенос.

## Чему вы научитесь

1. Сказать, чего домен платформы не знает о VMS, и где лежит то, что он знает.
2. Объявить, как камера называется во всём домене, что показывает общий вид и какие поля пускает дверь держателя.
3. Объявить книги, которые держатель пишет для каждого члена, и строки, которые он держит для всего домена.
4. Объявить виды токенов, которые подписывающий выпускает воркеру, и объяснить, почему в токене нет прав.
5. Запустить воркер VMS у держателя: его роль, слот, пульс, дверь, сокет токенов.
6. Назвать тесты, которые держат границу.

---

## Шаг 1 — Что домен знает о VMS: один раздел спеки

Весь вклад VMS в домен — это раздел `domain:` трёх спек: `vms`, `rec` и `auto`. Видеопродукта в нём нет, есть имена и списки:

```yaml
# vms.subsystem.yaml
domain:
  ref: ref
  view: [name, enabled]   # what the holder knows of a camera: its name, and whether it is on (domain.edit)
  edit: [enabled]
  books: [sources, primaries, poll, upstream, asks]
  kept: [crossings, roads]
  tables: [crossings]
  tokens:
    stream: {lifetime: 86400, claims: [aud, ref]}
    ask: {lifetime: 86400, claims: [aud, ask, by, acts, up]}
  shared: [folders, alarms, events_retention_days]
  keys:
    - {id: roads, keys: [domain/vms/roads]}
    - {id: crossings, keys: [domain/vms/crossings]}
    - {id: sources, keys: [domain/vms/sources], prefix: domain/vms/sources/}
    ...
    - {id: worker, keys: [domain/vms/worker]}
```

```yaml
# rec.subsystem.yaml
domain:
  reports: [ingest, polled/]
  witness: {report: polled, member_field: cam}
  edit: [enabled, retention_days]
```

```yaml
# auto.subsystem.yaml
domain:
  shared:
    - name: scenarios                  # the scenarios between cameras: a document the domain holds whole
      type: json
      schema: …
```

Читает это платформа, в одном месте — `w2cplatform/domain/declared.py`. Каждый список берётся из каталога загруженных спек в момент вопроса: спеку, загруженную позже, видит следующий проход.

```python
def books() -> list[str]:
    """Every book a member carries home: `domain/<sub>/<book>` (the holder keeps one per member, `…/<member>`)."""
    return [f"{s.domain_prefix}{b}" for s in specs() for b in s.domain.books]


def kept() -> list[str]:
    """Every row a subsystem keeps at the holder for the whole domain: `domain/<sub>/<name>`, and every family of them,
    `domain/<sub>/<name>/` — a prefix, as every reader of this list takes it (`term.exported`, `rights.agent_denials`)."""
    return [f"{s.domain_prefix}{k}" for s in specs() for k in s.domain.kept]
```

Префикс даёт платформа: `domain/<sub>/` (`SubsystemSpec.domain_prefix`), у VMS — `domain/vms/`. Строк домена вне своего префикса подсистема не называет: семья ключа под чужим префиксом — отказ при загрузке (`DomainSection._families`).

Загрузчик проверяет раздел целиком, как любой раздел спеки (ADR 0012): `ref` и `view` — поля снимка, потому что домен читает единицу только из снимка; имя не может быть и книгой, и хранимой строкой («одного писателя строки, одна форма»); таблица — только из `kept`; вид токена `person` — платформенный; поле `edit` — поле единицы и не секрет. Тест: `test_domain_platform.py::test_a_domain_section_that_names_what_is_not_there_is_refused_when_the_spec_loads`.

## Шаг 2 — Камера во всём домене: `ref`, `view`, `edit`

**`ref: ref`** ставит камеры VMS в каталог домена: камеру ищут поперёк кластеров по полю `ref` её строки (`declared.directory`). У `rec` поля `ref` нет, и записи в каталоге домена нет — запись принадлежит кластеру записи, а домен знает камеру, которую она пишет.

От этого объявления у держателя появляются маршруты, которых никто не писал руками. Дверь держателя разбирает `/domain/<sub>/<name>` по декларациям (`console.Console.route`): имя строк спеки (`rows: cameras`) у подсистемы каталога — список её единиц, имя из `tables` — таблица.

    GET  /domain/vms/cameras?q=&page=&size=&cluster=   камеры всех членов из представления для чтения, с возрастом
    PUT  /domain/vms/cameras/<ref>                     правка, пересланная консоли кластера-владельца
    GET  /domain/where/<ref>                           где камера, и полон ли ответ
    GET  /domain/vms/crossings                         таблица, которую VMS держит у держателя (шаг 4)

**`view: [name, enabled]`** — поля, которые общий вид домена (`domain/view`, его отдаёт `GET /domain`) показывает рядом с платформенными: кластер, сервер, воркер, фаза, возраст. Единица вида — `{sub, id, ref, cluster, worker, server, phase, age, state, view: {name, enabled}}` (`ReadView.doc`). Страница рисует дерево домена из этого документа и ни о чём не спрашивает членов.

**`edit: [enabled]`** — что дверь держателя пускает в правку камеры члена. Камеру можно включить и выключить через домен, а имя, папки, метки и сроки остаются за консолью её кластера (ADR 0031). Любое другое поле — 400 со списком, раньше, чем вопрос дойдёт до члена или правка ляжет храниться для молчащего кластера:

```python
        allowed = edit_fields(sub)
        if not allowed:
            raise ApiError(400, f"{sub}'s spec declares no domain.edit: the domain's door lets no field of its units "
                                f"into an edit — they are edited in their own cluster")
        bad = sorted(k for k in fields if k not in allowed)
```

У `rec` объявлено `edit: [enabled, retention_days]` — как у продукта. Дверь курса правит только единицы каталога, а у записи нет `ref`, поэтому маршрута для неё нет; объявление готово к тому дню, когда он появится. Тест на `testsub`: `test_domain_platform.py::test_an_edit_through_the_domains_door_carries_only_the_fields_its_spec_lets_through`.

## Шаг 3 — Книги: строка на каждого члена

**`books: [sources, primaries, poll, upstream, asks]`** — строки, которые у держателя лежат по одной на члена, `domain/vms/<книга>/<член>`, а агент члена уносит домой как `domain/vms/<книга>`. Что в них — дело VMS и следующих уроков:

| Книга | Для кого | Урок |
|---|---|---|
| `sources` | кластер записи: где последний раз видели камеры других кластеров, которые он пишет | 2 |
| `primaries` | кластер камеры: кто её пишет, пишется ли, куда толкать | 2, 3 |
| `poll` | толкающая камера, которую никто не пишет: приёмник, который она опрашивает | 3 |
| `upstream` | ретранслятор: приёмник центра по каждой камере | 4 |
| `asks` | камера-триггер сценария: кого и какими дорогами она может просить | 3, 4 |

Платформа несёт их, не читая. Агент члена спрашивает дверь держателя `GET /api/carry/<кластер>`, подписав вопрос ключом члена, и получает свои строки — общие и `<путь>/<кластер>` из списка, который собирается из объявлений:

```python
def per_cluster() -> tuple[str, ...]:
    return (*PLATFORM_PER_CLUSTER, *declared.books())
```

Чужой книги член не видит и не может увидеть: в хранилище держателя он не читает ничего (`w2cplatform/domain/carry.py`). Секрет в книге — поле, чьё имя кончается на `_secret`, наверху строки или внутри JSON-объекта, который лежит в её значении, — платформа находит по форме, не зная, зачем оно. У держателя он запечатан его кольцом, в дороге — ключом члена (X25519), у члена — кольцом члена. У VMS это суточный токен в записи книги, `token_secret` (`vms/domainpart/keys.py`). Тест: `test_domain_secrets_vms.py::test_nothing_is_open_in_any_store_of_three_clusters_and_the_camera_still_pushes` — ни одного токена в открытую ни в одном хранилище трёх кластеров, и камера всё равно толкает.

Сторона VMS называет эти строки теми же именами и ничем другим. Книга, переименованная в спеке и не переименованная здесь, падает при импорте, а не в хранилище члена:

```python
def _book(name: str) -> str:
    if name not in SPEC.domain.books:
        raise ValueError(f"vms.subsystem.yaml declares no book {name!r} (domain.books: {list(SPEC.domain.books)})")
    return SPEC.domain_prefix + name

SOURCES_PATH = _book("sources")
...
CROSSINGS = _kept("crossings")
```

## Шаг 4 — Что держатель хранит для всего домена: `kept`, `tables`, `names`

**`kept: [crossings, roads]`** — строки, которые VMS держит у держателя для домена целиком, `domain/vms/<имя>`:

- `domain/vms/crossings` — какой кластер пишет какую камеру другого кластера (урок 2);
- `domain/vms/roads` — память дорог: камеры, переведённые на «камера толкает», потому что регистратор не смог забрать поток (урок 3).

Это решения, и второй раз их так же не принять. Поэтому они уходят в резервную копию держателя вместе с тем, что решила сама платформа, и перенос домена их восстанавливает: список копии — платформенные строки плюс объявленные (`term.exported`). Книги в копию не идут: следующий проход воркера построит их заново. Имя с `/` на конце было бы **семейством** строк, `domain/<sub>/<имя>/<строка>`, — у VMS курса семейств нет. Тест на `testsub`: `test_domain_platform.py::test_the_holder_backs_up_what_a_spec_keeps_and_a_move_restores_it`.

**`tables: [crossings]`** — какие из хранимых строк дверь держателя отдаёт на чтение: `GET /domain/vms/crossings`, и в общем виде — `tables["vms/crossings"]` (его кладёт проход подписывающего, `Holder.tables`). Что значит строка таблицы, знает страница продукта; дверь отдаёт её как хранит.

**`names`** — семейство хранимых строк, чьи строки — субъекты грантов рядом с людьми домена (`{<семейство>/: {exclusive_with: domain/users, grant: <право>}}`, ADR 0031). Человек не заводится под именем такой строки, строка не пишется под именем человека, грант субъекту не шире `grant`, и проверяет это платформа на каждой записи хранилища держателя (`declared.guarded`). У VMS курса учёток RTSP нет, и `names` в его спеке нет; ADR 0031 называет форму продукта — `stream-clients/`. Пример с этим объявлением — `testsub` (М12A).

Всё, что объявлено в `books` и `kept`, — строки держателя. Агенту, который на каждом члене пишет `domain/*`, они запрещены поимённо, и запрет выводится из объявлений (`w2cplatform/domain/rights.py`):

```python
    for s in _on_domain(specs):
        out += [f"!{s.domain_prefix}{b}/*" for b in s.domain.books]       # the books the holder keeps for each member
        # what a subsystem keeps for the domain: a row, or every row of a family (`kept: [x/]`)
        out += [f"!{s.domain_prefix}{k}{'*' if k.endswith('/') else ''}" for k in s.domain.kept]
        if s.domain.books or s.domain.kept:
            out += [f"!{s.domain_prefix}worker", f"!{s.domain_prefix}heartbeat"]   # its worker's slot on the holder
```

Агент пишет `domain/vms/sources` — книгу, которую унёс домой, — и не пишет `domain/vms/sources/srv-a` или `domain/vms/crossings`. Тест: `test_domain_secrets_vms.py::test_a_members_agent_neither_reads_nor_writes_the_signers_key`.

## Шаг 5 — Токены: вид, утверждения, срок — и никаких прав

Книги VMS несут токены: камере — толкать на приёмник, опрашивать его и забирать с него (`stream`), камере-триггеру — просить другую камеру (`ask`). Подписывает их подписывающий домена — единственный процесс с ключами домена (ADR 0032). Спека объявляет вид, его утверждения и срок:

```yaml
  tokens:
    stream: {lifetime: 86400, claims: [aud, ref]}
    ask: {lifetime: 86400, claims: [aud, ask, by, acts, up]}
```

Подписывающий выпускает только объявленное (`trust.tokens.DeclaredIssuer`): вид, которого не объявил никто, и утверждение, которого нет в списке вида, — отказ:

```python
    def issue(self, kind: str, subject: str, now: float | None = None, **claims) -> str:
        life = self.lifetime(kind)
        allowed = set(self.kinds[kind].get("claims") or ())
        extra = sorted(c for c in claims if c not in allowed or c in RESERVED_CLAIMS)
        if extra:
            raise Undeclared(f"a {kind} token names {', '.join(extra)}, which its spec does not declare")
        return self.issuer.issue(subject, life, now=now, kind=kind, **claims)
```

Два правила вокруг. **Токен прав не несёт** (ADR 0031): что может его субъект, решают гранты, а не токен, и ключа `grant` у вида токена загрузчик не примет. **Один вид — одна спека**: две спеки, объявившие `stream`, — отказ (`declared.token_kinds`), иначе токен одной подсистемы открывал бы дверь другой. Тест на `testsub`: `test_domain_platform.py::test_the_signer_issues_only_the_kinds_of_token_a_spec_declares_with_their_claims`.

Ключ при этом из процесса подписывающего не выходит. Воркер VMS просит токен через **сокет токенов** подписывающего, `SIGNER_TOKENS_UNIX` (`/run/w2c-signer/tokens.sock`), а не через сетевую дверь (`w2cplatform/domain/tokendoor.py`):

    GET  /kid               {"kid"} — ключ, которым подписывают сейчас
    GET  /kinds             {вид: {lifetime, claims}} — что объявили загруженные спеки
    POST /tokens/<вид>      {"sub", "claims": {...}} -> {"token"}; 400 на необъявленный вид или утверждение

Кто может спросить токен — тот, кто может открыть этот файл. Каталог сокета — `/run/w2c-signer`, `2750 w2c vms-vmsdomaintokens` (`deploy/domain/systemd/w2c-domain.tmpfiles`): сокет, который там делает подписывающий (`w2c`), берёт собственную группу сокета токенов, `<deployment>-<sub>domaintokens` (`w2cplatform/domain/rights.py::tokens_group`), с одним членом — юнитом воркера VMS, — и больше никто на коробке его не открывает (ADR 0031: группу сокета получает только процесс, которому токены нужны). Это не группа роли хранилища `vms-vmsdomain`: в ту входит всякий, кто открывает сокет роли, configstore тоже.

## Шаг 6 — Воркер `domainpart`: работа VMS у держателя

Книги нужно писать: читать отчёты членов, решать, кто пишет камеру, выпускать токены за половиной срока, опустошать книгу, которую больше не наполняет ни один сценарий. Это работа VMS, и делает её воркер VMS у держателя — `vms/domainpart/worker.py`, глагол `python3 -m vms domainpart`, юнит `vms-domainpart.service`:

```ini
[Service]
User=vms
Group=vms
SupplementaryGroups=vms-vmsdomain vms-vmsdomaintokens w2c-store w2c-secrets
Environment=PLATFORM_STORE=configstore:///run/configstore/vmsdomain.sock
Environment=SIGNER_TOKENS_UNIX=/run/w2c-signer/tokens.sock
Environment=DOMAINPART_PORT=8096
Environment=BOOKS_EVERY=5
...
ExecStart=/opt/w2c/bin/w2c-run.sh vms domainpart
```

**Права.** Процесс VMS работает от `vms`, не от `w2c` (ADR 0030), и ходит в хранилище держателя через сокет своей роли — `vmsdomain`. Роль выводится из спеки так же, как запреты агента (`rights.roles`, роль `<sub>domain` для подсистемы с `books` или `kept`): пишет свой префикс `domain/vms/*` и ничего больше; читает то, из чего сделаны книги, — набор ключей, топологию, список членов, указатель общих настроек, единицы подсистем и строки платформы. Роль с семейством субъектов (`names`) читала бы ещё людей и гранты; у VMS курса её нет.

**Слот.** У держателя может стоять второй экземпляр — запасной (М11). Книги пишет один: воркер берёт слот `domain/vms/worker` по CAS и держит его, а второй ждёт, пока первый не промолчит `SLOT_LOST` (45 с):

```python
    def claim(self) -> bool:
        """The slot: ours, or nobody's for `SLOT_LOST` seconds — then taken by CAS. False: another instance holds it."""
        items, idx = self.vars.get(SLOT)
        now = self.wall()
        if items and items.get("instance") != self.instance and now - float(items.get("at", 0)) < SLOT_LOST:
            return False
        try:
            self.vars.put(SLOT, {"instance": self.instance, "at": now}, cas=idx)
        except Conflict:
            return False
        return True
```

**Проход.** Каждые `BOOKS_EVERY` секунд — `Books.pass_once` (`vms/domainpart/books.py`), шаг за шагом в платформенном `Steps`: следовать за списком членов и топологией, обновить представление для чтения, потом книги в том порядке, в каком они друг от друга зависят, — источники, основные, опрос, вышестоящие, общие настройки, и последней книга запросов, потому что она читает решённое остальными. Шаг, который бросил, назван и посчитан, его книга остаётся последней записанной, а следующие шаги идут.

**Пульс.** После прохода воркер кладёт `domain/vms/heartbeat` в хранилище объектов держателя: `{ts, instance, passes, failing, …}`, а с ним — сколько записей книг и сценариев общих настроек он не смог прочитать (`garbled`, `GARBLED_SHOWN`).

**Дверь.** То, что VMS считает на домене, отдаёт воркер VMS, а не дверь держателя — у той нет маршрута, который ей пришлось бы понимать:

    GET /metrics    чего приёмники и передатчики членов не передали: кадры по причинам, шаги часов камеры,
                    сброшенное и дыры передатчика (`ingest.stream_metrics`, уроки 3 и 4)
    GET /catalog    что сценарий между камерами может назвать: действия, о которых одна камера может
                    просить другую, и по каждой камере — что она поднимает и умеет (`scenario.catalog`, урок 3)

Порт — `DOMAINPART_PORT` (8096). С `AUTH=1` (умолчание) дверь просит токен человека, проверенный набором ключей держателя, и право `view` на домен — как дверь домена.

Итог шага — три процесса платформы у держателя и один VMS. Подписывающий (`w2c-domain.service`) держит ключи и весь проход держателя; консоль домена (`w2c-domain-console.service`) ключей не держит и только читает; агент (`w2c-domainagent.service`) несёт строки (ADR 0032). Воркер VMS (`vms-domainpart.service`) пишет книги VMS и ничего больше.

## Шаг 7 — Что видит страница: `keys`, `shared`, `reports`, `witness`

**`keys`** — семьи ключей VMS для вкладки «Ключи» карточки домена. `GET /domain/keys` отдаёт каждый ключ под `domain/` в хранилищах держателя — строку с индексом и именами полей, объект с размером и возрастом, без значений и тел (`keysview.py`; «Архитектор», 2026-10-06). Закрывать секреты по имени поля оказалось мало: запись книги VMS несёт `token_secret` внутри значения, и вкладка показывала его целиком. Значения видны только у открытых половин, которые домен публикует сам (`keysview.PUBLIC`: набор ключей, корень, открытые ключи члена, сертификат кластера); содержимое книги придёт своим маршрутом, с полями, которые спека объявит показывать. Тест: `test_domain_platform.py::test_the_keys_view_shows_names_and_never_a_value_a_nested_token_or_an_objects_body`. Это список хранилища, так что ключ, для которого у страницы нет слов, всё равно виден. Какая семья что значит, говорит спека: `/spec` несёт `domain: {keys, shared, edit, view}`, а слова семей — `display.keys` (`{<id>: {title, about, absent}}`), страница сводит их по `id`. Платформа по ним не делает ничего. Тест держит, что каждый ключ, который VMS пишет на домене, — у держателя, у кластера записи и на камере, — попадает в объявленную семью и у каждой семьи есть слова: `test_domain_secrets_vms.py::test_every_key_the_vms_writes_on_the_domain_falls_into_a_family_its_spec_declares`.

**`shared: [folders, alarms, events_retention_days]`** — поля камеры, общее на домен значение которых держит домен (М12A, урок 12): папки, которые предлагает страница, тревоги площадки, которые добавляются к тревогам камеры, и срок хранения событий. Разрешает их платформа (`shared.resolve`: значение камеры, потом домена, потом `inherit` спеки) и отдаёт одной дверью консоли кластера — `GET /domain/shared/vms[?unit=<id>]`; маршрута VMS для этого нет. Правка общего документа с полем, которого спека не объявила, — 400: правка неверна по спекам сама по себе. Рядом — документ `auto`, `scenarios`: сценарии между камерами, которые домен держит целиком и подписывающий проверяет по их схеме ([урок 3, шаг 8](03-a-camera-nobody-can-reach.md)).

**`reports` и `witness`** — у `rec`. Член докладывает домену heartbeat'ы и снимок каждой подсистемы, а `reports: [ingest, polled/]` добавляет объявление приёмника `rec/ingest` и семью `rec/polled/<приёмник>` — когда каждая камера-член последний раз опрашивала этот приёмник, под именем члена. `witness: {report: polled, member_field: cam}` делает эту семью свидетелем; `cam` — поле записи «чья это камера», объявленное `fixed: true`, как платформа требует от поля, по которому свидетель называет члена. Приёмник называет камеру-члена тем членом, которым она является (субъект её токена потока), и домен ищет молчащего члена у свидетеля по его собственному имени: камера, чей агент молчит, а приёмник её слышал, — «жива, не докладывает» (М12A, [урок 13](../М12A_Domain/13-alarms-from-every-member.md)).

## Шаг 8 — Что держит границу

| Что | Тест |
|---|---|
| платформа не переходит границу, кроме записанного долга | `tests/test_boundary.py::test_the_platform_crosses_the_boundary_nowhere_but_where_the_debt_says_and_the_debt_only_shrinks` |
| домен целиком на `testsub`: каталог, вид, таблица, книги, токены, копия, семьи ключей, `names`, `edit`, общие поля | `tests/test_domain_platform.py` |
| каждый ключ VMS на домене — в объявленной семье | `tests/domainvms/test_domain_secrets_vms.py::test_every_key_the_vms_writes_on_the_domain_falls_into_a_family_its_spec_declares` |
| член через дверь получает только своё | `…::test_a_member_gets_only_its_own_rows_through_the_door` |
| ретранслятор отдаёт камере только её | `…::test_the_relay_gives_a_camera_only_its_own` |
| агент не пишет строк держателя и не читает ключа подписывающего | `…::test_a_members_agent_neither_reads_nor_writes_the_signers_key` |
| дверь воркера: `/metrics` и право `view` | `tests/domainvms/test_lesson17_chain.py::test_what_the_ingests_and_the_forwarder_did_not_hand_on_is_on_the_vms_domain_workers_metrics` |
| глагол и юнит воркера | `tests/test_deploy_units.py::test_the_units_run_the_entrypoints_the_package_has` |

---

## Что может пойти не так

| Симптом | Вероятная причина |
|---|---|
| `w2cplatform/domain` не собирается без `vms` | Домен зовёт код подсистемы. Смысл крючка — в спеку (`domain:`), в воркер (`domainpart`) или в страницу. |
| Спека не загружается: «not in the snapshot» | `ref` или поле `view` не из снимка. Домен читает единицу только из снимка — добавьте поле в `snapshot:`. |
| `PUT /domain/vms/cameras/<ref>` — 400 с полями | Поле не из `domain.edit`. Имя, папки, метки, сроки правятся в консоли кластера камеры. |
| Книга не доходит до члена | Её нет в `domain.books`, или воркер пишет её не под `<книга>/<член>`. Агент несёт только объявленное. |
| Импорт `vms.domainpart` падает: «declares no book» | Книгу переименовали в спеке и не в коде. Так и задумано: падает при импорте, а не у члена. |
| После переноса домена камеры одного кластера снова пишет другой | Решение лежало не в `kept`, и копия его не унесла. Решения — в `kept`; книги пересчитываются. |
| Агент члена пишет в `domain/vms/crossings` | Запреты агента сгенерированы не из этих спек. Файл прав — `python3 -m w2cplatform.cluster rights` по загруженным спекам. |
| Подписывающий отказывает: «which its spec does not declare» | Воркер просит утверждение, которого нет в `domain.tokens.<вид>.claims`. Объявите или не просите. |
| Воркер не получает токенов: дверь не отвечает | Сокет `/run/w2c-signer/tokens.sock` не той группы или воркер не в `vms-vmsdomaintokens`. Каталог — из `w2c-domain.tmpfiles`. |
| Книги пишут два экземпляра по очереди | Слот не берётся по CAS. `domain/vms/worker`, `SLOT_LOST`. |
| На вкладке «Ключи» ключ VMS в «прочих» | Ключ не попал ни в одну семью `domain.keys`. Тест семей это ловит. |

## Итог

- Домен платформы знает VMS по разделу `domain:` трёх спек и ни по чему больше; крючков нет (ADR 0002, ADR 0010).
- `ref` ставит камеры в каталог домена, `view` — их поля в общий вид, `edit` — что дверь держателя пускает в правку: у VMS только «вкл/выкл» (ADR 0031).
- `books` — строки держателя по одной на члена, `domain/vms/<книга>/<член>`; агент уносит их домой как `domain/vms/<книга>` через дверь держателя, не читая; секреты в них запечатаны на каждом шаге (ADR 0024).
- `kept` — решения VMS для всего домена: они в копии держателя и восстанавливаются переносом; `tables` — что из них отдаёт дверь; агенту всё это запрещено поимённо, и запрет выводится из спеки.
- `tokens` — виды, утверждения и сроки; подписывающий выпускает только объявленное, через свой сокет, и права в токене нет.
- Работа — воркер VMS `domainpart` у держателя: роль `vmsdomain`, слот по CAS, пульс, дверь с `/metrics` и `/catalog`; ключа у него нет (ADR 0032).
- `keys`, `shared`, `reports`, `witness` — семьи ключей для страницы, общие поля, отчёт и свидетель для тревог.

## Упражнения

1. Добавьте VMS книгу `presets` — для каждой камеры-члена список пресетов, которые разрешено вызывать из центра. Что меняется в спеке, в `keys.py`, в файле прав, в семьях ключей и в тестах? Что не меняется в `w2cplatform/domain`?
2. Продукт объявляет `names: {stream-clients/: {exclusive_with: domain/users, grant: view}}`. Какой строкой `kept` это должно сопровождаться, что начинает читать роль `vmsdomain` и какие две записи платформа теперь отказывает?
3. Почему `domain/vms/roads` в `kept`, а `domain/vms/primaries` — в `books`? Что будет после переноса домена, если поменять их местами?
4. `edit` у VMS — `[enabled]`. Оператор центра хочет переименовать камеру объекта. Где он это делает, и что увидит центр, пока кластер камеры выключен?
5. Сокет токенов открыт группе `w2c-store`. Кто ещё на держателе сможет выпустить токен `stream` на любую камеру, и что этот токен откроет?

## Что дальше

Объявления на месте, воркер у держателя пишет книги. [**Урок 2**](02-a-stream-from-another-cluster.md) пишет первую из них — книгу источников: регистратор серверной пишет камеру, которая сама кластер, и находит её не в heartbeat'ах своего кластера, а в книге, которую агент принёс домой.
